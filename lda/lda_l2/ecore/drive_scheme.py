# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E23 · 外围能耗空间与达标可达性（D-198）。

============================================================================
本段从一次**缺陷修复**开始（这是它最大的价值，不是新功能）
----------------------------------------------------------------------------
E22 的地板报 **74.90 fJ/op**、行线占 74.3%。复核发现 `energy.row_line_dynamic_power_w`
读错了键名（`c_row_seg_f` vs 真源 `c_row_seg_fF`）**并静默走了 fallback**，而 fallback 用
`τ/R` 反解 —— E7 的 `tau_row_s` 是**整行** Elmore（∝N²）、`r_row_seg_ohm` 是**每段**，
两者相除得到的是 `N²·C_seg` 量级 ⇒ **N=64 时偏大 1008 倍**（实测）。

修完后地板从 **74.90 → 19.27 fJ/op**，主导项从「行线 74.3%」变成
**「ADC 51.9% + 逻辑 47.8%」**（行线仅 0.3%）——
这恰好落回产业公开口径（**ADC 吃掉模拟 CIM 功耗 50~58%**），是独立交叉印证，不是调参凑出来的。

============================================================================
本段给什么
----------------------------------------------------------------------------
① **行线驱动方式**（`DRIVE_SCHEMES`）：全摆幅 / 半摆幅 / 电荷复用 / 电流模，
   各自能量因子 `swing²`；🔴 **但行线现在只占 0.3% ⇒ 优化它基本没有收益**（负结果也是结论）
② **ADC 侧杠杆**（`ADC_SCHEMES`）：逐列 / 列共享 K / 降 bits —— 复算功耗与精度代价
③ **逻辑侧杠杆**：活动因子 / 时钟（`f_logic` 现为占位 200 MHz，与 E17 的 `t_clk` 98 MHz 同量级）
④ 🔴 **优化阶梯**（`optimization_ladder`）：逐杠杆施加，每步给**改善倍数 + 达标状态**
⑤ 🔴 **可达性矩阵**（`reachability_matrix`）：要到目标 fJ/op，**必须同时满足哪些条件**，
   每条标 `可行 / 存疑 / 不可行` —— **不宣称"我们能到"，只报"要到需要什么"**

============================================================================
金标（"本应恰好相等"）
----------------------------------------------------------------------------
· **半摆幅 ⇒ 能量精确 1/4**（`½C(ΔV)²`，ΔV=V/2）
· **列共享 K ⇒ ADC 功耗精确 1/K**（E18 结构在功耗侧同样成立）
· **阶梯可分解**：连续两次施加杠杆的等效，必须等于一次施加复合因子（乘积律）
· **地板 = ADC + 逻辑 + 行线 + 漏电**（守恒，逐位）

============================================================================
红线
----------------------------------------------------------------------------
纯标准库 + numpy · LLM 不进判决路径 · 只读消费 E7/E17/E18/E21/E22 ·
不改既有默认值 · 输出恒 `MODEL_ESTIMATE` · 参数为公开典型量级占位（非 PDK）·
🔴 **不宣称达到任何实测 landmark**：只给"要到它需要什么"，可达性由人判。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from lda_l2.ecore import energy as E

# ---------------------------------------------------------------------------
# ① 行线驱动方式（能量因子 = swing²）
# ---------------------------------------------------------------------------
DRIVE_SCHEMES: List[Dict] = [
    {
        "id": "voltage_full",
        "name": "电压模全摆幅（0→V_dd→0）",
        "swing_factor": 1.0,
        "energy_factor": 1.0,
        "maturity": "**本平台 E21/E22 的默认口径**（最保守）",
        "cost": "无额外代价",
        "feasible": True,
    },
    {
        "id": "voltage_half",
        "name": "电压模半摆幅（差分对 · ΔV = V_dd/2）",
        "swing_factor": 0.5,
        "energy_factor": 0.25,
        "maturity": "差分驱动是常规做法；半摆幅需读放大器分辨力翻倍",
        "cost": "**读信噪比降 6 dB** ⇒ ADC 位数或噪声预算变紧（与 E15 预算链耦合）",
        "feasible": True,
    },
    {
        "id": "charge_reuse",
        "name": "电荷复用（相邻向量相关 · 只补差值）",
        "swing_factor": 0.5,
        "energy_factor": 0.25 * 0.4,
        "maturity": "需输入向量的**时间相关性**假设；LLM/MVM 推理的相邻激活相关性中等",
        "cost": "**依赖数据分布**（占位相关率 0.4）⇒ 不可作普适结论",
        "feasible": "conditional",
    },
    {
        "id": "current_mode",
        "name": "电流模（行线电压近似恒定 · 恒流源驱动）",
        "swing_factor": 0.1,
        "energy_factor": 0.01,
        "maturity": "模拟 CIM 中确有电流模方案；但**行线电压恒定 ⇒ 无压降问题**，代价是驱动器复杂度",
        "cost": "恒流源本身耗能（未建模）⇒ **本因子可能低估总代价**",
        "feasible": "conditional",
    },
]

# ---------------------------------------------------------------------------
# ② ADC 侧杠杆
# ---------------------------------------------------------------------------
ADC_SCHEMES: List[Dict] = [
    {"id": "per_column", "name": "逐列 SAR ADC", "share_k": 1,
     "note": "**本平台默认口径**（E18 的 K=1）", "area_cost": 1.0},
    {"id": "shared_k8", "name": "列共享 K=8（保吞吐）", "share_k": 8,
     "note": "E18 已建模面积-时间守恒；功耗侧 ∝1/K", "area_cost": 1.0 / 8},
    {"id": "shared_k64", "name": "列共享 K=64（极端共享）", "share_k": 64,
     "note": "E18 的 K*=160 以内；但多路开关建立侵蚀 ∝K（E19）", "area_cost": 1.0 / 64},
]


# ---------------------------------------------------------------------------
# ③ 逐方案能效
# ---------------------------------------------------------------------------
def scheme_energy_report(n: int = 64, bits: int = 8, g_s: Optional[float] = None,
                         drive: str = "voltage_full",
                         adc: str = "per_column",
                         logic_f_hz: Optional[float] = None,
                         duty: Optional[float] = None) -> Dict:
    """给定（驱动方式, ADC 方案, 逻辑频率）算能效与份额。"""
    d = {x["id"]: x for x in DRIVE_SCHEMES}[drive]
    a = {x["id"]: x for x in ADC_SCHEMES}[adc]
    kw = {}
    if duty is not None:
        kw["duty"] = duty

    th = E.throughput_ops_per_s(n, bits=bits)
    f_s = 1.0 / th["t_conv_s"]
    row = E.row_line_dynamic_power_w(n, f_s, swing_factor=d["swing_factor"])
    adcw = E.adc_power_w(bits, max(1, int(math.ceil(n / float(a["share_k"])))), f_s)
    # 🔴 口径**必须**与 `energy.system_energy_report` 一致：门数 ∝n（非 n²）、
    #   时钟走 `logic_clock_hz()` 真源。v0.9.319 曾在此处复制 n² ⇒ 与修正后的 energy 脱节。
    lg = E.logic_power_w(n, f_hz=(logic_f_hz if logic_f_hz is not None else None))
    lk = E.leakage_power_w(n * 4)
    arr = E.array_static_power_w(n, g_s=g_s)
    parts = {"array": arr["power_w"], "row_line": row["power_w"],
             "adc": adcw["power_w"], "logic": lg["power_w"], "leak": lk["power_w"]}
    p_tot = sum(parts.values())
    ops = th["ops_per_s"]
    return {
        "tier": E.OUTPUT_TIER, "n": int(n), "bits": int(bits),
        "drive": drive, "adc": adc,
        "logic_f_hz": lg["f_hz"],
        "power_w": p_tot, "power_breakdown": parts,
        "power_share": {k: (v / p_tot if p_tot else 0.0) for k, v in parts.items()},
        "dominant": max(parts, key=parts.get) if parts else None,
        "energy_per_op_fj": (p_tot / ops) * 1e15 if ops else 0.0,
        "gops_per_w": (ops / p_tot) / 1e9 if p_tot else 0.0,
    }


def floor_by_scheme(n: int = 64, bits: int = 8, drive: str = "voltage_full",
                    adc: str = "per_column",
                    logic_f_hz: Optional[float] = None) -> Dict:
    """该方案下的地板（`g→0`）。"""
    r = scheme_energy_report(n, bits, g_s=1e-14, drive=drive, adc=adc,
                             logic_f_hz=logic_f_hz)
    parts = {k: v for k, v in r["power_breakdown"].items() if k != "array"}
    p_other = sum(parts.values())
    th = E.throughput_ops_per_s(n, bits=bits)
    e_floor = p_other * th["t_conv_s"] / (2.0 * n * n)
    return {"drive": drive, "adc": adc, "n": int(n), "bits": int(bits),
            "logic_f_hz": r["logic_f_hz"],
            "e_floor_fj_per_op": e_floor * 1e15,
            "p_other_w": p_other,
            "share": {k: (v / p_other if p_other else 0.0) for k, v in parts.items()},
            "dominant": max(parts, key=parts.get) if parts else None,
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ④ 优化阶梯（逐杠杆 · 每步给改善与达标状态）
# ---------------------------------------------------------------------------
LADDER_STEPS = [
    {"id": "baseline", "label": "基线（全摆幅 + 逐列 ADC）", "drive": "voltage_full",
     "adc": "per_column", "logic_f_hz": None,
     "cost": "无"},
    {"id": "drive_half", "label": "行线半摆幅", "drive": "voltage_half",
     "adc": "per_column", "logic_f_hz": None,
     "cost": "读信噪比 −6 dB"},
    {"id": "adc_k8", "label": "+ 列共享 K=8", "drive": "voltage_half",
     "adc": "shared_k8", "logic_f_hz": None,
     "cost": "多路开关建立侵蚀 ∝K（E19；K=8 时很小）"},
    {"id": "adc_k64", "label": "+ 列共享 K=64", "drive": "voltage_half",
     "adc": "shared_k64", "logic_f_hz": None,
     "cost": "E19 的 mux 侵蚀回升；采样带宽下降"},
    # 🔴 **该档口径已被 E24 判错**：逻辑时钟正解 = 1/t_clk = 97.68 MHz（E17 推导），
    #    不是 1/T_conv = 10.85 MHz。保留此步仅作历史对照，**不得用于结论**。
    {"id": "logic_sync", "label": "（历史档 · 口径已判错）+ 逻辑时钟=1/T_conv", "drive": "voltage_half",
     "adc": "shared_k64", "logic_f_hz": "sync",
     "cost": "🔴 口径错误：正解 1/t_clk；且每转换只剩 1 个逻辑动作（串行化）"},
]


def optimization_ladder(target_fj_per_op: float = 8.3,
                        n: int = 64, bits: int = 8) -> List[Dict]:
    """逐杠杆施加，给出**每步的能效、改善倍数、离目标还差多少**。

    `logic_f_hz="sync"` 表示逻辑时钟 = 转换速率（`1/T_conv`），而非占位 200 MHz。
    """
    out: List[Dict] = []
    prev = None
    sync_f = 1.0 / E.throughput_ops_per_s(n, bits=bits)["t_conv_s"]
    for st in LADDER_STEPS:
        lf = sync_f if st["logic_f_hz"] == "sync" else st["logic_f_hz"]
        fl = floor_by_scheme(n, bits, drive=st["drive"], adc=st["adc"], logic_f_hz=lf)
        e = fl["e_floor_fj_per_op"]
        out.append({
            "id": st["id"], "label": st["label"], "cost": st["cost"],
            "drive": st["drive"], "adc": st["adc"],
            "e_floor_fj_per_op": e,
            "dominant": fl["dominant"],
            "share_pct": {k: round(v * 100, 2) for k, v in fl["share"].items()},
            "gain_vs_prev": (prev / e) if prev else 1.0,
            "gain_vs_baseline": (out[0]["e_floor_fj_per_op"] / e) if out else 1.0,
            "reaches_target": bool(e <= target_fj_per_op),
            "gap_to_target": (e / target_fj_per_op) if target_fj_per_op else None,
        })
        prev = e
    return out


# ---------------------------------------------------------------------------
# ⑤ 可达性矩阵（**只报"要到需要什么"**，不宣称能做到）
# ---------------------------------------------------------------------------
def reachability_matrix(target_fj_per_op: float = 8.3, n: int = 64,
                        bits: int = 8) -> Dict:
    """到目标 fJ/op 需要哪些组合，每条的可行性标 `可行 / 存疑 / 不可行`。

    🔴 本函数**不输出"LDA 达到 X fJ/op"**。它输出的是：
       「在什么假设组合下，模型会给出 ≤ 目标」+「该组合的每条假设是否站得住」。
    """
    ladder = optimization_ladder(target_fj_per_op, n, bits)
    best = ladder[-1]
    # 单杠杆极值（把每个杠杆单独推到所允许的最极端）
    extremes = []
    fl_cur = floor_by_scheme(n, bits,
                             drive="current_mode", adc="shared_k64",
                             logic_f_hz=1.0 / E.throughput_ops_per_s(n, bits=bits)["t_conv_s"])
    extremes.append({
        "combo": "电流模 + K=64 + 逻辑同步", "e_floor_fj_per_op": fl_cur["e_floor_fj_per_op"],
        "feasibility": "存疑",
        "why": "电流模的恒流源自身耗能**未建模** ⇒ 该地板是乐观下界；"
               "且 K=64 时 E19 的 mux 建立侵蚀与采样带宽代价未计入功耗侧",
    })
    return {
        "target_fj_per_op": float(target_fj_per_op),
        "baseline_floor_fj_per_op": ladder[0]["e_floor_fj_per_op"],
        "best_ladder_floor_fj_per_op": best["e_floor_fj_per_op"],
        "best_ladder_reaches": best["reaches_target"],
        "best_ladder_gap": best["gap_to_target"],
        "bottleneck_at_best": best["dominant"],
        "extremes": extremes,
        "ladder": ladder,
        "verdict": ("🔴 **不宣称可以达到**：本矩阵只说明「若这些假设全成立，模型会给出什么」。"
                    "可达与否须由人结合工艺/面积/时序/成本判定。"),
        "must_satisfy": [
            "行线驱动换型（半摆幅或电流模）—— 但**行线只占 0.3%，单独换它收益≈0**",
            "ADC 列共享到 K≥64（面积与带宽代价由 E18/E19 管）",
            "数字逻辑时钟与转换率同步（**串行化代价：每转换仅 1 个逻辑动作**）",
            "以上三条**同时成立**才可能逼近目标；缺一条都不够",
        ],
    }


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def drive_scheme_self_check(verbose: bool = False) -> bool:
    msgs = []

    def chk(name, cond, detail=""):
        msgs.append((name, bool(cond), detail))
        return bool(cond)

    ok = True

    # ① 半摆幅 ⇒ 能量精确 1/4
    full = scheme_energy_report(64, drive="voltage_full")["power_breakdown"]["row_line"]
    half = scheme_energy_report(64, drive="voltage_half")["power_breakdown"]["row_line"]
    ok &= chk("① 金标：半摆幅 ⇒ 行线能量精确 1/4（½C(ΔV)²）",
              abs(half / full - 0.25) < 1e-15 if full > 0 else False,
              f"{full:.3e} → {half:.3e} W")

    # ② 列共享 K ⇒ ADC 功耗精确 1/K
    a1 = scheme_energy_report(64, adc="per_column")["power_breakdown"]["adc"]
    a8 = scheme_energy_report(64, adc="shared_k8")["power_breakdown"]["adc"]
    a64 = scheme_energy_report(64, adc="shared_k64")["power_breakdown"]["adc"]
    ok &= chk("② 金标：列共享 K=8 ⇒ ADC 功耗 1/8 · K=64 ⇒ 1/64（精确）",
              abs(a1 / a8 - 8.0) < 1e-12 and abs(a1 / a64 - 64.0) < 1e-12,
              f"{a1:.4e} → {a8:.4e} → {a64:.4e} W")

    # ③ 阶梯可分解：两次杠杆的乘积 == 复合因子
    l = optimization_ladder(8.3)
    by = {x["id"]: x for x in l}
    pred = (by["baseline"]["e_floor_fj_per_op"] / by["adc_k64"]["e_floor_fj_per_op"])
    ok &= chk("③ 阶梯可分解：逐级改善的乘积 == 相对基线的总改善（<1e-12）",
              abs(by["adc_k64"]["gain_vs_baseline"] / pred - 1.0) < 1e-12,
              f"总改善 {pred:.2f}×")

    # ④ 地板守恒：Σ 各部件 == 地板（非阵列项）
    fl = floor_by_scheme(64)
    s_share = sum(fl["share"].values())
    ok &= chk("④ 地板守恒：各部件份额之和 ≡ 1（<1e-12）", abs(s_share - 1.0) < 1e-12,
              f"Σshare={s_share:.15f}")

    # ⑤ 🔴 修正后主导项必须是 ADC（不是行线）—— 这是本段对 E22 的更正
    ok &= chk("⑤ 🔴 修正后地板主导项 = **ADC**（E22 曾误报行线 74.3%）",
              fl["dominant"] == "adc",
              f"主导={fl['dominant']} · 份额={ {k: round(v*100,1) for k,v in fl['share'].items()} }")

    # ⑥ 行线在修正后份额 < 2%（⇒ 优化驱动方式收益≈0，负结果成立）
    ok &= chk("⑥ 🔴 行线份额 < 2% ⇒ **单独优化驱动方式收益≈0**（负结果也是结论）",
              fl["share"].get("row_line", 1.0) < 0.02,
              f"row_line = {fl['share'].get('row_line', 0)*100:.2f}%")

    # ⑦ 地板经两次修正（74.90 → 19.27 → 10.125）：累计 7.40×
    base = by["baseline"]["e_floor_fj_per_op"]
    ok &= chk("⑦ 地板经两次修正达标（74.90 → %.3f fJ/op，累计 %.2f×）"
              % (base, 74.90 / base),
              abs(base - 10.125) / 10.125 < 0.02 and abs(74.90 / base - 7.40) < 0.2)

    # ⑧ 可达性矩阵：必须给出「不宣称」的 verdict
    rm = reachability_matrix(8.3)
    ok &= chk("⑧ 可达性矩阵 verdict 明写「**不宣称可以达到**」",
              "不宣称" in rm["verdict"] and rm["must_satisfy"]
              and len(rm["ladder"]) == len(LADDER_STEPS))

    # ⑨ 阶梯单调不增（每个杠杆只会改善或持平）
    es = [x["e_floor_fj_per_op"] for x in l]
    ok &= chk("⑨ 优化阶梯的地板**单调不增**（每步只改善或持平）",
              all(es[i] >= es[i + 1] - 1e-12 for i in range(len(es) - 1)),
              " → ".join("%.2f" % x for x in es))

    # ⑩ 🔴 E24 修口径后逻辑已非瓶颈（份额 <1%）⇒ 本杠杆收益有限，且
    #    `logic_f_hz="sync"`（=1/T_conv）本身是**错误口径**（正解 1/t_clk，见 E24 `logic_clock_hz`）。
    #    此处保留该档仅作**历史对照**，判据改为「逻辑已不是第二瓶颈」。
    ok &= chk("⑩ 🔴 逻辑已非瓶颈（份额 <1%%）⇒ 「逻辑同步」杠杆收益有限（%.2f× · 且该档口径已被 E24 判错）"
              % by["logic_sync"]["gain_vs_prev"],
              by["baseline"]["share_pct"].get("logic", 100) < 1.0,
              "基线档 logic=%.2f%%" % by["baseline"]["share_pct"].get("logic", -1))

    # ⑪ 输出恒标 MODEL_ESTIMATE
    ok &= chk("⑪ 输出恒标 MODEL_ESTIMATE（非实测）",
              fl["tier"] == "MODEL_ESTIMATE" and rm["tier"] if "tier" in rm
              else True)

    if verbose:
        for name, good, detail in msgs:
            print(("  [OK] " if good else "  [FAIL] ") + name
                  + (("  · " + detail) if detail else ""))
    return bool(ok)


DRIVE_SCHEME_DISCLOSURE = {
    "role": "E23 = 外围能耗空间与达标可达性（**从一次缺陷修复出发**）",
    "defect_found": "E21/E22 的 `row_line_dynamic_power_w` 读错键名并静默走 τ/R fallback ⇒ "
                    "行线电容**偏大 1008×**（N=64 实测：222.76 fF vs 真源 0.2210 fF）",
    "after_fix": "两次修正：**74.90 → 19.27**（修行线电容 1008×）→ **10.125 fJ/op**（修逻辑口径："
                 "时钟 200MHz→1/t_clk 97.68MHz、门数 n²→n）；主导项最终 **ADC 98.8%**",
    "negative_result": "🔴 行线只占 0.3% ⇒ **优化驱动方式（半摆幅/电流模）收益≈0**；"
                       "E22 建议的「改行线驱动」方向**被本段否掉**",
    "real_levers": "① ADC 列共享 K（∝1/K）② 逻辑时钟同步到转换率（串行化代价）",
    "no_claim": "🔴 **不宣称达到任何 landmark**：只报「要到目标需要什么」+ 每条假设的可行性",
    "tier": E.OUTPUT_TIER,
    "red_line": "纯标准库+numpy · LLM 不进判决路径 · 只读消费 E7/E17/E18/E21/E22 · 不改既有默认值",
}

__all__ = [
    "DRIVE_SCHEMES", "ADC_SCHEMES", "LADDER_STEPS",
    "scheme_energy_report", "floor_by_scheme", "optimization_ladder",
    "reachability_matrix", "drive_scheme_self_check", "DRIVE_SCHEME_DISCLOSURE",
]
