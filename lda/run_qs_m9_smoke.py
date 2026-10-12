#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M9（G11 多物理场量子传感整合）· 光泵原子磁力计（OPM / SERF · 腿 C）门禁（v0.9.226）。

═══ 判什么（分节）═══
A 五链物理（光子能量/通量自洽 · R_op=σ_abs·Φ·f_depump 线性 · R_sd 三源求和 ·
  P∞ 单调 + R_sd→0 饱和到 1 · **FID 闭式 ⇄ RK4 数值**一致 + **粗网格残差放大** ·
  Larmor ∝ B + B=0 纯衰减 · **密度闭式 ⇄ 梯形数值**一致 + 粗网格放大 + 单调 + T_ref 自洽 ·
  **透过率闭式 ⇄ RK4 数值**一致 + 粗网格放大 + τ=1 ⇒ 1/e · SERF 灵敏度量级 + 单调性 +
  谱密度归一自洽 · 亥姆霍兹线圈闭式）·
B 🔴 **跨源一致性**：`lda_l2.qs_m9` 闭式 ≡ `lda_harness._batch_b47_numeric` 锚 golden **逐位**
  （防「演示模块与锚核两份实现漂移」）·
C 🔴 **判据 D 扫描**（对三锚逐锚扫候选自身离散参数：残差须**严格单调收敛**且粗端 ≫ 细端
  ⇒ 真数值残差、非代数恒等）·
D 🔴 **三锚接线复核**（B491–B493 入 BENCHMARK_DEFS · 分类 = strict_independent ·
  候选有响应（反自证桩）· 残差非零（防回落 golden）· tol 读自 DEFS 不硬编码 ·
  默认档 = 判据 D 扫描网格末端）·
E 反向探针（零 N_a / 零 R_tot / 零温度 / 零长度 ⇒ 抛 · 错口径 ⇒ 抛 ·
  情景单调性方向反证 · 极粗网格 ⇒ 残差 ≫ 细网格）·
F 多物理场整合（三腿同口径对照 · SERF η 量级 · SOTA 对照比 · 五情景可现算 · 签核全绿）·
G 自入 CI core（防静默漏接 · **golden 分派必含三锚**（防漏登 ⇒ 假自证桩）·
  三锚必在 BENCHMARK_ORDER · `_PHYSICAL_LAW` 必含三锚）·
H 模块自检直连（`qs_m9.selfcheck_qs_m9` 全项 PASS）。

═══ 🔴 锚账本口径（本档**净增 3 道锚** B491–B493）═══
QS-M9 交付**新物理量**（OPM 腿 C 专属 · 非既有锚重复）：
  · **B491** 自由进动横向极化 P_x(t*)（时域信号本体 · 无量纲）；
  · **B492** 碱金属饱和蒸气数密度 n(T)（气室温度定标 · m⁻³）；
  · **B493** 泵浦光 Beer–Lambert 透过率 T(L)（气室光路 · 无量纲）。
🔴 **如实不登记**：P∞ 速率方程稳态（**稳态闭式**）· 亥姆霍兹线圈 B(0)（**闭式算术**）·
弛豫率三源求和（**定义式**）· SERF 灵敏度 η 整合标量（其自旋投影噪声因子 √(1/N_a) 的
统计本质**无可行数值候选** —— 任何 MC 需模拟 N_a≈1e13 个独立自旋）· 各极限/自洽点
（τ=1 ⇒ 1/e · n(T_ref)=n_ref · R_sd→0 ⇒ P∞=1）——以上归本 smoke 覆盖，**不登记为 B 锚**
（同 B-44/B-45/B-46 纪律：宁可少，不越级谎报）。
🔴 **不含线圈磁场锚**（亥姆霍兹闭式算术）⇒ **不与 B488 的离散 Neumann 互感撞车**。

═══ 诚实边界 ═══
· 泵浦功率 / 束面积 / 吸收截面 / 弛豫率 / 气室几何 / 温度 / 数密度均为**设计示例量级**
  （SERF OPM 典型），**非实测装置 PDK**。
· 🔴 本档**不做**器件级/系统级性能宣称；报告为**建模值**（η≈0.97 fT/√Hz）。
· 🔴 「SERF ~0.16 fT/√Hz」为**蓝图层引用的公开文献值**（SERF 最优报道），作**对标准星**；
  本档建模值与之**独立**，**不得**声称「实测达到」该水平。
· 🔴 三腿对照（NV 8.47e5 / SQUID 1.73 / OPM 0.97 fT/√Hz）**只做同口径量级对照**，
  **不构成任何性能宣称**、**不同台比较**。
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
    from lda_l2 import qs_m9 as M

    # ══════════════════════ A 五链物理 ══════════════════════
    eph = M.photon_energy_j()
    check("A1 光子能量 E_ph=hc/λ（795 nm ⇒ 2.499e-19 J）· 通量 Φ=P/(E_ph·A) 自洽",
          abs(eph - 2.499e-19) / 2.499e-19 < 1e-3
          and abs(M.photon_flux_per_m2_s(5e-3, 4e-6) * eph - 5e-3 / 4e-6) < 1e-3)

    r_op = M.optical_pumping_rate_s1(5e-18, M.photon_flux_per_m2_s(5e-3, 4e-6), 0.5)
    check("A2 泵浦率 R_op ∝ σ_abs·Φ·f_depump（线性三段 + 非零）",
          r_op > 0 and abs(M.optical_pumping_rate_s1(2 * 5e-18,
                                                     M.photon_flux_per_m2_s(5e-3, 4e-6),
                                                     0.5) - 2 * r_op) < 1e-9)

    check("A3 自旋破坏率 R_sd = 壁 + 缓冲气体 + 探测光（三源相加 = 300 1/s）",
          abs(M.spin_destruction_rate_s1(50, 150, 100) - 300.0) < 1e-12)

    p_inf = M.steady_polarization(r_op, 300.0)
    check("A4 稳态极化 P∞ ∈(0,1) · R_op↑ ⇒ P∞↑（单调）· R_sd=0 ⇒ P∞=1（饱和极限）",
          0.0 < p_inf < 1.0
          and M.steady_polarization(2 * r_op, 300.0) > p_inf
          and abs(M.steady_polarization(r_op, 0.0) - 1.0) < 1e-15)

    p_c = M.transverse_polarization_closed(1.0, 300.0, 10e-9, 2e-3)
    p_n = M.transverse_polarization_numeric(1.0, 300.0, 10e-9, 2e-3, n_steps=64)
    p_coarse = M.transverse_polarization_numeric(1.0, 300.0, 10e-9, 2e-3, n_steps=8)
    check("A5 FID 闭式 ⇄ RK4 数值一致（rel<1e-7）· 粗网格(n=8) 残差放大 >10× · "
          "B=0 ⇒ 纯衰减 e^(−R t)",
          abs(p_n - p_c) / abs(p_c) < 1e-7
          and abs(p_coarse - p_c) > 10.0 * abs(p_n - p_c)
          and abs(M.transverse_polarization_closed(1.0, 300.0, 0.0, 2e-3)
                  - 2.718281828459045 ** -0.6) < 1e-12)

    check("A6 Larmor ∝ B（ω_L=2πγ_eB）· B=0 ⇒ ω_L=0",
          abs(M.larmor_rad_s(2e-9) - 2 * M.larmor_rad_s(1e-9)) < 1e-9
          and M.larmor_rad_s(0.0) == 0.0)

    n_c = M.alkali_density_closed(1e17, 313.15, 8384.0, 333.15)
    n_n = M.alkali_density_numeric(1e17, 313.15, 8384.0, 333.15, n_seg=256)
    n_coarse = M.alkali_density_numeric(1e17, 313.15, 8384.0, 333.15, n_seg=32)
    check("A7 密度闭式 ⇄ 梯形数值一致（rel<1e-5）· 粗网格放大 ≥20× · T↑⇒n↑（单调）· "
          "T=T_ref ⇒ n=n_ref（自洽点）",
          abs(n_n - n_c) / n_c < 1e-5
          and abs(n_coarse - n_c) >= 20.0 * abs(n_n - n_c)
          and M.alkali_density_closed(1e17, 313.15, 8384.0, 373.15) > n_c
          and abs(M.alkali_density_closed(1e17, 313.15, 8384.0, 313.15) - 1e17) < 1e3)

    t_c = M.pump_transmission_closed(1.0, 1e19, 5e-18, 0.02)
    t_n = M.pump_transmission_numeric(1.0, 1e19, 5e-18, 0.02, n_steps=64)
    t_coarse = M.pump_transmission_numeric(1.0, 1e19, 5e-18, 0.02, n_steps=8)
    check("A8 透过率闭式 ⇄ RK4 数值一致（rel<1e-7）· 粗网格放大 >10× · 光学厚度=1 ⇒ T=1/e",
          abs(t_n - t_c) / t_c < 1e-7
          and abs(t_coarse - t_c) > 10.0 * abs(t_n - t_c)
          and abs(t_c - 2.718281828459045 ** -1.0) < 1e-12)

    eta = M.serf_sensitivity_t_per_sqrt_hz(1.28e4, 1e13, 0.9766)
    slope = M.low_field_slope_per_t(1.28e4, 0.9766)
    dp = M.spin_projection_polarization_noise(1e13)
    check("A9 SERF 灵敏度量级 1e-17~1e-14 T/√Hz · N_a↑⇒η↓ · R_tot↑⇒η↑ · "
          "谱密度归一自洽（δp/斜率·√τ_c ≡ η）",
          1e-17 <= eta <= 1e-14
          and M.serf_sensitivity_t_per_sqrt_hz(1.28e4, 4e13, 0.9766) < eta
          and M.serf_sensitivity_t_per_sqrt_hz(2.56e4, 1e13, 0.9766) > eta
          and abs(dp / slope * (1.0 / 1.28e4) ** 0.5 - eta) / eta < 1e-12)

    check("A10 亥姆霍兹线圈 B(0)=(4/5)^{3/2}µ₀NI/R（闭式 · 正值 · 线性于 I）",
          M.helmholtz_field_t(1.0, 100, 0.05) > 0
          and abs(M.helmholtz_field_t(2.0, 100, 0.05)
                  - 2 * M.helmholtz_field_t(1.0, 100, 0.05)) < 1e-15)

    # ══════════════════════ B 跨源一致性（模块 ⇄ 锚核）══════════════════════
    from lda_harness import _batch_b47_numeric as NB

    _pairs = [
        ("B491", M.transverse_polarization_closed(1.0, 300.0, 10e-9, 2e-3),
         NB.fid_polarization_golden(1.0, 300.0, 10e-9, 2e-3)),
        ("B492", M.alkali_density_closed(1e17, 313.15, 8384.0, 333.15),
         NB.alkali_density_golden(1e17, 313.15, 8384.0, 333.15)),
        ("B493", M.pump_transmission_closed(1.0, 1e19, 5e-18, 0.02),
         NB.pump_transmission_golden(1.0, 1e19, 5e-18, 0.02)),
    ]
    _w = max(abs(a - b) / max(abs(b), 1e-300) for _, a, b in _pairs)
    check("B1 🔴 模块闭式 ≡ 锚核 golden **逐位**（三锚 rel < 1e-12 · 防两份实现漂移）",
          _w < 1e-12, "max rel = %.3e" % _w)

    _pc = [
        ("B491", M.transverse_polarization_numeric(1.0, 300.0, 10e-9, 2e-3, n_steps=64),
         NB.fid_polarization_candidate(1.0, 300.0, 10e-9, 2e-3, 64)),
        ("B492", M.alkali_density_numeric(1e17, 313.15, 8384.0, 333.15, 256),
         NB.alkali_density_candidate(1e17, 313.15, 8384.0, 333.15, 256)),
        ("B493", M.pump_transmission_numeric(1.0, 1e19, 5e-18, 0.02, 64),
         NB.pump_transmission_candidate(1.0, 1e19, 5e-18, 0.02, 64)),
    ]
    _wc = max(abs(a - b) / max(abs(b), 1e-300) for _, a, b in _pc)
    check("B2 🔴 模块数值候选 ≡ 锚核 candidate **逐位**（三锚 rel < 1e-12）",
          _wc < 1e-12, "max rel = %.3e" % _wc)

    check("B3 物理常数跨源一致（γ_e / ΔH/k_B / 参考点 n_ref,T_ref）",
          M.GAMMA_RB_HZ_T == NB._GAMMA_RB_HZ_T
          and M.DH_VAP_OVER_KB_K == NB._DH_OVER_KB_RB_K
          and M.N_REF_M3 == NB.B492_DEFAULT_PARAMS["n_ref_m3"]
          and M.T_REF_K == NB.B492_DEFAULT_PARAMS["t_ref_k"])

    # ══════════════════════ C 判据 D（离散化响应）══════════════════════
    # 🔴 判据 D 的**权威扫描网格** = 锚核 `_GRID_BY_BID`（4 档等比 ×2）；不复用
    #   `harness.candidate_discretization_responds`（它固定扫 n∈{2,4,8,32,128,512}，
    #   而本批护栏要求 n_seg/n_steps ≥ 4 ⇒ n=2 会抛 ⇒ 该助手提前返回 error、无残差链）。
    #   本段自行扫 4 档并要求：**严格单调降** ∧ 粗端 ≥ 20× 细端 ∧ 收敛比在同阶带内。
    from lda_harness import _batch_b47_numeric as _NB  # noqa: E402,F811
    _CP = {
        "B491": (lambda n: M.transverse_polarization_numeric(
            1.0, 300.0, 10e-9, 2e-3, n_steps=n),
            lambda: M.transverse_polarization_closed(1.0, 300.0, 10e-9, 2e-3)),
        "B492": (lambda n: M.alkali_density_numeric(1e17, 313.15, 8384.0, 333.15, n_seg=n),
                 lambda: M.alkali_density_closed(1e17, 313.15, 8384.0, 333.15)),
        "B493": (lambda n: M.pump_transmission_numeric(
            1.0, 1e19, 5e-18, 0.02, n_steps=n),
            lambda: M.pump_transmission_closed(1.0, 1e19, 5e-18, 0.02)),
    }
    for _bid, (_cf, _gf) in _CP.items():
        _g = _gf()
        _res = [abs(_cf(n) - _g) / max(abs(_g), 1e-300) for n in _NB._GRID_BY_BID[_bid]]
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

    _BIDS = ("B491", "B492", "B493")
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
    check("E1 🔴 零 N_a ⇒ 抛（非法 · 灵敏度发散）",
          _raises(lambda: M.serf_sensitivity_t_per_sqrt_hz(1.0, 0.0, 1.0)))
    check("E2 🔴 零 R_tot / 零 p_inf ⇒ 抛",
          _raises(lambda: M.serf_sensitivity_t_per_sqrt_hz(0.0, 1e13, 0.5))
          and _raises(lambda: M.serf_sensitivity_t_per_sqrt_hz(1.0, 1e13, 0.0)))
    check("E3 🔴 零温度 / 零长度 / 零 t* ⇒ 抛",
          _raises(lambda: M.alkali_density_closed(1e17, 313.15, 8384.0, 0.0))
          and _raises(lambda: M.pump_transmission_closed(1.0, 1e19, 5e-18, 0.0))
          and _raises(lambda: M.transverse_polarization_closed(1.0, 300.0, 1e-9, 0.0)))
    check("E4 🔴 错口径 ⇒ assert_caliber 抛（禁与线宽受限 LOD 混比）",
          _raises(lambda: M.assert_caliber("linearwidth_limited_LOD")))
    check("E5 🔴 情景单调性方向反证（高温更优 / 低弛豫更优 —— 方向反则必红）",
          M.evaluate_scenario("hot_cell")["eta_t_per_sqrt_hz"]
          < M.evaluate_scenario("baseline")["eta_t_per_sqrt_hz"]
          and M.evaluate_scenario("low_relaxation")["eta_t_per_sqrt_hz"]
          < M.evaluate_scenario("baseline")["eta_t_per_sqrt_hz"]
          and M.evaluate_scenario("cold_cell")["eta_t_per_sqrt_hz"]
          > M.evaluate_scenario("baseline")["eta_t_per_sqrt_hz"])
    check("E6 🔴 极粗网格 ⇒ 三链残差 ≫ 细网格（真数值残差 · 非代数恒等）",
          abs(M.transverse_polarization_numeric(1.0, 300.0, 10e-9, 2e-3, n_steps=8)
              - M.transverse_polarization_closed(1.0, 300.0, 10e-9, 2e-3))
          > 100.0 * abs(M.transverse_polarization_numeric(1.0, 300.0, 10e-9, 2e-3, n_steps=64)
                        - M.transverse_polarization_closed(1.0, 300.0, 10e-9, 2e-3))
          and abs(M.alkali_density_numeric(1e17, 313.15, 8384.0, 333.15, 32)
                  - M.alkali_density_closed(1e17, 313.15, 8384.0, 333.15))
          > 20.0 * abs(M.alkali_density_numeric(1e17, 313.15, 8384.0, 333.15, 256)
                       - M.alkali_density_closed(1e17, 313.15, 8384.0, 333.15))
          and abs(M.pump_transmission_numeric(1.0, 1e19, 5e-18, 0.02, 8)
                  - M.pump_transmission_closed(1.0, 1e19, 5e-18, 0.02))
          > 100.0 * abs(M.pump_transmission_numeric(1.0, 1e19, 5e-18, 0.02, 64)
                        - M.pump_transmission_closed(1.0, 1e19, 5e-18, 0.02)))

    # ══════════════════════ F 多物理场整合 ══════════════════════
    _legs = M.three_legs_table()
    check("F1 🔴 三腿同口径对照（OPM < SQUID < NV · fT/√Hz · **只做量级对照 · 非宣称**）",
          _legs["opm_leg_fT_per_sqrt_hz"] < _legs["squid_leg_fT_per_sqrt_hz"]
          < _legs["nv_leg_fT_per_sqrt_hz"],
          "OPM %.4f / SQUID %.3f / NV %.3e fT/√Hz"
          % (_legs["opm_leg_fT_per_sqrt_hz"], _legs["squid_leg_fT_per_sqrt_hz"],
             _legs["nv_leg_fT_per_sqrt_hz"]))

    _ph = M.opm_serf_physics()
    check("F2 SERF η 落在自旋投影噪声极限的合理量级（1e-16~1e-14 T/√Hz · 建模值）",
          1e-16 <= _ph["eta_t_per_sqrt_hz"] <= 1e-14,
          "η = %.4f fT/√Hz" % _ph["eta_fT_per_sqrt_hz"])

    check("F3 SOTA 对照比 = η/SOTA > 1（**未达** SOTA ⇒ 如实不宣称「已达国际水平」）",
          _ph["sota_ratio"] > 1.0, "sota_ratio = %.2f" % _ph["sota_ratio"])

    _st = M.sensitivity_table()
    check("F4 五情景表可现算（每项有限正）",
          len(_st) == 5 and all(v["eta_fT_per_sqrt_hz"] > 0 for v in _st.values()))

    _rep = M.design_qs_opm(run_checks=True)
    check("F5 五链串联签核（design_qs_opm verdict=ACCEPT + 三腿表 + 情景表）",
          _rep["verdict"] == "ACCEPT" and _rep["three_legs"]["caliber"]
          == M.SENSITIVITY_CALIBER and len(_rep["scenarios"]) == 5)

    # ══════════════════════ G 自入 CI core ══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        check("G1 本 smoke 已登记进 CORE_SMOKES（防静默漏接）",
              "run_qs_m9_smoke.py" in R.CORE_SMOKES, "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("G1 本 smoke 已登记进 CORE_SMOKES（防静默漏接）", False, "import 失败: %s" % e)

    from lda_harness.golden import _GOLDEN_DISPATCH as _GD  # noqa: E402
    from lda_harness.golden import _PHYSICAL_LAW as _PL  # noqa: E402
    check("G2 🔴 B491–B493 golden 必在 `_GOLDEN_DISPATCH` 内有定义（防漏登 ⇒ 假自证桩）",
          all(b in _GD for b in _BIDS))
    check("G3 🔴 B491–B493 必在 `BENCHMARK_ORDER` 内（增锚同登契约 · 硬编码表）",
          all(b in BENCHMARK_ORDER for b in _BIDS)
          and len(BENCHMARK_ORDER) == len(BENCHMARK_DEFS))
    check("G4 🔴 B491–B493 必在 `_PHYSICAL_LAW` 内（防 `golden_with_source` 判不出物理定律来源）",
          all(b in _PL for b in _BIDS))

    # ══════════════════════ H 模块自检直连 ══════════════════════
    check("H1 模块自检直连（qs_m9.selfcheck_qs_m9 全项 PASS）",
          all(M.selfcheck_qs_m9().values()),
          "n=%d" % len(M.selfcheck_qs_m9()))

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
