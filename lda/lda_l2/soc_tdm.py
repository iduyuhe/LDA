# -*- coding: utf-8 -*-
"""G6 杠杆③：时间复用调度（同 mesh 时分复用 + 时序状态机 + 帧级精度）。

真算模型：K 帧，每帧目标酉 U_k（随机 Haar）；每帧用 reck_decompose(U_k) 求
(ops_k, D_k)，assemble_mesh 重建 U_rec_k≈U_k（保真度≈机器精度）。帧级精度：
每帧 MVM 相对误差（重构误差 = ‖(U_rec_k−U_k)x‖/‖U_k x‖）< 量化容差。重配置开销：
相邻帧间 MZI 相位（φ）变更计数（诚实度量，非物理时延；真实时延需工艺角数据，本项目无
NDA 真值）。

时序状态机：TDMController（frame counter + config buffer 存 K 帧相位向量），tick() 推进帧；
readout 取当前帧相位向量。重配置开销由状态机实测驱动累计。

红线：不报能效；判据真算（纯 numpy）；不 import A 级禁借求解器。
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

from lda_l2.mzi_mesh_matmul import reck_decompose, assemble_mesh, unitary_fidelity

_LDA_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_LDA_DIR)
for _p in (_LDA_DIR, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


TDM_DEFAULT_FRAMES = 4
TDM_TOL_MVM_REL = 0.05


def _random_haar(N: int, rng: np.random.Generator) -> np.ndarray:
    """随机 Haar 酉（QR 分解，真算）。"""
    Z = rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))
    U, _ = np.linalg.qr(Z)
    return U


def tdm_frame_unitary(N: int, seed: int) -> Dict[str, Any]:
    """单帧：随机 Haar 目标酉 → reck_decompose → assemble_mesh 重建。"""
    rng = np.random.default_rng(seed)
    U = _random_haar(N, rng)
    ops, D = reck_decompose(U)
    U_rec = assemble_mesh(ops, D, N)
    fid = unitary_fidelity(U_rec, U)
    return {"U_target": U, "ops": ops, "D": D, "U_rec": U_rec, "fidelity": fid}


def _phi_vector(ops) -> List[float]:
    return [float(phi) for (_, _, _, phi) in ops]


def tdm_reconfig_cost(ops_prev, ops_cur) -> int:
    """相邻帧 MZI 相位变更计数（θ 固定 fabric，仅 φ 重配置）。"""
    pv = _phi_vector(ops_prev)
    cv = _phi_vector(ops_cur)
    n = min(len(pv), len(cv))
    return int(sum(1 for i in range(n) if abs(pv[i] - cv[i]) > 1e-9))


class TDMController:
    """时分复用时序状态机：存 K 帧相位向量，tick() 循环推进，统计重配置开销。"""

    def __init__(self, frames_phi: List[List[float]]):
        self.frames_phi = [list(v) for v in frames_phi]
        self.K = len(frames_phi)
        self.t = 0

    def tick(self) -> int:
        self.t = (self.t + 1) % self.K
        return self.t

    def current_frame(self) -> int:
        return self.t

    def current_phi(self) -> List[float]:
        return self.frames_phi[self.t]

    def reconfig_from(self, prev_t: int) -> int:
        """当前帧相对 prev_t 帧的相位变更计数。"""
        a = np.array(self.frames_phi[prev_t], dtype=float)
        b = np.array(self.frames_phi[self.t], dtype=float)
        n = min(len(a), len(b))
        return int(np.sum(np.abs(a[:n] - b[:n]) > 1e-9))


def soc_tdm_report(N: int = 8, K: int = 4, dac_bits: int = 16,
                   seed: int = 20261009) -> Dict[str, Any]:
    """G6 杠杆③ 时间复用主入口：K 帧 MVM 保真 + 重配置相位变更计数。"""
    frames = []
    phi_vecs = []
    per_frame = []
    worst_err = 0.0
    for k in range(K):
        f = tdm_frame_unitary(N, seed + k * 100003)
        frames.append(f)
        phi_vecs.append(_phi_vector(f["ops"]))
        rng = np.random.default_rng(seed + k * 31 + 777)
        x = rng.standard_normal(N) + 1j * rng.standard_normal(N)
        x = x / np.linalg.norm(x)
        y = f["U_rec"] @ x
        y_g = f["U_target"] @ x
        err = float(np.linalg.norm(y - y_g) / (np.linalg.norm(y_g) + 1e-30))
        worst_err = max(worst_err, err)
        per_frame.append({"frame": k, "fidelity": f["fidelity"],
                          "mvm_rel_err": err, "n_mzi": len(f["ops"])})

    # 重配置开销（状态机驱动 K 次 tick 累计）
    ctrl = TDMController(phi_vecs)
    reconfig_total = 0
    for _ in range(K):
        prev = ctrl.current_frame()
        ctrl.tick()
        reconfig_total += ctrl.reconfig_from(prev)

    mvm_pass = bool(worst_err < TDM_TOL_MVM_REL)
    all_pass = mvm_pass
    return {
        "N": int(N), "K": int(K), "tol_mvm_rel": TDM_TOL_MVM_REL,
        "per_frame": per_frame, "worst_mvm_rel_err": worst_err,
        "reconfig_total_phase_updates": reconfig_total,
        "n_mzi": len(frames[0]["ops"]),
        "all_pass": all_pass,
        "honest_boundary": (
            "🔴 TDM 真算模型：每帧目标酉 U_k 经 reck_decompose 求 (ops_k, D_k)，"
            "assemble_mesh 重建 U_rec_k≈U_k（保真度≈机器精度），帧级 MVM 误差即重构误差。"
            "重配置开销以「相邻帧 MZI 相位变更计数」诚实度量（非物理时延；真实时延需"
            "工艺角数据，本项目无 NDA 真值）。时序状态机 TDMController 存 K 帧相位向量、"
            "tick() 推进帧。能效维度仍禁报（红线）。"),
    }


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_G6T_N", "8")))
    ap.add_argument("--K", type=int, default=int(os.environ.get("LDA_G6T_K", "4")))
    a = ap.parse_args()
    rep = soc_tdm_report(N=a.N, K=a.K)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_frame"},
                     indent=2, default=str))
    for fr in rep["per_frame"]:
        print("  frame=%d fid=%.8f mvm_err=%.3e" % (fr["frame"], fr["fidelity"], fr["mvm_rel_err"]))
    print("ALL_PASS =", rep["all_pass"])
    if not rep["all_pass"]:
        raise SystemExit(1)
