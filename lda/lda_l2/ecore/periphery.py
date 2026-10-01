# -*- coding: utf-8 -*-
"""ecore · E14 · **行驱动外设 + 端到端系统链**（把「设计链」补成「系统链」）。

============================================================================
为什么存在
----------------------------------------------------------------------------
E1–E13 里，交叉阵列的行线一直是**理想电压源**直接钉住（`crossbar_mvm.py` 的
`ckt.vsource(rown[i], 0, inputs[i])`）—— 没有输出阻抗、没有建立时间、没有驱动能力约束。
真实芯片里行线由**行驱动器**（单位增益缓冲 / 源跟随）驱动，而驱动器的
**闭环输出电阻 `R_oc`** 会与行线电阻**串联累加** ⇒ 直接改变 E9 的 IR drop 与**可及规模上界**。

本模块做三件事：
  ① **行驱动闭式**：`v_load = v_in·A/(1 + A + R_ol/R_L)`（**精确解**，不是两次分压的近似 ——
     推导见 `buffered_row_voltage`；它同时含**增益误差** `A/(1+A)` 与**闭环输出电阻** `R_ol/(1+A)`）。
  ② 🔴 **把 `R_oc` 串进 E9 的三对角 IR-drop 模型** ⇒ 重算**可及规模上界**。
     **这是本段最有价值的系统级结论：器件级参数第一次反馈到规模律。**
  ③ **端到端系统链**：`DAC → 行驱动 → 阵列 → TIA → ADC` 的**系统误差分解** ⇒
     发现**行系统项**（驱动负载调整引入的按行增益误差，**不会被 MC 平均掉** ⇒ 同 E8 的列系统项同型）。

🔴 方法学
  golden = 闭式（分压 / 三对角 IR-drop / 数字全精度矩阵乘）；
  与 E9 **交叉核对**：`R_oc = 0` 时本模块的三对角解必须与 `array_scale.row_line_profile`
  **逐位一致**（极限一致性 ⇒ 证明不是另起一套模型）。
  与闭式的**电路级**核对：行驱动建 MNA 真实电路（VCVS 闭环 + 开环输出电阻 + 负载）⟷ 闭式。

🔴 诚实边界
  行驱动器用 **VCVS（理想电压控制电压源）+ 开环输出电阻** 的**宏模型**，**非晶体管级运放**
  （E2 已证朴素 NMOS 差分对无法闭合高增益环路）；阵列用 E2 已验证的解析列电流模型
  （MNA 一致性已在 E2/E7 判据内）；参数公开典型量级占位（非 PDK）；不报 TOPS/TOPS-W/fJ/op。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .mna import Circuit
from .mosfet import NmosParams

try:                                        # 与 E7 寄生同源（取 r_seg / g 的默认口径）
    from . import parasitic as PA
except ImportError:                         # pragma: no cover
    PA = None                               # type: ignore

try:
    from . import array_scale as AS
except ImportError:                         # pragma: no cover
    AS = None                               # type: ignore

__all__ = [
    "PERIPHERY_PROCESS", "buffer_closed_loop_gain", "buffer_closed_loop_rout",
    "buffered_row_voltage", "row_driver_mna_check", "vcvs_polarity_fact",
    "row_line_profile_with_driver",
    "max_scale_with_driver", "driver_scale_table", "row_load_conductance",
    "system_chain", "row_system_error", "PERIPHERY_DISCLOSURE",
    "periphery_self_check",
]

# ═══════════════════════════ 默认量（公开典型量级占位）═══════════════════════════
PERIPHERY_PROCESS = {
    "a_gain": 1.0e3,          # 缓冲器开环增益 A（典型运放量级）
    "r_out_open_ohm": 1.0e3,  # 开环输出电阻（闭环后 /(1+A)）
    "vfs_v": 1.0,             # DAC 满量程（行驱动输入摆幅）
    "vdd_v": 3.0,
}


def _p(key: str, override: Optional[dict] = None):
    if override and key in override:
        return override[key]
    return PERIPHERY_PROCESS[key]


# ═══════════════════════ ① 行驱动闭式（精确解）═══════════════════════
def buffer_closed_loop_gain(a_gain: float = 1.0e3) -> float:
    """单位增益缓冲的**闭环增益** `A/(1+A)`（空载）。"""
    a = float(a_gain)
    if a <= 0:
        raise ValueError("开环增益须 > 0")
    return a / (1.0 + a)


def buffer_closed_loop_rout(r_out_open_ohm: float = 1.0e3,
                            a_gain: float = 1.0e3) -> float:
    """闭环输出电阻 `R_oc = R_ol/(1+A)`（**反馈把输出阻抗降 (1+A) 倍**）。"""
    a = float(a_gain)
    if a <= 0:
        raise ValueError("开环增益须 > 0")
    return float(r_out_open_ohm) / (1.0 + a)


def buffered_row_voltage(v_in: float, a_gain: float = 1.0e3,
                         r_out_open_ohm: float = 1.0e3,
                         r_load_ohm: float = 1.0e3) -> float:
    """**行驱动负载电压（精确闭式）**：`v_load = v_in·A/(1 + A + R_ol/R_L)`。

    推导（单位增益缓冲 · 反馈端接输出节点）：
      运放输出 `v_o1 = A(v_in − v_load)`；`i = (v_o1 − v_load)/R_ol = v_load/R_L`
      ⇒ `A·v_in − A·v_load − v_load = v_load·R_ol/R_L`
      ⇒ **`v_load = v_in·A/(1 + A + R_ol/R_L)`**。
    该式同时包含两个真实效应：
      · **增益误差** `A/(1+A)`（空载极限）；
      · **负载调整**：分母多出 `R_ol/R_L`（等价于闭环输出电阻 `R_oc = R_ol/(1+A)` 与负载分压）。
    """
    a = float(a_gain)
    rl = float(r_load_ohm)
    if a <= 0 or rl <= 0:
        raise ValueError("A 与 R_L 须 > 0")
    r_ol = float(r_out_open_ohm)
    return float(v_in) * a / (1.0 + a + r_ol / rl)


def row_driver_mna_check(v_in: float = 0.8, a_gain: float = 1.0e3,
                         r_out_open_ohm: float = 1.0e3,
                         r_load_ohm: float = 1.0e3) -> Dict:
    """**电路级核对**：建真实 MNA 电路（VCVS 闭环 + 开环输出电阻 + 负载）⟷ 闭式。

    电路：`vsource(in,0,v_in)` · `VCVS(o1,0, 反馈差分, A)` · `R_ol: o1→load` · `R_L: load→0`。

    🔴🔴 **E14 发现的平台缺陷（已登记 · 本段不修 mna）**：
      `mna.Circuit.vcvs` 的 **docstring 声明** `V(out_p)−V(out_n) = gain·(V(ctl_p)−V(ctl_n))`，
      但 `_stamp_dc` 的 E 分支写的是 `A[ix,cp] += gain; A[ix,cn] -= gain`（移项后等价于
      **`V_out = gain·(V(ctl_n) − V(ctl_p))`**）⇒ **实际极性与声明相反**。
      ⇒ 本函数**把 `ctl_p` / `ctl_n` 对调**以得到所推导的负反馈：
      `vcvs(O1, 0, LOAD, IN, A)` 实际给出 `V_O1 = A·(V_IN − V_LOAD)` ✓。
      · **为什么不直接修 `mna.py`**：E1–E13 全部已上线数字（含 E2 的 ideal-TIA 虚地电路）
        建立在现有行为上（查 E2/E3 判据：TIA 虚地是 `|A|→∞` 的**极限**，符号只改变放大器输出的
        定向，不改变虚地机制 ⇒ 功能等价、结论仍成立）；改动会**静默改变平台语义**且可能让
        多段判据变红 —— 按保护性约束（同 `NmosParams` 默认值）**不改**，改为**适配 + 显式登记**。
      · 自检 ⑨ 把这个事实**锁死**：若未来有人"顺手改正"，判据会红并提示适配过期。
    """
    ckt = Circuit("rowdrv")
    IN, O1, LOAD = 1, 2, 3
    ckt.vsource(IN, 0, float(v_in), "VIN")
    ckt.vcvs(O1, 0, LOAD, IN, float(a_gain), "EA")   # ← ctl 对调（见上方登记）
    ckt.resistor(O1, LOAD, float(r_out_open_ohm), "RO")
    ckt.resistor(LOAD, 0, float(r_load_ohm), "RL")
    ckt.resistor(0, 0, 1.0e9, "dummy")
    x = ckt.solve_dc()
    v_load = float(ckt.node_voltages(x)[LOAD])
    closed = buffered_row_voltage(v_in, a_gain, r_out_open_ohm, r_load_ohm)
    return {"v_load_mna_v": v_load, "v_load_closed_form_v": closed,
            "rel_err": abs(v_load - closed) / abs(closed) if closed else float("inf"),
            "a_gain": float(a_gain),
            "closed_loop_gain": buffer_closed_loop_gain(a_gain),
            "r_out_closed_ohm": buffer_closed_loop_rout(r_out_open_ohm, a_gain),
            "is_oracle": False}


def vcvs_polarity_fact() -> Dict:
    """**登记并锁定** `mna.Circuit.vcvs` 的实际极性（E14 发现）。

    用一个最小电路取证：`vsource(in,0,+1)` + `vcvs(out,0, in, 0, A)`。
      · docstring 声明 ⇒ `V_out = +A`
      · 实际行为（本函数实测） ⇒ `V_out = −A`
    返回 `polarity_inverted=True` 即表示「**实际与声明相反**」。
    """
    ckt = Circuit("vcvs_probe")
    IN, OUT = 1, 2
    ckt.vsource(IN, 0, 1.0, "V1")
    ckt.vcvs(OUT, 0, IN, 0, 1000.0, "E1")
    ckt.resistor(0, 0, 1.0e9, "dummy")
    x = ckt.solve_dc()
    v_out = float(ckt.node_voltages(x)[OUT])
    return {"v_out_with_ctl_p_positive": v_out,
            "docstring_expected": 1000.0,
            "polarity_inverted": bool(v_out < 0.0),
            "note": "docstring 声明 V_out = gain·(V_cp−V_cn)，实际 _stamp_dc 给出 "
                    "gain·(V_cn−V_cp) —— **已登记 · 本段不修 mna（保护 E1–E13 已上线数字）**",
            "is_oracle": False}


# ═══════════════════════ ② R_oc 耦合的 IR-drop（三对角）═══════════════════════
def row_line_profile_with_driver(n: int, r_seg: float, g: float,
                                 r_out_cl_ohm: float, v_in: float = 1.0) -> Dict:
    """**带驱动输出电阻**的行线剖面（O(N) 三对角）。

    与 E9 `row_line_profile` 的唯一差别在**首端边界**：
      E9（理想源）：`V_0 = v_in`
      本版（`R_oc > 0`）：`−(1 + (1+gr)/ρ)·V_0 + (1/ρ)·V_1 = −v_in`，`ρ = r_seg/R_oc`
    🔴 **`R_oc = 0` 时取极限 ⇒ `V_0 = v_in`（与 E9 逐位一致）** —— 这是与 E9 的**极限交叉核对**。
    """
    if n <= 0:
        raise ValueError("n 须 > 0")
    if g <= 0.0 or r_seg < 0.0:
        raise ValueError("g 须 > 0、r_seg 须 ≥ 0")
    v_in = float(v_in)
    r_oc = float(r_out_cl_ohm)
    if r_oc < 0:
        raise ValueError("R_oc 须 ≥ 0")
    if n == 1 or r_seg == 0.0:
        vs = np.full(n, v_in)
        return {"voltages": vs, "far_end_v": v_in, "far_drop_rel": 0.0,
                "avg_rel_err": 0.0, "gr": g * r_seg, "r_out_cl_ohm": r_oc}

    gr = g * float(r_seg)
    lower = np.zeros(n); diag = np.zeros(n); upper = np.zeros(n); rhs = np.zeros(n)
    if r_oc == 0.0:                             # 理想源极限 ⇒ 与 E9 完全同构
        diag[0], rhs[0] = 1.0, v_in
    else:
        rho = float(r_seg) / r_oc
        diag[0] = -(1.0 + (1.0 + gr) / rho)
        upper[0] = 1.0 / rho
        rhs[0] = -v_in
    for k in range(1, n - 1):
        lower[k], diag[k], upper[k] = 1.0, -(2.0 + gr), 1.0
    lower[n - 1], diag[n - 1] = 1.0, -(1.0 + gr)

    cp = np.zeros(n); dp = np.zeros(n)
    cp[0] = upper[0] / diag[0]; dp[0] = rhs[0] / diag[0]
    for k in range(1, n):
        m_ = diag[k] - lower[k] * cp[k - 1]
        cp[k] = upper[k] / m_
        dp[k] = (rhs[k] - lower[k] * dp[k - 1]) / m_
    x = np.zeros(n)
    x[-1] = dp[-1]
    for k in range(n - 2, -1, -1):
        x[k] = dp[k] - cp[k] * x[k + 1]

    return {"voltages": x, "far_end_v": float(x[-1]),
            "far_drop_rel": (v_in - float(x[-1])) / v_in if v_in else 0.0,
            "avg_rel_err": 1.0 - float(np.mean(x)) / v_in if v_in else 0.0,
            "gr": gr, "r_out_cl_ohm": r_oc,
            "v_head_v": float(x[0])}


def max_scale_with_driver(budget_rel_err: float, r_seg: float, g: float,
                          r_out_cl_ohm: float = 0.0, hi: int = 4096) -> int:
    """给定误差预算，二分反解**可及最大行数 N**（带驱动输出电阻）。"""
    f = lambda nn: row_line_profile_with_driver(nn, r_seg, g, r_out_cl_ohm)["avg_rel_err"]  # noqa: E731
    if f(2) > budget_rel_err:
        return 1
    lo, hi_i = 2, int(hi)
    if f(hi_i) <= budget_rel_err:
        return hi_i
    while lo < hi_i - 1:
        mid = (lo + hi_i) // 2
        if f(mid) <= budget_rel_err:
            lo = mid
        else:
            hi_i = mid
    return lo


def driver_scale_table(r_seg: float, g: float, budget_rel_err: float = 0.05,
                       r_out_list: Sequence[float] = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0),
                       n_probe: int = 18) -> Dict:
    """**驱动输出电阻 ⇒ 可及规模上界**扫描表（本段核心系统结论）。"""
    rows = []
    for r_oc in r_out_list:
        nmax = max_scale_with_driver(budget_rel_err, r_seg, g, float(r_oc))
        prof = row_line_profile_with_driver(n_probe, r_seg, g, float(r_oc))
        rows.append({"r_out_cl_ohm": float(r_oc),
                     "n_max": int(nmax),
                     "avg_rel_err_at_probe": float(prof["avg_rel_err"]),
                     "far_drop_rel_at_probe": float(prof["far_drop_rel"]),
                     "v_head_at_probe": float(prof["v_head_v"])})
    ns = [r["n_max"] for r in rows]
    return {"budget_rel_err": float(budget_rel_err), "r_seg_ohm": float(r_seg),
            "g_siemens": float(g), "n_probe": int(n_probe), "rows": rows,
            "monotone_shrink": all(ns[i] <= ns[i - 1] for i in range(1, len(ns))),
            "n_max_ideal": int(ns[0]), "n_max_worst": int(ns[-1]),
            "is_oracle": False}


# ═══════════════════════ ③ 端到端系统链 ═══════════════════════
def row_load_conductance(g_row: Sequence[float]) -> float:
    """一行的**等效负载电导** = `Σ_j g_ij`（列端理想虚地 ⇒ 行看进去是并联电导）。"""
    return float(np.sum(np.asarray(g_row, dtype=float)))


def system_chain(g_matrix, x_digital, vfs: float = 1.0, rf: float = 1.0e4,
                 a_gain: float = 1.0e3, r_out_open_ohm: float = 1.0e3,
                 dac_bits: int = 0, adc_bits: int = 0) -> Dict:
    """**端到端系统链**：`DAC → 行驱动 → 阵列 → TIA → ADC`。

    · DAC：理想闭式 `v = vfs·x`（真电路已由 `converter` 覆盖）；
    · **行驱动**：`v_row_i = buffered_row_voltage(v_dac_i, A, R_ol, 1/Σ_j g_ij)`
      ⇒ **按行负载调整**（行负载随行权重和变化 ⇒ **行增益误差**）；
    · 阵列：`I_j = Σ_i g_ij·v_row_i`（E2 已验证的列电流模型）；
    · TIA：`v_out_j = −rf·I_j`；
    · ADC：均匀量化（真 SAR 见 `converter`）。
    golden = `−rf·(G @ (vfs·x))`（E3 的数字全精度通路）。
    """
    G = np.asarray(g_matrix, dtype=float)
    x = np.asarray(x_digital, dtype=float)
    nr, nc = G.shape
    if x.shape[0] != nr:
        raise ValueError("x 长度须 == G 行数")
    v_dac = float(vfs) * x
    r_ol = float(r_out_open_ohm)
    v_row, load_err = np.zeros(nr), np.zeros(nr)
    for i in range(nr):
        g_row = float(np.sum(G[i, :]))
        r_load = 1.0 / g_row if g_row > 0 else float("inf")
        v_row[i] = buffered_row_voltage(v_dac[i], a_gain, r_ol, r_load)
        ideal_row = v_dac[i] * buffer_closed_loop_gain(a_gain)
        load_err[i] = (v_row[i] - ideal_row) / ideal_row if ideal_row else 0.0
    i_col = G.T @ v_row
    v_out = -float(rf) * i_col
    v_out_golden = -float(rf) * (G.T @ v_dac)
    if dac_bits and int(dac_bits) > 0:
        v_dac_q = np.round(v_dac / (float(vfs) / (1 << int(dac_bits)))) \
            * (float(vfs) / (1 << int(dac_bits)))
        v_row = np.zeros(nr)
        for i in range(nr):
            g_row = float(np.sum(G[i, :]))
            r_load = 1.0 / g_row if g_row > 0 else float("inf")
            v_row[i] = buffered_row_voltage(v_dac_q[i], a_gain, r_ol, r_load)
        v_out = -float(rf) * (G.T @ v_row)
    if adc_bits and int(adc_bits) > 0:
        fs = float(np.max(np.abs(v_out_golden))) if np.max(np.abs(v_out_golden)) > 0 else 1.0
        q = fs / (1 << int(adc_bits))
        v_out_used = np.clip(np.round(v_out / q) * q, -fs, fs)
    else:
        v_out_used = v_out
    rel = np.abs(v_out_used - v_out_golden) / np.maximum(np.abs(v_out_golden), 1e-30)
    return {
        "n_rows": nr, "n_cols": nc,
        "v_dac": v_dac, "v_row": v_row, "row_load_rel_err": load_err,
        "v_out": v_out_used, "v_out_golden": v_out_golden,
        "max_rel_err": float(np.max(rel)), "mean_rel_err": float(np.mean(rel)),
        "max_row_load_rel_err": float(np.max(np.abs(load_err))),
        "spread_row_load_rel_err": float(np.max(load_err) - np.min(load_err)),
        "dac_bits": int(dac_bits), "adc_bits": int(adc_bits),
        "is_oracle": False,
    }


def row_system_error(g_matrix, x_digital, **kw) -> Dict:
    """**行系统项**度量：驱动负载调整引入的**按行增益误差**（MC 平均不掉）。

    对照实验（同 E8 的"判据必须只对被测机制敏感"纪律）：
      · `with_driver`：真驱动（含 R_ol）⇒ 行增益逐行不同；
      · `ideal_driver`：R_ol = 0 ⇒ 行增益全部 = `A/(1+A)`（**行间一致**）。
    ⇒ 判据 = 两次的**行增益离散度**：前者 ≫ 后者（且理想驱动下离散度为 0）。
    """
    G = np.asarray(g_matrix, dtype=float)
    x = np.asarray(x_digital, dtype=float)
    real = system_chain(G, x, **kw)
    kw2 = dict(kw)
    kw2["r_out_open_ohm"] = 0.0
    ideal = system_chain(G, x, **kw2)
    return {
        "with_driver_spread": real["spread_row_load_rel_err"],
        "ideal_driver_spread": ideal["spread_row_load_rel_err"],
        "max_row_load_rel_err": real["max_row_load_rel_err"],
        "row_errors": real["row_load_rel_err"],
        "is_oracle": False,
    }


PERIPHERY_DISCLOSURE: dict = {
    "route": "电子计算征程 E14 · 行驱动外设 + 端到端系统链",
    "capability": "单位增益缓冲闭式（增益误差 + 闭环输出电阻）· R_oc 耦合三对角 IR-drop · "
                  "可及规模上界重算 · 端到端系统链误差分解（含行系统项）",
    "golden": "分压闭式 v_in·A/(1+A+R_ol/R_L) · 三对角 IR-drop（E9 同构）· 数字全精度矩阵乘",
    "cross_check": "① 行驱动建 **MNA 真实电路**（VCVS 闭环 + R_ol + R_L）⟷ 闭式；"
                   "② **R_oc = 0 时三对角解 ⟷ E9 `array_scale.row_line_profile` 逐位一致**（极限一致性）",
    "honest_boundary": "行驱动器为 **VCVS（理想压控源）+ 开环输出电阻的宏模型，非晶体管级运放**"
                       "（E2 已证朴素 NMOS 差分对无法闭合高增益环路）；阵列用 E2 已验证的解析列电流模型；"
                       "参数为公开典型量级占位（非 PDK）；无建立时间/摆率/输出级非线性建模；"
                       "不做流片 · **不报 TOPS/TOPS-W/fJ/op**。"
                       "🔴 **平台缺陷登记**：`mna.Circuit.vcvs` 的**实际极性与 docstring 相反**"
                       "（`_stamp_dc` 给 `V_out = gain·(V_cn−V_cp)`）—— 本段**适配 + 登记、不改 mna**"
                       "（E1–E13 全部已上线数字建立其上）；E2 ideal-TIA 的虚地是 `|A|→∞` 极限，"
                       "符号只改变放大器输出定向、不改变虚地机制 ⇒ 既有结论仍成立。",
    "redline": "红线 = 分层口径；LLM 不进判决路径；C 级自主（纯 numpy/标准库，零商业 SPICE）",
}


# ═══════════════════════════ 自检 ═══════════════════════════
def periphery_self_check(verbose: bool = True) -> bool:
    msgs: List[Tuple[str, bool, str]] = []

    def chk(name, cond, det=""):
        msgs.append((name, bool(cond), det))
        return bool(cond)

    ok = True

    # ① 行驱动闭式 ⟷ MNA 真实电路（方法学独立）
    c1 = row_driver_mna_check(0.8, 1.0e3, 1.0e3, 1.0e3)
    ok &= chk("① 行驱动闭式 ⟷ **MNA 真实电路**（VCVS 闭环 + R_ol + R_L · rel < 1e-9）",
              c1["rel_err"] < 1e-9,
              "MNA=%.9f ⟷ 闭式 %.9f（rel=%.2e · R_oc=%.3f Ω）"
              % (c1["v_load_mna_v"], c1["v_load_closed_form_v"], c1["rel_err"],
                 c1["r_out_closed_ohm"]))

    # ② 反馈降输出阻抗：(1+A) 倍
    r_oc = buffer_closed_loop_rout(1.0e3, 1.0e3)
    ok &= chk("② 闭环输出电阻 R_oc = R_ol/(1+A)（反馈降输出阻抗 1+A 倍）",
              abs(r_oc - 1.0e3 / 1001.0) < 1e-9,
              "R_ol=1000 Ω · A=1000 ⇒ R_oc=%.6f Ω" % r_oc)

    # ③ 负载调整单调：R_L ↓ ⇒ 负载电压 ↓
    vs = [buffered_row_voltage(1.0, 1.0e3, 1.0e3, rl) for rl in (1.0e5, 1.0e4, 1.0e3, 1.0e2)]
    ok &= chk("③ 负载调整单调：R_L ↓ ⇒ v_load ↓（且趋于空载极限 A/(1+A)）",
              all(vs[i] < vs[i - 1] for i in range(1, len(vs)))
              and abs(vs[0] - 1.0 * 1000.0 / 1001.0) < 2e-3,
              "R_L=1e5→%.5f · 1e4→%.5f · 1e3→%.5f · 1e2→%.5f"
              % tuple(vs))

    # ④ 🔴 与 E9 极限交叉核对：R_oc = 0 ⇒ 逐位一致
    r_seg = 0.504
    g = 120e-6 * 10.0 * 1.7
    mine = row_line_profile_with_driver(24, r_seg, g, 0.0)["voltages"]
    if AS is not None:
        ref = AS.row_line_profile(24, r_seg, g)["voltages"]
        dmax = float(np.max(np.abs(np.asarray(mine) - np.asarray(ref))))
        ok &= chk("④ 🔴 **R_oc = 0 ⟷ E9 三对角逐位一致**（极限交叉核对 · max|Δ| < 1e-12）",
                  dmax < 1e-12, "max|Δ|=%.3e" % dmax)
    else:                                        # pragma: no cover
        ok &= chk("④ 🔴 R_oc = 0 ⟷ E9 三对角逐位一致", False, "array_scale 不可导入")

    # ⑤ R_oc ↑ ⇒ 可及规模上界 ↓（**本段核心系统结论**）
    tbl = driver_scale_table(r_seg, g, 0.05, (0.0, 1.0, 5.0, 20.0))
    ns = [r["n_max"] for r in tbl["rows"]]
    ok &= chk("⑤ 🔴 驱动输出电阻 ⇒ 可及规模上界：R_oc ↑ ⇒ N_max 单调↓（5% 预算）",
              tbl["monotone_shrink"] and ns[0] > ns[-1],
              "N_max: %s（R_oc=%s Ω）" % (ns, [r["r_out_cl_ohm"] for r in tbl["rows"]]))

    # ⑥ 行系统项：真驱动 ⇒ 行增益离散；理想驱动 ⇒ 离散消失（对照实验）
    rng = np.random.RandomState(0)
    G = rng.uniform(1.0e-4, 5.0e-4, (8, 6))
    x = rng.uniform(0.1, 1.0, 8)
    se = row_system_error(G, x, vfs=1.0, rf=1.0e4, a_gain=1.0e3, r_out_open_ohm=1.0e3)
    ok &= chk("⑥ 🔴 **行系统项**：真驱动（R_ol=1 kΩ）⇒ 行增益**离散**；理想驱动 ⇒ 离散 = 0",
              se["with_driver_spread"] > 1e-4 and abs(se["ideal_driver_spread"]) < 1e-12,
              "真驱动 spread=%.3e · 理想驱动 spread=%.3e"
              % (se["with_driver_spread"], se["ideal_driver_spread"]))

    # ⑦ 端到端系统链：误差随驱动输出阻抗上升（理想驱动 = A→∞ 且 R_ol=0）
    ch_ideal = system_chain(G, x, vfs=1.0, rf=1.0e4, a_gain=1.0e9, r_out_open_ohm=0.0)
    ch_real = system_chain(G, x, vfs=1.0, rf=1.0e4, r_out_open_ohm=1.0e3)
    ok &= chk("⑦ 系统链：真驱动 max_rel_err > 理想驱动（A→∞ & R_ol=0 ⇒ 趋 0）",
              ch_real["max_rel_err"] > ch_ideal["max_rel_err"]
              and ch_ideal["max_rel_err"] < 1e-8,
              "真 %.3e ⟷ 理想 %.3e" % (ch_real["max_rel_err"], ch_ideal["max_rel_err"]))

    # ⑧ 诚实披露：宏模型 + 不报 TOPS
    ok &= chk("⑧ 披露显式声明「行驱动器为宏模型 / 非晶体管级运放」且不报 TOPS",
              "宏模型" in PERIPHERY_DISCLOSURE["honest_boundary"]
              and "TOPS" in PERIPHERY_DISCLOSURE["honest_boundary"])

    # ⑨ 🔴 **登记并锁定平台缺陷**：mna.vcvs 实际极性与 docstring 相反（E14 发现 · 不修 mna）
    pol = vcvs_polarity_fact()
    ok &= chk("⑨ 🔴 **platform 事实锁定**：`mna.vcvs` 实际极性 ⟷ docstring **相反**"
              "（`V_out = gain·(V_cn−V_cp)`）—— 本段适配 + 登记，不改 mna",
              pol["polarity_inverted"] is True and pol["v_out_with_ctl_p_positive"] < 0.0,
              "v_out(ctl_p=+1)=%.1f（docstring 期望 +1000）" % pol["v_out_with_ctl_p_positive"])

    if verbose:
        for nm, c, det in msgs:
            print(("  [PASS] " if c else "  [FAIL] ") + nm + ((" :: " + det) if det else ""))
        print("  —— periphery 自检 %d/%d ——" % (sum(1 for _, c, _ in msgs if c), len(msgs)))
    return ok


if __name__ == "__main__":
    import json
    print("=== periphery 自检 ===")
    periphery_self_check(verbose=True)
    print("=== 驱动 ⇒ 规模上界 ===")
    print(json.dumps(driver_scale_table(0.504, 120e-6 * 10.0 * 1.7, 0.05), ensure_ascii=False, indent=1)[:1200])
