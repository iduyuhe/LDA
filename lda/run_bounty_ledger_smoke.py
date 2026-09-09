#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LDA 名誉榜台账护栏：结构合法 + 反作弊 + 实时排名。

验证：
- 交易台账表格结构合法（类型 / 锚判定 / 得分三栏受枚举约束）
- 得分与（类型, 锚判定）组合严格一致（防刷分：不能自己写 +100）
- defect/confirmed 行必须在备注引用锚 ID（如 S12 / B29），防自证式自嗨
- 累计得分 = 各行得分之和（交叉校验）
- 打印实时排名（名誉榜）

可独立运行：python lda/run_bounty_ledger_smoke.py
"""
import os
import re
import sys
import unittest

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
    for ln in lines[start + 2:]:  # 跳过表头 + 分隔行
        s = ln.strip()
        if not s.startswith("|"):
            if rows:
                break  # 表结束
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 6:
            continue
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
    if not lb:
        print("（暂无记录）")
    for rank, (who, sc, c, a, d) in enumerate(lb, 1):
        print(f"  #{rank}  {who}: {sc} 分  [语料 {c} / 对抗 {a} / 缺陷 {d}]")
    print(f"[OK] 台账 {len(rows)} 行，累计 {total} 分，结构合法、无刷分、无自证。")
    return 0


class BountyLedgerSmoke(unittest.TestCase):
    def test_ledger_integrity(self):
        with open(LEDGER, encoding="utf-8") as f:
            text = f.read()
        rows = parse_ledger(text)
        total = validate(rows)
        recomputed = sum(int(r["score"]) for r in rows)
        self.assertEqual(total, recomputed, "累计得分交叉校验失败")
        # 类型枚举受约束
        for r in rows:
            self.assertIn(r["kind"], VALID_TYPES)
        # confirmed 缺陷必挂锚
        for r in rows:
            if r["kind"] == "defect" and r["verdict"] == "confirmed":
                self.assertRegex(r["note"], r"[SB]\d+", "confirmed 缺陷必须引用锚 ID")


if __name__ == "__main__":
    rc = main()
    sys.exit(rc)
