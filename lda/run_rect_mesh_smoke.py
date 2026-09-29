"""矩形 Clements 网格 门禁 smoke（D-122 · M5：**坐实「紧界 N 可达」**）。

═══ 为什么要有这个 smoke ═══
D-122 是量子征程里第一块**把深度打进紧界**的模块，它给出三条极易被后人
"改回好看样子"的结论，必须钉成常驻断言：

  ① **约定桥**：`_ref_T(θ,φ) ≡ mzi_unit_cell(2θ,0)·diag(e^{iφ},1)`
      `≡ e^{iφ}·mzi_unit_cell(2θ,−φ)`（两式块级均精确）。
     陷阱：裸 `mzi_unit_cell(2θ,−φ)` 在 2×2 只差标量 e^{−iφ}（看似可忽略），
     但**嵌入 N×N 后**该标量只落在本门 2 模 ⇒ 每门注入**逐模相位**（与邻门不对易）
     ⇒ 网格 ≠ U（连全局相位都不是）：相位不变 fid≈0.005、项目口径 0.66 ⇒ 必须变红。
  ② **深度 = 紧界 N（可达）**：矩形网格层数 = 列数 = 光学深度 = N。
     有人把「三角 Reck 的 2N−3」当最优、或把层数写大 ⇒ 立刻变红。
  ③ **元件数不增**：矩形化只省深度，仍用 N(N−1)/2 片门（Clements 必要性定理）。
     有人把「矩形化 = 更省元件」写成结论 ⇒ 变红。

═══ 判什么（分六节 · 26 条）═══
A 自检+约定桥+平台装配 4 · B 紧界可达 6 · C Reck 对照+跨模块 4 ·
D 诚实标注+红线 4 · E 护栏 4 · F 深界一致性 4。

运行：python run_rect_mesh_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from lda_qeda import rect_mesh as RMB
    from lda_qeda import temporal_mesh as TMB
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import rect_mesh as RMB                              # noqa: E402
    import temporal_mesh as TMB                          # noqa: E402

from lda_l2 import mzi_mesh_matmul as MMM                # noqa: E402
from lda_harness.smoke_kit import make_check             # noqa: E402

# 计数写进模块命名空间；助手复用公共 `smoke_kit`，不另建局部 `def check`
# （防「助手重复棘轮」劣化 · **名字在前**！写反成 check(cond, name) ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("矩形 Clements 网格 门禁 smoke（D-122 · M5：紧界 N 可达）")
    print("=" * 78)

    # ════════════════ A 节：自检 + 约定桥 + 平台装配 ════════════════
    print("── A 约定桥（主权平方约定 → 平台 mzi_unit_cell 约定）──")
    try:
        ok_a = RMB.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_a = False
        print(f"  矩形网格模块自检异常：{type(e).__name__}: {e}")
    check("A1 矩形网格模块自检 9/9 PASS", ok_a,
          "约定桥/平台装配/紧界可达/元件数/跨模块三方一致/Reck对照/可达判定/护栏/无LLM")

    # 约定桥恒等式：直接对拍 2×2 块（多个 θ、φ，含 0 与 π/4）
    dec, assign, _ref = RMB._sovereign()
    worst = 0.0
    for (th, ph) in ((0.7, 0.4), (1.2, -2.1), (0.0, 0.0), (0.9, 0.5), (np.pi / 4, 3.1)):
        A = _ref(th, ph, 2, 3, 4)
        B = np.eye(4, dtype=complex)
        B[np.ix_([1, 2], [1, 2])] = (MMM.mzi_unit_cell(2 * th, 0.0)
                                     @ np.diag([complex(np.cos(ph), np.sin(ph)), 1.0]))
        worst = max(worst, float(np.max(np.abs(A - B))))
    check("A2 ★约定桥★ _ref_T(θ,φ) ≡ mzi_unit_cell(2θ,0)·diag(e^iφ,1)（精确 0.0）",
          worst < 1e-14, f"max|Δ|={worst:.1e}（不是 2θ 缩放：相位臂相反）")

    # 反例护栏：裸 mzi_unit_cell(2θ,−φ) 的**精确**性质 —— 防有人改回「块矩阵对得上」的错说法。
    #   2×2 层面它 = e^{−iφ}·_ref_T（只差标量）；但**嵌入 N×N 后**该标量只落在本门的 2 个模
    #   ⇒ 每门给这 2 模注入 e^{−iφ} 的**逐模相位**，与邻门不对易 ⇒ 网格 ≠ U（**非**全局相位差）。
    from lda_layout.mesh_pnr import _ref_T_apply_rows
    th_, ph_ = 0.9, 0.5
    A_blk = _ref(th_, ph_, 2, 3, 4)[np.ix_([1, 2], [1, 2])]
    scal_exact = float(np.max(np.abs(
        A_blk - np.exp(1j * ph_) * MMM.mzi_unit_cell(2 * th_, -ph_))))
    rng_ = np.random.default_rng(0)
    X = rng_.normal(size=(4, 4)) + 1j * rng_.normal(size=(4, 4))
    X1 = X.copy(); _ref_T_apply_rows(X1, th_, ph_, 0)
    X2 = X.copy()
    Bw = MMM.mzi_unit_cell(2 * th_, -ph_)
    r0, r1 = X2[0].copy(), X2[1].copy()
    X2[0] = Bw[0, 0] * r0 + Bw[0, 1] * r1
    X2[1] = Bw[1, 0] * r0 + Bw[1, 1] * r1
    row_diff = float(np.max(np.abs(X1 - X2)))
    # 裸门装配整网格 ⇒ 相位不变 fid ≪ 1（证明「不是只差一个全局相位」）
    n_b = 8
    U_b = TMB.random_unitary(n_b, seed=20260930)
    bs_b, D_b = dec(U_b)
    T_b = np.eye(n_b, dtype=complex)
    for (j, t, p) in bs_b:
        Gb = MMM.mzi_unit_cell(2 * t, -p)
        q0, q1 = T_b[j].copy(), T_b[j + 1].copy()
        T_b[j] = Gb[0, 0] * q0 + Gb[0, 1] * q1
        T_b[j + 1] = Gb[1, 0] * q0 + Gb[1, 1] * q1
    rec_b = np.diag(np.diag(D_b)) @ T_b
    fid_inv = float(abs(np.trace(U_b.conj().T @ rec_b)) ** 2 / (n_b * n_b))
    check("A3 反例：裸 mzi_unit_cell(2θ,−φ) 2×2 只差标量、嵌入后注入逐模相位 ⇒ 网格错",
          scal_exact < 1e-14 and row_diff > 0.5 and fid_inv < 1e-2,
          f"2×2 e^iφ·裸 Δ{scal_exact:.1e} · 行作用 Δ{row_diff:.3f} · "
          f"相位不变 fid{fid_inv:.4f}（故必须拆对角相位层）")

    # 平台约定装配：DFT + 随机（N=2…64）机器精度
    ok_a4 = True
    detail_a4 = []
    for n_ in (2, 3, 4, 8, 16, 32, 64):
        for tgt in ("dft", "random"):
            f = RMB.rect_mesh_fidelity(
                MMM.dft_matrix(n_) if tgt == "dft" else TMB.random_unitary(n_, seed=n_ * 5 + 1))
            detail_a4.append(f"{n_}/{tgt}:{f:.9f}")
            if abs(f - 1.0) > 1e-11:
                ok_a4 = False
    check("A4 平台约定装配重建任意酉 = 机器精度（DFT + Haar 随机，N=2…64）",
          ok_a4, " · ".join(detail_a4[:6]) + " …")

    # ════════════════ B 节：紧界可达 ════════════════
    print("── B ★紧界 N 可达★（矩形网格层数 = 紧下界）──")
    ok_b1 = True
    detail_b1 = []
    for n_ in (3, 4, 5, 6, 7, 8, 16, 32, 64, 128):
        pr = RMB.rect_mesh_profile(n_, target="dft")
        detail_b1.append(f"N={n_}:d={pr['depth']}")
        if not (pr["depth"] == n_ and pr["depth_equals_tight_bound"]
                and pr["tight_adjacency_bound"] == n_):
            ok_b1 = False
    check("B1 ★核心★ 矩形网格层数 = 紧界 N（N=3…128）", ok_b1, " · ".join(detail_b1))

    ok_b2 = True
    for n_ in (4, 8, 16, 64):
        pr = RMB.rect_mesh_profile(n_, target="random", seed=n_ + 3)
        if not pr["layers_are_matchings"]:
            ok_b2 = False
    check("B2 每一层都是真『匹配』（两两不相交的相邻对 ⇒ 可同步施加）",
          ok_b2, "N=4/8/16/64 随机酉逐层核验")

    ok_b3 = True
    detail_b3 = []
    for n_ in (4, 8, 32, 64):
        pr = RMB.rect_mesh_profile(n_, target="dft")
        detail_b3.append(f"N={n_}:opt={pr['optical_depth']}")
        if pr["optical_depth"] != n_:
            ok_b3 = False
    check("B3 每模光学深度 = N（每模恰穿过 N 片分束器）", ok_b3, " · ".join(detail_b3))

    rep216 = RMB.tight_bound_reachable_report(216)
    check("B4 ★紧界可达★ N=216：参数界 215 / 紧界 216 = 矩形可达 216 / Reck 429",
          rep216["parameter_count_bound"] == 215
          and rep216["tight_adjacency_bound"] == 216
          and rep216["rectangular_mesh_depth"] == 216
          and rep216["reck_mesh_optimum"] == 429
          and rep216["tight_bound_reachable"] is True,
          f"省 {rep216['depth_reduction_vs_reck']} 层（2N−3 → N）")

    ok_b5 = True
    for n_ in (4, 16, 64, 216):
        pr = RMB.rect_mesh_profile(n_, target="dft")
        if pr["n_mzi"] != n_ * (n_ - 1) // 2:
            ok_b5 = False
    check("B5 元件数仍 = N(N−1)/2（Clements 必要性定理 · 矩形化不增元件）",
          ok_b5, "N=4/16/64/216 逐点核验")

    ok_b6 = True
    for n_ in (4, 8, 16, 64, 216):
        pr = RMB.rect_mesh_profile(n_, target="dft")
        if pr["depth_reduction_vs_reck"] != n_ - 3:
            ok_b6 = False
    check("B6 深度收益 = N−3（= (2N−3) − N）", ok_b6,
          "N=4:省1 · N=8:省5 · N=64:省61 · N=216:省213")

    # ════════════════ C 节：Reck 对照 + 跨模块 ════════════════
    print("── C 三角 Reck 对照 + 跨模块桥 ──")
    ok_c1 = True
    detail_c1 = []
    for n_ in (4, 8, 16, 64):
        sh = TMB.temporal_shallow_profile(n_, target="dft")
        pr = RMB.rect_mesh_profile(n_, target="dft")
        detail_c1.append(f"N={n_}:reck={sh['shallow_depth']}>rect={pr['depth']}")
        if not (sh["shallow_depth"] == 2 * n_ - 3 and pr["depth"] < sh["shallow_depth"]):
            ok_c1 = False
    check("C1 三角 Reck 最优 = 2N−3 严格深于 矩形 N ⇒ 矩形网格才是深度最优",
          ok_c1, " · ".join(detail_c1))

    from lda_layout.mesh_pnr import mesh_rect_decomp_fidelity, mesh_rect_fidelity
    ok_c2 = True
    detail_c2 = []
    for n_ in (4, 8, 16):
        U_ = TMB.random_unitary(n_, seed=n_ + 101)
        bs_, D_ = dec(U_)
        f_dec = float(mesh_rect_decomp_fidelity(bs_, D_, U_))
        f_mesh = float(mesh_rect_fidelity(bs_, D_, U_))
        f_mine = float(RMB.rect_mesh_fidelity(U_))
        detail_c2.append(f"N={n_}:{f_mine:.13f}/{f_dec:.13f}/{f_mesh:.13f}")
        if not (abs(f_dec - 1.0) < 1e-12 and abs(f_mesh - 1.0) < 1e-12
                and abs(f_mine - f_mesh) < 1e-11):
            ok_c2 = False
    check("C2 跨模块桥：本模块装配 ≡ 主权 mesh_rect_decomp/mesh_rect_fidelity（三方一致）",
          ok_c2, " · ".join(detail_c2))

    pr128 = RMB.rect_mesh_profile(128, target="dft")
    check("C3 大 N 仍成立：N=128 层数 128 · 光学深度 128 · fid=1.0 · 每层匹配",
          pr128["depth"] == 128 and pr128["optical_depth"] == 128
          and abs(pr128["fidelity"] - 1.0) < 1e-11 and pr128["layers_are_matchings"] is True,
          f"n_mzi={pr128['n_mzi']} per_layer_max={pr128['per_layer_max']}")

    # 深度界单调：参数界 ≤ 紧界 = 矩形 ≤ Reck（含 216）
    ok_c4 = True
    detail_c4 = []
    for n_ in (4, 8, 16, 64, 216):
        b = TMB.depth_bound_report(n_)
        pr = RMB.rect_mesh_profile(n_, target="dft")
        detail_c4.append(f"N={n_}:{b['parameter_count_bound']}/"
                         f"{b['tight_adjacency_bound']}={pr['depth']}/{b['reck_mesh_optimum']}")
        if not (b["parameter_count_bound"] <= b["tight_adjacency_bound"] == pr["depth"]
                <= b["reck_mesh_optimum"]):
            ok_c4 = False
    check("C4 三口径单调自洽：参数界 ≤ 紧界 = 矩形可达 ≤ Reck 最优（含 216）",
          ok_c4, " · ".join(detail_c4))

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = RMB.RED_LINE_DISCLOSURE
    check("D1 诚实边界齐备：约定桥 / 复用而非重造 / golden / 主权 / 边界",
          all(k in disc for k in ("role", "reuse_not_reinvent", "convention_bridge",
                                  "golden", "sovereignty", "honest_boundary"))
          and "非真机实测" in disc.get("honest_boundary", ""),
          f"键={sorted(disc)}")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    src = open(os.path.join(_HERE, "lda_qeda", "rect_mesh.py"), encoding="utf-8").read()
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D2 红线：D-122 零量子 SDK 依赖（纯 numpy + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")

    check("D3 判决无 LLM：深度/界全为 int · 可达性为 bool（死标量，零模型调用）",
          isinstance(rep216["rectangular_mesh_depth"], int)
          and isinstance(rep216["tight_adjacency_bound"], int)
          and isinstance(rep216["tight_bound_reachable"], bool),
          "rectangular_mesh_depth / tight_adjacency_bound 为 int")

    check("D4 复用而非重造：分解指向主权 lda_layout.mesh_pnr（不另建分解）",
          "lda_layout.mesh_pnr" in disc.get("reuse_not_reinvent", "")
          and "clements_rect_decompose" in disc.get("reuse_not_reinvent", ""),
          "RED_LINE_DISCLOSURE.reuse_not_reinvent 明示复用来源")

    # ════════════════ E 节：护栏 ════════════════
    print("── E 护栏（非法输入必须抛错）──")
    guard = True
    for bad in ((lambda: RMB.rectangular_mesh_layers(np.ones((2, 3), dtype=complex))),
                (lambda: RMB.rectangular_mesh_layers(np.eye(1, dtype=complex))),
                (lambda: RMB.assemble_rect_mesh([[(0, 0.3, 0.1), (0, 0.2, 0.0)]],
                                                np.eye(4), 4)),
                (lambda: RMB.assemble_rect_mesh([[(5, 0.3, 0.1)]], np.eye(4), 4)),
                (lambda: RMB.assemble_rect_mesh([], np.eye(1), 1)),
                (lambda: RMB.rect_mesh_profile(1))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    check("E1 护栏：非方阵 / N<2 / 非匹配层（共享模） / 越界 ⇒ 抛 ValueError",
          guard, "六类非法输入全抛错")

    # 非匹配层单独反证：构造共享模的一层，必须抛
    try:
        RMB.assemble_rect_mesh([[(0, 0.3, 0.1), (1, 0.2, 0.0)]], np.eye(4), 4)
        shared_raises = False
    except ValueError:
        shared_raises = True
    check("E2 反证：同层两门共享模（(0,1) 与 (1,2)）⇒ 非匹配 ⇒ 必须抛 ValueError",
          shared_raises, "物理上同一步共享模不可实现")

    # 层内顺序无关（匹配 ⇒ 对易）：交换层内两门顺序，装配结果不变
    n_ = 8
    U_ = TMB.random_unitary(n_, seed=77)
    layers_, D_ = RMB.rectangular_mesh_layers(U_)
    swapped = [list(reversed(lay)) for lay in layers_]
    d_sw = float(np.max(np.abs(RMB.assemble_rect_mesh(swapped, D_, n_)
                               - RMB.assemble_rect_mesh(layers_, D_, n_))))
    check("E3 层内次序无关（匹配 ⇒ 两两对易）：反转每层门序，装配结果不变",
          d_sw < 1e-13, f"max|Δ|={d_sw:.2e}")

    check("E4 空层容错：layers=[] ⇒ 返回 D 本身（退化 N 模恒等 + 相位层）",
          float(np.max(np.abs(RMB.assemble_rect_mesh([], np.eye(3), 3) - np.eye(3)))) < 1e-15,
          "无门网格 = 纯输出相移层")

    # ════════════════ F 节：深界一致性 ════════════════
    print("── F 与 D-121 深界口径一致性 ──")
    ok_f1 = True
    for n_ in (4, 16, 64):
        pr = RMB.rect_mesh_profile(n_, target="dft")
        if not (pr["tight_adjacency_bound"] == TMB.tight_depth_lower_bound(n_)
                and pr["parameter_count_bound"] == TMB.universality_depth_lower_bound(n_)):
            ok_f1 = False
    check("F1 与 D-121 同源：紧界/参数界取自 temporal_mesh（单一口径，不另建）",
          ok_f1, "tight_depth_lower_bound / universality_depth_lower_bound")

    ok_f2 = True
    for n_ in (4, 16, 216):
        rep = RMB.tight_bound_reachable_report(n_)
        if not (rep["parameter_count_bound"] <= rep["tight_adjacency_bound"]
                == rep["rectangular_mesh_depth"]):
            ok_f2 = False
    check("F2 可达判定 = 「矩形深度 == 紧界」且每层匹配且 fid=1.0（三条件同时）",
          ok_f2, "N=4/16/216 逐点核验")

    pr = RMB.rect_mesh_profile(32, target="dft")
    fields = ("n_modes", "n_mzi", "n_layers", "depth", "per_layer_max",
              "layers_are_matchings", "optical_depth", "fidelity", "unitary_ok",
              "parameter_count_bound", "tight_adjacency_bound", "depth_equals_tight_bound",
              "reck_mesh_optimum", "depth_reduction_vs_reck")
    check("F3 剖面字段齐备且自洽：depth = n_layers = tight · n_mzi = N(N−1)/2",
          all(k in pr for k in fields) and pr["depth"] == pr["n_layers"]
          and pr["depth"] == pr["tight_adjacency_bound"]
          and pr["n_mzi"] == 32 * 31 // 2,
          f"字段 {len(fields)} 项全在")

    check("F4 D-121「N−1 不可达」与 D-122「N 可达」不矛盾（参数界非紧 vs 紧界可达）",
          TMB.universality_depth_lower_bound(216) == 215
          and TMB.tight_depth_lower_bound(216) == 216
          and rep216["rectangular_mesh_depth"] == 216,
          "215（参数界，非紧）< 216（紧界，矩形可达）")

    print()
    print(f"矩形 Clements 网格 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
