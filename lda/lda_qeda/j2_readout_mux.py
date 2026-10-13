"""J2 M3 · 超导 Transmon 色散读出链 + FDM 多址 mux 规划（吃狗粮）。

承 J2 蓝图 M3「色散读出链 + 串扰」：把读出链补成**可签核**的一环。

物理链（全闭式 + 复用既有 S 分支模块，零量子 SDK）：
  · **通道隔离（本档新锚 B508 的工程化）**：FDM 把 N 个 λ/4 读出谐振器挂同一 feedline，
    每个通道线型是洛伦兹 L(f)=(γ/π)/((f−f_c)²+γ²)（γ=κ/2 半高半宽）。相邻通道间隔 δ 时
    归一化频谱重叠（串扰比）
        X(δ;γ) = ∫L_iL_j df / ∫L_i² df = 4γ²/(4γ²+δ²) = 1/(1+(δ/(2γ))²)。
    给定串扰容限 X_tol ⇒ **最小通道间隔** Δf_min = 2γ·√(1/X_tol − 1)；
    带宽 B 内可容纳通道数 N_max = ⌊B/Δf_min⌋（复用 `sc_freq_alloc.frequency_capacity`）。
  · **残余静态 ZZ 预算**：复用 `sc_readout.crosstalk_budget` 的全 pair ζ_zz 与
    **σ_zz ≤ 1.0 MHz 硬上限**（S 铁律②；D-140/D-142 频率规划同口径）。
  · `readout_chain_budget`：通道隔离 ∧ ZZ 预算 **双 ACCEPT** ⇒ 读出链签核。

诚实边界：γ/δ/B/X_tol 均为**设计参数**（非实测 PDK/非流片）；本模块只做**设计预算**
（不含量子线路仿真、不含脉冲级控制），结论只可用于设计与量级，**不得作制造/性能宣称**。
红线：纯 numpy/标准库 · 零量子 SDK · LLM 不进判决路径 · 阈值为设计规则。
"""
from __future__ import annotations

from typing import Dict, Optional

from lda_qeda import sc_readout as S4
from lda_qeda.sc_freq_alloc import frequency_capacity

# 读出 mux 设计阈值（设计参数 · 可覆盖 · 非实测 golden）
DEFAULT_MUX = {
    "kappa_mhz": 1.0,        # 读出谐振器线宽 κ（FWHM，MHz）⇒ γ = κ/2
    "delta_mhz": 1.2,        # 相邻通道频率间隔 δ（MHz）
    "band_mhz": 500.0,       # 读出频带 B（MHz）
    "x_tol": 0.02,           # 相邻通道串扰容限（2%）
}


def mux_overlap_ratio(gamma_mhz: float, delta_mhz: float) -> float:
    """洛伦兹通道归一化重叠比 X(δ;γ)=4γ²/(4γ²+δ²)（闭式 · 与 B508 golden 同一物理律）。"""
    g2 = 4.0 * float(gamma_mhz) ** 2
    return g2 / (g2 + float(delta_mhz) ** 2)


def min_spacing_for_crosstalk(gamma_mhz: float, x_tol: float) -> float:
    """给定串扰容限 X_tol 的最小通道间隔 Δf_min = 2γ·√(1/X_tol − 1)（MHz）。

    🔴 本式是 X(δ) 的**代数反解**（不是独立物理量）⇒ 只作设计用，**不登记为锚**
    （B-11 被否候选「开普勒方程数值求根（代数恒等改写 ⇒ 判据 D 不响应）」先例）。
    """
    x = float(x_tol)
    if not (0.0 < x < 1.0):
        raise ValueError("串扰容限须落 0 < X_tol < 1，实际 %r" % x_tol)
    return 2.0 * float(gamma_mhz) * (1.0 / x - 1.0) ** 0.5


def mux_capacity(band_mhz: Optional[float] = None,
                 kappa_mhz: Optional[float] = None,
                 x_tol: Optional[float] = None) -> Dict:
    """FDM mux 容量：带宽 B + 线宽 κ + 串扰容限 X_tol ⇒ {Δf_min, N_max}。"""
    d = DEFAULT_MUX
    B = float(d["band_mhz"] if band_mhz is None else band_mhz)
    kap = float(d["kappa_mhz"] if kappa_mhz is None else kappa_mhz)
    xt = float(d["x_tol"] if x_tol is None else x_tol)
    gamma = kap / 2.0
    dmin = min_spacing_for_crosstalk(gamma, xt)
    n_max = frequency_capacity(B / 1000.0, dmin)     # 复用 sc_freq_alloc 闭式
    return {
        "band_mhz": B, "kappa_mhz": kap, "gamma_mhz": gamma,
        "x_tol": xt, "delta_min_mhz": dmin, "n_max": n_max,
        "note": ("FDM mux 容量 = 通道隔离判据：Δf_min=2γ√(1/X_tol−1)（γ=κ/2），"
                 "N_max=⌊B/Δf_min⌋。复用 `sc_freq_alloc.frequency_capacity`。"),
    }


def readout_zz_budget(params: Optional[Dict] = None) -> Dict:
    """复用 S4 `crosstalk_budget` 的残余静态 ZZ 预算（σ_zz ≤ 1.0 MHz 硬上限 · 铁律②）。"""
    xt = S4.crosstalk_budget(params)
    return {
        "max_stray_zz_mhz": float(xt["max_stray_zz_mhz"]),
        "zz_stray_limit_mhz": float(xt["zz_stray_limit_mhz"]),
        "stray_zz_ok": bool(xt["stray_zz_ok"]),
        "max_control_xtalk": float(xt["max_control_xtalk"]),
        "control_xtalk_limit": float(xt["control_xtalk_limit"]),
        "control_xtalk_ok": bool(xt["control_xtalk_ok"]),
        "verdict": xt["verdict"],
        "note": "复用 sc_readout.crosstalk_budget（全 pair ζ_zz=2J²α/(Δ(Δ+α)) 闭式）。",
    }


def readout_chain_budget(params: Optional[Dict] = None,
                         x_tol: Optional[float] = None) -> Dict:
    """读出链签核 = FDM 通道隔离 ∧ 残余 ZZ 预算 双 ACCEPT。"""
    mux = mux_capacity(x_tol=x_tol)
    zz = readout_zz_budget(params)
    iso_ok = bool(mux["n_max"] >= 2)
    verdict = "ACCEPT" if (iso_ok and zz["stray_zz_ok"]) else "REJECT"
    return {
        "verdict": verdict, "mux": mux, "zz": zz,
        "mux_iso_ok": iso_ok,
        "note": ("读出链 = FDM 通道隔离（X≤X_tol ∧ N_max≥2）+ 残余静态 ZZ "
                 "（σ_zz≤1.0 MHz）双 ACCEPT。设计预算，不含量子线路仿真。"),
    }


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：闭式链单调性 / 反解一致 / 容量单调 / ZZ 预算复用 / 签核良定义。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    g = 0.5
    # ① 重叠比：δ→0 ⇒ 1；δ≫γ ⇒ 0；严格单调下降
    chk("X(δ→0)=1", abs(mux_overlap_ratio(g, 0.0) - 1.0) < 1e-15)
    chk("X 单调降", all(mux_overlap_ratio(g, d1) > mux_overlap_ratio(g, d2)
                        for d1, d2 in ((0.5, 1.0), (1.0, 2.0), (2.0, 4.0))))
    chk("X(δ≫γ)→0", mux_overlap_ratio(g, 1e4) < 1e-8)
    # ② 反解自洽：Δf_min 处重叠比恰 == X_tol
    for xt in (0.01, 0.02, 0.05, 0.1):
        dmin = min_spacing_for_crosstalk(g, xt)
        chk("反解自洽 X(Δf_min)=X_tol (%.3f)" % xt,
            abs(mux_overlap_ratio(g, dmin) - xt) < 1e-12)
    # ③ 容量：带宽↑ ⇒ N_max 不减；线宽↑ ⇒ N_max 不增；与复用的闭式一致
    c1 = mux_capacity(band_mhz=500.0)
    c2 = mux_capacity(band_mhz=1000.0)
    c3 = mux_capacity(kappa_mhz=2.0)
    chk("容量随带宽单调不减", c2["n_max"] >= c1["n_max"])
    chk("容量随线宽单调不增", c3["n_max"] <= c1["n_max"])
    chk("容量 ≥ 2（mux 可用）", c1["n_max"] >= 2)
    chk("与 sc_freq_alloc 闭式一致",
        c1["n_max"] == frequency_capacity(0.5, c1["delta_min_mhz"]))
    # ④ ZZ 预算复用：合法默认 ⇒ ACCEPT；σ_zz 恰好可读
    zz = readout_zz_budget()
    chk("ZZ 预算可读", zz["zz_stray_limit_mhz"] == S4.ZZ_STRAY_LIMIT_MHZ)
    chk("ZZ 预算有限非负", zz["max_stray_zz_mhz"] >= 0.0)
    # ⑤ 签核良定义：ACCEPT/REJECT 二值 + 双条件一致
    cb = readout_chain_budget()
    chk("签核二值", cb["verdict"] in ("ACCEPT", "REJECT"))
    chk("签核 = 双条件",
        (cb["verdict"] == "ACCEPT") == (cb["mux_iso_ok"] and cb["zz"]["stray_zz_ok"]))
    # ⑥ 反向：容限取到荒谬小 ⇒ 容量塌到 1 ⇒ 隔离判 REJECT
    cb_bad = readout_chain_budget(x_tol=1e-6)
    chk("反向：X_tol→0 ⇒ 隔离 FAIL", not cb_bad["mux_iso_ok"])

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J2 M3 读出链 + FDM mux 规划自检")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
