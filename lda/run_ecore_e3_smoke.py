# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E3 · MVM 数据通路门禁 + 突变探针（D-152）。

============================================================================
E3（吃狗粮：把 E2 的 MVM 阵列接成**完整矩阵运算数据通路**，做端到端正确性验证）
----------------------------------------------------------------------------
数据通路：数字 → DAC(量化) → 交叉阵列(E2 · 参考列法承载带符号权重) → ADC(量化) → 数字。

验收（与 CI core 同口径，死标量 + 突变探针）：
  ① 单层 8bit 数据通路 vs 全精度数字 golden（量化界内）；
  ② 量化趋势：位数↑ ⇒ 误差单调下降（可反向证伪）；
  ③ 2 层 MLP(ReLU) 端到端 vs 数字 golden（层间累积量化界内）；
  ④ 分块(tiling) 合成 == 全阵 MVM（可组合性，精确相等）；
  ⑤ 交叉阵列精度（隔离量化：forward_analog）vs golden（证恒等映射链路正确）；
  ⑥ 自证桩量化趋势判据为真。

🔴 突变探针（防常数假绿 / 防死断言）：
  ⑦ 破坏数字 golden → ① 必红；
  ⑧ 破坏量化器 → ① 必红；
  ⑨ 破坏交叉阵列 solve → ① 必红；
  ⑩ 还原后重跑①/③，确无残留漂移（探针反向完备：仍绿(死断言!) 必须为空）。

主权纪律（与全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；
golden 为全精度数字参考（非外部 ORACLE）；T1 电路级（不碰 Foundry TCAD/流片）。
"""
import sys

import numpy as np
from unittest.mock import patch

from lda_l2.ecore import crossbar_mvm, mvm_datapath
from lda_l2.ecore.mvm_datapath import MvmDatapath, mvm_datapath_self_check, tiled_mvm
from lda_l2.ecore.crossbar_mvm import CrossbarMVM


# ---------------------------------------------------------------------------
# 绿色检查（端到端正确性）
# ---------------------------------------------------------------------------
def _fixture():
    rng = np.random.RandomState(0)
    x = rng.uniform(0.0, 1.0, 6)
    W = rng.uniform(-1.0, 1.0, (4, 6))
    W1 = rng.uniform(-1.0, 1.0, (5, 6))
    W2 = rng.uniform(-1.0, 1.0, (3, 5))
    return x, W, W1, W2


def chk_single_layer():
    x, W, _, _ = _fixture()
    dp = MvmDatapath([W], dac_bits=8, adc_bits=8)
    err = dp.max_abs_err(x)
    return err < 0.03, f"single 8bit maxerr={err:.5f}"


def chk_quant_trend():
    x, W, _, _ = _fixture()
    errs = {b: MvmDatapath([W], dac_bits=b, adc_bits=b).max_abs_err(x)
            for b in (3, 4, 6, 8)}
    ok = errs[8] < errs[6] < errs[4] < errs[3]
    return ok, f"err(3,4,6,8)={errs[3]:.3f}/{errs[4]:.3f}/{errs[6]:.3f}/{errs[8]:.3f}"


def chk_mlp_two_layer():
    x, _, W1, W2 = _fixture()
    dp = MvmDatapath([W1, W2], dac_bits=6, adc_bits=6)
    err = dp.max_abs_err(x)
    return err < 0.1, f"MLP 2-layer 6bit maxerr={err:.5f}"


def chk_tiling():
    x, W, _, _ = _fixture()
    y_full = MvmDatapath([W], dac_bits=8, adc_bits=8).forward(x)
    y_tile = tiled_mvm(W, x, tile=2, dac_bits=8, adc_bits=8)
    err = float(np.max(np.abs(y_full - y_tile)))
    return err < 1e-9, f"tiling vs full maxerr={err:.2e}"


def chk_crossbar_precision():
    # 隔离量化：模拟输出（不含 ADC）vs golden ⇒ 证恒等映射链路（参考列法+交叉阵列）正确
    x, W, _, _ = _fixture()
    dp = MvmDatapath([W], dac_bits=12, adc_bits=12)
    err = float(np.max(np.abs(dp.forward_analog(x) - dp.golden(x))))
    return err < 0.01, f"crossbar-only maxerr={err:.5f}"


# ---------------------------------------------------------------------------
# 突变探针：返回 True 表示「突变后对应检查确实变红」
# ---------------------------------------------------------------------------
def probe_golden_corrupt():
    def bad_golden(self, x):
        return self._chain(x, lambda u, a: u.W @ a) * 2.0
    with patch.object(MvmDatapath, "golden", bad_golden):
        ok, _ = chk_single_layer()
    return not ok


def probe_quantizer_corrupt():
    bad = lambda v, bits, vmin, vmax: np.asarray(v, dtype=float) * 2.0
    with patch.object(mvm_datapath, "quantize_uniform", bad):
        ok, _ = chk_single_layer()
    return not ok


def probe_crossbar_corrupt():
    orig = CrossbarMVM.solve

    def bad_solve(self):
        return orig(self) * 1.5                     # 破坏阵列输出
    with patch.object(CrossbarMVM, "solve", bad_solve):
        ok, _ = chk_single_layer()
    return not ok


def main():
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA 电子计算征程 E3 · MVM 数据通路门禁（D-152）===")
    print("MVM_DATAPATH_DISCLOSURE:", mvm_datapath.MVM_DATAPATH_DISCLOSURE["route"])
    sc = mvm_datapath_self_check()
    print(f"自证桩: single8={sc['single_layer_8bit_max_err']:.5f} "
          f"mlp={sc['mlp_2layer_6bit_max_err']:.5f} "
          f"trend={sc['quant_trend_monotone_decreasing']} "
          f"tiling={sc['tiling_vs_full_max_err']:.2e}")

    # —— 绿：端到端正确性 ——
    ok, det = chk_single_layer()
    check("① 单层 8bit 数据通路 vs 全精度 golden", ok, det)
    ok, det = chk_quant_trend()
    check("② 量化趋势: 位数↑误差单调↓", ok, det)
    ok, det = chk_mlp_two_layer()
    check("③ 2 层 MLP(ReLU) 端到端 vs 数字 golden", ok, det)
    ok, det = chk_tiling()
    check("④ 分块合成 == 全阵 MVM", ok, det)
    ok, det = chk_crossbar_precision()
    check("⑤ 交叉阵列精度(隔离量化) vs golden", ok, det)
    check("⑥ 自证桩: 量化趋势判据为真", sc["quant_trend_monotone_decreasing"],
          str(sc["quant_error_by_bits"]))

    # —— 红：突变探针（必变红，否则为死断言）——
    check("🔴 ⑦ 突变探针: 破坏数字 golden 必红", probe_golden_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑧ 突变探针: 破坏量化器必红", probe_quantizer_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑨ 突变探针: 破坏交叉阵列 solve 必红", probe_crossbar_corrupt(),
          "未变红（死断言!）")

    # —— 还原完整性：突变后重跑绿，确无残留漂移 ——
    ok, det = chk_single_layer()
    check("⑩ 还原重跑: 单层无残留漂移", ok, det)
    ok, det = chk_mlp_two_layer()
    check("⑩ 还原重跑: MLP 无残留漂移", ok, det)

    if fails:
        print(f"\nE3 门禁: {len(fails)} FAIL -> {fails}")
        sys.exit(1)
    print("\nE3 门禁: ALL GREEN（含 3 道突变探针 + 还原完整性）")


if __name__ == "__main__":
    main()
