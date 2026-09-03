# Changelog

## v0.9.27（2026-09-03 · T-1 判据 D 立法 · 全 20 道独立候选普查 · 0 道假独立）

**指令**：「T-1」（技术侧路线图 `docs/lda_tech_roadmap_2026-09-03.md` 第一优先级）。

**三分类不变**：**严格独立 20 道 · 降级量级参考 0 道 · 自证桩 28 道（三类和 = 48）**
—— 普查结论：**20 道宣称无一虚报，独立数无需下调。**

---

### 一、判据级缺陷 D 的发现与立法

现行行为判据（v0.9.24/25 立的 `candidate_responds`：「残差≡0 **且** 扰动无响应 ⇒
自证桩」）拦得住「裸桩」（`return golden`），**拦不住「数学等价的另一种写法」**：

- **实测反例 B28**：候选=沿程积分+二分（`mzm_vpi_integral`，已在代码里），golden=
  解析闭式。均匀段 `Σ Γ_i·Δz_i ≡ Γ·L`（**剖分守恒**，docstring 自认"退化等于闭式"）
  ⇒ 二者**代数恒等**；但扰动 n_eff 时两式**同步响应** ⇒ `candidate_responds`=True
  ⇒ 若接此候选会被误判「独立」——虚报。
- **判据 D（新增）**：固定物理参数，只扫**候选自身的离散参数**（步长/段数/网格/
  截断维数）。真数值方法的**截断误差**必然随离散参数变化（粗端浮出噪声地板、
  随加密单调下降、收敛阶与算法标称阶一致）；代数恒等式的残差**任何档位恒
  ~1e-16 纹丝不动** ⇒ 判假独立，不计入独立候选数。
- **落地**：`candidate_discretization_responds()` 定义于 `lda_harness/harness.py`
  （与 `candidate_responds` 同文件 = 单一定义处纪律）。

### 二、判据 D 的双向验证（正例/反例都实测）

| 例 | 扫描 | 残差 | 判定 |
|---|---|---|---|
| **B10** RK4 vs 解析闭式（t/T1=1.0 未收敛点，扫 n_steps 2→512） | 3.86e-4 → 1.84e-5 → 1.00e-6 → 3.55e-9 → 1.35e-11 → 5.24e-14 | n 每加倍降 ~21×（首段比 21.0）⇒ **O(h⁴)** | ✅ 真独立 |
| **B28** 沿程积分 vs 闭式（扫 n_segments 10→20000，2000×） | **恒 4.44e-16 纹丝不动** | 代数恒等 | ❌ 假独立（护栏会响） |
| B9 对角化（扫电荷基 N 2→512） | 5.1 → 0.34 → 7.2e-3 → 收敛 7.3e-3 | 截断收敛清晰 | ✅ |
| B23 对角化（扫 ncut 2→512） | 2.4 → 1.3 → 7.7e-2 → 1.5e-12 → 4.2e-14 | 收敛后贴地板（印证 ncut 钉 24 勿再加的铁律） | ✅ |

⚠️ **判据 D 必须双向标定（B10 差点被误判）**：默认参数 `t/T1=5e-4` 时 RK4 截断
误差 ~1e-22 **沉在双精度噪声 1e-16 之下**（过度收敛区）⇒ 真独立的 B10 残差也恒
1.11e-16，与 B28 不可区分。**必须在「未完全收敛」的物理参数点扫离散档位**，
窗口 `1e-15 < 粗端残差 < tol`（与既有「网格/截断双向标定」铁律同源）。

### 三、全 20 道已接线候选的普查（T-1 主体）

**方法**：逐道测基线残差 `|cand−golden|`。代数恒等在**值域上**只能给 ~1e-16；
残差 >1e-12 即排除恒等。

**结果**：
- **19/20 道基线残差 1.85e-8 ~ 1.5e-2**，全部远高于恒等特征 ⇒ 值域排除代数恒等。
- **B10 唯一基线=0**（过度收敛区特例）⇒ 判据 D 深验通过（O(h⁴)，见上表）。
- **结论：0 道假独立，独立候选 20 的宣称经查属实，无需下调。**
- 附带：20 道候选类型总表（数值对角化 9 道 / 谱峰拟合 4 道 / 数值积分 2 道 /
  传播模拟 3 道 / 解析互证 2 道），判据 D 适用面与人工论证面已划清。

### 四、常驻护栏 `run_d_criterion_smoke.py`（9/9 PASS，~15s，入 CI core 88→89）

九项断言：① B10 正例判据 D PASS ② B10 收敛阶 O(h⁴) ③ **B28 反例必须 FAIL
（证明护栏会响——没被验证过的护栏不算护栏）** ④ 20 道登记完整 ⑤ 20 道基线残差
普查（B10 特例豁免并注明）⑥ B9 截断响应留痕 ⑦ B23 截断响应留痕 ⑧ B23 ncut=32
贴地板印证双向标定铁律 ⑨ 单一定义处导入检查。

**三处同步登记**（v0.9.24 铁律）：`run_ci_regression.CORE_SMOKES` + `TIMEOUTS`
(180s) + `run_ci_industrial_smoke._SLOW_CORE`。README「当前账本」CI core 88→**89**，
`run_count_consistency_smoke.py` 11/11 OK。

### 五、验证无回归

- `run_benchmark_falsifiability_smoke.py`：**12/12 PASS**（独立 20 / 降级 0 /
  自证 28 口径不变）。
- `run_ci_industrial_smoke.py`：内部子回归含 d_criterion 全绿（见 CI 日志）。

---

## v0.9.26（2026-09-03 · B8 锥度传输 EME 接线 · 严格独立 19 → 20）

**指令**：延续 P0 接线段（B8 绝热锥度传输锚）。

**三分类刷新**：**严格独立 20 道 · 降级量级参考 0 道 · 自证桩 28 道（三类和 = 48）**

---

### 一、B8 候选接线：`taper_eme`（本征模展开）

| 项 | 内容 |
|---|---|
| 锚 | B8「绝热锥度传输 T→1」，`w1=0.2 / w2=0.5 / L=200µm / λ=1.55 / n_eff=2.44 / n_clad=1.44`，`tol=0.01` |
| golden | 常量 1.0（`b8_taper_transmission`，绝热定理 + 能量守恒硬约束）|
| 候选 | 新写 `lda/lda_solver/eme_taper.py`：EME 本征模展开（每切片解**完整 Helmholtz 本征值问题** `scipy.linalg.eigh_tridiagonal`，无旁轴假设；切片间**模式重叠矩阵**投影；功率守恒内建 T≤1）|
| 方法学独立 | golden 是常量上界（不知道锥度怎么演化）↔ 候选逐切片解本征模并投影，全然不同的物理路径 |
| 实测 | 正向 T=**0.999953504**，1−T=**4.65e-5**（占 tol 的 0.47%，严格非零故可标定）；反向非绝热短锥 `w2=3.0 / L=1.0` ⇒ T=**0.43528**、越界量 0.5647 ≫ tol ⇒ 必 FAIL |

### 二、🔴 BPM 两轮实测证否（模型误差，不是数值误差）

先写 `lda_solver/bpm_taper.py`（分步傅里叶束传播）。**第一轮**（dz 过大）：调 dz 至 0.05、模式数至 64，T 全域稳在 0.9956~0.9969，**与 L 无关** ⇒ 判据零判别力。**第二轮**（换掉固定的 n_slices 之后）：物理趋势**反号** ——

| L (µm) | T |
|---|---|
| 2 | 0.9967 |
| 25 | 0.9936 |
| 200 | 0.9729 |

绝热定理要求 **L 越长 T 越高**，实测却是**单调下降**，且**减小 dz / 加密横向网格均不收敛** ⇒ 这是旁轴近似本身的**模型误差**（展开参数 ≈65%，伪辐射随传播长度累积），不是离散化误差。**减小步长不收敛 = 必须换模型**，这一条已写为铁律。

处置：`bpm_taper.py` **已删除**（教训转移至普查文档与 EME 模块注释），不留失效求解器污染代码库。

### 三、🔴 EME 三个坑（全部钉进生产模块 docstring + 常驻 smoke）

1. **固定 `n_slices` ⇒ 判据零判别力**。Δw 与 L 无关，且 L=200µm 时 dz=1µm 使 Δβ·dz 达 ~5 rad/片严重欠采样 ⇒ T 在 L=2 与 L=200 同为 0.996。修：改为**按 dz 推导切片数** `DEFAULT_DZ=0.4`、`nsl = max(MIN_NSLICES=20, round(L/dz))`。
2. **折射率剖面硬判据 ⇒ 锥度被离散成 ~8 次突跳**。dx=0.02µm 时半宽只跨 7.5 个网格 ⇒ 4000 片里只有 ~8 个不同剖面，物理上是 8 个突变结而非锥度。修：改为**亚网格面积加权**（对 n² 按格心覆盖比例平均）。
3. **倏逝模两连错**。`np.maximum(w_, 0)` 把 β²<0 截断成 β=0（**不衰减**，物理错）；改复数 sqrt 后又因 `sqrt` 取**主值 +i|β|**，使 `exp(−i·(+i|β|)·dz) = exp(+|β|dz)` 变成**指数增长**（L=5µm → 4e30，L=200 → inf/nan）。修：正确分支是 **Im(β)<0**（衰减），`betas = np.where(betas.imag > 0, -betas, betas)`。

### 四、✅ 模式解算器的独立验证（非自证）

- 数值 n_eff(w=0.2) = 1.85897~1.85966 ↔ 平板 TE0 解析色散 `u·tan u = √(V²−u²)` 的 **1.85971**
- 数值 n_eff(w=0.5) = 2.21911 ↔ 解析 **2.21863**
- dx 减半误差降 **O(dx²)**（收敛比值严格 → 4.00）

**自校锚从「单点阈值」改为「收敛到解析值」**：原本设阈值 5e-4 出现假 FAIL（实测 7.37e-4 / 4.83e-4 / 8.33e-5），但**不拍脑袋放宽阈值**——改做 dx 收敛探测，确认 O(dx²) 后改判 `max|Δ| < 1e-4 且 min 降幅 ≥ 8×`（实测 16× / 24× / 16×）。这比放宽阈值更强：**解算器若错就收敛不到解析值**。

另：单调性自校锚**只取已收敛区 L≥5µm**（L≲2µm 时窗口 8/16/32 相差 4e-3），不拿未收敛区充数。

### 五、反向测试

B8 单扰 L 无法击穿 tol（L 越长越绝热，方向相反），故反向改用**非绝热短锥** `w2=3.0µm / L=1.0µm` ⇒ T=0.43528、越界量 0.5647 ≫ tol ⇒ 判 FAIL。已钉入 `run_benchmark_falsifiability_smoke.py` 第 ③″ 项。

### 六、🔴 常驻护栏 `run_eme_taper_smoke.py`（9/9 PASS，~33s，入 CI core 87→88）

八项断言：①求解器九条自校锚全 PASS ②tol/golden 读自 `BENCHMARK_DEFS`（不硬编码）③candidate 必须是 `taper_eme`（防回退自证桩）④正向 PASS ⑤1−T **严格非零且 < tol** ⑥反向非绝热必被抓 ⑦数值档位防漂移 ⑧突变结下界（0.98525）对照。

同步登记三处（遵守 v0.9.24 铁律）：`run_ci_regression.CORE_SMOKES`、`run_ci_regression.TIMEOUTS`(+400s)、`run_ci_industrial_smoke._SLOW_CORE`。

### 七、⚠️ 诚实边界（四条，均已实测）

1. 余量 4.65e-5 很小 ⇒ 只宣称「1−T 非零且可标定、量级合理」，**不宣称精度验证**。
2. **EIM 降维**：垂向压成常数 n_eff，是横向一维问题，非完整 2D/3D。
3. **单向近似**：逐切片前向投影，不含背向反射的多次往返累积。
4. **短锥度未收敛**：L≲2µm 时计算窗口 8/16/32 相差 4e-3。

### 八、🔧 顺带修正：E3 循环论证标注

`run_empirical_anchor_smoke` 的 E3 断言原写「实测↔解析**交叉验证**」。但语料 `method` 字段明写「实测 FSR，**反算 n_g=4.92**」⇒ golden 与解析式**共用同一 n_g**，不是独立验证。已改标为「**自洽性检查（非独立交叉验证）**」，并注明：n_g 每变 0.01 ⇒ FSR 变 0.021nm，而所谓"吻合"仅 0.024nm，等于舍入噪声。

---

## v0.9.25（2026-09-03 · B19 无源无增益接线 · 首开不等式锚 cmp='le' · 严格独立 18 → 19）

**指令**：延续 P0 接线段（B19 无源链路无增益上界锚）。

**三分类刷新**：**严格独立 19 道 · 降级量级参考 0 道 · 自证桩 29 道（三类和 = 48）**

---

### 一、B19 候选接线：`link_passivity`（首开不等式锚 cmp='le'）

| 项 | 内容 |
|---|---|
| golden | 常量上界 1.0（`b19_link_passivity_bound`，无源性/能量守恒硬约束，**不依赖任何模型**）|
| 候选 | `lda_chain` 真实链路引擎端到端级联：`build_wdm_link → route_and_simulate → max_transfer_of`（消费 `alpha_cm` 布线损耗 → `net_loss_db` → 级联）|
| 比较 | `cmp='le'`（越界量 `max(0, cand−oracle)`），损耗合法、增益 FAIL |
| 方法学独立 | 最强一档：golden 是物理硬约束常量，候选是整条工程师序，候选甚至不知道 golden 是多少 |

### 二、🔴 path① cmp 分发修复（B19 假 FAIL 根因）

`build_harness_specs` 对所有物理定律锚硬编码 `compare_fn=cmp_abs`，把 B19 的 `cmp='le'` 上界当绝对误差判定 ⇒ candidate=0.9998962、golden=1.0 判 `|0.9999−1.0|=1.04e-4 > tol 1e-9` 假 FAIL。

修复：`verification_spec.py` 新增 `cmp_le`/`cmp_ge`/`compare_fn_for`，`verification_adapters.py` 按 `d.get("cmp", "abs")` 分发。修复后 forward `passed=True err=0.0`。

### 三、🔴 行为判据 v0.9.25 升级（抓常量缩放桩）

`candidate_responds` 从「比 golden」改为「比候选自己基线 `base=cand_fn(spec, oracle)`」。否则「返回 golden×0.99988 的常量缩放桩」（完全不看 params）在不等式锚上会被误判「有响应」而漏过——实测攻击演示 old=True 漏过、new=False 抓到，且 **18 道现有独立锚口径零回归**。

### 四、B19 反向测试 = 注入负增益（非参数 ±10%）

不等式锚的「参数 ±10% 扰动」仍无源（不会让 max|T| 越过 1），必须 monkeypatch 弯曲损耗翻负注入增益：注入 −0.3/−0.5/−1.0 dB/cm ⇒ max|T| 1.0033/1.0056/1.0112 全部 >1 判 FAIL。smoke 第 ③′ 项钉死。

### 五、⚠️ 诚实边界

余量仅 **1.2e-4**（离共振 thru 路径的残余弯曲损耗），已写入 note。全量 smoke `run_benchmark_falsifiability_smoke.py` **11/11 PASS · 严格独立 19 · 自证桩 29/48**。

---

## v0.9.24（2026-09-03 · B10 门保真度接线 + D-66 第 8 例 · 严格独立 17 → 18）

**指令**：延续 P0 自证段（B10 量子门保真度锚接线）。用户明确要求：**本轮自证完成前不发布、不部署** ⇒ 全程零 commit / 零 push / 零部署。

**三分类刷新**：**严格独立 18 道 · 降级量级参考 0 道 · 自证桩 30 道（三类和 = 48）**

---

### 一、新写候选 `lda/lda_solver/lindblad_gate_fidelity.py`（纯 numpy、零外部依赖、零 GPU）

| 步骤 | 内容 |
|---|---|
| 主方程 | `dρ/dt = γ₁·D[σ₋]ρ + γ_φ·D[σ_z]ρ`，`γ₁=1/T1`，`γ_φ=(1/T2 − 1/(2T1))/2` |
| 超算子 | 4×4，row-major vec：`vec(AρB)=(A⊗Bᵀ)vec(ρ)` ⇒ `D[A]=A⊗conj(A) − ½[(A†A)⊗I + I⊗(A†A)ᵀ]` |
| 积分 | RK4，`N_STEPS=50`，对 **4 个 Pauli 基各积分一次** ⇒ 完整 PTM |
| PTM | `PTM[i,j] = ½·Tr[σ_i·Λ(σ_j)]` |
| 保真度 | `F_avg = ½ + (Λ_xx+Λ_yy+Λ_zz)/6` |

↔ **golden = 解析闭式** `(3 + 2e^{−t/T2} + e^{−t/T1})/6`（Nielsen & Chuang，d=2；独立 `math.exp` 实现）。

**方法学独立性凭据**：候选**不套任何衰减率闭式**、**不假设 PTM 对角**。实测 `PTM[Z,I] = −2.4997e-4` 是**非对角下三角元**（振幅阻尼把激发态布居转到基态），而闭式里根本没有这一项 —— 候选比 golden 多解出一个 golden 没描述的自由度。

---

### 二、🔴 D-66「怀疑 golden 本身」第 8 例：B10 旧 golden 被证否

**旧 golden**：`F = exp(−t·(1/T1 + 1/(2·T2)))`

**发现入口（不是怀疑公式，是接不出判据窗口倒查上来的）**：接候选时逐键标定判据窗口，发现旧 golden 与严格解**基线差 2.638e-4**，而**全部 10% 扰动信号只有 1.5e-5~4.2e-5** ⇒ 基线差 > 任何扰动信号 ⇒ **判据窗口在旧 golden 下不可能成立**。

**证否过程**：逐个排查四种标准保真度定义的一阶系数，均不匹配 ——

| 定义 | 一阶系数 | 与旧式 `1/T1 + 1/(2T2)` 比 |
|---|---|---|
| 平均门保真度（采用） | `(1/T1 + 2/T2)/6` | 旧式是其 **2.727×** |
| 纠缠保真度 | `(1/T1 + 2/T2)/4` | 不匹配 |
| \|+⟩ 态保真度 | `1/(2T2)` | 缺 T1 项 |
| Haar 平均态保真度 | `(1/T1 + 2/T2)/4` | 不匹配 |

比值恰为 **30/11**，无物理来源。**结论：旧式不对应任何标准保真度定义，是经验式。**

**新 golden**：`(3 + 2e^{−t/T2} + e^{−t/T1})/6`（由 `1/T2 = γ₁/2 + 2γ_φ` 与 Bloch 球面积分 ⟨r_i⟩=0、⟨r_i r_j⟩=δ_ij/3 严格导出，**不依赖 PTM 对角假设** ⇒ 有非对角元也精确）。

> **这是 D-66 台账里第一次「物理定律锚的 golden 从定律降级为经验式再被替换」** ⇒ 教训：**物理定律锚的 golden 不等于免检**；接入独立候选后必须先验「golden 与候选能否构成判据窗口」，验不过就该怀疑 golden。

---

### 三、tol 0.01 → 1e-8（收紧 1e6 倍）

| | 旧 | 新 |
|---|---|---|
| tol | 0.01 | **1e-8** |
| 允许 F 掉到 | 0.99（比真实门误差 1.53e-4 大 **65 倍**） | 1e-8 |
| 六路 10% 扰动信号 / tol | 0.0015~0.0042（**比 tol 小 240~660 倍** ⇒ 零判别力） | 379×~1527× |

**新判据窗口三元组**：`baseline 1.11e-16 < tol 1e-8 < min 信号 3.787e-6`（余量下界 9.0e7× / 上界 379×）

**反向测试三键六路全部可抓**（与 E2 四个弱键抓不住形成对照）：

| 键 | +10% 信号 | −10% 信号 | 余量 |
|---|---|---|---|
| `T1` | 3.787e-6 | 4.628e-6 | 379× / 463× |
| `T2` | 1.010e-5 | 1.234e-5 | 1010× / 1234× |
| `t_gate` | 1.527e-5 | 1.527e-5 | 1527× / 1527× |

---

### 四、🔴 铁律升级：自证桩判据从「值」改为「行为」（本轮最重要工程产出）

**升级动因（不是理论洁癖，是实测被咬）**：B10 残差真实为 **1.11e-16**，旧判据 `|cand−golden|<1e-12 ⇒ 自证桩` 把它打成自证桩，与路径⑧（按登记表判独立）当场打架 ⇒ 可证伪性 smoke 首轮 **rc=1、5/8**，三处 FAIL：

```
[FAIL] 进判决的独立候选锚题数 ≥ 18 … 严格独立=17 … 自证桩=31/48
[FAIL] 对外账本三分类与实测口径逐项一致 … 独立集合差=['B10']；自证集合差=['B10']；CLI verified=18≠17
[FAIL] 路径②…标非自证桩却 |diff|≡0 的假独立=['B10']
```

**🔴 更本质的判据**：自证桩的充要特征不是「残差小」，而是「**跟着 golden 走**」——`_harness_reference_candidate` 直接 `return oracle_value`、**完全不看 `spec.params`** ⇒ 扰动参数后候选值**纹丝不动**。

新增 `_candidate_responds(sp, cand_fn, oracle_value)`：扰动全部数值参数 ±10%，看候选值有无物理响应。判据改为「**残差≡0 且 扰动无响应** ⇒ 自证桩」。

**新判据比旧判据严格更严**：旧判据既会**误伤**「残差恰好小」的真候选（B10 就是），也会**漏过**「残差恰好大」的自证桩。路径①与路径⑧同步升级 ⇒ **8/8 恢复全绿**，三分类刷新为 18 / 0 / 30。

---

### 五、⚠️ 三条诚实边界（必须与结论一起读）

**(a) 生产档位残差不可标定 —— 不拿它当验证凭据**

`|L|·t ≈ 2.5e-4`（t_gate=0.02µs、T1/T2~60-80µs）⇒ RK4 从 N=5 到 N=400 残差**恒为 1.11e-16 且与步数无关**，**与自证桩的 |Δ|≡0 在数值上无法区分**。

「候选真在工作」改由**三条可标定自校锚**证明：

| 自校锚 | 判据 | 实测 |
|---|---|---|
| PTM 非对角元 | `PTM[Z,I]` ↔ 解析 `−(1−e^{−t/T1})` | `−2.499687526e-4`，差 2.2e-16，**该值远在机器精度之上** |
| 敏感 regime 收敛 | t=200µs（`\|L\|·t≈O(1)`）残差浮出机器精度，N 加倍降 16× | 5.57159e-9 → 3.41038e-10，**降 16.34×**（严格 O(h⁴)） |
| 稳态极限 | t→∞ 完全退相干 ⇒ `F→0.5` | `F(t=5000µs)=0.5`，\|Δ\|=0 |
| （外加） | 六路反向扰动 | 全部可抓，见上表 |

外加 `T2>2T1` 抛 ValueError 护栏（4/4 自校锚全 PASS）。

**(b) T=0 热库 + H=0 idle 门口径** ⇒ 结果是退相干**极限上界**，未含脉冲形状误差 / 泄漏 / 串扰，**不是实测门保真度**。

**(c) T2 > 2T1 属非物理输入**（γ_φ<0），golden 与候选均**抛 ValueError 而非 clamp** —— clamp 会让非物理参数产生看似合法的保真度。

---

### 六、新增常驻护栏 `lda/run_lindblad_gate_smoke.py`（13 项全 PASS，<3s，入 CI core **86 → 87**）

- 四道自校锚全 PASS
- `tol` 从 `BENCHMARK_DEFS` 动态读取（防漂移）
- 🔴 **反向断言**：现行 golden 与已证否旧经验式的差必须 **> 1e-4**（实测 |差|=2.6383e-04）—— **防有人改回去**
- 正向 PASS + baseline 严格非零（防回落 golden）+ 判据窗口下界
- 三键六路扰动上界（六条）
- golden 拒绝非物理输入（`T2 > 2·T1` 抛 ValueError）

> 理由 = 铁律「**没被验证过的护栏不算护栏**」：升级凭据若只写在 note 散文里，改 `N_STEPS` / 改 tol / 改 golden 都会静默失效。

---

### 七、连带修正

**`lda/lda_l2/pdk_examples.py`** 的 B10+B9 逆设计 PDK：

| 字段 | 旧 | 新 |
|---|---|---|
| `target` | 0.99 | **0.9999** |
| `target_tol` | 0.01 | **5e-4** |
| `bounds` | (0.05, 1.0) | **(0.001, 1.0)** |

**理由**：新 golden 下 t_gate∈[0.05, 1.0]µs 内 F 只能取 **[0.99242, 0.99962]** ⇒ **0.99 根本不可达**（要 F=0.99 需 t_gate≈1.33µs，远超超导单比特门物理区间 10~50ns）；旧 `target_tol=0.01` 比整个可达跨度 7.2e-3 还大、无意义。新目标 0.9999 对应 t_gate≈**13.1ns**（落在物理区间内）。

---

### 八、🔴 踩坑登记（已写入生产模块 docstring「三条必须钉死的坑」第 1 条）

**row-major vec 下 bipartite 分解不是裸 `np.kron(L, I₄)`**。

2-qubit row-major vec 的索引顺序是 `(iA, iB, jA, jB)`，而 `np.kron` 要求 `(iA, jA, iB, jB)` ⇒ 直接 kron 构造 16×16 超算子会让 ρ **根本不演化**、F 恒等于 1.0（探针 v1 实测：RK4 从 N=10 到 N=400 输出**完全相同**）。

**解法**：**不构造 Choi 矩阵、不升 2-qubit 维**，改用 4×4 Liouvillian + 4 个 Pauli 基各积分一次 ⇒ 数学等价、更省，且**顺带拿到可标定的非对角元自校锚** `PTM[Z,I]`（这是「(a) 残差不可标定」的解药）。

> 探针的价值：v1 若直接进生产且只看「F 是不是在 [0,1] 内」，会得到一个**恒为 1.0 的假绿**，且数值上完全「合理」。

---

### 九、改动文件清单

| 文件 | 改动 |
|---|---|
| `lda/lda_solver/lindblad_gate_fidelity.py` | **新建**（候选求解器 + 4 道自校锚） |
| `lda/run_lindblad_gate_smoke.py` | **新建**（13 项常驻护栏） |
| `lda/lda_harness/golden.py` | `b10_gate_fidelity` 改为 Lindblad 严格闭式（**D-66 第 8 例**）+ 非物理输入护栏 |
| `lda/lda_harness/verification_adapters.py` | 登记新候选 `lindblad_gate_f` |
| `lda/lda_harness/benchmarks.py` | B10：`oracle` 换标注、`tol` 0.01→1e-8、挂 `candidate`、note 追加 |
| `lda/run_benchmark_falsifiability_smoke.py` | `MIN_INDEPENDENT` 17→18；B10 三键六路入 `PERTURB_SPEC`；**新增 `_candidate_responds` 行为判据**（路径①⑧ 同步） |
| `lda/run_ci_regression.py` | 新 smoke 入 CORE（86→87）+ timeout 180s |
| `lda/lda_webui/routes.py` | 对外账本散文同步 18/0/30 + B10 段 |
| `lda/lda_l2/pdk_examples.py` | 逆设计目标 0.99→0.9999 等三处 |
| `pyproject.toml` | 0.9.23 → **0.9.24** |
| `README.md` / `CHANGELOG.md` | 版本同步 |

⚠️ **诚实边界（未变）**：**独立候选仍只有 18/48**，自证桩 30 道按 P0 计划继续接线。提高的是「可被外部验货的比例」，不是单道验证强度。

---

### 十、🔴 全量回归抓出的真 bug：numpy 标量泄漏进判决链（v0.9.24 收口时实测）

**现象**：全量 `--tag core` 回归跑到第 2 条 `run_harness.py` 即 **FAIL**（Exit=1）：

```
File "lda_harness\report.py", line 207, in format_json
    return json.dumps(out, indent=2, ensure_ascii=False)
TypeError: Object of type bool is not JSON serializable
```

**根因**：新候选 `average_gate_fidelity` 返回 `np.float64`（PTM 矩阵元素是 numpy 标量）⇒ 下游 `passed = abs(cand − golden) <= tol` 得到 **`np.bool_`** ⇒ `json.dumps` 不认（`np.bool_` 不是 `bool` 子类）。

🔴 **这是同一类 bug 的第二次**：**v0.9.17 B24**（候选返回 numpy 标量）当时修了，但**只修了个案、没加护栏** ⇒ 现在 B10 原样复发。

**修复（两层）**：
1. 模块内 `average_gate_fidelity` 返回 `float(...)` 包裹；
2. 适配器 `_lindblad_gate_f_candidate` 再包一层 `float(...)` 双保险 —— **判决链上不许出现 numpy 标量**。

---

### 十一、🔴 覆盖盲区根治：新增第 ⑨ 项常驻护栏（可证伪性 smoke 8 → 9 项）

**为什么之前抓不到**：可证伪性 smoke 的路径⑧ 在**进程内**复现路径② 时，注释明写「**不写报告文件**，避免每次回归污染工作区」⇒ **`report.format_json` 从未被执行** ⇒ 该 bug 只能等全量回归里 `run_harness.py` 撞上。

> 🔴 **教训（永久）**：**进程内复现 ≠ 覆盖真实出口**。省掉的那一步就是盲区——省得越「无害」，盲区越隐蔽。

**新增第 ⑨ 项**：在**内存里**对路径② 的结果跑 `rep.format_json`（保留原「不落盘」设计），断言：

- `format_json` 不抛异常；
- 结果可被 `json.loads` 回读；
- **每道题的 `passed` 必须是 Python `bool`**（不是 `np.bool_`）。

**反向测试（已做，护栏会响）**：把 B10 候选临时改成返回 `np.float64(golden)`（= 真 bug 原样复现）⇒

```
[FAIL] 路径② 报告可 JSON 序列化（判决链无 numpy 标量泄漏）
       | TypeError: Object of type bool is not JSON serializable
```

⇒ smoke 9/9 全绿，且第 ⑨ 项**被证明会响**。

---

### 十二、🔴 判据单一定义处：CLI 自身断言同步升级（v0.9.24 收口时实测）

**现象**：修好 JSON bug 后重跑 `run_harness.py`，其**自己的**断言又崩了：

```
AssertionError: 标为独立/降级候选却 candidate≡golden（假独立）：['B10']
```

**根因**：`run_harness.py` 里**另有一份** `|cand−golden|<1e-12 ⇒ 假独立` 的判据副本。我在第四节只升级了 smoke 的路径①⑧，**漏了 CLI 这份** ⇒ smoke 8/8 全绿而 CLI 崩。

> 🔴 **教训（永久）**：**判据必须单一定义处**（与 v0.9.16「三分类常量全库唯一定义处」同一纪律）。分散实现 ⇒ 升级必然漏改 ⇒ 两处口径当场打架。

**修复**：行为判据上移到 `lda_harness/harness.py` 的 `candidate_responds()`（**全库唯一权威定义**），`run_harness.py` 与 smoke 的 `_candidate_responds()` **都改为薄委托**。

**反向测试（已做，护栏会响）**：把 B10 候选临时改成 `lambda spec, golden: golden`（= `ReferenceCandidate` 自证桩行为：直接返回 golden、**完全不看 params**）⇒

```
run_harness rc=1
  AssertionError: 标为独立/降级候选却 candidate≡golden（假独立）：['B10']
  ——路由或候选实现可能已静默回落 golden，verified 会被虚报
```

⇒ **新判据确实抓得住「静默回落 golden」**，且对 B10（残差 1.11e-16 但扰动响应 1.5e-5）**不误伤**。

**反向自检总账（`_reverse_v0924.py`，3/3 PASS）**：

| # | 被验护栏 | 篡改手法 | 实测结果 |
|---|---|---|---|
| A | 第 ⑨ 项（报告可序列化） | B10 候选返回 `np.float64(golden)` | **PASS** — `[FAIL] … TypeError: Object of type bool is not JSON serializable`，rc=1 |
| B | `run_harness` 假独立断言（行为判据） | B10 候选改 `lambda: golden` | **PASS** — `AssertionError: 假独立：['B10']`，rc=1 |
| C | 复原确认 | 无（原样重跑） | **PASS** — rc=0，`verified=18 · 降级 0 · 自证桩 30 · 48/48 闭合` |

> 🔴 **反向测试自身的坑（值得记，第一次就是这么误判的）**：第一版用 `subprocess.run([sys.executable, "run_harness.py"])`，而**父进程的 monkeypatch 不会传给子进程** ⇒ 得出「护栏不响」的**错误结论**（rc=0、未触发、报告 `2/3 PASS`）。改用**注入脚本**（让子进程自己 import 后打补丁）才测出真实行为。🔴 **反向测试失败时，先怀疑测试手法，再怀疑护栏**——把「护栏不响」当成结论去改护栏，会掩盖真问题。

---

### 十三、改动文件清单（补）

| 文件 | 改动 |
|---|---|
| `lda/lda_solver/lindblad_gate_fidelity.py` | `average_gate_fidelity` 返回 `float(...)` 包裹（修 numpy 标量泄漏） |
| `lda/lda_harness/verification_adapters.py` | 候选返回值再包一层 `float(...)` 双保险 |
| `lda/lda_harness/harness.py` | **新增 `candidate_responds()`** —— 行为判据的**全库唯一权威定义处** |
| `lda/run_harness.py` | 假独立断言改为调 `candidate_responds`（升级为行为判据） |
| `lda/run_benchmark_falsifiability_smoke.py` | `_candidate_responds` 改为薄委托；**新增第 ⑨ 项**（报告可序列化 + 无 numpy 标量泄漏）；`import json` |

**CI core 仍为 87 条**（新增断言进已有 smoke 文件，未新增文件）。

---

### 十四、第三个发现：`run_ci_industrial_smoke.py` TIMEOUT（v0.9.24 全量回归实测）

**现象**：全量 `--tag core` 回归 **86 PASS / 0 SKIP / 1 FAIL**，失败项 `run_ci_industrial_smoke.py`。但状态是 **`[TIMEOUT] … (600.0s)`**，不是真失败。

**验证**：单独跑 `run_ci_industrial_smoke.py`（无外层时限）⇒ **3/3 ALL PASS**：

```
[PASS] 正例-回归core快速子集: ok=True
       验证合约工业化回归 core 集：64 PASS / 0 SKIP / 0 FAIL，总耗时 667.62s —— 全绿
[PASS] 正例-性能基准greens: ok=True  （greens speedup 71.23×）
[PASS] 负例-坏smoke被检出: ok=True  （fail=1）
```

**根因**：`run_ci_industrial_smoke.py` 内部**递归**跑一次 core 回归子集，并用 `_SLOW_CORE` 排除慢 smoke 以保住可完成性。v0.9.23 把 `run_semivec_mode_smoke.py`（2D 半矢量本征模，5 次本征解，实测 **~97s**）加入 `CORE_SMOKES` 时，**漏了同步这张排除表** ⇒ 内部子回归 **~570s → 667.62s** ⇒ 撑破外层 600s 上限。

> 🔴 **教训（永久）**：**新增慢 smoke 入 `CORE_SMOKES` 时，必须同步检查所有「内部递归跑 core 子集」的脚本**（本例是全库唯一一处 `run_ci_industrial_smoke._SLOW_CORE`）。v0.9.24 之前 v0.9.23 的 semivec 从没跑过全量 core 回归 ⇒ 这个漏登记一直没暴露。

**修复（两处）**：

| 文件 | 改动 |
|---|---|
| `lda/run_ci_industrial_smoke.py` | `_SLOW_CORE` 补登 `run_semivec_mode_smoke.py` |
| `lda/run_ci_regression.py` | `_BUILTIN_TIMEOUT_OVERRIDE["run_ci_industrial_smoke.py"]` 600 → **900s** |

**修复后实测**：内部子回归 **667.62s → 577.41s**（−90.2s，与 semivec 的 97s 吻合 ⇒ 根因确认无误），本脚本总耗时 **695s**，**3/3 ALL PASS、EXIT=0**，新上限 900s 余量 **1.30×**。

⚠️ **为什么放宽 timeout 不是红线**：`_run_one` 把 **TIMEOUT 与 FAIL 区分为两种状态**（铁律「宁可红不可假绿」），且本项**单独跑 3/3 ALL PASS**、不含任何物理/数值判据 —— 是纯耗时问题。原 600s 在补登前只剩个位数量级余量，故顺手放宽到 900s（1.5× 余量）防慢机器抖动。

---

## v0.9.23（2026-09-03 · E2 升级为严格独立候选 · 严格独立 16 → 17 · 降级量级参考 1 → 0）

**指令**：延续 P0 自证段（E2 实证锚从「降级量级参考」升为「严格独立候选」）。

**背景判断（为什么是 E2）**：E2 是全库**唯一一道**被 `candidate_status=degraded_ordinal` 挡在死标量判决外的锚。降级的原始理由是 D-65/R16：标量 FDFD 候选与环器件 golden 几何不同源、精度不足。**正确的解法不是接受降级，而是换一个更好的候选**——降级是「暂时没办法」的诚实标注，不是终点。

**换将**：`fdfd_ng`（标量亥姆霍兹 FDFD）→ `semivec_ng`（新写 `lda/lda_solver/semivec_mode_solver.py`）
- 控制方程（准 TE，u=E_x、E_y≡0）：`∂ₓ[(1/n²)∂ₓ(n²u)] + ∂ᵧ²u + k₀²n²u = β²u`；准 TM 由 x↔y 转置实现
- 界面：x 向调和通量（非对称矩阵，乘了 n² 权重属正常）；y 向裸中心差分（u 与 ∂ᵧu 均连续）
- 🔴 **Dirichlet 墙面 ghost-point**（`main_x[0,:] -= invh2`）：漏掉 ⇒ x 边界静默退化成 Neumann，解错成纯 slab 值
- 色散：Sellmeier（Si / SiO₂ / Si₃N₄），`_n_disp` 按形状给色散、整体平移到标称值（保留 dn/dλ）
- n_g = n_eff − λ·dn_eff/dλ（λ 中心差分，Δλ=0.02µm）

**换将的两条实测理由**：
| 缺陷 | FDFD（换下） | 半矢量（换上） |
|---|---|---|
| 计算窗口散射 | **±0.04~0.08**（clad 1.5→4.0µm，n_g 1.878~1.962） | **<1e-5**（L=5.0/6.0/8.0 → 1.956401/1.957177/1.956362，极差 8.15e-4） |
| 偏振 | 标量，只有一个解 | 准 TE / 准 TM 分离，与实测 TE 1.892 / TM 1.717 口径对齐 |

窗口散射是**首要理由**：FDFD 的散射几乎吃掉 tol=0.10 的全部预算 ⇒ 其 PASS 可能只是窗口挑得好，判决不可信。

**精度凭据（唯一凭据，缺此不可宣称）**：自校锚③ A 级实证对照 —— Si₃N₄ 1.2×0.3 **纯净对照组**（Coatings 10(4) 309 (2020) Figure 5，无 SiOC、全 PECVD silica 包层、R=100µm 无弯曲、**λ²/(FSR·L)=1.9667 ≈ 原文 1.9666 口径自洽**），实测 n_g=1.9666 ↔ 计算 **1.966684** ⇒ **Δ=+8.4e-5**。同材料体系、同尺寸量级（1.2×0.3 vs E2 的 1.0×0.3）⇒ 端到端校准「算子+色散+数值微分」整条链路。
另两道**可分离精确解自校锚**：均匀方向上算子退化为 Dirichlet 区间 −∂²，基模 (π/L)² ⇒ `n_eff² = n_slab² − (π/(k₀L))²`；h 减半 Δ 降 ~3.5×（O(h²) 收敛）。

**踩坑与修正（两条，均已写进实现注释）**：
1. 🔴 **ARPACK sigma 位置决定能否采到基模**。原用 `sigma = k₀²·((n_core+n_clad)/2)²`（中值）：退化构型下模谱是密集阶梯，中值附近采到的**不是基模**，且窗口越大漏得越彻底（L=6.0 时 Δ=−1.08）。改为**贴近带顶** `sigma = k₀²·n_core²·1.02` 后 y 均匀锚从 −1.09 修正到 **+3.08e-4**。另注：`k` 从 8 加到 16 结果逐位相同 ⇒ **增大 k 救不了 sigma 选错**。
2. 🔴 **自校锚的窗口 L 必须固定 2.4，不能跟着生产窗口走**。参考值含 (π/(k₀L))²，L 越大离散谱越密（阶梯间距 ∝1/L²），同一 k 采到的模越少 ⇒ 窗口放大后自校会**假失败**（L=6.0 时 x 均匀 Δ=−1.43e-1，L=2.4 时仅 +1.19e-3）。
3. 生产网格 `H_GRID` 由 0.02 降到 **0.015**（h=0.02 未收敛：实证对照 Δ=+0.024；0.015 → +8.4e-5，0.01 → 差 8.4e-4 已收敛）。

**判据窗口（铁律 baseline < tol < 扰动信号）实测**：
- baseline |Δ| = **0.0652**（1.957174 vs golden 1.892）< tol 0.10 ✓
- 扰动信号：n_core×1.1 → 0.3600（3.6×）✅ · n_core×0.9 → 0.2231（2.2×）✅ · n_clad×0.9 → 0.1212 ✅ · h_um×1.1 → 0.1032 ✅(仅 1.03×，不用)
- 灵敏度：最小可检出扰动 **2%**
- 🔴 **四个弱键抓不住，如实登记不掩盖**：w_um×1.1 0.0764 / w_um×0.9 0.0511 / h_um×0.9 0.0191 / n_clad×1.1 0.0173 均 < tol ⇒ 反向测试**只用 n_core**，不改用弱键充数

**新增常驻护栏 `lda/run_semivec_mode_smoke.py`（入 CI core 85→86，实测 89s，8 项）**：
自校锚 5 项 + 三窗口散射 <1e-3 + 正向 PASS + baseline 非零（防回落 golden）+ 判据窗口上下界双向。
理由=铁律「**没被验证过的护栏不算护栏**」——升级凭据若只写在 note 散文里，改网格/窗口/ARPACK 参数就会静默失效。

**顺带修正**：
- **D-66 第 7 例**：`E-SIN-NG-1200` 的 `n_clad` 1.44 → **2.2**。原文三处逐字：①"The refractive index of the deposited SiOC film at standard telecom wavelength 1550 nm was measured as **n = 2.2**"（SiOC 折射率**高于** Si₃N₄ 芯 1.9963，不是低折射率包层）②"The SiOC/Si3N4 structures were covered by PECVD silica with n = 1.45"（SiOC 层 350nm）③"Figure 3 ... TE mode ... is leaky and ... stable propagation of **TM** mode"。该条**不作任何锚题 golden**，修正属数据完整性整修；并明文禁止拿它做精度判定（口径不自洽：λ²/(FSR·L)=2.3305 ≠ 原文 2.2834）。
- **`fdfd_ng` 取消登记**：E2 换候选后全库无锚题引用它，而可证伪性 smoke 的「已登记候选类型与实测独立锚一致」护栏断言 `set(BENCHMARK_CANDIDATES) ⊆ {被引用候选}` ⇒ 继续登记会直接 FAIL。**这是故意的**：登记了却没人用 = 接口失配，护栏本就该响。函数保留（供 `run_empirical_anchor_smoke.py` 复现 D-65/R16 证据）。
- E 族候选分发**去硬编码**（原 `== "fdfd_ng"` 分支）改查登记表，与 B 族同构 ⇒ 失配护栏现在能覆盖 E 族。

**验证证据链**：可证伪性 smoke **8/8 PASS**（严格独立 17 · 降级 0 · 自证桩 31 · E2 反向 FAIL✅ d=3.600e-1/tol=0.1 · 灵敏度 ≤2.0% · 全量 48 锚无回归 · 对外账本端点 独立17/降级0/自证31 逐项相等）· 新 smoke 8/8 PASS（89s）· 计数一致性 11/11 OK（CI core 86）

⚠️ **诚实边界（必须与结论一起读）**：**残差 0.0652 不等于精度已验证**。残差主成分：①**对象不对齐**——golden 1.892 来自 OFDR **环**腔群延迟，候选解**直波导**；同文 MZI 直波导交叉验证给出 1.90~1.92（比环测高 0.01~0.03），不对齐本身值 ~0.02 量级；②**制造公差**——h_um ±10% 就移动 n_g ∓0.046，300nm LPCVD 膜厚公差轻松达 ±5%。⇒ tol=0.10 中**没有多少物理裕度**，E2 只能宣称「独立求解路径 + 判决可证伪 + 量级与公差内一致」，**不宣称精度验证**。另：候选**采用** Sellmeier 色散（物理事实），关掉色散时 n_g=1.921778（Δ=+0.0298，反而更近）——**不据此择优**，择优凑近 golden 即拟合回算（红线）。**降级档清零不代表问题消失**：它表示「当前没有几何不同源的候选在充数」，E2 的对象不对齐仍如实写在 note 里。

## v0.9.22（2026-09-03 · golden 语义修正 D-66 第 5 例：TM 平板色散方程加权因子）

**D-66「怀疑 golden 本身」第 5 例**：`lda_harness/golden.py::_slab_neff` 的 **TM 分支误用 n_eff² 代替 n_clad²** 作加权因子。

- 正确式（界面条件 H 切向连续 + E_z 切向连续，E_z ∝ (1/n²)∂_yH_x ⇒ (u·sin u)/n_core² = (v·cos u)/n_clad²）：`u·tan u = (n_core²/n_clad²)·v`
- 旧式误差：0.22µm / 0.5µm 芯分别达 **+5.45e-1 / +1.06e-1**
- **独立验证**：面积加权的 1D 矢量 FD（TM 未知量 H_x，界面系数 2n_i²/(n_i²+n_{i+1}²)，非对称矩阵 + eigs）以**精确 O(h²)**（残差比值 4.00）收敛到**标准解析**而非旧 golden
- TE 分支经同一 FD 校核无误（与解析差 4.4e-16）
- **零下游影响**：旧 TM 分支**无任何消费点**（全部调用走默认 TE）
- 修好的 TM 解析现用作 v0.9.23 的 2D 半矢量求解器**自校锚②**（y 均匀极限）

## v0.9.21（2026-09-02 · B1 米氏散射接线 · 严格独立 15 → 16）

**指令**：延续 P0 接线段（B1 米氏散射 Q_scat）。

**独立候选**：新写 `lda_solver/mie_solver.py`（纯 numpy 递推，零外部依赖）
- golden = Rayleigh（偶极子）一阶极限 Q=(8/3)·x⁴·r²（x≪1 只保留 a₁ 首项）
- cand = 完整 Mie 级数（B&H 4.53：Q=(2/x²)Σ(2n+1)(|a_n|²+|b_n|²)，维度形式系数 + Wiscombe 截断 nmax=x+4x^⅓+2）
- 独立性：物理同源（麦克斯韦方程）、方法独立（一阶展开 vs 全阶求和）⇒ |diff|=Rayleigh 固有截断误差，随 x 单调增长（-0.001%@x=0.01 → 1.388%@x=0.4），即「x≪1 精确一致」的定量边界

**数值自检（写进实现）**：
- x→0 收敛 Rayleigh（O(x²) 高阶项精确消失）
- 递推 vs scipy.special.spherical_jn/yn 交叉验证 max|Δ|≤3e-8（x=0.4, nmax=6）

**🔴 环境确定性修复**：golden `b1_mie_qscat(use_miepython=True)` 原会在装有 miepython 的环境自动切完整 Mie（ORACLE）⇒ **golden 环境相关、判决不可复现**。接线后 default_params 钉死 `use_miepython=False`（golden 固定 Rayleigh，任何环境一致）；Mie ORACLE 路径保留给显式外部验货，判决路径不依赖。

**标定（m=1.33/x=0.4，golden=2.8413e-3）**：
- baseline |diff| = 3.945e-5（rel 1.388%，tol=2e-4 **未动**，余量 5.1×）
- 判据窗口：3.945e-5 < 2e-4 < min 反向信号 1.246e-3（6.2×）✓
- 扰动谱：m×1.1→2.357e-3（11.9× 最强）· x×1.1→1.246e-3（6.2×）⇒ PERTURB 固定扰 m

**接线（三处）**：adapters 注册 `mie_exact` · benchmarks B1 加 candidate 字段 + 钉死 use_miepython=False + note · smoke `MIN_INDEPENDENT 15→16` + `PERTURB_SPEC` 加 B1@m

**验证证据链**：可证伪性 smoke **8/8 PASS**（严格独立 16 · 自证桩 31 · B1 反向 FAIL✅ d=2.357e-3/tol=2e-4）· `run_harness.py` RC=0（B1 行 0.00284131 vs 0.00280186 / diff=3.945e-05 / PASS、verified=16）· 全量 core 回归 **85 PASS / 0 SKIP / 0 FAIL（1385.9s，REGRESSION_RC=0）**

## v0.9.20（2026-09-02 · B14 定向耦合器接线 + golden 语义修正 · 严格独立 14 → 15）

**指令**：延续 P0 接线段（B14 定向耦合器 3dB 耦合长度）。

**🔴 golden 语义修正（D-66「怀疑 golden 本身」第 4 例）**：
- 原式 λ/(2|n_e−n_o|)=15.5µm 是**完全转移长度**（P₂=sin²(κz) 在该点=sin²(π/2)=**1.0**，RK4 数值实证），被错标为 3dB 点
- 真 3dB 点（P₂=0.5）=λ/(4|n_e−n_o|)=**7.75µm**（P₂=sin²(π/4)=0.5，RK4 实证 8e-15 精度）
- 同源消费点一并修正：`device_library._dc_supermode_core`（其相位校验 Δβ·L=π 本就是完全转移点 → 改 π/2）· `design_engine.py` note · `device_library` verdict 文案；`run_kernel_seal_smoke` 动态调用 golden 自动跟随（实测 5/5 PASS）
- tol 0.5→0.25（占 golden 的 3.2%，同比重定——旧 tol 是旧 golden 的 3.2%）

**独立候选**：新写 `lda_solver/dc_cmt_solver.py`（纯 numpy rFFT+复矩阵乘，零 GPU）
- 方法：增量 2×2 复传播矩阵数值传播 [A1,A2]（每步一次矩阵乘，全程无 sin² 闭式）→ P₂(z) 序列去均值+Hann 窗 → rFFT 功率谱 → 谱峰三点抛物线细化 → L_P=1/f_peak → L_3dB=L_P/4；与 B3/B4/B20 同款「数值序列提取频域周期」方法学，与 golden 闭式反解独立
- 🔴 **方法学发现（二模恒耦合陷阱）**：该系统传播矩阵是**精确旋转**，任何「数值传播+根查找」路线（RK4/分段传输矩阵/采样插值）都退化为机器精度（实测 8e-15~4.6e-13）→ 撞 1e-12 自证桩判据 ⇒ **必须走 FFT 谱峰路线**，残差由谱分辨率+抛物线近似控制（1.56e-4，非机器精度）
- 标定：dz=0.01/n_periods=8（baseline 1.56e-4，tol 0.25 余量 1560×）；判据窗口 1.56e-4 < 0.25 < min 反向信号 5.71（22.9×）✓
- 反向扰动信号谱：n_e×1.1→6.44（25.8×）✅ · n_o×1.1→5.71 ✅ · wl×1.1→0.775（3.1×）✅ ⇒ PERTURB 固定扰 n_e

**接线（三处）**：`verification_adapters.py` 注册 `dc_cmt_fft` · `benchmarks.py` B14 加 candidate 字段+note 记录语义修正 · smoke `MIN_INDEPENDENT 14→15` + `PERTURB_SPEC` 加 B14@n_e

**验证证据链**：
- kernel_seal 5/5 PASS（golden 修正动态跟随）· device_library ALL GREEN
- 可证伪性 smoke **8/8 PASS**：严格独立 **15** · 降级 1 · 自证桩 32 · B14 反向 `FAIL✅(d=6.437e+00/tol=0.25)`
- 对外主报告 `run_harness.py` RC=0：B14 行 `7.75 vs 7.74984 / diff=1.563e-4 / PASS`、verified=15
- 全量 core 回归 **85 PASS / 0 SKIP / 0 FAIL（1390.4s，REGRESSION_RC=0）**

## v0.9.19（2026-09-02 · B15 波导光栅严格求解器接线 · 严格独立 13 → 14）

**指令**：B15 波导光栅严格求解器接线（v0.9.18 遗留任务）。

**核心反转（本轮方法学贡献）**：v0.9.18 判 B15「不可接」的前提是「在库唯一求解器 tmm.py 是垂直入射多层膜，物理模型错配」。本轮证明该前提可被推翻——**写正确的求解器本身就是解法**。严格侧求解器不是等来的，是为锚题定制的（P0 接线段的深层含义）。

**新求解器**：`lda_solver/bragg_solver.py`（纯 numpy + scipy.linalg.eigvalsh，零 GPU、零重依赖）
- 物理对象：波导 Bragg 光栅 E(z)=n_eff²·(1+m·cos(2πz/Λ))——折射率沿**传播方向**周期调制（tmm.py 是沿分层法向，本质不同）
- 方法：反周期 Bloch 边界 ψ(z+Λ)=−ψ(z) 把 Bloch 波矢锁定在 k=±π/Λ，离散亥姆霍兹算子与 E(z) 构成**广义本征值问题** A ψ=β²·B ψ；谱最低简并对（无调制时机器精度简并）即第一 Bragg 带隙上下沿，带隙中心 → λ_B=2π/β_c
- 与 golden 独立性：golden=一阶相位匹配闭式 λ_B=2·n_eff·Λ（**运动学**，k 演化只计基波）vs cand=**动力学**全波本征谱（调制深度 m 进入算子）⇒ 物理同源、方法独立，|diff| 反映一阶条件的固有近似误差

**标定（实测，n_eff=2.4/Λ=0.323/m=0.004）**：
- 网格双向标定：N=120→4.16e-5 · N=240→8.36e-6（**选定**）· N=480→5.41e-8（偶然抵消点，避开——同 B26 现象）· N=960→2.02e-6（越 LAPACK 地板反升，同 B22 现象）
- 无调制简并自校：w[0]/w[1] 劈裂 3.7e-13~2.7e-11（机器精度简并对），β_c 命中 π/(Λ·n_eff)（离散色散 O(1/N²)）
- m 扫描：m=0.008 为偶然抵消点（2.2e-7，避开），取 m=0.004（弱调制典型值）
- 判据窗口铁律：baseline 8.36e-6 < tol 0.01（余量 1196×）< 反向 n_eff×1.1 信号 1.55e-1（15.5×）✓ **tol 未动**

**接线（三处）**：`verification_adapters.py` 注册 `bragg_bloch_exact` 候选 · `benchmarks.py` B15 加 `candidate` 字段 + note 记录 v0.9.18 判错→v0.9.19 新求解器接通 · smoke `MIN_INDEPENDENT 13→14` + `PERTURB_SPEC` 加 B15@n_eff（period 与 n_eff 一阶等价 λ_B∝n_eff·Λ，固定扰 n_eff）

**验证证据链**：
- 可证伪性 smoke **8/8 PASS**：严格独立 **14** · 降级 1 · 自证桩 33 · B15 反向 `FAIL✅(d=1.550e-01/tol=0.01)` · 灵敏度 ≤1.0% · 端点三分类 ≡ 本机实测 · 路径② verified=14/14
- 对外主报告 `run_harness.py` RC=0：B15 行 `1.5504 vs 1.55041 / diff=8.36e-06 / PASS`、verified=14、独立列表含 B15（float 返回值无 B24 式序列化 bug）
- 全量 core 回归 **85 PASS / 0 SKIP / 0 FAIL（1392.9s，REGRESSION_RC=0）**

## v0.9.18（2026-09-02 · S13 设计良率锚接线 · 严格独立 12 → 13）

**指令**：延续 P0 计划的「接线段」。盘点 35 道自证桩，识别真正可低成本接线的批次。

**方法学铁律（本轮新贡献）**：
- 🔴 **伪独立陷阱（S7/S8 实测证否）**：统计锚的「解析均值」是硬编码常量（S7=10.5 / S8=46.93），且由均值定理对工艺容差 σ 不敏感（E[margin] 不依赖 σ）。golden=MC 均值、candidate=该常量 ⇒ 反向扰动 σ 只改变 MC 重采样涨落、candidate 不变 ⇒ |diff| 恒为 MC 涨落、被 tol(0.15/0.20) 完全吞没 ⇒ **反向必漏抓**。实测：扰 seed 后 |cand−golden| 仅 0.016~0.026 ≪ tol ⇒ 永远 PASS。数学上无法同时满足「正向 PASS（tol>涨落）」与「反向 FAIL（tol<扰动信号）」→ **绝不接**，否则假绿。
- 🔴 **模型错配（B15 留待 v0.9.19）**：`tmm.py` 是垂直入射多层膜 TMM，B15 golden 是波导光栅一阶条件 λ_B=2·n_eff·Λ（沿线周期扰动），物理模型不同 → 用 TMM 算需 hack n_low 才凑得出 golden，违反「独立候选必须方法学独立且物理正确」→ 不接。

**结果**：严格独立候选 **12 → 13**（新增 **S13**）· 降级量级参考 **1**（E2）· 自证桩 **35 → 34**（三类和 = 48 校验通过）。
- S13：golden=蒙特卡洛仿真良率（固定种子 1313，采样 20000 点，0.954750）↔ candidate=解析高斯积分闭式 `Y=Φ((L_hi−L0)/σ_L)−Φ((L_lo−L0)/σ_L)`（FSR=c/L 单调 ⇒ 规格窗口逆变换为 L 区间，精确误差函数积分、保留 1/L 非线性）。
- 实测：baseline|diff|=3.37e-4（rel 0.035%，tol=0.01 余量 29.7×）· 反向扰动信号谱：delta×1.1→1.73e-2（51×）✅ · sigma_rel×1.1→2.39e-2（71×）✅ · fsr_nom×1.1→3.37e-4（=baseline 漏抓：yield 对 fsr_nom 免疫，σ 按比例缩放）→ 盲区 fsr_nom_nm 已诚实披露，PERTURB 固定扰 delta（最强键）。
- 全量 core 回归 85 PASS/0 FAIL（1442s）确认无回归；可证伪性 smoke 8/8 PASS（严格独立 13、反向 13 道全 FAIL✅）。

---

## v0.9.17（2026-09-02 · 量子侧五道接线 · 严格独立 7 → 12）

**指令**：延续 P0 计划的「接线段」工作 —— 严格侧数值求解器早已躺在代码库，只是从未接成 candidate。
本批锁定 **B12 / B13 / B22 / B23 / B24** 五道：它们的 `note` 里**早就宣称有严格侧对拍**（"D-39 离散 TL 三对角特征值"、"441 维电荷 basis 对角化"、"数值对角化双基对拍"），
但 harness 一直落 `_harness_reference_candidate` ⇒ **宣称 ≠ 事实**。本次把宣称接成事实。

**结果**：严格独立候选 **7 → 12**（B3/B4/B9/**B12**/**B13**/B20/**B22**/**B23**/**B24**/B25/B26/B27）· 降级量级参考 **1**（E2）· 自证桩 **40 → 35**（三类和 = 48 校验通过）。

---

### 改动一：五个新独立候选（`verification_adapters.py` 新 1d 段，+211 行）

| 锚 | 候选 key | 数值路径 | 标定 | 实测残差 | tol | 余量 |
|---|---|---|---|---|---|---|
| B12 | `tl_eigen_f0` | 二阶 ghost 边界离散 TL 三对角本征值 | N=400 | 6.913e-6 | 0.02（**未动**） | 2894× |
| B13 | `coupler_charge_exact` | 441 维电荷基严格对角化 `solve_coupler` | Nq=10 | 1.3131e-3 | 0.10 → **2.0e-3**（收紧 50×） | 1.52× |
| B22 | `tl_eigen_qres` | 同一台离散 TL 本征求解器（v=c0/n_eff） | N=4000 | 4.982e-8 | 1e-6（**未动**） | 20× |
| B23 | `fluxonium_ho_exact` | 谐振子基矩阵严格对角化（Ej=0 极限） | ncut=24 | 7.752e-9 | 1e-6（**未动**） | 129× |
| B24 | `tcoup_fock_exact` | 三模 Fock 空间联合对角化 + 宇称定符号 | ncut=3 | 1.272e-5 | 1e-6 → **3e-5**（实测差 ×2.36） | 31.8× 窗口内 |

**四道 tol 未放宽或反而收紧，只有 B24 按实测重定** —— 放宽 tol 到掩盖真实误差 = 取消验证，是 P0 纪律红线。
B13 的 `tol=0.10` 原相当于 golden（0.0316）的 **316%**，是典型「什么都抓不住」的自证桩容差，本次**加严 50 倍**。

### 改动二：三条方法学发现（都是实测证伪换来的）

🔴 **1. TL 离散化必须用二阶 ghost-point 边界**
库内 `resonator_solver._discrete_f0` 在开路端用单边一阶差分（`A[N-1,N-1] = -1`）⇒ 收敛仅 **O(1/N)**，N=200 残差 2.7e-2，**连 B12 的 tol=0.02 都过不去**。
新写 `_tl_eigen_f0_2nd`：`diag[0]=-3`（Dirichlet ghost，V₋₁=−V₀）+ `diag[-1]=-1`（Neumann ghost，V_N=V_{N-1}）⇒ 恢复 **O(1/N²)**，用 `scipy.linalg.eigh_tridiagonal(..., select="i", select_range=(N-1,N-1))` 取最接近 0 的负本征值，`ω=√(−λ)·v/dx`。

🔴 **2. TL-FDTD 路线不可用（实测证伪，已写进 B22 note）**
`device_library._qres_tlfdtd_core` 的 FFT 记录长度 ∝ dt ∝ 1/N ⇒ **网格细化反而缩短时窗、降低频率分辨率**，残差随 N **恶化**：N=200 → 8.4e-2、N=1600 → 3.6e-2，全部远超 tol。故 B22 走本征值路线而非时域路线。

🔴 **3. 多体张量索引必须与构造序一致（B24 血案）**
`q1⊗q2⊗c` 构造下 q1 是最高位 ⇒ qubit2 激发是 `i010 = 1*ncut`，**不是** `1`（那是耦合器激发 `i001`）。误用导致宇称判反、signed 出正值、残差 **7.99e-3（超 tol 7987×）**。
另：**符号类判定不得取绝对值** —— B24 默认 Δ1=Δ2=−2.5 ⇒ golden 为**负**（−0.004），符号由本征矢宇称独立判定（较低 qubit-like 态若 |100⟩ 与 |010⟩ 振幅同号 ⇒ g_eff<0）。

### 改动三：🔴 判据窗口铁律（本版核心方法学贡献）

接独立候选必须满足 **`baseline残差 < tol < min(反向扰动信号)`**，否则「正向 PASS」与「反向必 FAIL」二选一必破。
B13 实测窗口**仅 3.10×**，逐键扰动信号谱（10%）：

| 扰动键 | 残差 | 相对基线 | 能否抓住 |
|---|---|---|---|
| C1 / C2 | 4.07e-3 | 3.10× | ✅ |
| E_C1 / E_C2 | 2.06e-3 | 1.57× | ✅ |
| Cc | 1.72e-3 | 1.31× | ❌ 漏抓 |
| E_J1 / E_J2 | 5.50e-4 | **0.42×（比基线还小）** | ❌ 注定漏抓 |

E_J 扰动使严格解朝渐近闭式靠近（**扰动与近似误差偶然抵消**，同 B26 现象）⇒ 任何 `tol > 基线` 的取值都抓不住 E_J 键。
`tol=2.0e-3` 是「正向 PASS」与「尽量多抓反向键」的最优折中（**4/7 键可抓**），反向测试固定扰 C1，**弱键盲区已在 note 里如实披露**。

### 改动四：网格/截断双向标定（太精也是错）

| 锚 | 太粗 | 选定 | 太精（触雷） |
|---|---|---|---|
| B22 | N=200 ⇒ 2.57e-4（d/tol=19，假红） | **N=4000** ⇒ 4.98e-8 | N=16000 ⇒ 反升 1.04e-7（越过 LAPACK 数值地板） |
| B23 | ncut=20 ⇒ 4.89e-7（d/tol=0.49，余量不足 2×） | **ncut=24** ⇒ 7.75e-9 | ncut=32 ⇒ 1.73e-12 / ncut=40 ⇒ 4.7e-14（贴到 1e-12 判据 ⇒ 与自证桩按值不可区分 ⇒ **护栏误报假独立**） |

### 改动五：门禁升级（`run_benchmark_falsifiability_smoke.py`）

- `MIN_INDEPENDENT` **7 → 12**（v0.9.14 起步 4 → v0.9.16 七道 → v0.9.17 十二道）
- `PERTURB_SPEC` 追加五条：`B12@l` · `B22@L_um` · `B23@el_ghz` · `B24@wq_ghz` · **`B13@C1`**（注释写明：C1 是唯一稳超 tol=2.0e-3 的强键，不得改扰弱键）

**实测 8/8 PASS（rc=0）**：严格独立 **12** 道 · 降级 1 · 自证桩 **35/48**；
正向 d/tol 全披露（B12 3.5e-04 / B13 6.6e-01 / B22 5.0e-02 / B23 7.8e-03 / B24 4.2e-01）；
**反向 12 道全 FAIL ✅**（新增 B12@l d=9.78e-1 · B22@L_um d=6.81e-1 · B23@el_ghz d=1.381e-1 · B24@wq_ghz d=9.752e-4 · B13@C1 d=4.069e-3）；
灵敏度最差 5.0%；全量 48 锚无回归；端点三分类 ≡ CLI verified=12；路径② 48/48 按题标注。

### 反向自检：八处护栏逐一确认「会响」

> 没被验证过的护栏不算护栏。以下每处均为「临时篡改源码 → 子进程跑 smoke → finally 还原」。

| # | 篡改手法 | smoke 实测反应 |
|---|---|---|
| A | B22 候选静默回落 golden | 4 项 FAIL，含「独立集合差=['B22']」 |
| B | B23 候选从登记表摘除 | 3 项 FAIL |
| C | B13 tol 放水回 0.10 | 反向漏抓 ⇒ 第 ④ 项 FAIL |
| D | B24 宇称索引改回 `i010=1` | B24 正向 `d/tol=2.7e+02` FAIL + 47/48 回归 + verified 11≠12 |
| E | B12 `candidate` 字段摘除 | 独立数 11 < 12 |
| F | B24 `ncut=1`（求解器算废/抛异常） | 47/48 回归 FAIL（**异常路径被归入自证桩，不出现在「正向」行** —— 与超差路径归属不同） |
| G | B22 网格改 N=200（太粗） | B22 `d/tol=1.9e+01` **假红** |
| H | B23 截断改 ncut=40（太精） | 「标非自证桩却 \|diff\|≡0 的**假独立**=['B23']」 ⇒ **H 这条证明了双向标定不是空话** |

还原后 smoke `rc=0`，**8/8 处护栏确认会响**。

⚠️ **诚实边界**：严格独立 **12/48**、自证桩仍有 **35** 道。提高的是「可被外部验货的比例」，不是单道验证强度；
B13 有**已知反向盲区**（Cc / E_J 两组键漏抓）已写进 note；剩余 35 道按 P0 计划继续接线。

### 改动六：🔴 B24 候选返回类型修正（全量回归抓出，v0.9.17 收口关键）

**全量 `--tag core` 回归第 1 条就 FAIL**：`run_harness.py` 抛 `TypeError: Object of type bool is not JSON serializable`。
根因：B24 候选 `tcoup_fock_exact` 原 `return -mag if ... else mag` 中 `mag = 0.5*(e_hi-e_lo)` 是 **numpy 标量（np.float64）**，
⇒ harness 比较 `abs(cv-ov) < tol` 产生的 `passed` 成了 **np.bool_**，`format_json` 序列化即炸。
可证伪性 smoke 不调 `format_json` ⇒ 8/8 全绿**掩盖了它** —— 又一次实证「全绿 ≠ 无失真、发版前必跑全量回归」。
修复：`verification_adapters.py` 第 637 行 `return float(-mag if ... else mag)` 显式转 python float（其余四道候选早已 `float()` 包裹）。
修复后复跑 `run_harness.py` **RC=0**，`verified=12 · 自证桩 35 · 48/48 闭合`。

---

## v0.9.16（2026-09-02 · P0-3 闭合 + 光子侧低成本批次 · 严格独立 4 → 7）

**指令**：v0.9.15 收口后，杜先生拍板下一步 = **P0-3 + 光子侧低成本批次（B3/B4/B20）**。
理由：严格侧求解器早已躺在代码库，P0 是**接线段工作**，不需等 C 期解锁；风险可控、见效快。

**结果**：严格独立候选 **4 → 7**（B3/B4/B9/B20/B25/B26/B27）· 降级量级参考 **1**（E2）· 自证桩 **43 → 40**。

---

### 改动一：P0-3 闭合（`fdfd_ng` 登记 + 三分类判序）

v0.9.15 遗留缺口：端点 `harness_cli.self_consistent_stub_count` 写 44，
而路径①（内部 smoke）真实自证桩是 43 —— 因为 `fdfd_ng` **没登记进** `BENCHMARK_CANDIDATES`，
E2 在路径①是真 FDFD 候选（golden 1.892 / cand 1.9587 / |diff|=0.0667），在路径②却回落成自证桩。

- `verification_adapters.py`：`_fdfd_ng_candidate` 用 `@_register_candidate("fdfd_ng", ...)` **正式登记**，
  docstring 写明「直波导候选 vs 环器件 golden **几何不同源**，仅作量级参考」。
- `harness.py`：新增三分类常量 —— **全库唯一定义处**：
  ```python
  CANDIDATE_CLASS_STRICT   = "strict_independent"
  CANDIDATE_CLASS_DEGRADED = "degraded_ordinal"
  CANDIDATE_CLASS_STUB     = "self_consistent_stub"
  ```
  新增 `IndependentCandidateRouter.candidate_class(bid)` / `describe_trichotomy()`；
  `is_independent(bid)` 改为 `candidate_class(bid) == CANDIDATE_CLASS_STRICT`。
- `BenchmarkResult.__init__` 加 `candidate_class` 字段；`VerificationHarness.run` 优先消费三分类 API
  （`getattr` 探测，兼容未改造的旧 candidate 对象）。
- `report.py`：新增 `candidate_class_counts()`；`independence_counts` 在三分类可用时取**真实自证桩数**
  （degraded 不再混进来）；`_MIXED_WARNING` 拆出「仅自证桩」与「含降级」两种措辞；
  `format_json` summary 增 `candidate_class_totals`、results 每项增 `candidate_class`。
- `routes.py`：`self_consistent_stub_count` 从 `len(_stub)+len(_degraded)` 改回 `len(_stub)`
  （闭合后不再需要「44 vs 43」的散文解释）；`detail` 改写为「✅ P0-3 已于 v0.9.16 闭合」。

🔴 **判序是本改动的命门**（`candidate_class` 内固定为「先降级 → 再查表 → 否则自证桩」）：

| 判序 | E2 结果 | `verified` | 性质 |
|---|---|---|---|
| 先判降级 ✅（本版） | degraded | 7 | 真实 |
| 先查登记表 ❌ | strict 且 PASS | **8** | **假绿** |

「接线越多越容易假绿」的典型：登记动作本身是**对的**，但少了「先判降级」这一步，
登记就会把降级项抬成独立项。反向自检 A 精确复现（见下）。

---

### 改动二：光子侧 B3/B4/B20 接线（频域峰周期拟合）

新增 `verification_adapters.py` 1c 节，三个候选：

| 锚题 | 候选 | 数值响应 | 残差 rel | d/tol |
|---|---|---|---|---|
| B3 | `fp_fsr_peakfit` | Airy `T=1/(1+F·sin²(δ/2))`，δ=4πnL/λ | 1.4e-8 % | 1.7e-08 |
| B4 | `ring_fsr_peakfit` | add-drop drop 口 `D∝1/|1−a·t·e^{−iφ}|²` | 2.0e-7 % | 6.2e-08 |
| B20 | `mzi_fsr_peakfit` | `T=½(1+cos(2π·n_eff·ΔL/λ))` | 2.3e-9 % | 4.7e-04 |

🔬 **关键方法学：FSR 必须按「频域周期」取值，不能按「相邻峰波长间距」。**
谐振/干涉峰满足 光程 = m·λ ⇒ **1/λ_m 严格等距**；教科书闭式 FSR_λ = λ²/光程
只是该频域等距性在 λ0 处的**一阶连续化**，与「相邻峰实测波长间距」相差 O(1/m)：

| 锚题 | m | 闭式 vs 实测峰间距 | 若按波长间距取值 |
|---|---|---|---|
| B3 | ≈12.9 | **6.7 %**（8.1 nm） | 假红（超 tol=1.0） |
| B4 | ≈169 | 0.59 % | 假红 |
| B20 | ≈77.5 | 1.29 %（0.26 nm） | 假红（tol=1e-6 的 **26 万倍**） |

🔧 **网格规模是刻意标定的**：`_FSR_GRID_N = 50001`。太粗 ⇒ 残差超 tol（B20 的 tol=1e-6 最紧）⇒ 假红；
太精 ⇒ 残差掉到 1e-12 以下、**与自证桩按值不可区分** ⇒ 护栏误报假独立。
实测扫描 20001/50001/100001/200001 后选 50001：三道残差 1.7e-8 / 1.9e-8 / 4.7e-10，
离 1e-12 判据有 ≥467× 余量，同时远低于各自 tol。

🚫 **峰位只做三点抛物线亚网格细化，不做牛顿/二分精化** —— 打磨到机器精度会让 |diff| < 1e-12，
与自证桩不可区分，反而毁掉可证伪性（理由写进代码注释，防止后人"优化"掉）。

🔴 **三道 tol 一律未放宽**。放宽 tol 等于取消验证，是 P0 纪律红线；实测余量充足（B20 达 2000×）。

---

### 改动三：护栏升级为三分类双向复核

`run_harness.py` 假独立断言 + `run_benchmark_falsifiability_smoke.py` 第 ⑧ 项，
均从**单向**（只查「标独立者 |diff| 非零」）升级为**双向**：

| 方向 | 判据 | 抓什么 |
|---|---|---|
| ① | 非自证桩 ⇒ \|diff\| 必须 **非零** | 回落 golden 的**假独立** |
| ② | 自证桩 ⇒ \|diff\| 必须 **为零** | 新接线被误分类吞掉的**漏算** |

只做 ① 会放过「路由已改坏、标签仍为真」的假绿（v0.9.15 血案）；只做 ① 也放过
「某道已接独立候选却被标成自证桩」的漏算。

smoke 同步：`MIN_INDEPENDENT` 4 → 7；`PERTURB_SPEC` 新增 B3@L、B4@R、B20@deltaL_um 三道 10% 扰动；
正向检查额外披露 `d/tol` 比值。

---

### 反向自检：五处篡改全部被抓（护栏真的会响）

| # | 篡改手法 | 实测报错 |
|---|---|---|
| A | `candidate_class` 判序反转（先查表后判降级） | `独立数=8≠路径①7；路径②三分类=(8,0,40)≠路径①(7,1,40)` |
| B | B20 候选静默回落 golden | `标非自证桩却 \|diff\|≡0 的假独立=['B20']` |
| C | B1 漏分类（已接线却标自证桩） | `标自证桩却 \|diff\|≠0 的漏算=['B1']` |
| D | 对外 stub 口径改回旧值 41 | `CLI stub=41≠40` |
| E | CLI 自身断言（同 B 手法） | `AssertionError: 标为独立/降级候选却 candidate≡golden（假独立）：['B20']` |

全部 `finally` 还原，`grep` 确认无残留。自检脚本 `_tamper_check.py` 保留在工作区（可复用）。

---

### 实测验收

- **可证伪性 smoke 8/8 PASS**：
  `严格独立=7 ['B20','B25','B26','B27','B3','B4','B9'] · 降级=['E2'] · 自证桩=40/48`；
  正向 d/tol 全量披露；反向 10% 扰动三道全 FAIL（B20 灵敏度 ≤0.1%）；全量 48 锚无回归。
- **路径②三模式全通**（exit=0）：默认 `verified=7 / 降级 1 / 自证 40`；
  `--perturb 0.10` → 10；`--ai` → **2**（诚实值，未误伤）。
- **版本号**：`pyproject.toml` 0.9.15 → 0.9.16。

⚠️ **诚实边界（未变）**：严格独立 **7/48**，自证桩 **40/48**。提高的是「可被外部验货的比例」
而非单道验证强度；光子侧新接三道验证的是**峰位周期性**（干涉/谐振的基本物理），
不是器件全物理。剩余 40 道按 P0 计划继续接线。

---

## v0.9.15（2026-09-02 · P0-2 独立性接到对外验货面）

**指令**：战略审计（v0.9.13 基线）→ 杜先生拍板 E1=A「锚题独立候选化」→ P0-1 已完成，续做 P0-2。

**起因（v0.9.14 作用域缺口）**：
P0-1 接通的 4 道独立候选**只在路径①（内部 `build_harness_specs`+`cand_map`）成立**。
LDA 有三条验证路径各自用不同 candidate：

| 路径 | 入口 | v0.9.14 后状态 |
|---|---|---|
| ① | `build_harness_specs` + `cand_map`（内部 smoke） | ✅ 4 道独立 |
| ② | `harness.run(specs, ReferenceCandidate)`（`run_harness.py` 对外主报告） | ❌ 全自证、`verified=0` |
| ③ | `L3AISolverCandidate` → `_local_approx`（MCP/L1/WebUI） | ❌ 41 道 `return golden` |

**对外验货面走 ②③ ⇒ 「可被外部验货」战略没真正兑现。** 本次三线收口。

**改动一：路径②接线（CLI 默认候选改走路由）**
- `harness.py` 新增 `_SpecShim`（把 dict spec 适配成候选所需对象接口）+ `IndependentCandidateRouter`
  （按 `spec_id` 查 `BENCHMARK_DEFS[x].candidate` → `BENCHMARK_CANDIDATES` 分发，未登记者**诚实回落**
  参考候选，不假装已独立）。⇒ 路径①候选**零改动**复用到路径②。
- `BenchmarkResult` 加 `independent` **三态**字段：`True`=独立 / `False`=自证桩 / `None`=未标注旧路径。
  三态设计是为**渐进式改造**——只有显式路由的候选才改变 `verified` 语义，其余路径行为完全不变。
- `report.py`：新增 `independence_counts()` 与 `verified_count()`（**全库唯一权威口径**）；
  混合态下报告头部改为**分列陈述**「N 项独立 / M 项自证」，`format_json` summary 增
  `verified` / `self_consistent_stub_count` / `independent_candidate_count` 三字段。
- `run_harness.py`：默认候选 `ReferenceCandidate()` → `IndependentCandidateRouter()`；
  原单向断言（`verified == 0`）升级为**双向护栏**：
  ```
  verified ≡ 独立候选项数（多算=把自证桩当已验证，少算=独立候选被降级）
  stub     ≡ 总项数 − 独立候选项数
  verified + stub ≡ 总项数（不得有第三态漏算）
  混合态下报告必须出现「独立候选求解器」字样
  ```
- **实测**：`[D-64/P0-2] 混合态断言通过：独立候选 verified=4 · 自证桩 44 · 判决回路 48/48 闭合`；
  4 道误差非零（B25/B9 0.01475、B26 4.573e-05、B27 13.76）。旧路径零波及（`--perturb` 仍 10、`--ai` 见下）。

**改动二：路径③治理（假绿修复）**
- `l3_ai_solver.py` 订正 **B3/B10 两处注释与实现不符**（注释写"正确实现"、实际 `return golden`）。
- 新增 `_LOCAL_INDEPENDENT_IDS = {B1,B2,B4,B8,B9}`——真有独立实现的只有 5 道，不是 41 道。
- 新增 `is_independent(bid)`：**LLM 启用时一律返回 False**（项目红线：LLM 不进判决路径）。
- **实测**：`--ai` 的 `verified` 从 **假绿 45 → 诚实 2**（5 道独立中 B2/B8/B9 故意错判 FAIL，仅 B1/B4 通过）。

**改动三：对外账本去硬编码**
- `/api/verification_ledger` 的 `judgment_paths` 原写死 `independent_candidate=["E2"]`，
  **而 E2 恰是 v0.9.14 已降级那道，新接的 B9/B25/B26/B27 一道都没出现** ⇒ 对外验货面失真。
  与 `run_count_consistency_smoke` 守护的 ci_core 漂移（82→85）属**同一类缺陷：写死 vs 实际**。
- 改为从 `BENCHMARK_DEFS[*].candidate` × `BENCHMARK_CANDIDATES` **动态推导三分类**，
  判序固定为「先判 `degraded_ordinal`、再查登记表、否则自证」（E2 的 `fdfd_ng` 未登记进
  `BENCHMARK_CANDIDATES`，若按登记表判断会被误分到 stub）。
- `judgment_paths` 增 `derived` 块（三分类 + totals + definitions），`empirical` 拆独立/降级/自证三字段，
  `harness_cli.verified` 改动态；`open_gaps` 的 R15 重写（原「复制 E2 模式到其余六道」已作废——E2 自身已降级）。
- **生产实测**：`{"anchors":48,"strict_independent":4,"degraded_ordinal":1,"self_consistent_stub":43}`，三类和=48。

**改动四：新增第 ⑦⑧ 两项常驻护栏（钉死口径不漂移）**
`run_benchmark_falsifiability_smoke.py` 6 → 8 项：

- **⑦ 对外口径**：直接调 `h_verification_ledger`，断言端点三分类**逐项等于**本机实测
  分类（独立/降级/自证集合差 + 总和 + CLI verified）。这样「登记表漏登记 /
  候选跑挂回落 golden / 分类条件被改坏」三类失效都会被抓。
- **⑧ 路径②一致**：在进程内复现路径②（`VerificationHarness.run` + `IndependentCandidateRouter`，
  **不写报告文件**以免每次回归污染工作区），断言其 `verified` 口径与路径①一致、48 题
  **全部按题标注**独立性、且**标独立的题 |cand−golden| 必须非零**。
  为什么需要它：`ci.yml` 第 29 行会直跑 `run_harness.py`，但**本地 `--tag core` 门禁不跑它**
  ⇒ 本地存在覆盖盲区（与 v0.9.10「脚本在 ci.yml 却不在本地 core」同类缺陷）。

**🔴 反向自检三连（护栏自身必须先被证伪）**

| # | 篡改手法 | 结果 |
|---|---|---|
| ⑦ | 端点分类条件改成 `if False and ...` | ✅ 立刻 `exit=1`，精确报 `降级集合差=['E2']；自证集合差=['E2']` |
| ⑧ 首版 | 把 `router.__call__` 改成全回落 golden | ❌ **仍 PASS** —— 护栏无效！ |
| ⑧ 加强版 | 同上 | ✅ 立刻 `exit=1`，精确报 `标独立却 \|diff\|≡0 的假独立=['B25','B26','B27','B9']` |

**⑧ 首版为何无效（关键教训）**：它只核对 `independent` **标签**，而该标签来自
`is_independent(bid)`（查登记表），被改坏的是 `__call__`（查表后执行）——
**标签为真、实现已回落**，护栏看不出来。**标签 ≠ 行为**。
⇒ 加强为**按值复核**：凡标独立的题，实测 `|candidate − golden|` 必须 `≥ 1e-12`。

**顺带查出 CLI 自身断言有同一个洞**：`run_harness.py` 也是只看 `independent` 标签，
同样会被「标签为真、实现回落」骗过 ⇒ 补同款按值复核。
- ⚠️ **但语义必须按路径区分，否则会误伤**：
  - 路径② `IndependentCandidateRouter` 承诺的是「golden=解析闭式 ↔ candidate=严格数值」
    **方法学不同源** ⇒ `|diff|` 必须非零，为 0 **只可能是静默回落** ⇒ 严格断言。
  - 路径③ `--ai`（L3 AI 内核）验证的是「**AI 写的内核对不对**」⇒ `|diff|≡0` 表示
    **内核把公式算对了**（实测 **B1/B4** 即此情形：AI 内核独立重算 Rayleigh / 环形 FSR
    闭式，与 golden 数值一致），是合法 PASS **而不是**回落失败。
  - 一刀切会把「算对了」误判成「假独立」（实测确实误报过：`AssertionError: 假独立=['B1','B4']`）
    ⇒ 该断言用 `isinstance(candidate, IndependentCandidateRouter)` **按路径收敛**。

**验证结果**
- `run_benchmark_falsifiability_smoke.py` **8/8 PASS**，末行 `严格独立 4 道 · 降级量级参考 1 道 · 自证桩 43/48 道`。
- 路径②实跑：混合态断言通过（verified=4 / stub=44 / 48-48 闭合），4 道误差非零。
- `run_harness.py` 三模式全通：默认 `verified=4` / `--perturb 0.10` `verified=10` / `--ai` `verified=2`。
- 端点三分类：生产实测三类和 = 48。

**补记：生产实测又查出对外与实际的 1 处口径差（E2 在路径② 回落）**

生产外网实测三分类正确（4 / 1 / 43，和=48），但核对 `harness_cli` 时发现：
端点写 `self_consistent_stub_count=43`，而 `run_harness.py` 报告**实际是 44**。

- **根因（实测确认）**：`fdfd_ng` **未登记进** `BENCHMARK_CANDIDATES` ⇒
  - **路径①**（`build_harness_specs`）：E2 走真 FDFD 候选，实测 `golden=1.892 / cand=1.9587 / |diff|=0.0667` ⇒ 分类为「降级量级参考」
  - **路径②**（`IndependentCandidateRouter`）：查表未命中 ⇒ **回落参考候选**，diff≡0 ⇒ 被计入「非独立」
- 故路径② 的 stub = 三分类 stub(43) + degraded(1) = **44**，端点写 43 是**对外宣称与实际差 1**
  （与 ci_core 漂移、写死 `["E2"]` 属**同一类缺陷**）。
- **已修**：`harness_cli.self_consistent_stub_count` 改 `len(_stub) + len(_degraded)`，
  新增 `trichotomy_totals` 字段把两套口径**同时暴露**（不再让人二选一），
  并加注说明这是低估而非虚报（`verified` 计数不受影响）。
- **护栏 ⑦ 补两条断言**：CLI stub 必须 = 三分类 stub + degraded；`trichotomy_totals` 必须逐项相等。
  反向自检：把数字改回 43 ⇒ smoke 立刻 `exit=1` 报 `CLI stub=43≠44`（再次证明会响）。
- 🔴 **登记 P0-3 缺口（未修，留给下一批）**：路径② 少接 E2 这一道。修复需把 `fdfd_ng`
  登记进 `BENCHMARK_CANDIDATES`，**同时**让 `is_independent` 尊重 `candidate_status=degraded_ordinal`
  —— 否则 E2 会被判为独立且 PASS ⇒ `verified` 从 4 虚报成 5（假绿）。这是"接线越多越容易假绿"的典型。

**诚实边界（未变）**
独立候选仍只有 **4/48**。本次是**让对外如实显示这个数字**，而非提高验证强度；
`--ai` 的 45 → 2 是**戳破假绿**，不是能力倒退。剩余 43 道自证桩按 P0 计划继续接线
（下一批候选：B12/B22 离散 TL 三对角、B13/B24 电荷基/三模 Fock、B23 Fluxonium 相位网格、光子侧 B3/B4/B20）。

**CI core**：维持 85 条（本轮为既有 smoke 增项，未新增文件）。

---

## v0.9.14（2026-09-02 · P0-1 锚题独立候选化 · 反自证桩第一刀）

**指令**：战略审计（v0.9.13 基线）后，杜先生拍板 E1=A「锚题独立候选化」，开工 P0。

**起因（2026-09-02 战略审计实测）**：
- 48 锚实跑 48 PASS，其中 **47 道是自证桩**——`build_harness_specs` 对所有非实证锚
  一律落 `_harness_reference_candidate`（直接返回 golden），|cand−golden| ≡ 0 恒 PASS、零验证价值。
- 结构性缺陷：**B 类 28 道连"接入独立候选"的入口都没有**（只有 E 类能指定 `candidate: "fdfd_ng"`）。
- **全绿 ≠ 可证伪**：84/84 全绿与 47/48 自证桩并不矛盾，前者只证明无回归。

**改动（P0-1 · 4 道真独立候选）**：
1. **首开 B 类接入口**：`verification_adapters.py` 新增 `BENCHMARK_CANDIDATES` 注册表 +
   `_register_candidate` 装饰器；`build_harness_specs` 按 `BENCHMARK_DEFS[x]["candidate"]`
   查表分发（未登记者诚实保留自证桩，不假装已独立）。
2. **接通 4 道**（golden=解析闭式 ↔ candidate=严格数值对角化，方法学独立）：
   | 锚题 | golden | 独立候选 | 实测偏差 | tol 变更 |
   |---|---|---|---|---|
   | **B9** | Koch 色散近似 | 电荷基严格对角化（41 维 eigh） | rel 0.22% | 0.05（原就合理，未动） |
   | **B25** | Koch(Φ) | 同上（E_J(Φ)） | rel 0.22~0.40% | 1e-6 → 0.05 |
   | **B26** | Blais 微扰闭式 | L=6 多能级+Fock 联合对角化（162 维 eigh） | rel 1.98% | 1e-6 → 1e-4 |
   | **B27** | t_CZ=π/(2\|χ\|) | 严格 χ 反推 | rel 2.02% | 1e-6 → 30ns |
   - tol 放宽依据：实测偏差的 **2.2~2.5 倍余量**，逐条写入 note（不拍脑袋）。
   - 🔍 顺带实证：**B9 的 tol=0.05 是早期按物理容差设的**，恰好合理；B20–B28 后期锚清一色
     `tol=1e-6`——该量级设计上只容得下 candidate≡golden，即"自证桩容差"。
3. **`candidate_status` 字段**：把「降级量级参考」（E2，FDFD 直波导候选 vs 环 golden 几何不同源）
   从散文 note 变为**机器可读**，杜绝用已降级锚充数虚报独立强度。

**新增常驻护栏 `run_benchmark_falsifiability_smoke.py`（入 CI core，84→85）**：
- ① 独立候选数下限（当前 4，随进度递增）② 正向 PASS ③ **反向测试：10% 参数扰动必 FAIL**
  ④ 灵敏度登记（最小可检出扰动）⑤ 全量 48 锚无回归 ⑥ 披露剩余自证桩清单。
- **为什么③比②重要**：②只能证明"没坏"，③才能证明"坏了能发现"。只做②不做③，
  等于把「放宽容差」变成「取消验证」——正是自证桩的翻版。

**⚠️ 诚实边界（反向测试实测暴露）**：
- **B26 在 g 扰动 +1% 处 diff=1.68e-6，反而小于未扰动时的 4.57e-5** —— 扰动方向与
  （闭式↔数值）近似误差**偶然抵消**。属物理正常现象，但意味着**小幅系统误差存在检测盲点**，
  这是放宽容差所付的代价 → 反向测试取 10% 稳健档（该档 4 道全 FAIL），而非单点小扰动。
- **B27 与 B26 共用同一数值 χ**，独立性弱于 B26，只验证「χ→t_CZ 换算链路」，不重复计入独立强度。
- 灵敏度实测：B9 ≤2%、B25/B26/B27 ≤5%（断言上界 ≤10%）。

**验证**：独立候选 0→**4 道**（严格独立，E2 另计为降级量级参考）；48 PASS / 0 FAIL，耗时仍 1.1s；
关键 smoke 全绿（harness 48/48、实证锚 29/29、计数守护 11/11、新冒烟 6/6、
benchmark crosscheck / quantum design / quantum devices / device_library / statistical 均 EXIT=0）。

**⚠️ 作用域澄清（重要，避免高估本轮成果）**

LDA 存在**三条验证路径，各自用不同 candidate**，本轮改动**只覆盖第 ① 条**：

| # | 路径 | candidate | 使用方 | 本轮后状态 |
|---|---|---|---|---|
| ① | `build_harness_specs` + `cand_map` | 按题查表分发 | `run_empirical_anchor_smoke`、新增的 `run_benchmark_falsifiability_smoke` | ✅ **4 道独立**（B9/B25/B26/B27） |
| ② | `harness.run(specs, ReferenceCandidate)` | 恒定 `return golden` | **`run_harness.py`（对外主报告）** | ❌ 仍全自证，`verified=0` |
| ③ | `L3AISolverCandidate` → `_local_approx` | 未配置 LLM 时回退；41 道 `return golden` | **MCP / L1 协议 / WebUI** | ❌ 仍全自证 |

- 因此「48 锚中 4 道可证伪」**仅在路径①成立**。对外验货面走的是 ②③，仍显示 `diff=0`。
  报告里 `verified=0` 在 ②③ 下是**准确的**（不是失真），因为它如实反映那两条路径仍是自证。
- 接线成本很低（② 只需一个按 `spec_id` 路由的适配器，约 15 行；`harness.run` 已接受
  `callable(spec, golden, params)`），但会改变对外报告与 `run_harness.py:117` 的
  `verified==0` 断言 ⇒ **登记 P0-2，本轮不动**（回归在跑，不叠加改动面）。

**未做（按 P0 计划顺延）**：剩余 **43/48 仍为自证桩**（全部 S 类 13 道 + E1/E3-E7 +
B1-B8/B10-B24/B28），需继续接线；E2 建议的 numpy 版 DC/YB 候选（E2 决策点）未动。

**🔴 本轮顺带挖出：第二条自证桩路径（登记为 P0-2，本轮不动代码）**

改动 B25/B26/B27 的 tol 后复跑，发现 `lda/reports_mcp/verification_report.md` 里这三道
**diff 仍是 0** —— 该报告头部写明 `candidate：L3AISolverCandidate`，走的是**不同于**
`build_harness_specs` 的第二条验证路径（`lda_harness/l3_ai_solver.py`）。

- 机制：`L3AISolverCandidate` 未配置 LLM 端点时回退 `_local_approx()`，而该函数
  **只对 B1/B2/B3/B4/B8/B9/B10 七道有实现**（其中 B2/B8/B9 还是**故意**写错以演示
  harness 的 FAIL 判别能力），**其余 41 道一律 `return golden`** ⇒ diff=0、全 PASS。
- 影响面：该路径被 **`lda_webui/app.py:356`** 与 `lda_l1/protocol.py:121` 直接使用，
  **对外可见** —— 外部验货者看到的「全 PASS + diff=0」实为自证，非验证。
- 性质判定：这条是 **L3「AI 写内核」的演示/沙盒路径**（设计意图是演示 harness 判别能力，
  非判决路径），与 harness 判决路径性质不同；但因其对外暴露，存在误导风险。
- 处置：**登记 P0-2，本轮不动代码**（回归在跑，不叠加第二处改动面）。
  待办方向：①默认分支改为显式"未实现"并返回非 golden 的哨兵值
  ②报告头部标注「演示/沙盒路径，非判决结论」③或限制其不对外暴露。

**P0-2 合并规划（路径 ②③ 接线，下一轮）**：
- ② `run_harness.py`：默认 candidate 从 `ReferenceCandidate` 改为**路由适配器**
  （按 `spec_id` 查 `build_harness_specs` 的 `cand_map`，未登记者回退 `return golden`），
  同步把 `run_harness.py:117` 的 `verified==0` 断言改为 `verified>=1`（动态取独立候选数）。
  ⇒ 对外主报告首次显示真验证（`verified=4`），这是「可被外部验货」战略的直接兑现。
- ③ `l3_ai_solver._local_approx`：默认分支改为显式未实现哨兵值 + 报告标注演示路径。
- 预期收益：可证伪锚题在**对外验货面**从 0 → 4（当前仅内部路径可见）。

---

## v0.9.13（2026-09-01 · R16 实测证伪 + 诚实边界 C 降级）

**指令**：开始 R16 阶段1（sub-cell 体积分数 averaging），实测证伪原假设，杜先生拍板 C 诚实边界降级。

**R16 阶段1 实测结论（重大反向）**：
- 在 `build_waveguide_field_3d` + `fdfd_neff` 启用 sub-cell averaging（界格点 ε 按芯/包层体积加权），
  用 corpus golden 同源几何复跑 FDFD 对照：SOI n_g **3.776→3.741 恶化**、SiN n_g **1.961→1.928 恶化**；
  D-65 窗口散射 SiN ±0.0385→±0.0018（改善）、SOI ±0.0215→±0.0305（略恶化）。
- 网格 dl_factor 24→64 扫描：n_g **纹丝不动**（SOI~3.72 / SiN~1.93），偏差与网格无关。
- 直波导 n_eff 直检：SOI=2.62（文献~2.44，+0.18）/ SiN=1.61（文献~1.98，−0.37）→ **求解器本身精度不足**。
- 🔴 两层根因（均非网格）：①最简标量 FDFD 对高反差细波导 n_eff 偏差 0.18~0.37；②**对象不对齐**：
  golden 4.18/2.2834 是**弯曲/环器件**群折射率（Garrisi 用 ring FSR 反演；E-SIN 是 R=100µm 环），
  FDFD 解直波导，弯曲使模式更受限→n_g 天然高 ~0.46。
- **R16 原假设（「网格过粗导致偏差，上 averaging/细网格解锁 E1/E2/E3」）被实测证伪**。
  sub-cell averaging 单独使用恶化绝对精度且无净收益（D-65 窗口散射原本就 <±0.04 达标）。
- 纪律：averaging 两处**回退**（工作区源码干净），**不提交实验态假绿**。
- 附：D-65 原「网格过粗」诊断不实——±0.042 实为**窗口扫描**散射非网格（dl 24→64 已收敛）。

**C 诚实边界降级（杜先生拍板）**：E1/E2/E3 的 golden 来自环器件，FDFD 直波导候选与之
「量纲同源、几何不同源」+ FDFD 求解器精度不足 → 仅作量级参考，不参加死标量对照；
E1 保持自证桩（candidate≡golden）。与 D-66 诚实边界一致。

**代码/文档同步（不假绿，全部改注记/诚实边界，不改判决逻辑）**：
- `benchmarks.py` E1/E2 note：R16 由「待根治」改为「已证伪 + 诚实边界 C」
- `run_empirical_anchor_smoke.py` D-65 护栏注记：R16 已证伪
- `lda_webui/routes.py` open_gaps R16：标注已证伪 + 与战略审计 R16（单人瓶颈）编号撞车提示
- `benchmark_report.py` Waveguide empirical_dim_note：扩展为量纲+几何不同源 + FDFD 精度不足 + R16 证伪
- `docs/lda_d64_replication_feasibility.md`：R16「最高杠杆一次性解锁 E1/E2/E3」改为已证伪
- 注：战略审计文档的 R16 = 单人瓶颈（商业模式），与此处 FDFD 缺口 R16 编号撞车，已分别标注

**验证**：全量 core 回归 84 PASS / 0 SKIP / 0 FAIL；empirical_anchor_smoke / D-65 护栏仍 PASS

## v0.9.12（2026-09-01 · CI 达标线政策化：80% → 90%+）

**指令**：CI 达标线随语料补充逐步上调至 90%+。

**改动**（治理向，不影响引擎逻辑、不影响生产运行时行为）：
- `lda/run_provenance_audit.py`：`--min-ratio` 默认由 **0.80 → 0.90**。
  这是审计脚本的**宽松下限基线**；当前语料库 A 级占比 100%（30/30），90% 基线轻松达标。
- `lda/run_empirical_anchor_smoke.py`：注释明确达标线演进政策——
  **80% → 100%（B 级零容忍）**，且当前下限 90%+、强制门禁 100%。

**纪律澄清（🔴 不回退）**：
提交门禁（硬 gate `traceable_ratio >= 1.0`）**维持 100% 死守**，不下调到 90%。
理由：实证锚是「第二道非 AI ground」，其可信度完全建立在可独立复验上，
任何一条 B 级语料混入都会稀释该 ground。90%+ 仅是审计宽松基线，
CI 提交门禁的强制线仍是 100%（B 级零容忍）。

**验证**：溯源审计（默认 0.90）达标 ✅ · 实证锚 smoke 29/29 PASS ✅ · 计数守护同步版本线。

## v0.9.11（2026-09-01 · D-67 回归修复 · 链路预算漏算 3.0103dB 分光 + 双护栏）

🔴 **v0.9.10（D-66）引入了一个「假绿」回归，本次修复并加装护栏。**

**根因**：D-66 判定「3.01 dB 是 1×2 功率均分的几何必然、非器件品质指标」——**这个判定本身是对的**，
但实现时把 `engine_ybranch_split` 的默认输出 `value` 从「含分光的分支插损 `split_loss_dB`」
直接改成了「过量损耗 `excess_loss_dB`」。而该引擎的 `value` **同时是链路预算的被加数量**
（`golden_product_benchmarks._photon_cascade_il` 的 `n_yb * yb`），于是**每个分束器少算 3.0103 dB**。

**影响面（5 条整芯片链路 + 1 条器件级，全部静默）**：

| 条目 | 修复前（v0.9.10 漏算） | 修复后（正确） | 偏差 |
|---|---|---|---|
| GC-PLC-1X8（3 级分光） | 0.33 dB | **9.3309 dB** | −9.0 dB |
| GC-PLC-1X16（4 级分光） | 0.44 dB | **12.4412 dB** | −12.0 dB |
| GC-SENSE（2 级） | 7.63 dB | **13.6508 dB** | −6.0 dB |
| GC-QKD-TX（2 级） | 7.54 dB | **13.5638 dB** | −6.0 dB |
| GC-CPO-8CH（1 级） | 7.62 dB | **10.6335 dB** | −3.0 dB |
| GP-YBRANCH | 0.10 dB（拿过量损耗比总插损 golden 3.15） | **3.1103 dB** | 语义错配 |

**为何 84/84 全绿没抓到（三重失真叠加）**：
1. 插损类 metric 方向为 `le`（**越小越 PASS**）→ 「少算损耗」被伪装成「设计做得更好」；
2. `run_golden_product_smoke` 只校验 PASS **条数**，不校验死标量数值；
3. `ProductBenchmark.evaluate` 在 metric 名对不上时**静默回退**到 `out["value"]`
   → 「拿 A 量比 B golden」不会报错。

**修复（原则：分离而非替换 —— 两个量都真实存在，各归其位）**：
- `engine_ybranch_split` 同时输出两个**互斥且互补**的量：
  `value`/`metric` = **`split_loss_dB`**（链路预算量 = 3.0103 + 过量，向后兼容）；
  `excess_loss_dB` 以**同名字段**显式暴露（器件品质量，供实证锚对照）。
  新增模块常量 `SPLIT_LOSS_3DB = −10·log₁₀0.5 = 3.0103`。
- `resolve_corpus_engine` 改**按 metric 名取值**（不再一律取 `"value"`）。
- `_loss_verify` / `_loss_cheap` 新增 `field` 参数；`YbranchLoss` 显式传
  `field="excess_loss_dB"`，使「搜索目标 / 判决量 / golden」三者同量纲。

**新增两道护栏（均已做反向测试，证明会响）**：
1. **能量守恒下界**（`_photon_cascade_il`）——每个 1×2 分束器的每支路插损不可能低于
   3.0103 dB（能量守恒，与工艺水平无关）。⚠️ 关键设计：必须**按贡献项逐项守底**，
   不能用「总插损 ≥ n_yb×3.0103」——反向测试证明混合判据会让 GC-CPO-8CH / GC-SENSE /
   GC-QKD-TX 三条因其他损耗垫高而**逃逸（只抓住 2/5）**；逐项守底才 5/5 全抓。
2. **metric 语义错配硬失败**（`ProductBenchmark.evaluate`）——MetricSpec 声明的量在
   引擎输出里既不是主 metric 也不是显式字段时，**禁止静默回退到 `value`**，直接报错
   （宁可红，不可假绿）。

**护栏的护栏**：`run_golden_product_smoke` 新增 **D-67 反向测试**——临时注入「漏算分光」
的坏引擎，断言两道护栏都命中（能量下界 5/5 + 语义错配 1/1），否则 smoke 直接 FAIL。
**没被验证过的护栏不算护栏。**

**同步改动**：`run_loss_engine_smoke` 新增 2 条引擎层双量语义 + 能量守恒断言（7→9 条，9/9 PASS）；
`design_engine.YbranchLoss` note / `loss_engines` 模块 docstring 如实标注双量不可混用。

🔴 **工程铁律（新）**：**改引擎默认输出 `value` 的语义前，必须 grep 全部 `["value"]` 消费点**，
而不只是同步改断言；**「越小越 PASS」的方向性 metric 必须配物理下界护栏**，
否则「算漏了损耗」会被伪装成「设计变好」——这是失真最隐蔽的一类回归。

## v0.9.10（2026-09-01 · 实证锚逐字核实 · D-66）

**指令**：5 条 B 级语料（E-SOI-NEFF-220 / E-SIN-NEFF-300 / E-YBRANCH-LOSS / E-RING-FSR / E-GRATING-EFF）**逐字核实**补 DOI/URL 才能升 A 级。纪律：**不编造 DOI、找不到就保持 B 级**。

**结果：语料库 A 级 25/30 → 30/30（100%），B 级清零；可溯源实证锚题 6/7 → 7/7。**

| 原 ID | 原 metric / 值 | 核实结论 | 处置 | 新值（可溯源出处） |
|---|---|---|---|---|
| E-SOI-NEFF-220 | n_eff 2.63 | **原值是错的** | 改判 n_g 锚 → `E-SOI-NG-220` | n_g **4.18±0.05**（DOI 10.48550/arXiv.2011.03273） |
| E-SIN-NEFF-300 | n_eff 1.53 | 无可溯源实测出处 | 改判 n_g 锚 + 按文献照实改写几何 → `E-SIN-NG-1200` | n_g **2.2834±0.05**（DOI 10.3390/coatings10040309） |
| E-YBRANCH-LOSS | split_loss_dB 3.4 | **量纲不符** | 改判实测**过量损耗** | excess_loss_dB **0.28±0.02**（DOI 10.1364/OE.21.001310） |
| E-RING-FSR | FSR_nm 9.15 | **系解析反算值**，非测量 | 换文献实测值 | FSR_nm **8.6±0.1**（arXiv:2011.03273，racetrack L=66.8 µm） |
| E-GRATING-EFF | coupling_eff 0.45 | 无出处 | 换文献实测值 | coupling_eff **0.42±0.05**（DOI 10.1063/1.3304791） |

**逐字引用（证据链，原文照抄）**

- E-SOI-NG-220 / E-RING-FSR：`"The resonator has the shape of a racetrack, it is 66.8 um long and its free spectral range (FSR) is 8.6 nm, from which we infer that its group index is 4.18."`
- E-SIN-NG-1200：`"The free spectral range (FSR) measured from the transmission spectra given in Figure 4b was estimated as 1.61 nm that resulted in the effective group index ng = 2.2834."`
- E-YBRANCH-LOSS：`"Measured average insertion loss is 0.28 ± 0.02 dB, uniform across an 8-inch wafer."`
- E-GRATING-EFF：`"A peak coupling efficiency of 42% at 1550 nm and 1 dB bandwidth of 37 nm, as well as a low back reflection, are achieved."`

**自洽校验**：λ²/(n_g·L) —— SOI 1547.6²/(4.18×66.8×10³)=**8.59 nm** ≈ 实测 8.6 ✅；SiN 1550²/(2.2834×640.3×10³)=**1.64 nm** ≈ 实测 1.61 ✅

### 三个「差点踩进去」的坑（方法论教训，价值高于结果）

1. **差点把仿真值当实测值**：arXiv:1909.09538 的 `−3.05 dB ~ −3.15 dB` 看似完美实测，逐字核对前文是 **`"This simulation is shown in Fig. 5"`** → **已排除**。只看数值不看上下文，会让两道 ground 短路，判决即自证。（PDF 经 curl 下载 + pypdf 提取才读到，WebFetch 三次失败。）
2. **metric 量纲陷阱**：Y-branch 的 3.4 dB 是**含 3.01 dB 理想分光的分支插损**，而文献实测的 0.28 dB 是**过量损耗**。3.01 dB 是 1×2 功率均分的**几何必然**（−10·log₁₀0.5），**非器件品质指标、非被测量的量**。直接拿 3.4 对 0.28 会得到一个量级的"偏差"，但那不是模型错了，是量纲错了。
3. **原 golden 本身就是错值**：`E-SOI-NEFF-220` 的 2.63 与文献及 **3 个独立模式求解器**一致结论（2.44~2.46）差 **0.19**（为其自称 ±0.02 的近 10 倍），2.63 实为 λ≈1.39 µm 处的取值。这类错误在"看上去合理"的数值上最难发现——**它不报错，只让所有对照系统性偏移**。原值存疑证据链保留在新 `note` 字段，不静默丢弃。

### 配套工程改动

- `EmpiricalMeasurement` 新增 **`note`** 一等字段（溯源核实批注；**判定路径不读**，仅作证据链，不影响任何死标量比较）。
- `loss_engines.engine_ybranch_split` 改为**只输出过量损耗**（剔除 3.0 dB 常数），与既有 `E-MMI-1X2-EL` 口径一致；`design_engine.YbranchLoss` / `design_package` 目标值 / `benchmark_report.DEFAULT_TARGET` 三处同步 3.4→0.28、0.45→0.42。
- B5 设计守则锚**保留不动**（理想 50/50 下限 3.0 dB），note 增 D-66 澄清：它与实证锚的过量损耗**非同一量、互补不可混用**。
- `benchmark_report` Waveguide 行：引擎输出 **n_eff**、语料实测 **n_g** → **量纲不同源如实披露**（`empirical_dim_note`，报告渲染带 ⚠️ 行），不假装同 metric 对照。
- 语料库 A 级达标线 **80% → 100%**（提交门禁已强制 A 级，存量不应再出现 B 级；实证锚可信度完全建立在可独立复验上，零容忍）。
- 下游同步 8 处：`benchmarks.py`(E1 锚) / `benchmark_report.py`(3) / `loss_engines.py`(2) / `design_engine.py`(2) / `design_package.py`(3) / `run_empirical_anchor_smoke.py`(4) / `run_d06_smoke.py`(5) / `run_loss_engine_smoke.py`(3) / `run_empirical_d62_report.py`(1) / `corpus_template.csv`。

### 🔴 顺带修掉：GitHub Actions 主干自 v0.9.8 起一直红灯

`empirical_bank.traceability()` 用 `from .provenance import ...` 相对导入，而 **ci.yml 以脚本方式直跑**（`cd lda/lda_harness && python run_empirical_bank.py`）→ `ImportError: attempted relative import with no known parent package`。该脚本 **不在本地 `CORE_SMOKES`**，故**本地全绿、主干红**（v0.9.8 D-63 引入）。修复为双路导入（包内相对优先，回退绝对），并**把该脚本纳入 core 门禁**（CI core 83→84），这类缺口今后由本地兜底。

> 又一次印证两条铁律：①**改判定/公共字段时，把依赖它的 smoke 一起改**；②**「宣称全绿」必须有近期实跑证据支撑**——本地 core 覆盖不到的脚本，等于没有门禁。

### 底数变化

语料 **30 条（A 级 30/30 = 100%，B 级 0）**· 可溯源实证锚题 **7/7** · 题库 48 题不变 · **CI core 83 → 84 条**。

### 诚实边界（不掩饰的缺陷）

1. **E-GRATING-EFF 结构不同源**：文献器件为**全刻蚀光子晶体孔阵**（孔径约 143 nm），与参数化周期光栅**非同一结构**；仅作量级对照，geometry **不构成 golden 判决输入**。
2. **n_g 由 FSR 反演得到**（E-SOI-NG-220 / E-SIN-NG-1200）：强于纯仿真（FSR 是直接测量量），但**弱于 n_g 直接测量**（如 E-SIN-NG-300 的 OFDR 群延迟法）；`method` 字段逐条标注反演路径。
3. **Y-branch 模型粗糙度如实暴露**：默认唯象系数 c1=0.004 dB/deg² 给 0.4 dB vs 实测 0.28 dB，**rel≈43%**。**不做拟合回算**（调 c1 让该点通过 = 用被验证量标定验证量，循环自证，见 E6 教训），改为**防回归护栏**（≤50%）并在检查名中标注「未标定，待真实 PDK 工艺标定」。
4. **E1 升 A 级 ≠ 判决路径变真**：E1 的 candidate **仍是占位自证桩**；且标量 FDFD 对高对比度 SOI 差约 10%，即便接入也必 FAIL，需待 **R16**（亚网格 ε 平均）。golden 可溯源只是必要不充分条件。

---

## v0.9.9（2026-09-01 · 判决路径独立性整改 · D-64）

**🔴 审计发现：实证锚判决路径为空（7 道全是假绿）。** v0.9.8 把「golden 必须真实可溯源」这条做到了，但漏了另一半——**candidate（候选求解器）也必须独立求解**。`verification_adapters.py` 的 `_harness_reference_candidate` 直接 `return oracle_value`，实测 E1-E7 七道 `|candidate − golden| ≡ 0.0000`：

```
ID   metric              golden   candidate  |diff|
E1   n_eff                 2.63       2.63   0.0000   ← 自证
E2   n_g                  1.892     1.9587   0.0667   ← 整改后独立求解 ✅
E3   FSR_nm               10.44      10.44   0.0000   ← 自证
E4   insertion_loss_dB     0.18       0.18   0.0000   ← 自证
E5   excess_loss_dB        0.05       0.05   0.0000   ← 自证
E6   propagation_loss_dBcm 0.087     0.087   0.0000   ← 自证
E7   crosstalk_dB         -41.0      -41.0   0.0000   ← 自证
```

这也解释了为什么 v0.9.8 把 E3 golden 从 9.15 改成 10.44 后 smoke 仍全绿——改的是 golden，而 candidate 恒等于 golden。项目内部其实**知情**（`benchmarks.py` 有 9 处 note 写「harness 默认 ReferenceCandidate 自洽 PASS」），属已知占位设计；我的疏失是 v0.9.8 改 E1/E2 note 时把这句标注弄丢了。本轮补回并**强化为三处明示**：note / 报告 `candidate_desc` / CI smoke 断言。

**整改（按杜先生拍板「先打通 E2 样板再复制」）：E2 单题做完整闭环。**

- **几何对齐**：E2 原 500nm 宽波导与任何公开实测器件都对不上，改为 **1000×300 nm**（对齐 Munoz 300nm Si₃N₄ 平台实测器件）。
- **golden 换 A 级实测**：新增语料 `E-SIN-NG-300`，**n_g = 1.892**（TE），来源 `https://www.mdpi.com/1424-8220/17/9/2088`（P. Munoz et al., *Sensors* 17, 2088, 2017）——OFDR 环形谐振腔群延迟实测（1514–1594 nm 线性拟合）+ MZI 传输谱交叉验证 1.90–1.92，TM=1.717。数值与 URL 均经 WebFetch 逐字核实，未推断 DOI。
- **新增独立求解器** `_fdfd_ng_candidate`（`verification_adapters.py`）：标量亥姆霍兹 FDFD 本征模算 n_eff(λ)，**固定网格**中心差分得 n_g = n_eff − λ·dn_eff/dλ。结果 **1.959 vs 实测 1.892，|diff|=0.067（3.5%）≤ tol 0.10** —— **LDA 首道「实测 ↔ 独立求解」真交叉验证**。
- **E1 保留 B 级并如实标注**（杜先生拍板）：标量 FDFD 对高对比度 SOI（3.48/1.44）**不达标**——算 3.71~3.78 vs 参考 4.19，差约 10%，且 n_eff 网格未收敛（f=24→48：2.585→2.542）。note 写明需**全矢量模式求解器**方可升 A 级。

**同批量化的求解器能力边界（真实数值实验，非推测）**

| 波导 | 对比度 | FDFD 算 n_g | 实测/参考 | 偏差 | 结论 |
|---|---|---|---|---|---|
| SiN 1000×300nm | 2.0/1.44（低） | 1.950 | 1.892（实测 TE） | 3.1% | ✅ 可用 |
| SOI 500×220nm | 3.48/1.44（高） | 3.71–3.78 | ~4.19（参考） | ~10% | ❌ 需全矢量 |

补 Sellmeier 材料色散（Lipson Si₃N₄ / Tan SiO₂）后 SiN 反而更远（1.950→1.990）→ 误差主因是**标量近似不辨 TE/TM**（实测 TE 1.892 / TM 1.717，标量解偏高），不是色散缺失。

**实验铁律（本轮踩坑）**：求数值导数时**网格 dl 必须由中心波长固定**。初版把 `dl = λ/f` 写在 `neff(λ)` 内部，网格随扫描波长变化 → 差分测到的是网格伪变化而非物理色散，n_g 乱跳 5.93 / 1.85 / 1.61。提到外层由中心波长定 dl 后：f=24→48 仅差 0.008、δ=20/10nm 完全一致。

**CI 加固（宁可红不可假绿）**：`run_empirical_anchor_smoke` 新增 2 条 D-64 断言（23→25）——①E2 candidate 必须**非** golden 自证且落在容差内；②其余 6 道**必须**仍是自证桩（一旦有人偷偷接了求解器而断言没改，会立刻变红，防止再次失真）。`run_empirical_d62_report` 同步 A 级 5 道→6 道（第三次同类「断言写死过期」教训）。

**底数变化**：语料 29→**30 条**，A 级 24→**25（83.3%，达标线 80%）**，**可溯源实证锚题 5/7 → 6/7**；CI core 维持 **83 条**（仅加断言，未新增 smoke 文件）。

### D-65（同批实测发现）：FDFD 候选的网格收敛缺口 —— E2 只判「量级一致」

打通 E2 后做稳健性检查，发现这个 PASS **不能按字面读**：同一器件**只改计算窗口**，n_g 就在 1.878~1.962 间散射。

```
SiN 1000×300（E2 器件）        SOI 500×220        SiN 800×800（对照）
clad  n_eff    n_g             n_eff    n_g       n_eff    n_g
1.5   1.5637   1.8777          2.5384   3.7924    1.7642   2.0829
2.0   1.5699   1.8818          2.7385   3.8192    1.7884   2.0843
2.5   1.6197   1.9621          2.7843   3.8000    1.7884   2.0843
3.0   1.6129   1.9587          2.5852   3.7761    1.7642   2.0829
4.0   1.5699   1.8817          2.7385   3.8192    1.7884   2.0843
散射  ±0.028   ±0.042          ±0.123   ±0.022    ±0.012   ±0.0008
```

**根因=网格过粗，不是 σ 也不是物理**：0.3µm 芯厚在 dl=λ/24=64.6nm 下只有约 **4.6 格**，阶梯边界随窗口尺寸改变对齐位置 → 离散化误差跳变。对照组（厚 SiN 800×800，约 12 格分辨）**完全收敛**，n_g 散射仅 0.0015 —— 反证了「是分辨率问题，不是求解器逻辑问题」。

排查过程两次推翻自己的假设，如实记录：
- ❌ 假设一「σ 硬编码 2.3 导致取错模态」：`oracle_mode.py` 的 shift-invert 目标确实被写死为 n=2.3（与其上方注释「σ 由 EIM 估计给出」不符，且对低对比度 SiN 而言 σ 落在整个导模谱**之外**）。修成按 EIM 估计取值后——**结果逐位不变**（实测 4 个构型全部相同），σ 不是主因。该 latent bug 仍修（代码与注释对齐、消除低对比度结构隐患），但不宣称它解决了问题。
- ❌ 假设二「矢量 FDTD 能闭合标量近似的缺口」：仓库已有真 3D 全 Yee 矢量本征模求解器（`lda_solver/fdtd3d_waveguide_vec.py`，此前只与标量 ORACLE 自校、**从未对实测验证过**）。实测：单次 **305 秒**（太慢），且 n_eff(λ) **非单调**（1.53→1.5566、1.55→1.6298、1.57→1.3684），相位法精度不足 → n_g 得 8.76（荒谬值）。**矢量 FDTD 当前不可用于 n_g 判定**。

**处置（宁可难看，不可假绿）**：
- E2 的 note 改为如实写法——「当前只能判定**量级一致 + 判决路径真实**，不能宣称**精度验证**；0.10 容差中约 ±0.08 是数值不确定度而非物理裕度」。
- 新增 **D-65 窗口鲁棒性断言**（smoke 25→27）：5 个计算窗口的 n_g **全部**必须落在容差内（实测最大 |diff|=0.0701 < 0.10）——证明 PASS 不是挑了个好窗口凑出来的；同时对散射设上界 0.12 护栏，防网格实现退化。
- 登记 **R16**（FDFD 网格收敛缺口），根治方向=**亚网格 ε 平均**（sub-cell averaging）+ 更细网格。

### 对外验货面同步整改（把 D-64 的诚实披露延伸到报告与 API）

- **`run_harness.py` 报告**：此前默认走 `ReferenceCandidate`（候选≡黄金），报告顶部赫然写着「## 汇总：48/48 通过」却只有一行 `candidate：ReferenceCandidate` 说明——外部读者极易误读为「48 项已验证」。现加醒目警告段 + 汇总行改「48/48 通过（自证闭环，**非验证结论**）」，JSON 增 `summary.self_consistent=true / summary.verified=0` 供机器判定。
- **CI 断言防丢失**（v0.8.55 教训：改了东西没同步 smoke，主干红而宣称全绿）：`run_harness.py` 末尾新增断言——自证模式下报告必须含警告文本、JSON `verified` 必须为 0；独立候选（`--perturb`）模式下 `self_consistent` 必须为 False。警告一旦被弄丢，CI 立刻红。
- **`/api/verify`**（WebUI）：`meta` 增 `self_consistent` 字段，自证时附 `warning` 说明。
- **`/api/verification_ledger`**（无鉴权对外验货端点）：①`ci_core` 由写死 82 改为动态读 `CORE_SMOKES` 长度（此前实际已 83，对外端点与 README 账本不一致，同一类漂移第二次）②新增 `judgment_paths` 字段，明示「7 道实证锚中仅 E2 有独立候选、其余 6 道为占位自证」及「harness CLI 默认模式为自证闭环」③`open_gaps` 登记 **R15**（判决路径独立性缺口）与 **R16**（FDFD 网格收敛缺口）。

## v0.9.8（2026-09-01 · 实证锚来源边界与溯源审计 · D-63）

确立**实证语料来源边界**：仅限 ①公开论文 ②公开 datasheet ③公开测量数据集，且**必须可公开溯源**。新增 `lda_harness/provenance.py` 做**机器可判**的三级分级——A 级（citation 含 DOI / arXiv / 公开 URL 定位符，第三方可独立复验，可作 golden 进判决）、B 级（仅有描述性来源无定位符，**禁止作 golden**）、X 级（无来源，拒收）；内网/私有地址段 URL 不算公开。门禁落三处：新语料准入（`submit_measurement` 非 A 级一律 rejected）、golden 取值（`EmpiricalAnchor.resolve` 默认 `require_traceable=True`）、判决路径（`harness.py` / `verification_adapters.py` 按锚题类型传参，A 级强制溯源、B 级显式放行但标注且不计入可溯源计数）。新增独立审计器 `run_provenance_audit.py`（已入 CORE_SMOKES，82→83）。

审计结果：语料 23→**29 条**，A 级 18→**24 条（82.8%）**；补 6 条 A 级真实实测语料（Sridaran & Bhave, Opt. Express 18(4) 3850–3857 (2010)，URL 定位符）：FSR 10.44/11.15 nm、cut-back 损耗 3.88/5.06 dB/cm、Q 46,500/148,000。

**审计暴露两个重大问题并整改**：①E3 原 golden 9.15 nm 实为解析式 λ²/(n_g·2πR) 闭式反算（且 n_g=4.18 源自 2D FDTD 仿真），属「定律/仿真冒充实测」——已换成**实测 10.44 nm**，并形成实测↔解析交叉验证（10.44 vs 10.464，差 0.024 nm）；②n_eff 在工程上是导出量（多为仿真或反演，少有直接测量），E1/E2 缺公开可溯源实测源，已改标 `empirical_unverified`（B 级，仍走死标量判决但不计入可溯源计数），建议后续改为可实测的群折射率 n_g 锚。**可溯源实证锚题：5/7**。详见 `docs/lda_empirical_source_boundary_2026-09-01.md`。

### 发版回归（core 83 条）抓出并根治的三类连带问题

- **① 门禁漏改（第三次同类教训）**：`resolve_specs()` 两处把 B 级锚题的 spec `anchor` 硬写回 `"empirical"`，使 `run()` 中 `require_traceable=(anchor=="empirical")` 恒为真 → E1/E2 golden 被判 None → verify_design 掉到 46/48（mcp、l1_agent 两条 smoke 红）。**根因在赋值点而非比较点**——此前只 grep 了 `== "empirical"`（比较），漏了 `"anchor": "empirical"`（赋值）。已改为透传 `anchor` 原值，两条 smoke 回到 48/48。
- **② 展示路径未适配 None**：`benchmark_report.run_crosscheck` 对 B 级语料仍走默认强制溯源 → `val=None` → `mval - None` TypeError（crosscheck 报告、飞轮 smoke 红）。已改为覆盖率展示显式 `require_traceable=False` 取值并标 `traceable` 字段（该报告是展示不是判决）；同时**修掉一句失真宣称**：`honest_note` 原写「9 条全部 DOI 可溯源」与事实不符，改为按 `provenance.audit_items` **实时统计** A 级条数，杜绝写死。
- **③ 冒烟脚本自带语料被新门禁挡下**（同类第二次）：`run_tapeout_smoke` 的 citation 无定位符被拒、`run_d06_smoke` 断言 `src=="empirical-measurement"` 与 B 级现状冲突。已分别改为「补公开 URL（SkyWater SKY130 公开 PDK）+ 追加反向断言（无定位符必须 rejected）」与「默认门禁返回 `empirical-untraceable`、显式放行返回 `empirical-B-untraceable`」——把新门禁本身也钉进 smoke。
- **额外根治：CI 回归 SKIP 判定过宽（假绿温床）**。旧规则「输出含『未安装』等字样即记 SKIP」，会把真失败误记 SKIP——本次 3 条（d06 / cli / ci_industrial）均为用例失败被洗白，其中 cli 仅因某条 PASS 行里提到「gdsfactory 未安装」就被记 SKIP。已收紧为两级：①行首 `[SKIP]`/`SKIPPED` 显式标记 → 无条件 SKIP；②环境缺失短语 → **仅当输出中无 Traceback / AssertionError / FAIL 行**时才记 SKIP，否则一律 FAIL。宁可红，不可假绿（对齐 v0.8.55「宣称全绿必须有实跑证据」教训，且实证锚 smoke 已覆盖 5 类判定用例）。

## v0.9.7（2026-09-01 · 生产安全加固 · POST 重计算端点登录闸门）

复盘：在 v0.9.6 四重并发护栏（每端点锁+全局上限+缓存+入参上限）基础上，于 `_heavy_guard` 统一入口追加**登录闸门**——把「无鉴权重计算」敞口从「被并发数封顶」升级为「须登录才能触发」。验证优先 `store.user_by_token(token)`（store 会话态），回退 `_check_admin(headers)`（管理员 / 外部 ORACLE 验货用 Bearer）；未登录直接 401 且不占缓存/并发资源。GET 验货端点（cpo_array / verification_ledger）仍无鉴权，维持「可被外部验货」战略可达性。影响面排查：现有 CI smoke（`run_adjoint_design_smoke` 等）直接 import 库函数不走 WebUI HTTP、无 `run_*smoke` 经 HTTP POST 调这些端点、`run_api_v1_smoke` 走独立 `/api/v1/*`，故加闸门不会让 CI 失同步（规避 v0.8.55 教训）；前端 insights.html 仅拉 GET 不受影响。

## v0.9.6（2026-09-01 · 生产安全加固 · POST 重计算端点统一并发护栏）

复盘：经排查，WebUI 的仿真/设计类 POST 端点（`/api/ring_fdtd`、`/api/sparams`、`/api/sparams_3d`、`/api/gc_sparams`、`/api/adjoint_design`、`/api/quantum_design`、`/api/wdm_design`、`/api/pdk_design`、`/api/pdk_compare` 等 50 个 `run_*` 端点）**同样无鉴权、直接触发重计算**，与之前打爆服务器的 GET 端点同源——且 `app.py` 的 `_dispatch` 无统一鉴权闸门。纯「按端点逐个锁」只能锁单端点，攻击者同时打 50 个端点仍可达 50 路并行 → 同样打爆。本次采用「每端点锁（公平）+ 全局并发上限（总资源封顶）」双锁设计：

- **① 每端点独立串行锁**：每端点任意时刻至多一个重计算在跑，并发 429「重计算忙，请 1-2 秒后重试」，避免跨端点队头阻塞。
- **② 全局并发上限**：`threading.Semaphore(min(cpu_count, 4))`，总重计算并发封顶，彻底封死「同时打所有端点」的总并发敞口（纯按端点锁做不到）。
- **③ 参数哈希缓存**：TTL 120s、限容 32 条，重复相同请求秒回，防内存膨胀。
- **④ 入参体积硬上限**：单请求体 256KB，超则 413，防超大 payload OOM。

护栏经 `_dispatch` 在 POST 精确路由层接入，仅对 `HEAVY_POST_PATHS`（50 个重计算端点）生效；鉴权/商店/生态/opinion/verify 等轻端点与有副作用端点不进护栏，行为不变。本次**未加登录鉴权**（用户决策：先只做并发护栏，鉴权作独立议题）。

验证（本地冒烟）：50 端点入表、轻端点不入表；单次 200；同参缓存命中秒回；并发 6 路同端点 `max_overlap=1`（每端点锁完全串行化，无并行堆叠）。`py_compile` 两文件通过。

## v0.9.5（2026-08-31 · 生产安全加固 · 验货端点并发护栏补全）

复盘：`GET /api/benchmark_crosscheck` 是 v0.9.3 同期存在的无鉴权公开 GET 端点，默认实跑 `run_crosscheck(quick=True)`（本地实测 9.2s），同样运行在 `ThreadingHTTPServer`（每请求一线程）下、与 `cpo_array` 同类——一旦被并发请求打中会把生产服务器并行打爆。本次补齐同款三护栏：全局串行锁（任意时刻至多一个 crosscheck 在跑，并发 429）+ 结果缓存（TTL 120s，重复 curl 秒回）。至此所有「公开 GET + 默认实跑重计算」端点（cpo_array、benchmark_crosscheck）均带护栏；verification_ledger / scale_demo / capability_demos(默认) / status / health 等均为轻量只读或需显式 `?run=1`，不在敞口之列。

## v0.9.4（2026-08-31 · 生产安全加固 · CPO 验货端点并发护栏）

复盘：v0.9.2 部署的 `GET /api/cpo_array`（无鉴权、默认实跑十万级器件，build+DRC+LVS ~数秒~数十秒）运行在 `ThreadingHTTPServer`（每请求一线程）下，一旦被并发请求（外部扫描 / 监控轮询 / 反复自测）打中，多个重计算会并行吃满 CPU/内存，存在把生产服务器打爆的风险。本次加固：

- **① 输入硬上限**：`oe<=48, ch<=96, lane<=16`，超出即 400，防止单请求 scale 到 OOM。
- **② 全局串行锁**：任意时刻至多一个重计算在跑（`threading.Lock` + 1s 超时），其余并发请求 429「重计算忙，请 1-2 秒后重试」，杜绝并行堆叠。
- **③ 默认配置结果缓存**：TTL 120s，重复 curl 同配置秒回，不再重算。

验证（本地）：默认 100,096 器件 ACCEPT（4.19s）· 二次命中缓存 0.000s · 超限 400 · 冷缓存并发 3 线程 → 1 个 3.99s 实算 200、其余 2 个 1.05s 内 429（锁串行，无并行堆叠）。

## v0.9.3（2026-08-31 · 验证可信度外部验货 · 全量验证账本端点）

战略审计 #1 缺口「可被外部验货的验证可信度」从单点（CPO 规模死锚）扩展到整引擎：

- **新增 `GET /api/verification_ledger`（无鉴权、可 curl 验货）**：暴露全部已注册验证资产的**分类与计数**——`physical-law` 确定性物理定律锚（B1–B28 / S1–S13，38 道，任何人都可独立复算）+ `oracle-or-design-anchor` ORACLE 依赖锚（B5/B6/B7，3 道，meep/tidy3d 缺失时回退 numpy 离线近似或设计守则下限）+ `empirical` 实证大数据锚（E1–E7，7 道，真实器件实测语料）；合计 **48 题**；旁挂 `CI core 82 条` 与 `CPO 规模死锚`（默认 100,096 / 规模 250,240 ACCEPT）。
- **诚实分类（verified_by）**：明确标注每类事实来源与开放缺口——R2 外部 ORACLE 默认不通（物理定律锚无法现场交叉验证）、R3 实证锚仅 7 条种子语料、R4 B5/B6/B7 为 ORACLE 依赖（根因=R2）。LLM 不进判决路径，PASS/FAIL 一律由死标量比对。
- 端点纯内省、无重计算，纳入 WebUI 路由层冒烟（GET_ROUTES 静态校验）。

## v0.9.2（2026-08-31 · 阶段2 · CPO 共封装光引擎阵列：十万级真实器件样例）

把 v0.8.45（LVS 短路检测 O(n²) 治理）与 v0.8.46（GDS 导出 O(n²) 治理）打通的十万器件级全链能力，落到**真实器件样例**上——不再是「N 个 Waveguide 串成一条链」，而是层次化的**共封装光学（CPO）光子引擎阵列**。

- **新增 `lda/lda_harness/cpo_array.py`**：CPO 阵列生成器，层次为
  阵列（n_oe 光引擎）→ 光引擎（n_ch 波长通道）→ 通道（n_lane 条波长 lane）。
  - 器件构成真实：微环调制器 MRM（`RingAddDrop`）/ WDM add-drop 解复用环 /
    功率监测·波长锁定抽头（`RingResonator`）/ 光栅耦合器（`GratingCoupler`）
    / 互连波导段（`Waveguide`）——每通道 92 器件 = Tx 链 58 + Rx 链 34。
  - **参数由物理反解，非拟合常数**：微环半径 `R = m·λ/(2π·n_eff)`
    （m=91 **整数**谐振级数、n_eff=2.45 → 7.530–7.713 µm，LAN-WDM 8 波）；
    光栅周期 `Λ = λ_c/(n_eff,gr − sin θ) = 0.612 µm`（θ=15°，齿宽 0.367 /
    齿隙 0.245 µm 同时满足 DRC 线宽与间距双约束）。
  - **几何策略：端口线对齐 + 零跳线**——放置按「入端口（链首用出端口）」
    做 y 补偿，使同行全部连接端口落在同一条水平线上；pitch_x 取
    `max(2·max_hw + margin, max(out_dx) − min(in_dx) + 6)` 保证连线不回折；
    通道宽度整除行宽使通道不跨行。于是全部布线为同层 M1 水平段，
    **同层短路数 = 0 由几何保证，而非靠 LVS 兜底**。
- **新增 `lda/run_cpo_array_demo.py`**：全链闭环演示（构建→放置→布线→
  GDS→DRC→LVS→正/反例→报告）。默认配置 32 引擎 × 34 通道 × 8 波长实测：
  - **100,096 器件 / 2,176 条独立光路 / 97,920 布线网 + 4,352 外部 IO**
  - DRC **100,096/100,096** 全过
  - LVS **ACCEPT**（0 违规 · 97,920/97,920 网表全匹配）
  - 反例（注入断路）→ **REJECT**（证明判决非「永远 ACCEPT」）
  - GDS **38.98 MB / 359,040 元素**（4.02s，round-trip 可解析）
  - 芯片 **13.14 × 7.89 mm = 103.67 mm²**（≈1.04 cm²，真实 CPO 中介层量级）
  - 全链 **8.34s**
- **新增 `lda/run_cpo_array_smoke.py`**：21 条断言入 CI core（**80→81**），
  含层次推导死标量、端口线对齐零回折、**独立重算** R = m·λ/(2π·n_eff) 逐项
  比对、光栅布拉格条件、DRC/LVS 正反例、GDS round-trip、十万配置推导、
  配置护栏（ch_per_row 不整除则拒绝）、源码零 LLM 红线。
- **诚实边界（不可省略）**：仅建模**无源光子层**，有源器件（激光器/探测器/
  驱动 IC/TIA）按黑箱处理（负面清单）；工艺为公开文献近似非真实 foundry
  PDK；本样例只做**版图闭环**，未做光学仿真验证（插损/串扰/FSR 属另一条
  链路）；未流片、无实测回流。

## v0.8.56（2026-08-29 · 创新超市商业闭环：会员 + 统一订单 + 自动交付）
- **商业闭环核心**：新增 `lda/lda_webui/store.py`（零依赖，数据落盘 `dist/store.json` gitignored）——会员注册/登录（PBKDF2 + 会话令牌）、统一订单状态机（created→paid_unverified→approved→rejected）、微信个人收款（收款码+凭证）、管理员「确认收款并自动发货」（复用 `ship_package` 生成一次性兑换码）。
- **双通道**：个人用户（微信个人收款凭证）+ 企业客户（对公转账）共用同一套订单流；下单自动带单价（¥1999 默认，可按货架覆盖）。
- **路由接入**：`lda/lda_webui/app.py` 新增 `/api/store/*`（register/login/me/order/orders/mine/config）与 `/api/admin/*`（orders/config/order/<id>/approve|reject）；新增 `_bearer()` 统一去 Bearer 前缀；管理员鉴权统一认可 `LDA_ADMIN_TOKEN` 环境变量（修复 list_orders 仅认 store 用户、下载路由 `parts[4]/count==5` 解析错位两处 bug）。
- **前端**：`lda/lda_webui/static/store.html`（会员登录/注册、货架下单、上传支付凭证、自助下载）、`admin.html`（订单审核、一键发货、微信收款码配置）；静态白名单放行进 `store.html`。
- 端到端验证通过：注册→下单→凭证→管理员审批（自动生成兑换码）→会员自助下载 zip；个人/企业两通道均跑通。
- **Track 0 计费身份中枢**：注册新增三档身份（standard 标准个人 / academic 学术个人 / institution 机构席位，机构必填单位名称）；`tier_discount` 折扣引擎（1.0 / 0.6 / 0.85，管理员可经 `config.tiers` 覆盖）；`price_of(shelf_id, user_type)` 按身份计价；订单记录 `tier` 字段；`/api/shelf` 按登录身份返回 `price_cny/base_price/price_tier`；前端注册弹窗三身份选择 + 货架实付价 + 下单金额 + 会员中心/导航身份徽标；老账号无 user_type 字段安全回退 standard。生产 e2e 16/16 通过（三身份价格 1999 / 1199.4 / 1699.15 联动验证）。

## v0.8.55（2026-08-29 · 管理后台上线打通商务闭环 + 生产部署真实账户）
- **管理后台**：新增 `lda/lda_webui/static/admin.html`——令牌登录（localStorage）、待处理申请列表（公司/联系人/电话/邮箱/货架/备注/时间）、一键审批并生成一次性兑换码、兑换码复制 + 下载链接；静态页白名单放行进 `admin.html`。
- **文案修正**：`/api/purchase/request` 响应去掉"邮件发送兑换码"空头承诺，改为"到账后管理员生成兑换码、凭码下载"准确表述（手动发码阶段）。
- **生产部署**：`115.191.20.92` 部署真实对公收款账户（上海农商银行陈行支行 32434508010036375）+ 联系人（杜先生 13636690529/13311602075、范女士 13901700712）+ 联系电话；管理员弱令牌通过 `LDA_ADMIN_TOKEN` 环境变量替换为强令牌加固。
- 货架/开放数维持 58/50；量子 8 维持咨询制；CI core 维持 69 条。

## v0.8.54（2026-08-29 · 对公收款程序适配：创新超市接对公购买申请闭环）
- **对公收款适配**：营业执照确认上海杜特企业管理咨询有限公司为有限责任公司（自然人投资或控股），B2B 设计包交付采用直接对公转账 + 兑换码交付。
- **前端**：`lda/lda_webui/static/insights.html` 增加顶部「对公收款说明」弹窗、货架卡片「对公购买」按钮；弹窗收集公司/联系人/电话/邮箱/付款备注。
- **后端**：`lda/lda_webui/app.py` 新增 `POST /api/purchase/request`、`GET /api/admin/purchase_requests`、`POST /api/admin/purchase/{id}/approve`；申请持久化到 `dist/purchase_requests.json`（gitignored）；审批通过调用 `ship_package.mint_license` 生成绑定货架的兑换码。
- **管理**：管理员端点通过 `Authorization: Bearer <LDA_ADMIN_TOKEN>` 鉴权，默认令牌为弱默认值并提示通过环境变量 `LDA_ADMIN_TOKEN` 替换。

## v0.8.53（2026-08-29 · 持续扩货架：新增 5 光子缺口品类开放下载、货架 53→58）
- 货架 53→58：新增 5 个真实 2026 市场缺口光子品类（信号源可溯源、composition⊆GP-*、非出口管制、honest_tier=前瞻预研）：
  - `IM-AWG-DEMUX`（阵列波导光栅解复用器 AWG DeMUX；AWG MUX/DeMUX $735M(2025)→$1.375B(2031) CAGR 8.14%、Arrayed Waveguide Market $320-570M(2026) CAGR 6.5-11.7%、AI 数据中心 DWDM/CPO 推升）
  - `IM-ONCHIP-SPECTROMETER`（片上微型光谱仪；Chip-scale Spectrometer $2.44B(2025)→$8.7B(2033) CAGR 17.2%、Miniature Spectrometer IC $1.36B(2025)→$3.99B(2034) CAGR 12.7%）
  - `IM-MDM-MUX`（模分复用器 MDM；MDM Equipment $1.42B(2024)→$4.16B(2033) CAGR 12.6%、Few-Mode Fibers $10.74B(2025) CAGR 6.86%、突破单模 Shannon 极限）
  - `IM-OPTCOMB`（芯片级光频梳 Microcomb；全球光频梳 $1.87B(2026) 年增 31.7%、Intel $58M(2025)→$108M(2034) CAGR 7.4%、芯片级微梳 CAGR 47.8%）
  - `IM-POL-ROTATOR`（片上偏振旋转器；光偏振控制器 $4.72B(2026) 增 12.9%、Polarization Rotator CAGR 10.3%(2026-2033)、集成波导型增速 28%）
- 开放下载白名单 `OPEN_SHELVES` 45→50（前述 5 个光子缺口品类全量放开；工厂产能已具备，任意已知货架可现场生成设计就绪包）。
- 量子 8 个维持「咨询制」，不进自动下载白名单（出口管制合规红线）。
- `docs/store_launch/04_market_analysis.md` 新增趋势段：AWG 解复用（DWDM/CPO $1.375B 2031）、片上光谱仪（Chip-scale $8.7B 2033）、模分复用（MDM $4.16B 2033）、芯片级光频梳（微梳 CAGR 47.8%）、偏振旋转器（集成波导型增速 28%）；光子细分表格扩容，开放策略 45→50 货架。
- 沿用 `OPEN_SHELVES ⊆ DEFAULT_SHELF` 回归护栏；重新生成 `innovation_market.json`（58 货架）；货架 smoke **58/58 ALL PASS**；`run_count_consistency_smoke` **11/11 OK**（CI core 维持 69 条）。

## v0.8.52（2026-08-28 · 持续扩货架：新增 5 光子缺口品类开放下载、货架 48→53）
- 货架 48→53：新增 5 个真实 2026 市场缺口光子品类（信号源可溯源、composition⊆GP-*、非出口管制、honest_tier=前瞻预研）：
  - `IM-MRR-FILTER`（微环谐振滤波器/可重构光滤波 add-drop；Silicon Microring Resonators $450M→$1.66B CAGR 20.5%、Microring Filter Array $41.58M→$245M CAGR 27.8%、add-drop 占 55.5%）
  - `IM-SPLITTER-TREE`（1×N 功分树/PLC 功分网络；PLC Splitter $2.8B→$5.6B CAGR 8.1%、1×N 占 62.4%、FTTR/XGS-PON 推升 1×32+）
  - `IM-TRUE-TIME-DELAY`（微波光子真延时 TTD 波束成形；Phased Array Antenna $3.90B→$8.38B CAGR 10.04%、相控阵系统 $18.7B→$38.5B CAGR 12.8%、MWP 真延时用于相控阵雷达）
  - `IM-GAS-SENSE`（波导气体/吸收光谱传感 SiN 宽波段；SiN PIC $320M→$1113.58M CAGR 19.5%、VOC 中红外检测灵敏度较 Si 提升 5×）
