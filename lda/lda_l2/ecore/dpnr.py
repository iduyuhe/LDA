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
 | `_net_pins` 单元中心 | 可接入引脚 pad 的接入点（A/B/Y 各自独立、两两 ≥pitch） | **B2 / E41 + v0.9.349** |
 | `detail_route` 无容量 | 按**通道**分配 M3 轨道 + M4 列分配 + **实际用轨数 >T 即整通道不布** | **B2 + A2 / E41/E39** |
 | `dextract` 标量 R/C | 分布式 RC 网络（SPEF 可逆） | **B3+ / E43** |
 | 无电源网 | M3/M4 网格全域 IR 求解 | **B3+ / E44** |

═══════════════════════════════════════════════════════════════════════════════
路由模型（说清楚，因为它决定了结论的适用范围）
───────────────────────────────────────────────────────────────────────────────
· **单元行**：行高取所用到单元类型的最大值（`dcells` 的 INV=1.24µm、NAND2=1.50µm **不等高**，
  真实 std-cell 是等高行 ⇒ 本模型取 max 并底对齐，属已知几何简化）。
· **单元间距**：`CELL_GAP_UM = 0.46` ⇒ `pitch_x = 0.98 + 0.46 = 1.44 = 4×轨道间距`。
  这条不是随手取的数：**只有 pitch_x 是 pitch 的整数倍，全库引脚的接入点才落在同一列网格上**
  ⇒ 每个接入点自带一条列，跳线长度为 0。真实 std-cell 行内紧邻、靠 M2 绕行；
  本模型没有 M2 细节 ⇒ **用间隙换 pin 可达性**（这是为了「零 DRC」付的面积代价）。
· **通道**：每行**上方**一条，共 `rows` 条（旧版少一条 ⇒ 末行 M4 要穿过上一行，列区间被迫重叠）。
· **每网一条 M3 trunk**（在离其引脚中位最近的通道内）＋ 每个引脚一条 M4 竖直到 trunk。
  trunk 用**区间着色**在通道内分配轨道（同轨不同网必须隔开 S_MIN），着色区间取
  **「引脚 ∪ 列」的真实跨度**（旧版用引脚跨度 ⇒ 列被推远后同轨 trunk 直接叠死）。
· **容量律**：通道只有 `T = floor((CH−W)/PITCH)+1` 条轨道；**实际用轨数 > T ⇒ 该通道
  整通道不布**（并在 `ch_info` 里如实记 `tracks_used`），A2 密度 `d` 是下界不是上界。
· 引脚接入：**M1 pad（单元自带，240×240）→ VIA1 → M2 焊盘 → V2 → M3 焊盘 → M4 竖段**。
  路由器**不再外挂 M1 焊盘**（v0.9.349）：接入点内缩 0.12 后，包围由单元引脚自己提供。

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

CELL_GAP_UM = 0.46        # 单元间距 ⇒ pitch_x = 0.98 + 0.46 = 1.44 = **4×轨道间距**
CH_UM = 1.60              # 行间通道高度
PITCH = DD.TRACK_PITCH    # 0.36
EXT = DD.VIA / 2.0 + DL.ENC   # 0.12：金属须超出孔边 ENC
W = DD.W_ROUTE            # 0.24

#: 引脚接入 x 的**库级列网格相位**（µm）。`dcells` 全部信号引脚的 pad 中心取
#: 120 / 480 / 840 nm ⇒ 与 CELL_GAP 一起保证「任意两单元的任意两个接入点，
#: 要么 x 相同（异行，y 区间不相交），要么 x 差 ≥ 一个 pitch」。
PIN_GRID_UM = 0.12


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
    #: 🔴 通道数 == 行数：每行**上方**各有一条通道（v0.9.349 修）。
    #: 旧版只给 rows−1 条，最后一行只能往**下**接到上面那条通道 ⇒ 它的 M4 竖段
    #: 要穿过倒数第二行的单元，两行的列 y 区间被迫重叠 ⇒ 同列冲突、跳线变长。
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
    n_ch = rows
    insts = []
    pitch_x = max(f().w for f in CL.CELLS.values()) / 1000.0 + CELL_GAP_UM
    for k, (g, kind) in enumerate(picked):
        r, c = divmod(k, cols)
        cell = CL.CELLS[kind]()
        insts.append({"name": g.name, "cell": g.cell, "kind": kind, "gate": g,
                      "r": r, "c": c, "x0": c * pitch_x, "y0": r * row_pitch,
                      "w": cell.w / 1000.0, "h": cell.h / 1000.0, "geom": cell})

    die_w = max((i["x0"] + i["w"] for i in insts)) + CELL_GAP_UM
    die_h = rows * row_pitch + CH_UM          # 含最上一行的通道
    return {"insts": insts, "rows": rows, "cols": cols, "die_w_um": die_w,
            "pitch_x_um": pitch_x, "n_channels": n_ch,
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
    """引脚接入栈：**VIA1 → M2 pad → V2 → M3 pad**。

    🔴 **不再另加 M1 焊盘**（v0.9.349 起）：单元引脚本身就是 240×240 的 pad，接入点
    内缩 `VIA/2+ENC = 0.12` ⇒ VIA1 的 M1 侧包围由**单元引脚**提供 —— 这正是
    「引脚可接入」的定义。旧几何（引脚仅 65nm 高）装不下 200nm 孔，只能由路由器
    补一块 M1 焊盘；那块焊盘没有单元版图约束，会与相邻网的焊盘互撞，是 E45 残差
    的来源之一。
    🔴 必须走 **V2（M2↔M3）**：原 `VIA_BRIDGE` 只有 M1–M2 与 M3–M4，**没有 M2–M3**
    ⇒ 单元引脚（M1）在几何上根本到不了 M3。本层于 v0.9.348 补入。
    """
    hv = DD.VIA / 2.0
    hp = DD.VIA / 2.0 + DL.ENC + 0.001
    return [
        Shape(DD.L_VIA1, x - hv, y - hv, x + hv, y + hv, net=net, kind="via"),
        Shape(DD.L_M2, x - hp, y - hp, x + hp, y + hp, net=net, kind="metal"),
        Shape(DD.L_V2, x - hv, y - hv, x + hv, y + hv, net=net, kind="via"),
        Shape(DD.L_M3, x - hp, y - hp, x + hp, y + hp, net=net, kind="metal"),
    ]


def pin_access_points(inst: dict) -> list:
    """该实例的**引脚接入点**（绝对坐标）：落在引脚矩形内、且离四边 ≥ `VIA/2+ENC`。

    🔴 为什么必须内缩 0.12：接入栈要在引脚上落 VIA1（0.20 见方）并由**引脚自身**
    提供 0.02 的单边包围 ⇒ 孔心离引脚边缘必须 ≥0.12。这条内缩把「引脚尺寸」从
    审美问题变成物理约束：引脚必须 ≥0.24×0.24，否则孔无处可落。
    v0.9.349 重画后接入点 = 引脚矩形中心（**零移动**）；旧几何（65nm 高）无法内缩，
    只能靠外移，而外移又要另加焊盘 —— 那条链条就是 E45 的 14 条残差。
    """
    inset = DD.VIA / 2.0 + DL.ENC          # 0.12
    out = []
    for p in pin_points(inst):
        x0, y0, x1, y1 = p["rect"]
        xlo, xhi = x0 + inset, x1 - inset
        ylo, yhi = y0 + inset, y1 - inset
        okx, oky = xlo <= xhi + 1e-9, ylo <= yhi + 1e-9
        x = min(max(p["x"], xlo), xhi) if okx else p["x"]
        y = min(max(p["y"], ylo), yhi) if oky else p["y"]
        out.append({"pin": p["pin"], "x": round(x, 6), "y": round(y, 6),
                    "x_pin": p["x"], "y_pin": p["y"],
                    "moved_um": round(max(abs(x - p["x"]), abs(y - p["y"])), 4),
                    "pad_um": (round(x1 - x0, 4), round(y1 - y0, 4)),
                    "feasible": bool(okx and oky)})
    return out


def pin_legality(cells: dict = None) -> dict:
    """**单元侧**的引脚可接入判据（不看路由器）。

    ① 每个信号 pad 两维都 ≥ `VIA + 2*ENC = 0.24`（否则 VIA1 无处可落，只能外挂焊盘）；
    ② 同一单元内接入点两两 2D 分离 ≥ 轨道 pitch（否则两个 M3 焊盘必叠）。

    这两条合起来等价于「引脚自身就是合法的 landing pad」，是 v0.9.349 重画的验收面。
    `cells` 可传入替换的 `Cell` 对象（判据的反例探针用）。
    """
    need = DD.VIA + 2.0 * DL.ENC
    inset = DD.VIA / 2.0 + DL.ENC
    src = cells if cells is not None else {n: f() for n, f in CL.CELLS.items()}
    out = {}
    for name in sorted(src):
        c = src[name]
        pads, pts, viol = {}, [], []
        for k, r in sorted(c.pins.items()):
            if k in ("VDD", "VSS"):
                continue
            w, h = r.w / 1000.0, r.h / 1000.0
            pads[k] = (round(w, 4), round(h, 4))
            if min(w, h) < need - 1e-9:
                viol.append(("pad_too_small", k, round(min(w, h), 4), round(need, 4)))
            x = min(max((r.x0 + r.x1) / 2000.0, r.x0 / 1000.0 + inset), r.x1 / 1000.0 - inset)
            y = min(max((r.y0 + r.y1) / 2000.0, r.y0 / 1000.0 + inset), r.y1 / 1000.0 - inset)
            pts.append((k, round(x, 6), round(y, 6)))
        pairs = []
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                a, b = pts[i], pts[j]
                dx, dy = abs(a[1] - b[1]), abs(a[2] - b[2])
                pairs.append({"a": a[0], "b": b[0], "dx_um": round(dx, 4),
                              "dy_um": round(dy, 4), "sep_um": round(max(dx, dy), 4)})
                if dx < PITCH - 1e-9 and dy < PITCH - 1e-9:
                    viol.append(("pins_too_close", a[0], b[0],
                                 round(max(dx, dy), 4), PITCH))
        out[name] = {"pads": pads,
                     "min_pad_um": round(min(min(v) for v in pads.values()), 4) if pads else None,
                     "min_sep_um": round(min((p["sep_um"] for p in pairs), default=PITCH), 4),
                     "access": pts, "pairs": pairs,
                     "violations": viol, "ok": not viol}
    return {"cells": out, "ok": all(v["ok"] for v in out.values()),
            "need_pad_um": round(need, 4), "need_sep_um": PITCH,
            "n_violations": sum(len(v["violations"]) for v in out.values())}


def pin_access_conflicts(pl: dict) -> dict:
    """量化**同一单元内不同网接入点**的间距冲突（2D：两轴都 < 轨道 pitch 即冲突）。

    判据是二维的，因为 DRC 也是二维的：两个接入点各自的 M3 焊盘是 0.242 见方、
    互相要 0.10 间距 ⇒ 只要**任一轴**拉开 ≥0.342，两个焊盘就不重叠。两轴都 < pitch
    时无解 —— 换列、换轨、换顺序都救不了，只能回到单元版图重画引脚。
    """
    pairs = []
    for inst in pl["insts"]:
        pts = pin_access_points(inst)
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                a, b = pts[i], pts[j]
                dx, dy = abs(a["x"] - b["x"]), abs(a["y"] - b["y"])
                if dx < PITCH - 1e-9 and dy < PITCH - 1e-9:
                    pairs.append({"inst": inst["name"], "cell": inst["kind"],
                                  "a": a["pin"], "b": b["pin"],
                                  "dx_um": round(dx, 4), "dy_um": round(dy, 4),
                                  "sep_um": round(max(dx, dy), 4)})
    worst = min((p["sep_um"] for p in pairs), default=None)
    return {"n_conflicts": len(pairs), "worst_um": worst, "need_um": PITCH,
            "samples": pairs[:6], "n_insts": len(pl["insts"])}


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
    """按通道分轨 + 列分配布内部网。返回路由结果与**容量判定**。

    🔴 **顺序是本模块的第二个真修复（v0.9.349）**：trunk 的实际长度是
    `[min(引脚x ∪ 列x), max(引脚x ∪ 列x)]`，但 v0.9.348 是按**引脚跨度**做区间着色的
    —— 列一被推远，trunk 就长出色好的区间，同轨两个网的 trunk 直接叠在一起
    （实测就是那几条「trunk vs trunk 同 y 短接」）。现在改成三步：

      ① 先按**该通道最高轨**（最坏情况）预分配列 ⇒ 竖直段只多不少；
      ② 用「引脚 ∪ 列」的**真实跨度**着色分轨 ⇒ trunk 长度与着色区间逐位一致；
      ③ 实际轨号一定 ≤ 最高轨 ⇒ 竖直段不长于预分配时的假设 ⇒ 列冲突只会更少。

    容量判定也从「A2 密度 d ≤ T」升级为「**实际用轨数 ≤ T**」：列被推远会让真实需求
    大于密度下界，只查 d 会漏判。
    """
    ch_um = pl["ch_um"] if ch_um is None else ch_um
    t_cap = tracks_in_channel(ch_um)
    pins = net_pins(pl)
    n_rows = pl["rows"]

    # —— ① 每网选一个通道（离引脚 y 中位最近的通道）——
    net_ch = {}
    for net, pts in pins.items():
        if len(pts) < 2:
            continue
        ys = [p[3] for p in pts]
        rows_of = [min(n_rows - 1, max(0, int(y // pl["row_pitch_um"]))) for y in ys]
        net_ch[net] = (min(range(n_rows),
                           key=lambda c: abs(c - sum(rows_of) / len(rows_of)))
                       if n_rows > 1 else 0)

    # —— ② 预分配列：yt 取该通道**最高轨**（最坏情况，竖直段只长不短）——
    x0_grid = PIN_GRID_UM
    runs = []
    for net in sorted(net_ch):
        y_worst = channel_y(pl, net_ch[net]) + W / 2.0 + (t_cap - 1) * PITCH
        for (_i, _p, x, y) in pins[net]:
            runs.append((net, min(y, y_worst) - EXT, max(y, y_worst) + EXT, x))
    xs, ncol_used, col_fail = _alloc_columns(runs, x0_grid, pl["die_w_um"])
    cols = defaultdict(list)
    for (net, _ya, _yb, _x), cx in zip(runs, xs):
        cols[net].append(cx)
    col_fail = sorted(set(col_fail))

    # —— ③ 用「引脚 ∪ 列」的真实跨度着色（trunk 的实际长度）——
    spans = defaultdict(list)
    for net, ch in net_ch.items():
        if net in col_fail:
            continue
        xsr = [p[2] for p in pins[net]] + cols[net]
        spans[ch].append((min(xsr), max(xsr), net))

    ch_info = {}
    track_of = {}
    for ch, ivs in spans.items():
        xs_nm = [(int(round(a * 1000)), int(round(b * 1000))) for (a, b, _n) in ivs]
        d = MT.channel_density(xs_nm) if xs_nm else 0
        trk, ntrk = _color_intervals([(a, b) for (a, b, _n) in ivs], gap=DL.S_MIN)
        ch_info[ch] = {"d": int(d), "t_avail": t_cap, "n_nets": len(ivs),
                       "tracks_used": ntrk, "routable": ntrk <= t_cap}
        if ntrk > t_cap:
            continue
        for (a, b, n), t in zip(ivs, trk):
            track_of[n] = (ch, t)

    routed = sorted(track_of)
    unrouted = sorted(n for n in (spans_to_nets(spans) | set(net_ch)) if n not in track_of)

    # —— ④ 引脚竖直（M4）：y 从引脚到 trunk（列已在 ② 分配好）——
    y_of = {}
    for net, (ch, t) in track_of.items():
        y_of[net] = channel_y(pl, ch) + W / 2.0 + t * PITCH

    # —— ⑤ 建形：分「引脚接入」与「走线」两类（判据要能分开归因）——
    acc: list = []      # 引脚接入栈（M1/M2/M3 pad + 孔）—— 受**单元引脚几何**限制
    shapes: list = []   # 走线金属（M3 trunk / M4 竖 / 弯角孔与 landing）
    hv = DD.VIA / 2.0
    for net in routed:
        yt = y_of[net]
        cols_net = cols[net]
        for (_iname, _p, x, y), cx in zip(pins[net], cols_net):
            acc += pin_stub(x, y, net)
            if abs(cx - x) > 1e-9:
                # M3 短跳线：引脚 → 列。**两端都延伸 EXT**：远端要包围 VIA2，
                # 近端也要 —— 否则 |cx−x| 落在 (0.04, 0.08) 时跳线与引脚焊盘
                # 都盖不住孔（v0.9.348 的 6 条 via_enclosure 就是这个区间）。
                shapes.append(Shape(DD.L_M3, min(x, cx) - EXT, y - W / 2.0,
                                    max(x, cx) + EXT, y + W / 2.0,
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
            "routed": routed, "unrouted": unrouted, "n_unrouted": len(unrouted),
            "ch_info": ch_info, "t_cap": t_cap, "n_cols_used": ncol_used,
            "col_fail": col_fail, "track_of": track_of,
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
    "what": "B 系列接入主链：真单元几何 + 可接入引脚 + 按通道分轨（容量律）+ 网络提取 + 网格 IR",
    "claimable": False,
    "not_full_ip": True,
    "zero_drc_scope": ("路由 DRC = 0 只在 **12 单元 / 4 列 / INV+NAND2 / LDA-DEMO45 规则集**"
                       " 这一个用例上成立；换单元类型、列数、通道高度都必须重测"),
    "limits": [
        "主链**子块**接入，不是 1340 单元全 IP：dcells 仅建模 INV/NAND2（DFF 等跳过并计数），"
        "DRC 为 O(n²) 逐对比较，规模上限受 Python 限制",
        "不是通用路由器：每网一条 M3 trunk 的星形拓扑，无 maze/rip-up/协商，不做线长优化与层分配搜索；"
        "只有一层垂直层（M4）可用，真实设计还有 M5+",
        "M2 只画 pin access 焊盘，不画 M2 走线（沿用 E36 / ddrc_lvs.BRIDGE_PRESENT 既有约定）",
        "行高取 max(INV 1.24, NAND2 1.50)=1.50 底对齐 ⇒ 每颗 INV 上方留 0.26µm 空行（真实 std-cell 等高）",
        "单元间距 0.46µm（= 1.44 − 0.98，**为轨道间距整数倍**才使全库引脚同相位）；"
        "真实 std-cell 行内紧邻，pin access 靠 M2 绕行 ⇒ 本模型是**用面积换可接入性**",
        "通道数 == 行数（每行上方一条）；旧版少一条会让末行 M4 穿过上一行、列 y 区间被迫重叠",
        "只布 gate-to-gate 内部网；带 primary I/O 的网如实计入未布（块边界无 pad/IO 环）",
        "规则集 LDA-DEMO45 自建教科书尺度，非任何 foundry PDK 真值",
        "静态 DC 提取/IR，单角 tt；不宣称可制造或可流片",
    ],
}
