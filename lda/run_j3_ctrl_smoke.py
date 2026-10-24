#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J3 量子测控与读出征程 · M0/M1 常驻门禁（时域驱动脉冲 + DRAG 泄漏抑制 + 测控闭环）。

═══ 判什么（分节）═══
A 🔴 **M0 时域驱动脉冲（净增账本锚 B510）**：B510 **广义 Rabi 时域布居**
   P₁=(Ω²/Ω_R²)sin²(Ω_R t/2)（二能级 RWA 常矩阵哈密顿的**精确解析解**）⇄ **时域 TDSE
   四阶 RK4 态矢推进** —— 在 DEFS tol 内、且残差**非零**（非代数恒等）；判据 D 残差随步数
   严格单调↓（O(h⁴)，粗端 >1e-12 显著放大）；反自证桩（候选对参数扰动有响应）+ 反向探针
   （参数扰动 ⇒ 候选偏离 golden 必超 tol，证明 anchor 真在算）；防回退（candidate 键指向
   本批新候选）。🔴 tol/golden 一律**读自 `BENCHMARK_DEFS` 不硬编码**（与账本判决同源）。
B 🔴 **M1 DRAG 泄漏抑制（净增账本锚 B511）**：B511 **三能级 transmon 驱动泄漏布居**
   （特征多项式 λ³−αλ²−(3Ω²/4)λ+αΩ²/4=0 的 **depressed-cubic 三角法精确谱闭式**）⇄
   **时域 RK4 三能级态矢推进** —— 同上五项。
C 🔴 **能力层常驻自检**：`lda_qeda/pulse_library.py`（包络/导数闭式 + 面积线性 + 定标反解 +
   频率限带）· `lda_qeda/qubit_dynamics.py`（常/含时 RK4 精度 + 物理极限 + DRAG 抑制趋势 +
   **极限行为纠正**）· `lda_qeda/control_closed_loop.py`（闭环几何收敛 + 标定不变量 +
   **捕获范围守卫** + 读出误判链 + 签核二值）。
D 🔴 **能力层↔账本锚同物理律**（防漂移）：`qubit_dynamics.rabi_population` ≡ B510 golden；
   `qubit_dynamics.qutrit_leakage` ≡ B511 golden（rel 判据）；**测控闭环可用性**：
   `control_loop_report()` 默认档 ACCEPT（定标收敛 ∧ DRAG 泄漏达标 ∧ 读出误判达标），
   反向 SNR 取到荒谬小 ⇒ 必 REJECT（可证伪）；捕获范围外（θ₀>π）⇒ 显式 diverged（不静默溢出）。
E 🔴 **跨模块口径与边界**：读出误判 `½erfc(SNR/√2)` 与 D-47 `lda_agent.readout_fidelity`
   的 `eps` **同源**（数值逐位一致）；tol 与 `_batch_j3_numeric` 三表同值（防两处漂移）；
   主权边界机械可核（零量子 SDK）。
F 🔴 **M2 门保真标定（净增账本锚 B512）**：B512 **去极化信道纯度衰减（二阶 unitarity）**
   P=(1+e^{−2Γt})/2（Bloch 线性 ODE 的**精确指数闭式**）⇄ **密度矩阵 Liouvillian 四阶
   RK4** —— 同 A 五项，tol=1e-7。
G 🔴 **M3 读出链（净增账本锚 B513）**：B513 **Purcell 滤波器抑制比** S=1/|S21(f_q)|²
   （并联开路 λ/4 短截线 **ABCD 代数闭式**）⇄ **导纳 ODE 四阶 RK4** —— 同五项，tol=1e-6。
H 🔴 **M4 低温电子学（净增账本锚 B514）**：B514 **分布式相位不敏感放大链附加噪声**
   n_add=(η/g)(1−e^{−gL})（**解析闭式**；gL→∞ ⇒ Caves 极限 1/2）⇄ **复合 Simpson 求积**
   —— 同五项，tol=1e-6。
I 🔴 **M2/M3/M4 能力层常驻自检**：`rb_benchmark`（Clifford 24 元 + u=p² + 纯度衰减 +
   相干分解）· `readout_demod`（erfc 口径 + 匹配滤波 + 分配矩阵 + Purcell）·
   `cryo_electronics`（Caves 极限 + Friis + cryo-CMOS）· `control_closed_loop`
   **测控闭环总装**（脉冲→门→读出→反馈→低温电子学，五段全 ACCEPT + 回写规格）。
J 🔴 **能力层↔账本锚同物理律 + 总装可证伪**：`rb_benchmark` 纯度 ≡ B512 · `readout_demod`
   Purcell ≡ B513 · `cryo_electronics` 分布式噪声 ≡ B514（三处逐位一致）；总装反向 SNR=0.5
   ⇒ REJECT。
K 🔴 **三表一致（五锚）**：`_TOL_BY_BID` 与 BENCHMARK_DEFS tol 同值。

═══ 诚实边界 ═══
· 本门禁覆盖 **M0–M4 全档**（章程 §3）；WebUI 面板 `/api/j3_ctrl` 属 **M4 交付项**（章程 §2.4）
  由独立 `run_webui_j3_render_path_smoke` 覆盖（不在本门禁内）。
· Ω/α/δ/Γ/t/σ/β/g/L/f_q/f_s/SNR 均为**设计示例量级**（非实测 PDK / 非流片 / 非任意波形
  发生器标定）；三能级模型未建模 |3⟩+ 高阶能级、驱动线非线性、T1/T2 退相干（属 J2
  `physical_error_model`）。
· 只证「闭式 ⇄ 数值」一致 + 测控物理链自洽，**不作制造/性能宣称**，不报能效/TOPS/fJ-op。
· 零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）；LLM 不进判决路径。
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

# 🔴 关键模块**模块级**导入（不是 main() 内局部导入）—— 突变探针 `scripts/d154_j3_probe.py`
#   正是 patch 这几个**同一模块对象**；若改成 main 内 `from x import f`，探针会 patch 到
#   另一个绑定 ⇒ 打空 ⇒ 假绿（本仓 M-121 血案：探针必须打门禁同一模块对象）。
from lda_harness import _batch_j3_numeric as J3  # noqa: E402
from lda_qeda import pulse_library as PL  # noqa: E402
from lda_qeda import qubit_dynamics as QD  # noqa: E402
from lda_qeda import control_closed_loop as CC  # noqa: E402
from lda_qeda import rb_benchmark as RB  # noqa: E402
from lda_qeda import readout_demod as RD  # noqa: E402
from lda_qeda import cryo_electronics as CE  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")



# ===========================================================================
# N2 · 超导域判据深度：门禁运行时登记（v0.9.282）
# ---------------------------------------------------------------------------
# 本门禁**真的执行**账本锚（harness 统一判决：闭式 golden vs 已注册候选），
# 不是"为刷覆盖写锚号"（见 N2 规划 §1.3 的反例）。
# 登记面走 `asserted_anchor_ids()`（scripts/gate_manifest.py 消费），
# 由末尾 H7 **双向锁死**：声明集 ≡ 本次运行实际断言集 ⇒ 删掉执行代码必红。
# 🔴 本段只用 print + 退出码，**不增加门禁判据数**（护住 `run_webui_*` 的
#    「N PASS == span.gate_checks」自洽判据）。
# ===========================================================================
ASSERTED_ANCHORS = ('B18',)
_RUNTIME_ASSERTED: list = []


def asserted_anchor_ids():
    """本门禁运行时实际断言的锚集（未运行则回落到声明面）。"""
    return tuple(_RUNTIME_ASSERTED) or tuple(ASSERTED_ANCHORS)


def _run_ledger_anchor(bid):
    """真跑一条账本锚（golden 与已注册候选均由 harness 解析）。"""
    from lda_harness.verification_adapters import build_harness_specs
    from lda_harness.verification_spec import run_verification
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == bid][0]
    ov = sp.oracle_fn(sp.params)
    cv = cand[bid](sp, ov)
    return sp, run_verification(sp, cand[bid], oracle_value=ov), float(cv), float(ov)


def main() -> int:
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_agent.readout_fidelity import readout_fidelity

    def _defs_golden(bid: str, params: dict) -> float:
        return float(BENCHMARK_DEFS[bid]["golden_fn"](**params))

    def _defs_params(bid: str, fallback: dict) -> dict:
        return dict(BENCHMARK_DEFS[bid].get("default_params") or fallback)

    # ----------------------------------------------------------------- A
    # M0 时域驱动脉冲（净增账本锚 B510）· 广义 Rabi 时域布居。
    p510 = _defs_params("B510", dict(J3.B510_DEFAULT_PARAMS))
    tol510 = float(BENCHMARK_DEFS["B510"]["tol"])
    grid510 = (8, 16, 32, 64, 128)
    g510 = _defs_golden("B510", p510)
    c510 = float(J3.cand_b510(**p510))
    r510 = abs(c510 - g510)
    check("A1 B510 广义 Rabi 时域布居：RWA 常矩阵精确解析闭式 ⇄ 时域 TDSE 四阶 RK4 一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r510, tol510),
          0.0 < r510 < tol510, "golden=%.9f cand=%.9f" % (g510, c510))

    res510 = [abs(float(J3.cand_b510(**{**p510, "n": n})) - g510) for n in grid510]
    mono510 = all(res510[i] > res510[i + 1] for i in range(len(res510) - 1))
    ratio510 = [res510[i] / res510[i + 1] for i in range(len(res510) - 1)]
    check("A2 B510 判据 D：RK4 残差随步数严格单调↓（O(h⁴)，粗端 >1e-12 显著放大）",
          mono510 and res510[0] > 1e-12 and res510[-1] < tol510 and ratio510[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res510),
                                 "/".join("%.1f" % x for x in ratio510)))

    resp510 = abs(float(J3.cand_b510(**{**p510, "Omega": p510["Omega"] * 1.1})) - c510)
    check("A3 反自证桩：B510 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp510 > 0.0, "Δcand510(Ω×1.1)=%.2e" % resp510)

    dev510 = abs(float(J3.cand_b510(**{**p510, "Omega": p510["Omega"] * 1.1})) - g510)
    check("A4 反向探针：B510@Ω ×1.1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev510 > tol510, "dev510=%.2e(tol=%.1e)" % (dev510, tol510))

    cand_key510 = str(BENCHMARK_DEFS["B510"].get("candidate"))
    check("A5 防回退：B510 candidate 键指向本批新候选（非自证桩占位）",
          cand_key510 == "b510_rabi_population_cand", "candidate=%s" % cand_key510)

    # ----------------------------------------------------------------- B
    # M1 DRAG 泄漏抑制（净增账本锚 B511）· 三能级驱动泄漏布居。
    p511 = _defs_params("B511", dict(J3.B511_DEFAULT_PARAMS))
    tol511 = float(BENCHMARK_DEFS["B511"]["tol"])
    grid511 = (16, 32, 64, 128, 256)
    g511 = _defs_golden("B511", p511)
    c511 = float(J3.cand_b511(**p511))
    r511 = abs(c511 - g511)
    check("B1 B511 三能级驱动泄漏布居：depressed-cubic 三角法精确谱闭式 ⇄ 时域 RK4 一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r511, tol511),
          0.0 < r511 < tol511, "golden=%.9f cand=%.9f" % (g511, c511))

    res511 = [abs(float(J3.cand_b511(**{**p511, "n": n})) - g511) for n in grid511]
    mono511 = all(res511[i] > res511[i + 1] for i in range(len(res511) - 1))
    ratio511 = [res511[i] / res511[i + 1] for i in range(len(res511) - 1)]
    check("B2 B511 判据 D：RK4 残差随步数严格单调↓（O(h⁴)，粗端 >1e-12 显著放大）",
          mono511 and res511[0] > 1e-12 and res511[-1] < tol511 and ratio511[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res511),
                                 "/".join("%.1f" % x for x in ratio511)))

    resp511 = abs(float(J3.cand_b511(**{**p511, "alpha": p511["alpha"] * 1.1})) - c511)
    check("B3 反自证桩：B511 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp511 > 0.0, "Δcand511(α×1.1)=%.2e" % resp511)

    dev511 = abs(float(J3.cand_b511(**{**p511, "alpha": p511["alpha"] * 1.1})) - g511)
    check("B4 反向探针：B511@α ×1.1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev511 > tol511, "dev511=%.2e(tol=%.1e)" % (dev511, tol511))

    cand_key511 = str(BENCHMARK_DEFS["B511"].get("candidate"))
    check("B5 防回退：B511 candidate 键指向本批新候选（非自证桩占位）",
          cand_key511 == "b511_qutrit_leakage_cand", "candidate=%s" % cand_key511)

    # ----------------------------------------------------------------- C
    # 能力层常驻自检（三模块）。
    pl_ok = PL.run_selfchecks()
    qd_ok = QD.run_selfchecks()
    cc_ok = CC.run_selfchecks()
    check("C1 能力层 pulse_library 自检全过（包络/导数闭式 + 面积线性 + 定标反解 + 限带二值）",
          bool(pl_ok), "run_selfchecks()=%s" % pl_ok)
    check("C2 能力层 qubit_dynamics 自检全过（RK4 精度 + 物理极限 + DRAG 抑制 + 极限行为纠正）",
          bool(qd_ok), "run_selfchecks()=%s" % qd_ok)
    check("C3 能力层 control_closed_loop 自检全过（闭环收敛 + 标定不变量 + 捕获范围 + 签核二值）",
          bool(cc_ok), "run_selfchecks()=%s" % cc_ok)

    # ----------------------------------------------------------------- D
    # 能力层↔账本锚同物理律 + 测控闭环可用性。
    law510 = abs(QD.rabi_population(p510["Omega"], p510["delta"], p510["t"],
                                    n=4096) - g510) / abs(g510)
    law511 = abs(QD.qutrit_leakage(p511["Omega"], p511["alpha"], p511["t"],
                                   n=8192) - g511) / abs(g511)
    check("D1 能力层↔账本锚同律：rabi_population ≡ B510 golden（rel=%.2e<1e-8）；"
          "qutrit_leakage ≡ B511 golden（rel=%.2e<1e-6）" % (law510, law511),
          law510 < 1e-8 and law511 < 1e-6, "law510=%.2e law511=%.2e" % (law510, law511))

    amp = PL.calibrate_amplitude()
    pl_off = QD.drag_leakage(beta=0.0, amplitude=amp)
    pl_on = QD.drag_leakage(beta=1.0, amplitude=amp)
    ratio = QD.leakage_suppression_ratio()
    beta_star = QD.drag_optimal_beta()
    check("D2 DRAG 泄漏抑制：P_leak(无 DRAG)=%.4e → P_leak(DRAG)=%.4e（抑制比 %.2f×，"
          "最优 β*=%.2f）" % (pl_off, pl_on, ratio, beta_star),
          pl_on < pl_off and ratio > 1.0 and beta_star in (0.0, 0.25, 0.5, 0.75,
                                                          1.0, 1.25, 1.5, 2.0),
          "off=%.4e on=%.4e L=%.2f" % (pl_off, pl_on, ratio))

    rep = CC.control_loop_report()
    check("D3 测控闭环可用性（ACCEPT）：Ring A 定标收敛 %d 迭代 · Ring B 泄漏 %.3e<%.0e · "
          "Ring C 误判 %.2e" % (rep["ring_a"]["iterations"],
                                rep["ring_b"]["p_leak_with_drag"],
                                rep["ring_b"]["leakage_limit"],
                                rep["ring_c"]["readout_error"]),
          rep["verdict"] == "ACCEPT" and rep["ring_a"]["converged"]
          and rep["ring_b"]["within_limit"] and rep["ring_c"]["within_limit"],
          "verdict=%s" % rep["verdict"])

    rep_bad = CC.control_loop_report(snr=0.5)
    ra_out = CC.rabi_amplitude_calibrate(true_gain=2.5)
    check("D4 闭环反向可证伪：SNR=0.5 ⇒ REJECT；捕获范围外（θ₀=4.0>π，g=2.5）⇒ "
          "显式 diverged 且不静默溢出",
          rep_bad["verdict"] == "REJECT" and ra_out["diverged"] is True
          and ra_out["converged"] is False and math.isfinite(ra_out["omega"]),
          "bad=%s diverged=%s" % (rep_bad["verdict"], ra_out["diverged"]))

    # ----------------------------------------------------------------- E
    # 跨模块口径 + 三表一致 + 诚实边界可核。
    snr_probe = 5.0
    check("E1a 读出误判链自洽：ε(SNR=5) = ½erfc(5/√2) = %.3e"
          % CC.readout_error_probability(snr_probe),
          abs(CC.readout_error_probability(snr_probe)
              - 0.5 * math.erfc(snr_probe / math.sqrt(2.0))) < 1e-18,
          "ε=%.15e" % CC.readout_error_probability(snr_probe))
    # D-47 的 eps 由其内部 SNR 决定 ⇒ 反解其 SNR 后用本模块同式重算，核 erfc 口径同源。
    # 🔴 参数须让 SNR 落在 O(1)（否则 eps→0 的退化解会让比较变成「0==0」而无信息量）。
    b_d47 = readout_fidelity(0.01, 0.005, 1.0, 1.0, 5.0, 8.75e-8, 100.0)
    eps_d47 = float(b_d47["eps"])
    eps_ours = CC.readout_error_probability(float(b_d47["snr"]))
    check("E1b 跨模块口径同源：control_closed_loop 读出误判 ≡ D-47 readout_fidelity 的 ε"
          "（同 SNR 下逐位一致，|Δ|=%.2e）" % abs(eps_d47 - eps_ours),
          abs(eps_d47 - eps_ours) < 1e-15,
          "ε(D-47)=%.15e ε(本模块)=%.15e" % (eps_d47, eps_ours))

    check("E2 三表一致：`_TOL_BY_BID` 与 BENCHMARK_DEFS tol 同值（防两处漂移）",
          float(J3._TOL_BY_BID["B510"]) == float(BENCHMARK_DEFS["B510"]["tol"])
          and float(J3._TOL_BY_BID["B511"]) == float(BENCHMARK_DEFS["B511"]["tol"]),
          "B510 %.1e/%.1e B511 %.1e/%.1e"
          % (J3._TOL_BY_BID["B510"], BENCHMARK_DEFS["B510"]["tol"],
             J3._TOL_BY_BID["B511"], BENCHMARK_DEFS["B511"]["tol"]))

    src = open(os.path.join(_HERE, "lda_qeda", "qubit_dynamics.py"), encoding="utf-8").read()
    check("E3 主权/边界机械可核：能力层源码零量子 SDK 依赖（qiskit/cirq/pennylane/qutip）",
          all(k not in src for k in ("qiskit", "cirq", "pennylane", "qutip")),
          "qubit_dynamics 源码零量子 SDK 命中")

    # ----------------------------------------------------------------- F
    # M2 门保真标定（净增账本锚 B512）· 去极化信道纯度衰减（二阶 unitarity）。
    p512 = _defs_params("B512", dict(J3.B512_DEFAULT_PARAMS))
    tol512 = float(BENCHMARK_DEFS["B512"]["tol"])
    grid512 = (4, 8, 16, 32, 64)
    g512 = _defs_golden("B512", p512)
    c512 = float(J3.cand_b512(**p512))
    r512 = abs(c512 - g512)
    check("F1 B512 去极化信道纯度衰减 unitarity：精确指数闭式 (1+e^{−2Γt})/2 ⇄ 密度矩阵"
          " Liouvillian 四阶 RK4 一致（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r512, tol512),
          0.0 < r512 < tol512, "golden=%.9f cand=%.9f" % (g512, c512))
    res512 = [abs(float(J3.cand_b512(**{**p512, "n": n})) - g512) for n in grid512]
    mono512 = all(res512[i] > res512[i + 1] for i in range(len(res512) - 1))
    ratio512 = [res512[i] / res512[i + 1] for i in range(len(res512) - 1)]
    check("F2 B512 判据 D：RK4 残差随步数严格单调↓（O(h⁴)，粗端 >1e-12 显著放大）",
          mono512 and res512[0] > 1e-12 and res512[-1] < tol512 and ratio512[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res512),
                                 "/".join("%.1f" % x for x in ratio512)))
    resp512 = abs(float(J3.cand_b512(**{**p512, "Gamma": p512["Gamma"] * 1.1})) - c512)
    check("F3 反自证桩：B512 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp512 > 0.0, "Δcand512(Γ×1.1)=%.2e" % resp512)
    dev512 = abs(float(J3.cand_b512(**{**p512, "Gamma": p512["Gamma"] * 1.1})) - g512)
    check("F4 反向探针：B512@Γ ×1.1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev512 > tol512, "dev512=%.2e(tol=%.1e)" % (dev512, tol512))
    cand_key512 = str(BENCHMARK_DEFS["B512"].get("candidate"))
    check("F5 防回退：B512 candidate 键指向本批新候选（非自证桩占位）",
          cand_key512 == "b512_unitarity_purity_cand", "candidate=%s" % cand_key512)

    # ----------------------------------------------------------------- G
    # M3 读出链（净增账本锚 B513）· Purcell 滤波器抑制比。
    p513 = _defs_params("B513", dict(J3.B513_DEFAULT_PARAMS))
    tol513 = float(BENCHMARK_DEFS["B513"]["tol"])
    grid513 = (64, 128, 256, 512, 1024)
    g513 = _defs_golden("B513", p513)
    c513 = float(J3.cand_b513(**p513))
    r513 = abs(c513 - g513)
    check("G1 B513 Purcell 滤波器抑制比：ABCD 代数闭式 1/|S21|² ⇄ 导纳 ODE 四阶 RK4"
          " 数值积分一致（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r513, tol513),
          0.0 < r513 < tol513, "golden=%.9f cand=%.9f" % (g513, c513))
    res513 = [abs(float(J3.cand_b513(**{**p513, "n": n})) - g513) for n in grid513]
    mono513 = all(res513[i] > res513[i + 1] for i in range(len(res513) - 1))
    ratio513 = [res513[i] / res513[i + 1] for i in range(len(res513) - 1)]
    check("G2 B513 判据 D：RK4 残差随步数严格单调↓（O(h⁴)，粗端 >1e-12 显著放大）",
          mono513 and res513[0] > 1e-12 and res513[-1] < tol513 and ratio513[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res513),
                                 "/".join("%.1f" % x for x in ratio513)))
    resp513 = abs(float(J3.cand_b513(**{**p513, "f_q": p513["f_q"] * 1.02})) - c513)
    check("G3 反自证桩：B513 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp513 > 0.0, "Δcand513(f_q×1.02)=%.2e" % resp513)
    dev513 = abs(float(J3.cand_b513(**{**p513, "f_q": p513["f_q"] * 1.02})) - g513)
    check("G4 反向探针：B513@f_q ×1.02 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev513 > tol513, "dev513=%.2e(tol=%.1e)" % (dev513, tol513))
    cand_key513 = str(BENCHMARK_DEFS["B513"].get("candidate"))
    check("G5 防回退：B513 candidate 键指向本批新候选（非自证桩占位）",
          cand_key513 == "b513_purcell_suppression_cand", "candidate=%s" % cand_key513)

    # ----------------------------------------------------------------- H
    # M4 低温电子学（净增账本锚 B514）· 分布式相位不敏感放大链附加噪声（Caves 极限）。
    p514 = _defs_params("B514", dict(J3.B514_DEFAULT_PARAMS))
    tol514 = float(BENCHMARK_DEFS["B514"]["tol"])
    grid514 = (16, 32, 64, 128, 256)
    g514 = _defs_golden("B514", p514)
    c514 = float(J3.cand_b514(**p514))
    r514 = abs(c514 - g514)
    check("H1 B514 分布式放大链附加噪声：解析闭式 (η/g)(1−e^{−gL}) ⇄ 复合 Simpson 求积"
          "一致（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r514, tol514),
          0.0 < r514 < tol514, "golden=%.9f cand=%.9f" % (g514, c514))
    res514 = [abs(float(J3.cand_b514(**{**p514, "n": n})) - g514) for n in grid514]
    mono514 = all(res514[i] > res514[i + 1] for i in range(len(res514) - 1))
    ratio514 = [res514[i] / res514[i + 1] for i in range(len(res514) - 1)]
    check("H2 B514 判据 D：Simpson 残差随步数严格单调↓（O(h⁴)，粗端 >1e-12 显著放大）",
          mono514 and res514[0] > 1e-12 and res514[-1] < tol514 and ratio514[-1] > 8.0,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res514),
                                 "/".join("%.1f" % x for x in ratio514)))
    resp514 = abs(float(J3.cand_b514(**{**p514, "g": p514["g"] * 1.1})) - c514)
    check("H3 反自证桩：B514 候选对参数扰动有物理响应（非 return-golden 桩）",
          resp514 > 0.0, "Δcand514(g×1.1)=%.2e" % resp514)
    dev514 = abs(float(J3.cand_b514(**{**p514, "g": p514["g"] * 1.1})) - g514)
    check("H4 反向探针：B514@g ×1.1 扰动 ⇒ |cand−golden| 必超 tol（可证伪）",
          dev514 > tol514, "dev514=%.2e(tol=%.1e)" % (dev514, tol514))
    cand_key514 = str(BENCHMARK_DEFS["B514"].get("candidate"))
    check("H5 防回退：B514 candidate 键指向本批新候选（非自证桩占位）",
          cand_key514 == "b514_amp_noise_cand", "candidate=%s" % cand_key514)

    # ----------------------------------------------------------------- I
    # 能力层常驻自检（M2/M3/M4 三模块 + 测控闭环总装）。
    check("I1 能力层 rb_benchmark 自检全过（Clifford 24 元 + u=p² + 纯度衰减 + 相干分解）",
          bool(RB.run_selfchecks()), "run_selfchecks()=%s" % RB.run_selfchecks())
    check("I2 能力层 readout_demod 自检全过（erfc 口径 + 匹配滤波 + 分配矩阵 + Purcell）",
          bool(RD.run_selfchecks()), "run_selfchecks()=%s" % RD.run_selfchecks())
    check("I3 能力层 cryo_electronics 自检全过（Caves 极限 + Friis + cryo-CMOS 权衡）",
          bool(CE.run_selfchecks()), "run_selfchecks()=%s" % CE.run_selfchecks())
    full = CC.full_control_loop_report()
    check("I4 测控闭环总装 ACCEPT（脉冲→门→读出→反馈→低温电子学 五段全 ACCEPT + 回写规格）",
          full["verdict"] == "ACCEPT" and len(full["spec"]) == 8,
          "verdict=%s spec_keys=%d" % (full["verdict"], len(full["spec"])))

    # ----------------------------------------------------------------- J
    # 能力层↔账本锚同物理律（防漂移，三新锚）。
    law512 = abs(RB.purity_decay_analytic(1, p512["Gamma"]) - J3.golden_b512(p512["Gamma"], 1.0))
    law513 = abs(RD.purcell_suppression(p513["f_q"], p513["f_s"], p513["z_ratio"]) - g513)
    law514 = abs(CE.distributed_amp_nadd(p514["eta_ratio"], p514["g"], p514["L"]) - g514)
    check("J1 能力层↔锚同律：rb_benchmark 纯度 ≡ B512（|Δ|=%.2e）；readout_demod Purcell ≡ "
          "B513（|Δ|=%.2e）；cryo_electronics 分布式噪声 ≡ B514（|Δ|=%.2e）"
          % (law512, law513, law514),
          law512 < 1e-15 and law513 < 1e-15 and law514 < 1e-15,
          "law512=%.2e law513=%.2e law514=%.2e" % (law512, law513, law514))
    check("J2 总装回写规格八键齐备（脉冲幅度/β*/p/u/阈值/误判/抑制比/附加噪声）",
          all(k in full["spec"] for k in
              ("pulse_amplitude", "drag_beta", "gate_fidelity_param_p", "unitarity",
               "readout_threshold", "readout_error", "purcell_suppression",
               "amp_added_noise")), "spec=%s" % sorted(full["spec"]))
    check("J3 总装反向可证伪：SNR=0.5 ⇒ 总装 REJECT",
          CC.full_control_loop_report(snr=0.5)["verdict"] == "REJECT",
          "snr=0.5 ⇒ REJECT")

    # ----------------------------------------------------------------- K
    # 三表一致（五锚）。
    check("K1 三表一致：`_TOL_BY_BID` 与 BENCHMARK_DEFS tol 同值（五锚防漂移）",
          all(float(J3._TOL_BY_BID[b]) == float(BENCHMARK_DEFS[b]["tol"])
              for b in ("B510", "B511", "B512", "B513", "B514")),
          "tol=%s" % {b: J3._TOL_BY_BID[b] for b in ("B510", "B511", "B512", "B513", "B514")})

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("J3 量子测控与读出（M0–M4：脉冲 + DRAG + unitarity + 读出链 + 低温电子学 + 闭环总装）"
          "门禁：%d PASS / %d FAIL" % (good, bad))
    # ── N2（v0.9.282）：账本锚真跑 + 运行时登记（H7 双向锁死）──
    _sp, _res, _cv, _ov = _run_ledger_anchor('B18')
    if bool(_res.passed):
        _RUNTIME_ASSERTED.append('B18')
    _h7 = tuple(_RUNTIME_ASSERTED) == tuple(ASSERTED_ANCHORS)
    print("  [%s] 账本锚 %s 真跑：残差=%.3e tol=%s"
          % ("PASS" if _res.passed else "FAIL", 'B18',
             abs(_cv - _ov), _sp.tol))
    print("  [%s] H7 声明面 ≡ 运行时断言集 —— 声明=%s 运行=%s"
          % ("PASS" if _h7 else "FAIL", ASSERTED_ANCHORS, tuple(_RUNTIME_ASSERTED)))
    _n2_ok = bool(_res.passed) and _h7
    return 0 if (bad == 0 and _n2_ok) else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
