# -*- coding: utf-8 -*-
"""验证适配器 · 分片 4/6（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

覆盖原文件 L3218..L4636（110 个顶层定义）。正文**逐字节**取自原文，不重排、不重格式化。
🔴 装配顺序由 `verification_adapters.py` 的 import 次序决定，勿单独调整。
"""

from __future__ import annotations

from ._adapter_core import (
    _get_batch_b, _get_batch_b2, _get_batch_b28, _get_batch_b3, _get_batch_b4, _get_batch_b5,
    _get_batch_b6, _get_batch_b7, _get_batch_b8, _register_candidate,
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
