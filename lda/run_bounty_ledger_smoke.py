#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LDA 名誉榜台账护栏：结构合法 + 反作弊 + 实时排名。

验证：
- 交易台账表格结构合法（类型 / 锚判定 / 得分三栏受枚举约束）
- 得分与（类型, 锚判定）组合严格一致（防刷分：不能自己写 +100）
- defect/confirmed 行必须在备注引用锚 ID（如 S12 / B29），防自证式自嗨
- 累计得分 = 各行得分之和（交叉校验）
- 打印实时排名（名誉榜）

🔴 v0.9.114（2026-09-20 · 审计 F-07/F-18 残留项 item 1 裁决：删死码 + 堵 G1 + 补判据）
-------------------------------------------------------------------------------
① **删死码**：`BountyLedgerSmoke` 类**从未被执行**（旧 `__main__` 只跑 `main()`）。
   逐条比对后确认其 5 组断言**全部**是 `main()` / `validate()` 已覆盖的**严格子集**
   （parse → validate → total==recomputed → kind∈VALID_TYPES → note 挂锚）
   ⇒ 把它接进 unittest 只会 **+0 覆盖**，并把 F-18 刚消掉的「两套测试范式并存」
   重新固化。故整体删除，本文件回到单一范式。

② **堵 G1（真缺口）**：列数不足的行原先 `continue` **静默丢弃** —— 台账输出仍宣称
   「结构合法、无刷分、无自证」，而畸形行无声消失（实测：5 列行 `rows=0` 且不报错；
   「合法行 + 畸形行」混排时畸形行同样蒸发）⇒「结构合法」这一宣称**不可验证**。
   现改为**报错**，并给出行号与原文，杜绝「写坏即隐身」。

③ **补 11 条判据**（10 条反向 R1~R10 + 1 条「反证的对照」R0b）：把「护栏真能变红」
   固化成判据。铁律：**没被验证过的护栏不算护栏**。R7/R8 专盯 G1 本体；R0b 是
   **反证的对照** —— 证明合法合成台账必须通过，否则 `_rejects` 恒真 ⇒ R1~R10 全部假绿。

④ **堵 G2（v0.9.115 闭环 · 前一轮登记的「策略待裁」项）**：表头在而**零数据行**时
   `main()` 原判 rc=0 并称「结构合法、无刷分、无自证」—— 这三个宣称在空表下都是
   **空洞为真**（vacuously true），等于「**清空整表即漂绿**」。取证：① 台账是**入库
   资产**（`git ls-files` 确认，含 2 行机制演示行）⇒ 正常状态**永不应为空**；
   ② 台账文档**自称「防台账漂绿 / 刷分」** ⇒ 允许空表与自身承诺冲突；③ 全新克隆的
   仓库也不会遇到（演示行随仓库入库）。故现改为**判非法**（`validate` 起始处断言
   `rows` 非空），与「表头缺失」（R6）同性质：**宣称必须与内容匹配**。

可独立运行：python lda/run_bounty_ledger_smoke.py
"""
from __future__ import annotations

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "bounty_leaderboard.md")

# (类型, 锚判定) -> 期望得分；不在表内即非法组合
EXPECTED = {
    ("corpus", "landed"): 1,
    ("corpus", "not_landed"): 0,
    ("adversarial", "landed"): 2,
    ("adversarial", "not_landed"): 0,
    ("defect", "confirmed"): 10,
    ("defect", "rejected"): 0,
}
VALID_TYPES = {"corpus", "adversarial", "defect"}
ANCHOR_RE = re.compile(r"[SB]\d+")  # S12 / B29 之类锚 ID

# 列数口径（死标量）：表头 7 列 = 提交人/类型/内容摘要/锚判定/得分/备注/日期；
# 日期可省 ⇒ 数据行允许 6 列。**< 6 列即畸形**（v0.9.114 之前此处是静默 continue）。
MIN_COLS = 6


def parse_ledger(text: str):
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("|") and "提交人" in ln and "类型" in ln and "锚判定" in ln:
            start = i
            break
    if start is None:
        raise AssertionError("未找到交易台账表头（需含 提交人/类型/锚判定 列）")
    rows = []
    for no, ln in enumerate(lines[start + 2:], start=start + 3):  # 跳过表头 + 分隔行
        s = ln.strip()
        if not s.startswith("|"):
            if rows:
                break  # 表结束
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < MIN_COLS:
            # 🔴 v0.9.114 · 堵 G1：原先 `continue` 静默丢弃 ⇒ 畸形行无声消失，
            #   而输出仍声称「结构合法」。改为报错（含行号 + 原文），让坏行可见。
            raise AssertionError(
                "交易台账第 %d 行列数不足：需 ≥%d 列"
                "（提交人/类型/内容摘要/锚判定/得分/备注[+日期]），实际 %d 列 —— %r"
                % (no, MIN_COLS, len(cells), s))
        rows.append({
            "who": cells[0],
            "kind": cells[1],
            "summary": cells[2],
            "verdict": cells[3],
            "score": cells[4],
            "note": cells[5],
            "date": cells[6] if len(cells) > 6 else "",
        })
    return rows


def validate(rows):
    # 🔴 v0.9.115 · 堵 G2：台账**不得为空**。表头在而零数据行时，本护栏的三个宣称
    #   （结构合法 / 无刷分 / 无自证）都是**空洞为真**（vacuously true）⇒ 等于
    #   「清空整表即漂绿」。台账是**入库资产**（含机制演示行）⇒ 正常状态永不应为空；
    #   全新克隆的仓库亦不会遇到（演示行随仓库入库）。故零数据行 ⇒ 判非法，
    #   与「表头缺失」（R6）同性质：宣称必须与内容匹配。
    assert rows, (
        "名誉榜台账为空（表头在 · 零数据行）—— 空表下「结构合法/无刷分/无自证」"
        "三个宣称空洞为真，等于漂绿（清空整表即通过）。台账须至少保留一行"
        "（机制演示行或真实提交行）。")
    total = 0
    for r in rows:
        assert r["kind"] in VALID_TYPES, f"非法类型: {r['kind']!r} (提交人 {r['who']})"
        key = (r["kind"], r["verdict"])
        assert key in EXPECTED, f"非法(类型,锚判定)组合: {key} (提交人 {r['who']})"
        exp = EXPECTED[key]
        try:
            sc = int(r["score"])
        except ValueError:
            raise AssertionError(f"得分非整数: {r['score']!r} (提交人 {r['who']})")
        assert sc == exp, f"得分不一致: 期望 {exp} 实际 {sc} (提交人 {r['who']}, {key})"
        if r["kind"] == "defect" and r["verdict"] == "confirmed":
            assert ANCHOR_RE.search(r["note"]), (
                f"confirmed 缺陷未引用锚ID: 备注={r['note']!r} (提交人 {r['who']})——防自证，必须挂锚")
        total += sc
        r["score_int"] = sc
    return total


def compute_leaderboard(rows):
    agg = {}
    for r in rows:
        a = agg.setdefault(r["who"], {"score": 0, "corpus": 0, "adv": 0, "defect": 0})
        a["score"] += r["score_int"]
        if r["kind"] == "corpus" and r["verdict"] == "landed":
            a["corpus"] += 1
        if r["kind"] == "adversarial" and r["verdict"] == "landed":
            a["adv"] += 1
        if r["kind"] == "defect" and r["verdict"] == "confirmed":
            a["defect"] += 1
    ranked = sorted(agg.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
    return [(who, v["score"], v["corpus"], v["adv"], v["defect"]) for who, v in ranked]


def main():
    with open(LEDGER, encoding="utf-8") as f:
        text = f.read()
    rows = parse_ledger(text)
    total = validate(rows)
    recomputed = sum(int(r["score"]) for r in rows)
    assert total == recomputed, f"累计得分不一致: validate={total} sum={recomputed}"
    lb = compute_leaderboard(rows)
    print("=== LDA 名誉榜（实时排名）===")
    # 注：原「if not lb: print('（暂无记录）')」在 v0.9.115 后成为**不可达分支**
    #   —— `validate` 已保证 rows 非空 ⇒ `compute_leaderboard` 至少产出 1 个 key。
    #   按「不留死码」纪律移除（空表改为在上游 raise，不再走友好提示路径）。
    for rank, (who, sc, c, a, d) in enumerate(lb, 1):
        print(f"  #{rank}  {who}: {sc} 分  [语料 {c} / 对抗 {a} / 缺陷 {d}]")
    print(f"[OK] 台账 {len(rows)} 行，累计 {total} 分，结构合法、无刷分、无自证。")
    return 0


# 🔴 check 已归一：实现**单一定义**在 lda_harness/smoke_kit.py
#   （v0.9.113 · 波次 2 · 源自 2026-09-19 审计 F-07）。输出格式与 smoke_kit 一致。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

_PASS = 0
_FAIL = 0
check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL", indent="  ",
                   detail_fmt="  —— {d}", detail_on="fail", return_ok=True)

# 合成台账骨架（表头 7 列 + 分隔行），供反向测试拼装
_HDR = ("| 提交人 | 类型 | 内容摘要 | 锚判定 | 得分 | 备注(锚ID/引用) | 日期 |\n"
        "|---|---|---|---|---|---|---|\n")
_R_GOOD = "| 张三 | corpus | x | landed | 1 | - | 2026-09-09 |\n"


def _rejects(text: str) -> bool:
    """把合成台账喂进 parse_ledger + validate：护栏**拒绝**（raise AssertionError）则 True。"""
    try:
        validate(parse_ledger(text))
    except AssertionError:
        return True
    return False


def _selfcheck() -> int:
    """🔴 反向判据：证明本护栏**真能变红**（铁律：没被验证过的护栏不算护栏）。"""
    rc = 0

    # R0b 反证的**对照**：合法合成台账必须**通过**。
    #   缺失这条 ⇒ `_rejects` 恒真也能让 R1~R8 全绿（假绿通道），故必须先钉死。
    rc |= not check("R0b 对照：合法合成台账必须通过（防 _rejects 恒真假绿）",
                    not _rejects(_HDR + _R_GOOD))

    # R1~R6：反作弊 / 结构判据（v0.9.114 之前**从未有过**反向测试固化）
    rc |= not check("R1 刷分：defect/confirmed 写 +100 必拒",
                    _rejects(_HDR + "| 张三 | defect | 造假 | confirmed | 100 | S12 | 2026-09-09 |\n"))
    rc |= not check("R2 非法类型 kind=foo 必拒",
                    _rejects(_HDR + "| 张三 | foo | x | landed | 1 | - | 2026-09-09 |\n"))
    rc |= not check("R3 非法组合 corpus/rejected 必拒",
                    _rejects(_HDR + "| 张三 | corpus | x | rejected | 1 | - | 2026-09-09 |\n"))
    rc |= not check("R4 defect/confirmed 备注无锚ID 必拒（防自证）",
                    _rejects(_HDR + "| 张三 | defect | x | confirmed | 10 | 无锚 | 2026-09-09 |\n"))
    rc |= not check("R5 得分非整数 必拒",
                    _rejects(_HDR + "| 张三 | corpus | x | landed | 一分 | - | 2026-09-09 |\n"))
    rc |= not check("R6 表头缺失 必拒",
                    _rejects("# 标题\n\n没有台账。\n"))

    # R7/R8：🔴 G1 本体 —— 列数不足的行不得静默消失
    rc |= not check("R7 G1：5 列行必拒（v0.9.114 前被静默丢弃 ⇒ rows=0 且不报错）",
                    _rejects(_HDR + "| 张三 | defect | 造假 | confirmed | 100 |\n"))
    rc |= not check("R8 G1：合法行与畸形行混排，畸形行不得静默蒸发",
                    _rejects(_HDR + _R_GOOD + "| 李四 | defect | y | confirmed | 10 |\n"))

    # R9/R10：🔴 G2 本体 —— 空台账不得通过（三个宣称在空表下空洞为真 = 清空整表即漂绿）
    rc |= not check("R9 G2：空台账（仅表头 · 零数据行）必拒（v0.9.115 前判 rc=0 且称「结构合法」）",
                    _rejects(_HDR))
    rc |= not check("R10 G2：表头后仅空行同样判空表必拒",
                    _rejects(_HDR + "\n"))

    return rc


if __name__ == "__main__":
    _rc = _selfcheck()
    try:
        main()  # 正向：校验真台账 + 打印实时排名
    except AssertionError as exc:
        check("R0 正向：真台账必须结构合法（bounty_leaderboard.md）", False, str(exc))
        _rc = 1
    print("-" * 74)
    print("汇总：%d PASS / %d FAIL / 共 %d 项" % (_PASS, _FAIL, _PASS + _FAIL))
    if _rc:
        print("FAIL — 台账护栏或反作弊判据失效，请按上方 FAIL 项修复")
    raise SystemExit(int(_rc or (_FAIL > 0)))
