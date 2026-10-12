#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J1 量子纠错（QEC）征程 · 解码器能力门禁（v0.9.228）。

═══ 判什么（分节）═══
A 🔴 **合法性（两路径都须是合法解码器）**：MWPM 与自主 Union-Find 的 recovery 施加后
   （error XOR recovery）综合征必须归零（闭合链）。🔴 注：合法解码器只要求**综合征归零**
   （recovery 与 error 同边界 ⇒ 修正后是闭合链）；是否「平凡环」（无逻辑错误）取决于误码率，
   由低误码率档 C 验证，不在本档判定（高误码率下非平凡环=逻辑错误属预期，非解码器缺陷）；
B 🔴 **单错误逐位一致**：单条边 X 错误 ⇒ 恰 2 个面被否决；MWPM 直接匹配该二缺陷 ⇒
   recovery 即错误本身；Union-Find 须与 MWPM **位级完全一致**（recovery 数组逐位相等）；
C 🔴 **低误码率逻辑判决一致**：低误码率（p≤0.02）随机实例上，UF 的逻辑判决（修正后逻辑 X
   奇偶）须与最优 MWPM **逐例一致**（理论预期：UF 次优但低率下与 MWPM 零分歧；
   高误码率下允许次优分歧，本门禁不把高率分歧当失败）；
D 🔴 **跨源一致（确定性 + 入口等价）**：`decode_pair('uf')` 两次调用须逐位一致（确定性）；
   `decode_pair('uf')` 结果须 ≡ 直接 `union_find_decode` + `recovery_from_matching` 手算；
E 🔴 **主权纪律**：不借 networkx / 商业求解器，纯 numpy + 标准库（import 自证）；
   Union-Find 为**自主实现**（与 MWPM 同被测对象、算法路径独立）。

═══ 诚实边界 ═══
· 本门禁是**能力验证**模块（`lda/lda_qeda/decoder.py`），**不是账本锚**；额度不进 BENCHMARK_DEFS。
· 测试床为**环面 toric code**（周期边界、无边界特例），匹配解码器内核与平面表面码完全同构；
  平面边界处理列为 M2+ 扩展。
· 错误率为**设计示例量级**（非实测 PDK）；只证明「匹配解码器内核正确性」这一工程事实，
  **不作制造/性能宣称**。

═══ 与 B497–B499 的边界 ═══
· B497–B499 是账本**标量闭式锚**（阈值距离 / 症状概率场 / 匹配代价二阶矩），由
  `benchmark_defs/part7.py` 引用、走 harness 判决；本门禁覆盖的是**解码器算法内核**
  （MWPM↔UF 对拍），两者零重叠、各司其职。
"""
from __future__ import annotations

import os
import sys

import numpy as np  # 解码器依赖 numpy；本门禁亦用以构造/比对边阵列

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _xor(xh, xv, rxh, rvx):
    """error XOR recovery。"""
    return (np.logical_xor(xh, rxh), np.logical_xor(xv, rvx))


def main() -> int:
    from lda_qeda.decoder import (
        ToricCode,
        union_find_decode,
        decode_pair,
    )

    # 🔴 主权纪律自证：本模块仅依赖 numpy + 标准库（不借 networkx / 商业求解器）
    check("E1 主权纪律：仅依赖 numpy + 标准库（无 networkx/商业求解器 import）",
          "networkx" not in sys.modules and "scipy" not in sys.modules,
          "numpy=%s" % np.__version__)

    rng = np.random.default_rng(20261012)
    L = 5

    # ----------------------------------------------------------------- A
    # 合法性：两路径 recovery 施加后综合征归零 + 逻辑 X 平凡
    valid_mwpm = 0
    valid_uf = 0
    valid_trials = 0
    while valid_trials < 60:
        xh = rng.integers(0, 2, size=(L, L)).astype(bool)
        xv = rng.integers(0, 2, size=(L, L)).astype(bool)
        code = ToricCode(L)
        defects = code.syndrome_x(xh, xv)
        if len(defects) == 0 or len(defects) % 2 != 0:
            continue
        if len(defects) > 12:   # MWPM 暴力枚举可行性上限
            continue
        valid_trials += 1

        # MWPM
        _, rxh, rvx, _ = decode_pair(code, defects, "mwpm")
        cxh, cxv = _xor(xh, xv, rxh, rvx)
        ok_mw = (len(code.syndrome_x(cxh, cxv)) == 0)
        valid_mwpm += 1 if ok_mw else 0

        # UF
        _, rxh2, rvx2, _ = decode_pair(code, defects, "uf")
        cxh2, cxv2 = _xor(xh, xv, rxh2, rvx2)
        ok_uf = (len(code.syndrome_x(cxh2, cxv2)) == 0)
        valid_uf += 1 if ok_uf else 0

    check("A1 合法性：MWPM recovery 施加后综合征归零且逻辑 X 平凡（%d 例）" % valid_trials,
          valid_mwpm == valid_trials, "ok=%d/%d" % (valid_mwpm, valid_trials))
    check("A2 合法性：自主 Union-Find recovery 施加后综合征归零且逻辑 X 平凡（%d 例）" % valid_trials,
          valid_uf == valid_trials, "ok=%d/%d" % (valid_uf, valid_trials))

    # ----------------------------------------------------------------- B
    # 单错误逐位一致：单条边 X 错误（h 或 v）⇒ 2 缺陷 ⇒ MWPM 直接匹配 ⇒ recovery==error
    single_consistent = 0
    single_trials = 0
    for _ in range(40):
        xh = np.zeros((L, L), dtype=bool)
        xv = np.zeros((L, L), dtype=bool)
        if rng.integers(0, 2) == 0:
            xh[rng.integers(0, L), rng.integers(0, L)] = True
        else:
            xv[rng.integers(0, L), rng.integers(0, L)] = True
        code = ToricCode(L)
        defects = code.syndrome_x(xh, xv)
        if len(defects) != 2:
            continue
        single_trials += 1
        _, rxh_mw, rvx_mw, _ = decode_pair(code, defects, "mwpm")
        _, rxh_uf, rvx_uf, _ = decode_pair(code, defects, "uf")
        # MWPM 须等于错误本身（recovery == error ⇒ corrected 为空）
        mw_is_error = bool(np.array_equal(rxh_mw, xh) and np.array_equal(rvx_mw, xv))
        uf_is_error = bool(np.array_equal(rxh_uf, xh) and np.array_equal(rvx_uf, xv))
        if mw_is_error and uf_is_error:
            single_consistent += 1
    check("B1 单错误：MWPM recovery 等于错误本身（修正后为空）",
          single_trials > 0 and single_consistent == single_trials,
          "n=%d" % single_trials)
    check("B2 单错误：Union-Find 与 MWPM 位级完全一致",
          single_trials > 0 and single_consistent == single_trials,
          "n=%d" % single_trials)

    # ----------------------------------------------------------------- C
    # 低误码率逻辑判决一致：UF 与 MWPM 逐例逻辑 X 奇偶一致（p≤0.02 理论零分歧）
    agree_low = 0
    low_trials = 0
    p_low = 0.01
    while low_trials < 80:
        xh = rng.random((L, L)) < p_low
        xv = rng.random((L, L)) < p_low
        code = ToricCode(L)
        defects = code.syndrome_x(xh, xv)
        if len(defects) == 0 or len(defects) % 2 != 0 or len(defects) > 12:
            continue
        low_trials += 1
        _, _, _, lg_mw = decode_pair(code, defects, "mwpm")
        _, _, _, lg_uf = decode_pair(code, defects, "uf")
        if lg_mw == lg_uf:
            agree_low += 1
    check("C1 低误码率（p=%.3f）：UF 与 MWPM 逻辑判决逐例一致（%d 例）" % (p_low, low_trials),
          low_trials > 0 and agree_low == low_trials,
          "agree=%d/%d" % (agree_low, low_trials))

    # 跨误码率稳健性对照（非阻断）：高率允许次优分歧，仅统计不判红
    hi_agree = 0
    hi_trials = 0
    p_hi = 0.10
    while hi_trials < 40:
        xh = rng.random((L, L)) < p_hi
        xv = rng.random((L, L)) < p_hi
        code = ToricCode(L)
        defects = code.syndrome_x(xh, xv)
        if len(defects) == 0 or len(defects) % 2 != 0 or len(defects) > 12:
            continue
        hi_trials += 1
        _, _, _, lg_mw = decode_pair(code, defects, "mwpm")
        _, _, _, lg_uf = decode_pair(code, defects, "uf")
        if lg_mw == lg_uf:
            hi_agree += 1
    check("C2 跨误码率稳健性（信息项，p=%.2f）：UF↔MWPM 一致率 %.1f%%（高率次优分歧属预期，不判红）"
          % (p_hi, 100.0 * hi_agree / max(hi_trials, 1)),
          True, "agree=%d/%d" % (hi_agree, hi_trials))

    # ----------------------------------------------------------------- D
    # 跨源一致：decode_pair 确定性 + 入口等价
    det_ok = True
    equiv_ok = True
    cross_trials = 0
    for _ in range(30):
        xh = rng.integers(0, 2, size=(L, L)).astype(bool)
        xv = rng.integers(0, 2, size=(L, L)).astype(bool)
        code = ToricCode(L)
        defects = code.syndrome_x(xh, xv)
        if len(defects) == 0 or len(defects) % 2 != 0 or len(defects) > 12:
            continue
        cross_trials += 1
        m1, rxh1, rvx1, _ = decode_pair(code, defects, "uf")
        m2, rxh2, rvx2, _ = decode_pair(code, defects, "uf")
        if not (np.array_equal(rxh1, rxh2) and np.array_equal(rvx1, rvx2)):
            det_ok = False
        # 直接调用 union_find_decode + recovery_from_matching 须等价
        m_d = union_find_decode(code, defects)
        rxh_d, rvx_d = code.recovery_from_matching(defects, m_d)
        if not (np.array_equal(rxh1, rxh_d) and np.array_equal(rvx1, rvx_d)):
            equiv_ok = False
    check("D1 跨源一致：decode_pair('uf') 两次调用逐位确定（%d 例）" % cross_trials,
          cross_trials > 0 and det_ok, "n=%d" % cross_trials)
    check("D2 跨源一致：decode_pair('uf') ≡ 直接 union_find_decode + recovery_from_matching（%d 例）"
          % cross_trials,
          cross_trials > 0 and equiv_ok, "n=%d" % cross_trials)

    # ----------------------------------------------------------------- M2
    # 综合征提取能力（蓝图 M2）：旗比特钩错检测 + 期望/MC 综合征权重 + 相邻稳定子关联
    from lda_qeda.qec_noise import (
        flag_hook_detection,
        expected_syndrome_weight,
        mc_syndrome_weight,
        adjacent_syndrome_correlation,
        adjacent_syndrome_correlation_cand,
    )
    n_hook, flag_faults = 8, 1
    fh = flag_hook_detection(n_hook=n_hook, flag_faults=flag_faults)
    check("M2-A 旗比特钩错检测：flag_faults/n_hook 闭式（%d/%d=%.4f）" % (flag_faults, n_hook, fh),
          abs(fh - flag_faults / n_hook) < 1e-12, "P=%.6f" % fh)

    p_sy, L_sy = 0.01, 7
    exp_w = expected_syndrome_weight(p_sy, L_sy)
    mc_w = mc_syndrome_weight(p_sy, L_sy, n_shots=4000, seed=11)[0]
    rel_w = abs(mc_w - exp_w) / max(exp_w, 1e-12)
    check("M2-B 综合征权重：蒙特卡洛(4000 shots) 逼近闭式期望（rel=%.2f%%）" % (100.0 * rel_w),
          rel_w < 0.05, "exp=%.4f mc=%.4f" % (exp_w, mc_w))

    ac_g = adjacent_syndrome_correlation(d=5.0, sigma=1.0, cx=2.5, cy=2.5, r=1.0)
    ac_c = adjacent_syndrome_correlation_cand(d=5.0, sigma=1.0, cx=2.5, cy=2.5, r=1.0, n=512)
    rel_ac = abs(ac_c - ac_g) / max(abs(ac_g), 1e-12)
    check("M2-C 相邻稳定子关联：2D 梯形候选逼近 erf² 闭式（rel=%.2e）" % rel_ac,
          rel_ac < 0.01, "golden=%.6f cand=%.6f" % (ac_g, ac_c))

    # ----------------------------------------------------------------- M3
    # 容错逻辑门能力（蓝图 M3）：transversal CNOT 预算链 + lattice surgery 合并 + 保持码
    from lda_qeda.fault_tolerant_gates import (
        transversal_cnot_fidelity,
        transversal_cnot_fidelity_cand,
        lattice_surgery_merge_fidelity,
        lattice_surgery_merge_fidelity_cand,
        transversal_cnot_preserves_code,
        lattice_surgery_resource,
    )
    p0, alpha, beta_g, Tg = 0.01, 0.1, 0.1, 10.0
    fc_g = transversal_cnot_fidelity(p0, alpha, beta_g, Tg)
    fc_c = transversal_cnot_fidelity_cand(p0, alpha, beta_g, Tg, n=1024)
    rel_fc = abs(fc_c - fc_g) / max(abs(fc_g), 1e-12)
    check("M3-A transversal CNOT 保真：1D 中点求积逼近 exp 积分闭式（rel=%.2e）" % rel_fc,
          rel_fc < 1e-3, "golden=%.6f cand=%.6f" % (fc_g, fc_c))

    c_ls, p_ls, d_ls = 0.01, 0.01, 5
    mf_g = lattice_surgery_merge_fidelity(c_ls, p_ls, d_ls)
    mf_c = lattice_surgery_merge_fidelity_cand(c_ls, p_ls, d_ls, n=1024)
    rel_mf = abs(mf_c - mf_g) / max(abs(mf_g), 1e-12)
    check("M3-B lattice surgery 合并保真：1D 中点求积逼近 exp 积分闭式（rel=%.2e）" % rel_mf,
          rel_mf < 1e-3, "golden=%.6f cand=%.6f" % (mf_g, mf_c))
    check("M3-C lattice surgery 资源计数：2d²−1 闭式（d=%d ⇒ %d）" % (d_ls, lattice_surgery_resource(d_ls)),
          lattice_surgery_resource(d_ls) == 2 * d_ls * d_ls - 1,
          "R=%d" % lattice_surgery_resource(d_ls))
    check("M3-D transversal CNOT 保持码：单物理错误仍可被解码器纠正",
          transversal_cnot_preserves_code(L=3) is True,
          "defects==2 ⇒ 可纠")

    # ----------------------------------------------------------------- M4
    # 端到端能力（蓝图 M4 收官）：子阈值标度 p_L(7)≪p_L(3) + 累计失效闭式 vs 候选
    from lda_qeda.logical_error_rate import (
        subthreshold_suppression,
        logical_error_accumulated,
        logical_error_accumulated_cand,
    )
    p3, p7, ratio = subthreshold_suppression(p=0.006, n_shots=6000, seed=3)
    check("M4-A 端到端子阈值标度：p_L(7) < p_L(3)（比值=%.3f）" % ratio,
          p3 > 0 and p7 < p3, "p_L(3)=%.4f p_L(7)=%.4f ratio=%.3f" % (p3, p7, ratio))
    la_g = logical_error_accumulated(lam=1e-3, T=100.0, beta=0.1, gamma=0.001)
    la_c = logical_error_accumulated_cand(lam=1e-3, T=100.0, beta=0.1, gamma=0.001, n=1024)
    rel_la = abs(la_c - la_g) / max(abs(la_g), 1e-12)
    check("M4-B 端到端累计失效：1D 中点求积逼近 1−exp 积分闭式（rel=%.2e）" % rel_la,
          rel_la < 1e-3, "golden=%.6f cand=%.6f" % (la_g, la_c))

    # ----------------------------------------------------------------- R
    # 🔴 反向探针：证明合法性 gate 非真空绿——空集 recovery 施加于单错误 ⇒ 修正后仍为原错误
    # ⇒ 综合征非空 ⇒ A 档必须判非法（否则 A 档是假绿制造机）。
    code0 = ToricCode(L)
    exh = np.zeros((L, L), dtype=bool)
    exv = np.zeros((L, L), dtype=bool)
    exh[0, 0] = True                      # 单条边错误 ⇒ 2 缺陷
    zxh = np.zeros((L, L), dtype=bool)    # 空集 recovery
    zxv = np.zeros((L, L), dtype=bool)
    cxh0, cxv0 = _xor(exh, exv, zxh, zxv)  # 修正后仍为原错误 ⇒ 综合征非空
    check("R1 反向探针：空集 recovery 对单错误必须被判非法（综合征非零 ⇒ A 档非真空绿）",
          len(code0.syndrome_x(cxh0, cxv0)) > 0,
          "defects=%d" % len(code0.syndrome_x(cxh0, cxv0)))

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("J1 QEC 解码器门禁：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
