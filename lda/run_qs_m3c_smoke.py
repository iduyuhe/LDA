#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M3c（G5 量子传感 PDK 腔几何 · 腔 QED 物理链）门禁（v0.9.227）。

═══ 判什么（分节）═══
A 三链物理（**Q=ω/κ 闭式 ⇄ RK4 能量衰减反解**一致 + 粗网格残差放大 + 单调 + κ→0 护栏 ·
  **V_eff=A·8a/15 闭式 ⇄ 中点求积**一致 + 粗网格放大 + 单调 + A→0 护栏 ·
  **g=(μ/ħ)√(ħω/(εV_eff)) 闭式 ⇄ 数值场能积分**一致 + 粗网格放大 + g∝μ 线性 + μ→0 护栏）·
B 🔴 **跨源一致性**：`lda_l2.qs_m3c` 闭式 ≡ `lda_harness._batch_qs_m3c_numeric` 锚 golden **逐位**
  （防「演示模块与锚核两份实现漂移」）·
C 🔴 **判据 D 扫描**（对三锚逐锚扫候选自身离散参数：残差须**严格单调收敛**且粗端 ≫ 细端
  ⇒ 真数值残差、非代数恒等）·
D 🔴 **三锚接线复核**（B494–B496 入 BENCHMARK_DEFS · 分类 = strict_independent ·
  候选有响应（反自证桩）· 残差非零（防回落 golden）· tol 读自 DEFS 不硬编码 ·
  默认档 = 判据 D 扫描网格末端）·
E 反向探针（零 κ / 零 A / 零 μ / 零 V_eff ⇒ 抛 · 错口径 ⇒ 抛 ·
  情景单调性方向反证 · 极粗网格 ⇒ 残差 ≫ 细网格）·
F 物理整合（finesse 两式逐位 · cooperativity 约定因子 2n · Purcell FOM 量级 · 综合签核 ACCEPT）·
G 自入 CI core（防静默漏接 · **golden 分派必含三锚**（防漏登 ⇒ 假自证桩）·
  三锚必在 BENCHMARK_ORDER · `_PHYSICAL_LAW` 必含三锚）·
H 模块自检直连（`qs_m3c.selfcheck_qs_m3c` 全项 PASS）。

═══ 🔴 锚账本口径（本档**净增 3 道锚** B494–B496）═══
QS-M3c 交付**新物理量**（腔 QED 物理链 · 平台缺口 G5 专属 · 非既有锚重复）：
  · **B494** 腔品质因子 Q=ω/κ（腔自身损耗属性 · 无量纲）；
  · **B495** 有效模体积 V_eff=A·8a/15（腔空间局域度 · m³）；
  · **B496** 单光子耦合 g=(μ/ħ)√(ħω/(εV_eff))（腔 QED 耦合强度 · Hz）。
🔴 **如实不登记**：finesse ℱ=Q·λ/(2na)（**闭式算术**）· γ_rad=ω³μ²/(3πε₀ħc³)（**闭式算术**）·
  cooperativity **两口径**：g_form C=4g²/(κγ_rad) / qv_form C=F_P·(γ_rad/γ₁)（**比值闭式 2n·γ₁/γ_rad · K1 已结算**）·
  Purcell FOM F_P=(3/4π²)(λ/n)³(Q/V)（**组合标量**，与 B18 对照）——以上归本 smoke 覆盖，
  **不登记为 B 锚**（同 B-44/B-45/B-46/B-47 纪律：宁可少，不越级谎报）。

═══ 诚实边界 ═══
· ω/κ/a/A/μ/n 均为**设计示例量级**（金刚石微盘腔 telecom 典型），**非实测 PDK**。
· 🔴 本档**不做**器件级/系统级性能宣称；报告为**建模值**（Q=1e4 · V_eff≈4.13e-20 m³ ·
  g≈1.65e10 Hz 设计示例）。
· 🔴 cooperativity 的因子 2n 是**本仓约定**下的实现自洽检查（查 bug，非跨约定物理恒等式宣示）。
· 🔴 与 B18（Purcell 组合标量 F_P=4g²/(κγ₁)）**对照而不混**：本档登的是 F_P 的**输入量**
  （Q/V/g 本身 ≠ F_P），物理对象不同 ⇒ 记新锚。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    from lda_l2 import qs_m3c as M

    # 设计示例参数（与模块 design_defaults / 锚核默认档一致）
    _omega = 2.0 * 3.141592653589793 * 299792458.0 / 1550.0e-9
    _kappa = _omega / 1.0e4
    _a = 1.55e-6
    _A = 5.0e-14
    _mu = 1.0e-29
    _eps = 8.8541878128e-12 * 3.4 ** 2
    _t = 8.22e-12

    # ══════════════════════ A 三链物理 ══════════════════════
    q_c = M.cavity_q_factor(_omega, _kappa)
    q_n = M.cavity_q_factor_numeric(_omega, _kappa, _t, 64)
    q_coarse = M.cavity_q_factor_numeric(_omega, _kappa, _t, 8)
    check("A1 腔品质因子 Q：闭式 ⇄ RK4 数值一致（rel<1e-7）· 粗网格(n=8) 残差放大 >100× · "
          "κ↑⇒Q↓（单调）· κ=0 ⇒ 抛",
          abs(q_n - q_c) / abs(q_c) < 1e-7
          and abs(q_coarse - q_c) > 100.0 * abs(q_n - q_c)
          and M.cavity_q_factor(_omega, 2.0 * _kappa) < q_c
          < M.cavity_q_factor(_omega, 0.5 * _kappa)
          and _raises(lambda: M.cavity_q_factor(_omega, 0.0)))

    v_c = M.mode_volume_closed(_a, _A)
    v_n = M.mode_volume_numeric(_a, _A, 256)
    v_coarse = M.mode_volume_numeric(_a, _A, 32)
    check("A2 有效模体积 V_eff：闭式 A·8a/15 ⇄ 中点求积一致（rel<1e-4）· 粗网格放大 ≥20× · "
          "a↑⇒V_eff↑（单调）· A=0 ⇒ 抛",
          abs(v_n - v_c) / abs(v_c) < 1e-4
          and abs(v_coarse - v_c) >= 20.0 * abs(v_n - v_c)
          and M.mode_volume_closed(2.0 * _a, _A) > v_c
          and _raises(lambda: M.mode_volume_closed(_a, 0.0)))

    g_c = M.single_photon_coupling_closed(_mu, _omega, _eps, _a, _A)
    g_n = M.single_photon_coupling_numeric(_mu, _omega, _eps, _a, _A, 256)
    g_coarse = M.single_photon_coupling_numeric(_mu, _omega, _eps, _a, _A, 32)
    check("A3 单光子耦合 g：闭式 ⇄ 数值场能积分一致（rel<1e-4）· 粗网格放大 ≥20× · "
          "g∝μ（线性）· μ=0 ⇒ 抛",
          abs(g_n - g_c) / abs(g_c) < 1e-4
          and abs(g_coarse - g_c) >= 20.0 * abs(g_n - g_c)
          and abs(M.single_photon_coupling_closed(2.0 * _mu, _omega, _eps, _a, _A)
                  / g_c - 2.0) < 1e-9
          and _raises(lambda: M.single_photon_coupling_closed(
              0.0, _omega, _eps, _a, _A)))

    # ══════════════════════ B 跨源一致性（模块 ⇄ 锚核）══════════════════════
    from lda_harness import _batch_qs_m3c_numeric as NB

    _dp494 = NB.B494_DEFAULT_PARAMS
    _dp495 = NB.B495_DEFAULT_PARAMS
    _dp496 = NB.B496_DEFAULT_PARAMS
    _pairs_closed = [
        ("B494", M.cavity_q_factor(_dp494["omega"], _dp494["kappa"]),
         NB.q_factor_golden(_dp494["omega"], _dp494["kappa"], _dp494["t_observe"])),
        ("B495", M.mode_volume_closed(_dp495["a"], _dp495["A"]),
         NB.mode_volume_golden(_dp495["a"], _dp495["A"])),
        ("B496", M.single_photon_coupling_closed(
            _dp496["mu"], _dp496["omega"], _dp496["eps"], _dp496["a"], _dp496["A"]),
         NB.coupling_golden(
            _dp496["mu"], _dp496["omega"], _dp496["eps"], _dp496["a"], _dp496["A"])),
    ]
    _wc = max(abs(a - b) / max(abs(b), 1e-300) for _, a, b in _pairs_closed)
    check("B1 🔴 模块闭式 ≡ 锚核 golden **逐位**（三锚 rel < 1e-12 · 防两份实现漂移）",
          _wc < 1e-12, "max rel = %.3e" % _wc)

    _pairs_num = [
        ("B494", M.cavity_q_factor_numeric(
            _dp494["omega"], _dp494["kappa"], _dp494["t_observe"], 64),
         NB.q_factor_candidate(
            _dp494["omega"], _dp494["kappa"], _dp494["t_observe"], 64)),
        ("B495", M.mode_volume_numeric(_dp495["a"], _dp495["A"], 256),
         NB.mode_volume_candidate(_dp495["a"], _dp495["A"], 256)),
        ("B496", M.single_photon_coupling_numeric(
            _dp496["mu"], _dp496["omega"], _dp496["eps"], _dp496["a"], _dp496["A"], 256),
         NB.coupling_candidate(
            _dp496["mu"], _dp496["omega"], _dp496["eps"], _dp496["a"], _dp496["A"], 256)),
    ]
    _wn = max(abs(a - b) / max(abs(b), 1e-300) for _, a, b in _pairs_num)
    check("B2 🔴 模块数值候选 ≡ 锚核 candidate **逐位**（三锚 rel < 1e-12）",
          _wn < 1e-12, "max rel = %.3e" % _wn)

    _omega_mod = 2.0 * 3.141592653589793 * M.C_LIGHT / M.design_defaults()["lambda0_m"]
    check("B3 物理常数跨源一致（HBAR/C/EPSILON_0 · 设计 ω 与锚核 _OMEGA_DEF 逐位）",
          M.HBAR == NB.HBAR and M.C_LIGHT == NB.C_LIGHT and M.EPSILON_0 == NB.EPSILON_0
          and abs(_omega_mod - NB._OMEGA_DEF) / NB._OMEGA_DEF < 1e-12)

    # ══════════════════════ C 判据 D（离散化响应）══════════════════════
    # 🔴 判据 D 的**权威扫描网格** = 锚核 `_GRID_BY_BID`（4 档等比 ×2）；不复用
    #   `harness.candidate_discretization_responds`（它固定扫 n∈{2,4,8,32,128,512}，
    #   而本批护栏要求 n_seg/n_steps ≥ 4 ⇒ n=2 会抛 ⇒ 该助手提前返回 error、无残差链）。
    _CP = {
        "B494": (lambda n: M.cavity_q_factor_numeric(_omega, _kappa, _t, n_steps=n),
                 lambda: M.cavity_q_factor(_omega, _kappa)),
        "B495": (lambda n: M.mode_volume_numeric(_a, _A, n_seg=n),
                 lambda: M.mode_volume_closed(_a, _A)),
        "B496": (lambda n: M.single_photon_coupling_numeric(
            _mu, _omega, _eps, _a, _A, n_seg=n),
                 lambda: M.single_photon_coupling_closed(_mu, _omega, _eps, _a, _A)),
    }
    for _bid, (_cf, _gf) in _CP.items():
        _g = _gf()
        _res = [abs(_cf(n) - _g) / max(abs(_g), 1e-300) for n in NB._GRID_BY_BID[_bid]]
        _mono = all(_res[i] > _res[i + 1] for i in range(len(_res) - 1))
        _ratio = [_res[i] / _res[i + 1] for i in range(len(_res) - 1)]
        _order_ok = all(1.5 <= x <= 40.0 for x in _ratio)
        check("C %s 判据 D PASS（4 档残差**严格单调收敛** · 粗端 ≥20× 细端 · 收敛比同阶）" % _bid,
              _mono and _order_ok and _res[0] >= 20.0 * _res[-1],
              "残差 " + " → ".join("%.2e" % r for r in _res)
              + " | 比 " + " ".join("%.2f×" % x for x in _ratio))

    # ══════════════════════ D 三锚接线复核 ══════════════════════
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER  # noqa: E402
    from lda_harness.harness import (CANDIDATE_CLASS_STRICT,  # noqa: E402
                                     IndependentCandidateRouter)
    from lda_harness.verification_adapters import build_harness_specs  # noqa: E402

    _BIDS = ("B494", "B495", "B496")
    # 🔴 门禁必须**能自判红而非崩溃**（skill 纪律）：`build_harness_specs()` 依赖三锚 golden
    #   全登记，突变掉任一 golden 会抛 ⇒ 必须捕获成**具名 [FAIL]**（否则 exit=99 丢失归因）。
    _smap, _cls, _res_nonzero = {}, {}, {}
    try:
        _specs, _cand = build_harness_specs()
        _smap = {s.spec_id: s for s in _specs}
        _router = IndependentCandidateRouter()
        _cls = {b: _router.candidate_class(b) for b in _BIDS}
        for _b in _BIDS:
            _sp = _smap[_b]
            _ov = _sp.oracle_fn(_sp.params)
            _cv = _cand[_b](_sp, _ov)
            _res_nonzero[_b] = abs(float(_cv) - float(_ov))
        _build_ok, _exc = True, None
    except Exception as e:  # noqa: BLE001
        _build_ok, _exc = False, e
    check("D0 🔴 三锚 harness 接线可用（`build_harness_specs` 不抛：golden 全登记）",
          _build_ok, "exc=%r" % (_exc,))

    check("D1 🔴 三锚分类 = strict_independent（非自证桩/非降级）",
          bool(_cls) and all(v == CANDIDATE_CLASS_STRICT for v in _cls.values()), str(_cls))

    check("D2 🔴 三锚判决残差**严格非零**（防候选回落 golden ⇒ 假独立）",
          bool(_res_nonzero) and all(v > 0.0 for v in _res_nonzero.values()),
          str({k: "%.3e" % v for k, v in _res_nonzero.items()}))

    _pass_ok = False
    if _build_ok:
        _pass_ok = all(
            _smap[b].compare_fn(_cand[b](_smap[b], _smap[b].oracle_fn(_smap[b].params)),
                                _smap[b].oracle_fn(_smap[b].params)) for b in _BIDS)
    check("D3 🔴 三锚正向判决全 PASS（candidate ⇄ golden）", _pass_ok, "build_ok=%s" % _build_ok)

    _tol_ok = all(BENCHMARK_DEFS[b]["tol"] == NB._TOL_BY_BID[b] for b in _BIDS)
    check("D4 🔴 三锚 tol 读自 BENCHMARK_DEFS 且 ≡ 锚核 `_TOL_BY_BID`（不硬编码/不漂移）",
          _tol_ok, str({b: BENCHMARK_DEFS[b]["tol"] for b in _BIDS}))

    _default_is_grid_end = all(
        BENCHMARK_DEFS[b]["default_params"] and NB._N_BY_BID[b] == NB._GRID_BY_BID[b][-1]
        for b in _BIDS)
    check("D5 🔴 默认档 = 判据 D 扫描网格**末端**（纪律：定档必须 = 扫描最大档）",
          _default_is_grid_end,
          str({b: (NB._N_BY_BID[b], NB._GRID_BY_BID[b][-1]) for b in _BIDS}))

    _param_keys_ok = all(
        set(BENCHMARK_DEFS[b]["default_params"])
        <= set(__import__("inspect").signature(BENCHMARK_DEFS[b]["golden_fn"]).parameters)
        for b in _BIDS)
    check("D6 🔴 `default_params` 键集 ⊆ golden 形参集（防 `golden_value` 抛 TypeError · 血案）",
          _param_keys_ok,
          str({b: sorted(BENCHMARK_DEFS[b]["default_params"]) for b in _BIDS}))

    # ══════════════════════ E 反向探针 ══════════════════════
    check("E1 🔴 零 κ ⇒ 抛（非法 · Q 发散）",
          _raises(lambda: M.cavity_q_factor(_omega, 0.0)))
    check("E2 🔴 零 A / 零 V_eff(a=0) ⇒ 抛",
          _raises(lambda: M.mode_volume_closed(_a, 0.0))
          and _raises(lambda: M.single_photon_coupling_closed(
              _mu, _omega, _eps, 0.0, _A)))
    check("E3 🔴 零 μ ⇒ 抛",
          _raises(lambda: M.single_photon_coupling_closed(
              0.0, _omega, _eps, _a, _A)))
    check("E4 🔴 错口径 ⇒ assert_caliber 抛（禁与幅度谱密度 T/√Hz 混比）",
          _raises(lambda: M.assert_caliber("linearwidth_limited_LOD")))
    check("E5 🔴 情景单调性方向反证（高 κ 更差 / 大 a 更差 —— 方向反则必红）",
          M.cavity_q_factor(_omega, 2.0 * _kappa) < q_c
          and M.mode_volume_closed(2.0 * _a, _A) > v_c
          and M.single_photon_coupling_closed(2.0 * _mu, _omega, _eps, _a, _A) > g_c)
    check("E6 🔴 极粗网格 ⇒ 三链残差 ≫ 细网格（真数值残差 · 非代数恒等）",
          abs(M.cavity_q_factor_numeric(_omega, _kappa, _t, 8)
              - M.cavity_q_factor(_omega, _kappa))
          > 100.0 * abs(M.cavity_q_factor_numeric(_omega, _kappa, _t, 64)
                        - M.cavity_q_factor(_omega, _kappa))
          and abs(M.mode_volume_numeric(_a, _A, 32)
                  - M.mode_volume_closed(_a, _A))
          > 20.0 * abs(M.mode_volume_numeric(_a, _A, 256)
                       - M.mode_volume_closed(_a, _A))
          and abs(M.single_photon_coupling_numeric(_mu, _omega, _eps, _a, _A, 32)
                  - M.single_photon_coupling_closed(_mu, _omega, _eps, _a, _A))
          > 20.0 * abs(M.single_photon_coupling_numeric(_mu, _omega, _eps, _a, _A, 256)
                       - M.single_photon_coupling_closed(_mu, _omega, _eps, _a, _A)))

    # ══════════════════════ F 物理整合 ══════════════════════
    _ph = M.cavity_qed_physics()
    check("F1 🔴 finesse 两式逐位一致（ℱ=Q·λ/(2na) ≡ FSR/Δν）",
          abs(_ph["finesse"] - _ph["finesse_from_defs"]) / abs(_ph["finesse"]) < 1e-12,
          "finesse=%.6e" % _ph["finesse"])

    _ratio_c = _ph["cooperativity_g_form"] / _ph["purcell_F_P"]
    check("F2 🔴 cooperativity 约定因子 = 2n（诚实口径 · 模块内自洽查 bug · 非跨约定恒等式宣示）",
          abs(_ratio_c - 2.0 * M.design_defaults()["n_r"]) < 1e-9,
          "ratio=%.6e · 2n=%.6e" % (_ratio_c, 2.0 * M.design_defaults()["n_r"]))

    check("F3 Purcell FOM F_P=(3/4π²)(λ/n)³(Q/V) 量级合理（正有限 · 设计示例量级）",
          0.0 < _ph["purcell_F_P"] < 1e6,
          "F_P = %.4e" % _ph["purcell_F_P"])

    _rep = M.design_qs_m3c(run_checks=True)
    check("F4 🔴 综合签核（design_qs_m3c verdict=ACCEPT + 物理链全键齐全）",
          _rep["verdict"] == "ACCEPT"
          and all(k in _ph for k in ("Q", "V_eff_m3", "g_Hz",
                                     "finesse", "purcell_F_P", "cooperativity_g_form")))

    # ══════════════════════ G 自入 CI core ══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        check("G1 本 smoke 已登记进 CORE_SMOKES（防静默漏接）",
              "run_qs_m3c_smoke.py" in R.CORE_SMOKES, "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("G1 本 smoke 已登记进 CORE_SMOKES（防静默漏接）", False, "import 失败: %s" % e)

    from lda_harness.golden import _GOLDEN_DISPATCH as _GD  # noqa: E402
    from lda_harness.golden import _PHYSICAL_LAW as _PL  # noqa: E402
    check("G2 🔴 B494–B496 golden 必在 `_GOLDEN_DISPATCH` 内有定义（防漏登 ⇒ 假自证桩）",
          all(b in _GD for b in _BIDS))
    check("G3 🔴 B494–B496 必在 `BENCHMARK_ORDER` 内（增锚同登契约 · 硬编码表）",
          all(b in BENCHMARK_ORDER for b in _BIDS)
          and len(BENCHMARK_ORDER) == len(BENCHMARK_DEFS))
    check("G4 🔴 B494–B496 必在 `_PHYSICAL_LAW` 内（防 `golden_with_source` 判不出物理定律来源）",
          all(b in _PL for b in _BIDS))

    # ══════════════════════ H 模块自检直连 ══════════════════════
    check("H1 模块自检直连（qs_m3c.selfcheck_qs_m3c 全项 PASS）",
          all(M.selfcheck_qs_m3c().values()),
          "n=%d" % len(M.selfcheck_qs_m3c()))

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
