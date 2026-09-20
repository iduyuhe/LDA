# -*- coding: utf-8 -*-
"""验证适配器 · 公共基座（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

内容：路径常量 / `_ensure_paths` / **候选注册表** `BENCHMARK_CANDIDATES` 与装饰器
`_register_candidate` / 各批次数值核的懒加载器（`_get_batch_*` + `_BATCH_*_MOD`）。

🔴 全文唯一注册表实例在此；所有分片 `from ._adapter_core import _register_candidate`。
拆片**不得**在分片内新建同名容器，否则注册表被割裂而账本静默变化。
"""

from __future__ import annotations

import os

import sys

from typing import (
    Callable, Dict,
)

_HERE = os.path.dirname(os.path.abspath(__file__))

_ROOT = os.path.dirname(os.path.dirname(_HERE))  # 项目根（lda/ 的父目录）：使 `from lda.lda_solver import` 绝对包导入可用

_SOLVER_DIR = os.path.join(os.path.dirname(_HERE), "lda_solver")

_AGENT_DIR = os.path.join(os.path.dirname(_HERE), "lda_agent")

def _ensure_paths():
    # 🔴 v0.9.73：必须也加入 `_HERE`（lda_harness 自身目录）。B31/B32 的候选用
    # `from lda.lda_harness import <mod>`，失败时回退 `import <mod>`——后者要求
    # lda_harness 目录在 sys.path 上。原先只加 solver/agent 目录 ⇒ 直接 `python
    # run_harness.py`（仓库根不在 sys.path）时 B31 候选 ImportError **裸崩**，
    # 主对外报告生成失败（CI 主入口）。见 run_harness.py B31 崩溃复现。
    for p in (_ROOT, _SOLVER_DIR, _AGENT_DIR, _HERE):
        if p not in sys.path:
            sys.path.insert(0, p)

BENCHMARK_CANDIDATES: Dict[str, Callable] = {}

def _register_candidate(key: str, desc: str):
    """登记一个 B 类独立候选（装饰器：同时写入 desc 供报告显示）。"""
    def _wrap(fn: Callable) -> Callable:
        fn.candidate_desc = desc
        BENCHMARK_CANDIDATES[key] = fn
        return fn
    return _wrap

_BATCH_B_MOD = None

def _get_batch_b():
    """双路兜底导入 Batch B-1 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B_MOD
    if _BATCH_B_MOD is not None:
        return _BATCH_B_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b_numeric as _m
    _BATCH_B_MOD = _m
    return _m

_BATCH_B22_MOD = None

def _get_batch_b22():
    """双路兜底导入 Batch B-22 数值核（光纤物理定律族，缓存，项目铁律）。"""
    global _BATCH_B22_MOD
    if _BATCH_B22_MOD is not None:
        return _BATCH_B22_MOD
    try:
        from lda_harness import _batch_b22_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b22_numeric as _m
    _BATCH_B22_MOD = _m
    return _m

_BATCH_B23_MOD = None

def _get_batch_b23():
    """双路兜底导入 Batch B-23 数值核（高斯光束旁轴光学族，缓存，项目铁律）。"""
    global _BATCH_B23_MOD
    if _BATCH_B23_MOD is not None:
        return _BATCH_B23_MOD
    try:
        from lda_harness import _batch_b23_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b23_numeric as _m
    _BATCH_B23_MOD = _m
    return _m

_BATCH_B24_MOD = None

def _get_batch_b24():
    """双路兜底导入 Batch B-24 数值核（标量衍射族，缓存，项目铁律）。"""
    global _BATCH_B24_MOD
    if _BATCH_B24_MOD is not None:
        return _BATCH_B24_MOD
    try:
        from lda_harness import _batch_b24_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b24_numeric as _m
    _BATCH_B24_MOD = _m
    return _m

_BATCH_B25_MOD = None

def _get_batch_b25():
    """双路兜底导入 Batch B-25 数值核（静电/静磁有限源族，缓存，项目铁律）。"""
    global _BATCH_B25_MOD
    if _BATCH_B25_MOD is not None:
        return _BATCH_B25_MOD
    try:
        from lda_harness import _batch_b25_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b25_numeric as _m
    _BATCH_B25_MOD = _m
    return _m

_BATCH_B26_MOD = None

def _get_batch_b26():
    """双路兜底导入 Batch B-26 数值核（单界面 Fresnel/Snell 光学族，缓存，项目铁律）。"""
    global _BATCH_B26_MOD
    if _BATCH_B26_MOD is not None:
        return _BATCH_B26_MOD
    try:
        from lda_harness import _batch_b26_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b26_numeric as _m
    _BATCH_B26_MOD = _m
    return _m

_BATCH_B27_MOD = None

def _get_batch_b27():
    """双路兜底导入 Batch B-27 数值核（色散与群速度族，缓存，项目铁律）。"""
    global _BATCH_B27_MOD
    if _BATCH_B27_MOD is not None:
        return _BATCH_B27_MOD
    try:
        from lda_harness import _batch_b27_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b27_numeric as _m
    _BATCH_B27_MOD = _m
    return _m

_BATCH_B28_MOD = None

def _get_batch_b28():
    """双路兜底导入 Batch B-28 数值核（不完全 Beta / 积分正余弦函数族，缓存，项目铁律）。

    🔴 命名避让：单锚 **B28**（`b28_modulator_vpi_anchor` / `run_b28_*_smoke`）占用无连字符
    写法 `b28_`，故批次核一律用连字符形式 `_batch_b28_numeric` / `_get_batch_b28`
    （接手前已实 grep 核占名：`_BATCH_B28` / `_get_batch_b28` 零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B28_MOD
    if _BATCH_B28_MOD is not None:
        return _BATCH_B28_MOD
    try:
        from lda_harness import _batch_b28_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b28_numeric as _m
    _BATCH_B28_MOD = _m
    return _m

_BATCH_B2_MOD = None

def _get_batch_b2():
    """双路兜底导入 Batch B-2 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B2_MOD
    if _BATCH_B2_MOD is not None:
        return _BATCH_B2_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b2_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b2_numeric as _m
    _BATCH_B2_MOD = _m
    return _m

_BATCH_B3_MOD = None

_BATCH_B4_MOD = None

_BATCH_B5_MOD = None

_BATCH_B6_MOD = None

_BATCH_B7_MOD = None

_BATCH_B8_MOD = None

_BATCH_B9_MOD = None

_BATCH_B10_MOD = None

_BATCH_B11_MOD = None

_BATCH_B12_MOD = None

_BATCH_B13_MOD = None

_BATCH_B14_MOD = None

_BATCH_B15_MOD = None

_BATCH_B16_NUMERIC_MOD = None

_BATCH_B17_NUMERIC_MOD = None

_BATCH_B18_NUMERIC_MOD = None

_BATCH_B19_NUMERIC_MOD = None

_BATCH_B20_NUMERIC_MOD = None

_BATCH_B21_NUMERIC_MOD = None

def _get_batch_b3():
    """双路兜底导入 Batch B-3 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B3_MOD
    if _BATCH_B3_MOD is not None:
        return _BATCH_B3_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b3_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b3_numeric as _m
    _BATCH_B3_MOD = _m
    return _m

def _get_batch_b4():
    """双路兜底导入 Batch B-4 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B4_MOD
    if _BATCH_B4_MOD is not None:
        return _BATCH_B4_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b4_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b4_numeric as _m
    _BATCH_B4_MOD = _m
    return _m

def _get_batch_b5():
    """双路兜底导入 Batch B-5 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B5_MOD
    if _BATCH_B5_MOD is not None:
        return _BATCH_B5_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b5_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b5_numeric as _m
    _BATCH_B5_MOD = _m
    return _m

def _get_batch_b6():
    """双路兜底导入 Batch B-6 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B6_MOD
    if _BATCH_B6_MOD is not None:
        return _BATCH_B6_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b6_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b6_numeric as _m
    _BATCH_B6_MOD = _m
    return _m

def _get_batch_b7():
    """双路兜底导入 Batch B-7 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B7_MOD
    if _BATCH_B7_MOD is not None:
        return _BATCH_B7_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b7_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b7_numeric as _m
    _BATCH_B7_MOD = _m
    return _m

def _get_batch_b8():
    """双路兜底导入 Batch B-8 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B8_MOD
    if _BATCH_B8_MOD is not None:
        return _BATCH_B8_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b8_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b8_numeric as _m
    _BATCH_B8_MOD = _m
    return _m

def _get_batch_b9():
    """双路兜底导入 Batch B-9 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B9_MOD
    if _BATCH_B9_MOD is not None:
        return _BATCH_B9_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b9_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b9_numeric as _m
    _BATCH_B9_MOD = _m
    return _m

def _get_batch_b10():
    """双路兜底导入 Batch B-10 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B10_MOD
    if _BATCH_B10_MOD is not None:
        return _BATCH_B10_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b10_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b10_numeric as _m
    _BATCH_B10_MOD = _m
    return _m

def _get_batch_b11():
    """双路兜底导入 Batch B-11 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B11_MOD
    if _BATCH_B11_MOD is not None:
        return _BATCH_B11_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b11_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b11_numeric as _m
    _BATCH_B11_MOD = _m
    return _m

def _get_batch_b12():
    """双路兜底导入 Batch B-12 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B12_MOD
    if _BATCH_B12_MOD is not None:
        return _BATCH_B12_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b12_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b12_numeric as _m
    _BATCH_B12_MOD = _m
    return _m

def _get_batch_b13():
    """双路兜底导入 Batch B-13 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B13_MOD
    if _BATCH_B13_MOD is not None:
        return _BATCH_B13_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b13_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b13_numeric as _m
    _BATCH_B13_MOD = _m
    return _m

def _get_batch_b14():
    """双路兜底导入 Batch B-14 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B14_MOD
    if _BATCH_B14_MOD is not None:
        return _BATCH_B14_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b14_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b14_numeric as _m
    _BATCH_B14_MOD = _m
    return _m

def _get_batch_b15():
    """双路兜底导入 Batch B-15 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B15_MOD
    if _BATCH_B15_MOD is not None:
        return _BATCH_B15_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b15_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b15_numeric as _m
    _BATCH_B15_MOD = _m
    return _m

def _get_batch_b16_numeric():
    """双路兜底导入 Batch B-16 数值核（缓存，项目铁律：不依赖单一导入路径）。

    ⚠️ 命名避让：`_get_batch_b16()` / `_BATCH_B16_MOD` 已被「B16 单锚重审（脊形 MMI）
    的 `_batch_b16_rib_mmi`」占用；本批次（B-16，B265–B280）的数值核 `_batch_b16_numeric`
    必须另起标识符，两者勿合并。
    """
    global _BATCH_B16_NUMERIC_MOD
    if _BATCH_B16_NUMERIC_MOD is not None:
        return _BATCH_B16_NUMERIC_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b16_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b16_numeric as _m
    _BATCH_B16_NUMERIC_MOD = _m
    return _m

def _get_batch_b17_numeric():
    """双路兜底导入 Batch B-17 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B17_NUMERIC_MOD
    if _BATCH_B17_NUMERIC_MOD is not None:
        return _BATCH_B17_NUMERIC_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b17_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b17_numeric as _m
    _BATCH_B17_NUMERIC_MOD = _m
    return _m

def _get_batch_b18_numeric():
    """双路兜底导入 Batch B-18 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B18_NUMERIC_MOD
    if _BATCH_B18_NUMERIC_MOD is not None:
        return _BATCH_B18_NUMERIC_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b18_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b18_numeric as _m
    _BATCH_B18_NUMERIC_MOD = _m
    return _m

def _get_batch_b19_numeric():
    """双路兜底导入 Batch B-19 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B19_NUMERIC_MOD
    if _BATCH_B19_NUMERIC_MOD is not None:
        return _BATCH_B19_NUMERIC_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b19_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b19_numeric as _m
    _BATCH_B19_NUMERIC_MOD = _m
    return _m

def _get_batch_b20_numeric():
    """双路兜底导入 Batch B-20 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B20_NUMERIC_MOD
    if _BATCH_B20_NUMERIC_MOD is not None:
        return _BATCH_B20_NUMERIC_MOD
    try:  # 优先包路径
        from lda_harness import _batch_b20_numeric as _m
    except ImportError:  # 回退
        _ensure_paths()
        import _batch_b20_numeric as _m
    _BATCH_B20_NUMERIC_MOD = _m
    return _m

def _get_batch_b21_numeric():
    """双路兜底导入 Batch B-21 数值核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B21_NUMERIC_MOD
    if _BATCH_B21_NUMERIC_MOD is not None:
        return _BATCH_B21_NUMERIC_MOD
    try:  # 优先包路径
        from lda_harness import _batch_b21_numeric as _m
    except ImportError:  # 回退
        _ensure_paths()
        import _batch_b21_numeric as _m
    _BATCH_B21_NUMERIC_MOD = _m
    return _m

_BATCH_B16_MOD = None

def _get_batch_b16():
    """双路兜底导入 B16 rib-MMI 求解核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B16_MOD
    if _BATCH_B16_MOD is not None:
        return _BATCH_B16_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b16_rib_mmi as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b16_rib_mmi as _m
    _BATCH_B16_MOD = _m
    return _m

_BATCH_B567_MOD = None

def _get_batch_b567():
    """双路兜底导入 B5/B6 求解核（缓存，项目铁律：不依赖单一导入路径）。"""
    global _BATCH_B567_MOD
    if _BATCH_B567_MOD is not None:
        return _BATCH_B567_MOD
    try:  # 优先包路径（仓库根在 sys.path 时）
        from lda_harness import _batch_b567_numeric as _m
    except ImportError:  # 回退：把 lda_harness 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import _batch_b567_numeric as _m
    _BATCH_B567_MOD = _m
    return _m
