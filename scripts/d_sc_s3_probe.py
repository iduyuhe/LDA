"""D-135 突变探针（scratch · 不入 CI）：证明 run_schip_s3_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

🔴 教训（见 d_sc_s1_probe.py / d_sc_s2_probe.py 文件头）：探针必须 patch 门禁
**同一模块对象**（SM.S3 / SM.CR）——门禁走 `from lda_qeda import sc_array as S3`，
另起 `from lda_qeda import sc_array` 会拿到不同实例 ⇒ 假绿。故一律经 SM 取对象。

人工记录（改动 → 应红判据）：
  · M1 run_sc_array_drc 恒 ACCEPT    ⇒ B2/B3/B4/B6（DRC 违规漏判）应红
  · M2 sc_array_lvs_signoff 恒 ACCEPT ⇒ C4/C5/C6/C7（LVS 违规漏判）应红
  · M3 array_physics relJ=0.99       ⇒ F1/F5（J 双验证失守）应红
  · M4 cross_resonance ok=False      ⇒ F2/F5（CR 有效模型落窗失守）应红
  · M5 _bbox 坍缩                    ⇒ C1（合法 LVS 连通性假绿 → 红）应红
  · M6 披露缺 physics 键             ⇒ D1（红线披露缺漏）应红
  · M7 array_gds 返空字节           ⇒ E1（GDS 真出失败）应红
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_s3_smoke as SM                             # noqa: E402

# 同一模块对象（见文件头教训）：经 SM 取，避免另起 import 拿到不同实例
S3 = SM.S3
CR = SM.CR


def run_smoke() -> int:
    SM.PASS = 0
    SM.FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = SM.main()
    return rc


def _accept_drc(els, limits=None):
    return {"verdict": "ACCEPT", "violations": [], "n_rules": 6,
            "limits": S3.DEFAULT_DRC_LIMITS, "checked": 0}


def _accept_lvs(els):
    # 含 netlist 子键，避免门禁 C2/C3 读键崩；M2 仍由 C3/C4/C5/C6/C7 红（拓扑边数/
    # 缺耦合器/误桥/地短接/无 net 的 REJECT 期望被假 ACCEPT 击穿）
    return {"verdict": "ACCEPT", "issues": [],
            "netlist": {"qubit_nets": 4, "coupler": 4, "ground_nets": 1,
                        "edges_bridged": 4, "graph_connected": True},
            "n_checks": 6}


def _make_mutations():
    orig = {
        "drc": S3.run_sc_array_drc,
        "lvs": S3.sc_array_lvs_signoff,
        "phys": S3.array_physics,
        "cr": CR.cross_resonance,
        "bbox": S3._bbox,
        "disc": S3.RED_LINE_DISCLOSURE,
        "gds": S3.array_gds,
    }

    def m1():
        S3.run_sc_array_drc = _accept_drc

    def m2():
        S3.sc_array_lvs_signoff = _accept_lvs

    def m3():
        o = orig["phys"]

        def bad(p=None):
            r = o(p)
            r["max_relJ"] = 0.99
            r["all_j_double_validated"] = False
            r["J_rel_err"] = 0.99
            for e in r.get("edges", []):
                e["J_rel_err"] = 0.99
                e["J_double_validated"] = False
            return r
        S3.array_physics = bad

    def m4():
        o = orig["cr"]

        def bad(*a, **k):
            r = o(*a, **k)
            r["ok"] = False
            return r
        CR.cross_resonance = bad

    def m5():
        S3._bbox = lambda d: (-1.0, -1.0, -1.0, -1.0)

    def m6():
        S3.RED_LINE_DISCLOSURE = {k: v for k, v in orig["disc"].items()
                                   if k != "physics"}

    def m7():
        S3.array_gds = lambda *a, **k: b""

    def restore():
        S3.run_sc_array_drc = orig["drc"]
        S3.sc_array_lvs_signoff = orig["lvs"]
        S3.array_physics = orig["phys"]
        CR.cross_resonance = orig["cr"]
        S3._bbox = orig["bbox"]
        S3.RED_LINE_DISCLOSURE = orig["disc"]
        S3.array_gds = orig["gds"]

    muts = [("M1-DRC恒ACCEPT", m1), ("M2-LVS恒ACCEPT", m2),
            ("M3-relJ失真", m3), ("M4-CR恒否", m4),
            ("M5-bbox坍缩", m5), ("M6-披露缺键", m6), ("M7-GDS空", m7)]
    return muts, restore


def main() -> int:
    print("=" * 78)
    print("D-135 阵列 突变探针（七突变各必红 · 还原复绿）")
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
