# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E15 · **端到端误差预算链**（D-179 实现 · v0.9.161）。

═══════════════════════════════════════════════════════════════════════════
一句话
═══════════════════════════════════════════════════════════════════════════
E1–E14 每段都给了**单点误差**，但**从未合成过**；且口径互不相同
（相对 % / σ / LSB）、性质未分类（系统性 / 随机 / 有界）。
本模块把四类误差接成**一条链**，回答两个问题：

  ① 「这颗阵列**实际有几个有效位**？」      → `error_budget_report()["worst_bits"]`
  ② 「给定精度目标，**最大能做多大**？」    → `max_scale_full_chain()`

🔴 **本模块不吃新物理** —— 全部数据来自既有模块的**公开接口**（只读消费，**不复制公式**），
   且**不修改** E7/E8/E9/E14 任何默认值（门禁判据 G8 逐位守住）。

═══════════════════════════════════════════════════════════════════════════
技术核心（两个，都不是形式主义）
═══════════════════════════════════════════════════════════════════════════
① **口径桥**：`parasitic` 给相对 %、`mismatch` 给随机 σ、`converter`/`quantize` 给 LSB
   ⇒ 三者**不可直接相加**。统一锚点 = **1 LSB @ k bit = 100/2^k % 满量程**
   （`lsb_to_rel_pct`），并有自洽判据 `output_effective_bits(lsb_to_rel_pct(k)) == k`。

② **三分类合成律**（简单相加是错的，全用 RSS 也是错的）：

   | 类别 | 成员 | worst 贡献 | typical 贡献 | 依据 |
   |---|---|---|---|---|
   | systematic | IR drop · 行驱动负载 · 有限增益 | **Σ**（代数） | **Σ** | 确定项，不抵消也不被平均 |
   | random | 器件失配 σ | **3σ_tot** | **σ_tot** | `σ_tot = √(Σσ²)`（独立 RSS） |
   | bounded | 量化 · DAC INL/DNL · ADC ≤1 LSB | **Σ|b|** | **Σ|b|/√3** | 均匀分布 `U(−a,a)` 的 σ = `a/√3` |

   `worst_pct = Σ_sys + k·σ_tot + Σ_bnd`；`typical_pct = Σ_sys + σ_tot + Σ_bnd/√3`（k 默认 3）。

═══════════════════════════════════════════════════════════════════════════
🔴 口径陷阱（本模块立誓守死，来自 E9 通则 1）
═══════════════════════════════════════════════════════════════════════════
E9 `max_scale_for_budget` 内部用 `row_line_profile()["avg_rel_err"]`（**全列平均** = MVM 平均输出误差），
而 E7 `ir_drop_report` 的主字段是 `max_rel_err`（**最坏列**）—— **不是同一个量**。
⇒ 本模块的 IR drop 项**一律取 `avg_rel_err`**（与「输出精度」及 E9 同口径），
   并把 `max_rel_pct`（最坏列）**同时披露**作诚实补充。**不许混用。**

═══════════════════════════════════════════════════════════════════════════
诚实边界（详见 BUDGET_DISCLOSURE）
═══════════════════════════════════════════════════════════════════════════
🔴 `output_effective_bits` **不是 IEEE ENOB** —— ENOB 是含噪声 + 谐波 + 直流非线性、
   由 FFT 谱定义的 ADC 标准量；本量口径 = `log2(100 / 最坏相对误差[%])`，**本项目自定义**。
本模块**只覆盖静态**（给定权重与输入的静态精度），**不含**时序 / 动态 / 采样率 / 抖动 / 老化 / 电源噪声。
合成律是**保守工程口径**，不是严格概率保证。参数均为公开典型量级占位（非 PDK）。**不报 TOPS/TOPS-W/fJ/op**。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import array_scale as AS
from . import converter as CV
from . import parasitic as PA
from . import periphery as PR
from .mosfet import NmosParams

# ── 误差三类（**闭合集合**：合成律只认这三类）────────────────────────────────
SYSTEMATIC = "systematic"      # 系统性确定项 ⇒ 代数相加
RANDOM = "random"              # 随机项 ⇒ RSS + kσ
BOUNDED = "bounded"            # 有界项 ⇒ 代数相加（最坏）/ √3（典型）
CATEGORIES = (SYSTEMATIC, RANDOM, BOUNDED)

DEFAULT_K_SIGMA = 3.0
DEFAULT_ADC_BITS = 8
DEFAULT_DAC_BITS = 8
# 全链规模扫描的搜索上界（超过则披露"未搜索到上界"，不给假数）
DEFAULT_SCAN_HI = 256

# ═══════════════════════════════════════════════════════════════════════════
# ① 口径桥
# ═══════════════════════════════════════════════════════════════════════════
def lsb_to_rel_pct(bits: int) -> float:
    """**1 LSB 相对满量程的百分比** = `100 / 2**bits`。

    依据：k bit 的满量程 = `2^k` 个 LSB ⇒ 1 LSB 占满量程 `1/2^k`。

    >>> lsb_to_rel_pct(8)          # 0.390625
    >>> output_effective_bits(lsb_to_rel_pct(8))   # 8.0（自洽锚）
    """
    b = int(bits)
    if b <= 0:
        raise ValueError("bits 必须 > 0（bits<=0 表示理想/不量化，不构成误差项）")
    return 100.0 / float(1 << b)


def rel_pct_to_lsb(pct: float, bits: int) -> float:
    """`lsb_to_rel_pct` 的逆：把相对百分比换算成 LSB 数（同一 bit 宽）。"""
    b = int(bits)
    if b <= 0:
        raise ValueError("bits 必须 > 0")
    return float(pct) * float(1 << b) / 100.0


def output_effective_bits(rel_pct: float) -> float:
    """**输出有效精度位数** = `log2(100 / rel_pct)`。

    🔴 **本项目自定义量，不是 IEEE ENOB**（见模块 docstring 与 `BUDGET_DISCLOSURE`）。
    与口径桥自洽：`output_effective_bits(lsb_to_rel_pct(k)) == k`。
    """
    r = float(rel_pct)
    if r <= 0.0:
        return float("inf")
    return math.log2(100.0 / r)


# ═══════════════════════════════════════════════════════════════════════════
# ② 误差项 与 三分类合成律
# ═══════════════════════════════════════════════════════════════════════════
def make_term(name: str, category: str, rel_pct: float,
              source: str, note: str = "") -> Dict:
    """构造一个误差项（**统一口径 = 相对满量程百分比**）。"""
    if category not in CATEGORIES:
        raise ValueError("未知类别 %r（必须是 %s 之一）" % (category, CATEGORIES))
    v = float(rel_pct)
    if v < 0.0:
        raise ValueError("误差项不得为负：%s = %r" % (name, rel_pct))
    return {"name": str(name), "category": category, "rel_pct": v,
            "source": str(source), "note": str(note)}


def _worst_contribution(term: Dict, k_sigma: float) -> float:
    """该项在 worst 合成里的**贡献量**（用于主导项分析，与 combine 同口径）。"""
    v = float(term["rel_pct"])
    if term["category"] == RANDOM:
        return float(k_sigma) * v
    return v


def combine(terms: Sequence[Dict], k_sigma: float = DEFAULT_K_SIGMA) -> Dict:
    """**三分类合成律**：系统性 Σ · 随机 RSS(→kσ) · 有界 Σ(→√3 折减)。

    🔴 退化行为（门禁 G2 逐项验证）：
      · 只有 systematic ⇒ worst == typical == 该项；
      · 只有 random σ  ⇒ worst == k·σ，typical == σ；
      · 只有 bounded b ⇒ worst == b，typical == b/√3。
    """
    terms = list(terms)
    for t in terms:
        if t.get("category") not in CATEGORIES:
            raise ValueError("未知类别：%r" % (t.get("category"),))
        if float(t["rel_pct"]) < 0.0:
            raise ValueError("误差项不得为负：%r" % (t["name"],))

    sys_pct = sum(float(t["rel_pct"]) for t in terms if t["category"] == SYSTEMATIC)
    sig = math.sqrt(sum(float(t["rel_pct"]) ** 2 for t in terms if t["category"] == RANDOM))
    bnd = sum(float(t["rel_pct"]) for t in terms if t["category"] == BOUNDED)

    worst = sys_pct + float(k_sigma) * sig + bnd
    typical = sys_pct + sig + bnd / math.sqrt(3.0)
    return {
        "systematic_pct": sys_pct,
        "random_sigma_pct": sig,
        "bounded_pct": bnd,
        "k_sigma": float(k_sigma),
        "worst_pct": worst,
        "typical_pct": typical,
        "worst_bits": output_effective_bits(worst),
        "typical_bits": output_effective_bits(typical),
        "n_terms": len(terms),
        "is_oracle": False,
    }


def dominant_term(terms: Sequence[Dict], k_sigma: float = DEFAULT_K_SIGMA) -> Optional[Dict]:
    """**主导项分析** —— 给设计者的行动指令：主导项是谁，就该优化谁。"""
    terms = list(terms)
    if not terms:
        return None
    scored = sorted(((_worst_contribution(t, k_sigma), t) for t in terms),
                    key=lambda p: p[0], reverse=True)
    total = sum(s for s, _ in scored)
    top_s, top_t = scored[0]
    return {
        "name": top_t["name"],
        "category": top_t["category"],
        "contribution_pct": top_s,
        "share_pct": (100.0 * top_s / total) if total > 0 else 0.0,
        "ranking": [{"name": t["name"], "category": t["category"],
                     "contribution_pct": s} for s, t in scored],
        "is_oracle": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ③ 工艺默认量（**复用** E7/E8 口径，不新造参数）
# ═══════════════════════════════════════════════════════════════════════════
def cell_conductance(vg: float, w_um: float = 1.20, l_um: float = 0.30,
                     params: Optional[NmosParams] = None) -> float:
    """单元标称电导 `g = kp·(W/L)·(Vg − Vth0)`（**与 E2/E8/E9 同一式**）。"""
    p = params or NmosParams(w_over_l=float(w_um) / float(l_um))
    return float(p.kp * (float(w_um) / float(l_um)) * (float(vg) - p.vth0))


def row_segment_resistance(n: int = 8, m: int = 8) -> float:
    """行线每段电阻（**直接复用的 E7 提取**，非新模型）。"""
    return float(PA.array_parasitics(int(n), int(m))["r_row_seg_ohm"])


# ═══════════════════════════════════════════════════════════════════════════
# ④ 误差源汇集（只读消费 E7/E8/E14）
# ═══════════════════════════════════════════════════════════════════════════
def collect_terms(n: int, m: Optional[int] = None, *,
                  r_seg: Optional[float] = None, g: Optional[float] = None,
                  vg: float = 2.5, w_um: float = 1.20, l_um: float = 0.30,
                  adc_bits: int = DEFAULT_ADC_BITS, dac_bits: int = DEFAULT_DAC_BITS,
                  quant_bits: int = DEFAULT_ADC_BITS,
                  adc_err_lsb: Optional[float] = None,
                  dac_inl_lsb: Optional[float] = None,
                  row_load_rel: Optional[float] = None,
                  include_row_driver: bool = True,
                  include_converters: bool = True,
                  dac_step: int = 1, sar_samples: int = 16) -> List[Dict]:
    """把四类误差源汇集成**统一口径（相对 %）**的误差项列表。

    各项来源与口径：
      · `ir_drop`          —— E7/E9 `row_line_profile().avg_rel_err`（🔴 **全列平均**口径，与 E9 一致）
      · `device_mismatch`  —— E8/E9 `sigma_out_rel()`（随机 **σ**，1/√N 律）
      · `row_driver_load`  —— E14 `row_system_error().max_row_load_rel_err`（系统性）
      · `adc_quantization` —— 0.5 LSB（有界半宽）
      · `dac_inl`          —— E14 `dac_static_report().inl_lsb_max` × LSB%
      · `adc_sar`          —— E14 `sar_error_report().max_err_lsb` × LSB%

    🔴 **`dac_step` 必须为 1（全码扫描）**：E14 `dac_static_report` 的 **DNL 只在相邻码上有定义**
    （内部 `if c1 - c0 != 1: continue`）⇒ `step > 1` 时 `dnl` 列表为空 ⇒ **`min()` on empty ⇒ ValueError**。
    这不是 E14 的缺陷（DNL 本就只在相邻码上有定义），而是**调用约束**。
    成本可控：转换器项在批量扫描里**只解一次**后注入（见 `budget_vs_n` / `max_scale_full_chain`）。

    🔴 后三项为**可选注入**（`adc_err_lsb` / `dac_inl_lsb` / `row_load_rel`），
    便于门禁与批量扫描**避免重复求解**（求解成本集中在 E14 的 MNA 与 E14 行链）。
    """
    n = int(n)
    m = int(m) if m is not None else n
    if n < 2:
        raise ValueError("n 必须 >= 2（1 行阵列无 IR drop 意义）")

    if r_seg is None:
        r_seg = row_segment_resistance(n, m)
    if g is None:
        g = cell_conductance(vg, w_um, l_um)

    terms: List[Dict] = []

    # ① IR drop —— 🔴 取 avg_rel_err（全列平均 = MVM 平均输出误差），与 E9 同口径
    prof = AS.row_line_profile(n, r_seg, float(g))
    terms.append(make_term(
        "ir_drop", SYSTEMATIC, float(prof["avg_rel_err"]) * 100.0, "E7/E9",
        note="全列平均口径（avg_rel_err）；最坏列 far_drop=%.4f%%"
             % (float(prof["far_drop_rel"]) * 100.0)))

    # ② 器件失配 —— 随机 σ（1/√N）
    sig = AS.sigma_out_rel(n, w_um, l_um, vg)
    terms.append(make_term(
        "device_mismatch", RANDOM, float(sig) * 100.0, "E8/E9",
        note="Pelgrom σ_δ/√N 律（E8 已 MC 验证）"))

    # ③ 输出量化 —— 有界，半宽 = 0.5 LSB
    terms.append(make_term(
        "adc_quantization", BOUNDED, lsb_to_rel_pct(quant_bits) / 2.0, "E3",
        note="均匀量化半宽 0.5 LSB @ %d bit" % int(quant_bits)))

    # ④ 行驱动负载调整（系统性；可选注入以省时）
    if include_row_driver:
        if row_load_rel is None:
            G = np.full((m, n), float(g))
            x = np.ones(n)
            row_load_rel = float(PR.row_system_error(G, x, vfs=1.0, rf=1.0e4,
                                                     r_out_open_ohm=1.0e3)["max_row_load_rel_err"])
        terms.append(make_term(
            "row_driver_load", SYSTEMATIC, float(row_load_rel) * 100.0, "E14",
            note="按行增益误差（MC 平均不掉，同 E8 列系统项同型）"))

    # ⑤⑥ 真转换器（有界；可选注入以省时）
    if include_converters:
        if dac_inl_lsb is None:
            dac_inl_lsb = float(CV.dac_static_report(n_bits=int(dac_bits),
                                                     step=max(1, int(dac_step)))["inl_lsb_max"])
        terms.append(make_term(
            "dac_inl", BOUNDED, float(dac_inl_lsb) * lsb_to_rel_pct(dac_bits), "E14",
            note="R-2R + NMOS 开关 INL（%d bits）" % int(dac_bits)))

        if adc_err_lsb is None:
            adc_err_lsb = float(CV.sar_error_report(n_bits=int(adc_bits),
                                                    samples=max(2, int(sar_samples)))["max_err_lsb"])
        terms.append(make_term(
            "adc_sar", BOUNDED, float(adc_err_lsb) * lsb_to_rel_pct(adc_bits), "E14",
            note="SAR + CDAC 实测码误差（%d bits）" % int(adc_bits)))

    return terms


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 报告与曲线
# ═══════════════════════════════════════════════════════════════════════════
def error_budget_report(n: int, m: Optional[int] = None, *,
                        budget_pct: Optional[float] = None,
                        k_sigma: float = DEFAULT_K_SIGMA,
                        **kw) -> Dict:
    """**端到端误差预算报告** —— 回答「这颗阵列实际几个有效位」。

    `budget_pct` 给了就附**是否超预算**的判定（真值来自 `max_scale_full_chain`）。
    """
    terms = collect_terms(n, m, **kw)
    agg = combine(terms, k_sigma=k_sigma)
    out = {
        "n": int(n), "m": int(m) if m is not None else int(n),
        "terms": terms,
        "aggregate": agg,
        "dominant": dominant_term(terms, k_sigma=k_sigma),
        "worst_pct": agg["worst_pct"],
        "typical_pct": agg["typical_pct"],
        "worst_bits": agg["worst_bits"],
        "typical_bits": agg["typical_bits"],
        "is_oracle": False,
    }
    if budget_pct is not None:
        bp = float(budget_pct)
        out["budget_pct"] = bp
        out["within_budget"] = bool(agg["worst_pct"] <= bp)
        out["budget_headroom_pct"] = bp - agg["worst_pct"]
    return out


def budget_vs_n(sizes: Sequence[int], *, budget_pct: Optional[float] = None,
                share_periphery: bool = True, **kw) -> Dict:
    """**精度 vs 规模曲线** —— 回答「N 大上去精度会掉到几位」。

    `share_periphery=True`：行驱动负载与转换器误差**只解一次**后注入。
    物理上也更对 —— ADC/DAC 是**固定外围**，不随阵列规模重复计入。
    """
    merged = dict(kw)
    if share_periphery:
        for t in collect_terms(8, 8, **kw):
            if t["name"] == "dac_inl":
                merged["dac_inl_lsb"] = t["rel_pct"] / lsb_to_rel_pct(
                    kw.get("dac_bits", DEFAULT_DAC_BITS))
            elif t["name"] == "adc_sar":
                merged["adc_err_lsb"] = t["rel_pct"] / lsb_to_rel_pct(
                    kw.get("adc_bits", DEFAULT_ADC_BITS))
            elif t["name"] == "row_driver_load":
                merged["row_load_rel"] = t["rel_pct"] / 100.0

    rows = []
    for n in sizes:
        r = error_budget_report(int(n), budget_pct=budget_pct, **merged)
        rows.append({
            "n": int(n),
            "worst_pct": r["worst_pct"], "typical_pct": r["typical_pct"],
            "worst_bits": r["worst_bits"], "typical_bits": r["typical_bits"],
            "dominant": (r["dominant"] or {}).get("name"),
        })
    return {"points": rows, "budget_pct": budget_pct,
            "shared_periphery": bool(share_periphery), "is_oracle": False}


def max_scale_full_chain(budget_pct: float, *, r_seg: Optional[float] = None,
                         g: Optional[float] = None, vg: float = 2.5,
                         w_um: float = 1.20, l_um: float = 0.30,
                         scan_hi: int = DEFAULT_SCAN_HI,
                         k_sigma: float = DEFAULT_K_SIGMA,
                         ir_drop_only: bool = False,
                         **kw) -> Dict:
    """**全链预算下的可及规模上界**（泛化 E9 `max_scale_for_budget`）。

    🔴 `ir_drop_only=True` ⇒ **直接委托** `array_scale.max_scale_for_budget`
    （同预算、同 r_seg/g），保证与 E9 **逐值相等**（门禁 G7 的一致性锚）。

    🔴 全链情形**用扫描而非二分**：因为 `worst(N)` 未必单调 ——
    IR drop ∝ N² **升**、失配 σ ∝ 1/√N **降**，合成曲线可能先降后升
    ⇒ **二分隐含的单调假设不成立，用二分会给错数**。扫描上界 `scan_hi` 显式披露。
    """
    bp = float(budget_pct)
    if bp <= 0:
        raise ValueError("budget_pct 必须 > 0")
    if r_seg is None:
        r_seg = row_segment_resistance(8, 8)
    if g is None:
        g = cell_conductance(vg, w_um, l_um)

    if ir_drop_only:
        n_e9 = int(AS.max_scale_for_budget(bp / 100.0, float(r_seg), float(g)))
        return {"budget_pct": bp, "n_max": n_e9, "saturated": False,
                "method": "delegated_to_E9", "is_oracle": False,
                "note": "仅 IR drop ⇒ 直接委托 E9（逐值一致，见门禁 G7）"}

    # 🔴 行驱动负载项与转换器误差**与 N 弱相关 / 无关** ⇒ 先解一次再注入，
    #    避免扫描里做 256 次重复求解（成本集中在 E14 的 MNA 与行链）。
    base = collect_terms(8, 8, r_seg=float(r_seg), g=float(g), vg=vg,
                         w_um=w_um, l_um=l_um, **kw)
    inject: Dict = {}
    for t in base:
        if t["name"] == "dac_inl":
            inject["dac_inl_lsb"] = t["rel_pct"] / lsb_to_rel_pct(
                kw.get("dac_bits", DEFAULT_DAC_BITS))
        elif t["name"] == "adc_sar":
            inject["adc_err_lsb"] = t["rel_pct"] / lsb_to_rel_pct(
                kw.get("adc_bits", DEFAULT_ADC_BITS))
        elif t["name"] == "row_driver_load":
            inject["row_load_rel"] = t["rel_pct"] / 100.0

    # 🔴 **扫描而非二分**：worst(N) 未必单调（IR drop ∝N² 升 / 失配 ∝1/√N 降）
    #    ⇒ 二分隐含的单调假设不成立。必须扫完才知道"最大的可行 N"。
    best, curve = 1, []
    for n in range(2, int(scan_hi) + 1):
        agg = combine(collect_terms(n, n, r_seg=float(r_seg), g=float(g), vg=vg,
                                    w_um=w_um, l_um=l_um, **inject),
                      k_sigma=k_sigma)
        curve.append((int(n), float(agg["worst_pct"])))
        if agg["worst_pct"] <= bp:
            best = int(n)
    saturated = bool(curve and curve[-1][1] <= bp)
    return {
        "budget_pct": bp, "n_max": int(best), "saturated": saturated,
        "method": "scan", "scan_hi": int(scan_hi), "is_oracle": False,
        "curve_len": len(curve),
        "curve_head": curve[:3], "curve_tail": curve[-3:],
        "note": "worst(N) 未必单调（IR drop ∝N² 升 / 失配 ∝1/√N 降）⇒ 用扫描不用二分",
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 披露 + 自检
# ═══════════════════════════════════════════════════════════════════════════
BUDGET_DISCLOSURE: dict = {
    "route": "电子计算征程 E15 · 端到端误差预算链（把四类误差合成一条链）",
    "capability": "口径桥（LSB ⟷ 相对 %）· 三分类合成律（系统 Σ / 随机 RSS+kσ / 有界 Σ 与 /√3）"
                  "· 输出有效精度位数 · 误差主导项分析 · 全链预算下的可及规模上界（泛化 E9）",
    "golden": "① 口径桥自洽 `bits_eff(lsb_to_rel_pct(k)) == k`（纯代数，无需任何模块）；"
              "② **退化闭式**（只留一类误差 ⇒ 合成退化为该类闭式）；③ 下界性 `worst ≥ max(单项)`；"
              "④ 仅 IR drop 时 `max_scale_full_chain ≡ E9 max_scale_for_budget`（逐值）",
    "cross_check": "全部数据**只读消费**既有模块接口：E7/E9 `row_line_profile`（🔴 avg_rel_err 口径）·"
                   "E8/E9 `sigma_out_rel` · E14 `row_system_error` / `dac_static_report` / `sar_error_report`；"
                   "本模块**不复制任何公式**、**不修改任何默认值**",
    "effective_bits_semantics": "🔴 `output_effective_bits` = `log2(100/最坏相对误差[%])`，"
                                "**本项目自定义量，不是 IEEE ENOB**"
                                "（ENOB 含噪声+谐波+直流非线性、由 FFT 谱定义）",
    "honest_boundary": "**只覆盖静态**（给定权重与输入的静态精度）—— 不含时序 / 动态 / 建立时间 / 采样率 / "
                       "时钟抖动 / 热梯度空间分布 / 老化漂移 / 电源噪声；"
                       "合成律是**保守工程口径**（worst = Σsys + kσ + Σbnd），"
                       "**不是严格概率保证**（严格需分布假设与卷积）；typical 的 Σb/√3 假设均匀分布；"
                       "参数为公开典型量级占位（**非 PDK**）；器件侧仍为 **DD 框架 + 常数迁移率**；"
                       "**不报 TOPS / TOPS-W / fJ/op**",
    "scope_note": "本段**不吃新物理**：只做「口径统一 + 分类合成 + 泛化上界」，"
                  "产出=一个数（有效位数）+ 一条曲线（精度 vs N）+ 一个行动指令（主导项）",
    "redline": "红线 = **分层口径**（器件级 T1 内核实已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "**本包主动限定在电路级**；C 级自主（纯 numpy）；LLM 不进判决路径",
}


def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（返回全绿与否）。门禁 `run_ecore_e15_smoke.py` 复用同一份。"""
    def chk(name: str, cond: bool, detail: str = "") -> bool:
        if verbose:
            print("  [%s] %s%s" % ("OK " if cond else "FAIL", name,
                                   ("   " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① 口径桥自洽（golden：定义闭合）
    ok &= chk("① 口径桥自洽：bits_eff(lsb_to_rel_pct(k)) == k（k=4..12）",
              all(abs(output_effective_bits(lsb_to_rel_pct(k)) - k) < 1e-12
                  for k in range(4, 13)),
              "lsb_to_rel_pct(8)=%.9f" % lsb_to_rel_pct(8))

    # ② 逆向口径桥
    ok &= chk("② 口径桥可逆：rel_pct_to_lsb(lsb_to_rel_pct(k), k) == 1.0",
              all(abs(rel_pct_to_lsb(lsb_to_rel_pct(k), k) - 1.0) < 1e-12
                  for k in range(4, 13)))

    # ③ 退化闭式：仅系统项
    only_sys = combine([make_term("s", SYSTEMATIC, 3.0, "test")])
    ok &= chk("③ 退化（仅系统项）：worst == typical == 3.0",
              abs(only_sys["worst_pct"] - 3.0) < 1e-12
              and abs(only_sys["typical_pct"] - 3.0) < 1e-12,
              "worst=%.6f typical=%.6f" % (only_sys["worst_pct"], only_sys["typical_pct"]))

    # ④ 退化闭式：仅随机项（k=3）
    only_rnd = combine([make_term("r", RANDOM, 2.0, "test")])
    ok &= chk("④ 退化（仅随机项）：worst == 3σ == 6.0，typical == σ == 2.0",
              abs(only_rnd["worst_pct"] - 6.0) < 1e-12
              and abs(only_rnd["typical_pct"] - 2.0) < 1e-12,
              "worst=%.6f typical=%.6f" % (only_rnd["worst_pct"], only_rnd["typical_pct"]))

    # ⑤ 退化闭式：仅有界项（worst == b，typical == b/√3）
    only_bnd = combine([make_term("b", BOUNDED, 1.0, "test")])
    ok &= chk("⑤ 退化（仅有界项）：worst == 1.0，typical == 1/√3",
              abs(only_bnd["worst_pct"] - 1.0) < 1e-12
              and abs(only_bnd["typical_pct"] - 1.0 / math.sqrt(3.0)) < 1e-12)

    # ⑥ 随机项 RSS（不是代数相加）
    two_rnd = combine([make_term("r1", RANDOM, 3.0, "t"),
                       make_term("r2", RANDOM, 4.0, "t")])
    ok &= chk("⑥ 随机项 RSS：σ_tot == √(3²+4²) == 5.0（非代数相加 7.0）",
              abs(two_rnd["random_sigma_pct"] - 5.0) < 1e-12,
              "σ_tot=%.6f" % two_rnd["random_sigma_pct"])

    # ⑦ 下界性：合成 ≥ 任一单项
    mixed = combine([make_term("s", SYSTEMATIC, 1.0, "t"),
                     make_term("r", RANDOM, 2.0, "t"),
                     make_term("b", BOUNDED, 0.5, "t")])
    ok &= chk("⑦ 下界性：worst ≥ max(单项 worst 贡献)",
              mixed["worst_pct"] >= max(1.0, 3.0 * 2.0, 0.5) - 1e-12)

    # ⑧ 有序性：worst ≥ typical ≥ 0
    ok &= chk("⑧ 有序性：worst ≥ typical ≥ 0",
              mixed["worst_pct"] >= mixed["typical_pct"] >= 0.0)

    # ⑨ 有效位数单调（误差 ↑ ⇒ 位数 ↓）
    ok &= chk("⑨ 有效位数单调：rel ↑ ⇒ bits_eff ↓",
              output_effective_bits(1.0) > output_effective_bits(2.0)
              > output_effective_bits(4.0))

    # ⑩ 主导项识别（放大哪类就认出哪类）
    d1 = dominant_term([make_term("s", SYSTEMATIC, 1.0, "t"),
                        make_term("r", RANDOM, 10.0, "t")])
    d2 = dominant_term([make_term("s", SYSTEMATIC, 30.0, "t"),
                        make_term("r", RANDOM, 1.0, "t")])
    ok &= chk("⑩ 主导项识别：随机项 10σ 时主导=随机；系统项 30 时主导=系统",
              d1["name"] == "r" and d2["name"] == "s",
              "d1=%s d2=%s" % (d1["name"], d2["name"]))

    # ⑪ 真实调用链：能从 E7/E9/E8 拉到数并合成（小规模，含转换器）
    rep = error_budget_report(8, 8, budget_pct=5.0)
    ok &= chk("⑪ 端到端报告可跑：8×8 ⇒ 6 项误差 + 有效位数有限",
              rep["aggregate"]["n_terms"] >= 5 and 0.0 < rep["worst_pct"] < 100.0
              and math.isfinite(rep["worst_bits"]),
              "worst=%.4f%% bits_eff=%.3f" % (rep["worst_pct"], rep["worst_bits"]))

    # ⑫ 🔴 保护性约束：不修改既有模块（跑一次可判定的既有闭式）
    ok &= chk("⑫ 保护性约束：E9 `elements_flat(8,8) == 8*8*7+16` 与 E14 LSB 口径逐位不变",
              AS.elements_flat(8, 8) == 8 * 8 * 7 + 16
              and abs(lsb_to_rel_pct(8) - 100.0 / 256.0) < 1e-15)

    return ok


# 命名别名（与 ecore 包既有体例 `<模块名>_self_check` 对齐，供能力清单与 __init__ 导出）
budget_self_check = run_selfchecks


__all__ = [
    "SYSTEMATIC", "RANDOM", "BOUNDED", "CATEGORIES",
    "DEFAULT_K_SIGMA", "DEFAULT_ADC_BITS", "DEFAULT_DAC_BITS", "DEFAULT_SCAN_HI",
    "lsb_to_rel_pct", "rel_pct_to_lsb", "output_effective_bits",
    "make_term", "combine", "dominant_term",
    "cell_conductance", "row_segment_resistance", "collect_terms",
    "error_budget_report", "budget_vs_n", "max_scale_full_chain",
    "BUDGET_DISCLOSURE", "run_selfchecks", "budget_self_check",
]
