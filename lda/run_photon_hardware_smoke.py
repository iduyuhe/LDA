"""光子硬件物理门禁 smoke（D-114/115/116 · 源/探测/开放系统的凭据守护）。

═══ 为什么要有这个 smoke ═══
D-114（单光子源）/ D-115（SNSPD 探测）/ D-116（多模 Lindblad 开放系统）一次性把 LDA-Q3b
从「理想酉」推进到「真实光子硬件」，三块都**必须**有常驻护栏：

  ① **闭式物理律锚**：HBT g²(0)（|1⟩=0/相干=1/热光=2）、SPDC 二项分布、on/off 响应
     1−(1−η)ⁿ、PNR 二项、损耗布居二项、相干态保真 exp(−|α|²(1−√η)²)、纠缠保真度。
     若有人把分束器相位/归一化/Kraus 约定改错，这些闭式立刻失真 ⇒ 必须钉成断言。
  ② **方法学独立**：每条物理都用**结构不同**的两/三条算法交叉验证（见各模块 docstring）：
     · 源：闭式解析 × 压缩算符矩阵指数；       · 探测：闭式二项 × 永久式玻色振幅(Stinespring)；
     · 开放系统：全空间 ODE × 逐模张量收缩 × 全空间嵌入 Kraus。
     🔴 本批实测被三法逮住两个真 bug（记录在案，防复发）：
       (i) on/off 预告误写 Σ_{i≥1,i'≥1}（非对角部分迹）⇒ 得秩 1 纯态（应 Σ_{i≥1} 对角）；
       (ii) 逐模通道误用 np.kron(M₀,M₁,…) ⇒ 行主序 vec 索引序不符 ⇒ 与 ODE 差 2.2e-1。
     ⇒ 自检**必须**覆盖这些结构性陷阱（多模/多光子），不能只测单模双光子。
  ③ **反自证桩**：on/off（阈值）与 PNR 是**不同**探测器 —— 前者 η=1 时对 |1⟩/|2⟩ 都响应 1
     （丢光子数信息），后者可分辨。若两者被写成同一个模型，本 smoke 必须红。

═══ 判什么（分四节 · 25 条）═══
A 源（D-114）8 条 · B 探测（D-115）7 条 · C 开放系统（D-116）7 条 · D 跨模块+红线 4 条。

运行：python run_photon_hardware_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 统一命名空间：用 `lda_qeda.*` 导入（与各物理模块内部一致 ⇒ 防同一文件双实例）
try:
    from lda_qeda import photon_sources as PS
    from lda_qeda import detectors as DT
    from lda_qeda import open_system as OS
except ImportError:                                      # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import photon_sources as PS      # noqa: E402
    import detectors as DT           # noqa: E402
    import open_system as OS         # noqa: E402

from lda_harness.smoke_kit import make_check        # noqa: E402

# 判据计数写进模块命名空间（尾部读 PASS/FAIL）；助手复用公共 `smoke_kit`，
# 不另建局部 `def check`（防「助手重复棘轮」J3/J4 劣化 · 名字在前！写反成
# check(cond, name) ⇒ 字符串恒真 ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("光子硬件物理门禁 smoke（D-114 源 / D-115 探测 / D-116 开放系统）")
    print("=" * 78)

    # ════════════════ A 节：单光子源（D-114）════════════════
    print("── A 单光子源物理（D-114）──")
    try:
        ok_a = PS.run_selfchecks(verbose=False)
    except Exception as e:                            # noqa: BLE001
        ok_a = False
        print(f"  源自检异常：{type(e).__name__}: {e}")
    check("A1 源模块自检 8/8 PASS", ok_a, "HBT三态/TMSS双路/热态约化/预告纯度/g²/孪生/WCS/护栏")

    n_max = 150
    g1 = PS.second_order_g2(PS.fock_dm(1, n_max), n_max)
    gth = PS.second_order_g2(PS.thermal_dm(2.0, n_max), n_max)
    gco = PS.second_order_g2(PS.coherent_dm(2.0, n_max), n_max)
    check("A2 单光子反聚束 g²(0)=0（Fock |1⟩，单光子判据）",
          abs(g1) < 1e-12, f"g²(|1⟩)={g1:.3e}")
    check("A3 热光聚束 g²(0)=2 · 相干态 g²(0)=1",
          abs(gth - 2.0) < 1e-9 and abs(gco - 1.0) < 1e-9,
          f"g²(热)={gth:.9f} g²(相干)={gco:.9f}")

    lam = 0.35
    rr = math.atanh(lam)
    psi = PS.tmss_numeric_state(rr, PS.TMSS_TRUNC)
    d = PS.TMSS_TRUNC + 1
    cl = PS.tmss_joint_probs(lam, PS.TMSS_TRUNC)
    tot = float(np.vdot(psi, psi).real)
    max_j = max(abs(float(abs(psi[n * d + n]) ** 2) / tot - cl[(n, n)]) for n in range(d))
    check("A4 TMSS 双路独立：闭式 (1−λ²)λ²ⁿ × 压缩算符矩阵指数",
          max_j < 1e-10, f"max|Δ|={max_j:.3e}（λ={lam} 截断残差={PS.truncation_residual(lam):.1e}）")

    rho2 = np.outer(psi, psi.conj())
    pure_pnr = float(np.real(np.trace(PS.heralded_pnr(rho2, PS.TMSS_TRUNC, 1) @
                                      PS.heralded_pnr(rho2, PS.TMSS_TRUNC, 1))))
    cond_oo = PS.heralded_onoff(rho2, PS.TMSS_TRUNC)
    pure_oo = float(np.real(np.trace(cond_oo @ cond_oo)))
    check("A5 预告纯度：PNR⇒1（纯 |1⟩）· on/off⇒(1−λ²)/(1+λ²) 闭式",
          abs(pure_pnr - 1.0) < 1e-10 and abs(pure_oo - PS.heralded_purity_onoff(lam)) < 1e-10,
          f"PNR={pure_pnr:.12f} on/off={pure_oo:.12f} 闭式={PS.heralded_purity_onoff(lam):.12f}")

    g2_oo = PS.second_order_g2(cond_oo, PS.TMSS_TRUNC)
    check("A6 预告 on/off 态 g²(0)=2λ² 闭式（源多光子污染度量）",
          abs(g2_oo - PS.heralded_g2_onoff(lam)) < 1e-9,
          f"数值={g2_oo:.9f} 闭式={PS.heralded_g2_onoff(lam):.9f}")

    mu = 0.6
    p_ge2 = 1.0 - PS.wcs_probs(mu, 50)[0] - PS.wcs_probs(mu, 50)[1]
    check("A7 WCS 多光子污染闭式 1−e^{−μ}(1+μ)",
          abs(p_ge2 - PS.wcs_multiphoton_prob(mu)) < 1e-12,
          f"μ={mu} P(≥2)={p_ge2:.6e}")

    guard_a = True
    try:
        PS.tmss_amplitudes(1.0)
        guard_a = False
    except ValueError:
        pass
    check("A8 护栏：压缩参数 λ≥1 抛 ValueError（tanh r 物理域）", guard_a)

    # ════════════════ B 节：SNSPD 探测（D-115）════════════════
    print("── B SNSPD 探测物理（D-115）──")
    try:
        ok_b = DT.run_selfchecks(verbose=False)
    except Exception as e:                            # noqa: BLE001
        ok_b = False
        print(f"  探测自检异常：{type(e).__name__}: {e}")
    check("B1 探测模块自检 11/11 PASS", ok_b, "on/off三路/PNR双路/半分辨/死时间/POVM/标度/HOM/桥/护栏")

    eta = 0.85
    max_c = 0.0
    for n in range(0, 8):
        rho = np.zeros((41, 41), dtype=complex)
        rho[n, n] = 1.0
        max_c = max(max_c, abs(DT.click_prob(rho, eta, 1e-6) - DT.click_prob_closed_form(eta, n, 1e-6)))
    check("B2 on/off 响应三路一致（POVM × 布居闭式 × Stinespring）",
          max_c < 1e-12, f"max|Δ|={max_c:.3e}（η={eta}）")

    max_p = max(abs(DT.pnr_prob_closed_form(n, k, eta) - DT.pnr_prob_stinespring(n, k, eta))
                for n in range(0, 7) for k in range(0, n + 1))
    check("B3 PNR 双路独立：闭式二项 × 永久式玻色振幅（Stinespring）",
          max_p < 1e-12, f"max|Δ|={max_p:.3e}")

    tau, r_hi = 10e-9, 1e9
    ok_dt = (DT.dead_time_nonparalyzable(r_hi, tau) < 1.0 / tau
             and DT.dead_time_paralyzable(r_hi, tau) < DT.dead_time_nonparalyzable(r_hi, tau))
    check("B4 死时间饱和：非瘫痪 <1/τ · 瘫痪高率回落",
          ok_dt, f"R_np={DT.dead_time_nonparalyzable(r_hi, tau):.3e} "
                 f"R_pl={DT.dead_time_paralyzable(r_hi, tau):.3e} 上限={1.0 / tau:.1e}")

    vis = [DT.hom_visibility_onoff(math.pi / 4.0, e) for e in (0.3, 0.6, 0.9, 1.0)]
    e_small = 1e-4
    p_coin = DT.coincidence_prob_onoff({(1, 1): 1.0}, e_small, 0.0)
    check("B5 HOM on/off 探测：可见度 V=1（与 η 无关）· 符合率标度 ∝η²",
          max(abs(v - 1.0) for v in vis) < 1e-12 and abs(p_coin - e_small ** 2) < 1e-15,
          f"V={['%.4f' % v for v in vis]} 符合(η=1e-4)={p_coin:.3e}=η²")

    max_bridge = max(abs(DT.loss_then_ideal_no_click(n, eta) - (1.0 - eta) ** n) for n in range(0, 9))
    check("B6 桥：探测器 η ≡ 损耗通道 η + 理想探测器（Φ_η 残留真空=(1−η)ⁿ）",
          max_bridge < 1e-12, f"max|Δ|={max_bridge:.3e}")

    guard_b = True
    for bad in (-0.1, 1.1):
        try:
            DT.onoff_povm(bad)
            guard_b = False
        except ValueError:
            pass
    check("B7 护栏：探测效率 η∉[0,1] 抛 ValueError", guard_b)

    # ════════════════ C 节：多模开放系统（D-116）════════════════
    print("── C 多模 Lindblad 开放系统（D-116）──")
    try:
        ok_c = OS.run_selfchecks(verbose=False)
    except Exception as e:                            # noqa: BLE001
        ok_c = False
        print(f"  开放系统自检异常：{type(e).__name__}: {e}")
    check("C1 开放系统模块自检 7/7 PASS", ok_c, "单模过程矩阵/布居/相干态/纠缠保真/多模三法/CP/护栏")

    max_M = 0.0
    for (kk, tt) in ((0.7, 0.55), (1.3, 0.2), (2.0, 0.4)):
        e = OS.transmissivity_from_kappa(kk, tt)
        max_M = max(max_M, float(np.max(np.abs(
            OS.process_matrix_ode_single(kk, tt, 4) - OS.process_matrix_kraus(OS.loss_kraus(e, 3), 4)))))
    check("C2 单模过程矩阵：ODE(RK4) × Kraus 逐元素一致（跨 η 网格）",
          max_M < 1e-10, f"max|Δ|={max_M:.3e}（d=4）")

    max_tri = 0.0
    for (M, dd, kaps, tt) in ((2, 4, (0.7, 0.3), 0.55), (3, 2, (0.5, 0.9, 0.2), 0.6)):
        rg = np.random.default_rng(2026 + M * 7 + dd)
        X = rg.standard_normal((dd ** M, dd ** M)) + 1j * rg.standard_normal((dd ** M, dd ** M))
        rho0 = X @ X.conj().T
        rho0 = rho0 / np.trace(rho0)
        ra = OS.full_ode_evolve(kaps, M, dd, rho0, tt)
        rb = OS.factorized_evolve(kaps, M, dd, rho0, tt)
        rc = OS.kraus_multimode_evolve(kaps, M, dd, rho0, tt)
        max_tri = max(max_tri, float(np.max(np.abs(ra - rb))), float(np.max(np.abs(ra - rc))))
    check("C3 多模三法一致（含纠缠初态）：全空间 ODE × 逐模张量收缩 × 全空间 Kraus",
          max_tri < 1e-9, f"max|Δ|={max_tri:.3e}（防 row-major vec 裸 kron 陷阱）")

    alpha, e2 = 1.3, OS.transmissivity_from_kappa(0.7, 0.55)
    out_coh = OS.kraus_channel(PS.coherent_dm(alpha, 40), OS.loss_kraus(e2, 40))
    v_a = np.array([math.exp(-alpha ** 2 / 2) * alpha ** n / math.sqrt(math.factorial(n))
                    for n in range(41)], dtype=complex)
    v_a = v_a / float(np.linalg.norm(v_a))
    fid = float(abs(np.vdot(v_a, out_coh @ v_a)))
    check("C4 相干态损耗保真 × 闭式 exp(−|α|²(1−√η)²)",
          abs(fid - OS.coherent_loss_fidelity_closed_form(alpha, e2)) < 1e-10,
          f"F 数值={fid:.12f} 闭式={OS.coherent_loss_fidelity_closed_form(alpha, e2):.12f}")

    fe1 = OS.entanglement_fidelity_kraus(OS.loss_kraus(1.0, 3), 4)
    check("C5 纠缠保真度 η=1 ⇒ 1（恒等通道，非退化为去相位）",
          abs(fe1 - 1.0) < 1e-12, f"F_e(η=1)={fe1:.12f}（去相位实现会错成 1/d=0.25）")

    kraus = OS.loss_kraus(e2, 3)
    tp = float(np.max(np.abs(sum(A.conj().T @ A for A in kraus) - np.eye(4))))
    check("C6 物理性：通道保迹 ΣA†A=I（Choi 半正定在同模块自检）", tp < 1e-15, f"max|ΣA†A−I|={tp:.2e}")

    guard_c = True
    for bad in ((lambda: OS.loss_liouvillian([-0.1], 1, 2)),
                (lambda: OS.loss_kraus(1.5, 3))):
        try:
            bad()
            guard_c = False
        except ValueError:
            pass
    check("C7 护栏：κ<0 / η∉[0,1] 抛 ValueError", guard_c)

    # ════════════════ D 节：跨模块 + 红线 ════════════════
    print("── D 跨模块一致性 + 红线 ──")
    max_x = max(abs(DT.pnr_prob_closed_form(n, k, e2) - OS.loss_population_closed_form(n, k, e2))
                for n in range(0, 7) for k in range(0, n + 1))
    check("D1 跨模块：D-115 PNR 二项 ≡ D-116 损耗布居（探测效率=损耗透射率）",
          max_x < 1e-15, f"max|Δ|={max_x:.3e}")

    # D-116 损耗通道 + 理想探测器 与 D-115 click_prob(η) 等价
    max_x2 = 0.0
    for n in range(0, 8):
        rho = np.zeros((8, 8), dtype=complex)
        rho[n, n] = 1.0
        out = OS.kraus_channel(rho, OS.loss_kraus(eta, 7))
        p_ideal_after_loss = 1.0 - float(np.real(out[0, 0]))          # 理想 on/off：无光子则不响应
        max_x2 = max(max_x2, abs(p_ideal_after_loss - DT.click_prob_closed_form(eta, n, 0.0)))
    check("D2 跨模块：损耗通道(D-116)+理想探测器 ≡ 效率 η 的 on/off(D-115)",
          max_x2 < 1e-12, f"max|Δ|={max_x2:.3e}")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = []
    for mod in ("photon_sources", "detectors", "open_system"):
        src = open(os.path.join(_HERE, "lda_qeda", mod + ".py"), encoding="utf-8").read()
        hits += [f"{mod}:{b}" for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D3 红线：三模块零量子 SDK 依赖（纯 numpy，C 级自主）",
          not hits, f"命中={hits or '无'}")

    # 反自证桩：on/off ≠ PNR（阈值探测丢光子数信息）
    onoff_sat = (abs(DT.click_prob_closed_form(1.0, 1) - 1.0) < 1e-15
                 and abs(DT.click_prob_closed_form(1.0, 2) - 1.0) < 1e-15)
    pnr_res = (abs(DT.pnr_prob_closed_form(1, 1, 1.0) - 1.0) < 1e-15
               and abs(DT.pnr_prob_closed_form(2, 1, 1.0)) < 1e-15)
    check("D4 反自证桩：on/off 对 |1⟩/|2⟩ 均响应 1（丢分辨）≠ PNR 可分辨",
          onoff_sat and pnr_res,
          f"on/off η=1: P(1)= {DT.click_prob_closed_form(1.0,1):.1f} P(2)={DT.click_prob_closed_form(1.0,2):.1f}"
          f" · PNR: P(1|1)={DT.pnr_prob_closed_form(1,1,1.0):.1f} P(1|2)={DT.pnr_prob_closed_form(2,1,1.0):.1f}")

    print()
    print(f"光子硬件物理门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
