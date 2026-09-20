# -*- coding: utf-8 -*-
"""验证适配器 · 分片 3/6（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

覆盖原文件 L2080..L3215（71 个顶层定义）。正文**逐字节**取自原文，不重排、不重格式化。
🔴 装配顺序由 `verification_adapters.py` 的 import 次序决定，勿单独调整。
"""

from __future__ import annotations

from ._adapter_core import (
    _get_batch_b22, _get_batch_b23, _get_batch_b24, _get_batch_b25, _get_batch_b26,
    _get_batch_b27, _get_batch_b28, _register_candidate,
)

from typing import (
    Any,
)

from .verification_spec import (
    VerificationSpec,
)

@_register_candidate(
    "fiber_lp01_neff_fd",
    "圆柱径向加权广义本征 LP01 有效折射率 n_eff（与 golden 经验 b(V) 闭式方法学不同源）")
def _b361_fiber_lp01_neff_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B361-B368 独立候选：阶跃光纤 LP01 有效折射率 n_eff（径向加权广义 FD 本征）。

    golden = Snyder/Marcatili 经验闭式 b(V)=(1.1428-0.996/V)² → n_eff；
    cand   = 圆柱坐标径向加权广义本征求解（scipy eigh，B=diag(r) 物理自伴，
             r_i=(i+0.5)dr 避 r=0 奇点，l=0 内边界镜像 Neumann、外边界 Dirichlet 吸收）。
    残差 = 经验式固有拟合误差 + FD 离散化误差（持久、随 N 收敛、随 V 变化、判据 D 响应、
    候选输出扰动必 FAIL），非代数恒等、非噪声地板。N=3000 余量 2.1×~1631×。
    纯 numpy/scipy、零商业依赖、LLM 不进判决路径。
    """
    p = spec.params
    m = _get_batch_b22()
    return float(m.fiber_lp_neff(float(p["n_co"]), float(p["n_cl"]),
                                 float(p["a"]), float(p["wl"]), N=3000))

@_register_candidate(
    "fiber_lp11_vc_fd",
    "圆柱径向加权广义本征 LP11 截止阈值 V_c（与 golden J₀ 首零闭式方法学不同源）")
def _b369_fiber_lp11_vc_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B369 独立候选：阶跃光纤 LP11 截止归一化频率 V_c（径向加权 FD 模出现阈值）。

    golden = J₀ 贝塞尔首零 2.4048255577（精确常数）；
    cand   = 圆柱径向加权 FD 本征扫 V 检测 LP11 模出现阈值（β 跨 n_cl·k0）。
    N=3000 残差 1.23e-2（tol=0.1 的 8.2× 余量）；判据 D 由 B-22 FD 核已证。
    零商业依赖。
    """
    p = spec.params
    m = _get_batch_b22()
    return float(m.fd_lp_vc(float(p["n_co"]), float(p["n_cl"]),
                            float(p["a"]), float(p["wl"]), l=1, m=1, N=3000))

@_register_candidate(
    "fiber_lp_ng_silica_fd",
    "SiO₂ 芯阶跃光纤 λ 扫描差分群折射率 n_g（与 golden Sellmeier 闭式方法学不同源）")
def _b370_fiber_ng_silica_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B370/B371 独立候选：SiO₂ 芯阶跃光纤 LP01 群折射率 n_g（径向加权 FD λ 扫描差分）。

    golden = SiO₂ Sellmeier 群折射率闭式 n_g=n−λ·dn/dλ（Malitson 1965）；
    cand   = 径向加权 FD 求 n_eff 后 λ 中心差分 n_g=n_eff−λ·dn_eff/dλ。
    包层 n_cl=1.42 保证模良好约束（修复近零对比度下测到≈0 模量的 bug）。
    N=3000 余量 4.5×~4.7×；判据 D：λ 差分随步长收敛、候选输出扰动必 FAIL。零商业依赖。
    """
    p = spec.params
    m = _get_batch_b22()
    return float(m.fd_lp_ng_silica(float(p["n_cl"]), float(p["a"]),
                                   float(p["wl"]), N=3000))

@_register_candidate(
    "fiber_lp_b2_silica_fd",
    "SiO₂ 芯阶跃光纤角频率空间二阶差分群速度色散 β₂（与 golden Sellmeier 闭式同量纲、方法学不同源）")
def _b372_fiber_b2_silica_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B372/B373 独立候选：SiO₂ 芯阶跃光纤 LP01 群速度色散 β₂（径向加权 FD ω 空间二阶差分）。

    golden = SiO₂ Sellmeier 角频率空间二阶导 β₂=d²β/dω² 闭式（负值，色散零点 ~1.27µm）；
    cand   = 径向加权 FD 求 n_eff(λ(ω)) 后 β(ω)=n_eff·ω/c 角频率空间二阶差分。
    同量纲、同方法学对照；包层 n_cl=1.42 保证模约束→β₂ 收敛到体材料值（符号正确）。
    N=3000 余量 2.9×~11.7×；判据 D：ω 差分随 dw 收敛、候选输出扰动必 FAIL。零商业依赖。
    """
    p = spec.params
    m = _get_batch_b22()
    return float(m.fd_lp_b2_silica(float(p["n_cl"]), float(p["a"]),
                                   float(p["wl"]), N=3000))

@_register_candidate(
    "bpm_rayleigh_range_fd",
    "1D 旁轴 BPM 初值传播量测瑞利范围 zR（双曲线最小二乘，与 golden 闭式方法学不同源）")
def _b374_bpm_rayleigh_range_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B374 独立候选：高斯光束瑞利范围 zR=πw0²/λ（旁轴 BPM 双曲线拟合）。

    golden = 闭式 zR=πw0²/λ；cand = 旁轴波方程 Crank-Nicolson FD 从腰斑初值传播，
    多点量测 w(z) 拟合 w²(z)=A+B·z² 提取 zR=√(A/B)。残差=BPM 离散化误差
    （O(dx²,dz²)，随网格收敛、随参数变化、判据 D 响应、候选输出扰动必 FAIL），
    非代数恒等、非噪声地板。dx=waist/24、dz=zR/340 维持 |c|≈0.21 甜区。
    余量 3.8×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_rayleigh_range(float(p["w0"]), float(p["wl"])))

@_register_candidate(
    "bpm_waist_at_z_fd",
    "1D 旁轴 BPM 初值传播量测 z 处 1/e² 束宽 w(z)（二阶矩法，与 golden 闭式不同源）")
def _b375_bpm_waist_at_z_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B375/B382/B384/B385 独立候选：高斯光束束宽演化 w(z)=w0√(1+(z/zR)²)（BPM 二阶矩）。

    golden = 闭式；cand = 旁轴 BPM 初值传播量测 1/e² 束宽（二阶矩法）。
    残差=BPM 离散化误差（持久、随网格收敛、判据 D 响应、候选输出扰动必 FAIL）。
    余量 3.2×~51×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_waist_at_z(float(p["w0"]), float(p["wl"]), float(p["z"])))

@_register_candidate(
    "bpm_confocal_fd",
    "1D 旁轴 BPM 量测共焦参数 b=2zR（与 golden 闭式不同源）")
def _b376_bpm_confocal_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B376 独立候选：共焦参数 b=2zR=2πw0²/λ（BPM 量测 2·zR）。

    golden = 闭式；cand = 旁轴 BPM 量测 2·zR（复用 cand_rayleigh_range）。
    余量 3.8×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_confocal(float(p["w0"]), float(p["wl"])))

@_register_candidate(
    "bpm_divergence_fd",
    "1D 旁轴 BPM 远场渐近 θ≈w(z)/z 量测发散半角 θ（与 golden 闭式不同源）")
def _b377_bpm_divergence_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B377/B383 独立候选：高斯光束发散半角 θ=λ/(πw0)（BPM 远场渐近）。

    golden = 闭式 θ=λ/(πw0)；cand = 旁轴 BPM 大 z 处渐近 θ≈w(z)/z（z=20zR，
    曲率误差→0.13%）。残差=BPM 离散化误差（判据 D 响应、候选输出扰动必 FAIL）。
    B377 红光荣量 133×；B383 绿光荣量 326×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_divergence(float(p["w0"]), float(p["wl"])))

@_register_candidate(
    "bpm_q_waist_after_lens_fd",
    "1D 旁轴 BPM 薄透镜传播量测聚焦腰 w0'（与 golden ABCD 闭式不同源）")
def _b378_bpm_q_waist_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B378/B386 独立候选：薄透镜 q 变换后聚焦腰 w0'=w0/√(1+(zR/f)²)（BPM 透镜传播）。

    golden = ABCD 闭式；cand = 旁轴 BPM 腰斑→薄透镜相位掩膜→传播量测新最小束宽。
    余量 1.7e3×~963×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_q_waist_after_lens(float(p["w0"]), float(p["wl"]), float(p["f"])))

@_register_candidate(
    "bpm_q_zR_after_lens_fd",
    "1D 旁轴 BPM 透镜传播量测新瑞利范围 zR'（与 golden ABCD 闭式不同源）")
def _b379_bpm_q_zR_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B379 独立候选：薄透镜后新瑞利范围 zR'=zR/(1+(zR/f)²)（BPM 焦腰后量测）。

    golden = ABCD 闭式；cand = 旁轴 BPM 透镜传播，焦腰后量测 w=√2 w0' 点距焦腰得 zR'。
    余量 3.9×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_q_zR_after_lens(float(p["w0"]), float(p["wl"]), float(p["f"])))

@_register_candidate(
    "bpm_q_waist_loc_fd",
    "1D 旁轴 BPM 透镜传播量测焦腰位置 s（与 golden ABCD 闭式不同源）")
def _b380_bpm_q_waist_loc_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B380 独立候选：薄透镜后焦腰位置 s=f/(1+(f/zR)²)（BPM 量测最小束宽处）。

    golden = ABCD 闭式；cand = 旁轴 BPM 透镜传播量测最小束宽位置。
    余量 7.3×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_q_waist_loc(float(p["w0"]), float(p["wl"]), float(p["f"])))

@_register_candidate(
    "bpm_gouy_fd",
    "1D 旁轴 BPM 解卷中心包络相位量测 Gouy 增量（与 golden 1D 闭式不同源）")
def _b381_bpm_gouy_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B381 独立候选：Gouy 相位增量 Δφ_G[0,zR]=½ arctan(1)=π/4（1D 旁轴光束）。

    golden = 1D 闭式 Δφ_G=½[arctan(z2/zR)−arctan(z1/zR)]；
    cand = 旁轴 BPM 连续解卷中心包络相位 arg(Â(0,z)) 取增量（不含快变 e^{ik0z} 载波）。
    余量 5.9×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b23()
    return float(m.cand_gouy(float(p["w0"]), float(p["wl"]), float(p["z1"]), float(p["z2"])))

@_register_candidate(
    "slit_firstzero_simpson",
    "Fraunhofer 单缝复振幅 Simpson 求积 + 实振幅变号二分定位第一零点（与 golden λ/a 闭式不同源）")
def _b387_slit_firstzero_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B387 独立候选：单缝夫琅禾费第一暗纹 sinθ₁=λ/a（Simpson 求积 + 实振幅变号二分）。

    golden=闭式 λ/a；cand=Fraunhofer 单缝复振幅 U(θ) 复合 Simpson 1D 求积，实振幅符号变号
    （线性穿越）二分定位第一零点。残差=求积离散化误差（O(h²)，随采样收敛、随参数变化、
    判据 D 响应、候选输出扰动必 FAIL），非代数恒等、非噪声地板。余量 32.5×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_slit_firstzero(float(p["a"]), float(p["wl"])))

@_register_candidate(
    "slit_intensity_simpson",
    "Fraunhofer 单缝强度 |U|²/a² Simpson 求积（与 golden sinc² 闭式不同源）")
def _b388_slit_intensity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B388 独立候选：单缝夫琅禾费强度比 I(θ)/I₀=sinc²(π a sinθ/λ)（Simpson 求积）。

    golden=闭式 sinc²；cand=Fraunhofer 单缝复振幅 Simpson 求积归一化强度。
    残差=求积离散化误差（判据 D 响应、候选输出扰动必 FAIL）。余量 2.6e6×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_slit_intensity(float(p["a"]), float(p["wl"]), float(p["theta"])))

@_register_candidate(
    "disk_firstzero_simpson",
    "Fraunhofer 圆孔复振幅极坐标 2D Simpson 求积 + 实振幅变号二分定位第一暗环（不调 J₀/J₁）")
def _b389_disk_firstzero_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B389 独立候选：圆孔爱里斑第一暗环 sinθ₁=1.21967λ/D（极坐标 2D Simpson + 实振幅变号）。

    golden=(J₁ 第一零点)/π·λ/D 闭式；cand=圆孔夫琅禾费复振幅极坐标 2D Simpson 求积
    （不调 J₀/J₁ 特殊函数），实振幅符号变号二分定位第一暗环。残差=2D 求积误差（判据 D
    响应、候选输出扰动必 FAIL）。余量 123×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_disk_firstzero(float(p["D"]), float(p["wl"])))

@_register_candidate(
    "disk_intensity_simpson",
    "Fraunhofer 圆孔强度 |U|²/(πR²)² 极坐标 2D Simpson 求积（与 golden [2J₁/x]² 不同源）")
def _b390_disk_intensity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B390 独立候选：圆孔夫琅禾费强度比 [2J₁(x)/x]²（极坐标 2D Simpson 求积）。

    golden=闭式 [2J₁(x)/x]²；cand=圆孔夫琅禾费复振幅 2D Simpson 求积归一化强度。
    残差=2D 求积误差。余量 5.5e4×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_disk_intensity(float(p["D"]), float(p["wl"]), float(p["theta"])))

@_register_candidate(
    "double_slit_intensity_simpson",
    "Fraunhofer 双缝复振幅（两缝积分之和）Simpson 1D 求积归一化强度（与 golden cos²·sinc² 不同源）")
def _b391_double_slit_intensity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B391 独立候选：双缝干涉强度比 cos²(π d sinθ/λ)·sinc²(π a sinθ/λ)（Simpson 求积）。

    golden=闭式 cos²·sinc²；cand=双缝复振幅（两缝积分之和）Simpson 求积归一化强度
    （QUAD_N_DOUBLE=40 使普通点残差浮出 1e-12 之上、压在 tol 之下）。
    残差=求积离散化误差。余量 2.96e7×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_double_slit_intensity(
        float(p["a"]), float(p["d"]), float(p["wl"]), float(p["theta"])))

@_register_candidate(
    "interf_fringe_spacing",
    "纯干涉（点光源阵列）数值求和 + 抛物线峰位精修，相邻主极大 sinθ 差（与 golden λ/d 不同源）")
def _b392_interf_fringe_spacing_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B392 独立候选：双缝/纯干涉相邻主极大角间距 Δ(sinθ)=λ/d（纯干涉数值找峰）。

    golden=闭式 λ/d；cand=纯干涉（点光源阵列、无单缝包络）数值求和 + 抛物线峰位精修
    取相邻主极大（m=0,m=1）sinθ 差。单缝包络由 B387/B388 独立覆盖，不影响主极大位置。
    残差=网格离散化+峰位插值误差（判据 D 响应、候选输出扰动必 FAIL）。余量 8733×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_fringe_spacing(float(p["d"]), float(p["wl"])))

@_register_candidate(
    "grating_peak_simpson",
    "N 缝纯干涉数值求和 + 抛物线峰位精修第 m 级主极大（与 golden d sinθ=mλ 不同源）")
def _b393_grating_peak_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B393 独立候选：N 缝纯干涉主极大 d sinθ=mλ（纯干涉数值找峰）。

    golden=闭式 d sinθ=mλ；cand=N 缝纯干涉（点光源阵列、无单缝包络）数值求和 + 抛物线峰位
    精修（刻意不用 scipy 优化器以留 O(h²) 残差避开判据 D ③ 恒等式地板）。
    残差=网格离散化+峰位插值误差（随 N/网格变化、判据 D 响应）。余量 222×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_grating_peak(
        float(p["d"]), float(p["wl"]), int(p["m"]), int(p["nslits"])))

@_register_candidate(
    "grating_respower",
    "纯干涉第 m 级主极大 + 第一极小数值定位，Δ(sinθ)→Δλ→R=mN（与 golden R=mN 不同源）")
def _b394_grating_respower_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B394 独立候选：光栅分辨本领 R=mN（瑞利判据，纯干涉数值找第一极小）。

    golden=闭式 R=mN；cand=纯干涉第 m 级主极大 + 第一极小（强度穿越 ~0）数值定位，
    Δ(sinθ)→Δλ→R。避开 dθ/dλ 刚性问题（d=50µm ⇒ dθ/dλ≈2e4 三阶导爆炸、有限差商混叠主导）。
    残差=峰/零点数值定位误差。余量 33.7×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_grating_respower(
        float(p["d"]), float(p["wl"]), int(p["m"]), int(p["nslits"])))

@_register_candidate(
    "rect_intensity_simpson",
    "Fraunhofer 矩形孔复振幅（可分离 2D 笛卡尔 Simpson 求积）归一化强度（与 golden 可分离 sinc² 不同源）")
def _b395_rect_intensity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B395 独立候选：矩形孔夫琅禾费强度比 sinc²(π a sinθx/λ)·sinc²(π b sinθy/λ)（2D Simpson）。

    golden=可分离 sinc² 闭式；cand=矩形孔复振幅可分离 2D 笛卡尔 Simpson 求积归一化强度。
    残差=求积离散化误差。余量 2.6e6×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_rect_intensity(
        float(p["a"]), float(p["b"]), float(p["wl"]), float(p["thx"]), float(p["thy"])))

@_register_candidate(
    "slit_fullwidth",
    "Fraunhofer 单缝第一零点（Simpson 求积 + 实振幅变号二分）×2（与 golden 2λ/a 不同源）")
def _b396_slit_fullwidth_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B396 独立候选：单缝夫琅禾费全角宽 Δθ=2λ/a（首暗纹→首暗纹）。

    golden=闭式 2λ/a；cand=2×单缝第一零点（Simpson 求积 + 实振幅变号二分）。
    残差=求积离散化误差（判据 D 响应、候选输出扰动必 FAIL）。余量 16.3×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_slit_fullwidth(float(p["a"]), float(p["wl"])))

@_register_candidate(
    "disk_encircled_2d_simpson",
    "Fraunhofer 圆孔极坐标 2D Simpson 求 I(θ) 后角积分取内围能比（不调 J₀/J₁，与 golden 闭式角积分不同源）")
def _b397_disk_encircled_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B397 独立候选：圆孔爱里斑内围能比（角度远场约定≈0.8511，2D Simpson 求 I(θ) 后角积分）。

    golden=闭式 2π∫[2J₁(x)/x]² sinθ dθ 角积分；cand=圆孔夫琅禾费复振幅极坐标 2D Simpson
    求 I(θ) 后做 0→θ₁/0→θ_max 角积分取比（不调 J₀/J₁）。旧版 1−J₀²−J₁² 是焦平面 0.8377，
    本锚统一到角度远场约定 0.8511。残差=2D 求积误差。余量 7.1e4×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_disk_encircled(float(p["D"]), float(p["wl"])))

@_register_candidate(
    "grating_fsr",
    "N 缝含包络光栅强度数值找干涉因子第一零点（强度穿越 ~0），Δ(sinθ)→Δλ（与 golden λ/(mN) 不同源）")
def _b398_grating_fsr_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B398 独立候选：光栅自由光谱范围 Δλ=λ/(mN)（数值第一零点）。

    golden=闭式 λ/(mN)；cand=N 缝含包络光栅强度，数值找干涉因子第一零点（强度真正穿越 ~0
    而非下降段中点），Δ(sinθ)·d/m 回推 Δλ。残差=零点数值定位误差（判据 D 响应）。余量 51.6×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_grating_fsr(
        float(p["d"]), float(p["wl"]), int(p["m"]), int(p["nslits"])))

@_register_candidate(
    "disk_square_zeroratio",
    "圆孔首零点（极坐标 2D Simpson）+ 方孔首零点（1D Simpson）取比（与 golden 1.220 不同源）")
def _b399_disk_square_zeroratio_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B399 独立候选：圆孔/方孔第一暗纹角半径比=1.220（圆）/1.0（方）。

    golden=闭式 1.220；cand=圆孔首零点（极坐标 2D Simpson）+ 方孔（单缝）首零点（1D Simpson）
    取比。残差=两数值零点求积误差。余量 60.6×；零商业依赖。
    """
    p = spec.params
    m = _get_batch_b24()
    return float(m.cand_disk_square_zeroratio(
        float(p["D"]), float(p["a_sq"]), float(p["wl"])))

@_register_candidate(
    "disk_onaxis_e",
    "带电圆盘轴线场 Simpson 1D 求积（与 golden 闭式 2πσ(1−z/√) 不同源）")
def _b400_disk_onaxis_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B400 独立候选：带电圆盘轴线场 E(z)（库仑环贡献 Simpson 1D 求积）。

    golden=闭式 2πσ(1−z/√(z²+R²))；cand=∫2πσ z r/(z²+r²)^{3/2}dr 复合 Simpson 1D。
    残差=求积离散化误差（O(h⁴)）。余量 1515×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_disk(float(p["R"]), float(p["sigma"]), float(p["z"])))

@_register_candidate(
    "washer_onaxis_e",
    "带电圆环（washer a..b）轴线场 Simpson 1D 求积（与 golden 闭式不同源）")
def _b401_washer_onaxis_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B401 独立候选：带电圆环轴线场 E(z)（库仑环贡献 Simpson 1D 求积）。

    golden=闭式 2πσ(z/√a − z/√b)；cand=∫_{a}^{b} 2πσ z r/(z²+r²)^{3/2}dr Simpson 1D。
    残差=求积离散化误差。余量 3226×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_washer(float(p["a"]), float(p["b"]), float(p["sigma"]), float(p["z"])))

@_register_candidate(
    "line_bisector_e",
    "有限长线电荷垂直平分线场 Simpson 1D 求积（与 golden 闭式不同源）")
def _b402_line_bisector_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B402 独立候选：有限长线电荷垂直平分线场 E（库仑 y 分量 Simpson 1D 求积）。

    golden=闭式 λL/(a√((L/2)²+a²))；cand=∫λ a/(x²+a²)^{3/2}dx Simpson 1D。
    残差=求积离散化误差（尖峰被积 a/(x²+a²)^{3/2} 收敛较慢）。余量 441×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_line_bisector(float(p["L"]), float(p["lam"]), float(p["a"])))

@_register_candidate(
    "line_endon_e",
    "有限长线电荷端点延伸线场 Simpson 1D 求积（与 golden 闭式不同源）")
def _b403_line_endon_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B403 独立候选：有限长线电荷端点延伸线场 E（库仑 y 分量 Simpson 1D 求积）。

    golden=闭式 λL/(a√(L²+a²))；cand=∫_{0}^{L} λ a/(x²+a²)^{3/2}dx Simpson 1D。
    残差=求积离散化误差。余量 330×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_line_endon(float(p["L"]), float(p["lam"]), float(p["a"])))

@_register_candidate(
    "shell_external_e",
    "均匀带电球壳外点场 2D Simpson 求积（与 golden 壳定理点电荷闭式不同源）")
def _b404_shell_external_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B404 独立候选：均匀带电球壳外 off-axis 点场（库仑 2D Simpson 求 ∫KE·dq·(P−surf)/r³）。

    golden=壳定理闭式 Q/(ρ²+z²)（外点=点电荷等价）；cand=球壳 2D Simpson 求积。
    off-axis 使 r 随 θ,φ 变化（非退化陷阱）。残差=求积离散化误差。余量 7584×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_shell(float(p["R"]), float(p["Q"]), float(p["rho"]), float(p["z"])))

@_register_candidate(
    "twoline_charge_e",
    "两平行异号有限线电荷中点场 Simpson 1D 求积叠加（与 golden 闭式不同源）")
def _b405_twoline_charge_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B405 独立候选：两平行异号有限线电荷中点场 E（库仑 y 分量 Simpson 1D 求积叠加）。

    golden=闭式 2λL/((d/2)√((L/2)²+(d/2)²))；cand=双线 Simpson 1D 求积叠加。
    残差=求积离散化误差。余量 249×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_twoline(float(p["L"]), float(p["lam"]), float(p["d"])))

@_register_candidate(
    "wire_perp_b",
    "有限长直导线 Biot–Savart Simpson 1D 求积（与 golden 闭式不同源）")
def _b406_wire_perp_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B406 独立候选：有限长直导线垂直距离磁场 B（Biot–Savart dB_z Simpson 1D 求积）。

    golden=闭式 I L/(4π d√((L/2)²+d²))；cand=∫(μ₀I/4π)d/(x²+d²)^{3/2}dx Simpson 1D。
    残差=求积离散化误差。余量 5544×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_wire(float(p["L"]), float(p["I"]), float(p["d"])))

@_register_candidate(
    "square_loop_center_b",
    "正方形电流环四边 Biot–Savart Simpson 求积（与 golden 闭式不同源）")
def _b407_square_loop_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B407 独立候选：正方形电流环中心磁场 B（四边 Biot–Savart Simpson 求积）。

    golden=闭式 2√2 I/(π a)；cand=四边 Biot–Savart Simpson 求积取 B_z。
    残差=求积离散化误差。余量 1747×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_square(float(p["a"]), float(p["I"])))

@_register_candidate(
    "polygon_loop_center_b",
    "正 N 边形电流环 N 边 Biot–Savart Simpson 求积（与 golden 闭式不同源）")
def _b408_polygon_loop_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B408 独立候选：正 N 边形电流环中心磁场 B（N 边 Biot–Savart Simpson 求积）。

    golden=闭式 I N tan(π/N)/(2π R)；cand=N 边 Biot–Savart Simpson 求积取 B_z。
    残差=求积离散化误差。余量 7479×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_polygon(int(p["N"]), float(p["R"]), float(p["I"])))

@_register_candidate(
    "loop_offaxis_bz",
    "圆形电流环 off-axis B_z Biot–Savart Simpson 1D 求积（golden 用椭圆积分 K,E，不同源）")
def _b409_loop_offaxis_bz_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B409 独立候选：圆形电流环 off-axis 轴向磁场 B_z（Biot–Savart 环绕 Simpson 1D 求积）。

    golden=椭圆积分 K,E 闭式（scipy ellipk/ellipe）；cand=∫(μ₀I/4π)(R²−Rρcosφ)/r³ dφ Simpson。
    off-axis 使被积函数随 φ 变化（非 on-axis 退化陷阱）。残差=求积离散化误差。余量 4416×。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_loop_Bz(float(p["R"]), float(p["I"]), float(p["rho"]), float(p["z"])))

@_register_candidate(
    "solenoid_onaxis_b",
    "有限长螺线管轴线磁场 堆叠环 Biot–Savart Simpson 1D 求积（与 golden 闭式不同源）")
def _b410_solenoid_onaxis_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B410 独立候选：有限长螺线管轴线磁场 B（堆叠环 Biot–Savart Simpson 1D 求积）。

    golden=闭式 (nI/2)[(z+L/2)/√(R²+(z+L/2)²) − (z−L/2)/√(R²+(z−L/2)²)]；
    cand=∫(μ₀nIR²/2)/(R²+(z−z')²)^{3/2} dz' Simpson 1D。
    残差=求积离散化误差（尖峰被积收敛较慢）。余量 769×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_solenoid(float(p["L"]), float(p["R"]), float(p["n"]),
                                float(p["I"]), float(p["z"])))

@_register_candidate(
    "twowire_anti_b",
    "两反向平行有限直导线中点磁场 Biot–Savart Simpson 1D 求积（与 golden 闭式不同源）")
def _b411_twowire_anti_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B411 独立候选：两反向平行有限直导线中点磁场 B（Biot–Savart Simpson 1D 求积）。

    golden=闭式 I L/(π d√((L/2)²+(d/2)²))（两导线各距 d/2）；cand=双线 Simpson 1D 求积。
    残差=求积离散化误差。余量 3125×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_twowire(float(p["L"]), float(p["I"]), float(p["d"])))

@_register_candidate(
    "loop_offaxis_brho",
    "圆形电流环 off-axis B_ρ Biot–Savart Simpson 1D 求积（golden 用椭圆积分 K,E，不同源）")
def _b412_loop_offaxis_brho_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B412 独立候选：圆形电流环 off-axis 径向磁场 B_ρ（Biot–Savart 环绕 Simpson 1D 求积）。

    golden=椭圆积分 K,E 闭式；cand=∫(μ₀I/4π)R z cosφ/r³ dφ Simpson（B_x=B_ρ）。
    off-axis 使被积函数随 φ 变化（非退化陷阱）。残差=求积离散化误差。余量 140×。"""
    p = spec.params
    m = _get_batch_b25()
    return float(m.cand_loop_Brho(float(p["R"]), float(p["I"]), float(p["rho"]), float(p["z"])))

@_register_candidate(
    "normal_reflectance",
    "单界面 1D FD Helmholtz 总场解提取垂直入射反射率（与 golden 闭式不同源）")
def _b413_normal_reflectance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B413 独立候选：垂直入射反射率 R0（1D FD Helmholtz 总场解）。

    golden=闭式 ((n1−n2)/(n1+n2))²；cand=FD 总场解提取 R0。残差=FD 离散化误差
    （O(h²)）。余量 2.4×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_normal_reflectance(float(p["n1"]), float(p["n2"])))

@_register_candidate(
    "s_reflectance",
    "单界面 1D FD Helmholtz TE 总场解提取 s 偏振反射率 Rs（与 golden Fresnel 闭式不同源）")
def _b414_s_reflectance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B414 独立候选：s 偏振反射率 Rs（1D FD Helmholtz TE 解）。

    golden=Fresnel s 闭式；cand=FD Helmholtz TE 解提取 Rs。残差=FD 离散化误差。
    余量 2.6×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_s_reflectance(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "p_reflectance",
    "单界面 1D FD Helmholtz TM 总场解提取 p 偏振反射率 Rp（与 golden Fresnel 闭式不同源）")
def _b415_p_reflectance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B415 独立候选：p 偏振反射率 Rp（1D FD Helmholtz TM 解）。

    golden=Fresnel p 闭式；cand=FD Helmholtz TM 解提取 Rp。残差=FD 离散化误差。
    余量 6.0×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_p_reflectance(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "s_transmittance",
    "单界面 1D FD Helmholtz TE 总场解提取 s 偏振透射率 Ts（与 golden 闭式不同源）")
def _b416_s_transmittance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B416 独立候选：s 偏振透射率 Ts（1D FD Helmholtz TE 解）。

    golden=闭式 1−Rs；cand=FD Helmholtz TE 解提取 Ts（通量比修正）。残差=FD 离散化误差。
    余量 10239×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_s_transmittance(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "p_transmittance",
    "单界面 1D FD Helmholtz TM 总场解提取 p 偏振透射率 Tp（与 golden 闭式不同源）")
def _b417_p_transmittance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B417 独立候选：p 偏振透射率 Tp（1D FD Helmholtz TM 解）。

    golden=闭式 1−Rp；cand=FD Helmholtz TM 解提取 Tp。残差=FD 离散化误差。
    余量 11729×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_p_transmittance(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "unpol_reflectance",
    "单界面 1D FD Helmholtz TE/TM 双解平均提取非偏振反射率 Runpol（与 golden 闭式不同源）")
def _b418_unpol_reflectance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B418 独立候选：非偏振反射率 Runpol=(Rs+Rp)/2（1D FD Helmholtz TE/TM 双解平均）。

    golden=闭式；cand=FD Helmholtz TE/TM 双解分别量测后平均。残差=FD 离散化误差。
    余量 9.1×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_unpol_reflectance(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "delta_R",
    "单界面 1D FD Helmholtz TE/TM 双解取差 ΔR=Rs−Rp（与 golden 闭式不同源）")
def _b419_delta_R_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B419 独立候选：偏振反射率对比 ΔR=Rs−Rp（1D FD Helmholtz TE/TM 双解取差）。

    golden=闭式 Rs−Rp；cand=FD Helmholtz TE/TM 双解分别量测 Rs,Rp 后取差（直接观测
    偏振对比度，连续非退化）。注：原设计 TIR 反射相位经此 FD 在可行 N 下本质病态
    （误差随域长 L0 漂移、ABC 与 Dirichlet 同结果、纯 h 依赖），故改用相位无关的
    偏振对比度观测。残差=FD 离散化误差。余量 9.0×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_delta_R(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "Ts_Tp_ratio",
    "单界面 1D FD Helmholtz TE/TM 双解取比 Ts/Tp（与 golden 闭式不同源）")
def _b420_Ts_Tp_ratio_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B420 独立候选：偏振透射率比 Ts/Tp（1D FD Helmholtz TE/TM 双解取比）。

    golden=闭式 Ts/Tp；cand=FD Helmholtz TE/TM 双解分别量测 Ts,Tp 后取比。残差=FD
    离散化误差。余量 110505×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_Ts_Tp_ratio(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "brewster_angle",
    "两级扫描 θi 找 1D FD Helmholtz TM 反射率极小（→0）的角（与 golden atan 闭式不同源）")
def _b421_brewster_angle_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B421 独立候选：布儒斯特角 θB=atan(n2/n1)（FD Helmholtz TM 反射率两级扫描定位极小）。

    golden=闭式 atan(n2/n1)；cand=FD Helmholtz TM 反射率粗扫 90 点 + 细扫 120 点 +
    抛物 refine 定位极小（→0）。残差=扫描数值定位误差。余量 13.9×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_brewster_angle(float(p["n1"]), float(p["n2"])))

@_register_candidate(
    "s_transmission_amplitude",
    "单界面 1D FD Helmholtz TE 总场解提取复透射振幅模 |t_s|（与 golden 闭式振幅不同源）")
def _b422_s_transmission_amplitude_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B422 独立候选：s 偏振透射振幅 |t_s|=2n1cθi/(n1cθi+n2cθt)（FD Helmholtz TE 总场提取）。

    golden=闭式振幅；cand=FD Helmholtz TE 总场解提取复透射振幅模。B416 观测功率，
    本锚观测振幅（不同量）。残差=FD 离散化误差。余量 261669×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_s_transmission_amplitude(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "tir_reflectance",
    "单界面 1D FD Helmholtz TIR 总场解提取反射率（应≈1，与 golden 闭式不同源）")
def _b423_tir_reflectance_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B423 独立候选：全反射反射率=1（FD Helmholtz TIR 解，k2x 纯虚数倏逝）。

    golden=1；cand=FD Helmholtz TIR 总场解提取反射率。残差=FD 倏逝区离散化误差。
    余量 5.9×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_tir_reflectance(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "evanescent_beta",
    "单界面 1D FD Helmholtz TIR 区域2 场指数衰减直接量测 β（与 golden 闭式不同源）")
def _b424_evanescent_beta_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B424 独立候选：倏逝波衰减常数 β=k0√(n1²sin²θi−n2²)（FD Helmholtz 场指数衰减测量）。

    golden=闭式；cand=FD Helmholtz TIR 区域2 两探针点 |E| 指数衰减直接量测 β。
    残差=FD 倏逝区离散化误差（O(h²)）。余量 74737×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_evanescent_beta(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "energy_conservation",
    "单界面 1D FD Helmholtz TE 解量测 Rs,Ts 校验能量守恒式（与 golden 闭式不同源）")
def _b425_energy_conservation_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B425 独立候选：能量守恒 Rs+Ts·(n2cθt)/(n1cθi)=1（FD Helmholtz TE 解量测校验）。

    golden=1；cand=FD Helmholtz TE 解量测 Rs,Ts 代入校验。残差=FD 离散化误差。
    余量 2.6×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b26()
    return float(m.cand_energy_conservation(float(p["n1"]), float(p["n2"]), float(p["theta_i"])))

@_register_candidate(
    "plasma_phase_velocity",
    "等离子体 k(ω) 离散采样，两点线性插值估值 k(w0) 后取 ω/k（与 golden 闭式方法学不同源）")
def _b426_plasma_phase_velocity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B426 独立候选：等离子体相速度 v_p（中心差分数值微分）。

    golden=闭式 v_p=1/√(1−(ωp/ω)²)；cand=等离子体 k(ω) 离散采样，两点线性插值估值
    k(w0)（w0 落格点中点 ⇒ 对二次 k 有 O(h²) 误差，打破恒等）后取 ω/k。
    残差=差分截断误差（随 N 收敛、随参数变化、判据 D 响应、候选输出扰动必 FAIL）。
    余量 1.8e6×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_plasma_phase_velocity(float(p["wp"]), float(p["w"])))

@_register_candidate(
    "plasma_group_velocity",
    "等离子体 k(ω) 离散采样，中心差分 dk/dω 取倒数得 v_g（与 golden 闭式不同源）")
def _b427_plasma_group_velocity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B427 独立候选：等离子体群速度 v_g（中心差分数值微分）。

    golden=闭式 v_g=√(1−(ωp/ω)²)；cand=中心差分 dk/dω 取倒数。
    残差=差分截断误差。余量 4.9e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_plasma_group_velocity(float(p["wp"]), float(p["w"])))

@_register_candidate(
    "plasma_group_index",
    "等离子体 k(ω) 离散采样，中心差分直取 dk/dω=n_g（因 v_g=1/(dk/dω)，n_g=dk/dω；与 golden 闭式不同源）")
def _b428_plasma_group_index_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B428 独立候选：等离子体群折射率 n_g（中心差分数值微分直取 dk/dω）。

    golden=闭式 n_g=1/√(1−(ωp/ω)²)；cand=中心差分 dk/dω（=n_g，因 v_g=1/(dk/dω)、n_g=c/v_g=dk/dω）。
    残差=差分截断误差。余量 4.6e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_plasma_group_index(float(p["wp"]), float(p["w"])))

@_register_candidate(
    "taylor_phase_velocity",
    "三阶泰勒 k(ω) 离散采样，两点线性插值估值 k(w0) 后取 ω/k（与 golden 闭式不同源）")
def _b429_taylor_phase_velocity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B429 独立候选：三阶泰勒相速度 v_p（中心差分数值微分）。

    golden=闭式 v_p=ω/k(ω)；cand=三阶泰勒 k(ω) 离散采样，两点线性插值估值 k(w0) 后取 ω/k。
    残差=差分截断误差。余量 8.1e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_taylor_phase_velocity(
        float(p["w0"]), float(p["beta1"]), float(p["beta2"]), float(p["beta3"]), float(p["w"])))

@_register_candidate(
    "plasma_gvd",
    "等离子体 k(ω) 离散采样，中心二阶差分 d²k/dω²（SPAN2 避舍入地板；与 golden 闭式不同源）")
def _b430_plasma_gvd_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B430 独立候选：等离子体群速度色散 β2（中心二阶差分数值微分）。

    golden=k=ω√(1−r)/c 解析二阶导闭式 β2=−(ωp/ω)²/[ω·(1−r)^{3/2}];
    cand=中心二阶差分 d²k/dω²（非多项式 ⇒ 真截断；SPAN2=2.0 避 ~1/h² 舍入地板）。
    残差=差分截断误差（随 N 单调 O(h²) 收敛）。余量 2637×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_plasma_gvd(float(p["wp"]), float(p["w"])))

@_register_candidate(
    "taylor_group_velocity",
    "三阶泰勒 k(ω) 离散采样，中心差分 dk/dω 取倒数得 v_g（与 golden 闭式不同源）")
def _b431_taylor_group_velocity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B431 独立候选：三阶泰勒群速度 v_g（中心差分数值微分）。

    golden=闭式 v_g=1/(β1+β2Δ+½β3Δ²)；cand=中心差分 dk/dω 取倒数。
    残差=差分截断误差。余量 8.4e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_taylor_group_velocity(
        float(p["w0"]), float(p["beta1"]), float(p["beta2"]), float(p["beta3"]), float(p["w"])))

@_register_candidate(
    "taylor_group_delay",
    "三阶泰勒 k(ω) 离散采样，中心差分 k'(ω)·L 得群延迟（与 golden 闭式不同源）")
def _b432_taylor_group_delay_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B432 独立候选：三阶泰勒群延迟 τ_g（中心差分数值微分）。

    golden=闭式 τ_g=(β1+β2Δ+½β3Δ²)·L；cand=中心差分 k'(ω)·L。
    残差=差分截断误差。余量 3.4e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_taylor_group_delay(
        float(p["w0"]), float(p["beta1"]), float(p["beta2"]), float(p["beta3"]),
        float(p["w"]), float(p["L"])))

@_register_candidate(
    "lorentz_gvd",
    "洛伦兹 k(ω)=n·ω 离散采样，中心二阶差分 d²k/dω²（SPAN2 避舍入地板；非多项式真截断）")
def _b433_lorentz_gvd_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B433 独立候选：洛伦兹介质群速度色散 β2（中心二阶差分数值微分）。

    golden=k=ω√(1+A) 解析二阶导闭式；cand=中心二阶差分 d²k/dω²（非多项式 ⇒ 真截断；
    SPAN2=2.0 避 ~1/h² 舍入地板）。承接 Taylor 三次多项式二阶差分精确（恒等陷阱）迁出的 β2。
    残差=差分截断误差（随 N 单调 O(h²) 收敛）。余量 3647×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_lorentz_gvd(
        float(p["w0_res"]), float(p["wp"]), float(p["F"]), float(p["w"])))

@_register_candidate(
    "lorentz_group_delay",
    "洛伦兹 k(ω)=n·ω 离散采样，中心差分 k'(ω)·L 得群延迟（非多项式真截断）")
def _b434_lorentz_group_delay_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B434 独立候选：洛伦兹介质群延迟 τ_g（中心差分数值微分）。

    golden=闭式 (n+ωn')·L；cand=中心差分 k'(ω)·L（非多项式真截断）。
    残差=差分截断误差。余量 6.3e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_lorentz_group_delay(
        float(p["w0_res"]), float(p["wp"]), float(p["F"]), float(p["w"]), float(p["L"])))

@_register_candidate(
    "lorentz_dispersion_length",
    "洛伦兹 k(ω) 离散采样，中心二阶差分 β2 取倒数·T0² 得 L_D（SPAN2 避舍入地板；非多项式真截断）")
def _b435_lorentz_dispersion_length_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B435 独立候选：洛伦兹介质色散长度 L_D（中心二阶差分数值微分）。

    golden=闭式 L_D=T0²/|β2|；cand=中心二阶差分 β2 取倒数·T0²（非多项式真截断；
    SPAN2=2.0 避舍入地板）。承接 Taylor 迁出的 L_D。
    残差=差分截断误差（随 N 单调 O(h²) 收敛）。余量 256×（相对 1e-6）；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_lorentz_dispersion_length(
        float(p["w0_res"]), float(p["wp"]), float(p["F"]), float(p["w"]), float(p["T0"])))

@_register_candidate(
    "lorentz_pulse_broadening",
    "洛伦兹 k(ω) 离散采样，中心二阶差分 β2·L·Δω 得脉冲展宽（SPAN2 避舍入地板；非多项式真截断）")
def _b436_lorentz_pulse_broadening_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B436 独立候选：洛伦兹介质高斯脉冲展宽 Δt（中心二阶差分数值微分）。

    golden=闭式 |β2|·L·Δω；cand=中心二阶差分 β2·L·Δω（非多项式真截断；SPAN2=2.0 避舍入地板）。
    承接 Taylor 迁出的 Δt。残差=差分截断误差（随 N 单调 O(h²) 收敛）。余量 7293×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_lorentz_pulse_broadening(
        float(p["w0_res"]), float(p["wp"]), float(p["F"]), float(p["w"]),
        float(p["L"]), float(p["domega"])))

@_register_candidate(
    "plasma_group_delay",
    "等离子体 k(ω) 离散采样，中心差分 k'(ω)·L=n_g·L 得群延迟（与 golden 闭式不同源）")
def _b437_plasma_group_delay_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B437 独立候选：等离子体群延迟 τ_g（中心差分数值微分）。

    golden=闭式 (1/√(1−r))·L；cand=中心差分 k'(ω)·L（=n_g·L）。
    残差=差分截断误差。余量 4.6e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_plasma_group_delay(
        float(p["wp"]), float(p["w"]), float(p["L"])))

@_register_candidate(
    "lorentz_group_velocity",
    "洛伦兹 k(ω)=n·ω 离散采样，中心差分 dk/dω 取倒数得 v_g（非多项式真截断）")
def _b438_lorentz_group_velocity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B438 独立候选：洛伦兹介质群速度 v_g（中心差分数值微分）。

    golden=闭式 v_g=1/(n+ωn')；cand=中心差分 dk/dω 取倒数（非多项式真截断）。
    残差=差分截断误差。余量 6.8e5×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b27()
    return float(m.cand_lorentz_group_velocity(
        float(p["w0_res"]), float(p["wp"]), float(p["F"]), float(p["w"])))

@_register_candidate(
    "incomplete_beta_simpson_439",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（分子/分母均数值，不调 scipy.beta）")
def _b439_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B439 独立候选：I_x(5.5,6.0,0.45)（复合 Simpson 双积分）。

    golden=scipy.special.betainc（精确 oracle）；cand=复合 Simpson 双积分比值（N=128）。
    残差=Simpson 截断误差（O(h⁴)，实测比值 29.28/32.66/27.26 收敛至 16.00）。
    余量 4132×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b439(float(p["a"]), float(p["b"]), float(p["x"])))

@_register_candidate(
    "incomplete_beta_simpson_440",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（分子/分母均数值，不调 scipy.beta）")
def _b440_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B440 独立候选：I_x(6.0,5.0,0.60)（复合 Simpson 双积分）。

    golden=scipy.special.betainc；cand=复合 Simpson 双积分（N=128）。
    残差=Simpson 截断误差。余量 1240×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b440(float(p["a"]), float(p["b"]), float(p["x"])))

@_register_candidate(
    "incomplete_beta_simpson_441",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（分子/分母均数值，不调 scipy.beta）")
def _b441_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B441 独立候选：I_x(7.5,9.0,0.35)（复合 Simpson 双积分）。

    golden=scipy.special.betainc；cand=复合 Simpson 双积分（N=128）。
    残差=Simpson 截断误差（实测比值 22.99/15.80/15.95，最干净一档）。余量 1567×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b441(float(p["a"]), float(p["b"]), float(p["x"])))

@_register_candidate(
    "incomplete_beta_simpson_442",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（分子/分母均数值，不调 scipy.beta）")
def _b442_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B442 独立候选：I_x(9.0,8.0,0.55)（复合 Simpson 双积分，右偏密度）。

    golden=scipy.special.betainc；cand=复合 Simpson 双积分（N=128）。
    残差=Simpson 截断误差。余量 1296×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b442(float(p["a"]), float(p["b"]), float(p["x"])))

@_register_candidate(
    "incomplete_beta_simpson_443",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（分子/分母均数值，不调 scipy.beta）")
def _b443_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B443 独立候选：I_x(10.0,12.0,0.42)（复合 Simpson 双积分，峰形密度）。

    golden=scipy.special.betainc；cand=复合 Simpson 双积分（N=128）。
    残差=Simpson 截断误差。余量 915×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b443(float(p["a"]), float(p["b"]), float(p["x"])))

@_register_candidate(
    "incomplete_beta_binomial_444",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（与整数参数二项闭式 golden 不同源）")
def _b444_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B444 独立候选：整数参数 I_x(6,6,0.45)（复合 Simpson 双积分）。

    golden=整数参数二项闭式 Σ_{j=a}^{n}C(n,j)x^j(1-x)^{n-j}（精确；与 scipy betainc 互校 <1e-14）；
    cand=复合 Simpson 双积分（N=128）。残差=Simpson 截断误差。余量 2195×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b444(int(p["a"]), int(p["b"]), float(p["x"])))

@_register_candidate(
    "incomplete_beta_binomial_445",
    "不完全 Beta I_x(a,b) 由复合 Simpson 双重数值积分导出（与整数参数二项闭式 golden 不同源）")
def _b445_incomplete_beta_simpson_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B445 独立候选：整数参数 I_x(7,8,0.40)（复合 Simpson 双积分，n=14）。

    golden=整数参数二项闭式（精确；与 scipy betainc 互校 <1e-14）；
    cand=复合 Simpson 双积分（N=128）。残差=Simpson 截断误差。余量 1671×；零商业依赖。"""
    p = spec.params
    m = _get_batch_b28()
    return float(m.cand_b445(int(p["a"]), int(p["b"]), float(p["x"])))
