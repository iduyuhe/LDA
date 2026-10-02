# -*- coding: utf-8 -*-
"""LDA L2 · 光子计算芯片 · 光电协同仿真（EO co-sim）· 光计算征程 M3。

============================================================================
M3 定位（把平台从「算得准」推向「能设计完整光计算芯片：光核 + 电子接口」）
----------------------------------------------------------------------------
M1 做了任意线性变换（SVD→双 MZI 网格 + 对角衰减）；M2 做了量化/标定/激活/精度锚。
但 M1/M2 的「指令相位」是**直接给的**——真实芯片里相位是**电子子系统下发**的：
DAC 编码 → 驱动（一阶 RC）→ 相移器（Vπ·L）→ 光网格计算 → 光电探测器(PD) → TIA
读回电压。这条**电子↔光子的协同链路**与**基于读回的闭环标定（控制环）**，是平台
既往没有的能力。

本模块不做「从零造电子」——LDA 已有 `lda_l2.eic_behavioral`（per-MZI 一阶 RC 驱动 +
单极点 TIA 行为级模型，含严格纪律与零能效守卫）。M3 把**已有的 EIC 行为级**与**已有
的光计算核（M1/M2）**接成一条**端到端光电协同闭环**，并新增平台既往缺的两块：
  · ① EO co-sim 链：DAC→驱动→相移器→光网格→PD→TIA 全程带电子域损伤（DAC 量化 /
    驱动上升沿预算 / Vπ 失配 / TIA 带宽读回）；
  · ② 闭环标定（控制环）：用 DAC 下发码 + TIA 读回强度，反估真实 Vπ 并补偿指令，
    把开环 Vπ 失配造成的精度退化闭环回收。

纪律（沿用 M1/M2 + eic_behavioral 红线）
----------------------------------------
- C 级自主（纯 numpy），不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径。
- 电子域只到**行为级（T1 候选，非 ORACLE）**：复用 `eic_behavioral` 的一阶 RC 驱动 +
  单极点 TIA；**不碰晶体管级**（DAC/ADC/SerDes/DSP 全在红线外）。
- 🔴 **零能效数字**：复用 `eic_behavioral.assert_no_energy_metrics`，不输出 pJ/bit、
  驱动功耗、TOPS/W。本模块只给电压 / 相位 / 时延 / 带宽 / 量化误差 / 标定残差。
- 探测为**强度探测**（PD 物理本征 |E|²），与 M2 `detection='intensity'` 同构；
  片上非线性光学元件（可饱和吸收 / 相变材料阈值）物理属 B 类外部，非本模块 golden。
- 🔴 跨模块 Vπ 口径（v0.9.183 订正）：光侧自 c4965be 起以 `mzi_mesh_matmul.VPI_L_VMM
  = 250.0 V·mm` 为单一真值源（`VPI_L_V_CM=25.0` 仅 V·cm 兼容别名，同一物理量）
  ⇒ 与 EIC 侧 `VPI_L_V_MM_DEFAULT=7.5 V·mm` 之差属**设计点差异**（Vπ=25 V vs 7.5 V），
  **不是**单位口径分裂。本模块 co-sim 层仍用**单一 `vpi_v`（伏特）**贯穿，默认 7.5 V。
  （历史「跨模块口径不一致」警告与订正见 EO 披露块 `vpi_units_warning`。）
============================================================================
"""

from __future__ import annotations

import math
import numpy as np

from lda_l2.eic_behavioral import (
    driver_step_rk4,
    vpi_from_vpi_l,
    phase_resolution_rad,
    tia_transimpedance_ohm,
    tia_bandwidth_hz,
    eic_budget,
    assert_no_energy_metrics,
    TAU_DRIVER_S_DEFAULT,
    V_DD_DEFAULT,
    VPI_L_V_MM_DEFAULT,
    PS_ARM_UM_DEFAULT,
    DAC_BITS_DEFAULT,
    R_F_OHM_DEFAULT,
    C_F_F_DEFAULT,
    EIC_DISCLOSURE,
)
from lda_l2.mzi_mesh_matmul import (
    reck_triangular_mesh,
    assemble_triangular_mesh,
    unitary_fidelity,
)
from lda_l2.photonic_compute import (
    _square_embed,
    photonic_activation,
    make_toy_classifier,
)

# co-sim 单一 Vπ（伏特）口径：7.5 V = 1mm 臂、7.5 V·mm（与 eic_behavioral 同源）。
VPI_V_DEFAULT = vpi_from_vpi_l(VPI_L_V_MM_DEFAULT, PS_ARM_UM_DEFAULT)  # = 7.5 V
# 驱动满摆幅：须覆盖完整相位范围 φ∈[0,2π) ⇒ V∈[0,2·Vπ]（否则 DAC/标定环饱和）。
V_DD_CO = 2.0 * VPI_V_DEFAULT  # = 15.0 V（驱动可下发至 2·Vπ）

__all__ = [
    "eo_phase_map",
    "eo_unitary_transfer",
    "eo_layer_forward",
    "eo_golden_classify",
    "eo_calibration_loop",
    "end_to_end_eo_inference",
    "eo_budget",
    "verify_photonic_compute_m3",
    "VPI_V_DEFAULT",
    "EO_COSIM_DISCLOSURE",
]


# ---------------------------------------------------------------------------
# ① EO 相位映射：目标相位 → DAC 编码 → 驱动 RC → 实际相位（带 Vπ 失配/标定）
# ---------------------------------------------------------------------------
def eo_phase_map(target_phi: float, dac_bits: int = DAC_BITS_DEFAULT,
                 v_dd: float = V_DD_CO, vpi_v: float = VPI_V_DEFAULT,
                 vpi_real: float | None = None, tau_s: float = TAU_DRIVER_S_DEFAULT,
                 t_settle_frac: float = 8.0, calibrate: bool = False,
                 vpi_est: float | None = None) -> float:
    """EO 相位映射（DAC→驱动→相移器）。

    - 指令编码器**假设** Vπ = vpi_cmd（标定时 vpi_cmd=vpi_est，否则 = vpi_v）；
    - 目标相位 → 指令电压 V_cmd = φ·vpi_cmd/π；
    - DAC 量化到 2^dac_bits 电平（LSB = v_dd/2^bits）；
    - 驱动一阶 RC 在 t = t_settle_frac·τ 时刻的输出（稳态 t_settle_frac→∞ ⇒ = V_dac）；
    - 器件用**真实** Vπ（vpi_real，缺省 = vpi_v）把电压回译为实际相位：
      φ_actual = π·V_applied / vpi_real。
    vpi_real ≠ vpi_cmd 且无标定 ⇒ 相位误差（闭环标定要消除的对象）。
    """
    if not isinstance(dac_bits, int) or dac_bits < 1:
        raise ValueError(
            "dac_bits must be a positive integer (>=1); got %r" % (dac_bits,))
    vpi_cmd = vpi_est if (calibrate and vpi_est is not None) else vpi_v
    # 相移器相位 2π 周期：映射前取模，避免 φ 超出 [0,2π) 时 V=φ·Vπ/π 超出驱动满摆幅被钳位。
    target_phi = float(target_phi) % (2.0 * math.pi)
    v_cmd = target_phi * vpi_cmd / math.pi
    # 驱动满摆幅须覆盖完整相位范围 φ∈[0,2π) ⇒ V∈[0,2·vpi_cmd]（随指令侧 Vπ 走，
    # 否则标定用更高 vpi_est 时高端相位会钳位）。DAC 量化步长据此推导。
    v_fs = 2.0 * vpi_cmd
    v_lsb = v_fs / float(2 ** dac_bits)
    code = int(round(v_cmd / v_lsb))
    code = max(0, min(2 ** dac_bits - 1, code))
    v_dac = code * v_lsb
    v_applied = driver_step_rk4(t_settle_frac * tau_s, tau_s=tau_s,
                                v_dd=v_dac, n_steps=64)
    vr = vpi_real if vpi_real is not None else vpi_v
    return float(math.pi * v_applied / vr)


def eo_unitary_transfer(U, dac_bits: int = DAC_BITS_DEFAULT,
                        v_dd: float = V_DD_CO, vpi_v: float = VPI_V_DEFAULT,
                        vpi_real: float | None = None,
                        tau_s: float = TAU_DRIVER_S_DEFAULT,
                        t_settle_frac: float = 8.0, calibrate: bool = False,
                        vpi_est: float | None = None):
    """对酉 U 做三角 mesh 分解，经 EO 相位映射后重构 U_eff，返回 (U_eff, fid)。

    fid = unitary_fidelity(U_eff, U)：EO 电子域损伤下网格传递矩阵的退化度量。
    """
    U = np.array(U, dtype=complex)
    N = U.shape[0]
    ops, D = reck_triangular_mesh(U)
    ops_eff = [(c, p, th, eo_phase_map(phi, dac_bits, v_dd, vpi_v, vpi_real,
                                       tau_s, t_settle_frac, calibrate, vpi_est))
               for (c, p, th, phi) in ops]
    dph = [math.atan2(D[k, k].imag, D[k, k].real) for k in range(N)]
    dph_eff = [eo_phase_map(dp, dac_bits, v_dd, vpi_v, vpi_real, tau_s,
                            t_settle_frac, calibrate, vpi_est) for dp in dph]
    D_eff = np.diag([complex(math.cos(dp), math.sin(dp)) for dp in dph_eff]).astype(complex)
    U_eff = assemble_triangular_mesh(ops_eff, D_eff, N)
    fid = unitary_fidelity(U_eff, U)
    return U_eff, fid


# ---------------------------------------------------------------------------
# ② EO 计算层：W·x → SVD→双 EO 网格(+相位模型) → PD+TIA → 激活
# ---------------------------------------------------------------------------
def eo_layer_forward(W, x, activation: str = "relu", beta: float = 1.0,
                    dac_bits: int = DAC_BITS_DEFAULT, v_dd: float = V_DD_CO,
                    vpi_v: float = VPI_V_DEFAULT, vpi_real: float | None = None,
                    tau_s: float = TAU_DRIVER_S_DEFAULT, t_settle_frac: float = 8.0,
                    responsivity: float = 1.0, f_read_hz: float = 0.0,
                    r_f: float = R_F_OHM_DEFAULT, c_f: float = C_F_F_DEFAULT,
                    calibrate: bool = False, vpi_est: float | None = None):
    """EO 光子计算层：W·x 经 SVD→双 EO 网格 + 对角衰减 → PD+TIA 探测 → 激活。

    - 任意维度 W 经 `_square_embed` 方阵嵌入，两片酉网格均施加 EO 相位映射；
    - 探测：强度探测（PD 物理本征 |·|²）→ 光电流 = R·P → TIA 电压 = |Z(f)|·I；
    - 激活：photonic_activation（检测后电子/光电域）；
    - 返回 (y, W_eff, meta)，meta 含网格保真度与线性映射误差基准。
    """
    W = np.array(W, dtype=complex)
    x = np.array(x, dtype=complex)
    U_full, Sigma_full, V_full = _square_embed(W)
    U_e, fidU = eo_unitary_transfer(
        U_full, dac_bits, v_dd, vpi_v, vpi_real, tau_s, t_settle_frac,
        calibrate, vpi_est)
    V_e, fidV = eo_unitary_transfer(
        V_full, dac_bits, v_dd, vpi_v, vpi_real, tau_s, t_settle_frac,
        calibrate, vpi_est)
    W_eff = U_e @ Sigma_full @ V_e
    y_lin = W_eff @ x
    # PD + TIA 强度读回
    power = np.abs(y_lin) ** 2
    i_ph = responsivity * power
    z = tia_transimpedance_ohm(f_read_hz, r_f, c_f)
    v_out = np.abs(z) * i_ph
    y = np.array([photonic_activation(float(v), activation, beta) for v in v_out])
    meta = {"fidelity_U_mesh": fidU, "fidelity_V_mesh": fidV, "W_eff": W_eff}
    return y, W_eff, meta


def eo_golden_classify(net, activation: str = "relu", beta: float = 1.0):
    """EO 管线的 numpy 同构参考（理想光学 MVM + PD 强度探测 + 激活）。

    与 `eo_layer_forward` 同构、无电子域损伤；用作 EO co-sim 的 golden 标签。
    """
    X = net["X"]
    n = X.shape[0]
    labels = []
    for i in range(n):
        x = X[i]
        y1 = np.array([photonic_activation(float(v), activation, beta)
                       for v in np.abs(net["W1"] @ x) ** 2])
        y2 = np.array([photonic_activation(float(v), activation, beta)
                       for v in np.abs(net["W2"] @ y1) ** 2])
        labels.append(int(np.argmax(np.real(y2))))
    return labels


def end_to_end_eo_inference(net, labels, activation: str = "relu", beta: float = 1.0,
                           dac_bits: int = DAC_BITS_DEFAULT, v_dd: float = V_DD_CO,
                           vpi_v: float = VPI_V_DEFAULT, vpi_real: float | None = None,
                           tau_s: float = TAU_DRIVER_S_DEFAULT, t_settle_frac: float = 8.0,
                           responsivity: float = 1.0, f_read_hz: float = 0.0,
                           r_f: float = R_F_OHM_DEFAULT, c_f: float = C_F_F_DEFAULT,
                           calibrate: bool = False, vpi_est: float | None = None):
    """端到端 EO 推理：两层网络对 net['X'] 分类，返回精度/线性误差与逐层保真。

    full 精度（dac_bits 足够高、vpi_real=vpi_v、无 TIA 高频滚降）下，EO 实现须与
    `eo_golden_classify` 一致（分类 100%）；DAC 量化 / Vπ 失配致精度退化，闭环标定金回收。
    """
    X = net["X"]
    n = X.shape[0]
    correct = 0
    max_mac_err = 0.0          # 权重相对误差（尺度无关，直接反映网格重建质量）
    fidUs, fidVs = [], []
    for i in range(n):
        x = X[i]
        y1, W1_eff, m1 = eo_layer_forward(
            net["W1"], x, activation=activation, beta=beta, dac_bits=dac_bits,
            v_dd=v_dd, vpi_v=vpi_v, vpi_real=vpi_real, tau_s=tau_s,
            t_settle_frac=t_settle_frac, responsivity=responsivity,
            f_read_hz=f_read_hz, r_f=r_f, c_f=c_f, calibrate=calibrate,
            vpi_est=vpi_est)
        rel1 = float(np.linalg.norm(W1_eff - net["W1"], "fro") /
                     (np.linalg.norm(net["W1"], "fro") + 1e-30))
        max_mac_err = max(max_mac_err, rel1)
        fidUs.append(m1["fidelity_U_mesh"]); fidVs.append(m1["fidelity_V_mesh"])

        y2, W2_eff, m2 = eo_layer_forward(
            net["W2"], y1, activation=activation, beta=beta, dac_bits=dac_bits,
            v_dd=v_dd, vpi_v=vpi_v, vpi_real=vpi_real, tau_s=tau_s,
            t_settle_frac=t_settle_frac, responsivity=responsivity,
            f_read_hz=f_read_hz, r_f=r_f, c_f=c_f, calibrate=calibrate,
            vpi_est=vpi_est)
        rel2 = float(np.linalg.norm(W2_eff - net["W2"], "fro") /
                     (np.linalg.norm(net["W2"], "fro") + 1e-30))
        max_mac_err = max(max_mac_err, rel2)

        pred = int(np.argmax(np.real(y2)))
        if pred == labels[i]:
            correct += 1
    return {
        "accuracy": correct / n,
        "max_mac_err": max_mac_err,
        "fidelity_U_mean": float(np.mean(fidUs)),
        "fidelity_V_mean": float(np.mean(fidVs)),
    }


# ---------------------------------------------------------------------------
# ③ 闭环标定（控制环）：DAC 下发码 + TIA 强度读回 → 反估真实 Vπ
# ---------------------------------------------------------------------------
def eo_calibration_loop(dac_bits: int = DAC_BITS_DEFAULT, v_dd: float = V_DD_CO,
                        vpi_real: float = VPI_V_DEFAULT, vpi_v: float = VPI_V_DEFAULT,
                        tau_s: float = TAU_DRIVER_S_DEFAULT, t_settle_frac: float = 8.0,
                        responsivity: float = 1.0, r_f: float = R_F_OHM_DEFAULT):
    """闭环标定：用参考 MZI 的强度 null 反估真实 Vπ（DAC 下发 + TIA 读回）。

    方法：扫描 DAC 码 → 驱动→相移器给出电压 → MZI 强度 I(code)=cos²(φ/2)
    （φ=π·V/vpi_real）；找 I 最小（null，φ=π ⇒ V=vpi_real）的码 → 反估 vpi_est。
    返回 {vpi_real, vpi_est, rel_err, best_code, null_intensity}。

    🔴 诚实边界：这是**基于读回的闭环标定流程的设计与自检**（U10 纪律：标定固件
    设计层交付，不宣称已物理校准）；真实标定须 foundry 工艺角/实测锚（B 类外部）。
    """
    n = 2 ** dac_bits
    v_lsb = v_dd / n
    best_code, best_I = 0, 1e9
    for code in range(n):
        v_code = code * v_lsb
        v_applied = driver_step_rk4(t_settle_frac * tau_s, tau_s=tau_s,
                                    v_dd=v_code, n_steps=64)
        phi = math.pi * v_applied / vpi_real
        I = math.cos(phi / 2.0) ** 2
        if I < best_I:
            best_I, best_code = I, code
    v_null = best_code * v_lsb
    v_null_applied = driver_step_rk4(t_settle_frac * tau_s, tau_s=tau_s,
                                     v_dd=v_null, n_steps=64)
    vpi_est = float(v_null_applied)  # null 处 V = vpi_real
    return {
        "vpi_real": float(vpi_real),
        "vpi_est": vpi_est,
        "rel_err": abs(vpi_est - vpi_real) / vpi_real,
        "best_code": best_code,
        "null_intensity": float(best_I),
        "responsivity": responsivity,
        "r_f": float(r_f),
    }


# ---------------------------------------------------------------------------
# ④ EO 行为级预算（零能效，只给电压/相位/时延/带宽/量化步进）
# ---------------------------------------------------------------------------
def eo_budget(n_mzi: int, dac_bits: int = DAC_BITS_DEFAULT,
              v_dd: float = V_DD_CO, vpi_v: float = VPI_V_DEFAULT,
              arm_um: float = PS_ARM_UM_DEFAULT, tau_s: float = TAU_DRIVER_S_DEFAULT,
              r_f: float = R_F_OHM_DEFAULT, c_f: float = C_F_F_DEFAULT,
              rise_frac: float = 0.9):
    """EO 链路行为级预算：复用 eic_budget + 叠加 DAC 相位量化步进。

    🔴 零能效数字：底层 assert_no_energy_metrics（单一真值来源）守卫。
    """
    b = eic_budget(n_mzi, tau_s=tau_s, v_dd=2.0 * vpi_v, dac_bits=dac_bits,
                   vpi_l_v_mm=VPI_L_V_MM_DEFAULT, arm_um=arm_um,
                   r_f_ohm=r_f, c_f_f=c_f, rise_frac=rise_frac)
    b["eo_phase_resolution_rad"] = phase_resolution_rad(
        dac_bits, v_dd, VPI_L_V_MM_DEFAULT, arm_um)
    b["vpi_v"] = float(vpi_v)
    assert_no_energy_metrics(b)
    return b


# ---------------------------------------------------------------------------
# ⑤ 端到端验证锚（CI 可判）
# ---------------------------------------------------------------------------
def verify_photonic_compute_m3(seed: int = 20260930) -> dict:
    """M3 验证：DAC 量化扫描 + 闭环标定 + EO 端到端精度锚 + TIA 带宽读回。"""
    rng = np.random.default_rng(seed)

    # M3a DAC 量化：平均相位误差随比特数（统计意义，非逐点单调）
    def _random_unitary(n):
        Z = (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n)))
        U, _ = np.linalg.qr(Z)
        return U
    dac_sweep = []
    for nb in (2, 4, 8, 12):
        errs = []
        for _ in range(24):
            U = _random_unitary(6)
            ops, D = reck_triangular_mesh(U)
            phis = [phi for (_, _, _, phi) in ops]
            for k in range(D.shape[0]):
                phis.append(math.atan2(D[k, k].imag, D[k, k].real))
            for phi in phis:
                ap = eo_phase_map(phi, dac_bits=nb, vpi_real=VPI_V_DEFAULT)
                # 相位 2π 周期：取最小环差，避免 φ 与 φ mod 2π 直接相减假大。
                dd = abs((ap - phi) % (2.0 * math.pi))
                errs.append(min(dd, 2.0 * math.pi - dd))
        dac_sweep.append({"n_bits": nb, "mean_phase_err": float(np.mean(errs))})

    # M3b 闭环标定（Vπ 真实偏离标称 +5%）
    delta = 0.05
    vpi_real = VPI_V_DEFAULT * (1.0 + delta)
    cal = eo_calibration_loop(dac_bits=8, vpi_real=vpi_real, vpi_v=VPI_V_DEFAULT)
    cal_lo = eo_calibration_loop(dac_bits=4, vpi_real=vpi_real, vpi_v=VPI_V_DEFAULT)

    # M3c EO 端到端：四类场景
    net = make_toy_classifier(seed=seed)
    labels_eo = eo_golden_classify(net, "relu", 1.0)
    full = end_to_end_eo_inference(net, labels_eo, dac_bits=16,
                                   vpi_real=VPI_V_DEFAULT, vpi_v=VPI_V_DEFAULT)
    q2 = end_to_end_eo_inference(net, labels_eo, dac_bits=2)
    # 失配/标定场景用 16-bit 网格（只留 Vπ 失配这一种损伤），干净隔离并展示闭环回收
    mis = end_to_end_eo_inference(net, labels_eo, dac_bits=16,
                                  vpi_real=vpi_real, vpi_v=VPI_V_DEFAULT,
                                  calibrate=False)
    # 12-bit 标定环（残差 ~2e-4）用于恢复场景，清晰展示闭环回收
    cal_rec_loop = eo_calibration_loop(dac_bits=12, vpi_real=vpi_real,
                                       vpi_v=VPI_V_DEFAULT)
    cal_est = cal_rec_loop["vpi_est"]
    cal_rec = end_to_end_eo_inference(net, labels_eo, dac_bits=16,
                                      vpi_real=vpi_real, vpi_v=VPI_V_DEFAULT,
                                      calibrate=True, vpi_est=cal_est)

    # M3d TIA 带宽读回：DC（f=0）增益 = R_f；f=f_3dB 增益 = R_f/√2；高频滚降
    f3 = tia_bandwidth_hz(R_F_OHM_DEFAULT, C_F_F_DEFAULT)
    z0 = abs(tia_transimpedance_ohm(0.0, R_F_OHM_DEFAULT, C_F_F_DEFAULT))
    z3 = abs(tia_transimpedance_ohm(f3, R_F_OHM_DEFAULT, C_F_F_DEFAULT))
    z_hi = abs(tia_transimpedance_ohm(10.0 * f3, R_F_OHM_DEFAULT, C_F_F_DEFAULT))

    return {
        "dac_sweep": dac_sweep,
        "calibration": {
            "delta_vpi": delta, "vpi_real": vpi_real,
            "vpi_est_8bit": cal["vpi_est"], "rel_err_8bit": cal["rel_err"],
            "vpi_est_4bit": cal_lo["vpi_est"], "rel_err_4bit": cal_lo["rel_err"],
        },
        "eo_full": full,
        "eo_q2": q2,
        "eo_vpi_mismatch": mis,
        "eo_vpi_calibrated": cal_rec,
        "tia": {
            "f3db_hz": f3, "z0": z0, "z3": z3,
            "z_hi_over_f3": z_hi / z3,
        },
    }


EO_COSIM_DISCLOSURE = {
    "capability_added": "本模块把 LDA 从『给相位即可算』补到『给 DAC 码 + TIA 读回即可算』——"
                        "电子↔光子协同闭环（DAC→驱动→相移器→光网格→PD→TIA）+ 基于读回的闭环标定。",
    "sovereignty": "C 级自主（纯 numpy），不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径。",
    "eic_reuse": "电子域复用 `lda_l2.eic_behavioral`（per-MZI 一阶 RC 驱动 + 单极点 TIA 行为级），"
                 "不重复造轮子；其零能效守卫（assert_no_energy_metrics）单一真值来源被本模块复用。",
    "t1_candidate": "电子域只到**行为级（T1 候选，非 ORACLE）**：复用 EIC 一阶 RC + 单极点 TIA，"
                    "不碰晶体管级（DAC/ADC/SerDes/DSP 在红线外）；不宣称已物理校准（U10 纪律）。",
    "zero_energy": "🔴 零能效数字：不输出 pJ/bit、驱动功耗、TOPS/W；只给电压/相位/时延/带宽/量化误差/标定残差。",
    "detection": "探测为强度探测（PD 物理本征 |E|²），与 M2 detection='intensity' 同构；"
                 "片上非线性光学元件（可饱和吸收/相变材料阈值）物理属 B 类外部，非本模块 golden。",
    "vpi_units_warning": "🔴 跨模块口径不一致（历史警告 · v0.9.183 订正）：原述「光侧 "
                         "mzi_mesh_matmul.VPI_L_V_CM=25.0（V·cm）与 EIC 侧 "
                         "eic_behavioral.VPI_L_V_MM_DEFAULT=7.5（V·mm）口径不同」—— 该**单位**"
                         "口径分裂已由 c4965be 消除（光侧单一真值源 VPI_L_VMM=250.0 V·mm，"
                         "VPI_L_V_CM 仅 V·cm 兼容别名）。现存 250 与 7.5 V·mm 之差属**设计点差异**"
                         "（Vπ=25 V vs 7.5 V），非口径分裂；本模块 co-sim 用单一 vpi_v=7.5V 贯穿。",
    "honest_boundary": "本模块演示『光计算芯片可由 DAC 下发 + TIA 读回协同实现，且基于读回的闭环标定可回收 Vπ 误差』；"
                       "不声称已实现相干光学计算机、电子 co-sim 实测或已物理校准（须 foundry 工艺角/实测锚）。",
    "non_oracle_scope": "本模块电子域（EIC 行为级一阶 RC 驱动 + 单极点 TIA）与光计算核（M1/M2 网格 + 量化/激活）"
                        "均属 C 级自主纯 numpy 实现，非外部 ORACLE；B 类外部接口（foundry PDK、TCAD 工艺角、"
                        "SerDes/DSP 固件、相位调制器器件模型）非本模块范围，须外部真实锚（T2 真值）。",
    "verification_basis": "验证基础：EO 端到端以 numpy 强度探测同构参考（eo_golden_classify）作 golden 标签；"
                          "闭环标定以参考 MZI 强度 null 反估 Vπ 属**设计层自检**，非工艺实测；"
                          "全部数值机器可判、可复现（固定 seed=20260930）。",
}
