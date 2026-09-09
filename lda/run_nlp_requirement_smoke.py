"""T0-2 NLP 需求入口护栏（WBS-T0-2）。

验收（判据 D 思路，防常数假绿）：
  ① 中文需求正确解析为结构化 req（八信道→8 等）
  ② 英文需求正确解析（含「数字在前、关键词在后」语序：50GHz spacing）
  ③ 缺失字段回退典型默认值并标注 source=default——**绝不杜撰数字**
  ④ 反常数假绿：原文数字不同 → req 必须不同（证明解析非常量）
"""
import unittest

from lda_harness.proposal_compiler import parse_nlp_requirement, design_pipeline_from_nlp


class TestNLPRequirement(unittest.TestCase):

    def test_cn_parsing(self):
        r = parse_nlp_requirement(
            "我要一个八信道、间隔50GHz、带宽25GHz、余量2dB的WDM链路")
        self.assertEqual(r["req"].get("n_channels"), 8)
        self.assertEqual(r["req"].get("channel_spacing_ghz"), 50.0)
        self.assertEqual(r["req"].get("filter_bw_ghz"), 25.0)
        self.assertEqual(r["req"].get("link_budget_db"), 2.0)
        # 中文数字 / 关键词映射来源正确标注
        self.assertEqual(r["source"]["n_channels"], "parsed_cn")
        self.assertEqual(r["source"]["channel_spacing_ghz"], "parsed")

    def test_en_parsing_bidirectional_order(self):
        # 英文习惯「数字在前、关键词在后」：50GHz spacing / 25GHz bandwidth / 2dB margin
        r = parse_nlp_requirement(
            "8 channels, 50GHz spacing, 25GHz bandwidth, 2dB margin, tx power 3dBm")
        self.assertEqual(r["req"].get("n_channels"), 8)
        self.assertEqual(r["req"].get("channel_spacing_ghz"), 50.0)
        self.assertEqual(r["req"].get("filter_bw_ghz"), 25.0)
        self.assertEqual(r["req"].get("link_budget_db"), 2.0)
        self.assertEqual(r["req"].get("p_tx_dbm"), 3.0)

    def test_missing_field_falls_back_default_no_fabrication(self):
        # 模糊需求：只给信道数，其余回退默认且明确标注 default（不杜撰）
        r = parse_nlp_requirement("给我做个8信道滤波器")
        self.assertEqual(r["req"].get("n_channels"), 8)
        # 未提供的字段不应出现在 req（避免编造物理数字）
        self.assertNotIn("channel_spacing_ghz", r["req"])
        self.assertNotIn("filter_bw_ghz", r["req"])
        self.assertEqual(r["source"]["channel_spacing_ghz"], "default")
        self.assertEqual(r["source"]["filter_bw_ghz"], "default")
        # 经 design_pipeline 仍跑通（默认链路可行）
        res = design_pipeline_from_nlp("做个8信道滤波器", n_top=1)
        self.assertIn("ranked", res)
        self.assertEqual(res["nlp_source"]["n_channels"], "parsed")

    def test_reverse_numbers_must_change_req(self):
        # 反常数假绿：原文数字不同 → 解析结果必须不同
        a = parse_nlp_requirement("4信道 间隔100GHz")
        b = parse_nlp_requirement("8信道 间隔100GHz")
        self.assertNotEqual(a["req"].get("n_channels"), b["req"].get("n_channels"))
        self.assertEqual(a["req"].get("n_channels"), 4)
        self.assertEqual(b["req"].get("n_channels"), 8)
        # 间隔解析随原文变化
        c = parse_nlp_requirement("4信道 间隔50GHz")
        d = parse_nlp_requirement("4信道 间隔200GHz")
        self.assertNotEqual(c["req"].get("channel_spacing_ghz"),
                            d["req"].get("channel_spacing_ghz"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
