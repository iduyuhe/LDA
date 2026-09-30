# -*- coding: utf-8 -*-
"""LDA · T1 器件级内核 · MOSCAP（金属-氧化层-半导体）1D 自洽泊松求解。

============================================================================
为什么存在（E11-c · 电子计算征程）
----------------------------------------------------------------------------
平台已有 `drift_diffusion_1d/2d`（**两端 p-n 结**），而 ecore 的器件模型是
**三端 MOSFET**（栅氧 + 反型层 + 栅控）—— 两者**不是同一种器件**，
器件级物理**无法直接校验**电路级的解析平方根律（见
`docs/LDA_电子计算征程_E11b_接缝勘查_2026-10-01.md` §3）。

本模块补上这块：**MOSCAP 结构的一维自洽泊松解**（栅 / SiO₂ / p-Si），
给出表面势 ψ_s、半导体面电荷 Q_s、栅压 V_g 与**物理阈值电压 V_th**，
从而让「**器件级 PDE 真解 ⟷ 教科书闭式**」的交叉验证成为可能。

主权纪律（与全平台同源）：
  · C 级自主（纯 numpy；**零外部依赖**、不 import 任何 A 级商业 TCAD）；
  · LLM 不进判决路径；
  · 🔴 **T1 输出不作 ORACLE（红线）**：本模块解出的 ψ(x)/Q_s/V_th 仅为
    **候选（candidate）**，`is_oracle=False`；判决由**教科书闭式**
    （Sze 耗尽近似 / 完整 Q_s 式）定。守卫 `guard_t1_not_oracle` 单一定义在
    `lda_solver/redline.py`，本模块仅 `bind_guard` 绑定文案（不复制定义）。
  · 平台红线为**分层口径**（2026-09-11 §八§九 · 2026-09-23 逐步解锁）：
    **器件级 T1 数值内核已解锁**；**T2 工艺真值 / 工艺角 / 流片永久锁**。

物理（Sze《Physics of Semiconductor Devices》第 6 章 MOS 电容）
----------------------------------------------------------------------------
结构：金属栅 ── SiO₂(厚度 t_ox) ── p 型 Si(掺杂 N_A) ── 背接触（深体）。
- 半导体侧泊松：d²ψ/dx² = −(q/ε_si)·(p − n + N_D − N_A)
  其中 p = n_i·e^{−ψ/V_T}，n = n_i·e^{ψ/V_T}（玻尔兹曼，与 `drift_diffusion_1d` 同源）。
- 边界：界面 ψ(0)=ψ_s（**给定表面势**，本模块以 ψ_s 为自变量扫）；深体 ψ(L)=0。
- 高斯定理给出半导体面电荷（**含符号**）：**Q_s = −ε_si·E_s**
  （E_s = −dψ/dx|₀₊ 为指向体内的电场幅值）。耗尽区电离受主带负电 ⇒ **Q_s < 0**。
- 氧化层分压 ⇒ 栅压：**V_g = V_FB + ψ_s − Q_s/C_ox**（C_ox = ε_ox/t_ox）。

golden（教科书闭式 = 科学原理层公共品，**可作真值**）：
- **golden-A · 完整 Q_s 闭式**（Sze 式 6.2.15/6.2.16，含反型层与玻尔兹曼尾）：
      Q_s = sign(ψ_s)·(√2·ε_si·V_T/L_D)·F(βψ_s, n_i/N_A)
      F = √[ (e^{−βψ_s} + βψ_s − 1) + (n_i/N_A)²·(e^{βψ_s} − βψ_s − 1) ]
      L_D = √(ε_si·V_T/(q·N_A))          （p 型德拜长度）
  ⇒ PDE 应**精确收敛到它**（同物理、不同方法：闭式积分 vs 全场数值）。
- **golden-B · 教科书耗尽近似 V_th**（Sze 6.3.2，本科教材标准式）：
      φ_F = V_T·ln(N_A/n_i)·；W_dmax = √(2ε_si·2φ_F/(q·N_A))
      V_th = V_FB + 2φ_F + √(2·q·ε_si·N_A·2φ_F)/C_ox
  ⇒ PDE 的 V_th 与它相差**约 1.6%**——该差**是物理的**（完整式含反型层电荷与
     玻尔兹曼尾，耗尽近似把它们丢掉），不是数值误差。

🔴 诚实边界
- 本结构是**一维 MOS 电容**（无源/漏、无沟道长度）⇒ **天然不含短沟道效应**
  （V_th roll-off / DIBL 一个都不会出现）。要短沟道必须 2D MOS，**本平台无此能力**。
- `t_ox` / `N_A` / `V_FB` 为**公开典型量级占位**，**非 PDK 标定**；无实测锚。
- 不宣称器件性能；不报 TOPS/TOPS-W/fJ/op。
- 🔴 **EAR 744.23**：声明仅用于成熟节点 / 非先进用途半导体器件设计仿真。
"""
from __future__ import annotations

import math

import numpy as np

try:  # 包内导入
    from .drift_diffusion_1d import (  # noqa: F401
        EPS0,
        EPS_SI,
        N_I,
        Q_E,
        V_T,
        _thomas_solve,
    )
    from .redline import T1_OUTPUT_IS_ORACLE, GROUND_ANCHOR, bind_guard
except ImportError:  # 脚本直跑自检
    from drift_diffusion_1d import (  # type: ignore  # noqa: F401
        EPS0,
        EPS_SI,
        N_I,
        Q_E,
        V_T,
        _thomas_solve,
    )
    from redline import (  # type: ignore
        T1_OUTPUT_IS_ORACLE,
        GROUND_ANCHOR,
        bind_guard,
    )

# 🔴 T1 守卫（**逻辑单一定义**在 lda_solver/redline.py；本模块只绑定文案）
guard_t1_not_oracle = bind_guard("MOSCAP 数值 ψ(x)/Q_s/V_th", GROUND_ANCHOR)
_REDLINE_EXPORTS = (T1_OUTPUT_IS_ORACLE, guard_t1_not_oracle)

# ---- 结构默认值（公开典型量级占位 · 非 PDK）----
N_A_DEFAULT = 1.0e23           # 受主掺杂 (m^-3, 1e17 cm^-3) · 与 drift_diffusion_1d 同源
T_OX_DEFAULT = 4.0e-9          # 栅氧厚度 (m, 4 nm ≈ 8.63 fF/µm²)
VFB_DEFAULT = -0.60            # 平带电压 (V) · n+ 多晶硅栅/p-Si 的公开典型量级
EPS_OX_R = 3.9                 # SiO₂ 相对介电常数
EPS_OX = EPS_OX_R * EPS0       # SiO₂ 介电常数 (F/m)
# 精细网格参数（幂律网格：界面附近加密，深体放稀）
GRID_POWER = 1.4               # x_i = L·(i/N)^p
DEFAULT_DX_IF = 0.05e-9        # 界面首点间距目标 (m, 0.05 nm)
GRID_N_FLOOR = 400             # 最小网格点数
GRID_N_CEIL = 20000            # 最大网格点数（防爆）


# ---------------------------------------------------------------------------
# 网格
# ---------------------------------------------------------------------------
def moscap_grid(L_si: float, dx_if: float = DEFAULT_DX_IF,
                power: float = GRID_POWER) -> np.ndarray:
    """幂律网格 x_i = L·(i/N)^p（界面加密 · 深体贴片）。

    由目标界面首点间距 `dx_if` 反解点数：N^p = L/dx_if ⇒ N = (L/dx_if)^(1/p)。
    点数被夹在 [GRID_N_FLOOR, GRID_N_CEIL]。
    """
    r = float(L_si) / float(dx_if)
    n = int(round(r ** (1.0 / power)))
    n = max(GRID_N_FLOOR, min(GRID_N_CEIL, n))
    i = np.arange(n + 1, dtype=float)
    x = float(L_si) * (i / n) ** power
    x[0] = 0.0
    x[-1] = float(L_si)
    return x


def _pad(x: np.ndarray) -> int:
    """把非严格递增（浮点重复）的网格点合并，返回有效点数（原地去重）。"""
    keep = np.concatenate(([True], np.diff(x) > 0.0))
    if keep.all():
        return x.size
    return int(keep.sum())


# ---------------------------------------------------------------------------
# 教科书闭式 golden
# ---------------------------------------------------------------------------
def phi_f(N_A: float = N_A_DEFAULT, n_i: float = N_I, v_t: float = V_T) -> float:
    """费米势（本征能级到费米能级的电势差）：φ_F = V_T·ln(N_A/n_i)。"""
    return float(v_t) * math.log(float(N_A) / float(n_i))


def max_depletion_width(N_A: float = N_A_DEFAULT, psi_s: float | None = None,
                        two_phi_f: float | None = None,
                        eps_si: float = EPS_SI) -> float:
    """耗尽近似最大耗尽宽度 W = √(2·ε_si·ψ_s/(q·N_A))（默认取 ψ_s = 2φ_F）。"""
    psi = float(two_phi_f) if two_phi_f is not None else (
        float(psi_s) if psi_s is not None else 2.0 * phi_f(N_A))
    return math.sqrt(2.0 * eps_si * psi / (Q_E * float(N_A)))


def oxide_capacitance(t_ox: float = T_OX_DEFAULT, eps_ox: float = EPS_OX) -> float:
    """栅氧面电容 C_ox = ε_ox/t_ox (F/m²)。"""
    return float(eps_ox) / float(t_ox)


def sze_qs_closed_form(psi_s: float, N_A: float = N_A_DEFAULT, n_i: float = N_I,
                       v_t: float = V_T, eps_si: float = EPS_SI) -> float:
    """**golden-A**：Sze 完整半导体面电荷 Q_s(ψ_s) 闭式（含反型层 + 玻尔兹曼尾）。

    Q_s = −sign(ψ_s)·(√2·ε_si·V_T/L_D)·F(βψ_s)，
    F = √[(e^{−βψ_s}+βψ_s−1) + (n_i/N_A)²(e^{βψ_s}−βψ_s−1)]，L_D = √(ε_si·V_T/(q·N_A))。

    符号口径 = **物理电荷**（耗尽区电离受主带负电 ⇒ ψ_s>0 时 Q_s<0），与
    `−ε_si·E_s`（高斯定理）一致。

    这是**确定性闭合解**（对玻尔兹曼-泊松系统做一次首次积分），属科学原理层公共品，
    **可作 golden**；PDE 数值解应精确收敛到它。数值上对指数项做安全裁剪防溢出。
    """
    na = float(N_A)
    v_t = float(v_t)
    b = float(psi_s) / v_t
    e_pos = math.exp(min(b, 300.0))          # e^{βψ_s}
    e_neg = math.exp(min(-b, 300.0))         # e^{−βψ_s}
    term_p = e_neg + b - 1.0                 # 空穴（多数载流子）项
    lam2 = (float(n_i) / na) ** 2
    inner_n = e_pos - b - 1.0
    term_n = lam2 * inner_n if inner_n > 0.0 else 0.0
    f = math.sqrt(max(term_p + term_n, 0.0))
    l_d = math.sqrt(float(eps_si) * v_t / (Q_E * na))
    qs = math.sqrt(2.0) * float(eps_si) * v_t / l_d * f
    return -math.copysign(qs, b)


def moscap_vth_closed_form(N_A: float = N_A_DEFAULT, t_ox: float = T_OX_DEFAULT,
                           VFB: float = VFB_DEFAULT, n_i: float = N_I,
                           v_t: float = V_T, eps_si: float = EPS_SI,
                           eps_ox: float = EPS_OX) -> dict:
    """**golden-B**：教科书耗尽近似阈值电压闭式（Sze §6.3 / 本科教材标准式）。

    V_th = V_FB + 2φ_F + √(2·q·ε_si·N_A·2φ_F)/C_ox。
    """
    pf = phi_f(N_A, n_i, v_t)
    two_pf = 2.0 * pf
    w_dmax = max_depletion_width(N_A, two_phi_f=two_pf, eps_si=eps_si)
    q_dep = math.sqrt(2.0 * Q_E * float(eps_si) * float(N_A) * two_pf)
    c_ox = oxide_capacitance(t_ox, eps_ox)
    vth = float(VFB) + two_pf + q_dep / c_ox
    return {
        "V_th": float(vth),
        "phi_f": float(pf),
        "two_phi_f": float(two_pf),
        "W_dmax": float(w_dmax),
        "Q_dep": float(q_dep),
        "C_ox": float(c_ox),
        "V_FB": float(VFB),
        "N_A": float(N_A),
        "t_ox": float(t_ox),
        "provenance": "design_rule_anchor_textbook_depletion",
    }


# ---------------------------------------------------------------------------
# T1 数值内核：MOSCAP 自洽泊松
# ---------------------------------------------------------------------------
def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    """梯形积分（自实现，避免 numpy 版本间 `trapz`/`trapezoid` 差异）。"""
    return float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(x)))


def _newton_psi(psi_s: float, psi_init: np.ndarray, *, m: int, na: float,
                phi_f_v: float, a_sub: np.ndarray, c_sup: np.ndarray,
                b_diag: np.ndarray, n_i: float, v_t: float, eps_si: float,
                max_iter: int, resid_tol: float, step_cap: float):
    """非均匀网格上的玻尔兹曼-泊松阻尼牛顿（给定界面 ψ_s 的 Dirichlet 问题）。

    🔴 载流子口径（**本轮血案 · 物理**）：Sze 的 ψ 是**相对体内本征能级的带弯**
    （体内 ψ=0 即电中性），故
        n = n_i·e^{(ψ−φ_F)/V_T}，  p = n_i·e^{(φ_F−ψ)/V_T}
    漏掉 φ_F 偏移（写成 p = n_i·e^{−ψ/V_T}）会使中性区被判成密度 −N_A 的负电荷
    ⇒ 泊松解整体偏移（实测 V_th 偏大 170×，且中性区反号）。

    🔴 三对角装配索引（**本轮血案 · 数值**）：行 k 对应内部点 i=k+1，未知量 ψ_{k'+1}
    落在列 k'。故 `_thomas_solve(A_diag, A_sub, A_sup, d)` 需要
      A_sub[j] = A[j+1][j] = a_sub[j+1] ⇒ 传 `a_sub[1:]`
      A_sup[j] = A[j][j+1] = c_sup[j]   ⇒ 传 `c_sup[:-1]`
    传 `a_sub[:-1]`（看似对称）会**下对角整体错位一格** ⇒ 解恒错、牛顿必不收敛。
    """
    psi = psi_init.copy()
    psi[0] = float(psi_s)
    psi[-1] = 0.0
    converged = False
    n_iter = 0
    for n_iter in range(1, max_iter + 1):
        xi_v = (psi - phi_f_v) / v_t
        n_ = n_i * np.exp(np.clip(xi_v, -300.0, 300.0))
        p_ = n_i * np.exp(np.clip(-xi_v, -300.0, 300.0))
        rho = p_ - n_ - na
        lap = np.zeros(m)
        lap[1:-1] = a_sub * psi[:-2] + b_diag * psi[1:-1] + c_sup * psi[2:]
        resid = lap + (Q_E / eps_si) * rho
        jac = b_diag - (Q_E / eps_si) * (n_[1:-1] + p_[1:-1]) / v_t
        delta = _thomas_solve(jac, a_sub[1:].copy(), c_sup[:-1].copy(),
                              resid[1:-1])
        delta = np.clip(delta, -step_cap, step_cap)
        psi[1:-1] = psi[1:-1] - delta
        if float(np.max(np.abs(delta))) < resid_tol:
            converged = True
            break
    return psi, converged, n_iter


def solve_moscap_1d(psi_s: float, N_A: float = N_A_DEFAULT,
                    t_ox: float = T_OX_DEFAULT, VFB: float = VFB_DEFAULT,
                    dx_if: float = DEFAULT_DX_IF, n_i: float = N_I,
                    v_t: float = V_T, eps_si: float = EPS_SI,
                    eps_ox: float = EPS_OX, l_si_factor: float = 10.0,
                    max_iter: int = 300, resid_tol: float = 1e-9,
                    step_cap: float = 0.05, n_continuation: int = 8) -> dict:
    """MOSCAP 1D 自洽泊松（T1 内核候选）：给定**表面势 ψ_s**，解出 ψ(x) 与 Q_s。

    做法：以 ψ_s 为自变量（比"给定 V_g 求 ψ_s"稳健——后者需外层根求解）。
    半导体侧（0 ≤ x ≤ L_si）解玻尔兹曼-泊松，界面 Dirichlet ψ(0)=ψ_s，
    深体 Dirichlet ψ(L_si)=0（L_si ≫ W_dmax ⇒ 与诺伊曼无通量等价）。
    非均匀（幂律）网格 + 有限体积离散 + 阻尼牛顿（复用 `_thomas_solve`）。
    🔴 **continuation**：强反型下界面电子浓度可达 1e30 m⁻³，直接跳到 ψ_s=2φ_F
    牛顿必发散 ⇒ 从小 ψ_s 分 8 步升温、前一步解作下一步初值。

    返回 dict：
      x / psi / n / p            场分布
      psi_s / E_s / Q_s          表面势 / 界面电场（指向体内）· 半导体面电荷
      V_g                        由 V_g = V_FB + ψ_s + Q_s/C_ox 得到
      Q_s_body                   ∫(p−n+N_D−N_A)dx·q（**独立路径**核 Q_s，自检用）
      converged / n_iter / provenance / is_oracle(False)
    """
    na = float(N_A)
    l_si = max(float(l_si_factor) * max_depletion_width(na), 1.0e-6)
    x = moscap_grid(l_si, dx_if)
    n_eff = _pad(x)
    if n_eff != x.size:
        x = x[:n_eff]
    m = x.size
    h = np.diff(x)
    d_mid = 0.5 * (h[:-1] + h[1:])                  # 长度 m-2（内部点）
    a_sub = 1.0 / (h[:-1] * d_mid)                  # 内部点 i=k+1 的 ψ_k 系数
    c_sup = 1.0 / (h[1:] * d_mid)                   # 内部点 i=k+1 的 ψ_{k+2} 系数
    b_diag = -(a_sub + c_sup)
    phi_f_v = phi_f(na, n_i, v_t)                   # φ_F：ψ 的体内电中性参考

    psi = None
    converged = False
    n_iter = 0
    total_iter = 0
    for frac in np.linspace(1.0 / n_continuation, 1.0, n_continuation):
        target = float(psi_s) * float(frac)
        if psi is None:
            w0 = (max_depletion_width(na, psi_s=abs(target))
                  if target != 0.0 else 1.0e-8)
            xi = np.clip(1.0 - x / max(2.0 * w0, 1.0e-9), 0.0, 1.0)
            psi = target * xi ** 2
        psi, converged, n_iter = _newton_psi(
            target, psi, m=m, na=na, phi_f_v=phi_f_v, a_sub=a_sub,
            c_sup=c_sup, b_diag=b_diag, n_i=n_i, v_t=v_t, eps_si=eps_si,
            max_iter=max_iter, resid_tol=resid_tol, step_cap=step_cap)
        total_iter += n_iter
        if not converged:
            break

    xi_v = (psi - phi_f_v) / v_t
    n_ = n_i * np.exp(np.clip(xi_v, -300.0, 300.0))
    p_ = n_i * np.exp(np.clip(-xi_v, -300.0, 300.0))
    # 界面电场（指向体内）：E_s = −dψ/dx|₀₊，单侧二阶差分
    h0, h1 = float(h[0]), float(h[1])
    dpsi0 = (-(2.0 * h0 + h1) / (h0 * (h0 + h1)) * psi[0]
             + (h0 + h1) / (h0 * h1) * psi[1]
             - h0 / (h1 * (h0 + h1)) * psi[2])
    e_s = -float(dpsi0)
    q_s = -eps_si * e_s                                 # 高斯定理（含符号：耗尽为负）
    q_body = Q_E * _trapz(p_ - n_ - na, x)              # 独立路径（自检用）
    c_ox = oxide_capacitance(t_ox, eps_ox)
    v_g = float(VFB) + float(psi_s) - q_s / c_ox
    return {
        "x": x, "psi": psi, "n": n_, "p": p_,
        "psi_s": float(psi_s), "E_s": e_s, "Q_s": float(q_s),
        "Q_s_body": float(q_body),
        "V_g": float(v_g), "C_ox": float(c_ox),
        "N_A": na, "t_ox": float(t_ox), "V_FB": float(VFB),
        "L_si": float(l_si), "dx_if": float(dx_if), "n_grid": int(m),
        "converged": bool(converged), "n_iter": int(total_iter),
        "provenance": "self_authored_t1_candidate",
        "is_oracle": False,
    }


def moscap_vth_pde(N_A: float = N_A_DEFAULT, t_ox: float = T_OX_DEFAULT,
                   VFB: float = VFB_DEFAULT, dx_if: float = DEFAULT_DX_IF,
                   **kw) -> dict:
    """物理阈值电压 **候选**（T1 内核）：取强反型判据 ψ_s = 2φ_F，返回 V_g 即 V_th。

    🔴 `is_oracle=False`——它只是 candidate；真值判据仍是教科书闭式
    （`moscap_vth_closed_form`）。
    """
    pf = phi_f(N_A, N_I, kw.get("v_t", V_T))
    sol = solve_moscap_1d(2.0 * pf, N_A=N_A, t_ox=t_ox, VFB=VFB,
                          dx_if=dx_if, **kw)
    out = dict(sol)
    out["V_th"] = sol["V_g"]
    out["psi_s_vth"] = 2.0 * pf
    return out


def moscap_cv_sweep(psi_s_list, N_A: float = N_A_DEFAULT,
                    t_ox: float = T_OX_DEFAULT, VFB: float = VFB_DEFAULT,
                    dx_if: float = DEFAULT_DX_IF, **kw) -> list:
    """低频 C–V 扫描点：对每个 ψ_s 解场后，用数值微分给 C_s 与串联总电容。

    返回 [{"psi_s", "V_g", "Q_s", "C_s", "C_total"}, ...]（按传入顺序）。
    """
    pts = []
    for ps in psi_s_list:
        pts.append(solve_moscap_1d(ps, N_A=N_A, t_ox=t_ox, VFB=VFB,
                                   dx_if=dx_if, **kw))
    c_ox = oxide_capacitance(t_ox)
    out = []
    for k, s in enumerate(pts):
        cs = None
        if 0 < k < len(pts) - 1:
            dq = pts[k + 1]["Q_s"] - pts[k - 1]["Q_s"]
            dp = pts[k + 1]["psi_s"] - pts[k - 1]["psi_s"]
            cs = dq / dp if dp != 0.0 else None
        c_tot = (c_ox * cs / (c_ox + cs)) if (cs is not None and cs > 0.0) else None
        out.append({"psi_s": s["psi_s"], "V_g": s["V_g"], "Q_s": s["Q_s"],
                    "C_s": cs, "C_total": c_tot})
    return out


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = True) -> bool:
    """模型层自检：闭式对拍 · 网格收敛 · 高斯-体电荷一致 · 物理趋势 · 守卫。"""
    msgs = []

    def chk(name, cond, _detail=""):
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True
    pf = phi_f()
    two_pf = 2.0 * pf

    # ① Q_s(PDE) vs golden-A（Sze 完整闭式）——应精确（同物理、异方法）
    s = solve_moscap_1d(two_pf)
    q_gold = sze_qs_closed_form(two_pf)
    rel = abs(s["Q_s"] - q_gold) / abs(q_gold)
    ok &= chk("① Q_s(PDE) ≡ golden-A 完整闭式（rel < 1%）", rel < 0.01,
              "rel=%.4f%% · PDE=%.6e · gold=%.6e" % (rel * 100, s["Q_s"], q_gold))

    # ② 高斯定理 ↔ 体电荷积分（两条独立路径）
    rel_b = abs(s["Q_s_body"] - s["Q_s"]) / abs(s["Q_s"])
    ok &= chk("② 高斯定理 ≡ 体电荷积分（rel < 0.5%）", rel_b < 0.005,
              "rel=%.4f%%" % (rel_b * 100))

    # ③ **网格独立性**：五档网格下 Q_s 散布 < 0.01%（解已与网格无关）
    qs_seq = [solve_moscap_1d(two_pf, dx_if=d)["Q_s"]
              for d in (0.4e-9, 0.2e-9, 0.1e-9, 0.05e-9, 0.025e-9)]
    spread = (max(qs_seq) - min(qs_seq)) / abs(q_gold)
    ok &= chk("③ 网格独立性：五档网格 Q_s 散布 < 0.01%", spread < 1e-4,
              "spread=%.5f%% · Q_s=%.6e" % (spread * 100, qs_seq[0]))

    # ④ V_th(PDE) vs golden-B（教科书耗尽式）——差应为物理差（~2% 量级）
    g = moscap_vth_closed_form()
    v = moscap_vth_pde()
    dv = abs(v["V_th"] - g["V_th"]) / abs(g["V_th"])
    ok &= chk("④ V_th(PDE) 与教科书闭式同量级（rel < 5%）", dv < 0.05,
              "PDE=%.4f V · gold=%.4f V · rel=%.3f%%" % (v["V_th"], g["V_th"], dv * 100))

    # ⑤ 物理趋势：t_ox ↑ ⇒ 体电荷分压 Q_dep/C_ox ↑ ⇒ V_th ↑（厚氧更难反型）
    va = moscap_vth_closed_form(t_ox=2e-9)["V_th"]
    vb = moscap_vth_closed_form(t_ox=8e-9)["V_th"]
    ok &= chk("⑤ t_ox ↑ ⇒ 体电荷分压 ↑ ⇒ V_th ↑（厚氧更难反型）", vb > va,
              "2nm=%.4f V < 8nm=%.4f V" % (va, vb))

    # ⑥ N_A ↑ ⇒ Q_dep ↑
    q1 = moscap_vth_closed_form(N_A=5e22)["Q_dep"]
    q2 = moscap_vth_closed_form(N_A=2e23)["Q_dep"]
    ok &= chk("⑥ N_A ↑ ⇒ Q_dep ↑", q2 > q1, "%.4e > %.4e" % (q2, q1))

    # ⑦ 强反型（ψ_s=2.5φ_F）处完整式 ≫ 纯耗尽式（反型层电荷开始主导）
    ps_inv = 2.5 * pf
    q_g_i = sze_qs_closed_form(ps_inv)
    q_d_i = math.sqrt(2.0 * Q_E * EPS_SI * N_A_DEFAULT * ps_inv)
    ok &= chk("⑦ ψ_s=2.5φ_F 处 |完整式| ≫ |纯耗尽式|（反型层贡献）",
              abs(q_g_i) > 2.0 * abs(q_d_i),
              "完整=%.4e · 耗尽=%.4e · 比=%.2f" %
              (q_g_i, q_d_i, abs(q_g_i) / abs(q_d_i)))

    # ⑧ 🔴 T1 不作 ORACLE：正常通过；force_oracle 必 raise
    guard_ok = guard_t1_not_oracle(s) is True
    raised = False
    try:
        guard_t1_not_oracle(s, force_oracle=True)
    except RuntimeError:
        raised = True
    ok &= chk("⑧ guard_t1_not_oracle：正常通过 + force_oracle 必 raise",
              guard_ok and raised, "is_oracle=%s" % s["is_oracle"])

    if verbose:
        for name, good in msgs:
            print("  [%s] %s" % ("PASS" if good else "FAIL", name))
        print("  selfcheck %d/%d" % (sum(1 for _, g_ in msgs if g_), len(msgs)))
    return bool(ok)


MOSCAP_DISCLOSURE: dict = {
    "level": "器件级 T1 数值内核（1D MOSCAP 自洽泊松）· 本模块**主动限定在 MOS 电容结构**"
             "（设计取舍，非红线要求）；平台红线为**分层口径**（器件级 T1 内核已解锁 · "
             "T2 工艺真值/工艺角/流片永久锁）。",
    "no_oracle": "🔴 T1 输出不作 ORACLE：ψ(x)/Q_s/V_th 皆 `is_oracle=False`（候选）；"
                 "真值判据为教科书闭式（Sze 完整 Q_s 式 / 耗尽近似 V_th 式）。",
    "no_short_channel": "1D MOS 电容**无源/漏、无沟道长度** ⇒ **天然不含短沟道效应**"
                        "（V_th roll-off / DIBL 均不出现）；平台无 2D MOS 能力。",
    "params_are_typical": "t_ox / N_A / V_FB 为**公开典型量级占位**（非 PDK 标定）；无实测锚。",
    "no_capability_claim": "不做器件性能宣称；不报 TOPS/TOPS-W/fJ/op。",
}


if __name__ == "__main__":
    print("=== MOSCAP 1D 关键量 ===")
    cl = moscap_vth_closed_form()
    print("  φ_F=%.4f V · 2φ_F=%.4f V · W_dmax=%.2f nm" %
          (cl["phi_f"], cl["two_phi_f"], cl["W_dmax"] * 1e9))
    print("  C_ox=%.4e F/m² · Q_dep=%.4e C/m² · V_th(教科书)=%.4f V" %
          (cl["C_ox"], cl["Q_dep"], cl["V_th"]))
    pv = moscap_vth_pde()
    print("  V_th(PDE 候选)=%.4f V · converged=%s · n_grid=%d" %
          (pv["V_th"], pv["converged"], pv["n_grid"]))
    print("=== 自检 ===")
    run_selfchecks(verbose=True)
