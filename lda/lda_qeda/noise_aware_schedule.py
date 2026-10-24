# -*- coding: utf-8 -*-
"""D-226 · **编译后噪声感知资源核算**（净增 0 锚 · 能力层）。

════════ 这一层补的是哪半边 ════════
审计第二轮判 `schip_case` 的 **G-D** 与 `j2_case` 的 **J2-G-C** 各缺一半：
「无量子线路级仿真**与**门标定」。v0.9.270 的 `ft_compiler` 补了**编译**半边
（逻辑线路 → 物理 op 序列 + ASAP 分层），本模块补**核算**半边：

    编译结果（ops + layers + depth）  ──叠加门级错误率预算──▶  四条核算
      ① 累积错误上界  ② 一阶近似与可证双侧界
      ③ 并行化收益（整数比）  ④ 达到给定错误预算所需的纠错轮数（整数）

════════ 🔴 三条边界（必读，防过度解读）════════
① **这不是仿真器**。它不演化量子态、不算保真度、不做线路级噪声仿真。
   `schip_case.G-D` 里"线路级仿真"那半边**仍然缺**，本模块只补"资源核算"。
   任何把它读成"LDA 能预测线路保真度"的说法都是错的。
② **判据全部是整数 / 集合 / 可证不等式，没有浮点 golden**：
   · 双侧界 `max_i p_i ≤ p_exact ≤ Σ p_i` 是 **Weierstrass 不等式**的直接推论
     （`∏(1−x_i) ≥ 1−Σx_i`），**理论可证**，不靠参考实现；
   · 纠错轮数用**定义式不等式**验证（`1−(1−p_L)^{r−1} < p_c ≤ 1−(1−p_L)^r`）；
   · 并行化收益是**整数比** `n_ops / depth`，全不冲突时严格等于 `n_ops`。
   这条纪律来自 D3 的裁决：**浮点保真不可锚（两实现差 3–53 ulp），别拿它当判据**。
③ **不新增锚**（`ANCHORABLE = False`）：错误预算是**设计输入的函数**，没有第二条
   独立数值路径；累积上界是**定义式**（撞 D-220/221/222 已判死的"定义式"类）；
   轮数是整数恒等（resid ≡ 0）。重评条件见 `why_not_anchored()`。

红线：纯 stdlib · 零第三方 · 零网络 · 零 LLM · LLM 不进判决路径。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ANCHORABLE",
    "DEFAULT_GATE_ERROR",
    "ROLE",
    "error_budget",
    "parallel_gain",
    "syndrome_rounds",
    "syndrome_rounds_acc",
    "layer_profile",
    "budget_report",
    "why_not_anchored",
    "run_selfchecks",
]

ROLE = ("D-226 · 编译后噪声感知资源核算（能力层）—— 在 ft_compiler 的物理 op 序列上叠加"
        "门级错误率预算，给出累积上界 / 可证双侧界 / 并行化整数比 / 纠错轮数整数；"
        "**不是仿真器**，不做线路级量子态演化")

#: 🔴 可锚性裁决（负结果机器化）：不做锚，理由见 `why_not_anchored()`
ANCHORABLE = False

#: 门级错误率**设计预算**（非实测、非 PDK 认证值；可整体覆盖）
#: 量级取超导 transmon 的设计期典型值，仅用于"预算核算"演示
DEFAULT_GATE_ERROR: Dict[str, float] = {
    "CX": 1.0e-3,
    "T": 2.0e-4,
    "S": 1.0e-4,
    "H": 5.0e-5,
    "X": 5.0e-5,
    "Z": 5.0e-5,
    "MEASURE": 5.0e-3,
    "RESET": 2.0e-3,
}

#: 未知门种类的兜底错误率（保守取最大已登记值；**不静默当 0**）
_FALLBACK_P = max(DEFAULT_GATE_ERROR.values())


def _p_of(kind: str, per_gate: Optional[Dict[str, float]]) -> Tuple[float, str]:
    """取某个门种类的错误率，并回带来源（`budget` / `fallback`）。"""
    if per_gate and kind in per_gate:
        p = float(per_gate[kind])
        src = "budget"
    elif kind in DEFAULT_GATE_ERROR:
        p = float(DEFAULT_GATE_ERROR[kind])
        src = "default"
    else:
        p = float(_FALLBACK_P)
        src = "fallback"
    if not math.isfinite(p) or p < 0.0 or p >= 1.0:
        raise ValueError("门 %r 的错误率必须 ∈ [0,1)，实际 %r" % (kind, p))
    return p, src


# ═══════════════════════ ① 累积错误上界 + ② 可证双侧界 ═══════════════════════
def error_budget(ops: Sequence[Dict[str, Any]],
                 *,
                 per_gate: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """对物理 op 序列做累积错误**预算核算**（独立失效假设）。

    返回：
      - `n_ops`           op 数（整数）
      - `p_exact`         `1 − ∏(1 − p_i)`（精确式，浮点但**只作报告值**）
      - `p_first_order`   `Σ p_i`（一阶近似）
      - `p_max`           `max p_i`
      - `bound_ok`        `p_max ≤ p_exact ≤ p_first_order`（**Weierstrass 可证界**）
      - `by_kind`         各门种类的 {n, p, p_sum, source}
      - `fallback_kinds`  未登记、走了兜底错误率的门种类（**必须可见**，不得静默）

    🔴 这三条量的关系是**可证的**，不是拟合出来的：
      `∏(1−x_i) ≥ 1−Σx_i`（Weierstrass）⇒ `p_exact ≤ p_first_order`；
      `1−∏(1−x_i) ≥ 1−(1−x_max) = x_max` ⇒ `p_exact ≥ p_max`。
      所以判据可以是**双侧不等式**，不需要任何 golden 浮点。
    """
    seq = [o for o in (ops or []) if isinstance(o, dict)]
    if not seq:
        return {"n_ops": 0, "p_exact": 0.0, "p_first_order": 0.0, "p_max": 0.0,
                "bound_ok": True, "by_kind": {}, "fallback_kinds": []}

    prod = 1.0
    s1 = 0.0
    pmax = 0.0
    by_kind: Dict[str, Dict[str, Any]] = {}
    for o in seq:
        kind = str(o.get("kind", "?"))
        p, src = _p_of(kind, per_gate)
        prod *= (1.0 - p)
        s1 += p
        pmax = max(pmax, p)
        rec = by_kind.setdefault(kind, {"n": 0, "p": p, "p_sum": 0.0, "source": src})
        rec["n"] += 1
        rec["p_sum"] += p
        if src == "fallback":
            rec["source"] = "fallback"

    p_exact = 1.0 - prod
    # 双侧可证界（留 1e-15 浮点松弛，容差只为吸收舍入，不放宽不等式方向）
    bound_ok = (pmax <= p_exact + 1e-15) and (p_exact <= s1 + 1e-15)
    return {
        "n_ops": len(seq),
        "p_exact": p_exact,
        "p_first_order": s1,
        "p_max": pmax,
        "bound_ok": bool(bound_ok),
        "by_kind": by_kind,
        "fallback_kinds": sorted(k for k, v in by_kind.items() if v["source"] == "fallback"),
    }


# ═══════════════════════ ③ 并行化收益（整数比）═══════════════════════
def parallel_gain(result: Dict[str, Any]) -> Dict[str, Any]:
    """ASAP 分层相对全串行的收益 —— **整数比，不是加速比宣称**。

    `depth_serial = n_ops`（每层一个 op）⇒ `gain = n_ops / depth`，恒有
    `1 ≤ gain ≤ n_ops`。**全不冲突**（任意两 op 物理比特不相交）⇒ `gain == n_ops`；
    **全串行**（每层恰 1 op）⇒ `gain == 1`。

    这两个端点是**整数等式**，可以直接当判据（不需要拍阈值）。
    """
    ops = [o for o in (result.get("ops") or []) if isinstance(o, dict)]
    layers = result.get("layers") or []
    depth = int(result.get("depth") if result.get("depth") is not None else len(layers))
    n_ops = len(ops)
    if n_ops == 0:
        return {"n_ops": 0, "depth": 0, "depth_serial": 0, "gain": 1.0,
                "gain_in_range": True, "all_disjoint": True, "all_serial": True}
    if depth <= 0:
        raise ValueError("depth 必须 ≥1（ops=%d，depth=%r）" % (n_ops, depth))

    # 全不冲突判定：按物理比特出现次数判（同层约束由 ASAP 保证，这里查全局）
    bits = [set(o.get("phys") or ()) for o in ops]
    all_disjoint = True
    seen: set = set()
    for b in bits:
        if seen & b:
            all_disjoint = False
            break
        seen |= b
    all_serial = (depth == n_ops)
    gain = n_ops / float(depth)
    return {
        "n_ops": n_ops,
        "depth": depth,
        "depth_serial": n_ops,
        "gain": gain,
        "gain_in_range": (1.0 - 1e-15) <= gain <= (n_ops + 1e-15),
        "all_disjoint": all_disjoint,
        "all_serial": all_serial,
    }


# ═══════════════════════ ④ 纠错轮数（整数，定义式验证）═══════════════════════
def syndrome_rounds_acc(rounds: int, p_logical: float) -> float:
    """`r` 轮纠错后的累积逻辑失效率 `1 − (1 − p_L)^r`（纯定义式）。"""
    r = int(rounds)
    if r < 0:
        raise ValueError("rounds 必须 ≥0，实际 %r" % (rounds,))
    if not (0.0 < float(p_logical) < 1.0):
        raise ValueError("p_logical 必须 ∈ (0,1)，实际 %r" % (p_logical,))
    return float(1.0 - (1.0 - float(p_logical)) ** r)


def syndrome_rounds(p_circuit: float, p_logical: float) -> int:
    """达到 `p_circuit` 预算所需的**最小整数轮数** `r`。

    定义（本函数返回值的判据就是它本身，可由 `syndrome_rounds_acc` 复算验证）：

        `r = 0`                             若 `p_circuit = 0`
        `1 − (1−p_L)^{r−1} < p_c ≤ 1 − (1−p_L)^r`     否则

    实现：闭式 `ceil(ln(1−p_c)/ln(1−p_L))` 起手，然后**用定义式逐步校正 ±1**
    （防浮点边界错一位）。校正后返回值**恒满足定义式** —— 所以判据可严格复算，
    不需要"参考实现"。
    """
    pc = float(p_circuit)
    pl = float(p_logical)
    if not math.isfinite(pc) or not (0.0 <= pc < 1.0):
        raise ValueError("p_circuit 必须 ∈ [0,1)，实际 %r" % (p_circuit,))
    if not math.isfinite(pl) or not (0.0 < pl < 1.0):
        raise ValueError("p_logical 必须 ∈ (0,1)，实际 %r" % (p_logical,))
    if pc == 0.0:
        return 0
    r = int(math.ceil(math.log1p(-pc) / math.log1p(-pl)))
    r = max(1, r)
    while r > 1 and syndrome_rounds_acc(r - 1, pl) >= pc:
        r -= 1
    while syndrome_rounds_acc(r, pl) < pc:
        r += 1
    return r


# ═══════════════════════ 分层画像（集合口径）═══════════════════════
def layer_profile(result: Dict[str, Any],
                  *,
                  per_gate: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """逐层的物理比特占用（**集合**）与该层错误预算。

    每层返回 {index, n_ops, n_bits, bits, p_layer, kinds}。
    `bits` 是**同层物理比特并集** —— 同层两 op 不相交由 `ft_compiler.schedule_asap`
    保证，本函数只做画像，不重复校验（校验在 `ft_compiler` 的 I4）。
    """
    layers = result.get("layers") or []
    out: List[Dict[str, Any]] = []
    for i, layer in enumerate(layers):
        ops = [o for o in layer if isinstance(o, dict)]
        bits: set = set()
        kinds: Dict[str, int] = {}
        b = error_budget(ops, per_gate=per_gate)
        for o in ops:
            bits |= set(o.get("phys") or ())
            k = str(o.get("kind", "?"))
            kinds[k] = kinds.get(k, 0) + 1
        out.append({
            "index": i,
            "n_ops": len(ops),
            "n_bits": len(bits),
            "bits": sorted(bits),
            "p_layer": b["p_exact"],
            "kinds": dict(sorted(kinds.items())),
        })
    return out


# ═══════════════════════ 汇总报告 ═══════════════════════
def budget_report(result: Dict[str, Any],
                  *,
                  per_gate: Optional[Dict[str, float]] = None,
                  p_logical: float = 1.0e-6) -> Dict[str, Any]:
    """把四条核算合成一份报告（**全部字段要么整数、要么可证界内的浮点**）。"""
    eb = error_budget(result.get("ops") or [], per_gate=per_gate)
    pg = parallel_gain(result)
    rounds = syndrome_rounds(eb["p_exact"], p_logical)
    lp = layer_profile(result, per_gate=per_gate)
    return {
        "n_ops": eb["n_ops"],
        "p_exact": eb["p_exact"],
        "p_first_order": eb["p_first_order"],
        "p_max": eb["p_max"],
        "bound_ok": eb["bound_ok"],
        "fallback_kinds": eb["fallback_kinds"],
        "by_kind": eb["by_kind"],
        "depth": pg["depth"],
        "depth_serial": pg["depth_serial"],
        "gain": pg["gain"],
        "gain_in_range": pg["gain_in_range"],
        "all_disjoint": pg["all_disjoint"],
        "all_serial": pg["all_serial"],
        "p_logical": float(p_logical),
        "syndrome_rounds": int(rounds),
        "p_after_rounds": syndrome_rounds_acc(int(rounds), p_logical),
        "layers": lp,
        "caliber": ("错误预算核算（独立失效假设 · 门级 p 为**设计预算**非实测）；"
                    "**非线路级仿真**，不演化量子态、不预测线路保真度"),
        "not_a_simulator": True,
    }


def why_not_anchored() -> Dict[str, Any]:
    """负结果机器化（三问 + 重评条件）。"""
    return {
        "anchorable": False,
        "q1_exact_combinatorial": False,
        "q2_threshold_or_mc": False,
        "q3_closed_form_only": True,
        "reasons": [
            "累积错误上界 `1−∏(1−p_i)` 是**定义式** ⇒ 与任何闭式比对 resid ≡ 0"
            "（撞 D-220/Q=1/tanδ · D-222/√(4kTRΔf) 已判死的「定义式」类）",
            "纠错轮数 `ceil(ln(1−p_c)/ln(1−p_L))` 是**整数恒等** ⇒ 无独立第二条路径"
            "（撞 D-218 编译层的整数恒等类：可作判据，不可作锚）",
            "并行化收益 `n_ops/depth` 是**两个整数的比** ⇒ 精确有理量，resid ≡ 0",
            "门级 p 是**设计预算输入**，不是物理量 ⇒ 任何「预测值 vs 参考值」都不构成锚",
        ],
        "substitute_criteria": [
            "双侧可证界 `p_max ≤ p_exact ≤ Σp_i`（Weierstrass 不等式的直接推论）",
            "定义式不等式 `1−(1−p_L)^{r−1} < p_c ≤ 1−(1−p_L)^r`（返回值可严格复算）",
            "整数比端点 `gain == n_ops`（全不冲突）/ `gain == 1`（全串行）",
            "跨模块 `n_cx` / `n_slots` 与 `ft_compiler.resource_report` 逐字相同",
        ],
        "revisit_condition": (
            "若将来引入**真机门级表征数据**（逐门实测 p_i 及其置信区间），并且问题是"
            "「预算是否与实测一致」，那时这是**实测对照**而非 golden 锚 —— 走 empirical "
            "锚通道（E 类），仍不属本模块。"
        ),
    }


# ═══════════════════════════ 自检 ═══════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。全部为可证不等式 / 整数恒等断言。"""
    res: List[Tuple[str, bool]] = []

    def chk(name: str, cond: bool) -> None:
        res.append((name, bool(cond)))

    def _ops(kinds: Sequence[str]) -> List[Dict[str, Any]]:
        return [{"kind": k, "phys": (i,), "logical": (i,)} for i, k in enumerate(kinds)]

    # ① 双侧界：多组 op 序列都必须满足 p_max ≤ p_exact ≤ Σp
    ok1 = True
    for ks in (["CX"], ["CX"] * 5, ["CX", "T", "H"], ["MEASURE"] * 3,
               ["CX", "T", "CX", "T", "unknown_gate"]):
        b = error_budget(_ops(ks))
        ok1 = ok1 and b["bound_ok"] and b["p_max"] <= b["p_exact"] + 1e-15 \
            and b["p_exact"] <= b["p_first_order"] + 1e-15
    chk("① 双侧可证界 p_max ≤ p_exact ≤ Σp 五组全成立", ok1)

    # ② 单调：加一门（p>0）⇒ p_exact 严格增
    seq = _ops(["CX"] * 8)
    mono = True
    prev = 0.0
    for k in range(1, len(seq) + 1):
        cur = error_budget(seq[:k])["p_exact"]
        mono = mono and cur > prev
        prev = cur
    chk("② 逐 op 累加 ⇒ p_exact 严格单调递增（8 步全成立）", mono)

    # ③ 单门边界：p_exact 恰等于该门 p（残差 <1e-15）
    one = error_budget(_ops(["CX"]))
    chk("③ 单门 ⇒ p_exact == p(CX)（残差<1e-15）",
        abs(one["p_exact"] - DEFAULT_GATE_ERROR["CX"]) < 1e-15)

    # ④ 未知门走兜底且可见（不静默当 0）
    unk = error_budget(_ops(["never_registered_gate"]))
    chk("④ 未登记门 ⇒ 走兜底且进 fallback_kinds（不静默当 0）",
        unk["fallback_kinds"] == ["never_registered_gate"]
        and unk["p_exact"] > 0.0)

    # ⑤ 并行化端点：全不冲突 ⇒ gain == n_ops；全串行 ⇒ gain == 1
    ops_dis = [{"kind": "CX", "phys": (i, i + 1)} for i in range(0, 6, 2)]
    res_dis = {"ops": ops_dis, "layers": [ops_dis], "depth": 1}
    g_dis = parallel_gain(res_dis)
    ops_ser = [{"kind": "CX", "phys": (0, 1)} for _ in range(4)]
    res_ser = {"ops": ops_ser, "layers": [[o] for o in ops_ser], "depth": 4}
    g_ser = parallel_gain(res_ser)
    chk("⑤ 并行化端点：全不冲突 ⇒ gain == n_ops；全串行 ⇒ gain == 1",
        g_dis["all_disjoint"] and abs(g_dis["gain"] - len(ops_dis)) < 1e-12
        and g_ser["all_serial"] and abs(g_ser["gain"] - 1.0) < 1e-12)

    # ⑥ 纠错轮数：定义式不等式恒成立（6 组）
    ok6 = True
    for pc, pl in ((3.7e-4, 1e-6), (1e-3, 1e-5), (1e-6, 1e-6), (1e-4, 1e-9),
                   (0.5, 1e-6), (1e-9, 1e-3)):
        r = syndrome_rounds(pc, pl)
        if pc == 0.0:
            ok6 = ok6 and r == 0
        elif pc <= pl:
            ok6 = ok6 and r == 1
        else:
            ok6 = ok6 and (syndrome_rounds_acc(r - 1, pl) < pc
                           <= syndrome_rounds_acc(r, pl))
    chk("⑥ 纠错轮数满足定义式不等式（6 组：含 p_c<p_L / 相等 / 大预算）", ok6)

    # ⑦ r=0 边界
    chk("⑦ p_circuit=0 ⇒ rounds=0（不虚报需要纠错）",
        syndrome_rounds(0.0, 1e-6) == 0)

    # ⑧ 负结果机器化齐备
    w = why_not_anchored()
    chk("⑧ 负结果：anchorable=False ∧ 四类理由 ∧ 替代判据 ∧ 重评条件",
        w["anchorable"] is False and len(w["reasons"]) >= 4
        and len(w["substitute_criteria"]) >= 4 and bool(w["revisit_condition"]))

    ok = all(v for _, v in res)
    if verbose:
        for n, v in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n)
    return ok


if __name__ == "__main__":
    print("noise_aware_schedule 自检：",
          "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
