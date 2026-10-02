# -*- coding: utf-8 -*-
"""LDA WebUI · 光联接模块案例卡（M0 双通道基线 + M1 800G 预算 · 只读案例）。

============================================================================
A 档接入（对齐 qchip/schip/pchip/ecore/accel/d4 案例卡体例）
----------------------------------------------------------------------------
把「光联接模块新征程」以**只读案例**呈现：
  · **M0**：2 通道 WDM 收发器基线（Tx MZI 调制器阵列 + Rx 微环 add-drop 滤波阵列 +
    双 GratingCoupler + 光纤 span）—— 功率/链路预算层。
  · **M1**：在其上补 **频域（级联 EO S21 / −3dB 带宽）** 与 **时域（PAM4 三眼 / Q /
    链路预算级 BER / 光纤色散 / 驱动-TIA 协同）**，并给出**梳齿规避信道规划**
    （8 通道隔离 −0.85dB → 39.5dB 的根因与解）。

🔴 只读与缓存纪律：结果为**确定性现算**（纯闭式 + 级联引擎 + IFFT 时域 + 几何搜索，
零重计算 / 不跑 P&R / 不跑 FDTD），首次调用后按配置键**模块级缓存**（同配置秒回）。
不进 HEAVY_POST_PATHS、不要求登录（与 qchip/schip/pchip/ecore/accel/d4 同属
「公开只读验货」类）。

🔴 不伪装实测：`verdict` 恒为 `DESIGN_BUDGET`（非 ACCEPT/PASS）——链路/带宽预算是
设计期行为验证，非流片后实测；**不报 TOPS/TOPS-W/fJ/op**。

🔴 诚实边界：M0/M1 均为**设计预算层**（器件用 L0 级解析模型 + A 档闭式/行为级）；
M1 的 BER 是**光通道预算级**闭式估计（不含 SerDes/DSP/FEC/均衡/CDR，与
`eic_behavioral.EIC_DISCLOSURE` 的 EIC 电路级排除**显式分层**），接受 SNR 为
**设计输入假设**；真实版图 GDS 由 D4 域 `photonic_interconnect`（复用
`wdm_mesh_pnr`）单独承载 —— 本卡只报预算。
"""
from __future__ import annotations

CASE_ID = "OI-M0/M1 · 光联接模块（M0 双通道基线 + M1 800G 频域/时域预算）"

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
        "claim": ("用 LDA 自家光链路设计验证链（lda_chain + lda_l2.oi_m1）可把一款 WDM 收发器"
                  "从装配一路推进到**800G（8×100G PAM4）频域/时域预算**：闭式预算与级联引擎"
                  "两种方法逐位一致（差 <0.05dB），且吃狗粮过程**抓出并修复了 4 处平台级缺陷**"
                  "（星型网级联重复计数 · 环区数硬编码 · FSR 目标单位错 · KP4 门限口径差 100×），并**补齐了"
                  "「梳齿规避信道规划」这一平台此前不具备的能力**"),
        "identity": {
            "topology": "Tx：MZI 调制器（cos² 传递）× N 通道；Rx：微环 add-drop 滤波器"
                        "级联下路 + 双 GratingCoupler 耦合 + 光纤 span",
            "method": "两种方法独立交叉验证——(A) 闭式链路预算（含前置环 thru 总线链）"
                      "；(B) lda_chain 级联引擎（信号流图精确信道波长评估）",
            "method_m1": "M1 在功率预算之上补**频域**（级联 EO S21：调制器 RC+渡越 × 探测器"
                         "τ=RC × TIA 单极点）与**时域**（PAM4 符号间隔抽头 → 三眼 / Q / BER；"
                         "高斯色散展宽闭式 ⟷ 时域仿真对拍）两维",
            "anchor_B19": "无源无增益不等式 |T|≤1（所有 transfer 幅值 ≤1），M0/M1 全部满足",
            "honest_layer": "M0/M1 均属设计预算层（L0 解析器件模型 + A 档闭式/行为级）；真实版图"
                            " GDS 由 D4 域 photonic_interconnect（复用 wdm_mesh_pnr）承载",
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
        ],
        "gaps": [
            {"id": "G-OI1", "closed": True,
             "title": "相邻信道隔离（M1 已闭合：−0.85dB → 39.5dB）",
             "detail": "靠**梳齿规避信道规划**（m=129 / gap=0.55µm，最小梳齿偏移 1.24nm）闭合；"
                       "新增平台能力 `oi_m1.plan_lwdm_channels`（搜索解与设计常量由门禁互锁）"},
            {"id": "G-OI2", "closed": False,
             "title": "M0/M1 收发器拓扑尚无专用真 GDS 版图 builder",
             "detail": "本卡是链路预算层；平台已有 D4 域 photonic_interconnect（复用 wdm_mesh_pnr"
                       "的 K×N WDM 网格 P&R，真 GDS+DRC+LVS），但「N 调制器+N 环+2GC+光纤」"
                       "这一具体拓扑的专用 layout builder 仍是缺口，须后续补（不重造既有单元）"},
            {"id": "G-OI3", "closed": True,
             "title": "级电光行为模型（M1 已闭合四项）",
             "detail": "EO S21 带宽（G-OI3-a）· 眼图/BER（G-OI3-b，光链路预算级 + 与 EIC 电路级"
                       "显式分层）· 驱动-TIA 协同（G-OI3-c，复用 eic_behavioral）· 光纤色散"
                       "（G-OI3-d）四子项全部落地，见 `lda_l2/oi_m1.py`"},
            {"id": "G-OI4", "closed": False,
             "title": "电路级模型 · 无 PDK · 不报 TOPS",
             "detail": "继承主权红线：无 foundry 数据 ⇒ 无能效宣称资格；规模与能效外推属 T2 锁死区"},
        ],
        "gaps_closed": 2,
        "gaps_total": 4,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "链路预算设计行为验证口径（确定性现算 · 非流片实测 · 非实测签核）",
        "honest_note": ("🔴 本卡为只读案例：数字由确定性现算（闭式 + lda_chain 级联引擎 + "
                        "oi_m1 IFFT 时域 + 几何搜索，零重计算 · 免登录 · 不跑 P&R/FDTD）；"
                        "M0/M1 均属**设计预算层**（L0 解析器件模型 / A 档闭式行为级），真实版图 GDS "
                        "由 D4 域 photonic_interconnect 承载；M1 的 BER 是**光通道预算级**闭式估计"
                        "（不含 SerDes/DSP/FEC/均衡/CDR），接受 SNR 为**设计输入假设**；"
                        "不报 TOPS/TOPS-W/fJ/op；判决由死标量给出，LLM 不进判决路径。"),
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
    need = ["case_id", "claim", "identity", "requested", "channels", "m1", "b19_passivity",
            "milestones", "findings", "gaps", "verdict", "honest_note"]
    if any(k not in c for k in need):
        return False
    if c["verdict"] != "DESIGN_BUDGET":
        return False
    # 🔴 只守「能力宣称面」：`honest_note` / `honest_note_m1` 是否定语境的**正确自我否定**
    #    （「不报 TOPS/…」）⇒ 不参与判据（否则正确否定被误判违规 —— E12/E13/E17 血案同族）。
    _surf = {k: v for k, v in c["m1"].items() if k != "honest_note_m1"}
    blob = repr(c["claim"]) + repr(c["identity"]) + repr(c["requested"]) + repr(_surf)
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
    if verbose:
        print("[%s] OI-M0/M1 case_card · 通道=%d · 闭式≡级联=%s · B19=%s"
              % ("PASS" if good else "FAIL", len(c["channels"]), ok_ab, ok_b19))
        print("      M1: 800G=%s · 隔离=%s(%.1fdB vs M0默认 %.2fdB) · 规划=%s · 设计点=%s · "
              "修复=%s · 裕量=%s(%.2fdB)"
              % (ok_agg, ok_iso, m1["worst_isolation_db"],
                 m1["ring_plan"]["m0_default_min_xt_db"], ok_plan, ok_exp, ok_fix,
                 ok_margin, m1["snr_margin_db"]))
    return good


if __name__ == "__main__":
    print("OI-M0 case self-check:", "PASS" if run_selfchecks(verbose=True) else "FAIL")
