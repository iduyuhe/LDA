"""E55 · **单元内部图形接入 DRC** —— 让「短路」不再被当成「同网」。

═══════════════════════════════════════════════════════════════════════════════
为什么必须有这一步（E54 留下的唯一结构性盲区）
───────────────────────────────────────────────────────────────────────────────
E54 把 DFF 画出来了：单看 DRC 0 / 双射 LVS 0 / 面积 2.5000µm²。但它**接不进布线**，
原因不是「布线器不会连引脚」，而是：

    `dcells.run_drc(cell)` 只看**一颗单元内部**；
    `dpnr.route_block(...)` 只看**走线自己**；
    两者之间（单元↔单元、单元↔走线）**没有任何检查器**。

更糟的是旧口径下的**反向失效**：同层间距规则用「几何连通分量相同 ⇒ 视为同网 ⇒ 跳过」。
于是两条**本不该相接**的走线一旦真的搭上，几何会「正确地把它们并成一个网」——
短路被当成同网，DRC 静默放行。这不是漏检一条，是**判据方向错了**：用「结果」去证明「意图」。

本模块把**意图**单独记一份（`dcells.label_cell` 的网标签），于是两套口径互为对照：
标签不同、几何相连 ⇒ 短路必报。

═══════════════════════════════════════════════════════════════════════════════
可复用 / 可扩展的架构（本模块真正想交付的东西）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **不造第二套检查器**：单元内、单元间、单元↔走线的规则**完全一样**（同层宽/距、
   孔包围、NWELL 包住）。所以这里不新写 DRC，而是把联合场景 **compose 成一个 `Cell`**，
   让已有的 `run_drc` / `extract_devices` 原样覆盖。新增代码只有「平移 + 标签迁移」。
2. 🔴 **规则与节点是参数**：`joint_drc(..., rules=HD.HD_RULES)` 换库只换一个 dict，
   判定器一行不改（E53 的 `run_drc(rules=)` 延续到这里）。
3. 🔴 **网标签是一等公民**：新单元只要按拓扑生成几何，标签由 `label_cell` 自动导出
   （引脚落到的分量用引脚名，其余按几何稳定编号 `#k`），不要求作者手写网表。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何对外引用一起给出）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **只做几何短路/间距**：不建模电阻/电容导致的电学退化，不做串扰、天线、密度、
   OPC、ESD、well-tap。规则集仍是自建 LDA-DEMO28/DEMO45 教科书尺度，**非 foundry PDK**。
2. 🔴 **走线网名 → 引脚标签的映射必须由调用方显式给出**（`net_map`）。不给时按
   「未声明连接即短路」处理 —— 这是**保守**方向，不是漏检方向。
3. 🔴 **单位边界**：`dcells` 内部一律 nm 整数；布线器（`dpnr`/`ddrc_lvs`）一律 µm 浮点。
   `route_tile` 是唯一的换算口（×1000 后 `round`），换算只此一处，防两次真源。
4. 🔴 **不是通用 LVS/DRC**：`run_lvs_pos` 的排序键是全局沟道 x ⇒ `compose` 的 tile
   必须**按 x 升序**给，判据 K3 机核这一点。
"""
from __future__ import annotations

from . import dcells as CL

#: 布线器（µm 浮点）↔ 单元库（nm 整数）的唯一换算口
NM_PER_UM = 1000

#: 走线形状在合成 Cell 里的标签前缀（防止与单元内部网塌成一个）
ROUTE_PREFIX = "rt"


def to_nm(v: float) -> int:
    """µm → nm 整数（**唯一**换算点）。"""
    return int(round(float(v) * NM_PER_UM))


def from_nm(v: int) -> float:
    """nm 整数 → µm（配套 `to_nm`）。"""
    return float(v) / NM_PER_UM


def route_tile(shapes, prefix: str = ROUTE_PREFIX) -> CL.Cell:
    """把布线器产出的 `Shape` 列表（µm 浮点）转成一颗「走线 Cell」（nm 整数）。

    `Shape` 需要 `layer/x0/y0/x1/y1/net` 五个字段（`ddetail.Shape` 即此形）。
    `net` 为空时按几何顺序编号 `<prefix>/#k` —— 空网名 = 未声明连接，
    与单元内任何网都不同 ⇒ 一旦接触就报违例（保守方向）。
    """
    rects: list = []
    labels: dict = {}
    anon = 0
    for s in shapes:
        nm = getattr(s, "net", None)
        if not nm:
            anon += 1
            nm = "#%d" % anon
        # 🔴 `prefix=""` 是合法且有意义的（与单元侧电路网名对齐）；不能退化成 "/n3"
        full = nm if (not prefix or nm.startswith(prefix + "/")) else "%s/%s" % (prefix, nm)
        r = CL.R(int(s.layer), to_nm(s.x0), to_nm(s.y0), to_nm(s.x1), to_nm(s.y1),
                 net=full, role="route")
        rects.append(r)
        labels[CL._geom_key(r)] = full
    w = max((r.x1 for r in rects), default=0)
    h = max((r.y1 for r in rects), default=0)
    return CL.Cell(name="%s_tile" % prefix, w=w, h=h, rects=rects,
                   pins={}, devices_expected=[], labels=labels)


def pin_shapes(cell: CL.Cell, prefix: str = None) -> list:
    """该单元的**引脚矩形**（带网标签）—— 布线器可连的东西只有这些。"""
    out = []
    for pn, pr in cell.pins.items():
        lab = CL._qualify(pn, prefix)
        out.append({"net": lab, "layer": pr.layer,
                    "x0": from_nm(pr.x0), "y0": from_nm(pr.y0),
                    "x1": from_nm(pr.x1), "y1": from_nm(pr.y1)})
    return out


def obstacles(cell: CL.Cell, include_pins: bool = False,
              layers=None) -> list:
    """单元内部**非引脚**图形（nm）—— 布线器必须避让的部分。

    🔴 这是 E54 留下的那句「`cell_shapes` 只带引脚 ⇒ 内部 M2 是盲区」的正面回答：
    不是把内部图形**藏**起来，而是明确交出去当**障碍**。`include_pins=False` 是默认，
    因为引脚是要连的（不是要躲的）；要查「走线有没有压到引脚以外的图形」时用本函数。
    """
    pins = {CL._geom_key(pr) for pr in cell.pins.values()}
    # 🔴 回退到现算：单元 Cell 自带 `labels` 时才用它。HD 库的单元（E53/E54）**不预置**
    # labels（它们是按拓扑生成的，标签是派生量）⇒ 只读 `cell.labels` 会得到一整片 None，
    # 布线器就分不清「要躲」和「可接」（E55 判据 A5 首跑即红，抓的就是这个）。
    lab = cell.labels or CL.label_cell(cell)
    out = []
    # 🔴 遍历 `_shapes` 而不是 `cell.rects`：DIFF 必须按**栅切开的段**给出。
    # 一块 DIFF 被栅切开后各段属于不同网（源/漏/沟道），用整块矩形无法用单一网名表示
    # —— 直接遍历 rects 会让那两块 DIFF 永远没有标签（判据 A5 实测 10/12）。
    for r in CL._shapes(cell):
        if r.layer in CL.NON_SIGNAL_LAYERS:
            continue
        if layers is not None and r.layer not in layers:
            continue
        if not include_pins and CL._geom_key(r) in pins:
            continue
        out.append({"layer": r.layer, "role": r.role,
                    "x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1,
                    "net": lab.get(CL._geom_key(r))})
    return out


def joint_drc(tiles: list, route=None, rules: dict = None, net_map: dict = None,
              global_nets=CL.GLOBAL_NETS, route_prefix: str = ROUTE_PREFIX,
              allow_multi_fragment: bool = False,
              route_offset: tuple = (0, 0)) -> dict:
    """**联合 DRC**：单元实例 + 走线 一次查完（间距 / 短路 / 标签一致性）。

    `tiles = [(cell, dx_nm, dy_nm, prefix[, pin_names]), …]`（按 x 升序，见模块 docstring 第 4 条）。
    `route` = `Shape` 列表（µm）或已建好的走线 `Cell`。
    `route_prefix` = 走线网名前缀。**要与单元侧的网名对齐时传空串** —— 例如
      单元侧用了 `netlist` 的电路网名（`n3`），布线器也用同一套网名（`route_block` 的
      `net_pins` 就是 `gate.out`/`gate.ins[k]`），此时 `route_prefix=""` 才能让
      「接到自己引脚」被判成同网而不是短路。
    `net_map` = 额外的网名重写表（个别工具用别的前缀时兜底）。

    返回 {drc, bridges, labels, n_conflicts, cell, …}：
      · `n_conflicts` = `compose` 写入时抓到的图形位置冲突（完全不同网的图形**完全重合**）；
      · `bridges` = 跨实例意外桥接（不同标签被几何并成一组）。
    """
    R = rules
    tiles = list(tiles)
    if route is not None:
        rt = route if isinstance(route, CL.Cell) else route_tile(route, prefix=route_prefix)
        if net_map:
            new_rects, new_labels = [], {}
            for r in rt.rects:
                tgt = net_map.get(r.net, r.net)
                nr = CL.R(r.layer, r.x0, r.y0, r.x1, r.y1, net=tgt, role=r.role)
                new_rects.append(nr)
                new_labels[CL._geom_key(nr)] = tgt
            rt = CL.Cell(name=rt.name, w=rt.w, h=rt.h, rects=new_rects,
                         pins={}, devices_expected=[], labels=new_labels)
        # 🔴 不能写 `route_prefix or ROUTE_PREFIX`：空串是**有意义的取值**（网名对齐），
        # 而空串是 falsy ⇒ 会被悄悄换回前缀，实测让 14 条「同网接触」全变假短路。
        tiles.append((rt, int(route_offset[0]), int(route_offset[1]), route_prefix))
    cell = CL.compose(tiles, name="JOINT", global_nets=global_nets)
    drc = CL.run_drc(cell, R)
    rep = CL.label_report(cell, global_nets=global_nets,
                          allow_multi_fragment=allow_multi_fragment)
    return {"drc": drc, "n_drc": drc["n"], "bridges": CL.bridges(cell, tiles, global_nets),
            "labels": rep, "n_conflicts": len(cell.conflicts), "cell": cell,
            "n_rects": len(cell.rects), "w_nm": cell.w, "h_nm": cell.h,
            "area_um2": cell.w * cell.h / 1e6}


def place_tiles(pl: dict, netlist=None, limit: int = 0) -> tuple:
    """把 `dpnr.place_real` 的布局结果（µm）转成 `compose` 的 tiles（nm 整数）。

    返回 `(tiles, meta)`，`tiles` **已按 x 升序**（`run_lvs_pos` 的排序键要求，见 K3）。
    `meta` 里带回「单元原点换算的最大偏差」——它是 `µm→nm` 唯一的精度风险点，
    必须被量化而不是假设为零。

    🔴 `netlist`（可选）：给出时**引脚标签改用电路网名**（`Y→gate.out`、`A/B→gate.ins[k]`）。
    这是「真实装配」与「并排摆放」的分界：
      · 不给 ⇒ 每实例加前缀（`u0/Y`），两实例的引脚**永远不同网**，只能查「摆在一起打不打架」；
      · 给   ⇒ `u0.Y` 与 `u1.A` 若在网表里同属一网则**同标签**，才能判「布线连得对不对」。
    """
    insts = list(pl["insts"])
    if limit:
        insts = insts[:limit]
    tiles, worst = [], 0.0
    for inst in insts:
        x_nm, y_nm = to_nm(inst["x0"]), to_nm(inst["y0"])
        worst = max(worst, abs(x_nm / float(NM_PER_UM) - inst["x0"]),
                    abs(y_nm / float(NM_PER_UM) - inst["y0"]))
        pm = None
        if netlist is not None:
            g = inst["gate"]
            pm = {"Y": g.out}
            for k, n in enumerate(list(g.ins)[:2]):
                pm["AB"[k]] = n
        tiles.append((inst["geom"], x_nm, y_nm, inst["name"], pm))
    tiles.sort(key=lambda t: (t[1], t[2]))
    return tiles, {"n_tiles": len(tiles), "max_origin_err_um": worst,
                   "die_w_um": pl.get("die_w_um"), "die_h_um": pl.get("die_h_um"),
                   "netlist_named": netlist is not None}


def row_of(cells: list, gap_nm: int = 0, y_nm: int = 0) -> tuple:
    """把若干单元**按 x 顺序排成一行**，返回 `(tiles, total_w_nm)`。

    这是最常用的一种拼接，单独提出是为了让调用方不必自己算 x —— 但**不做合法性担保**：
    该报的间距/短路仍由 `joint_drc` 抓（本模块不提供「静默摆放」的口子）。
    """
    tiles, x = [], 0
    for k, c in enumerate(cells):
        tiles.append((c, x, y_nm, "u%d" % k))
        x += c.w + int(gap_nm)
    return tiles, (x - int(gap_nm) if cells else 0)
