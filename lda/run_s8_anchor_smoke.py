"""T0-3 S8 锚接入管线护栏（WBS-T0-3）。

验收（判据 D 思路，防常数假绿 / 防 S8 成装饰）：
  ① 合理 OSNR 链路 → S8 PASS（p5 ≥ 需求）
  ② 噪声系数退化（nf=40，真实放大器仅 3–8dB）→ S8 FAIL → 整体被剪枝；
     且 S1–S7 不受影响（隔离证明 S8 真生效，非误伤）
  ③ 纯 WDM 无放大器链路 → S8 标记 N/A，不杜撰、不参与判决
  ④ 反向：nf_db ±20% → S8 p5 必须变化（反常数假绿）
方法学：S8 候选=闭式高斯 p5（s8_gaussian_moments，v0.9.29 T-3 已证伪独立），
与蒙特卡洛 golden 是两种算法；此处作预算阈值死标量检查。
"""
import unittest

from lda_harness.proposal_compiler import compile_proposal, screen_proposal
from lda_harness.statistical_anchor import s8_gaussian_moments

Z = 1.6448536269514722  # 高斯 5% 分位系数


def _s8(proposal):
    sc = screen_proposal(proposal)
    return sc, [c for c in sc["checks"] if c["anchor"] == "S8-osnr-p5"][0]


class TestS8Anchor(unittest.TestCase):

    def test_s8_pass_reasonable_link(self):
        sc, s8 = _s8(compile_proposal(
            {"n_channels": 4, "p_sig_dbm": 0.0, "n_amp": 1,
             "nf_db": 5.0, "bw_ghz": 50.0, "min_osnr_p5_db": 15.0}))
        self.assertTrue(s8["applicable"])
        self.assertTrue(s8["passed"])
        self.assertGreaterEqual(s8["value"], 15.0)
        self.assertTrue(sc["accepted"])

    def test_s8_fail_degraded_nf_rejects_only_s8(self):
        sc, s8 = _s8(compile_proposal(
            {"n_channels": 4, "p_sig_dbm": 0.0, "n_amp": 1,
             "nf_db": 40.0, "bw_ghz": 50.0, "min_osnr_p5_db": 15.0}))
        self.assertTrue(s8["applicable"])
        self.assertFalse(s8["passed"])           # S8 真挂
        self.assertLess(s8["value"], 15.0)
        self.assertFalse(sc["accepted"])          # 整体被剪枝
        # 隔离：S1/S2/S5/S7 仍全过，失败仅来自 S8
        others = [(c["anchor"], c["passed"])
                   for c in sc["checks"] if c["anchor"] != "S8-osnr-p5"]
        self.assertTrue(all(p for _, p in others), others)

    def test_s8_na_for_pure_wdm_no_fabrication(self):
        # 纯 WDM 链路不提供 OSNR 参数 → S8 必须 N/A，不杜撰
        sc, s8 = _s8(compile_proposal({"n_channels": 8}))
        self.assertFalse(s8["applicable"])
        self.assertIsNone(s8["value"])
        self.assertTrue(s8["passed"])            # 占位 True，不影响判决
        self.assertTrue(sc["accepted"])

    def test_reverse_nf_perturbation_changes_s8(self):
        # 反常数假绿：nf_db 扰动 → S8 p5 必须变化
        def p5(nf):
            mu, sig = s8_gaussian_moments(nf_db=nf)
            return mu - Z * sig
        lo, hi = p5(4.0), p5(6.0)               # ±20% 扰动
        self.assertNotAlmostEqual(lo, hi, places=3)
        self.assertGreater(lo, hi)               # nf 越大 OSNR 越差


if __name__ == "__main__":
    unittest.main(verbosity=2)
