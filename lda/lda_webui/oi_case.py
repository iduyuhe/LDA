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

CASE_ID = ("OI-M0/M1/M2/M2b · 光联接模块（M0 双通道基线 + M1 800G 频域/时域 + "
           "M2 1.6T·LPO·G-OI2 真 GDS + M2b 均衡/热调/热串扰/良率/封装 G-OI5）")

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

    🔴 数字**全部现算**（不写死）：与 `lda/run_oi_m2b_smoke.py` 的 85 判据同源同一份
    `lda_l2.oi_m2b`，卡内只是**呈现层**，`run_selfchecks` 再回读比对防静默失真。

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
            "flat_after_equalization_db": round(float(des["total_gain_spread_db"]), 12),
            "flat_ok": bool(des["flat_after_equalization"]),
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
                     "**有限差分热网络**（网格加密相对误差单调下降）。"),
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
        "method_m2b": "M2b 把**设计 ⟷ 版图 ⟷ 工艺 ⟷ 封装**四层咬成闭环：(均衡) 逐 lane CTLE "
                      "抽头（各 lane 工艺离散 ⇒ 目标 boost 不同 ⇒ 均衡后总增益拉平）+ "
                      "形态↔均衡映射（LPO 无 DSP ⇒ 只有模拟 CTLE，不能 FFE）；(热) 热调 "
                      "Pπ 进链路（只报 mW）+ 热串扰 Γ 矩阵（**坐标取自真版图 placement**，"
                      "互易/单调/对角最大三条物理律 + 有限差分热网络第二通道）；"
                      "(工艺/封装) 工艺偏差→良率（golden 闭式 Φ ⟷ MC 第二通道）、"
                      "封装容差（对准 IL 预算先扣模场失配底 + GC 出射角温漂真物理）",
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
            "m2b": _m2b_block(),
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
            {"id": "G-OI5", "closed": True,
             "title": "M2b 已闭合：多通道均衡 · 热调 · 热串扰 Γ · 良率 MC · 封装容差",
             "detail": "五项全部落地（`lda_l2/oi_m2b.py` + 门禁 `run_oi_m2b_smoke.py` 85 判据 / "
                       "8 探针 + 模块自检 29 项）：① 多通道 CTLE（逐 lane 抽头，工艺离散 ±3% ⇒ "
                       "目标 boost 各异 ⇒ 均衡后总增益拉平，spread<1e-15 dB）+ **形态↔均衡映射**"
                       "（LPO 无 DSP ⇒ 只有模拟 CTLE、不能 FFE，探针 P3 守）；② 热调 Pπ 进链路"
                       "（只报 mW，不做能效比）；③ Γ 矩阵**版图绑定**（坐标取真版图 placement，"
                       "互易/单调/对角最大 + 有限差分热网络第二通道）；④ 工艺偏差→良率"
                       "（golden 闭式 Φ ⟷ MC N=20000 固定 seed 第二通道）；⑤ 封装容差"
                       "（对准 IL 预算先扣模场失配底 + GC 出射角温漂真物理）。"
                       "与 G-OI4 合并考虑后，G-OI4「电路级模型 · 无 PDK · 不报 TOPS」**仍开放**"},
        ],
        "gaps_closed": 4,
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


def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检：卡结构完备 + 判决诚实 + 关键数字与模块自检同源（M0 + M1 + M2 + M2b）。

    🔴 「卡内数字 ≡ 模块现算」逐位同源：M1 块的关键标量回读 `lda_l2.oi_m1` 现算比对，
    防「案例卡写死一份、模块改了卡不动」的静默失真（血案同族）。
    """
    c = case_card(use_cache=False)
    need = ["case_id", "claim", "identity", "requested", "channels", "m1", "m2", "m2b",
            "b19_passivity", "milestones", "findings", "gaps", "verdict", "honest_note"]
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
                 and bool(m2b["lane_equalizer"]["flat_ok"])
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
    ok_m2b_gap = ([g["id"] for g in c["gaps"]] == ["G-OI1", "G-OI2", "G-OI3",
                                                   "G-OI4", "G-OI5"]
                  and bool([g for g in c["gaps"] if g["id"] == "G-OI5"
                            and g["closed"]])
                  and bool([g for g in c["gaps"] if g["id"] == "G-OI4"
                            and not g["closed"]]))
    good3 = (ok_m2b_form and ok_m2b_ctle and ok_m2b_eq and ok_m2b_th
             and ok_m2b_g and ok_m2b_y and ok_m2b_pkg and ok_m2b_gap)
    # 🔴 探针进判决（此前 `probe_banned_token_scan` 写好却没接进 good ⇒ 装饰性判据，
    #    「写得绿」不等于「拦得住」；禁词口径与温漂同源回读两条都必须是真拦）。
    _PROBE_OK = probe_banned_token_scan() and probe_m2b_pkg_same_source()
    good = good and good2 and good3 and _PROBE_OK
    if _DEBUG_SELFCHECK:                                     # noqa: F821
        print("DBG good=%s good2=%s | m2b: form=%s ctle=%s eq=%s th=%s g=%s y=%s "
              "pkg=%s gap=%s | m0/m1: ab=%s b19=%s ch=%s" %
              (good, good2, ok_m2b_form, ok_m2b_ctle, ok_m2b_eq, ok_m2b_th,
               ok_m2b_g, ok_m2b_y, ok_m2b_pkg, ok_m2b_gap, ok_ab, ok_b19, ok_ch))
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
    return good


if __name__ == "__main__":
    print("OI-M0/M1/M2b case self-check:",
          "PASS" if run_selfchecks(verbose=True) else "FAIL")
