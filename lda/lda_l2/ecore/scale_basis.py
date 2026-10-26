# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E20 · 规模/误差口径的单一真源 + 解析金标（D-195）。

============================================================================
它解决什么问题（缺口取证，不是凭空造能力）
----------------------------------------------------------------------------
E7/E9/E15 各自产出了「IR drop」与「可及规模上界」，但同一件事在四个模块里
有 **四个不同口径**，且此前**没有任何一处机器可读地登记它们的关系**：

  · `parasitic.ir_drop_report()["max_rel_err"]`   —— 2D 稠密 MNA 的**最坏列**压降
  · `array_scale.row_line_profile()["far_drop_rel"]` —— 1D 三对角**末端节点**压降（≡ 上一条）
  · `array_scale.row_line_profile()["avg_rel_err"]`  —— 1D **全列平均**输出误差
  · `array_scale.max_scale_for_budget()`          —— 仅 IR-drop 的可及规模上界（avg 口径）
  · `budget.max_scale_full_chain()`               —— 全链误差预算的可及规模上界（含失配/量化/编程）

🔴 **实测到的三处真缺陷（本模块 + 门禁逐条闭合）**：
  ① **对外载体口径未标注**：WebUI 案例卡 `SCALE_CEILING` 只给一个 `max_rows`，
     读者无法分辨它是「仅 IR」还是「全链」。实测 5% 预算：仅 IR = **18 行**，
     全链 = **12 行**，卡 note 原写「~18 行」而不标口径 ⇒ **读者会当成全链能力**。
  ② **对外载体存在不可复现的陈旧值**：`SCALE_PRESSURE_TIERS` 的 `ir_drop_rel`
     四点中只有 N=16（0.0375）与 N=1024（0.956）与当前默认参数现算的 **avg** 精确一致；
     N=64=0.152、N=256=0.549 与 avg（0.3738 / 0.8247）、far（0.5478 / 0.9937）**都对不上**
     ⇒ 参数自 E7/E9 引入后从未变更（git 已核），故不是参数漂移，是**引入时即不可复现**。
  ③ **门禁只判存在性、不判数值**：`run_ecore_case_smoke` 的 ⑲ 只检查该块「登记齐全」，
     `compression_1024` 是硬编码对硬编码 ⇒ **对外数字从未与底层模块真拉平**。

============================================================================
本模块给什么
----------------------------------------------------------------------------
1. **`SCALE_BASIS` 单一真源**：每个口径的 id / 定义式 / 单位 / 语义 / 属主函数 /
   是否可对外 / 是否必须成对出现 —— **机器可读**，且做**反向完备**
   （登记项必须解析到真实可调用对象；成对约束必须可机检）。
2. **解析金标（不是自证）**：行线 IR-drop 有**闭式解**，本模块给出
   `p_m = (u^{m+1} + u^{-m})/(1+u)`（`u = e^α`，`α = arccosh(1+g·r/2)`），
   由 KCL 递推 `p_0=1, p_1=1+g·r, p_m=(2+g·r)p_{m-1}-p_{m-2}` 精确导出，且
   等价于 `p_m = σ(α)e^{αm} + σ(-α)e^{-αm}`（`σ` = sigmoid）。
   ⇒ `far_drop_rel = 1 − 1/p_{n−1}`、`avg_rel_err = 1 − S/(n·p_{n−1})`，
   `S = u(u^n − u^{−n})/(u² − 1)`。**解析解 ⟷ Thomas 数值解是两条独立路径**，
   不是同一套公式算两遍。这是 E20 唯一的硬金标。
3. **成对输出**：`scale_ceiling_paired()` 同时给 `ir_only` 与 `full_chain` 两档，
   并标 `tighter`。**对外的规模数字必须成对出现**，否则读者必然误读。

============================================================================
红线（与全平台同源）
----------------------------------------------------------------------------
C 级自主（纯标准库 + numpy）· LLM 不进判决路径 · **只读消费** E7/E9/E15，
**不改** `ELEC_PROCESS` / `DEFAULT_CELL_PARAMS` / 任何既有默认值 ·
不报 TOPS/TOPS-W/fJ-op · 规模数字对外一律标「设计期版型容量 · 非流片」。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from lda_l2.ecore import array_scale as AS
from lda_l2.ecore import budget as BG
from lda_l2.ecore import parasitic as PA
from lda_l2.ecore.layout import DEFAULT_CELL_PARAMS
from lda_l2.ecore.mosfet import NmosParams

# ---------------------------------------------------------------------------
# ① 口径登记表（单一真源）
# ---------------------------------------------------------------------------
# 字段约定：
#   id            机器键（唯一，不得改名）
#   name          中文名（对外可直接用）
#   definition    定义式（**必须写出来**，这是防"两个数看起来矛盾"的唯一办法）
#   unit          relative | count | percent
#   semantics     这个量回答什么问题（**不是**它怎么算的）
#   owner         属主函数（"模块.函数"；反向完备会 import 并取属性校验）
#   field         属主函数返回 dict 里的字段名（None ⇒ 返回标量）
#   stricter_than 本口径比谁更严（None ⇒ 无）
#   claimable     能否作为对外能力表述
#   must_pair_with 对外时必须同时出现的口径 id（成对约束）
SCALE_BASIS: List[Dict] = [
    {
        "id": "ir_far_drop_rel",
        "name": "最坏列压降（末端节点 · 1D 行线 · 忽略列线电阻）",
        "definition": "1 − V[n−1]/v_in，其中 V 为行线电压剖面末端电压（列端理想虚地）",
        "unit": "relative",
        "semantics": "驱动最远那一列还剩下多少电压 —— 判「驱得动驱不动」",
        "owner": "lda_l2.ecore.array_scale.row_line_profile",
        "field": "far_drop_rel",
        "stricter_than": None,
        "claimable": True,
        "must_pair_with": ["ir_avg_rel_err", "ir_far_drop_rel_2d_with_col"],
    },
    {
        "id": "ir_avg_rel_err",
        "name": "全列平均输出误差（1D · 忽略列线电阻）",
        "definition": "1 − mean(V)/v_in",
        "unit": "relative",
        "semantics": "MVM 的平均输出误差 —— 判「算得准不准」（E9 规模律用此口径）",
        "owner": "lda_l2.ecore.array_scale.row_line_profile",
        "field": "avg_rel_err",
        "stricter_than": None,
        "claimable": True,
        "must_pair_with": ["ir_far_drop_rel"],
    },
    {
        "id": "ir_far_drop_rel_2d_with_col",
        "name": "最坏列压降（2D 稠密 MNA · **含列线电阻**）",
        "definition": "含行线 + 列线串联电阻的全阵列 MNA 求解，取最坏列输出相对误差",
        "unit": "relative",
        "semantics": "「列线电阻到底吃掉多少」的唯一可判量 —— 实测比 1D 高 **+29.8%~+40.7%**，"
                     "**不是二阶小量**（E20 量化，推翻旧披露措辞）",
        "owner": "lda_l2.ecore.parasitic.ir_drop_report",
        "field": "max_rel_err",
        "stricter_than": "ir_far_drop_rel",
        "claimable": True,
        "must_pair_with": ["ir_far_drop_rel"],
    },
    {
        "id": "max_rows_ir_only",
        "name": "可及规模上界（仅 IR-drop · 1D）",
        "definition": "在给定输出误差预算下，使 ir_avg_rel_err ≤ 预算的最大行数 N",
        "unit": "count",
        "semantics": "**只把行线压降**作为约束时的规模天花板 —— 是**乐观上界**",
        "owner": "lda_l2.ecore.array_scale.max_scale_for_budget",
        "field": None,
        "stricter_than": None,
        "claimable": True,
        "must_pair_with": ["max_rows_full_chain"],
    },
    {
        "id": "max_rows_full_chain",
        "name": "可及规模上界（全链误差预算）",
        "definition": "在给定预算下，使 E15 全链（IR + 失配 + 量化 + 编程 + 列共享）总误差 ≤ 预算的最大 N",
        "unit": "count",
        "semantics": "**把所有已建模的误差项一起算**的规模天花板 —— 是对外应报的那一档",
        "owner": "lda_l2.ecore.budget.max_scale_full_chain",
        "field": "n_max",
        "stricter_than": "max_rows_ir_only",
        "claimable": True,
        "must_pair_with": ["max_rows_ir_only"],
    },
]

#: 预算单位口径（D-195 实测踩过：两个函数一个吃 0.05、一个吃 5.0）
BUDGET_UNIT = {
    "lda_l2.ecore.array_scale.max_scale_for_budget": "fraction（0.05 = 5%）",
    "lda_l2.ecore.budget.max_scale_full_chain": "percent（5.0 = 5%）",
}

#: 对外成对约束组（每组内的口径必须同时出现，缺一即判违规）
PAIRED_GROUPS: List[List[str]] = [
    ["max_rows_ir_only", "max_rows_full_chain"],
    ["ir_far_drop_rel", "ir_avg_rel_err"],
    ["ir_far_drop_rel", "ir_far_drop_rel_2d_with_col"],
]

#: 默认工艺/器件档（只读消费 E6/E7/E9 的默认值，**本模块不另设参数**）
DEFAULT_VG = 2.5


# ---------------------------------------------------------------------------
# ② 解析金标（闭式）：行线 IR-drop
# ---------------------------------------------------------------------------
def row_line_alpha(gr: float) -> float:
    """衰减指数 α = arccosh(1 + g·r/2)（小 gr 用 log1p 防抵消）。"""
    gr = float(gr)
    if gr < 0.0:
        raise ValueError("gr 须 ≥ 0")
    if gr == 0.0:
        return 0.0
    x = 0.5 * gr
    # arccosh(1+x) = log1p(x + sqrt(x·(2+x)))  —— 避免 1+x 的抵消与 sqrt 的相消
    return math.log1p(x + math.sqrt(x * (2.0 + x)))


def _p_series(n: int, alpha: float) -> np.ndarray:
    """递推基 p_m（m=0..n−1）：p_0=1, p_1=1+gr, p_m=(2+gr)p_{m−1}−p_{m−2}。

    闭式 p_m = (u^{m+1} + u^{−m})/(1+u)，u=e^α。

    🔴 用**对数域**求值：n 到 1024 时 u^{n} 会溢出（gr 大时尤甚）。
    """
    if n <= 0:
        raise ValueError("n 须 > 0")
    if n == 1:
        return np.ones(1)
    m = np.arange(n, dtype=float)
    # log p_m = αm + log1p(exp(−α(2m+1))) − log1p(exp(−α))
    #   推导：(u^{m+1}+u^{−m})/(1+u) = u^m·(u + u^{−2m−1})/(1+u)
    #   小 α 时 u→1，用 log1p 保证精度；大 α 时指数项自动趋 0
    if alpha == 0.0:
        return np.ones(n)
    log_p = alpha * m + np.log1p(np.exp(-alpha * (2.0 * m + 1.0))) - math.log1p(math.exp(-alpha))
    return np.exp(log_p)


def row_line_closed_form(n: int, r_seg: float, g: float, v_in: float = 1.0) -> Dict:
    """行线 IR-drop 的**解析闭式**（与 `AS.row_line_profile` 的 Thomas 数值解独立）。

    数学来源（KCL，非拟合）：
      内部节点 `V_{k−1} − (2+gr)V_k + V_{k+1} = 0` ·
      末端 `V_{n−2} = (1+gr)V_{n−1}` · 首端 `V_0 = v_in`
      令 `V_k = p_{n−1−k}·V_{n−1}` ⇒ 二阶递推，特征根 `u`, `u^{−1}`，`u = e^α`，
      `α = arccosh(1+gr/2)`；由 `p_0=1, p_1=1+gr` 定系数得
      `p_m = (u^{m+1} + u^{−m})/(1+u)`（≡ `σ(α)e^{αm} + σ(−α)e^{−αm}`）。
    返回 `far_drop_rel = 1 − 1/p_{n−1}` · `avg_rel_err = 1 − S/(n·p_{n−1})` ·
      `S = u(u^n − u^{−n})/(u² − 1)`。
    """
    n = int(n)
    if n <= 0:
        raise ValueError("n 须 > 0")
    if g <= 0.0 or r_seg < 0.0:
        raise ValueError("g 须 > 0、r_seg 须 ≥ 0")
    v_in = float(v_in)
    gr = float(g) * float(r_seg)
    if n == 1 or gr == 0.0:
        return {"far_drop_rel": 0.0, "avg_rel_err": 0.0, "gr": gr,
                "alpha": 0.0, "p_end": 1.0, "method": "closed_form_degenerate"}

    alpha = row_line_alpha(gr)
    p = _p_series(n, alpha)
    p_end = float(p[-1])
    # 和 S：为防溢出，直接用 p 的和（解析式仅作交叉核对，见 self_check）
    s = float(np.sum(p))
    far = 1.0 - 1.0 / p_end
    avg = 1.0 - s / (n * p_end)
    return {"far_drop_rel": far, "avg_rel_err": avg, "gr": gr,
            "alpha": alpha, "p_end": p_end, "sum_p": s,
            "method": "closed_form"}


def closed_form_sum_n(n: int, alpha: float) -> float:
    """`Σ_{m=0}^{n−1} p_m` 的闭式：`u(u^n − u^{−n})/(u² − 1)`（对数域求值防溢出）。"""
    n = int(n)
    if n <= 0:
        raise ValueError("n 须 > 0")
    if alpha == 0.0:
        return float(n)
    # log 形式：S = u(u^n − u^{−n})/(u²−1) = (u^{n+1} − u^{1−n})/(u²−1)
    #   = exp(α(n+1))·(1 − exp(−2αn)) / (exp(2α) − 1)
    log_num = alpha * (n + 1) + math.log1p(-math.exp(-2.0 * alpha * n))
    log_den = math.log(math.expm1(2.0 * alpha))
    return math.exp(log_num - log_den)


# ---------------------------------------------------------------------------
# ③ 双口径并报 + 成对规模上界
# ---------------------------------------------------------------------------
def dual_ir_basis(n: int, r_seg: Optional[float] = None,
                  g: Optional[float] = None, v_in: float = 1.0,
                  params: Optional[Dict[str, float]] = None,
                  vg: float = DEFAULT_VG) -> Dict:
    """同一阵列的**两个 IR 口径并报**（far / avg），并给二者关系与闭式交叉核对。

    🔴 对外只报其中一个 = 口径丢失。本函数是**唯一**推荐的取数入口。
    """
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    n = int(n)
    ap = PA.array_parasitics(n, n, p)
    r = ap["r_row_seg_ohm"] if r_seg is None else float(r_seg)
    if g is None:
        nm = NmosParams(w_over_l=p["w_um"] / p["l_um"])
        g = nm.kp * nm.w_over_l * (vg - nm.vth0)
    num = AS.row_line_profile(n, r, g, v_in)
    clo = row_line_closed_form(n, r, g, v_in)
    far, avg = float(num["far_drop_rel"]), float(num["avg_rel_err"])
    return {
        "n": n, "r_row_seg_ohm": r, "g_s": float(g), "gr": float(num["gr"]),
        "ir_far_drop_rel": far,
        "ir_avg_rel_err": avg,
        "far_ge_avg": bool(far >= avg),
        "closed_form": {"far_drop_rel": clo["far_drop_rel"],
                        "avg_rel_err": clo["avg_rel_err"]},
        "closed_form_max_abs_diff": max(abs(far - clo["far_drop_rel"]),
                                        abs(avg - clo["avg_rel_err"])),
        "basis_pair": ["ir_far_drop_rel", "ir_avg_rel_err"],
    }


def scale_ceiling_paired(budgets: Sequence[float] = (0.10, 0.05, 0.02, 0.01),
                         r_seg: Optional[float] = None,
                         g: Optional[float] = None,
                         params: Optional[Dict[str, float]] = None,
                         vg: float = DEFAULT_VG,
                         scan_hi: int = 256) -> List[Dict]:
    """**成对**给出可及规模上界：`ir_only`（乐观）与 `full_chain`（对外应报）。

    🔴 `budgets` 用**分数**（0.05 = 5%）；内部转成 `budget.max_scale_full_chain`
    要求的百分数。两函数的预算单位不同，此处是唯一转换点（`BUDGET_UNIT` 已登记）。
    """
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    if r_seg is None or g is None:
        ap = PA.array_parasitics(64, 64, p)
        if r_seg is None:
            r_seg = ap["r_row_seg_ohm"]
        if g is None:
            nm = NmosParams(w_over_l=p["w_um"] / p["l_um"])
            g = nm.kp * nm.w_over_l * (vg - nm.vth0)
    out: List[Dict] = []
    for b in budgets:
        b = float(b)
        n_ir = int(AS.max_scale_for_budget(b, r_seg, g))
        n_fc = int(BG.max_scale_full_chain(b * 100.0, r_seg=r_seg, g=g,
                                           vg=vg, scan_hi=scan_hi)["n_max"])
        out.append({
            "budget_rel": b,
            "max_rows_ir_only": n_ir,
            "max_rows_full_chain": n_fc,
            "tighter": "max_rows_full_chain" if n_fc < n_ir else (
                "max_rows_ir_only" if n_ir < n_fc else "equal"),
            "full_chain_is_stricter": bool(n_fc <= n_ir),
            "basis_pair": ["max_rows_ir_only", "max_rows_full_chain"],
        })
    return out


def card_pressure_tiers(sizes: Sequence[int] = (16, 64, 256, 1024),
                        params: Optional[Dict[str, float]] = None,
                        vg: float = DEFAULT_VG) -> List[Dict]:
    """**从底层现算** WebUI 案例卡 `SCALE_PRESSURE_TIERS` 应有的值（供门禁对拍）。

    卡片刻意零重算（公开只读端点），故数值仍是硬编码；本函数是它的**唯一真源**，
    由 `run_ecore_e20_smoke` 逐点对拍 —— 这样「对外数字」与「底层能力」才真拉平。
    """
    out: List[Dict] = []
    for s in sizes:
        d = dual_ir_basis(int(s), params=params, vg=vg)
        out.append({
            "n": d["n"],
            "ir_drop_rel": d["ir_avg_rel_err"],       # 卡片口径 = avg（E9 规模律同源）
            "basis": "ir_avg_rel_err",
            "ir_far_drop_rel": d["ir_far_drop_rel"],   # 并报，防误读
        })
    return out


def col_resistance_contribution(n: int, params: Optional[Dict[str, float]] = None,
                                vg: float = DEFAULT_VG) -> Dict:
    """**量化「1D 忽略列线电阻」到底省掉了多少**（旧披露称"二阶项"，E20 实测推翻）。

    对同一阵列，分别解：
      · `r_col_seg = 0`（1D 等价：列端理想虚地）⇒ `max_rel_err`
      · `r_col_seg = 实测几何值`（2D 全 MNA）⇒ `max_rel_err`
    返回提升量 `rel_lift = with/without − 1`。

    🔴 **实测：+29.8%（N=32）~ +40.7%（N=8）** ⇒ 「二阶小量」的说法**不成立**，
    它是**主导量级修正**。以此判「1D 简化能不能用于对外规模结论」。
    """
    p = dict(DEFAULT_CELL_PARAMS)
    if params:
        p.update(params)
    n = int(n)
    ap = PA.array_parasitics(n, n, p)
    nm = NmosParams(w_over_l=p["w_um"] / p["l_um"])
    g = nm.kp * nm.w_over_l * (vg - nm.vth0)
    gm = np.full((n, n), g)
    vin = [1.0] * n
    without = float(PA.ir_drop_report(n, n, gm, vin, ap["r_row_seg_ohm"], 0.0)["max_rel_err"])
    with_col = float(PA.ir_drop_report(n, n, gm, vin, ap["r_row_seg_ohm"],
                                       ap["r_col_seg_ohm"])["max_rel_err"])
    return {
        "n": n,
        "r_row_seg_ohm": ap["r_row_seg_ohm"],
        "r_col_seg_ohm": ap["r_col_seg_ohm"],
        "far_1d_no_col": without,
        "far_2d_with_col": with_col,
        "rel_lift": (with_col / without - 1.0) if without > 0 else 0.0,
        "is_second_order_small": bool(without > 0 and (with_col / without - 1.0) < 0.10),
    }


def col_contribution_sweep(sizes: Sequence[int] = (4, 8, 16, 32),
                           params: Optional[Dict[str, float]] = None,
                           vg: float = DEFAULT_VG) -> List[Dict]:
    """逐规模量化列线电阻贡献（E20 的核心证据链）。"""
    return [col_resistance_contribution(s, params=params, vg=vg) for s in sizes]


# ---------------------------------------------------------------------------
# ④ 反向完备 / 成对约束机检
# ---------------------------------------------------------------------------
def _resolve(dotted: str):
    """把 "lda_l2.ecore.x.y" 解析成可调用对象（不使用 eval）。"""
    mod_name, _, attr = dotted.rpartition(".")
    mod = __import__(mod_name, fromlist=[attr])
    return getattr(mod, attr)


def basis_coverage_report() -> Dict:
    """反向完备：每条登记口径都必须解析到**真实可调用**对象（缺失即判违规）。"""
    missing, not_callable, ok = [], [], []
    for e in SCALE_BASIS:
        try:
            obj = _resolve(e["owner"])
        except Exception as ex:                       # noqa: BLE001
            missing.append({e["id"]: repr(ex)})
            continue
        if not callable(obj):
            not_callable.append({e["id"]: e["owner"]})
            continue
        ok.append(e["id"])
    declared = {e["id"] for e in SCALE_BASIS}
    dup = sorted({x for x in declared if [e["id"] for e in SCALE_BASIS].count(x) > 1})
    return {"ok": ok, "missing": missing, "not_callable": not_callable,
            "duplicate_ids": dup, "declared": sorted(declared)}


def pairing_report() -> Dict:
    """成对约束机检：`must_pair_with`（列表）必须**互相声明**且与 `PAIRED_GROUPS` 一致。"""
    ids = {e["id"] for e in SCALE_BASIS}
    by_id = {e["id"]: e for e in SCALE_BASIS}
    dangling, asym = [], []
    for e in SCALE_BASIS:
        for mp in (e.get("must_pair_with") or []):
            if mp not in ids:
                dangling.append({e["id"]: mp})
            elif e["id"] not in (by_id[mp].get("must_pair_with") or []):
                asym.append({e["id"]: mp})          # 单向声明 = 不对称
    decl_pairs = {frozenset([e["id"], mp])
                  for e in SCALE_BASIS for mp in (e.get("must_pair_with") or [])}
    group_pairs = {frozenset([a, b])
                   for grp in PAIRED_GROUPS
                   for i, a in enumerate(grp) for b in grp[i + 1:]}
    return {"dangling": dangling, "asymmetric": asym,
            "groups_not_declared": sorted(map(sorted, group_pairs - decl_pairs)),
            "declared_not_grouped": sorted(map(sorted, decl_pairs - group_pairs)),
            "consistent": not (dangling or asym) and (group_pairs == decl_pairs)}


# ---------------------------------------------------------------------------
# ⑤ 自检
# ---------------------------------------------------------------------------
def scale_basis_self_check(verbose: bool = False) -> bool:
    """≥ 14 项自检：解析金标 ⟷ 数值解 · 双口径序关系 · 成对约束 · 反向完备。"""
    msgs = []

    def chk(name, cond, detail=""):
        msgs.append((name, bool(cond), detail))
        return bool(cond)

    ok = True
    p = dict(DEFAULT_CELL_PARAMS)
    nm = NmosParams(w_over_l=p["w_um"] / p["l_um"])
    g = nm.kp * nm.w_over_l * (DEFAULT_VG - nm.vth0)
    r = PA.array_parasitics(64, 64, p)["r_row_seg_ohm"]

    # ① 解析金标 ≡ Thomas 数值解（两条独立路径）
    worst = 0.0
    for n in (2, 3, 4, 8, 16, 32, 64, 256, 1024):
        num = AS.row_line_profile(n, r, g)
        clo = row_line_closed_form(n, r, g)
        worst = max(worst, abs(num["far_drop_rel"] - clo["far_drop_rel"]),
                    abs(num["avg_rel_err"] - clo["avg_rel_err"]))
    ok &= chk("① 解析闭式 ≡ Thomas 三对角数值解（9 档 N，绝对差 < 1e-9）",
              worst < 1e-9, f"最大绝对差 {worst:.3e}")

    # ② Σp 的两种闭式一致（级数求和 ⟷ 有理闭式）
    a = row_line_alpha(g * r)
    d_sum = max(abs(float(np.sum(_p_series(n, a))) - closed_form_sum_n(n, a))
                for n in (2, 4, 8, 32, 256))
    ok &= chk("② Σp 级数求和 ≡ 有理闭式 u(u^n−u^{−n})/(u²−1)（绝对差 < 1e-10）",
              d_sum < 1e-10, f"最大绝对差 {d_sum:.3e}")

    # ③ 退化：r_seg=0 ⇒ 两口径均为 0（**本应恰好为 0 的对照组**）
    d0 = row_line_closed_form(32, 0.0, g)
    ok &= chk("③ 对照组 r_seg=0 ⇒ far=avg=0（精确 0，非近似）",
              d0["far_drop_rel"] == 0.0 and d0["avg_rel_err"] == 0.0)

    # ④ 序关系：far ≥ avg > 0（全 N 段成立）
    rel_ok = True
    for n in (2, 3, 8, 64, 1024):
        d = dual_ir_basis(n, r_seg=r, g=g)
        rel_ok &= bool(d["far_ge_avg"]) and d["ir_avg_rel_err"] > 0.0
    ok &= chk("④ 双口径序关系 far ≥ avg > 0（N=2/3/8/64/1024 全成立）", rel_ok)

    # ⑤ **精确代数恒等**：n=2 时 avg ≡ far/2（不是近似 —— 由 p 递推直推）
    #    n=2 ⇒ p_0=1, p_1=1+gr ⇒ far = gr/(1+gr)，avg = gr/(2(1+gr)) = far/2
    d2 = dual_ir_basis(2, r_seg=r, g=g)
    ok &= chk("⑤ n=2 时 avg ≡ far/2（精确代数恒等，非近似；差 < 1e-15）",
              abs(d2["ir_avg_rel_err"] - d2["ir_far_drop_rel"] / 2.0) < 1e-15,
              f"far={d2['ir_far_drop_rel']:.12f} avg={d2['ir_avg_rel_err']:.12f}")

    # ⑤b 两口径均随 N 严格单调增（一维链电压剖面的直接推论）
    fars = [dual_ir_basis(n, r_seg=r, g=g)["ir_far_drop_rel"] for n in (2, 4, 8, 16, 32)]
    avgs = [dual_ir_basis(n, r_seg=r, g=g)["ir_avg_rel_err"] for n in (2, 4, 8, 16, 32)]
    ok &= chk("⑤b far 与 avg 均随 N 严格单调增（N=2→32）",
              all(fars[i] < fars[i + 1] for i in range(len(fars) - 1))
              and all(avgs[i] < avgs[i + 1] for i in range(len(avgs) - 1)))

    # ⑥ 规模上界成对：全链 ≤ 仅 IR（严格更严）
    paired = scale_ceiling_paired()
    ok &= chk("⑥ 成对规模上界：full_chain ≤ ir_only（4 档预算全成立）",
              all(x["full_chain_is_stricter"] for x in paired),
              " / ".join(f"{int(x['budget_rel']*100)}%:{x['max_rows_ir_only']}vs"
                         f"{x['max_rows_full_chain']}" for x in paired))

    # ⑦ 5% 预算两个数必须都能复现（对外成对报的那两个）
    p5 = [x for x in paired if abs(x["budget_rel"] - 0.05) < 1e-12][0]
    ok &= chk("⑦ 5% 预算：仅IR=18 行 · 全链=12 行（两数均现算可复现）",
              p5["max_rows_ir_only"] == 18 and p5["max_rows_full_chain"] == 12,
              f"ir={p5['max_rows_ir_only']} full={p5['max_rows_full_chain']}")

    # ⑧ 预算单调：预算越紧 ⇒ 两档都不增
    ok &= chk("⑧ 预算收紧 ⇒ 两档规模上界均单调不增",
              all(paired[i]["max_rows_ir_only"] >= paired[i + 1]["max_rows_ir_only"]
                  and paired[i]["max_rows_full_chain"] >= paired[i + 1]["max_rows_full_chain"]
                  for i in range(len(paired) - 1)))

    # ⑨ 反向完备：登记项必须解析到可调用对象
    cov = basis_coverage_report()
    ok &= chk(f"⑨ 反向完备：{len(SCALE_BASIS)} 条口径全部解析到真实可调用对象",
              not cov["missing"] and not cov["not_callable"] and not cov["duplicate_ids"]
              and len(cov["ok"]) == len(SCALE_BASIS), str(cov["missing"]))

    # ⑮ 列线电阻贡献：**推翻「二阶小量」措辞**（实测 +29.8%~+40.7%）
    sweep = col_contribution_sweep()
    lifts = [x["rel_lift"] for x in sweep]
    ok &= chk("⑮ 列线电阻贡献 +29.8%~+40.7%（**不是二阶小量** ⇒ 旧披露措辞不成立）",
              all(0.25 < v < 0.45 for v in lifts)
              and not any(x["is_second_order_small"] for x in sweep),
              " / ".join(f"N={x['n']}:{x['rel_lift']*100:+.1f}%" for x in sweep))

    # ⑯ E7 卡片三点（含列线 2D max_rel_err）必须可由本模块现算复现
    #    🔴 容差 5e-3 的**依据**：卡片是 2~3 位有效数字（0.0042 / 0.0806 / 0.270），
    #       最粗一位（0.0042 vs 实测 0.004216）相对差 3.9e-3 ⇒ 容差须匹配卡片的书写精度，
    #       **不是放宽到"差不多就行"**（实测值已由本模块现算锁定）。
    card_e7 = {4: 0.0042, 16: 0.0806, 32: 0.270}
    d_e7 = max(abs(x["far_2d_with_col"] - card_e7[x["n"]]) / card_e7[x["n"]]
               for x in sweep if x["n"] in card_e7)
    ok &= chk("⑯ E7 卡片 IR drop 三点（0.42%/8.06%/27.0%）≡ 现算含列线 2D"
              "（相对差 < 5e-3 · 卡片 2~3 位有效数字）",
              d_e7 < 5e-3, f"最大相对差 {d_e7:.3e}")

    # ⑩ 成对约束自洽
    pr = pairing_report()
    ok &= chk("⑩ 成对约束自洽（无悬空 · 无不对称 · 组表与登记表一致）",
              pr["consistent"], str(pr))

    # ⑪ 预算单位已登记（两个函数单位不同，是真实踩点）
    ok &= chk("⑪ 预算单位口径已显式登记（fraction vs percent）",
              len(BUDGET_UNIT) == 2 and all("percent" in v or "fraction" in v
                                            for v in BUDGET_UNIT.values()))

    # ⑫ 卡片现算：N=16/1024 两点与 E9 蓝图公布的 3.75%/95.6% 一致
    tiers = card_pressure_tiers()
    t16 = [t for t in tiers if t["n"] == 16][0]["ir_drop_rel"]
    t1024 = [t for t in tiers if t["n"] == 1024][0]["ir_drop_rel"]
    ok &= chk("⑫ 卡片现算：N=16 ⇒ 3.75% · N=1024 ⇒ 95.6%（与 E9 蓝图公布值一致）",
              abs(t16 - 0.0375) < 5e-4 and abs(t1024 - 0.956) < 1e-3,
              f"{t16:.6f} / {t1024:.6f}")

    # ⑬ 卡片每档都带 basis 标注（防"单值无口径"复发）
    ok &= chk("⑬ 卡片每档都带 basis 标注（口径不可省略）",
              all(t.get("basis") == "ir_avg_rel_err" for t in tiers))

    # ⑭ 只读纪律：本模块不改被消费模块的默认值
    ok &= chk("⑭ 只读纪律：ELEC_PROCESS / DEFAULT_CELL_PARAMS 未被本模块改动",
              PA.ELEC_PROCESS["r_leak_ohm"] == 1.0e9
              and DEFAULT_CELL_PARAMS["w_um"] == 1.2
              and DEFAULT_CELL_PARAMS["l_um"] == 0.3)

    if verbose:
        for name, good, detail in msgs:
            print(("  [OK] " if good else "  [FAIL] ") + name
                  + (("  · " + detail) if detail else ""))
    return bool(ok)


SCALE_BASIS_DISCLOSURE = {
    "role": "E20 = 规模/误差口径的单一真源 + 行线 IR-drop 解析金标（闭合对外载体口径未标注）",
    "closed_defects": [
        "对外载体口径未标注（SCALE_CEILING / 卡 note 只给一个 max_rows）",
        "对外载体存在不可复现的陈旧值（SCALE_PRESSURE_TIERS 中间两点）",
        "门禁只判存在性不判数值（compression_1024 硬编码对硬编码）",
    ],
    "golden": "行线 IR-drop 解析闭式 p_m=(u^{m+1}+u^{-m})/(1+u)，u=e^α，α=arccosh(1+gr/2) "
              "—— 由 KCL 递推导出，与 Thomas 数值解**互相独立**对拍（差 < 1e-9）",
    "paired_rule": "对外的规模数字必须成对：max_rows_ir_only（乐观）+ max_rows_full_chain（应报）",
    "budget_unit": BUDGET_UNIT,
    "process": "工艺参数沿用 E6/E7 的公开典型量级占位（**非 Foundry PDK**）",
    "honest": "规模上界是**设计期版型容量**，非流片能力；不报 TOPS / TOPS-W / fJ/op",
    "red_line": "只读消费 E7/E9/E15，不改任何既有默认值 · 纯标准库+numpy · LLM 不进判决路径",
}
