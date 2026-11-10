"""P5 · 单元版图模板化：结构公式（代码）+ 校准表（数据）。

═══════════════════════════════════════════════════════════════════════════════
它解决什么问题
───────────────────────────────────────────────────────────────────────────────
`dcells` 里两个单元的版图是**手写坐标**（`build_inv`/`build_nand2` 共 129 行、每个坐标一个
魔法数）。本模块把「结构」抽成公式、把「这批手写值的折中」抽成数据：

    Cell = TEMPLATE[family](PARAMS[cell])

⇒ `INV_X1` / `NAND2_X1` 在本模块下**逐位复现**手写几何（矩形 + 引脚，DRC 0 / LVS 0）。
⇒ 参数压缩：`INV_X1` 18 矩形×4 坐标 **72 个数 → 33 个参数**；`NAND2_X1` 25×4 **100 → 39**。

═══════════════════════════════════════════════════════════════════════════════
🔴🔴 但 P5 的 DoD 三条**不能同时成立**（实测，不是推测）
───────────────────────────────────────────────────────────────────────────────
规划 §3 P5 DoD：①18 个单元全可造 ②模板输出与手写逐位相同 ③加第 19 个单元改 0 个 .py。

实测状态：

| DoD | 状态 | 证据 |
|---|---|---|
| ② 逐位相同 | ✅ **成立**（2/2 手写单元） | `verify_bitwise()` 逐矩形逐引脚；`EC-P501` |
| ① 18 个全可造 | ❌ **不成立** | 只有 2 个家族有模板；且见下面两条硬约束 |
| ③ 加第 19 个改 0 个 .py | ❌ **不成立**（零参数意义下） | 外推 NAND3 连撞 4 类 DRC + 1 类 LVS |

**硬约束一（拓扑）**：并联 PMOS 在 `n≥3` 时**不能**用「单条 DIFF 被栅切段」的画法外推。
`Y—a—VDD—b—VDD—c—Y` 会让中间器件的源漏都变成 `VDD` ⇒ LVS 提取出 `('pmos',…,('VDD','VDD'))`
**退化器件**。真实库用叉指（每器件独立源接 VDD、漏接 Y）—— 那是**新拓扑**，不是参数。

**硬约束二（校准不可省）**：手写值的折中极精细且**逐器件不同**：
栅 cont 左移量逐栅为 **14.5 / 20.5 nm**（不是常数）、pin pad 尺寸逐引脚不同、
cont 到 DIFF 边 72.5 vs 67.5 不对称。任何「居中/均分」的默认规则都会撞
`min_space_L23` / `cont_enc_m1`（实测 3 轮迭代仍不收敛）。

⇒ **诚实定位**：本模块是「**已校准单元的等价重现 + 新单元的起点**」，
不是「自动生成器」。加新单元仍需一段 PARAMS（约 35 个数），**但不需要改一行模板代码** ——
这是把「改 `.py`」降级为「加数据」的真实收益，不是「零工作量」。

═══════════════════════════════════════════════════════════════════════════════
不做什么
───────────────────────────────────────────────────────────────────────────────
· 不改 `dcells.CELLS`（主链仍用手写版，本模块只做等价重现与诊断）。
· 不宣称任何几何是「最优」；它是**手写版的参数化表达**，尺寸/DRC 状态与手写版逐位一致。
"""

from typing import Any, Dict, List, Optional

from . import dcells as CL

L_DIFF, L_POLY, L_CONT, L_M1, L_NWELL = 20, 21, 22, 23, 19

P5_DISCLOSURE = {
    "claimable": False,
    "scope": "DIAGNOSTIC_ONLY",
    "in_blocking": False,
    "what": "把两个手写单元的版图抽成「结构公式 + 校准参数表」，并逐位复现手写几何",
    "not_claimed": (
        "① 不是自动生成器：新单元仍需人工校准时参数（约 35 个数）"
        "；② 不覆盖 18 个单元（仅 inv / nand2 两族）"
        "；③ 不产出比手写更优的版图（是等价表达）"),
    "dod_status": {
        "逐位相同": "成立（2/2）",
        "18 个单元全可造": "不成立（2/18，见硬约束）",
        "加第 19 个改 0 个 .py": "不成立（零参数意义）；成立的部分=改数据不改模板代码",
    },
}


def _C(cx: float, cy: float, size: int, role: str, layer: int = L_CONT):
    """接触孔：**只取整一次**再固定尺寸（两次独立 round 会得到 44/46 宽 ⇒ 1nm 即违例）。"""
    x0 = int(round(cx - size / 2.0))
    y0 = int(round(cy - size / 2.0))
    return CL.R(layer=layer, x0=x0, y0=y0, x1=x0 + size, y1=y0 + size, role=role)


# ─────────────────────────────────────────────────────────────────────────────
# ① 模板：inv 族
# ─────────────────────────────────────────────────────────────────────────────
def gen_inv(P: Dict[str, Any]):
    """单输入反相器：1 PMOS + 1 NMOS，栅共用 A，漏共用 Y。"""
    w, h = P["w"], P["h"]
    dx0, dw, dh = P["diff_x0"], P["diff_w"], P["diff_h"]
    dx1 = dx0 + dw
    ny0 = P["ndiff_y0"]
    ny1 = ny0 + dh
    py0 = ny1 + P["gap"]
    py1 = py0 + dh
    rail = P["rail_h"]
    gx0 = P["gate_cx"] - P["gate_l"] // 2
    gx1 = gx0 + P["gate_l"]
    cs = P["cont"]

    rects: List[Any] = []
    rects.append(CL.R(L_NWELL, P["nwell_x0"], py0 - 80, dx1 + 80, py1 + 80, role="nwell"))
    rects.append(CL.R(L_DIFF, dx0, ny0, dx1, ny1, role="diff"))
    rects.append(CL.R(L_DIFF, dx0, py0, dx1, py1, role="diff"))
    rects.append(CL.R(L_POLY, gx0, ny0 - 50, gx1, py1 + 50, role="gate"))
    rects.append(CL.R(L_POLY, gx0 - P["gp_dx0"], ny1 + P["gp_dy0"],
                      gx1 - P["gp_dx1"], ny1 + P["gp_dy1"], role="gate_pad"))

    csl = dx0 + P["cont_l_off"]
    csr = dx1 - P["cont_r_off"]
    for cy in (P["cont_y_n"], P["cont_y_p"]):
        for cx in (csl, csr):
            rects.append(_C(cx, cy, cs, "cont_sd"))
    rects.append(_C(P["cont_gate_cx"], ny1 + P["cont_gate_dy"], cs, "cont_gate"))

    sw = P["strap_w"]

    def X(cx):
        return int(round(cx - sw / 2.0))

    rects.append(CL.R(L_M1, 0, 0, w, rail, role="rail"))
    rects.append(CL.R(L_M1, 0, h - rail, w, h, role="rail"))
    rects.append(CL.R(L_M1, X(csl), rail, X(csl) + sw, ny0 + P["strap_vss_h"], role="strap"))
    rects.append(CL.R(L_M1, X(csr), ny0 + P["my_y0"], X(csr) + sw, P["my_y1"], role="strap"))
    rects.append(CL.R(L_M1, P["pin_a"][0], P["pin_a"][1],
                      P["pin_a"][0] + P["pad"], P["pin_a"][1] + P["pad"], role="pin"))
    rects.append(CL.R(L_M1, P["strap_a"][0], P["strap_a"][1],
                      P["strap_a"][0] + P["strap_a_w"],
                      P["strap_a"][1] + P["strap_a_h"], role="strap"))
    rects.append(CL.R(L_M1, X(csl), py0 + P["strap_vdd_y0"], X(csl) + sw, h - rail, role="strap"))
    rects.append(CL.R(L_M1, P["pin_y"][0], P["pin_y"][1],
                      P["pin_y"][0] + P["pad"], P["pin_y"][1] + P["pad"], role="pin"))

    pins = {
        "VDD": CL.R(L_M1, 0, h - rail, w, h, net="VDD"),
        "VSS": CL.R(L_M1, 0, 0, w, rail, net="VSS"),
        "A": CL.R(L_M1, P["pin_a"][0], P["pin_a"][1],
                  P["pin_a"][0] + P["pad"], P["pin_a"][1] + P["pad"], net="A"),
        "Y": CL.R(L_M1, P["pin_y"][0], P["pin_y"][1],
                  P["pin_y"][0] + P["pad"], P["pin_y"][1] + P["pad"], net="Y"),
    }
    devs = [("pmos", dh, P["gate_l"], "A", "Y", "VDD"),
            ("nmos", dh, P["gate_l"], "A", "VSS", "Y")]
    return CL.Cell("INV_X1", w, h, rects, pins, devs)


# ─────────────────────────────────────────────────────────────────────────────
# ② 模板：nand2 族（**只对 n=2 成立**，见模块头「硬约束一」）
# ─────────────────────────────────────────────────────────────────────────────
def gen_nand2(P: Dict[str, Any]):
    """2 输入 NAND：2 串联 NMOS（两端 cont）+ 2 并联 PMOS（3 cont）。"""
    w, h = P["w"], P["h"]
    dx0, dw, dh = P["diff_x0"], P["diff_w"], P["diff_h"]
    dx1 = dx0 + dw
    ny0 = P["ndiff_y0"]
    ny1 = ny0 + dh
    py0 = ny1 + P["gap"]
    py1 = py0 + dh
    rail = P["rail_h"]
    gl = P["gate_l"]
    cs = P["cont"]

    gx = [(P["gate0"] + P["gate_pitch"] * i, P["gate0"] + P["gate_pitch"] * i + gl)
          for i in range(2)]

    rects: List[Any] = []
    rects.append(CL.R(L_M1, 0, 0, w, rail, role="rail"))
    rects.append(CL.R(L_M1, 0, h - rail, w, h, role="rail"))
    rects.append(CL.R(L_NWELL, P["nwell_x0"], py0 - 80, dx1 + 80, py1 + 80, role="nwell"))
    rects.append(CL.R(L_DIFF, dx0, ny0, dx1, ny1, role="diff"))
    rects.append(CL.R(L_DIFF, dx0, py0, dx1, py1, role="diff"))
    for (g0, g1) in gx:
        rects.append(CL.R(L_POLY, g0, ny0 - 50, g1, py1 + 10, role="gate"))
    for (g0, g1), (px0, px1) in zip(gx, P["gate_pads"]):
        rects.append(CL.R(L_POLY, px0, P["gp_y0"], px1, P["gp_y1"], role="gate_pad"))

    nm = (P["cont_n_x0"], P["cont_n_x1"])
    for cx in nm:
        rects.append(_C(cx, P["cont_y_n"], cs, "cont_sd"))
    for cx in P["cont_p_x"]:
        rects.append(_C(cx, P["cont_y_p"], cs, "cont_sd"))
    for cx in P["cont_gate_x"]:
        rects.append(_C(cx, P["cont_gate_y"], cs, "cont_gate"))

    sw = P["strap_w"]

    def X(cx):
        return int(round(cx - sw / 2.0))

    rects.append(CL.R(L_M1, X(nm[0]), rail, X(nm[0]) + sw, P["strap_vss_y1"], role="strap"))
    rects.append(CL.R(L_M1, X(nm[1]), P["my_y0"], X(nm[1]) + sw, P["my_y1"], role="strap"))
    for cx in P["vdd_cont_x"]:
        rects.append(CL.R(L_M1, X(cx), P["strap_vdd_y0"], X(cx) + sw, h - rail, role="strap"))
    for (px, py) in P["pins_in_xy"]:
        rects.append(CL.R(L_M1, px, py, px + P["pad"], py + P["pad"], role="pin"))
    for (bx, by, bw, bh) in P["gate_bridges"]:
        rects.append(CL.R(L_M1, bx, by, bx + bw, by + bh, role="strap"))
    rects.append(CL.R(L_M1, X(nm[0]), P["strap_yl_y0"], X(nm[0]) + sw, P["strap_yl_y1"],
                      role="strap"))
    rects.append(CL.R(L_M1, X(nm[0]), P["y_h_y0"], X(nm[1]) + sw,
                      P["y_h_y0"] + P["y_h_h"], role="strap"))
    yx, yy = P["pin_y_xy"]
    rects.append(CL.R(L_M1, yx, yy, yx + P["pad"], yy + P["pad"], role="pin"))

    pins = {"VDD": CL.R(L_M1, 0, h - rail, w, h, net="VDD"),
            "VSS": CL.R(L_M1, 0, 0, w, rail, net="VSS")}
    for nm_, (px, py) in zip(P["in_names"], P["pins_in_xy"]):
        pins[nm_] = CL.R(L_M1, px, py, px + P["pad"], py + P["pad"], net=nm_)
    pins["Y"] = CL.R(L_M1, yx, yy, yx + P["pad"], yy + P["pad"], net="Y")

    devs = [("pmos", dh, gl, "A", "Y", "VDD"),
            ("pmos", dh, gl, "B", "VDD", "Y"),
            ("nmos", dh, gl, "A", "VSS", "n1"),
            ("nmos", dh, gl, "B", "n1", "Y")]
    return CL.Cell("NAND2_X1", w, h, rects, pins, devs)


TEMPLATES = {"inv": gen_inv, "nand2": gen_nand2}

#: 校准表 = **数据**（值取自手写版；每个数的来历是"手写折中"，不是"从规则推出"）
PARAMS: Dict[str, Dict[str, Any]] = {
    "INV_X1": dict(
        family="inv",
        w=620, h=1240, rail_h=70,
        diff_x0=110, diff_w=400, diff_h=300,
        ndiff_y0=180, gap=220,
        gate_cx=315, gate_l=50,
        nwell_x0=30,
        gp_dx0=65, gp_dy0=60, gp_dx1=5, gp_dy1=145,
        cont=45, cont_l_off=72.5, cont_r_off=67.5,
        cont_y_n=312.5, cont_y_p=772.5,
        cont_gate_cx=267.5, cont_gate_dy=102.5,
        strap_w=65, strap_vss_h=170, my_y0=100, my_y1=1105,
        strap_vdd_y0=40,
        pin_a=(0, 415), pin_y=(375, 850), pad=240,
        strap_a=(233, 550), strap_a_w=67, strap_a_h=70,
    ),
    "NAND2_X1": dict(
        family="nand2",
        w=980, h=1500, rail_h=70,
        diff_x0=110, diff_w=680, diff_h=300,
        ndiff_y0=180, gap=520,
        gate0=250, gate_pitch=310, gate_l=50,
        nwell_x0=30,
        gate_pads=[(145, 310), (505, 615)], gp_y0=545, gp_y1=660,
        cont=45, cont_y_n=312.5, cont_y_p=1087.5,
        cont_n_x0=172.5, cont_n_x1=722.5,
        cont_p_x=(172.5, 422.5, 722.5),
        cont_gate_x=(260.0, 565.0), cont_gate_y=585.0,
        strap_w=65, strap_vss_y1=345, my_y0=280, my_y1=1120,
        strap_yl_y0=780, strap_yl_y1=1120,
        strap_vdd_y0=1055, vdd_cont_x=(422.5,),
        pins_in_xy=[(0, 410), (360, 410)], pad=240,
        gate_bridges=[(226, 550, 68, 70)],
        y_h_y0=780, y_h_h=70, pin_y_xy=(720, 780),
        in_names=["A", "B"],
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# ③ 构建与校验
# ─────────────────────────────────────────────────────────────────────────────
def build(name: str, params: Optional[Dict[str, Any]] = None):
    """按名字生成 Cell：模板由 `family` 选，几何由参数表给。"""
    p = dict(params or PARAMS[name])
    fam = p["family"]
    if fam not in TEMPLATES:
        raise KeyError("没有 family=%r 的模板（现有 %s）" % (fam, sorted(TEMPLATES)))
    return TEMPLATES[fam](p)


def _sig(cell):
    return sorted((r.layer, r.x0, r.y0, r.x1, r.y1, r.role) for r in cell.rects)


def verify_bitwise(name: str) -> Dict[str, Any]:
    """模板产出 vs 手写版：**逐矩形、逐引脚**比较（DoD② 的机核）。"""
    ref = CL.CELLS[name]()
    got = build(name)
    same_rects = _sig(ref) == _sig(got)
    pk_r = {k: (v.layer, v.x0, v.y0, v.x1, v.y1) for k, v in ref.pins.items()}
    pk_g = {k: (v.layer, v.x0, v.y0, v.x1, v.y1) for k, v in got.pins.items()}
    drc, lvs = CL.run_drc(got), CL.run_lvs(got)
    return {
        "cell": name,
        "n_params": len([k for k in PARAMS[name] if k != "family"]),
        "n_rects": len(ref.rects),
        "same_size": (ref.w, ref.h) == (got.w, got.h),
        "same_rects": same_rects,
        "same_pins": pk_r == pk_g,
        "drc": drc["n"], "lvs": lvs["n"],
        "bitwise": same_rects and pk_r == pk_g,
        "coord_numbers": len(ref.rects) * 4,
    }


def coverage() -> Dict[str, Any]:
    """18 个逻辑单元的**诚实覆盖表**：谁能用模板生成、谁不能、为什么。"""
    from . import dcell as DC

    rows = {}
    for name, c in sorted(DC.CELLS.items()):
        key = name + "_X1"
        if key in PARAMS:
            rows[name] = {"status": "TEMPLATED", "family": PARAMS[key]["family"],
                          "n_tr": c.n_tr, "why": "有校准参数表"}
        elif c.family in ("nand", "nor") and c.n_in >= 3:
            rows[name] = {"status": "NEEDS_INTERDIGIT", "family": c.family, "n_tr": c.n_tr,
                          "why": ("并联 PMOS 在 n≥3 时单条 DIFF 串联画法会产生 (VDD,VDD) "
                                  "退化器件 ⇒ 需叉指拓扑（新模板，非参数）")}
        elif c.family in ("and", "or"):
            rows[name] = {"status": "NEEDS_COMPOSITE", "family": c.family, "n_tr": c.n_tr,
                          "why": "= 基门 + INV 两级，需拼接模板"}
        elif c.family in ("aoi", "oai", "xor", "mux", "seq"):
            rows[name] = {"status": "NEEDS_COMPOSITE", "family": c.family, "n_tr": c.n_tr,
                          "why": "复合/多级拓扑，需独立模板"}
        else:
            rows[name] = {"status": "TODO", "family": c.family, "n_tr": c.n_tr,
                          "why": "尚未建模"}
    n_ok = sum(1 for v in rows.values() if v["status"] == "TEMPLATED")
    return {
        "cells": rows,
        "n_total": len(DC.CELLS),
        "n_templated": n_ok,
        "n_missing": len(DC.CELLS) - n_ok,
        "scope": "DIAGNOSTIC_ONLY",
        "in_blocking": False,
    }


def self_check() -> Dict[str, Any]:
    """自检：正向两条 + **反向构造**（改坏必报）。"""
    problems: List[str] = []

    # ① 正向：两个手写单元逐位复现
    for name in ("INV_X1", "NAND2_X1"):
        v = verify_bitwise(name)
        if not v["bitwise"]:
            problems.append("not_bitwise:%s(rects=%s,pins=%s)"
                            % (name, v["same_rects"], v["same_pins"]))
        if v["drc"] or v["lvs"]:
            problems.append("not_clean:%s(drc=%d,lvs=%d)" % (name, v["drc"], v["lvs"]))

    # ② 反向：把参数改 1nm ⇒ 必须不再逐位（证明比较是真比较，不是恒真）
    bad = dict(PARAMS["INV_X1"])
    bad["w"] = bad["w"] + 1
    ref = CL.CELLS["INV_X1"]()
    got_bad = build("INV_X1", bad)
    if _sig(ref) == _sig(got_bad):
        problems.append("control_1nm_change_silent")

    # ③ 反向：覆盖表不能报满（18/18）—— 报了就是没测
    cov = coverage()
    if cov["n_templated"] == cov["n_total"]:
        problems.append("coverage_all_templated_unexpected")
    if cov["n_templated"] < 1:
        problems.append("coverage_nothing_templated")

    return {
        "ok": not problems,
        "problems": problems,
        "n_templated": cov["n_templated"],
        "n_total": cov["n_total"],
        "dod_status": P5_DISCLOSURE["dod_status"],
    }
