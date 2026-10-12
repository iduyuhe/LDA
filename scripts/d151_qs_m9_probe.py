#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M9（G11 · 光泵原子磁力计 OPM/SERF 腿 C）门禁 `run_qs_m9_smoke` · 突变探针（11 条）。

每条突变只破坏**一个**语义，验证门禁对应判据确实能变红（「先证能变红」——全绿的门禁
若探针打不红，就是死测试）；每条跑完后还原并复绿。

  M1  稳态极化 P∞ 退化为常数（破坏单调性）      ⇒ A4 应红
  M2  物理常数篡改（γ_e ×2）                    ⇒ B3 应红
  M3  物理常数篡改（ΔH/k_B ×1.1）               ⇒ B1/B3 应红
  M4  模块数值候选篡改（FID 把 gamma 当 n_steps）⇒ B2/C 应红
  M5  删 B491 的 `candidate` 键                 ⇒ D1/D3 应红
  M6  tol 篡改（B493 tol ×1000）                ⇒ D4 应红
  M7  默认档改非扫描末端（B492 n→32）            ⇒ D5 应红
  M8  三腿对照方向反转（OPM 表返回倒序）         ⇒ F1 应红
  M9  golden 未登记（删 `_GOLDEN_DISPATCH["B492"]`）⇒ G2 应红
  M10 `_PHYSICAL_LAW` 删 B493                   ⇒ G4 应红
  M11 三锚从 `BENCHMARK_ORDER` 删除             ⇒ G3 应红

运行：python scripts/d151_qs_m9_probe.py（本机建议重定向到文件再读）
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

import run_qs_m9_smoke as SMOKE          # noqa: E402
from lda_l2 import qs_m9 as M            # noqa: E402
from lda_harness import _batch_b47_numeric as NB  # noqa: E402
from lda_harness import benchmarks as BM  # noqa: E402
from lda_harness import golden as GD     # noqa: E402

_ORIG = {
    "steady_polarization": M.steady_polarization,
    "GAMMA_RB_HZ_T": M.GAMMA_RB_HZ_T,
    "DH_VAP_OVER_KB_K": M.DH_VAP_OVER_KB_K,
    "transverse_polarization_numeric": M.transverse_polarization_numeric,
    "three_legs_table": M.three_legs_table,
    "DEFS_B491": copy.deepcopy(BM.BENCHMARK_DEFS["B491"]),
    "DEFS_B492": copy.deepcopy(BM.BENCHMARK_DEFS["B492"]),
    "DEFS_B493": copy.deepcopy(BM.BENCHMARK_DEFS["B493"]),
    "ORDER": list(BM.BENCHMARK_ORDER),
    "GD_B492": GD._GOLDEN_DISPATCH.get("B492"),
    "PL_has_B493": "B493" in GD._PHYSICAL_LAW,
}


def run_smoke():
    """in-process 跑门禁 main()，返回 (退出码, FAIL 行列表)。"""
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
    M.steady_polarization = _ORIG["steady_polarization"]
    M.GAMMA_RB_HZ_T = _ORIG["GAMMA_RB_HZ_T"]
    M.DH_VAP_OVER_KB_K = _ORIG["DH_VAP_OVER_KB_K"]
    M.transverse_polarization_numeric = _ORIG["transverse_polarization_numeric"]
    M.three_legs_table = _ORIG["three_legs_table"]
    BM.BENCHMARK_DEFS["B491"] = copy.deepcopy(_ORIG["DEFS_B491"])
    BM.BENCHMARK_DEFS["B492"] = copy.deepcopy(_ORIG["DEFS_B492"])
    BM.BENCHMARK_DEFS["B493"] = copy.deepcopy(_ORIG["DEFS_B493"])
    BM.BENCHMARK_ORDER[:] = _ORIG["ORDER"]
    if _ORIG["GD_B492"] is not None:
        GD._GOLDEN_DISPATCH["B492"] = _ORIG["GD_B492"]
    if _ORIG["PL_has_B493"]:
        GD._PHYSICAL_LAW.add("B493")


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

    # M1 P∞ 退化为常数
    M.steady_polarization = lambda r_op, r_sd: 0.5
    rows.append(("M1 P∞ 退化常数（破单调）", *run_smoke(), ["A4"]))
    _restore()

    # M2 γ_e ×2
    M.GAMMA_RB_HZ_T = _ORIG["GAMMA_RB_HZ_T"] * 2.0
    rows.append(("M2 γ_e ×2（常数篡改）", *run_smoke(), ["B3", "B1"]))
    _restore()

    # M3 ΔH/k_B ×1.1
    M.DH_VAP_OVER_KB_K = _ORIG["DH_VAP_OVER_KB_K"] * 1.1
    rows.append(("M3 ΔH/k_B ×1.1（常数篡改）", *run_smoke(), ["B3", "B1"]))
    _restore()

    # M4 模块数值候选篡改（把第 5 位置参数当 gamma）
    M.transverse_polarization_numeric = (
        lambda p0, r, b, t, gamma_hz_t=64, n_steps=64:
        _ORIG["transverse_polarization_numeric"](p0, r, b, t, gamma_hz_t))
    rows.append(("M4 模块数值候选篡改", *run_smoke(), ["B2", "C B491", "C"]))
    _restore()

    # M5 删 B491 candidate 键
    _d = copy.deepcopy(BM.BENCHMARK_DEFS["B491"])
    _d.pop("candidate", None)
    BM.BENCHMARK_DEFS["B491"] = _d
    rows.append(("M5 删 B491 candidate 键", *run_smoke(), ["D1", "D3"]))
    _restore()

    # M6 tol 篡改
    _d = copy.deepcopy(BM.BENCHMARK_DEFS["B493"])
    _d["tol"] = 1e-3
    BM.BENCHMARK_DEFS["B493"] = _d
    rows.append(("M6 B493 tol ×1e4", *run_smoke(), ["D4"]))
    _restore()

    # M7 默认档改非扫描末端
    NB._N_BY_BID["B492"] = 32
    try:
        rows.append(("M7 B492 默认档改非末端", *run_smoke(), ["D5"]))
    finally:
        NB._N_BY_BID["B492"] = 256

    # M8 三腿对照方向反转
    M.three_legs_table = lambda: dict(_ORIG["three_legs_table"](),
                                      opm_leg_fT_per_sqrt_hz=1e9,
                                      squid_leg_fT_per_sqrt_hz=1.73,
                                      nv_leg_fT_per_sqrt_hz=8.47e5)
    rows.append(("M8 三腿对照方向反转", *run_smoke(), ["F1"]))
    _restore()

    # M9 golden 未登记
    GD._GOLDEN_DISPATCH.pop("B492", None)
    rows.append(("M9 删 _GOLDEN_DISPATCH['B492']", *run_smoke(), ["G2"]))
    _restore()

    # M10 _PHYSICAL_LAW 删 B493
    GD._PHYSICAL_LAW.discard("B493")
    rows.append(("M10 删 _PHYSICAL_LAW 的 B493", *run_smoke(), ["G4"]))
    _restore()

    # M11 ORDER 删 B491/B492/B493
    BM.BENCHMARK_ORDER[:] = [b for b in BM.BENCHMARK_ORDER
                             if b not in ("B491", "B492", "B493")]
    rows.append(("M11 ORDER 删三锚", *run_smoke(), ["G3"]))
    _restore()

    rc_z, fz, cz = run_smoke()
    rows.append(("还原（须复绿 exit=0）", rc_z, fz, cz, []))

    print("=" * 78)
    print("QS-M9 门禁 · 突变探针（11 条）")
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
