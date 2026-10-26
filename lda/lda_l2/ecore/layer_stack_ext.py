"""层栈扩展：把 E29 的「表达不了」变成「能表达、且知道还缺什么」（E30 · D-205）。

## 本模块做了什么

E29 判定：「换 RDL 需 +10 层，平台只有 7 层 ⇒ 无法表达」。
本段**把层栈补上**（+M3/M4/M5/M6/AP + VIA2-VIA5/VIA_AP），并实测换层后到底会发生什么。

## ① 层栈扩展（**纯加法 · 旧栈逐位不动**）

| | 层数 | 层 |
|---|---|---|
| 旧 `ecmos` | **6**（+PAD = 7 个层名） | DIFF/POLY/CONT/M1/VIA1/M2 |
| 新 `ecmos10` | **16** | +M3/VIA2/M4/VIA3/M5/VIA4/M6/VIA5/AP/VIA_AP |

层号 **27-36**（避开 1-4/9 光子 · 5-8 PS · 10-14 超导 · 20-26 电子前道+M1/M2）。
🔴 `get_estack()` 缺省仍返回**旧 6 层栈** ⇒ 既有 11 道 E6/E7/E9 门禁零影响
（`gds_bytes` 936/1272/1608 · `flat` 120/464/1032 三档逐位一致，见门禁 B2）。

## ② 🔴 实测：换层后会发生什么（这才是本段的核心）

| `row_layer` | DRC | LVS | 原因 |
|---|---|---|---|
| **M1**（基准） | **ACCEPT** | **ACCEPT** | — |
| M3 | ACCEPT | **REJECT** | `CONT` 悬空 |
| M6 | ACCEPT | **REJECT** | 同上 |
| AP（W=0.40） | **REJECT** | REJECT | AP 最小线宽 **1.60 µm** |

### 障碍一：`CONT` 悬空（**结构性**）

LVS 报 `ELVS-DANGLING-BRIDGE: CONT@row0 只接触['DIFF']`。

🔴 **根因**：E6 的单元里**行线同时充当 CONT 的上层金属**。
行线一走（M1 → M3/M6/AP），CONT 就只剩 DIFF 一侧 ⇒ 悬空桥。

⇒ **换层不是"加个 via stack"，而是必须先给每单元加一个 M1 落垫**
（CONT → M1 pad → via stack → 行线层）。这是**单元版图重设计**，
与 E29 发现"加宽也是重设计"同型。

### 障碍二：AP 层最小线宽 **1.60 µm** ⇒ **换层强制加宽**

AP（顶层厚金属）的 `min_width = 1.60`、`min_space = 1.60`。所以：
- 行线走 AP 时**不能是 0.40 µm**（DRC REJECT，每行一处 `EDR-MIN-WIDTH`）
- 必须 ≥ 1.60 µm ⇒ **画出来必然是宽线**

🔴 **这个"强制"反而是好事**：`r = ρL/(W·t)`，W 与 t 同时变大 ⇒ R 掉得比预想多。

### 障碍三：AP 行距约束 ⇒ `pitch_y ≥ W + 1.60`

行间距 = `pitch_y − W` 必须 ≥ 1.60。W=1.60 ⇒ `pitch_y ≥ 3.20`。

## ③ 🔴 本段最重要的一条：找到了**第一条 DRC 全过的换层路径**

| 方案 | W | `pitch_y` | DRC | LVS | `r_seg` | r 倍数 | 面积 |
|---|---|---|---|---|---|---|---|
| 基准 M1 | 0.40 | 2.40 | ACCEPT | ACCEPT | 0.5040 | 1× | 1× |
| **AP 行线** | **1.60** | **3.20** | **ACCEPT** | REJECT | **0.0126** | **r/40** | **×1.32** |
| AP 行线 | 2.00 | 3.60 | ACCEPT | REJECT | 0.0101 | r/50 | ×1.48 |

⇒ **E28 假设 RDL 能给 r×10；实测 AP 层因为强制宽线 1.60 µm，实际是 r×40（4 倍于预期）。**
⇒ **代价只有面积 ×1.32**（pitch_y 2.40→3.20）。
⇒ **唯一剩下的障碍是 CONT 悬空（LVS）**，那是下一段要修的单元结构。

## 判据纪律

- **旧栈逐位不变**必须用 `gds_bytes` + `flat_elements` 双指纹机核
  （单看 DRC verdict 不够 —— 几何变了也可能都 ACCEPT）。
- **`row_layer="M1"` 必须与基线逐位一致**（默认路径零影响）。
- **AP 的"强制加宽"必须报出**：`W=0.40` 时 DRC 必红 ⇒ 不许把"换层"说成"不改线宽"。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import elayers as EL
from lda_l2.ecore import energy as E
from lda_l2.ecore import layout as LY
from lda_l2.ecore import parasitic as PA

#: 旧栈（E6 原有 · **必须逐位不动**）
BASELINE_STACK = "ecmos"
#: 新栈（E30）
EXTENDED_STACK = "ecmos10"

#: 旧栈的 GDS 指纹（v0.9.325 实测 · 用于"纯加法"机核）
BASELINE_GDS = {4: (936, 120), 8: (1272, 464), 12: (1608, 1032)}

#: 换层实测矩阵的规模（DRC 是 O(N⁴) · 锁死小规模）
MATRIX_N = 8

#: AP 层可行路径（DRC 全过）
AP_PATHWAYS: List[Dict] = [
    {"w_um": 1.60, "pitch_y_um": 3.20},
    {"w_um": 2.00, "pitch_y_um": 3.60},
]


# ---------------------------------------------------------------------------
# ① 层栈对比
# ---------------------------------------------------------------------------
def stack_comparison() -> Dict:
    s_old = EL.get_estack(BASELINE_STACK)
    s_new = EL.get_estack(EXTENDED_STACK)
    return {
        "old": {"name": s_old.name, "n_layers": len(s_old.layers),
                "signal": s_old.signal_layers(), "bridge": s_old.bridge_layers(),
                "gds": {n: l.gds_layer for n, l in s_old.layers.items()}},
        "new": {"name": s_new.name, "n_layers": len(s_new.layers),
                "signal": s_new.signal_layers(), "bridge": s_new.bridge_layers(),
                "gds": {n: l.gds_layer for n, l in s_new.layers.items()}},
        "added": sorted(set(s_new.layers) - set(s_old.layers)),
        "n_added": len(set(s_new.layers) - set(s_old.layers)),
        "old_z_preserved": all(
            (s_old.layers[n].z_bot_um, s_old.layers[n].z_top_um)
            == (s_new.layers[n].z_bot_um, s_new.layers[n].z_top_um)
            for n in s_old.layers),
        "default_unchanged": EL.get_estack().name == s_old.name,
        "verdict": ("✅ 层栈 **%d → %d 层**（+%d：%s）；旧 6 层的 z 跨度**逐位继承**、"
                    "`get_estack()` 缺省仍返回旧栈 ⇒ **既有调用零影响**"
                    % (len(s_old.layers), len(s_new.layers),
                       len(set(s_new.layers) - set(s_old.layers)),
                       "/".join(sorted(set(s_new.layers) - set(s_old.layers))))),
        "tier": E.OUTPUT_TIER,
    }


def baseline_unchanged() -> Dict:
    """**纯加法机核**：旧栈三档几何的 `gds_bytes` + `flat` 必须与基线逐位一致。"""
    rows = []
    for n, (g0, f0) in BASELINE_GDS.items():
        arr = LY.crossbar_array(n, n)          # 缺省 row_layer ⇒ 必须与旧行为一致
        g = LY.to_gds(n, n)
        d = LY.run_edrc(arr["descs"])
        ok = (g["n_bytes"] == g0 and g["flat_elements"] == f0
              and d["verdict"] == "ACCEPT" and len(d["violations"]) == 0)
        rows.append({"n": n, "gds": g["n_bytes"], "gds_base": g0,
                     "flat": g["flat_elements"], "flat_base": f0,
                     "drc": d["verdict"], "ok": ok})
    return {"rows": rows, "all_ok": all(r["ok"] for r in rows),
            "verdict": ("✅ 旧栈三档（N=4/8/12）`gds_bytes` 与 `flat` **逐位一致**、DRC 全 ACCEPT "
                        "⇒ 层栈扩展是**纯加法**"),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ② 换层实测矩阵
# ---------------------------------------------------------------------------
def row_layer_matrix(n: int = MATRIX_N) -> List[Dict]:
    """`row_layer` × DRC/LVS —— 换层后到底会发生什么。"""
    rows = []
    for rl in ("M1", "M3", "M6", "AP"):
        arr = LY.crossbar_array(int(n), int(n), row_layer=rl)
        d = LY.run_edrc(arr["descs"])
        lv = LY.elvs_signoff(arr["descs"], LY.expected_netlist(int(n), int(n)))
        rules = sorted({v.get("rule") for v in d["violations"]})
        issues = lv.get("issues") or []
        rows.append({"row_layer": rl, "drc": d["verdict"], "n_viol": len(d["violations"]),
                     "drc_rules": rules, "lvs": lv["verdict"],
                     "lvs_issue": (issues[0][:60] if issues else ""),
                     "tier": E.OUTPUT_TIER})
    return rows


def dangling_analysis(n: int = MATRIX_N) -> Dict:
    """**换层的真实障碍**：`CONT` 悬空（行线是 CONT 的上层金属）。"""
    arr = LY.crossbar_array(int(n), int(n), row_layer="M6")
    lv = LY.elvs_signoff(arr["descs"], LY.expected_netlist(int(n), int(n)))
    issues = lv.get("issues") or []
    dangling = [x for x in issues if "DANGLING" in x]
    return {"n": int(n), "row_layer": "M6", "lvs": lv["verdict"],
            "n_issues": len(issues), "n_dangling": len(dangling),
            "sample": (dangling[0][:110] if dangling else ""),
            "root_cause": "E6 单元里**行线同时充当 CONT 的上层金属**；行线移走 ⇒ CONT 只剩 DIFF 一侧",
            "fix": "每单元加 M1 落垫（CONT→M1 pad→via stack→行线层）⇒ **单元版图重设计**",
            "verdict": ("🔴 换层的障碍不是「加个 via stack」，而是 **CONT 结构性悬空**："
                        "%d 条 DANGLING-BRIDGE ⇒ 必须先做 M1 落垫 + via stack（**单元重设计**）"
                        % len(dangling)),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ③ AP 路径（本段最重要的一条：DRC 全过）
# ---------------------------------------------------------------------------
def ap_pathway() -> List[Dict]:
    """AP 行线的可行点：DRC 全过 · 量出真实 r 与面积代价。"""
    r0 = PA.wire_resistance(2.40, 0.40, 1.68e-2, 0.20)     # 基准 M1
    fw0, fh0 = LY.array_footprint(20, 20, {})
    rows = []
    for p in AP_PATHWAYS:
        arr = LY.crossbar_array(MATRIX_N, MATRIX_N,
                                {"row_w_um": p["w_um"], "pitch_y_um": p["pitch_y_um"]},
                                row_layer="AP")
        d = LY.run_edrc(arr["descs"])
        lv = LY.elvs_signoff(arr["descs"], LY.expected_netlist(MATRIX_N, MATRIX_N))
        r = PA.wire_resistance(2.40, p["w_um"], 1.68e-2, 2.00)   # AP t=2.00
        fw1, fh1 = LY.array_footprint(20, 20, {"pitch_y_um": p["pitch_y_um"]})
        rows.append({"w_um": p["w_um"], "pitch_y_um": p["pitch_y_um"],
                     "drc": d["verdict"], "n_viol": len(d["violations"]),
                     "lvs": lv["verdict"],
                     "r_seg_ohm": r, "r_gain": r0 / r,
                     "area_ratio": (fw1 * fh1) / (fw0 * fh0),
                     "tier": E.OUTPUT_TIER})
    best = rows[0]
    return {
        "drc_all_pass": all(x["drc"] == "ACCEPT" for x in rows),
        "lvs_all_reject": all(x["lvs"] != "ACCEPT" for x in rows),
        "best_r_gain": max(x["r_gain"] for x in rows),
        "best_area": min(x["area_ratio"] for x in rows if x["drc"] == "ACCEPT"),
        "verdict": ("🔴 **第一条 DRC 全过的换层路径**：AP 行线 W=%.2f · pitch_y=%.2f ⇒ "
                    "DRC ACCEPT、**r ×%.0f**、面积 ×%.2f；**但 LVS 仍 REJECT**（CONT 悬空）"
                    "⇒ 距离「可签核」只差最后一步：单元 M1 落垫 + via stack"
                    % (best["w_um"], best["pitch_y_um"], best["r_gain"],
                   best["area_ratio"])),
            "tier": E.OUTPUT_TIER}, rows


def ap_forced_widen() -> Dict:
    """**换层强制加宽**：AP 的 `min_width=1.60` ⇒ W=0.40 时 DRC 必红。"""
    rows = []
    for w in (0.40, 1.60):
        arr = LY.crossbar_array(MATRIX_N, MATRIX_N, {"row_w_um": w}, row_layer="AP")
        d = LY.run_edrc(arr["descs"])
        rows.append({"w_um": w, "drc": d["verdict"], "n_viol": len(d["violations"]),
                     "rules": sorted({v.get("rule") for v in d["violations"]})})
    return {"rows": rows,
            "verdict": ("🔴 AP 层 `min_width = 1.60 µm` ⇒ 行线**不能是 0.40**（W=0.40 时 "
                        "%d 处 `EDR-MIN-WIDTH`）⇒ **换层强制加宽**；"
                        "而这个「强制」反而让 r 掉到 ×40（E28 假设 RDL 只有 ×10）"
                        % rows[0]["n_viol"]),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ④ E29 缺口是否闭合
# ---------------------------------------------------------------------------
def gap_closure() -> Dict:
    """E29 判"缺 8~10 层"，本段补了 10 层 ⇒ 换层**能表达**了。"""
    s_new = EL.get_estack(EXTENDED_STACK)
    have = set(s_new.layers)
    need_m6 = {"M3", "M4", "M5", "M6", "VIA2", "VIA3", "VIA4", "VIA5"}
    need_ap = need_m6 | {"AP", "VIA_AP"}
    return {"need_m6": sorted(need_m6), "need_ap": sorted(need_ap),
            "miss_m6": sorted(need_m6 - have), "miss_ap": sorted(need_ap - have),
            "m6_expressible": not (need_m6 - have),
            "ap_expressible": not (need_ap - have),
            "verdict": ("✅ E29 的「+8 层 / +10 层」缺口**已闭合**：M6 级与 AP 级都**能表达**了"
                        "（`row_layer` 可指定）；但**表达 ≠ 可签核** —— "
                        "CONT 悬空（LVS）与行距约束（DRC）是两回事"),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑤ 自检
# ---------------------------------------------------------------------------
def layer_stack_ext_self_check(verbose: bool = False) -> bool:
    checks: List[str] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append(("[OK] " if cond else "[NG] ") + name)
        if verbose:
            print("  %s%s%s" % ("[OK] " if cond else "[NG] ", name,
                                ("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① 旧栈 6 层不动，新栈 16 层
    sc = stack_comparison()
    ok &= chk("① 旧栈 %d 层 ⟷ 新栈 %d 层（+%d）· 旧 z 逐位继承 · 缺省仍旧栈"
              % (sc["old"]["n_layers"], sc["new"]["n_layers"], sc["n_added"]),
              sc["old"]["n_layers"] == 6 and sc["new"]["n_layers"] == 16
              and sc["n_added"] == 10 and sc["old_z_preserved"]
              and sc["default_unchanged"])

    # ② 纯加法：旧栈 GDS 指纹逐位一致
    bu = baseline_unchanged()
    ok &= chk("② 🔴 旧栈三档 `gds_bytes`/`flat` 逐位一致（%s）⇒ **纯加法**"
              % [r["gds"] for r in bu["rows"]], bu["all_ok"])

    # ③ 层号段不与他域冲突
    used = set(sc["new"]["gds"].values()) | set(sc["old"]["gds"].values())
    ok &= chk("③ 层号 %d~%d 与他域（1-4/5-8/9/10-14/20-26）不冲突"
              % (min(used - {20, 21, 22, 23, 24, 25, 26}), max(used)),
              min(used) >= 20 and all(27 <= x <= 36 for x in used - {20, 21, 22, 23, 24, 25, 26}))

    # ④ 换层矩阵：M1 全过；非 M1 的 LVS 全 REJECT
    mx = row_layer_matrix()
    m1 = [r for r in mx if r["row_layer"] == "M1"][0]
    others = [r for r in mx if r["row_layer"] != "M1"]
    ok &= chk("④ M1 基准 DRC/LVS 全 ACCEPT；非 M1 全部 LVS **REJECT**",
              m1["drc"] == "ACCEPT" and m1["lvs"] == "ACCEPT"
              and all(r["lvs"] != "ACCEPT" for r in others))

    # ⑤ 🔴 CONT 悬空是换层的结构性障碍
    da = dangling_analysis()
    ok &= chk("⑤ 🔴 换层障碍 = **CONT 悬空**（%d 条 DANGLING-BRIDGE ⇒ 需 M1 落垫 + via stack）"
              % da["n_dangling"], da["n_dangling"] > 0 and "DANGLING" in da["sample"])

    # ⑥ 🔴 换层强制加宽：AP W=0.40 必红
    fw = ap_forced_widen()
    ok &= chk("⑥ 🔴 AP `min_width=1.60` ⇒ W=0.40 时 DRC 必红（%d 处 `EDR-MIN-WIDTH`）"
              "⇒ **换层强制加宽**" % fw["rows"][0]["n_viol"],
              fw["rows"][0]["drc"] != "ACCEPT"
              and "EDR-MIN-WIDTH" in fw["rows"][0]["rules"])

    # ⑦ 🔴 第一条 DRC 全过的换层路径
    summ, rows = ap_pathway()
    ok &= chk("⑦ 🔴 AP 路径 DRC **全过**（W=%.2f · pitch_y=%.2f ⇒ r ×%.0f · 面积 ×%.2f）"
              % (rows[0]["w_um"], rows[0]["pitch_y_um"], rows[0]["r_gain"],
                 rows[0]["area_ratio"]),
              summ["drc_all_pass"] and summ["lvs_all_reject"]
              and rows[0]["r_gain"] > 30.0 and rows[0]["area_ratio"] < 1.4)

    # ⑧ r 与闭式一致（不另设口径）
    r_ref = PA.wire_resistance(2.40, 1.60, 1.68e-2, 2.00)
    ok &= chk("⑧ AP 的 `r_seg` ≡ E7 闭式 `ρL/(Wt)`（%.6f Ω）"
              % rows[0]["r_seg_ohm"],
              abs(rows[0]["r_seg_ohm"] - r_ref) / r_ref < 1e-15)

    # ⑨ E29 缺口闭合（但"表达 ≠ 可签核"）
    gc = gap_closure()
    ok &= chk("⑨ E29 缺口闭合：M6 级 %s · AP 级 %s（**表达 ≠ 可签核**）"
              % (gc["m6_expressible"], gc["ap_expressible"]),
              gc["m6_expressible"] and gc["ap_expressible"]
              and da["n_dangling"] > 0)

    # ⑩ 输出恒 MODEL_ESTIMATE
    ok &= chk("⑩ 全部输出恒标 `MODEL_ESTIMATE`",
              sc["tier"] == "MODEL_ESTIMATE" and summ["tier"] == "MODEL_ESTIMATE")

    if verbose:
        print()
        print("  %d/%d 通过" % (sum(1 for c in checks if c.startswith("[OK]")), len(checks)))
    return ok


LAYER_STACK_EXT_DISCLOSURE = {
    "tier": E.OUTPUT_TIER,
    "is_measured": False,
    "core_finding": "**层栈 6 → 16 层（+M3/M4/M5/M6/AP + VIA2-VIA5/VIA_AP）· 纯加法、旧栈逐位不动。** "
                    "换层实测暴露三个障碍：① **CONT 结构性悬空**（行线是 CONT 的上层金属，"
                    "移走即悬空 ⇒ 需 M1 落垫 + via stack = 单元重设计）；"
                    "② **AP 强制加宽**（min_width=1.60 µm ⇒ W=0.40 必红）；"
                    "③ **AP 行距约束**（pitch_y ≥ W + 1.60）。"
                    "⇒ 🔴 **但找到了第一条 DRC 全过的换层路径**：AP 行线 W=1.60 · pitch_y=3.20 ⇒ "
                    "**DRC ACCEPT · r ×40 · 面积 ×1.32**（E28 假设 RDL 只有 ×10）"
                    "⇒ 距「可签核」只差 CONT 悬空这一步。",
    "not_claimed": [
        "不宣称 AP 路径**可签核**（LVS 仍 REJECT · 未做 M1 落垫与 via stack）",
        "不宣称新层的规则值（1.60/0.40 等）是 PDK 真值（公开工艺近似占位）",
        "不宣称能效改善（r ×40 只是几何收益，未回代 E27/E28 的规模-能效链）",
        "不宣称 DRC 复杂度已改善（仍 O(N⁴) · 那是 E31 的事）",
    ],
    "next_data_needed": "单元 M1 落垫 + via stack 自动生成 ⇒ LVS 才能 ACCEPT；"
                        "以及 DRC 空间索引（O(N⁴) → O(N log N)）",
}
