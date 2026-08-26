# LDA 器件类型完整清单（v0.8.x · 闭环面板「器件类型」下拉）

> 生成时间：2026-08-26
> 面板下拉现含 **15 类**器件类型，分两组：
> - **● 闭环引擎（4 类）**：给目标值 → 参数空间网格搜索 + 真实求解器双重验证 → 最优已验证器件
> - **○ 参数驱动包（11 类）**：成熟器件，用默认参数直接包成统一 DesignPackage
>
> 全部经本地实测跑通（schema 校验通过、verification.passed 为真），见门禁 `run_design_outcome_smoke.py`。

---

## 一、闭环引擎（target 驱动 · 4 类）

| kind | 中文名 | 域 | 默认目标 | 计算强度 | 说明 |
|------|--------|----|---------|---------|------|
| engine_waveguide | 直波导 | 光子 | neff = 3.25 | FDTD（~20s） | 目标有效折射率，FDTD 网格搜索 |
| engine_braggmirror | 布拉格镜 | 光子 | R_min ≥ 0.999 | FDTD（~59s） | 目标反射率，最少周期求解 |
| engine_transmon | Transmon 量子比特 | 量子 | f01 = 5.0 GHz | 对角化（~0s） | 能级对角化闭式反解 |
| engine_ringresonator | 环形谐振器 | 光子 | FSR = 9.0 nm | 解析锚（~0s） | 自由光谱范围，解析 ORACLE（FDTD 抽检需 GPU） |

---

## 二、统一设计包（params 驱动 · 11 类）

| kind | 中文名 | 域 | 默认参数 | 计算强度 | 说明 |
|------|--------|----|---------|---------|------|
| add_drop | 环形 add-drop | 光子 | fsr=17.5nm, gap=0.3 | ~6s | D-37 可制造环形分插滤波器 |
| quantum | 量子逆设计（Transmon） | 量子 | kind=Transmon, target=5.0 | ~0s | D-41 量子闭式反解 + 严格双验证 |
| wdm | WDM 多环级联 | 光子 | 4 通道[1550,1552.5,1555,1557.5], gap=0.3 | ~0s | D-42 波分复用级联系统 |
| readout_chain | 光子-量子混合读出链路 | 混合 | f01=5.0, delta=1.0, g=0.10, kappa_r=0.005 | ~0s | D-43 dispersive readout 混合链路 |
| multiqubit | N-qubit 频率复用读出 | 量子 | f01s=[4.8,5.0,5.2] | ~0s | D-46 多量子比特复用读出 |
| readout_fidelity | 单发读出保真度预算 | 量子 | f01=5.0 | ~0s | D-47 读出保真度预算 |
| multiqubit_fidelity | N-qubit 复用读出保真度 | 量子 | f01s=[4.8,5.0,5.2], T1=[20,15,25]µs | ~0s | D-51 逐 qubit 保真度 |
| mixed_system | WDM×量子读出混合巨型系统 | 混合 | wdm[1550,1553,1556], qubit[4.8,5.0,5.2] | ~0s | D-52 光子-量子混合大系统 |
| coupler | 方向耦合器 | 光子 | target_cross=0.5, cycles=400 | FDTD（~9s） | D-55 定向耦合器设计闭环 |
| wdm_coupler | 耦合器×WDM 组合 | 光子 | channels[1550,1553,1556], gap_scan[0.25,0.30,0.35] | ~0s | D-57 FDTD 标定驱动 gap |
| splitter_readout | 分束网络供电读出 | 混合 | f01s=[4.8,5.0,5.2] | FDTD（~46s） | D-63 分束网络供电控制线 |

---

## 三、诚实边界（务必对齐对外口径）

1. **这是「器件（device）级」设计，不是完整「芯片（chip）」。** 产出 = 单一功能元件的已验证几何参数 + 验证报告 + 可仿真文件。
2. **芯片级仍需**：多器件版图集成、布线、GDSII 生成、PDK 绑定、DRC/LVS、流片准备 —— 对应 LDA 架构 L2（PDK/Registry）+ 版图层，仍在后续里程碑。
3. **LLM 不进判决路径**：所有验收由物理定律 ORACLE / 真实求解器死标量比对决定。
4. **重计算标注**：标 FDTD 的类目（waveguide/braggmirror/coupler/splitter_readout 及 engine 相关）需跑真实电磁求解，耗时见「计算强度」；其余为闭式/解析，瞬时。
