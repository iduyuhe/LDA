"""行线电阻反解与版图可行性：**打开 N 的天花板**（E28 · D-203）。

## 本模块要回答的问题

E27 的结论是：**能效第一杠杆是行线电阻**（它决定 N 上界，N 决定 ADC 摊薄 ∝1/N）。
但 E27 只给了「r↓4× / r↓10×」这样的**目标倍数**，没说「用什么工艺/版图手段能拿到多少」。

本模块把「目标倍数」换成「**具体的版图动作 + 各自的代价**」。

## 物理依据（全部复用 E7 闭式，不另设口径）

```
R = ρ·L/(W·t)  ≡  R□·L/W,   R□ = ρ/t
C' = ε₀·ε_r·W/d           （平行板对地 + 经验耦合系数）
```

🔴 两条决定性性质：

| 性质 | 推论 |
|---|---|
| **`C` 的公式里没有 `t`** | ⇒ **加厚金属层 = 纯收益**（R↓ 而 C 完全不变） |
| **`R ∝ 1/W` 且 `C ∝ W`** | ⇒ `R·C` 与线宽**无关**（RC 不变）⇒ 加宽只改善**静态 IR drop**，代价是**动态功耗 ∝C** |

## 三条路径的量化（5% 误差预算 · 现算）

| 方案 | `r_eff` | N 上界 | ADC 项 | vs Mythic 8.3 | 行线功耗份额 |
|---|---|---|---|---|---|
| 基准 M1 单端（t=0.20 · W=0.40） | 0.504 | **12** | 179.2 fJ/op | **21.6×** | 0.09% |
| **A：M6 级厚金属**（t=1.00） | 0.1008 | **29** | 74.2 | 8.9× | 0.24% |
| **A：RDL/AP 厚金属**（t=2.00） | 0.0504 | **42** | 51.2 | 6.2× | 0.35% |
| **A + C：RDL + 双端驱动** | 0.0126 | **87** | 24.7 | **3.0×** | 0.73% |
| A + B + C：RDL + W0.8 + 双端 | 0.0063 | **125** | 17.2 | 2.1× | 1.05% |
| A + B + C：RDL + W2.0 + 双端 | 0.00252 | **200** | 10.8 | 1.3× | 1.68% |

## 🔴 结论

**「5% 预算只有 12 行」不是物理极限，是 `M1 + 单端驱动` 这个版图选择的结果。**

只换 RDL 厚金属（**零 C 代价**）⇒ 42 行；再加双端驱动 ⇒ **87 行**。
能效从「差 21.6×」缩到「**差 3.0×**」—— **7.2 倍改善，且主要成本只是换金属层 + 多一条驱动线。**

## 代价必须同屏（这是本模块的纪律）

- **换层**：需 via stack 到 RDL（每单元一组）+ 额外掩模 ⇒ **工艺成本，不是物理代价**
- **加宽**：`C ∝ W` ⇒ 行线动态功耗 ∝W ⇒ 实测份额 0.09% → 1.68%（**总功耗 +1.6%**，可接受）
- **双端驱动**：驱动器数量 ×2，且阵列左右边界需留出路由通道
- 🔴 **以上全部未做 DRC/LVS**（本模块只算 R/C 与规模，不出版图）

## 判据纪律

- **`R·C` 对 W 恒定** 是一条精确恒等式（0.111382 在 W=0.4/0.8/2.0 下逐位相等）——
  它是"加宽只换静态 IR、不换 RC"的**物理依据**，写成判据才守得住。
- **`C` 对 `t` 恒定** 是"换层纯收益"的依据，同样写成判据（探针：让 C 依赖 t ⇒ 必红）。
- N 上界用 E15 `max_scale_full_chain` **扫描**（`scan_hi` 显式放大到 512 并披露），
  **不二分**（`worst(N)` 非单调 —— 见 E15 的披露）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import adc_calibration as C
from lda_l2.ecore import budget as BG
from lda_l2.ecore import energy as E
from lda_l2.ecore import layout as LY
from lda_l2.ecore import parasitic as PA

#: 金属层登记（**公开典型量级 · 非 PDK**）
METAL_LAYERS: List[Dict] = [
    {"id": "m1", "name": "M1（现状 · 行线所在层）", "t_um": 0.20,
     "note": "标准逻辑最小金属，方块电阻最高"},
    {"id": "m2", "name": "M2 级", "t_um": 0.30, "note": "列线现用层"},
    {"id": "m4", "name": "M4 级", "t_um": 0.60, "note": "中层厚金属"},
    {"id": "m6", "name": "M6 级", "t_um": 1.00, "note": "上层厚金属"},
    {"id": "rdl", "name": "RDL / AP 厚金属", "t_um": 2.00,
     "note": "顶层厚铜/铝，CIM 阵列降 IR 的常规手段"},
]

#: 驱动方式（`r_factor` = 等效电阻倍率）
DRIVE_MODES: List[Dict] = [
    {"id": "single", "name": "单端驱动", "r_factor": 1.0,
     "why": "最坏点在远端：Σ_{m=1..N} m·r·I ≈ rI·N²/2"},
    {"id": "dual", "name": "双端驱动", "r_factor": 0.25,
     "why": "最坏点在中点：Σ_{m=1..N/2} m·r·I ≈ rI·N²/8 ⇒ 等效 r/4"},
]

#: 线宽档（加宽的代价在 `cost_model` 里显式给出）
WIDTHS: List[float] = [0.40, 0.60, 0.80, 2.00]

#: 方案组合（本模块的对外表）
PLANS: List[Dict] = [
    {"id": "base", "label": "基准 M1 单端", "layer": "m1", "width": 0.40, "drive": "single"},
    {"id": "a_m6", "label": "A：M6 级厚金属", "layer": "m6", "width": 0.40, "drive": "single"},
    {"id": "a_rdl", "label": "A：RDL 厚金属", "layer": "rdl", "width": 0.40, "drive": "single"},
    {"id": "ac", "label": "A+C：RDL + 双端驱动", "layer": "rdl", "width": 0.40, "drive": "dual"},
    {"id": "abc08", "label": "A+B+C：RDL + W0.8 + 双端", "layer": "rdl", "width": 0.80, "drive": "dual"},
    {"id": "abc20", "label": "A+B+C：RDL + W2.0 + 双端", "layer": "rdl", "width": 2.00, "drive": "dual"},
]

DEFAULT_PITCH_UM = float(LY.DEFAULT_CELL_PARAMS["pitch_x_um"])


def _layer(lid: str) -> Dict:
    for x in METAL_LAYERS:
        if x["id"] == lid:
            return x
    raise KeyError("未登记的金属层：" + lid)


def _drive(did: str) -> Dict:
    for x in DRIVE_MODES:
        if x["id"] == did:
            return x
    raise KeyError("未登记的驱动方式：" + did)


# ---------------------------------------------------------------------------
# ① 单段 R / C（**直接复用 E7 闭式**）
# ---------------------------------------------------------------------------
def seg_rc(layer: str = "m1", width_um: float = 0.40,
           pitch_um: Optional[float] = None,
           proc: Optional[Dict[str, float]] = None) -> Dict:
    """一段行线的 R 与 C（`R = ρL/(Wt)` · `C = wire_capacitance`）。

    🔴 **不重算闭式**：直接调 E7 `wire_resistance` / `wire_capacitance` / `sheet_resistance`。
    """
    pr = dict(PA.ELEC_PROCESS)
    if proc:
        pr.update(proc)
    L = float(DEFAULT_PITCH_UM if pitch_um is None else pitch_um)
    t = _layer(layer)["t_um"]
    r = PA.wire_resistance(L, float(width_um), pr["rho_cu_ohm_um"], t)
    c = PA.wire_capacitance(L, float(width_um), pr)["c_total_fF"]
    return {"layer": layer, "t_um": t, "width_um": float(width_um), "pitch_um": L,
            "r_seg_ohm": r, "c_seg_fF": c, "rc_product": r * c,
            "sheet_r_ohm_sq": PA.sheet_resistance(pr["rho_cu_ohm_um"], t),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ② 两条物理不变性（**金标**）
# ---------------------------------------------------------------------------
def rc_invariance() -> Dict:
    """**`R·C` 与线宽无关**（`R∝1/W`、`C∝W` ⇒ 乘积恒定）。

    ⇒ 加宽**不改变 RC 时间常数**，只改善**静态 IR drop**，代价是动态功耗 ∝C。
    """
    rows = [seg_rc("m1", w) for w in WIDTHS]
    rcs = [x["rc_product"] for x in rows]
    dev = (max(rcs) - min(rcs)) / (sum(rcs) / len(rcs))
    return {"rows": rows, "rc_values": rcs, "rel_dev": dev,
            "invariant": bool(dev < 1e-12),
            "verdict": "🔴 `R·C` 对线宽**恒定**（相对偏差 %.2e）⇒ 加宽只换静态 IR，不换 RC"
                       % dev,
            "tier": E.OUTPUT_TIER}


def c_vs_thickness() -> Dict:
    """**`C` 与金属厚度无关**（`C' = ε₀ε_r·W/d` 里没有 `t`）。

    ⇒ **换更厚的金属层是纯收益**：R↓ 而 C 完全不变。
    🔴 前提：ILD 厚度 `d` 不变（真实工艺里厚金属的 ILD 通常更厚 ⇒ C 会更低，本题保守按不变处理）。
    """
    rows = [{"layer": x["id"], "t_um": x["t_um"],
             "c_seg_fF": seg_rc(x["id"], 0.40)["c_seg_fF"],
             "r_seg_ohm": seg_rc(x["id"], 0.40)["r_seg_ohm"]} for x in METAL_LAYERS]
    cs = [x["c_seg_fF"] for x in rows]
    dev = (max(cs) - min(cs)) / (sum(cs) / len(cs))
    return {"rows": rows, "c_values": cs, "rel_dev": dev,
            "invariant": bool(dev < 1e-12),
            "verdict": "🔴 `C` 对金属厚度**恒定**（相对偏差 %.2e）⇒ "
                       "**换层是纯收益**（R 降而 C 不动）" % dev,
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ③ N 上界（**委托 E15 扫描** · scan_hi 显式放大并披露）
# ---------------------------------------------------------------------------
_SCAN_HI = 512


def n_ceiling_for(r_seg: float, budget_pct: float = 5.0,
                  scan_hi: int = _SCAN_HI) -> Dict:
    r = float(r_seg)
    full = BG.max_scale_full_chain(float(budget_pct), r_seg=r, scan_hi=int(scan_hi))
    iron = BG.max_scale_full_chain(float(budget_pct), r_seg=r, scan_hi=int(scan_hi),
                                   ir_drop_only=True)
    return {"r_seg_ohm": r, "n_max": int(full["n_max"]), "n_max_ir_only": int(iron["n_max"]),
            "saturated": bool(full.get("saturated")), "scan_hi": int(scan_hi),
            "budget_pct": float(budget_pct), "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ④ 方案表（**收益与代价必须同屏**）
# ---------------------------------------------------------------------------
_PLAN_CACHE: Optional[List[Dict]] = None


def plan_table(budget_pct: float = 5.0) -> List[Dict]:
    """六条方案的 `r_eff` → N 上界 → ADC 项 → vs Mythic → **代价**。"""
    global _PLAN_CACHE
    if _PLAN_CACHE is not None and abs(budget_pct - 5.0) < 1e-12:
        return _PLAN_CACHE
    e_conv_fj = C.anchor_energy_per_conversion("a28_8b")["e_conv_j"] * 1e15
    rows = []
    base_share = None
    for p in PLANS:
        rc = seg_rc(p["layer"], p["width"])
        dm = _drive(p["drive"])
        r_eff = rc["r_seg_ohm"] * dm["r_factor"]
        nc = n_ceiling_for(r_eff, budget_pct)
        n = nc["n_max"]
        adc = e_conv_fj / (2.0 * n)
        share = E.system_energy_report(n, g_s=1e-14)["power_share"].get("row_line", 0.0)
        if base_share is None:
            base_share = share
        rows.append({"id": p["id"], "label": p["label"], "layer": p["layer"],
                     "width_um": p["width"], "drive": p["drive"],
                     "r_seg_ohm": rc["r_seg_ohm"], "r_factor": dm["r_factor"],
                     "r_eff_ohm": r_eff, "c_seg_fF": rc["c_seg_fF"],
                     "n_max": n, "adc_fj": adc, "vs_mythic": adc / 8.3,
                     "row_line_share": share,
                     "cost_c": (rc["c_seg_fF"] / seg_rc("m1", 0.40)["c_seg_fF"]),
                     "tier": E.OUTPUT_TIER})
    if abs(budget_pct - 5.0) < 1e-12:
        _PLAN_CACHE = rows
    return rows


def best_plan(budget_pct: float = 5.0) -> Dict:
    """在**代价可接受**范围内给出推荐方案。

    推荐口径（**显式两项约束**）：`cost_c ≤ 2.0`（电容不超过 2×）且
    **行线功耗份额增量 < 2 个百分点**，在此范围内取 N 最大。
    ⇒ **A+B+C（RDL + W0.8 + 双端）**：N=125，C×2 但总功耗只 +0.70%。
    🔴 这是"**小代价换大收益**"，**不是零代价** —— 不写成"纯收益"是为了不误导。
    """
    rows = plan_table(budget_pct)
    ok = [r for r in rows if r["cost_c"] <= 2.0
          and (r["row_line_share"] - rows[0]["row_line_share"]) * 100.0 < 2.0]
    best = max(ok, key=lambda r: r["n_max"])
    base = rows[0]
    return {"plan": best, "baseline": base,
            "n_gain": best["n_max"] / base["n_max"],
            "eff_gain": base["adc_fj"] / best["adc_fj"],
            "verdict": ("🔴 推荐 **%s**：N %d → %d（%.2f×）· ADC 项 %.1f → %.1f fJ/op（%.2f×）· "
                        "vs Mythic %.1f× → **%.1f×** · 代价：C %.2f× / 总功耗 +%.2f%%"
                        % (best["label"], base["n_max"], best["n_max"],
                           best["n_max"] / base["n_max"], base["adc_fj"], best["adc_fj"],
                           base["adc_fj"] / best["adc_fj"], base["vs_mythic"],
                           best["vs_mythic"], best["cost_c"],
                           (best["row_line_share"] - base["row_line_share"]) * 100)),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑤ 代价模型（**不得只报收益**）
# ---------------------------------------------------------------------------
def cost_model(plan_id: str = "ac") -> Dict:
    """换层 / 加宽 / 双端 各自的代价（**物理的与工艺的分开列**）。"""
    rows = {r["id"]: r for r in plan_table()}
    p = rows[plan_id]
    base = rows["base"]
    c_ratio = p["cost_c"]
    return {
        "plan": plan_id, "label": p["label"],
        "physical": {
            "c_ratio": c_ratio,
            "row_line_share_from": base["row_line_share"],
            "row_line_share_to": p["row_line_share"],
            "total_power_penalty_pct": (p["row_line_share"] - base["row_line_share"]) * 100,
        },
        "process": {
            "via_stack_per_cell": 1 if p["layer"] != "m1" else 0,
            "extra_masks": 1 if p["layer"] == "rdl" else 0,
            "drivers_multiplied": 2.0 if p["drive"] == "dual" else 1.0,
            "routing_channel": "阵列左右边界需留驱动通道" if p["drive"] == "dual" else "单侧",
        },
        "not_modeled": ["via 电阻与占用面积", "厚金属的 DRC 最小线宽/间距",
                        "双端驱动的时序对齐与偏斜", "工艺成本与良率"],
        "verdict": ("代价：**电容 %.2f×**（总功耗 +%.2f%% 绝对值）· 工艺：via stack %s / 额外掩模 %s / "
                    "驱动器 ×%.0f。🔴 **以上未做 DRC/LVS** —— 本模块只算 R/C 与规模，不出版图"
                    % (c_ratio, (p["row_line_share"] - base["row_line_share"]) * 100,
                       "需要" if p["layer"] != "m1" else "不需要",
                       "需要" if p["layer"] == "rdl" else "不需要",
                       2.0 if p["drive"] == "dual" else 1.0)),
        "tier": E.OUTPUT_TIER,
    }


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def row_metal_self_check(verbose: bool = False) -> bool:
    checks: List[str] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append(("%s%s" % ("[OK] " if cond else "[NG] ", name)))
        if verbose:
            print("  %s%s%s" % ("[OK] " if cond else "[NG] ", name,
                                ("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① R□ ≡ ρ/t（与 E7 `sheet_resistance` 逐位一致）
    pr = PA.ELEC_PROCESS
    worst = 0.0
    for x in METAL_LAYERS:
        ref = PA.sheet_resistance(pr["rho_cu_ohm_um"], x["t_um"])
        worst = max(worst, abs(seg_rc(x["id"], 0.40)["sheet_r_ohm_sq"] - ref) / ref)
    ok &= chk("① `R□ ≡ ρ/t`（与 E7 `sheet_resistance` 逐位一致 · 5 层）",
              worst < 1e-15, "最大相对差 %.3e" % worst)

    # ② R ∝ 1/W（加倍宽 ⇒ 精确半电阻）
    r1 = seg_rc("m1", 0.40)["r_seg_ohm"]
    r2 = seg_rc("m1", 0.80)["r_seg_ohm"]
    ok &= chk("② `R(2W) ≡ R(W)/2`（R∝1/W · 精确）",
              abs(r2 / r1 - 0.5) < 1e-15, "%.9f" % (r2 / r1))

    # ③ C ∝ W（加倍宽 ⇒ 精确双倍电容）
    c1 = seg_rc("m1", 0.40)["c_seg_fF"]
    c2 = seg_rc("m1", 0.80)["c_seg_fF"]
    ok &= chk("③ `C(2W) ≡ 2·C(W)`（C∝W · 精确）",
              abs(c2 / c1 - 2.0) < 1e-15, "%.9f" % (c2 / c1))

    # ④ 🔴 金标：R·C 与 W 无关（4 档 W）
    inv = rc_invariance()
    ok &= chk("④ 🔴 `R·C` 对线宽**恒定**（4 档 W · 相对偏差 <1e-12）",
              inv["invariant"], "值 %.6f · 偏差 %.2e" % (inv["rc_values"][0], inv["rel_dev"]))

    # ⑤ 🔴 金标：C 与金属厚度无关（"换层纯收益"的物理依据）
    ct = c_vs_thickness()
    ok &= chk("⑤ 🔴 `C` 对金属厚度**恒定**（5 层 · 相对偏差 <1e-12）⇒ 换层是纯收益",
              ct["invariant"], "值 %.6f · 偏差 %.2e" % (ct["c_values"][0], ct["rel_dev"]))

    # ⑥ 双端驱动 ⇒ r_eff 精确 1/4
    ok &= chk("⑥ 双端驱动 `r_eff/r ≡ 0.25`（IR ∝ N²/8 vs N²/2）",
              abs(_drive("dual")["r_factor"] - 0.25) < 1e-15)

    # ⑦ N 上界随 r 单调不增（5 档）
    rs = [seg_rc("m1", 0.40)["r_seg_ohm"] * f for f in (1.0, 0.25, 0.1, 0.05, 0.02)]
    ns = [n_ceiling_for(r)["n_max"] for r in rs]
    ok &= chk("⑦ N 上界随 r 下降单调不减：%s" % ns,
              all(ns[i] <= ns[i + 1] for i in range(len(ns) - 1)) and ns[-1] > ns[0])

    # ⑧ 方案表数值复现（6 条）
    rows = plan_table()
    an_n = [12, 29, 42, 87, 125, 200]
    ok &= chk("⑧ 六条方案的 N 上界复现：%s" % an_n,
              [r["n_max"] for r in rows] == an_n)

    # ⑨ 🔴 代价必须报出，且随线宽单调上升（守"不得只报收益"）
    shares = [r["row_line_share"] for r in rows]
    ok &= chk("⑨ 🔴 代价（行线功耗份额）随方案推进上升：%s %%"
              % ["%.2f" % (s * 100) for s in shares],
              all(shares[i] <= shares[i + 1] + 1e-12 for i in range(len(shares) - 1))
              and shares[-1] > shares[0])

    # ⑩ 推荐方案必须在**两项显式约束**内（C ≤2× 且 行线份额增量 <2pp）
    bp = best_plan()
    d_pp = (bp["plan"]["row_line_share"] - bp["baseline"]["row_line_share"]) * 100.0
    ok &= chk("⑩ 推荐方案 %s 在约束内：C %.2f×（≤2）· 总功耗 +%.2f%%（<2pp）"
              % (bp["plan"]["label"], bp["plan"]["cost_c"], d_pp),
              bp["plan"]["cost_c"] <= 2.0 and d_pp < 2.0)

    # ⑪ 推荐方案的能效改善必须 >3×
    ok &= chk("⑪ 推荐方案能效改善 %.2f×（>3× ⇒ 天花板被打开）" % bp["eff_gain"],
              bp["eff_gain"] > 3.0)

    # ⑫ 输出恒 MODEL_ESTIMATE
    ok &= chk("⑫ 全部输出恒标 `MODEL_ESTIMATE`",
              rows[0]["tier"] == "MODEL_ESTIMATE" and bp["tier"] == "MODEL_ESTIMATE")

    if verbose:
        print()
        print("  %d/%d 通过" % (sum(1 for c in checks if c.startswith("[OK]")), len(checks)))
    return ok


ROW_METAL_DISCLOSURE = {
    "tier": E.OUTPUT_TIER,
    "is_measured": False,
    "core_finding": "**「5%% 预算只有 12 行」不是物理极限，是 `M1 + 单端驱动` 这个版图选择的结果。** "
                    "只换 RDL 厚金属（`C` 完全不变 ⇒ 零电容代价）⇒ 42 行；"
                    "再加双端驱动 ⇒ **87 行** ⇒ 面效从「差 21.6×」缩到「**差 3.0×**」（7.2 倍改善）。"
                    "物理依据：`C` 的闭式里**没有 `t`** ⇒ 换层纯收益；"
                    "`R·C` 对线宽**恒定** ⇒ 加宽只换静态 IR，代价是动态功耗。",
    "not_claimed": [
        "不宣称换层/加宽/双端驱动**已在版图上实现**（本模块只算 R/C 与规模，未做 DRC/LVS）",
        "不宣称 `t=2.0 µm` 与 `ρ_Cu=1.68e-2` 是 PDK 真值（公开典型占位）",
        "不宣称 87 行的阵列**电气可行**（IR drop 在预算内 ≠ 版图可布通）",
        "不宣称 vs Mythic 3.0× 是最终值（ADC 锚本身是区间 · E26）",
    ],
    "next_data_needed": "真实金属层方块电阻（PDK 或公开工艺表）+ RDL 的 DRC 最小线宽/间距 ⇒ "
                        "把方案从「设计目标」变成「可签核的版图约束」",
}
