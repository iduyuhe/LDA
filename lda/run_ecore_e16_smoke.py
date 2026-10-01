# -*- coding: utf-8 -*-
"""E16 权重编程通路门禁（D-183 · v0.9.163）。

═══════════════════════════════════════════════════════════════════════════
判什么（分节）
═══════════════════════════════════════════════════════════════════════════
A 模块自检（`weight_prog.weight_prog_self_check` **14 项**）
B 关键事实 name-first：五个闭式 golden（G-1 电平 · G-2 轨迹 · G-3 脉冲数 ·
  G-4 **写入噪声地板** · G-5 漂移/重校准）· 矩阵感知 σ 严格式 · 良率 · 差分对 ·
  🔴 **E15 默认逐位不变** · 含编程新锚 + 电平敏感性 + 上界收缩 · 端到端 ·
  保护性约束 · 诚实披露
C 反向可证伪：**6 条突变探针**（电平系数 / 噪声地板公式 / 去掉 1/√N /
  良率丢指数 / **默认改 ON（静默改已发布数字）** / 电平界用 min(g)）⇒ 均必红 + **还原重跑**
K 自入 CI core（防静默漏接 · 血案 #28）

═══════════════════════════════════════════════════════════════════════════
🔴 本门禁的核心价值
═══════════════════════════════════════════════════════════════════════════
1. **G-4 写入噪声地板**是本段的物理内核：`σ_∞ = σ_p/√(α(2−α))` 由**无穷级数**给出，
   必须由**独立 MC** 核对（B5），不能自证。且**零噪声时 MC 必须逐步等于 G-2 闭式**（B6）——
   这是"两条独立路径"而非"一条路径自说自话"。
2. **保护性约束**（B12）：`budget.collect_terms` 新增的 `include_programming` **默认 False**
   ⇒ E15 已发布的 8×8（4.06012% / 4.6223 位）与 5% 上界（N≤12）**逐位不变**。
   这是与 `NmosParams` / `mna.vcvs` 同一族的纪律：**会静默改掉已发布数字的"顺手优化"必须被门禁拦住**。
   探针 C5 专门模拟"有人把默认改成 ON"。
3. **口径必须与被测机制同口径**（本段新血案）：`programming_error_matrix` 曾只存**绝对值**误差，
   而 `std(|Z|) = σ·√(1−2/π) = 0.603σ` ⇒ 用绝对值序列估 σ 会**系统性偏低 40%**。
   正解 = 同时保留**带符号**版本（`rel_err_col0`）供 σ 对拍。
4. **E8/E9 的 `σ/√N` 是理想化**（隐含各单元电导相同）。含电导离散时严格式 =
   `σ·√(Σ(gx)²)/|Σgx|`，两者之比即**条件数 ≥ 1** ⇒ B9 用"等电导时**精确退化**"作为可证伪点。

🔴 两条诚实纪律（写进判据 B16）：
  · 参数（α / σ_p / tol / ν / p_stuck）为**公开典型量级占位 · 非 PDK**
    ⇒ 漂移结论（5% 预算 ⇒ t_max ≈ 2.79 s）**条件于 ν**，不是普适断言。
  · **共模漂移可被单次全局增益校准消除 ⇒ 不进预算**；进预算的只有 ν 的**单元间离散**。
"""

from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np                                # noqa: E402

from lda_l2.ecore import array_scale as AS        # noqa: E402
from lda_l2.ecore import budget as B              # noqa: E402
from lda_l2.ecore import weight_prog as WP        # noqa: E402

_results: list = []
PR = WP.WEIGHT_PROG_PROCESS


def check(name: str, cond: bool, detail: str = "") -> bool:
    _results.append((name, bool(cond), detail))
    return bool(cond)


# ── 复用的绿色判据（突变探针也调同一份 —— 保证「打的判据」就是「守的判据」）──
def _level_ok() -> bool:
    """G-1 电平量化闭式 + 穷举紧界。"""
    lv = WP.program_levels(6)
    grid = np.arange(lv) / float(lv - 1)
    half = 0.5 / float(lv - 1)
    return (WP.program_levels(6) == 64
            and abs(WP.level_lsb_rel(6) - 1.0 / 63.0) < 1e-18
            and abs(WP.level_error_bound_rel(6) - 1.0 / 126.0) < 1e-18
            and float(np.max(np.abs(WP.quantize_to_levels(grid, 6) - grid))) < 1e-15
            and abs(float(np.max(np.abs(WP.quantize_to_levels(grid + half, 6)
                                                  - (grid + half)))) - WP.level_lsb_rel(6) / 2.0) < 1e-15)


def _closed_ok() -> bool:
    """G-2 轨迹 + G-3 脉冲数（含紧性）。"""
    tr = WP.write_verify_closed(1.0, 0.30, 12)
    k = WP.iter_to_tolerance(1.0, 0.01, 0.30)
    return (all(abs(tr["errors"][j] - 0.7 ** j) < 1e-15 for j in range(13))
            and k == 13 and 0.7 ** k <= 0.01 < 0.7 ** (k - 1))


def _floor_ok() -> bool:
    """G-4 噪声地板 ⟷ MC。"""
    closed = WP.noise_floor_sigma(PR["sigma_pulse_rel"], PR["alpha_pulse"])
    mc = WP.write_verify_stochastic(sigma_pulse_rel=PR["sigma_pulse_rel"],
                                    alpha=PR["alpha_pulse"], max_pulses=64,
                                    seed=0, trials=4000)
    return abs(mc["sigma_residual"] - closed) / closed < 0.03


def _zero_noise_ok() -> bool:
    """零噪声 MC ⟷ G-2 闭式（第二条独立路径）。"""
    mcz = WP.write_verify_stochastic(sigma_pulse_rel=0.0, alpha=0.30, max_pulses=10,
                                     tol_rel=1e-12, seed=1, trials=200)
    return abs(mcz["mean_relative_error"] - 0.7 ** 10) < 1e-9


def _sqrt_n_ok() -> bool:
    """1/√N 律 + 矩阵感知严格式（等电导 ⇒ 精确退化）。"""
    s8 = WP.residual_sigma_out(0.007, 8)
    s32 = WP.residual_sigma_out(0.007, 32)
    geq = np.full(8, 3.0e-4)
    gdis = np.linspace(1.0e-4, 5.0e-4, 8)
    f_eq = WP.output_sigma_matrix_aware(geq, np.ones(8), 0.007)
    f_dis = WP.output_sigma_matrix_aware(gdis, np.ones(8), 0.007)
    return abs(s8 / s32 - 2.0) < 1e-12 and abs(f_eq - s8) < 1e-15 and f_dis > s8


def _drift_ok() -> bool:
    """G-5 漂移闭式 + 重校准间隔闭式（代回）+ 单调。"""
    tm = WP.recal_interval(1.0, 0.05, 0.05)
    return (abs(WP.drift_factor(1000.0, 1.0, 0.05) - 1000.0 ** (-0.05)) < 1e-15
            and abs(WP.drift_factor(tm, 1.0, 0.05) - 0.95) < 1e-12
            and WP.drift_factor(100.0, 1.0, 0.05) > WP.drift_factor(1000.0, 1.0, 0.05))


def _yield_ok() -> bool:
    """良率闭式 ⟷ 直接枚举（p>0 ⇒ 必须用非零 p，否则 (1−p) 与 (1−p)^N 恒等）。"""
    p = 0.01
    rng = np.random.default_rng(7)
    big = float(np.mean(np.all(rng.random((20000, 8)) >= p, axis=1)))
    return (abs(WP.yield_fraction(8, p) - (1 - p) ** 8) < 1e-15
            and abs(big - (1 - p) ** 8) < 0.02)


def _diffpair_ok() -> bool:
    ds = [WP.differential_pair(w, 1e-4, w_max=1.0) for w in (-1.0, -0.3, 0.0, 0.7, 1.0)]
    return all(d["exact"] and d["g_min_positive"] for d in ds)


def _e15_default_ok() -> bool:
    """🔴 保护性约束：E15 默认口径的已发布数字**逐位不变**。"""
    r = B.error_budget_report(8, 8)
    return (abs(r["worst_pct"] - 4.06012) < 0.01
            and abs(r["worst_bits"] - 4.6223) < 0.01
            and r["dominant"]["name"] == "device_mismatch"
            and B.max_scale_full_chain(5.0)["n_max"] == 12)


def _with_prog_ok() -> bool:
    """🔴 开启编程后的新锚 + 电平敏感性单调 + 上界收缩。"""
    W8 = WP.canonical_weights(8, 8)
    r_a = B.error_budget_report(8, 8, include_programming=True,
                               prog_terms=WP.programming_budget_terms(8, 8, w=W8, include_level=False))
    r_m = B.error_budget_report(8, 8, include_programming=True,
                               prog_terms=WP.programming_budget_terms(8, 8, w=W8,
                                                                      include_level=True, bits=6))
    lv = [WP.programming_budget_terms(8, 8, w=W8, include_level=True, bits=b)  # 4→12 bit 单调降
          for b in (4, 6, 8, 10, 12)]
    lev = [next(t["rel_pct"] for t in ts if t["name"] == "weight_prog_level") for ts in lv]
    n_an = B.max_scale_full_chain(5.0, prog_terms_fn=lambda n: WP.programming_budget_terms(
        n, n, include_level=False))["n_max"]
    n_mc = B.max_scale_full_chain(5.0, prog_terms_fn=lambda n: WP.programming_budget_terms(
        n, n, include_level=True, bits=6))["n_max"]
    return (abs(r_a["worst_pct"] - 4.20838) < 0.01 and abs(r_a["worst_bits"] - 4.5706) < 0.01
            and abs(r_m["worst_pct"] - 5.27562) < 0.01 and abs(r_m["worst_bits"] - 4.2445) < 0.01
            and all(lev[i] > lev[i + 1] for i in range(len(lev) - 1))
            and n_an == 11 and n_mc < n_an)


def _e2e_ok() -> bool:
    """🔴 端到端：实测 σ（**带符号**序列）⟷ 矩阵感知严格式 · max ≤ 1.5× 理想化界。"""
    W = WP.canonical_weights(8, 6)
    x = np.ones(8)
    e2e = WP.programming_error_matrix(W, x, trials=600, seed=100,
                                      include_level=True, bits=6, stuck_p=0.0)
    pa = WP.program_array(W, include_level=True, bits=6, stuck_p=0.0, seed=0)
    strict = WP.output_sigma_matrix_aware(pa["g_ideal"][:, 0], x, pa["sigma_cell_rel"])
    emp = float(np.std(e2e["rel_err_col0"], ddof=1))
    bd = B.combine(WP.programming_budget_terms(8, 6, w=W, include_level=True, bits=6))["worst_pct"]
    return abs(emp - strict) / strict < 0.10 and e2e["rel_err_max"] * 100.0 <= 1.5 * bd


def _protection_ok() -> bool:
    """保护性约束：E7/E8/E9/E14 既有默认值与闭式逐位不变（同 E15 G8）。"""
    return (AS.elements_flat(8, 8) == 8 * 8 * 7 + 16
            and AS.elements_hierarchical(8, 8) == 7 + 1 + 16
            and abs(B.cell_conductance(2.5) - (120e-6 * 4.0 * (2.5 - 0.4))) < 1e-15
            and abs(B.lsb_to_rel_pct(8) - 100.0 / 256.0) < 1e-15)


def _disclosure_ok() -> bool:
    """诚实披露 + 分类正确（RANDOM/BOUNDED + 共模漂移不进预算）。"""
    d = WP.WEIGHT_PROG_DISCLOSURE
    terms = WP.programming_budget_terms(8, 8, w=WP.canonical_weights(8, 8))
    names = {t["name"]: t["category"] for t in terms}
    return ("非 PDK" in d["honest_boundary"]
            and "TOPS" in d["honest_boundary"]
            and "参数" in d["honest_boundary"]
            and "共模" in d["drift_semantics"]
            and "不进预算" in d["drift_semantics"]
            and names.get("weight_prog_residual") == B.RANDOM
            and names.get("weight_prog_level") == B.BOUNDED)


# ══════════════════════════════════════════════════════════════════════════
def main() -> int:
    print("=" * 74)
    print("E16 权重编程通路门禁（D-183 · 写-校验 · 噪声地板 · 接 E15 预算）")
    print("=" * 74)

    # ── A 模块自检 ──────────────────────────────────────────────────────
    ok_a = WP.weight_prog_self_check(verbose=False)
    check("A1 模块自检 14/14 PASS（G-1 电平闭式/穷举 · G-2 轨迹 · G-3 脉冲数 · "
          "G-4 地板⟷MC · 零噪声 MC⟷闭式 · 1√N · G-5 漂移/重校准 · 良率⟷枚举 · "
          "差分对 · 编程复现 · E15 项分类 · 保护性约束 · 矩阵感知 σ 退化）", ok_a)

    # ── B 关键事实 ─────────────────────────────────────────────────────
    check("B1 🔴 G-1 电平量化闭式：levels(6)=64 · lsb=1/63 · 界=1/126",
          abs(WP.level_lsb_rel(6) - 1.0 / 63.0) < 1e-18
          and abs(WP.level_error_bound_rel(6) - 1.0 / 126.0) < 1e-18,
          "lsb_rel(6)=%.10f" % WP.level_lsb_rel(6))
    check("B2 🔴 量化穷举：64 电平自映射 · 上界**恰为** lsb/2（紧界，非松弛）", _level_r_ok())
    check("B3 🔴 G-2 确定性轨迹 ⟷ 闭式 e0(1−α)^k（逐点机精度）", _closed_ok(),
          "e_12=%.6f" % WP.write_verify_closed(1.0, 0.30, 12)["errors"][12])
    check("B4 🔴 G-3 脉冲数 ⟷ 闭式 ceil(ln(tol/e0)/ln(1−α))=13 · k*−1 步尚未达标（紧性）",
          WP.iter_to_tolerance(1.0, 0.01, 0.30) == 13
          and 0.7 ** 13 <= 0.01 < 0.7 ** 12)
    check("B5 🔴 G-4 写入噪声地板 σ_p/√(α(2−α)) ⟷ **独立 MC**（rel<3%）", _floor_ok(),
          "闭式=%.6f%% ⟷ MC=%.6f%%" % (WP.noise_floor_sigma(PR["sigma_pulse_rel"], PR["alpha_pulse"]) * 100,
                                   WP.write_verify_stochastic(sigma_pulse_rel=PR["sigma_pulse_rel"],
                                                              alpha=PR["alpha_pulse"], max_pulses=64,
                                                              seed=0, trials=4000)["sigma_residual"] * 100))
    check("B6 🔴 零噪声 MC 均值 ⟷ G-2 闭式（**独立于解析式的第二条路径**，rel<1e-9）",
          _zero_noise_ok())
    check("B7 🔴 输出 1/√N 律：σ_out(32) == σ_out(8)/2（精确）", _sqrt_n_ok())
    check("B8 🔴 G-5 漂移闭式 (t/t0)^(−ν) + **重校准间隔闭式** t0(1−β)^(−1/ν) 代回 ⟹ "
          "drift(t_max)==0.95（rel<1e-12）· 单调递减", _drift_ok())
    check("B9 🔴 矩阵感知 σ 严格式：**等电导 ⇒ 精确退化为 σ/√N**（条件数==1）· "
          "电导离散 ⇒ 严格式 **>** 理想式（E8/E9 的 1/√N 是理想化）", _sqrt_n_ok())
    check("B10 🔴 良率闭式 (1−p)^N ⟷ **直接枚举**（🔴 必须用 p>0：p=0 时 (1−p) 与 (1−p)^N 恒等）",
          _yield_ok())
    check("B11 差分对：g± = g_base ± s·w · w 恢复精确 · g− > 0", _diffpair_ok(),
          "w=0.7 ⟹ g+=%.4e / g−=%.4e" % (WP.differential_pair(0.7, 1e-4, w_max=1.0)["g_plus"],
                                          WP.differential_pair(0.7, 1e-4, w_max=1.0)["g_minus"]))
    check("B12 🔴🔴 **保护性约束**：默认 include_programming=False ⇒ E15 已发布数字"
          "**逐位不变**（8×8 worst 4.06012% / bits 4.6223 / 主导 device_mismatch / 5% 上界 N≤12）",
          _e15_default_ok(),
          "worst=%.5f%% bits=%.4f n_max=%s" % (B.error_budget_report(8, 8)["worst_pct"],
                                                B.error_budget_report(8, 8)["worst_bits"],
                                                B.max_scale_full_chain(5.0)["n_max"]))
    check("B13 🔴 开启编程后的新锚：模拟写入 **4.20838% / 4.5706 位** · "
          "MLC 6 位 **5.27562% / 4.2445 位**（−0.378 位）· 电平敏感性 4→12 bit **单调降** · "
          "5% 上界 **12 → 11**（模拟写入）/ **<11**（MLC 6 位）", _with_prog_ok())
    check("B14 🔴 端到端（E8 `mvm_output` · 600 trials）：实测 σ ⟷ 矩阵感知严格式 "
          "**rel<10%** · max ≤ 1.5× 理想化界（条件数 > 1 导致理想化界略低）", _e2e_ok())
    check("B15 🔴 保护性约束：E7/E8/E9/E14 既有默认值与闭式**逐位不变**（同 E15 G8）",
          _protection_ok(),
          "elements_flat(8,8)=%d · g(2.5)=%.6e" % (AS.elements_flat(8, 8), B.cell_conductance(2.5)))
    check("B16 🔴 诚实披露：非 PDK · 不报 TOPS · 漂移结论**条件于 ν** · "
          "**共模漂移可校准 ⇒ 不进预算** · 项分类正确（residual=RANDOM / level=BOUNDED）",
          _disclosure_ok())

    # ── C 反向可证伪（突变探针）────────────────────────────────────────
    print("-" * 74)
    print("C 反向可证伪（突变探针）：每条都必须能把对应判据打红")
    print("-" * 74)

    # C1 电平系数写错：1/(2^k−1) → 1/2^k
    with mock.patch.object(WP, "level_lsb_rel", lambda bits: 1.0 / float(WP.program_levels(bits))):
        c1 = not _level_ok()
    check("C1 反向：电平步长写成 1/2^k（漏 −1）⇒ B1/B2 必红", c1,
          "电平判据实测变红 = %s" % c1)

    # C2 噪声地板公式写错：σ_p/√(α(2−α)) → σ_p/α
    with mock.patch.object(WP, "noise_floor_sigma",
                           lambda sigma_pulse_rel=0.005, alpha=0.30:
                           float(sigma_pulse_rel) / float(alpha)):
        c2 = not _floor_ok()
    check("C2 反向：噪声地板写成 σ_p/α（漏 √(2−α)）⇒ B5 必红（闭式⟷MC 交叉校验被破坏）", c2,
          "地板判据实测变红 = %s" % c2)

    # C3 去掉写入残差的 1/√N 律
    with mock.patch.object(WP, "residual_sigma_out",
                           lambda s, n: abs(float(s))):
        c3 = not _sqrt_n_ok()
    check("C3 反向：去掉 1/√N 律（输出 σ 与 N 无关）⇒ B7/B9 必红", c3,
          "1√N 判据实测变红 = %s" % c3)

    # C4 良率公式写错：(1−p)^N → (1−p)
    with mock.patch.object(WP, "yield_fraction", lambda nc, p=1e-3: (1.0 - float(p))):
        c4 = not _yield_ok()
    check("C4 反向：良率写成 (1−p)（漏指数 N）⇒ B10 必红", c4,
          "良率判据实测变红 = %s（🔴 必须用 p>0，否则原式与错式恒等）" % c4)

    # C5 默认改 ON（静默改掉 E15 已发布数字）
    _real_ct = B.collect_terms

    def _forced_prog(n, m=None, **kw):
        kw["include_programming"] = True
        return _real_ct(n, m, **kw)

    with mock.patch.object(B, "collect_terms", _forced_prog):
        c5 = not _e15_default_ok()
    check("C5 反向：`include_programming` 默认**改 ON** ⇒ B12 必红"
          "（这是本门禁最重要的一条：**会静默改掉已发布数字的改动必须被拦**）", c5,
          "E15 默认判据实测变红 = %s" % c5)

    # C6 电平界用 min(g) 而非 mean(g)
    with mock.patch.object(WP, "level_bound_in_output",
                           lambda hi, lo, g_ref, bits: ((float(hi) - float(lo))
                                                        * WP.level_error_bound_rel(bits)
                                                        / float(lo) if lo > 0 else 0.0)):
        c6 = not _with_prog_ok()
    check("C6 反向：电平界改用 **min(g)**（把「绝对步长/平均电导」错写成「/最小电导」）"
          "⇒ B13 必红（电平项被放大 ~3×）", c6,
          "新锚判据实测变红 = %s" % c6)

    # 还原重跑（无残留漂移）
    check("C7 还原完整性：全部探针退出后，A1 自检 + B5/B12/B14 复跑仍全绿",
          WP.weight_prog_self_check(verbose=False) and _floor_ok()
          and _e15_default_ok() and _e2e_ok())

    # ── K 自入 CI core ────────────────────────────────────────────────
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e16_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        if not ok:
            print("FAIL | " + name + (("  :: " + detail) if detail else ""))
        elif detail:
            print("PASS | " + name + "  :: " + detail)
    print()
    print("=" * 74)
    print("E16 门禁结果：%d PASS / %d FAIL（共 %d 判据）" % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


def _level_r_ok() -> bool:
    """B2 专用（与 _level_ok 同义，便于探针分别打击）——穷举紧界。"""
    lv = WP.program_levels(6)
    grid = np.arange(lv) / float(lv - 1)
    half = 0.5 / float(lv - 1)
    return (float(np.max(np.abs(WP.quantize_to_levels(grid, 6) - grid))) < 1e-15
            and abs(float(np.max(np.abs(WP.quantize_to_levels(grid + half, 6)
                                                  - (grid + half)))) - WP.level_lsb_rel(6) / 2.0) < 1e-15)


if __name__ == "__main__":
    sys.exit(main())
