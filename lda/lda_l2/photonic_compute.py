"""LDA L2 · 光子计算芯片 · 非酉权重矩阵的光学乘加（光计算征程 M1）。

============================================================================
光计算征程定位（与量子/光子征程同一四层红线纪律，详见 IRONLAWS.md）
----------------------------------------------------------------------------
本模块补的**平台能力短板**：LDA 既往的 mzi_mesh_matmul 只能做**酉**矩阵乘
（Reck 分解只收酉输入）。而真正的计算芯片要做**任意（非酉）权重矩阵**的乘加——
标准做法是 SVD 分解 W = U·Σ·V†：
  · U、V† 为酉（N×N）→ 各用一片 MZI 网格实现（复用 reck_triangular_mesh）；
  · Σ 为实数对角（奇异值）→ 用对角衰减（VOA / 幅度均衡）实现。
这样光子芯片就能做**任意线性变换**（矩阵-向量乘、MAC 阵列的基础）。

纪律：
- C 级自主：纯 numpy，零外部求解器；不借 Meep / Tidy3D（A 级禁）；
- LLM 不进判决路径：全部死标量 / numpy 运算；
- 物理锚沿用 mzi_mesh_matmul（CMT 耦合长度 / Vπ·L 电压）与 mesh_pnr
  （主权 GDS / DRC / LVS）；
- 诚实边界：本模块演示「任意权重矩阵可由 SVD → 双 MZI 网格 + 对角衰减」实现，
  且 Σ 在**理想衰减**模型下复现 numpy 数值（机器精度）。物理损耗 / 量化 / 光电
  读出由 mesh_loss_basis（损耗预算）、amplitude_equalization 框架（VOA 选型）、
  及 M2/M3 里程碑覆盖——不虚报已具备相干实测或电子 co-sim。
============================================================================

光学 MVM 光路实现：
    x → [V† 网格] → [diag(Σ) 对角衰减] → [U 网格] → 探测 = y = W·x
（顺序依 SVD 标准：W = U Σ V†，故 x 先经 V† 再经 Σ 再经 U。）
"""
from __future__ import annotations

import math
import numpy as np

from lda_l2.mzi_mesh_matmul import (
    reck_triangular_mesh,
    assemble_triangular_mesh,
    unitary_fidelity,
    mesh_loss_basis,
    voltage_from_phase,
    VPI_L_V_CM,
)
from lda_layout.mesh_pnr import build_mesh_pnr, write_mesh_gds

__all__ = [
    "svd_decompose_weights",
    "photonic_mv_multiply",
    "verify_photonic_compute",
    "build_compute_core_gds",
    "quantize_phase",
    "apply_phase_model",
    "mesh_transfer_with_model",
    "photonic_activation",
    "photonic_layer_forward",
    "make_toy_classifier",
    "golden_classify",
    "end_to_end_inference",
    "verify_photonic_compute_m2",
    "RED_LINE_DISCLOSURE_PC",
]


# ---------------------------------------------------------------------------
# SVD · 非酉 → 酉(双网格) + 对角衰减
# ---------------------------------------------------------------------------
def svd_decompose_weights(W: np.ndarray):
    """SVD 分解任意（含非酉）权重矩阵 W = U · diag(S) · Vh。

    - U, Vh 为酉（N×N），S 为非负奇异值（降序）。
    - 光计算实现：x → Vh(网格) → diag(S)(对角衰减) → U(网格) → 探测。
    返回 (U, S, Vh)，均为 numpy 数组。
    """
    W = np.array(W, dtype=complex)
    U, S, Vh = np.linalg.svd(W, full_matrices=False)
    return U, S, Vh


def photonic_mv_multiply(W: np.ndarray, x: np.ndarray) -> np.ndarray:
    """光学矩阵-向量乘 y = W·x 的理想模型（SVD + 双网格 + 对角衰减）。

    返回光学输出 y_opt（复向量）。理想衰减下 == W·x（机器精度）。
    """
    U, S, Vh = svd_decompose_weights(W)
    x = np.array(x, dtype=complex)
    y = U @ (S * (Vh @ x))          # x → V† → Σ(衰减) → U → 探测
    return y


# ---------------------------------------------------------------------------
# 端到端验证锚（CI 可判）
# ---------------------------------------------------------------------------
def verify_photonic_compute(W: np.ndarray, x: np.ndarray,
                           n_crossings: int = 0) -> dict:
    """端到端验证：光学 MVM 与 numpy 参考 y_ref = W·x 比对，并附各网格重构保真度与损耗预算。

    判据（M1 接受闸）：
      - fid_U, fid_V ≥ 0.9999999（三角网格机器精度复现酉）
      - mvm_fidelity ≥ 0.999（理想衰减模型下 == numpy）
    """
    W = np.array(W, dtype=complex)
    x = np.array(x, dtype=complex)
    N = W.shape[0]
    U, S, Vh = svd_decompose_weights(W)

    # 网格重构（三角 mesh，机器精度复现 U / Vh）
    ops_U, D_U = reck_triangular_mesh(U)
    U_rec = assemble_triangular_mesh(ops_U, D_U, N)
    ops_V, D_V = reck_triangular_mesh(Vh)
    Vh_rec = assemble_triangular_mesh(ops_V, D_V, N)

    fid_U = unitary_fidelity(U_rec, U)
    fid_V = unitary_fidelity(Vh_rec, Vh)

    # 光学 MVM（理想模型）
    y_opt = photonic_mv_multiply(W, x)
    y_ref = W @ x
    mvm_err = float(np.linalg.norm(y_opt - y_ref))
    norm_ref = float(np.linalg.norm(y_ref))
    mvm_fid = float(max(0.0, 1.0 - mvm_err / (N * math.sqrt(2.0) * max(1.0, norm_ref))))

    # 损耗预算（U / Vh 各一片三角网格）
    loss_U = mesh_loss_basis(ops_U, n_crossings=n_crossings)
    loss_V = mesh_loss_basis(ops_V, n_crossings=n_crossings)

    return {
        "N": N,
        "n_mzi_U": len(ops_U),
        "n_mzi_V": len(ops_V),
        "fidelity_U_mesh": fid_U,
        "fidelity_V_mesh": fid_V,
        "svd_singular_values": [float(s) for s in S],
        "mvm_err_fro": mvm_err,
        "mvm_fidelity": mvm_fid,
        "y_ref": [complex(v) for v in y_ref],
        "y_opt": [complex(v) for v in y_opt],
        "loss_U_mesh": loss_U,
        "loss_V_mesh": loss_V,
    }


# ---------------------------------------------------------------------------
# 主权 GDS（证明「真实可制造」）
# ---------------------------------------------------------------------------
def build_compute_core_gds(W: np.ndarray, out_dir: str,
                           which: str = "U") -> dict:
    """对计算核的酉部分（U 或 V†）产出主权 GDS + DRC/LVS 签核。

    返回 build_mesh_pnr 报告 dict（含 gds_bytes / drc_pass / lvs_verdict /
    layout_fidelity），并落盘 GDS 文件。V† 与 U 同模块，M1 演示其一即证明可制造性。
    """
    import os
    U, S, Vh = svd_decompose_weights(W)
    target = U if which == "U" else Vh
    rep = build_mesh_pnr(target)      # 默认 serpentine，小 N 秒级
    os.makedirs(out_dir, exist_ok=True)
    fname = f"compute_core_{which}_{rep['N']}x{rep['N']}.gds"
    gds_path = write_mesh_gds(rep, os.path.join(out_dir, fname))
    rep["gds_path"] = gds_path
    return rep


# ===========================================================================
# M2 · 性能爬坡：相位量化 + 相位标定闭环 + 非线性激活 + 端到端计算精度锚
# ---------------------------------------------------------------------------
# 本段补的**平台能力短板**（M1 只做了理想模型下的任意线性变换）：
#   · 相位量化：相移器有限比特分辨率 → 网格传递矩阵退化模型；
#   · 相位标定闭环：Vπ·L 物理定律下，标称指令电压 → 真实器件相位，并用探针
#     反估真实 Vπ 补偿（V↔φ↔T 自洽）；
#   · 非线性激活：检测后（电子/光电域）激活函数（relu/sigmoid/tanh）——平台既往
#     无激活模块；
#   · 端到端精度锚：两层网络「光学 MVM→探测→激活」对比 numpy 参考管线，报告
#     MAC 误差与分类精度，并量化「量化/标定误差 → 精度退化 → 标定回收」链路。
#
# 纪律（沿用 M1）：
# - C 级自主（纯 numpy），不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径；
# - 所有参考为闭式 / numpy 自洽（golden 与 candidate 同源数学，判据为浮点级吻合，
#   非「自证桩」——真变更会动、扰动会动，见 run_photonic_compute_m2_smoke.py 反向断言）；
# - 诚实边界：量化/标定为**模型级**能力（有限分辨率 / Vπ 增益误差），真实器件的
#   热串扰、Vπ 漂移、片上非线性光学元件物理属 B 类外部，非本模块 golden（见披露块）。
# ===========================================================================

def quantize_phase(phi: float, n_bits: int):
    """把相位 φ 量化到 n_bits（2^n 电平，范围 [0, 2π) 周期映射）。

    n_bits<=0 / None → 不量化（原样返回）。这是相移器有限比特分辨率的物理模型。
    """
    if n_bits is None or n_bits <= 0:
        return float(phi)
    twopi = 2.0 * math.pi
    p = phi % twopi
    n_levels = 2 ** n_bits
    step = twopi / n_levels
    idx = int(round(p / step))
    if idx >= n_levels:
        idx = n_levels - 1
    return float(idx * step)


def apply_phase_model(ops, D, N, n_bits=None, vpi_cmd=VPI_L_V_CM,
                     vpi_real=None, calibrate=True):
    """对 MZI 网格施加有限精度（量化）+ 相位标定模型，返回 (ops_eff, D_eff)。

    - 量化：MZI 的 φ 与对角相位层 D 的相位均量化到 n_bits；
    - 标定：标称 Vπ 指令相位→电压，真实器件 Vπ_real 把电压回译为相位；
      若 calibrate=True，先用标准探针（π/2 命令）反估 vpi_real，回令时补偿；
    - 仅影响相位（θ 由耦合器几何决定，属 B 类外部，本模块不扰动）。
    """
    vpi_use = vpi_cmd
    if vpi_real is not None and calibrate:
        # 探针：命令 π/2 → 测得真实相位 = π/2 · vpi_cmd/vpi_real → 反估 vpi_real。
        probe_phi_cmd = math.pi / 2.0
        v_probe = voltage_from_phase(probe_phi_cmd, vpi_l_v_cm=vpi_cmd)
        phi_probe_real = math.pi * v_probe / vpi_real
        vpi_use = math.pi * v_probe / phi_probe_real  # 模型自洽 ⇒ = vpi_real

    def _map(phi):
        if vpi_real is not None:
            # 指令电压用「标定后」的 vpi_use：标定时 vpi_use=vpi_real（探针反估），
            # 设备回译 φ_real=π·V/vpi_real 即还原目标相位；未标定时 vpi_use=vpi_cmd(标称)
            # ⇒ φ_real 被 vpi_nominal/vpi_real 缩放 ⇒ 退化。
            v = voltage_from_phase(phi, vpi_l_v_cm=vpi_use)
            phi = math.pi * v / vpi_real
        if n_bits and n_bits > 0:
            phi = quantize_phase(phi, n_bits)
        return float(phi)

    ops_eff = [(c, p, th, _map(phi)) for (c, p, th, phi) in ops]
    dph = [math.atan2(D[k, k].imag, D[k, k].real) for k in range(N)]
    dph_eff = [_map(dp) for dp in dph]
    D_eff = np.diag([complex(math.cos(dp), math.sin(dp)) for dp in dph_eff]).astype(complex)
    return ops_eff, D_eff


def mesh_transfer_with_model(U, n_bits=None, vpi_real=None, calibrate=True,
                             vpi_cmd=VPI_L_V_CM):
    """对酉 U 做三角 mesh 分解，施加相位模型后返回 (U_eff, ops_eff, D_eff, fid)。

    fid = unitary_fidelity(U_eff, U)：有限精度 / 标定误差下网格传递矩阵的退化度量。
    """
    U = np.array(U, dtype=complex)
    N = U.shape[0]
    ops, D = reck_triangular_mesh(U)
    ops_eff, D_eff = apply_phase_model(ops, D, N, n_bits=n_bits,
                                       vpi_cmd=vpi_cmd, vpi_real=vpi_real,
                                       calibrate=calibrate)
    U_eff = assemble_triangular_mesh(ops_eff, D_eff, N)
    fid = unitary_fidelity(U_eff, U)
    return U_eff, ops_eff, D_eff, fid


def photonic_activation(z, kind="relu", beta=1.0):
    """非线性激活（检测后电子/光电域实现 · 平台 M2 新增能力）。

    kind: 'relu' | 'sigmoid' | 'tanh'；z 为实值（光探测后信号）。
    诚实边界：本函数实现检测后（电子/光电）激活的数学；片上非线性光学元件
    （可饱和吸收 / 相变材料阈值）物理属 B 类外部，非本模块 golden。
    """
    z = float(z)
    if kind == "relu":
        return max(0.0, z)
    if kind == "sigmoid":
        return 1.0 / (1.0 + math.exp(-beta * z))
    if kind == "tanh":
        return math.tanh(beta * z)
    raise ValueError(f"未知激活 {kind}")


def _square_embed(W):
    """把任意（含非方阵）权重矩阵 W(M×K) 方阵嵌入为 W = U_full·Σ_full·V_full。

    U_full(M×M)、V_full(K×K) 均为酉（分别由 SVD 的 U0/Vh0 经零空间补全到酉）；
    Σ_full(M×K) 仅在左上 min(M,K) 对角放奇异值。这样非方阵层也能走 MZI 网格
    （三角 mesh 只收方阵酉输入），且 full 精度下 W_eff == W（机器精度）。
    """
    W = np.array(W, dtype=complex)
    M, K = W.shape
    min_ = min(M, K)
    U0, S, Vh0 = np.linalg.svd(W, full_matrices=False)  # U0 M×min, Vh0 min×K

    # U_full：补全 U0 的列到 M×M 酉（前 min 列 = U0）
    if M > min_:
        _, _, Vt = np.linalg.svd(U0.conj().T)
        Nc = Vt[min_:, :].conj().T               # M×(M-min) 零空间列
        U_full = np.hstack([U0, Nc])
    else:
        U_full = U0                              # M×M

    # V_full：补全 Vh0 的行到 K×K 酉（前 min 行 = Vh0）
    if K > min_:
        _, _, Vt = np.linalg.svd(Vh0)
        Z = Vt[min_:, :].conj().T                # K×(K-min) 行空间正交补列
        V_full = np.vstack([Vh0, Z.conj().T])    # 前 min 行 = Vh0
    else:
        V_full = Vh0                             # K×K

    Sigma_full = np.zeros((M, K), dtype=complex)
    np.fill_diagonal(Sigma_full[:min_, :min_], S)
    return U_full, Sigma_full, V_full


def photonic_layer_forward(W, x, activation="relu", beta=1.0,
                           detection="real", n_bits=None,
                           vpi_real=None, calibrate=True,
                           vpi_cmd=VPI_L_V_CM):
    """光子计算层：W·x 经 SVD→双网格(+相位模型)→探测→激活，返回 (y, W_eff, meta)。

    - 任意维度 W 经 _square_embed 方阵嵌入（U_full·Σ_full·V_full），两片酉网格均施加相位模型；
    - 探测：'real'=取实部（相干探测常规约定）；'intensity'=|·|²；
    - 激活：photonic_activation；
    - meta 含各网格保真度与 W_eff（与 golden W 比对用）。
    """
    W = np.array(W, dtype=complex)
    x = np.array(x, dtype=complex)
    U_full, Sigma_full, V_full = _square_embed(W)
    U_e, _, _, fidU = mesh_transfer_with_model(
        U_full, n_bits=n_bits, vpi_real=vpi_real, calibrate=calibrate, vpi_cmd=vpi_cmd)
    V_e, _, _, fidV = mesh_transfer_with_model(
        V_full, n_bits=n_bits, vpi_real=vpi_real, calibrate=calibrate, vpi_cmd=vpi_cmd)
    W_eff = U_e @ Sigma_full @ V_e
    y_lin = W_eff @ x
    if detection == "real":
        y_det = np.real(y_lin)
    elif detection == "intensity":
        y_det = np.abs(y_lin) ** 2
    else:
        raise ValueError(f"未知探测 {detection}")
    y = np.array([photonic_activation(float(v), activation, beta) for v in y_det])
    meta = {
        "fidelity_U_mesh": fidU,
        "fidelity_V_mesh": fidV,
        "W_eff": W_eff,
    }
    return y, W_eff, meta


def make_toy_classifier(N0=4, N1=4, N2=2, seed=20260930):
    """构造一个在 R^N0 → {0,1} 上的小网络（权重确定性、可光学编译）。"""
    rng = np.random.default_rng(seed)
    W1 = (rng.standard_normal((N1, N0)) + 1j * rng.standard_normal((N1, N0))) / math.sqrt(2.0)
    W2 = (rng.standard_normal((N2, N1)) + 1j * rng.standard_normal((N2, N1))) / math.sqrt(2.0)
    X = rng.standard_normal((12, N0))
    return {"W1": W1, "W2": W2, "X": X}


def golden_classify(net, activation="relu", beta=1.0, detection="real"):
    """用 numpy 参考管线（与光学实现同构）计算每条样本的分类标签。"""
    X = net["X"]
    n = X.shape[0]
    labels = []
    for i in range(n):
        x = X[i]
        y1 = np.array([photonic_activation(float(v), activation, beta)
                       for v in np.real(net["W1"] @ x)])
        y2 = np.array([photonic_activation(float(v), activation, beta)
                       for v in np.real(net["W2"] @ y1)])
        labels.append(int(np.argmax(np.real(y2))))
    return labels


def end_to_end_inference(net, labels, activation="relu", beta=1.0,
                        detection="real", n_bits=None, vpi_real=None,
                        calibrate=True, vpi_cmd=VPI_L_V_CM):
    """端到端推理：两层网络对 net['X'] 分类，返回精度/误差与逐层保真。

    - full 精度（n_bits=None, vpi_real=None）下，光学实现须与 numpy 参考管线逐位一致
      （MAC 误差 ≈ 机器精度，分类精度 = 100%）；
    - 量化 / 标定误差 → MAC 误差上升 + 分类精度下降；标定闭环应回收精度。
    """
    X = net["X"]
    n = X.shape[0]
    correct = 0
    max_mac_err = 0.0
    fidUs, fidVs = [], []
    for i in range(n):
        x = X[i]
        y1, _, m1 = photonic_layer_forward(
            net["W1"], x, activation=activation, beta=beta, detection=detection,
            n_bits=n_bits, vpi_real=vpi_real, calibrate=calibrate, vpi_cmd=vpi_cmd)
        g1 = np.array([photonic_activation(float(v), activation, beta)
                       for v in np.real(net["W1"] @ x)])
        max_mac_err = max(max_mac_err, float(np.linalg.norm(y1 - g1)))
        fidUs.append(m1["fidelity_U_mesh"]); fidVs.append(m1["fidelity_V_mesh"])

        y2, _, m2 = photonic_layer_forward(
            net["W2"], y1, activation=activation, beta=beta, detection=detection,
            n_bits=n_bits, vpi_real=vpi_real, calibrate=calibrate, vpi_cmd=vpi_cmd)
        g2 = np.array([photonic_activation(float(v), activation, beta)
                       for v in np.real(net["W2"] @ y1)])
        max_mac_err = max(max_mac_err, float(np.linalg.norm(y2 - g2)))

        pred = int(np.argmax(np.real(y2)))
        if pred == labels[i]:
            correct += 1
    return {
        "accuracy": correct / n,
        "max_mac_err": max_mac_err,
        "fidelity_U_mean": float(np.mean(fidUs)),
        "fidelity_V_mean": float(np.mean(fidVs)),
    }


def verify_photonic_compute_m2(seed=20260930):
    """M2 端到端验证：量化扫描 + 标定闭环 + 端到端精度锚。返回结构化 dict。"""
    rng = np.random.default_rng(seed)
    # 随机酉（QR 正交化）
    Z = (rng.standard_normal((6, 6)) + 1j * rng.standard_normal((6, 6)))
    U, _ = np.linalg.qr(Z)

    # M2a 量化扫描
    q_sweep = []
    for nb in (1, 2, 4, 8, 12):
        _, _, _, fid = mesh_transfer_with_model(U, n_bits=nb)
        q_sweep.append({"n_bits": nb, "fidelity": fid})

    # M2b 标定闭环
    delta = 0.05
    vpi_real = VPI_L_V_CM * (1.0 + delta)
    _, _, _, fid_no = mesh_transfer_with_model(U, vpi_real=vpi_real, calibrate=False)
    _, _, _, fid_cal = mesh_transfer_with_model(U, vpi_real=vpi_real, calibrate=True)

    # M2c + 精度锚：端到端网络
    net = make_toy_classifier(seed=seed)
    labels = golden_classify(net, "relu", 1.0, "real")
    full = end_to_end_inference(net, labels, n_bits=None, vpi_real=None, calibrate=True)
    q2 = end_to_end_inference(net, labels, n_bits=2)
    noc = end_to_end_inference(net, labels, vpi_real=vpi_real, calibrate=False)
    cal = end_to_end_inference(net, labels, vpi_real=vpi_real, calibrate=True)

    return {
        "quantization_sweep": q_sweep,
        "calibration": {"delta_vpi": delta, "fid_no_cal": fid_no, "fid_cal": fid_cal},
        "e2e_full": full,
        "e2e_q2": q2,
        "e2e_vpi_no_cal": noc,
        "e2e_vpi_cal": cal,
    }


RED_LINE_DISCLOSURE_PC = {
    "capability_added": "本模块把 LDA 从『只能做酉矩阵乘』补到『能做任意（非酉）权重矩阵的"
                        "光学乘加』——SVD(W=U·Σ·V†) + 双 MZI 网格(U/V†) + 对角衰减(Σ)。",
    "sovereignty": "C 级自主（纯 numpy），不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径。",
    "physics_anchor": "MZI 网格耦合长度由 CMT（dc_cmt_solver B14 方法学独立候选）锚定；"
                      "相移器由 Vπ·L 物理定律（Soref-Bennett）给出；主权 GDS/DRC/LVS 复用 mesh_pnr。",
    "ideal_model": "M1 在**理想对角衰减**模型下验证；Σ 物理实现（VOA / 幅度均衡）由 "
                   "amplitude_equalization 框架覆盖，其 floor loss / 动态范围属 P2 PDK。",
    "loss_budget": "网格插入损耗由 mesh_loss_basis（每模口径）预算；未含相干实测标定 / "
                   "相位量化误差（M2）/ 电子驱动 co-sim（M3）。",
    "honest_boundary": "本模块演示『任意权重矩阵可由 SVD → 双 MZI 网格 + 对角衰减』实现，"
                       "理想模型下复现 numpy 数值；不声称已实现相干光学计算机或电子 co-sim。",
    # ---- M2 新增能力披露（性能爬坡：量化 / 标定 / 激活 / 精度锚）----
    "m2_quantization": "相位量化是相移器有限比特分辨率的物理模型（φ 量化到 2^n 电平）；"
                       "网格传递矩阵保真度随比特数上升，2bit 即出现可测退化。",
    "m2_calibration": "相位标定闭环基于 Vπ·L 物理定律（Soref-Bennett）：标称指令电压 → 真实器件相位；"
                      "用 π/2 探针反估真实 Vπ 补偿。模型自洽下可完全回收因 Vπ 增益误差造成的退化。",
    "m2_activation": "非线性激活在检测后（电子/光电域）实现（relu/sigmoid/tanh）。片上非线性光学元件"
                     "（可饱和吸收 / 相变材料阈值）物理属 B 类外部，非本模块 golden——不声称已建光学非线性求解器。",
    "m2_accuracy_anchor": "端到端精度锚：两层网络『光学 MVM→探测→激活』与 numpy 同构参考管线比对，"
                          "报告 MAC 误差与分类精度；full 精度须逐位一致（分类 100%），量化/标定误差致精度退化、"
                          "标定闭环回收。所有参考为闭式 / numpy 自洽，非自证桩。",
    "m2_honest_boundary": "量化 / 标定为**模型级**能力，非实测 PDK。真实器件的热串扰、Vπ 漂移、探针噪声、"
                          "片上非线性元件物理属 B 类外部（measurement / foundry T2 消费，非本模块求解）。",
}
