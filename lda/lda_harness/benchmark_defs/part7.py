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
          B484（QS-M5 衍生：AC 灵敏度带宽折算 η_AC —— 动态范围/读出）。
分类（诚实）：**B473 = 严格独立**（`candidate` 指向 `_batch_b39_numeric` 注册的
  数值误差传播链候选；实测 rel≈2.4e-5，非代数恒等）。
  **B478–B481 = 严格独立**（`candidate` 指向 `_batch_b43_numeric` 注册的
  点偶极场数值积分 / MC 噪声功率叠加 / 含噪样本 LSQ 斜率比 / MC 两点差分标准差
  候选；实测 rel 4.7e-9 / 1.9e-6 / 4.2e-5 / 1.0e-4，**均 ≫ 机器精度，非代数恒等**）。
  **B482–B484 = 严格独立**（`candidate` 指向 `_batch_b44_numeric` 注册的
  FID 数值线型中心差分斜率 / 全跨多点 LSQ 标度 / MC 带限噪声 rms 候选；
  实测 rel 6.7e-6 / 3.4e-8 / 2.1e-4，**均 ≫ 机器精度，非代数恒等**）。

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
}
