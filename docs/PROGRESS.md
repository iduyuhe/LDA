# LDA 进度仪表盘（多维计量）

> **本文件由 `scripts/gen_progress_dashboard.py` 生成，请勿手改** ——
> 门禁 `run_p2_usability_smoke` 会重跑生成器比对，零漂移才通过。
> 数据源全部**现算**（账本 / 报告 / 台账 / 路由表），无时间戳。

## 为什么不用「锚数」当主轴

> 🔴 **判决锚已饱和**：86.1% 的锚是闭式/解析类（analytical 249 + closed_form 217 = 466/541）；6 个被判死模块（R_s / cpw_quasi_static / ft_compiler / kinetic_inductance / noise_aware_schedule / conductor_surface）的 why_not_anchored 理由已逐条核实**全部成立**；唯一有实证的新机制（收敛阶锚）验实现不验物理，不能并入同一计数。详见 docs/LDA_F19_锚产出机制诊断_2026-10-25.md

⇒ 锚数仍在表里（它是对外最硬的东西），但**不再单独代表进展**。

## 一、判决层（**已饱和**）

| 指标 | 值 | 状态 |
|---|---|---|
| 账本锚 | **546** | 🔴 饱和 |
| 其中 strict_independent | 524 | — |
| 其中 self_certified | 19 | 已知桩 |
| 其中 degraded | 3 | 已知降级 |
| 闭式/解析类占比 | **471 / 546 = 86.3%** | 🔴 饱和的**证据** |

oracle 类型分布：

| oracle | 数 |
|---|---|
| `analytical` | 249 |
| `closed_form` | 222 |
| `special_function` | 19 |
| `empirical-measurement` | 10 |
| `physical-law` | 6 |
| `scipy.special.iv` | 6 |
| `scipy.special.exp1/expn` | 5 |
| `正交归一恒等式 = 1（精确）；均匀网格（θ×φ）复合梯形球面积分 N=160` | 5 |
| `scipy.special.betainc（精确特殊函数 oracle） + composite-Simpson double-integral independent_cross_check` | 5 |
| `design-rule` | 4 |
| `statistical` | 4 |
| `scipy.special.sici（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check` | 4 |
| `deterministic` | 3 |
| `integer-parameter binomial closed form Σ_{j=a}^{a+b-1}C` | 2 |
| `scipy.special.shichi（精确特殊函数 oracle） + RK4-defining-ODE integration independent_cross_check` | 2 |

## 二、证据层（活跃）

> 锚「通过」不等于「已验证」。本层回答：**每一条判决的证据到底是什么强度的**。

| 证据档 | strict 内 | 全体 |
|---|---|---|
| `RESIDUAL_NONZERO`（有残差证据） | 510 | 513 |
| `PERTURBATION_RESPONSE`（靠扰动响应，**弱证据**） | 14 | 14 |
| `STUB`（桩） | 0 | 19 |

> `PERTURBATION_RESPONSE` **只证明「候选真在算」**，不证明方法学独立。

## 三、覆盖层（活跃）

| 指标 | 值 |
|---|---|
| 锚总数（覆盖分母） | 546 |
| 盲区（无任何门禁覆盖） | **0** |
| 盲区（无子集覆盖） | 0 |

盲区按号段：`{"B1–B99": 2, "E（实证）": 5, "S（系统层）": 10}`

## 四、契约层（活跃）

| 指标 | 值 | 意义 |
|---|---|---|
| CI core 门禁成员 | **379** | 每道闸防一类退化；成员只增不减 |

## 五、接口层（活跃）

| 指标 | 值 |
|---|---|
| REST 端点 | **159**（需登录 60） |
| 端点有描述 | 159 |
| 案例面板族 | **19** |

## 六、待改层（**本层最能说明「还差什么」**）

| 指标 | 值 | 说明 |
|---|---|---|
| 案例卡缺口 | **127** | 并账后总数（**四值口径**） |
| 已闭合 | 70 | 证据链可查 |
| 已结算 | 11 | 已裁决**不再挂账**，但能力/证据未必具备 |
| 🔴 **未闭合（真欠债）** | **0** | 确认仍未做 —— **只有这一列是欠债** |
| 边界声明 | 46 | 永久能力边界，**不是欠债** |
| 无状态标记 | 0 | 应为 0（棘轮守，>0 即拒跑） |

> 🔴 说「127 条缺口」时**必须带分布**：把「边界声明」读成欠债、把「已结算」读成已完成，都是误读。

> 详见 `docs/GAP_SETTLEMENT.md`（同样由生成器产出，门禁 ⑬ 守）。

## 七、签核维度（另有专表）

18 张案例卡的 grade × evidence × deck 三维、以及**对外可宣称口径**，
见 `GET /api/signing`（`lda_harness/signing_schema.py` 为真源）。

> 🔴 **18 张卡无一可进对外材料**（`allow_external=[]`）—— 全项目零对外签核，
> 因为没有一张卡的 deck 是 NDA。这是事实登记，不是缺陷遗漏。
