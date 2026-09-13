"""线程预算：限制数值内核并发度，避免满载功耗峰值触发系统保护性掉电。

🔴 血案（2026-09-05，两次宕机取证）
--------------------------------
跑 `run_coupler_band_smoke.py`（torch CPU 全波段 3D FDTD，7 波长）时系统两次硬重启：
  - `wevtutil` 证据：Kernel-Power **Event 41（关键）**，`BugcheckCode=0`、
    `SleepInProgress=0`、`PowerButtonTimestamp=0`、`WHEABootErrorCount=0`
    ⇒ **不是蓝屏、不是睡眠唤醒失败、不是长按电源键，是硬掉电**。
  - 伴随 `Kernel-Processor-Power` **Event 37（警告）**：「处理器速度受系统固件限制」
    ⇒ PROCHOT / 供电或散热保护触发的固件级限速。
  - 机器 20 线程、**内存 63.3GB（空闲 54.8GB）** ⇒ **排除内存耗尽**。
  - 无 WHEA 硬件错误、无 BugCheck 转储 ⇒ 排除内存/CPU 可纠正错误导致蓝屏。
  - 两次都发生在同一个最重的 CPU 任务（DC 123s + YB 164s 全波段 FDTD）运行中期，
    回归全量 27min 反而没宕机，但**该 smoke 单独在回归中也崩过一次（178.98s，
    恰在 DC 之后进入 YB 的位置）** ⇒ 指向**满载功耗/散热峰值**，而非代码缺陷。

对策（治标且可验证，不动任何物理与判据）
--------------------------------------
把数值内核并发度从「吃满 20 线程」压到「一半核心、上限 10」，功耗峰值显著下降；
代价是耗时上升（实测见 CHANGELOG v0.9.38）。可用 `LDA_FDTD_THREADS` 覆盖。

**本模块只限制并发度，不改任何数值算法、不改判据、不改测量窗。**
"""
from __future__ import annotations

import os

ENV_N = "LDA_FDTD_THREADS"          # 显式覆盖（正整数）
DEFAULT_CAP = 10                    # 上限：再多线程收益递减而功耗线性上升

_ENV_KEYS = (
    "OMP_NUM_THREADS",              # torch / OpenMP
    "MKL_NUM_THREADS",              # Intel MKL（BLAS/LAPACK）
    "NUMEXPR_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMBA_NUM_THREADS",            # numba parallel（须在 numba 导入前设好）
)

# 🔴 确定性铁律（v0.9.75「根治提交噪声」）：**禁止动态线程调整**。
# 血案：torch 在 Windows 上随包分发 Intel OpenMP（libiomp5md.dll），其
# `OMP_DYNAMIC` 默认 **TRUE**（MKL 亦然）⇒ 并行区线程数会**随系统负载自动
# 增减** ⇒ 归约（`torch.sum` 等）的分段与求和顺序随之变化 ⇒ float32 结果
# run-to-run 抖动。D-23 的 κ=(βs−βa)/2 是「大数小差」量（放大 ~180×），
# 该抖动被放大到 ~1e-5，**足以翻写受跟踪报告**（本地 0.1706571 / CI
# 0.1706428 即此）。显式关掉动态调整 ⇒ 线程数严格固定 ⇒ 归约顺序固定 ⇒
# 相同输入字节一致。必须在任何数值内核（torch/MKL）初始化**之前**落 env。
_ENV_FLAGS = (
    ("OMP_DYNAMIC", "FALSE"),       # Intel/GNU OpenMP：禁止动态线程调整
    ("MKL_DYNAMIC", "FALSE"),       # MKL：禁止按负载动态选线程数
)


def budget_threads(default_cap: int = DEFAULT_CAP) -> int:
    """目标并发线程数：env 显式指定优先，否则 = min(cap, cpu//2)。"""
    raw = (os.environ.get(ENV_N) or "").strip()
    if raw:
        try:
            n = int(raw)
            if n > 0:
                return n
        except ValueError:
            pass
    cpu = os.cpu_count() or 4
    return max(1, min(default_cap, max(1, cpu // 2)))


def thread_env_overrides(default_cap: int = DEFAULT_CAP) -> dict:
    """线程预算 + 确定性开关的**完整 env 覆盖表**（供 smoke 与 CI 子进程共用）。

    调用方一律用 `os.environ.setdefault(k, v)` 落地：外部显式设置优先，
    不由本模块覆盖（便于人工诊断时临时改）。
    """
    n = budget_threads(default_cap)
    env = {k: str(n) for k in _ENV_KEYS}
    env[ENV_N] = str(n)
    for k, v in _ENV_FLAGS:
        env[k] = v
    return env


def apply_thread_budget(default_cap: int = DEFAULT_CAP,
                        verbose: bool = False) -> dict:
    """落线程预算到 env + torch，返回披露信息（供 report 诚实记录）。

    注意：env 必须在 numpy/numba/torch 的线程池初始化**之前**设置才完全生效，
    故调用点应尽量靠前（smoke 顶部）。torch 侧额外运行时设置（总是生效）。
    """
    n = budget_threads(default_cap)
    for k, v in thread_env_overrides(default_cap).items():
        os.environ.setdefault(k, v)        # 外部显式设置优先，不覆盖

    torch_n = None
    try:
        import torch
        torch.set_num_threads(n)
        torch_n = torch.get_num_threads()
    except Exception:
        pass

    info = {
        "threads": n,
        "cpu_count": os.cpu_count(),
        "torch_threads": torch_n,
        "source": ENV_N if (os.environ.get(ENV_N) or "").strip() else "auto",
        # 动态线程调整**是否已显式关闭**（确定性前提；label==behavior 披露）。
        # 注意字段名带 `_disabled`：True = 已关闭（好），False = 仍可能随负载伸缩。
        "dynamic_threads_disabled": (os.environ.get("OMP_DYNAMIC", "").upper() == "FALSE"),
    }
    if verbose:
        tail = f"，torch {torch_n} 线程" if torch_n else ""
        print(f"[thread-budget] cpu={info['cpu_count']} → 限 {n} 线程{tail}"
              f"（来源：{info['source']}；可用 {ENV_N} 覆盖）")
    return info
