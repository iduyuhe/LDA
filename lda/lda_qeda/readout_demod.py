# -*- coding: utf-8 -*-
"""J3 M3 · 读出链能力层：匹配滤波 + IQ 解调 + 判别阈值 + 分配矩阵 + Purcell 滤波。

════════════════════════════════════════════════════════════════
物理（章程 §3 M3 · 缺口 G-CTRL-3）——

  · **匹配滤波 / 积分窗**：把测量信噪比从 **√t** 累积（白噪极限），最优积分时间由
    χ/κ_r 决定（复用 D-47 静态预算，不重做）。
  · **IQ 解调 + 判别**：|0⟩/|1⟩ 对应 IQ 平面两个高斯团 ⇒ 最近邻/阈值判别，
    误判率 **ε = ½·erfc(SNR/√2)**（与 D-47 `readout_fidelity` **同口径**）。
  · **分配矩阵**：A[i][j] = P(判为 i | 真实 j)，**列和 = 1**（列 j = 真实态）。
  · **Purcell 滤波器抑制比**：并联开路 λ/4 短截线把 qubit 经 feedline 的 Purcell
    外泄率压低 **S = 1/|S21(f_q)|²** 倍（与账本锚 **B513** 同物理律）。

🔴 与账本锚 **B513** 同物理律（`run_j3_ctrl_smoke` 节点核验）：
   `purcell_suppression ≡ B513 golden`。

主权：纯 numpy/math；**零量子 SDK**。设计预算，不含量子线路噪声仿真。
"""
from __future__ import annotations

import math


def matched_filter_snr(amp: float, noise: float, n_avg: int = 1) -> float:
    """匹配滤波 SNR = (amp/noise)·√n_avg（白噪累积 ⇒ √t 律）。"""
    amp, noise, n_avg = float(amp), float(noise), int(n_avg)
    if noise <= 0.0 or n_avg < 1:
        raise ValueError("noise > 0 且 n_avg ≥ 1")
    return amp / noise * math.sqrt(n_avg)


def readout_error_probability(snr: float) -> float:
    """IQ 高斯判别误判率 **ε = ½·erfc(SNR/√2)**（与 D-47 / B30 同口径）。"""
    return 0.5 * math.erfc(float(snr) / math.sqrt(2.0))


def discrimination_threshold(mu0: float, mu1: float) -> float:
    """等方差高斯的最优判别阈值 θ* = (μ0 + μ1)/2（最大似然）。"""
    return 0.5 * (float(mu0) + float(mu1))


def assignment_matrix(eps0: float, eps1: float) -> list:
    """分配矩阵 A[i][j] = P(判为 i | 真实 j)（**列和** = 1，列 j 为真实态）。

    A = [[1−ε0, ε1], [ε0, 1−ε1]]（列 0 = 真实 |0⟩、列 1 = 真实 |1⟩）。
    """
    eps0, eps1 = float(eps0), float(eps1)
    if not (0.0 <= eps0 <= 1.0 and 0.0 <= eps1 <= 1.0):
        raise ValueError("ε 须 ∈ [0, 1]")
    return [[1.0 - eps0, eps1], [eps0, 1.0 - eps1]]


def purcell_suppression(f_q: float = 5.5, f_s: float = 6.0,
                        z_ratio: float = 1.0) -> float:
    """Purcell 滤波器抑制比 **S = 1/|S21(f_q)|²**（与 B513 golden 同式）。

    S21 = 2/(2 + j·(Z0/Zs)·tan βl)，βl = (π/2)(f_q/f_s)。

    🔴 **带阻极点边界（如实登记）**：βl → π/2（即 f_q → f_s）时 tan 发散 ⇒ **S → ∞**
    （物理上 = 完美带阻）。**跨过**极点（f_q > f_s ⇒ βl > π/2）时 tan **变号** ⇒
    抑制比转为有限小值；账本锚 B513 的数值候选（导纳 ODE `dy/dθ=j(1−y²)`）在极点附近
    |y| → ∞ ⇒ **数值发散**。本设计档 f_q/f_s = 11/12（βl ≈ 1.44，离极点留有余量）。
    """
    th = (math.pi / 2.0) * (float(f_q) / float(f_s))
    s21 = 2.0 / complex(2.0, float(z_ratio) * math.tan(th))
    return 1.0 / abs(s21) ** 2


def purcell_t1_gain(suppression: float) -> float:
    """滤波器带来的 T1 提升倍率 = 抑制比 S（T1^{filter} = S·T1^{no}）。"""
    return float(suppression)


DEFAULT_READOUT = {"snr": 4.0, "f_q": 5.5, "f_s": 6.0, "z_ratio": 1.0,
                   "eps_target": 1e-2, "suppression_target": 5.0}


def readout_chain_report(snr: float = None, f_q: float = None, f_s: float = None,
                         z_ratio: float = None) -> dict:
    """读出链签核报告：判别误判 ∧ Purcell 抑制 双条件。"""
    d = DEFAULT_READOUT
    snr = d["snr"] if snr is None else float(snr)
    f_q = d["f_q"] if f_q is None else float(f_q)
    f_s = d["f_s"] if f_s is None else float(f_s)
    z_ratio = d["z_ratio"] if z_ratio is None else float(z_ratio)
    eps = readout_error_probability(snr)
    sup = purcell_suppression(f_q, f_s, z_ratio)
    eps_ok = eps < d["eps_target"]
    sup_ok = sup >= d["suppression_target"]
    verdict = "ACCEPT" if (eps_ok and sup_ok) else "REJECT"
    return {
        "verdict": verdict,
        "snr": snr, "readout_error": eps, "eps_target": d["eps_target"], "eps_ok": eps_ok,
        "purcell_suppression": sup, "suppression_target": d["suppression_target"],
        "suppression_ok": sup_ok,
        "t1_gain": purcell_t1_gain(sup),
        "assignment": assignment_matrix(eps, eps),
        "threshold": discrimination_threshold(0.0, 1.0),
        "note": ("读出链 = IQ 判别（ε=½erfc(SNR/√2)，与 D-47 同口径）+ Purcell 滤波抑制"
                 "（S=1/|S21|²，与 B513 同律）双 ACCEPT。设计预算，不含量子线路仿真。"),
    }


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：erfc 口径 / 单调性 / 分配矩阵行和 / Purcell 极限 / 签核二值。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    # ① 误判率闭式：ε(SNR=5) 逐位 == ½erfc(5/√2)
    chk("ε 闭式口径", abs(readout_error_probability(5.0)
                        - 0.5 * math.erfc(5.0 / math.sqrt(2.0))) < 1e-18)
    # ② ε 随 SNR 单调降 + 极限
    chk("ε 单调降", all(readout_error_probability(s1) > readout_error_probability(s2)
                        for s1, s2 in ((1.0, 2.0), (2.0, 4.0), (4.0, 8.0))))
    chk("ε(SNR→0) = 1/2", abs(readout_error_probability(0.0) - 0.5) < 1e-15)
    chk("ε(SNR 大)→0", readout_error_probability(10.0) < 1e-22)
    # ③ 匹配滤波 √n 律
    s1 = matched_filter_snr(1.0, 1.0, n_avg=1)
    s4 = matched_filter_snr(1.0, 1.0, n_avg=4)
    chk("匹配滤波 √n 律", abs(s4 / s1 - 2.0) < 1e-15)
    # ④ 判别阈值居中
    chk("判别阈值 = (μ0+μ1)/2", abs(discrimination_threshold(0.0, 1.0) - 0.5) < 1e-15)
    # ⑤ 分配矩阵**列和** = 1（列 = 真实态）
    A = assignment_matrix(0.03, 0.07)
    col_sums = [sum(A[i][j] for i in range(2)) for j in range(2)]
    chk("分配矩阵列和 = 1", all(abs(c - 1.0) < 1e-15 for c in col_sums))
    # ⑥ Purcell 抑制：f_q → f_s ⇒ 发散（带阻）；远离 ⇒ → 1（透明）；≥ 1 恒成立
    chk("Purcell S ≥ 1 恒成立", all(purcell_suppression(f_q=f) >= 1.0
                                 for f in (1.0, 3.0, 5.0, 5.9)))
    chk("Purcell f_q→f_s ⇒ 大抑制", purcell_suppression(f_q=5.99, f_s=6.0) > 100.0)
    chk("Purcell 远离 ⇒ →1", abs(purcell_suppression(f_q=0.01, f_s=6.0) - 1.0) < 1e-3)
    chk("Purcell 单调（f_q↑靠近 f_s ⇒ S 增）",
        purcell_suppression(f_q=5.0) < purcell_suppression(f_q=5.5)
        < purcell_suppression(f_q=5.8))
    # ⑦ 签核：默认 ACCEPT + 反向可证伪
    rep = readout_chain_report()
    chk("读出链默认 ACCEPT", rep["verdict"] == "ACCEPT")
    chk("签核二值", rep["verdict"] in ("ACCEPT", "REJECT"))
    bad_rep = readout_chain_report(snr=0.5)
    chk("反向：SNR=0.5 ⇒ REJECT", bad_rep["verdict"] == "REJECT")
    bad_sup = readout_chain_report(f_q=2.0)
    chk("反向：f_q 远离 ⇒ 抑制不足 REJECT", bad_sup["verdict"] == "REJECT")

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J3 M3 读出链自检（IQ 解调 + 分配矩阵 + Purcell 滤波）")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
