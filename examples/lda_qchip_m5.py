"""LDA-Q5 · 矩形 Clements 网格（M5）——「深度紧界 N 到底可不可达？」

承接 LDA-Q4b（M4 延伸）留下的唯一悬问：

  ❓ 三角 Reck 的「深度最优 = 2N−3」是终点吗？
     参数计数下界 N−1 已证**不可达**，那**紧界 N**（偶 N 唯一最大匹配给出的真下界）呢？

本演示把它放到**可构造 + 可判死**的标准下重测，回答是一个肯定的：
**换矩形（Clements）网格，紧界 N 可达**，且对一切 N ≥ 3 成立。

三条由真实 API 驱动的结论（无硬编码结果）：
  ① 约定桥   两条**块级精确**恒等式（实测 max|Δ|<1e−15）：
               `_ref_T(θ,φ) = mzi_unit_cell(2θ,0)·diag(e^{iφ},1)`（**无标量**，D-122 采用）
               `_ref_T(θ,φ) = e^{iφ}·mzi_unit_cell(2θ,−φ)`（**含标量**）
             主权「平方约定」的相位在**输入臂 / 较低模 j**，平台 `mzi_unit_cell` 在
             **输出臂 / 较高模 j+1** ——两个不同 SU(2) 相位约定，**不是** 2θ 缩放。
             🔴 陷阱：裸 `mzi_unit_cell(2θ,−φ)` 在 2×2 只差标量 e^{−iφ}（看似可忽略），
             但**嵌入 N×N 后**该标量只落在本门 2 模 ⇒ 每门注入**逐模相位**（与邻门不对易）
             ⇒ 网格 ≠ U（**连全局相位都不是**）：相位不变 fid≈0.005、项目口径 0.66（N=8）。
  ② 紧界可达 矩形网格层数 = 列数 = 光学深度 = **N**（每层真匹配）
             ⇒ 与 D-121 相邻耦合紧下界 N **相等** ⇒ **紧界可达**。
             三角 Reck 最优 2N−3 并非最优；矩形化把深度**减半**（2N−3 → N）。
  ③ 构造正确 用**平台物理原语**装配（diag 相位层 + mzi_unit_cell(2θ,0) 分束器），
             DFT 与 Haar 随机酉重建保真度 = **1.0**（机器精度），
             并与主权 `mesh_rect_decomp_fidelity` / `mesh_rect_fidelity` **三方一致**。

🔴 红线：纯 numpy + 平台模块（零量子 SDK）；LLM 不进判决路径；闭式恒等式作 golden。

诚实边界：本演示是**网格拓扑 + 酉重构**的正确性证明（数学 + 构造性数值），**非真机实测**；
   未含波导损耗 / 非理想耦合 / 串扰 / 热串扰（属 P1-B 工艺级）。
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_qeda import rect_mesh as RMB            # noqa: E402
from lda_qeda import temporal_mesh as TMB        # noqa: E402
from lda_l2 import mzi_mesh_matmul as MMM        # noqa: E402

N_SWEEP = (4, 8, 16, 32, 64, 128)               # 实跑扫频（构造 + 保真度）
N_TARGET = 216                                   # 对标 Borealis 的模数
SEED = 20260930


def _bridge_error_case() -> dict:
    """血案复现：裸 `mzi_unit_cell(2θ,−φ)` 的精确性质（防「块矩阵对得上」的错说法）。

    · 2×2：`e^{iφ}·mzi_unit_cell(2θ,−φ) = _ref_T` **精确** ⇒ 裸门只差一个标量；
    · 但嵌入 N×N 后该标量只落在本门 2 模 ⇒ 逐模相位注入 ⇒ 网格 ≠ U（非全局相位差）；
      以**相位不变**保真度 |Tr(U†rec)|²/N² ≪ 1 反证「不是全局相位」。
    """
    from lda_layout.mesh_pnr import _ref_T_apply_rows
    th, ph = 0.9, 0.5
    rng = np.random.default_rng(0)
    X = rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))
    X1 = X.copy()
    _ref_T_apply_rows(X1, th, ph, 0)
    X2 = X.copy()
    Bw = MMM.mzi_unit_cell(2 * th, -ph)
    r0, r1 = X2[0].copy(), X2[1].copy()
    X2[0] = Bw[0, 0] * r0 + Bw[0, 1] * r1
    X2[1] = Bw[1, 0] * r0 + Bw[1, 1] * r1
    # 裸门整网格装配
    n = 8
    U = TMB.random_unitary(n, seed=SEED)
    dec, assign, _ref = RMB._sovereign()
    A_blk = _ref(th, ph, 2, 3, 4)[np.ix_([1, 2], [1, 2])]
    bs, D = dec(U)
    T = np.eye(n, dtype=complex)
    for (j, thk, phk) in bs:
        Bw2 = MMM.mzi_unit_cell(2 * thk, -phk)       # ← 裸门（未拆对角相位层）
        q0, q1 = T[j].copy(), T[j + 1].copy()
        T[j] = Bw2[0, 0] * q0 + Bw2[0, 1] * q1
        T[j + 1] = Bw2[1, 0] * q0 + Bw2[1, 1] * q1
    rec = np.diag(np.diag(D)) @ T
    return {
        "block_diff_bare_vs_ref": float(np.max(np.abs(A_blk - MMM.mzi_unit_cell(2 * th, -ph)))),
        "block_diff_scaled_exact": float(np.max(np.abs(
            A_blk - np.exp(1j * ph) * MMM.mzi_unit_cell(2 * th, -ph)))),
        "row_action_max_abs_diff": float(np.max(np.abs(X1 - X2))),
        "wrong_bridge_fidelity_N8": float(MMM.unitary_fidelity(rec, U)),
        "phase_invariant_fidelity_N8": float(abs(np.trace(U.conj().T @ rec)) ** 2 / (n * n)),
    }


def run() -> dict:
    dec, assign, _ref = RMB._sovereign()

    # ① 约定桥恒等式（精确 0.0）
    worst = 0.0
    for (th, ph) in ((0.7, 0.4), (1.2, -2.1), (0.0, 0.0), (0.9, 0.5), (np.pi / 4, 3.1)):
        A = _ref(th, ph, 2, 3, 4)
        B = np.eye(4, dtype=complex)
        B[np.ix_([1, 2], [1, 2])] = (MMM.mzi_unit_cell(2 * th, 0.0)
                                     @ np.diag([complex(np.cos(ph), np.sin(ph)), 1.0]))
        worst = max(worst, float(np.max(np.abs(A - B))))
    bridge = {
        "identity": "_ref_T(theta,phi) = mzi_unit_cell(2*theta, 0) @ diag(exp(1j*phi), 1)",
        "max_abs_diff": worst,
        "exact": bool(worst < 1e-14),
        "note": "相位臂相反（输入/上臂 vs 输出/下臂）⇒ 非 2θ 缩放；须拆独立对角相位层。",
    }
    error_case = _bridge_error_case()

    # ② 保真度扫频（构造性正确）
    fid_sweep = []
    for n in N_SWEEP:
        f_dft = RMB.rect_mesh_fidelity(MMM.dft_matrix(n))
        f_rnd = RMB.rect_mesh_fidelity(TMB.random_unitary(n, seed=n * 5 + 1))
        fid_sweep.append({"n_modes": n, "fidelity_dft": f_dft, "fidelity_random": f_rnd})
    worst_fid = min(min(p["fidelity_dft"], p["fidelity_random"]) for p in fid_sweep)

    # ③ 深度扫频：矩形 N vs 三角 Reck 2N−3
    depth_sweep = []
    for n in N_SWEEP:
        pr = RMB.rect_mesh_profile(n, target="dft")
        depth_sweep.append({
            "n_modes": n, "n_mzi": pr["n_mzi"], "rect_depth": pr["depth"],
            "optical_depth": pr["optical_depth"], "per_layer_max": pr["per_layer_max"],
            "layers_are_matchings": pr["layers_are_matchings"],
            "reck_optimum": pr["reck_mesh_optimum"],
            "depth_reduction_vs_reck": pr["depth_reduction_vs_reck"],
            "parameter_count_bound": pr["parameter_count_bound"],
            "tight_adjacency_bound": pr["tight_adjacency_bound"],
            "depth_equals_tight_bound": pr["depth_equals_tight_bound"],
            "fidelity": pr["fidelity"],
        })

    # ④ N=216 紧界可达判定（落点）
    tgt = RMB.tight_bound_reachable_report(N_TARGET)

    # ⑤ 三方一致（跨模块桥）
    three_way = []
    from lda_layout.mesh_pnr import mesh_rect_decomp_fidelity, mesh_rect_fidelity
    for n in (4, 8, 16):
        U_ = TMB.random_unitary(n, seed=n + 101)
        bs_, D_ = dec(U_)
        three_way.append({
            "n_modes": n,
            "mine": float(RMB.rect_mesh_fidelity(U_)),
            "decomp": float(mesh_rect_decomp_fidelity(bs_, D_, U_)),
            "mesh": float(mesh_rect_fidelity(bs_, D_, U_)),
        })

    diag_ok = (
        bridge["exact"]
        and error_case["block_diff_scaled_exact"] < 1e-14          # 2×2 只差标量（精确）
        and error_case["block_diff_bare_vs_ref"] > 0.3              # 裸门块 ≠ _ref_T
        and error_case["row_action_max_abs_diff"] > 0.5
        and error_case["wrong_bridge_fidelity_N8"] < 0.9
        and error_case["phase_invariant_fidelity_N8"] < 1e-2        # 非「只差全局相位」
        and all(p["rect_depth"] == p["n_modes"] and p["depth_equals_tight_bound"]
                and p["tight_adjacency_bound"] == p["n_modes"]
                and p["optical_depth"] == p["n_modes"]
                and p["layers_are_matchings"]
                and p["reck_optimum"] == 2 * p["n_modes"] - 3
                and p["depth_reduction_vs_reck"] == p["n_modes"] - 3
                and p["n_mzi"] == p["n_modes"] * (p["n_modes"] - 1) // 2
                for p in depth_sweep)
        and all(p["rect_depth"] == p["n_modes"] and p["fidelity"] > 1 - 1e-11
                for p in depth_sweep)
        and all(abs(p["fidelity_dft"] - 1.0) < 1e-11
                and abs(p["fidelity_random"] - 1.0) < 1e-11 for p in fid_sweep)
        and tgt["tight_bound_reachable"] is True
        and tgt["rectangular_mesh_depth"] == N_TARGET == tgt["tight_adjacency_bound"]
        and all(abs(p["mine"] - 1.0) < 1e-11 and abs(p["decomp"] - 1.0) < 1e-12
                and abs(p["mesh"] - 1.0) < 1e-12 for p in three_way)
    )
    verdict_str = "PASS" if diag_ok else "FAIL"

    return {
        "chip_family": "LDA-Q5 · 矩形 Clements 网格（M5）",
        "platform_capability": ("lda_qeda/rect_mesh.py(D-122) 复用 lda_layout.mesh_pnr 主权矩形分解 "
                                "+ lda_l2.mzi_mesh_matmul.mzi_unit_cell 平台物理原语"),
        "n_sweep": list(N_SWEEP),
        "n_target": N_TARGET,
        "convention_bridge": bridge,
        "convention_bridge_error_case": error_case,
        "fidelity_sweep": fid_sweep,
        "worst_fidelity": float(worst_fid),
        "depth_sweep": depth_sweep,
        "n_target_report": tgt,
        "three_way_agreement": three_way,
        "headline_findings": [
            "① ★约定桥★ 两条**块级精确**恒等式（均 max|Δ|≈0）："
            "`_ref_T(θ,φ) = mzi_unit_cell(2θ,0)·diag(e^{iφ},1)`（无标量，D-122 采用）"
            " = `e^{iφ}·mzi_unit_cell(2θ,−φ)`（含标量）。相位落于**输入臂/较低模 j**"
            f"（主权）vs **输出臂/较高模 j+1**（平台）—— 非 2θ 缩放（实测 max|Δ|={bridge['max_abs_diff']:.1e}）。",
            "① 血案（比「块对不上」更精微）：裸 `mzi_unit_cell(2θ,−φ)` 在 2×2 只差标量 e^{−iφ}"
            f"（e^iφ·裸 − _ref_T 的 max|Δ|={error_case['block_diff_scaled_exact']:.1e}，精确）；"
            f"但**嵌入 N×N 后**该标量只落在本门 2 模（裸门 vs _ref_T 块 max|Δ|="
            f"{error_case['block_diff_bare_vs_ref']:.3f}）⇒ 每门注入**逐模相位**（与邻门不对易）"
            f"⇒ 网格 ≠ U（**连全局相位都不是**）：相位不变 fid="
            f"{error_case['phase_invariant_fidelity_N8']:.4f}（≪1 即反证）、项目 Frobenius 口径 "
            f"{error_case['wrong_bridge_fidelity_N8']:.4f} ⇒ 必须拆出独立对角相位层。",
            "★ 结论 1（紧界可达）：矩形网格层数 = 列数 = 光学深度 = **N**（N≥3 每层真匹配）"
            "⇒ 与 D-121 相邻耦合紧下界 N 相等 ⇒ **紧界可达**。对照三角 Reck 最优 2N−3，"
            "矩形化把深度**减半**（N=216：429 → **216**，省 **213** 层）。",
            "★ 结论 2（构造正确）：用平台物理原语装配，DFT 与 Haar 随机酉重建保真度均 = "
            f"**1.0**（最差 fid={worst_fid:.12f}，N=4…128），且与主权 "
            "`mesh_rect_decomp_fidelity`/`mesh_rect_fidelity` **三方一致**。",
            "★ 结论 3（元件数不变）：矩形网格仍用 **N(N−1)/2** 片 MZI（Clements 必要性定理）"
            "⇒ 收益纯在**深度**；深度仍 Ω(N) ⇒ D-121「通用与省损不可兼得」**不变**。",
            "★ 结论 4（D-121 悬问闭环）：D-121「参数界 N−1 不可达」与 D-122「紧界 N 可达」"
            "**不矛盾** —— 前者是**参数计数下界（非紧）**，后者是**相邻耦合紧下界（真·可达）**。",
        ],
        "scale_verdict": (
            "M5 结论：三角 Reck 的 2N−3 并非深度最优 —— 换**矩形（Clements）网格**即可把"
            "通用 N 模酉的深度打到**紧界 N**（每层真匹配、构造 fid=1.0），且不增加元件数。"
            "但深度仍 Ω(N)：矩形化把「损耗墙 = 深度墙」下界从 2N−3 降到 N，"
            "**不改变**「通用与省损不可兼得」这一结构性结论。"),
        "honest_boundary": (
            "① 本演示是**网格拓扑 + 酉重构**的正确性证明（数学 + 构造性数值），**非真机实测**；"
            "② 未含波导损耗 / 非理想耦合 / 串扰 / 热串扰（属 P1-B 工艺级）；"
            "③ 「深度」= 网格**列数**（同列配对互不共享波导 ⇒ 同列可共享抽头 ⇒ 层数即物理深度）；"
            "④ 分解**非本模块自研**：复用 `lda_layout.mesh_pnr.clements_rect_decompose`"
            "（主权验证 fid=1.0 至 N=512）；本模块新增 = 约定桥 + 深度可达性判定；"
            "⑤ 与 Clements 原始文献同结论（矩形 N、三角 2N−3），但不引其数值作 golden ——"
            "判据全部为闭式恒等式 + 构造性实测。"),
        "verdict": verdict_str,
    }


# ---------------------------------------------------------------------------
# 可视化：四面板 —— 约定桥 / 深度对照 / 紧界可达 / 三方一致
# ---------------------------------------------------------------------------
def _panel_bridge(parts, x0, y0, w, h, bridge, err):
    parts.append(f'<text x="{x0}" y="{y0 - 8}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">约定桥：主权平方约定 → 平台 mzi_unit_cell</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + 20}" font-family="Arial" font-size="8.4" '
                 f'fill="#334155">_ref_T(θ,φ) = mzi_unit_cell(2θ,0) · diag(e^{{iφ}},1)</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + 36}" font-family="Arial" font-size="8.4" '
                 f'font-weight="bold" fill="#16a34a">正确 max|Δ| = {bridge["max_abs_diff"]:.1e}'
                 f'（精确）</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + 54}" font-family="Arial" font-size="8.4" '
                 f'fill="#475569">等价式：e^iφ · mzi_unit_cell(2θ,−φ)（含标量，精确）</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + 72}" font-family="Arial" font-size="8.4" '
                 f'fill="#dc2626">✗ 裸 mzi_unit_cell(2θ,−φ)：2×2 只差标量'
                 f'（Δ={err["block_diff_scaled_exact"]:.1e}）</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + 86}" font-family="Arial" font-size="8.4" '
                 f'fill="#dc2626">但嵌入 N×N 后注入**逐模相位**（与邻门不对易）</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + 100}" font-family="Arial" font-size="8.4" '
                 f'fill="#dc2626">⇒ 网格 ≠ U：相位不变 fid={err["phase_invariant_fidelity_N8"]:.4f}'
                 f'（项目口径 {err["wrong_bridge_fidelity_N8"]:.3f}）</text>')
    # 相位臂示意（两个 2×2 方块）
    bx = x0 + 10
    by = y0 + h - 66
    parts.append(f'<text x="{bx}" y="{by - 4}" font-family="Arial" font-size="8" '
                 f'fill="#475569">主权：相位在输入/上臂</text>')
    parts.append(f'<rect x="{bx}" y="{by}" width="66" height="30" fill="#eff6ff" '
                 f'stroke="#2563eb" rx="3"/>')
    parts.append(f'<text x="{bx + 33}" y="{by + 13}" font-family="Arial" font-size="7.6" '
                 f'fill="#2563eb" text-anchor="middle">e^iφ · cosθ</text>')
    parts.append(f'<text x="{bx + 33}" y="{by + 25}" font-family="Arial" font-size="7.6" '
                 f'fill="#2563eb" text-anchor="middle">e^iφ · sinθ</text>')
    bx2 = x0 + w / 2 + 6
    parts.append(f'<text x="{bx2}" y="{by - 4}" font-family="Arial" font-size="8" '
                 f'fill="#475569">平台：相位在输出/下臂</text>')
    parts.append(f'<rect x="{bx2}" y="{by}" width="66" height="30" fill="#eff6ff" '
                 f'stroke="#2563eb" rx="3"/>')
    parts.append(f'<text x="{bx2 + 33}" y="{by + 13}" font-family="Arial" font-size="7.6" '
                 f'fill="#2563eb" text-anchor="middle">cos(2θ)</text>')
    parts.append(f'<text x="{bx2 + 33}" y="{by + 25}" font-family="Arial" font-size="7.6" '
                 f'fill="#2563eb" text-anchor="middle">e^iφ · sin(2θ)</text>')


def _panel_depth(parts, x0, y0, w, h, depth_sweep):
    parts.append(f'<text x="{x0}" y="{y0 - 8}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">深度对照：矩形 N vs 三角 Reck 2N−3</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    hi = max(p["reck_optimum"] for p in depth_sweep) * 1.05
    bx = x0 + 40
    for i, p in enumerate(depth_sweep):
        yy = y0 + 20 + i * 20
        blr = (p["reck_optimum"] / hi) * (w - 70)
        blg = (p["rect_depth"] / hi) * (w - 70)
        parts.append(f'<text x="{x0 + 6}" y="{yy + 4}" font-family="Arial" font-size="8" '
                     f'fill="#0f172a">N={p["n_modes"]}</text>')
        parts.append(f'<rect x="{bx}" y="{yy - 8}" width="{blr:.1f}" height="7" '
                     f'fill="#dc2626" opacity="0.75" rx="2"/>')
        parts.append(f'<rect x="{bx}" y="{yy + 1}" width="{blg:.1f}" height="7" '
                     f'fill="#2563eb" opacity="0.85" rx="2"/>')
        parts.append(f'<text x="{bx + blr + 3:.1f}" y="{yy - 2}" font-family="Arial" '
                     f'font-size="7.6" fill="#dc2626">{p["reck_optimum"]}</text>')
        parts.append(f'<text x="{bx + blg + 3:.1f}" y="{yy + 8}" font-family="Arial" '
                     f'font-size="7.6" fill="#2563eb">{p["rect_depth"]}（省 '
                     f'{p["depth_reduction_vs_reck"]}）</text>')
    parts.append(f'<rect x="{x0 + 6}" y="{y0 + h - 16}" width="9" height="7" fill="#dc2626" '
                 f'opacity="0.75" rx="1"/>')
    parts.append(f'<text x="{x0 + 19}" y="{y0 + h - 10}" font-family="Arial" font-size="7.8" '
                 f'fill="#475569">三角 Reck 最优 2N−3</text>')
    parts.append(f'<rect x="{x0 + 128}" y="{y0 + h - 16}" width="9" height="7" fill="#2563eb" '
                 f'opacity="0.85" rx="1"/>')
    parts.append(f'<text x="{x0 + 141}" y="{y0 + h - 10}" font-family="Arial" font-size="7.8" '
                 f'fill="#475569">矩形网格 N（= 紧界，可达）</text>')


def _panel_target(parts, x0, y0, w, h, tgt):
    parts.append(f'<text x="{x0}" y="{y0 - 8}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">N=216：紧界可达判定</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    rows = ((tgt["parameter_count_bound"], "#94a3b8", "参数计数下界（非紧）"),
            (tgt["tight_adjacency_bound"], "#2563eb", "紧界（相邻耦合）"),
            (tgt["rectangular_mesh_depth"], "#16a34a", "矩形网格可达"),
            (tgt["reck_mesh_optimum"], "#dc2626", "三角 Reck 最优"))
    hi = max(r[0] for r in rows) * 1.12
    bx = x0 + 118
    bw = w - 138
    for i, (v, col, lab) in enumerate(rows):
        yy = y0 + 22 + i * 24
        bl = (v / hi) * bw
        parts.append(f'<rect x="{bx}" y="{yy - 9}" width="{bl:.1f}" height="13" '
                     f'fill="{col}" opacity="0.85" rx="2"/>')
        parts.append(f'<text x="{bx - 4}" y="{yy + 1}" font-family="Arial" font-size="7.6" '
                     f'fill="#475569" text-anchor="end">{lab}</text>')
        parts.append(f'<text x="{bx + bl + 4:.1f}" y="{yy + 1}" font-family="Arial" '
                     f'font-size="8.5" font-weight="bold" fill="{col}">{v}</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + h - 8}" font-family="Arial" font-size="8" '
                 f'fill="#16a34a">★ 矩形深度 216 = 紧界 216 ⇒ 紧界可达'
                 f'（省 {tgt["depth_reduction_vs_reck"]} 层）</text>')


def _panel_threeway(parts, x0, y0, w, h, three_way, worst_fid):
    parts.append(f'<text x="{x0}" y="{y0 - 8}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">构造正确：平台装配 ≡ 主权分解（三方一致）</text>')
    parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f8fafc" '
                 f'stroke="#e2e8f0" rx="4"/>')
    cols = ((x0 + 10, "N"), (x0 + 40, "本模块"), (x0 + 130, "主权 decomp"),
            (x0 + 218, "主权 mesh"))
    for cx, txt in cols:
        parts.append(f'<text x="{cx}" y="{y0 + 20}" font-family="Arial" font-size="8.2" '
                     f'font-weight="bold" fill="#475569">{txt}</text>')
    for i, p in enumerate(three_way):
        yy = y0 + 38 + i * 16
        parts.append(f'<text x="{x0 + 10}" y="{yy}" font-family="Arial" font-size="8.2" fill="#0f172a">{p["n_modes"]}</text>')
        parts.append(f'<text x="{x0 + 40}" y="{yy}" font-family="Arial" font-size="8.2" font-weight="bold" fill="#16a34a">{p["mine"]:.12f}</text>')
        parts.append(f'<text x="{x0 + 130}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{p["decomp"]:.12f}</text>')
        parts.append(f'<text x="{x0 + 218}" y="{yy}" font-family="Arial" font-size="8.2" fill="#334155">{p["mesh"]:.12f}</text>')
    parts.append(f'<text x="{x0 + 10}" y="{y0 + h - 8}" font-family="Arial" font-size="8" '
                 f'fill="#475569">DFT + Haar 随机酉最差重建 fid = {worst_fid:.12f}（机器精度）</text>')


def render_svg(rep: dict) -> str:
    vcol = "#16a34a" if rep["verdict"] == "PASS" else "#dc2626"
    tgt = rep["n_target_report"]
    dw = rep["depth_sweep"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 620" width="680" height="620">',
        '<rect width="680" height="620" fill="#ffffff"/>',
        '<text x="34" y="30" font-family="Arial" font-size="18" font-weight="bold" '
        'fill="#0f172a">LDA-Q5 · 矩形 Clements 网格（M5）</text>',
        '<text x="34" y="48" font-family="Arial" font-size="10.5" fill="#64748b">'
        '深度紧界 N 可达 · 约定桥 精确 0.0 · 矩形 vs 三角 Reck（2N−3 → N）· '
        '平台物理原语装配 fid=1.0 · 纯 numpy · 闭式恒等式作 golden</text>',
        '<line x1="34" y1="58" x2="646" y2="58" stroke="#e2e8f0"/>',
    ]
    _panel_bridge(parts, 34, 92, 290, 190, rep["convention_bridge"],
                  rep["convention_bridge_error_case"])
    _panel_depth(parts, 356, 92, 290, 190, dw)

    parts.append('<line x1="34" y1="300" x2="646" y2="300" stroke="#e2e8f0"/>')
    _panel_target(parts, 34, 316, 290, 130, tgt)
    _panel_threeway(parts, 356, 316, 290, 130, rep["three_way_agreement"],
                    rep["worst_fidelity"])

    parts += [
        '<line x1="34" y1="462" x2="646" y2="462" stroke="#e2e8f0"/>',
        f'<text x="34" y="482" font-family="Arial" font-size="9.5" fill="#475569">'
        f'约定桥两式 max|Δ|={rep["convention_bridge"]["max_abs_diff"]:.1e}（精确）· '
        f'裸门 2×2 只差标量 Δ={rep["convention_bridge_error_case"]["block_diff_scaled_exact"]:.1e}，'
        f'但嵌入后注入逐模相位 ⇒ 相位不变 fid='
        f'{rep["convention_bridge_error_case"]["phase_invariant_fidelity_N8"]:.4f}'
        f'（项目口径 {rep["convention_bridge_error_case"]["wrong_bridge_fidelity_N8"]:.3f}，血案）</text>',
        f'<text x="34" y="498" font-family="Arial" font-size="9.5" fill="#475569">'
        f'紧界可达（N=216）：参数界 {tgt["parameter_count_bound"]} ≤ 紧界 '
        f'{tgt["tight_adjacency_bound"]} = 矩形可达 {tgt["rectangular_mesh_depth"]} ≤ '
        f'Reck 最优 {tgt["reck_mesh_optimum"]} ⇒ 省 {tgt["depth_reduction_vs_reck"]} 层</text>',
        '<text x="34" y="514" font-family="Arial" font-size="9.5" fill="#475569">'
        '元件数仍 = N(N−1)/2（Clements 必要性定理）⇒ 收益纯在深度，不增元件；'
        '深度仍 Ω(N)</text>',
        '<text x="34" y="536" font-family="Arial" font-size="8.8" fill="#94a3b8">'
        '诚实边界：本演示为网格拓扑 + 酉重构的正确性证明（数学 + 构造性数值），非真机实测；'
        '未含波导损耗/非理想耦合/串扰</text>',
        '<text x="34" y="550" font-family="Arial" font-size="8.8" fill="#94a3b8">'
        '（属 P1-B 工艺级）· 分解复用主权 lda_layout.mesh_pnr.clements_rect_decompose'
        '（fid=1.0 至 N=512）· 与 Clements 文献同结论，但不引其数值作 golden</text>',
        f'<text x="34" y="578" font-family="Arial" font-size="11" font-weight="bold" fill="{vcol}">'
        f'M5 判决：{rep["verdict"]}（紧界 N 可达 · 约定桥精确 · 平台装配 fid=1.0 · '
        f'矩形化省深度 {tgt["depth_reduction_vs_reck"]} 层 @N=216）</text>',
        '</svg>',
    ]
    return "\n".join(parts)


def main() -> int:
    rep = run()
    with open(os.path.join(_HERE, "lda_q5_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(_HERE, "lda_q5_mesh.svg"), "w", encoding="utf-8") as f:
        f.write(render_svg(rep))

    print("=" * 84)
    print("LDA-Q5 · 矩形 Clements 网格（M5）")
    print("=" * 84)
    b = rep["convention_bridge"]
    e = rep["convention_bridge_error_case"]
    print(f"① ★约定桥★ _ref_T(θ,φ) = mzi_unit_cell(2θ,0)·diag(e^iφ,1)"
          f" = e^iφ·mzi_unit_cell(2θ,−φ)：max|Δ|={b['max_abs_diff']:.1e} 精确={b['exact']}")
    print(f"   血案：裸 mzi_unit_cell(2θ,−φ) 2×2 只差标量 Δ={e['block_diff_scaled_exact']:.1e}，"
          f"但嵌入后注入逐模相位（非全局）")
    print(f"         ⇒ 相位不变 fid={e['phase_invariant_fidelity_N8']:.4f}（≪1 反证）、"
          f"项目口径 {e['wrong_bridge_fidelity_N8']:.4f} ⇒ 须拆独立对角相位层")
    print("② 构造正确性（平台物理原语装配）：")
    for p in rep["fidelity_sweep"]:
        print(f"   N={p['n_modes']:4d}  fid(DFT)={p['fidelity_dft']:.12f}  "
              f"fid(随机)={p['fidelity_random']:.12f}")
    print(f"   最差 fid={rep['worst_fidelity']:.12f}")
    print("③ ★紧界可达★ 深度对照（矩形 N vs 三角 Reck 2N−3）：")
    for p in rep["depth_sweep"]:
        print(f"   N={p['n_modes']:4d}  元件={p['n_mzi']:5d}  矩形深={p['rect_depth']:4d}  "
              f"Reck 最优={p['reck_optimum']:4d}  省={p['depth_reduction_vs_reck']:4d}  "
              f"光深={p['optical_depth']:4d}  匹配={'真' if p['layers_are_matchings'] else '假'}  "
              f"fid={p['fidelity']:.9f}")
    t = rep["n_target_report"]
    print(f"④ N=216 紧界可达判定：参数界 {t['parameter_count_bound']} ≤ 紧界 "
          f"{t['tight_adjacency_bound']} = 矩形可达 {t['rectangular_mesh_depth']} ≤ "
          f"Reck 最优 {t['reck_mesh_optimum']} ⇒ 可达={t['tight_bound_reachable']}，"
          f"省 {t['depth_reduction_vs_reck']} 层")
    print("⑤ 三方一致（平台装配 ≡ 主权 decomp ≡ 主权 mesh）：")
    for p in rep["three_way_agreement"]:
        print(f"   N={p['n_modes']:3d}  {p['mine']:.12f} / {p['decomp']:.12f} / "
              f"{p['mesh']:.12f}")
    print()
    for h in rep["headline_findings"]:
        print("  " + h)
    print()
    print(f"M5 判决：{rep['verdict']}")
    print("产物：lda_q5_report.json · lda_q5_mesh.svg")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
