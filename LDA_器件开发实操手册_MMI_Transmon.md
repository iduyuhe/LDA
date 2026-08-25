# LDA 器件开发实操手册：MMI + Transmon + 逆设计

> 版本：v2.0（2026-08-25）· 配套 LDA v0.6.x（D-01~D-112 全交付）
> 案例：① 1550nm 1×2 MMI 均分分束器（光器件 · PDA）② E_J=15GHz transmon 读出设计（量子器件 · QEDA）③ 谱形目标逆设计（自动搜几何 · 设计引擎）
> 性质：**真实运行产出**（本手册全部数值来自系统实际计算，非示意）；v2.0 新增案例三 + 性能/生态章节 + WebUI 图文操作
> 配套：`docs/images/`（WebUI 实测截图）

---

## 0. 手册定位

### 0.1 系统是什么（一句话）

LDA 是**开源 · Agent 原生**的光子（PDA）+ 量子（QEDA）器件设计验证系统：给定器件目标 → 自动搜索参数/几何 → 真实求解器计算 → **双重验证**（解析契约 + 数值自洽，LLM 不进判决路径）→ 返回**带验证报告**的设计。

### 0.2 四层能力

| 层 | 内容 |
|---|---|
| 入口层 | WebUI 57 面板 · L1 Agent 协议（MCP + CLI）· run_*.py 脚本 · 库级 API |
| 设计引擎 | 逆设计（3D adjoint / 截面 / voxel 拓扑 · 谱形目标）· 参数扫描 · Agent 自迭代闭环 |
| 求解内核 | 1D/2D/3D FDTD（numpy · numba 20×+ · torch）· transmon/谐振器严格对角化 |
| 验证裁判 | harness 21 题 = 物理定律锚 B1-B18 + 实证锚 E1-E3（死标量，LLM 永不进判决） |

### 0.3 诚实边界（全文适用）

- 仿真为 **2D TEz / 设计级近似**，非流片签核级；分束比绝对值依赖自成像长度精确设计，χ 等量级为设计参考
- **未接入真实晶圆厂 PDK**（发动期事项，D-62 联动延后）；真实数据经社区评审流（citation 必填 → 具名评审 → 落库）流入
- 所有 PASS 含义 = **通过系统内置确定性物理定律锚验收**，可追溯、可复现
- 逆设计有**收敛率问题**（见案例三 §3.4）：单次运行未必收敛，须多起点/调参——系统会诚实标注 FAIL 而非假装成功

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

### 1.5 工程洞察

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

### 2.5 物理洞察

1. **α 修正必要性的活例子**：χ 三能级 -0.88 MHz vs 二能级近似 -4.92 MHz——**差 5.6 倍**。忽略 transmon 非谐性会把读出设计算错近一个数量级；系统用三值对拍（数值 ↔ 三能级解析 ↔ 二能级）直接量化
2. **求解器自洽**：拉比分裂反推 g=0.0800 与输入一致（rel=1.2e-4），无系统性偏差
3. **E_C 扫描中 α≈-E_C 一阶线性**（严格对角化确认），Koch 对拍全谱成立

---

## 3. 案例三：谱形目标逆设计（自动搜几何 · 设计引擎）

### 3.1 设计目标

- 不给定几何，**只给定目标谱**，由系统自动搜索几何（伴随法梯度驱动拓扑优化）
- 目标：分束比 50:50（split_ratio）与多波长谱形（spectrum 1.53/1.55/1.57μm）
- 验收判据（D-80 死标量）：
  - adjoint 梯度 vs 有限差分对拍 max_rel_err ≤ 0.15（**求解器正确性**）
  - 目标 FOM improvement ≥ 1.5（**优化有效性**）
  - 谱形目标：逐波长 FOM 均提升 + 加权 improvement ≥ 1.5

### 3.2 运行结果（真实，两次运行）

| 目标 | 结果 | 验收 |
|---|---|---|
| **spectrum（3 波长谱形）** | FOM 加权 **15.68×**（1.53:15.30× / 1.55:15.97× / 1.57:15.77×），25 轮 71s | **PASS ✓** |
| split_ratio（50:50） | improvement=0.75×，final_ratio=0.635（目标 0.5） | 🔴 **FAIL（诚实标注）** |

- **PASS 案例**：给"3 波长目标谱"→ 系统 25 轮伴随法优化 → FOM 提升 **15.68×**，且 adjoint 梯度对拍 max_rel_err=0.0000（6 样本）——**优化梯度物理正确性由有限差分独立证实**
- **FAIL 案例**：split_ratio 目标对默认起点收敛失败（0.75×<1.5）——**系统如实返回未全过**（adjoint 梯度仍对拍 2.3e-5 通过，说明是优化收敛问题而非求解器错误），需要多起点/调参重试

### 3.3 关键代码（库级 API，可复现）

```python
import sys; sys.path.insert(0, "lda")
from lda_agent.spectral_inverse_design import design_spectral

# PASS 路径：谱形目标（3 波长）
r = design_spectral(target_type="spectrum", wavelengths="1.53,1.55,1.57")
# r["acceptance"]["passed"]=True, improvement=15.68×
# verify.max_rel_err=0.0000（adjoint vs FD 对拍）

# FAIL 路径（诚实标注）：分束比目标，默认起点未收敛
r2 = design_spectral(target_type="split_ratio", target_ratio=0.5)
# r2["acceptance"]["passed"]=False（improvement=0.75×）——需调参/多起点
```

### 3.4 工程洞察（逆设计的正确打开方式）

1. **梯度正确性 ≠ 优化收敛**：两次运行的 adjoint 对拍都 ≈0（求解器物理正确），但 split_ratio 未收敛——**收敛率是独立问题**，须多起点扫描、调整超参
2. **诚实 FAIL 是设计特性**：系统不会伪装成功；FAIL 输出携带诊断信息（哪条判据不过），支持迭代重试
3. **目标定义决定难度**：谱形目标（多波长能量约束）比单一分束比约束更易收敛——实际工程中合理设计目标函数比调优化器更关键

---

## 4. 性能基准实操（求解内核加速）

### 4.1 运行结果（`run_perf_bench.py --quick`，真实）

```
求解器性能基准 PASS：
  greens（2D 格林函数）:  numpy → numba 加速 30.0×，物理一致 rel=4.8e-16
  透射谱 3 case:          numpy ↔ numba 结果一致 rel=1.45e-15，overall 2.0×
  GPU 基准:               SKIP（CUDA 不可用——优雅降级，非失败）
```

- 说明：quick 模式用小网格；完整模式记录（D-107 复核）：greens **76.89×**、3D adjoint 大域 **27.6×**（≥20× 阈值）、FOM rel=1.3e-16（bit-level）
- **加速链设计**：纯 numpy（正确性基线）→ numba JIT（CPU 加速）→ torch（GPU 可切）；缺失环境自动降级，无 numba 回退纯 numpy 仍正确

### 4.2 关键命令

```bash
python lda/run_perf_bench.py --quick            # 快速性能基准（秒级）
python lda/run_perf_bench.py                    # 完整基准（分钟级，与历史基线对比）
python lda/run_perf_adjoint3d.py                # 3D adjoint 性能（27.6× 验收）
```

---

## 5. 生态链实操：社区贡献 → 权威 ORACLE

### 5.1 全链演示（真实运行）

```
① 提交    submit_benchmark_proposal → accepted_pending
          （B19 微环 FSR：FSR=c/(n_g·L)，oracle_fn=b19_micro_ring_fsr）
② 评审    review_proposal(approve, 评审人甲) → approved
          （具名人工评审，附 ORACLE 源码；LLM 不进判决路径）
③ 落地    land_proposal → landed（确定性自测值 749.48 GHz）
          （自动注册进 harness golden，实时纳入统一回归）
④ 发布    publish_proposal(杜玉河) → published
          （生成 golden.py/benchmarks.py 可 git apply 补丁 + Release Notes）
⑤ 归档    list_published → [('B19', '杜玉河')]
          （补丁经维护者 git apply 合并后成为权威版本控制内容）
```

### 5.2 治理红线

- 全链**确定性门禁**：签名完备性 / 数值界限 / core 双评审 quorum / 提交期防重 / 白名单 / 最短源码
- 判题 = 死标量比对（LLM 不进判决路径）；**落库(live) ≠ 进版本控制**，权威以维护者 git 提交为准
- 实证语料同管道：citation 必填（无引用不予收录）→ 具名评审 → 落库 → harness E 题实时生效

---

## 6. WebUI 图文操作（五十七面板）

启动：`python lda/lda_webui/app.py` → 浏览器打开（默认端口 3006）。以下为真实截图（`docs/images/`）。

### 6.1 首屏（自动演示，能力总览）

![WebUI 首屏](docs/images/01_webui_top.png)

加载即自动运行核心演示（求解器/裁判/生态）；顶部为系统定位横幅。

### 6.2 谱形目标逆设计面板（㊶ D-80）

![谱形逆设计面板](docs/images/02_spectral_inverse.png)

操作：选择目标类型（分束比/谱形/模式匹配）→ 填目标 → 运行 → 查看 FOM 提升曲线与验收结果（案例三即此面板能力）。

### 6.3 实证大数据锚判题（面板 57 · D-62）

![实证锚判题面板](docs/images/03_empirical_judge.png)

操作：选 E 题 → 输入候选值 → 判题（死标量比对 |cand−measured|≤σ，LLM 不进判决路径）；下方为语料提交流（citation 必填 → 评审 → 落库）。

### 6.4 生态共建框架（面板 53 · D-93）

![生态面板](docs/images/04_ecosystem.png)

harness 21 题 + 主权依赖 A/B/C + Registry 入口实时状态；面板 54-57 分别承载提交 / 评审落地发布 / 实证锚。

---

## 7. 通用方法论：设计→验证闭环

### 7.1 工作方式（四步）

```
① 定义目标（器件 + 指标 + 阈值）
② 参数化/扫描 或 逆设计（几何网格 / 伴随法拓扑）
③ 真实求解（FDTD / 严格对角化）
④ 死标量验收（物理定律锚 / 实证锚，LLM 不进判决路径）→ PASS 交付 / FAIL 诊断重设计
```

### 7.2 判题哲学

- 判决 = **确定性死标量比对**（|candidate − oracle| ≤ tol），**LLM 永不进判决路径**（红线）
- Oracle 两类：**物理定律锚**（解析解/严格对角化/自成像对称必然推论）+ **实证锚**（真实测量语料，citation 必填）
- 落库(live) ≠ 进版本控制；权威内容以维护者 git 提交为准

### 7.3 迭代是特性

验收 FAIL **不是失败**——它暴露真实物理约束（带宽、非谐性、收敛率、损耗），驱动重设计。单波长"看起来对"不等于可用，谱形/多判据验收才能交付可靠设计。

---

## 8. 四入口对照

| 入口 | 适合场景 | 手册案例 |
|---|---|---|
| WebUI 面板 | 可视化验证 / 演示 / 生态操作 | §6（截图实操） |
| CLI / run_*.py | 批量、脚本化、性能基准 | §4（性能） |
| 库级 API | 深度定制 / 二次开发 | §1/§2/§3/§5（全部案例） |
| L1 Agent（MCP/CLI） | 自动化编排、verify_design 判题 | run_agent.py / run_l1_agent_smoke.py |

---

## 9. 附录

### 9.1 本手册相关文件

| 文件 | 说明 |
|---|---|
| `lda/lda_l2/primitives.py` | MMI/taper/光栅等基元几何生成（`mmi_descs`） |
| `lda/lda_solver/port_sparams.py` | MMI 2D FDTD + S 参数 + D-72 验收 |
| `lda/lda_solver/transmon_solver.py` | transmon 哈密顿量严格对角化（Koch 对拍） |
| `lda/lda_solver/qubit_resonator_solver.py` | D-88 色散读出严格求解（χ/n_crit/Purcell） |
| `lda/lda_agent/spectral_inverse_design.py` | D-80 谱形目标逆设计（伴随法拓扑优化） |
| `lda/lda_design/design_engine.py` | DesignEngine 参数化设计入口（Waveguide/Bragg/Transmon/Ring） |
| `lda/lda_pdk/` | 生态链（submit → review → land → publish） |
| `lda/reports/mmi_1550_design.json` | 案例一设计报告 |
| `lda/reports/qeda_ej15_readout_design.json` | 案例二设计报告 |
| `docs/images/01~04_*.png` | WebUI 实测截图（§6） |

### 9.2 环境要求

- Python 3.13 venv（必装 numpy/scipy/jsonschema；可选 numba/torch 加速，缺失自动降级）
- 全部案例零外部 EDA 依赖（自研求解器 + 物理定律锚）

### 9.3 复现命令

```bash
# 案例一（MMI）：smoke 已内置
python lda/run_webui_api_smoke.py            # 路由层门禁
# 案例二（QEDA）：
python lda/run_quantum_design_smoke.py       # 量子设计 smoke
# 案例三（逆设计）：
python lda/run_spectral_design_smoke.py      # 谱形逆设计 smoke（正例+负例）
# 性能 / 生态：
python lda/run_perf_bench.py --quick         # 性能基准
python lda/run_ecosystem_publish_smoke.py    # 生态链全链 smoke
```

### 9.4 后续扩展方向

- MMI：3D FDTD 复验（需 GPU，D-89 numba 路径）+ 多模干涉成像点逐点分析
- Transmon：D-91 纵深三件套（多能级展开 / Rabi+AC Stark / ZZ 串扰）+ 退相干工程参数
- 逆设计：多起点扫描自动化、目标函数工程化（收敛率改进）
- 真实 PDK 数据经社区评审流流入后，几何/工艺参数可对接真实流片（发动期 D-62 联动）

---

*本文档由 LDA 系统真实运行数据整理；所有验收判据均为确定性物理定律锚，LLM 不进判决路径。*
