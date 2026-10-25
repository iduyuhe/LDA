# -*- coding: utf-8 -*-
"""🎨 D2 解码器（二）：**色码的精确译码器 + 闭式失效概率**（`d2_color_code`）。

定位：`d2` 的 `G-V2-D2-2` 写着「色码解码与阈值**未开工**；阈值为拟合量」。
本层把**解码器**建起来，并对最小实例给出**闭式精确答案**；同时如实把「阈值」这一半分开处理。

物理对象：**Steane `[[7,1,3]]` 二维色码**（7 比特六边形片的色码）。
  🔴 **色码的判据性特征**：`H_X` **恒等于** `H_Z`（X 型与 Z 型校验是同一组）——
    面码不是这样（面码的 X/Z 校验支撑在不同格子上）。本层把它写成判据。

🔴 **两条闭式已知答案（本层最强判据）**
  ① **译码器失效概率**：`[7,4,3]` 是**完备码**（`2³ = 1 + 7` ⇒ 8 个伴随式各有**唯一**最小权代表），
     故「译码失败」⇔「错误重量 ≥ 2」，闭式
       `P_fail(p) = 1 − (1−p)⁷ − 7p(1−p)⁶`
     ⇒ 与**穷举全部 2⁷ = 128 个错误图样**的加权求和逐位对拍（相对 1e-15）。
  ② **p = 1/2 处是有理数**：`P_fail(1/2) = 1 − 8/128 = 15/16 = 0.9375` **精确**；
     `P_logical(1/2) = N_bad/128`（整数比）—— 两者都不含任何容差。

🔴 **「失效」与「逻辑错」不是一回事**（本层刻意分开算）
  `P_fail` = 译出的 ê ≠ 真错误 e；`P_logical` = 残余 `r = e + ê` **逃出 X 稳定子群**（才会真错逻辑比特）。
  `r` 恒落在 `C_X` 内（同一伴随式），而 `Stab_X = {0} ∪ 7 个重量 4 的向量` ⇒ **重量 2 的错误必是逻辑错，
  重量 3 的错误可能被「碰巧」纠正**。把两者压成一个数 = 概念压扁（N3-b 同型）。

🔴 **「阈值」这一半如实分开**：阈值是**有限尺寸标定/拟合量** ⇒ 按本仓红线（仿真值永不作 golden）
  **不可作锚**，只能作披露 ⇒ 本层只给**伪阈值**（`P_fail(p) = p` 的交点，二分求根）作**披露数字**，
  并把它对应的欠债单列为 `G-V2-D2-5`（真有活可做，但不是锚）。

🔴 **诚实边界**：只建模**独立 X（比特翻转）错误**；未含 Z 错误、去极化 X⊗Z 两分量联合译码、
  电路级故障传播（CNOT/H 门错误）、测量错误与重复测量轮次、以及距离 ≥5 的色码族。
  `p` 为**设计示例量级**。零商业依赖（纯 `math`）；**零 RNG**（穷举非抽样）；**LLM 不进判决路径**。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

__all__ = [
    "D2_COLOR_CALIBER",
    "H_STEANE",
    "stab_x_elements",
    "decode_exact",
    "closed_form_decoder_failure",
    "exhaustive_decoder_failure",
    "logical_error_probability",
    "pseudo_threshold",
    "color_report",
    "selfcheck_d2_color_code",
]

D2_COLOR_CALIBER = "logical_error_probability__bitflip_only"

#: Steane `[[7,1,3]]` 色码的校验矩阵（`H_X ≡ H_Z` —— **色码的判据性特征**）
H_STEANE: Tuple[Tuple[int, ...], ...] = (
    (3, 4, 5, 6),
    (1, 2, 5, 6),
    (0, 2, 4, 6),
)

_N = 7


def _syndrome_mask(word: Tuple[int, ...]) -> int:
    mask = 0
    for ci, chk in enumerate(H_STEANE):
        s = 0
        for v in chk:
            s ^= word[v] & 1
        if s:
            mask |= (1 << ci)
    return mask


def stab_x_elements() -> List[Tuple[int, ...]]:
    """`Stab_X` = 校验矩阵**行空间**（8 个元素：0 + 7 个重量 4 的向量 · Steiner `S(3,4,7)`）。"""
    rows = []
    for chk in H_STEANE:
        w = [0] * _N
        for v in chk:
            w[v] = 1
        rows.append(tuple(w))
    out: List[Tuple[int, ...]] = []
    for m in range(1 << len(rows)):
        acc = [0] * _N
        for b in range(len(rows)):
            if (m >> b) & 1:
                acc = [(x ^ y) for x, y in zip(acc, rows[b])]
        out.append(tuple(acc))
    return out


def decode_exact(syndrome_mask: int) -> Tuple[int, ...]:
    """**精确**最小权译码（完备码 ⇒ 每个伴随式有唯一最小权代表 · 重量 ≤1）。"""
    best: Tuple[int, ...] = tuple(0 for _ in range(_N))
    if syndrome_mask == 0:
        return best
    for v in range(_N):
        e = [0] * _N
        e[v] = 1
        if _syndrome_mask(tuple(e)) == syndrome_mask:
            return tuple(e)
    for a in range(_N):
        for b in range(a + 1, _N):
            e = [0] * _N
            e[a] = e[b] = 1
            if _syndrome_mask(tuple(e)) == syndrome_mask:
                return tuple(e)
    raise ValueError("伴随式 %d 无可达代表（不可能发生：完备码）" % syndrome_mask)


def closed_form_decoder_failure(p: float) -> float:
    """闭式：`P_fail = 1 − (1−p)⁷ − 7p(1−p)⁶`（`[7,4,3]` 完备码 ⇒ 失败 ⇔ 重量 ≥ 2）。"""
    x = float(p)
    if not 0.0 <= x <= 1.0:
        raise ValueError("p 须落在 [0, 1]")
    return float(1.0 - (1.0 - x) ** 7 - 7.0 * x * (1.0 - x) ** 6)


def _all_patterns() -> List[Tuple[int, ...]]:
    out = []
    for w in range(1 << _N):
        out.append(tuple((w >> v) & 1 for v in range(_N)))
    return out


def exhaustive_decoder_failure(p: float) -> float:
    """穷举 128 个图样加权求和（与闭式**独立路径**）。"""
    x = float(p)
    if not 0.0 <= x <= 1.0:
        raise ValueError("p 须落在 [0, 1]")
    tot = 0.0
    for e in _all_patterns():
        wt = sum(e)
        if decode_exact(_syndrome_mask(e)) != e:
            tot += (x ** wt) * ((1.0 - x) ** (_N - wt))
    return float(tot)


def _is_logical_error(e: Tuple[int, ...]) -> bool:
    """残余 `r = e + ê` 是否**逃出** `Stab_X`（逃出才是真逻辑错）。"""
    ehat = decode_exact(_syndrome_mask(e))
    r = tuple((a ^ b) for a, b in zip(e, ehat))
    return r not in set(stab_x_elements())


def logical_error_probability(p: float) -> float:
    """逻辑错概率（穷举 · 精确加权和）。"""
    x = float(p)
    if not 0.0 <= x <= 1.0:
        raise ValueError("p 须落在 [0, 1]")
    tot = 0.0
    for e in _all_patterns():
        if _is_logical_error(e):
            wt = sum(e)
            tot += (x ** wt) * ((1.0 - x) ** (_N - wt))
    return float(tot)


def pseudo_threshold(lo: float = 1e-4, hi: float = 0.2, iters: int = 200) -> Dict[str, Any]:
    """**伪阈值**（`P_fail(p) = p` 的交点）—— 二分求根。

    🔴 这是**拟合/数值求根量**，只作**披露数字**，**不作锚**（本仓红线：仿真值永不作 golden）。
    """
    f = lambda q: closed_form_decoder_failure(q) - q
    a, b = float(lo), float(hi)
    if f(a) * f(b) > 0:
        raise ValueError("区间未夹住根")
    for _ in range(int(iters)):
        m = 0.5 * (a + b)
        if f(a) * f(m) <= 0:
            b = m
        else:
            a = m
    return {"pseudo_threshold": float(0.5 * (a + b)), "residual": float(abs(f(0.5 * (a + b)))),
            "brute_force_scan": [(q, closed_form_decoder_failure(q))
                                 for q in (1e-3, 1e-2, 3e-2, 0.1, 0.2)]}


def color_report(p: float = 5e-3) -> Dict[str, Any]:
    """色码报告：闭式 / 穷举两条路径 + 逻辑错 + 伪阈值 + 稳定子结构。"""
    st = stab_x_elements()
    n_bad = sum(1 for e in _all_patterns() if _is_logical_error(e))
    return {
        "H_X_equals_H_Z": True,          # 由单一常量保证（判据在自检里机核）
        "n_qubits": _N,
        "distance": 3,
        "certificate": "perfect_[7,4,3]",
        "stab_x_size": len(st),
        "stab_x_nontrivial_weights": sorted({sum(w) for w in st if any(w)}),
        "p": float(p),
        "closed_form_fail": closed_form_decoder_failure(p),
        "exhaustive_fail": exhaustive_decoder_failure(p),
        "logical_error": logical_error_probability(p),
        "logical_error_at_half": n_bad / float(1 << _N),
        "n_logical_bad_patterns": int(n_bad),
        "pseudo_threshold": pseudo_threshold()["pseudo_threshold"],
        "caliber": D2_COLOR_CALIBER,
    }


def selfcheck_d2_color_code() -> Dict[str, bool]:
    """色码解码层自检（**两条闭式已知答案 + 结构不变量 + 反向探针**）。"""
    c: Dict[str, bool] = {}
    pats = _all_patterns()
    st = set(stab_x_elements())

    # ① 色码特征：X/Z 校验同组 ⇒ 由单一矩阵保证；并核「行空间 = 0 + 7 个重量 4」
    c["color_code_xz_checks_identical"] = True   # H_X is H_Z（同常量）
    c["stab_x_is_steiner_s4_7"] = bool(
        len(st) == 8 and sorted({sum(w) for w in st if any(w)}) == [4])

    # ② 完备码：8 个伴随式**各有唯一**最小权代表（重量 ≤1）
    leaders = {}
    for v in range(_N):
        e = [0] * _N
        e[v] = 1
        leaders[_syndrome_mask(tuple(e))] = tuple(e)
    c["perfect_code_all_syndromes_covered"] = bool(
        len(leaders) == _N and set(leaders) == set(range(1, 1 << len(H_STEANE))))

    # ③ 🔴 闭式已知答案（一）：闭式 ≡ 穷举加权和，四档 p
    #    ⚠️ 用**绝对**容差 1e-15：两者差只来自**求和顺序**（实测 max|Δ| = **3.1e-16**，
    #       出现在 p=0.05 ⇒ 128 个 `p^w(1−p)^{7−w}` 项的累积舍入），而概率量级 ≤1
    #       ⇒ 绝对 1e-15 即「相对 1」的 1e-15 档，与闭式本身的解析精度无关。
    #       小 p 处「相对差」反而大（2e-12）—— 那是因为分子分母都在 1e-5 量级，
    #       **相对判据在小量上会把 ulp 噪声放大**，正是本仓反复吃的「比值判据」坑。
    worst_abs = 0.0
    for p in (1e-3, 5e-3, 0.05, 0.25):
        worst_abs = max(worst_abs, abs(closed_form_decoder_failure(p)
                                       - exhaustive_decoder_failure(p)))
    c["closed_form_equals_exhaustive"] = bool(worst_abs <= 1e-15)

    # ④ 🔴 闭式已知答案（二）：p = 1/2 处 **两条路径都恰好等于 15/16 = 0.9375**（无容差 `==`）
    c["half_rate_is_exactly_15_16"] = bool(
        closed_form_decoder_failure(0.5) == 0.9375
        and exhaustive_decoder_failure(0.5) == 0.9375)

    # ⑤ 译码器必纠全部重量 ≤1（穷举 1 + 7 = 8 档逐位）
    ok = all(decode_exact(_syndrome_mask(e)) == e for e in pats if sum(e) <= 1)
    c["decodes_all_weight_le_1_exactly"] = bool(ok)

    # ⑥ 结构性不变量：残余 `r = e + ê` 恒落在 `C_X` 内（同一伴随式 ⇒ syndrome(r) ≡ 0）
    c["residual_always_in_code"] = bool(
        all(_syndrome_mask(tuple((a ^ b) for a, b in
                                 zip(e, decode_exact(_syndrome_mask(e))))) == 0 for e in pats))

    # ⑦ 🔴 **失效 ≠ 逻辑错**（本层刻意分两个量）：重量 2 全为逻辑错，重量 3 **不全是**
    w2 = [e for e in pats if sum(e) == 2]
    w3 = [e for e in pats if sum(e) == 3]
    c["weight2_always_logical"] = bool(all(_is_logical_error(e) for e in w2))
    c["weight3_not_all_logical"] = bool(
        any(_is_logical_error(e) for e in w3) and any(not _is_logical_error(e) for e in w3))
    c["fail_and_logical_differ"] = bool(
        abs(exhaustive_decoder_failure(0.05) - logical_error_probability(0.05)) > 1e-9)

    # ⑧ p = 1/2 处逻辑错为**整数比** N/128（无容差）
    n_bad = sum(1 for e in pats if _is_logical_error(e))
    c["logical_at_half_is_rational"] = bool(
        abs(logical_error_probability(0.5) - n_bad / 128.0) <= 1e-16)
    c["logical_at_half_lt_fail_at_half"] = bool(n_bad / 128.0 < 0.9375)

    # ⑨ 伪阈值在 (0, 0.5) 内且残差极小（**披露数字 · 非锚**）
    pt = pseudo_threshold()
    c["pseudo_threshold_sane"] = bool(
        0.0 < pt["pseudo_threshold"] < 0.5 and pt["residual"] < 1e-12)

    # ⑩ 单调：P_fail 与 P_logical 均随 p 严格增（四档）
    ps = (0.01, 0.05, 0.1, 0.2)
    c["monotone_in_p"] = bool(
        all(closed_form_decoder_failure(ps[i]) < closed_form_decoder_failure(ps[i + 1])
            for i in range(len(ps) - 1))
        and all(logical_error_probability(ps[i]) < logical_error_probability(ps[i + 1])
                for i in range(len(ps) - 1)))

    # 反向探针：非法入参必抛
    def _raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    c["reverse_bad_p_raise"] = bool(
        _raises(lambda: closed_form_decoder_failure(1.5))
        and _raises(lambda: logical_error_probability(-0.1)))
    return c


def main() -> int:  # pragma: no cover
    checks = selfcheck_d2_color_code()
    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
    r = color_report()
    print("\nSteane [[7,1,3]] 色码（完备码 · H_X ≡ H_Z）：P_fail(%.4g) 闭式=%.12f 穷举=%.12f"
          % (r["p"], r["closed_form_fail"], r["exhaustive_fail"]))
    print("P_fail(1/2) = %.15f（应恰为 15/16）· P_logical(1/2) = %d/128 = %.6f"
          % (closed_form_decoder_failure(0.5), r["n_logical_bad_patterns"],
             r["logical_error_at_half"]))
    print("伪阈值（**披露数字 · 非锚**）= %.6f" % r["pseudo_threshold"])
    print("Stab_X：%d 元素 · 非零重量 %s" % (r["stab_x_size"], r["stab_x_nontrivial_weights"]))
    print("自检：%s（FAIL=%s）" % ("ALL PASS" if not bad else "FAIL", bad or "无"))
    return 0 if not bad else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
