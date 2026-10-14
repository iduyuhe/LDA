# -*- coding: utf-8 -*-
"""J3 M4 · 低温电子学能力层：Caves 量子极限 + 级联噪声 + cryo-CMOS 权衡。

════════════════════════════════════════════════════════════════
物理（章程 §3 M4 · 缺口 G-CTRL-4）——

  · **Caves 量子极限**：相位不敏感线性放大器（如 JPA/HEMT）的输入参考附加噪声
    **n_add ≥ 1/2 光子**（Caves 1982 量子极限）。JPA 接近此限；HEMT 远高于此。
  · **级联噪声（Friis）**：多级放大链的输入参考附加噪声
        n_add,total = n₁ + n₂/G₁ + n₃/(G₁G₂) + …
    ⇒ 前级高增益把后级噪声压低（这就是低温第一级要用 JPA 的原因）。
  · **分布式放大链**：行波参量放大器（TWPA）的附加噪声
        n_add = (η/g)(1 − e^{−gL})，  gL→∞ ⇒ n_add → η/g = 1/2（量子极限）。
  · **cryo-CMOS 权衡**：多路复用器通道数 ↑ ⇒ 冷却功耗 ↑（4 K / 20 mK 制冷预算），
    噪声略增；给出功耗-噪声工作点。

🔴 与账本锚 **B514** 同物理律（`run_j3_ctrl_smoke` 节点核验）：
   `distributed_amp_nadd ≡ B514 golden`；`caves_limit_nadd ≡ 1/2`（Caves 极限）。

主权：纯 math/numpy；**零商业 PDK / 无 SPICE**（闭式噪声链）。设计预算，非流片实测。
"""
from __future__ import annotations

import math

#: 物理常数（示例量级用）
_H_PLANCK = 6.62607015e-34      # J·s
_K_B = 1.380649e-23            # J/K

#: 默认放大链（示例量级）：JPA（近量子极限）→ HEMT（4 K）→ 室温
DEFAULT_CHAIN = (
    ("JPA", {"gain_db": 20.0, "n_add": 0.5}),      # 接近 Caves 极限
    ("HEMT", {"gain_db": 30.0, "n_add": 15.0}),    # 4 K HEMT 典型
    ("room", {"gain_db": 30.0, "n_add": 1e4}),     # 室温后级（被前面增益压低）
)


def caves_limit_nadd() -> float:
    """Caves 量子极限：相位不敏感放大器附加噪声下限 **n_add = 1/2 光子**。"""
    return 0.5


def distributed_amp_nadd(eta_ratio: float = 0.5, g: float = 0.5, L: float = 10.0) -> float:
    """分布式（行波）放大链输入参考附加噪声（与 B514 golden 同式）。

        n_add = (η/g)·(1 − e^{−gL})；η/g = 单位增益附加噪声（量子极限 = 1/2）。
    """
    return float(eta_ratio) * (1.0 - math.exp(-float(g) * float(L)))


def db_to_linear(gain_db: float) -> float:
    """功率增益（dB）→ 线性倍数。"""
    return 10.0 ** (float(gain_db) / 10.0)


def friis_cascade(stages) -> dict:
    """Friis 级联：输入参考附加噪声 = n₁ + n₂/G₁ + n₃/(G₁G₂) + …。

    stages = [(name, {"gain_db": g, "n_add": n}), …]（顺序 = 信号传播方向）。
    返回 n_add_in（输入参考总附加噪声光子数）、g_total（总增益倍数）、逐级贡献。
    """
    total = 0.0
    g_cum = 1.0
    contrib = []
    for name, spec in stages:
        n = float(spec["n_add"])
        c = n / g_cum
        contrib.append((name, c))
        total += c
        g_cum *= db_to_linear(float(spec["gain_db"]))
    return {"n_add_in": total, "g_total": g_cum, "contributions": contrib}


def photon_to_temperature(n_add: float, freq_ghz: float) -> float:
    """附加噪声光子数 → 等效噪声温度（K）：T = n_add·h·f/k_B。"""
    return float(n_add) * _H_PLANCK * float(freq_ghz) * 1e9 / _K_B


def cryo_cmos_tradeoff(n_mux: int = 8, power_per_ch_mw: float = 1.0,
                       noise_penalty_per_ch: float = 1e-3) -> dict:
    """cryo-CMOS 多路复用权衡：通道数 ↑ ⇒ 冷却功耗 ↑、噪声略增。

    · 总功耗 = n_mux · power_per_ch_mw（mW）—— 受 4 K/20 mK 制冷预算约束；
    · 噪声惩罚 = 1 + n_mux·noise_penalty_per_ch（复用器插损/串扰）。
    """
    n_mux = int(n_mux)
    if n_mux < 1:
        raise ValueError("n_mux ≥ 1")
    return {
        "n_mux": n_mux,
        "total_power_mw": n_mux * float(power_per_ch_mw),
        "noise_penalty": 1.0 + n_mux * float(noise_penalty_per_ch),
    }


DEFAULT_CRYO = {"eta_ratio": 0.5, "g": 0.5, "L": 10.0,
                "freq_ghz": 5.0, "n_add_limit": 2.0}


def cryo_noise_report(eta_ratio: float = None, g: float = None, L: float = None) -> dict:
    """低温电子学签核报告：放大链附加噪声 ∧ 量子极限可达性 双条件。"""
    d = DEFAULT_CRYO
    eta_ratio = d["eta_ratio"] if eta_ratio is None else float(eta_ratio)
    g = d["g"] if g is None else float(g)
    L = d["L"] if L is None else float(L)
    n_dist = distributed_amp_nadd(eta_ratio, g, L)
    cas = friis_cascade(DEFAULT_CHAIN)
    # 量子极限可达性：分布式链的 η/g 是否 = 1/2（Caves）
    at_limit = abs(eta_ratio - caves_limit_nadd()) < 1e-15
    within = cas["n_add_in"] < d["n_add_limit"]
    verdict = "ACCEPT" if (within and at_limit) else "REJECT"
    return {
        "verdict": verdict,
        "caves_limit": caves_limit_nadd(),
        "distributed_nadd": n_dist,
        "eta_ratio": eta_ratio,
        "cascade_nadd_in": cas["n_add_in"],
        "cascade_contributions": cas["contributions"],
        "n_add_limit": d["n_add_limit"],
        "within_limit": within,
        "at_quantum_limit": at_limit,
        "t_add_mk": photon_to_temperature(cas["n_add_in"], d["freq_ghz"]) * 1e3,
        "note": ("低温电子学 = Caves 量子极限（n_add ≥ 1/2）+ Friis 级联 + cryo-CMOS 权衡。"
                 "设计预算（非流片 / 非商用 PDK），闭式噪声链，无 SPICE。"),
    }


def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：Caves 极限 / 分布式极限 / Friis 级联 / 增益压制 / 权衡单调 / 签核二值。"""
    bad = []

    def chk(name: str, cond: bool) -> None:
        if verbose:
            print("  [%s] %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            bad.append(name)

    # ① Caves 量子极限 = 1/2
    chk("Caves 极限 = 1/2", abs(caves_limit_nadd() - 0.5) < 1e-15)
    # ② 分布式链：gL→∞ ⇒ → η/g = 1/2；gL→0 ⇒ → 0；单调增
    chk("分布式 gL→∞ ⇒ 量子极限 1/2",
        abs(distributed_amp_nadd(0.5, 5.0, 100.0) - 0.5) < 1e-15)
    chk("分布式 gL→0 ⇒ → 0", distributed_amp_nadd(0.5, 0.5, 1e-6) < 1e-6)
    chk("分布式随 gL 单调增",
        distributed_amp_nadd(0.5, 0.5, 2.0) < distributed_amp_nadd(0.5, 0.5, 5.0)
        < distributed_amp_nadd(0.5, 0.5, 10.0))
    # ③ Friis：单级 ⇒ = 自身
    one = friis_cascade([("A", {"gain_db": 20.0, "n_add": 7.0})])
    chk("Friis 单级 = 自身", abs(one["n_add_in"] - 7.0) < 1e-15)
    # ④ 增益压制：前级增益↑ ⇒ 后级贡献↓（单调）
    def _tail(g1_db):
        c = friis_cascade([("A", {"gain_db": g1_db, "n_add": 0.5}),
                           ("B", {"gain_db": 30.0, "n_add": 100.0})])
        return c["contributions"][1][1]
    chk("前级增益↑ ⇒ 后级贡献↓", _tail(10.0) > _tail(20.0) > _tail(30.0))
    # ⑤ 噪声温度：0.5 光子 @5 GHz ⇒ ~0.12 K（h f/k_B=0.24 K ⇒ 0.5 光子 0.12 K）
    t = photon_to_temperature(0.5, 5.0)
    chk("0.5 光子 @5 GHz ⇒ ~0.12 K", 0.1 < t < 0.15)
    # ⑥ cryo-CMOS 权衡：功耗随通道数线性、噪声惩罚单调
    c1 = cryo_cmos_tradeoff(4)
    c2 = cryo_cmos_tradeoff(16)
    chk("功耗随 n_mux 线性（×4）", abs(c2["total_power_mw"] / c1["total_power_mw"] - 4.0) < 1e-12)
    chk("噪声惩罚随 n_mux 单调增", c2["noise_penalty"] > c1["noise_penalty"])
    # ⑦ 分布式噪声恒 ≤ 量子极限 1/2（η/g = 1/2 时的上确界）
    chk("分布式噪声 ≤ 1/2 上确界", distributed_amp_nadd(0.5, 0.5, 10.0) < 0.5)
    # ⑧ 签核二值 + 反向（把 η/g 设成 1 ⇒ 非量子极限 ⇒ REJECT）
    rep = cryo_noise_report()
    chk("低温电子学默认 ACCEPT", rep["verdict"] == "ACCEPT")
    chk("签核二值", rep["verdict"] in ("ACCEPT", "REJECT"))
    bad_rep = cryo_noise_report(eta_ratio=1.0)
    chk("反向：η/g=1 ≠ 量子极限 ⇒ REJECT", bad_rep["verdict"] == "REJECT")

    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J3 M4 低温电子学自检（Caves 极限 + Friis 级联 + cryo-CMOS）")
    ok = run_selfchecks(verbose=True)
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
