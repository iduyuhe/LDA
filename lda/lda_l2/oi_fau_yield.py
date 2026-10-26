"""OI · `G-OI7a`：FAU 装配公差 **从角点变成分布** → 耦合损耗的统计（闭式 + MC + 反演）。

═══════════════════════════════════════════════════════════════════════════
缺口原文（`oi G-OI7`）
═══════════════════════════════════════════════════════════════════════════
「封装级热-机械-光真值缺失：**CTE 为公开手册值 · FAU 公差无分布 · 应力/翘曲无实测**」

三件事，按「须不需要实验台」拆开（v0.9.300 立的规则）：
  · **CTE 手册值** / **应力·翘曲实测**  ⇒ 须材料样品 + 应力台 ⇒ **边界声明**（`G-OI7b`）
  · **FAU 公差无分布**                ⇒ 分布→损耗的传播是**纯建模活** ⇒ 本模块做掉（`G-OI7a`）

═══════════════════════════════════════════════════════════════════════════
要修的那个字面量
═══════════════════════════════════════════════════════════════════════════
`oi_m4.fau_cte_misalignment()` 里原来写着：

    assembly_tol_um = 0.5                                  # ← 函数体里的字面量
    il_assembly_db  = −10·log10( exp(−(0.5 / w)²) )        # ← 把**公差带边缘**当位移量

两处毛病：
① `0.5` 不进参数表（`OI_M4_PROCESS`）⇒ 扫不动、没有窗口、改不了；
② 把 **±0.5 µm 的边缘**当成**位移量**算一次 ⇒ 输出的是**最坏角点**，却写成
   「装配公差带来的 0.121 dB」，读起来像典型值。

🔴 **差多少（本模块算出来的）**：按 ±3σ 口径，装配损耗的**期望**只有 **0.0267 dB** ——
角点是它的 **4.5 倍**。而同一句「±0.5 µm」在四种常见约定下给 **0.0267 ~ 0.2348 dB**，
**跨约定差 8.8 倍**。所以「±0.5 µm 公差」这句话**单独拿出来是不确定的**。

═══════════════════════════════════════════════════════════════════════════
模型与闭式
═══════════════════════════════════════════════════════════════════════════
横向失准 `d`（2D，只有横向平动）下两个同参数高斯模的功率耦合

    η(d) = exp( −(d/w)² )        w = **1/e² 强度半径**

🔴 **指数里的系数由计算钉死，不由注释钉死**：自检 ① 真的做 2D 数值重叠积分
（振幅重叠取模方），`w` 取 1/e² **强度**半径时得到 `exp(−(d/w)²)`；只有当 `w` 是 1/e
**场**半径时才得到教科书上那个 `exp(−d²/(2w²))`。两种写法差一个 2 倍指数，
**不能凭印象选** —— 本模块第一版就在这里把「振幅重叠」当成了「功率耦合」，① 当场抓出。

若失准两轴 `iid N(0, σ²)`（或等价地 `d²` 服从均值 `2σ²` 的指数分布），三条闭式：

    E[η]      = w² / (w² + 2σ²)                     ← 期望效率
    η_p       = p^{2σ²/w²}                          ← p 分位效率
    Yield(L₀) = 1 − 10^{ −(w²/(2σ²))·L₀/10 }        ← 损耗 ≤ L₀ dB 的比例

反演（设计用）：要 `Yield ≥ Y` 且额度 `L₀`，则须 `σ ≤ w/√(2β)`，`β = −10·log₁₀(1−Y)/L₀`。

🔴 **三个式子的 2 因子必须一致**：`E[η] = ∫η dP`、`P(η ≤ x) = x^{w²/(2σ²)}`、
`Yield(L₀) = P(η ≥ 10^{−L₀/10})` 三者互为恒等 —— 自检 ⑤ 用分位函数与良率函数
**互相反解**来核，不是三条各写一遍。第一版把 `2σ²` 写成 `σ²`，③④⑤ 一起红。

═══════════════════════════════════════════════════════════════════════════
「±tol」到底是什么分布 —— 本模块不下结论，只把它摊开
═══════════════════════════════════════════════════════════════════════════
`convention_table()` 把同一句「±0.5 µm」在四种常见约定下**并列**（w = 3 µm，tol = 0.5 µm）：

| 约定 | σ（µm） | E[η] | 期望损耗 | 角点/期望 |
|---|---|---|---|---|
| corner（现有实现：带边缘当位移） | — | 0.97260 | **0.1206** | 1.00× |
| gauss_1sigma | 0.5000 | 0.94737 | **0.2348** | 0.51× |
| gauss_2sigma | 0.2500 | 0.98630 | **0.0599** | 2.01× |
| gauss_3sigma（最常见） | 0.1667 | 0.99387 | **0.0267** | 4.51× |
| uniform_square（硬极限） | 0.2887 | 0.98182 | **0.0797** | 1.51× |

⇒ 跨约定 **8.8 倍**。另一个精确一点的观察（自检 ⑨）：**角点 ≈ `σ = tol/√2` 的期望**
（差 1%），也就是「把带边缘当位移」隐含了 **±tol ≈ ±1.41σ** 这个没人写下来的约定。

诚实边界：模场按**理想高斯**、两端口径**相同**、失准只有**横向平动**（不含角度失准、
波长失配、模场半径失配）；分布形状是**给定的**（本层不推断它，推断它须实测 ⇒ `G-OI7b`）。
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

__all__ = [
    "CONVENTIONS", "convention_sigma", "coupling_efficiency", "loss_db",
    "expected_eta_closed", "expected_loss_closed", "eta_quantile_closed",
    "yield_closed", "sigma_max_for_yield", "convention_table", "corner_vs_expected",
    "mc_statistics", "mode_overlap_2d", "cte_vs_assembly", "run_selfchecks",
]

#: 「±tol」的四种常见读法：name → (`σ/tol` 的系数 或 `None`（确定性角点）, 说明)
CONVENTIONS: Dict[str, Tuple[Optional[float], str]] = {
    "corner": (None, "把公差带边缘当位移量算一次（= 确定性角点，非分布）"),
    "gauss_1sigma": (1.0, "±tol 就是 ±1σ（最悲观；此时典型位移比带边缘还大）"),
    "gauss_2sigma": (1.0 / 2.0, "±tol 是 ±2σ"),
    "gauss_3sigma": (1.0 / 3.0, "±tol 是 ±3σ（过程能力口径，最常见）"),
    "uniform_square": (1.0 / math.sqrt(3.0), "在 [−tol, tol]² 上均匀（硬极限/合格率口径）"),
}


def convention_sigma(tol_um: float, convention: str) -> Optional[float]:
    """把「±tol」按某种约定换成**每轴**标准差；`corner` 返回 `None`（不是分布）。"""
    if convention not in CONVENTIONS:
        raise ValueError("未知约定 %r（可选 %s）" % (convention, sorted(CONVENTIONS)))
    tol = float(tol_um)
    if tol <= 0.0:
        raise ValueError("公差须 > 0，收到 %r" % (tol_um,))
    k = CONVENTIONS[convention][0]
    return None if k is None else k * tol


# ---------------------------------------------------------------------------
# ① 单点模型
# ---------------------------------------------------------------------------
def coupling_efficiency(d_um: float, w_um: float) -> float:
    """横向失准 `d` 下的**功率**耦合 `η = exp(−(d/w)²)`（`w` = 1/e² 强度半径）。"""
    w = float(w_um)
    if w <= 0.0:
        raise ValueError("模场半径须 > 0，收到 %r" % (w_um,))
    r = float(d_um) / w
    return math.exp(-(r * r))


def loss_db(eta: float) -> float:
    """效率 → 损耗（dB）。`η ≤ 0` 返回 `inf`（不抛错 —— 便于画曲线）。"""
    e = float(eta)
    if e <= 0.0:
        return float("inf")
    return -10.0 * math.log10(e)


# ---------------------------------------------------------------------------
# ② 三条闭式 + 反演
# ---------------------------------------------------------------------------
def _beta(w_um: float, sigma_um: float) -> float:
    """`β = w²/(2σ²)`（2D 各向同性高斯失准下 `P(η ≤ x) = x^β`）。"""
    w, s = float(w_um), float(sigma_um)
    if w <= 0.0:
        raise ValueError("模场半径须 > 0")
    if s < 0.0:
        raise ValueError("σ 须 ≥ 0，收到 %r" % (sigma_um,))
    return (w * w) / (2.0 * s * s) if s > 0.0 else float("inf")


def expected_eta_closed(w_um: float, sigma_um: float) -> float:
    """`E[η] = w²/(w²+2σ²)`。

    两条独立来源必须一致（自检 ③ 用 MC、⑤ 用分位/良率互解）：直接对 2D 高斯求期望
    `E[e^{−dx²/w²}]·E[e^{−dy²/w²}] = 1/(1+2σ²/w²)`。
    """
    w, s = float(w_um), float(sigma_um)
    b = _beta(w, s)
    if b == float("inf"):
        return 1.0
    return b / (b + 1.0)


def expected_loss_closed(w_um: float, sigma_um: float) -> float:
    """`−10·log10(E[η])`（🔴 是**效率的期望**再取 dB，不是 dB 的期望）。"""
    return loss_db(expected_eta_closed(w_um, sigma_um))


def eta_quantile_closed(p: float, w_um: float, sigma_um: float) -> float:
    """效率的 `p` 分位：`η_p = p^{2σ²/w²}`（`p=0` ⇒ 0；`σ=0` ⇒ 1）。"""
    pp = float(p)
    if not (0.0 <= pp <= 1.0):
        raise ValueError("分位 p 须在 [0,1]，收到 %r" % (p,))
    b = _beta(w_um, sigma_um)
    if b == float("inf"):
        return 1.0
    if pp == 0.0:
        return 0.0
    return pp ** (1.0 / b)


def yield_closed(l0_db: float, w_um: float, sigma_um: float) -> float:
    """损耗 `≤ L₀ dB` 的比例：`1 − 10^{−(w²/(2σ²))·L₀/10}`。"""
    l0 = float(l0_db)
    if l0 < 0.0:
        raise ValueError("损耗额度须 ≥ 0，收到 %r" % (l0_db,))
    b = _beta(w_um, sigma_um)
    if l0 == 0.0:
        return 0.0
    if b == float("inf"):
        return 0.0
    return 1.0 - 10.0 ** (-b * l0 / 10.0)


def sigma_max_for_yield(l0_db: float, w_um: float, target_yield: float) -> float:
    """反演：要「损耗 ≤ L₀ 的比例 ≥ Y」，σ 的上限 `w/√(2β)`，`β = −10log₁₀(1−Y)/L₀`。"""
    l0 = float(l0_db)
    y = float(target_yield)
    w = float(w_um)
    if l0 <= 0.0:
        raise ValueError("损耗额度须 > 0 才能反演（收到 %r）" % (l0_db,))
    if not (0.0 < y < 1.0):
        raise ValueError("目标良率须在 (0,1)，收到 %r" % (target_yield,))
    if w <= 0.0:
        raise ValueError("模场半径须 > 0")
    b = -10.0 * math.log10(1.0 - y) / l0
    return w / math.sqrt(2.0 * b)


# ---------------------------------------------------------------------------
# ③ 五种约定并列（本模块的「诚实面」）
# ---------------------------------------------------------------------------
def convention_table(w_um: float, tol_um: float) -> List[Dict]:
    """同一句「±tol」在各约定下的期望损耗 —— **不选一个，全给出来**。"""
    w = float(w_um)
    tol = float(tol_um)
    corner = loss_db(coupling_efficiency(tol, w))
    order = [k for k in CONVENTIONS]
    rows: List[Dict] = []
    for name in order:
        sig = convention_sigma(tol, name)
        if sig is None:
            eta_e, los = coupling_efficiency(tol, w), corner
        else:
            eta_e, los = expected_eta_closed(w, sig), expected_loss_closed(w, sig)
        rows.append({"convention": name, "sigma_um": sig, "eta": eta_e,
                     "loss_db": los,
                     "corner_over_loss": (corner / los) if los > 0 else float("inf"),
                     "meaning": CONVENTIONS[name][1]})
    return rows


def corner_vs_expected(w_um: float, tol_um: float,
                       convention: str = "gauss_3sigma") -> Dict:
    """角点损耗 vs 该约定下的**期望**损耗 —— 量化「把边缘当典型」放大了多少。"""
    sig = convention_sigma(tol_um, convention)
    if sig is None:
        raise ValueError("corner 约定不是分布，无法给期望")
    corner = loss_db(coupling_efficiency(tol_um, w_um))
    mean = expected_loss_closed(w_um, sig)
    return {"convention": convention, "sigma_um": sig,
            "corner_loss_db": corner, "expected_loss_db": mean,
            "ratio": corner / mean if mean > 0 else float("inf")}


# ---------------------------------------------------------------------------
# ④ MC（只用来对拍闭式，不作真值）
# ---------------------------------------------------------------------------
def mc_statistics(w_um: float, sigma_um: float, l0_db: float,
                  trials: int = 4000, seed: int = 20261026) -> Dict:
    """2D 各向同性高斯失准的 MC：期望效率 / 良率 / 中位数，与闭式对拍用。"""
    n = int(trials)
    if n <= 0:
        raise ValueError("trials 须为正整数")
    w, s = float(w_um), float(sigma_um)
    if w <= 0.0 or s < 0.0:
        raise ValueError("w 须 > 0 且 σ 须 ≥ 0")
    rng = random.Random(int(seed))
    acc = 0.0
    npass = 0
    vals: List[float] = []
    lim = float(l0_db)
    for _ in range(n):
        dx = rng.gauss(0.0, s)
        dy = rng.gauss(0.0, s)
        e = math.exp(-((dx * dx + dy * dy) / (w * w)))
        acc += e
        vals.append(e)
        if loss_db(e) <= lim:
            npass += 1
    vals.sort()
    ph = npass / n
    return {"trials": n, "mean_eta": acc / n, "yield": ph,
            "median_eta": vals[n // 2],
            "se_yield": math.sqrt(max(ph * (1 - ph), 1e-12) / n)}


# ---------------------------------------------------------------------------
# ⑤ 把「w 是哪个半径」用计算钉死（不靠注释）
# ---------------------------------------------------------------------------
def mode_overlap_2d(d_um: float, w_um: float, half_span_w: float = 6.0,
                    n_grid: int = 401) -> Dict:
    """数值积分两个**同参数**高斯模的 2D 重叠（只有横向平动 `d`）。

    模场取 `E(r) = exp(−r²/w²)` ⇒ 强度 `∝ exp(−2r²/w²)` ⇒ **1/e² 强度半径恰为 `w`**。
    返回：振幅重叠 `C`、**功率** `|C|²`、两个候选闭式 —— 用来自证「哪个式子是这口径」。
    """
    w = float(w_um)
    d = float(d_um)
    if w <= 0.0:
        raise ValueError("模场半径须 > 0")
    n = int(n_grid)
    if n < 51 or n % 2 == 0:
        raise ValueError("网格点须为 ≥51 的奇数（Simpson），收到 %r" % (n_grid,))
    span = half_span_w * w + abs(d)
    h = 2.0 * span / (n - 1)

    def E(x: float, y: float) -> float:
        return math.exp(-((x * x + y * y) / (w * w)))

    num = 0.0
    den = 0.0
    for i in range(n):
        x = -span + i * h
        wx = 1.0 if i in (0, n - 1) else (4.0 if i % 2 else 2.0)
        for j in range(n):
            y = -span + j * h
            wy = 1.0 if j in (0, n - 1) else (4.0 if j % 2 else 2.0)
            a = E(x, y)
            num += wx * wy * a * E(x - d, y)
            den += wx * wy * a * a
    amp = num / den
    eta = amp * amp                      # 🔴 功率 = |振幅重叠|²，第一版漏了这个平方
    return {"amp_overlap": amp, "eta_numeric": eta,
            "eta_exp_1_over_w2": math.exp(-((d / w) ** 2)),            # w = 1/e² 强度半径
            "eta_exp_1_over_2w2": math.exp(-(d * d) / (2.0 * w * w)),   # w = 1/e 场半径
            "d_um": d, "w_um": w}


# ---------------------------------------------------------------------------
# ⑥ 与 oi_m4 现有结论的关系
# ---------------------------------------------------------------------------
def cte_vs_assembly(w_um: Optional[float] = None, tol_um: Optional[float] = None,
                    convention: str = "gauss_3sigma") -> Dict:
    """把 `fau_cte_misalignment` 的 CTE 损耗与**分布口径下**的装配损耗并排放。

    🔴 要回答的是：卡上那句「CTE **远小于** 装配公差带来的损耗 ⇒ CTE 不是主因」
       在分布口径下**还成不成立**。
    """
    from lda_l2 import oi_m4 as M4
    w = float(M4.OI_M4_PROCESS["mfd_w_um"] if w_um is None else w_um)
    tol = float(M4.OI_M4_PROCESS["fau_assembly_tol_um"] if tol_um is None else tol_um)
    cte = M4.fau_cte_misalignment(w_um=w)
    tab = {r["convention"]: r for r in convention_table(w, tol)}
    row = tab[convention]
    il_cte = float(cte["il_cte_db"])
    corner = tab["corner"]["loss_db"]
    mean = row["loss_db"]
    return {"w_um": w, "tol_um": tol, "convention": convention,
            "il_cte_db": il_cte,
            "il_assembly_corner_db": corner,
            "il_assembly_expected_db": mean,
            "ratio_corner": (corner / il_cte) if il_cte > 0 else float("inf"),
            "ratio_expected": (mean / il_cte) if il_cte > 0 else float("inf"),
            "cte_is_dominant": bool(il_cte > mean),
            "note": ("角点口径下装配损耗是 CTE 的 %.1f×（「远小于」成立）；"
                     "分布口径（%s）下只剩 %.2f× ⇒ **方向不变、措辞不成立**。"
                     % ((corner / il_cte) if il_cte > 0 else float("inf"),
                        convention, (mean / il_cte) if il_cte > 0 else float("inf")))}


# ---------------------------------------------------------------------------
# ⑦ 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = True) -> Tuple[int, int, List[str]]:
    """自检 14 项。返回 `(npass, total, lines)`。"""
    lines: List[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        lines.append("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                                    ("  |  " + detail) if detail else ""))

    w0 = 3.0
    tol = 0.5

    # ① 🔴 用**数值 2D 重叠积分**钉死「w 是哪个半径」—— 不靠注释、不靠印象
    ov = mode_overlap_2d(0.8, w0)
    d1 = abs(ov["eta_numeric"] - ov["eta_exp_1_over_w2"])
    d2 = abs(ov["eta_numeric"] - ov["eta_exp_1_over_2w2"])
    chk("① 口径钉死：2D 数值重叠（振幅取模方）⇄ exp(−(d/w)²) 差 %.1e，"
        "⇄ exp(−d²/2w²) 差 %.1e ⇒ w=1/e² 强度半径时前者对" % (d1, d2),
        d1 < 1e-6 and d2 > 1e6 * max(d1, 1e-18),
        "振幅重叠=%.6f 功率=%.6f" % (ov["amp_overlap"], ov["eta_numeric"]))

    # ② σ=0 退化必须**恰**成立（精确已知量，用 ==）
    chk("② σ=0 退化：E[η] 恰 1.0 ∧ 良率(L₀>0) 恰 0.0 ∧ η_p 恰 1.0 ∧ 良率(L₀=0) 恰 0.0",
        expected_eta_closed(w0, 0.0) == 1.0 and yield_closed(0.1, w0, 0.0) == 0.0
        and eta_quantile_closed(0.5, w0, 0.0) == 1.0 and yield_closed(0.0, w0, 1.0) == 0.0)

    # ③ MC ⇄ 闭式 E[η]（3 档 σ；η 的保守标准误 0.5/√n ⇒ 4σ）
    zs, det3 = [], []
    for sig in (0.05, 0.1667, 0.5):
        mc = mc_statistics(w0, sig, 0.1, trials=3000, seed=1000 + int(sig * 1000))
        c = expected_eta_closed(w0, sig)
        z = (mc["mean_eta"] - c) / (0.5 / math.sqrt(mc["trials"]))
        zs.append(z)
        det3.append("σ=%.4f: %.6f vs %.6f" % (sig, mc["mean_eta"], c))
    chk("③ MC ⇄ 闭式 E[η]=w²/(w²+2σ²)：3 档 σ 全部 |z| ≤ 4（max=%.2f，保守 se）"
        % max(abs(z) for z in zs), all(abs(z) <= 4.0 for z in zs), " ; ".join(det3))

    # ④ MC ⇄ 闭式良率（3 个额度，4σ）
    zs4, det4 = [], []
    for l0 in (0.02, 0.05, 0.10):
        mc = mc_statistics(w0, 0.1667, l0, trials=3000, seed=2000 + int(l0 * 1000))
        c = yield_closed(l0, w0, 0.1667)
        se = math.sqrt(max(c * (1 - c), 1e-12) / mc["trials"])
        zs4.append((mc["yield"] - c) / se)
        det4.append("L₀=%.2f: %.4f vs %.4f" % (l0, mc["yield"], c))
    chk("④ MC ⇄ 闭式良率 1−10^(−(w²/2σ²)L₀/10)：3 个额度全部 |z| ≤ 4（max=%.2f）"
        % max(abs(z) for z in zs4), all(abs(z) <= 4.0 for z in zs4), " ; ".join(det4))

    # ⑤ 🔴 两条闭式**互相反解**（不是三条各写一遍）：良率给 p，分位须还原 10^(−L₀/10)
    worst5, det5 = 0.0, []
    for sig in (0.1, 0.25, 0.4):
        for l0 in (0.01, 0.05, 0.2):
            p = 1.0 - yield_closed(l0, w0, sig)
            got = eta_quantile_closed(p, w0, sig)
            want = 10.0 ** (-l0 / 10.0)
            worst5 = max(worst5, abs(got - want) / want)
            det5.append("%.2f" % (abs(got - want) / want))
    # 这条是**代数恒等**，容差只留浮点舍入（10^x 与 pow 两条路的舍入不同，实测 ~6e-11）
    chk("⑤ 闭式互洽：由良率反解 p 再取分位 ≡ 10^(−L₀/10)（9 组，最差相对差 %.1e ≤ 1e-9 舍入）"
        % worst5, worst5 < 1e-9, "最差=%s" % max(det5))

    # ⑥ 分位数闭式 ⇄ MC 经验分位（中位数；容差按样本量定）
    mc6 = mc_statistics(w0, 0.3, 0.1, trials=5000, seed=777)
    chk("⑥ 分位闭式 η_p=p^(2σ²/w²)：p=0.5 与 MC 中位数差 ≤ 0.005（%.5f vs %.5f）"
        % (eta_quantile_closed(0.5, w0, 0.3), mc6["median_eta"]),
        abs(eta_quantile_closed(0.5, w0, 0.3) - mc6["median_eta"]) <= 0.005)

    # ⑦ 反演：σ_max 回代 ⇒ 良率 **恰**等于目标（1e-12）
    ok7, det7 = True, []
    for tgt in (0.9, 0.99, 0.999):
        smax = sigma_max_for_yield(0.05, w0, tgt)
        got = yield_closed(0.05, w0, smax)
        det7.append("%.3f→%.6f" % (tgt, got))
        if abs(got - tgt) > 1e-12:
            ok7 = False
    chk("⑦ 反演 σ_max（良率→σ 上限）回代 90/99/99.9% 均恰命中（1e-12）", ok7,
        " ".join(det7))

    # ⑧ 单调性三条
    chk("⑧ 单调性：E[η] 随 σ 递减 ∧ 良率随 L₀ 递增 ∧ 良率随 σ 递减",
        expected_eta_closed(w0, 0.1) > expected_eta_closed(w0, 0.2)
        and yield_closed(0.1, w0, 0.2) < yield_closed(0.2, w0, 0.2)
        and yield_closed(0.1, w0, 0.1) > yield_closed(0.1, w0, 0.2))

    # ⑨ 🔴 「角点」到底是什么口径：等价于 σ = tol/√2 的期望（一阶恒等 ln(1+2x)≈2x）
    corner = loss_db(coupling_efficiency(tol, w0))
    at_iso = expected_loss_closed(w0, tol / math.sqrt(2.0))
    chk("⑨ 角点 ≡ σ=tol/√2 的期望（%.6f vs %.6f，相对差 %.2f%%）⇒「带边缘当位移」"
        "隐含 ±tol ≈ ±1.41σ —— 这个约定没人写过"
        % (corner, at_iso, 100 * abs(corner - at_iso) / corner),
        abs(corner - at_iso) / corner < 0.02)

    # ⑩ 🔴 量级差：3σ 口径下角点是期望的 ≥4 倍
    cv = corner_vs_expected(w0, tol, "gauss_3sigma")
    chk("⑩ 把边缘当典型放大了 %.2f 倍（3σ：角点 %.4f dB vs 期望 %.4f dB）≥ 4 倍"
        % (cv["ratio"], cv["corner_loss_db"], cv["expected_loss_db"]), cv["ratio"] >= 4.0)

    # ⑪ 反向探针：口径写错（把功率写成 exp(−d²/2w²)）⇒ 良率明显不同
    sig = 0.1667
    b_right = (w0 * w0) / (2.0 * sig * sig)
    y_right = 1.0 - 10.0 ** (-b_right * 0.05 / 10.0)
    y_wrong = 1.0 - 10.0 ** (-2.0 * b_right * 0.05 / 10.0)
    chk("⑪ 反向探针：口径写错（指数差 2 倍）⇒ 良率 %.4f vs 正确 %.4f，相对差 %.0f%% ⇒ 能区分"
        % (y_wrong, y_right, 100 * abs(y_wrong - y_right) / max(y_right, 1e-300)),
        abs(y_wrong - y_right) / max(y_right, 1e-300) > 0.10)

    # ⑫ 🔴 单一真源：公差必须进参数表（此前是函数体里的字面量）
    from lda_l2 import oi_m4 as M4
    has_key = "fau_assembly_tol_um" in M4.OI_M4_PROCESS
    same = has_key and (float(M4.fau_cte_misalignment()["assembly_tol_um"])
                        == float(M4.OI_M4_PROCESS["fau_assembly_tol_um"]))
    chk("⑫ 公差单一真源：`OI_M4_PROCESS['fau_assembly_tol_um']` 在位 ∧ "
        "`fau_cte_misalignment()['assembly_tol_um']` 与之逐位相等",
        bool(same), "key=%s" % has_key)

    # ⑬ CTE ⇄ 装配：方向不变，但「远小于」在分布口径下不成立
    ca = cte_vs_assembly(convention="gauss_3sigma")
    chk("⑬ 结论强度：角点口径 CTE 是装配的 1/%.1f（「远小于」成立）↔ 3σ 口径只剩 1/%.2f "
        "⇒ 方向不变（CTE 仍非主因=%s）、措辞不成立"
        % (ca["ratio_corner"], ca["ratio_expected"], ca["cte_is_dominant"] is False),
        ca["cte_is_dominant"] is False and ca["ratio_corner"] > 10.0
        and 3.0 < ca["ratio_expected"] < 6.0)

    # ⑭ 非物理入参
    n_bad = 0
    for fn, kw in ((convention_sigma, {"tol_um": 0.0, "convention": "gauss_3sigma"}),
                   (expected_eta_closed, {"w_um": 0.0, "sigma_um": 0.1}),
                   (yield_closed, {"l0_db": -0.1, "w_um": w0, "sigma_um": 0.1}),
                   (eta_quantile_closed, {"p": 1.5, "w_um": w0, "sigma_um": 0.1}),
                   (sigma_max_for_yield, {"l0_db": 0.0, "w_um": w0, "target_yield": 0.9})):
        try:
            fn(**kw)
        except ValueError:
            n_bad += 1
    chk("⑭ 非物理入参（tol≤0 / w≤0 / L₀<0 / p∉[0,1] / 反演 L₀≤0）必须抛 ValueError",
        n_bad == 5, "拦截 %d/5" % n_bad)

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print("oi_fau_yield 自检：%d/%d PASS" % (npass, len(lines)))
    return npass, len(lines), lines


if __name__ == "__main__":    # pragma: no cover
    import sys
    p, t, _ = run_selfchecks()
    sys.exit(0 if p == t else 1)
