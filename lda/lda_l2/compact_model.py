"""LDA L2 · 带参数紧凑模型 schema（WBS-T1-1 · 光电接口层）。

范围：把网表从拓扑骨架升级为**带参数紧凑模型**：VπL / 3dB 带宽 / 结电容 /
响应度 / 暗电流 / 电极 RC。接进 Cadence（行为级模型 + 带参数网表）由后续
WBS-T1-2/3 完成；本模块只定义 schema + 物理映射 + 反向护栏 + B29/B30 锚接入。

诚实边界（与 parasitic_rc.py 同源主权纪律）：
  - 默认物理常数为**公开文献典型量级占位**，非真实 PDK 声明；
  - B29（热光相移效率）/ B30（读出保真度）是**方法学独立物理锚**，
    calibrate_from_anchors 把其实测值接入作为紧凑模型锚定点（供 T2 真值链）；
  - 真实 PDK 标定参数发动期由真实工艺提供后替换（数据驱动，不杜撰）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CompactModelSpec:
    """带参数紧凑模型规格（调制器 / 光电探测器通用占位）。"""
    name: str = "unnamed"
    # —— 调制器 ——
    VpiL_Vcm: float = 2.0          # 半波电压·长度积 (V·cm)
    length_mm: float = 1.0         # 调制臂长度 (mm)
    # —— 光电 / 寄生 ——
    R_electrode_ohm: float = 50.0  # 电极串联电阻 (Ω)
    C_junction_fF: float = 100.0   # 结电容 (fF)
    C_electrode_fF: float = 20.0   # 电极寄生电容 (fF)
    quantum_eff: float = 0.80      # 量子效率 η (0–1)
    wavelength_nm: float = 1550.0  # 工作波长 (nm)
    dark_current_nA: float = 1.0   # 暗电流 (nA)
    # —— 锚定点（接 B29/B30，发动期填充；None=未标定占位）——
    thermal_phase_deg_per_mW: Optional[float] = None  # 来自 B29
    readout_fidelity_F: Optional[float] = None        # 来自 B30
    source: Dict[str, str] = field(default_factory=dict)


def derive_responses(spec: CompactModelSpec) -> Dict[str, float]:
    """由紧凑模型参数派生可测响应（死标量，供反向护栏验证非自证桩）。

    物理映射（公开文献典型量级，占位；真实标定待 T2 真值链）：
      C_total_fF      = C_junction + C_electrode              （总负载电容）
      bw_3db_ghz      = 1 / (2π · R_electrode · C_total)     （RC 限制带宽）
      responsivity_AW = quantum_eff · λ_nm / 1240            （量子效率 → 响应度）
      Vpi_at_length_V = VpiL_Vcm / length_mm                 （该长度下半波电压）
    暗电流直接透传（参数即响应）。C_electrode 进入 C_total → 无悬空死参数。
    """
    c_total_ff = spec.C_junction_fF + spec.C_electrode_fF
    c_total = c_total_ff * 1e-15
    bw_3db_hz = 1.0 / (2.0 * math.pi * spec.R_electrode_ohm * c_total)
    bw_3db_ghz = bw_3db_hz / 1e9
    responsivity = spec.quantum_eff * spec.wavelength_nm / 1240.0
    vpi_v = spec.VpiL_Vcm / max(spec.length_mm, 1e-9)
    return {
        "bw_3db_ghz": round(bw_3db_ghz, 6),
        "C_total_fF": round(c_total_ff, 6),
        "responsivity_AW": round(responsivity, 6),
        "Vpi_at_length_V": round(vpi_v, 6),
        "dark_current_nA": spec.dark_current_nA,
    }


def calibrate_from_anchors(spec: CompactModelSpec,
                           b29_report: Optional[Dict] = None,
                           b30_report: Optional[Dict] = None) -> CompactModelSpec:
    """把 B29/B30 独立物理锚实测值接入紧凑模型锚定点（不杜撰，仅记录来源）。"""
    if b29_report and "value" in b29_report:
        spec.thermal_phase_deg_per_mW = float(b29_report["value"])
        spec.source["thermal_phase_deg_per_mW"] = "B29-anchor"
    if b30_report and "value" in b30_report:
        spec.readout_fidelity_F = float(b30_report["value"])
        spec.source["readout_fidelity_F"] = "B30-anchor"
    return spec


def compact_model_markdown(spec: CompactModelSpec,
                           responses: Optional[Dict[str, float]] = None) -> str:
    if responses is None:
        responses = derive_responses(spec)
    L = ["### 带参数紧凑模型（主权 schema · 非真实 PDK 占位）", ""]
    L.append(f"- 名称：`{spec.name}`")
    L.append("")
    L.append("| 参数 | 值 | 来源 |")
    L.append("|---|---|---|")
    rows = [
        ("VπL (V·cm)", spec.VpiL_Vcm, spec.source.get("VpiL_Vcm", "default")),
        ("长度 (mm)", spec.length_mm, "default"),
        ("R_electrode (Ω)", spec.R_electrode_ohm, "default"),
        ("C_junction (fF)", spec.C_junction_fF, "default"),
        ("C_electrode (fF)", spec.C_electrode_fF, "default"),
        ("量子效率 η", spec.quantum_eff, "default"),
        ("波长 (nm)", spec.wavelength_nm, "default"),
        ("暗电流 (nA)", spec.dark_current_nA, "default"),
        ("热光效率 (°/mW)", spec.thermal_phase_deg_per_mW,
         spec.source.get("thermal_phase_deg_per_mW", "未标定")),
        ("读出保真度 F", spec.readout_fidelity_F,
         spec.source.get("readout_fidelity_F", "未标定")),
    ]
    for name, val, src in rows:
        L.append(f"| {name} | {val} | {src} |")
    L.append("")
    L.append("**派生响应（RC / 量子效率物理映射）**")
    L.append("")
    L.append(f"- 3dB 带宽：{responses['bw_3db_ghz']:.4f} GHz（RC 限制）")
    L.append(f"- 响应度：{responses['responsivity_AW']:.4f} A/W")
    L.append(f"- 半波电压@长度：{responses['Vpi_at_length_V']:.4f} V")
    L.append(f"- 暗电流：{responses['dark_current_nA']:.4f} nA")
    L.append("")
    L.append("*诚实边界：默认物理常数为公开文献典型量级占位，非真实 PDK；"
             "B29/B30 锚定点发动期由真实工艺实测填充。*")
    return "\n".join(L)
