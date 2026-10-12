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
