# -*- coding: utf-8 -*-
"""P0-2 计数护栏同步纪律·机器守护（v0.9.79 · 固化必查项）。

背景（同类「标签≠行为 / 计数一致性」血案）：加 `degraded_ordinal` / 严格独立锚只改
`BENCHMARK_DEFS`（登记 `candidate` + `candidate_status`），三分类（严格 / 降级 / 自证桩）
**逻辑自动跟随**；但下列四处**含硬编码数字**的陈述必须随 README 同步，否则会静默失真——
历史曾因 B31/B32 落地未同步致 `run_three_class_consistency_smoke` 红 4+1 条、v0.9.74 计数护栏欠账。

本 smoke 把「**任何加 degraded_ordinal/严格锚的 PR，必须 grep 全仓同步硬编码计数护栏**」
这一人工纪律变成**机器断言**：动态推导三分类真值，再 grep 四处护栏表面，凡数字与真值不符
（或数字被删）立即 FAIL 拦截，且带反向测试证明会响（非假绿）。

🔴 覆盖范围（与既有护栏不冲突，互为补充）：
  - README 当前账本「验证三分类（...）：严格独立 N 道 · 降级量级参考 M 道 · 自证桩 K 道」
    （亦由 run_three_class_consistency_smoke C2 守护）
  - ledger smoke 文档串（run_webui_verification_ledger_smoke.py 模块 docstring）
  - CONTRIBUTING.md 顶部账本块
  - 三分类和 == 锚总数（84）不变量
  注：引擎/包/题库/CI core 条数由 run_count_consistency_smoke 守护，本 smoke 不重复。

动态真值源：BENCHMARK_DEFS + BENCHMARK_CANDIDATES，判序「先 degraded_ordinal、再查登记表、否则自证桩」
（与 routes.py / three_class smoke / ledger smoke 同源）。
运行：python run_p0_count_guard_sync_smoke.py
"""
from __future__ import annotations

import os
import re
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)  # D:/agent_LDA
README = os.path.join(_ROOT, "README.md")
CONTRIB = os.path.join(_ROOT, "CONTRIBUTING.md")
LEDGER_DOC = os.path.join(_HERE, "run_webui_verification_ledger_smoke.py")


def _derive_true_tiers():
    """与 routes.py / three_class smoke / ledger smoke 同源判序推导三分类真值。"""
    sys.path.insert(0, _HERE)
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness.verification_adapters import BENCHMARK_CANDIDATES
    strict = deg = stub = 0
    for _bid, _d in BENCHMARK_DEFS.items():
        if _d.get("candidate_status") == "degraded_ordinal":
            deg += 1
        elif _d.get("candidate") and _d["candidate"] in BENCHMARK_CANDIDATES:
            strict += 1
        else:
            stub += 1
    return strict, deg, stub, len(BENCHMARK_DEFS)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as _fh:
        return _fh.read()


def _match_triple(content: str, pattern: str):
    """在 content 中按 pattern（含 3 个捕获组）取三分类三元组；未匹配返回 None。"""
    m = re.search(pattern, content, re.S)
    if not m:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except (ValueError, IndexError):
        return None


# 三处「严格/降级/自证桩」硬编码陈述的正则（允许不同分隔与包装）
_PAT_README = (r"验证三分类（[^）]*）\s*：\s*严格独立\s*(\d+)\s*道.*?"
               r"降级量级参考\s*(\d+)\s*道.*?自证桩\s*(\d+)\s*道")
_PAT_SLASH = r"严格独立\s*(\d+)\s*/\s*降级\s*(\d+).*?自证桩\s*(\d+)"


class P0CountGuardSyncSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.true = _derive_true_tiers()  # (strict, deg, stub, total)
        cls.strict, cls.deg, cls.stub, cls.total = cls.true

    def test_true_tiers_nonzero(self):
        s, d, st, t = self.true
        self.assertGreater(t, 0)
        self.assertGreaterEqual(s, 0)
        self.assertGreaterEqual(d, 0)
        self.assertGreaterEqual(st, 0)
        self.assertEqual(s + d + st, t, "三分类和必须等于锚总数")

    def test_readme_three_class_matches_truth(self):
        txt = _read(README)
        triple = _match_triple(txt, _PAT_README)
        self.assertIsNotNone(triple, "README 当前账本须含三分类陈述（验证三分类 …）")
        self.assertEqual(triple, (self.strict, self.deg, self.stub),
                         f"README 三分类 {triple} ≠ 动态真值 {self.true[:3]}（护栏失同步）")

    def test_ledger_smoke_docstring_matches_truth(self):
        txt = _read(LEDGER_DOC)
        triple = _match_triple(txt, _PAT_SLASH)
        self.assertIsNotNone(triple, "ledger smoke docstring 须含三分类数字（严格独立 N / 降级 M / 自证桩 K）")
        self.assertEqual(triple, (self.strict, self.deg, self.stub),
                         f"ledger smoke docstring 三分类 {triple} ≠ 动态真值 {self.true[:3]}（P0-2 失同步）")

    def test_contributing_top_block_matches_truth(self):
        txt = _read(CONTRIB)
        triple = _match_triple(txt, _PAT_SLASH)
        self.assertIsNotNone(triple, "CONTRIBUTING.md 顶部账本块须含三分类数字")
        self.assertEqual(triple, (self.strict, self.deg, self.stub),
                         f"CONTRIBUTING 三分类 {triple} ≠ 动态真值 {self.true[:3]}（P0-2 失同步）")

    def test_degraded_explicitly_three(self):
        """P0-2 锚点：B21 诚实升 degraded_ordinal 后，降级量级参考必须 = 3（E9 + E10 + B21）。"""
        self.assertEqual(self.deg, 3,
                         f"降级量级参考应为 3（E9+E10+B21），实际 {self.deg}（B21 未同步？）")

    def test_reverse_tamper_is_caught(self):
        """反向可证伪：篡改 CONTRIBUTING 数字 ⇒ 比对必须失配（护栏真会响，非假绿）。"""
        txt = _read(CONTRIB)
        polluted = txt.replace(f"严格独立 {self.strict} / 降级 {self.deg}",
                               f"严格独立 99 / 降级 {self.deg}", 1)
        triple = _match_triple(polluted, _PAT_SLASH)
        # 篡改后的三元组不得等于真值（否则护栏漏报）
        self.assertNotEqual(triple, (self.strict, self.deg, self.stub),
                            "护栏未对 CONTRIBUTING 数字篡改响应（假绿）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
