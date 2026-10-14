#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""J4 量子传感系统集成征程（M0）· 门禁的**突变探针**（逐条必红 + 还原复绿）。

═══════════════════════════════════════════════════════════════════════════
为什么需要这一层
═══════════════════════════════════════════════════════════════════════════
门禁自身有 in-gate 反向探针（A3/A4…），但它们都在**门禁内部**构造。
本脚本从**模块外部**对门禁所依赖的**同一模块对象**做突变，再跑**整道门禁**，
并断言**预期判据 id** 出现在 `[FAIL]` 行里（不是只看 `FAIL>0`）：

  M1  无突变（baseline）                          ⇒ 全绿（13 PASS / 0 FAIL）
  M2  B515 候选退回自证桩（cand ≡ golden）        ⇒ A1 必红（|Δ|≡0）
  M3  B515 候选粗化（步数强制 k=64）              ⇒ A1 必红（残差 > tol）
  M4  B515 候选忽略请求步数（恒 k=320）           ⇒ A2 必红（残差与离散参数无关）
  M5  B515 候选丢弃 coupling（**被扰键**）        ⇒ A3 必红（不随参数走）
  M6  能力层响应矩阵 _C 被改（跨模块同源破坏）    ⇒ C1 必红
  M7  能力层 Cramer 解耦破坏（恒 0）              ⇒ C2/B1 必红
  M8  能力层 Landweber 迭代破坏（恒 0）           ⇒ C3/B1 必红
  M9  tol 三表漂移（_TOL_BY_BID["B515"]=1e-12）   ⇒ D1 必红
  M10 默认档漂移（B515_DEFAULT_PARAMS coupling=2.0）⇒ D2 必红
  M11 候选键回退（B515 candidate 改名）           ⇒ A5 必红
  M12 全部还原                                     ⇒ 复绿（还原完整性）

🔴 惯例：`scripts/*_probe.py` **不入 CI**（人工复核用）；in-process monkeypatch
   **不碰源文件** ⇒ 无需文件还原/哈希复核。
运行：python scripts/d155_j4_probe.py
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

import run_j4_multiparam_smoke as S            # noqa: E402
from lda_harness import benchmarks as BM       # noqa: E402

J4 = S.J4
MP = S.MP
MC = S.MC
IG = S.IG
PK = S.PK
SYS = S.SYS

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
    _c515 = J4.cand_b515
    _g515 = J4.golden_b515
    _tol515 = J4._TOL_BY_BID["B515"]
    _defp515 = dict(J4.B515_DEFAULT_PARAMS)
    _cand515_key = BM.BENCHMARK_DEFS["B515"]["candidate"]
    _C = MP._C.copy()
    _cramer = MP.decouple_cramer
    _lw = MP.decouple_landweber
    _c518 = J4.cand_b518
    _g518 = J4.golden_b518
    _tol518 = J4._TOL_BY_BID["B518"]
    _pkg_load = PK.cryo_wiring_heat_load
    _sys_anchors = SYS.SYSTEM_ANCHORS

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

    # M2 —— B515 候选退回自证桩
    J4.cand_b515 = lambda **k: float(_g515(**k))
    rec("M2 B515 候选退回自证桩（cand≡golden）", {"A1"}, *run_smoke())
    J4.cand_b515 = _c515

    # M3 —— B515 候选粗化（收敛未达标档 k=64）
    J4.cand_b515 = lambda **k: float(_c515(**{**k, "n": 64}))
    rec("M3 B515 候选粗化（步数强制 k=64）", {"A1"}, *run_smoke())
    J4.cand_b515 = _c515

    # M4 —— B515 候选忽略请求步数（恒 k=320 ⇒ 残差与离散参数无关）
    J4.cand_b515 = lambda **k: float(_c515(**{**k, "n": 320}))
    rec("M4 B515 候选忽略请求步数（残差与步数无关）", {"A2"}, *run_smoke())
    J4.cand_b515 = _c515

    # M5 —— B515 候选丢弃 coupling（**正是反自证桩扰动的那一个键** ⇒ 候选不随参数走）
    #   🔴 教训（J3 血案继承）：**突变必须打在被门禁扰动/检出的那一个键上**，
    #     否则「变异无效」会被误读成「护栏不响」。
    J4.cand_b515 = lambda **k: float(_c515(coupling=1.0, n=int(k.get("n", 320))))
    rec("M5 B515 候选丢弃 coupling（不随被扰键走）", {"A3"}, *run_smoke())
    J4.cand_b515 = _c515

    # M6 —— 能力层响应矩阵被改（跨模块同源破坏）
    MP._C = _C.copy()
    MP._C[0, 1] = 0.99
    rec("M6 能力层响应矩阵 _C 被改（跨模块同源破坏）", {"C1"}, *run_smoke())
    MP._C = _C.copy()

    # M7 —— 能力层 Cramer 解耦破坏
    MP.decouple_cramer = lambda *a, **k: __import__("numpy").zeros(4)
    rec("M7 能力层 Cramer 解耦恒 0", {"C2"}, *run_smoke())
    MP.decouple_cramer = _cramer

    # M8 —— 能力层 Landweber 迭代破坏
    MP.decouple_landweber = lambda *a, **k: __import__("numpy").zeros(4)
    rec("M8 能力层 Landweber 迭代恒 0", {"C3"}, *run_smoke())
    MP.decouple_landweber = _lw

    # M9 —— tol 三表漂移
    J4._TOL_BY_BID["B515"] = 1e-12
    rec("M9 tol 三表漂移（_TOL_BY_BID 与 DEFS 不一致）", {"D1"}, *run_smoke())
    J4._TOL_BY_BID["B515"] = _tol515

    # M10 —— 默认档漂移
    J4.B515_DEFAULT_PARAMS = dict(_defp515)
    J4.B515_DEFAULT_PARAMS["coupling"] = 2.0
    rec("M10 默认档漂移（B515_DEFAULT_PARAMS coupling=2.0）", {"D2"}, *run_smoke())
    J4.B515_DEFAULT_PARAMS = dict(_defp515)

    # M11 —— 候选键回退
    BM.BENCHMARK_DEFS["B515"]["candidate"] = "b515_reverted_stub"
    rec("M11 候选键回退（candidate 改名为旧桩）", {"A5"}, *run_smoke())
    BM.BENCHMARK_DEFS["B515"]["candidate"] = _cand515_key

    # M12 —— B518 候选退回自证桩
    J4.cand_b518 = lambda **k: float(_g518(**k))
    rec("M12 B518 候选退回自证桩（cand≡golden）", {"F1"}, *run_smoke())
    J4.cand_b518 = _c518

    # M13 —— B518 候选粗化（收敛未达标档 n=32）
    J4.cand_b518 = lambda **k: float(_c518(**{**k, "n": 32}))
    rec("M13 B518 候选粗化（步数强制 n=32）", {"F1"}, *run_smoke())
    J4.cand_b518 = _c518

    # M14 —— B518 候选忽略请求步数（恒 n=512 ⇒ 残差与离散参数无关）
    J4.cand_b518 = lambda **k: float(_c518(**{**k, "n": 512}))
    rec("M14 B518 候选忽略请求步数（残差与步数无关）", {"F2"}, *run_smoke())
    J4.cand_b518 = _c518

    # M15 —— B518 候选丢弃被扰键 β（反自证桩扰动的那一个键）
    J4.cand_b518 = lambda **k: float(_c518(rho0_ohm_m=float(k.get("rho0_ohm_m", 1e-10)),
                                           beta_ohm_m_per_K=5.6e-11))
    rec("M15 B518 候选丢弃 β（不随被扰键走）", {"F3"}, *run_smoke())
    J4.cand_b518 = _c518

    # M16 —— 能力层包装热负载破坏（恒 0 ⇒ 跨模块同律 + 自检双红）
    PK.cryo_wiring_heat_load = lambda *a, **k: 0.0
    rec("M16 能力层 cryo_wiring_heat_load 恒 0（跨模块同律破坏）", {"G3"}, *run_smoke())
    PK.cryo_wiring_heat_load = _pkg_load

    # M17 —— M1 锚状态被偷改（净增 0 登记被绕过）
    MC.ANCHOR_STATUS = "B519"
    rec("M17 M1 锚状态被偷改（ANCHOR_STATUS≠none）", {"I1"}, *run_smoke())
    MC.ANCHOR_STATUS = "none"

    # M18 —— 系统链锚来源被改
    SYS.SYSTEM_ANCHORS = ("B515", "B519")
    rec("M18 系统链锚来源被改（多报一锚）", {"I2"}, *run_smoke())
    SYS.SYSTEM_ANCHORS = _sys_anchors

    # M19 —— tol 三表漂移（B518）
    J4._TOL_BY_BID["B518"] = 1.0
    rec("M19 tol 三表漂移（B518 _TOL_BY_BID 与 DEFS 不一致）", {"D1"}, *run_smoke())
    J4._TOL_BY_BID["B518"] = _tol518

    # M20 —— 全部还原
    rec("M20 全部还原（复绿完整性）", set(), *run_smoke())

    print("=" * 100)
    print("J4（M0）门禁突变探针 · 逐条必红 + 还原复绿")
    print("=" * 100)
    bad = 0
    for tag, ids, ok in rows:
        bad += 0 if ok else 1
        print("  [%s] %-52s  FAIL 判据=%s" % ("PASS" if ok else "FAIL", tag,
                                              ",".join(ids) if ids else "（无）"))
    print("=" * 100)
    print("%d 条探针：%s" % (len(rows), "ALL PASS" if bad == 0 else "%d FAIL" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
