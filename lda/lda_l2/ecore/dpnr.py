"""B 系列接入 P&R 主链（D-238）—— 把 B1/B2/B3 从演示用例接进 E35/E36 的主链。

═══════════════════════════════════════════════════════════════════════════════
主链原来缺什么（这是本模块存在的唯一理由）
───────────────────────────────────────────────────────────────────────────────
E35/E36 的主链是 `dplac.place → ddetail.detail_route → ddetail.real_cell_geom →
ddrc_lvs.run_drc/run_lvs → dmacro.build_ip`，三处结构性简化：

 ① **单元几何是索引形的**：`real_cell_geom` 每颗单元只画「0.06µm 有源标记 + 中心 M1 焊垫 +
    叠放通孔」。真实 DIFF/POLY/CONT/NWELL 一个都没有 ⇒ DRC 只能验金属，LVS 无从谈起。
 ② **引脚被塌缩到单元中心**：`_net_pins` 把同一单元的所有引脚都记成 `(cx, cy)` 一个点
    ⇒ 多输入单元（NAND2 的 A/B）在网表层面就**不可区分**，布线连的是「单元中心」而不是引脚。
 ③ **布线没有容量上界**：`detail_route` 的 H 段压在引脚 y、V 段压在引脚 x，同层金属在共享
    行/列上大量重叠 ⇒ baseline DRC **204,320**。`track_route`（E37）加了区间着色，但引脚仍在
    中心、且**轨道数不受通道高度约束**，所以只能消主段重叠、无法清零。

本模块把这三处换成 B 系列的实现：

 | 主链原实现 | 本模块 | 来自 |
 |---|---|---|
 | `real_cell_geom` 索引形 | `dcells` 真几何（DIFF/POLY/CONT/M1/NWELL，整数 nm） | **B1 / E40** |
 | `_net_pins` 单元中心 | 真引脚矩形中心（A/B 左边界、Y 内部 strap），逐引脚独立 | **B2 / E41** |
 | `detail_route` 无容量 | 按**通道**分配 M3 轨道 + M4 列分配 + **T < d 即布不通**（容量律） | **B2 + A2 / E41/E39** |
 | `dextract` 标量 R/C | 分布式 RC 网络（SPEF 可逆） | **B3+ / E43** |
 | 无电源网 | M3/M4 网格全域 IR 求解 | **B3+ / E44** |

═══════════════════════════════════════════════════════════════════════════════
路由模型（说清楚，因为它决定了结论的适用范围）
───────────────────────────────────────────────────────────────────────────────
· **单元行**：行高取所用到单元类型的最大值（`dcells` 的 INV=1.24µm、NAND2=1.50µm **不等高**，
  真实 std-cell 是等高行 ⇒ 本模型取 max 并底对齐，属已知几何简化）。
· **单元间距**：`CELL_GAP_UM = 0.36`（= 轨道间距）。真实 std-cell 行内紧邻、pin access 靠 M2
  局部绕行；本模型没有 M2 细节 ⇒ **用间隙换 pin 可达性**（这是为了「能布通」付的面积代价）。
· **每网一条 M3 trunk**（在离其引脚中位最近的通道内）＋ 每个引脚一条 M4 竖直到 trunk。
  trunk 用**区间着色**在通道内分配轨道（同轨不同网必须隔开 S_MIN）；M4 竖直用**列分配器**
  在离散列网格上做 y-区间着色 ⇒ 两条不同网的 M4 在 y 上永不重叠（强于 DRC 要求）。
· **容量律**：通道只有 `T = floor((CH−W)/PITCH)+1` 条轨道，所需 `d` 由 `dmtrack.channel_density`
  给出；**T < d ⇒ 该通道的网如实报「布不通」**，不偷偷叠轨。
· 引脚接入：M1 焊垫（单元自带）→ VIA1 → M2 焊盘 → VIA2 → M3 焊盘 → M4 竖段。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何引用一起给）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **这是主链的子块接入，不是 1340 单元全 IP**：`dcells` 只有 2 种单元（INV/NAND2），
   全 IP 的 1340 单元里还有 DFF 等未建模类型；且本模块的 DRC 是 O(n²) 逐对比较，
   规模上限受 Python 限制（实测边界见门禁 C3）。**不宣称全 IP 可跑**。
2. 🔴 **不是通用路由器**：每网一条 trunk 的星形拓扑（不是 maze/negotiated router），
   不做线长优化、不做 rip-up、不做层分配搜索。trunk 选通道只按引脚中位，不避让拥塞。
3. 🔴 **M2 只画焊盘**：M1→M3 的 M2 段仅作为 pin access 焊盘存在，**不画 M2 走线**
   （沿用 E36/`ddrc_lvs.BRIDGE_PRESENT` 的既有约定）。
4. 🔴 **行高不等高**：INV 1.24 / NAND2 1.50 取 max=1.50 底对齐 ⇒ 每颗 INV 上方留 0.26µm 空行。
5. 🔴 **端口网不布**：只布 gate-to-gate 内部网；带端口（primary I/O）的网如实计入「未布」，
   因为块边界的 pad/IO 环不在本模型内。
6. 🔴 规则集仍是 LDA-DEMO45（自建教科书尺度），非任何 foundry PDK。
7. 🔴 `claimable=False`，**净增 0 锚**（整数几何 + 组合分配 ⇒ resid≡0）⇒ 门禁形态（E45）。
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import dcells as CL
from . import dcroute as DR
from . import ddetail as DD
from . import ddrc_lvs as DL
from . import dmtrack as MT
from .ddetail import Shape

# ═══════════════════════════════════════════════════════════════════════════
# 几何常量（全部显式）
# ═══════════════════════════════════════════════════════════════════════════
#: 主链网表的单元名 → `dcells` 里已建模的类型（**显式映射**，不猜）
#: 🔴 DFF 未建模（`dcells` 只有 INV/NAND2）⇒ 如实跳过并计数，不装作能布。
CELL_MAP = {"INV": "INV_X1", "NAND2": "NAND2_X1"}

CELL_GAP_UM = 0.36        # 单元间距 = 轨道间距（换 pin 可达性，见披露 ②）
CH_UM = 1.60              # 行间通道高度
PITCH = DD.TRACK_PITCH    # 0.36
EXT = DD.VIA / 2.0 + DL.ENC   # 0.12：金属须超出孔边 ENC
W = DD.W_ROUTE            # 0.24


def row_height_um() -> float:
    """行高 = 所用到单元类型的最大高度（INV 1.24 / NAND2 1.50 ⇒ 1.50）。"""
    return max(f().h for f in CL.CELLS.values()) / 1000.0


def tracks_in_channel(ch_um: float = CH_UM) -> int:
    """通道可容纳的 M3 轨道数 `T = floor((CH−W)/pitch)+1`。"""
    return max(1, int((ch_um - W) // PITCH) + 1)


# ═══════════════════════════════════════════════════════════════════════════
# ① 布局（用 B1 的真实单元宽度，不用面积模型反推）
# ═══════════════════════════════════════════════════════════════════════════
def place_real(nl, max_cells: int = 32, cols: int = None) -> dict:
    """行式布局：单元按 `dcells` 真实宽度排进行，行高 = 1.50µm。

    只用 `dcells` 里有的单元类型；遇到未建模类型（如 DFF）**跳过并计数**（披露 ①）。
    """
    h_row = row_height_um()
    row_pitch = h_row + CH_UM
    picked = []
    skipped = defaultdict(int)
    for g in nl.gates:
        kind = CELL_MAP.get(g.cell)
        if kind is None or kind not in CL.CELLS:
            skipped[g.cell] += 1
            continue
        if len(picked) >= max_cells:
            break
        picked.append((g, kind))
    if not picked:
        raise ValueError("没有可布局的单元（dcells 未建模任何出现的类型）")

    cols = cols or int(math.ceil(math.sqrt(len(picked))))
    rows = int(math.ceil(len(picked) / cols))
    insts = []
    pitch_x = max(f().w for f in CL.CELLS.values()) / 1000.0 + CELL_GAP_UM
    for k, (g, kind) in enumerate(picked):
        r, c = divmod(k, cols)
        cell = CL.CELLS[kind]()
        insts.append({"name": g.name, "cell": g.cell, "kind": kind, "gate": g,
                      "r": r, "c": c, "x0": c * pitch_x, "y0": r * row_pitch,
                      "w": cell.w / 1000.0, "h": cell.h / 1000.0, "geom": cell})

    die_w = max((i["x0"] + i["w"] for i in insts)) + CELL_GAP_UM
    die_h = rows * row_pitch - CH_UM
    return {"insts": insts, "rows": rows, "cols": cols, "die_w_um": die_w,
            "pitch_x_um": pitch_x,
            "die_h_um": die_h, "h_row_um": h_row, "row_pitch_um": row_pitch,
            "ch_um": CH_UM, "t_tracks": tracks_in_channel(CH_UM),
            "skipped_cells": dict(skipped), "n_picked": len(picked),
            "n_gates_total": len(nl.gates)}


def channel_y(pl: dict, r: int) -> float:
    """通道 r（行 r 与行 r+1 之间）的基准 y（第一条轨道的内边）。"""
    return r * pl["row_pitch_um"] + pl["h_row_um"]


# ═══════════════════════════════════════════════════════════════════════════
# ② 单元实例几何（B1 真几何，平移到绝对坐标）
# ═══════════════════════════════════════════════════════════════════════════
def cell_shapes(inst: dict) -> list:
    """把某实例的 `dcells` 几何（nm 整数）平移到 die 绝对坐标（µm）。"""
    out = []
    dx, dy = inst["x0"], inst["y0"]
    for r in inst["geom"].rects:
        out.append(Shape(r.layer, dx + r.x0 / 1000.0, dy + r.y0 / 1000.0,
                         dx + r.x1 / 1000.0, dy + r.y1 / 1000.0,
                         net=None, kind=("pin" if r.role.startswith("p") else "metal"),
                         cell=inst["name"]))
    return out


def pin_points(inst: dict) -> list:
    """该实例所有**信号引脚**的绝对坐标（真引脚矩形中心）—— 与主链的「单元中心」不同。"""
    out = []
    for pname, r in inst["geom"].pins.items():
        if pname in ("VDD", "VSS"):
            continue
        cx = inst["x0"] + (r.x0 + r.x1) / 2000.0
        cy = inst["y0"] + (r.y0 + r.y1) / 2000.0
        out.append({"pin": pname, "x": cx, "y": cy,
                    "rect": (inst["x0"] + r.x0 / 1000.0, inst["y0"] + r.y0 / 1000.0,
                             inst["x0"] + r.x1 / 1000.0, inst["y0"] + r.y1 / 1000.0)})
    return out


def net_pins(pl: dict) -> dict:
    """net → [(inst_name, pin, x, y)]，**逐引脚独立**（不塌缩到单元中心）。"""
    pins = defaultdict(list)
    for inst in pl["insts"]:
        g = inst["gate"]
        names = ["A", "B"] if inst["kind"] == "NAND2_X1" else ["A"]
        idx = {n: k for k, n in enumerate(names)}
        for p in pin_access_points(inst):
            if p["pin"] == "Y":
                pins[g.out].append((inst["name"], "Y", p["x"], p["y"]))
            elif p["pin"] in idx:
                k = idx[p["pin"]]
                if k < len(g.ins):
                    pins[g.ins[k]].append((inst["name"], p["pin"], p["x"], p["y"]))
    return dict(pins)


def pin_stub(x: float, y: float, net: str) -> list:
    """引脚接入栈：**M1 pad → VIA1 → M2 pad → V2 → M3 pad**。

    🔴 必须补 M1/M2 焊盘：`dcells` 的 M1 引脚矩形只有 65nm 高（A 引脚 y 550–615），
    装不下 200nm 的 VIA1 ⇒ 直接打孔必 `via_enclosure`。加焊盘是标准做法（pin access pad）。
    🔴 必须走 **V2（M2↔M3）**：原 `VIA_BRIDGE` 只有 M1–M2 与 M3–M4，**没有 M2–M3**
    ⇒ 单元引脚（M1）在几何上根本到不了 M3。本版补 V2 层（v0.9.348）。
    """
    hv = DD.VIA / 2.0
    hp = DD.VIA / 2.0 + DL.ENC + 0.001
    return [
        Shape(DD.L_M1, x - hp, y - hp, x + hp, y + hp, net=net, kind="metal"),
        Shape(DD.L_VIA1, x - hv, y - hv, x + hv, y + hv, net=net, kind="via"),
        Shape(DD.L_M2, x - hp, y - hp, x + hp, y + hp, net=net, kind="metal"),
        Shape(DD.L_V2, x - hv, y - hv, x + hv, y + hv, net=net, kind="via"),
        Shape(DD.L_M3, x - hp, y - hp, x + hp, y + hp, net=net, kind="metal"),
    ]


def pin_access_points(inst: dict, spread: bool = True) -> list:
    """该实例的**引脚接入点**（绝对坐标）。

    `spread=True` 时按「相邻接入点间距 ≥ 轨道 pitch」在**引脚矩形内部**挪点
    （`dcells` 原始引脚位置不足以容纳两条 M4：INV 的 A/Y 只隔 0.269µm、
    NAND2 的 A/B 只隔 0.155µm，而两条 M4 需要 ≥0.34µm）。
    这是**单元侧的必要修补**，不是路由器的自由度 —— 见 `pin_access_conflicts`。
    """
    raw = []
    for p in pin_points(inst):
        raw.append([p["pin"], p["x"], p["y"], p["rect"][0], p["rect"][2]])
    if not spread:
        return [{"pin": r[0], "x": r[1], "y": r[2]} for r in raw]

    raw.sort(key=lambda r: r[3])          # 按引脚矩形左边界排
    placed = []
    prev = None
    for (pn, xc, y, lo, hi) in raw:
        want = lo if prev is None else max(lo, prev + PITCH)
        ok = want <= hi + 1e-9
        if not ok:                        # 引脚矩形装不下 ⇒ 贴右边界，并如实标 infeasible
            want = hi
        placed.append({"pin": pn, "x": round(want, 6), "y": y, "x_pin": xc,
                       "moved_um": round(want - xc, 4), "feasible": ok})
        prev = want
    return placed


def pin_access_conflicts(pl: dict) -> dict:
    """量化 `dcells` **原始**引脚位置的接入冲突（这是本模块查出的单元侧缺陷）。"""
    pairs = []
    per_inst = {}
    for inst in pl["insts"]:
        pts = pin_points(inst)
        sig = [p for p in pts if p["pin"] != "Y"] + [p for p in pts if p["pin"] == "Y"]
        sig = [p for p in pts]
        for i in range(len(sig)):
            for j in range(i + 1, len(sig)):
                a, b = sig[i], sig[j]
                d = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
                if d < PITCH - 1e-9:
                    pairs.append({"inst": inst["name"], "cell": inst["kind"],
                                  "a": a["pin"], "b": b["pin"], "dist_um": round(d, 4)})
        per_inst[inst["name"]] = len(sig)
    worst = min((p["dist_um"] for p in pairs), default=None)
    return {"n_conflicts": len(pairs), "worst_um": worst, "need_um": PITCH,
            "samples": pairs[:6], "n_insts": len(per_inst)}


# ═══════════════════════════════════════════════════════════════════════════
# ③ 路由：trunk（M3，按通道分轨）+ 引脚竖直（M4，按列分配）
# ═══════════════════════════════════════════════════════════════════════════
def _color_intervals(ivs: list, gap: float = 0.0) -> list:
    """区间着色（贪心，确定性）：返回每段被分配的轨道号。

    同轨两段之间必须留 `gap`（= W + S_MIN ⇒ 膨胀 gap/2 再判重叠）。
    """
    order = sorted(range(len(ivs)), key=lambda i: (ivs[i][0], ivs[i][1], i))
    track_end: list = []
    assign = [0] * len(ivs)
    for i in order:
        a, b = ivs[i]
        ia, ib = a - gap / 2.0, b + gap / 2.0
        placed = False
        for t, ends in enumerate(track_end):
            if all(ib <= e0 or ia >= e1 for (e0, e1) in ends):
                ends.append((ia, ib))
                assign[i] = t
                placed = True
                break
        if not placed:
            track_end.append([(ia, ib)])
            assign[i] = len(track_end) - 1
    return assign, len(track_end)


def _alloc_columns(runs: list, x0_grid: float, die_w: float) -> tuple:
    """M4 列分配：离散列网格 + y 区间着色 ⇒ 不同网的 M4 在 y 上永不重叠。

    `runs` = [(net, y_lo, y_hi, x_desired)]，返回 (每段的列 x, 用到的列数, 失败列表)。
    """
    ncol = max(1, int((die_w - W) // PITCH) + 1)
    col_ivs: list = [[] for _ in range(ncol)]     # 每列已占用的 y 区间
    xs = [0.0] * len(runs)
    fail = []
    order = sorted(range(len(runs)), key=lambda i: (runs[i][3], runs[i][1], i))
    for i in order:
        _net, ya, yb, xd = runs[i]
        if yb - ya <= 1e-9:
            xs[i] = xd
            continue
        ia, ib = ya - DL.S_MIN / 2.0, yb + DL.S_MIN / 2.0
        k0 = int(round((xd - x0_grid) / PITCH))
        best = None
        for d in range(0, ncol):
            for k in (k0 + d, k0 - d):
                if k < 0 or k >= ncol:
                    continue
                if all(ib <= e0 or ia >= e1 for (e0, e1) in col_ivs[k]):
                    best = k
                    break
            if best is not None:
                break
        if best is None:
            fail.append(_net)
            xs[i] = xd
            continue
        col_ivs[best].append((ia, ib))
        xs[i] = x0_grid + best * PITCH
    used = sum(1 for c in col_ivs if c)
    return xs, used, fail


def route_block(nl, pl: dict, ch_um: float = None) -> dict:
    """按通道分轨 + 列分配布内部网。返回路由结果与**容量判定**。"""
    ch_um = pl["ch_um"] if ch_um is None else ch_um
    t_cap = tracks_in_channel(ch_um)
    pins = net_pins(pl)
    n_rows = pl["rows"]

    # —— ① 每网选一个通道（离引脚 y 中位最近的通道），约束 trunk 的 x 跨度 ——
    net_ch = {}
    spans = defaultdict(list)      # ch -> [(x0,x1,net)]
    for net, pts in pins.items():
        if len(pts) < 2:
            continue
        ys = [p[3] for p in pts]
        rows = [min(n_rows - 2, max(0, int(y // pl["row_pitch_um"]))) for y in ys]
        ch = min(range(max(1, n_rows - 1)),
                 key=lambda c: abs(c - sum(rows) / len(rows))) if n_rows > 1 else 0
        net_ch[net] = ch
        xs = [p[2] for p in pts]
        spans[ch].append((min(xs), max(xs), net))

    # —— ② 通道容量律：d 由 A2 的区间密度给出，T < d ⇒ 该通道布不通 ——
    ch_info = {}
    track_of = {}
    for ch, ivs in spans.items():
        xs_nm = [(int(round(a * 1000)), int(round(b * 1000))) for (a, b, _n) in ivs]
        d = MT.channel_density(xs_nm) if xs_nm else 0
        ch_info[ch] = {"d": int(d), "t_avail": t_cap, "routable": int(d) <= t_cap,
                       "n_nets": len(ivs)}
        if not ch_info[ch]["routable"]:
            continue
        trk, ntrk = _color_intervals([(a, b) for (a, b, _n) in ivs], gap=DL.S_MIN)
        for (a, b, n), t in zip(ivs, trk):
            track_of[n] = (ch, t)
        ch_info[ch]["tracks_used"] = ntrk

    routed = sorted(track_of)
    unrouted = sorted(n for n in spans_to_nets(spans) if n not in track_of)

    # —— ③ 引脚竖直（M4）：y 从引脚到 trunk，按列分配 ——
    y_of = {}
    for net, (ch, t) in track_of.items():
        y_of[net] = channel_y(pl, ch) + W / 2.0 + t * PITCH

    x0_grid = W / 2.0 + 0.02
    runs = []
    for net in routed:
        yt = y_of[net]
        for (_iname, _p, x, y) in pins[net]:
            runs.append((net, min(y, yt) - EXT, max(y, yt) + EXT, x))
    xs, ncol_used, col_fail = _alloc_columns(runs, x0_grid, pl["die_w_um"])

    # —— ④ 建形：分「引脚接入」与「走线」两类（判据要能分开归因）——
    acc: list = []      # 引脚接入栈（M1/M2/M3 pad + 孔）—— 受**单元引脚几何**限制
    shapes: list = []   # 走线金属（M3 trunk / M4 竖 / 弯角孔与 landing）
    hv = DD.VIA / 2.0
    k = 0
    for net in routed:
        yt = y_of[net]
        cols_net = []
        for (_iname, _p, x, y) in pins[net]:
            cx = xs[k]
            k += 1
            cols_net.append(cx)
            acc += pin_stub(x, y, net)
            if abs(cx - x) > 1e-9:
                # M3 短跳线：引脚 → 列。**只在外端（列侧）延伸 EXT** 以包围孔；
                # 引脚端不延伸（那里由 pin_stub 的 M3 焊盘包围），否则相邻引脚的跳线会互相顶到。
                lo = x if cx > x else cx - EXT
                hi = cx + EXT if cx > x else x
                shapes.append(Shape(DD.L_M3, lo, y - W / 2.0, hi, y + W / 2.0,
                                    net=net, kind="metal"))
            # 列底部：M3 → M4 必须过一个 VIA2（否则 M3 与 M4 在几何上不相连）
            shapes.append(Shape(DD.L_VIA2, cx - hv, y - hv, cx + hv, y + hv,
                                net=net, kind="via"))
            # M4 竖直：列底部 → trunk，两端各延伸 EXT 以包围两端的 VIA2
            shapes.append(Shape(DD.L_M4, cx - W / 2.0, min(y, yt) - EXT,
                                cx + W / 2.0, max(y, yt) + EXT, net=net, kind="metal"))
            # trunk 端：VIA2（trunk 与竖段宽度 0.24 已包围 0.20 孔）
            shapes.append(Shape(DD.L_VIA2, cx - hv, yt - hv, cx + hv, yt + hv,
                                net=net, kind="via"))
        xspan = [p[2] for p in pins[net]] + cols_net
        # trunk 两端各延伸 EXT：否则末端的 VIA2 没有 M3 侧包围（via_enclosure）
        shapes.append(Shape(DD.L_M3, min(xspan) - EXT, yt - W / 2.0,
                            max(xspan) + EXT, yt + W / 2.0, net=net, kind="metal"))

    # 全量 = 接入 + 走线（连通性/端口检查要看全量，DRC 归因要看分开的）
    shapes_all = shapes + acc
    return {"shapes": shapes_all, "shapes_route": shapes, "shapes_access": acc,
            "routed": routed, "unrouted": unrouted,
            "ch_info": ch_info, "t_cap": t_cap, "n_cols_used": ncol_used,
            "col_fail": sorted(set(col_fail)), "track_of": track_of,
            "trunk_y": y_of, "pins": pins, "n_pins": sum(len(v) for v in pins.values())}


def spans_to_nets(spans: dict) -> set:
    out = set()
    for _ch, ivs in spans.items():
        for (_a, _b, n) in ivs:
            out.add(n)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ④ 判据辅助
# ═══════════════════════════════════════════════════════════════════════════
def routing_only(rt: dict) -> list:
    """走线金属（**不含**引脚接入栈）—— 用于把 DRC 归因到「路由器」而非「单元引脚」。"""
    return [s for s in rt["shapes_route"] if s.kind in ("metal", "via", "pin")]


def access_only(rt: dict) -> list:
    return [s for s in rt["shapes_access"] if s.kind in ("metal", "via", "pin")]


def all_routing(rt: dict) -> list:
    return [s for s in rt["shapes"] if s.kind in ("metal", "via", "pin")]


def net_components_rt(rt: dict) -> dict:
    """每网的层感知连通分量数（复用 E36 的 `net_components` 口径）。"""
    return DR.net_components([s for s in rt["shapes"] if s.net])


def cell_drc_lvs(pl: dict) -> dict:
    """逐**单元类型**跑 B1 的 DRC/LVS（平移不变 ⇒ 每类型一次即可）。"""
    out = {}
    for cname in sorted({i["kind"] for i in pl["insts"]}):
        c = CL.CELLS[cname]()
        out[cname] = {"drc": CL.run_drc(c)["n"], "lvs": CL.run_lvs(c)["n"],
                      "area_um2": round(c.area_um2, 6)}
    return out


def route_baseline(nl, pl: dict) -> dict:
    """主链 E36 式的 **L 路由基线**（引脚取单元中心、无轨道分配、无引脚接入栈）。

    与 `route_block` 用**同一网表、同一布局**，只换路由策略 ⇒ 两者 DRC 的差就是
    「真引脚 + 按通道分轨 + 容量律」的净贡献。这是本模块唯一允许的对比口径。
    """
    centers = {i["name"]: (i["x0"] + i["w"] / 2.0, i["y0"] + i["h"] / 2.0)
               for i in pl["insts"]}
    pins = defaultdict(list)
    for inst in pl["insts"]:
        g = inst["gate"]
        cx, cy = centers[inst["name"]]
        pins[g.out].append((inst["name"], "Y", cx, cy))
        for n in g.ins:
            pins[n].append((inst["name"], "A", cx, cy))

    shapes = []
    n_net = 0
    hv = DD.VIA / 2.0
    for net, pts in pins.items():
        if len(pts) < 2:
            continue
        n_net += 1
        xy = [(p[2], p[3]) for p in pts]
        for (a, b) in DD._mst_edges(xy):
            ax, ay = xy[a]
            bx, by = xy[b]
            if abs(ax - bx) > 1e-9:
                shapes.append(Shape(DD.L_M3, min(ax, bx), ay - W / 2.0,
                                    max(ax, bx), ay + W / 2.0, net=net, kind="metal"))
            if abs(ay - by) > 1e-9:
                shapes.append(Shape(DD.L_M4, bx - W / 2.0, min(ay, by),
                                    bx + W / 2.0, max(ay, by), net=net, kind="metal"))
            if abs(ax - bx) > 1e-9 and abs(ay - by) > 1e-9:
                shapes.append(Shape(DD.L_VIA2, bx - hv, ay - hv, bx + hv, ay + hv,
                                    net=net, kind="via"))
    return {"shapes": shapes, "n_nets": n_net}


DPNR_DISCLOSURE = {
    "what": "B 系列接入主链：真单元几何 + 真引脚 + 按通道分轨（容量律）+ 网络提取 + 网格 IR",
    "claimable": False,
    "not_full_ip": True,
    "limits": [
        "主链**子块**接入，不是 1340 单元全 IP：dcells 仅建模 INV/NAND2（DFF 等跳过并计数），"
        "DRC 为 O(n²) 逐对比较，规模上限受 Python 限制",
        "不是通用路由器：每网一条 M3 trunk 的星形拓扑，无 maze/rip-up/协商，不做线长优化与层分配搜索",
        "M2 只画 pin access 焊盘，不画 M2 走线（沿用 E36 / ddrc_lvs.BRIDGE_PRESENT 既有约定）",
        "行高取 max(INV 1.24, NAND2 1.50)=1.50 底对齐 ⇒ 每颗 INV 上方留 0.26µm 空行（真实 std-cell 等高）",
        "单元间距 0.36µm 换 pin 可达性（真实 std-cell 行内紧邻，pin access 靠 M2 绕行）",
        "只布 gate-to-gate 内部网；带 primary I/O 的网如实计入未布（块边界无 pad/IO 环）",
        "规则集 LDA-DEMO45 自建教科书尺度，非任何 foundry PDK 真值",
        "静态 DC 提取/IR，单角 tt；不宣称可制造或可流片",
    ],
}
