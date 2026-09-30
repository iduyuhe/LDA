# -*- coding: utf-8 -*-
"""LDA · 电子计算征程（E1…Ex）核心包 ecore（electronic compute core）。

路线：模拟电子计算核（MVM 交叉阵列）——电子版的「光子 MZI 网格」。
E1 基座：晶体管级模型（mosfet）+ MNA 电路仿真器（mna）+ 最小模拟计算单元（analog_mvm）。
"""
from __future__ import annotations

from .analog_mvm import (
    inverting_summer,
    inverting_summer_golden,
    mosfet_saturation_bias,
    mosfet_saturation_golden,
)
from .crossbar_mvm import (
    CROSSBAR_DISCLOSURE,
    CrossbarMVM,
    build_ota_circuit,
    ota_open_loop_gain,
)
from .capability_manifest import (
    ECORE_CAPABILITY_DISCLOSURE,
    ECORE_CAPABILITY_MANIFEST,
    ecore_module_names,
    manifest_check,
)
from .mna import Circuit
from .mvm_datapath import (
    MVM_DATAPATH_DISCLOSURE,
    AnalogMvmUnit,
    MvmDatapath,
    mvm_datapath_self_check,
    quantize_uniform,
    relu,
    tiled_mvm,
)
from .scale_bench import (
    LANDMARKS,
    LDA_CAPABILITIES,
    NON_CLAIMED,
    SCALE_BENCH_DISCLOSURE,
    honest_boundary_ok,
    honest_comparison,
    scale_bench_self_check,
    scale_sweep,
)
from .mosfet import (
    MOSFET_DISCLOSURE,
    NmosParams,
    id_gm_gds,
    id_saturation_closed,
    mosfet_self_check,
    vdsat,
)

__all__ = [
    "Circuit",
    "NmosParams",
    "id_gm_gds",
    "id_saturation_closed",
    "vdsat",
    "mosfet_self_check",
    "MOSFET_DISCLOSURE",
    "inverting_summer",
    "inverting_summer_golden",
    "mosfet_saturation_bias",
    "mosfet_saturation_golden",
    "CrossbarMVM",
    "build_ota_circuit",
    "ota_open_loop_gain",
    "CROSSBAR_DISCLOSURE",
    "AnalogMvmUnit",
    "MvmDatapath",
    "quantize_uniform",
    "relu",
    "tiled_mvm",
    "mvm_datapath_self_check",
    "MVM_DATAPATH_DISCLOSURE",
    "scale_sweep",
    "scale_bench_self_check",
    "honest_comparison",
    "honest_boundary_ok",
    "LANDMARKS",
    "LDA_CAPABILITIES",
    "NON_CLAIMED",
    "SCALE_BENCH_DISCLOSURE",
    "ECORE_CAPABILITY_MANIFEST",
    "ECORE_CAPABILITY_DISCLOSURE",
    "manifest_check",
    "ecore_module_names",
]

# 征程入口披露（对外引用须携此诚实边界）
ECORE_DISCLOSURE: dict = {
    "route": "模拟电子计算核（MVM 交叉阵列）：电子版的「光子 MZI 网格」。",
    "e1_scope": "E1 基座：晶体管级长沟道模型 + MNA 电路仿真器（DC/瞬态/AC）+ 最小模拟计算单元。",
    "e2_scope": "E2 参数化阵列：N×M 模拟 MVM 交叉阵列生成器（amp='ideal' VCVS TIA / amp='transistor' NMOS三极管权重）；另含晶体管级 OTA 开环增益表征。",
    "e3_scope": "E3 数据通路：数字→DAC→交叉阵列→ADC→数字 的模拟计算引擎；多层级联(MLP+ReLU)+分块(tiling)；带符号权重用参考列法映射；端到端 vs 全精度数字 golden 正确性判据。",
    "e4_scope": "E4 规模对标（诚实边界）：N×N 数据通路规模扫描(至 256×256=65536 突触) + 公开模拟加速器 landmark 诚实对标；不报 TOPS/TOPS/W；相对误差有界/绝对误差 ∝N。",
    "e5_scope": "E5 平台能力硬化：ecore 能力清单（ECORE_CAPABILITY_MANIFEST·单一真源）+ 常驻守护门禁（清单↔模块/符号双向完备 + 披露一致 + 诚实边界）。",
    "redline": "电域→仅电路级（T1）：不碰 Foundry TCAD / 工艺角 / 流片（属 T2 真值，永久锁）。",
    "sovereignty": "C 级自主（纯 numpy），不借 HSPICE/Spectre 等商业 SPICE 引擎；LLM 不进判决路径。",
    "honest_boundary": "电路级设计验证引擎，非签核级 SPICE（无温度/噪声/稀疏矩阵/收敛增强）；"
                       "晶体管参数为公开典型量级占位，非 PDK 标定，无实测锚 ⇒ 不宣称器件性能。",
    "not_oracle": "golden 均为闭式物理律（分压/平方律/一阶 RC）；不引入任何外部 ORACLE。",
}
