"""LDA 新征程 · LDA-Q3：量子态层（M3 物理深度第一步）——让芯片「按量子力学算」。

============================================================================
定位（吃自己的狗粮 · M3 = 物理深度）
----------------------------------------------------------------------------
M1（LDA-Q1）走通主权全链路；M2（LDA-Q2）把布局升级为参数化 N×N mesh P&R 生成器，
画出的 mesh 传递矩阵 ≡ 目标酉（经典光学层）。但「量子计算芯片」必须在**量子态层**
工作：输入的是 Fock（光子数）态，输出的是量子干涉后的量子态，而非经典功率 |U|²。

M3 补上这一层（平台缺口 G_Q2 Fock 态仿真 / G_Q4 HOM）：
- 新平台能力 `lda_qeda/loqc_states.py`（D-113）：permanent / 线性光学振幅 / 输出分布
  / 符合计数 / HOM，两种结构不同算法交叉验证（永久式 × 产生算符多项式展开）。
- 本脚本把 **M2 产出的 mesh 酉 U** 直接当线性光学变换，演示：
  ① 片上 HOM 干涉（单个 MZI：不可区分双光子符合计数 = 0，破坏性干涉）；
  ② 双光子/多光子 Fock 态穿过 4/6/8 模 DFT mesh 的**量子输出分布**；
  ③ 量子 vs 经典（可区分光子）分布对比 —— 量子干涉不可用经典功率模拟；
  ④ HOM dip 曲线 vs θ（可见度 V=1）。

物理定律锚（闭式 · 公共品）：HOM 符合概率 = cos²(2θ) = (T−R)²；玻色采样振幅 =
per(U_T,S)/√(Πn!Πm!)。红线：纯 numpy、LLM 不进判决路径。

诚实边界：理想酉（无损耗/噪声/探测物理）；单光子源/SNSPD 物理（G_Q1）、开放系统
完全过程层（G_Q3 Lindblad 到多模）、量子 DRC/LVS（G_Q7）属后续增量。
============================================================================
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lda"))

from lda_l2.mzi_mesh_matmul import (              # noqa: E402
    reck_triangular_mesh, assemble_triangular_mesh, unitary_fidelity, dft_matrix,
)
from lda_qeda.loqc_states import (                # noqa: E402
    permanent, output_distribution,
    apply_linear_optics_polynomial, bs_unitary, hom_coincidence,
    hom_coincidence_closed_form, hom_coincidence_distinguishable, hom_visibility,
    coincidence_probability,
)

OUT = HERE


# ── 组态工具 ──────────────────────────────────────────────────────────────────
def _compositions(n, M):
    if M == 1:
        yield (n,)
        return
    for first in range(n + 1):
        for rest in _compositions(n - first, M - 1):
            yield (first,) + rest


def _fact(occ):
    d = 1.0
    for c in occ:
        d *= math.factorial(int(c))
    return d


def classical_distribution(U, in_occ):
    """可区分（经典）光子的输出分布：per(|U_T,S|²)/(Πn!Πm!)。

    这是「独立光子」基线——HOM 型量子干涉会使其偏离，偏离量即量子性证据。
    """
    U2 = np.abs(np.asarray(U, dtype=complex)) ** 2
    M = U2.shape[0]
    in_occ = tuple(int(x) for x in in_occ)
    N = sum(in_occ)
    cols = [i for i, n in enumerate(in_occ) for _ in range(n)]
    out = {}
    for out_occ in _compositions(N, M):
        rows = [j for j, m in enumerate(out_occ) for _ in range(m)]
        if not rows:
            out[out_occ] = 1.0
            continue
        per = permanent(U2[np.ix_(rows, cols)].astype(complex))
        out[out_occ] = float(per.real / (_fact(in_occ) * _fact(out_occ)))
    return out


def tv_distance(p, q):
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys)


def chip_unitary(N):
    """M2 芯片实际实现的酉：三角 mesh 分解 → 装配（与目标 DFT 比对保真度）。"""
    target = dft_matrix(N)
    ops, D = reck_triangular_mesh(target)
    U = assemble_triangular_mesh(ops, D, N)
    return U, unitary_fidelity(U, target), len(ops)


# ── SVG 报告（HOM dip 曲线 + 输出分布柱状）─────────────────────────────────────
def render_svg(path, hom_theta, hom_p, dist4, dist4_cls):
    W, H = 680, 300
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<text x="16" y="26" font-family="Segoe UI,Arial" font-size="15" '
             'font-weight="600" fill="#1e293b">LDA-Q3 · 量子态层：片上 HOM 干涉 + '
             '量子输出分布</text>']
    # 面板 A：HOM dip
    ax, ay, aw, ah = 40, 50, 250, 200
    parts.append(f'<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" fill="#f8fafc" '
                 'stroke="#cbd5e1"/>')
    parts.append(f'<text x="{ax}" y="{ay-6}" font-family="Segoe UI,Arial" '
                 'font-size="12" fill="#475569">A · HOM 符合概率 P(θ)（蓝=数值，'
                 '橙虚线=cos²2θ 闭式）</text>')
    th = np.asarray(hom_theta)
    pv = np.asarray(hom_p)
    xs = ax + (th / (math.pi / 2.0)) * aw
    ys = ay + ah - (pv / 0.5) * ah
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#2563eb" '
                 'stroke-width="2"/>')
    # 闭式虚线
    cf = np.cos(2.0 * th) ** 2
    yc = ay + ah - (cf / 0.5) * ah
    ptsc = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, yc))
    parts.append(f'<polyline points="{ptsc}" fill="none" stroke="#f59e0b" '
                 'stroke-width="1.6" stroke-dasharray="5 3"/>')
    # 50:50 标记
    x50 = ax + 0.5 * aw
    parts.append(f'<line x1="{x50}" y1="{ay}" x2="{x50}" y2="{ay+ah}" '
                 'stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 3"/>')
    parts.append(f'<circle cx="{x50}" cy="{ay+ah}" r="3.2" fill="#dc2626"/>')
    parts.append(f'<text x="{x50+4}" y="{ay+ah-6}" font-family="Segoe UI,Arial" '
                 'font-size="10" fill="#dc2626">50:50 → P=0</text>')
    parts.append(f'<text x="{ax}" y="{ay+ah+16}" font-family="Segoe UI,Arial" '
                 'font-size="10" fill="#64748b">θ=0</text>')
    parts.append(f'<text x="{ax+aw-30}" y="{ay+ah+16}" font-family="Segoe UI,Arial" '
                 'font-size="10" fill="#64748b">θ=π/2</text>')
    # 面板 B：4 模输出分布（量子 vs 经典）
    bx, by, bw, bh = 360, 50, 290, 200
    parts.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="#f8fafc" '
                 'stroke="#cbd5e1"/>')
    parts.append(f'<text x="{bx}" y="{by-6}" font-family="Segoe UI,Arial" '
                 'font-size="12" fill="#475569">B · |1,1,0,0⟩ 穿 4 模 DFT mesh 的'
                 '输出分布（蓝=量子，灰=经典）</text>')
    items = sorted(dist4.items(), key=lambda kv: -kv[1])[:9]
    pmax = max([v for _, v in items] + [1e-9])
    n = len(items)
    bwid = (bw - 20) / max(n, 1)
    for k, (occ, p) in enumerate(items):
        x = bx + 10 + k * bwid
        hbar = (p / pmax) * (bh - 46)
        pc = dist4_cls.get(occ, 0.0)
        hbarc = (pc / pmax) * (bh - 46)
        parts.append(f'<rect x="{x+1:.1f}" y="{by+bh-22-hbarc:.1f}" '
                     f'width="{bwid*0.42:.1f}" height="{hbarc:.1f}" fill="#cbd5e1"/>')
        parts.append(f'<rect x="{x+bwid*0.5:.1f}" y="{by+bh-22-hbar:.1f}" '
                     f'width="{bwid*0.42:.1f}" height="{hbar:.1f}" fill="#2563eb"/>')
        lbl = "".join(str(c) for c in occ)
        parts.append(f'<text x="{x+bwid*0.45:.1f}" y="{by+bh-8}" '
                     f'font-family="Segoe UI,Arial" font-size="8.5" fill="#475569" '
                     f'text-anchor="middle">{lbl}</text>')
    parts.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    report = {
        "chip_family": "LDA-Q3 · 量子态层（LOQC 通用处理器量子仿真）· M3 物理深度第一步",
        "platform_capability": "lda_qeda/loqc_states.py（D-113）：Fock 态 + 线性光学"
                               " + 符合计数 + HOM（闭合 G_Q2/G_Q4）",
        "methodology": "永久式（组合计数）× 产生算符多项式展开（符号）双算法交叉验证；"
                       "闭式物理律 HOM=cos²2θ 作 golden；LLM 不进判决路径",
    }

    # ── ① 片上 HOM 干涉（单个 MZI：50:50 不可区分双光子符合计数 = 0）──
    p_hom = hom_coincidence(math.pi / 4.0)
    p_hom_cf = hom_coincidence_closed_form(math.pi / 4.0)
    p_dist = hom_coincidence_distinguishable(math.pi / 4.0)
    vis = hom_visibility(math.pi / 4.0)
    print("① 片上 HOM 干涉（不可区分双光子 → 破坏性干涉）")
    print(f"   50:50 符合概率 = {p_hom:.3e}（闭式 {p_hom_cf:.3e}）· "
          f"可区分 = {p_dist:.6f} · 可见度 V = {vis:.9f}")
    report["hom_5050"] = {
        "coincidence": p_hom, "closed_form": p_hom_cf,
        "distinguishable": p_dist, "visibility": vis,
    }

    # HOM dip 曲线 vs θ（数值 × 闭式）
    hom_theta = [float(t) for t in np.linspace(0.0, math.pi / 2.0, 61)]
    hom_p = [hom_coincidence(t) for t in hom_theta]
    max_cf_dev = max(abs(p - hom_coincidence_closed_form(t))
                     for t, p in zip(hom_theta, hom_p))
    print(f"   HOM dip 曲线：数值 × 闭式 max|Δ| = {max_cf_dev:.3e}")
    report["hom_dip_vs_closed_form_max_dev"] = max_cf_dev

    # ── ② 光子 Fock 态穿 M2 mesh 的量子输出分布（N=4/6/8）──
    print("\n② 多光子 Fock 态 → M2 mesh 酉 U → 量子输出分布")
    runs = []
    for N, nphot in ((4, 2), (6, 3), (8, 4)):
        U, fid, n_mzi = chip_unitary(N)
        in_occ = tuple(1 if k < nphot else 0 for k in range(N))
        dist = output_distribution(U, in_occ)
        dist_poly = apply_linear_optics_polynomial(U, in_occ)
        max_dev = max(abs(dist.get(o, 0.0) - abs(dist_poly.get(o, 0.0 + 0.0j)) ** 2)
                      for o in dist)
        sum_p = sum(dist.values())
        dist_cls = classical_distribution(U, in_occ)
        tv = tv_distance(dist, dist_cls)
        top = sorted(dist.items(), key=lambda kv: -kv[1])[:6]
        runs.append({
            "N": N, "n_photons": nphot, "n_mzi": n_mzi,
            "mesh_fidelity": round(float(fid), 12),
            "n_output_configs": len(dist),
            "sum_probability": round(float(sum_p), 12),
            "dual_method_max_dev": float(max_dev),
            "quantum_vs_classical_TV": round(float(tv), 6),
            "top_outcomes": [[list(o), round(p, 6)] for o, p in top],
        })
        print(f"   N={N} 光子={nphot}: mesh保真={fid:.1e} 组态={len(dist)} "
              f"ΣP={sum_p:.12f} 双算法Δ={max_dev:.1e} 量子×经典TV={tv:.4f}")
    report["runs"] = runs

    # ── ③ 量子 vs 经典对比（HOM 是量子性的直接证据）──
    # 4 模 mesh 上 |1,1,0,0⟩：量子分布在模(0,2)/(1,3) 对已纠缠相关
    U4, fid4, _ = chip_unitary(4)
    d4q = output_distribution(U4, (1, 1, 0, 0))
    d4c = classical_distribution(U4, (1, 1, 0, 0))
    tv4 = tv_distance(d4q, d4c)
    print(f"\n③ 量子 × 经典 TV 距离（4 模 |1,1,0,0⟩）= {tv4:.4f} > 0 "
          f"⇒ 量子干涉不可用经典功率模拟")
    report["quantum_classical_TV_4mode"] = round(float(tv4), 6)

    # ── ④ 芯片级 HOM：HOM 要求两光子被**同一个 50:50 分束器**耦合 ──
    #   ④a 最小 2 模 mesh（DFT(2)=Hadamard 即 50:50 分束器，M2 P&R 生成器的最小实例）
    U2, fid2, _ = chip_unitary(2)
    p_chip2 = coincidence_probability(U2, (1, 1), in_modes=(0, 1), out_modes=(0, 1))
    #   ④b M1 路径纠缠原语（模 0,2 上 50:50 BS）——芯片的纠缠元件
    U4pe = np.eye(4, dtype=complex)
    U4pe[np.ix_([0, 2], [0, 2])] = bs_unitary(math.pi / 4.0)
    p_chip4 = coincidence_probability(U4pe, (1, 0, 1, 0), in_modes=(0, 2),
                                      out_modes=(0, 2))
    print(f"④ 芯片级 HOM：2 模 mesh 符合={p_chip2:.3e} · "
          f"M1 路径纠缠原语(模0,2)符合={p_chip4:.3e}（均应 = 0）")
    report["chip_hom_coincidence_2mode_mesh"] = p_chip2
    report["chip_hom_coincidence_path_entangle"] = p_chip4

    # ── 输出 SVG ──
    svg_path = os.path.join(OUT, "lda_q3_quantum.svg")
    render_svg(svg_path, hom_theta, hom_p, d4q, d4c)
    report["svg_path"] = svg_path
    print(f"\nSVG : {svg_path}")

    report["honest_note"] = (
        "M3 把芯片从经典光学层提升到量子态层：输入 Fock 态、输出量子干涉分布（真量子）。"
        "仍为理想酉（无损耗/相位噪声/探测器暗计数）；单光子源/SNSPD 探测物理（G_Q1）、"
        "开放系统完全过程层（G_Q3）、量子 DRC/LVS（G_Q7）、量子基准（G_Q8）属后续增量。"
        "HOM/玻色采样为闭式物理律锚（非拟合、非仿真值）。"
    )
    rep_path = os.path.join(OUT, "lda_q3_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2,
                  default=lambda o: (list(o) if isinstance(o, tuple) else str(o)))
    print(f"报告: {rep_path}")

    # 出口判据（死标量）：HOM=0 + 闭式对齐 + mesh 保真 + 归一
    ok = (p_hom < 1e-12 and abs(p_hom_cf) < 1e-15 and max_cf_dev < 1e-12
          and p_chip2 < 1e-12 and p_chip4 < 1e-12
          and all(r["sum_probability"] > 1 - 1e-9 and r["dual_method_max_dev"] < 1e-10
                  and r["mesh_fidelity"] > 1 - 1e-9 for r in runs))
    print(f"\nLDA-Q3 出口判据：{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
