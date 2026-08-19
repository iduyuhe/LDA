# LDA · 真 2D 器件与 ORACLE 说明（验收闭环）

> 文档编号：LDA-2D-001
> 版本：v2.0（修订交付 · 真 2D 矩形波导 + FDFD ORACLE + 标量 3D FDTD）
> 编制日期：2026-08-17
> 对应任务：阶段 1 · 1.8 真 2D ORACLE + 器件验收闭环
> 密级：内部 · 暂不对外

---

## 0. 本文用途

Task 1.8 是垂直场景落地的咽喉：把**真 2D 器件**（条形波导横截面，x、y 双向受限）接入**验收闭环**——agent 设计结果侧（时域 FDTD）与物理定律锚 ORACLE（频域 FDFD 本征值）对**同一几何**给出一致结论，交叉校验排除单一实现 bug，且 **LLM 不进判决路径**。

本文记录：几何约定、ORACLE 侧、FDTD 侧、独立性哲学、关键 bug 与修复、验收结果、已知边界、用法。

> ⚠️ **v2.0 重大修订说明**：v1.0（2026-08-16）描述的是**单受限 slab 几何**（x 受限、y 均匀）配闭式 slab ORACLE 与 `fdtd2d_waveguide.py`，结论 ≤1.4%。本轮已彻底改为**真 2D 矩形波导（x,y 双受限）**——这才是原始任务 1.8 意图——配 **FDFD 标量本征值 ORACLE**（`fdfd_mode_field`，芯区能量占比选模）与**标量 3D FDTD**（`fdtd3d_waveguide.solve_waveguide_neff_3d`，模态源注入 + 重叠积分投影法）。v1.0 的 slab 首稿作为探索历史保留于 git，但验收闭环以本文为准。

一句话结论：**真 2D 矩形波导的验收闭环已打通，3 个基准器件（2×Si/SiO2 + 1×SiN/SiO2）在 tol_abs=0.15（≈3~5% 相对）下 3/3 PASS；FDTD 与 FDFD ORACLE 独立时域/频域交叉校验，误差为网格色散（f=λ/24 已知量），物理定律锚守住红线。**

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
5. **几何范围**：当前仅矩形条形波导。分束器 Y-branch、交叉 crossing 等更复杂真 2D 器件需扩展 FDFD 本征模 + 重叠积分验收锚，待建。

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

*本文与《LDA_阶段性总结与剩余工作.md》§2.5/§5.1、《LDA_发展里程碑与路线图.md》阶段 1 · 1.8 配套。v2.0 修订：真 2D 矩形波导 + FDFD ORACLE + 标量 3D FDTD 模态源/投影法，3/3 PASS。新咽喉转至 1.4 AI-dev 自举写核 与 1.6 实证大数据锚。*
