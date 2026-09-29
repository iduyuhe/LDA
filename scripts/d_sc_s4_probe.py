"""D-136 突变探针（scratch · 不入 CI）：证明 run_schip_s4_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

🔴 教训（见 d_sc_s1_probe.py / d_sc_s2_probe.py / d_sc_s3_probe.py 文件头）：探针
必须 patch 门禁**同一模块对象**（SM.S4）——门禁走 `from lda_qeda import sc_readout
as S4`，另起 `from lda_qeda import sc_readout` 会拿到不同实例 ⇒ 假绿。故一律经 SM 取对象。

人工记录（改动 → 应红判据）：
  · M1 run_readout_drc 恒 ACCEPT    ⇒ B2/B3/B4/B5/B6（DRC 违规漏判）应红
  · M2 readout_lvs_signoff 恒 ACCEPT ⇒ C4/C5/C6/C7（LVS 违规漏判）应红
  · M3 crosstalk_budget 杂散ZZ超限  ⇒ F1/F2/F7/F8（串扰预算失守）应红
  · M4 loss_budget T1 不足          ⇒ F5/F6/F7/F8（损耗预算失守）应红
  · M5 _bbox 坍缩                    ⇒ C1（合法 LVS 连通性假绿 → 红）应红
  · M6 披露缺 physics 键             ⇒ D1/D3（红线披露缺漏 · 物理标注缺）应红
  · M7 readout_gds 返空字节          ⇒ E1（GDS 真出失败）应红
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_s4_smoke as SM                             # noqa: E402

# 同一模块对象（见文件头教训）：经 SM 取，避免另起 import 拿到不同实例
S4 = SM.S4


def run_smoke() -> int:
    SM.PASS = 0
    SM.FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = SM.main()
    return rc


def _accept_drc(els, limits=None):
    return {"verdict": "ACCEPT", "violations": [], "n_rules": 10,
            "limits": S4.DEFAULT_READOUT_LIMITS, "checked": 0}


def _accept_lvs(els):
    # 含 netlist 子键，避免门禁 C2/C3 读键崩；M2 仍由 C4/C5/C6/C7 红（缺读出/短接/
    # 控制-地/无 net 的 REJECT 期望被假 ACCEPT 击穿）
    return {"verdict": "ACCEPT", "issues": [],
            "netlist": {"qubit_nets": 4, "feedline_segments": 2, "readout": 4,
                        "control": 4, "coupler": 4, "ground_nets": 1,
                        "edges_bridged": 4},
            "n_checks": 9}


def _make_mutations():
    orig = {
        "drc": S4.run_readout_drc,
        "lvs": S4.readout_lvs_signoff,
        "xt": S4.crosstalk_budget,
        "lb": S4.loss_budget,
        "bbox": S4._bbox,
        "disc": S4.RED_LINE_DISCLOSURE,
        "gds": S4.readout_gds,
    }

    def m1():
        S4.run_readout_drc = _accept_drc

    def m2():
        S4.readout_lvs_signoff = _accept_lvs

    def m3():
        o = orig["xt"]

        def bad(p=None):
            r = o(p)
            r["max_stray_zz_mhz"] = 9.99          # 远超 ZZ_STRAY_LIMIT_MHZ=1.0
            r["stray_zz_ok"] = False
            r["verdict"] = "REJECT"
            return r
        S4.crosstalk_budget = bad

    def m4():
        o = orig["lb"]

        def bad(p=None):
            r = o(p)
            r["min_t1_total_us"] = 0.5            # 远低于 T1_TARGET_US=20.0
            r["all_ok"] = False
            r["verdict"] = "REJECT"
            for q in r.get("per_qubit", []):
                q["ok"] = False
            return r
        S4.loss_budget = bad

    def m5():
        S4._bbox = lambda d: (-1.0, -1.0, -1.0, -1.0)

    def m6():
        S4.RED_LINE_DISCLOSURE = {k: v for k, v in orig["disc"].items()
                                   if k != "physics"}

    def m7():
        S4.readout_gds = lambda *a, **k: b""

    def restore():
        S4.run_readout_drc = orig["drc"]
        S4.readout_lvs_signoff = orig["lvs"]
        S4.crosstalk_budget = orig["xt"]
        S4.loss_budget = orig["lb"]
        S4._bbox = orig["bbox"]
        S4.RED_LINE_DISCLOSURE = orig["disc"]
        S4.readout_gds = orig["gds"]

    muts = [("M1-DRC恒ACCEPT", m1), ("M2-LVS恒ACCEPT", m2),
            ("M3-杂散ZZ超限", m3), ("M4-损耗T1不足", m4),
            ("M5-bbox坍缩", m5), ("M6-披露缺键", m6), ("M7-GDS空", m7)]
    return muts, restore


def main() -> int:
    print("=" * 78)
    print("D-136 读出/控制+串扰/损耗 突变探针（七突变各必红 · 还原复绿）")
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
