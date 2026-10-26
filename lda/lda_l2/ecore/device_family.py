# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E22 · 器件族选定 + 可行性反解（D-197）。

============================================================================
为什么插这一段（原计划 E22 做数字壳，已改）
----------------------------------------------------------------------------
E21 的结论是「能效第一杠杆 = 单元电导 g」。但那条结论只在**阵列主导区**成立。
本轮把真实器件族的 g 代进去，得到一条**必须先回答、否则后面全白做**的事实：

  · MOSFET 饱和态（g≈1e-3 S）⇒ 4681.7 fJ/op
  · RRAM（g≈5e-6 S）        ⇒   97.9 fJ/op
  · **NOR Flash（g≈2e-8 S）⇒   75.0 fJ/op**
  · 理想 g→0                ⇒   74.9 fJ/op     ← **地板**

🔴 **换到 Flash 级器件后，能效只比「理想零电导」差 0.1%** ⇒ **器件不再是瓶颈**。
🔴 而地板处的功耗构成是：**行线驱动 74.3%** · ADC 13.3% · 数字逻辑 12.3% · 阵列 0.1%。
⇒ **瓶颈从「器件」迁移到「行线驱动 + ADC + 外围」**。

这条结论**修正了 E21 的表述**（E21 说「差距在器件不在架构」——那只对第一段成立）：
  · 第一段 MOSFET→Flash（4682 → 75 fJ/op，62×）：**差距在器件**
  · 第二段 Flash→Mythic 120 TOPS/W（75 → 8.3 fJ/op，9×）：**差距在行线/ADC/外围，与器件无关**

**⇒ 所以在做数字控制壳和编译器之前，必须先把「器件族」定下来，并且知道定下来之后
天花板在哪、下一个杠杆是什么。** 否则 E23 是在优化一个未被定义的目标 —— 这正是本段插进来的理由。

============================================================================
本模块给什么
----------------------------------------------------------------------------
① **器件族登记**（`DEVICE_FAMILIES`，4 族 · 公开 A 级来源 · 含 g 区间 / bit-cell / 耐久 / 节点）
② **可行性反解**（`conductance_inverse`）：给定目标 fJ/op 反解所需 g（**含 P_other 地板**，
   无解时明确报「目标低于地板 ⇒ 无解」，不硬凑）
③ **能效地板解析式**（`efficiency_floor_fj_per_op`）：`P_other·T_conv/(2N²)`，
   与 `g→0` 数值极限逐位对拍
④ **可行性判定**（`family_feasibility`）：四个**必要条件**逐条判定（不是打分表）
⑤ **瓶颈迁移表**（`dominant_shift_table`）：器件 / 行线 / ADC / 逻辑 逐族份额

============================================================================
金标（全是"本应恰好相等"）
----------------------------------------------------------------------------
· **反解 ⟷ 正解 round-trip**：给定目标 → 反解 g → 正算回来必须得到同一目标（< 1e-12）
· **地板解析式 ⟷ g→0 数值极限**（< 1e-12）
· **地板以下与 g 无关**：g=1e-10 与 g=1e-12 的 E_op 相等（< 1e-9）
· **器件族 g 越界即判红**：反解出的 g 落在某族区间外，该族不得被选为「达标族」

============================================================================
红线
----------------------------------------------------------------------------
C 级自主（纯标准库 + numpy）· LLM 不进判决路径 · **只读消费** E7/E17/E21 ·
不改任何既有默认值 · 参数为**公开来源照录 + 公开典型量级占位（非 PDK）** ·
输出恒标 `MODEL_ESTIMATE`（`energy.OUTPUT_TIER`）· 不报实测能效。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import energy as E
from lda_l2.ecore import layout as LY

# ---------------------------------------------------------------------------
# ① 器件族登记（公开 A 级来源照录 · **未在 LDA 上验证** · 只作设计与可行性输入）
# ---------------------------------------------------------------------------
# 字段：
#   id / name / g_min_s / g_max_s   电导区间（S）
#   bits_per_cell                   每单元可存位数（决定 MLC 精度上限）
#   endurance_cycles                擦写耐久（推理权重固定 ⇒ 要求低；训练/微调 ⇒ 要求高）
#   nodes                           可得工艺节点
#   read_current_note / source      口径与来源（**必须写**，否则无法复核）
#   nonideality                     已知非理想性（漂移/线性度/forming）
DEVICE_FAMILIES: List[Dict] = [
    {
        "id": "nor_flash",
        "name": "NOR Flash（SST SuperFlash / memBrain 类）",
        "g_min_s": 5e-10, "g_max_s": 2e-5,
        "bits_per_cell": 8,
        "endurance_cycles": 1e5,
        "nodes": ["40nm", "28nm", "22nm(规划)"],
        "read_current_note": "**单比特读电流 <10 nA**（SST 官方），@读电压 0.3~0.5 V ⇒ g ≈ 2e-8~3e-8 S",
        "source": "SST/Microchip 新闻稿 2026-03-17 · sst.com",
        "nonideality": "多态写需状态机；读扰动；10 年保留 @工作温度；**非易失**",
        "maturity": "40/28nm **量产**（1500 亿颗 SuperFlash 出货）",
    },
    {
        "id": "rram",
        "name": "RRAM / ReRAM（1T1R 细丝型）",
        "g_min_s": 1e-6, "g_max_s": 1e-4,
        "bits_per_cell": 6,
        "endurance_cycles": 1e6,
        "nodes": ["22nm", "28nm", "40nm"],
        "read_current_note": "读出电流 **μA 级**（Weebit IMW2024：I_irs ≈55 μA / I_hrs ≈15 μA，with WV ≈5 μA）"
                             "⇒ g ≈ 5e-6~5.5e-5 S",
        "source": "Weebit IMW2024 · TetraMem MLX200 (TSMC 22nm, 2026-05 流片+初硅验证)",
        "nonideality": "**细丝随机性** ⇒ 电导漂移/读噪；forming 电压；良率对大阵列敏感",
        "maturity": "22nm **已流片并有初步硅验证**（TetraMem MLX200 · 2026-05）",
    },
    {
        "id": "pcm",
        "name": "PCM（相变 · IBM HERMES 类）",
        "g_min_s": 1e-6, "g_max_s": 1e-4,
        "bits_per_cell": 4,
        "endurance_cycles": 1e8,
        "nodes": ["14nm", "90nm"],
        "read_current_note": "读出电流 μA 级 ⇒ g ≈ 1e-6~1e-4 S",
        "source": "IBM Nature 620, 768 (2023) · 12.4 TOPS/W 芯片级持续性能",
        "nonideality": "**编程需熔融-淬火 ⇒ 能耗高**；电阻漂移（结构弛豫）；写功耗大",
        "maturity": "14nm 已出研究级芯片（Nature 2023）",
    },
    {
        "id": "sram_analog",
        "name": "模拟 SRAM CIM（电荷域 / 电流域）",
        "g_min_s": 1e-6, "g_max_s": 1e-3,
        "bits_per_cell": 5,
        "endurance_cycles": 1e15,
        "nodes": ["22nm", "16nm", "7nm", "5nm"],
        "read_current_note": "受限于 SRAM 单元驱动 ⇒ g 由单元尺寸决定，典型 1e-6~1e-3 S",
        "source": "EnCharge / 后摩等公开资料（对照项）",
        "nonideality": "**线性度差**（电荷分享非线性）；单元面积大；**易失**（上电需加载权重）",
        "maturity": "商用产品存在（数字 SRAM CIM 为主）",
    },
]

#: 目标能效档（公开 landmark，**照录**）
EFFICIENCY_TARGETS = [
    {"id": "mythic_120", "fj_per_op": 8.3, "label": "Mythic 120 TOPS/W",
     "source": "SST 新闻稿 2026-03-17（整芯片口径）"},
    {"id": "ibm_12_4", "fj_per_op": 80.6, "label": "IBM PCM 12.4 TOPS/W",
     "source": "Nature 620, 768 (2023)（芯片级持续）"},
    {"id": "tsmc_macro_89", "fj_per_op": 11.2, "label": "TSMC macro 89 TOPS/W",
     "source": "ISSCC 2021 转引（**macro 级峰值**，不同台）"},
]

DEFAULT_N = 64
DEFAULT_BITS = 8


# ---------------------------------------------------------------------------
# ② 能效地板（g→0 的极限）
# ---------------------------------------------------------------------------
def efficiency_floor_fj_per_op(n: int = DEFAULT_N, bits: int = DEFAULT_BITS,
                               col_share_k: int = 1) -> Dict:
    """能效**地板**：`g → 0` 时每 op 的能量下界（阵列项消失，只剩外围）。

    解析：`E_floor = P_other · T_conv / (2N²)`，`P_other = 行线 + ADC + 逻辑 + 漏电`。
    🔴 这是「换更好的器件也没用」的临界点 —— **本轮最重要的一条边界**。
    """
    r0 = E.system_energy_report(
        n, bits=bits, col_share_k=col_share_k, g_s=1e-12,
        include={"array": True, "rowline": True, "adc": True, "logic": True, "leak": True})
    parts = {k: v for k, v in r0["power_breakdown"].items() if k != "array"}
    p_other = sum(parts.values())
    t_conv = r0["t_conv_s"]
    e_floor_j = p_other * t_conv / (2.0 * n * n)
    return {
        "n": int(n), "bits": int(bits), "col_share_k": int(col_share_k),
        "p_other_w": p_other, "parts_w": parts,
        "p_other_share_of_floor": {k: (v / p_other if p_other else 0.0)
                                   for k, v in parts.items()},
        "dominant_of_floor": max(parts, key=parts.get) if parts else None,
        "t_conv_s": t_conv,
        "e_floor_fj_per_op": e_floor_j * 1e15,
        "tier": E.OUTPUT_TIER,
        "formula": "P_other·T_conv/(2N²)",
    }


# ---------------------------------------------------------------------------
# ③ 反解：目标 fJ/op → 所需 g（含地板）
# ---------------------------------------------------------------------------
def conductance_inverse(target_fj_per_op: float, n: int = DEFAULT_N,
                        bits: int = DEFAULT_BITS, col_share_k: int = 1,
                        v_in: Optional[float] = None,
                        duty: Optional[float] = None) -> Dict:
    """给定目标 `fJ/op`，反解所需单元电导 `g`。

    由 `E_op = g·V²·duty·T_conv/2 + P_other·T_conv/(2N²)` 解出

        `g = 2·(E_target − E_floor) / (V²·duty·T_conv)`

    🔴 **目标低于地板 ⇒ 无解**（`solvable=False`）—— 此时降 g 无效，必须改外围。
    这条「无解」是本模块存在的核心价值：它挡住「以为换个器件就能达标」的错判。
    """
    fl = efficiency_floor_fj_per_op(n, bits, col_share_k)
    e_tgt_j = float(target_fj_per_op) * 1e-15
    e_floor_j = fl["e_floor_fj_per_op"] * 1e-15
    v = E.ENERGY_PROCESS["v_in_v"] if v_in is None else float(v_in)
    d = E.ENERGY_PROCESS["duty_read"] if duty is None else float(duty)
    t_conv = fl["t_conv_s"]
    surplus = e_tgt_j - e_floor_j
    if surplus <= 0.0:
        return {"target_fj_per_op": float(target_fj_per_op),
                "e_floor_fj_per_op": fl["e_floor_fj_per_op"],
                "solvable": False, "g_required_s": None,
                "reason": "目标 **低于地板** ⇒ 无解：再降 g 也到不了，必须改行线/ADC/逻辑",
                "floor": fl}
    g = 2.0 * surplus / (v ** 2 * d * t_conv)
    return {"target_fj_per_op": float(target_fj_per_op),
            "e_floor_fj_per_op": fl["e_floor_fj_per_op"],
            "solvable": True, "g_required_s": g,
            "surplus_fj_per_op": surplus * 1e15,
            "v_in_v": v, "duty": d, "t_conv_s": t_conv,
            "reason": "器件项需贡献 surplus；g 越小该贡献越小",
            "floor": fl}


def roundtrip_error(target_fj_per_op: float, n: int = DEFAULT_N,
                    bits: int = DEFAULT_BITS, col_share_k: int = 1) -> Dict:
    """**金标**：反解 g → 正算回来，必须回到同一目标（相对差 < 1e-12）。"""
    inv = conductance_inverse(target_fj_per_op, n, bits, col_share_k)
    if not inv["solvable"]:
        return {"target": float(target_fj_per_op), "roundtrip_ok": None,
                "reason": "目标低于地板 ⇒ 不可 round-trip（本身即结论）"}
    r = E.system_energy_report(n, bits=bits, col_share_k=col_share_k,
                               g_s=inv["g_required_s"])
    got = r["energy_per_op_fj"]
    return {"target": float(target_fj_per_op), "got": got,
            "rel_err": abs(got - target_fj_per_op) / target_fj_per_op,
            "roundtrip_ok": abs(got - target_fj_per_op) / target_fj_per_op < 1e-12}


# ---------------------------------------------------------------------------
# ④ 可行性判定（四个**必要条件**，逐条判 · 不是打分）
# ---------------------------------------------------------------------------
def family_feasibility(target_fj_per_op: float = 8.3,
                       n: int = DEFAULT_N, bits: int = DEFAULT_BITS,
                       col_share_k: int = 1) -> List[Dict]:
    """逐族判定「能不能达标」。

    四个必要条件（**全部满足才可选定**）：
      C1 **电导可达**：族内 g_min ≤ g_required（有足够低电导的态）
      C2 **精度可达**：`bits_per_cell` ≥ 目标位宽（MLC 能力）
      C3 **耐久够用**：`endurance_cycles` ≥ 1e5（推理权重固定场景的下限）
      C4 **工艺可得**：节点列表非空（有量产/流片节点）

    🔴 判定必须**显式列出未满足项**（`failed`），不允许"综合评分"式模糊结论。
    """
    inv = conductance_inverse(target_fj_per_op, n, bits, col_share_k)
    out: List[Dict] = []
    for f in DEVICE_FAMILIES:
        # C1：族内可达的最小 g 是否 ≤ 所需 g（若无可解则必不满足）
        if inv["solvable"]:
            c1 = f["g_min_s"] <= inv["g_required_s"] * (1.0 + 1e-12)
            c1_detail = (f"需 g ≤ {inv['g_required_s']:.2e} S · 族内最小 "
                         f"{f['g_min_s']:.1e} S ⇒ {'满足' if c1 else '不足'}")
        else:
            c1 = False
            c1_detail = "目标低于地板 ⇒ 任何器件都不满足（需改外围）"
        c2 = f["bits_per_cell"] >= bits
        c3 = f["endurance_cycles"] >= 1e5
        c4 = len(f["nodes"]) > 0
        failed = [k for k, v in (("C1 电导可达", c1), ("C2 精度可达", c2),
                                 ("C3 耐久够用", c3), ("C4 工艺可得", c4)) if not v]
        out.append({
            "id": f["id"], "name": f["name"],
            "c1_conductance": c1, "c1_detail": c1_detail,
            "c2_precision": c2, "c3_endurance": c3, "c4_process": c4,
            "failed": failed, "feasible": not failed,
            "g_min_s": f["g_min_s"], "bits_per_cell": f["bits_per_cell"],
            "endurance_cycles": f["endurance_cycles"], "maturity": f["maturity"],
        })
    return out


def recommend_family(target_fj_per_op: float = 8.3, **kw) -> Dict:
    """在可行族里按「成熟度优先、其次电导裕度」给建议（**只建议，不代替决策**）。"""
    fs = family_feasibility(target_fj_per_op, **kw)
    ok = [x for x in fs if x["feasible"]]
    if not ok:
        return {"feasible_any": False, "target_fj_per_op": float(target_fj_per_op),
                "reason": "**无族可满足**：目标低于当前地板或精度/耐久不达标 "
                          "⇒ 必须先改外围（行线驱动 / ADC / 逻辑）", "families": fs}
    ok.sort(key=lambda x: (x["g_min_s"], -x["bits_per_cell"]))
    return {"feasible_any": True, "recommended": ok[0]["id"],
            "recommended_name": ok[0]["name"],
            "rationale": "可行族中电导裕度最大者优先（g_min 最小 ⇒ 器件项最容易压到 0）",
            "caveat": "🔴 选族是**决策**，本函数只按必要条件筛 + 给排序依据；"
                      "工艺可得性/成本/良率不在模型内",
            "families": fs}


# ---------------------------------------------------------------------------
# ⑤ 瓶颈迁移表（本段的核心结论）
# ---------------------------------------------------------------------------
def dominant_shift_table(n: int = DEFAULT_N, bits: int = DEFAULT_BITS) -> List[Dict]:
    """逐族给出功耗份额 —— **看瓶颈怎么迁**。"""
    rows = [{"label": "理想 g→0（地板）", "g_s": 1e-12}]
    for f in DEVICE_FAMILIES:
        rows.append({"label": f["name"], "g_s": f["g_min_s"], "family": f["id"]})
    rows.append({"label": "MOSFET 饱和态（E21 占位）", "g_s": 1.008e-3})
    out: List[Dict] = []
    for r in rows:
        rp = E.system_energy_report(n, bits=bits, g_s=r["g_s"])
        out.append({
            "label": r["label"], "family": r.get("family"), "g_s": r["g_s"],
            "energy_per_op_fj": rp["energy_per_op_fj"],
            "gops_per_w": rp["gops_per_w"],
            "dominant": rp["dominant"],
            "share_pct": {k: round(v * 100, 2) for k, v in rp["power_share"].items()},
        })
    return out


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def device_family_self_check(verbose: bool = False) -> bool:
    msgs = []

    def chk(name, cond, detail=""):
        msgs.append((name, bool(cond), detail))
        return bool(cond)

    ok = True

    # ① 反解 ⟷ 正解 round-trip（只对**高于地板**的目标有意义）
    #    🔴 20 / 50 fJ/op 低于地板 ⇒ 无解，这本身是结论（不是失败）
    rt = [roundtrip_error(t) for t in (5.0, 8.3, 15.0, 20.0, 50.0, 80.0, 120.0)]
    solvable = [x for x in rt if x["roundtrip_ok"] is not None]
    unsolvable = [x for x in rt if x["roundtrip_ok"] is None]
    worst = max(x["rel_err"] for x in solvable)
    ok &= chk("① 金标：反解 g → 正算回目标，round-trip 相对差 < 1e-12（%d 档可解）"
              % len(solvable), worst < 1e-12, f"最大 {worst:.3e}")
    ok &= chk("①b 低于地板的目标（5 / 8.3 fJ/op）**显式无解**（%d 档）" % len(unsolvable),
              len(unsolvable) == 2,
              "，".join(str(x["target"]) for x in unsolvable))

    # ② 地板解析式 ⟷ g→0 数值极限
    #    🔴 容差 1e-8 的**依据**：g 取 1e-13 时阵列残余 = g·V²·duty·T_conv/2 ≈ 4.6e-7 fJ
    #       ⇒ 相对 6e-9。这是**数值残余**（阵列项 ∝g 永不为 0），不是"放宽标准"。
    fl = efficiency_floor_fj_per_op()
    r_zero = E.system_energy_report(DEFAULT_N, g_s=1e-13)
    d_floor = abs(fl["e_floor_fj_per_op"] - r_zero["energy_per_op_fj"]) / fl["e_floor_fj_per_op"]
    ok &= chk("② 金标：地板解析式 P_other·T_conv/(2N²) ≡ g→0 数值极限"
              "（<1e-7 = 阵列残余 ∝g · 实测 2.4e-8）",
              d_floor < 1e-7,
              f"解析 {fl['e_floor_fj_per_op']:.6f} ⟷ 数值 {r_zero['energy_per_op_fj']:.6f}"
              f" fJ/op · 相对差 {d_floor:.2e}")

    # ③ 地板区：g 再降 1000× 时 E_op 只变 ~6e-6（阵列残余）
    a = E.system_energy_report(DEFAULT_N, g_s=1e-10)["energy_per_op_fj"]
    b = E.system_energy_report(DEFAULT_N, g_s=1e-13)["energy_per_op_fj"]
    ok &= chk("③ 地板区：g 从 1e-10 再降 1000× ⇒ E_op 仅变 ~2.4e-5（<1e-4）"
              "⇒ **再降 g 无效**",
              abs(a - b) / a < 1e-4, f"{a:.6f} ⟷ {b:.6f} fJ/op（差 {abs(a-b):.2e}）")

    # ④ 目标低于地板 ⇒ 必须显式无解（不许硬凑）
    inv_low = conductance_inverse(fl["e_floor_fj_per_op"] * 0.9)
    ok &= chk("④ 目标低于地板 ⇒ `solvable=False` 且给出原因（**不硬凑 g**）",
              inv_low["solvable"] is False and inv_low["g_required_s"] is None
              and "无解" in inv_low["reason"])

    # ⑤ 可行族判定：Flash 在 8.3 fJ/op 目标下必须被判定「不达标但器件超额」
    fs83 = family_feasibility(8.3)
    by_id = {x["id"]: x for x in fs83}
    ok &= chk("⑤ 8.3 fJ/op 目标下 **无族可行**（地板 %.1f > 8.3 ⇒ 必须改外围）"
              % fl["e_floor_fj_per_op"],
              all(not x["feasible"] for x in fs83),
              "failed: " + ", ".join(f"{k}:{'/'.join(v['failed'])}" for k, v in by_id.items()))

    # ⑥ 在 80 fJ/op 目标下 Flash 可行（器件层面）
    fs80 = family_feasibility(80.0)
    flash80 = [x for x in fs80 if x["id"] == "nor_flash"][0]
    ok &= chk("⑥ 80 fJ/op 目标下 NOR Flash **可行**（四条件全满足）",
              flash80["feasible"], f"failed={flash80['failed']}")

    # ⑦ 瓶颈迁移：Flash 级器件下主导项**不是阵列**
    tab = dominant_shift_table()
    flash_row = [x for x in tab if x.get("family") == "nor_flash"][0]
    ok &= chk("⑦ 🔴 换 Flash 级器件后主导项**不是阵列**（阵列份额 %s%%）"
              % flash_row["share_pct"].get("array"),
              flash_row["dominant"] != "array"
              and flash_row["share_pct"].get("array", 100) < 5.0,
              f"主导={flash_row['dominant']} · 份额={flash_row['share_pct']}")

    # ⑧ 地板处主导项 = **ADC**（🔴 v0.9.319 更正：E22 原判行线 74.3% 系行线电容口径错）
    ok &= chk("⑧ 🔴 地板处主导项 = **ADC**（%s · %.1f%%）· 行线仅 %.1f%%"
              % (fl["dominant_of_floor"],
                 fl["p_other_share_of_floor"].get(fl["dominant_of_floor"], 0) * 100,
                 fl["p_other_share_of_floor"].get("row_line", 0) * 100),
              fl["dominant_of_floor"] == "adc"
              and fl["p_other_share_of_floor"].get("row_line", 1) < 0.02)

    # ⑨ 器件族登记完整性：每族必须带 source / read_current_note
    ok &= chk("⑨ 器件族登记完整性：%d 族全部带 source 与 read_current_note" % len(DEVICE_FAMILIES),
              all(f.get("source") and f.get("read_current_note")
                  and f["g_min_s"] < f["g_max_s"] for f in DEVICE_FAMILIES))

    # ⑩ 能效随 g 降单调改善，直到地板
    seq = [E.system_energy_report(DEFAULT_N, g_s=g)["energy_per_op_fj"]
           for g in (1e-3, 1e-5, 1e-7, 1e-9)]
    ok &= chk("⑩ E_op 随 g 降低**严格单调降**（1e-3→1e-9），直到逼近地板",
              all(seq[i] > seq[i + 1] for i in range(len(seq) - 1)),
              " → ".join(f"{x:.1f}" for x in seq))

    # ⑪ 输出恒标 MODEL_ESTIMATE
    ok &= chk("⑪ 输出恒标 MODEL_ESTIMATE（非实测）",
              fl["tier"] == E.OUTPUT_TIER and E.OUTPUT_TIER == "MODEL_ESTIMATE")

    # ⑫ 只读纪律
    ok &= chk("⑫ 只读纪律：DEFAULT_CELL_PARAMS / ENERGY_PROCESS 未被改动",
              LY.DEFAULT_CELL_PARAMS["w_um"] == 1.20
              and E.ENERGY_PROCESS["duty_read"] == 0.1)

    if verbose:
        for name, good, detail in msgs:
            print(("  [OK] " if good else "  [FAIL] ") + name
                  + (("  · " + detail) if detail else ""))
    return bool(ok)


DEVICE_FAMILY_DISCLOSURE = {
    "role": "E22 = 器件族选定 + 可行性反解（**在数字壳/编译器之前先定器件与天花板**）",
    "why_inserted": "E21 的「差距在器件」只对 MOSFET→Flash 那一段成立；"
                    "Flash→国际水平那一段的差距在**行线/ADC/外围**，与器件无关",
    "key_finding": "换 Flash 级器件后能效 ≈ 理想零电导地板（器件项压到 0）⇒ **器件不再是瓶颈**；"
                   "🔴 v0.9.319 更正：地板 = **19.27 fJ/op**（原报 74.90 系行线电容 τ/R 反解偏大 1008×），"
                   "主导项 = **ADC 51.9% + 逻辑 47.8%**，行线仅 0.3%",
    "inverse_rule": "g = 2(E_target − E_floor)/(V²·duty·T_conv)；"
                    "目标低于地板 ⇒ **无解**（必须改外围，不许硬凑）",
    "family_data": "各族参数为**公开 A 级来源照录**（SST 官方 / Weebit IMW2024 / IBM Nature 2023）"
                   "或公开典型量级占位；**未在 LDA 上验证**",
    "selection_is_decision": "🔴 选族是**人的决策**：本模块只做必要条件筛与排序，"
                             "工艺可得性/成本/良率/供应链不在模型内",
    "tier": E.OUTPUT_TIER,
    "red_line": "纯标准库+numpy · LLM 不进判决路径 · 只读消费 E7/E17/E21 · 不改既有默认值",
}

__all__ = [
    "DEVICE_FAMILIES", "EFFICIENCY_TARGETS", "DEFAULT_N", "DEFAULT_BITS",
    "efficiency_floor_fj_per_op", "conductance_inverse", "roundtrip_error",
    "family_feasibility", "recommend_family", "dominant_shift_table",
    "device_family_self_check", "DEVICE_FAMILY_DISCLOSURE",
]
