# LDA 器件开发实操手册：MMI + Transmon 双案例

> 版本：v1.0（2026-08-25）· 配套 LDA v0.6.x（D-01~D-112 全交付）
> 案例：① 1550nm 1×2 MMI 均分分束器（光器件 · PDA）② E_J=15GHz transmon 读出设计（量子器件 · QEDA）
> 性质：**真实运行产出**（本手册全部数值来自系统实际计算，非示意）

---

## 0. 手册定位

### 0.1 系统是什么（一句话）

LDA 是**开源 · Agent 原生**的光子（PDA）+ 量子（QEDA）器件设计验证系统：给定器件目标 → 自动搜索参数/几何 → 真实求解器计算 → **双重验证**（解析契约 + 数值自洽，LLM 不进判决路径）→ 返回**带验证报告**的设计。

### 0.2 四层能力

| 层 | 内容 |
|---|---|
| 入口层 | WebUI 57 面板 · L1 Agent 协议（MCP + CLI）· run_*.py 脚本 · 库级 API |
| 设计引擎 | 逆设计（3D adjoint / 截面 / voxel 拓扑）· 参数扫描 · Agent 自迭代闭环 |
| 求解内核 | 1D/2D/3D FDTD（numpy · numba 20×+ · torch）· transmon/谐振器严格对角化 |
| 验证裁判 | harness 21 题 = 物理定律锚 B1-B18 + 实证锚 E1-E3（死标量，LLM 永不进判决） |

### 0.3 诚实边界（全文适用）

- 仿真为 **2D TEz / 设计级近似**，非流片签核级；分束比绝对值依赖自成像长度精确设计，χ 等量级为设计参考
- **未接入真实晶圆厂 PDK**（发动期事项，D-62 联动延后）；真实数据经社区评审流（citation 必填 → 具名评审 → 落库）流入
- 所有 PASS 含义 = **通过系统内置确定性物理定律锚验收**，可追溯、可复现

---

## 1. 案例一：1550nm 1×2 MMI 均分分束器（PDA）

### 1.1 设计目标

- 工艺：SOI（n_core=3.48 / n_clad=1.44）
- 目标：1×2 对称 MMI，**工作波长 1550nm，双输出均分（50:50）**
- 验收判据（D-72 死标量，LLM 不进判决）：
  - (a) 仿真有效：注入能量被收集（power_sum>0）
  - (b) 对称性：双输出平衡度 |S21−S31|/(S21+S31) ≤ 0.15
  - (c) 透射存在：S21+S31 ≥ 0.05

### 1.2 设计流程（真实走完的闭环）

| 步骤 | 操作 | 结果 |
|---|---|---|
| ① 基线 | 默认参数（W_mmi=6.0, L_mmi=20μm）跑 2D FDTD | balance=0.142（不均分） |
| ② 扫描 | 扫多模区长度 L_mmi（10~40μm） | L=40 在 1.55μm 完美均分（balance=0.0022, T=0.860） |
| ③ 验收 | 5 波长（1.49~1.61μm）死标量验收 | 🔴 **FAIL**：λ=1.52μm balance=0.188>0.15——**带宽受限** |
| ④ 重设计 | 诊断"W_mmi 越大带宽越窄"→ 减小 W 换带宽 | W=5.5/L=45 → **5 波长全过 PASS** |

### 1.3 关键代码（库级 API，可复现）

```python
import sys; sys.path.insert(0, "lda")
from lda_solver.port_sparams import s_parameter_spectrum, verify_s_params

# ① 几何生成（lda_l2/primitives.mmi_descs 被内部调用）
params = dict(width=0.5, W_mmi=5.5, L_mmi=45.0, L_tap=4.0,
              out_gap=0.5, L_out=3.0)

# ② 单波长快速扫描找均分点
r = s_parameter_spectrum("mmi", params, [1.55])
p = r["points"][0]   # S11_2 / S21_2 / S31_2 / balance / T_total

# ③ 完整验收（5 波长谱形 + 死标量判据）
r = verify_s_params("mmi", params)   # 默认 wl0=1.55, n_wl=5, span=0.06
print(r["acceptance"], r["verdict"])
```

### 1.4 交付设计（最终）

```
几何参数（μm）：width=0.5 · W_mmi=5.5 · L_mmi=45 · L_tap=4 · out_gap=0.5 · L_out=3
仿真结果（2D FDTD，输入归一）：
  分束比   51.7% : 48.3%（@1550nm，≈均分）
  平衡度   0.0335（阈值 0.15；全带宽 max=0.110）
  总透射   0.729（回波 S11≈-5.7dB）
  验收     5 波长 1.49~1.61μm 全部 PASS（acceptance=true）
报告：    lda/reports/mmi_1550_design.json
```

### 1.5 工程洞察（本案例的价值）

1. **验收诚实暴露缺陷**：中心波长完美均分（balance=0.0022）但带宽内 FAIL——若只看单波长会误交付带宽受限设计
2. **MMI 带宽对 W_mmi 敏感**：W=6.0 时 1.52μm 平衡退化（0.188）；W=5.5 全带宽平衡≤0.11——**设计结论：减 W 换带宽**
3. **迭代式开发**：基线 → 扫描 → 验收 → 重设计，四步闭环即系统工作方式

---

## 2. 案例二：E_J=15GHz transmon 读出设计（QEDA）

### 2.1 设计目标

- 给定 **E_J=15 GHz**（约瑟夫森能）
- 设计：① transmon 本体（E_C → f01 / α）② 色散读出（腔频率 f_r、耦合 g、κ → χ、n_crit、Purcell）
- 验收判据（D-88 死标量）：
  - 色散区 |Δ|/g ≥ 5
  - χ：数值严格对角化 ↔ Blais 三能级解析 rel ≤ 0.10
  - 拉比分裂自洽：g 反推与输入 rel ≤ 0.02
  - **α 修正必要性**：三能级显著优于二能级近似（≥3×）

### 2.2 设计流程

| 步骤 | 操作 | 结果 |
|---|---|---|
| ① 本体 | E_J=15 扫 E_C（0.15~0.35），目标 α≈-0.3GHz | **选定 E_C=0.25**：f01=5.214GHz、α=-0.283GHz、f12=4.931GHz |
| ② 双验证 | Koch 解析 vs 严格对角化 | rel=0.25%（全谱 <0.4%），E_J/E_C=60（transmon 区） |
| ③ 读出 | f_r=f_q+1.3=6.514GHz、g=0.08、κ=0.01 | Δ/g=16.3、χ=-0.88MHz、n_crit=66、T1_Purcell=4.2ms |
| ④ 验收 | 4 判据死标量 | **acceptance=True（全过）** |

### 2.3 关键代码（库级 API，可复现）

```python
import sys; sys.path.insert(0, "lda")
from lda_solver.transmon_solver import solve_transmon, koch_f01, koch_alpha
from lda_solver.qubit_resonator_solver import solve_qubit_resonator

# ① 本体：严格对角化 + Koch 对拍
tr = solve_transmon(E_J=15.0, E_C=0.25, N=24)      # f01 / f12 / alpha
rel = abs(tr["f01"] - koch_f01(15.0, 0.25)) / koch_f01(15.0, 0.25)

# ② 色散读出：三能级严格求解
qr = solve_qubit_resonator(f_q=tr["f01"], alpha=tr["alpha"],
                           f_r=6.5142, g=0.08, kappa=0.01)
# chi_num_ghz / chi_3level_ghz / chi_2level_ghz / n_crit /
# gamma_purcell_ghz / t1_purcell_us / ac_stark_1ph_ghz / acceptance
```

### 2.4 交付设计（最终）

```
Transmon 本体:  E_J=15 GHz · E_C=0.25 GHz · f01=5.214 GHz · α=-0.283 GHz
               （E_J/E_C=60；Koch 对拍 rel=0.25%）
读出腔:        f_r=6.514 GHz · g=0.08 GHz · κ=0.01 GHz（Q≈150）
关键物理量:     χ=-0.88 MHz（色散位移）· n_crit=66 光子
               T1_Purcell=4.2 ms · AC Stark 1ph=-1.76 MHz
验收:          4 判据全过（acceptance=true）
报告：         lda/reports/qeda_ej15_readout_design.json
```

### 2.5 物理洞察（本案例的价值）

1. **α 修正必要性的活例子**：χ 三能级 -0.88 MHz vs 二能级近似 -4.92 MHz——**差 5.6 倍**。忽略 transmon 非谐性会把读出设计算错近一个数量级；系统用三值对拍（数值 ↔ 三能级解析 ↔ 二能级）直接量化
2. **求解器自洽**：拉比分裂反推 g=0.0800 与输入一致（rel=1.2e-4），无系统性偏差
3. **E_C 扫描中 α≈-E_C 一阶线性**（严格对角化确认），Koch 对拍全谱成立

---

## 3. 通用方法论：设计→验证闭环

### 3.1 工作方式（四步）

```
① 定义目标（器件 + 指标 + 阈值）
② 参数化/扫描（几何或电路参数网格）
③ 真实求解（FDTD / 严格对角化）
④ 死标量验收（物理定律锚 / 实证锚，LLM 不进判决路径）→ PASS 交付 / FAIL 诊断重设计
```

### 3.2 判题哲学

- 判决 = **确定性死标量比对**（|candidate − oracle| ≤ tol），**LLM 永不进判决路径**（红线）
- Oracle 两类：**物理定律锚**（解析解/严格对角化/自成像对称必然推论）+ **实证锚**（真实测量语料，citation 必填）
- 落库(live) ≠ 进版本控制；权威内容以维护者 git 提交为准

### 3.3 迭代是特性

验收 FAIL **不是失败**——它暴露真实物理约束（带宽、非谐性、损耗），驱动重设计。单波长"看起来对"不等于可用，谱形/多判据验收才能交付可靠设计。

---

## 4. 三入口对照（同能力三种操作方式）

| 入口 | 适合场景 | 本次用法 |
|---|---|---|
| WebUI 面板 | 可视化验证 / 演示 / 生态操作 | 面板 1-52 仿真演示、53-57 生态/实证锚 |
| CLI / run_*.py | 批量、脚本化 | 逆设计引擎、性能基准 |
| 库级 API | 深度定制 / 二次开发 | 本手册两案例（s_parameter_spectrum / solve_transmon） |
| L1 Agent（MCP/CLI） | 自动化编排、verify_design 判题 | run_agent.py / run_l1_agent_smoke.py |

---

## 5. 附录

### 5.1 本手册相关文件

| 文件 | 说明 |
|---|---|
| `lda/lda_l2/primitives.py` | MMI/taper/光栅等基元几何生成（`mmi_descs`） |
| `lda/lda_solver/port_sparams.py` | MMI 2D FDTD + S 参数 + D-72 验收 |
| `lda/lda_solver/transmon_solver.py` | transmon 哈密顿量严格对角化（Koch 对拍） |
| `lda/lda_solver/qubit_resonator_solver.py` | D-88 色散读出严格求解（χ/n_crit/Purcell） |
| `lda/lda_design/design_engine.py` | DesignEngine 参数化设计入口（Waveguide/Bragg/Transmon/Ring） |
| `lda/reports/mmi_1550_design.json` | 案例一设计报告 |
| `lda/reports/qeda_ej15_readout_design.json` | 案例二设计报告 |

### 5.2 环境要求

- Python 3.13 venv（必装 numpy/scipy/jsonschema；可选 numba/torch 加速）
- 全部案例零外部 EDA 依赖（自研求解器 + 物理定律锚）

### 5.3 复现命令

```bash
# 案例一（MMI）：可运行 smoke 已有
python lda/run_webui_api_smoke.py        # 路由层门禁（含 /api/ecosystem）
# 案例二（QEDA）：
python lda/run_quantum_design_smoke.py   # 量子设计 smoke（DesignEngine Transmon 路径）
```

### 5.4 后续扩展方向

- MMI：3D FDTD 复验（需 GPU，D-89 numba 路径）+ 多模干涉成像点逐点分析
- Transmon：D-91 纵深三件套（多能级展开 / Rabi+AC Stark / ZZ 串扰）+ 退相干工程参数
- 真实 PDK 数据经社区评审流流入后，几何/工艺参数可对接真实流片（发动期 D-62 联动）

---

*本文档由 LDA 系统真实运行数据整理；所有验收判据均为确定性物理定律锚，LLM 不进判决路径。*
