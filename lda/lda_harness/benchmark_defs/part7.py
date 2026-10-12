# -*- coding: utf-8 -*-
"""BENCHMARK_DEFS 分片 7/7（QS 量子传感器芯片征程 · v0.9.221）。

覆盖 key：B473（QS-M0 衍生：NV 色心磁力计磁灵敏度）
          B474（QS-M1 衍生：灵敏度 FOM 体系 —— 线宽 FOM 路径）
          B475（QS-M2 衍生：自旋回波相位方差 —— 退相干/DD 相干时间建模）
          B476（QS-M3 衍生：最优色心深度 —— 几何优化）
          B477（QS-M3 衍生：NA 立体角收集效率 —— 几何优化）
          B478（QS-M4 衍生：磁偶极近场串扰系数 —— 阵列化）
          B479（QS-M4 衍生：串扰恶化灵敏度倍率 —— 阵列化）
          B480（QS-M4 衍生：梯度计共模抑制比 CMRR —— 阵列化）
          B481（QS-M4 衍生：梯度计差模灵敏度 η_grad —— 阵列化）
          B482（QS-M5 衍生：微波频锁鉴别器中心斜率 —— 闭环标定）
          B483（QS-M5 衍生：磁场标度因子自标定 —— 闭环标定）
          B484（QS-M5 衍生：AC 灵敏度带宽折算 η_AC —— 动态范围/读出）
          B485（QS-M6 衍生：SQUID 环路临界电流磁通调制 I_c(Φ) —— 超导磁力计）
          B486（QS-M6 衍生：磁通-电压转导 ∂I_c/∂Φ —— 超导磁力计）
          B487（QS-M6 衍生：磁场灵敏度谱密度 B_N —— 超导磁力计）
          B488（QS-M7 衍生：磁通聚焦变压器有效面积 A_eff —— SQUID 噪声优化）
          B489（QS-M7 衍生：亚微米结噪声约束磁通噪声谱密度 S_Φ,opt —— SQUID 噪声优化）
          B490（QS-M7 衍生：优化后磁场灵敏度 B_N,opt —— SQUID 噪声优化）
          B491（QS-M9 衍生：自由进动横向极化 P_x(t*) —— OPM/SERF 腿 C 时域信号）
          B492（QS-M9 衍生：碱金属饱和蒸气数密度 n(T) —— OPM 气室温度定标）
          B493（QS-M9 衍生：泵浦光 Beer–Lambert 透过率 T(L) —— OPM 气室光路）。
分类（诚实）：**B473 = 严格独立**（`candidate` 指向 `_batch_b39_numeric` 注册的
  数值误差传播链候选；实测 rel≈2.4e-5，非代数恒等）。
  **B478–B481 = 严格独立**（`candidate` 指向 `_batch_b43_numeric` 注册的
  点偶极场数值积分 / MC 噪声功率叠加 / 含噪样本 LSQ 斜率比 / MC 两点差分标准差
  候选；实测 rel 4.7e-9 / 1.9e-6 / 4.2e-5 / 1.0e-4，**均 ≫ 机器精度，非代数恒等**）。
  **B482–B484 = 严格独立**（`candidate` 指向 `_batch_b44_numeric` 注册的
  FID 数值线型中心差分斜率 / 全跨多点 LSQ 标度 / MC 带限噪声 rms 候选；
  实测 rel 6.7e-6 / 3.4e-8 / 2.1e-4，**均 ≫ 机器精度，非代数恒等**）。
  **B485–B487 = 严格独立**（`candidate` 指向 `_batch_b45_numeric` 注册的
  相位空间扫描 / 数值中心差分 / MC Johnson 噪声传播候选；
  实测 rel 4.6e-11 / 2.9e-11 / 8.1e-4(跨20种子最坏)，**均 ≫ 机器精度，非代数恒等**）。

🔴 本片初版曾拟三道锚，逐条实测**如实砍到一锚**（三锚均为代数恒等/机器精度，
会被 `run_benchmark_falsifiability_smoke` 判自证桩）——详见 `_batch_b39_numeric.py`
模块头「为何只一锚」。宁可少一锚，不越级谎报（同 PS-M8 B472 诚实降级纪律）。

🔴 增锚必同登两处契约：`BENCHMARK_DEFS`（本片）+ `benchmarks.py::BENCHMARK_ORDER`。
🔴 三分类自动跟随：有 `candidate` 键（且函数在 `BENCHMARK_CANDIDATES` 登记）⇒
   `_vmm_classify` 自动判 `strict_independent`。四处硬编码数字陈述（README 当前账本 +
   验证三分类、CONTRIBUTING 顶块、`run_webui_verification_ledger_smoke.py` docstring）
   须手动同步。
🔴 scipy 隔离：本片仅 `from .._batch_b39_numeric import ...` 顶层别名（模块顶层
   scipy-free）；golden 函数体纯 numpy（无 scipy 依赖）。
🔴 **锚携带可扰动参数**（v0.9.216）：`default_params` = 物理设计量（T2*/n_ph/C/a），
   使反自证桩护栏的**行为判据**能真扰动（初版空 params 致 η 绝对残差 2e-14 < 1e-12
   时被误判自证桩；带参后 `candidate_responds=True` ⇒ 正确判严格独立）。
"""
from .._batch_b39_numeric import (  # Batch B-39 量子传感器芯片征程 QS-M0 衍生（NV 色心磁力计磁灵敏度）
    golden_b473,
    B473_DEFAULT_PARAMS,
)
from .._batch_b40_numeric import (  # Batch B-40 量子传感器芯片征程 QS-M1 衍生（灵敏度 FOM 体系 · 线宽路径）
    golden_b474,
    B474_DEFAULT_PARAMS,
)
from .._batch_b41_numeric import (  # Batch B-41 量子传感器芯片征程 QS-M2 衍生（自旋回波相位方差 · 退相干/DD）
    golden_b475,
    B475_DEFAULT_PARAMS,
)
from .._batch_b42_numeric import (  # Batch B-42 量子传感器芯片征程 QS-M3 衍生（灵敏度几何优化 · 最优深度 + NA 收集效率）
    golden_b476,
    B476_DEFAULT_PARAMS,
    golden_b477,
    B477_DEFAULT_PARAMS,
)
from .._batch_b43_numeric import (  # Batch B-43 量子传感器芯片征程 QS-M4 衍生（阵列化 · 串扰 + 梯度计）
    golden_b478,
    B478_DEFAULT_PARAMS,
    golden_b479,
    B479_DEFAULT_PARAMS,
    golden_b480,
    B480_DEFAULT_PARAMS,
    golden_b481,
    B481_DEFAULT_PARAMS,
)
from .._batch_b44_numeric import (  # Batch B-44 量子传感器芯片征程 QS-M5 衍生（闭环标定 · 频锁 + 标度自标定 + AC 带宽）
    golden_b482,
    B482_DEFAULT_PARAMS,
    golden_b483,
    B483_DEFAULT_PARAMS,
    golden_b484,
    B484_DEFAULT_PARAMS,
)
from .._batch_b45_numeric import (  # Batch B-45 量子传感器芯片征程 QS-M6 衍生（超导 SQUID 磁力计 · I_c(Φ) + 转导 + B_N）
    golden_b485,
    B485_DEFAULT_PARAMS,
    golden_b486,
    B486_DEFAULT_PARAMS,
    golden_b487,
    B487_DEFAULT_PARAMS,
)
from .._batch_b46_numeric import (  # Batch B-46 量子传感器芯片征程 QS-M7 衍生（SQUID 性能冲刺 · 磁通聚焦变压器 + 亚微米结噪声优化）
    golden_b488,
    B488_DEFAULT_PARAMS,
    golden_b489,
    B489_DEFAULT_PARAMS,
    golden_b490,
    B490_DEFAULT_PARAMS,
)
from .._batch_b47_numeric import (  # Batch B-47 量子传感器芯片征程 QS-M9 衍生（光泵原子磁力计 OPM/SERF · 自由进动横向极化 + 碱金属数密度 + 光路吸收）
    golden_b491,
    B491_DEFAULT_PARAMS,
    golden_b492,
    B492_DEFAULT_PARAMS,
    golden_b493,
    B493_DEFAULT_PARAMS,
)
from .._batch_qs_m3c_numeric import (  # Batch B-48 量子传感器芯片征程 QS-M3c 衍生（腔 QED 物理链 · 腔品质因子 Q / 有效模体积 V_eff / 单光子耦合 g）
    golden_b494,
    B494_DEFAULT_PARAMS,
    golden_b495,
    B495_DEFAULT_PARAMS,
    golden_b496,
    B496_DEFAULT_PARAMS,
)
from .._batch_j1_numeric import (  # Batch J1 量子纠错征程 QEC · M0 阈值标度 + M1 解码器（G_Q9 主项）+ M2/M3/M4 续做（G_Q9 收官）：表面码阈值距离 d* / 解码器综合征概率场 / 解码器匹配代价二阶矩 / 旗比特钩错 / 相邻稳定子关联 / transversal CNOT 预算链 / lattice surgery 合并 / 端到端累计失效 / 累计逻辑错误面积
    golden_b497,
    B497_DEFAULT_PARAMS,
    golden_b498,
    B498_DEFAULT_PARAMS,
    golden_b499,
    B499_DEFAULT_PARAMS,
    golden_b500,
    B500_DEFAULT_PARAMS,
    golden_b501,
    B501_DEFAULT_PARAMS,
    golden_b502,
    B502_DEFAULT_PARAMS,
    golden_b503,
    B503_DEFAULT_PARAMS,
    golden_b504,
    B504_DEFAULT_PARAMS,
    golden_b505,
    B505_DEFAULT_PARAMS,
)
DEFS = {
    "B473": {
        "title": "NV 色心磁力计磁灵敏度谱密度 η（闭式散粒极限 golden vs 数值误差传播链候选 · T/√Hz）",
        "metric": "nv_magnetometer_sensitivity",
        "oracle": "closed_form(η=ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*)), Raman/散粒受限) + 数值误差传播链独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B473_DEFAULT_PARAMS),
        "golden_fn": golden_b473,
        "candidate": "b473_nv_eta_error_propagation_cand",
        "candidate_desc": "数值误差传播链：相位噪声率 ρ_φ=√(1+a²)/(C·√n_ph) → 最优时间 τ_opt=T2*/√2 → 磁场-相位斜率用双能级量子时间演化核（复指数）的数值中心差商求得 → 谱密度归一 η=√2·ρ_φ·τ_opt/(|dφ/dB|·√T2*)。方法学独立：golden=代数整理标量闭式，cand=复指数演化核 + 有限差分 + 逐步数值合成",
        "note": "golden = NV 色心 Ramsey 磁力计的光子散粒噪声极限灵敏度闭式：η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*))（T/√Hz）。物理：Ramsey 相位噪声率 ρ_φ=√(1+a²)/(C√n_ph)（rad/√s）；最优自由进动时间 τ_opt=T2*/√2（对比度包络 e^(−(τ/T2*)²) 斜率最大化点）；÷ 磁场-相位斜率 (gμB/ħ)τ_opt 归一到谱密度。candidate=数值误差传播链（演化核差商求斜率 + 逐步合成），方法学独立（golden=线性化代数闭式不重算，cand=复指数核数值差商）。实测默认档 |Δ|=2.058e-14、rel=2.431e-05（tol=1e-3 的 41.1× 余量）。🔴 **量纲血案（本锚吃狗粮抓到的真 bug）**：初版候选链误用「每循环光子数 N=n_ph·τ_opt」+ δB·√τ_opt 归一，与 golden 差 1000×（=1/√T2*）；根因=标准敏感度用**单位时间相位噪声率** ρ_φ=1/(C√n_ph) 而非 1/√N。🔴 **诚实规模（同源体检）**：`magnetomet|磁力计|NV|nitrogen.vacancy|金刚石|Ramsey|ODMR` 在 BENCHMARK_DEFS 内 **0 命中** ⇒ **量子传感器族零锚占用（本族首锚）**。初版另拟「Ramsey 相位积累」（rel~1.6e-16 机器精度）、「Zeeman 分裂含横向场」（rel~8.5e-12，横向耦合 γBx/D 二阶小量）、「Ramsey sinc² 条纹」（傅里叶定义恒等）三锚，**均为代数恒等 ⇒ 如实不登记**（若登记会被反自证桩护栏判自证桩），本片如实只留一锚。⚠️ **诚实边界**：T2*=1µs / C=0.03 / n_ph=1e5/s 为**设计示例**（室温 NV 集合体典型量级）；本锚只证明「闭式散粒极限 ⇄ 数值误差传播链」数值一致这一数学事实，结论只可用于数值方法与量级，**不得作制造/性能宣称**（真灵敏度受微波功率展宽、磁场不均匀、表象噪声等未建模因素降级，实际远差于本理想极限）。零商业依赖（纯 numpy + math）。",
    },
    "B474": {
        "title": "量子传感器灵敏度 FOM 体系（线宽 FOM 路径）：闭式散粒极限 golden vs 数值线宽提取链候选 · T/√Hz",
        "metric": "qs_sensitivity_fom_linewidth_path",
        "oracle": "closed_form(η=ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*))) + 数值线宽提取链独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B474_DEFAULT_PARAMS),
        "golden_fn": golden_b474,
        "candidate": "b474_qs_fom_linewidth_cand",
        "candidate_desc": "数值线宽提取链：从高斯对比度包络 C(τ)=e^(−(τ/T2*)²) 的时间域采样做**数值半高全宽（FWHM）提取** → 频域宽度 σ_f=FWHM_t 高斯对偶 → 反解等效 T2*'=√2/(2π·σ_f) → 合成 η=√(1+a²)·√2/(C·√(n_ph·T2*'))/(gμB/ħ)。方法学独立：golden=直接代数代入 T2*（T2* 路径），cand=不以 T2* 解析式代入，而经「时间包络→数值 FWHM→σ_f→T2*」逐步数值链（时间/频域 vs 相位域，与 B473 的相位域链物理域不同）",
        "note": "golden = 量子传感器灵敏度 FOM 体系（QS-M1）的**统一口径** η = δB·√T（白噪声幅度谱密度，T/√Hz；🔴 禁与线宽受限 LOD 混比）散粒极限闭式：η = ħ/(gμB)·√(1+a²)·√2/(C·√(n_ph·T2*))。FOM 三条独立可测量：对比度 C、频域线宽 σ_f、光子计数率 n_ph（T2* 由 σ_f 反解：T2*=√2/(2π·σ_f)）。candidate=**数值线宽提取链**（不从 T2* 解析式代入，而走 时间包络→数值 FWHM→σ_f→T2*'→η），方法学独立（golden=T2* 路径代数；cand=线宽路径数值提取）。实测默认档 |Δ|=2.344e-15、rel=2.769e-06（tol=1e-3 的 361× 余量；网格离散化引入，**非**机器精度）。🔴 **与 B473 不同物理量**：B473 candidate 走**相位域**（ρ_φ + 复指数演化核差商），B474 candidate 走**时间/频域**（对比度包络 FWHM 数值提取）——两者方法学互不重叠，非重复计数。🔴 **诚实规模**：初版另拟「口径自检 assert_caliber 反向探针」「四情景单调性」两项，二者均**非标量物理量**（守卫逻辑/不等式约束）⇒ 归 `run_qs_m1_smoke` 覆盖，**如实不登记为 B 锚**；本批只登记 B474 一锚（同 B472/B473 纪律）。⚠️ **诚实边界**：默认 T2*=1µs / C=0.03 / n_ph=1e5/s 为**设计示例**（室温 NV 集合体典型量级）；本锚只证明「T2* 路径闭式 ⇄ 线宽路径数值提取」数值一致这一数学事实，**不得作制造/性能宣称**（真灵敏度受微波功率展宽、磁场不均匀、表象噪声等未建模因素降级）。零商业依赖（纯 numpy + math）。",
    },
    "B475": {
        "title": "自旋回波（Hahn echo）相位方差（退相干/DD 相干时间建模）：闭式 golden vs 时间域数值积分候选 · 无量纲",
        "metric": "spin_echo_phase_variance",
        "oracle": "closed_form(⟨Φ²⟩_echo=2(1−cos(ωt/2))²，归一化丢 (γb/ω)²) + 时间域数值积分链独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B475_DEFAULT_PARAMS),
        "golden_fn": golden_b475,
        "candidate": "b475_echo_variance_time_integration_cand",
        "candidate_desc": "时间域数值积分链：时间网格 s∈[0,t] + 均匀初相 φ_k → 噪声波形 B(s;φ)=cos(ωs+φ)（ω=ωt/t）→ 在 t/2 处符号翻转（Hahn 回波 π 脉冲时序）→ 梯形积分 Φ(φ_k)=∫sign(s)·B(s;φ_k)ds → 对 φ 取 ⟨Φ²⟩ → 乘 (γb/ω)²=ω² 恢复归一化口径。方法学独立：golden=解析推导（∫cos 闭式 + φ 平均恒等式），cand=纯采样+梯形积分+数值 φ 平均，**不用任何闭式**",
        "note": "golden = 量子传感器芯片征程 QS-M2（退相干 + 多源噪声）的**自旋回波相位方差**闭式：单色噪声 B(t)=b·cos(ωt+φ)（φ 均匀）下，Hahn 回波对初相平均后的相位方差 ⟨Φ²⟩_echo = (γb/ω)²·2(1−cos(ωt/2))²（归一化口径丢 (γb/ω)²）。🔴 **物理意义**：DC 极限 ⟨Φ²⟩_echo ~ (ωt)⁴/32 为**四阶**，而 FID 仅**二阶** ⟨Φ²⟩_fid ~ (ωt)² ⇒ 回波把低频噪声四阶压制，正是**动力学去耦（DD）**提升相干时间的物理根因（平台缺口 G4「自旋相干时间建模」）。candidate=**时间域数值积分链**（纯采样+梯形积分+数值 φ 平均，不用任何闭式），方法学独立（golden=解析闭式；cand=数值时域积分）。实测默认档(ωt=2.0) rel=2.541e-09（tol=1e-3 的 3.94e5× 余量；时间/φ 网格离散化引入，**非**机器精度）。🔴 **与 B474 不同物理量**：B474 走灵敏度 η 的线宽 FOM 路径（时间包络 FWHM→σ_f→η 标量），B475 走相干时间建模本身（回波相位方差函数族）——candidate 物理对象不同（η 标量 vs 相位方差函数），非重复计数。🔴 **诚实规模**：QS-M2 另含「四源噪声正交合成」（平方和恒等 ⇒ 属 smoke）、「CPMG 滤波函数 F_n(ω→0)=0」（极限恒等 ⇒ 属 smoke），二者**非独立标量物理量** ⇒ 归 `run_qs_m2_smoke` 覆盖，**如实不登记为 B 锚**；本批只登记 B475 一锚（同 B472/B473/B474 纪律）。⚠️ **诚实边界**：本锚为**归一化无量纲**相位方差（b=1, γ=1 约定），只证明「回波方差闭式 ⇄ 时间域数值积分」数值一致这一数学事实，**不得作退相干时间/灵敏度的制造或性能宣称**（真实器件的 T₂ 受自旋浴谱、脉冲误差、有限脉宽等未建模因素降级）。零商业依赖（纯 numpy + math）。",
    },
    "B476": {
        "title": "最优色心深度 d*（灵敏度几何优化：深度 ⇄ 收集效率 ⇄ 表面噪声权衡）：闭式根方程 golden vs 网格扫描+抛物插值候选 · nm",
        "metric": "optimal_nv_depth_nm",
        "oracle": "closed_form(解 d⁴+d₀³·d=3·d₀³·d_att，由 d(ln η_tot)/dd=0 解析导出) + 网格扫描+抛物插值独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B476_DEFAULT_PARAMS),
        "golden_fn": golden_b476,
        "candidate": "b476_optimal_depth_grid_search_cand",
        "candidate_desc": "网格扫描 + 三点抛物插值定极小：在 [1e-3·d_att, 10·d_att] 上均匀取 200000 点，逐点算 η_tot(d)=√(1+(d₀/d)³)/√exp(−d/d_att)，argmin 定位极小格点后用 (i−1,i,i+1) 三点抛物插值精修极小位置。方法学独立：golden=解析求导→根方程→二分求根，cand=离散网格+抛物精修（不用任何导数/根方程）",
        "note": "golden = QS-M3（灵敏度几何优化）的**最优色心深度**闭式：对几何灵敏度 FOM η_tot(d)=√(1+(d₀/d)³)/√η_coll(d) 取 d(ln η_tot)/dd=0 ⇒ 闭式根方程 **d⁴+d₀³·d=3·d₀³·d_att**（f(d) 严格单调增 ⇒ 唯一正根，二分必收敛）。🔴 **物理意义**：色心深度是 NV 量子传感的核心几何旋钮——越深越难收集（出射衰减 exp(−d/d_att)），太浅受表面自旋浴噪声（谱扩散 ∝1/d³）劣化对比度 ⇒ **存在最优深度**（本档默认 d*=45.885 nm）。candidate=**网格扫描+抛物插值**（不用导数），方法学独立（golden=解析求导+二分；cand=离散网格+三阶抛物精修）。实测默认档 rel=3.617e-08（tol=1e-3 的 2.76e4× 余量；网格离散化+抛物三阶项引入，**非**机器精度）。🔴 **与 B473/B474/B475 不同物理量**：三者均为灵敏度/相干时间的**标量或函数族**，本锚是**几何量（深度）**，物理对象不同。🔴 **诚实规模**：QS-M3 另含「Purcell 计数率比闭式 ⇄ 数值峰值提取」（与 B18 同物理量 ⇒ 属 smoke）、「bulk 极限对照比 ∈(0,1]」（不等式约束 ⇒ 属 smoke）、「收集效率随深度单调降」（单调性 ⇒ 属 smoke），三者归 `run_qs_m3_smoke` 覆盖，**如实不登记为 B 锚**；本批只登记 B476/B477 两锚（同 B472–B475 纪律）。⚠️ **诚实边界**：d₀=20nm / d_att=200nm 为**设计示例**（室温 NV 典型量级）；本锚只证明「解析根方程 ⇄ 网格扫描+抛物插值」数值一致这一数学事实，**不得作制造/性能宣称**（真实最优深度受晶体取向、表面处理、实际出射几何等未建模因素影响）。零商业依赖（纯 numpy + math）。",
    },
    "B477": {
        "title": "NA 立体角收集效率 η_NA（偶极图样 sin²θ 在 NA 锥内能量占比）：闭式解析积分 golden vs 数值角分布采样候选 · 无量纲",
        "metric": "na_collection_efficiency",
        "oracle": "closed_form(η_NA=[cos³θ/3−cosθ]₀^{θmax}/(2/3)，θmax=arcsin NA) + 数值角分布采样独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B477_DEFAULT_PARAMS),
        "golden_fn": golden_b477,
        "candidate": "b477_na_efficiency_sampling_cand",
        "candidate_desc": "数值角分布采样：偶极图样 w(θ)=sin³θ·dθ（强度 sin²θ × 立体角 sinθ）全半球归一，取 θ≤θmax=arcsin(NA) 的权重占比（400000 点均匀采样求和）。方法学独立：golden=解析积分（∫sin³θ dθ 闭式代入），cand=数值逐点求和（不用任何闭式）",
        "note": "golden = QS-M3（灵敏度几何优化）的 **NA 立体角收集效率**闭式：偶极图样 I(θ)∝sin²θ（θ 自偶极轴量起），上半球总能量 ∝∫₀^{π/2}sin³θdθ=2/3；η_NA(NA)=[cos³θ/3−cosθ]₀^{θmax}/(2/3)，θmax=arcsin(NA)。🔴 **物理意义**：NA（数值孔径）决定每单位时间收集的光子数 ⇒ 直接影响散粒极限灵敏度（QS-M1 FOM ∝1/√n_ph）。candidate=**数值角分布采样**（不用闭式），方法学独立（golden=解析积分；cand=数值求和）。实测默认档(NA=0.75) rel=3.830e-06（tol=1e-3 的 261× 余量）；NA 扫描 0.3→1.0 残差 1.76e-05→0（最大残差在 NA=0.3，56× 余量；均 ≫ 机器精度，**非**代数恒等）。🔴 **量纲/边界**：NA=1 ⇒ θmax=π/2 ⇒ η_NA=1（全半球）；NA→0 ⇒ η_NA→0。🔴 **与 B476 不同物理量**：B476 是**深度**（nm），本锚是**立体角收集比**（无量纲），几何维度不同。🔴 **诚实规模**：同 B476 note（QS-M3 三链中两条归 smoke）。⚠️ **诚实边界**：NA=0.75 为**设计示例**（高 NA 物镜典型值）；本锚只证明「解析积分 ⇄ 数值采样」数值一致这一数学事实，**不得作制造/性能宣称**（真实收集效率还受金刚石内全内反射、金属反射镜损耗、色心取向分布等未建模因素降级）。零商业依赖（纯 numpy + math）。",
    },
    "B478": {
        "title": "磁偶极近场串扰系数 X（阵列相邻 NV 柱互相污染）：闭式立方律 golden vs 点偶极场数值积分候选 · 无量纲",
        "metric": "nv_array_crosstalk_coefficient",
        "oracle": "closed_form(X=(d_crit/r)³，轴向点偶极近场 B∝2m/r³ 与自场标度 m/d_crit³ 之比) + 点偶极场数值积分独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B478_DEFAULT_PARAMS),
        "golden_fn": golden_b478,
        "candidate": "b478_crosstalk_dipole_field_cand",
        "candidate_desc": "点偶极场数值积分：把轴向偶极离散成 ±q 分离 δ 的双单极子，场点 xo 处带符号轴向场 ∝[1/(xo−δ/2)²−1/(xo+δ/2)²]（两单极子符号相反 ⇒ 差分，泰勒展开回到 ∝2m/r³），比值 X_num=B(r)/B(d_crit)。方法学独立：golden=解析立方律，cand=双单极子差分场数值求和",
        "note": "golden = QS-M4（阵列化与规模）的**磁偶极近场串扰系数**闭式：轴向点偶极 i 在 j 处场 B_ij=μ₀/(4π)·2m/r³；自场标度 ∝m/d_crit³（d_crit=参考近距，取柱径）⇒ 比值 X=(d_crit/r)³。🔴 **物理意义**：相邻 NV 柱经磁偶极近场互相污染（∝1/r³ 快速衰减）——**阵列密度的根本物理约束**，决定「能排多密」。candidate=**点偶极场数值积分**（双单极子差分场，不用 r⁻³ 解析），方法学独立（golden=解析立方律；cand=数值求和）。实测默认档(r=1.20µm, d_crit=0.30µm) rel=4.679e-09（tol=1e-3 的 2.1e5× 余量；δ 二阶项引入，**非**代数恒等）。🔴 **与 B473 不同物理量**：B473 是**单器件**灵敏度标量，本锚是**阵列**串扰系数（几何/耦合量），物理对象不同。🔴 **诚实规模**：QS-M4 另含「串扰随 r 单调降」「阵列布局对称/节距」「读出 mux 音唯一性」「阵列 DRC/LVS」（单调性/几何约束/逻辑判据 ⇒ 属 smoke），归 `run_qs_m4_smoke` 覆盖，**不登记为 B 锚**。⚠️ **诚实边界**：d_crit 取柱径为**建模标度**（非任何 foundry 的真实金刚石阵列 deck）；本锚只证明「解析立方律 ⇄ 数值偶极场积分」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B479": {
        "title": "串扰恶化灵敏度倍率 √(1+X_tot²)（阵列通道被串扰噪声污染）：闭式平方和 golden vs 蒙特卡洛噪声功率叠加候选 · 无量纲",
        "metric": "nv_array_crosstalk_sensitivity_penalty",
        "oracle": "closed_form(√(1+X_tot²)，信号 + 正交串扰噪声平方和) + 蒙特卡洛噪声功率叠加独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B479_DEFAULT_PARAMS),
        "golden_fn": golden_b479,
        "candidate": "b479_crosstalk_penalty_montecarlo_cand",
        "candidate_desc": "蒙特卡洛噪声功率叠加：生成 n 对独立白噪声样本 (s,c)；纯净通道=s、受污染通道=s+X_tot·c；由数值方差比 sqrt(Var(polluted)/Var(pure)) 反推倍率。方法学独立：golden=解析平方和，cand=随机样本数值方差（残差=MC 统计误差）",
        "note": "golden = QS-M4（阵列化与规模）的**串扰恶化灵敏度倍率**闭式：η_eff=η_single·√(1+X_tot²)（串扰场与自信号统计独立 ⇒ 平方和）。🔴 **物理意义**：串扰不只是「读数串味」——它给通道注入额外噪声，直接恶化灵敏度；本锚把「串扰 → 灵敏度代价」钉进账本。candidate=**蒙特卡洛噪声功率叠加**（随机样本数值方差，不用解析平方和），方法学独立。实测默认档(X_tot=0.05) rel=1.918e-06（tol=1e-3 的 521× 余量；MC 统计误差，**非**代数恒等）。🔴 **与 B478 不同物理量**：B478 是**几何耦合系数**（X 本身），本锚是**灵敏度代价倍率**（X 的函数，含噪声统计），物理对象不同。🔴 **诚实规模**：同 B478 note。⚠️ **诚实边界**：X_tot=0.05 为**设计示例**；本锚只证明「解析平方和 ⇄ MC 数值方差」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B480": {
        "title": "梯度计共模抑制比 CMRR（两近邻 NV 柱差分抑共模）：闭式 20log₁₀(1/ε) golden vs 含噪样本 LSQ 斜率比候选 · dB",
        "metric": "nv_array_gradiometer_cmrr_db",
        "oracle": "closed_form(CMRR=20·log₁₀(1/ε)，ε=|ΔS|/S̄ 标度失配) + 含噪样本 LSQ 斜率比独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B480_DEFAULT_PARAMS),
        "golden_fn": golden_b480,
        "candidate": "b480_cmrr_noisy_lsq_slope_cand",
        "candidate_desc": "含噪样本 LSQ 斜率比：对真实磁力计逐点采样（读数含相对 σ 读出噪声）生成共模/差模激励序列，逐点算差分读数 D_c=(S₁−S₂)·B_c、D_d=S̄·ΔB，用**过原点最小二乘斜率**求比值再取 dB。方法学独立：golden=解析 ε 代入 log 闭式，cand=含噪样本 → LSQ 斜率比 → dB（不复用 ε 与 log 公式）",
        "note": "golden = QS-M4（阵列化与规模）的**梯度计共模抑制比**闭式：差分读数 D=S₁B₁−S₂B₂；共模 B_c ⇒ D_c=(S₁−S₂)B_c=ε·S̄·B_c；差模 ΔB ⇒ D_d=S̄·ΔB ⇒ 比=1/ε ⇒ CMRR=20log₁₀(1/ε)。🔴 **物理意义**：梯度计取两近邻柱**差分**读出 ⇒ 共模（环境磁噪声）被抑制，是阵列**必需**的抗噪手段；本锚把「标度失配 → 共模抑制代价」钉进账本。🔴 **口径对齐（吃狗粮抓到的真 bug）**：ε≡|S₁−S₂|/S̄ ⇒ 取 S₁=S̄(1+ε/2)、S₂=S̄(1−ε/2)（初版误用 S̄(1±ε) 致数值链系统性差 6 dB —— 已修正并登记为本锚口径）。candidate=**含噪样本 LSQ 斜率比**（不用 ε 与 log 闭式），方法学独立。实测默认档(ε=0.01) rel=2.295e-05（tol=1e-3 的 43.6× 余量；读出噪声统计起伏，**非**代数恒等——初版用中心差分对线性函数**恰精确** ⇒ 被判代数恒等，改用含噪样本 LSQ 才有真残差）。🔴🔴 **参数二次标定（全量照妖镜抓到的贴线 bug）**：初版 nf=0.001/n=2e6 ⇒ 跨种子最坏偏差 **2.8e-3 dB > tol 1e-3**（首轮侥幸 4.2e-5，重跑 1.68e-3 ⇒ 判决跨轮非确定）；根因 = CMRR 是 dB 量 ⇒ `20·log₁₀` 把斜率比相对噪声放大 20/ln10≈8.686 倍 + 共模斜率幅度只 ε=0.01 放大 `1/√<x²>`；处置 nf 0.001→0.0001、n 2e6→4e6 ⇒ seed 档 2.3e-5、跨 30 种子最坏 1.4e-4（tol 的 7× 余量，跨轮确定）。🔴 **与 B478/B479 不同物理量**：B478=串扰系数、B479=串扰灵敏度代价，本锚=**共模抑制比**（梯度计专属），物理对象不同。🔴 **诚实规模**：同 B478 note（QS-M4 四锚之外的单调性/几何/逻辑判据归 smoke）。⚠️ **诚实边界**：ε=0.01 为**设计示例**；本锚只证明「解析 log 闭式 ⇄ 含噪 LSQ 斜率比」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B481": {
        "title": "梯度计差模灵敏度 η_grad（两点差分噪声 ×√2 传播）：闭式 η√2/baseline golden vs 蒙特卡洛两点差分标准差候选 · T/√Hz/µm",
        "metric": "nv_array_gradiometer_eta",
        "oracle": "closed_form(η_grad=η_single·√2/baseline，两点差分噪声叠加) + 蒙特卡洛两点差分标准差独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B481_DEFAULT_PARAMS),
        "golden_fn": golden_b481,
        "candidate": "b481_grad_eta_montecarlo_diff_cand",
        "candidate_desc": "蒙特卡洛两点差分标准差：生成两独立通道噪声序列（各自 σ=η_single），取差分序列 (n1−n2) 的**数值标准差** ⇒ 直接得到 √2 因子（样本统计，非解析代入），再 /baseline。方法学独立：golden=解析 √2 因子，cand=样本差分标准差（残差=MC 统计误差）",
        "note": "golden = QS-M4（阵列化与规模）的**梯度计差模灵敏度**闭式：η_grad=η_single·√2/baseline（两点差分 ⇒ 两通道独立噪声叠加 ×√2；÷ baseline 归一到梯度量纲）。🔴 **物理意义**：梯度计基线（两柱间距）越短 ⇒ 梯度灵敏度越差（分母 baseline）；本锚把「基线 → 梯度灵敏度代价」钉进账本。candidate=**蒙特卡洛两点差分标准差**（样本差分统计，不用解析 √2），方法学独立。实测默认档(η=1nT/√Hz, baseline=1.2µm) rel=1.000e-04（tol=1e-3 的 10× 余量；MC 统计误差，**非**代数恒等）。🔴 **与 B480 不同物理量**：B480 是**共模抑制比**（dB，无量纲），本锚是**差模灵敏度**（T/√Hz/µm，带量纲），物理对象不同。🔴 **诚实规模**：同 B478 note。⚠️ **诚实边界**：η_single=1nT/√Hz / baseline=1.2µm 为**设计示例**；本锚只证明「解析 √2 因子 ⇄ MC 样本差分标准差」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B482": {
        "title": "微波频锁鉴别器中心斜率（ODMR 锁定增益）：闭式解析线型差分斜率 golden vs 时域 FID 数值线型中心差分斜率候选 · 无量纲（Hz⁻¹）",
        "metric": "qs_freqlock_discriminator_slope",
        "oracle": "closed_form(S(f)=L(f−δ)−L(f+δ) 的解析中心斜率 dS/df|f₀，L 为洛伦兹) + 时域 FID 数值变换线型的中心差分斜率独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B482_DEFAULT_PARAMS),
        "golden_fn": golden_b482,
        "candidate": "b482_freqlock_slope_fid_cand",
        "candidate_desc": "时域 FID 数值变换线型的中心差分斜率：用指数衰减包络 C(t)=e^{−πwt} 的数值 Fourier 变换构造洛伦兹线型（采集窗 t_max=t_max_factor/(πw)），再对鉴别器 S=L(f−δ)−L(f+δ) 在 f₀ 处中心差分求斜率。方法学独立：golden=解析洛伦兹差分，cand=FID 时域采样 → 数值变换 → 数值差分（不用解析求导）",
        "note": "golden = QS-M5（闭环标定 + 动态范围）的**微波频锁鉴别器中心斜率**闭式：S(f)=L(f−δ)−L(f+δ)（洛伦兹线型 L(x)=1−(w/2)²/((x−f₀)²+(w/2)²)），在真共振 f₀ 处取中心差分 ⇒ 鉴别器**增益 dS/df|f₀**（决定频锁环路带宽与噪声传递）。🔴 **物理意义**：微波源漂移会让 ODMR 工作点漂出零场分裂（DZFS=2.87 GHz）⇒ 灵敏度骤降；频锁靠**鉴别器**给出误差信号 S，而**增益=S 的中心斜率**决定环路性能 ⇒ 本锚把「锁定增益」钉进账本（平台缺口 G7「量子传感器标定/读出闭环」）。candidate=**时域 FID 数值变换线型的中心差分斜率**（不用解析差分），方法学独立（golden=解析；cand=FID 数值变换）。实测默认档(w=10 MHz, δ=2.5 MHz) rel=6.696e-06（tol=1e-3 的 ~150× 余量；**有限 FID 采集窗截断**引入，**非**代数恒等；t_max_factor 从 15→60 ⇒ 残差单调降，实测确证收敛）。🔴 **与 B473/B474 不同物理量**：B473/B474 是**灵敏度 η**（T/√Hz 标量/函数族），本锚是**频锁鉴别器增益**（Hz⁻¹，锁定回路专属标量），物理对象不同。🔴 **诚实规模**：QS-M5 另含「动态范围 DR=20log₁₀(B_max/B_min)」（**纯定义式** ⇒ 属 smoke，登记会构成定义充数）、「频锁几何收敛 gain=0.9 ⇒ 残差 ×0.1」（控制律收敛性 ⇒ 属 smoke）、「鉴别器对称性 S(f₀)=0」「DR 随线宽/积分时间单调」「磁场闭环读数误差=ε_k」（对称性/单调性/恒等 ⇒ 属 smoke）、「线性段耗尽场 B_max=(w/2)/γ」（定义标度 ⇒ 属 smoke），均归 `run_qs_m5_smoke` 覆盖，**如实不登记为 B 锚**；本批只登记 B482–B484 三锚（同 B472/B476/B478 纪律）。⚠️ **诚实边界**：w=10 MHz / δ=2.5 MHz 为**设计示例**（室温 NV 集合体典型量级）；本锚只证明「解析鉴别器斜率 ⇄ FID 数值线型斜率」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B483": {
        "title": "磁场标度因子自标定 k̂（磁场闭环核心）：闭式两点法 golden vs 全跨多点 LSQ 斜率候选 · V/T",
        "metric": "qs_fieldloop_scale_factor",
        "oracle": "closed_form(k̂=V_ref/B_ref 两点法，无噪声代数精确) + 全跨多点最小二乘斜率独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B483_DEFAULT_PARAMS),
        "golden_fn": golden_b483,
        "candidate": "b483_fieldloop_scale_lsq_cand",
        "candidate_desc": "全跨多点最小二乘斜率：在 ±B_ref 全量程上取 n 点激励，读数含相对读出噪声 σ=noise_rel·V_ref，过原点 LSQ 斜率 ⇒ k̂。方法学独立：golden=单点相除（两点法），cand=多点 LSQ 斜率（抗噪，物理上与高阶标定一致）",
        "note": "golden = QS-M5（闭环标定 + 动态范围）的**磁场标度因子自标定**闭式：施加**已知参考场** B_ref，读响应 V_ref，k̂=V_ref/B_ref。🔴 **物理意义**：读出「电压」必须换成「磁场」⇒ 标度因子 k 必须测得准，读数相对误差恰等于标度失配 ε_k=|k̂−k|/k ⇒ 本锚把「标定算法」钉进账本（平台缺口 G7）。candidate=**全跨多点 LSQ 斜率**（不用单点相除），方法学独立（golden=两点法单点；cand=多点 LSQ）。实测默认档(V_ref=0.1 V, B_ref=100 µT, noise_rel=1e-4) rel=3.439e-08（tol=1e-3 的 ~2.9e4× 余量；**LSQ 噪声投影残差**，**非**代数恒等；noise_rel=0 ⇒ 恰等，如实标注）。🔴 **与 B473 不同物理量**：B473 是**物理灵敏度**（T/√Hz），本锚是**仪器标度因子**（V/T，标定量），物理对象不同。🔴 **诚实规模**：同 B482 note（QS-M5 六链中四条归 smoke）。⚠️ **诚实边界**：V_ref=0.1 V / B_ref=100 µT 为**设计示例**；本锚只证明「两点法 ⇄ 多点 LSQ」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B484": {
        "title": "AC 灵敏度带宽折算 η_AC（动态范围/读出）：闭式 η·√(2Δf) golden vs 蒙特卡洛带限噪声 rms 候选 · T",
        "metric": "qs_ac_sensitivity_bandwidth",
        "oracle": "closed_form(η_AC=η·√(2Δf)，两点差分 ×√2 + 带宽折算 √Δf) + 蒙特卡洛带限噪声 rms 独立_cross_check",
        "tol": 5e-3,
        "default_params": dict(B484_DEFAULT_PARAMS),
        "golden_fn": golden_b484,
        "candidate": "b484_ac_sensitivity_mc_cand",
        "candidate_desc": "蒙特卡洛带限噪声 rms：生成 n 对白噪声样本（σ=η），取差分序列 (n1−n2) 的**数值 rms** ⇒ 直接得到 √2 因子（样本统计），再按 √Δf 折算带宽。方法学独立：golden=解析 √2·√Δf，cand=样本差分 rms（残差=MC 统计误差）",
        "note": "golden = QS-M5（闭环标定 + 动态范围）的**AC 灵敏度带宽折算**闭式：η_AC=η·√(2·Δf)（幅度谱密度 η，AC 两点差分 ×√2，带宽折算 √Δf）。🔴 **物理意义**：AC（差分）读出相对 DC 的灵敏度代价 = √(2Δf)，是动态范围下限（噪声底）的关键换算 ⇒ 本锚把「带宽 → 灵敏度」钉进账本（口径与 DC 的 η 同源，**禁**与线宽受限 LOD / 单次测量不确定度混比）。candidate=**蒙特卡洛带限噪声 rms**（样本差分统计，不用解析 √2），方法学独立（golden=解析因子；cand=样本 rms）。🔴🔴 **样本数/tol 二次标定（承 QS-M4 B480 血案：含噪余量必按跨种子最坏偏差标定）**：初版 n=8e6 ⇒ **跨 20 种子最坏偏差 5.1e-4**，仅 tol=1e-3 的 **2× 余量**（贴线 ⇒ 违确定性纪律）；处置 n 8e6→32e6 ⇒ 最坏降到 **2.1e-4**，并把本锚 **tol 定为 5e-3**（余量 **≈24×**，跨轮确定）；实测 n→64e6 **无收益**（≈1.9e-4，σ 由**有限样本分布形状**主导，非样本数）⇒ 如实取 32e6。🔴 **与 B473/B474 不同物理量**：B473/B474 是 DC 灵敏度 η（口径本身），本锚是**AC 带宽折算后的灵敏度**（带 Δf 量纲），物理对象不同。🔴 **诚实规模**：同 B482 note。⚠️ **诚实边界**：η=1 nT/√Hz / Δf=1 kHz 为**设计示例**；本锚只证明「解析 √2·√Δf ⇄ MC 样本差分 rms」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B485": {
        "title": "SQUID 环路临界电流磁通调制 I_c(Φ)（超导磁力计）：闭式矢量叠加 golden vs 数值相空间扫描候选 · A",
        "metric": "qs_squid_ic_flux_modulation",
        "oracle": "closed_form(I_c(Φ)=2·I_c0·|cos(π·Φ/Φ0)|，对称双结并联环路磁通量子化矢量叠加) + 数值相空间扫描独立_cross_check",
        "tol": 1e-12,
        "default_params": dict(B485_DEFAULT_PARAMS),
        "golden_fn": golden_b485,
        "candidate": "b485_squid_ic_phase_scan_cand",
        "candidate_desc": "数值相空间扫描：对 I(δ)=I_c0·[sinδ+sin(δ+2πf)] 在 δ∈[0,2π) 以 2^18 网格扫 |I| 最大 ⇒ 独立复算临界电流（固定**非对齐** f=0.30）。方法学独立：golden=闭式矢量叠加，cand=逐相位扫描取极值（残差=相位网格截断）",
        "note": "golden = QS-M6（超导 SQUID 磁力计 · 第二腿）的**环路临界电流磁通调制**闭式：I_c(Φ)=2·I_c0·|cos(π·Φ/Φ0)|（对称双结并联 SQUID，磁通量子化约束两结相位差 δ1−δ2=2πf ⇒ 两结临界电流**矢量叠加**取模，周期 Φ0）。🔴 **物理意义**：I_c(Φ) 是 SQUID 一切功能之源（磁通周期调制）；本锚把「磁通量子化 ⇒ 临界电流调制」钉进账本 ⇒ 误改调制律必被机器判红（平台缺口 G8「超导量子器件物理（约瑟夫森结/磁通）」）。candidate=**数值相空间扫描**（逐相位取极值，不用闭式），方法学独立（golden=闭式矢量叠加；cand=相位扫描）。🔴🔴 **独立性关键坑**：f=0.25（及一切使极值点 δ*=π/2−πf 落 2 幂网格节点的 f）时扫描**恰好命中极值** ⇒ 残差**恒 0**（**代数恒等**），会被 `run_benchmark_falsifiability_smoke` 判自证桩 ⇒ 本锚固定 **f=0.30**（δ*/Δδ=25.6 非整数）。实测默认档(ic0=2 µA, f=0.30) **rel=4.596e-11**（abs 残差 1.08e-16 · **tol=1e-12**〔按量级标定 · 同 B33/B36/B473 约定〕⇒ **~9.3e3×** 余量；**相位网格截断残差**，**非**代数恒等；粗网格 n=64 ⇒ 残差 7.7e-4 放大 1.7e7×，反向探针确证）。🔴 **与 B473–B484 不同物理量**：B473–B484 是 NV 色心的**光-自旋-磁**耦合（自旋能级/ODMR）；本锚是**电-磁通**耦合（宏观量子相位/约瑟夫森效应），物理对象完全不同。🔴 **与 B18/B25 不同物理量**：B18/B25 是 transmon/磁通调谐 qubit 的 **E_J(Φ)/koch_f01**（量子比特**能谱**，GHz）；本锚是**传感器临界电流**（电流量纲），物理量纲与用途均不同。🔴 **诚实规模**：QS-M6 另含「RCSJ 锁定判据 δ_eq=asin(I_b/I_c)」（平衡态/定义 ⇒ 属 smoke）、「β_c 滞回判据」（无量纲定义 ⇒ 属 smoke）、「I_c 在 f=0 极大 / f=0.5 为零」（对称性 ⇒ 属 smoke）、「A_eff=side² / B=Φ/A」（纯几何定义 ⇒ 属 smoke）、「S_Φ∝T / B_N∝√S_Φ / B_N∝1/A」（标度律 ⇒ 属 smoke）、「情景单调性」（单调性 ⇒ 属 smoke），均归 `run_qs_m6_smoke` 覆盖，**如实不登记为 B 锚**；本批只登记 B485–B487 三锚（同 B482/B478 纪律）。⚠️ **诚实边界**：ic0=2 µA / R_n=20 Ω / T=4.2 K / 环路 100 µm 均为**设计示例**（4 K 超导典型量级），**非实测**；本锚只证明「闭式矢量叠加 ⇄ 相位扫描」数值一致这一数学事实，**不得作制造/性能宣称**；蓝图 §3 的「1–5 fT/√Hz」系公开文献值（物理学报 2025,74,20250426），仅作对标准星。零商业依赖（纯 numpy + math）。",
    },
    "B486": {
        "title": "磁通-电压转导 ∂I_c/∂Φ（超导磁力计）：闭式解析导数 golden vs 数值中心差分候选 · A/Wb",
        "metric": "qs_squid_flux_transfer",
        "oracle": "closed_form(∂I_c/∂Φ=−2π·I_c0·sin(πf)·sgn(cosπf)/Φ0) + 数值中心差分独立_cross_check",
        "tol": 5e3,
        "default_params": dict(B486_DEFAULT_PARAMS),
        "golden_fn": golden_b486,
        "candidate": "b486_squid_transfer_fd_cand",
        "candidate_desc": "数值中心差分：对闭式 I_c(Φ±ΔΦ) 做 (hi−lo)/(2ΔΦ)，ΔΦ=1e-6，固定 f=0.30（只调用 I_c 闭式，**不求导**）。方法学独立：golden=解析求导，cand=离散差分（残差=有限差分截断+舍入折衷，对 ΔΦ 非单调）",
        "note": "golden = QS-M6（超导 SQUID 磁力计 · 第二腿）的**磁通-电压转导**闭式：∂I_c/∂Φ=−2π·I_c0·sin(πf)·sgn(cos(πf))/Φ0（A/Wb，f 在 |cos| 光滑区间内）。🔴 **物理意义**：转导 = 环路临界电流对磁通的**斜率** ⇒ 决定磁通→电流读出增益；磁灵敏度 B_N ∝ 1/|转导|（B487 直接依赖）。本锚把「转导律」钉进账本（缺口 G8）。candidate=**数值中心差分**（只调用 I_c 闭式、不求导），方法学独立（golden=解析求导；cand=离散差分）。实测默认档(ic0=2 µA, f=0.30, ΔΦ=1e-6) **rel=2.869e-11**（abs 残差 0.141 · **tol=5e3**〔按量级标定 · 同 B33/B36/B473 约定〕⇒ **~3.5e4×** 余量；**有限差分截断（∝ΔΦ²）+ 舍入（∝1/ΔΦ）双向折衷** ⇒ 残差对 ΔΦ **非单调**，正是真数值残差签名，**非**代数恒等；粗步长 ΔΦ=1e-2 ⇒ 残差 1.6e-4，反向探针确证）。🔴 **与 B18/B25 不同物理量**：B18/B25 是 transmon 能谱（f01）；本锚是**传感器转导**（电流/磁通比），物理量纲与用途均不同。🔴 **诚实规模**：同 B485 note（QS-M6 其余六链归 smoke）。⚠️ **诚实边界**：ic0=2 µA / ΔΦ=1e-6 Φ0 为**设计示例**；本锚只证明「解析求导 ⇄ 数值差分」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B487": {
        "title": "磁场灵敏度谱密度 B_N（超导磁力计）：闭式逐级代入 golden vs 蒙特卡洛 Johnson 噪声传播候选 · T/√Hz",
        "metric": "qs_squid_field_sensitivity",
        "oracle": "closed_form(B_N=√(4·k_B·T/R)/|∂I_c/∂Φ|/A_eff，Johnson 噪声+转导+面积三链代入) + 蒙特卡洛噪声传播独立_cross_check",
        "tol": 1e-15,
        "default_params": dict(B487_DEFAULT_PARAMS),
        "golden_fn": golden_b487,
        "candidate": "b487_field_sens_mc_cand",
        "candidate_desc": "蒙特卡洛 Johnson 噪声传播：生成 n_mc=4e6 个电流样本 σ=√(4k_BT/R)，经数值转导折算磁通样本，取**数值方差** ⇒ S_Φ ⇒ √/A_eff ⇒ B_N（样本统计，不用解析 √）。方法学独立：golden=闭式逐级代入，cand=样本方差统计（固定 seed）",
        "note": "golden = QS-M6（超导 SQUID 磁力计 · 第二腿）的**磁场灵敏度谱密度**闭式：B_N=√(4·k_B·T/R)/|∂I_c/∂Φ|/A_eff（T/√Hz）——三链串联终值（RCSJ → I_c(Φ)/转导 → Johnson 热噪声 → B_N）。🔴 **物理意义**：Johnson 噪声电流 S_I=4k_BT/R 经转导折算磁通噪声 S_Φ=S_I/(∂I/∂Φ)²、再除有效面积 ⇒ 磁力计噪声底；本锚把「噪声+转导+面积」的耦合钉进账本（缺口 G8 的落地标量），是「分步达国际水平」的性能天花板靶（蓝图 §3：SQUID 集成 1–5 fT/√Hz 系公开文献值，本档只作对标准星）。candidate=**蒙特卡洛 Johnson 噪声传播**（样本方差，不用解析公式），方法学独立（golden=闭式逐级代入；cand=MC 统计）。🔴🔴 **含噪余量标定（承 QS-M4 B480 血案：含噪余量必按跨种子最坏偏差标定）**：实测 n_mc=4e6 ⇒ **跨 20 种子最坏 rel = 8.09e-4**（abs 6.4e-17）⇒ 本锚 **tol=1e-15**〔按量级标定 · 同 B33/B36/B473 约定〕（余量 **≈15.6×**，按最坏而非单次 seed 判）；n_mc 4e5→4e6 使最坏 1.9e-3→8.1e-4。🔴 **与 B473 不同物理量**：B473 是 NV 色心的**自旋散粒极限灵敏度**（光-自旋耦合）；本锚是超导 SQUID 的**热噪声受限灵敏度**（电-磁通耦合），物理机制与量级均不同（NV 芯片级 ~26 nT/√Hz vs SQUID 集成 ~1 fT/√Hz，高一个量级）。🔴 **诚实规模**：同 B485 note。⚠️ **诚实边界**：T=4.2 K / R_n=20 Ω / ic0=2 µA / 环路 100 µm 均为**设计示例**（建模值 79.25 fT/√Hz，**非实测**）；本锚只证明「闭式逐级代入 ⇄ MC 样本方差」数值一致这一数学事实，**不得冒充 LDA 实测**、**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B488": {
        "title": "磁通聚焦变压器有效面积 A_eff（超导磁力计优化）：闭式分压比 golden vs 离散 Neumann 互感重建候选 · m²",
        "metric": "qs_flux_transformer_effective_area",
        "oracle": "closed_form(A_eff=γ_A·A_p·M/(L_i+L_p)，匝间互感分压) + 离散 Neumann 互感双和独立_cross_check",
        "tol": 2e-2,
        "default_params": dict(B488_DEFAULT_PARAMS),
        "golden_fn": golden_b488,
        "candidate": "b488_flux_transformer_neumann_cand",
        "candidate_desc": "离散 Neumann 互感重建：把拾取环（r_p=1）与输入线圈（r_i=0.5，轴向间距 0.2）离散为 n_seg=2048 段，由逐段互感双和数值重建耦合几何比（含 2n 网格 Richardson 外推），再由给定电感还原分压比 ⇒ A_eff。方法学独立：golden=闭式分式，cand=离散互感求和（残差=Neumann 离散化截断）",
        "note": "golden = QS-M7（超导 SQUID 性能冲刺 · 噪声优化）的**磁通聚焦变压器有效面积**闭式：A_eff=γ_A·A_p·M/(L_i+L_p)（m²）——拾取环磁通经互感 M 耦合到输入线圈（分压比 M/(L_i+L_p)）再进 SQUID 环，周期外推 ⇒ 有效面积远超裸环几何（本档 15×）。🔴 **物理意义**：磁通聚焦变压器是超导磁力计逼近 SOTA 的**第一条杠杆**（把大拾取环的有效面积放大）；本锚把「互感分压增益」钉进账本（平台缺口 G9「超导量子传感优化」）。candidate=**离散 Neumann 互感重建**（逐段互感双和，不用闭式分式），方法学独立（golden=闭式分压比；cand=离散互感求和）。实测默认档(A_p=(500µm)², M=1.6nH, L_i=L_p=2nH, γ=1.5) **rel=1.644e-03**（abs 2.47e-10 · **tol=2e-2**〔按量级标定 · 同 B33/B36/B473 约定〕⇒ **~12.2×** 余量；**Neumann 离散化截断 ∝1/n_seg**，**非**代数恒等；粗网格 n_seg=32 ⇒ 残差 0.105 放大 64×，反向探针确证）。🔴 **与 B480/B481 不同物理量**：B480/B481 是**梯度计差分读出**（共模抑制比 CMRR / 差模灵敏度）；本锚是**单器件磁通聚焦放大**（有效面积增益，m²），物理对象完全不同（差分抑制 vs 单通道放大）⇒ 🔴 **本档不含梯度计/CMRR 链**（避免与 B480 撞车）。🔴 **与 B485 不同物理量**：B485 是**裸环几何面积** A_eff=side²（纯几何定义）；本锚是**变压器放大后的有效面积**（互感分压，含 η），物理对象与量纲链均不同。🔴 **诚实规模**：QS-M7 另含「washer 电感 L≅1.25µ0d」（定义式 ⇒ 属 smoke）、「阻抗匹配 L_i=L_p ⇒ A_eff 最大」（最优性 ⇒ 属 smoke）、「γ↑⇒A_eff↑」（单调性 ⇒ 属 smoke），均归 `run_qs_m7_smoke` 覆盖，**如实不登记为 B 锚**；本批只登记 B488–B490 三锚（同 B482/B485 纪律）。⚠️ **诚实边界**：A_p=(500µm)² / M=1.6 nH / L_i=L_p=2 nH / γ=1.5 均为**设计示例**（4 K 超导典型量级），**非实测 PDK**；本锚只证明「闭式分压比 ⇄ 离散互感重建」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B489": {
        "title": "亚微米结噪声约束磁通噪声谱密度 S_Φ,opt（超导磁力计优化）：闭式逐级代入 golden vs 蒙特卡洛 Johnson 噪声传播候选 · Wb²/Hz",
        "metric": "qs_submicron_junction_noise_psd",
        "oracle": "closed_form(S_Φ,opt=4k_B·T/R_n,opt/(2π·I_c0·sin(πf)/Φ0)²，Johnson 噪声 + 转导逐级代入) + 蒙特卡洛噪声传播独立_cross_check",
        "tol": 1e-2,
        "default_params": dict(B489_DEFAULT_PARAMS),
        "golden_fn": golden_b489,
        "candidate": "b489_submicron_noise_mc_cand",
        "candidate_desc": "蒙特卡洛 Johnson 噪声传播：生成 n_mc=4e6 个电流样本 σ=√(4k_BT/R_n,opt)，经数值转导（中心差分）折算磁通样本，取数值方差 ⇒ S_Φ,opt（样本统计，不用解析公式）。方法学独立：golden=闭式逐级代入，cand=样本方差统计（固定 seed）",
        "note": "golden = QS-M7（超导 SQUID 性能冲刺 · 噪声优化）的**亚微米结噪声约束磁通噪声谱密度**闭式：S_Φ,opt=4k_B·T/R_n,opt/(2π·I_c0·sin(πf)/Φ0)²（Wb²/Hz）——亚微米结抬升 R_n ⇒ Johnson 噪声 S_I=4k_BT/R_n ↓；转导 ∝ I_c0 ⇒ S_Φ=S_I/转导²。🔴 **物理意义**：亚微米结是超导磁力计逼近 SOTA 的**第二条杠杆**（抬高分流电阻 R_n ⇒ 压低 Johnson 噪声底）；本锚把「结工艺 → 噪声底」这一优化律钉进账本（缺口 G9）。candidate=**蒙特卡洛 Johnson 噪声传播**（样本方差，不用解析公式），方法学独立（golden=闭式逐级代入；cand=MC 统计）。🔴🔴 **含噪余量标定（承 QS-M4 B480 / QS-M6 B487 血案：含噪余量必按跨种子最坏偏差标定）**：实测 n_mc=4e6 ⇒ **跨 20 种子最坏 rel = 1.18e-3**（abs 1.4e-47）⇒ 本锚 **tol=1e-2**（余量 **≈8.5×**，按最坏而非单次 seed 判）。🔴 **与 B487 不同物理量**：B487 是**裸结**（R_n=20 Ω）的 B_N；本档 B489 是**亚微米结抬升后**（R_n,opt=142.5 Ω）的 S_Φ,opt —— 同链不同参（裸结 vs 优化结），且 B487 是**灵敏度**（T/√Hz）而本锚是**噪声谱密度**（Wb²/Hz）⇒ 物理量与参数面均不同。🔴 **退化自洽**：R_n,opt=裸结 R_n 时 B489 **精确退化**为 QS-M6 的 S_Φ（同式同参）⇒ 本档登记的是「R_n 抬升后的优化量」，非重复。🔴 **诚实规模**：同 B488 note。⚠️ **诚实边界**：T=4.2 K / I_c0=2 µA / R_n,opt=142.5 Ω（=20 Ω×7.125）为**设计示例**（非实测 PDK）；本锚只证明「闭式逐级代入 ⇄ MC 样本方差」数值一致这一数学事实，**不得冒充 LDA 实测**、**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B490": {
        "title": "优化后磁场灵敏度 B_N,opt（超导磁力计优化）：闭式三重叠加 golden vs MC + 数值变压器解候选 · T/√Hz",
        "metric": "qs_optimized_field_sensitivity",
        "oracle": "closed_form(B_N,opt=√(S_Φ,opt)/A_eff，变压器增益 + 亚微米结 + 温降三重叠加) + MC 噪声 + 数值互感独立_cross_check",
        "tol": 2e-2,
        "default_params": dict(B490_DEFAULT_PARAMS),
        "golden_fn": golden_b490,
        "candidate": "b490_opt_field_sens_mc_neumann_cand",
        "candidate_desc": "MC 噪声 + 离散 Neumann 变压器解：有效面积走离散 Neumann 互感重建（n_seg=2048），噪声走 n_mc=4e6 样本方差 ⇒ B_N,opt（复合独立路径，不用闭式）。方法学独立：golden=闭式逐级代入，cand=MC 统计 + 数值互感（固定 seed）",
        "note": "golden = QS-M7（超导 SQUID 性能冲刺 · 噪声优化）的**优化后磁场灵敏度**闭式：B_N,opt=√(S_Φ,opt)/A_eff（T/√Hz）——三重叠加（变压器增益 A_eff ↑ + 亚微米结 R_n ↑ + 温降 T ↓）。🔴 **物理意义**：本锚是 QS-M7 的**落地标量**——三链串联终值，把「磁通聚焦/亚微米结 → 灵敏度」的优化叠加钉进账本（缺口 G9 的落地标量，是「分步达国际水平」的性能靶；本档建模 B_N,opt≈1.73 fT/√Hz，**进入**蓝图 §3 的集成 SOTA 带 1–5 fT/√Hz）。candidate=**MC 噪声 + 离散 Neumann 变压器解**（样本方差 + 数值互感），方法学独立（golden=闭式逐级代入；cand=MC 统计 + 数值互感）。实测默认档 **rel=2.105e-03**（abs 3.6e-18 · **tol=2e-2**〔按量级标定 · 同 B33/B36/B473 约定〕⇒ **~9.5×** 余量；**MC 统计 + Neumann 截断复合残差**，**非**代数恒等）。🔴 **与 B487 不同物理量**：B487 是**裸环基线**灵敏度（79.25 fT/√Hz）；本锚是**优化后**灵敏度（1.73 fT/√Hz）—— 同链不同优化档，且本锚含变压器增益 / 亚微米结 / 温三重叠加 ⇒ 物理量不同（基线 vs 优化）。🔴 **与 B480/B481 不同物理量**：B480/B481 是**梯度计差分读出**；本锚是**单器件优化灵敏度**，物理对象不同。🔴 **诚实规模**：同 B488 note。⚠️ **诚实边界**：全部参数为**设计示例**（建模值 1.73 fT/√Hz，**非实测**）；蓝图 §3 的「集成 1–5 fT/√Hz」系**公开文献值**（物理学报 2025,74,20250426），本档只把它作**对标准星**引用，**不冒充 LDA 实测**；本锚只证明「闭式三重叠加 ⇄ MC + 数值互感」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B491": {
        "title": "光抽运关闭后自由进动横向极化 P_x(t*)（OPM/SERF 腿 C 时域信号）：闭式 Bloch 精确解 golden vs RK4 时间推进候选 · 无量纲",
        "metric": "qs_opm_fid_polarization",
        "oracle": "closed_form(P_x(t)=P₀·e^(−R_tot·t)·cos(2π·γ_e·B·t)，2D 线性 Bloch 方程初值 (P₀,0) 的精确解) + RK4 时间推进独立_cross_check",
        "tol": 1e-7,
        "default_params": dict(B491_DEFAULT_PARAMS),
        "golden_fn": golden_b491,
        "candidate": "b491_fid_polarization_rk4_cand",
        "candidate_desc": "RK4 时间推进 2D Bloch 方程（固定步长 h=t*/n=64，逐点四阶 Runge–Kutta，不含任何解析指数/余弦成分）⇒ 取 t* 处 P_x。方法学独立：golden=闭式精确解，cand=数值时间推进",
        "note": "golden = QS-M9（光泵原子磁力计 OPM/SERF · 腿 C）的**自由进动横向极化**闭式：P_x(t)=P₀·e^(−R_tot·t)·cos(ω_L·t)（无量纲，ω_L=2π·γ_e·B）——光抽运关闭后自旋在静磁场中自由进动，横向极化按自旋相关时间 1/R_tot 衰减、按 Larmor 频率振荡；该式是 2D 线性 Bloch 方程的**精确解**（不含近似）⇒ 可作 golden。🔴 **物理意义**：这是 OPM 的**时域信号本体**（与腿 A 的 ODMR/Ramsey、腿 B 的 SQUID 磁通调制并列）—— 本锚把「光-自旋-磁」三场耦合的时域响应钉进账本（平台缺口 G11 多物理场量子传感整合）。candidate=**RK4 时间推进**（方法学独立），实测默认档(P₀=1, R_tot=300 1/s, B=10 nT, t*=2 ms) **rel=7.071e-10**（abs 2.475e-10 · **tol=1e-7** ⇒ **141×** 余量；残差链 2.770e-6 → 1.779e-7 → 1.125e-8 → 7.071e-10，**比值 15.57/15.81/15.91×** ⇒ **O(h⁴)**，与 RK4 标称阶一致 ⇒ **非**代数恒等；n_steps=8 粗网格残差放大 ~3917×）。🔴 **与 B475 不同物理量**：B475 是**自旋回波（Hahn echo）的相位方差**（退相干谱 · 时间域数值积分链）；本锚是**自由进动的横向极化分量** P_x(t) ⇒ 被测标量不同（相位方差 vs 极化）+ 构型不同（脉冲序列 vs 自由进动）⇒ 记新锚（先例 B452 vs B33）。🔴 **与 B452 不同物理量**：B452 是**驱动器一阶 RC 阶跃电压**（1D 单调弛豫）；本锚是**衰减振荡的 2D 耦合 Bloch 系统**（横向极化）⇒ 标量/构型/解的结构（振荡 vs 单调）三处分歧 ⇒ 记新锚（同上先例）。🔴 **与 B473–B484（腿 A NV）不同物理对象**：NV 是**金刚石固体单自旋**（ODMR/Ramsey）；本锚是**碱金属蒸气集合自旋**（光抽运 + 自由进动）⇒ 换能机制与物态均不同。🔴 **诚实规模**：QS-M9 另含「稳态极化 P∞=R_op/(R_op+R_sd)」「亥姆霍兹线圈 B(0)=(4/5)^{3/2}µ₀NI/R」「自旋破坏率=壁+缓冲气体+探测光」「SERF 灵敏度 η=√(R_tot/N_a)/(2πγ_eP∞)」等量 —— 前二者为**闭式算术/速率方程稳态**、后者其自旋投影噪声因子 √(1/N_a) **无可行数值候选**（任何 MC 需模拟 N_a≈1e13 个独立自旋）⇒ 均归 `run_qs_m9_smoke` 覆盖，**如实不登记为锚**（本批只 B491–B493 三锚 · 同 B-44/B-45/B-46 纪律：宁可少，不越级谎报）。⚠️ **诚实边界**：P₀ / R_tot / B / t* 为**设计示例量级**（SERF OPM 典型），**非实测装置 PDK**；本锚只证明「闭式精确解 ⇄ RK4 时间推进」数值一致这一数学事实，**不得作制造/性能宣称**、**不冒充 LDA 实测**。零商业依赖（纯 numpy + math）。",
    },
    "B492": {
        "title": "碱金属（Rb）饱和蒸气数密度 n(T)（OPM 气室温度定标）：闭式 Clausius–Clapeyron golden vs 复合梯形数值积分候选 · m⁻³",
        "metric": "qs_alkali_vapor_density",
        "oracle": "closed_form(n(T)=n_ref·exp(−(ΔH/k_B)·(1/T − 1/T_ref))，Clausius–Clapeyron 常数汽化焓模型) + 复合梯形数值积分独立_cross_check",
        "tol": 5e12,
        "default_params": dict(B492_DEFAULT_PARAMS),
        "golden_fn": golden_b492,
        "candidate": "b492_alkali_density_trapezoid_cand",
        "candidate_desc": "复合梯形数值积分 d(ln n)/dT=ΔH/(k_B·T²)（n_seg=256 段，逐段梯形平均，不含闭式指数）⇒ 由积分结果取 exp。方法学独立：golden=闭式指数，cand=数值求积",
        "note": "golden = QS-M9（OPM/SERF · 腿 C）的**碱金属饱和蒸气数密度**闭式：n(T)=n_ref·exp(−(ΔH/k_B)(1/T−1/T_ref))（m⁻³，Rb 汽化焓/k_B=8384 K）—— 气室的**温度→密度**定标律。🔴 **物理意义**：N_a=n(T)·V_cell 是**自旋投影噪声的分母**（N_a ↑ ⇒ 灵敏度 ↑），同时决定光抽运与自旋交换弛豫 ⇒ 多物理场「热-几何-自旋」耦合的第一环；本锚把气室热力学钉进账本（缺口 G11）。candidate=**复合梯形数值积分**（方法学独立），实测默认档(n_ref=1e17 m⁻³ @40 °C, T=60 °C) **rel=4.708e-08**（abs 2.349e10 · **tol=5e12**〔**绝对口径** · 对 |golden|≈4.99e17 即相对 1.0e-5 —— 同 B486「量级标定」先例〕⇒ **213×** 余量；残差链 3.013e-6 → 7.532e-7 → 1.883e-7 → 4.708e-8，**比值 4.00/4.00/4.00×** ⇒ **O(h²)**，与梯形标称阶一致）。🔴🔴 **非剖分守恒（关键区分）**：被积函数 ΔH/(k_B·T²) **随 T 变化**（非常数）⇒ 与 B28「均匀段 ΣΓ_i·Δz_i ≡ Γ·L **剖分守恒**」型代数恒等**不同**（n_seg=32 粗网格残差放大 ~64×，反向探针确证）⇒ **真数值残差**，非「同式异写」。🔴 **与 B473–B490 不同物理对象**：本锚是**气室热力学**（原子数密度），既不属腿 A 的固体自旋物理量、也不属腿 B 的超导磁通物理量 ⇒ 记新锚。🔴 **诚实规模**：QS-M9 另含「气室壁/缓冲气体/探测光弛豫率分量（定义式求和）」⇒ 闭式算术，归 `run_qs_m9_smoke` 覆盖、**不登记为锚**。⚠️ **诚实边界**：n_ref / T_ref / T / (ΔH/k_B) 为**设计示例量级**（常数汽化焓**模型**，真实 Rb 蒸气压有更精细的多项式拟合 ⇒ 本锚证明的是「闭式模型 ⇄ 数值积分」数值一致这一数学事实，**非**与实测蒸气压比对）；**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B493": {
        "title": "泵浦光 Beer–Lambert 透过率 T(L)（OPM 气室光路）：闭式指数 golden vs RK4 空间推进候选 · 无量纲",
        "metric": "qs_pump_transmission",
        "oracle": "closed_form(T(L)=T₀·exp(−n·σ_abs·L)，Beer–Lambert 吸收律) + RK4 空间推进独立_cross_check",
        "tol": 1e-7,
        "default_params": dict(B493_DEFAULT_PARAMS),
        "golden_fn": golden_b493,
        "candidate": "b493_pump_transmission_rk4_cand",
        "candidate_desc": "RK4 沿 z 数值积分 dI/dz=−n·σ_abs·I（n_steps=64 段，四阶 Runge–Kutta，不含闭式指数）⇒ 取 L 处透过率。方法学独立：golden=闭式指数，cand=数值空间推进",
        "note": "golden = QS-M9（OPM/SERF · 腿 C）的**泵浦光透过率**闭式：T(L)=T₀·exp(−n·σ_abs·L)（无量纲 · Beer–Lambert），光学厚度 τ_opt=n·σ_abs·L。🔴 **物理意义**：气室的**光路**物理 —— 光学厚度决定抽运均匀性与（探测/泵浦功率权衡的）信噪比 ⇒ 多物理场「光-几何」耦合；本锚把它钉进账本（缺口 G11）。candidate=**RK4 沿 z 数值积分**（方法学独立），实测默认档(T₀=1, n=1e19 m⁻³, σ_abs=5e-18 m², L=2 cm ⇒ τ_opt=1.0) **rel=5.032e-10**（abs 1.851e-10 · **tol=1e-7** ⇒ **199×** 余量；残差链 2.258e-6 → 1.340e-7 → 8.157e-9 → 5.032e-10，**比值 16.86/16.42/16.21×** ⇒ **O(h⁴)**）⇒ **非**代数恒等；τ_opt=1 时 T=1/e 恰为自洽点（smoke 覆盖）。🔴 **与 B452/B491 不同物理量**：B452 是 RC 阶跃电压、B491 是 2D 衰减振荡的横向极化；本锚是**光强沿传播方向的单调衰减（空间推进）**⇒ 被测标量（透过率）、构型（碱金属气室光吸收）、推进维（空间 z vs 时间 t）三处分歧 ⇒ 记新锚（先例 B452 vs B33）。🔴 **与 B462（Langmuir 吸附 RK4）不同体系**：本锚是**光抽运气室**的光吸收，非表面吸附平衡。🔴 **诚实规模**：QS-M9 另含「亥姆霍兹线圈 B(0)=(4/5)^{3/2}µ₀NI/R」（**闭式算术** ⇒ 属 smoke，**不登记为锚**；亦因此**无**「离散 Biot–Savart 线圈」锚 ⇒ 不与 B488 的离散 Neumann 互感撞车）。⚠️ **诚实边界**：T₀ / n / σ_abs / L 为**设计示例量级**（缓冲气体压致展宽后的有效截面），**非实测 PDK**；本锚只证明「闭式指数 ⇄ RK4 空间推进」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math）。",
    },
    "B494": {
        "title": "腔品质因子 Q=ω/κ（腔 QED 物理链）：闭式 Q=ω/κ golden vs RK4 能量衰减反解 κ 候选 · 无量纲",
        "metric": "qs_cavity_quality_factor",
        "oracle": "closed_form(Q=ω/κ，ω=2πc/λ) + RK4 能量衰减 dU/dt=−κU 反解 κ_cand=−ln(U(T))/T ⇒ Q_cand=ω/κ_cand 独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B494_DEFAULT_PARAMS),
        "golden_fn": golden_b494,
        "candidate": "b494_q_factor_rk4_cand",
        "candidate_desc": "RK4 时间推进能量衰减 dU/dt=−κU（U₀=1，n_steps=64 四阶 Runge–Kutta，不含闭式除式）⇒ 取 U(T) ⇒ 反解 κ_cand=−ln(U(T))/T ⇒ Q_cand=ω/κ_cand。方法学独立：golden=闭式除式，cand=数值 ODE 反解",
        "note": "golden = QS-M3c（腔 QED 物理链 · 平台缺口 G5 量子传感 PDK 腔几何）的**腔品质因子**闭式：Q=ω/κ（ω=2πc/λ 谐振角频率，κ 为能量衰减率）。🔴 **物理意义**：Q 衡量腔损耗 / 光子寿命 —— 高 Q 腔才能把发射体强耦合进谐振模式；本锚把「腔损耗 → Q」钉进账本（承 QS-M3 链④ Purcell 因子的腔几何拆分）。candidate=**RK4 时间推进能量衰减** dU/dt=−κU（方法学独立），实测默认档(ω=2πc/1550nm, Q=1e4, κ·t_observe≈1) **rel=5.011e-10**（abs 5.011e-6 · **tol=1e-3**〔按量级标定 · 同 B491/B493 约定〕⇒ **200×** 余量；残差链 2.248e-6 → 1.334e-7 → 8.122e-9 → 5.011e-10，**比值 16.86/16.42/16.21×** ⇒ **O(h⁴)** ⇒ **非**代数恒等）。🔴 **与 B18 不同物理量**：B18 是**谐振腔 Purcell 因子 F_P=4g²/(κγ₁)**（**组合标量**）；本锚是 **Q 这一输入量本身**（F_P 由 Q/V/g 决定，但 Q ≠ F_P）⇒ 物理对象不同 ⇒ 记新锚（先例 B491 vs B475：同物理域不同标量即分立）。🔴 **诚实规模**：QS-M3c 另含「finesse ℱ=Q·λ/(2na)」「γ_rad=ω³μ²/(3πε₀ħc³)」「cooperativity C=4g²/(κγ_rad)=(3λ³Q/4π²V)(γ_rad/γ₁)」「Purcell FOM F_P=(3/4π²)(λ/n)³(Q/V)」—— 前二者为**闭式算术 / 组合自洽**，后二者**约定因子 2n 的闭式自洽** ⇒ 均归 `run_qs_m3c_smoke` 覆盖，**如实不登记为锚**（本批只 B494–B496 三锚 · 同 B-44~B-47 纪律：宁可少，不越级谎报）。⚠️ **诚实边界**：ω/κ 为**设计示例量级**（金刚石微盘腔 telecom 典型），**非实测 PDK**；本锚只证明「闭式 Q=ω/κ ⇄ RK4 能量衰减反解」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B495": {
        "title": "有效模体积 V_eff（腔 QED 物理链）：闭式 A·8a/15 golden vs 单波腹腔模包络中点求积候选 · m³",
        "metric": "qs_effective_mode_volume",
        "oracle": "closed_form(V_eff=A·∫(1−4x²/a²)²dx=A·8a/15) + 中点求积 ∫_{-a/2}^{a/2}(1−4x²/a²)²dx 独立_cross_check",
        "tol": 1e-27,
        "default_params": dict(B495_DEFAULT_PARAMS),
        "golden_fn": golden_b495,
        "candidate": "b495_mode_volume_midpoint_cand",
        "candidate_desc": "中点求积 ∫_{-a/2}^{a/2}(1−4x²/a²)²dx（n_seg=256 段，不含闭式积分）⇒ ×A。方法学独立：golden=解析积分，cand=数值求积",
        "note": "golden = QS-M3c（腔 QED 物理链 · 平台缺口 G5）的**有效模体积**闭式：V_eff=∫ε|E|²dV/max(ε|E|²)；取单波腹腔模包络 E(x)=E₀(1−4x²/a²)（x∈[−a/2,a/2]，中心单极大、边界归零）⇒ V_eff=A·8a/15（∫_{-a/2}^{a/2}(1−4x²/a²)²dx=8a/15）。🔴 **物理意义**：V_eff 衡量模式场空间局域程度 —— V_eff 越小耦合越强，是腔 QED 耦合 g 与 Purcell 因子 F_P 的核心几何量；本锚把它钉进账本。candidate=**中点求积**（方法学独立），实测默认档(a=1.55µm, A=5e-14 m²) **rel=2.037e-10**（abs 8.421e-30 · **tol=1e-27**〔**绝对口径 · 对 |golden|≈4.13e-20 即相对 2.04e-10 —— 同 B492/B494 量级标定先例**〕⇒ **118×** 余量；残差链 8.345e-7 → 5.215e-8 → 3.260e-9 → 2.037e-10，**比值 16.00×** ⇒ **O(h⁴)**（偶函数在对称区间中点法额外加速），被积函数是四次非多项式 ⇒ 中点非精确 ⇒ **真数值残差**，非「同式异写」/ 非机器零残差）。🔴 **与 B18 不同物理量**：B18 是 Purcell 组合标量；本锚是 **V_eff 这一输入量** ⇒ 物理对象不同 ⇒ 记新锚。🔴 **诚实规模**：V_eff 量级极小（~1e-20 m³），tol 取**绝对口径** 1e-27（绝不同用 O(1) 相对量当绝对 tol，血案 B492：同族量级标定）。⚠️ **诚实边界**：a/A 为**设计示例量级**（金刚石微盘腔典型），**非实测 PDK**；本锚只证明「闭式积分 ⇄ 中点求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B496": {
        "title": "单光子耦合 g=(μ/ħ)√(ħω/(εV_eff))（腔 QED 物理链）：闭式 golden vs 数值场能积分候选 · Hz",
        "metric": "qs_single_photon_coupling",
        "oracle": "closed_form(g=(μ/ħ)·√(ħω/(ε·V_eff))，V_eff=A·8a/15) + 数值 ∫|E|²dV（⇒ 数值 V_eff）独立_cross_check",
        "tol": 1e3,
        "default_params": dict(B496_DEFAULT_PARAMS),
        "golden_fn": golden_b496,
        "candidate": "b496_coupling_field_energy_cand",
        "candidate_desc": "数值积分 ∫|E|²dV（中点求积 ⇒ 数值 V_eff_num）⇒ 单光子场幅 E₀=√(ħω/(ε·V_eff_num)) ⇒ g=μE₀/ħ。方法学独立：golden=闭式 V_eff，cand=数值场能积分",
        "note": "golden = QS-M3c（腔 QED 物理链 · 平台缺口 G5）的**单光子耦合**闭式：g=(μ/ħ)·√(ħω/(ε·V_eff))（μ=跃迁偶极矩，E₀=√(ħω/(εV_eff)) 为单光子场幅，V_eff=A·8a/15）。🔴 **物理意义**：g 是发射体偶极与腔模场幅的耦合强度（单光子 Rabi 频率），强耦合判据 g>κ,γ；本锚把它钉进账本（与单锚 B48 = 单光子 Rabi 耦合同物理族，但本锚是**腔 QED 组合链**的可证伪数值实现 —— 经独立数值场能积分验证，非直接引用）。candidate=**数值积分 ∫|E|²dV**（方法学独立），实测默认档(μ=1e-29 C·m, ω=2πc/1550nm, ε=ε₀·3.4², a=1.55µm, A=5e-14 m²) **rel=1.019e-10**（abs 1.681 Hz · **tol=1e3**〔按量级标定〕⇒ **595×** 余量；残差链 4.172e-7 → 2.608e-8 → 1.630e-9 → 1.019e-10，**比值 16.00×** ⇒ **O(h⁴)**；g ∝ V_eff^(−1/2)，残差随 V_eff 积分残差）⇒ **非**代数恒等。🔴 **与 B18 不同物理量**：B18 是 Purcell 组合标量 F_P=4g²/(κγ₁)；本锚是 **g 这一输入量** ⇒ 物理对象不同 ⇒ 记新锚。🔴 **与 B48（单锚）不同实现**：B48 是量子力学单光子 Rabi 耦合的闭式/数值对；本锚是**腔 QED 组合链**（g 由腔模场能导出），命名上以连字符 `_batch_qs_m3c_numeric` / `b494_/b495_/b496_` 规避 B-48 与单锚 B48 号段撞名（实 grep 核验：`_BATCH_QS_M3C` / `_get_qs_m3c_numeric` / `b48_` 全仓占用检查已做）。⚠️ **诚实边界**：μ/ω/ε/a/A 为**设计示例量级**（金刚石微盘腔 telecom 典型），**非实测 PDK**；本锚只证明「闭式 g ⇄ 数值场能积分」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B497": {
        "title": "表面码逻辑错误阈值距离 d*（量子纠错 QEC · M0 阈值标度）：闭式反解 golden vs 二分根求解候选 · 无量纲",
        "metric": "qec_threshold_distance",
        "oracle": "closed_form(d*=2·log(target/A)/log(p_phys/p_th)−1) + 二分根求解 f(d)=A·(p_phys/p_th)^((d+1)/2)−target=0 独立_cross_check",
        "tol": 1e-6,
        "default_params": dict(B497_DEFAULT_PARAMS),
        "golden_fn": golden_b497,
        "candidate": "b497_threshold_distance_bisect_cand",
        "candidate_desc": "二分根求解 f(d)=0 于 [3,121]（n_steps=35 步取中点，不含闭式对数反解）⇒ d*。方法学独立：golden=闭式反解，cand=通用根求解器（二分）",
        "note": "golden = 量子纠错征程 J1（M0 阈值标度）的**表面码逻辑错误阈值距离**闭式：由标度律 p_L(d,p)=A·(p/p_th)^((d+1)/2) ≤ target 反解 d*=2·log(target/A)/log(p_phys/p_th)−1。🔴 **物理意义**：表面码阈值 p_th≈1% 以下，逻辑错误率随距离 d 指数下降；达到容错预算目标逻辑错误率所需的最小距离 d* 是容错架构的核心标量。本锚把「阈值标度律 ⇄ 通用二分根求解器」钉进账本（承 J1 蓝图 M0 阈值标度）。candidate=**二分根求解**（方法学独立），实测默认档(p_phys=5e-3, target=1e-15, p_th=0.01, A=0.03 ⇒ golden≈88.54) **rel=1.468e-11**（abs 1.300e-9 · **tol=1e-6**〔**绝对口径·对 |golden|≈88.54 即相对 1.47e-11**〕⇒ **769×** 余量；残差链 5.383e-10 → 7.286e-11 → 3.407e-11 → 1.468e-11，**比值 7.39/2.14/2.32×** ⇒ 二分区间每步折半 ⇒ 残差严格单调、且 **非**机器零残差 ⇒ **非**代数恒等）。🔴 **与 B494–B496 不同物理量**：本锚是表面码阈值标度（量子纠错 QEC 征程），QS 三锚是腔 QED 物理量 ⇒ 零占用新族（实 grep 核验：`surface|阈值|标度|解码|syndrome|matching|Union` 在 `lda_harness/` 内仅本批命中）。⚠️ **诚实边界**：p_th=1% / A=0.03 / target=1e-15 为**公认/设计示例量级**（rotated surface code 典型阈值的文献值、标度前因子为设计示例），**非实测 PDK**；本锚只证明「闭式反解 ⇄ 二分根求解」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B498": {
        "title": "解码器综合症状概率场总权重（量子纠错 QEC · M1 解码器）：闭式 erf golden vs 二维梯形求积候选 · 无量纲",
        "metric": "qec_syndrome_field_weight",
        "oracle": "closed_form(∫₀ᵈ∫₀ᵈ exp(−((x−cx)²+(y−cy)²)/(2σ²))dxdy=σ²(π/2)[erf((d−cx)/(σ√2))−erf(−cx/(σ√2))]²) + 二维梯形求积 独立_cross_check",
        "tol": 1e-2,
        "default_params": dict(B498_DEFAULT_PARAMS),
        "golden_fn": golden_b498,
        "candidate": "b498_syndrome_field_trapz_cand",
        "candidate_desc": "二维梯形求积（N×N=1024² 均匀网格，不含 erf 闭式）⇒ ∫∫exp(...)dxdy。方法学独立：golden=erf 闭式，cand=数值求积",
        "note": "golden = 量子纠错征程 J1（M1 解码器信念传播前置量）的**解码器综合症状概率场总权重**闭式：∫₀ᵈ∫₀ᵈ exp(−((x−cx)²+(y−cy)²)/(2σ²))dxdy = σ²(π/2)[erf((d−cx)/(σ√2))−erf(−cx/(σ√2))]²（二维分解）。🔴 **物理意义**：Union-Find / MWPM 解码器的信念传播依赖每个数据比特的错误概率场；其全片积分（综合症状权重）是解码置信度的归一化量。本锚把它钉进账本（承 J1 蓝图 M1 解码器）。candidate=**二维梯形求积**（方法学独立），实测默认档(d=5, σ=1, cx=cy=2.5 ⇒ golden≈6.128) **rel=1.763e-07**（abs 1.080e-6 · **tol=1e-2**〔**绝对口径·对 |golden|≈6.128 即相对 1.76e-7**〕⇒ **9255×** 余量；残差链 1.128e-5 → 2.821e-6 → 7.053e-7 → 1.763e-7，**比值 4.00×** ⇒ **O(h²)**（高斯光滑被积函数梯形收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B497 不同物理量**：B497 是阈值标度距离（一维标度），本锚是解码器二维概率场积分 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：d/σ/cx/cy 为**设计示例量级**（rotated surface code d=5 码片典型），**非实测 PDK**；本锚只证明「erf 闭式 ⇄ 二维梯形求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B499": {
        "title": "解码器匹配代价二阶矩（量子纠错 QEC · M1 解码器）：闭式 L²/3 golden vs 一维梯形求积候选 · 无量纲",
        "metric": "qec_match_cost_moment",
        "oracle": "closed_form(∫₀ᴸ x²·(1/L)dx=L²/3) + 一维梯形求积 独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B499_DEFAULT_PARAMS),
        "golden_fn": golden_b499,
        "candidate": "b499_match_cost_moment_trapz_cand",
        "candidate_desc": "一维梯形求积（N=1024 点，不含多项式闭式）⇒ ∫₀ᴸ x²dx/L。方法学独立：golden=多项式闭式，cand=数值求积",
        "note": "golden = 量子纠错征程 J1（M1 解码器代价分布）的**解码器匹配代价二阶矩**闭式：缺陷均匀分布于 [0,L]，代价 cost(x)=x 的二阶矩 ∫₀ᴸ x²·(1/L)dx = L²/3。🔴 **物理意义**：解码器最小权匹配的总代价随缺陷位置分布成随机变量；其二阶矩（方差尺度）量化解码不确定度。本锚把它钉进账本（承 J1 蓝图 M1 解码器）。candidate=**一维梯形求积**（方法学独立），实测默认档(L=5 ⇒ golden≈8.333) **rel=2.384e-07**（abs 1.987e-6 · **tol=1e-3**〔**绝对口径·对 |golden|≈8.333 即相对 2.38e-7**〕⇒ **503×** 余量；残差链 1.526e-5 → 3.815e-6 → 9.537e-7 → 2.384e-7，**比值 4.00×** ⇒ **O(h²)**（x² 光滑被积函数梯形收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B497/B498 不同物理量**：B497 是阈值标度、B498 是二维概率场；本锚是解码器一维代价矩 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：L=5 为**设计示例量级**（缺陷均匀分布于码片边长量级），**非实测 PDK**；本锚只证明「多项式闭式 ⇄ 一维梯形求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B500": {
        "title": "旗比特钩错检测概率 P(φ>φ_th)（量子纠错 QEC · M2 综合征提取）：erfc 闭式 golden vs 高斯尾一维梯形求积候选 · 无量纲",
        "metric": "qec_flag_hook_detection",
        "oracle": "closed_form(½·erfc(φ_th/(σ√2))) + 高斯尾一维梯形求积 ∫_{φ_th}^{φ_th+6σ} (1/(σ√(2π)))e^{−φ²/2σ²}dφ 独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B500_DEFAULT_PARAMS),
        "golden_fn": golden_b500,
        "candidate": "b500_flag_hook_erfc_trapz_cand",
        "candidate_desc": "高斯尾一维梯形求积（[φ_th,φ_th+6σ] 上 n=65536 点，不含 erfc 闭式）⇒ ∫pdf dφ。方法学独立：golden=erfc 闭式，cand=数值求积",
        "note": "golden = 量子纠错征程 J1（M2 综合征提取）的**旗比特钩错检测概率**闭式：P(钩相 φ>φ_th)=½·erfc(φ_th/(σ√2))（φ~N(0,σ²) 越阈概率）。🔴 **物理意义**：flag qubit 用于检测晶格手术中测量钩错（hook error）；其越阈概率量化了旗比特告警灵敏度。本锚把它钉进账本（承 J1 蓝图 M2 综合征提取 / 旗比特钩错检测）。candidate=**高斯尾一维梯形求积**（方法学独立），实测默认档(φ_th=2.0, σ=1.0 ⇒ golden≈2.275e-2) **rel=1.658e-09**（abs 3.771e-11 · **tol=1e-3**〔**绝对口径·对 |golden|≈2.275e-2 即相对 1.66e-9**〕⇒ **2.65e7×** 余量；残差链 6.790e-6 → 4.244e-7 → 2.652e-8 → 1.658e-9，**比值 16.00×** ⇒ **O(h²)**（高斯尾光滑被积函数梯形收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B497–B499 不同物理量**：B497 阈值标度 / B498 二维概率场 / B499 一维代价矩；本锚是旗比特钩错越阈概率 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：φ_th=2σ / σ=1.0 为**设计示例量级**（flag qubit 阈值设定的典型值），**非实测 PDK**；本锚只证明「erfc 闭式 ⇄ 高斯尾梯形求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B501": {
        "title": "相邻稳定子综合征关联 ∫₀ᵈ∫₀ᵈ g(x,y)g(x+r,y)dxdy（量子纠错 QEC · M2 综合征提取）：erf² 高斯积闭式 golden vs 二维梯形求积候选 · 无量纲",
        "metric": "qec_adjacent_syndrome_correlation",
        "oracle": "closed_form((πσ²/4)e^{−r²/4σ²}[erf((d−cy)/σ)−erf(−cy/σ)][erf((d−cx+r/2)/σ)−erf(−(cx−r/2)/σ)]) + 二维梯形求积 独立_cross_check",
        "tol": 1e-2,
        "default_params": dict(B501_DEFAULT_PARAMS),
        "golden_fn": golden_b501,
        "candidate": "b501_adjacent_syndrome_2d_trapz_cand",
        "candidate_desc": "二维梯形求积（N×N=512² 均匀网格，不含 erf 闭式）⇒ ∫∫g(x,y)g(x+r,y)dxdy。方法学独立：golden=erf 高斯积闭式，cand=数值求积",
        "note": "golden = 量子纠错征程 J1（M2 综合征提取）的**相邻稳定子综合征关联**闭式：∫₀ᵈ∫₀ᵈ (1/(2πσ²))e^{−((x−cx)²+(y−cy)²)/2σ²}·e^{−((x+r−cx)²+(y−cy)²)/2σ²}dxdy = (πσ²/4)e^{−r²/4σ²}[erf((d−cy)/σ)−erf(−cy/σ)][erf((d−cx+r/2)/σ)−erf(−(cx−r/2)/σ)]（高斯积可分解）。🔴 **物理意义**：相邻测量圆的综合征读出相互关联（串扰/邻近效应），解码器需据此修正相关错误；其积分量化解码的输入相关结构。本锚把它钉进账本（承 J1 蓝图 M2 综合征提取 / 相邻稳定子关联）。candidate=**二维梯形求积**（方法学独立），实测默认档(d=5, σ=1, cx=cy=2.5, r=1 ⇒ golden≈2.440) **rel=2.096e-07**（abs 5.114e-7 · **tol=1e-2**〔**绝对口径·对 |golden|≈2.440 即相对 2.10e-7**〕⇒ **1.96e4×** 余量；残差链 1.339e-5 → 3.352e-6 → 8.383e-7 → 2.096e-7，**比值 4.00×** ⇒ **O(h²)**（高斯光滑被积函数梯形收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B498 不同物理量**：B498 是单稳定子二维概率场；本锚是**两相邻稳定子关联**（含位移 r）⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：d/σ/cx/cy/r 为**设计示例量级**（码片典型几何），**非实测 PDK**；本锚只证明「erf 高斯积闭式 ⇄ 二维梯形求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B502": {
        "title": "transversal CNOT 保真预算链 F=exp(−∫率)（量子纠错 QEC · M3 容错逻辑门）：积分 exp 闭式 golden vs 一维中点求积候选 · 无量纲",
        "metric": "qec_transversal_cnot_fidelity",
        "oracle": "closed_form(F=exp(−p₀(T+αT²/2+βT³/3))) + 一维中点求积 ∫₀ᵀ p₀(1+αt+βt²)dt 独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B502_DEFAULT_PARAMS),
        "golden_fn": golden_b502,
        "candidate": "b502_transversal_fid_trapz_cand",
        "candidate_desc": "一维中点求积（n=1024 点，不含指数积分闭式）⇒ ∫₀ᵀ p₀(1+αt+βt²)dt 后取 exp。方法学独立：golden=exp 积分闭式，cand=数值积分",
        "note": "golden = 量子纠错征程 J1（M3 容错逻辑门）的**transversal CNOT 保真预算链**闭式：时间依赖错误率 p(t)=p₀(1+αt+βt²)（工艺老化/温漂二次项）⇒ F=exp(−∫₀ᵀ p(t)dt)=exp(−p₀(T+αT²/2+βT³/3))。🔴 **物理意义**：transversal CNOT 是容错逻辑门实现方式之一；其保真度随运行时长与温漂累积衰减，预算链量化该衰减。本锚把它钉进账本（承 J1 蓝图 M3 容错逻辑门 / transversal CNOT 保真预算）。candidate=**一维中点求积后 exp**（方法学独立），实测默认档(p₀=0.01, α=0.1, β=0.1, T=10 ⇒ golden≈6.167e-1) **rel=7.947e-08**（abs 4.901e-8 · **tol=1e-3**〔**绝对口径·对 |golden|≈6.167e-1 即相对 7.95e-8**〕⇒ **2.04e4×** 余量；残差链 5.086e-6 → 1.272e-6 → 3.179e-7 → 7.947e-8，**比值 4.00×** ⇒ **O(h²)**（二次 integrand 中点求积收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B503/B504 不同物理量**：B503 是合并保真、B504 是端到端累计失效；本锚是 transversal 门保真 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：p₀/α/β/T 为**设计示例量级**（transversal 门错误率预算的典型量级），**非实测 PDK**；本锚只证明「指数积分闭式 ⇄ 一维中点求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B503": {
        "title": "lattice surgery 合并保真 F=exp(−c·p·∫(2x²−1)dx)（量子纠错 QEC · M3 容错逻辑门）：积分 exp 闭式 golden vs 一维中点求积候选 · 无量纲",
        "metric": "qec_lattice_surgery_merge_fidelity",
        "oracle": "closed_form(F=exp(−c·p·(2d³/3−d))) + 一维中点求积 ∫₀ᵈ c(2x²−1)p dx 独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B503_DEFAULT_PARAMS),
        "golden_fn": golden_b503,
        "candidate": "b503_merge_fid_trapz_cand",
        "candidate_desc": "一维中点求积（n=1024 点，不含积分闭式）⇒ ∫₀ᵈ c(2x²−1)p dx 后取 exp。方法学独立：golden=exp 积分闭式，cand=数值积分",
        "note": "golden = 量子纠错征程 J1（M3 容错逻辑门）的**lattice surgery 合并保真**闭式：合并两枚逻辑块时资源随 patch 尺寸 x 累积（x:1→d），率 c(2x²−1)p ⇒ F=exp(−c·p·∫₀ᵈ(2x²−1)dx)=exp(−c·p·(2d³/3−d))。🔴 **物理意义**：lattice surgery 把两枚逻辑块合并为更大逻辑块，合并期间错误随 patch 尺寸积分累积；该保真量化合并可靠性。本锚把它钉进账本（承 J1 蓝图 M3 容错逻辑门 / lattice surgery 合并）。candidate=**一维中点求积后 exp**（方法学独立），实测默认档(c=0.01, p=0.01, d=5 ⇒ golden≈9.922e-1) **rel=1.987e-09**（abs 1.971e-9 · **tol=1e-3**〔**绝对口径·对 |golden|≈9.922e-1 即相对 1.99e-9**〕⇒ **5.07e5×** 余量；残差链 1.272e-7 → 3.179e-8 → 7.947e-9 → 1.987e-9，**比值 4.00×** ⇒ **O(h²)**（二次 integrand 中点求积收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B502 不同物理量**：B502 是 transversal 门保真；本锚是 lattice surgery 合并保真 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：c/p/d 为**设计示例量级**（合并操作的错误预算典型值），**非实测 PDK**；本锚只证明「指数积分闭式 ⇄ 一维中点求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B504": {
        "title": "端到端累计逻辑失效 P=1−exp(−∫率)（量子纠错 QEC · M4 端到端收官）：积分 1−exp 闭式 golden vs 一维中点求积候选 · 无量纲",
        "metric": "qec_end_to_end_accumulated_failure",
        "oracle": "closed_form(P=1−exp(−λ(T+βT²/2+γT³/3))) + 一维中点求积 ∫₀ᵀ λ(1+βt+γt²)dt 独立_cross_check",
        "tol": 1e-3,
        "default_params": dict(B504_DEFAULT_PARAMS),
        "golden_fn": golden_b504,
        "candidate": "b504_accumulated_fail_trapz_cand",
        "candidate_desc": "一维中点求积（n=1024 点，不含积分闭式）⇒ ∫₀ᵀ λ(1+βt+γt²)dt 后取 1−exp。方法学独立：golden=1−exp 积分闭式，cand=数值积分",
        "note": "golden = 量子纠错征程 J1（M4 端到端收官）的**端到端累计逻辑失效**闭式：运行期间逻辑失效率 λ(1+βt+γt²) 累积 ⇒ P=1−exp(−∫₀ᵀ λ(1+βt+γt²)dt)=1−exp(−λ(T+βT²/2+γT³/3))。🔴 **物理意义**：端到端逻辑错误随运行时间累积，是「逻辑错误率 p_L ≪ 阈值」的最终工程判据；本锚量化长时间运行的累计失效概率。本锚把它钉进账本（承 J1 蓝图 M4 端到端收官 / 累计逻辑失效）。candidate=**一维中点求积后 1−exp**（方法学独立），实测默认档(λ=1e-3, β=0.1, γ=0.001, T=100 ⇒ golden≈6.068e-1) **rel=5.151e-08**（abs 3.125e-8 · **tol=1e-3**〔**绝对口径·对 |golden|≈6.068e-1 即相对 5.15e-8**〕⇒ **3.20e4×** 余量；残差链 3.296e-6 → 8.241e-7 → 2.060e-7 → 5.151e-8，**比值 4.00×** ⇒ **O(h²)**（二次 integrand 中点求积收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B502/B503 不同物理量**：B502 是 transversal 门、B503 是合并；本锚是端到端累计失效 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：λ/β/γ/T 为**设计示例量级**（端到端运行失效预算典型值），**非实测 PDK**；本锚只证明「1−exp 积分闭式 ⇄ 一维中点求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
    "B505": {
        "title": "累计逻辑错误面积 ∫₀ᴸ(1−e^{−kx})dx=L−(1−e^{−kL})/k（量子纠错 QEC · M4 端到端收官）：初等闭式 golden vs 一维梯形求积候选 · 无量纲",
        "metric": "qec_logical_error_area",
        "oracle": "closed_form(L−(1−e^{−kL})/k) + 一维梯形求积 ∫₀ᴸ(1−e^{−kx})dx 独立_cross_check",
        "tol": 1e-2,
        "default_params": dict(B505_DEFAULT_PARAMS),
        "golden_fn": golden_b505,
        "candidate": "b505_logical_area_trapz_cand",
        "candidate_desc": "一维梯形求积（n=1024 点，不含初等闭式）⇒ ∫₀ᴸ(1−e^{−kx})dx。方法学独立：golden=初等闭式，cand=数值积分",
        "note": "golden = 量子纠错征程 J1（M4 端到端收官）的**累计逻辑错误面积**闭式：沿码链长 L 的累积错误 ∫₀ᴸ(1−e^{−kx})dx=L−(1−e^{−kL})/k。🔴 **物理意义**：把逻辑错误在物理链长上的累积量化为「面积」，是端到端规模标度的几何判据（逻辑错误面积须低于裸标度界）。本锚把它钉进账本（承 J1 蓝图 M4 端到端收官 / 累计逻辑错误面积）。candidate=**一维梯形求积**（方法学独立），实测默认档(k=0.01, L=100 ⇒ golden≈3.679e+1) **rel=6.828e-08**（abs 2.512e-6 · **tol=1e-2**〔**绝对口径·对 |golden|≈3.679e+1 即相对 6.83e-8**〕⇒ **3.98e3×** 余量；残差链 4.370e-6 → 1.092e-6 → 2.731e-7 → 6.828e-8，**比值 4.00×** ⇒ **O(h²)**（指数被积函数梯形收敛），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **与 B504 不同物理量**：B504 是时间累计失效概率；本锚是空间（链长）累计错误面积 ⇒ 物理对象不同 ⇒ 记新锚。⚠️ **诚实边界**：k/L 为**设计示例量级**（逻辑错误沿链衰减的典型尺度），**非实测 PDK**；本锚只证明「初等闭式 ⇄ 一维梯形求积」数值一致这一数学事实，**不得作制造/性能宣称**。零商业依赖（纯 math）。",
    },
}
