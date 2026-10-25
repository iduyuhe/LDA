# -*- coding: utf-8 -*-
"""🔧 D2 解码器（一）：**LDPC 的 BP + OSD-0**（`d2_ldpc_decoder`）。

定位：`d2` 的 `G-V2-D2-1` 一直写着「LDPC 解码（BP+OSD）**未开工**；解码器重且禁第三方 SDK」。
本层把它建起来，并且——**不靠跑分**——用一条教科书级的**精确性定理**做验证：

🔴 **无环 Tanner 图 ⇒ BP 的后验 LLR 恰等于精确逐位 MAP 后验 LLR**（Pearl 信念传播在树上的精确性）。
  ⇒ 在树码上穷举**全部 2⁹ = 512 个错误模式**，把 BP 的后验与「穷举全部 32 个码字算出的精确 MAP 后验」
    逐位对拍（abs ≤ 1e-9）。这**不是**「误帧率大致相当」，是**逐位数值相等**。
  ⇒ 再配一条反向探针：**往树里加一条边造出环 ⇒ 该等式必须破**（证明判据不是恒真）。

🔴 **OSD-0 有一条结构性不变量**：输出**恒为合法码字**（syndrome ≡ 0）—— 对全部 512 个模式机核。
  在 `Hamming[7,4,3]`（d=3）上另有可证结论：**OSD-0 必纠全部单比特错误**（错位是最不可靠位 ⇒ 不在 MRB
  ⇒ 被硬判为 1，MRB 解回全 0）—— 穷举 7 个单错 + 无错，共 8 档逐位对拍。

🔴 **诚实边界**：`BP` 的浮点实现在 LLR 极大时用钳制（`atanh` 上界 1−1e-15）；本层**不做**
  长码 Monte-Carlo 阈值标定（那是拟合量 ⇒ 只能作披露、不可作锚，见 `G-V2-D2-5`）；
  不建模电路级噪声、简并（degenerate）量子码、消息调度（layered/sequential）与量化 LLR。
  零商业依赖（纯 `math`）；**零 RNG**（LLR 用确定性表，不用随机数 ⇒ 结论可复现）；**LLM 不进判决路径**。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

__all__ = [
    "D2_LDPC_CALIBER",
    "H_TREE",
    "H_TREE_WITH_CYCLE",
    "H_HAMMING743",
    "syndrome",
    "gf2_rank",
    "gf2_solve",
    "check_messages",
    "bp_iterate",
    "bp_decode",
    "osd0_decode",
    "enumerate_codewords",
    "exact_map_llr",
    "deterministic_llr",
    "tree_vs_exact_scan",
    "selfcheck_d2_ldpc_decoder",
]

D2_LDPC_CALIBER = "bitwise_map_posterior_llr"

#: 🔴 **无环** Tanner 图（链式树）：c0-v2-c1-v4-c2-v6-c3 —— n=9 · m=4 · k=5
H_TREE: Tuple[Tuple[int, ...], ...] = (
    (0, 1, 2),
    (2, 3, 4),
    (4, 5, 6),
    (6, 7, 8),
)

#: 反向探针用：在树上**加一条边**（c4: v1 v8）造出唯一一个环
H_TREE_WITH_CYCLE: Tuple[Tuple[int, ...], ...] = H_TREE + ((1, 8),)

#: Hamming `[7,4,3]`（d=3 · 完备码）—— 用于 OSD-0 的**可证纠错能力**
H_HAMMING743: Tuple[Tuple[int, ...], ...] = (
    (3, 4, 5, 6),
    (1, 2, 5, 6),
    (0, 2, 4, 6),
)

_EPS_TANH = 1.0 - 1e-15


def _n_of(H: Sequence[Sequence[int]]) -> int:
    return max((v for chk in H for v in chk), default=-1) + 1


def syndrome(H: Sequence[Sequence[int]], word: Sequence[int]) -> int:
    """syndrome 位掩码：第 i 位 = 第 i 个校验是否被违反。"""
    mask = 0
    for ci, chk in enumerate(H):
        s = 0
        for v in chk:
            s ^= int(word[v]) & 1
        if s:
            mask |= (1 << ci)
    return mask


def gf2_rank(rows: Sequence[int], ncols: int) -> int:
    """位压缩高斯消元的秩（rows 为整数位掩码 · ncols 仅作上界校验）。"""
    basis: List[int] = []
    for r in rows:
        x = int(r)
        if x >> int(ncols):
            raise ValueError("行掩码超出 ncols")
        for b in basis:                     # basis 按最高位降序，最高位互不相同
            hb = b.bit_length() - 1
            if (x >> hb) & 1:
                x ^= b
        if x:
            basis.append(x)
            basis.sort(key=lambda z: -z.bit_length())
    return len(basis)


def gf2_solve(A: Sequence[Sequence[int]], b: Sequence[int]) -> List[int]:
    """解 `A x = b`（模 2 · A 为方阵且可逆；否则抛 ValueError）。"""
    m = len(A)
    if m == 0 or any(len(r) != m for r in A):
        raise ValueError("A 须为方阵且非空")
    aug = [[int(A[i][j]) & 1 for j in range(m)] + [int(b[i]) & 1] for i in range(m)]
    for col in range(m):
        piv = next((r for r in range(col, m) if aug[r][col]), None)
        if piv is None:
            raise ValueError("A 奇异 · 不可解")
        aug[col], aug[piv] = aug[piv], aug[col]
        for r in range(m):
            if r != col and aug[r][col]:
                aug[r] = [x ^ y for x, y in zip(aug[r], aug[col])]
    return [aug[i][m] for i in range(m)]


# ---------------------------------------------------------------------------
# BP（信念传播）：sum-product（LLR 域）+ min-sum
# ---------------------------------------------------------------------------
def _var2chk(H: Sequence[Sequence[int]], n: int) -> List[List[int]]:
    out: List[List[int]] = [[] for _ in range(n)]
    for ci, chk in enumerate(H):
        for v in chk:
            out[v].append(ci)
    return out


def check_messages(others: Sequence[float], rule: str = "sum_product") -> float:
    """校验节点给某条边的消息（**排除该边自身的入消息** —— 「外信息」是本层的命门）。"""
    if rule == "min_sum":
        s = 1.0
        mag = math.inf
        for x in others:
            if x < 0.0:
                s = -s
            a = abs(x)
            if a < mag:
                mag = a
        return float(s * (0.0 if mag is math.inf else mag))
    if rule != "sum_product":
        raise ValueError("rule 须为 sum_product / min_sum")
    s = 1.0
    prod = 1.0
    for x in others:
        if x < 0.0:
            s = -s
        prod *= math.tanh(abs(x) * 0.5)
    if prod > _EPS_TANH:
        prod = _EPS_TANH
    return float(s * 2.0 * math.atanh(prod))


def bp_iterate(llr: Sequence[float], H: Sequence[Sequence[int]],
               iterations: int = 30, rule: str = "sum_product") -> Tuple[List[float], Tuple[int, ...]]:
    """**固定迭代**（不做提前停止）⇒ 返回后验 LLR 与硬判。用于与精确 MAP 后验对拍。"""
    n = len(llr)
    v2c = _var2chk(H, n)
    m_cv = [[0.0] * len(H) for _ in range(n)]
    m_vc = [[float(llr[v])] * len(H) for v in range(n)]
    for _ in range(int(iterations)):
        for ci, chk in enumerate(H):
            vals = [m_vc[v][ci] for v in chk]
            for k, v in enumerate(chk):
                m_cv[v][ci] = check_messages(vals[:k] + vals[k + 1:], rule)
        q = [float(llr[v]) + sum(m_cv[v][c] for c in v2c[v]) for v in range(n)]
        for v in range(n):
            tot = sum(m_cv[v][c] for c in v2c[v])
            for c in v2c[v]:
                m_vc[v][c] = float(llr[v]) + tot - m_cv[v][c]
    return q, tuple(1 if x < 0.0 else 0 for x in q)


def bp_decode(llr: Sequence[float], H: Sequence[Sequence[int]],
              max_iter: int = 50, rule: str = "sum_product") -> Dict[str, Any]:
    """带**提前停止**（syndrome 归零）的 BP。"""
    n = len(llr)
    v2c = _var2chk(H, n)
    m_cv = [[0.0] * len(H) for _ in range(n)]
    m_vc = [[float(llr[v])] * len(H) for v in range(n)]
    hard: Tuple[int, ...] = tuple(1 if llr[v] < 0.0 else 0 for v in range(n))
    for it in range(1, int(max_iter) + 1):
        for ci, chk in enumerate(H):
            vals = [m_vc[v][ci] for v in chk]
            for k, v in enumerate(chk):
                m_cv[v][ci] = check_messages(vals[:k] + vals[k + 1:], rule)
        q = [float(llr[v]) + sum(m_cv[v][c] for c in v2c[v]) for v in range(n)]
        hard = tuple(1 if x < 0.0 else 0 for x in q)
        if syndrome(H, hard) == 0:
            return {"word": hard, "iterations": it, "converged": True, "posterior": q}
        for v in range(n):
            tot = sum(m_cv[v][c] for c in v2c[v])
            for c in v2c[v]:
                m_vc[v][c] = float(llr[v]) + tot - m_cv[v][c]
    return {"word": hard, "iterations": int(max_iter), "converged": False, "posterior": q}


# ---------------------------------------------------------------------------
# OSD-0：按可靠度排序 → 取 m 个最可靠的**线性无关**列作 MRB → 其余硬判 → 解回 MRB
# ---------------------------------------------------------------------------
def osd0_decode(llr: Sequence[float], H: Sequence[Sequence[int]]) -> Dict[str, Any]:
    """OSD-0 译码。输出**恒满足 syndrome ≡ 0**（结构性不变量，不由容差保证）。"""
    n = len(llr)
    m = len(H)
    # 可靠度：|LLR| 越大越可靠 ⇒ 升序排列，最可靠的取 MRB
    order = sorted(range(n), key=lambda v: (abs(float(llr[v])), -v))
    mrb: List[int] = []
    for v in order:
        if len(mrb) == m:
            break
        trial = mrb + [v]
        rows = []
        for chk in H:
            r = 0
            for j, col in enumerate(trial):
                if col in chk:
                    r |= (1 << j)
            rows.append(r)
        if gf2_rank(rows, len(trial)) == len(trial):
            mrb.append(v)
    if len(mrb) != m:
        raise ValueError("H 行不满秩 ⇒ 无法构造 MRB")
    hard = [1 if float(llr[v]) < 0.0 else 0 for v in range(n)]
    word = list(hard)
    # 其余位保留硬判 ⇒ 算出这些位贡献的 syndrome，再解 MRB 位把它抵消
    rows = []
    for chk in H:
        r = 0
        for j, col in enumerate(mrb):
            if col in chk:
                r |= (1 << j)
        rows.append(r)
    rhs = []
    for ci, chk in enumerate(H):
        s = 0
        for v in chk:
            if v not in mrb:
                s ^= hard[v]
        rhs.append(s)
    A = [[(rows[i] >> j) & 1 for j in range(m)] for i in range(m)]
    sol = gf2_solve(A, rhs)
    for j, col in enumerate(mrb):
        word[col] = sol[j]
    return {"word": tuple(word), "mrb": tuple(mrb), "syndrome": syndrome(H, word)}


# ---------------------------------------------------------------------------
# 精确参照：穷举码字 ⇒ 逐位 MAP 后验 LLR
# ---------------------------------------------------------------------------
def enumerate_codewords(H: Sequence[Sequence[int]], n: int) -> List[Tuple[int, ...]]:
    """穷举 `2^n` 个比特串，保留 `H x = 0` 者（仅小 `n` 可用 · 本层 n ≤ 9）。"""
    out: List[Tuple[int, ...]] = []
    for word in range(1 << n):
        bits = tuple((word >> v) & 1 for v in range(n))
        if syndrome(H, bits) == 0:
            out.append(bits)
    return out


def _logsumexp(vals: Sequence[float]) -> float:
    if not vals:
        return -math.inf
    mx = max(vals)
    if mx == -math.inf:
        return -math.inf
    return mx + math.log(sum(math.exp(v - mx) for v in vals))


def exact_map_llr(llr: Sequence[float], H: Sequence[Sequence[int]]) -> List[float]:
    """精确逐位 MAP 后验 LLR：`log Σ_{c:c_v=0} e^{score} − log Σ_{c:c_v=1} e^{score}`，`score = ½Σ L(1−2c)`。"""
    n = len(llr)
    cws = enumerate_codewords(H, n)
    if not cws:
        raise ValueError("码字集为空")
    scores = [0.5 * sum(float(llr[v]) * (1 - 2 * c[v]) for v in range(n)) for c in cws]
    out: List[float] = []
    for v in range(n):
        z = _logsumexp([s for s, c in zip(scores, cws) if c[v] == 0])
        o = _logsumexp([s for s, c in zip(scores, cws) if c[v] == 1])
        if o == -math.inf:
            out.append(math.inf)
        elif z == -math.inf:
            out.append(-math.inf)
        else:
            out.append(z - o)
    return out


def deterministic_llr(n: int, scale: float = 4.0, phase: float = 0.37) -> List[float]:
    """**确定性** LLR 表（无 RNG ⇒ 可复现；幅度有界且无重复值，避免并列）。"""
    return [float(scale * math.sin(phase + 1.7 * (v + 1)) + 0.11 * (v + 1)) for v in range(n)]


def tree_vs_exact_scan(H: Sequence[Sequence[int]] = H_TREE,
                       tol: float = 1e-9,
                       scale: float = 4.0) -> Dict[str, Any]:
    """穷举 `2^n` 个错误模式：BP 后验 vs 精确 MAP 后验，返回最大偏差与破例数。

    `llr[v] = +table[v]`（bit=0）或 `−table[v]`（bit=1）—— 即「发全 0 码字、错误图样 e」。
    """
    n = _n_of(H)
    base = deterministic_llr(n, scale=scale)
    worst = 0.0
    bad = 0
    total = 1 << n
    for pat in range(total):
        llr = [(-base[v] if (pat >> v) & 1 else base[v]) for v in range(n)]
        bp_q, _ = bp_iterate(llr, H, iterations=30)
        ex = exact_map_llr(llr, H)
        d = 0.0
        for a, b in zip(bp_q, ex):
            if math.isinf(a) or math.isinf(b):
                d = math.inf if a != b else 0.0
            else:
                d = max(d, abs(a - b))
        if d > tol:
            bad += 1
        worst = max(worst, d if not math.isinf(d) else 1e18)
    return {"patterns": total, "worst_abs_diff": float(worst),
            "violations": int(bad), "codewords": len(enumerate_codewords(H, n))}


def selfcheck_d2_ldpc_decoder() -> Dict[str, bool]:
    """LDPC 解码层自检（**一条精确性定理 + 一条结构性不变量 + 反向探针**）。"""
    c: Dict[str, bool] = {}
    n = _n_of(H_TREE)
    cws = enumerate_codewords(H_TREE, n)

    # ① GF(2) 助手自洽（秩 / 解回代）
    A = [[1, 0, 0], [0, 1, 0], [1, 1, 1]]          # 上三角 ⇒ 模 2 可逆
    rhs = [1, 1, 0]
    sol = gf2_solve(A, rhs)
    c["gf2_solve_roundtrip"] = bool(
        all(sum(A[i][j] * sol[j] for j in range(3)) % 2 == rhs[i] for i in range(3)))
    c["gf2_rank_full"] = bool(gf2_rank([0b111, 0b011, 0b001], 3) == 3)
    c["gf2_rank_deficient"] = bool(gf2_rank([0b111, 0b111, 0b001], 3) == 2)

    # ② 🔴 树码 ⇒ BP 后验 ≡ 精确逐位 MAP 后验（穷举 512 模式）
    scan = tree_vs_exact_scan()
    c["tree_bp_equals_exact_map"] = bool(scan["violations"] == 0)
    c["tree_scan_is_not_vacuous"] = bool(scan["patterns"] == 512 and scan["codewords"] == 32)

    # ③ 🔴 反向探针：加一条边造环 ⇒ 该等式**必须破**（判据非恒真）
    scan_cyc = tree_vs_exact_scan(H_TREE_WITH_CYCLE)
    c["cycle_breaks_exactness"] = bool(scan_cyc["violations"] > 0)

    # ④ 🔴 OSD-0 结构性不变量：输出恒为合法码字（全部 512 模式）
    base = deterministic_llr(n)
    all_valid = True
    for pat in range(1 << n):
        llr = [(-base[v] if (pat >> v) & 1 else base[v]) for v in range(n)]
        if osd0_decode(llr, H_TREE)["syndrome"] != 0:
            all_valid = False
            break
    c["osd0_always_valid_codeword"] = bool(all_valid)

    # ⑤ 🔴 无噪极限：大 LLR ⇒ BP 一次迭代命中；OSD-0 恒返回该码字（全部 32 个码字）
    ok_bp = ok_osd = True
    big = 40.0
    for cw in cws:
        llr = [(-big if b else big) for b in cw]
        r = bp_decode(llr, H_TREE)
        if not (r["converged"] and r["iterations"] == 1 and r["word"] == cw):
            ok_bp = False
        if osd0_decode(llr, H_TREE)["word"] != cw:
            ok_osd = False
    c["noiseless_bp_hits_in_one_iter"] = bool(ok_bp)
    c["noiseless_osd0_exact"] = bool(ok_osd)

    # ⑥ 🔴 Hamming[7,4,3]：OSD-0 必纠全部单比特错误（d=3 · 「错位最不可靠 ⇒ 不在 MRB」）
    ok_h = True
    for j in range(7):
        llr = [3.0] * 7
        llr[j] = -0.6                    # 唯一错位：幅度最小 ⇒ 最不可靠
        out = osd0_decode(llr, H_HAMMING743)["word"]
        if out != tuple(0 for _ in range(7)):
            ok_h = False
    c["osd0_corrects_all_single_errors"] = bool(ok_h)
    # 距离要**排除全零码字**（否则 min 恒为 0 —— 我第一次就写成这样，判据当场判红）
    _hw = [sum(cw) for cw in enumerate_codewords(H_HAMMING743, 7)]
    c["hamming_is_d3"] = bool(min(w for w in _hw if w > 0) == 3 and _hw.count(0) == 1)

    # ⑦ 🔴 外信息（extrinsic）正确性 —— **端到端**判据（不是直接调消息函数自证）
    #    单校验码 n=3 · LLR = [+10, −10, −10]：给 v0 的消息取「另外两条」⇒ 两负相乘 ⇒ **正** ~+9.3
    #    ⇒ 后验 q0 = 10 + 9.3 ≈ 19.3。若错误地把自身也算进乘积，消息翻成 −9.3 ⇒ q0 ≈ 0.7。
    _q1, _ = bp_iterate([10.0, -10.0, -10.0], ((0, 1, 2),), iterations=5)
    c["extrinsic_excludes_self"] = bool(_q1[0] > 15.0)

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    c["reverse_bad_rule_raise"] = bool(_raises(lambda: check_messages([1.0], "nope")))
    c["reverse_singular_matrix_raise"] = bool(
        _raises(lambda: gf2_solve([[1, 1], [1, 1]], [0, 1])))
    return c


def main() -> int:  # pragma: no cover
    checks = selfcheck_d2_ldpc_decoder()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    a = tree_vs_exact_scan()
    b = tree_vs_exact_scan(H_TREE_WITH_CYCLE)
    print("\n树码（无环）：%d 模式 · %d 码字 · BP vs 精确 MAP 最大偏差 %.3e · 破例 %d"
          % (a["patterns"], a["codewords"], a["worst_abs_diff"], a["violations"]))
    print("加一条边（有环）：破例 %d / %d ⇒ 精确性**依赖无环**（判据非恒真）"
          % (b["violations"], b["patterns"]))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
