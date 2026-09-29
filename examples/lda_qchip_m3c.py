"""LDA-Q3c · 全链路量子签核演示（M3 收口）——源 → 网格 → 损耗 → 探测 → 标定 → DRC/LVS → 基准。

把 M3 补齐的全部量子光子能力**串成一条签核链路**，回答一个问题：
「这颗光量子芯片，从光子源到最后基准分，整条链能不能签核通过？」

链路（每段都由对应模块的真实 API 驱动，无硬编码结果）：
  ① 源      D-114  SPDC 预告单光子 → 纯度 g²(0)=2λ²、不可区分度（HOM 可见度 μ）
  ② 网格    lda_l2 Reck 三角 mesh（N=4 DFT）→ 本征酉保真度
  ③ 损耗    D-116  片上逐模透射率 η_chip → 连通链路的透镜预算
  ④ 探测    D-115  SNSPD 效率 η_det（效率≡损耗桥）
  ⑤ 标定    D-117  逐相位三点法闭环 + 散粒噪声极限 σ_cal=1/(𝒱√N_ph)
  ⑥ DRC     D-118  9 条量子设计规则（含上面各段的量子参数）
  ⑦ LVS     D-118  酉层版图-原理图签核（量化 12bit + 标定残差污染）
  ⑧ 基准    D-119  玻色采样正确性 + HOM 可见度 + 过程保真度 + 综合对标分

🔴 红线：纯 numpy + 平台模块（零量子 SDK）；LLM 不进判决路径；闭式物理律作 golden；
   综合对标分是**平台自定义**量（非国际公认指标），仅内部追踪。

诚实边界：损耗/效率为设计预算口径，非实测 PDK（D5 外部依赖）；标定读数为合成数值。
"""
from __future__ import annotations

import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_l2 import mzi_mesh_matmul as MMM            # noqa: E402
from lda_qeda import loqc_states as LS               # noqa: E402
from lda_qeda import photon_sources as PS            # noqa: E402
from lda_qeda import detectors as DT                 # noqa: E402
from lda_qeda import open_system as OSYS             # noqa: E402
from lda_qeda import calibration as CAL              # noqa: E402
from lda_qeda import quantum_drc_lvs as QDR          # noqa: E402
from lda_qeda import quantum_benchmark as QBM        # noqa: E402

# ── 设计预算参数（可调；全部标注为设计值，非实测）─────────────────────────
N_MODES = 4
LAMBDA_SRC = 0.20          # SPDC 压缩参数 λ（预告源）
HOM_VISIBILITY = 0.94      # 源光子不可区分度 μ（HOM 可见度）
ETA_CHIP = 0.85            # 片上逐模透射率（= 链路损耗预算）
ETA_DET = 0.90             # SNSPD 探测效率
N_PHOTONS_CAL = 2.0e6      # 标定光子预算（决定散粒噪声极限）
PHASE_BITS = 12            # 数字相移器比特数
FID_THRESHOLD = 0.999      # LVS 酉保真度签核阈值
SEED = 20260929


def run() -> dict:
    # ① 源（D-114）
    g2 = PS.heralded_g2_onoff(LAMBDA_SRC)          # = 2λ²（on/off 预告态 g²(0)）
    wcs_p2 = PS.wcs_multiphoton_prob(0.05)         # 参考：弱相干多光子污染

    # ② 网格（lda_l2）
    U_target = MMM.dft_matrix(N_MODES)
    ops, D = MMM.reck_triangular_mesh(U_target)
    U_mesh = MMM.assemble_triangular_mesh(ops, D, N_MODES)
    fid_mesh_ideal = MMM.unitary_fidelity(U_mesh, U_target)

    # ③ 链路损耗 / ④ 探测（D-115 效率≡损耗桥）
    eta_eff = ETA_CHIP * ETA_DET
    link_loss_db = -10.0 * math.log10(eta_eff)
    mesh_loss_db = MMM.mesh_cascade_loss_db(len(ops), n_crossings=0)
    # D-115 真实调用：单光子点击概率 = η_det（on/off 闭式）；链路后残留真空 = (1−η_chip)
    det_click_p1 = DT.click_prob_closed_form(ETA_DET, 1, 0.0)
    link_residual_vacuum = DT.loss_then_ideal_no_click(1, ETA_CHIP)

    # ⑤ 标定闭环（D-117）：逐相位闭环 + 散粒噪声极限
    per_op_resid = []
    for (c, p, th, ph) in ops:
        r = CAL.calibrate_phase(ph, hardware_slope=1.0, vis=HOM_VISIBILITY)
        per_op_resid.append(abs(r["residual_rad"]))
    calib_residual_rad = CAL.shot_noise_phase_uncertainty(HOM_VISIBILITY, N_PHOTONS_CAL)
    # 标定精度 → 酉保真度惩罚（二次律，用标定模块的 MC 点）
    fid_pen_cal = 1.0 - CAL.mzi_fidelity_vs_phase_error(
        math.pi / 2.0, 0.7, calib_residual_rad, n_samples=3000)

    # ⑥ 量子 DRC（D-118）
    design = {"ops": ops, "N": N_MODES, "n_crossings": 0,
              "source_g2": g2, "hom_visibility": HOM_VISIBILITY,
              "detector_eta": ETA_DET, "calib_residual_rad": calib_residual_rad,
              "phase_bits": PHASE_BITS}
    drc = QDR.run_quantum_drc(design)

    # ⑦ 量子 LVS（D-118）：酉层签核（量化 + 标定残差污染）
    lvs = QDR.quantum_lvs_signoff(U_target, ops, D, N_MODES, phase_bits=PHASE_BITS,
                                  calib_sigma=calib_residual_rad, seed=SEED)

    # ⑧ 量子基准（D-119）
    bs = QBM.boson_sampling_benchmark(U_target, (1, 1, 0, 0))
    hom_v = LS.hom_visibility(math.pi / 4.0)
    ef = OSYS.entanglement_fidelity_closed_form(ETA_CHIP, N_MODES)
    pf = QBM.process_fidelity_benchmark(ef, lvs["fidelity"])
    score = QBM.composite_quantum_score(n_modes=N_MODES, n_photons=2,
                                        fidelity=lvs["fidelity"], source_g2=g2,
                                        hom_visibility=HOM_VISIBILITY, detector_eta=ETA_DET)

    signoff = (drc["verdict"] == "ACCEPT" and lvs["verdict"] == "ACCEPT"
               and score["score"] > 0.0)

    rep = {
        "chip": "LDA-Q3c",
        "identity": "4 模可编程 MZI 干涉仪（LOQC 通用处理器）· 全链路量子签核",
        "platform_capability": (
            "D-114 源 + lda_l2 网格 + D-116 损耗 + D-115 探测 + D-117 标定 + "
            "D-118 DRC/LVS + D-119 基准"),
        "sources": {
            "lambda": LAMBDA_SRC,
            "g2_onoff": float(g2),
            "hom_visibility": HOM_VISIBILITY,
            "wcs_multiphoton_ref": float(wcs_p2),
        },
        "mesh": {
            "N": N_MODES, "n_mzi": len(ops),
            "unitary_fidelity_ideal": float(fid_mesh_ideal),
            "cascade_loss_db": float(mesh_loss_db),
        },
        "link": {
            "eta_chip": ETA_CHIP, "eta_det": ETA_DET, "eta_eff": float(eta_eff),
            "link_loss_db": float(link_loss_db),
        },
        "detection": {
            "detector_click_prob_1photon": float(det_click_p1),
            "link_residual_vacuum_1photon": float(link_residual_vacuum),
            "bridge": "探测器效率 ≡ 损耗透射率（D-115 效率≡损耗桥）",
        },
        "calibration": {
            "n_photons": N_PHOTONS_CAL,
            "closed_loop_residual_max_rad": float(max(per_op_resid)),
            "shot_noise_limit_rad": float(calib_residual_rad),
            "fidelity_penalty": float(fid_pen_cal),
        },
        "quantum_drc": drc,
        "quantum_lvs": lvs,
        "benchmark": {
            "boson_sampling_norm": float(bs["norm"]),
            "boson_sampling_entropy_bits": float(bs["entropy_bits"]),
            "hom_visibility_ideal": float(hom_v),
            "entanglement_fidelity": float(ef),
            "process_fidelity_product": float(pf["product"]),
            "composite_score": score,
        },
        "verdict": "PASS" if signoff else "FAIL",
        "honest_note": (
            "损耗/效率为设计预算口径（非实测 PDK，属 D5 外部依赖）；标定读数为合成数值；"
            "综合对标分为平台自定义量（非国际公认指标），仅作内部趋势追踪；"
            "全链路无量子 SDK，纯 numpy + 平台模块。"),
    }
    return rep


# ── 可视化：签核链路图 ────────────────────────────────────────────────────
def _svg_bar(x, y, w, h, frac, label, val, color):
    frac = max(0.0, min(1.0, frac))
    return (
        f'<text x="{x}" y="{y - 4}" font-family="Arial" font-size="11" fill="#334155">{label}</text>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#e2e8f0" rx="3"/>'
        f'<rect x="{x}" y="{y}" width="{w * frac:.1f}" height="{h}" fill="{color}" rx="3"/>'
        f'<text x="{x + w + 8}" y="{y + h - 3}" font-family="Arial" font-size="11" '
        f'fill="#0f172a">{val}</text>')


def render_svg(rep: dict) -> str:
    drc = rep["quantum_drc"]
    rules = ["QDR-PHASE-DOMAIN", "QDR-COUPLING-RANGE", "QDR-PHASE-RESOLUTION",
             "QDR-CROSSING-BUDGET", "QDR-LOSS-BUDGET", "QDR-SOURCE-PURITY",
             "QDR-INDISTINGUISHABILITY", "QDR-DETECTOR-EFFICIENCY", "QDR-CALIB-RESIDUAL"]
    bad = {v["rule"] for v in drc["violations"]}
    cells = []
    for i, r in enumerate(rules):
        cx = 40 + (i % 3) * 200
        cy = 320 + (i // 3) * 34
        okrule = r not in bad
        col = "#16a34a" if okrule else "#dc2626"
        mark = "PASS" if okrule else "FAIL"
        cells.append(f'<rect x="{cx}" y="{cy}" width="188" height="24" fill="#f1f5f9" rx="3"/>'
                     f'<text x="{cx + 6}" y="{cy + 16}" font-family="Arial" font-size="10" '
                     f'fill="#334155">{r}</text>'
                     f'<text x="{cx + 150}" y="{cy + 16}" font-family="Arial" font-size="10" '
                     f'font-weight="bold" fill="{col}">{mark}</text>')

    s = rep["benchmark"]["composite_score"]
    lvs = rep["quantum_lvs"]
    verdict_col = "#16a34a" if rep["verdict"] == "PASS" else "#dc2626"

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 500" width="680" height="500">',
        '<rect width="680" height="500" fill="#ffffff"/>',
        '<text x="40" y="34" font-family="Arial" font-size="19" font-weight="bold" '
        'fill="#0f172a">LDA-Q3c · 全链路量子签核（源→网格→损耗→探测→标定→DRC/LVS→基准）</text>',
        '<text x="40" y="54" font-family="Arial" font-size="11" fill="#64748b">'
        '4 模可编程 MZI 干涉仪 · 纯 numpy + 平台模块 · 零量子 SDK · LLM 不进判决路径</text>',
        '<line x1="40" y1="66" x2="640" y2="66" stroke="#e2e8f0"/>',
        '<text x="40" y="92" font-family="Arial" font-size="13" font-weight="bold" fill="#0f172a">'
        '链路指标（归一化）</text>',
    ]
    # 顶部指标条
    items = [
        ("源纯度 1−g²(0)", 1.0 - rep["sources"]["g2_onoff"], f'{1 - rep["sources"]["g2_onoff"]:.3f}', "#2563eb"),
        ("网格酉保真度", rep["mesh"]["unitary_fidelity_ideal"], f'{rep["mesh"]["unitary_fidelity_ideal"]:.4f}', "#2563eb"),
        ("链路效率 η_eff", rep["link"]["eta_eff"], f'{rep["link"]["eta_eff"]:.3f}', "#2563eb"),
        ("标定精度 1−σ", 1.0 - rep["calibration"]["shot_noise_limit_rad"] * 10,
         f'{rep["calibration"]["shot_noise_limit_rad"]:.2e} rad', "#2563eb"),
        ("LVS 酉保真度", lvs["fidelity"], f'{lvs["fidelity"]:.5f}', "#2563eb"),
    ]
    for i, (lab, frac, val, col) in enumerate(items):
        parts.append(_svg_bar(40, 108 + i * 34, 420, 18, frac, lab, val, col))

    parts += [
        '<line x1="40" y1="296" x2="640" y2="296" stroke="#e2e8f0"/>',
        '<text x="40" y="312" font-family="Arial" font-size="13" font-weight="bold" fill="#0f172a">'
        f'量子 DRC 九规则（{drc["verdict"]}）</text>',
    ]
    parts += cells

    parts += [
        '<line x1="40" y1="436" x2="640" y2="436" stroke="#e2e8f0"/>',
        f'<text x="40" y="466" font-family="Arial" font-size="15" font-weight="bold" '
        f'fill="{verdict_col}">全链路判决：{rep["verdict"]}</text>',
        f'<text x="250" y="466" font-family="Arial" font-size="12" fill="#334155">'
        f'LVS {lvs["verdict"]} · 综合对标分 {s["score"]:.2f}</text>',
        '<text x="40" y="486" font-family="Arial" font-size="10" fill="#94a3b8">'
        '综合对标分为平台自定义量（非国际公认指标）；损耗/效率为设计预算口径，非实测 PDK。</text>',
        '</svg>',
    ]
    return "\n".join(parts)


def main() -> int:
    rep = run()
    out_dir = _HERE
    with open(os.path.join(out_dir, "lda_q3c_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "lda_q3c_signoff.svg"), "w", encoding="utf-8") as f:
        f.write(render_svg(rep))

    print("=" * 78)
    print("LDA-Q3c · 全链路量子签核")
    print("=" * 78)
    print(f"① 源    g²(0)={rep['sources']['g2_onoff']:.4f}(on/off 预告) "
          f"HOM V={rep['sources']['hom_visibility']}")
    print(f"② 网格  N={rep['mesh']['N']} n_mzi={rep['mesh']['n_mzi']} "
          f"酉保真度={rep['mesh']['unitary_fidelity_ideal']:.6f} "
          f"级联损耗={rep['mesh']['cascade_loss_db']:.2f} dB")
    print(f"③④链路 η_chip={rep['link']['eta_chip']} ×η_det={rep['link']['eta_det']} "
          f"=η_eff={rep['link']['eta_eff']:.4f}（{rep['link']['link_loss_db']:.2f} dB）")
    print(f"⑤ 标定  闭环残差≤{rep['calibration']['closed_loop_residual_max_rad']:.1e} "
          f"散粒极限 σ={rep['calibration']['shot_noise_limit_rad']:.2e} rad")
    print(f"⑥ DRC   {rep['quantum_drc']['verdict']}（{rep['quantum_drc']['n_rules']} 规则，"
          f"{len(rep['quantum_drc']['violations'])} 违规）")
    print(f"⑦ LVS   {rep['quantum_lvs']['verdict']} fid={rep['quantum_lvs']['fidelity']:.6f}")
    b = rep["benchmark"]
    print(f"⑧ 基准  玻色采样归一={b['boson_sampling_norm']:.6f} "
          f"HOM V={b['hom_visibility_ideal']:.3f} 综合分={b['composite_score']['score']:.2f}")
    print()
    print(f"全链路判决：{rep['verdict']}")
    print("产物：lda_q3c_report.json · lda_q3c_signoff.svg")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
