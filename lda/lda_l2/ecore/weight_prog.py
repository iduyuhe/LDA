"""**E16 权重编程通路**（`lda_l2/ecore/weight_prog.py` · 电子计算征程 · D-181）

═══════════════════════════════════════════════════════════════════════════
为什么需要这个模块（缺口取证）
═══════════════════════════════════════════════════════════════════════════
E1–E15 全程把权重当作**已知且精确**的输入：
  · `crossbar_mvm.CrossbarMVM(weights, …)` —— weights 直接是电导(S) 或栅压(V)；
  · `mvm_datapath.AnalogMvmUnit(W, …)` —— `G = g_base + s·W` **解析**算出，一步到位；
  · `layout.crosspoint_cell(…, net_gate)` —— 权重栅 `wg_{i}_{j}` 只是**对外端口**，
    docstring 明写「栅驱动/编程路径属 E7+，本段不含」。
⇒ 平台从来没有「**写入**」这一步。真实模拟 CIM 芯片里，编程是**最贵、最容易出错、
最需要架构配合**的环节。本模块补上它。

与 E8（器件失配）**不是重复**：
  · E8 = **制造**涨落（Pelgrom），流片后固定、不可控；
  · E16 = **写入动作本身**（脉冲分辨率 / 写入噪声 / 卡位 / 漂移），每次编程都不同、部分可控。
两者物理机制与设计对策都不同（失配靠面积/校准，编程靠脉冲策略）⇒ 必须分开建模。

═══════════════════════════════════════════════════════════════════════════
模型：1T1R 类模拟电导 + 写-校验（write-verify）
═══════════════════════════════════════════════════════════════════════════
    g ← g_erase
    repeat up to max_pulses:
        g ← g + α·(g* − g) + η          # 比例修正 + 写入噪声
        if |g − g*| / g* ≤ tol_rel: break

五个**闭式 golden**（判据的锚，全部可手算）：
  G-1 电平量化步长      lsb_rel = 1/(2^k − 1)            （相对**电导窗口**）
  G-2 确定性轨迹        e_k = e_0·(1−α)^k                 （等比数列，精确）
  G-3 到容差脉冲数      k* = ceil( ln(tol/e_0) / ln(1−α) )
  G-4 写入噪声地板      σ_∞ = σ_p / √(α(2−α))             （无穷级数，精确）
  G-5 漂移幂律          g(t)/g_0 = (t/t0)^(−ν) ⇒ 重校准间隔 t_max = t0·(1−β)^(−1/ν)

🔴 **G-4 是本模块最有价值的结论**：`Var(e_∞) = σ_p²·Σ_{j≥0}(1−α)^{2j} = σ_p²/(α(2−α))`
⇒ 单脉冲噪声 σ_p 是**硬地板**，写-校验最多把地板抬升 `1/√(α(2−α))` 倍；
`tol_rel < σ_∞` 时**期望意义上不可达**（越校验越白校验）。
⇒ **设计指令：要提精度必须降 σ_p（脉冲整形 / 电流限制），不是加脉冲数。**

═══════════════════════════════════════════════════════════════════════════
与 E15 误差预算链的桥（本模块是「系统层」而非「器件层」的证明）
═══════════════════════════════════════════════════════════════════════════
`programming_budget_terms()` 返回 **E15 `make_term` 格式**的误差项，可直接注入
`budget.collect_terms(..., include_programming=True, prog_terms=…)`（`prog_terms` 省略时
`collect_terms` 会**惰性导入**本模块自动构造 —— 函数内导入 ⇒ **无导入期环依赖**）。
🔴 本模块**不修改** `budget.py` 的任何默认值（`include_programming` 默认 False）
⇒ **E15 已发布数字逐位不变**（8×8 worst 4.06012% / 4.622 位）；E15 自己的门禁
自动成为本模块的**回归保护**。

═══════════════════════════════════════════════════════════════════════════
🔴 诚实边界（本段自带）
═══════════════════════════════════════════════════════════════════════════
· **参数为公开典型量级占位（非 PDK · 无实测锚）**：α / σ_p / tol / ν / p_stuck 都是**设计自由度**，
  不是某颗真实芯片的标定值 ⇒ **结论随参数变，报告必须携带参数**。
· **漂移结论条件于 ν**：`t_max ≈ 2.79 s`（5% 预算 · ν=0.05）是**参数推出的**，不是普适断言。
· **器件模型是行为级**：写-校验 = 比例修正 + 加性噪声的**现象学模型**，
  **不含**真实 RRAM 的细丝动力学 / 非线性 / 脉冲宽度依赖 / 温度加速。
· **无 endurance / retention 联合退化**；**只覆盖静态**（不含编程时间/能耗）。
· **不报 TOPS / TOPS-W / fJ/op**（全征程纪律）。
· 🔴 **保护性约束**：默认路径下**不改任何既有模块的默认值与闭式**。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from .budget import make_term, combine, collect_terms, RANDOM, BOUNDED
from .mismatch import mvm_output

# ═══════════════════════════════════════════════════════════════════════════
# 参数（公开典型量级占位 · 非 PDK）
# ═══════════════════════════════════════════════════════════════════════════
WEIGHT_PROG_PROCESS: dict = {
    "g_min_us": 1.0,          # 电导窗口下限（µS · 公开典型）
    "g_max_us": 100.0,        # 电导窗口上限 ⇒ 窗口比 100:1
    "prog_bits": 6,           # 可编程电平数 2^k（模拟 RRAM 公开典型 4–6 bit）
    "alpha_pulse": 0.30,      # 每脉冲比例修正量
    "sigma_pulse_rel": 0.005, # 每脉冲写入噪声（相对目标 · 0.5%）
    "tol_rel": 0.01,          # 写-校验目标容差（1%）
    "max_pulses": 64,         # 脉冲上限
    "stuck_p": 1.0e-3,        # 单元卡位概率
    "nu_drift": 0.05,         # 电导漂移幂律指数
    "sigma_nu": 0.0015,       # ν 的单元间离散（漂移**不可校准**的那部分）
    "t0_s": 1.0,              # 漂移参考时刻
    "t_read_s": 1000.0,       # 参考读时刻（仅用于报告，不进默认预算）
}

DEFAULT_S = 1.0e-4            # 权重→电导的尺度（与 E3 `AnalogMvmUnit(s=…)` 同口径）
DEFAULT_G_BASE_FACTOR = 1.5   # g_base = factor·max|W|·s（与 E3 同口径 ⇒ 窗口比 ≈ 5:1）


# ═══════════════════════════════════════════════════════════════════════════
# ① 电平量化（MLC 视图）
# ═══════════════════════════════════════════════════════════════════════════
def program_levels(bits: int) -> int:
    """可编程电平数 `2^k`。"""
    b = int(bits)
    if b < 1:
        raise ValueError("编程位数须 >= 1（0 表示不量化 ⇒ 不构成电平误差）")
    return 1 << b


def level_lsb_rel(bits: int) -> float:
    """**G-1 闭式**：一个电平步长占**电导窗口**的比例 = `1/(2^k − 1)`。

    ### 判据
    >>> level_lsb_rel(6)                      # 1/63
    >>> abs(level_lsb_rel(6) - 1.0/63.0) < 1e-18
    """
    return 1.0 / float(program_levels(bits) - 1)


def level_error_bound_rel(bits: int) -> float:
    """电平量化误差**界**（相对窗口）= 半步长 `lsb/2`。"""
    return level_lsb_rel(bits) / 2.0


def level_bound_in_output(g_hi: float, g_lo: float, g_ref: float, bits: int) -> float:
    """**输出口径下的电平量化相对界** = 半步长 / `g_ref`。

    🔴 `g_ref` 必须取 **平均电导 `g_mean`**（不是 `min(g)`）：
    电平在窗口内**等间距** ⇒ 每个单元的量化误差**绝对值**同为半步长（与 g 无关）
    ⇒ 输出相对误差界 = `half_step·Σ|x| / |Σ g_i x_i|` = `half_step / g_mean`
    （同号权重 + 等 |x| 的理想化，与 E8/E9 同口径）。
    **低电导单元的「大相对误差」在求和里并不放大。**

    单独调用（`g_ref = g_lo`）可得到**低电导端最坏单元**的相对误差，仅作告警用。
    """
    if g_hi <= g_lo or program_levels(bits) <= 1 or g_ref <= 0.0:
        return 0.0
    return (float(g_hi) - float(g_lo)) * level_error_bound_rel(bits) / float(g_ref)


def quantize_to_levels(w_rel, bits: int):
    """把 `w_rel ∈ [0,1]`（窗口内归一化位置）量化到最近电平（含钳位）。"""
    lv = program_levels(bits)
    x = np.clip(np.asarray(w_rel, dtype=float), 0.0, 1.0)
    idx = np.rint(x * float(lv - 1))
    return idx / float(lv - 1)


# ═══════════════════════════════════════════════════════════════════════════
# ② 写-校验（write-verify）
# ═══════════════════════════════════════════════════════════════════════════
def write_verify_closed(e0: float = 1.0, alpha: float = 0.30,
                        n_steps: int = 16) -> Dict:
    """**G-2 闭式（golden）**：确定性写-校验的相对误差轨迹 `e_k = e_0·(1−α)^k`。

    `is_oracle=False` —— 本函数是**解析解**，随机仿真（`write_verify_stochastic`）才是候选。
    两者在 **σ_p = 0** 时必须逐步相等（门禁 B6）。
    """
    a = float(alpha)
    if not (0.0 < a < 1.0):
        raise ValueError("alpha 须在 (0,1)")
    n = int(n_steps)
    e0 = float(e0)
    traj = [e0 * (1.0 - a) ** k for k in range(n + 1)]
    return {"e0": e0, "alpha": a, "n_steps": n, "errors": traj, "is_oracle": False,
            "formula": "e_k = e0*(1-alpha)**k"}


def iter_to_tolerance(e0: float = 1.0, tol_rel: float = 0.01,
                      alpha: float = 0.30) -> int:
    """**G-3 闭式**：确定性轨迹首次落到容差内所需脉冲数
    `k* = ceil( ln(tol/e_0) / ln(1−α) )`（`e_0 ≤ tol` ⇒ 0）。

    ### 判据
    >>> iter_to_tolerance(1.0, 0.01, 0.30)     # 13（0.7^13 = 0.00969 ≤ 0.01）
    """
    a = float(alpha)
    tol = float(tol_rel)
    e = abs(float(e0))
    if not (0.0 < a < 1.0):
        raise ValueError("alpha 须在 (0,1)")
    if tol <= 0.0:
        raise ValueError("tol_rel 须 > 0")
    if e <= tol:
        return 0
    return int(math.ceil(math.log(tol / e) / math.log(1.0 - a)))


def noise_floor_sigma(sigma_pulse_rel: float = 0.005,
                      alpha: float = 0.30) -> float:
    """**G-4 闭式**：写-校验的**写入噪声地板**（相对目标的 σ）。
    `Var(e_∞) = σ_p²·Σ_{j≥0}(1−α)^{2j} = σ_p²/(α(2−α))` ⇒ `σ_∞ = σ_p/√(α(2−α))`。

    🔴 **单脉冲噪声是硬地板**：`σ_∞ ∈ [σ_p, σ_p/√(α(2−α))]`。
    """
    a = float(alpha)
    if not (0.0 < a < 1.0):
        raise ValueError("alpha 须在 (0,1)")
    sp = float(sigma_pulse_rel)
    if sp < 0.0:
        raise ValueError("sigma_pulse_rel 不得为负")
    return sp / math.sqrt(a * (2.0 - a))


def write_verify_stochastic(e0: float = 1.0, alpha: float = 0.30,
                            sigma_pulse_rel: float = 0.005,
                            tol_rel: float = 0.01, max_pulses: int = 64,
                            seed: int = 0, trials: int = 2000) -> Dict:
    """**候选**（含噪声的写-校验 MC）。

    🔴 返回的 `sigma_residual` 用**未停机的过程**（收敛后继续施脉冲）估计 ——
    这正是 G-4 那个无穷级数所描述的量（门禁 B5 用它核对闭式）。
    """
    a = float(alpha)
    sp = float(sigma_pulse_rel)
    tol = float(tol_rel)
    mp = int(max_pulses)
    nt = int(trials)
    if not (0.0 < a < 1.0):
        raise ValueError("alpha 须在 (0,1)")
    if mp < 1 or nt < 2:
        raise ValueError("max_pulses >= 1 且 trials >= 2")
    rng = np.random.default_rng(int(seed))
    e = np.full(nt, float(e0))
    iters = np.full(nt, mp, dtype=int)
    conv = np.zeros(nt, dtype=bool)
    for k in range(1, mp + 1):
        e = e * (1.0 - a) + rng.normal(0.0, sp, nt)
        newly = (~conv) & (np.abs(e) <= tol)
        iters[newly] = k
        conv |= newly
    return {"sigma_residual": float(np.std(e, ddof=1)),
            "mean_relative_error": float(np.mean(e)),
            "iters_mean": float(np.mean(iters)),
            "iters_max": int(np.max(iters)),
            "converged_frac": float(np.mean(conv)),
            "alpha": a, "sigma_pulse_rel": sp, "tol_rel": tol,
            "max_pulses": mp, "trials": nt, "is_oracle": False}


def residual_sigma_out(sigma_cell_rel: float, n: int) -> float:
    """**输出口径（理想化）**：单元级独立随机误差经 N 项求和 ⇒ `σ_out = σ_cell/√N`（与 E8 同律）。

    🔴 **该式隐含「各单元电导相同」**。电导有离散时，输出 σ 的严格式见
    `output_sigma_matrix_aware`（两者之比 = 条件数 `√(Σ(g x)²)/|Σ g x|` ≥ 1/√N）。
    """
    nn = int(n)
    if nn < 1:
        raise ValueError("n 须 >= 1")
    return abs(float(sigma_cell_rel)) / math.sqrt(float(nn))


def output_sigma_matrix_aware(g, x, sigma_cell_rel: float) -> float:
    """**输出 σ 的严格式（矩阵感知）**：`σ_cell·√(Σ_i (g_i x_i)²) / |Σ_i g_i x_i|`。

    🔴 与 `residual_sigma_out(σ, N) = σ/√N` 的差别就是**电导离散度**：
    `√(Σ(g x)²)/|Σ g x| ≥ 1/√N`，等号仅在**全部 `g_i x_i` 相等**时成立。
    ⇒ E8/E9 的 `σ/√N` 是**理想化**（各单元相同）；本函数是含离散的**严格**口径。
    """
    G = np.asarray(g, dtype=float)
    xx = np.asarray(x, dtype=float)
    if G.shape != xx.shape:
        raise ValueError("g 与 x 形状须相同（同一行内 n 个单元）")
    s = float(np.sum(G * xx))
    if abs(s) < 1e-300:
        raise ValueError("Σ g·x 为 0 ⇒ 相对误差无定义")
    return abs(float(sigma_cell_rel)) * math.sqrt(float(np.sum((G * xx) ** 2))) / abs(s)


# ═══════════════════════════════════════════════════════════════════════════
# ③ 漂移（幂律）
# ═══════════════════════════════════════════════════════════════════════════
def drift_factor(t: float = 1.0, t0: float = 1.0, nu: float = 0.05) -> float:
    """**G-5 闭式**：`g(t)/g_0 = (t/t0)^(−ν)`。"""
    tt = float(t)
    t00 = float(t0)
    if tt <= 0.0 or t00 <= 0.0:
        raise ValueError("t / t0 须 > 0")
    return (tt / t00) ** (-float(nu))


def drift_rel_pct(t: float = 1000.0, t0: float = 1.0, nu: float = 0.05) -> float:
    """**共模漂移**（相对丢电导的百分比）—— 🔴 所有单元同向 ⇒ 单次全局增益校准即可消除。"""
    return (1.0 - drift_factor(t, t0, nu)) * 100.0


def recal_interval(t0: float = 1.0, nu: float = 0.05,
                   budget_rel: float = 0.05) -> float:
    """**重校准间隔（闭式）**：解 `1 − (t/t0)^(−ν) = β` ⇒ `t_max = t0·(1−β)^(−1/ν)`。

    ### 判据
    >>> abs(drift_factor(recal_interval(1.0, 0.05, 0.05), 1.0, 0.05) - 0.95) < 1e-12
    """
    b = float(budget_rel)
    n = float(nu)
    if not (0.0 < b < 1.0):
        raise ValueError("budget_rel 须在 (0,1)")
    if n <= 0.0:
        raise ValueError("nu 须 > 0")
    return float(t0) * (1.0 - b) ** (-1.0 / n)


def drift_curve(times: Sequence[float], t0: float = 1.0, nu: float = 0.05,
                sigma_nu: float = 0.0015) -> List[Dict]:
    """漂移曲线：**共模**（可校准）与**离散项**（σ_ν 引起、**校准不掉**）分开报。"""
    t00 = float(t0)
    n = float(nu)
    sn = float(sigma_nu)
    out: List[Dict] = []
    for tt in times:
        f = drift_factor(tt, t00, n)
        ld = math.log(float(tt) / t00) if float(tt) > 0 else 0.0
        out.append({
            "t_s": float(tt),
            "drift_factor": f,
            "common_mode_pct": (1.0 - f) * 100.0,
            "spread_pct": abs(sn * ld) * 100.0,   # σ_ν·ln(t/t0)，单元的 ν 不同 ⇒ 校准不掉
        })
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ④ 良率 / 卡位
# ═══════════════════════════════════════════════════════════════════════════
def yield_fraction(n_cells: int, p_stuck: float = 1.0e-3) -> float:
    """**全部单元都编程成功**的概率 `(1−p)^N`（独立假设）。

    ### 判据
    >>> abs(yield_fraction(64, 1e-3) - (1-1e-3)**64) < 1e-15
    """
    nc = int(n_cells)
    p = float(p_stuck)
    if nc < 0:
        raise ValueError("n_cells 须 >= 0")
    if not (0.0 <= p <= 1.0):
        raise ValueError("p_stuck 须在 [0,1]")
    return (1.0 - p) ** nc


def stuck_error_bound_rel(p_stuck: float, n_cells: int,
                          stuck_rel_span: float = 1.0) -> float:
    """卡位造成的**最坏**输出误差界（有界项口径）。

    最坏情形 = 期望卡位数（`p·N`）全部朝同一方向偏 `stuck_rel_span`（相对该单元目标）⇒
    相对输出误差 ≲ `p·N·stuck_rel_span / N = p·stuck_rel_span`（N 项同向平均即抵消 N）。
    """
    return max(0.0, float(p_stuck)) * float(stuck_rel_span)


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 差分对（有符号权重）
# ═══════════════════════════════════════════════════════════════════════════
def differential_pair(w: float, s: float = DEFAULT_S,
                      g_base: Optional[float] = None,
                      w_max: float = 1.0) -> Dict:
    """**差分对**：有符号权重用两个单元表示 `g± = g_base ± s·w`
    ⇒ `w = (g+ − g−) / (2s)`（精确代数）。

    `g_base` 缺省取 `1.5·w_max·s`（与 E3 口径同）⇒ 保证 `g− ≥ 0.5·w_max·s > 0`。
    """
    ww = float(w)
    ss = float(s)
    wm = abs(float(w_max))
    gb = float(g_base) if g_base is not None else DEFAULT_G_BASE_FACTOR * wm * ss
    gp = gb + ss * ww
    gm = gb - ss * ww
    rec = (gp - gm) / (2.0 * ss)
    return {"w": ww, "g_plus": gp, "g_minus": gm, "g_base": gb,
            "w_recovered": rec, "exact": abs(rec - ww) <= 1e-15 * max(1.0, abs(ww)),
            "g_min_positive": min(gp, gm) > 0.0, "is_oracle": False}


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 阵列编程（矩阵感知 · 接 E8 `mvm_output`）
# ═══════════════════════════════════════════════════════════════════════════
def canonical_weights(n: int, m: Optional[int] = None, seed: int = 0):
    """**参考权重分布**（确定性 · 供无矩阵调用的口径使用）：U(−1, 1)。"""
    nn = int(n)
    mm = int(m) if m is not None else nn
    rng = np.random.default_rng(int(seed))
    return rng.uniform(-1.0, 1.0, (nn, mm))


def _ideal_conductances(w, s: float = DEFAULT_S,
                        g_base: Optional[float] = None):
    """E3 同口径的权重→电导映射 `g = g_base + s·W`（另有 g_base 参考行）。"""
    W = np.asarray(w, dtype=float)
    wmax = float(np.max(np.abs(W))) if W.size else 0.0
    gb = (DEFAULT_G_BASE_FACTOR * wmax * float(s)) if g_base is None else float(g_base)
    return gb + float(s) * W


def program_array(w, s: float = DEFAULT_S, g_base: Optional[float] = None,
                  *, bits: Optional[int] = None, include_level: bool = True,
                  alpha_pulse: Optional[float] = None,
                  sigma_pulse_rel: Optional[float] = None,
                  tol_rel: Optional[float] = None,
                  stuck_p: Optional[float] = None,
                  seed: int = 0) -> Dict:
    """对权重矩阵做**一次完整编程**（电平量化 + 写入残差 + 卡位）。

    返回含 `g_ideal`（目标）/ `g_prog`（实际）/ 逐单元相对误差 / 脉冲数 / 卡位掩码。
    """
    pr = WEIGHT_PROG_PROCESS
    bits = int(pr["prog_bits"] if bits is None else bits)
    a = float(pr["alpha_pulse"] if alpha_pulse is None else alpha_pulse)
    sp = float(pr["sigma_pulse_rel"] if sigma_pulse_rel is None else sigma_pulse_rel)
    tol = float(pr["tol_rel"] if tol_rel is None else tol_rel)
    ps = float(pr["stuck_p"] if stuck_p is None else stuck_p)

    g_ideal = _ideal_conductances(w, s, g_base)
    lo = float(np.min(g_ideal))
    hi = float(np.max(g_ideal))
    span = hi - lo

    # ① 电平量化（窗口内归一化后取最近电平）
    if include_level and span > 0.0 and program_levels(bits) > 1:
        rel_pos = (g_ideal - lo) / span
        g_tgt = lo + quantize_to_levels(rel_pos, bits) * span
    else:
        g_tgt = g_ideal.copy()

    # ② 写入残差（G-4 地板；🔴 相对量 ⇒ 与单元尺度无关）
    #    🔴 直接**从稳态地板抽样**（而非逐步施 max_pulses 个脉冲）：
    #    `max_pulses` 足够大时 `e_∞` 就是稳态分布（G-4），逐脉冲模拟与之等价（门禁 B5 已证闭式⟷MC 一致）。
    rng = np.random.default_rng(int(seed))
    sig_cell = noise_floor_sigma(sp, a)
    resid = rng.normal(0.0, sig_cell, g_tgt.shape)

    # ③ 卡位（朝最坏方向：按符号推向窗口边界）
    stuck = rng.random(g_tgt.shape) < ps
    if np.any(stuck):
        span2 = max(hi, 1e-30)
        resid = np.where(stuck, np.sign(g_tgt) * (span2 / np.maximum(g_tgt, 1e-30)), resid)

    g_prog = g_tgt * (1.0 + resid)

    rel_target = (g_tgt - g_ideal) / g_ideal          # 电平量化引入（有界）
    rel_total = (g_prog - g_ideal) / g_ideal          # 合计
    e0 = float(np.max(np.abs(rel_target))) if g_ideal.size else 0.0
    iters = iter_to_tolerance(max(e0, 1e-12), tol, a)

    return {
        "g_ideal": g_ideal, "g_target": g_tgt, "g_prog": g_prog,
        "rel_level_err": rel_target, "rel_total_err": rel_total,
        "max_abs_level_rel": float(np.max(np.abs(rel_target))) if g_ideal.size else 0.0,
        "max_abs_total_rel": float(np.max(np.abs(rel_total))) if g_ideal.size else 0.0,
        "sigma_cell_rel": float(sig_cell), "residual_sigma_floor": float(sig_cell),
        "iters": int(iters), "tol_rel": tol, "alpha": a, "sigma_pulse_rel": sp,
        "stuck_mask": stuck, "stuck_count": int(np.count_nonzero(stuck)),
        "bits": bits, "include_level": bool(include_level),
        "window_lo": lo, "window_hi": hi, "window_ratio": (hi / lo if lo > 0 else float("inf")),
        "is_oracle": False,
    }


def programming_error_matrix(w, x, s: float = DEFAULT_S,
                             g_base: Optional[float] = None,
                             *, trials: int = 1, seed: int = 0,
                             **kw) -> Dict:
    """**端到端**：编程后的电导经 **E8 `mvm_output`** 的输出相对误差（矩阵感知）。

    🔴 **维度约定（与 E8 一致）**：`w` 形状 `(n, m)` = （行/输入维, 列/输出维），
    `x` 长度 **n**（输入施加在行上），输出长度 **m**。
    （注意：这与 `crossbar_mvm` 的 `weights (M,N) = (输出, 输入)` 是**转置**关系 ——
    `mismatch.mvm_output` 走 `g.T @ x`。）

    `program_array`（一次编程）⟶ 多个试验 ⟶ 每次用 E8 的 `mvm_output` 算输出 ⟷ 理想。
    """
    W = np.asarray(w, dtype=float)
    xx = np.asarray(x, dtype=float)
    if W.ndim != 2:
        raise ValueError("w 须为二维 (n, m)")
    if xx.ndim != 1 or xx.shape[0] != W.shape[0]:
        raise ValueError("x 长度须等于 w 的行数 n=%d（E8 mvm_output 口径：g.T @ x）"
                         % W.shape[0])
    g_ideal = _ideal_conductances(W, s, g_base)
    y_ideal = mvm_output(g_ideal, xx)
    denom = np.abs(y_ideal)
    denom = np.where(denom < 1e-300, 1e-300, denom)
    signed = np.zeros((int(trials), g_ideal.shape[1]))
    for k in range(int(trials)):
        pa = program_array(W, s, g_base, seed=int(seed) + k, **kw)
        y = mvm_output(pa["g_prog"], xx)
        signed[k, :] = (y - y_ideal) / denom           # 🔴 **带符号**
    absm = np.abs(signed)
    return {"y_ideal": y_ideal,
            # 🔴 必须保留**带符号**版本：`std(|Z|) = σ·√(1−2/π) = 0.603σ`
            #    ⇒ 用绝对值序列估 σ 会系统性偏低 40%（判据口径血案）
            "rel_err_signed_matrix": signed,               # (trials, m) 带符号
            "rel_err_col0": signed[:, 0].tolist(),         # 单列**带符号**（与 σ 公式对拍）
            "rel_err_abs_matrix": absm,                    # (trials, m) 绝对值（算 max 用）
            "rel_err_trials": absm.max(axis=1).tolist(),   # 逐试验取列 max（极值统计量）
            "rel_err_max": float(np.max(absm)),
            "rel_err_mean": float(np.mean(absm)),
            "n_trials": int(trials), "is_oracle": False}


# ═══════════════════════════════════════════════════════════════════════════
# ⑦ 误差项（E15 格式）与报告
# ═══════════════════════════════════════════════════════════════════════════
def programming_budget_terms(n: int, m: Optional[int] = None, *,
                             w=None, s: float = DEFAULT_S,
                             g_base: Optional[float] = None,
                             bits: Optional[int] = None,
                             include_level: bool = True,
                             include_stuck: bool = False,
                             alpha_pulse: Optional[float] = None,
                             sigma_pulse_rel: Optional[float] = None,
                             stuck_p: Optional[float] = None) -> List[Dict]:
    """把权重编程误差做成 **E15 `make_term` 格式**的误差项（统一口径 = 相对满量程 %）。

    分类（🔴 分类不是形式主义 —— 决定它会不会被 1/√N 平均掉）：
      · `weight_prog_residual` **RANDOM**   写入噪声 ⇒ 单元独立 ⇒ 输出 `σ_cell/√N`
      · `weight_prog_level`    **BOUNDED**  电平量化有界（**N 无关**）—— 取**最坏单元**的半步长占比
      · `weight_prog_stuck`    **BOUNDED**  卡位最坏方向（默认不出现）

    🔴 `w=None` 时用 `canonical_weights(n, m)`（U(−1,1) 参考分布）——
    电平项**本质上依赖权重分布**（低电导单元的**相对**电平误差远大于高电导单元），
    故必须矩阵感知；参考分布已显式披露。
    """
    pr = WEIGHT_PROG_PROCESS
    nn = int(n)
    W = canonical_weights(nn, m) if w is None else np.asarray(w, dtype=float)
    include_level = bool(include_level)

    terms: List[Dict] = []

    # RANDOM —— 写入残差（矩阵无关：相对噪声地板 × 1/√N）
    sig_cell = noise_floor_sigma(
        float(pr["sigma_pulse_rel"] if sigma_pulse_rel is None else sigma_pulse_rel),
        float(pr["alpha_pulse"] if alpha_pulse is None else alpha_pulse))
    sig_out = residual_sigma_out(sig_cell, nn)
    terms.append(make_term(
        "weight_prog_residual", RANDOM, sig_out * 100.0, "E16",
        note="写-校验噪声地板 σ_cell=%.4f%% ÷ √N 律（G-4 闭式 ⟷ MC 已在门禁 B5 核对）"
             % (sig_cell * 100.0)))

    # BOUNDED —— 电平量化
    # 🔴 **界必须用 g_mean，不能用 min(g)**：电平在窗口内**等间距** ⇒ 每个单元的量化误差
    #    **绝对值**同为半步长 `half_step`（与 g 无关）⇒ 输出相对误差界 =
    #    `half_step·Σ|x| / |Σ g_i x_i|` = `half_step / g_mean`（同号权重 + 等 |x| 的理想化，
    #    与 E8/E9 同口径）。**低电导单元的"大相对误差"在求和里并不放大** ——
    #    真正决定输出误差的是「绝对步长 / 平均电导」。
    #    另单列 `worst_cell_rel = half_step/min(g)` 供低电导端告警（不进预算）。
    worst_cell = 0.0
    if include_level:
        g = _ideal_conductances(W, s, g_base)
        lo, hi = float(np.min(g)), float(np.max(g))
        b = int(pr["prog_bits"] if bits is None else bits)
        g_mean = float(np.mean(g)) if g.size else 0.0
        worst = level_bound_in_output(hi, lo, g_mean, b)
        worst_cell = level_bound_in_output(hi, lo, lo, b) if lo > 0 else 0.0
        terms.append(make_term(
            "weight_prog_level", BOUNDED, worst * 100.0, "E16",
            note="%d 位电平跨窗口 %.3g:1 · 界 = 半步长/平均电导（电平**等间距 ⇒ 绝对误差与 g 无关**）；"
                 "N 无关（有界项不被平均）；低电导端最坏单元 %.2f%% 仅作告警"
                 % (b, (hi / lo if lo > 0 else float("inf")), worst_cell * 100.0)))

    # BOUNDED —— 卡位（默认 p=0 ⇒ 不出现）
    ps = float(pr["stuck_p"] if stuck_p is None else stuck_p)
    if include_stuck and ps > 0.0:
        terms.append(make_term(
            "weight_prog_stuck", BOUNDED, stuck_error_bound_rel(ps, nn) * 100.0, "E16",
            note="卡位率 %.1e（良率 (1−p)^N）" % ps))

    return terms


def programming_report(w=None, n: Optional[int] = None,
                       m: Optional[int] = None, *, x=None,
                       include_level: bool = True,
                       include_stuck: bool = False,
                       bits: Optional[int] = None,
                       s: float = DEFAULT_S,
                       g_base: Optional[float] = None,
                       end_to_end_trials: int = 1,
                       stuck_p: Optional[float] = None,
                       seed: int = 0) -> Dict:
    """**编程通路报告**：误差项 + 噪声地板 + 脉冲数 + 良率 + 漂移 + 端到端（可选）。"""
    pr = WEIGHT_PROG_PROCESS
    if w is None:
        nn = int(n if n is not None else 8)
        W = canonical_weights(nn, m)
    else:
        W = np.asarray(w, dtype=float)
    nrow, ncol = W.shape

    a = float(pr["alpha_pulse"])
    sp = float(pr["sigma_pulse_rel"])
    tol = float(pr["tol_rel"])
    terms = programming_budget_terms(
        nrow, ncol, w=W, s=s, g_base=g_base, bits=bits,
        include_level=include_level, include_stuck=include_stuck, stuck_p=stuck_p)
    ps = float(pr["stuck_p"] if stuck_p is None else stuck_p)

    out: Dict = {
        "shape": [int(nrow), int(ncol)],
        "n_cells": int(nrow * ncol),
        "terms": terms,
        "noise_floor_sigma_cell": float(noise_floor_sigma(sp, a)),
        "iters_to_tol": int(iter_to_tolerance(1.0, tol, a)),
        "tol_rel": tol, "alpha": a, "sigma_pulse_rel": sp,
        "yield_cells": float(yield_fraction(nrow * ncol, ps)),
        "drift_common_mode_pct": float(drift_rel_pct(pr["t_read_s"], pr["t0_s"], pr["nu_drift"])),
        "drift_spread_pct": float(abs(pr["sigma_nu"] * math.log(pr["t_read_s"] / pr["t0_s"])) * 100.0),
        "process": dict(pr),
        "is_oracle": False,
    }
    if x is not None:
        out["end_to_end"] = programming_error_matrix(
            W, x, s=s, g_base=g_base, trials=int(end_to_end_trials), seed=int(seed),
            include_level=include_level, bits=bits, stuck_p=(ps if include_stuck else 0.0))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ⑧ 披露
# ═══════════════════════════════════════════════════════════════════════════
WEIGHT_PROG_DISCLOSURE: dict = {
    "route": "电子计算征程 E16 · 权重编程通路（补上「权重怎么写进去」这一此前完全不存在的一环）",
    "capability": "1T1R 类模拟电导的**写-校验**建模：电平量化（G-1）· 确定性轨迹（G-2）· "
                  "到容差脉冲数（G-3）· **写入噪声地板（G-4）** · 漂移幂律与重校准间隔（G-5）· "
                  "良率 (1−p)^N · 差分对 · 矩阵感知的端到端编程误差（接 E8 `mvm_output`）· "
                  "**E15 误差预算项**（RANDOM/BOUNDED 分类）",
    "golden": "五个闭式：`1/(2^k−1)` · `e_0(1−α)^k` · `ceil(ln(tol/e0)/ln(1−α))` · "
              "`σ_p/√(α(2−α))` · `(t/t0)^(−ν)` 与 `t0(1−β)^(−1/ν)`；"
              "另有**良率闭式 `(1−p)^N`**（与直接枚举对拍）与**差分对代数精确性**",
    "independent_cross_check": "① 零噪声 MC 均值 ⟷ G-2 闭式（第二条路径，非自证）；"
                               "② 噪声地板 MC ⟷ G-4 闭式；③ `σ·√N` 近恒定（1/√N 律）；"
                               "④ 良率闭式 ⟷ 逐单元枚举；⑤ 编程后电导经 **E8 `mvm_output`** 的输出误差 ≤ 解析预算界",
    "bridge_to_e15": "`programming_budget_terms()` 返回 E15 `make_term` 格式；"
                     "注入 `budget.collect_terms(include_programming=True, prog_terms=…)`。"
                     "🔴 **默认 OFF ⇒ E15 已发布数字逐位不变**（保护性约束）",
    "honest_boundary": "参数（α / σ_p / tol / ν / p_stuck）为**公开典型量级占位 · 非 PDK · 无实测锚** ⇒ "
                       "结论随参数变，报告必须携带参数；器件模型为**行为级**（比例修正 + 加性噪声），"
                       "**不含**细丝动力学 / 脉冲宽度依赖 / 温度加速；无 endurance/retention 联合退化；"
                       "**只覆盖静态**（不含编程时间与能耗）；**不报 TOPS/TOPS-W/fJ/op**",
    "drift_semantics": "🔴 **共模漂移（可被单次全局增益校准消除）单列报告，不进预算**；"
                       "进预算的只有 **ν 的单元间离散**（校准不掉）—— "
                       "一个能被单次校准消掉的项，不是精度上限",
    "protective": "**不改任何既有模块的默认值与闭式**；`budget.collect_terms` 新增参数默认 False "
                  "⇒ E15 的 8×8（4.06012% / 4.622 位）与 5% 上界（N≤12）逐位不变",
}


# ═══════════════════════════════════════════════════════════════════════════
# ⑨ 自检
# ═══════════════════════════════════════════════════════════════════════════
def weight_prog_self_check(verbose: bool = True) -> bool:
    """模块自检 **14 项**（闭式 golden + 独立交叉 + 保护性约束）。"""
    res = True

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        nonlocal res
        if verbose:
            print(("PASS | " if cond else "FAIL | ") + name
                  + (("  :: " + detail) if detail else ""))
        res = res and bool(cond)
        return bool(cond)

    pr = WEIGHT_PROG_PROCESS

    # ① G-1 电平量化闭式
    chk("① G-1 电平量化闭式：levels(6)=64 · lsb_rel(6)=1/63 · 界=1/126",
        program_levels(6) == 64 and abs(level_lsb_rel(6) - 1.0 / 63.0) < 1e-18
        and abs(level_error_bound_rel(6) - 1.0 / 126.0) < 1e-18,
        "lsb=%.10f" % level_lsb_rel(6))

    # ② 量化穷举：全电平自映射 + 界恰好取到
    lv = program_levels(6)
    grid = np.arange(lv) / float(lv - 1)
    chk("② 量化穷举：64 个电平自映射 · 随机点上界恰为 lsb/2（紧界，非松弛）",
        float(np.max(np.abs(quantize_to_levels(grid, 6) - grid))) < 1e-15
        and abs(float(np.max(np.abs(quantize_to_levels(grid + 0.5 / (lv - 1), 6)
                                                 - (grid + 0.5 / (lv - 1))))) * 2
                - level_lsb_rel(6)) < 1e-15)

    # ③ G-2 轨迹 ⟷ 闭式（逐点）
    tr = write_verify_closed(1.0, 0.30, 12)
    chk("③ G-2 确定性轨迹 ⟷ 闭式 e0(1−α)^k：逐点机精度一致",
        all(abs(tr["errors"][k] - 1.0 * 0.7 ** k) < 1e-15 for k in range(13)),
        "e_12=%.6f" % tr["errors"][12])

    # ④ G-3 迭代数 ⟷ 闭式（含紧性：k*−1 步仍在容差外）
    k = iter_to_tolerance(1.0, 0.01, 0.30)
    chk("④ G-3 脉冲数 ⟷ 闭式 ceil(ln(tol/e0)/ln(1−α))=13 · 且「k*−1 步尚未达标」（紧性）",
        k == 13 and 0.7 ** k <= 0.01 < 0.7 ** (k - 1),
        "k*=%d · e=%.6f" % (k, 0.7 ** k))

    # ⑤ G-4 噪声地板 ⟷ MC（方法学独立）
    closed = noise_floor_sigma(pr["sigma_pulse_rel"], pr["alpha_pulse"])
    mc = write_verify_stochastic(sigma_pulse_rel=pr["sigma_pulse_rel"],
                                 alpha=pr["alpha_pulse"], max_pulses=64,
                                 seed=0, trials=4000)
    rel5 = abs(mc["sigma_residual"] - closed) / closed
    chk("⑤ 🔴 G-4 噪声地板 σ_p/√(α(2−α)) ⟷ MC（rel<3%）",
        rel5 < 0.03, "闭式=%.6f ⟷ MC=%.6f（rel=%.2f%%）" % (closed, mc["sigma_residual"], rel5 * 100))

    # ⑥ 零噪声 MC ⟷ 闭式（第二条独立路径）
    mcz = write_verify_stochastic(sigma_pulse_rel=0.0, alpha=0.30, max_pulses=10,
                                  tol_rel=1e-12, seed=1, trials=200)
    chk("⑥ 🔴 零噪声 MC 均值 ⟷ G-2 闭式（独立于解析式的第二条路径，rel<1e-9）",
        abs(mcz["mean_relative_error"] - 0.7 ** 10) < 1e-9,
        "MC=%.12f ⟷ 闭式=%.12f" % (mcz["mean_relative_error"], 0.7 ** 10))

    # ⑦ 1/√N 律
    mcv = write_verify_stochastic(sigma_pulse_rel=pr["sigma_pulse_rel"],
                                  alpha=pr["alpha_pulse"], seed=3, trials=4000)
    s8 = residual_sigma_out(float(mcv["sigma_residual"]), 8)
    s32 = residual_sigma_out(float(mcv["sigma_residual"]), 32)
    chk("⑦ 输出 1/√N 律：σ_out(32) == σ_out(8)/2（精确）",
        abs(s8 / s32 - 2.0) < 1e-12, "σ8=%.6f%% σ32=%.6f%%" % (s8 * 100, s32 * 100))

    # ⑧ G-5 漂移闭式 + 重校准间隔互验 + 单调
    d1 = drift_factor(1000.0, 1.0, 0.05)
    tm = recal_interval(1.0, 0.05, 0.05)
    chk("⑧ G-5 漂移闭式 (t/t0)^(−ν) · 重校准间隔闭式代回 ⟹ drift(t_max)==0.95 · 单调递减",
        abs(d1 - 1000.0 ** (-0.05)) < 1e-15
        and abs(drift_factor(tm, 1.0, 0.05) - 0.95) < 1e-12
        and drift_factor(100.0, 1.0, 0.05) > drift_factor(1000.0, 1.0, 0.05),
        "g(1000s)/g0=%.4f ⟹ 共模掉 %.2f%% · t_max=%.4f s" % (d1, (1 - d1) * 100, tm))

    # ⑨ 良率闭式 ⟷ 枚举
    p = 0.01
    rng = np.random.default_rng(7)
    big = float(np.mean(np.all(rng.random((20000, 8)) >= p, axis=1)))
    chk("⑨ 良率闭式 (1−p)^N ⟷ 直接枚举（p>0 · N=8 · rel<2%）",
        abs(yield_fraction(8, p) - (1 - p) ** 8) < 1e-15
        and abs(big - (1 - p) ** 8) < 0.02,
        "闭式=%.8f ⟷ 枚举=%.6f" % (yield_fraction(8, p), big))

    # ⑩ 差分对代数精确
    ds = [differential_pair(w, 1e-4, w_max=1.0) for w in (-1.0, -0.3, 0.0, 0.7, 1.0)]
    chk("⑩ 差分对：g± = g_base ± s·w 且 w 恢复精确 · g− > 0",
        all(d["exact"] and d["g_min_positive"] for d in ds),
        "w=0.7 ⟹ g+=%.4e g−=%.4e" % (ds[3]["g_plus"], ds[3]["g_minus"]))

    # ⑪ program_array：误差有界 + 可复现
    W = canonical_weights(8, 8)
    pa1 = program_array(W, seed=11)
    pa2 = program_array(W, seed=11)
    bound = float(np.max(np.abs(pa1["rel_level_err"]))) + 5.0 * pa1["sigma_cell_rel"]
    chk("⑪ program_array：种定可复现 · 总误差 ≤ 电平界 + 5σ",
        np.allclose(pa1["g_prog"], pa2["g_prog"])
        and pa1["max_abs_total_rel"] <= bound,
        "max|rel|=%.4f%% ≤ 界 %.4f%%" % (pa1["max_abs_total_rel"] * 100, bound * 100))

    # ⑫ E15 格式误差项合法 + 类别正确
    terms = programming_budget_terms(8, w=W, include_level=True)
    names = {t["name"]: t for t in terms}
    chk("⑫ E15 格式项：residual=**RANDOM** · level=**BOUNDED**（分类决定是否被 1/√N 平均）",
        set(names) == {"weight_prog_residual", "weight_prog_level"}
        and names["weight_prog_residual"]["category"] == RANDOM
        and names["weight_prog_level"]["category"] == BOUNDED
        and all(t["rel_pct"] >= 0.0 for t in terms),
        "residual=%.4f%% level=%.4f%%"
        % (names["weight_prog_residual"]["rel_pct"], names["weight_prog_level"]["rel_pct"]))

    # ⑬ 🔴 保护性约束：默认口径下 E15 数字逐位不变 + 披露
    base = combine(collect_terms(8, 8))
    withp = combine(collect_terms(8, 8, include_programming=True, prog_terms=terms))
    chk("⑬ 🔴 保护性约束：默认 include_programming=False ⇒ E15 的 8×8 合成逐位不变（4.06012%）· "
        "开启后**严格变差**",
        abs(base["worst_pct"] - 4.06012) < 0.01 and withp["worst_pct"] > base["worst_pct"]
        and "非 PDK" in WEIGHT_PROG_DISCLOSURE["honest_boundary"],
        "默认=%.5f%% ⟷ 含编程=%.5f%%" % (base["worst_pct"], withp["worst_pct"]))

    # ⑭ 🔴 矩阵感知 σ 严格式：等电导时**精确退化**为 1/√N 理想式（条件数 == 1）
    geq = np.full(8, 3.0e-4)          # 等电导
    gdis = np.linspace(1.0e-4, 5.0e-4, 8)   # 有离散
    f_ideal = residual_sigma_out(0.007, 8)
    f_eq = output_sigma_matrix_aware(geq, np.ones(8), 0.007)
    f_dis = output_sigma_matrix_aware(gdis, np.ones(8), 0.007)
    chk("⑭ 🔴 矩阵感知 σ 严格式：**等电导 ⇒ 精确退化为 σ/√N**（条件数 == 1）· "
        "电导离散 ⇒ 严格式 **>** 理想式",
        abs(f_eq - f_ideal) < 1e-15 and f_dis > f_ideal,
        "等电导=%.6f%% ⟷ 理想=%.6f%% · 离散=%.6f%%（条件数 %.4f）"
        % (f_eq * 100, f_ideal * 100, f_dis * 100, f_dis / f_ideal))

    if verbose:
        print("── weight_prog 自检 %s ──" % ("全绿" if res else "有 FAIL"))
    return res


__all__ = [
    "WEIGHT_PROG_PROCESS", "DEFAULT_S", "DEFAULT_G_BASE_FACTOR",
    "program_levels", "level_lsb_rel", "level_error_bound_rel", "level_bound_in_output",
    "quantize_to_levels",
    "write_verify_closed", "iter_to_tolerance", "noise_floor_sigma",
    "write_verify_stochastic", "residual_sigma_out", "output_sigma_matrix_aware",
    "drift_factor", "drift_rel_pct", "recal_interval", "drift_curve",
    "yield_fraction", "stuck_error_bound_rel",
    "differential_pair",
    "canonical_weights", "program_array", "programming_error_matrix",
    "programming_budget_terms", "programming_report",
    "WEIGHT_PROG_DISCLOSURE", "weight_prog_self_check",
]
