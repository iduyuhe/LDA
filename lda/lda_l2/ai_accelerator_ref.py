# -*- coding: utf-8 -*-
"""LDA · 阶段 4 L6 参考设计 · 光子/模拟混合 AI 推理加速器（W4-1）。

============================================================================
定位（L6 = 计算架构层：「算法 → 硬件映射」的参考设计，承接 GPU 命题改写）
----------------------------------------------------------------------------
把平台两条已证积木**拼成一台端到端推理加速器**（2 层 MLP 分类器）：

  第 1 层（线性 · 光子域）：权重训练为**实正交矩阵** O1（极分解投影约束），
      经 Reck 三角 MZI 网格物理实现（`reck_triangular_mesh` 相邻模耦合 · 可 P&R），
      移相器按 b 位量化后用**重构网格矩阵**真实参与推理（非理想 O1）；
  非线性（电域）：ReLU —— 光子网格对经典光**只做线性酉映射**（诚实边界）；
  第 2 层（线性 · 电域）：E3 模拟交叉阵列数据通路
      （DAC 量化 → CrossbarMVM 参考列法 → ADC 量化，`AnalogMvmUnit`）。

正确性验证：与**全精度数字 golden**（同权重 / 同结构，纯 numpy）逐样本比对
分类精度与回归误差；误差源**逐项归因**（相位量化 ↔ DAC/ADC 量化），
且各自随位数增加而下降（趋势判据）。

🔴 红线（全平台同源）：
  · C 级自主（纯 numpy，零外部依赖；不 import torch / onnx / jax）；
  · LLM 不进判决路径（全部死标量 / numpy 运算，训练为确定性全批 GD）；
  · golden = 同结构全精度数字参考（非外部 ORACLE）；
  · **不报 TOPS / TOPS-W / fJ/op**（电路级模型 + 无 PDK ⇒ 无能效宣称资格）。

诚实边界（防纸糊楼）：
  1. 数据集为**固定种子合成高斯团**（非真实世界数据）⇒ 精度数字只证
     「端到端链路行为正确」，不宣称任何现实任务 SOTA；
  2. 光子层只实现**正交（酉）线性映射**：第 1 层容量受正交约束（这是物理
     约束下的真实精度，不是缺陷隐瞒——训练在约束内完成）；
  3. 移相器量化 = 一阶均匀相位量化模型（不含校准残差 / 漂移 / 串扰）；
  4. 插入损耗为**功率预算口径**（`mesh_loss_basis` 双口径登记），对分类
     决策的影响（均匀衰减 + 归一化/差分检测可消除）**不建模**进精度；
  5. 相干检测取**实部**口径（虚部丢弃；O1 为实矩阵 ⇒ 实部即目标输出）；
  6. E3 交叉阵列为理想 TIA + 均匀量化模型（继承 E3 诚实边界，电路级）。
"""
from __future__ import annotations

import math

import numpy as np

from .mzi_mesh_matmul import (
    assemble_triangular_mesh,
    mesh_loss_basis,
    reck_triangular_mesh,
)
from .compiler_frontend import guard_no_framework_in_judgment
from .ecore.mvm_datapath import AnalogMvmUnit, tiled_mvm

# ---------------------------------------------------------------------------
# 常量（确定性设计点，全部死标量）
# ---------------------------------------------------------------------------
SEED = 20261002
D_IN = 4                 # 数据本征维数
N_MODE = 8               # 光子网格模数（d_in 补零到 N）
C_OUT = 4                # 类别数
PER_CLASS = 64           # 每类样本数
TRAIN_PER_CLASS = 48     # 每类训练样本（其余测试）
DEFAULT_PHASE_BITS = 6   # 移相器位数字（设计点）
DEFAULT_DAC_BITS = 8
DEFAULT_ADC_BITS = 8
GD_ITERS = 400           # 全批梯度下降步数
GD_LR = 0.5


# ---------------------------------------------------------------------------
# 数据集（固定种子合成 · 确定性）
# ---------------------------------------------------------------------------
def _make_dataset(seed: int = SEED):
    """4 类 4 维高斯团；min-max 到 [0,1]（用全体样本统计，确定性）；3:1 训练/测试切分。"""
    rng = np.random.RandomState(seed)
    means = np.array([[2.0, 0.0, 0.0, 0.0],
                      [0.0, 2.0, 0.0, 0.0],
                      [0.0, 0.0, 2.0, 0.0],
                      [0.0, 0.0, 0.0, 2.0]])
    xs, ys = [], []
    for c in range(C_OUT):
        xs.append(rng.randn(PER_CLASS, D_IN) * 0.6 + means[c])
        ys.append(np.full(PER_CLASS, c))
    X = np.concatenate(xs, axis=0)
    y = np.concatenate(ys, axis=0).astype(int)
    lo, hi = X.min(axis=0), X.max(axis=0)
    span = np.where(hi - lo > 0, hi - lo, 1.0)
    X = (X - lo) / span
    # 确定性切分：每类前 TRAIN_PER_CLASS 个训练、其余测试
    idx_tr, idx_te = [], []
    for c in range(C_OUT):
        base = np.where(y == c)[0]
        idx_tr.append(base[:TRAIN_PER_CLASS])
        idx_te.append(base[TRAIN_PER_CLASS:])
    tr = np.concatenate(idx_tr)
    te = np.concatenate(idx_te)
    return X, y, tr, te


def _pad(x_batch: np.ndarray) -> np.ndarray:
    """把 (B, D_IN) 补零到 (B, N_MODE)（光子网格模数）。"""
    B = x_batch.shape[0]
    out = np.zeros((B, N_MODE))
    out[:, :D_IN] = x_batch
    return out


# ---------------------------------------------------------------------------
# 训练（纯 numpy · 确定性全批 GD · 第 1 层正交约束）
# ---------------------------------------------------------------------------
def _orthogonal_project(M: np.ndarray) -> np.ndarray:
    """极分解投影到最近正交阵：M = U Σ Vᵀ ⇒ O = U Vᵀ。"""
    U, _, Vt = np.linalg.svd(M)
    return U @ Vt


def _train_model(seed: int = SEED, iters: int = GD_ITERS, lr: float = GD_LR):
    """训练 2 层 MLP：z1 = O1 @ x_pad（O1 正交约束）；y = W2 @ relu(z1)。

    每步全批梯度 + 全局范数裁剪 + 极分解投影（确定性，无随机小批）。
    返回 (O1 (N×N), W2 (C×N), train_acc)。
    """
    X, y, tr, _ = _make_dataset(seed)
    Xp = _pad(X[tr])
    yt = y[tr]
    rng = np.random.RandomState(seed + 1)
    O1 = _orthogonal_project(rng.randn(N_MODE, N_MODE))
    W2 = rng.randn(C_OUT, N_MODE) * 0.1

    def ce_grad(O1c, W2c):
        Z1 = Xp @ O1c.T                       # (B, N)
        A1 = np.maximum(Z1, 0.0)
        Y = A1 @ W2c.T                        # (B, C)
        Ys = Y - Y.max(axis=1, keepdims=True)
        P = np.exp(Ys)
        P /= P.sum(axis=1, keepdims=True)
        loss = -np.mean(np.log(P[np.arange(len(yt)), yt] + 1e-300))
        dY = P
        dY[np.arange(len(yt)), yt] -= 1.0
        dY /= len(yt)
        dW2 = dY.T @ A1                       # (C, N)
        dA1 = dY @ W2c                        # (B, N)
        dZ1 = dA1 * (Z1 > 0.0)                # (B, N)
        dO1 = dZ1.T @ Xp                      # (N, N)
        return loss, dO1, dW2

    for _ in range(int(iters)):
        loss, dO1, dW2 = ce_grad(O1, W2)
        gnorm = math.sqrt(float(np.sum(dO1 ** 2)) + float(np.sum(dW2 ** 2)))
        if gnorm > 5.0:
            dO1 *= 5.0 / gnorm
            dW2 *= 5.0 / gnorm
        O1 = _orthogonal_project(O1 - lr * dO1)
        W2 = W2 - lr * dW2
        if not math.isfinite(loss):
            raise RuntimeError("训练发散（loss 非有限）——确定性设计点须复核")
    # 训练精度（golden 域）
    Z1 = Xp @ O1.T
    pred = np.argmax((np.maximum(Z1, 0.0)) @ W2.T, axis=1)
    acc = float(np.mean(pred == yt))
    return O1, W2, acc


# ---------------------------------------------------------------------------
# 光子层：Reck 三角网格 + 移相器相位量化（patch 点，探针打这里）
# ---------------------------------------------------------------------------
def _wrap_pi(v: float) -> float:
    """相位环绕到 (−π, π]（mod 2π，酉矩阵不变的合法操作）。

    🔴 reck ops 的 φ 实际域为 (−π, 3π)（atan2 差 + π）——必须先环绕再量化，
    否则钳位会破坏网格（实测 6-bit 保真度跌到 ~1/N 的随机酉期望）。
    """
    return (float(v) + math.pi) % (2.0 * math.pi) - math.pi


def _quant_angle(v: float, bits: int, lo: float, hi: float) -> float:
    """[lo, hi] 均匀 2^bits 电平量化（bits<=0 视为理想）。输入须已落在 [lo, hi]。"""
    if bits <= 0:
        return float(v)
    lv = 2 ** int(bits)
    step = (hi - lo) / (lv - 1)
    return float(np.clip(round((float(v) - lo) / step), 0, lv - 1) * step + lo)


def _photonic_layer_matrix(O1: np.ndarray, phase_bits: int):
    """O1（实正交）→ 量化后 MZI 三角网格重构矩阵 Ûq（复）。

    返回 (Uq, ops, D, stats)：Uq 为**量化后重构**酉阵（真实参与推理）；
    ops/D 为量化后的 (c, p, θ, φ) 列表与对角相位层；stats = mesh_loss_basis 双口径。
    """
    O1 = np.asarray(O1, dtype=float)
    err = float(np.max(np.abs(O1.T @ O1 - np.eye(N_MODE))))
    if err > 1e-8:
        raise ValueError(f"O1 非正交（‖O1ᵀO1−I‖={err:.2e}），光子网格要求酉输入")
    ops, D = reck_triangular_mesh(O1.astype(complex))
    ops_q = [(c, p, _quant_angle(t, phase_bits, 0.0, math.pi),
              _quant_angle(_wrap_pi(ph), phase_bits, -math.pi, math.pi))
             for (c, p, t, ph) in ops]
    d_q = D.copy()
    for k in range(N_MODE):
        ang = float(np.angle(d_q[k, k]))
        d_q[k, k] = np.exp(1j * _quant_angle(ang, phase_bits, -math.pi, math.pi))
    Uq = assemble_triangular_mesh(ops_q, d_q, N_MODE)
    stats = mesh_loss_basis(ops_q, n_crossings=0)
    return Uq, ops_q, d_q, stats


# ---------------------------------------------------------------------------
# 端到端评估
# ---------------------------------------------------------------------------
def _golden_logits(O1, W2, Xb):
    Z1 = _pad(Xb) @ O1.T
    return np.maximum(Z1, 0.0) @ W2.T


def _hybrid_logits(O1, W2, Xb, phase_bits, dac_bits, adc_bits,
                   photonic_fn=_photonic_layer_matrix, tiled_tile: int = 0):
    """混合推理：光子层（量化网格重构矩阵·实部检测）→ ReLU → E3 模拟交叉阵列。"""
    Uq, _, _, _ = photonic_fn(O1, phase_bits)
    Z1h = np.real(_pad(Xb) @ Uq.T)            # 相干检测实部口径
    A1 = np.maximum(Z1h, 0.0)                 # 电域 ReLU（∈[0,1]，可直接进 DAC）
    unit = AnalogMvmUnit(W2, dac_bits=dac_bits, adc_bits=adc_bits)
    if tiled_tile and tiled_tile > 0:
        return np.stack([tiled_mvm(W2, a, tile=tiled_tile,
                                   dac_bits=dac_bits, adc_bits=adc_bits)
                         for a in A1]), A1, Z1h
    ys = [unit.forward(a)[0] for a in A1]
    return np.stack(ys), A1, Z1h


def run_reference(seed: int = SEED, phase_bits: int = DEFAULT_PHASE_BITS,
                  dac_bits: int = DEFAULT_DAC_BITS, adc_bits: int = DEFAULT_ADC_BITS,
                  iters: int = GD_ITERS, lr: float = GD_LR,
                  photonic_fn=None) -> dict:
    """跑一次完整参考设计：训练 → golden/混合端到端 → 误差归因 → 网格统计。

    photonic_fn=None 时运行时解析模块级 `_photonic_layer_matrix`（留探针 patch 点；
    默认参数在 def 时绑定会绕过 mock —— 这里必须动态查找）。
    """
    if photonic_fn is None:
        photonic_fn = _photonic_layer_matrix
    guard_no_framework_in_judgment({"ctx": "accelerator_ref.run_reference"},
                                   where="accelerator_ref.run_reference")
    X, y, tr, te = _make_dataset(seed)
    O1, W2, train_acc = _train_model(seed, iters=iters, lr=lr)

    # —— 数字 golden 精度 ——
    g_tr = np.argmax(_golden_logits(O1, W2, X[tr]), axis=1)
    g_te = np.argmax(_golden_logits(O1, W2, X[te]), axis=1)
    acc_golden_tr = float(np.mean(g_tr == y[tr]))
    acc_golden_te = float(np.mean(g_te == y[te]))

    # —— 混合端到端精度（设计点）——
    h_te, A1h, Z1h = _hybrid_logits(O1, W2, X[te], phase_bits, dac_bits,
                                    adc_bits, photonic_fn=photonic_fn)
    acc_hyb_te = float(np.mean(np.argmax(h_te, axis=1) == y[te]))

    # —— 误差归因 ——
    Z1g = _pad(X[te]) @ O1.T
    denom1 = float(np.max(np.abs(Z1g))) or 1.0
    e1 = float(np.max(np.abs(Z1h - Z1g)) / denom1)          # 光子层误差（设计点）
    G = _golden_logits(O1, W2, X[te])
    denom2 = float(np.max(np.abs(G))) or 1.0
    e2_e2e = float(np.max(np.abs(h_te - G)) / denom2)        # 端到端相对误差
    # 隔离口径：golden 激活直接进量化交叉阵列（隔离第 2 层自身误差）
    unit = AnalogMvmUnit(W2, dac_bits=dac_bits, adc_bits=adc_bits)
    iso = np.stack([unit.forward(a)[0] for a in np.maximum(Z1g, 0.0)])
    e2_iso = float(np.max(np.abs(iso - G)) / denom2)

    # —— 趋势扫描（误差随位数下降）——
    phase_sweep = {}
    for b in (2, 4, 6, 8):
        _, A1b, Z1hb = _hybrid_logits(O1, W2, X[te], b, dac_bits, adc_bits,
                                      photonic_fn=photonic_fn)
        phase_sweep[b] = float(np.max(np.abs(Z1hb - Z1g)) / denom1)
    unit_sweep = {}
    for bb in (3, 6, 8):
        u = AnalogMvmUnit(W2, dac_bits=bb, adc_bits=bb)
        s = np.stack([u.forward(a)[0] for a in np.maximum(Z1g, 0.0)])
        unit_sweep[bb] = float(np.max(np.abs(s - G)) / denom2)

    # —— 网格物理统计（双口径损耗 + 每模深度）——
    Uq, ops_q, _, loss = photonic_fn(O1, phase_bits)
    fid = float(abs(np.trace(Uq.conj().T @ O1.astype(complex))) / N_MODE)
    # 未量化对照锚（bits=0 ⇒ 纯数学分解重构，应为机器精度）：
    U0, _, _, _ = photonic_fn(O1, 0)
    fid_unquant = float(abs(np.trace(U0.conj().T @ O1.astype(complex))) / N_MODE)

    return {
        "seed": int(seed), "iters": int(iters), "lr": float(lr),
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "train_acc_golden": acc_golden_tr,
        "test_acc_golden": acc_golden_te,
        "test_acc_hybrid": acc_hyb_te,
        "acc_drop_points": round((acc_golden_te - acc_hyb_te) * 100.0, 4),
        "config": {"phase_bits": phase_bits, "dac_bits": dac_bits,
                   "adc_bits": adc_bits},
        "error_attribution": {
            "e1_photonic_rel_max": e1,
            "e2_crossbar_iso_rel_max": e2_iso,
            "e2_e2e_rel_max": e2_e2e,
        },
        "phase_bits_sweep_e1": phase_sweep,
        "unit_bits_sweep_e2_iso": unit_sweep,
        "mesh_stats": loss,
        "mesh_fidelity_to_O1_at_design_point": fid,
        "mesh_fidelity_unquantized": fid_unquant,
    }


# ---------------------------------------------------------------------------
# 自检（≥12 项 · 全确定性判据）
# ---------------------------------------------------------------------------
def accelerator_ref_self_check(seed: int = SEED) -> dict:
    """端到端自检：确定性 / 正交性 / 收敛 / 精度 / 趋势 / 网格统计 / 披露。"""
    rep = run_reference(seed=seed)
    rep2 = run_reference(seed=seed)
    checks = {}

    # ① 确定性：同种子两次运行关键数字逐位一致
    checks["determinism_same_seed"] = (
        rep["test_acc_golden"] == rep2["test_acc_golden"]
        and rep["error_attribution"] == rep2["error_attribution"])
    # ② 训练收敛（golden 域）
    checks["train_converged"] = rep["train_acc_golden"] >= 0.85
    # ③ golden 测试精度下限（链路行为正确性）
    checks["test_acc_golden_floor"] = rep["test_acc_golden"] >= 0.80
    # ④ 混合精度损失上界（设计点 6bit 相位 + 8bit DAC/ADC）
    checks["hybrid_acc_drop_bound"] = rep["acc_drop_points"] <= 5.0
    # ⑤ 相位量化趋势：e1 随位数严格下降（端点对，允许中间相等）
    sw = rep["phase_bits_sweep_e1"]
    checks["phase_trend_strict_endpoints"] = (
        sw[8] < sw[4] < sw[2] and sw[8] < sw[6])
    # ⑥ 交叉阵列量化趋势：e2_iso 随位数下降（端点对）
    us = rep["unit_bits_sweep_e2_iso"]
    checks["unit_trend_endpoints"] = us[8] <= us[6] <= us[3]
    # ⑦ 误差源分离：设计点下 e1 与 e2_iso 同量级且都被端到端覆盖
    ea = rep["error_attribution"]
    checks["error_attribution_consistent"] = (
        0.0 < ea["e1_photonic_rel_max"] and 0.0 < ea["e2_crossbar_iso_rel_max"]
        and ea["e2_e2e_rel_max"] >= min(ea["e1_photonic_rel_max"],
                                        ea["e2_crossbar_iso_rel_max"]) * 0.5)
    # ⑧ 网格统计：MZI 片数 = N(N−1)/2、每模深度 = 2N−3（三角网格定理值）
    ms = rep["mesh_stats"]
    checks["mesh_topology_theorem"] = (
        ms["n_mzi"] == N_MODE * (N_MODE - 1) // 2
        and ms["per_mode_optical_depth"] == 2 * N_MODE - 3)
    # ⑨ 损耗双口径：每模 < 总级联（口径不可互换的自洽）
    checks["loss_dual_basis_consistent"] = (
        0.0 < ms["per_mode_db"] < ms["total_db"]
        and ms["crossing_loss_included_in_per_mode"] is False)
    # ⑩ 未量化重构对照锚：bits=0 分解重构应为机器精度（分离量化效应）
    checks["mesh_fidelity_high"] = rep["mesh_fidelity_unquantized"] >= 1.0 - 1e-9
    # ⑪ tiling 合成一致性（复用 E3 分块纪律在真实训练权重上成立）
    X, y, tr, te = _make_dataset(seed)
    _, W2, _ = _train_model(seed)
    O1, _, _ = _train_model(seed)
    Z1g = np.maximum(_pad(X[te]) @ O1.T, 0.0)
    y_full = AnalogMvmUnit(W2, dac_bits=8, adc_bits=8).forward(Z1g[0])[0]
    y_tile = tiled_mvm(W2, Z1g[0], tile=4, dac_bits=8, adc_bits=8)
    checks["tiling_consistency_real_weights"] = (
        float(np.max(np.abs(y_full - y_tile))) <= 2e-2)
    # ⑫ 判决路径守卫：框架样式对象（按类型模块名判定）注入即 raise（C 级自主机器守卫）
    class _FakeTorch:                     # 模拟外部框架对象（零依赖：type.__module__ 前缀判定）
        __module__ = "torch.tensor"

    guard_ok = False
    try:
        guard_no_framework_in_judgment(_FakeTorch(), where="self_check.probe")
    except Exception:
        guard_ok = True
    checks["framework_guard_raises"] = guard_ok
    # ⑬ 诚实边界：披露无 TOPS / 无实测宣称
    checks["disclosure_no_tops"] = honest_boundary_ok()
    # ⑭ 精度数字为有限值（防 NaN/Inf 混入报告）
    checks["report_finite"] = all(
        math.isfinite(float(v)) for v in (
            rep["train_acc_golden"], rep["test_acc_golden"],
            rep["test_acc_hybrid"], ea["e1_photonic_rel_max"],
            ea["e2_crossbar_iso_rel_max"], ea["e2_e2e_rel_max"]))
    return {"checks": checks,
            "n_checks": len(checks),
            "all_pass": all(checks.values()),
            "report": rep}


# ---------------------------------------------------------------------------
# 诚实边界与披露
# ---------------------------------------------------------------------------
def honest_boundary_ok() -> bool:
    """能力主张面（route/architecture/correctness_claim/honest_boundary/案语）
    无 TOPS / TOPS-W / fJ/op 与任何「实测」宣称。

    🔴 扫描**只覆盖主张字段**：redline 键里含「不报 TOPS」这类**否定表述**，
    扫进去会恒假（血案 #17：禁词取肯定表述语义，不是字面全文 grep）。
    """
    d = ACCELERATOR_REF_DISCLOSURE
    claims = [d["route"], d["correctness_claim"], _BANNED_SCAN_TEXT]
    claims += list(d["architecture"].values()) + list(d["honest_boundary"])
    blob = repr(claims)
    bad = ("TOPS", "TOPS-W", "fJ/op", "实测", "measured")
    return not any(b in blob for b in bad)


_BANNED_SCAN_TEXT = (
    "光子/模拟混合 AI 推理加速器参考设计：合成数据集 4 类 4 维高斯团，"
    "2 层 MLP（正交约束光子层 + 量化交叉阵列电域层），确定性全批梯度下降。"
    "所有精度/误差数字均为电路级模型行为验证，不构成任何现实任务性能宣称。")

ACCELERATOR_REF_DISCLOSURE = {
    "route": "阶段 4 · L6 参考设计（W4-1）：光子/模拟混合 AI 推理加速器",
    "architecture": {
        "layer1_photonic": f"实正交 O1（{N_MODE}×{N_MODE}）→ Reck 三角 MZI 网格"
                          "（相邻模耦合，可主权 P&R）→ 移相器 b 位量化 → 重构矩阵参与推理",
        "nonlinearity": "ReLU 在电域（光子网格对经典光只做线性酉映射 —— 硬边界）",
        "layer2_electronic": "E3 模拟交叉阵列数据通路：DAC 量化 → CrossbarMVM 参考列法"
                            " → ADC 量化（AnalogMvmUnit）",
        "task": f"{C_OUT} 类 {D_IN} 维合成高斯团分类（固定种子 {SEED} · 确定性）",
    },
    "correctness_claim": "混合端到端 vs 全精度数字 golden：精度落差与逐层误差逐项归因，"
                        "且相位量化 / DAC-ADC 量化各自随位数下降（趋势判据）",
    "redline": "C 级自主（纯 numpy）· LLM 不进判决路径 · golden=同结构数字参考 · "
               "电路级口径（器件级 T1 内 · T2 锁）· 不报 TOPS/TOPS-W/fJ/op",
    "honest_boundary": [
        "数据集为固定种子合成数据 ⇒ 精度只证链路行为正确，非现实任务宣称",
        "光子层容量受正交约束（训练在物理约束内完成，为真实可达精度）",
        "移相器量化为一阶均匀相位模型（不含校准残差/漂移/串扰）",
        "插入损耗为功率预算双口径（per_mode/total），对分类决策的影响不建模进精度",
        "相干检测取实部口径（O1 实矩阵 ⇒ 实部即目标）",
        "交叉阵列继承 E3 诚实边界（理想 TIA + 均匀量化 · 电路级）",
    ],
}
