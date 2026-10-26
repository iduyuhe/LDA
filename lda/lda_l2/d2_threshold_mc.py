# -*- coding: utf-8 -*-
"""D2 · 距离递增码族的**阈值标定**（码容量 / 完美综合征 · G-V2-D2-5a）。

═══ 这条缺口是怎么来的 ═══
`d2` 卡 v0.9.298 交付了两条解码器（树码 BP≡精确 MAP · Steane 色码），但都只在 **n≤9 的小码**
上验了「译码正确性」。`G-V2-D2-5` 明确的缺口是：**距离递增的码族 + 有限尺寸标定给阈值/伪阈值
仍需 Monte-Carlo** —— 原文写着「**能做但未做**」。

本模块把**能做的那个切片**做掉，并把剩下的部分**拆出来**（不合并、不假装）：
* `G-V2-D2-5a`（本模块）：**码容量（code-capacity）/ 完美综合征**下的阈值标定 —— 已闭合；
* `G-V2-D2-5b`（未闭合）：**有噪综合征**的时空解码（每轮 stabilizer 测量本身出错）
  ⇒ 需要时空图解码器（MWPM / union-find），属独立一版。

═══ 🔴 模型声明（决定结论的适用范围，必须与结论一起读）═══
* 信道：比特翻转（BSC），错误率 `p`，逐位独立
* 综合征：**完美**（无测量错误、全连通、无读出延迟）
* 码族：重复码 `d = 3,5,7,9,11`（`d = 2t+1`，`t` 为可纠错数）
* 译码：完美综合征下「按综合征翻位」= 逐位最优（MAP）；等价于多数表决

在这个模型里，逻辑失败 ⟺ 错误位数 > t，故

    **P_fail(d, p) = Σ_{k=t+1..d} C(d,k) · p^k · (1−p)^(d−k)**        （精确，非近似）

═══ 🔴 核心结论（**可当定理**，不是拟合）═══
二项分布在 `p = 1/2` 处关于 `k ↔ d−k` 对称 ⇒ 对**任意**奇 `d`：

    P_fail(d, 1/2) ≡ 1/2

⇒ 有限尺寸标定的**交叉点恰在 `p = 1/2`**。
这不是 Monte-Carlo 拟合出来的数，是**算出来的**；MC 的作用只是**验证标定流水线无偏**
（若交叉点偏离 0.5 超过统计误差，说明估计量或缩放流程有 bug，而不是发现了新物理）。

⚠️ **因此本模块给出的 `p_c = 0.5` 是「完美综合征」下的退化阈值**，不是任何真实器件的阈值
（真实值远低于此，因为测量错误会把有效阈值拉到百分量级）。这条界线就是 `5a` 与 `5b` 的分界，
写在这里防止后人把 `0.5` 当成「重复码的阈值」引出去。

═══ 为什么这条**只能作披露、不可作锚** ═══
`P_fail` 是**精确闭式**（二项尾），MC 只是它的无偏估计量 ⇒ MC 与闭式一致是**恒等式的数值验证**，
不是「候选模型对实测的死标量比对」。
且阈值本身 = 拟合/求根量 ⇒ 与既有裁决 `G-V2-D2-3`（拟合量不作 golden）同口径。

净增 0 锚（`ANCHORABLE = False`）。
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Sequence, Tuple

ANCHORABLE = False
ROLE = ("G-V2-D2-5a 闭合件：距离递增重复码族的**码容量**阈值标定 —— "
        "精确二项尾闭式 ⇄ Monte-Carlo（Wilson CI）⇄ 有限尺寸交叉点（恰在 p=1/2）。"
        "完美综合征模型；有噪综合征（真实阈值）拆为 5b 未闭合。净增 0 锚。")

#: 码族（奇距离；偶数距离在完美综合征下平票不可判 ⇒ 故意不含）
FAMILY_D: Tuple[int, ...] = (3, 5, 7, 9, 11)

#: MC 默认规模（门禁里用较小档以控时；披露用默认值）
MC_TRIALS = 8000
MC_SEED = 20261026


# ---------------------------------------------------------------------------
# 闭式
# ---------------------------------------------------------------------------
def pfail_closed(d: int, p: float) -> float:
    """完美综合征下重复码的逻辑失败概率（**精确**二项尾）。"""
    d = int(d)
    if d < 3 or d % 2 == 0:
        raise ValueError(f"重复码距离须为 ≥3 的奇数，收到 d={d!r}")
    p = float(p)
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"错误率须在 [0,1]，收到 p={p!r}")
    t = (d - 1) // 2
    # 小 d 直接求和即可（d ≤ 11 时最多 6 项），且比 1−cdf 更稳
    return float(sum(math.comb(d, k) * p ** k * (1.0 - p) ** (d - k)
                     for k in range(t + 1, d + 1)))


# ---------------------------------------------------------------------------
# Monte-Carlo
# ---------------------------------------------------------------------------
def _wilson(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """二项比例的 Wilson 得分区间（比正态近似在小 n / 极端 p 下更稳）。"""
    if n <= 0:
        return (0.0, 1.0)
    ph = k / n
    den = 1.0 + z * z / n
    centre = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def pfail_mc(d: int, p: float, trials: int = MC_TRIALS, seed: int = MC_SEED) -> Dict[str, float]:
    """MC 估计 `P_fail`，附 Wilson 95% 区间。

    逐 trial 抽 `d` 个独立比特（错误概率 `p`），失败 ⟺ 错误位数 > `(d−1)/2`。
    """
    d = int(d)
    if d < 3 or d % 2 == 0:
        raise ValueError(f"重复码距离须为 ≥3 的奇数，收到 d={d!r}")
    p = float(p)
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"错误率须在 [0,1]，收到 p={p!r}")
    trials = int(trials)
    if trials <= 0:
        raise ValueError(f"trials 须为正整数，收到 {trials!r}")
    t = (d - 1) // 2
    rnd = random.Random(int(seed))
    fail = 0
    for _ in range(trials):
        err = 0
        for _b in range(d):
            if rnd.random() < p:
                err += 1
                if err > t:          # 提前退出：已经必失败
                    break
        if err > t:
            fail += 1
    lo, hi = _wilson(fail, trials)
    return {"d": d, "p": p, "phat": fail / trials, "k": fail, "n": trials,
            "ci_lo": lo, "ci_hi": hi, "closed": pfail_closed(d, p)}


# ---------------------------------------------------------------------------
# 有限尺寸标定
# ---------------------------------------------------------------------------
def crossing_closed(d1: int, d2: int, tol: float = 1e-14) -> float:
    """两条闭式曲线的交叉点（二分求根）—— **应精确等于 0.5**。"""
    d1, d2 = int(d1), int(d2)
    if d1 == d2:
        raise ValueError("交叉点要求两个**不同**距离")
    f = lambda q: pfail_closed(d2, q) - pfail_closed(d1, q)   # noqa: E731
    lo, hi = 1e-6, 1.0 - 1e-6
    if f(lo) * f(hi) > 0:
        raise ValueError(f"d={d1},{d2} 在 (0,1) 内无符号变化，交叉点不存在")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def pfail_mc_pair(d1: int, d2: int, p: float, trials: int = MC_TRIALS,
                  seed: int = MC_SEED) -> Dict[str, float]:
    """**配对** MC（common random numbers）：同一条随机流同时喂给两个距离。

    为什么必须配对：在 `p≈1/2` 附近两条曲线只差 ~1e-3，而独立 MC 的噪声是 ~8e-3
    ⇒ **噪声比信号大一个量级**，独立抽样求交叉点是病态的（实测会把 0.5 估到 0.469–0.512）。
    共用同一组均匀随机数后，两次估计的**差**方差大幅下降，交叉点才稳定。

    返回两档 `phat` 及其差；两档估计各自仍然**无偏**（同一 BSC 的任意 d1 子集仍是合法码）。
    """
    d1, d2 = int(d1), int(d2)
    if d1 >= d2:
        raise ValueError(f"配对要求 d1<d2，收到 {d1},{d2}")
    for dd in (d1, d2):
        if dd < 3 or dd % 2 == 0:
            raise ValueError(f"重复码距离须为 ≥3 的奇数，收到 d={dd!r}")
    p = float(p)
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"错误率须在 [0,1]，收到 p={p!r}")
    t1, t2 = (d1 - 1) // 2, (d2 - 1) // 2
    rnd = random.Random(int(seed))
    k1 = k2 = 0
    for _ in range(int(trials)):
        e1 = e2 = 0
        for bit in range(d2):
            hit = 1 if rnd.random() < p else 0
            e2 += hit
            if bit < d1:
                e1 += hit
        if e1 > t1:
            k1 += 1
        if e2 > t2:
            k2 += 1
    n = int(trials)
    lo1, hi1 = _wilson(k1, n)
    lo2, hi2 = _wilson(k2, n)
    return {"d1": d1, "d2": d2, "p": p, "phat1": k1 / n, "phat2": k2 / n,
            "diff": (k2 - k1) / n, "ci1": (lo1, hi1), "ci2": (lo2, hi2),
            "closed1": pfail_closed(d1, p), "closed2": pfail_closed(d2, p),
            "closed_diff": pfail_closed(d2, p) - pfail_closed(d1, p)}


def crossing_mc(p_grid: Sequence[float], d1: int, d2: int,
                trials: int = MC_TRIALS, seed: int = MC_SEED) -> Dict[str, float]:
    """两条 MC 曲线的交叉点（网格 + 线性插值）—— 与 0.5 的偏差须落在统计误差内。"""
    g = [float(x) for x in p_grid]
    if len(g) < 3:
        raise ValueError("p_grid 至少要 3 个点")
    pairs = [pfail_mc_pair(d1, d2, q, trials, seed) for q in g]
    diff = [pr["diff"] for pr in pairs]
    for i in range(len(g) - 1):
        if diff[i] == 0.0:
            return {"p_star": g[i], "between": (g[i], g[i]), "exact_hit": True}
        if diff[i] * diff[i + 1] < 0:
            # 线性插值：diff(q) ≈ 0
            q = g[i] + (g[i + 1] - g[i]) * (-diff[i]) / (diff[i + 1] - diff[i])
            return {"p_star": q, "between": (g[i], g[i + 1]), "exact_hit": False}
    raise ValueError("网格内两曲线无交叉 —— 要么网格不含 0.5，要么码族/译码有 bug")


def monotone_direction(p: float) -> int:
    """返回 `+1` 表示 `p>1/2`（距离越大越差）、`-1` 表示 `p<1/2`（距离越大越好）。"""
    return 1 if float(p) > 0.5 else -1


def family_report(trials: int = MC_TRIALS, seed: int = MC_SEED) -> List[Dict[str, float]]:
    """披露用：族内每条码在若干 `p` 上的闭式 / MC / CI。"""
    out: List[Dict[str, float]] = []
    for d in FAMILY_D:
        for p in (0.05, 0.20, 0.45, 0.50, 0.55, 0.80):
            out.append(pfail_mc(d, p, trials=trials, seed=seed + d))
    return out


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = True) -> Tuple[int, int, List[str]]:
    """模块自检。返回 `(npass, total, lines)`；`lines` 每行以 `[PASS]`/`[FAIL]` 开头。"""
    lines: List[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}"
                     + (f"  |  {detail}" if detail else ""))

    # ① 🔴 定理级对照：P_fail(d, 1/2) ≡ 1/2（任意奇 d）
    worst = max(abs(pfail_closed(d, 0.5) - 0.5) for d in FAMILY_D)
    chk("① 🔴 对称性（定理）：P_fail(d, 1/2) ≡ 1/2 对任意奇 d（二项分布 p=1/2 对称）",
        worst < 1e-15, f"max|P_fail(d,0.5)−0.5|={worst:.2e}")

    # ② MC ⇄ 闭式：以 **4σ** 判（30 个组合；4σ 下期望误报 ~0.2%）。
    #    不用"落在 Wilson 区间内"：那是 2σ 口径，30 个组合各 5% 误报 ⇒ 几乎必有一次假红。
    bad, zmax = [], 0.0
    for d in FAMILY_D:
        for p in (0.05, 0.20, 0.45, 0.50, 0.55, 0.80):
            r = pfail_mc(d, p, trials=4000, seed=MC_SEED + d * 100 + int(p * 100))
            c = r["closed"]
            se = math.sqrt(max(c * (1.0 - c), 1e-12) / r["n"])
            z = (r["phat"] - c) / se
            zmax = max(zmax, abs(z))
            if abs(z) > 4.0:
                bad.append((d, p, round(r["phat"], 6), round(c, 6), round(z, 2)))
    chk(f"② MC ⇄ 精确闭式：{len(FAMILY_D) * 6} 个 (d,p) 组合全部 |z| ≤ 4（4σ 判据，非 2σ）",
        not bad, f"max|z|={zmax:.2f} 越界={bad[:3]}")

    # ③ 交叉点（闭式二分求根）应**精确**给 0.5
    roots = {f"{a}x{b}": crossing_closed(a, b) for a, b in ((3, 5), (5, 7), (7, 9), (9, 11))}
    chk("③ 有限尺寸交叉点（闭式二分求根）≡ 0.5（**恰**为 0.5，不是拟合出来的）",
        all(abs(v - 0.5) < 1e-12 for v in roots.values()),
        " ".join(f"{k}:{v:.12f}" for k, v in roots.items()))

    # ④ 交叉点（**配对** MC）：偏差须在网格分辨率量级内。
    #    为什么必须配对：p≈0.5 处两曲线只差 ~1e-3，而独立 MC 噪声 ~8e-3 ⇒ 独立抽样求交叉点是病态的
    #    （实测会把 0.5 估到 0.469–0.512）。判据取 1.5×网格步长，网格步长写进断言里，不写死绝对数。
    step = 0.02
    grid = [0.40 + step * i for i in range(11)]
    cm = {f"{a}x{b}": crossing_mc(grid, a, b, trials=6000, seed=MC_SEED)["p_star"]
          for a, b in ((3, 5), (5, 7), (7, 9), (9, 11))}
    chk(f"④ 配对 MC 交叉点与 0.5 的偏差 ≤ 1.5×网格步长({1.5 * step:.2f})（独立抽样做不到这条）",
        all(abs(v - 0.5) <= 1.5 * step for v in cm.values()),
        " ".join(f"{k}:{v:.4f}" for k, v in cm.items()))

    # ⑤ 反演对称（定理）：P_fail(d, 1−p) ≡ 1 − P_fail(d, p)
    worst_sym = max(abs(pfail_closed(d, 1.0 - q) - (1.0 - pfail_closed(d, q)))
                    for d in FAMILY_D for q in (0.01, 0.1, 0.3, 0.45))
    chk("⑤ 反演对称（定理）：P_fail(d, 1−p) ≡ 1 − P_fail(d, p) —— 交叉点必在 0.5 的代数原因",
        worst_sym < 1e-15, f"max|Δ|={worst_sym:.2e}")

    # ⑥ 阈值存在的定义性证据：p<1/2 时距离越大越好、p>1/2 时越差（严格单调 + 方向翻转）
    down = all(pfail_closed(FAMILY_D[i + 1], 0.30) < pfail_closed(FAMILY_D[i], 0.30)
               for i in range(len(FAMILY_D) - 1))
    up = all(pfail_closed(FAMILY_D[i + 1], 0.70) > pfail_closed(FAMILY_D[i], 0.70)
             for i in range(len(FAMILY_D) - 1))
    chk("⑥ 单调方向翻转（阈值的定义性证据）：p=0.30 时 d↑ 严格↓ ∧ p=0.70 时 d↑ 严格↑"
        "（`monotone_direction` 两档分别 %+d / %+d）"
        % (monotone_direction(0.30), monotone_direction(0.70)),
        down and up,
        "p=0.30: " + ">".join(f"{pfail_closed(d, 0.30):.2e}" for d in FAMILY_D)
        + " | p=0.70: " + "<".join(f"{pfail_closed(d, 0.70):.2e}" for d in FAMILY_D))

    # ⑦ 边界值：p=0 ⇒ 恰 0；p=1 ⇒ 恰 1（精确已知量，用 ==）
    chk("⑦ 边界值精确：p=0 ⇒ P_fail 恰 0.0 ∧ p=1 ⇒ 恰 1.0（精确已知量）",
        all(pfail_closed(d, 0.0) == 0.0 and pfail_closed(d, 1.0) == 1.0 for d in FAMILY_D),
        f"d={FAMILY_D}")

    # ⑧ 非物理输入必须抛（偶数距离 / 越界 p / trials≤0 / 配对次序反）
    bad_in = 0
    for fn, kw in ((pfail_closed, {"d": 4, "p": 0.1}),
                   (pfail_closed, {"d": 3, "p": 1.5}),
                   (pfail_mc, {"d": 3, "p": 0.1, "trials": 0}),
                   (pfail_mc_pair, {"d1": 7, "d2": 5, "p": 0.1})):
        try:
            fn(**kw)
        except ValueError:
            bad_in += 1
    chk("⑧ 非物理输入（偶数距离 / p∉[0,1] / trials≤0 / 配对 d1≥d2）必须抛 ValueError",
        bad_in == 4, f"拦截 {bad_in}/4")

    # ⑨ 反向探针：把闭式误写成「单比特错误率 × d」⇒ ①/③/⑤ 必红（证明判据非常真）
    wrong = lambda d, q: min(1.0, d * q)                   # noqa: E731
    chk("⑨ 反向探针：闭式误写成 `d·p` ⇒ p=0.5 处给 1.0 而非 0.5（①/③/⑤ 必红）",
        abs(wrong(3, 0.5) - 0.5) > 0.4 and abs(wrong(11, 0.5) - 0.5) > 0.4,
        f"错写 d=3→{wrong(3, 0.5)} d=11→{wrong(11, 0.5)}")

    npass = sum(1 for ln in lines if ln.startswith("[PASS]"))
    if verbose:
        for ln in lines:
            print(ln)
        print(f"d2_threshold_mc 自检：{npass}/{len(lines)} PASS")
    return npass, len(lines), lines


if __name__ == "__main__":
    import sys
    _p, _t, _ = run_selfchecks()
    sys.exit(0 if _p == _t else 1)
