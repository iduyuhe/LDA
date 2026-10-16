# -*- coding: utf-8 -*-
"""J5 突变探针（`scripts/d156_j5_probe.py` · M0–M3 四档）—— **先证门禁能变红**。

纪律（J4 血案沉淀）：
  ① 突变必须打在**门禁判据扰动/检出的那个键**上（否则「红对了但红在别处」）；
  ② 突变须「**可被判据区分**」而非「令门禁崩溃」（崩成异常 = 丢失可归因性）；
  ③ 必须 patch **门禁同一模块对象**（经 `S.J5` 属性访问；`from x import f` 会 patch 到副本）；
  ④ 探针存在本身即为抓「门禁 `main()` 恒 return 0 = 假绿」（J4 轮 12 条探针中 9 条当场抓出）。

输出：每条突变打印「预期判据是否出现在 [FAIL] 行」+ 还原后复绿。
"""

from __future__ import annotations

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
for p in (_LDA,):
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib  # noqa: E402

S = importlib.import_module("run_j5_qnet_smoke")
J5 = S.J5
CH = S.CH
DS = S.DS
RP = S.RP
SR = S.SR
TR = S.TR
DEFS = S.BENCHMARK_DEFS

D519 = DEFS["B519"]
D520 = DEFS["B520"]
D521 = DEFS["B521"]
D522 = DEFS["B522"]
_ORIG = {
    "golden_fn": D519["golden_fn"],
    "tol": D519["tol"],
    "candidate": D519["candidate"],
    "default_params": dict(D519["default_params"]),
    "M": dict(J5._M_BY_BID),
    "TOL": dict(J5._TOL_BY_BID),
    "GRID": {k: list(v) for k, v in J5._GRID_BY_BID.items()},
    "PARAMS": dict(J5.B519_DEFAULT_PARAMS),
    "cand_b519": J5.cand_b519,
    "golden_b519": J5.golden_b519,
    "ch_selfcheck": CH.selfcheck_qnet_channel,
    "ds_selfcheck": DS.selfcheck_qnet_distribution,
    "ch_link_fid": CH.link_fidelity,
}

records = []


def run_smoke():
    """跑门禁，返回 (fail_lines, passed_count)。"""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        S.FAIL = 0
        S.main()
    except Exception as e:  # noqa: BLE001
        sys.stdout = old
        return ["<EXC> %s: %s" % (type(e).__name__, str(e)[:80])], 0
    finally:
        sys.stdout = old
    out = buf.getvalue()
    fails = [l.strip() for l in out.split("\n") if "[FAIL]" in l]
    npass = out.count("[PASS]")
    return fails, npass


def rec(name, expect_id, fails, npass):
    ok = any(expect_id in f for f in fails)
    records.append((name, ok, expect_id, npass, fails[:2]))
    print("  [%s] %-52s 预期红=%s  实红=%d 条  PASS=%d"
          % ("PASS" if ok else "FAIL", name, expect_id, len(fails), npass))
    if not ok:
        for f in fails[:3]:
            print("        · %s" % f[:150])


def restore():
    D519["golden_fn"] = _ORIG["golden_fn"]
    D519["tol"] = _ORIG["tol"]
    D519["candidate"] = _ORIG["candidate"]
    D519["default_params"] = dict(_ORIG["default_params"])
    J5._M_BY_BID.clear()
    J5._M_BY_BID.update(_ORIG["M"])
    J5._TOL_BY_BID.clear()
    J5._TOL_BY_BID.update(_ORIG["TOL"])
    J5._GRID_BY_BID.clear()
    J5._GRID_BY_BID.update({k: list(v) for k, v in _ORIG["GRID"].items()})
    J5.B519_DEFAULT_PARAMS.clear()
    J5.B519_DEFAULT_PARAMS.update(_ORIG["PARAMS"])
    J5.cand_b519 = _ORIG["cand_b519"]
    J5.golden_b519 = _ORIG["golden_b519"]
    CH.selfcheck_qnet_channel = _ORIG["ch_selfcheck"]
    DS.selfcheck_qnet_distribution = _ORIG["ds_selfcheck"]
    CH.link_fidelity = _ORIG["ch_link_fid"]


def main() -> int:
    print("=" * 78)
    print("J5 M0 突变探针（B519）")
    print("=" * 78)

    # M0 baseline
    fails, npass = run_smoke()
    print("\n[M0] baseline（无突变）")
    ok0 = len(fails) == 0
    records.append(("M0 原样必绿", ok0, "无红", npass, fails[:2]))
    print("  [%s] M0 原样必绿（FAIL 行 = %d · PASS=%d）"
          % ("PASS" if ok0 else "FAIL", len(fails), npass))

    # M1 篡改 golden ⇒ 残差变（A1/A2）
    D519["golden_fn"] = lambda **kw: _ORIG["golden_fn"](**kw) + 1.0
    fails, npass = run_smoke()
    rec("M1 golden +1.0 ⇒ A2 残差 > tol", "A2", fails, npass)
    restore()

    # M2 篡改 tol 极小 ⇒ A2
    D519["tol"] = 1e-15
    J5._TOL_BY_BID["B519"] = 1e-15
    fails, npass = run_smoke()
    rec("M2 tol→1e-15 ⇒ A2 判决不通过", "A2", fails, npass)
    restore()

    # M3 候选回退成 golden（自证桩）⇒ A7 + A1
    # 🔴 门禁读 `J5._CAND_BY_BID[bid]`（import 时绑定）⇒ 必须**同时** patch 该路径，
    #    只 patch `J5.cand_b519` 不会影响门禁（J4 血案变体：patch 目标须与门禁读取路径一致）。
    _c519, _b519 = J5.cand_b519, J5._CAND_BY_BID["B519"]
    _fake519 = lambda **kw: _ORIG["golden_fn"](  # noqa: E731
        **{k: v for k, v in kw.items() if k != "n"})
    J5.cand_b519 = _fake519
    J5._CAND_BY_BID["B519"] = _fake519
    fails, npass = run_smoke()
    rec("M3 候选≡golden（自证桩回退）⇒ A7 反自证桩", "A7", fails, npass)
    J5.cand_b519 = _c519
    J5._CAND_BY_BID["B519"] = _b519

    # M4 候选键改错 ⇒ A8
    D519["candidate"] = "b999_fake_candidate"
    fails, npass = run_smoke()
    rec("M4 候选键漂移 ⇒ A8 防回退", "A8", fails, npass)
    restore()

    # M5 _M_BY_BID ≠ 扫描格末端 ⇒ D2
    J5._M_BY_BID["B519"] = 64
    fails, npass = run_smoke()
    rec("M5 _M_BY_BID=64（非格末端）⇒ D2", "D2", fails, npass)
    restore()

    # M6 _TOL_BY_BID 与 DEFS 脱钩 ⇒ D1
    J5._TOL_BY_BID["B519"] = 1e-6
    fails, npass = run_smoke()
    rec("M6 _TOL_BY_BID 与 DEFS 脱钩 ⇒ D1", "D1", fails, npass)
    restore()

    # M7 默认档漂移 ⇒ D3
    J5.B519_DEFAULT_PARAMS["l_depol_m"] = 3.0e4
    fails, npass = run_smoke()
    rec("M7 B519_DEFAULT_PARAMS 漂移 ⇒ D3", "D3", fails, npass)
    restore()

    # M8 能力层自检被破坏 ⇒ B1
    CH.selfcheck_qnet_channel = lambda: {"broken": False}
    fails, npass = run_smoke()
    rec("M8 qnet_channel 自检破坏 ⇒ B1", "B1", fails, npass)
    restore()

    # M9 分发能力层自检被破坏 ⇒ B2
    DS.selfcheck_qnet_distribution = lambda: {"broken": False}
    fails, npass = run_smoke()
    rec("M9 qnet_distribution 自检破坏 ⇒ B2", "B2", fails, npass)
    restore()

    # M10 跨模块同源漂移 ⇒ C2
    CH.link_fidelity = lambda length_m=1.0e5, l_depol_m=2.2e4: 0.5
    fails, npass = run_smoke()
    rec("M10 qnet_channel.link_fidelity 漂移 ⇒ C2", "C2", fails, npass)
    restore()

    # M11 B520 golden 偏移 ⇒ A2·B520
    _g520 = D520["golden_fn"]
    D520["golden_fn"] = lambda **kw: _g520(**kw) + 1.0
    fails, npass = run_smoke()
    rec("M11 B520 golden +1.0 ⇒ A2·B520", "A2\u00b7B520", fails, npass)
    D520["golden_fn"] = _g520

    # M12 B520 候选≡golden（自证桩）⇒ A7·B520（同样须 patch 门禁读取路径）
    _c520, _b520 = J5.cand_b520, J5._CAND_BY_BID["B520"]
    _fake520 = lambda **kw: _g520(**{k: v for k, v in kw.items() if k != "n"})  # noqa: E731
    J5.cand_b520 = _fake520
    J5._CAND_BY_BID["B520"] = _fake520
    fails, npass = run_smoke()
    rec("M12 B520 候选≡golden ⇒ A7·B520", "A7\u00b7B520", fails, npass)
    J5.cand_b520 = _c520
    J5._CAND_BY_BID["B520"] = _b520

    # M13 qnet_source 自检破坏 ⇒ B3
    _sr = SR.selfcheck_qnet_source
    SR.selfcheck_qnet_source = lambda: {"broken": False}
    fails, npass = run_smoke()
    rec("M13 qnet_source 自检破坏 ⇒ B3", "B3 ", fails, npass)
    SR.selfcheck_qnet_source = _sr

    # M15 B521 golden 偏移 ⇒ A2·B521
    _g521 = D521["golden_fn"]
    D521["golden_fn"] = lambda **kw: _g521(**kw) + 1.0
    fails, npass = run_smoke()
    rec("M15 B521 golden +1.0 ⇒ A2·B521", "A2\u00b7B521", fails, npass)
    D521["golden_fn"] = _g521

    # M16 B521 候选≡golden（自证桩）⇒ A7·B521（同样须 patch 门禁读取路径）
    _c521, _b521 = J5.cand_b521, J5._CAND_BY_BID["B521"]
    _fake521 = lambda **kw: _g521(**{k: v for k, v in kw.items() if k != "n"})  # noqa: E731
    J5.cand_b521 = _fake521
    J5._CAND_BY_BID["B521"] = _fake521
    fails, npass = run_smoke()
    rec("M16 B521 候选≡golden ⇒ A7·B521", "A7\u00b7B521", fails, npass)
    J5.cand_b521 = _c521
    J5._CAND_BY_BID["B521"] = _b521

    # M17 qnet_repeater 自检破坏 ⇒ B4
    _rp = RP.selfcheck_qnet_repeater
    RP.selfcheck_qnet_repeater = lambda: {"broken": False}
    fails, npass = run_smoke()
    rec("M17 qnet_repeater 自检破坏 ⇒ B4", "B4 ", fails, npass)
    RP.selfcheck_qnet_repeater = _rp

    # M18 qnet_repeater.repeater_yield 漂移 ⇒ C5
    _ry = RP.repeater_yield
    RP.repeater_yield = lambda *a, **kw: 0.5
    fails, npass = run_smoke()
    rec("M18 qnet_repeater.repeater_yield 漂移 ⇒ C5", "C5", fails, npass)
    RP.repeater_yield = _ry

    # M19 B521 默认档漂移 ⇒ D3（数值核常量对象被门禁 `_DEFPARAMS` 绑定 ⇒ 当场红）
    J5.B521_DEFAULT_PARAMS["t_mem_s"] = 3.0e-4
    fails, npass = run_smoke()
    rec("M19 B521_DEFAULT_PARAMS 漂移 ⇒ D3", "D3", fails, npass)
    J5.B521_DEFAULT_PARAMS["t_mem_s"] = 1.6e-4

    # M21 B522 golden 偏移 ⇒ A2·B522
    _g522d = D522["golden_fn"]
    D522["golden_fn"] = lambda **kw: _g522d(**kw) + 1.0
    fails, npass = run_smoke()
    rec("M21 B522 golden +1.0 ⇒ A2·B522", "A2\u00b7B522", fails, npass)
    D522["golden_fn"] = _g522d

    # M22 B522 候选≡golden（自证桩）⇒ A7·B522（须 patch 门禁读取路径）
    _c522, _b522 = J5.cand_b522, J5._CAND_BY_BID["B522"]
    _fake522 = lambda **kw: _g522d(**{k: v for k, v in kw.items() if k != "n"})  # noqa: E731
    J5.cand_b522 = _fake522
    J5._CAND_BY_BID["B522"] = _fake522
    fails, npass = run_smoke()
    rec("M22 B522 候选≡golden ⇒ A7·B522", "A7\u00b7B522", fails, npass)
    J5.cand_b522 = _c522
    J5._CAND_BY_BID["B522"] = _b522

    # M23 qnet_transducer 自检破坏 ⇒ B5
    _tr = TR.selfcheck_qnet_transducer
    TR.selfcheck_qnet_transducer = lambda: {"broken": False}
    fails, npass = run_smoke()
    rec("M23 qnet_transducer 自检破坏 ⇒ B5", "B5 ", fails, npass)
    TR.selfcheck_qnet_transducer = _tr

    # M24 qnet_transducer.transducer_efficiency 漂移 ⇒ C6
    _te = TR.transducer_efficiency
    TR.transducer_efficiency = lambda *a, **kw: 0.5
    fails, npass = run_smoke()
    rec("M24 qnet_transducer.transducer_efficiency 漂移 ⇒ C6", "C6", fails, npass)
    TR.transducer_efficiency = _te

    # M25 B522 默认档漂移 ⇒ D3
    J5.B522_DEFAULT_PARAMS["band_half_rad_s"] = 1.0e7
    fails, npass = run_smoke()
    rec("M25 B522_DEFAULT_PARAMS 漂移 ⇒ D3", "D3", fails, npass)
    J5.B522_DEFAULT_PARAMS["band_half_rad_s"] = 2.0 * 3.141592653589793 * 5.0e6

    # M26 还原复绿
    fails, npass = run_smoke()
    print("\n[M26] 全部还原")
    print("  [%s] M26 全部还原（复绿完整性 · FAIL 行 = %d）"
          % ("PASS" if len(fails) == 0 else "FAIL", len(fails)))
    records.append(("M26 还原复绿", len(fails) == 0, "无红", npass, fails[:2]))

    bad = sum(1 for _, ok, _, _, _ in records if not ok)
    print("\n" + "=" * 78)
    print("探针结果：%d/%d PASS" % (len(records) - bad, len(records)))
    print("=" * 78)
    return 1 if bad else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
