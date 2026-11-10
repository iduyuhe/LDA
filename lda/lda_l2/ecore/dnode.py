"""工艺节点参数化：**同一套布线架构，换节点只换规则**（E52 · D-244）。

═══════════════════════════════════════════════════════════════════════════════
为什么要有这个模块
───────────────────────────────────────────────────────────────────────────────
E45–E51 的全部结论都建立在**一套写死的 0.35µm 级规则**上：

    W_ROUTE = 240nm · S_MIN = 100nm · VIA = 200nm · ENC = 20nm · 行高 1500nm

于是引脚 pad 必须做到 **240×240nm**（VIA 200 + 两倍 ENC 20）才可接入。这个 pad 把
**行内资源吃干了** —— 实测行内只剩 2 条 340nm 节距的轨道，而 pin access 自己就要用掉它们
⇒ 行内没有布线空间、M2 不能做布线层 ⇒ **只剩 M4 一层竖直资源** ⇒ 列供给/需求比被
锁死在 1.33–1.43 ⇒ **布通率 87% 的结构渐近线**（E51 结论）。

**但这不是"布线这件事做不到"** —— 成熟工艺的同一件事是能做的，差别在**规则密度**：
先进节点的 pad 只有 70nm、金属节距 140nm，同样一条 900nm 高的单元行里能放下 **5 条**轨道。

⇒ 本模块把「节点」变成一个**可替换的参数集**，让同一套布线架构能在不同节点上跑，
并给出「行内可用轨道数」这个关键派生量（它直接决定行内布线是否可行）。

═══════════════════════════════════════════════════════════════════════════════
两个节点的差别在哪（这是本模块要暴露的核心变量）
───────────────────────────────────────────────────────────────────────────────
| 项 | DEMO45（本仓历史默认） | DEMO28（28nm 级） | 比值 |
|---|---|---|---|
| 金属线宽 W | 240 nm | 70 nm | 0.29 |
| 最小间距 S | 100 nm | 70 nm | 0.70 |
| 通孔 VIA | 200 nm | 50 nm | 0.25 |
| 通孔包围 ENC | 20 nm | 10 nm | 0.50 |
| **引脚 pad = VIA+2·ENC** | **240 nm** | **70 nm** | **0.29** |
| 轨道节距 = W+S | 340 nm | 140 nm | 0.41 |
| 单元行高 | 1500 nm | 900 nm | 0.60 |
| **行内可用轨道**（实测派生） | **2** | **5** | 2.5× |

🔴 关键观察：**器件尺寸只缩 0.6 倍，金属规则缩 0.29–0.41 倍**。这正是真实工艺演进的形态
（互连比器件缩得慢，但 pad 与节距相对**行高**的比例显著变小），所以行内腾出了空间。
**等比缩放规则是无效的**（pad/pitch 比值不变 ⇒ 轨道数还是 2 条，已实测）。
"""

#: 纳米 → 微米
NM = 1000.0


class Node:
    """一个工艺节点：器件缩放因子 + 各层规则（全部以 **nm** 为单位）。

    `device_scale` 只作用于**器件与版图几何**（DIFF/POLY/NWELL/CONT 的坐标）；
    金属规则（W/S/VIA/ENC/pitch）独立给定 —— 这正是真实节点演进里两者**不同步**的地方。
    """

    def __init__(self, name, device_scale, w_min, s_min, via, enc, h_row,
                 note="", real_pdk=False):
        self.name = name
        self.device_scale = float(device_scale)
        self.w_min = float(w_min)          # nm
        self.s_min = float(s_min)          # nm
        self.via = float(via)              # nm
        self.enc = float(enc)              # nm
        self.h_row = float(h_row)          # nm
        self.note = note
        self.real_pdk = bool(real_pdk)

    # ---- 派生量 ----------------------------------------------------------
    @property
    def pad(self) -> float:
        """引脚 pad 边长（nm）= VIA + 2·ENC —— 行内资源的头号消费者。"""
        return self.via + 2.0 * self.enc

    @property
    def pitch(self) -> float:
        """轨道节距（nm）= W + S。"""
        return self.w_min + self.s_min

    def route_rules(self, unit: str = "um") -> dict:
        """布线侧的规则包（**单位显式**，避免 µm/nm 混用 —— 本仓踩过单位血案）。

        `unit="nm"` 给单元库/几何比较用；`unit="um"` 给布线器/DRC 用（它们以 µm 为口径）。
        """
        k = 1.0 if unit == "nm" else 0.001
        return {"w_min": self.w_min * k, "s_min": self.s_min * k,
                "via": self.via * k, "enc": self.enc * k, "pitch": self.pitch * k}

    def inner_tracks(self, pin_ys_nm, n_rows_cells=1) -> list:
        """**行内可用轨道 y**（nm，相对行底）：避开所有引脚 pad 后的空闲带。

        多个单元类型共存时，必须取**所有类型占用带的并集**（同一行里它们混排）。
        返回每条可用轨道的中心 y。
        """
        occ = []
        for ys in pin_ys_nm:
            for y in ys:
                occ.append((y - self.pad / 2.0, y + self.pad / 2.0))
        occ.sort()
        merged = []
        for (a, b) in occ:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        segs, prev = [], 0.0
        for (a, b) in merged:
            if a > prev:
                segs.append((prev, a))
            prev = max(prev, b)
        if self.h_row > prev:
            segs.append((prev, self.h_row))
        tracks = []
        for (a, b) in segs:
            n = int((b - a) // self.pitch)
            for i in range(n):
                tracks.append(round(a + self.pitch / 2.0 + i * self.pitch, 3))
        return tracks

    def __repr__(self):
        return ("Node(%s: pad=%.0fnm pitch=%.0fnm h_row=%.0fnm device_scale=%.2f)"
                % (self.name, self.pad, self.pitch, self.h_row, self.device_scale))


#: 本仓历史默认（0.35µm 级教科书尺度）。**不是任何 foundry PDK。**
DEMO45 = Node("DEMO45", device_scale=1.00, w_min=240, s_min=100, via=200, enc=20,
              h_row=1500, note="本仓历史默认 · 0.35µm 级教科书尺度 · 非 PDK")

#: 28nm 级（教科书尺度参数，量级参照公开工艺讨论，**不是真实 PDK 数值**）。
DEMO28 = Node("DEMO28", device_scale=0.60, w_min=70, s_min=70, via=50, enc=10,
              h_row=900, note="28nm 级教科书参数 · 非 PDK · 只用于验证「规则密度」这个变量")

NODES = {n.name: n for n in (DEMO45, DEMO28)}
DEFAULT_NODE = "DEMO45"


def get(name) -> Node:
    """按名字取节点；已是 `Node` 则原样返回。"""
    if isinstance(name, Node):
        return name
    if name not in NODES:
        raise KeyError("未知节点 %r（可选 %s）" % (name, sorted(NODES)))
    return NODES[name]


def compare(nodes=("DEMO45", "DEMO28"), with_capacity: bool = False) -> list:
    """节点对比表：核心是「行内可用轨道数」这一条。

    引脚 y 取自**真实单元库**（按节点的 `device_scale` 缩放），不是估的。

    `with_capacity=True` 时每行多一个 `cell_capacity` —— **该节点下单元几何能造到什么程度**
    （宽度余量的**理论上限** ∧ `max_feasible_scale` 的**实测**）。默认关：这两件事要跑
    DRC/LVS，属诊断计算，不该拖慢默认对比。

    🔴 两个数必须一起读（见 `dnodefit.width_headroom` 的 docstring）：
    「按该节点规则重画有余量」**不等于**「现有几何能缩」——实测后者恒为 `1.0`（不可缩）。
    """
    out = []
    for nm in nodes:
        nd = get(nm)
        tr = inner_tracks_for(nd)
        row = {"node": nd.name, "pad_nm": nd.pad, "pitch_nm": nd.pitch,
               "h_row_nm": nd.h_row, "device_scale": nd.device_scale,
               "n_inner_tracks": len(tr), "tracks_nm": tr,
               "in_row_feasible": len(tr) >= 1,
               "note": nd.note}
        if with_capacity:
            from . import dnodefit as NF      # 延迟导入：避免与 dcells 的初始化顺序耦合
            row["cell_capacity"] = {
                name: dict(NF.width_headroom(fn(), node=nd),
                           max_feasible_scale=NF.max_feasible_scale(fn()))
                for name, fn in sorted(NF.CL.CELLS.items())}
        out.append(row)
    return out


def capacity_projection(node, same_row_rate: float, avg_pins: float,
                        pin_access_tracks: int = 0) -> dict:
    """给定节点，算「行内布线可行时，列需求能降到原来的几倍」。

    ⚠️ 这是**几何下界估计**，不是实测布通率：
      · 同行网（占比 `same_row_rate`）若能在行内互联，每网只需 **1 条锚列**，
        而不是「每引脚 1 条」（平均 `avg_pins` 条）⇒ 这部分需求乘 `1/avg_pins`；
      · 跨行网不变 ⇒ 乘 1。
      · 加权：`ratio = (1 − f) + f / avg_pins`。

    `pin_access_tracks`：pin access 自己占掉的轨道数（M2 pad + 逃逸条）。
    本仓 DEMO45 实测 **2 条全被占** ⇒ 行内布线不可行（除以可用轨道前先扣这个）。

    返回 `ratio`（越小越好）、`feasible`（行内是否真能用）、以及判断依据。
    """
    nd = get(node)
    tracks = inner_tracks_for(nd)
    free = max(0, len(tracks) - int(pin_access_tracks))
    ratio = (1.0 - same_row_rate) + (same_row_rate / max(avg_pins, 1.0))
    return {"node": nd.name, "n_inner_tracks": len(tracks),
            "pin_access_tracks": int(pin_access_tracks), "n_free_tracks": free,
            "in_row_feasible": free >= 1,
            "same_row_rate": same_row_rate, "avg_pins": avg_pins,
            "col_demand_ratio": ratio,
            "tracks_nm": tracks,
            "note": nd.note}


def inner_tracks_for(node) -> list:
    """公开入口：给定节点，算**行内可用轨道 y**（nm，相对行底）。

    引脚 y 取自真实单元库，按节点的 `device_scale` 缩放 —— 不手填。
    """
    nd = get(node)
    return nd.inner_tracks(_pin_ys(nd))


def _pin_ys(nd):
    """按节点的 `device_scale` 缩放后的引脚 y 中心（nm）。"""
    from . import dcells as CL

    ys = []
    for cname in sorted(CL.CELLS):
        c = CL.CELLS[cname]()
        ys.append([(v.y0 + v.y1) / 2.0 * nd.device_scale
                   for k, v in c.pins.items() if k not in ("VDD", "VSS")])
    return ys


NODE_DISCLOSURE = {
    "what": "工艺节点参数化（器件缩放 + 金属规则分离），并派生「行内可用轨道数」",
    "claimable": False,
    "not_a_pdk": True,
    "limits": [
        "两个节点都是**教科书尺度参数**，量级参照公开工艺讨论，**不是任何 foundry PDK 数值**",
        "`device_scale` 只缩几何坐标；器件电学（V_th/迁移率/电容）**不随节点变**，"
        "所以节点间的延迟/功耗数字**不可比**，只有**几何容量**可比",
        "DEMO28 的金属规则（W=70/S=70/VIA=50）来自量级估算，未与任何真实 PDK 校准",
        "「行内可用轨道数」是几何派生量（避开 pin pad 后的空闲带），"
        "不含 DRC 的其余约束（如最小面积、密度、OPC）",
        "净增 0 锚（计数派生 ⇒ resid≡0）⇒ 门禁形态",
    ],
}
