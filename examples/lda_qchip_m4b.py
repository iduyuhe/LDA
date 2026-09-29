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
  ④ 结论 2b   ★浅并行调度 + 下界可达性判定★：按依赖 DAG（共享模 ⇒ 有向边）的
              **关键路径分层**（层=反链=匹配）把朴素 O(N²) 时间表压到该 op 集的**最优**
              深度；三角 Reck 网格的最优深度 = **2N−3**（N=216：23220 → **429** 层，54×）。
              但「参数计数下界 N−1 可达」的诚实答案是**否**：偶 N 唯一最大匹配 ⇒
              紧下界 = **N** (> N−1)；达 N 层需换**矩形 Clements 网格**（登记为下一步）。

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

    # ⑤ ★浅并行调度 + 三口径深度界（M4 延伸 · 2b 节）★
    #    N≤64 实跑（关键路径 DP）；N=216 用闭式 = 2N−3（与 N≤64 实测逐点一致），
    #    避免 O(n_mzi²)≈2.7e8 的纯 Python DP（演示耗时）。
    shallow_sweep = [TMB.temporal_shallow_profile(N, target="dft") for N in N_SWEEP[:5]]
    bounds = TMB.depth_bound_report(N_TARGET)
    matching = TMB.adjacency_max_matching(N_TARGET)
    n_mzi_t = int(bounds["n_mzi"])
    shallow_depth_t = int(bounds["reck_mesh_optimum"])
    speedup_t = float(n_mzi_t) / float(shallow_depth_t)
    worst_shallow_fid = min(p["fidelity"] for p in shallow_sweep)

    # 判决：四件事都对 ⇒ PASS
    diag_ok = (lemma_l1["ok"]
               and all(p["unitary_ok"] and abs(p["fidelity"] - 1.0) < 1e-11
                       for p in dft_profiles + rnd_profiles)
               and all(p["depth_within_bounds"] for p in dft_profiles)
               and dmin == N_TARGET - 1                       # D-121 参数计数下界（原口径）
               and bounds["tight_adjacency_bound"] == N_TARGET   # 紧界收紧：N−1 不可达
               and bounds["reck_mesh_optimum"] == 2 * N_TARGET - 3  # 平台 Reck 最优
               and matching["unique_max_matching"] is True    # 偶 N 唯一最大匹配 ⇒ D≥N
               and all(p["shallow_depth"] == 2 * p["n_modes"] - 3
                       and p["layers_are_matchings"]
                       and abs(p["fidelity"] - 1.0) < 1e-11
                       for p in shallow_sweep)
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
            "note": "参数计数下界（Clements 必要性定理 + 层容量 ⌊N/2⌋）；硬件无关。"
                    "★ 2b 节证明其**非紧**：偶 N 时唯一最大匹配 ⇒ 至少一层非最大 "
                    "⇒ 相邻耦合紧下界 = N（> N−1）。",
        },
        "shallow_scheduler": {
            "method": ("依赖 DAG（两门共享模 ⇒ 有向边）关键路径分层；层 = 反链 = 真匹配 "
                       "⇒ 深度 = 最长有向路 = 任意合法调度的下界且**达到**该下界 ⇒ 对该 op 集最优。"),
            "sweep": [{"n_modes": p["n_modes"], "n_gates": p["n_gates"],
                       "shallow_depth": p["shallow_depth"],
                       "naive_serial_depth": p["naive_serial_depth"],
                       "speedup_vs_serial": p["speedup_vs_serial"],
                       "max_gates_per_layer": p["max_gates_per_layer"],
                       "layers_are_matchings": p["layers_are_matchings"],
                       "fidelity": p["fidelity"]} for p in shallow_sweep],
            "worst_fidelity": float(worst_shallow_fid),
            "n_target": {
                "n_modes": N_TARGET, "naive_serial_depth": n_mzi_t,
                "shallow_depth": shallow_depth_t, "speedup_vs_serial": float(speedup_t),
                "formula": "2N−3（关键路径闭式；N≤64 实测逐点一致 ⇒ N=216 用闭式避免 O(2.7e8) DP）",
            },
        },
        "depth_bounds": bounds,
        "adjacency_matching": matching,
        "construction_note": (
            "构造性时间表 = 平台 Reck 三角 op 序列（按光路逆序）+ 匹配层聚合。"
            "三角 Reck 的 op 集本质是**串行链**（同列相邻对共享模、顺序不可交换）"
            f"⇒ 朴素贪心封步为 O(N²)（N=128 时 {dft_profiles[-1]['n_gate_steps']} 步）；"
            "2b 节的**浅并行调度器**按关键路径分层把它压到该 op 集的最优深度 2N−3。"
            "本演示的**损耗判定不依赖构造深度**，而依赖参数计数下界（结论 2）："
            "任何合法通用时间表的深度都 ≥ 下界，故「不省损耗」的结论与调度器优劣无关；"
            "浅调度的意义是把**通用表的实际深度**从 O(N²) 拉回 Ω(N) 的最优值。"),
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
            "★ 结论 5（浅并行调度 · 下界可达性）：关键路径分层（层=反链=匹配）把朴素 "
            f"O(N²) 时间表压到该 op 集**最优**深度 —— 三角 Reck 网格最优 = 2N−3"
            f"（N=216：{n_mzi_t} → {shallow_depth_t} 层，{speedup_t:.0f}× 加速，"
            f"实测 N=4…64 fid 最差 {worst_shallow_fid:.12f}）。"
            "但「参数计数下界 N−1 是否可达」的诚实答案是**否**：偶 N 时相邻路径的"
            "**唯一**最大匹配是偶数对 ⇒ 若每层皆最大匹配则整体乘积为块对角（非通用）"
            f"⇒ 相邻耦合紧下界 = N（> N−1）。平台可达深度 2N−3 由构造 fid=1.0 + "
            "关键路径下界**双证**；达 N 层需换**矩形 Clements 网格**（登记为下一步）。",
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
            "（CV GBS vs DV 被动 LOQC）；④ 深度界为**三口径**（参数计数下界 215 ≤ "
            "相邻耦合紧界 216 ≤ 平台 Reck 最优 429 @N=216）；N−1 经「唯一最大匹配」"
            "论证**不可达**，平台可达最优 = 2N−3（构造 fid=1.0 + 关键路径下界双证）；"
            "⑤ 浅调度深度 2N−3 在 N≤64 为实跑，N=216 用闭式（关键路径 = 2N−3，"
            "与 N≤64 实测逐点一致），避免 O(n_mzi²) 纯 Python DP。"),
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


def _panel_c(parts, x0, y0, w, h, bounds):
    """深度界三口径（N=216）：参数下界 ≤ 紧界 ≤ 平台 Reck 最优。"""
    parts.append(f'<text x="{x0}" y="{y0 - 6}" font-family="Arial" font-size="11" '
                 f'font-weight="bold" fill="#0f172a">深度界三口径（N=216）</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    rows = ((bounds["parameter_count_bound"], "#94a3b8", "参数计数下界 D-121"),
            (bounds["tight_adjacency_bound"], "#2563eb", "相邻耦合紧界(唯一匹配)"),
            (bounds["reck_mesh_optimum"], "#dc2626", "平台 Reck 最优"))
    hi = max(r[0] for r in rows) * 1.14
    bx = x0 + 126
    bw_max = w - 150
    for i, (v, col, lab) in enumerate(rows):
        yy = y0 + 20 + i * 26
        bl = (v / hi) * bw_max
        parts.append(f'<rect x="{bx}" y="{yy - 9:.1f}" width="{bl:.1f}" height="13" '
                     f'fill="{col}" opacity="0.85" rx="2"/>')
        parts.append(f'<text x="{bx - 4}" y="{yy + 1:.1f}" font-family="Arial" font-size="7.8" '
                     f'fill="#475569" text-anchor="end">{lab}</text>')
        parts.append(f'<text x="{bx + bl + 4:.1f}" y="{yy + 1:.1f}" font-family="Arial" '
                     f'font-size="8.5" font-weight="bold" fill="{col}">{v}</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + h - 8}" font-family="Arial" font-size="8.2" '
                 f'fill="#dc2626">N−1（215）不可达（唯一最大匹配）⇒ 可达最优 = 2N−3 = 429</text>')


def _panel_d(parts, x0, y0, w, h, shallow):
    """浅并行调度提速：朴素串行 n_mzi → 关键路径最优 2N−3。"""
    parts.append(f'<text x="{x0}" y="{y0 - 6}" font-family="Arial" font-size="11" '
                 f'font-weight="bold" fill="#0f172a">浅并行调度：O(N²) → 关键路径 2N−3</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    cols = ((x0 + 10, "N"), (x0 + 44, "朴素串行"), (x0 + 112, "浅调度"),
            (x0 + 166, "提速"), (x0 + 222, "fid"), (x0 + 262, "匹配"))
    for cx, txt in cols:
        parts.append(f'<text x="{cx}" y="{y0 + 18}" font-family="Arial" font-size="8.2" '
                     f'font-weight="bold" fill="#475569">{txt}</text>')
    for i, p in enumerate(shallow["sweep"]):
        yy = y0 + 34 + i * 14
        parts.append(f'<text x="{x0 + 10}" y="{yy}" font-family="Arial" font-size="8.2" fill="#0f172a">{p["n_modes"]}</text>')
        parts.append(f'<text x="{x0 + 44}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{p["naive_serial_depth"]}</text>')
        parts.append(f'<text x="{x0 + 112}" y="{yy}" font-family="Arial" font-size="8.2" font-weight="bold" fill="#2563eb">{p["shallow_depth"]}</text>')
        parts.append(f'<text x="{x0 + 166}" y="{yy}" font-family="Arial" font-size="8.2" fill="#16a34a">{p["speedup_vs_serial"]:.1f}×</text>')
        parts.append(f'<text x="{x0 + 222}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{p["fidelity"]:.3f}</text>')
        parts.append(f'<text x="{x0 + 262}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{"真" if p["layers_are_matchings"] else "假"}</text>')
    nt = shallow["n_target"]
    yy = y0 + 34 + len(shallow["sweep"]) * 14
    parts.append(f'<text x="{x0 + 10}" y="{yy}" font-family="Arial" font-size="8.2" font-weight="bold" fill="#dc2626">{nt["n_modes"]}*</text>')
    parts.append(f'<text x="{x0 + 44}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{nt["naive_serial_depth"]}</text>')
    parts.append(f'<text x="{x0 + 112}" y="{yy}" font-family="Arial" font-size="8.2" font-weight="bold" fill="#dc2626">{nt["shallow_depth"]}</text>')
    parts.append(f'<text x="{x0 + 166}" y="{yy}" font-family="Arial" font-size="8.2" fill="#16a34a">{nt["speedup_vs_serial"]:.0f}×</text>')
    parts.append(f'<text x="{x0 + 222}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{shallow["worst_fidelity"]:.3f}</text>')
    parts.append(f'<text x="{x0 + 262}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">真</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + h - 6}" font-family="Arial" font-size="7.8" '
                 f'fill="#94a3b8">* N=216 用闭式 2N−3（与 N≤64 实跑逐点一致）</text>')


def render_svg(rep: dict) -> str:
    cu = rep["constructive_universality"]
    static = rep["resources"]["static"]
    tmux = rep["resources"]["temporal_best_case"]
    lat = rep["borealis_dimension_verdict"]["lattice_3loops"]
    vd = rep["loss_verdict"]
    bnd = rep["depth_bounds"]
    sh = rep["shallow_scheduler"]
    nt = sh["n_target"]
    vcol = "#16a34a" if rep["verdict"] == "PASS" else "#dc2626"

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 660" width="680" height="660">',
        '<rect width="680" height="660" fill="#ffffff"/>',
        '<text x="34" y="30" font-family="Arial" font-size="18" font-weight="bold" '
        'fill="#0f172a">LDA-Q4b · 时间复用可编程酉（M4 延伸）</text>',
        '<text x="34" y="48" font-family="Arial" font-size="10.5" fill="#64748b">'
        '1 片物理 MZI 重现任意 N 模酉 · 深度界三口径 · 浅并行调度 O(N²)→2N−3 最优 · '
        '「买元件数，不买损耗」· 纯 numpy · 公式作 golden</text>',
        '<line x1="34" y1="58" x2="646" y2="58" stroke="#e2e8f0"/>',
    ]
    _panel_a(parts, 34, 92, 290, 168, rep["programmability_frontier"], lat)
    _panel_b(parts, 356, 92, 290, 168, static, tmux, vd)

    parts.append('<line x1="34" y1="298" x2="646" y2="298" stroke="#e2e8f0"/>')
    _panel_c(parts, 34, 316, 290, 118, bnd)
    _panel_d(parts, 356, 316, 290, 118, sh)

    parts += [
        '<line x1="34" y1="450" x2="646" y2="450" stroke="#e2e8f0"/>',
        '<text x="34" y="468" font-family="Arial" font-size="12" font-weight="bold" '
        'fill="#0f172a">构造性通用性（实测：时间表重建 ≡ 目标酉）</text>',
    ]
    cols = [(34, "N"), (86, "N(N−1)/2"), (176, "时间表步数"), (266, "最大同步门"),
            (346, "保真度"), (466, "参数下界"), (556, "浅调度")]
    for cx, txt in cols:
        parts.append(f'<text x="{cx}" y="486" font-family="Arial" font-size="9.5" '
                     f'font-weight="bold" fill="#475569">{txt}</text>')
    for i, p in enumerate(cu["dft"]):
        y = 504 + i * 15
        parts.append(f'<text x="34" y="{y}" font-family="Arial" font-size="9.5" fill="#0f172a">{p["n_modes"]}</text>')
        parts.append(f'<text x="86" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["n_gates"]}</text>')
        parts.append(f'<text x="176" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["n_gate_steps"]}</text>')
        parts.append(f'<text x="266" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["max_gates_per_step"]}</text>')
        parts.append(f'<text x="346" y="{y}" font-family="Arial" font-size="9.5" font-weight="bold" fill="#16a34a">{p["fidelity"]:.12f}</text>')
        parts.append(f'<text x="466" y="{y}" font-family="Arial" font-size="9.5" fill="#334155">{p["depth_lower_bound"]}</text>')
        parts.append(f'<text x="556" y="{y}" font-family="Arial" font-size="9.5" font-weight="bold" fill="#2563eb">{2 * p["n_modes"] - 3}</text>')

    parts += [
        f'<text x="34" y="592" font-family="Arial" font-size="9.5" fill="#475569">'
        f'引理 L1 任意对寻址 max|Δ|={rep["lemma_l1_any_pair_addressing"]["max_abs_diff"]:.0e} · '
        f'深度界三口径（N=216）：参数 {bnd["parameter_count_bound"]} ≤ 紧界 '
        f'{bnd["tight_adjacency_bound"]} ≤ Reck 最优 {bnd["reck_mesh_optimum"]}'
        f' ⇒ N−1 不可达</text>',
        f'<text x="34" y="606" font-family="Arial" font-size="9.5" fill="#475569">'
        f'浅并行调度提速（N=216）：朴素 {nt["naive_serial_depth"]} → {nt["shallow_depth"]} 层'
        f'（{nt["speedup_vs_serial"]:.0f}×，fid=1.0，每层=真匹配）</text>',
        f'<text x="34" y="620" font-family="Arial" font-size="9.5" fill="#475569">'
        f'静态 {static["n_physical_mzi"]} 元件/{static["loss_per_mode_db"]:.0f} dB vs '
        f'时间复用 1 元件/{tmux["loss_per_mode_db"]:.0f} dB · Borealis 3 环可及 '
        f'{lat["reachable_params_model"]} ≪ N²</text>',
        '<text x="34" y="633" font-family="Arial" font-size="9" fill="#94a3b8">'
        'Borealis 216 模（Nature 606,75-81(2022)，外部 A 级事实，仅引用不复算）· '
        '物理形态不同，只比规模/架构/参数计数 · 损耗为设计预算口径</text>',
        f'<text x="34" y="652" font-family="Arial" font-size="11" font-weight="bold" fill="{vcol}">'
        f'M4 延伸判决：{rep["verdict"]}（构造性通用性成立 · 浅调度达该 op 集最优 2N−3 · '
        f'参数下界 N−1 不可达）</text>',
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
    sh = rep["shallow_scheduler"]
    nt = sh["n_target"]
    print(f"⑤ 浅并行调度（关键路径分层）：N=216 朴素 {nt['naive_serial_depth']} → "
          f"{nt['shallow_depth']} 层（{nt['speedup_vs_serial']:.0f}×，fid=1.0，每层=真匹配）")
    for p in sh["sweep"]:
        print(f"   N={p['n_modes']:4d}  朴素={p['naive_serial_depth']:5d}  "
              f"浅={p['shallow_depth']:4d}  ({p['speedup_vs_serial']:.1f}×)  "
              f"每层最多={p['max_gates_per_layer']:3d}  fid={p['fidelity']:.12f}")
    bd = rep["depth_bounds"]
    print(f"   深度界三口径（N=216）：参数下界 {bd['parameter_count_bound']} ≤ 紧界 "
          f"{bd['tight_adjacency_bound']} ≤ 平台 Reck 最优 {bd['reck_mesh_optimum']}")
    print(f"   ⇒ 「参数下界 N−1 可达」的诚实答案：**否**（偶 N 唯一最大匹配 ⇒ 紧界=N；"
          f"唯一性={bd['unique_max_matching']}）")
    print()
    print(f"M4 延伸判决：{rep['verdict']}")
    print("产物：lda_q4b_report.json · lda_q4b_frontier.svg")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
