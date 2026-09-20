"""LDA 流片级验证管道 smoke（任务 259 · 门3 接口细化门禁）。

验证：
  1. 管道全链路可运行（PDK → DRC → 工艺角 → 实测回流接口）
  2. 正例 ACCEPT（合规器件三角落全过）
  3. 门禁为真：min_width 违规 → REJECT（TT/SS/FF 全 FAIL）
  4. 工艺角缩放有效（SS/FF 参数与 TT 不同但合法）
  5. 实测回流：submit_empirical 占位提交走实证语料流（溯源门禁/防重/校验）

🔴 v0.9.116 修复（「秒级 id × 跨进程防重守卫」= 同秒重跑必假红）
------------------------------------------------------------------
旧版 `test_empirical_submission_interface` 有两处结构性缺陷（实测取证）：

  (R-a) **唯一 id 来源是秒级时间戳** ——
        `uniq = f"tapeout-sim-uniq-{int(_t.time())}"`，而防重守卫的 pending
        记录**跨进程持久化** ⇒ 同一秒内第二次运行 id 相同 ⇒ 必被判
        `rejected` ⇒ `assertEqual(status, "accepted_pending")` 假红。
        实测：同秒两次 → 第 1 次 accepted_pending / 第 2 次 rejected（防重守卫）。

  (R-b) **测试写入仓库内共享语料库（根因）** ——
        三处提交调用均**不传 `proposals_path`** ⇒ 落到
        `lda_pdk/empirical_proposals.json`（`.gitignore` 忽略的「生态共建社区
        贡献库」）。实测该文件当日积压 **38 条 pending，100% 为
        `proposed_by="tapeout-smoke"` 的测试残留**（method=simulated，非真实测量）
        ⇒ 既是**污染**，也使本 smoke **非 hermetic**（结果依赖历史残留）。
        R-b 是 R-a 的成因：正因为写共享库，才需要「绕防重」的秒级 id hack。

修法（与 `run_empirical_anchor_smoke` / `run_empirical_d62_report` 同范式）：
  ① `setUp` 建 `tempfile.mkdtemp()` 临时提案库；所有提交显式传 `proposals_path`
     （`run_tapeout_pipeline` 为此新增可注入形参，向后兼容）。
  ② 唯一 id 改用 `uuid4` ⇒ 与时钟无关，同秒重跑亦必唯一。
  ③ 顺带收紧断言：旧版「accepted_pending / rejected 二选一都算过」是**弱断言**
     （其通过依赖脏库残留，属偶然），现改为确定性断言，并**补一条防重守卫的
     正向断言**（防重守卫此前只被偶然覆盖，从未被显式验证）。
  ④ 删掉旧版悬空的重复调用（结果被丢弃、每次白写一条残留记录）。

同类复发预防：`run_smoke_isolation_ratchet_smoke.py`（v0.9.116 新增 core 护栏）
静态扫描全仓 `lda/run_*_smoke.py`：① empirical 存储 mutator 调用必传 path 关键字；
② 不得出现 `int(time.time())`（秒级整数时间戳 = 脆弱唯一性来源）。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
import uuid

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)


class TapeoutPipelineSmoke(unittest.TestCase):

    def setUp(self):
        # 🔴 v0.9.116：测试隔离——本 smoke 的实证语料读写全部落在**临时库**，
        #    绝不触碰仓库内共享库（见模块 docstring R-b）。
        self.tmp = tempfile.mkdtemp(prefix="lda_tapeout_")
        self.pp = os.path.join(self.tmp, "empirical_proposals.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

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
        from lda_pdk.empirical import (
            submit_measurement, DEFAULT_PROPOSALS_PATH,
        )

        # ① 管道占位提交（submit_empirical=True）——证接口连通 + 红线可验证。
        #    占位 citation **不含 DOI/arXiv/公开 URL 定位符** ⇒ D-63 溯源门禁必须拒
        #    （=「真实流片前不占位入库」；该拒发生在 store.add 之前 ⇒ 不写任何库）。
        #    旧版此处只断言「二选一」，掩盖了真实语义 ⇒ v0.9.116 收紧为确定性断言。
        r = run_tapeout_pipeline({"Waveguide": {"width": 0.5}},
                                 submit_empirical=True,
                                 proposals_path=self.pp)
        self.assertIsNotNone(r.empirical_submission)
        st = r.empirical_submission
        self.assertEqual(st.get("status"), "rejected",
                         msg=f"占位提交（无定位符）不得入库：{st}")
        self.assertIn("溯源门禁", st.get("reason", ""))

        # ② 唯一 id 走通 accepted_pending 路径。
        #    🔴 id 用 uuid4（与时钟无关）——旧版用 int(time.time())，同秒重跑必撞防重守卫。
        uniq = "tapeout-sim-uniq-" + uuid.uuid4().hex[:10]
        # D-63 溯源门禁：citation 必须带 DOI/arXiv/公开 URL 定位符才予收录。
        # 本用例为接口连通性验证（method=simulated，非真实测量），定位符指向
        # SkyWater SKY130 公开 PDK 的公开 DRC 规则仓库（真实可访问的公开出处）。
        PAY = {
            "id": uniq, "device": "Waveguide", "metric": "drc_pass",
            "measured_value": 1.0, "uncertainty_abs": 0.0,
            "fab_source": "smoke",
            "citation": ("smoke 接口验证（simulated，非真实测量）；判据出处："
                         "SkyWater SKY130 公开 PDK DRC 规则集 "
                         "https://github.com/google/skywater-pdk"),
            "source_url": "https://github.com/google/skywater-pdk",
            "method": "simulated", "proposed_by": "tapeout-smoke",
        }
        st2 = submit_measurement(dict(PAY), proposals_path=self.pp)
        self.assertEqual(st2.get("status"), "accepted_pending",
                         msg=f"唯一 id 应走通：{st2}")
        # 断言返回体的**真实键**（旧版断言 st.get("citation")——该键并不存在，
        # 只因旧路径恒为 rejected 才从未走到 ⇒ 是颗埋着的假绿地雷）。
        self.assertEqual(st2.get("id"), uniq)
        self.assertEqual(st2.get("review_status"), "pending")
        self.assertIn("待具名人工评审", st2.get("reason", ""))

        # ③ 防重守卫（正向断言 · v0.9.116 补）：同 id 重提必被拒。
        #    旧版此语义只被「脏库残留」偶然覆盖，且用二选一弱断言 ⇒ 从未被显式验证。
        st_dup = submit_measurement(dict(PAY), proposals_path=self.pp)
        self.assertEqual(st_dup.get("status"), "rejected",
                         msg=f"同 id 重提须被防重守卫拒：{st_dup}")
        self.assertIn("防重守卫", st_dup.get("reason", ""))
        self.assertIn(uniq, st_dup.get("reason", ""))

        # ④ D-63 溯源门禁反向验证：无定位符的 citation 必须被拒（A/B/X 分级硬门禁）
        st3 = submit_measurement({
            "id": uniq + "-noref", "device": "Waveguide", "metric": "drc_pass",
            "measured_value": 1.0, "uncertainty_abs": 0.0,
            "fab_source": "smoke", "citation": "无出处的自述数据",
            "method": "simulated", "proposed_by": "tapeout-smoke",
        }, proposals_path=self.pp)
        self.assertEqual(st3.get("status"), "rejected",
                         msg=f"无定位符应被溯源门禁拒收：{st3}")
        self.assertIn("溯源门禁", st3.get("reason", ""))

        # ⑤ 隔离自证（v0.9.116 立）：本 smoke 不得污染仓库内共享语料库。
        #    本次 id 泄漏即被抓 —— 泄漏必然使该文件被创建/写入 ⇒ 本断言不会空洞通过。
        #    （repo 级不变式「共享库不得含任何测试残留」由
        #      `run_smoke_isolation_ratchet_smoke.py` 持有：那里扫描全仓、
        #      归因清晰；放在此处会变成「别家 smoke 污染、本 smoke 报错」的混淆归因。）
        leaked = (open(DEFAULT_PROPOSALS_PATH, encoding="utf-8").read()
                  if os.path.exists(DEFAULT_PROPOSALS_PATH) else "")
        self.assertNotIn(uniq, leaked,
                         msg="测试 id 泄漏进了共享语料库（测试未隔离）")

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
    # F-18（v0.9.113 · 波次 2 · 审计：「19 个 smoke 用 unittest、其余用自研
    # check() ⇒ 两套测试范式并存」）：本文件保留标准 unittest 写测试体，
    # 但**报告与退出契约统一走 smoke_kit** —— 逐条 `  [PASS] <name>`，
    # 失败/错误仍打标准 FAIL:/ERROR: 块（含 traceback，CI 判定「失败痕迹」可命中，
    # 不会被误判 SKIP），rc 与 `unittest.main(verbosity=2)` 逐位一致。
    from lda_harness.smoke_kit import run_unittest_suite

    raise SystemExit(run_unittest_suite(TapeoutPipelineSmoke))
