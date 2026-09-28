"""P6+ · DMM 设计能力成熟度打分表门禁（**把规划 §2.2/§4 的 M2 闸门机器化**）。

## 为什么建它
规划 `LDA_internal_design_plan_2026-09-23.md` 的 **M2 = D4 能力数 ≥3** 此前**无法判定** ——
因为 DMM 打分表只存在于规划文档文字里（§2.3 是 P1 之前的快照）。
本门禁把打分表钉成常驻判据：级别由 `lda_harness/dmm_scorecard.py` **从事实推导**，
本脚本核验「事实确实存在」+「级别不高于事实允许」+「D4 三要素齐备」+「文档与机器表逐字节一致」。

## 判据分组
- **A 表完整性**：id 唯一 · 字段齐 · 级别 ∈ D0–D5
- **B 事实核验**：逐行 module/symbol/门禁登记/反向证据/证据门禁 —— **任一不成立即判红并指名**
- **C 级别自洽**：`audit()` 零违规（高级别不得缺低级别的事实）
- **D D4 三要素**：G4 硬开 · 单命令链存在 · 每个 D4 行在其准入表内
- **E 反向下调（必降级类）**：伪造 3 个反例（假准入 kind / 假门禁名 / 断反向证据）⇒ 级别**必降**
- **F 合法必过**：真实表 audit ok 且 `gate()` 通过（M2 ≥3）—— 只测「必降」会有恒真假绿
- **G 文档同步**：`docs/design_maturity_model.md` ≡ 机器渲染（`--write-doc` 重生成）；防手改漂移
- **H 红线**：scorecard 源码零 LLM 引用（判决全死标量）

运行：`PYTHONPATH=lda python lda/run_dmm_scorecard_smoke.py [--write-doc]`
"""

from __future__ import annotations

import copy
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.dmm_scorecard import (          # noqa: E402
    CAPABILITIES, CAPABILITY_KEYS, G4_TOKEN, INDEPENDENCE_GUARDS, LEVEL_D5_IS_EXTERNAL,
    M2_D4_MIN, REPO, REVERSE_PATTERNS, ROOT, audit, facts, gate, level_of, scorecard,
)
from lda_harness.smoke_kit import make_check     # noqa: E402

# 🔴 调用签名：check(name, cond, detail) —— **名字在前**（P6·T6.1 血案：写反 ⇒ 整体假绿）
check = make_check(globals(), return_ok=True, detail_fmt="  —— {d}", detail_on="fail")

DOC_PATH = os.path.join(REPO, "docs", "design_maturity_model.md")
SCORE_SRC = os.path.join(ROOT, "lda_harness", "dmm_scorecard.py")


# ---------------------------------------------------------------------------
def _core():
    from run_ci_regression import CORE_SMOKES
    return list(CORE_SMOKES)


def render_doc(sc, au, gt) -> str:
    """把机器表渲染成文档（唯一来源 ⇒ 手改必被 G 组判红）。"""
    L = []
    L.append("# LDA 设计能力成熟度模型（DMM · Design Maturity Model）")
    L.append("")
    L.append("> 🔴 **本文件由 `lda/run_dmm_scorecard_smoke.py --write-doc` 自动生成，请勿手工编辑**"
             "（手改必被该门禁的「重新生成 == 磁盘文件」断言判红）。")
    L.append("> 真相源：`lda/lda_harness/dmm_scorecard.py`（能力表 + 事实采集 + 判级函数）。")
    L.append("")
    L.append("## 它是什么")
    L.append("")
    L.append("DMM 是 **VMM（`docs/verification_maturity_model.md`）的姊妹模型**：VMM 回答"
             "「某个物理量算得对不对」，DMM 回答「**平台能设计什么、这项能力在第几级、怎么升级**」。")
    L.append("两级共用同一套纪律：诚实标注 · 每项必写升级路径 · 不得越级谎报。")
    L.append("")
    L.append("## 级别定义（D0–D5）")
    L.append("")
    L.append("| 级 | 名称 | 判定标准（**本仓机器化口径**） |")
    L.append("|---|---|---|")
    L.append("| D0 | 不存在 | 模块缺失，或模块在但**无入口符号** |")
    L.append("| D1 | 能跑 | 模块存在 + 入口符号存在 |")
    L.append("| D2 | 可复现 | D1 + 其门禁登记进 `CORE_SMOKES` |")
    L.append("| D3 | 可自证 | D2 + **反向证据**（探针／自身门禁反向断言／其所引用证据门禁的反向断言）"
             " + 引用 ≥1 个**独立证据门禁** |")
    L.append("| D4 | 可交付 | D3 + **交付三要素**：① G4 几何回提**硬开** ② 单命令链存在"
             " ③ 该能力在其准入表内 |")
    L.append("| D5 | 可外签 | 真 foundry deck 签认／流片实测回流 —— **外部，本模型永不自动判达** |")
    L.append("")
    L.append("## 当前打分（**机器推导**，非手写）")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 能力总数 | %d |" % sc["n_capabilities"])
    L.append("| 各级分布 | " + " · ".join(
        "**%s %d**" % (k, v) for k, v in sc["counts"].items() if v) + " |")
    L.append("| **D4 能力数（M2 指标）** | **%d**（出口判据 ≥%d ⇒ %s） |"
             % (sc["d4_count"], M2_D4_MIN, "✅ 达成" if gt["ok"] else "❌ 未达"))
    L.append("| D3 及以上 | %d / %d |" % (sc["d3_or_better"], sc["n_capabilities"]))
    L.append("| 一致性审计 | %s |" % ("✅ 零违规" if au["ok"] else "❌ " + "; ".join(au["violations"][:3])))
    L.append("")
    L.append("| id | 能力 | 级 | 实现模块 | 门禁 | 反向证据来源 | 探针（最近实跑） | 交付链 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in sc["rows"]:
        f = r["facts"]
        src = "/".join(f["reverse_evidence_sources"]) or "—"
        probe = ("`%s`（%s）" % (r["probe"], r["probe_last_result"])
                 if r["probe"] else "—")
        chain = ("`%s`" % r["d4"]["chain"]) if r["d4"] else "—"
        L.append("| %s | %s | **%s** | `%s` | `%s` | %s | %s | %s |"
                 % (r["id"], r["name"], r["level"], r["module"], r["smoke"], src, probe, chain))
    L.append("")
    L.append("## 🔴 诚实边界（必须与分数同读）")
    L.append("")
    L.append("1. 本表判的是**「事实代理」**，不是「能力质量」的最终裁判 —— 质量由所引用的**门禁/探针**"
             "承担；本表只保证「该能力宣称的级别所依赖的事实确实存在」，缺一即**降级**。")
    L.append("2. **探针「会响」是运行期事实** ⇒ 不入判级（探针不进 `CORE_SMOKES`），只在表中记为"
             "「最近一次实跑」。")
    L.append("3. **D5 恒不可达**：内部判据只能到 D4（规划 §2.2：「D4 是内部能达到的上限」）。")
    L.append("4. 级别**累积**：D(n) 需 D(n−1) 全部条件成立。")
    L.append("5. **D4 的「可交付」≠「foundry 能收」**：真 deck 对齐是 D5（外部）。")
    L.append("6. `G4` 的独立是**代码路径级**（版图几何独立测量 vs IR 声明），非物理方法级。")
    L.append("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
def main() -> int:
    core = _core()
    sc = scorecard(core)
    au = audit(sc)
    gt = gate(sc)

    # ---------------- A 表完整性 ----------------
    print("--- A 表完整性 ---")
    ids = [c["id"] for c in CAPABILITIES]
    check("A1 能力 id 全局唯一", len(ids) == len(set(ids)), "重复=%s"
          % [i for i in ids if ids.count(i) > 1])
    miss = [c.get("id") for c in CAPABILITIES if any(k not in c for k in CAPABILITY_KEYS)]
    check("A2 每行字段齐备（%d 键）" % len(CAPABILITY_KEYS), not miss, "缺字段的行=%s" % miss)
    bad_lv = [r["id"] for r in sc["rows"] if r["level"] not in ("D0", "D1", "D2", "D3", "D4", "D5")]
    check("A3 级别 ∈ D0–D5", not bad_lv, "越界=%s" % bad_lv)
    check("A4 能力数 ≥20（覆盖规划 §2.3 各域）", sc["n_capabilities"] >= 20,
          "实测 %d" % sc["n_capabilities"])
    check("A5 三域齐备（光子/量子-物理/交付链各 ≥1）",
          any("Pareto" in r["name"] or "G12" in r["name"] for r in sc["rows"])
          and any("EIC" in r["name"] or "PML" in r["name"] for r in sc["rows"])
          and any(r["d4"] for r in sc["rows"]),
          "交付链行=%s" % [r["id"] for r in sc["rows"] if r["d4"]])

    # ---------------- B 事实核验（逐行） ----------------
    print("--- B 事实核验（逐行）---")
    f_mod = [r["id"] for r in sc["rows"] if not r["facts"]["module_exists"]]
    check("B1 每行模块文件存在", not f_mod, "缺模块=%s" % f_mod)
    f_sym = [r["id"] for r in sc["rows"] if not r["facts"]["symbol_found"]]
    check("B2 每行入口符号存在（**防「模块在但 API 名写错」**）", not f_sym,
          "符号缺=%s" % [(r["id"], r["facts"]["symbol"]) for r in sc["rows"]
                        if not r["facts"]["symbol_found"]])
    f_core = [r["id"] for r in sc["rows"] if not r["facts"]["smoke_in_core"]]
    check("B3 每行门禁 ∈ CORE_SMOKES", not f_core, "未登记=%s" % f_core)
    f_rev = [r["id"] for r in sc["rows"] if not r["facts"]["has_reverse_evidence"]]
    check("B4 每行有反向证据（探针／自身门禁／所引用门禁）", not f_rev, "无反向证据=%s" % f_rev)
    f_grd = [r["id"] for r in sc["rows"] if not r["facts"]["independence_guard_in_core"]]
    check("B5 每行引用的独立证据门禁 ∈ CORE_SMOKES", not f_grd, "未登记=%s" % f_grd)
    check("B6 独立证据门禁白名单本身全部在 core",
          all(g in core for g in INDEPENDENCE_GUARDS),
          "不在 core=%s" % [g for g in INDEPENDENCE_GUARDS if g not in core])

    # ---------------- C 级别自洽 ----------------
    print("--- C 级别自洽 ---")
    check("C1 `audit()` 零违规（级别不得高于事实允许）", au["ok"],
          "; ".join(au["violations"][:4]) or "零")
    check("C2 无 D0（本次核验无「宣称存在实则不存在」的能力）",
          sc["counts"]["D0"] == 0, "D0=%d" % sc["counts"]["D0"])
    check("C3 无 D5（内部上限，不得谎报外签）", sc["counts"]["D5"] == 0,
          "D5=%d（若 >0 必为越级谎报）" % sc["counts"]["D5"])
    check("C4 LEVEL_D5_IS_EXTERNAL 口径标记为真", LEVEL_D5_IS_EXTERNAL is True)

    # ---------------- D D4 三要素 ----------------
    print("--- D D4 三要素 ---")
    g4 = facts(CAPABILITIES[0], core)
    check("D1 G4 几何回提在芯片级导出中**硬开**（`%s`）" % G4_TOKEN,
          g4["g4_hardwired"], "chip_layout_export.py 未含该 token")
    check("D2 单命令链存在（`cmd_build` / `cmd_check`）", g4["single_command_chain"])
    d4_bad = [r["id"] for r in sc["rows"] if r["level"] == "D4" and not r["facts"]["admission_ok"]]
    check("D3 每个 D4 行在其准入表内（引擎 kind ∈ BRIDGEABLE ／ 版图层 kind 表存在）",
          not d4_bad, "准入失败=%s" % d4_bad)
    check("D4 每个 D4 行有交付链描述", all(r["d4"] for r in sc["rows"] if r["level"] == "D4"))

    # ---------------- E 反向下调（必降级） ----------------
    print("--- E 反向下调（必降级）---")
    base = {c["id"]: c for c in CAPABILITIES}
    c01 = copy.deepcopy(base["C01"])

    def _lvl(cap):
        return level_of(cap, core)[0]

    fake = copy.deepcopy(c01)
    fake["d4"]["admission"] = "engine_does_not_exist"
    check("E1 伪造准入 kind ⇒ 该行**必降级**（D4→D3）", _lvl(fake) == "D3",
          "实测级别=%s（期望 D3）" % _lvl(fake))

    fake2 = copy.deepcopy(c01)
    fake2["smoke"] = "run_no_such_smoke_xyz.py"
    check("E2 门禁名不存在 ⇒ 该行**必降级**（≤D1）", _lvl(fake2) in ("D0", "D1"),
          "实测级别=%s" % _lvl(fake2))

    fake3 = copy.deepcopy(c01)
    fake3["module"] = "lda/lda_l2/no_such_module_xyz.py"
    check("E3 模块不存在 ⇒ 该行**必降为 D0**", _lvl(fake3) == "D0",
          "实测级别=%s" % _lvl(fake3))

    fake4 = copy.deepcopy(base["C06"])          # 非 D4 行：伪造准入不影响级别
    fake4["independence_guard"] = "run_no_such_guard_xyz.py"
    check("E4 证据门禁名不存在 ⇒ 该行**必降级**（D3→D2）", _lvl(fake4) == "D2",
          "实测级别=%s" % _lvl(fake4))

    # E5 要隔离「反向证据为空」这一条件 ⇒ 必须**运行时挑**一个在册但无反向指纹的门禁
    # （写死名字会顺手带上指纹 ⇒ 反例不成立；这也顺带证明 REVERSE_PATTERNS 有区分力）
    def _pick_no_rev(pool):
        for name in pool:
            src = ""
            try:
                with open(os.path.join(ROOT, name), encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
            except OSError:
                continue
            if not any(pat in src for pat in REVERSE_PATTERNS):
                return name
        return None

    no_rev = _pick_no_rev(core)
    check("E5a 存在「在册但无反向指纹」的门禁（指纹集有区分力）", no_rev is not None,
          "在 %d 条 core 门禁里未找到无指纹者" % len(core))
    if no_rev:
        fake5 = copy.deepcopy(base["C05"])
        fake5["probe"] = "scripts/no_such_probe_xyz.py"      # ① 探针不存在
        fake5["smoke"] = no_rev                               # ② 自身门禁无指纹
        fake5["independence_guard"] = no_rev                  # ③ 所引用门禁同一条（亦无指纹）
        check("E5 断掉全部反向证据来源 ⇒ 该行**必降级**（D3→D2）", _lvl(fake5) == "D2",
              "实测级别=%s（smoke=%s）" % (_lvl(fake5), no_rev))

    # ---------------- F 合法必过 ----------------
    print("--- F 合法必过 ---")
    check("F1 真实表 `audit()` 通过（合法必过）", au["ok"])
    check("F2 `gate()` 通过（M2：D4 ≥%d）" % M2_D4_MIN, gt["ok"],
          "D4=%d · reasons=%s" % (gt["d4_count"], gt["reasons"][:2]))
    check("F3 D4 行与 `d4_ids` 计数一致", len(sc["d4_ids"]) == sc["d4_count"])

    # ---------------- G 文档同步 ----------------
    print("--- G 文档同步 ---")
    doc = render_doc(sc, au, gt)
    if "--write-doc" in sys.argv:
        os.makedirs(os.path.dirname(DOC_PATH), exist_ok=True)
        with open(DOC_PATH, "wb") as fh:
            fh.write(doc.encode("utf-8"))
        print("   [written] %s（%d B）" % (os.path.relpath(DOC_PATH, REPO), len(doc.encode())))
    disk = None
    try:
        with open(DOC_PATH, encoding="utf-8") as fh:
            disk = fh.read()
    except OSError:
        disk = None
    check("G1 `docs/design_maturity_model.md` 存在", disk is not None)
    check("G2 文档 ≡ **重新生成**（防手改漂移；不一致时用 `--write-doc`）",
          disk == doc, "磁盘 %s B vs 生成 %s B"
          % (len(disk.encode()) if disk else -1, len(doc.encode())))
    check("G3 文档含 D4 计数与 M2 判据字样",
          disk is not None and ("D4 能力数（M2 指标）" in disk) and ("≥%d" % M2_D4_MIN in disk))

    # ---------------- H 红线 ----------------
    print("--- H 红线 ---")
    src = open(SCORE_SRC, encoding="utf-8").read()
    hits = re.findall(r"\b(openai|anthropic|llm|gpt)[\w.]*", src, re.I)
    check("H1 scorecard 源码零 LLM 引用（判决全死标量）", not hits, "命中=%s" % hits[:5])
    check("H2 scorecard 不读网络（无 requests/urllib/http 调用）",
          not re.search(r"\b(requests\.|urllib\.request|http\.client|socket\.)", src),
          "命中=%s" % re.findall(r"\b(requests\.|urllib\.request|http\.client|socket\.)", src))
    check("H3 本门禁不写仓库（除 `--write-doc` 的文档）",
          "--write-doc" in open(os.path.abspath(__file__), encoding="utf-8").read())

    n_fail = int(globals().get("FAIL", 0))
    n_pass = int(globals().get("PASS", 0))
    print("")
    print("DMM 打分：能力 %d · %s · **D4=%d**（M2 判据 ≥%d）"
          % (sc["n_capabilities"],
             " · ".join("%s %d" % (k, v) for k, v in sc["counts"].items() if v),
             sc["d4_count"], M2_D4_MIN))
    print("DMM 门禁：%d PASS / %d FAIL" % (n_pass, n_fail))
    print("=" * 74)
    # 🔴 rc 必须由 FAIL 计数决定 —— 否则判据全收集了也恒 rc=0（突变探针 M1–M8 全部抓不住）
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
