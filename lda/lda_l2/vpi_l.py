# -*- coding: utf-8 -*-
"""Vπ·L 单一真值源（single source of truth）· 统一单位 **V·mm**。

任务 #7（吃狗粮发现）的统一落点：消除「光侧 25 V·cm vs EIC 侧 7.5 V·mm」
的跨模块口径分裂。

══════════════════════════════════════════════════════════════════════════
口径两层语义（二者是不同设计语义，**不是同一物理量的冲突**，不可强行合并为一个数）：

① VPI_L_REDLINE_VMM = 250.0  (V·mm)
   = 光侧原 `mzi_mesh_matmul.VPI_L_V_CM = 25.0 V·cm`（同单位 250 V·mm），
     热光硅相移器 **red-line 保守设计上界**（Soref-Bennett 硅热光 10–50 V·cm
     取中值 25）。用于设计预算 / 安全余量语义，**不得作为典型工作值**。

② VPI_L_TYP_TIN_VMM = 7.5  (V·mm)
   = EIC 侧原 `eic_behavioral.VPI_L_V_MM_DEFAULT = 7.5`（2.5–15 V·mm 取中值），
     TiN 加热器 **代表生产值**。用于典型工作点语义。

物理换算：25 V·cm = 250 V·mm，与 7.5 V·mm 同单位下相差 33× —— 这是 red-line
上界 vs 代表值的合理量级差（前者是保守最坏情况预算），**不是 bug**。任务原描述
「差 ~3.3×」是忽略单位（25/7.5）的误算，已在此订正。

注意：两常量均属**设计预算 / 行业设计规则量纲**，**非 golden 实测锚**；
改变它们只改预算与映射量级，不构成能力宣称（见各模块红线披露）。
══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

# 热光硅相移器 red-line 保守设计上界（原 25 V·cm 换算为 V·mm）。
VPI_L_REDLINE_VMM = 250.0

# TiN 加热器代表生产值（原 EIC 默认 7.5 V·mm）。
VPI_L_TYP_TIN_VMM = 7.5

# 遗留 V·cm 兼容别名（= 250 V·mm ÷ 10）。仅用于保留旧调用方接口，
# 新代码应直接使用上述 V·mm 真值。
VPI_L_REDLINE_VCM = VPI_L_REDLINE_VMM / 10.0   # = 25.0 V·cm


__all__ = [
    "VPI_L_REDLINE_VMM",
    "VPI_L_TYP_TIN_VMM",
    "VPI_L_REDLINE_VCM",
]
