# -*- coding: utf-8 -*-
"""蓝图 v2 · D1 光-量异质集成 · **M3 低温共集成热接口** —— Kapitza 界面热导（声子界面温跳）。

锚 **B524**：异质界面（金属换能器 / 半导体衬底）的**界面热导 h_K**（`W/(m²·K)`）与
界面热阻 `R_K = 1/h_K`（`m²·K/W`）。

物理链
------
1. **DMM（Diffuse Mismatch Model）声子透射概率**（声学 Debye · 全角度平均 ⇒ 与入射角无关）：
   由界面**细致平衡**给出 `α_{1→2}·Φ₁ = α_{2→1}·Φ₂`，且 `α_{1→2}+α_{2→1}=1`；
   入射声子通量 `Φ_i ∝ Σ_j D_{ij}·v_{ij} ∝ Σ_j 1/v_{ij}²`（Debye：`D ∝ ω²/v³`）
   ⇒ `α_{1→2} = v₁²/(v₁²+v₂²)`，`α_{2→1} = v₂²/(v₁²+v₂²)`（单支平均声速口径）。

2. **界面净热流**（Swartz–Pohl 形式）：
   `q = (1/4)·[α_{1→2}·v₁·C₁(T₁) + α_{2→1}·v₂·C₂(T₂)]·ΔT` ⇒
   **`h_K = (1/4)·[α_{1→2}·v₁·C₁ + α_{2→1}·v₂·C₂]`**
   （`C_i` = 单位体积声子热容；`1/4` 来自各向同性声子气的角度平均 `⟨cosθ⟩=1/2`×半球立体角归一）。

3. **低温 Debye 极限热容**（`T ≪ θ_D`，**精确**闭式，非截断近似）：
   `C(T) = (12π⁴/5)·n·k_B·(T/θ_D)³`
   （由 `U(T)=(3π⁴/5)n k_B T⁴/θ_D³` 对 T 求导；等价于 `C=9nk_B(T/θ)³·∫₀^∞ x⁴e^x/(e^x−1)²dx`，积分 `=4π⁴/15`）。

🔴 **为何低温极限**：Kapitza 热阻在**低温**（mK–K）是异质集成/低温 CMOS 与超导器件的
   实际瓶颈（`R_K ∝ T^{−3}` 在低 T 急剧放大）；取 `T ≪ θ_D` 使热容有**精确闭式**，
   避免「有限 Debye 截断 ⇒ 模型偏置」（这类偏置不可用压 tol 解决，见 BL 征程结论）。

🔴 **与既有锚避让（实 grep 全账本）**：`kapitza|界面热阻|thermal boundary|温跳|声学失配|dmm|amm`
   在 `BENCHMARK_DEFS` 内 **0 命中** ⇒ 界面热阻族零占用（本族首锚）。
   - vs **B465**（圆柱微通道壁面**径向** Fourier 热阻 `ln(r_o/r_i)/(2πkL)`）：那是**体材料**导热
     （连续温度场），本条是**界面温跳**（声子输运跨材料边界，`ΔT=q·R_K` 与体导热串联的另一物理量）。
   - vs **B518**（低温布线束**热负载** `Q(T)`）：那是沿温度轴的**积分量**（W），本条是界面**局部系数**。
   - vs **B466**（阵列**热串扰**比）：那是空间扩散耦合，本条是单界面输运。
   ⇒ 被测标量 / 物理构型 / 数值格式三处均异 ⇒ 非重复计数。

🔴 **诚实边界**：`θ_D / v / n` 为**设计示例量级**（Al / Si 的常用手册量级，非任何 foundry
   实测标定，非实测 Kapitza 数据）；模型为 **DMM + 声学 Debye + 单支平均声速**（未含真实
   声子色散、多支权重、界面粗糙度、氧化层、电子-声子耦合）；结论只可用于**数值方法与量级**，
   **不得作制造/性能宣称**，不报能效/TOPS/fJ-op。
🔴 零商业依赖（纯 `math`；零 RNG）。

确定性：本模块只做纯函数计算，无时钟/随机/文件 IO。
"""

from __future__ import annotations

import math

__all__ = [
    "K_B",
    "T_DEFAULT_K",
    "DEBYE_DEFAULTS",
    "dmm_transmission",
    "debye_energy_density_lowT",
    "debye_heat_capacity_lowT",
    "kapitza_conductance",
    "kapitza_resistance",
    "interface_thermal_report",
    "selfcheck_hetero_thermal",
]

#: 玻尔兹曼常数（J/K · CODATA 2018 精确值）
K_B = 1.380649e-23

#: 默认工作温度（K）—— 低温共集成（超导 / 低温 CMOS）区间
T_DEFAULT_K = 4.0

#: 设计示例材料参数（🔴 手册量级 · 非 foundry 标定 · 非实测）
DEBYE_DEFAULTS = {
    "side1": {  # 换能器金属（Al）
        "name": "Al",
        "theta_D_K": 428.0,
        "v_sound_m_s": 5100.0,
        "n_atom_m3": 6.02e28,
    },
    "side2": {  # 半导体衬底（Si）
        "name": "Si",
        "theta_D_K": 645.0,
        "v_sound_m_s": 6400.0,
        "n_atom_m3": 5.00e28,
    },
}

#: `∫₀^∞ x³/(e^x−1)dx = π⁴/15`（低温 Debye 内能系数来源）
_DEBYE_U_COEF = 3.0 * math.pi ** 4 / 5.0      # U = _DEBYE_U_COEF · n·k_B·T⁴/θ³
_DEBYE_C_COEF = 12.0 * math.pi ** 4 / 5.0     # C = _DEBYE_C_COEF · n·k_B·(T/θ)³


def _pos(x, name: str) -> float:
    v = float(x)
    if not v > 0.0:
        raise ValueError("%s 须 > 0" % name)
    return v


def dmm_transmission(v1_m_s: float, v2_m_s: float) -> float:
    """DMM 声子透射概率 `α_{1→2} = v₁²/(v₁²+v₂²)`（细致平衡 + `Φ ∝ 1/v²`）。"""
    v1 = _pos(v1_m_s, "v1_m_s")
    v2 = _pos(v2_m_s, "v2_m_s")
    return v1 * v1 / (v1 * v1 + v2 * v2)


def debye_energy_density_lowT(T_K: float, theta_D_K: float, n_atom_m3: float) -> float:
    """低温 Debye 声子能密度 `U = (3π⁴/5)·n·k_B·T⁴/θ³`（J/m³）。"""
    T = _pos(T_K, "T_K")
    th = _pos(theta_D_K, "theta_D_K")
    n = _pos(n_atom_m3, "n_atom_m3")
    return _DEBYE_U_COEF * n * K_B * (T ** 4) / (th ** 3)


def debye_heat_capacity_lowT(T_K: float, theta_D_K: float, n_atom_m3: float) -> float:
    """低温 Debye 声子热容 `C = (12π⁴/5)·n·k_B·(T/θ)³`（J/(m³·K)）。"""
    T = _pos(T_K, "T_K")
    th = _pos(theta_D_K, "theta_D_K")
    n = _pos(n_atom_m3, "n_atom_m3")
    return _DEBYE_C_COEF * n * K_B * (T / th) ** 3


def kapitza_conductance(T_K: float = T_DEFAULT_K,
                        side1: dict | None = None,
                        side2: dict | None = None) -> float:
    """Kapitza 界面热导 `h_K = (1/4)[α_{1→2}v₁C₁ + α_{2→1}v₂C₂]`（W/(m²·K)）。"""
    s1 = DEBYE_DEFAULTS["side1"] if side1 is None else side1
    s2 = DEBYE_DEFAULTS["side2"] if side2 is None else side2
    T = _pos(T_K, "T_K")
    v1 = _pos(s1["v_sound_m_s"], "side1.v_sound_m_s")
    v2 = _pos(s2["v_sound_m_s"], "side2.v_sound_m_s")
    a12 = dmm_transmission(v1, v2)
    a21 = 1.0 - a12
    C1 = debye_heat_capacity_lowT(T, s1["theta_D_K"], s1["n_atom_m3"])
    C2 = debye_heat_capacity_lowT(T, s2["theta_D_K"], s2["n_atom_m3"])
    return 0.25 * (a12 * v1 * C1 + a21 * v2 * C2)


def kapitza_resistance(T_K: float = T_DEFAULT_K,
                       side1: dict | None = None,
                       side2: dict | None = None) -> float:
    """界面热阻 `R_K = 1/h_K`（m²·K/W）。"""
    return 1.0 / kapitza_conductance(T_K, side1, side2)


def interface_thermal_report(T_K: float = T_DEFAULT_K) -> dict:
    """界面热预算只读报告（设计期签核量 · 零重计算：全部由闭式现算）。"""
    s1, s2 = DEBYE_DEFAULTS["side1"], DEBYE_DEFAULTS["side2"]
    v1, v2 = s1["v_sound_m_s"], s2["v_sound_m_s"]
    a12 = dmm_transmission(v1, v2)
    C1 = debye_heat_capacity_lowT(T_K, s1["theta_D_K"], s1["n_atom_m3"])
    C2 = debye_heat_capacity_lowT(T_K, s2["theta_D_K"], s2["n_atom_m3"])
    h = kapitza_conductance(T_K)
    return {
        "T_K": float(T_K),
        "materials": (s1["name"], s2["name"]),
        "alpha_1to2": a12,
        "alpha_2to1": 1.0 - a12,
        "C1_J_m3K": C1,
        "C2_J_m3K": C2,
        "h_K_W_m2K": h,
        "R_K_m2K_W": 1.0 / h,
        # 等效：1 µm² 面积上的界面热导（W/K）—— 便于与器件热预算对照
        "h_K_per_um2_W_K": h * 1e-12,
        "T_cubed_scaling": "h_K ∝ T³（低温 Debye 极限）",
        "verdict": "DESIGN_BUDGET",
        "honesty": ("θ_D/v/n 为设计示例量级（非 foundry 标定、非实测 Kapitza 数据）；"
                    "模型 DMM+声学 Debye+单支平均声速（未含色散/多支/粗糙度/氧化层）；"
                    "仅数值方法与量级，不作制造或性能宣称"),
    }


def selfcheck_hetero_thermal() -> dict:
    """能力层自检（纯结构 + 物理不变式 · 零 IO）。"""
    ch = {}
    s1, s2 = DEBYE_DEFAULTS["side1"], DEBYE_DEFAULTS["side2"]
    v1, v2 = s1["v_sound_m_s"], s2["v_sound_m_s"]

    a = dmm_transmission(v1, v2)
    ch["dmm_complementary"] = abs(a + dmm_transmission(v2, v1) - 1.0) < 1e-15
    ch["dmm_equal_media_half"] = abs(dmm_transmission(5000.0, 5000.0) - 0.5) < 1e-15
    ch["dmm_in_unit_interval"] = 0.0 < a < 1.0

    # C ∝ T³：温度翻倍 ⇒ 热容 ×8
    c4 = debye_heat_capacity_lowT(4.0, s1["theta_D_K"], s1["n_atom_m3"])
    c8 = debye_heat_capacity_lowT(8.0, s1["theta_D_K"], s1["n_atom_m3"])
    ch["capacity_cubic_scaling"] = abs(c8 / c4 - 8.0) < 1e-12
    ch["capacity_positive"] = c4 > 0.0

    # U 与 C 的关系：C = 4U/T（低温极限 ⇒ U ∝ T⁴）
    u4 = debye_energy_density_lowT(4.0, s1["theta_D_K"], s1["n_atom_m3"])
    ch["capacity_equals_4U_over_T"] = abs(c4 - 4.0 * u4 / 4.0) / c4 < 1e-12

    h4 = kapitza_conductance(4.0)
    h8 = kapitza_conductance(8.0)
    ch["kapitza_positive"] = h4 > 0.0
    ch["kapitza_cubic_scaling"] = abs(h8 / h4 - 8.0) < 1e-12
    ch["resistance_reciprocal"] = abs(kapitza_resistance(4.0) * h4 - 1.0) < 1e-15
    # 侧交换对称：h(1,2) == h(2,1)
    ch["side_swap_symmetric"] = (
        abs(kapitza_conductance(4.0, side1=s2, side2=s1) - h4) / h4 < 1e-15)
    ch["monotone_in_T"] = kapitza_conductance(2.0) < h4 < kapitza_conductance(6.0)
    # 量级门（设计示例 · Al/Si @4K 落在 1e4..1e6 W/m²K）
    ch["magnitude_in_design_band"] = 1e4 < h4 < 1e6

    rep = interface_thermal_report(4.0)
    ch["report_keys_present"] = all(
        k in rep for k in ("h_K_W_m2K", "R_K_m2K_W", "alpha_1to2", "C1_J_m3K", "verdict"))
    ch["report_matches_closed_form"] = abs(rep["h_K_W_m2K"] - h4) < 1e-9

    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    ch["rejects_nonpositive_T"] = _raises(lambda: kapitza_conductance(0.0))
    ch["rejects_nonpositive_theta"] = _raises(
        lambda: debye_heat_capacity_lowT(4.0, 0.0, 1e28))
    ch["rejects_negative_v"] = _raises(lambda: dmm_transmission(-1.0, 5000.0))
    return ch
