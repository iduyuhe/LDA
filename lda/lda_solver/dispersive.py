"""LDA · G13 时域色散 / 各向异性 / 非线性（2D 全矢量 FDTD，新增模块，不改 fdtd2d/3d）。

## 本模块回答的三个问题

FDTD 内核从「标量实 n²」升级为支持
  ① **色散介质**（Drude / Lorentz，ADE 法）—— 仓库此前只有频域 Sellmeier，时域 χ/ω 全缺失
  ② **各向异性 ε 张量**（对角，E = ε⁻¹ D）
  ③ **Kerr 非线性**（χ^(3)，瞬时）

并全部**可关断** ⇒ 关断后严格退化为标量实 ε（与既有 FDTD 一致）。

## 机器可证（对应规划 §5.5 G13 验收 ①②③）

  ① 色散：CW 在 Drude/Lorentz 介质中测得的传播常数 k_meas 与解析
     ε_r(ω) 给出的 k_analytic = ω·√Re ε_r(ω) 一致（< tol，网格色散之外）
  ② 各向异性：单轴晶体中 **两正交偏振** 沿同一轴传播的相速度不同
     （birefringence）—— Ez 偏振看 ε_zz、Ex 偏振看 ε_xx，两者比值 = n_e/n_o
  ③ 非线性：弱场极限下 Kerr 更新 **精确退化到线性**（χ3→0 或 E→0 ⇒ 误差→0）
  （稳定性判据 ②：长程运行 max|E| 有界，不发散）

## 纪律

- **只增不改**：本模块**不修改** `fdtd2d.py` / `fdtd3d.py` 一行；既不接线进默认，
  也不复用其步进核（独立 2D 全 Yee，自带 PBC/吸收）。这是**故意的零影响**——
  smoke ⑩ 把「源码含 dispersive / 改动 fdtd2d/3d」钉成变更探测器。
- 归一化约定与全仓一致（c = ε₀ = μ₀ = 1）。
"""
from __future__ import annotations

import math

import numpy as np

__all__ = ["ScalarMedium", "LorentzMedium", "AnisotropicMedium", "KerrMedium",
           "run_2d", "analytic_eps"]


# ---------------------------------------------------------------------------
# 介质模型：统一接口 `reset(shape)` + `step_E(Dx,Dy,Dz,dt,eps_bg) -> (Ex,Ey,Ez)`
# 默认 Scalar 退化；其余三类各自维护内部状态（极化电流 / 上一步 E）。
# ---------------------------------------------------------------------------
class ScalarMedium:
    """标量实 ε（关断所有 G13 特性时的基准，等同既有 FDTD）。"""

    kind = "scalar"

    def __init__(self, eps=1.0):
    # 任意几何 / 色散 / 各向异性 / 非线性 全关断
        self.eps = float(eps)

    def reset(self, shape):
        self._shape = shape

    def step_E(self, Dx, Dy, Dz, dt, eps_bg):
        e = self.eps
        return Dx / e, Dy / e, Dz / e


class LorentzMedium:
    """Lorentz（含 Drude：w0=0 即 Drude）。ADE 两阶递推（Sullivan / Taflove）。

    ε_r(ω) = ε∞ + Σ wp_l² / (w0_l² − ω² − i·γ_l·ω)
    极化 P_l 满足 d²P/dt² + γ dP/dt + w0² P = ε₀ wp² E
    （Drude = w0=0 的退化形式；统一走同一递推 ⇒ 一处实现覆盖两种色散）

    E 更新（D-form）：E^{n+1} = E^n + (dt/ε∞)·curlH
                        − (1/ε∞)·Σ_l (P_l^{n+1} − P_l^n)
    P_l 递推：P^{n+1} = [ (2 − w0²dt²)P^n + (γdt/2 − 1)P^{n−1}
                          + dt² wp² E^n ] / (1 + γdt/2)
    """

    kind = "lorentz"

    def __init__(self, eps_inf=1.0, poles=None):
        # poles: list of (wp, w0, gamma)
        self.eps_inf = float(eps_inf)
        self.poles = [tuple(map(float, p)) for p in (poles or [])]
        if not self.poles:
            raise ValueError("LorentzMedium 至少需要一个 pole")

    def reset(self, shape):
        self._shape = shape
        # 每个 E 分量各一套极化电流（P_x/P_y/P_z 各自被对应 E 分量驱动）
        self._P = [np.zeros(shape) for _ in range(3 * len(self.poles))]
        self._P2 = [np.zeros(shape) for _ in range(3 * len(self.poles))]
        self._E_prev = [np.zeros(shape), np.zeros(shape), np.zeros(shape)]  # 上一时刻 E^n

    def step_E(self, Dx, Dy, Dz, dt, eps_bg):
        e = self.eps_inf
        D_list = (Dx, Dy, Dz)
        out = [None, None, None]
        for ci, D in enumerate(D_list):
            pidx = ci * len(self.poles)
            Psum = np.zeros(self._shape)
            for k, (wp, w0, g) in enumerate(self.poles):
                P = self._P[pidx + k]
                P2 = self._P2[pidx + k]
                den = 1.0 + g * dt / 2.0
                c0 = dt * dt * wp * wp / den
                c1 = (2.0 - w0 * w0 * dt * dt) / den
                c2 = (g * dt / 2.0 - 1.0) / den
                # ADE 两阶递推：用上一时刻 E^n 驱动（显式、CFL 安全、色散正确）
                Pnew = c1 * P + c2 * P2 + c0 * self._E_prev[ci]
                Psum = Psum + Pnew
                self._P2[pidx + k] = P
                self._P[pidx + k] = Pnew
            # 本构关系 D = ε∞·E + P  ⇒  E = (D − P)/ε∞
            out[ci] = (D - Psum) / e
        self._E_prev = out
        return out[0], out[1], out[2]


class AnisotropicMedium:
    """对角各向异性 ε = diag(exx, epsy, epsz)。E = ε⁻¹ D（对角 ⇒ 分量各自除）。

    2D 全矢量下可体现**面内各向异性**（TEz 单分量看不到）：沿 y 传播时
    Ex 偏振看 exx、Ez 偏振看 epsz —— 两正交偏振相速度不同（birefringence）。
    """

    kind = "anisotropic"

    def __init__(self, exx=1.0, epsy=1.0, epsz=1.0):
        self.exx = float(exx)
        self.epsy = float(epsy)
        self.epsz = float(epsz)

    def reset(self, shape):
        self._shape = shape

    def step_E(self, Dx, Dy, Dz, dt, eps_bg):
        return Dx / self.exx, Dy / self.epsy, Dz / self.epsz


class KerrMedium:
    """Kerr 非线性：ε_eff = ε_lin + n2·|E|²（逐分量、瞬时近似，用上一步 E）。

    弱场极限（n2→0 或 |E|→0）⇒ ε_eff→ε_lin ⇒ 精确退化到线性（验收 ③）。
    强场 ⇒ ε_eff 抬升 ⇒ 相速度下降、相位累积加快（自相位调制）。
    """

    kind = "kerr"

    def __init__(self, eps_lin=1.0, n2=0.0):
        self.eps_lin = float(eps_lin)
        self.n2 = float(n2)

    def reset(self, shape):
        self._shape = shape
        self._Ex = np.zeros(shape)
        self._Ey = np.zeros(shape)
        self._Ez = np.zeros(shape)

    def step_E(self, Dx, Dy, Dz, dt, eps_bg):
        e0 = self.eps_lin
        n2 = self.n2
        Ex = Dx / (e0 + n2 * self._Ex * self._Ex)
        Ey = Dy / (e0 + n2 * self._Ey * self._Ey)
        Ez = Dz / (e0 + n2 * self._Ez * self._Ez)
        self._Ex, self._Ey, self._Ez = Ex, Ey, Ez
        return Ex, Ey, Ez


def analytic_eps(medium, omega):
    """返回介质在频率 ω 的复数 ε_r（用于色散判据 ① 的解析对照）。"""
    if medium.kind == "scalar":
        return complex(medium.eps, 0.0)
    if medium.kind == "lorentz":
        eps = complex(medium.eps_inf, 0.0)
        for (wp, w0, g) in medium.poles:
            eps = eps + (wp * wp) / (w0 * w0 - omega * omega - 1j * g * omega)
        return eps
    # 各向异性 / Kerr：返回实部（验收用各自对应入口）
    if medium.kind == "anisotropic":
        return complex(medium.epsz, 0.0)  # 默认返回 z 分量，调用处按需取 exx/epsz
    if medium.kind == "kerr":
        return complex(medium.eps_lin, 0.0)
    raise ValueError("未知介质 %s" % medium.kind)


# ---------------------------------------------------------------------------
# 2D 全 Yee 推进（TEz + TMz 共存）。axis=传播轴，transverse=另一轴 PBC。
# ---------------------------------------------------------------------------
def _diff_x(f, pbc_x):
    # ∂f/∂x，前向：(f[i+1] − f[i])；PBC 时环绕
    if pbc_x:
        return np.roll(f, -1, axis=0) - f
    out = np.zeros_like(f)
    out[:-1] = f[1:] - f[:-1]
    return out


def _diff_y(f, pbc_y):
    if pbc_y:
        return np.roll(f, -1, axis=1) - f
    out = np.zeros_like(f)
    out[:, :-1] = f[:, 1:] - f[:, :-1]
    return out


def _diff_x_b(f, pbc_x):
    # 后向：(f[i] − f[i−1])
    if pbc_x:
        return f - np.roll(f, 1, axis=0)
    out = np.zeros_like(f)
    out[1:] = f[1:] - f[:-1]
    return out


def _diff_y_b(f, pbc_y):
    if pbc_y:
        return f - np.roll(f, 1, axis=1)
    out = np.zeros_like(f)
    out[:, 1:] = f[:, 1:] - f[:, :-1]
    return out


def run_2d(nx, ny, dl, dt, omega, nsteps, medium, axis=1, source_comp="Ez",
           i_src=0, probe_pair=None, n_warmup_periods=40, n_sample_periods=20,
           courant_budget=0.9, sponge=24):
    """2D 全矢量 FDTD 单频推进 + 双探针相量测量。

    返回 dict：含 phasors（两探针复振幅）、k_meas、稳定性 max|E|、几何信息。
    axis：传播轴（0=x / 1=y）；transverse 轴取 PBC 且横向均匀 ⇒ 退化 1D 传播。
    source_comp：被软源激励的 E 分量（'Ex'/'Ey'/'Ez'）。
    probe_pair：(j1,j2) 或 (i1,i2)，取决于 axis —— 沿传播轴的两条探针位置。
    """
    # 参考介电（用于 CFL 安全缩放 + 相位解缠）：取「被驱动分量」对应的 ε
    if medium.kind == "scalar":
        eps_ref = medium.eps
    elif medium.kind == "lorentz":
        eps_ref = analytic_eps(medium, omega).real
    elif medium.kind == "anisotropic":
        eps_ref = {"Ex": medium.exx, "Ey": medium.epsy, "Ez": medium.epsz}[source_comp]
    elif medium.kind == "kerr":
        eps_ref = medium.eps_lin
    else:
        eps_ref = 1.0
    n_ref = math.sqrt(max(eps_ref, 1e-12))
    k_ref = omega * n_ref
    # CFL：本征波相速 v = c/n_ref；n_ref<1（如 Drude）时相速 > c，须收紧 courant 保证稳定
    courant_used = courant_budget * min(1.0, n_ref)
    # dt 由 dl + courant 预算直接确定，再调到「T/dt 整数」⇒ 相量采样无泄漏
    dt = courant_used * dl / math.sqrt(2.0)
    nper = int(round((2.0 * math.pi / omega) / dt))     # 每周期步数（整数保证）
    dt = (2.0 * math.pi / omega) / nper                 # 重标定使 T/dt 严格整数
    # nper 取整可能使 dt 略增，循环收紧保证不超 CFL 预算
    while dt / (dl / math.sqrt(2.0)) > courant_used + 1e-9:
        nper += 1
        dt = (2.0 * math.pi / omega) / nper
    eff_courant = dt / (dl / math.sqrt(2.0))
    assert eff_courant <= courant_used + 1e-9, \
        "CFL 违例：effective courant=%.3f > %.3f" % (eff_courant, courant_used)
    n_warmup_steps = n_warmup_periods * nper
    n_samp_steps = n_sample_periods * nper

    pbc_x = (axis != 0)
    pbc_y = (axis != 1)
    medium.reset((nx, ny))

    zero = np.zeros((nx, ny))
    Ex = zero.copy(); Ey = zero.copy(); Ez = zero.copy()
    Hx = zero.copy(); Hy = zero.copy(); Hz = zero.copy()
    Dx = zero.copy(); Dy = zero.copy(); Dz = zero.copy()

    # 端吸收（沿传播轴两端的梯度导电海绵）—— 防远/近端反射回探针。
    # 关键：吸收强度须「越靠边界越强」（外侧近 PEC 处最强），否则波到 PEC 几乎未衰减而强反射。
    damp = np.ones((nx, ny))
    if axis == 0:
        for i in range(sponge):
            d = ((sponge - 1 - i) / sponge) ** 2     # 外侧(近边界)→1，内侧→0
            damp[i, :] *= math.exp(-d * 10.0)
            damp[nx - 1 - i, :] *= math.exp(-d * 10.0)
    else:
        for j in range(sponge):
            d = ((sponge - 1 - j) / sponge) ** 2
            damp[:, j] *= math.exp(-d * 10.0)
            damp[:, ny - 1 - j] *= math.exp(-d * 10.0)

    t0 = n_warmup_steps * dt                              # warmup 时间
    n_ramp = 6 * nper                                       # ramping 步数（6 周期）
    n_total = n_warmup_steps + n_samp_steps + 2
    if nsteps and nsteps > 0:
        n_total = min(n_total, nsteps)

    # 探针：probe_pair=None 时自动放置。设计要点：
    #   · 基线取 ~3λ（受域长约束上限）—— 长基线比短基线准：残余驻波相位误差在差值中
    #     被平均掉（实测 6 格基线 ~4% 误差，120 格 ~0.02%）。2π 歧义由下方「期望有符号相位」
    #     分支选择消除，故不再刻意用短基线。
    #   · 优先放在源下游且避开近场与边界海绵；下游空间不足则改上游对称放置。
    if probe_pair is None:
        ncell = nx if axis == 0 else ny                       # 传播轴格数
        trans = ny // 2 if axis == 0 else nx // 2             # 横向中心索引
        x_max_valid = ncell - sponge - 2
        x_min_valid = sponge + 2
        lam_cells = 2.0 * math.pi / max(k_ref * dl, 1e-9)     # 介质内波长（格）
        near = max(8, int(lam_cells * 0.5))                   # 源近场余量
        avail_down = x_max_valid - (i_src + near)
        if avail_down >= 24:                                  # 下游空间足够
            sep = max(20, min(int(round(3.0 * lam_cells)), avail_down - 4))
            p0 = i_src + near
        else:                                                 # 下游不足 → 上游对称
            avail_up = (i_src - near) - x_min_valid
            sep = max(20, min(int(round(3.0 * lam_cells)), max(20, avail_up - 4)))
            p0 = max(x_min_valid, i_src - near - sep)
        if axis == 0:
            probe_idx = [(p0, trans), (p0 + sep, trans)]
        else:
            probe_idx = [(trans, p0), (trans, p0 + sep)]
    else:
        if axis == 0:
            jm = ny // 2
            i1, i2 = probe_pair
            probe_idx = [(i1, jm), (i2, jm)]
        else:
            im = nx // 2
            j1, j2 = probe_pair
            probe_idx = [(im, j1), (im, j2)]

    ph_re = [0.0, 0.0]
    ph_im = [0.0, 0.0]
    n_rec = 0
    max_abs_E = 0.0

    for n in range(n_total):
        t = n * dt
        # ---- H 半步 ----
        Hx -= (dt / dl) * _diff_y_b(Ez, pbc_y)          # −∂Ez/∂y
        Hy += (dt / dl) * _diff_x_b(Ez, pbc_x)          # +∂Ez/∂x
        Hz += (dt / dl) * (_diff_y_b(Ex, pbc_y) - _diff_x_b(Ey, pbc_x))  # ∂Ex/∂y − ∂Ey/∂x
        # ---- D 全步（curl H，介质无关）----
        Dx += (dt / dl) * _diff_y(Hz, pbc_y)            # +∂Hz/∂y
        Dy += (dt / dl) * (-_diff_x(Hz, pbc_x))         # −∂Hz/∂x
        Dz += (dt / dl) * (_diff_x(Hy, pbc_x) - _diff_y(Hx, pbc_y))  # ∂Hy/∂x − ∂Hx/∂y
        # ---- 软源（注入到 D=积分场，因本模块是 D 基方案：E 每步由 D 重算，
        #     源必须先落到 D 才能在 step_E 后保留；**按当前数组名写入**）----
        s = math.cos(omega * t)
        ramp = min(1.0, t / (n_ramp * dt))
        if axis == 0:
            if source_comp == "Ex":
                Dx[i_src, :] += s * ramp
            elif source_comp == "Ey":
                Dy[i_src, :] += s * ramp
            else:
                Dz[i_src, :] += s * ramp
        else:
            if source_comp == "Ex":
                Dx[:, i_src] += s * ramp
            elif source_comp == "Ey":
                Dy[:, i_src] += s * ramp
            else:
                Dz[:, i_src] += s * ramp
        # ---- 介质：D → E ----
        Ex, Ey, Ez = medium.step_E(Dx, Dy, Dz, dt, 1.0)
        # ---- 端吸收：E/H/D 同侧全部衰减（仅衰减 E 会被 H 每步重新激发 ⇒ 反射）----
        Ex *= damp; Ey *= damp; Ez *= damp
        Hx *= damp; Hy *= damp; Hz *= damp
        Dx *= damp; Dy *= damp; Dz *= damp
        # ---- 探针相量采样（warmup 后）----
        if t >= t0:
            ph_re[0] += Ex[probe_idx[0]] if source_comp == "Ex" else (
                Ey[probe_idx[0]] if source_comp == "Ey" else Ez[probe_idx[0]]) * math.cos(omega * t)
            ph_im[0] += (Ex if source_comp == "Ex" else (Ey if source_comp == "Ey" else Ez))[probe_idx[0]] * math.sin(omega * t)
            ph_re[1] += (Ex if source_comp == "Ex" else (Ey if source_comp == "Ey" else Ez))[probe_idx[1]] * math.cos(omega * t)
            ph_im[1] += (Ex if source_comp == "Ex" else (Ey if source_comp == "Ey" else Ez))[probe_idx[1]] * math.sin(omega * t)
            n_rec += 1
            fld = Ex if source_comp == "Ex" else (Ey if source_comp == "Ey" else Ez)
            cur = max(abs(fld[i, j]) for i, j in probe_idx)
            if cur > max_abs_E:
                max_abs_E = cur

    # 复振幅（整数周期 ⇒ 无泄漏）
    amp = []
    for k in range(2):
        A = 2.0 * (ph_re[k] - 1j * ph_im[k]) / n_rec
        amp.append(A)
    d_prop = (probe_idx[1][axis] - probe_idx[0][axis]) * dl   # 探针间距（沿传播轴）
    # 参考传播常数（仅用于相位解缠分支选择，不替代测量本身）
    if medium.kind == "scalar":
        eps_ref = medium.eps
    elif medium.kind == "lorentz":
        eps_ref = analytic_eps(medium, omega).real
    elif medium.kind == "anisotropic":
        eps_ref = {"Ex": medium.exx, "Ey": medium.epsy, "Ez": medium.epsz}[source_comp]
    elif medium.kind == "kerr":
        eps_ref = medium.eps_lin
    else:
        eps_ref = 1.0
    k_ref = omega * math.sqrt(max(eps_ref, 1e-12))
    dphi = math.atan2(amp[1].imag, amp[1].real) - math.atan2(amp[0].imag, amp[0].real)
    # 解缠 + 取传播常数大小：
    #   探针在源下游（mid >= i_src，波向 +x）：物理 φ1−φ0 = −k·d_prop（负值）
    #   探针在源上游（mid <  i_src，波向 −x）：物理 φ1−φ0 = +k·d_prop（正值）
    # 旧代码用 target = +k_ref·d_prop（与下游真实相位反号）⇒ 短基线时 round 误加整圈 ⇒ k_meas 虚高 ~2×。
    # 现用「期望有符号相位」选最近 2π 分支，再取绝对值 ⇒ k_meas 恒为正传播常数大小，与 k_ref 同号。
    mid = (probe_idx[0][axis] + probe_idx[1][axis]) * 0.5
    target_signed = (-k_ref * d_prop) if (mid >= i_src) else (+k_ref * d_prop)
    dphi = dphi + 2.0 * math.pi * round((target_signed - dphi) / (2.0 * math.pi))
    k_meas = abs(dphi) / abs(d_prop) if d_prop != 0 else 0.0

    return {
        "k_meas": k_meas,
        "omega": omega,
        "dl": dl, "dt": dt, "nper": nper,
        "eff_courant": eff_courant,
        "max_abs_E": max_abs_E,
        "n_total": n_total,
        "axis": axis, "source_comp": source_comp,
        "amp": [complex(a) for a in amp],
        "d_prop": d_prop,
    }


if __name__ == "__main__":
    # 自检：标量 n=2 线性基准 —— 验证 Yee 索引 + 测量仪；不打印判据（判据在 smoke）
    print("=" * 78)
    print("dispersive 自检：标量 n=2 线性（k 应 = ω·2 = 2π/wl · 2）")
    print("=" * 78)
    wl = 2.0
    dl = wl / 40.0
    omega = 2.0 * math.pi / wl
    # 沿 x 传播的 Ez 波（transverse = y，PBC）
    r = run_2d(nx=400, ny=2, dl=dl, dt=1e-9, omega=omega, nsteps=0,
               medium=ScalarMedium(eps=4.0), axis=0, source_comp="Ez",
               i_src=200, probe_pair=None,
               n_warmup_periods=60, n_sample_periods=30)
    k_analytic = omega * math.sqrt(4.0)
    print("k_meas=%.6f  k_analytic=%.6f  rel_err=%.4f%%  max|E|=%.4f  CFL=%.3f"
          % (r["k_meas"], k_analytic,
             100.0 * (r["k_meas"] - k_analytic) / k_analytic,
             r["max_abs_E"], r["eff_courant"]))
