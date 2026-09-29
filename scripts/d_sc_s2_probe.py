"""D-134 突变探针（scratch · 不入 CI）：证明 run_schip_s2_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

🔴 教训（见 d_sc_s1_probe.py 文件头）：探针必须 patch 门禁**同一模块对象**
（SM.S2 / SM.S2.CR）——门禁走 `from lda_qeda import sc_coupler as S2`，
另起 `from lda_qeda import sc_coupler` 会拿到不同实例 ⇒ 假绿。故一律经 SM 取对象。

人工记录（改动 → 应红判据）：
  · M1 run_sc_pair_drc 恒 ACCEPT   ⇒ B2/B3/B4（DRC 违规漏判）应红
  · M2 sc_pair_lvs_signoff 恒 ACCEPT ⇒ C2/C4/C5（LVS 违规漏判）应红
  · M3 coupled_pair_physics relJ=0.99 ⇒ F1（J 双验证失守）应红
  · M4 cross_resonance ok=False    ⇒ F2/F5（CR 有效模型落窗失守）应红
  · M5 _bbox 坍缩                  ⇒ C1（合法 LVS 连通性假红）应红
  · M6 披露缺 physics 键           ⇒ D1（红线披露缺漏）应红
  · M7 coupled_pair_gds 返空字节   ⇒ E1（GDS 真出失败）应红
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_s2_smoke as SM                             # noqa: E402

# 同一模块对象（见文件头教训）：经 SM 取，避免另起 import 拿到不同实例
S2 = SM.S2
CR = SM.S2.CR


def run_smoke() -> int:
    SM.PASS = 0
    SM.FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = SM.main()
    return rc


def _accept_drc(els, limits=None):
    return {"verdict": "ACCEPT", "violations": [], "n_rules": 4,
            "limits": S2.DEFAULT_DRC_LIMITS, "checked": 0}


def _accept_lvs(els):
    return {"verdict": "ACCEPT", "issues": [], "netlist": {}, "n_checks": 6}


def _make_mutations():
    orig = {
        "drc": S2.run_sc_pair_drc,
        "lvs": S2.sc_pair_lvs_signoff,
        "phys": S2.coupled_pair_physics,
        "cr": CR.cross_resonance,
        "bbox": S2._bbox,
        "disc": S2.RED_LINE_DISCLOSURE,
        "gds": S2.coupled_pair_gds,
    }

    def m1():
        S2.run_sc_pair_drc = _accept_drc

    def m2():
        S2.sc_pair_lvs_signoff = _accept_lvs

    def m3():
        o = orig["phys"]

        def bad(p=None):
            r = o(p)
            r["J_rel_err"] = 0.99
            return r
        S2.coupled_pair_physics = bad

    def m4():
        o = orig["cr"]

        def bad(*a, **k):
            r = o(*a, **k)
            r["ok"] = False
            return r
        CR.cross_resonance = bad

    def m5():
        S2._bbox = lambda d: (-1.0, -1.0, -1.0, -1.0)

    def m6():
        S2.RED_LINE_DISCLOSURE = {k: v for k, v in orig["disc"].items()
                                   if k != "physics"}

    def m7():
        S2.coupled_pair_gds = lambda *a, **k: b""

    def restore():
        S2.run_sc_pair_drc = orig["drc"]
        S2.sc_pair_lvs_signoff = orig["lvs"]
        S2.coupled_pair_physics = orig["phys"]
        CR.cross_resonance = orig["cr"]
        S2._bbox = orig["bbox"]
        S2.RED_LINE_DISCLOSURE = orig["disc"]
        S2.coupled_pair_gds = orig["gds"]

    muts = [("M1-DRC恒ACCEPT", m1), ("M2-LVS恒ACCEPT", m2),
            ("M3-relJ失真", m3), ("M4-CR恒否", m4),
            ("M5-bbox坍缩", m5), ("M6-披露缺键", m6), ("M7-GDS空", m7)]
    return muts, restore


def main() -> int:
    print("=" * 78)
    print("D-134 耦合对 突变探针（七突变各必红 · 还原复绿）")
    print("=" * 78)

    rc0 = run_smoke()
    base_green = (rc0 == 0)
    print(f"[基线] smoke 返回 {rc0}（期望 0=全绿）· {'绿' if base_green else '基线红(异常)'}")
    if not base_green:
        return 1

    muts, restore = _make_mutations()
    all_red = True
    for name, apply in muts:
        apply()
        rc = run_smoke()
        reddened = (rc != 0)
        all_red = all_red and reddened
        print(f"[{name}] 突变后 smoke 返回 {rc} · {'红(断言活)' if reddened else '仍绿(死断言!)'}")
        restore()

    rc2 = run_smoke()
    restored_green = (rc2 == 0)
    print(f"[还原] smoke 返回 {rc2} · {'复绿' if restored_green else '未复绿'}")
    ok = base_green and all_red and restored_green
    print()
    print(f"突变探针结论：基线绿={base_green} · 七突变各红={all_red} · 还原绿={restored_green}"
          f" => {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
