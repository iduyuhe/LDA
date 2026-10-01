# -*- coding: utf-8 -*-
"""LDA WebUI · 光子/模拟混合 AI 推理加速器案例卡（阶段 4 · L6 参考设计 · W4-2）。

============================================================================
A 档接入（对齐 qchip/schip/pchip 案例卡体例）
----------------------------------------------------------------------------
把阶段 4 的跨域拼接成果在 UI 中以**只读案例**呈现：光子 MZI 网格（第 1 层 ·
实正交约束 + 移相器相位量化）+ 电域 ReLU + E3 模拟交叉阵列（第 2 层 · DAC/ADC
量化）= 端到端 2 层 MLP 分类推理加速器，vs 全精度数字 golden 逐项误差归因。

🔴 只读与缓存纪律：结果为**固定种子确定性现算**（纯 numpy · 零外部依赖 ·
不跑 P&R / 不跑 FDTD），首次调用后按配置键**模块级缓存**（同配置秒回）。
不进 HEAVY_POST_PATHS、不要求登录（与 qchip/schip/pchip 同属「公开只读验货」类）。

🔴 不伪装实测：`verdict` 恒为 `DESIGN_BUDGET`（非 ACCEPT/PASS）——精度数字是
**合成任务上的链路行为验证**，非流片后实测；**不报 TOPS/TOPS-W/fJ/op**。
"""
from __future__ import annotations

CASE_ID = "LDA-A · 光子/模拟混合 AI 推理加速器（L6 参考设计 · 阶段 4）"

_CACHE: dict = {}


def _fmt_pct(v: float) -> str:
    return f"{v * 100.0:.2f}%"


def case_card(phase_bits: int = 6, dac_bits: int = 8, adc_bits: int = 8,
              use_cache: bool = True) -> dict:
    """组装案例卡（确定性现算 + 模块级缓存）。phase/dac/adc 各位数为可调设计点。"""
    key = (int(phase_bits), int(dac_bits), int(adc_bits))
    if use_cache and key in _CACHE:
        return _CACHE[key]

    from lda_l2.ai_accelerator_ref import (
        ACCELERATOR_REF_DISCLOSURE,
        run_reference,
    )

    rep = run_reference(phase_bits=phase_bits, dac_bits=dac_bits, adc_bits=adc_bits)
    ea = rep["error_attribution"]
    ms = rep["mesh_stats"]
    cfg = rep["config"]
    ps = rep["phase_bits_sweep_e1"]
    us = rep["unit_bits_sweep_e2_iso"]

    card = {
        "endpoint": "/api/accel_demo",
        "case_id": CASE_ID,
        "claim": ("光子 MZI 网格 × 模拟交叉阵列可以拼成一台端到端 AI 推理加速器："
                  "与全精度数字 golden 比对精度落差逐点可归因、随位数可收敛"),
        "identity": {
            "layer1_photonic": "实正交 O1（8×8）→ Reck 三角 MZI 网格（相邻模耦合 · 可主权 P&R）"
                               "→ 移相器相位量化 → 重构矩阵真实参与推理",
            "nonlinearity": "ReLU 在电域（光子网格对经典光只做线性酉映射 —— 硬边界）",
            "layer2_electronic": "E3 模拟交叉阵列数据通路：DAC 量化 → CrossbarMVM 参考列法"
                                 " → ADC 量化",
            "task": "4 类 4 维合成高斯团分类（固定种子 20261002 · 确定性 · 256 样本 3:1 切分）",
            "route_note": ("承接 GPU 命题改写：LDA 的 L6 定位是「模拟/光子计算加速器」的"
                           "设计平台（非数字 GPU——无数字 RTL/PDK 不可行也不该做）"),
        },
        "requested": {"phase_bits": cfg["phase_bits"], "dac_bits": cfg["dac_bits"],
                      "adc_bits": cfg["adc_bits"]},
        "accuracy": {
            "train_acc_golden": rep["train_acc_golden"],
            "test_acc_golden": rep["test_acc_golden"],
            "test_acc_hybrid": rep["test_acc_hybrid"],
            "acc_drop_points": rep["acc_drop_points"],
            "n_train": rep["n_train"], "n_test": rep["n_test"],
        },
        "error_attribution": {
            "e1_photonic_rel_max": ea["e1_photonic_rel_max"],
            "e2_crossbar_iso_rel_max": ea["e2_crossbar_iso_rel_max"],
            "e2_e2e_rel_max": ea["e2_e2e_rel_max"],
            "note": "e1=光子层（相位量化主导）；e2_iso=golden 激活直接进量化交叉阵列"
                    "（隔离第 2 层自身误差）；e2_e2e=端到端",
        },
        "phase_bits_sweep_e1": ps,
        "unit_bits_sweep_e2_iso": us,
        "mesh_stats": {
            "n_mzi": ms["n_mzi"], "per_mode_optical_depth": ms["per_mode_optical_depth"],
            "per_mzi_loss_db": ms["per_mzi_loss_db"], "per_mode_db": ms["per_mode_db"],
            "total_db": ms["total_db"],
            "crossing_loss_included_in_per_mode": ms["crossing_loss_included_in_per_mode"],
            "basis_note": ms["basis_note"],
        },
        "mesh_fidelity": {
            "unquantized": rep["mesh_fidelity_unquantized"],
            "at_design_point": rep["mesh_fidelity_to_O1_at_design_point"],
        },
        "disclosure": ACCELERATOR_REF_DISCLOSURE,
        "milestones": [
            {"id": "A1", "label": "积木就位",
             "detail": "光子：MZI 网格 Reck 三角分解 + 每模损耗双口径（LOQC 线）· "
                       "编译前端非酉→最近酉投影（L2 编译器）；电子：E3 模拟 MVM 数据通路"
                       "（DAC→参考列交叉阵列→ADC + ReLU + tiling）"},
            {"id": "A2", "label": "W4-1 跨域拼接",
             "detail": "第 1 层训练为实正交（极分解投影约束）→ 光子网格物理实现；"
                       "ReLU 电域；第 2 层走模拟交叉阵列——端到端 2 层 MLP 分类器"},
            {"id": "A3", "label": "行为验证与误差归因",
             "detail": "golden 0.984375 = 混合 0.984375（设计点落差 0 点）；"
                       "e1=1.460e-2 / e2_iso=2.042e-2 / e2_e2e=2.396e-2，"
                       "相位 2→8 bit 与 DAC/ADC 3→8 bit 各自下降"},
            {"id": "A4", "label": "首跑抓出真 bug 并修复",
             "detail": "reck ops 的 φ 实际域 (−π, 3π)，直接钳位量化破坏网格"
                       "（保真度跌至 ~1/N 随机酉期望 0.112）——先 mod 2π 环绕再量化，"
                       "保真恢复 0.9966"},
            {"id": "A5", "label": "门禁 + 案例卡 + 前端（W4-2）",
             "detail": "run_ai_accel_ref_smoke（14 自检 + 3 突变探针）入 CI core 261；"
                       "本卡 + 前端面板 + API 参考对齐"},
        ],
        "findings": [
            {"title": "混合端到端与数字 golden 精度持平（设计点）",
             "detail": "6bit 相位 + 8bit DAC/ADC 下测试精度落差 0 点——量化误差"
                       "（e1≈1.5e-2 / e2_iso≈2.0e-2）在该任务分辨率下不翻转任何样本"},
            {"title": "误差源可分离、可收敛",
             "detail": "相位 2→8 bit：e1 2.146→0.003；DAC/ADC 3→8 bit：e2_iso "
                       "0.718→0.020——两位数轴独立扫频，给设计者真实的位宽-精度权衡曲线"},
            {"title": "相位环绕：域假设错误会被量化器静默放大",
             "detail": "φ 域 (−π,3π) 直接钳位 ⇒ 矩阵几乎随机化（保真 0.112）——"
                       "量化前必须 mod 2π 环绕；该 bug 首跑即被保真度对照锚抓住"},
            {"title": "光子层容量受正交约束是物理事实而非缺陷",
             "detail": "训练在约束内完成 ⇒ 报出的 0.984375 是物理可达精度；"
                       "任意权重矩阵需走 SVD 双网格 + 对角衰减路线（见 pchip 卡）"},
        ],
        "gaps": [
            {"id": "G-A1", "closed": False,
             "title": "数据集为固定种子合成高斯团",
             "detail": "精度只证端到端链路行为正确；真实任务（MNIST/语音等）需数据管道与"
                       "训练基础设施，不在本参考设计范围"},
            {"id": "G-A2", "closed": False,
             "title": "移相器量化为一阶均匀相位模型",
             "detail": "不含校准残差 / 热漂移 / 串扰 / 相位噪声；校准闭环见 E8/E16 纪律"},
            {"id": "G-A3", "closed": False,
             "title": "插入损耗只进功率预算、不进精度",
             "detail": "均匀衰减可被差分检测/归一化消除的论证未建模；per_mode 31.2 dB / "
                       "total 67.2 dB 为设计预算口径（非实测）"},
            {"id": "G-A4", "closed": False,
             "title": "电路级模型 · 无 PDK · 不报 TOPS",
             "detail": "继承 E3/E19 红线：无 foundry 数据 ⇒ 无能效宣称资格；"
                       "规模与能效外推属 T2 锁死区"},
            {"id": "G-A5", "closed": False,
             "title": "规模止步于 N=8 网格 × 4×8 交叉阵列",
             "detail": "更大规模需 tiling/多核（E9/E18 纪律）与 WDM/时间复用（光子线），"
                       "本卡为单核行为验证参考设计"},
        ],
        "gaps_closed": 0,
        "gaps_total": 5,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计行为验证口径（合成任务 · 确定性现算 · 非流片实测）",
        "honest_note": ("🔴 本卡为只读案例：数字由固定种子确定性现算（零重计算缓存秒回 · "
                        "免登录 · 不跑 P&R/FDTD）；精度为合成任务上的链路行为验证，"
                        "非流片后实测；不报 TOPS/TOPS-W/fJ/op；判决位由死标量给出，"
                        "LLM 不进判决路径。"),
    }
    if use_cache:
        _CACHE[key] = card
    return card


def run_selfchecks() -> bool:
    """模块自检（门禁同源）：卡结构完备 + 判决诚实 + 关键数字与模块自检同源。"""
    c = case_card(use_cache=False)
    need = ["case_id", "claim", "identity", "accuracy", "error_attribution",
            "phase_bits_sweep_e1", "unit_bits_sweep_e2_iso", "mesh_stats",
            "mesh_fidelity", "milestones", "findings", "gaps", "verdict",
            "honest_note"]
    if any(k not in c for k in need):
        return False
    if c["verdict"] != "DESIGN_BUDGET":
        return False
    # 🔴 扫描只覆盖主张性字段（claim/identity/accuracy）——honest_note / gaps 里的
    # 「不报 TOPS」是**否定表述**，扫进去会恒假（血案 #17 同型，勿再踩）。
    blob = repr(c["claim"]) + repr(c["identity"]) + repr(c["accuracy"])
    if "TOPS" in blob or "实测" in blob:
        return False
    a = c["accuracy"]
    if not (0.0 <= a["test_acc_golden"] <= 1.0 and a["test_acc_golden"] > 0.8):
        return False
    if c["gaps_total"] != len(c["gaps"]):
        return False
    return c["mesh_fidelity"]["unquantized"] >= 1.0 - 1e-9
