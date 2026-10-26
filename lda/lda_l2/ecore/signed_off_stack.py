"""E31（D-206）· 换层签核：漏极 via stack + DRC/LVS 两个静默漏检的修复。

## 这一段要解决什么

E29 判定「换 RDL 需 +10 层 ⇒ 无法表达」，E30 把层栈补到 16 层并找到「AP 路径 DRC 全过」。
但 E30 的 AP 路径 **LVS 仍 REJECT**，而且 —— 本段发现 —— **那个「DRC 全过」本身是假绿**。

## 本段的三个发现（全部实测，非推测）

### ① via 的 z 位置整体错位一层（E30 建栈缺陷）

E30 把 `VIA_n` 放在 `M_n` 与 `M_{n+1}` 之间，而它应该夹在**自己所连的两层**之间。
后果：`pos_of(VIA_AP) = 15 > pos_of(AP) = 14` ⇒ LVS 的「桥须跨下层+上层」判定里
VIA_AP **没有上层** ⇒ **结构性悬空，无论几何怎么画都不通过**。

⇒ 本段修正 5 个 via 的 z 跨度（M1/VIA1/M2 三段 **逐位保持**，旧栈继承不变）。

### ② DRC 与 LVS 各有一次静默漏检（同一病根：层栈取的是旧栈）

| 检查 | 旧实现的后果 | 实测证据 |
|---|---|---|
| `run_edrc` 的 enclosure | `bridge_layers()` 只有 CONT/VIA1 ⇒ **VIA2+ 的 enclosure 完全不查** | M3 落垫缩到 0.22（enclosure 0.01 ≪ 0.10）⇒ 旧栈仍报 **ACCEPT 0 违规** |
| `elvs_signoff` 的桥判定 | 同上 ⇒ VIA2+ 不参与连通性 | 换层几何在旧栈下 **16 条 issues 全是 CONT**，VIA2+ 一个都没提 |

⇒ 两个函数都加 `stack` 参数（缺省旧栈 ⇒ 既有调用零影响），
并要求多层几何**必须显式传 16 层栈**。

修完之后，E30 的「AP 路径 DRC 全过」**当场变 REJECT**：
`VIA_AP 被 M6 包围 0.000 < 0.200` —— 因为 M6 落垫只做了 0.40，而 VIA_AP 是 0.40 且需 0.20 enclosure。

### ③ 落垫尺寸必须按**上方 via** 的 enclosure 反算，不能一律取 `pad_um`

`side ≥ via_size + 2·enclosure`：

| via | size | enclosure | 落垫最小 |
|---|---|---|---|
| VIA1-VIA5 | 0.20 | 0.10 | 0.40（= `pad_um`，巧合对上） |
| **VIA_AP** | **0.40** | **0.20** | **0.80** |

⇒ M6 落垫必须 0.80。这是「**约束反而帮忙**」的第三个实例（前两个：E29 的加宽被拒、
E30 的 AP 强制 1.60 宽线）。

## 签核结果（本段交付的核心表）

7 个目标层，`via_stack=True` + 16 层栈：

| 行线层 | 栈长 | DRC | LVS | 结论 |
|---|---|---|---|---|
| M1 | 0 | ACCEPT | ACCEPT | 基准（无需栈） |
| **M2** | 2 | **REJECT** | **REJECT** | 🔴 **物理不可行**：M2 是列线层，同层相交 = 真短路 |
| M3 | 4 | ACCEPT | ACCEPT | ✅ |
| M4 | 6 | ACCEPT | ACCEPT | ✅ |
| M5 | 8 | ACCEPT | ACCEPT | ✅ |
| M6 | 10 | ACCEPT | ACCEPT | ✅ |
| **AP** | **12** | ACCEPT | ACCEPT | ✅ **推荐** |

## 规模与能效（各层取**合法最小线宽**）

| 层 | t (µm) | 合法 W | `r_seg` | r 倍数 | `pitch_y` | N 上界 | ADC 项 | vs Mythic 8.3 |
|---|---|---|---|---|---|---|---|---|
| M1 | 0.20 | 0.40 | 0.50400 | 1.0 | 2.40 | 12 | 179.2 fJ/op | 21.6× |
| M3 | 0.30 | 0.40 | 0.33600 | 1.5 | 2.40 | 15 | 143.4 | 17.3× |
| M4 | 0.60 | 0.40 | 0.16800 | 3.0 | 2.40 | 22 | 97.7 | 11.8× |
| M5 | 0.70 | 0.40 | 0.14400 | 3.5 | 2.40 | 24 | 89.6 | 10.8× |
| M6 | 1.00 | 0.40 | 0.10080 | 5.0 | 2.40 | 29 | 74.2 | 8.9× |
| **AP** | **2.00** | **1.60** | **0.01260** | **40.0** | **3.20** | **87** | **24.7** | **3.0×** |

🔴 **两点必须同屏说**：
1. **M3-M6 换层不增加面积**（`pitch_y` 保持 2.40，只有金属厚度变）；
   **只有 AP 增加 33%**（`pitch_y` 2.40→3.20，被 `ap_min_space=1.60` 逼的）。
2. AP 的 r 掉 40 倍而不是 5 倍，**不是因为用了更厚的金属，而是因为被强制加宽到 1.60**
   （`R ∝ 1/(W·t)`：t×10 且 W×4 ⇒ R÷40）。

## 版图代价（必须与收益同屏）

| 项 | 值 |
|---|---|
| 每单元 via stack 面积 | 0.40×0.40 = 0.16 µm² |
| 占单元面积 | 2.08%（AP · 单元 7.68 µm²）/ 2.78%（M3-M6 · 单元 5.76 µm²） |
| N=12 的 via 总数 | 144 × 12 = **1,728** |
| **N=87 的串联 via 节点** | 7,569 × **6** = **45,414**（链长 12 含 6 个金属落垫） |
| 阵列面积（N=87 · `pitch_y` 3.20） | 207.6 × 276.9 µm = **0.0575 mm²** |

🔴 **45,414 个串联 via 节点的良率未建模** —— 每个 1 ppm 即整体 ~4.5% 失效。
（v0.9.329 修正：原写 90,828 / 8.7% 是把链长 12 当成 via 数，高估 2×。）
这是本段**最大的未建模风险**，不能因为 DRC/LVS 过了就当它不存在。

## 诚实边界

- 层厚 / 规则值全部是**公开工艺近似占位（非 PDK）**；
- DRC/LVS 通过只说明**几何自洽**，不是可制造性（无 CMP/OPC/天线规则/密度规则）；
- `N=87` 是 **5% 全链误差预算下的一维规模律上界**，未做电路仿真验证；
- 签核矩阵规模锁 **N=4**（`run_edrc` 是 O(N⁴)：N=24 已需 17 s，N=87 不可跑 —— 那是 E32 的事）；
- 输出恒 `MODEL_ESTIMATE`；**净增 0 锚**（版图签核不是实测语料）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import layout as LY
from lda_l2.ecore import elayers as EL
from lda_l2.ecore import parasitic as PA
from lda_l2.ecore import budget as BG
from lda_l2.ecore import adc_calibration as AC
from lda_l2.ecore import energy as E

#: 签核矩阵用的规模（`run_edrc` 是 O(N⁴)，锁 N=4 才能做到 0.02 s/层）
MATRIX_N = 4

#: 各层「合法最小线宽」的取值口径：`max(0.40, min_width)`。
#   🔴 用 `max` 而不是直接用 `min_width`：M1-M6 的 min_width 都 ≤0.40，
#   而 0.40 是基准线宽（与 E28/E29/E30 的 `row_w_um` 一致）；AP 的 1.60 才真的逼人加宽。
BASE_WIDTH_UM = 0.40

#: 目标层 → 该层的金属厚度（µm）· 与 E28 `row_metal.METAL_LAYERS` 同源口径
LAYER_THICKNESS_UM: Dict[str, float] = {
    "M1": 0.20, "M3": 0.30, "M4": 0.60, "M5": 0.70, "M6": 1.00, "AP": 2.00,
}

#: 目标层 → 末端 via 名（决定端帽与落垫尺寸）
END_VIA_OF: Dict[str, str] = {
    "M2": "VIA1", "M3": "VIA2", "M4": "VIA3", "M5": "VIA4",
    "M6": "VIA5", "AP": "VIA_AP",
}


#: 模块级缓存（DRC/LVS 是 O(N⁴)，自检里 signoff_matrix 会被多次调用）
_CACHE: Dict[str, object] = {}


def _cached(key: str, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def _lim() -> Dict[str, float]:
    return EL.ELEC_DESIGN_RULES


def _stack10():
    return EL.get_estack("ecmos10")


# ---------------------------------------------------------------------------
# ① 层序审计：本段第一件事（z 错位让 VIA_AP 永远悬空）
# ---------------------------------------------------------------------------
def z_order_audit() -> Dict:
    """每个 via 是否**严格夹在其声称连接的两层之间**（用 `pos_of` 判）。

    🔴 这是 E30 缺失的判据。E30 的栈里 `pos_of(VIA_AP)=15 > pos_of(AP)=14`
    ⇒ VIA_AP 被判「无上层」⇒ **无论几何怎么画都悬空**。
    """
    st = _stack10()
    order = [n for n in sorted(st.layers, key=lambda k: st.pos_of(k))]
    rows: List[Dict] = []
    for name, pairs in st.via_map.items():
        claim = pairs[0]
        i = order.index(name)
        below = order[i - 1] if i > 0 else None
        above = order[i + 1] if i + 1 < len(order) else None
        rows.append({
            "via": name, "claims": claim, "below": below, "above": above,
            # 🔴 CONT 是**旧栈继承**的布局：下方在 pos 上是 POLY（z 0.10-0.25），
            #   而它实际靠 y 向几何重叠接触 DIFF。旧栈 LVS 一直 ACCEPT ⇒ 不改也不判红。
            "legacy_cont": name == "CONT",
            "strict": (below == claim[0] and above == claim[1]),
        })
    new_vias = [r for r in rows if not r["legacy_cont"]]
    return {
        "rows": rows,
        "n_vias": len(rows),
        "n_strict": sum(1 for r in new_vias if r["strict"]),
        "n_new_vias": len(new_vias),
        "all_new_strict": all(r["strict"] for r in new_vias),
        "order": order,
        "verdict": ("🔴 %d 个新 via **全部**严格夹在其所连两层之间（CONT 除外：旧栈继承，"
                    "靠几何接触判定）" % len(new_vias)),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ② 落垫尺寸：必须按上方 via 的 enclosure 反算
# ---------------------------------------------------------------------------
def pad_sizing_rule() -> Dict:
    """`side ≥ via_size + 2·enclosure` —— E30 的「一律 0.40」在这里被证伪。"""
    lim = _lim()
    rows = []
    for via in ("VIA1", "VIA2", "VIA3", "VIA4", "VIA5", "VIA_AP"):
        k = via.lower()
        size = lim[f"{k}_size_um"]
        enc = lim[f"{k}_enclosure_um"]
        need = size + 2.0 * enc
        rows.append({"via": via, "size_um": size, "enclosure_um": enc,
                     "min_pad_um": need,
                     "pad_used_um": max(0.40, need),
                     "exceeds_default": need > 0.40 + 1e-12})
    over = [r for r in rows if r["exceeds_default"]]
    return {
        "rows": rows,
        "over_default": over,
        "rule": "pad_side ≥ via_size + 2·enclosure",
        "verdict": ("🔴 只有 %s 的落垫需要超过缺省 0.40（需 %.2f µm）；"
                    "其余 5 个 via 的 0.20+2×0.10 = 0.40 **恰好**等于缺省值 —— "
                    "所以「一律 0.40」在 VIA1-VIA5 上侥幸成立、在 VIA_AP 上崩掉"
                    % (",".join(r["via"] for r in over),
                       over[0]["min_pad_um"] if over else 0.0)),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ③ 签核矩阵（DRC + LVS，7 个目标层）
# ---------------------------------------------------------------------------
def _params_for(row_layer: str) -> Dict[str, float]:
    """该层的合法布线参数：线宽 = `max(0.40, min_width)`；AP 另需满足行距。"""
    lim = _lim()
    if row_layer == "M1":
        return {}
    k = row_layer.lower()
    w = max(BASE_WIDTH_UM, lim.get(f"{k}_min_width_um", BASE_WIDTH_UM))
    pr: Dict[str, float] = {"row_w_um": w}
    if row_layer == "AP":
        pr["pitch_y_um"] = w + lim["ap_min_space_um"]
    return pr


def signoff_matrix(n: Optional[int] = None) -> List[Dict]:
    """7 个目标层的 DRC/LVS 签核（`via_stack=True` + 16 层栈）。结果带缓存。"""
    nn = MATRIX_N if n is None else int(n)
    return _cached("matrix_%d" % nn, lambda: _signoff_matrix_impl(nn))


def _signoff_matrix_impl(nn: int) -> List[Dict]:
    st = _stack10()
    rows: List[Dict] = []
    for rl in ("M1", "M2", "M3", "M4", "M5", "M6", "AP"):
        pr = _params_for(rl)
        arr = LY.crossbar_array(nn, nn, pr, row_layer=rl, via_stack=True)
        drc = LY.run_edrc(arr["descs"], stack=st)
        lvs = LY.elvs_signoff(arr["descs"], LY.expected_netlist(nn, nn, arr["params"]),
                              stack=st)
        rules = sorted({v["rule"] for v in drc["violations"]})
        rows.append({
            "row_layer": rl,
            "n_elements": len(arr["descs"]),
            "n_stack_per_cell": (len(LY.via_stack_descs(nn, nn, arr["params"],
                                                        row_layer=rl)) // (nn * nn)),
            "drc": drc["verdict"], "n_drc_viol": len(drc["violations"]),
            "drc_rules": rules,
            "lvs": lvs["verdict"], "n_lvs_issues": len(lvs["issues"]),
            "first_issue": (drc["violations"][0]["detail"] if drc["violations"]
                            else (lvs["issues"][0] if lvs["issues"] else "")),
            "signoff": drc["verdict"] == "ACCEPT" and lvs["verdict"] == "ACCEPT",
            "params": pr,
        })
    return rows


def signoff_summary() -> Dict:
    rows = signoff_matrix()
    passed = [r["row_layer"] for r in rows if r["signoff"]]
    failed = [r["row_layer"] for r in rows if not r["signoff"]]
    return {
        "rows": rows, "passed": passed, "failed": failed,
        "n_passed": len(passed), "n_failed": len(failed),
        "verdict": ("🔴 %d/%d 层签核通过（%s）· 失败 %s —— "
                    "**M2 失败是物理必然**（它是列线层，行线放上去 = 同层短路）"
                    % (len(passed), len(rows), "、".join(passed),
                       "、".join(failed) or "无")),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ④ M2 的负结果（物理不可行，不是工具问题）
# ---------------------------------------------------------------------------
def m2_infeasibility() -> Dict:
    """把行线放到 M2：与列线**同层相交** ⇒ 真短路，加什么栈都救不了。"""
    nn = MATRIX_N
    st = _stack10()
    arr = LY.crossbar_array(nn, nn, row_layer="M2", via_stack=True)
    drc = LY.run_edrc(arr["descs"], stack=st)
    lvs = LY.elvs_signoff(arr["descs"], LY.expected_netlist(nn, nn, arr["params"]),
                          stack=st)
    shorts = [i for i in lvs["issues"] if "ELVS-SHORT" in i]
    return {
        "row_layer": "M2", "drc": drc["verdict"], "lvs": lvs["verdict"],
        "n_short_issues": len(shorts),
        "first": (shorts[0] if shorts else (drc["violations"][0]["detail"]
                                            if drc["violations"] else "")),
        "reason": ("M2 是列线所在层；行线与列线同层相交 ⇒ `can_short(M2,M2)` 为真 ⇒ "
                   "短路。**这是拓扑必然，与层厚/线宽/栈长全部无关**"),
        "verdict": ("🔴 M2 **不可作行线层**（%d 条 ELVS-SHORT）—— "
                    "换层路径只剩 M3/M4/M5/M6/AP" % len(shorts)),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ⑤ 规模与能效（各层合法最小线宽）
# ---------------------------------------------------------------------------
def attainable_table(budget_rel: float = 5.0) -> List[Dict]:
    """每层的 `r_seg` → N 上界 → ADC 项 → vs Mythic（全部现算）。结果带缓存。"""
    return _cached("attain_%g" % float(budget_rel),
                   lambda: _attainable_impl(float(budget_rel)))


def _attainable_impl(budget_rel: float) -> List[Dict]:
    rho = PA.ELEC_PROCESS["rho_cu_ohm_um"]
    px = LY.DEFAULT_CELL_PARAMS["pitch_x_um"]
    e_conv = AC.anchor_energy_per_conversion("a28_8b")["e_conv_j"] * 1e15   # fJ
    mythic = 8.3                                                            # fJ/op
    r_base = PA.wire_resistance(px, BASE_WIDTH_UM, rho, 0.20)
    rows: List[Dict] = []
    for rl, t in LAYER_THICKNESS_UM.items():
        k = rl.lower()
        w = max(BASE_WIDTH_UM, _lim().get(f"{k}_min_width_um", BASE_WIDTH_UM))
        r = PA.wire_resistance(px, w, rho, t)
        f = BG.max_scale_full_chain(float(budget_rel), r_seg=r, scan_hi=512)
        n = int(f["n_max"])
        adc = e_conv / (2.0 * n)
        fw, fh = LY.array_footprint(n, n, _params_for(rl))
        rows.append({
            "row_layer": rl, "t_um": t, "w_um": w,
            "r_seg_ohm": r, "r_ratio": r_base / r,
            "pitch_y_um": _params_for(rl).get(
                "pitch_y_um", LY.DEFAULT_CELL_PARAMS["pitch_y_um"]),
            "n_max": n, "adc_fj": adc, "vs_mythic": adc / mythic,
            "area_mm2": fw * fh / 1e6,
        })
    return rows


def best_layer() -> Dict:
    """签核通过里能效最好的那一层（= AP）。"""
    ok = {r["row_layer"] for r in signoff_matrix() if r["signoff"]}
    cand = [r for r in attainable_table() if r["row_layer"] in ok]
    best = max(cand, key=lambda r: r["r_ratio"])
    base = [r for r in attainable_table() if r["row_layer"] == "M1"][0]
    return {
        "layer": best["row_layer"], "row": best, "baseline": base,
        "n_gain": best["n_max"] / base["n_max"],
        "adc_gain": base["adc_fj"] / best["adc_fj"],
        "vs_mythic_before": base["vs_mythic"],
        "vs_mythic_after": best["vs_mythic"],
        "area_ratio": best["area_mm2"] / base["area_mm2"],
        "verdict": ("🔴 签核通过里最强 = **%s**（W=%.2f · t=%.2f）⇒ "
                    "N %d→%d（×%.2f）· ADC 项 %.1f→%.1f fJ/op（×%.2f）· "
                    "vs Mythic %.1f×→**%.1f×** · 面积 ×%.2f"
                    % (best["row_layer"], best["w_um"], best["t_um"],
                       base["n_max"], best["n_max"], best["n_max"] / base["n_max"],
                       base["adc_fj"], best["adc_fj"], base["adc_fj"] / best["adc_fj"],
                       base["vs_mythic"], best["vs_mythic"],
                       best["area_mm2"] / base["area_mm2"])),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ⑥ via 数量与良率风险（未建模项必须显式报）
# ---------------------------------------------------------------------------
def via_count_cost(n_list: Optional[List[int]] = None) -> Dict:
    """漏极通路的 **串联 via 数** × 单元数（良率风险必须显式报）。

    🔴 **本函数 v0.9.329 修正过一个口径错**（E33 串流程时抓到）：
    第一版写 `n_vias = n² × len(ROW_STACK_CHAIN)` = `n² × 12`，但 `ROW_STACK_CHAIN`
    的 12 项里**只有 6 项是 via**（VIA1..VIA5 + VIA_AP），另外 6 项是**金属落垫**
    （M1..M6）。把金属算成 via ⇒ 良率风险**高估 2 倍**（9.1% vs 实际 4.5%）。

    ⇒ 现在区分两个量：
      · `n_via_in_path` = 串联 via 数 = **6**（漏极 → AP 行线，任一失效即通路失效）
      · `n_via_total`   = 串联数 × 单元数（良率口径）
      · `stack_len`     = 链长 **12**（含金属落垫，**不是 via 数**）
    """
    lim = _lim()
    st10 = EL.get_estack("ecmos10")
    stack_len = len(LY.ROW_STACK_CHAIN)
    n_via_in_path = sum(1 for nm in LY.ROW_STACK_CHAIN
                        if st10.layers[nm].kind == "via")
    pad = max(0.40, lim["via_ap_size_um"] + 2.0 * lim["via_ap_enclosure_um"])  # 0.80（M6 落垫）
    cell_area_ap = (LY.DEFAULT_CELL_PARAMS["pitch_x_um"]
                    * (max(BASE_WIDTH_UM, lim["ap_min_width_um"])
                       + lim["ap_min_space_um"]))
    rows = []
    for n in (n_list or [12, 29, 87]):
        rows.append({
            "n": int(n), "n_cells": int(n) * int(n),
            # 🔴 `n_vias` 是**串联节点总数**（良率口径），不是链长 × 单元数
            "n_vias": int(n) * int(n) * n_via_in_path,
            "n_vias_in_path": n_via_in_path,
            "stack_area_um2": (int(n) * int(n)) * BASE_WIDTH_UM * BASE_WIDTH_UM,
        })
    return {
        "stack_len": stack_len,
        "n_via_in_path": n_via_in_path,
        "pad_side_um": pad,
        "stack_area_frac": (BASE_WIDTH_UM ** 2) / cell_area_ap,
        "rows": rows,
        "yield_note": ("🔴 漏极通路 **串联 %d 个 via** × %s 单元 = **%s 个串联节点**（N=87）"
                       "⇒ 1 ppm/节点即整体 ~%.2f%% 失效。**良率未建模**；DRC/LVS 过 ≠ 可制造"
                       % (n_via_in_path, format(rows[-1]["n_cells"], ","),
                          format(rows[-1]["n_vias"], ","),
                          rows[-1]["n_vias"] * 1e-6 * 100)),
        "verdict": ("🔴 N=87 需 **串联 %d 个 via/单元**（链长 %d 含金属落垫）· 共 **%s 个串联节点** · "
                    "栈面积占单元 %.2f%% · **良率是拒绝清单外的最大未知**"
                    % (n_via_in_path, stack_len, format(rows[-1]["n_vias"], ","),
                       (BASE_WIDTH_UM ** 2) / cell_area_ap * 100)),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ⑦ 基线保护（E31 的全部改动都是可选的，默认必须逐位不变）
# ---------------------------------------------------------------------------
#: v0.9.326 的三档默认几何指纹（`gds_bytes`, `flat_elements`）
BASELINE_GDS: Dict[int, tuple] = {4: (936, 120), 8: (1272, 464), 12: (1608, 1032)}


def baseline_unchanged() -> Dict:
    """默认路径（`row_layer=M1` · `via_stack=False`）必须与 v0.9.326 逐位一致。"""
    rows = []
    for n, (g0, f0) in BASELINE_GDS.items():
        LY.crossbar_array(n, n)
        g = LY.to_gds(n, n)
        rt = LY.gds_roundtrip_check(n, n)
        rows.append({"n": n, "gds_bytes": g["n_bytes"], "expect_bytes": g0,
                     "flat": g["flat_elements"], "expect_flat": f0,
                     "roundtrip": rt["match"],
                     "ok": g["n_bytes"] == g0 and g["flat_elements"] == f0 and rt["match"]})
    return {"rows": rows, "all_ok": all(r["ok"] for r in rows),
            "verdict": ("✅ 默认路径与 v0.9.326 逐位一致（%s）"
                        % " · ".join("%dB/%df" % (r["gds_bytes"], r["flat"]) for r in rows)),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑧ 自检
# ---------------------------------------------------------------------------
def signed_off_stack_self_check(verbose: bool = False) -> bool:
    checks: List[tuple] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append((bool(cond), name, detail))
        if verbose:
            print(("[OK] " if cond else "[NG] ") + name + (("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① 层序：新 via 全部严格夹层
    za = z_order_audit()
    # 🔴 **反向完备**：必须同时断言 via 数量 == 6。
    #   只写 `all_new_strict` 时，若 via_map 被删掉一项（例如 VIA_AP），
    #   "剩下的都合格" 恒真 ⇒ 判据反而变绿（E30 的 `all([])` 同型，门禁 C3 专守此点）。
    ok &= chk("① 🔴 %d 个新 via（VIA1..VIA_AP）**全部**严格夹在其所连两层之间"
              % za["n_new_vias"],
              za["all_new_strict"] and za["n_new_vias"] == 6,
              "n_strict=%d/%d" % (za["n_strict"], za["n_new_vias"]))

    # ② VIA_AP 必须在 AP 之下（E30 的错位就是这条不成立）
    ok &= chk("② 🔴 `pos_of(VIA_AP) < pos_of(AP)`（E30 是反的 ⇒ 永远悬空）",
              za["order"].index("VIA_AP") < za["order"].index("AP"),
              "VIA_AP@%d < AP@%d" % (za["order"].index("VIA_AP"),
                                     za["order"].index("AP")))

    # ③ 落垫规则：VIA_AP 需 0.80，其余 0.40
    ps = pad_sizing_rule()
    ok &= chk("③ 🔴 `pad ≥ via_size+2·enclosure`：只有 VIA_AP 超过 0.40（需 %.2f）"
              % (ps["over_default"][0]["min_pad_um"] if ps["over_default"] else 0.0),
              len(ps["over_default"]) == 1
              and ps["over_default"][0]["via"] == "VIA_AP"
              and abs(ps["over_default"][0]["min_pad_um"] - 0.80) < 1e-12)

    # ④ 签核矩阵：6 通过 / 1 失败（M2）
    sm = signoff_summary()
    ok &= chk("④ 🔴 签核 %d 通过（%s）· 仅 %s 失败"
              % (sm["n_passed"], "、".join(sm["passed"]), "、".join(sm["failed"])),
              sm["n_passed"] == 6 and sm["failed"] == ["M2"])

    # ⑤ M2 失败是短路（不是工具问题）
    m2 = m2_infeasibility()
    ok &= chk("⑤ 🔴 M2 失败根因 = **同层短路**（%d 条 ELVS-SHORT），非工具缺陷"
              % m2["n_short_issues"], m2["n_short_issues"] > 0)

    # ⑥ 栈长 = 2×层数（每层一个 via + 一个落垫，末端行线充当落垫）
    lens = {r["row_layer"]: r["n_stack_per_cell"] for r in sm["rows"]}
    ok &= chk("⑥ 栈长递增：M1=0 · M2=2 · M3=4 · M6=10 · AP=12（=2×层数）",
              lens["M1"] == 0 and lens["M2"] == 2 and lens["M3"] == 4
              and lens["M6"] == 10 and lens["AP"] == 12)

    # ⑦ 换层必须靠栈：关掉栈则 M3/AP 全 REJECT
    st = _stack10()
    off = []
    for rl in ("M3", "AP"):
        arr = LY.crossbar_array(MATRIX_N, MATRIX_N, _params_for(rl),
                                row_layer=rl, via_stack=False)
        lv = LY.elvs_signoff(arr["descs"],
                             LY.expected_netlist(MATRIX_N, MATRIX_N, arr["params"]),
                             stack=st)
        off.append(lv["verdict"])
    ok &= chk("⑦ 🔴 关掉 via stack ⇒ M3/AP 的 LVS 全部 REJECT（%s）⇒ **栈是充分必要件**"
              % "/".join(off), all(v != "ACCEPT" for v in off))

    # ⑧ 默认路径逐位不变
    bu = baseline_unchanged()
    ok &= chk("⑧ 默认路径（M1·无栈）与 v0.9.326 逐位一致（%s）" % bu["verdict"][2:20],
              bu["all_ok"])

    # ⑨ AP 是签核通过里最强
    bl = best_layer()
    ok &= chk("⑨ 🔴 最强签核层 = **%s**（N %d→%d · vs Mythic %.1f×→%.1f×）"
              % (bl["layer"], bl["baseline"]["n_max"], bl["row"]["n_max"],
                 bl["vs_mythic_before"], bl["vs_mythic_after"]),
              bl["layer"] == "AP" and bl["row"]["n_max"] > bl["baseline"]["n_max"])

    # ⑩ AP 的 r 倍数 = t 倍数 × W 倍数（**分解清楚，不能只说 ×40**）
    ap = bl["row"]
    t_ratio = ap["t_um"] / 0.20
    w_ratio = ap["w_um"] / BASE_WIDTH_UM
    ok &= chk("⑩ AP 的 r×%.0f 分解 = t×%.0f × W×%.0f（**强制加宽贡献了一半以上**）"
              % (ap["r_ratio"], t_ratio, w_ratio),
              abs(ap["r_ratio"] - t_ratio * w_ratio) / ap["r_ratio"] < 1e-9)

    # ⑪ 面积：M3-M6 不变、AP ×1.33
    area_ok = True
    for r in attainable_table():
        pass
    base_py = LY.DEFAULT_CELL_PARAMS["pitch_y_um"]
    for rl in ("M3", "M4", "M5", "M6"):
        area_ok &= abs(_params_for(rl).get("pitch_y_um", base_py) - base_py) < 1e-12
    ap_py = _params_for("AP")["pitch_y_um"]
    ok &= chk("⑪ 🔴 面积：M3-M6 的 `pitch_y` 保持 %.2f（**换层不加面积**）· AP→%.2f（×%.2f）"
              % (base_py, ap_py, ap_py / base_py),
              area_ok and abs(ap_py / base_py - 4.0 / 3.0) < 1e-9)

    # ⑫ via 数量代价必须显式
    vc = via_count_cost()
    # 🔴 判据必须钉**串联 via 数 = 6**（不是链长 12）：链里有 6 个金属落垫，
    #   把它们算成 via 会让良率风险高估 2×（v0.9.329 修正）
    ok &= chk("⑫ 🔴 N=87 需 **串联 %d 个 via/单元**（链长 %d 含金属落垫）⇒ 共 %s 个串联节点 · "
              "良率未建模（1 ppm ⇒ ~%.2f%%）"
              % (vc["n_via_in_path"], vc["stack_len"],
                 format(vc["rows"][-1]["n_vias"], ","),
                 vc["rows"][-1]["n_vias"] * 1e-6 * 100),
              vc["n_via_in_path"] == 6
              and vc["rows"][-1]["n_vias"] == 87 * 87 * 6
              and vc["stack_len"] == 12)

    # ⑬ 恒标 MODEL_ESTIMATE
    ok &= chk("⑬ 全部输出恒标 `MODEL_ESTIMATE`",
              all(x["tier"] == E.OUTPUT_TIER
                  for x in (za, ps, m2, vc)))

    npass = sum(1 for c, _, _ in checks if c)
    nfail = len(checks) - npass
    if verbose:
        print()
        print("MODE=%s 合计 %d 判据 · PASS %d / FAIL %d"
              % (E.OUTPUT_TIER, len(checks), npass, nfail))
    return ok


SIGNED_OFF_STACK_DISCLOSURE = {
    "role": "E31 = 换层签核（漏极 via stack + DRC/LVS 漏检修复）· 让 E30 的「表达不了」变成「可签核」",
    "what_changed": "① 修 5 个 via 的 z 位置（E30 错位一层 ⇒ VIA_AP 永远悬空）· "
                    "② `run_edrc`/`elvs_signoff` 加 `stack` 参数（旧栈下新层 via 完全不查 = 静默漏检）· "
                    "③ 落垫尺寸按上方 via enclosure 反算（M6 需 0.80）· "
                    "④ 行线端帽（AP 最外侧 via 差 0.025）· ⑤ `to_gds` 透传（否则 stack 静默丢失）",
    "what_it_does_not_mean": "DRC/LVS 过只说明**几何自洽**，不是可制造性（无 CMP/OPC/天线/密度规则）；"
                             "N=87 是一维规模律上界，未做电路仿真；"
                             "45,414 个串联 via 节点的良率**完全未建模**",
    "tier": E.OUTPUT_TIER,
}


__all__ = [
    "MATRIX_N", "BASE_WIDTH_UM", "LAYER_THICKNESS_UM", "END_VIA_OF",
    "BASELINE_GDS", "z_order_audit", "pad_sizing_rule", "signoff_matrix",
    "signoff_summary", "m2_infeasibility", "attainable_table", "best_layer",
    "via_count_cost", "baseline_unchanged", "signed_off_stack_self_check",
    "SIGNED_OFF_STACK_DISCLOSURE",
]
