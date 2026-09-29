"""D-133 突变探针（scratch · 不入 CI）：证明 run_schip_s1_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 run_sc_drc 恒 ACCEPT ⇒ B2（CPW 太细应 REJECT）应红
  · M2 sc_lvs_signoff 恒 ACCEPT ⇒ C2/C3/C4/C5（LVS 应 REJECT）应红
  · M3 run_selfchecks 恒 False ⇒ A1 应红
  · M4 koch_f01 返回 999 ⇒ F1（物理 rel≤3%）应红
  · M5 _bbox 坍缩 ⇒ B1（合法 DRC ACCEPT）+ C1（合法 LVS ACCEPT）应红
  · M6 默认 min_width 抹成 100 ⇒ B1（合法 DRC ACCEPT）应红
  · M7 披露抹掉 ⇒ D1 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.SCD / S.TS）——门禁走双路兜底
   可能绑成 top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_s1_smoke as S                          # noqa: E402

SCD = S.SCD                                            # 同一模块对象（见文件头教训）
TS = S.TS


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                              # 突变致病态 ⇒ 崩溃也算红
        rc = 99
        buf.write(f"[FAIL] 门禁异常：{type(e).__name__}: {e}")
    out = buf.getvalue()
    return rc, out.count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _drc = SCD.run_sc_drc
    _lvs = SCD.sc_lvs_signoff
    _self = SCD.run_selfchecks
    _bbox = SCD._bbox
    _limits = dict(SCD.DEFAULT_DRC_LIMITS)
    _disc = SCD.RED_LINE_DISCLOSURE
    _koch = TS.koch_f01

    # M1 run_sc_drc 恒 ACCEPT
    SCD.run_sc_drc = lambda el, limits=None: {"verdict": "ACCEPT",
                                              "violations": [], "n_rules": 4,
                                              "limits": {}, "checked": 0}
    rows.append(("M1 run_sc_drc 恒 ACCEPT", *run_smoke()))
    SCD.run_sc_drc = _drc

    # M2 sc_lvs_signoff 恒 ACCEPT
    SCD.sc_lvs_signoff = lambda el: {"verdict": "ACCEPT", "issues": [],
                                      "netlist": {}, "n_checks": 5}
    rows.append(("M2 sc_lvs_signoff 恒 ACCEPT", *run_smoke()))
    SCD.sc_lvs_signoff = _lvs

    # M3 run_selfchecks 恒 False
    SCD.run_selfchecks = lambda verbose=False: False
    rows.append(("M3 run_selfchecks 恒 False", *run_smoke()))
    SCD.run_selfchecks = _self

    # M4 koch_f01 返回 999（物理造假）
    TS.koch_f01 = lambda ej, ec: 999.0
    rows.append(("M4 koch_f01 返回 999", *run_smoke()))
    TS.koch_f01 = _koch

    # M5 _bbox 坍缩（所有元素 bbox→原点）
    SCD._bbox = lambda d: (0.0, 0.0, 0.0, 0.0)
    rows.append(("M5 _bbox 坍缩", *run_smoke()))
    SCD._bbox = _bbox

    # M6 默认 min_width 抹成 100
    SCD.DEFAULT_DRC_LIMITS = dict(_limits, min_width_um=100.0)
    rows.append(("M6 默认 min_width 抹成 100", *run_smoke()))
    SCD.DEFAULT_DRC_LIMITS = _limits

    # M7 披露抹掉
    SCD.RED_LINE_DISCLOSURE = {"role": "x"}
    rows.append(("M7 披露抹掉", *run_smoke()))
    SCD.RED_LINE_DISCLOSURE = _disc

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：超导 transmon 单元 门禁（D-133）")
    print("=" * 74)
    for name, rc, nf in rows:
        print(f"  {name:32s} exit={rc}  [FAIL]×{nf}")

    n_probe = len(rows) - 2
    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in range(1, 1 + n_probe))
          and rows[-1][1] == 0 and rows[-1][2] == 0)
    print()
    print(f"探针结论：{'PASS —— %d 条突变各必红，还原复绿' % n_probe if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
