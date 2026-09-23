"""LDA · L3 自研 CFS-PML 吸收边界（G11「真 PML」）— C 级自主，纯 numpy。

## 背景（v0.9.132 前的实测状态）

本仓 `fdtd2d` / `fdtd3d` 的吸收边界是**梯度二次型导电海绵**
（`_sponge_1d` + 乘性阻尼，代码自述「无 Mur-ABC、无 CPML」）。它不是阻抗
匹配的 PML —— 只靠 σ 剖面耗散，斜入射与低频 / 倏逝分量回反射大。

## 本模块做什么

把吸收边界升级为 **CFS-PML（Complex-Frequency-Shifted PML，复频移坐标拉伸
PML）**（Taflove & Hagness, *Computational Electrodynamics*, 3rd ed. §7.9）：

    κ(x)   实坐标拉伸    — 抑制倏逝波（纯 σ 层会放大倏逝分量）
    σ(x)   导电率剖面    — 吸收传播波
    α(x)   复频移        — 吸收低频 / 静态分量
    ψ      卷积记忆变量  — 递归更新 ⇒ O(1) 存储 / 步、O(1) 计算 / 步

归一化单位与 `fdtd2d` / `fdtd3d` **逐字一致**（c = ε₀ = μ₀ = 1）⇒ η₀ = 1；
匹配层取 σ*/μ₀ = σ/ε₀ ⇒ E 侧与 H 侧**共用同一组系数**（这正是「匹配」的含义）。

## 离散式（本模块是**单一定义处**，调用方不得另写一份）

    b(x) = exp(−(σ/κ + α)·Δt)
    c(x) = σ/(σ·κ + κ²·α)·(b − 1)          （σ → 0 时 c ≡ 0）
    ψⁿ   = b·ψⁿ⁻¹ + c·(∂/∂x)
    ∂/∂x  →  (1/κ)·(∂/∂x) + ψ

## 三条不变量（本模块的铁律）

1. **零外部依赖**：只 `numpy` + `math`。
2. **层外逐位恒等**：σ = α = 0 且 κ = 1 处 b ≡ 1、c ≡ 0 ⇒ ψ 恒 0 ⇒ 与
   「无吸收」逐位相同。这是 CPML「不污染物理区」的**机器可证**形式，
   由 `__main__` 自检断言（不是声称）。
3. **只增不改**：本模块与 `fdtd_cpml.py` 都**不修改** `fdtd2d` / `fdtd3d`
   的既有默认路径。⚠️ 改默认吸收器 = 改**全部 FDTD 依赖锚**的数值 ⇒
   那是另一项决策（须重跑锚验证），**不属本批**。

## 诚实边界

- σ_max 的默认值用经典最优式 `σ_opt = −(m+1)·ln(R₀)/(2·η·L)`（η = 1 归一化）。
  该式保证「反射 ≈ R₀ 且**与层厚无关**」⇒ **不适合**做判据 D 的扫描参数
  （扫层厚则残差不变 ⇒ 无判据 D）。判据 D 须**显式固定 σ_max** 再扫层厚，
  见 `fdtd_cpml.py` 与 `run_cpml_absorber_smoke.py`。
- 本模块只做**真空 / 单一背景 ε_r** 的剖面装配（反射测量全程在 n = 1 做）；
  **非均匀背景内的 PML 标度未验**（如实标注，不声称）。
"""
from __future__ import annotations

import math

import numpy as np

__all__ = [
    "DEFAULT_ORDER",
    "DEFAULT_KAPPA_MAX",
    "DEFAULT_ALPHA_MAX",
    "sigma_max_for_target",
    "graded_profile",
    "cn_coefficients",
    "cpml_axis",
    "null_axis",
]

#: 多项式梯度阶数（经典取值 3~4；越大则外边缘越陡）
DEFAULT_ORDER = 3
#: 实坐标拉伸上限（κ_max = 1 退化为纯 PML；>1 抑制倏逝波，经典 5~15）
DEFAULT_KAPPA_MAX = 5.0
#: 复频移上限（在 PML 内边缘处最大）
DEFAULT_ALPHA_MAX = 0.08


def sigma_max_for_target(n_abs, dl, r_target=1e-8, order=DEFAULT_ORDER):
    """经典最优 σ_max：`σ_opt = −(m+1)·ln(R₀)/(2·η·L)`，归一化单位 η = 1。

    物理含义：在该 σ_max 下，**理论反射系数 ≈ R₀**，且与层厚 L 无关
    （因为 σ_max ∝ 1/L）。⇒ 它**不能**当判据 D 的扫描参数。
    """
    L = float(n_abs) * float(dl)
    if L <= 0.0:
        return 0.0
    return -(order + 1) * math.log(r_target) / (2.0 * L)


def graded_profile(n, n_abs, order, dl, sigma_max, kappa_max, alpha_max):
    """构造 σ / κ / α 剖面（仅两端各 `n_abs` 格内非平凡）。

    约定与 `_sponge_1d` **同构**（便于逐项对照）：
      · 索引 0 是**外边缘**（深度最大）、`n_abs-1` 是**内边缘**（深度 0）；
      · 右端镜像（`n-1` 外边缘）。
    深度按**格索引**量（`(n_abs-1-i)·dl`），故两端恰好取到 g = 1 与 g = 0
    —— 内边缘 σ = 0、κ = 1（**连续、无阻抗跳变**，这是 CPML 低反射的根源）。
    """
    sigma = np.zeros(n, dtype=float)
    kappa = np.ones(n, dtype=float)
    alpha = np.zeros(n, dtype=float)
    if n_abs < 1 or n < 2 * n_abs:
        return sigma, kappa, alpha

    xs = np.arange(n_abs, dtype=float)
    lg = max(1.0, float(n_abs - 1) * float(dl))      # 梯度归一化长度（格索引口径）
    depth = (n_abs - 1.0 - xs) * float(dl)           # 0（内边缘）→ (n_abs-1)·dl（外）
    g = (depth / lg) ** order

    sig = sigma_max * g
    kap = 1.0 + (kappa_max - 1.0) * g
    alp = alpha_max * (1.0 - depth / lg) ** order    # α 内边缘最大、外边缘 0

    sigma[:n_abs] = sig                              # 左端：i=0 → 深度最大
    kappa[:n_abs] = kap
    alpha[:n_abs] = alp
    sigma[n - n_abs:] = sig[::-1]                    # 右端镜像：i=n-1 → 深度最大
    kappa[n - n_abs:] = kap[::-1]
    alpha[n - n_abs:] = alp[::-1]
    return sigma, kappa, alpha


def cn_coefficients(sigma, kappa, alpha, dt):
    """(σ, κ, α) → (b, c) —— CPML 卷积系数的**单一定义处**。

    `b = exp(−(σ/κ + α)·Δt)`；`c = σ/(σ·κ + κ²·α)·(b − 1)`，σ = 0 处 c ≡ 0。

    ⚠️ 不可对 (b, c) 做节点平均来取半格偏移（b 对 σ 是非线性的）——
    必须先对 (σ, κ, α) 平均、再代入本函数。见 `cpml_axis` 的 `_h` 一套。
    """
    sigma = np.asarray(sigma, dtype=float)
    kappa = np.asarray(kappa, dtype=float)
    alpha = np.asarray(alpha, dtype=float)
    b = np.exp(-(sigma / kappa + alpha) * dt)
    c = np.zeros_like(sigma)
    nz = sigma > 0.0
    if np.any(nz):
        den = sigma[nz] * kappa[nz] + kappa[nz] ** 2 * alpha[nz]
        c[nz] = sigma[nz] / den * (b[nz] - 1.0)
    return b, c


def _half(a):
    """一维剖面的半格偏移：0.5·(a[i] + a[i+1])，末位取边缘值。"""
    out = np.empty_like(a)
    if a.size < 2:
        return a.copy()
    out[:-1] = 0.5 * (a[:-1] + a[1:])
    out[-1] = a[-1]
    return out


def null_axis(n):
    """PBC 轴的「空吸收器」：σ = α = 0、κ = 1 ⇒ b ≡ 1、c ≡ 0、ψ 恒 0。

    存在的意义：让时间步进核**只有一条代码路径**（PBC 轴走同一套公式），
    同时把「PBC 轴不吸收」这件事变成**数组上可断言**的事实
    （见 `fdtd_cpml._assert_null_axes`），而不是靠调用方自觉。
    """
    z = np.zeros(n, dtype=float)
    o = np.ones(n, dtype=float)
    return {
        "n": int(n), "n_abs": 0, "sigma_max": 0.0, "thickness_um": 0.0,
        "sigma": z.copy(), "kappa": o.copy(), "alpha": z.copy(),
        "kappa_e": o.copy(), "b_e": o.copy(), "c_e": z.copy(),
        "kappa_h": o.copy(), "b_h": o.copy(), "c_h": z.copy(),
        "null": True,
    }


def cpml_axis(n, n_abs, dt, dl, order=DEFAULT_ORDER,
              kappa_max=DEFAULT_KAPPA_MAX, alpha_max=DEFAULT_ALPHA_MAX,
              sigma_max=None, r_target=1e-8):
    """一个轴上的 CPML 系数（E 节点 / H 节点两套）。

    参数
    ----
    n : int        该轴格数
    n_abs : int    两端各多少格做 PML
    dt, dl : float 时间步 / 格距（归一化单位，c = 1）
    order, kappa_max, alpha_max : CPML 剖面参数
    sigma_max : float | None
        None ⇒ 用 `sigma_max_for_target(...)`（理论反射 ≈ r_target、与层厚无关）；
        显式给值 ⇒ 用该值（**判据 D 的扫描方式**：固定 σ_max 扫层厚）。
    r_target : float
        仅当 sigma_max 为 None 时使用。

    ###### 返回
    dict，键：sigma/kappa/alpha（E 节点剖面）、
    `kappa_e/b_e/c_e`（E 节点系数）、`kappa_h/b_h/c_h`（半格偏移的 H 节点系数）、
    `sigma_max`、`thickness_um`。
    """
    if sigma_max is None:
        sigma_max = sigma_max_for_target(n_abs, dl, r_target, order)
    sigma, kappa, alpha = graded_profile(
        n, n_abs, order, dl, sigma_max, kappa_max, alpha_max)
    b_e, c_e = cn_coefficients(sigma, kappa, alpha, dt)

    sig_h = _half(sigma)
    kap_h = _half(kappa)
    alp_h = _half(alpha)
    b_h, c_h = cn_coefficients(sig_h, kap_h, alp_h, dt)

    return {
        "n": int(n), "n_abs": int(n_abs), "sigma_max": float(sigma_max),
        "thickness_um": float(n_abs) * float(dl),
        "sigma": sigma, "kappa": kappa, "alpha": alpha,
        "kappa_e": kappa, "b_e": b_e, "c_e": c_e,
        "kappa_h": kap_h, "b_h": b_h, "c_h": c_h,
        "null": False,
    }


if __name__ == "__main__":
    # ---- 自检：把「层外逐位恒等」钉成断言，而不是声称 ----
    ok = True
    dl, dt, n, n_abs = 0.05, 0.0336, 200, 40
    ax = cpml_axis(n, n_abs, dt, dl, sigma_max=18.0)

    inner = slice(n_abs, n - n_abs)
    same_b = bool(np.all(ax["b_e"][inner] == 1.0))
    same_c = bool(np.all(ax["c_e"][inner] == 0.0))
    same_k = bool(np.all(ax["kappa_e"][inner] == 1.0))
    print("① 层外恒等：b==1 %s · c==0 %s · kappa==1 %s" % (same_b, same_c, same_k))
    ok &= same_b and same_c and same_k

    sym = bool(np.allclose(ax["sigma"], ax["sigma"][::-1], rtol=0, atol=0)
               and np.allclose(ax["kappa"], ax["kappa"][::-1], rtol=0, atol=0))
    print("② 左右镜像对称：%s" % sym)
    ok &= sym

    edge_sig = max(ax["sigma"][0], ax["sigma"][-1])
    inner_sig = ax["sigma"][n_abs - 1]
    print("③ σ 剖面：内边缘 %.3e → 外边缘 %.3e（应 0 → σ_max）" % (inner_sig, edge_sig))
    ok &= (inner_sig == 0.0) and abs(edge_sig - ax["sigma_max"]) < 1e-12

    kap_edge = max(ax["kappa"][0], ax["kappa"][-1])
    print("④ κ 剖面：内边缘 %.6f → 外边缘 %.6f" % (ax["kappa"][n_abs - 1], kap_edge))
    ok &= (ax["kappa"][n_abs - 1] == 1.0) and abs(kap_edge - 5.0) < 1e-12

    c_neg = bool(np.all(ax["c_e"][ax["sigma"] > 0] < 0.0))
    print("⑤ σ>0 处 c < 0 且 |c| ≤ 1：%s（max|c| %.4f）"
          % (c_neg, float(np.max(np.abs(ax["c_e"])))))
    ok &= c_neg and bool(np.max(np.abs(ax["c_e"])) <= 1.0)

    # b 对 (σ,κ,α) 非线性 ⇒ 半格偏移必须先平均剖面再算系数（不可平均系数）
    wrong = 0.5 * (ax["b_e"][:-1] + ax["b_e"][1:])
    print("⑥ 半格偏移口径：|b_h − b_e均值| 最大 %.3e（应 > 0 ⇒ 两法不等价）"
          % float(np.max(np.abs(ax["b_h"][:-1] - wrong))))
    ok &= bool(np.max(np.abs(ax["b_h"][:-1] - wrong)) > 0.0)

    # σ_opt 式 ⇒ 反射与层厚无关（故不可作判据 D 的扫描参数）
    s20 = sigma_max_for_target(20, dl)
    s80 = sigma_max_for_target(80, dl)
    print("⑦ σ_opt(20) = %.6f · σ_opt(80) = %.6f ⇒ σ_opt·L 守恒 %.9f"
          % (s20, s80, s20 * 20 * dl))
    ok &= abs(s20 * 20 * dl - s80 * 80 * dl) < 1e-12

    nx = null_axis(16)
    print("⑧ 空吸收器：b≡1 %s · c≡0 %s · κ≡1 %s"
          % (bool(np.all(nx["b_e"] == 1.0)), bool(np.all(nx["c_e"] == 0.0)),
             bool(np.all(nx["kappa_e"] == 1.0))))
    ok &= bool(np.all(nx["b_e"] == 1.0) and np.all(nx["c_e"] == 0.0)
               and np.all(nx["kappa_e"] == 1.0))

    print("=" * 60)
    print("cpml.py selfcheck:", "ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
