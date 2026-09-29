"""LDA-Q4b · 时间复用可编程酉演示（M4 延伸）——「时间复用能不能实现任意 N 模酉？」

承接 LDA-Q4（M4 规模对标）留下的挂起结论：「真路线是时间复用（省 507 dB）」。
本演示把那句口号放到**可构造 + 可判死**的标准下重测，回答：

  ❓ 时间复用架构能不能实现**任意** 216 模酉？若不能，它到底买到了什么？

三条由真实 API 驱动的结论（无硬编码结果）：
  ① 引理 L1   延迟环 = 模置换；非相邻对 (i,i+m) 由置换共轭寻址（逐位一致）。
  ② 结论 1    构造性通用性：**1 片物理 MZI** 的时间表重建任意酉到机器精度
              （N=4…128，DFT 与 Haar 随机酉各一遍）。
  ③ 结论 2/3  深度下界（参数计数）= ⌈N(N−1)/2 / ⌊N/2⌋⌉ ⇒ N 偶 N−1；
              **即便取这个对时间复用最有利的深度，每模损耗仍严格高于静态网格**
              ⇒ 时间复用买的是**元件数 O(N²)→O(1)**，**不买**深度/损耗；
              Borealis 能 216 模 @ 浅深度，靠的是**放弃通用性**（维度计数判死）。

🔴 红线：纯 numpy + 平台模块（零量子 SDK）；LLM 不进判决路径；数学恒等式作 golden；
   Borealis 数据为外部 A 级可溯源事实（Nature 606, 75-81 (2022)），仅引用不复算。

诚实边界：本演示是**架构-资源模型**（设计预算口径），非真机实测比对；
   与 Borealis 只比规模/架构/参数计数，不比数值（CV GBS vs DV 被动 LOQC）。
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_qeda import temporal_mesh as TMB            # noqa: E402
from lda_qeda import scale_bench as SBM              # noqa: E402

N_SWEEP = (4, 8, 16, 32, 64, 128)
N_TARGET = 216                       # 对标 Borealis 的模数
SEED = 20260929


def run() -> dict:
    # ① 引理 L1：非相邻对由延迟共轭寻址
    n_l, m_l, i_l, th_l, ph_l = 7, 3, 2, 0.7, 0.4
    direct = TMB.pair_rotation_unitary(n_l, i_l, i_l + m_l, th_l, ph_l)
    P = np.zeros((n_l, n_l), dtype=complex)        # 🔴 零阵起建（踩坑点）
    for k in range(n_l):
        P[(k + i_l) % n_l, k] = 1.0
    conj = P @ TMB.pair_rotation_unitary(n_l, 0, m_l, th_l, ph_l) @ P.conj().T
    lemma_l1 = {
        "n_modes": n_l, "stride_m": m_l, "target_pair": [i_l, i_l + m_l],
        "max_abs_diff": float(np.max(np.abs(direct - conj))),
        "ok": bool(float(np.max(np.abs(direct - conj))) < 1e-14),
    }

    # ② 构造性通用性：DFT + Haar 随机酉（各 6 个 N）
    dft_profiles = [TMB.temporal_schedule_profile(N, target="dft") for N in N_SWEEP]
    rnd_profiles = [TMB.temporal_schedule_profile(N, target="random", seed=N * 7 + 1)
                    for N in N_SWEEP]
    # 双精度可观测性：>128 模 Time 会上升，但本次只做「能不能通用」的可判事实
    worst_fid = min([p["fidelity"] for p in dft_profiles + rnd_profiles])

    # ③ 资源 / 下界 / 损耗（N=216）
    dmin = TMB.universality_depth_lower_bound(N_TARGET)
    static = TMB.static_mesh_resources(N_TARGET)
    tmux = TMB.temporal_mesh_resources(N_TARGET, dmin)
    verdict = TMB.temporal_mesh_verdict(N_TARGET)
    frontier = TMB.programmability_frontier(N_TARGET)

    # ④ Borealis 维度判死
    borealis = TMB.benchmark_against_borealis_temporal(N_TARGET)
    lattice = TMB.fixed_lattice_programmability(N_TARGET)

    # 判决：三件事都对 ⇒ PASS
    diag_ok = (lemma_l1["ok"]
               and all(p["unitary_ok"] and abs(p["fidelity"] - 1.0) < 1e-11
                       for p in dft_profiles + rnd_profiles)
               and all(p["depth_within_bounds"] for p in dft_profiles)
               and dmin == N_TARGET - 1
               and static["n_physical_mzi"] == 23220
               and tmux["n_physical_mzi"] == 1
               and verdict["loss_saving_strictly_negative"] is True
               and lattice["universal"] is False
               and borealis["mode_count_matches"] is True)
    verdict_str = "PASS" if diag_ok else "FAIL"

    return {
        "chip_family": "LDA-Q4b · 时间复用可编程酉（M4 延伸）",
        "platform_capability": "lda_qeda/temporal_mesh.py(D-121) 复用 lda_l2 Reck + D-120 规模律",
        "n_sweep": list(N_SWEEP),
        "n_target": N_TARGET,
        "lemma_l1_any_pair_addressing": lemma_l1,
        "constructive_universality": {
            "dft": [{"n_modes": p["n_modes"], "n_gates": p["n_gates"],
                     "n_gate_steps": p["n_gate_steps"],
                     "max_gates_per_step": p["max_gates_per_step"],
                     "fidelity": p["fidelity"], "unitary_ok": p["unitary_ok"],
                     "depth_lower_bound": p["depth_lower_bound"]} for p in dft_profiles],
            "random": [{"n_modes": p["n_modes"], "fidelity": p["fidelity"],
                        "unitary_ok": p["unitary_ok"]} for p in rnd_profiles],
            "worst_fidelity": float(worst_fid),
            "n_physical_mzi": 1,
        },
        "depth_lower_bound": {
            "n_modes": N_TARGET, "formula": "ceil(n_mzi / floor(N/2))",
            "value": int(dmin),
            "note": "参数计数下界（Clements 必要性定理 + 层容量 ⌊N/2⌋）；硬件无关。",
        },
        "construction_note": (
            "构造性时间表 = 平台 Reck 三角 op 序列（按光路逆序）+ 匹配贪心聚合。"
            "三角 Reck 的 op 集本质是**串行链**（同列相邻对共享模、顺序不可交换）"
            f"⇒ 朴素构造步数为 O(N²)（N=128 时 {dft_profiles[-1]['n_gate_steps']} 步）。"
            "本演示的**损耗判定不依赖构造深度**，而依赖参数计数下界（结论 2）："
            "任何合法通用时间表的深度都 ≥ 下界，故「不省损耗」的结论与调度器优劣无关。"),
        "resources": {"static": static, "temporal_best_case": tmux},
        "loss_verdict": verdict,
        "programmability_frontier": frontier,
        "borealis_dimension_verdict": {
            "lattice_3loops": lattice,
            "reported_params": SBM.BOREALIS_REF["programmable_parameters"],
            "reported_fraction": borealis["reported_params_fraction"],
            "verdict": "浅晶格可及参数 ≪ N² ⇒ 不可能实现任意 216 模酉（放弃通用性换浅深度）。",
        },
        "headline_findings": [
            "① 引理 L1：延迟环就是模置换；非相邻模对 (i,i+m) 由置换共轭寻址"
            "（实测逐位一致 max|Δ|=0）。",
            "★ 结论 1：时间复用**能**实现任意 N 模酉 —— 用 **1 片物理 MZI**，"
            f"时间表重建 DFT 与 Haar 随机酉到机器精度（最差 fid={worst_fid:.12f}，N=4…128）。",
            f"★ 结论 2：通用性深度下界（参数计数）= {dmin}（N=216）——"
            "任何通用时间表都不可能更浅；该下界与硬件细节无关。",
            "★ 结论 3（修正 M4 口号）：**即便取理论最优深度**，时间复用每模损耗 "
            f"{tmux['loss_per_mode_db']:.0f} dB 仍**严格高于**静态网格 "
            f"{static['loss_per_mode_db']:.0f} dB（多出 环/开关 损耗）。"
            "⇒ 时间复用买的是**元件数 O(N²)→O(1)**（可制造性 / 版图 / 对准），"
            "**不买**深度与损耗 ——「通用」与「省损」不可兼得。",
            "★ 结论 4：Borealis 216 模 @ 浅深度(3 环) 靠的是**放弃通用性**："
            f"可及参数 {lattice['reachable_params_model']}（报称 "
            f"{SBM.BOREALIS_REF['programmable_parameters']}）≪ N²=46656 ⇒ 维度计数判死。",
        ],
        "scale_verdict": (
            "M4 延伸结论：M4 的「真路线是时间复用」必须精确化为"
            "「真路线是**时间复用 + 浅电路（放弃通用性）**」。"
            "时间复用解决的是**可制造性墙**（元件数、耦合比越域、版图面积），"
            "而**损耗墙的本质是电路深度**，深度下界由参数计数钉死在 Ω(N) ——"
            "故通用酉在两架构下的每模损耗同阶，时间复用甚至略差。"),
        "honest_boundary": (
            "① 本演示是**架构-资源模型**（设计预算口径），非任一真机实测比对；"
            "② 每轮次损耗为设计预算（MZI + 环/延迟/开关），非实测 PDK（D5 外部依赖）；"
            "③ 与 Borealis 只比**规模/架构/参数计数**，不比数值"
            "（CV GBS vs DV 被动 LOQC）；④ 深度下界为参数计数下界（不问硬件细节），"
            "可达性由构造性时间表独立给出（实测深度 ≥ 下界）。"),
        "verdict": verdict_str,
    }


# ---------------------------------------------------------------------------
# 可视化：双面板 —— 左「深度-可编程性前沿」右「买什么 / 不买什么」
# ---------------------------------------------------------------------------
def _panel_a(parts, x0, y0, w, h, frontier, lattice):
    parts.append(f'<text x="{x0}" y="{y0 - 8}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">可编程性前沿：可及参数占比 vs 深度</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    rows = frontier["rows"]
    dmin = frontier["depth_lower_bound"]
    f_max = max(r["param_fraction_of_unitary"] for r in rows)
    # y 轴网格（占比 0…f_max）
    for k in range(5):
        fr = f_max * k / 4.0
        yy = y0 + h - (fr / f_max) * h if f_max > 0 else y0 + h
        parts.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x0 + w}" y2="{yy:.1f}" '
                     f'stroke="#e2e8f0" stroke-dasharray="2,3"/>')
        parts.append(f'<text x="{x0 + 3}" y="{yy - 2:.1f}" font-family="Arial" '
                     f'font-size="8" fill="#94a3b8">{fr * 100:.0f}%</text>')
    # x 轴：深度 1…dmin（线性）
    pts = []
    for r in rows:
        d = r["depth"]
        xx = x0 + 6 + (d / float(dmin)) * (w - 16)
        yy = y0 + h - (r["param_fraction_of_unitary"] / f_max) * h
        pts.append(f"{xx:.1f},{yy:.1f}")
        parts.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="2.5" fill="#2563eb"/>')
    parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#2563eb" '
                 f'stroke-width="2"/>')
    # 通用阈值竖线
    x_uni = x0 + 6 + (dmin / float(dmin)) * (w - 16)
    parts.append(f'<line x1="{x_uni:.1f}" y1="{y0}" x2="{x_uni:.1f}" y2="{y0 + h}" '
                 f'stroke="#16a34a" stroke-width="1.5" stroke-dasharray="4,3"/>')
    parts.append(f'<text x="{x_uni - 4:.1f}" y="{y0 + 12}" font-family="Arial" '
                 f'font-size="8.5" fill="#16a34a" text-anchor="end">通用 ⟺ D≥{dmin}</text>')
    # Borealis 点（深度 3）
    xb = x0 + 6 + (lattice["n_loops_depth"] / float(dmin)) * (w - 16)
    yb = y0 + h - (lattice["param_fraction"] / f_max) * h
    parts.append(f'<circle cx="{xb:.1f}" cy="{yb:.1f}" r="4" fill="#dc2626"/>')
    parts.append(f'<text x="{xb + 6:.1f}" y="{yb + 3:.1f}" font-family="Arial" '
                 f'font-size="8.5" fill="#dc2626">Borealis 3 环 '
                 f'({lattice["param_fraction"] * 100:.1f}%)</text>')
    parts.append(f'<text x="{x0 + w / 2:.0f}" y="{y0 + h + 26}" font-family="Arial" '
                 f'font-size="9" fill="#64748b" text-anchor="middle">时间表深度 D（1 → {dmin}）</text>')


def _panel_b(parts, x0, y0, w, h, static, tmux, verdict):
    parts.append(f'<text x="{x0}" y="{y0 - 8}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">买什么 / 不买什么（N=216）</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    # 左：元件数（对数条形）
    bx = x0 + 14
    bw = 58
    base_y = y0 + h - 34
    # 统一对数标度：1 … 23220
    lg_hi = math.log10(static["n_physical_mzi"])
    def _bh(v):
        if v <= 1.5:
            return 6.0
        return (math.log10(v) / lg_hi) * (h - 70)
    for (v, col, lab) in ((static["n_physical_mzi"], "#dc2626", "静态"),
                          (tmux["n_physical_mzi"], "#16a34a", "时间复用")):
        hh = _bh(v)
        parts.append(f'<rect x="{bx}" y="{base_y - hh:.1f}" width="{bw}" height="{hh:.1f}" '
                     f'fill="{col}" opacity="0.85" rx="2"/>')
        parts.append(f'<text x="{bx + bw / 2:.1f}" y="{base_y - hh - 4:.1f}" '
                     f'font-family="Arial" font-size="9" font-weight="bold" fill="{col}" '
                     f'text-anchor="middle">{v}</text>')
        parts.append(f'<text x="{bx + bw / 2:.1f}" y="{base_y + 12:.1f}" '
                     f'font-family="Arial" font-size="8.5" fill="#475569" '
                     f'text-anchor="middle">{lab}</text>')
        bx += bw + 22
    parts.append(f'<text x="{x0 + 14}" y="{y0 + 14}" font-family="Arial" font-size="9.5" '
                 f'font-weight="bold" fill="#0f172a">物理元件数（对数轴）</text>')
    parts.append(f'<text x="{x0 + 14}" y="{base_y + 28}" font-family="Arial" font-size="9" '
                 f'fill="#16a34a">省 {verdict["element_saving_factor"]:.0f}× ✅</text>')
    # 右：每模损耗（线性条形）
    bx2 = x0 + w / 2 + 14
    l_hi = max(static["loss_per_mode_db"], tmux["loss_per_mode_db"]) * 1.15
    def _lh(v):
        return (v / l_hi) * (h - 70)
    for (v, col, lab) in ((static["loss_per_mode_db"], "#16a34a", "静态"),
                          (tmux["loss_per_mode_db"], "#dc2626", "时间复用(最优深度)")):
        hh = _lh(v)
        parts.append(f'<rect x="{bx2}" y="{base_y - hh:.1f}" width="{bw}" height="{hh:.1f}" '
                     f'fill="{col}" opacity="0.85" rx="2"/>')
        parts.append(f'<text x="{bx2 + bw / 2:.1f}" y="{base_y - hh - 4:.1f}" '
                     f'font-family="Arial" font-size="9" font-weight="bold" fill="{col}" '
                     f'text-anchor="middle">{v:.0f} dB</text>')
        parts.append(f'<text x="{bx2 + bw / 2:.1f}" y="{base_y + 12:.1f}" '
                     f'font-family="Arial" font-size="8" fill="#475569" '
                     f'text-anchor="middle">{lab}</text>')
        bx2 += bw + 26
    parts.append(f'<text x="{x0 + w / 2 + 14}" y="{y0 + 14}" font-family="Arial" '
                 f'font-size="9.5" font-weight="bold" fill="#0f172a">每模插损（线性轴）</text>')
    parts.append(f'<text x="{x0 + w / 2 + 14}" y="{base_y + 28}" font-family="Arial" '
                 f'font-size="9" fill="#dc2626">不省，反 +'
                 f'{-verdict["loss_saved_db_by_time_multiplexing"]:.0f} dB ❌</text>')


def render_svg(rep: dict) -> str:
    cu = rep["constructive_universality"]
    static = rep["resources"]["static"]
    tmux = rep["resources"]["temporal_best_case"]
    lat = rep["borealis_dimension_verdict"]["lattice_3loops"]
    vd = rep["loss_verdict"]
    vcol = "#16a34a" if rep["verdict"] == "PASS" else "#dc2626"
    dmin = rep["depth_lower_bound"]["value"]

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 540" width="680" height="540">',
        '<rect width="680" height="540" fill="#ffffff"/>',
        '<text x="34" y="30" font-family="Arial" font-size="18" font-weight="bold" '
        'fill="#0f172a">LDA-Q4b · 时间复用可编程酉（M4 延伸）</text>',
        '<text x="34" y="48" font-family="Arial" font-size="10.5" fill="#64748b">'
        '1 片物理 MZI 重现任意 N 模酉 · 深度下界=参数计数 · '
        '「买元件数，不买损耗」· 纯 numpy · 公式作 golden</text>',
        '<line x1="34" y1="58" x2="646" y2="58" stroke="#e2e8f0"/>',
    ]
    _panel_a(parts, 34, 96, 290, 186, rep["programmability_frontier"], lat)
    _panel_b(parts, 356, 96, 290, 186, static, tmux, vd)

    parts += [
        '<line x1="34" y1="342" x2="646" y2="342" stroke="#e2e8f0"/>',
        '<text x="34" y="362" font-family="Arial" font-size="12" font-weight="bold" '
        'fill="#0f172a">构造性通用性（实测：时间表重建 ≡ 目标酉）</text>',
    ]
    cols = [(34, "N"), (86, "N(N−1)/2"), (176, "时间表步数"), (266, "最大同步门"), (346, "保真度"), (466, "下界")]
    for cx, txt in cols:
        parts.append(f'<text x="{cx}" y="382" font-family="Arial" font-size="9.5" '
                     f'font-weight="bold" fill="#475569">{txt}</text>')
    for i, p in enumerate(cu["dft"]):
        y = 400 + i * 16
        parts.append(f'<text x="34" y="{y}" font-family="Arial" font-size="9.5" fill="#0f172a">{p["n_modes"]}</text>')
        parts.append(f'<text x="86" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["n_gates"]}</text>')
        parts.append(f'<text x="176" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["n_gate_steps"]}</text>')
        parts.append(f'<text x="266" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["max_gates_per_step"]}</text>')
        parts.append(f'<text x="346" y="{y}" font-family="Arial" font-size="9.5" font-weight="bold" fill="#16a34a">{p["fidelity"]:.12f}</text>')
        parts.append(f'<text x="466" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["depth_lower_bound"]}</text>')

    parts += [
        f'<text x="34" y="508" font-family="Arial" font-size="9.5" fill="#475569">'
        f'引理 L1 任意对寻址 max|Δ|={rep["lemma_l1_any_pair_addressing"]["max_abs_diff"]:.0e} · '
        f'深度下界 {dmin}（N=216）· 静态 {static["n_physical_mzi"]} 元件/'
        f'{static["loss_per_mode_db"]:.0f} dB vs 时间复用 1 元件/'
        f'{tmux["loss_per_mode_db"]:.0f} dB · Borealis 3 环可及 {lat["reachable_params_model"]}'
        f'≪N²</text>',
        '<text x="34" y="522" font-family="Arial" font-size="9" fill="#94a3b8">'
        'Borealis 216 模（Nature 606,75-81(2022)，外部 A 级事实，仅引用不复算）· '
        '物理形态不同，只比规模/架构/参数计数 · 损耗为设计预算口径</text>',
        f'<text x="34" y="538" font-family="Arial" font-size="11" font-weight="bold" fill="{vcol}">'
        f'M4 延伸判决：{rep["verdict"]}（构造性通用性成立 · 通用目标下不省损）</text>',
        '</svg>',
    ]
    return "\n".join(parts)


def main() -> int:
    rep = run()
    with open(os.path.join(_HERE, "lda_q4b_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(_HERE, "lda_q4b_frontier.svg"), "w", encoding="utf-8") as f:
        f.write(render_svg(rep))

    print("=" * 84)
    print("LDA-Q4b · 时间复用可编程酉（M4 延伸）")
    print("=" * 84)
    print(f"① 引理 L1 任意对寻址：max|Δ|={rep['lemma_l1_any_pair_addressing']['max_abs_diff']:.2e}"
          f" ⇒ {rep['lemma_l1_any_pair_addressing']['ok']}")
    for p in rep["constructive_universality"]["dft"]:
        print(f"   N={p['n_modes']:4d}  门数={p['n_gates']:5d}  时间表步数={p['n_gate_steps']:5d}  "
              f"最大同步门={p['max_gates_per_step']:3d}  fid={p['fidelity']:.12f}  "
              f"下界={p['depth_lower_bound']}")
    r1 = rep["constructive_universality"]["random"][-1]
    print(f"② 构造性通用性：DFT 与 Haar 随机酉最差 fid="
          f"{rep['constructive_universality']['worst_fidelity']:.12f}"
          f"（随机 N={r1['n_modes']} fid={r1['fidelity']:.12f}）· 物理 MZI 数=1")
    st = rep["resources"]["static"]
    tm = rep["resources"]["temporal_best_case"]
    print(f"③ 资源：静态 {st['n_physical_mzi']} 片/{st['loss_per_mode_db']:.0f} dB  vs  "
          f"时间复用 {tm['n_physical_mzi']} 片/{tm['loss_per_mode_db']:.0f} dB"
          f"（深度取最优 {tm['depth']}）")
    print(f"   深度下界（参数计数）= {rep['depth_lower_bound']['value']}（N=216）；"
          f"省元件 {rep['loss_verdict']['element_saving_factor']:.0f}×；"
          f"损耗省 {rep['loss_verdict']['loss_saved_db_by_time_multiplexing']:.0f} dB")
    bv = rep["borealis_dimension_verdict"]
    print(f"④ Borealis 维度判死：3 环可及 {bv['lattice_3loops']['reachable_params_model']}"
          f"（报称 {bv['reported_params']}，占 N² 的 {bv['reported_fraction'] * 100:.1f}%）"
          f"⇒ 通用={bv['lattice_3loops']['universal']}")
    print()
    print(f"M4 延伸判决：{rep['verdict']}")
    print("产物：lda_q4b_report.json · lda_q4b_frontier.svg")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
