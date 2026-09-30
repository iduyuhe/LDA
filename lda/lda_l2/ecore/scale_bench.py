# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E4 · 规模对标（诚实边界）（D-153）。

============================================================================
设计定位（吃狗粮：把 E3 的数据通路**推到大规模**并与公开模拟加速器 landmark 对标）
----------------------------------------------------------------------------
两条线：
  ① **规模扫描**：N×N 交叉阵列从 32 到 256（65536 突触），验证端到端正确性并测设计/验证成本；
  ② **诚实对标**：用 A 级公开来源登记的产业界/学术界**模拟计算（compute-in-memory MVM）**
     landmark，对照 LDA 已验证的设计&验证能力，给出**诚实的达国际水平口径**。

🔴 核心纪律（沿用光子 M5 体例）：
  · LDA 是**设计 & 验证工具链**（非流片芯片）⇒ **不报任何 fabricated TOPS / TOPS/W / fJ/op**；
  · landmark 一律照录公开来源并标注 A 级 + 未验证，**不用于计算 LDA 的任何"成就值"**；
  · 对标只在**同族维度**上做（架构族 MVM 交叉阵列 / 精度类别 INT8-class），
    「不同层级（设计工具 vs 流片产品）」与「不做数值性能超越比较」写进 NON_CLAIMED。

🔴 规模律（实测发现，诚实报告）：**相对误差有界、绝对误差 ∝ N**——MVM 输出幅度随 N 增长，
固定 ADC 位数下绝对 LSB 随之增大 ⇒ 须按层输出定标（E3 `out_norm`）；相对误差 ≈ 1/2^bits 有界。

主权纪律（全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；T1 电路级。
"""
from __future__ import annotations

import time

import numpy as np

from .mvm_datapath import MvmDatapath


# ---------------------------------------------------------------------------
# 公开 landmark 登记（A 级公开来源，照录、未验证、不用于计算 LDA 成就值）
# ---------------------------------------------------------------------------
LANDMARKS = [
    {
        "name": "Mythic M1076 AMP (Analog Matrix Processor)",
        "org": "Mythic AI",
        "grain": "product",
        "arch": "analog compute-in-memory MVM crossbar (flash array + on-die ADC)",
        "precision": "INT4 / INT8 (weights)",
        "published_metric": "up to 25 TOPS · typ. 3–4 W · 76 AMP tiles · up to 80M weights（厂商宣称）",
        "source": "https://mythic.ai/?p=134/",
        "tier": "A(厂商公开·照录·未验证)",
    },
    {
        "name": "Academic analog-CIM crossbar proposals (ISAAC/PUMA lineage)",
        "org": "学术界（ISCA/MICRO/Nature 系列等）",
        "grain": "architecture_family",
        "arch": "RRAM/ReRAM MVM crossbar accelerator",
        "precision": "multi-bit cell（随论文而异）",
        "published_metric": "架构级提案（具体数值随论文而异，不逐条登记）",
        "source": "公开学术文献（架构族参照）",
        "tier": "A(公开学术·架构族参照)",
    },
]

# LDA 已验证的能力（**仅设计 & 验证**，不含任何硬件性能主张）
LDA_CAPABILITIES = [
    "可设计并验证 N×N 模拟 MVM 交叉阵列（含晶体管级 MOSFET 模型 + MNA 电路仿真器 DC/瞬态/AC）",
    "端到端模拟计算数据通路（DAC→交叉阵列→ADC）：输出 vs 全精度数字 golden 在量化界内",
    "架构族 = MVM 交叉阵列（模拟 compute-in-memory，与商业/学术同类加速器**同族**）",
    "含带符号权重映射（参考列法）、多层级联（MLP+ReLU）、分块合成、规模扫描（至 256×256）",
]

# LDA **明确不主张**的维度（诚实边界）
NON_CLAIMED = [
    "不报任何 TOPS / TOPS/W / fJ/op 等能效或吞吐指标（LDA 是设计&验证工具链，非流片芯片）",
    "不宣称实测精度 / 良率 / 工艺（无硅、无 PDK 标定、无实测锚）",
    "不与商业器件做数值上的「性能超越」比较（不同层级：设计工具 vs 流片产品）",
]

# 禁止出现在 LDA_CAPABILITIES 里的「硬件性能指标」token（防把 landmark 数字误当 LDA 成就）
_FABRICATED_METRIC_TOKENS = ("TOPS", "fJ/op", "TOPS/W")


def honest_boundary_ok() -> bool:
    """诚实边界护栏：LDA_CAPABILITIES 不得含任何硬件能效/吞吐指标断言。"""
    joined = " ".join(LDA_CAPABILITIES)
    return not any(tok in joined for tok in _FABRICATED_METRIC_TOKENS)


def honest_comparison() -> dict:
    """诚实对标口径：同族维度可比；层级不同；数值性能不主张。"""
    return {
        "matched_dimensions": [
            ("架构族", "MVM 交叉阵列 / 模拟 compute-in-memory"),
            ("精度类别（模型层）", "INT8-class 量化（LDA 建模 6–8 bit）"),
        ],
        "different_layer": "商业/学术 landmark = 流片硅（或有硅实测）；LDA = 设计 & 验证工具链（无流片）",
        "non_claimed": list(NON_CLAIMED),
        "landmarks": list(LANDMARKS),
    }


# ---------------------------------------------------------------------------
# 规模扫描（把数据通路推到大规模，测正确性 + 设计/验证成本）
# ---------------------------------------------------------------------------
def scale_sweep(sizes=(32, 64, 128, 256), dac_bits: int = 8, adc_bits: int = 8,
                seed: int = 0) -> list:
    """对每个 N 建 N×N 单层数据通路，测绝对/相对误差 + 建解耗时 + 突触数。"""
    rng = np.random.RandomState(seed)
    out = []
    for N in sizes:
        W = rng.uniform(-1.0, 1.0, (N, N))
        x = rng.uniform(0.0, 1.0, N)
        t0 = time.perf_counter()
        dp = MvmDatapath([W], dac_bits=dac_bits, adc_bits=adc_bits)
        ea = dp.max_abs_err(x)
        er = dp.max_rel_err(x)
        dt = time.perf_counter() - t0
        out.append({"n": N, "synapses": N * N, "abs_err": float(ea),
                    "rel_err": float(er), "seconds": float(dt)})
    return out


def scale_bench_self_check(seed: int = 0) -> dict:
    """规模对标自证：相对误差有界 / 绝对误差随 N 增长（固定位数 ADC 的固有律）/ 对标口径完整。"""
    rows = scale_sweep((32, 64, 128, 256), seed=seed)
    rel = [r["rel_err"] for r in rows]
    abs_ = [r["abs_err"] for r in rows]
    # 相对误差有界（不随 N 爆炸）；绝对误差随 N 单调增长（∝N 的固有律）
    rel_bounded = max(rel) < 0.1
    abs_growing = abs_[-1] > abs_[0]
    return {
        "rows": rows,
        "rel_err_max": float(max(rel)),
        "rel_err_bounded": bool(rel_bounded),
        "abs_err_growing_with_N": bool(abs_growing),
        "max_scale_tested": int(rows[-1]["n"]),
        "max_synapses_tested": int(rows[-1]["synapses"]),
        "honest_boundary_ok": bool(honest_boundary_ok()),
        "landmark_count": len(LANDMARKS),
    }


SCALE_BENCH_DISCLOSURE = {
    "route": "电子计算征程 E4 · 规模对标（诚实边界）",
    "e4_scope": "N×N 数据通路规模扫描（至 256×256=65536 突触）+ 公开模拟加速器 landmark 诚实对标",
    "scale_law": "相对误差有界（≈1/2^bits，N 无关）；绝对误差 ∝ N（固定位数 ADC 固有律，须按层输出定标）",
    "honest_boundary": "LDA 是设计&验证工具链（非流片芯片）⇒ 不报 TOPS/TOPS/W/fJ/op；"
                       "landmark 照录公开来源(A级)、未验证、不用于计算 LDA 成就值；只在同族维度对标",
    "redline": "T1 电路级（不碰 Foundry TCAD/流片）；C 级自主（纯 numpy）；LLM 不进判决路径",
}
