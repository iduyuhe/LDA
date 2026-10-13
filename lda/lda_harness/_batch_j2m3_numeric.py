# -*- coding: utf-8 -*-
"""Batch J2-M3 数值实现 · 超导 Transmon 征程（J2）M3 色散读出链 + 串扰。

════════════════════════════════════════════════════════════════
本批**一锚**（`benchmark_defs/part7.py` 引用）——

  B508：**FDM 多音读出的相邻通道频谱重叠串扰比**（readout multiplexing crosstalk）
        golden   = 闭式 **X(δ;γ) = 4γ²/(4γ² + δ²) = 1/(1 + (δ/(2γ))²)**
                   —— 两个**洛伦兹**通道线型 L(f) = (γ/π)/((f−f_c)²+γ²) 的**归一化重叠**
                   （洛伦兹自相关，**精确闭式、非截断近似**）：
                     ∫ L_i(f)·L_j(f) df = 2γ/(π(4γ²+δ²))，  ∫ L_i(f)² df = 1/(2πγ)
        candidate = **sinh 换元 + 复合 Simpson 数值卷积**：
                     两个积分各自数值求积 ⇒ X_num = ∫L_iL_j / ∫L_i²
                     （换元 f = γ(a + sinh u)、a = δ/(2γ)，把 1/f² 慢衰减尾部
                      压成 e^{−3|u|} 指数衰减 ⇒ 截断不再主导残差 —— B-11 族 D 血案解法）。
        ——方法学独立：golden 走「洛伦兹自相关解析闭式」；candidate 走「数值卷积求积」。
        🔴 实测残差链（复合 Simpson）：单调下降、默认档仍 >0（非机器零残差）⇒ **非代数恒等**。

🔴 物理意义（承 J2 超导 Transmon 蓝图 · M3「色散读出链 + 串扰」）：
  · FDM（频分复用）读出把 N 个 λ/4 读出谐振器挂**同一条 feedline**，每个通道占据频带内
    一段。相邻通道间隔 δ 时，两个洛伦兹线型互相**泄漏**：
      - δ ≫ γ（远隔）⇒ X → 0：通道隔离，读出互不污染；
      - δ ~ 2γ ⇒ X ~ 1/2：串扰显著，误判概率抬升；
      - δ → 0 ⇒ X → 1：通道**碰撞**（复用失效）。
  · X 是 **mux 频率规划的物理判据**：给定串扰容限 X_tol，最小通道间隔就是
      Δf_min = 2γ·√(1/X_tol − 1)；带宽 B 内可容纳的通道数 N_max = ⌊B/Δf_min⌋。
    （Δf_min 的**反解**不作锚 —— 那是代数恒等改写、判据 D 不响应，见
      B-11 被否候选「开普勒方程数值求根」先例；只在能力层 `lda_qeda/j2_readout_mux.py`
      里做设计用。）

🔴 与既有锚的边界（**同源体检 · 实 grep 全仓核验**，本批第一道闸）：
  · **宪章原定 M3 两候选均被否决**（承 M0/M1 先例「用户/宪章选的新族先验同源」）：
      - 宪章 **B511**「读出分配错误率（χ/κ/SNR ⇄ 数值二态分类）」 ⇒ **被既有 B30 完全占用**：
        B30 golden = 色散读出 SNR→erfc 误判链 `ε=½·erfc(SNR/√2)`、
        candidate = `readout_fidelity_quad`（误判概率的**高斯重叠数值积分 = 二态分类**）。
        被测标量（读出误判概率/保真度）·物理构型（色散读出 χ/κ/SNR）·数值格式
        （erfc 闭式 ⇄ 数值重叠积分）**三者全同** ⇒ 只是换名 ⇒ 否决。
      - 宪章 **B512**「杂散 ZZ 串扰错误预算（σ_zz ⇄ 数值）」 ⇒ **被本征程 B507 完全占用**：
        B507 golden = `ε=(4/5)sin²(ζt/2)`（ζ = ZZ 耦合）、candidate = 矩阵传播子 RK4。
        同一被测标量（ZZ 诱导错误率）·同一物理构型·同族数值格式 ⇒ 否决。
        （S4/`sc_readout.crosstalk_budget` 另有 `σ_zz ≤ 1.0 MHz` **规格硬上限**，属纯算术
          规格检查，不是「闭式 ⇄ 数值」可锚对。）
  · 本批实际净增落在 M3 里**唯一既有锚未覆盖**的连续物理量：**FDM 通道间频谱重叠**。
  · **B459**（洛伦兹谐振线型**幅度斜率极值**）：scalar=极值斜率(depth·3√3/(4·FWHM))、
    格式=等距采样+**中心差分**取极值。与 B508 **三者均不同**：①标量 **串扰重叠比** vs
    **斜率极值**；②构型 **双通道 FDM mux 互漏** vs **单谐振峰线型**；③格式 **数值卷积求积**
    vs **数值微分**。⇒ 计新锚（承 B452↔B33 先例）。
  · **B197/B199**（Voigt **线心值** V(0;·)）：标量是**单点线型值**（多普勒⊗洛伦兹），
    与「双洛伦兹归一重叠积分」不同标量、不同格式（B197/B199 = 解析 sinh 换元求积单积分）。
  · **B30**（读出保真度 F）：标量是**误判概率**（含 erfc/SNR/T1 权重），非**频谱重叠**；且
    B508 与读出**信噪比**无关（纯线型几何） ⇒ 不同物理量。
  · 实 grep 核验：`mux|FDM|multiplex|频谱重叠|spectral_overlap|overlap_ratio` 在
    `benchmark_defs/` 与 `lda_solver/` 内 **零占用**（既有锚无同族）。

🔴 命名避让：批次号 **J2-M3** 用连字符写法 `_batch_j2m3_numeric` / `_get_j2m3_numeric`
  （与 M2 的 `_batch_j2_numeric` 并列、互不覆盖）；候选 key 前缀 `b508_` 尚未占用
  （`b31_*` 属单锚 B31；`b508_*` 无冲突）。磁盘 `_adapter_p*.py` **不新建**（L9 守卫：恒 6 片）。

🔴 纪律：
· golden 与 candidate 是**两种结构不同的算法**（非「同式异写」）；进报告数字一律**现算**。
· 🔴 **判据 D 双向标定**：本锚离散参数 n 若取过大（n≥384）⇒ 残差沉到双精度地板
  （~7e-16，**与自证桩不可区分**，B10/B-10 族 B 血案）⇒ 定档必须落在**离散误差主导区**。
  实测扫描（U=12）：
      n= 32 → 2.191e-02      n=128 → 1.481e-05
      n= 64 → 2.302e-03      n=256 → 4.253e-10   ← 默认档（>1e-12，留 235× 余量）
      n=384 → 7.216e-16（**撞地板，弃用**）
  ⇒ 默认档 n=256；tol=1e-7 ⇒ 余量 235×。诚实边界：**被积函数解析 ⇒ 复合 Simpson 在
  sinh 换元后收敛快于标称 O(h⁴)**（实测比值 9.5×/155×/3.5e4×）；本锚**不虚报「恰 O(h⁴)」**，
  只报实测链与「单调下降、粗端浮出地板」两条可证伪事实。
· 诚实边界：γ/δ 为**设计示例量级**（非实测 PDK/非流片）；本锚只证明「解析闭式 ⇄ 数值卷积」
  一致这一数学事实 + mux 规划的物理链自洽，**不得作制造/性能宣称**。零商业依赖（纯 numpy）。
"""
from __future__ import annotations

import functools
import math

import numpy as np

# ── 三表（判据 D 扫描格 / 默认档 = 格末端 / tol 绝对口径按量级标定）─────────────
_N_BY_BID = {"B508": 256}
_GRID_BY_BID = {"B508": [32, 64, 128, 256]}
_TOL_BY_BID = {"B508": 1e-7}

#: 默认物理参数（只放 golden 接受的键；离散参数 n 由候选签名默认值承载）
_B508_DEFAULT = {"gamma": 0.5, "delta": 1.2}

#: sinh 换元截断半宽（u∈[−U,U]）。U=12 ⇒ 被积函数 ~e^{−3U} ≈ 2e−16 已入舍入地板，
#: 截断不再主导残差（B-11 族 D：截断上限由「尾部 < 最细档离散误差」反推）。
_U_SINH = 12.0


def _simpson(y: "np.ndarray", h: float) -> float:
    """复合 Simpson（区间数必须为偶数；权重 1,4,2,…,4,1 × h/3）。"""
    n = len(y) - 1
    if n < 2 or n % 2 != 0:
        raise ValueError("复合 Simpson 需偶数区间，实际区间数 %d" % n)
    w = np.ones(n + 1)
    w[1:n:2] = 4.0
    w[2:n:2] = 2.0
    return float(h / 3.0 * np.dot(w, y))


def _overlap_numeric(gamma: float, delta: float, n: int, u_half: float = _U_SINH):
    """数值卷积：X_num = ∫L_iL_j df / ∫L_i² df（sinh 换元 + 复合 Simpson）。

    换元 f = γ(a + sinh u)（a = δ/(2γ)，两通道中心 f=0 与 f=δ 的对称中点）：
        ∫L_iL_j df = (1/(π²γ))·∫ cosh u / [((a+sh)²+1)((sh−a)²+1)] du
        ∫L_i²   df = (1/(π²γ))·∫ cosh u / (sh²+1)²              du
    返回 (overlap, self)，二者同用 n（离散误差在比值里部分相消，仍为真实离散误差）。
    """
    n = int(n)
    u = np.linspace(-u_half, u_half, n + 1)
    h = 2.0 * u_half / n
    sh = np.sinh(u)
    ch = np.cosh(u)
    a = delta / (2.0 * gamma)
    f1 = ch / (((a + sh) ** 2 + 1.0) * ((sh - a) ** 2 + 1.0))
    f0 = ch / ((sh ** 2 + 1.0) ** 2)
    pref = 1.0 / (math.pi ** 2 * gamma)
    return _simpson(f1, h) * pref, _simpson(f0, h) * pref


def fdm_mux_overlap_golden(gamma: float = 0.5, delta: float = 1.2) -> float:
    """B508 golden：洛伦兹通道归一化重叠比闭式（**精确**，洛伦兹自相关）。

        X(δ;γ) = 4γ²/(4γ² + δ²) = 1/(1 + (δ/(2γ))²)

    推导：FT[L](t) = e^{−2πγ|t|} ⇒ ∫L(f)L(f−δ)df = ∫e^{−4πγ|t|}e^{i2πδt}dt
          = 2γ/(π(4γ²+δ²))；又 ∫L² df = 1/(2πγ) ⇒ 比值 = 4γ²/(4γ²+δ²)。
    """
    g2 = 4.0 * float(gamma) ** 2
    return g2 / (g2 + float(delta) ** 2)


def fdm_mux_overlap_candidate(gamma: float = 0.5, delta: float = 1.2,
                              n: int = _N_BY_BID["B508"]) -> float:
    """B508 candidate：sinh 换元 + 复合 Simpson 数值卷积（与 golden 方法学独立）。"""
    ov, slf = _overlap_numeric(float(gamma), float(delta), int(n))
    if slf == 0.0:
        raise ZeroDivisionError("自重叠积分为 0（gamma 非法）")
    return ov / slf


# ── 统一入口（harness / golden.py 按名调用）────────────────────────────────
def golden_b508(gamma: float = 0.5, delta: float = 1.2) -> float:
    return fdm_mux_overlap_golden(gamma, delta)


def cand_b508(gamma: float = 0.5, delta: float = 1.2,
              n: int = _N_BY_BID["B508"]) -> float:
    return fdm_mux_overlap_candidate(gamma, delta, n)


@functools.lru_cache(maxsize=None)
def _g508_c(gamma: float, delta: float) -> float:
    return golden_b508(gamma, delta)


@functools.lru_cache(maxsize=None)
def _c508_c(gamma: float, delta: float, n: int) -> float:
    return cand_b508(gamma, delta, n)


B508_DEFAULT_PARAMS = dict(_B508_DEFAULT)


#: 自检用例：bid, 物理参数（golden 键）, 期望的实测区间（由扫描填）
_CASES = (
    ("B508", _B508_DEFAULT),
)


def _measure_candidates():
    """现算：默认档 golden/cand/残差 + 判据 D 扫描链（粗→细）。"""
    out = {}
    for bid, params in _CASES:
        tol = _TOL_BY_BID[bid]
        grid = _GRID_BY_BID[bid]
        gold = golden_b508(**params)
        chain = []
        for n in grid:
            c = cand_b508(n=n, **params)
            chain.append((n, abs(c - gold)))
        resid = [r for _, r in chain]
        default_n = _N_BY_BID[bid]
        d_res = abs(cand_b508(n=default_n, **params) - gold)
        ratios = [resid[i] / resid[i + 1] for i in range(len(resid) - 1)
                  if resid[i + 1] > 0]
        out[bid] = {
            "golden": gold, "default_n": default_n, "tol": tol,
            "chain": chain, "resid": resid, "default_resid": d_res,
            "mono": all(resid[i] > resid[i + 1] for i in range(len(resid) - 1)),
            "ratios": ratios,
            "margin": tol / d_res if d_res > 0 else float("inf"),
            "gold_over_tol": abs(gold) / tol,
        }
    return out


if __name__ == "__main__":  # pragma: no cover —— 逐锚自检（判据 D 可标定 + 非代数恒等）
    print("=" * 72)
    print("Batch J2-M3 数值核自检（B508 · FDM 多址读出相邻通道频谱重叠串扰比）")
    print("=" * 72)
    bad = 0
    for bid, m in _measure_candidates().items():
        print(f"\n[{bid}] golden={m['golden']:.12e}  tol={m['tol']:.1e}  "
              f"默认 n={m['default_n']}")
        print("  判据 D 残差链：" +
              "  ".join(f"n={n}→{r:.3e}" for n, r in m["chain"]))
        print("  实测比值：  " + "  ".join(f"{x:.2f}×" for x in m["ratios"]))
        print(f"  默认档残差={m['default_resid']:.3e}  余量={m['margin']:.1f}×  "
              f"|golden|/tol={m['gold_over_tol']:.3e}  MONO={m['mono']}")
        for name, cond in (
            ("默认档残差 > 1e-12（排除代数恒等）", m["default_resid"] > 1e-12),
            ("默认档残差 < tol", m["default_resid"] < m["tol"]),
            ("余量 ≥ 100×", m["margin"] >= 100.0),
            ("|golden|/tol ≥ 13.5", m["gold_over_tol"] >= 13.5),
            ("判据 D 严格单调（粗→细）", m["mono"]),
            ("粗端残差浮出地板（>1e-12）", m["resid"][0] > 1e-12),
            ("残差动态范围 ≥ 1e4×（排除「残差与离散参数无关」指纹）",
             m["resid"][0] / m["default_resid"] >= 1e4),
            ("每档比值 > 1（真下降）", all(x > 1.0 for x in m["ratios"])),
        ):
            ok = bool(cond)
            bad += 0 if ok else 1
            print(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    print("\n" + ("ALL PASS" if bad == 0 else f"{bad} FAIL"))
    raise SystemExit(0 if bad == 0 else 1)
