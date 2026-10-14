# -*- coding: utf-8 -*-
"""J4-M0 多参数 NV 传感链（Quantum Sensing System Integration · Layer 4 / 缺口 G-QSYS-1）。

═══ 这是什么 ═══
把 QS 征程的**单参数** NV 磁力计（`qs_m0`：只回答「B 场多少」）升级为**四参数**传感：
一次 ODMR 谱测量同时被 **B / ΔT / E / σ** 四个物理参数调制，读数方程
`b = S·x`（S = 交叉灵敏度矩阵）⇒ 必须**解耦反演** `x = S⁻¹b` 才能得到各参数真值。

    x = [B, ΔT, E, σ]                      4 个待测参数（磁场 / 温度 / 轴向电场 / 应力）
    b = [b₁, b₂, b₃, b₄]                   4 条 ODMR 谱特征的读数偏移
    S = ∂b/∂x                              4×4 交叉灵敏度矩阵（对角线 = 自响应，非对角 = 交叉响应）

═══ 物理链（三段）═══
① **特征灵敏度标度** g_j（物理量纲，设计示例量级）
     g_B    = γ_e      = 28.024 MHz/µT    （NV 电子自旋旋磁比，Zeeman 分裂 Δf = 2γ_e·B）
     g_ΔT   = |dD/dT|  = 74.2 kHz/K       （零场劈裂 D 的温度系数）
     g_E    = dD/dE_⊥  = 17.0 kHz/(kV/cm) （轴向电场 Stark 位移）
     g_σ    = dD/dσ    = 1.4 kHz/MPa      （应力位移，= 1.4 MHz/GPa）
② **无量纲响应矩阵** C（4 条谱特征 × 4 参数）：对角 = 各特征对自身主参数的响应、
   非对角 = 交叉响应。归一化约定 `x_j ≜ g_j·(物理量 j)` ⇒ 读数方程化为 **b = C·x**
   （C 与 `_batch_j4_numeric._C_MP` **同源逐位一致** —— 门禁跨模块判据）。
③ **解耦**：`x̂ = C⁻¹b`（Cramer 闭式）/ Landweber 迭代；`κ(C)` = 条件数（串扰对
   解耦稳定性的量化）；`N_amp` = 解耦噪声放大因子 `‖(C⁻¹)[:,1]‖₂`（列范数）。

═══ 🔴 为什么温度是重点 ═══
QS-M2（`qs_m2.temperature_eta`）把温度当作**噪声源**（`η_temp = |dB/dT|·S_T`，污染
磁灵敏度）；本模块第一次把温度**升为被测量**并给出解耦后的估计 τ̂ ⇒ 这是「温度既是
噪声、又是被测参数」这一多参数传感特有张力的物理落点。

═══ 诚实边界 ═══
· γ_e / dD/dT / dD/dE / dD/dσ 为**文献量级的设计示例**（非任何 foundry 实测标定）；
  响应矩阵 C 的元素为**设计示例**（非实测 ODMR 谱拟合）。
· 只证「闭式解析反演 ⇄ 迭代解耦」数值一致 + 多参数解耦物理链自洽，
  **不作制造/性能宣称**；模型为**一阶线性化**（未建模高阶项、谱线非洛伦兹化、
  参数间非线性耦合）。
· 零商业依赖（纯 numpy + math；零 RNG）。
"""
from __future__ import annotations

import math

import numpy as np

# ══════════════════════════════════════════════════════════════════════
# 物理常量（设计示例量级）
# ══════════════════════════════════════════════════════════════════════
GAMMA_E_HZ_PER_UT = 28.024e6        # Hz/µT —— NV 电子自旋旋磁比（= gμB/h）
DD_DT_HZ_PER_K = -74.2e3            # Hz/K —— 零场劈裂温度系数 dD/dT
DD_DE_HZ_PER_KV_CM = 17.0e3         # Hz/(kV/cm) —— 轴向 Stark 系数 dD/dE_⊥
DD_DSIGMA_HZ_PER_MPA = 1.4e3        # Hz/MPa —— 应力系数 dD/dσ（= 1.4 MHz/GPa）

#: 参数与谱特征命名（顺序固定：B, ΔT, E, σ）
PARAM_NAMES = ("B_uT", "dT_K", "E_kVcm", "sigma_MPa")
FEATURE_NAMES = ("odmr_axial_hi", "odmr_axial_lo", "odmr_tilted", "odmr_transverse")

#: 特征灵敏度标度 g（与 PARAM_NAMES 同序 · 物理量纲）
SENS_SCALE = np.array([GAMMA_E_HZ_PER_UT,
                       abs(DD_DT_HZ_PER_K),
                       DD_DE_HZ_PER_KV_CM,
                       DD_DSIGMA_HZ_PER_MPA], dtype=float)

#: 无量纲响应矩阵 C（4 谱特征 × 4 参数；对角 = 自响应、非对角 = 交叉响应）
#: 🔴 与 `lda_harness._batch_j4_numeric._C_MP` 同源逐位一致（门禁跨模块判据）
_C = np.array([[1.00, 0.25, 0.10, 0.04],
               [0.15, 0.60, 0.08, 0.03],
               [0.06, 0.14, 0.30, 0.05],
               [0.04, 0.08, 0.03, 0.20]], dtype=float)

#: 归一化读数向量 b（设计示例）
_B = np.array([1.00, 0.55, 0.28, 0.17], dtype=float)

_CALIBER = "归一化（各参数以自身特征灵敏度 g_j 为单位）· 一阶线性化 · 设计示例量级"


def assert_caliber(caliber: str) -> None:
    """口径守卫：只接受本模块的统一口径串（防止下游误用其他口径）。"""
    if caliber != _CALIBER:
        raise ValueError("灵敏度口径不符：本模块仅支持 %r" % _CALIBER)


def response_matrix(coupling: float = 1.0) -> "np.ndarray":
    """无量纲交叉响应矩阵 C(coupling) = diag(C) + c·(C − diag(C))。

    c = 0 ⇒ 纯对角（无串扰，解耦退化为逐参数直读）；c = 1 ⇒ 设计示例标准交叉。
    负 coupling 允许（表示交叉符号翻转）但不改变可逆性。
    """
    d = np.diag(np.diag(_C))
    return d + float(coupling) * (_C - d)


def sensitivity_matrix_physical(coupling: float = 1.0) -> "np.ndarray":
    """物理量纲灵敏度矩阵 S_phys = C(c) · diag(g)（4×4，各列单位 = Hz / 参数单位）。"""
    return response_matrix(coupling) @ np.diag(SENS_SCALE)


def condition_number(coupling: float = 1.0) -> float:
    """解耦条件数 κ(C) = σ_max/σ_min（奇异值比）—— 串扰对解耦稳定性的量化。

    κ = 1 ⇒ 完美条件（纯对角）；κ 越大 ⇒ 交叉耦合越强 ⇒ 解耦对读数噪声越敏感。
    """
    sv = np.linalg.svd(response_matrix(coupling), compute_uv=False)
    return float(sv[0] / sv[-1])


def decouple_cramer(coupling: float = 1.0) -> "np.ndarray":
    """闭式解析反演（Cramer 法则 · 手写 4×4 行列式展开）⇒ x̂（4 维）。"""
    S = response_matrix(coupling)
    out = np.zeros(4, dtype=float)
    detS = _det4(S)
    if detS == 0.0:
        raise ValueError("响应矩阵奇异（coupling 取值使 det(S)=0）")
    for j in range(4):
        Sj = S.copy()
        Sj[:, j] = _B
        out[j] = _det4(Sj) / detS
    return out


def decouple_landweber(coupling: float = 1.0, k: int = 320) -> "np.ndarray":
    """Landweber 迭代解耦（固定最优步长 τ* = 2/(λ_min+λ_max) 的梯度下降最小二乘）。"""
    k = int(k)
    if k < 1:
        raise ValueError("迭代步数 k 须 ≥ 1")
    S = response_matrix(coupling)
    ev = np.linalg.eigvalsh(S.T @ S)
    tau = 2.0 / (float(ev[0]) + float(ev[-1]))
    x = np.zeros(4, dtype=float)
    for _ in range(k):
        x = x + tau * (S.T @ (_B - S @ x))
    return x


def decoupling_noise_amplification(coupling: float = 1.0) -> float:
    """解耦噪声放大因子 N_amp = ‖(C⁻¹)[:, 温度列]‖₂（温度参数的解耦噪声增益）。

    N_amp = 1 ⇒ 温度与其余三参数正交（无串扰污染）；N_amp > 1 ⇒ 交叉耦合放大
    了「折算到温度轴上的」读数噪声。
    """
    inv = np.linalg.inv(response_matrix(coupling))
    return float(np.linalg.norm(inv[:, 1]))


def cross_coupling_table(coupling: float = 1.0) -> dict:
    """逐参数对的交叉耦合占比 ρ_ij = |C_ij| / |C_jj|（j = 被串扰的参数）。"""
    S = response_matrix(coupling)
    out = {}
    for i in range(4):
        for j in range(4):
            if i != j:
                out["%s<-%s" % (FEATURE_NAMES[i], PARAM_NAMES[j])] = \
                    float(abs(S[i, j]) / abs(S[j, j]))
    return out


def multiparam_report(coupling: float = 1.0, k: int = 320) -> dict:
    """多参数解耦总装报告（解耦解 / 条件数 / 噪声放大 / 交叉耦合 / 签核）。"""
    x_closed = decouple_cramer(coupling)
    x_iter = decouple_landweber(coupling, k)
    resid_iter = float(np.linalg.norm(x_iter - x_closed))
    kappa = condition_number(coupling)
    n_amp = decoupling_noise_amplification(coupling)
    tau_hat = float(x_closed[1])
    # 签核：解耦残差小 ∧ 条件数有限 ∧ 噪声放大有限 ∧ 温度分量正
    verdict = "ACCEPT" if (resid_iter < 1e-6 and kappa < 20.0
                           and n_amp < 3.0 and tau_hat > 0.0) else "REJECT"
    return {
        "caliber": _CALIBER,
        "coupling": float(coupling),
        "iter_steps": int(k),
        "x_closed_form": [float(v) for v in x_closed],
        "x_landweber": [float(v) for v in x_iter],
        "tau_hat_temperature": tau_hat,
        "decoupling_residual": resid_iter,
        "condition_number": kappa,
        "noise_amplification_temperature": n_amp,
        "cross_coupling": cross_coupling_table(coupling),
        "verdict": verdict,
    }


# ── 自检 ────────────────────────────────────────────────────────────────
def _det3(m) -> float:
    return float(m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                 - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                 + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _det4(M) -> float:
    d = 0.0
    for j in range(4):
        minor = [[float(M[r][c]) for c in range(4) if c != j] for r in range(1, 4)]
        d += ((-1.0) ** j) * float(M[0][j]) * _det3(minor)
    return float(d)


def selfcheck_qs_j4() -> dict:
    """J4-M0 自检（全项 PASS 才算通过）。"""
    checks = {}

    S = response_matrix(1.0)
    checks["response_diag_matches_C"] = bool(np.allclose(np.diag(S), np.diag(_C), atol=0.0))
    checks["response_offdiag_scaled"] = bool(abs(S[0, 1] - 0.25) < 1e-15)
    checks["c0_is_pure_diagonal"] = bool(np.allclose(np.abs(
        response_matrix(0.0) - np.diag(np.diag(_C))), 0.0, atol=1e-15))
    # c=0 ⇒ 纯对角 ⇒ κ = 对角展布 max/min = 1.00/0.20 = 5.0（不是 1 —— 对角元素本身不同）
    checks["cond_c0_equals_diag_spread"] = bool(
        abs(condition_number(0.0) - 1.0 / 0.20) < 1e-10)
    checks["cond_c1_gt_one"] = bool(condition_number(1.0) > 1.0)
    checks["cond_monotone_in_coupling"] = bool(condition_number(1.0) > condition_number(0.5))
    checks["strict_diag_dominant"] = bool(all(
        abs(S[i, i]) > sum(abs(S[i, j]) for j in range(4) if j != i) for i in range(4)))

    # 解耦正确性：S·x̂ = b（回代）
    x_closed = decouple_cramer(1.0)
    checks["closed_form_reconstructs_b"] = bool(
        np.allclose(S @ x_closed, _B, atol=1e-12))
    # 迭代解耦收敛到闭式解
    x_iter = decouple_landweber(1.0, 320)
    checks["landweber_converges_to_closed"] = bool(
        float(np.linalg.norm(x_iter - x_closed)) < 1e-6)
    # 迭代残差随步数单调下降
    r64 = float(np.linalg.norm(decouple_landweber(1.0, 64) - x_closed))
    r320 = float(np.linalg.norm(decouple_landweber(1.0, 320) - x_closed))
    checks["landweber_residual_decreases"] = bool(r320 < r64)

    checks["noise_amp_ge_one"] = bool(decoupling_noise_amplification(1.0) >= 1.0)
    checks["noise_amp_grows_with_coupling"] = bool(
        decoupling_noise_amplification(1.0) > decoupling_noise_amplification(0.5))

    tbl = cross_coupling_table(1.0)
    checks["cross_coupling_table_nonzero"] = bool(len(tbl) == 12 and all(
        v > 0.0 for v in tbl.values()))

    rep = multiparam_report(1.0, 320)
    checks["report_verdict_accept"] = bool(rep["verdict"] == "ACCEPT")
    checks["report_tau_positive"] = bool(rep["tau_hat_temperature"] > 0.0)
    checks["report_residual_small"] = bool(rep["decoupling_residual"] < 1e-6)

    # 反向探针：非法步数 / 错口径 / 耦合强度零响应 ⇒ 必抛或必变
    checks["reverse_iteration_not_identity"] = bool(
        float(np.linalg.norm(decouple_landweber(1.0, 64) - x_closed)) > 1e-3)
    checks["reverse_coupling_changes_solution"] = bool(
        abs(float(decouple_cramer(0.0)[1]) - float(decouple_cramer(1.0)[1])) > 1e-3)
    checks["reverse_bad_k_raises"] = _raises(lambda: decouple_landweber(1.0, 0))
    checks["reverse_bad_caliber_raises"] = _raises(lambda: assert_caliber("wrong"))

    return checks


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    sc = selfcheck_qs_j4()
    bad = 0
    print("=" * 64)
    print("J4-M0 多参数解耦自检：")
    for k, v in sc.items():
        ok = bool(v)
        bad += 0 if ok else 1
        print("  [%s] %s" % ("PASS" if ok else "FAIL", k))
    print("=" * 64)
    print("ALL PASS" if bad == 0 else "%d FAIL" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
