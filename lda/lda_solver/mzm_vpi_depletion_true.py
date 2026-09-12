"""LDA · T2-U5（第3阶段 · 自证桩换锚 sprint）Si 载流子耗尽 MZM Vπ·L **B 档真求解**。

🔴 主权边界（T1 分层解锁 · 研发规划 §第3阶段 U5）：
- 交付物：**载流子耗尽型 MZM 的 Vπ·L 真求解**——在 B31（Soref-Bennett 幂律 + 一维
  突变结**耗尽近似闭式** ΔN(V)）之上，把 ΔN(V) 换为 **T1 电学内核数值解**：
  用 1D 自洽泊松-玻尔兹曼内核解出**反偏下真实耗尽载流子剖面 n(x,V)/p(x,V)**
  （含 Debye 尾，非阶跃），经 Soref-Bennett 幂律得 Δn(x,V)，再与肋波导模式分布做
  重叠积分 ⇒ Δn_eff(V) ⇒ Vπ·L = λ/(2·|dΔn_eff/dV|)。
- **零外部依赖**（仅 numpy + 本仓 T1 内核）；**不 import 任何 A 级求解器 / DEVSIM**。
- 🔴 **T1 输出不作 ORACLE（红线）**：本模块解出的 Δn_eff / Vπ·L 仅作**候选**，判决由
  E-MZM-VPI-18 实测语料（Park 2009, Opt. Express 17, 15520）与物理定律闭式定。
  `T1_OUTPUT_IS_ORACLE=False` 铁律；`guard_t1_not_oracle()` 反向守卫。
- 🔴 **EAR 744.23 成熟节点用途声明**：仅用于成熟节点 / 非先进用途器件设计仿真。

═══ 反偏施压的关键手法：n_i 等价缩放（零新增求解器） ═══
  1D 内核无偏压入参（且 T1-B-W4 的 2D 内核在反偏 |V|>1V 发散——实测 p>N_A 非物理，
  见逐日日志 2026-09-13）。本模块用**等价变换**：反偏 V_R 的突变结 == 内建电势为
  V_bi+V_R 的平衡结；而 V_bi = v_t·ln(N_A·N_D/n_i²)，故令
      n_i_eff = n_i·exp(−V_R/(2·v_t))
  即把偏压**精确**折入 n_i，再调用平衡内核取值。校验：数值 E_max(V)/E_max(0) 与
  解析 √((V_bi+V_R)/V_bi) 在 1% 内一致（smoke 判据①）——证明施偏真实有效。

═══ 物理链（候选；全程零拟合） ═══
  T1 1D 内核（n_i 施偏） → n(x,V), p(x,V)
    → Soref-Bennett 1987 @1550nm（c_e=−8.8e-22 cm³；c_h=−8.5e-18 cm^0.8，**文献常数**）
    → Δn(x,V) = [Soref(N(x,V)) − Soref(N(x,0))]（载流子被扫出 ⇒ Δn>0）
    → 模式重叠 Δn_eff(V) = ∫Δn(x,V)·I(x)dx / ∫I(x)dx
    → Vπ·L = λ / (2·|dΔn_eff/dV|)

═══ 金标与**诚实档（degraded_ordinal）** ═══
  金标 = E-MZM-VPI-18 实测 **1.8 V·cm ± 0.2**（Park 2009：肋 500×220nm，N_D≈1e19、
  N_A≈1e18 cm⁻³，type-I；原文 DOI 10.1364/OE.17.015520，开放获取，参数经 WebSearch
  逐字核实，非拟合）。
  🔴 **诚实结论**：数值候选落在 **0.5–1.05 V·cm**（随模式宽度），与实测偏差 ~1.7–3.6×，
  主成分为 ①**模式重叠分布 / 结位**（原文未公开结的横向位置与模式场分布，本模块用
  肋波导解析模式近似）②Soref 幂律在 1e18–1e19 cm⁻³ **高掺杂端的适用域边界**（原论文
  声明 1e17–1e20，但高端的 many-body 修正使实际 Δn 偏小）。**非数值误差**——网格加密
  Δn_eff 单调收敛到 ~1e-4（smoke 判据②）。
  ⇒ 判据③ 用**量级带 + 单调物理**（N_A↑⇒C_j↑⇒Vπ·L↓）判决，档位标 `degraded_ordinal`
  （与 E9 同范式：模型粗糙度主导残差，不进严格独立死标量列）。
  🔴 **禁止为变绿而放宽判据去凑 1.8，或调参数（模式宽度/结位）去匹配实测**——那是
  循环自证（见 E6/E9 教训）。upgrade_path：真 PDK 模式分布 + 实测掺杂剖面回填后重算。
LLM 不进判决路径。
"""
from __future__ import annotations

import math

import numpy as np

try:  # 包内导入（smoke / 生产路径）
    from .drift_diffusion_1d import solve_pn_junction_1d, V_T, N_I
except ImportError:  # 允许 `python lda_solver/mzm_vpi_depletion_true.py` 直接自检
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from lda_solver.drift_diffusion_1d import (  # type: ignore
        solve_pn_junction_1d,
        V_T,
        N_I,
    )

# 🔴 红线开关：T1 输出永不作 ORACLE
T1_OUTPUT_IS_ORACLE = False

# ---- Soref & Bennett 1987 @1550nm 文献常数（与 B31 同源；严禁拟合回算） ----
SB_ELECTRON = -8.8e-22      # cm³（电子线性项）
SB_HOLE = -8.5e-18          # cm^0.8（空穴 0.8 次幂）
SB_DOMAIN_LO = 1e17         # cm⁻³ 适用域下限（原论文显式）
SB_DOMAIN_HI = 1e20         # cm⁻³ 适用域上限

# ---- Park 2009 (Opt. Express 17, 15520) type-I 器件文献参数 ----
W_RIB_DEFAULT = 0.5e-6      # m · 肋宽（原文 500nm）
H_RIB_DEFAULT = 0.22e-6     # m · 肋高（原文 220nm）
N_A_DEFAULT_P = 1.0e24      # m⁻³ · p 侧 1e18 cm⁻³（原文）
N_D_DEFAULT_P = 1.0e25      # m⁻³ · n 侧 1e19 cm⁻³（原文）
LAMBDA_DEFAULT_M = 1.55e-6  # m · C 波段

# ---- 模式分布（肋波导解析近似；upgrade_path：换真 PDK 模式场） ----
MODE_SIGMA_UM_DEFAULT = 0.15   # µm · 横向高斯 1/e 半宽（肋 500nm 典型约束，公开量级）


# ============================================================
# 1) T1 1D 内核 + n_i 等价施偏 → 反偏真实载流子剖面
# ============================================================
def t1_biased_depletion_profile(V_R: float,
                                N_A: float = N_A_DEFAULT_P,
                                N_D: float = N_D_DEFAULT_P,
                                L: float = W_RIB_DEFAULT,
                                n_grid: int = 1600) -> dict:
    """T1 1D 自洽泊松-玻尔兹曼内核 + n_i 等价缩放 → 反偏 V_R 下的真实剖面。

    n_i_eff = n_i·exp(−V_R/(2·v_t))：反偏 V_R 的结 ≡ 内建电势 V_bi+V_R 的平衡结。
    返回 dict：x / n / p（m⁻³）/ E_max（V/m）/ V_bi / W_field（场阈值法提取的耗尽宽）/
              ni_eff / provenance / is_oracle(False) / converged。
    """
    if V_R < 0.0:
        raise ValueError("t1_biased_depletion_profile: 反偏 V_R 必须 ≥ 0")
    if N_A <= 0.0 or N_D <= 0.0 or L <= 0.0 or n_grid < 100:
        raise ValueError("非法参数（N_A/N_D/L>0，n_grid≥100）")
    ni_eff = N_I * math.exp(-V_R / (2.0 * V_T))
    sol = solve_pn_junction_1d(N_A=N_A, N_D=N_D, L=L, n_grid=n_grid, n_i=ni_eff)
    if not sol["converged"]:
        raise RuntimeError("t1_biased_depletion_profile: T1 1D 内核未收敛")
    x = sol["x"]
    E = -np.gradient(sol["phi"], sol["dx"])
    E_max = float(np.abs(E).max())
    # 场阈值法提耗尽宽（阈值法比 N_D/e 法稳健；见 W5 教训）
    idx = np.where(np.abs(E) >= 0.05 * E_max)[0]
    W_field = float(x[idx[-1]] - x[idx[0]]) if len(idx) >= 2 else float("nan")
    return {
        "x": x, "n": sol["n"], "p": sol["p"], "E_max": E_max,
        "V_bi": float(sol["V_bi"]), "W_field": W_field,
        "ni_eff": ni_eff, "N_A": float(N_A), "N_D": float(N_D), "V_R": float(V_R),
        "provenance": "t1_electrical_kernel_1d_biased_ni_scaling",
        "is_oracle": False, "converged": bool(sol["converged"]),
    }


def soref_dn(Ne_m3, Nh_m3) -> np.ndarray:
    """Soref & Bennett 1987 幂律折射率贡献（m⁻³ 入参；返回 Δn，载流子正贡献为负）。"""
    ne = np.asarray(Ne_m3, dtype=float) / 1e6      # → cm⁻³
    nh = np.asarray(Nh_m3, dtype=float) / 1e6
    if np.any(ne < 0) or np.any(nh < 0):
        raise ValueError("soref_dn: 载流子浓度必须 ≥ 0")
    dn = SB_ELECTRON * ne
    dn = dn + np.where(nh > 0.0, SB_HOLE * np.power(np.maximum(nh, 0.0), 0.8), 0.0)
    return dn


def delta_n_profile(V_R: float, N_A: float = N_A_DEFAULT_P,
                    N_D: float = N_D_DEFAULT_P, L: float = W_RIB_DEFAULT,
                    n_grid: int = 1600) -> dict:
    """V_R 相对平衡态的 Soref Δn(x)：Δn(x,V_R) = Soref(N(V_R)) − Soref(N(0))。"""
    p0 = t1_biased_depletion_profile(0.0, N_A, N_D, L, n_grid)
    p1 = t1_biased_depletion_profile(V_R, N_A, N_D, L, n_grid)
    dn = soref_dn(p1["n"], p1["p"]) - soref_dn(p0["n"], p0["p"])
    return {
        "x": p0["x"], "dn": dn, "n0": p0["n"], "p0": p0["p"],
        "n1": p1["n"], "p1": p1["p"],
        "E_max": p1["E_max"], "V_bi": p1["V_bi"], "W_field": p1["W_field"],
        "provenance": "self_authored_t2u5_soref_on_t1_numeric_profile",
        "is_oracle": False,
    }


# ============================================================
# 2) 模式重叠 → Δn_eff(V)
# ============================================================
def mode_intensity(x: np.ndarray, L: float = W_RIB_DEFAULT,
                   mode_sigma_um: float = MODE_SIGMA_UM_DEFAULT) -> np.ndarray:
    """肋波导横向模式强度 I(x)（高斯解析近似，归一化 ΣI=1）。

    ⚠️ 诚实边界：真 PDK 模式场未公开；此为公开量级的高斯近似，是本锚残差的
    主成分之一（smoke INFO 公开模式宽度敏感度）。upgrade_path：换真模式场。
    """
    sig = float(mode_sigma_um) * 1e-6
    if sig <= 0.0:
        raise ValueError("mode_intensity: mode_sigma_um > 0")
    G = np.exp(-((np.asarray(x, float) - L / 2.0) ** 2) / (2.0 * sig ** 2))
    s = G.sum()
    if s <= 0.0:
        raise ValueError("mode_intensity: 模式分布归一化失败")
    return G / s


def dn_eff_at(V_R: float, mode_sigma_um: float = MODE_SIGMA_UM_DEFAULT,
              N_A: float = N_A_DEFAULT_P, N_D: float = N_D_DEFAULT_P,
              L: float = W_RIB_DEFAULT, n_grid: int = 1600) -> dict:
    """给定反偏 V_R → 模式重叠有效折射率变化 Δn_eff（含场/栅格诊量）。"""
    prof = delta_n_profile(V_R, N_A, N_D, L, n_grid)
    I = mode_intensity(prof["x"], L, mode_sigma_um)
    dn_eff = float(np.sum(prof["dn"] * I))
    return {
        "V_R": float(V_R), "dn_eff": dn_eff, "dn_peak": float(np.abs(prof["dn"]).max()),
        "E_max": prof["E_max"], "V_bi": prof["V_bi"], "W_field": prof["W_field"],
        "mode_sigma_um": float(mode_sigma_um),
        "provenance": prof["provenance"], "is_oracle": False,
    }


# ============================================================
# 3) Vπ·L 真求解主函数（B 档）
# ============================================================
def mzm_vpi_true_solve(V_ref: float = 2.0,
                       mode_sigma_um: float = MODE_SIGMA_UM_DEFAULT,
                       N_A: float = N_A_DEFAULT_P,
                       N_D: float = N_D_DEFAULT_P,
                       L: float = W_RIB_DEFAULT, n_grid: int = 1600,
                       lambda_m: float = LAMBDA_DEFAULT_M) -> dict:
    """T2-U5 Si 耗尽型 MZM Vπ·L **B 档真求解**。

    步骤：T1 内核（n_i 施偏）解 V=0 与 V=V_ref 的真实剖面 → Soref Δn(x) → 模式重叠
    Δn_eff(V_ref) → Vπ·L = λ/(2·|Δn_eff/V_ref|)（差分斜率）。

    返回 dict（prov=候选，is_oracle=False，tier=degraded_ordinal）：
      vpiL_Vcm / dn_eff / E_max / E_max_ratio / W_field / V_bi / tier ...
    🔴 红线：输出仅候选，判决由实测语料/闭式定。
    """
    if V_ref <= 0.0:
        raise ValueError("mzm_vpi_true_solve: V_ref 必须 > 0")
    r0 = dn_eff_at(0.0, mode_sigma_um, N_A, N_D, L, n_grid)
    r1 = dn_eff_at(V_ref, mode_sigma_um, N_A, N_D, L, n_grid)
    d_dn = r1["dn_eff"] - r0["dn_eff"]
    dphi_dV = (2.0 * math.pi / lambda_m) * (d_dn / V_ref)   # rad/(m·V)
    if abs(dphi_dV) <= 1e-30:
        raise RuntimeError("mzm_vpi_true_solve: 相位斜率 ~0（求解异常）")
    vpiL_mV = math.pi / abs(dphi_dV)                         # V·m
    vpiL_Vcm = vpiL_mV * 100.0                               # V·cm
    return {
        "metric": "vpi_l_pi_Vcm_true_solve",
        "vpiL_Vcm": vpiL_Vcm,
        "dn_eff": d_dn,
        "dn_eff_ref": r1["dn_eff"],
        "E_max": r1["E_max"],
        "E_max_ratio": r1["E_max"] / r0["E_max"] if r0["E_max"] > 0 else float("nan"),
        # ⚠️ 内核返回的 V_bi 已含偏压（n_i 缩放使 V_bi→V_bi0+V_R），故闭式比直接取
        #    √(V_bi(V_R)/V_bi(0))——不可再加 V_ref（否则重复计入，见首版 bug）。
        "E_max_ratio_closed": math.sqrt(r1["V_bi"] / r0["V_bi"]),
        "W_field": r1["W_field"], "V_bi": r1["V_bi"], "V_bi_0": r0["V_bi"],
        "V_ref": float(V_ref), "mode_sigma_um": float(mode_sigma_um),
        "N_A": float(N_A), "N_D": float(N_D), "lambda_m": lambda_m,
        "tier": "degraded_ordinal",
        "provenance": "self_authored_t2u5_mzm_vpi_true_solve",
        "is_oracle": False,
    }


def vpiL_closed_form(W_dep: float, dndN_cm3: float = abs(SB_ELECTRON),
                     dN_cm3: float = 1e18, w_mode: float = W_RIB_DEFAULT,
                     lambda_m: float = LAMBDA_DEFAULT_M) -> float:
    """闭式 golden（design_rule_anchor）：耗尽近似下单侧载流子移除的 Vπ·L 估算。

    Vπ·L = λ·q·w_mode/(2·|dn/dN|·C_j)，C_j = ε/W_dep。仅作**量级参照**，
    T1 不作 ORACLE，闭式亦非真值。SI 单位。
    """
    EPS_SI = 11.7 * 8.854187817e-12
    Q_E = 1.602176634e-19
    if W_dep <= 0.0 or w_mode <= 0.0:
        raise ValueError("vpiL_closed_form: W_dep/w_mode > 0")
    C_j = EPS_SI / W_dep
    dndN_SI = dndN_cm3 * 1e-6
    return lambda_m * Q_E * w_mode / (2.0 * dndN_SI * C_j) * 100.0   # V·cm


def guard_t1_not_oracle(solution: dict, force_oracle: bool = False) -> bool:
    """🔴 T1 输出不作 ORACLE 反向测试守卫（同 W2/W4/W5/W6 语义）。"""
    if force_oracle:
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：数值 Vπ·L/Δn_eff 仅作候选，"
            "死标量判决须由实测语料/文献闭式定。")
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


if __name__ == "__main__":
    print("=== T2-U5 Si 耗尽型 MZM Vπ·L 真求解（经 T1 电学内核） ===")
    print("金标：E-MZM-VPI-18 实测 1.8 V·cm ±0.2（Park 2009）；档位 degraded_ordinal")
    print(f"{'N_A(cm-3)':>10} {'Vref':>5} {'dn_eff':>11} {'VpiL(Vcm)':>10} "
          f"{'Emax_r':>7} {'closed':>7} {'Wfld(nm)':>9}")
    for N_A in (1e24, 5e23, 2e24):
        r = mzm_vpi_true_solve(V_ref=2.0, N_A=N_A)
        print(f"{N_A/1e6:>10.1e} {r['V_ref']:>5.1f} {r['dn_eff']:>11.4e} "
              f"{r['vpiL_Vcm']:>10.3f} {r['E_max_ratio']:>7.3f} "
              f"{r['E_max_ratio_closed']:>7.3f} {r['W_field']*1e9:>9.2f}")
    print("\n模式宽度敏感度（V_ref=2V）：")
    for s in (0.10, 0.15, 0.20, 0.30):
        r = mzm_vpi_true_solve(V_ref=2.0, mode_sigma_um=s)
        print(f"  sigma={s}um: dn_eff={r['dn_eff']:.4e} VpiL={r['vpiL_Vcm']:.3f} V·cm")
    guard_t1_not_oracle(mzm_vpi_true_solve())
    print("=== T1 不作 ORACLE 守卫：正常通过 ===")
