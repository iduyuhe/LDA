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

_BATCH_B29_MOD = None

def _get_batch_b29():
    """双路兜底导入 Batch B-29 数值核（一阶 RC 阶跃充电，缓存，项目铁律）。

    🔴 命名避让：单锚 **B29**（`b29_thermal_phase_anchor` / `run_b29_*`）占用无连字符
    写法 `b29_`，故批次核一律用连字符形式 `_batch_b29_numeric` / `_get_batch_b29`
    （与 B-28 同规；接手前已实 grep 核占名：`_BATCH_B29` / `_get_batch_b29` 零命中）。
    """
    global _BATCH_B29_MOD
    if _BATCH_B29_MOD is not None:
        return _BATCH_B29_MOD
    try:
        from lda_harness import _batch_b29_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b29_numeric as _m
    _BATCH_B29_MOD = _m
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


_BATCH_B30_MOD = None

def _get_batch_b30():
    """双路兜底导入 Batch B-30 数值核（量子征程回填 · 有限维 Fock 截断 × 解析闭式，缓存，项目铁律）。

    🔴 命名避让：单锚 **B30**（色散读出保真度 erfc 链）占用无连字符写法 `b30_`，
    故批次核一律用连字符形式 `_batch_b30_numeric` / `_get_batch_b30`
    （接手前已实 grep 核占名：`_BATCH_B30` / `_get_batch_b30` 全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B30_MOD
    if _BATCH_B30_MOD is not None:
        return _BATCH_B30_MOD
    try:
        from lda_harness import _batch_b30_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b30_numeric as _m
    _BATCH_B30_MOD = _m
    return _m
_BATCH_B32_MOD = None
_BATCH_B31_MOD = None
_BATCH_B33_MOD = None
_BATCH_B34_MOD = None

def _get_batch_b31():
    """双路兜底导入 Batch B-31 数值核（量子征程再评估 · WCS/Poisson 有限维 Fock 截断 × 解析闭式，缓存，项目铁律）。

    🔴 命名避让：单锚 **B31**（Soref-Bennett 载流子色散相移）占用无连字符写法 `b31_`
    （`b31_soref_bennett_anchor.py` / `b31_drude_phase_shift`），故批次核一律用连字符形式
    `_batch_b31_numeric` / `_get_batch_b31`（接手前已实 grep 核占名：`_BATCH_B31` /
    `_get_batch_b31` 全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B31_MOD
    if _BATCH_B31_MOD is not None:
        return _BATCH_B31_MOD
    try:
        from lda_harness import _batch_b31_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b31_numeric as _m
    _BATCH_B31_MOD = _m
    return _m

def _get_batch_b32():
    """B-32 数值核（几何栅格化收敛 · 解析 Shoelace × 亚格平均栅格化，缓存，项目铁律）。

    🔴 命名避让：单锚 **B32** 占用无连字符写法 `b32_`（`b32_cpml_reflection` 等 CPML 锚），
    故批次核一律用连字符形式 `_batch_b32_numeric` / `_get_batch_b32`（接手前已实 grep 核占名，
    B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B32_MOD
    if _BATCH_B32_MOD is not None:
        return _BATCH_B32_MOD
    try:
        from lda_harness import _batch_b32_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b32_numeric as _m
    _BATCH_B32_MOD = _m
    return _m

def _get_batch_b33():
    """B-33 数值核（光子传感器新征程 PS-M2 衍生 · 洛伦兹谐振线型斜率极值：解析闭式 golden × 中心差分数值微分候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B33** 占用无连字符写法 `b33_`（`b33_detector_bandwidth_anchor.py` /
    `b33_detector_bandwidth`），故批次核一律用连字符形式 `_batch_b33_numeric` / `_get_batch_b33`
    （接手前已实 grep 核占名：`_BATCH_B33` / `_get_batch_b33` 全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B33_MOD
    if _BATCH_B33_MOD is not None:
        return _BATCH_B33_MOD
    try:
        from lda_harness import _batch_b33_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b33_numeric as _m
    _BATCH_B33_MOD = _m
    return _m


def _get_batch_b34():
    """B-34 数值核（光子传感器新征程 PS-M3 衍生 · 波导灵敏度 HF 微扰闭式 golden × 有限差分候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B34** 沿用连字符写法 `_batch_b34_numeric` / `_get_batch_b34`
    （与 B-33 同构；接手前已实 grep 核占名：`_BATCH_B34` / `_get_batch_b34` 全仓零命中，
    B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B34_MOD
    if _BATCH_B34_MOD is not None:
        return _BATCH_B34_MOD
    try:
        from lda_harness import _batch_b34_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b34_numeric as _m
    _BATCH_B34_MOD = _m
    return _m


# B-35 数值核缓存占位（与 B-31~B-34 同构，项目铁律）
_BATCH_B35_MOD = None


def _get_batch_b35():
    """B-35 数值核（光子传感器新征程 PS-M4 衍生 · 表面灵敏度 HF 闭式 golden × 三层 TMM-FD 候选 / 朗缪尔闭式 golden × RK4 候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B35** 沿用连字符写法 `_batch_b35_numeric` / `_get_batch_b35`
    （与 B-34 同构；接手前已实 grep 核占名：`_BATCH_B35` / `_get_batch_b35` 全仓零命中，
    B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B35_MOD
    if _BATCH_B35_MOD is not None:
        return _BATCH_B35_MOD
    try:
        from lda_harness import _batch_b35_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b35_numeric as _m
    _BATCH_B35_MOD = _m
    return _m


# B-36 数值核缓存占位（与 B-31~B-35 同构，项目铁律）
_BATCH_B36_MOD = None


def _get_batch_b36():
    """B-36 数值核（光子传感器新征程 PS-M5 衍生 · 微流控/Lab-on-chip 多物理场：矩形 Hagen-Poiseuille 级数 golden × 2D FD Poisson 候选 / Lucas-Washburn 闭式 golden × 后向欧拉候选 / 圆柱径向热阻 Fourier 闭式 golden × 1D FD 径向 Laplace 候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B36** 沿用连字符写法 `_batch_b36_numeric` / `_get_batch_b36`
        （与 B-35 同构；接手前已实 grep 核占名：`_BATCH_B36` / `_get_batch_b36` 全仓零命中，
        B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B36_MOD
    if _BATCH_B36_MOD is not None:
        return _BATCH_B36_MOD
    try:
        from lda_harness import _batch_b36_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b36_numeric as _m
    _BATCH_B36_MOD = _m
    return _m


# B-37 数值核缓存占位（与 B-31~B-36 同构，项目铁律）
_BATCH_B37_MOD = None


def _get_batch_b37():
    """B-37 数值核（光子传感器新征程 PS-M6 衍生 · 规模与集成：密集阵列热串扰闭式 golden × 1D FD 三对角候选 / TIA 读出噪声底 kT/C 频域闭式 golden × 时域冲激响应数值积分候选 / 对准耦合效率高斯重叠闭式 golden × 采样-插值重叠积分候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B37** 沿用连字符写法 `_batch_b37_numeric` / `_get_batch_b37`
        （与 B-35/B-36 同构；接手前已实 grep 核占名：`_BATCH_B37` / `_get_batch_b37` / `b37_`
        全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B37_MOD
    if _BATCH_B37_MOD is not None:
        return _BATCH_B37_MOD
    try:
        from lda_harness import _batch_b37_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b37_numeric as _m
    _BATCH_B37_MOD = _m
    return _m


# B-38 数值核缓存占位（与 B-31~B-37 同构，项目铁律）
_BATCH_B38_MOD = None


def _get_batch_b38():
    """B-38 数值核（光子传感器新征程 PS-M8 衍生 · 几何灵敏度半 + Q 增强 LOD 缩放：薄线/狭缝/悬浮高灵敏几何折射率灵敏度一阶本征值微扰 golden × FV-FD 候选 / Q-scaling LOD 闭式 golden × 模型实算候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B38** 沿用连字符写法 `_batch_b38_numeric` / `_get_batch_b38`
        （与 B-35/B-36/B-37 同构；接手前已实 grep 核占名：`_BATCH_B38` / `_get_batch_b38` / `b38_`
        全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B38_MOD
    if _BATCH_B38_MOD is not None:
        return _BATCH_B38_MOD
    try:
        from lda_harness import _batch_b38_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b38_numeric as _m
    _BATCH_B38_MOD = _m
    return _m


# B-39 数值核缓存占位（与 B-31~B-38 同构，项目铁律）
_BATCH_B39_MOD = None


def _get_batch_b39():
    """B-39 数值核（量子传感器芯片征程 QS-M0 衍生 · NV 色心磁力计磁灵敏度谱密度 η：闭式散粒极限 golden × 数值误差传播链候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B39** 沿用连字符写法 `_batch_b39_numeric` / `_get_batch_b39`
        （与 B-35~B-38 同构；接手前已实 grep 核占名：`_BATCH_B39` / `_get_batch_b39` / `b39_`
        全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B39_MOD
    if _BATCH_B39_MOD is not None:
        return _BATCH_B39_MOD
    try:
        from lda_harness import _batch_b39_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b39_numeric as _m
    _BATCH_B39_MOD = _m
    return _m


# B-40 数值核缓存占位（与 B-31~B-39 同构，项目铁律）
_BATCH_B40_MOD = None


def _get_batch_b40():
    """B-40 数值核（量子传感器芯片征程 QS-M1 衍生 · 灵敏度 FOM 体系：T2* 路径闭式 golden × 数值线宽提取链候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B40** 沿用连字符写法 `_batch_b40_numeric` / `_get_batch_b40`
        （与 B-35~B-39 同构；接手前已实 grep 核占名：`_BATCH_B40` / `_get_batch_b40` / `b40_`
        全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B40_MOD
    if _BATCH_B40_MOD is not None:
        return _BATCH_B40_MOD
    try:
        from lda_harness import _batch_b40_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b40_numeric as _m
    _BATCH_B40_MOD = _m
    return _m


_BATCH_B41_MOD = None


def _get_batch_b41():
    """B-41 数值核（量子传感器芯片征程 QS-M2 衍生 · 自旋回波相位方差：闭式 golden × 时间域数值积分候选，缓存，项目铁律）。

    🔴 命名避让：单锚 **B41** 沿用连字符写法 `_batch_b41_numeric` / `_get_batch_b41`
        （与 B-35~B-40 同构；接手前已实 grep 核占名：`_BATCH_B41` / `_get_batch_b41` / `b41_`
        全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B41_MOD
    if _BATCH_B41_MOD is not None:
        return _BATCH_B41_MOD
    try:
        from lda_harness import _batch_b41_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b41_numeric as _m
    _BATCH_B41_MOD = _m
    return _m


_BATCH_B42_MOD = None


def _get_batch_b42():
    """B-42 数值核（量子传感器芯片征程 QS-M3 衍生 · 灵敏度几何优化：最优色心深度 + NA 立体角收集效率，缓存，项目铁律）。

    🔴 命名避让：单批 **B42** 沿用连字符写法 `_batch_b42_numeric` / `_get_batch_b42`
        （与 B-35~B-41 同构；接手前已实 grep 核占名：`_BATCH_B42` / `_get_batch_b42` / `b42_`
        全仓零命中，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B42_MOD
    if _BATCH_B42_MOD is not None:
        return _BATCH_B42_MOD
    try:
        from lda_harness import _batch_b42_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b42_numeric as _m
    _BATCH_B42_MOD = _m
    return _m


_BATCH_B43_MOD = None


def _get_batch_b43():
    """B-43 数值核（量子传感器芯片征程 QS-M4 衍生 · 阵列化与规模：串扰系数 + 串扰恶化倍率 + 梯度计 CMRR + 梯度灵敏度，缓存，项目铁律）。

    🔴 命名避让：单批 **B43** 沿用连字符写法 `_batch_b43_numeric` / `_get_batch_b43`
        （与 B-35~B-42 同构；接手前已实 grep 核占名：`_BATCH_B43` / `_get_batch_b43`
        全仓零命中——`b43` 仅命中旧锚 `golden_b43`（B43，与批次号无关），B-16 型
        静默撞名风险已排除）。
    """
    global _BATCH_B43_MOD
    if _BATCH_B43_MOD is not None:
        return _BATCH_B43_MOD
    try:
        from lda_harness import _batch_b43_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b43_numeric as _m
    _BATCH_B43_MOD = _m
    return _m


_BATCH_B44_MOD = None


def _get_batch_b44():
    """B-44 数值核（量子传感器芯片征程 QS-M5 衍生 · 闭环标定与动态范围：频锁鉴别器中心斜率 + 磁场标度因子自标定 + AC 灵敏度带宽折算，缓存，项目铁律）。

    🔴 命名避让：单批 **B44** 沿用连字符写法 `_batch_b44_numeric` / `_get_batch_b44`
        （与 B-35~B-43 同构；接手前已实 grep 核占名：`_BATCH_B44` / `_get_batch_b44`
        全仓零命中——`b44` 不命中任何旧锚，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B44_MOD
    if _BATCH_B44_MOD is not None:
        return _BATCH_B44_MOD
    try:
        from lda_harness import _batch_b44_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b44_numeric as _m
    _BATCH_B44_MOD = _m
    return _m


_BATCH_B45_MOD = None


def _get_batch_b45():
    """B-45 数值核（量子传感器芯片征程 QS-M6 衍生 · 超导 SQUID 磁力计：I_c(Φ) 磁通调制 + 磁通-电压转导 + 磁场灵敏度 B_N，缓存，项目铁律）。

    🔴 命名避让：单批 **B45** 沿用连字符写法 `_batch_b45_numeric` / `_get_batch_b45`
        （与 B-35~B-44 同构；接手前已实 grep 核占名：`_BATCH_B45` / `_get_batch_b45`
        全仓零命中——`b45` 不命中任何旧锚，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B45_MOD
    if _BATCH_B45_MOD is not None:
        return _BATCH_B45_MOD
    try:
        from lda_harness import _batch_b45_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b45_numeric as _m
    _BATCH_B45_MOD = _m
    return _m


_BATCH_B46_MOD = None


def _get_batch_b46():
    """B-46 数值核（量子传感器芯片征程 QS-M7 衍生 · SQUID 性能冲刺/噪声优化：磁通聚焦变压器有效面积 A_eff + 亚微米结噪声谱密度 S_Φ,opt + 优化后磁场灵敏度 B_N,opt，缓存，项目铁律）。

    🔴 命名避让：单批 **B46** 沿用连字符写法 `_batch_b46_numeric` / `_get_batch_b46`
        （与 B-35~B-45 同构；接手前已实 grep 核占名：`_BATCH_B46` / `_get_batch_b46`
        全仓零命中——`b46` 不命中任何旧锚，B-16 型静默撞名风险已排除）。
    """
    global _BATCH_B46_MOD
    if _BATCH_B46_MOD is not None:
        return _BATCH_B46_MOD
    try:
        from lda_harness import _batch_b46_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b46_numeric as _m
    _BATCH_B46_MOD = _m
    return _m


_BATCH_B47_MOD = None


def _get_batch_b47():
    """B-47 数值核（量子传感器芯片征程 QS-M9 衍生 · 光泵原子磁力计 OPM/SERF 腿 C：自由进动横向极化 P_x(t*) + 碱金属饱和蒸气数密度 n(T) + 泵浦光 Beer–Lambert 透过率 T(L)，缓存，项目铁律）。

    🔴 命名避让（**本批实踩**）：批次号 **B47** 与**单锚 B47**（`_b47_qm_ho_e2_candidate`，
    量子力学谐振子跃迁）号段重叠 ⇒ 沿用连字符写法 `_batch_b47_numeric` /
    `_get_batch_b47`（实 grep 核验：`_BATCH_B47` / `_get_batch_b47` 全仓零命中；
    而裸 `b47_` 前缀**已被占用** ⇒ 与 B-16 型静默撞名同族，故**禁止**裸 `b47_` 命名）。
    """
    global _BATCH_B47_MOD
    if _BATCH_B47_MOD is not None:
        return _BATCH_B47_MOD
    try:
        from lda_harness import _batch_b47_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_b47_numeric as _m
    _BATCH_B47_MOD = _m
    return _m


_BATCH_QS_M3C_MOD = None


def _get_qs_m3c_numeric():
    """B-48 数值核（量子传感器芯片征程 QS-M3c 衍生 · 腔 QED 物理链：腔品质因子 Q / 有效模体积 V_eff / 单光子耦合 g，缓存，项目铁律）。

    🔴 命名避让（**本批实踩**）：批次号 **B48** 与**单锚 B48**（`_b48_qm_ho_e2_candidate`，
    量子力学单光子 Rabi 耦合）号段重叠 ⇒ 沿用连字符写法 `_batch_qs_m3c_numeric` /
    `_get_qs_m3c_numeric`（实 grep 核验：`_BATCH_QS_M3C` / `_get_qs_m3c_numeric` 全仓零命中；
    而裸 `b48_` 前缀**已被占用** ⇒ 与 B-16 型静默撞名同族，故**禁止**裸 `b48_` 命名）。
    """
    global _BATCH_QS_M3C_MOD
    if _BATCH_QS_M3C_MOD is not None:
        return _BATCH_QS_M3C_MOD
    try:
        from lda_harness import _batch_qs_m3c_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_qs_m3c_numeric as _m
    _BATCH_QS_M3C_MOD = _m
    return _m


_BATCH_J1_MOD = None


def _get_j1_numeric():
    """Batch J1 数值核（量子纠错征程 QEC · M0 阈值标度 + M1 解码器（G_Q9 主项）：
    表面码阈值距离 d*（闭式反解 × 二分根求解）+ 解码器综合症状概率场（erf 闭式 × 二维梯形求积）
    + 解码器匹配代价二阶矩（L²/3 闭式 × 一维梯形求积），缓存，项目铁律）。

    🔴 命名避让（**本批实踩**）：批次号 **J1** 与量子征程里程碑 **J1**（量子纠错）同名 ⇒
    沿用连字符写法 `_batch_j1_numeric` / `_get_j1_numeric`（实 grep 核验：`_BATCH_J1` /
    `_get_j1` 全仓零命中；而 `b497_`/`b498_`/`b499_` 前缀**尚未占用** ⇒ 候选统一
    `b497_/b498_/b499_`）。
    """
    global _BATCH_J1_MOD
    if _BATCH_J1_MOD is not None:
        return _BATCH_J1_MOD
    try:
        from lda_harness import _batch_j1_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j1_numeric as _m
    _BATCH_J1_MOD = _m
    return _m


_BATCH_J2_MOD = None


def _get_j2_numeric():
    """Batch J2 数值核（超导 Transmon 征程 J2 · M2 两比特门层：两比特 CR 门退相干错误率
    （张量 A+D 信道闭式 × 16×16 Liouvillian RK4）+ 残余 ZZ 诱导门错误率
    （闭式 (4/5)sin²(ζt/2) × 矩阵传播子 RK4）），缓存，项目铁律。

    🔴 命名避让：批次号 **J2** 与量子征程里程碑 **J2**（Transmon）同名 ⇒
    沿用连字符写法 `_batch_j2_numeric` / `_get_j2_numeric`；候选 key
    `b506_`/`b507_` 前缀尚未占用。
    """
    global _BATCH_J2_MOD
    if _BATCH_J2_MOD is not None:
        return _BATCH_J2_MOD
    try:
        from lda_harness import _batch_j2_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j2_numeric as _m
    _BATCH_J2_MOD = _m
    return _m


_BATCH_J2M3_MOD = None


def _get_j2m3_numeric():
    """Batch J2-M3 数值核（超导 Transmon 征程 J2 · M3 色散读出链 + 串扰：FDM 多音读出
    相邻通道频谱重叠串扰比 —— 闭式洛伦兹自相关 4γ²/(4γ²+δ²) × sinh 换元+复合 Simpson
    数值卷积），缓存，项目铁律。

    🔴 命名避让：批次号 **J2-M3** 沿用连字符写法 `_batch_j2m3_numeric` / `_get_j2m3_numeric`
    （与 M2 的 `_batch_j2_numeric` / `_get_j2_numeric` 并列，互不覆盖）；候选 key
    前缀 `b508_` 尚未占用。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。
    """
    global _BATCH_J2M3_MOD
    if _BATCH_J2M3_MOD is not None:
        return _BATCH_J2M3_MOD
    try:
        from lda_harness import _batch_j2m3_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j2m3_numeric as _m
    _BATCH_J2M3_MOD = _m
    return _m


_BATCH_J2M4_MOD = None


def _get_j2m4_numeric():
    """Batch J2-M4 数值核（超导 Transmon 征程 J2 · M4 QPU 误差预算集成 + 拓扑对接：
    QPU 耦合图代数连通度 λ₂（Fiedler 值）—— 谱定理闭式 2−2cos(π/max(rows,cols)) ×
    嵌套 Krylov 子空间 Rayleigh–Ritz 最小值），缓存，项目铁律。

    🔴 命名避让：批次号 **J2-M4** 沿用连字符写法 `_batch_j2m4_numeric` / `_get_j2m4_numeric`
    （与 M2 的 `_batch_j2_numeric` / M3 的 `_batch_j2m3_numeric` 并列，互不覆盖）；候选 key
    前缀 `b509_` 尚未占用。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。
    """
    global _BATCH_J2M4_MOD
    if _BATCH_J2M4_MOD is not None:
        return _BATCH_J2M4_MOD
    try:
        from lda_harness import _batch_j2m4_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j2m4_numeric as _m
    _BATCH_J2M4_MOD = _m
    return _m


_BATCH_J3_MOD = None


def _get_j3_numeric():
    """Batch J3-M0M1 数值核（量子测控与读出征程 J3 · M0 时域驱动脉冲 + M1 DRAG 泄漏抑制：
    广义 Rabi 时域布居 解析闭式 × 时域 TDSE RK4；三能级 transmon 驱动泄漏布居
    depressed-cubic 三角法精确谱闭式 × 时域 RK4），缓存，项目铁律。

    🔴 命名避让：批次号 **J3-M0M1** 沿用连字符写法 `_batch_j3_numeric` / `_get_j3_numeric`
    （与 J2 的 `_batch_j2_numeric` / `_batch_j2m3_numeric` / `_batch_j2m4_numeric` 并列，
    互不覆盖）；候选 key 前缀 `b510_` / `b511_` 尚未占用。磁盘 `_adapter_p*.py`
    **不新建**（L9 守卫：恒 6 片）。
    """
    global _BATCH_J3_MOD
    if _BATCH_J3_MOD is not None:
        return _BATCH_J3_MOD
    try:
        from lda_harness import _batch_j3_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j3_numeric as _m
    _BATCH_J3_MOD = _m
    return _m


_BATCH_J4_MOD = None


def _get_j4_numeric():
    """Batch J4 数值核（量子传感系统集成征程 J4 · M0 多参数传感：
    多参数 NV 交叉灵敏度解耦温度分量 —— Cramer 闭式解析反演 × Landweber 迭代解耦），缓存，项目铁律。

    🔴 命名避让：批次号 **J4-M0** 沿用连字符写法 `_batch_j4_numeric` / `_get_j4_numeric`
    （与 `_batch_j1_*` / `_batch_j2*_numeric` / `_batch_j3_numeric` 并列，互不覆盖）；
    候选 key 前缀 `b515_` 尚未占用。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。
    """
    global _BATCH_J4_MOD
    if _BATCH_J4_MOD is not None:
        return _BATCH_J4_MOD
    try:
        from lda_harness import _batch_j4_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j4_numeric as _m
    _BATCH_J4_MOD = _m
    return _m


_BATCH_J5_MOD = None


def _get_j5_numeric():
    """Batch J5 数值核（量子网络与接口征程 J5 · M0 纠缠分发：
    分发后两体纠缠保真度 —— Werner 族解析闭式 (1+3p)/4 × 4×4 密度矩阵距离步进 RK4），缓存，项目铁律。

    🔴 命名避让：批次号 **J5-M0** 沿用连字符写法 `_batch_j5_numeric` / `_get_j5_numeric`
    （与 `_batch_j1_*` / `_batch_j2*_numeric` / `_batch_j3_numeric` / `_batch_j4_numeric` 并列，互不覆盖）；
    候选 key 前缀 `b519_` 尚未占用（`b518_` 已用于 J4-M3）。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。
    """
    global _BATCH_J5_MOD
    if _BATCH_J5_MOD is not None:
        return _BATCH_J5_MOD
    try:
        from lda_harness import _batch_j5_numeric as _m
    except ImportError:
        _ensure_paths()
        import _batch_j5_numeric as _m
    _BATCH_J5_MOD = _m
    return _m
