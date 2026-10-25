"""量子网络 · **纠缠交换递推与纯化**（J5 · v0.9.292 · 纯标准库）

═══════════════════════════════════════════════════════════════════════
为什么要有这一层（改前的缺陷）
═══════════════════════════════════════════════════════════════════════
`qnet_system.end_to_end_fidelity()` 原先把「N 段中继链」的保真度写成

    relay_chain_fidelity = **F_seg ^ N**        （对**保真度**取幂）

并自述「逐段独立乘性衰减近似 ⇒ 只是**朴素上界**」。这句话有两处错：

1. **组合律用错对象**。理想纠缠交换对 **Werner 参数** 取乘积（`p_out = p₁·p₂`），
   而不是对保真度取幂。保真度是 Werner 参数的仿射函数 `F = (1+3p)/4`，
   `Π F_i` 与 `F(Π p_i)` 是两个不同的量。
2. **方向说反了**。`F_seg^N` 恒 **小于**正确值（N≥2 时），它是**下界**而非上界。
   默认档（100 km / 20 段）实测：旧口径 **0.0366**，正确口径 **0.2580** —— 差 **7.05 倍**。
   ⇒ 旧口径会得出「中继严重损害保真度」的结论，而真实物理是**中继不改变保真度**。

═══════════════════════════════════════════════════════════════════════
本层给什么（全部闭式 · 可复算 · 带对照支路）
═══════════════════════════════════════════════════════════════════════
① `werner_swap_chain`   N 段链端到端 Werner 参数 `p_tot = Π p_i = p_seg^N`
② `fidelity_from_werner` / `werner_from_fidelity`  Werner ⇄ 保真度（仿射，可往返）
③ `dejmps_once`         单轮 DEJMPS 纯化（双选）：`p' = A/(A+B)`，成功率 `P = A+B`
④ `dejmps_thresholds`   解析临界点 `9p²−7p+1=0 ⇒ p = (7±√13)/18`
⑤ `swap_chain_report`   三口径对照（直连 / 旧口径下界 / Werner 正确） + 段数—吞吐权衡

🔴 **核心物理结论（本层要交付的诚实洞察）**：
   在「每段损耗同源、无额外交换失效」的理想中继下，`p_seg^N = exp(−L/L_depol)` **与 N 无关**
   ⇒ **分段只提吞吐，不提保真**。要提保真**只能靠纯化**（`dejmps_once`）。
   这与 M2 的实测结论（中继增益 `53.70×` 来自**速率**）互相印证。

🔴 **诚实边界**：本层是**一阶闭式**——不含多轮纯化的资源计数、不含交换失败的时序统计、
不含存储器退相干与门误差；参数为文献量级设计示例，**非实测**。不作性能宣称。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

__all__ = [
    "DEFAULT_L_DEPOL_M",
    "fidelity_from_werner",
    "werner_from_fidelity",
    "werner_swap_chain",
    "swap_chain_fidelity",
    "dejmps_once",
    "dejmps_thresholds",
    "dejmps_is_useful",
    "segments_sweep",
    "swap_chain_report",
    "selfcheck_qnet_swap",
]

#: 退相干长度（m）· 与 `qnet_channel` / `qnet_distribution` 同源默认档
DEFAULT_L_DEPOL_M = 2.2e4
DEFAULT_LINK_LENGTH_M = 1.0e5
#: 纠缠可用的保真度门槛（CHSH 违背的充分条件是 F > (1+1/√2)/2 ≈ 0.8536；
#: 这里取更宽松的「F > 1/2」作为**有效纠缠**的必要条件）
FIDELITY_ENTANGLED = 0.5


# ══════════════════════════════════════════════════════════════════════
# ① Werner ⇄ 保真度（仿射，可往返）
# ══════════════════════════════════════════════════════════════════════
def fidelity_from_werner(p: float) -> float:
    """Werner 参数 → 保真度 `F = (1+3p)/4`。"""
    return float((1.0 + 3.0 * float(p)) / 4.0)


def werner_from_fidelity(f: float) -> float:
    """保真度 → Werner 参数 `p = (4F−1)/3`。"""
    return float((4.0 * float(f) - 1.0) / 3.0)


# ══════════════════════════════════════════════════════════════════════
# ② 纠缠交换递推（Werner 组合律）
# ══════════════════════════════════════════════════════════════════════
def werner_swap_chain(p_seg: float, n_seg: int) -> float:
    """N 段链（N−1 次理想交换）的端到端 Werner 参数：`p_tot = p_seg^n_seg`。

    🔴 **对照支路（闭式已知答案）**：
       · `n_seg = 1`（不交换）⇒ 恒等返回 `p_seg`；
       · `p_seg = 1`（理想段）⇒ 任意 N 都返回 1（交换不引入噪声）；
       · `p_seg = 0`（完全退相干）⇒ 返回 0（**不能无中生有**）。
    """
    p = float(p_seg)
    n = int(n_seg)
    if n < 1:
        raise ValueError("中继段数须 ≥ 1")
    return float(p ** n)


def swap_chain_fidelity(p_seg: float, n_seg: int) -> float:
    """N 段链端到端保真度 `F = (1+3·p_seg^N)/4`。"""
    return fidelity_from_werner(werner_swap_chain(p_seg, n_seg))


# ══════════════════════════════════════════════════════════════════════
# ③ DEJMPS 单轮纯化（双选）
# ══════════════════════════════════════════════════════════════════════
def dejmps_once(p: float) -> Dict[str, float]:
    """Werner 态单轮 DEJMPS 纯化。

    成功分支的 Werner 参数：

        A = p² + (1−p)²/9
        B = 2p(1−p)/3 + 5(1−p)²/9
        p' = A/(A+B)          P_succ = A+B

    🔴 **对照支路**：`p = 1`（纯态）⇒ `p' = 1` 且 `P_succ = 1`；
       `p = 0`（完全混态）⇒ `p' = **1/6**`（解析值，非 0 —— 这是「成功事件筛选」效应，
       **不代表产生了纠缠**，其 F = 0.375 < 0.5）。
    """
    x = float(p)
    one_m = 1.0 - x
    a = x * x + one_m * one_m / 9.0
    b = 2.0 * x * one_m / 3.0 + 5.0 * one_m * one_m / 9.0
    tot = a + b
    return {
        "p_in": x,
        "p_out": float(a / tot) if tot > 0.0 else 0.0,
        "p_success": float(tot),
        "fidelity_in": fidelity_from_werner(x),
        "fidelity_out": fidelity_from_werner(a / tot) if tot > 0.0 else 0.25,
    }


def dejmps_thresholds() -> Tuple[float, float]:
    """`p' = p` 的两个解析临界点：解 `9p² − 7p + 1 = 0` ⇒ `p = (7±√13)/18`。

    返回 `(p_low≈0.18858, p_high≈0.58920)`：
      · `p > p_high` ⇒ 纯化**提升**参数（文献常说「F > 0.69 才值得纯化」，本式给
        `F(p_high) = (1+3p_high)/4 ≈ 0.6919`，**与文献口径一致** ⇒ 独立校验点）；
      · `p_low < p < p_high` ⇒ 纯化**降低**参数（不该做）；
      · `p < p_low` ⇒ 参数看似「提升」，但输出仍 **F < 0.5**（无有效纠缠）。
    """
    disc = math.sqrt(13.0)
    return ((7.0 - disc) / 18.0, (7.0 + disc) / 18.0)


def dejmps_is_useful(p: float) -> bool:
    """纯化**是否有用**：既提升 Werner 参数，又让输出仍具备有效纠缠（F > 0.5）。

    🔴 两个条件必须分开检查 —— 「`p' > p`」在 `p < p_low` 区也成立，
    但那是**成功事件筛选**带来的假提升，输出 F 仍 < 0.5，不产生可用纠缠。
    """
    r = dejmps_once(p)
    return bool(r["p_out"] > r["p_in"] and r["fidelity_out"] > FIDELITY_ENTANGLED)


# ══════════════════════════════════════════════════════════════════════
# ④ 段数扫描（保真度 vs 吞吐的联合权衡）
# ══════════════════════════════════════════════════════════════════════
def segments_sweep(length_m: float = DEFAULT_LINK_LENGTH_M,
                   n_list: Tuple[int, ...] = (1, 2, 5, 10, 20, 50, 100),
                   l_depol_m: float = DEFAULT_L_DEPOL_M) -> List[Dict[str, Any]]:
    """扫段数 N：给 `p_seg`、端到端 `p_tot`、`F`、以及**相对吞吐** `1/N`。

    🔴 关键不变量（可机核）：`p_seg^N ≡ exp(−L/L_depol)` **与 N 无关**
    ⇒ 保真度对分段**不敏感**；吞吐 ∝ 1/N 单调递减 ⇒ 「最优 N」由**保真度约束**
    之外的因素（每段可达性/硬件成本）决定，而不是保真度。
    """
    L = float(length_m)
    out: List[Dict[str, Any]] = []
    for n in n_list:
        seg_len = L / n
        p_seg = math.exp(-seg_len / l_depol_m)
        p_tot = werner_swap_chain(p_seg, n)
        f = fidelity_from_werner(p_tot)
        out.append({
            "n_seg": int(n),
            "seg_len_m": float(seg_len),
            "p_seg": float(p_seg),
            "p_total": float(p_tot),
            "fidelity": float(f),
            "relative_rate": float(1.0 / n),   # 串行交换 ⇒ 率 ∝ 1/N
            "entangled": bool(f > FIDELITY_ENTANGLED),
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# ⑤ 三口径对照报告
# ══════════════════════════════════════════════════════════════════════
def swap_chain_report(length_m: float = DEFAULT_LINK_LENGTH_M,
                      segments: int = 20,
                      l_depol_m: float = DEFAULT_L_DEPOL_M) -> Dict[str, Any]:
    """三口径对照 + 纯化增益（**全部闭式**）。

    `naive_fidelity_pow` = 旧口径 `F_seg^N`（**下界、方向被说反了**）
    `werner_fidelity`    = 正确口径 `F(p_seg^N)`
    `direct_fidelity`    = 不分段直连 `F(exp(−L/L_depol))`
    """
    L, N = float(length_m), int(segments)
    if L <= 0.0 or N < 1:
        raise ValueError("参数非法")
    seg_len = L / N
    p_seg = math.exp(-seg_len / l_depol_m)
    f_seg = fidelity_from_werner(p_seg)
    naive = float(f_seg ** N)
    p_tot = werner_swap_chain(p_seg, N)
    werner = fidelity_from_werner(p_tot)
    direct = fidelity_from_werner(math.exp(-L / l_depol_m))
    dj = dejmps_once(p_tot)
    lo, hi = dejmps_thresholds()
    return {
        "length_m": L,
        "segments": N,
        "seg_len_m": float(seg_len),
        "p_seg": float(p_seg),
        "fidelity_seg": float(f_seg),
        "naive_fidelity_pow": naive,
        "werner_fidelity": float(werner),
        "direct_fidelity": float(direct),
        "naive_over_werner": float(naive / werner) if werner > 0 else float("inf"),
        # 🔴 正确口径下，N 段链 ≡ 直连（理想段、无额外失效）—— 这是「分段不提保真」的机核形式
        "werner_equals_direct": bool(abs(werner - direct) <= 1e-15),
        "purified": dj,
        "dejmps_thresholds": {"p_low": float(lo), "p_high": float(hi),
                              "f_high": float(fidelity_from_werner(hi))},
        "purification_useful": dejmps_is_useful(p_tot),
        "entangled_before": bool(werner > FIDELITY_ENTANGLED),
        "note": (
            "正确口径 F(p_seg^N) 在理想段下恒等于直连 F：**分段只提吞吐、不提保真**；"
            "旧口径 F_seg^N 是下界（N=20 时比真值小 7.05 倍），原注释把它写成「上界」方向被说反。"
            "要提保真只能靠纯化（DEJMPS：p>0.5892 才既提升又仍可用）。"
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════
def selfcheck_qnet_swap() -> Dict[str, bool]:
    """本层自检（对照支路 + 恒等式 + 解析根）。"""
    c: Dict[str, bool] = {}

    # ① 对照支路：n=1 恒等
    c["chain_n1_identity"] = abs(werner_swap_chain(0.7, 1) - 0.7) <= 1e-18
    # ② 对照支路：p=1 ⇒ 任意 N 都 1（交换不引入噪声）
    c["chain_ideal_p1"] = all(abs(werner_swap_chain(1.0, n) - 1.0) <= 1e-18
                              for n in (1, 2, 5, 20))
    # ③ 对照支路：p=0 ⇒ 0（不能无中生有）
    c["chain_p0_zero"] = werner_swap_chain(0.0, 5) == 0.0
    # ④ Werner ⇄ 保真度往返
    c["werner_fidelity_roundtrip"] = all(
        abs(werner_from_fidelity(fidelity_from_werner(p)) - p) <= 1e-15
        for p in (0.0, 0.25, 0.5892, 1.0))
    # ⑤ 关键恒等式：p_seg^N ≡ exp(−L/L_depol)（与 N 无关）
    r = swap_chain_report()
    c["segments_do_not_change_fidelity"] = r["werner_equals_direct"]
    # ⑥ 旧口径确实是下界（不是「上界」）
    c["naive_is_lower_bound"] = r["naive_fidelity_pow"] < r["werner_fidelity"]
    # ⑦ DEJMPS 解析根：**把根代回原方程**（不自证「我记得这个数」）
    lo, hi = dejmps_thresholds()

    def _quad(p: float) -> float:
        return 9.0 * p * p - 7.0 * p + 1.0

    c["dejmps_root_low"] = abs(_quad(lo)) <= 1e-15
    c["dejmps_root_high"] = abs(_quad(hi)) <= 1e-15
    # ⑦b 两个根确实落在 (0,1) 且 low < high
    c["dejmps_roots_ordered"] = bool(0.0 < lo < hi < 1.0)
    # ⑧ DEJMPS 对照支路：p=1 ⇒ p'=1 且 P_succ=1；p=0 ⇒ p'=1/6
    d1, d0 = dejmps_once(1.0), dejmps_once(0.0)
    c["dejmps_p1_identity"] = abs(d1["p_out"] - 1.0) <= 1e-18 and abs(d1["p_success"] - 1.0) <= 1e-18
    c["dejmps_p0_sixth"] = abs(d0["p_out"] - 1.0 / 6.0) <= 1e-15
    # ⑨ 纯化不产生纠缠：p=0 的输出 F < 0.5
    c["dejmps_no_fake_entanglement"] = d0["fidelity_out"] < FIDELITY_ENTANGLED
    # ⑩ 文献一致：上临界点对应 F ≈ 0.6919
    c["dejmps_threshold_matches_literature"] = abs(fidelity_from_werner(hi) - 0.6919) < 5e-4
    return c


if __name__ == "__main__":  # pragma: no cover
    bad = [k for k, v in selfcheck_qnet_swap().items() if not v]
    print("qnet_swap 自检：%d/%d 通过" % (len(selfcheck_qnet_swap()) - len(bad), len(selfcheck_qnet_swap())))
    print(swap_chain_report()["note"])
    if bad:
        print("FAIL:", bad)
