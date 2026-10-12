# -*- coding: utf-8 -*-
"""验证适配器 · 分片 4/6（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

覆盖原文件 L3218..L4636（110 个顶层定义）。正文**逐字节**取自原文，不重排、不重格式化。
🔴 装配顺序由 `verification_adapters.py` 的 import 次序决定，勿单独调整。
"""

from __future__ import annotations

from ._adapter_core import (
    _get_batch_b, _get_batch_b2, _get_batch_b28, _get_batch_b29, _get_batch_b3, _get_batch_b4,
    _get_batch_b5, _get_batch_b6, _get_batch_b7, _get_batch_b8, _register_candidate,
    _get_batch_b30, _get_batch_b31, _get_batch_b32, _get_batch_b33, _get_batch_b34,
    _get_batch_b35, _get_batch_b36,
    _get_batch_b37,
    _get_batch_b38,
    _get_batch_b39,
    _get_batch_b40,
    _get_batch_b41,
    _get_batch_b42,
    _get_batch_b43,
    _get_batch_b44,
    _get_batch_b45,
    _get_batch_b46,
    _get_batch_b47,
    _get_qs_m3c_numeric,
    _get_j1_numeric,
)

from typing import (
    Any,
)

from .verification_spec import (
    VerificationSpec,
)

@_register_candidate(
    "sine_integral_rk4_446",
    "正弦积分 Si 由四阶 RK4 积分定义 ODE y'=sin x/x（自解析 Taylor 级数启动）导出")
def _b446_sine_integral_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B446 独立候选：Si(4.0)（RK4 积分定义 ODE）。

    golden=scipy.special.sici（精确 oracle）；cand=RK4 积分 y'=sin x/x，自 x0=1e-3 的
    解析 Taylor 级数启动（N=64）。残差=RK4 截断误差（O(h⁴)，实测比值 16.18/16.05/16.01）。
    余量 850×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b446(float(p["X"])))

@_register_candidate(
    "sine_integral_rk4_447",
    "正弦积分 Si 由四阶 RK4 积分定义 ODE y'=sin x/x（自解析级数启动）导出")
def _b447_sine_integral_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B447 独立候选：Si(12.0)（大 x 档，误差累积于整段）。

    golden=scipy.special.sici；cand=RK4 积分 y'=sin x/x（N=256）。
    残差=RK4 截断误差（O(h⁴)）。余量 759×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b447(float(p["X"])))

@_register_candidate(
    "cosine_integral_rk4_448",
    "余弦积分 Ci 由四阶 RK4 积分定义 ODE y'=cos x/x（起点 0.1 避 1/t 奇性阶退化）导出")
def _b448_cosine_integral_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B448 独立候选：Ci(1.0)（RK4 积分定义 ODE，起点 0.1）。

    golden=scipy.special.sici（精确 oracle）；cand=RK4 积分 y'=cos x/x，自 x0=0.1 的解析
    级数启动（N=512）。⚠️ 起点若取 1e-3 则 1/t 奇性使收敛阶退化为 ~3（B-28 血案 2）。
    残差=RK4 截断误差（O(h⁴)）。余量 503×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b448(float(p["X"])))

@_register_candidate(
    "cosine_integral_rk4_449",
    "余弦积分 Ci 由四阶 RK4 积分定义 ODE y'=cos x/x（起点 0.1 避 1/t 奇性阶退化）导出")
def _b449_cosine_integral_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B449 独立候选：Ci(2.0)（RK4 积分定义 ODE，起点 0.1）。

    golden=scipy.special.sici；cand=RK4 积分 y'=cos x/x（N=1024）。
    残差=RK4 截断误差（O(h⁴)）。余量 405×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b449(float(p["X"])))

@_register_candidate(
    "hyperbolic_sine_integral_rk4_450",
    "双曲正弦积分 Shi 由四阶 RK4 积分定义 ODE y'=sinh x/x（自解析 Taylor 级数启动）导出")
def _b450_hyperbolic_sine_integral_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B450 独立候选：Shi(2.0)（RK4 积分定义 ODE）。

    golden=scipy.special.shichi（精确 oracle）；cand=RK4 积分 y'=sinh x/x，自 x0=1e-3 的
    解析级数启动（N=64）。残差=RK4 截断误差（O(h⁴)）。余量 486×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b450(float(p["X"])))

@_register_candidate(
    "hyperbolic_cosine_integral_rk4_451",
    "双曲余弦积分 Chi 由四阶 RK4 积分定义 ODE y'=cosh x/x（起点 0.1 避 1/t 奇性阶退化）导出")
def _b451_hyperbolic_cosine_integral_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B451 独立候选：Chi(2.0)（RK4 积分定义 ODE，起点 0.1）。

    golden=scipy.special.shichi；cand=RK4 积分 y'=cosh x/x（N=1024）。
    ⚠️ 起点若取 1e-3 则 1/t 奇性使收敛阶退化（B-28 血案 2）。
    残差=RK4 截断误差（O(h⁴)）。余量 405×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b451(float(p["X"])))

@_register_candidate(
    "rc_driver_step_rk4_452",
    "驱动器一阶 RC 阶跃响应由四阶 RK4 积分定义 ODE dv/dt=(V_dd−v)/τ（自 v(0)=0）导出")
def _b452_rc_driver_step_rk4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B452 独立候选：驱动器 RC 阶跃 v(4τ)（RK4 积分定义 ODE）。

    golden=解析闭式 v(t)=V_dd·(1−e^{−t/τ})（Kirchhoff 一阶电路瞬态，教科书物理定律）；
    cand=四阶经典 RK4 直接积分 dv/dt=(V_dd−v)/τ（不解析求解、不调任何指数闭式，N=256）。
    残差=RK4 截断误差（O(h⁴)，实测比值 16.86/16.42/16.21，MONO）。余量 1356×；零商业依赖。
    ⚠️ 同源体检：与 B33 共享「一阶线性 RC 这一 ODE 形式」，但被测标量（阶跃电压值 vs
    f3dB_Hz）、物理构型（驱动器 τ=20ps 驱动 MZI 相移臂 vs 结电容 C=εA/d 配 R=50Ω）、
    数值格式（四阶 RK4 直接积分 vs 梯形法 2 阶 + τ 最小二乘拟合）三者均不同 ⇒ 非重复计数。"""
    p = spec.params
    m = _get_batch_b29()
    return float(m.cand_b452(float(p["t_s"]), float(p["tau_s"]), float(p["v_dd"])))

@_register_candidate(
    "slab_te0_neff_exact",
    "严格横向谐振超越方程二分求根 n_eff（Marcatili 解析近似 vs 数值超越方程，方法学不同源）")
def _b34_slab_neff_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B34 独立候选：条形介质波导 TE0 n_eff（Marcatili 近似 vs 超越方程二分）。

    golden = Marcatili 1969 等效宽度近似（w_eff=t+2d, d=1/(k0√(n_f²−n_c²))）；
    cand   = 严格横向谐振超越方程 tan(κt/2)=γ/κ 二分求根（同一物理定律的
             两种算法，方法学不同源）。

    基线（默认参数）残差 2.46e-3（tol=0.01 的 ~4× 余量，≫1e-12 噪声地板）。
    判据 D 不适用（解析超越方程二分无离散参数，同 B9 闭式互证先例）。
    反向 t×1.1 ⇒ 候选 3.304 vs golden 3.273，|Δ|≈0.031 > tol 必 FAIL。
    """
    p = spec.params
    m = _get_batch_b()
    return float(m.exact_slab_neff(
        float(p["n_f"]), float(p["n_c"]), float(p["t"]), float(p["wl"])))

@_register_candidate(
    "rect_wg_te10_fd",
    "1D Dirichlet 盒 FD 本征值取基模（与 B12/B22 同源 TL 本征核，判据 D 真数值收敛）")
def _b36_rect_te10_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B36 独立候选：矩形波导 TE10 截止频率（c/(2a) 闭式 vs 1D FD 本征基模）。

    golden = c/(2a)；cand = 1D Dirichlet 盒（x∈[0,a]）FD 本征取最弱模（w[-1]）
             ⇒ f_c = c·k/(2π)。复用 B12/B22 已验证 FD 本征核（scipy eigh，
             w[-mode] 取最靠近 0 的最小模，非最高模）。
    N=400 残差 ~1.7e-5 GHz（tol=0.01GHz 的 ~590× 余量）；判据 D 由 B12/B22 已证。
    反向 a×1.1 ⇒ 候选 5.96 vs golden 6.557 GHz，|Δ|≈0.60GHz ≫ tol 必 FAIL。
    """
    p = spec.params
    m = _get_batch_b()
    return float(m.fd1d_rect_te10_fc(float(p["a"])))

@_register_candidate(
    "rect_wg_te20_fd",
    "1D Dirichlet 盒 FD 本征值取第二模（与 B12/B22 同源 TL 本征核）")
def _b37_rect_te20_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B37 独立候选：矩形波导 TE20 截止频率（c/a 闭式 vs 1D FD 本征第二模）。

    golden = c/a（第二模，k=2π/a）；cand = 1D FD 本征取第二最弱模（w[-2]）。
    N=400 残差 ~1.3e-4 GHz（tol=0.1GHz 的 ~770× 余量）；判据 D 由 B12/B22 已证。
    反向 a×1.1 ⇒ 候选 11.92 vs golden 13.11 GHz，|Δ|≈1.19GHz ≫ tol 必 FAIL。
    """
    p = spec.params
    m = _get_batch_b()
    return float(m.fd1d_rect_te20_fc(float(p["a"])))

@_register_candidate(
    "rect_wg_te11_fd",
    "2D Dirichlet 盒 FD 本征值取最弱模（与 B12/B22 同源 FD 本征核，判据 D 真数值收敛）")
def _b40_rect_te11_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B40 独立候选：矩形波导 TE11 截止频率（解析闭式 vs 2D FD 本征）。

    golden = c/(2π)√((π/a)²+(π/b)²)；cand = 2D Dirichlet 盒（x∈[0,a], y∈[0,b]）
             FD 本征取最弱模（w[-1]）。网格 60×40 残差 ~1.6e-3 GHz（tol=0.1GHz
             的 ~62× 余量）；判据 D 由 B12/B22 已证。反向 a×1.1 ⇒ 候选 15.91 vs
             golden 16.15 GHz，|Δ|≈0.24GHz ≫ tol 必 FAIL。
    """
    p = spec.params
    m = _get_batch_b()
    return float(m.fd2d_rect_te11_fc(float(p["a"]), float(p["b"])))

@_register_candidate(
    "fp_cavity_fd",
    "1D Dirichlet 腔 FD 本征取第 m 腔模（与 B12/B22 同源 FD 本征核）")
def _b41_fp_cavity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B41 独立候选：Fabry-Pérot 1D 腔谐振波长（2nL/m 闭式 vs 1D FD 腔模本征）。

    golden = 2nL/m；cand = 1D Dirichlet 腔（L 内均匀 n，两端 Dirichlet 壁）FD
             本征取第 m 最弱模 ⇒ λ0 = 2πn/k。N=400 残差 ~1.8e-7 m（tol=1e-3 m
             的 ~5500× 余量）；判据 D 由 B12/B22 已证。反向 L×1.1 ⇒ 候选 76.56
             vs golden 69.6 mm，|Δ|≈6.96mm ≫ tol 必 FAIL。
    """
    p = spec.params
    m = _get_batch_b()
    return float(m.fd1d_cavity_lambda(
        float(p["n"]), float(p["L"]), int(p.get("m", 1))))

@_register_candidate(
    "qmw_infinite_well_e1_cand",
    "1D FD 薛定谔哈密顿本征值基态（无限深势阱闭式 ℏ²π²/2mL² 方法学不同源，判据 D 真数值收敛）")
def _b42_qmw_e1_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B42 独立候选：一维无限深方势阱基态 E1（ℏ²π²/2mL² 闭式 vs 1D FD 本征基态）。"""
    p = spec.params
    m = _get_batch_b2()
    return float(m.qmw_infinite_well_fd(float(p["L"]), 600, float(p["m"]), 1))

@_register_candidate(
    "qmw_infinite_well_e2_cand",
    "1D FD 薛定谔哈密顿本征值第2模（无限深势阱闭式 4E1 方法学不同源）")
def _b43_qmw_e2_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    return float(m.qmw_infinite_well_fd(float(p["L"]), 600, float(p["m"]), 2))

@_register_candidate(
    "qmw_infinite_well_e3_cand",
    "1D FD 薛定谔哈密顿本征值第3模（无限深势阱闭式 9E1 方法学不同源）")
def _b44_qmw_e3_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    return float(m.qmw_infinite_well_fd(float(p["L"]), 600, float(p["m"]), 3))

@_register_candidate(
    "qm_ho_e0_cand",
    "1D FD 谐振子哈密顿本征值基态（½ℏω 闭式方法学不同源，判据 D 真数值收敛）")
def _b45_qm_ho_e0_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    # 谐振子能级仅依赖 ℏω（m 为 FD 网格离散参数，取电子质量固定）。
    return float(m.qm_ho_fd_n(float(p["hbar_omega"]), 9.1093837015e-31, 0))

@_register_candidate(
    "qm_ho_e1_cand",
    "1D FD 谐振子哈密顿本征值第2模（1.5ℏω 闭式方法学不同源）")
def _b46_qm_ho_e1_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    return float(m.qm_ho_fd_n(float(p["hbar_omega"]), 9.1093837015e-31, 1))

@_register_candidate(
    "qm_ho_e2_cand",
    "1D FD 谐振子哈密顿本征值第3模（2.5ℏω 闭式方法学不同源）")
def _b47_qm_ho_e2_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    return float(m.qm_ho_fd_n(float(p["hbar_omega"]), 9.1093837015e-31, 2))

@_register_candidate(
    "qm_finwell_e0_cand",
    "1D FD 薛定谔哈密顿本征值基态（有限深势阱超越方程二分方法学不同源）")
def _b48_qm_finwell_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    # L_box 为 FD 离散盒长（内部常量，非物理参数）；V0/a/m 为 SI/J 输入。
    return float(m.qm_finwell_fd(
        float(p["V0"]), float(p["a"]), float(p["m"]), 1.0e-8))

@_register_candidate(
    "barrier_transmit_cand",
    "1D FD 中心匹配双基 Numerov 散射求 T（方势垒双曲闭式方法学不同源，判据 D 真数值收敛）")
def _b49_barrier_transmit_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    # E/V0/a/m 均为 SI/J 输入（default_params 已为焦耳）。
    return float(m.barrier_transmit_fd(
        float(p["E"]), float(p["V0"]), float(p["a"]), float(p["m"])))

@_register_candidate(
    "rect_wg_te30_cand",
    "1D Dirichlet 盒 FD 本征值取第三模（TE30 3c/(2a) 闭式方法学不同源）")
def _b50_rect_te30_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    return float(m.rect_wg_te30_fc(float(p["a"])))

@_register_candidate(
    "rect_wg_te40_cand",
    "1D Dirichlet 盒 FD 本征值取第四模（TE40 2c/a 闭式方法学不同源）")
def _b51_rect_te40_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b2()
    return float(m.rect_wg_te40_fc(float(p["a"])))

@_register_candidate(
    "qm_finwell_e1_cand",
    "1D FD 薛定谔哈密顿本征值第2模（有限深势阱第1激发态超越方程二分方法学不同源）")
def _b52_finwell_e1_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qm_finwell_fd_state(
        float(p["V0"]), float(p["a"]), float(p["m"]), 2.0e-8, 1000, 1))

@_register_candidate(
    "qm_finwell_e2_cand",
    "1D FD 薛定谔哈密顿本征值第3模（有限深势阱第2激发态超越方程二分方法学不同源）")
def _b53_finwell_e2_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qm_finwell_fd_state(
        float(p["V0"]), float(p["a"]), float(p["m"]), 2.0e-8, 1000, 2))

@_register_candidate(
    "qmw_infinite_well_e4_cand",
    "1D FD 薛定谔哈密顿本征值第4模（无限深势阱 E4=16E1 闭式方法学不同源）")
def _b54_qmw_e4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qmw_infinite_well_fd(float(p["L"]), 600, float(p["m"]), 4))

@_register_candidate(
    "qmw_infinite_well_e5_cand",
    "1D FD 薛定谔哈密顿本征值第5模（无限深势阱 E5=25E1 闭式方法学不同源）")
def _b55_qmw_e5_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qmw_infinite_well_fd(float(p["L"]), 600, float(p["m"]), 5))

@_register_candidate(
    "qm_ho_e3_cand",
    "1D FD 谐振子哈密顿本征值第4模（E3=3.5ℏω 闭式方法学不同源）")
def _b56_qm_ho_e3_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qm_ho_fd_n(float(p["hbar_omega"]), 9.1093837015e-31, 3))

@_register_candidate(
    "qm_ho_e4_cand",
    "1D FD 谐振子哈密顿本征值第5模（E4=4.5ℏω 闭式方法学不同源）")
def _b57_qm_ho_e4_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qm_ho_fd_n(float(p["hbar_omega"]), 9.1093837015e-31, 4))

@_register_candidate(
    "qm_cubic3d_e0_cand",
    "三维 = 三独立 1D FD 基态之和（三维立方无限阱基态 3E1 闭式方法学不同源）")
def _b58_cubic3d_e0_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.qm_cubic3d_fd(float(p["L"]), 600, float(p["m"])))

@_register_candidate(
    "poschl_teller_e0_cand",
    "1D FD 薛定谔哈密顿本征值基态（Pöschl-Teller 精确谱方法学不同源）")
def _b59_poschl_e0_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.poschl_teller_fd(
        float(p["V0"]), float(p["alpha"]), float(p["m"]), 3.0e-8, 6000, 0))

@_register_candidate(
    "poschl_teller_e1_cand",
    "1D FD 薛定谔哈密顿本征值第2模（Pöschl-Teller 第1激发态精确谱方法学不同源）")
def _b60_poschl_e1_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.poschl_teller_fd(
        float(p["V0"]), float(p["alpha"]), float(p["m"]), 3.0e-8, 6000, 1))

@_register_candidate(
    "rect_wg_tm11_cand",
    "x/y 两方向 1D Dirichlet 盒 FD 本征乘积 kc²=kx²+ky²（TM11 闭式方法学不同源）")
def _b61_rect_tm11_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.rect_wg_tm_fd(float(p["a"]), float(p["b"]), 600, 600, 1, 1))

@_register_candidate(
    "rect_wg_tm21_cand",
    "x/y 两方向 1D Dirichlet 盒 FD 本征乘积 kc²=kx²+ky²（TM21 闭式方法学不同源）")
def _b62_rect_tm21_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.rect_wg_tm_fd(float(p["a"]), float(p["b"]), 600, 600, 2, 1))

@_register_candidate(
    "circ_wg_te11_cand",
    "径向场方程直接数值积分 + 边界根搜索测 X11（圆波导 TE11 截止闭式方法学不同源）")
def _b63_circ_te11_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.circ_wg_te11_fd(float(p["a"])))

@_register_candidate(
    "bragg_lambda_cand",
    "单周期转移矩阵迹 argmin 定位阻带中心 λB（Bragg λB=2·n_eff·Λ 闭式方法学不同源）")
def _b64_bragg_lambda_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b3()
    return float(m.bragg_peak_lambda(
        float(p["n1"]), float(p["n2"]), float(p["Lambda"]), 60))

@_register_candidate(
    "b65_sqbarrier_T_deep_cand",
    "切片转移矩阵数值透射（深隧穿 E<V0）↔ 方势垒解析闭式 sinh²，方法学独立")
def _b65_sqbarrier_T_deep(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b66_sqbarrier_T_neartop_cand",
    "切片转移矩阵数值透射（近顶 E<V0）↔ 方势垒解析闭式 sinh²，方法学独立")
def _b66_sqbarrier_T_neartop(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b67_sqbarrier_T_osc_cand",
    "切片转移矩阵数值透射（E>V0 振荡区）↔ 方势垒解析闭式 sin²，方法学独立")
def _b67_sqbarrier_T_osc(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b68_sqbarrier_R_cand",
    "1 − 切片转移矩阵数值透射 ↔ 方势垒解析反射 R=1−T（E<V0），方法学独立")
def _b68_sqbarrier_R(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return 1.0 - float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b70_dbbar_Tpeak_cand",
    "数值扫 E 取切片转移矩阵透射最大 ↔ 双势垒谐振峰解析 T_peak≈1，方法学独立")
def _b70_dbbar_Tpeak(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_double_barrier_T_peak(p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, p["b_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b71_dbbar_T_detune_cand",
    "切片转移矩阵双势垒透射 ↔ 双势垒总转移矩阵闭式（失谐 E≠E_r），方法学独立")
def _b71_dbbar_T_detune(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_double_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, p["b_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b73_finwell_Tpeak_cand",
    "数值扫 E 取切片转移矩阵透射最大 ↔ 有限深势阱散射解析共振峰，方法学独立")
def _b73_finwell_Tpeak(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_finwell_scatter_T_peak(p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b74_finwell_Tmin_cand",
    "数值扫 E 取切片转移矩阵透射最小 ↔ 有限深势阱散射解析反共振谷，方法学独立")
def _b74_finwell_Tmin(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_finwell_scatter_T_min(p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b75_delta_T_cand",
    "极薄高超薄片近似 δ 极限切片转移矩阵透射 ↔ δ 势垒精确闭式，方法学独立")
def _b75_delta_T(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    alpha_Jm = float(p["alpha_eVnm"]) * m.EV * 1e-9
    return float(m.cand_delta_T(p["E_eV"] * m.EV, alpha_Jm, m.ME))

@_register_candidate(
    "b76_delta_R_cand",
    "1 − δ 极限切片转移矩阵透射 ↔ δ 势垒解析反射 R=1−T，方法学独立")
def _b76_delta_R(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    alpha_Jm = float(p["alpha_eVnm"]) * m.EV * 1e-9
    return 1.0 - float(m.cand_delta_T(p["E_eV"] * m.EV, alpha_Jm, m.ME))

@_register_candidate(
    "b77_step_T_cand",
    "阶跃剖面切片转移矩阵透射 ↔ 阶跃势解析透射 T=4k1k2/(k1+k2)²（E>V0），方法学独立")
def _b77_step_T(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_step_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, m.ME))

@_register_candidate(
    "b78_step_R_cand",
    "1 − 阶跃剖面切片转移矩阵透射 ↔ 阶跃势全反射解析 R=1（E<V0），方法学独立")
def _b78_step_R(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return 1.0 - float(m.cand_step_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, m.ME))

@_register_candidate(
    "b79_periodic_T_cand",
    "N 胞切片转移矩阵连乘数值透射 ↔ Kronig-Penney 精确闭式（单胞矩阵幂），方法学独立")
def _b79_periodic_T(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    E = 0.5 * p["V0_eV"] * m.EV  # 带边
    return float(m.cand_periodic_T(E, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, p["d_nm"] * 1e-9, int(p["N"]), m.ME))

@_register_candidate(
    "b80_asym_dbbar_T_cand",
    "非对称双势垒切片转移矩阵透射 ↔ 非对称双势垒总转移矩阵闭式（异高 V1≠V2），方法学独立")
def _b80_asym_dbbar_T(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_asym_double_barrier_T(p["E1_eV"] * m.EV, p["E2_eV"] * m.EV, p["a_nm"] * 1e-9, p["b_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b81_sqbarrier_T_v2_cand",
    "切片转移矩阵数值透射（异参数深隧穿）↔ 方势垒解析闭式，方法学独立")
def _b81_sqbarrier_T_v2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b82_sqbarrier_R_v2_cand",
    "1 − 切片转移矩阵数值透射（异参数深隧穿）↔ 方势垒解析反射 R=1−T，方法学独立")
def _b82_sqbarrier_R_v2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return 1.0 - float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b83_sqbarrier_T_v3_cand",
    "切片转移矩阵数值透射（异参数 E>V0 振荡）↔ 方势垒解析闭式 sin²，方法学独立")
def _b83_sqbarrier_T_v3(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b84_finwell_R_cand",
    "1 − 切片转移矩阵数值透射 ↔ 有限深势阱散射解析反射 R=1−T（异参数），方法学独立")
def _b84_finwell_R(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return 1.0 - float(m.cand_finwell_scatter_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b85_delta_T_v2_cand",
    "δ 极限切片转移矩阵透射（异参数）↔ δ 势垒精确闭式，方法学独立")
def _b85_delta_T_v2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    alpha_Jm = float(p["alpha_eVnm"]) * m.EV * 1e-9
    return float(m.cand_delta_T(p["E_eV"] * m.EV, alpha_Jm, m.ME))

@_register_candidate(
    "b86_step_R_v2_cand",
    "1 − 阶跃剖面切片转移矩阵透射 ↔ 阶跃势全反射解析 R=1（异参数 E<V0），方法学独立")
def _b86_step_R_v2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return 1.0 - float(m.cand_step_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, m.ME))

@_register_candidate(
    "b87_sqbarrier_T_v4_cand",
    "切片转移矩阵数值透射（异参数极深隧穿）↔ 方势垒解析闭式，方法学独立")
def _b87_sqbarrier_T_v4(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_square_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b88_dbbar_T_detune_v2_cand",
    "切片转移矩阵双势垒透射（异参数）↔ 双势垒总转移矩阵闭式，方法学独立")
def _b88_dbbar_T_detune_v2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b4()
    return float(m.cand_double_barrier_T(p["E_eV"] * m.EV, p["V0_eV"] * m.EV, p["a_nm"] * 1e-9, p["b_nm"] * 1e-9, m.ME))

@_register_candidate(
    "b89_hydrogen_1s_cand",
    "氢原子径向 FD 薛定谔本征第 0 径向态（Dirichlet 盒 1D 径向 ODE 数值积分）↔ 解析闭式 E_n=-RYDBERG·Z²/n²，方法学独立")
def _b89_hydrogen_1s(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_hydrogen(0, 0, float(p["Z"])))

@_register_candidate(
    "b90_hydrogen_2s_cand",
    "氢原子径向 FD 薛定谔本征第 1 径向态 ↔ 解析闭式 E_2=-RYDBERG·Z²/4，方法学独立")
def _b90_hydrogen_2s(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_hydrogen(0, 1, float(p["Z"])))

@_register_candidate(
    "b91_hydrogen_2p_cand",
    "氢原子径向 FD 薛定谔本征（l=1, n_r=0）↔ 解析闭式 E_2=-RYDBERG·Z²/4，方法学独立")
def _b91_hydrogen_2p(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_hydrogen(1, 0, float(p["Z"])))

@_register_candidate(
    "b92_hydrogen_3s_cand",
    "氢原子径向 FD 薛定谔本征第 2 径向态 ↔ 解析闭式 E_3=-RYDBERG·Z²/9，方法学独立")
def _b92_hydrogen_3s(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_hydrogen(0, 2, float(p["Z"])))

@_register_candidate(
    "b93_hydrogen_3p_cand",
    "氢原子径向 FD 薛定谔本征（l=1, n_r=1）↔ 解析闭式 E_3=-RYDBERG·Z²/9，方法学独立")
def _b93_hydrogen_3p(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_hydrogen(1, 1, float(p["Z"])))

@_register_candidate(
    "b94_hydrogen_3d_cand",
    "氢原子径向 FD 薛定谔本征（l=2, n_r=0）↔ 解析闭式 E_3=-RYDBERG·Z²/9，方法学独立")
def _b94_hydrogen_3d(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_hydrogen(2, 0, float(p["Z"])))

@_register_candidate(
    "b95_ho3d_l0_cand",
    "3D 各向同性谐振子径向 FD 薛定谔本征第 0 径向态 ↔ 解析闭式 E=(3/2)·ℏω，方法学独立")
def _b95_ho3d_l0(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_ho3d(0, 0, float(p["hbar_omega"])))

@_register_candidate(
    "b96_ho3d_l1_cand",
    "3D 各向同性谐振子径向 FD 薛定谔本征（l=1, n_r=0）↔ 解析闭式 E=(5/2)·ℏω，方法学独立")
def _b96_ho3d_l1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_ho3d(0, 1, float(p["hbar_omega"])))

@_register_candidate(
    "b97_ho3d_l2_cand",
    "3D 各向同性谐振子径向 FD 薛定谔本征（l=2, n_r=0）↔ 解析闭式 E=(7/2)·ℏω，方法学独立")
def _b97_ho3d_l2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_ho3d(0, 2, float(p["hbar_omega"])))

@_register_candidate(
    "b98_circ_wg_TE21_cand",
    "圆波导 TE21 截止由径向 Helmholtz ODE 数值积分 + 边界根搜索导出 X ↔ 解析 Bessel 零点 X'_21，方法学独立")
def _b98_circ_wg_TE21(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_circ(2, "TE", float(p["a_nm"])))

@_register_candidate(
    "b99_circ_wg_TM01_cand",
    "圆波导 TM01 截止由径向 Helmholtz ODE 数值积分 + 边界根搜索导出 X ↔ 解析 Bessel 零点 X_01，方法学独立")
def _b99_circ_wg_TM01(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_circ(0, "TM", float(p["a_nm"])))

@_register_candidate(
    "b100_circ_wg_TE01_cand",
    "圆波导 TE01 截止由径向 Helmholtz ODE 数值积分 + 边界根搜索导出 X ↔ 解析 Bessel 零点 X'_01，方法学独立")
def _b100_circ_wg_TE01(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_circ(0, "TE", float(p["a_nm"])))

@_register_candidate(
    "b101_rect_wg_TE12_cand",
    "矩形波导 TE12 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立")
def _b101_rect_wg_TE12(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_rect(1, 2, float(p["a"]), float(p["b"])))

@_register_candidate(
    "b102_rect_wg_TE22_cand",
    "矩形波导 TE22 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立")
def _b102_rect_wg_TE22(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_rect(2, 2, float(p["a"]), float(p["b"])))

@_register_candidate(
    "b103_rect_wg_TE31_cand",
    "矩形波导 TE31 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立")
def _b103_rect_wg_TE31(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_rect(3, 1, float(p["a"]), float(p["b"])))

@_register_candidate(
    "b104_rect_wg_TE13_cand",
    "矩形波导 TE13 截止由二盒 1D FD 乘积数值积分导出 ↔ 解析闭式 fc=c/2·√((m/a)²+(n/b)²)，方法学独立")
def _b104_rect_wg_TE13(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b5()
    return float(m.cand_rect(1, 3, float(p["a"]), float(p["b"])))

@_register_candidate(
    "b105_rotor_J1_cand",
    "刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立")
def _b105_rotor_J1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_rotor(1, float(p["mom_47"])))

@_register_candidate(
    "b106_rotor_J2_cand",
    "刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立")
def _b106_rotor_J2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_rotor(2, float(p["mom_47"])))

@_register_candidate(
    "b107_rotor_J3_cand",
    "刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立")
def _b107_rotor_J3(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_rotor(3, float(p["mom_47"])))

@_register_candidate(
    "b108_rotor_J4_cand",
    "刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立")
def _b108_rotor_J4(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_rotor(4, float(p["mom_47"])))

@_register_candidate(
    "b109_rotor_J5_cand",
    "刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立")
def _b109_rotor_J5(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_rotor(5, float(p["mom_47"])))

@_register_candidate(
    "b110_rotor_J6_cand",
    "刚性转子能级由关联 Legendre 方程 FD 本征导出 ↔ 解析闭式 E_J=ℏ²J(J+1)/(2I)，方法学独立")
def _b110_rotor_J6(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_rotor(6, float(p["mom_47"])))

@_register_candidate(
    "b111_box2d_11_cand",
    "2D 无限方势阱能级由 2D FD 拉普拉斯本征（Kronecker 和分解）导出 ↔ 解析闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²)，方法学独立")
def _b111_box2d_11(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_box2d(1, 1, float(p["Lx_nm"]), float(p["Ly_nm"])))

@_register_candidate(
    "b112_box2d_21_cand",
    "2D 无限方势阱能级由 2D FD 拉普拉斯本征导出 ↔ 解析闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²)，方法学独立")
def _b112_box2d_21(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_box2d(2, 1, float(p["Lx_nm"]), float(p["Ly_nm"])))

@_register_candidate(
    "b113_box2d_12_cand",
    "2D 无限方势阱能级由 2D FD 拉普拉斯本征导出 ↔ 解析闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²)，方法学独立")
def _b113_box2d_12(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_box2d(1, 2, float(p["Lx_nm"]), float(p["Ly_nm"])))

@_register_candidate(
    "b114_box2d_22_cand",
    "2D 无限方势阱能级由 2D FD 拉普拉斯本征导出 ↔ 解析闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²)，方法学独立")
def _b114_box2d_22(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_box2d(2, 2, float(p["Lx_nm"]), float(p["Ly_nm"])))

@_register_candidate(
    "b115_triangular_n1_cand",
    "量子三角势阱能级由 1D 斜坡势 FD 薛定谔本征导出 ↔ Airy 零点闭式 E_n=(ℏ²(eF)²/2m_e)^{1/3}·ζ_n，方法学独立")
def _b115_triangular_n1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_triangular(1, float(p["F_7"])))

@_register_candidate(
    "b116_triangular_n2_cand",
    "量子三角势阱能级由 1D 斜坡势 FD 薛定谔本征导出 ↔ Airy 零点闭式 E_n=(ℏ²(eF)²/2m_e)^{1/3}·ζ_n，方法学独立")
def _b116_triangular_n2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_triangular(2, float(p["F_7"])))

@_register_candidate(
    "b117_triangular_n3_cand",
    "量子三角势阱能级由 1D 斜坡势 FD 薛定谔本征导出 ↔ Airy 零点闭式 E_n=(ℏ²(eF)²/2m_e)^{1/3}·ζ_n，方法学独立")
def _b117_triangular_n3(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_triangular(3, float(p["F_7"])))

@_register_candidate(
    "b118_spherical_l0n1_cand",
    "三维无限球形势阱能级由 3D 径向 FD 薛定谔本征导出 ↔ 球 Bessel 零点闭式 E_nl=x_nl²ℏ²/(2mR²)，方法学独立")
def _b118_spherical_l0n1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_spherical(0, 1, float(p["R_nm"])))

@_register_candidate(
    "b119_spherical_l1n1_cand",
    "三维无限球形势阱能级由 3D 径向 FD 薛定谔本征（l=1 离心项）导出 ↔ 球 Bessel 零点闭式，方法学独立")
def _b119_spherical_l1n1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_spherical(1, 1, float(p["R_nm"])))

@_register_candidate(
    "b120_spherical_l2n1_cand",
    "三维无限球形势阱能级由 3D 径向 FD 薛定谔本征（l=2 离心项）导出 ↔ 球 Bessel 零点闭式，方法学独立")
def _b120_spherical_l2n1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b6()
    return float(m.cand_spherical(2, 1, float(p["R_nm"])))

@_register_candidate(
    "b121_morse_n0_cand",
    "Morse 势振动能级由 1D FD 薛定谔本征（V=D_e(1−e^{−a(r−r_e)})²，Dirichlet 盒）导出 ↔ 解析非谐谱 E_n=ℏω(n+½)−[ℏω(n+½)]²/(4D_e)，方法学独立")
def _b121_morse_n0(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_morse(0, float(p["de_ev"])))

@_register_candidate(
    "b122_morse_n1_cand",
    "Morse 势振动能级由 1D FD 薛定谔本征（第 2 束缚态）导出 ↔ 解析非谐谱闭式，方法学独立")
def _b122_morse_n1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_morse(1, float(p["de_ev"])))

@_register_candidate(
    "b123_morse_n2_cand",
    "Morse 势振动能级由 1D FD 薛定谔本征（第 3 束缚态）导出 ↔ 解析非谐谱闭式，方法学独立")
def _b123_morse_n2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_morse(2, float(p["de_ev"])))

@_register_candidate(
    "b124_morse_n3_cand",
    "Morse 势振动能级由 1D FD 薛定谔本征（第 4 束缚态）导出 ↔ 解析非谐谱闭式，方法学独立")
def _b124_morse_n3(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_morse(3, float(p["de_ev"])))

@_register_candidate(
    "b125_ho2d_00_cand",
    "二维各向异性谐振子能级由 2D FD 本征（两 1D FD 谐振子本征值 Kronecker 和）导出 ↔ 闭式 E=ℏω_x(n_x+½)+ℏω_y(n_y+½)，方法学独立")
def _b125_ho2d_00(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_ho2d(0, 0, float(p["ox"]), float(p["oy"])))

@_register_candidate(
    "b126_ho2d_10_cand",
    "二维各向异性谐振子能级由 2D FD 本征（Kronecker 和）导出 ↔ 闭式，方法学独立")
def _b126_ho2d_10(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_ho2d(1, 0, float(p["ox"]), float(p["oy"])))

@_register_candidate(
    "b127_ho2d_01_cand",
    "二维各向异性谐振子能级由 2D FD 本征（Kronecker 和）导出 ↔ 闭式，方法学独立")
def _b127_ho2d_01(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_ho2d(0, 1, float(p["ox"]), float(p["oy"])))

@_register_candidate(
    "b128_ho2d_11_cand",
    "二维各向异性谐振子能级由 2D FD 本征（Kronecker 和）导出 ↔ 闭式，方法学独立")
def _b128_ho2d_11(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_ho2d(1, 1, float(p["ox"]), float(p["oy"])))

@_register_candidate(
    "b129_box3d_111_cand",
    "三维长方体势阱能级由 3D FD 拉普拉斯本征（三路 1D Dirichlet 本征值 Kronecker 和）导出 ↔ 闭式 E=(π²ℏ²/2m)(n_x²/L_x²+n_y²/L_y²+n_z²/L_z²)，方法学独立")
def _b129_box3d_111(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_box3d(1, 1, 1, float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b130_box3d_211_cand",
    "三维长方体势阱能级由 3D FD 拉普拉斯本征（Kronecker 和）导出 ↔ 闭式，方法学独立")
def _b130_box3d_211(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_box3d(2, 1, 1, float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b131_box3d_121_cand",
    "三维长方体势阱能级由 3D FD 拉普拉斯本征（Kronecker 和）导出 ↔ 闭式，方法学独立")
def _b131_box3d_121(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_box3d(1, 2, 1, float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b132_box3d_112_cand",
    "三维长方体势阱能级由 3D FD 拉普拉斯本征（Kronecker 和）导出 ↔ 闭式，方法学独立")
def _b132_box3d_112(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_box3d(1, 1, 2, float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b133_h_4s_cand",
    "类氢离子激发态能级由径向 FD 薛定谔本征（Coulomb 势，n_r=n−l−1 径向节点）导出 ↔ Rydberg 闭式 E_n=−RYDBERG·Z²/n²，方法学独立")
def _b133_h_4s(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_hydrogen(0, 3, float(p["Z"])))   # H 4s: l=0, n_r=n−l−1=3

@_register_candidate(
    "b134_he_4d_cand",
    "类氢离子激发态能级由径向 FD 薛定谔本征（Z=2 Coulomb + l=2 离心项）导出 ↔ Rydberg 闭式，方法学独立")
def _b134_he_4d(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_hydrogen(2, 1, float(p["Z"])))   # He⁺ 4d: l=2, n_r=1

@_register_candidate(
    "b135_li_4f_cand",
    "类氢离子激发态能级由径向 FD 薛定谔本征（Z=3 Coulomb + l=3 强离心势垒）导出 ↔ Rydberg 闭式，方法学独立")
def _b135_li_4f(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_hydrogen(3, 0, float(p["Z"])))   # Li²⁺ 4f: l=3, n_r=0

@_register_candidate(
    "b136_h_5d_cand",
    "类氢离子激发态能级由径向 FD 薛定谔本征（H n=5 d 态，l=2）导出 ↔ Rydberg 闭式，方法学独立")
def _b136_h_5d(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b7()
    return float(m.cand_hydrogen(2, 2, float(p["Z"])))   # H 5d: l=2, n_r=2

@_register_candidate(
    "b137_h2d_m2_cand",
    "2D 类氢 (m=2,n_r=0) 由 2D 径向 FD 本征（u=√r·R，(m²−¼)ℏ²/2mr²−Ze²/4πε₀r）导出 ↔ 2D Coulomb 闭式 E=−Z²Ry/(N−½)²，方法学独立")
def _b137_h2d_m2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_hydrogen2d(2, 0, float(p["Z"])))

@_register_candidate(
    "b138_h2d_m2n1_cand",
    "2D 类氢 (m=2,n_r=1) 由 2D 径向 FD 本征导出 ↔ 2D Coulomb 闭式，方法学独立")
def _b138_h2d_m2n1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_hydrogen2d(2, 1, float(p["Z"])))

@_register_candidate(
    "b139_h2d_m4_cand",
    "2D 类氢 (m=4) 强离心态由 2D 径向 FD 本征导出 ↔ 2D Coulomb 闭式，方法学独立")
def _b139_h2d_m4(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_hydrogen2d(4, 0, float(p["Z"])))

@_register_candidate(
    "b140_h2d_z2_cand",
    "2D 类氢 (Z=2,m=2,n_r=0) 由 2D 径向 FD 本征导出 ↔ 2D Coulomb 闭式，方法学独立")
def _b140_h2d_z2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_hydrogen2d(2, 0, float(p["Z"])))

@_register_candidate(
    "b141_annulus_nu0_cand",
    "2D 圆环 (ν=0) 由径向 FD 本征（(ν²−¼)/r² 离心项，u(R_i)=u(R_o)=0）导出 ↔ Bessel 交叉积零点闭式，方法学独立")
def _b141_annulus_nu0(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_annulus(0.0, 1, float(p["ri_nm"]), float(p["ro_nm"])))

@_register_candidate(
    "b142_annulus_nu1_cand",
    "2D 圆环 (ν=1) 由径向 FD 本征导出 ↔ Bessel 交叉积零点闭式，方法学独立")
def _b142_annulus_nu1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_annulus(1.0, 1, float(p["ri_nm"]), float(p["ro_nm"])))


@_register_candidate(
    "b453_coherent_loss_fidelity_cand",
    "相干态经损耗通道的输入-输出保真度：截断 Fock 空间建归一 |α⟩⟨α|（D-114 coherent_dm）+ D-116 振幅阻尼 Kraus 算子求和 ⇒ F=Tr(ρ_out ρ_in) ↔ 解析闭式 exp(−|α|²(1−√η)²)，方法学独立（离散参数=Fock 截断维数 N=22）")
def _b453_coherent_loss_fidelity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b30()
    return float(m.cand_b453(float(p["alpha"]), float(p["eta"])))


@_register_candidate(
    "b454_heralded_purity_cand",
    "TMSS on/off 预报条件态纯度：截断 Fock 空间矩阵指数建 TMSV（D-114 tmss_numeric_state）→ on/off 投影 → 部分迹 ⇒ Tr(ρ²) ↔ 解析闭式 (1−λ²)/(1+λ²)，方法学独立（离散参数=Fock 截断维数 N=26）")
def _b454_heralded_purity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b30()
    return float(m.cand_b454(float(p["lam"])))


@_register_candidate(
    "b455_heralded_g2_cand",
    "TMSS on/off 预报条件态 g²(0)：同 B454 截断 Fock 空间路线 ⇒ ⟨n(n−1)⟩/⟨n⟩² ↔ 解析闭式 2λ²，方法学独立（离散参数=Fock 截断维数 N=36）")
def _b455_heralded_g2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b30()
    return float(m.cand_b455(float(p["lam"])))
@_register_candidate(
    "b456_wcs_single_photon_cand",
    "WCS 单光子概率·有限 Fock 空间：截断 Fock 空间建归一 WCS 布居 P(n)=e^{−μ}μⁿ/n!（D-114 `wcs_probs`）→ 读 ρ₁₁ ↔ 解析闭式 μe^{−μ}，方法学独立（离散参数=Fock 截断维数 N=10）")
def _b456_wcs_single_photon_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b31()
    return float(m.cand_b456(float(p["mu"])))


@_register_candidate(
    "b457_wcs_multiphoton_cand",
    "WCS 多光子污染·有限 Fock 空间：同 B456 的归一截断密态 → Tr(ρ·Π_{≥2}) = Σ_{n≥2}ρ_nn ↔ 解析闭式 1−e^{−μ}(1+μ)，方法学独立（离散参数=Fock 截断维数 N=10）")
def _b457_wcs_multiphoton_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b31()
    return float(m.cand_b457(float(p["mu"])))


@_register_candidate(
    "b458_polygon_area_cand",
    "多边形面积·版图栅格化：平台 `voxel_field.rasterize_polygon` 的**亚格平均**覆盖率 Σfrac·dl²（even-odd 交叉数 + s×s 子采样）↔ 解析闭式 Shoelace 面积，方法学独立（离散参数 = subpixel，默认 16）")
def _b458_polygon_area_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b32()
    return float(m.cand_b458())


@_register_candidate(
    "b459_lorentzian_slope_cand",
    "洛伦兹谐振线型斜率极值·数值微分：等距采样 T(λ)=T_bg−depth·Γ²/((λ−λ0)²+Γ²)（Γ=FWHM/2），中心差分 np.gradient 取 |dT/dλ| 最大值 ↔ 闭式 slope_closed=depth·(3√3/4)/FWHM，方法学独立（离散参数=采样点数 n，默认 4001）")
def _b459_lorentzian_slope_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b33()
    return float(m.cand_b459(float(p["depth"]), float(p["FWHM"])))


@_register_candidate(
    "b460_sensitivity_cand",
    "波导灵敏度·有限差分：对称平板波导 TE0 解析特征方程 u=V·cos(u) 解 n_eff，perturb n_clad ±dp → 重解 n_eff → 中心差商 dneff/dn_clad ↔ HF 微扰闭式 golden=(n_clad/n_eff)·Γ_clad，方法学独立（离散参数=dp，默认 1e-6）")
def _b460_sensitivity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b34()
    return float(m.sensitivity_fd(float(p["n_f"]), float(p["n_c"]), float(p["d_um"]), float(p["wl_um"])))


@_register_candidate(
    "b461_sensitivity_cand",
    "表面/吸附层灵敏度·三层对称平板 TE0 传递矩阵（连续域匹配法，无空间网格）：解 n_eff(n_a) → 中心差商 dneff/dn_a ↔ HF 微扰闭式 golden=(n_a/n_eff)·Γ_adlayer（Γ_adlayer=Γ_clad·(1−e^(−2γ·ds))），方法学独立（离散参数=da，默认 1e-5）")
def _b461_sensitivity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b35()
    return float(m.surface_sensitivity_fd(
        float(p["n_f"]), float(p["n_c"]), float(p["n_a"]),
        float(p["d_um"]), float(p["ds_um"]), float(p["wl_um"]), da=1e-5))


@_register_candidate(
    "b462_langmuir_cand",
    "朗缪尔吸附覆盖度·四阶 RK4 积分：dθ/dt=k_on·C·(1−θ)−k_off·θ，θ(0)=0，积分到 ~20 时间常数 ≈ 平衡 ↔ 闭式 golden θ_eq=K_A·C/(1+K_A·C)（K_A=k_on/k_off），方法学独立（离散参数=n_steps，默认 2000）")
def _b462_langmuir_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b35()
    return float(m.langmuir_rk4(
        float(p["k_on"]), float(p["k_off"]), float(p["C"]), n_steps=2000))


@_register_candidate(
    "b463_poiseuille_cand",
    "矩形微通道 Hagen-Poiseuille 体积流量·2D 有限差分 Poisson（红黑棋盘 SOR 矢量解，纯 numpy 无空间双循环，Young 最优 ω*）：解 −∇²u=ΔP/(μL)，u|边=0，Q=∫∫u dA ↔ 矩形级数闭式 golden Q=(ΔP/μL)·(a·b³/12)·C_f(α)（α=小/大边长），方法学独立（离散参数=N_grid，默认 200）")
def _b463_poiseuille_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b36()
    return float(m.poiseuille_flow_rate_fd_nl_s(
        float(p["dp_pa"]), float(p["mu_pas"]), float(p["L_m"]),
        float(p["w_m"]), float(p["h_m"]), N_grid=200))


@_register_candidate(
    "b464_washburn_cand",
    "Lucas-Washburn 毛细填充长度·后向欧拉（隐式·无条件稳定·L(0)=0 奇点不爆）：dL/dt=(D·γ·cosθ)/(8ηL) ⟺ 闭式 golden L=√[(D·γ·cosθ)/(4η)·t]，方法学独立（离散参数=n_steps，默认 2000）")
def _b464_washburn_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b36()
    return float(m.washburn_length_be_mm(
        float(p["D_m"]), float(p["gamma_Nm"]), float(p["cos_theta"]),
        float(p["eta_Pas"]), float(p["t_s"]), n_steps=2000))


@_register_candidate(
    "b465_thermal_cand",
    "圆柱微通道壁面径向热阻·1D 有限差分径向 Laplace（守恒界面通量格式）：解 d/dr(r·dT/dr)=0，界面热流 Q=−2π·r_{1/2}·k·(T_1−T_0)/dr·L ⟺ Fourier 闭式 golden R_th=ln(r_o/r_i)/(2πkL)，方法学独立（离散参数=N，默认 600）")
def _b465_thermal_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b36()
    return float(m.thermal_resistance_fd_k_W(
        float(p["r_i_m"]), float(p["r_o_m"]), float(p["k_WmK"]),
        float(p["L_m"]), N=600))


@_register_candidate(
    "b466_array_crosstalk_cand",
    "密集传感阵列热串扰比·1D 有限差分 BVP（三对角 Thomas O(N)，条带源，T(±X)=0）↔ 阻尼热扩散闭式 golden sinh(a/L)·e^{−d/L}/(1−e^{−a/L})，方法学独立（离散参数=N，默认 6400）")
def _b466_array_crosstalk_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b37()
    return float(m.array_crosstalk_fd(
        float(p["L_th_um"]), float(p["d_um"]), float(p["a_um"]), N=6400))


@_register_candidate(
    "b467_tia_noise_floor_cand",
    "TIA 读出噪声底·时域冲激响应数值积分（梯形，z=(1/C)e^{−t/τ}，τ=R_f·C）↔ 频域闭式 golden √(S_i·R_f²·(π/2)·f_p)=√(kT/C)（R_f 显式相消），方法学独立（离散参数=n，默认 32000）")
def _b467_tia_noise_floor_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b37()
    return float(m.tia_noise_floor_td_uV(
        float(p["C_fF"]), float(p["R_kOhm"]), float(p["T_K"]), n=32000))


@_register_candidate(
    "b468_align_overlap_cand",
    "光纤-波导横向对准耦合效率·离散采样+线性插值+数值重叠积分（模拟模式剖面仅在有限网格已知、平移落点非格点）↔ 高斯模场重叠闭式 golden e^{−d²/(2w²)}，方法学独立（离散参数=N，默认 1024）")
def _b468_align_overlap_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b37()
    return float(m.align_overlap_sampled(
        float(p["d_um"]), float(p["w_um"]), N=1024))


@_register_candidate(
    "b469_thinwire_sensitivity_cand",
    "薄线波导折射率灵敏度·FV-FD 有限差分（perturb n_a±δ→重解 n_eff→中心差商，δ=1e-4）↔ 一阶本征值微扰闭式 golden（Rayleigh 商 + 左本征矢），方法学独立（薄线 w=0.22/substrate/water n_a=1.33）")
def _b469_thinwire_sensitivity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b38()
    return float(m.cand_b469())


@_register_candidate(
    "b470_slot_sensitivity_cand",
    "狭缝波导折射率灵敏度·FV-FD 有限差分（perturb n_a±δ→重解 n_eff→中心差商，δ=1e-4）↔ 一阶本征值微扰闭式 golden（Rayleigh 商 + 左本征矢），方法学独立（slot rail=0.22/gap=0.05/substrate/water 填缝）")
def _b470_slot_sensitivity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b38()
    return float(m.cand_b470())


@_register_candidate(
    "b471_suspended_sensitivity_cand",
    "悬浮波导折射率灵敏度·FV-FD 有限差分（perturb n_a±δ→重解 n_eff→中心差商，δ=1e-4；suspended 去衬底）↔ 一阶本征值微扰闭式 golden（Rayleigh 商 + 左本征矢），方法学独立（suspended w=0.45/无 substrate/water 包围）")
def _b471_suspended_sensitivity_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b38()
    return float(m.cand_b471())


# 🔴 v0.9.209：**B472 无候选登记**（诚实降级为自证桩）。
# 原实现 `b472_q_scaling_lod_cand`（PS-M2 lod_real(Q) 逐分量合成）与 golden **代数恒等**
# （slope=depth·(3√3/4)/FWHM、FWHM=λ/Q ⇒ slope 严格 ∝Q ⇒ LOD_elec 严格 ∝1/Q ⇒ 缩放闭式
# 精确重现 lod_real，实测 |Δ|=0.0），经 `run_benchmark_falsifiability_smoke` 实测判为**自证桩**
# （B28 同型「同式异写 ⇒ 虚报」）。故撤下登记、不越级谎报；golden 仍为物理律锚
# （golden.py `_GOLDEN_DISPATCH`/`_PHYSICAL_LAW` 保留 B472）。升级路径见 part6.py B472 note。



@_register_candidate(
    "b473_nv_eta_error_propagation_cand",
    "NV 色心磁力计磁灵敏度·数值误差传播链（相位噪声率 ρ_φ=√(1+a²)/(C√n_ph) → 最优时间 τ_opt=T2*/√2 → 磁场-相位斜率用双能级量子时间演化核的数值中心差商 → 谱密度归一 η=√2·ρ_φ·τ_opt/(|dφ/dB|·√T2*)）↔ 闭式散粒极限 golden，方法学独立（复指数演化核+有限差分 vs 代数标量闭式）")
def _b473_nv_eta_error_propagation_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b39()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b39_numeric.B473_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b473(
        T2star_s=float(p.get("T2star_s", 1e-6)),
        n_ph_per_s=float(p.get("n_ph_per_s", 1e5)),
        contrast=float(p.get("contrast", 0.03)),
        dark_ratio=float(p.get("dark_ratio", 0.0)),
    ))


@_register_candidate(
    "b474_qs_fom_linewidth_cand",
    "量子传感器灵敏度 FOM 体系·数值线宽提取链（时间域对比度包络 C(τ)=e^(−(τ/T2*)²) 数值 FWHM 提取 → 频域宽度 σ_f → 反解等效 T2*'=√2/(2πσ_f) → 合成 η）↔ T2* 路径闭式散粒极限 golden，方法学独立（时间/频域数值提取 vs 相位域代数闭式；与 B473 物理域不同）")
def _b474_qs_fom_linewidth_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b40()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b40_numeric.B474_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b474(
        T2star_s=float(p.get("T2star_s", 1e-6)),
        n_ph_per_s=float(p.get("n_ph_per_s", 1e5)),
        contrast=float(p.get("contrast", 0.03)),
        dark_ratio=float(p.get("dark_ratio", 0.0)),
    ))


@_register_candidate(
    "b475_echo_variance_time_integration_cand",
    "自旋回波（Hahn echo）相位方差·时间域数值积分链（时间网格+均匀初相 → 噪声波形 B(s;φ)=cos(ωs+φ) → t/2 处符号翻转（π 脉冲） → 梯形积分 Φ(φ) → 对 φ 取 ⟨Φ²⟩ → 乘 ω² 归一化）↔ 回波方差闭式 2(1−cos(ωt/2))² golden，方法学独立（数值时域积分 vs 解析闭式 + φ 平均恒等式）")
def _b475_echo_variance_time_integration_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b41()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b41_numeric.B475_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b475(
        omega_t=float(p.get("omega_t", 2.0)),
        t=float(p.get("t", 1.0)),
    ))


@_register_candidate(
    "b476_optimal_depth_grid_search_cand",
    "最优色心深度 d*·网格扫描+三点抛物插值定极小（离散网格逐点算 η_tot(d)=√(1+(d₀/d)³)/√exp(−d/d_att)，argmin 后用三点抛物精修） ↔ 闭式根方程 d⁴+d₀³·d=3·d₀³·d_att（由 d(ln η_tot)/dd=0 解析导出，二分求唯一正根） golden，方法学独立（网格+抛物插值 vs 解析求导+根方程）")
def _b476_optimal_depth_grid_search_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b42()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b42_numeric.B476_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b476(
        d0_nm=float(p.get("d0_nm", 20.0)),
        d_att_nm=float(p.get("d_att_nm", 200.0)),
    ))


@_register_candidate(
    "b477_na_efficiency_sampling_cand",
    "NA 立体角收集效率 η_NA·数值角分布采样（偶极图样 w(θ)=sin³θ·dθ 全半球归一，取 θ≤arcsin(NA) 的权重占比逐点求和） ↔ 闭式解析积分 η_NA=[cos³θ/3−cosθ]₀^{θmax}/(2/3) golden，方法学独立（数值求和 vs 解析积分）")
def _b477_na_efficiency_sampling_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b42()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b42_numeric.B477_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b477(
        na=float(p.get("na", 0.75)),
    ))


@_register_candidate(
    "b478_crosstalk_dipole_field_cand",
    "磁偶极近场串扰系数 X·点偶极场数值积分（把偶极离散成 ±q 分离 δ 的双单极子，逐点算带符号场 [1/(r−δ/2)² − 1/(r+δ/2)²] 再取比值） ↔ 闭式立方律 X=(d_crit/r)³ golden，方法学独立（双单极子差分场数值求和 vs 解析立方律）")
def _b478_crosstalk_dipole_field_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b43()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b43_numeric.B478_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b478(
        r_um=float(p.get("r_um", 1.20)),
        d_crit_um=float(p.get("d_crit_um", 0.30)),
    ))


@_register_candidate(
    "b479_crosstalk_penalty_montecarlo_cand",
    "串扰恶化灵敏度倍率 √(1+X_tot²)·蒙特卡洛噪声功率叠加（生成独立白噪声对 s/c，构造信号+X_tot·c 泄露通道，由数值方差比反推倍率） ↔ 闭式平方和 golden，方法学独立（随机样本数值方差 vs 解析平方和）")
def _b479_crosstalk_penalty_montecarlo_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b43()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b479(
        x_total=float(p.get("x_total", 0.05)),
    ))


@_register_candidate(
    "b480_cmrr_noisy_lsq_slope_cand",
    "梯度计共模抑制比 CMRR·含噪样本 LSQ 斜率比（含读出噪声的共模/差模激励序列，过原点最小二乘斜率求比值再取 dB） ↔ 闭式 20log₁₀(1/ε) golden，方法学独立（含噪样本 LSQ 斜率比 vs 解析 ε 代入 log 闭式）")
def _b480_cmrr_noisy_lsq_slope_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b43()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b480(
        mismatch=float(p.get("mismatch", 0.01)),
    ))


@_register_candidate(
    "b481_grad_eta_montecarlo_diff_cand",
    "梯度计差模灵敏度 η_grad·蒙特卡洛两点差分标准差（两独立通道噪声序列取差分序列的数值标准差 ⇒ 直接得 √2 因子，再 /baseline） ↔ 闭式 η√2/baseline golden，方法学独立（样本差分标准差 vs 解析 √2 因子）")
def _b481_grad_eta_montecarlo_diff_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b43()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b481(
        eta_single=float(p.get("eta_single", 1.0e-9)),
        baseline_um=float(p.get("baseline_um", 1.20)),
    ))


@_register_candidate(
    "b482_freqlock_slope_fid_cand",
    "微波频锁鉴别器中心斜率·时域 FID 数值变换线型的中心差分斜率（指数衰减包络 C(t)=e^{−πwt} 数值 Fourier 变换构造洛伦兹线型，采集窗 t_max=t_max_factor/(πw)，再对鉴别器 S=L(f−δ)−L(f+δ) 在 f₀ 处中心差分） ↔ 闭式解析洛伦兹差分斜率 golden，方法学独立（FID 数值变换微分 vs 解析差分）")
def _b482_freqlock_slope_fid_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b44()
    # 从 spec.params 取物理设计参数（缺省回落到真源默认值）——使反自证桩护栏的
    # 行为判据能真正扰动参数（详见 _batch_b44_numeric.B482_DEFAULT_PARAMS 注释）。
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b482(
        f0_hz=float(p.get("f0_hz", 2.87e9)),
        linewidth_hz=float(p.get("linewidth_hz", 1.0e7)),
        probe_offset_hz=float(p.get("probe_offset_hz", 2.5e6)),
    ))


@_register_candidate(
    "b483_fieldloop_scale_lsq_cand",
    "磁场标度因子自标定·全跨多点最小二乘斜率（±B_ref 全量程取 n 点激励，读数含相对读出噪声，过原点 LSQ 斜率 ⇒ k̂） ↔ 闭式两点法 k̂=V_ref/B_ref golden，方法学独立（多点 LSQ vs 单点相除）")
def _b483_fieldloop_scale_lsq_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b44()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b483(
        v_ref_v=float(p.get("v_ref_v", 1.0e-1)),
        b_ref_t=float(p.get("b_ref_t", 1.0e-4)),
    ))


@_register_candidate(
    "b484_ac_sensitivity_mc_cand",
    "AC 灵敏度带宽折算·蒙特卡洛带限噪声 rms（生成 n 对白噪声样本 σ=η，取差分序列数值 rms ⇒ 直接得 √2 因子，再按 √Δf 折算带宽） ↔ 闭式 η·√(2Δf) golden，方法学独立（样本差分 rms vs 解析因子）")
def _b484_ac_sensitivity_mc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b44()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b484(
        eta_t_per_sqrt_hz=float(p.get("eta_t_per_sqrt_hz", 1.0e-9)),
        bandwidth_hz=float(p.get("bandwidth_hz", 1.0e3)),
    ))


@_register_candidate(
    "b485_squid_ic_phase_scan_cand",
    "SQUID 环路临界电流磁通调制 I_c(Φ)·数值相空间扫描（对 I(δ)=I_c0·[sinδ+sin(δ+2πf)] 在 δ∈[0,2π) 以 2^18 网格扫 |I| 最大 ⇒ 独立复算临界电流，固定非对齐 f=0.30） ↔ 闭式 2·I_c0·|cos(πf)| golden，方法学独立（逐相位扫描取极值 vs 闭式矢量叠加）")
def _b485_squid_ic_phase_scan_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b45()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b485(
        ic0_a=float(p.get("ic0_a", 2.0e-6)),
        flux_phi0=float(p.get("flux_phi0", 0.30)),
    ))


@_register_candidate(
    "b486_squid_transfer_fd_cand",
    "磁通-电压转导 ∂I_c/∂Φ·数值中心差分（对闭式 I_c(Φ±ΔΦ) 做 (hi−lo)/(2ΔΦ)，ΔΦ=1e-6，固定 f=0.30） ↔ 闭式解析导数 −2π·I_c0·sin(πf)·sgn(cosπf)/Φ0 golden，方法学独立（离散差分 vs 解析求导）")
def _b486_squid_transfer_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b45()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b486(
        ic0_a=float(p.get("ic0_a", 2.0e-6)),
        flux_phi0=float(p.get("flux_phi0", 0.30)),
    ))


@_register_candidate(
    "b487_field_sens_mc_cand",
    "磁场灵敏度谱密度 B_N·蒙特卡洛 Johnson 噪声传播（生成 n_mc=4e6 个电流样本 σ=√(4k_BT/R)，经数值转导折算为磁通样本，取数值方差 ⇒ S_Φ ⇒ √/A_eff ⇒ B_N，固定 seed） ↔ 闭式 √(4k_BT/R)/|∂I/∂Φ|/A_eff golden，方法学独立（样本方差统计 vs 闭式逐级代入）")
def _b487_field_sens_mc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b45()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b487(
        temp_k=float(p.get("temp_k", 4.2)),
        resistance_ohm=float(p.get("resistance_ohm", 20.0)),
        ic0_a=float(p.get("ic0_a", 2.0e-6)),
        loop_side_m=float(p.get("loop_side_m", 100.0e-6)),
    ))


@_register_candidate(
    "b488_flux_transformer_neumann_cand",
    "磁通聚焦变压器有效面积 A_eff·离散 Neumann 互感重建（把拾取环/输入线圈离散为 n_seg=2048 段，逐段互感双和数值重建耦合几何比，再还原分压比） ↔ 闭式分压比 γ_A·A_p·M/(L_i+L_p) golden，方法学独立（离散互感求和 vs 闭式分式）")
def _b488_flux_transformer_neumann_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b46()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b488(
        pickup_area_m2=float(p.get("pickup_area_m2", (500.0e-6) ** 2)),
        mutual_h=float(p.get("mutual_h", 1.6e-9)),
        input_inductance_h=float(p.get("input_inductance_h", 2.0e-9)),
        pickup_inductance_h=float(p.get("pickup_inductance_h", 2.0e-9)),
    ))


@_register_candidate(
    "b489_submicron_noise_mc_cand",
    "亚微米结噪声约束磁通噪声谱密度 S_Φ,opt·蒙特卡洛 Johnson 噪声传播（生成 n_mc=4e6 个电流样本 σ=√(4k_BT/R_n,opt)，经数值转导折算磁通样本，取数值方差） ↔ 闭式逐级代入 golden，方法学独立（样本方差统计 vs 闭式逐级代入）")
def _b489_submicron_noise_mc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b46()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b489(
        temp_k=float(p.get("temp_k", 4.2)),
        ic0_a=float(p.get("ic0_a", 2.0e-6)),
        rn_ohm=float(p.get("rn_ohm", 142.5)),
    ))


@_register_candidate(
    "b490_opt_field_sens_mc_neumann_cand",
    "优化后磁场灵敏度 B_N,opt·MC 噪声 + 离散 Neumann 变压器解（有效面积走数值互感，噪声走样本方差） ↔ 闭式三重叠加 golden，方法学独立（MC 统计 + 数值互感 vs 闭式逐级代入）")
def _b490_opt_field_sens_mc_neumann_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b46()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b490(
        temp_k=float(p.get("temp_k", 4.2)),
        ic0_a=float(p.get("ic0_a", 2.0e-6)),
        rn_ohm=float(p.get("rn_ohm", 142.5)),
        pickup_area_m2=float(p.get("pickup_area_m2", (500.0e-6) ** 2)),
        mutual_h=float(p.get("mutual_h", 1.6e-9)),
        input_inductance_h=float(p.get("input_inductance_h", 2.0e-9)),
        pickup_inductance_h=float(p.get("pickup_inductance_h", 2.0e-9)),
    ))


@_register_candidate(
    "b491_fid_polarization_rk4_cand",
    "光抽运关闭后自由进动横向极化 P_x(t*)·RK4 时间推进 2D Bloch 方程（固定步长 h=t*/64 逐点四阶 Runge–Kutta，不含解析指数/余弦） ↔ 闭式 Bloch 精确解 golden，方法学独立（数值时间推进 vs 闭式精确解）")
def _b491_fid_polarization_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b47()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b491(
        p0=float(p.get("p0", 1.0)),
        r_tot_s1=float(p.get("r_tot_s1", 300.0)),
        b_t=float(p.get("b_t", 10.0e-9)),
        t_s=float(p.get("t_s", 2.0e-3)),
    ))


@_register_candidate(
    "b492_alkali_density_trapezoid_cand",
    "碱金属（Rb）饱和蒸气数密度 n(T)·复合梯形数值积分 d(ln n)/dT=ΔH/(k_B·T²)（n_seg=256 逐段梯形平均后取 exp，不含闭式指数） ↔ 闭式 Clausius–Clapeyron golden，方法学独立（数值求积 vs 闭式指数）")
def _b492_alkali_density_trapezoid_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b47()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b492(
        n_ref_m3=float(p.get("n_ref_m3", 1.0e17)),
        t_ref_k=float(p.get("t_ref_k", 313.15)),
        dh_over_kb_k=float(p.get("dh_over_kb_k", 8384.0)),
        t_k=float(p.get("t_k", 333.15)),
    ))


@_register_candidate(
    "b493_pump_transmission_rk4_cand",
    "泵浦光 Beer–Lambert 透过率 T(L)·RK4 沿 z 数值积分 dI/dz=−n·σ_abs·I（n_steps=64 四阶 Runge–Kutta，不含闭式指数） ↔ 闭式 Beer–Lambert golden，方法学独立（数值空间推进 vs 闭式指数）")
def _b493_pump_transmission_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_batch_b47()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b493(
        trans0=float(p.get("trans0", 1.0)),
        n_density_m3=float(p.get("n_density_m3", 1.0e19)),
        sigma_abs_m2=float(p.get("sigma_abs_m2", 5.0e-18)),
        length_m=float(p.get("length_m", 0.02)),
    ))


@_register_candidate(
    "b494_q_factor_rk4_cand",
    "腔品质因子 Q=ω/κ·RK4 时间推进能量衰减 dU/dt=−κU（U₀=1，n_steps=64 四阶 Runge–Kutta，不含闭式除式）⇒ U(T) ⇒ 反解 κ_cand=−ln(U(T))/T ⇒ Q_cand=ω/κ_cand ↔ 闭式 Q=ω/κ golden，方法学独立（数值 ODE 反解 vs 闭式除式）")
def _b494_q_factor_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_qs_m3c_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b494(
        omega=float(p.get("omega", 1.0)),
        kappa=float(p.get("kappa", 1.0)),
        t_observe=float(p.get("t_observe", 8.22e-12)),
    ))


@_register_candidate(
    "b495_mode_volume_midpoint_cand",
    "有效模体积 V_eff·中点求积 ∫_{-a/2}^{a/2}(1−4x²/a²)²dx（n_seg=256 段，不含闭式积分）⇒ ×A ↔ 闭式 V_eff=A·8a/15 golden，方法学独立（数值求积 vs 解析积分）")
def _b495_mode_volume_midpoint_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_qs_m3c_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b495(
        a=float(p.get("a", 1.55e-6)),
        A=float(p.get("A", 5.0e-14)),
    ))


@_register_candidate(
    "b496_coupling_field_energy_cand",
    "单光子耦合 g=(μ/ħ)√(ħω/(εV_eff))·数值积分 ∫|E|²dV（中点求积 ⇒ 数值 V_eff_num）⇒ 单光子场幅 E₀=√(ħω/(ε·V_eff_num)) ⇒ g=μE₀/ħ ↔ 闭式 g golden，方法学独立（数值场能积分 vs 闭式 V_eff）")
def _b496_coupling_field_energy_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_qs_m3c_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b496(
        mu=float(p.get("mu", 1.0e-29)),
        omega=float(p.get("omega", 1.0)),
        eps=float(p.get("eps", 1.0)),
        a=float(p.get("a", 1.55e-6)),
        A=float(p.get("A", 5.0e-14)),
    ))


@_register_candidate(
    "b497_threshold_distance_bisect_cand",
    "表面码逻辑错误阈值距离 d*·二分根求解 f(d)=A·(p_phys/p_th)^((d+1)/2)−target=0 于 [3,121]（n_steps=35 步取中点，不含闭式对数反解）→ d* ↔ 闭式 d*=2·log(target/A)/log(p_phys/p_th)−1 golden，方法学独立（通用根求解器 vs 闭式反解）")
def _b497_threshold_distance_bisect_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b497(
        p_phys=float(p.get("p_phys", 5e-3)),
        target=float(p.get("target", 1e-15)),
        p_th=float(p.get("p_th", 0.01)),
        A=float(p.get("A", 0.03)),
    ))


@_register_candidate(
    "b498_syndrome_field_trapz_cand",
    "解码器综合症状概率场总权重·二维梯形求积 ∫₀ᵈ∫₀ᵈ exp(−((x−cx)²+(y−cy)²)/(2σ²))dxdy（N×N=1024² 均匀网格，不含 erf 闭式）→ 权重 ↔ 闭式 erf 二维分解 golden，方法学独立（数值求积 vs 闭式）")
def _b498_syndrome_field_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b498(
        d=float(p.get("d", 5.0)),
        sigma=float(p.get("sigma", 1.0)),
        cx=float(p.get("cx", 2.5)),
        cy=float(p.get("cy", 2.5)),
    ))


@_register_candidate(
    "b499_match_cost_moment_trapz_cand",
    "解码器匹配代价二阶矩·一维梯形求积 ∫₀ᴸ x²·(1/L)dx（N=1024 点，不含多项式闭式）→ L²/3 ↔ 闭式 L²/3 golden，方法学独立（数值求积 vs 闭式）")
def _b499_match_cost_moment_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b499(
        L=float(p.get("L", 5.0)),
    ))


@_register_candidate(
    "b500_flag_hook_erfc_trapz_cand",
    "旗比特钩错检测概率·高斯尾一维梯形求积 ∫_{φ_th}^{φ_th+6σ} (1/(σ√(2π)))e^{−φ²/2σ²}dφ（n=65536 点，不含 erfc 闭式）→ P(φ>φ_th) ↔ 闭式 ½·erfc(φ_th/(σ√2)) golden，方法学独立（数值求积 vs 闭式）")
def _b500_flag_hook_erfc_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b500(
        phi_th=float(p.get("phi_th", 2.0)),
        sigma=float(p.get("sigma", 1.0)),
    ))


@_register_candidate(
    "b501_adjacent_syndrome_2d_trapz_cand",
    "相邻稳定子综合征关联·二维梯形求积 ∫₀ᵈ∫₀ᵈ g(x,y)g(x+r,y)dxdy（N×N=512² 均匀网格，不含 erf 闭式）→ 关联 ↔ 闭式 erf² 高斯积 golden，方法学独立（数值求积 vs 闭式）")
def _b501_adjacent_syndrome_2d_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b501(
        d=float(p.get("d", 5.0)),
        sigma=float(p.get("sigma", 1.0)),
        cx=float(p.get("cx", 2.5)),
        cy=float(p.get("cy", 2.5)),
        r=float(p.get("r", 1.0)),
    ))


@_register_candidate(
    "b502_transversal_fid_trapz_cand",
    "transversal CNOT 保真预算链·一维中点求积 ∫₀ᵀ p₀(1+αt+βt²)dt 后 exp（n=1024 点，不含指数积分闭式）→ F ↔ 闭式 exp(−p₀(T+αT²/2+βT³/3)) golden，方法学独立（数值积分 vs 闭式）")
def _b502_transversal_fid_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b502(
        p0=float(p.get("p0", 0.01)),
        alpha=float(p.get("alpha", 0.1)),
        beta=float(p.get("beta", 0.1)),
        T=float(p.get("T", 10.0)),
    ))


@_register_candidate(
    "b503_merge_fid_trapz_cand",
    "lattice surgery 合并保真·一维中点求积 ∫₀ᵈ c(2x²−1)p dx 后 exp（n=1024 点，不含积分闭式）→ F ↔ 闭式 exp(−c·p·(2d³/3−d)) golden，方法学独立（数值积分 vs 闭式）")
def _b503_merge_fid_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b503(
        c=float(p.get("c", 0.01)),
        p=float(p.get("p", 0.01)),
        d=float(p.get("d", 5)),
    ))


@_register_candidate(
    "b504_accumulated_fail_trapz_cand",
    "端到端累计逻辑失效·一维中点求积 ∫₀ᵀ λ(1+βt+γt²)dt 后 1−exp（n=1024 点，不含积分闭式）→ P ↔ 闭式 1−exp(−λ(T+βT²/2+γT³/3)) golden，方法学独立（数值积分 vs 闭式）")
def _b504_accumulated_fail_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b504(
        lam=float(p.get("lam", 1e-3)),
        beta=float(p.get("beta", 0.1)),
        gamma=float(p.get("gamma", 0.001)),
        T=float(p.get("T", 100.0)),
    ))


@_register_candidate(
    "b505_logical_area_trapz_cand",
    "累计逻辑错误面积·一维梯形求积 ∫₀ᴸ(1−e^{−kx})dx（n=1024 点，不含初等闭式）→ 面积 ↔ 闭式 L−(1−e^{−kL})/k golden，方法学独立（数值求积 vs 闭式）")
def _b505_logical_area_trapz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    m = _get_j1_numeric()
    p = getattr(spec, "params", None) or {}
    return float(m.cand_b505(
        k=float(p.get("k", 0.01)),
        L=float(p.get("L", 100.0)),
    ))
