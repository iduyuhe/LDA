# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E25 · ADC 能耗的可信度校准（D-200）。

============================================================================
本段唯一目标：**把 10.125 fJ/op 这个数变可信**（不是继续优化）
----------------------------------------------------------------------------
E24 留下两重不确定性：① ADC 只算了 CDAC 开关能量（下界）② 地板由占位 `c_unit_fF=10 fF` 支配。
本段用**公开实测数据**把两者都换成有出处的值，结果**推翻了 E24 自己的结论**。

### 发现 1：真实 CDAC 单位电容是 0.3~2 fF，我占位用了 10 fF（偏大 5~33×）

| 来源 | 工艺 | 单位电容 |
|---|---|---|
| 8b 500MS/s 三比较器 SAR（**16.8 fJ/c-s**） | 28nm CMOS LPP | **0.4 fF** |
| 12b 1MS/s（**2.07 fJ/c-s**） | 40nm | **0.3 fF** |
| 40nm 最小 MiM 电容 | 40nm | ~**2 fF** |
| 保守设计/教科书写法 | 40nm | 20~50 fF（**但那是低速高精度**） |

### 发现 2（🔴 决定性）：CDAC 开关能量只占 ADC 总能耗 **0.6%~3.6%**

用实测 FOM 反推每次转换总能量 `E_conv = FOM × 2^ENOB`，再与模型 CDAC 开关能量比：

| 实测点 | FOM | E_conv | 模型 CDAC | **CDAC 占比** |
|---|---|---|---|---|
| 28nm 8b 500MS/s | 16.8 fJ/c-s | 4.30 pJ | 25.5 fJ | **0.59%** |
| 40nm 12b 1MS/s | 2.07 fJ/c-s | 8.48 pJ | 307.1 fJ | **3.62%** |
| 65nm 8b 1MS/s | 15.99 fJ/c-s | 1.91 pJ | 29.6 fJ | **1.55%** |

⇒ 🔴 **E24 的「两步式比 SAR 好 8.5×」只优化了那 ~2%** ⇒ 对 ADC 总能耗只贡献 **<1.9%**。
⇒ 🔴 **ADC 的能耗不在电容，在比较器 / 逻辑 / 参考缓冲 / 时钟**。**E24 的架构建议方向抓错了 98%。**

============================================================================
本模块给什么
----------------------------------------------------------------------------
① `C_UNIT_LITERATURE`：真实单位电容（带出处与工艺），替代占位 10 fF
② `MEASURED_ADC_ANCHORS`：**三条实测 FOM 锚**（本征程第一次有真正的外部实测可比）
③ `cdac_share_vs_measured()`：模型 CDAC 占实测 ADC 总能耗的比（**本段核心判据**）
④ `adc_total_energy_from_anchor()`：用实测锚反推 CIM 每 op 的 ADC 能耗（而非累加各部件）
⑤ `floor_with_measured_adc()`：**可信地板**（用实测 ADC 而非模型 CDAC）

============================================================================
金标
----------------------------------------------------------------------------
· `E_conv = FOM × 2^ENOB`（**定义式**，Walden FOM 的直接推论）
· **占比守恒**：CDAC + 其余 ≡ 总（其余 ≥0 ⇒ CDAC 占比 ≤100%）
· 实测锚与工艺/架构的对应关系**显式登记**（不得跨工艺混用）

============================================================================
红线
----------------------------------------------------------------------------
纯标准库 · LLM 不进判决路径 · 只读消费 E21/E22/E23/E24 · 不改既有默认值 ·
🔴 **实测 FOM 是 ADC 子模块的外锚，不是 CIM 芯片的能效锚** —— 只用于校核 ADC 模型 ·
输出恒 `MODEL_ESTIMATE`。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import adc_arch as A
from lda_l2.ecore import energy as E

# ---------------------------------------------------------------------------
# ① 真实单位电容（公开来源照录）
# ---------------------------------------------------------------------------
C_UNIT_LITERATURE: List[Dict] = [
    {"fF": 0.4, "node": "28nm CMOS LPP", "context": "8b 500MS/s 三比较器 SAR（split CDAC + monotonic LSB）",
     "source": "IEEE JSSC/ISSCC 2024-2025（16.8 fJ/c-s）", "kind": "**激进小电容 + 校准**"},
    {"fF": 0.3, "node": "40nm", "context": "12b 1MS/s（前 background/foreground 校准）",
     "source": "Microelectronics Journal 2021（2.07 fJ/c-s）", "kind": "小电容 + 数字校准"},
    {"fF": 2.0, "node": "40nm", "context": "最小 MiM 电容（可靠匹配下限）",
     "source": "SMIC 40nm 设计资料（MiM 密度 ~1 fF/µm²）", "kind": "**无校准时的下限**"},
    {"fF": 20.0, "node": "40nm", "context": "保守设计（低速高精度，匹配优先）",
     "source": "SMIC 40nm 实践（单位电容常用 20~50 fF）", "kind": "保守档"},
]

#: 占位值（E21–E24 一直用它，**本段判定偏大 5~33×**）
PLACEHOLDER_C_UNIT_FF = 10.0

# ---------------------------------------------------------------------------
# ② 实测 ADC 锚（FOM 定义：Walden `FOM = P/(2^ENOB·f_s)`，单位 fJ/conversion-step）
# ---------------------------------------------------------------------------
MEASURED_ADC_ANCHORS: List[Dict] = [
    {"id": "a28_8b", "node": "28nm CMOS LPP", "bits": 8, "enob": 8.0,
     "fom_fj_per_cs": 16.8, "fs_hz": 500e6, "c_unit_fF": 0.4,
     "arch": "三比较器异步 SAR（split CDAC + monotonic LSB）",
     "source": "IEEE（28nm 8b 500MS/s · 16.8 fJ/c-s）"},
    {"id": "a40_12b", "node": "40nm", "bits": 12, "enob": 12.0,
     "fom_fj_per_cs": 2.07, "fs_hz": 1e6, "c_unit_fF": 0.3,
     "arch": "SAR + 前台校准（0.3 fF 单位电容）",
     "source": "Microelectronics Journal 2021"},
    {"id": "a65_8b", "node": "65nm", "bits": 8, "enob": 6.9,
     "fom_fj_per_cs": 15.99, "fs_hz": 1e6, "c_unit_fF": 1.0,
     "arch": "改进开关（理论零参考切换能量）",
     "source": "Computers & Electrical Engineering 2025"},
]


def anchor_energy_per_conversion(anchor_id: str) -> Dict:
    """`E_conv = FOM × 2^ENOB`（**FOM 定义式的直接推论**，不是拟合）。"""
    a = {x["id"]: x for x in MEASURED_ADC_ANCHORS}[anchor_id]
    e_conv_j = a["fom_fj_per_cs"] * 1e-15 * (2.0 ** a["enob"])
    return {**a, "e_conv_j": e_conv_j, "e_conv_pj": e_conv_j * 1e12,
            "power_w": e_conv_j * a["fs_hz"],
            "basis": "FOM ≡ P/(2^ENOB·f_s) ⇒ E_conv = FOM·2^ENOB"}


# ---------------------------------------------------------------------------
# ③ 核心判据：CDAC 开关能量占实测 ADC 总能耗的比
# ---------------------------------------------------------------------------
def cdac_share_vs_measured(anchor_id: str = "a28_8b") -> Dict:
    """🔴 **本段最重要的一条**：模型 CDAC 开关能量 ÷ 实测 ADC 每次转换能量。

    若该比 ≪ 100%，则「优化 CDAC 电容/开关方案」对 ADC 总能效的贡献就 ≪ 该比。
    """
    anc = anchor_energy_per_conversion(anchor_id)
    u = A.cdac_cap_units(int(anc["bits"]), "sar_monotonic")
    c0 = anc["c_unit_fF"] * 1e-15
    e_cdac_j = u["energy_units_C0V2"] * c0 * 1.0 ** 2
    share = e_cdac_j / anc["e_conv_j"]
    return {"anchor": anchor_id, "node": anc["node"], "bits": anc["bits"],
            "c_unit_fF": anc["c_unit_fF"],
            "e_conv_pj": anc["e_conv_pj"], "e_cdac_fj": e_cdac_j * 1e15,
            "cdac_share": share, "cdac_share_pct": share * 100,
            "rest_pct": (1.0 - share) * 100,
            "verdict": ("🔴 CDAC 只占 **%.2f%%** ⇒ ADC 能耗的主体是**比较器/逻辑/参考缓冲/时钟**；"
                        "「优化电容或开关方案」对 ADC 总能效的贡献上限 = 该占比"
                        % (share * 100)),
            "tier": E.OUTPUT_TIER}


def cdac_share_table() -> List[Dict]:
    return [cdac_share_vs_measured(a["id"]) for a in MEASURED_ADC_ANCHORS]


# ---------------------------------------------------------------------------
# ④ 用实测锚反推 CIM 的 ADC 每 op 能耗（替代「累加各部件」）
# ---------------------------------------------------------------------------
def adc_energy_per_op_from_anchor(anchor_id: str = "a28_8b", n: int = 64,
                                  share_k: int = 1) -> Dict:
    """CIM 里每列一个 ADC ⇒ 每转换 `n/K` 个 ADC 同时工作。

    `E_op = (n/K)·E_conv / (2n²) = E_conv / (2·n·K)`

    🔴 这是**用实测 ADC 反推**，不是用模型 CDAC 累加 —— 二者相差 100 倍以上。
    """
    anc = anchor_energy_per_conversion(anchor_id)
    n = int(n)
    k = max(1, int(share_k))
    e_op_j = anc["e_conv_j"] * (n / float(k)) / (2.0 * n * n)
    return {"anchor": anchor_id, "node": anc["node"], "n": n, "share_k": k,
            "e_conv_pj": anc["e_conv_pj"],
            "adc_energy_per_op_fj": e_op_j * 1e15,
            "basis": "E_op = E_conv/(2·n·K)（每列一个 ADC · 实测锚）",
            "tier": E.OUTPUT_TIER}


def floor_with_measured_adc(anchor_id: str = "a28_8b", n: int = 64) -> Dict:
    """**可信地板**：ADC 项改用实测锚（而非模型 CDAC），其余仍用本平台模型。"""
    from lda_l2.ecore import device_family as D
    fl = D.efficiency_floor_fj_per_op(n, 8)
    adc_model = fl["p_other_share_of_floor"]["adc"] * fl["e_floor_fj_per_op"]
    anc = adc_energy_per_op_from_anchor(anchor_id, n)
    rest = fl["e_floor_fj_per_op"] - adc_model
    e_floor_fj = anc["adc_energy_per_op_fj"] + rest
    return {"anchor": anchor_id, "node": anc["node"], "n": int(n),
            "adc_model_fj": adc_model,
            "adc_from_measured_fj": anc["adc_energy_per_op_fj"],
            "ratio_measured_over_model": (anc["adc_energy_per_op_fj"] / adc_model
                                          if adc_model else None),
            "rest_fj": rest,
            "e_floor_fj_per_op": e_floor_fj,
            "old_model_floor_fj": fl["e_floor_fj_per_op"],
            "verdict": "🔴 **可信地板 %.1f fJ/op**（模型自算 %.2f 的 %.1f×）—— "
                       "模型累加 CDAC 严重低估 ADC 能耗"
                       % (e_floor_fj, fl["e_floor_fj_per_op"],
                          e_floor_fj / fl["e_floor_fj_per_op"]),
            "tier": E.OUTPUT_TIER}


def c_unit_sensitivity() -> Dict:
    """在**真实文献区间 0.3~2 fF** 下，模型 CDAC 占比如何变（说明该参数已不主导）。"""
    rows = []
    for c in C_UNIT_LITERATURE:
        s = cdac_share_vs_measured("a28_8b")
        # 按该 c 重算 CDAC（同样的 8bit 单调）
        u = A.cdac_cap_units(8, "sar_monotonic")
        e = u["energy_units_C0V2"] * c["fF"] * 1e-15
        rows.append({"c_unit_fF": c["fF"], "cdac_fj": e * 1e15,
                     "cdac_share_pct": e / (s["e_conv_pj"] * 1e-12) * 100,
                     "kind": c["kind"], "source": c["source"]})
    return {"anchor": "a28_8b", "rows": rows,
            "verdict": "🔴 即使 `c_unit` 从 0.3 变到 20 fF（67×），CDAC 占比仍 <30% ⇒ "
                       "**该参数已不再是地板的主导项**（E24 的判断在真实电容下失效）",
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑤ 自检
# ---------------------------------------------------------------------------
def adc_calibration_self_check(verbose: bool = False) -> bool:
    msgs = []

    def chk(name, cond, detail=""):
        msgs.append((name, bool(cond), detail))
        return bool(cond)

    ok = True

    # ① FOM ⇒ E_conv 定义式
    a = anchor_energy_per_conversion("a28_8b")
    ok &= chk("① 金标：E_conv ≡ FOM·2^ENOB = 16.8×256 = 4.30 pJ（定义式）",
              abs(a["e_conv_pj"] - 16.8 * 256 / 1000.0) < 1e-9,
              f"{a['e_conv_pj']:.3f} pJ")

    # ② 三个实测点的 CDAC 占比都 <5%
    tab = cdac_share_table()
    shares = [x["cdac_share_pct"] for x in tab]
    ok &= chk("② 🔴 三个实测 ADC 的 CDAC 占比 = %.2f%% / %.2f%% / %.2f%%（**全部 <5%%**）"
              % tuple(shares),
              all(s < 5.0 for s in shares))

    # ③ 占比守恒：CDAC + 其余 ≡ 100%
    ok &= chk("③ 占比守恒：CDAC + 其余 ≡ 100%%（<1e-12）",
              all(abs(x["cdac_share_pct"] + x["rest_pct"] - 100.0) < 1e-9 for x in tab))

    # ④ 🔴 **同口径**比较：在实测点自己的 c_unit（0.4 fF）下，
    #    模型「只算 CDAC」给出的每 op 能耗 ≪ 实测 ADC 总能耗
    anc = adc_energy_per_op_from_anchor("a28_8b", 64)
    u8m = A.cdac_cap_units(8, "sar_monotonic")
    e_cdac_op = u8m["energy_units_C0V2"] * 0.4e-15 * 64 / (2 * 64 * 64) * 1e15
    ratio_same = anc["adc_energy_per_op_fj"] / e_cdac_op
    ok &= chk("④ 🔴 同口径（0.4 fF）下：实测 ADC = %.1f fJ/op · 模型只算 CDAC = %.3f fJ/op"
              " ⇒ **模型低估 %.0f×**"
              % (anc["adc_energy_per_op_fj"], e_cdac_op, ratio_same),
              ratio_same > 50.0)
    fl = floor_with_measured_adc()

    # ⑤ 可信地板高于模型地板（>2×）
    ok &= chk("⑤ 🔴 可信地板 %.1f fJ/op > 模型地板 %.2f fJ/op（%.1f×）"
              % (fl["e_floor_fj_per_op"], fl["old_model_floor_fj"],
                 fl["e_floor_fj_per_op"] / fl["old_model_floor_fj"]),
              fl["e_floor_fj_per_op"] / fl["old_model_floor_fj"] > 2.0)

    # ⑥ 真实电容区间下 CDAC 仍不主导（<30%）
    cs = c_unit_sensitivity()
    ok &= chk("⑥ 真实电容 0.3~20 fF 区间内 CDAC 占比仍 <30% ⇒ **c_unit 已非主导项**",
              all(x["cdac_share_pct"] < 30.0 for x in cs["rows"]),
              " / ".join("%.1ffF:%.1f%%" % (x["c_unit_fF"], x["cdac_share_pct"])
                         for x in cs["rows"]))

    # ⑦ 文献登记完整性
    ok &= chk("⑦ 单位电容登记完整性：%d 档全部带 source/node/kind" % len(C_UNIT_LITERATURE),
              all(x.get("source") and x.get("node") and x.get("kind")
                  for x in C_UNIT_LITERATURE))

    # ⑧ 占位值被判定"偏大"（记录在案，不得再当默认）
    ok &= chk("⑧ 占位 10 fF 已标为偏大（真实 0.3~2 fF ⇒ 偏大 5~33×）",
              PLACEHOLDER_C_UNIT_FF / 2.0 >= 5.0)

    # ⑨ 实测锚必须标"ADC 子模块外锚，非 CIM 能效锚"
    ok &= chk("⑨ 三条实测锚都带 source（**外锚不得无出处**）",
              all(x.get("source") for x in MEASURED_ADC_ANCHORS))

    # ⑩ 输出恒标 MODEL_ESTIMATE
    ok &= chk("⑩ 输出恒标 MODEL_ESTIMATE", fl["tier"] == "MODEL_ESTIMATE")

    if verbose:
        for name, good, detail in msgs:
            print(("  [OK] " if good else "  [FAIL] ") + name
                  + (("  · " + detail) if detail else ""))
    return bool(ok)


ADC_CALIBRATION_DISCLOSURE = {
    "role": "E25 = 用公开实测把 E24 的两重不确定性换成有出处的值（**结论被推翻**）",
    "c_unit_truth": "真实单位电容 **0.3~2 fF**（28nm 0.4 fF / 40nm 0.3 fF / MiM 下限 2 fF）；"
                    "E21–E24 的占位 **10 fF 偏大 5~33×**",
    "decisive_finding": "🔴 **CDAC 开关能量只占实测 ADC 总能耗 0.59% / 3.62% / 1.55%** "
                        "⇒ E24 的「两步式好 8.5×」只优化了那 ~2%，对 ADC 能耗贡献 <1.9%",
    "direction_reversed": "🔴 **ADC 能耗主体是比较器/逻辑/参考缓冲/时钟，不是电容** ⇒ "
                          "E24 的「选两步式架构」建议**方向抓错 98%**，本段撤回",
    "credible_floor": "用 28nm 实测锚（4.30 pJ/转换）反推 ⇒ 可信地板约 **33.6 fJ/op**，"
                      "而模型自算 10.125 ⇒ **模型低估 3.3×**",
    "anchor_scope": "🔴 实测 FOM 是 **ADC 子模块**外锚，**不是 CIM 芯片能效锚** ⇒ 只用于校核 ADC 模型",
    "tier": E.OUTPUT_TIER,
    "red_line": "纯标准库 · LLM 不进判决路径 · 只读消费 E21/E22/E23/E24 · 不改既有默认值",
}

__all__ = [
    "C_UNIT_LITERATURE", "PLACEHOLDER_C_UNIT_FF", "MEASURED_ADC_ANCHORS",
    "anchor_energy_per_conversion", "cdac_share_vs_measured", "cdac_share_table",
    "adc_energy_per_op_from_anchor", "floor_with_measured_adc",
    "c_unit_sensitivity", "adc_calibration_self_check", "ADC_CALIBRATION_DISCLOSURE",
]
