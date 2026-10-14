#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J3 量子测控与读出征程（M0–M4）· 门禁的**突变探针**（逐条必红 + 还原复绿）。

═══════════════════════════════════════════════════════════════════════════
为什么需要这一层
═══════════════════════════════════════════════════════════════════════════
门禁自身有 in-gate 反向探针（A4/B3/B4/F4/G4/H4/E1b…），但它们都在**门禁内部**构造。
本脚本从**模块外部**对门禁所依赖的**同一模块对象**做突变，再跑**整道门禁**，
并断言**预期判据 id** 出现在 `[FAIL]` 行里（不是只看 `FAIL>0`）：

  M1  无突变（baseline）                         ⇒ 全绿（44 PASS / 0 FAIL）
  M2  B510 候选退回自证桩（cand ≡ golden）        ⇒ A1 必红（|Δ|≡0）
  M3  B510 候选粗化（步数强制 n=4）               ⇒ A1 必红（残差 > tol）
  M4  B510 候选忽略请求步数（恒 n=128）           ⇒ A2 必红（残差与离散参数无关）
  M5  B510 候选丢弃驱动幅度 Ω（被扰键）           ⇒ A3/A4 必红（不随参数走）
  M6  B511 候选退回自证桩（cand ≡ golden）        ⇒ B1 必红
  M7  B511 候选忽略请求步数（恒 n=256）           ⇒ B2 必红
  M8  B511 触发 RK4 稳定性越界档（t=100, n=8）    ⇒ B1/B2 必红（发散 ≫ tol）
  M9  能力层 rabi_population 破坏（恒 0）         ⇒ C2/D1 必红
  M10 能力层 qutrit_leakage 破坏（恒 0）          ⇒ D1 必红
  M11 DRAG 抑制趋势反转（β=1 泄漏 > β=0）         ⇒ C2/D2 必红
  M12 闭环定标不收敛（converged 恒 False）        ⇒ C3/D3 必红
  M13 捕获范围守卫抹掉（diverged 恒 False）       ⇒ D4 必红
  M14 读出误判链破坏（恒 0）                      ⇒ C3/E1a/e1b 必红
  M15 签核与三环脱钩（强报 ACCEPT）               ⇒ C3/D4 必红
  M16 tol 三表漂移（_TOL_BY_BID["B510"]=1e-12）   ⇒ E2 必红
  M17 候选键回退（B510 candidate 改名）           ⇒ A5 必红
  M18 B512 候选退回自证桩                         ⇒ F1 必红
  M19 B512 候选忽略请求步数                       ⇒ F2 必红
  M20 B512 候选丢弃去极化率 Γ（被扰键）           ⇒ F3 必红
  M21 B513 候选退回自证桩                         ⇒ G1 必红
  M22 B513 候选忽略请求步数                       ⇒ G2 必红
  M23 B513 候选丢弃 qubit 频率 f_q（被扰键）      ⇒ G3 必红
  M24 B514 候选退回自证桩                         ⇒ H1 必红
  M25 B514 候选忽略请求步数                       ⇒ H2 必红
  M26 能力层 rb_benchmark 纯度衰减口径错（不随 Γ 走）⇒ J1 必红
  M27 能力层 readout_demod Purcell 破坏（恒 1）   ⇒ J1 必红
  M28 能力层 cryo_electronics 分布式噪声破坏      ⇒ J1 必红
  M29 总装签核脱钩（强报 REJECT）                 ⇒ I4 必红
  M30 tol 三表漂移（_TOL_BY_BID["B512"]=1e-12）   ⇒ K1 必红
  M31 候选键回退（B513 candidate 改名）           ⇒ G5 必红
  M32 全部还原                                       ⇒ 复绿（还原完整性）

🔴 惯例：`scripts/*_probe.py` **不入 CI**（人工复核用）；in-process monkeypatch
   **不碰源文件** ⇒ 无需文件还原/哈希复核。
运行：python scripts/d154_j3_probe.py
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_j3_ctrl_smoke as S            # noqa: E402
from lda_harness import benchmarks as BM  # noqa: E402

J3 = S.J3
QD = S.QD
CC = S.CC
PL = S.PL
RB = S.RB
RD = S.RD
CE = S.CE

_FAIL_RE = re.compile(r"\[FAIL\]\s+([A-Z]\d+[ab]?)")


def run_smoke():
    """跑整道门禁，返回 (rc, FAIL 数, 失败判据 id 集合, 输出)。"""
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                     # 突变致病态 ⇒ 崩溃也算红
        rc = 99
        buf.write("[FAIL] X0 门禁异常：%s: %s" % (type(e).__name__, e))
    out = buf.getvalue()
    ids = set(_FAIL_RE.findall(out))
    return rc, out.count("[FAIL]"), ids, out


def _green(ids):
    return not ids


def main() -> int:
    _c510, _c511, _c512, _c513, _c514 = (J3.cand_b510, J3.cand_b511, J3.cand_b512,
                                         J3.cand_b513, J3.cand_b514)
    _g510 = J3.golden_b510
    _g512, _g513, _g514 = J3.golden_b512, J3.golden_b513, J3.golden_b514
    _rb_purity = RB.purity_decay_analytic
    _rd_purcell = RD.purcell_suppression
    _ce_dist = CE.distributed_amp_nadd
    _full = CC.full_control_loop_report
    _tol512 = J3._TOL_BY_BID["B512"]
    _cand513_key = BM.BENCHMARK_DEFS["B513"]["candidate"]
    _rabi, _leak = QD.rabi_population, QD.qutrit_leakage
    _drag = QD.drag_leakage
    _calib = CC.rabi_amplitude_calibrate
    _report = CC.control_loop_report
    _eps = CC.readout_error_probability
    _tol510 = J3._TOL_BY_BID["B510"]
    _cand510_key = BM.BENCHMARK_DEFS["B510"]["candidate"]

    rows = []

    def rec(tag, expect_ids, rc, nfail, ids, _out):
        ok = (rc != 0) and (nfail > 0)
        if expect_ids:
            ok = ok and bool(set(expect_ids) & ids)
        else:                                   # baseline / 还原档：须全绿
            ok = (rc == 0) and (nfail == 0) and _green(ids)
        rows.append((tag, sorted(ids), ok))

    # M1 —— baseline
    rec("M1 baseline 无突变（须全绿）", set(), *run_smoke())

    # M2 —— B510 候选退回自证桩
    J3.cand_b510 = lambda **k: float(_g510(**k))
    rec("M2 B510 候选退回自证桩（cand≡golden）", {"A1"}, *run_smoke())
    J3.cand_b510 = _c510

    # M3 —— B510 候选粗化（n=4）
    J3.cand_b510 = lambda **k: float(_c510(**{**k, "n": 4}))
    rec("M3 B510 候选粗化（步数强制 n=4）", {"A1"}, *run_smoke())
    J3.cand_b510 = _c510

    # M4 —— B510 候选忽略请求步数
    J3.cand_b510 = lambda **k: float(_c510(**{**k, "n": 128}))
    rec("M4 B510 候选忽略请求步数（残差与步数无关）", {"A2"}, *run_smoke())
    J3.cand_b510 = _c510

    # M5 —— B510 候选丢弃驱动幅度 Ω（**正是反向探针扰动的那一个键** ⇒ 候选不随参数走）
    #   🔴 本轮血案：初版改成「丢弃失谐 δ」，而反向探针扰动的是 Ω ⇒ 候选仍响应 ⇒ 门禁仍全绿。
    #     教训：**突变必须打在被门禁扰动/检出的那一个键上**，否则「变异无效」会被误读成「护栏不响」。
    J3.cand_b510 = lambda **k: float(_c510(Omega=0.05,
                                           delta=float(k.get("delta", 0.03)),
                                           t=float(k.get("t", 100.0)),
                                           n=int(k.get("n", 128))))
    rec("M5 B510 候选丢弃驱动幅度 Ω（不随被扰键走）", {"A3"}, *run_smoke())
    J3.cand_b510 = _c510

    # M6 —— B511 候选退回自证桩
    J3.cand_b511 = lambda **k: float(J3.golden_b511(**k))
    rec("M6 B511 候选退回自证桩（cand≡golden）", {"B1"}, *run_smoke())
    J3.cand_b511 = _c511

    # M7 —— B511 候选忽略请求步数
    J3.cand_b511 = lambda **k: float(_c511(**{**k, "n": 256}))
    rec("M7 B511 候选忽略请求步数（残差与步数无关）", {"B2"}, *run_smoke())
    J3.cand_b511 = _c511

    # M8 —— B511 触发 RK4 稳定性越界档（含 α 实对角项 ⇒ |hα|=3.75 > 2√2 ⇒ 发散）
    J3.cand_b511 = lambda **k: float(_c511(Omega=float(k.get("Omega", 0.05)),
                                           alpha=float(k.get("alpha", -0.3)),
                                           t=100.0, n=8))
    rec("M8 B511 越稳定性界档（t=100/n=8 ⇒ 发散）", {"B1"}, *run_smoke())
    J3.cand_b511 = _c511

    # M9 —— 能力层 rabi_population 破坏
    QD.rabi_population = lambda *a, **k: 0.0
    rec("M9 能力层 rabi_population 恒 0（同律破坏）", {"D1"}, *run_smoke())
    QD.rabi_population = _rabi

    # M10 —— 能力层 qutrit_leakage 破坏
    QD.qutrit_leakage = lambda *a, **k: 0.0
    rec("M10 能力层 qutrit_leakage 恒 0（同律破坏）", {"D1"}, *run_smoke())
    QD.qutrit_leakage = _leak

    # M11 —— DRAG 抑制趋势反转
    QD.drag_leakage = lambda sigma=None, alpha=None, beta=None, n_sigma=None, n=4000, \
        amplitude=None: (1.0e-2 if (beta or 0.0) == 0.0 else 5.0e-1)
    rec("M11 DRAG 抑制趋势反转（β=1 泄漏 > β=0）", {"D2"}, *run_smoke())
    QD.drag_leakage = _drag

    # M12 —— 闭环定标不收敛
    def _calib_bad(**k):
        d = dict(_calib(**k))
        d["converged"] = False
        return d

    CC.rabi_amplitude_calibrate = _calib_bad
    rec("M12 闭环定标不收敛（converged 恒 False）", {"C3"}, *run_smoke())
    CC.rabi_amplitude_calibrate = _calib

    # M13 —— 捕获范围守卫抹掉
    def _calib_nodiv(**k):
        d = dict(_calib(**k))
        d["diverged"] = False
        return d

    CC.rabi_amplitude_calibrate = _calib_nodiv
    rec("M13 捕获范围守卫抹掉（diverged 恒 False）", {"D4"}, *run_smoke())
    CC.rabi_amplitude_calibrate = _calib

    # M14 —— 读出误判链破坏
    CC.readout_error_probability = lambda snr: 0.0
    rec("M14 读出误判链恒 0（erfc 口径破坏）", {"E1a"}, *run_smoke())
    CC.readout_error_probability = _eps

    # M15 —— 签核与三环脱钩（强报 ACCEPT）
    def _report_lie(**k):
        d = dict(_report(**k))
        d["verdict"] = "ACCEPT"
        d["ring_c"] = dict(d["ring_c"])
        d["ring_c"]["within_limit"] = False
        return d

    CC.control_loop_report = _report_lie
    rec("M15 签核与三环脱钩（强报 ACCEPT）", {"C3"}, *run_smoke())
    CC.control_loop_report = _report

    # M16 —— tol 三表漂移
    J3._TOL_BY_BID["B510"] = 1e-12
    rec("M16 tol 三表漂移（_TOL_BY_BID 与 DEFS 不一致）", {"E2"}, *run_smoke())
    J3._TOL_BY_BID["B510"] = _tol510

    # M17 —— 候选键回退
    BM.BENCHMARK_DEFS["B510"]["candidate"] = "b510_reverted_stub"
    rec("M17 候选键回退（candidate 改名为旧桩）", {"A5"}, *run_smoke())
    BM.BENCHMARK_DEFS["B510"]["candidate"] = _cand510_key

    # M18 —— B512 候选退回自证桩
    J3.cand_b512 = lambda **k: float(_g512(**k))
    rec("M18 B512 候选退回自证桩（cand≡golden）", {"F1"}, *run_smoke())
    J3.cand_b512 = _c512

    # M19 —— B512 候选忽略请求步数
    J3.cand_b512 = lambda **k: float(_c512(**{**k, "n": 64}))
    rec("M19 B512 候选忽略请求步数（残差与步数无关）", {"F2"}, *run_smoke())
    J3.cand_b512 = _c512

    # M20 —— B512 候选丢弃 Γ（**正是反向探针扰动的那一个键** ⇒ 候选不随参数走）
    J3.cand_b512 = lambda **k: float(_c512(Gamma=0.02, t=float(k.get("t", 100.0)),
                                           n=int(k.get("n", 64))))
    rec("M20 B512 候选丢弃去极化率 Γ（不随被扰键走）", {"F3"}, *run_smoke())
    J3.cand_b512 = _c512

    # M21 —— B513 候选退回自证桩
    J3.cand_b513 = lambda **k: float(_g513(**k))
    rec("M21 B513 候选退回自证桩（cand≡golden）", {"G1"}, *run_smoke())
    J3.cand_b513 = _c513

    # M22 —— B513 候选忽略请求步数
    J3.cand_b513 = lambda **k: float(_c513(**{**k, "n": 1024}))
    rec("M22 B513 候选忽略请求步数（残差与步数无关）", {"G2"}, *run_smoke())
    J3.cand_b513 = _c513

    # M23 —— B513 候选丢弃 f_q（**被扰键**）
    J3.cand_b513 = lambda **k: float(_c513(f_q=5.5, f_s=float(k.get("f_s", 6.0)),
                                           z_ratio=float(k.get("z_ratio", 1.0)),
                                           n=int(k.get("n", 1024))))
    rec("M23 B513 候选丢弃 qubit 频率 f_q（不随被扰键走）", {"G3"}, *run_smoke())
    J3.cand_b513 = _c513

    # M24 —— B514 候选退回自证桩
    J3.cand_b514 = lambda **k: float(_g514(**k))
    rec("M24 B514 候选退回自证桩（cand≡golden）", {"H1"}, *run_smoke())
    J3.cand_b514 = _c514

    # M25 —— B514 候选忽略请求步数
    J3.cand_b514 = lambda **k: float(_c514(**{**k, "n": 256}))
    rec("M25 B514 候选忽略请求步数（残差与步数无关）", {"H2"}, *run_smoke())
    J3.cand_b514 = _c514

    # M26 —— 能力层 rb_benchmark 纯度衰减破坏（非零但口径错：不依赖 Γ ⇒ J1 必红）
    #   🔴 首版用「恒 0」，导致内部 `unitarity_from_purity_sequence` 因 d≤0 抛异常 ⇒ 门禁崩溃（X0）
    #   ⇒ 改为**非零但口径错**（不随 Γ 走）—— 突变须「可被判据区分」而非「令门禁崩溃」。
    RB.purity_decay_analytic = lambda m, Gamma=0.02: 0.5 + 0.1 ** (int(m) + 1)
    rec("M26 能力层 rb_benchmark 纯度衰减口径错（不随 Γ 走）", {"J1"}, *run_smoke())
    RB.purity_decay_analytic = _rb_purity

    # M27 —— 能力层 readout_demod Purcell 破坏
    RD.purcell_suppression = lambda f_q=5.5, f_s=6.0, z_ratio=1.0: 1.0
    rec("M27 能力层 readout_demod Purcell 抑制恒 1（同律破坏）", {"J1"}, *run_smoke())
    RD.purcell_suppression = _rd_purcell

    # M28 —— 能力层 cryo_electronics 分布式噪声破坏
    CE.distributed_amp_nadd = lambda eta_ratio=0.5, g=0.5, L=10.0: 0.0
    rec("M28 能力层 cryo_electronics 分布式噪声恒 0（同律破坏）", {"J1"}, *run_smoke())
    CE.distributed_amp_nadd = _ce_dist

    # M29 —— 总装签核脱钩（强报 REJECT）
    def _full_lie(**k):
        d = dict(_full(**k))
        d["verdict"] = "REJECT"
        return d

    CC.full_control_loop_report = _full_lie
    rec("M29 总装签核脱钩（强报 REJECT）", {"I4"}, *run_smoke())
    CC.full_control_loop_report = _full

    # M30 —— tol 三表漂移（B512）
    J3._TOL_BY_BID["B512"] = 1e-12
    rec("M30 tol 三表漂移（_TOL_BY_BID['B512'] 与 DEFS 不一致）", {"K1"}, *run_smoke())
    J3._TOL_BY_BID["B512"] = _tol512

    # M31 —— 候选键回退（B513）
    BM.BENCHMARK_DEFS["B513"]["candidate"] = "b513_reverted_stub"
    rec("M31 候选键回退（B513 candidate 改名为旧桩）", {"G5"}, *run_smoke())
    BM.BENCHMARK_DEFS["B513"]["candidate"] = _cand513_key

    # M32 —— 还原复绿
    rec("M32 全部还原（须复绿）", set(), *run_smoke())

    print("=" * 92)
    print("J3 门禁突变探针（scripts/d154_j3_probe.py · 不入 CI）")
    print("=" * 92)
    bad = 0
    for tag, ids, ok in rows:
        bad += 0 if ok else 1
        print("  [%s] %-46s  FAIL 判据=%s" % ("OK " if ok else "ERR", tag,
                                              ",".join(ids) if ids else "—"))
    print("-" * 92)
    print("合计：%d 条，%s" % (len(rows), "ALL AS EXPECTED" if bad == 0
                             else "%d 条不符预期" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
