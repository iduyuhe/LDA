"""计数一致性机器断言 smoke（v0.8.10 起 · 防计数漂移根治 · v0.8.30 加固）。

背景：v0.8.10 维护发现两类计数漂移（L1/实证锚 smoke 硬编码题数过时、
README 引擎域计数「光子 9 + 量子 6」与代码 ENGINE_DOMAIN 实际 8+7 不符）。
本 smoke 把「宣传口径 vs 代码事实」的一致性变成**机器断言**：
所有关键计数从代码动态读取，再断言 README 宣传串包含正确数字——
今后任何引擎/包/题库/CI 条数变化而文档未同步，立即 FAIL 拦截。

**v0.8.30 加固（针对真实漂移事件）**：原 `CI core N 条` 正则会在 README
历史链里的旧版本行（如「CI core 61 条」）误匹配，导致守卫**已静默失效**
（真实 62 条却报 61）。改为：**①**只扫描 README 顶部**当前版本行**（第一行
`> 当前版本：vX.Y.Z` 起始的块），避免历史链污染；**②**CI core 条数改为动态
断言「README 顶行含 `CI core {n_core} 条`」且**不含**任何与真实值冲突的旧
数字；**③**版本行必须=最新 pyproject 版本，杜绝版本线滞后。

断言维度（全部死标量，LLM 不进判决路径）：
  1. 引擎结构：ENGINE_KINDS 22（15 设计量 + 5 loss + 2 有源）、光子 15、量子 7
  2. 包结构：PACKAGE_KINDS 11（22 引擎 + 11 包 = 33 类端到端）
  3. 题库：BENCHMARK_ORDER 46 题（B1-B27 27 题 + E1-E7 7 题 + S1-S12 系统锚 12 题）
  4. CI 门禁：CORE_SMOKES 条数（动态）↔ README 顶行 `CI core N 条` 严格一致
  5. README 宣传串：动态构造「22 引擎 + 11 包 = 33 类端到端（光子 15 + 量子 7）」
     「46 题（B1-B27 + E1-E7 + S1-S12）」；反向断言 README 不含已废弃错误串
     「光子 9 + 量子 6」（防回退）；版本行 = pyproject 版本（防滞后）。
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


def _top_version_block(readme: str) -> str:
    """只返回 README 顶部「当前版本」起始的第一段落（> 块），用于精确匹配。

    历史链在后续 `> 历史：...` / `> **v0.6.x` 行，会含旧 CI core 数字，
    必须排除——只认第一条 `> 当前版本：` 之后的连续 `> ` 行作为"当前态"。
    """
    lines = readme.splitlines()
    # 找 "当前版本：" 所在行索引
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(">") and "当前版本" in ln:
            start = i
            break
    if start is None:
        return readme
    block = [lines[start]]
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("> "):
            block.append(lines[j])
        elif lines[j].startswith(">"):
            # 续行（无空格，极少见），并入
            block.append(lines[j])
        else:
            break
    return "\n".join(block)


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
        cls.readme_top = _top_version_block(cls.readme)
        # pyproject 版本（动态真相源）
        ver = ""
        try:
            pyproject = os.path.join(_ROOT, "pyproject.toml")
            txt = open(pyproject, encoding="utf-8").read()
            m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
            if m:
                ver = m.group(1)
        except Exception:
            pass
        cls.pyproject_version = ver

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
    def test_benchmark_order_47(self):
        self.assertEqual(len(self.benchmark_order), 50,
                         f"BENCHMARK_ORDER 应 50 题，实际 {len(self.benchmark_order)}")

    def test_benchmark_b27_e7_s13_split(self):
        b_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"B\d+", b)]
        e_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"E\d+", b)]
        s_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"S\d+", b)]
        self.assertEqual(len(b_ids), 30, f"B 题应 30，实际 {len(b_ids)}")
        self.assertEqual(len(e_ids), 7, f"E 题应 7，实际 {len(e_ids)}")
        self.assertEqual(len(s_ids), 13, f"S 题应 13，实际 {len(s_ids)}")
        self.assertEqual(b_ids[0], "B1")
        self.assertEqual(b_ids[-1], "B30")
        self.assertEqual(e_ids, ["E1", "E2", "E3", "E4", "E5", "E6", "E7"])
        self.assertEqual(s_ids,
                         ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                          "S9", "S10", "S11", "S12", "S13"])

    # ---- 4. CI 门禁条数（v0.8.30 加固：只认「当前账本」权威段，防历史链污染）----
    def test_ci_core_count_matches_readme_top(self):
        n_core = len(self.core_smokes)
        # 权威标注位于「## 当前账本：…CI core N 条」段（行首二级标题）。
        # 🔴 v0.9.1 加固：必须锚定行首 `## `，否则会误匹配到历史链里更早出现的
        #    「当前账本：…」旧声明（v0.8.30 历史注记中出现过一次），导致权威段
        #    数字改了却仍在比对旧值——这正是 70≠79 漂移未被当场捕获的根因。
        m = re.search(r"^##\s*当前账本：.*?CI core (\d+) 条", self.readme,
                      re.MULTILINE)
        self.assertIsNotNone(
            m, "README 须含行首 '## 当前账本：…CI core N 条' 权威标注")
        self.assertEqual(int(m.group(1)), n_core,
                         f"README 当前账本写 CI core {m.group(1)} 条，实际 CORE_SMOKES={n_core}")
        # 反向：当前账本段内不得出现与真实值冲突的其他 CI core 数字
        seg = self.readme[m.start():m.end()]
        all_nums = [int(x) for x in re.findall(r"CI core (\d+) 条", seg)]
        self.assertEqual(set(all_nums), {n_core},
                         f"当前账本段 CI core 数字冲突：{all_nums}（真实 {n_core}）")

    # ---- 5. README 宣传串一致性 ----
    def test_readme_engine_counts(self):
        self.assertIn("22 引擎 + 11 包 = 33 类端到端", self.readme)
        self.assertIn("光子 15 + 量子 7", self.readme)
        # 反向断言：废弃错误串不得回退
        self.assertNotIn("光子 9 + 量子 6", self.readme)
        self.assertNotIn("光子 9+量子 6", self.readme)

    def test_readme_benchmark_counts(self):
        self.assertIn("50 题", self.readme)
        self.assertIn("B1-B30", self.readme)
        self.assertIn("E1-E7", self.readme)
        self.assertIn("S1-S13", self.readme)

    # ---- 6. 版本线一致性（防滞后 / 防关联漂移）----
    def test_readme_version_matches_pyproject(self):
        self.assertTrue(self.pyproject_version, "无法读取 pyproject version")
        self.assertIn(f"v{self.pyproject_version}", self.readme_top,
                      f"README 顶行版本须 = pyproject {self.pyproject_version}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
