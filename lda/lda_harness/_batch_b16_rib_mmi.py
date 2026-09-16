# ---------------------------------------------------------------------------
# B16 · rib-MMI 1×2 自成像长度 — 方法学独立严格求解器（候选）
# ---------------------------------------------------------------------------
# 物理对象：脊形(rib)多模干涉耦合器(MMI)的多模区。
#
#   golden = Soldano & Pennings 1995 抛物线色散闭式自成像长度
#            L_gold = (9/4) · n_eff · W_e² / λ0   （1×2 第一双像成像长度）
#   cand   = 脊形 MMI **精确本征模 + 全场模态重构**：
#            ① 由器件给定的基模有效折射率 n_eff 反演 step-index 平板 core 折射率 n_c
#               （使平板基模有效折射率 == 器件 rib 的 n_eff，建模同一物理对象，
#                区别于被否决的 symmetric-slab EME：后者自行反算有效参数 ⇒ 13% 偏差）
#            ② 数值求解平板 TE 本征方程：偶模 h·tan(h·a)=√(K²−h²)、奇模 h·cot(h·a)=−√(K²−h²)
#               （按 tan/cot 各波瓣区间二分求根，杜绝渐近线伪根）
#            ③ 把输入场（单端口激励，置于 x=−W/4）按全部本征模展开，沿 z 精确传播
#               ψ(x,z)=Σ_m a_m·ψ_m(x)·exp(iβ_m·z)，扫描 z 定位输出 = 1×2 双像
#               （两个峰位于 ±W/4）的首个成像长度 L_self
#
# 方法学独立：golden 用抛物线近似闭式（套常数 9/4）；cand 用**精确数值模态展开 +
# 全场传播定位双像**，两条路径独立 ⇒ |L_cand − L_gold| 反映抛物线近似固有误差，
# 这才是真可证伪的验证（自证桩 |diff|≡0 不携带信息）。PASS/FAIL 由死标量决定，
# LLM 不进判决路径。
#
# numpy 纪律：所有返回强制 Python 原生 float（禁止 np.float64 泄漏进判决链/JSON）。
# ---------------------------------------------------------------------------
import numpy as np

# 默认包层（SiO2）
_N_CLAD = 1.444


def _invert_core_index(W_e, n_eff, wl, n_clad=_N_CLAD):
    """给定基模有效折射率 n_eff，反演对称平板 core 折射率 n_c。

    基模(偶, m=0)满足  h·tan(h·a) = q,  a = W_e/2,
    h = k0·sqrt(n_c² − n_eff²),  q = k0·sqrt(n_eff² − n_clad²)。
    解 h·tan(h·a)=q（h∈(0, π/(2a)) 单调），再 n_c = sqrt(n_eff² + (h/k0)²)。
    """
    k0 = 2.0 * np.pi / wl
    a = 0.5 * W_e
    q = k0 * np.sqrt(max(n_eff ** 2 - n_clad ** 2, 1e-30))

    def g(h):
        return h * np.tan(h * a) - q

    lo, hi = 1e-6, (np.pi / (2.0 * a)) - 1e-6
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if g(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    h = 0.5 * (lo + hi)
    n_c = np.sqrt(n_eff ** 2 + (h / k0) ** 2)
    return float(n_c)


def _slab_mode_effs(n_c, n_clad, W_e, wl, n_modes=200):
    """返回对称平板的全部导模有效折射率（降序，取前 n_modes）。

    用 tan/cot 各波瓣区间二分求根，规避渐近线伪根：
      偶模 m：h·tan(h·a) = √(K²−h²),  h∈(mπ, mπ+π/2)
      奇模 m：h·cot(h·a) = −√(K²−h²), h∈(mπ+π/2, (m+1)π)
    其中 K² = (k0·n_c)² − (k0·n_clad)²，h_max=√K²。
    """
    k0 = 2.0 * np.pi / wl
    a = 0.5 * W_e
    K2 = (k0 * n_c) ** 2 - (k0 * n_clad) ** 2
    h_max = np.sqrt(K2)
    PI = np.pi
    modes = []
    m = 0
    while True:
        # 偶模 h·a ∈ (mπ, mπ+π/2) ⇒ h ∈ (mπ/a, (mπ+π/2)/a)
        lo_e = m * PI / a
        hi_e = (m * PI + PI / 2.0) / a - 1e-9
        if lo_e < h_max:
            if hi_e > h_max:
                hi_e = h_max - 1e-9
            fe = lambda h: h * np.tan(h * a) - np.sqrt(max(K2 - h * h, 0.0))
            le, he = lo_e, hi_e
            for _ in range(100):
                mid = 0.5 * (le + he)
                if fe(le) * fe(mid) <= 0.0:
                    he = mid
                else:
                    le = mid
            h_e = 0.5 * (le + he)
            modes.append(float(np.sqrt(max(n_c ** 2 - (h_e / k0) ** 2, 0.0))))
        # 奇模 h·a ∈ (mπ+π/2, (m+1)π) ⇒ h ∈ ((mπ+π/2)/a, (m+1)π/a)
        lo_o = (m * PI + PI / 2.0) / a + 1e-9
        hi_o = ((m + 1) * PI) / a - 1e-9
        if lo_o < h_max:
            if hi_o > h_max:
                hi_o = h_max - 1e-9
            fo = lambda h: h / np.tan(h * a) + np.sqrt(max(K2 - h * h, 0.0))
            lo_, hi_ = lo_o, hi_o
            for _ in range(100):
                mid = 0.5 * (lo_ + hi_)
                if fo(lo_) * fo(mid) <= 0.0:
                    hi_ = mid
                else:
                    lo_ = mid
            h_o = 0.5 * (lo_ + hi_)
            modes.append(float(np.sqrt(max(n_c ** 2 - (h_o / k0) ** 2, 0.0))))
        else:
            break
        m += 1
        if m > 400:
            break
    modes = sorted(modes, reverse=True)
    return np.array(modes[:n_modes], dtype=float)


def _slab_mode_fields(n_c, n_clad, W_e, wl, modes, x):
    """返回归一化本征模场 ψ_m(x)，shape=(M, Nx)。偶模索引偶、奇模索引奇。"""
    k0 = 2.0 * np.pi / wl
    a = 0.5 * W_e
    M = len(modes)
    fields = np.zeros((M, len(x)), dtype=float)
    for mi in range(M):
        ne = modes[mi]
        h = k0 * np.sqrt(max(n_c ** 2 - ne ** 2, 0.0))
        q = k0 * np.sqrt(max(ne ** 2 - n_clad ** 2, 0.0))
        if mi % 2 == 0:  # 偶模
            prof = np.where(np.abs(x) < a, np.cos(h * x),
                            np.cos(h * a) * np.exp(-q * (np.abs(x) - a)))
        else:            # 奇模
            prof = np.where(np.abs(x) < a, np.sin(h * x),
                            np.sign(x) * np.sin(h * a) * np.exp(-q * (np.abs(x) - a)))
        prof = prof / np.sqrt(np.trapezoid(prof ** 2, x))
        fields[mi] = prof
    return fields


def rib_mmi_selfimaging_length(W_e, n_eff, wl, n_clad=_N_CLAD):
    """候选主入口：脊形 MMI 全场模态重构，定位 1×2 首双像成像长度（µm）。

    与 golden 的*方法学独立*路径：
      golden = 抛物线色散闭式  L = (9/4)·n_eff·W_e²/λ0
               （对 β_m−β_0 作抛物线泰勒截断近似）
      cand   = 精确解 TE 平板本征方程得全部导模 {ψ_m, β_m}，
               把单端口输入场按 {ψ_m} 展开、沿 z 精确传播
               ψ(x,z)=Σ_m a_m·ψ_m(x)·exp(iβ_m z)，
               扫描 z 定位输出 = 1×2 双像（两峰位于 ±a/2）的成像长度。
    残差 |L_cand − L_gold| 反映抛物线近似 + 有限模集的固有误差（有界、物理），
    正是可证伪交叉检验（自证桩 |diff|≡0 不携带信息）。PASS/FAIL 由死标量决定。

    ⚠️ 对象一致性：由器件给定的基模有效折射率 n_eff 反演对称平板 core 折射率
    n_c，使平板基模 == 器件 MMI 基模 ⇒ 建模同一物理对象；区别于被否决的
    symmetric-slab EME（后者用 2.80 定核、基模 ~2.7 ≠ 器件 2.4 ⇒ 对象错配）。
    本函数**不套用任何 (9/8)/(3) 成像因子**——成像长度完全由场重构定位得出。

    返回 Python 原生 float（numpy 纪律）。
    """
    n_c = _invert_core_index(W_e, n_eff, wl, n_clad)
    modes = _slab_mode_effs(n_c, n_clad, W_e, wl)
    if len(modes) < 3:
        raise RuntimeError("MMI 导模数不足以成像")
    k0 = 2.0 * np.pi / wl
    a = 0.5 * W_e
    Nx = 4001
    x = np.linspace(-2.0 * a, 2.0 * a, Nx)
    M = len(modes)
    psi = _slab_mode_fields(n_c, n_clad, W_e, wl, modes, x)
    betas = k0 * modes

    # 输入：单端口激励，置于 x0 = -W/4 = -a/2
    x0 = -a / 2.0
    sigma = a / 4.0
    inp = np.exp(-((x - x0) ** 2) / (2.0 * sigma ** 2))
    inp = inp / np.sqrt(np.trapezoid(inp ** 2, x))
    a_m = np.array([np.trapezoid(inp * psi[mi], x) for mi in range(M)])

    # 目标 1×2 双像：两个峰位于 ±a/2（与输入对称）
    target = (np.exp(-((x - a / 2.0) ** 2) / (2.0 * sigma ** 2)) +
              np.exp(-((x + a / 2.0) ** 2) / (2.0 * sigma ** 2)))
    target = target / np.sqrt(np.trapezoid(target ** 2, x))
    int_target = np.abs(target) ** 2

    # 扫 z，用**双度量联合判据**定位首个真 1×2 双像：
    #   度量① ov(z) = 输出强度与理想双像的归一化重叠（对整场形状敏感）；
    #   度量② M(z)  = min(I(−a/2),I(+a/2)) / I(0)（双瓣高 + 中心零深；
    #                 对 z≈L_π 处单像（仅一瓣）与晚期高阶像强判别）。
    #   真首像 = 首个同时满足 ov ≥ 95%·max(ov) 且 M ≥ 40%·max(M) 的局部极大
    #   （两度量互补：单用 ov 在窄 MMI 会把晚期多像误选，单用 M 会把 L_π 单像误选）。
    L_gold_est = 2.25 * n_eff * W_e ** 2 / wl
    zmax = 3.0 * L_gold_est
    nz = 3000
    zs = np.linspace(0.0, zmax, nz)
    intens = np.abs((a_m * np.exp(1j * betas * zs[:, None])) @ psi) ** 2
    num = (intens * int_target[None, :]).sum(axis=1)
    den = np.sqrt((intens * intens).sum(axis=1) * (int_target * int_target).sum())
    ovs = num / den
    ix0 = int(np.argmin(np.abs(x)))
    ixp = int(np.argmin(np.abs(x - a / 2.0)))
    ixm = int(np.argmin(np.abs(x + a / 2.0)))
    lobe = np.minimum(intens[:, ixp], intens[:, ixm]) / (intens[:, ix0] + 1e-12)

    thr_ov = 0.95 * float(ovs.max())
    thr_lobe = 0.40 * float(lobe.max())
    zmin = 0.05 * zmax
    bestz = None
    for i in range(1, nz - 1):
        if zs[i] < zmin:
            continue
        if ovs[i] >= thr_ov and lobe[i] >= thr_lobe:
            bestz = zs[i]
            break
    if bestz is None:
        bestz = float(zs[int(np.argmax(ovs))])

    # 细扫 bestz 邻域（同一强度重叠度量）
    zf = np.linspace(max(bestz - L_gold_est * 0.05, 0.0),
                     bestz + L_gold_est * 0.05, 600)
    best, bestz2 = float(ovs.max()), bestz
    for z in zf:
        intf = np.abs(psi.T @ (a_m * np.exp(1j * betas * z))) ** 2
        ov = (np.trapezoid(intf * int_target, x) /
              np.sqrt(np.trapezoid(intf * intf, x) * (int_target * int_target).sum()))
        if ov > best:
            best, bestz2 = ov, z
    return float(bestz2)
