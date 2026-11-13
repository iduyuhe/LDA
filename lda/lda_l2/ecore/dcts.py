# -*- coding: utf-8 -*-
"""F3-1 · 时钟树综合（CTS）一阶模型：拓扑枚举 + 闭式延迟 + 每端点到达时间 + skew。

═══════════════════════════════════════════════════════════════════════════════
这个模块要证明什么 / 不证明什么
───────────────────────────────────────────────────────────────────────────────
✅ 证明：给定 N 个时钟接收端，**拓扑可以被枚举穷尽**，且「总延迟最小」的拓扑是
   `(级数, 扇出)` 的闭式解；每个端点的到达时间与 **skew** 由「每级扇出不均」决定，
   而不是拍脑袋给一个数。
❌ 不证明：不建模叶段线载（`wire_modeled=False`）、不布线、不做 PVT、不是 SPICE。
   `claimable=False`。

═══════════════════════════════════════════════════════════════════════════════
为什么 `insertion delay` 与 `skew` 必须分开报（F3 立项论证的核心事实）
───────────────────────────────────────────────────────────────────────────────
`T_ref(cim_ctrl) = 715.024 ps` ⇒ 5% 预算 = 35.751 ps。
56 端点的**插入延迟闭式下界 = 47.589 ps**（3 级 × 4 扇出），**必然超 5%** ——
根因是 `t_intr = 2.0 ps`/级 + `cin = 1.0 fF`，与实现优劣无关（枚举 1–8 级 × 2–16 扇出
的全部 120 个组合，最优即 47.589 ps）。

而 `skew`（端点之间到达时间的差）在对称/均匀分配下只有「最后一级扇出差一格」的量级
≈ 3.466 ps << 35.751 ps。
⇒ 行业标准的「skew ≤ 5% 周期」是**可满足的**；把 5% 卡在插入延迟上则是**不可满足的判据**。
用户已拍板 D8：硬判据卡 **skew**，`insertion delay` 独立披露、不设 5% 上限。

═══════════════════════════════════════════════════════════════════════════════
为什么时钟负载要自算
───────────────────────────────────────────────────────────────────────────────
`dsta.loads_of` 刻意 `continue` 掉 DFF 与 `"CLK"`（时钟不计入组合负载）⇒
若复用它会得到「时钟网负载恒 0」的假象。本模块按「每个内部节点的负载 = 子节点数 × CIN_FF」
自算，并把 `CIN_FF` 作为显式常量披露。

═══════════════════════════════════════════════════════════════════════════════
D7：源与汇是两个网名
───────────────────────────────────────────────────────────────────────────────
本项目现状：`nl.clocks = ('clk',)`（小写，primary input），而 DFF 的时钟脚接大写 `'CLK'`，
`'CLK'` **没有任何驱动源**。`_validate_clock` 做三条 fail-closed 校验后**显式登记
`bridged=True`**（「这两个网被当作同一时钟域」），**不改网表**。
"""
from __future__ import annotations

from . import dcell as DC

#: 🔴 **不写 `ANCHORABLE`**：本仓 ecore 侧（光子/电子）的模块一律不写该声明
#: （它是量子侧「模块即被判对象」的约定）⇒ 本模块**不进** `capability_modules()`，
#: 不触发 G7 反向锁定。净增 0 锚（避免 ledger 与 zero_resid 棘轮被牵动）。

#: 拓扑搜索空间（闭区间）。判据 EC-G43 用 `cell_delay_ps` 独立复算，不读这两组常量。
TOPO_LV_RANGE = (1, 8)
TOPO_FO_RANGE = (2, 16)

#: 🔴 以下三个常量**只用于搜索排序与披露**，不用于判据结论：
#: `T_INTR_PS` / `K_PS_PER_FF` 是 `dcell.cell_delay_ps("BUF", load)` 的闭式系数
#: （`2.000 + 3.465×load`），一旦 `dcell` 漂移，EC-G43 的「两条路径一致」立刻红。
T_INTR_PS = 2.000
K_PS_PER_FF = 3.465
CIN_FF = 1.00                    # fF · 每个扇入引脚的等效电容

#: 叶段线载（**本批不建模**，只登记参数与公式，不给结果——避免「编数」）
C_WIRE_FF_PER_UM = 0.20

DCTS_DISCLOSURE = {
    "basis": "FIRST_ORDER_CTS",
    "delay_model": "dcell.cell_delay_ps(cell, fanout*CIN_FF)，每级独立累加",
    "wire_modeled": False,
    "wire_note": ("叶段线载未建模：C_WIRE=%g fF/um；额外门延迟按 "
                  "cell_delay_ps('BUF', 1+C_WIRE*L_um) - cell_delay_ps('BUF',1) 现算"
                  % C_WIRE_FF_PER_UM),
    "clock_load": ("自算（dsta.loads_of 刻意排除 DFF 与 CLK ⇒ 不能复用）"),
    "not_modeled": "叶段线载 / 真布线 / PVT / 串扰 / 时钟门控 / 多时钟域",
    "claimable": False,
}


def _level_delay_ps(fanout: int, cell: str = "BUF") -> float:
    """一级缓冲驱动 `fanout` 个同类输入的延迟（ps）—— 直接问 `dcell`，不自造公式。"""
    return DC.cell_delay_ps(cell, fanout * CIN_FF)


def _plan_tree(n_sinks: int, cell: str = "BUF") -> dict:
    """枚举 (级数, 扇出)，返回**总延迟最小**的可行拓扑。

    可行性 = `leaves >= n_sinks`（不要求恰好相等）。
    `n_sinks <= 1` ⇒ 抛错（一个端点不需要树）。
    `n_buf_repr` 是**满树**的缓冲数上界；实际点数在 `build_clock_tree` 里按需分配后更少。
    """
    if n_sinks <= 1:
        raise ValueError("plan_tree: n_sinks=%r ≤ 1，不需要时钟树" % (n_sinks,))
    best = None
    for lv in range(TOPO_LV_RANGE[0], TOPO_LV_RANGE[1] + 1):
        for fo in range(TOPO_FO_RANGE[0], TOPO_FO_RANGE[1] + 1):
            leaves = fo ** lv
            if leaves < n_sinks:
                continue
            per = _level_delay_ps(fo, cell)
            tot = per * lv
            if best is None or tot < best["_tot"] - 1e-12:
                best = {"_tot": tot, "lv": lv, "fanout": fo, "leaves": leaves,
                        "n_buf_repr": sum(fo ** i for i in range(lv)),
                        "per_level_ps": [round(per, 9)] * lv,
                        "delay_ideal_ps": round(tot, 9), "feasible": True}
    if best is None:                       # 搜索空间不足（n_sinks 过大）
        raise ValueError("plan_tree: %d 端点在搜索空间 %r×%r 内无可行拓扑"
                         % (n_sinks, TOPO_LV_RANGE, TOPO_FO_RANGE))
    best.pop("_tot", None)
    return best


def _clock_sinks(nl, sink_net: str = "CLK") -> list:
    """找出所有「把 `sink_net` 当输入」的端点：`[(gate_name, pin_index), ...]`。

    端点数为 0 ⇒ 抛错（fail-closed）：**不返回空树**，因为空树的 skew=0 会被误读成「完美」。
    """
    out = []
    for g in nl.gates:
        for i, n in enumerate(g.ins):
            if n == sink_net:
                out.append((g.name, i))
    if not out:
        raise ValueError("clock_sinks: 没有任何门把 %r 当输入（fail-closed，不返回空树）"
                         % (sink_net,))
    return out


def _validate_clock(nl, source_port: str, sink_net: str) -> dict:
    """D7 三条 fail-closed 校验 + 显式桥接登记（**不改网表**）。

    ① 源必须是 primary input；
    ② 汇必须真的被 >=1 个门引用；
    ③ 两者是**两个不同的网名**时，显式登记 `bridged=True`，不假装同源。
    """
    ports = sorted({p for p, _w in nl.inputs})
    if source_port not in ports:
        raise ValueError("clock 源 %r 不是 primary input（可选 %r）"
                         % (source_port, ports))
    sinks = _clock_sinks(nl, sink_net)
    return {"source_port": source_port, "sink_net": sink_net,
            "n_sinks": len(sinks), "bridged": True,
            "bridge_note": ("源与汇是两个网名（%r vs %r）：本函数只做显式桥接登记，"
                            "不改网表、不假装同源" % (source_port, sink_net))}


def build_clock_tree(nl, source_port: str = "clk", sink_net: str = "CLK",
                     cell: str = "BUF", t_ref_ps: float = None) -> dict:
    """完整时钟树：拓扑 + 负载 + 每级延迟 + 每端点到达时间 + skew。

    🔴 `skew_ps` 与 `delay_ps` **分开报**：前者是端点之间的到达差，后者是插入延迟。
    给 `t_ref_ps` 时额外报 `budget_5pct_ps = 5% × t_ref_ps` 与 `skew_ok`；
    **不对 `delay_ps` 设 5% 上限**（D8 拍板：旧写法不可满足，见模块 docstring）。
    """
    meta = _validate_clock(nl, source_port, sink_net)
    n = meta["n_sinks"]
    topo = _plan_tree(n, cell)
    lv, fo = topo["lv"], topo["fanout"]

    # ── 按需分配每级节点数：底部是 n 个叶，往上每级 ceil(remain / fo^(剩余级数)) ──
    need = [1]
    for i in range(1, lv + 1):
        up = -(-n // (fo ** (lv - i)))          # ceil(n / fo^(lv-i))，倒推该级所需节点
        need.append(min(up, fo ** i))
    need[lv] = n                                # 叶数就是端点数（不取 fo^lv 的空位）

    # ── 每级：把子节点尽量平均分给父节点（余数给前 extra 个）──
    fanouts = []
    for i in range(1, lv + 1):
        base, extra = divmod(need[i], need[i - 1])
        fanouts.append([base + 1] * extra + [base] * (need[i - 1] - extra))

    # ── 逐级传播到达时间：叶的到达 = 其父（最后一级缓冲）的到达 ──
    arrive = [[0.0] * need[0]]
    per_level = []
    for i in range(lv):
        lvl = []
        child = []
        for p, f in enumerate(fanouts[i]):
            d = _level_delay_ps(f, cell)
            lvl.append(d)
            for _ in range(f):
                child.append(arrive[i][p] + d)
        arrive.append(child)
        per_level.append(round(max(lvl), 9))

    sink_arr = arrive[lv][:n]
    if len(sink_arr) != n:
        raise ValueError("内部错误：叶到达时间 %d ≠ 端点数 %d" % (len(sink_arr), n))
    delay = max(sink_arr)
    skew = delay - min(sink_arr)
    spread = max(max(f) for f in fanouts) - min(min(f) for f in fanouts)

    out = dict(meta)
    out.update({
        "lv": lv, "fanout": fo, "levels": need,
        "n_buf": sum(need[:-1]),
        "n_buf_repr": topo["n_buf_repr"],
        "fanout_spread": spread,
        "per_level_ps": per_level,
        "delay_ps": round(delay, 9),
        "skew_ps": round(skew, 9),
        "arrive_ps": [round(a, 9) for a in sink_arr],
        "cell": cell,
        "t_ref_ps": t_ref_ps,
        "budget_5pct_ps": None if t_ref_ps is None else round(t_ref_ps * 0.05, 9),
        "skew_ok": None if t_ref_ps is None else bool(skew <= t_ref_ps * 0.05),
        "delay_is_displayed": True,      # 插入延迟必须并排报（不许只报 skew）
        "wire_modeled": False,
        "wire_note": DCTS_DISCLOSURE["wire_note"],
        "claimable": False,
    })
    return out
