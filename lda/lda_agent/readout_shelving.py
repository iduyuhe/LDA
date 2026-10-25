# -*- coding: utf-8 -*-
"""读出保真度 · **shelving / 有效寿命层**（v0.9.305 · 补 `G-READSHELV`）。

═══ 为什么有这个模块 ═══
v0.9.304 判 A2 时算出一条硬结论：把 `lda_agent/readout_fidelity.py` 的预算模型
用在 Chen et al.（npj Quantum Inf. 9 (2023)，DOI 10.1038/s41534-023-00689-6）
的器件上（`t_m = 140 ns`、该 qubit `T01 = 6.18 µs`），**取极限乐观（ε→0）也只能到**

    F_max = (1 + (1 − t_m/T1))/2 = 0.98867  <  实测 0.995

**上界就差 0.63 个百分点，不是参数没调好** —— 两档完全不同的 χ/κ/n̄ 参数算出来
`F` 都停在 0.98867，因为上界只由 `t_m/T1` 决定。根因是旧模型

    F1 = (1−ε)·(1 − t_m/T1)          ← 把整个读出期都记成「|1⟩ 在按 T1 衰减」

而实验用的是 **shelving**：读出前先用 π12（必要时再 π23）把布居搬到更高的能级，
使 |1⟩→|0⟩ 这条**致错通道**变成「多级串联」——要走完 n 步才落到 |0⟩，
而每多一步就要多乘一个「这一步还没走完」的因子。

═══ 🔴 核心结论（闭式 · 可当作定理）═══
设 shelving 级数为 `n`（`n=1` 即无 shelving），并假设**理想等比阶梯**
`1/T12 = 2/T01`、`1/T23 = 3/T01`、…（即第 i 级向下一级的速率 = `i/T1`），则

    P_decay(t_m, T1; n) = (1 − e^(−t_m/T1))^n

**证明就是二项式定理**：从第 n+1 级走到第 1 级的吸收时间 = Σ_{k=1..n} Exp(k/T1)，
其 CDF 的拉普拉斯反演给出 `1 − Σ_j c_j e^(−j·t/T1)`，其中
`c_j = Π_{k≠j} k/(k−j) = (−1)^(j−1)·C(n, j)` ⇒ 恰好是 `(1 − e^(−x))^n` 的二项展开。
（n=1..4 已在自检里与数值 ODE 逐点对拍，残差 < 1e-9。）

**三条推论（都写成了判据）**：
1. `n=1` ⇒ `1 − e^(−x)`，与旧模型的线性近似 `x = t_m/T1` **差一个闭式**：
   `Δ = x − (1 − e^(−x)) = x²/2 − x³/6 + …`（`x=2.27%` 时 Δ = 2.57e-4）。
   ⇒ 旧模型的偏差**不是随机的**，是「把指数截断到一阶」，可以被精确算出来。
2. **每加一级 shelving，衰减误差被再乘一个 `(1−e^(−x))`** —— 收益是乘性/指数级的，
   不是线性的。这解释了为什么 π12 一步就把 2.24% 压到 0.05%。
3. 因此「读出保真度上界」必须写成 `F_max(n) = (1 + (1 − P_decay(n)))/2`，
   **`n` 是序列参数、不是拟合参数** —— 不许拿 `n` 或 `T1_eff` 去凑实测值（凑 = 循环自证）。

═══ 与实测的对拍（披露级，**不作锚**）═══
同论文三档（`t_m=140 ns`、`T1=6.18 µs`）：

| 序列 | 本文闭式 | 论文报告 | 绝对差（百分点） |
|---|---|---|---|
| 无 shelving (n=1) | 2.2395 % | 2.24 % | **0.0005** |
| π12 (n=2) | 0.05016 % | 0.057 % | 0.0068 |
| π12+π23 (n=3) | 1.1214e-3 % | 8.7e-4 % | 2.5e-4 |

🔴 **为什么只作披露、不作锚**：`n=1` 那条论文用的就是 `1−e^(−t/T1)`（同一个式子），
`n≥2` 的数值多半也出自论文 SI 的速率方程 —— **与本文同源**。同源对拍不能证明物理
（同 E10「不得由 FSR 反演 n_g」、E1 的 `n_eff` 改判 `n_g`）。真正被证的是
**本仓模型能不能达到那个保真度**，而下表给出了肯定答案：

| n | F_max |
|---|---|
| 1 | 0.98880 ← 本模块（精确指数）的天花板，**达不到 0.995** |
| 2 | 0.99975 ✓ |
| 3 | 0.99999 ✓ |

⚠️ **与 v0.9.303/304 报的 0.98867 的差**：那两版用的是**旧模型**（`F1 = (1−ε)(1 − t_m/T1)`，
即一阶截断），`F_max = (1 + (1−x))/2 = 0.98867`。本模块 `n=1` 用**精确指数**，给 `0.98880`。
两者差 **1.3e-4 = Δ/2 = (x − (1−e^(−x)))/2**，是**可精确预测的截断差**，不是模型改了口径。
（判据 ③ 把这条差钉死成 `x²/2 − x³/6`，防以后有人"顺手"改一个数而没人发现。）

═══ 边界（必须与结论一起读）═══
* 等比阶梯 `i/T1` 是**理想假设**：真实器件的 `T12/T01`、`T23/T01` 未必严格等于 2、3。
  本文**不**用实测去反推这两个比值（那是拟合）；若将来拿到独立测得的比值，
  把 `decay_error` 的阶梯速率换成实测比值即可，闭式仍成立（换成一般速率的卷积）。
* 不含：shelving 脉冲本身的**非绝热误差**（π12 不完备 ⇒ 有残余布居留在 |1⟩）、
  读出驱动下的 AC Stark 展宽、光子数引起的额外跃迁。
  ⇒ 本模块给的是**衰减通道的下界收益**，不是完整读出预算。
* 不含测量错误相关（assignment matrix 的非对角元）。

净增 0 锚（`ANCHORABLE = False`）：本模块交付的是**能力**（模型能算到 0.995 了），
不是新锚。锚数的变化见 `docs/GAP_SETTLEMENT.md`。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

ANCHORABLE = False
ROLE = ("G-READSHELV 闭合件：读出保真度的 shelving / 有效寿命层。"
        "闭式 P_decay = (1 − e^(−t/T1))^n（n = shelving 级数），"
        "用于把读出保真度上界从「只看 t_m/T1」扩展到「看脉冲序列」。净增 0 锚。")

#: 论文锚点（Chen et al., npj Quantum Inf. 9 (2023), DOI 10.1038/s41534-023-00689-6）
#: —— 这三个数是**公开实测工作**报告出来的，用作**披露级**对照，不进判决路径。
PAPER = {
    "doi": "10.1038/s41534-023-00689-6",
    "t_m_ns": 140.0,
    "t1_us": 6.18,
    "decay_error_pct": {1: 2.24, 2: 0.057, 3: 8.7e-4},
    "assignment_fidelity_2state": 0.995,
}


# ---------------------------------------------------------------------------
# 核心：阶梯衰减闭式
# ---------------------------------------------------------------------------
def decay_error(t_m_s: float, t1_s: float, n_shelve: int = 1) -> float:
    """读出窗口内「落到基态」的概率（致错通道）· 闭式。

    Args:
        t_m_s: 读出窗口时长（s）
        t1_s: 量子比特 T1（s）
        n_shelve: shelving 级数（`n=1` = 无 shelving；`n=2` = 打了 π12；`n=3` = π12+π23）

    Returns:
        `(1 − e^(−t_m/T1)) ** n`

    Raises:
        ValueError: 非物理输入（`t_m_s<0` / `t1_s<=0` / `n_shelve<1`）
    """
    t_m_s = float(t_m_s)
    t1_s = float(t1_s)
    n = int(n_shelve)
    if not (t_m_s >= 0.0) or not math.isfinite(t_m_s):
        raise ValueError(f"t_m_s 须为有限非负数，收到 {t_m_s!r}")
    if not (t1_s > 0.0) or not math.isfinite(t1_s):
        raise ValueError(f"t1_s 须为有限正数，收到 {t1_s!r}")
    if n < 1:
        raise ValueError(f"n_shelve 须 ≥1（1 = 无 shelving），收到 {n_shelve!r}")
    x = t_m_s / t1_s
    base = -math.expm1(-x)                 # = 1 − e^(−x)，小 x 下比 1−exp 更准
    return float(base ** n)


def decay_error_ladder_ode(t_m_s: float, t1_s: float, n_shelve: int = 1,
                           n_step: int = 4000) -> float:
    """**同一物理的独立数值解**（RL 阶梯主方程的 RK4 积分），供判据对拍用。

    能级 `1..N`（`1` = 基态 / 致错态，`N = n_shelve+1` = 读出态）。
    第 `i` 级向下的衰减率 `r_i = (i−1)/T1`（`r_1`：`i=1` 无向下通道 ⇒ 0）。

        dP_i/dt = r_{i+1}·P_{i+1} − r_i·P_i

    返回 `P_1(t_m)`。⇒ 与 `decay_error` 的闭式**逐点对拍**（残差应在 1e-9 内）。
    """
    n = int(n_shelve)
    if n < 1:
        raise ValueError(f"n_shelve 须 ≥1，收到 {n_shelve!r}")
    t1 = float(t1_s)
    big_n = n + 1
    rate = [0.0] * (big_n + 1)                     # rate[0] 占位；rate[i] = (i−1)/T1
    for i in range(1, big_n + 1):
        rate[i] = (i - 1) / t1
    p = [0.0] * (big_n + 1)
    p[big_n] = 1.0

    def deriv(q: List[float]) -> List[float]:
        d = [0.0] * (big_n + 1)
        for i in range(1, big_n + 1):
            down = rate[i] * q[i]
            up = rate[i + 1] * q[i + 1] if i + 1 <= big_n else 0.0
            d[i] = up - down
        return d

    tt = float(t_m_s)
    h = tt / n_step
    for _ in range(n_step):
        k1 = deriv(p)
        p2 = [p[i] + 0.5 * h * k1[i] for i in range(big_n + 1)]
        k2 = deriv(p2)
        p3 = [p[i] + 0.5 * h * k2[i] for i in range(big_n + 1)]
        k3 = deriv(p3)
        p4 = [p[i] + h * k3[i] for i in range(big_n + 1)]
        k4 = deriv(p4)
        p = [p[i] + h / 6.0 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i])
             for i in range(big_n + 1)]
    return float(p[1])


def linear_model_delta(t_m_s: float, t1_s: float) -> Dict[str, float]:
    """旧模型（`P = t_m/T1` 一阶截断）与闭式（`P = 1 − e^(−x)`）的**闭式差**。

    `Δ = x − (1 − e^(−x))`，即「指数被截断到一阶」丢掉的那部分。
    判据用它把「新旧不一致」变成**可精确预测的量**，而不是「应该差不多」。
    """
    x = float(t_m_s) / float(t1_s)
    exact = -math.expm1(-x)
    return {"x": x, "linear": x, "exact": exact, "delta": x - exact,
            "series_first_term": 0.5 * x * x}


def readout_fidelity_shelved(chi_ghz: float, kappa_r_ghz: float, nbar: float,
                             eta: float, N_amp: float, t_m_s: float,
                             t1_s: float, n_shelve: int = 1) -> Dict[str, float]:
    """带 shelving 层的单发读出保真度预算（SNR 复用 `readout_fidelity.readout_snr`）。

    `F1 = (1−ε)·(1 − P_decay(n))`，`P_decay` 由 `decay_error` 给（**不是** `t_m/T1`）。
    `n_shelve=1` 时退化为「精确指数」版本，与旧线性版的差由 `linear_model_delta` 给出。
    """
    try:
        from .readout_fidelity import readout_snr
    except ImportError:                                   # 脚本方式直接运行
        from readout_fidelity import readout_snr  # type: ignore[no-redef]

    snr = readout_snr(float(chi_ghz), float(kappa_r_ghz), float(nbar),
                      float(eta), float(N_amp), float(t_m_s))
    eps = 0.5 * math.erfc(snr / math.sqrt(2.0))
    p_dec = decay_error(t_m_s, t1_s, n_shelve)
    f0 = 1.0 - eps
    f1 = (1.0 - eps) * (1.0 - p_dec)
    return {"t_m_s": float(t_m_s), "n_shelve": int(n_shelve), "snr": snr,
            "eps": eps, "p_decay": p_dec, "F0": f0, "F1": f1,
            "F": (f0 + f1) / 2.0,
            "F_max": (1.0 + (1.0 - p_dec)) / 2.0}


def fidelity_ceiling(t_m_s: float, t1_s: float, n_shelve: int = 1) -> float:
    """极限保真度（`ε→0`）—— **与 χ/κ/n̄ 全部无关**，只由 `t_m/T1` 与 `n` 决定。

    这就是 v0.9.304 那条硬结论的来源：`n=1` 时它给 0.98867，够不到实测的 0.995。
    """
    return (1.0 + (1.0 - decay_error(t_m_s, t1_s, n_shelve))) / 2.0


def paper_benchmark() -> List[Dict[str, Any]]:
    """与公开实测工作（`PAPER`）三档衰减误差的对照（**披露级，不进判决**）。"""
    t_m = PAPER["t_m_ns"] * 1e-9
    t1 = PAPER["t1_us"] * 1e-6
    out: List[Dict[str, Any]] = []
    for n, ref_pct in sorted(PAPER["decay_error_pct"].items()):
        pred_pct = decay_error(t_m, t1, n) * 100.0
        out.append({
            "n_shelve": n,
            "predicted_pct": pred_pct,
            "reported_pct": ref_pct,
            "abs_diff_pp": abs(pred_pct - ref_pct),
            "fidelity_ceiling": fidelity_ceiling(t_m, t1, n),
        })
    return out


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = True) -> Tuple[int, int, List[str]]:
    """模块自检。返回 `(npass, total, lines)`；`lines` 每行以 `[PASS]`/`[FAIL]` 开头。"""
    lines: List[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}"
                     + (f"  |  {detail}" if detail else ""))

    t1 = PAPER["t1_us"] * 1e-6
    t_m = PAPER["t_m_ns"] * 1e-9
    x = t_m / t1

    # ① 闭式 ⇄ 数值 ODE 逐点对拍（n=1..4）
    worst = 0.0
    for n in (1, 2, 3, 4):
        cl = decay_error(t_m, t1, n)
        od = decay_error_ladder_ode(t_m, t1, n)
        worst = max(worst, abs(cl - od))
    chk("① 闭式 (1−e^(−x))^n ⇄ 阶梯主方程 RK4 数值解（n=1..4）残差 < 1e-9",
        worst < 1e-9, f"max|Δ|={worst:.2e}")

    # ② n=1 必须**精确**退化为单指数（这是"通式退化为特例"的对照支路）
    chk("② n=1 精确退化为单指数 1−e^(−x)（对照支路 · 不是「差不多」）",
        abs(decay_error(t_m, t1, 1) - (-math.expm1(-x))) < 1e-15,
        f"闭式={decay_error(t_m, t1, 1):.12e} 单指数={-math.expm1(-x):.12e}")

    # ③ 与旧线性模型的差必须等于闭式 Δ = x − (1−e^(−x))；且落在其交错级数的夹逼内
    #    Δ = x²/2 − x³/6 + x⁴/24 − …（交错级数 ⇒ |Δ − (x²/2 − x³/6)| ≤ x⁴/24）
    d = linear_model_delta(t_m, t1)
    two_term = d["x"] ** 2 / 2.0 - d["x"] ** 3 / 6.0
    rem = d["x"] ** 4 / 24.0
    chk("③ 与旧一阶截断模型的差 ≡ Δ = x−(1−e^(−x))，且落在交错级数夹逼内（≤x⁴/24）",
        abs(d["delta"] - (d["x"] - d["exact"])) < 1e-18
        and abs(d["delta"] - two_term) <= rem
        and two_term < d["delta"] < d["series_first_term"],
        f"Δ={d['delta']:.9e} ∈ (x²/2−x³/6={two_term:.9e}, x²/2={d['series_first_term']:.9e})，"
        f"余项界 x⁴/24={rem:.2e}，实测余项={d['delta']-two_term:.2e}")

    # ④ 单调：每加一级 shelving，衰减误差必须严格下降
    seq = [decay_error(t_m, t1, n) for n in (1, 2, 3, 4)]
    chk("④ 单调性：n↑ ⇒ P_decay 严格↓（shelving 有收益，且收益乘性）",
        all(seq[i] > seq[i + 1] > 0.0 for i in range(len(seq) - 1)),
        " → ".join(f"{v:.3e}" for v in seq))

    # ⑤ 乘性律：P(n+1) / P(n) 必须恒等于 (1−e^(−x))（这正是闭式的结构）
    ratios = [seq[i + 1] / seq[i] for i in range(len(seq) - 1)]
    base = -math.expm1(-x)
    chk("⑤ 乘性律：P(n+1)/P(n) ≡ (1−e^(−x))（shelving 收益是「再乘一个因子」）",
        all(abs(r - base) < 1e-12 for r in ratios),
        f"比值={['%.6f' % r for r in ratios]} 基准={base:.6f}")

    # ⑥ 极限保真度：n=1 够不到论文的 0.995，n≥2 够得到（这就是那条硬结论）
    f1c, f2c = fidelity_ceiling(t_m, t1, 1), fidelity_ceiling(t_m, t1, 2)
    chk("⑥ 🔴 上界判据：n=1 达不到实测 0.995，n=2 达到（旧模型的真天花板）",
        f1c < PAPER["assignment_fidelity_2state"] <= f2c,
        f"F_max(n=1)={f1c:.5f} < 0.995 ≤ F_max(n=2)={f2c:.5f}")

    # ⑦ 论文三档披露级对照（绝对百分点，不用相对误差——分母趋零时相对误差无意义）
    rows = paper_benchmark()
    ok7 = all(r["abs_diff_pp"] < 0.01 for r in rows)
    chk("⑦ 论文三档对照：绝对偏差 < 0.01 个百分点（绝对值判据，不用相对误差）",
        ok7, "; ".join(f"n={r['n_shelve']}: {r['predicted_pct']:.4g}% vs "
                       f"{r['reported_pct']:.4g}% (Δ={r['abs_diff_pp']:.2e}pp)" for r in rows))

    # ⑧ 非物理输入必须抛，不许静默出数
    bad = 0
    for kw in ({"t_m_s": -1e-9, "t1_s": t1, "n_shelve": 1},
               {"t_m_s": t_m, "t1_s": 0.0, "n_shelve": 1},
               {"t_m_s": t_m, "t1_s": t1, "n_shelve": 0}):
        try:
            decay_error(**kw)
        except ValueError:
            bad += 1
    chk("⑧ 非物理输入（负窗口 / T1≤0 / n<1）必须抛 ValueError，不许静默出数",
        bad == 3, f"拦截 {bad}/3")

    # ⑨ 零窗口 ⇒ 恰为 0（精确已知量，用 ==；与 v0.9.296「== 只用于精确已知量」一致）
    chk("⑨ 零读出窗口 ⇒ P_decay 恰为 0.0（精确已知量）",
        decay_error(0.0, t1, 3) == 0.0, "t_m=0 ⇒ 无衰减")

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print(f"readout_shelving 自检：{npass}/{len(lines)} PASS")
    return npass, len(lines), lines


if __name__ == "__main__":
    import sys
    _p, _t, _ = run_selfchecks()
    sys.exit(0 if _p == _t else 1)
