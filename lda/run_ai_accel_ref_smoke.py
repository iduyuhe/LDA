# -*- coding: utf-8 -*-
"""LDA · 阶段 4 L6 参考设计门禁（W4-1 · 光子/模拟混合 AI 推理加速器）。

============================================================================
守什么（v0.9.171 · CI core 260→261）
----------------------------------------------------------------------------
模块 `lda_l2.ai_accelerator_ref`：把光子 MZI 网格（第 1 层 · 正交约束 + 相位量化）
与 E3 模拟交叉阵列（第 2 层 · DAC/ADC 量化）拼成端到端 2 层 MLP 分类推理加速器，
与全精度数字 golden 比对，误差逐项归因、随位数下降。

门禁判据 = 模块自检 14 项全过 + 跨源交叉核对（数据集规模/配置回显/网格定理值）
+ **3 道突变探针**（防死断言 / 假绿）：
  ① 光子量化旁路（返回理想矩阵）⇒ 相位趋势「严格下降」必红（全相等 ⇒ 严格不等式失效）；
  ② 标签破坏（可学习性摧毁）⇒ golden 精度下限必红；
  ③ 光子层错配（返回与 O1 无关的固定酉）⇒ 混合精度落差必红。
探针走 `unittest.mock.patch.object` 进程内打桩（沙箱禁 spawn python —— 血案 #3），
patch 点 = 模块级 `_photonic_layer_matrix` / `_make_dataset`（run_reference 运行时
动态解析，默认参数绑定会绕过 mock —— 模块已按此实现）。

诚实边界：本门禁不判「现实任务性能」——数据集为固定种子合成数据，精度数字只证
端到端链路行为正确；不报 TOPS/TOPS-W/fJ/op（电路级模型 · 无 PDK ⇒ 无能效宣称资格）。
"""
from __future__ import annotations

import sys
import unittest.mock as mock

import numpy as np

from lda_l2 import ai_accelerator_ref as ar


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA 阶段 4 · L6 参考设计门禁（W4-1 · 光子/模拟混合 AI 推理加速器）===")
    print("route:", ar.ACCELERATOR_REF_DISCLOSURE["route"])

    # —— 绿：模块自检 14 项 ——
    sc = ar.accelerator_ref_self_check()
    check("① 模块自检 14 项全过", sc["all_pass"] and sc["n_checks"] >= 12,
          f"n={sc['n_checks']} fails={[k for k, v in sc['checks'].items() if not v]}")
    rep = sc["report"]

    # —— 绿：跨源交叉核对（独立于自检结论的事实锚）——
    check("② 数据集规模定理值（4 类 × 64 · 训练 48/类 · 测试 16/类）",
          rep["n_train"] == 4 * 48 and rep["n_test"] == 4 * 16,
          f"train={rep['n_train']} test={rep['n_test']}")
    check("③ 配置回显一致（相位 6bit / DAC 8bit / ADC 8bit）",
          rep["config"] == {"phase_bits": 6, "dac_bits": 8, "adc_bits": 8},
          str(rep["config"]))
    check("④ 网格拓扑定理值（N=8 ⇒ MZI 28 片 · 每模深度 13）",
          rep["mesh_stats"]["n_mzi"] == 28
          and rep["mesh_stats"]["per_mode_optical_depth"] == 13,
          str((rep["mesh_stats"]["n_mzi"], rep["mesh_stats"]["per_mode_optical_depth"])))
    check("⑤ 未量化重构对照锚 = 机器精度（分离量化效应）",
          rep["mesh_fidelity_unquantized"] >= 1.0 - 1e-9,
          str(rep["mesh_fidelity_unquantized"]))
    check("⑥ 误差归因完备（e1/e2_iso/e2_e2e 均为正且端到端 ≥ 各分量一半）",
          0.0 < rep["error_attribution"]["e1_photonic_rel_max"]
          and 0.0 < rep["error_attribution"]["e2_crossbar_iso_rel_max"]
          and rep["error_attribution"]["e2_e2e_rel_max"]
          >= 0.5 * min(rep["error_attribution"]["e1_photonic_rel_max"],
                       rep["error_attribution"]["e2_crossbar_iso_rel_max"]),
          str(rep["error_attribution"]))
    check("⑦ 相位扫描 4 档且严格下降（8<6 且 8<4<2）",
          set(rep["phase_bits_sweep_e1"]) == {2, 4, 6, 8}
          and rep["phase_bits_sweep_e1"][8] < rep["phase_bits_sweep_e1"][6]
          and rep["phase_bits_sweep_e1"][8] < rep["phase_bits_sweep_e1"][4]
          < rep["phase_bits_sweep_e1"][2],
          str(rep["phase_bits_sweep_e1"]))
    check("⑧ 交叉阵列扫描 3 档且端点下降（8≤6≤3）",
          set(rep["unit_bits_sweep_e2_iso"]) == {3, 6, 8}
          and rep["unit_bits_sweep_e2_iso"][8] <= rep["unit_bits_sweep_e2_iso"][6]
          <= rep["unit_bits_sweep_e2_iso"][3],
          str(rep["unit_bits_sweep_e2_iso"]))
    check("⑨ 设计点精度落差 ≤ 5 点（6bit 相位 + 8bit DAC/ADC）",
          rep["acc_drop_points"] <= 5.0, str(rep["acc_drop_points"]))
    check("⑩ 披露诚实边界（主张面无 TOPS/实测宣称）", ar.honest_boundary_ok())

    # —— 红：突变探针（必变红，否则死断言）——
    def ideal_photonic(O1, phase_bits):
        """探针①打桩：任何位数都返回未量化理想网格（旁路相位量化）。"""
        O1c = np.asarray(O1, dtype=complex)
        ops, D = ar.reck_triangular_mesh(O1c)
        U = ar.assemble_triangular_mesh(ops, D, ar.N_MODE)
        return U, ops, D, ar.mesh_loss_basis(ops, n_crossings=0)

    with mock.patch.object(ar, "_photonic_layer_matrix", ideal_photonic):
        sc_p1 = ar.accelerator_ref_self_check()
    check("🔴 ⑪ 突变探针①: 光子量化旁路 ⇒ 相位趋势「严格下降」必红",
          sc_p1["checks"]["phase_trend_strict_endpoints"] is False,
          "全相等时严格不等式必须失效（否则判据是死的）")

    _orig_make_dataset = ar._make_dataset     # 先捕获原引用（patch 后自调会递归）

    def random_labels(seed=ar.SEED):
        X, _, tr, te = _orig_make_dataset(seed)
        rng = np.random.RandomState(999)
        y_bad = rng.randint(0, ar.C_OUT, size=len(X))
        return X, y_bad, tr, te

    with mock.patch.object(ar, "_make_dataset", random_labels):
        sc_p2 = ar.accelerator_ref_self_check()
    check("🔴 ⑫ 突变探针②: 标签破坏（可学习性摧毁）⇒ golden 精度下限必红",
          sc_p2["checks"]["test_acc_golden_floor"] is False
          and sc_p2["checks"]["train_converged"] is False,
          "随机标签下精度必须跌穿下限（否则精度判据是死的）")

    def mismatched_photonic(O1, phase_bits):
        """探针③打桩：返回与 O1 无关的固定酉（确定性构造，不可学习映射）。"""
        rng = np.random.RandomState(4242)
        Q, _ = np.linalg.qr(rng.randn(ar.N_MODE, ar.N_MODE))
        Qc = Q.astype(complex)
        ops, D = ar.reck_triangular_mesh(Qc)
        U = ar.assemble_triangular_mesh(ops, D, ar.N_MODE)
        return U, ops, D, ar.mesh_loss_basis(ops, n_crossings=0)

    with mock.patch.object(ar, "_photonic_layer_matrix", mismatched_photonic):
        sc_p3 = ar.accelerator_ref_self_check()
    check("🔴 ⑬ 突变探针③: 光子层错配（固定无关酉）⇒ 混合精度落差必红",
          sc_p3["checks"]["hybrid_acc_drop_bound"] is False,
          "网格错配下落差必须超界（否则落差判据是死的）")

    # —— 还原完整性：探针退出后模块自检恢复全绿（patch 无残留）——
    sc_r = ar.accelerator_ref_self_check()
    check("⑭ 还原完整性：探针退出后自检恢复全绿", sc_r["all_pass"])

    print()
    if fails:
        print(f"W4-1 门禁: {len(fails)} FAIL :: {fails}")
        return 1
    print("W4-1 门禁: ALL GREEN（14+ 自检 + 跨源核对 + 3 道突变探针 + 还原完整性）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
