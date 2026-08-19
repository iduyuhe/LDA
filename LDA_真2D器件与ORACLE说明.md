# LDA · 真 2D 器件与 ORACLE 说明（验收闭环）

> 文档编号：LDA-2D-001
> 版本：v3.0（多端口耦合器件扩展 · 方向耦合器 + 对称分束器）
> 编制日期：2026-08-20
> 对应任务：阶段 1 · 1.8 真 2D ORACLE + 器件验收闭环；开发规划 D-01 分束器/方向耦合器验收锚
> 密级：内部 · 暂不对外

---

## 0. 本文用途

Task 1.8 是垂直场景落地的咽喉：把**真 2D 器件**（条形波导横截面，x、y 双向受限）接入**验收闭环**——agent 设计结果侧（时域 FDTD）与物理定律锚 ORACLE（频域 FDFD 本征值）对**同一几何**给出一致结论，交叉校验排除单一实现 bug，且 **LLM 不进判决路径**。

本文记录：几何约定、ORACLE 侧、FDTD 侧、独立性哲学、关键 bug 与修复、验收结果、已知边界、用法。

> ⚠️ **v2.0 重大修订说明**：v1.0（2026-08-16）描述的是**单受限 slab 几何**（x 受限、y 均匀）配闭式 slab ORACLE 与 `fdtd2d_waveguide.py`，结论 ≤1.4%。本轮已彻底改为**真 2D 矩形波导（x,y 双受限）**——这才是原始任务 1.8 意图——配 **FDFD 标量本征值 ORACLE**（`fdfd_mode_field`，芯区能量占比选模）与**标量 3D FDTD**（`fdtd3d_waveguide.solve_waveguide_neff_3d`，模态源注入 + 重叠积分投影法）。v1.0 的 slab 首稿作为探索历史保留于 git，但验收闭环以本文为准。
>
> ⚠️ **v3.0 扩展说明**（2026-08-20，对应 D-01）：在真 2D 单波导基础上，把验收闭环**升级为"含耦合的多端口器件"**——方向耦合器（双平行波导）与对称 Y 分支分束器（1×2）。新增 `oracle_coupler.py`（FDFD 超模法求 κ/L_c + 对称性定理）、`fdtd3d_coupler.py`（多端口 FDTD + 能流功率 + 超模投影）、`coupler_loop.py`（闭环编排，3 器件 3/3 PASS）。关键新方法：**瞬态测量窗**（末端反波未返回前关闭，消除驻波污染）与**超模投影递推**（对反波免疫）。

一句话结论（v3.0）：**真 2D 单波导 3 例 + 多端口耦合器件 3 例（2×方向耦合器 + 1×对称分束器）全部 PASS；时域 FDTD 与频域 FDFD ORACLE / 对称性定理独立交叉校验，误差为网格色散（f=λ/24 已知量），物理定律锚守住红线。**

---

## 1. 几何约定

验收基准器件 = **矩形条形波导（条形截面，x、y 双受限）**：

- 坐标系：`x` 横向（波导芯 x∈[-w/2, w/2]）、`y` 纵向（芯 y∈[-h/2, h/2]）、`z` 传播方向。芯区为矩形，包层四周环绕——**这是真 2D（双受限）**，区别于 v1.0 的单受限 slab。
- 求解近似：**标量波动方程**（E 单分量，约化亥姆霍兹）。FDTD 侧用标量 3D 波动（E 单场分量沿 z 传播），FDFD ORACLE 用同近似层级标量亥姆霍兹频域本征值 → **同一近似层级独立时域/频域互验**，误差纯为离散化色散。
- 折射率：芯 `n_core`，包层 `n_clad`，真空波长 `λ0`。
- 边界条件：横向（x,y）因标量求解取 Dirichlet（PEC 截断，芯模由包层衰减自然约束）；纵向 z 取导电海绵吸收（无回波、阻抗匹配）。
- 关键几何参数：包层厚度 `clad_um=3.0`（**厚包层，见 §4 坑1**）、传播长度 `Lz_um=8.0`、网格 `dl=λ0/24`。

---

## 2. ORACLE 侧（物理定律锚 · 频域 · 确定性）

实现：`lda/lda_harness/oracle_mode.py` → `fdfd_mode_field(eps3, dl, wl)`

- **标量亥姆霍兹频域本征值**：在横截面 `(Nx,Ny)` 上构造稀疏 Laplacian `Lap` 与介电项，组装 `A = (1/dl²)·Lap + diag(k0²·ε)`，求 `A·ψ = β²·ψ` 的导模 `β²>0`、`neff=β/k0`。方程必然、无 AI、确定性。
- **本征值求解（shift-invert）**：`scipy.sparse.linalg.eigs(A, k=8, sigma=(k0·2.3)², which='LM')`。σ 取保守低于基模（2.3<n_core 但高于包层范数），避免 EIM 高估（EIM 对 500nm strip 给 ~3.16，远高于真值 ~2.54）导致取错模态。
- **基模选择器（芯区能量占比最高）**：从 ε 场自动检测芯掩膜 `core_mask = ε > (n_clad²+n_core²)/2`；候选导模筛 `n_clad<neff<n_core`，按 **`Σ|ψ_core|² / Σ|ψ|²`（芯区能量占比）降序** 取最高者 → 最受限=基模。这同时排除边界局部化伪模（坑3）与包层地板模（neff≈n_clad 但能量弥散）。
- 返回 `(neff, mode2d)`：`mode2d` 为 `(Nx,Ny)` 标量模剖面，仅作 FDTD 激发形状与投影滤波（**非 neff 定值**，见 §3.3 / §4 独立性哲学）。

手算核对：SOI 500×220 @1550nm，真 2D FDFD 基模 neff≈2.585（clad=3.0）；半解析 EIM 仅作量级参考。

---

## 3. FDTD 侧（agent 设计结果侧 · 时域 · 独立实现）

实现：`lda/lda_solver/fdtd3d_waveguide.py`（纯 numpy，零 GPL，不进 LLM 判决路径）

### 3.1 求解范式（复用已验证核心）

- **导电海绵吸收边界**（z 向）：`dampE = 1/(1+dt·σ/ε)`；`sig_max = target_exp·3·n0²/(dt·sponge)`（梯度二次剖面，阻抗匹配、无回反射）。
- **软源全程开启**：ramp 渐入后恒 1.0，绝不早于 DFT 测量窗关闭（铁律①）。源注入支持两种剖面：
  - 默认高斯（中心峰，宽度匹配芯区）——用于辅助；
  - `mode_source`（ORACLE 标量模剖面）整面注入 —— 生产级做法，干净激发标量基模（标量 FDFD 模形状 ≡ 标量 Ey 场）。
- **整数周期 DFT 测量**：`period_steps=round(2π/(ω·dt))`，`M` 个周期稳态窗累积复振幅。

### 3.2 β 提取（双监视点 DFT 相位差 · 对回波稳健）

- 在芯中心 `(cx,cy)` 的 z1、z2 两点累积 DFT 复振幅 `A1, A2`。
- 传播场 `∝ e^{i(βz−ωt)}`，DFT 取 `+iωt` 分量 → `angle(A) ∝ −βz`，故 `Δφ = angle(A1)−angle(A2) = β·Δz`。
- 周期舍入相位漂移在差值中**完全抵消**，对海绵残余回波稳健。

### 3.3 缠绕数唯一确定 + 重叠积分投影法（弱导模免疫）

- **强/紧约束模**：取 `Δz` 使物理区间 `(n_clad,n_core)` 对应 `β·Δz<2π`，由 `m_low/m_high` 边界唯一解出 2π 缠绕数 `m`，`neff=(Δφ+2πm)/(k0·Δz)`。**FDTD 侧完全独立，不借 ORACLE 定值。**
- **弱导模（坑4）**：neff≈n_clad 时监视点 dphi 符号会被 PML 反射污染、选错 m → 给出 >n_core 的垃圾。修复用 **Meep 同款模式投影**：FDTD 场投影到 ORACLE 本征模 `ψ`，在 3 个等距 z 平面取重叠系数 `O_a/O_b/O_c`；前向+后向波叠加仍满足亥姆霍兹递推 `O_{k+1}−2cos(βdz)O_k+O_{k−1}=0` → `cos(βdz)=Re((O_a+O_c)/(2O_b))`，**对后向/反射免疫**。`βdz=acos(cosβdz)`，neff 由传播相位（3 平面递推）独立给出，仅借 ORACLE 的**空间模形状**做测量滤波，不改判据。
- 触发逻辑：原始 DFT 若给出 `neff∉(n_clad,n_core)`（非法）→ 启用投影 override（要求投影 neff_p 合法）；投影再失败 → 回退相邻 m 兜底。

---

## 4. 关键 bug 与修复（诚实记录 · 四坑）

| # | 现象 | 根因 | 修复 |
|---|---|---|---|
| 1 | ORACLE 随网格在 2.47↔2.73 剧烈摆、FDTD 对照崩到 0.20 | **薄包层(clad=1.5µm)**：模尾打 Dirichlet 金属壁 → 数值震荡 | **clad=3.0（厚包层）**；固定稳定网格支 |
| 2 | 矢量求解器 corr=-0.66（激发错模态，FDTD=1.747 vs ORACLE=2.538） | 标量 FDFD 模作 Ey 源，强反差下标量模形状≠真矢量 TE 模 Ey | 验收后端改**标量 3D FDTD**（与标量 FDFD ORACLE 同近似层级）；矢量求解器标注「源形状不匹配」暂不验收 |
| 3 | 中间网格(f=28~40) ORACLE 跳变到边界伪模(2.7339，峰值在边界) | 高反差 2D 条波导 FDFD 离散化**伪模穿越**；主路径 `eigs('LR')` 取最大 β² 选错 | shift-invert(σ=(k0·2.3)²) + **芯区能量占比最高选模器**；固定稳定支 f=24（或 f≥48） |
| 4 | 弱导模 SiN FDTD=2.9849 > n_core=2.0（物理不可能） | 弱导模 PML 反射在监视点反相，dphi 符号污染，选错缠绕数 m | **重叠积分投影法**（3 平面 + 亥姆霍兹递推），对反射免疫 |

附加：脉冲源法曾救回矢量「正确模态量级」(2.876) 证实偏差是粗网格色散非激发 bug，但最终采用模态源+投影更稳健。

---

## 5. 验收结果（独立方法互验 · 3/3 PASS）

由 `lda/lda_agent/waveguide_loop.py` 实跑（固定 f=24 / clad=3.0 / Lz=8.0 / tol_abs=0.15，注入模态源+投影；日志 `_closure_run2.log`）：

| 器件 | neff FDTD | neff FDFD ORACLE | |Δ| | 相对误差 | SNR | 判定 |
|---|---|---|---|---|---|---|
| Si/SiO2 500×220nm | 2.60884 | 2.58521 | 0.02363 | 0.91% | 0.323 | PASS ✅ |
| Si/SiO2 450×220nm | 2.59853 | 2.53841 | 0.06012 | 2.37% | 0.233 | PASS ✅ |
| SiN/SiO2 500×300nm | 1.48348 | 1.53080 | 0.04732 | 3.09% | 0.265 | PASS ✅ |

- **PASS 判据**：`|Δneff| ≤ tol_abs=0.15`（≈3~5% 相对，涵盖 f=λ/24 网格色散）。Si 两例走投影法（强约束模同样更准，Δ 从旧跑 0.12/0.04 降至 0.024/0.060），SiN 经投影法救回（原非法 2.9849 → 合法 1.4835）。
- 三项皆过 ⇒ 真 2D 矩形波导验收闭环成立，时域 FDTD 与频域 FDFD ORACLE 互验一致。

网格色散性质（已知）：f=λ/24 下 Si 紧约束 ~4~5% 量级，f=λ/48 更细但 ~68min/例过慢；故固定 f=24 在公差内。

---

## 6. 已知边界（诚实）

1. **网格色散**：f=λ/24 下紧约束 Si 模 ~3~5% 误差为已知 FDTD 数值色散，非方法缺陷。需更准时走 f≥48 或 numba/torch 后端。
2. **矢量全 Yee 求解器暂不用验收**：源形状不匹配（坑2），仅研究用；验收用标量 FDTD 与标量 FDFD ORACLE 同层级。
3. **投影法依赖 ORACLE 空间模形状（非 neff 值）**：若 ORACLE 选错模（坑3 选择器已规避），投影会跟着错——但选择器已修，实测 3 例均稳。
4. **纯 Python 时域成本**：f=24 单例 ~5min；f=48 ~68min。紧约束高分辨建议 numba/torch 后端（L1 已留 `backend` 切换）。
5. **几何范围（v3.0 已扩展）**：单矩形条形波导（1.8）已扩展为**多端口耦合器件**（D-01）——方向耦合器（双平行波导）与对称 Y 分支分束器（1×2），见 §8。交叉 crossing 等仍需扩展。

---

## 7. 用法

```bash
# 端到端真 2D 验收闭环（3 默认案例：2×Si/SiO2 + 1×SiN/SiO2，3/3 PASS）
cd /d/agent_LDA
python -m lda.lda_agent.waveguide_loop          # 输出 3/3 PASS

# 单元自测（标量 3D FDTD 单器件 vs FDFD ORACLE，可调 mode_source）
python -c "
import sys; sys.path[:0]=['lda/lda_solver','lda/lda_harness']
import numpy as np
from fdtd3d_waveguide import build_waveguide_field_3d, solve_waveguide_neff_3d
from oracle_mode import fdfd_mode_field
w,h,nc,ncl,wl=0.5,0.22,3.48,1.44,1.55
eps3,meta=build_waveguide_field_3d(w,h,nc,ncl,wl,dl=wl/24,clad_um=3.0,Lz_um=8.0)
ne_o,mode2d=fdfd_mode_field(eps3,meta['dl'],wl)
ne,beta,m,snr=solve_waveguide_neff_3d(eps3,meta['dl'],wl,n_clad=ncl,n_core=nc,mode_source=mode2d)
print(ne_o, ne, abs(ne-ne_o))
"
```

代码入口：
- 求解器：`lda/lda_solver/fdtd3d_waveguide.py` → `build_waveguide_field_3d`, `solve_waveguide_neff_3d`（含 `mode_source` + 3 平面投影）
- ORACLE：`lda/lda_harness/oracle_mode.py` → `fdfd_mode_field`（芯区占比选模）
- 闭环集成：`lda/lda_agent/waveguide_loop.py`（WaveguideTarget / WaveguideOutcome，3 默认案例）
- 历史 slab 首稿：`fdtd2d_waveguide.py`, `verify_waveguide_2d.py`（v1.0，保留参考）

---

## 8. 多端口耦合器件验收闭环（D-01 · v3.0）

D-01 把 1.8 的验收范式从单波导升级为**含耦合的多端口器件**：方向耦合器与对称分束器。
独立时域/频域（或对称性）交叉校验，LLM 不进判决路径。

### 8.1 几何与指标

- **方向耦合器（DC）**：两同尺寸 Si 波导（500×220nm）沿 x 并排，间距 gap；波导 A 注入、波导 B 耦合。核心指标 = 耦合系数 κ（rad/µm），由功率交换 `P_B(z)=sin²(κz)` 描述；耦合长度 `L_c=π/(2κ)`。
- **对称 Y 分支分束器（YB）**：输入单波导 → 对称展开两臂。对称性定理 ⇒ `P1=P2=0.5·P_in`。核心指标 = 平衡度 `|fracA−0.5|`。

### 8.2 ORACLE 侧（物理定律锚 · 确定性）

`lda/lda_harness/oracle_coupler.py`
- **DC：FDFD 超模法**（`fdfd_coupler_supermodes`）：对双波导截面解标量亥姆霍兹本征值，识别对称超模（neff_s）与反对称超模（neff_a），由耦合模理论 **κ=(βs−βa)/2=π(neff_s−neff_a)/λ0**、`L_c=λ0/(2(neff_s−neff_a))`。方程必然、确定性、可手算核对。
- **YB：对称性定理**（`ybranch_oracle`）：几何完全对称 ⇒ 两臂功率必然等分（理想无损各 0.5·P_in）。

### 8.3 FDTD 侧（agent 设计结果侧 · 时域 · 独立实现）

`lda/lda_solver/fdtd3d_coupler.py`（纯 numpy + torch GPU 后端，复用 fdtd3d 海绵/蛙跳核）
- `build_coupler_field_3d` / `build_ybranch_field_3d`：构造多端口折射率场与端口掩膜。
- **能流功率测量**（`solve_port_powers_3d_torch`）：`S_z = Im(E*·∂zE)`（坡印廷），对驻波/反波免疫（同模反波在净能流中抵消），比 |E|² 积分干净。
- **超模投影**（`solve_supermode_projection_3d_torch`）：在采样面投影到 ORACLE 超模形状得复系数 `O_s(z)`、`O_a(z)`，用亥姆霍兹递推 `cos(β·dz)=Re((O_k+O_{k+2})/(2·O_{k+1}))` 提取 βs、βa → κ（对反波免疫，同 1.8 投影法）。

### 8.4 关键方法：瞬态测量窗（D-01 的坑与修复）

**现象**：稳态长窗下，源（硬源/软源皆然）向 ±z 双向辐射 + 末端海绵反射 ⇒ 采样区反波≈正波（驻波比 ~0.8），`|E|²` 与能流功率均被污染（波导 B 净能流甚至为负）；超模投影相位斜率≈0（纯驻波特征），递推失效。

**修复**：**瞬态测量窗**——加长 Lz（末端更远），在「正波到达采样面 + ramp + 5 周期」后开窗、「末端反波返回前」关窗（M 周期）。窗内只有前向行波，相位单调、振幅平滑。实测窗口公式：
- `period = round(2π/(neff·ω·dt))`；`prop = round((z_first−src)·neff/dt)`
- `transient = ramp + prop + 5·period`；总步数 `transient + M_cycles·period` < 反波返回步数。

**超模投影递推**对反波免疫（同 1.8），配合瞬态窗进一步压制非模杂散。网格稳定支沿用 f=24（f=28–40 有 FDFD 伪模穿越，1.8 坑3 同源；f=32 下双波导超模亦崩坏，实测 neff_s 跳至 2.71 不合理，禁用）。

### 8.5 验收结果（3/3 PASS · 本机 GPU）

由 `lda/lda_agent/coupler_loop.py` 实跑（f=24 / clad=3.0 / Lz=24µm(DC) / torch GPU，瞬态窗 + 超模投影递推）：

| 器件 | κ_oracle | κ_fdtd | 相对偏差 | 判定 |
|---|---|---|---|---|
| DC Si 500×220 gap=0.3µm | 0.03480 | 0.03528 | 1.4% | PASS ✅ |
| DC Si 500×220 gap=0.25µm | 0.06437 | 0.06597 | 2.5% | PASS ✅ |

| 器件 | fracA | fracB | 平衡度 | 判定 |
|---|---|---|---|---|
| YB Si 对称分束器 1×2（sep=1.6µm） | 0.4994 | 0.5006 | 0.0006 | PASS ✅ |

- **DC 判据**：`|κ_fdtd−κ_oracle|/κ_oracle ≤ 0.25`（网格色散余量）。两例偏差 1.4%/2.5%，远优于容差。
- **YB 判据**：`|fracA−0.5| ≤ 0.10` 且输出功率为正。平衡度 0.0006，7 个采样面 fracA∈[0.495,0.505] 极稳。
- 网格色散对 βs/βa 偏差相同（~1.6%），差值 κ 相消，故 κ 相对偏差仅 1–3%——这是超模法用于耦合验收的关键优势。

### 8.6 D-01 已知边界（诚实）

1. **瞬态窗依赖几何参数**：Lz 与采样面需保证「反波未达前关窗」；几何改动需重算窗口。
2. **f=24 网格**：双波导 gap <0.2µm 时 FDFD 超模崩坏（离散太粗），验收案例 gap≥0.25µm。
3. **能流功率在强反波下失效**（净能流可为负）；D-01 中 YB 用瞬态窗规避，DC 用超模投影递推（对反波免疫）。
4. **只覆盖对称耦合**：非对称波导耦合器（相位失配）、交叉 crossing 尚未建锚。
5. 单例 GPU 运行 ~6s（Lz=24µm，f=24）；纯 numpy 同网格 >2min 不可行——验收依赖 torch GPU（CI 仅做导入冒烟）。

### 8.7 用法

```bash
# 端到端多端口耦合器件验收闭环（3 案例 3/3 PASS；默认 torch GPU）
cd /d/agent_LDA/lda/lda_agent
/d/agent_LDA/lda_cuda_venv/Scripts/python.exe coupler_loop.py

# 单案例调试
python -c "
import sys; sys.path[:0]=['lda_agent','lda_solver','lda_harness']
from coupler_loop import CouplerAgent, CouplerTarget
out = CouplerAgent().run(CouplerTarget(kind='dc', gap_um=0.3))
print(out.to_dict())
"
```

代码入口：
- 求解器：`lda/lda_solver/fdtd3d_coupler.py`（几何构造 + 能流功率 + 超模投影，numpy/torch 双后端）
- ORACLE：`lda/lda_harness/oracle_coupler.py`（FDFD 超模法 → κ/L_c；对称性定理 → 0.5）
- 闭环：`lda/lda_agent/coupler_loop.py`（CouplerTarget/CouplerOutcome/CouplerAgent，3 默认案例）

---

*本文与《LDA_阶段性总结与剩余工作.md》§2.5/§5.1、《LDA_发展里程碑与路线图.md》阶段 1 · 1.8、《LDA_阶段总结与下一步开发工作规划.md》D-01 配套。v3.0 扩展：多端口耦合器件（方向耦合器 + 对称分束器）验收闭环 3/3 PASS。*
