# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E21 · 能效口径（功耗模型 + 三档口径 + 对标，D-196）。

============================================================================
为什么本模块存在（G-D 红线的解除方式，**不是**"可以随便报数了"）
----------------------------------------------------------------------------
G-D 原条文：「零能效数字纪律 —— 不报 TOPS / TOPS-W / fJ/op」。
它挡住的其实是**两件不同的事**，过去被压成了一条：

  (a) **不许算** —— 平台没有功耗模型（G-R 明写「时序为宏模型级 · **不做功耗**」），
      所以 E1–E19 全链跑完也拿不到一个 P，自然报不出能效；
  (b) **不许宣称** —— LDA 是设计验证工具链，**不是流片芯片**；用模型算出的
      TOPS/W 当"我们的芯片达到 N TOPS/W"说出去 = fabricated 指标。

🔴 **本模块只解 (a)，绝不解 (b)**。三档口径写死（`ENERGY_TIERS`）：

  · `INTERNAL_TARGET` —— 内部设计目标反解：假设随便设，只为回答「要多少 P 才够」。
  · `MODEL_ESTIMATE`  —— 模型推算：**本模块的输出全部落在这一档**。必须带
                          `basis`（假设清单）+ `is_measured=False`。
  · `MEASURED`        —— 实测：**当前无硅，本档空置**（`MEASURED_AVAILABLE=False`）。
                          任何代码路径都不得在此档产出数字。

⇒ 「离 Mythic 的 120 TOPS/W 差多少」从此**可判定**（在 MODEL_ESTIMATE 档内、
  在明示假设下），但「LDA 芯达到 120 TOPS/W」**仍不可说**。

============================================================================
本模块给什么
----------------------------------------------------------------------------
① 功耗分解（动态 ½CV²·f + 静态 I·V），逐部件可查：
   阵列单元 / 行线充放电 / 行驱动 / CDAC 开关 / 逐列 ADC / 数字逻辑。
② 吞吐与能效：`ops = 2·N²`（一次 MVM 的 MAC 数 ×2）· `throughput = ops/T_conv`。
③ 🔴 **两条可判定的标度律**（本模块最有价值的东西，见 §3）：
   · 阵列主导区：**TOPS/W 与 N 无关**（`P ∝ N²` 而 `ops ∝ N²` 相消）
   · ADC 主导区：**TOPS/W ∝ N**（ADC 数 ∝ N，而 ops ∝ N²）
   ⇒ 二者交叉点 `N*` 就是「能效天花板由谁决定」的判据，**直接回答"差在哪"**。
④ 物理地板：Landauer `kT·ln2`（每次不可逆操作的能量下界）—— 任何 per-op 能量
   低于它即判红（物理定律锚，比任何实测 landmark 更硬）。

============================================================================
金标（"本应恰好为 X"的对照组 · 不是自证）
----------------------------------------------------------------------------
· 单电容充放电能量 **½CV²**（**不是** CV² —— 项目史上漏因子 2 出现过多次）
· **Landauer 地板** `kT·ln2 = 2.8707e-21 J @300K`
· CDAC 电荷重分配能量 = `Σ ½C_i·V_i²`，且**位数每 +1 ⇒ 能量 ×2**（精确标度）
· 能量守恒：Σ 各部件 = total（精确，浮点同源）
· 阵列主导区能效**与 N 无关**（解析闭式 `2/(T_conv·g·V)`，相对差 < 1e-12）

============================================================================
红线（与全平台同源）
----------------------------------------------------------------------------
C 级自主（纯标准库 + numpy）· LLM 不进判决路径 · **只读消费** E7/E14/E17/E18，
**不改**任何既有默认值 · 参数为**公开典型量级占位（非 Foundry PDK）** ·
🔴 **输出恒标 `MODEL_ESTIMATE`，`MEASURED` 档空置** · 不做流片。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from lda_l2.ecore import layout as LY
from lda_l2.ecore import parasitic as PA
from lda_l2.ecore import timing as T
from lda_l2.ecore.mosfet import NmosParams

# ---------------------------------------------------------------------------
# ① 三档口径（G-D 的解除方式写死在这里）
# ---------------------------------------------------------------------------
ENERGY_TIERS = {
    "INTERNAL_TARGET": {
        "id": "INTERNAL_TARGET",
        "name": "内部设计目标反解",
        "allowed": True,
        "meaning": "假设随便设，只为回答「要多少功耗/能效才够」；**不得对外引用**",
        "must_label": False,
    },
    "MODEL_ESTIMATE": {
        "id": "MODEL_ESTIMATE",
        "name": "模型推算（非实测）",
        "allowed": True,
        "meaning": "由已建模的 C/V/f 推出；**必须**同时给出假设清单与 `is_measured=False`",
        "must_label": True,
    },
    "MEASURED": {
        "id": "MEASURED",
        "name": "实测（硅上测得）",
        "allowed": False,          # 🔴 本仓无硅 ⇒ 此档永久空置
        "meaning": "**当前不可用**：LDA 无流片、无实测硅 ⇒ 任何声称落在本档的数字都是 fabricated",
        "must_label": True,
    },
}

MEASURED_AVAILABLE = False      # 🔴 硬开关：有硅之前恒 False，判据据此守"冒充实测"
OUTPUT_TIER = "MODEL_ESTIMATE"  # 本模块全部输出的档位

#: 功耗/能量工艺与电路参数（**公开典型量级占位 · 非 PDK**）
ENERGY_PROCESS: Dict[str, float] = {
    "vdd_v": 1.0,                 # 数字/驱动电源
    "v_ref_v": 1.0,               # ADC/DAC 参考电压（满量程）
    "v_in_v": 1.0,                # 行输入电压（满量程最坏口径）
    "alpha_act": 0.5,             # 数字逻辑活动因子（典型）
    "c_logic_fF_per_cell": 2.0,   # 每单元逻辑等效电容（占位）
    # 🔴 **已废弃**（v0.9.320）：逻辑时钟**不得**用占位常数，必须由 E17 的 `1/t_clk` 推导。
    #   保留此键仅为向后兼容，`logic_power_w` 已改用 `logic_clock_hz()`。
    "f_logic_hz": 200.0e6,
    "c_unit_fF": 10.0,            # ADC 单位电容（占位 · 决定 CDAC 总容）
    "i_leak_a_per_cell": 1.0e-12, # 单元/门静态漏电（占位）
    # 🔴 **读出占空比**：模拟 CIM 的电流只流一个**短读出窗口**（几 ns），
    #    不是整个转换周期（92 ns）。这是模拟 CIM 能效优势的**物理来源**，
    #    漏掉它会把阵列功耗高估 1/占空比 倍 ⇒ 结论会把瓶颈错判到阵列。
    "duty_read": 0.1,             # 读窗口/转换周期（占位 · 公开量级）
    "t_kelvin": 300.0,            # 温度（Landauer 地板用）
}

#: 公开 landmark（A 级来源照录 · **未在 LDA 上验证** · 仅背景坐标）
EFFICIENCY_LANDMARKS = [
    {"name": "TSMC 数字 SRAM CIM macro (22nm)", "tops_per_w": 89.0,
     "note": "macro 级峰值（ISSCC 2021 转引）", "source": "ISSCC 2021 (转引)"},
    {"name": "TSMC 数字 SRAM CIM macro (5nm)", "tops_per_w": 254.0,
     "note": "macro 级峰值（ISSCC 2022 转引）", "source": "ISSCC 2022 (转引)"},
    {"name": "Mythic APU (模拟 NOR Flash aCIM)", "tops_per_w": 120.0,
     "note": "整芯片口径（SST memBrain · 40/28nm）", "source": "mythic.ai / Microchip 2026-03"},
    {"name": "IBM PCM 模拟 (14nm)", "tops_per_w": 12.4,
     "note": "芯片级持续性能（Nature 2023）", "source": "Nature 620, 768 (2023)"},
]


# ---------------------------------------------------------------------------
# ② 能量基元（金标都在这里）
# ---------------------------------------------------------------------------
KB = 1.380649e-23      # J/K（SI 定义值，**精确**）


def cap_energy_j(c_f: float, v: float) -> float:
    """单电容充放电能量 **½·C·V²**（一次完整充放）。

    🔴 金标：**是 ½CV²，不是 CV²**。写成 CV² 会让能效偏低一半 ——
    项目史上「漏因子 2」已出现三次（295/296 等），此处单独立判据守。
    """
    return 0.5 * float(c_f) * float(v) ** 2


def landauer_limit_j(t_kelvin: Optional[float] = None) -> float:
    """Landauer 地板：每次**不可逆**操作的最小能量 `kT·ln2`。

    @300 K ⇒ 2.8707e-21 J。任何 per-op 能量低于此即**物理上不可能** ⇒ 判红。
    """
    t = ENERGY_PROCESS["t_kelvin"] if t_kelvin is None else float(t_kelvin)
    return KB * t * math.log(2.0)


def cdac_switching_energy_j(bits: int, c_unit_fF: float, v_ref: float) -> Dict:
    """SAR-CDAC 电荷重分配能量（二进制加权电容阵列，逐位切换）。

    单位电容 C0，第 k 位电容 `2^k·C0`。每次对该位切换 `½·C_k·V_ref²`。
    满码扫描（全部位都切过）⇒ `E = ½·C0·V_ref²·(2^bits − 1)`。
    🔴 标度：**位数每 +1 ⇒ 能量 ×2**（精确，除常数偏移）。
    """
    bits = int(bits)
    if bits <= 0:
        raise ValueError("bits 须 > 0")
    c0 = float(c_unit_fF) * 1e-15
    n_switch = float(2 ** bits - 1)
    e = 0.5 * c0 * float(v_ref) ** 2 * n_switch
    return {"bits": bits, "c_unit_f": c0, "n_unit_switch": n_switch,
            "energy_j": e, "energy_per_sample_fj": e * 1e15}


def cdac_total_cap_f(c_unit_fF: float, bits: int) -> float:
    """CDAC 总采样电容 `C_tot = C0·2^bits`（含 dummy 位按惯例不计）。"""
    return float(c_unit_fF) * 1e-15 * float(2 ** int(bits))


# ---------------------------------------------------------------------------
# ③ 逐部件功耗
# ---------------------------------------------------------------------------
def array_static_power_w(n: int, g_s: Optional[float] = None,
                         v_in: Optional[float] = None,
                         params: Optional[Dict[str, float]] = None) -> Dict:
    """阵列计算功耗 `P_arr = N²·g·V_in²`（列端虚地 ⇒ 全压降落在单元上）。

    🔴 取**满量程最坏口径**（所有行 V=V_in）⇒ 高估功耗 ⇒ **低估**能效，
    方向上是诚实的（不美化）。
    """
    p = dict(LY.DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    n = int(n)
    if g_s is None:
        nm = NmosParams(w_over_l=p["w_um"] / p["l_um"])
        g_s = nm.kp * nm.w_over_l * (2.5 - nm.vth0)
    v = ENERGY_PROCESS["v_in_v"] if v_in is None else float(v_in)
    duty = float(ENERGY_PROCESS["duty_read"])
    pw = float(n) ** 2 * float(g_s) * v ** 2 * duty
    return {"n": n, "g_s": float(g_s), "v_in_v": v, "duty": duty,
            "n_cells": n * n, "power_w": pw,
            "basis": "N²·g·V_in²·duty（满量程最坏 × 读出占空比）"}


def row_line_dynamic_power_w(n: int, f_hz: float,
                             params: Optional[Dict[str, float]] = None,
                             v: Optional[float] = None,
                             swing_factor: float = 1.0) -> Dict:
    """行线充放电动态功耗 `P = n × ½·C_row_total·(swing·V)²·f`。

    `swing_factor` = 电压摆幅 / V_dd（1.0 = 全摆幅；0.5 = 半摆幅 ⇒ 能量 ×1/4）。

    🔴 **口径必须来自 E7 真源 `c_row_seg_fF`**（单位 fF），**不得用 τ/R 反解**：
       E7 的 `tau_row_s` 是**整行** Elmore（∝ N²），而 `r_row_seg_ohm` 是**每段** ——
       两者相除得到的"c_seg"实际是 `N²·C_seg` 量级（N=64 时**偏大 1008 倍**，已实测）。
       这是一个曾经发生过的真缺陷（v0.9.317 的 E21/E22 地板 74.90 fJ/op 因此被膨胀 4 倍）。
    """
    p = dict(LY.DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    n = int(n)
    ap = PA.array_parasitics(n, n, p)
    c_row_total_fF = ap["C_row_total_fF"]            # 🔴 真源键名（带单位后缀）
    c_row_total_f = float(c_row_total_fF) * 1e-15
    vv = (ENERGY_PROCESS["vdd_v"] if v is None else float(v)) * float(swing_factor)
    e_per_row = cap_energy_j(c_row_total_f, vv)
    pw = e_per_row * float(f_hz) * n
    return {"n": n, "c_row_seg_fF": ap["c_row_seg_fF"],
            "c_row_total_f": c_row_total_f, "f_hz": float(f_hz),
            "swing_factor": float(swing_factor),
            "power_w": pw,
            "basis": "n × ½·C_row_total·(swing·V)²·f（C 取 E7 真源 c_row_seg_fF）"}


def adc_power_w(bits: int, n_converters: int, f_sample_hz: float,
                c_unit_fF: Optional[float] = None,
                v_ref: Optional[float] = None) -> Dict:
    """逐列 SAR ADC 功耗（电容阵列充放电主导）。

    每列 ADC 每样本能量 `E_s = ½·C_tot·V_ref²`（C_tot = C0·2^bits）⇒
    `P = n_conv · E_s · f_s`。
    🔴 关键：`n_converters ∝ N`（每列一个，或列共享后 N/K），而 `ops ∝ N²`
    ⇒ **ADC 主导时能效 ∝ N**（见 §4 标度律）。
    """
    c0 = ENERGY_PROCESS["c_unit_fF"] if c_unit_fF is None else float(c_unit_fF)
    vr = ENERGY_PROCESS["v_ref_v"] if v_ref is None else float(v_ref)
    c_tot = cdac_total_cap_f(c0, bits)
    e_s = cap_energy_j(c_tot, vr)
    pw = e_s * float(f_sample_hz) * int(n_converters)
    return {"bits": int(bits), "n_converters": int(n_converters),
            "c_tot_f": c_tot, "e_per_sample_j": e_s,
            "power_w": pw, "basis": "n_conv·½·C_tot·V_ref²·f_s"}


def logic_clock_hz(bits: int = 8) -> Dict:
    """**逻辑时钟真源**：`1/t_clk`，由 E17 `sar_stage_time` 推导。

    🔴 两个曾用错的口径：
      · 占位常数 200 MHz（偏高 2.05×，v0.9.317–319 用它）；
      · `1/T_conv = 10.85 MHz`（偏低 9×，E23 的「逻辑同步」一档误用此值）。
    正解 = `1/t_clk = n_clk/T_conv = 97.68 MHz @8bit`（两者恒等，可交叉核对）。
    """
    r = T.sar_stage_time(bits=bits)
    return {"f_logic_hz": 1.0 / r["t_clk_s"],
            "t_clk_s": r["t_clk_s"], "n_clk": r["n_clk"],
            "f_from_conv": r["n_clk"] / r["t_s"],
            "identity_ok": abs(1.0 / r["t_clk_s"] - r["n_clk"] / r["t_s"])
                            / (1.0 / r["t_clk_s"]) < 1e-12,
            "basis": "E17 sar_stage_time ⇒ 1/t_clk（≡ n_clk/T_conv）"}


def logic_power_w(n_cells: int, f_hz: Optional[float] = None,
                  alpha: Optional[float] = None,
                  v: Optional[float] = None,
                  c_cell_fF: Optional[float] = None) -> Dict:
    """数字逻辑动态功耗 `P = α·C·V²·f`（C = n_cells × 每单元等效电容）。"""
    f = logic_clock_hz()["f_logic_hz"] if f_hz is None else float(f_hz)
    a = ENERGY_PROCESS["alpha_act"] if alpha is None else float(alpha)
    vv = ENERGY_PROCESS["vdd_v"] if v is None else float(v)
    c_cell = ENERGY_PROCESS["c_logic_fF_per_cell"] if c_cell_fF is None else float(c_cell_fF)
    c_tot = int(n_cells) * c_cell * 1e-15
    pw = a * c_tot * vv ** 2 * f
    return {"n_cells": int(n_cells), "c_tot_f": c_tot, "f_hz": f,
            "power_w": pw, "basis": "α·C·V²·f"}


def leakage_power_w(n_devices: int, v: Optional[float] = None,
                    i_leak_a: Optional[float] = None) -> Dict:
    """静态漏电功耗 `P = n_dev · I_leak · V`。"""
    vv = ENERGY_PROCESS["vdd_v"] if v is None else float(v)
    il = ENERGY_PROCESS["i_leak_a_per_cell"] if i_leak_a is None else float(i_leak_a)
    pw = int(n_devices) * il * vv
    return {"n_devices": int(n_devices), "power_w": pw, "basis": "n_dev·I_leak·V"}


# ---------------------------------------------------------------------------
# ④ 系统能效（含两条标度律 —— 本模块的核心结论）
# ---------------------------------------------------------------------------
def throughput_ops_per_s(n: int, t_conv_s: Optional[float] = None,
                         bits: int = 8) -> Dict:
    """吞吐：一次转换完成整个 N×N MVM ⇒ `ops/s = 2·N²/T_conv`。

    `T_conv` 复用 E17 `sar_period`（**不另设时序参数**）。
    """
    n = int(n)
    tc = float(T.sar_stage_time(bits=bits)["t_s"]) if t_conv_s is None else float(t_conv_s)
    ops_per_sample = 2.0 * n * n            # MAC = 2 ops；N² 个 MAC
    tps = ops_per_sample / tc
    return {"n": n, "t_conv_s": tc, "ops_per_sample": ops_per_sample,
            "ops_per_s": tps, "gops": tps / 1e9}


def system_energy_report(n: int, bits: int = 8,
                         col_share_k: int = 1,
                         params: Optional[Dict[str, float]] = None,
                         g_s: Optional[float] = None,
                         include: Optional[Dict[str, bool]] = None) -> Dict:
    """端到端功耗/能效分解（**全部落 MODEL_ESTIMATE 档**）。

    `col_share_k`：几列共享一个 ADC（E18 的 K；1 = 每列一个）。
    `include`：逐部件开关（默认全开）；用于做「理想 vs 实际」对照。
    """
    p = dict(LY.DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    n = int(n)
    inc = {"array": True, "rowline": True, "adc": True, "logic": True, "leak": True}
    if include:
        inc.update(include)

    th = throughput_ops_per_s(n, bits=bits)
    f_s = 1.0 / th["t_conv_s"]                     # 每列样本率

    parts: List[Dict] = []
    if inc["array"]:
        a = array_static_power_w(n, g_s=g_s, params=p)
        parts.append({"name": "array", **a})
    if inc["rowline"]:
        # 🔴 每次转换所有行**并行**被驱动一次 ⇒ 行线频率 = f_s（曾误写 f_s·n ⇒ 引入虚假 ∝N³）
        r = row_line_dynamic_power_w(n, f_s, params=p)
        parts.append({"name": "row_line", **r})
    if inc["adc"]:
        n_conv = max(1, int(math.ceil(n / float(max(1, int(col_share_k))))))
        a = adc_power_w(bits, n_conv, f_s)
        parts.append({"name": "adc", **a})
    if inc["logic"]:
        # 🔴 口径修正（v0.9.320）：逻辑单元数 **∝ n（每列一个 ADC 控制/后处理单元）**，
        #   不是 n²（阵列单元数）。v0.9.317–319 用 n² ⇒ **偏高 64×**（N=64 时）。
        lg = logic_power_w(n, c_cell_fF=ENERGY_PROCESS["c_logic_fF_per_cell"])
        parts.append({"name": "logic", **lg})
    if inc["leak"]:
        lk = leakage_power_w(n * n * 4)            # 每交叉点约 4 个器件（1T + 开关）
        parts.append({"name": "leak", **lk})

    p_tot = sum(x["power_w"] for x in parts)
    tops_per_w = th["ops_per_s"] / p_tot if p_tot > 0 else 0.0
    p_share = {x["name"]: (x["power_w"] / p_tot if p_tot > 0 else 0.0) for x in parts}
    dom = max(p_share, key=p_share.get) if p_share else None

    return {
        "tier": OUTPUT_TIER,
        "is_measured": False,
        "n": n, "bits": int(bits), "col_share_k": int(col_share_k),
        "t_conv_s": th["t_conv_s"],
        "ops_per_s": th["ops_per_s"],
        "power_w": p_tot,
        "power_breakdown": {x["name"]: x["power_w"] for x in parts},
        "power_share": p_share,
        "dominant": dom,
        "tops_per_w": tops_per_w / 1e12,
        "gops_per_w": tops_per_w / 1e9,
        "energy_per_op_fj": (p_tot / th["ops_per_s"]) * 1e15 if th["ops_per_s"] > 0 else 0.0,
        "parts": parts,
        "basis": ["满量程最坏 V_in", "公开典型量级占位（非 PDK）",
                  "静态为主（阵列单元计算功耗）", "T_conv 复用 E17 sar_period"],
    }


def efficiency_vs_n(sizes: Optional[List[int]] = None, bits: int = 8,
                    col_share_k: int = 1) -> List[Dict]:
    """能效-规模曲线（**用来判「能效由谁决定」**）。"""
    if sizes is None:
        sizes = [4, 8, 12, 16, 32, 64, 128, 256]
    out = []
    for s in sizes:
        r = system_energy_report(int(s), bits=bits, col_share_k=col_share_k)
        out.append({"n": r["n"], "gops_per_w": r["gops_per_w"],
                    "tops_per_w": r["tops_per_w"], "dominant": r["dominant"],
                    "power_w": r["power_w"]})
    return out


# ---------------------------------------------------------------------------
# ⑤ 两条标度律（解析闭式 · 判据在此）
# ---------------------------------------------------------------------------
def array_dominated_efficiency_gops_per_w(bits: int = 8,
                                          g_s: Optional[float] = None,
                                          v_in: Optional[float] = None) -> Dict:
    """**阵列主导区**能效解析闭式：`TOPS/W = 2/(T_conv·g·V_in)` —— **与 N 无关**。

    推导：`ops = 2N²/T_conv`，`P = N²·g·V²` ⇒ `N²` 完全相消。
    🔴 这条是判据：解析值 ⟷ `system_energy_report(仅阵列)` 的数值，相对差 < 1e-12；
    且 **N=8 与 N=256 两点的数值能效必须相等**（"本应恰好相等"的对照组）。
    """
    th = throughput_ops_per_s(8, bits=bits)
    tc = th["t_conv_s"]
    if g_s is None:
        p = dict(LY.DEFAULT_CELL_PARAMS)
        nm = NmosParams(w_over_l=p["w_um"] / p["l_um"])
        g_s = nm.kp * nm.w_over_l * (2.5 - nm.vth0)
    v = ENERGY_PROCESS["v_in_v"] if v_in is None else float(v_in)
    duty = float(ENERGY_PROCESS["duty_read"])
    # 🔴 duty 在**分母**（占空比越小 ⇒ 平均功耗越低 ⇒ 能效越高）。
    #   曾误写成分子 ⇒ 量级差 100 倍；被「解析 ⟷ 数值**绝对**对拍」抓住（比值判据抓不住量级错）。
    gops = 2.0 / (tc * float(g_s) * v * duty) / 1e9
    return {"gops_per_w": gops, "t_conv_s": tc, "g_s": float(g_s), "v_in_v": v,
            "duty": duty, "n_independent": True,
            "formula": "2/(T_conv·g·V_in·duty)"}


def crossover_n(bits: int = 8, params: Optional[Dict[str, float]] = None,
                hi: int = 512) -> Dict:
    r"""阵列主导 ⟷ ADC 主导的**交叉规模 N***（谁决定能效天花板）。

    判据：`N < N*` 时 ADC 功耗份额更大；`N > N*` 时阵列更大。
    用扫描找份额相等点（`worst(N)` 未必单调，故不用二分）。
    """
    prev = None
    for n in range(2, int(hi) + 1, 2):
        r = system_energy_report(n, bits=bits, params=params)
        s = r["power_share"]
        d = s.get("array", 0.0) - s.get("adc", 0.0)
        if prev is not None and prev[1] < 0.0 <= d:
            return {"n_star": n, "bits": int(bits),
                    "meaning": "N<N* ADC 主导（能效 ∝ N）· N>N* 阵列主导（能效趋平）",
                    "found": True}
        prev = (n, d)
    return {"n_star": None, "bits": int(bits), "found": False,
            "meaning": f"在 N≤{hi} 内未出现交叉（单一主导贯穿全区间）"}


def sensitivity_on_unit_conductance(g_list: Optional[List[float]] = None,
                                    n: int = 64, bits: int = 8) -> Dict:
    """**能效对单元电导的敏感性** —— 本段最重要的设计指令。

    解析：`TOPS/W = 2/(T_conv·g·V_in·duty)` ⇒ **能效 ∝ 1/g**。
    ⇒ 想提能效，第一杠杆是**降低单元电导**（换低电导器件 / 降权重量化电流），
      **不是**做架构、也不是换 ADC。

    `g_list` 缺省给 MOSFET 饱和态（~1e-3 S）到 flash/RRAM 量级（1e-6 S）的扫描。
    """
    if g_list is None:
        g_list = [1e-3, 1e-4, 1e-5, 1e-6]
    rows = []
    for g in g_list:
        r = system_energy_report(n, bits=bits, g_s=float(g))
        rows.append({"g_s": float(g), "gops_per_w": r["gops_per_w"],
                     "energy_per_op_fj": r["energy_per_op_fj"],
                     "dominant": r["dominant"]})
    # 🔴 精确偏离闭式：g 降 10× 时阵列项降 10×、其余不变 ⇒
    #   能效比 = 1/(0.1·s + (1−s))，s = 上一点的**阵列功耗份额**。
    #   ⇒ 只有 s→1（阵列完全主导）时才趋近 10×；s 越小偏离越大（进入 ADC/逻辑主导）。
    ratios, pred = [], []
    for i in range(len(rows) - 1):
        # 方向约定：g 逐点**递减**（1e-3 → 1e-6），故 g 降十倍 ⇒ 能效升 ⇒ 比值 > 1
        ratios.append(rows[i + 1]["gops_per_w"] / rows[i]["gops_per_w"])
        sh = system_energy_report(n, bits=bits,
                                  g_s=rows[i]["g_s"])["power_share"].get("array", 0.0)
        pred.append(1.0 / (0.1 * sh + (1.0 - sh)))
    return {"n": int(n), "bits": int(bits), "rows": rows,
            "decade_ratios": ratios, "decade_ratios_predicted": pred,
            "law": "TOPS/W ∝ 1/g **仅在阵列主导区渐近成立**；精确比 = 1/(0.1·s+(1−s))，s=阵列功耗份额",
            "design_directive": "能效第一杠杆 = **单元电导**；第二杠杆 = 读出占空比；"
                                "第三 = 转换周期。**扩阵列规模不提能效**（P∝N² 与 ops∝N² 相消）。"}


def energy_vs_landmark(report: Optional[Dict] = None) -> Dict:
    """与公开 landmark 的**同族维度**对比（🔴 不同台、不越级）。"""
    r = report or system_energy_report(64)
    gops = r["gops_per_w"]
    rows = []
    for lm in EFFICIENCY_LANDMARKS:
        rows.append({
            "landmark": lm["name"], "tops_per_w": lm["tops_per_w"],
            "lda_gops_per_w": gops,
            "ratio_lda_over_landmark": (gops / 1e3) / lm["tops_per_w"],
            "note": lm["note"], "source": lm["source"],
        })
    return {
        "tier": OUTPUT_TIER, "is_measured": False,
        "lda_n": r["n"], "lda_gops_per_w": gops,
        "comparability": "🔴 **不同台**：LDA 是 40nm 档公开占位参数 + 满量程最坏口径 + 无硅；"
                         "landmark 是实测芯片（工艺/口径/精度档均不同）⇒ **只作量级坐标，不作胜负**",
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def energy_self_check(verbose: bool = False) -> bool:
    """≥ 16 项自检：金标因子 · Landauer 地板 · 标度律 · 守恒 · 三档口径。"""
    msgs = []

    def chk(name, cond, detail=""):
        msgs.append((name, bool(cond), detail))
        return bool(cond)

    ok = True

    # ① ½CV² vs CV²：能量必须**恰好**是 CV² 的一半
    e1 = cap_energy_j(1e-15, 1.0)
    ok &= chk("① 单电容充放电能量 = ½CV²（**不是** CV²；1fF@1V ⇒ 0.5e-15 J）",
              abs(e1 - 0.5e-15) < 1e-30 and abs(e1 / 1e-15 - 0.5) < 1e-15,
              f"{e1:.6e} J")

    # ② Landauer 地板：kT·ln2 @300K = 2.8707e-21 J
    lj = landauer_limit_j()
    ok &= chk("② Landauer 地板 = kT·ln2 = 2.8707e-21 J @300K（物理定律锚）",
              abs(lj - 2.8707e-21) / lj < 1e-3, f"{lj:.6e} J")

    # ③ CDAC 标度律：位数 +1 ⇒ 能量 ×2（精确）
    e8 = cdac_switching_energy_j(8, 10.0, 1.0)["energy_j"]
    e9 = cdac_switching_energy_j(9, 10.0, 1.0)["energy_j"]
    # 🔴 判据纪律：和式 E(b)=½C0V²(2^b−1) 的比值 **不是** 精确 2（511/255=2.0039）
    #   ⇒ 精确恒等写成 E(b+1) − 2·E(b) = ½·C0·V²（代数恒等，容差 1e-27）
    resid = e9 - 2.0 * e8 - 0.5 * 10e-15 * 1.0 ** 2
    ok &= chk("③ CDAC 精确恒等 E(b+1) − 2E(b) = ½C0V²（和式比值非精确 2）",
              abs(resid) < 1e-27, f"残差 {resid:.3e} J")

    # ④ CDAC 闭式 = Σ½C_i V²（独立算式对拍）
    bits = 8
    c0 = 10e-15
    brute = sum(0.5 * c0 * 2 ** k * 1.0 ** 2 for k in range(bits))
    ok &= chk("④ CDAC 闭式 ≡ Σ_{k=0}^{b−1} ½·C0·2^k·V²（独立求和，相对差 < 1e-15）",
              abs(e8 - brute) / brute < 1e-15)

    # ⑤ 能量守恒：Σ 各部件 = total（同源浮点，精确）
    r = system_energy_report(32)
    ok &= chk("⑤ 能量守恒：Σ parts.power == total（精确，容差 1e-15）",
              abs(sum(x["power_w"] for x in r["parts"]) - r["power_w"])
              / r["power_w"] < 1e-15)

    # ⑥ 阵列主导能效与 N 无关（"本应恰好相等"的对照组）
    g = NmosParams(w_over_l=1.2 / 0.3)
    gs = g.kp * g.w_over_l * (2.5 - g.vth0)
    only_arr = {"array": True, "rowline": False, "adc": False,
                "logic": False, "leak": False}
    r8 = system_energy_report(8, include=only_arr, g_s=gs)
    r256 = system_energy_report(256, include=only_arr, g_s=gs)
    ok &= chk("⑥ 阵列主导：N=8 与 N=256 能效**相等**（P∝N² 与 ops∝N² 相消）",
              abs(r8["gops_per_w"] - r256["gops_per_w"])
              / r256["gops_per_w"] < 1e-12,
              f"{r8['gops_per_w']:.6f} ⟷ {r256['gops_per_w']:.6f} GOPS/W")

    # ⑦ 阵列主导能效 ≡ 解析闭式 2/(T_conv·g·V)
    clo = array_dominated_efficiency_gops_per_w(g_s=gs)
    ok &= chk("⑦ 阵列主导能效 ≡ 解析闭式 2/(T_conv·g·V_in)（相对差 < 1e-12）",
              abs(r8["gops_per_w"] - clo["gops_per_w"]) / clo["gops_per_w"] < 1e-12,
              f"数值 {r8['gops_per_w']:.6f} ⟷ 闭式 {clo['gops_per_w']:.6f}")

    # ⑧ ops = 2N²（一次 MVM 的 MAC 数 × 2）
    th = throughput_ops_per_s(16)
    ok &= chk("⑧ 吞吐 ops = 2·N²（16 ⇒ 512 ops/sample；MAC=2 ops）",
              abs(th["ops_per_sample"] - 512.0) < 1e-9)

    # ⑨ ADC 数量 ∝ N ⇒ 全链能效随 N 增（ADC 主导区）
    f4 = system_energy_report(4)
    f64 = system_energy_report(64)
    ok &= chk("⑨ 全链能效随 N 增（ADC 数 ∝N 而 ops ∝N²）⇒ N=64 高于 N=4",
              f64["gops_per_w"] > f4["gops_per_w"],
              f"{f4['gops_per_w']:.4f} → {f64['gops_per_w']:.4f} GOPS/W")

    # ⑩ per-op 能量必须高于 Landauer 地板（物理不可能判红）
    epo = f64["energy_per_op_fj"] * 1e-15
    ok &= chk("⑩ per-op 能量 > Landauer 地板（低于即物理不可能）",
              epo > landauer_limit_j(), f"{epo:.3e} J vs {lj:.3e} J")

    # ⑪ 三档口径：MEASURED 档**空置**且不可产出
    ok &= chk("⑪ 三档口径：MEASURED.allowed=False 且 MEASURED_AVAILABLE=False（无硅）",
              ENERGY_TIERS["MEASURED"]["allowed"] is False
              and MEASURED_AVAILABLE is False)

    # ⑫ 输出恒标 MODEL_ESTIMATE + is_measured=False
    ok &= chk("⑫ 所有输出恒标 tier=MODEL_ESTIMATE 且 is_measured=False",
              r["tier"] == "MODEL_ESTIMATE" and r["is_measured"] is False
              and energy_vs_landmark()["is_measured"] is False)

    # ⑬ 对标表必须自带「不同台」声明
    cmp_ = energy_vs_landmark()
    ok &= chk("⑬ landmark 对标自带「不同台/不作胜负」声明",
              "不同台" in cmp_["comparability"] and len(cmp_["rows"]) == len(EFFICIENCY_LANDMARKS))

    # ⑭ col_share_k 增大 ⇒ ADC 功耗单调降（E18 列共享的能效侧验证）
    k1 = system_energy_report(64, col_share_k=1)["power_breakdown"].get("adc", 0.0)
    k8 = system_energy_report(64, col_share_k=8)["power_breakdown"].get("adc", 0.0)
    ok &= chk("⑭ 列共享 K=8 ⇒ ADC 功耗降为 1/8（E18 结构在能效侧同样成立）",
              abs(k1 / k8 - 8.0) < 1e-12, f"{k1:.4e} → {k8:.4e} W")

    # ⑮ 只读纪律：不改 E7/E17/E18 默认值
    ok &= chk("⑮ 只读纪律：ELEC_PROCESS / DEFAULT_CELL_PARAMS 未被改动",
              PA.ELEC_PROCESS["r_leak_ohm"] == 1.0e9
              and LY.DEFAULT_CELL_PARAMS["w_um"] == 1.20)

    # ⑱ 🔴 行线电容**必须取 E7 真源**（防 τ/R 反解再犯 —— v0.9.317 曾偏大 1008 倍）
    _ap = PA.array_parasitics(64, 64)
    _rl = row_line_dynamic_power_w(64, 1.0e7)
    ok &= chk("⑱ 行线电容 ≡ E7 真源 `c_row_seg_fF`（禁 τ/R 反解 · 曾偏大 1008×）",
              abs(_rl["c_row_seg_fF"] - _ap["c_row_seg_fF"]) < 1e-12
              and abs(_rl["c_row_total_f"] - _ap["C_row_total_fF"] * 1e-15) < 1e-24,
              f"c_seg={_rl['c_row_seg_fF']:.4f} fF · C_tot={_rl['c_row_total_f']*1e15:.2f} fF")

    # ⑲ 半摆幅 ⇒ 能量精确 1/4（½C(ΔV)² 的直接推论）
    full = row_line_dynamic_power_w(64, 1.0e7, swing_factor=1.0)["power_w"]
    half = row_line_dynamic_power_w(64, 1.0e7, swing_factor=0.5)["power_w"]
    ok &= chk("⑲ 半摆幅 ⇒ 行线能量精确 1/4（swing² 律）",
              abs(half / full - 0.25) < 1e-15, f"{full:.3e} → {half:.3e} W")

    # ⑰ 敏感性的偏离必须与闭式逐位吻合：ratio = 1/(0.1·s + (1−s))
    sens = sensitivity_on_unit_conductance()
    d_sens = max(abs(a - b) / b for a, b in
                 zip(sens["decade_ratios"], sens["decade_ratios_predicted"]))
    ok &= chk("⑰ 电导敏感性偏离 ≡ 闭式 1/(0.1·s+1−s)（逐点相对差 < 1e-12）",
              d_sens < 1e-12, f"最大相对差 {d_sens:.3e}")

    # ⑯ 交叉规模可判定（要么给出 N*，要么明说全区间单一主导）
    cx = crossover_n(bits=8)
    ok &= chk("⑯ 交叉规模 N* 判定可给出结论（有交叉给 N* · 无交叉明说）",
              ("n_star" in cx) and (cx["found"] or cx["n_star"] is None),
              f"N*={cx['n_star']} found={cx['found']}")

    if verbose:
        for name, good, detail in msgs:
            print(("  [OK] " if good else "  [FAIL] ") + name
                  + (("  · " + detail) if detail else ""))
    return bool(ok)


ENERGY_DISCLOSURE = {
    "role": "E21 = 功耗模型 + 能效口径三档（**只解「不许算」，不解「不许宣称」**）",
    "tiers": {k: v["name"] for k, v in ENERGY_TIERS.items()},
    "measured_status": "🔴 **MEASURED 档永久空置**：本仓无流片、无实测硅 "
                       "⇒ 任何落在该档的数字都是 fabricated（`MEASURED_AVAILABLE=False`）",
    "golden": "½CV²（**非 CV²**）· Landauer kT·ln2 · CDAC 位数+1⇒能量×2 · "
              "阵列主导能效 2/(T_conv·g·V) 与 N 无关",
    "scale_laws": "阵列主导区 TOPS/W 与 N 无关；ADC 主导区 TOPS/W ∝ N；交叉点 N* 判「能效由谁决定」",
    "process": "V_dd/V_ref/α/C_logic/C_unit/I_leak 均为**公开典型量级占位（非 PDK）**",
    "worst_case": "阵列功耗取**满量程最坏**（全行 V_in）⇒ 高估功耗 ⇒ **低估**能效（方向诚实）",
    "comparable": "landmark 与 LDA **不同台**（工艺/口径/精度档不同）⇒ 只作量级坐标，不作胜负",
    "red_line": "纯标准库+numpy · LLM 不进判决路径 · 只读消费 E7/E14/E17/E18 · 不改既有默认值",
}

#: 供 capability 守护门禁反向完备引用的公开符号（避免"隐身"）
__all__ = [
    "ENERGY_TIERS", "ENERGY_PROCESS", "EFFICIENCY_LANDMARKS", "MEASURED_AVAILABLE",
    "OUTPUT_TIER", "KB", "cap_energy_j", "landauer_limit_j",
    "cdac_switching_energy_j", "cdac_total_cap_f", "array_static_power_w",
    "row_line_dynamic_power_w", "adc_power_w", "logic_power_w", "leakage_power_w",
    "throughput_ops_per_s", "system_energy_report", "efficiency_vs_n",
    "array_dominated_efficiency_gops_per_w", "crossover_n", "sensitivity_on_unit_conductance",
    "energy_vs_landmark",
    "energy_self_check", "ENERGY_DISCLOSURE",
]
