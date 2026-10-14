#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J4 量子传感系统集成征程 · M0 常驻门禁（多参数 NV 交叉灵敏度解耦）。

═══ 判什么（分节）═══
A 🔴 **M0 多参数解耦（净增账本锚 B515）**：B515 **多参数 NV 传感交叉灵敏度解耦温度分量 τ̂**
   —— 4×4 灵敏度方程 S·x=b 的 **Cramer 闭式解析反演**（行列式 Laplace 展开 → 3×3 余子式
   手写展开，τ̂=det(S₁)/det(S)）⇄ **Landweber 迭代解耦**（固定最优步长 τ*=2/(λ_min+λ_max)
   的梯度下降最小二乘，k 步）—— 在 DEFS tol 内、且残差**非零**（非代数恒等）；判据 D 残差
   随迭代步数严格单调↓（**几何收敛**：等差扫描格 ⇒ 比值恒定 = ρ^{−Δk}，粗端 >1e-12 显著
   放大）；反自证桩（候选对 coupling 扰动有响应）+ 反向探针（**粗档 k=64 ⇒ 候选偏离 golden
   必超 tol**，证明 anchor 真在算）；防回退（candidate 键指向本批新候选）。
   🔴 tol/golden 一律**读自 `BENCHMARK_DEFS` 不硬编码**（与账本判决同源）。
   🔴 **反向探针用离散参数（k）而非物理参数**：coupling 扰动会同时改变 golden 与候选，
   残差仍 <tol（实测 coupling×1.1 ⇒ 2.01e-08）⇒ 物理参数扰动**不能**证明可证伪；
   只有「收敛未达标的粗档」才使残差浮出 tol 之上。
B 🔴 **能力层常驻自检**：`lda_l2/qs_j4_multiparam.py`（响应矩阵结构 + 条件数单调 +
   解耦回代重构 b + 迭代收敛到闭式 + 噪声放大 + 交叉耦合表 + 反向探针）。
C 🔴 **能力层↔账本锚同物理律（跨模块同源，防漂移）**：能力层 `_C` ≡ 数值核 `_C_MP`
   （逐位）；能力层 Cramer 解 ≡ 数值核 golden（逐位）；能力层 Landweber ≡ 数值核候选（逐位）。
D 🔴 **三表/默认档一致**：`_TOL_BY_BID["B515"]` ≡ `BENCHMARK_DEFS["B515"]["tol"]`；
   `_M_BY_BID["B515"]` = 扫描格末端；默认参数 coupling 与 DEFS `default_params` 同值。
E 🔴 **主权边界机械可核**：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）。

═══ 诚实边界 ═══
· γ_e/dD/dT/dD/dE/dD/dσ 为**文献量级的设计示例**（非任何 foundry 实测标定）；响应矩阵 C
  与读数向量 b 为**设计示例**（非实测 ODMR 谱拟合）；模型为**一阶线性化**。
· 只证「Cramer 闭式解析反演 ⇄ Landweber 迭代解耦」数值一致 + 多参数解耦物理链自洽，
  **不作制造/性能宣称**，不报能效/TOPS/fJ-op。
· 零量子 SDK；LLM 不进判决路径。
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

# 🔴 关键模块**模块级**导入（不是 main() 内局部导入）—— 突变探针 `scripts/d155_j4_probe.py`
#   正是 patch 这几个**同一模块对象**；若改成 main 内 `from x import f`，探针会 patch 到
#   另一个绑定 ⇒ 打空 ⇒ 假绿（本仓 M-121 血案：探针必须打门禁同一模块对象）。
from lda_harness import _batch_j4_numeric as J4  # noqa: E402
from lda_l2 import qs_j4_multiparam as MP  # noqa: E402
from lda_l2 import qs_j4_microcell as MC  # noqa: E402
from lda_l2 import qs_j4_integration as IG  # noqa: E402
from lda_l2 import qs_j4_packaging as PK  # noqa: E402
from lda_l2 import qs_j4_system as SYS  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def main() -> int:
    import numpy as np
    from lda_harness.benchmarks import BENCHMARK_DEFS

    def _defs_golden(bid: str, params: dict) -> float:
        return float(BENCHMARK_DEFS[bid]["golden_fn"](**params))

    def _defs_params(bid: str, fallback: dict) -> dict:
        return dict(BENCHMARK_DEFS[bid].get("default_params") or fallback)

    # ----------------------------------------------------------------- A
    # M0 多参数解耦（净增账本锚 B515）· 温度分量 τ̂。
    p515 = _defs_params("B515", dict(J4.B515_DEFAULT_PARAMS))
    tol515 = float(BENCHMARK_DEFS["B515"]["tol"])
    grid515 = (64, 128, 192, 256, 320)
    g515 = _defs_golden("B515", p515)
    c515 = float(J4.cand_b515(**p515))
    r515 = abs(c515 - g515)
    check("A1 B515 多参数解耦温度分量：Cramer 闭式解析反演 ⇄ Landweber 迭代解耦一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r515, tol515),
          0.0 < r515 < tol515, "golden=%.9f cand=%.9f" % (g515, c515))

    res515 = [abs(float(J4.cand_b515(**{**p515, "n": k})) - g515) for k in grid515]
    mono515 = all(res515[i] > res515[i + 1] for i in range(len(res515) - 1))
    ratio515 = [res515[i] / res515[i + 1] for i in range(len(res515) - 1)]
    ratio_flat = (max(ratio515) / min(ratio515)) < 1.05
    check("A2 B515 判据 D：迭代残差随步数严格单调↓（几何收敛 ⇒ 比值恒定 ~%.1f，"
          "粗端 >1e-12 显著放大）" % (sum(ratio515) / len(ratio515)),
          mono515 and res515[0] > 1e-12 and res515[-1] < tol515
          and all(x > 1.0 for x in ratio515) and ratio_flat,
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res515),
                                 "/".join("%.1f" % x for x in ratio515)))

    resp515 = abs(float(J4.cand_b515(**{**p515, "coupling": p515["coupling"] * 1.1})) - c515)
    check("A3 反自证桩：B515 候选对交叉耦合强度扰动有物理响应（非 return-golden 桩）",
          resp515 > 0.0, "Δcand515(coupling×1.1)=%.2e" % resp515)

    dev515 = abs(float(J4.cand_b515(**{**p515, "n": 64})) - g515)
    check("A4 反向探针：B515@粗档 k=64（收敛未达标）⇒ |cand−golden| 必超 tol（可证伪）",
          dev515 > tol515, "dev515=%.2e(tol=%.1e)" % (dev515, tol515))

    cand_key515 = str(BENCHMARK_DEFS["B515"].get("candidate"))
    check("A5 防回退：B515 candidate 键指向本批新候选（非自证桩占位）",
          cand_key515 == "b515_multiparam_decoupling_cand", "candidate=%s" % cand_key515)

    # ----------------------------------------------------------------- B
    # 能力层常驻自检。
    mp_sc = MP.selfcheck_qs_j4()
    mp_bad = [k for k, v in mp_sc.items() if not v]
    check("B1 能力层 qs_j4_multiparam 自检全过（响应矩阵 + 条件数 + 解耦回代 + 迭代收敛 + "
          "噪声放大 + 交叉耦合 + 反向探针）",
          not mp_bad, "FAIL 项=%s" % (mp_bad or "无"))

    # ----------------------------------------------------------------- C
    # 能力层↔账本锚同物理律（跨模块同源，防漂移）。
    same_C = bool(np.array_equal(MP._C, J4._C_MP) and np.array_equal(MP._B, J4._B_MP))
    check("C1 跨模块同源：能力层响应矩阵 _C ≡ 数值核 _C_MP 且读数向量 _B ≡ _B_MP（逐位）",
          same_C, "equal=%s" % same_C)

    x_mp = MP.decouple_cramer(p515["coupling"])
    x_j4 = float(J4.multiparam_decouple_golden(p515["coupling"]))
    same_g = abs(float(x_mp[1]) - x_j4) == 0.0
    check("C2 能力层 Cramer 解 ≡ 账本锚 golden（逐位）：τ̂=%.12e" % x_j4,
          same_g, "mp=%r j4=%r" % (float(x_mp[1]), x_j4))

    x_lw = MP.decouple_landweber(p515["coupling"], 320)
    same_c = abs(float(x_lw[1]) - c515) == 0.0
    check("C3 能力层 Landweber ≡ 账本锚候选（逐位）：τ̂=%.12e" % c515,
          same_c, "mp=%r j4=%r" % (float(x_lw[1]), c515))

    # ----------------------------------------------------------------- D
    # 三表/默认档一致。
    _bids = ("B515", "B518")
    _tol_ok = all(float(J4._TOL_BY_BID[b]) == float(BENCHMARK_DEFS[b]["tol"]) for b in _bids)
    _end_ok = all(int(J4._GRID_BY_BID[b][-1]) == int(J4._M_BY_BID[b]) for b in _bids)
    check("D1 三表一致（两锚）：_TOL_BY_BID ≡ BENCHMARK_DEFS tol；_M_BY_BID = 扫描格末端",
          _tol_ok and _end_ok,
          "tol=%s end=%s" % ({b: J4._TOL_BY_BID[b] for b in _bids}, _end_ok))

    same_p515 = dict(J4.B515_DEFAULT_PARAMS) == dict(p515)
    same_p518 = dict(J4.B518_DEFAULT_PARAMS) == dict(
        BENCHMARK_DEFS["B518"].get("default_params") or {})
    check("D2 默认档一致（两锚）：B515/B518 _DEFAULT_PARAMS ≡ DEFS default_params",
          same_p515 and same_p518,
          "B515=%s B518=%s" % (same_p515, same_p518))

    # ----------------------------------------------------------------- E
    # 主权边界机械可核：零量子 SDK。
    sdk = [m for m in ("qiskit", "cirq", "pennylane", "qutip", "strawberryfields")
           if m in sys.modules]
    check("E1 主权边界：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）",
          not sdk, "命中=%s" % (sdk or "无"))

    # ----------------------------------------------------------------- F
    # M3 封装热负载（净增账本锚 B518）· 低温布线束热负载。
    p518 = _defs_params("B518", dict(J4.B518_DEFAULT_PARAMS))
    tol518 = float(BENCHMARK_DEFS["B518"]["tol"])
    grid518 = (32, 64, 128, 256, 512)
    g518 = _defs_golden("B518", p518)
    c518 = float(J4.cand_b518(**p518))
    r518 = abs(c518 - g518)
    check("F1 B518 低温布线束热负载：WF 电子热导有理闭式 ⇄ RK4 积分定义 ODE 一致"
          "（|Δ|=%.2e < tol=%.1e 且 >0 非恒等）" % (r518, tol518),
          0.0 < r518 < tol518, "golden=%.9e cand=%.9e" % (g518, c518))

    res518 = [abs(float(J4.cand_b518(**{**p518, "n": n})) - g518) for n in grid518]
    mono518 = all(res518[i] > res518[i + 1] for i in range(len(res518) - 1))
    ratio518 = [res518[i] / res518[i + 1] for i in range(len(res518) - 1)]
    check("F2 B518 判据 D：RK4 残差随步数严格单调↓（O(h⁴) ⇒ 比值趋向 16，粗端 >1e-12）",
          mono518 and res518[0] > 1e-12 and res518[-1] < tol518
          and 4.0 <= ratio518[-1] <= 20.0 and ratio518[-1] > ratio518[0],
          "resid=%s ratio=%s" % (" → ".join("%.2e" % x for x in res518),
                                 "/".join("%.1f" % x for x in ratio518)))

    resp518 = abs(float(J4.cand_b518(**{**p518,
                                        "beta_ohm_m_per_K": p518["beta_ohm_m_per_K"] * 1.5})) - c518)
    check("F3 反自证桩：B518 候选对电阻率斜率 β 扰动有物理响应（非 return-golden 桩）",
          resp518 > 0.0, "Δcand518(β×1.5)=%.2e" % resp518)

    dev518 = abs(float(J4.cand_b518(**{**p518, "n": 32})) - g518)
    check("F4 反向探针：B518@粗档 n=32（收敛未达标）⇒ |cand−golden| 必超 tol（可证伪）",
          dev518 > tol518, "dev518=%.2e(tol=%.1e)" % (dev518, tol518))

    cand_key518 = str(BENCHMARK_DEFS["B518"].get("candidate"))
    check("F5 防回退：B518 candidate 键指向本批新候选（非自证桩占位）",
          cand_key518 == "b518_cryo_wiring_heat_cand", "candidate=%s" % cand_key518)

    # ----------------------------------------------------------------- G
    # 四能力层常驻自检（M1 微型化 / M2 集成 / M3 封装 / M4 总装）。
    mc_bad = [k for k, v in MC.selfcheck_qs_j4_microcell().items() if not v]
    ig_bad = [k for k, v in IG.selfcheck_qs_j4_integration().items() if not v]
    pk_bad = [k for k, v in PK.selfcheck_qs_j4_pkg().items() if not v]
    sy_bad = [k for k, v in SYS.selfcheck_qs_j4_system().items() if not v]
    check("G1 能力层 qs_j4_microcell 自检全过（扩散/壁弛豫/涂层/缓冲/总弛豫 + 反向探针）",
          not mc_bad, "FAIL 项=%s" % (mc_bad or "无"))
    check("G2 能力层 qs_j4_integration 自检全过（dB↔比值/20dB 十倍/净劣化/签核 + 反向探针）",
          not ig_bad, "FAIL 项=%s" % (ig_bad or "无"))
    check("G3 能力层 qs_j4_packaging 自检全过（WF 极限退化/线性标度/单调性/预算 + 反向探针）",
          not pk_bad, "FAIL 项=%s" % (pk_bad or "无"))
    check("G4 能力层 qs_j4_system 自检全过（四档签核链 + 超预算必 REJECT + 跨模块同源）",
          not sy_bad, "FAIL 项=%s" % (sy_bad or "无"))

    # ----------------------------------------------------------------- H
    # 能力层↔账本锚同物理律（跨模块同源，防漂移）。
    pk_g = PK.cryo_wiring_heat_load(p518["rho0_ohm_m"], p518["beta_ohm_m_per_K"])
    same518 = abs(float(pk_g) - g518) < 1e-18
    check("H1 跨模块同律：packaging.cryo_wiring_heat_load ≡ B518 golden（Δ=%.1e）"
          % abs(float(pk_g) - g518), same518, "pkg=%.12e b518=%.12e" % (pk_g, g518))

    m3 = PK.package_report()
    sysrep = SYS.qs_system_report()
    same_load = abs(sysrep["m3_total_load_w"] - m3["total_load_w"]) == 0.0
    same_tau = abs(sysrep["m0_tau_hat"] - float(MP.decouple_cramer(1.0)[1])) == 0.0
    check("H2 系统总装 ≡ 子模块（M3 热负载逐位 · M0 τ̂ 逐位）+ 四档全 ACCEPT",
          same_load and same_tau and sysrep["all_accept"],
          "load_same=%s tau_same=%s verdict=%s" % (same_load, same_tau, sysrep["verdict"]))

    # ----------------------------------------------------------------- I
    # 锚归属（M1/M2 净增 0 如实登记 · 防「偷偷加锚」）。
    check("I1 J4-M1/M2 锚净增 0 登记齐备（ANCHOR_STATUS='none' + 避让表 5/4 条）",
          MC.ANCHOR_STATUS == "none" and IG.ANCHOR_STATUS == "none"
          and len(MC.ANCHOR_AVOIDANCE) == 5 and len(IG.ANCHOR_AVOIDANCE) == 4,
          "MC=%s(%d) IG=%s(%d)" % (MC.ANCHOR_STATUS, len(MC.ANCHOR_AVOIDANCE),
                                   IG.ANCHOR_STATUS, len(IG.ANCHOR_AVOIDANCE)))

    sys_anchors = list(SYS.SYSTEM_ANCHORS)
    check("I2 系统链锚来源 = ['B515','B518']（总装层本身不新增锚）",
          sys_anchors == ["B515", "B518"], "anchors=%s" % sys_anchors)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("J4 量子传感系统集成（M0：多参数 NV 交叉灵敏度解耦）门禁：%d PASS / %d FAIL"
          % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
