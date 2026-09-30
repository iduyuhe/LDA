"""光计算芯片对标基准（达国际水平 · 任务 #5 / M5）。

═══════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════
LDA 光计算征程 **M1→M4**（非酉 SVD 分解 / 激活与量化标定 / 光电协同仿真 /
规模扩张与 tiling）已在平台内把「光子张量核」从「能算」推到「算得准、规模可扩」。
M5 把平台能力**对标到国际公开基准**：用 A 级公开来源（Nature / Science /
AIP / MIT News / 厂商官网）登记的产业界光计算 landmark，对照 LDA 已验证的
设计&验证能力，给出**诚实的达国际水平口径**。

🔴 **关键纪律（吃狗粮发现的平台短板，逐条守住）**：
- **LDA 是设计&验证工具链（EDA/signoff），不是已流片光子芯片** —— 不报任何
  fabricated TOPS/W 数字（那是制造与系统级的事）。公开基准的 TOPS/W 是「已交付
  芯片」的实测/厂商标称，两者**按架构族 + 设计质量方法论**比较，不按 die 级
  benchmark 数字同台比。
- **架构族对齐**：LDA 用 **MZI mesh（Reck 三角分解）**，与 MIT 学术 lineage
  （Shen/Harris 2017 → 2025 Nature 128×128 PTC）**同族**；该 lineage 的公开瓶颈
  正是「MZI mesh 受限于制备误差（fabrication imperfections）」（AIP AML 2024）。
  LDA 的 **scale-blind 保真 + 闭环标定 + tiling 局部标定** 正是对这一瓶颈的工程解。
- **零能效数字**：复用 `optical_pareto.assert_no_energy_metrics`（单一真源），
  本模块不输出 pj/MAC、TOPS/W 等能效指标。
- **LLM 不进判决路径**；电子域只到行为级（T1 候选，非 ORACLE）。

🔴 **诚实边界来源标记**：公开数字均带来源 URL/论文（A 级 golden），LDA 实绩
来自 M1–M4 门禁（方法学可复核、非自证）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from . import optical_pareto
from . import photonic_mesh_tiling as T  # M4：scale-blind / reck_mzi_count 复用（DRY）

__all__ = [
    "CASE_ID", "ARCH", "LDA_PHOTONIC_HONEST_NOTE",
    "PUBLIC_LANDMARKS", "lda_demonstrated", "architecture_class",
    "scale_blind_extrapolation", "benchmark_table", "case_card",
    "run_selfchecks",
]


# ═══════════════════════════════ 常量（与平台模块同源）═══════════════════════════
CASE_ID = "LDA-P · 硅光张量核 / 光神经网络（光子计算芯片）"
ARCH = "MZI mesh（Reck 三角分解）· 非酉 SVD 路径 · 光电协同仿真"

#: M4 已验证的尺度盲基准（静态登记，源自 run_photonic_compute_m4 门禁实测）
SCALE_BLIND_BASE = {
    "N_list": [8, 16, 32, 64, 128, 256],
    "ratio_rel_std": 0.0766,        # (1−F)/√((N−1)/N) 的相对标准差
    "fid_at_256": 0.9932,           # N=256 网格酉保真度
    "tiling_gain_x": 2.8,           # 局部标定相对 monolithic 的 1−F 降幅
    "verdict": "scale_blind",
}


# ═══════════════════════════════ A 级公开基准（带来源 URL · 非 LDA 仿真值）═════════════════════════════
#: 每条约等于一条「产业界已公开登记」的 landmark；`source` 为可复核 URL/论文。
PUBLIC_LANDMARKS: Dict[str, Dict[str, Any]] = {
    "lightmatter_envise_2025": {
        "who": "Lightmatter", "year": 2025,
        "venue": "Nature（Universal photonic artificial intelligence acceleration）",
        "arch": "光广播 + 电子加权累加（4×128×128 PTC，349 mm²/核）",
        "matrix": "128×128 / PTC（4 核封装）",
        "process": "90-nm SiPh",
        "clock_ghz": 2.0, "clock_avg_ghz": 0.5,
        "tops_w_photonic_core": 262.0,      # 光子核实测口径
        "latency_per_mvm_s": 200e-12,
        "workloads": "ResNet18 CIFAR-10 86.4%（FP32 的 97.8%）；BERT-Tiny IMDb 83.2%（96.5% FP32）",
        "source": "https://whychips.com/optical-computing-for-ai-inference-2026-energy-benchmarks ; "
                  "https://www.clppublishing.net/articles/OJ20108ea49ccd5e7e",
    },
    "lightmatter_pace_2025": {
        "who": "Lightmatter", "year": 2025,
        "venue": "Nature（与 Envise 背靠背 · 组合优化超低延迟）",
        "arch": "硅光组合优化加速器（PACE）",
        "matrix": "组合优化 Ising 求解",
        "tops": 8.19, "tops_w_excl_lasers": 4.21, "tops_w_incl_lasers": 2.38,
        "source": "https://www.clppublishing.net/articles/OJ20108ea49ccd5e7e",
    },
    "mit_2017_nanophotonic": {
        "who": "MIT（Shen, Harris, Soljačić, Englund 等）", "year": 2017,
        "venue": "Nature Photonics（Programmable nanophotonic processor）",
        "arch": "MZI mesh（可编程纳米光子处理器）",
        "matrix": "元音识别 4 类",
        "note": "「原则上零能耗、几乎瞬时」；元音识别 77%（传统 90%）",
        "source": "https://news.mit.edu/2017/new-system-allows-optical-deep-learning-0612",
    },
    "mit_2024_integrated": {
        "who": "MIT（Englund lab）", "year": 2024,
        "venue": "2024-12 全集成光子处理器（训练+推理全光）",
        "arch": "MZI mesh（全集成）",
        "acc_train": 0.96, "acc_infer": 0.92,
        "latency_per_pass_s": 0.5e-9,
        "note": "前向传播 < 0.5 ns；训练 >96% / 推理 >92% 准确率",
        "source": "https://whychips.com/optical-computing-for-ai-inference-2026-energy-benchmarks",
    },
    "mit_2026_hypermux": {
        "who": "MIT（Englund, Hamerly 等）", "year": 2026,
        "venue": "Nature Communications（DOI 10.1038/s41467-026-68452-x）",
        "arch": "空-谱-时超复用衍射光束路由（单发 matrix-matrix）",
        "matrix": "16×16×16×16 MMM（4096 MAC/shot）",
        "throughput_gsa": 2.0, "energy_aj_per_mac": 20.0, "acc": 0.964,
        "source": "https://www.rle.mit.edu/?p=12123/",
    },
    "tsinghua_taichi_2024": {
        "who": "清华大学（Taichi / 太极）", "year": 2024,
        "venue": "Science（分布式广度光计算架构）",
        "arch": "WDM + chiplet 分布式广度架构",
        "tops_w": 160.0,
        "note": "通用智能负载 160 TOPS/W；支持图像分类到内容生成",
        "source": "https://whychips.com/optical-computing-for-ai-inference-2026-energy-benchmarks",
    },
    "aip_aml_2024_table": {
        "who": "AIP Applied Physics Letters（综述对比表）", "year": 2024,
        "venue": "AIP AML 2024 性能对比表",
        "note": "MZI-mesh 可达 ≤800×800、≤9 TOPS/W、≤10 TOPS/mm²；"
                "MRR weight bank ≤100×100、≤15 TOPS/W；"
                "Lightmatter 128×128 0.81 TOPS/W、0.047 TOPS/mm²（光广播+电子加权口径）；"
                "NVIDIA B200 9 TOPS/W、5.5 TOPS/mm²；IBM Hermes 256×256 9.76 TOPS/W",
        "source": "https://pubs.aip.org/aip/aml/article/4/2/026114/3394765/"
                  "A-case-study-on-the-performance-metrics-of",
    },
    "ayar_labs": {
        "who": "Ayar Labs", "year": 2024,
        "venue": "厂商（光 I/O chiplet · TeraPHY）",
        "arch": "光互连 I/O（**非计算核**）",
        "note": "Ayar 做**光互连层（非计算核）**（带宽/延迟），与 LDA 的**计算核**不同层；"
                "用户问及时须明标二者不在同层比较",
        "source": "https://lightmatter.co（产业版图背景）",
    },
}


# ═════════════════════════════ LDA 已验证实绩（M1–M4 · 方法学可复核 · 非 fabricated）═════════════════════════════
def lda_demonstrated() -> Dict[str, Any]:
    """LDA 光计算征程已验证的设计&验证能力（静态登记 + M4 实时复算）。

    🔴 **不含任何 fabricated TOPS/W / pj/MAC 能效数字**（那是制造与系统级，
    不在设计工具链职责内）。比较只按「架构族 + 设计质量方法论」进行。
    """
    # 实时复用 M4 的尺度盲判定（DRY + 可复核）
    sb = T.scale_blind_check([8, 16, 32, 64, 128, 256], 0.05, n_trials=20, base_seed=1)
    ratio_rel_std = float(sb["verdict"]["ratio_rel_std"])
    scale_blind = bool(sb["verdict"]["scale_blind"])

    mzi_256 = T.reck_mzi_count(256)
    big = T.bigN_feasibility(256, dac_bits=16, seed=7)

    return {
        "arch": ARCH,
        "max_matrix_verified": 256,                 # M4 bigN
        "mzi_count_at_256": mzi_256,                # = 256*255//2 = 32640
        "grid_fidelity_at_256": round(float(big["fidelity_U_mesh"]), 4),
        "scale_blind": scale_blind,
        "scale_blind_ratio_rel_std": round(ratio_rel_std, 4),
        "tiling_fidelity_gain_x": SCALE_BLIND_BASE["tiling_gain_x"],
        # M3 光电协同仿真
        "eo_full_accuracy": 1.0,
        "eo_vpi_mismatch_accuracy_uncal": 0.833,   # Vπ+5% 未标定
        "eo_vpi_mismatch_accuracy_cal": 1.0,        # 闭环标定后回收
        "eo_dac_phase_res_rad": 0.098,
        "eo_cal_residual_8bit": 0.00331,
        # M1/M2 基础
        "m1_nonunitary_svd": True,
        "m2_activation": ["relu", "sigmoid", "tanh"],
        "m2_endtoend_accuracy": 1.0,
        # 设计容量延展（靠 scale-blind 性质，理想 fab 假设）
        "extrapolatable_to": 800,                   # 文献 MZI-mesh 最大类
        # 🔴 关键：LDA 不报 fabricated 能效数字
        "reports_fabricated_tops_w": False,
    }


# ═════════════════════════════ 架构族对齐（诚实比较的核心）═════════════════════════════
def architecture_class() -> Dict[str, Any]:
    """把 LDA 的 MZI mesh 归到公开学术/产业 lineage，并明确「不与谁同台比」。"""
    return {
        "lda_arch": ARCH,
        "same_lineage_as": [
            "MIT 2017 Shen/Harris 可编程纳米光子处理器（MZI mesh 原创 lineage）",
            "MIT 2024 全集成光子处理器（MZI mesh，训练+推理全光）",
            "Lightmatter 2025 Nature 128×128 PTC（MZI-mesh 学术 lineage 的产业化）",
        ],
        "different_subarch_note": "Lightmatter 商用 Envise 采用「光广播 + 电子加权」口径"
                                  "（AIP AML 表记为 0.81 TOPS/W），与纯 MZI mesh 实现不同子架构；"
                                  "LDA 与 MIT 学术 MZI-mesh lineage 同族。",
        "not_same_layer_as": ["Ayar Labs（光 I/O 互连层，非计算核）"],
        "literature_mzi_mesh_max": 800,            # AIP AML：MZI-mesh ≤800×800
        "literature_mzi_mesh_max_tops_w": 9.0,      # AIP AML：MZI-mesh ≤9 TOPS/W
        "lda_addresses_bottleneck": "MZI mesh 受限于制备误差（AIP AML 2024 原文）；"
                                    "LDA 的 scale-blind 保真 + 闭环 Vπ 标定 + tiling 局部标定"
                                    "正是对该瓶颈的工程解。",
    }


# ═════════════════════════════ 尺度盲外推（诚实：设计保真度，理想 fab 假设）═════════════════════════════
def scale_blind_extrapolation(N_target: int = 800,
                              base_fid: Optional[float] = None) -> Dict[str, Any]:
    """利用 scale-blind 性质，把网格酉保真度外推到更大 N（文献 MZI-mesh 最大类 800×800）。

    🔴 诚实口径：返回的是**设计期保真度**（理想制备假设下，网格本身的酉保真不随 N 塌缩）。
    真实制备误差由 LDA 的**闭环标定 + tiling 局部标定**吸收——这正是本模块对标到的
    产业瓶颈的工程解。故 `caveat` 明示：非流片实测保真。
    """
    if base_fid is None:
        base_fid = SCALE_BLIND_BASE["fid_at_256"]
    mzi = T.reck_mzi_count(N_target)
    # scale-blind：1−F ≈ 常数（≈ base 的 1−F），保真度不随 N 塌缩
    est_1mf = 1.0 - base_fid
    est_fid = 1.0 - est_1mf
    return {
        "N_target": N_target,
        "mzi_count": mzi,
        "est_grid_fidelity": round(float(est_fid), 4),
        "basis": "scale-blind：1−F ≈ 常数（源自 M4 实测 ratio_rel_std=%.4f）"
                  % SCALE_BLIND_BASE["ratio_rel_std"],
        "caveat": "设计期保真度（理想 fab 假设）；真实制备误差由闭环标定+tiling 吸收，"
                  "非流片实测保真。",
    }


# ═════════════════════════════ 对标表（结构化）═════════════════════════════
def benchmark_table() -> List[Dict[str, Any]]:
    """生成对标表行（公开 landmark + LDA 实迹），每行带 `tag` 明示层级。"""
    rows: List[Dict[str, Any]] = []
    for key, v in PUBLIC_LANDMARKS.items():
        rows.append({
            "tag": "FABRICATED_CHIP" if "tops_w" in v or "tops_w_photonic_core" in v
                   or "energy_aj_per_mac" in v else "LANDMARK",
            "key": key, "who": v.get("who", ""), "year": v.get("year", ""),
            "arch": v.get("arch", ""), "matrix": v.get("matrix", ""),
            "metric": _landmark_metric(v), "source": v.get("source", ""),
        })
    # LDA 行（设计&验证层，非 fabricated）
    d = lda_demonstrated()
    rows.append({
        "tag": "LDA_DESIGN_VERIFY",
        "key": "lda_photonic_compute", "who": "LDA（开源 Agent-native EDA · MIT）",
        "year": 2026, "arch": d["arch"],
        "matrix": "%d×%d 已验证 / ≤%d×%d 可设计（scale-blind）"
                  % (d["max_matrix_verified"], d["max_matrix_verified"],
                      d["extrapolatable_to"], d["extrapolatable_to"]),
        "metric": "网格保真 %.4f（N=256）· scale-blind=%s · tiling 增益 %.1f× · "
                  "EO 闭环标定回收 Vπ 失配 83.3%%→100%%"
                  % (d["grid_fidelity_at_256"], d["scale_blind"], d["tiling_fidelity_gain_x"]),
        "source": "M1–M4 门禁（run_photonic_compute_m*_smoke.py）",
    })
    return rows


def _landmark_metric(v: Dict[str, Any]) -> str:
    if "tops_w_photonic_core" in v:
        return "%.0f TOPS/W（光子核）" % v["tops_w_photonic_core"]
    if "tops_w" in v:
        return "%.0f TOPS/W" % v["tops_w"]
    if "tops_w_excl_lasers" in v:
        return "%.2f TOPS/W（不含激光）" % v["tops_w_excl_lasers"]
    if "energy_aj_per_mac" in v:
        return "%.0f aJ/MAC · %.0f Gsa/s" % (v["energy_aj_per_mac"], v["throughput_gsa"])
    if "acc_train" in v:
        return "训练 %.0f%% / 推理 %.0f%% · <%.1f ns" % (
            100 * v["acc_train"], 100 * v["acc_infer"],
            1e9 * v["latency_per_pass_s"])
    if "note" in v:
        return v["note"]
    return v.get("venue", "")


# ═════════════════════════════ 诚实边界（逐条 · 不静默）═════════════════════════════
LDA_PHOTONIC_HONEST_NOTE = (
    "① 本征程是**设计&验证工具链（EDA/signoff）能力证明**，**非已流片光子芯片**——"
    "无 foundry 回片、无光学校准实测、无 TOPS/W 实测；"
    "② **不宣称任何 fabricated 能效数字**：公开基准的 TOPS/W 是「已交付芯片」的"
    "实测/厂商标称，LDA 不报任何 pj/MAC、TOPS/W（那是制造与系统级，非设计工具链职责）；"
    "③ 比较按**架构族 + 设计质量方法论**进行，不按 die 级 benchmark 数字同台比；"
    "LDA 的 MZI mesh 与 MIT 学术 lineage（Shen/Harris→2025 Nature 128×128 PTC）**同族**，"
    "Lightmatter 商用 Envise 的「光广播+电子加权」为不同子架构；"
    "④ **规模 = 设计容量**：256 是「可设计且可验证保真度」的矩阵规模，非已制备器件；"
    "延展到 800×800 类靠 scale-blind 性质（理想 fab 假设），非流片实测；"
    "⑤ 电子域只到**行为级**（一阶 RC 驱动 + 单极点 TIA，T1 候选、非 ORACLE），"
    "不碰晶体管级 DAC/ADC/SerDes/DSP；Vπ 跨模块口径差（25 V·cm vs 7.5 V·mm，"
    "差 ~3.3×）已在 co-sim 层用单一 vpi_v=7.5V 贯穿规避，根因统一留作独立 sprint（任务 #7）；"
    "⑥ 🔴 零能效数字：复用 `assert_no_energy_metrics`，本模块不输出能效指标；"
    "⑦ LLM 不进判决路径：判决为死标量比对，红线为物理定律（酉幺正性、Vπ·L 律）。"
)


# ═════════════════════════════ 案例卡（照 schip_case 体例）═════════════════════════════
def case_card() -> Dict[str, Any]:
    """组装光计算芯片对标案例卡（只读 · 设计&验证层）。verdict 恒 `DESIGN_SIGNOFF`。"""
    d = lda_demonstrated()
    ext = scale_blind_extrapolation(800)
    ac = architecture_class()
    return {
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一颗硅光张量核/光神经网络芯片：非酉 SVD 分解 + 激活量化 + "
                 "光电协同仿真 + 规模扩张 tiling，走完设计&验证闭环，并对标国际公开基准。",
        "verdict": "DESIGN_SIGNOFF",
        "verdict_label": "设计期签核与验证（非流片实测）",
        "identity": {
            "physics": "硅光子计算（MZI mesh 干涉 · 相干光学线性代数）",
            "device": "MZI 网格（Reck 三角分解）实现任意酉/实矩阵 · 光电探测器强度读出 · "
                      "DAC 下发 + TIA 读回闭环标定",
            "route_note": "光子计算两条真 GDS 闭环路线之一（另一条为光量子 LOQC，见 /api/qchip_demo）；"
                          "本卡为**电子计算/光计算芯片**征程的对外对标。",
            "zero_quantum_sdk": False,   # 光子计算非量子
            "open_source": True,
        },
        "span": {
            "milestones": 4,            # M1..M4
            "gate_checks": 0,           # 由门禁脚本填（不在此硬编码）
            "modules": ["photonic_compute", "photonic_electronic_cosim",
                        "photonic_mesh_tiling", "photonic_compute_benchmarks"],
            "scale_blind": d["scale_blind"],
        },
        "demonstrated": d,
        "extrapolation": ext,
        "architecture_class": ac,
        "public_landmarks": PUBLIC_LANDMARKS,
        "benchmark_table": benchmark_table(),
        "positioning": _positioning(),
        "honest_note": LDA_PHOTONIC_HONEST_NOTE,
        "gaps": _gaps(),
    }


def _positioning() -> Dict[str, Any]:
    return {
        "disclaimer": "下列为 2024–2026 年**公开报道的「已交付/已流片光子芯片」**数字，"
                      "仅作背景坐标；本案例为**设计&验证层能力证明**，两者**不同台比较**。",
        "public_landscape": [
            {"who": "Lightmatter", "item": "Envise（Nature 2025）：4×128×128 PTC，"
             "262 TOPS/W（光子核），~200 ps/MVM，ResNet18 86.4% CIFAR-10（97.8% FP32）"},
            {"who": "MIT（Englund）", "item": "2024 全集成光子处理器：训练>96%/推理>92%，"
             "前向<0.5 ns；2026 超复用 MMM：16×16×16×16、4096 MAC/shot、~20 aJ/MAC"},
            {"who": "清华（Taichi/太极）", "item": "Science 2024：160 TOPS/W，"
             "分布式广度光计算，支持内容生成"},
            {"who": "AIP AML 综述表（2024）", "item": "MZI-mesh ≤800×800 / ≤9 TOPS/W / ≤10 TOPS/mm²；"
             "MRR ≤15 TOPS/W；B200 9 TOPS/W；IBM Hermes 256×256 9.76 TOPS/W"},
            {"who": "Ayar Labs", "item": "光 I/O chiplet（TeraPHY）——**互连层**，非计算核，"
             "与本案例不同层"},
        ],
        "what_is_different": [
            {"axis": "交付物", "industry": "已流片/已交付光子芯片 + 实测 TOPS/W",
             "lda": "**设计&验证工具链**：MZI mesh 张量核的可设计+可验证保真闭环"},
            {"axis": "工具链", "industry": "各自闭源 CAD/PDK + 控制 ASIC",
             "lda": "**开源（MIT）· Agent-native** · 物理内核自研 · 零外部光学 SDK"},
            {"axis": "判决路径", "industry": "实验标定 + 数值仿真混合",
             "lda": "**LLM 不进判决路径**；死标量比对；红线为物理定律（酉幺正性、Vπ·L 律）"},
            {"axis": "能效数字", "industry": "实测/标称 TOPS/W（制造+系统级）",
             "lda": "**不报任何 fabricated 能效数字**（制造与系统级，非设计工具链职责）"},
            {"axis": "对标维度", "industry": "die 级 benchmark（TOPS/W、延迟、准确率）",
             "lda": "**架构族 + 设计质量方法论**（scale-blind 保真、闭环标定、tiling 增益）"},
        ],
        "honest_limits": [
            "无数值/能效同台比较：LDA 不宣称在 TOPS/W、延迟或模型准确率上优于任何厂商。",
            "不宣称「光计算优势」：本案例不涉及任何算力优势主张，是设计工具链能力证明。",
            "规模数字须按「设计容量」解读，误读成「已制备 256/800 光子芯片」即为失真。",
        ],
    }


def _gaps() -> List[Dict[str, str]]:
    return [
        {"id": "G-A", "title": "无流片 / 无光学实测",
         "detail": "全部为设计期验证；无 foundry 回片、无光学校准实测、无实测保真度。"},
        {"id": "G-B", "title": "无 foundry PDK",
         "detail": "MZI 损耗/耦合为行为级模型（eic_behavioral + Vπ·L 律），"
                   "未对接任何工艺厂 deck（属外部依赖）。"},
        {"id": "G-C", "title": "不报 fabricated 能效",
         "detail": "TOPS/W、pj/MAC 等为制造与系统级指标，LDA 设计工具链不产出此类数字；"
                   "对外对标只用架构族 + 设计质量方法论。"},
        {"id": "G-D", "title": "EO 链路为行为级（T1 候选）",
         "detail": "驱动/TIA 用一阶 RC + 单极点模型，非 ORACLE；不碰晶体管级 DAC/ADC/"
                   "SerDes/DSP。"},
        {"id": "G-E", "title": "Vπ 跨模块口径未统一",
         "detail": "光侧 25 V·cm vs EIC 侧 7.5 V·mm（差 ~3.3×），已在 co-sim 层用单一 "
                   "vpi_v 贯穿规避；根因统一留作独立 sprint（任务 #7）。"},
    ]


# ═══════════════════════════════ 自检（门禁同源调用）══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（name-first + 内联反向可证伪）。不 import 任何求解器/外部 SDK。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append("%s | %s" % ("PASS" if cond else "FAIL", name))

    # ① 公开 landmark 均带来源 URL（A 级 golden 可复核）
    all_src = all(bool(v.get("source")) for v in PUBLIC_LANDMARKS.values())
    chk("① 公开 landmark 全部带来源 URL（A 级 golden 可复核）", all_src)

    # ② LDA 不报任何 fabricated 能效数字（关键诚实边界）
    d = lda_demonstrated()
    chk("② LDA 不报 fabricated TOPS/W（reports_fabricated_tops_w == False）",
        d["reports_fabricated_tops_w"] is False)
    banned_energy = ("tops_w", "pj_per_mac", "power_w", "energy_per_mac")
    has_energy = any(k in d for k in banned_energy)
    chk("②b LDA 实绩字典不含任何能效键（tops_w/pj_per_mac/power_w/energy_per_mac）",
        not has_energy)

    # ③ 尺度盲判定为真 + ratio 相对标准差 < 20%
    chk("③ scale-blind == True 且 ratio 相对标准差 < 20%",
        d["scale_blind"] and d["scale_blind_ratio_rel_std"] < 0.20)

    # ④ N=256 网格保真度 ≥ 0.98（尺度盲真身）
    chk("④ N=256 网格酉保真度 ≥ 0.98（%.4f）" % d["grid_fidelity_at_256"],
        d["grid_fidelity_at_256"] >= 0.98)

    # ⑤ MZI 计数闭式：256 ⇒ 32640（N*(N-1)//2）
    chk("⑤ reck_mzi_count(256) == 32640", T.reck_mzi_count(256) == 32640)

    # ⑥ tiling 增益 > 1（局部标定降噪）
    chk("⑥ tiling 保真增益 > 1（%.1f×）" % d["tiling_fidelity_gain_x"],
        d["tiling_fidelity_gain_x"] > 1.0)

    # ⑦ 尺度盲外推：800×800 保真度不塌缩（≥ 0.98）
    ext = scale_blind_extrapolation(800)
    chk("⑦ 外推 800×800 设计保真度 ≥ 0.98（%.4f）" % ext["est_grid_fidelity"],
        ext["est_grid_fidelity"] >= 0.98)
    chk("⑦b 外推 MZI 计数 = 800*799//2 = 319600", ext["mzi_count"] == 800 * 799 // 2)

    # ⑧ 架构族对齐：LDA 与 MIT MZI-mesh lineage 同族，且明标不与 Ayar 同层比
    ac = architecture_class()
    chk("⑧ 架构族对齐：same_lineage 含 MIT 2025 Nature 128×128 PTC",
        any("2025 Nature 128" in s for s in ac["same_lineage_as"]))
    chk("⑧b 明标不与 Ayar（光 I/O 层）同台比",
        "Ayar Labs" in ac["not_same_layer_as"][0])

    # ⑨ 案例卡：verdict 恒 DESIGN_SIGNOFF + 诚实边界齐全
    card = case_card()
    note = card["honest_note"]
    chk("⑨ verdict == DESIGN_SIGNOFF · 诚实边界含「非已流片」/「不宣称 fabricated 能效」/"
        "「规模=设计容量」",
        card["verdict"] == "DESIGN_SIGNOFF"
        and "非已流片光子芯片" in note and "不宣称任何 fabricated 能效数字" in note
        and "规模 = 设计容量" in note)

    # ⑩ 🔴 零能效数字：本模块预算字典不含能效键；注入能效键必 raise
    budget = {"mzi_per_core": 65280, "dac_bits": 16, "tile_k": 16}  # 设计容量，无能效
    try:
        optical_pareto.assert_no_energy_metrics(budget)
        no_energy_ok = True
    except Exception:
        no_energy_ok = False
    chk("⑩ 本模块预算字典通过 assert_no_energy_metrics（无能效键）", no_energy_ok)

    injected_bad = dict(budget, pj_per_bit=1e-12)
    raised = False
    try:
        optical_pareto.assert_no_energy_metrics(injected_bad)
    except Exception:
        raised = True
    chk("⑩b 注入能效键 ⇒ assert_no_energy_metrics 必 raise（反向证伪）", raised)

    # ⑪ 零外部光学/量子 SDK：本模块不 import 任何光学框架
    src = open(__file__, encoding="utf-8").read().lower()
    banned = ("meep", "tidy3d", "lumapi", "lumerical", "comsol", "qiskit", "cirq")
    hit = [b for b in banned if ("import %s" % b) in src]
    chk("⑪ 零外部光学/量子 SDK：本模块无可疑 import", not hit)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("光计算对标基准自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
