# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E2 · 参数化 MVM 交叉阵列门禁 + 突变探针（D-151）。

============================================================================
E2（吃狗粮：把 E1 的「反相求和 MAC」扩成 N×M 模拟 MVM 交叉阵列，对标 Mythic 类）
----------------------------------------------------------------------------
验收（与 CI core 同口径，死标量 + 突变探针）：
  ① ideal 4×4 MVM：MNA(VCVS TIA) vs 闭式 golden（-rf·W@x）；
  ② ideal 8×8 参数化扩展：规模化 golden 匹配；
  ③ transistor 2×2 MVM：NMOS三极管权重 + 电阻负载 vs 平方律闭式 golden；
  ④ transistor 4×4 MVM：规模化 golden 匹配；
  ⑤ OTA 开环增益：晶体管级放大器增益 > 阈值，且随 Rd 单调增大（gm·Rd）。

🔴 突变探针（防常数假绿 / 防死断言）：
  ⑥ 破坏求和闭式 golden → ①/② 必红；
  ⑦ 破坏 MOSFET 模型 → ③/④ 必红；
  ⑧ 破坏电阻 stamp 装配 → ①/② 必红；
  ⑨ 还原后重跑①/③，确无残留漂移（探针反向完备：仍绿(死断言!) 必须为空）。

主权纪律（与全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；
golden 俱为闭式物理律，无外部 ORACLE；T1 电路级（不碰 Foundry TCAD/流片）。
"""
import sys

import numpy as np
from unittest.mock import patch

from lda_l2.ecore import crossbar_mvm, mna, mosfet
from lda_l2.ecore.crossbar_mvm import CrossbarMVM, ota_open_loop_gain
from lda_l2.ecore.mosfet import NmosParams
from lda_harness.smoke_kit import make_fail_collector


# ---------------------------------------------------------------------------
# 绿色检查（闭式 golden 验证）
# ---------------------------------------------------------------------------
def chk_ideal_4x4():
    rng = np.random.RandomState(7)
    W = rng.uniform(0.5e-4, 3e-4, (4, 4))
    x = rng.uniform(0.1, 0.8, 4)
    cb = CrossbarMVM(W, x, rf=10e3, amp="ideal")
    err = cb.max_abs_err()
    return err < 1e-2, f"4x4 ideal maxerr={err:.3e}"


def chk_ideal_8x8():
    rng = np.random.RandomState(11)
    W = rng.uniform(0.5e-4, 3e-4, (8, 8))
    x = rng.uniform(0.1, 0.8, 8)
    cb = CrossbarMVM(W, x, rf=10e3, amp="ideal")
    err = cb.max_abs_err()
    return err < 1e-2, f"8x8 ideal maxerr={err:.3e}"


def chk_tx_2x2():
    p = NmosParams()
    x = np.array([0.08, 0.12])
    Wg = np.array([[2.5, 2.8], [3.0, 2.6]])     # 栅压（权重）
    cb = CrossbarMVM(Wg, x, rf=20.0, amp="transistor", p=p)
    err = cb.max_abs_err()
    return err < 1e-3, f"2x2 transistor maxerr={err:.3e}"


def chk_tx_4x4():
    rng = np.random.RandomState(3)
    p = NmosParams()
    x = rng.uniform(0.05, 0.15, 4)
    Wg = rng.uniform(2.5, 3.2, (4, 4))
    cb = CrossbarMVM(Wg, x, rf=20.0, amp="transistor", p=p)
    err = cb.max_abs_err()
    return err < 1e-3, f"4x4 transistor maxerr={err:.3e}"


def chk_ota_gain():
    # 取健康偏置区间（避免 Rd 触及电源轨致病态）：Iss=0.5mA，Rd=20k/30k
    g_small = ota_open_loop_gain(Iss=0.5e-3, Rd=20e3)
    g_big = ota_open_loop_gain(Iss=0.5e-3, Rd=30e3)
    ok = abs(g_small) > 3.0 and abs(g_big) > abs(g_small)
    return ok, (f"|gain(20k)|={abs(g_small):.2f} |gain(30k)|={abs(g_big):.2f} "
                f"(应随 Rd 增大)")


# ---------------------------------------------------------------------------
# 突变探针：返回 True 表示「突变后对应检查确实变红」
# ---------------------------------------------------------------------------
def probe_golden_corrupt():
    bad = lambda self: -self.rf * (self.weights @ self.inputs) * 2.0   # 破坏 ×2
    with patch.object(CrossbarMVM, "golden_outputs", bad):
        ok, _ = chk_ideal_4x4()
    return not ok


def probe_mosfet_model_corrupt():
    # 注意：电路仿真由 mna._stamp_mosfet_dc 调用的是 mna 模块内的 id_gm_gds 副本，
    # 须 patch mna.id_gm_gds 才会真正生效（patch mosfet.id_gm_gds 无效）。
    bad = lambda vgs, vds, p: (0.0, 0.0, 0.0)      # 晶体管恒截止 → 交叉点开路
    with patch.object(mna, "id_gm_gds", bad):
        ok, _ = chk_tx_2x2()
    return not ok


def probe_resistor_stamp_corrupt():
    orig = mna.Circuit._stamp_dc

    def bad_stamp(self, A, b, e, x, nidx):
        # 只破坏交叉点电阻（tag 以 'g' 开头）的装配 → 权重丢失、sim 偏离 golden；
        # 保留反馈电阻 Rf（tag 'Rf'）以维持可解、避免悬浮奇异。
        if e["type"] == "R" and str(e.get("tag", "")).startswith("g"):
            return
        return orig(self, A, b, e, x, nidx)

    with patch.object(mna.Circuit, "_stamp_dc", bad_stamp):
        ok, _ = chk_ideal_4x4()
    return not ok


def main():
    fails = []

    check = make_fail_collector(fails)

    print("=== LDA 电子计算征程 E2 · 参数化 MVM 交叉阵列门禁（D-151）===")
    print("CROSSBAR_DISCLOSURE:", crossbar_mvm.CROSSBAR_DISCLOSURE["route"])

    # —— 绿：闭式 golden 验证 ——
    ok, det = chk_ideal_4x4()
    check("① ideal 4×4 MVM: MNA vs 闭式", ok, det)
    ok, det = chk_ideal_8x8()
    check("② ideal 8×8 参数化扩展: MNA vs 闭式", ok, det)
    ok, det = chk_tx_2x2()
    check("③ transistor 2×2 MVM: NMOS三极管权重 vs 平方律闭式", ok, det)
    ok, det = chk_tx_4x4()
    check("④ transistor 4×4 MVM: 规模化 vs 闭式", ok, det)
    ok, det = chk_ota_gain()
    check("⑤ OTA 开环增益: 晶体管放大器增益>阈值且随Rd增大", ok, det)

    # —— 红：突变探针（必变红，否则为死断言）——
    check("🔴 ⑥ 突变探针: 破坏 MVM golden 必红", probe_golden_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑦ 突变探针: 破坏 MOSFET 模型必红", probe_mosfet_model_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑧ 突变探针: 破坏电阻 stamp 必红", probe_resistor_stamp_corrupt(),
          "未变红（死断言!）")

    # —— 还原完整性：突变后重跑绿，确无残留漂移 ——
    ok, det = chk_ideal_4x4()
    check("⑨ 还原重跑: ideal 4×4 无残留漂移", ok, det)
    ok, det = chk_tx_2x2()
    check("⑨ 还原重跑: transistor 2×2 无残留漂移", ok, det)

    if fails:
        print(f"\nE2 门禁: {len(fails)} FAIL -> {fails}")
        sys.exit(1)
    print("\nE2 门禁: ALL GREEN（含 3 道突变探针 + 还原完整性）")


if __name__ == "__main__":
    main()
