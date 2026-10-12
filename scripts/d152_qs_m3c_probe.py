#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M3c（G5 · 腔 QED 物理链）门禁 `run_qs_m3c_smoke` · 突变探针（12 条）。

每条突变只破坏**一个**语义，验证门禁对应判据确实能变红（「先证能变红」——全绿的门禁
若探针打不红，就是死测试）；每条跑完后还原并复绿。

  M1  腔 Q 闭式退化为常数（破坏单调性）          ⇒ A1 应红
  M2  物理常数篡改（EPSILON_0 ×1.01）             ⇒ B3/B1 应红
  M3  模块数值候选篡改（RK4 反解退化为常数）       ⇒ B2/C 应红
  M4  删 B495 的 `candidate` 键                   ⇒ D1/D3 应红
  M5  tol 篡改（B494 tol 改非锚核值）              ⇒ D4 应红
  M6  默认档改非扫描末端（B495 n→32）              ⇒ D5 应红
  M7  golden 未登记（删 `_GOLDEN_DISPATCH["B496"]`）⇒ G2 应红
  M8  `_PHYSICAL_LAW` 删 B494                     ⇒ G4 应红
  M9  三锚从 `BENCHMARK_ORDER` 删除               ⇒ G3 应红
  M10 零 κ 护栏拆除（cavity_q_factor 不抛）         ⇒ E1 应红
  M11 finesse 两式不一致（from_defs 改错值）        ⇒ F1 应红
  M12 零 A 护栏拆除（mode_volume_closed 不抛）       ⇒ E2 应红

运行：python scripts/d152_qs_m3c_probe.py（本机建议重定向到文件再读）
"""
from __future__ import annotations

import copy
import io
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_qs_m3c_smoke as SMOKE          # noqa: E402
from lda_l2 import qs_m3c as M            # noqa: E402
from lda_harness import _batch_qs_m3c_numeric as NB  # noqa: E402
from lda_harness import benchmarks as BM  # noqa: E402
from lda_harness import golden as GD     # noqa: E402

_ORIG = {
    "cavity_q_factor": M.cavity_q_factor,
    "cavity_q_factor_numeric": M.cavity_q_factor_numeric,
    "mode_volume_closed": M.mode_volume_closed,
    "cavity_finesse_from_defs": M.cavity_finesse_from_defs,
    "EPSILON_0": M.EPSILON_0,
    "DEFS_B494": copy.deepcopy(BM.BENCHMARK_DEFS["B494"]),
    "DEFS_B495": copy.deepcopy(BM.BENCHMARK_DEFS["B495"]),
    "DEFS_B496": copy.deepcopy(BM.BENCHMARK_DEFS["B496"]),
    "ORDER": list(BM.BENCHMARK_ORDER),
    "N_BY_BID": dict(NB._N_BY_BID),
    "GD_B496": GD._GOLDEN_DISPATCH.get("B496"),
    "PL_has_B494": "B494" in GD._PHYSICAL_LAW,
}


def run_smoke():
    """in-process 跑门禁 main()，返回 (退出码, FAIL 行列表, CRASH 行列表)。"""
    SMOKE.PASS = 0
    SMOKE.FAIL = 0
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = SMOKE.main()
    except SystemExit as e:                       # pragma: no cover
        rc = e.code
    except Exception as e:                        # noqa: BLE001
        rc = 99
        buf.write("[CRASH] %r\n" % (e,))
    finally:
        sys.stdout = old
    lines = buf.getvalue().splitlines()
    fails = [l.strip() for l in lines if "[FAIL]" in l]
    crashes = [l for l in lines if "[CRASH]" in l]
    return (rc, fails, crashes)


def _restore():
    M.cavity_q_factor = _ORIG["cavity_q_factor"]
    M.cavity_q_factor_numeric = _ORIG["cavity_q_factor_numeric"]
    M.mode_volume_closed = _ORIG["mode_volume_closed"]
    M.cavity_finesse_from_defs = _ORIG["cavity_finesse_from_defs"]
    M.EPSILON_0 = _ORIG["EPSILON_0"]
    BM.BENCHMARK_DEFS["B494"] = copy.deepcopy(_ORIG["DEFS_B494"])
    BM.BENCHMARK_DEFS["B495"] = copy.deepcopy(_ORIG["DEFS_B495"])
    BM.BENCHMARK_DEFS["B496"] = copy.deepcopy(_ORIG["DEFS_B496"])
    BM.BENCHMARK_ORDER[:] = _ORIG["ORDER"]
    NB._N_BY_BID.clear()
    NB._N_BY_BID.update(_ORIG["N_BY_BID"])
    if _ORIG["GD_B496"] is not None:
        GD._GOLDEN_DISPATCH["B496"] = _ORIG["GD_B496"]
    if _ORIG["PL_has_B494"]:
        GD._PHYSICAL_LAW.add("B494")


def _hit(fails, keys):
    return any(any(k in ln for k in keys) for ln in fails)


def main():
    rows = []

    rc0, f0, c0 = run_smoke()
    rows.append(("基线（须全绿 exit=0）", rc0, f0, c0, []))
    if rc0 != 0:
        print("！！基线未全绿 —— 后续突变结论不可信")
        for ln in f0:
            print("   ", ln)

    # M1 腔 Q 闭式退化为常数（破单调）
    M.cavity_q_factor = lambda omega, kappa: 1.0
    rows.append(("M1 腔 Q 退化常数（破单调）", *run_smoke(), ["A1"]))
    _restore()

    # M2 物理常数篡改 EPSILON_0 ×1.01
    M.EPSILON_0 = _ORIG["EPSILON_0"] * 1.01
    rows.append(("M2 EPSILON_0 ×1.01（常数篡改）", *run_smoke(), ["B3", "B1"]))
    _restore()

    # M3 模块数值候选篡改（RK4 反解退化为常数）
    M.cavity_q_factor_numeric = (
        lambda omega, kappa, t_observe=8.22e-12, n_steps=64: 12345.0)
    rows.append(("M3 模块数值候选篡改", *run_smoke(), ["B2", "C"]))
    _restore()

    # M4 删 B495 candidate 键
    _d = copy.deepcopy(BM.BENCHMARK_DEFS["B495"])
    _d.pop("candidate", None)
    BM.BENCHMARK_DEFS["B495"] = _d
    rows.append(("M4 删 B495 candidate 键", *run_smoke(), ["D1", "D3"]))
    _restore()

    # M5 tol 篡改（B494 DEFS tol 改非锚核值）
    _d = copy.deepcopy(BM.BENCHMARK_DEFS["B494"])
    _d["tol"] = 1e-9
    BM.BENCHMARK_DEFS["B494"] = _d
    rows.append(("M5 B494 tol 改非锚核值", *run_smoke(), ["D4"]))
    _restore()

    # M6 默认档改非扫描末端（B495 n→32）
    NB._N_BY_BID["B495"] = 32
    try:
        rows.append(("M6 B495 默认档改非末端", *run_smoke(), ["D5"]))
    finally:
        NB._N_BY_BID.clear()
        NB._N_BY_BID.update(_ORIG["N_BY_BID"])

    # M7 golden 未登记
    GD._GOLDEN_DISPATCH.pop("B496", None)
    rows.append(("M7 删 _GOLDEN_DISPATCH['B496']", *run_smoke(), ["G2"]))
    _restore()

    # M8 _PHYSICAL_LAW 删 B494
    GD._PHYSICAL_LAW.discard("B494")
    rows.append(("M8 删 _PHYSICAL_LAW 的 B494", *run_smoke(), ["G4"]))
    _restore()

    # M9 ORDER 删三锚
    BM.BENCHMARK_ORDER[:] = [b for b in BM.BENCHMARK_ORDER
                             if b not in ("B494", "B495", "B496")]
    rows.append(("M9 ORDER 删三锚", *run_smoke(), ["G3"]))
    _restore()

    # M10 零 κ 护栏拆除（cavity_q_factor 不抛）
    _q0 = _ORIG["cavity_q_factor"]
    M.cavity_q_factor = (lambda omega, kappa:
                         0.0 if kappa <= 0 else _q0(omega, kappa))
    rows.append(("M10 零 κ 护栏拆除（不抛）", *run_smoke(), ["E1"]))
    _restore()

    # M11 finesse 两式不一致
    M.cavity_finesse_from_defs = lambda Q, lam, n, a: 999.0
    rows.append(("M11 finesse from_defs 改错值", *run_smoke(), ["F1"]))
    _restore()

    # M12 零 A 护栏拆除（mode_volume_closed 不抛）
    _v0 = _ORIG["mode_volume_closed"]
    M.mode_volume_closed = (lambda a, A:
                            0.0 if A <= 0 else _v0(a, A))
    rows.append(("M12 零 A 护栏拆除（不抛）", *run_smoke(), ["E2"]))
    _restore()

    rc_z, fz, cz = run_smoke()
    rows.append(("还原（须复绿 exit=0）", rc_z, fz, cz, []))

    print("=" * 78)
    print("QS-M3c 门禁 · 突变探针（12 条）")
    print("=" * 78)
    bad = 0
    for name, rc, fails, crashes, keys in rows:
        if name.startswith("基线") or name.startswith("还原"):
            ok = (rc == 0)
            print("  [%s] %s   exit=%s fails=%d"
                  % ("PASS" if ok else "FAIL", name, rc, len(fails)))
            if not ok:
                bad += 1
                for ln in fails:
                    print("        ", ln)
            continue
        expect_ok = (rc != 0) and bool(fails) and (not keys or _hit(fails, keys)) and not crashes
        print("  [%s] %-30s exit=%-3s fails=%-2d %s"
              % ("PASS" if expect_ok else "FAIL", name, rc, len(fails),
                 ("命中 " + ",".join(keys)) if expect_ok else "期望=%s" % keys))
        if not expect_ok:
            bad += 1
            for ln in (fails or crashes)[:4]:
                print("        ", ln)
    print("-" * 78)
    print("探针结论：%s（%d 项不符）" % ("ALL PASS" if bad == 0 else "FAIL", bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(2)
