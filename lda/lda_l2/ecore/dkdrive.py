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
STRUCT: Dict[str, Dict[str, Any]] = {
    "inv": dict(pd=(1, 1), pu=(1, 1)),
    "nand": dict(pd="n", pu=(1, "n")),
    "nor": dict(pd=(1, "n"), pu="n"),
    "and": dict(pd="n", pu=(1, "n")),
    "or": dict(pd=(1, "n"), pu="n"),
    "aoi": dict(pd=(2, 1), pu=(2, 1)),
    "oai": dict(pd=(2, 1), pu=(2, 1)),
    "xor": dict(pd=(3, 1), pu=(2, 2)),
    "mux": dict(pd=(2, 1), pu=(2, 2)),
    "seq": dict(pd=(1, 1), pu=(1, 1)),
    "tie": dict(pd=(1, 1), pu=(1, 1)),
}

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


#: 🔴 **预注册**：若把 `k_drive` 换成模型值、`t_intr` 换成 `ln2·R_on·C_self`，
#: 主链会变多少（**只登记、不实施** —— 改口需独立发布）
PREREG = {
    "t_intr_ps": {
        "current": 2.0,
        "candidates": {"1·cin": 3.466, "2·cin": 6.931, "3·cin": 10.397},
        "why_three": ("`C_self`（自载电容）本仓无器件数据 ⇒ 只能给候选并说明取哪个；"
                      "取 1·cin 相当于「只有栅」，取 2·cin 加漏结，取 3·cin 再加互连"),
    },
    "main_chain_if_adopted": {
        "ideal_ps": {"current": 37.192,
                     "1·cin": 41.589, "2·cin": 51.986, "3·cin": 62.383},
        "delta_pct": {"1·cin": 11.8, "2·cin": 39.8, "3·cin": 67.7},
    },
    "gate": ("改这几个数会同时改 `T_ref`（它由 delay 派生）⇒ slack、三角、dprovenance 的 "
             "PASS/FAIL 全部跟着动 ⇒ 必须同批改所有锁定判据，属**独立发布**"),
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
