# -*- coding: utf-8 -*-
"""BENCHMARK_DEFS 装配点（F-08 巨石治理 · v0.9.117）。

🔴 合并顺序契约：**必须**按 part1→partN 顺序 `update`，不得调换、不得改用 dict 合并
表达式（`{**a, **b}` 亦可但需保序）。`BENCHMARK_DEFS` 的**插入序**与 `BENCHMARK_ORDER`
共同决定全仓遍历序，是账本三分类的输入；顺序漂移不会报错，只会静默换账本。
判据：`python scripts/registry_snapshot.py --check <拆前快照>`。
"""
from .part1 import DEFS as _P1
from .part2 import DEFS as _P2
from .part3 import DEFS as _P3
from .part4 import DEFS as _P4
from .part5 import DEFS as _P5

BENCHMARK_DEFS: dict = {}
for _part in (_P1, _P2, _P3, _P4, _P5):
    BENCHMARK_DEFS.update(_part)
del _part
