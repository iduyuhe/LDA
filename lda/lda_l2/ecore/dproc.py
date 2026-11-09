"""E53 · **工艺规则的运行期切换**（`use()`）—— 让同一份布线/DRC 实现服务不同节点。

═══════════════════════════════════════════════════════════════════════════════
为什么需要它（可复用/可扩展的核心）
───────────────────────────────────────────────────────────────────────────────
本仓的布线器 (`dpnr`) 与 DRC (`ddrc_lvs`/`ddetail`) 读的都是**模块级常量**：
`PITCH / W / EXT / S_MIN / ENC / VIA`。这让「换一个工艺节点」变成改一堆文件。

`use(node)` 把这些量在**一个上下文内**整体切换，退出时逐项还原：
  · 调用方不必改任何实现代码；
  · 默认不进入 ⇒ 现有 388 道门禁读到的是原值，行为逐位不变；
  · 规则来源是 `dnode.Node`（唯一真源），不在这里重抄数字。

🔴 **为什么不是「再造一套 HD 布线器」**：两份实现必然漂移 —— 上一轮 `dnode.tracks_for`
自己重算 `T` 就已经踩过一次（两份真源）。所以这里只做「参数切换」，算法一份。

═══════════════════════════════════════════════════════════════════════════════
诚实边界
───────────────────────────────────────────────────────────────────────────────
1. 🔴 这是**运行期可变状态**，非线程安全。本仓的门禁都是单进程串行跑，可以接受；
   但任何并发/异步路径都**不得**在 `use()` 上下文内工作（本仓无此路径）。
2. 🔴 切换的是**规则数值**，不是**算法能力**：换到 28nm 规则不会让路由器变聪明，
   它只是让「同样的算法」在更密的资源下跑 —— 这正是我们要测的东西。
3. 🔴 退出时按保存值还原到**字节级相同**（含 float），由判据 `d09` 机核。
"""
from __future__ import annotations

import contextlib

from . import ddetail as DD
from . import ddrc_lvs as DL
from . import dnode as DN
from . import dpnr as PN

#: `use()` 会动到的全部属性（顺序无关；判据据此做「退出后逐项还原」检查）
#: 🔴 Q2（v0.9.396）删掉三项：`dpnr.EXT` / `dpnr.PAD_HALF` / `dpnr.M2_HALF`。
#:   它们是**同一个量的三份副本**，且都是 import 期求值的常量 —— 在这里 setattr
#:   只能改副本、改不到几何发射点（二阶早绑定的温床）。现在它们统一由 `dpnr.pad_half()`
#:   从 `ddetail.VIA` / `ddrc_lvs.ENC` 现取 ⇒ 下面两条真源一旦被替换，几何立刻跟着变。
TOUCHED = (
    ("ddetail", "W_ROUTE"), ("ddetail", "VIA"), ("ddetail", "TRACK_PITCH"),
    ("ddrc_lvs", "S_MIN"), ("ddrc_lvs", "ENC"), ("ddrc_lvs", "W_MIN"),
    ("dpnr", "PITCH"), ("dpnr", "W"),
    ("dpnr", "CELL_GAP_UM"), ("dpnr", "CH_UM"),
)

_MODS = {"ddetail": DD, "ddrc_lvs": DL, "dpnr": PN}


def snapshot() -> dict:
    """当前规则快照（用于「还原是否逐位一致」的机核）。"""
    return {(m, a): getattr(_MODS[m], a) for (m, a) in TOUCHED}


def diff(before: dict, after: dict = None) -> list:
    """快照差异（空列表 = 完全还原）。`None` 表示取当前值。"""
    now = snapshot() if after is None else after
    return [(k, before[k], now[k]) for k in before if before[k] != now[k]]


@contextlib.contextmanager
def use(node, channel_um: float = None, cell_gap_um: float = None, lib=None):
    """在上下文内把布线/DRC 规则切到 `node`（`dnode.Node` 或其名字）。

    · `channel_um`：行间通道高度，默认按节点节距取 `4 × pitch`（给足 4–5 条轨道）；
    · `cell_gap_um`：单元间距，默认 `1 × pitch`（行内布线之后不再需要靠间隙换可达性）。
    """
    nd = DN.get(node) if isinstance(node, str) else node
    r = nd.route_rules()
    pitch, w, s = r["pitch"], r["w_min"], r["s_min"]
    via, enc = r["via"], r["enc"]
    # 🔴 Q2：缺省通道高与单元间距都**按派生规则**取（不写字面量、不用 1×pitch 的第二套规则）：
    #    通道要装 `TRACKS_TARGET` 条轨道；间距 = `GAP_K·pitch − 单元宽`（与 `dpnr` 同一规则）。
    ch = ((PN.TRACKS_TARGET - 1) * pitch + w + PN.DELTA_ESCAPE) \
        if channel_um is None else float(channel_um)
    gap = (PN.GAP_K * pitch - PN.CELL_W_UM) if cell_gap_um is None else float(cell_gap_um)

    saved = snapshot()
    saved_lib = (PN.CL, dict(PN.CELL_MAP))
    try:
        if lib is not None:
            PN.CL = lib
            PN.CELL_MAP = dict(lib.CELL_MAP)
        DD.W_ROUTE, DD.VIA, DD.TRACK_PITCH = w, via, pitch
        DL.S_MIN, DL.ENC, DL.W_MIN = s, enc, w
        PN.PITCH, PN.W = pitch, w
        # 🔴 pad 半宽 / 金属延伸量**不再在这里赋值**：它由 `dpnr.pad_half()` 从
        # `DD.VIA` / `DL.ENC`（上面两行已替换）现取。旧写法 `PN.PAD_HALF = via/2+enc`
        # 是在切换点算一次、把结果盖到模块常量上 —— 一旦几何发射点读的是自己那份副本，
        # 切换就失效（v0.9.394 实测：`VIA 0.20→0.30` 时 `PAD_HALF` 仍报 0.1200）。
        PN.CELL_GAP_UM, PN.CH_UM = gap, ch
        yield {"node": nd.name, "pitch": pitch, "w": w, "s": s, "via": via,
               "enc": enc, "channel_um": ch, "cell_gap_um": gap}
    finally:
        for (m, a), val in saved.items():
            setattr(_MODS[m], a, val)
        PN.CL, PN.CELL_MAP = saved_lib[0], saved_lib[1]


DPROC_DISCLOSURE = {
    "what": "运行期把布线/DRC 规则切到指定节点（同一份算法，参数可换）",
    "claimable": False,
    "not_thread_safe": True,
    "limits": [
        "运行期可变状态，**非线程安全**；只在单进程串行门禁内使用，退出时逐项还原",
        "只切规则数值，不改变算法能力 —— 换节点不会让路由器变聪明",
        "不切器件电学（W/L/方块电阻仍取 dcells 的值）⇒ 跨节点的延迟/功耗不可比",
        "净增 0 锚 ⇒ 以门禁形态落地",
    ],
}
