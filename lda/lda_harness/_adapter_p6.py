# -*- coding: utf-8 -*-
"""验证适配器 · 分片 6/6（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

覆盖原文件 L5793..L6786（100 个顶层定义）。正文**逐字节**取自原文，不重排、不重格式化。
🔴 装配顺序由 `verification_adapters.py` 的 import 次序决定，勿单独调整。
"""

from __future__ import annotations

from ._adapter_core import (
    _get_batch_b16, _get_batch_b16_numeric, _get_batch_b17_numeric, _get_batch_b18_numeric,
    _get_batch_b19_numeric, _get_batch_b20_numeric, _get_batch_b21_numeric, _get_batch_b567,
    _register_candidate,
)

from typing import (
    Any,
)

from .verification_spec import (
    VerificationSpec,
)

@_register_candidate(
    "rib_mmi_recon",
    "脊形 MMI 全场模态重构：反演核心折射率(基模≡器件 n_eff) + 精确解 TE 平板本征方程 "
    "+ 输入场按全部导模展开沿 z 精确传播 + 双度量联合定位 1×2 首像 "
    "（抛物线闭式 golden 方法学不同源；残差 = 抛物线近似固有误差，~1–4%）")
def _b16_rib_mmi_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B16 独立候选：脊形 MMI 1×2 自成像长度（全场模态重构）。

    与 golden `(9/4)·n_eff·W_e²/λ`（抛物线色散闭式）方法学独立：
      · 反演 core 折射率使平板基模 ≡ 器件 n_eff（对象一致，修正 slab≠rib）；
      · 精确解 tan/cot 本征方程得全部导模 {ψ_m, β_m}（非抛物线截断）；
      · 输入场按 {ψ_m} 展开、沿 z 精确传播，用「双像重叠 + 双瓣对比」联合判据
        定位首个 1×2 双像 ⇒ **不套用任何 (9/8)/(3) 成像因子**。
    返回 Python 原生 float（numpy 纪律）。
    """
    p = spec.params
    m = _get_batch_b16()
    return float(m.rib_mmi_selfimaging_length(
        float(p["W_e"]), float(p["n_eff"]), float(p["wl"])))

@_register_candidate(
    "ybranch_eme",
    "Y 分支双芯超模 EME：EIM 垂向降维 + 锥区逐片解**完整横向 Helmholtz 本征问题**"
    "（无旁轴假设）+ 模式重叠矩阵级联 ⇒ 末片导模功率和 T，分束损耗 = 3.0103 "
    "− 10log10(T)。与 golden 的唯象拟合式方法学不同源，不套任何成像/拟合因子")
def _b5_ybranch_eme_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B5 独立候选：Y 分支 1×2 分束插入损耗（双芯超模 EME 全场传播）。

    golden = `oracle_field._ybranch_overlap` 唯象离线估计 3.0 + 0.4·(θ/10)²（3.4 dB）
    cand   = 见 `_batch_b567_numeric.ybranch_split_loss_dB`：
             ① EIM 把垂向结构降维成横向问题芯折射率；
             ② 锥区按 z 切片，每片解完整横向 Helmholtz 本征问题；
             ③ 输入基模片内精确模态传播 + 片间重叠矩阵投影；
             ④ 末片导模功率和 T ⇒ 分束损耗 = 3.0103 − 10·log10(T)。

    **方法学独立性**：候选全程不知道 golden 是多少，也不调用任何拟合式；
    它只解亥姆霍兹方程。golden 的 0.4·(θ/10)² 是唯象拟合（二次），候选的
    excess（0.008–0.061 dB, θ∈[5°,20°]）是从 Maxwell 方程算出的实测缺口 —
    两者的 θ 依赖**形状完全不同**（拟合二次 vs 严格近线性小量）。

    ⚠️ 诚实边界：本锚 tol=1.0 dB **远宽于**候选的参数响应幅度（±10% 扰动仅
    ~0.005 dB，因锥长随 θ 自相似、T 近乎不变）⇒ 本锚**无参数判别力**（与 B8
    同型），只回答「是否接近理想均分下限」，不回答精度。故**不进 PERTURB_SPEC**
    （逐参数扰动打不穿 tol，非缺陷而是几何本身性质）。
    """
    p = spec.params
    m = _get_batch_b567()
    return float(m.ybranch_split_loss_dB(
        float(p["w_core"]), float(p["h_core"]), float(p["n_si"]),
        float(p["n_clad"]), float(p["wl"]), float(p["theta_deg"])))

@_register_candidate(
    "grating_fp",
    "光栅耦合器峰值效率首原理分解：η_dir(上下包层对称 ⇒ 一阶衍射上/下功率相等 = 1/2)"
    " × η_ov(光栅指数辐射场 ⊗ 单模光纤高斯模 MFD=10.4µm 的模场重叠，对 α 取设计最优)"
    " × F(ff)=sin(π·ff)（方波一阶傅里叶强度） × M=exp(−(Δβ·L_g/2)²)（光栅方程相位匹配）。"
    "与 golden 的设计守则常数 0.5 方法学不同源，也不引用 E8 的引擎模型")
def _b6_grating_fp_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B6 独立候选：光栅耦合器峰值耦合效率（首原理四因子分解）。

    golden = 设计守则锚常数 0.5（`_b6_oracle` 需 Tidy3D key，缺失 ⇒ 回退）
    cand   = `_batch_b567_numeric.grating_coupler_eff`：
             η = η_dir · η_ov · F(ff) · M
             · η_dir = 1/2 —— 无底部反射镜、上下包层对称 ⇒ 一阶衍射向上/向下
               功率相等（**由对称性推出**，非经验常数）；
             · η_ov = 0.7846 —— 均匀光栅辐射场（振幅 ∝ exp(−αz/2)）与高斯光纤模
               （w0=5.2µm）的归一化模场重叠，对 α 取设计最优（「峰值」语义）；
             · F(ff) = sin(π·ff) —— 方波光栅介电常数一阶傅里叶强度（ff=0.5 → 1）；
             · M = exp(−(Δβ·L_g/2)²) —— 光栅方程相位匹配因子（L_g=20 周期）。

    **方法学独立性**：候选不引用 0.5，也不引用 E8 的 `0.5·sin²(πff)·exp(−θ²/2σ²)`
    （后者含 σ=15° 唯象倾斜散布参数）。本候选的每一因子都是几何/材料参数的
    闭式或数值积分，无待标定系数。

    ⚠️ 诚实边界（写进 note）：
      1. η_dir=1/2 假设**无底部反射镜且上下包层对称**；真实 SOI 有 Si 衬底反射
         （方向性可 >1/2），但 spec 未给 BOX 厚度 ⇒ 无法建模，取保守对称值。
      2. 光纤模场取标准 SMF-28（MFD=10.4µm）；spec 未给光纤参数。
      3. 残差 |0.3909−0.5| = 0.109 < tol 0.15：**物理含义明确** —— 设计守则 0.5
         是「η_ov→1 的理想模场匹配」上限（= 无镜面光栅的理论天花板），
         本候选给出真实均匀光栅（η_ov=0.785）的可达值 ⇒ 设计守则偏乐观 22%。
    """
    p = spec.params
    m = _get_batch_b567()
    return float(m.grating_coupler_eff(
        float(p["wl"]), float(p["n_si"]), float(p["n_clad"]),
        float(p["period"]), float(p["ff"]), float(p["theta_deg"])))

@_register_candidate(
    "crossing_cmt",
    "波导交叉串扰双芯超模/CMT 本征解：gap 相隔双芯横向剖面 Helmholtz 本征解 "
    "→ even/odd 超模有效折射率 n_e/n_o → 拍频 κ=π|n_e−n_o|/λ → 串扰 "
    "sin²(κ·L_eff)（L_eff=芯宽）。与 golden 的设计守则锚、以及已撤出的 2D "
    "FDTD 均方法学不同源")
def _b7_crossing_cmt_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B7 独立候选：波导交叉串扰（双波导超模 / CMT）。

    golden = 设计守则锚 −40 dB（`B7_DESIGN_ANCHOR`；离线 2D FDTD 已于 v0.9.82
             撤出 golden 调度、降级为机理诊断量）
    cand   = `_batch_b567_numeric.crossing_crosstalk_dB`：
             κ = π·|n_even − n_odd|/λ，串扰 = 10·log10(sin²(κ·L_eff))，
             其中 n_even/n_odd 由双芯横向折射率剖面的**完整 Helmholtz 本征解**
             严格给出（`eigh_tridiagonal`），L_eff = 芯宽（交叉耦合段量级估计）。

    **方法学独立性**：候选不引用 −40，也不调用 FDTD；它只解本征值问题。
    参数响应单调且物理正确：gap 0.1/0.2/0.3 µm → −24.96/−35.36/−45.72 dB；
    w_core 0.4/0.5/0.6 µm → −32.59/−35.36/−37.75 dB。

    ⚠️ 诚实边界（同时写进 `benchmarks.BENCHMARK_DEFS["B7"]["note"]`）：
      1. |−35.36 − (−40)| = 4.64 dB 占 tol 5.0 窗口的 **93%** —— **边缘通过**；
      2. L_eff = 芯宽 是交叉耦合段的量级估计，非严格场解；
      3. `gap` 对 90° 十字的几何语义在原锚中未定义，本模型按「两臂间距」解释，
         gap 响应仅供趋势参考（故本锚**进 PERTURB_SPEC 的不包含 gap 语义断言**）；
      4. 与锚定器件实测 −41±2 dB 的彻底对齐需 **3D 全波 + 真实 taper 版图**
         （T2 级缺口，同 E4/E7）。
    """
    p = spec.params
    m = _get_batch_b567()
    return float(m.crossing_crosstalk_dB(
        float(p["w_core"]), float(p["gap"]), float(p["wl"]),
        float(p["n_si"]), float(p["n_clad"])))

@_register_candidate(
    "b265_burgers_tanh_cand",
    "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立")
def _b265_burgers_tanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b265(float(p["c"]), float(p["nu"])))

@_register_candidate(
    "b266_burgers_tanh_cand",
    "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立")
def _b266_burgers_tanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b266(float(p["c"]), float(p["nu"])))

@_register_candidate(
    "b267_burgers_tanh_cand",
    "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立")
def _b267_burgers_tanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b267(float(p["c"]), float(p["nu"])))

@_register_candidate(
    "b268_burgers_tanh_cand",
    "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立")
def _b268_burgers_tanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b268(float(p["c"]), float(p["nu"])))

@_register_candidate(
    "b269_burgers_tanh_cand",
    "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立")
def _b269_burgers_tanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b269(float(p["c"]), float(p["nu"])))

@_register_candidate(
    "b270_burgers_tanh_cand",
    "u(x*,T) 由显式 RK4 时间推进 + 二阶中心差分（对流与扩散均中心）导出 ↔ tanh 行波闭式 c·[1−tanh(cξ/2ν)]，方法学独立")
def _b270_burgers_tanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b270(float(p["c"]), float(p["nu"])))

@_register_candidate(
    "b271_expn_simpson_cand",
    "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立")
def _b271_expn_simpson_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b271(int(p["nn"]), float(p["x"])))

@_register_candidate(
    "b272_expn_simpson_cand",
    "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立")
def _b272_expn_simpson_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b272(int(p["nn"]), float(p["x"])))

@_register_candidate(
    "b273_expn_simpson_cand",
    "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立")
def _b273_expn_simpson_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b273(int(p["nn"]), float(p["x"])))

@_register_candidate(
    "b274_expn_simpson_cand",
    "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立")
def _b274_expn_simpson_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b274(int(p["nn"]), float(p["x"])))

@_register_candidate(
    "b275_expn_simpson_cand",
    "E_n(x) 由区间 [1,60] 截断 + 复合 Simpson（2N+1 等距节点）数值求积导出 ↔ 特殊函数闭式库值，方法学独立")
def _b275_expn_simpson_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b275(int(p["nn"]), float(p["x"])))

@_register_candidate(
    "b276_haar_mra_cand",
    "V_J 正交投影由 2^K 等距采样逐层 Haar 低通降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立")
def _b276_haar_mra_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b276(float(p["p"]), int(p["J"]), int(p["k"])))

@_register_candidate(
    "b277_haar_mra_cand",
    "V_J 正交投影由 2^K 等距采样逐层 Haar 低通降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立")
def _b277_haar_mra_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b277(float(p["p"]), int(p["J"]), int(p["k"])))

@_register_candidate(
    "b278_haar_mra_cand",
    "V_J 正交投影由 2^K 等距采样逐层 Haar 低通降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立")
def _b278_haar_mra_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b278(float(p["p"]), int(p["J"]), int(p["k"])))

@_register_candidate(
    "b279_haar_mra_cand",
    "V_J 正交投影由 2^K 等距采样逐层 Haar 低通降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立")
def _b279_haar_mra_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b279(float(p["p"]), int(p["J"]), int(p["k"])))

@_register_candidate(
    "b280_haar_mra_cand",
    "V_J 正交投影由 2^K 等距采样逐层 Haar 低通降到 J 层后取第 k 段导出 ↔ 段内平均闭式 (b^{p+1}−a^{p+1})/((p+1)h)，方法学独立")
def _b280_haar_mra_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b16_numeric()
    return float(m.cand_b280(float(p["p"]), int(p["J"]), int(p["k"])))

@_register_candidate(
    "b281_forced_etd2_cand",
    "受迫阻尼 ODE y(T) 由指数时间差分 ETD2（线性部分精确 + forcing 段内线性插值）导出 ↔ 初等闭式，方法学独立")
def _b281_forced_etd2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b281(float(p["a"]), float(p["b"]), float(p["w"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b282_forced_etd2_cand",
    "受迫阻尼 ODE y(T) 由指数时间差分 ETD2 导出 ↔ 初等闭式，方法学独立")
def _b282_forced_etd2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b282(float(p["a"]), float(p["b"]), float(p["w"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b283_forced_etd2_cand",
    "受迫阻尼 ODE y(T) 由指数时间差分 ETD2 导出 ↔ 初等闭式，方法学独立")
def _b283_forced_etd2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b283(float(p["a"]), float(p["b"]), float(p["w"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b284_forced_etd2_cand",
    "受迫阻尼 ODE y(T) 由指数时间差分 ETD2 导出 ↔ 初等闭式，方法学独立")
def _b284_forced_etd2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b284(float(p["a"]), float(p["b"]), float(p["w"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b285_forced_etd2_cand",
    "受迫阻尼 ODE y(T) 由指数时间差分 ETD2 导出 ↔ 初等闭式，方法学独立")
def _b285_forced_etd2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b285(float(p["a"]), float(p["b"]), float(p["w"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b286_forced_etd2_cand",
    "受迫阻尼 ODE y(T) 由指数时间差分 ETD2 导出 ↔ 初等闭式，方法学独立")
def _b286_forced_etd2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b286(float(p["a"]), float(p["b"]), float(p["w"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b287_zernike_rms_cand",
    "圆域波前 RMS 由极坐标均匀中点求积（ρ/θ 双中点 + ρ 权重）导出 ↔ Zernike Parseval 闭式，方法学独立")
def _b287_zernike_rms_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b287(int(p["n1"]), int(p["m1"]), float(p["a1"]), int(p["n2"]), int(p["m2"]), float(p["a2"])))

@_register_candidate(
    "b288_zernike_rms_cand",
    "圆域波前 RMS 由极坐标均匀中点求积导出 ↔ Zernike Parseval 闭式，方法学独立")
def _b288_zernike_rms_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b288(int(p["n1"]), int(p["m1"]), float(p["a1"]), int(p["n2"]), int(p["m2"]), float(p["a2"])))

@_register_candidate(
    "b289_zernike_rms_cand",
    "圆域波前 RMS 由极坐标均匀中点求积导出 ↔ Zernike Parseval 闭式，方法学独立")
def _b289_zernike_rms_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b289(int(p["n1"]), int(p["m1"]), float(p["a1"]), int(p["n2"]), int(p["m2"]), float(p["a2"])))

@_register_candidate(
    "b290_zernike_rms_cand",
    "圆域波前 RMS 由极坐标均匀中点求积导出 ↔ Zernike Parseval 闭式，方法学独立")
def _b290_zernike_rms_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b290(int(p["n1"]), int(p["m1"]), float(p["a1"]), int(p["n2"]), int(p["m2"]), float(p["a2"])))

@_register_candidate(
    "b291_zernike_rms_cand",
    "圆域波前 RMS 由极坐标均匀中点求积导出 ↔ Zernike Parseval 闭式，方法学独立")
def _b291_zernike_rms_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b291(int(p["n1"]), int(p["m1"]), float(p["a1"]), int(p["n2"]), int(p["m2"]), float(p["a2"])))

@_register_candidate(
    "b292_duffing_yoshida4_cand",
    "Duffing 振子 x(t*) 由四阶组合辛积分（Yoshida 组合，辛结构保持）导出 ↔ Jacobi cn 精确解，方法学独立")
def _b292_duffing_yoshida4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b292(float(p["A"]), float(p["a"]), float(p["beta"]), float(p["tstar"])))

@_register_candidate(
    "b293_duffing_yoshida4_cand",
    "Duffing 振子 x(t*) 由四阶组合辛积分导出 ↔ Jacobi cn 精确解，方法学独立")
def _b293_duffing_yoshida4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b293(float(p["A"]), float(p["a"]), float(p["beta"]), float(p["tstar"])))

@_register_candidate(
    "b294_duffing_yoshida4_cand",
    "Duffing 振子 x(t*) 由四阶组合辛积分导出 ↔ Jacobi cn 精确解，方法学独立")
def _b294_duffing_yoshida4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b294(float(p["A"]), float(p["a"]), float(p["beta"]), float(p["tstar"])))

@_register_candidate(
    "b295_duffing_yoshida4_cand",
    "Duffing 振子 x(t*) 由四阶组合辛积分导出 ↔ Jacobi cn 精确解，方法学独立")
def _b295_duffing_yoshida4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b295(float(p["A"]), float(p["a"]), float(p["beta"]), float(p["tstar"])))

@_register_candidate(
    "b296_duffing_yoshida4_cand",
    "Duffing 振子 x(t*) 由四阶组合辛积分导出 ↔ Jacobi cn 精确解，方法学独立")
def _b296_duffing_yoshida4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b17_numeric()
    return float(m.cand_b296(float(p["A"]), float(p["a"]), float(p["beta"]), float(p["tstar"])))

@_register_candidate(
    "b297_filon_osc_cand",
    "振荡积分 I=∫₀¹cos(ωt)e^{at}dt 由 Filon 型分段二次插值 + 段内解析 cos 核积分导出 ↔ 初等闭式，方法学独立")
def _b297_filon_osc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b297(float(p["w"]), float(p["a"])))

@_register_candidate(
    "b298_filon_osc_cand",
    "振荡积分 I=∫₀¹cos(ωt)e^{at}dt 由 Filon 型分段二次插值 + 段内解析 cos 核积分导出 ↔ 初等闭式，方法学独立")
def _b298_filon_osc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b298(float(p["w"]), float(p["a"])))

@_register_candidate(
    "b299_filon_osc_cand",
    "振荡积分 I=∫₀¹cos(ωt)e^{at}dt 由 Filon 型分段二次插值 + 段内解析 cos 核积分导出 ↔ 初等闭式，方法学独立")
def _b299_filon_osc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b299(float(p["w"]), float(p["a"])))

@_register_candidate(
    "b300_filon_osc_cand",
    "振荡积分 I=∫₀¹cos(ωt)e^{at}dt 由 Filon 型分段二次插值 + 段内解析 cos 核积分导出 ↔ 初等闭式，方法学独立")
def _b300_filon_osc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b300(float(p["w"]), float(p["a"])))

@_register_candidate(
    "b301_filon_osc_cand",
    "振荡积分 I=∫₀¹cos(ωt)e^{at}dt 由 Filon 型分段二次插值 + 段内解析 cos 核积分导出 ↔ 初等闭式，方法学独立")
def _b301_filon_osc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b301(float(p["w"]), float(p["a"])))

@_register_candidate(
    "b302_filon_osc_cand",
    "振荡积分 I=∫₀¹cos(ωt)e^{at}dt 由 Filon 型分段二次插值 + 段内解析 cos 核积分导出 ↔ 初等闭式，方法学独立")
def _b302_filon_osc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b302(float(p["w"]), float(p["a"])))

@_register_candidate(
    "b303_gl_implicit_rk4_cand",
    "非线性 ODE y(T) 由 Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定，Newton 解隐式方程）导出 ↔ 超越初等闭式，方法学独立")
def _b303_gl_implicit_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b303(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b304_gl_implicit_rk4_cand",
    "非线性 ODE y(T) 由 Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定，Newton 解隐式方程）导出 ↔ 超越初等闭式，方法学独立")
def _b304_gl_implicit_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b304(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b305_gl_implicit_rk4_cand",
    "非线性 ODE y(T) 由 Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定，Newton 解隐式方程）导出 ↔ 超越初等闭式，方法学独立")
def _b305_gl_implicit_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b305(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b306_gl_implicit_rk4_cand",
    "非线性 ODE y(T) 由 Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定，Newton 解隐式方程）导出 ↔ 超越初等闭式，方法学独立")
def _b306_gl_implicit_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b306(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b307_gl_implicit_rk4_cand",
    "非线性 ODE y(T) 由 Gauss–Legendre 2 级隐式 RK（4 阶，A-稳定，Newton 解隐式方程）导出 ↔ 超越初等闭式，方法学独立")
def _b307_gl_implicit_rk4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b307(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b308_ab4_multistep_cand",
    "非线性 ODE y(T) 由 Adams–Bashforth 4 阶线性多步（RK4 同阶启动 3 步）导出 ↔ 超越初等闭式，方法学独立")
def _b308_ab4_multistep_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b308(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b309_ab4_multistep_cand",
    "非线性 ODE y(T) 由 Adams–Bashforth 4 阶线性多步（RK4 同阶启动 3 步）导出 ↔ 超越初等闭式，方法学独立")
def _b309_ab4_multistep_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b309(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b310_ab4_multistep_cand",
    "非线性 ODE y(T) 由 Adams–Bashforth 4 阶线性多步（RK4 同阶启动 3 步）导出 ↔ 超越初等闭式，方法学独立")
def _b310_ab4_multistep_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b310(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b311_ab4_multistep_cand",
    "非线性 ODE y(T) 由 Adams–Bashforth 4 阶线性多步（RK4 同阶启动 3 步）导出 ↔ 超越初等闭式，方法学独立")
def _b311_ab4_multistep_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b311(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b312_ab4_multistep_cand",
    "非线性 ODE y(T) 由 Adams–Bashforth 4 阶线性多步（RK4 同阶启动 3 步）导出 ↔ 超越初等闭式，方法学独立")
def _b312_ab4_multistep_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b18_numeric()
    return float(m.cand_b312(float(p["a"]), float(p["y0"]), float(p["T"])))

@_register_candidate(
    "b313_lane_emden_cand",
    "广义 Lane–Emden θ''+(2/ξ)θ'+λθ^n=0 的 θ(ξ) 由原点 Taylor 级数启动 + 经典四阶 RK4 导出 ↔ 初等/超越闭式，方法学独立")
def _b313_lane_emden_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b313(int(p["n"]), float(p["lam"]), float(p["th0"]), float(p["xi"])))

@_register_candidate(
    "b314_lane_emden_cand",
    "广义 Lane–Emden θ''+(2/ξ)θ'+λθ^n=0 的 θ(ξ) 由原点 Taylor 级数启动 + 经典四阶 RK4 导出 ↔ 初等/超越闭式，方法学独立")
def _b314_lane_emden_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b314(int(p["n"]), float(p["lam"]), float(p["th0"]), float(p["xi"])))

@_register_candidate(
    "b315_lane_emden_cand",
    "广义 Lane–Emden θ''+(2/ξ)θ'+λθ^n=0 的 θ(ξ) 由原点 Taylor 级数启动 + 经典四阶 RK4 导出 ↔ 初等/超越闭式，方法学独立")
def _b315_lane_emden_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b315(int(p["n"]), float(p["lam"]), float(p["th0"]), float(p["xi"])))

@_register_candidate(
    "b316_lane_emden_cand",
    "广义 Lane–Emden θ''+(2/ξ)θ'+λθ^n=0 的 θ(ξ) 由原点 Taylor 级数启动 + 经典四阶 RK4 导出 ↔ 初等/超越闭式，方法学独立")
def _b316_lane_emden_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b316(int(p["n"]), float(p["lam"]), float(p["th0"]), float(p["xi"])))

@_register_candidate(
    "b317_lane_emden_cand",
    "广义 Lane–Emden θ''+(2/ξ)θ'+λθ^n=0 的 θ(ξ) 由原点 Taylor 级数启动 + 经典四阶 RK4 导出 ↔ 初等/超越闭式，方法学独立")
def _b317_lane_emden_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b317(int(p["n"]), float(p["lam"]), float(p["th0"]), float(p["xi"])))

@_register_candidate(
    "b318_lane_emden_cand",
    "广义 Lane–Emden θ''+(2/ξ)θ'+λθ^n=0 的 θ(ξ) 由原点 Taylor 级数启动 + 经典四阶 RK4 导出 ↔ 初等/超越闭式，方法学独立")
def _b318_lane_emden_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b318(int(p["n"]), float(p["lam"]), float(p["th0"]), float(p["xi"])))

@_register_candidate(
    "b319_laplace_bem_cand",
    "二维 Laplace Dirichlet 边值由间接单层位势边界元（常数元 + 12 点 GL）导出 ↔ 调和函数闭式 r^n·cos nθ，方法学独立")
def _b319_laplace_bem_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b319(int(p["nb"]), float(p["r_obs"]), float(p["th_obs"])))

@_register_candidate(
    "b320_laplace_bem_cand",
    "二维 Laplace Dirichlet 边值由间接单层位势边界元（常数元 + 12 点 GL）导出 ↔ 调和函数闭式 r^n·cos nθ，方法学独立")
def _b320_laplace_bem_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b320(int(p["nb"]), float(p["r_obs"]), float(p["th_obs"])))

@_register_candidate(
    "b321_laplace_bem_cand",
    "二维 Laplace Dirichlet 边值由间接单层位势边界元（常数元 + 12 点 GL）导出 ↔ 调和函数闭式 r^n·cos nθ，方法学独立")
def _b321_laplace_bem_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b321(int(p["nb"]), float(p["r_obs"]), float(p["th_obs"])))

@_register_candidate(
    "b322_laplace_bem_cand",
    "二维 Laplace Dirichlet 边值由间接单层位势边界元（常数元 + 12 点 GL）导出 ↔ 调和函数闭式 r^n·cos nθ，方法学独立")
def _b322_laplace_bem_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b322(int(p["nb"]), float(p["r_obs"]), float(p["th_obs"])))

@_register_candidate(
    "b323_laplace_bem_cand",
    "二维 Laplace Dirichlet 边值由间接单层位势边界元（常数元 + 12 点 GL）导出 ↔ 调和函数闭式 r^n·cos nθ，方法学独立")
def _b323_laplace_bem_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b323(int(p["nb"]), float(p["r_obs"]), float(p["th_obs"])))

@_register_candidate(
    "b324_eikonal_fmm_cand",
    "Eikonal 方程 |∇T|=f 的到达时由快速行进法（Godunov 一阶迎风 + 二叉堆）导出 ↔ 制造解闭式，方法学独立")
def _b324_eikonal_fmm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b324(float(p["f0"]), float(p["xo"]), float(p["yo"])))

@_register_candidate(
    "b325_eikonal_fmm_cand",
    "Eikonal 方程 |∇T|=f 的到达时由快速行进法（Godunov 一阶迎风 + 二叉堆）导出 ↔ 制造解闭式，方法学独立")
def _b325_eikonal_fmm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b325(float(p["f0"]), float(p["xo"]), float(p["yo"])))

@_register_candidate(
    "b326_eikonal_fmm_cand",
    "Eikonal 方程 |∇T|=f 的到达时由快速行进法（Godunov 一阶迎风 + 二叉堆）导出 ↔ 制造解闭式，方法学独立")
def _b326_eikonal_fmm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b326(float(p["f0"]), float(p["xo"]), float(p["yo"])))

@_register_candidate(
    "b327_eikonal_fmm_cand",
    "Eikonal 方程 |∇T|=f 的到达时由快速行进法（Godunov 一阶迎风 + 二叉堆）导出 ↔ 制造解闭式，方法学独立")
def _b327_eikonal_fmm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b327(float(p["f0"]), float(p["xo"]), float(p["yo"])))

@_register_candidate(
    "b328_eikonal_fmm_cand",
    "Eikonal 方程 |∇T|=f 的到达时由快速行进法（Godunov 一阶迎风 + 二叉堆）导出 ↔ 制造解闭式，方法学独立")
def _b328_eikonal_fmm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b19_numeric()
    return float(m.cand_b328(float(p["f0"]), float(p["xo"]), float(p["yo"])))

@_register_candidate(
    "b329_bessel_iv_cand",
    "修正 Bessel I_ν(x) 由修正 Bessel ODE 原点 Frobenius 级数启动 + 经典四阶 RK4 导出 ↔ scipy.special.iv 精确 oracle，方法学独立")
def _b329_bessel_iv_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.iv_rk4(float(p["nu"]), float(p["x"]), 128))

@_register_candidate(
    "b330_bessel_iv_cand",
    "修正 Bessel I_ν(x) 由修正 Bessel ODE 原点 Frobenius 级数启动 + 经典四阶 RK4 导出 ↔ scipy.special.iv 精确 oracle，方法学独立")
def _b330_bessel_iv_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.iv_rk4(float(p["nu"]), float(p["x"]), 128))

@_register_candidate(
    "b331_bessel_iv_cand",
    "修正 Bessel I_ν(x) 由修正 Bessel ODE 原点 Frobenius 级数启动 + 经典四阶 RK4 导出 ↔ scipy.special.iv 精确 oracle，方法学独立")
def _b331_bessel_iv_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.iv_rk4(float(p["nu"]), float(p["x"]), 128))

@_register_candidate(
    "b332_bessel_iv_cand",
    "修正 Bessel I_ν(x) 由修正 Bessel ODE 原点 Frobenius 级数启动 + 经典四阶 RK4 导出 ↔ scipy.special.iv 精确 oracle，方法学独立")
def _b332_bessel_iv_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.iv_rk4(float(p["nu"]), float(p["x"]), 128))

@_register_candidate(
    "b333_bessel_iv_cand",
    "修正 Bessel I_ν(x) 由修正 Bessel ODE 原点 Frobenius 级数启动 + 经典四阶 RK4 导出 ↔ scipy.special.iv 精确 oracle，方法学独立")
def _b333_bessel_iv_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.iv_rk4(float(p["nu"]), float(p["x"]), 128))

@_register_candidate(
    "b334_bessel_iv_cand",
    "修正 Bessel I_ν(x) 由修正 Bessel ODE 原点 Frobenius 级数启动 + 经典四阶 RK4 导出 ↔ scipy.special.iv 精确 oracle，方法学独立")
def _b334_bessel_iv_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.iv_rk4(float(p["nu"]), float(p["x"]), 128))

@_register_candidate(
    "b335_sph_proj_cand",
    "球谐 Y_l^m 自投影系数由均匀网格复合梯形球面积分导出 ↔ 正交归一恒等式（=1），方法学独立")
def _b335_sph_proj_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.sph_proj_trapz(int(p["l"]), int(p["m"]), 160))

@_register_candidate(
    "b336_sph_proj_cand",
    "球谐 Y_l^m 自投影系数由均匀网格复合梯形球面积分导出 ↔ 正交归一恒等式（=1），方法学独立")
def _b336_sph_proj_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.sph_proj_trapz(int(p["l"]), int(p["m"]), 160))

@_register_candidate(
    "b337_sph_proj_cand",
    "球谐 Y_l^m 自投影系数由均匀网格复合梯形球面积分导出 ↔ 正交归一恒等式（=1），方法学独立")
def _b337_sph_proj_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.sph_proj_trapz(int(p["l"]), int(p["m"]), 160))

@_register_candidate(
    "b338_sph_proj_cand",
    "球谐 Y_l^m 自投影系数由均匀网格复合梯形球面积分导出 ↔ 正交归一恒等式（=1），方法学独立")
def _b338_sph_proj_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.sph_proj_trapz(int(p["l"]), int(p["m"]), 160))

@_register_candidate(
    "b339_sph_proj_cand",
    "球谐 Y_l^m 自投影系数由均匀网格复合梯形球面积分导出 ↔ 正交归一恒等式（=1），方法学独立")
def _b339_sph_proj_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.sph_proj_trapz(int(p["l"]), int(p["m"]), 160))

@_register_candidate(
    "b340_rbf_interp_cand",
    "一维 MQ RBF 插值（形状随 h 缩放 c=0.5h + 二次多项式）由离格测试点估值导出 ↔ 已知函数闭式，方法学独立")
def _b340_rbf_interp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.rbf_interp(float(p["a"]), float(p["x"]), 256))

@_register_candidate(
    "b341_rbf_interp_cand",
    "一维 MQ RBF 插值（形状随 h 缩放 c=0.5h + 二次多项式）由离格测试点估值导出 ↔ 已知函数闭式，方法学独立")
def _b341_rbf_interp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.rbf_interp(float(p["a"]), float(p["x"]), 256))

@_register_candidate(
    "b342_rbf_interp_cand",
    "一维 MQ RBF 插值（形状随 h 缩放 c=0.5h + 二次多项式）由离格测试点估值导出 ↔ 已知函数闭式，方法学独立")
def _b342_rbf_interp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.rbf_interp(float(p["a"]), float(p["x"]), 256))

@_register_candidate(
    "b343_rbf_interp_cand",
    "一维 MQ RBF 插值（形状随 h 缩放 c=0.5h + 二次多项式）由离格测试点估值导出 ↔ 已知函数闭式，方法学独立")
def _b343_rbf_interp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.rbf_interp(float(p["a"]), float(p["x"]), 256))

@_register_candidate(
    "b344_rbf_interp_cand",
    "一维 MQ RBF 插值（形状随 h 缩放 c=0.5h + 二次多项式）由离格测试点估值导出 ↔ 已知函数闭式，方法学独立")
def _b344_rbf_interp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b20_numeric()
    return float(m.rbf_interp(float(p["a"]), float(p["x"]), 256))

@_register_candidate(
    "b345_hermite_fd_cand",
    "Hermite 多项式 H_n(x) 由 n 阶中心差分 Rodrigues（对 e^{-x^2} 做 n 阶中心差分导数）×(−1)^n e^{x^2} 导出 ↔ numpy.polynomial.hermite 精确 oracle，方法学独立")
def _b345_hermite_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.hermite_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b346_hermite_fd_cand",
    "Hermite 多项式 H_n(x) 由 n 阶中心差分 Rodrigues（对 e^{-x^2} 做 n 阶中心差分导数）×(−1)^n e^{x^2} 导出 ↔ numpy.polynomial.hermite 精确 oracle，方法学独立")
def _b346_hermite_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.hermite_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b347_hermite_fd_cand",
    "Hermite 多项式 H_n(x) 由 n 阶中心差分 Rodrigues（对 e^{-x^2} 做 n 阶中心差分导数）×(−1)^n e^{x^2} 导出 ↔ numpy.polynomial.hermite 精确 oracle，方法学独立")
def _b347_hermite_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.hermite_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b348_hermite_fd_cand",
    "Hermite 多项式 H_n(x) 由 n 阶中心差分 Rodrigues（对 e^{-x^2} 做 n 阶中心差分导数）×(−1)^n e^{x^2} 导出 ↔ numpy.polynomial.hermite 精确 oracle，方法学独立")
def _b348_hermite_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.hermite_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b349_hermite_fd_cand",
    "Hermite 多项式 H_n(x) 由 n 阶中心差分 Rodrigues（对 e^{-x^2} 做 n 阶中心差分导数）×(−1)^n e^{x^2} 导出 ↔ numpy.polynomial.hermite 精确 oracle，方法学独立")
def _b349_hermite_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.hermite_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b350_laguerre_fd_cand",
    "Laguerre 多项式 L_n(x) 由 n 阶中心差分 Rodrigues（对 x^n e^{-x} 做 n 阶中心差分导数）×e^{x}/n! 导出 ↔ scipy.special.genlaguerre 精确 oracle，方法学独立")
def _b350_laguerre_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.laguerre_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b351_laguerre_fd_cand",
    "Laguerre 多项式 L_n(x) 由 n 阶中心差分 Rodrigues（对 x^n e^{-x} 做 n 阶中心差分导数）×e^{x}/n! 导出 ↔ scipy.special.genlaguerre 精确 oracle，方法学独立")
def _b351_laguerre_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.laguerre_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b352_laguerre_fd_cand",
    "Laguerre 多项式 L_n(x) 由 n 阶中心差分 Rodrigues（对 x^n e^{-x} 做 n 阶中心差分导数）×e^{x}/n! 导出 ↔ scipy.special.genlaguerre 精确 oracle，方法学独立")
def _b352_laguerre_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.laguerre_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b353_laguerre_fd_cand",
    "Laguerre 多项式 L_n(x) 由 n 阶中心差分 Rodrigues（对 x^n e^{-x} 做 n 阶中心差分导数）×e^{x}/n! 导出 ↔ scipy.special.genlaguerre 精确 oracle，方法学独立")
def _b353_laguerre_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.laguerre_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b354_laguerre_fd_cand",
    "Laguerre 多项式 L_n(x) 由 n 阶中心差分 Rodrigues（对 x^n e^{-x} 做 n 阶中心差分导数）×e^{x}/n! 导出 ↔ scipy.special.genlaguerre 精确 oracle，方法学独立")
def _b354_laguerre_fd_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.laguerre_fd(float(p["n"]), float(p["x"]), 512))

@_register_candidate(
    "b355_bernstein_cand",
    "Bernstein 多项式 degree-N 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k} 逼近已知闭式 f(t) ↔ 精确 oracle，方法学独立")
def _b355_bernstein_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.bernstein(p["name"], float(p["t"]), 512))

@_register_candidate(
    "b356_bernstein_cand",
    "Bernstein 多项式 degree-N 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k} 逼近已知闭式 f(t) ↔ 精确 oracle，方法学独立")
def _b356_bernstein_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.bernstein(p["name"], float(p["t"]), 512))

@_register_candidate(
    "b357_bernstein_cand",
    "Bernstein 多项式 degree-N 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k} 逼近已知闭式 f(t) ↔ 精确 oracle，方法学独立")
def _b357_bernstein_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.bernstein(p["name"], float(p["t"]), 512))

@_register_candidate(
    "b358_bernstein_cand",
    "Bernstein 多项式 degree-N 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k} 逼近已知闭式 f(t) ↔ 精确 oracle，方法学独立")
def _b358_bernstein_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.bernstein(p["name"], float(p["t"]), 512))

@_register_candidate(
    "b359_bernstein_cand",
    "Bernstein 多项式 degree-N 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k} 逼近已知闭式 f(t) ↔ 精确 oracle，方法学独立")
def _b359_bernstein_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.bernstein(p["name"], float(p["t"]), 512))

@_register_candidate(
    "b360_bernstein_cand",
    "Bernstein 多项式 degree-N 基求和 Σ f(k/N)·C(N,k)·t^k·(1−t)^{N−k} 逼近已知闭式 f(t) ↔ 精确 oracle，方法学独立")
def _b360_bernstein_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b21_numeric()
    return float(m.bernstein(p["name"], float(p["t"]), 512))
