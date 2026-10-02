# -*- coding: utf-8 -*-
"""LDA WebUI · 光联接模块案例卡（M0 双通道基线 + M1 800G + M2 1.6T/LPO/真 GDS · 只读案例）。

============================================================================
A 档接入（对齐 qchip/schip/pchip/ecore/accel/d4 案例卡体例）
----------------------------------------------------------------------------
把「光联接模块新征程」以**只读案例**呈现：
  · **M0**：2 通道 WDM 收发器基线（Tx MZI 调制器阵列 + Rx 微环 add-drop 滤波阵列 +
    双 GratingCoupler + 光纤 span）—— 功率/链路预算层。
  · **M1**：在其上补 **频域（级联 EO S21 / −3dB 带宽）** 与 **时域（PAM4 三眼 / Q /
    链路预算级 BER / 光纤色散 / 驱动-TIA 协同）**，并给出**梳齿规避信道规划**
    （8 通道隔离 −0.85dB → 39.5dB 的根因与解）。
  · **M2**：规模翻到 **1.6T（8×200G PAM4）** + **LPO「模块内无 DSP」形态**（设计约束，
    非免责声明：FEC 口径由级联 4.8e-3 收紧回 RS-only 2.4e-4 ⇒ 所需 SNR 上升 2.744dB）
    + **G-OI2 收发器专用真 GDS 版图**（Tx 调制器阵列 + MMIC 合波 + GC / GC + 环解波 +
    探测器阵列，单次主权 DRC/LVS 双闸）。

🔴 只读与缓存纪律：结果为**确定性现算**（纯闭式 + 级联引擎 + IFFT 时域 + 几何搜索 +
收发器真 GDS，零重计算 / 不跑 P&R / 不跑 FDTD），首次调用后按配置键**模块级缓存**（同配置秒回）。
不进 HEAVY_POST_PATHS、不要求登录（与 qchip/schip/pchip/ecore/accel/d4 同属
「公开只读验货」类）。

🔴 不伪装实测：`verdict` 恒为 `DESIGN_BUDGET`（非 ACCEPT/PASS）——链路/带宽预算是
设计期行为验证，非流片后实测；**不报 TOPS/TOPS-W/fJ/op/pJ/bit**。

🔴 诚实边界：M0/M1/M2 均为**设计预算层**（器件用 L0 级解析模型 + A 档闭式/行为级）；
M1/M2 的 BER 是**光通道预算级**闭式估计（不含 SerDes/DSP/FEC/均衡/CDR，与
`eic_behavioral.EIC_DISCLOSURE` 的 EIC 电路级排除**显式分层**），接受 SNR 为
**设计输入假设**（M2 另给 TIA 噪声闭式**上界**做方法学独立交叉核对）；真实版图 GDS 由
D4 域 `photonic_interconnect` 与 `oi_transceiver`（M2 · G-OI2）单独承载 —— 本卡只报预算 + 版图签核。
"""
from __future__ import annotations

CASE_ID = ("OI-M0/M1/M2 · 光联接模块（M0 双通道基线 + M1 800G 频域/时域 + "
           "M2 1.6T·LPO·G-OI2 真 GDS）")

_CACHE: dict = {}

CHANNELS_NM = [1550.0, 1551.6]
N_LANES = 2


def _m1_block() -> dict:
    """M1（800G）现算块：频域（EO S21）/ 时域（色散·眼·BER）/ 驱动-TIA / 梳齿规避规划。

    🔴 全部由 `lda_l2.oi_m1` **确定性现算**（闭式 + IFFT 时域 + 几何搜索），不读缓存文件、
    不跑 FDTD/P&R；数字与 `run_oi_m1_smoke.py` 的门禁断言同源。
    """
    from lda_l2 import oi_m1 as M1

    points = M1.m1_budget_all_points(seed=0)
    plan = M1.plan_lwdm_channels()
    bp = plan["best"] or {}
    link8 = M1.build_transceiver_m1()
    rep8 = M1.transceiver_m1_budget(link8, M1.m1_channels(8))

    # M0 默认环参数（m=170 / gap=0.30）下的 8 通道隔离 —— 梳齿混叠崩溃的对照证据
    from lda_l2.oi_module import build_transceiver_m0, transceiver_m0_budget
    ch8 = M1.m1_channels(8)
    link_m0d = build_transceiver_m0(n_lanes=8, channels_nm=ch8, gap=0.30, m=170)
    m0_default_xt = min(
        pc["isolation_db"] for pc in transceiver_m0_budget(
            link_m0d, ch8, gap=0.30, m=170)["per_channel"])

    dt = M1.driver_tia_cosim()
    ils = [pc["il_db"] for pc in rep8["per_channel"]]
    # 设计裕量 = 假设 SNR − 「可达设计点中最坏的所需 SNR」（未含 EDC/DSP 的预算级口径）
    _req = [points[sp["key"]]["per_channel"][0]["required_snr_db"]
            for sp in M1.SPEC_POINTS
            if points[sp["key"]]["per_channel"][0]["required_snr_reachable"]]
    _worst_req = max(_req) if _req else None
    spec = []
    for sp in M1.SPEC_POINTS:
        pc = points[sp["key"]]["per_channel"][0]
        spec.append({
            "key": sp["key"], "band": sp["band"], "wl_nm": sp["wl_nm"],
            "reach_km": sp["reach_km"], "expect": sp["expect"],
            "q": round(points[sp["key"]]["worst_q"], 3),
            "ber": points[sp["key"]]["worst_ber_closed"],
            "disp_penalty_db": round(pc["disp_penalty_db"], 3),
            "sim_penalty_db": (round(pc["sim_penalty_db"], 3)
                               if pc["sim_penalty_db"] is not None else None),
            "required_snr_db": (round(pc["required_snr_db"], 3)
                                if pc["required_snr_db"] is not None else None),
            "required_snr_reachable": bool(pc["required_snr_reachable"]),
        })
    return {
        "stage_label": "M1 · 800G（8×100G PAM4）频域 / 时域预算",
        "n_lanes": int(rep8["n_lanes"]),
        "aggregate_gbps": rep8["aggregate_gbps"],
        "baud_gbd": rep8["baud_gbd"],
        "target_ber_kp4": M1.TARGET_BER_KP4,
        "snr_db": rep8["snr_db"],
        "worst_required_snr_db": (round(_worst_req, 3)
                                  if _worst_req is not None else None),
        "snr_margin_db": (round(rep8["snr_db"] - _worst_req, 3)
                          if _worst_req is not None else None),
        "f_3db_eo_ghz": round(rep8["per_channel"][0]["f_3db_eo_ghz"], 3),
        "worst_q": round(rep8["worst_q"], 3),
        "worst_ber": rep8["worst_ber_closed"],
        "il_min_db": round(min(ils), 3),
        "il_max_db": round(max(ils), 3),
        "worst_isolation_db": round(rep8["worst_isolation_db"], 2),
        "driver": {
            "rise_ui": round(dt["rise_10_90_ui"], 3),
            "tia_ghz": round(dt["f_tia_ghz"], 3),
            "tia_over_nyquist": round(dt["tia_over_nyquist"], 3),
            "t90_closed_ps": round(dt["t90_closed_form_s"] * 1e12, 3),
            "t90_rk4_ps": round(float(dt["t90_rk4_s"]) * 1e12, 3),
        },
        "ring_plan": {
            "m": int(bp.get("m", 0)),
            "R_um": bp.get("R_um"),
            "gap_um": bp.get("gap_um"),
            "min_fsr_nm": bp.get("min_fsr_nm"),
            "min_comb_detune_nm": bp.get("min_comb_detune_nm"),
            "min_xt_db": bp.get("min_xt_db"),
            "max_il_drop_db": bp.get("max_il_drop_db"),
            "max_fsr_at_rmin_nm": plan["max_fsr_at_rmin_nm"],
            "fsr_rule_rejects_span": bool(plan["fsr_rule_rejects_span"]),
            "m0_default_min_xt_db": round(m0_default_xt, 2),
            "n_solutions": int(plan["n_solutions"]),
        },
        "spec_points": spec,
        "m0_fixes": [
            {"title": "级联引擎星型网重复计数（M0 已修 · 本卡登记）",
             "detail": "≥3 端口星型网 all-pairs 全连边 ⇒ 同一信号多路径重复求和；改 hub 模型"},
            {"title": "`transceiver_m0_budget` 硬编码环区数 m=170",
             "detail": "与 build 的 m 脱钩 ⇒ 换 m 装配时闭式(A)与级联(B)静默分歧；已改为显式入参"},
            {"title": "B4（FSR）目标单位错（1.55 当 nm 传）",
             "detail": "`fsr_nm` 口径为 λ 用 nm / R 用 µm；目标恒为 0.0nm ⇒ 修为 9.118nm"},
            {"title": "KP4 FEC 门限口径差 100×（2.4e-2 应为 2.4e-4）",
             "detail": "IEEE 802.3bs/df Clause 91：KP4 = RS(544,514)，pre-FEC 门限 ≈ 2.4e-4"
                       "（Keysight / Vitex / Heather 三源独立一致）。误写 2.4e-2 会把「达门限"
                       "所需 SNR」低估约 5dB（20.92 → 26.56dB），使设计点显得远宽松于真实 ⇒ "
                       "已修并加 `C13 公开规格锚 + 探针 P6` 机器锁死。"},
        ],
        "honest_note_m1": (
            "🔴 M1 同为**设计预算层**（A 档闭式/行为级）：BER 是**光通道预算级**闭式估计"
            "（golden = 闭式 Q 函数），**不含** SerDes/DSP/FEC/均衡/CDR（与 `eic_behavioral`"
            " 的 EIC 电路级排除**显式分层**）；接受 SNR 为**设计输入假设**（非实测噪声预算），"
            "另给免假设的「达 KP4 门限所需 SNR」；环模型为 L0 add-drop 解析谱（无 FDTD 标定）；"
            "**不报 TOPS / TOPS-W / fJ/op**；verdict 恒 `DESIGN_BUDGET`。"),
    }


def _m2_block() -> dict:
    """M2（1.6T）现算块：FEC 双口径 / LPO 代价 / 带宽墙 / 3 设计点 / 接收噪声 / G-OI2 真 GDS。

    🔴 全部由 `lda_l2.oi_m2` + `lda_layout.oi_transceiver_pnr` **确定性现算**；关键标量与
    `run_oi_m2_smoke.py` / `run_oi_transceiver_pnr_smoke.py` 两道门禁的断言同源。
    """
    from lda_l2 import oi_m2 as M2

    pts = M2.m2_budget_all_points()
    plan = M2.plan_m2_rings()
    bp = plan["best"] or {}
    prof = M2.FEC_MODE_PROFILES
    noise = M2.tia_noise_snr_db()
    dt = M2.driver_tia_200g()

    def _z(v):
        return (round(v, 3) if v is not None else None)

    spec = []
    for sp in M2.SPEC_POINTS_M2:
        pb = pts[sp["key"]]
        spec.append({
            "key": sp["key"], "band": sp["band"], "wl_nm": sp["wl_nm"],
            "reach_km": sp["reach_km"], "process": pb["process"],
            "role": sp["role"], "expect": sp["expect"],
            "verdict_point": pb["verdict_point"],
            "limiting_cause": pb["limiting_cause"],
            "eo_f3db_ghz": round(pb["eo_f3db_ghz"], 3),
            "nyquist_ghz": round(pb["nyquist_ghz"], 3),
            "bandwidth_headroom_ghz": round(pb["bandwidth_headroom_ghz"], 3),
            "retimed_margin_db": _z(pb["retimed"]["margin_db"]),
            "lpo_margin_db": _z(pb["lpo"]["margin_db"]),
            "lpo_penalty_db": _z(pb["lpo_penalty_db"]),
            "required_snr_retimed_db": _z(pb["retimed"]["required_snr_db"]),
            "required_snr_lpo_db": _z(pb["lpo"]["required_snr_db"]),
        })

    # G-OI2 真 GDS 现算（0.3–0.5s；版图确定性 ⇒ 与门禁 sha 同源）
    try:
        from lda_layout import oi_transceiver_pnr as TX
        r = TX.build_oi_transceiver_pnr(n_lanes=int(M2.OI_M2_PROCESS["n_lanes"]))
        g_oi2 = {
            "n_devices": int(r["n_devices"]), "n_nets": int(r["n_nets"]),
            "gds_bytes": len(r["gds_bytes"]), "gds_elements": int(r["gds_elements"]),
            "drc_pass": bool(r["drc_pass"]),
            "lvs_verdict": r["lvs_verdict"],
            "lvs_n_violations": int(r["lvs_n_violations"]),
            "footprint_um2": round(r["footprint_um2"]),
            "ring_R_um": r["ring_anchor"]["R_um"],
            "fiber_off_chip": bool(r["fiber_off_chip"]),
            "layout_discipline_ok": bool(
                TX.layout_discipline_ok(r["link"], r["placement"],
                                        int(r["n_lanes"]))["ok"]),
        }
    except Exception as _e:                                    # noqa: BLE001
        g_oi2 = {"error": type(_e).__name__}

    return {
        "stage_label": ("M2 · 1.6T（8×200G PAM4）· LPO「模块内无 DSP」形态 + "
                        "G-OI2 收发器真 GDS"),
        "n_lanes": int(M2.OI_M2_PROCESS["n_lanes"]),
        "aggregate_gbps": M2.aggregate_gbps(),
        "net_per_lane_gbps": M2.NET_PER_LANE_GBPS,
        "baud_gbd": M2.PAM4_BAUD_200G_GBD,
        "nyquist_ghz": M2.NYQUIST_200G_GHZ,
        "channels_nm": M2.m2_channels(),
        "fec": {
            "concatenated": {
                "pre_fec_ber": prof["concatenated"]["pre_fec_ber"],
                "needs_module_dsp": bool(prof["concatenated"]["needs_module_dsp"]),
                "required_snr_ideal_db": round(
                    M2.required_snr_ideal_db("concatenated"), 3),
                "label": prof["concatenated"]["label"],
            },
            "rs_only": {
                "pre_fec_ber": prof["rs_only"]["pre_fec_ber"],
                "needs_module_dsp": bool(prof["rs_only"]["needs_module_dsp"]),
                "required_snr_ideal_db": round(M2.required_snr_ideal_db("rs_only"), 3),
                "label": prof["rs_only"]["label"],
            },
            "ber_ratio": round(prof["concatenated"]["pre_fec_ber"]
                               / prof["rs_only"]["pre_fec_ber"], 3),
            "lpo_inner_code_gain_db": round(M2.lpo_inner_code_gain_db(), 3),
            "form_map": {"retimed": M2.mode_for_form_factor("retimed"),
                         "lpo": M2.mode_for_form_factor("lpo")},
        },
        "eo_f3db_fast_ghz": round(M2.eo_f3db_ghz("fast"), 3),
        "eo_f3db_legacy_ghz": round(M2.eo_f3db_ghz("legacy"), 3),
        "bandwidth_headroom_fast_ghz": round(M2.bandwidth_headroom_ghz("fast"), 3),
        "bandwidth_headroom_legacy_ghz": round(M2.bandwidth_headroom_ghz("legacy"), 3),
        "snr_assumed_db": M2.OI_M2_PROCESS["snr_db"],
        "tia_noise_snr_db": round(noise["snr_db"], 3),
        "driver": {
            "rise_ui": round(dt["rise_10_90_ui"], 3),
            "tia_ghz": round(dt["f_tia_ghz"], 3),
            "tia_over_nyquist": round(dt["tia_over_nyquist"], 3),
            "t90_closed_ps": round(dt["t90_closed_form_s"] * 1e12, 3),
            "t90_rk4_ps": round(float(dt["t90_rk4_s"]) * 1e12, 3),
        },
        "ring_plan": {
            "m": int(bp.get("m", 0)),
            "R_um": bp.get("R_um"),
            "gap_um": bp.get("gap_um"),
            "min_xt_db": bp.get("min_xt_db"),
            "max_il_drop_db": bp.get("max_il_drop_db"),
            "n_solutions": int(plan["n_solutions"]),
            "max_fsr_at_rmin_nm": plan.get("max_fsr_at_rmin_nm"),
            "fsr_rule_rejects_span": bool(plan["fsr_rule_rejects_span"]),
        },
        "spec_points": spec,
        "g_oi2": g_oi2,
        "platform_fixes_m2": [
            {"title": "`NO_NAMED_ADD_DEVICE` 登记表漂移（LVS 几何门禁 ⑲ 红）",
             "detail": "M0 的 `oi_module.py` 已具名构造 `MziModulator`/`Photodetector` ⇒ "
                       "登记表里的 6 类实际只剩 4 类；扫描 vs 登记失配 ⇒ 已同步（门禁回归 0 FAIL）"},
            {"title": "布局纪律三条**隐含前提**此前无人机器化（吃狗粮最大收获）",
             "detail": "「源 x 次序 ⟂ 目标 y 次序（反序）+ 目标 x 全同」的无交叉证明需三条前提"
                       "（目标 x 全同且 > 源 x 上界 · 目标 y 次序与源次序相反 · 目标 y 与源 y 同侧）。"
                       "首版把 MMIC x / detector x / detector y0 写成常量 ⇒ n=8 全绿、n=12 分别报 "
                       "5/3/10 处 `short_cross`。已改为**派生式**并加 `layout_discipline_ok` 常驻判据"},
            {"title": "诚实口径升级：LPO 不是免责声明而是**设计约束**",
             "detail": "级联 FEC 的内码在模块 DSP 内 ⇒ LPO（无 DSP）只能 RS-only ⇒ pre-FEC 门限"
                       "由 4.8e-3 收紧回 2.4e-4 ⇒ 所需 SNR 上升 2.744 dB（内码增益），"
                       "实测 LPO 代价 3.169 dB（= 内码增益 + ISI 口径差 0.425）"},
            {"title": "🔴 环区数常量漂移：`ring_m` 抄成 M1 的 C-band 解（版图 ⟷ 预算不同参）",
             "detail": "`oi_m2.OI_M2_PROCESS['ring_m']` 与 `oi_transceiver_pnr.RX_RING_M` 均曾写成 "
                       "**129**（M1 在 C-band 栅上的解；注释却称「M1/M2 规划给出」）。M2 的 "
                       "O-band 栅（1311 nm 起 / 4.5 nm）搜索解实为 **268**（R 13.31 µm vs 6.41 µm）"
                       "⇒ 版图签核的环 ≠ 链路预算的环，而**原有全部判据仍全绿**。已对齐为 268，"
                       "并补 M1 同款互锁判据 C13c（搜索解 ⟷ 常量）+ 新增跨模块 C15c"
                       "（builder ⟷ 规划解）+ 探针 P8/P9 锁死"},
        ],
        "honest_note_m2": (
            "🔴 M2 仍属**设计预算层**：FEC 门限口径四源独立一致（802.3dj 级联 4.8e-3 / RS-only "
            "2.4e-4）但**非**本平台实测；LPO 代价为**闭式 Q 函数**推算（golden = 闭式），"
            "BER 为**光通道预算级**（与 `eic_behavioral` 的 EIC 电路级**显式分层**）；"
            "接收噪声 SNR 为**乐观上界**（只含热+散粒+TIA 输入参考，不含 RIN/反射/串扰/老化）"
            "⇒ **不得**当灵敏度规格宣称，其价值在「噪声是否瓶颈」的判定；"
            "G-OI2 版图为**设计期签核**（非流片、非实测；层规为公开工艺近似，非 Foundry PDK）；"
            "MMIC 宽多模区**未建模自成像长度** L_π∝W²/λ；**不报 TOPS / TOPS-W / fJ/op / pJ/bit**；"
            "verdict 恒 `DESIGN_BUDGET`。"),
    }


def case_card(use_cache: bool = True, channels_nm=None, n_lanes=None) -> dict:
    """组装 M0 案例卡（确定性现算 + 模块级缓存）。

    channels_nm / n_lanes 可调（设计点），默认 2 通道 LAN-WDM 1.6nm 间隔。
    """
    if channels_nm is None:
        channels_nm = list(CHANNELS_NM)
    if n_lanes is None:
        n_lanes = N_LANES
    key = (tuple(channels_nm), int(n_lanes))
    if use_cache and key in _CACHE:
        return _CACHE[key]

    from lda_l2.oi_module import (
        build_transceiver_m0, transceiver_m0_budget,
    )

    link = build_transceiver_m0(n_lanes=n_lanes, channels_nm=channels_nm)
    rep = transceiver_m0_budget(link, channels_nm)
    per = rep["per_channel"]

    channels = [{
        "lane": pc["lane"],
        "channel_nm": pc["channel_nm"],
        "R_um": round(pc["R_um"], 4),
        "il_closedform_db": round(pc["il_a_db"], 3),
        "il_cascade_db": round(pc["il_b_db"], 3),
        "il_ab_diff_db": round(pc["il_ab_diff_db"], 4),
        "isolation_db": (round(pc["isolation_db"], 2)
                         if pc["isolation_db"] != float("inf") else None),
    } for pc in per]
    min_iso = min((c["isolation_db"] for c in channels if c["isolation_db"] is not None),
                  default=None)
    max_il = max((c["il_cascade_db"] for c in channels), default=None)

    card = {
        "endpoint": "/api/oi_demo",
        "case_id": CASE_ID,
        "claim": ("用 LDA 自家光链路设计验证链（lda_chain + lda_l2.oi_m1 + lda_l2.oi_m2 + "
                  "lda_layout.oi_transceiver_pnr）可把一款 WDM 收发器从装配一路推进到"
                  "**1.6T（8×200G PAM4）**：规模翻倍、补上 **LPO「模块内无 DSP」形态**"
                  "（把免责声明变成设计约束：丢掉级联内码 ⇒ 所需 SNR 上升 2.744dB）与"
                  "**G-OI2 收发器专用真 GDS 版图**（Tx 调制器阵列 + MMIC 合波 + GC 出片 / "
                  "GC 入片 + 环解波 + 探测器阵列，单次主权 DRC/LVS 双闸签核）；"
                  "且吃狗粮过程**抓出并修复了 4 处平台级缺陷**（星型网级联重复计数 · 环区数硬编码 · "
                  "FSR 目标单位错 · KP4 门限口径差 100×）**+ M2 再抓 3 处**（LVS 登记表漂移 · "
                  "布局纪律三条隐含前提未机器化 · 形态↔FEC 映射缺失），并**补齐了「梳齿规避信道规划」"
                  "与「收发器真 GDS builder」两项平台此前不具备的能力**"),
        "identity": {
            "topology": "Tx：MZI 调制器（cos² 传递）× N 通道；Rx：微环 add-drop 滤波器"
                        "级联下路 + 双 GratingCoupler 耦合 + 光纤 span",
            "method": "两种方法独立交叉验证——(A) 闭式链路预算（含前置环 thru 总线链）"
                      "；(B) lda_chain 级联引擎（信号流图精确信道波长评估）",
            "method_m1": "M1 在功率预算之上补**频域**（级联 EO S21：调制器 RC+渡越 × 探测器"
                         "τ=RC × TIA 单极点）与**时域**（PAM4 符号间隔抽头 → 三眼 / Q / BER；"
                         "高斯色散展宽闭式 ⟷ 时域仿真对拍）两维",
            "method_m2": "M2 再补**规模 × 形态 × 物理落地**三维：(规模) 8×200G PAM4 = 1.6T、"
                         "奈奎斯特 26.56→53.13GHz；(形态) LPO 无模块 DSP ⇒ 形态↔FEC 映射"
                         "（retimed→级联 / lpo→RS-only）+ 逐形态裕量与 LPO 代价；(物理落地) "
                         "收发器专用真 GDS + DRC/LVS 双闸 + 「源 x 次序 ⟂ 目标 y 次序（反序）」"
                         "L 型走线的**结构性零 cross_short**（三条前提机器化）",
            "anchor_B19": "无源无增益不等式 |T|≤1（所有 transfer 幅值 ≤1），M0/M1/M2 全部满足",
            "honest_layer": "M0/M1/M2 均属设计预算层（L0 解析器件模型 + A 档闭式/行为级）；"
                            "真实版图 GDS 由 D4 域 photonic_interconnect 与 M2 新增的 "
                            "oi_transceiver（G-OI2 收发器拓扑）承载",
        },
        "requested": {
            "n_lanes": n_lanes,
            "channels_nm": channels_nm,
            "v_pi_v": rep.get("v_pi_v"),
            "gc_coupling": rep.get("gc_coupling"),
            "fiber_span_db": rep.get("fiber_span_db"),
        },
        "channels": channels,
        "m1": _m1_block(),
        "m2": _m2_block(),
        "b19_passivity": rep["b19_passivity"],
        "min_isolation_db": min_iso,
        "max_il_db": max_il,
        "design_notes": rep.get("design_notes", []),
        "milestones": [
            {"id": "M0-1", "label": "平台底座就位",
             "detail": "P1 光链路征程 M1–M4（WDM link 框架 / 自动布线+损耗+GDS / Agent 元编排"
                       " / L1 原语 / B19 无源无增益不等式锚）；lda_chain 光链路设计验证链"},
            {"id": "M0-2", "label": "M0 基线组装",
             "detail": "2 通道 WDM 收发器（Tx MZI×2 + Rx 微环 add-drop×2 + GC×2 + 光纤 span）"
                       "用 lda_chain 拼装 IR，闭式(A)与级联(B)双法预算"},
            {"id": "M0-3", "label": "吃狗粮抓出真平台 bug 并修复",
             "detail": "级联引擎对 ≥3 端口星型网用 all-pairs 全连边 ⇒ 同一信号多路径重复求和"
                       "（GC 耦合被翻倍 2×~4×）——双通道 Rx 星形合波首跑即暴露（ch0 级联 IL="
                       "3.01dB / ch1=0.07dB vs 闭式 7.02dB）。改 hub 模型修复，2 端口网语义不变，"
                       "重跑 4 道 P1 link 引擎门禁零回归"},
            {"id": "M0-4", "label": "门禁 + 案例卡 + 前端（M0 回合）",
             "detail": "run_oi_m0_smoke（C7 引擎回归 + C1–C6 基线 + P1/P2/P3a/P3b 突变探针）"
                       "全 PASS；本卡 + 前端面板 + D4 photonic_interconnect 真 GDS 域接入"},
            {"id": "M1-1", "label": "频域：级联 EO S21 与 −3 dB 带宽",
             "detail": "调制器（RC 闭式 + 渡越限制）× 探测器（τ=RC，复用 B33 口径）× TIA"
                       "（单极点，复用 eic_behavioral）级联 ⇒ 链路 f_3dB 用几何二分严格求"
                       "（回代 |H|=1/√2 校验）"},
            {"id": "M1-2", "label": "时域：PAM4 眼 / Q / 链路预算级 BER",
             "detail": "符号间隔冲激响应抽头 → 三眼 Q；golden = 闭式 Q 函数 0.375·erfc(Q/√2)；"
                       "另给**免 SNR 假设**的「达 KP4 门限所需 SNR」（仿真二分 ⟷ 闭式解析对拍）"},
            {"id": "M1-3", "label": "光纤色散 + 驱动-TIA 协同",
             "detail": "β₂ 相位算子 + 高斯展宽闭式 σ₁²=σ₀²+(β₂L)²/(4σ₀²)（与 IFFT 时域仿真"
                       "方法学独立对拍）；驱动阶跃闭式 ⟷ RK4 两法对照 + TIA 带宽余量"},
            {"id": "M1-4", "label": "吃狗粮：信道规划能力补齐 + 4 处平台缺陷修复",
             "detail": "8 通道在 M0 默认环参数下隔离崩溃（−0.85dB）⇒ 定位出「FSR>跨度」旧判据"
                       "充分非必要，新增**梳齿规避信道规划**（m 搜索 + system_metrics 实证）"
                       "⇒ m=129/gap=0.55 隔离 39.5dB；顺带修 4 处平台缺陷（星型网级联重复计数 · "
                       "环区数硬编码 · FSR 目标单位错 · KP4 门限口径差 100×）+ 2 项历史欠账"
                       "（CI 覆盖登记 · 超时预算基线 5 行）"},
            {"id": "M2-1", "label": "规模：8×200G PAM4 = 1.6T（奈奎斯特 53.125GHz）",
             "detail": "每通道 200G = 106.25 GBd PAM4（线速率 212.5 Gb/s）；8 通道聚合净 1.6 Tb/s。"
                       "🔴 FEC 口径**必须换**：200G/lane 用 802.3dj **级联 FEC**（外 KP4 ⊗ 内 "
                       "Hamming/BCH(128,120) + 卷积交织）⇒ pre-FEC 门限 4.8e-3（非 100G/lane 的 2.4e-4）"},
            {"id": "M2-2", "label": "形态：LPO「模块内无 DSP」是为**设计约束**",
             "detail": "级联内码在模块 DSP 内实现 ⇒ LPO 拿不到 ⇒ 只能 RS-only ⇒ 门限由 4.8e-3 收紧回 "
                       "2.4e-4 ⇒ 所需 SNR 上升 **2.744 dB**（内码增益）；实测 LPO 裕量缩水 "
                       "**3.169 dB**（= 内码增益 + ISI 口径差 0.425）。形态↔FEC 映射由 "
                       "`mode_for_form_factor` 单一真源 + 门禁 C6 锁死"},
            {"id": "M2-3", "label": "物理落地：G-OI2 收发器专用真 GDS builder",
             "detail": "新建 `lda_layout/oi_transceiver_pnr.py`：Tx N 个 MZI 调制器阶梯阵列 → MMIC "
                       "N×1 合波 → GC 出片；Rx GC 入片 → N 个环 add-drop 级联 → N 个探测器阵列；"
                       "fiber span **片外不落版图**；单 LinkModel + 单次主权 DRC/LVS ⇒ 8×200G 为 "
                       "27 器件 / 25 网 / 158 GDS 元素 / 17434 B，DRC 全绿 + LVS ACCEPT(0 违规)"},
            {"id": "M2-4", "label": "吃狗粮：布局纪律三条隐含前提机器化 + 3 处平台修复",
             "detail": "「源 x 次序 ⟂ 目标 y 次序（**反序**）+ 目标 x 全同」的无交叉证明需三条**隐含**"
                       "前提——首版把三个坐标写成常量 ⇒ n=8 全绿、n=12 分别报 5/3/10 处 `short_cross`"
                       "（逐规模实测才暴露）。已改**派生式** + 新增 `layout_discipline_ok` 常驻判据"
                       "（两条独立通道：builder 标量 ⟂ 读 port_anchor 反推）；另修 LVS 登记表漂移"},
        ],
        "findings": [
            {"title": "闭式与级联两种方法预算逐位一致",
             "detail": "双通道 IL 闭式≡级联差 <0.0001dB——证明装配接线正确，不是两套独立实现"},
            {"title": "吃狗粮抓出真平台 bug（星型网级联重复计数）",
             "detail": "级联引擎 internal_map 对星型网 all-pairs 全连边 ⇒ 多路径求和翻倍；"
                       "这是客户用前我们自己先跑才暴露的能力短板，已 root-cause 并 hub 模型修复"},
            {"title": "🔴 8 通道暴露架构级短板：环梳齿混叠使隔离崩溃",
             "detail": "M0 默认环区数 m=170（FSR≈9.12nm）< 信道跨度 31.5nm ⇒ 第 i±2 环的梳齿"
                       "落在 λᵢ 偏 **0.118nm** 处 ⇒ 实测最坏隔离 **−0.85dB**（M0 只测 2 通道时"
                       "完全未暴露）"},
            {"title": "🔴 平台旧判据「FSR > 信道跨度」充分非必要 ⇒ 容量被严重低估",
             "detail": "真正必要条件是「任一环梳齿不得落在其它信道线宽内」。按旧判据在 LDA DRC"
                       "（R≥5µm）下 8×4.5nm 直接判死；改用**梳齿规避**选 m=129（梳齿偏移 1.24nm）"
                       "⇒ 最坏隔离 **39.5dB**、drop IL 7.18–7.55dB（且更均匀）。已补 `plan_lwdm_channels`"},
            {"title": "C 波段 10km 在无 EDC 预算下不可行（两法同向结论）",
             "detail": "闭式色散代价 12.30dB；时域侧「达 KP4 门限所需 SNR」在 60dB 内**不可达**"
                       "（眼被 ISI 闭合）⇒ 设计结论：长距须改 O-band（现网 FR8/LR8 正是 O 波段）"
                       "或加 EDC/DSP（本模块不含）"},
            {"title": "🔴 设计裕量只有约 1.4dB（KP4 门限口径修正后才看见）",
             "detail": "修正 KP4 pre-FEC 门限 2.4e-2→2.4e-4 后，「达门限所需 SNR」由 20.92dB 升到"
                       "**26.56dB**，而设计假设 SNR 仅 28dB ⇒ 裕量 ≈ **1.44dB**（原口径下虚高到"
                       "~7dB）。这正是「外部标准必须取对」的价值：口径错一处，整条链路的余量判断"
                       "就反了；已由 C13 规格锚 + 探针 P6 锁死。"},
            {"title": "基线 IL≈7dB 是结构预算，可压缩",
             "detail": "GC -3dB×2 + 光纤 span + 环总线 thru 累积；M1 通过梳齿规避（更均匀 7.2–7.6dB）"
                       "改善，进一步压缩须低损耗 GC / 短总线"},
            {"title": "🔴 M2 口径陷阱：200G/lane 的 FEC **不是** 100G/lane 的 FEC",
             "detail": "802.3dj 在 200G/lane 用**级联** FEC ⇒ pre-FEC 门限 4.8e-3，比 RS-only 的 "
                       "2.4e-4 宽 **20×**。若沿用 M1 门限 ⇒ 所需 SNR 被虚高一档；若把级联门限误用于 "
                       "LPO（无 DSP 拿不到内码）⇒ 裕量被虚高 2.744dB。已由**规格锚 A1–A5** "
                       "（窗口判据 + 同源自洽 + 20× 门限比反向判据）机器锁死"},
            {"title": "🔴 M2 吃狗粮最大收获：布局纪律的三条前提是**隐含的**",
             "detail": "「反序 ⇒ 无交叉」只在三条前提同时成立时才是可证充分条件（目标 x 全同且 > 源 x "
                       "上界 · 目标 y 次序与源 y 次序相反 · 目标 y 与源 y 线同侧）。首版把 MMIC x / "
                       "detector x / detector y0 写成常量 ⇒ n=8（默认档）全绿，**n=12 才崩**（5/3/10 处 "
                       "`short_cross`）⇒ 已改派生式 + `layout_discipline_ok` + 逐规模门禁 T9；"
                       "V1/V2 反例保留作「反序」必要性的实证"},
            {"title": "G-OI2 版图「零 cross_short」是**结构性**的，不是调出来的",
             "detail": "Tx/Rx 均用 L 型走线：源 x 递增 ⟂ 目标 y 反向 ⇒ 竖直段 i 与水平段 j 的相交"
                       "充要条件退化为 i=j（自身），故**零交叉**。Tx 与 Rx 的 y 带再整体分离"
                       "（Tx y∈[−3.8,178.2] / Rx y∈[−379.3,−250.9]）⇒ 跨域也不交叉"},
            {"title": "LPO 代价实测 ≥ 内码增益（3.169 vs 2.744 dB）",
             "detail": "LPO 相对重定时的裕量缩水 = 理想内码增益 **+ ISI 口径差**（0.425dB，因 RS-only "
                       "门限更紧 ⇒ 可达 SNR 工作点不同）。恒等式 `pen ≡ gain + (ISI_LPO − ISI_retimed)` "
                       "已由门禁 C10d 逐位锁死（Δ<1e-9）"},
        ],
        "gaps": [
            {"id": "G-OI1", "closed": True,
             "title": "相邻信道隔离（M1 已闭合：−0.85dB → 39.5dB）",
             "detail": "靠**梳齿规避信道规划**（m=129 / gap=0.55µm，最小梳齿偏移 1.24nm）闭合；"
                       "新增平台能力 `oi_m1.plan_lwdm_channels`（搜索解与设计常量由门禁互锁）"},
            {"id": "G-OI2", "closed": True,
             "title": "M2 已闭合：收发器拓扑专用真 GDS builder",
             "detail": "新增 `lda_layout/oi_transceiver_pnr.py`（Tx 调制器阵列 + MMIC 合波 + GC 出片 / "
                       "GC 入片 + 环解波 + 探测器阵列，片外 fiber 不落版图）⇒ 单 LinkModel + 单次"
                       "主权 DRC/LVS 双闸 + D4 新域 `oi_transceiver`（下载端点 + 限幅 + 诚实注记）；"
                       "门禁 `run_oi_transceiver_pnr_smoke.py` 40 项（含逐规模 n∈{1,2,4,8,12} 双闸）"},
            {"id": "G-OI3", "closed": True,
             "title": "级电光行为模型（M1 已闭合四项）",
             "detail": "EO S21 带宽（G-OI3-a）· 眼图/BER（G-OI3-b，光链路预算级 + 与 EIC 电路级"
                       "显式分层）· 驱动-TIA 协同（G-OI3-c，复用 eic_behavioral）· 光纤色散"
                       "（G-OI3-d）四子项全部落地，见 `lda_l2/oi_m1.py`"},
            {"id": "G-OI4", "closed": False,
             "title": "电路级模型 · 无 PDK · 不报 TOPS",
             "detail": "继承主权红线：无 foundry 数据 ⇒ 无能效宣称资格；规模与能效外推属 T2 锁死区"},
            {"id": "G-OI5", "closed": False,
             "title": "M2b 预留：多通道均衡 · 热调/串扰 · 良率 · 封装容差",
             "detail": "多通道均衡（IL/倾斜/眼高平坦化）· 热调（Pπ 预算进链路）· 热串扰 Γ 矩阵"
                       "（版图绑定）· 光子工艺偏差 → 良率 MC · 封装容差（对准 + 温度）。"
                       "本轮按用户裁定的「核心四件」范围**后置为 M2b**，不在 M2 判据内（诚实登记，"
                       "不冒充已完成）"},
        ],
        "gaps_closed": 3,
        "gaps_total": 5,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "链路预算设计行为验证口径（确定性现算 · 非流片实测 · 非实测签核）",
        "honest_note": ("🔴 本卡为只读案例：数字由确定性现算（闭式 + lda_chain 级联引擎 + "
                        "oi_m1/oi_m2 时域与预算 + 几何搜索 + 收发器真 GDS，零重计算 · 免登录 · "
                        "不跑 P&R/FDTD）；M0/M1/M2 均属**设计预算层**（L0 解析器件模型 / A 档闭式"
                        "行为级），真实版图 GDS 由 D4 域 photonic_interconnect 与 oi_transceiver 承载；"
                        "M1/M2 的 BER 是**光通道预算级**闭式估计（不含 SerDes/DSP/FEC/均衡/CDR），"
                        "接受 SNR 为**设计输入假设**（M2 另给免假设的 TIA 噪声闭式**上界**做交叉核对，"
                        "不含 RIN/反射/串扰/老化 ⇒ 不得当灵敏度规格）；M2 的 G-OI2 版图为"
                        "**设计期签核**（非流片、非实测；非 Foundry PDK）；"
                        "不报 TOPS/TOPS-W/fJ/op/pJ/bit；判决由死标量给出，LLM 不进判决路径。"),
    }
    if use_cache:
        _CACHE[key] = card
    return card


def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检：卡结构完备 + 判决诚实 + 关键数字与模块自检同源（M0 + M1）。

    🔴 「卡内数字 ≡ 模块现算」逐位同源：M1 块的关键标量回读 `lda_l2.oi_m1` 现算比对，
    防「案例卡写死一份、模块改了卡不动」的静默失真（血案同族）。
    """
    c = case_card(use_cache=False)
    need = ["case_id", "claim", "identity", "requested", "channels", "m1", "m2",
            "b19_passivity", "milestones", "findings", "gaps", "verdict", "honest_note"]
    if any(k not in c for k in need):
        return False
    if c["verdict"] != "DESIGN_BUDGET":
        return False
    # 🔴 只守「能力宣称面」：`honest_note` / `honest_note_m1` / `honest_note_m2` 是否定语境的
    #    **正确自我否定**（「不报 TOPS/…」）⇒ 不参与判据（否则正确否定被误判违规 —— E12/E13/E17 血案同族）。
    _surf = {k: v for k, v in c["m1"].items() if k != "honest_note_m1"}
    _surf2 = {k: v for k, v in c["m2"].items() if k != "honest_note_m2"}
    blob = (repr(c["claim"]) + repr(c["identity"]) + repr(c["requested"]) + repr(_surf)
            + repr(_surf2))
    for _tok in ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "pJ/bit", "W/op"):
        if _tok in blob:
            return False
    if c["gaps_total"] != len(c["gaps"]):
        return False
    if c["gaps_closed"] != sum(1 for g in c["gaps"] if g["closed"]):
        return False
    # 闭式≡级联：所有通道差 ≤0.05dB
    ok_ab = all(ch["il_ab_diff_db"] <= 0.05 for ch in c["channels"])
    ok_b19 = bool(c["b19_passivity"])
    ok_ch = len(c["channels"]) == c["requested"]["n_lanes"]

    # ── M1 自洽 + 与模块现算逐位同源 ──
    from lda_l2 import oi_m1 as M1
    m1 = c["m1"]
    plan = M1.plan_lwdm_channels()
    bp = plan["best"] or {}
    ok_plan = (m1["ring_plan"]["m"] == M1.OI_M1_PROCESS["ring_m"]
               and abs(m1["ring_plan"]["gap_um"] - M1.OI_M1_PROCESS["ring_gap_um"]) < 1e-9
               and m1["ring_plan"]["m"] == bp.get("m")
               and m1["ring_plan"]["min_xt_db"] == bp.get("min_xt_db"))
    ok_agg = (m1["aggregate_gbps"] == 800.0
              and m1["n_lanes"] == 8 and m1["n_lanes"] == plan["n_lanes"])
    ok_iso = m1["worst_isolation_db"] >= 15.0 and m1["ring_plan"]["m0_default_min_xt_db"] < 15.0
    ok_pts = ([s["key"] for s in m1["spec_points"]]
              == [s["key"] for s in M1.SPEC_POINTS])
    ok_exp = all((s["ber"] < M1.TARGET_BER_KP4) == (s["expect"] == "pass")
                 for s in m1["spec_points"])
    ok_ber = (m1["worst_ber"] < M1.TARGET_BER_KP4 and m1["il_min_db"] >= 3.0
              and m1["il_max_db"] <= 20.0)
    ok_fix = len(m1["m0_fixes"]) == 4 and "no_energy" in M1.OI_M1_DISCLOSURE
    # 设计裕量：卡内自洽（裕量 ≡ 假设SNR − 最坏可达所需SNR）∧ 物理不等式
    #   最坏所需 SNR ≥ 平坦 golden `ideal_required_snr_db()`（有 ISI/色散只会更差）
    _wr = m1["worst_required_snr_db"]
    ok_margin = (_wr is not None and m1["snr_margin_db"] is not None
                 and abs(m1["snr_margin_db"] - (m1["snr_db"] - _wr)) < 1e-6
                 and _wr >= M1.ideal_required_snr_db() - 1e-6
                 and 0.0 < m1["snr_margin_db"] < 6.0)
    good = (ok_ab and ok_b19 and ok_ch and ok_plan and ok_agg and ok_iso
            and ok_pts and ok_exp and ok_ber and ok_fix and ok_margin)

    # ── M2 自洽 + 与模块现算逐位同源（1.6T / FEC 双口径 / LPO / 带宽墙 / G-OI2）──
    from lda_l2 import oi_m2 as M2
    m2 = c["m2"]
    ok_m2_agg = (m2["aggregate_gbps"] == 1600.0 and m2["n_lanes"] == 8
                 and abs(m2["baud_gbd"] - M2.PAM4_BAUD_200G_GBD) < 1e-9
                 and abs(m2["nyquist_ghz"] - M2.NYQUIST_200G_GHZ) < 1e-9)
    # FEC 双口径：级联门限宽 20×；形态映射 lpo→rs_only / retimed→concatenated
    ok_m2_fec = (m2["fec"]["concatenated"]["pre_fec_ber"]
                 == M2.FEC_MODE_PROFILES["concatenated"]["pre_fec_ber"]
                 and m2["fec"]["rs_only"]["pre_fec_ber"]
                 == M2.FEC_MODE_PROFILES["rs_only"]["pre_fec_ber"]
                 and abs(m2["fec"]["ber_ratio"] - 20.0) < 1e-6
                 and m2["fec"]["form_map"]["lpo"] == "rs_only"
                 and m2["fec"]["form_map"]["retimed"] == "concatenated"
                 and m2["fec"]["rs_only"]["needs_module_dsp"] is False
                 and m2["fec"]["concatenated"]["needs_module_dsp"] is True
                 and abs(m2["fec"]["lpo_inner_code_gain_db"]
                         - M2.lpo_inner_code_gain_db()) < 1e-3)   # 卡内展示 round 到 3 位
    # 带宽墙反例：fast 有余量 ∧ legacy 不足（吃狗粮证据）
    ok_m2_bw = (m2["bandwidth_headroom_fast_ghz"] > 0
                and m2["bandwidth_headroom_legacy_ghz"] < 0
                and abs(m2["eo_f3db_fast_ghz"] - M2.eo_f3db_ghz("fast")) < 1e-3
                and abs(m2["eo_f3db_legacy_ghz"] - M2.eo_f3db_ghz("legacy")) < 1e-3)
    # 逐设计点：verdict ≡ 声明 expect（pass / disp_limited / bw_limited）
    ok_m2_pts = ([s["key"] for s in m2["spec_points"]]
                 == [s["key"] for s in M2.SPEC_POINTS_M2]
                 and all(s["verdict_point"] == s["expect"] for s in m2["spec_points"]))
    # LPO 代价 ≥ 理想内码增益（物理不等式；恒等式本身由门禁 C10d 逐位锁死）
    _lpo = [s for s in m2["spec_points"] if s["lpo_penalty_db"] is not None]
    ok_m2_lpo = bool(_lpo) and all(
        s["lpo_penalty_db"] >= m2["fec"]["lpo_inner_code_gain_db"] - 1e-9 for s in _lpo)
    # 接收噪声**上界** > 设计假设（⇒ 噪声非瓶颈）· 与模块现算逐位同源
    ok_m2_noise = (m2["tia_noise_snr_db"] > m2["snr_assumed_db"]
                   and abs(m2["tia_noise_snr_db"]
                           - M2.tia_noise_snr_db()["snr_db"]) < 1e-3)  # 展示 round 到 3 位
    # G-OI2 真 GDS：双闸 ACCEPT + 拓扑计数 + 片外 fiber + 布局纪律三前提
    _g = m2["g_oi2"]
    ok_m2_gds = ("error" not in _g and _g["drc_pass"]
                 and _g["lvs_verdict"] == "ACCEPT" and _g["lvs_n_violations"] == 0
                 and _g["n_devices"] == 3 * 8 + 3 and _g["n_nets"] == 3 * 8 + 1
                 and _g["fiber_off_chip"] and _g["layout_discipline_ok"]
                 and _g["gds_bytes"] > 0)
    good2 = (ok_m2_agg and ok_m2_fec and ok_m2_bw and ok_m2_pts and ok_m2_lpo
             and ok_m2_noise and ok_m2_gds)
    good = good and good2
    if verbose:
        print("[%s] OI-M0/M1/M2 case_card · 通道=%d · 闭式≡级联=%s · B19=%s"
              % ("PASS" if good else "FAIL", len(c["channels"]), ok_ab, ok_b19))
        print("      M1: 800G=%s · 隔离=%s(%.1fdB vs M0默认 %.2fdB) · 规划=%s · 设计点=%s · "
              "修复=%s · 裕量=%s(%.2fdB)"
              % (ok_agg, ok_iso, m1["worst_isolation_db"],
                 m1["ring_plan"]["m0_default_min_xt_db"], ok_plan, ok_exp, ok_fix,
                 ok_margin, m1["snr_margin_db"]))
        print("      M2: 1.6T=%s · FEC双口径=%s(级联%.1e/RS-only%.1e · 比%.0f×) · LPO代价=%s "
              "(%.3fdB ≥ 内码增益 %.3fdB) · 带宽墙=%s(fast %+.2f / legacy %+.2f GHz) · "
              "设计点=%s · 噪声上界=%s(%.2fdB > 假设 %.0fdB) · G-OI2=%s(%s件/%s网 · %s · 纪律%s)"
              % (ok_m2_agg, ok_m2_fec, m2["fec"]["concatenated"]["pre_fec_ber"],
                 m2["fec"]["rs_only"]["pre_fec_ber"], m2["fec"]["ber_ratio"],
                 ok_m2_lpo, min(s["lpo_penalty_db"] for s in _lpo) if _lpo else float("nan"),
                 m2["fec"]["lpo_inner_code_gain_db"], ok_m2_bw,
                 m2["bandwidth_headroom_fast_ghz"], m2["bandwidth_headroom_legacy_ghz"],
                 ok_m2_pts, ok_m2_noise, m2["tia_noise_snr_db"], m2["snr_assumed_db"],
                 ok_m2_gds, _g.get("n_devices"), _g.get("n_nets"),
                 _g.get("lvs_verdict"), _g.get("layout_discipline_ok")))
    return good


if __name__ == "__main__":
    print("OI-M0/M1/M2 case self-check:",
          "PASS" if run_selfchecks(verbose=True) else "FAIL")
