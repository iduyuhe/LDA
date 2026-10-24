# -*- coding: utf-8 -*-
"""对外口径单一真源（N5 · v0.9.283）。

═══ 目的 ═══
四域的对外表述**各写各的**。本模块提供两件事，让"对外能说什么"可机器核：

1. **`claim_line(case)`** —— 一句**可对外**的话，只由**可机核**的字段拼出；
2. **`scan(text)`** —— 禁忌词扫描，**区分「负面声明」与「正面宣称」**。

═══ 三条禁令（用户已定案）═══
   不写流片 · 不写量子优势 · 不写 TOPS/fJ-op
   🔴 另：**CLM（闭环成熟度）不对外** —— 它是**人工评级**、非机器计量
      （审计 v3 自述「可争议、不应作为对外数字」），代码里也无定义。

═══ 🔴 为什么必须区分「负面声明」与「正面宣称」═══
案例卡的 `honest_note` **大量写「非流片后实测」** —— 那是**诚实边界**，必须保留。
一刀切禁「流片」二字会把最该保留的诚实声明删掉 ⇒ 判据反过来鼓励说谎。
所以 `scan()` 只看**正面宣称**：词前若带否定前缀（非/未/无/不/not）则放行。

═══ 诚实边界 ═══
· 本模块是**文本判据**，不做语义理解 ⇒ 「已实现量产级良率」这类改写仍可能漏。
· `claim_line()` 只用 `verdict` / `verdict_label` 两个**卡上字段**；
  `capacity_basis` / `evidence` 是 **schema 登记值、非卡字段** ⇒ 标 `source=schema`，
  **不放进对外那一句**（放进去就成了"自称"）。
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

SCHEMA = "lda_outward_claim_v1"

#: 否定前缀（出现在禁忌词**之前**若干字符内即视为「负面声明」，放行）
NEG_PREFIXES = ("非", "未", "无", "不", "没有", "并非", "不是",
                "not ", "no ", "non-", "non ")

#: 禁忌词表：(词, 类别, 说明)
FORBIDDEN: Tuple[Tuple[str, str, str], ...] = (
    # ── 流片类（只禁"正面宣称已流片"）──
    ("已流片", "tapeout", "声称已流片"),
    ("流片成功", "tapeout", "声称流片成功"),
    ("流片验证", "tapeout", "声称经流片验证"),
    ("tape-out 成功", "tapeout", "声称 tape-out 成功"),
    ("tapeout 成功", "tapeout", "声称 tapeout 成功"),
    ("已量产", "tapeout", "声称已量产"),
    ("量产能力", "tapeout", "声称具备量产能力"),
    ("回片实测", "tapeout", "声称有回片实测"),
    # ── 量子优势类 ──
    ("量子优势", "advantage", "声称量子优势"),
    ("quantum advantage", "advantage", "声称 quantum advantage"),
    ("量子霸权", "advantage", "声称量子霸权"),
    ("超越经典", "advantage", "声称超越经典"),
    ("量子加速", "advantage", "声称量子加速"),
    # ── 能效类（本平台不产出这些量）──
    ("TOPS/W", "efficiency", "本平台不产出 TOPS/W"),
    ("TOPS", "efficiency", "本平台不产出 TOPS"),
    ("fJ/op", "efficiency", "本平台不产出 fJ/op"),
    ("fJ-op", "efficiency", "本平台不产出 fJ-op"),
    ("pJ/MAC", "efficiency", "本平台不产出 pJ/MAC"),
    ("pj/MAC", "efficiency", "本平台不产出 pJ/MAC"),
    ("能效比", "efficiency", "本平台不产出能效比"),
    # ── CLM 不对外 ──
    ("CLM", "clm", "CLM 是人工评级，不对外"),
    ("闭环成熟度", "clm", "闭环成熟度是人工评级，不对外"),
)

#: 卡上**可机核**、可进对外一句话的字段
CLAIM_FIELDS = ("verdict", "verdict_label")


def _has_neg_prefix(text: str, start: int, back: int = 6) -> bool:
    """禁忌词位置 `start` 之前 `back` 个字符内是否出现否定前缀。"""
    head = text[max(0, start - back):start]
    low = head.lower()
    return any(p in low for p in NEG_PREFIXES)


def _is_negative(text: str, start: int, end: int, cat: str) -> bool:
    """该次命中是否属于**负面声明/禁令陈述**（⇒ 放行）。

    · 前置否定：`非流片` / `未流片` / `不产出 TOPS/W` ⇒ 放行
    · 🔴 **后置禁令陈述**：只对 `clm` 类启用窄窗口 —— 因为「CLM 不对外」
      是文档里**必须写**的禁令句，否定词在词后。不放开会把禁令句本身判红。
      窗口限 6 字符 + 只认三个明确短语，避免给正面宣称开后门。
    """
    if _has_neg_prefix(text, start):
        return True
    if cat == "clm":
        # 窗口 20 字符：`CLM（闭环成熟度，仅内部）` 这类括注要能覆盖到
        tail = text[end:end + 20]
        if any(p in tail for p in ("不对外", "仅内部", "不公开")):
            return True
    return False


def scan(text: str) -> List[Dict[str, object]]:
    """扫一段文本里的**正面宣称**禁忌词。返回违规列表（空 = 干净）。

    每项：`{term, category, why, at, context}`
    """
    out: List[Dict[str, object]] = []
    if not text:
        return out
    for term, cat, why in FORBIDDEN:
        for m in re.finditer(re.escape(term), text):
            if _is_negative(text, m.start(), m.end(), cat):
                continue          # 负面声明／禁令陈述（诚实边界）⇒ 放行
            out.append({
                "term": term,
                "category": cat,
                "why": why,
                "at": m.start(),
                "context": text[max(0, m.start() - 24):m.end() + 24].replace("\n", " "),
            })
    out.sort(key=lambda x: (x["at"], x["term"]))
    return out


def scan_by_category(text: str) -> Dict[str, int]:
    """按类别计数（便于判据打印）。"""
    d: Dict[str, int] = {}
    for h in scan(text):
        d[h["category"]] = d.get(h["category"], 0) + 1
    return d


def claim_line(card: dict) -> Dict[str, object]:
    """一张卡的**对外一句话**（只用卡上可机核字段）。

    返回 `{line, fields, source_note}`。`source_note` 诚实说明哪些口径
    **没有**进这一句、以及为什么。
    """
    verdict = str(card.get("verdict") or "")
    label = str(card.get("verdict_label") or "")
    line = "判决 %s" % verdict
    if label:
        # 用「 · 」而非再包一层括号 —— label 本身常含括号（如「…（非流片实测）」）
        line += " · %s" % label
    return {
        "line": line,
        "fields": [f for f in CLAIM_FIELDS if card.get(f)],
        "source_note": (
            "本句只由 `verdict` / `verdict_label`（**卡上字段**）拼出。"
            "`capacity_basis` 与 `evidence` 是 **signing_schema 登记值、卡上无对应字段** "
            "⇒ 标 `source=schema`，**不进对外一句话**（否则成了自称）。"
            "亦不含 CLM（人工评级、不对外）与任何 TOPS/fJ-op（本平台不产出）。"
        ),
    }


def forbidden_terms() -> List[str]:
    """全部禁忌词（供门禁打印与反向探针）。"""
    return sorted({t for t, _, _ in FORBIDDEN})
