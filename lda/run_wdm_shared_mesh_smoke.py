# -*- coding: utf-8 -*-
"""U1 · WDM **共享网格** P&R 回归护栏（K 波长共享单套 N×N 网格）。

把 `lda_layout/wdm_shared_mesh_pnr.py` 接入 CI 核心门禁。任何主权链改动
（mesh_pnr 分解/压实列分配 / placement.port_anchor / lvs / drc / mzi_mesh）
一旦破坏下述任一条即 FAIL：

  - **共享语义**：MZI 只用一次（n_mzi = N(N−1)/2），而非 K 套（K·N(N−1)/2）；
  - **面积判据**：footprint = 单面（比值 1/K），严格小于朴素 K 套的下界；
  - 网格保真度（分解级 + 版级）在参考波长处机器精度；
  - DRC PASS · 单一 LinkModel 单次 LVS ACCEPT（0 违规、器件/网络全匹配）；
  - **色散量化**（诚实边界）：K 波长共享同一位相配置时 φ(λ)∝1/λ 引起偏差，
    本 smoke 断言该偏差**被量化且物理自洽**（离参考波长越远偏差越大），
    而非断言「K 波长完全等价」；
  - λ 接口预算（微环方案 FSR > 信道间隔）；
  - **反向护栏**（缺陷态必亮红）：面积判据可区分共享/复制；色散判据在宽窗口
    下必破 0.999；非酉 U ⇒ 分解拒绝；断一条 rail net ⇒ LVS REJECT。

数据流全程几何独立：路由端点 → LVS 版图网表（几何恢复）比对原理图 netlist。
不依赖 torch/numba/cupy/meep/tidy3d；纯 numpy。按准入准则（<5s 且无重依赖）
无权豁免，必须进 CORE_SMOKES。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))   # lda/
ROOT = os.path.dirname(HERE)                          # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), return_ok=True, detail_on="fail")


def main() -> int:
    from lda_layout.wdm_shared_mesh_pnr import (demo_wdm_shared_mesh,
                                                wdm_shared_reverse_guard)

    K, N = 4, 16
    rep = demo_wdm_shared_mesh(K=K, N=N)
    ok = True

    # ---- ① 共享语义：网格只用一次 ----
    n_expected = N * (N - 1) // 2
    ok &= check(f"共享网格 MZI 数 == N(N-1)/2 == {n_expected}",
                rep["n_mzi"] == n_expected, detail=str(rep["n_mzi"]))
    ok &= check("朴素（K 套）MZI 数 == K × 共享数",
                rep["n_mzi_naive"] == K * rep["n_mzi"],
                detail=f"{rep['n_mzi_naive']} vs {K}×{rep['n_mzi']}")
    ok &= check("共享 < 朴素（网格确实共享，非复制）",
                rep["n_mzi"] < rep["n_mzi_naive"],
                detail=f"{rep['n_mzi']} < {rep['n_mzi_naive']}")

    # ---- ② 面积判据（U1 核心）----
    ratio = rep["area_ratio_vs_naive"]
    ok &= check("面积比 == 1/K（共享 ⇒ 单面）", abs(ratio - 1.0 / K) < 1e-12,
                detail=f"{ratio:.12f} vs {1.0 / K:.12f}")
    fp, fp_naive = rep["footprint_um2"], rep["footprint_naive_lower_um2"]
    ok &= check("footprint < K × 单面（严格面积收益）", fp < fp_naive,
                detail=f"{fp:.1f} < {fp_naive:.1f} µm²")

    # ---- ③ 保真度（参考波长处机器精度）----
    ok &= check("分解级保真度 ≈1.0（参考波长）",
                abs(rep["fidelity"] - 1.0) < 1e-9,
                detail=f"{rep['fidelity']:.15f}")
    ok &= check("版级保真度 ≈1.0（参考波长）",
                abs(rep["layout_fidelity"] - 1.0) < 1e-9,
                detail=f"{rep['layout_fidelity']:.15f}")

    # ---- ④ DRC / LVS ----
    ok &= check("DRC PASS（逐 MZI 死标量）", bool(rep["drc_pass"]))
    ok &= check("LVS ACCEPT", rep["lvs_verdict"] == "ACCEPT",
                detail=f"{rep['lvs_verdict']} viol={rep['lvs_n_violations']}")
    ok &= check("LVS 0 违规", rep["lvs_n_violations"] == 0,
                detail=str(rep["lvs_n_violations"]))
    m = rep["lvs_match"]
    sch = rep["lvs_full"]["schematic"]
    ok &= check("LVS 器件全匹配", m["n_devices_match"] == sch["n_instances"],
                detail=f"{m} sch={sch['n_instances']}")
    ok &= check("LVS 网络全匹配", m["n_nets_match"] == m["n_nets_total"],
                detail=str(m))

    # ---- ⑤ 色散量化（诚实边界，非「完全等价」断言）----
    broad = rep["dispersion_broadband_theta"]
    full = rep["dispersion_dispersive_theta"]
    per = broad["per_wavelength"]
    wl_ref = rep["wl_ref_nm"]
    ref_entry = [p for p in per if abs(p["wl_nm"] - wl_ref) < 1e-9]
    ok &= check("参考波长处色散偏差为零（ratio=1 定义自洽）",
                len(ref_entry) == 1 and ref_entry[0]["deviation"] < 1e-12,
                detail=str(ref_entry))
    worst = max(per, key=lambda p: abs(p["delta_nm"]))
    max_dev = max(p["deviation"] for p in per)
    ok &= check("色散偏差随 |Δλ| 单调（最远波长偏差最大 ⇒ 物理自洽）",
                abs(worst["deviation"] - max_dev) < 1e-12,
                detail=f"worst Δλ={worst['delta_nm']} dev={worst['deviation']:.6e}")
    ok &= check("θ 全色散极限比宽带极限更差（色散模型有区分度）",
                full["min_fidelity"] < broad["min_fidelity"],
                detail=f"{full['min_fidelity']:.9f} < {broad['min_fidelity']:.9f}")
    ok &= check("色散偏差已量化且非平凡（0 < max_dev < 1e-2 · LAN-WDM 窗口）",
                0.0 < broad["max_deviation"] < 1e-2,
                detail=f"{broad['max_deviation']:.6e}")

    # ---- ⑥ λ 接口预算 ----
    iface = rep["lambda_interface"]
    ok &= check("接口 FSR > 信道间隔（微环方案可行）",
                bool(iface["fsr_ge_spacing_ok"]),
                detail=f"FSR={iface['fsr_min_nm']:.2f} spacing={iface['channel_spacing_nm']:.2f}")
    ok &= check("接口 IL/串扰预算非空（设计预算，非实测）",
                iface["il_total_db"] > 0 and iface["xtalk_db"] < 0,
                detail=f"IL={iface['il_total_db']} xtalk={iface['xtalk_db']}")

    # ---- ⑦ GDS 非空 ----
    ok &= check("GDS 非空", rep["gds_elements"] > 0 and bool(rep["gds_bytes"]),
                detail=f"elems={rep['gds_elements']}")

    # ---- ⑧ 反向护栏（护栏自证：判据真会响）----
    g = wdm_shared_reverse_guard(rep)
    ok &= check("反向 G1：面积判据可区分「共享 / 复制」",
                g.get("G1_area_jurisdiction_works") is True, detail=str(g))
    ok &= check("反向 G2：宽波长窗口 ⇒ 色散判据必破 0.999",
                g.get("G2_dispersion_judge_works") is True, detail=str(g))
    ok &= check("反向 G3：非酉 U ⇒ 分解护栏拒绝",
                g.get("G3_nonunitary_rejected") is True, detail=str(g))
    ok &= check("反向 G4：断 rail net ⇒ LVS REJECT",
                g.get("G4_open_detected") is True, detail=str(g))

    return 0 if ok else 1


if __name__ == "__main__":
    rc = main()
    print(f"PASS={globals().get('PASS', 0)} FAIL={globals().get('FAIL', 0)}")
    sys.exit(rc)
