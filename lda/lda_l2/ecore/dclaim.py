# -*- coding: utf-8 -*-
"""MEM1 / MEM1.1 · 对外物料**声明门禁**（`dclaim`）。

═══════════════════════════════════════════════════════════════════════════════
唯一职责：把「对外物料只写 *设计期闭式核对·非流片实测*」从口号变成机器门禁。
───────────────────────────────────────────────────────────────────────────────
四道检查（缺一不可，前 3 道由 MEM1 三轮探针实证，第 4 道由 MEM1.1 三轮探针实证）：
  ① **必需声明**：物料必须逐字含 `设计期闭式核对·非流片实测` 或 `设计期签核·非流片实测`；
  ② **剥离后禁语**：先剥离 WHITE / NEGATION 短语再扫禁用词 —— 否则标准声明里的
     「非流片实测」会被子串误伤；
  ③ **数字通式回算**：TB/s 必须能由公开 DQ × 窗口内速率复算 —— **不列白名单**
     （4.096 = 4096×8GT/s 是合法值，白名单会误伤）；
  ④ MEM1.1 增补三项：
     · K6 数字正则含**整数**写法（`4TB/s` 不再绕过）；
     · K7 比值 claim **语境敏感**：「位宽两倍」放行，「带宽两倍」判红；
     · K5 带宽↔UI **跨项同源**：4.000 TB/s 隐含 7.8125 GT/s ⇒ UI 必须 128 ps，
       不能与 125 ps 各自过白名单（4.096 TB/s + 125 ps 是合法特例）。

🔴 禁语一律连否定式也禁（"复现不了"同样不进对外物料）：截图传播会丢上下文。
   唯一豁免是 WHITE / NEGATION 短语本身（剥离后再判）。

消费者：`scripts/build_mem1_material.py` 在写盘前调用本模块，不合规即 `raise`
（fail-closed）。本模块**不**用于门禁自检造消费者（reachability 的 `run_*`
不算产品链下游）。

边界：纯文本规则 + stdlib + 同层 `memif`；LLM 不进判决路径；不产任何新断言；
只读、不写盘。
"""
from __future__ import annotations

import io
import os
import re

from .memif import bw_closed, bw_is_derivable, public_derived, ui_consistent

__all__ = [
    "WHITE_STATEMENTS", "BANNED_TOKENS", "TBPS_RE", "UNIT_RE", "RATIO_RE",
    "check_claim", "check_material_file", "self_check",
]

WHITE_STATEMENTS = (
    "设计期闭式核对·非流片实测",
    "设计期签核·非流片实测",
)

# 🔴 否定语境豁免：物料尾部的「边界：非流片实测」是标准声明本身，含
#    "流片实测" 子串；不做豁免会把唯一合规文案判红。
NEGATION_EXEMPT = ("非流片实测", "不做流片实测", "未经流片实测")

BANNED_TOKENS = (
    "复现", "验证了", "已达到", "达到", "超越", "赶超", "量产",
    "流片实测", "签核通过", "对标", "等效于", "达到 HBM 水平",
)

# K6：整数写法必须纳入回算（旧正则只认 N.NNN，4TB/s 直接绕过）
TBPS_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*TB/s")
UNIT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(TB/s|GB/s|ps|ms|倍)")
# K7：只在「带宽/速率」语境下抓倍数 claim，避免误伤「位宽是两倍」真结论
RATIO_RE = re.compile(
    r"(带宽|速率)[^。；;，,<\n]{0,28}?([0-9]+(?:\.[0-9]+)?\s*倍|两倍|2倍)")

_ACTUAL_RATIO = bw_closed(4096, 7.8125) / bw_closed(2048, 8.0)  # 1.953125


def _strip_white(text: str) -> str:
    out = text
    for w in WHITE_STATEMENTS + NEGATION_EXEMPT:
        out = out.replace(w, "")
    return out


def _plain(text: str) -> str:
    """去 HTML 标签，避免标签插在「带宽」与倍数之间造成语境漏判。"""
    return re.sub(r"<[^>]+>", " ", text)


def _clauses(text: str) -> list:
    """按 HTML 表格行 / 句读切分：跨项同源逐 clause 判定。"""
    raw = re.split(r"</tr>|<tr[^>]*>|<p>|</p>|[。；;\n]", text, flags=re.I)
    return [c for c in (_plain(p).strip() for p in raw) if c]


def _ratio_bad(text: str) -> list:
    """带宽/速率倍数 claim 是否与实际代际比值一致（K7）。"""
    bad = []
    for clause in _clauses(text):
        for hit in RATIO_RE.finditer(clause):
            tok = hit.group(2)
            nums = re.findall(r"[0-9]+(?:\.[0-9]+)?", tok)
            claimed = float(nums[0]) if nums else 2.0
            if abs(claimed - _ACTUAL_RATIO) > 1e-6:
                bad.append(tok.strip())
    return sorted(set(bad))


def _number_bad(text: str) -> list:
    """带单位数字的回算：TB/s 走通式，其余走公开工作点投影 + 跨项同源。"""
    derived = public_derived()
    bad = set()
    for clause in _clauses(text):
        nums = UNIT_RE.findall(clause)
        tbs = [float(v) for v, u in nums if u == "TB/s"]
        pss = [float(v) for v, u in nums if u == "ps"]
        for v, u in nums:
            x = float(v)
            if u == "TB/s":
                if not bw_is_derivable(x):
                    bad.add(v)
            elif u == "GB/s":
                if not any(abs(x - y) <= 1e-6 for y in derived["gb_s"]):
                    bad.add(v)
            elif u == "ms":
                if not any(abs(x - y) <= 1e-6 for y in derived["ms"]):
                    bad.add(v)
            elif u == "ps":
                # 单 TB/s + 单 UI 的 clause 做跨项同源；多值 clause 走公开集合
                if len(tbs) == 1 and len(pss) == 1:
                    if not ui_consistent(tbs[0], x):
                        bad.add(v)
                elif not any(abs(x - y) <= 1e-6 for y in derived["ps"]):
                    bad.add(v)
    return sorted(bad)


def check_claim(text: str) -> dict:
    """对一段对外物料正文做声明合规判决（只读；返回逐项证据）。

    返回 `ok` / `hits` / `has_white` / `numbers` / `bad_numbers` / `bad_ratio` /
    `verdict`。`verdict` 是二态文本门；三态由 `memif` 负责。
    """
    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "verdict": "FAIL", "hits": [], "has_white": False,
                "numbers": [], "bad_numbers": [], "bad_ratio": [],
                "reason": "空文本"}

    has_white = any(w in text for w in WHITE_STATEMENTS)
    stripped = _strip_white(text)
    hits = sorted({w for w in BANNED_TOKENS if w in stripped})

    numbers = TBPS_RE.findall(text)
    bad_numbers = _number_bad(text)
    bad_ratio = _ratio_bad(text)

    ok = has_white and not hits and not bad_numbers and not bad_ratio
    return {
        "ok": bool(ok), "verdict": "PASS" if ok else "FAIL",
        "has_white": bool(has_white), "hits": hits,
        "numbers": numbers, "bad_numbers": bad_numbers, "bad_ratio": bad_ratio,
        "claimable": False, "in_blocking": False,
        "boundary": "设计期闭式核对·非流片实测；文本门禁，不产新断言",
    }


def check_material_file(path: str) -> dict:
    """读物料文件并判决（文件不存在 / 读失败 ⇒ FAIL，fail-closed）。"""
    try:
        with io.open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeError) as exc:
        return {"ok": False, "verdict": "FAIL", "hits": [], "has_white": False,
                "numbers": [], "bad_numbers": [], "bad_ratio": [],
                "reason": "读失败: %s" % exc, "path": os.path.basename(str(path))}
    res = check_claim(text)
    res["path"] = os.path.basename(str(path))
    return res


def self_check() -> tuple:
    """自检：正样板必须过，6 类反例必须红（含三次误伤回归）。"""
    good = ("设计期闭式核对·非流片实测：按公开参数计算，"
            "4096 DQ × 7.8125 GT/s ÷ 8 = 4.000 TB/s；"
            "核对仅验证量级自洽，不构成设计能力或性能结论。")
    bad_claim = "我们平台复现了华为 HBM，达到 4TB/s，已完成流片实测签核。"
    bad_number = "设计期闭式核对·非流片实测：带宽 999.000 TB/s。"
    bad_int = "设计期闭式核对·非流片实测：带宽 9TB/s。"              # K6
    bad_ui = good.replace("4.000 TB/s；", "4.000 TB/s，UI=125 ps；")  # K5（同 clause 才做跨项）
    bad_ratio = good + " 带宽是 HBM4 标准的两倍。"                    # K7
    legal_4096 = "设计期签核·非流片实测：4096 DQ × 8 GT/s ÷ 8 = 4.096 TB/s。"
    no_white = "4096 DQ × 7.8125 GT/s ÷ 8 = 4.000 TB/s。"
    neg_tail = good + " 边界：非流片实测；不构成性能结论。"
    good_width = good + " 位宽是 HBM4 标准的两倍。"                   # K7 正例
    good_ui = good + " UI=128 ps；每通道 62.5 GB/s；80 ms。"          # K5 正例

    g = check_claim(good)
    b1 = check_claim(bad_claim)
    b2 = check_claim(bad_number)
    b3 = check_claim(no_white)
    g2 = check_claim(legal_4096)
    g3 = check_claim(neg_tail)
    b4 = check_claim(bad_int)
    b5 = check_claim(bad_ui)
    b6 = check_claim(bad_ratio)
    g4 = check_claim(good_width)
    g5 = check_claim(good_ui)

    ok = (g["ok"] and g2["ok"] and g3["ok"] and g4["ok"] and g5["ok"]
          and not b1["ok"] and "复现" in b1["hits"]
          and not b2["ok"] and "999.000" in b2["bad_numbers"]
          and not b3["ok"] and not b3["has_white"]
          and not b4["ok"] and "9" in b4["bad_numbers"]
          and not b5["ok"] and "125" in b5["bad_numbers"]
          and not b6["ok"] and b6["bad_ratio"]
          and abs(_ACTUAL_RATIO - 1.953125) <= 1e-12)
    return bool(ok), "正例=%s/%s/%s/%s/%s 反例=%s" % (
        g["verdict"], g2["verdict"], g3["verdict"], g4["verdict"], g5["verdict"],
        "/".join(x["verdict"] for x in (b1, b2, b3, b4, b5, b6)))
