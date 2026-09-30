# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E1 · 基座门禁 + 突变探针（D-150）。

============================================================================
E1 基座（吃狗粮逼出的平台短板：此前平台**无晶体管级模型 / 无电路仿真器**）
----------------------------------------------------------------------------
四大模块：mosfet（长沟道平方律 NMOS）/ mna（MNA 电路仿真器 DC/瞬态/AC）/
analog_mvm（最小模拟计算单元：反相求和 MAC + NMOS 饱和偏置）/ ecore 包入口。

本门禁验收（与 CI core 同口径，死标量 + 突变探针）：
  ① 反相求和 MAC：MNA(理想运放=超大增益 VCVS) vs 闭式 golden（分压/求和）；
  ② 电阻分压：MNA vs 闭式 golden；
  ③ NMOS 饱和偏置：MNA 仿真 vs 闭式 golden（含 λ）+ KCL 一致性；
  ④ RC 瞬态：后向欧拉 vs 指数闭式（τ=RC）；
  ⑤ RC 交流：AC 复导纳 vs 闭式转移函数；
  ⑥ MOSFET 模型自证桩：三区 + 与闭式一致 + 边界连续。

🔴 突变探针（防常数假绿 / 防死断言）：
  ⑦ 破坏求和闭式 golden → ① 必红；
  ⑧ 破坏 MOSFET id_gm_gds 模型 → ⑥ 必红；
  ⑨ 破坏电阻 stamp 装配 → ② 必红；
  ⑩ 还原后重跑①/③，确无残留漂移（探针反向完备：仍绿(死断言!) 必须为空）。

主权纪律（与全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；
golden 俱为闭式物理律，无外部 ORACLE；T1 电路级（不碰 Foundry TCAD/流片）。
"""
import sys

import numpy as np
from unittest.mock import patch

from lda_l2.ecore import mosfet, mna, analog_mvm
from lda_l2.ecore.analog_mvm import (
    inverting_summer,
    inverting_summer_golden,
    mosfet_saturation_bias,
)
from lda_l2.ecore.mosfet import NmosParams, mosfet_self_check
from lda_l2.ecore import ECORE_DISCLOSURE


# ---------------------------------------------------------------------------
# 绿色检查（返回 (ok, detail)）—— 闭式 golden 验证
# ---------------------------------------------------------------------------
def chk_summer():
    r = inverting_summer(0.3, 0.2, 1e3, 1e3, 1e3)
    ok = (abs(r["vout"] - r["golden"]) < 1e-3) and (abs(r["v_minus"]) < 1e-3)
    return ok, (f"vout={r['vout']:.6f} golden={r['golden']:.6f} "
                f"vminus={r['v_minus']:.2e}")


def chk_divider():
    ckt = mna.Circuit("divider")
    ckt.vsource(3, 0, 1.0)
    ckt.resistor(3, 1, 1e3)
    ckt.resistor(1, 0, 2e3)
    try:
        x = ckt.solve_dc()
        nv = ckt.node_voltages(x)
        v1 = nv[1]
    except Exception as e:  # noqa
        return False, f"raise {e!r}"
    gold = 1.0 * 2e3 / (1e3 + 2e3)
    ok = abs(v1 - gold) < 1e-9
    return ok, f"v1={v1:.9f} gold={gold:.9f}"


def chk_bias():
    p = NmosParams()
    r = mosfet_saturation_bias(1.0, 500.0, p)
    ok_kcl = abs(r["id_from_load"] - r["id_from_model"]) < 1e-6
    ok_gold = (abs(r["vd"] - r["golden"]["vd"]) < 1e-6) and r["golden"]["in_saturation"]
    ok = ok_kcl and ok_gold
    return ok, (f"vd={r['vd']:.6f} gold_vd={r['golden']['vd']:.6f} "
                f"idload={r['id_from_load']:.3e} idmodel={r['id_from_model']:.3e} "
                f"sat={r['golden']['in_saturation']}")


def chk_rc_transient():
    ckt = mna.Circuit("rc")
    ckt.vsource(3, 0, 1.0)
    ckt.resistor(3, 1, 1e3)
    ckt.capacitor(1, 0, 1e-6)
    t_end, n = 5e-3, 500
    try:
        times, out = ckt.solve_transient(t_end, n)
    except Exception as e:  # noqa
        return False, f"raise {e!r}"
    v_end = out[-1, 1]
    tau = 1e3 * 1e-6
    gold_end = 1.0 * (1.0 - np.exp(-t_end / tau))
    v_mid = out[100, 1]                       # t = 100*10us = 1ms = 1 tau
    gold_mid = 1.0 * (1.0 - np.exp(-1.0))
    ok = (abs(v_end - gold_end) < 0.01) and (abs(v_mid - gold_mid) < 0.01)
    return ok, (f"vend={v_end:.6f} gold={gold_end:.6f} "
                f"vmid={v_mid:.6f} gold={gold_mid:.6f}")


def chk_ac():
    ckt = mna.Circuit("ac")
    ckt.resistor(1, 0, 1e3)
    ckt.capacitor(1, 0, 1e-6)
    f = 100.0
    try:
        w, v = ckt.solve_ac(f, ac_sources={(1, 0): complex(1.0, 0)})
    except Exception as e:  # noqa
        return False, f"raise {e!r}"
    v1 = v[1]
    gold = -complex(1.0, 0) / (1.0 / 1e3 + 1j * w * 1e-6)
    ok = abs(v1 - gold) < 1e-6
    return ok, f"v1={v1!r} gold={gold!r} abserr={abs(v1 - gold):.2e}"


def selfcheck_ok():
    sc = mosfet_self_check()
    ok = (sc["saturation_points_in_agreement"] == 64
          and sc["saturation_vs_closed_form_max_abs_err"] < 1e-9
          and abs(sc["cutoff_id"]) < 1e-12
          and sc["triode_sat_boundary_continuity_abs_err"] < 1e-6)
    return ok, str(sc)


# ---------------------------------------------------------------------------
# 突变探针：返回 True 表示「突变后对应检查确实变红」（防死断言）
# ---------------------------------------------------------------------------
def probe_summer_golden_corrupt():
    bad = lambda v1, v2, r1, r2, rf: -rf * (v1 / r1 + v2 / r2) * 2.0  # 破坏 ×2
    with patch.object(analog_mvm, "inverting_summer_golden", bad):
        ok, _ = chk_summer()
    return not ok


def probe_mosfet_model_corrupt():
    bad = lambda vgs, vds, p: (0.0, 0.0, 0.0)     # 晶体管恒截止
    with patch.object(mosfet, "id_gm_gds", bad):
        ok, _ = selfcheck_ok()
    return not ok


def probe_divider_stamp_corrupt():
    orig = mna.Circuit._stamp_dc

    def bad_stamp(self, A, b, e, x, nidx):
        if e["type"] == "R":
            return                                  # 跳过电压 stamp → 节点悬空
        return orig(self, A, b, e, x, nidx)

    with patch.object(mna.Circuit, "_stamp_dc", bad_stamp):
        ok, _ = chk_divider()
    return not ok


def main():
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA 电子计算征程 E1 · 基座门禁（D-150）===")
    print("ECORE_DISCLOSURE:", ECORE_DISCLOSURE["route"])

    # —— 绿：闭式 golden 验证 ——
    ok, det = chk_summer()
    check("① 反相求和 MAC: MNA vs 闭式", ok, det)
    ok, det = chk_divider()
    check("② 电阻分压: MNA vs 闭式", ok, det)
    ok, det = chk_bias()
    check("③ NMOS 饱和偏置: MNA vs 闭式 + KCL", ok, det)
    ok, det = chk_rc_transient()
    check("④ RC 瞬态: 后向欧拉 vs 指数", ok, det)
    ok, det = chk_ac()
    check("⑤ RC 交流: AC 复导纳 vs 闭式", ok, det)
    ok, det = selfcheck_ok()
    check("⑥ MOSFET 模型自证桩", ok, det)

    # —— 红：突变探针（必变红，否则为死断言）——
    check("🔴 ⑦ 突变探针: 破坏求和 golden 必红", probe_summer_golden_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑧ 突变探针: 破坏 MOSFET 模型必红", probe_mosfet_model_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑨ 突变探针: 破坏电阻 stamp 必红", probe_divider_stamp_corrupt(),
          "未变红（死断言!）")

    # —— 还原完整性：突变后重跑绿，确无残留漂移 ——
    ok, det = chk_summer()
    check("⑩ 还原重跑: 反相求和无残留漂移", ok, det)
    ok, det = chk_bias()
    check("⑩ 还原重跑: NMOS 饱和偏置无残留漂移", ok, det)

    if fails:
        print(f"\nE1 基座门禁: {len(fails)} FAIL -> {fails}")
        sys.exit(1)
    print("\nE1 基座门禁: ALL GREEN（含 3 道突变探针 + 还原完整性）")


if __name__ == "__main__":
    main()
