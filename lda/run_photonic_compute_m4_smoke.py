# -*- coding: utf-8 -*-
"""P6 · 光计算征程 M4 · 规模扩张 / 阵列化（tiling）压力测试常驻门禁（L2 系统级）。

判据分组（A–K）
---------------
A 契约 / 披露（MESH_TILING 披露键齐全 + 关键立场字面：零能效 / 尺度盲 / tiling 架构）
B MZI 计数（reck_mzi_count == N(N−1)/2 闭式；reck_mzi_count(1)=0, (2)=1）
C 规模盲保真度（网格酉保真度 1−F 随 N 次线性，is_scale_blind 判 True）
D tiling 收益（局部标定环 ⇒ tiled 1−F < mono 1−F）
E 路由损耗（k=1 ⇒ 0 dB；随块数单调上升）
F 标定问题规模（monolithic==N(N−1)/2；per_tile==T(T−1)/2；缩减倍数≥1）
G 零能效守卫（m4_budget 必过；注入 pj_per_bit 必 raise）
H 输入域（N<1 / tile_size<1 / crossbar_db<0 必 raise；边界合法必过）
I 反向可证伪（注入「1−F 随 N 线性塌缩」或「恒为 0」⇒ is_scale_blind 必 False；注入真尺度盲 ⇒ True）
J 通用纪律（σ=0 ⇒ 保真度=1.0；量化致退化存在）
K 自入 core 校验（本文件在 CORE_SMOKES 内）

🔴 立场：断言的是**事实** —— C 断言规模盲（非恒真，注入线性塌缩会拉红）；D 断言 tiling 收益
（非恒真，断局部标定会拉红）；G 断言零能效（非恒真，加 pJ/bit 会拉红）。CI core 234→235。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check
from lda_l2.photonic_mesh_tiling import (  # noqa: E402
    verify_photonic_compute_m4,
    reck_mzi_count,
    n_mzi_formula,
    tile_layout,
    routing_loss_db,
    calibration_loop_size,
    mesh_transfer_with_noise,
    tiled_transfer,
    is_scale_blind,
    _random_unitary,
    MESH_TILING_DISCLOSURE,
)
from lda_l2.eic_behavioral import assert_no_energy_metrics  # noqa: E402
from lda_l2.optical_pareto import OpticalParetoError  # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}", detail_on="fail")


def _raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def main():  # noqa: C901
    print("=== P6 · 光计算征程 M4 · 规模扩张 / 阵列化（tiling）压力测试门禁 ===")
    r = verify_photonic_compute_m4()

    # ----------------------------------------------------------- A 契约 / 披露
    print("--- A 契约 / 披露 ---")
    check("A1 MESH_TILING 披露键齐全（>=10）", len(MESH_TILING_DISCLOSURE) >= 10,
          "%d 键" % len(MESH_TILING_DISCLOSURE))
    blob = " ".join(MESH_TILING_DISCLOSURE.values())
    check("A2 披露含「零能效数字」「尺度盲保真度」「tiling 阵列化架构」字面",
          "零能效数字" in blob and "尺度盲保真度" in blob and "tiling 阵列化" in blob)
    check("A3 披露含「不声称已实现千级 MZI 流片」字面", "不声称已实现千级 MZI 流片" in blob)

    # ----------------------------------------------------------- B MZI 计数
    print("--- B MZI 计数（reck 实际输出 == 闭式 N(N−1)/2）---")
    for N in (1, 2, 4, 8, 16, 32):
        check("B1 reck_mzi_count(%d) == %d 闭式" % (N, n_mzi_formula(N)),
              reck_mzi_count(N) == n_mzi_formula(N),
              "reck=%d formula=%d" % (reck_mzi_count(N), n_mzi_formula(N)))
    check("B2 reck_mzi_count(1)==0（单模无耦合）", reck_mzi_count(1) == 0)
    check("B3 reck_mzi_count(2)==1（双模一耦合器）", reck_mzi_count(2) == 1)

    # ----------------------------------------------------------- C 规模盲保真度
    print("--- C 规模盲保真度（1−F 随 N 次线性）---")
    sb = r["scale_blind"]
    check("C1 is_scale_blind 判定 True（N=8→256 实测）", sb["verdict"]["scale_blind"],
          "ratio_rel_std=%.3f fit_slope=%.5f" %
          (sb["verdict"]["ratio_rel_std"], sb["verdict"]["fit_slope"]))
    check("C2 ratio 跨 N 近似常数（相对标准差 < 10%）",
          sb["verdict"]["ratio_rel_std"] < 0.10,
          "%.4f" % sb["verdict"]["ratio_rel_std"])
    check("C3 1−F 不随 N 线性塌缩（sublinear_ok）", bool(sb["verdict"]["sublinear_ok"]),
          "fit_slope=%.5f ratio_rel_std=%.4f" %
          (sb["verdict"]["fit_slope"], sb["verdict"]["ratio_rel_std"]))

    # ----------------------------------------------------------- D tiling 收益
    print("--- D tiling 阵列化收益（局部标定环降噪）---")
    tl = r["tiling"]
    check("D1 tiled 平均 1−F < mono 平均 1−F（局部标定增益）",
          tl["tiled_one_minus_F"] < tl["mono_one_minus_F"],
          "mono=%.5f tiled=%.5f" % (tl["mono_one_minus_F"], tl["tiled_one_minus_F"]))
    check("D2 tiled_better 标志为真", bool(tl["tiled_better"]))

    # ----------------------------------------------------------- E 路由损耗
    print("--- E 块间路由损耗（交叉开关插入损耗）---")
    rt = r["routing"]
    check("E1 k=1（不切片）路由损耗 = 0 dB", rt["k1_db"] == 0.0, "%.2f" % rt["k1_db"])
    check("E2 路由损耗随块数单调上升（k1<=k2<=k4）", bool(rt["monotonic"]),
          "k1=%.1f k2=%.1f k4=%.1f" % (rt["k1_db"], rt["k2_db"], rt["k4_db"]))
    # 独立重算确认（不依赖 verify 的同一对象）
    c1 = routing_loss_db(128, 128); c2 = routing_loss_db(128, 16); c4 = routing_loss_db(128, 4)
    check("E3 重算路由损耗单调（128 网格：tile=128→16→4）",
          c1 <= c2 <= c4 and c1 == 0.0, "%.1f/%.1f/%.1f" % (c1, c2, c4))

    # ----------------------------------------------------------- F 标定问题规模
    print("--- F 标定问题规模（monolithic 单一大环 vs 每 tile 独立小环）---")
    cal = r["calibration"]
    N_t, T = 128, 16
    check("F1 monolithic_mzi == N(N−1)/2", cal["monolithic_mzi"] == n_mzi_formula(N_t),
          "%d vs %d" % (cal["monolithic_mzi"], n_mzi_formula(N_t)))
    check("F2 per_tile_mzi == T(T−1)/2", cal["per_tile_mzi"] == n_mzi_formula(T),
          "%d vs %d" % (cal["per_tile_mzi"], n_mzi_formula(T)))
    check("F3 缩减倍数 >= 1（tiling 必缩减问题规模）", cal["reduction_factor"] >= 1.0,
          "%.1f×" % cal["reduction_factor"])

    # ----------------------------------------------------------- G 零能效守卫
    print("--- G 零能效守卫（单一真值来源）---")
    from lda_l2.photonic_mesh_tiling import m4_budget  # noqa: E402
    b = m4_budget(256, 16)
    check("G1 m4_budget 零能效/功耗键名（机器可查 · 不 raise）",
          not _raises(lambda: assert_no_energy_metrics(b), OpticalParetoError))
    check("G2 预算含 n_mzi_total / routing_loss_db 键",
          "n_mzi_total" in b and "routing_loss_db" in b)
    check("G3 注入 pj_per_bit ⇒ assert_no_energy_metrics 必 raise",
          _raises(lambda: assert_no_energy_metrics({"pj_per_bit": 3.0}), OpticalParetoError))
    check("G4 注入 power_w ⇒ 必 raise",
          _raises(lambda: assert_no_energy_metrics({"power_w": 0.5}), OpticalParetoError))

    # ----------------------------------------------------------- H 输入域
    print("--- H 输入域 ---")
    check("H1 reck_mzi_count(0) 必 raise", _raises(lambda: reck_mzi_count(0)))
    check("H2 tile_layout(N, 0) 必 raise", _raises(lambda: tile_layout(128, 0)))
    check("H3 tile_layout(0, 1) 必 raise", _raises(lambda: tile_layout(0, 1)))
    check("H4 routing_loss_db(N, T, -1) 必 raise", _raises(lambda: routing_loss_db(128, 16, -1.0)))
    check("H5 边界合法（N=1, tile=1）⇒ 必过",
          not _raises(lambda: (reck_mzi_count(1), tile_layout(1, 1), routing_loss_db(1, 1))))

    # ----------------------------------------------------------- I 反向可证伪
    print("--- I 反向可证伪（is_scale_blind 判别力）---")
    Ns = [8, 16, 32, 64]
    # 注入「1−F 随 N 线性塌缩」（翻倍）→ ratio 暴涨 → 应判 False（防死度量/防误判）
    collapse = [0.01 * (2 ** i) for i in range(len(Ns))]
    v_collapse = is_scale_blind(Ns, collapse)
    check("I1 注入线性塌缩序列 ⇒ is_scale_blind 必 False", not v_collapse["scale_blind"])
    # 注入「恒为 0」（死度量）→ all_positive 失败 → 应判 False
    zeros = [0.0, 0.0, 0.0, 0.0]
    v_zero = is_scale_blind(Ns, zeros)
    check("I2 注入全零序列（死度量）⇒ is_scale_blind 必 False", not v_zero["scale_blind"])
    # 注入真·尺度盲序列（1−F = c·√((N−1)/N)）→ 应判 True（证明检查能识别真信号，非恒 False）
    c_const = 0.03
    genuine = [c_const * math.sqrt((n - 1) / n) for n in Ns]
    v_genuine = is_scale_blind(Ns, genuine)
    check("I3 注入真尺度盲序列 ⇒ is_scale_blind 必 True（检查有判别力，非恒 False）",
          v_genuine["scale_blind"])

    # ----------------------------------------------------------- J 通用纪律
    print("--- J 通用纪律（reverse 反例）---")
    U = _random_unitary(64, seed=7)
    _, fid_zero_mono = mesh_transfer_with_noise(U, 0.0, seed=7)
    _, fid_zero_tiled = tiled_transfer(U, 0.0, 16, seed=7)
    check("J1 σ=0 ⇒ monolithic 保真度 == 1.0（无噪声完美复现）",
          abs(fid_zero_mono - 1.0) < 1e-9, "%.15f" % fid_zero_mono)
    check("J2 σ=0 ⇒ tiled 保真度 == 1.0", abs(fid_zero_tiled - 1.0) < 1e-9,
          "%.15f" % fid_zero_tiled)
    _, fid_noisy = mesh_transfer_with_noise(U, 0.05, seed=7)
    check("J3 量化/噪声致退化（σ=0.05 保真度 < 1.0）", fid_noisy < 1.0,
          "%.6f" % fid_noisy)

    # ----------------------------------------------------------- K 自入 core 校验
    print("--- K 自入 core 校验 ---")
    import run_ci_regression as R  # noqa: E402
    check("K1 本 smoke 在 CORE_SMOKES 内",
          "run_photonic_compute_m4_smoke.py" in R.CORE_SMOKES,
          "CORE_SMOKES 共 %d 条" % len(R.CORE_SMOKES))

    print("=" * 74)
    print("P6 · 光计算征程 M4 · 规模扩张 / tiling 压力测试：%d PASS / %d FAIL" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
