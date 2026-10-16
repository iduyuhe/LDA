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
          B493（QS-M9 衍生：泵浦光 Beer–Lambert 透过率 T(L) —— OPM 气室光路）
          B506（J2 超导 Transmon · M2 衍生：两比特 CR 门退相干错误率 —— 张量 A+D 信道闭式 ⇄ 16×16 Liouvillian RK4）
          B507（J2 超导 Transmon · M2 衍生：残余 ZZ 诱导门错误率 —— 闭式 (4/5)sin²(ζt/2) ⇄ 矩阵传播子 RK4）。
          B508（J2 超导 Transmon · M3 衍生：FDM 多音读出相邻通道频谱重叠串扰比 —— 闭式洛伦兹自相关 4γ²/(4γ²+δ²) ⇄ sinh 换元 + 复合 Simpson 数值卷积）。
          B509（J2 超导 Transmon · M4 衍生：QPU 耦合图代数连通度 λ₂（Fiedler 值）—— 谱定理闭式 2−2cos(π/max(rows,cols)) ⇄ 嵌套 Krylov 子空间 Rayleigh–Ritz 最小值）。
          B510（J3 量子测控与读出 · M0 衍生：广义 Rabi 时域布居 —— 解析闭式 (Ω²/Ω_R²)sin²(Ω_R t/2) ⇄ 时域 TDSE 四阶 RK4）。
          B511（J3 量子测控与读出 · M1 衍生：三能级 transmon 驱动泄漏布居 —— depressed-cubic 三角法精确谱闭式 ⇄ 时域 RK4）。
          B512（J3 量子测控与读出 · M2 衍生：去极化信道纯度衰减 unitarity —— 解析指数闭式 (1+e^{−2Γt})/2 ⇄ 密度矩阵 Liouvillian RK4）。
          B513（J3 量子测控与读出 · M3 衍生：Purcell 滤波器抑制比 —— ABCD 代数闭式 1/|S21|² ⇄ 导纳 ODE 四阶 RK4 数值积分）。
          B514（J3 量子测控与读出 · M4 衍生：分布式相位不敏感放大链附加噪声（Caves 极限）—— 解析闭式 (η/g)(1−e^{−gL}) ⇄ 复合 Simpson 求积）。
          B515（J4 量子传感系统集成 · M0 衍生：多参数 NV 传感交叉灵敏度解耦温度分量 τ̂ —— Cramer 闭式解析反演 ⇄ Landweber 迭代解耦）。
          B518（J4 量子传感系统集成 · M3 衍生：低温布线束热负载 —— Wiedemann–Franz 电子热导有理闭式 ⇄ RK4 积分定义 ODE）。
          B519（J5 量子网络与接口 · M0 衍生：分发后两体纠缠保真度 —— Werner 族解析闭式 (1+3p)/4 ⇄ 4×4 密度矩阵距离步进 RK4）。
          B520（J5 量子网络与接口 · M1 衍生：光子不可分辨性 → HOM 干涉可见度 —— 高斯波包重叠解析闭式 ⇄ 复合梯形时间域数值积分）。
          B521（J5 量子网络与接口 · M2 衍生：中继站期望交换产出数 —— 生成窗 ⊗ 存储窗 嵌套卷积初等闭式 ⇄ 单重复合 Simpson 求积）。
          B522（J5 量子网络与接口 · M3 衍生：微波-光换能效率 —— 协同度极限 × 有限探测带侧带重叠 分层 log+arctan 闭式 ⇄ 有限窗复合 Simpson 求积）。
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
  **B510/B511 = 严格独立**（`candidate` 指向 `_batch_j3_numeric` 注册的
  时域 TDSE 四阶 RK4 态矢推进候选；实测残差 2.092e-09（tol 1e-6 的 478×）/ 1.030e-08
  （tol 1e-5 的 971×），残差链比值收敛至 ~16 ⇒ 准 O(h⁴)，**均 ≫ 机器精度，非代数恒等**）。
  **B512–B514 = 严格独立**（`candidate` 指向 `_batch_j3_numeric` 注册的密度矩阵 Liouvillian
  RK4 / 导纳 ODE RK4 / 复合 Simpson 求积候选；实测残差 2.988e-10（tol 1e-7 的 335×）/
  4.652e-09（tol 1e-6 的 215×）/ 4.015e-10（tol 1e-6 的 2491×），残差链比值收敛至 ~16
  ⇒ 准 O(h⁴)，动态范围均 >6e4×，**均 ≫ 机器精度，非代数恒等**）。
  **B515 = 严格独立**（`candidate` 指向 `_batch_j4_numeric` 注册的 **Landweber 迭代解耦**候选；
  实测残差 6.634e-09（tol 1e-6 的 150.7×），残差链 n=64→1.217e-02 … n=320→6.634e-09
  比值**恒定 ~36.82×**（等差扫描格 Δk=64 ⇒ 几何收敛 ρ^{−64}，与 Landweber 标称收敛率一致），
  动态范围 1.83e6×，**≫ 机器精度，非代数恒等**）。
  **B518 = 严格独立**（`candidate` 指向 `_batch_j4_numeric` 注册的 **RK4 积分定义 ODE**候选；
  实测残差 3.213e-11（tol 1e-8 的 311.2×），残差链 n=32→1.019e-06 … n=512→3.213e-11
  比值 10.15/13.21/15.03/15.73× ⇒ 趋向 **O(h⁴)**〔RK4 标称阶〕，动态范围 3.17e4×，
  **≫ 机器精度，非代数恒等**）。
  **B519 = 严格独立**（`candidate` 指向 `_batch_j5_numeric` 注册的 **4×4 密度矩阵距离步进 RK4**候选；
  实测残差 3.042e-11（tol 1e-8 的 328.7×），残差链 n=16→2.491e-06 … n=256→3.042e-11
  比值 18.02/16.98/16.48/16.24× ⇒ 趋向 **O(h⁴)**〔RK4 标称阶〕，动态范围 8.19e4×，
  **≫ 机器精度，非代数恒等**）。
  **B520 = 严格独立**（`candidate` 指向 `_batch_j5_numeric` 注册的 **复合梯形时间域数值积分**候选；
  实测残差 1.0451e-11（tol 3e-9 的 287.1×），残差链 n=8→2.709e-01 → 12→2.450e-02 → 16→7.645e-04
  → 20→6.735e-06 → 24→1.611e-08 → **28→1.045e-11**，比值 11.06/32.05/113.51/418.02/1541.59×
  ⇒ **超几何收敛**（高斯×振荡被积函数的解析性所致、**非幂律**，如实登记不假称「恰 4」；
  同 B453 截断型先例），动态范围 **2.59e10×**，**≫ 机器精度，非代数恒等**）。
  **B521 = 严格独立**（`candidate` 指向 `_batch_j5_numeric` 注册的**单重复合 Simpson 求积**候选；
  实测残差 4.1157e-10（tol 1e-7 的 **243.0×**），残差链 n=8→4.1444e-04 → 16→2.6700e-05 →
  32→1.6815e-06 → 64→1.0530e-07 → 128→6.5843e-09 → **256→4.1157e-10**，
  比值 15.52/15.88/15.97/15.99/16.00× ⇒ 从**下方**趋近 **O(h⁴)**〔复合 Simpson 标称阶〕，
  动态范围 **1.007e6×**，**≫ 机器精度，非代数恒等**）。
  **B522 = 严格独立**（`candidate` 指向 `_batch_j5_numeric` 注册的**有限窗内复合 Simpson 求积**候选；
  实测残差 6.7050e-11（tol 1e-7 的 **1491.4×**），残差链 n=8→3.7736e-06 → 16→2.6338e-07 →
  32→1.6989e-08 → 64→1.0706e-09 → **128→6.7050e-11**，比值 **14.33/15.50/15.87/15.97×**
  ⇒ 从**下方**趋近 **O(h⁴)**〔复合 Simpson 标称阶，粗端未入渐近区故略低于 16，如实登记不假称「恰 16」〕，
  动态范围 **5.628e4×**，**≫ 机器精度，非代数恒等**；🔴 另证**双独立闭式互证**
  （分层 log+arctan ⇄ 复留数+复对数，相对差 **1.51e-15**）。
  **B473–B522 全片 = 严格独立**（本片无自证桩、无降级锚；J4 的 M1/M2 两档**锚净增 0**——
  候选物理量（Voigt 线型 / 气室数密度 / 透过率 / 1/S21 隔离度 / 耦合模 / 串扰劣化倍率）
  经实 grep 逐条被既有锚占用，见 `lda_l2/qs_j4_{microcell,integration}.py` 的避让表；
  J5 的 M2 **亦有两条候选锚净增 0**（交换后保真递推 = Werner 参数纯代数学积 ·
  中继增益 = 纯比值）⇒ 见 `lda_l2/qnet_repeater.py` 的避让表）。

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
from .._batch_j2_numeric import (  # Batch J2 超导 Transmon 征程 · M2 两比特门层（CR 门退相干错误率 / 残余 ZZ 诱导错误率）
    golden_b506,
    B506_DEFAULT_PARAMS,
    golden_b507,
    B507_DEFAULT_PARAMS,
)
from .._batch_j2m3_numeric import (  # Batch J2 超导 Transmon 征程 · M3 色散读出链 + 串扰（FDM 通道频谱重叠串扰比）
    golden_b508,
    B508_DEFAULT_PARAMS,
)
from .._batch_j2m4_numeric import (  # Batch J2 超导 Transmon 征程 · M4 QPU 误差预算集成 + 拓扑对接（耦合图代数连通度 λ₂）
    golden_b509,
    B509_DEFAULT_PARAMS,
)
from .._batch_j3_numeric import (  # Batch J3 量子测控与读出征程 · M0–M4（Rabi 布居 / 三能级泄漏 / unitarity 纯度衰减 / Purcell 滤波抑制比 / Caves 级联噪声）
    golden_b510,
    golden_b511,
    golden_b512,
    golden_b513,
    golden_b514,
    B510_DEFAULT_PARAMS,
    B511_DEFAULT_PARAMS,
    B512_DEFAULT_PARAMS,
    B513_DEFAULT_PARAMS,
    B514_DEFAULT_PARAMS,
)
from .._batch_j4_numeric import (  # Batch J4 量子传感系统集成征程 · M0 多参数 NV 交叉灵敏度解耦 + M3 低温布线束热负载
    golden_b515,
    B515_DEFAULT_PARAMS,
    golden_b518,
    B518_DEFAULT_PARAMS,
)
from .._batch_j5_numeric import (  # Batch J5 量子网络与接口征程 · M0 分发后两体纠缠保真度 + M1 光子不可分辨性 + M2 中继产出 + M3 换能效率
    golden_b519,
    B519_DEFAULT_PARAMS,
    golden_b520,
    B520_DEFAULT_PARAMS,
    golden_b521,
    B521_DEFAULT_PARAMS,
    golden_b522,
    B522_DEFAULT_PARAMS,
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
    "B506": {
        "title": "两比特 CR 门退相干错误率 ε=1−(4·F_pro^A·F_pro^B+1)/5（超导 Transmon J2 · M2 两比特门层）：张量 A+D 信道闭式 golden vs 16×16 Liouvillian RK4 候选 · 无量纲",
        "metric": "cr_gate_decoherence_error",
        "oracle": "closed_form(ε=1−(4·F_pro+1)/5, F_pro=F_pro^A·F_pro^B, F_proⁱ=(1+e^{−t/T1ⁱ}+2e^{−t/T2ⁱ})/4) + 16×16 Liouvillian RK4 独立_cross_check",
        "tol": 1e-7,
        "default_params": dict(B506_DEFAULT_PARAMS),
        "golden_fn": golden_b506,
        "candidate": "b506_cr_gate_decoherence_cand",
        "candidate_desc": "16×16 Liouville 超算子（vec-F 序）RK4 传播 16 个 2q Pauli 基算子 ⇒ 过程保真度 F_pro=Σ_m tr(σ_m E(σ_m))/64 ⇒ ε=1−(4F_pro+1)/5。方法学独立：golden=张量 A+D 信道解析闭式，cand=Lindblad 超算子数值积分（n=16 步）",
        "note": "golden = 超导 Transmon 征程 J2（M2 两比特门层）的**两比特 CR（cross-resonance）门退相干错误率**闭式：门执行期间两比特各经受幅度阻尼（T1）+ 纯退相（Tφ，1/T2=1/2T1+1/Tφ）⇒ 单比特 A+D 信道过程保真度 F_proⁱ=(1+e^{−t/T1ⁱ}+2e^{−t/T2ⁱ})/4（与 B10 的 (3+2e^{−t/T2}+e^{−t/T1})/6 同源换算 F_avg=(2F_pro+1)/3）；2q 张量信道 F_pro=F_pro^A·F_pro^B ⇒ 平均门保真度 (d·F_pro+1)/(d+1), d=4。🔴 **物理意义**：CR 门是固定频率 transmon 的主流 2q 门（控制比特微波驱动经交换耦合 J 生成有效 ZX，门时间 t_CR=π/|g_CR|）；退相干是 CR 门错误首要项。本锚把**器件物理层（T1/T2）→ 2q 门错误率**钉进账本。candidate=**16×16 Liouville 超算子（vec-F 序）RK4**（方法学独立），实测默认档(T1_A=10, T1_B=12, T2_A=8, T2_B=9, t=2 ⇒ golden≈2.179e-1) **rel=2.988e-09**（abs 6.511e-10 · **tol=1e-7**〔绝对口径〕⇒ **153.6×** 余量；|golden|/tol=2.18e6；残差链 1.439e-05 → 8.198e-07 → 4.892e-08 → 2.988e-09，**比值 17.56/16.76/16.37×** ⇒ **O(h⁴)**（RK4 标称阶），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **同源体检**：与 **B10**（单量子比特门保真度）**标量/构型/格式三者均不同**（1q 门保真 F vs 2q CR 门错误率 ε；单比特信道 vs 两比特 CR 门张量信道；4×4 vs 16×16 超算子）⇒ 按 B452↔B33 先例计新锚（宪章原 B508「单比特门错误率」与 B10 三者全同 ⇒ 已否决，见 `docs/LDA_J2_..._2026-10-13.md` §7.1）；与 B26/B27（χ / t_CZ，门时间非错误率）、S4（∏fᵢ 纯算术）、B502–B504（J1 QEC 率积分）**均不同源**。⚠️ **诚实边界**：默认档为**退相干标定档**（t 与 T1/T2 同量级 ⇒ 截断误差可标定；典型生产门 t_CR≪T1 ⇒ 残差沉噪声地板、判据 D 不可标定）。T1/T2/t 为**设计示例量级**（非实测 PDK）；本锚只证「张量信道闭式 ⇄ Lindblad 数值」一致这一数学事实，**不得作制造/性能宣称**（未建模泄漏/ZZ/驱动误差——另由 B507 与 M3/M4 覆盖）。零商业依赖（纯 numpy）。",
    },
    "B507": {
        "title": "残余 ZZ 诱导门错误率 ε=(4/5)·sin²(ζt/2)（超导 Transmon J2 · M2 两比特门层）：闭式 golden vs 矩阵传播子 RK4 候选 · 无量纲",
        "metric": "residual_zz_error",
        "oracle": "closed_form(ε=(4/5)sin²(ζt/2)) + 4×4 复矩阵传播子 RK4 dU/dt=−iH U 独立_cross_check",
        "tol": 1e-6,
        "default_params": dict(B507_DEFAULT_PARAMS),
        "golden_fn": golden_b507,
        "candidate": "b507_residual_zz_error_cand",
        "candidate_desc": "4×4 复矩阵传播子 RK4 积分 dU/dt=−iH U（H=(ζ/2)Z⊗Z, U(0)=I₄, n=16 步）⇒ F_pro=|tr(U)/4|² ⇒ ε=1−(4F_pro+1)/5。方法学独立：golden=闭式 cos²，cand=矩阵 ODE 数值积分",
        "note": "golden = 超导 Transmon 征程 J2（M2 两比特门层）的**残余 ZZ 诱导门错误率**闭式：固定频率 transmon 对存在静态残余 ZZ 角耦合 ζ（交换耦合二阶虚交换），门/idle 期间累积条件相位 ⇒ H=(ζ/2)·Z⊗Z 严格演化 U=e^{−iHt}，本征值 {e^{∓iζt/2}}×2 ⇒ F_pro=|tr(U)/4|²=cos²(ζt/2) ⇒ F_avg=(4F_pro+1)/5 ⇒ ε=1−F_avg=(4/5)sin²(ζt/2)（小角极限 ε→(1/5)(ζt)²）。🔴 **物理意义**：残余 ZZ 是固定频率 transmon 相干错误主要来源（crosstalk 使「不操作」的邻居比特也积累 ZZ 相位）；本锚把它钉进账本。candidate=**4×4 复矩阵传播子 RK4**（方法学独立），实测默认档(ζ=0.5 rad/µs, t=2 µs ⇒ golden≈1.839e-1) **rel=1.385e-08**（abs 2.547e-09 · **tol=1e-6**〔绝对口径〕⇒ **392.7×** 余量；|golden|/tol=1.84e5；残差链 3.571e-05 → 2.995e-06 → 2.103e-07 → 1.385e-08，**比值 11.93/14.24/15.18×** ⇒ **O(h⁴)**（RK4 标称阶），严格单调、残差 >0 ⇒ **非**代数恒等）。🔴 **同源体检**：与 B26/B27（χ / t_CZ，色散量非 ZZ 错误率）、B506（退相干信道 vs 相干 ZZ 相位，**不同算子**）、B502–B504（exp(−∫率) 一维积分 vs 4×4 矩阵演化）**均不同源**；实 grep 核验 `residual ZZ|残余 ZZ|zz_error` 在 BENCHMARK_DEFS/lda_solver 零占用。⚠️ **诚实边界**：默认档为 **ZZ 标定档**（ζ·t≈O(1) ⇒ 相位演化误差可标定；典型 ζ~0.1–1 MHz、t~0.1–0.4 µs ⇒ ζ·t~O(0.1) 时错误更小、残差同步变小）。ζ/t 为**设计示例量级**（非实测 PDK）；本锚只证「ZZ 相位闭式 ⇄ 矩阵演化数值」一致这一数学事实，**不得作制造/性能宣称**（未建模 echoed-CR 抵消、ζ 的时间噪声）。零商业依赖（纯 numpy）。",
    },
    "B508": {
        "title": "FDM 多音读出相邻通道频谱重叠串扰比 X=4γ²/(4γ²+δ²)（超导 Transmon J2 · M3 色散读出链 + 串扰）：闭式 golden vs sinh 换元+复合 Simpson 数值卷积候选 · 无量纲",
        "metric": "fdm_mux_overlap_ratio",
        "oracle": "closed_form(X=4γ²/(4γ²+δ²)=1/(1+(δ/(2γ))²)，洛伦兹自相关) + sinh 换元 + 复合 Simpson 数值卷积独立_cross_check",
        "tol": 1e-7,
        "default_params": dict(B508_DEFAULT_PARAMS),
        "golden_fn": golden_b508,
        "candidate": "b508_fdm_mux_overlap_cand",
        "candidate_desc": "sinh 换元（f=γ(a+sinh u), a=δ/(2γ)）+ 复合 Simpson 数值卷积：∫L_iL_j / ∫L_i²，两积分各 n=256 区间。方法学独立：golden=洛伦兹自相关解析闭式，cand=数值卷积求积",
        "note": "golden = 超导 Transmon 征程 J2（M3 色散读出链 + 串扰）的 **FDM 多音读出相邻通道频谱重叠串扰比**闭式：FDM 把 N 个 λ/4 读出谐振器挂同一 feedline，每通道线型是洛伦兹 L(f)=(γ/π)/((f−f_c)²+γ²)（γ=κ/2 半高半宽，κ 为读出线宽）。相邻通道间隔 δ 时归一化频谱重叠（串扰比）X=∫L_iL_j df/∫L_i² df；由 FT[L]=e^{−2πγ|t|} ⇒ ∫L_iL_j=2γ/(π(4γ²+δ²))、∫L²=1/(2πγ) ⇒ **X=4γ²/(4γ²+δ²)=1/(1+(δ/(2γ))²)**（洛伦兹自相关，**精确闭式、非截断近似**）。🔴 **物理意义**：X 是 mux 频率规划的**物理判据**——给定串扰容限 X_tol 的最小通道间隔 Δf_min=2γ√(1/X_tol−1)、带宽内通道数 N_max=⌊B/Δf_min⌋（能力层 `lda_qeda/j2_readout_mux.py`）。candidate=**sinh 换元 + 复合 Simpson 数值卷积**（方法学独立；换元把 1/f² 慢衰减尾部压成 e^{−3|u|}，避免尾部截断主导残差 —— B-11 族 D 血案解法）。实测默认档(γ=0.5 MHz, δ=1.2 MHz ⇒ golden=4.098360e-1)：残差链 n=32→2.191e-02 → 64→2.302e-03 → 128→1.481e-05 → **256→4.253e-10**（**tol=1e-7**〔绝对口径〕⇒ **235.1×** 余量；|golden|/tol=4.10e6），**严格单调**、残差 >0 ⇒ **非**代数恒等；实测比值 **9.52/155.45/34825×**（被积函数解析 ⇒ 收敛快于标称 O(h⁴)，**如实披露不虚报「恰 O(h⁴)」**）。🔴 **同源体检（实 grep 零占用）**：宪章原定 M3 两候选**均被否决** —— ①宪章 B511「读出分配错误率（χ/κ/SNR ⇄ 数值二态分类）」被既有 **B30**（读出保真度 F：SNR→erfc 误判链 ⇄ `readout_fidelity_quad` 高斯重叠数值积分=二态分类）**三者全同** ⇒ 只是换名；②宪章 B512「杂散 ZZ 串扰错误预算（σ_zz ⇄ 数值）」被本征程 **B507**（残余 ZZ 诱导错误率 ⇄ 矩阵传播子 RK4）占用。本锚落在 M3 中唯一未覆盖的连续量（FDM 通道间频谱重叠）：与 **B459**（洛伦兹**幅度斜率极值** / 中心差分）、**B197·B199**（Voigt **线心值** / sinh 换元单积分）、**B30**（**误判概率**，含 erfc/SNR/T1 权重）**标量·构型·格式三者均异** ⇒ 计新锚（承 B452↔B33 先例）。⚠️ **诚实边界**：γ/δ 为**设计示例量级**（非实测 PDK/非流片）；本锚只证「洛伦兹自相关闭式 ⇄ 数值卷积求积」一致这一数学事实 + mux 规划物理链自洽，**不得作制造/性能宣称**（未建模 feedline 阻抗失配、非线性 Kerr 频移、tone 间互调）。零商业依赖（纯 numpy）。",
    },
    "B509": {
        "title": "QPU 耦合图代数连通度 λ₂（Fiedler 值）（超导 Transmon J2 · M4 QPU 误差预算集成 + 拓扑对接）：谱定理闭式 golden vs 嵌套 Krylov 子空间 Rayleigh–Ritz 候选 · 无量纲",
        "metric": "qpu_graph_algebraic_connectivity",
        "oracle": "closed_form(λ₂=2−2·cos(π/max(rows,cols))，Cartesian 积 P_rows□P_cols 的 Laplacian Kronecker 和) + 嵌套 Krylov 子空间 Rayleigh–Ritz 最小值独立_cross_check",
        "tol": 1e-7,
        "default_params": dict(B509_DEFAULT_PARAMS),
        "golden_fn": golden_b509,
        "candidate": "b509_graph_algebraic_connectivity_cand",
        "candidate_desc": "嵌套 Krylov 子空间 Rayleigh–Ritz 最小值：对组合 Laplacian L=D−A（方阵最近邻耦合图）取确定性起始向量 v₀⊂1⊥，逐维扩张 Krylov 基 K_m=L^(m−1)v₀（全重正交防基病态），在 K_m 上求最小 Ritz 值作 λ₂ 上界。方法学独立：golden=Cartesian 积谱定理闭式，cand=大规模稀疏特征值数值下界估计（min-max 原理）",
        "note": "golden = 超导 Transmon 征程 J2（M4 QPU 误差预算集成 + 拓扑对接）的 **QPU 耦合图代数连通度 λ₂（Fiedler 值）**闭式：qubit 耦合图（heavy-hex / 方阵，最近邻连接）的组合 Laplacian L=D−A 的第二小特征值 λ₂ 度量图的「连通紧密度」，是 QEC 局部解码（表面码 2D 最近邻匹配 / Union-Find / MWPM）可行性的**谱判据**。方阵耦合图 = Cartesian 积 P_rows □ P_cols ⇒ Laplacian 谱 = 因子谱的 **Kronecker 和** ⇒ **λ₂ = 2 − 2·cos(π / max(rows, cols))**（精确闭式、**非截断近似**；实测与稠密 `eigvalsh` 差 ≤ 3.84e-15）。🔴 **物理意义**：λ₂ 越小 ⇒ 图越「瓶颈化」⇒ 局部割能力差；配合 Cheeger 不等式 λ₂/2 ≤ h(G) ≤ √(2λ₂) 把谱隙与等周数 h(G)（局部割能力）钉在一起，给出表面码 2D 局部匹配可行性的物理门槛（能力层 `lda_qeda/topology_qec_bridge.py`：方阵度≥4⇒DIRECT、heavy-hex 度3⇒ADAPTED、度<3⇒FAIL）。candidate=**嵌套 Krylov 子空间 Rayleigh–Ritz 最小值**（方法学独立；min-max 原理下嵌套子空间 K_m⊂K_{m+1}（⊂1⊥）上最小 Ritz 值**单调非增**且恒 ≥ λ₂ ⇒ 残差单调降；🔴 必须**全重正交**防基病态 + **m<N** 防常数向量泄漏。实测默认档(rows=10, cols=10 ⇒ N=100, **golden=9.788696740969e-02**)：残差链 m=4→**4.626e-01** → 8→**9.999e-02** → 16→**1.082e-02** → **32→1.122e-10**（**tol=1e-7**〔绝对口径〕⇒ **891.4×** 余量；|golden|/tol=9.789e5），**严格单调**、残差 >0 ⇒ **非**代数恒等；实测比值 **4.63/9.25/9.64e7×**（**动态范围 4.1e9×**）。🔴 **诚实边界（不虚报收敛阶）**：Krylov 极值收敛在**低维段近似线性、末段超收敛**（m 从 16→32 残差骤降 9.6e7×），**非等比收敛** ⇒ 如实披露「非均匀收敛」，**不虚报「恰 O(hᵏ)」**。🔴 **同源体检（实 grep 零占用）**：宪章原定 M4 两候选**均被否决** —— ①宪章 B513「拓扑连通性 vs 表面码需求（heavy-hex 度3 / 方阵度4 ⇄ 表面码最近邻判据）」的「连通性」是**布尔/整数**量（度是整数）、残差恒沉地板 ⇒ 属**不可锚**（同 S1–S6 纯算术 / B17 定义式）⇒ **改靶到其连续化**：同一「连通性」概念的**谱形式 λ₂**；②宪章 B514「QPU 总错误率 ≤ 阈值余量（闭式预算 ⇄ 数值）」被完全占用 —— ∏/Σ 算术级联与既有 **S4**（∏fᵢ 乘法级联保真预算，`s4_fidelity_budget`）同源、∫率 dt 数值路线与 J1 锚 **B502/B503/B504/B505**（exp(−∫率) / 1−exp(−∫率)）同原子族 ⇒ 否决。本锚落在 M4 中唯一未被覆盖的**连续**物理量（耦合图谱隙）：与 **B10/B506/B507**（门错误率 ⇄ Lindblad/矩阵 RK4）**标量·构型·格式三者均异**；实 grep 核验 `fiedler|algebraic_connect|laplacian|lanczos|krylov|power_iter|eigsh|谱隙|spectral_gap|graph_spectr` 在**锚定义**内零占用（part2 2D 方势阱注释的 Laplacian=量子阱本征、`_batch_b15/b19` 的 Laplacian 验调和、`_batch_b9/b22`/`_adapter_p1` 的 eigsh 求**物理本征值** ⇒ 标量均不同）⇒ 计新锚（承 B452↔B33 先例）。⚠️ **诚实边界**：rows/cols 为**设计示例量级**（非实测 PDK/非流片）；本锚只证「谱定理闭式 ⇄ Krylov 数值下界」一致这一数学事实 + 拓扑↔QEC 物理链自洽，**不得作制造/性能宣称**。零商业依赖（纯 numpy；candidate 零 RNG——确定性起始向量）。",
    },
    "B510": {
        "title": "广义 Rabi 时域布居 P₁=(Ω²/Ω_R²)·sin²(Ω_R t/2)（量子测控 J3 · M0 时域驱动脉冲）：解析闭式 golden vs 时域 TDSE RK4 候选 · 无量纲",
        "metric": "rabi_time_domain_population",
        "oracle": "closed_form(P₁=(Ω²/Ω_R²)sin²(Ω_R t/2), Ω_R=√(Ω²+δ²)) + 时域 TDSE 四阶 RK4 态矢推进独立_cross_check",
        "tol": 1e-6,
        "default_params": dict(B510_DEFAULT_PARAMS),
        "golden_fn": golden_b510,
        "candidate": "b510_rabi_population_cand",
        "candidate_desc": "时域 TDSE 四阶 RK4 推进 i dψ/dt=Hψ（H=(δ/2)σz+(Ω/2)σx，ψ(0)=|0⟩，n=128 步）⇒ P₁=|ψ₁|²。方法学独立：golden=RWA 常矩阵哈密顿的**精确解析解**，cand=时间推进数值积分",
        "note": "golden = 量子测控与读出征程 J3（M0 时域驱动脉冲）的**广义 Rabi 时域布居**闭式：二能级 RWA 驱动哈密顿 H=(δ/2)σ_z+(Ω/2)σ_x（δ 为驱动失谐、Ω 为 Rabi 角频率）为**常矩阵** ⇒ 演化 e^{−iHt} 有精确解析解，ψ(0)=|0⟩ 给出 P₁(t)=(Ω²/Ω_R²)·sin²(Ω_R t/2)（Ω_R=√(Ω²+δ²)；δ=0 退化 sin²(Ωt/2)，Ω=0 退化 0）—— **精确式、非截断近似**。🔴 **物理意义**：Rabi 时域布居是**脉冲幅度/时长定标**的物理基础（π 脉冲 ⇒ P₁=1 ⇒ Ωt=π）与失谐降效（最大转移效率 Ω²/(Ω²+δ²)）的判据源头；能力层 `lda_qeda/control_closed_loop.py` 的闭环第一环（Rabi 幅度定标）与 `lda_qeda/qubit_dynamics.py` 的演化器均复用同一物理律。candidate=**时域 TDSE 四阶 RK4 态矢推进**（方法学独立；i dψ/dt=Hψ，n=128 步）。实测默认档(Ω=0.05 rad/ns, δ=0.03 rad/ns, t=100 ns ⇒ golden≈3.696e-02) **残差=2.092e-09**（**tol=1e-6**〔绝对口径·对 |golden|≈3.696e-2 即相对 5.66e-8〕⇒ **478.1×** 余量；|golden|/tol=3.70e4；残差链 n=8→1.218e-04 → 16→8.205e-06 → 32→5.269e-07 → 64→3.330e-08 → **128→2.092e-09**，**比值 14.85/15.57/15.82/15.92×** ⇒ **O(h⁴)**〔RK4 标称阶〕，严格单调、残差>0 ⇒ **非**代数恒等）。🔴 **同源体检（实 grep 零占用）**：与既有 **B10**（单比特门保真度 F·退相干极限）三方分歧 —— ①被测标量（**时域布居 P₁** vs 平均门保真度 F）②物理构型（**含时驱动演化** vs 纯退相干信道）③数值格式（**态矢 RK4** vs 4×4 PTM 超算子积分）；与 **B506/B507**（J2 两比特 CR 门 / 残余 ZZ 错误率）同样三方分歧（门错误率 ε vs 布居概率 / 两比特门或静态 ZZ 相位 vs 单比特相干 Rabi 动力学 / 16×16·4×4 传播子 vs 2 维态矢）；与本征程 **D-91 `solve_drive`**（`lda_solver/qeda_depth_solver.py`：**静态 RWA 本征分裂=Ω**，且**非账本锚**）分歧在「时域布居函数 vs 静态本征值标量 / 含时演化 vs 静态对角化 / RK4 步进 vs eigvalsh」⇒ 计新锚（承 B452↔B33 先例）。🔴 实 grep：`rabi` 在 `BENCHMARK_DEFS` 内仅命中 B494/B496 的 note 文本（描述腔 QED **单光子耦合 g** 被称「单光子 Rabi 频率」，**非**驱动下的时域振荡）⇒ 锚定义零占用。⚠️ **诚实边界**：Ω/δ/t 为**设计示例量级**（非实测 PDK / 非任意波形发生器标定）；本锚只证「解析闭式 ⇄ 时域数值」一致这一数学事实 + 脉冲层物理链自洽，**不得作制造/性能宣称**（未建模脉冲形状误差、泄漏、退相干——泄漏另由 B511 覆盖）。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B511": {
        "title": "三能级 transmon 驱动泄漏布居 P_leak（量子测控 J3 · M1 DRAG 泄漏抑制）：三角法精确谱闭式 golden vs 时域 RK4 候选 · 无量纲",
        "metric": "qutrit_driven_leakage_population",
        "oracle": "closed_form(λ³−αλ²−(3Ω²/4)λ+αΩ²/4=0 三角法精确根 ⇒ P_leak(t)=|Σ_k⟨0|v_k⟩⟨v_k|2⟩e^{−iλ_k t}|²) + 时域 RK4 三能级态矢推进独立_cross_check",
        "tol": 1e-5,
        "default_params": dict(B511_DEFAULT_PARAMS),
        "golden_fn": golden_b511,
        "candidate": "b511_qutrit_leakage_cand",
        "candidate_desc": "时域 TDSE 四阶 RK4 推进三能级 i dψ/dt=Hψ（H=(Ω/2)(a+a†)+α|2⟩⟨2|，a 为 √2 升降算符，ψ(0)=|0⟩，n=256 步）⇒ P_leak=|ψ₂|²。方法学独立：golden=特征方程三角法解析求根 + 谱分解，cand=时间推进数值积分",
        "note": "golden = 量子测控与读出征程 J3（M1 DRAG 泄漏抑制）的**三能级 transmon 驱动泄漏布居**闭式：三能级 RWA 驱动哈密顿 H=(Ω/2)(|0⟩⟨1|+|1⟩⟨0|)+(√2·Ω/2)(|1⟩⟨2|+|2⟩⟨1|)+α|2⟩⟨2|（√2 为谐振子升降矩阵元、α 为 transmon 非谐性）的**精确谱分解**：特征多项式 λ³−αλ²−(3Ω²/4)λ+αΩ²/4=0 经 **depressed cubic 三角法**（λ=μ−A/3；p=−(a²+b²)−α²/3、q=−2α³/27 —— Ω 在 q 中恰好相消、闭式化简的直接后果）解析求三实根，本征矢 v_k∝(1, λ_k/a, (λ_k²−a²)/(a·b)) 归一化 ⇒ P_leak(t)=|Σ_k⟨0|v_k⟩⟨v_k|2⟩e^{−iλ_k t}|²（ψ(0)=|0⟩）—— **精确式、非截断近似、非数值迭代**。🔴 **物理意义**：三能级 transmon 的非谐性 α 使 |1⟩→|2⟩ 被失谐 α（且 √2 加强耦合）⇒ 驱动计算比特时**非计算态被布居**（coherent leakage）；DRAG（derivative removal by adiabatic gate）正为压制该泄漏而设计 ⇒ P_leak 是**泄漏抑制比**的分子/分母（能力层 `lda_qeda/qubit_dynamics.py`：实测默认档 P_leak(无 DRAG)=1.610e-01 → P_leak(DRAG)=7.144e-03 ⇒ 抑制比 **22.53×**，最优 β*=1.0 = DRAG 标准值）。candidate=**同一 ODE 的时域 RK4 三能级态矢推进**（方法学独立：解析谱分解 vs 时间推进；n=256 步）。实测默认档(Ω=0.05 rad/ns, α=−0.3 rad/ns, t=π/Ω=62.831853 ns ⇒ golden≈1.285e-02) **残差=1.030e-08**（**tol=1e-5**〔绝对口径·相对 8.02e-7〕⇒ **970.5×** 余量；|golden|/tol=1.285e3；残差链 n=16→4.461e-04 → 32→4.244e-05 → 64→2.715e-06 → 128→1.671e-07 → **256→1.030e-08**，**比值 10.51/15.63/16.24/16.22×** ⇒ **O(h⁴)**〔RK4 标称阶〕，严格单调、残差>0 ⇒ **非**代数恒等）。🔴 **判据 D 稳定性边界（实测，如实登记）**：三能级含 α 的**实对角项** ⇒ RK4 稳定域 |hλ| ≤ 2√2；t=100 ns 时 n=8（h=12.5 ⇒ |hα|=3.75）**已越界发散**（实测残差 1.95e8）⇒ 本锚扫描格从 n=16 起（t=π/Ω 档 n=8 虽边缘稳定，但未入渐近区、比值仅 1.16 ⇒ 一并弃用）。🔴 **极限行为（本轮实测纠正错直觉，已入库）**：泄漏极小来自 |α|≫Ω；**α→0（谐振子极限）泄漏反而显著**（实测 α=−1e-6、Ω=0.02、t=300 ⇒ P_leak≈6.36e-02），因 1-2 跃迁共振、粒子沿能级阶梯上行 —— **「α→0 泄漏塌陷」是错的**，该结论已写成 `qubit_dynamics.run_selfchecks` 的常驻判据（另附 |α| 单调降判据）。🔴 **同源体检（实 grep 零占用）**：`drag` **0 命中**、`leakage` **0 命中**、`脉冲面积|pulse_area` **0 命中**；`泄漏` 仅出现在 note 文本（B10 note「未含…泄漏」= 显式声明**不在**其口径内；part2 隧穿尾泄漏；part7 J2 描述）⇒ 无任何锚以泄漏/DRAG 为被测标量；与 **B10**（平均门保真度）在①被测标量（**泄漏概率** vs 门保真度）②物理构型（**三能级相干泄漏** vs 二能级退相干信道）③数值格式（**3 维态矢 RK4** vs 4×4 PTM）三方分歧；与 **B510**（二能级计算态布居）在**算子维度与结构**（3×3 含 √2 耦合 + 非谐性 α vs 2×2 纯驱动）及被测标量（非计算态泄漏 vs 计算态布居）上分歧 ⇒ 非「同算子换语境」⇒ 各计一锚（承 B448/B449「同族不同参数各计一锚」先例）。⚠️ **诚实边界**：Ω/α/t 为**设计示例量级**（非实测 PDK / 非流片）；本锚只证「三角法精确谱闭式 ⇄ 时域数值」一致 + DRAG 抑制趋势自洽，**不得作制造/性能宣称**（未建模 |3⟩+ 高阶能级、驱动线非线性、T1/T2 退相干）。零商业依赖（纯 numpy + math；零 RNG —— 特征根为确定性三角法）。",
    },

    "B512": {
        "title": "去极化信道纯度衰减 P(t)=Tr(ρ²)（量子测控 J3 · M2 门保真标定 · unitarity）：解析闭式 golden vs 密度矩阵 Liouvillian RK4 候选 · 无量纲",
        "metric": "unitarity_purity_decay",
        "oracle": "closed_form(P(t)=(1+e^{−2Γt})/2, Bloch 各向同性收缩 r(t)=e^{−Γt}) + 密度矩阵 Liouvillian 四阶 RK4 独立_cross_check",
        "tol": 1e-7,
        "default_params": dict(B512_DEFAULT_PARAMS),
        "golden_fn": golden_b512,
        "candidate": "b512_unitarity_purity_cand",
        "candidate_desc": "密度矩阵 Liouvillian 时域四阶 RK4 积分（2×2 复 ρ，初态 |0⟩⟨0|，dρ/dt=(Γ/4)(σ_xρσ_x+σ_yρσ_y+σ_zρσ_z−3ρ)，n=64 步）⇒ P=Tr(ρ²)。方法学独立：golden=Bloch 线性 ODE 的**精确指数闭式**，cand=数值时间推进",
        "note": "golden = 量子测控与读出征程 J3（M2 门保真标定）的**去极化信道纯度衰减**闭式：去极化 Lindblad 主方程 dρ/dt=(Γ/4)(Σᵢσᵢρσᵢ−3ρ) 的 Bloch 表示为 **dr/dt=−Γr**（各向同性收缩）⇒ **严格解 r(t)=r(0)e^{−Γt}** ⇒ 纯度 P(t)=Tr(ρ²)=(1+|r₀|²e^{−2Γt})/2（初态 |0⟩ ⇒ |r₀|=1、P(0)=1、P(∞)=1/2）—— **精确式、非截断近似**。🔴 **物理意义（M2 的核心）**：这是 **unitarity（二阶纯度衰减率 u=e^{−2Γ}=p²，p=e^{−Γ} 为一阶 RB 保真度参数）** 的物理内容 —— 二阶纯度量对**相干（酉）误差不敏感**（酉演化保纯度 ⇒ u=1）、对**非相干（去极化）误差敏感**（u=p²），故与一阶 RB 保真度 F 联立可把「相干误差 vs 非相干误差」分离（Wallman 2015）；能力层 `lda_qeda/rb_benchmark.py` 用 24 元 Clifford 群 + 逐门纯度序列实现该分解，`lda_qeda/control_closed_loop.py` 的 Ring E 复用同一物理律。candidate=**密度矩阵 Liouvillian 的时域四阶 RK4 积分**（方法学独立；2×2 复 ρ，n=64 步）。实测默认档(Γ=0.02 /ns, t=100 ns ⇒ **golden=5.091578194444e-01**) **残差=2.988e-10**（**tol=1e-7**〔绝对口径〕⇒ **334.7×** 余量；|golden|/tol=5.09e6；残差链 n=4→2.905e-05 → 8→1.470e-06 → 16→8.272e-08 → 32→4.907e-09 → **64→2.988e-10**，**比值 19.77/17.77/16.86/16.42×** ⇒ **O(h⁴)**〔RK4 标称阶〕，严格单调、残差>0 ⇒ **非**代数恒等；动态范围 9.72e4×）。🔴 **同源体检（实 grep 全仓核验）**：`unitarity` 在 `BENCHMARK_DEFS` 内 **0 命中**；`纯度|purity` 仅命中 `part5.py` B454（TMSS **光学连续变量**预报条件态纯度，与 qubit 门序列纯度衰减完全不同构型）⇒ 锚定义零占用。与 **B10**（单比特门保真度 F·退相干极限 `(3+2e^{−t/T2}+e^{−t/T1})/6`）**三方分歧** —— ①**被测标量**：**二阶纯度 P=Tr(ρ²)**（∝e^{−2Γt}）vs **一阶保真度 F**（∝e^{−Γt}）—— 对相干误差敏感度根本不同（酉误差 u=1 而 F<1，正是 unitarity 的物理价值）②**物理构型**：**对称去极化**（各向同性自旋弛豫，单率 Γ）vs **T1/T2 非对称退相干**（振幅 + 相位双通道）③**数值格式**：**2×2 复密度矩阵 Liouvillian RK4** vs **4×4 PTM 超算子积分** ⇒ 计新锚（承 B452↔B33 先例）。⚠️ **诚实边界**：Γ/t 为**设计示例量级**（非实测 PDK / 非流片）；本锚只证「解析指数闭式 ⇄ 数值 Liouvillian 积分」一致这一数学事实 + unitarity 物理链自洽，**不得作制造/性能宣称**；未建模真实硬件的非马尔可夫噪声。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B513": {
        "title": "Purcell 滤波器抑制比 S=1/|S21(f_q)|²（量子测控 J3 · M3 读出链）：ABCD 代数闭式 golden vs 导纳 ODE RK4 数值积分候选 · 无量纲",
        "metric": "purcell_filter_suppression",
        "oracle": "closed_form(S=1/|S21|², S21=2/(2+j·(Z0/Zs)·tanβl), βl=(π/2)(f_q/f_s) ABCD 代数) + 导纳 ODE 四阶 RK4 数值积分独立_cross_check",
        "tol": 1e-6,
        "default_params": dict(B513_DEFAULT_PARAMS),
        "golden_fn": golden_b513,
        "candidate": "b513_purcell_suppression_cand",
        "candidate_desc": "导纳 ODE dy/dθ=j(1−y²)（y(0)=0 ⇒ y=j·tanθ）的四阶 RK4 数值积分（沿 stub 长度从负载积到输入端，n=1024 步）⇒ Y_stub ⇒ S21 ⇒ S=1/|S21|²。方法学独立：golden=ABCD 矩阵代数闭式，cand=数值 ODE 积分",
        "note": "golden = 量子测控与读出征程 J3（M3 读出链）的 **Purcell 滤波器抑制比**闭式：并联在主线上的**开路 λ/4 短截线**带阻滤波器（ABCD=[[1,0],[Y_stub,1]]，Y_stub=j·Y_s·tan(βl)）⇒ **S21(f)=2/(2+j·(Z₀/Z_s)·tanβl)**（βl=(π/2)(f_q/f_s)），抑制比 **S=Γ_P^{no}/Γ_P^{filter}=1/|S21(f_q)|²**（qubit 频率处外泄率被压低的倍率）—— **精确代数式、非近似**；f_q→f_s ⇒ tan→∞ ⇒ S21→0 ⇒ S→∞（完美带阻），f_q 远离 f_s ⇒ S→1（透明）。🔴 **物理意义**：qubit 经读出腔/feedline 的 Purcell 衰减是超导量子比特的主要 T1 限制之一，λ/4 短截线滤波器在 qubit 频率处形成阻带、压低外泄率 ⇒ 提升 T1 **S 倍**；能力层 `lda_qeda/readout_demod.py` 复用同式，`lda_qeda/control_closed_loop.py` 的 Ring F 与 M4 总装均接线。candidate=**导纳 ODE dy/dθ=j(1−y²) 的时域四阶 RK4 数值积分**（方法学独立；y(0)=0（开路负载）⇒ y=j·tanθ，沿 stub 长度 RK4 步进 n 步）。实测默认档(f_q=5.5 GHz, f_s=6.0 GHz, Z₀=Z_s ⇒ **golden=1.542387013525e+01**) **残差=4.652e-09**（**tol=1e-6**〔绝对口径〕⇒ **215.0×** 余量；|golden|/tol=1.54e7；残差链 n=64→2.988e-04 → 128→1.905e-05 → 256→1.193e-06 → 512→7.451e-08 → **1024→4.652e-09**，**比值 15.69/15.96/16.02/16.02×** ⇒ **O(h⁴)**〔RK4 标称阶〕，严格单调、残差>0 ⇒ **非**代数恒等；动态范围 6.42e4×）。🔴 **同源体检（实 grep 全仓核验）**：`filter_reflect|S参数|S 参数|滤波器` 在锚定义内无「滤波抑制比」占用（`滤波器` 仅命中 1 处非本量纲文本）；`purcell|Purcell` 仅命中 `part1.py` **B18**（谐振腔 Purcell 因子 F_P）⇒ 与 **B18**（F_P=4g²/(κγ)，**器件级衰减增强因子**）**三方分歧** —— ①**被测标量**：**滤波器系统级抑制倍率 S**（加滤波器后的 T1 提升比）vs **器件级 F_P 因子**②**物理构型**：**传输线 + λ/4 短截线滤波器网络** vs **单腔-qubit 耦合**③**数值格式**：**导纳 ODE 的 RK4 数值积分** vs B18 的**纯代数闭式** ⇒ 计新锚；与 **B30**（读出保真度，已占）、**B26**（色散 χ，已占）、J2 **B508**（FDM mux，已占）三者亦异 ⇒ 本档唯一净增锚（章程 §3 M3 已预设「若判同源则净增 0」路径，实测零占用）。⚠️ **诚实边界**：f_q/f_s/Z₀/Z_s 为**设计示例量级**（非实测 PDK / 非流片）；模型为**理想传输线 + 集中式 stub**（忽略介质损耗、接头反射、滤波器有限 Q）⇒ 只证「ABCD 闭式 ⇄ 数值 ODE 积分」一致 + Purcell 物理链自洽，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B514": {
        "title": "分布式相位不敏感放大链附加噪声 n_add（量子测控 J3 · M4 低温电子学 · Caves 极限）：解析闭式 golden vs 复合 Simpson 求积候选 · 光子数",
        "metric": "amp_added_noise_photons",
        "oracle": "closed_form(n_add=(η/g)(1−e^{−gL}), z 处噪声 e^{−gz} 权重积分) + 复合 Simpson 数值求积独立_cross_check",
        "tol": 1e-6,
        "default_params": dict(B514_DEFAULT_PARAMS),
        "golden_fn": golden_b514,
        "candidate": "b514_amp_noise_cand",
        "candidate_desc": "复合 Simpson 数值求积（[0,L] 等分 n=256 段，权重 1,4,2,4,…,1，O(h⁴)）⇒ n_add=(η/g)·∫₀^L g·e^{−gz}dz。方法学独立：golden=解析积分闭式，cand=数值求积",
        "note": "golden = 量子测控与读出征程 J3（M4 低温电子学）的**分布式（行波）相位不敏感放大链附加噪声**闭式：z 处每单位长度产生 η 光子噪声、传播到输出被增益 e^{g(L−z)} 放大，输入参考（除总增益 e^{gL}）⇒ **n_add=∫₀^L(η/g)·g·e^{−gz}dz=(η/g)(1−e^{−gL})** —— **严格解析结果**；单位增益附加噪声 η/g=1/2 ⇒ **Caves 量子极限**（相位不敏感放大器），gL→∞ ⇒ n_add→1/2。🔴 **物理意义**：超导量子比特读出链的**第一级放大器**必须接近量子极限（JPA/TWPA 的 n_add≈1/2 光子），否则后级 HEMT（n_add≈10–20）的噪声虽被前级增益压低，系统仍受第一级限制；B514 给出**分布式增益-噪声权衡**的闭式，能力层 `lda_qeda/cryo_electronics.py` 用 Friis 级联 + Caves 极限实现完整噪声预算，`lda_qeda/control_closed_loop.py` 的 Ring G 与 M4 总装接线。candidate=**复合 Simpson 数值求积**（方法学独立；[0,L] 离散为 n 段，O(h⁴)）。实测默认档(η/g=0.5〔量子极限〕, g=0.5 /mm, L=10 mm ⇒ **golden=4.966310265005e-01**) **残差=4.015e-10**（**tol=1e-6**〔绝对口径〕⇒ **2490.8×** 余量；|golden|/tol=4.97e5；残差链 n=16→2.601e-05 → 32→1.640e-06 → 64→1.027e-07 → 128→6.423e-09 → **256→4.015e-10**，**比值 15.86/15.97/15.99/16.00×** ⇒ **O(h⁴)**〔复合 Simpson 标称阶〕，严格单调、残差>0 ⇒ **非**代数恒等；动态范围 6.48e4×）。🔴 **同源体检（实 grep 全仓核验）**：`Caves|n_add|附加噪声|量子极限|JPA|参量放大|级联噪声|noise_factor` 在 `BENCHMARK_DEFS` 内 **0 命中** ⇒ 低温放大链噪声族**零锚占用（本族首锚）**；与 **B467**（TIA 读出噪声底 kT/C）**三方分歧** —— ①**被测标量**：**附加噪声光子数 n_add**（无量纲/光子数）vs **输出 rms 噪声电压 v_n（µV）**②**物理构型**：**微波分布式参量放大链** vs **跨阻放大器反馈电阻热噪声**③**数值格式**：**复合 Simpson 求积** vs B467 的**时域冲激响应 Parseval 积分** ⇒ 计新锚。⚠️ **诚实边界**：η/g、g、L 为**设计示例量级**（非实测 PDK / 非商用放大器数据表）；模型为**理想分布式放大器**（忽略增益饱和、泵浦噪声、温度依赖）⇒ 只证「解析闭式 ⇄ 数值求积」一致 + Caves 极限物理链自洽，**不得作制造/性能宣称**；SOTA（商用 JPA 实际噪声）**未达如实标注**。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B515": {
        "title": "多参数 NV 传感交叉灵敏度解耦温度分量 τ̂（J4 量子传感系统集成 · M0 多参数传感）：Cramer 闭式解析反演 golden vs Landweber 迭代解耦候选 · 无量纲",
        "metric": "nv_multiparam_decoupling_temperature",
        "oracle": "closed_form(τ̂=det(S₁)/det(S), Cramer 法则 4×4 行列式按第一行 Laplace 展开 → 3×3 余子式手写展开) + Landweber 迭代解耦独立_cross_check",
        "tol": 1e-6,
        "default_params": dict(B515_DEFAULT_PARAMS),
        "golden_fn": golden_b515,
        "candidate": "b515_multiparam_decoupling_cand",
        "candidate_desc": "Landweber 迭代解耦（梯度下降最小二乘 x_{k+1}=x_k+τ*·Sᵀ(b−S·x_k)，固定**最优步长** τ*=2/(λ_min+λ_max) ⇒ 谱半径 ρ=(λ_max−λ_min)/(λ_max+λ_min)<1 恒收敛；k=320 步）⇒ 温度分量 τ̂_k。方法学独立：golden=Cramer 解析求逆（行列式展开），cand=迭代逼近",
        "note": "golden = 量子传感系统集成征程 J4（M0 多参数传感）的**多参数交叉灵敏度解耦解**：NV 色心的 ODMR 谱特征同时被**四参数**（①磁场 B：Zeeman `Δf=2γ_eB`、γ_e=28.024 MHz/µT ②温度 ΔT：零场劈裂温度系数 `dD/dT≈−74.2 kHz/K` ③轴向电场 E：Stark `dD/dE_⊥=17.0 kHz/(kV/cm)` ④应力 σ：`dD/dσ=1.4 kHz/MPa`）调制 ⇒ 读数方程 `b=S·x`（S=4×4 交叉灵敏度矩阵）是**四参数耦合线性组合**，「一次读数=一个参数」的朴素做法把交叉项误当本参数变化（**多参数串扰**）；解耦 = 解 `S·x=b` 得四参数真值。golden 用 **Cramer 法则**（4×4 行列式按第一行 Laplace 展开 → 3×3 余子式手写展开）解析求**温度分量** τ̂=det(S₁)/det(S)、S₁ = S 第 1 列被读数向量 b 替换 ⇒ **精确代数式（非迭代、非截断、非近似）**。🔴 **物理意义**：多参数解耦是多参数 NV 传感**可用性的物理前提**；温度分量是核心代表 —— QS-M2（`qs_m2.temperature_eta`）把温度当**噪声源**（污染磁灵敏度 η），本锚第一次把温度**升为被测量**并给出解耦估计 ⇒ 落点「温度既是被测参数、又是串扰源」这一多参数传感特有张力（缺口 G-QSYS-1）；能力层 `lda_l2/qs_j4_multiparam.py` 用同一物理链（物理系数 γ_e/dD/dT/dD/dE/dD/dσ → 无量纲响应矩阵 C → 解耦 → 条件数 κ / 噪声放大 N_amp）实现，实测 κ=**5.9586**、N_amp=**2.1262**、解耦残差 1.59e-08、签核 **ACCEPT**。candidate=**Landweber 迭代解耦**（方法学独立：解析行列式展开 vs 迭代逼近；固定最优步长 τ*=2/(λ_min+λ_max) ⇒ ρ<1 恒收敛，k=320 步）。实测默认档(coupling=1.0 ⇒ **golden=6.475252706753e-01**) **残差=6.634e-09**（**tol=1e-6**〔绝对口径〕⇒ **150.7×** 余量；|golden|/tol=6.48e5；残差链 k=64→1.217e-02 → 128→3.312e-04 → 192→8.996e-06 → 256→2.443e-07 → **320→6.634e-09**，**比值 36.74/36.82/36.82/36.82×** ⇒ **恒定**（扫描格等差 Δk=64 ⇒ 比值 = ρ^{−64} = **几何收敛**，与 Landweber 标称收敛率一致），严格单调、残差>0 ⇒ **非**代数恒等；动态范围 1.83e6×）。🔴 **判据 D 双向标定（实测，如实登记）**：κ 不能太小 —— 实测对角抬高族 κ=1.58 / 2.06 档**收敛过快**（k=64 即沉机器地板 1.11e-16，不可标定）⇒ 本档选 κ≈5.96 使「默认档残差 ∈[1e-10,1e-8] ∧ 动态范围 ≥1e4」同时成立。🔴 **同源体检（实 grep 全仓核验）**：`解耦|decoupl` **0 命中**、`多参数|multi_param|multiparam` **0 命中**、`交叉灵敏度|cross_sensitivity|sensitivity_matrix` **0 命中**、`cramer|伴随矩阵|adjugate` **0 命中**、`landweber|梯度下降|gradient_descent` **0 命中**、`条件数|condition_number` **0 命中** ⇒ **多参数解耦族零锚占用（本族首锚）**。与 **B473**（NV 单参数磁力计散粒极限灵敏度 η·T/√Hz）**三方分歧** —— ①**被测标量**：**归一化解耦解 τ̂**（四参数联立反演的一个分量，**无量纲**）vs **灵敏度谱密度 η（T/√Hz）**②**物理构型**：**四场耦合的观测方程组（交叉灵敏度矩阵 + 读数向量）** vs **单场 Ramsey 自由进动 + 误差传播**③**数值格式**：**Cramer 解析求逆 ⇄ Landweber 迭代解耦** vs **闭式代数 ⇄ 复指数演化核数值差商** ⇒ 计新锚（承 B452↔B33 先例）。与 **B478/B479**（QS-M4 **阵列**串扰：磁偶极近场串扰系数 X / 灵敏度恶化倍率 √(1+X_tot²)）三方分歧：①被测标量：**解耦反演解 τ̂** vs **串扰系数/恶化倍率**②构型：**单一 NV 内的四场参数耦合**（横跨**参数空间**）vs **相邻 NV 柱的空间磁偶极耦合**（横跨**空间**）③数值格式：**Cramer/迭代线性反演** vs **点偶极场数值积分 / MC 噪声功率叠加** ⇒ 计新锚（J4 章程 §1.2 已预设「集成串扰」改靶，本锚**不碰空间串扰族**）。与 **B476/B477**（几何）、**B482–B484**（标定/动态范围）被测标量均不同 ⇒ 非重复计数。⚠️ **诚实边界**：γ_e/dD/dT/dD/dE/dD/dσ 为**文献量级的设计示例**（非任何 foundry 实测标定）；响应矩阵 C 与读数向量 b 为**设计示例**（非实测 ODMR 谱拟合）；模型为**一阶线性化**（未建模高阶项、谱线非洛伦兹化、参数间非线性耦合）⇒ 只证「Cramer 闭式解析反演 ⇄ Landweber 迭代解耦」数值一致 + 多参数解耦物理链自洽，**不得作制造/性能宣称**，不报能效/TOPS/fJ-op。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B518": {
        "title": "低温布线束热负载 Q（J4 量子传感系统集成 · M3 封装热负载）：Wiedemann–Franz 电子热导有理闭式 golden vs RK4 积分定义 ODE 候选 · W",
        "metric": "cryo_wiring_heat_load",
        "oracle": "closed_form(Q=(A/L)·L₀/β²·{[(ρ₀+βT)−ρ₀·ln(ρ₀+βT)]}_{T_c}^{T_h}, L₀=π²k_B²/3e²) + RK4 积分定义 ODE 独立_cross_check",
        "tol": 1e-8,
        "default_params": dict(B518_DEFAULT_PARAMS),
        "golden_fn": golden_b518,
        "candidate": "b518_cryo_wiring_heat_cand",
        "candidate_desc": "RK4 积分定义 ODE dQ/dT=(A/L)·L₀·T/(ρ₀+βT)，Q(T_c)=0，从 T_c=4 K 到 T_h=300 K 步进 n=512 步 ⇒ Q(T_h)。方法学独立：golden=初等有理闭式（∫T/(ρ₀+βT)dT 的解析原函数），cand=数值积分",
        "note": "golden = 量子传感系统集成征程 J4（M3 封装热负载）的**低温布线束热负载**：无源稳态一维传导 ⇒ Q=(A/L)·∫_{T_c}^{T_h}k(T)dT（沿线温度积分）；**Wiedemann–Franz 电子热导** k_el(T)=L₀·T/ρ(T)（L₀=π²k_B²/(3e²)=2.44e-8 W·Ω/K² 为 **Lorenz 数**、物理常数），ρ(T)=ρ₀+βT 为铜的**两区简化电阻率**（低温杂质散射残差 ρ₀ + 电子–声子线性项 β）⇒ 令 u=ρ₀+βT 得 ∫T/(ρ₀+βT)dT=(1/β²)[u−ρ₀ln u] ⇒ **初等有理闭式 Q=(A/L)·L₀/β²·{[(ρ₀+βT)−ρ₀ln(ρ₀+βT)]}_{T_c}^{T_h}**（**精确解析结果、非截断近似**；β→0 退化纯 WF 极限 (A/L)L₀(T_h²−T_c²)/(2ρ₀)）。🔴 **物理意义**：4 K 冷台的**线束热负载**是「设计得出来」与「用得起来」之间的分水岭 —— 超导腿（SQUID）与低温 OPM 都必须把室温机架经线束漏入的热量压进稀释制冷机冷量预算；QS 器件征程（M0–M9，B473–B496）**24 锚全在器件物理**，本锚是**第一个系统级成本项**（缺口 G-QSYS-4）。candidate=**RK4 积分定义 ODE** dQ/dT=(A/L)·L₀T/(ρ₀+βT)（方法学独立：数值积分 vs 解析原函数；n=512 步）。实测默认档(ρ₀=1.0e-10 Ω·m, β=5.6e-11 Ω·m/K, A=1.0e-7 m², L=0.5 m, T_h=300 K, T_c=4 K ⇒ **golden=2.517894426405e-02 W**) **残差=3.213e-11**（**tol=1e-8**〔绝对口径 · 对 golden≈2.52e-2 即相对 1.3e-9〕⇒ **311.2×** 余量；golden/tol=2.52e6；残差链 n=32→1.019e-06 → 64→1.003e-07 → 128→7.596e-09 → 256→5.053e-10 → **512→3.213e-11**，**比值 10.15/13.21/15.03/15.73×** ⇒ 趋向 **O(h⁴)**〔RK4 标称阶 · 粗端未入渐近区故偏低〕，严格单调、残差>0 ⇒ **非**代数恒等；动态范围 3.17e4×）。🔴 **判据 D 前提（实测踩过，如实登记）**：被积函数必须**非线性** —— 若 ρ(T)≡ρ₀（线性被积函数），RK4 对多项式**精确** ⇒ 残差恒 ~1e-16 ⇒ 判据 D 不成立（超收敛/代数恒等陷阱，同 B28）；故本锚取 **β>0** 的有理非线性。🔴 **同源体检（实 grep 全仓核验）**：`heat_load / Wiedemann / wiring / thermal_load / 低温布线` 在 `BENCHMARK_DEFS` 内 **0 命中** ⇒ **低温布线热负载族零锚占用（本族首锚）**；与 **B465**（圆柱壳**径向热阻** R_th=ln(r_o/r_i)/(2πkL) · **K/W** + 1D FD）**三方分歧** —— ①**被测标量**：**热负载 Q（W）** vs **热阻 R_th（K/W）**②**物理构型**：**金属线束的 WF 电子热导跨 300 K→4 K** vs **圆柱壳稳态径向导热（无源温区固定）**③**数值格式**：**RK4 积分定义 ODE（dQ/dT）** vs **FD 守恒界面通量的 Laplace BVP**；与 **B466**（密集阵列**热串扰比** · 横向阻尼扩散 · **无量纲比值**）同样三方分歧（标量/构型/格式均异）⇒ 计新锚（承 B452↔B33 先例）。⚠️ **诚实边界**：ρ₀/β/A/L/T_h/T_c 为**设计示例量级**（铜的两区简化电阻率模型，非实测线束 PDK）；未建模**辐射热负载**（同轴线黑体传播）、超导线非线性热导、接头热阻、多级冷台分配 ⇒ 本锚为**电子热导通道的下界估算**，只证「有理闭式 ⇄ 数值积分」一致 + 系统级热负载链自洽，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B519": {
        "title": "分发后两体纠缠保真度 F（J5 量子网络与接口 · M0 纠缠分发）：Werner 族解析闭式 golden vs 4×4 密度矩阵距离步进 RK4 候选 · 无量纲",
        "metric": "entanglement_distribution_fidelity",
        "oracle": "closed_form(F=(1+3p)/4, p=exp(−L/L_depol), Werner 族) + 4x4 density-matrix distance-stepping RK4 independent_cross_check",
        "tol": 1e-8,
        "default_params": dict(B519_DEFAULT_PARAMS),
        "golden_fn": golden_b519,
        "candidate": "b519_entanglement_distribution_fidelity_cand",
        "candidate_desc": "距离域 Liouvillian dρ/dL=−(ρ−I/4)/L_depol 的 4×4 密度矩阵四阶 RK4 步进（16 个实分量全演化，n=256 步走完 100 km），末端读 F=Tr(ρ·ρ_ideal)。方法学独立：golden=Werner 族解析闭式，cand=距离步进数值时间推进（离散参数=步数 n）",
        "note": "golden = 量子网络与接口征程 J5（M0 纠缠分发）的**分发后两体纠缠保真度**：初始 Bell 态 |Φ+⟩=(|00⟩+|11⟩)/√2 经**退极化信道**（偏振去相干）后进入 **Werner 族** ρ(L)=p(L)·|Φ+⟩⟨Φ+|+(1−p(L))·I/4，p(L)=exp(−L/L_depol)，对理想态取重叠 Tr(ρ·ρ_ideal)=p+(1−p)/4 ⇒ **F(L)=(1+3p(L))/4**（**Werner 族教科书闭式，非迭代非截断**）。🔴 **物理意义**：这是 J1–J4 全部「芯片内 / 实验室距离」建模之外**第一次引入公里级距离**维度 —— J5 的独立变量是**光纤链路长度 L**，信道把指数衰减的相干度折算成纠缠质量，是「多节点量子网络」可用性的物理前提（缺口 G-QNET-1）。candidate=**4×4 密度矩阵沿距离的 RK4 步进**（方法学独立：解析闭式 vs 数值时间推进；ρ(0)=|Φ+⟩⟨Φ+|，dρ/dL=−(ρ−I/4)/L_depol，n=256 步）。实测默认档(L=100 km, L_depol=22 km ⇒ **golden=2.579615098464825e-01**) **残差=3.042e-11**（**tol=1e-8**〔绝对口径 · 对 golden≈0.258 即相对 1.2e-10〕⇒ **328.7×** 余量；golden/tol=2.58e7；残差链 n=16→2.4914e-06 → 32→1.3823e-07 → 64→8.1415e-09 → 128→4.9399e-10 → **256→3.0420e-11**，**比值 18.02/16.98/16.48/16.24×** ⇒ 趋向 **O(h⁴)**〔RK4 标称阶 · 粗端未入渐近区故偏高〕，严格单调、残差>0 ⇒ **非**代数恒等；动态范围 8.19e4×）。🔴 **判据 D 双向标定（实测）**：被观测量必须是**线性 ODE 的非平凡数值解** —— RK4 对线性系统给出 R(hλ) 而非 e^{hλ}（差 O((hλ)⁵)），故只要 hλ 不落超收敛区即浮出真残差（实测 hλ≈0.0178 @n=256）；若把 n 推到 hλ≪1 则残差沉地板（同 B10 过度收敛区陷阱）。🔴 **同源体检（2026-10-15 实 grep `BENCHMARK_DEFS` 全量核验）**：`werner` **0 命中**；`entangl / bell / EPR / concurrence / CHSH / teleport` 在锚定义内 **0 命中**（唯一近邻为 part1.py:221「EPR 哈密顿量对角化(pyEPR/Ansys)仅作外部 ORACLE」**文本非锚**）⇒ **纠缠保真族零锚占用（本族首锚）**。与 **B453**（相干态经损耗通道保真度 · **单模** · 静态 Fock 截断 **Kraus 算子求和**）**三方分歧** —— ①**被测标量**：**两体纠缠态保真度**（Werner 族 · 含纠缠语义）vs **单模相干态**输入-输出重叠②**物理构型**：**含公里级信道传输的两体态**（距离 L 为自变量）vs **本地单模振幅阻尼**（无距离）③**数值格式**：**距离步进 RK4 超算子**（离散参数=步数）vs **静态 Kraus 算子代数**（离散参数=Fock 截断维数）⇒ 计新锚（本条**刻意避开 Kraus 求和格式**，见 `qnet_channel.py` 体检注）；与 **B10**（单量子比特门保真度·退相干极限 · 平均门保真度 (3+2e^{−t/T2}+e^{−t/T1})/6 · 4×4 PTM）三方分歧（标量/构型/格式均异）；与 **B502/B503**（QEC transversal CNOT / lattice surgery 合并保真度 · 离散逻辑门）三方分歧；另 `fiber` 命中为**阶跃光纤 LP01 模式折射率**锚（part5 `fiber_lp01_neff_fd`）⇒ 那是**模式本征值求解**，与「信道损耗/纠缠保真」**物理量不同** ⇒ 非重复计数（承 B452↔B33 先例）。⚠️ **诚实边界**：L=100 km / L_depol=22 km / α=0.2 dB/km 为**公开典型值 / 设计示例**（非任何实测链路）；信道模型为**单一退极化通道**（未建模双折射随机游走、光纤非线性、探测器暗计数、存储-检索损耗）⇒ 只证「Werner 闭式 ⇄ 距离步进 RK4」数值一致 + 纠缠分发物理链自洽，**不得作制造/性能宣称**，不报能效/TOPS/fJ-op。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B520": {
        "title": "光子不可分辨性 → HOM 干涉可见度 V（J5 量子网络与接口 · M1 纠缠源）：高斯波包重叠解析闭式 golden vs 复合梯形时间域数值积分候选 · 无量纲",
        "metric": "hom_interference_visibility",
        "oracle": "closed_form(V=|M|^2, M=gaussian wavepacket overlap, σ1=σ2) + composite-trapezoid time-domain numerical integration independent_cross_check",
        "tol": 3e-9,
        "default_params": dict(B520_DEFAULT_PARAMS),
        "golden_fn": golden_b520,
        "candidate": "b520_hom_visibility_cand",
        "candidate_desc": "复合梯形法时间域数值积分 ∫ψ₁*(t)ψ₂(t)dt ⇒ |M|²（两个高斯波包，含时间延迟 δt 与频率差 δω；n=28 步）。方法学独立：golden=高斯积分解析闭式，cand=数值求积",
        "note": "golden = 量子网络与接口征程 J5（M1 纠缠源 · 光子不可分辨性）的 **HOM 干涉可见度**：两个高斯波包 ψ_i(t) ∝ (2πσ_i²)^{−1/4}·exp(−(t−t_i)²/(4σ_i²))·exp(−iω_i t) 的重叠幅度 M=∫ψ₁*(t)ψ₂(t)dt ⇒ **V=|M|²**（两光子波包**不可分辨**时 HOM dip 越深、可见度越高）。闭式（σ₁=σ₂=σ）：**V = exp(−δt²/(4σ²))·exp(−δω²σ²)**（配方后两次用 ∫exp(−ax²+bx)dx=√(π/a)·exp(b²/4a) ⇒ **精确解析、非截断**）。🔴 **物理意义**：M0 解决了「**分发后**纠缠态还剩多少保真」（信道侧）；本条解决「**源侧**两个光子是否真的不可分辨」—— 光子频率/时间不匹配会**直接限制纠缠交换的干涉质量**，是纠缠源可用性的第一个判据（缺口 G-QNET-2）。candidate=**复合梯形法时间域数值积分** `∫ψ₁*ψ₂dt`（复值被积函数，n=28 步）。实测默认档(σ=1 ps, δt=2σ, δω=1/σ ⇒ **golden=1.353352832366127e-01**) **残差=1.0451e-11**（**tol=3e-9**〔绝对口径 · 对 golden≈0.135 即相对 7.7e-11〕⇒ **287.1×** 余量；golden/tol=4.51e7；残差链 n=8→2.709e-01 → 12→2.450e-02 → 16→7.645e-04 → 20→6.735e-06 → 24→1.611e-08 → **28→1.045e-11**，**比值 11.06/32.05/113.51/418.02/1541.59×** ⇒ **超几何收敛**〔比值单调递增、**非幂律** —— 高斯×振荡被积函数的解析性所致；如实登记不假称「恰 4」，同 B453 截断型先例〕，严格单调、残差>0 ⇒ **非**代数恒等；动态范围 **2.59e10×**）。🔴 **判据 D 双向标定（实测踩过，如实登记）**：**candidate 刻意不用 Simpson** —— 被积函数含振荡因子 exp(iδωt)，Simpson 在粗端**非单调**（实测 n=8→10 残差反升 2.97e-02→3.17e-01），判据 D 不成立；**复合梯形 O(h²)** 给出严格单调残差链。另一陷阱：n≥64 后残差沉机器地板（超收敛区），故扫描格收在 **n≤28** 的误差主导区。🔴 **同源体检（2026-10-15 实 grep `BENCHMARK_DEFS` 全量核验）**：`HOM` / `hom_` / `不可分辨` / `indistinguish` / `bunching` / `anti-bunching` / `双光子` / `two_photon` / `visibility` 在锚定义内 **0 命中** ⇒ **HOM 干涉族零锚占用（本族首锚）**；⚠️ `g2` 命中 **B455**（`heralded_g2_0` · 条件态 g²(0)）⇒ 本条靶锁「**可见度**」而非 g²(0)。🔴 **与 `lda_qeda/loqc_states.py` 既有 `hom_*` 函数族的分歧（关键 · 防同源）**：既有族（`hom_coincidence` / `hom_coincidence_closed_form` / `hom_visibility`）的**自变量是分束器角度 θ**（假设两光子**完全不可区分**，V(θ) 在 50:50 处理论值 1）；**本条的自变量是波包参数（时间延迟 δt / 频率差 δω）**——即「**光子到底有多不可分辨**」这一维（既有族完全没有）。三方分歧：①**被测标量**：**含波包不可分辨性的时间域可见度 V(δt,δω)** vs **BS 分束比维度的 V(θ)**②**物理构型**：**两个有限带宽高斯波包（含延迟与频率差）** vs **理想不可区分单频光子 + 可变分束器**③**数值格式**：**高斯积分解析闭式 ⇄ 复合梯形时间域数值积分** vs **解析 cos²(2θ) ⇄ 永久式 prob_of** ⇒ 计新锚（承 B452↔B33 先例）。⚠️ **诚实边界**：σ=1 ps / δt=2σ / δω=1/σ 为**设计示例量级**（非实测光谱）；只建模**两个理想高斯波包**（未含真实 NV 发射线型、腔滤波、探测器时间抖动、多光子成分）⇒ 只证「高斯重叠闭式 ⇄ 梯形数值积分」数值一致 + 光子不可分辨性物理链自洽，**不得作制造/性能宣称**。零商业依赖（纯 numpy + math；零 RNG）。",
    },
    "B521": {
        "title": "中继站期望交换产出数 N_swap（J5 量子网络与接口 · M2 中继）：生成窗 ⊗ 存储窗 嵌套卷积初等闭式 golden vs 单重复合 Simpson 求积候选 · 无量纲",
        "metric": "repeater_swap_yield",
        "oracle": "closed_form(N_swap=κλ/(γ−λ)·[(1−e^{−λT})/λ−(1−e^{−γT})/γ], γ=μ+κ) + composite-simpson quadrature independent_cross_check",
        "tol": 1e-7,
        "default_params": dict(B521_DEFAULT_PARAMS),
        "golden_fn": golden_b521,
        "candidate": "b521_repeater_yield_cand",
        "candidate_desc": "单重复合 Simpson 求积（n 段 · 偶数）∫₀ᵀh(t)dt，h(t)=(e^{−λt}−e^{−γt})/(γ−λ)；λ=1/T_gen · μ=1/T_mem · κ=1/T_swap；残差 = Simpson 截断误差（实测从下方趋近 O(h⁴)）",
        "note": "golden = 量子网络与接口征程 J5（M2 量子中继 · G-QNET-3）的 **中继站期望交换产出数 N_swap**：三态竞争（态0 空闲等待生成 / 态1 已存储存活 / 态2 已交换产出），速率 = 生成 λ=1/T_gen · 存储退相干 μ=1/T_mem · 交换消耗 κ=1/T_swap ⇒ P₀(t)=e^{−λt}、P₁(t)=∫₀ᵗλ e^{−λt′}e^{−γ(t−t′)}dt′（γ=μ+κ）⇒ **N_swap(T)=κ∫₀ᵀP₁dt=κλ∫₀ᵀ∫₀ᵗ e^{−λt′}e^{−γ(t−t′)}dt′dt**（生成窗 ⊗ **存储窗** 嵌套卷积；**存储窗因子 e^{−t/T_mem} 即章程要求的「P_succ 含 ∫e^{−t/T_mem}dt」落点**）⇒ 闭式 **κλ/(γ−λ)·[(1−e^{−λT})/λ−(1−e^{−γT})/γ]**（**初等、精确、非截断**；γ=λ 退化档取极限 (κ/λ)[1−e^{−λT}(1+λT)]）⇄ **单重复合 Simpson 求积**（与闭式方法学独立；实测 golden=**5.369673805632804e-01** · tol 1e-7 · 残差 **4.1157e-10（243.0×）** · 残差链 n=8→4.1444e-04 … n=256→4.1157e-10 · 比值 **15.52/15.88/15.97/15.99/16.00×** ⇒ 从**下方**趋近 **O(h⁴)**〔复合 Simpson 标称阶，粗端未入渐近区故略低于 16，如实登记不假称「恰 16」〕 · 动态范围 **1.007e6×** · |golden|/tol=5.37e6× · 扰动最弱键 t_gen_s ×1.1 ⇒ **9.7678e-03 = 9.77e4× tol**〔C5 窗口极大〕）。🔴 **与 `passivity` 锚（B19「无源链路 无增益 max|T|≤1」）物理地位不同**：B19 判的是**光子链路传递矩阵**不得被放大；本条是**中继站的产出计数**——既非传递矩阵、亦非增益比值，二者无重叠（章程 R4 首行声明义务）。🔴 **同源体检（2026-10-15 实 grep benchmark_defs 全量）**：`中继|repeater|relay|swapping|交换|exchange` **4 处命中全为其它锚 note 中的普通用词**（B491 数密度 / B506 CR 门 / B507 ZZ / B520 HOM）⇒ **中继族零锚占用（本族首锚）**；`吞吐|throughput|产出|rate_equation` **0 命中**；`T_mem|存储时间|存储窗` 仅 1 处（B519 note 用词）⇒ **存储时间维度零占用**；`增益|gain` 另有 B482（频锁鉴别器**斜率**）· B467/B488（跨阻/磁通聚焦）· B19（passivity）⇒ 物理量均不同。⚠️ **矩阵指数族 B221/B222**（`状态转移矩阵 exp(At)[0,1]=−sin t` · 候选 scaling–squaring + Taylor 截断）与 golden「生成元指数」**结构邻接** ⇒ 三方分歧：①被测标量（**κ 加权的累积产出计数∫P₁dt** vs 旋转矩阵元素 −sin t）②物理构型（**三态吸收型 Markov 生成-存储-交换竞争**（含三时间尺度）vs 纯旋转线性系统）③数值格式（**单重复合 Simpson 求积** vs scaling–squaring + Taylor 截断）⇒ 计新锚。🔴 **嵌套双重复合 Simpson 实测被否**（内层域随外层节点变化 ⇒ 主误差退化 O(h²)、比值恒 2.00、动态范围仅 ~30× < 章程 R2 的 1e4× 线）⇒ 如实登记不采用。⚠️ **诚实边界**：T_gen=50 µs / T_mem=160 µs / T_swap=100 µs / T_obs=200 µs 为**设计示例量级**（非任何实测中继链）；只建模**三态竞争这一最小骨架**（未含多段链级联、交换门保真度、探测器效率、多光子噪声）⇒ 只证「嵌套卷积闭式 ⇄ Simpson 求积」数值一致 + 中继产出计数物理链自洽，**不得作制造/性能宣称**，不报能效/TOPS/fJ-op。零商业依赖（纯 math；零 RNG）；**LLM 不进判决路径**。",
    },
    "B522": {
        "title": "微波-光换能效率 η（J5 量子网络与接口 · M3 换能）：协同度极限 × 有限探测带侧带重叠 分层 log+arctan 闭式 golden vs 有限窗复合 Simpson 求积候选 · 无量纲",
        "metric": "microwave_optical_transduction_efficiency",
        "oracle": "closed_form(η=4C/(1+C)²·N(Ω_c)/D, C=4G²/(κ_mw·γ_mech), N=∫_{−Ω_c}^{Ω_c}L_aL_b, D=∫_{−∞}^{∞}L_aL_b; 分层 log+arctan 精确原函数) + composite-simpson finite-window quadrature independent_cross_check",
        "tol": 1e-7,
        "default_params": dict(B522_DEFAULT_PARAMS),
        "golden_fn": golden_b522,
        "candidate": "b522_transducer_efficiency_cand",
        "candidate_desc": "有限窗内复合 Simpson 求积（n=128 段偶数）N(Ω_c) ÷ 解析全带 D，再乘协同度极限 η_peak=4C/(1+C)²；残差 = 窗内 Simpson 截断误差（实测从下方趋近 O(h⁴)）",
        "note": "golden = 量子网络与接口征程 J5（M3 微波-光换能器 · G-QNET-4）的 **跨频段转换效率 η**（三因子合成）：① **协同度极限效率** `η_peak = 4C/(1+C)²`（阻抗匹配最优档），`C = 4G²/(κ_mw·γ_mech)` —— **与 `lda_l2.qs_m3c.cooperativity_from_g` 同律**（能力层逐位对拍，见 `qnet_transducer`）；② **有限探测带侧带重叠（归一化）** `η_band = N(Ω_c)/D`：微波腔洛伦兹响应中心 −Δ、半宽 γ；光腔中心 +Δ、半宽 γ ⇒ `N(Ω)=∫_{−Ω}^{Ω}L_aL_b dω`（**只接收带内部分** · 硬件带宽受限）· `D=∫_{−∞}^{∞}L_aL_b dω`（全带可达），`L_x(ω)=γ/((ω−ω_x)²+γ²)` ⇒ 闭式（**精确 · 非截断**）：`N=γ²[F(Ω)−F(−Ω)]`（F 为分层 log+arctan 精确原函数，分层系数由 4 个幂次匹配条件解出）· `D=π[γ_b/R_a+γ_a/R_b]`（`R_a=(a−b+iγ_a)²+γ_b²`）⇄ **有限窗内复合 Simpson 求积**（与闭式方法学独立；实测 golden=**1.1253071063e-02** · tol 1e-7 · 残差 **6.7050e-11（1491.4×）** · 残差链 n=8→3.7736e-06 … n=128→6.7050e-11 · 比值 **14.33/15.50/15.87/15.97×** ⇒ 从**下方**趋近 **O(h⁴)**〔复合 Simpson 标称阶，粗端未入渐近区故略低于 16，如实登记不假称「恰 16」〕 · 动态范围 **5.628e4×** · |golden|/tol=1.125e5× · 扰动最弱键 kappa_mw ×1.1 ⇒ 7.2e3× tol〔C5 窗口极大〕）。🔴 **双独立闭式互证**（自检项）：分层 log+arctan ⇄ **复留数 + 复对数**（共轭对虚部**精确相消**）相对差 **1.51e-15**。🔴 **同源体检（2026-10-16 实 grep benchmark_defs 全量）**：`侧带|sideband|upconv|downconv|频率转换|frequency_conv` **0 命中** ⇒ **跨频段换能族零占用（本族首锚）**；`换能|transduc|光机|optomech|电光|electro_optic` 4 处命中 = **B28（MZM 调制器半波电压 Vπ · Pockels）** + note 用词 + `.pyc` ⇒ **无换能锚**；`效率|efficiency` 共 8 锚（NA 立体角收集 / 光栅耦合 / 光纤-波导对准 / 最优色心深度 / 热光相移 / 米氏散射 Q_scat / 绝热锥度）**全为同频段光学效率**（vs 本条**跨频段**微波↔光）；`cooperativ|协同度` 仅 1 处 note 用词 ⇒ 协同度本身无锚。🔴 **三方分歧**：① 被测标量（**跨频段转换效率 η（无量纲）** vs B28 的**调制电压 Vπ（V）**）② 物理构型（**微波腔↔光腔双腔换能 + 泵浦耦合 G + 有限探测带** vs 同频段行波 MZM 相位调制（λ/n/r/Γ/L 几何式））③ 数值格式（**有限窗内复合 Simpson 求积**（有理函数代数尾）vs 解析 Vπ 几何公式）⇒ 计新锚。⚠️ **B508（FDM 多音读出相邻通道频谱重叠串扰比）**亦以「两洛伦兹频谱重叠」为闭式 ⇒ **如实披露邻接**：本条的分歧点是「**有限探测带截断**」（`N(Ω_c)/D` 比值结构）+ 跨频段物理量 + 双腔换能构型（非重复计数，承 B452↔B33 先例）。🔴 **章程硬纪律②（效率跨量级）**：本条 η 为 O(1e-2)、tol 取**绝对** 1e-7（相对 ⇒ 8.9e-6），**判据「绝对 ∨ 相对」并列登记、不用 `max`**（不得选择性披露）。⚠️ **诚实边界**：G=2π×5 MHz / κ_mw=2π×2 MHz / γ_mech=2π×2 MHz（⇒ C=25）/ γ=2π×1 MHz / Δ=2π×10 MHz / Ω_c=2π×5 MHz 为**设计示例量级**（非任何实测换能器件）；只建模**两洛伦兹响应 × 有限探测带**这一最小骨架（未含机械模热噪声、多模复用、脉冲泵浦时序、非线性饱和、双向同时工作）⇒ 只证「分层闭式 ⇄ Simpson 求积」数值一致 + 跨频段换能效率物理链自洽，**不得作制造/性能宣称**，不报能效/TOPS/fJ-op。零商业依赖（纯 math + numpy；零 RNG）；**LLM 不进判决路径**。",
    },
}
