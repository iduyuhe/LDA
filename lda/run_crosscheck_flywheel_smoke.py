"""对照报告飞轮 smoke（v0.8.30 · 入 CI core）。

验证 `lda_harness.crosscheck_report` 飞轮：
  ① 生成 Markdown + JSON 对照报表（跨源死标量对照）；
  ② 归档历史快照（reports/crosscheck_history/）；
  ③ 覆盖度指标（引擎通过 / 实证覆盖 / 实证 rel）符合当前账本；
  ④ 重复运行幂等（报告文件可复写、历史累加）。

红线：全部死标量；不依赖 gdsfactory；复用 benchmark_report 同一份对照逻辑。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class CrosscheckFlywheelSmoke(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lda_xc_")
        self.hist = os.path.join(self.tmp, "crosscheck_history")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_flywheel_build_and_archive(self):
        from lda_harness.crosscheck_report import build_report
        r = build_report(quick=True, out_dir=self.tmp, archive=True)
        # ① 报告文件生成
        self.assertTrue(os.path.exists(r["md_path"]), "Markdown 报告未生成")
        self.assertTrue(os.path.exists(r["json_path"]), "JSON 报告未生成")
        # ② 历史归档
        self.assertTrue(os.path.exists(self.hist) and
                        any(f.endswith(".json") for f in os.listdir(self.hist)),
                        "历史快照未归档")
        # ③ 覆盖度指标符合账本（quick 子集 18 引擎 / 9 实证语料全覆盖）
        s = r["score"]
        self.assertEqual(s["engines_total"], 18, "quick 子集应 18 引擎")
        # quick 子集应全部 passed（与设计闭环一致）
        self.assertEqual(s["engines_passed"], 18)
        self.assertEqual(s["empirical_covered"], 9, "实证语料 9 条应全有引擎对照")
        # JSON 报告可解析且含 rows
        data = json.load(open(r["json_path"], encoding="utf-8"))
        self.assertIn("rows", data)
        self.assertIn("corpus_coverage", data)

    def test_flywheel_idempotent_rerun(self):
        from lda_harness.crosscheck_report import build_report
        r1 = build_report(quick=True, out_dir=self.tmp, archive=True)
        n1 = len(os.listdir(self.hist))
        # 重复运行：报告文件复写、历史累加（>=n1）
        r2 = build_report(quick=True, out_dir=self.tmp, archive=True)
        n2 = len(os.listdir(self.hist))
        self.assertGreaterEqual(n2, n1, "历史快照应随重跑累加")
        self.assertTrue(os.path.exists(r2["md_path"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
