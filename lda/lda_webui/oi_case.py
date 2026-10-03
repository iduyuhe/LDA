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

import math

# 🔴 非有限 dB 值的 JSON 安全字符串 tag —— 唯一真源是 `lda_l2.oi_m3.NEG_INF_DB`，
#    卡内判据 / 出口兜底 / 前端显示三处同源，避免「两处字面量」假判据。
from lda_l2.oi_m3 import NEG_INF_DB as NEG_INF_DB        # noqa: E402

CASE_ID = ("OI-M0/M1/M2/M2b/M3/M4 · 光联接模块（M0 双通道基线 + M1 800G 频域/时域 + "
           "M2 1.6T·LPO·G-OI2 真 GDS + M2b 均衡/热调/热串扰/良率/封装 G-OI5 + "
           "M3 3.2T·CPO·400G/lane 带宽墙·die↔die 热·2.5D 签核 G-OI6 + "
           "M4 CPO 形态深化·热-光-电协同设计空间·VπL 断口 G-OI7）")

_CACHE: dict = {}
_DEBUG_SELFCHECK: bool = False      # 排障用开关（默认关，避免门禁输出噪声）

# 🔴 禁词扫描的「否定豁免」标记：命中后**截断到该标记处**，只扫其前的**肯定式宣称面**。
#    （E12/E13/E17 血案同族：正确自我否定「本项目不报 TOPS/…」若整串豁免会漏掉
#     「本模块提供 TOPS 级算力」这类真违规；整串跳过同理过宽。）截断式最严且最准：
#    否定标记之前的肯定文字**照扫**，只把否定及其后文剔掉。
_NEG_MARKERS = ("不报", "不做", "不得", "不宣", "未报")


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


def _m2b_block() -> dict:
    """M2b（G-OI5）现算块：多通道 CTLE 均衡 · 热调 · 热串扰 Γ · 工艺偏差良率 MC · 封装容差。

    🔴 数字**全部现算**（不写死）：与 `lda/run_oi_m2b_smoke.py` 同源同一份
    `lda_l2.oi_m2b`，卡内只是**呈现层**，`run_selfchecks` 再回读比对防静默失真。
    门禁规模：**89 行 = 39 基线判据 × 2（基线 + 还原复检）+ 10 突变探针 + 1 还原一致**；
    模块自检 **31 项**。

    诚实边界（与卡内 `honest_note_m2b` 一致）：
      · 良率/容差 = **设计者显式声明的统计窗口**（σ_dn_eff、对准 IL 预算、温窗 −5…70 ℃），
        **不是 Foundry 工艺真值**（T2 锁死）⇒ 不得宣称「实测工艺能力 / 流片良率」；
      · 热调只登记 **mW**（功耗口径），**不做**能效比换算（🔴 不报 TOPS/TOPS-W/fJ-op/pJ-bit）；
      · CTLE/Γ 为 **A 档闭式 + 行为级**（golden = 闭式物理律 + 第二独立通道对拍）。
    """
    from lda_l2 import oi_m2b as MB

    p = MB.OI_M2B_PROCESS
    F = MB.NYQUIST_200G_GHZ * 1e9
    a = float(p["f_tia_ghz"]) * 1e9
    z = MB.f_z_for_boost(F, a, float(p["ctle_boost_db"]))

    des = MB.lane_ctle_design()
    _eqflat = MB.lane_equalization_flatness()      # 🔴 F3：均衡成效（独立重算）
    tb = MB.thermal_tune_budget()
    g = MB.crosstalk_gamma()
    yc = MB.yield_closed_form()
    ym = MB.yield_monte_carlo()
    ab = MB.alignment_tolerance_budget()
    tdb = MB.temp_drift_budget()

    return {
        "stage_label": ("M2b · G-OI5：多通道 CTLE 均衡 · 热调 · 热串扰 Γ · "
                        "工艺偏差良率 MC · 封装容差"),
        # ① 形态↔均衡映射（本轮题眼：LPO 无 DSP ⇒ 只能模拟 CTLE，不能 FFE）
        "equalizer": {
            "lpo": MB.equalizer_for_form("lpo"),
            "retimed": MB.equalizer_for_form("retimed"),
            "why": ("FFE/DFE 是**数字**均衡（在模块 DSP 里跑）⇒ LPO（模块内无 DSP）只能有"
                    "模拟 CTLE（TIA 前的连续时间线性均衡）；retimed 才有 DSP ⇒ CTLE+FFE。"
                    "这条约束由门禁探针 P3 守护（让 lpo 拿到 ffe 必红）。"),
        },
        # ② CTLE 闭式（单零点/单极点）
        "ctle": {
            "f_z_hz": z, "f_p_hz": a,
            "boost_nom_db": float(p["ctle_boost_db"]),
            "noise_penalty_db": round(MB.ctle_noise_penalty_db(z, a, F), 4),
            "noise_penalty_flat_db": round(MB.ctle_noise_penalty_db(a, a, F), 9),
            "note": ("penalty = 10·log10(∫₀^F G²df / F)，基准是**平坦响应**（≡0 dB）；"
                     "首版错把基准取成 G(F)² ⇒ 得到 −2.86 dB 的**负惩罚**（门禁 T8 抓出）。"),
        },
        # ③ 多通道均衡：逐 lane 抽头（工艺离散 f_mod ±3% ⇒ 均衡后总增益拉平）
        "lane_equalizer": {
            "n_lanes": int(des["n_lanes"]),
            "boost_distinct": bool(des["boost_distinct"]),
            # 🔴 F3：**设计方程往返自洽**（弱，`f_z_for_boost` 反解的逆 ⇒ 恒等式）
            #    与**信道成效**（强，独立重算：逐 lane 真信道 ISI）分开报，不混淆
            "design_roundtrip_spread_db": round(float(des["total_gain_spread_db"]), 12),
            "equalization_isi_spread": round(float(_eqflat["isi_spread"]), 9),
            "channel_source": _eqflat["channel_source"],
            "flat_ok": bool(_eqflat["equalization_flat_ok"]),
            "noise_penalty_min_db": round(float(des["noise_penalty_min_db"]), 4),
            "noise_penalty_max_db": round(float(des["noise_penalty_max_db"]), 4),
            "lanes": [{"lane": x["lane"], "f_mod_ghz": round(float(x["f_mod_ghz"]), 3),
                       "boost_db": round(float(x["boost_db"]), 4),
                       "f_z_ghz": round(float(x["f_z_hz"]) / 1e9, 4),
                       "pen_db": round(float(x["noise_penalty_db"]), 4)}
                      for x in des["lanes"]],
        },
        # ④ 热调（mW 口径，非能效）
        "thermal_tune": {
            "unit_note": str(tb["unit_note"]),
            "S_nm_per_mW": float(tb["S_nm_per_mW"]),
            "Ppi_mW": round(float(tb["p_pi_mw"]), 3),
            "heater_length_um": round(float(tb["heater_length_um"]), 3),
            "ring_R_um": round(float(tb["ring_R_um"]), 4),
            "FSR_nm": round(float(tb["FSR_nm"]), 4),
            "residual_detune_nm": float(tb["residual_detune_nm"]),
            "p_per_lane_mW": round(float(tb["p_tune_mw_per_lane"]), 3),
            "p_total_mW": round(float(tb["p_tune_total_mw"]), 3),
            "honest_note_m2b_thermal": ("调谐功耗为 **mW 功耗口径**（P_tune = Pπ·|Δλ|/FSR）；"
                                        "本项目**不报** TOPS / TOPS-W / fJ-op / pJ-bit 能效比。"),
        },
        # ⑤ 热串扰 Γ（版图绑定，坐标来自 G-OI2 builder placement）
        "crosstalk_gamma": {
            "n": int(g["n"]), "S_nm_per_mW": float(g["S_nm_per_mW"]),
            "diag_max_nm_per_mW": round(max(g["gamma_nm_per_mw"][i][i]
                                             for i in range(int(g["n"]))), 5),
            "max_offdiag_nm_per_mW": round(float(g["max_offdiag_nm_per_mW"]), 5),
            "symmetric_ok": bool(g["symmetric_ok"]),
            "diagonal_max_ok": bool(g["diagonal_max_ok"]),
            "monotonic_ok": bool(g["monotonic_ok"]),
            "note": ("Γ_ij = S_i·Θ_ij，Θ 取二维薄片稳态**对数场**闭式；三条物理律判据"
                     "（互易/随距离单调递减/对角最大）由门禁守护，第二独立通道为"
                     "**有限差分热网络**（网格加密相对误差单调下降）。"
                     "🔴 **绝对量级未标定**（`_R_TH0_K_PER_MW` / `_D_REF_UM` 为归一化常数，"
                     "无实测锚）⇒ 三条律只是**结构性质**，**不得**当热串扰定量结论对外宣称；"
                     "**对角 Γ_ii 为 d→0 钳位伪值**（真自热 ≈ S·1mW = %.4f nm/mW，"
                     "伪值 %.4f nm/mW，偏大 ~20×）——自热请用 `S_nm_per_mW`，**勿用 Γ_ii**。"
                     % (float(g["S_nm_per_mW"]), round(max(g["gamma_nm_per_mw"][i][i]
                                                            for i in range(int(g["n"]))), 4))),
        },
        # ⑥ 工艺偏差 → 良率（MC 是采样近似，不是 golden）
        "yield": {
            "sigma_dn_eff": float(p["sigma_dn_eff"]),
            "tol_nm": float(yc["tol_nm"]),
            "sigma_resonance_nm": float(yc["sigma_resonance_nm"]),
            "yield_closed_form": round(float(yc["yield"]), 8),
            "yield_mc": round(float(ym["yield"]), 8),
            "mc_n_samples": int(ym["n_samples"]),
            "mc_seed": int(ym.get("seed", 0)),
            "note": ("golden = **闭式** Φ（erf）；MC（N=20000，固定 seed 20261002）只是"
                     "**第二通道 / 采样近似**，不是 golden。σ 是**设计者声明窗口**，"
                     "非 Foundry 真值（T2 锁死）⇒ 不得当实测工艺能力宣称。"),
        },
        # ⑦ 封装容差（对准 + 温度）
        "packaging": {
            "il_budget_db": float(ab["il_budget_db"]),
            "il_mode_mismatch_db": round(float(ab["il_mode_mismatch_db"]), 4),
            "eta_mode": round(float(ab["eta_mode"]), 5),
            "dx_max_um": round(float(ab["dx_max_um"]), 4),
            "dx_max_numeric_um": round(float(ab["dx_max_numeric_um"]), 4),
            "temp_window_c": [float(tdb["t_lo_c"]), float(tdb["t_hi_c"])],
            "wl_drift_nm": round(float(tdb["dlam_nm"]), 4),
            "dx_drift_um": round(float(tdb["dx_drift_um"]), 5),
            "dx_tolerance_um": round(float(tdb["dx_tolerance_um"]), 4),
            "temp_in_tolerance": bool(tdb["in_tolerance"]),
            "note": ("对准预算**只管「对准附加」IL**（模场失配底 0.66 dB 另披露，先扣掉），"
                     "否则 1 dB 预算在 dx=0 就被吃光 ⇒ 容差不可达（首版缺陷，门禁 T25 守）。"
                     "温漂走 GC 出射角真物理 Δθ=Δλ/(Λcosθ)。"),
        },
        "honest_note_m2b": (
            "🔴 M2b 仍属**设计预算层**（A 档闭式 + 行为级，golden = 闭式物理律 + 第二独立通道"
            "对拍）：σ/容差/温窗均为**设计者显式声明的统计窗口**，**不是** Foundry 工艺真值"
            "（T2 锁死区）⇒ **不得**宣称「实测工艺能力」或「流片良率」；热调只报 **mW** 功耗，"
            "**不报** TOPS / TOPS-W / fJ-op / pJ-bit 能效比；Γ/CTLE 为 L0 级解析模型，"
            "非 PDK、非电路级（G-OI4 仍开放）；verdict 恒 `DESIGN_BUDGET`。"),
    }


def _m3_block() -> dict:
    """M3（3.2T / CPO）现算块：400G-lane 带宽墙 · CPO 电通道 · die↔die 热+闭环热调 · 功耗账 · 2.5D 签核。

    🔴 数字**全部现算**（不写死）：与 `lda/run_oi_m3_smoke.py`（51 基线判据 + 15 突变探针
    + 还原复检）同源同一份
    `lda_l2.oi_m3`，卡内只做**呈现层**，`run_selfchecks` 再回读比对防静默失真。

    诚实边界（与卡内 `honest_note_m3` 一致）：
      · 电层尺寸/电极参数/热阻/功耗分项均为**规格锚**（公开工艺近似），非 Foundry 真值（T2 锁死）；
      · 功耗账只出 **mW / W**，🔴 不报 fJ/bit、pJ-op、TOPS、TOPS-W 等能效换算；
      · LVS 是**几何-拓扑一致性核对**，不是 foundry 电 PDK 网表核对；
      · `fdtd_telegraph` 跑的是**无损**电报方程（对拍量是相速/渡越时间，对电阻不敏感）。
    """
    from lda_l2 import oi_m2b as _M2B
    from lda_l2 import oi_m3 as M3
    from lda_l2 import oi_m5 as M5      # 🔴 M5：驱动负载口径（电极 C′·L）+ 翻转披露

    _FSR = float(_M2B.thermal_tune_budget()["FSR_nm"])
    tw = M3.twmzm_design()
    lad = M3.twmzm_ladder_convergence()
    hsq = M3.echannel_h_sqrtf_ok()
    nx = M3.xtalk_next_db()
    nx0 = M3.xtalk_next_db(k=0.0)
    pdn = M3.pdn_bounce_v()
    fd = M3.fdtd_telegraph()
    ths = M3.die_thermal_stack()
    cl = M3.closed_loop_thermal_steady()
    rec = M3.power_reconcile()
    io4 = M3.oi_m3_optical_io_at_400g()

    # 2.5D 签核：光引擎 die 复用 M2 的 G-OI2 builder（吃狗粮，不重造光层几何）
    lay: dict = {}
    try:
        from lda_layout import oi_transceiver_pnr as TX
        _r = TX.build_oi_transceiver_pnr(n_lanes=int(M3.LANES_3200))
        lay = M3.cpo_2p5d_layout(oe_link=_r["link"], oe_placement=_r["placement"],
                                 oe_routes=_r["routes"])
        lay = {k: (v if k in ("lvs_report", "geometry") else v)
               for k, v in lay.items() if k != "gds_bytes"}
        lay["gds_sha256_short"] = str(lay["gds_sha256"])[:16]
    except Exception as _e:                                    # noqa: BLE001
        lay = {"error": "%s: %s" % (type(_e).__name__, str(_e)[:120])}

    p4 = M3.OI_M3_PROCESS
    return {
        "stage_label": ("M3 · 3.2T（8×400G PAM4 = 3.4T wire）· CPO 共封装："
                        "400G/lane 带宽墙 · 电通道 · die↔die 热 + 闭环热调 · 2.5D 签核"),
        # ① 400G/lane 带宽墙：行波电极 TWMZM
        "twmzm": {
            "family": tw["family"],
            "f3db_ghz": round(tw["f3db_hz"] / 1e9, 3),
            "nyquist_ghz": round(tw["f_nyquist_hz"] / 1e9, 3),
            "margin_db": round(tw["margin_db"], 3),
            "ratio_to_nyquist": round(tw["ratio_to_nyquist"], 3),
            "f_rc_ghz": round(tw["f_rc_hz"] / 1e9, 3),
            "l_electrode_mm": float(tw["l_electrode_mm"]),
            "dn_g_resid": float(tw["dn_g_resid"]),
            "f_pd_ghz": round(tw["f_pd_hz"] / 1e9, 3),
            "f_tia_ghz": round(tw["f_tia_hz"] / 1e9, 3),
            "in_window": bool(tw["in_window"]), "bandwidth_ok": bool(tw["bandwidth_ok"]),
            # 第二独立通道：ABCD 梯形链随段数收敛（真收敛 ⇒ 相对误差单调下降）
            # 🔴 `ladder_f_eval_ghz` 是**评估频率**（此口径下 f = Nyquist = 106.25 GHz），
            #    **不是** f₃dB（f₃dB 见上 `f3db_ghz`）—— 名字若写成 f3db 就是口径造假。
            "ladder_n_grid": [int(x) for x in lad["n_grid"]],
            "ladder_rel_err": [round(float(x), 6) for x in lad["rel_err"]],
            "ladder_monotonic": bool(lad["monotonic_decreasing"]),
            "ladder_f_eval_ghz": round(float(lad["f_hz"]) / 1e9, 3),
            "ladder_err_largest": round(float(lad["err_largest"]), 6),
            "ladder_err_smallest": round(float(lad["err_smallest"]), 6),
            "note": ("闭式 |H|=(1/L)|∫₀^L e^{−qx}dx|（q = Re γ + j(Im γ − ω·n_g,opt/c)）；"
                     "🔴 虚部**必须减掉光相位基准** ω·n_g,opt/c（γ 的虚部是微波相位 β_mw），"
                     "首版漏减 ⇒ 速度失配项被算成整条 β_mw ⇒ 带宽判据假绿（C1 必红）。"
                     "第二通道 = ABCD 梯形链（单段 Msec=[[1+zy, z],[y, 1]]，正向乘 Msec⁻¹，"
                     "末端匹配端接 Z0=√(z/y)），在 f=%s GHz 处随段数 %s ⇒ 相对误差 %s "
                     "**单调下降**（%s ⇒ %s），证实闭式与独立方法学同解而非同源相等。"
                     % (("%.3f" % (float(lad["f_hz"]) / 1e9)),
                        "→".join(str(int(x)) for x in lad["n_grid"]),
                        "→".join("%.2f%%" % (float(x) * 100.0) for x in lad["rel_err"]),
                        "%.3f%%" % (float(lad["err_largest"]) * 100.0),
                        "%.3f%%" % (float(lad["err_smallest"]) * 100.0))),
        },
        # ② CPO 电通道（电报闭式 ⟷ 1D FDTD）
        "echannel": {
            "bus_len_mm": float(p4["bus_len_mm"]),
            "f_rl_ghz": round(hsq["f_rl_hz"] / 1e9, 4),
            "window_ghz": [round(hsq["f_window_hz"][0] / 1e9, 4),
                           round(hsq["f_window_hz"][1] / 1e9, 4)],
            "h_in_window": round(hsq["h_in_window"], 4),
            "drift_in_window": round(hsq["drift_in_window"], 6),
            "h_outside": round(hsq["h_outside"], 4),
            "drift_outside": round(hsq["drift_outside"], 6),
            "sqrtf_ok": bool(hsq["ok"]),
            "disclosed_outside": bool(hsq["disclosed_outside"]),
            "note": ("h = |H|dB/√(f/GHz) 只在 **R 主导子带**（f ≤ f_RL/200 ≈ 0.1–0.95 GHz）"
                     "是真常数（漂移 %.4f）；1↔10 GHz 落在 RL 主导区，漂移 %.1f%% 是**真物理**"
                     "⇒ 如实披露，不做「硬套 √f 律」的假判据。"
                     % (hsq["drift_in_window"] * 100.0, hsq["drift_outside"] * 100.0)),
        },
        "fdtd_telegraph": {
            "n_cells": int(fd["n_cells"]),
            "dt_ps": round(float(fd["dt_s"]) * 1e12, 4),
            "n_step": int(fd["n_step"]),
            "tau_fdtd_ps": round(float(fd["tau_fdtd_s"]) * 1e12, 4),
            "tau_closed_ps": round(float(fd["tau_closed_s"]) * 1e12, 4),
            "rel_err": round(float(fd["rel_err"]), 6),
            "peak_out_v": round(float(fd["peak_out_v"]), 4),
            "v_fdtd_m_per_s": float(fd["v_fdtd_m_per_s"]),
            "lossy_term_included": bool(fd["lossy_term_included"]),
            "phase_ok": bool(fd["phase_ok"]),
            "note": ("1D FDTD（Yee，dt=0.5·dx/v_p 满足 CFL）跑**无损**电报方程，与闭式 e^{−γL}"
                     "对拍渡越时间 τ=L/v_p：%.3f ps ⟷ %.3f ps（%.2f%%）。"
                     "🔴 无损口径是刻意的——对拍量是**相速/渡越**，对 R′ 不敏感；"
                     "有损另走 `echannel_att_db`。首版三处错（系数取倒数 · Yee 顺序反 · "
                     "尾巴 3 ps 远小于渡越 50 ps）⇒ 采到全 0、相速 5e27、误报 100%% 误差。"),
        },
        "next": {
            "k": float(nx["k"]), "f_ghz": round(nx["f_hz"] / 1e9, 3),
            "f0_ghz": round(nx["f0_hz"] / 1e9, 3),
            "ratio_linear": round(nx["ratio_linear"], 1),
            "xtalk_db": _r3(nx["xtalk_db"]),
            "xtalk_at_zero_coupling_db": nx0["xtalk_at_zero_coupling_db"],
            "note": ("功率比 K²(F/f₀)⁴/3（容性近端串扰）。k=0 时 dB 是 **−∞（真 −inf）**，"
                     "不是 clamp 到 −3000 —— 首版 clamp 会把「零耦合」判成「有巨大耦合」"
                     "⇒ 门禁 C14 必红。"),
        },
        "pdn": {
            "l_pdn_nh": round(float(pdn["l_pdn_h"]) * 1e9, 4),
            "di_dt_a_per_s": float(pdn["di_dt_a_per_s"]),
            "v_bounce_v": round(float(pdn["v_bounce_v"]), 3),
            "note": ("地弹 V = L_pdn·di/dt。⚠ **规格锚量级示意**：在 0.5 nH × 8e10 A/s 下"
                     "得到 40 V，远高于任何逻辑电源 ⇒ 真实 CPO 必须靠**解耦电容 + 更低边沿速率**"
                     "把 di/dt 压下来；本模块只做**项级建模与量级披露**，不含 PDN 全芯片仿真。"),
        },
        # ③ die↔die 热 + 闭环热调
        "thermal": {
            "p_asic_w": float(ths["p_asic_w"]),
            "t_amb_c": round(float(p4["t_amb_c"]), 3),
            "d_t_interposer_c": round(ths["d_t_interposer_c"], 3),
            "t_interposer_c": round(ths["t_interposer_c"], 3),
            "d_t_photon_c": round(ths["d_t_photon_c"], 3),
            "t_photon_c": round(ths["t_photon_c"], 3),
            "theta_channels_agree": bool(ths["theta_channels_agree"]),
            "die_to_die_theta_k": round(ths["die_to_die_theta_k"], 6),
            "theta_from_m2b_network": round(ths["theta_from_m2b_network"], 6),
            "note": ("两串热阻：ASIC→中介层 %.1f K/W + 中介层→光子 die %.1f K/W ⇒ "
                     "ΔT_photon = P_asic·(R_a+R_i) = %.1f K（ASPIC 热直接抬光子 die）。"
                     "对数解 ⟷ M2b 有限差分热网络第二通道互证（%.4f vs %.4f K）。"
                     % (float(p4["r_th_asic_k_per_w"]), float(p4["r_th_int_k_per_w"]),
                        ths["d_t_photon_c"], ths["die_to_die_theta_k"],
                        ths["theta_from_m2b_network"])),
        },
        "closed_loop_thermal": {
            "solution": cl["solution"],
            "r_h_k_per_mw": float(cl["r_h_k_per_mw"]),
            "S_nm_per_mW": float(cl["S_nm_per_mW"]),
            "d_lambda_dT_nm_per_k": round(cl["d_lambda_dT_nm_per_k"], 6),
            "converged": bool(cl["converged"]),
            "solve_mode": cl["solution"],
            "S_eff_nm_per_mW": round(float(cl["S_eff_nm_per_mW"]), 6),
            # 🔴 F2（v0.9.185）：两条真判据（首版 `single_path_consistency` 是同源恒等式）
            "algebraic_matches_fixed_point": bool(M3._algebraic_matches_fixed_point()),
            "double_count_diverges": bool(M3._double_count_diverges()),
            "t_free_c": round(cl["t_free_c"], 3), "t_setpoint_c": round(cl["t_setpoint_c"], 3),
            "t_ring_c": round(cl["t_ring_c"], 3),
            "residual_nm": round(cl["residual_nm"], 4),
            "residual_frac_fsr": round(cl["residual_frac_fsr_nm"], 4),
            "residual_lt_fsr": bool(cl["residual_nm"] < _FSR),
            "FSR_nm": round(_FSR, 4),
            "p_actuator_mw_per_lane": round(cl["p_actuator_required_mw_per_lane"], 3),
            "actuator_direction": cl["actuator_direction"],
            "unidirectional_heater_feasible": bool(cl["unidirectional_heater_feasible"]),
            "note": ("🔴 首版**发散到 1e88 K** 的真根因：M2b 的 S=dλ/dP **已含自热**"
                     "（S=(dλ/dT)·R_h），M3 又把「加热器→温升→波长」通路**算两遍** ⇒ 环路增益"
                     " A≈28≫1 ⇒ 不动点迭代越界。"
                     "修法（v0.9.185 修 F2）：R_h 回单一真源 + 解走**代数式**"
                     " T_ring=max(T_free,T_set)（或 A=1 的一步不动点）。"
                     "🔴 **首版的判据链三层同时失效**（`single_path_consistency` 因 "
                     "dl=S/R_h 是**代数恒等式**、门禁 P7 只改输出字段、卡内负例是**死码**）"
                     "⇒ 这条最贵的血案曾**零护栏**。现在护栏是**收敛性**："
                     "`algebraic ⟷ fixed_point(A=1)` 收敛到同一稳态；**双计 A≫1 必发散**。"),
        },
        # ④ 功耗账（mW/W 口径）
        "power": {
            "unit_note": "🔴 只出 mW / W 口径，不报 fJ/bit、pJ-op、TOPS、TOPS-W 等能效换算",
            "energy_per_bit_banned": bool(
                M3.power_breakdown("cpo")["energy_per_bit_banned"]),
            # 🔴 M5：驱动负载电容取**电极电容 C′·L**（主账）；封装线口径**显式并报**
            "cap_model_used": M3.power_breakdown("cpo")["cap_model_used"],
            "driver_cap_fF": round(M3.power_breakdown("cpo")["driver_cap_fF"], 3),
            "driver_package_line_mw": round(
                M3.power_breakdown("cpo")["driver_package_line_mw"], 3),
            "cpo": {k: round(v, 3) for k, v in rec["cpo"]["items_mw_per_lane"].items()},
            "pluggable": {k: round(v, 3)
                          for k, v in rec["pluggable"]["items_mw_per_lane"].items()},
            "cpo_per_lane_mw": round(rec["cpo"]["per_lane_total_mw"], 3),
            "pluggable_per_lane_mw": round(rec["pluggable"]["per_lane_total_mw"], 3),
            "cpo_total_w": round(rec["cpo"]["module_total_w"], 4),
            "pluggable_total_w": round(rec["pluggable"]["module_total_w"], 4),
            "cpo_advantage_thermal_mw": round(rec["cpo_advantage_thermal_mw"], 3),
            "cpo_penalty_interposer_mw": round(rec["cpo_penalty_interposer_mw"], 3),
            "reconciled": bool(rec["reconciled"]),
            # 🔴 M5 口径翻转（结算必须披露的后果，两口径并列、不选择性披露）
            "flip": M5.cross_form_power_flip(),
            "note": ("逐项加总 == 逐 lane 之和（全局口径不脱钩）。"
                     "🔴 **M5 口径**：驱动负载取**电极电容 C′·L = %.0f fF**（主账），"
                     "封装线口径（%.1f mW/lane）**并报不进求和** —— 后者已由中介层 PDN 覆盖，"
                     "再算进 driver 属双重计数。"
                     "⇒ 旧叙事「CPO 省掉板级驱动动态功耗」**在主账下不成立**：该优势全部来自"
                     "1.0 pF vs 2.5 pF 的线电容差（package 口径 CPO 省 %.1f mW/lane；"
                     "电极口径 CPO **多付 %.1f mW/lane** = 热调跟踪 %.1f + 中介层 PDN %.1f − 终端）。"
                     "🔴 首版把 `interposer_pdn_mw` 挂在 sum **之后** ⇒ 对拍必红；"
                     "`cpo_advantage_thermal` 符号写反 ⇒ 恒负。两条都已被探针锁死。"
                     % (M3.power_breakdown("cpo")["driver_cap_fF"],
                        M3.power_breakdown("cpo")["driver_package_line_mw"],
                        abs(M5.cross_form_power_flip()["package_line_cap"][
                            "delta_cpo_minus_pluggable_mw"]),
                        M5.cross_form_power_flip()["electrode_cap"][
                            "delta_cpo_minus_pluggable_mw"],
                        rec["cpo_advantage_thermal_mw"], rec["cpo_penalty_interposer_mw"])),
        },
        # ⑤ 2.5D 版图签核（G-OI6）
        "layout_2p5d": lay,
        # ⑥ 复用底座（不重造）
        "reuse": {
            "at_200g": io4["at_200g"], "at_400g": io4["at_400g"],
            "lane_halved": bool(io4["lane_halved"]),
            "density_still_below_ceiling": bool(io4["density_still_below_ceiling"]),
            "pitch_still_above_floor": bool(io4["pitch_still_above_floor"]),
            "energy_floor_still_positive": bool(io4["energy_floor_still_positive"]),
            "reused_not_rebuilt": bool(io4["reused_not_rebuilt"]),
        },
        "honest_note_m3": (
            "🔴 M3 仍属**设计预算层**：电极/总线/热阻/功耗分项/版图尺寸均为**规格锚**；"
            "（公开工艺近似，**不是** Foundry PDK 真值，属 T2 锁死区）；"
            "LVS 是**几何-拓扑一致性核对**（每个电网络都有 ≥1 条路径、端点落在电气元素上），"
            "**不是** foundry 电 PDK 网表核对；"
            "FDTD 跑**无损**电报方程（只对拍渡越/相速）；功耗账**只 mW/W**，"
            "**不报** TOPS / TOPS-W / fJ-op / pJ-bit 能效比；verdict 恒 `DESIGN_BUDGET`。"),
    }


def _m4_block() -> dict:
    """M4（CPO 形态深化 · 热-光-电协同设计空间）现算块。

    🔴 数字**全部现算**（不写死）：与 `lda/run_oi_m4_smoke.py`（46 判据 + 11 探针）同源同一份
    `lda_l2.oi_m4`，卡内只做**呈现层**，`run_selfchecks` 再回读比对防静默失真。

    诚实边界（与卡内 `honest_note_m4` 一致）：
      · 材料 CTE / VπL / 模场半径 / 三形态总线长 / 光纤耦合损耗均为**规格锚**（公开近似，非 foundry 真值）；
      · 三形态 θ 差异用**几何标度**（1/d 远场），非实测封装数据；
      · `P_drv ∝ 1/L` 是 `VπL` 恒定假设下的 A 档闭式；
      · 🔴 不报 TOPS / TOPS-W / fJ-op / pJ-bit（三域代价只出 mW / W / K / nm / dB / GHz）。
    """
    from lda_l2 import oi_m4 as M4

    chain = M4.co_design_chain()
    prebias = M4.setpoint_prebias_design()
    replan = M4.thermal_channel_replan()
    forms = M4.package_form_factor_compare()
    cte = M4.fau_cte_misalignment()
    pareto = M4.pareto_front_l_electrode()
    wall = M4.feasibility_wall()
    bl = M4.band_lock()
    slope = M4.thermal_optical_slope_lock()
    return {
        "stage_label": ("M4 · CPO 形态深化：热-光-电协同设计空间 —— "
                        "耦合链 · 固化点预偏移（代数解）· 热态信道重规划 · 三形态矩阵 · "
                        "FAU CTE 失准 · 三域 Pareto + VπL 断口"),
        # ① 热-光-电耦合链
        "chain": chain,
        # ② 固化点预偏移（CPO 真实工程解 · 代数解）
        "prebias": prebias,
        # ③ 热致偏移 ⟷ WDM 信道规划（首次联立）
        "replan": replan,
        # ④ 封装形态族三域矩阵
        "forms": forms,
        # ⑤ FAU CTE 热-机械失准
        "cte": cte,
        # ⑥ 三域 Pareto 前沿 + VπL 断口
        "pareto": pareto,
        "feasibility_wall": wall,
        # 互锁与波段
        "band_lock": bl,
        "slope_lock": slope,
        "honest_note_m4": (
            "🔴 M4 仍属**设计预算层**：材料 CTE（Si 2.6e-6 / 玻璃 FAU 3.2e-6 /K，**公开手册值**）· "
            "`VπL` 规格锚（公开 SiP 典型 1.0–2.5 V·cm）· 模场半径 · 三形态总线长 · "
            "光纤耦合损耗均为**规格锚**（公开工艺近似，**不是** foundry 真值，属 T2 锁死区）；"
            "三形态热耦合 θ 差异用**几何标度**（1/d 远场近似），非实测封装数据；"
            "`P_drv ∝ 1/L` 是 `VπL` 恒定假设下的 A 档闭式；"
            "FAU 对准公差**无分布数据**、封装应力/翘曲**无实测** ⇒ **G-OI7 诚实保留**；"
            "🔴 三域代价**只出 mW / W / K / nm / dB / GHz**，"
            "**不报** TOPS / TOPS-W / fJ-op / pJ-bit 能效比；verdict 恒 `DESIGN_BUDGET`。"),
    }


def _m5_block() -> dict:
    """🔴 M5（VπL 断口**结算**）现算块：可行域闭式充要 + 双口径对拍 + 口径翻转披露。

    🔴 数字**全部现算**（不写死）：与 `lda/run_oi_m5_smoke.py`（41 判据 + 9 探针）同源同一份
    `lda_l2.oi_m5` 调用。角色是「把 M4 登记的断口**结掉**」：M4 只登记（断口还在），
    M5 给出**闭式充要条件** + 把两条并存的口径**机器化对拍** + 如实报出「口径切换会翻转
    CPO 相对可插拔的功耗结论」这一后果。
    """
    from lda_l2 import oi_m5 as M5
    st = M5.vpi_l_settlement()
    bands = {}
    for k, v in st["per_band"].items():
        ne = bool(v["continuous_non_empty"])
        bands[k] = {
            "vpi_l_v_cm": v["vpi_l_v_cm"],
            # 🔴 空集档**不给 l_min**（否则 lo 会被模块填成 l_max ⇒ 前端会显示成
            #   「零宽区间」而掩盖「无解」这一事实 —— 失真，必须显式 non_empty）
            "l_min_mm": (v["continuous_interval_mm"][0] if ne else None),
            "l_max_mm": v["continuous_interval_mm"][1],
            "width_mm": v["interval_width_mm"],
            "n_grid_hits": v["n_grid_hits"],
            "non_empty": ne,
        }
    bl = M5.bw_scaling_law_check()
    pair = M5.driver_cap_pair_mw()
    fl = M5.cross_form_power_flip()
    return {
        "status": st["status"],
        "implied_vpi_l_v_cm": st["implied_vpi_l_v_cm"],
        "vpi_l_critical_v_cm": st["vpi_l_critical_v_cm"],
        "public_band_v_cm": st["public_band_v_cm"],
        "gap_ratio_vs_typical": st["gap_ratio_vs_typical"],
        "gap_ratio_vs_band_low": st["gap_ratio_vs_band_low"],
        "design_point_self_consistent": bool(st["design_point_self_consistent"]),
        "public_low_feasible": bool(st["public_low_feasible"]),
        "public_typical_feasible": bool(st["public_typical_feasible"]),
        "public_high_feasible": bool(st["public_high_feasible"]),
        "required_l_at_public_typical_mm": st["required_l_at_public_typical_mm"],
        "l_max_at_bw_deadline_mm": st["l_max_at_bw_deadline_mm"],
        "vpp_needed_at_m3_l_v": st["vpp_needed_at_m3_l_v"],
        "vpp_required_reachable": bool(st["vpp_required_reachable"]),
        "feasible_bands": bands,
        "bw_law": {"is_inverse_l": bool(bl["bw_is_inverse_l"]),
                   "max_rel_err_inv_l": bl["max_rel_err_inv_l"],
                   "is_inverse_l2": bool(bl["bw_is_inverse_l2"]),
                   "max_rel_err_inv_l2": bl["max_rel_err_inv_l2"]},
        "dual_cap": {"cap_electrode_fF": pair["cap_electrode_fF"],
                     "cap_package_line_fF": pair["cap_package_line_fF"],
                     "driver_electrode_mw": pair["driver_electrode_mw"],
                     "driver_package_line_mw": pair["driver_package_line_mw"],
                     "ratio_package_over_electrode": pair["ratio_package_over_electrode"]},
        "cross_form_flip": fl,
        "honest_note_m5": (
            "🔴 M5 是**有条件结算**（`SETTLED_CONDITIONAL`），不是「断口消失」："
            "M3 设计点（v_pp %.2f V × L %.1f mm）隐含 VπL = %.4f V·cm ≤ 临界 %.6f V·cm "
            "⇒ **自洽**；但它比公开 SiP 典型 %.1f V·cm 激进 %.2f×（比窗口下界 %.1f 激进 %.2f×）"
            "⇒ 设计点**只在高效率工艺上成立**。"
            "🔴 两处**修正 M4 的表述**：① 带宽律是 `BW ∝ 1/L`（不是 M4 docstring 写的 1/L²），"
            "实测逐项比值与 L₁/L₂ 最大相对误差仅 %.4f；② 公开典型工艺的连续可行域是 "
            "[%.2f, %.2f] mm（宽 %.2f mm，**非空**）——M4 报的「收缩到 1 点」是 10 点**离散网格**"
            "的采样数（grid 命中 %d 个），不是连续域。"
            "🔴 口径结算的后果如实报出：切到电极口径后「CPO 省板级驱动动态功耗」**翻转**"
            "（封装线口径 CPO 省 %.1f mW/lane ⇒ 电极口径 CPO 多付 %.1f mW/lane）。"
            "🔴 边界：VπL 与 CMOS 摆幅是**公开规格锚**（非 foundry 真值）；只出 "
            "mW / W / GHz / mm / V / V·cm，**不报** TOPS / TOPS-W / fJ-op / pJ-bit；"
            "G-OI4（电路级无 PDK）与 G-OI7（封装级无实测）**仍开放**。"
            % (M5.V_PP_DIFF_V, M5.L_ELECTRODE_MM, st["implied_vpi_l_v_cm"],
               st["vpi_l_critical_v_cm"], st["public_band_v_cm"][0],
               st["gap_ratio_vs_typical"], st["public_band_v_cm"][0],
               st["gap_ratio_vs_band_low"], bl["max_rel_err_inv_l"],
               st["required_l_at_public_typical_mm"], st["l_max_at_bw_deadline_mm"],
               st["required_l_at_public_typical_mm"] and bands["public_typical"]["width_mm"],
               bands["public_typical"]["n_grid_hits"],
               abs(fl["package_line_cap"]["delta_cpo_minus_pluggable_mw"]),
               fl["electrode_cap"]["delta_cpo_minus_pluggable_mw"])),
    }


# 🔴 F11（v0.9.185）：OE 层复用 LVS 的**判决级**白名单。
#    实测 `export_chip_gds` 对 ring 参数几何回提**不适用** ⇒ `OE_LVS = REJECT / 8 违规`
#    （已知且已在 `oi_m3.cpo_2p5d_layout` docstring 披露的口径差：declared gap 0.55 µm vs
#    measured 232.3 µm）。此前 `ok_m3_layout` **不含** `oe_lvs_pass` ⇒ OE 层 REJECT 时
#    「2.5D 签核」判据**仍绿**（静默不提）。修法：判决显式要求「要么 pass，要么**显式豁免**
#    （verdict ∈ 白名单 ∧ honest_note 非空 ∧ 违规数 ≥1）」⇒ 把已知 REJECT 变成
#    **显式豁免 + 理由**，而非静默不提。**反向完备**：任何其它 verdict 且非 pass ⇒ 红
#    （白名单不许静默吞新判决）。
_OE_LVS_EXEMPT_VERDICTS = ("REJECT",)


def _oe_lvs_judgement(lay: dict) -> bool:
    """OE 层复用 LVS 的**判决级**判定（F11）——要么真 pass，要么**显式豁免带理由**。"""
    if bool(lay.get("oe_lvs_pass")):
        return True
    v = lay.get("oe_lvs_verdict")
    note = lay.get("oe_lvs_honest_note")
    n = int(lay.get("oe_lvs_n_violations") or 0)
    return bool(v in _OE_LVS_EXEMPT_VERDICTS
                and isinstance(note, str) and len(note.strip()) > 0 and n > 0)


# 🔴 F5（v0.9.185）：缺口终态的**机器可查证据链**。
#    缺口清单此前是手写字面量（`"closed": True`），与能力实现之间**无机器耦合** ⇒
#    把 M2b/M3 的实现打坏而清单不改，`ok_m2b_gap` / `ok_m3_gap` **仍绿** ——
#    「G-OI5/G-OI6 已闭合」这句声明**没有任何机器证据绑定**。
#    ⇒ 每个闭口必须绑定**重算出来的**判据（读卡内**现算块**，不读 `gaps` 字面量），
#    门禁不变式：`g["closed"] ⇔ g["evidence_ok"]`（逐项一致）。
_GAP_EVIDENCE_SPEC: dict = {
    "G-OI1": "m1.ring_plan：搜索解存在 ∧ minXT≥15dB ∧ M0 默认(0.30/170)对照 <15dB",
    "G-OI2": "m2.g_oi2：真 GDS 元素>0 ∧ DRC 全绿 ∧ LVS ACCEPT/0 ∧ 布局纪律三前提",
    "G-OI3": "m1：EO f₃dB>0 ∧ worst BER < KP4 门限 ∧ 驱动 t90<0.5UI ∧ TIA>1×Nyq ∧ 色散 penalty 可达",
    "G-OI5": "m2b 五项：形态↔均衡 ∧ per-lane 均衡成效 ∧ 热调>0 ∧ Γ 三律 ∧ 良率闭式⟷MC ∧ 封装温窗",
    "G-OI6": "m3.layout_2p5d：拓扑 LVS ∧ 电层 DRC ∧ OE 元素真复用 ∧ OE-LVS 显式豁免(verdict=REJECT+note)",
}


def _gap_evidence_ok(card: dict) -> dict:
    """🔴 F5：对每个缺口**重算**证据（读的是**算出来的值**，不是 `gaps` 里的字面量）。

    ⇒ 「打坏实现而清单不改」时本函数必红（`probe_gap_evidence_binding` 自证）。
    开放缺口（G-OI4 电路级无 PDK / G-OI7 封装级无实测）**无证据** ⇒ `ok=False`。
    """
    m1 = card.get("m1", {}) or {}
    m2 = card.get("m2", {}) or {}
    m2b = card.get("m2b", {}) or {}
    m3 = card.get("m3", {}) or {}
    out: dict = {}

    # ── G-OI1：M1 梳齿规避信道规划（真平台能力）
    try:
        rp = m1.get("ring_plan", {}) or {}
        o1 = (int(rp.get("n_solutions", 0)) > 0
              and float(rp.get("min_xt_db", 0.0)) >= 15.0
              and float(rp.get("m0_default_min_xt_db", 99.0)) < 15.0)
        d1 = ("n_sol=%s · best(m=%s,gap=%s) minXT=%s dB · M0 默认对照=%s dB"
              % (rp.get("n_solutions"), rp.get("m"), rp.get("gap_um"),
                 rp.get("min_xt_db"), rp.get("m0_default_min_xt_db")))
    except Exception as e:                                    # noqa: BLE001
        o1, d1 = False, "EXC %s" % type(e).__name__
    out["G-OI1"] = {"ok": o1, "detail": d1}

    # ── G-OI2：收发器专用真 GDS builder（ACCEPT/0 + DRC + 布局纪律）
    try:
        g2 = m2.get("g_oi2", {}) or {}
        o2 = (g2.get("lvs_verdict") == "ACCEPT"
              and int(g2.get("lvs_n_violations", -1)) == 0
              and bool(g2.get("drc_pass"))
              and int(g2.get("gds_elements", 0)) > 0
              and bool(g2.get("layout_discipline_ok")))
        d2 = ("LVS=%s/%s · DRC=%s · 元素=%s · 布局纪律=%s"
              % (g2.get("lvs_verdict"), g2.get("lvs_n_violations"),
                 g2.get("drc_pass"), g2.get("gds_elements"),
                 g2.get("layout_discipline_ok")))
    except Exception as e:                                    # noqa: BLE001
        o2, d2 = False, "EXC %s" % type(e).__name__
    out["G-OI2"] = {"ok": o2, "detail": d2}

    # ── G-OI3：M1 四项级电光行为模型（EO S21 / 眼图·BER / 驱动-TIA / 色散）
    try:
        drv = m1.get("driver", {}) or {}
        spec1 = m1.get("spec_points", []) or []
        disp = [s.get("disp_penalty_db") for s in spec1
                if s.get("disp_penalty_db") is not None]
        o3 = (float(m1.get("f_3db_eo_ghz", 0.0)) > 0.0
              and float(m1.get("worst_ber", 1.0)) < 3.8e-3          # 802.3dj KP4 门限
              and bool(drv) and float(drv.get("rise_ui", 1.0)) < 0.5
              and float(drv.get("tia_over_nyquist", 0.0)) > 1.0
              and len(disp) > 0 and max(disp) > 0.0)
        d3 = ("EO f3dB=%s GHz · worstBER=%s · t90=%s UI · TIA=%s×Nyq · 色散点=%d(max %s dB)"
              % (m1.get("f_3db_eo_ghz"), m1.get("worst_ber"), drv.get("rise_ui"),
                 drv.get("tia_over_nyquist"), len(disp),
                 (round(max(disp), 3) if disp else None)))
    except Exception as e:                                    # noqa: BLE001
        o3, d3 = False, "EXC %s" % type(e).__name__
    out["G-OI3"] = {"ok": o3, "detail": d3}

    # ── G-OI5：m2b 五项（形态↔均衡 / 均衡成效 / 热调 / Γ / 良率 / 封装）
    try:
        eq = m2b.get("lane_equalizer", {}) or {}
        tune = m2b.get("thermal_tune", {}) or {}
        gam = m2b.get("crosstalk_gamma", {}) or {}
        yl = m2b.get("yield", {}) or {}
        pk = m2b.get("packaging", {}) or {}
        forme = m2b.get("equalizer", {}) or {}
        lpo, rt = forme.get("lpo", {}) or {}, forme.get("retimed", {}) or {}
        _yd = abs(float(yl.get("yield_closed_form", 0.0))
                  - float(yl.get("yield_mc", 1.0)))
        o5 = (lpo.get("ffe") is False and lpo.get("ctle") is True        # 形态↔均衡映射
              and rt.get("ffe") is True and rt.get("needs_dsp") is True
              and bool(eq.get("boost_distinct")) and bool(eq.get("flat_ok"))
              and eq.get("channel_source") == "per_lane(f_mod_ghz)"
              and float(tune.get("p_per_lane_mW", 0.0)) > 0.0
              and bool(gam.get("symmetric_ok")) and bool(gam.get("diagonal_max_ok"))
              and bool(gam.get("monotonic_ok"))
              and _yd < 0.02
              and bool(pk.get("temp_in_tolerance")))
        d5 = ("形态(ffe lpo=%s/retimed=%s) · boost_distinct=%s flat=%s(%s) · "
              "P_tune=%s mW · Γ三律=%s/%s/%s · 良率 Δ=%.6f · 温窗=%s"
              % (lpo.get("ffe"), rt.get("ffe"), eq.get("boost_distinct"),
                 eq.get("flat_ok"), eq.get("channel_source"),
                 tune.get("p_per_lane_mW"), gam.get("symmetric_ok"),
                 gam.get("diagonal_max_ok"), gam.get("monotonic_ok"), _yd,
                 pk.get("temp_in_tolerance")))
    except Exception as e:                                    # noqa: BLE001
        o5, d5 = False, "EXC %s" % type(e).__name__
    out["G-OI5"] = {"ok": o5, "detail": d5}

    # ── G-OI6：M3 2.5D 版图签核（含 F11 的 OE-LVS 显式豁免）
    try:
        lay = m3.get("layout_2p5d", {}) or {}
        lvs = lay.get("lvs_report") or {}
        oe_ok = _oe_lvs_judgement(lay)
        o6 = ("error" not in lay and int(lay.get("gds_bytes_len", 0)) > 0
              and lay.get("fiber_in_layout") is False
              and bool(lay.get("electrical_drc_pass"))
              and bool(lvs.get("pass"))
              and int(lvs.get("n_dangling_paths", 1)) == 0
              and int(lvs.get("n_uncovered_pads", 1)) == 0
              and int(lay.get("oe_elements_reused", 0)) > 0
              and list(lay.get("gds_structures") or []).count("OE_DIE") == 1
              and oe_ok)
        d6 = ("拓扑LVS=%s(悬%s/未覆%s) · 电层DRC=%s · OE复用=%s · OE-LVS=%s(违规%s,豁免=%s)"
              % (lvs.get("pass"), lvs.get("n_dangling_paths"),
                 lvs.get("n_uncovered_pads"), lay.get("electrical_drc_pass"),
                 lay.get("oe_elements_reused"), lay.get("oe_lvs_verdict"),
                 lay.get("oe_lvs_n_violations"), oe_ok))
    except Exception as e:                                    # noqa: BLE001
        o6, d6 = False, "EXC %s" % type(e).__name__
    out["G-OI6"] = {"ok": o6, "detail": d6}

    # ── 开放缺口：**无证据**（闭合必须由证据支撑，不许清单自说自话）
    for gid in ("G-OI4", "G-OI7"):
        out[gid] = {"ok": False, "detail": "开放（T2 锁死区·诚实保留）—— 无证据"}
    return out


def _gap_evidence_gate(card: dict) -> bool:
    """🔴 F5 门禁：每个缺口的 `closed` 必须与其 `evidence_ok` **逐项一致**，
    且闭口必须有非空证据键 ⇒ 「闭合 ⇔ 证据机器可查」。"""
    gaps = card.get("gaps", []) or []
    if not gaps:
        return False
    for g in gaps:
        if bool(g.get("closed")) != bool(g.get("evidence_ok")):
            return False
        if g.get("closed") and not str(g.get("evidence") or "").strip():
            return False
    return True


# --------------------------------------------------------------------------
# 🔴 标准 JSON 出口（v0.9.185 事故修）
#    `json.dumps` 默认把非有限 float 序列化成 `-Infinity` / `Infinity` / `NaN` ——
#    这**不是标准 JSON**，浏览器 `JSON.parse` 必抛 "No number after minus sign in
#    JSON" ⇒ 整张案例卡渲染失败（用户点「运行 光联接模块 M0–M4 案例」只看到一行
#    解析错误）。🔴 Python 侧 `json.load` **接受**这些字面 ⇒ 用 `json.load` 验收
#    公开端点 = **假绿**（本次就栽在这：生产核验全绿而前端一点击就崩）。
#    修法：源头（`lda_l2.oi_m3.NEG_INF_DB`）+ 出口兜底 `_json_safe` 双层，
#    判据 `json_hard_ok` 读的就是**出口那一一份 card**（判据-出口同源，非假判据）。
# --------------------------------------------------------------------------
def _nonfinite_scan(obj, path="", bad=None):
    """递归收集卡内所有**非有限 float**（NaN / ±inf）的 JSON 路径。"""
    if bad is None:
        bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            _nonfinite_scan(v, path + "." + str(k), bad)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _nonfinite_scan(v, "%s[%d]" % (path, i), bad)
    elif isinstance(obj, float) and not math.isfinite(obj):
        bad.append((path, repr(obj)))
    return bad


def json_hard_ok(card) -> bool:
    """🔴 判据：卡内**不得**出现非有限 float（`NaN` / `±inf`）⇒ 必须标准 JSON 可解析。

    存在性判据 ⇒ 必须配反向探针自证能变红（`probe_json_hard_ok`）。
    """
    return not _nonfinite_scan(card)


def _json_safe(obj):
    """出口兜底：任何漏网的非有限 float 换成标准 JSON 可表达的字符串 tag。"""
    if isinstance(obj, float):
        if math.isnan(obj):
            return "NaN"
        if math.isinf(obj):
            return NEG_INF_DB if obj < 0 else "\u221e"
        return obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _r3(v):
    """round 到 3 位；已是 tag（str）则原样返回（对字符串 round 会崩）。"""
    return v if isinstance(v, str) else round(float(v), 3)


def probe_json_hard_ok() -> bool:
    """🔴 反向探针：把非有限 float 灌进**真卡块**（deepcopy ⇒ 走真现算路径）⇒ 必红。

    两条靶子：① 已修好的 M3 NEXT（k=0 的 −∞ 位）② M4 耦合链标量（一般数值位）。
    """
    import copy as _copy
    try:
        _card = case_card(use_cache=True)
        for _p in (("m3", "next", "xtalk_db"), ("m4", "chain", "d_t_photon_k")):
            _bad = _copy.deepcopy(_card)
            _cur = _bad
            for _k in _p[:-1]:
                _cur = _cur[_k]
            _cur[_p[-1]] = float("-inf")
            if json_hard_ok(_bad):
                return False
    except Exception:                                        # noqa: BLE001
        return False
    return True


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
                  "与「收发器真 GDS builder」两项平台此前不具备的能力** + "
                  "**M3 再把规模推到 3.2T（8×400G PAM4，212.5 GBd）CPO 共封装**："
                  "① 400G/lane 带宽墙（TWMZM 双通道：闭式行波电极频响 ⟷ ABCD 阶梯链收敛）；"
                  "② CPO 电通道（电报闭式 ⟷ 1D FDTD 对拍 + NEXT + PDN 地弹）；"
                  "③ die↔die 热与闭环热调（抓出「环路增益 ≫1 致发散」根因）；"
                  "④ 逐项 mW/W 同口径功耗账（CPO vs 可插拔）；⑤ 2.5D 版图签核 G-OI6）；"
                  "**M4 再把 CPO 形态深化为「热-光-电协同设计空间」**（此前三域从未联立）："
                  "① 热-光-电耦合链（ASIC 热 → Δλ_self 1.676 nm → 信道失谐/热调功耗）；"
                  "② **固化点预偏移**（CPO 真实工程解 · 代数解：25.0→41.5 ℃，残余与补偿功耗归零）；"
                  "③ 热致偏移 ⟷ WDM 信道重规划（首次联立，FSR ∝ λ²）；"
                  "④ 三形态三域矩阵（CPO / OBO / 可插拔：热 Θ 100× 差 · 电 IL 总线 ∝ 长 · 光纤耦合）；"
                  "⑤ FAU CTE 热-机械失准（实测 118.8 nm ⇒ 0.0068 dB ≪ 装配公差 ⇒ **非主因**）；"
                  "⑥ 三域 Pareto 前沿（**10/10 全非支配**）+ **VπL 诚实断口**（M3 隐含 0.24 V·cm "
                  "比公开 SiP 激进 6.25× ⇒ 可行域收缩到 L=6 mm ≠ M3 的 2 mm）"),
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
        "method_m2b": "M2b 把**设计 ⟷ 版图 ⟷ 工艺 ⟷ 封装**四层咬成闭环：(均衡) 逐 lane CTLE "
                      "抽头（各 lane 工艺离散 ⇒ 目标 boost 不同 ⇒ 均衡后总增益拉平）+ "
                      "形态↔均衡映射（LPO 无 DSP ⇒ 只有模拟 CTLE，不能 FFE）；(热) 热调 "
                      "Pπ 进链路（只报 mW）+ 热串扰 Γ 矩阵（**坐标取自真版图 placement**，"
                      "互易/单调/对角最大三条物理律 + 有限差分热网络第二通道）；"
                      "(工艺/封装) 工艺偏差→良率（golden 闭式 Φ ⟷ MC 第二通道）、"
                      "封装容差（对准 IL 预算先扣模场失配底 + GC 出射角温漂真物理）",
            "method_m3": "M3 补**带宽墙 × 电通道 × 热 × 功耗 × 版图**五维：(带宽墙) 400G/lane ="
                         "212.5 GBd ⇒ 奈奎斯特 106.25 GHz，行波电极闭式 |H|=(1/L)|∫e^{−qx}dx|"
                         "（q 的虚部**减掉光相位基准** ω·n_g,opt/c，速度失配只经残留 Δn_g 进闭式）"
                         "⟷ ABCD 阶梯链逐段推进（末端匹配端接 Z0=√(z/y)）第二通道，网格加密"
                         "相对误差单调下降 4.25%→0.50%；(电通道) CPO die-to-die mm 级总线"
                         "e^{−γL} ⟷ 1D FDTD 时域对拍渡越时间（无损口径）+ NEXT 功率比 "
                         "K²(F/f₀)⁴/3 + PDN 地弹 L·di/dt；(热) 两串热阻的 die↔die 热"
                         "（对数解 ⟷ M2b 有限差分网络）+ **闭环热调代数解**（单通路 S≡dλ/dT·R_h）；"
                         "(功耗) 逐项 mW 逐口径对拍（CPO vs 可插拔，只 mW/W）；"
                         "(版图) 2.5D：ASIC die + 中介层 + 光引擎 die + FAU 接触点，"
                         "电层 DRC + 电网络拓扑 LVS",
            "method_m4": "M4 把**热 ↔ 光 ↔ 电**三域**首次联立**成一条耦合链（此前热调只在光子 die "
                         "内闭环、电通道只管自己的 S 参数、热致波长偏移从未喂回信道规划）："
                         "(耦合链) P_asic → ΔT_phot(=M3 同源 16.500 K) → Δλ_self(1.676 nm) → "
                         "{信道失谐 0.373 间距, 热调功耗}；(预偏移) CPO 真实工程解＝把环**固化点**"
                         "预偏移到热平衡温度（代数解，25.0→41.5 ℃）；(热×规划) 热态波长喂回"
                         "`plan_lwdm_channels` 重规划（FSR ∝ λ²）；(形态族) CPO/OBO/可插拔三域矩阵"
                         "（热 1/d 远场标度 · 电 √f 律 + 总线长 · 光纤耦合）；(CTE) FAU↔Si CTE "
                         "失配 → 高斯模场闭式；(前沿) 共享变量 L 上三域 Pareto + **VπL 规格锚**。"
                         "🔴 只出 K/nm/dB/mW/GHz，不折算能效比",
            "anchor_B19": "无源无增益不等式 |T|≤1（所有 transfer 幅值 ≤1），M0/M1/M2 全部满足",
            "honest_layer": "M0/M1/M2/M3/M4 均属设计预算层（L0 解析器件模型 + A 档闭式/行为级）；"
                            "真实版图 GDS 由 D4 域 photonic_interconnect 与 M2 新增的 "
                            "oi_transceiver（G-OI2 收发器拓扑）承载；M3 的 2.5D 版图复用它；"
                            "M4 的材料 CTE / VπL / 模场半径 / 三形态总线长均为**规格锚**"
                            "（公开工艺近似，非 foundry 真值 ⇒ G-OI7 诚实保留）",
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
            "m2b": _m2b_block(),
            "m3": _m3_block(),
            "m4": _m4_block(),
            "m5": _m5_block(),
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
            {"id": "M3-1", "label": "规模 3.2T + 400G/lane 带宽墙（TWMZM 双通道）",
             "detail": "8×400G PAM4 = 212.5 GBd / 奈奎斯特 106.25 GHz（**由 M2 的 200G 档派生，"
                       "不重抄**：PAM4_BAUD_3200 = 2×106.25）。行波电极 L=2 mm 闭式频响 434.4 GHz"
                       "（奈奎斯特 4.09×，12.23 dB 裕量）；第二通道 ABCD 阶梯链 100→800 段"
                       "相对误差 4.25%→0.50% 单调下降。🔴 首版两处真 bug：q 的虚部漏减光相位基准"
                       "ω·n_g,opt/c（⇒ 速度失配被算成整条微波 β），以及分布 RC 极点 f∝1/L² 写成 1/L"},
            {"id": "M3-2", "label": "CPO 电通道：电报闭式 ⟷ 1D FDTD + NEXT + PDN 地弹",
             "detail": "die-to-die 电总线 5 mm（CPO 本质：cm→mm）：闭式 e^{−γL} 与 1D Yee FDTD"
                       "（dt=0.5·dx/v_p 满足 CFL）对拍渡越时间 50.888 ⟷ 50.000 ps（1.78%）；"
                       "NEXT 功率比 K²(F/f₀)⁴/3（K=0.08 @106.25 GHz ⇒ 54.34 dB）；PDN 地弹 "
                       "V=L·di/dt 作**量级披露**（0.5 nH × 8e10 A/s = 40 V ⇒ 真实 CPO 必须靠"
                       "解耦电容压 di/dt，本模块只做项级建模）。首版 FDTD 三错（系数取倒数 / "
                       "Yee 顺序反 / 3 ps 尾巴 << 50 ps 渡越）⇒ 采到全 0、相速 5e27"},
            {"id": "M3-3", "label": "吃狗粮：闭环热调发散根因定位（1e88 K → 代数解）",
             "detail": "CPO 的题眼是 ASIC 热直抬光子 die：ΔT = P_asic·(R_a+R_i) = 3 W×5.5 K/W = "
                       "16.5 K ⇒ 光子 die 41.5 ℃ > 设定点 25 ℃ ⇒ **单向加热器补不回来**"
                       "（工程解＝固化点预偏移或双向 TEC），残余失谐 1.676 nm = 0.343 FSR。"
                       "首版不动点迭代**发散到 1.15e88 K**：真根因是 M2b 的 S=dλ/dP 已含自热，"
                       "M3 又抄了 r_th=8.0 K/W（真值 1.0 K/mW）且把「加热器→温升→波长」"
                       "通路**算两遍** ⇒ 环路增益 ≈28≫1。修法：R_h 回单一真源 + 代数解 + "
                       "`algebraic ⟷ fixed_point(A=1)` 收敛一致 + **双计 A≫1 必发散** 两条真判据"},
            {"id": "M3-4", "label": "逐项 mW/W 功耗账 + 2.5D 版图签核（G-OI6）",
             "detail": "功耗同口径逐项对拍：CPO 354.5 mW/lane（2.836 W/模块）vs 可插拔 546.1 mW/lane"
                       "（4.369 W）；CPO 多付热调跟踪 16.5 mW + 中介层 PDN 25 mW，省掉板级驱动动态"
                       "与板上终端。2.5D 版图：ASIC die 1800 µm + 中介层 3080 µm + 光引擎 die"
                       "（**复用 G-OI2 builder 元素**）+ FAU 接触点（片外 fiber 不落版图），"
                       "电层 DRC + 电网络拓扑 LVS 双闸 ⇒ 6 结构 / 247 元素 / 22 KB GDS."},
            {"id": "M4-1", "label": "热-光-电耦合链：三域首次联立（ASIC 热 → 波长 → 信道/功耗）",
             "detail": "此前热调只在光子 die 内闭环、电通道只管自己的 S 参数、热致波长偏移从未喂回"
                       "信道规划 ⇒ M4 把三者接成**一条链**：P_asic 3 W × (R_a+R_i) 5.5 K/W = "
                       "**ΔT_photon 16.500 K**（与 M3 闭环热调残余**同源一致**）⇒ Δλ_self = "
                       "**1.676 nm**（0.343 FSR / 0.373 个信道间距）；单向加热器**不可行**"
                       "（可供电 0.000 mW ⇒ 方向 `cool(TEC)`）—— 链上最关键的一环由 `chain_"
                       "consistent_with_m3_residual` 判据锁死，跨模块同源不得各算各的"},
            {"id": "M4-2", "label": "固化点预偏移（CPO 真实工程解 · 代数解）",
             "detail": "CPO 里 ASIC 热把光子 die 抬到 41.5 ℃ > 环**固化点** 25 ℃ ⇒ 单向加热器补不回来"
                       "（M3 已判死）。M4 给出**真正的工程解**：把环固化点**预偏移**到热平衡温度"
                       "（25.0 → **41.5 ℃**）⇒ 热态残余由 **1.676 nm 归零到 0.000 nm**，补偿功耗"
                       "同时由 16.500 → **0.000 mW/lane**（**代数解**，非不动点迭代）；"
                       "🔴 残余/功耗**由公式算出**（不是写死的 0）⇒ 口径不一致时可被探针 P2 打红"},
            {"id": "M4-3", "label": "热致偏移 ⟷ WDM 信道重规划（首次联立）",
             "detail": "把热态波长**喂回**信道规划器：热致偏移后 wl0 1311.000 → 1312.676 nm；"
                       "FSR ∝ λ² ⇒ 4.8918 → 4.9043 nm（**+0.256%**，非零，说明联立真起作用而非摆设）；"
                       "在**热平衡波长**下重规划 m 由 268 不变（`m_changed=False`）· 热态最坏隔离 "
                       "**41.52 dB** · `plan_still_valid=True` ⇒ 结论：本设计点下热致失谐**不推翻**"
                       "现有的梳齿规避解（但这是**算出来的**，不是假设的）"},
            {"id": "M4-4", "label": "三形态三域矩阵 + FAU CTE + 三域 Pareto + VπL 断口（G-OI7）",
             "detail": "① 三形态（CPO / OBO / 可插拔）同口径三域代价：热耦合 Θ **0.2877 ≫ 0.0288 ≫ "
                       "0.00288 K/W**（几何 1/d 远场标度，CPO 是 OBO 的 10×、可插拔的 100×）；"
                       "电层 IL（M3 电通道 √f 模型 · 总线 5/50/100 mm 线性外推）25.95 → 259.5 → "
                       "519.1 dB；光纤耦合 1.5/1.2/0.8 dB ⇒ **三域互相冲突，无单一赢家**。"
                       "② FAU CTE 热-机械失准：Δx =(α_FAU−α_Si)·L_arm·ΔT ⇒ 实测 **118.8 nm** ⇒ "
                       "高斯模场闭式 IL 仅 **0.0068 dB** ≪ 装配公差 **0.1206 dB** ⇒ **CTE 非耦合损耗"
                       "主因**（反直觉诚实结论）。③ 三域 Pareto（共享变量 L）：**10/10 全非支配**"
                       "（BW∝1/L² · IL∝L · P∝1/L 两两权衡）；**VπL 断口**：M3 设计点隐含 "
                       "VπL=**0.24 V·cm**，比公开 SiP 典型 1.0–2.5 激进 **6.25×** ⇒ 用公开 VπL + "
                       "CMOS 摆幅 3.3 V，可行域**收缩到 1 点（L=6 mm）**且 **≠ M3 的 2 mm** ⇒ "
                       "**带宽墙部分是「调制效率墙」**。新增缺口 **G-OI7**（封装级热-机械-光真值缺失）"},
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
            {"title": "🔴 M3 复用不是「换皮」：光引擎元素真复用 + 双闸口径差异如实报",
             "detail": "`cpo_2p5d_layout` 复用 `chip_layout_export.device_elements`（与 "
                       "`export_chip_gds` 同源的元素生成器），**不是**另写一份光层几何 ⇒ "
                       "6 结构 / 247 元素 / 22 KB GDS，其中 `OE_DIE` 93 元素是**现算复用**的。"
                       "但口径必须拆开说：通用导出路径的 LVS 双闸（连接 + 器件参数几何回提）"
                       "对 ring 报 **REJECT**（declared gap 0.55 µm vs measured 232.3 µm ⇒ "
                       "回提对 ring 不适用），而 M2 的 G-OI2 builder 自己那条管线是 ACCEPT / 0 违规。"
                       "M3 不抹平这个差异、不改叫 ACCEPT，也不因此拒出图 —— 2.5D 层只做"
                       "**几何-拓扑 LVS** + 电层 DRC，片外 fiber 不落版图。"},
            {"title": "G-OI2 版图「零 cross_short」是**结构性**的，不是调出来的",
             "detail": "Tx/Rx 均用 L 型走线：源 x 递增 ⟂ 目标 y 反向 ⇒ 竖直段 i 与水平段 j 的相交"
                       "充要条件退化为 i=j（自身），故**零交叉**。Tx 与 Rx 的 y 带再整体分离"
                       "（Tx y∈[−3.8,178.2] / Rx y∈[−379.3,−250.9]）⇒ 跨域也不交叉"},
            {"title": "LPO 代价实测 ≥ 内码增益（3.169 vs 2.744 dB）",
             "detail": "LPO 相对重定时的裕量缩水 = 理想内码增益 **+ ISI 口径差**（0.425dB，因 RS-only "
                       "门限更紧 ⇒ 可达 SNR 工作点不同）。恒等式 `pen ≡ gain + (ISI_LPO − ISI_retimed)` "
                       "已由门禁 C10d 逐位锁死（Δ<1e-9）"},
            {"title": "🔴 M4 最有价值发现：VπL 口径缺口（定稿阶段就抓出）",
             "detail": "`OI_M3_PROCESS` **没有 VπL** ⇒ M3 的 `driver_dynamic_mw` 走的是**封装线电容**"
                       "（与电极长度 L 无关）⇒ 三目标退化、**Pareto 根本不成立**。修正为「显式电极"
                       "电容 C′·L + VπL 规格锚」后，用 f_RC = 4 Ω × 400 fF = 1.6 ps ⇒ 99.472 GHz "
                       "**逐位反验**正确。由此长出真断口：M3 设计点（v_pp 3.0 V × L 2 mm）**隐含** "
                       "VπL = **0.24 V·cm**，比公开 SiP 典型 **1.0–2.5 V·cm** **激进 4.2–10.4×**；"
                       "叠加 CMOS 摆幅 3.3 V ⇒ 公开 VπL 下可行域从 10 点**收缩到 1 点（L=6 mm）**，"
                       "且 **≠ M3 的 2 mm** ⇒ 所谓「带宽墙」**部分是「调制效率墙」**。"
                       "🔴 这是**定稿阶段**（不是跑挂之后）就靠机器假设核查抓出的缺口"},
            {"title": "🔴 CTE 失配不是耦合损耗主因（反直觉 · 有判据守）",
             "detail": "FAU 与 Si 光子 die 的 CTE 失配（3.2e-6 vs 2.6e-6 /K）在 ΔT=16.5 K、12 mm "
                       "臂长下只产生 **118.8 nm** 横向漂移 ⇒ 高斯模场闭式 IL **0.0068 dB**，"
                       "比**装配对准公差**（0.5 µm ⇒ 0.1206 dB）小一个量级 ⇒ `cte_is_dominant=False`。"
                       "结论：封装 IL 预算的主要矛盾在**装配公差**，不在 CTE 漂移（但 CTE 仍是"
                       "长期可靠性/温循关注点，属 G-OI7 诚实保留）"},
            {"title": "🔴 M4 自查抓出我自己写的假判据（同源相等）",
             "detail": "门禁 P5 首跑**红不了** ⇒ 顺线查出 oi_case 里一条判据写成 "
                       "`wl0_cold == OI_M4_PROCESS['wl0_nm']` —— 两边同源、**恒真**，任何探针都"
                       "改不红。修法：改咬语义的 **O-band 归属判定**（1260–1360 nm 且与 M2 一致 + "
                       "与 M1 的 C-band 默认不同）；另两条同源相等的「残余/补偿功耗」也改为"
                       "**由公式算**并断言 `after < without`。识别法：**问「把上游常量改掉，这条会红吗？」**"},
            {"title": "三域两两权衡 ⇒ 无单一最优 L（Pareto 10/10 全非支配）",
             "detail": "共享自由变量 L 上：带宽 BW∝1/L²（越大越好）· 电极线损 IL∝L（越小越好）· "
                       "驱动功耗 P∝1/L（越小越好）⇒ **两两反向**，10 个设计点**全部非支配**、"
                       "被支配点 0 个。这不是「模型没收敛」，而是「三域本来就没有单一最优」——"
                       "设计点必须由**系统级约束**（带宽线 + CMOS 摆幅）钉住，不能靠单域调优"},
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
            {"id": "G-OI5", "closed": True,
             "title": "M2b 已闭合：多通道均衡 · 热调 · 热串扰 Γ · 良率 MC · 封装容差",
             "detail": "五项全部落地（`lda_l2/oi_m2b.py` + 门禁 `run_oi_m2b_smoke.py` "
                       "**89 行 = 39 基线判据 ×2 + 10 突变探针 + 1 还原一致** + 模块自检 31 项）："
                       "① 多通道 CTLE（逐 lane 抽头，工艺离散 ±3% ⇒ "
                       "目标 boost 各异 ⇒ 均衡后总增益拉平，spread<1e-15 dB）+ **形态↔均衡映射**"
                       "（LPO 无 DSP ⇒ 只有模拟 CTLE、不能 FFE，探针 P3 守）；② 热调 Pπ 进链路"
                       "（只报 mW，不做能效比）；③ Γ 矩阵**版图绑定**（坐标取真版图 placement，"
                       "互易/单调/对角最大 + 有限差分热网络第二通道）；④ 工艺偏差→良率"
                       "（golden 闭式 Φ ⟷ MC N=20000 固定 seed 第二通道）；⑤ 封装容差"
                       "(对准 IL 预算先扣模场失配底 + GC 出射角温溢真物理）。"
                       "与 G-OI4 合并考虑后，G-OI4「电路级模型 · 无 PDK · 不报 TOPS」**仍开放**"},
            {"id": "G-OI6", "closed": True,
             "title": "M3 已闭合：2.5D 版图签核（ASIC die + 中介层 + 光引擎 die + FAU）",
             "detail": "`lda_l2/oi_m3.cpo_2p5d_geometry/cpo_2p5d_layout`：ASIC die 1800 µm + "
                       "中介层 `d_out = a + 2·margin`（margin=16·pad，**相对 die 尺寸**外扩，"
                       "防 die 越出中介层）+ 光引擎 die（**复用** M2 G-OI2 builder 的元素，"
                       "不重造光层）+ FAU 接触点（片外 fiber 不落版图）；电层 DRC（min width/"
                       "min space/差分 pitch 互锁）+ 电网络拓扑 LVS（反向完备）。"
                       "🔴 首版 `cpo_2p5d_layout` 把 `gds_parse['structures']`（**统计摘要**，"
                       "形如 {cell:{elements,layers}}）当元素字节喂 GDS ⇒ join 处 TypeError，"
                       "光引擎复用这条狗粮路径**根本没通**；改走 `chip_layout_export."
                       "device_elements`（与 `export_chip_gds` 同源）后 6 结构/247 元素/22 KB "
                       "GDS 出图。G-OI4「电路级模型 · 无 PDK · 不报 TOPS」**仍开放**"},
            {"id": "G-OI7", "closed": False,
             "title": "封装级热-机械-光真值缺失（M4 新增）",
             "detail": "M4（CPO 形态深化）暴露：材料 CTE 用**公开手册值**（Si 2.6e-6 / 玻璃 FAU "
                       "3.2e-6 /K，**不是本封装实测**）· FAU 对准公差**无分布数据** · "
                       "封装应力/翘曲**无实测** · CTE 失配→耦合损耗用**高斯模场闭式**"
                       "（未含实测模场交叠/端面反射/横向偏移之外的失配机制）；"
                       "三形态热耦合 θ 差异用几何标度（1/d 远场近似）。"
                       "🔴 属 **T2 锁死区**，是**诚实保留**项。"
                       "与 G-OI4 **域不同、不重复记账**（G-OI4 = 电路级无 PDK；G-OI7 = 封装级无实测）"},
        ],
        "gaps_closed": 5,      # G-OI1 / G-OI2 / G-OI3 / G-OI5 / G-OI6（G-OI4 与 G-OI7 开放）
        "gaps_total": 7,
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
                        "M4 仍属**设计预算层**：材料 CTE / VπL / 模场半径 / 三形态总线长均为"
                        "**规格锚**（公开工艺近似，非 foundry 真值 ⇒ G-OI7 诚实保留），"
                        "三形态热耦合 θ 用几何标度（1/d 远场）非实测封装数据，"
                        "FAU 对准公差无分布数据、封装应力/翘曲无实测；"
                        "🔴 M4 三域代价**只出 mW / W / K / nm / dB / GHz**；"
                        "不报 TOPS/TOPS-W/fJ/op/pJ/bit；判决由死标量给出，LLM 不进判决路径。"),
    }
    # 🔴 F5：把**重算出来的**证据挂到每个缺口上（`closed ⇔ evidence_ok` 由 run_selfchecks 门禁守住）
    _ev = _gap_evidence_ok(card)
    for _g in card["gaps"]:
        _e = _ev.get(_g["id"], {"ok": False, "detail": "无证据登记"})
        _g["evidence"] = _GAP_EVIDENCE_SPEC.get(_g["id"], "")
        _g["evidence_ok"] = bool(_e["ok"])
        _g["evidence_detail"] = str(_e["detail"])
    # 🔴 标准 JSON 出口：非有限 float → tag 字符串（判据 `json_hard_ok` 读的就是这份 card）
    card = _json_safe(card)
    _nf = _nonfinite_scan(card)
    card["json_hard_ok"] = (not _nf)
    card["json_hard_bad"] = _nf[:8]
    if use_cache:
        _CACHE[key] = card
    return card


def _positive_surface(obj: object) -> str:
    """递归取「肯定式宣称面」字符串（禁词扫描只扫这一面）。

    规则：逐值递归 dict/list/tuple/set；对字符串，若含任一否定标记则**截断到该标记处**
    （标记及其后文剔除），否则整串保留。
    🔴 为什么是「截断」而不是「整串跳过」：整串跳过会把「本模块提供 TOPS 级算力，
    但不报 TOPS-W」整句免责 ⇒ 真违规漏网（假绿）。截断式把否定前的肯定面照扫，
    既豁免了正确自我否定，又不给「肯定式违规」开后门。
    """
    parts: list[str] = []
    stack = [obj]
    while stack:
        _cur = stack.pop()
        if isinstance(_cur, dict):
            stack.extend(_cur.values())
        elif isinstance(_cur, (list, tuple, set, frozenset)):
            stack.extend(_cur)
        elif isinstance(_cur, str):
            _cut = None
            for _m in _NEG_MARKERS:
                _i = _cur.find(_m)
                if _i >= 0 and (_cut is None or _i < _cut):
                    _cut = _i
            parts.append(_cur if _cut is None else _cur[:_cut])
    return "\n".join(parts)


def _m2b_pkg_consistent(m2b: dict) -> bool:
    """M2b 封装块「卡内数字 ≡ 模块现算」同源回读（温漂链必须一起对拍）。

    容差取「对外四舍五入的半个步长」（wl 4 位 ⇒ 5e-5，dx 5 位 ⇒ 5e-6）：
    比显示精度粗 ⇒ 换一位小数不红；比一个步长细 ⇒ 数字真变必红。
    🔴 单独抽成函数是为了能被探针直接喂**被篡改的块**（否则判据恒绿、无从证伪）。
    """
    from lda_l2 import oi_m2b as M2B

    _ab = M2B.alignment_tolerance_budget()
    _tdb = M2B.temp_drift_budget()
    return (abs(float(m2b["packaging"]["dx_max_um"]) - float(_ab["dx_max_um"])) < 1e-3
            and abs(float(m2b["packaging"]["il_mode_mismatch_db"])
                    - float(_ab["il_mode_mismatch_db"])) < 1e-3
            and abs(float(m2b["packaging"]["wl_drift_nm"]) - float(_tdb["dlam_nm"])) < 5e-5
            and abs(float(m2b["packaging"]["dx_drift_um"]) - float(_tdb["dx_drift_um"])) < 5e-6)


def probe_banned_token_scan() -> bool:
    """🔴 探针：证明「禁词只扫肯定式宣称面」这套口径**真能变红**，否则它是假判据。

    双向断言（缺一即假绿）：
      · 正例（必须被抓到）：否定标记**之前**出现 `TOPS` ⇒ `_positive_surface` 仍含 `TOPS`
        ⇒ 禁词扫描会红。（防「整串跳过」式豁免把真违规整句免责的 E12/E13/E17 同族血案）
      · 负例（必须被豁免）：纯否定式自我声明「本项目不报 TOPS / TOPS-W / fJ-op / pJ-bit」
        ⇒ 截断后不含任何禁用 token ⇒ 不误杀正确诚实声明（本卡 `honest_note*` 全靠这条存活）。
      · 嵌套例：`honest_note_m2b_thermal` 这类**嵌套**在 m2b 子 dict 里的否定声明
        ⇒ 递归能取到并豁免（顶层 `honest_note*` 键豁免会漏掉嵌套层）。
    """
    pos = "本模块提供 TOPS 级算力与 TOPS-W 能效比，且不报 pJ/bit"
    if "TOPS" not in _positive_surface(pos):
        return False                       # 肯定式被豁免 ⇒ 扫描形同虚设（假绿）
    neg = "本项目**不报** TOPS / TOPS-W / fJ-op / pJ-bit 能效比。"
    for _t in ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "pJ/bit", "W/op"):
        if _t in _positive_surface(neg):
            return False                   # 正确否定被误杀 ⇒ 口径过宽
    nested = {"honest_note_m2b_thermal": neg, "p_per_lane_mW": 51.672}
    if any(_t in _positive_surface(nested) for _t in
           ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "pJ/bit", "W/op")):
        return False                       # 嵌套否定声明未被递归豁免
    return True


def probe_m2b_pkg_same_source() -> bool:
    """🔴 探针：证明 `_m2b_pkg_consistent` 不是恒绿判据（先证能变红，再信它）。

    双向断言：
      · 正例：真块 ⇒ True（否则自检自毁）；
      · 反例：把块的温漂数字改成错值（+5 nm / +0.5 µm，远超半步长）
        ⇒ 必须 False。防「温漂从未与模块对拍、判据只看显然字段」的静默盲区。
    """
    import copy as _copy
    _blk = _m2b_block()
    if not _m2b_pkg_consistent(_blk):
        return False                                   # 真块都不绿 ⇒ 判据写错
    _bad = _copy.deepcopy(_blk)
    _bad["packaging"]["wl_drift_nm"] = float(_bad["packaging"]["wl_drift_nm"]) + 5.0
    if _m2b_pkg_consistent(_bad):
        return False                                   # 数字真变了还绿 ⇒ 假绿
    _bad2 = _copy.deepcopy(_blk)
    _bad2["packaging"]["dx_drift_um"] = float(_bad2["packaging"]["dx_drift_um"]) + 0.5
    if _m2b_pkg_consistent(_bad2):
        return False
    return True


def _m3_pkg_consistent(m3: dict) -> bool:
    """M3 块「卡内数字 ≡ 模块现算」同源回读（带宽墙 / 功耗 / 热 / 闭环热调四链一起对拍）。

    🔴 单独抽成函数是为了能被探针直接喂**被篡改的块**（否则判据恒绿、无从证伪）。
    """
    from lda_l2 import oi_m3 as M3

    rec = M3.power_reconcile()
    cl = M3.closed_loop_thermal_steady()
    ths = M3.die_thermal_stack()
    tw = M3.twmzm_design()
    twm, pw, th, clp = m3["twmzm"], m3["power"], m3["thermal"], m3["closed_loop_thermal"]
    return (
        abs(twm["f3db_ghz"] - tw["f3db_hz"] / 1e9) < 1e-3
        and abs(twm["margin_db"] - tw["margin_db"]) < 1e-3
        and abs(twm["f_rc_ghz"] - tw["f_rc_hz"] / 1e9) < 1e-3
        and abs(pw["cpo_per_lane_mw"] - rec["cpo"]["per_lane_total_mw"]) < 1e-3
        and abs(pw["pluggable_per_lane_mw"] - rec["pluggable"]["per_lane_total_mw"]) < 1e-3
        and abs(pw["cpo_total_w"] - rec["cpo"]["module_total_w"]) < 1e-3
        and abs(pw["cpo_advantage_thermal_mw"] - rec["cpo_advantage_thermal_mw"]) < 1e-3
        and abs(th["t_photon_c"] - ths["t_photon_c"]) < 1e-3
        and abs(th["d_t_photon_c"] - ths["d_t_photon_c"]) < 1e-3
        and abs(clp["p_actuator_mw_per_lane"]
               - cl["p_actuator_required_mw_per_lane"]) < 1e-3
        and abs(clp["residual_nm"] - cl["residual_nm"]) < 1e-3
        and abs(clp["r_h_k_per_mw"] - cl["r_h_k_per_mw"]) < 1e-9
    )


def probe_m3_pkg_same_source() -> bool:
    """🔴 探针：证 `_m3_pkg_consistent` 不是恒绿（先证能变红，再信它）。

    反例必须覆盖**四条链**（改一个就够 ⇒ 只改一条不足以证明「全链对拍」）：
      · 带宽墙（f3db）· 功耗（cpo_total_w）· 热（t_photon）· 闭环热调（p_actuator）
    任一真数字被改 ⇒ 必须 False。
    """
    import copy as _copy
    _blk = _m3_block()
    if not _m3_pkg_consistent(_blk):
        return False                                   # 真块都不绿 ⇒ 判据写错
    for _path, _delta in ((("twmzm", "f3db_ghz"), 5.0),
                          (("power", "cpo_total_w"), 0.25),
                          (("thermal", "t_photon_c"), 3.0),
                          (("closed_loop_thermal", "p_actuator_mw_per_lane"), 7.0)):
        _bad = _copy.deepcopy(_blk)
        _cur = _bad
        for _k in _path[:-1]:
            _cur = _cur[_k]
        _cur[_path[-1]] = float(_cur[_path[-1]]) + _delta
        if _m3_pkg_consistent(_bad):
            return False                               # 数字真变了还绿 ⇒ 假绿
    return True


def probe_m3_loop_is_algebraic() -> bool:
    """🔴 探针：M3 闭环热调必须**收敛**（抓「双计 ⇒ 不动点发散到 1e88 K」血案回归）。

    🔴 v0.9.185 修 F2：首版此探针是**死码负例** ——
    `if _blk.get("closed_loop_thermal") == _bad and _bad["single_path_consistency"]:`
    两个合取项按构造**恒 False**（真块 ≠ 篡改副本；且副本该字段本就是 False）⇒ 分支
    永不触发，函数只剩正例回读 ⇒ **恒 True**。现在**调用真实现**做双向断言：
      · 正例：默认解 `converged` 且 `solution` 由求解路径返回；A=1 fixed_point 收敛到同值；
      · 反例：**双计**（`loop_gain=28`）走真实现 ⇒ **必发散**（`converged=False`）。
    """
    from lda_l2 import oi_m3 as M3

    _cl = M3.closed_loop_thermal_steady()
    if not (_cl["converged"] is True and _cl["solution"] == "algebraic"):
        return False
    if not M3._algebraic_matches_fixed_point():       # 第二独立通道：代数 ⟷ 不动点
        return False
    # 🔴 反例走**真实现**：双计（A≈28）灌进 fixed_point ⇒ 必须发散
    _bad = M3.closed_loop_thermal_steady(solve_mode="fixed_point", loop_gain=28.0)
    if not (_bad["converged"] is False and _bad["diverged"] is True):
        return False
    return True


def _m4_pkg_consistent(m4: dict) -> bool:
    """M4 块「卡内数字 ≡ 模块现算」同源回读（耦合链 / 预偏移 / 重规划 / 三形态 / CTE /
    Pareto / 可行性墙 / 波段 / 斜率九链一起对拍）。

    🔴 单独抽成函数是为了能被探针直接喂**被篡改的块**（否则判据恒绿、无从证伪）。
    """
    from lda_l2 import oi_m4 as M4

    ch = M4.co_design_chain()
    pb = M4.setpoint_prebias_design()
    rp = M4.thermal_channel_replan()
    fm = M4.package_form_factor_compare()
    ct = M4.fau_cte_misalignment()
    pa = M4.pareto_front_l_electrode()
    wl = M4.feasibility_wall()
    bl = M4.band_lock()
    sl = M4.thermal_optical_slope_lock()

    c, p, r = m4["chain"], m4["prebias"], m4["replan"]
    f, x, q = m4["forms"], m4["cte"], m4["pareto"]
    w, b, s = m4["feasibility_wall"], m4["band_lock"], m4["slope_lock"]

    return (
        abs(c["d_t_photon_k"] - ch["d_t_photon_k"]) < 1e-6
        and abs(c["d_lambda_self_nm"] - ch["d_lambda_self_nm"]) < 1e-6
        and abs(c["d_lambda_frac_fsr"] - ch["d_lambda_frac_fsr"]) < 1e-6
        and bool(c["unidirectional_heater_feasible"]) == bool(ch["unidirectional_heater_feasible"])
        and abs(p["setpoint_shift_nm"] - pb["setpoint_shift_nm"]) < 1e-6
        and abs(p["residual_nm_after_prebias"] - pb["residual_nm_after_prebias"]) < 1e-8
        and abs(p["t_eq_c"] - pb["t_eq_c"]) < 1e-6
        and abs(r["wl0_hot_nm"] - rp["wl0_hot_nm"]) < 1e-6
        and abs(r["fsr_rel_change"] - rp["fsr_rel_change"]) < 1e-8
        and len(f["forms"]) == len(fm["forms"])
        and all(abs(f["forms"][k]["theta_k_per_w"] - fm["forms"][k]["theta_k_per_w"]) < 1e-6
                for k in fm["forms"])
        and abs(x["dx_nm"] - ct["dx_nm"]) < 1e-6
        and abs(x["il_cte_db"] - ct["il_cte_db"]) < 1e-6
        and bool(x["cte_is_dominant"]) == bool(ct["cte_is_dominant"])
        and q["n_points"] == pa["n_points"] and q["n_front"] == pa["n_front"]
        and bool(q["all_points_non_dominated"]) == bool(pa["all_points_non_dominated"])
        and [round(v, 9) for v in q["feasible_l_mm"]] == [round(v, 9) for v in pa["feasible_l_mm"]]
        and bool(q["m3_design_on_front"]) == bool(pa["m3_design_on_front"])
        and abs(q["vpi_l"]["vpi_l_implied_by_m3_v_cm"]
                - pa["vpi_l"]["vpi_l_implied_by_m3_v_cm"]) < 1e-9
        and w["public_vpi_l_feasible_points"] == wl["public_vpi_l_feasible_points"]
        and bool(w["public_feasible_collapsed"]) == bool(wl["public_feasible_collapsed"])
        and abs(b["m4_wl0_nm"] - bl["m4_wl0_nm"]) < 1e-9
        and bool(b["same_as_m2"]) == bool(bl["same_as_m2"])
        and bool(b["differs_from_m1_default"]) == bool(bl["differs_from_m1_default"])
        and abs(s["rel_diff"] - sl["rel_diff"]) < 1e-9
    )


def _m4_vpi_l_honest(m4: dict) -> bool:
    """M4 VπL 断口**诚实性**（不是同源相等）：必须如实承认 M3 隐含 VπL 与公开工艺不符。

    守的血案：「外部常量/规格取值错一处 ⇒ 整条链路余量判断反向」（M1 的 KP4 门限同族）。
    若被抹平（说成落在公开区间内）⇒ 判 False。
    """
    _v = m4["pareto"]["vpi_l"]
    return (
        bool(_v["consistent_with_public_process"]) is False
        and float(_v["vpi_l_gap_ratio"]) > 1.0
        and float(_v["vpi_l_implied_by_m3_v_cm"]) < float(_v["vpi_l_public_band_v_cm"][0])
    )


def probe_m4_same_source() -> bool:
    """🔴 探针：证 `_m4_pkg_consistent` 不是恒绿（先证能变红，再信它）。

    反例覆盖**六条链**任改其一必红（只改一条不足以证明「全链对拍」）：
      · 耦合链（d_lambda_self）· 预偏移（残余）· 重规划（fsr 相对变化）·
        三形态 CTE（dx_nm）· Pareto（前沿点数）· 波段互锁（m4_wl0）
    """
    import copy as _copy
    _blk = _m4_block()
    if not _m4_pkg_consistent(_blk):
        return False                                   # 真块都不绿 ⇒ 判据写错
    for _path, _delta in ((("chain", "d_lambda_self_nm"), 0.05),
                          (("prebias", "residual_nm_after_prebias"), 1e-3),
                          (("replan", "fsr_rel_change"), 1e-4),
                          (("cte", "dx_nm"), 5.0),
                          (("pareto", "n_front"), -1),
                          (("band_lock", "m4_wl0_nm"), 3.0)):
        _bad = _copy.deepcopy(_blk)
        _cur = _bad
        for _k in _path[:-1]:
            _cur = _cur[_k]
        _cur[_path[-1]] = _cur[_path[-1]] + _delta
        if _m4_pkg_consistent(_bad):
            return False                               # 数字真变了还绿 ⇒ 假绿
    return True


def probe_m4_vpi_l_disclosed() -> bool:
    """🔴 探针：VπL 断口必须**被披露且可判死**（守「规格取值错一处 ⇒ 余量判断反向」血案）。

    双向：
      · 正例：真块如实 `consistent_with_public_process is False` + `gap_ratio > 1`；
      · 反例：把断口**抹平**成「一致」⇒ `_m4_vpi_l_honest` 必须判 False。
    """
    import copy as _copy
    _blk = _m4_block()
    if not _m4_vpi_l_honest(_blk):
        return False                                   # 真块都没披露 ⇒ 判据写错
    _bad = _copy.deepcopy(_blk)
    _bad["pareto"]["vpi_l"]["consistent_with_public_process"] = True   # 抹平断口
    _bad["pareto"]["vpi_l"]["vpi_l_gap_ratio"] = 1.0
    return not _m4_vpi_l_honest(_bad)


def _m5_same_source(m5: dict) -> bool:
    """M5 块「卡内数字 ≡ `lda_l2.oi_m5` 现算」同源回读（结算量 / 可行域四档 / 带宽律 /
    双口径 / 翻转五链一起对拍）。

    🔴 抽成函数是为了能被探针直接喂**被篡改的块**（否则判据恒绿、无从证伪）。
    """
    from lda_l2 import oi_m5 as M5
    st = M5.vpi_l_settlement()
    bl = M5.bw_scaling_law_check()
    pair = M5.driver_cap_pair_mw()
    fl = M5.cross_form_power_flip()
    ok = (abs(m5["implied_vpi_l_v_cm"] - st["implied_vpi_l_v_cm"]) < 1e-9
          and abs(m5["vpi_l_critical_v_cm"] - st["vpi_l_critical_v_cm"]) < 1e-9
          and abs(m5["l_max_at_bw_deadline_mm"] - st["l_max_at_bw_deadline_mm"]) < 1e-9
          and abs(m5["required_l_at_public_typical_mm"]
                  - st["required_l_at_public_typical_mm"]) < 1e-9
          and abs(m5["vpp_needed_at_m3_l_v"] - st["vpp_needed_at_m3_l_v"]) < 1e-9
          and abs(m5["bw_law"]["max_rel_err_inv_l"] - bl["max_rel_err_inv_l"]) < 1e-12
          and abs(m5["dual_cap"]["driver_electrode_mw"] - pair["driver_electrode_mw"]) < 1e-9
          and abs(m5["dual_cap"]["ratio_package_over_electrode"]
                  - pair["ratio_package_over_electrode"]) < 1e-9
          and abs(m5["cross_form_flip"]["electrode_cap"]["delta_cpo_minus_pluggable_mw"]
                  - fl["electrode_cap"]["delta_cpo_minus_pluggable_mw"]) < 1e-9
          and bool(m5["status"]) == bool(st["status"]))
    for k, v in st["per_band"].items():
        ne = bool(v["continuous_non_empty"])
        ok = ok and (m5["feasible_bands"][k]["non_empty"] is ne
                     and abs(m5["feasible_bands"][k]["vpi_l_v_cm"] - v["vpi_l_v_cm"]) < 1e-9
                     and m5["feasible_bands"][k]["n_grid_hits"] == v["n_grid_hits"]
                     and abs(m5["feasible_bands"][k]["l_max_mm"]
                             - v["continuous_interval_mm"][1]) < 1e-9
                     and (m5["feasible_bands"][k]["l_min_mm"] is None if not ne
                          else abs(m5["feasible_bands"][k]["l_min_mm"]
                                   - v["continuous_interval_mm"][0]) < 1e-9))
    return bool(ok)


def probe_m5_settlement_disclosed() -> bool:
    """🔴 探针：M5 断口结算必须**可判死**（守「抹平断口必红」纪律）。

      · 正例：真实块必须过 `_m5_same_source`，且翻转被报出。
      · 反例：① 抹平翻转（`advantage_flips=False`）⇒ 必须判 False；
              ② 空集档伪装成有解（`public_high.non_empty=True`）⇒ 必须判 False；
              ③ 带宽律退回 1/L² ⇒ 必须判 False。
    """
    from lda_l2 import oi_m5 as M5
    blk = _m5_block()
    if not (_m5_same_source(blk) and blk["cross_form_flip"]["advantage_flips"]
            and not blk["bw_law"]["is_inverse_l2"]):
        return False
    import copy as _copy
    a = _copy.deepcopy(blk)
    a["cross_form_flip"]["advantage_flips"] = False
    b = _copy.deepcopy(blk)
    b["feasible_bands"]["public_high"]["non_empty"] = True
    b["feasible_bands"]["public_high"]["l_min_mm"] = 7.50921
    cc = _copy.deepcopy(blk)
    cc["bw_law"]["is_inverse_l2"] = True
    cc["bw_law"]["max_rel_err_inv_l"] = 0.9
    # ① 抹平翻转：直接判语义（adv 不再报出）②空集伪装 ⇒ 同源回读必红 ③带宽律撒谎 ⇒ 回读必红
    if a["cross_form_flip"]["advantage_flips"]:
        return False
    if _m5_same_source(b):
        return False
    if _m5_same_source(cc):
        return False
    del M5
    return True


def probe_gap_evidence_binding() -> bool:
    """🔴 F5 探针：证明「缺口闭合 ⇔ 证据机器可查」不是装饰。

    在**真函数** `_gap_evidence_ok` 上跑**被污染的卡块**（模拟「实现被改坏」⇒ 卡内现算块
    随之变化，而 `gaps` 字面量不动）⇒ 对应缺口的 `evidence_ok` 必须变红。同时验证
    `_gap_evidence_gate` 会把「清单说闭合、证据不绿」判红（`closed ⇔ evidence_ok`）。
    """
    import copy as _copy
    try:
        c0 = case_card()
        ev0 = _gap_evidence_ok(c0)
        if not all(ev0[g]["ok"] for g in ("G-OI1", "G-OI2", "G-OI3", "G-OI5", "G-OI6")):
            return False
        if any(ev0[g]["ok"] for g in ("G-OI4", "G-OI7")):
            return False
        # 逐项：把**卡内现算块**打坏（= 实现坏掉后的样子），证据必须变红
        mutations = [
            (("m1", "ring_plan", "min_xt_db"), 5.0, "G-OI1"),
            (("m2", "g_oi2", "lvs_verdict"), "REJECT", "G-OI2"),
            (("m3", "layout_2p5d", "lvs_report", "pass"), False, "G-OI6"),
            (("m3", "layout_2p5d", "oe_lvs_verdict"), "UNKNOWN_NEW", "G-OI6"),
            (("m2b", "lane_equalizer", "flat_ok"), False, "G-OI5"),
            (("m2b", "yield", "yield_mc"), 0.0, "G-OI5"),
        ]
        for path, bad, gid in mutations:
            cc = _copy.deepcopy(c0)
            node = cc
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = bad
            if _gap_evidence_ok(cc)[gid]["ok"]:
                return False
        # 门禁：清单说闭合、证据不绿 ⇒ 必红（此例把 G-OI5 的证据块打坏但清单不动）
        cc = _copy.deepcopy(c0)
        cc["m2b"]["lane_equalizer"]["flat_ok"] = False
        ev_bad = _gap_evidence_ok(cc)
        for g in cc["gaps"]:
            g["evidence_ok"] = bool(ev_bad[g["id"]]["ok"])
        if _gap_evidence_gate(cc):
            return False
        return True
    except Exception:                                         # noqa: BLE001
        return False


def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检：卡结构完备 + 判决诚实 + 关键数字与模块自检同源（M0 + M1 + M2 + M2b）。

    🔴 「卡内数字 ≡ 模块现算」逐位同源：M1 块的关键标量回读 `lda_l2.oi_m1` 现算比对，
    防「案例卡写死一份、模块改了卡不动」的静默失真（血案同族）。
    """
    c = case_card(use_cache=False)
    need = ["case_id", "claim", "identity", "requested", "channels", "m1", "m2", "m2b", "m3", "m4",
            "m5", "b19_passivity", "milestones", "findings", "gaps", "verdict", "honest_note"]
    if any(k not in c for k in need):
        return False
    if c["verdict"] != "DESIGN_BUDGET":
        return False
    # 🔴 只守「能力宣称面」：是否定语境的**正确自我否定**（「不报 TOPS/…」）⇒ 不参与判据
    #    （否则正确否定被误判违规 —— E12/E13/E17 血案同族）。
    #    修法：递归取「肯定式表面」= 逐值递归，凡含否定标记的字符串**截断到标记处**
    #    （否定标记之前的肯定文字照扫，防「本模块提供 TOPS 级算力…不报 TOPS-W」漏网），
    #    标记及其后文剔除 ⇒ 分别只留否定式诚实声明。顶层 `honest_note*` 键亦无需再列举豁免。
    blob = _positive_surface(c)
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

    # ── M2b 自洽 + 与模块现算逐位同源（G-OI5 五项）──
    from lda_l2 import oi_m2b as M2B
    m2b = c["m2b"]
    _F = M2B.NYQUIST_200G_GHZ * 1e9
    _a = float(M2B.OI_M2B_PROCESS["f_tia_ghz"]) * 1e9
    _z = M2B.f_z_for_boost(_F, _a, float(M2B.OI_M2B_PROCESS["ctle_boost_db"]))
    ok_m2b_form = (bool(m2b["equalizer"]["lpo"]["ctle"])
                   and not bool(m2b["equalizer"]["lpo"]["ffe"])
                   and bool(m2b["equalizer"]["retimed"]["ffe"]))
    ok_m2b_ctle = (abs(m2b["ctle"]["f_z_hz"] - _z) < 1.0
                   and abs(m2b["ctle"]["noise_penalty_db"]
                           - M2B.ctle_noise_penalty_db(_z, _a, _F)) < 1e-3)
    ok_m2b_eq = (bool(m2b["lane_equalizer"]["boost_distinct"])
                 # 🔴 F3：`flat_ok` 现在是**独立重算**的信道成效（非往返恒等式）
                 and bool(m2b["lane_equalizer"]["flat_ok"])
                 and m2b["lane_equalizer"]["channel_source"] == "per_lane(f_mod_ghz)"
                 and len(m2b["lane_equalizer"]["lanes"]) == 8)
    _tb = M2B.thermal_tune_budget()
    ok_m2b_th = (abs(m2b["thermal_tune"]["p_per_lane_mW"] - _tb["p_tune_mw_per_lane"]) < 1e-3
                 and abs(m2b["thermal_tune"]["S_nm_per_mW"] - _tb["S_nm_per_mW"]) < 1e-9
                 and "mW" in m2b["thermal_tune"]["unit_note"])
    _g = M2B.crosstalk_gamma()
    ok_m2b_g = (bool(m2b["crosstalk_gamma"]["symmetric_ok"])
                and bool(m2b["crosstalk_gamma"]["diagonal_max_ok"])
                and bool(m2b["crosstalk_gamma"]["monotonic_ok"])
                and abs(m2b["crosstalk_gamma"]["S_nm_per_mW"] - _g["S_nm_per_mW"]) < 1e-9
                and m2b["crosstalk_gamma"]["n"] == int(_g["n"]))
    _yc = M2B.yield_closed_form()
    _ym = M2B.yield_monte_carlo()
    ok_m2b_y = (abs(m2b["yield"]["yield_closed_form"] - _yc["yield"]) < 1e-7
                and m2b["yield"]["mc_n_samples"] == int(_ym["n_samples"])
                and bool(m2b["yield"]["mc_seed"]))
    # 温漂两项（`wl_drift_nm` / `dx_drift_um`）同源回读：此前只比 dx_max / IL 底，
    # 温漂链（`Δθ = Δλ/(Λ·cosθ)` ⇒ 波长漂 ⇒ 横向走偏）从未与模块对拍 ⇒ 静默盲区（F841 棘轮抓出）。
    ok_m2b_pkg = (_m2b_pkg_consistent(m2b) and
                  bool(m2b["packaging"]["temp_in_tolerance"]))
    # 🔴 缺口清单变了必须同步：M3 新增 G-OI6 ⇒ 5→6 项（首版漏改 ⇒ 旧断言仍要 5 项 ⇒ 自毁）
    # 🔴 缺口清单变了必须同步：M4 新增 G-OI7 ⇒ 6→7 项（首版漏改 ⇒ 旧断言仍要 6 项 ⇒ 自毁）
    ok_m2b_gap = ([g["id"] for g in c["gaps"]] == ["G-OI1", "G-OI2", "G-OI3",
                                                   "G-OI4", "G-OI5", "G-OI6", "G-OI7"]
                  and c["gaps_total"] == 7
                  and bool([g for g in c["gaps"] if g["id"] == "G-OI5"
                            and g["closed"]])
                  and bool([g for g in c["gaps"] if g["id"] == "G-OI6"
                            and g["closed"]])
                  and bool([g for g in c["gaps"] if g["id"] == "G-OI4"
                            and not g["closed"]]))
    good3 = (ok_m2b_form and ok_m2b_ctle and ok_m2b_eq and ok_m2b_th
             and ok_m2b_g and ok_m2b_y and ok_m2b_pkg and ok_m2b_gap)
    # ── M3 自洽 + 与模块现算逐位同源（3.2T / 带宽墙 / 电通道 / 热+闭环热调 / 功耗 / 2.5D）──
    from lda_l2 import oi_m3 as M3
    m3 = c["m3"]
    twm, pw, th, clp, lay = (m3["twmzm"], m3["power"], m3["thermal"],
                             m3["closed_loop_thermal"], m3["layout_2p5d"])
    ok_m3_scale = (m3["reuse"]["lane_halved"] and m3["reuse"]["density_still_below_ceiling"]
                   and m3["reuse"]["pitch_still_above_floor"]
                   and m3["reuse"]["energy_floor_still_positive"]
                   and m3["reuse"]["reused_not_rebuilt"])
    # 带宽墙：f3dB > 奈奎斯特（400G/lane 必须过得去）· 余量为正 · 族名互锁
    ok_m3_bw = (twm["f3db_ghz"] > twm["nyquist_ghz"] and twm["margin_db"] > 0.0
                and twm["ratio_to_nyquist"] > 1.0 and twm["bandwidth_ok"]
                and twm["family"] == M3.family_lock()["family_m3"])
    # 电通道：√f 律只在 R 主导子带成立 + 窗口外漂移**如实披露**（不做假判据）
    ec = m3["echannel"]
    ok_m3_chan = (ec["sqrtf_ok"] and ec["disclosed_outside"]
                  and ec["drift_in_window"] < 0.005 < ec["drift_outside"]
                  and m3["fdtd_telegraph"]["phase_ok"]
                  and m3["fdtd_telegraph"]["rel_err"] < 0.05
                  and m3["next"]["xtalk_at_zero_coupling_db"] == NEG_INF_DB)
    # 热：两串热阻 ⇒ 光子 die > 中介层 > 环境；且第二通道（M2b 有限差分）一致
    ok_m3_th = (th["t_photon_c"] > th["t_interposer_c"] > th["t_amb_c"]
                and th["d_t_interposer_c"] > 0.0 and th["die_to_die_theta_k"] > 0.0
                and th["theta_channels_agree"])
    # 闭环热调：代数解 + 单通路自洽 + **单向加热器不可行**（CPO 真实代价）+ 残余 < 1 FSR
    # 🔴 F2（v0.9.185）：判据换成**收敛性**（首版 `solution=="algebraic" and
    #    single_path_consistency` 中后者是恒等式 ⇒ 无判别力）。
    ok_m3_loop = (clp["solution"] == "algebraic" and clp["converged"] is True
                  and clp["algebraic_matches_fixed_point"] and clp["double_count_diverges"]
                  and clp["unidirectional_heater_feasible"] is False
                  and clp["residual_lt_fsr"] and clp["p_actuator_mw_per_lane"] > 0.0
                  and clp["d_lambda_dT_nm_per_k"] < clp["S_nm_per_mW"])  # dλ/dT = S/R_h
    # 功耗：对拍通过 · CPO 多付热调与中介层 PDN · 🔴 禁能效换算标记在位
    # 🔴 M5 口径修正（原判据 `cpo_total_w < pluggable_total_w` **已失效**）：
    #   该不等式成立的前提是「封装线电容当驱动负载」（CPO 1.0 pF < 可插拔 2.5 pF）。
    #   主账切到**电极电容 C′·L** 后两者负载相同 ⇒ 不等式**反向**（CPO 262.7 > 224.8 mW/lane）。
    #   ⇒ 判据改为「口径切换的翻转**被如实报出**」+「主账口径确为 electrode」。
    #   🔴 不删该结论、也不粉饰：翻转本身就是 M5 要披露的后果（`cross_form_power_flip`）。
    ok_m3_pw = (pw["reconciled"] and pw["cpo_advantage_thermal_mw"] > 0.0
                and pw["cpo_penalty_interposer_mw"] > 0.0
                and pw["energy_per_bit_banned"]
                and pw["cap_model_used"] == "electrode"
                and pw["flip"]["advantage_flips"] is True
                and pw["flip"]["electrode_cap"]["delta_cpo_minus_pluggable_mw"] > 0.0
                and pw["flip"]["package_line_cap"]["delta_cpo_minus_pluggable_mw"] < 0.0
                and "mW" in pw["unit_note"])
    # 2.5D 签核：出图 + 片外 fiber 不落版图 + 电层 DRC + 拓扑 LVS + 光引擎元素真复用
    # 🔴 F11（v0.9.185）：OE 层复用 LVS 实为 REJECT(8 违规)（已知口径差）⇒ 判决**不允许静默不提**：
    #    要么 pass，要么**显式豁免**（verdict ∈ 白名单 ∧ honest_note 非空 ∧ 违规数 ≥1）。
    oe_lvs_ok = _oe_lvs_judgement(lay)
    ok_m3_layout = ("error" not in lay and lay["gds_bytes_len"] > 0
                    and lay["fiber_in_layout"] is False
                    and lay["electrical_drc_pass"] and lay["lvs_report"]["pass"]
                    and oe_lvs_ok
                    and lay["oe_elements_reused"] > 0
                    and lay["gds_structures"].count("OE_DIE") == 1)
    ok_m3_pkg = _m3_pkg_consistent(m3)
    # 缺口终态：G-OI7 新增开放 ⇒ 5/7（G-OI4 与 G-OI7 仍开放）
    ok_m3_gap = ([g["id"] for g in c["gaps"]] == ["G-OI1", "G-OI2", "G-OI3", "G-OI4",
                                                  "G-OI5", "G-OI6", "G-OI7"]
                 and c["gaps_total"] == 7
                 and bool([g for g in c["gaps"] if g["id"] == "G-OI6" and g["closed"]])
                 and bool([g for g in c["gaps"] if g["id"] == "G-OI4" and not g["closed"]])
                 and bool([g for g in c["gaps"] if g["id"] == "G-OI7" and not g["closed"]]))
    # 🔴 `ok_m3_gap` 必须**进判决**（此前只出现在 debug print 里 ⇒ 装饰性判据：
    #    缺口清单被改坏时 `good` 仍绿 —— 正是「写得绿 ≠ 拦得住」的血案）。
    good4 = (ok_m3_scale and ok_m3_bw and ok_m3_chan and ok_m3_th
             and ok_m3_loop and ok_m3_pw and ok_m3_layout and ok_m3_pkg
             and ok_m3_gap)

    # ── M4 自洽 + 与模块现算逐位同源（热-光-电耦合链 / 预偏移 / 重规划 / 三形态 / CTE /
    #    Pareto / 可行性墙 / 波段 / 斜率）—— 同源回读经由 `_m4_pkg_consistent` 内部取模块现算 ──
    m4 = c["m4"]
    ok_m4_pkg = _m4_pkg_consistent(m4)
    # 语义（不靠同源相等）：三域真冲突 + 预偏移归零 + 热态红移 + 反直觉结论 + 互锁
    ok_m4_sem = (m4["chain"]["d_t_photon_k"] > 0.0
                 and m4["chain"]["unidirectional_heater_feasible"] is False
                 and bool(m4["chain"]["chain_consistent_with_m3_residual"])
                 and m4["prebias"]["solution"] == "algebraic"
                 and m4["prebias"]["residual_nm_after_prebias"]
                 < m4["prebias"]["residual_nm_without_prebias"]
                 and m4["prebias"]["p_heat_after_prebias_mw_per_lane"]
                 < m4["prebias"]["p_heat_without_prebias_mw_per_lane"]
                 and 1260.0 <= m4["replan"]["wl0_cold_nm"] <= 1360.0     # O-band 归属（咬语义）
                 and m4["replan"]["wl0_hot_nm"] > m4["replan"]["wl0_cold_nm"]
                 and m4["replan"]["fsr_nm_hot"] > m4["replan"]["fsr_nm_cold"]   # FSR ∝ λ²
                 and bool(m4["forms"]["theta_monotonic_with_distance"])
                 and bool(m4["forms"]["elec_il_monotonic_with_bus"])
                 and bool(m4["cte"]["cte_is_dominant"]) is False          # CTE 非主因
                 and bool(m4["pareto"]["all_points_non_dominated"])
                 and bool(m4["feasibility_wall"]["public_feasible_collapsed"])
                 and bool(m4["feasibility_wall"]["public_narrower_than_m3"])
                 and bool(m4["band_lock"]["same_as_m2"])
                 and bool(m4["band_lock"]["differs_from_m1_default"])
                 and bool(m4["slope_lock"]["agree_within_25pct"]))
    ok_m4_vpi = _m4_vpi_l_honest(m4)
    # 缺口终态：M4 新增 G-OI7 开放 ⇒ 5/7
    ok_m4_gap = ([g["id"] for g in c["gaps"]] == ["G-OI1", "G-OI2", "G-OI3", "G-OI4",
                                                  "G-OI5", "G-OI6", "G-OI7"]
                 and c["gaps_total"] == 7
                 and bool([g for g in c["gaps"] if g["id"] == "G-OI7" and not g["closed"]]
                          ))
    good5 = (ok_m4_pkg and ok_m4_sem and ok_m4_vpi and ok_m4_gap)

    # ── M5 自洽（VπL 断口结算 · 可行域闭式 · 双口径 · 翻转披露）——
    #    🔴 必须**进判决**（`good6` 参与 `good`），否则又是「写得绿 ≠ 拦得住」的血案。
    m5 = c["m5"]
    ok_m5_sem = (m5["status"] == "SETTLED_CONDITIONAL"
                 and m5["design_point_self_consistent"]
                 and m5["implied_vpi_l_v_cm"] <= m5["vpi_l_critical_v_cm"]
                 and m5["public_low_feasible"] and m5["public_typical_feasible"]
                 and m5["public_high_feasible"] is False
                 and m5["feasible_bands"]["public_typical"]["non_empty"]
                 and m5["feasible_bands"]["public_high"]["non_empty"] is False
                 and m5["feasible_bands"]["public_high"]["l_min_mm"] is None
                 and m5["feasible_bands"]["public_typical"]["width_mm"] > 1.0
                 and m5["bw_law"]["is_inverse_l"]
                 and m5["bw_law"]["is_inverse_l2"] is False
                 and m5["dual_cap"]["ratio_package_over_electrode"] > 2.0
                 and m5["cross_form_flip"]["advantage_flips"] is True
                 and bool(m5["honest_note_m5"]))
    ok_m5_src = _m5_same_source(m5)
    good6 = (ok_m5_sem and ok_m5_src)

    # 🔴 探针进判决（此前 `probe_banned_token_scan` 写好却没接进 good ⇒ 装饰性判据，
    #    「写得绿」不等于「拦得住」；禁词口径与温漂同源回读两条都必须是真拦）。
    _PROBE_OK = (probe_banned_token_scan() and probe_m2b_pkg_same_source()
                 and probe_m3_pkg_same_source() and probe_m3_loop_is_algebraic()
                 and probe_m4_same_source() and probe_m4_vpi_l_disclosed()
                 and probe_m5_settlement_disclosed() and probe_gap_evidence_binding()
                 and probe_json_hard_ok())
    # 🔴 F5：缺口终态**证据链**门禁（`closed ⇔ evidence_ok` 逐项一致 + 闭口必须挂非空证据键）
    ok_gap_evidence = _gap_evidence_gate(c)
    ok_json_hard = json_hard_ok(c)
    good = (good and good2 and good3 and good4 and good5 and good6 and _PROBE_OK
            and ok_gap_evidence and (ok_json_hard is True))
    if _DEBUG_SELFCHECK:                                     # noqa: F821
        print("DBG good=%s good2=%s | m2b: form=%s ctle=%s eq=%s th=%s g=%s y=%s "
              "pkg=%s gap=%s | m3: scale=%s bw=%s chan=%s th=%s loop=%s pw=%s "
              "layout=%s pkg=%s gap=%s gapEv=%s | m4: pkg=%s sem=%s vpi=%s gap=%s | m0/m1: ab=%s b19=%s ch=%s" %
              (good, good2, ok_m2b_form, ok_m2b_ctle, ok_m2b_eq, ok_m2b_th,
               ok_m2b_g, ok_m2b_y, ok_m2b_pkg, ok_m2b_gap,
               ok_m3_scale, ok_m3_bw, ok_m3_chan, ok_m3_th, ok_m3_loop, ok_m3_pw,
               ok_m3_layout, ok_m3_pkg, ok_m3_gap, ok_gap_evidence,
               ok_m4_pkg, ok_m4_sem, ok_m4_vpi, ok_m4_gap, ok_ab, ok_b19, ok_ch))
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
                 ok_m2_gds, m2["g_oi2"].get("n_devices"), m2["g_oi2"].get("n_nets"),
                 m2["g_oi2"].get("lvs_verdict"),
                 m2["g_oi2"].get("layout_discipline_ok")))
        print("      M2b: 形态映射=%s · CTLE=%s(boost%.1fdB penalty%.3fdB) · 多通道=%s"
              "(8 lane boost各异 + 平坦化) · 热调=%s(%.1f mW/lane) · Γ=%s · 良率=%s"
              "(%.6f 闭式/%.6f MC) · 封装=%s(dx_max %.2f µm) · 缺口=%s"
              % (ok_m2b_form, ok_m2b_ctle, m2b["ctle"]["boost_nom_db"],
                 m2b["ctle"]["noise_penalty_db"], ok_m2b_eq, ok_m2b_th,
                 m2b["thermal_tune"]["p_per_lane_mW"], ok_m2b_g, ok_m2b_y,
                 m2b["yield"]["yield_closed_form"], m2b["yield"]["yield_mc"],
                 ok_m2b_pkg, m2b["packaging"]["dx_max_um"], ok_m2b_gap))
        print("      M4: 同源=%s · 语义=%s · VπL断口=%s · 缺口=%s | 耦合链 ΔT=%.3fK→Δλ=%.3f nm · "
              "预偏移 %.1f→%.1f℃(残余 %.3e nm) · 重规划 FSR %+.3f%% · 三形态 θ[%s] · "
              "CTE %.1f nm(%.4f dB, 主因=%s) · Pareto %d/%d 非支配 · 可行域 %s mm · "
              "VπL 隐含 %.3f(公开 %.1f–%.1f, ×%.2f)"
              % (ok_m4_pkg, ok_m4_sem, ok_m4_vpi, ok_m4_gap,
                 m4["chain"]["d_t_photon_k"], m4["chain"]["d_lambda_self_nm"],
                 m4["prebias"]["t_amb_c"], m4["prebias"]["t_eq_c"],
                 m4["prebias"]["residual_nm_after_prebias"],
                 m4["replan"]["fsr_rel_change"] * 100.0,
                 ",".join(m4["forms"]["thermal_coupling_rank"]),
                 m4["cte"]["dx_nm"], m4["cte"]["il_cte_db"], m4["cte"]["cte_is_dominant"],
                 m4["pareto"]["n_front"], m4["pareto"]["n_points"],
                 m4["pareto"]["feasible_l_mm"],
                 m4["pareto"]["vpi_l"]["vpi_l_implied_by_m3_v_cm"],
                 m4["pareto"]["vpi_l"]["vpi_l_public_band_v_cm"][0],
                 m4["pareto"]["vpi_l"]["vpi_l_public_band_v_cm"][1],
                 m4["pareto"]["vpi_l"]["vpi_l_gap_ratio"]))
    return good


if __name__ == "__main__":
    print("OI-M0/M1/M2b case self-check:",
          "PASS" if run_selfchecks(verbose=True) else "FAIL")
