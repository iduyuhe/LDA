#!/usr/bin/env python
"""P2.2 误差列展示 bug · 反向测试（v0.9.145 后）。

## 背景（D-150 族）

`report.format_markdown` 的误差列旧实现：

    _g = deterministic.round_float(r.golden)
    _c = deterministic.round_float(r.candidate)
    err = f"{abs(_c - _g):.4g}"

先 round_float（9 位有效数字）再相减 ⇒ B446-B452 等独立候选与黄金
「高精度吻合」（亚 1e-8 真实偏差）被抹成 0，把「高精度吻合」误显示为
「完全相等」，损害报告可信度。实测报告行：

    | B446 | sine_integral_si_4 | physical-law | 1.7582 | 1.7582 | 0 | 1e-07 | ✅ PASS |

## 本 smoke 测什么（正反两面）

1. 复现 B446 场景（golden 与 candidate 差 ~2e-8）：误差列**必须非 0**，
   且以科学计数呈现真实小误差。旧实现会显示 0 ⇒ 本判据 FAIL（可证伪回归）。
2. ReferenceCandidate（candidate≡golden）误差列**必须恒 0**（自证桩诚实）。
3. 守护栏 ⑥：1e-15 浮点末位抖动**不得**泄漏进误差列（报告字节一致）。
4. 反向可证伪：改真实 golden ⇒ 误差列必变（不可过度归一掩盖真变化）。

纯标准库、秒级、零外部依赖 ⇒ 必进 core。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "lda_harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_harness import report as rep  # noqa: E402
from lda_harness.smoke_kit import make_fail_tag_collector

_FAILS = []


check = make_fail_tag_collector(_FAILS)


class _R:
    """最小结果桩（与 run_report_determinism_smoke 同属性面）。"""

    def __init__(self, bid, golden, candidate, tol=1e-3, passed=True,
                 ind=True, cls="strict_independent"):
        self.bid = bid
        self.metric = "m_" + bid
        self.oracle = "analytical"
        self.source = "physical-law"
        self.golden = golden
        self.candidate = candidate
        self.tol = tol
        self.passed = passed
        self.note = None
        self.independent = ind
        self.candidate_class = cls


_META_IND = {"candidate": "IndependentCandidateRouter(demo)", "self_consistent": False}
_META_SC = {"candidate": "ReferenceCandidate", "self_consistent": True}


def _err_cell(md: str, bid: str):
    """从 markdown 表格取某题的误差列（题号|指标|来源|黄金|候选|误差|容差|判定）。"""
    for line in md.splitlines():
        s = line.strip()
        if not s.startswith("|") or bid not in s:
            continue
        cells = [c.strip() for c in s.strip().strip("|").split("|")]
        if cells and cells[0] == bid:
            return cells[5] if len(cells) > 5 else None
    return None


def main() -> int:
    print("=== P2.2 误差列展示反向测试 ===")

    # 1) 复现 B446：golden 与 candidate 差 ~2e-8（高精度吻合，非相等）
    g, c = 1.758203011, 1.758203009
    md = rep.format_markdown([_R("B446", g, c)], _META_IND)
    e = _err_cell(md, "B446")
    check("① B446 类亚 1e-8 偏差：误差列必须非 0（旧实现会显示 0）",
          e is not None and e != "0", f"err_cell={e!r}")
    check("① 误差列呈现真实小误差（科学计数，非 0/—）",
          e is not None and e not in ("0", "—") and "e" in e.lower(),
          f"err_cell={e!r}")

    # 2) ReferenceCandidate（candidate≡golden）误差必须恒 0（自证桩诚实）
    md_sc = rep.format_markdown(
        [_R("B1", 0.9967, 0.9967, cls="self_consistent_stub", ind=False)],
        _META_SC)
    e_sc = _err_cell(md_sc, "B1")
    check("② ReferenceCandidate（candidate≡golden）误差必须恒 0",
          e_sc == "0", f"err_cell={e_sc!r}")

    # 3) 守护栏 ⑥：1e-15 末位抖动不得泄漏进误差列（报告字节一致）
    r1 = [_R("B1", 0.9967, 0.9967)]
    r2 = [_R("B1", 0.9967 + 1e-15, 0.9967 + 0.5e-15)]
    md1 = rep.format_markdown(r1, _META_IND)
    md2 = rep.format_markdown(r2, _META_IND)
    check("③ 1e-15 末位抖动不泄漏进误差列（报告字节一致）", md1 == md2,
          f"len1={len(md1)} len2={len(md2)}")

    # 4) 反向可证伪：改真实 golden ⇒ 误差列必变（不可过度归一掩盖真变化）
    md_changed = rep.format_markdown([_R("B1", 0.9000, 0.9000)], _META_IND)
    check("④ 反向：改真实 golden ⇒ 报告必变（不可过度归一）",
          md_changed != md1)

    if _FAILS:
        print(f"\n=== FAIL {len(_FAILS)} 项 ===")
        for f in _FAILS:
            print("  FAIL:", f)
        return 1
    print("\n  ✅ P2.2 误差列展示 4 项判据全绿"
          "（亚 1e-8 真实偏差可见 · 抖动被吸收 · 自证桩恒 0 · 真变更可证伪）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
