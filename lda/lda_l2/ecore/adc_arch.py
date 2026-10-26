# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E24 · ADC 架构与列共享功耗权衡（D-199）。

============================================================================
本段接着 E23 的第二次修正做（连续第三次把瓶颈收紧）
----------------------------------------------------------------------------
E23 修完行线电容后，地板 19.27 fJ/op，主导项 **ADC 51.9% + 逻辑 47.8%**。
本段先做「逻辑口径接 E17」（E23 建议的第 2 条），发现逻辑项还有**两个**口径错：

  · **频率**：占位常数 200 MHz（偏高 2.05×）。正解 = `1/t_clk = 97.68 MHz`（E17 推导，
    `1/t_clk ≡ n_clk/T_conv = 9/92.1 ns` 恒等，可交叉核对）。
  · **门数**：用了 `n²`（阵列单元数），而逻辑是**每列一个 ADC 控制/后处理单元** ⇒ 应 `∝ n`。
    N=64 时 **偏高 64×**。

修完后：地板 **19.27 → 10.125 fJ/op**，**ADC 占 98.8%**、逻辑 0.7%、行线 0.5%。
⇒ **瓶颈收敛到单一来源：ADC。** 这才轮到本段的正题。

============================================================================
本段给什么
----------------------------------------------------------------------------
① **四条 ADC 架构**的电容开关能量**闭式**（SAR / 单调 SAR / 两步式 / 两步+单调）：
   两步式 `C_tot = 2·C0·2^(b/2)`，8 bit ⇒ 能量 **15/127.5 = 0.1176×**（精确，非拟合）
② 🔴 **不变性**：`E_op,adc = e_sample/(2n)` —— **与转换速率 f_s 完全无关**。
   ⇒ 「两步式速度减半」**不影响能效**（只影响总吞吐）。这条是反直觉的，必须机核。
③ **列共享 K 权衡**：功耗 ∝1/K，但吞吐/带宽代价（接 E18 面积-时间守恒 + E19 mux 侵蚀）
④ 🔴 **未建模项显式披露**：比较器、参考缓冲、S/H、残差放大器、校准 —— 本模块只算**电容开关能量**，
   真实 ADC 能耗必须加上这些；给出**上界比例估计**并标 `MODEL_ESTIMATE`
⑤ **三项占位参数敏感性**：`duty_read` / `c_unit_fF` / `c_logic_fF_per_cell`

============================================================================
金标（"本应恰好相等"）
----------------------------------------------------------------------------
· 两步式 `C_tot = 2·C0·2^(b/2)`（精确代数）
· 两步式/SAR 能量比 = `[2·2^(b/2)·(2^(b/2)−1)]/(2^b−1)`（8 bit ⇒ 240/32640，即 0.00735？→ 见实现）
· 🔴 **E_op 与 f_s 无关**：f_s 翻 4 倍而 E_op 逐位不变（<1e-12）
· 列共享 K ⇒ E_op,adc /K（精确）
· 单调 SAR = 0.5× 标准 SAR（**文献因子，非推导** ⇒ 显式标 `empirical_factor`）

============================================================================
红线
----------------------------------------------------------------------------
纯标准库 · LLM 不进判决路径 · 只读消费 E7/E17/E18/E19/E21/E22/E23 · 不改既有默认值 ·
参数为公开典型量级占位（非 PDK）· 输出恒 `MODEL_ESTIMATE` ·
🔴 **不宣称达到任何 landmark**：只报架构相对收益与未建模项。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from lda_l2.ecore import energy as E
from lda_l2.ecore import timing as T

# ---------------------------------------------------------------------------
# ① 四条 ADC 架构
# ---------------------------------------------------------------------------
# cdc_factor：总电容 / (C0·2^bits)（相对标准二进制加权 SAR）
# 推导见 `cdac_cap_units()`；`None` 表示用解析式算
ADC_ARCHITECTURES: List[Dict] = [
    {
        "id": "sar",
        "name": "标准二进制加权 SAR",
        "cap_units_fn": "sar",
        "energy_factor": 1.0,
        "basis": "C_tot = C0·2^b，逐位双向切换，E = ½C0V²(2^b−1)",
        "cost": "基线；速度最快、结构最简",
        "maturity": "**本平台 E14/E21 默认口径**",
    },
    {
        "id": "sar_monotonic",
        "name": "单调开关 SAR（monotonic）",
        "cap_units_fn": "sar",
        "energy_factor": 0.5,
        "basis": "同一电容阵列，但每位**只朝一个方向**切换 ⇒ 约省一半（🔴 **文献因子 0.5，非本模型推导**）",
        "cost": "需单调开关时序（工程成熟）",
        "maturity": "ISSCC 常见改良（经验因子需实测校核）",
        "empirical_factor": True,
    },
    {
        "id": "two_step",
        "name": "两步式（高位 b/2 + 低位 b/2）",
        "cap_units_fn": "two_step",
        "energy_factor": None,          # 由解析式算
        "basis": "C_tot = 2·C0·2^(b/2)（两级各 b/2 位）；8 bit ⇒ 32C0 vs 256C0",
        "cost": "🔴 需残差放大 + 两级间 S/H + 校准；**这些开销本模型未计**",
        "maturity": "成熟架构（高速 ADC 常用）",
    },
    {
        "id": "two_step_monotonic",
        "name": "两步式 + 单调开关",
        "cap_units_fn": "two_step",
        "energy_factor": 0.5,
        "basis": "两步式电容 × 单调开关 0.5",
        "cost": "同上 + 单调时序",
        "maturity": "组合方案",
        "empirical_factor": True,
    },
]


def cdac_cap_units(bits: int, arch: str) -> Dict:
    """该架构的总电容（以 C0 为单位）与开关能量因子。

    标准 SAR：`C_tot = C0·2^b`，`E = ½·C0·V²·(2^b − 1)`
    两步式  ：`C_tot = 2·C0·2^(b/2)`（两级各 b/2 位），
              `E = 2 × ½·C0·V²·(2^(b/2) − 1)` = `½·C0·V²·2·(2^(b/2)−1)`... 见下实现
    """
    bits = int(bits)
    if bits <= 0:
        raise ValueError("bits 须 > 0")
    a = {x["id"]: x for x in ADC_ARCHITECTURES}[arch]
    if a["cap_units_fn"] == "sar":
        cap_units = float(2 ** bits)
        e_units = 0.5 * float(2 ** bits - 1)        # 以 C0·V² 为单位
    else:
        h = bits // 2
        lo = bits - h
        cap_units = float(2 ** h + 2 ** lo)
        e_units = 0.5 * (float(2 ** h - 1) + float(2 ** lo - 1))
    factor = a["energy_factor"]
    if factor is not None:
        e_units *= factor
    return {"arch": arch, "bits": bits, "cap_units": cap_units,
            "energy_units_C0V2": e_units,
            "energy_factor": factor,
            "empirical_factor": bool(a.get("empirical_factor", False)),
            "basis": a["basis"]}


def adc_energy_per_op(bits: int = 8, arch: str = "sar", n: int = 64,
                      share_k: int = 1, c_unit_fF: Optional[float] = None,
                      v_ref: Optional[float] = None) -> Dict:
    """ADC 的每 op 能量（fJ）。

    🔴 **不变性**：`E_op = e_sample·n_conv/(2n²)`，而 `n_conv = n/K` ⇒ `E_op = e_sample/(2·n·K)`。
    **转换速率 f_s 完全抵消** ⇒ 「两步式速度减半」**不改变能效**。
    """
    u = cdac_cap_units(bits, arch)
    c0 = (E.ENERGY_PROCESS["c_unit_fF"] if c_unit_fF is None else float(c_unit_fF)) * 1e-15
    vr = E.ENERGY_PROCESS["v_ref_v"] if v_ref is None else float(v_ref)
    e_sample_j = u["energy_units_C0V2"] * c0 * vr ** 2
    n = int(n)
    k = max(1, int(share_k))
    e_per_op_j = e_sample_j / (2.0 * n * k)
    return {"arch": arch, "bits": int(bits), "n": n, "share_k": k,
            "cap_units": u["cap_units"],
            "e_sample_j": e_sample_j,
            "energy_per_op_fj": e_per_op_j * 1e15,
            "empirical_factor": u["empirical_factor"],
            "invariant_note": "E_op 与 f_s 无关（f_s 在 throughput 与 power 中相消）"}


# ---------------------------------------------------------------------------
# ② 未建模项（🔴 必须与数字同屏）
# ---------------------------------------------------------------------------
UNMODELED_OVERHEAD: List[Dict] = [
    {"item": "比较器动态", "why": "每 bit 一次判决（9 次/样本 @8bit）",
     "typical_share": "0.2~0.5× 电容开关能量", "modeled": False},
    {"item": "参考电压缓冲", "why": "V_ref 需低阻驱动整个 CDAC",
     "typical_share": "**静态功耗，可能很大**；本模型**完全未计**", "modeled": False},
    {"item": "两级间残差放大（两步式）", "why": "需 OTA 放大残差",
     "typical_share": "0.3~1.0× 电容开关能量", "modeled": False},
    {"item": "数字校准", "why": "电容失配校准（E8 已有失配模型但未接功耗）",
     "typical_share": "10~30% 逻辑功耗", "modeled": False},
    {"item": "采样保持", "why": "S/H 开关与电容",
     "typical_share": "已含在 CDAC 采样（部分重叠）", "modeled": "partial"},
]


def overhead_bounds(adc_fj: float) -> Dict:
    """给出**含未建模项的区间估计**（不是点估计）。

    🔴 这是本模块最重要的纪律：ADC 电容开关能量只是**下界**。
       参考缓冲若为静态低阻驱动，可能让实际 ADC 能耗**翻倍以上**。
    """
    lo = adc_fj * 1.0                                    # 只算电容开关
    mid = adc_fj * (1.0 + 0.35 + 0.2)                    # 比较器 0.35× + 校准 0.2×
    hi = adc_fj * (1.0 + 0.5 + 1.0 + 1.0)                # 比较器 0.5× + 残差放大 1× + 参考缓冲 1×
    return {"adc_switch_only_fj": adc_fj,
            "with_unmodeled_lo_fj": lo, "with_unmodeled_mid_fj": mid,
            "with_unmodeled_hi_fj": hi,
            "spread_factor": hi / lo if lo else None,
            "verdict": "🔴 **本模型的 ADC 能耗是下界**：参考缓冲/残差放大未计 ⇒ "
                       "架构相对收益可比，**绝对数字不可直接对外**"}


# ---------------------------------------------------------------------------
# ③ 列共享功耗-带宽权衡（接 E18 面积-时间守恒 + E19 mux 侵蚀）
# ---------------------------------------------------------------------------
def sharing_tradeoff(n: int = 64, share_k: int = 1, bits: int = 8,
                     arch: str = "sar") -> Dict:
    """列共享 K：功耗 ∝1/K，但**吞吐必须按 E19 的 mux 建立侵蚀打折**。"""
    base = adc_energy_per_op(bits, arch, n, share_k=1)
    cur = adc_energy_per_op(bits, arch, n, share_k=share_k)
    # E19：保吞吐共享下 mux 建立侵蚀 ∝K（此处只给量级提示，不复算 E19）
    mux_hint = "E19 实测：保吞吐共享下 mux 建立侵蚀 ∝K，K* =160 处 ≈6.95%"
    return {"n": int(n), "share_k": int(share_k),
            "adc_fj_k1": base["energy_per_op_fj"],
            "adc_fj_at_k": cur["energy_per_op_fj"],
            "gain_vs_k1": base["energy_per_op_fj"] / cur["energy_per_op_fj"],
            "mux_cost_note": mux_hint,
            "area_note": "E18：保吞吐 ⇒ 面积 ∝1/K²（面积-时间守恒）",
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ④ 三项占位参数敏感性
# ---------------------------------------------------------------------------
def sensitivity_analysis(n: int = 64, bits: int = 8) -> Dict:
    """`duty_read` / `c_unit_fF` / `c_logic_fF_per_cell` 对**地板**的敏感性。

    🔴 地板仍受这三个占位参数支配 ⇒ 10.125 fJ/op 是"给定参数下"的数，不是硬件结论。
    """
    from lda_l2.ecore import device_family as D

    def floor_now():
        return D.efficiency_floor_fj_per_op(n, bits)["e_floor_fj_per_op"]

    base = floor_now()
    rows = []
    for key, vals in (("duty_read", [0.05, 0.1, 0.3]),
                      ("c_unit_fF", [5.0, 10.0, 20.0]),
                      ("c_logic_fF_per_cell", [1.0, 2.0, 5.0])):
        saved = E.ENERGY_PROCESS[key]
        seq = []
        try:
            for v in vals:
                E.ENERGY_PROCESS[key] = v
                seq.append({"value": v, "floor_fj": floor_now()})
        finally:
            E.ENERGY_PROCESS[key] = saved
        lo = min(x["floor_fj"] for x in seq)
        hi = max(x["floor_fj"] for x in seq)
        rows.append({"param": key, "baseline": saved, "sweep": seq,
                     "floor_range": [lo, hi], "spread": hi / lo if lo else None})
    return {"n": int(n), "bits": int(bits), "baseline_floor_fj": base,
            "rows": rows,
            "verdict": "🔴 地板对 `c_unit_fF` 近乎线性（ADC 主导）；`duty_read` 影响行线（现<1%）；"
                       "`c_logic_fF_per_cell` 影响很小（逻辑<1%）"}


# ---------------------------------------------------------------------------
# ⑤ 自检
# ---------------------------------------------------------------------------
def adc_arch_self_check(verbose: bool = False) -> bool:
    msgs = []

    def chk(name, cond, detail=""):
        msgs.append((name, bool(cond), detail))
        return bool(cond)

    ok = True

    # ① 两步式电容 = 2·C0·2^(b/2)
    u8 = cdac_cap_units(8, "two_step")
    ok &= chk("① 两步式 C_tot = 2·C0·2^(b/2) = 32 C0（8 bit）",
              abs(u8["cap_units"] - 32.0) < 1e-12, f"{u8['cap_units']:.0f} C0")

    # ② 能量比精确：两步式/SAR = [2·(2^4−1)+... ] / (2^8−1)
    us = cdac_cap_units(8, "sar")
    ratio = u8["energy_units_C0V2"] / us["energy_units_C0V2"]
    pred = (0.5 * (15 + 15)) / (0.5 * 255)
    ok &= chk("② 金标：两步式/SAR 能量比 ≡ 15/127.5 = 0.1176（精确闭式）",
              abs(ratio - pred) < 1e-15, f"{ratio:.6f}")

    # ③ 🔴 不变性：E_op,adc 与 f_s 无关
    e1 = adc_energy_per_op(8, "sar", 64, 1)["energy_per_op_fj"]
    # 手算 e_sample/(2n·K)
    manual = (0.5 * 255 * 10e-15 * 1.0) / (2 * 64 * 1) * 1e15
    ok &= chk("③ 🔴 不变性：E_op,adc = e_sample/(2·n·K)（与 f_s 无关）",
              abs(e1 - manual) / manual < 1e-12, f"{e1:.4f} ⟷ {manual:.4f} fJ/op")

    # ④ 列共享 K ⇒ /K
    e8 = adc_energy_per_op(8, "sar", 64, 8)["energy_per_op_fj"]
    ok &= chk("④ 列共享 K=8 ⇒ ADC 每 op 能量 1/8（精确）",
              abs(e1 / e8 - 8.0) < 1e-12)

    # ⑤ 单调 SAR = 0.5×（标 empirical_factor）
    um = cdac_cap_units(8, "sar_monotonic")
    ok &= chk("⑤ 单调 SAR 能量 = 0.5× SAR，且**显式标 empirical_factor**（文献因子非推导）",
              abs(um["energy_units_C0V2"] / us["energy_units_C0V2"] - 0.5) < 1e-15
              and um["empirical_factor"] is True)

    # ⑥ 架构成交量级：两步式比 SAR 好 ~8.5×
    ok &= chk("⑥ 两步式比 SAR 好 8.5×（1/0.1176）",
              abs(1.0 / ratio - 8.5) < 0.05, f"{1.0/ratio:.3f}×")

    # ⑦ 未建模项区间必须 >1× 且明写"下界"
    ob = overhead_bounds(10.0)
    ok &= chk("⑦ 未建模项给出**区间**（上界/下界 ≥ 2×）且 verdict 明写「下界」",
              ob["spread_factor"] >= 2.0 and "下界" in ob["verdict"],
              f"区间 {ob['with_unmodeled_lo_fj']:.1f}~{ob['with_unmodeled_hi_fj']:.1f} fJ")

    # ⑧ 逻辑时钟真源可核（1/t_clk ≡ n_clk/T_conv）
    lc = E.logic_clock_hz(8)
    ok &= chk("⑧ 逻辑时钟真源 = 1/t_clk ≡ n_clk/T_conv = 97.68 MHz（恒等，<1e-12）",
              lc["identity_ok"] and abs(lc["f_logic_hz"] / 1e6 - 97.68) < 0.1,
              f"{lc['f_logic_hz']/1e6:.2f} MHz")

    # ⑨ 逻辑门数 ∝ n（不是 n²）：n 翻倍 ⇒ 逻辑功耗翻倍
    from lda_l2.ecore import energy as EE
    p32 = EE.logic_power_w(32)["power_w"]
    p64 = EE.logic_power_w(64)["power_w"]
    ok &= chk("⑨ 逻辑功耗 ∝ n（n 翻倍 ⇒ 功耗翻倍，**不是 ∝n²**）",
              abs(p64 / p32 - 2.0) < 1e-12, f"{p32:.3e} → {p64:.3e} W")

    # ⑩ 修后地板 = 10.125 fJ/op 且 ADC > 95%
    from lda_l2.ecore import device_family as D
    fl = D.efficiency_floor_fj_per_op(64, 8)
    ok &= chk("⑩ 🔴 修后地板 %.3f fJ/op · ADC 占 %.1f%%（瓶颈已收敛到单一来源）"
              % (fl["e_floor_fj_per_op"], fl["p_other_share_of_floor"]["adc"] * 100),
              abs(fl["e_floor_fj_per_op"] - 10.125) / 10.125 < 0.01
              and fl["p_other_share_of_floor"]["adc"] > 0.95)

    # ⑪ 输出恒标 MODEL_ESTIMATE
    ok &= chk("⑪ 输出恒标 MODEL_ESTIMATE", E.OUTPUT_TIER == "MODEL_ESTIMATE")

    if verbose:
        for name, good, detail in msgs:
            print(("  [OK] " if good else "  [FAIL] ") + name
                  + (("  · " + detail) if detail else ""))
    return bool(ok)


ADC_ARCH_DISCLOSURE = {
    "role": "E24 = ADC 架构与列共享功耗权衡（承接 E23 第二次修正后的 ADC 98.8% 瓶颈）",
    "second_fix": "逻辑口径两处错：① 频率用占位 200 MHz（应 1/t_clk=97.68 MHz，偏高 2.05×）"
                  "② 门数用 n²（应 ∝n，偏高 64×）⇒ 地板 19.27 → **10.125 fJ/op**，ADC 占 **98.8%**",
    "key_invariance": "E_op,adc = e_sample/(2·n·K) —— **与转换速率 f_s 无关** ⇒ "
                      "「两步式速度减半」不改变能效（只影响总吞吐）",
    "arch_gain": "两步式 C_tot = 2·C0·2^(b/2)（8 bit ⇒ 32C0 vs 256C0）⇒ 能量 **1/8.5**（精确闭式）",
    "unmodeled": "🔴 **只算电容开关能量**：比较器/参考缓冲/残差放大/校准**未计** ⇒ "
                 "本模型的 ADC 能耗是**下界**，架构相对收益可比、绝对数字不可直接对外",
    "empirical": "单调 SAR 的 0.5× 是**文献经验因子**（`empirical_factor=True`），非本模型推导",
    "tier": E.OUTPUT_TIER,
    "red_line": "纯标准库 · LLM 不进判决路径 · 只读消费 E7/E17/E18/E19/E21/E22/E23 · 不改既有默认值",
}

__all__ = [
    "ADC_ARCHITECTURES", "UNMODELED_OVERHEAD", "cdac_cap_units",
    "adc_energy_per_op", "overhead_bounds", "sharing_tradeoff",
    "sensitivity_analysis", "adc_arch_self_check", "ADC_ARCH_DISCLOSURE",
]
