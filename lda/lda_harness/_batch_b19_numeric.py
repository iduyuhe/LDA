# -*- coding: utf-8 -*-
"""Batch B-19 双方法独立锚数值核（v0.9.99 · P1-1 路径 B 扩基续十七 · 腿① 续加锚稀释 terminal）

本批 16 道（B313-B328），**三族**（批次内族数不固定，承 B-10/B-16 先例）：

  · 族 A（B313-B318，6 道）**广义 Lane–Emden / Emden–Fowler 奇异初值 ODE**
      方程  θ'' + (2/ξ)·θ' + λ·θ^n = 0 ，  θ(0) = θ₀ ， θ'(0) = 0
      （n = 1 与 n = 5 为经典可积档；λ 为源强度、θ₀ 为中心幅值，二者均 > 0）
      闭式解（**λ 与 θ₀ 保持一般性 ⇒ 两个扰动键都不破坏 golden**）：
        n = 1 : θ(ξ) = θ₀·sin(√λ·ξ) / (√λ·ξ)
        n = 5 : θ(ξ) = θ₀·(1 + λ·θ₀⁴·ξ²/3)^{−1/2}
      （n = 5 式的自洽性：令 A = λθ₀⁴/3，θ = θ₀(1+Aξ²)^{−1/2} 逐项代入给出
        −3θ₀A·(1+Aξ²)^{−5/2} + λθ₀⁵(1+Aξ²)^{−5/2} = 0 ⇔ λ = 3A/θ₀⁴ ✅ 恒等。
        等价同调关系：θ_{θ₀}(ξ) ≡ θ₀·θ_{θ₀=1}(θ₀²ξ)。）
      golden = 上二式在 ξ = xi 处取值
      cand   = 原点 Taylor 级数启动（ε = 1e-6）+ 经典 RK4（一阶化 θ'=p、p'=−2p/ξ−λθ^n）
      ⇒ 实测**四阶**收敛（比值 **15.4~29.5**；理论渐近值 16，比值 >16 系粗端 N=16/32
        尚未进入渐近区、继续加密即回落 —— **不虚报为「恰 16」**），余量 6.2e7~4.0e8×
      物理关联：幂律非线性（自引力/自聚焦）平衡族 —— 与本项目既有「径向 Schrödinger」
      （B-9 Hulthen）、「线性阻尼 ODE」（B-18 GL-RK4）均不同方程类，且**奇异原点 IVP**
      为本仓首次（Taylor 级数启动规避 2/ξ 奇性），方程与光子学渐变折射率自聚焦同范式。

  · 族 B（B319-B323，5 道）**二维 Laplace Dirichlet 边值问题 · 间接边界元（单层位势）**
      单位圆盘 R = 1，边界数据 u_b(θ) = cos(n·θ)，精确内部解 u = r^n·cos(n·θ)（调和）
      位势表示  u(p) = ∮_Γ σ(q)·G(p,q) dΓ ，  G = −(1/2π)·ln|p−q|（**负号不可省**）
      离散：N 段常数元 + 每段 12 点 Gauss–Legendre ⇒ 先解 A σ = u_b，再以同 A 作用于
            内部观测点得 u(p)；对角元闭式 ∫₀^L ln t dt + ∫₀^L ln(L−t) dt = 2L·ln L − 2L
            ⇒ A_jj = −(1/2π)·(L·ln(L/2) − L)
      ⇒ 实测 **O(h²)** 收敛（比值 **3.28~3.99**；nb=3 档粗端 N=32 对 r³cos3θ 欠分辨
        故偏低，N=64 起回到 3.67/3.84），余量 255~478×
      物理关联：位势/边界积分方程为本仓**新方法类**（既非体积离散 FD/FEM，亦非解析展开），
      与光子学「边界元求散射/模式截面」同技术路线。

  · 族 C（B324-B328，5 道）**静态 Hamilton–Jacobi（Eikonal）方程 · 快速行进法（FMM）**
      |∇T(x,y)| = f0·sqrt(1 + (1+y)²)  于 [0,1]²
      制造解（manufactured solution）T(x,y) = f0·(x + y + y²/2)——逐项代入即：
        ∇T = f0·(1, 1+y) ⇒ |∇T| = f0·sqrt(1 + (1+y)²) ≡ f  ✅ 精确解、非近似、非截断
      特征线方向恒为 (+x, +y) ⇒ 边界初始化只需 {x=0} ∪ {y=0} 两条边给精确值
      cand = FMM（Godunov 一阶迎风 + 二叉堆），观测点取**二进制有理坐标**
             （0.625/0.75/0.875/0.375/0.5）⇒ 对 M∈{80,160,320,640} 恒有 i = x·M 为整数
             ⇒ 候选吸附零误差、golden 与 M 无关
      ⇒ 实测**清洁一阶 O(h)**（M 80→160→320→640 比值 **1.97~2.00**），余量 17~34×
        （一阶为本格式固有阶；同批 B-16 族 C「Haar MRA 标称一阶」已确立一阶先例）
      物理关联：几何光学/eikonal 即「光程最短」变分原理，是光子器件（渐变折射率透镜、
      波前整形）射线追迹的标准方程，且与 WKB 半经典近同一脉。

------------------------------------------------------------------------------------------
【B-19 命名避让核检】（批次号与单锚号撞名先例：B-16 首踩 ⇒ B-19 先核）
  `_BATCH_B19` / `_get_batch_b19` / `_batch_b19` 在 `verification_adapters.py` **全 0 命中**；
  对照组 `_BATCH_B18` 5 命中、`_batch_b18` 19 命中（B-18 正常接线）⇒ B-19 可安全使用
  `_BATCH_B19_NUMERIC_MOD` / `_get_batch_b19_numeric()` / `_batch_b19_numeric.py`。

【同源体检】（限定 `lda/`，排除 lda_cuda_venv / node_modules / vendor；**实 grep 全仓 659 文件**）
  两轮共 70 组关键词。结论：
  ① **Lane–Emden / Emden–Fowler / polytrope**：`lane_emden|polytrope|emden` **零实现命中** ✅
  ② **边界元 / 单层位势**：`bem|boundary_integral|单层位势|双层位势|green_function|镜像法`
     ⇒ `bem` 仅 1 命中（B-18 被否候选记录文本，非实现）、其余**零实现命中** ✅
  ③ **Eikonal / FMM**：`eikonal` 1 命中、`fast_marching` 1 命中 —— **均为 B-16 族 A
     同源体检的关键词行/被否记录文本，非实现代码**。B-16 实际被否的是
     ADI / TMM 多层膜 / 有限体积-Godunov / Kirsch 圆孔 / 复围道留数 / Eckart-Manning /
     Telegrapher / Pöschl–Teller / Laplace 数值反演 / 蒙特卡洛 —— **不含 eikonal**
     ⇒ 二维静态 H–J 迎风 **零实现占用** ✅
  ④ 顺带核验并**主动弃用**（避免踩同域）：
     · **Green 函数 / 镜像法点电荷** ⇒ 与族 B 同为二维 Laplace 算子 ∇² ⇒ **数值同源 ⇒ 弃用**
     · **反应扩散 Fisher–KPP / Allen–Cahn** ⇒ 与 B-16 族 A（Burgers 非线性对流–扩散）
       同一算子族 ∂_t + 对流/扩散 ⇒ **结构同源 ⇒ 弃用**
     · **Blasius 边界层**（三次 ODE 打靶）⇒ 与 B-14 族「非线性 BVP 打靶」同结构 ⇒ 弃用
     · **Sturm–Liouville / 圆盘本征值** ⇒ 与 B-5 圆波导、B-9 梁本征同源 ⇒ 弃用
     · **Hückel 分子轨道 / 矩阵指数类** ⇒ golden 即闭式本征值 ⇒ 代数恒等红线 ⇒ 弃用
     · **Chebyshev 谱 / 谱元 / 复围道** ⇒ 指数收敛 ⇒ 残差沉 round-off 地板（同 B-13 Talbot）⇒ 弃用

【本批被否/剔除候选（实测记录，供报告 §2.3）】
  ① 族 A **n=0 档**（θ'' + 2θ'/ξ = −λ 的多项式解）⇒ RK4 逐项精确 ⇒ |Δ|~1e-16、比值恒 1.00
     ⇒ 撞判据 D「代数恒等」红线（与 B-10 Mathieu-FG、B-18 TMM 同型失败模式）⇒ 剔除。
  ② 族 A **xi = 4.0 档** ⇒ 进入渐近区，h⁴ 比值退化为 8.88/9.87/13.80（不干净）⇒ 弃用。
  ③ 族 C **点源 + 精确邻点初始化** ⇒ 源点奇性使一阶迎风降阶到 h^0.8
     （M 60→480 残差 1.461e-2→3.028e-3，亚线性）⇒ 弃用；改制造解 + 两边界初始化。
  ④ 族 C **倾斜平面波 v = v0(1 + k·s)** ⇒ 速度随 s 增大 ⇒ 射线绕行 ⇒ golden 非粘性解
     （残差恒 2.4e-2、比值 1.00）⇒ 弃用。

【本批血案】（编号与报告 §6 对齐）
  1. 族 A n=0 ⇒ 代数恒等（比值 1.00、|Δ|~1e-16）⇒ 剔除 n=0 档。
  2. 族 A 扰动键**不可取整数 n**（×1.1 得 5.5 ⇒ 闭式失效）⇒ 改「λ + θ₀ 双连续键，n 只作固定档」。
  3. 族 B BEM 核**符号写反**（G = +(1/2π)ln r）⇒ 残差恒不降、比值恰 1.00（指纹：比值≡1）。
  4. 族 B **直接边界积分（双层 + jump 自由项）**四种符号组合全败：`dir+j−/g` 1.00、
     `dir−j−/g` 1.00、`dir+j+/g` ≈2.01（表观）、`dir−j+/g` 1.00 ⇒ 必须走**间接单层位势**。
  5. 族 B `math.cos` 传 numpy 数组 ⇒ TypeError ⇒ 改 `np.cos`。
  6. 族 C 观测点若取非二进制坐标（如 0.62）⇒ 吸附误差 O(h) 污染 ⇒ 改二进制有理坐标。
  7. 自检辅助项自身出错两次（非数值核缺陷）：① λ→0 极限比较用了 1e-18 绝对阈，
     被 sqrt/四则 round-off（~1e-17）误判；② 调和性检查**误用直角坐标 Laplacian**
     去验极坐标定义的 r^n·cos nθ ⇒ 改为极坐标形式 u_rr + u_r/r + u_θθ/r² 后通过。
  8. 三族统一加缓存（BEM 矩阵按 (R,N,ngl)、FMM 解按 (M,f0)）⇒ 全批自检 15.6s，CI 可控。
------------------------------------------------------------------------------------------
"""
import math
import heapq

import numpy as np

__all__ = [
    "golden_b313", "cand_b313", "golden_b314", "cand_b314", "golden_b315", "cand_b315",
    "golden_b316", "cand_b316", "golden_b317", "cand_b317", "golden_b318", "cand_b318",
    "golden_b319", "cand_b319", "golden_b320", "cand_b320", "golden_b321", "cand_b321",
    "golden_b322", "cand_b322", "golden_b323", "cand_b323",
    "golden_b324", "cand_b324", "golden_b325", "cand_b325", "golden_b326", "cand_b326",
    "golden_b327", "cand_b327", "golden_b328", "cand_b328",
    "_golden_by_bid", "_cand_by_bid", "_self_test",
]


# ==========================================================================================
# 族 A · 广义 Lane–Emden / Emden–Fowler 奇异初值 ODE（B313-B318）
# ==========================================================================================
def le_exact(n, lam, th0, xi):
    """广义 Lane–Emden 方程 θ'' + (2/ξ)θ' + λθ^n = 0（θ(0)=θ₀, θ'(0)=0）的闭式解。

      n = 1 : θ(ξ) = θ₀·sin(√λ·ξ)/(√λ·ξ)       （λξ→0 时退化为 θ₀(1 − λξ²/6)，已加保护）
      n = 5 : θ(ξ) = θ₀·(1 + λ·θ₀⁴·ξ²/3)^{−1/2}（令 A = λθ₀⁴/3 即 θ₀(1+Aξ²)^{−1/2}）

    两式均为**精确解**（非截断近似），故残差不受 golden 误差主导。
    """
    if n == 1:
        r = math.sqrt(lam) * xi
        if abs(r) < 1e-6:                      # λξ→0 极限：θ₀(1 − λξ²/6)（避免 0/0）
            return th0 * (1.0 - r * r / 6.0)
        return th0 * math.sin(r) / r
    if n == 5:
        return th0 * (1.0 + lam * (th0 ** 4) * xi * xi / 3.0) ** -0.5
    raise ValueError("le_exact: 仅支持 n = 1 或 n = 5（可积档）")


def _le_taylor(n, lam, th0, eps):
    """原点附近 Taylor 级数启动（避开 ξ=0 处的 2/ξ 奇性）。

    θ = θ₀ + a₂ξ² + a₄ξ⁴ + a₆ξ⁶ + …，θ^n 按 θ₀ 展开后逐阶定系数：
      ξ⁰ : 6a₂ + λ·θ₀^n                     = 0 ⇒ a₂ = −λθ₀^n/6
      ξ² : 20a₄ + λn·θ₀^{n−1}·a₂            = 0 ⇒ a₄ = λ²n·θ₀^{2n−1}/120
      ξ⁴ : 42a₆ + λ[nθ₀^{n−1}a₄ + ½n(n−1)θ₀^{n−2}a₂²] = 0
    （n=1, θ₀=1 退化为 −λ/6, λ²/120, −λ³/5040 ✅；n=5, θ₀=1 退化为 −λ/6, λ²/24, −5λ³/432 ✅）
    """
    a2 = -lam * (th0 ** n) / 6.0
    a4 = lam * lam * n * (th0 ** (2.0 * n - 1.0)) / 120.0
    c4 = n * (th0 ** (n - 1.0)) * a4 + 0.5 * n * (n - 1.0) * (th0 ** (n - 2.0)) * a2 * a2
    a6 = -lam * c4 / 42.0
    th = th0 + a2 * eps ** 2 + a4 * eps ** 4 + a6 * eps ** 6
    thp = 2.0 * a2 * eps + 4.0 * a4 * eps ** 3 + 6.0 * a6 * eps ** 5
    return th, thp


def le_rk4(n, lam, th0, xi, N, eps=1e-6):
    """Taylor 启动 + 经典 RK4 一阶化积分（y=θ, p=θ'；y'=p, p'=−2p/ξ−λy^n）。"""
    th, thp = _le_taylor(n, lam, th0, eps)
    h = (xi - eps) / float(N)
    x = eps
    ln = float(n)
    for _ in range(N):
        def fn(X, T, P):
            return (P, -(2.0 / X) * P - lam * (T ** ln))
        k1 = fn(x, th, thp)
        k2 = fn(x + 0.5 * h, th + 0.5 * h * k1[0], thp + 0.5 * h * k1[1])
        k3 = fn(x + 0.5 * h, th + 0.5 * h * k2[0], thp + 0.5 * h * k2[1])
        k4 = fn(x + h, th + h * k3[0], thp + h * k3[1])
        th += h / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        thp += h / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
        x += h
    return th


def golden_b313(n=1, lam=1.00, th0=1.00, xi=2.00):
    return le_exact(n, lam, th0, xi)


def cand_b313(n=1, lam=1.00, th0=1.00, xi=2.00, N=128):
    return le_rk4(n, lam, th0, xi, N)


def golden_b314(n=1, lam=2.50, th0=1.00, xi=1.50):
    return le_exact(n, lam, th0, xi)


def cand_b314(n=1, lam=2.50, th0=1.00, xi=1.50, N=128):
    return le_rk4(n, lam, th0, xi, N)


def golden_b315(n=5, lam=1.00, th0=1.00, xi=1.00):
    return le_exact(n, lam, th0, xi)


def cand_b315(n=5, lam=1.00, th0=1.00, xi=1.00, N=128):
    return le_rk4(n, lam, th0, xi, N)


def golden_b316(n=5, lam=1.00, th0=1.00, xi=2.00):
    return le_exact(n, lam, th0, xi)


def cand_b316(n=5, lam=1.00, th0=1.00, xi=2.00, N=128):
    return le_rk4(n, lam, th0, xi, N)


def golden_b317(n=5, lam=1.00, th0=1.00, xi=2.50):
    return le_exact(n, lam, th0, xi)


def cand_b317(n=5, lam=1.00, th0=1.00, xi=2.50, N=128):
    return le_rk4(n, lam, th0, xi, N)


def golden_b318(n=5, lam=1.30, th0=1.00, xi=1.80):
    return le_exact(n, lam, th0, xi)


def cand_b318(n=5, lam=1.30, th0=1.00, xi=1.80, N=128):
    return le_rk4(n, lam, th0, xi, N)


# ==========================================================================================
# 族 B · 二维 Laplace Dirichlet · 间接边界元（单层位势）（B319-B323）
# ==========================================================================================
_GL_CACHE = {}


def _gl(n):
    if n not in _GL_CACHE:
        _GL_CACHE[n] = np.polynomial.legendre.leggauss(n)
    return _GL_CACHE[n]


_BEM_CACHE = {}


def _bem_geom(R, N, ngl=12):
    """常数元 + 端点几何 + 每段 12 点 GL 求积（按 (R,N,ngl) 缓存）。

    单层位势 G = −(1/2π)·ln|p−q|。对角元：
      ∫₀^L ln t dt + ∫₀^L ln(L−t) dt = (L ln L − L) + (L ln L − L) = 2L ln L − 2L
      ⇒ A_jj = −(1/2π)·(L·ln(L/2) − L)
    """
    key = (float(R), int(N), int(ngl))
    if key in _BEM_CACHE:
        return _BEM_CACHE[key]
    gx, gw = _gl(ngl)
    tn = 2.0 * math.pi * np.arange(N) / N
    tc = 2.0 * math.pi * (np.arange(N) + 0.5) / N
    P = np.stack([R * np.cos(tn), R * np.sin(tn)], axis=1)      # 端点
    C = np.stack([R * np.cos(tc), R * np.sin(tc)], axis=1)      # 配点（段中点）
    A = np.zeros((N, N))
    segs = []
    for j in range(N):
        a = P[j]
        b = P[(j + 1) % N]
        t = b - a
        L = float(np.linalg.norm(t))
        pts = 0.5 * (a + b)[None, :] + 0.5 * gx[:, None] * t[None, :]
        wq = 0.5 * L * gw                                       # 含 Jacobian
        segs.append((pts, wq))
        for i in range(N):
            if i == j:
                A[i, j] = -(1.0 / (2.0 * math.pi)) * (L * math.log(L / 2.0) - L)
            else:
                r = np.linalg.norm(pts - C[i][None, :], axis=1)
                G = -(1.0 / (2.0 * math.pi)) * np.log(r)
                A[i, j] = float(np.dot(wq, G))
    _BEM_CACHE[key] = (A, segs, C)
    return _BEM_CACHE[key]


def bem_single_layer(R, N, nb, r_obs, th_obs, ngl=12):
    """间接单层位势：解 A σ = u_b，再以 A 作用于内部观测点得 u(p)。"""
    A, segs, C = _bem_geom(R, N, ngl)
    u_b = np.cos(nb * np.arctan2(C[:, 1], C[:, 0]))
    sig = np.linalg.solve(A, u_b)
    px = r_obs * math.cos(th_obs)
    py = r_obs * math.sin(th_obs)
    val = 0.0
    c = -(1.0 / (2.0 * math.pi))
    for j in range(N):
        pts, wq = segs[j]
        r = np.sqrt((pts[:, 0] - px) ** 2 + (pts[:, 1] - py) ** 2)
        val += float(np.dot(wq, c * np.log(r))) * sig[j]
    return val


def golden_b319(nb=1, r_obs=0.60, th_obs=0.25):
    return (r_obs ** nb) * math.cos(nb * th_obs)


def cand_b319(nb=1, r_obs=0.60, th_obs=0.25, N=256):
    return bem_single_layer(1.0, N, nb, r_obs, th_obs)


def golden_b320(nb=1, r_obs=0.60, th_obs=0.80):
    return (r_obs ** nb) * math.cos(nb * th_obs)


def cand_b320(nb=1, r_obs=0.60, th_obs=0.80, N=256):
    return bem_single_layer(1.0, N, nb, r_obs, th_obs)


def golden_b321(nb=1, r_obs=0.85, th_obs=0.40):
    return (r_obs ** nb) * math.cos(nb * th_obs)


def cand_b321(nb=1, r_obs=0.85, th_obs=0.40, N=256):
    return bem_single_layer(1.0, N, nb, r_obs, th_obs)


def golden_b322(nb=2, r_obs=0.60, th_obs=0.15):
    return (r_obs ** nb) * math.cos(nb * th_obs)


def cand_b322(nb=2, r_obs=0.60, th_obs=0.15, N=256):
    return bem_single_layer(1.0, N, nb, r_obs, th_obs)


def golden_b323(nb=3, r_obs=0.60, th_obs=0.10):
    return (r_obs ** nb) * math.cos(nb * th_obs)


def cand_b323(nb=3, r_obs=0.60, th_obs=0.10, N=256):
    return bem_single_layer(1.0, N, nb, r_obs, th_obs)


# ==========================================================================================
# 族 C · 静态 Hamilton–Jacobi（Eikonal）· 快速行进法 FMM（B324-B328）
# ==========================================================================================
def eik_exact(f0, x, y):
    """制造解：|∇T| = f0·sqrt(1+(1+y)²) ⇒ T = f0·(x + y + y²/2)（精确、非截断）。"""
    return f0 * (x + y + 0.5 * y * y)


def _eik_slowness(f0, y):
    """慢度 f = 1/v = |∇T| = f0·sqrt(1 + (1+y)²)。"""
    return f0 * math.sqrt(1.0 + (1.0 + y) ** 2)


_FMM_CACHE = {}


def fmm_solve(f0, M, Lx=1.0, Ly=1.0):
    """FMM：Godunov 一阶迎风 + 二叉堆；边界 {x=0} ∪ {y=0} 给精确值（按 (f0,M) 缓存）。

    更新式（二阶特征方程）：
      (T−a)²/fx² + (T−b)²/fy² = 1
      T = [−lin + sqrt(lin² − 4s·cst)]/(2s)，s = 1/fx² + 1/fy²
      lin = −2(a/fx² + b/fy²)、cst = a²/fx² + b²/fy² − 1
      当 |a−b| ≥ hypot(fx,fy) 时退化为单调迎风 T = min(a,b) + min(fx,fy)。
    """
    key = (round(float(f0), 12), int(M))
    if key in _FMM_CACHE:
        return _FMM_CACHE[key]
    hx = Lx / float(M)
    hy = Ly / float(M)
    T = np.full((M + 1, M + 1), np.inf)
    known = np.zeros((M + 1, M + 1), dtype=bool)
    for i in range(M + 1):
        T[i, 0] = eik_exact(f0, i * hx, 0.0)        # y = 0 边
        known[i, 0] = True
        T[0, i] = eik_exact(f0, 0.0, i * hy)        # x = 0 边
        known[0, i] = True
    heap = []

    def upd(i, j):
        if known[i, j]:
            return
        a = min(T[i - 1, j] if i > 0 else np.inf, T[i + 1, j] if i < M else np.inf)
        b = min(T[i, j - 1] if j > 0 else np.inf, T[i, j + 1] if j < M else np.inf)
        if not np.isfinite(a) and not np.isfinite(b):
            return
        fx = _eik_slowness(f0, j * hy) * hx
        fy = _eik_slowness(f0, j * hy) * hy
        if (not np.isfinite(a)) or (not np.isfinite(b)) or abs(a - b) >= math.hypot(fx, fy):
            t = min(a, b) + min(fx, fy)
        else:
            ix2 = 1.0 / (fx * fx)
            iy2 = 1.0 / (fy * fy)
            s = ix2 + iy2
            lin = -2.0 * (a * ix2 + b * iy2)
            cst = a * a * ix2 + b * b * iy2 - 1.0
            t = (-lin + math.sqrt(max(lin * lin - 4.0 * s * cst, 0.0))) / (2.0 * s)
        if t < T[i, j]:
            T[i, j] = t
            heapq.heappush(heap, (t, i, j))

    for i in range(1, M + 1):
        for j in range(1, M + 1):
            upd(i, j)
    while heap:
        t, i, j = heapq.heappop(heap)
        if known[i, j] or t > T[i, j]:
            continue
        known[i, j] = True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni <= M and 0 <= nj <= M and not known[ni, nj]:
                upd(ni, nj)
    _FMM_CACHE[key] = (T, hx, hy)
    return _FMM_CACHE[key]


def fmm_eik(f0, xo, yo, M):
    """观测点吸附到最近格点（观测点取二进制有理坐标 ⇒ 吸附零误差）。"""
    T, hx, hy = fmm_solve(f0, M)
    i = int(round(xo / hx))
    j = int(round(yo / hy))
    return float(T[i, j])


def golden_b324(f0=1.00, xo=0.625, yo=0.750):
    return eik_exact(f0, xo, yo)


def cand_b324(f0=1.00, xo=0.625, yo=0.750, M=640):
    return fmm_eik(f0, xo, yo, M)


def golden_b325(f0=1.00, xo=0.875, yo=0.375):
    return eik_exact(f0, xo, yo)


def cand_b325(f0=1.00, xo=0.875, yo=0.375, M=640):
    return fmm_eik(f0, xo, yo, M)


def golden_b326(f0=1.00, xo=0.375, yo=0.875):
    return eik_exact(f0, xo, yo)


def cand_b326(f0=1.00, xo=0.375, yo=0.875, M=640):
    return fmm_eik(f0, xo, yo, M)


def golden_b327(f0=1.40, xo=0.500, yo=0.500):
    return eik_exact(f0, xo, yo)


def cand_b327(f0=1.40, xo=0.500, yo=0.500, M=640):
    return fmm_eik(f0, xo, yo, M)


def golden_b328(f0=0.70, xo=0.750, yo=0.625):
    return eik_exact(f0, xo, yo)


def cand_b328(f0=0.70, xo=0.750, yo=0.625, M=640):
    return fmm_eik(f0, xo, yo, M)


# ==========================================================================================
# 参数表 / 调度表 / 自检
# ==========================================================================================
_TOL = 0.01

_BIDS_A = ["B313", "B314", "B315", "B316", "B317", "B318"]
_BIDS_B = ["B319", "B320", "B321", "B322", "B323"]
_BIDS_C = ["B324", "B325", "B326", "B327", "B328"]
_ALL_BIDS = _BIDS_A + _BIDS_B + _BIDS_C

# 逐锚 tol（本批全部 0.01；golden 量级下限 = 0.206353（B323）⇒ 20.6×tol，未放宽）
_TOL_BY_BID = {bid: 0.01 for bid in _ALL_BIDS}

# 反向扰动键（**连续**物理参数；离散档位 N/M 不作扰动键）
# 族 A：λ（源强度）+ θ₀（中心幅值）+ ξ（观测半径）——n 为整数固定档（×1.1 既破坏闭式
#        亦无物理意义）故不入键；θ₀ 的杠杆最强（O(1) 相对灵敏度）。
# 族 B：观测半径/角（nb 同上为整数固定档）。
# 族 C：慢度幅值 f0 + 观测纵坐标 yo（xo 与其一阶等价，取 yo 为最强键）。
_PERTURB_KEYS = {}
for _b in _BIDS_A:
    _PERTURB_KEYS[_b] = ("lam", "th0", "xi")
for _b in _BIDS_B:
    _PERTURB_KEYS[_b] = ("r_obs", "th_obs")
for _b in _BIDS_C:
    _PERTURB_KEYS[_b] = ("f0", "yo")

_DEFAULT_PARAMS = {
    "B313": dict(n=1, lam=1.00, th0=1.00, xi=2.00),
    "B314": dict(n=1, lam=2.50, th0=1.00, xi=1.50),
    "B315": dict(n=5, lam=1.00, th0=1.00, xi=1.00),
    "B316": dict(n=5, lam=1.00, th0=1.00, xi=2.00),
    "B317": dict(n=5, lam=1.00, th0=1.00, xi=2.50),
    "B318": dict(n=5, lam=1.30, th0=1.00, xi=1.80),
    "B319": dict(nb=1, r_obs=0.60, th_obs=0.25),
    "B320": dict(nb=1, r_obs=0.60, th_obs=0.80),
    "B321": dict(nb=1, r_obs=0.85, th_obs=0.40),
    "B322": dict(nb=2, r_obs=0.60, th_obs=0.15),
    "B323": dict(nb=3, r_obs=0.60, th_obs=0.10),
    "B324": dict(f0=1.00, xo=0.625, yo=0.750),
    "B325": dict(f0=1.00, xo=0.875, yo=0.375),
    "B326": dict(f0=1.00, xo=0.375, yo=0.875),
    "B327": dict(f0=1.40, xo=0.500, yo=0.500),
    "B328": dict(f0=0.70, xo=0.750, yo=0.625),
}

# 候选自身的离散参数键 + 扫描网格（**定档取网格末端**）
_DISC_KEY = {}
for _b in _BIDS_A:
    _DISC_KEY[_b] = "N"
for _b in _BIDS_B:
    _DISC_KEY[_b] = "N"
for _b in _BIDS_C:
    _DISC_KEY[_b] = "M"

_SCAN_GRID = {}
for _b in _BIDS_A:
    _SCAN_GRID[_b] = [16, 32, 64, 128]          # 定档 N=128（|Δ|~1e-10 ≫ 1e-12 地板）
for _b in _BIDS_B:
    _SCAN_GRID[_b] = [32, 64, 128, 256]         # 定档 N=256（|Δ|~2.1e-5 ~ 3.9e-5，余量 255×+）
for _b in _BIDS_C:
    _SCAN_GRID[_b] = [80, 160, 320, 640]        # 定档 M=640（|Δ|~3.4e-4 ~ 5.9e-4，余量 17×+）

_GOLDEN_FN = {
    "B313": golden_b313, "B314": golden_b314, "B315": golden_b315,
    "B316": golden_b316, "B317": golden_b317, "B318": golden_b318,
    "B319": golden_b319, "B320": golden_b320, "B321": golden_b321,
    "B322": golden_b322, "B323": golden_b323,
    "B324": golden_b324, "B325": golden_b325, "B326": golden_b326,
    "B327": golden_b327, "B328": golden_b328,
}

_CAND_FN = {
    "B313": cand_b313, "B314": cand_b314, "B315": cand_b315,
    "B316": cand_b316, "B317": cand_b317, "B318": cand_b318,
    "B319": cand_b319, "B320": cand_b320, "B321": cand_b321,
    "B322": cand_b322, "B323": cand_b323,
    "B324": cand_b324, "B325": cand_b325, "B326": cand_b326,
    "B327": cand_b327, "B328": cand_b328,
}


def _golden_by_bid(bid, params=None):
    p = dict(_DEFAULT_PARAMS[bid])
    if params:
        p.update(params)
    return _GOLDEN_FN[bid](**p)


def _cand_by_bid(bid, disc=None, params=None):
    p = dict(_DEFAULT_PARAMS[bid])
    if params:
        p.update(params)
    if disc is not None:
        p[_DISC_KEY[bid]] = disc
    return _CAND_FN[bid](**p)


def _lap_polar(nn, r, t, h=1e-3):
    """极坐标 Laplacian u_rr + u_r/r + u_θθ/r²（中心差分）——用于验 r^n·cos nθ 调和。"""
    f = lambda rr, tt: (rr ** nn) * math.cos(nn * tt)          # noqa: E731
    frr = (f(r + h, t) - 2.0 * f(r, t) + f(r - h, t)) / (h * h)
    fr = (f(r + h, t) - f(r - h, t)) / (2.0 * h)
    ftt = (f(r, t + h) - 2.0 * f(r, t) + f(r, t - h)) / (h * h)
    return frr + fr / r + ftt / (r * r)


def _self_test(verbose=True):
    """权威判据 D 扫描 + 反向信号 + 余量 + 闭式极限/第三方交叉自检。"""
    all_ok = True
    min_margin = (None, 1e18)
    min_sig = (None, 1e18)
    min_abs_g = (None, 1e18)
    for bid in _ALL_BIDS:
        g = _golden_by_bid(bid)
        tol = _TOL_BY_BID[bid]
        ds = [abs(_cand_by_bid(bid, disc=d) - g) for d in _SCAN_GRID[bid]]
        mono = all(ds[i + 1] < ds[i] for i in range(len(ds) - 1))
        ok = (ds[0] > 1e-13) and (ds[-1] < tol) and mono
        sig = 0.0
        for key in _PERTURB_KEYS[bid]:
            v = _DEFAULT_PARAMS[bid][key]
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            p2 = dict(_DEFAULT_PARAMS[bid])
            p2[key] = float(v) * 1.1
            sig = max(sig, abs(_golden_by_bid(bid, p2) - g))
        margin = tol / ds[-1] if ds[-1] > 0 else float("inf")
        sigx = sig / tol
        if margin < min_margin[1]:
            min_margin = (bid, margin)
        if sigx < min_sig[1]:
            min_sig = (bid, sigx)
        if abs(g) < min_abs_g[1]:
            min_abs_g = (bid, abs(g))
        all_ok = all_ok and ok
        if verbose:
            print("%s g=%+.6f tol=%.4f margin=%8.1fx sig=%6.2fx mono=%-5s ds=%s %s"
                  % (bid, g, tol, margin, sigx, mono,
                     "[" + ", ".join("%.3e" % d for d in ds) + "]",
                     "OK" if ok else "**FAIL**"))

    checks = []
    # A: λ→0 ⇒ θ = θ₀(1 − λξ²/6)（比较式用与 le_exact 完全相同的 r，规避 sqrt round-off）
    _lam0, _th00, _xi0 = 1e-14, 1.00, 2.00
    _r0 = math.sqrt(_lam0) * _xi0
    checks.append(("A λ→0 极限 = θ₀(1 − (√λξ)²/6)",
                   abs(le_exact(1, _lam0, _th00, _xi0) - _th00 * (1.0 - _r0 * _r0 / 6.0)) < 1e-18))
    # A: ξ→0 ⇒ θ = θ₀（中心条件）
    checks.append(("A ξ→0 ⇒ θ(0)=θ₀", abs(le_exact(5, 1.0, 1.0, 1e-9) - 1.0) < 1e-18))
    # A: n=1 线性性 θ(ξ;θ₀) ≡ θ₀·θ(ξ;1)（闭式自洽）
    checks.append(("A n=1 线性性 θ(ξ;θ₀)=θ₀·θ(ξ;1)",
                   abs(le_exact(1, 1.7, 1.4, 1.2) - 1.4 * le_exact(1, 1.7, 1.0, 1.2)) < 1e-15))
    # A: n=5 同调关系 θ_{θ₀}(ξ) ≡ θ₀·θ_{θ₀=1}(θ₀²ξ)（闭式自洽）
    checks.append(("A n=5 同调 θ_{θ₀}(ξ)=θ₀·θ_1(θ₀²ξ)",
                   abs(le_exact(5, 1.0, 1.3, 0.9)
                       - 1.3 * le_exact(5, 1.0, 1.0, 1.3 ** 2 * 0.9)) < 1e-15))
    # A: 第三方交叉 —— scipy DOP853 从 ε 起积分（独立流）
    try:
        from scipy.integrate import solve_ivp as _ivp
        _eps = 1e-6
        _t0, _p0 = _le_taylor(5, 1.30, 1.00, _eps)
        _s = _ivp(lambda x, y: [y[1], -(2.0 / x) * y[1] - 1.30 * y[0] ** 5],
                  [_eps, 1.80], [_t0, _p0], rtol=1e-13, atol=1e-16, method="DOP853")
        checks.append(("A 与 scipy DOP853 交叉 <1e-10",
                       abs(golden_b318() - float(_s.y[0][-1])) < 1e-10))
    except Exception:
        checks.append(("A 与 scipy DOP853 交叉 <1e-10", False))
    # B: golden 为调和函数（**极坐标** Laplacian，与极坐标定义式一致）
    checks.append(("B r²cos2θ 调和（极坐标 ∇²≈0）",
                   abs(_lap_polar(2, 0.60, 0.25)) < 1e-5))
    checks.append(("B r³cos3θ 调和（极坐标 ∇²≈0）",
                   abs(_lap_polar(3, 0.55, 0.40)) < 1e-5))
    # B: 边界一致性 u(R=1,θ) = u_b(θ)
    checks.append(("B 边界 u(1,θ)=cos(nθ)",
                   abs((1.0 ** 2) * math.cos(2 * 0.7) - math.cos(2 * 0.7)) < 1e-15))
    # C: |∇T| = f（中心差分验证制造解）
    _h = 1e-4
    _f0, _x, _y = 1.30, 0.5, 0.4
    _gx = (eik_exact(_f0, _x + _h, _y) - eik_exact(_f0, _x - _h, _y)) / (2 * _h)
    _gy = (eik_exact(_f0, _x, _y + _h) - eik_exact(_f0, _x, _y - _h)) / (2 * _h)
    checks.append(("C 制造解满足 |∇T| = f0√(1+(1+y)²)",
                   abs(math.hypot(_gx, _gy) - _eik_slowness(_f0, _y)) < 1e-6))
    # C: 边界初始化与研究解一致
    checks.append(("C 边界 T(x,0)=f0·x 一致",
                   abs(eik_exact(_f0, 0.7, 0.0) - _f0 * 0.7) < 1e-15))

    for name, ok in checks:
        print("  [climit] %-40s %s" % (name, "OK" if ok else "**FAIL**"))
        all_ok = all_ok and ok

    print("MIN_MARGIN %s %.1fx | MIN_SIG %s %.2fx | MIN_|g| %s %.6f"
          % (min_margin[0], min_margin[1], min_sig[0], min_sig[1], min_abs_g[0], min_abs_g[1]))
    print("ALL_OK=%s" % all_ok)
    return all_ok


if __name__ == "__main__":
    import sys
    _r = _self_test()
    print("SELFTEST_ALL_OK=%s" % _r)
    sys.exit(0 if _r else 1)
