"""Batch B-42 数值实现 · 量子传感器芯片征程 QS-M3（灵敏度几何优化）。

════════════════════════════════════════════════════════════════════════════
本批**两锚**（`benchmark_defs/part7.py` 引用）——
  B476：**最优色心深度 d\\*** 闭式 ⇄ 网格扫描+抛物插值 互验
        golden   = 解闭式根方程 **d⁴ + d₀³·d = 3·d₀³·d_att**（由 d(ln η_tot)/dd=0
                   解析导出；二分法求唯一正根，f'=4d³+d₀³>0 严格单调）。
        candidate = **全网格扫描 + 三点抛物插值定极小**（不用任何导数/根方程）。
        ——方法学独立：golden 走「解析求导 → 根方程 → 二分求根」；
        candidate 走「离散网格 + 抛物精修」。实测 rel≈1e-8（网格+抛物三阶项）。

  B477：**NA 立体角收集效率 η_NA** 闭式 ⇄ 数值角分布采样 互验
        golden   = 闭式 η_NA(NA) = [cos³θ/3 − cosθ]₀^{θmax} / (2/3)（θmax=arcsin NA）。
        candidate = **数值角分布采样**：对偶极图样 w(θ)=sin³θ·dθ 逐点求和，
                    取 θ≤θmax 的权重占比（不用任何闭式积分）。
        ——方法学独立：golden 走「解析积分」；candidate 走「数值求和」。
        实测 rel≈1e-6…1e-5（网格离散化；NA 越小残差越大但仍 ≪ tol=1e-3）。

🔴 物理意义（承 QS-M3 蓝图 · 平台缺口 G5「量子传感专用 PDK 器件」）：
  · 色心深度是 NV 量子传感的**核心几何设计旋钮**：越深越难收集（出射衰减），
    但太浅受表面自旋浴噪声（谱扩散 ∝1/d³）劣化 ⇒ **存在最优深度**。
  · NA 收集效率决定每单位时间光子数 ⇒ 直接影响散粒极限灵敏度（QS-M1 FOM）。
  两锚把几何设计链钉进账本 ⇒ 任何对「深度-收集权衡」或「NA 立体角」的误改
  都会被机器判红。

🔴 与既有锚的边界（**不同物理量**，非重复计数）：
  · B18（Purcell 因子 F_P=4g²/(κγ₁)）：QS-M3 链④ 复用同一 Purcell 物理
    ⇒ **不另登记 B 锚**（避免重复），归 `run_qs_m3_smoke` 覆盖。
  · B473（NV 磁力计磁灵敏度 η）：QS-M0 的**灵敏度标量**；本批是**几何量**
    （最优深度 / NA 收集效率），物理对象不同。
  · B459–B472（光子传感器灵敏度族）：**折射率传感**，与本批自旋系综不同域。

🔴 **为何只两锚（诚实规模 · 吃狗粮）**：QS-M3 另含
  · 「Purcell 计数率比闭式 ⇄ 数值峰值提取」（与 B18 同物理量 ⇒ 属 smoke）；
  · 「bulk 极限对照比 ∈(0,1]」（不等式约束 ⇒ 属 smoke）；
  · 「收集效率随深度单调降」（单调性 ⇒ 属 smoke）；
  三者归 `run_qs_m3_smoke` 覆盖，**不登记为 B 锚**（避免「非独立标量物理量充数」）。
本批如实只登记 B476/B477 两锚（同 Batch B-38 的三锚、B-39~B-41 单锚纪律：
**宁可少，不越级谎报**）。

🔴 纪律：
· 本模块**顶层只 import numpy/math**（不触发 scipy）。
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」，已实测残差
  B476≈1e-8 / B477≈1e-6 远高于机器精度 1e-16）；进报告数字一律**现算**。
· 🔴 **锚携带可扰动参数**（`B476_DEFAULT_PARAMS` / `B477_DEFAULT_PARAMS`）：
  参数对输出单调、非零响应 ⇒ 反自证桩护栏 `candidate_responds` 可证伪。
"""
from __future__ import annotations

import functools
import math

import numpy as np


# ===========================================================================
# B476 · 最优色心深度 d*：闭式根方程 ⇄ 网格扫描+抛物插值
# ===========================================================================
def _fom_model(depth_nm: float, d0_nm: float, d_att_nm: float) -> float:
    """几何灵敏度 FOM（∝ η_tot，越小越好，未归一）：

    η_tot(d) = √(1 + (d₀/d)³) / √(exp(−d/d_att))
      · 分子 √(1+(d₀/d)³)：表面自旋浴噪声（谱扩散 ∝1/d³）劣化对比度；
      · 分母 √η_coll：收集效率（出射衰减 exp(−d/d_att)）越低 ⇒ 光子越少 ⇒ 越差。
    """
    if depth_nm <= 0.0:
        raise ValueError("depth_nm 必须 > 0")
    eta_coll = math.exp(-depth_nm / d_att_nm)
    return math.sqrt(1.0 + (d0_nm / depth_nm) ** 3) / math.sqrt(eta_coll)


def optimal_depth_golden(d0_nm: float = 20.0, d_att_nm: float = 200.0) -> float:
    """golden：闭式最优深度 —— 解 **d⁴ + d₀³·d = 3·d₀³·d_att**。

    推导：ln η_tot = ½ln(1+(d₀/d)³) + d/(2d_att)。
      d/dd = ½·[−3d₀³/d⁴/(1+(d₀/d)³)] + 1/(2d_att) = 0
      ⇒ 3 d₀³ d_att / (d⁴ + d₀³ d) = 1 ⇒ d⁴ + d₀³ d = 3 d₀³ d_att。
    🔴 f(d)=d⁴+d₀³d−3d₀³d_att 严格单调增（f'=4d³+d₀³>0）⇒ 唯一正根，二分必收敛。
    """
    if d0_nm <= 0.0 or d_att_nm <= 0.0:
        raise ValueError("d0_nm / d_att_nm 必须 > 0")
    rhs = 3.0 * d0_nm ** 3 * d_att_nm
    lo, hi = 1e-9, 1e3 * d_att_nm
    for _ in range(400):
        mid = 0.5 * (lo + hi)
        if mid ** 4 + d0_nm ** 3 * mid < rhs:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def optimal_depth_candidate(d0_nm: float = 20.0, d_att_nm: float = 200.0,
                            n_grid: int = 200000) -> float:
    """candidate：**全网格扫描 + 三点抛物插值定极小**（方法学独立 · 不用导数）。

    ① 在 [1e-3·d_att, 10·d_att] 上均匀取 n_grid 点，逐点算 η_tot；
    ② argmin 定位极小格点 i；
    ③ 用 (i−1, i, i+1) 三点做**抛物插值**精修极小位置（非导数、非根方程）。
    残差 = 网格离散化 + 抛物近似的三阶项 ⇒ ≈1e-8。
    """
    if d0_nm <= 0.0 or d_att_nm <= 0.0:
        raise ValueError("d0_nm / d_att_nm 必须 > 0")
    ds = np.linspace(1e-3 * d_att_nm, 10.0 * d_att_nm, n_grid)
    ys = np.array([_fom_model(float(x), d0_nm, d_att_nm) for x in ds])
    i = int(np.argmin(ys))
    if 0 < i < n_grid - 1:
        y0, y1, y2 = ys[i - 1], ys[i], ys[i + 1]
        denom = y0 - 2.0 * y1 + y2
        if abs(denom) > 1e-300:
            step = ds[i + 1] - ds[i]
            return float(ds[i] - 0.5 * step * (y2 - y0) / denom)
    return float(ds[i])


# ===========================================================================
# B477 · NA 立体角收集效率 η_NA：闭式解析积分 ⇄ 数值角分布采样
# ===========================================================================
def na_efficiency_golden(na: float) -> float:
    """golden：闭式 η_NA(NA) = [cos³θ/3 − cosθ]₀^{θmax} / (2/3)，θmax=arcsin(NA)。

    🔴 NA=1 ⇒ θmax=π/2 ⇒ η_NA=1（全半球）；NA→0 ⇒ η_NA→0。
    """
    if not (0.0 < na <= 1.0):
        raise ValueError("NA 必须 ∈ (0, 1]")
    tm = math.asin(na)

    def F(x: float) -> float:
        c = math.cos(x)
        return c ** 3 / 3.0 - c

    return (F(tm) - F(0.0)) / (2.0 / 3.0)


def na_efficiency_candidate(na: float, n_theta: int = 400000) -> float:
    """candidate：数值角分布采样（方法学独立 · 不用任何闭式积分）。

    偶极图样 w(θ) = sin³θ·dθ（强度 sin²θ × 立体角 sinθ）；全半球归一；
    取 θ≤θmax 的权重占比。残差 = 网格离散化 ⇒ ≈1e-6…1e-5。
    """
    if not (0.0 < na <= 1.0):
        raise ValueError("NA 必须 ∈ (0, 1]")
    th = (np.arange(n_theta) + 0.5) * (math.pi / 2.0) / n_theta
    dth = (math.pi / 2.0) / n_theta
    w = np.sin(th) ** 3 * dth
    tot = float(np.sum(w))
    m = th <= math.asin(na)
    return float(np.sum(w[m]) / tot)


# ===========================================================================
# 锚的物理设计参数（default_params 真源 · 单一出处）
# ===========================================================================
# 🔴 为什么必须带**数值参数**（v0.9.216 吃狗粮抓到 · 反自证桩护栏盲区）：
#   反自证桩护栏的行为判据 `candidate_responds` 需**扰动数值参数**方可证伪。
#   · B476：d0_nm（表面噪声长度）对 d* 单调、非零响应 ⇒ ±10% 扰动可证伪；
#   · B477：na 对 η_NA 单调、非零响应（NA<1 时）⇒ ±10% 扰动可证伪。
B476_DEFAULT_PARAMS = {
    "d0_nm": 20.0,         # 表面自旋浴噪声特征长度（nm）；非零 ⇒ d* 响应
    "d_att_nm": 200.0,     # 出射衰减长度（nm）
}

B477_DEFAULT_PARAMS = {
    "na": 0.75,            # 数值孔径；<1 ⇒ η_NA 响应非零
}


# ===========================================================================
# 记忆化入口（part7.py 顶层引用；纯函数 ⇒ 数值逐位不变）
# ===========================================================================
@functools.lru_cache(maxsize=256)
def _b476_golden_c(d0_nm: float, d_att_nm: float) -> float:
    return optimal_depth_golden(d0_nm, d_att_nm)


@functools.lru_cache(maxsize=256)
def _b476_cand_c(d0_nm: float, d_att_nm: float) -> float:
    return optimal_depth_candidate(d0_nm, d_att_nm)


def golden_b476(d0_nm: float = 20.0, d_att_nm: float = 200.0) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b476_golden_c(d0_nm, d_att_nm)


def cand_b476(d0_nm: float = 20.0, d_att_nm: float = 200.0) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b476_cand_c(d0_nm, d_att_nm)


@functools.lru_cache(maxsize=256)
def _b477_golden_c(na: float) -> float:
    return na_efficiency_golden(na)


@functools.lru_cache(maxsize=256)
def _b477_cand_c(na: float) -> float:
    return na_efficiency_candidate(na)


def golden_b477(na: float = 0.75) -> float:
    """part7.py 顶层引用的 golden 入口（**接受 default_params 关键字**）。"""
    return _b477_golden_c(na)


def cand_b477(na: float = 0.75) -> float:
    """candidate 入口（_adapter_p4 用）——接受 default_params 关键字。"""
    return _b477_cand_c(na)
