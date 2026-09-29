# -*- coding: utf-8 -*-
"""可编程子流形（「非通用但浅」）· D-127 · 深度预算 D 下**最大化可及自由度**。

背景（D-121 → D-126 留下的缺口）：
D-121 给出「时间复用的可编程性前沿 = 可及参数 ≈ ⌊N/2⌋·D」，D-123/D-126 用它做损耗账。
但那个 `⌊N/2⌋·D` 是**参数计数**（一个上界），**不是**真正的自由度 ——
D-121 的 2b 节已经证明「偶 N 唯一最大匹配 ⇒ 每层皆最大匹配 ⇒ 块对角 ⇒ 非通用」，
那只说明**门多 ≠ 自由度高**，却没有量化。

本模块把这件事**量化**并**机器测量**出来：

  ★ **可及自由度 = 可达子流形的维数** `dim`
      = 参数映射 Φ: R^P → U(N)（P = 2g + N）在一般点的**雅可比秩**（数值实测）。

  ① **饱和上界**：`dim ≤ min(2g + N, N²)`（g = 门数；N² 是 U(N) 的实维数）。
  ② **🔴 参数计数会骗人**：全最大匹配（O-only）序列 g 线性增而 **dim 恒为 2N**
     （块对角 ⇒ 可达集 = (U(2))^{N/2}，实维 4·N/2 = 2N）—— 这是 D-121 2b 阻塞的定量版。
  ③ **最优浅电路 = 交替砖墙（O,E,O,E…）**：实测 `dim = min(2·g_bw(D) + N, N²)`
     —— **逐点达到上界**；N=4 全序列穷举 + N≤8 beam search 均无更优。
  ④ **通用前沿 `D* = N`**（dim = N²）：与 D-122 矩形网格深度 N、D-121 相邻耦合紧界 N
     **三方一致**；`D = N−1` 时 dim < N² ⇒ 坐实「参数界 N−1 **不可达**」。

约定（平台静态网格 · 显式披露）：
  · 每片 2 模门 = 平台 `mzi_unit_cell(θ, φ)` ⇒ **2 个实参数**；
  · 末端输出相移屏 `diag(e^{iψ₁..ψ_N})` ⇒ **N 个实参数**（= `clements_rect_decompose` 的 `D`）；
  · 目标 `dim U(N) = N²`；`通用 ⟺ dim = N²`（Clements 必要性+充分性 ⇒ g ≥ N(N−1)/2）。
  🔴 D-121 用的是**另一套口径**（每门 1 参数、局部相位作规范）⇒ 两口径回答不同问题，
     **只有「门数」可比**（本模块门禁 F 节机器核对）。

诚实边界（`SUBMANIFOLD_DISCLOSURE`）：见该常量（含「实测秩非解析证明」「只在 N≤8 搜索」
「纯运动学自由度、不含损耗/相位噪声」等）。
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from lda_l2 import mzi_mesh_matmul as MMM

Pair = Tuple[int, int]
Layer = Tuple[Pair, ...]

#: 布尔/整数/实数判决位（死标量）—— 本模块无 LLM 参与
_UNIVERSAL_TOL = 0.0

SUBMANIFOLD_DISCLOSURE: Dict[str, str] = {
    "role": "D-127 = 「非通用但浅」的可编程子流形设计：把 **可及自由度** 从**参数计数**升级为"
            "**可达子流形维数**（雅可比秩，机器实测），并在深度预算 D 下求最优层序列。",
    "why": "D-121 的 `⌊N/2⌋·D` 是参数计数（上界），D-121 §2b 已定性指出「门多 ≠ 通用」；"
           "本模块给出**定量**版本：全最大匹配序列 dim 恒为 2N，而交替砖墙逐点达到上界。",
    "convention": "平台静态网格口径：每片 2 模门 = `mzi_unit_cell(θ,φ)` ⇒ 2 实参数；"
                  "末端相移屏 ⇒ N 实参数；P = 2g + N；目标 dim U(N) = N²。"
                  "🔴 D-121 用「每门 1 参数 · 局部相位作规范」口径 ⇒ **只有门数可比**"
                  "（门禁 F 节机器核对）。",
    "dim_is_measured": "🔴 `dim` 是**数值实测**（中心差分雅可比 → SVD 秩），取 `n_samples` 个随机点的"
                       "**最大秩**（秩是一般性质，退化点是零测集）。它是**实测证据**，不是解析证明。",
    "search_is_bounded": "🔴 最优性证据**只在 N ≤ 8、D ≤ 6**：N=4 全序列穷举；N=6/8 用 beam search"
                         "（beam=4/8）+ O-heavy 变体对照。⇒ 结论是「在已搜索空间内无更优」，"
                         "**不宣称**对所有 N/D 的全局最优证明。",
    "kinematics_only": "本模块只谈**运动学自由度**（可达流形维数）：**不含**损耗（见 D-123/D-126）、"
                       "不含相位噪声/标定误差（见 D-117）、不含探测器/源（见 D-114/D-115）。",
    "phase_gauge": "`dim` 计入了**全局相位**（U(N) 实维 = N²，含 U(1) 因子）；"
                   "若按「不计全局相位」（SU(N) = N²−1）应减 1 —— 本模块统一按 U(N) 口径并在"
                   "`universal_dim` 键显式给出 N²。",
    "even_n_note": "偶 N 的**唯一最大匹配**是偶数对 O（D-121 `adjacency_max_matching`）⇒ "
                   "「每层都最大」必然全为 O ⇒ 块对角 ⇒ dim 上不去。奇 N 无此唯一性。",
    "no_llm": "本模块全部为整数/实数/布尔比对，**LLM 不进判决路径**；零量子 SDK（纯 numpy + 平台模块）。",
}


class SubmanifoldError(Exception):
    """输入/不变量违规。"""


# ---------------------------------------------------------------------------
# 1) 层（匹配）与门数
# ---------------------------------------------------------------------------
def odd_pairs(n_modes: int) -> Layer:
    """O = {(0,1),(2,3),…} —— 偶 N 时 **唯一** 最大匹配（尺寸 ⌊N/2⌋）。"""
    n = int(n_modes)
    if n < 2:
        raise SubmanifoldError("n_modes ≥ 2")
    return tuple((2 * i, 2 * i + 1) for i in range(n // 2))


def even_pairs(n_modes: int) -> Layer:
    """E = {(1,2),(3,4),…} —— 交错匹配（尺寸 ⌊(N−1)/2⌋）。"""
    n = int(n_modes)
    if n < 2:
        raise SubmanifoldError("n_modes ≥ 2")
    return tuple((2 * i + 1, 2 * i + 2) for i in range((n - 1) // 2))


def layer_gate_count(layer: Sequence[Pair]) -> int:
    """一层内的门数（= 匹配尺寸）。"""
    return int(len(tuple(layer)))


def n_gates(layers: Sequence[Sequence[Pair]]) -> int:
    """全序列门总数 g。"""
    return int(sum(layer_gate_count(L) for L in layers))


def layer_is_matching(n_modes: int, layer: Sequence[Pair]) -> bool:
    """该层是否为 P_N 上的**匹配**（相邻对两两不相交且不越界）。

    匹配 ⇒ 同层各门作用于不同模对 ⇒ 彼此对易 ⇒ 可同步、与顺序无关（物理可实现性约束）。
    """
    n = int(n_modes)
    if n < 2:
        raise SubmanifoldError("n_modes ≥ 2")
    used: set = set()
    for (p, q) in layer:
        p, q = int(p), int(q)
        if not (0 <= p and q == p + 1 and q < n):
            return False
        if p in used or q in used:
            return False
        used.add(p)
        used.add(q)
    return True


def path_matchings(n_modes: int) -> Tuple[Layer, ...]:
    """P_N 的**全部**匹配（含空层），按尺寸降序 —— 搜索空间。"""
    n = int(n_modes)
    if n < 2:
        raise SubmanifoldError("n_modes ≥ 2")
    pairs = [(p, p + 1) for p in range(n - 1)]
    out: List[Layer] = []
    for r in range(len(pairs) + 1):
        for combo in itertools.combinations(pairs, r):
            used: set = set()
            ok = True
            for (a, b) in combo:
                if a in used or b in used:
                    ok = False
                    break
                used.add(a)
                used.add(b)
            if ok:
                out.append(tuple(combo))
    out.sort(key=lambda m: (-len(m), m))
    return tuple(out)


# ---------------------------------------------------------------------------
# 2) 参数映射与「可及自由度」= 雅可比秩
# ---------------------------------------------------------------------------
def param_count(n_modes: int, layers: Sequence[Sequence[Pair]]) -> int:
    """平台口径参数数 `P = 2g + N`（每门 2 参数 + 末端相移屏 N）。"""
    n = int(n_modes)
    if n < 2:
        raise SubmanifoldError("n_modes ≥ 2")
    return int(2 * n_gates(layers) + n)


def universal_dim(n_modes: int) -> int:
    """U(N) 的实维数 = N²（本模块的目标维数 `dim = N²` 即通用）。"""
    n = int(n_modes)
    if n < 2:
        raise SubmanifoldError("n_modes ≥ 2")
    return int(n * n)


def saturation_bound(n_modes: int, layers: Sequence[Sequence[Pair]]) -> int:
    """★ 可及自由度**上界**：`min(2g + N, N²)`（参数数上限 ∧ 流形维数上限）。"""
    n = int(n_modes)
    return int(min(param_count(n, layers), universal_dim(n)))


def build_submanifold_unitary(n_modes: int, layers: Sequence[Sequence[Pair]],
                              x: Sequence[float]) -> np.ndarray:
    """参数化映射 Φ(x) = diag(e^{iψ}) · Π_layers Π_gates mzi_unit_cell(θ,φ)（嵌入 N×N）。

    `x` 长度必须 = `param_count`：前 2g 个为逐门的 (θ, φ)（按层序、层内按对序），
    末尾 N 个为输出相移屏 ψ。层内门互不相交 ⇒ 层内顺序**不影响**结果（可机器验证）。
    """
    n = int(n_modes)
    xs = np.asarray(x, dtype=float)
    P = param_count(n, layers)
    if xs.shape != (P,):
        raise SubmanifoldError("x 长度须为 %d（= 2g + N），得到 %d" % (P, xs.shape[0]))
    if not all(layer_is_matching(n, L) for L in layers):
        raise SubmanifoldError("layers 含非匹配层（共享模 / 越界）")
    U = np.eye(n, dtype=complex)
    k = 0
    for L in layers:
        for (p, q) in L:
            g = MMM.mzi_unit_cell(float(xs[2 * k]), float(xs[2 * k + 1]))
            G = np.eye(n, dtype=complex)
            G[p, p] = g[0, 0]; G[p, q] = g[0, 1]
            G[q, p] = g[1, 0]; G[q, q] = g[1, 1]
            U = G @ U
            k += 1
    psi = xs[2 * k:2 * k + n]
    return np.diag(np.exp(1j * psi)) @ U


def _flat_real(U: np.ndarray) -> np.ndarray:
    return np.concatenate([U.real.ravel(), U.imag.ravel()])


def reachable_dim(n_modes: int, layers: Sequence[Sequence[Pair]], *,
                  seed: int = 0, h: float = 1e-7, tol_rel: float = 1e-7,
                  n_samples: int = 2) -> int:
    """★ **可及自由度**：可达子流形在一般点的维数 = 参数映射的雅可比秩（数值实测）。

    中心差分构造 `J ∈ R^{2N²×P}` → SVD → 数 `sv > tol_rel·sv_max` 的个数 ⇒ 秩。
    取 `n_samples` 个随机点的**最大**秩（秩是一般性质；退化点是零测集）。

    🔴 这是**实测**：它不是解析证明。零参数（空序列）⇒ 秩 0（只有相移屏也不改变 dim？）
       —— 空序列时 P = N（仅相移屏），Φ 的值域是 N 个相位 ⇒ 秩 = N（对角相位流形维 N）。
    """
    n = int(n_modes)
    if not all(layer_is_matching(n, L) for L in layers):
        raise SubmanifoldError("layers 含非匹配层")
    P = param_count(n, layers)
    if P == 0:
        return 0
    best = 0
    for s in range(max(1, int(n_samples))):
        rng = np.random.default_rng(int(seed) * 1000 + s)
        x = rng.uniform(0.0, 2.0 * np.pi, P)
        J = np.zeros((2 * n * n, P))
        for i in range(P):
            xp = x.copy(); xp[i] += h
            xm = x.copy(); xm[i] -= h
            J[:, i] = (_flat_real(build_submanifold_unitary(n, layers, xp))
                       - _flat_real(build_submanifold_unitary(n, layers, xm))) / (2.0 * h)
        sv = np.linalg.svd(J, compute_uv=False)
        r = int((sv > tol_rel * max(float(sv[0]), 1e-300)).sum())
        best = max(best, r)
    return int(best)


def reachable_dim_report(n_modes: int, layers: Sequence[Sequence[Pair]], **kw: Any) -> Dict[str, Any]:
    """一体化报告：`dim` / 上界 / 缺口 / 门数 / 参数数 / 是否饱和 / 是否通用。"""
    n = int(n_modes)
    g = n_gates(layers)
    dim = reachable_dim(n, layers, **kw)
    ub = saturation_bound(n, layers)
    P = param_count(n, layers)
    nd = universal_dim(n)
    return {
        "n_modes": n,
        "depth": int(len(layers)),
        "n_gates": int(g),
        "param_count": int(P),
        "dim": int(dim),
        "saturation_bound": int(ub),
        "gap_to_bound": int(ub - dim),
        "saturated": bool(dim == ub),
        "universal": bool(dim == nd),
        "universal_dim": int(nd),
        "layer_sizes": [layer_gate_count(L) for L in layers],
        "basis_note": "dim = 雅可比秩（实测）；上界 = min(2g+N, N²)；通用 ⟺ dim = N²。",
    }


# ---------------------------------------------------------------------------
# 3) 设计：交替砖墙 + O-only 饱和见证
# ---------------------------------------------------------------------------
def brick_wall_layers(n_modes: int, depth: int) -> Tuple[Layer, ...]:
    """★ **最优浅电路设计**：交替砖墙 O,E,O,E,…（长度 = depth）。

    D-122 的 Clements 矩形网格在 depth = N 时正是这一结构（⇒ dim = N²）。
    depth 为奇数时以 O 结尾（O 比 E 多一门，优先多门）。
    """
    n = int(n_modes)
    d = int(depth)
    if d < 0:
        raise SubmanifoldError("depth ≥ 0")
    O, E = odd_pairs(n), even_pairs(n)
    return tuple((O if i % 2 == 0 else E) for i in range(d))


def brick_wall_gate_count(n_modes: int, depth: int) -> int:
    """砖墙门数闭式：`⌈D/2⌉·|O| + ⌊D/2⌋·|E|`（|O| = ⌊N/2⌋、|E| = ⌊(N−1)/2⌋）。"""
    n, d = int(n_modes), int(depth)
    no = len(odd_pairs(n))
    ne = len(even_pairs(n))
    return int(((d + 1) // 2) * no + (d // 2) * ne)


def o_only_layers(n_modes: int, depth: int) -> Tuple[Layer, ...]:
    """O-only（全最大匹配）序列 —— **参数计数的陷阱见证**（dim 恒 2N）。"""
    n, d = int(n_modes), int(depth)
    if d < 0:
        raise SubmanifoldError("depth ≥ 0")
    return tuple([odd_pairs(n)] * d)


def saturation_witness(n_modes: int, depth: int, **kw: Any) -> Dict[str, Any]:
    """★ 定量见证「参数计数 ≠ 可及自由度」：O-only vs 砖墙（同 D）。

    O-only：可达集 = (U(2))^{N/2} ⇒ dim = 4·⌊N/2⌋ = **2N**（与 D 无关，D ≥ 1）。
    砖墙：dim = min(2·g_bw(D) + N, N²) —— 逐点达到上界。
    """
    n, d = int(n_modes), int(depth)
    o = reachable_dim_report(n, o_only_layers(n, d), **kw)
    bw = reachable_dim_report(n, brick_wall_layers(n, d), **kw)
    deltas = {
        "gate_count_ratio_o_over_bw": (float(o["n_gates"]) / float(bw["n_gates"])
                                       if bw["n_gates"] else None),
        "dim_gain_bw_over_o": int(bw["dim"] - o["dim"]),
        "o_dim_is_2N": bool(o["dim"] == 2 * n),
        "o_saturates_its_block_diagonal_manifold": bool(o["dim"] == 2 * n),
    }
    return {
        "n_modes": n, "depth": d,
        "o_only": o, "brick_wall": bw, "deltas": deltas,
        "verdict": (f"同 D={d}：O-only 门数 {o['n_gates']}（更多）但 dim 仅 {o['dim']}（= 2N = {2 * n}，"
                    f"块对角 ⇒ 与 D 无关）；砖墙门数 {bw['n_gates']} 却 dim {bw['dim']}"
                    f"（上界 {bw['saturation_bound']}，缺口 {bw['gap_to_bound']}）"
                    f"⇒ **门多 ≠ 自由度高**（D-121 §2b 的定量版）。"),
    }


def _random_design(n_modes: int, depth: int, n_trials: int, seed: int, **kw: Any) -> Dict[str, Any]:
    """随机层序列基线（对照砖墙用）。"""
    n, d = int(n_modes), int(depth)
    rng = np.random.default_rng(int(seed))
    pool = path_matchings(n)
    best: Optional[Tuple[int, Layer]] = None
    tot = 0
    for _ in range(max(1, int(n_trials))):
        seq = tuple(pool[int(rng.integers(0, len(pool)))] for _ in range(d))
        r = reachable_dim(n, seq, n_samples=1)
        tot += 1
        if best is None or r > best[0]:
            best = (r, seq)
    return {"n_modes": n, "depth": d, "n_trials": tot,
            "best_dim": int(best[0]) if best else 0,
            "best_layers": list(best[1]) if best else [],
            "saturation_bound_of_best": saturation_bound(n, best[1]) if best else 0}


def design_shallow(n_modes: int, depth: int, *, method: str = "brick_wall",
                   beam_width: int = 4, n_trials: int = 40, seed: int = 0,
                   max_exhaustive: int = 4000, **kw: Any) -> Dict[str, Any]:
    """在深度预算 D 下**最大化可及自由度**：返回最优/最佳已知层序列。

    method:
      · `"brick_wall"`（默认，闭式设计，O(D) 代价）；
      · `"exhaustive"`（仅小 N·D：穷举全部匹配序列 —— 真·最优，附反证「无更优」）；
      · `"beam"`（beam search，代价 O(D·w·|M|)）；
      · `"random"`（随机基线）。
    返回含 `brick_wall` 对照与 `optimal_claim`（诚实标注证据强度）。
    """
    n, d = int(n_modes), int(depth)
    bw_layers = brick_wall_layers(n, d)
    bw = reachable_dim_report(n, bw_layers, **kw)
    out: Dict[str, Any] = {"n_modes": n, "depth": d, "method": method, "brick_wall": bw}
    pool = path_matchings(n)
    if method == "brick_wall":
        out.update({"best_layers": list(bw_layers), "best_dim": bw["dim"],
                    "best_bound": bw["saturation_bound"],
                    "beats_brick_wall": False,
                    "optimal_claim": "闭式设计；最优性由 exhaustive/beam 在 N≤8 上反证（见门禁 D 节）"})
        return out
    if method == "exhaustive":
        n_comb = len(pool) ** d
        if n_comb > int(max_exhaustive):
            raise SubmanifoldError("穷举组合数 %d > 上限 %d（换 beam）" % (n_comb, max_exhaustive))
        best: Optional[Tuple[int, Layer]] = None
        for seq in itertools.product(pool, repeat=d):
            r = reachable_dim(n, seq, n_samples=1)
            if best is None or r > best[0]:
                best = (r, seq)
        out.update({"best_layers": list(best[1]), "best_dim": int(best[0]),
                    "best_bound": saturation_bound(n, best[1]),
                    "combinations": int(n_comb),
                    "beats_brick_wall": bool(best[0] > bw["dim"]),
                    "optimal_claim": "真·最优（穷举全部 %d 个匹配序列）" % n_comb})
        return out
    if method == "beam":
        beam: List[Tuple[int, Layer]] = [(0, tuple())]
        for _ in range(d):
            cand: List[Tuple[int, Layer]] = []
            for _sc, seq in beam:
                for m in pool:
                    ns = seq + (m,)
                    cand.append((reachable_dim(n, ns, n_samples=1), ns))
            cand.sort(key=lambda t: (-t[0], t[1]))
            beam = cand[:max(1, int(beam_width))]
        bd, bs = beam[0]
        out.update({"best_layers": list(bs), "best_dim": int(bd),
                    "best_bound": saturation_bound(n, bs),
                    "beam_width": int(beam_width),
                    "beats_brick_wall": bool(bd > bw["dim"]),
                    "optimal_claim": "beam(width=%d) 最佳已知；非全局最优证明" % int(beam_width)})
        return out
    if method == "random":
        rd = _random_design(n, d, n_trials, seed)
        out.update({"best_layers": rd["best_layers"], "best_dim": rd["best_dim"],
                    "random": rd,
                    "beats_brick_wall": bool(rd["best_dim"] > bw["dim"]),
                    "optimal_claim": "随机基线（%d 次）" % rd["n_trials"]})
        return out
    raise SubmanifoldError("method=%r 非法（brick_wall/exhaustive/beam/random）" % (method,))


def dof_curve(n_modes: int, *, d_max: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
    """可及自由度曲线（砖墙设计 vs O-only 陷阱），D = 0..d_max。

    对偶报告 **参数计数**（D-121 口径的量）与 **实测 dim** ⇒ 直接暴露「计数会骗人」。
    """
    n = int(n_modes)
    dm = int(d_max) if d_max is not None else n
    rows = []
    for d in range(dm + 1):
        bw = reachable_dim_report(n, brick_wall_layers(n, d), **kw)
        o = reachable_dim_report(n, o_only_layers(n, d), **kw)
        rows.append({
            "D": d,
            "bw_n_gates": bw["n_gates"], "bw_param_count": bw["param_count"],
            "bw_bound": bw["saturation_bound"], "bw_dim": bw["dim"],
            "bw_gap": bw["gap_to_bound"], "bw_universal": bw["universal"],
            "o_n_gates": o["n_gates"], "o_bound": o["saturation_bound"], "o_dim": o["dim"],
            "o_dim_over_param_count": (float(o["dim"]) / float(o["param_count"])
                                       if o["param_count"] else None),
        })
    return {"n_modes": n, "d_max": dm, "rows": rows,
            "headline": "砖墙逐点达到上界 min(2g+N, N²)；O-only 门数更多却 dim 恒 2N。"}


def universality_frontier(n_modes: int, *, d_max: Optional[int] = None, **kw: Any) -> Dict[str, Any]:
    """★ **通用前沿**：使 `dim = N²` 的最小深度 `D*`，并与 D-121/D-122 交叉核对。

    预期：`D* = N`（偶 N）。
      · 与 D-122 矩形网格深度 N（`rect_mesh` 紧界可达）一致；
      · 与 D-121 相邻耦合**紧**界 N（`tight_depth_lower_bound`）一致；
      · 且 `dim(D*−1) < N²` ⇒ 坐实参数界 N−1 **不可达**。
    """
    n = int(n_modes)
    cap = int(d_max) if d_max is not None else (n + 2)
    dims = {d: reachable_dim(n, brick_wall_layers(n, d), **kw) for d in range(0, cap + 1)}
    nd = universal_dim(n)
    d_star = next((d for d in sorted(dims) if dims[d] == nd), None)
    return {
        "n_modes": n,
        "universal_dim": nd,
        "d_star": d_star,
        "dim_by_depth": {int(k): int(v) for k, v in sorted(dims.items())},
        "dim_at_d_star_minus_1": (int(dims[d_star - 1]) if d_star and d_star - 1 in dims else None),
        "param_count_bound_D121_style": int(-(-(n * (n - 1) // 2) // (n // 2))),
        "tight_adjacency_bound_D121": int(n if n > 2 else 1),
        "frontier_equals_N": bool(d_star == n),
        "verdict": (f"D* = {d_star}（= N）；D = {d_star - 1 if d_star else None} 时 dim = "
                    f"{dims.get((d_star - 1) if d_star else 0)} < N² = {nd} ⇒ "
                    "参数计数下界 N−1 **不可达**（与 D-121 紧界 N、D-122 矩形深度 N 三方一致）。"),
    }


# ---------------------------------------------------------------------------
# 4) 自检（判据由 run_submanifold_smoke.py 常驻守护）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """本模块自检（13 条）：层/门数/参数/上界/实测秩/饱和见证/前沿/护栏/披露。"""
    res: Dict[str, bool] = {}

    # ① 层原语
    res["① O/E 原语：|O|=⌊N/2⌋、|E|=⌊(N−1)/2⌋、均为匹配；N=4 时 |O|=2、|E|=1"] = (
        layer_gate_count(odd_pairs(4)) == 2 and layer_gate_count(even_pairs(4)) == 1
        and layer_is_matching(4, odd_pairs(4)) and layer_is_matching(4, even_pairs(4)))

    # ② 匹配判定反向
    res["② ★反向★ 非匹配层（共享模 (0,1),(1,2)）⇒ layer_is_matching 必 False"] = (
        layer_is_matching(4, ((0, 1), (1, 2))) is False
        and layer_is_matching(4, ((0, 1), (3, 4))) is False)   # 越界

    # ③ 匹配枚举
    res["③ P_N 匹配枚举计数：N=4 ⇒ 5、N=6 ⇒ 13（含空层）"] = (
        len(path_matchings(4)) == 5 and len(path_matchings(6)) == 13)

    # ④ 参数/上界闭式
    res["④ P = 2g + N；上界 = min(2g+N, N²)（N=8, D=8 砖墙：g=28, P=64, ub=64）"] = (
        param_count(8, brick_wall_layers(8, 8)) == 64
        and brick_wall_gate_count(8, 8) == 28
        and saturation_bound(8, brick_wall_layers(8, 8)) == 64)

    # ⑤ 砖墙门数闭式与逐层和一致
    res["⑤ 砖墙门数闭式 ≡ 逐层求和（N=6/8，D=0..9）"] = all(
        brick_wall_gate_count(n, d) == n_gates(brick_wall_layers(n, d))
        for n in (6, 8) for d in range(10))

    # ⑥ 🔴 O-only 饱和：dim 恒 2N（N=4/6/8，D=1..3）
    res["⑥ 🔴 O-only 饱和见证：dim ≡ 2N（与 D 无关）"] = all(
        reachable_dim(n, o_only_layers(n, d), n_samples=1) == 2 * n
        for n in (4, 6, 8) for d in (1, 2, 3))

    # ⑦ 砖墙 dim = min(2g+N, N²)（N=4/6/8，D=0..N）
    res["⑦ ★砖墙达上界★ dim ≡ min(2·g_bw + N, N²)（N=4/6/8，D=0..N）"] = all(
        reachable_dim(n, brick_wall_layers(n, d), n_samples=1)
        == saturation_bound(n, brick_wall_layers(n, d))
        for n in (4, 6, 8) for d in range(n + 1))

    # ⑧ 前沿 D* = N
    res["⑧ ★通用前沿★ D* = N 且 dim(D*−1) < N²（N=4/6）"] = all(
        universality_frontier(n, d_max=n + 1)["frontier_equals_N"]
        and universality_frontier(n, d_max=n + 1)["dim_at_d_star_minus_1"] < n * n
        for n in (4, 6))

    # ⑨ 空序列：仅相移屏 ⇒ dim = N
    res["⑨ 空序列（无门）⇒ dim = N（只有相移屏）"] = (
        reachable_dim(4, tuple()) == 4 and reachable_dim(4, ((),)) == 4)

    # ⑩ 层内顺序无关（匹配 ⇒ 对易）
    res["⑩ 层内门顺序无关（匹配 ⇒ 对易）：同一层两顺序参数重排后 U 相同"] = _order_invariance_ok()

    # ⑪ 设计：穷举 N=4 ⇒ 砖墙最优（无更优）
    ex = design_shallow(4, 3, method="exhaustive", max_exhaustive=100000)
    res["⑪ ★最优性★ N=4 穷举全部匹配序列 ⇒ 无序列优于砖墙（beats=False）"] = (
        ex["beats_brick_wall"] is False and ex["best_dim"] >= ex["brick_wall"]["dim"])

    # ⑫ beam 反证（N=6, D≤4）
    res["⑫ beam(4) 反证：N=6/D≤4 无更优（beats=False）"] = all(
        design_shallow(6, d, method="beam", beam_width=4)["beats_brick_wall"] is False
        for d in (2, 3, 4))

    # ⑬ 披露齐备 + 红线
    res["⑬ 披露键 %d 条逐键非空且含 dim_is_measured/search_is_bounded/no_llm"
        % len(SUBMANIFOLD_DISCLOSURE)] = (
        len(SUBMANIFOLD_DISCLOSURE) >= 9
        and all(isinstance(v, str) and v.strip() for v in SUBMANIFOLD_DISCLOSURE.values())
        and "dim_is_measured" in SUBMANIFOLD_DISCLOSURE
        and "search_is_bounded" in SUBMANIFOLD_DISCLOSURE
        and "no_llm" in SUBMANIFOLD_DISCLOSURE)

    if verbose:
        for k, v in res.items():
            print("[%s] %s" % ("PASS" if v else "FAIL", k))
    return bool(all(res.values()))


def _order_invariance_ok() -> bool:
    """同层内两门（不相交）交换顺序 ⇒ 传递矩阵相同（对易 ⇒ 顺序无关）。

    注意：交换层内对序时，**参数也要跟着对走**（否则测的是「参数重排」而非「对易」）。
    """
    n = 4
    ga = (0.3, 0.7)          # 作用在 (0,1) 的门
    gb = (1.1, 2.0)          # 作用在 (2,3) 的门
    psi = (0.2, 0.4, 0.6, 0.8)
    xa = np.array([ga[0], ga[1], gb[0], gb[1], psi[0], psi[1], psi[2], psi[3]])
    xb = np.array([gb[0], gb[1], ga[0], ga[1], psi[0], psi[1], psi[2], psi[3]])
    Ua = build_submanifold_unitary(n, (((0, 1), (2, 3)),), xa)
    Ub = build_submanifold_unitary(n, (((2, 3), (0, 1)),), xb)
    return bool(np.max(np.abs(Ua - Ub)) < 1e-12)


if __name__ == "__main__":                                  # 自测：打真实数字
    ok = run_selfchecks(verbose=True)
    print("=" * 82)
    print("submanifold（D-127）自检：%s" % ("全绿" if ok else "有红"))
    for n in (4, 6, 8):
        c = dof_curve(n)
        print(f"=== N={n} 可及自由度曲线（砖墙 vs O-only）===")
        print("  D | 砖墙 g  P   ub  dim | O-only g  ub  dim | 通用")
        for r in c["rows"]:
            print("  %2d | %6d %3d %4d %4d | %7d %4d %4d | %s"
                  % (r["D"], r["bw_n_gates"], r["bw_param_count"], r["bw_bound"], r["bw_dim"],
                     r["o_n_gates"], r["o_bound"], r["o_dim"], r["bw_universal"]))
        f = universality_frontier(n)
        print("  D* =", f["d_star"], "| dim(D*−1) =", f["dim_at_d_star_minus_1"],
              "| 与 D-121 紧界", f["tight_adjacency_bound_D121"], "一致:",
              f["frontier_equals_N"])
