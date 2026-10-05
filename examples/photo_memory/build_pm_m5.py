#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PM-M5 货架脚本：生成 `lda_pm_m5_report.json`（国际对标收官报告）。

落盘前硬断言：
  1) 报告 == `pm_m5.m5_report()` 现算（不转录）；
  2) 无未替换占位符（`%s` 残留）。
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "lda"))

from lda_l2 import pm_m5 as M5  # noqa: E402


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    rep = M5.m5_report("GST")
    rep["generated_by"] = "examples/photo_memory/build_pm_m5.py"

    text = json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True)
    assert "%s" not in text, "未替换占位符 %s 残留"
    assert text.count("{") > 10, "报告异常为空"

    out = os.path.join(here, "lda_pm_m5_report.json")
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    print("written %s (%d B) · rows=%d · verdicts=%s · gaps=%d/%d"
          % (os.path.basename(out), len(text.encode("utf-8")), len(rep["rows"]),
             rep["verdict_counts"], rep["gaps_closed"], rep["gaps_total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
