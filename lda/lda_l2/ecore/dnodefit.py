"""Q4 · 单元几何的**可造性判定**：给定节点缩放比例，这颗单元还造得出来吗？

═══════════════════════════════════════════════════════════════════════════════
为什么需要这个模块（Q4 立项前测算的结论，与规划预期**相反**）
───────────────────────────────────────────────────────────────────────────────
规划把 Q4 写成「`device_scale` 接线 ⇒ 改数字 ⇒ 单元几何参数化」。实测发现前提不成立：
**把现有几何按比例乘一个因子，除 `s=1.0` 外每一步都出 DRC 或 LVS 违例**（连 `s=0.98`
都出 2 条 DRC）。所以「接线」不是把 `device_scale` 乘进去，而是**必须按规则重推布局**
（= 规划里的 P5 模板化）。本模块先把这条边界钉死，并给出可机核的量。

═══════════════════════════════════════════════════════════════════════════════
三条实测结论（不是估计）
───────────────────────────────────────────────────────────────────────────────
① **按比例缩放不成立**：`s ∈ {0.98, 0.95, 0.90, 0.85, 0.80, 0.70, 0.60}` 全部违例。
   机制不是「缩太多」——`s=0.98` 就红。根因是**整数取整破坏了 1nm 级的下限**：
   规则值 `poly_s=120` 缩成 117 后，原坐标恰好在 120 处的间距变成 118 ⇒ 差 2nm 违规。
   ⇒ 「缩放」不是连续操作，`scale` 不是可用旋钮。

② **引脚 pad 不随器件缩**（金属有工艺最小尺寸），于是**单元宽度有硬下限**：
   `pad 240 + 接入点间距 342 + pad/2` ⇒ `W_floor = 240 + 342 = 582 nm`。
   现有 `INV_X1` 宽 620 nm ⇒ 宽度**最多缩 6.1%**。
   ⇒ 即使将来按规则重画，`device_scale=0.6` 的面积收益天花板也远不到 ×0.36
     （名义 ×0.36 是「宽高都缩 40%」，实际宽度只能缩 6%）。

③ **器件层与金属层是两套规则**：`dcells.RULES` 的 `m1_w=60nm`（单元内部 M1）
   与 `dnode.DEMO45.w_min=240nm`（布线层 M3，见 `ddetail.W_ROUTE`）**不同层、不同套**，
   不可互相替代；`m1_*` 不随器件缩，`diff_*/poly_*/cont_*` 才随器件缩。

═══════════════════════════════════════════════════════════════════════════════
本模块**不**做什么
───────────────────────────────────────────────────────────────────────────────
· 不产出「可造的新版图」—— 那是 P5（按 family 模板重画）。
· 不宣称任何比例是「工艺极限」—— 测的是**当前几何 + 当前规则集**。
· 不改任何产品数字：`CELLS` / 主链 9 数一位不动。
"""

from typing import Any, Dict, List, Optional, Tuple

from . import dcells as CL

L_DIFF, L_POLY, L_CONT, L_M1, L_NWELL = 20, 21, 22, 23, 19

#: 随**器件**尺寸缩的规则（沟道/有源/多晶硅/接触孔/阱包围）
DEVICE_RULES: Tuple[str, ...] = (
    "diff_w", "diff_s", "diff_a",
    "poly_w", "poly_s", "poly_a",
    "cont_w", "cont_s", "cont_enc_diff", "cont_enc_poly",
    "cont_enc_m1", "gate_cont", "nwell_enc",
)

#: **不随**器件缩的规则（金属工艺下限：线宽/间距/面积由金属层决定）
#: 🔴 这不是「懒得缩」，是物理：金属最小线宽由该层的光刻/刻蚀能力定，与器件沟道长度
#:   不同步。本仓没有第二套 M1 工艺数据 ⇒ 保持绝对量并在此登记（不静默）。
METAL_RULES: Tuple[str, ...] = ("m1_w", "m1_s", "m1_a")

#: 引脚 pad 边长（nm）：`PINS_V2_NOTE` 定的 240（要落 VIA1 0.20 + 单边包围 0.02×2）
PAD_NM = 240
#: 两个**不同网**引脚接入点之间的最小间距（nm）：0.242 焊盘 + 0.10 间距 ⇒ 0.342
ACCESS_GAP_NM = 342

#: 缩放扫描网格（门禁与 `max_feasible_scale` 共用；不写死"答案"，只写扫描点）
SCALE_GRID: Tuple[float, ...] = (0.98, 0.95, 0.90, 0.85, 0.80, 0.70, 0.60)

Q4_DISCLOSURE = {
    "claimable": False,
    "scope": "DIAGNOSTIC_ONLY",
    "in_blocking": False,
    "what": ("给定缩放比例 s，判定「把现有单元几何按 s 缩放后是否仍可造」"
             "（DRC 0 且 LVS 0），并给出宽度硬下限"),
    "verdict": "按比例缩放**不成立**（除 s=1.0）；真缩必须按规则重推布局（= P5）",
    "not_claimed": (
        "① 不产出可造的新版图；② 不宣称任何 s 是工艺极限；"
        "③ 只测当前几何 + 当前规则集，换库/换规则需重测"),
    "unit_note": ("nm 整数坐标 ⇒ 缩放必须取整 ⇒ 1~2nm 的间距损失足以违反下限。"
                  "这就是 s=0.98 也红的原因，不是「缩得不够少」。"),
}


# ─────────────────────────────────────────────────────────────────────────────
# ① 规则派生：器件类缩、金属类不动
# ─────────────────────────────────────────────────────────────────────────────
def scale_rules(scale: float, base: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """派生缩放后的规则集：**只有 `DEVICE_RULES` 跟着缩**，`METAL_RULES` 保持绝对量。

    取整用 `max(1, round(...))`：规则不能变成 0（否则「零宽金属」会被判合法）。
    """
    src = dict(CL.RULES if base is None else base)
    out = dict(src)
    s = float(scale)
    for k in DEVICE_RULES:
        if k in out:
            out[k] = max(1, int(round(src[k] * s)))
    return out


def metal_rules_unscaled(scale: float) -> bool:
    """缩放是否**真的**没动金属规则（判据用的自证，不靠注释）。"""
    a, b = CL.RULES, scale_rules(scale)
    return all(a[k] == b[k] for k in METAL_RULES if k in a)


# ─────────────────────────────────────────────────────────────────────────────
# ② 几何缩放
# ─────────────────────────────────────────────────────────────────────────────
def _scale_rect(r, s: float, keep_metal_size: bool):
    """缩放一个矩形。`keep_metal_size` 时 M1 只缩**中心位置**、保尺寸。

    🔴 保尺寸的代价必须说清：M1 图形相对缩小的器件**变大** ⇒ 覆盖关系变化 ⇒
    `s<1` 时 LVS 会先于 DRC 报错（实测 `s=0.80` 起 LVS 3~4 条）。这不是实现缺陷，
    是「金属不能跟着缩」这一物理事实的直接后果。
    """
    if keep_metal_size and r.layer == L_M1:
        cx, cy = r.cx * s, r.cy * s
        w, h = r.w, r.h
        x0, y0 = int(round(cx - w / 2.0)), int(round(cy - h / 2.0))
    else:
        x0, y0 = int(round(r.x0 * s)), int(round(r.y0 * s))
        w, h = int(round(r.w * s)), int(round(r.h * s))
    return CL.R(layer=r.layer, x0=x0, y0=y0, x1=x0 + w, y1=y0 + h,
                net=r.net, role=r.role)


def scale_cell(cell, scale: float, keep_metal_size: bool = True):
    """把一颗单元按 `scale` 几何缩放，返回**新** `Cell`（不改原对象）。

    `scale == 1.0` 时**返回等价几何**（判据要求与 `CELLS[...]()` 逐位相同）。
    """
    s = float(scale)
    rects = [_scale_rect(r, s, keep_metal_size) for r in cell.rects]
    pins = {}
    for k, r in cell.pins.items():
        nr = _scale_rect(r, s, keep_metal_size)
        pins[k] = CL.R(layer=nr.layer, x0=nr.x0, y0=nr.y0, x1=nr.x1, y1=nr.y1,
                       net=r.net, role=nr.role)
    devs = []
    for d in cell.devices_expected:
        kind, w_dev, l_dev, g, a, b = d
        devs.append((kind, int(round(w_dev * s)), int(round(l_dev * s)), g, a, b))
    return CL.Cell(cell.name, int(round(cell.w * s)), int(round(cell.h * s)),
                   rects, pins, devs, labels={})


# ─────────────────────────────────────────────────────────────────────────────
# ③ 可造性判定
# ─────────────────────────────────────────────────────────────────────────────
def feasibility(cell, scale: float, keep_metal_size: bool = True) -> Dict[str, Any]:
    """判定 `scale` 下该单元是否仍可造：**DRC 0 且 LVS 0**。

    复用 `dcells.run_drc(cell, rules=)` / `dcells.run_lvs(cell)` —— **不写第二套检查器**
    （本仓红线：两份真源必然漂移）。
    """
    s = float(scale)
    if s == 1.0:
        c, rr = cell, dict(CL.RULES)
    else:
        c, rr = scale_cell(cell, s, keep_metal_size), scale_rules(s)
    drc = CL.run_drc(c, rules=rr)
    lvs = CL.run_lvs(c)
    kinds: Dict[str, int] = {}
    for v in drc.get("violations", []):
        kinds[v[0]] = kinds.get(v[0], 0) + 1
    return {
        "cell": cell.name,
        "scale": s,
        "w_um": c.w / 1000.0,
        "h_um": c.h / 1000.0,
        "area_um2": c.area_um2,
        "area_ratio": (c.area_um2 / cell.area_um2) if cell.area_um2 else None,
        "drc": drc["n"],
        "lvs": lvs["n"],
        "drc_kinds": kinds,
        "metal_rules_unscaled": metal_rules_unscaled(s) if s != 1.0 else True,
        "feasible": drc["n"] == 0 and lvs["n"] == 0,
    }


def scan(cell, grid: Tuple[float, ...] = SCALE_GRID,
         keep_metal_size: bool = True) -> List[Dict[str, Any]]:
    """按给定网格逐点判定（**含 s=1.0 基线**，第一行永远是基线）。"""
    rows = [feasibility(cell, 1.0, keep_metal_size)]
    for s in grid:
        rows.append(feasibility(cell, s, keep_metal_size))
    return rows


def max_feasible_scale(cell, grid: Tuple[float, ...] = SCALE_GRID,
                       keep_metal_size: bool = True) -> float:
    """在网格上找**最大的可造比例**（不含 1.0）。找不到 ⇒ 返回 1.0（= 不可缩）。

    🔴 这是**网格上的**最大可造值，不是解析下界；返回值必须与 `grid` 一起报，
    否则「最大 0.98」与「最大 1.0」读起来一样危险。
    """
    best = 1.0
    for s in sorted(grid, reverse=True):
        if feasibility(cell, s, keep_metal_size)["feasible"]:
            return s
    return best


def width_floor_nm(pad_nm: int = None, access_gap_nm: int = None,
                   node=None) -> int:
    """单元**宽度**的硬下限（nm）：两个异网 pad 并排所需的最小宽度。

    `pad/2 + access_gap + pad/2 = pad + access_gap`（两个 pad 各自半个伸出边界）。

    🔴 **两条口径要分开**（否则会把 2nm 的差读成错）：
      · 不传 `node` ⇒ `pad=240`、`access=342`。342 来自 `PINS_V2_NOTE`：
        M3 **接入焊盘 0.242** + 异网间距 0.10。注意 0.242 ≠ M1 pin pad 的 0.240，
        两者是**不同层的两个量**（差 2nm），既有几何以此为锚，本模块不改。
      · 传 `node` ⇒ 按节点派生：`pad = node.pad`（via+2·enc）、
        `access = node.pad + node.s_min`（同层间距随节点缩）。
        DEMO45 得 240+340=580（与 582 差 2nm，即上面那 2nm），DEMO28 得 70+140=210。
    """
    if node is not None:
        p = float(node.pad)
        return int(round(p + (p + float(node.s_min))))
    p = PAD_NM if pad_nm is None else int(pad_nm)
    a = ACCESS_GAP_NM if access_gap_nm is None else int(access_gap_nm)
    return int(p + a)


def width_headroom(cell, pad_nm: int = PAD_NM, node=None) -> Dict[str, Any]:
    """现有宽度相对下限还有多少余量 ⇒ **面积收益的天花板**（宽度只缩得动这么多）。

    传 `node` 时下限按节点派生（见 `width_floor_nm`）—— 这是「换节点」的真实约束：
    节点金属更细 ⇒ 下限更低 ⇒ 同一颗单元的相对余量更大。但它**不**意味着单元能造，
    因为几何仍是 DEMO45 的（`feasibility` 会给出真正答案）。
    """
    floor = width_floor_nm(pad_nm, node=node)
    w = int(cell.w)
    return {
        "cell": cell.name,
        "w_nm": w,
        "w_floor_nm": floor,
        "node": (getattr(node, "name", None) if node is not None else None),
        "headroom_nm": w - floor,
        "max_width_scale": (floor / w) if w else None,
        "max_width_saving_pct": ((w - floor) / w * 100.0) if w else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ④ 自检（正向 + 反向构造：每条规则都要能"改坏必红"）
# ─────────────────────────────────────────────────────────────────────────────
def self_check(verbose: bool = False) -> Dict[str, Any]:
    """自检：正向结论一条 + 每条断言的**反向构造**。只测正向 = 没测。"""
    problems: List[str] = []
    inv = CL.CELLS["INV_X1"]()

    # ① 正向：s=1.0 必须与产品几何逐位相同
    c1 = scale_cell(inv, 1.0)
    if (c1.w, c1.h) != (inv.w, inv.h):
        problems.append("scale1_wh_changed:%r_vs_%r" % ((c1.w, c1.h), (inv.w, inv.h)))
    if [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in c1.rects] != \
            [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in inv.rects]:
        problems.append("scale1_rects_changed")
    if not feasibility(inv, 1.0)["feasible"]:
        problems.append("baseline_not_feasible")

    # ② 正向：金属规则不随缩（且器件规则**确实**缩了 —— 否则是"没缩"冒充"只缩器件"）
    rr = scale_rules(0.6)
    if not metal_rules_unscaled(0.6):
        problems.append("metal_rules_scaled")
    if rr["poly_w"] == CL.RULES["poly_w"]:
        problems.append("device_rules_not_scaled")

    # ③ 反向：声称"可缩"必须能被违例反驳 —— 强行把 s=0.6 判为可造就要报
    f06 = feasibility(inv, 0.6)
    if f06["feasible"]:
        problems.append("s06_feasible_unexpected:%r" % (f06,))
    if f06["drc"] == 0 and f06["lvs"] == 0:
        problems.append("s06_zero_both_but_marked_infeasible")

    # ④ 反向：`max_feasible_scale` 不能恒返回 1.0（换个"本身就可缩"的假单元应给出 <1）
    #    构造一颗**极小且规则宽松**的单元：器件与 pad 同尺寸 ⇒ 缩 0.6 仍合法
    tiny = CL.Cell("TINY", 600, 600,
                   [CL.R(L_M1, 0, 0, 600, 600, role="pin")],
                   {"A": CL.R(L_M1, 0, 0, 600, 600, net="A")}, [])
    if max_feasible_scale(tiny, (0.6,)) != 0.6:
        problems.append("max_feasible_not_detecting_scalable_cell")

    # ⑤ 反向：`width_floor_nm` 必须由参数决定（改 pad 就要变）
    if width_floor_nm() == width_floor_nm(pad_nm=100):
        problems.append("width_floor_ignores_pad")

    return {
        "ok": not problems,
        "problems": problems,
        "n_scales": len(SCALE_GRID),
        "width_floor_nm": width_floor_nm(),
        "verdict": Q4_DISCLOSURE["verdict"],
    }
