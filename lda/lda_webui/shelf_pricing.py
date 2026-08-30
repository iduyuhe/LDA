#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 LDA 创新超市货架三档定价（D2 落地 · 2026-08-30）。

分档规则（三维，可解释、可复现，不是拍脑袋）：
  ① 开源可替代性（第一判据）：核心功能是否能由 gdsfactory 现成标准件
     （straight/bend/mmi/coupler/grating_coupler/ring/mzi/y_splitter/taper）
     直接拼出 —— 能 → 基础档；需组合设计 → 标准档；生态无现成 → 高端档。
     判据来源：`lda/lda_l1/gdsfactory_bridge.py:26-38` GF_TO_LDA_KIND（项目自身桥接映射）
  ② 技术复杂度：composition 基元数 + 是否系统级（多通道/多物理场/异质集成）
  ③ 客户价值：对应产品市场规模与单价（成熟普惠 → 低；前沿稀缺 → 高）

市场锚（2026-08-30 调研）：
  - 国际 Design House 设计服务：标准 cell €5500 起、定制 €11000 起、评审 €495 起
    （VLC Photonics / Bright Photonics / Epiphany，JePPIX 平台公开报价）
  - 流片：国内无源 MPW ¥6-8 万、90nm 有源 ¥13 万、12 吋有源 ¥19 万
  - LDA 定价 ¥599/1999/4999 属「商业参考设计」区间，为国际设计服务的 1/10 ~ 1/100
    （性质差异：LDA 交付「仿真预期·未流片」预设计 + 死锚报告，非流片级设计服务）
  - ¥4999 卡中国企业采购免招标阈值线（多数企业 5000 元以下简易采购），降低采购摩擦
"""
from __future__ import annotations

# ---- 三档价格 ----
PRICE_TIERS = {"basic": 599.0, "standard": 1999.0, "premium": 4999.0}

# ---- 基础档 ¥599：gdsfactory 现成标准件可直接拼出 / 成熟普惠 / 教学科研常用 ----
TIER_BASIC = [
    "IM-FTTH-PLC8",        # 1×8 PLC 分光 = Y 分支级联（y_splitter 现成）
    "IM-FTTH-PLC16",       # 1×16 PLC 分光
    "IM-SPLITTER-TREE",    # 1×N 功分树
    "IM-GRATING-COUPLE",   # 光栅耦合阵列（grating_coupler 现成）
    "IM-MRR-FILTER",       # 微环滤波（ring 现成）
    "IM-SENSE-RING",       # 微环折射率传感（ring）
    "IM-SENS-MZI",         # MZI 干涉传感（mzi 现成）
    "IM-BIOSENSE",         # 环形生物传感（ring）
    "IM-GAS-SENSE",        # 波导气体/吸收光谱传感（straight 螺旋）
    "IM-VOA",              # 可变光衰减器（MZI/热调标准结构）
    "IM-POL-ROTATOR",      # 片上偏振旋转器（标准无源件）
    "IM-MDM-MUX",          # 模分复用器（标准无源）
    "IM-CWDM4-SHELF",      # 100G CWDM4（2014 成熟标准，替代方案多）
    "IM-PSM4-SHELF",       # 100G PSM4（成熟标准）
    "IM-100G-LR4",         # 100G LR4（成熟标准）
]

# ---- 标准档 ¥1999：需工程设计 know-how 的子系统（生态有零件无成品）----
TIER_STANDARD = [
    "IM-400G-DR4",         # 400G 主流，需系统设计
    "IM-FR4-SHELF",        # 400G FR4
    "IM-LPO-112G",         # LPO 线性直驱（新兴但渐成标准）
    "IM-RING-MOD",         # 微环调制器（需调制效率/热调设计）
    "IM-MZI-MOD",          # MZM 调制器
    "IM-PSR",              # 偏振分束旋转器
    "IM-AWG-DEMUX",        # AWG（有标准方法但需设计迭代）
    "IM-WDM-8CH-1D",       # 8 通道解复用
    "IM-OSW-1X8",          # 1×8 可重构光开关
    "IM-COHERENT-RX",      # 相干接收 90° 混频
    "IM-LIDAR-TX",         # FMCW 激光雷达发射
    "IM-LIDAR-RX",         # FMCW 相干接收
    "IM-LASER-INT",        # 片上激光源集成（异质集成黑箱源）
    "IM-MCF-FANOUT",       # 多芯光纤扇出
    "IM-ONCHIP-SPECTROMETER",  # 片上微型光谱仪
    "IM-PON-50G",          # 50G-PON 光前端
    "IM-XGS-PON",          # XGS-PON 光前端
    "IM-CPO-OCS",          # OCS 直连光交换（含交换矩阵黑箱）
]

# ---- 高端档 ¥4999：系统级 + 生态无现成 + 高客户价值（前沿稀缺赛道）----
TIER_PREMIUM = [
    "IM-1.6T-DR8",         # 1.6T 最前沿，技术门槛最高
    "IM-1.6T-FR4",         # 1.6T FR4
    "IM-800G-DR8",         # 800G 高端
    "IM-800G-FR4",         # 800G FR4
    "IM-CPO-WDM5",         # CPO 共封装（本站唯一验证需求的货架）
    "IM-PHOTONIC-INTERPOSER",  # 光子中介层 2.5D（5 基元，最复杂）
    "IM-CHIPLET-IO",       # XPU 光 IO（NVIDIA/TSMC 赛道）
    "IM-COHERENT-400ZR",   # 相干 400G ZR（120km DCI，壁垒最高）
    "IM-DWDM-40CH",        # 40 通道 DWDM（系统级）
    "IM-WSS-1X9",          # 波长选择开关（ROADM 高价值器件）
    "IM-ONCHIP-NOC",       # 片上光网络（4 基元，chiplet fabric）
    "IM-OPA-LIDAR",        # 光学相控阵固态激光雷达（4 基元）
    "IM-OCT",              # 光学相干层析（4 基元，医疗成像高价值）
    "IM-OPTICAL-GYRO",     # 光纤陀螺（4 基元，高精度惯性/国防）
    "IM-OPTO-COMPUTE",     # 光计算/光神经网络（前沿稀缺）
    "IM-OPTCOMB",          # 芯片级光频梳（稀缺高价值）
    "IM-TRUE-TIME-DELAY",  # 微波光子真延时（相控阵/国防）
]

# ---- 量子 8 项：咨询制（出口管制合规红线），起步价同高端档 ----
TIER_CONSULT = [
    "IM-QKD-TX-SHELF", "IM-QKD-RX-SHELF", "IM-QKD-MULTI4",
    "IM-QCTRL-ZC3-10Q", "IM-QCTRL-HERON-16Q", "IM-QCTRL-WILLOW-12Q",
    "IM-QCHIP-INT", "IM-QCOM-LINK",
]


def build_price_map():
    """返回 {shelf_id: price} 全量映射。"""
    out = {}
    for sid in TIER_BASIC:
        out[sid] = PRICE_TIERS["basic"]
    for sid in TIER_STANDARD:
        out[sid] = PRICE_TIERS["standard"]
    for sid in TIER_PREMIUM:
        out[sid] = PRICE_TIERS["premium"]
    for sid in TIER_CONSULT:
        out[sid] = PRICE_TIERS["premium"]   # 咨询制起步价（人工服务另议）
    return out


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from lda_l2.innovation_market import DEFAULT_SHELF  # noqa: E402
    from lda_l2.ship_package import OPEN_SHELVES  # noqa: E402

    all_ids = {s.id for s in DEFAULT_SHELF}
    pm = build_price_map()
    missing = sorted(all_ids - set(pm))
    extra = sorted(set(pm) - all_ids)
    print("货架总数:", len(all_ids))
    print("已定价:", len(pm))
    print("档位分布: ¥599=%d  ¥1999=%d  ¥4999(含咨询制)=%d"
          % (len(TIER_BASIC), len(TIER_STANDARD),
             len(TIER_PREMIUM) + len(TIER_CONSULT)))
    print("未覆盖:", missing if missing else "无 ✅")
    print("多余(不存在):", extra if extra else "无 ✅")
    # 咨询制货架不得出现在开放下载白名单（出口管制红线）
    bad = [s for s in TIER_CONSULT if s in OPEN_SHELVES]
    print("咨询制误入开放白名单:", bad if bad else "无 ✅")
    # 开放货架定价分布
    open_prices = [pm[s] for s in OPEN_SHELVES if s in pm]
    from collections import Counter
    print("开放货架档位:", dict(Counter(open_prices)))
