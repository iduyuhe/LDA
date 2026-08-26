"""LDA 流片级验证管道 smoke（任务 259 · 门3 接口细化门禁）。

验证：
  1. 管道全链路可运行（PDK → DRC → 工艺角 → 实测回流接口）
  2. 正例 ACCEPT（合规器件三角落全过）
  3. 门禁为真：min_width 违规 → REJECT（TT/SS/FF 全 FAIL）
  4. 工艺角缩放有效（SS/FF 参数与 TT 不同但合法）
  5. 实测回流：submit_empirical 占位提交走实证语料流（防重/校验）
"""
from __future__ import annotations

import sys
import os
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class TapeoutPipelineSmoke(unittest.TestCase):

    def test_pipeline_positive_accept(self):
        from lda_pdk.tapeout_pipeline import (
            run_tapeout_pipeline, tapeout_to_dict,
        )
        r = run_tapeout_pipeline({
            "RingAddDrop": {"R": 10.0, "gap": 0.3},
            "DirectionalCoupler": {"gap": 0.3, "width": 0.5},
            "Waveguide": {"width": 0.5},
        })
        d = tapeout_to_dict(r)
        self.assertTrue(r.drc_passed, msg=r.drc_violations)
        self.assertTrue(r.corners_all_pass)
        self.assertTrue(r.accepted)
        self.assertEqual(d["verdict"], "ACCEPT")
        self.assertEqual(len(r.corners), 3)  # SS/TT/FF
        self.assertIsNone(r.empirical_submission)  # 默认不占位提交
        self.assertIn("门3", r.honest_note)

    def test_pipeline_negative_reject(self):
        from lda_pdk.tapeout_pipeline import run_tapeout_pipeline
        r = run_tapeout_pipeline({"Waveguide": {"width": 0.20}})
        self.assertFalse(r.drc_passed)
        self.assertFalse(r.accepted)
        self.assertFalse(r.corners_all_pass)
        self.assertTrue(any("min_width" in v["rule"] for v in r.drc_violations))
        # 违规明细含实测值与要求值
        v = r.drc_violations[0]
        self.assertEqual(v["required"], 0.4)  # NOEIC min_width
        self.assertLess(v["value"], v["required"])

    def test_corner_scaling(self):
        from lda_pdk.tapeout_pipeline import _scale_params, PROCESS_CORNERS
        p = {"width": 0.5, "gap": 0.3, "n_core": 3.48}
        ps = _scale_params(p, PROCESS_CORNERS["SS"])
        pf = _scale_params(p, PROCESS_CORNERS["FF"])
        # SS 线宽偏小、gap 偏大；FF 相反（工艺波动方向正确）
        self.assertLess(ps["width"], p["width"])
        self.assertGreater(ps["gap"], p["gap"])
        self.assertGreater(pf["width"], p["width"])
        self.assertLess(pf["gap"], p["gap"])

    def test_empirical_submission_interface(self):
        from lda_pdk.tapeout_pipeline import run_tapeout_pipeline
        r = run_tapeout_pipeline({"Waveguide": {"width": 0.5}},
                                 submit_empirical=True)
        self.assertIsNotNone(r.empirical_submission)
        st = r.empirical_submission
        # 走实证语料流：accepted_pending（待具名评审）或 rejected（防重守卫）。
        # 防重守卫是特征（同一 id 已存在 → 拒重提），两种状态都证明接口连通。
        self.assertIn(st.get("status"), ("accepted_pending", "rejected"))
        if st.get("status") == "accepted_pending":
            self.assertTrue(st.get("citation"))
        else:
            # rejected = 防重守卫（此前已提交同 id）或校验失败 → 必有 reason
            self.assertTrue(st.get("reason"),
                            msg="rejected 须带 reason（防重/校验）")
        # 用时间戳唯一 id 验证 accepted_pending 路径（绕过防重）
        import time as _t
        uniq = f"tapeout-sim-uniq-{int(_t.time())}"
        r2 = run_tapeout_pipeline({"Waveguide": {"width": 0.5}},
                                  submit_empirical=True)
        # 复用管道内的 id 构造：直接调 submit 验证唯一 id 走通
        from lda_pdk.empirical import submit_measurement
        st2 = submit_measurement({
            "id": uniq, "device": "Waveguide", "metric": "drc_pass",
            "measured_value": 1.0, "uncertainty_abs": 0.0,
            "fab_source": "smoke", "citation": "tapeout smoke 唯一 id 验证",
            "method": "simulated", "proposed_by": "tapeout-smoke",
        })
        self.assertEqual(st2.get("status"), "accepted_pending",
                         msg=f"唯一 id 应走通：{st2}")

    def test_pdk_interface(self):
        from lda_pdk.tapeout_pipeline import _load_pdk
        pdk = _load_pdk()
        self.assertIsNotNone(pdk)
        self.assertTrue(pdk.foundry)
        self.assertTrue(pdk.node)
        # 设计规则表可用（rules_from_pdk 返回 min_width 等）
        from lda_l2.drc import rules_from_pdk
        rules = rules_from_pdk(pdk)
        self.assertIn("min_width_um", rules)
        self.assertIn("min_bend_R_um", rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
