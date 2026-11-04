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

CELL_GAP_UM = 0.46        # 默认单元间距 ⇒ pitch_x = 0.98 + 0.46 = 1.44 = **4×轨道间距**
#: 🔴 v0.9.351：M2 可承担「引脚 → 列」横向偏移后的**紧凑间距**（0.98 + 0.36 = 1.34，
#: 不再是轨道间距整数倍 ⇒ 引脚相位会漂移，偏移由 M2 吸收而不是 M3 跳线）。
CELL_GAP_TIGHT_UM = 0.36
#: 🔴 行内布线的**严格空隙规则**开关（供反向探针使用）。
#: `True`（默认）= 多带网只准用「夹在自己带之间」的空隙、单带网只准向外走；
#: `False` = 放开成「范围之内及紧邻上下」，会允许竖段穿过异网引脚带 ⇒ 必然撞
#: 那条带里的 M2 逃逸条（E53 实测 DRC 由 0 变 >0）。判据 H9 用它证明规则不是摆设。
IN_ROW_STRICT = True

#: M2 横向绕行长度上限（超过则如实报 too_far，不画长跳线）。0.72 = 2×轨道间距。
M2_JOG_MAX = 0.72
#: 引脚 pad 半宽 = `VIA/2 + ENC` = 0.12（E45 起单元引脚就是 240×240 pad）。
PAD_HALF = DD.VIA / 2.0 + DL.ENC
#: M2 逃逸条半宽 = pad 半宽 + 1nm 余量（条比 pad 略宽）。
M2_HALF = DD.VIA / 2.0 + DL.ENC + 0.001
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
def place_real(nl, max_cells: int = 32, cols: int = None, cell_gap: float = None) -> dict:
    """行式布局：单元按 `dcells` 真实宽度排进行，行高 = 1.50µm。

    只用 `dcells` 里有的单元类型；遇到未建模类型（如 DFF）**跳过并计数**（披露 ①）。
    """
    gap = CELL_GAP_UM if cell_gap is None else float(cell_gap)
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
    pitch_x = max(f().w for f in CL.CELLS.values()) / 1000.0 + gap
    for k, (g, kind) in enumerate(picked):
        r, c = divmod(k, cols)
        cell = CL.CELLS[kind]()
        insts.append({"name": g.name, "cell": g.cell, "kind": kind, "gate": g,
                      "r": r, "c": c, "x0": c * pitch_x, "y0": r * row_pitch,
                      "w": cell.w / 1000.0, "h": cell.h / 1000.0, "geom": cell})

    die_w = max((i["x0"] + i["w"] for i in insts)) + gap
    die_h = rows * row_pitch + CH_UM          # 含最上一行的通道
    return {"insts": insts, "rows": rows, "cols": cols, "die_w_um": die_w,
            "pitch_x_um": pitch_x, "n_channels": n_ch, "cell_gap_um": gap,
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


def point_off_budget(others: list, x: float, net: str, jog_max: float) -> tuple:
    """**y 邻域内**某个引脚允许的 M2 逃逸长度，**按方向分开**：`(向左, 向右)`。

    `others` = 该引脚 y 邻域内的 `[(x_other, net_other)]`（由调用方按 y 区间重叠筛好）。

    🔴 为什么必须分方向（v0.9.352）：逃逸条只朝**一个方向**扩张 ⇒ 向左逃只受**左邻**约束、
    向右逃只受**右邻**约束。初版用「两侧各摊一半」的单一额度，把「向左 0.5µm 完全合法」
    误判成「只能逃 0.01µm」—— 实测 12 单元布通率从 10/10 掉到 9/10（判据立刻抓到）。

    🔴 为什么必须按 **y 区间重叠**判邻（v0.9.352 第二修）：初版按 `round(y,2)` 分带，
    而 INV 的引脚中心 y=535nm、NAND2 是 530nm —— 两者 M2 条在 y 上**确实重叠**，却被
    分进不同的带 ⇒ 互不约束 ⇒ 64 单元 gap=0.36 时冒出 2 条 `min_spacing`。
    M2 条高 `W`、两条共存须留 `S_MIN` ⇒ **y 差 < W + S_MIN 就必须算邻居**。

    闭式：向左逃 δ 时条左端 = `x − M2_HALF − δ`，须与左邻条右端留 `S_MIN`
    ⇒ `δ ≤ (x − x_left) − 2·M2_HALF − S_MIN`。同单元 A/B（相隔一个 pitch）给出
    `0.36 − 0.242 − 0.10 = 0.018`，与 E48「内向逃逸总量 0.02µm」逐位一致。
    """
    left = right = None
    for (xo, no) in others:
        if no == net or abs(xo - x) < 1e-9:
            continue
        if xo < x:
            v = (x - xo) - 2.0 * M2_HALF - DL.S_MIN
            left = v if left is None else min(left, v)
        else:
            v = (xo - x) - 2.0 * M2_HALF - DL.S_MIN
            right = v if right is None else min(right, v)
    return (max(0.0, min(jog_max, left if left is not None else jog_max)),
            max(0.0, min(jog_max, right if right is not None else jog_max)))


def pin_stub(x: float, y: float, net: str, cx: float = None) -> list:
    """引脚接入栈：**VIA1 → M2 pad → M2 横条 → V2 → M3 pad**。

    🔴 **v0.9.351：把「引脚 → 列」的横向偏移交给 M2**（真实设计的做法）。
    · 旧版在 M3 上画横向跳线：跳线落在 pin 的 y 上，与邻网的 M3 焊盘/跳线抢同一层，
      单元间距一旦退回 0.36µm 就出 `min_spacing`（实测 4 条）；
    · 新版把偏移交给 **M2**（原本只用来放焊盘的那一层）：M1 pad --VIA1--> M2 --横条-->
      V2 --> M3。于是 **M3 侧永远落在列网格上**，不需要横向跳线；trunk 也能只覆盖列
      （更短 ⇒ 同轨重叠面更小）。`M2_JOG_MAX` 限长，超出则退回 M3 跳线并计数。

    🔴 **不再另加 M1 焊盘**（v0.9.349 起）：单元引脚本身就是 240×240 的 pad，接入点
    内缩 `VIA/2+ENC = 0.12` ⇒ VIA1 的 M1 侧包围由**单元引脚**提供 —— 这正是
    「引脚可接入」的定义。
    🔴 必须走 **V2（M2↔M3）**：原 `VIA_BRIDGE` 只有 M1–M2 与 M3–M4，**没有 M2–M3**
    ⇒ 单元引脚（M1）在几何上根本到不了 M3。该层于 v0.9.348 补入。
    """
    hv = DD.VIA / 2.0
    hp = M2_HALF                      # = VIA/2 + ENC + 1nm（可被 `dproc.use()` 替换）
    cx = x if cx is None else cx
    out = [
        Shape(DD.L_VIA1, x - hv, y - hv, x + hv, y + hv, net=net, kind="via"),
        Shape(DD.L_M2, x - hp, y - hp, x + hp, y + hp, net=net, kind="metal"),
        Shape(DD.L_V2, cx - hv, y - hv, cx + hv, y + hv, net=net, kind="via"),
        Shape(DD.L_M3, cx - hp, y - hp, cx + hp, y + hp, net=net, kind="metal"),
    ]
    if abs(cx - x) > 1e-9:
        # M2 横条：两端各延伸 hp，把 VIA1 与 V2 都包进去
        out.append(Shape(DD.L_M2, min(x, cx) - hp, y - W / 2.0,
                         max(x, cx) + hp, y + W / 2.0, net=net, kind="metal"))
    return out


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


def _alloc_columns(runs: list, x0_grid: float, die_w: float,
                   max_off: float = None) -> tuple:
    """M4 列分配：离散列网格 + y 区间着色 ⇒ 不同网的 M4 在 y 上永不重叠。

    `runs` = [(net, y_lo, y_hi, x_desired, dir_pref)]，
    返回 (每段的列 x, 用到的列数, 失败列表)，失败项是 `(net, reason)`：

    🔴 `too_far`（v0.9.352，**规模上探查出的真缺陷**）：`max_off` 给定时，列必须落在
    引脚 x 的 `±max_off` 内。起因是规模放大的真实失效路径 —— 列被推远超过 M2 逃逸上限后，
    旧代码退回 **M3 横向长跳线**，而跳线只能画在**引脚 y** 上；同一行所有引脚 y 相同 ⇒
    多条长跳线全部叠在同一 y、同层不同网 ⇒ `min_spacing` 成片（64 单元 8 行实测 41 条）。
    这是**资源冲突**而非算法缺陷：同 y 引脚的 M3 横向资源是有限的。正确做法是像容量律
    一样**如实报布不通**，不能画出违例假装布通。
    `no_column`：列网格已满（y 区间着色找不到空位）。

    🔴 `dir_pref`（v0.9.351）：**搜索方向的偏好**（−1 向左 / +1 向右 / 0 不限）。
    起因：M2 逃逸条本身占 y 带（高 W），**同一 y 带上的相邻引脚**若都朝同一侧逃逸，
    两条就会撞（实测 NAND2 的 A/B 同 y、只差 0.36µm）。让它们**左右交替**逃逸，
    自然分开；偏好只是搜索顺序，找不到合适的仍回退到另一侧/更远的列。
    """
    ncol = max(1, int((die_w - W) // PITCH) + 1)
    # 搜索半径：给了 max_off 就只在引脚 ±max_off 内找列（超出的段如实报 too_far）
    dmax = (ncol - 1) if max_off is None else min(ncol - 1, int(max_off // PITCH + 1e-9))
    col_ivs: list = [[] for _ in range(ncol)]     # 每列已占用的 y 区间
    xs = [0.0] * len(runs)
    fail = []
    order = sorted(range(len(runs)), key=lambda i: (runs[i][3], runs[i][1], i))
    for i in order:
        row = runs[i]
        _net, ya, yb, xd, pref = row[0], row[1], row[2], row[3], row[4]
        pt_off = row[5] if len(row) > 5 else None       # (向左, 向右) 或 None
        if yb - ya <= 1e-9:
            xs[i] = xd
            continue
        ia, ib = ya - DL.S_MIN / 2.0, yb + DL.S_MIN / 2.0
        k0 = int(round((xd - x0_grid) / PITCH))
        best = None
        for d in range(0, dmax + 1):
            cands = (k0 - d, k0 + d) if pref < 0 else ((k0, k0) if d == 0 else (k0 + d, k0 - d))
            for k in cands:
                if k < 0 or k >= ncol:
                    continue
                if pt_off is not None:
                    cx = x0_grid + k * PITCH
                    lim = pt_off[0] if cx < xd else pt_off[1]
                    if abs(cx - xd) > lim + 1e-9:
                        continue
                elif max_off is not None and abs(x0_grid + k * PITCH - xd) > max_off + 1e-9:
                    continue
                if all(ib <= e0 or ia >= e1 for (e0, e1) in col_ivs[k]):
                    best = k
                    break
            if best is not None:
                break
        if best is None:
            # 区分「网格满」与「超出逃逸半径」：前者是布线资源不足，后者是引脚横向可达性不足
            # 判「网格满」还是「超出逃逸半径」：任一方向额度内存在网格列 ⇒ 是前者
            reachable = False
            for k in range(ncol):
                cx = x0_grid + k * PITCH
                if pt_off is not None:
                    lim = pt_off[0] if cx < xd else pt_off[1]
                    if abs(cx - xd) <= lim + 1e-9:
                        reachable = True
                        break
                elif max_off is None or abs(cx - xd) <= max_off + 1e-9:
                    reachable = True
                    break
            fail.append((_net, "no_column" if reachable else "too_far"))
            xs[i] = xd
            continue
        col_ivs[best].append((ia, ib))
        xs[i] = x0_grid + best * PITCH
    used = sum(1 for c in col_ivs if c)
    return xs, used, fail


def _in_row_conflicts(shapes_all: list, inrow_nets: set) -> set:
    """返回**行内网的形状**与异网同层形状之间间距 < S_MIN 的网集合。

    用 `fast_drc` 已经被证明等价的空间哈希思路不在这里重复实现 —— 这里只需要
    「哪些网涉事」，用逐对 + 层分组即可（行内网数量少，且只在有行内网时调用一次）。
    """
    bad = set()
    by_layer = defaultdict(list)
    for s in shapes_all:
        if s.kind in ("metal", "pin") and s.net:
            by_layer[s.layer].append(s)
    half = DL.S_MIN / 2.0 - DL.SPACE_EPS
    for _lay, rs in by_layer.items():
        for i in range(len(rs)):
            a = rs[i]
            for j in range(i + 1, len(rs)):
                b = rs[j]
                if a.net == b.net:
                    continue
                if a.net not in inrow_nets and b.net not in inrow_nets:
                    continue
                if DD.rects_overlap(a, b, inflate=half):
                    bad.add(a.net if a.net in inrow_nets else b.net)
    return bad


def row_bands(pl: dict, pins: dict, pad_half: float = None) -> dict:
    """每行的**引脚带**与**带间空隙**（µm，绝对坐标）。

    行内布线的关键几何在这里：同一行内所有引脚只落在少数几条 y 带里
    （DEMO45 只有两条：A/B ≈0.41–0.65、Y ≈0.78–1.09），带与带之间是**空隙**。
    水平走线只能放空隙里；竖向走线**必须只穿过自己网的引脚带**，否则会撞上
    别的网在那条带里的 M2 逃逸条（实测就是这个撞法）。

    返回 `{row: {"bands": [(y0,y1)...], "gaps": [{"i":k,"y0","y1","tracks":[y...]}]}}`
    """
    # 🔴 带半宽取 `M2_HALF`（比 PAD_HALF 大 1nm）：实际画出来的 M3 焊盘是 M2_HALF 半宽，
    # 用 PAD_HALF 会少算 1nm ⇒ 轨道贴到焊盘边缘就撞。
    ph = (max(PAD_HALF, M2_HALF) if pad_half is None else pad_half)
    occ = defaultdict(list)
    for _net, pts in pins.items():
        for (_i, _p, _x, y) in pts:
            r = int(y // pl["row_pitch_um"])
            occ[r].append((y - ph, y + ph, y))
    out = {}
    for r, ivs in occ.items():
        ivs.sort()
        base = r * pl["row_pitch_um"]
        top = base + pl["h_row_um"]
        bands: list = []
        for (a, b, _y) in ivs:
            a, b = max(a, base), min(b, top)
            if b <= a:
                continue
            if bands and a <= bands[-1][1]:
                bands[-1] = (bands[-1][0], max(bands[-1][1], b))
            else:
                bands.append((a, b))
        gaps = []
        prev = base
        for (a, b) in bands:
            if a > prev:
                gaps.append((prev, a))
            prev = max(prev, b)
        if top > prev:
            gaps.append((prev, top))
        # 🔴 轨道切片必须留够 **W/2 + S**（不是 S/2）：轨道本身有宽度 W，
        # 它与两侧引脚带的净距必须是 S_MIN。初版写成 `a + PITCH/2` 起排 ⇒ 只留 S/2，
        # 实测立刻在 12 单元就出 2 条 min_spacing（行内水平段贴到邻网引脚焊盘）。
        gs = []
        margin = W / 2.0 + DL.S_MIN
        for k, (a, b) in enumerate(gaps):
            lo, hi = a + margin, b - margin
            n = 0 if hi < lo else int((hi - lo) // PITCH) + 1
            tr = [round(lo + i * PITCH, 6) for i in range(n)]
            gs.append({"i": k, "y0": a, "y1": b, "tracks": tr})
        out[r] = {"bands": bands, "gaps": gs}
    return out


def band_of(bands: list, y: float) -> int:
    """`y` 落在第几条带（0-based；不在任何带内返回 -1）。"""
    for k, (a, b) in enumerate(bands):
        if a - 1e-9 <= y <= b + 1e-9:
            return k
    return -1


def plan_in_row(pl: dict, pins: dict) -> dict:
    """把「所有引脚都在同一行」的网分配到**行内水平轨道**（按空隙 + 区间着色）。

    🔴 **可布性判据（这是 E53 相对 E51 的实质修复）**：一条行内竖向段从引脚 y 走到
    轨道 y，途中**只能穿过属于本网引脚的带**；穿过任何别的带 ⇒ 必然撞上那个带里
    异网的 M2 逃逸条（实测 `min_spacing`）。
    所以允许的空隙 = 本网引脚带范围之内及紧邻上下：设本网占第 `lo..hi` 条带
    （且必须**连续**），允许空隙下标 ∈ [lo, hi+1]。
    不连续（例如占了第 0 和第 2 条、中间第 1 条是别人的）⇒ **不按行内布**，如实退回常规布线。

    返回 `{plan: {net: (row, gap_i, track_y)}, n_int, n_same_row, eligible, fail, n_tracks}`。
    """
    rb = row_bands(pl, pins)
    per_row_gap = defaultdict(list)          # (row, gap_i) -> [(x0, x1, net)]
    n_int = n_same = 0
    eligible, fail = 0, []
    net_gap = {}
    for net, pts in pins.items():
        if len(pts) < 2:
            continue
        n_int += 1
        rows = {int(p[3] // pl["row_pitch_um"]) for p in pts}
        if len(rows) != 1:
            continue
        n_same += 1
        r = rows.pop()
        info = rb.get(r)
        if info is None:
            fail.append(net)
            continue
        bs = sorted({band_of(info["bands"], p[3]) for p in pts} - {-1})
        if not bs:
            fail.append(net)
            continue
        lo, hi = bs[0], bs[-1]
        if len(bs) != hi - lo + 1:            # 不连续 ⇒ 必穿过别人的带
            fail.append(net)
            continue
        # 🔴 空隙选择规则（v0.9.356 第二修，就是这条把 DRC 打到 0）：
        #   · 单带网：竖向只**向外**走（gap `lo` 在下、`lo+1` 在上）⇒ 不穿任何别的带；
        #   · 多带网：**必须**用**严格夹在自己带之间**的空隙（`lo+1..hi`）——
        #     竖向从两端向中间走，谁都不穿别人的带。若中间没有放得下轨道的空隙，
        #     就**如实退回常规布线**（不去试外侧空隙：那会让一端穿过另一条带，
        #     而那条带里躺着异网的 M2 逃逸条，实测就是 2 条 min_spacing）。
        by_i = {g["i"]: g for g in info["gaps"]}
        if IN_ROW_STRICT:
            order = [lo, lo + 1] if len(bs) == 1 else list(range(lo + 1, hi + 1))
        else:                                    # 反向探针通道：放开的（错）规则
            order = list(range(max(0, lo - 1), min(len(info["gaps"]), hi + 2)))
        cand = [by_i[k] for k in order if k in by_i and by_i[k]["tracks"]]
        if not cand:
            fail.append(net)
            continue
        net_gap[net] = (r, cand)
        eligible += 1

    # 按 (row, gap) 做区间着色；空隙内轨道不够的网如实记 fail
    # 🔴 **必须按 `(row, gap_i)` 分组，不能按列表对象的 id 分组**（初版就这么错的：
    # 每个网的候选空隙列表是**不同的对象** ⇒ id 不同 ⇒ 每个网独占一组 ⇒ 全部拿 track 0
    # ⇒ 同轨异网直接叠死，实测 86 条 min_spacing）。
    plan = {}
    pick = {}
    for net, (r, cand) in net_gap.items():
        g = cand[0]                     # 优先最靠近本网引脚带的空隙（竖向最短）
        pick[net] = (r, g)
        xs = [p[2] for p in pins[net]]
        per_row_gap[(r, g["i"])].append((min(xs), max(xs), net))
    used = {}
    for (r, gi), ivs in per_row_gap.items():
        g = pick[ivs[0][2]][1]
        ivs.sort()
        trk, ntrk = _color_intervals([(a, b) for (a, b, _q) in ivs], gap=DL.S_MIN)
        for (a, b, net), t in zip(ivs, trk):
            if t < len(g["tracks"]):
                plan[net] = (r, gi, g["tracks"][t])
            else:
                fail.append(net)
        used[(r, gi)] = max(used.get((r, gi), 0), ntrk)
    n_tracks = sum(len(g["tracks"]) for info in rb.values() for g in info["gaps"])
    return {"plan": plan, "bands": rb, "n_int": n_int, "n_same_row": n_same,
            "eligible": eligible, "fail": sorted(set(fail)), "n_tracks": n_tracks,
            "used": used}


def route_block(nl, pl: dict, ch_um: float = None, m2_jog: bool = True,
                m2_jog_max: float = None, in_row: bool = False,
                col_iters: int = 1, vert_layer: str = "M4",
                in_row_m3: bool = False, in_row_exclude=None,
                in_row_check: bool = True) -> dict:
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
    jog_max = M2_JOG_MAX if m2_jog_max is None else float(m2_jog_max)
    t_cap = tracks_in_channel(ch_um)
    pins = net_pins(pl)
    n_rows = pl["rows"]
    # 🔴 单端点网 = 另一端在 primary I/O 上（本模块**不建端口**）⇒ 无法布，但**必须记账**。
    #    此前这类网在 `len(pts) < 2` 处被静默跳过，而 `unrouted` 返回空 ⇒ 读者会以为「全布完了」。
    skipped_port = sorted(n for n, pts in pins.items() if len(pts) < 2)

    # —— ⓿ 行内布线预规划（v0.9.356 · E53）────────────────────────────
    # 所有引脚都在同一行的网，**不需要 trunk / 通道 / M4 列**：它可以在行内用
    # M2 竖段 + M3 水平段（走在行内空闲 y 带）自成一网。于是它同时释放
    # **1 条通道轨道 + 每引脚 1 条 M4 列** —— 这正是 E50/E51 卡住的两种资源。
    ip = (plan_in_row(pl, pins) if in_row_m3
          else {"plan": {}, "fail": [], "n_int": 0, "n_same_row": 0,
                "n_tracks": 0, "eligible": 0})
    inrow = {n: v for n, v in ip["plan"].items()
             if not in_row_exclude or n not in in_row_exclude}
    inrow_fail = set(ip["fail"])

    # —— ① 每网选一个通道（离引脚 y 中位最近的通道）——
    net_ch = {}
    for net, pts in pins.items():
        if len(pts) < 2 or net in inrow:
            continue
        ys = [p[3] for p in pts]
        rows_of = [min(n_rows - 1, max(0, int(y // pl["row_pitch_um"]))) for y in ys]
        net_ch[net] = (min(range(n_rows),
                           key=lambda c: abs(c - sum(rows_of) / len(rows_of)))
                       if n_rows > 1 else 0)

    # —— ② 预分配列：yt 取该通道**最高轨**（最坏情况，竖直段只长不短）——
    x0_grid = PIN_GRID_UM
    # 同一 y 带内的引脚按 x 排序后**左右交替**逃逸：M2 逃逸条本身占 y 带（高 W），
    # 同 y 的相邻引脚若都朝同一侧走，两条必然相撞（NAND2 的 A/B 就是同 y、只差 0.36µm）。
    pt_pref = {}
    bands = defaultdict(list)
    for net in sorted(net_ch):
        for i, (_iname, _p, x, y) in enumerate(pins[net]):
            bands[round(y, 2)].append((x, net, i))
    for _yk, items in bands.items():
        for rank, (_x, net, i) in enumerate(sorted(items)):
            pt_pref[(net, i)] = -1 if rank % 2 == 0 else 1

    # y 邻域：M2 条高 W、两条共存须留 S_MIN ⇒ |Δy| < W + S_MIN 就算邻居。
    # 用**滑窗**而不是哈希分带（分带会把 y 相差 5nm 的引脚错开，正是那 2 条 DRC 的来源）。
    y_tol = W + DL.S_MIN
    flat = []
    for net in sorted(net_ch):
        for i, (_iname, _p, x, y) in enumerate(pins[net]):
            flat.append((y, x, net, i))
    flat.sort()
    near = {}
    hi = 0
    for idx, (y, x, net, i) in enumerate(flat):
        lo = idx
        while lo > 0 and flat[lo - 1][0] >= y - y_tol:
            lo -= 1
        while hi < len(flat) and flat[hi][0] <= y + y_tol:
            hi += 1
        near[(net, i)] = [(fx, fn) for (_fy, fx, fn, _fi) in flat[lo:hi]]

    runs = []
    for net in sorted(net_ch):
        y_worst = channel_y(pl, net_ch[net]) + W / 2.0 + (t_cap - 1) * PITCH
        for i, (_iname, _p, x, y) in enumerate(pins[net]):
            # 🔴 `m2_jog=False` 时**不给逐点额度**：这是刻意保留的「旧行为」通道，
            # 供反向探针使用（退回无上限列搜索 ⇒ M3 长跳线 ⇒ DRC 成片）。
            # 若能随便关掉而不产生违例，就说明判据 A 不是修出来的、是天生如此。
            moff = (point_off_budget(near.get((net, i), []), x, net, jog_max)
                    if m2_jog else None)
            runs.append((net, min(y, y_worst) - EXT, max(y, y_worst) + EXT, x,
                         pt_pref.get((net, i), 0), moff))
    xs, ncol_used, col_fails = _alloc_columns(
        runs, x0_grid, pl["die_w_um"], max_off=(jog_max if m2_jog else None))
    cols = defaultdict(list)
    for r, cx in zip(runs, xs):
        cols[r[0]].append(cx)

    # ── 列分配迭代（v0.9.354 · E51）──────────────────────────────────
    # 🔴 第一轮用「通道**最高轨**」估 M4 竖段的 y 区间（最坏情况，保证不冲突但区间偏长）。
    # 实际轨号只会 ≤ 最高轨 ⇒ 真实 y 区间更短 ⇒ **同一列本可容纳更多网**。
    # 这里用第一轮的实际轨号再来一遍，取「列失败网数更少」的那一轮。
    # （为什么要有界：改列 ⇒ trunk 跨度变 ⇒ 着色变，迭代不保证单调收敛。）
    if col_iters >= 2:
        _best = (len({n for (n, _r) in col_fails}), xs, cols, runs, col_fails)
        for _it in range(col_iters - 1):
            # 用上一轮 cols 估「引脚 → trunk」的真实 y 跨度
            _sp = defaultdict(list)
            for _n, _ch in net_ch.items():
                if _n in {x for (x, _r) in col_fails}:
                    continue
                _xr = [p[2] for p in pins[_n]] + cols[_n]
                _sp[_ch].append((min(_xr), max(_xr), _n))
            _tof = {}
            for _ch, _ivs in _sp.items():
                _trk, _nt = _color_intervals([(a0, b0) for (a0, b0, _q) in _ivs], gap=DL.S_MIN)
                if _nt > t_cap:
                    continue
                for (a0, b0, _q), _t in zip(_ivs, _trk):
                    _tof[_q] = (_ch, _t)
            _runs = []
            for _n in sorted(net_ch):
                if _n not in _tof:
                    continue
                _ch, _t = _tof[_n]
                _yt = channel_y(pl, _ch) + W / 2.0 + _t * PITCH
                for _i, (_iname, _p, _x, _y) in enumerate(pins[_n]):
                    _runs.append((_n, min(_y, _yt) - EXT, max(_y, _yt) + EXT, _x,
                                  pt_pref.get((_n, _i), 0),
                                  (point_off_budget(near.get((_n, _i), []), _x, _n, jog_max)
                                   if m2_jog else None)))
            if not _runs:
                break
            _xs2, _nc2, _cf2 = _alloc_columns(
                _runs, x0_grid, pl["die_w_um"], max_off=(jog_max if m2_jog else None))
            _cols2 = defaultdict(list)
            for _r, _cx in zip(_runs, _xs2):
                _cols2[_r[0]].append(_cx)
            _nf = len({n for (n, _r) in _cf2})
            # 只在**覆盖的网数一致**时采用：否则会有网在新 cols 里没有条目，
            # 建形时 `xspan` 为空（第一版就这么崩的）。
            if _nf < _best[0] and len(_cols2) == len(cols) and len(_runs) == len(runs):
                _best = (_nf, _xs2, _cols2, _runs, _cf2)
            xs, cols, runs, col_fails = _best[1], _best[2], _best[3], _best[4]
            if _nf >= _best[0] and _it > 0:
                break
    col_fail = sorted({n for (n, _r) in col_fails})
    fail_reason = defaultdict(set)
    for (n, r) in col_fails:
        fail_reason[n].add(r)
    # 🔴 计数口径：**按网去重**（一个网可能有多个引脚段失败）。按「段」计数会让
    # 「列失败率」超过 100%（1024 单元实测 117%），那是口径错误不是数据。
    nets_too_far = {n for (n, r) in col_fails if r == "too_far"}
    nets_no_col = {n for (n, r) in col_fails if r == "no_column"}
    n_too_far, n_no_col = len(nets_too_far), len(nets_no_col)
    n_seg_fails = len(col_fails)

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

    routed = sorted(set(track_of) | set(inrow))
    unrouted = sorted(n for n in (spans_to_nets(spans) | set(net_ch))
                      if n not in track_of and n not in inrow)

    # —— ④ 引脚竖直（M4）：y 从引脚到 trunk（列已在 ② 分配好）——
    y_of = {}
    for net, (ch, t) in track_of.items():
        y_of[net] = channel_y(pl, ch) + W / 2.0 + t * PITCH

    # —— ⑤ 建形：分「引脚接入」与「走线」两类（判据要能分开归因）——
    acc: list = []      # 引脚接入栈（M1/M2/M3 pad + 孔）—— 受**单元引脚几何**限制
    shapes: list = []   # 走线金属（M3 trunk / M4 竖 / 弯角孔与 landing）
    hv = DD.VIA / 2.0
    n_m2_jog = 0
    n_m3_jog = 0
    n_in_row = 0
    # ── 行内网建形（v0.9.356 · E53）──────────────────────────────────
    # 每网：引脚 M1 --VIA1--> M2 竖段 --V2--> M3 水平段（走在**行内空闲 y 带**）。
    # 🔴 与 E51 的差别只有一处，但决定成败：水平段的 y 不是引脚 y，而是**空出来的轨道 y**。
    for net in sorted(inrow):
        _r, _gi, ty = inrow[net]
        xs_n = [p[2] for p in pins[net]]
        for (_i, _p, x, y) in pins[net]:
            acc += pin_stub(x, y, net)
            shapes.append(Shape(DD.L_M2, x - W / 2.0, min(y, ty) - EXT,
                                x + W / 2.0, max(y, ty) + EXT, net=net, kind="metal"))
            shapes.append(Shape(DD.L_V2, x - hv, ty - hv, x + hv, ty + hv,
                                net=net, kind="via"))
        shapes.append(Shape(DD.L_M3, min(xs_n) - EXT, ty - W / 2.0,
                            max(xs_n) + EXT, ty + W / 2.0, net=net, kind="metal"))

    for net in routed:
        if net in inrow:
            continue
        yt = y_of[net]
        cols_net = cols[net]
        m3_xs = []                     # trunk 还需覆盖的引脚 x（只在退回 M3 跳线时才有）

        # ── 行内局部互联（v0.9.354 · E51）────────────────────────────
        # 🔴 实测 **60–80% 的内部网所有引脚在同一行**（256 单元 cols=24 时 79%）。
        # 这些网根本不需要跨行长竖线：让它们**共享一条 M4 列**（锚 = 最左引脚），
        # 其余引脚用 M3 水平段在自己的 y 上接到锚列 ⇒ 列需求从「引脚数」降到「1」。
        # 同一列也因此能被**多行复用**（不同行的 y 区间不重叠），列压力大幅下降。
        # 代价：M3 水平段会横穿同行其他单元的上方，可能撞异网的 pad（判据 B2 守 DRC）。
        if in_row and len(cols_net) > 1:
            rows_of = {int(y // pl["row_pitch_um"]) for (_i, _pp, _xx, y) in pins[net]}
            if len(rows_of) == 1:
                cx = cols_net[0]
                ys = [y for (_i, _pp, _xx, y) in pins[net]]
                for (_i, _pp, x, y) in pins[net]:
                    if abs(x - cx) < 1e-9:
                        acc += pin_stub(x, y, net, cx)
                        continue
                    acc += pin_stub(x, y, net)          # 自身位置打孔到 M3
                    shapes.append(Shape(DD.L_M3, min(x, cx) - EXT, y - W / 2.0,
                                        max(x, cx) + EXT, y + W / 2.0,
                                        net=net, kind="metal"))
                    n_in_row += 1
                # 锚列上一条 M4 竖线（覆盖所有引脚的 y 到 trunk）
                shapes.append(Shape(DD.L_M4, cx - W / 2.0, min(min(ys), yt) - EXT,
                                    cx + W / 2.0, max(max(ys), yt) + EXT,
                                    net=net, kind="metal"))
                for y in ys:                            # 每个引脚在锚列的 VIA2
                    shapes.append(Shape(DD.L_VIA2, cx - hv, y - hv, cx + hv, y + hv,
                                        net=net, kind="via"))
                shapes.append(Shape(DD.L_VIA2, cx - hv, yt - hv, cx + hv, yt + hv,
                                    net=net, kind="via"))
                shapes.append(Shape(DD.L_M3, cx - EXT, yt - W / 2.0,
                                    cx + EXT, yt + W / 2.0, net=net, kind="metal"))
                continue

        for (_iname, _p, x, y), cx in zip(pins[net], cols_net):
            off = abs(cx - x)
            if m2_jog and off <= jog_max + 1e-9:
                # 🔴 M2 承担横向偏移：M3 侧直接落在列上 ⇒ 不需要 M3 跳线
                acc += pin_stub(x, y, net, cx)
                if off > 1e-9:
                    n_m2_jog += 1
            else:
                acc += pin_stub(x, y, net)
                if off > 1e-9:
                    # 退回 M3 跳线：**两端都延伸 EXT**（远端包围 VIA2，近端盖住引脚焊盘）
                    shapes.append(Shape(DD.L_M3, min(x, cx) - EXT, y - W / 2.0,
                                        max(x, cx) + EXT, y + W / 2.0,
                                        net=net, kind="metal"))
                    m3_xs.append(x)
                    n_m3_jog += 1
            # ── 竖直段所在的层（v0.9.355 架构修正）────────────────────────
            # 真实工艺层方向是 M1 水平 / **M2 竖直** / M3 水平 / **M4 竖直** / M5 水平…
            # 而本仓原先把 M2 当成「水平逃逸条」用 ⇒ **白扔了一套竖直资源**，
            # 只剩 M4 一层竖直线 ⇒ 列资源只有真实设计的一半。
            # 这里支持把竖直段放到 M2（用 L_V2 = M2↔M3）或 M4（用 L_VIA2 = M3↔M4）。
            if vert_layer == "M2":
                shapes.append(Shape(DD.L_V2, cx - hv, y - hv, cx + hv, y + hv,
                                    net=net, kind="via"))
                shapes.append(Shape(DD.L_M2, cx - W / 2.0, min(y, yt) - EXT,
                                    cx + W / 2.0, max(y, yt) + EXT, net=net, kind="metal"))
                shapes.append(Shape(DD.L_V2, cx - hv, yt - hv, cx + hv, yt + hv,
                                    net=net, kind="via"))
            else:
                # 列底部：M3 → M4 必须过一个 VIA2（否则 M3 与 M4 在几何上不相连）
                shapes.append(Shape(DD.L_VIA2, cx - hv, y - hv, cx + hv, y + hv,
                                    net=net, kind="via"))
                # M4 竖直：列底部 → trunk，两端各延伸 EXT 以包围两端的 VIA2
                shapes.append(Shape(DD.L_M4, cx - W / 2.0, min(y, yt) - EXT,
                                    cx + W / 2.0, max(y, yt) + EXT, net=net, kind="metal"))
                # trunk 端：VIA2（trunk 与竖段宽度 0.24 已包围 0.20 孔）
                shapes.append(Shape(DD.L_VIA2, cx - hv, yt - hv, cx + hv, yt + hv,
                                    net=net, kind="via"))
        xspan = cols_net + m3_xs
        if not xspan:                       # 兜底：列分配没覆盖到该网时用引脚 x（不该发生）
            xspan = [p[2] for p in pins[net]]
        # trunk 两端各延伸 EXT：否则末端的 VIA2 没有 M3 侧包围（via_enclosure）
        shapes.append(Shape(DD.L_M3, min(xspan) - EXT, yt - W / 2.0,
                            max(xspan) + EXT, yt + W / 2.0, net=net, kind="metal"))

    # 全量 = 接入 + 走线（连通性/端口检查要看全量，DRC 归因要看分开的）
    shapes_all = shapes + acc

    # ── 行内网的**诚实退回**（v0.9.356）──────────────────────────────
    # 行内竖段占的是「本网引脚的那一列 x」，而邻网的 M2 逃逸条也从它自己的引脚出发、
    # 终点在它的列上 —— 在 28nm 节距下两者侧向净距可能只有 (pitch − pad)/2 量级，
    # 不足以留 S_MIN。这类冲突**不能靠选轨道躲开**（竖段必须穿过自己的引脚 y 带）。
    # 处置：检出冲突网 → 把它们退回常规布线（重跑一次），而不是画出违例。
    _ex = set(in_row_exclude or ())
    if in_row_m3 and inrow and in_row_check:
        bad = _in_row_conflicts(shapes_all, set(inrow))
        bad -= _ex
        if bad:
            return route_block(nl, pl, ch_um=ch_um, m2_jog=m2_jog, m2_jog_max=m2_jog_max,
                               in_row=in_row, col_iters=col_iters, vert_layer=vert_layer,
                               in_row_m3=True, in_row_exclude=_ex | bad,
                               in_row_check=in_row_check)
    return {"shapes": shapes_all, "shapes_route": shapes, "shapes_access": acc,
            "routed": routed, "unrouted": unrouted, "n_unrouted": len(unrouted),
            "ch_info": ch_info, "t_cap": t_cap, "n_cols_used": ncol_used,
            "col_fail": col_fail, "track_of": track_of,
            "n_col_fail_too_far": n_too_far, "n_col_fail_no_column": n_no_col,
            "n_col_fail_segments": n_seg_fails,
            "col_fail_reason": {k: sorted(v) for k, v in sorted(fail_reason.items())},
            "n_m2_jog": n_m2_jog, "n_m3_jog": n_m3_jog, "m2_jog_on": bool(m2_jog),
            "n_in_row": n_in_row, "in_row_on": bool(in_row),
            "n_in_row_m3": len(inrow), "in_row_m3_on": bool(in_row_m3),
            "in_row_m3_tracks": ip["n_tracks"], "in_row_m3_fail": sorted(inrow_fail),
            "in_row_assign": {n: v for n, v in inrow.items()},
            "in_row_plan": {"n_int": ip["n_int"], "n_same_row": ip["n_same_row"],
                            "eligible": ip["eligible"], "n_tracks": ip["n_tracks"]},
            "col_iters": int(col_iters), "n_col_fail_nets": len(col_fail),
            "vert_layer": vert_layer,
            "trunk_y": y_of, "pins": pins, "n_pins": sum(len(v) for v in pins.values()),
            "skipped_port_nets": skipped_port, "n_skipped_port": len(skipped_port),
            "coverage": _coverage(routed=set(routed) | set(inrow),
                                  skipped=set(skipped_port),
                                  failed=set(unrouted) | set(inrow_fail),
                                  total=set(pins))}


def _coverage(routed: set, skipped: set, failed: set, total: set) -> dict:
    """网覆盖的四分类记账（**纯函数**，便于门禁独立复算）。

    · `routed`  真的画了金属的网；
    · `skipped` 单端点网（另一端是 primary I/O，本模块不建端口 ⇒ 布不了，但**不是**「已布」）；
    · `failed`  试图布但没成（列分配失败 / 行内规划失败）；
    · `total`   网表里出现过的全部网。

    🔴 `complete` 只表示「每条网都被归了类」，**不表示全布**；要看 `all_routed`。
    把这两件事混成一个布尔，就是本项目最容易出的那种失真。
    """
    R, S, F = set(routed), set(skipped), set(failed)
    acc = R | S | F
    # 🔴 四分类必须**互斥**：并集相等不足以证明记账正确 ——
    #    一条网同时出现在 routed 与 skipped（谎报「布了」但还挂着未布）时，
    #    并集不变量完全看不出问题。审计当日的反向探针就是这么把这一漏洞戳出来的。
    overlap = sorted((R & S) | (R & F) | (S & F))
    return {
        "total": len(total),
        "routed": len(R),
        "skipped_port": len(S),
        "failed": len(F),
        "accounted": len(acc),
        "complete": acc == set(total) and not overlap,   # 每条网恰好归一类
        "all_routed": (not S) and (not F),               # 真的全布（当前不可能为 True）
        "missing": sorted(set(total) - acc),    # 漏记（应为空）
        "unknown": sorted(acc - set(total)),    # 多记（应为空）
        "overlap": overlap,                     # 重复归类（应为空）
    }


def net_coverage(rt: dict) -> dict:
    """从路由结果**独立复算**覆盖度（门禁用它跟 `rt["coverage"]` 对拍）。"""
    return _coverage(
        routed=set(rt.get("routed") or []) | set(rt.get("in_row_assign") or {}),
        skipped=set(rt.get("skipped_port_nets") or []),
        failed=set(rt.get("unrouted") or []) | set(rt.get("in_row_m3_fail") or []),
        total=set(rt.get("pins") or {}),
    )


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
