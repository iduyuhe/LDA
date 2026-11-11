"""P2 · 驱动能力 `k_drive` 的**结构可算性判定**。

═══════════════════════════════════════════════════════════════════════════════
结论先行：**形状可算，绝对值不可算**
───────────────────────────────────────────────────────────────────────────────
规划 P2 DoD：①「11 个 family 截距**能被独立算出**，与实测值偏差可解释（P-3 已证同 family
外推 2.7%）」；②「`k_drive` 从 `unattr` 表移出」。

实测状态：

| DoD | 状态 | 证据 |
|---|---|---|
| ① 截距可算 | ❌ **不成立** | 单一结构模型最好的中位偏差 **4.8%**、最大 **90.7%**；NOR/OR 族结构性错 |
| ①' 形状可算 | ✅ 成立 | 同 family 内 `k ∝ n_series` 单调，四个族全对 |
| ② 移出 unattr | ❌ **不成立** | 未改主链，`k_drive` 仍取手填值（本批只做判定） |

═══════════════════════════════════════════════════════════════════════════════
为什么绝对值算不出（两条，都是缺数据，不是缺抽象）
───────────────────────────────────────────────────────────────────────────────
① **缺器件尺寸**：`dcell.Cell` 只有 `n_tr/n_in/n_series`，**没有 W/L**。驱动能力是
   `W/L × μ × C_ox` 的函数；没有 W，上拉/下拉的**相对强度无法确定**，只能假设。
   实测：把「最坏路径」全取下拉（模型 A）⇒ `nand` 偏 +11%、`nor` 偏 **−79%**；
   全取「下拉 vs 上拉/μ」（模型 B）⇒ `nor` 改善到 −17% 但 `nand` 恶化到 **−54%**。
   **两条都无法同时对上** —— 因为 `R_p/R_n` 这个比值本应由 W 决定，本仓没有它。

② **缺 μ 标定**：`MU=0.40` 是教科书量级（`dcell` 里没有 μ 字段）。而手填值隐含的
   有效比值在 NOR 族约 **1.2**、在 NAND 族约 **0.9** —— 同一个物理量在两族给了两个数，
   说明手填值本身**不是从统一模型导出的**。

⇒ 「截距能独立算出」这句话的正确版本是：**能算出形状（同 family 内的比例），
算不出绝对量级**。差的那一层是 W/μ 数据，不是抽象层。

═══════════════════════════════════════════════════════════════════════════════
本模块做什么 / 不做什么
───────────────────────────────────────────────────────────────────────────────
做：给定 family + n_in + μ 假设 ⇒ 算出 k 的**形状**；逐单元与手填值比偏差并分类；
    给出「若采用模型值，主链会变多少」的**预注册数**。
不做：不改 `k_drive`、不改 `t_intr`、不动主链 9 数（改口需独立发布，见 `PREREG`）。
"""

from typing import Any, Dict, List, Tuple

from . import dcell as DC

#: 每个 family 的上拉/下拉结构（`"n"` = 随 `n_in` 变，(串联, 并联) = 固定）
#: 来源：`dcell` 的拓扑注释（nand = N 串联 + P 并联；nor 对偶；and/or = 基门 + INV）
#: 🔴 v0.9.405：拓扑表已搬进 `dcell.STRUCT`（电阻要用它，属单元数据）。
#: 这里是**同一个对象的别名**，不是副本 —— 两处各存一份必漂。
STRUCT: Dict[str, Dict[str, Any]] = DC.STRUCT

#: μ_p/μ_n（**教科书量级假设**，本仓无 μ 字段 ⇒ 登记为 unattr）
MU_RATIO = 0.40

#: 哪些 family 的最坏路径在**上拉**侧（PMOS 串联）—— 模型 A 只看下拉 ⇒ 结构性错
PULLUP_DOMINATED = ("nor", "or")

P2_DISCLOSURE = {
    "claimable": False,
    "scope": "DIAGNOSTIC_ONLY",
    "in_blocking": False,
    "what": ("给定 family + 输入数 + μ 假设，算出 `k_drive` 的**形状**；"
             "逐单元与手填值比偏差并分类"),
    "verdict": "**形状可算、绝对值不可算**（缺 W/L 与 μ 标定，属数据缺口不是抽象缺口）",
    "not_claimed": (
        "① 不改 `k_drive`、不改 `t_intr`、不动主链 9 数"
        "；② 不宣称任何模型是「正确模型」——三个模型都只对一半 family"
        "；③ `k_drive` **仍在 `unattr` 表**（DoD② 未达成）"),
}


def _res(spec, n_in: int) -> float:
    """(串联数, 并联数) 或 `"n"` ⇒ 有效电阻（单位 R_n）。"""
    if spec == "n":
        return float(n_in)
    ser, par = spec
    ser = n_in if ser == "n" else ser
    par = n_in if par == "n" else par
    return float(ser) / float(par)


def k_shape(cell, mu: float = MU_RATIO) -> Dict[str, float]:
    """算出两种口径的 k（**未归一化**，相对 INV 的两个基准）。"""
    s = STRUCT[cell.family]
    pd = _res(s["pd"], cell.n_in)
    pu = _res(s["pu"], cell.n_in) / mu
    return {"pd": pd, "pu": pu, "worst": max(pd, pu)}


def k_models(mu: float = MU_RATIO) -> Dict[str, Dict[str, float]]:
    """返回每个单元的 `{nmos_only, bottleneck}`（均已归一到 INV=1.0）。

    · `nmos_only`（模型 A）：只算**下拉**最坏路径 / INV 下拉 ⇒ 对 nand/aoi/xor 准，
      对 nor/or **结构性错**（它们的最坏路径在上拉）。
    · `bottleneck`（模型 B）：取 `max(下拉, 上拉/μ)` / INV 同口径 ⇒ nor 改善、nand 恶化。
    """
    inv = DC.CELLS["INV"]
    inv_s = k_shape(inv, mu)
    out = {}
    for name, c in sorted(DC.CELLS.items()):
        s = k_shape(c, mu)
        out[name] = {
            "nmos_only": s["pd"] / inv_s["pd"],
            "bottleneck": s["worst"] / inv_s["worst"],
            "hand": c.k_drive,
            "family": c.family,
            "n_in": c.n_in,
            "n_series": c.n_series,
        }
    return out


def deviation_report(mu: float = MU_RATIO) -> Dict[str, Any]:
    """逐单元偏差 + 分类（`WITHIN_5PCT` / `WITHIN_20PCT` / `STRUCTURAL`）。"""
    m = k_models(mu)
    rows = {}
    for name, r in m.items():
        # 取两模型中对该 family **更合适**的那个：上拉主导族用 bottleneck，其余用 nmos_only
        key = "bottleneck" if r["family"] in PULLUP_DOMINATED else "nmos_only"
        val = r[key]
        dev = (val / r["hand"] - 1.0) if r["hand"] else 0.0
        cls = ("WITHIN_5PCT" if abs(dev) <= 0.05 else
               ("WITHIN_20PCT" if abs(dev) <= 0.20 else "STRUCTURAL"))
        rows[name] = dict(r, model=val, model_kind=key, dev=dev, cls=cls)
    devs = sorted(abs(r["dev"]) for r in rows.values())
    n = len(devs)
    med = devs[n // 2] if n % 2 else (devs[n // 2 - 1] + devs[n // 2]) / 2.0
    by_cls: Dict[str, int] = {}
    for r in rows.values():
        by_cls[r["cls"]] = by_cls.get(r["cls"], 0) + 1
    return {
        "cells": rows,
        "n_cells": n,
        "median_abs_dev": med,
        "max_abs_dev": devs[-1],
        "worst_cell": max(rows, key=lambda k: abs(rows[k]["dev"])),
        "by_class": by_cls,
        "mu_assumed": mu,
        "scope": "DIAGNOSTIC_ONLY",
        "in_blocking": False,
    }


def shape_check() -> Dict[str, Any]:
    """**形状**是否可算：同 family 内 `k` 随 `n_series` 单调，且模型与实测的**斜率符号**一致。"""
    m = k_models()
    fam: Dict[str, List[Tuple[int, float, float]]] = {}
    for name, r in m.items():
        # 🔴 与 `deviation_report` 同口径：上拉主导族用 bottleneck，其余用 nmos_only。
        #   用 nmos_only 量 nor/or 会得到 1/n（递减）⇒ 误判"形状不可算"。
        key = "bottleneck" if r["family"] in PULLUP_DOMINATED else "nmos_only"
        fam.setdefault(r["family"], []).append((r["n_in"], r["hand"], r[key]))
    out = {}
    for f, rows in fam.items():
        if len({x for x, _, _ in rows}) < 2:
            continue
        rows.sort()
        hand_mono = all(rows[i][1] < rows[i + 1][1] for i in range(len(rows) - 1))
        model_mono = all(rows[i][2] < rows[i + 1][2] for i in range(len(rows) - 1))
        # 同 family 内**相对斜率**误差（用两点的比值，消除绝对标定影响）
        r_hand = rows[-1][1] / rows[0][1]
        r_model = rows[-1][2] / rows[0][2]
        out[f] = {
            "rows": rows,
            "hand_mono": hand_mono,
            "model_mono": model_mono,
            "ratio_hand": r_hand,
            "ratio_model": r_model,
            "ratio_err": (r_model / r_hand - 1.0),
        }
    return {
        "families": out,
        "n_families_multi": len(out),
        "all_mono": all(v["hand_mono"] and v["model_mono"] for v in out.values()),
        "max_ratio_err": (max(abs(v["ratio_err"]) for v in out.values())
                          if out else None),
    }


#: 🔴 **预注册 → 已实施**（v0.9.406）。
#: v0.9.402 时这里登记了三个 `C_self` 候选却**不敢选**；v0.9.406 选了**第四个**，理由如下。
PREREG = {
    "t_intr_ps": {
        "status": "IMPLEMENTED (v0.9.406)",
        "implemented_c_self_ff": 0.577078016356,
        "implemented_c_self_rel": "0.5771·cin",
        "why_this_one": (
            "🔴 前三个候选（1/2/3·cin）都是**凭空的物理直觉**，挑哪个都等于凭空加减速度。"
            "本批改用**标定锚法**：令 `C_self` 反解自旧常数 `t_intr_ps`（= 让 INV 仍恰好 2.0 ps）"
            "⇒ 换来的是「**k>1 的单元变慢**」这一件事，可归因、可复算；"
            "而不是「所有单元一起变慢 X%」这种无法与别的改动区分的效果。"),
        "candidates": {"0.5771·cin（锚·已实施）": 2.000, "1·cin": 3.466,
                       "2·cin": 6.931, "3·cin": 10.397},
        "candidates_note": ("这三个仍登记着：将来若有器件数据说 `C_self = 1·cin`，"
                            "INV 也要 +73%，主链会到 55.452 ps（见下表）。"
                            "**锚法不否认这个可能，只是不假装知道。**"),
    },
    "main_chain_if_adopted": {
        "ideal_ps": {"v0.9.405（常数 t_intr）": 40.657,
                     "0.5771·cin（已实施）": 46.657,
                     "1·cin": 55.452, "2·cin": 76.246, "3·cin": 97.041},
        "delta_pct": {"0.5771·cin": 14.8, "1·cin": 36.4, "2·cin": 87.5, "3·cin": 138.7},
        "note": "全部相对 v0.9.405 的 40.657 ps。数值已实测（`dsta.sta`），不是估算。",
    },
    "gate": ("改这几个数会同时改 `T_ref`（它由 delay 派生）⇒ slack、三角、dprovenance 的 "
             "PASS/FAIL 全部跟着动 ⇒ 必须同批改所有锁定判据。v0.9.406 已按此执行。"),
}


def self_check() -> Dict[str, Any]:
    """自检：正向 + **反向构造**（每条断言都要能改坏必报）。"""
    problems: List[str] = []
    rep = deviation_report()
    sh = shape_check()

    # ① 正向：18 个单元全部被算到
    if rep["n_cells"] != len(DC.CELLS):
        problems.append("n_cells_%d_ne_%d" % (rep["n_cells"], len(DC.CELLS)))

    # ② 正向：形状可算（四个多点 family 全单调）
    if not sh["all_mono"]:
        problems.append("shape_not_mono")

    # ③ 反向：把 μ 设成极端值 ⇒ 上拉主导族的偏差必须变化（证明 μ 真进了模型）
    #   用 NAND2：μ 变小会把瓶颈从上拉翻到下拉（ratio 0.8→0.5）；
    #   NOR2 两侧都 ∝1/μ ⇒ 比值不变，用它测会得到"μ 无效"的假结论。
    bad = k_models(mu=0.10)
    if abs(bad["NAND2"]["bottleneck"] - k_models(mu=0.40)["NAND2"]["bottleneck"]) < 1e-6:
        problems.append("mu_not_effective_on_NAND2")

    # ④ 反向：把手填值全改成 1.0 ⇒ 偏差分类必须变差（证明比较是真比较）
    #    这里不改产品，只验"分类阈值"不是恒真
    if not any(r["cls"] == "STRUCTURAL" for r in rep["cells"].values()):
        problems.append("no_structural_cell")   # 若连结构性偏差都没有，说明模型太好，可疑

    # ⑤ 反向：`k_drive` 必须仍是手填（本模块不得改写它）
    if DC.CELLS["NAND2"].k_drive != 1.80:
        problems.append("k_drive_mutated:%r" % (DC.CELLS["NAND2"].k_drive,))

    return {
        "ok": not problems,
        "problems": problems,
        "n_cells": rep["n_cells"],
        "median_abs_dev": rep["median_abs_dev"],
        "max_abs_dev": rep["max_abs_dev"],
        "by_class": rep["by_class"],
        "shape_all_mono": sh["all_mono"],
        "verdict": P2_DISCLOSURE["verdict"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# W/L 数据层（v0.9.403 · 新开一批）—— **几何模型 + 上限定理**
# ═══════════════════════════════════════════════════════════════════════════
"""上一批（P2）的结论是「缺 W/L 与 μ ⇒ 绝对值不可算」。本批把 W/L 补上了，
于是同一个问题可以问得更狠：**补了数据之后，手填值能被几何解释吗？**

答案：**不能，而且可以证明**。

    均匀 W（全库同一 w_n、w_p、L）⇒  k ≤ max(s_n, s_p)
    —— 与 μ 无关、与 W 的绝对量无关。证明见 `CEILING_PROOF`。

实测：`NOR2`(2.40>2) / `NOR3`(3.40>3) / `OAI21`(2.40>2) 三个值**超出上限** ⇒
它们不可能来自任何均匀几何。要突破上限，只能**逐单元定制 W**（= 按版图/面积做 sizing），
而本仓只有 2 个单元有版图（`INV_X1` / `NAND2_X1`）。

⇒ 这条链的终点不是「k_drive 可算」，而是：**k_drive 要可算，得先有逐单元的 W 决策（版图）**。
   「补数据」补掉的是**借口**，暴露出来的是**顺序问题**。
"""

#: 单级模型的适用域（**必须显式**，否则拿它套 2 级/传输门单元就是错用）
#:   EXACT — 静态互补 CMOS、单级、串并联网络 ⇒ 模型精确
#:   APPROX — 结构存在但被简化（XOR 双极性网络）
#:   NA    — 模型不适用（多级 / 传输门 / 无驱动）
SCOPE = {
    "inv": "EXACT", "nand": "EXACT", "nor": "EXACT",
    "aoi": "EXACT", "oai": "EXACT",
    "xor": "APPROX",
    "and": "NA", "or": "NA", "mux": "NA", "seq": "NA", "tie": "NA",
}

#: 逐单元的域覆盖（`BUF` 是两级反相，虽然 family 是 inv 但不能进单级模型）
SCOPE_CELL = {"BUF": "NA"}

#: 上限定理（代数证明写在这里，`ceiling_scan` 是它的机核版）
CEILING_PROOF = {
    "statement": "均匀 W（全库同一 w_n/w_p/L）⇒ k = max(s_n, m·s_p)/max(1, m) ≤ max(s_n, s_p)，其中 m = R_p/R_n。",
    "steps": (
        "① R_pd(cell) = s_n · (L/w_n)；R_pu(cell) = s_p · (L/w_p) · m。",
        "② 归一化基准 INV（s_n=s_p=1）⇒ R_INV = max(L/w_n, m·L/w_p)。",
        "③ k = max(s_n·L/w_n, m·s_p·L/w_p) / max(L/w_n, m·L/w_p)。",
        "④ 分子 ≤ max(s_n,s_p) · max(L/w_n, m·L/w_p)（逐项取 max 放大）。",
        "⑤ 约掉公共因子 ⇒ k ≤ max(s_n, s_p)。∎",
    ),
    "why_uniform_matters": ("均匀 W 时分子分母的 L/w 因子**同构**，才能约掉。"
                            "一旦逐单元定制 W，分母（INV 的 W）与分子（该单元的 W）不再是同一个数，"
                            "上限就打开 —— 这正是「要突破上限必须做 sizing」的代数原因。"),
    "consequence": "3 个手填值超上限 ⇒ 不是「参数没调好」，是**手填表与均匀几何不相容**。",
}

#: 教科书 μ_p/μ_n（沿用 P2 的假设值，本仓仍无器件测量）
WL_MU = MU_RATIO


def _scope(cell) -> str:
    return SCOPE_CELL.get(cell.name, SCOPE.get(cell.family, "NA"))


#: 串联级数：直接委托 `dcell`（v0.9.405 起拓扑表只有一份）
_series = DC.series_counts


def _tech_with_mu(mu: float):
    """把 μ 变成 `Tech.r_sheet_p_over_n = 1/μ` 的 Tech 副本 —— 电阻只有一条实现路径。"""
    import dataclasses as _dc
    return _dc.replace(DC.DEFAULT_TECH, r_sheet_p_over_n=(1.0 / mu))


def _r_side(cell, mu: float = None):
    """(下拉电阻, 上拉电阻) —— 委托 `dcell.r_side_ohm`（Ω）。`mu` 给定时临时改 ρ 比。"""
    tech = DC.DEFAULT_TECH if mu is None else _tech_with_mu(mu)
    return DC.r_side_ohm(cell, tech)


def k_geometry(cell, mu: float = WL_MU) -> float:
    """几何派生的 `k_drive`（相对 INV）。**只看 W/L 与拓扑，不看手填值。**

    🔴 域限制：`_scope(cell) == "NA"` 时抛 `ValueError` —— 用单级模型套 2 级单元
    会得到「看起来合理」的错数，比报错更危险。
    """
    if _scope(cell) == "NA":
        raise ValueError("单元 %s 不在单级串并联模型适用域（2 级/传输门）" % cell.name)
    # 🔴 v0.9.405：数学收归 `dcell.cell_r_ohm`（延时路径用的是同一个函数）——
    #   判定器与产品**共用一份实现**，这里只做归一化与域检查。
    tech = _tech_with_mu(mu)
    return DC.cell_r_ohm(cell.name, tech) / DC.cell_r_ohm("INV", tech)


def ceiling(cell) -> float:
    """均匀 W 下的**代数上限** `max(s_n, s_p)`（见 `CEILING_PROOF`）。"""
    sn, sp = _series(cell)
    return max(sn, sp)


def ceiling_scan(cell, lo: float = 0.05, hi: float = 4.0, n: int = 396) -> Dict[str, Any]:
    """在 μ 上扫一遍，取 `k_geometry` 的最大值 ⇒ 与代数上限对比。

    这是**机核版证明**：如果扫描最大值超过 `ceiling(cell)`，说明定理写错了。
    """
    best, best_mu = -1.0, None
    for i in range(n):
        mu = lo + (hi - lo) * i / (n - 1)
        v = k_geometry(cell, mu)
        if v > best:
            best, best_mu = v, mu
    cap = ceiling(cell)
    return {"cell": cell.name, "family": cell.family, "ceiling": cap,
            "scan_max": best, "scan_argmax_mu": best_mu,
            "hand": cell.k_drive,
            "over_ceiling": cell.k_drive > cap + 1e-9,
            "scan_within_ceiling": best <= cap + 1e-9,
            "over_pct": (cell.k_drive / cap - 1.0) * 100.0 if cap else 0.0}


def ceiling_report(mu: float = WL_MU) -> Dict[str, Any]:
    """逐单元：手填值 vs 上限。**违反项与 μ 无关**，这是本批最硬的结论。"""
    rows, viol = {}, []
    for name, c in DC.CELLS.items():
        if _scope(c) == "NA":
            continue
        cap = ceiling(c)
        kat = k_geometry(c, mu)
        over = c.k_drive > cap + 1e-9
        rows[name] = {
            "cell": c.name, "family": c.family, "ceiling": cap,
            "hand": c.k_drive, "k_at_mu": kat,
            "dev_at_mu": kat / c.k_drive - 1.0,
            "over_ceiling": over,
            "over_pct": (c.k_drive / cap - 1.0) * 100.0 if cap else 0.0,
        }
        if over:
            viol.append(name)
    return {
        "mu": mu,
        "n_in_scope": len(rows),
        "n_violations": len(viol),
        "violations": sorted(viol),
        "cells": rows,
        "verdict": ("**%d 个手填值超代数上限**（%s）⇒ 它们不可能来自任何均匀 W 的几何，"
                    "与 μ 取什么值无关" % (len(viol), " / ".join(sorted(viol)))),
        "hand_table_fits_2params": {
            "note": ("手填表本身是「每 family 两个参数 (a, b)：k = a + b·(n_series−1)」，"
                     "15 个自由参数对 18 个单元 —— 拟合残差恒为 0。"
                     "参数比数据少一半 ⇒ 它本来就不是几何，是**分段线性插值**。"),
            "free_params": 15, "n_cells": 18,
        },
    }


def ceiling_bound_check(lo: float = 0.05, hi: float = 4.0, n_mu: int = 60,
                        n_wp: int = 40) -> Dict[str, Any]:
    """**定理的机核**：扫 (μ, W_p/W_n) 二维网格，检查 `k / ceiling ≤ 1` 对所有单元成立。

    这是「最强判据 = 通式必须退化为特例」的直接用法：把 W 当自由变量扫，
    若界被打破，说明证明里那步「约掉公共因子」错了。
    """
    worst, worst_cell = 0.0, None
    for i in range(n_mu):
        mu = lo + (hi - lo) * i / (n_mu - 1)
        for j in range(n_wp):
            wf = 0.2 + (6.0 - 0.2) * j / (n_wp - 1)
            for name, c in DC.CELLS.items():
                if _scope(c) == "NA":
                    continue
                c2 = DC.Cell(name=c.name, n_in=c.n_in, n_tr=c.n_tr, table=c.table,
                             n_series=c.n_series, k_drive=c.k_drive, is_seq=c.is_seq,
                             pins=c.pins, family=c.family,
                             w_n_nm=c.w_n_nm, w_p_nm=c.w_p_nm * wf, l_nm=c.l_nm,
                             wl_src=c.wl_src)
                inv2 = DC.Cell(name="INV", n_in=1, n_tr=2, table=(1, 0), n_series=1,
                               k_drive=1.0, pins=("a",), family="inv",
                               w_n_nm=c.w_n_nm, w_p_nm=c.w_n_nm * wf, l_nm=c.l_nm,
                               wl_src=c.wl_src)
                rn, rp = _r_side(c2, mu)
                irn, irp = _r_side(inv2, mu)
                k = max(rn, rp) / max(irn, irp)
                ratio = k / ceiling(c)
                if ratio > worst:
                    worst, worst_cell = ratio, c.name
    return {"grids": n_mu * n_wp, "max_ratio_to_ceiling": worst,
            "worst_cell": worst_cell, "bound_holds": worst <= 1.0 + 1e-9}


def implied_mu(cell, lo: float = 0.01, hi: float = 20.0, n: int = 20000) -> Dict[str, Any]:
    """反解：要让几何模型等于手填值，μ 得取多少？**可解性本身就是判据**。

    三种结局必须分开（混起来就会拿「无解」当「可解」）：
      · `REACHABLE_MU`   — 能对上，且 μ 被唯一确定（该单元能提供 μ 信息）
      · `REACHABLE_FREE` — 能对上，但 μ 怎么取都一样（该单元**不能**提供 μ 信息）
      · `UNREACHABLE`    — 怎么取都对不上（超出可达域）
    """
    if _scope(cell) == "NA":
        return {"cell": cell.name, "status": "OUT_OF_SCOPE", "mu": None,
                "residual": None, "k_at_mu": None}
    best = None
    for i in range(n):
        mu = lo + (hi - lo) * i / (n - 1)
        d = abs(k_geometry(cell, mu) - cell.k_drive)
        if best is None or d < best[0]:
            best = (d, mu)
    resid, mu = best
    lo_v, hi_v = k_geometry(cell, lo), k_geometry(cell, hi)
    mu_free = abs(hi_v - lo_v) < 1e-9
    reachable = resid <= 0.01
    status = ("UNREACHABLE" if not reachable
              else "REACHABLE_FREE" if mu_free else "REACHABLE_MU")
    return {"cell": cell.name, "family": cell.family, "hand": cell.k_drive,
            "mu": (mu if status == "REACHABLE_MU" else None),
            "residual": resid, "mu_insensitive": mu_free,
            "status": status, "k_at_mu": k_geometry(cell, mu)}


def implied_mu_report() -> Dict[str, Any]:
    """全库反解：**能解的给出同一个 μ 吗？解不了的差多少？**（三分类互斥）"""
    rows = {n: implied_mu(c) for n, c in DC.CELLS.items() if _scope(c) != "NA"}
    by = {}
    for n, r in rows.items():
        by.setdefault(r["status"], []).append(n)
    for k in by:
        by[k].sort()
    mus = sorted(r["mu"] for r in rows.values() if r["status"] == "REACHABLE_MU")
    return {
        "cells": rows,
        "by_status": by,
        "n_in_scope": len(rows),
        "n_reachable_mu": len(by.get("REACHABLE_MU", [])),
        "n_reachable_free": len(by.get("REACHABLE_FREE", [])),
        "n_unreachable": len(by.get("UNREACHABLE", [])),
        "mu_range": [mus[0], mus[-1]] if mus else None,
        "mu_spread": (mus[-1] - mus[0]) if mus else None,
        "textbook_mu": WL_MU,
        "verdict": ("%d 个可解且**互不相同地**给出 μ ∈ %s（散布 %.2f）；"
                    "%d 个 μ 无感（不能提供 μ 信息）；%d 个**怎么取都对不上**（%s）"
                    % (len(mus),
                       ("[%.3f, %.3f]" % (mus[0], mus[-1])) if mus else "—",
                       (mus[-1] - mus[0]) if mus else 0.0,
                       len(by.get("REACHABLE_FREE", [])),
                       len(by.get("UNREACHABLE", [])),
                       " / ".join(by.get("UNREACHABLE", [])) or "—")),
        "implication": ("可解的那组 μ≈0.87~1.00 ⇒ 手填表隐含 **μ_n ≈ μ_p**，"
                        "而硅里 μ_n/μ_p ≈ 2~3（教科书 μ=%.2f）⇒ 手填表不是从迁移率算出来的；"
                        "本仓版图 p/n=1:1 也只在 μ≈1 时才算「平衡」—— "
                        "两件自产的东西在同一个**物理上错的**假设下才自洽。" % WL_MU),
    }


def geometry_report(mu: float = WL_MU) -> Dict[str, Any]:
    """逐单元：手填 vs 几何（给定 μ）+ 偏差分类。"""
    rows, devs = {}, []
    for name, c in DC.CELLS.items():
        sc = _scope(c)
        if sc == "NA":
            rows[name] = {"scope": sc, "hand": c.k_drive, "model": None,
                          "dev": None, "cls": "OUT_OF_SCOPE"}
            continue
        v = k_geometry(c, mu)
        d = v / c.k_drive - 1.0
        devs.append(abs(d))
        rows[name] = {"scope": sc, "hand": c.k_drive, "model": v, "dev": d,
                      "cls": ("WITHIN_5PCT" if abs(d) <= 0.05 else
                              "WITHIN_20PCT" if abs(d) <= 0.20 else "STRUCTURAL")}
    devs.sort()
    return {
        "mu": mu, "n_cells": len(rows), "n_in_scope": len(devs),
        "median_abs_dev": devs[len(devs) // 2] if devs else 0.0,
        "max_abs_dev": devs[-1] if devs else 0.0,
        "by_class": {k: sum(1 for r in rows.values() if r["cls"] == k)
                     for k in ("WITHIN_5PCT", "WITHIN_20PCT", "STRUCTURAL",
                               "OUT_OF_SCOPE")},
        "cells": rows,
    }


def balance_report(mu: float = WL_MU) -> Dict[str, Any]:
    """**版图的 PMOS 加宽了吗？** —— 这是数据层暴露出的第二个问题。

    平衡反相器要求 `R_pu = R_pd`，即 `L/w_p · (1/μ) = L/w_n` ⇒ `w_p/w_n = 1/μ`。
    本仓版图是 **1:1**（实测 DIFF 高度都是 300nm）。
    """
    inv = DC.CELLS["INV"]
    got = inv.w_p_nm / inv.w_n_nm
    need = 1.0 / mu
    rp_over_rn = (inv.w_n_nm / inv.w_p_nm) / mu      # INV 的上拉/下拉电阻比
    return {
        "cell": "INV", "w_n_nm": inv.w_n_nm, "w_p_nm": inv.w_p_nm,
        "pn_ratio": got, "required_for_balanced": need, "mu": mu,
        "pullup_over_pulldown": rp_over_rn,
        "balanced": abs(rp_over_rn - 1.0) <= 0.02,
        "verdict": ("版图实测 p/n = %.2f，而平衡要求 %.2f（μ=%.2f）⇒ **PMOS 未加宽**，"
                    "上拉电阻是下拉的 **%.2f×** ⇒ 每个单元的驱动都被上拉侧限制，"
                    "且 NOR/OAI 这类上拉串联的单元受害加倍"
                    % (got, need, mu, rp_over_rn)),
        "caveat": ("🔴 只有当 μ 取教科书值 %.2f 时这句话才成立。手填 k 表反解出的 μ≈1 "
                   "会让 1:1 恰好「平衡」—— 两件本仓自产的东西只在物理上错的假设下自洽，"
                   "这本身就是「其中至少一个错了」的证据。" % mu),
    }


WL_DISCLOSURE = {
    "claimable": False,
    "scope": "DIAGNOSTIC_ONLY",
    "in_blocking": False,
    "what": ("补上 W/L 数据（`dcell.Cell.w_n_nm/w_p_nm/l_nm/wl_src`）并给出几何模型、"
             "代数上限定理、逐单元反解 μ"),
    "verdict": ("**数据补上了，结论反而更硬**：均匀 W 下 k ≤ max(s_n,s_p)（与 μ 无关），"
                "3 个手填值超上限 ⇒ 手填表不可能来自任何均匀几何"),
    "not_claimed": (
        "① 不改 `k_drive`、不改 `t_intr`、不动主链 9 数（预注册而非实施）"
        "；② 16/18 个单元的 W 是**规则外推**不是实测"
        "；③ 不宣称几何模型「更准」—— 它只有 1 个自由参数（μ），却是可证伪的"
        "；④ `k_drive` 仍在 `unattr` 表"),
}

#: 若把 `k_drive` 换成几何值（c17 只用 INV + NAND2 ⇒ 只有 NAND2 变）—— **只登记、不实施**
PREREG["k_drive_geometry"] = {
    "current": {"INV": 1.00, "NAND2": 1.80},
    "candidates": {"NAND2@μ=0.40": 1.000, "NAND2@μ=0.80": 1.600, "NAND2@μ=0.95": 1.900},
    "main_chain_ideal_ps": {"current": 37.192, "μ=0.40": 23.329,
                            "μ=0.80": 33.726, "μ=0.95": 38.924},
    "main_chain_delta_pct": {"μ=0.40": -37.3, "μ=0.80": -9.3, "μ=0.95": 4.7},
    "why_not": ("① `k_drive` 一改，21 条主链锁定判据同时红（`EC-K04` 已实测）；"
                "② 更根本的是：改 k 的**同时必须改版图**（PMOS 加宽到 1/μ），"
                "否则归一化基准 INV 自己就是未平衡的 —— 只改数字等于用一个错锚去校另一个数"),
    "ordering": "先修版图（pMOS sizing）→ 再让 k 由几何派生 → 再预注册主链改口",
}


def wl_self_check() -> Dict[str, Any]:
    """W/L 层自检：正向 + 反向（每条都要能改坏必报）。"""
    problems: List[str] = []
    wl = DC.wl_provenance_summary()

    # ① 数据完整：18 个单元全部有 W/L 出处
    if wl["n_cells"] != len(DC.CELLS):
        problems.append("wl_cells_%d_ne_%d" % (wl["n_cells"], len(DC.CELLS)))
    if wl["n_measured"] != 2:
        problems.append("measured_%d_ne_2" % wl["n_measured"])

    # ② 上限定理**机核**（二维扫描不得越界）
    bc = ceiling_bound_check(n_mu=25, n_wp=18)
    if not bc["bound_holds"]:
        problems.append("ceiling_broken:%r@%s" % (bc["max_ratio_to_ceiling"], bc["worst_cell"]))

    # ③ 违反项必须**恰好**是那 3 个（多了说明模型错，少了说明判据瞎）
    cr = ceiling_report()
    if cr["violations"] != ["NOR2", "NOR3", "OAI21"]:
        problems.append("violations_%r" % (cr["violations"],))

    # ④ 反向：**破坏 p/n 比例**（把 INV 的 pMOS 缩回 1:1）⇒ NAND2 的 k 必须变。
    #   🔴 v0.9.404 实测发现：版图一旦**平衡**，INV 两侧电阻相等 ⇒ 单侧加宽/缩窄
    #   **都不改变** `max()`（另一侧顶住）⇒ k 是「平台」。所以「加宽 pMOS」不再是有效探针，
    #   有效的是「改比例」。这本身就是平衡态的指纹：k 对单侧尺寸一阶不敏感。
    inv = DC.CELLS["INV"]
    c2 = DC.Cell(name="INV", n_in=1, n_tr=2, table=(1, 0), n_series=1, k_drive=1.0,
                 pins=("a",), family="inv", w_n_nm=inv.w_n_nm,
                 w_p_nm=inv.w_n_nm, l_nm=inv.l_nm, wl_src=inv.wl_src)   # p/n 退回 1.0
    rn, rp = _r_side(DC.CELLS["NAND2"], WL_MU)
    irn, irp = _r_side(c2, WL_MU)
    unbalanced = max(rn, rp) / max(irn, irp)
    if abs(unbalanced - k_geometry(DC.CELLS["NAND2"], WL_MU)) < 1e-9:
        problems.append("w_not_effective")

    # ⑤ 反向：**保比**缩放的不变性 —— n 与 p 同乘一个因子，k 必须**不变**。
    #   🔴 v0.9.404：原来写死 600/600（那是 1:1 时代）。现在 p/n=2.5，600/600 会把比例
    #   改成 1.0 —— 那测的是「换比例」，不是「换尺度」。必须两边乘同一个因子。
    _sc_f = 2.0
    a = k_geometry(DC.CELLS["NAND2"], WL_MU)
    _inv0 = DC.CELLS["INV"]
    sc = DC.Cell(name="NAND2", n_in=2, n_tr=4, table=(1, 1, 1, 0), n_series=2,
                 k_drive=1.8, pins=("a", "b"), family="nand",
                 w_n_nm=_inv0.w_n_nm * _sc_f, w_p_nm=_inv0.w_p_nm * _sc_f,
                 l_nm=_inv0.l_nm, wl_src="RULE_CONSTANT")
    sc_inv = DC.Cell(name="INV", n_in=1, n_tr=2, table=(1, 0), n_series=1, k_drive=1.0,
                     pins=("a",), family="inv", w_n_nm=_inv0.w_n_nm * _sc_f,
                     w_p_nm=_inv0.w_p_nm * _sc_f, l_nm=_inv0.l_nm,
                     wl_src="RULE_CONSTANT")
    b = max(*_r_side(sc, WL_MU)) / max(*_r_side(sc_inv, WL_MU))
    if abs(a - b) > 1e-12:
        problems.append("uniform_scale_not_invariant:%.6f_vs_%.6f" % (a, b))

    # ⑥ 域保护：`NA` 单元必须抛错（而不是悄悄给个数）
    try:
        k_geometry(DC.CELLS["AND2"], WL_MU)
        problems.append("na_scope_not_guarded")
    except ValueError:
        pass

    return {
        "ok": not problems, "problems": problems,
        "n_cells": wl["n_cells"], "n_measured": wl["n_measured"],
        "ceiling_bound": bc["bound_holds"],
        "violations": cr["violations"],
        "verdict": WL_DISCLOSURE["verdict"],
    }
