"""J2 超导 Transmon QPU 征程 · 物理错误模型（L2 物理比特层 · M0/M1 能力层）。

🔴 主权纪律：本模块是**能力验证**模块（功能门禁 `run_j2_qpu_smoke` 覆盖），**不是账本锚**；
纯标准库（`math`），零第三方依赖，全确定性（seed 无关）。与 `qec_noise.py` / `logical_error_rate.py`
同属「能力层」，与账本锚（B1+）零重叠、各司其职。

提供（单比特门物理错误模型）：
  · `gate_fidelity_decoherence` / `gate_error_decoherence`：**退相干极限平均门保真度**闭式
    F=(3+2e^{−t/T2}+e^{−t/T1})/6（↔ 门错误率 E=1−F）。
  · `gate_fidelity_lindblad_rk4`：Bloch 向量 Lindblad 主方程 **RK4 数值积分**（方法学独立候选，
    与闭式对拍——即 M1「闭式 ⇄ 数值 Lindblad」的能力实现）。
  · `dephasing_time_from_T2`：1/T2 = 1/(2T1) + 1/Tφ 反解纯去相位时间 Tφ。
  · `depolarizing_parameter`：门错误率 → J1 去极化噪声参数 p_depol=F_avg=1−p/2 口径。
  · `frequency_band_ok`：S 铁律① **频率限带守护**（f01 ∈ [5.0, 6.2] GHz）。

🔴🔴 同源声明（诚实边界 · 必读）：
  · 本模块 `gate_fidelity_decoherence` 的闭式与既有账本锚 **B10**（`benchmark_defs/part1.py`
    「单量子比特门保真度 F（退相干极限）」，v0.9.24 **已接入 Lindblad 候选** `lindblad_gate_f`）
    **完全同式**；`gate_fidelity_lindblad_rk4` 与其候选同方法族。
  · ⇒ **本模块不新增账本锚**（`lda-anchor-wiring` §0 同源体检：被测标量 / 物理构型 / 数值格式
    三者全同 = 「只是换名 ⇒ 否」）。J2 M0/M1 的**净增价值**在 `j2_to_j1_calibration` 的
    **J1↔J2 复利闭环桥**（该桥在既有锚/模块中均不存在）。
  · 单比特门保真度**已由 B10 全权覆盖** ⇒ J2 的新锚应落在既有锚未覆盖的物理量（M2 两比特 CR 门
    错误率 / M3 读出分配错误率 + 残余 ZZ / M4 拓扑对接），本模块只提供其输入量。

🔴 诚实边界：T1/T2/t_gate 为**设计示例量级**（非实测 PDK · 非流片数据）；本模块只证明
「闭式 ⇄ 数值」一致与 J2→J1 物理桥正确，**不作制造/性能宣称**，不报能效/TOPS/fJ-op。
"""
from __future__ import annotations

import math

__all__ = [
    "gate_fidelity_decoherence",
    "gate_error_decoherence",
    "gate_fidelity_lindblad_rk4",
    "dephasing_time_from_T2",
    "depolarizing_parameter",
    "frequency_band_ok",
]

#: S 铁律① 频率限带（GHz）——transmon f01 工作窗口，超出即 RED（复用，不重造）
BAND_LO_GHZ = 5.0
BAND_HI_GHZ = 6.2


def _check_physical(T1: float, T2: float, t_gate: float) -> None:
    """参数合法性：T1/T2 > 0，t_gate ≥ 0，且 T2 ≤ 2·T1（否则纯去相位率 1/Tφ < 0 非物理）。"""
    if T1 <= 0.0 or T2 <= 0.0:
        raise ValueError("T1 / T2 必须 > 0")
    if t_gate < 0.0:
        raise ValueError("t_gate 必须 ≥ 0")
    # 1/T2 = 1/(2T1) + 1/Tφ ⇒ Tφ>0 要求 1/T2 > 1/(2T1) ⇒ T2 < 2·T1；边界 T2=2T1 为纯弛豫
    if T2 > 2.0 * T1 * (1.0 + 1e-12):
        raise ValueError("非物理输入：T2 > 2·T1 ⇒ 纯去相位率 1/Tφ < 0")


def gate_fidelity_decoherence(t_gate: float, T1: float, T2: float) -> float:
    """golden 口径闭式：退相干极限**平均门保真度** F=(3+2e^{−t/T2}+e^{−t/T1})/6。

    🔴 与既有 B10 同式（本模块只作能力复算，不重复挂锚）；λ=0 时 F=1（理想门）。
    """
    _check_physical(T1, T2, t_gate)
    return float((3.0 + 2.0 * math.exp(-t_gate / T2) + math.exp(-t_gate / T1)) / 6.0)


def gate_error_decoherence(t_gate: float, T1: float, T2: float) -> float:
    """退相干极限门**错误率** E = 1 − F_avg（子阈值 QEC 的物理输入量 p_phys）。"""
    return float(1.0 - gate_fidelity_decoherence(t_gate, T1, T2))


def _bloch_rhs(x: float, y: float, z: float, T1: float, T2: float):
    """Bloch 向量 Lindblad 主方程（H=0 idle 门 · 振幅阻尼 + 纯去相位）：

        x' = −x/T2 ,  y' = −y/T2 ,  z' = −(z−1)/T1

    （z 向 +1=|0⟩ 弛豫；x/y 以 1/T2 去相位 —— 由 1/T2=1/(2T1)+1/Tφ 合并两通道。）
    """
    return (-x / T2, -y / T2, -(z - 1.0) / T1)


def _rk4_state(x: float, y: float, z: float, h: float, T1: float, T2: float):
    """经典四阶 Runge–Kutta 单步（残差 O(h⁴)，判据 D 标称阶同 RK4）。"""
    k1 = _bloch_rhs(x, y, z, T1, T2)
    k2 = _bloch_rhs(x + 0.5 * h * k1[0], y + 0.5 * h * k1[1], z + 0.5 * h * k1[2], T1, T2)
    k3 = _bloch_rhs(x + 0.5 * h * k2[0], y + 0.5 * h * k2[1], z + 0.5 * h * k2[2], T1, T2)
    k4 = _bloch_rhs(x + h * k3[0], y + h * k3[1], z + h * k3[2], T1, T2)
    return (x + h * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0,
            y + h * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0,
            z + h * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]) / 6.0)


def gate_fidelity_lindblad_rk4(t_gate: float, T1: float, T2: float,
                               n_steps: int = 256) -> float:
    """candidate：**Bloch 向量 Lindblad 主方程 RK4 数值积分** ⇒ 平均门保真度（方法学独立）。

    由 Bloch 仿射映射 r→M·r+c 提取 M=diag(Mxx,Myy,Mzz)，平均门保真度 F_avg=½+(1/6)·Tr(M)
    （Haar 平均 ⇒ 平移 c 不贡献，因 ∫r dψ=0）。数值积分 4 个初态（e_x/e_y/e_z/原点）得 M 与 c。
    残差来源 = RK4 截断（O(h⁴) 单调收敛）；与闭式 golden 方法学独立（数值积分 vs 解析闭式）。
    """
    _check_physical(T1, T2, t_gate)
    if n_steps < 1:
        raise ValueError("n_steps 必须 ≥ 1")
    h = t_gate / int(n_steps)

    def _evolve(x0: float, y0: float, z0: float):
        x, y, z = x0, y0, z0
        for _ in range(int(n_steps)):
            x, y, z = _rk4_state(x, y, z, h, T1, T2)
        return x, y, z

    mxx = _evolve(1.0, 0.0, 0.0)[0]             # x0=1 ⇒ x_out = Mxx（x 无平移）
    myy = _evolve(0.0, 1.0, 0.0)[1]             # y0=1 ⇒ y_out = Myy
    z1 = _evolve(0.0, 0.0, 1.0)[2]              # z0=1 ⇒ z_out = Mzz + c_z
    z0 = _evolve(0.0, 0.0, 0.0)[2]              # z0=0 ⇒ z_out = c_z
    mzz = z1 - z0                               # 消去平移 ⇒ Mzz
    return float(0.5 + (mxx + myy + mzz) / 6.0)


def dephasing_time_from_T2(T1: float, T2: float) -> float:
    """由 1/T2 = 1/(2T1) + 1/Tφ 反解**纯去相位时间** Tφ（1/Tφ>0 要求 T2<2T1）。"""
    if T1 <= 0.0 or T2 <= 0.0:
        raise ValueError("T1 / T2 必须 > 0")
    inv_tphi = 1.0 / T2 - 1.0 / (2.0 * T1)
    if inv_tphi <= 0.0:
        raise ValueError("非物理输入：1/Tφ ≤ 0（要求 T2 < 2·T1）")
    return float(1.0 / inv_tphi)


def depolarizing_parameter(t_gate: float, T1: float, T2: float) -> float:
    """门错误率 → J1 **去极化噪声参数** p_depol（口径 F_avg = 1 − p_depol/2 ⇒ p_depol = 2E）。

    🔴 口径钉死：J1 `qec_noise.sample_pauli_errors` 的 p 是单边 X 类错误概率；本函数给出
    与平均门保真度同口径的**去极化等效参数**（一个标量），供 J1↔J2 桥注入使用。
    """
    E = gate_error_decoherence(t_gate, T1, T2)
    return float(2.0 * E)


def frequency_band_ok(f01_ghz: float, lo: float = BAND_LO_GHZ, hi: float = BAND_HI_GHZ) -> bool:
    """S 铁律① **频率限带守护**：f01 ∈ [lo, hi] GHz 返回 True，否则 False（越界即 RED）。"""
    if hi < lo:
        raise ValueError("hi 必须 ≥ lo")
    return bool(lo <= float(f01_ghz) <= hi)
