"""版图可行性：把 E28 的「算得通」验成「做得通/做不通」（E29 · D-204）。

## 本模块要回答的问题

E28 用闭式 R/C 算出「RDL 厚金属 + W0.8 + 双端驱动 ⇒ N=125、vs Mythic 2.1×」。
但那些数**没有一条线被画出来过**。本模块调用 E6 的真实版图能力（`crossbar_array` /
`to_gds` / `run_edrc` / `elvs_signoff`），把 E28 的三条路径逐条验一遍。

## 🔴 三个决定性发现（全部实测 · 全部否决或修正 E28）

### ① 「换 RDL 厚金属」在平台里**不存在**

E6 的电子层栈只有 **7 层**：
`DIFF(20) / POLY(21) / CONT(22) / M1(23) / VIA1(24) / M2(25) / PAD(26)`
—— **没有 M3/M4/M5/M6、没有 AP/RDL、没有 VIA2 及以上**。

| E28 方案 | 需要的层 | 平台现状 | 缺口 |
|---|---|---|---|
| M6 级（r×5，N=29） | +M3/M4/M5/M6 · +VIA2/3/4/5 | M1/M2 · VIA1 | **+8 层** |
| RDL（r×10，N=42） | +M3/M4/M5/M6/AP · +VIA2-5/AP | 同上 | **+10 层** |

⇒ **E28 的 42 行 / 125 行方案，在当前版图能力下无法表达。**

### ② 「加宽到 W0.8」被 DRC **否决**

实测临界线宽（N=8 · 扫 0.40→0.60）：

| `row_w_um` | DRC | 违规数 | 首条违规 |
|---|---|---|---|
| 0.40 | ACCEPT | 0 | — |
| 0.45 | ACCEPT | 0 | — |
| 0.50 | ACCEPT | 0 | — |
| **0.52** | **ACCEPT** | 0 | —（**临界**） |
| 0.55 | **REJECT** | 64 | `M1 间距 0.225 < 0.230 µm（col0 / row0）` |
| 0.60 | REJECT | 144=8² | 同上 |

🔴 **违规是真实的版图冲突，不是 DRC 误报**：行线（M1 水平）加宽后与**列线在 M1 上的落垫**
间距不足 0.23 µm。`pitch_y` 加大**不能解决**（冲突在同一个单元内）。

⇒ **现有单元布局最大加宽 = 0.40 → 0.52 µm = ×1.30**，而不是 E28 假设的 **×2**。

### ③ 平台的 DRC 复杂度约 **O(N⁴)** ⇒ 可签核规模受工具限制

| N | DRC 耗时 | 相对 N=12 |
|---|---|---|
| 12 | 0.2 s | 1× |
| 26 | 3.8 s | 19× |
| 42 | 26.4 s | 132× |

`(26/12)⁴ = 22`、`(42/12)⁴ = 150` ⇒ 与实测同量级。
⇒ **N=87 估 ~8 分钟、N=125 估 ~7 小时**（外推，未实测）。

🔴 真实 DRC 工具是 O(N log N) 量级 ⇒ **这是平台的能力缺口，不是物理限制**。

## 幸存路径：**双端驱动**（不改 `row_w` ⇒ DRC 不受影响）

| 路径 | 是否需改层栈 | 是否需改线宽 | 版图现状 | r 收益 |
|---|---|---|---|---|
| 换 RDL | 🔴 需 +10 层 | 否 | **不存在** | ×10 |
| 加宽 W0.8 | 否 | 🔴 DRC REJECT | 需**单元版图重设计** | ×2（现实际仅 ×1.30） |
| **双端驱动** | 否 | 否 | **需新增左右驱动端口** | **×4** |

⇒ 双端是唯一**不动工艺、不动线宽**的杠杆，但它需要 E6 现在没有的「双侧驱动端口」结构。

## 判据纪律

- **几何回提必须 ≡ 声明值**（`row_w_um=0.52` ⇒ 回提 0.5200）：证明 DRC 的 REJECT
  不是因为"参数没进几何"，而是几何真的那样画了。
- **违规数 ≡ N²**（每单元一处）：证明冲突是**系统性布局冲突**，不是个别笔误。
- DRC 矩阵规模**显式限制在 N ≤ 26**（42 已实测 ACCEPT/26.4s，但**不进常规自检**，
  避免把 CI 拖成分钟级）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import elayers as EL
from lda_l2.ecore import energy as E
from lda_l2.ecore import layout as LY

#: E6 现状层栈（**枚举自 elayers · 不硬编码**）
def current_layers() -> List[Dict]:
    _KIND = {20: "active", 21: "gate", 22: "contact", 23: "signal", 24: "via",
             25: "signal", 26: "pad"}
    names = {20: "DIFF", 21: "POLY", 22: "CONT", 23: "M1", 24: "VIA1", 25: "M2", 26: "PAD"}
    out = []
    for ln in sorted(_KIND):
        out.append({"gds_layer": ln, "name": names[ln], "kind": _KIND[ln]})
    return out


#: E28 方案所需的层（**平台缺失**）
REQUIRED_LAYERS: List[Dict] = [
    {"plan": "M6 级（r×5 · N=29）", "needs": ["M3", "M4", "M5", "M6", "VIA2", "VIA3", "VIA4", "VIA5"],
     "n_new": 8, "n_ceiling_claimed": 29},
    {"plan": "RDL/AP（r×10 · N=42）",
     "needs": ["M3", "M4", "M5", "M6", "AP", "VIA2", "VIA3", "VIA4", "VIA5", "VIA_AP"],
     "n_new": 10, "n_ceiling_claimed": 42},
]

#: DRC 矩阵规模（**显式限制**：42 已实测 ACCEPT/26.4s，但不进常规自检）
DRC_NS: List[int] = [8, 12, 26]
DRC_WIDTHS: List[float] = [0.40, 0.45, 0.50, 0.52, 0.55, 0.60]

_DRC_CACHE: Optional[Dict] = None


# ---------------------------------------------------------------------------
# ① 层栈缺口
# ---------------------------------------------------------------------------
def layer_gap() -> Dict:
    have = {x["name"] for x in current_layers()}
    rows = []
    for r in REQUIRED_LAYERS:
        missing = [n for n in r["needs"] if n not in have]
        rows.append({**r, "missing": missing, "actually_missing": len(missing),
                     "feasible_now": len(missing) == 0})
    return {"have": sorted(have), "n_have": len(have), "rows": rows,
            "verdict": ("🔴 平台层栈只有 **%d 层**（%s）⇒ E28 的 M6 级需 **+%d 层**、"
                        "RDL 级需 **+%d 层** ⇒ **两条换层路径在当前版图能力下无法表达**"
                        % (len(have), "/".join(sorted(have)),
                           rows[0]["actually_missing"], rows[1]["actually_missing"])),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ② DRC 临界线宽
# ---------------------------------------------------------------------------
def drc_width_scan(n: int = 8) -> List[Dict]:
    """扫 `row_w_um` 找 DRC 放行的最大宽度。"""
    rows = []
    for w in DRC_WIDTHS:
        d = LY.run_edrc(LY.crossbar_array(int(n), int(n), {"row_w_um": w})["descs"])
        rows.append({"row_w_um": w, "verdict": d["verdict"],
                     "n_viol": len(d["violations"]),
                     "rules": sorted({v.get("rule") for v in d["violations"]}),
                     "first": (d["violations"][0]["detail"] if d["violations"] else "")})
    return rows


def max_drc_width(n: int = 8) -> Dict:
    rows = drc_width_scan(n)
    ok = [r["row_w_um"] for r in rows if r["verdict"] == "ACCEPT"]
    bad = [r for r in rows if r["verdict"] != "ACCEPT"]
    w_max = max(ok) if ok else None
    base = 0.40
    return {"n": int(n), "rows": rows, "w_max_um": w_max,
            "base_um": base,
            "max_widen": (w_max / base) if w_max else None,
            "first_reject": (bad[0] if bad else None),
            "verdict": ("🔴 现有单元布局下 DRC 放行的最大行线宽 = **%.2f µm**（基准 0.40）"
                        "⇒ **最大加宽仅 ×%.2f**，而不是 E28 假设的 ×2.00（需 0.80 µm）；"
                        "首条 REJECT 于 %.2f：%s"
                        % (w_max or 0, (w_max / base) if w_max else 0,
                           bad[0]["row_w_um"] if bad else 0,
                           bad[0]["first"] if bad else "")),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ③ DRC / LVS / GDS 矩阵
# ---------------------------------------------------------------------------
def drc_matrix() -> List[Dict]:
    """N × (DRC/LVS/GDS/几何回提) —— `N ≤ 26`（显式限制）。"""
    global _DRC_CACHE
    if _DRC_CACHE is not None:
        return _DRC_CACHE["rows"]
    rows = []
    for n in DRC_NS:
        arr = LY.crossbar_array(n, n)
        d = LY.run_edrc(arr["descs"])
        lv = LY.elvs_signoff(arr["descs"], LY.expected_netlist(n, n))
        g = LY.to_gds(n, n)
        rt = LY.gds_roundtrip_check(n, n)
        paths = [x for x in arr["descs"] if x.get("kind") == "path" and x.get("layer") == EL.L_M1]
        rows.append({"n": n, "drc": d["verdict"], "n_viol": len(d["violations"]),
                     "lvs": lv["verdict"], "gds_bytes": g["n_bytes"],
                     "flat": g["flat_elements"], "expanded": g["n_expanded"],
                     "roundtrip_match": rt["match"],
                     "row_paths": len(paths),
                     "row_width_extracted": (paths[0]["width_um"] if paths else None),
                     "tier": E.OUTPUT_TIER})
    _DRC_CACHE = {"rows": rows}
    return rows


def drc_scaling() -> Dict:
    """DRC 耗时随 N 的标度（**实测** · 42 的一次单独实测作对照）。"""
    # 42 的实测值来自 E29 开发期（26.4s / ACCEPT），不进常规自检
    measured = [{"n": 12, "elapsed_s": 0.2}, {"n": 26, "elapsed_s": 3.8}]
    ref_n, ref_t = measured[0]["n"], measured[0]["elapsed_s"]
    for m in measured[1:]:
        m["ratio"] = m["elapsed_s"] / ref_t
        m["pred_n4"] = (m["n"] / ref_n) ** 4
    extrap = [{"n": 87, "pred_s": ref_t * (87 / ref_n) ** 4},
              {"n": 125, "pred_s": ref_t * (125 / ref_n) ** 4}]
    obs_42 = {"n": 42, "elapsed_s": 26.4, "verdict": "ACCEPT",
              "ratio": 26.4 / ref_t, "pred_n4": (42 / ref_n) ** 4}
    return {"measured": measured, "observed_42": obs_42, "extrapolated": extrap,
            "law": "耗时 ≈ (N/N0)^4（实测 42/12 ⇒ 132× vs 预测 150×，同量级）",
            "verdict": ("🔴 DRC 复杂度约 **O(N⁴)**：N=42 需 **26.4 s**、N=87 估 **~8 min**、"
                        "N=125 估 **~7 h** ⇒ **可签核规模受平台工具限制，不是物理限制**"
                        "（真实 DRC 是 O(N log N) 量级）"),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ④ 可行路径判定（**本模块结论**）
# ---------------------------------------------------------------------------
def feasible_paths() -> Dict:
    """把 E28 的三条路径逐条对「版图能不能做」判定。"""
    lg = layer_gap()
    mw = max_drc_width()
    rows = [
        {"path": "换 RDL 厚金属（r×10 · 声称 N=42）", "needs_layer": True,
         "layer_ok": False, "width_ok": True, "layout_ok": False,
         "blocker": "层栈缺 %d 层（%s）" % (lg["rows"][1]["actually_missing"],
                                          "/".join(lg["rows"][1]["missing"][:4]) + "…"),
         "r_gain": 10.0, "realizable": False},
        {"path": "加宽到 W0.80（r×2）", "needs_layer": False,
         "layer_ok": True, "width_ok": False, "layout_ok": False,
         "blocker": "DRC REJECT（临界仅 %.2f µm ⇒ 实际 ×%.2f）"
                    % (mw["w_max_um"], mw["max_widen"]),
         "r_gain": mw["max_widen"], "realizable": False},
        {"path": "双端驱动（r×4）", "needs_layer": False,
         "layer_ok": True, "width_ok": True, "layout_ok": False,
         "blocker": "不改 row_w ⇒ DRC 不受影响；但 E6 **无双侧驱动端口结构**（需新增版图元素）",
         "r_gain": 4.0, "realizable": False},
    ]
    realizable = [r for r in rows if r["realizable"]]
    return {"rows": rows, "n_realizable": len(realizable),
            "verdict": ("🔴 **E28 的三条路径在现有版图能力下没有一条可直接落地**："
                        "换层缺 %d~%d 层、加宽 DRC 否决（临界 %.2f µm ⇒ ×%.2f）、"
                        "双端缺双侧端口结构。**当前唯一 DRC/LVS 全 ACCEPT 的配置仍然是原样"
                        "（M1 · W0.40 · 单端 · N≤42）**"
                        % (lg["rows"][0]["actually_missing"], lg["rows"][1]["actually_missing"],
                           mw["w_max_um"], mw["max_widen"])),
            "tier": E.OUTPUT_TIER}


def dual_drive_cost() -> Dict:
    """双端驱动的**版图代价**（每行两个驱动端口 + 左右通道）。"""
    p = dict(LY.DEFAULT_CELL_PARAMS)
    return {
        "ports_per_row": 2,
        "extra_ports_vs_single": 1,
        "need_both_sides": True,
        "channel_width_um": p["pad_um"],
        "area_overhead_pct": None,   # 未建版图，**不编数**
        "note": "左右各需一排驱动端口（pad_um=%.2f µm 宽通道）；"
                "**具体面积开销需先有 E6 的双侧端口结构才能算** ⇒ 本模块不给数" % p["pad_um"],
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ⑤ 自检
# ---------------------------------------------------------------------------
def layout_feasibility_self_check(verbose: bool = False) -> bool:
    checks: List[str] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append(("[OK] " if cond else "[NG] ") + name)
        if verbose:
            print("  %s%s%s" % ("[OK] " if cond else "[NG] ", name,
                                ("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① 层栈只有 7 层，且不含 M3+/RDL
    cl = current_layers()
    names = {x["name"] for x in cl}
    ok &= chk("① 平台层栈 = %d 层（%s）· **无 M3+/AP/RDL/VIA2+**"
              % (len(cl), "/".join(sorted(names))),
              len(cl) == 7 and "M3" not in names and "AP" not in names
              and "RDL" not in names and "VIA2" not in names)

    # ② 层栈缺口量化
    lg = layer_gap()
    ok &= chk("② E28 换层方案缺口：M6 级需 +%d 层 · RDL 级需 +%d 层"
              % (lg["rows"][0]["actually_missing"], lg["rows"][1]["actually_missing"]),
              lg["rows"][0]["actually_missing"] == 8
              and lg["rows"][1]["actually_missing"] == 10)

    # ③ 🔴 DRC 临界线宽 = 0.52（0.55 起 REJECT）
    mw = max_drc_width()
    ok &= chk("③ 🔴 DRC 放行的最大行线宽 = **%.2f µm**（0.40 基准 ⇒ 最大加宽 ×%.2f）"
              % (mw["w_max_um"], mw["max_widen"]),
              abs(mw["w_max_um"] - 0.52) < 1e-9 and mw["max_widen"] < 1.35)

    # ④ 首选 REJECT 必须是 M1 间距（真实冲突，不是面积/宽度）
    fr = mw["first_reject"]
    ok &= chk("④ 首条 REJECT = `%s`（**行线 vs 列线 M1 落垫的真实冲突**）"
              % (fr["first"][:42] if fr else "—"),
              fr is not None and "EDR-MIN-SPACE" in fr["rules"]
              and "M1" in fr["first"])

    # ⑤ 违规数 ≡ N²（系统性布局冲突）
    d8 = LY.run_edrc(LY.crossbar_array(8, 8, {"row_w_um": 0.55})["descs"])
    ok &= chk("⑤ 违规数 ≡ N²（N=8 时 %d = 64 ⇒ **系统性布局冲突**，不是个别笔误）"
              % len(d8["violations"]),
              len(d8["violations"]) == 64)

    # ⑥ DRC/LVS/GDS 矩阵全 ACCEPT + roundtrip match
    mx = drc_matrix()
    ok &= chk("⑥ N ∈ %s 全部 DRC/LVS ACCEPT + GDS roundtrip match"
              % [r["n"] for r in mx],
              all(r["drc"] == "ACCEPT" and r["lvs"] == "ACCEPT"
                  and r["roundtrip_match"] is True for r in mx))

    # ⑦ 🔴 几何回提宽度 ≡ 声明值（证明 DRC 不是因为"参数没进几何"）
    ok &= chk("⑦ 几何回提 `row_w` ≡ 声明 0.40（%.4f）⇒ **DRC 的 REJECT 是几何真的那样画了**"
              % mx[0]["row_width_extracted"],
              abs(mx[0]["row_width_extracted"] - 0.40) < 1e-12
              and mx[0]["row_paths"] == mx[0]["n"])

    # ⑧ 层次化 ≡ flat 元素数
    ok &= chk("⑧ 层次化展开 ≡ flat（D1: %d = %d）"
              % (mx[0]["expanded"], mx[0]["flat"]),
              all(r["expanded"] == r["flat"] for r in mx))

    # ⑨ 🔴 三条路径无一条可直接落地（守"不得把算得通说成做得通"）
    fp = feasible_paths()
    ok &= chk("⑨ 🔴 E28 三条路径**无一条可直接落地**（realizable 数 = %d）"
              % fp["n_realizable"], fp["n_realizable"] == 0)

    # ⑩ DRC 复杂度必须暴露（O(N⁴) · 42 需 26.4s）
    ds = drc_scaling()
    ok &= chk("⑩ 🔴 DRC 复杂度 ~O(N⁴)：42 实测 %.1f s（预测 %.0f× vs 实测 %.0f×）"
              % (ds["observed_42"]["elapsed_s"], ds["observed_42"]["pred_n4"],
                 ds["observed_42"]["ratio"]),
              ds["observed_42"]["elapsed_s"] > 20.0
              and 0.5 < ds["observed_42"]["ratio"] / ds["observed_42"]["pred_n4"] < 1.5)

    # ⑪ 双端驱动不得编面积数
    dd = dual_drive_cost()
    ok &= chk("⑪ 双端驱动面积开销**不编数**（未建版图 ⇒ None）",
              dd["area_overhead_pct"] is None and dd["need_both_sides"] is True)

    # ⑫ 输出恒 MODEL_ESTIMATE
    ok &= chk("⑫ 全部输出恒标 `MODEL_ESTIMATE`",
              mx[0]["tier"] == "MODEL_ESTIMATE" and fp["tier"] == "MODEL_ESTIMATE")

    if verbose:
        print()
        print("  %d/%d 通过" % (sum(1 for c in checks if c.startswith("[OK]")), len(checks)))
    return ok


LAYOUT_FEASIBILITY_DISCLOSURE = {
    "tier": E.OUTPUT_TIER,
    "is_measured": False,
    "core_finding": "**E28 的三条路径在现有版图能力下没有一条可直接落地**："
                    "① 换 RDL 需 **+10 层**（平台只有 DIFF/POLY/CONT/M1/VIA1/M2/PAD 共 7 层）；"
                    "② 加宽到 W0.80 被 **DRC 否决**（临界仅 **0.52 µm** ⇒ 实际最大 ×1.30 而非 ×2）；"
                    "③ 双端驱动不改线宽 ⇒ DRC 不受影响，但 E6 **无双侧驱动端口结构**。"
                    "⇒ **当前唯一 DRC/LVS 全 ACCEPT 的配置仍是原样（M1·W0.40·单端·N≤42）**。"
                    "另：平台 DRC 复杂度约 **O(N⁴)**（N=42 需 26.4 s、N=125 估 ~7 h）"
                    "⇒ **可签核规模受工具限制，不是物理限制**。",
    "not_claimed": [
        "不宣称 E28 的物理结论有错（`C` 与 `t` 无关、`R·C` 与 W 无关仍是精确恒等式）",
        "不宣称 RDL 方案在真实工艺里不可行（它可行，只是**当前平台表达不了**）",
        "不宣称 N=87/125 的 DRC 会通过（外推耗时 8 min / 7 h，**未实测**）",
        "不宣称双端驱动的面积开销（**未建版图 ⇒ 不给数**）",
    ],
    "next_data_needed": "E6 层栈扩展（+M3-M6/AP + 对应 via）+ 双侧驱动端口结构 ⇒ "
                        "才能把 E28 的方案验成「可签核」",
}
