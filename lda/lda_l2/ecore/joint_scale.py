"""N × K 联合规模优化：**天花板在哪、杠杆是什么**（E27 · D-202）。

## 本模块要回答的问题

E26 收口时留了一个悬案：`E23` 说「列共享 K=64 让地板从 19.27 → 9.38 fJ/op」，
但在 E26 的框架下，K 的作用从未被独立审计过。而「5% 预算只有 12 行」这个天花板
挡在所有能效数字前面，也一直没算过它对能效的影响。

本模块做两件事：
1. **审计 K**：列共享到底省了什么、代价是什么、净收益由谁决定；
2. **审计 N**：能效在**可及规模**（而非 N=64）上是多少，以及抬高 N 的杠杆是什么。

## 🔴 核心发现之一：E23 的 K 收益隐含了「β=1」，物理上不成立

ADC 功耗 `P_adc = n_adc · E_conv · f_adc`。

E23（`drive_scheme.scheme_energy_report`）的做法是：`adc_power_w(bits, ceil(n/K), f_s)`，
即 **ADC 数量 ÷K 而 `f_s` 不变**。这等于假设「一个 ADC 一次转换就能覆盖 K 列」——
**要么采样率 ×K，要么转换周期 ×K，两者必居其一，而两者都没建模。**

正确分解（区分动态 / 静态）：

```
P_adc(K) = n·f0·E_dyn + (n/K)·P_static          # 动态部分完全不受 K 影响
         = n·f0·E_conv·[1 − β·(1 − 1/K)]        # β ≡ E_static / E_conv
```

⇒ **K 的收益上界 = `1/(1−β)`，而 β 正是 E26 判定"不可建模"的那部分。**

| β（静态能量占比） | K=64 净收益 |
|---|---|
| 0.0188（E26 占位：仅预放大） | **0.9918× ⇒ 净亏损** |
| 0.10 | 1.079× |
| 0.30 | 1.381× |
| 0.50 | 1.916× |

### 还要扣掉 mux 侵蚀（E19 已建模 · ∝K）

保吞吐共享下 `erosion(K)`：K=8 → 0.99654、K=64 → 0.97297、K=160 → 0.93507。

⇒ **净收益 = 静态收益 × erosion(K)**，盈亏平衡的 β* 为：

| K | `β*` |
|---|---|
| 2 | 0.00087 |
| 8 | 0.00346 |
| 32 | 0.01370 |
| 64 | **0.02703** |
| 160 | 0.06494 |

🔴 **E26 的占位 β = 0.0209 < β*(64) = 0.0278 ⇒ 在 K=64 上是净亏损。**

## 🔴 核心发现之二：之前所有能效数字都建在「做不出来的规模」上

`E_op,adc = E_conv/(2·N·K)` —— **ADC 项被 `2N²` 个 op 摊薄 ⇒ ∝ 1/N**。

| N | ADC 项（28nm 锚） | 相对 N=64 |
|---|---|---|
| **12**（5% 预算可及 · 基准 r） | **179.2 fJ/op** | **5.33×** |
| 26（r/4） | 82.7 | 2.46× |
| 42（r/10） | 51.2 | 1.52× |
| 64（**E22–E26 一直用的**） | 33.6 | 1.00× |
| 140（r/100） | 15.4 | 0.46× |

⇒ **E26 报的「1.80×~7.98× vs Mythic」是 N=64 的区间。在可及的 N=12 上是 9.6×~21.6×。**

## 🔴 结论：能效第一杠杆是**行线电阻**，不是 K

| 杠杆 | 作用路径 | 5% 预算下的效果 |
|---|---|---|
| **行线电阻 r ↓4×** | N 上界 12→26 ⇒ ADC 项 ÷2.17 | **能效 ×2.17** |
| 行线电阻 r ↓10× | 12→42 | **×3.50** |
| 行线电阻 r ↓100× | 12→140 | **×11.6** |
| 列共享 K=64（β=0.0188） | 静态项 ÷64 × 侵蚀 | **×0.99（净亏）** |
| 列共享 K=64（β=0.3） | 同上 | ×1.38 |

⇒ **K 的收益符号由不可建模的 β 决定；而行线电阻的收益是确定且更大的。**

## 判据纪律（本模块的两处坑）

- 收益必须**相对 K=1 归一化**：K=1 本身有 0.043% 的 mux 基线开销，
  不归一化会把基线开销误算成"K 的损失"（**分母用错对象**）。
- `N ∝ 1/√r` 只是**近似**（IR drop ∝ N²r，但全链还有失配/量化项）——
  判据只要求**单调**，不要求幂律精确。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from lda_l2.ecore import adc_calibration as C
from lda_l2.ecore import budget as BG
from lda_l2.ecore import col_share_dynamic as CD
from lda_l2.ecore import device_family as D
from lda_l2.ecore import energy as E
from lda_l2.ecore import layout as LY
from lda_l2.ecore import parasitic as PA

#: 基准行线电阻（每段 · 由 E7 现算，**不硬编码**）
def baseline_r_seg() -> float:
    return PA.array_parasitics(64, 64, dict(LY.DEFAULT_CELL_PARAMS))["r_row_seg_ohm"]


#: E26 占位静态能量占比（仅比较器预放大 45 µW / 2.15 mW 档）
BETA_PLACEHOLDER = 45.0e-6 * 0.9 / (C.anchor_energy_per_conversion("a28_8b")["e_conv_j"]
                                    * 500e6)

#: 文献可辩护的 β 档位（静态能量占比 · **不可建模 · 只能给区间**）
BETA_SCENARIOS: List[Dict] = [
    {"beta": 0.0188, "label": "仅预放大静态（E26 占位）", "basis": "45 µW / 每次转换总能量"},
    {"beta": 0.10, "label": "低静态", "basis": "占位档"},
    {"beta": 0.30, "label": "中静态（含参考缓冲一部）", "basis": "占位档"},
    {"beta": 0.50, "label": "高静态（参考缓冲主导）", "basis": "占位档"},
]

#: 行线电阻缩放档（代表金属层/线宽/双端驱动的改善能力）
R_DIVS: List[Dict] = [
    {"r_div": 1, "label": "基准（M1 · 0.504 Ω/段）", "what": "当前布局"},
    {"r_div": 4, "label": "r/4", "what": "更宽线或上一层金属（等效）"},
    {"r_div": 10, "label": "r/10", "what": "高层厚金属 + 双端驱动"},
    {"r_div": 100, "label": "r/100", "what": "**理想上限**（不可达 · 仅作参考）"},
]


# ---------------------------------------------------------------------------
# ① N 上界 vs 行线电阻
# ---------------------------------------------------------------------------
def n_ceiling(r_div: float = 1.0, budget_pct: float = 5.0) -> Dict:
    """在给定误差预算下，行线电阻缩 `r_div` 倍时的可及规模上界。

    🔴 直接委托 E15 `max_scale_full_chain`（**不重算、不另设口径**）。
    """
    r = baseline_r_seg() / float(r_div)
    full = BG.max_scale_full_chain(float(budget_pct), r_seg=r)
    iron = BG.max_scale_full_chain(float(budget_pct), r_seg=r, ir_drop_only=True)
    return {"r_div": float(r_div), "r_seg_ohm": r, "budget_pct": float(budget_pct),
            "n_max": int(full["n_max"]), "n_max_ir_only": int(iron["n_max"]),
            "tier": E.OUTPUT_TIER}


def n_ceiling_table(budget_pct: float = 5.0) -> List[Dict]:
    rows = []
    n0 = None
    for d in R_DIVS:
        row = n_ceiling(d["r_div"], budget_pct)
        if n0 is None:
            n0 = row["n_max"]
        row.update({"label": d["label"], "what": d["what"],
                    "n_gain_vs_base": (row["n_max"] / n0 if n0 else None)})
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# ② ADC 项随 N 的摊薄（∝1/N · 精确）
# ---------------------------------------------------------------------------
def adc_dilution(n: int, anchor: str = "a28_8b", share_k: int = 1) -> Dict:
    """`E_op,adc = E_conv/(2·N·K)` ⇒ **∝1/N**（被 `2N²` 个 op 摊薄）。

    返回相对 N=64 的倍数（`64/n`，**精确**，与 `E_conv` 无关 ⇒ 可作金标）。
    """
    n = int(n)
    k = max(1, int(share_k))
    e = C.adc_energy_per_op_from_anchor(anchor, n, k)["adc_energy_per_op_fj"]
    e64 = C.adc_energy_per_op_from_anchor(anchor, 64, k)["adc_energy_per_op_fj"]
    return {"n": n, "anchor": anchor, "share_k": k,
            "adc_energy_per_op_fj": e,
            "ratio_vs_n64": e / e64,
            "exact_ratio_64_over_n": 64.0 / n,
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ③ K 的净收益（**相对 K=1 归一化** · 分母必须用对对象）
# ---------------------------------------------------------------------------
def k_net_gain(k: int, beta: float, n_cols: int = 64) -> Dict:
    """列共享 K 的**净能效收益**（相对 K=1）。

    ```
    static_gain = 1 / (1 − β·(1 − 1/K))          # 只有静态部分随 K 除以 K
    erosion     = e(K) / e(1)                    # E19 mux 建立侵蚀（∝K）
    net         = static_gain · erosion
    ```

    🔴 `e(1) ≠ 1`（K=1 本身有 0.043% 的基线 mux 开销）⇒ **必须归一化**，
    否则会把基线开销误算成"K 的损失"（分母用错对象 · 血案 290 同型）。
    """
    k = int(k)
    b = float(beta)
    e_k = CD.mux_settling_erosion(int(n_cols), k_adc=k, keep_throughput=True)["erosion_factor"]
    e_1 = CD.mux_settling_erosion(int(n_cols), k_adc=1, keep_throughput=True)["erosion_factor"]
    if not (0.0 <= b < 1.0):
        raise ValueError("beta 必须在 [0,1)")
    static_gain = 1.0 / (1.0 - b * (1.0 - 1.0 / k))
    erosion_rel = e_k / e_1
    net = static_gain * erosion_rel
    return {"k": k, "beta": b, "n_cols": int(n_cols),
            "static_gain": static_gain, "erosion_rel": erosion_rel,
            "net_gain": net,
            "profitable": bool(net > 1.0),
            "verdict": ("K=%-4d · β=%.4f ⇒ 静态收益 %.4f× × 侵蚀 %.6f = **净 %.4f×**（%s）"
                        % (k, b, static_gain, erosion_rel, net,
                           "↑ 正收益" if net > 1.0 else "↓ **净亏损**")),
            "tier": E.OUTPUT_TIER}


def k_breakeven_beta(k: int, n_cols: int = 64) -> Dict:
    """**盈亏平衡的静态能量占比** `β*`（闭式）。

    `1/(1−β(1−1/K)) · e(K)/e(1) = 1`
    ⇒ `β* = (1 − e(K)/e(1)) / (1 − 1/K)`

    🔴 **不能写成 `(e(1)/e(K) − 1)`** —— 两者不等（0.0270 vs 0.0273，差 2.7%）。
    `1 − x` 与 `1/x − 1` 只在 x 极接近 1 时才近似相等 ⇒ 判据 ④ 当场抓住（残差 4.8e-3）。
    """
    k = int(k)
    if k <= 1:
        return {"k": 1, "beta_star": 0.0, "note": "K=1 是基准，收益恒为 1",
                "tier": E.OUTPUT_TIER}
    e_k = CD.mux_settling_erosion(int(n_cols), k_adc=k, keep_throughput=True)["erosion_factor"]
    e_1 = CD.mux_settling_erosion(int(n_cols), k_adc=1, keep_throughput=True)["erosion_factor"]
    bs = (1.0 - e_k / e_1) / (1.0 - 1.0 / k)
    return {"k": k, "n_cols": int(n_cols), "beta_star": bs,
            "erosion_rel": e_k / e_1,
            "verdict": "K=%d ⇒ 只有 β > %.4f 时列共享才有净收益" % (k, bs),
            "tier": E.OUTPUT_TIER}


def k_gain_table(n_cols: int = 64) -> List[Dict]:
    """β 各档 × K 各档的净收益矩阵（**K 的收益符号由 β 决定**）。"""
    rows = []
    for sc in BETA_SCENARIOS:
        for k in (2, 8, 32, 64, 160):
            g = k_net_gain(k, sc["beta"], n_cols)
            rows.append({"beta": sc["beta"], "beta_label": sc["label"], "k": k,
                         "net_gain": g["net_gain"], "profitable": g["profitable"]})
    return rows


# ---------------------------------------------------------------------------
# ④ 可及规模下的能效（**不是 N=64**）
# ---------------------------------------------------------------------------
def attainable_efficiency(budget_pct: float = 5.0, anchor: str = "a28_8b",
                          k: int = 1) -> List[Dict]:
    """在**误差预算可及的 N** 上算能效（复现 E26 的 `floor_with_measured_adc`，但 N 由预算定）。

    🔴 这是 E22–E26 一直没做的事：它们在 **N=64** 上算能效，而 5% 预算只允许 12 行。
    """
    rows = []
    base = None
    for d in R_DIVS:
        nc = n_ceiling(d["r_div"], budget_pct)
        n = nc["n_max"]
        fl = C.floor_with_measured_adc(anchor, n)
        e_op = fl["e_floor_fj_per_op"]
        if k > 1:
            # 换算到共享 K：ADC 项 ÷ 净收益的倒数（其余项不变）
            g = k_net_gain(k, BETA_PLACEHOLDER)["net_gain"]
            e_op = fl["adc_from_measured_fj"] / g + fl["rest_fj"]
        if base is None:
            base = e_op
        rows.append({"r_div": d["r_div"], "label": d["label"], "n_max": n,
                     "adc_fj": fl["adc_from_measured_fj"], "rest_fj": fl["rest_fj"],
                     "e_op_fj": e_op, "vs_mythic": e_op / 8.3,
                     "gain_vs_base": (base / e_op if base else None)})
    return rows


# ---------------------------------------------------------------------------
# ⑤ 杠杆排序（**本模块的结论**）
# ---------------------------------------------------------------------------
def leverage_ranking(budget_pct: float = 5.0) -> Dict:
    """把「行线电阻」与「列共享 K」放在同一把尺子上比。

    尺子 = **相对基准的能效改善倍数**（`E_op(base) / E_op(方案)`）。
    """
    base_rows = attainable_efficiency(budget_pct, "a28_8b", k=1)
    base_e = base_rows[0]["e_op_fj"]
    levers = []
    for r in base_rows[1:]:
        levers.append({"lever": "行线电阻 " + r["label"], "kind": "row_resistance",
                       "detail": "N 上界 %d → %d" % (base_rows[0]["n_max"], r["n_max"]),
                       "gain": base_e / r["e_op_fj"]})
    for k in (8, 64):
        g = k_net_gain(k, BETA_PLACEHOLDER)["net_gain"]
        levers.append({"lever": "列共享 K=%d（β=%.4f）" % (k, BETA_PLACEHOLDER),
                       "kind": "column_share", "detail": "静态项 ÷K × mux 侵蚀",
                       "gain": g})
    levers.sort(key=lambda x: -x["gain"])
    best_r = max((l for l in levers if l["kind"] == "row_resistance"),
                 key=lambda x: x["gain"])
    best_k = max((l for l in levers if l["kind"] == "column_share"),
                 key=lambda x: x["gain"])
    return {"levers": levers, "base_e_op_fj": base_e,
            "row_resistance_wins": bool(best_r["gain"] > best_k["gain"]),
            "verdict": ("🔴 **能效第一杠杆 = 行线电阻**（最优 %.2f×）> 列共享 K（最优 %.2f×）。"
                        "K 的收益由不可建模的 β 决定（β=%.4f 时甚至净亏），"
                        "而行线电阻通过抬高 N 上界（%d→%d 行）**确定地**改善能效"
                        % (best_r["gain"], best_k["gain"], BETA_PLACEHOLDER,
                           base_rows[0]["n_max"], base_rows[-1]["n_max"])),
            "tier": E.OUTPUT_TIER}


# ---------------------------------------------------------------------------
# ⑥ 自检
# ---------------------------------------------------------------------------
def joint_scale_self_check(verbose: bool = False) -> bool:
    checks: List[str] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append(("%s%s" % ("[OK] " if cond else "[NG] ", name)))
        if verbose:
            print("  %s%s%s" % ("[OK] " if cond else "[NG] ", name,
                                ("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① ADC 摊薄：E_op(n)/E_op(64) ≡ 64/n（**精确**，与 E_conv 无关）
    worst = 0.0
    for n in (8, 12, 16, 26, 42, 64, 140):
        d = adc_dilution(n)
        worst = max(worst, abs(d["ratio_vs_n64"] - d["exact_ratio_64_over_n"])
                    / d["exact_ratio_64_over_n"])
    ok &= chk("① ADC 摊薄 `E_op(n)/E_op(64) ≡ 64/n`（精确恒等 · 7 档 N）",
              worst < 1e-12, "最大相对差 %.3e" % worst)

    # ② K=1 ⇒ 净收益恒 1（任意 β）
    g1 = [k_net_gain(1, b)["net_gain"] for b in (0.0, 0.1, 0.3, 0.5)]
    ok &= chk("② `k_net_gain(K=1, β) ≡ 1`（4 档 β · 归一化分母正确）",
              all(abs(x - 1.0) < 1e-15 for x in g1), " / ".join("%.12f" % x for x in g1))

    # ③ β=0 ⇒ 净收益 ≡ 相对侵蚀（全动态时 K 只有代价）
    g0 = k_net_gain(64, 0.0)
    e_k = CD.mux_settling_erosion(64, k_adc=64, keep_throughput=True)["erosion_factor"]
    e_1 = CD.mux_settling_erosion(64, k_adc=1, keep_throughput=True)["erosion_factor"]
    ok &= chk("③ `β=0 ⇒ 净收益 ≡ e(64)/e(1)`（全动态 ⇒ K 只有代价）",
              abs(g0["net_gain"] - e_k / e_1) < 1e-15,
              "%.9f vs %.9f" % (g0["net_gain"], e_k / e_1))

    # ④ β=β* ⇒ 净收益 ≡ 1（盈亏平衡定义，精确）
    worst = 0.0
    for k in (2, 8, 32, 64, 160):
        bs = k_breakeven_beta(k)["beta_star"]
        worst = max(worst, abs(k_net_gain(k, bs)["net_gain"] - 1.0))
    ok &= chk("④ `k_net_gain(K, β*(K)) ≡ 1`（盈亏平衡定义 · 5 档 K · 残差 <1e-12）",
              worst < 1e-12, "最大残差 %.3e" % worst)

    # ⑤ β* 单调递增（K 越大，要求的静态占比越高）
    bs = [k_breakeven_beta(k)["beta_star"] for k in (2, 4, 8, 16, 32, 64, 160)]
    ok &= chk("⑤ β* 随 K 单调递增（K 越大越难回本）",
              all(bs[i] < bs[i + 1] for i in range(len(bs) - 1)))

    # ⑥ 基准 β 落在 K=64 的盈亏平衡线**以下** ⇒ K=64 净亏
    bs64 = k_breakeven_beta(64)["beta_star"]
    ok &= chk("⑥ 🔴 基准 β=%.4f < β*(64)=%.4f ⇒ **K=64 净亏损**（%.4f×）"
              % (BETA_PLACEHOLDER, bs64, k_net_gain(64, BETA_PLACEHOLDER)["net_gain"]),
              BETA_PLACEHOLDER < bs64
              and k_net_gain(64, BETA_PLACEHOLDER)["net_gain"] < 1.0)

    # ⑦ 高 β 时 K=64 转为正收益（符号由 β 决定 ⇒ 不可作为设计杠杆）
    ok &= chk("⑦ β=0.30 ⇒ K=64 净收益 %.4f× >1（**符号由不可建模的 β 决定**）"
              % k_net_gain(64, 0.30)["net_gain"],
              k_net_gain(64, 0.30)["net_gain"] > 1.0)

    # ⑧ N 上界随 r 下降单调不减
    tab = n_ceiling_table()
    ns = [r["n_max"] for r in tab]
    ok &= chk("⑧ N 上界随行线电阻下降单调不减：%s" % ns,
              all(ns[i] <= ns[i + 1] for i in range(len(ns) - 1)) and ns[-1] > ns[0])

    # ⑨ 🔴 可及 N=12 上的能效必须显著差于 N=64（揭开"建在做不出的规模上"）
    d12 = adc_dilution(12)
    ok &= chk("⑨ 🔴 N=12 的 ADC 项是 N=64 的 %.2f×（之前所有能效数字都建在 N=64）"
              % d12["ratio_vs_n64"], d12["ratio_vs_n64"] > 5.0)

    # ⑩ 可及能效随 r 下降单调改善
    att = attainable_efficiency()
    es = [r["e_op_fj"] for r in att]
    ok &= chk("⑩ 可及能效随行线电阻下降单调改善：%s fJ/op"
              % ["%.1f" % x for x in es],
              all(es[i] > es[i + 1] for i in range(len(es) - 1)))

    # ⑪ 🔴 杠杆排序：行线电阻必须胜出
    lr = leverage_ranking()
    ok &= chk("⑪ 🔴 能效第一杠杆 = **行线电阻**（>K）：行线最优 %.2f× vs K 最优 %.2f×"
              % (max(l["gain"] for l in lr["levers"] if l["kind"] == "row_resistance"),
                 max(l["gain"] for l in lr["levers"] if l["kind"] == "column_share")),
              lr["row_resistance_wins"] is True)

    # ⑫ K 收益矩阵必须同时含正负（守"不得只报正收益"）
    gt = k_gain_table()
    ok &= chk("⑫ K 收益矩阵同时含正收益与净亏损（**不得只报正收益**）",
              any(r["profitable"] for r in gt) and any(not r["profitable"] for r in gt),
              "%d 正 / %d 负" % (sum(1 for r in gt if r["profitable"]),
                                sum(1 for r in gt if not r["profitable"])))

    # ⑬ 输出恒 MODEL_ESTIMATE
    ok &= chk("⑬ 全部输出恒标 `MODEL_ESTIMATE`",
              k_net_gain(8, 0.1)["tier"] == "MODEL_ESTIMATE"
              and lr["tier"] == "MODEL_ESTIMATE")

    if verbose:
        print()
        print("  %d/%d 通过" % (sum(1 for c in checks if c.startswith("[OK]")), len(checks)))
    return ok


JOINT_SCALE_DISCLOSURE = {
    "tier": E.OUTPUT_TIER,
    "is_measured": False,
    "core_finding": "① **E23 的列共享 K 收益隐含 β=1（ADC 全静态），物理不成立** —— "
                    "正确口径下 K 只省静态部分，再扣 mux 侵蚀；β=%.4f 时 K=64 **净亏 0.9934×**。"
                    "② **E22–E26 的能效都在 N=64 上算，而 5%% 预算只允许 N=12** —— "
                    "可及规模上 ADC 项高 5.33×（179.2 vs 33.6 fJ/op）。"
                    "③ ⇒ **能效第一杠杆是行线电阻**（r↓4× ⇒ N 12→26 ⇒ 能效 ×2.17），不是 K。"
                    % BETA_PLACEHOLDER,
    "not_claimed": [
        "不宣称任何列共享 K 的固定收益（符号由不可建模的 β 决定）",
        "不宣称 N=12 的能效是最终值（ADC 锚本身是区间 14.9~66.2 fJ/op @N=64）",
        "不宣称行线电阻可达 r/4 或 r/10（这是设计目标，不是本模型结论）",
    ],
    "next_data_needed": "参考缓冲的静态电流实测量（定 β）⇒ 才能判定列共享是否值得做",
}
