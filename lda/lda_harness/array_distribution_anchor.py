"""LDA 系统锚 · 阵列分布锚（S12 · v0.8.42 · 锚+统计混合判决）。

定位（系统级共识「统计锚不破红线」的落地）：
  单点死标量锚（B/E/S 系）判「单个设计点达标」；对**多实例阵列**
  （WDM 多通道、CPO 多通道、量子读出多比特、PIC 阵列）需要**分布级
  判决**——均值达标但个别通道劣化（离群）是单点锚抓不到的盲区。

S12 混合判决（全部纯算术，LLM 不进判决路径）：
  1. **均值锚**：|mean(values) − golden_mean| ≤ tol_mean（分布中心达标）；
  2. **下界锚**：min(values) ≥ golden_min − tol_min（最差实例不低于
     公开规格下限——「个别通道劣化」的直接捕获）；
  3. **离群锚**：max(values) ≤ median(values) + outlier_margin（无孤立
     异常实例——防「均值好看但某通道崩坏」）。
  三者 AND 才 PASS——比单点锚严格，正是系统级需要的阵列判决。

红线与诚实边界：
  - 判决 = 死标量算术（statistics 模块），LLM 只可能生成候选/默认参数；
  - golden 可来自解析（物理定律锚）或公开规格（实证锚）——本模块提供
    通用统计判决器 + 两个可溯源示例（多通道插损 / 多比特保真度）；
  - 确定性：同一输入序列 → 同一判决（无随机）；可复现性由 smoke 守护。
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Sequence, Tuple


def array_distribution_verdict(
        values: Sequence[float],
        golden_mean: float,
        tol_mean: float,
        golden_min: float,
        tol_min: float,
        outlier_margin: float,
) -> Dict[str, Any]:
    """多实例阵列分布判决（锚+统计混合，纯算术）。

    参数：
      values          实测性能序列（N 实例，如各通道插损 dB / 各比特保真度）
      golden_mean     分布中心 golden（公开规格均值 / 解析值）
      tol_mean        均值容差（|mean−golden| ≤ tol）
      golden_min      最差实例下限（公开规格 min 值）
      tol_min         下限容差（min ≥ golden_min − tol_min）
      outlier_margin  离群阈值（max ≤ median + margin——防孤立劣化）
    返回：
      verdict ACCEPT/REJECT + 逐锚分解 + 分布统计（确定性可复现）。
    """
    if not values:
        return {"verdict": "REJECT", "error": "空序列",
                "checks": [], "stats": {}}
    mean = statistics.fmean(values)
    med = statistics.median(values)
    vmin = min(values)
    vmax = max(values)
    mean_ok = abs(mean - golden_mean) <= tol_mean
    min_ok = vmin >= golden_min - tol_min
    out_ok = vmax <= med + outlier_margin
    checks = [
        {"name": "均值锚", "ok": mean_ok, "detail": f"mean={mean:.4f} vs "
         f"golden {golden_mean}±{tol_mean}"},
        {"name": "下界锚", "ok": min_ok, "detail": f"min={vmin:.4f} vs "
         f"下限 {golden_min}−{tol_min}"},
        {"name": "离群锚", "ok": out_ok, "detail": f"max={vmax:.4f} vs "
         f"median+margin {med + outlier_margin:.4f}"},
    ]
    return {
        "verdict": "ACCEPT" if (mean_ok and min_ok and out_ok) else "REJECT",
        "checks": checks,
        "stats": {"n": len(values), "mean": round(mean, 4),
                  "median": round(med, 4), "min": round(vmin, 4),
                  "max": round(vmax, 4),
                  "p5": round(sorted(values)[max(0, int(len(values) * 0.05) - 1)], 4),
                  "p95": round(sorted(values)[min(len(values) - 1,
                                                  int(len(values) * 0.95))], 4)},
    }


def array_insertion_loss_anchor(n_channels: int = 8, seed: int = 42
                                ) -> Tuple[float, List[float]]:
    """S12a 示例：多通道插损阵列分布（可溯源公开规格量级）。

    golden：CPO/光引擎每通道插损公开规格（6–12 dB 区间，均值≈9）。
    生成 N 通道高斯分布（确定性 seed），返回 (均值, 全通道序列)。
    这是**示例锚**——真实 PDK 实测阵列替换 values 即生效（接口不变）。
    """
    import random
    rng = random.Random(seed)
    vals = [round(9.0 + rng.gauss(0.0, 0.5), 4) for _ in range(n_channels)]
    return round(statistics.fmean(vals), 4), vals


def array_fidelity_anchor(n_qubits: int = 8, seed: int = 7
                          ) -> Tuple[float, List[float]]:
    """S12b 示例：多比特读出保真度阵列分布。

    golden：商用超导系统 per-qubit 读出保真度公开区间（98.5–99.33%）。
    生成 N 比特高斯分布（确定性 seed），返回 (均值, 全比特序列)。
    """
    import random
    rng = random.Random(seed)
    vals = [round(0.9900 + rng.gauss(0.0, 0.002), 6) for _ in range(n_qubits)]
    return round(statistics.fmean(vals), 6), vals


def s12_array_distribution_verdict(
        kind: str = "insertion_loss", seed: int = 42,
        n_instances: int = 8) -> float:
    """S12 golden_fn：生成确定性阵列 + 分布判决（返回标量 1.0/0.0）。

    harness 判决要求 golden_fn 返回标量（与 S9/S10/S11 verdict 锚同模式）。
    值在函数内生成（确定性 seed，与 S7 蒙特卡洛同构）——固定输入得到
    固定判决，可复现是统计锚的判决前提。详细结构见
    s12_array_distribution_report（smoke/报告直接调用）。
    """
    r = s12_array_distribution_report(kind=kind, seed=seed,
                                      n_instances=n_instances)
    return 1.0 if r["verdict"] == "ACCEPT" else 0.0


def s12_array_distribution_report(
        kind: str = "insertion_loss", seed: int = 42,
        n_instances: int = 8) -> Dict[str, Any]:
    """S12 详细报告（生成序列 + 逐锚分解 + 分布统计）——smoke/WebUI 消费。"""
    if kind == "insertion_loss":
        _, vals = array_insertion_loss_anchor(n_instances, seed=seed)
        return array_distribution_verdict(
            vals, golden_mean=9.0, tol_mean=0.3,
            golden_min=6.0, tol_min=0.5, outlier_margin=2.0)
    if kind == "fidelity":
        _, vals = array_fidelity_anchor(n_instances, seed=seed)
        return array_distribution_verdict(
            vals, golden_mean=0.99, tol_mean=0.005,
            golden_min=0.985, tol_min=0.005, outlier_margin=0.01)
    raise ValueError(f"未知 kind: {kind}")
