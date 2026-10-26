# -*- coding: utf-8 -*-
"""参考通道入设计点：把「CMR ≥ 42.37」这句话拆成**三条可闭合档**（v0.9.313 · `G_temp_drift_ref-a`）。

## 缺口原文（`sensor_case.G_temp_drift_ref`，未闭合）

> 现役设计点仍为 `CMR = 1.0`（无参考通道）：须 CMR ≥ **42.37** 才能使温漂项降到电学项以下，
> 比工艺典型 33.33 高 **1.27×** ⇒ 需锁相/调制参考或更优分光比；
> ⚠️ 未擅自改现役设计点与对外数字，仅并列披露。
> **能做且未做的具体工程动作：把参考通道纳入现役设计点（不是硬件锁死，是设计点选择）**。

`42.37` 这个数在 v0.9.297 里是**恒等式的一个推论**，不是独立指标：

```
dT_req  = LOD_elec / (dn/dT)                 （CMR=1 时 parity 所需温度稳定度 7.6584 µK）
δT_floor = T·√(k_B/C_ring)                   （器件自身热涨落下限 324.50 µK）
CMR_req  = δT_floor / dT_req = 42.3713       （即 v0.9.297 的 CMR_req·dT_req ≡ δT）
```

## 本模块做什么

**不改现役设计点、不改任何对外数字**（现役对外仍是 `CMR=1.0`、`LOD_temp=9.3e-7`），
只把「把参考通道纳入设计点」这个**设计点选择**做成三条**可机核**的闭合档：

| 档 | 手段 | 反解 | 实测裕度 | 代价 |
|---|---|---|---|---|
| **A 分光比** | 幅度平衡更紧 | `δ ≤ 1/CMR_req = 2.3601%` | 比工艺典型 3% 只紧 **1.2711×** | 需 trim / 校准工步 |
| **B 锁相平均** | `CMR_eff = CMR_typ·√N`（相干平均） | `N ≥ (CMR_req/CMR_typ)² = 1.6158` ⇒ **N=2** | `CMR_eff = 47.1405 ≥ 42.37` ✓ | 读出带宽 ÷N（或测量时间 ×N） |
| **C 热容放大** | 增大环热容 ⇒ `δT_floor ∝ 1/√C` | `C ×1.6158`（`C ∝ R` ⇒ **R 10 → 16.158 µm**） | 回代 `CMR_req' = 33.333` **恰等于**工艺典型 | FSR ÷1.6158（10.653 → 6.593 nm）⇒ 动态范围缩小 |

🔴 **三条都是「设计点选择」，都不需要新硬件**（B 甚至只要多测几次）。这是本缺口 note 里
「不是硬件锁死」那句话的**可执行版本**。

## 为什么不直接改现役设计点

现役对外数字（`DEFAULT_NOISE["CMR"]=1.0`、`LOD_temp=9.3e-7`、`dominant_limit="temp"`）
是**已经对外披露过的**。改它等于悄悄换口径 —— 与 v0.9.293 的 `H7`（未擅自改对外数字）
同一条纪律：**新档并列披露，默认值不动；动之前单独一版**。
判据 `S9` 把这条写成机核：`sensor_case.DEFAULT_NOISE["CMR"]` 必须仍等于 `CURRENT_DESIGN_CMR`。

## 诚实边界

* `CMR = 1/δ` 是**架构极限**（幅度平衡双通道）；实际还受探测器非线性、时序失配恶化
  ⇒ A 档的 2.3601% 是**下界要求**，不是可达值。
* `CMR_eff = CMR_typ·√N` 假定残余漂移是**零均值、样本间独立**的；若有 1/f 或温漂慢变，
  平均收益低于 `√N` ⇒ B 档的 N=2 是**乐观下界**。
* C 档 `C ∝ R` 来自 `ring_heat_capacity_j_per_k(R) = ρc_p·2πR·w·h`（线性）；同时 `FSR ∝ 1/R`
  ⇒ 换来的代价是动态范围。**本模块不给「哪一档最优」的结论** —— 三档代价量纲不同
  （工艺工步 / 带宽 / 面积），不可相加，也不可排序。
* 本层**不新增任何锚**：全部是恒等式与反解，没有物理标量对实测。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

__all__ = [
    "ANCHORABLE", "CURRENT_DESIGN_CMR", "R_UM_DESIGN",
    "budget", "product_invariance", "cmr_from_delta", "delta_for_cmr",
    "trim_closure", "lockin_closure", "thermal_mass_closure",
    "closure_options", "verdict", "why_not_anchored", "run_selfchecks",
]

#: 本层只证恒等式与反解，无物理标量对实测 ⇒ 不参与锚计数。
ANCHORABLE: bool = False

#: 现役设计点的 CMR（= 无参考通道）。**本模块不改它**；由门禁 `S9` 与卡内默认值对拍。
CURRENT_DESIGN_CMR: float = 1.0

#: 现役环半径（µm）—— 与 `sensor_case.DESIGN["R_um"]` 同源，由门禁 `S9` 对拍。
R_UM_DESIGN: float = 10.0


def why_not_anchored() -> str:
    """为什么本模块不可锚（须自答）。"""
    return ("本层证的是**恒等式与反解**：`CMR_req·dT ≡ δT`、三档闭合的反解与回代。"
            "没有任何物理标量对公开实测；三档「代价」还是三个不同量纲、不可排序 ⇒ 无锚可加。")


# ══════════════════════════════════════════════════════════════════════
# 预算（**读** sensor_temp_budget，不重算）
# ══════════════════════════════════════════════════════════════════════
def budget(*, r_um: float = R_UM_DESIGN, lod_elec_riu: float = 1.4244685071556232e-09,
           dn_dt_per_k: float = 1.86e-4, dT_stab_k: float = 5.0e-3,
           cmr: float = CURRENT_DESIGN_CMR) -> Dict[str, Any]:
    """取 `sensor_temp_budget` 的四条量（`dT_req` / `δT_floor` / `CMR_req` / `CMR_typ`）。

    🔴 参数默认值**取自卡片现役设计点**（`LOD_elec=1.4244685e-9` · `dn/dT=1.86e-4` ·
    `dT_stab=5 mK` · `CMR=1`），由门禁 `S1` 与 `sensor_case.case_card()["metrics"]` 逐位对拍。
    """
    from lda_l2 import sensor_temp_budget as STB

    rep = STB.temp_budget_report(float(r_um), float(lod_elec_riu), float(dn_dt_per_k),
                                 float(dT_stab_k), float(cmr))
    dT_req = float(rep["requirement"]["dT_req_K"])
    floor = float(rep["feasibility"]["thermal_floor_K"])
    cmr_req = float(rep["requirement"]["CMR_req_at_floor"])
    return {"r_um": float(r_um), "lod_elec_riu": float(lod_elec_riu),
            "dn_dt_per_k": float(dn_dt_per_k), "dT_stab_k": float(dT_stab_k),
            "cmr": float(cmr),
            "dT_req_k": dT_req, "delta_T_floor_k": floor,
            "cmr_req": cmr_req, "cmr_typ": float(STB.CMR_TYPICAL_PUBLIC),
            "shortfall_x": cmr_req / float(STB.CMR_TYPICAL_PUBLIC),
            "lod_temp_riu": float(rep["design_point"]["LOD_temp_riu"]),
            "lod_elec_riu_k": float(rep["design_point"]["LOD_elec_riu"]),
            "dominant": ("temp" if rep["design_point"]["LOD_temp_riu"]
                         > rep["design_point"]["LOD_elec_riu"] else "elec"),
            "note": ("🔴 `CMR_req ≡ δT_floor/dT_req`（v0.9.297 恒等式 `CMR_req·dT_req ≡ δT`）"
                     "⟹ **要求不是 42.37 这个数，是「CMR × dT_stab ≤ δT_floor」这个乘积**。")}


def product_invariance(*, dn_dt_per_k: float = 1.86e-4,
                       lod_elec_riu: float = 1.4244685071556232e-09,
                       dT_req_k: float = 7.658432834170017e-06,
                       dT_values: Tuple[float, ...] = (1e-5, 1e-3, 5e-3, 1e-2)) -> Dict[str, Any]:
    """两条**精确**不变式（不是「近似相等」）：

    ① `CMR_req(dT_stab) · dT_req ≡ dT_stab`      —— v0.9.297 恒等式的正确写法
    ② `CMR_req(dT_stab) / dT_stab ≡ (dn/dT)/LOD_elec`  —— 即 CMR_req **线性**于 dT

    🔴 第一版把不变式写成 `CMR_req × dT_stab ≡ const` —— **错的**：`CMR_req ∝ dT_stab`
    ⇒ 乘积 ∝ dT²，实测相对离散 **1e6**（判据 ③ 当场抓出）。正确的第二条是**商**不变。

    这条不变式的工程含义：**「CMR 门槛」与「温控门槛」是同一个乘积的两端**
    ⇒ 把温控做紧 1.271× 与把 CMR 做高 1.271× **等价**（本模块三档闭合里 A 与 C 正是这两个方向）。
    """
    from lda_l2 import sensor_temp_budget as STB

    dTr = float(dT_req_k)
    if not (dTr > 0.0):
        raise ValueError("dT_req 须为正（收到 %r）" % (dT_req_k,))
    rows = []
    for t in dT_values:
        c = float(STB.required_cmr_for_parity(float(dn_dt_per_k), float(t), float(lod_elec_riu)))
        rows.append({"dT_stab_k": float(t), "cmr_req": c,
                     "prod_with_dT_req": c * dTr,
                     "quot_cmr_over_dT": c / float(t)})
    # ① |CMR_req·dT_req − dT_stab| / dT_stab ≤ 1e-15
    spread1 = max(abs(r["prod_with_dT_req"] - r["dT_stab_k"]) / r["dT_stab_k"] for r in rows)
    # ② 商不变（相对离散）
    quots = [r["quot_cmr_over_dT"] for r in rows]
    spread2 = (max(quots) - min(quots)) / max(abs(min(quots)), 1e-300)
    return {"rows": rows, "spread_prod_identity": spread1, "spread_quot": spread2,
            "dn_over_lod": float(dn_dt_per_k) / float(lod_elec_riu),
            "invariant": bool(spread1 < 1e-15 and spread2 < 1e-15),
            "note": ("🔴 两条都是**恒等式**：`CMR_req·dT_req ≡ dT_stab` ∧ "
                     "`CMR_req/dT_stab ≡ (dn/dT)/LOD_elec`。"
                     "⇒ 「CMR 门槛」与「温控门槛」不是两个指标，是同一个乘积的两端。")}


# ══════════════════════════════════════════════════════════════════════
# 三档闭合
# ══════════════════════════════════════════════════════════════════════
def cmr_from_delta(delta: float) -> float:
    """`CMR = 1/δ`（幅度平衡双通道 · v0.9.291 的闭式，此处**引用而非另立**）。

    ⚠️ 与 `lda_webui.sensor_case.cmr_from_mismatch` 同源；由门禁 `S3` 逐值对拍
    （L2 不 import webui，避免层次倒置）。
    """
    d = float(delta)
    if d <= 0.0:
        return float("inf")
    return 1.0 / min(d, 1.0)


def delta_for_cmr(cmr: float) -> float:
    """`δ = 1/CMR`（反解；`CMR < 1` 无物理意义 ⇒ 返回 1.0）。"""
    c = float(cmr)
    if not (c >= 1.0):
        return 1.0
    return 1.0 / c


def trim_closure(cmr_req: float, cmr_typ: float, **kw: Any) -> Dict[str, Any]:
    """**A 档 · 分光比**：把幅度失配从工艺典型压到 `δ_max = 1/CMR_req`。"""
    req = float(cmr_req)
    typ = float(cmr_typ)
    if not (req >= 1.0) or not (typ >= 1.0):
        raise ValueError("CMR 须 ≥ 1（收到 req=%r typ=%r）" % (cmr_req, cmr_typ))
    d_max = delta_for_cmr(req)
    d_typ = delta_for_cmr(typ)
    return {"delta_max": d_max, "delta_typ": d_typ,
            "tighten_x": (d_typ / d_max if d_max > 0 else float("inf")),
            "cmr_achieved": cmr_from_delta(d_max),
            "feasible": bool(cmr_from_delta(d_max) >= req - 1e-12),
            "cost_kind": "trim/校准工步", "cost_unit": "道工步",
            "note": ("🔴 只紧 %.4f×（3%% → %.4f%%）—— 这不是「做不到」，是「要一道 trim」。"
                     % ((d_typ / d_max) if d_max > 0 else float("inf"), 100.0 * d_max))}


def lockin_closure(cmr_req: float, cmr_single: float) -> Dict[str, Any]:
    """**B 档 · 锁相/相干平均**：`CMR_eff = CMR_single·√N` ⇒ `N ≥ (req/single)²`。

    🔴 这里是 `√N` 不是 `N`：残余漂移按**幅度**抑制、噪声按**方差**平均。
    若误用线性律，`N=1` 就「够」了 —— 判据 `S7` 专门钉死这一点。
    """
    req = float(cmr_req)
    one = float(cmr_single)
    if not (req > 0.0) or not (one > 0.0):
        raise ValueError("CMR 须为正（收到 req=%r single=%r）" % (cmr_req, cmr_single))
    if one >= req:
        n_min = 1
    else:
        n_min = int(math.ceil((req / one) ** 2))
    eff = one * math.sqrt(n_min)
    # 🔴 N 必须取整 ⇒ 必然**过冲**：连续解 n* = (req/one)² = 1.6158，取整到 2 ⇒ 实际比 1.4142×
    n_star = (req / one) ** 2
    return {"n_min": n_min, "cmr_eff": eff, "feasible": bool(eff >= req - 1e-12),
            "n_star_continuous": n_star,
            "overshoot_x": (eff / req if req > 0 else float("inf")),
            "cmr_floor_with_n_minus_1": one * math.sqrt(max(n_min - 1, 0)),
            "n_min_linear_law": (1 if one >= req else int(math.ceil(req / one))),
            "cost_kind": "读出带宽（或测量时间）", "cost_unit": "×N",
            "note": ("🔴 `CMR_eff = CMR_single·√N` ⇒ 只需 **N=%d** 次平均即达 %.4f ≥ %.4f。"
                     "代价：带宽 ÷%d（或时间 ×%d）。" % (n_min, eff, req, n_min, n_min))}


def thermal_mass_closure(cmr_req: float, cmr_typ: float, *,
                         dT_req_k: float, temp_k: float = 293.15,
                         r_um: float = R_UM_DESIGN) -> Dict[str, Any]:
    """**C 档 · 放大环热容**：`δT_floor = T√(k_B/C)` ⇒ `C ∝ δT_floor^-2`。

    要求 `CMR_typ·dT_req ≥ δT_floor'` ⇒ `δT_floor' ≤ CMR_typ·dT_req` ⇒ `C'/C = (δT/δT')²`。
    因 `C = ρc_p·2πR·w·h ∝ R` ⇒ `R'/R = C'/C`，代价是 `FSR ∝ 1/R`。
    """
    from lda_l2 import sensor_temp_budget as STB

    req = float(cmr_req)
    typ = float(cmr_typ)
    dTr = float(dT_req_k)
    if not (req > 0.0 and typ >= 1.0 and dTr > 0.0):
        raise ValueError("非物理输入：req=%r typ=%r dT_req=%r" % (cmr_req, cmr_typ, dT_req_k))
    c_now = float(STB.ring_heat_capacity_j_per_k(float(r_um)))
    floor_now = float(STB.thermal_fluctuation_floor_k(float(temp_k), c_now))
    floor_need = typ * dTr                      # 工艺典型 CMR 所能容忍的温漂底
    c_scale = (floor_now / floor_need) ** 2
    c_need = c_now * c_scale
    floor_new = float(STB.thermal_fluctuation_floor_k(float(temp_k), c_need))
    cmr_after = floor_new / dTr                 # 回代：新设计点所需的 CMR
    return {"c_now_j_per_k": c_now, "c_need_j_per_k": c_need, "c_scale": c_scale,
            "floor_now_k": floor_now, "floor_need_k": floor_need, "floor_new_k": floor_new,
            "r_um_from": float(r_um), "r_um_to": float(r_um) * c_scale,
            "cmr_req_after": cmr_after, "cmr_typ": typ,
            "feasible": bool(cmr_after <= typ + 1e-9),
            "fsr_scale": (1.0 / c_scale),
            "cost_kind": "FSR（动态范围）与面积", "cost_unit": "÷%.4f×" % c_scale,
            "note": ("🔴 C ×%.4f ⇒ δT_floor %.6e → %.6e K ⇒ 所需 CMR 由 %.4f 降到 **%.4f**"
                     "（= 工艺典型）。代价：`FSR ∝ 1/R` ⇒ FSR ÷%.4f。"
                     % (c_scale, floor_now, floor_new, req, cmr_after, c_scale))}


def closure_options(**kw: Any) -> Dict[str, Any]:
    """三档并列（**不排序、不相加**：代价量纲各不相同）。"""
    b = budget(**{k: v for k, v in kw.items()
                  if k in ("r_um", "lod_elec_riu", "dn_dt_per_k", "dT_stab_k", "cmr")})
    a = trim_closure(b["cmr_req"], b["cmr_typ"])
    bb = lockin_closure(b["cmr_req"], b["cmr_typ"])
    c = thermal_mass_closure(b["cmr_req"], b["cmr_typ"], dT_req_k=b["dT_req_k"])
    return {"budget": b, "A_trim": a, "B_lockin": bb, "C_thermal_mass": c,
            "all_closable": bool(a["feasible"] and bb["feasible"] and c["feasible"]),
            "cost_units_distinct": len({a["cost_unit"] and a["cost_kind"],
                                        bb["cost_kind"], c["cost_kind"]}) == 3,
            "note": ("🔴 三档都能把「所需 CMR ≤ 42.3713」这一侧闭合；代价分别是"
                     "**工艺工步 / 带宽 / 面积·动态范围**，量纲不同 ⇒ **本层不给排序**。")}


def verdict() -> Dict[str, Any]:
    """本缺口的判词分两半：设计点侧（可闭合）与硬件侧（须流片）。"""
    return {
        "design_point_side": "closed",
        "hardware_side": "boundary",
        "current_design_unchanged": True,
        "design_point_actions": [
            "A 分光比：δ ≤ 2.3601%（工艺典型 3% 的 1.2711× 紧）",
            "B 锁相平均：N = 2（CMR_eff = 47.1405）",
            "C 放大热容：C ×1.6158 / R 10 → 16.158 µm（FSR ÷1.6158）",
        ],
        "boundary_reasons": [
            "片载参考通道**硬件**（分光器/双探测器/共模布局）须流片",
            "实测共模抑制比须在片测（本仓只给设计预算）",
            "`CMR=1/δ` 是架构极限，实际受探测器非线性/时序失配恶化 ⇒ A 档是下界要求",
        ],
        "must_not": "🔴 不得把三档写成「已验证可行」：它们是**设计预算**，不是实测抑制比；"
                    "也不得据此改现役对外数字（`CMR=1.0` / `LOD_temp=9.3e-7` / `dominant=temp`）。",
    }


# ══════════════════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════════════════
def run_selfchecks(verbose: bool = True) -> Tuple[int, int, List[str]]:
    """模块自检。返回 `(npass, total, lines)`。"""
    lines: List[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        lines.append("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                                    ("  |  " + detail) if detail else ""))

    b = budget()

    # ① 与 v0.9.297 的既存数字一致（42.3713 / 7.6584 µK / 324.50 µK）
    d1 = abs(b["cmr_req"] - 42.37128069221999) / 42.37128069221999
    d2 = abs(b["dT_req_k"] - 7.658432834170017e-06) / 7.658432834170017e-06
    d3 = abs(b["delta_T_floor_k"] - 3.2449760727913164e-04) / 3.2449760727913164e-04
    chk("① 与 v0.9.297 数字一致：CMR_req=%.6f（相对差 %.1e）∧ dT_req=%.6e ∧ δT_floor=%.6e"
        % (b["cmr_req"], d1, b["dT_req_k"], b["delta_T_floor_k"]),
        d1 < 1e-12 and d2 < 1e-12 and d3 < 1e-12)

    # ② 恒等式：CMR_req ≡ δT_floor / dT_req（逐位）
    ident = b["delta_T_floor_k"] / b["dT_req_k"]
    chk("② 恒等式 `CMR_req ≡ δT_floor/dT_req`（%.12f vs %.12f，|Δ|=%.1e）"
        % (b["cmr_req"], ident, abs(b["cmr_req"] - ident)),
        abs(b["cmr_req"] - ident) < 1e-12)

    # ③ 两条精确不变式（4 档）：CMR_req·dT_req ≡ dT_stab ∧ CMR_req/dT_stab ≡ (dn/dT)/LOD_elec
    pi = product_invariance()
    chk("③ 🔴 两条不变式：`CMR_req·dT_req ≡ dT_stab`（相对 %.1e）∧ `CMR_req/dT_stab ≡ "
        "(dn/dT)/LOD_elec`（相对 %.1e）—— 4 档 dT=1e-5…1e-2"
        % (pi["spread_prod_identity"], pi["spread_quot"]), pi["invariant"],
        "商=%.6e" % pi["dn_over_lod"])

    # ④ A 档：δ_max = 1/CMR_req，紧度 = CMR_req/CMR_typ
    a = trim_closure(b["cmr_req"], b["cmr_typ"])
    chk("④ A 档 trim：δ_max = %.6f（= 1/%.4f）∧ 紧度 %.6f× = CMR_req/CMR_typ ∧ 回代达标"
        % (a["delta_max"], b["cmr_req"], a["tighten_x"]),
        abs(a["delta_max"] * b["cmr_req"] - 1.0) < 1e-15
        and abs(a["tighten_x"] - b["cmr_req"] / b["cmr_typ"]) < 1e-12
        and a["feasible"])

    # ⑤ B 档：N_min = ⌈(req/typ)²⌉ = 2，回代 47.14 ≥ 42.37；且 N=1 不满足
    bb = lockin_closure(b["cmr_req"], b["cmr_typ"])
    chk("⑤ B 档锁相：N_min = %d（= ⌈(%.4f/%.4f)²⌉）∧ CMR_eff = %.6f ≥ %.6f ∧ N=1 时 %.4f < %.4f"
        % (bb["n_min"], b["cmr_req"], b["cmr_typ"], bb["cmr_eff"], b["cmr_req"],
           b["cmr_typ"], b["cmr_req"]),
        bb["n_min"] == 2 and bb["feasible"] and b["cmr_typ"] < b["cmr_req"])

    # ⑥ C 档：C ×1.6158 ⇒ 回代 CMR_req' ≡ CMR_typ
    c = thermal_mass_closure(b["cmr_req"], b["cmr_typ"], dT_req_k=b["dT_req_k"])
    chk("⑥ C 档热容：C ×%.6f（R %.3f → %.3f µm）⇒ 回代 CMR_req' = %.6f ≡ CMR_typ %.6f"
        % (c["c_scale"], c["r_um_from"], c["r_um_to"], c["cmr_req_after"], c["cmr_typ"]),
        abs(c["cmr_req_after"] - c["cmr_typ"]) < 1e-9 and c["feasible"],
        "δT_floor %.6e → %.6e K" % (c["floor_now_k"], c["floor_new_k"]))

    # ⑦ 同一道墙：A / C 精确落在 CMR_req/CMR_typ；B 因 **N 必须取整** 过冲
    span = b["cmr_req"] / b["cmr_typ"]
    chk("⑦ 同一道墙 %.6f×：A %.6f（精确）· C %.6f（精确）· B %.6f（= √⌈n*⌉/√n* 的**取整过冲**，"
        "n* = %.6f → N = %d）"
        % (span, a["tighten_x"], math.sqrt(c["c_scale"]),
           bb["cmr_eff"] / b["cmr_typ"], bb["n_star_continuous"], bb["n_min"]),
        abs(a["tighten_x"] - span) < 1e-12
        and abs(math.sqrt(c["c_scale"]) - span) < 1e-9
        and bb["cmr_eff"] / b["cmr_typ"] >= span - 1e-12
        and abs(bb["overshoot_x"] - math.sqrt(bb["n_min"] / bb["n_star_continuous"])) < 1e-12)

    # ⑧ 🔴 反向探针 A：把 δ_max 误写成工艺典型 δ_typ（3%）⇒ ④ 必红
    wrong_a = a["delta_typ"]
    chk("⑧ 反向探针 A：若 δ_max 取工艺典型 %.4f%%（而非 %.4f%%）⇒ 回代 CMR 仅 %.4f < %.4f ⇒ ④ 必红"
        % (100 * wrong_a, 100 * a["delta_max"], cmr_from_delta(wrong_a), b["cmr_req"]),
        cmr_from_delta(wrong_a) < b["cmr_req"])

    # ⑨ 🔴 反向探针 B：用 4× 比值让两律分道（1.27× 时两律都给 N=2，**没有判别力**）
    probe = lockin_closure(400.0, 100.0)
    chk("⑨ 🔴 反向探针 B：req/single = 4× ⇒ √N 律要 N=%d ∧ 线性律只要 N=%d（差 4×）"
        "（1.27× 时两律都给 2，**没有判别力** —— 第一版就在此踩空）"
        % (probe["n_min"], probe["n_min_linear_law"]),
        probe["n_min"] == 16 and probe["n_min_linear_law"] == 4
        and abs(probe["cmr_eff"] - 400.0) < 1e-9)

    # ⑩ 三方反解互洽：A/B/C 各自回代都命中同一目标
    # 🔴 B 是**整数**解 ⇒ 只能断言 `cmr_eff ≥ req` ∧ `N−1` 次不够（不能断言「恰等于」）
    ok10 = (abs(a["cmr_achieved"] - b["cmr_req"]) < 1e-9 * b["cmr_req"]
            and bb["cmr_eff"] >= b["cmr_req"] - 1e-12
            and bb["cmr_floor_with_n_minus_1"] < b["cmr_req"]
            and abs(c["cmr_req_after"] - b["cmr_typ"]) < 1e-9)
    chk("⑩ 三档反解回代互洽（A 恰命中 CMR_req ∧ B 整数解 ≥ CMR_req 且 N−1 不够 ∧ C 命中原 CMR_typ）",
        ok10, "A=%.6f B=%.6f(N-1→%.4f) C=%.6f"
        % (a["cmr_achieved"], bb["cmr_eff"], bb["cmr_floor_with_n_minus_1"],
           c["cmr_req_after"]))

    # ⑪ 非物理输入必须抛（5 类）
    guard = 0
    for fn, kw in ((trim_closure, {"cmr_req": 0.5, "cmr_typ": 33.3}),
                   (trim_closure, {"cmr_req": 42.4, "cmr_typ": 0.5}),
                   (lockin_closure, {"cmr_req": 0.0, "cmr_single": 33.3}),
                   (lockin_closure, {"cmr_req": 42.4, "cmr_single": -1.0}),
                   (thermal_mass_closure, {"cmr_req": 42.4, "cmr_typ": 33.3, "dT_req_k": 0.0})):
        try:
            fn(**kw)
        except ValueError:
            guard += 1
    chk("⑪ 非物理输入 5 类（CMR<1 两侧 / CMR≤0 / single<0 / dT_req=0）全部 raise",
        guard == 5, "拦截 %d/5" % guard)

    # ⑫ 单调性：dT_stab↑ ⇒ CMR_req↑；CMR_single↑ ⇒ N_min 非增
    from lda_l2 import sensor_temp_budget as STB
    c1 = STB.required_cmr_for_parity(1.86e-4, 1e-3, 1.4244685071556232e-09)
    c2 = STB.required_cmr_for_parity(1.86e-4, 1e-2, 1.4244685071556232e-09)
    n1 = lockin_closure(42.3713, 33.0)["n_min"]
    n2 = lockin_closure(42.3713, 45.0)["n_min"]
    chk("⑫ 单调：dT 1e-3→1e-2 ⇒ CMR_req %.3f→%.3f 升 ∧ CMR_single 33→45 ⇒ N 由 %d 降到 %d"
        % (c1, c2, n1, n2), c2 > c1 and n2 <= n1)

    # ⑬ 🔴 代价量纲不可相加/不可排序（写成显式断言）
    co = closure_options()
    kinds = {co["A_trim"]["cost_kind"], co["B_lockin"]["cost_kind"],
             co["C_thermal_mass"]["cost_kind"]}
    chk("⑬ 🔴 三档代价量纲互不相同（%d 类：%s）⇒ `cost_units_distinct` 为真，本层**不给排序**"
        % (len(kinds), " / ".join(sorted(kinds))),
        co["cost_units_distinct"] and len(kinds) == 3 and co["all_closable"])

    # ⑭ 判词：设计点侧 closed / 硬件侧 boundary ∧ 现役不变
    v = verdict()
    chk("⑭ 判词：设计点侧 `%s` / 硬件侧 `%s` ∧ `current_design_unchanged`=%s ∧ 边界理由 %d 条"
        % (v["design_point_side"], v["hardware_side"],
           v["current_design_unchanged"], len(v["boundary_reasons"])),
        v["design_point_side"] == "closed" and v["hardware_side"] == "boundary"
        and v["current_design_unchanged"] is True and len(v["boundary_reasons"]) == 3)

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print("sensor_ref_design 自检：%d/%d PASS" % (npass, len(lines)))
    return npass, len(lines), lines


if __name__ == "__main__":
    import sys
    _p, _t, _ = run_selfchecks()
    sys.exit(0 if _p == _t else 1)
