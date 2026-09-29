"""LDA-Q3b · 光子硬件物理链路演示（M3 物理深度 · 源→mesh→损耗→探测 端到端）。

把 M2 的「可编程 MZI mesh」从**理想酉器件**推进到**真实光子硬件链路**：

    ① SPDC 预告单光子源（D-114） → ② 片上可编程 mesh（M2/D-113） →
    ③ 逐模光子损耗（D-116） → ④ SNSPD on/off 探测（D-115）

════════════════════════════════════════════════════════════════════════════
四节
════════════════════════════════════════════════════════════════════════════
① **源质量**：λ 扫描——PNR 预告纯度=1、on/off 预告纯度 (1−λ²)/(1+λ²)、
   g²(0)=2λ²、多光子污染走 WCS 闭式。给出「理想单光子源」与「真实 SPDC 源」的差距。
② **片上 HOM 端到端**：2 模片上 50:50 分束器，两条**方法学独立**的路：
     (a) 全开放系统：Fock 空间酉（D-113 玻色振幅）→ 逐模损耗通道（D-116 Kraus）→
         on/off 符合 POVM（D-115）；
     (b) 有效效率捷径：理想量子分布 × on/off 响应（η_eff = µ·η，靠 D-115 效率≡损耗桥）。
   两条必须一致 ⇒ 芯片级验证「损耗 × 探测」可合并为单一效率。
③ **mesh + 损耗**：4 模 DFT mesh，输入 |1,1,0,0⟩ 双光子 → 逐模损耗后输出分布退化，
   报告量子态保真度随损耗的变化（理想酉 → 开放系统）。
④ **链路预算**：源污染 × 损耗 × 探测效率 ⇒ 等效单光子源品质与符合计数率。

产出：lda_q3b_report.json + lda_q3b_lossscan.svg
运行：python examples/lda_qchip_m3b.py
"""
from __future__ import annotations

import itertools
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if os.path.join(ROOT, "lda") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_qeda import loqc_states as LS          # noqa: E402
from lda_qeda import photon_sources as PSRC     # noqa: E402
from lda_qeda import detectors as DET           # noqa: E402
from lda_qeda import open_system as OPEN        # noqa: E402
from lda_l2.mzi_mesh_matmul import dft_matrix   # noqa: E402

OUT = HERE


# ── Fock 空间工具 ────────────────────────────────────────────────────────────
def _all_occ(M, d):
    """所有 M 模、每模 ≤d−1 的占据元组（d^M 个）。"""
    return list(itertools.product(range(d), repeat=M))


def fock_unitary_from_mode_matrix(U_mode, M: int, d: int) -> np.ndarray:
    """在 d^M 维 Fock 空间构造 M 模线性光学酉算符（用 D-113 玻色振幅/permanent）。

    χ[out,in] = ⟨out| Û |in⟩ = per(U_{T,S})/√(Π n! Π m!)（光子数不守恒处自然为 0）。
    """
    occs = _all_occ(M, d)
    D = len(occs)
    chi = np.zeros((D, D), dtype=complex)
    for j, occ_in in enumerate(occs):
        for i, occ_out in enumerate(occs):
            chi[i, j] = LS.linear_optics_amplitude(U_mode, occ_in, occ_out)
    return chi


def _occ_index(occs, occ) -> int:
    return occs.index(tuple(occ))


def _kappas_for_eta(eta: float, M: int, t: float = 1.0):
    """由目标透射率 η 反解损耗率 κ（η=e^{−κt}）。"""
    return [-math.log(eta) / t] * M


# ── ① 源质量 ─────────────────────────────────────────────────────────────────
def source_section():
    lams = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
    rows = []
    for lam in lams:
        rows.append({
            "lambda": lam,
            "nbar_per_mode": round(PSRC.tmss_mean_photon(lam), 6),
            "purity_pnr_herald": 1.0,
            "purity_onoff_herald": round(PSRC.heralded_purity_onoff(lam), 6),
            "g2_onoff_herald": round(PSRC.heralded_g2_onoff(lam), 6),
        })
    return {
        "model": "SPDC 双模压缩真空 |TMSV⟩=√(1−λ²)Σλⁿ|n,n⟩（λ=tanh r）",
        "anchors": "PNR 预告纯度=1（纯 |1⟩）；on/off 预告纯度=(1−λ²)/(1+λ²)；g²(0)=2λ²",
        "scan": rows,
        "chosen_lambda": 0.20,
        "honest_note": "理想 SPDC（无相位噪声/模式失配/传播损耗）；真实源纯度更低。",
    }


# ── ② 片上 HOM 端到端（2 模）──────────────────────────────────────────────────
def onchip_hom_section(eta_chip=0.9, eta_det=0.9):
    """跨 θ 网格两条独立路对拍（含非 50:50 ⇒ 符合率非零，避免 0≡0 的平凡一致）。

    路(a) 全开放系统：Fock 空间酉 → 逐模损耗通道(Kraus) → on/off 符合 POVM；
    路(b) 有效效率捷径：理想量子分布 × on/off 响应(η_eff=η_chip·η_det，靠 D-115 效率≡损耗桥)。
    """
    d, M = 3, 2                                       # 2 模、每模截断 2 光子
    occs = _all_occ(M, d)
    i11 = _occ_index(occs, (1, 1))
    _, Pi_on = DET.onoff_povm(eta_det, d - 1)
    Pi_coin = np.kron(Pi_on, Pi_on)                   # Π_on^{(0)} ⊗ Π_on^{(1)}
    eta_eff = eta_chip * eta_det

    rows = []
    max_diff = 0.0
    for th in (math.pi / 4.0, math.pi / 8.0, 0.3 * math.pi, 0.1 * math.pi):
        B = LS.bs_unitary(th)
        chi = fock_unitary_from_mode_matrix(B, M, d)
        rho_in = np.zeros((len(occs), len(occs)), dtype=complex)
        rho_in[i11, i11] = 1.0                        # 输入 |1,1⟩（SPDC 预告单光子对）
        rho_loss = OPEN.kraus_multimode_evolve(
            _kappas_for_eta(eta_chip, M), M, d, chi @ rho_in @ chi.conj().T, 1.0)
        p_full = float(np.real(np.trace(Pi_coin @ rho_loss)))
        ideal_joint = {tuple(o): float(p) for o, p in LS.output_distribution(B, (1, 1)).items()}
        p_short = DET.coincidence_prob_onoff(ideal_joint, eta_eff, 0.0)
        max_diff = max(max_diff, abs(p_full - p_short))
        rows.append({
            "theta_deg": round(math.degrees(th), 3),
            "p_coin_full_open_system": p_full,
            "p_coin_effective_eff": p_short,
            "p_coin_ideal_no_loss": DET.coincidence_prob_onoff(ideal_joint, 1.0, 0.0),
        })

    # 50:50 可见度（不可区分 vs 可区分）
    th50 = math.pi / 4.0
    c2, s2 = math.cos(th50) ** 2, math.sin(th50) ** 2
    dist_joint = {(2, 0): c2 * c2, (1, 1): 2 * c2 * s2, (0, 2): s2 * s2}
    p_dist = DET.coincidence_prob_onoff(dist_joint, eta_eff, 0.0)
    ideal50 = {tuple(o): float(p) for o, p in
               LS.output_distribution(LS.bs_unitary(th50), (1, 1)).items()}
    p_ind = DET.coincidence_prob_onoff(ideal50, eta_eff, 0.0)
    vis = (p_dist - p_ind) / (p_dist + p_ind) if (p_dist + p_ind) > 0 else float("nan")

    return {
        "eta_chip": eta_chip, "eta_det": eta_det, "eta_eff": eta_eff,
        "cross_method_max_diff": max_diff,
        "theta_scan": rows,
        "hom_visibility_5050": vis,
        "p_coin_distinguishable_5050": p_dist,
        "p_coin_indistinguishable_5050": p_ind,
        "scaling": f"符合率 ∝ η_eff² = {eta_eff ** 2:.6f}（单路 ∝ η_eff）",
        "honest_note": "理想不可区分 + 理想模式匹配；实测可见度受模式失配/多光子/抖动限制。",
    }


# ── ③ mesh + 逐模损耗 ────────────────────────────────────────────────────────
def mesh_loss_section(N=4, d=3, eta=0.85):
    M = N
    occs = _all_occ(M, d)
    U = dft_matrix(N)                                  # M2 生成的 N 模 DFT mesh 酉
    chi = fock_unitary_from_mode_matrix(U, M, d)

    in_occ = tuple(1 if k < 2 else 0 for k in range(M))   # |1,1,0,0⟩
    rho_in = np.zeros((len(occs), len(occs)), dtype=complex)
    rho_in[_occ_index(occs, in_occ), _occ_index(occs, in_occ)] = 1.0
    rho_mesh = chi @ rho_in @ chi.conj().T

    rho_loss = OPEN.kraus_multimode_evolve(_kappas_for_eta(eta, M), M, d, rho_mesh, 1.0)

    # 理想量子态（无损耗）与损耗后态的保真度
    psi_ideal = chi[:, _occ_index(occs, in_occ)]
    fid = float(np.real(np.vdot(psi_ideal, rho_loss @ psi_ideal)))

    # 输出光子数分布（2 光子扇区）
    dist_ideal = LS.output_distribution(U, in_occ)
    diag_loss = np.real(np.diag(rho_loss))
    dist_loss = {occs[k]: float(diag_loss[k]) for k in range(len(occs)) if diag_loss[k] > 1e-12}

    # 剩余总概率（损耗把光子移出 2 光子扇区）
    p_within = float(sum(v for o, v in dist_loss.items() if sum(o) == 2))

    return {
        "N": N, "cutoff_d": d, "mesh": "DFT（M2 可编程 mesh 生成器）",
        "input": "|1,1,0,0⟩（SPDC 预告的双单光子）",
        "eta_per_mode": eta,
        "fock_space_dim": len(occs),
        "state_fidelity_vs_ideal": fid,
        "state_fidelity_closed_form_etaN": eta ** 2,   # N=2 光子逐模损耗 ⇒ F=η^N（闭式锚）
        "p_still_2photon_sector": p_within,
        "top_ideal_outputs": sorted(
            [(list(k), round(v, 6)) for k, v in dist_ideal.items()], key=lambda x: -x[1])[:5],
        "top_lossy_outputs": sorted(
            [(list(k), round(v, 6)) for k, v in dist_loss.items()], key=lambda x: -x[1])[:5],
        "honest_note": "逐模独立损耗模型（无模间串扰/无相位噪声）。",
    }


# ── ④ 链路预算 ───────────────────────────────────────────────────────────────
def link_budget_section(lam=0.20, eta_chip=0.9, eta_det=0.9):
    eta_eff = eta_chip * eta_det
    g2_src = PSRC.heralded_g2_onoff(lam)              # on/off 预告源 g²(0)
    # 等效单光子源：on/off 预告态的 g²(0)（含多光子污染）
    return {
        "chain": "SPDC(on/off 预告) → 片上 mesh → 逐模损耗 → SNSPD on/off",
        "eta_chip": eta_chip, "eta_det": eta_det, "eta_eff": eta_eff,
        "source_g2_at_lambda": round(g2_src, 6),
        "coincidence_rate_scaling": round(eta_eff ** 2, 6),
        "verdict": ("理想链路下 HOM 可见度 V=1（η 无关）；符合计数率 ∝ η_eff²；"
                    "真实源的多光子污染（g²(0)=2λ²>0）是可见度损失主因之一"),
        "honest_note": "链路预算为设计口径（源理想/无模式失配），非实测锚。",
    }


# ── SVG（两面板折线）────────────────────────────────────────────────────────
def render_svg(src_rows, path):
    W, H = 720, 300
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="system-ui,sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#0f172a"/>']
    # 面板 1：源纯度/g² vs λ
    def panel(x0, title, series, xlabel, ymax):
        p = [f'<text x="{x0 + 150}" y="26" fill="#e2e8f0" font-size="13" '
             f'text-anchor="middle">{title}</text>']
        gx0, gy0, gw, gh = x0 + 50, 240, 240, 180
        p.append(f'<line x1="{gx0}" y1="{gy0}" x2="{gx0 + gw}" y2="{gy0}" stroke="#475569"/>')
        p.append(f'<line x1="{gx0}" y1="{gy0}" x2="{gx0}" y2="{gy0 - gh}" stroke="#475569"/>')
        p.append(f'<text x="{gx0 + gw // 2}" y="{gy0 + 30}" fill="#94a3b8" '
                 f'font-size="11" text-anchor="middle">{xlabel}</text>')
        for (name, xs, ys, color) in series:
            pts = []
            for xv, yv in zip(xs, ys):
                px = gx0 + (xv / max(xs)) * gw
                py = gy0 - (yv / ymax) * gh
                pts.append(f"{px:.1f},{py:.1f}")
            p.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/>')
        for i, (name, xs, ys, color) in enumerate(series):
            p.append(f'<text x="{gx0 + 6}" y="{58 + i * 16}" fill="{color}" font-size="11">'
                     f'■ {name}</text>')
        return "".join(p)
    parts.append(panel(10, "SPDC 源质量 vs 截止 λ", [
        ("on/off 预告纯度", [r["lambda"] for r in src_rows], [r["purity_onoff_herald"] for r in src_rows], "#38bdf8"),
        ("g²(0)=2λ²", [r["lambda"] for r in src_rows], [r["g2_onoff_herald"] for r in src_rows], "#f472b6"),
    ], "λ", 1.05))
    # 面板 2：HOM 符合率 vs η_eff
    etas = [0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
    theta = math.pi / 4.0
    c2, s2 = math.cos(theta) ** 2, math.sin(theta) ** 2
    dist_joint = {(2, 0): c2 * c2, (1, 1): 2 * c2 * s2, (0, 2): s2 * s2}
    coin_dist = [DET.coincidence_prob_onoff(dist_joint, e, 0.0) for e in etas]
    coin_ind = [DET.coincidence_prob_onoff({(2, 0): 0.5, (0, 2): 0.5}, e, 0.0) for e in etas]
    parts.append(panel(370, "片上 HOM 符合率 vs η_eff", [
        ("可区分", etas, coin_dist, "#fb923c"),
        ("不可区分", etas, coin_ind, "#4ade80"),
    ], "η_eff", 0.55))
    parts.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


# ── 主流程 ──────────────────────────────────────────────────────────────────
def main():
    report = {
        "chip_family": "LDA-Q3b · 光子硬件物理链路（源→mesh→损耗→探测）· M3 物理深度第二/三步",
        "platform_capability": "lda_qeda/photon_sources.py(D-114) + detectors.py(D-115) + open_system.py(D-116)",
        "methodology": "闭式物理律作 golden（HBT g²/二项分布/相干态保真/纠缠保真度）；"
                       "各物理两条以上结构不同算法交叉验证；LLM 不进判决路径",
    }

    print("=" * 78)
    print("LDA-Q3b 光子硬件链路：SPDC 源 → 片上 mesh → 逐模损耗 → SNSPD 探测")
    print("=" * 78)

    report["source"] = source_section()
    print("① 源质量（SPDC 预告）")
    for r in report["source"]["scan"]:
        print(f"   λ={r['lambda']:.2f}  n̄/模={r['nbar_per_mode']:.4f}  "
              f"on/off 纯度={r['purity_onoff_herald']:.4f}  g²(0)={r['g2_onoff_herald']:.4f}")

    report["onchip_hom"] = onchip_hom_section()
    h = report["onchip_hom"]
    print("② 片上 HOM 端到端（2 模）")
    for r in h["theta_scan"]:
        print(f"     θ={r['theta_deg']:6.1f}°  路(a)全开放系统={r['p_coin_full_open_system']:.6e}"
              f"  路(b)有效效率={r['p_coin_effective_eff']:.6e}  理想={r['p_coin_ideal_no_loss']:.6e}")
    print(f"   跨 θ 网格两路最大差 |Δ|={h['cross_method_max_diff']:.2e}（须机器精度一致）")
    print(f"   50:50 可见度={h['hom_visibility_5050']:.6f} · "
          f"不可区分符合={h['p_coin_indistinguishable_5050']:.2e} · {h['scaling']}")

    report["mesh_loss"] = mesh_loss_section()
    m = report["mesh_loss"]
    print(f"③ {m['N']} 模 DFT mesh + 逐模损耗 η={m['eta_per_mode']}")
    print(f"   量子态保真度(损耗后 vs 理想) = {m['state_fidelity_vs_ideal']:.6f}"
          f" ≡ 闭式 η^N = {m['state_fidelity_closed_form_etaN']:.6f}")
    print(f"   理想 Top 输出: {m['top_ideal_outputs'][:3]}")

    report["link_budget"] = link_budget_section()
    b = report["link_budget"]
    print(f"④ 链路预算：η_eff={b['eta_eff']:.4f} · 符合率∝{b['coincidence_rate_scaling']:.4f} "
          f"· 源 g²(0)={b['source_g2_at_lambda']:.4f}")

    ok = (h["cross_method_max_diff"] < 1e-10
          and abs(h["hom_visibility_5050"] - 1.0) < 1e-10
          and h["p_coin_indistinguishable_5050"] < 1e-12
          and abs(m["state_fidelity_vs_ideal"] - m["state_fidelity_closed_form_etaN"]) < 1e-9)
    report["verdict"] = "PASS" if ok else "FAIL"
    print()
    print(f"链路判定：{report['verdict']}（跨θ两路一致 + 理想HOM符合=0 + 可见度=1 + 保真度≡η^N）")

    rep_path = os.path.join(OUT, "lda_q3b_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    svg_path = os.path.join(OUT, "lda_q3b_lossscan.svg")
    render_svg(report["source"]["scan"], svg_path)
    print(f"产出：{os.path.basename(rep_path)} · {os.path.basename(svg_path)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
