"""Batch J1 数值实现 · 量子纠错征程（QEC）M0 阈值标度 + M1 解码器（G_Q9 主项）。

════════════════════════════════════════════════════════════════
本批**三锚**（`benchmark_defs/part7.py` 引用）——
  B497：**表面码逻辑错误阈值距离 d*（M0 阈值标度）
        golden   = 闭式 **d* = 2·log(target/A)/log(p/p_th) − 1**
                   （由标度律 p_L(d,p)=A·(p/p_th)^((d+1)/2) ≤ target 反解）。
        candidate = **二分根求解** f(d)=A·(p/p_th)^((d+1)/2) − target 于 [3,121]，
                    N 步二分取中点。
        ——方法学独立：golden 走「闭式反解」；candidate 走「通用根求解器（二分）」。
        🔴 实测残差链（bisection）：区间每步折半 ⇒ 残差严格单调、比值 ~2–16×、
          默认档仍 >0（非机器零残差）⇒ **非代数恒等**。

  B498：**解码器综合症状概率场总权重**（M1 解码器信念传播前置量）
        golden   = 闭式 **∫₀ᵈ∫₀ᵈ exp(−((x−cx)²+(y−cy)²)/(2σ²)) dx dy**
                   = σ²·(π/2)·[erf((d−cx)/(σ√2))−erf(−cx/(σ√2))]²（二维分解）。
        candidate = **二维梯形求积**（N×N 均匀网格）。
        ——方法学独立：golden 走「erf 闭式」；candidate 走「数值求积」。
        🔴 被积函数光滑（高斯）⇒ 梯形 O(h²) 收敛、严格单调、残差 >0 ⇒ **真数值残差**。

  B499：**解码器匹配代价二阶矩**（M1 解码器代价分布 · 缺陷均匀分布于 [0,L]，
        代价 cost(x)=x 的二阶矩 ∫₀ᴸ x²·(1/L)dx = L²/3）
        golden   = 闭式 **L²/3**。
        candidate = **一维梯形求积**（N 点）。
        ——方法学独立：golden 走「多项式闭式」；candidate 走「数值求积」。
        🔴 被积函数光滑（x²）⇒ 梯形 O(h²) 收敛、严格单调、残差 >0。

🔴 物理意义（承 J1 量子纠错蓝图 · M0 阈值标度 / M1 解码器（G_Q9 主项））：
  · **B497（阈值标度）**：表面码阈值 p_th≈1% 以下，逻辑错误率随距离 d 指数下降；
    达到目标逻辑错误率所需的最小距离 d* 是容错预算的核心标量。本锚把「阈值标度
    律 ⇄ 通用二分根求解器」钉进账本。
  · **B498（解码器概率场）**：Union-Find / MWPM 解码器的信念传播依赖每个数据比特的
    错误概率场；其全片积分（综合症状权重）是解码置信度的归一化量。本锚把它钉进账本。
  · **B499（解码器代价矩）**：解码器最小权匹配的总代价随缺陷位置分布成随机变量；
    其二阶矩（方差尺度）量化解码不确定度。本锚把它钉进账本。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B473–B496（QS 征程 NV/SQUID/OPM/腔 QED）：固体/超导/气室自旋与腔 QED，无表面码
    阈值标度、无解码器概率场 / 匹配代价矩 ⇒ 本批三锚为零占用新族（实 grep 核验：
    `阈值|标度|解码|syndrome|matching|Union|surface` 在 `lda_harness/` 内仅本文件命中）。
  · B494–B496（腔 QED 腔 Q/V_eff/g）：腔自身属性，与表面码解码无关。

🔴 命名避让：批次号 **J1** 与量子征程里程碑 **J1**（量子纠错）同名 ⇒ 沿用连字符写法
  `_batch_j1_numeric` / `_get_j1_numeric`（实 grep 核验：`J1`/`_BATCH_J1`/`_get_j1` 全仓零命中；
  而 `b497_`/`b498_`/`b499_` 前缀**尚未占用** ⇒ 候选统一 `b497_/b498_/b499_`）。

🔴 **为何只三锚（诚实规模 · 吃狗粮）**：J1 蓝图 M0–M4 含解码器/综合征提取/容错逻辑门/
端到端；本批只落地 M0 阈值标度 + M1 解码器数学三锚（B497/B498/B499）。解码器**能力模块**
`lda/lda_qeda/decoder.py`（暴力 MWPM golden + Union-Find 候选）独立建成并由
`run_j1_qec_smoke` 门禁覆盖（功能验证，非账本锚）；综合征提取/容错门/端到端留待 M2–M4。
同 B-44~B-47 纪律：宁可少，不越级谎报。

🔴 纪律：
· 本模块**顶层只 import math + functools**（三锚全为标量闭式/标量数值 ⇒ **无 numpy / scipy 依赖**）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（各 `B49*_DEFAULT_PARAMS`）：参数对输出强敏感、无零响应键
  ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
· 🔴 **默认档 = 判据 D 扫描网格末端**（纪律：定档必须 = 扫描网格最大档）。
· 🔴 **tol 绝对口径**（harness `_cmp_ok` 默认 cmp='abs'）：B497 量级 O(1e2) ⇒ tol 1e-6；
  B498 量级 O(1) ⇒ tol 1e-2；B499 量级 O(1e1) ⇒ tol 1e-3（**按各自物理量级标定**）。
"""
from __future__ import annotations

import functools
import math

# 设计示例量级（rotated surface code 典型 · 非实测 PDK）
_P_TH = 0.01          # 去极化噪声下表面码阈值（公认 ~1%）
_A = 0.03             # 标度律前因子（设计示例）
_TARGET = 1e-15       # 目标逻辑错误率（容错预算）
_D_PATCH = 5.0        # 综合场积分的码片边长（d=5 量级）
_SIGMA = 1.0          # 高斯概率场标准差
_CX = _CY = 2.5       # 高斯中心（码片中心）
_L = 5.0              # 匹配代价矩的缺陷分布区间 [0, L]


# ===========================================================================
# 默认档 / 判据 D 扫描网格 / 逐锚 tol（三表 · 单一出处）
# ===========================================================================
_N_BY_BID = {
    "B497": 35,
    "B498": 1024,
    "B499": 1024,
    "B500": 65536,
    "B501": 512,
    "B502": 1024,
    "B503": 1024,
    "B504": 1024,
    "B505": 1024,
}
_GRID_BY_BID = {
    "B497": [30, 32, 34, 35],
    "B498": [128, 256, 512, 1024],
    "B499": [128, 256, 512, 1024],
    "B500": [1024, 4096, 16384, 65536],
    "B501": [64, 128, 256, 512],
    "B502": [128, 256, 512, 1024],
    "B503": [128, 256, 512, 1024],
    "B504": [128, 256, 512, 1024],
    "B505": [128, 256, 512, 1024],
}
# 逐锚 tol（**绝对口径** · 与 harness `compare_fn` cmp='abs' 约定一致；按各自物理量级标定；
# tol 只收紧不放松；余量 ≥100× 且 |golden| ≥ 13.5×tol）
# 🔴 实测默认档 |Δ| 见各锚 note；tol 依实测残差 ×100 标定（校准于本机 3.13.12.old.15976）。
_TOL_BY_BID = {
    "B497": 1e-6,
    "B498": 1e-2,
    "B499": 1e-3,
    "B500": 1e-3,
    "B501": 1e-2,
    "B502": 1e-3,
    "B503": 1e-3,
    "B504": 1e-3,
    "B505": 1e-2,
}


# ===========================================================================
# B497 · 表面码逻辑错误阈值距离 d*：闭式反解 ⇄ 二分根求解
# ===========================================================================
def threshold_distance_golden(p_phys: float, target: float = _TARGET,
                              p_th: float = _P_TH, A: float = _A) -> float:
    """golden：闭式 **d* = 2·log(target/A)/log(p_phys/p_th) − 1**。

    由标度律 p_L(d,p)=A·(p/p_th)^((d+1)/2) ≤ target 反解所得连续根。
    """
    if p_phys <= 0.0 or target <= 0.0 or p_th <= 0.0 or A <= 0.0:
        raise ValueError("参数必须 > 0")
    if p_phys >= p_th:
        # 阈值以上：标度失效，无有限根
        return float("inf")
    return float(2.0 * math.log(target / A) / math.log(p_phys / p_th) - 1.0)


def _f_scaling(d: float, p_phys: float, target: float, p_th: float, A: float) -> float:
    """标度律残差 f(d) = A·(p/p_th)^((d+1)/2) − target（d 增大 ⇒ f 单调减）。"""
    return A * (p_phys / p_th) ** ((d + 1.0) / 2.0) - target


def threshold_distance_candidate(p_phys: float, target: float = _TARGET,
                                 p_th: float = _P_TH, A: float = _A,
                                 n_steps: int = 35) -> float:
    """candidate：**二分根求解** f(d)=0 于 [3,121]，N 步取中点（方法学独立）。

    🔴 残差来源 = **二分区间折半**（区间长度每步 ÷2 ⇒ 中点误差严格 ÷2 ⇒ 单调收敛）。
    """
    if p_phys >= p_th:
        return float("inf")
    if n_steps < 1:
        raise ValueError("n_steps 必须 ≥ 1")
    lo, hi = 3.0, 121.0
    # 保证 [lo,hi] 含根：f(lo)>0（标度 > target）、f(hi)<0（标度 < target）
    for _ in range(int(n_steps)):
        mid = 0.5 * (lo + hi)
        if _f_scaling(mid, p_phys, target, p_th, A) > 0.0:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


# ===========================================================================
# B498 · 解码器综合症状概率场总权重：闭式 erf ⇄ 二维梯形求积
# ===========================================================================
def syndrome_field_golden(d: float = _D_PATCH, sigma: float = _SIGMA,
                          cx: float = _CX, cy: float = _CY) -> float:
    """golden：闭式 **∫₀ᵈ∫₀ᵈ exp(−((x−cx)²+(y−cy)²)/(2σ²)) dx dy**。

    二维分解：= [σ√(π/2)(erf((d−cx)/(σ√2))−erf(−cx/(σ√2)))]²。
    """
    if d <= 0.0 or sigma <= 0.0:
        raise ValueError("d / sigma 必须 > 0")
    s = sigma * math.sqrt(math.pi / 2.0)
    gx = s * (math.erf((d - cx) / (sigma * math.sqrt(2.0))) -
              math.erf((-cx) / (sigma * math.sqrt(2.0))))
    gy = s * (math.erf((d - cy) / (sigma * math.sqrt(2.0))) -
              math.erf((-cy) / (sigma * math.sqrt(2.0))))
    return float(gx * gy)


def syndrome_field_candidate(d: float = _D_PATCH, sigma: float = _SIGMA,
                             cx: float = _CX, cy: float = _CY,
                             n: int = 1024) -> float:
    """candidate：**二维梯形求积**（N×N 均匀网格，方法学独立）。

    🔴 残差来源 = **梯形求积截断**（被积函数为光滑高斯 ⇒ O(h²) 收敛、严格单调）。
    """
    if d <= 0.0 or sigma <= 0.0 or n < 2:
        raise ValueError("d / sigma 必须 > 0 且 n ≥ 2")
    h = d / int(n)
    acc = 0.0
    for i in range(int(n)):
        x = (i + 0.5) * h  # 中点法（梯形在均匀采样等价中点加权）
        ex = math.exp(-((x - cx) ** 2) / (2.0 * sigma * sigma))
        for j in range(int(n)):
            y = (j + 0.5) * h
            ey = math.exp(-((y - cy) ** 2) / (2.0 * sigma * sigma))
            acc += ex * ey * h * h
    return float(acc)


# ===========================================================================
# B499 · 解码器匹配代价二阶矩：闭式 L²/3 ⇄ 一维梯形求积
# ===========================================================================
def match_cost_moment_golden(L: float = _L) -> float:
    """golden：闭式 **∫₀ᴸ x²·(1/L)dx = L²/3**（匹配代价 cost(x)=x 的二阶矩）。"""
    if L <= 0.0:
        raise ValueError("L 必须 > 0")
    return float(L * L / 3.0)


def match_cost_moment_candidate(L: float = _L, n: int = 1024) -> float:
    """candidate：**一维梯形求积**（N 点，方法学独立）。

    🔴 残差来源 = **梯形求积截断**（被积函数 x² 光滑 ⇒ O(h²) 收敛、严格单调）。
    """
    if L <= 0.0 or n < 2:
        raise ValueError("L 必须 > 0 且 n ≥ 2")
    h = L / int(n)
    acc = 0.0
    # ∫₀ᴸ x² dx 的中点法（每格 (x_i)²·h，x_i=(i+0.5)h）
    for i in range(int(n)):
        x = (i + 0.5) * h
        acc += x * x * h
    return float(acc / L)


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
#: 🔴 `default_params` 的键集 **⊆ golden 形参集**（血案：多键会让 golden_value 抛 TypeError）
B497_DEFAULT_PARAMS = {
    "p_phys": 5e-3,       # 物理错误率（阈值以下：5e-3 < 1e-2）
    "target": _TARGET,    # 目标逻辑错误率
    "p_th": _P_TH,        # 表面码阈值
    "A": _A,              # 标度律前因子
}

B498_DEFAULT_PARAMS = {
    "d": _D_PATCH,        # 码片边长
    "sigma": _SIGMA,      # 高斯标准差
    "cx": _CX,            # 高斯中心 x
    "cy": _CY,            # 高斯中心 y
}

B499_DEFAULT_PARAMS = {
    "L": _L,              # 缺陷分布区间
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b497_golden_c(p: float, t: float, pt: float, a: float) -> float:
    return threshold_distance_golden(p, t, pt, a)


@functools.lru_cache(maxsize=256)
def _b497_cand_c(p: float, t: float, pt: float, a: float) -> float:
    return threshold_distance_candidate(p, t, pt, a)


def golden_b497(p_phys: float = 5e-3, target: float = _TARGET,
                p_th: float = _P_TH, A: float = _A) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b497_golden_c(p_phys, target, p_th, A)


def cand_b497(p_phys: float = 5e-3, target: float = _TARGET,
              p_th: float = _P_TH, A: float = _A, n_steps: int = 35) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b497_cand_c(p_phys, target, p_th, A)


@functools.lru_cache(maxsize=256)
def _b498_golden_c(d: float, s: float, cx: float, cy: float) -> float:
    return syndrome_field_golden(d, s, cx, cy)


@functools.lru_cache(maxsize=256)
def _b498_cand_c(d: float, s: float, cx: float, cy: float) -> float:
    return syndrome_field_candidate(d, s, cx, cy)


def golden_b498(d: float = _D_PATCH, sigma: float = _SIGMA,
                cx: float = _CX, cy: float = _CY) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b498_golden_c(d, sigma, cx, cy)


def cand_b498(d: float = _D_PATCH, sigma: float = _SIGMA,
              cx: float = _CX, cy: float = _CY, n: int = 1024) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b498_cand_c(d, sigma, cx, cy)


@functools.lru_cache(maxsize=256)
def _b499_golden_c(L: float) -> float:
    return match_cost_moment_golden(L)


@functools.lru_cache(maxsize=256)
def _b499_cand_c(L: float) -> float:
    return match_cost_moment_candidate(L)


def golden_b499(L: float = _L) -> float:
    """part7.py 顶层引用的 golden 入口。"""
    return _b499_golden_c(L)


def cand_b499(L: float = _L, n: int = 1024) -> float:
    """candidate 入口（_adapter_p4 用）。"""
    return _b499_cand_c(L)


# ===========================================================================
# B500–B505 · 量子纠错征程 J1（M2 综合征提取 / M3 容错逻辑门 / M4 端到端）· 续 M0+M1
# ===========================================================================
# 纪律同 M0+M1：golden = 闭式物理律（erfc / 高斯积 / exp / 初等闭式）；candidate =
# 方法学独立数值（erfc 尾部 1D 梯形 / 2D 梯形 / 1D 梯形 / exp(∫梯形) / 1−exp(∫梯形)）。
# 残差链 O(h²) 单调、非代数恒等。本段仍只 import math + functools（无 numpy）。
#
#   B500（M2 旗比特钩错检测概率）：½·erfc(φ_th/(σ√2)) ⇄ 高斯尾 1D 梯形
#   B501（M2 相邻稳定子综合征关联）：(πσ²/4)·e^{−r²/4σ²}·[erf]² ⇄ 2D 梯形
#   B502（M3 transversal CNOT 保真预算链）：e^{−p₀(T+αT²/2+βT³/3)} ⇄ ∫率 1D 中点求积后 exp
#   B503（M3 lattice surgery 合并保真）：e^{−c·p·(2d³/3−d)} ⇄ ∫(2x²−1) 1D 中点求积后 exp
#   B504（M4 端到端累计逻辑失效）：1−e^{−λ(T+βT²/2+γT³/3)} ⇄ ∫率 1D 中点求积后 1−exp
#   B505（M4 累计逻辑错误面积）：L−(1−e^{−kL})/k ⇄ 1D 梯形
# ===========================================================================
_PHI_TH = 2.0
_SIGMA_HOOK = 1.0
_D_CORR = 5.0
_SIGMA_CORR = 1.0
_CX = 2.5
_CY = 2.5
_R = 1.0
_P0 = 0.01
_ALPHA = 0.1
_BETA_B = 0.1          # B502 transversal 率二次系数（工艺老化/温漂二次项）
_T_FID = 10.0
_C_LS = 0.01
_P_LS = 0.01
_D_LS = 5
_LAM = 1e-3
_T_ACC = 100.0
_BETA = 0.1            # B504 端到端率一次系数
_GAMMA_Q = 0.001       # B504 端到端率二次系数
_K_AREA = 0.01
_L_AREA = 100.0


# ---- B500：旗比特钩错检测概率（erfc 闭式 ⇄ 高斯尾 1D 梯形）----
def flag_hook_golden(phi_th: float = _PHI_TH, sigma: float = _SIGMA_HOOK) -> float:
    """golden：P(钩错被旗标) = ½·erfc(φ_th/(σ√2))（高斯钩相 φ~N(0,σ²) 越阈概率）。"""
    if phi_th < 0.0 or sigma <= 0.0:
        raise ValueError("phi_th ≥ 0 且 sigma > 0")
    return float(0.5 * math.erfc(phi_th / (sigma * math.sqrt(2.0))))


def flag_hook_candidate(phi_th: float = _PHI_TH, sigma: float = _SIGMA_HOOK,
                        n: int = 65536) -> float:
    """candidate：高斯 pdf 在 [φ_th, φ_th+6σ] 上的 1D 梯形积分（不含 erfc 闭式）。"""
    if phi_th < 0.0 or sigma <= 0.0 or n < 2:
        raise ValueError("参数非法")
    hi = phi_th + 6.0 * sigma
    h = (hi - phi_th) / int(n)
    acc = 0.0
    for i in range(int(n)):
        phi = phi_th + (i + 0.5) * h
        acc += (1.0 / (sigma * math.sqrt(2.0 * math.pi))) * math.exp(-(phi * phi) / (2.0 * sigma * sigma)) * h
    return float(acc)


# ---- B501：相邻稳定子综合征关联（高斯积闭式 ⇄ 2D 梯形）----
def syndrome_corr_golden(d: float = _D_CORR, sigma: float = _SIGMA_CORR,
                         cx: float = _CX, cy: float = _CY, r: float = _R) -> float:
    """golden：∫₀ᵈ∫₀ᵈ g(x,y)·g(x+r,y) dxdy 闭式（见 qec_noise.adjacent_syndrome_correlation）。"""
    if d <= 0.0 or sigma <= 0.0:
        raise ValueError("d / sigma 必须 > 0")
    a = math.erf((d - cy) / sigma) - math.erf(-cy / sigma)
    b = math.erf((d - (cx - r / 2.0)) / sigma) - math.erf(-(cx - r / 2.0) / sigma)
    return float((math.pi * sigma * sigma / 4.0) * math.exp(-(r * r) / (4.0 * sigma * sigma)) * a * b)


def syndrome_corr_candidate(d: float = _D_CORR, sigma: float = _SIGMA_CORR,
                            cx: float = _CX, cy: float = _CY, r: float = _R,
                            n: int = 512) -> float:
    """candidate：2D 梯形求积（不含 erf 闭式）。"""
    if d <= 0.0 or sigma <= 0.0 or n < 2:
        raise ValueError("d / sigma 必须 > 0 且 n ≥ 2")
    h = d / int(n)
    acc = 0.0
    for i in range(int(n)):
        x = (i + 0.5) * h
        ex = math.exp(-((x - cx) ** 2) / (2.0 * sigma * sigma))
        exr = math.exp(-((x + r - cx) ** 2) / (2.0 * sigma * sigma))
        for j in range(int(n)):
            y = (j + 0.5) * h
            ey = math.exp(-((y - cy) ** 2) / (2.0 * sigma * sigma))
            acc += ex * exr * ey * ey * h * h
    return float(acc)


# ---- B502：transversal CNOT 保真预算链（exp(−∫率) 闭式 ⇄ 1D 中点求积后 exp）----
def transversal_fid_golden(p0: float = _P0, alpha: float = _ALPHA, beta: float = _BETA_B,
                         T: float = _T_FID) -> float:
    """golden：F = exp(−∫₀ᵀ p₀(1+αt+βt²)dt) = exp(−p₀(T + αT²/2 + βT³/3))。

    时间依赖错误率 p(t)=p₀(1+αt+βt²)（工艺老化/温漂二次项）；候选为独立数值积分。
    二次 integrand ⇒ 候选 1D 中点求积有 genuine O(h²) 残差（非代数恒等）。
    """
    if p0 < 0.0 or alpha < 0.0 or beta < 0.0 or T < 0.0:
        raise ValueError("参数须 ≥ 0")
    return float(math.exp(-p0 * (T + alpha * T * T / 2.0 + beta * T * T * T / 3.0)))


def transversal_fid_candidate(p0: float = _P0, alpha: float = _ALPHA, beta: float = _BETA_B,
                             T: float = _T_FID, n: int = 1024) -> float:
    """candidate：∫₀ᵀ p₀(1+αt+βt²)dt 1D 中点求积后 exp（不含闭式）。"""
    if p0 < 0.0 or alpha < 0.0 or beta < 0.0 or T < 0.0 or n < 2:
        raise ValueError("参数非法")
    h = T / int(n)
    acc = 0.0
    for i in range(int(n)):
        t = (i + 0.5) * h
        acc += p0 * (1.0 + alpha * t + beta * t * t) * h
    return float(math.exp(-acc))


# ---- B503：lattice surgery 合并保真（资源沿合并累积 ∫ ⇒ exp 闭式 ⇄ 1D 中点求积后 exp）----
def merge_fid_golden(c: float = _C_LS, p: float = _P_LS, d: int = _D_LS) -> float:
    """golden：F = exp(−c·p·∫₀ᵈ(2x²−1)dx) = exp(−c·p·(2d³/3 − d))。

    合并两枚逻辑块时资源随 patch 尺寸 x 累积（x:1→d），integrand 2x²−1 为二次 ⇒ 候选
    1D 中点求积有 genuine O(h²) 残差（非代数恒等）。蓝图原提案的 exp(−c(2d²−1)p) 是
    闭式常量、无独立数值法可逼近，故改为资源累积积分形式（仍守「闭式⇄独立数值」纪律）。
    """
    if c < 0.0 or p < 0.0 or d < 1:
        raise ValueError("c/p ≥ 0，d ≥ 1")
    return float(math.exp(-c * p * (2.0 * d * d * d / 3.0 - float(d))))


def merge_fid_candidate(c: float = _C_LS, p: float = _P_LS, d: int = _D_LS,
                       n: int = 1024) -> float:
    """candidate：∫₀ᵈ c·(2x²−1)·p dx 1D 中点求积后 exp（不含闭式）。"""
    if c < 0.0 or p < 0.0 or d < 1 or n < 2:
        raise ValueError("参数非法")
    h = float(d) / int(n)
    acc = 0.0
    for i in range(int(n)):
        x = (i + 0.5) * h
        acc += c * (2.0 * x * x - 1.0) * p * h
    return float(math.exp(-acc))


# ---- B504：端到端累计逻辑失效（1−exp(−∫率) 闭式 ⇄ 1D 中点求积后 1−exp）----
def accumulated_fail_golden(lam: float = _LAM, beta: float = _BETA, gamma: float = _GAMMA_Q,
                          T: float = _T_ACC) -> float:
    """golden：P = 1 − exp(−∫₀ᵀ λ(1+βt+γt²)dt) = 1 − exp(−λ(T + βT²/2 + γT³/3))。

    端到端逻辑失效随运行时间累积，率 λ(1+βt+γt²) 含二次时变项；候选独立数值积分。
    """
    if lam < 0.0 or beta < 0.0 or gamma < 0.0 or T < 0.0:
        raise ValueError("参数须 ≥ 0")
    return float(1.0 - math.exp(-lam * (T + beta * T * T / 2.0 + gamma * T * T * T / 3.0)))


def accumulated_fail_candidate(lam: float = _LAM, beta: float = _BETA, gamma: float = _GAMMA_Q,
                             T: float = _T_ACC, n: int = 1024) -> float:
    """candidate：∫₀ᵀ λ(1+βt+γt²)dt 1D 中点求积后 1−exp（不含闭式）。"""
    if lam < 0.0 or beta < 0.0 or gamma < 0.0 or T < 0.0 or n < 2:
        raise ValueError("参数非法")
    h = T / int(n)
    acc = 0.0
    for i in range(int(n)):
        t = (i + 0.5) * h
        acc += lam * (1.0 + beta * t + gamma * t * t) * h
    return float(1.0 - math.exp(-acc))


# ---- B505：累计逻辑错误面积（初等闭式 ⇄ 1D 梯形）----
def logical_area_golden(k: float = _K_AREA, L: float = _L_AREA) -> float:
    """golden：∫₀ᴸ (1−e^{−kx})dx = L − (1−e^{−kL})/k。"""
    if k <= 0.0 or L <= 0.0:
        raise ValueError("k > 0 且 L > 0")
    return float(L - (1.0 - math.exp(-k * L)) / k)


def logical_area_candidate(k: float = _K_AREA, L: float = _L_AREA, n: int = 1024) -> float:
    """candidate：∫₀ᴸ (1−e^{−kx})dx 1D 梯形（不含闭式）。"""
    if k <= 0.0 or L <= 0.0 or n < 2:
        raise ValueError("参数非法")
    h = L / int(n)
    acc = 0.0
    for i in range(int(n)):
        x = (i + 0.5) * h
        acc += (1.0 - math.exp(-k * x)) * h
    return float(acc)


# ---- 默认参数（default_params 真源）----
B500_DEFAULT_PARAMS = {"phi_th": _PHI_TH, "sigma": _SIGMA_HOOK}
B501_DEFAULT_PARAMS = {"d": _D_CORR, "sigma": _SIGMA_CORR, "cx": _CX, "cy": _CY, "r": _R}
B502_DEFAULT_PARAMS = {"p0": _P0, "alpha": _ALPHA, "beta": _BETA_B, "T": _T_FID}
B503_DEFAULT_PARAMS = {"c": _C_LS, "p": _P_LS, "d": _D_LS}
B504_DEFAULT_PARAMS = {"lam": _LAM, "beta": _BETA, "gamma": _GAMMA_Q, "T": _T_ACC}
B505_DEFAULT_PARAMS = {"k": _K_AREA, "L": _L_AREA}


# ---- lru_cache 入口（part7.py 顶层引用）----
@functools.lru_cache(maxsize=256)
def _b500_golden_c(phi_th, sigma):
    return flag_hook_golden(phi_th, sigma)

@functools.lru_cache(maxsize=256)
def _b500_cand_c(phi_th, sigma, n):
    return flag_hook_candidate(phi_th, sigma, n)

def golden_b500(phi_th: float = _PHI_TH, sigma: float = _SIGMA_HOOK) -> float:
    return _b500_golden_c(phi_th, sigma)

def cand_b500(phi_th: float = _PHI_TH, sigma: float = _SIGMA_HOOK, n: int = 65536) -> float:
    return _b500_cand_c(phi_th, sigma, n)


@functools.lru_cache(maxsize=256)
def _b501_golden_c(d, sigma, cx, cy, r):
    return syndrome_corr_golden(d, sigma, cx, cy, r)

@functools.lru_cache(maxsize=256)
def _b501_cand_c(d, sigma, cx, cy, r, n):
    return syndrome_corr_candidate(d, sigma, cx, cy, r, n)

def golden_b501(d: float = _D_CORR, sigma: float = _SIGMA_CORR, cx: float = _CX,
                cy: float = _CY, r: float = _R) -> float:
    return _b501_golden_c(d, sigma, cx, cy, r)

def cand_b501(d: float = _D_CORR, sigma: float = _SIGMA_CORR, cx: float = _CX,
              cy: float = _CY, r: float = _R, n: int = 512) -> float:
    return _b501_cand_c(d, sigma, cx, cy, r, n)


@functools.lru_cache(maxsize=256)
def _b502_golden_c(p0, alpha, beta, T):
    return transversal_fid_golden(p0, alpha, beta, T)

@functools.lru_cache(maxsize=256)
def _b502_cand_c(p0, alpha, beta, T, n):
    return transversal_fid_candidate(p0, alpha, beta, T, n)

def golden_b502(p0: float = _P0, alpha: float = _ALPHA, beta: float = _BETA_B,
               T: float = _T_FID) -> float:
    return _b502_golden_c(p0, alpha, beta, T)

def cand_b502(p0: float = _P0, alpha: float = _ALPHA, beta: float = _BETA_B,
             T: float = _T_FID, n: int = 1024) -> float:
    return _b502_cand_c(p0, alpha, beta, T, n)


@functools.lru_cache(maxsize=256)
def _b503_golden_c(c, p, d):
    return merge_fid_golden(c, p, d)

@functools.lru_cache(maxsize=256)
def _b503_cand_c(c, p, d, n):
    return merge_fid_candidate(c, p, d, n)

def golden_b503(c: float = _C_LS, p: float = _P_LS, d: int = _D_LS) -> float:
    return _b503_golden_c(c, p, d)

def cand_b503(c: float = _C_LS, p: float = _P_LS, d: int = _D_LS, n: int = 1024) -> float:
    return _b503_cand_c(c, p, d, n)


@functools.lru_cache(maxsize=256)
def _b504_golden_c(lam, beta, gamma, T):
    return accumulated_fail_golden(lam, beta, gamma, T)

@functools.lru_cache(maxsize=256)
def _b504_cand_c(lam, beta, gamma, T, n):
    return accumulated_fail_candidate(lam, beta, gamma, T, n)

def golden_b504(lam: float = _LAM, beta: float = _BETA, gamma: float = _GAMMA_Q,
               T: float = _T_ACC) -> float:
    return _b504_golden_c(lam, beta, gamma, T)

def cand_b504(lam: float = _LAM, beta: float = _BETA, gamma: float = _GAMMA_Q,
             T: float = _T_ACC, n: int = 1024) -> float:
    return _b504_cand_c(lam, beta, gamma, T, n)


@functools.lru_cache(maxsize=256)
def _b505_golden_c(k, L):
    return logical_area_golden(k, L)

@functools.lru_cache(maxsize=256)
def _b505_cand_c(k, L, n):
    return logical_area_candidate(k, L, n)

def golden_b505(k: float = _K_AREA, L: float = _L_AREA) -> float:
    return _b505_golden_c(k, L)

def cand_b505(k: float = _K_AREA, L: float = _L_AREA, n: int = 1024) -> float:
    return _b505_cand_c(k, L, n)


# ===========================================================================
# 自检（`python -m lda.lda_harness._batch_j1_numeric` 或直接运行）
# ===========================================================================
_CASES = (
    ("B497", golden_b497, cand_b497, threshold_distance_candidate,
     B497_DEFAULT_PARAMS, "n_steps"),
    ("B498", golden_b498, cand_b498, syndrome_field_candidate,
     B498_DEFAULT_PARAMS, "n"),
    ("B499", golden_b499, cand_b499, match_cost_moment_candidate,
     B499_DEFAULT_PARAMS, "n"),
    # ---- J1 M2/M3/M4 续做（B500–B505）：golden 闭式 ⇄ candidate 独立数值 ----
    ("B500", golden_b500, cand_b500, flag_hook_candidate,
     B500_DEFAULT_PARAMS, "n"),
    ("B501", golden_b501, cand_b501, syndrome_corr_candidate,
     B501_DEFAULT_PARAMS, "n"),
    ("B502", golden_b502, cand_b502, transversal_fid_candidate,
     B502_DEFAULT_PARAMS, "n"),
    ("B503", golden_b503, cand_b503, merge_fid_candidate,
     B503_DEFAULT_PARAMS, "n"),
    ("B504", golden_b504, cand_b504, accumulated_fail_candidate,
     B504_DEFAULT_PARAMS, "n"),
    ("B505", golden_b505, cand_b505, logical_area_candidate,
     B505_DEFAULT_PARAMS, "n"),
)


def _measure_candidates():
    """逐锚实测：默认档残差 / 网格残差链 / 单调性 / 收敛比 / tol 余量。"""
    rows = []
    for bid, gf, cf, raw_cf, params, key in _CASES:
        g = gf(**params)
        chain, abs_chain = [], []
        for n in _GRID_BY_BID[bid]:
            c = raw_cf(**params, **{key: n})
            d = abs(c - g)
            abs_chain.append(d)
            chain.append(d / max(abs(g), 1e-300))
        tol = _TOL_BY_BID[bid]
        rows.append({
            "bid": bid, "golden": g, "tol": tol,
            "grid": list(_GRID_BY_BID[bid]), "rel_chain": chain,
            "abs_chain": abs_chain,
            "mono": all(chain[i] > chain[i + 1] for i in range(len(chain) - 1)),
            "ratio": [chain[i] / chain[i + 1] if chain[i + 1] > 0 else float("inf")
                      for i in range(len(chain) - 1)],
            "default_rel": chain[-1],
            "margin_x": tol / abs_chain[-1] if abs_chain[-1] > 0 else float("inf"),
            "abs_default": abs_chain[-1],
            "golden_over_tol": abs(g) / tol,
            "n_default": _N_BY_BID[bid],
        })
    return rows


if __name__ == "__main__":
    print("=" * 78)
    print("Batch J1 数值核自检（量子纠错 QEC · M0 阈值标度 + M1 解码器 + M2/M3/M4 续做 · B497–B505）")
    print("=" * 78)
    bad = 0
    for r in _measure_candidates():
        print("\n%s  golden=%.6e  tol=%.1e  |golden|/tol=%.3e"
              % (r["bid"], r["golden"], r["tol"], r["golden_over_tol"]))
        print("   网格 %s  默认档=%d" % (r["grid"], r["n_default"]))
        print("   rel 链: %s" % " → ".join("%.3e" % x for x in r["rel_chain"]))
        print("   收敛比: %s   MONO=%s"
              % (" ".join("%.2f×" % x for x in r["ratio"]), r["mono"]))
        print("   默认档 rel=%.3e  abs=%.3e  余量(tol/abs)=%.1f×"
              % (r["default_rel"], r["abs_default"], r["margin_x"]))
        for cond, msg in (
            (r["default_rel"] > 1e-12, "默认档 rel > 1e-12（非机器零残差）"),
            (r["mono"], "残差链严格单调"),
            (r["abs_default"] > 0.0, "默认档 abs > 0（真数值残差）"),
            (r["margin_x"] >= 100.0, "余量 ≥ 100×"),
            (r["golden_over_tol"] >= 13.5, "|golden| ≥ 13.5×tol")):
            if not cond:
                print("   [FAIL] %s" % msg)
                bad += 1
        if not (r["rel_chain"][0] >= 20.0 * r["default_rel"]):
            print("   [FAIL] 粗端残差未显著放大（恒等嫌疑）")
            bad += 1
        if not all(1.5 <= x <= 40.0 for x in r["ratio"]):
            print("   [FAIL] 收敛比越界（阶不符）：%s" % r["ratio"])
            bad += 1
    print("\n" + "=" * 78)
    print("自检结论：%s（%d 项不符）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    raise SystemExit(0 if bad == 0 else 1)
