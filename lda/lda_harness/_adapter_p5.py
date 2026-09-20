# -*- coding: utf-8 -*-
"""验证适配器 · 分片 5/6（F-08 拆分自 `verification_adapters.py` · v0.9.117）。

覆盖原文件 L4639..L5761（122 个顶层定义）。正文**逐字节**取自原文，不重排、不重格式化。
🔴 装配顺序由 `verification_adapters.py` 的 import 次序决定，勿单独调整。
"""

from __future__ import annotations

from ._adapter_core import (
    _get_batch_b10, _get_batch_b11, _get_batch_b12, _get_batch_b13, _get_batch_b14,
    _get_batch_b15, _get_batch_b8, _get_batch_b9, _register_candidate,
)

from typing import (
    Any,
)

from .verification_spec import (
    VerificationSpec,
)

@_register_candidate(
    "b143_annulus_ab05_cand",
    "2D 圆环 (ν=½，Aharonov-Bohm 通量 Φ=½Φ₀) 由径向 FD 本征（半整数阶离心项）导出 ↔ 半整数阶 Bessel 交叉积零点闭式，方法学独立")
def _b143_annulus_ab05(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_annulus(0.5, 1, float(p["ri_nm"]), float(p["ro_nm"])))

@_register_candidate(
    "b144_annulus_ab15_cand",
    "2D 圆环 (ν=3/2，Aharonov-Bohm 通量 Φ=½Φ₀) 由径向 FD 本征导出 ↔ 半整数阶 Bessel 交叉积零点闭式，方法学独立")
def _b144_annulus_ab15(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_annulus(1.5, 1, float(p["ri_nm"]), float(p["ro_nm"])))

@_register_candidate(
    "b145_fsph_v1_cand",
    "3D 有限深球形阱 (V₀=1eV) 由 3D 径向 FD 本征（V=−V₀ 内 / 0 外，大盒）导出 ↔ 超越方程 k·cot(kR)=−κ 匹配闭式，方法学独立")
def _b145_fsph_v1(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_finite_sphere(float(p["V0_eV"]), float(p["R_nm"]), 1))

@_register_candidate(
    "b146_fsph_v5_cand",
    "3D 有限深球形阱 (V₀=5eV) 由 3D 径向 FD 本征导出 ↔ 超越方程闭式，方法学独立")
def _b146_fsph_v5(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_finite_sphere(float(p["V0_eV"]), float(p["R_nm"]), 1))

@_register_candidate(
    "b147_fsph_v10_cand",
    "3D 有限深球形阱 (V₀=10eV) 由 3D 径向 FD 本征导出 ↔ 超越方程闭式，方法学独立")
def _b147_fsph_v10(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_finite_sphere(float(p["V0_eV"]), float(p["R_nm"]), 1))

@_register_candidate(
    "b148_fsph_v10n2_cand",
    "3D 有限深球形阱 (V₀=10eV, ℓ=0 第 2 态) 由 3D 径向 FD 本征导出 ↔ 超越方程闭式，方法学独立")
def _b148_fsph_v10n2(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_finite_sphere(float(p["V0_eV"]), float(p["R_nm"]), 2))

@_register_candidate(
    "b149_ho3d_iso_cand",
    "3D 各向同性谐振子基态由三个 1D HO FD 谱 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立")
def _b149_ho3d_iso(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_ho3d_aniso(0, 0, 0, float(p["ox"]), float(p["oy"]), float(p["oz"])))

@_register_candidate(
    "b150_ho3d_aniso000_cand",
    "各向异性 3D 谐振子基态由三个 1D HO FD 谱 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立")
def _b150_ho3d_aniso000(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_ho3d_aniso(0, 0, 0, float(p["ox"]), float(p["oy"]), float(p["oz"])))

@_register_candidate(
    "b151_ho3d_aniso100_cand",
    "各向异性 3D 谐振子 (1,0,0) 由 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立")
def _b151_ho3d_aniso100(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_ho3d_aniso(1, 0, 0, float(p["ox"]), float(p["oy"]), float(p["oz"])))

@_register_candidate(
    "b152_ho3d_aniso111_cand",
    "各向异性 3D 谐振子 (1,1,1) 由 Kronecker 和导出 ↔ 可分离解析闭式，方法学独立")
def _b152_ho3d_aniso111(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b8()
    return float(m.cand_ho3d_aniso(1, 1, 1, float(p["ox"]), float(p["oy"]), float(p["oz"])))

@_register_candidate(
    "b153_beam_mode1_cand",
    "固支-固支 Euler-Bernoulli 梁第 1 阶横向振动频率由 Hermite 梁单元 FEM 广义本征 (Ne=200) 导出 ↔ 4 阶 ODE 超越方程 cos(βL)cosh(βL)=1 根闭式，方法学独立")
def _b153_beam_mode1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_beam(1, float(p["L_um"])))

@_register_candidate(
    "b154_beam_mode2_cand",
    "固支-固支梁第 2 阶频率由 Hermite 梁单元 FEM 广义本征导出 ↔ 超越方程根闭式，方法学独立")
def _b154_beam_mode2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_beam(2, float(p["L_um"])))

@_register_candidate(
    "b155_beam_mode3_cand",
    "固支-固支梁第 3 阶频率由 Hermite 梁单元 FEM 广义本征导出 ↔ 超越方程根闭式，方法学独立")
def _b155_beam_mode3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_beam(3, float(p["L_um"])))

@_register_candidate(
    "b156_beam_mode4_cand",
    "固支-固支梁第 4 阶频率由 Hermite 梁单元 FEM 广义本征导出 ↔ 超越方程根闭式，方法学独立")
def _b156_beam_mode4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_beam(4, float(p["L_um"])))

@_register_candidate(
    "b157_hulthen_n1_cand",
    "Hulthen 势 3D s-wave 第 1 束缚态由 3D 径向 FD 薛定谔本征导出 ↔ 超几何/Jacobi 精确闭式，方法学独立")
def _b157_hulthen_n1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_hulthen(1, float(p["V0_eV"]), float(p["a_nm"])))

@_register_candidate(
    "b158_hulthen_n2_cand",
    "Hulthen 势 3D s-wave 第 2 束缚态由 3D 径向 FD 本征导出 ↔ 精确闭式，方法学独立")
def _b158_hulthen_n2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_hulthen(2, float(p["V0_eV"]), float(p["a_nm"])))

@_register_candidate(
    "b159_hulthen_n3_cand",
    "Hulthen 势 3D s-wave 第 3 束缚态由 3D 径向 FD 本征导出 ↔ 精确闭式，方法学独立")
def _b159_hulthen_n3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_hulthen(3, float(p["V0_eV"]), float(p["a_nm"])))

@_register_candidate(
    "b160_hulthen_n4_cand",
    "Hulthen 势 3D s-wave 第 4 束缚态由 3D 径向 FD 本征导出 ↔ 精确闭式，方法学独立")
def _b160_hulthen_n4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_hulthen(4, float(p["V0_eV"]), float(p["a_nm"])))

@_register_candidate(
    "b161_fock_darwin_02_cand",
    "Fock-Darwin (n_r=0,m=2) 由 2D 径向 FD 本征 + L_z 项解析本征导出 ↔ 精确闭式，方法学独立")
def _b161_fock_darwin_02_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_fock_darwin(0, 2, float(p["B_T"])))

@_register_candidate(
    "b162_fock_darwin_03_cand",
    "Fock-Darwin (n_r=0,m=3) 由 2D 径向 FD 本征 + L_z 项导出 ↔ 精确闭式，方法学独立")
def _b162_fock_darwin_03_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_fock_darwin(0, 3, float(p["B_T"])))

@_register_candidate(
    "b163_fock_darwin_04_cand",
    "Fock-Darwin (n_r=0,m=4) 由 2D 径向 FD 本征 + L_z 项导出 ↔ 精确闭式，方法学独立")
def _b163_fock_darwin_04_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_fock_darwin(0, 4, float(p["B_T"])))

@_register_candidate(
    "b164_fock_darwin_12_cand",
    "Fock-Darwin (n_r=1,m=2) 由 2D 径向 FD 本征 + L_z 项导出 ↔ 精确闭式，方法学独立")
def _b164_fock_darwin_12_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_fock_darwin(1, 2, float(p["B_T"])))

@_register_candidate(
    "b165_rosen_morse_n0_cand",
    "Rosen-Morse II 势基态由 1D FD 本征导出 ↔ 超几何精确闭式（含奇宇称 tanh 项，非同 Pöschl-Teller），方法学独立")
def _b165_rosen_morse_n0_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_rosen_morse(0, float(p["C_eV"]), float(p["B_eV"])))

@_register_candidate(
    "b166_rosen_morse_n1_cand",
    "Rosen-Morse II 势第 1 激发态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立")
def _b166_rosen_morse_n1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_rosen_morse(1, float(p["C_eV"]), float(p["B_eV"])))

@_register_candidate(
    "b167_rosen_morse_n2_cand",
    "Rosen-Morse II 势第 2 激发态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立")
def _b167_rosen_morse_n2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_rosen_morse(2, float(p["C_eV"]), float(p["B_eV"])))

@_register_candidate(
    "b168_rosen_morse_n3_cand",
    "Rosen-Morse II 势第 3 激发态由 1D FD 本征导出 ↔ 超几何精确闭式，方法学独立")
def _b168_rosen_morse_n3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b9()
    return float(m.cand_rosen_morse(3, float(p["C_eV"]), float(p["B_eV"])))

@_register_candidate(
    "b169_mathieu_a0_cand",
    "Mathieu 偶族特征值 a₀ 由半周期 [0,π/2] P1-FEM 广义本征（BC=(N,N), k=0）导出 ↔ scipy Mathieu 特征值特殊函数，方法学独立")
def _b169_mathieu_a0_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_mathieu("a", 0, float(p["q"])))

@_register_candidate(
    "b170_mathieu_a1_cand",
    "Mathieu 偶族特征值 a₁ 由半周期 P1-FEM（BC=(N,D), k=0）导出 ↔ scipy Mathieu 特征值，方法学独立")
def _b170_mathieu_a1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_mathieu("a", 1, float(p["q"])))

@_register_candidate(
    "b171_mathieu_b1_cand",
    "Mathieu 奇族特征值 b₁ 由半周期 P1-FEM（BC=(D,N), k=0）导出 ↔ scipy Mathieu 特征值，方法学独立")
def _b171_mathieu_b1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_mathieu("b", 1, float(p["q"])))

@_register_candidate(
    "b172_mathieu_b2_cand",
    "Mathieu 奇族特征值 b₂ 由半周期 P1-FEM（BC=(D,D), k=0）导出 ↔ scipy Mathieu 特征值，方法学独立")
def _b172_mathieu_b2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_mathieu("b", 2, float(p["q"])))

@_register_candidate(
    "b173_mathieu_a2_cand",
    "Mathieu 偶族特征值 a₂ 由半周期 P1-FEM（BC=(N,N), k=1）导出 ↔ scipy Mathieu 特征值，方法学独立")
def _b173_mathieu_a2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_mathieu("a", 2, float(p["q"])))

@_register_candidate(
    "b174_ellipse_perimeter_2_1_cand",
    "椭圆截面周长（a=2 µm, b=1 µm）由纯数值复合 Simpson 4∫₀^{π/2}√(a²sin²θ+b²cos²θ)dθ 导出 ↔ 第二类椭圆积分 E(m) 特殊函数闭式，方法学独立")
def _b174_ellipse_perimeter_2_1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_ellipse_perimeter(float(p["a_um"]), float(p["b_um"])))

@_register_candidate(
    "b175_ellipse_perimeter_3_1_cand",
    "椭圆截面周长（高偏心度 a=3 µm, b=1 µm）由复合 Simpson 求积导出 ↔ 椭圆积分闭式，方法学独立")
def _b175_ellipse_perimeter_3_1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_ellipse_perimeter(float(p["a_um"]), float(p["b_um"])))

@_register_candidate(
    "b176_pendulum_135_cand",
    "大摆角单摆周期比（θ₀=135°）由纯数值复合 Simpson (2/π)∫₀^{π/2}dθ/√(1−m sin²θ) 导出 ↔ 第一类椭圆积分 K(m) 闭式，方法学独立")
def _b176_pendulum_135_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_pendulum(float(p["theta0_deg"])))

@_register_candidate(
    "b177_pendulum_150_cand",
    "大摆角单摆周期比（θ₀=150°，m→1 端点近奇异）由复合 Simpson 导出 ↔ 椭圆积分 K(m) 闭式，方法学独立")
def _b177_pendulum_150_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_pendulum(float(p["theta0_deg"])))

@_register_candidate(
    "b178_oblate_depol_Nc_cand",
    "扁椭球 c 轴去极化因子由 s→t 变换后的复合 Simpson 数值积分导出 ↔ 初等反正弦闭式，方法学独立")
def _b178_oblate_depol_Nc_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_oblate_Nc(float(p["ar"])))

@_register_candidate(
    "b179_prolate_depol_Na_cand",
    "长椭球 a 轴去极化因子由 s→t 变换后的复合 Simpson 数值积分导出 ↔ 初等对数闭式，方法学独立")
def _b179_prolate_depol_Na_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_prolate_Na(float(p["ar"])))

@_register_candidate(
    "b180_fresnel_C1_cand",
    "Fresnel 余弦积分 C(u) 由纯数值复合 Simpson 求积导出 ↔ scipy fresnel 特殊函数，方法学独立")
def _b180_fresnel_C1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_fresnel_C(float(p["u"])))

@_register_candidate(
    "b181_fresnel_S1_cand",
    "Fresnel 正弦积分 S(u) 由纯数值复合 Simpson 求积导出 ↔ scipy fresnel 特殊函数，方法学独立")
def _b181_fresnel_S1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_fresnel_S(float(p["u"])))

@_register_candidate(
    "b182_diffusion_profile_50nm_cand",
    "中心归一浓度剖面 R(x=50 nm) 由双端零通量 Crank-Nicolson 时间推进（相邻格点线性插值）导出 ↔ 高斯热核解析基础解，方法学独立")
def _b182_diffusion_profile_50nm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_diffusion(float(p["x_nm"])))

@_register_candidate(
    "b183_diffusion_profile_120nm_cand",
    "中心归一浓度剖面 R(x=120 nm) 由 Crank-Nicolson 时间推进导出 ↔ 高斯热核解析基础解，方法学独立")
def _b183_diffusion_profile_120nm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_diffusion(float(p["x_nm"])))

@_register_candidate(
    "b184_diffusion_profile_200nm_cand",
    "中心归一浓度剖面 R(x=200 nm，远场尾部) 由 Crank-Nicolson 时间推进导出 ↔ 高斯热核解析基础解，方法学独立")
def _b184_diffusion_profile_200nm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b10()
    return float(m.cand_diffusion(float(p["x_nm"])))

@_register_candidate(
    "b185_bose_moment_s4_cand",
    "玻色矩 s=4 由 t=x/(1+x) 换元后的 [0,1] 复合 Simpson 导出 ↔ Γ(s)ζ(s) 闭式，方法学独立")
def _b185_bose_moment_s4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b185(float(p["s"])))

@_register_candidate(
    "b186_bose_moment_s3_cand",
    "玻色矩 s=3 由换元 + 复合 Simpson 导出 ↔ 2ζ(3) 闭式，方法学独立")
def _b186_bose_moment_s3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b186(float(p["s"])))

@_register_candidate(
    "b187_fermi_moment_s3_cand",
    "费米矩 s=3 由换元 + 复合 Simpson 导出 ↔ (3/2)ζ(3) 闭式，方法学独立")
def _b187_fermi_moment_s3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b187(float(p["s"])))

@_register_candidate(
    "b188_debye_moment_s5_cand",
    "德拜矩 s=5 由换元 + 复合 Simpson 导出 ↔ Γ(5)ζ(4)=4π⁴/15 闭式，方法学独立")
def _b188_debye_moment_s5_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b188(float(p["s"])))

@_register_candidate(
    "b189_kepler_period_a1_cand",
    "轨道周期由中心力 ODE 的 RK4 时间积分（近心点穿越时刻差）导出 ↔ Kepler 第三定律闭式，方法学独立")
def _b189_kepler_period_a1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b189(float(p["a"])))

@_register_candidate(
    "b190_kepler_r_peri_cand",
    "近心点距离由 RK4 轨迹经三次 Hermite 插值定位穿越时刻后取 |r| 导出 ↔ a(1−e) 闭式，方法学独立")
def _b190_kepler_r_peri_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b190(float(p["a"]), float(p["ecc"])))

@_register_candidate(
    "b191_kepler_v_peri_cand",
    "近心点速率由 RK4 轨迹在 Hermite 定位的穿越时刻取 |v| 导出 ↔ 活力公式闭式，方法学独立")
def _b191_kepler_v_peri_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b191(float(p["a"]), float(p["ecc"])))

@_register_candidate(
    "b192_kepler_period_a2_cand",
    "宽轨道（a=2）周期由 RK4 时间积分导出 ↔ Kepler 解析闭式，方法学独立")
def _b192_kepler_period_a2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b192(float(p["a"])))

@_register_candidate(
    "b193_vf_parallel_1x1_cand",
    "角系数由 4D 张量积复合 Simpson 直接求积导出 ↔ 平行同轴矩形解析闭式，方法学独立")
def _b193_vf_parallel_1x1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b193(float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b194_vf_parallel_1x2_cand",
    "非方形平行矩形角系数由 4D 复合 Simpson 求积导出 ↔ 解析闭式，方法学独立")
def _b194_vf_parallel_1x2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b194(float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b195_vf_perp_common_edge_1x1_cand",
    "垂直共边角系数由 4D 分块复合 Simpson 求积导出 ↔ 解析闭式（含对数/反正切），方法学独立")
def _b195_vf_perp_common_edge_1x1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b195(float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b196_vf_perp_common_edge_2x1_cand",
    "垂直共边角系数（A=2,B=1）由 4D 分块复合 Simpson 导出 ↔ 解析闭式，方法学独立")
def _b196_vf_perp_common_edge_2x1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b196(float(p["a"]), float(p["b"]), float(p["c"])))

@_register_candidate(
    "b197_voigt_s1_g1_x0_cand",
    "Voigt 线心值由卷积定义式数值积分（τ=x+γ·sinh u 解析换元）导出 ↔ scipy voigt_profile（Faddeeva），方法学独立")
def _b197_voigt_s1_g1_x0_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b197(float(p["sigma"]), float(p["gamma"])))

@_register_candidate(
    "b198_voigt_s1_g05_x2_cand",
    "Voigt 远翼值由卷积数值积分导出 ↔ scipy voigt_profile，方法学独立")
def _b198_voigt_s1_g05_x2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b198(float(p["sigma"]), float(p["gamma"]), float(p["x"])))

@_register_candidate(
    "b199_voigt_s05_g2_x0_cand",
    "洛伦兹主导 Voigt 线心值由卷积数值积分导出 ↔ scipy voigt_profile，方法学独立")
def _b199_voigt_s05_g2_x0_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b199(float(p["sigma"]), float(p["gamma"])))

@_register_candidate(
    "b200_voigt_s2_g05_x3_cand",
    "Voigt 深远翼值由卷积数值积分导出 ↔ scipy voigt_profile，方法学独立")
def _b200_voigt_s2_g05_x3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b11()
    return float(m.cand_b200(float(p["sigma"]), float(p["gamma"]), float(p["x"])))

@_register_candidate(
    "b201_gl_pow_singular_cand",
    "端点幂奇性积分由 Gauss–Legendre n 节点高斯求积导出 ↔ 1/(1−p) 闭式，方法学独立")
def _b201_gl_pow_singular_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b201(float(p["p"])))

@_register_candidate(
    "b202_lag_frac_power_cand",
    "分数幂矩由 Gauss–Laguerre n 节点高斯求积导出 ↔ Γ(q+1) 闭式，方法学独立")
def _b202_lag_frac_power_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b202(float(p["q"])))

@_register_candidate(
    "b203_herm_abs_power_cand",
    "绝对值幂矩由 Gauss–Hermite n 节点高斯求积导出 ↔ Γ((p+1)/2) 闭式，方法学独立")
def _b203_herm_abs_power_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b203(float(p["p"])))

@_register_candidate(
    "b204_cheb_lorentz_cand",
    "Lorentz 型加权积分由 Gauss–Chebyshev n 节点高斯求积导出 ↔ π/√(1−a²) 闭式，方法学独立")
def _b204_cheb_lorentz_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b204(float(p["a"])))

@_register_candidate(
    "b205_cf_tan_cand",
    "tan x 由 Lambert 连分数 N 层截断递推导出 ↔ 初等超越闭式，方法学独立")
def _b205_cf_tan_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b205(float(p["x"])))

@_register_candidate(
    "b206_cf_arctan_cand",
    "arctan x 由 Euler 连分数 N 层截断导出 ↔ π/4 闭式，方法学独立")
def _b206_cf_arctan_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b206(float(p["x"])))

@_register_candidate(
    "b207_cf_coth_cand",
    "coth x 由双曲连分数 N 层截断（含 1/x 主项）导出 ↔ 初等闭式，方法学独立")
def _b207_cf_coth_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b207(float(p["x"])))

@_register_candidate(
    "b208_cf_sqrt1p_cand",
    "√(1+x) 由平方根连分数 N 层截断导出 ↔ 初等闭式（√2），方法学独立")
def _b208_cf_sqrt1p_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b208(float(p["x"])))

@_register_candidate(
    "b209_dk_x3_27_cand",
    "x³−27 实根由 Durand–Kerner 同时迭代导出（按实部最大选根，不借 golden）↔ a^{1/3} 闭式，方法学独立")
def _b209_dk_x3_27_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b209(float(p["a"])))

@_register_candidate(
    "b210_dk_x4_16_cand",
    "x⁴−16 实根由 Durand–Kerner 同时迭代导出 ↔ a^{1/4} 闭式，方法学独立")
def _b210_dk_x4_16_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b210(float(p["a"])))

@_register_candidate(
    "b211_dk_x5_243_cand",
    "x⁵−243 实根由 Durand–Kerner 同时迭代导出 ↔ a^{1/5} 闭式，方法学独立")
def _b211_dk_x5_243_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b211(float(p["a"])))

@_register_candidate(
    "b212_dk_x6_64_cand",
    "x⁶−64 实根由 Durand–Kerner 同时迭代导出 ↔ a^{1/6} 闭式，方法学独立")
def _b212_dk_x6_64_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b212(float(p["a"])))

@_register_candidate(
    "b213_hyp_asin_cand",
    "₂F₁(½,½;3/2;z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arcsin(z)/z 闭式，方法学独立")
def _b213_hyp_asin_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b213(float(p["z"])))

@_register_candidate(
    "b214_hyp_atanh_cand",
    "₂F₁(½,1;3/2;z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arctanh(z)/z 闭式，方法学独立")
def _b214_hyp_atanh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b214(float(p["z"])))

@_register_candidate(
    "b215_hyp_atan_cand",
    "₂F₁(½,1;3/2;−z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arctan(z)/z 闭式，方法学独立")
def _b215_hyp_atan_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b215(float(p["z"])))

@_register_candidate(
    "b216_hyp_asinh_cand",
    "₂F₁(½,½;3/2;−z²) 由 Euler 积分表示 + Gauss–Jacobi 求积导出 ↔ arcsinh(z)/z 闭式，方法学独立")
def _b216_hyp_asinh_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b12()
    return float(m.cand_b216(float(p["z"])))

@_register_candidate(
    "b217_gl_dhalf_const_cand",
    "D^0.5[1] 由 Grünwald–Letnikov 卷积差分（非整数阶、非局部算子）导出 ↔ 1/√(πt) 闭式，方法学独立")
def _b217_gl_dhalf_const_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b217(float(p["alpha"]), float(p["t"])))

@_register_candidate(
    "b218_gl_dhalf_linear_cand",
    "D^0.5[t] 由 Grünwald–Letnikov 卷积差分导出 ↔ √2/Γ(1.5) 闭式，方法学独立")
def _b218_gl_dhalf_linear_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b218(float(p["alpha"]), float(p["t"])))

@_register_candidate(
    "b219_gl_dhalf_cubic_cand",
    "D^0.5[t³] 由 Grünwald–Letnikov 卷积差分导出 ↔ 6/Γ(3.5) 闭式，方法学独立")
def _b219_gl_dhalf_cubic_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b219(float(p["alpha"]), float(p["t"])))

@_register_candidate(
    "b220_gl_dquarter_quad_cand",
    "D^0.25[t²] 由 Grünwald–Letnikov 卷积差分导出 ↔ 2/Γ(2.75) 闭式，方法学独立")
def _b220_gl_dquarter_quad_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b220(float(p["alpha"]), float(p["t"])))

@_register_candidate(
    "b221_matexp_rot1_cand",
    "exp(At)[0,1] 由自研 scaling–squaring（Taylor 截断 + 自乘 2^8）导出 ↔ −sin t 闭式，方法学独立")
def _b221_matexp_rot1_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b221(float(p["t"])))

@_register_candidate(
    "b222_matexp_rot25_cand",
    "exp(At)[0,1]（ω=2.5 旋转）由自研 scaling–squaring 导出 ↔ −sin(2.5t) 闭式，方法学独立")
def _b222_matexp_rot25_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b222(float(p["t"])))

@_register_candidate(
    "b223_matexp_damp_cand",
    "exp(At)[0,0]（A=diag(−1,−2)，t=1.5）由自研 scaling–squaring 导出 ↔ e^{−t} 闭式，方法学独立")
def _b223_matexp_damp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b223(float(p["t"])))

@_register_candidate(
    "b224_matexp_two_mode_cand",
    "exp(At)[0,0]（A=[[0,1],[−2,−3]]）由自研 scaling–squaring 导出 ↔ 2e^{−t}−e^{−2t} 闭式，方法学独立")
def _b224_matexp_two_mode_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b224(float(p["t"])))

@_register_candidate(
    "b225_gd_quartic_cand",
    "a(x⁴/4−x²/2) 的极小值由固定步长梯度下降（x₀=1.5, η=0.25, k 步）导出 ↔ −a/4 解析极小，方法学独立")
def _b225_gd_quartic_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b225(float(p["a"])))

@_register_candidate(
    "b226_gd_amgm_cand",
    "a/x + x 的极小值由固定步长梯度下降（x₀=3, η=0.30, k 步）导出 ↔ 2√a 解析极小，方法学独立")
def _b226_gd_amgm_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b226(float(p["a"])))

@_register_candidate(
    "b227_gd_free_energy_cand",
    "x ln x − b x 的极小值由固定步长梯度下降（x₀=2, η=0.30, k 步）导出 ↔ −e^{b−1} 解析极小，方法学独立")
def _b227_gd_free_energy_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b227(float(p["b"])))

@_register_candidate(
    "b228_gd_exp_potential_cand",
    "e^x − c x 的极小值由固定步长梯度下降（x₀=0, η=0.30, k 步）导出 ↔ c−c ln c 解析极小，方法学独立")
def _b228_gd_exp_potential_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b228(float(p["c"])))

@_register_candidate(
    "b229_volterra_exp_cand",
    "φ(1) 由分块梯形递推（含 k=j 隐式项移项）导出 ↔ 积分方程解析解，方法学独立")
def _b229_volterra_exp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b229(float(p["lam"])))

@_register_candidate(
    "b230_volterra_exp_long_cand",
    "φ(1.5) 由分块梯形递推导出 ↔ 积分方程解析解，方法学独立")
def _b230_volterra_exp_long_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b230(float(p["lam"])))

@_register_candidate(
    "b231_volterra_exp2_cand",
    "φ(1) 由分块梯形递推导出 ↔ 积分方程解析解 2−e^{−1}，方法学独立")
def _b231_volterra_exp2_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b231(float(p["lam"])))

@_register_candidate(
    "b232_volterra_ramp_cand",
    "φ(1) 由分块梯形递推导出 ↔ 积分方程解析解 cosh(√λx)，方法学独立")
def _b232_volterra_ramp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b13()
    return float(m.cand_b232(float(p["lam"])))

@_register_candidate(
    "b233_conv_diff_pe35_cand",
    "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立")
def _b233_conv_diff_pe35_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b233(float(p["pe"])))

@_register_candidate(
    "b234_conv_diff_pe50_cand",
    "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立")
def _b234_conv_diff_pe50_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b234(float(p["pe"])))

@_register_candidate(
    "b235_conv_diff_pe100_cand",
    "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立")
def _b235_conv_diff_pe100_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b235(float(p["pe"])))

@_register_candidate(
    "b236_conv_diff_pe200_cand",
    "θ(0.9) 由三点中心差分 + Thomas 追赶法导出 ↔ 定常对流–扩散方程闭式解，方法学独立")
def _b236_conv_diff_pe200_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b236(float(p["pe"])))

@_register_candidate(
    "b237_fredholm_lin2_one_cand",
    "φ(0.5) 由均匀节点梯形 Nyström 求积（稠密 (I−λWK)φ=f）导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立")
def _b237_fredholm_lin2_one_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b237(float(p["lam"])))

@_register_candidate(
    "b238_fredholm_lin2_exp_cand",
    "φ(0.5) 由均匀节点梯形 Nyström 求积导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立")
def _b238_fredholm_lin2_exp_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b238(float(p["lam"])))

@_register_candidate(
    "b239_fredholm_lin3_one_cand",
    "φ(0.5) 由均匀节点梯形 Nyström 求积导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立")
def _b239_fredholm_lin3_one_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b239(float(p["lam"])))

@_register_candidate(
    "b240_fredholm_lin2_cos_cand",
    "φ(0.5) 由均匀节点梯形 Nyström 求积导出 ↔ 第二类 Fredholm 可分核 resolvent 闭式，方法学独立")
def _b240_fredholm_lin2_cos_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b240(float(p["lam"])))

@_register_candidate(
    "b241_spline_e05s4_cand",
    "x₀ 点值由均匀节点自然三次样条（三对角解 M_j + 分段落值）导出 ↔ 初等闭式精确值，方法学独立")
def _b241_spline_e05s4_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b241(float(p["xq"])))

@_register_candidate(
    "b242_spline_at3_cand",
    "x₀ 点值由均匀节点自然三次样条导出 ↔ 初等闭式精确值，方法学独立")
def _b242_spline_at3_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b242(float(p["xq"])))

@_register_candidate(
    "b243_spline_e2x_cand",
    "x₀ 点值由均匀节点自然三次样条导出 ↔ 初等闭式精确值，方法学独立")
def _b243_spline_e2x_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b243(float(p["xq"])))

@_register_candidate(
    "b244_spline_rec_cand",
    "x₀ 点值由均匀节点自然三次样条导出 ↔ 初等闭式精确值，方法学独立")
def _b244_spline_rec_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b244(float(p["xq"])))

@_register_candidate(
    "b245_bvp_quad_cand",
    "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 y=(1+βx)^{−2}，方法学独立")
def _b245_bvp_quad_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b245(float(p["beta"])))

@_register_candidate(
    "b246_bvp_cubic_cand",
    "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 y=(1+βx)^{−1}，方法学独立")
def _b246_bvp_cubic_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b246(float(p["beta"])))

@_register_candidate(
    "b247_bvp_tan_cand",
    "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 √c·tan(√c x)，方法学独立")
def _b247_bvp_tan_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b247(float(p["cc"])))

@_register_candidate(
    "b248_bvp_log_cand",
    "y(0.5) 由 RK4 + 未知初斜率 s 打靶命中右端 BC 导出 ↔ 非线性 ODE 初等闭式 ln(1+x(e^{y1}−1))，方法学独立")
def _b248_bvp_log_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b14()
    return float(m.cand_b248(float(p["y1"])))

@_register_candidate(
    "b249_dde_steps_cand",
    "y(1.2) 由分步法（每步 RK4 等效 Simpson）+ 已算出历史点的三次 Hermite 插值导出 ↔ 延迟微分方程初等闭式 e^{−rT}，方法学独立")
def _b249_dde_steps_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b249(float(p["r"]), float(p["T"])))

@_register_candidate(
    "b250_dde_steps_cand",
    "y(1.2) 由分步法 + 历史点三次 Hermite 插值导出 ↔ 延迟微分方程初等闭式 e^{−rT}，方法学独立")
def _b250_dde_steps_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b250(float(p["r"]), float(p["T"])))

@_register_candidate(
    "b251_dde_steps_cand",
    "y(1.2) 由分步法 + 历史点三次 Hermite 插值导出 ↔ 延迟微分方程初等闭式 e^{−rT}，方法学独立")
def _b251_dde_steps_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b251(float(p["r"]), float(p["T"])))

@_register_candidate(
    "b252_dde_steps_cand",
    "y(1.2) 由分步法 + 历史点三次 Hermite 插值导出 ↔ 延迟微分方程初等闭式 e^{−rT}，方法学独立")
def _b252_dde_steps_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b252(float(p["r"]), float(p["T"])))

@_register_candidate(
    "b253_biharmonic_plate_cand",
    "中心挠度由 13 点双调和模板（≡5 点 Laplacian 复合）+ 简支 ghost 消去 w_ghost=−w_mirror 导出 ↔ 初等正弦闭式 q0/(4π⁴D)，方法学独立")
def _b253_biharmonic_plate_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b253(float(p["q0"]), float(p["dp"])))

@_register_candidate(
    "b254_biharmonic_plate_cand",
    "中心挠度由 13 点双调和差分 + 简支 ghost 消去导出 ↔ 初等闭式 q0/(4π⁴D)，方法学独立")
def _b254_biharmonic_plate_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b254(float(p["q0"]), float(p["dp"])))

@_register_candidate(
    "b255_biharmonic_plate_cand",
    "中心挠度由 13 点双调和差分 + 简支 ghost 消去导出 ↔ 初等闭式 q0/(4π⁴D)，方法学独立")
def _b255_biharmonic_plate_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b255(float(p["q0"]), float(p["dp"])))

@_register_candidate(
    "b256_biharmonic_plate_cand",
    "中心挠度由 13 点双调和差分 + 简支 ghost 消去导出 ↔ 初等闭式 q0/(4π⁴D)，方法学独立")
def _b256_biharmonic_plate_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b256(float(p["q0"]), float(p["dp"])))

@_register_candidate(
    "b257_transport_semilag_cand",
    "u(0.40,0.5) 由特征线逆追踪（落点 x_j−CFL·h 非格点）+ 4 点立方 Lagrange 重构导出 ↔ 输运方程刚性平移闭式 u0(x−ct)，方法学独立")
def _b257_transport_semilag_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b257(float(p["c"]), float(p["T"]), float(p["xs"])))

@_register_candidate(
    "b258_transport_semilag_cand",
    "u(0.30,0.5) 由半拉格朗日特征线 + 4 点立方 Lagrange 重构导出 ↔ 输运方程刚性平移闭式 u0(x−ct)，方法学独立")
def _b258_transport_semilag_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b258(float(p["c"]), float(p["T"]), float(p["xs"])))

@_register_candidate(
    "b259_transport_semilag_cand",
    "u(0.30,0.5) 由半拉格朗日特征线 + 4 点立方 Lagrange 重构导出 ↔ 输运方程刚性平移闭式 u0(x−ct)，方法学独立")
def _b259_transport_semilag_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b259(float(p["c"]), float(p["T"]), float(p["xs"])))

@_register_candidate(
    "b260_transport_semilag_cand",
    "u(0.30,0.5) 由半拉格朗日特征线 + 4 点立方 Lagrange 重构导出 ↔ 输运方程刚性平移闭式 u0(x−ct)，方法学独立")
def _b260_transport_semilag_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b260(float(p["c"]), float(p["T"]), float(p["xs"])))

@_register_candidate(
    "b261_nlse_soliton_cand",
    "Re u(x*,T) 由算子分裂（NL(dt/2)→L(dt)→NL(dt/2)，NL 相位 2|u|²dt）+ FFT 谱精确线性步导出 ↔ 孤子闭式 A·sech(A(x−x0))·cos(A²T)，方法学独立")
def _b261_nlse_soliton_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b261(float(p["A"]), float(p["x0"])))

@_register_candidate(
    "b262_nlse_soliton_cand",
    "Re u(x*,T) 由分裂步 Fourier（Strang）+ FFT 谱线性步导出 ↔ 孤子闭式，方法学独立")
def _b262_nlse_soliton_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b262(float(p["A"]), float(p["x0"])))

@_register_candidate(
    "b263_nlse_soliton_cand",
    "Re u(x*,T) 由分裂步 Fourier（Strang）+ FFT 谱线性步导出 ↔ 孤子闭式，方法学独立")
def _b263_nlse_soliton_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b263(float(p["A"]), float(p["x0"])))

@_register_candidate(
    "b264_nlse_soliton_cand",
    "Re u(x*,T) 由分裂步 Fourier（Strang）+ FFT 谱线性步导出 ↔ 孤子闭式，方法学独立")
def _b264_nlse_soliton_cand(spec: VerificationSpec, oracle_value: Any) -> float:
    p = spec.params
    m = _get_batch_b15()
    return float(m.cand_b264(float(p["A"]), float(p["x0"])))
