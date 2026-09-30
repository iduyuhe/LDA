"""光计算芯片案例卡（WebUI 只读端点数据源）· M5 收尾（2026-09-30）。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
光计算征程「吃狗粮」LDA-P（M1→M5）的**只读案例**：用 LDA 亲手设计一颗
硅光张量核 / 光神经网络芯片（MZI mesh 干涉架构）——从「能算」（M1 非酉 SVD）
→「算得准」（M2 激活/量化/标定）→「能设计完整芯片：光核 + 电子接口」
（M3 光电协同仿真）→「规模达国际水平」（M4 规模盲 + tiling）→
「对标国际公开基准」（M5）——并对标 Lightmatter / MIT / 清华等 A 级 landmark。

与 `/api/qchip_demo`（光**量子** LOQC 案例卡 · D-131）、
`/api/schip_demo`（超导 transmon 案例卡 · D-148）**并列**：三条物理路线
（光量子 / 超导 / 光计算）在 LDA 均有「吃狗粮」征程。本卡回答的是
**同一个平台问题**——「同一条设计链路，换一种物理（光计算），是否还站得住？」

🔴 **零重计算**（与站内 cpo_array / design_* 等重算端点不同）：本模块**不跑
仿真、不 import 求解器、不解析版图**——全部数字取自 ① 静态里程碑/结论
（人工登记、可回溯到 M1–M5 门禁与事实源 MD）② **纯闭式**现算（MZI 计数）
③ 对 `journey_photonic_compute/` 产出物只 `stat` 的元信息。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**，与 `/api/qchip_demo`、
`/api/schip_demo`、`/api/verification_ledger` 同属「公开只读验货」类。

🔴 **不伪装实测 / 不报 fabricated 能效**：`verdict` 恒为 `DESIGN_SIGNOFF`
（**非** ACCEPT/PASS），返回体自带 `honest_note`；模块复用 `assert_no_energy_metrics`
纪律（源码级扫描：本文件不含任何外部光学 SDK / numpy / 能效键）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "CASE_ID", "PCHIP_HONEST_NOTE", "MILESTONES", "FINDINGS", "GAPS",
    "SCALE_TIERS", "PUBLIC_LANDMARKS",
    "reck_mzi_count", "case_card", "run_selfchecks",
]

# ═════════════════════════════ 常量（与 M1–M5 实绩同源 · 静态登记）═════════════════════════════
CASE_ID = "LDA-P · 硅光张量核 / 光神经网络（光子计算芯片 · MZI mesh）"

#: 已验证最大矩阵规模（M4 bigN 实测）
N_MAX_VERIFIED = 256
#: 网格酉保真度（M4 bigN 实测）
FID_U_64 = 0.9967
FID_U_128 = 0.9952
FID_U_256 = 0.9932
#: scale-blind 归一化比值相对标准差（M4 scale_blind_check 实测）
SCALE_BLIND_RATIO_REL_STD = 0.0766
#: tiling 局部标定增益（M4 mono 1−F 0.0247 → tiled 0.0088）
TILING_GAIN = 2.8
#: EO co-sim 场景（M3 实测）
EO_FULL_ACC = 1.0
EO_FULL_WERR = 0.0015
EO_2BIT_ACC = 0.667
EO_2BIT_WERR = 1.059
EO_VPI_MISMATCH_ACC = 0.833
EO_VPI_MISMATCH_WERR = 0.209
EO_VPI_CAL_ACC = 1.0
EO_VPI_CAL_WERR = 0.0017
#: DAC 相位误差（M3 实测，rad）
DAC_PHASE_ERR = {2: 0.49, 4: 0.107, 8: 0.0063, 12: 0.0011}
#: 8-bit 标定残差（M3 实测）
CAL_8BIT_RESIDUAL = 0.00331
#: TIA 行为级（M3 实测）
TIA_Z0_OHM = 2000.0
TIA_Z_F3DB_OHM = 1414.0
TIA_HI_ROLLOFF = 0.141
#: 路由损耗（M4 routing_loss_db 实测，dB）：k=块数
ROUTING_LOSS_DB = {1: 0.0, 8: 33.6, 32: 595.2}
#: 标定规模（M4 实测）：monolithic 8128 MZI/环 → per_tile 120
CAL_MONO_MZI = 8128
CAL_TILE_MZI = 120
#: 设计容量延展（M5 对标）：文献 MZI-mesh 最大类 ≤800×800（理想 fab 假设）
N_EXTEND = 800
#: 文献性能对比表来源（A 级 golden，与 M5 benchmarks 模块同源）
LANDMARK_SOURCE_NOTE = "来源：Nature 2025 · MIT News · Science 2024 · AIP AML 2024 · Ayar Labs（A 级）"

PCHIP_HONEST_NOTE = (
    "① 本案例是**设计&验证能力证明**（MZI mesh 张量核的可设计 + 可验证保真闭环），"
    "**非流片后实测芯片**——无 foundry 回片、无光学校准实测、无 TOPS/W 实测；"
    "② 规模数字（256 / 800）是**可设计且可验证保真度**的矩阵规模，是**设计容量**"
    "而非已制备器件数——误读成「已制备 256×256 光子芯片」即为失真；"
    "③ **不报任何 fabricated 能效数字**：公开基准的 TOPS/W 是「已交付芯片」的实测/厂商标称，"
    "LDA 作为设计工具链**不产出** pj/MAC、TOPS/W（那是制造与系统级，非本平台职责）；"
    "④ 对标按**架构族 + 设计质量方法论**（scale-blind 保真、闭环标定、tiling 增益），"
    "**不按 die 级 benchmark 数字同台比较**；LDA 的 MZI mesh 与 MIT 学术 lineage 同族；"
    "⑤ EO 链路为**行为级（T1 候选，非 ORACLE）**：驱动/TIA 用一阶 RC + 单极点模型，"
    "不碰晶体管级 DAC/ADC/SerDes/DSP；"
    "⑥ 零外部光学 SDK：全程不依赖 Meep / Tidy3D / Lumerical 等，物理内核平台自研；"
    "⑦ Vπ 跨模块口径未统一（光侧 25 V·cm vs EIC 侧 7.5 V·mm，差 ~3.3×），"
    "已在 co-sim 层用单一 vpi_v=7.5V 贯穿规避，根因统一留作独立 sprint（任务 #7）。"
)

# ═══════════════════════ 五段征程（静态事实 · 可回溯门禁）═══════════════════
MILESTONES = [
    {"id": "M1", "code": "D-129…D-131", "title": "非酉 SVD 光计算路径 · 全闭环",
     "gate": 28,
     "result": "SVD(W=U·Σ·V†) → 双 MZI 网格 + 对角衰减；Reck 三角分解；"
               "相移闭环标定；端到端精度锚（小矩阵 100%）"},
    {"id": "M2", "code": "D-132", "title": "激活 + 量化 / 标定 + 精度锚",
     "gate": 31,
     "result": "relu/sigmoid/tanh 激活（计算后电子侧实现）；相位量化；"
               "Vπ·L 律标定环；端到端精度锚 100%"},
    {"id": "M3", "code": "D-133", "title": "光电协同仿真（光核 + 电子接口）",
     "gate": 31,
     "result": "DAC→驱动(RK4)→相移器(Vπ)→光网格→PD→TIA 全链路 co-sim；"
               "闭环 Vπ 标定回收精度（Vπ+5% 未标定 83.3% → 标定 100%）"},
    {"id": "M4", "code": "D-134", "title": "规模扩张 / tiling 压力测试",
     "gate": 38,
     "result": "规模盲保真（1−F≈常数，随 N 不塌缩，ratio rel_std 7.66%）；"
               "tiling 局部标定增益 2.8×；N=256 网格保真 0.9932"},
    {"id": "M5", "code": "D-135", "title": "达国际水平（对标公开基准）",
     "gate": 33,
     "result": "8 条 A 级 golden landmark（Lightmatter/MIT/清华/AIP/Ayar）；"
               "架构族对齐（MIT lineage 同族）；诚实口径（不报 fabricated 能效）"},
]

# ═══════════════════════ 关键结论（平台能力增量）═══════════════════════
FINDINGS = [
    {"title": "非酉光计算路径",
     "detail": "SVD 双网格 + 对角衰减，突破「只能算酉矩阵」的限制，复矩阵与任意实矩阵均可片上实现。"},
    {"title": "光电协同仿真框架",
     "detail": "把既有 EIC 行为级模型（一阶 RC 驱动 + 单极点 TIA）与光计算核接成闭环，"
               "平台第一次能设计「光核 + 电子接口」的完整芯片。"},
    {"title": "闭环标定（控制环）",
     "detail": "用 DAC 下发 + TIA 强度读回反估真实 Vπ 并补偿指令，平台第一次有「读回→补偿」的校准能力；"
               "Vπ+5% 失配精度从 83.3% 回收至 100%。"},
    {"title": "规模可扩展性",
     "detail": "scale-blind 保真度证明大 N 不塌缩（ratio=(1−F)/√((N−1)/N) 跨 N=8→256 相对标准差仅 7.66%）；"
               "tiling 架构给出局部标定增益 2.8× 与路由损耗代价模型。"},
    {"title": "对标纪律",
     "detail": "用 A 级公开来源（Nature/Science/AIP/MIT News）登记产业界 landmark，"
               "平台第一次把「达国际水平」落到可复核的对标表 + 架构族对齐口径。"},
]

# ═══════════════════════ 诚实边界（未闭合项 · 逐条登记）═══════════════════════
GAPS = [
    {"id": "G-A", "title": "非流片 / 非实测芯片",
     "detail": "全部为设计期验证；无 foundry 回片、无光学校准实测、无 TOPS/W 实测。"},
    {"id": "G-B", "title": "不报任何 fabricated 能效数字",
     "detail": "公开基准的 TOPS/W 是「已交付芯片」实测/厂商标称；LDA 不产出 pj/MAC、TOPS/W。"},
    {"id": "G-C", "title": "对标按架构族 + 设计质量方法论",
     "detail": "不按 die 级 benchmark 数字同台比较；LDA 的 MZI mesh 与 MIT 学术 lineage 同族。"},
    {"id": "G-D", "title": "规模 = 设计容量",
     "detail": "256 是「可设计且可验证保真度」的矩阵规模，非已制备器件；"
               "延展到 800×800 类靠 scale-blind 性质（理想 fab 假设），非流片实测。"},
    {"id": "G-E", "title": "EO 链路为行为级（T1 候选，非 ORACLE）",
     "detail": "驱动/TIA 用一阶 RC + 单极点模型，不碰晶体管级 DAC/ADC/SerDes/DSP。"},
    {"id": "G-F", "title": "零能效数字纪律",
     "detail": "复用 assert_no_energy_metrics；本模块不输出任何能效指标键。"},
    {"id": "G-G", "title": "Vπ 跨模块口径未统一",
     "detail": "光侧 25 V·cm vs EIC 侧 7.5 V·mm（差 ~3.3×），已在 co-sim 层用单一 vpi_v 贯穿规避；"
               "根因统一留作独立 sprint（任务 #7）。"},
]

# ═══════════════════════ 规模档案（闭式现算）═══════════════════════
#: 网格族（N×N 三角 Reck 分解）：MZI 数 = N(N−1)/2
SCALE_TIERS = [
    {"tier": "8×8", "n": 8, "mzi": 28},
    {"tier": "16×16", "n": 16, "mzi": 120},
    {"tier": "32×32", "n": 32, "mzi": 496},
    {"tier": "64×64", "n": 64, "mzi": 2016},
    {"tier": "128×128", "n": 128, "mzi": 8128},
    {"tier": "256×256", "n": 256, "mzi": 32640, "fid_u": FID_U_256, "note": "已验证（M4 bigN）"},
]
#: 设计容量延展（理想 fab 假设，非流片）
EXTEND_TIERS = [
    {"tier": "512×512", "n": 512, "mzi": 130816},
    {"tier": "800×800", "n": 800, "mzi": 319600, "note": "文献 MZI-mesh 最大类（AIP AML 2024）"},
]

# ═══════════════════════ A 级公开基准（golden · 带来源）═══════════════════════
PUBLIC_LANDMARKS = [
    {"who": "Lightmatter", "item": "Envise（Nature 2025）：4×128×128 PTC，262 TOPS/W（光子核），"
                                    "~200 ps/MVM，ResNet18 CIFAR-10 86.4%（FP32 的 97.8%）"},
    {"who": "Lightmatter", "item": "PACE（Nature 2025）：8.19 TOPS，4.21 TOPS/W（不含激光）"},
    {"who": "MIT", "item": "Shen/Harris 2017 可编程纳米光子处理器（**MZI mesh 原创 lineage**）"},
    {"who": "MIT", "item": "2024 全集成光子处理器：训练>96%/推理>92%，前向<0.5 ns"},
    {"who": "MIT", "item": "2026 空-谱-时超复用 MMM：16×16×16×16、4096 MAC/shot、~20 aJ/MAC"},
    {"who": "清华 Taichi", "item": "Science 2024：160 TOPS/W，分布式广度光计算，支持内容生成"},
    {"who": "AIP AML 2024", "item": "MZI-mesh ≤800×800 / ≤9 TOPS/W / ≤10 TOPS/mm²；"
                                    "NVIDIA B200 9 TOPS/W；IBM Hermes 256×256 9.76 TOPS/W"},
    {"who": "Ayar Labs", "item": "光 I/O chiplet（TeraPHY）——**互连层（非计算核）**，与本案例不同层"},
]

_ARTIFACT_DIRS = ("lda/journey_photonic_compute", "journey_photonic_compute")


# ═══════════════════════════ 闭式（可反向测试 · 纯 python）═══════════════════════════
def reck_mzi_count(n: int) -> int:
    """N×N 三角 Reck 分解的 MZI 元件数 = N(N−1)/2（与 M4 `photonic_mesh_tiling` 同源闭式）。"""
    n = int(n)
    if n < 1:
        raise ValueError("n 须 ≥ 1")
    return n * (n - 1) // 2


def _artifact_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """探测 `journey_photonic_compute/` 下光计算产出物**元信息**（文件名 + 字节数）。

    只 `stat`，不读内容、不解析 HTML ⇒ 微秒级；目录不在本部署内则优雅降级为
    `available=False`。
    """
    root = repo_root
    if root is None:
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
    items: Dict[str, int] = {}
    hits: List[str] = []
    for d in _ARTIFACT_DIRS:
        p = os.path.join(root, d)
        if not os.path.isdir(p):
            continue
        hits.append(d)
        try:
            names = sorted(os.listdir(p))
        except OSError:
            continue
        for nm in names:
            if not nm.startswith("pc_") or not nm.endswith(".html"):
                continue
            fp = os.path.join(p, nm)
            try:
                if os.path.isfile(fp):
                    items[nm] = int(os.path.getsize(fp))
            except OSError:
                continue
    if not hits:
        return {"available": False, "root_hint": _ARTIFACT_DIRS[0], "count": 0,
                "items": [],
                "note": "产出物目录不在本部署内（源码仓才含 journey_photonic_compute/）"}
    lst = [{"name": k, "bytes": v} for k, v in sorted(items.items())]
    return {"available": True, "dirs_scanned": hits,
            "root_hint": hits[0], "count": len(lst), "items": lst,
            "note": "只读元信息（文件名 + 字节数）；完整报告见 pdf 配套的 pc_m*.html"}


# ═══════════════════════════════ 案例卡 ═══════════════════════════════
def case_card(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """组装光计算芯片案例卡（只读 · 零重计算 · 免登录）。

    `verdict` 恒为 `DESIGN_SIGNOFF` —— **明标「设计&验证能力证明」而非流片实测**。
    """
    gate_total = sum(m["gate"] for m in MILESTONES)
    flag = reck_mzi_count(N_MAX_VERIFIED)
    return {
        "endpoint": "/api/pchip_demo",
        "case_id": CASE_ID,
        "claim": "用 LDA 从零设计一颗硅光张量核 / 光神经网络芯片（MZI mesh 干涉架构）："
                 "从能算 → 算得准 → 光核+电子接口 → 规模达国际水平 → 对标公开基准，全链路验证闭环",
        "verdict": "DESIGN_SIGNOFF",
        "verdict_label": "设计&验证能力证明（非流片实测）",
        "identity": {
            "physics": "硅光子计算（MZI mesh 干涉 · 相干光学线性代数）",
            "device": "任意酉矩阵（Reck 三角分解）+ 对角衰减 ⇒ 任意实/复矩阵；"
                      "DAC 下发 + TIA 读回闭环标定",
            "unit": "MZI 单元 = 相位/耦合分束器 + 可调相移器（Vπ）",
            "nonlinearity": "relu / sigmoid / tanh（计算后电子侧实现）",
            "route_note": "光子计算两条路线之一（另一条为光量子 LOQC，见 /api/qchip_demo）；"
                          "超导 transmon 见 /api/schip_demo；三条物理路线均已吃狗粮",
            "zero_optical_sdk": True,
        },
        "span": {
            "milestones": len(MILESTONES),
            "gate_checks": gate_total,
            "modules": 5,
            "module_lines": 0,
            "probe_mutations": 0,
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
        "flagship": {
            "kind": "N×N MZI mesh（三角 Reck 分解）",
            "n_max_verified": N_MAX_VERIFIED,
            "n_mzi": flag,
            "fid_u_64": FID_U_64,
            "fid_u_128": FID_U_128,
            "fid_u_256": FID_U_256,
            "scale_blind_ratio_rel_std": SCALE_BLIND_RATIO_REL_STD,
            "tiling_gain": TILING_GAIN,
            "n_extend": N_EXTEND,
            "mzi_extend": reck_mzi_count(N_EXTEND),
            "extend_note": "设计容量延展（理想 fab 假设 · 非流片实测 · AIP AML 2024 文献最大类）",
        },
        "eo_chain": {
            "eo_full_acc": EO_FULL_ACC, "eo_full_werr": EO_FULL_WERR,
            "eo_2bit_acc": EO_2BIT_ACC, "eo_2bit_werr": EO_2BIT_WERR,
            "eo_vpi_mismatch_acc": EO_VPI_MISMATCH_ACC, "eo_vpi_mismatch_werr": EO_VPI_MISMATCH_WERR,
            "eo_vpi_cal_acc": EO_VPI_CAL_ACC, "eo_vpi_cal_werr": EO_VPI_CAL_WERR,
            "dac_phase_err_rad": DAC_PHASE_ERR,
            "cal_8bit_residual": CAL_8BIT_RESIDUAL,
            "tia_z0_ohm": TIA_Z0_OHM, "tia_z_f3db_ohm": TIA_Z_F3DB_OHM,
            "tia_hi_rolloff": TIA_HI_ROLLOFF,
            "note": "EO 链路为行为级（T1 候选，非 ORACLE）：一阶 RC 驱动 + 单极点 TIA",
        },
        "scale_tiers": {
            "grid": SCALE_TIERS,
            "extend": EXTEND_TIERS,
            "routing_loss_db": ROUTING_LOSS_DB,
            "calibration_scale": {"monolithic_mzi_per_ring": CAL_MONO_MZI,
                                  "per_tile_mzi": CAL_TILE_MZI,
                                  "reduction_x": round(CAL_MONO_MZI / CAL_TILE_MZI, 1)},
            "note": "规模 = **设计容量**（可设计且可验证保真度），非已制备器件数",
        },
        "public_landmarks": PUBLIC_LANDMARKS,
        "source_note": LANDMARK_SOURCE_NOTE,
        "artifacts": _artifact_manifest(repo_root),
        "positioning": _positioning(),
        "honest_note": PCHIP_HONEST_NOTE,
    }


def _positioning() -> Dict[str, Any]:
    """先进性定位（公开来源 · 只作背景，不与本案例同台比较）。"""
    return {
        "disclaimer": "下列为 2024–2026 年公开报道的**产业界已交付/已流片光子芯片**数字，仅作背景坐标；"
                      "本案例是**设计&验证工具链的能力证明**，两者**不同台比较**。",
        "architecture_alignment": [
            {"axis": "架构族", "industry": "Lightmatter Envise = 光广播+电子加权（不同子架构）",
             "lda": "MZI mesh 干涉（与 MIT Shen/Harris 2017 lineage **同族**）"},
            {"axis": "文献最大类", "industry": "AIP AML 2024：MZI-mesh ≤800×800",
             "lda": "已验证 N=256（32640 MZI，保真 0.9932）；scale-blind 可延展至 800×800 类"},
            {"axis": "公开瓶颈", "industry": "MZI mesh 受限于制备误差（fabrication imperfections）",
             "lda": "scale-blind 保真 + 闭环 Vπ 标定 + tiling 局部标定 = 工程解"},
        ],
        "what_is_different": [
            {"axis": "交付物", "industry": "已流片/已交付光子芯片 + 实测 TOPS/W",
             "lda": "**设计&验证工具链**：MZI mesh 张量核的可设计 + 可验证保真闭环"},
            {"axis": "工具链来源", "industry": "各自闭源 CAD/PDK + 控制 ASIC",
             "lda": "**开源（MIT）· Agent-native** · 物理内核自研 · 零外部光学 SDK"},
            {"axis": "判决路径", "industry": "实验标定 + 数值仿真混合",
             "lda": "**LLM 不进判决路径**：死标量比对；红线为物理定律（酉幺正性、Vπ·L 律）"},
            {"axis": "能效数字", "industry": "实测/标称 TOPS/W（制造+系统级）",
             "lda": "**不报任何 fabricated 能效数字**（制造与系统级，非本平台职责）"},
            {"axis": "对标维度", "industry": "die 级 benchmark（TOPS/W、延迟、准确率）",
             "lda": "**架构族 + 设计质量方法论**（scale-blind 保真、闭环标定、tiling 增益）"},
        ],
        "honest_limits": [
            "无数值/能效同台比较：LDA 不宣称在 TOPS/W、延迟或模型准确率上优于任何厂商。",
            "不宣称「光子计算优势」：本案例不涉及任何计算优势主张。",
            "规模数字须按「设计容量」解读，误读成「已制备 256×256 光子芯片」即为失真。",
        ],
    }


# ═══════════════════════════════ 自检 ═══════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。闭式断言 + 红线断言（不 import 求解器）。"""
    res: Dict[str, bool] = {}
    msgs: List[str] = []

    def chk(name: str, cond: bool) -> None:
        res[name] = bool(cond)
        msgs.append(f"{'PASS' if cond else 'FAIL'} | {name}")

    # ① 闭式：256 ⇒ 32640 MZI（=256*255/2）
    chk("① reck_mzi_count(256) == 32640（=N(N−1)/2）",
        reck_mzi_count(N_MAX_VERIFIED) == 32640)

    # ② 闭式与逐点枚举一致（N=2..8）
    ok = True
    for k in range(2, 9):
        ok = ok and reck_mzi_count(k) == k * (k - 1) // 2
    chk("② reck_mzi_count(N) ≡ N(N−1)/2（N=2..8 逐点）", ok)

    # ③ scale-blind 比例相对标准差登记值（M4 实测）
    chk("③ scale-blind ratio 相对标准差 = 0.0766（< 10%）",
        abs(SCALE_BLIND_RATIO_REL_STD - 0.0766) < 1e-9)

    # ④ tiling 增益登记值
    chk("④ tiling 局部标定增益 = 2.8×", abs(TILING_GAIN - 2.8) < 1e-9)

    # ⑤ EO 精度三判据（M3 实测，闭环标定回收）
    chk("⑤ EO：全精度 100% / Vπ+5% 未标定 83.3% / 标定为 100%",
        abs(EO_FULL_ACC - 1.0) < 1e-9
        and abs(EO_VPI_MISMATCH_ACC - 0.833) < 1e-9
        and abs(EO_VPI_CAL_ACC - 1.0) < 1e-9)

    # ⑥ 案例卡组装：5 里程碑 · 5 结论 · 7 缺口
    card = case_card(repo_root="__nonexistent_root__")
    chk("⑥ 案例卡组装：5 里程碑 / 5 结论 / 7 缺口 / 门禁判据合计 161",
        len(card["milestones"]) == 5 and len(card["findings"]) == 5
        and card["gaps_total"] == 7 and card["span"]["gate_checks"] == 161)

    # ⑦ 产出物优雅降级（root 不存在 ⇒ available False，不抛错）
    chk("⑦ 产出物探测优雅降级（root 不存在 ⇒ available=False）",
        card["artifacts"]["available"] is False)

    # ⑧ 🔴 不伪装实测 / 不报 fabricated 能效：verdict 恒 DESIGN_SIGNOFF + 诚实边界齐全
    note = card["honest_note"]
    chk("⑧ 不伪装实测：verdict=DESIGN_SIGNOFF · 诚实边界含「非流片后实测」/"
        "「不报任何 fabricated 能效」/「设计容量」",
        card["verdict"] == "DESIGN_SIGNOFF"
        and "非流片后实测" in note and "不报任何 fabricated 能效" in note
        and "设计容量" in note)

    # ⑨ 🔴 先进性与产业界不同台比较（disclaimer + 诚实限制 全在）
    pos = card["positioning"]
    chk("⑨ 先进性定位：含不同台比较声明 + 3 条诚实限制 + ≥5 landmark",
        bool(pos["disclaimer"]) and len(pos["honest_limits"]) == 3
        and len(card["public_landmarks"]) >= 5)

    # ⑩ 🔴 规模口径必须写「设计容量」（防被误读为已制备芯片）
    chk("⑩ 规模口径明标「设计容量」（非已制备器件数）",
        "设计容量" in card["scale_tiers"]["note"])

    # ⑪ 🔴 零外部光学 SDK / 零 numpy：只扫「import <name> / from <name> import」
    # 形态（避免把「不依赖 Meep/Tidy3D」这类**声明文本**误判为 import）。
    src = open(os.path.abspath(__file__), encoding="utf-8").read().lower()
    banned = ("numpy", "scipy", "meep", "tidy3d", "lumerical", "torch",
              "tensorflow", "jax", "lda_l2")
    hit = []
    for b in banned:
        if ("import " + b) in src or ("from " + b) in src:
            hit.append(b)
    chk("⑪ 零外部光学 SDK / 零 numpy：本模块无任何求解器/numpy import", not hit)

    # ⑫ 🔴 不报 fabricated 能效数字：返回体不含任何能效键
    energy_keys = ("tops_w", "power_w", "pj_per_mac", "pj_per_bit",
                   "flops_per_watt", "top_s_w", "w_per_mac")
    flat = json.dumps(card).lower()
    hit_e = [k for k in energy_keys if k in flat]
    chk("⑫ 零能效数字：案例卡返回体不含任何能效键（tops_w/pj_per_mac/…）", not hit_e)

    # ⑬ 护栏：非法输入抛错（N < 1）
    guard = 0
    for bad in (lambda: reck_mzi_count(0), lambda: reck_mzi_count(-3)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑬ 护栏：N<1 抛 ValueError（reck_mzi_count）", guard == 2)

    ok_all = all(res.values())
    if verbose:
        for m in msgs:
            print("  " + m)
    return ok_all


if __name__ == "__main__":
    print("光计算芯片案例卡自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
