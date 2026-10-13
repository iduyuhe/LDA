#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J2 超导 Transmon QPU 征程 · 物理错误模型 + J1↔J2 复利闭环能力门禁（M0/M1 落地配套）。

═══ 判什么（分节）═══
A 🔴 **物理错误模型（闭式 ⇄ 数值 Lindblad RK4）**：单比特门退相干极限平均门保真度闭式
   F=(3+2e^{−t/T2}+e^{−t/T1})/6 与 Bloch 向量 Lindblad 主方程 RK4 数值积分一致（现实档
   rel 须 < 1e-9）；且敏感档（t/T=O(1)）RK4 残差随步数**单调收敛**（O(h⁴)，粗端浮出双精度地板）。
B 🔴 **T1/T2/Tφ 一致性**：1/T2 = 1/(2T1) + 1/Tφ 反解恒等（<1e-12）；非物理输入 T2>2T1 须抛错。
C 🔴 **去极化参数口径**：p_depol = 2·E 恒等（J1 注入口径钉死）；现实档门错误率落在 ~1e-4 量级。
D 🔴 **频率限带守护（S 铁律①）**：f01∈[5.0,6.2] GHz 判 True，越界判 False（复用，不重造）。
E 🔴 **J1↔J2 复利闭环**：J2 现实物理错误率 p_phys 子阈值（<p_th）；物理标定逻辑错误率随码距 d
   指数抑制（p_L 单调↓）；阈值下余量（数量级）与 J1→J2 硬指标自洽；闭式与 J1 解码器 MC 路径一致。
F 🔴 **M2 两比特 CR 门层（净增账本锚 B506/B507）**：B506 CR 门退相干错误率（闭式 ⇄ 16×16 Liouvillian
   RK4）与 B507 残余 ZZ 诱导门错误率（闭式 (4/5)sin²(ζt/2) ⇄ 4×4 矩阵传播子 RK4）均在 DEFS tol 内、且
   残差**非零**（非代数恒等）；判据 D 残差随步数严格单调↓（O(h⁴)）；反自证桩（候选对参数扰动有响应）+
   反向探针（参数扰动 ⇒ 候选偏离 golden 必超 tol，证明 anchor 真在算）。tol/golden 一律**读自
   `BENCHMARK_DEFS` 不硬编码**（与账本判决同源，防漂移）。
G 🔴 **M3 色散读出链 + 串扰（净增账本锚 B508）**：B508 FDM 多音读出**相邻通道频谱重叠串扰比**
   闭式 X(δ;γ)=4γ²/(4γ²+δ²) ⇄ **复合 Simpson 数值积分**（sinh 换元拉平洛伦兹尾）在 DEFS tol 内、且
   残差**非零**（非代数恒等）；残差随离散档严格单调↓（粗端 >1e-12 显著放大；收敛**快于标称 O(h⁴)**，
   如实披露不虚报）；反自证桩 + 反向探针（δ 扰动 ⇒ 偏离 golden 必超 tol）。并核 **M3 能力层
   `lda_qeda/j2_readout_mux.py`** 与账本锚**同物理律**（`mux_overlap_ratio` ≡ B508 golden）、容量链单调、
   残余 ZZ 上限复用 `sc_readout`（σ_zz≤1.0 MHz · S 铁律②）、读出链**双签核**（隔离 ∧ ZZ）且反向可 REJECT。
H 🔴 **M4 QPU 误差预算集成 + 拓扑对接（净增账本锚 B509）**：B509 **QPU 耦合图代数连通度 λ₂（Fiedler 值）**
   谱定理闭式 `2−2cos(π/max(rows,cols))`（Cartesian 积 P_rows□P_cols 的 Laplacian Kronecker 和）⇄
   **嵌套 Krylov 子空间 Rayleigh–Ritz 最小值**（min-max 原理 ⇒ 单调非增上界）在 DEFS tol 内、且残差
   **非零**（非代数恒等）；残差随 Krylov 维 m 严格单调↓（粗端 >1e-12 显著放大；**末段超收敛**，如实披露
   不虚报「等比收敛」）；反自证桩 + 反向探针（cols 扰动 ⇒ 偏离 golden 必超 tol）。并核 **M4 能力层
   `lda_qeda/qpu_error_budget.py`**（QPU 级误差预算集成：1q/2q/读出/idle/ZZ 逐分量 ⇒ 每操作平均错误率
   与阈值余量）与 **`lda_qeda/topology_qec_bridge.py`**（拓扑↔表面码：λ₂ ≡ B509 golden、嵌入 DIRECT/
   ADAPTED/FAIL、资源 2d²−1、桥签核）**与账本锚同物理律**、**双签核**且反向可 REJECT。
R 🔴 **反向探针（先证能变红）**：p_phys 抬到阈值以上 ⇒ 子阈值判据必红；参数扰动（T1×1.5）须有响应。

═══ 诚实边界 ═══
· 本门禁是**能力验证**模块（`lda_qeda/physical_error_model.py` + `j2_to_j1_calibration.py`），
  **不是账本锚**；额度不进 BENCHMARK_DEFS。
· 单比特门退相干极限闭式与既有账本锚 **B10**（v0.9.24 已含 Lindblad 候选）**同式** ⇒ M0/M1 门禁
  **不新增账本锚**（同源体检：被测标量/物理构型/数值格式三者全同 = 只是换名）；M0/M1 的净增价值在
  **复利闭环桥**。🔴 **M2 已落净增锚 B506/B507**（两比特 CR 门错误率 / 残余 ZZ 错误率，见 F 节）——
  与 B10 三者均异（被测标量 1q 保真度 vs 2q 门错误率 / 物理构型 单比特 vs 两比特 CR 门 / 格式 4×4
  vs 16×16）⇒ 计新锚。J2 后续新锚应落既有锚未覆盖的物理量（M3 读出+ZZ 串扰 / M4 拓扑）。
· T1/T2/t_gate/p_th/A 为**设计示例量级**（非实测 PDK/非流片数据）；只证「闭式⇄数值」一致与
  物理桥自洽，**不作制造/性能宣称**。

═══ 与 B10 / B497 的边界 ═══
· B10 是账本**闭式保真度锚**（走 harness 判决）；本门禁覆盖**物理错误模型 + J1↔J2 桥能力**内核。
· B497 是账本**阈值距离 d\\* 锚**（反解）；本门禁是**正算逻辑错误率 p_L + 闭环标定**，两者零重叠。
"""
from __future__ import annotations

import math
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


def main() -> int:
    from lda_qeda.physical_error_model import (
        gate_fidelity_decoherence,
        gate_error_decoherence,
        gate_fidelity_lindblad_rk4,
        dephasing_time_from_T2,
        depolarizing_parameter,
        frequency_band_ok,
    )
    from lda_qeda.j2_to_j1_calibration import (
        logical_error_rate_ideal,
        logical_error_rate_decoder,
        calibration_curve,
        ideal_vs_physical,
        orders_below_threshold,
        j2_hard_target_met,
    )

    # 现实 transmon 设计档（量级取自 B10：T1=80µs/T2=60µs/门 20ns ⇒ 门误差 ~1.53e-4）
    T1, T2, T_GATE = 80.0, 60.0, 0.02

    # ----------------------------------------------------------------- A
    # 物理错误模型：闭式 ⇄ 数值 Lindblad RK4
    f_closed = gate_fidelity_decoherence(T_GATE, T1, T2)
    f_rk4 = gate_fidelity_lindblad_rk4(T_GATE, T1, T2, n_steps=256)
    rel_a1 = abs(f_rk4 - f_closed) / max(abs(f_closed), 1e-30)
    check("A1 物理错误模型：闭式 F=(3+2e^{−t/T2}+e^{−t/T1})/6 ⇄ Lindblad RK4 一致（rel=%.2e）"
          % rel_a1,
          rel_a1 < 1e-9, "closed=%.9f rk4=%.9f" % (f_closed, f_rk4))

    # 敏感档（t/T=O(1)）RK4 残差随步数单调收敛（O(h⁴)），粗端须浮出双精度地板
    t_s, T1s, T2s = 2.0, 1.0, 0.6
    g_s = gate_fidelity_decoherence(t_s, T1s, T2s)
    grid = [16, 32, 64, 128, 256]
    resid = [abs(gate_fidelity_lindblad_rk4(t_s, T1s, T2s, n_steps=n) - g_s) for n in grid]
    mono = all(resid[i + 1] < resid[i] for i in range(len(resid) - 1))
    check("A2 Lindblad RK4 收敛：残差随步数严格单调↓（O(h⁴)，比值≈16）",
          mono and resid[0] > 1e-13 and resid[-1] < 1e-6,
          "resid=%s" % " → ".join("%.2e" % r for r in resid))

    # ----------------------------------------------------------------- B
    # T1/T2/Tφ 一致性：1/T2 = 1/(2T1) + 1/Tφ
    tphi = dephasing_time_from_T2(T1, T2)
    inv_lhs = 1.0 / T2
    inv_rhs = 1.0 / (2.0 * T1) + 1.0 / tphi
    check("B1 T1/T2/Tφ 一致性：1/T2 = 1/(2T1)+1/Tφ 反解恒等（|Δ|=%.2e，Tφ=%.3fµs）"
          % (abs(inv_lhs - inv_rhs), tphi),
          abs(inv_lhs - inv_rhs) < 1e-12, "1/T2=%.6e" % inv_lhs)

    raised_b2 = False
    try:
        dephasing_time_from_T2(30.0, 80.0)   # T2=80 > 2·T1=60 ⇒ 非物理
    except ValueError:
        raised_b2 = True
    check("B2 非物理输入拦截：T2 > 2·T1（纯去相位率<0）须抛 ValueError",
          raised_b2, "T1=30,T2=80 ⇒ raise")

    # ----------------------------------------------------------------- C
    # 去极化参数口径：p_depol = 2·E
    E_real = gate_error_decoherence(T_GATE, T1, T2)
    pd = depolarizing_parameter(T_GATE, T1, T2)
    check("C1 J1 注入口径：p_depol = 2·E 恒等（F_avg=1−p/2 口径）",
          abs(pd - 2.0 * E_real) < 1e-15, "p_depol=%.6e E=%.6e" % (pd, E_real))
    check("C2 现实设计档门错误率量级：1e-5 < E < 1e-3（设计示例，非实测）",
          1e-5 < E_real < 1e-3, "E=%.6e" % E_real)

    # ----------------------------------------------------------------- D
    # 频率限带守护（S 铁律①）
    check("D1 频率限带：f01=5.5 GHz 在带内 ⇒ True", frequency_band_ok(5.5) is True, "5.5∈[5.0,6.2]")
    check("D2 频率限带：f01=4.5 / 6.5 GHz 越界 ⇒ 均 False",
          frequency_band_ok(4.5) is False and frequency_band_ok(6.5) is False, "越界 RED")

    # ----------------------------------------------------------------- E
    # J1↔J2 复利闭环
    p_phys = pd
    check("E1 J2→J1 闭环：J2 现实物理错误率子阈值（p_phys < p_th=1%%）",
          p_phys < 0.01, "p_phys=%.3e p_th=1e-2" % p_phys)

    curve = calibration_curve(p_phys, [3, 5, 7])
    pL3, pL5, pL7 = (curve[0][1], curve[1][1], curve[2][1])
    check("E2 J1 逻辑错误率随码距指数抑制：p_L(7) < p_L(5) < p_L(3)",
          pL7 < pL5 < pL3, "p_L(3)=%.3e p_L(5)=%.3e p_L(7)=%.3e" % (pL3, pL5, pL7))

    orders = orders_below_threshold(p_phys, 0.01)
    check("E3 J1→J2 硬指标：阈值下余量 %.2f 数量级（目标≥2 ⇒ %s，设计示例档）"
          % (orders, "MET" if j2_hard_target_met(p_phys, 0.01) else "NOT-MET"),
          orders > 0.0, "orders=%.3f" % orders)

    # 闭式 vs J1 解码器 MC 路径（真实物理层注入）。🔴 口径：标度式 A·(p/p_th)^((d+1)/2) 是
    # **保守上界**（toric/表面码实测解码器更优 + 噪声口径 p*2/3），故断言 MC ≤ 标度上界，
    # 而非「逼近」；MC 为仿真证据（③ 级），只证「物理错误率可注入真实解码器」这一工程事实。
    p_inj = 0.008
    p_dec = logical_error_rate_decoder(p_inj, 3, n_shots=8000, seed=7)
    p_ub = logical_error_rate_ideal(p_inj, 3)
    check("E4 物理错误率注入 J1 解码器：MC p_L(d=3) 有限、≥0 且 ≤ 闭式标度上界（标度式保守）",
          math.isfinite(p_dec) and 0.0 <= p_dec <= p_ub,
          "mc=%.3e closed_ub=%.3e" % (p_dec, p_ub))

    # 理想 vs 物理标定对照（复利：物理层比理想差 ⇒ ratio>1）
    li, lp, ratio = ideal_vs_physical(1e-4, p_phys, 5)
    check("E5 物理标定对照：p_phys>p_ideal ⇒ 逻辑错误率比 >1（ratio=%.2f）" % ratio,
          ratio > 1.0, "ideal=%.3e physical=%.3e" % (li, lp))

    # ----------------------------------------------------------------- R
    # 反向探针（先证能变红）
    p_over = 0.02                                  # 阈值以上
    oversat = logical_error_rate_ideal(p_over, 5)  # 标度失效 ⇒ 饱和 1.0
    check("R1 反向探针：p_phys 抬到阈值以上 ⇒ 子阈值判据必红（p_L 饱和=%.1f，orders<0）"
          % oversat,
          (oversat >= 1.0) and (orders_below_threshold(p_over, 0.01) < 0.0),
          "p_over=%.2f" % p_over)

    e_base = gate_error_decoherence(T_GATE, T1, T2)
    e_pert = gate_error_decoherence(T_GATE, T1 * 1.5, T2)
    check("R2 反向探针：T1×1.5 扰动 ⇒ 门错误率有可测响应（|ΔE|=%.2e > 1e-6）"
          % abs(e_pert - e_base),
          abs(e_pert - e_base) > 1e-6, "ΔE=%.3e" % abs(e_pert - e_base))

    # ----------------------------------------------------------------- F
    # M2 两比特 CR 门层（净增账本锚 B506/B507）· 闭式 golden ⇄ 数值 RK4 候选。
    # 🔴 tol/golden 一律读自 BENCHMARK_DEFS（与账本判决同源，不硬编码防漂移）。
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness._batch_j2_numeric import (
        cand_b506,
        cand_b507,
    )

    def _defs_golden(bid: str, params: dict) -> float:
        return float(BENCHMARK_DEFS[bid]["golden_fn"](**params))

    def _defs_params(bid: str, fallback: dict) -> dict:
        return dict(BENCHMARK_DEFS[bid].get("default_params") or fallback)

    # F1 / F2 —— B506 交叉谐振门退相干错误率（闭式 ⇄ 16×16 Liouvillian RK4）
    p506 = _defs_params("B506", {"T1_A": 10.0, "T1_B": 12.0,
                                 "T2_A": 8.0, "T2_B": 9.0, "t": 2.0})
    tol506 = float(BENCHMARK_DEFS["B506"]["tol"])
    g506 = _defs_golden("B506", p506)
    c506 = float(cand_b506(**p506))
    r506 = abs(c506 - g506)
    check("F1 B506 两比特 CR 门退相干错误率：闭式 ⇄ 16×16 Liouvillian RK4 一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r506, tol506),
          0.0 < r506 < tol506, "golden=%.9f cand=%.9f" % (g506, c506))

    res506 = [abs(float(cand_b506(**{**p506, "n": n})) - g506) for n in (2, 4, 8, 16)]
    mono506 = all(res506[i] > res506[i + 1] for i in range(len(res506) - 1))
    ratio506 = [res506[i] / res506[i + 1] for i in range(len(res506) - 1)]
    check("F2 B506 判据 D：RK4 残差随步数严格单调↓（O(h⁴)，粗端显著放大）",
          mono506 and res506[0] > 50.0 * res506[-1] and ratio506[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res506),
                                 "/".join("%.1f" % x for x in ratio506)))

    # F3 / F4 —— B507 残余 ZZ 诱导门错误率（闭式 (4/5)sin²(ζt/2) ⇄ 4×4 矩阵传播子 RK4）
    p507 = _defs_params("B507", {"zeta": 0.5, "t": 2.0})
    tol507 = float(BENCHMARK_DEFS["B507"]["tol"])
    g507 = _defs_golden("B507", p507)
    c507 = float(cand_b507(**p507))
    r507 = abs(c507 - g507)
    check("F3 B507 残余 ZZ 诱导门错误率：闭式 (4/5)sin²(ζt/2) ⇄ 4×4 矩阵传播子 RK4 一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r507, tol507),
          0.0 < r507 < tol507, "golden=%.9f cand=%.9f" % (g507, c507))

    res507 = [abs(float(cand_b507(**{**p507, "n": n})) - g507) for n in (2, 4, 8, 16)]
    mono507 = all(res507[i] > res507[i + 1] for i in range(len(res507) - 1))
    ratio507 = [res507[i] / res507[i + 1] for i in range(len(res507) - 1)]
    check("F4 B507 判据 D：RK4 残差随步数严格单调↓（O(h⁴)，粗端显著放大）",
          mono507 and res507[0] > 50.0 * res507[-1] and ratio507[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res507),
                                 "/".join("%.1f" % x for x in ratio507)))

    # F5 —— 反自证桩：候选必须**跟着参数走**（自证桩只 return golden，扰动则纹丝不动）
    resp506 = abs(float(cand_b506(**{**p506, "t": p506["t"] * 1.1})) - c506)
    resp507 = abs(float(cand_b507(**{**p507, "zeta": p507["zeta"] * 1.1})) - c507)
    check("F5 反自证桩：B506/B507 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp506 > 0.0 and resp507 > 0.0,
          "Δcand506(t×1.1)=%.2e Δcand507(ζ×1.1)=%.2e" % (resp506, resp507))

    # F6 —— 反向探针：参数扰动 ⇒ 候选偏离 golden **必超 tol**（证明 anchor 真在算，非恒真）
    dev506 = abs(float(cand_b506(**{**p506, "t": p506["t"] * 1.1})) - g506)
    dev507 = abs(float(cand_b507(**{**p507, "zeta": p507["zeta"] * 1.1})) - g507)
    check("F6 反向探针：B506@t / B507@zeta ×1.1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev506 > tol506 and dev507 > tol507,
          "dev506=%.2e(tol=%.1e) dev507=%.2e(tol=%.1e)" % (dev506, tol506, dev507, tol507))

    # ----------------------------------------------------------------- G
    # M3 色散读出链 + 串扰（净增账本锚 B508）· FDM 多音读出相邻通道频谱重叠串扰比。
    # 🔴 tol/golden 一律读自 BENCHMARK_DEFS（与账本判决同源，不硬编码防漂移）。
    from lda_harness._batch_j2m3_numeric import (cand_b508, B508_DEFAULT_PARAMS)
    from lda_qeda import j2_readout_mux as MUX
    from lda_qeda.sc_readout import ZZ_STRAY_LIMIT_MHZ as S4_ZZ_LIMIT

    # G1 —— B508 FDM mux 相邻通道频谱重叠串扰比（闭式 4γ²/(4γ²+δ²) ⇄ 复合 Simpson 数值积分）
    p508 = _defs_params("B508", dict(B508_DEFAULT_PARAMS))
    tol508 = float(BENCHMARK_DEFS["B508"]["tol"])
    g508 = _defs_golden("B508", p508)
    c508 = float(cand_b508(**p508))
    r508 = abs(c508 - g508)
    check("G1 B508 FDM 多音读出相邻通道频谱重叠串扰比：闭式 ⇄ 复合 Simpson 数值积分一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r508, tol508),
          0.0 < r508 < tol508, "golden=%.9f cand=%.9f" % (g508, c508))

    # G2 —— 判据 D：残差随离散档严格单调↓，粗端 >1e-12 显著放大（排除「残差与离散参数无关」指纹）
    grid508 = (32, 64, 128, 256)
    res508 = [abs(float(cand_b508(**{**p508, "n": n})) - g508) for n in grid508]
    mono508 = all(res508[i] > res508[i + 1] for i in range(len(res508) - 1))
    ratio508 = [res508[i] / res508[i + 1] for i in range(len(res508) - 1)]
    check("G2 B508 判据 D：数值残差随离散档严格单调↓（粗端 >1e-12 显著放大，非恒等）",
          mono508 and res508[0] > 1e-12 and res508[-1] < tol508 and ratio508[-1] > 2.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res508),
                                 "/".join("%.2f" % x for x in ratio508)))

    # G3 —— 反自证桩：候选必须**跟着参数走**（自证桩只 return golden，扰动则纹丝不动）
    resp508 = abs(float(cand_b508(**{**p508, "delta": p508["delta"] * 1.1})) - c508)
    check("G3 反自证桩：B508 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp508 > 0.0, "Δcand508(δ×1.1)=%.2e" % resp508)

    # G4 —— 反向探针：参数扰动 ⇒ 候选偏离 golden **必超 tol**（证明 anchor 真在算，非恒真）
    dev508 = abs(float(cand_b508(**{**p508, "delta": p508["delta"] * 1.1})) - g508)
    check("G4 反向探针：B508@δ ×1.1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev508 > tol508, "dev508=%.2e(tol=%.1e)" % (dev508, tol508))

    # G5 —— M3 能力层常驻自检（通道隔离链 + 反解自洽 + 容量单调 + ZZ 复用 + 签核良定义）
    mux_ok = MUX.run_selfchecks()
    check("G5 M3 能力层 j2_readout_mux 自检全过（隔离链 + 反解自洽 + 容量单调 + ZZ 复用 + 签核良定义）",
          mux_ok, "run_selfchecks()=%s" % mux_ok)

    # G6 —— 能力层↔账本锚**同物理律**（防漂移）+ 容量单调 + ZZ 上限复用 S4
    cap1 = MUX.mux_capacity()
    cap2 = MUX.mux_capacity(band_mhz=1000.0)
    law_d = abs(MUX.mux_overlap_ratio(p508["gamma"], p508["delta"]) - g508)
    zz = MUX.readout_zz_budget()
    check("G6 M3 能力层↔账本锚同律：mux_overlap_ratio ≡ B508 golden（|Δ|<1e-15）；容量随带宽单调不减；"
          "ZZ 上限复用 S4（σ_zz≤%.1f MHz）" % zz["zz_stray_limit_mhz"],
          law_d < 1e-15 and cap2["n_max"] >= cap1["n_max"]
          and zz["zz_stray_limit_mhz"] == S4_ZZ_LIMIT,
          "Δlaw=%.1e N1=%d N2=%d σ_zz_lim=%.1f"
          % (law_d, cap1["n_max"], cap2["n_max"], zz["zz_stray_limit_mhz"]))

    # G7 —— 读出链**双签核**：默认档 ACCEPT（隔离 ∧ σ_zz≤1.0）；反向 X_tol→0 ⇒ 必 REJECT（可证伪）
    cb_ok = MUX.readout_chain_budget()
    cb_bad = MUX.readout_chain_budget(x_tol=1e-6)
    check("G7 读出链双签核：默认档 ACCEPT（隔离 ∧ σ_zz≤1.0 MHz）；反向 X_tol→0 ⇒ 必 REJECT",
          cb_ok["verdict"] == "ACCEPT" and cb_bad["verdict"] == "REJECT",
          "ok=%s(σ_zz=%.4f) bad=%s"
          % (cb_ok["verdict"], cb_ok["zz"]["max_stray_zz_mhz"], cb_bad["verdict"]))

    # ----------------------------------------------------------------- H
    # M4 QPU 误差预算集成 + 拓扑对接（净增账本锚 B509）· QPU 耦合图代数连通度 λ₂（Fiedler 值）。
    # 🔴 tol/golden 一律读自 BENCHMARK_DEFS（与账本判决同源，不硬编码防漂移）。
    from lda_harness._batch_j2m4_numeric import (cand_b509, B509_DEFAULT_PARAMS)
    from lda_qeda import qpu_error_budget as QEB
    from lda_qeda import topology_qec_bridge as TQB
    from lda_qeda import sc_topology_core as TOPO

    # H1 —— B509 耦合图代数连通度 λ₂（谱定理闭式 2−2cos(π/max) ⇄ 嵌套 Krylov Rayleigh–Ritz）
    p509 = _defs_params("B509", dict(B509_DEFAULT_PARAMS))
    tol509 = float(BENCHMARK_DEFS["B509"]["tol"])
    g509 = _defs_golden("B509", p509)
    c509 = float(cand_b509(**p509))
    r509 = abs(c509 - g509)
    check("H1 B509 QPU 耦合图代数连通度 λ₂（Fiedler 值）：谱定理闭式 ⇄ 嵌套 Krylov Rayleigh–Ritz"
          " 一致（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r509, tol509),
          0.0 < r509 < tol509, "golden=%.9f cand=%.9f" % (g509, c509))

    # H2 —— 判据 D：残差随 Krylov 维 m 严格单调↓，粗端 >1e-12 显著放大（排除「残差与离散参数无关」指纹）
    grid509 = (4, 8, 16, 32)
    res509 = [abs(float(cand_b509(**{**p509, "m": m})) - g509) for m in grid509]
    mono509 = all(res509[i] > res509[i + 1] for i in range(len(res509) - 1))
    ratio509 = [res509[i] / res509[i + 1] for i in range(len(res509) - 1)]
    check("H2 B509 判据 D：Krylov 残差随维 m 严格单调↓（粗端 >1e-12 显著放大，非恒等）",
          mono509 and res509[0] > 1e-12 and res509[-1] < tol509 and ratio509[-1] > 2.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res509),
                                 "/".join("%.2f" % x for x in ratio509)))

    # H3 —— 反自证桩：候选必须**跟着参数走**（自证桩只 return golden，扰动则纹丝不动）
    resp509 = abs(float(cand_b509(**{**p509, "cols": p509["cols"] + 1})) - c509)
    check("H3 反自证桩：B509 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp509 > 0.0, "Δcand509(cols+1)=%.2e" % resp509)

    # H4 —— 反向探针：参数扰动 ⇒ 候选偏离 golden **必超 tol**（证明 anchor 真在算，非恒真）
    dev509 = abs(float(cand_b509(**{**p509, "cols": p509["cols"] + 1})) - g509)
    check("H4 反向探针：B509@cols +1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev509 > tol509, "dev509=%.2e(tol=%.1e)" % (dev509, tol509))

    # H5 —— M4 能力层常驻自检①：QPU 误差预算集成（分量律 / 集成口径 / 余量方向 / 签核二值 / 反向）
    qeb_ok = QEB.run_selfchecks()
    check("H5 M4 能力层 qpu_error_budget 自检全过（1q/2q/读出/idle/ZZ 分量律 + 集成口径 + 反向）",
          qeb_ok, "run_selfchecks()=%s" % qeb_ok)

    # H6 —— M4 能力层常驻自检②：拓扑↔表面码对接桥（方阵 λ₂ 闭式一致 / 连通性 / 嵌入 / 资源 / 反向）
    tqb_ok = TQB.run_selfchecks()
    check("H6 M4 能力层 topology_qec_bridge 自检全过（λ₂ 闭式一致 + 嵌入判定 + 资源 + 反向）",
          tqb_ok, "run_selfchecks()=%s" % tqb_ok)

    # H7 —— 能力层↔账本锚**同物理律**（防漂移）+ λ₂ 随图规模单调不增
    g10 = TOPO.grid_topology(10, 10)
    g3 = TOPO.grid_topology(3, 3)
    lam10 = TQB.topology_lambda2(g10, m=32)
    law_rel = abs(lam10 - g509) / abs(g509)
    check("H7 M4 能力层↔账本锚同律：topology_lambda2(方阵10×10) ≡ B509 golden（rel<1e-8）；"
          "λ₂ 随图规模单调不增",
          law_rel < 1e-8 and TQB.topology_lambda2(g3, m=8) >= lam10,
          "λ₂(10×10)=%.9f golden=%.9f rel=%.2e λ₂(3×3)=%.6f"
          % (lam10, g509, law_rel, TQB.topology_lambda2(g3, m=8)))

    # H8 —— QPU 误差预算**双签核**：默认档 ACCEPT（余量>0 ∧ ZZ 在限内）；反向 T1/T2 ÷10 ⇒ 必 REJECT
    qb_ok = QEB.qpu_cycle_error_budget()
    qb_bad = QEB.qpu_cycle_error_budget({"T1_s": 80e-6 / 10.0, "T2_s": 60e-6 / 10.0})
    check("H8 QPU 误差预算双签核：默认档 ACCEPT（余量=%.2e>0 ∧ σ_zz=%.4f≤%.1f MHz）；"
          "反向 T1/T2÷10 ⇒ 必 REJECT" % (qb_ok["threshold_margin"], qb_ok["zeta_zz_mhz"],
                                        qb_ok["zeta_limit_mhz"]),
          qb_ok["verdict"] == "ACCEPT" and qb_ok["zz_within_limit"]
          and qb_bad["verdict"] == "REJECT",
          "ok=%s(margin=%.2e σ_zz=%.4f) bad=%s(margin=%.2e)"
          % (qb_ok["verdict"], qb_ok["threshold_margin"], qb_ok["zeta_zz_mhz"],
             qb_bad["verdict"], qb_bad["threshold_margin"]))

    # H9 —— 拓扑↔QEC 桥：方阵 10×10 d=3 ⇒ ACCEPT/DIRECT；heavy-hex 3×3 d=3 ⇒ ACCEPT/ADAPTED
    h3 = TOPO.heavy_hex_topology(3, 3)
    bv_g = TQB.bridge_verdict(g10, d=3)
    bv_h = TQB.bridge_verdict(h3, d=3)
    check("H9 拓扑↔QEC 桥签核：方阵 10×10 d=3 ⇒ ACCEPT/DIRECT；heavy-hex 3×3 d=3 ⇒ ACCEPT/ADAPTED",
          bv_g["verdict"] == "ACCEPT" and bv_g["embedding"] == "DIRECT"
          and bv_h["verdict"] == "ACCEPT" and bv_h["embedding"] == "ADAPTED",
          "grid=%s/%s(N=%d) hex=%s/%s(N=%d)"
          % (bv_g["verdict"], bv_g["embedding"], bv_g["graph"]["n_nodes"],
             bv_h["verdict"], bv_h["embedding"], bv_h["graph"]["n_nodes"]))

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("J2 QPU 物理错误模型 + J1↔J2 复利闭环门禁：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
