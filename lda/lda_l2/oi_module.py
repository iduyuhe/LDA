"""LDA 光联接模块征程 · M0 基线（收发器式 PIC · 链路/系统级设计）。

============================================================================
定位（吃狗粮式新征程 · 2026-10-02 启动）
----------------------------------------------------------------------------
用 LDA 已有光子积木（MziModulator / RingResonator / GratingCoupler /
Photodetector / Waveguide + lda_chain 级联引擎）拼出一个**基线收发器式
光联接模块 PIC**，证明「能设计出来」，并借设计过程暴露平台短板。

M0 基线定义（最简非平凡 N 通道 WDM 收发器）：
  Tx ：N 路激光(外部源) → N 个 MZI 电光调制器(V 驱动) → 星型合波(理想功率和)
       → GC 离芯片发射(wg→fib)
  光纤 span（net 损耗）
  Rx ：GC 入芯片捕获(fib→wg) → 环形解波(每环谐振一个信道) → N 个光电探测器
逐波长(single-λ)评估：在覆盖全部信道的波长栅上跑一次 simulate，按信道波长
读出各源的端到端传递 —— 同时给出「信道内 IL」与「信道间隔离」。

链路预算用**两种独立方法**互相印证（防自证门禁）：
  (A) 直接闭式分解：mod × η_tx × fiber × η_rx × ring_drop_i
  (B) 级联引擎 simulate 读出 source_i→det_i
  两者须一致（证明装配接线正确，非仅数值合理）。

诚实边界（沿用光子计算 M5 纪律）：
- LDA = 设计 & 验证 EDA，非流片厂；器件为解析模型 L0（无 FDTD 标定/实测校准）。
- 不报 fabricated 带宽 / 能效 / TOPS。
- 调制器、探测器、环、GC 均为**行为/解析级**，真实制备误差/带宽/封装未建模
  （见 transceiver_m0_report 的 gaps 字段，待 M1/M2 补）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# 装配
# ─────────────────────────────────────────────────────────────────────────────
def build_transceiver_m0(n_lanes: int = 2,
                         channels_nm: Optional[List[float]] = None,
                         v_pi_v: float = 4.0,
                         mod_v_on: float = 0.0,
                         gc_coupling: float = 0.5,        # ≈ -3 dB
                         fiber_span_db: float = 1.0,
                         n_g: float = 4.2, m: int = 170,
                         gap: float = 0.3) -> Any:
    """组装基线收发器 PIC 的 LinkModel。"""
    from lda_chain.link_model import LinkModel
    from lda_agent.wdm_system import inverse_ring_for_channel, fsr_nm
    from lda_ir import ObjectiveSpec

    if channels_nm is None:
        channels_nm = [1550.0 + 1.6 * i for i in range(n_lanes)]  # 粗 WDM 基线
    channels_nm = sorted(float(c) for c in channels_nm)

    link = LinkModel(domain="photon", name="oi-m0-transceiver",
                     notes=f"光联接模块 M0 基线 · {n_lanes} 通道 WDM 收发器 PIC")

    # —— Tx：调制器 + 外部激光源 ——
    for i in range(n_lanes):
        link.add_device(f"mod{i}", "MziModulator",
                        params={"V": float(mod_v_on), "V_pi": float(v_pi_v)})
        link.mark_source(f"mod{i}", "in")   # 外部激光注入调制器输入

    # —— Tx 星型合波（理想功率和，无额外损耗）——
    tx_ports = [f"mod{i}.out" for i in range(n_lanes)] + ["gc_tx.wg"]
    link.ir.connect("tx_mux", *tx_ports)

    # —— Tx 离芯片发射 GC（wg→fib）——
    link.add_device("gc_tx", "GratingCoupler",
                    params={"coupling": float(gc_coupling)})

    # —— 光纤 span（gc_tx.fib ↔ gc_rx.fib，net 损耗）——
    link.ir.connect("fiber_span", "gc_tx.fib", "gc_rx.fib")

    # —— Rx 入芯片捕获 GC（fib→wg）——
    link.add_device("gc_rx", "GratingCoupler",
                    params={"coupling": float(gc_coupling)})

    # —— Rx 环形解波 + 探测器 ——
    Rs = [inverse_ring_for_channel(c * 1e-3, n_g, m) for c in channels_nm]
    prev = "gc_rx.wg"
    for i in range(n_lanes):
        rid = f"ring{i}"
        link.add_device(rid, "RingResonator",
                        params={"R": float(Rs[i]), "n_g": n_g, "gap": gap})
        # 设计意图：每环 FSR 目标（与 P1 build_wdm_link 同构，过 IR.validate）
        link.ir.objectives.append(
            ObjectiveSpec(bid="B4",
                          target=round(fsr_nm(channels_nm[i] * 1e-3, Rs[i], n_g), 3),
                          tol=1e-3, role="objective"))
        # 仅首环由 GC 捕获端口喂入；后续环输入由 rx_thru_{i-1} 提供，
        # 不再重复连 rx_in_i（否则与上一环 thru 链形成重复网 → 级联重复计数）
        if i == 0:
            link.ir.connect(f"rx_in_{i}", prev, f"{rid}.in")
        if i + 1 < n_lanes:
            link.ir.connect(f"rx_thru_{i}", f"{rid}.out", f"ring{i + 1}.in")
        link.add_device(f"det{i}", "Photodetector", params={})
        link.ir.connect(f"rx_drop_{i}", f"{rid}.drop", f"det{i}.in")
        link.external_io(f"det{i}_out", f"det{i}", "out")
        prev = f"ring{i}.out"
    # 记录光纤 span 损耗，供级联引擎建模（闭式同样计入 → 两法一致）
    link.link_params["fiber_span_db"] = float(fiber_span_db)
    return link


# ─────────────────────────────────────────────────────────────────────────────
# 仿真 + 预算分解
# ─────────────────────────────────────────────────────────────────────────────
def _wl_grid(channels_nm: List[float], n_pts: int = 201) -> List[float]:
    lo = min(channels_nm) - 0.6
    hi = max(channels_nm) + 0.6
    return [lo + (hi - lo) * k / (n_pts - 1) for k in range(n_pts)]


def simulate_transceiver_m0(link: Any, channels_nm: List[float],
                            wls: Optional[List[float]] = None,
                            net_loss_db: Optional[Dict[str, float]] = None
                            ) -> Dict[str, Any]:
    """跑级联引擎，返回 transfers + 波长栅。

    默认在**精确信道波长**上评估（高 Q 环形谐振峰宽仅 ~0.005nm，粗栅会漏峰
    → 级联 IL/隔离失真）。如需带宽/形状分析可显式传入细栅。

    光纤 span 损耗默认从 link.link_params["fiber_span_db"] 取（与闭式同源），
    确保级联与闭式预算一致；可显式覆盖 net_loss_db。
    """
    from lda_chain.engine import simulate
    if wls is None:
        wls = sorted(c * 1e-3 for c in channels_nm)  # 精确信道波长 = 谐振点
    if net_loss_db is None:
        fs = link.link_params.get("fiber_span_db", 0.0)
        net_loss_db = {"fiber_span": fs} if fs else {}
    res = simulate(link, wls, net_loss_db=net_loss_db)
    return {"wavelengths_um": wls, "transfers": res["transfers"],
            "missing_models": res["missing_models"], "note": res["note"]}


def _nearest(wls: List[float], lam_nm: float) -> int:
    lam_um = lam_nm * 1e-3
    return min(range(len(wls)), key=lambda k: abs(wls[k] - lam_um))


def transceiver_m0_budget(link: Any, channels_nm: List[float],
                          v_pi_v: float = 4.0, mod_v_on: float = 0.0,
                          gc_coupling: float = 0.5,
                          fiber_span_db: float = 1.0,
                          n_g: float = 4.2, gap: float = 0.3,
                          n_pts: int = 201) -> Dict[str, Any]:
    """两种独立方法分解每信道链路预算 + 信道隔离 + 无源锚(B19)。

    光纤 span 损耗默认取自 link.link_params["fiber_span_db"]（build 时写入，
    与级联引擎同源）；仅当显式传入 fiber_span_db 时覆盖。这保证闭式(A)与级联(B)
    始终计入同一光纤损耗 → 两法一致（防 P2 类探针把"闭式漏计光纤"误判为分歧）。
    """
    from lda_agent.ring_adddrop import (adddrop_spectrum,
                                        bending_loss_db_per_cm, gap_to_kappa)
    channels_nm = sorted(float(c) for c in channels_nm)
    n = len(channels_nm)
    # 光纤 span 损耗：优先取 link 写入值，否则用入参默认
    fiber_span_db = float(link.link_params.get("fiber_span_db", fiber_span_db))
    Rs = [None] * n
    for i, c in enumerate(channels_nm):
        from lda_agent.wdm_system import inverse_ring_for_channel
        Rs[i] = inverse_ring_for_channel(c * 1e-3, n_g, 170)
    kappa = gap_to_kappa(gap)
    fiber_g = 10.0 ** (-fiber_span_db / 10.0)

    mod_on = math.cos(math.pi * mod_v_on / (2.0 * v_pi_v)) ** 2
    eta = gc_coupling

    per_channel = []
    for i in range(n):
        # 方法 A：直接闭式分解（含总线 thru 链）
        #   信号抵达目标环 i 之前须穿过前置环 0..i-1 的 thru（非目标环在总线
        #   上直通），故 IL_i = mod·η·fiber·η·(Π_{k<i} thru_k)·drop_i。
        #   （初版漏算前置 thru → 与级联不符；级联引擎含总线全链路，为真值）
        lam_i = channels_nm[i] * 1e-3
        bus = 1.0
        ring_drop = 0.0
        for k in range(i + 1):
            a_bend_k = bending_loss_db_per_cm(Rs[k])
            sp_k = adddrop_spectrum([lam_i], Rs[k], n_g, kappa, a_bend_k, 1.55)
            if k < i:
                bus *= sp_k["thru"][0]
            else:
                bus *= sp_k["drop"][0]
                ring_drop = sp_k["drop"][0]
        a_il = mod_on * eta * fiber_g * eta * bus

        # 方法 B：级联引擎（精确信道波长）
        sim = simulate_transceiver_m0(link, channels_nm)
        wls = sim["wavelengths_um"]
        idx = _nearest(wls, channels_nm[i])
        key_on = f"mod{i}.in->det{i}.out"
        b_il = sim["transfers"].get(key_on, [0.0] * len(wls))[idx]

        # 信道隔离：同信道的源串到其它探测器（在 λ_i 处）
        xtalk = 0.0
        for j in range(n):
            if j == i:
                continue
            key_xt = f"mod{i}.in->det{j}.out"
            v = sim["transfers"].get(key_xt, [0.0] * len(wls))[idx]
            xtalk += v
        iso_db = -10.0 * math.log10(xtalk / b_il) if (b_il > 0 and xtalk > 0) else float("inf")

        per_channel.append({
            "lane": i, "channel_nm": channels_nm[i], "R_um": Rs[i],
            "mod_on": mod_on, "gc_launch": eta, "fiber_g": fiber_g,
            "gc_capture": eta, "ring_drop": ring_drop,
            "il_a_db": -10.0 * math.log10(max(a_il, 1e-12)),
            "il_b_db": -10.0 * math.log10(max(b_il, 1e-12)),
            "il_ab_diff_db": abs(-10.0 * math.log10(max(a_il, 1e-12))
                                 - -10.0 * math.log10(max(b_il, 1e-12))),
            "crosstalk_power": xtalk, "isolation_db": iso_db,
            "missing_models": sim["missing_models"],
        })
    # 无源锚 B19：所有 transfer 幅值 ≤ 1（无增益）
    b19_pass = True
    for vec in sim["transfers"].values():
        for v in vec:
            if abs(v) > 1.0 + 1e-9:
                b19_pass = False
    # 设计洞察（诚实边界 · 平台 L0 模型基线特征，待 M1 优化）
    min_iso = min((pc["isolation_db"] for pc in per_channel), default=float("inf"))
    design_notes = []
    if min_iso < 30.0:
        design_notes.append(
            f"相邻信道隔离最小 {min_iso:.1f}dB（L0 环模型在 {channels_nm[1]-channels_nm[0]:.1f}nm "
            f"信道间隔下的本征旁瓣限制）——M1 调优目标：加大信道间隔或抬高环 Q（窄线宽）")
    if any(pc["il_a_db"] > 15.0 for pc in per_channel):
        design_notes.append("基线 IL 偏高（GC -3dB×2 + 光纤 + 环总线 thru 累积）——"
                            "M1 通过低损耗 GC / 短总线 / 高 Q 环压缩")
    return {"n_lanes": n, "channels_nm": channels_nm, "per_channel": per_channel,
            "b19_passivity": b19_pass, "v_pi_v": v_pi_v, "mod_v_on": mod_v_on,
            "gc_coupling": gc_coupling, "fiber_span_db": fiber_span_db,
            "design_notes": design_notes}


# ─────────────────────────────────────────────────────────────────────────────
# 自检（不含突变探针；突变探针在 run_oi_m0_smoke.py）
# ─────────────────────────────────────────────────────────────────────────────
def transceiver_m0_self_check(verbose: bool = True) -> Dict[str, Any]:
    n_lanes = 2
    channels = [1550.0, 1551.6]
    link = build_transceiver_m0(n_lanes=n_lanes, channels_nm=channels)
    assert link.validate() == [], f"IR.validate 应无错误：{link.validate()}"
    rep = transceiver_m0_budget(link, channels)
    checks = []
    # 1) 无缺失模型
    checks.append(("无缺失器件模型", all(not pc["missing_models"]
                                          for pc in rep["per_channel"])))
    # 2) B19 无源无增益
    checks.append(("B19 无源无增益 |T|≤1", rep["b19_passivity"]))
    # 3) 两法预算一致（装配接线正确）
    checks.append(("链路预算 闭式≡级联 (≤0.05dB)",
                   all(pc["il_ab_diff_db"] <= 0.05 for pc in rep["per_channel"])))
    # 4) 信道隔离达标（≥ 15 dB 为 M0·L0 基线下限；<30dB 见 design_notes 调优目标）
    checks.append(("信道隔离 ≥ 15 dB（M0·L0 基线下限）",
                   all((pc["isolation_db"] >= 15.0)
                       for pc in rep["per_channel"])))
    # 5) 基线 IL 在合理区间（不是 0 也不是 ∞）
    checks.append(("基线 IL 在 [3, 20] dB",
                   all(3.0 <= pc["il_b_db"] <= 20.0
                       for pc in rep["per_channel"])))
    ok = all(v for _, v in checks)
    if verbose:
        print("=== OI M0 自检 ===")
        for name, v in checks:
            print(f"  [{'PASS' if v else 'FAIL'}] {name}")
        for pc in rep["per_channel"]:
            print(f"  通道{pc['lane']} {pc['channel_nm']}nm: "
                  f"IL(a)={pc['il_a_db']:.2f}dB IL(b)={pc['il_b_db']:.2f}dB "
                  f"隔离={pc['isolation_db']:.1f}dB")
        for note in rep.get("design_notes", []):
            print(f"  · 设计洞察: {note}")
    return {"ok": ok, "checks": checks, "report": rep}


if __name__ == "__main__":
    r = transceiver_m0_self_check()
    raise SystemExit(0 if r["ok"] else 1)
