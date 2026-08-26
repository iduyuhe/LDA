"""计数一致性机器断言 smoke（v0.8.10 · 防计数漂移根治）。

背景：v0.8.10 维护发现两类计数漂移（L1/实证锚 smoke 硬编码题数过时、
README 引擎域计数「光子 9 + 量子 6」与代码 ENGINE_DOMAIN 实际 8+7 不符）。
本 smoke 把「宣传口径 vs 代码事实」的一致性变成**机器断言**：
所有关键计数从代码动态读取，再断言 README 宣传串包含正确数字——
今后任何引擎/包/题库/CI 条数变化而文档未同步，立即 FAIL 拦截。

断言维度（全部死标量，LLM 不进判决路径）：
  1. 引擎结构：ENGINE_KINDS 22（15 设计量 + 5 loss + 2 有源）、光子 15、量子 7
  2. 包结构：PACKAGE_KINDS 11（22 引擎 + 11 包 = 33 类端到端）
  3. 题库：BENCHMARK_ORDER 40 题（B1-B27 27 题 + E1-E7 7 题 + S1-S6 系统锚 6 题）
  4. CI 门禁：CORE_SMOKES 条数（当前 45 条，动态）
  5. README 宣传串：动态构造「22 引擎 + 11 包 = 33 类端到端（光子 15 + 量子 7）」
     「41 题（B1-B27 + E1-E7 + S1-S7）」「CI core N 条」断言 README.md 包含；
     反向断言 README 不含已废弃错误串「光子 9 + 量子 6」（防回退）。
"""
from __future__ import annotations

import os
import re
import sys
import unittest

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

_ROOT = os.path.dirname(_LDA)  # D:/agent_LDA
README_PATH = os.path.join(_ROOT, "README.md")


class CountConsistencySmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from lda_design.design_package import (
            ENGINE_DOMAIN, ENGINE_KIND_MAP, ENGINE_KINDS, PACKAGE_KINDS,
        )
        from lda_harness.benchmarks import BENCHMARK_ORDER
        from run_ci_regression import CORE_SMOKES
        cls.engine_kinds = tuple(ENGINE_KINDS)
        cls.kind_map = dict(ENGINE_KIND_MAP)
        cls.domain = dict(ENGINE_DOMAIN)
        cls.package_kinds = tuple(PACKAGE_KINDS)
        cls.benchmark_order = tuple(BENCHMARK_ORDER)
        cls.core_smokes = tuple(CORE_SMOKES)
        with open(README_PATH, encoding="utf-8") as f:
            cls.readme = f.read()

    # ---- 1. 引擎结构 ----
    def test_engine_total_22(self):
        self.assertEqual(len(self.engine_kinds), 22,
                         f"ENGINE_KINDS 应 22 类（15 设计量 + 5 loss + 2 有源双出口），实际 {len(self.engine_kinds)}")

    def test_engine_domain_split_15_7(self):
        # 域划分以 ENGINE_DOMAIN 动态统计为准（engine_kind → 显示名 → photon/quantum）
        names = []
        for k in self.engine_kinds:
            self.assertIn(k, self.kind_map,
                          f"引擎 {k} 缺 ENGINE_KIND_MAP 映射（新增引擎漏注册）")
            names.append(self.domain[self.kind_map[k]])
        self.assertEqual(len(names), 22, "ENGINE_KINDS 全部应在 ENGINE_DOMAIN 有映射")
        n_photon = sum(1 for d in names if d == "photon")
        n_quantum = sum(1 for d in names if d == "quantum")
        self.assertEqual(n_photon, 15, f"光子引擎应 15 类（8 设计量 + 5 loss + 2 有源），实际 {n_photon}")
        self.assertEqual(n_quantum, 7, f"量子引擎应 7 类，实际 {n_quantum}")
        self.assertEqual(n_photon + n_quantum, 22)

    def test_engine_domain_no_unknown(self):
        for k in self.engine_kinds:
            self.assertIn(k, self.kind_map,
                          f"引擎 {k} 缺 ENGINE_KIND_MAP 映射（新增引擎漏注册域）")
            name = self.kind_map[k]
            self.assertIn(name, self.domain,
                          f"引擎显示名 {name} 缺 ENGINE_DOMAIN 映射（新增引擎漏注册域）")

    # ---- 2. 包结构 ----
    def test_package_kinds_11(self):
        self.assertEqual(len(self.package_kinds), 11,
                         f"PACKAGE_KINDS 应 11 类，实际 {len(self.package_kinds)}")

    def test_engine_plus_package_33(self):
        self.assertEqual(len(self.engine_kinds) + len(self.package_kinds), 33,
                         "22 引擎 + 11 包应 = 33 类端到端")

    # ---- 3. 题库 ----
    def test_benchmark_order_41(self):
        self.assertEqual(len(self.benchmark_order), 41,
                         f"BENCHMARK_ORDER 应 41 题，实际 {len(self.benchmark_order)}")

    def test_benchmark_b27_e7_s7_split(self):
        b_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"B\d+", b)]
        e_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"E\d+", b)]
        s_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"S\d+", b)]
        self.assertEqual(len(b_ids), 27, f"B 题应 27，实际 {len(b_ids)}")
        self.assertEqual(len(e_ids), 7, f"E 题应 7，实际 {len(e_ids)}")
        self.assertEqual(len(s_ids), 7, f"S 题应 7，实际 {len(s_ids)}")
        self.assertEqual(b_ids[0], "B1")
        self.assertEqual(b_ids[-1], "B27")
        self.assertEqual(e_ids, ["E1", "E2", "E3", "E4", "E5", "E6", "E7"])
        self.assertEqual(s_ids, ["S1", "S2", "S3", "S4", "S5", "S6", "S7"])

    # ---- 4. CI 门禁条数 ----
    def test_ci_core_count_matches_readme(self):
        n_core = len(self.core_smokes)
        # README 顶部当前版本行必须标注对应 CI core 条数
        m = re.search(r"CI core (\d+) 条", self.readme)
        self.assertIsNotNone(m, "README 应含 'CI core N 条' 标注")
        self.assertEqual(int(m.group(1)), n_core,
                         f"README 写 CI core {m.group(1)} 条，实际 CORE_SMOKES={n_core}")

    # ---- 5. README 宣传串一致性 ----
    def test_readme_engine_counts(self):
        self.assertIn("22 引擎 + 11 包 = 33 类端到端", self.readme)
        self.assertIn("光子 15 + 量子 7", self.readme)
        # 反向断言：废弃错误串不得回退
        self.assertNotIn("光子 9 + 量子 6", self.readme)
        self.assertNotIn("光子 9+量子 6", self.readme)

    def test_readme_benchmark_counts(self):
        self.assertIn("41 题", self.readme)
        self.assertIn("B1-B27", self.readme)
        self.assertIn("E1-E7", self.readme)
        self.assertIn("S1-S7", self.readme)

    def test_readme_version_line(self):
        self.assertIn("v0.8.10", self.readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
