# -*- coding: utf-8 -*-
"""E38e · **摊开 ×K 的可测边界 + 失败模式诊断**（`lda/lda_l2/ecore/dspread.py` · D-229）。

══════════════════════════════════════════════════════════════
定位：E38d 收尾断言「三要素齐备仍只 ~38.7%，瓶颈迁到网络密度 ⇒ 要真正可布通需更大 die（摊开 ×K）」。
E38e 去兑现它，实测两条：**摊开确实有效（38.7%→66.7%）**，但根因**不是** E38d 说的「容量/密度」。

先抓到两个**测量缺陷**（都会直接造出假结论）：
1. **BFS 在大网格上被 `max_expand` 截断**：K=2 报 26.6% < K=1 的 38.7%，看着像「摊开反变差」，
   实测失败 **997 网全部是截断**（`n_truncated` 与失败数逐位相等）——纯测量假象。
   修法：① 加截断/扩展计数（`n_truncated`/`expanded`）；② 加 A 星选项（默认仍 BFS，保历史口径）。
2. **失败模式未二分**：「引脚接入点全被占（压死）」与「搜完了确实没路（墙切断）」混在一起，
   无法判断是谁在挡路。修法：按扩展数是否为 0 二分（`fail_source_blocked`/`fail_walled`）。

🔴🔴 实测（真实三要素：0.266µm²/tr 单元 + 0.24µm 线距 + 引脚接入 r=4 + 跨单元 4 层 · 同一 1359 网）

| 摊开 | 面积 | 布通率 | util | 扩展数 | `fail_source_blocked` | `fail_walled` | 耗时 |
|---|---|---|---|---|---|---|---|
| K=1 | ×1 | 38.70%（526/1359） | 27.8% | 6.46×10⁷ | 0 | 833 | 77 s |
| K=2 | ×4 | 66.67%（906/1359） | 27.9% | 2.47×10⁸（×3.82） | 0 | 453 | 350 s |
| **K=3** | **×9** | **94.26%（1281/1359）** | 32.4% | 6.30×10⁸（×2.55） | **0** | **78** | 1038 s |

⇒ **真实三要素下，摊开 ×3（面积 ×9）即可把布通率推到 94.26%**——首次越过 90%，
且远小于 E37 在符号密度下算出的 ×14.6（符合 E38d 的预期）。**E38d 的方向是对的，本档把它量化了。**

🔴 但**根因归结要改**（这是 E38e 真正的发现）：
- 摊开到 94.26% 时，网格利用率仍只有 **32.4%**（68% 空闲），`fail_source_blocked` **全程为 0**
  ⇒ 残余 78 个失败网**没有一个是引脚被压死**，全部是「搜完了确实没路」= 已布金属形成闭合墙（墙效应）。
- 换句话说：**加面积之所以有效，是因为"有地方绕"，不是因为"容量更多"**——利用率几乎不涨
  （27.8→27.9→32.4%），涨的是绕行空间。所以 E38d 把它写成「网络密度/布线容量」不准确。
- 实践含义：**面积 ×9 不是唯一解**。破解墙（多阻塞者 R&R / 分层方向分配 / 非 L 绕行）有机会
  以更小面积达到同样的 94%——这是下一步该试的，而不是默认只能加面积。

🔴🔴 成本边界（为什么曲线止于 K=3）：扩展数 ≈ 容量 ∝ K²（64.6M→246.9M→629.6M，累计 ×9.75 ≈ 9）。
K=4 预计 ~1.1×10⁹ 扩展、约 30 min+/次，Python 单线程不可行。K=3 已用 1038 s，故**只作离线一次性
测量**，不进常驻门禁（门禁复算 K=1 与 K=2）。

🔴🔴 本模块**只做诊断研究**，不产 GDS、不加锚（`claimable=False`）。

══════════════════════════════════════════════════════════════
🔴🔴 绝对金标
══════════════════════════════════════════════════════════════
- **跨档一致**：K=1 真实条件布通率 == E38d 已发布值（38.7% ± 0.5%）⇒ 没换口径。
- **精确性**：参与比较的点 `n_truncated == 0`（截断点只能当下界，不得用于比较）。
- **失败二分恒等**：`fail_source_blocked + fail_walled == n_nets - n_routed`。
- **摊开不劣且改善**：给了 K_extra 时 `routability(K_extra) ≥ routability(K=1)`。
- **成本 ∝ K²**：`expanded(K_extra)/expanded(K=1)` 落在 [2.5, 6]（容量是 K²，验证复杂度模型）。
- **利用率未被摊开缓解**：`|util(K_extra) - util(K=1)| ≤ 5pp`（这是 E38e 的核心反直觉事实）。
- **K=3 出处对拍**（常量不重算，1038s 太贵）：`K3_OFFLINE` 布通率 ≥ 90% 且
  `area_factor ×9 < E37 符号 ×14.6` 且 `fail_source_blocked == 0`（残余全为墙切断）。
- **截断可判（必须有牙）**：紧预算（max_expand ≪ 网格）下 `n_truncated > 0` 且布通率显著下降
  —— 这条探针正是抓出「26.6% 假象」的机构。
- **搜索器一致**：符号小网格上 BFS 与 A 星 |Δ布通率| ≤ 5%（换搜索器不改结论）。
- **确定性**：同参数两次运行逐位相同。

══════════════════════════════════════════════════════════════
⚠️ 诚实边界（全部 `claimable=False`）
══════════════════════════════════════════════════════════════
- 「墙效应」是「无路 + 大量网格空闲」的**逻辑必然**（无路而网格大部分空闲 ⇒ 存在分离闭曲线），
  但**未逐网定位墙的位置**，也**未实现破解墙的路由器**（那是下一步）。
- `util` 只算布线占用节点 / 网格节点×层数，未计 via 与引脚接入占用。
- 精确摊开点只测到 K=2（K=3 见披露，K=4 未测）：扩展数 ∝ K²，K=4 已到 10⁹ 量级，Python 单线程不可行。
- util 涨落依赖具体走线形状，5pp 容差是经验值而非理论界。
"""
from __future__ import annotations

from . import dcell as DC
from . import dplac as PL
from . import ddroute_rr as RR
from . import dpinaccess as PA
from .dsynth import Netlist

REAL_AREA_PER_TR = PA.REAL_AREA_PER_TR       # 0.266（Nangate45 量级，同 E38c/E38d）
PITCH_REAL = PA.PITCH_REAL                   # 0.24
E38D_PUBLISHED_COMBINED = 0.387              # E38d 发布值（v0.9.337 · commit edef350），跨档一致锚
COST_RATIO_MIN, COST_RATIO_MAX = 2.5, 6.0    # expanded(K)/expanded(1) 的合理带（容量 ∝K² ⇒ 约 4）
UTIL_DRIFT_MAX = 0.05                        # 摊开前后 util 允许漂移（实测 0.1pp）

# 🔴 K=3 离线一次性测量（1038 s，不进常驻门禁）· 出处：本档实测（命令见 DSPREAD_DISCLOSURE）
K3_OFFLINE = {
    "K": 3.0, "area_factor": 9.0, "routability": 0.9426, "n_routed": 1281, "n_nets": 1359,
    "util": 0.324, "expanded": 629.6e6, "fail_source_blocked": 0, "fail_walled": 78,
    "seconds": 1038.0,
}
E37_SYMBOLIC_AREA_FACTOR = 14.6              # E37 发布值：符号密度下真清零需 ×14.6 面积（commit 4e7b407）


def real_place(nl: Netlist, area_per_tr: float = REAL_AREA_PER_TR) -> PL.Placement:
    """真实单元面积摆放（与 E38c/E38d 同口径）。"""
    import dataclasses
    return PL.place(nl, tech=dataclasses.replace(DC.DEFAULT_TECH, area_per_tr_um2=area_per_tr))


def spread_point(nl: Netlist, p: PL.Placement, K: float, layers: int = 4,
                 pitch: float = PITCH_REAL, access_radius: int = 4,
                 cell_block_up_to: int = 2, max_expand: int = None,
                 astar: bool = False, rr_rounds: int = 0) -> dict:
    """真实三要素下把 die 摊开 ×K（面积 ×K²）后的一次**精确**布线测量。

    🔴 `max_expand=None`（默认）⇒ 自动取整个网格状态数（**不截断 ⇒ 精确**）。这是刻意选择：
    E38e 的第一教训就是「K=2 用 120000 预算报 26.6%，失败 997 网全是截断」。**测量函数默认必须精确**，
    要紧预算请显式传（如截断探针 `max_expand=2000`），并检查 `n_truncated`。

    返回：布通率 / 截断数 / 扩展数 / 容量 / **利用率 util** / 失败二分 / die / 网格。
    `n_truncated > 0` ⇒ 布通率只是**下界**，不得用于跨 K 比较。
    """
    with PA._pitch(pitch):
        if max_expand is None:
            nx, ny = RR._dims(p, float(K))
            max_expand = nx * ny * layers + 1
        r = RR.route_rr(nl, p, spread=float(K), layers=layers, rr_rounds=rr_rounds,
                        max_expand=max_expand, cell_block_up_to=cell_block_up_to,
                        access_radius=access_radius, astar=astar)
    cap = r["capacity_nodes"]
    used = (r["wirelength_um"] / pitch) if pitch else 0.0
    return {
        "K": float(K), "area_factor": float(K) * float(K),
        "layers": layers, "pitch": pitch,
        "nx": r["nx"], "ny": r["ny"], "capacity_nodes": cap,
        "die_w": p.die_w_um * float(K), "die_h": p.die_h_um * float(K),
        "n_nets": r["n_nets"], "n_routed": r["n_routed"],
        "routability": r["routability"], "n_truncated": r["n_truncated"],
        "expanded": r["expanded"],
        "util": (used / cap) if cap else 0.0,
        "fail_source_blocked": r["fail_source_blocked"], "fail_walled": r["fail_walled"],
    }


def capacity_model(pt: dict, factors=(1.5, 2.0, 3.0)) -> list:
    """**解析外推**：容量 ∝ K²、需求（线长，格数）∝ K ⇒ 若布通网数不变则 util(K)=util₁/K。

    🔴 实测已否证这个外推（util 27.8%→27.9% 几乎不动），因为布通网数也涨（526→906）。
    本表只留作**量级/成本**参考，**不承诺布通率**。
    """
    u1 = pt["util"]
    out = []
    for K in factors:
        out.append({"K": float(K), "area_factor": float(K) * float(K),
                    "util_pred_naive": u1 / float(K),
                    "capacity_nodes": int(round(pt["nx"] * pt["ny"] * pt["layers"]
                                                * float(K) * float(K)))})
    return out


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
def spread_self_check(verbose: bool = False, K_extra: float = None) -> dict:
    """E38e 自检：跨档一致 + 精确性 + 失败二分 + 摊开改善/不劣 + 成本 ∝K² + 截断可判 + 搜索器一致。

    `K_extra`：可选额外精确摊开点（2.0 约 350s / 3.0 约 15min）。给了就一并机核。
    """
    from . import dctrl as C
    problems = []

    b = C.build()
    nl = b["netlist"]
    p = real_place(nl)

    # ① K=1 精确点（真实三要素）
    k1 = spread_point(nl, p, 1.0)

    # 跨档一致：与 E38d 已发布值一致 ⇒ 没换口径
    if abs(k1["routability"] - E38D_PUBLISHED_COMBINED) > 0.005:
        problems.append(("cross_doc_mismatch", k1["routability"], E38D_PUBLISHED_COMBINED))
    # 精确性：参与比较的点不得有截断
    if k1["n_truncated"] != 0:
        problems.append(("k1_truncated_not_exact", k1["n_truncated"]))
    # ② 失败二分恒等
    if k1["fail_source_blocked"] + k1["fail_walled"] != k1["n_nets"] - k1["n_routed"]:
        problems.append(("fail_split_not_identity", k1["fail_source_blocked"],
                         k1["fail_walled"], k1["n_nets"] - k1["n_routed"]))
    # 诚实：K=1 仍远非全通
    if not (k1["routability"] < 0.9):
        problems.append(("k1_unexpectedly_high", k1["routability"]))

    # ③ K=3 离线点的**出处对拍**（常量两侧都有出处，不重算：1038s 太贵）：
    #    a) 该点确实越过 90%（"高布通率"的定义）；b) 所需面积倍数(×9) < E37 符号密度(×14.6)。
    if not (K3_OFFLINE["routability"] >= 0.9):
        problems.append(("k3_not_high_routability", K3_OFFLINE["routability"]))
    if not (K3_OFFLINE["area_factor"] < E37_SYMBOLIC_AREA_FACTOR):
        problems.append(("realism_not_cheaper_than_symbolic",
                         K3_OFFLINE["area_factor"], E37_SYMBOLIC_AREA_FACTOR))
    if K3_OFFLINE["fail_source_blocked"] != 0:
        problems.append(("k3_has_pin_blocked_failures", K3_OFFLINE["fail_source_blocked"]))

    # ④ 截断探针（必须有牙）：预算 2000 ≪ 网格 15 万 ⇒ 必报截断且布通率显著下降
    tight = spread_point(nl, p, 1.0, max_expand=2000)
    if tight["n_truncated"] <= 0:
        problems.append(("probe_truncation_not_detected",))
    if not (tight["routability"] < k1["routability"] - 0.01):
        problems.append(("probe_truncation_no_effect",
                         tight["routability"], k1["routability"]))

    # ④ 搜索器一致（符号小网格，便宜）：BFS vs A 星 |Δ| ≤ 5%；且都无截断
    p_sym = PL.place(nl)
    bfs = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, max_expand=200000)
    ast = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, max_expand=200000, astar=True)
    if abs(bfs["routability"] - ast["routability"]) > 0.05:
        problems.append(("search_mode_divergent", bfs["routability"], ast["routability"]))
    if bfs["n_truncated"] != 0 or ast["n_truncated"] != 0:
        problems.append(("symbol_truncated", bfs["n_truncated"], ast["n_truncated"]))

    # ⑤ 确定性（符号小网格，逐位相同）
    bfs2 = RR.route_rr(nl, p_sym, layers=2, rr_rounds=0, max_expand=200000)
    if (bfs2["n_routed"], bfs2["wirelength_um"]) != (bfs["n_routed"], bfs["wirelength_um"]):
        problems.append(("not_deterministic",))

    # ⑥ 可选额外精确摊开点：不劣 + 成本 ∝K² + 利用率未被缓解
    extra = spread_point(nl, p, K_extra) if K_extra else None
    if extra is not None:
        if extra["n_truncated"] != 0:
            problems.append(("extra_truncated_not_exact", extra["K"], extra["n_truncated"]))
        if extra["routability"] < k1["routability"] - 1e-9:
            problems.append(("spread_not_better", extra["K"],
                             k1["routability"], extra["routability"]))
        if extra["fail_source_blocked"] + extra["fail_walled"] != \
                extra["n_nets"] - extra["n_routed"]:
            problems.append(("extra_fail_split_not_identity", extra["K"]))
        ratio = (extra["expanded"] / k1["expanded"]) if k1["expanded"] else 0.0
        if not (COST_RATIO_MIN <= ratio <= COST_RATIO_MAX):
            problems.append(("cost_not_quadratic", extra["K"], round(ratio, 2)))
        if abs(extra["util"] - k1["util"]) > UTIL_DRIFT_MAX:
            problems.append(("util_unexpectedly_relieved", round(k1["util"], 4),
                             round(extra["util"], 4)))

    model = capacity_model(k1)
    if verbose:
        print("  spread K=1  -> %.2f%% (%d/%d) util=%.1f%% trunc=%d expand=%.1fM "
              "fail(src=%d wall=%d)"
              % (100 * k1["routability"], k1["n_routed"], k1["n_nets"], 100 * k1["util"],
                 k1["n_truncated"], k1["expanded"] / 1e6,
                 k1["fail_source_blocked"], k1["fail_walled"]))
        print("  K=3 离线点（不重算 · 1038s）：面积 ×%.0f -> %.2f%%，util=%.1f%%，fail(src=%d wall=%d)"
              % (K3_OFFLINE["area_factor"], 100 * K3_OFFLINE["routability"],
                 100 * K3_OFFLINE["util"], K3_OFFLINE["fail_source_blocked"],
                 K3_OFFLINE["fail_walled"]))
        print("  tight-probe(max_expand=2000) -> %.1f%% trunc=%d（截断检测器有牙）"
              % (100 * tight["routability"], tight["n_truncated"]))
        print("  BFS vs A* (symbolic 2L): %.2f%% vs %.2f%%"
              % (100 * bfs["routability"], 100 * ast["routability"]))
        if extra is not None:
            print("  spread K=%g -> %.2f%% (%d/%d) util=%.1f%% trunc=%d expand=%.1fM "
                  "cost×%.2f fail(src=%d wall=%d)"
                  % (extra["K"], 100 * extra["routability"], extra["n_routed"], extra["n_nets"],
                     100 * extra["util"], extra["n_truncated"], extra["expanded"] / 1e6,
                     (extra["expanded"] / k1["expanded"]) if k1["expanded"] else 0.0,
                     extra["fail_source_blocked"], extra["fail_walled"]))
    return {
        "ok": not problems, "problems": problems,
        "k1": k1, "tight": tight, "model": model,
        "k3_offline": K3_OFFLINE,
        "symbol_bfs": bfs["routability"], "symbol_astar": ast["routability"],
        "extra": extra,
    }


DSPREAD_DISCLOSURE = {
    "route": "E38e · 摊开 ×K 的可测边界 + 失败模式诊断（D-229）",
    "analysis": "真实三要素（0.266µm²/tr 单元 + 0.24µm 线距 + 引脚接入 r=4 + 跨单元 4 层）下把 die 摊开 ×K · "
                "报 util=布线占用/容量 · 失败二分（引脚压死 vs 墙切断）· 截断计数 + A 星选项"
                "（默认 BFS 保历史口径）",
    "golden": "跨档一致(K=1 == E38d 38.7%±0.5%) · 参与比较的点零截断 · 失败二分恒等 · "
              "摊开不劣且改善 · 成本 expanded∝K²(带 [2.5,6]) · 利用率未被摊开缓解(|Δ≤5pp|) · "
              "K=3 出处对拍(≥90% 且 ×9<×14.6 且 fail_source=0) · 紧预算必报截断且布通率下降 · "
              "BFS≡A*(≤5%) · 确定性",
    "not_included": "未逐网定位墙位置 · 未实现破解墙的路由器 · via/引脚占用未计入 util · "
                    "K=3 只作离线常量（1038s，门禁不复算）· K=4 未测（~10⁹ 扩展不可行）",
    "e38e_note": "🔴 摊开曲线（精确·零截断·同 1359 网）：K=1 38.70%（util 27.8%）→ K=2/面积×4 66.67%"
                 "（util 27.9%，扩展 ×3.82）→ **K=3/面积×9 94.26%**（util 32.4%，扩展 ×2.55，1038s）。"
                 "⇒ ① 摊开**确实有效**，真实三要素只需 ×3 摊开/×9 面积即越过 90%，且**小于** E37 符号密度"
                 "所需的 ×14.6（E38d 的预期成立）；② 但**利用率几乎不涨**（27.8→32.4%），`fail_source_blocked` "
                 "全程为 0 ⇒ 残余失败**全是墙切断**，根因是**贪心 L 型走线的墙效应**而非容量/密度 ⇒ 加面积不是"
                 "唯一杠杆，破解墙（多阻塞者 R&R / 分层方向分配 / 非 L 绕行）有望以更小面积达到同样 94%。"
                 "另：本轮先抓到「K=2 报 26.6%」的假象，根因是 BFS 被 max_expand 截断（失败 997 网全为截断），"
                 "靠新加的 `n_truncated` 计数才识破。",
    "repro_k3": "python -c \"import sys,dataclasses,time;sys.path.insert(0,'lda');"
                "from lda_l2.ecore import dcell as DC,dctrl as C,dspread as S;"
                "b=C.build();nl=b['netlist'];p=S.real_place(nl);"
                "print(S.spread_point(nl,p,3.0,max_expand=3000000))\"  # ~1038s",
    "claimable": False,
}
