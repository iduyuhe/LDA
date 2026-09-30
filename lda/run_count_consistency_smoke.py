"""计数一致性机器断言 smoke（v0.8.10 起 · 防计数漂移根治 · v0.8.30 加固）。

背景：v0.8.10 维护发现两类计数漂移（L1/实证锚 smoke 硬编码题数过时、
README 引擎域计数「光子 9 + 量子 6」与代码 ENGINE_DOMAIN 实际 8+7 不符）。
本 smoke 把「宣传口径 vs 代码事实」的一致性变成**机器断言**：
所有关键计数从代码动态读取，再断言 README 宣传串包含正确数字——
今后任何引擎/包/题库/CI 条数变化而文档未同步，立即 FAIL 拦截。

**v0.8.30 加固（针对真实漂移事件）**：原 `CI core N 条` 正则会在 README
历史链里的旧版本行（如「CI core 61 条」）误匹配，导致守卫**已静默失效**
（真实 62 条却报 61）。改为：**①**CI core 条数改为动态断言「README 权威段
含 `CI core {n_core} 条`」且**不含**任何与真实值冲突的旧数字；**②**版本行
必须=最新 pyproject 版本，杜绝版本线滞后。（**v0.9.1 再加固**：权威段由
「README 顶部当前版本行」**收紧为行首二级标题** `## 当前账本：…CI core N 条`——
历史链里更早出现的「当前账本：…」旧声明曾致权威段数字改了却仍在比对旧值，
即 70≠79 漂移未被当场捕获的根因；详见 `test_ci_core_count_matches_readme_top` 内注。）

断言维度（全部死标量，LLM 不进判决路径）：
  1. 引擎结构：ENGINE_KINDS 22（15 设计量 + 5 loss + 2 有源）、光子 15、量子 7
  2. 包结构：PACKAGE_KINDS 11（22 引擎 + 11 包 = 33 类端到端）
  3. 题库：BENCHMARK_ORDER 476 题（B1-B458 共 453 题 + E1-E10 10 题 + S1-S13 13 题）
  4. CI 门禁：CORE_SMOKES 条数（动态）↔ README `## 当前账本` 段 `CI core N 条` 严格一致
  5. README 宣传串：动态构造「22 引擎 + 11 包 = 33 类端到端（光子 15 + 量子 7）」
     「476 题（B1-B458 + E1-E10 + S1-S13）」；反向断言 README 不含已废弃错误串
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
CONTRIB_PATH = os.path.join(_ROOT, "CONTRIBUTING.md")


def _prose_ci_core(text: str):
    """从散文里抽取「CI core N 条」的数字（**纯函数，供正向 + 反向共用**）。

    🔴 2026-09-30（v0.9.145）实测发现：`CONTRIBUTING.md` 顶部账本块长期写
    「CI core **221** 条」而代码实际 **226**（D-133…D-148 新增 5 个征程门禁未同步），
    且**当时无任何判据覆盖**（`run_p0_count_guard_sync_smoke` 只守三分类 455/3/18）
    ⇒ 静默失真。本函数 + 下面的用例把该口径钉住。
    """
    m = re.search(r"CI core\s*\*{0,2}(\d+)\s*条", text or "")
    return int(m.group(1)) if m else None


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
        # T5.3：实证语料的权威路径（单一来源 = empirical_m6.SEED_PATH）
        from lda_harness.empirical_m6 import SEED_PATH
        cls._seed_path = SEED_PATH
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
    def test_benchmark_order_total(self):
        n_b = len([b for b in self.benchmark_order if re.fullmatch(r"B\d+", b)])
        n_e = len([b for b in self.benchmark_order if re.fullmatch(r"E\d+", b)])
        n_s = len([b for b in self.benchmark_order if re.fullmatch(r"S\d+", b)])
        self.assertEqual(len(self.benchmark_order), n_b + n_e + n_s,
                         f"BENCHMARK_ORDER 总数应 = B+E+S 分段之和，"
                         f"实际 {len(self.benchmark_order)} (B{n_b}+E{n_e}+S{n_s})")

    def test_benchmark_b30_e9_s13_split(self):
        b_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"B\d+", b)]
        e_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"E\d+", b)]
        s_ids = [b for b in self.benchmark_order
                 if re.fullmatch(r"S\d+", b)]
        # v0.9.67 新增 B33；v0.9.69/v0.9.70 启用 B31/B32（A 档有源严格锚）
        # → B 题 31→33；v0.9.79 路径 B 扩基新增 B34/B36/B37/B40/B41（末位跳 B41）→ 38；B-2 再加 B42-B51 → 48；B-3 再加 B52-B64 → 61；
        # v0.9.84 路径 B-4 扩基新增 B65-B68/B70-B71/B73-B88（缺口 B69 相移 / B72 线宽预留，无数值候选会触发棘轮）→ 83；
        # v0.9.85 B-5 加 B89-B104 → 99；v0.9.86 B-6 加 B105-B120 → 115；v0.9.87 B-7 加 B121-B136 → 131；
        # v0.9.88 B-8 加 B137-B152 → 147；v0.9.89 B-9 加 B153-B168 → 163；v0.9.90 B-10 加 B169-B184 → 179；
        # v0.9.91 B-11 加 B185-B200 → 195；v0.9.92 B-12 加 B201-B216 → 211；v0.9.93 B-13 加 B217-B232 → 227；
        # v0.9.95 B-15 加 B249-B264 → 259（B-14 加 B233-B248 → 243）；v0.9.96 B-16 加 B265-B280 → 275；
        # v0.9.97 B-17 加 B281-B296 → 291；v0.9.98 B-18 加 B297-B312 → 307；
        # v0.9.99 B-19 加 B313-B328 → 323；v0.9.100 B-20 加 B329-B344 → 339；v0.9.104 B-22 加 B361-B373 → 373；v0.9.105 B-23 加 B374-B386 → 381；v0.9.106 B-24 加 B387-B399 → 394；v0.9.107 B-25 加 B400-B412 → 407；v0.9.108 B-26 加 B413-B425 → 420；v0.9.109 B-27 加 B426-B438 → 433；v0.9.110 B-28 加 B439-B451 → 446；P6·T6.4 B-29 加 B452 → 447。
        # v0.9.111 Batch B-30（量子征程回填）加 B453-B455 → 450
        # v0.9.143 Batch B-31（量子征程再评估）加 B456-B457 → 452
    # v0.9.144 Batch B-32（几何栅格化收敛）加 B458 → 453
        self.assertEqual(len(b_ids), 453, f"B 题应 453（B1-B458，缺口 B35/B38/B39/B69/B72 预留），实际 {len(b_ids)}")
        self.assertEqual(len(e_ids), len([f"E{i}" for i in range(1, len(e_ids) + 1)]),
                         f"E 题数异常，实际 {len(e_ids)}")
        self.assertEqual(len(s_ids), 13, f"S 题应 13，实际 {len(s_ids)}")
        self.assertEqual(b_ids[0], "B1")
        self.assertEqual(max(b_ids, key=lambda x: int(x[1:])),
                         "B458", f"B 题最大编号应 B458，实际 {max(b_ids, key=lambda x: int(x[1:]))}")
        self.assertEqual(e_ids, [f"E{i}" for i in range(1, len(e_ids) + 1)],
                         f"E 题须连续编号 E1..E{len(e_ids)}，实际 {e_ids}")
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
        e_ids = [b for b in self.benchmark_order if re.fullmatch(r"E\d+", b)]
        e_last = int(e_ids[-1][1:]) if e_ids else 0
        # B 段末号**动态派生**（原硬编码 "B1-B451" 在 B452 落地时当场红 ⇒ 消除该手工
        # 同步点；真值源仍是唯一的 BENCHMARK_ORDER，判据强度不变）。
        b_ids = [b for b in self.benchmark_order if re.fullmatch(r"B\d+", b)]
        b_last = max(b_ids, key=lambda x: int(x[1:])) if b_ids else "B0"
        self.assertIn(f"{len(self.benchmark_order)} 题", self.readme)
        self.assertIn(f"B1-{b_last}", self.readme)
        self.assertIn(f"E1-E{e_last}", self.readme)
        self.assertIn("S1-S13", self.readme)

    # (a) 条数下限的**单一来源**：`empirical_m6.M6_CORPUS_MIN`（T5.3 起）。
    #     此前本 smoke 在写死数字上「保持沉默」，导致语料从 30 → 70 的扩容**无护栏**
    #     —— 若种子文件被意外截断，没有任何常驻门禁会当场红。
    #     现改为「动态真值 vs 计划下限」双判：既防截断，又不与 M6 计划线脱节。
    def test_empirical_corpus_floor(self):
        from lda_harness.empirical_m6 import M6_CORPUS_MIN
        from lda_harness.empirical_bank import EmpiricalCorpus
        n = len(EmpiricalCorpus.load(self._seed_path)._items)
        self.assertGreaterEqual(
            n, M6_CORPUS_MIN,
            f"实证语料应 ≥ {M6_CORPUS_MIN} 条（T5.3 计划下限），实际 {n}"
            f"——若为截断，请检查 lda/lda_harness/seed_empirical.json")

    # ---- 6. 版本线一致性（防滞后 / 防关联漂移）----
    def test_readme_version_matches_pyproject(self):
        self.assertTrue(self.pyproject_version, "无法读取 pyproject version")
        self.assertIn(f"v{self.pyproject_version}", self.readme_top,
                      f"README 顶行版本须 = pyproject {self.pyproject_version}")

    # ---- 7. 对外账本块的 CI core 数（v0.9.145 补：此前**无判据覆盖**）----
    def test_contributing_ci_core_matches_core_smokes(self):
        """`CONTRIBUTING.md` 顶部账本块的「CI core N 条」须 == `len(CORE_SMOKES)`。

        为什么单列：CI 成员增删是常规操作，而该处是**对外账本**（新人按它判断门禁规模）；
        README 侧早有 `test_ci_core_count_matches_readme_top` 守着，**CONTRIBUTING 侧一直裸奔**
        ⇒ v0.9.145 实测抓到它滞后 5 个（221 vs 226）。
        """
        from run_ci_regression import CORE_SMOKES
        self.assertTrue(os.path.exists(CONTRIB_PATH), "CONTRIBUTING.md 应存在")
        with open(CONTRIB_PATH, encoding="utf-8") as f:
            txt = f.read()
        got = _prose_ci_core(txt)
        self.assertIsNotNone(got, "CONTRIBUTING 顶部账本块应写明「CI core N 条」")
        want = len(CORE_SMOKES)
        self.assertEqual(
            got, want,
            f"CONTRIBUTING 写 CI core {got} 条，代码实际 {want} 条"
            f" —— 增删 CI 成员后须同步「三同步」清单：README 顶行 / `## 当前账本` 段 /"
            f" CONTRIBUTING 顶部账本块 / pyproject / CHANGELOG")
        # 反向：把计数改错 1 ⇒ 抽取器必须给出不符值（证明判据会响，非恒真）
        bad = txt.replace(f"CI core {got} 条", f"CI core {got + 1} 条", 1)
        self.assertNotEqual(_prose_ci_core(bad), want,
                            "反向用例：篡改计数后应判出不符（否则本判据恒真）")
        # 反向：缺写 ⇒ 抽取器返回 None（缺失也必须能被发现）
        self.assertIsNone(_prose_ci_core("本文件不含该口径"),
                          "反向用例：缺失「CI core N 条」时应返回 None")


if __name__ == "__main__":
    # F-18（v0.9.113 · 波次 2 · 审计：「19 个 smoke 用 unittest、其余用自研
    # check() ⇒ 两套测试范式并存」）：本文件保留标准 unittest 写测试体，
    # 但**报告与退出契约统一走 smoke_kit** —— 逐条 `  [PASS] <name>`，
    # 失败/错误仍打标准 FAIL:/ERROR: 块（含 traceback，CI 判定「失败痕迹」可命中，
    # 不会被误判 SKIP），rc 与 `unittest.main(verbosity=2)` 逐位一致。
    from lda_harness.smoke_kit import run_unittest_suite

    raise SystemExit(run_unittest_suite(CountConsistencySmoke))
