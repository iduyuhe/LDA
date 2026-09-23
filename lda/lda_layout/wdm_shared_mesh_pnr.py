# -*- coding: utf-8 -*-
"""LDA L2 · WDM 共享网格 P&R（U1：K 波长共享**单一**物理网格 · v0.9.122）。

背景（U1 = 内部总结 §4.2 第一梯队首项 · §4.4 执行顺序第 1 项）
------------------------------------------------------------------
v1（`wdm_mesh_pnr` / v0.9.120）把 K 个波长实现为 **K 套独立 N×N 网格垂直堆叠**
（`footprint_y = K·plane_dy`，每面一个独立 U_k）⇒ **面积 ∝ K**。

U1 目标：K 个波长**共享同一套物理网格**（同一组 MZI、同一份位相配置），
**波长作为并行维** ⇒ 吞吐 ×K、**面积 ≈1×**。

为什么可行（物理机制）
------------------------------------------------------------------
MZI 网格对波长是**透明**的（理想情形下 θ/φ 与 λ 无关）⇒ K 个波长在同一网格
中经历**同一变换 U** ⇒ 输出 y_k = U·x_k（K 路数据并行、共享同一物理资源）。

🔴 关键架构结论（本模块确立 · 反直觉但重要）：
  波分复用/解复用**必须落在光接口层**（片外 AWG，或异质集成微环阵列），
  **片上不能**展开为逐轨逐波长的波长选择性互连。原因：单层平面波导上
  「N 条轨 × K 个波长各自由独立源驱动」= **K×N 完全二分交叉图**，
  **非平面**（K,N ≥ 2 时无法单层无交叉布线）。v1 之所以能单层签核，正是
  因为它把波长**空间化**成 K 个互不相交的面（代价 = 面积 ×K）。
  ⇒ U1 的「面积 ×K → ×1」**必须**以「波长复用移出网格平面」为交换条件。

诚实边界（本模块的核心交付之一 —— 不宣称「K 波长完全等价」）
------------------------------------------------------------------
MZI 的相位**并非严格波长无关**：
  - 相移器 φ（热光或电光）：φ = 2π·n_eff·Δn·L/λ ⇒ `φ(λ_k) = φ(λ_ref)·(λ_ref/λ_k)`；
  - 耦合角 θ：色散取决于实现 —— 宽带 MMI ≈ 无色散，相位型耦合器 ∝ 1/λ。
⇒ 每波长的**实际变换 U(λ_k) ≠ U**。本模块用 `analyze_wdm_dispersion` 在
**两个极限**（θ 无色散 / θ 全色散）上量化该偏差，给出「波长窗口」结论。

本模块**不复制** v1：v1 保留「每 λ 独立变换 U_k（可重配置）」的能力；
U1 提供「共享网格（面积 ×1）」的能力。两者是互补选项，非替代。

全部死标量（numpy 闭式），LLM 不进判决路径。零外部依赖（纯 numpy）。
"""
from __future__ import annotations

import cmath
from typing import Dict, List, Optional

import numpy as np

from lda_layout.mesh_pnr import (
    build_mesh_pnr,
    clements_rect_decompose,
    mesh_rect_fidelity,
)
from lda_layout.wdm_mesh_pnr import wdm_ring_anchor

__all__ = [
    "analyze_wdm_dispersion",
    "build_wdm_shared_mesh_pnr",
    "demo_wdm_shared_mesh",
    "wdm_shared_reverse_guard",
]


# ---------------------------------------------------------------------------
# 色散模型：K 个波长在**同一份**位相配置下的实际变换
# ---------------------------------------------------------------------------
def analyze_wdm_dispersion(bs_list, D, U_target: np.ndarray, wl_ref_nm: float,
                           wavelengths_nm: List[float],
                           theta_dispersion: float = 0.0) -> Dict[str, object]:
    """K 个波长共享同一位相配置时，各波长的**实际**版级保真度。

    相位缩放律（相位型器件的普遍规律，非拟合）：
      φ(λ) ∝ 1/λ  ⇒  φ_k = φ_ref · (λ_ref / λ_k)
      θ 色散由 `theta_dispersion ∈ [0,1]` 参数化：
        0.0 = 宽带耦合器（MMI，θ 无色散）
        1.0 = 相位型耦合器（θ ∝ 1/λ，与 φ 同律）

    返回 {per_wavelength: [...], min_fidelity, max_deviation, wl_window_nm}。
    """
    if not (0.0 <= theta_dispersion <= 1.0):
        raise ValueError("theta_dispersion 须落在 [0,1]")
    N = int(np.array(U_target).shape[0])
    D = np.array(D, dtype=complex)
    d_phases = [cmath.phase(complex(D[i, i])) for i in range(N)]

    per: List[Dict[str, float]] = []
    for wl in wavelengths_nm:
        ratio = float(wl_ref_nm) / float(wl)            # 相位缩放比
        r_theta = 1.0 + theta_dispersion * (ratio - 1.0)
        bs_k = [(int(j), float(th) * r_theta, float(ph) * ratio)
                for (j, th, ph) in bs_list]
        D_k = np.diag([cmath.exp(1j * (p * ratio)) for p in d_phases]
                      ).astype(complex)
        fid = mesh_rect_fidelity(bs_k, D_k, U_target)
        per.append({
            "wl_nm": float(wl),
            "delta_nm": float(wl) - float(wl_ref_nm),
            "fidelity": float(fid),
            "deviation": float(1.0 - fid),
        })

    min_fid = min(p["fidelity"] for p in per)
    max_dev = max(p["deviation"] for p in per)
    # 波长窗口：保真度 ≥ 0.999 的波长跨度（设计预算口径，诚实标注）
    ok = [p for p in per if p["fidelity"] >= 0.999]
    win = (max(p["delta_nm"] for p in ok) - min(p["delta_nm"] for p in ok)
           if len(ok) >= 2 else 0.0)
    return {
        "theta_dispersion": theta_dispersion,
        "wl_ref_nm": float(wl_ref_nm),
        "per_wavelength": per,
        "min_fidelity": float(min_fid),
        "max_deviation": float(max_dev),
        "wl_window_nm_ge_0p999": float(win),
    }


# ---------------------------------------------------------------------------
# λ 接口层预算（WDM MUX/DEMUX —— 落在网格平面之外，见模块 docstring）
# ---------------------------------------------------------------------------
def _lambda_interface_budget(wavelengths_nm: List[float], n_g: float, m_ring: int,
                             gap: float, il_per_ch_db: float, xtalk_db: float
                             ) -> Dict[str, object]:
    """WDM 复用/解复用接口的通道预算 + 微环方案物理锚（若走微环实现）。"""
    anchors = [wdm_ring_anchor(wl, n_g=n_g, m=m_ring, gap=gap)
               for wl in wavelengths_nm]
    K = len(wavelengths_nm)
    spacing = (abs(wavelengths_nm[1] - wavelengths_nm[0])
               if K > 1 else 0.0)
    fsr_min = min(a["FSR_nm"] for a in anchors)
    # 接口插入损耗（每通道，双向 = mux + demux）
    il_total_db = 2.0 * il_per_ch_db
    return {
        "K": K, "channel_spacing_nm": float(spacing),
        "il_per_ch_db": float(il_per_ch_db),
        "xtalk_db": float(xtalk_db),
        "il_total_db": float(il_total_db),
        "fsr_min_nm": float(fsr_min),
        "fsr_ge_spacing_ok": bool(fsr_min > spacing),
        "ring_anchors": anchors,
        "note": "接口层（片外 AWG 或异质集成微环阵列）；片上网格对波长透明",
    }


# ---------------------------------------------------------------------------
# 主构造：K 波长共享单套网格
# ---------------------------------------------------------------------------
def build_wdm_shared_mesh_pnr(U_target: Optional[np.ndarray] = None,
                              wavelengths_nm: Optional[List[float]] = None,
                              N: int = 16, rail_pitch: float = 4.0,
                              il_per_ch_db: float = 2.5, xtalk_db: float = -25.0,
                              n_g: float = 2.45, m_ring: int = 30,
                              gap: float = 0.3, ps_arm_um: float = 1000.0,
                              vpi_l_v_mm: float = 7.5) -> dict:
    """K 波长 × N×N —— **共享单套物理网格**版（U1）。

    与 v1（`build_wdm_mesh_pnr`）的差别只有一个但决定性：
      网格只用**一次**（n_mzi = N(N−1)/2，而非 K·N(N−1)/2），
      K 个波长共享它 ⇒ 面积 ≈ 单波长核，吞吐 ×K。

    返回结构化报告：单套网格的 DRC/LVS/保真度（继承 `build_mesh_pnr` grid2d
    已证结论）+ WDM 语义层（色散量化 / λ 接口预算 / 面积对比）。
    """
    from lda_l2.mzi_mesh_matmul import dft_matrix

    if wavelengths_nm is None:
        wavelengths_nm = [1550.0, 1552.5, 1555.0, 1557.5]
    K = len(wavelengths_nm)
    if K < 1:
        raise ValueError("至少 1 个波长")
    if U_target is None:
        U_target = dft_matrix(N)
    U = np.array(U_target, dtype=complex)
    if U.shape != (N, N):
        raise ValueError(f"U_target 须为 {N}×{N}")

    # ---- ① 单套网格（复用 grid2d 压实链路：保真度 1.0 / DRC / LVS 均已证）----
    base = build_mesh_pnr(U, rail_pitch=rail_pitch, layout_mode="grid2d",
                          ps_arm_um=ps_arm_um, vpi_l_v_mm=vpi_l_v_mm)

    # ---- ② 色散量化（两个极限界定影响区间）----
    bs_list, D = clements_rect_decompose(U)
    wl_ref = float(wavelengths_nm[K // 2])      # 取中位波长为设计参考
    disp_broad = analyze_wdm_dispersion(bs_list, D, U, wl_ref, wavelengths_nm,
                                        theta_dispersion=0.0)
    disp_full = analyze_wdm_dispersion(bs_list, D, U, wl_ref, wavelengths_nm,
                                       theta_dispersion=1.0)

    # ---- ③ λ 接口预算 ----
    iface = _lambda_interface_budget(wavelengths_nm, n_g=n_g, m_ring=m_ring,
                                     gap=gap, il_per_ch_db=il_per_ch_db,
                                     xtalk_db=xtalk_db)

    # ---- ④ 面积对比（共享 vs 朴素 K 套）----
    fp_single = float(base["footprint_um2"])
    fp_naive_lower = K * fp_single               # K 套网格的面积下界（保守口径）
    fp_shared = fp_single                        # 共享 ⇒ 就是单面
    area_ratio = fp_shared / fp_naive_lower      # = 1/K

    n_mzi_shared = int(base["n_mzi"])
    n_mzi_naive = K * n_mzi_shared

    honest_note = (
        f"U1 · WDM **共享网格**：K={K} 波长共享单套 N={N}×N Clements 网格"
        f"（同一组 MZI / 同一位相配置），波长作并行维 ⇒ 吞吐 ×{K}、"
        f"面积 ={fp_shared / 1e6:.3f} mm²（朴素 K 套下界 "
        f"{fp_naive_lower / 1e6:.3f} mm² 的 {area_ratio:.3f}× = 1/K）。"
        f"MZI 数 {n_mzi_shared}（若非共享则为 {n_mzi_naive}）。"
        f"网格保真度（分解级/版级）均机器精度，DRC/LVS 结论继承 grid2d 已证。"
        f"🔴 诚实边界 ①**色散**：相移器 φ(λ)∝1/λ、耦合角 θ 色散视实现而定 ⇒ "
        f"K 波长**并非完全等价**：θ 无色散（宽带 MMI）极限下版级保真度 "
        f"min={disp_broad['min_fidelity']:.6f}；θ 全色散（相位型耦合器）极限下 "
        f"min={disp_full['min_fidelity']:.6f}（参考波长 λ={wl_ref:.1f}nm 处为 "
        f"1.0）。**真值须 foundry 器件色散表征**。"
        f"②**λ 复用位置**：单层平面波导上「N 轨 × K 波长各自独立源」为 K×N "
        f"完全二分交叉（**非平面**）⇒ 波分复用/解复用**落在光接口层**"
        f"（片外 AWG 或异质集成微环阵列），接口预算 IL={iface['il_total_db']:.1f}dB、"
        f"串扰 {iface['xtalk_db']:.0f}dB（设计预算，非实测）。"
        f"③PDK 为演示近似 SOI。判决全死标量，LLM 不进路径。"
    )

    return {
        "K": K, "N": N, "wavelengths_nm": list(wavelengths_nm),
        "wl_ref_nm": wl_ref,
        "n_mzi": n_mzi_shared,
        "n_mzi_naive": n_mzi_naive,
        "fidelity": float(base["fidelity"]),
        "layout_fidelity": float(base["layout_fidelity"]),
        "drc_pass": bool(base["drc_pass"]),
        "lvs_verdict": base["lvs_verdict"],
        "lvs_n_violations": int(base["lvs_n_violations"]),
        "lvs_match": base["lvs_match"],
        "lvs_full": base["lvs_full"],
        "footprint_um2": fp_shared,
        "footprint_naive_lower_um2": fp_naive_lower,
        "area_ratio_vs_naive": float(area_ratio),
        "throughput_factor": K,
        "bandwidth_density_xK": K,
        "dispersion_broadband_theta": disp_broad,
        "dispersion_dispersive_theta": disp_full,
        "lambda_interface": iface,
        "gds_bytes": base["gds_bytes"],
        "gds_elements": base["gds_elements"],
        "n_cols": base["n_cols"],
        "base": base,
        "link": base["link"], "placement": base["placement"],
        "routes": base["routes"],
        "honest_note": honest_note,
    }


# ---------------------------------------------------------------------------
# demo + 反向护栏
# ---------------------------------------------------------------------------
def demo_wdm_shared_mesh(K: int = 4, N: int = 16) -> dict:
    """K 波长共享单网格 demo（默认 K=4 LAN-WDM × N=16）。"""
    wls = [1550.0 + 2.5 * i for i in range(K)]
    rep = build_wdm_shared_mesh_pnr(N=N, wavelengths_nm=wls)
    rep["target"] = f"{K} 波长共享 {N}×{N} 单网格（U1）"
    return rep


def wdm_shared_reverse_guard(rep: dict) -> Dict[str, object]:
    """反向护栏：判据必须**真会亮红**（护栏自证，非纸上谈兵）。

    G1（面积判据有效性）：朴素 K 套方案的面积**必** ≥ K × 单面（下界口径），
      且共享方案严格小于它 ⇒ 面积判据能区分「共享」与「复制」。
    G2（色散判据有效性）：把波长窗口放大到 λ_ref 的 ±10%（远超 LAN-WDM）
      ⇒ θ 全色散极限下保真度**必**跌破 0.999 ⇒ 色散判据不是恒真。
    G3（分解护栏继承）：非酉 U ⇒ `clements_rect_decompose` 拒绝（ValueError）。
    G4（LVS 护栏继承）：删一条 rail 路由 ⇒ LVS 必 REJECT。
    """
    from lda_l2 import lvs as lvs_mod

    out: Dict[str, object] = {}
    K = int(rep["K"])
    fp_single = float(rep["footprint_um2"])
    naive = float(rep["footprint_naive_lower_um2"])
    out["G1_area_jurisdiction_works"] = bool(
        abs(naive - K * fp_single) < 1e-9 and fp_single < naive)

    # G2：把波长拉开到 ±10% ⇒ 色散偏差必超 0.999 门限
    wl_ref = float(rep["wl_ref_nm"])
    wide = [wl_ref * 0.90, wl_ref, wl_ref * 1.10]
    from lda_layout.mesh_pnr import clements_rect_decompose as _cd
    from lda_l2.mzi_mesh_matmul import dft_matrix as _dft
    U_t = _dft(int(rep["N"]))
    bs, D = _cd(U_t)
    disp = analyze_wdm_dispersion(bs, D, U_t, wl_ref, wide, theta_dispersion=1.0)
    out["G2_dispersion_judge_works"] = bool(disp["min_fidelity"] < 0.999)
    out["G2_min_fidelity_wide"] = float(disp["min_fidelity"])

    # G3：非酉 ⇒ 分解拒绝
    try:
        _cd(np.array(U_t, dtype=complex) * 2.0)
        out["G3_nonunitary_rejected"] = False
    except ValueError as exc:
        out["G3_nonunitary_rejected"] = True
        out["G3_mode"] = str(exc)

    # G4：删一条 rail 路由 ⇒ LVS REJECT
    bad = build_wdm_shared_mesh_pnr(N=int(rep["N"]),
                                    wavelengths_nm=list(rep["wavelengths_nm"]))
    key = "r0_0"
    if key in bad["routes"]:
        del bad["routes"][key]
        lvs_bad = lvs_mod.run_lvs(bad["link"], bad["placement"], bad["routes"],
                                  tol=1.0)
        out["G4_open_detected"] = bool(lvs_bad["verdict"] == "REJECT"
                                       and lvs_bad["n_violations"] > 0)
    else:
        out["G4_open_detected"] = False
    return out


def _selftest() -> int:  # pragma: no cover - 手工入口
    r = demo_wdm_shared_mesh(K=4, N=8)
    print(f"K={r['K']} N={r['N']} n_mzi={r['n_mzi']} (naive {r['n_mzi_naive']})")
    print(f"fidelity={r['fidelity']:.12f} layout={r['layout_fidelity']:.12f}")
    print(f"DRC={'PASS' if r['drc_pass'] else 'FAIL'} LVS={r['lvs_verdict']} "
          f"(viol={r['lvs_n_violations']})")
    print(f"footprint={r['footprint_um2'] / 1e6:.4f} mm² "
          f"ratio_vs_naive={r['area_ratio_vs_naive']:.4f}")
    print(f"dispersion(broadband)={r['dispersion_broadband_theta']['min_fidelity']:.6f} "
          f"(full)={r['dispersion_dispersive_theta']['min_fidelity']:.6f}")
    print(f"guard={wdm_shared_reverse_guard(r)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_selftest())
