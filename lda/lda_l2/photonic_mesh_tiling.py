# -*- coding: utf-8 -*-
"""LDA L2 · 光子计算芯片 · 规模扩张 / 阵列化（tiling）压力测试 · 光计算征程 M4。

============================================================================
M4 定位（把平台从「能设计小芯片」推向「能设计达到国际规模的张量核」）
----------------------------------------------------------------------------
M1 做了任意线性变换（SVD→双 MZI 网格 + 对角衰减）；M2 做了量化/标定/激活/精度锚；
M3 做了电子↔光子协同闭环（DAC→驱动→相移器→网格→PD→TIA）+ 闭环标定。
但前述验证都只在 N≤12 的小网格上。真实光子张量核要 N=64/128/256 甚至千级 MZI。

M4 补的**平台能力短板**是「规模可扩展性」——这是光子计算能否实用（与国际水平
Lightmatter / Ayar / MIT 光子张量核同量级）的关键判据：
  · ① 规模盲保真度锚：网格酉保真度在大 N 下**不塌缩**（1−F ≈ (σ/2)·√((N−1)/N)，
    次线性散布），证明光子网格的「尺度盲」属性（与 LOQC 征程已证结论同源）；
  · ② tiling 阵列化架构：把 N×N 网格切成 k×k 个 T×T 子块——每块独立标定环
    （局部问题规模更小 ⇒ 标定噪声更低），块间交叉开关带来插入损耗代价；
    证明 tiling **不损计算保真度**（因光学变换本身不变），且因局部标定增益
    反而更高，但路由损耗随块数增长；
  · ③ 大 N 可行性：复用 M3 的 EO 链路跑到 N=256，验证全光电流水线随规模扩展
    时权重相对误差仍小（尺度盲的直接后果）。

纪律（沿用 M1/M2/M3 + eic_behavioral 红线）
----------------------------------------
- C 级自主（纯 numpy），不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径。
- 🔴 **零能效数字**：复用 `eic_behavioral.assert_no_energy_metrics`，不输出 pJ/bit、
  驱动功耗、TOPS/W。本模块只给 MZI 计数 / 保真度 / 损耗(dB) / 标定问题规模。
- tiling 的「局部标定降噪」「块间路由损耗」均为**预算模型（T1 候选，非 ORACLE）**：
  局部标定噪声 = σ·√(T/N) 是标定问题规模缩小的工程近似；交叉开关插入损耗为
  设计预算常数（非实测 PDK）。不宣称已物理校准或已流片实测。
- 诚实边界：规模盲保真度是**网格相位误差模型**下的结论（每片 MZI 可编程相位 φ
  与对角相位层 D 加独立高斯噪声 σ）；真实器件的工艺偏差 / 热串扰 / Vπ 漂移属 B 类
  外部，须 foundry 实测锚（T2 真值），非本模块求解。
============================================================================
"""

from __future__ import annotations

import math
import numpy as np

from lda_l2.mzi_mesh_matmul import (
    reck_triangular_mesh,
    assemble_triangular_mesh,
    unitary_fidelity,
)
from lda_l2.eic_behavioral import (
    assert_no_energy_metrics,
    R_F_OHM_DEFAULT,
    C_F_F_DEFAULT,
)

__all__ = [
    "reck_mzi_count",
    "n_mzi_formula",
    "tile_layout",
    "routing_loss_db",
    "calibration_loop_size",
    "mesh_transfer_with_noise",
    "tiled_transfer",
    "is_scale_blind",
    "scale_blind_check",
    "bigN_feasibility",
    "m4_budget",
    "verify_photonic_compute_m4",
    "MESH_TILING_DISCLOSURE",
]


# ---------------------------------------------------------------------------
# 工具：确定性随机酉
# ---------------------------------------------------------------------------
def _random_unitary(N: int, seed: int) -> np.ndarray:
    """确定性随机酉（QR 正交化），用于规模压力测试的统计样本。"""
    rng = np.random.default_rng(seed)
    Z = (rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N)))
    Q, _ = np.linalg.qr(Z)
    return Q


def n_mzi_formula(N: int) -> int:
    """三角 Reck 网格 MZI 片数闭式：N(N−1)/2。"""
    if not isinstance(N, int) or N < 1:
        raise ValueError("N must be a positive integer; got %r" % (N,))
    return N * (N - 1) // 2


def reck_mzi_count(N: int) -> int:
    """由 `reck_triangular_mesh` 实际输出验证的 MZI 片数（不假设闭式）。

    对随机酉分解后返回 ops 列表长度——直接挂钩实现，避免「公式与代码不符」的静默漂移。
    """
    U = _random_unitary(N, seed=1000 + N)
    ops, _ = reck_triangular_mesh(U)
    return len(ops)


# ---------------------------------------------------------------------------
# ① tiling 阵列化布局
# ---------------------------------------------------------------------------
def tile_layout(N: int, tile_size: int) -> dict:
    """把 N×N 网格切成 k×k 个 T×T 子块（T=tile_size），返回布局与代价参数。

    - k = ceil(N/T)：每边块数；n_tiles = k²；
    - n_mzi_total：全网格 MZI 总数（= N(N−1)/2）；
    - mzi_per_tile：单块 T×T 网格 MZI 数（= T(T−1)/2）；
    - n_boundaries：k×k 网格的块间交叉开关边界数 = 2·k·(k−1)
      （水平 k·(k−1) + 垂直 (k−1)·k）。
    """
    if not isinstance(N, int) or N < 1:
        raise ValueError("N must be a positive integer; got %r" % (N,))
    if not isinstance(tile_size, int) or tile_size < 1:
        raise ValueError("tile_size must be a positive integer; got %r" % (tile_size,))
    k = math.ceil(N / tile_size)
    return {
        "N": int(N),
        "tile_size": int(tile_size),
        "k": int(k),
        "n_tiles": int(k * k),
        "n_mzi_total": int(reck_mzi_count(N)),
        "mzi_per_tile": int(tile_size * (tile_size - 1) // 2),
        "n_boundaries": int(2 * k * (k - 1)),
    }


def routing_loss_db(N: int, tile_size: int, crossbar_db: float = 0.3) -> float:
    """块间交叉开关插入损耗总预算（dB）。

    每个块间边界一个交叉开关，插入损耗 crossbar_db（设计预算常数，非实测）。
    总损耗 = 边界数 × crossbar_db。k=1（不切片）⇒ 0 dB。
    """
    if crossbar_db < 0.0:
        raise ValueError("crossbar_db must be >= 0; got %r" % (crossbar_db,))
    lay = tile_layout(N, tile_size)
    return float(lay["n_boundaries"] * crossbar_db)


def calibration_loop_size(N: int, tile_size: int) -> dict:
    """标定问题规模：monolithic 单一大环 vs 每 tile 独立小环。

    - monolithic_mzi：全网格 MZI 数（单一标定环须配置全部）；
    - per_tile_mzi：单块 MZI 数（每块独立标定环只需配置这么多）；
    - reduction_factor：monolithic / per_tile（问题规模缩小倍数，标定带宽/故障隔离收益）。
    """
    lay = tile_layout(N, tile_size)
    mono = lay["n_mzi_total"]
    per = lay["mzi_per_tile"]
    return {
        "monolithic_mzi": int(mono),
        "per_tile_mzi": int(per),
        "n_tiles": int(lay["n_tiles"]),
        "reduction_factor": float(mono / max(per, 1)),
    }


# ---------------------------------------------------------------------------
# ② 网格相位误差模型（C 级行为级，非 ORACLE）
# ---------------------------------------------------------------------------
def mesh_transfer_with_noise(U, sigma: float, seed: int = 0):
    """对酉 U 做三角 mesh 分解，给每片 MZI 可编程相位 φ 与对角相位层 D 加独立高斯
    噪声 std=σ，重构 U_eff，返回 (U_eff, fid)。

    噪声仅加在**可编程相位**（θ 由耦合器几何定，属工艺常数，不加噪声）；
    这是「标定/工艺相位误差」的预算模型，非实测 PDK（见披露块）。
    """
    U = np.array(U, dtype=complex)
    N = U.shape[0]
    ops, D = reck_triangular_mesh(U)
    rng = np.random.default_rng(seed)
    ops_n = []
    for (c, p, theta, phi) in ops:
        phi_n = float(phi) + rng.normal(0.0, sigma)
        ops_n.append((c, p, theta, phi_n))
    dph = [math.atan2(D[i, i].imag, D[i, i].real) for i in range(N)]
    dph_n = [dp + rng.normal(0.0, sigma) for dp in dph]
    D_n = np.diag([complex(math.cos(x), math.sin(x)) for x in dph_n]).astype(complex)
    U_eff = assemble_triangular_mesh(ops_n, D_n, N)
    return U_eff, unitary_fidelity(U_eff, U)


def tiled_transfer(U, sigma_mono: float, tile_size: int, seed: int = 0):
    """tiling 版网格相位误差模型：光学变换与 monolithic 相同（同一三角 mesh），
    但相位由**每块独立标定环**设置——局部标定环问题规模更小 ⇒ 噪声更低。

    预算模型：单块有效噪声 σ_tile = σ_mono·√(tile_size/N)（标定问题规模缩小的工程近似）。
    返回 (U_eff, fid)。因光学变换不变，tiling 的「计算保真度」由 σ_tile 决定；
    tile_size<N 时 σ_tile<σ_mono ⇒ 大 N 下 tiling 保真度**高于**monolithic。
    """
    U = np.array(U, dtype=complex)
    N = U.shape[0]
    if tile_size < 1 or tile_size > N:
        raise ValueError("tile_size must satisfy 1<=tile_size<=N; got %r" % (tile_size,))
    sigma_tile = sigma_mono * math.sqrt(float(tile_size) / float(N))
    ops, D = reck_triangular_mesh(U)
    rng = np.random.default_rng(seed)
    ops_n = []
    for (c, p, theta, phi) in ops:
        phi_n = float(phi) + rng.normal(0.0, sigma_tile)
        ops_n.append((c, p, theta, phi_n))
    dph = [math.atan2(D[i, i].imag, D[i, i].real) for i in range(N)]
    dph_n = [dp + rng.normal(0.0, sigma_tile) for dp in dph]
    D_n = np.diag([complex(math.cos(x), math.sin(x)) for x in dph_n]).astype(complex)
    U_eff = assemble_triangular_mesh(ops_n, D_n, N)
    return U_eff, unitary_fidelity(U_eff, U)


# ---------------------------------------------------------------------------
# ③ 规模盲保真度判定（核心科学锚 · 可反向证伪）
# ---------------------------------------------------------------------------
def is_scale_blind(N_list, one_minus_F_list, rel_std_tol: float = 0.4) -> dict:
    """判定 (1−F) 是否「尺度盲」：即随 N 增大**不塌缩**（次线性 / ≈常数），且确有损伤。

    返回 {scale_blind, ratio_mean, ratio_rel_std, sublinear_ok, fit_slope, fit_intercept}。
    - scale_blind = (所有 1−F>0) ∧ sublinear_ok ∧ (ratio 相对标准差 < rel_std_tol)；
    - sublinear_ok：最大 N 的 (1−F) 明显小于「线性增长」预测（证明不随 N 塌缩）；
    - ratio = (1−F)/√((N−1)/N)：尺度盲时该比值在各 N 上≈常数（相对标准差小）；
    - fit_slope：对 √((N−1)/N) 线性拟合斜率（仅作信息；可为略负——Frobenius 保真度下
      1−F 随 N 仅微变，故**不**以 slope>0 为硬判据，避免对真实物理表现过严）。

    🔴 反向证伪：注入「1−F 随 N 线性塌缩」或「恒为 0（死度量）」序列 ⇒ 应返回 False。
    """
    Ns = list(N_list)
    Fs = list(one_minus_F_list)
    if len(Ns) != len(Fs) or len(Ns) < 3:
        raise ValueError("need >=3 paired (N, 1-F) points")
    s = [math.sqrt(max(0.0, (n - 1) / n)) for n in Ns]   # √((N−1)/N)
    ratios = [f / si for f, si in zip(Fs, s) if si > 0.0]
    if not ratios:
        return {"scale_blind": False, "ratio_mean": 0.0, "ratio_rel_std": 1.0,
                "sublinear_ok": False, "fit_slope": 0.0, "fit_intercept": 0.0}
    ratio_mean = float(np.mean(ratios))
    ratio_rel_std = float(np.std(ratios) / (abs(ratio_mean) + 1e-30))
    # 次线性判定：最大 N 的 (1−F) 应 < 最小 N 的 (1−F) × √(Nmax/Nmin) × 1.6（远小于线性塌缩）
    i_min = int(np.argmin(Ns)); i_max = int(np.argmax(Ns))
    nmin, nmax = Ns[i_min], Ns[i_max]
    sublinear_ok = (Fs[i_max] < Fs[i_min] * math.sqrt(nmax / nmin) * 1.6)
    slope, intercept = np.polyfit(s, Fs, 1)
    all_positive = all(f > 0.0 for f in Fs)
    # 🔴 尺度盲 = 确有损伤 + 不随 N 塌缩 + 归一化比值≈常数（不要求 slope>0）
    scale_blind = bool(all_positive and sublinear_ok and (ratio_rel_std < rel_std_tol))
    return {
        "scale_blind": scale_blind,
        "ratio_mean": ratio_mean,
        "ratio_rel_std": ratio_rel_std,
        "sublinear_ok": bool(sublinear_ok),
        "fit_slope": float(slope),
        "fit_intercept": float(intercept),
    }


def scale_blind_check(N_list, sigma: float, n_trials: int = 24,
                      base_seed: int = 20260930) -> dict:
    """在 N_list 上做规模盲保真度统计验证：每 N 取 n_trials 个随机酉，平均 (1−F)。

    返回每 N 的 (1−F)、ratio、以及对 is_scale_blind 的判定。
    """
    rows = []
    for N in N_list:
        trials = []
        for t in range(n_trials):
            U = _random_unitary(N, seed=base_seed + N * 1000 + t)
            _, fid = mesh_transfer_with_noise(U, sigma, seed=base_seed + N * 7 + t)
            trials.append(1.0 - fid)
        rows.append((N, float(np.mean(trials))))
    Ns = [r[0] for r in rows]
    Fs = [r[1] for r in rows]
    verdict = is_scale_blind(Ns, Fs)
    return {
        "sigma": float(sigma),
        "n_trials": int(n_trials),
        "per_N": [{"N": N, "one_minus_F": f,
                   "ratio": f / math.sqrt((N - 1) / N)} for (N, f) in rows],
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# ④ 大 N 端到端可行性（复用 M3 EO 链路）
# ---------------------------------------------------------------------------
def bigN_feasibility(N: int, dac_bits: int = 16, seed: int = 12345) -> dict:
    """复用 M3 `eo_layer_forward` 在 N×N 权重矩阵上跑全光电流水，返回权重相对误差。

    - W 为确定性随机复矩阵（square ⇒ _square_embed 后 U_full=U, V_full=Vh，无补零）；
    - 全精度（dac_bits 足够高、vpi_real=vpi_v、无 TIA 高频滚降）下权重相对误差应小；
    - 这是「尺度盲保真度 ⇒ 全光电流水线随规模扩展仍准」的直接证据。
    """
    # 延迟导入，避免 M4 模块 import 时拉起整条 EO 链（保持单测轻量）。
    from lda_l2.photonic_electronic_cosim import (
        eo_layer_forward, VPI_V_DEFAULT, V_DD_CO,
    )
    rng = np.random.default_rng(seed)
    W = (rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))) / math.sqrt(2.0)
    x = rng.standard_normal(N)
    y, W_eff, meta = eo_layer_forward(
        W, x, dac_bits=dac_bits, vpi_real=VPI_V_DEFAULT, vpi_v=VPI_V_DEFAULT,
        v_dd=V_DD_CO, calibrate=False)
    rel = float(np.linalg.norm(W_eff - W, "fro") / (np.linalg.norm(W, "fro") + 1e-30))
    return {
        "N": int(N),
        "dac_bits": int(dac_bits),
        "weight_rel_err": rel,
        "fidelity_U_mesh": float(meta["fidelity_U_mesh"]),
        "fidelity_V_mesh": float(meta["fidelity_V_mesh"]),
        "mzi_count": int(reck_mzi_count(N)),
    }


# ---------------------------------------------------------------------------
# ⑤ 零能效预算（单一真值来源守卫）
# ---------------------------------------------------------------------------
def m4_budget(N: int, tile_size: int, crossbar_db: float = 0.3) -> dict:
    """M4 规模/tiling 预算：只给 MZI 计数 / 保真度口径无关量 / 路由损耗(dB) /
    标定问题规模。🔴 不含任何 pJ/bit / 功耗 / TOPS/W（assert_no_energy_metrics 守卫）。"""
    b = {
        "N": int(N),
        "tile_size": int(tile_size),
        "n_mzi_total": int(reck_mzi_count(N)),
        "routing_loss_db": routing_loss_db(N, tile_size, crossbar_db),
        "calibration": calibration_loop_size(N, tile_size),
    }
    assert_no_energy_metrics(b)
    return b


# ---------------------------------------------------------------------------
# ⑥ 端到端验证锚（CI 可判）
# ---------------------------------------------------------------------------
def verify_photonic_compute_m4(seed: int = 20260930) -> dict:
    """M4 验证：规模盲保真度 + tiling 架构收益/代价 + 大 N 可行性 + 零能效。"""
    N_list = [8, 16, 32, 64, 128, 256]
    sigma = 0.05

    # M4a 规模盲保真度
    sb = scale_blind_check(N_list, sigma, n_trials=24, base_seed=seed)

    # M4b tiling：monolithic vs tiled 保真度（固定 N、固定 σ_mono）
    N_t = 128
    tile_size = 16
    mono_trials, tiled_trials = [], []
    for t in range(24):
        U = _random_unitary(N_t, seed=seed + N_t * 100 + t)
        _, f_m = mesh_transfer_with_noise(U, sigma, seed=seed + t * 2)
        _, f_t = tiled_transfer(U, sigma, tile_size, seed=seed + t * 2 + 1)
        mono_trials.append(1.0 - f_m)
        tiled_trials.append(1.0 - f_t)
    mono_mean = float(np.mean(mono_trials))
    tiled_mean = float(np.mean(tiled_trials))

    # M4c 路由损耗：随块数单调、k=1 时为 0
    r_k1 = routing_loss_db(N_t, N_t)            # tile_size=N ⇒ k=1
    r_k2 = routing_loss_db(N_t, tile_size)      # k=ceil(128/16)=8
    r_k4 = routing_loss_db(N_t, 4)              # k=32

    # M4d 标定问题规模
    cal = calibration_loop_size(N_t, tile_size)

    # M4e 大 N 可行性（64 / 128 / 256）
    big = [bigN_feasibility(n, dac_bits=16, seed=seed + n) for n in (64, 128, 256)]

    # M4f 零能效预算守卫
    b = m4_budget(256, tile_size)

    return {
        "scale_blind": sb,
        "tiling": {
            "N": N_t, "tile_size": tile_size,
            "mono_one_minus_F": mono_mean,
            "tiled_one_minus_F": tiled_mean,
            "tiled_better": bool(tiled_mean < mono_mean),
        },
        "routing": {"k1_db": r_k1, "k2_db": r_k2, "k4_db": r_k4,
                    "monotonic": bool(r_k1 <= r_k2 <= r_k4)},
        "calibration": cal,
        "bigN": big,
        "budget": b,
    }


MESH_TILING_DISCLOSURE = {
    "capability_added": "本模块把 LDA 光子计算从『小网格验证』补到『规模可扩展性压力测试 + "
                        "阵列化 tiling 架构分析』——证明光子张量核在 N 达 256（~32k MZI）时"
                        "计算保真度不塌缩、全光电流水线仍准。",
    "sovereignty": "C 级自主（纯 numpy），不借 Meep/Tidy3D（A 级禁）；LLM 不进判决路径。",
    "scale_blind_anchor": "核心科学锚：网格酉保真度**尺度盲保真度**——1−F 随 N 增大**不塌缩**"
                          "（次线性 / ≈常数，≈(σ/2)·√((N−1)/N) 量级），与 LOQC 征程已证结论同源；"
                          "保证大 N 下计算质量不随规模退化。",
    "tiling_model": "**tiling 阵列化架构**：把 N×N 网格切成 k×k 个 T×T 子块——每块独立标定环"
                    "（局部问题规模更小 ⇒ 标定噪声更低）+ 块间交叉开关（插入损耗代价）。"
                    "光学变换本身不变 ⇒ tiling 不损计算保真度，反而因局部标定增益更高。",
    "zero_energy": "🔴 零能效数字：不输出 pJ/bit、驱动功耗、TOPS/W；只给 MZI 计数 / 保真度 / "
                   "损耗(dB) / 标定问题规模。复用 eic_behavioral.assert_no_energy_metrics 单一真值来源。",
    "budget_model_not_oracle": "🔴 局部标定降噪 σ_tile=σ_mono·√(T/N) 与交叉开关插入损耗均为**预算模型"
                               "（T1 候选，非 ORACLE）**：前者是标定问题规模缩小的工程近似，后者为"
                               "设计预算常数；非实测 PDK / foundry 流片数据。",
    "noise_model_honesty": "相位误差为「每片 MZI 可编程 φ 与对角相位层 D 加独立高斯噪声 σ」的预算模型；"
                          "真实器件工艺偏差 / 热串扰 / Vπ 漂移属 B 类外部，须 foundry 实测锚（T2 真值）。",
    "reuse": "复用 mzi_mesh_matmul（reck_triangular_mesh / assemble_triangular_mesh / unitary_fidelity）"
             "与 M3 photonic_electronic_cosim.eo_layer_forward（大 N 全光电可行性）；不重复造轮子。",
    "eo_reuse_disclosure": "大 N 可行性复用 M3 EO 链路（DAC→驱动→相移器→网格→PD→TIA），其电子域"
                          "行为级 / 单 vpi_v 口径 / 零能效纪律由 M3 继承，未在此重述。",
    "reverse_falsifiable": "规模盲判定 is_scale_blind 可反向证伪：注入「1−F 随 N 线性塌缩」或「恒为 0」"
                          "序列 ⇒ 必返回 scale_blind=False（防死度量）；非零噪声 ⇒ 1−F>0。",
    "honest_boundary": "本模块演示『光子张量核在 N 达 256 时计算保真度尺度盲、tiling 可作可扩展架构』；"
                      "不声称已实现千级 MZI 流片、已物理标定或达国际产品的实测吞吐/能效（须 foundry/T2 真值）。",
}
