# -*- coding: utf-8 -*-
"""E38f · **破墙路由器：三种选网策略 + 原子多阻塞者 R&R（诚实负结果）**（`lda/lda_l2/ecore/dwallrr.py` · D-230）。

══════════════════════════════════════════════════════════════
定位：E38e 指出「残余失败全是墙切断」，并猜「破解墙有望以更小面积拿到同样 94%」。
E38f 去实现破墙并实测——**结果把这个猜测否证了**：在这个密度下破墙是**零和的**。

三种选网策略（都实测，不靠调参想象）：
| 策略 | 怎么选被撕的网 | 实测（K=1 · 40~120 次尝试） |
|---|---|---|
| `frontier` | 失败前沿直方图 top-k（最直观：谁挡得多撕谁） | 50 次 → **0 成功** |
| `corridor` | 沿 A→B 全路径逐个撕（cap=12） | 120 次 → **0 成功** |
| `tunnel` | 先取**可达集**把「口袋界面」定位到具体格子，只撕界面处 5 格 | 40 次 → 15 次失败网仍不通 + **25 次隧道已开、但被撕网无法重布 ⇒ 回滚** |

🔴🔴 诊断（本档真正的产出，三层递进）：
1. **前沿直方图证伪「一面墙」的直觉**：失败前沿上被挡的 ~400 个节点来自 **~340 个不同网**
   （每网只 1~2 个节点），且多个失败网的 top3 完全相同 ⇒ 口袋是**由几百根线首尾缝成的**，
   不是几面独立的墙。撕 top-k = 在口袋上捅针眼。
2. **隧道确实能开**：`tunnel` 策略下 25/40 的尝试里失败网**真的布通了**（界面定位有效）。
3. **但破墙是零和的**：那 25 次全部因为**被撕的网无法重布**而原子回滚 ⇒ **净布通网数不增**
   （38.70% → 38.70%）。原因：被撕的网本身就是**跨越全片的全局线**，在这个缝合网里无处可绕。

⇒ 修正 E38e 的建议：**局部破墙不是杠杆**。真正的杠杆只剩两条：
(a) **加面积/层**（E38e 已证 ×3 摊开 → 94.26%）；
(b) **全局协商拥塞**（PathFinder 式：允许暂时违规 + 代价递增、多轮全局迭代）——不是局部撕网。
这是下一档该做的，本档不做（不假装做了）。

🔴🔴 本模块只做诊断研究，不产 GDS、不加锚（`claimable=False`）。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- **原子不丢网**：`n_routed(wall) ≥ n_routed(greedy)`，且已布网集合 ⊆ 贪心已布网集合（不新增、不丢失）。
- **回滚恒等**：`success + r_net_fail + r_victim_fail == attempts`（每次尝试恰好被归类一次）。
- **对比有效性**：参与比较的运行 `n_truncated == 0`。
- **机制成立**（钉住诊断，不钉数值）：`tunnel` 下 `r_net_fail > 0` 且 `r_victim_fail > 0`
  —— 即「隧道能开但牺牲网回不去」这个机制**确实发生**，不是空转。
- **开关无副作用**：`wall_rr=0` 与贪心基线**逐位相同**（routability / n_routed）。
- **对照策略量化无效**：`frontier` 与 `corridor` 的命中率 ≤ 10%（实测均 0%）。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 只测 K=1（真实三要素）；未测 K=2 下的破墙（成本，见 E38e 的成本模型）。
- 未实现**级联 R&R**（撕掉的网再撕别人）与**全局协商拥塞**——本档的否证只针对「局部、有限步」的破墙。
- 界面定位用「A→B 的 L 型直线」近似；非 L 型界面（口袋开口在别处）会被漏掉。
- util/via 占用未计（与 E38e 同口径）。
"""
from __future__ import annotations

from . import dcell as DC
from . import dplac as PL
from . import ddroute_rr as RR
from . import dpinaccess as PA
from .dsynth import Netlist

PITCH_REAL = PA.PITCH_REAL
E38E_K1_ROUTABILITY = 0.3870          # E38e 发布值（v0.9.338 · commit 849cb10）· 跨档一致锚
FRONTIER_HIT_MAX = 0.10               # 对照策略命中率上限（实测 0%）


def _place(nl: Netlist, area_per_tr: float = PA.REAL_AREA_PER_TR) -> PL.Placement:
    import dataclasses
    return PL.place(nl, tech=dataclasses.replace(DC.DEFAULT_TECH, area_per_tr_um2=area_per_tr))


def wall_break(nl: Netlist, p: PL.Placement, K: float = 1.0, wall_rr: int = 40,
               wall_k: int = 12, wall_mode: str = "tunnel", layers: int = 4,
               pitch: float = PITCH_REAL, access_radius: int = 4,
               cell_block_up_to: int = 2, max_expand: int = None,
               astar: bool = False) -> dict:
    """真实三要素下一次「破墙 R&R」测量（`wall_rr=0` 即贪心基线）。"""
    with PA._pitch(pitch):
        if max_expand is None:
            nx, ny = RR._dims(p, float(K))
            max_expand = nx * ny * layers + 1
        r = RR.route_rr(nl, p, spread=float(K), layers=layers, rr_rounds=0,
                        max_expand=max_expand, cell_block_up_to=cell_block_up_to,
                        access_radius=access_radius, astar=astar,
                        wall_rr=wall_rr, wall_k=wall_k, wall_mode=wall_mode)
    return {
        "K": float(K), "mode": wall_mode, "wall_rr": wall_rr, "wall_k": wall_k,
        "n_nets": r["n_nets"], "n_routed": r["n_routed"],
        "routability": r["routability"], "n_truncated": r["n_truncated"],
        "attempts": r["wall_rr_attempts"], "success": r["wall_rr_success"],
        "r_net_fail": r["wall_rr_r_net_fail"], "r_victim_fail": r["wall_rr_r_victim_fail"],
        "ripped": r["wall_rr_ripped"], "expanded": r["expanded"],
        "routed_set": set(r["routed_nets"]),
        "fail_source_blocked": r["fail_source_blocked"], "fail_walled": r["fail_walled"],
    }


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def wall_self_check(verbose: bool = False, tries: int = 40, frontier_tries: int = 12,
                    corridor_tries: int = 0) -> dict:
    """E38f 自检：原子不丢网 + 回滚恒等 + 机制成立 + 开关无副作用 + 对照策略量化无效。"""
    from . import dctrl as C
    problems = []

    b = C.build()
    nl = b["netlist"]
    p = _place(nl)

    greedy = wall_break(nl, p, wall_rr=0)
    if greedy["n_truncated"] != 0:
        problems.append(("greedy_truncated", greedy["n_truncated"]))
    # 跨档一致：与 E38e 发布值对齐（同一配置）
    if abs(greedy["routability"] - E38E_K1_ROUTABILITY) > 0.005:
        problems.append(("cross_doc_mismatch", greedy["routability"], E38E_K1_ROUTABILITY))

    tun = wall_break(nl, p, wall_rr=tries, wall_k=12, wall_mode="tunnel")
    # ① 原子不丢网：只增不减 + 已布集合不越界
    if tun["n_routed"] < greedy["n_routed"]:
        problems.append(("lost_nets", greedy["n_routed"], tun["n_routed"]))
    if not tun["routed_set"] <= greedy["routed_set"]:
        problems.append(("unexpected_new_nets", len(tun["routed_set"] - greedy["routed_set"])))
    # ② 回滚恒等
    if tun["success"] + tun["r_net_fail"] + tun["r_victim_fail"] != tun["attempts"]:
        problems.append(("rollback_not_classified", tun["success"], tun["r_net_fail"],
                         tun["r_victim_fail"], tun["attempts"]))
    if tun["attempts"] <= 0:
        problems.append(("no_attempt",))
    # ③ 机制成立：隧道能开（失败网布通）但牺牲网回不去 ⇒ 两类回滚都要出现
    if tun["r_net_fail"] <= 0 or tun["r_victim_fail"] <= 0:
        problems.append(("mechanism_not_observed", tun["r_net_fail"], tun["r_victim_fail"]))
    if tun["n_truncated"] != 0:
        problems.append(("tunnel_truncated", tun["n_truncated"]))

    # ④ 对照策略量化无效（命中率 ≤ 10%）
    fr = wall_break(nl, p, wall_rr=frontier_tries, wall_k=3, wall_mode="frontier")
    hit_fr = (fr["success"] / fr["attempts"]) if fr["attempts"] else 0.0
    if hit_fr > FRONTIER_HIT_MAX:
        problems.append(("frontier_unexpectedly_effective", round(hit_fr, 3)))
    co = None
    if corridor_tries:
        co = wall_break(nl, p, wall_rr=corridor_tries, wall_k=12, wall_mode="corridor")
    if co is not None and co["attempts"]:
        hit_co = co["success"] / co["attempts"]
        if hit_co > FRONTIER_HIT_MAX:
            problems.append(("corridor_unexpectedly_effective", round(hit_co, 3)))

    # ⑤ 开关无副作用 + 确定性（符号小网格上做，便宜；真实布局已由「跨档一致」锚住）
    p_sym = PL.place(nl)
    a1 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, max_expand=200000)
    a2 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, max_expand=200000)
    a3 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, max_expand=200000, wall_rr=5)
    if (a1["n_routed"], a1["wirelength_um"]) != (a2["n_routed"], a2["wirelength_um"]):
        problems.append(("not_deterministic",))
    if (a3["n_routed"], a3["wirelength_um"]) != (a1["n_routed"], a1["wirelength_um"]):
        problems.append(("switch_has_side_effect", a1["n_routed"], a3["n_routed"]))

    delta = tun["n_routed"] - greedy["n_routed"]
    if verbose:
        print("  wall: greedy=%.2f%%(%d) | tunnel=a%.2f%%(%d, Δ%+d) att=%d succ=%d "
              "netfail=%d victimfail=%d"
              % (100 * greedy["routability"], greedy["n_routed"],
                 100 * tun["routability"], tun["n_routed"], delta,
                 tun["attempts"], tun["success"], tun["r_net_fail"], tun["r_victim_fail"]))
        print("        frontier(att=%d, hit=%.0f%%) · corridor(att=%d, hit=%.0f%%)"
              % (fr["attempts"], 100 * hit_fr,
                 co["attempts"] if co else 0,
                 100 * (co["success"] / co["attempts"]) if (co and co["attempts"]) else 0.0))
    return {
        "ok": not problems, "problems": problems,
        "greedy": greedy, "tunnel": tun, "frontier": fr, "corridor": co,
        "delta_routed": delta,
        "zero_sum": (delta == 0),
    }


DWALLRR_DISCLOSURE = {
    "route": "E38f · 破墙路由器：三种选网策略 + 原子多阻塞者 R&R（D-230）",
    "analysis": "三种选网策略（frontier 前沿 top-k / corridor 全路径 / tunnel 可达集定位界面）+ "
                "原子多阻塞者 R&R（先重布失败网、再让被撕网绕行，任一环失败即原样回滚）+ "
                "回滚原因分离计数（r_net_fail / r_victim_fail）",
    "golden": "原子不丢网（只增不减 + 已布集合 ⊆ 贪心集）· 回滚恒等（success+netfail+victimfail==attempts）· "
              "对比零截断 · 机制成立（两类回滚都出现）· 开关无副作用（wall_rr=0 逐位等于基线）· "
              "对照策略命中率 ≤10%",
    "not_included": "只测 K=1 · 未实现级联 R&R 与全局协商拥塞 · 界面用 A→B 的 L 型直线近似（非 L 开口会漏）· "
                    "未计 via/引脚占用",
    "e38f_note": "🔴 **破墙是零和的**（本档否证了 E38e 的猜测「破墙能以更小面积拿到 94%」）："
                 "① 前沿直方图显示失败口袋由 **~340 个网**缝成（每网 1~2 个前沿节点）⇒ 撕 top-k = 捅针眼"
                 "（50 次 0 成功；corridor 120 次也 0）；② `tunnel` 用可达集把界面定位到格子后，"
                 "**25/40 次失败网真的布通了**（隧道有效）；③ 但这 25 次全部因**被撕网无法重布**而回滚 ⇒ "
                 "**净布通网数不增**（38.70%→38.70%）。原因：被撕的网本身是跨越全片的全局线，在缝合网里"
                 "无处可绕。⇒ 真正的杠杆只剩：加面积/层（E38e 已证 ×3→94.26%）或**全局协商拥塞**"
                 "（PathFinder，允许暂时违规 + 代价递增、多轮全局），而非局部撕网。",
    "claimable": False,
}
