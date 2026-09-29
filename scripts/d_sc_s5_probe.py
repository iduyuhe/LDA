"""D-137/D-142/D-143 突变探针（scratch · 不入 CI）：证明 run_schip_s5_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

🔴 教训（见 d_sc_s1..s4_probe.py 文件头）：探针必须 patch 门禁**同一模块对象**
（SM.SR / SM.FA）——门禁走 `from lda_qeda import sc_routing as SR`，另起
`from lda_qeda import sc_routing` 会拿到不同实例 ⇒ 假绿。故一律经 SM 取对象。

人工记录（改动 → 应红判据）：
  · M1 run_routing_drc 恒 ACCEPT     ⇒ B2/B3/B4（路由 DRC 违规漏判）应红
  · M2 routed_array_lvs 恒 ACCEPT    ⇒ C3/C4/C5（LVS 违规漏判）应红
  · M3 routing_capacity 错值         ⇒ F9（路由容量自洽）应红
  · M4 路由披露缺 routing 键         ⇒ D1（披露缺漏）应红
  · M5 routed_gds 返空字节           ⇒ E1（GDS 真出失败）应红
  · M6 FA.check_plan 恒 ok=True      ⇒ A2（频率自检：碰撞/共振/近邻漏检）应红
  · M7 FA.plan 恒 REJECT             ⇒ F 四个规模的频率规划应红
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_s5_smoke as SM                            # noqa: E402

SR = SM.SR
FA = SM.FA


def run_smoke() -> int:
    SM.PASS = 0
    SM.FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = SM.main()
    return rc


def _accept_drc(els, limits=None):
    return {"verdict": "ACCEPT", "violations": [], "n_rules": len(SR.ROUTING_DRC_RULES),
            "limits": SR.DEFAULT_ROUTING_LIMITS, "checked": 0}


def _accept_lvs(els):
    return {"verdict": "ACCEPT", "issues": [],
            "netlist": {"qubit_nets": 4, "feedline_segments": 2, "readout": 4,
                        "control": 4, "pads_control": 4, "pads_total": 6, "coupler": 4,
                        "ground_nets": 1, "edges_bridged": 4},
            "n_checks": 11}


def _make_mutations():
    orig = {
        "drc": SR.run_routing_drc,
        "lvs": SR.routed_array_lvs,
        "cap": SR.routing_capacity,
        "disc": SR.RED_LINE_DISCLOSURE,
        "gds": SR.routed_gds,
        "check": FA.check_plan,
        "plan": FA.plan,
    }

    def m1():
        SR.run_routing_drc = _accept_drc

    def m2():
        SR.routed_array_lvs = _accept_lvs

    def m3():
        def bad(p=None):
            r = orig["cap"](p)
            r["n_signals"] = 0
            r["pitch_y_eff_um"] = 0.0
            return r
        SR.routing_capacity = bad

    def m4():
        SR.RED_LINE_DISCLOSURE = {k: v for k, v in orig["disc"].items()
                                  if k != "routing"}

    def m5():
        SR.routed_gds = lambda *a, **k: b""

    def m6():
        o = orig["check"]

        def bad(freqs, edges, params=None):
            r = o(freqs, edges, params)
            r["ok"] = True
            r["n_collisions"] = 0
            r["n_resonance_hits"] = 0
            r["nn_violations"] = []
            r["detune_violations"] = []
            return r
        FA.check_plan = bad

    def m7():
        o = orig["plan"]

        def bad(params=None):
            r = o(params)
            r["verdict"] = "REJECT"
            return r
        FA.plan = bad

    def restore():
        SR.run_routing_drc = orig["drc"]
        SR.routed_array_lvs = orig["lvs"]
        SR.routing_capacity = orig["cap"]
        SR.RED_LINE_DISCLOSURE = orig["disc"]
        SR.routed_gds = orig["gds"]
        FA.check_plan = orig["check"]
        FA.plan = orig["plan"]

    muts = [("M1-路由DRC恒ACCEPT", m1), ("M2-路由LVS恒ACCEPT", m2),
            ("M3-路由容量错值", m3), ("M4-路由披露缺键", m4),
            ("M5-路由GDS空", m5), ("M6-频率校验恒ok", m6),
            ("M7-频率规划恒REJECT", m7)]
    return muts, restore


def main() -> int:
    print("=" * 78)
    print("D-137/D-142/D-143 S5 门禁 突变探针（七突变各必红 · 还原复绿）")
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
