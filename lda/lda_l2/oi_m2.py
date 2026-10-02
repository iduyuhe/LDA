# -*- coding: utf-8 -*-
"""LDA 光联接模块征程 · M2（1.6T 收发器 · 200G/lane · LPO 无 DSP 线性形态）。

M0 = 链路预算（功率）；M1 = 频域 + 时域（800G）；**M2 = 规模 × 形态 × 物理落地**：
把每通道速率从 100G 翻到 **200G（106.25 GBd PAM4，1.6T = 8×200G）**，并补上两个
此前完全空白的维度：

  · **形态维（LPO）**：Linear Pluggable Optics = **模块内无 DSP**（host SerDes 直接
    驱动）。这不是免责声明，而是**设计约束** —— 级联 FEC 的内码（Hamming/BCH(128,120)）
    在**模块 DSP 内**实现 ⇒ LPO 拿不到内码增益 ⇒ pre-FEC 门限从 **4.8e-3 退回 2.4e-4**
    ⇒ 所需 SNR 收紧 **2.744 dB**（闭式 Q 函数差，见 `lpo_inner_code_gain_db`）。
  · **物理落地维（G-OI2）**：该收发器拓扑的**专用真 GDS builder**
    （`lda_layout/oi_transceiver_pnr.py`）—— 由本模块给出**设计参数与波长栅**，
    builder 产出可签核版图，经 D4 域 `oi_transceiver` 对外交付。

🔴 吃狗粮发现（本模块量化 · 平台短板）：
  M1 的 100G 档器件常量（EO f_3dB **32.94 GHz**）在 200G/lane 下 **< 奈奎斯特
  **53.125 GHz**（缺 20.2 GHz）⇒ 眼被 ISI 闭合、所需 SNR 不可达。这是**「性能升级」
  暴露的真短板**：不是把通道数乘 2 就完事，器件带宽必须整体重标定。

🔴 诚实边界（红线 `docs/lda_active_device_redline_clarification_2026-09-10.md` §四 A 档）：
  · 全部为 **闭式物理律 / 行为级**（A 档）：不碰电-光耦合增益真值（T2 锁）· 不用 A 级商业工具 · 不流片。
  · 🔴 **BER = 光链路预算级闭式估计**（golden = 闭式 Q 函数 `0.375·erfc(Q/√2)`），**不含**
    SerDes / DSP / FEC 编解码 / 均衡(FFE/DFE) / CDR 的**实现**；与 `eic_behavioral.EIC_DISCLOSURE`
    （排除 **EIC 电路级** BER）**显式分层**。
  · 🔴 **接收 SNR 是设计输入假设**（`OI_M2_PROCESS["snr_db"]`）；本模块另给
    `tia_noise_snr_db`（热+散粒闭式推算）作**上界交叉核对**，**非**实测噪声预算。
  · `verdict` 恒 `DESIGN_BUDGET`；**不报** TOPS / TOPS-W / fJ/op / pJ/bit。
  · 器件为 **L0/L1 解析 / 行为模型**，参数为公开文献典型量级占位（**非 PDK**），**无实测锚**。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lda_l2 import oi_m1 as _M1

# ═════════════════════════════════════════════════════════════════════════════
# 1) 规格锚常量（外部标准 = 限值口径 · 「外部对标四层」第 ④ 层，可用）
# ═════════════════════════════════════════════════════════════════════════════
PAM4_BAUD_200G_GBD = 106.25          # IEEE 802.3dj · 200G/lane（DR8/2×DR4 变体）
LINE_RATE_PER_LANE_GBPS = 212.5      # 线速率 = 2×baud（PAM4）
NET_PER_LANE_GBPS = 200.0            # FEC 后净荷
NYQUIST_200G_GHZ = PAM4_BAUD_200G_GBD / 2.0   # 53.125 GHz

# 🔴 四源独立一致：Signal Integrity Journal《200Gbps Ethernet FEC Analysis》(DesignCon
#   2024 最佳论文) · Netnod《To Infinity and Beyond!》(802.3df/3dj 提案) ·
#   Vitex《1.6T Optical Transceivers 2026》· Ethernet Alliance（802.3dj 主席 D'Ambrosio）。
#   200G/lane **不是** 100G/lane 的 FEC：802.3dj 用**级联**（外 KP4 ⊗ 内 Hamming/BCH(128,120)），
#   pre-FEC 门限从 2.4e-4 放宽到 ~4.8e-3（≈4.85e-3）；RS-only 模式仍为 2.4e-4。
FEC_MODE_PROFILES: Dict[str, Dict[str, Any]] = {
    "concatenated": {
        "label": "级联 FEC（外 KP4 RS(544,514) ⊗ 内 Hamming/BCH(128,120) + 卷积交织）",
        "pre_fec_ber": 4.8e-3,
        "inner_code": "Hamming/BCH(128,120)",
        "needs_module_dsp": True,
        "note": "内码在**模块 DSP** 内实现 ⇒ 仅重定时（retimed）模块可得。",
    },
    "rs_only": {
        "label": "RS-only（KP4 RS(544,514) 单级）",
        "pre_fec_ber": 2.4e-4,
        "inner_code": None,
        "needs_module_dsp": False,
        "note": "🔴 **LPO（模块内无 DSP）唯一可用模式** —— 拿不到内码增益。",
    },
}
# 规格锚窗口（防口径静默写错 —— M1 血案同族：值本身错 100× 时原判据全绿）
_FEC_BER_ANCHOR_BAND = {"concatenated": (4.5e-3, 5.2e-3), "rs_only": (2.0e-4, 2.8e-4)}
_BAUD_ANCHOR_BAND_GBD = (106.0, 106.5)
_LPO_INNER_GAIN_BAND_DB = (2.4, 3.1)


# ═════════════════════════════════════════════════════════════════════════════
# 2) 设计常量（公开文献典型量级占位 · **非 PDK**）
# ═════════════════════════════════════════════════════════════════════════════
OI_M2_PROCESS: Dict[str, Any] = {
    "n_lanes": 8,
    "baud_gbd": PAM4_BAUD_200G_GBD,
    # 200G 档器件带宽（三单极点级联 ⇒ EO f_3dB ≈ 56.4 GHz ≥ Nyquist 53.125）
    "f_mod_ghz": 105.0,          # 调制器 EO 3dB（行波设计目标；非解析行波电极）
    "f_pd_ghz": 105.0,           # 探测器 3dB（τ=RC 口径）
    "f_tia_ghz": 125.0,          # TIA 单极点 3dB（200G 档）
    "r_f_ohm": 300.0,            # TIA 反馈电阻（200G 档）
    "c_f_fF": 5.0,               # TIA 反馈电容
    "spacing_nm": 4.5,           # LWDM ≈ 800 GHz 间隔（设计近似，非标准栅）
    "wl0_nm": 1311.0,            # 首信道波长（**O-band 主设计点**）
    "d_ps_nm_km": 0.0,           # O-band 近零色散
    "reach_km": 2.0,
    "snr_db": 28.0,              # 🔴 **设计输入假设**（满幅信噪比）；非实测噪声预算
    "tx_sigma_frac": 0.25,       # 源脉冲 RMS σ₀ = frac × T_sym
    "tau_driver_ps": 1.6,        # 🔴 驱动一阶时间常数设计目标（200G 档；非实测）
    "ring_m": 268,               # 环区数 m = `plan_m2_rings()` 的搜索解（M2 O-band 栅）
    # 🔴 **不是** 129：129 是 M1 在 C-band 栅上的解（`OI_M1_PROCESS["ring_m"]`）。
    #    同一规划器切到 M2 的 O-band 栅（1311 nm 起 / 4.5 nm ≈ 800 GHz）后最优 m 变为 268
    #    （R = m·λ/(2π·n_g) = 13.31 µm；129 ⇒ 6.41 µm）。两者不可互抄 —— M1 有此互锁判据
    #    （`oi_m1_self_check` #9），M2 原缺 ⇒ v0.9.179 补 #14b 同款判据 + 探针 P10。
    "ring_gap_um": 0.55,
}

# 🔴 吃狗粮证据常量：M1 的 100G 档器件（用于「带宽墙」反例）
OI_M2_LEGACY_PROCESS: Dict[str, float] = {
    "f_mod_ghz": 55.0, "f_pd_ghz": 60.0, "f_tia_ghz": 90.9,
    "note": "M1（100G/lane）档常量：EO f_3dB ≈ 32.94 GHz。",
}

# 设计点预设：主设计 + 色散边界 + **带宽墙反例**（吃狗粮证据）
# 🔴 `expect` 为门禁消费的**声明式期望**：新增设计点必须显式声明，否则门禁判 FAIL
#    （防「新成员静默进盲区」）。取值：`pass` · `disp_limited` · `bw_limited`。
SPEC_POINTS_M2: List[Dict[str, Any]] = [
    {"key": "O_2km", "band": "O", "wl_nm": 1311.0, "d_ps_nm_km": 0.0, "reach_km": 2.0,
     "process": "fast", "role": "main", "expect": "pass",
     "note": "主设计点：O-band 2 km（近零色散）· 200G 档器件带宽"},
    {"key": "C_2km", "band": "C", "wl_nm": 1550.0, "d_ps_nm_km": 17.0, "reach_km": 2.0,
     "process": "fast", "role": "limit", "expect": "disp_limited",
     "note": ("设计边界：C-band 2 km 在 200G/lane 下**色散主导** —— "
              "同一点在 M1（100G/lane）曾是 pass ⇒ 量化「速率翻倍 ⇒ 色散代价 ~4×」")},
    {"key": "O_2km_legacy", "band": "O", "wl_nm": 1311.0, "d_ps_nm_km": 0.0,
     "reach_km": 2.0, "process": "legacy", "role": "counterexample",
     "expect": "bw_limited",
     "note": ("🔴 吃狗粮反例：同链路换回 M1 的 100G 档器件常量（EO f_3dB 32.94 GHz "
              "< Nyquist 53.125 GHz）⇒ 眼被 ISI 闭合、所需 SNR 不可达")},
]


# ═════════════════════════════════════════════════════════════════════════════
# 3) FEC 规格锚 + LPO 代价（闭式 Q 函数 · golden = M1 闭式）
# ═════════════════════════════════════════════════════════════════════════════
def fec_pre_fec_ber(mode: str) -> float:
    """FEC 模式 → pre-FEC BER 门限（单一真源 = `FEC_MODE_PROFILES`）。"""
    try:
        return float(FEC_MODE_PROFILES[mode]["pre_fec_ber"])
    except KeyError:
        raise ValueError("未知 FEC 模式：%r（已注册=%s）"
                         % (mode, sorted(FEC_MODE_PROFILES)))


def required_snr_ideal_db(mode: str) -> float:
    """该 FEC 模式在 **AWGN 无 ISI** 下所需 SNR（闭式 Q 函数 · golden）。"""
    return _M1.ideal_required_snr_db(fec_pre_fec_ber(mode))


def lpo_inner_code_gain_db() -> float:
    """**LPO 代价（FEC 分项）**：级联内码带来的门限增益 = `SNR(RS-only) − SNR(级联)`。

    LPO 模块内无 DSP ⇒ 内码不可用 ⇒ 丢掉这部分增益（正数 = 所需 SNR 上升）。
    """
    return required_snr_ideal_db("rs_only") - required_snr_ideal_db("concatenated")


def mode_for_form_factor(form: str) -> str:
    """形态 → 可用 FEC 模式：`retimed`（有模块 DSP）⇒ 级联；`lpo`（无 DSP）⇒ RS-only。"""
    if form == "lpo":
        return "rs_only"
    if form == "retimed":
        return "concatenated"
    raise ValueError("未知形态：%r（应为 'lpo' | 'retimed'）" % (form,))


# ═════════════════════════════════════════════════════════════════════════════
# 4) 带宽：EO S21 / 奈奎斯特 / 余量（复用 M1 闭式）
# ═════════════════════════════════════════════════════════════════════════════
def eo_f3db_ghz(process: str = "fast", **override: Any) -> float:
    """该工艺档的级联 EO S21 −3 dB 带宽（GHz）。"""
    p = OI_M2_PROCESS if process == "fast" else OI_M2_LEGACY_PROCESS
    fm = float(override.get("f_mod_ghz", p["f_mod_ghz"])) * 1e9
    fp = float(override.get("f_pd_ghz", p["f_pd_ghz"])) * 1e9
    ft = float(override.get("f_tia_ghz", p["f_tia_ghz"])) * 1e9
    return _M1.eo_s21_f3db_hz(fm, fp, ft) / 1e9


def bandwidth_headroom_ghz(process: str = "fast", baud_gbd: float = PAM4_BAUD_200G_GBD
                           ) -> float:
    """EO f_3dB − 奈奎斯特（>0 = 带宽富余；<0 = 眼被 ISI 侵蚀）。"""
    return eo_f3db_ghz(process) - baud_gbd / 2.0


# ═════════════════════════════════════════════════════════════════════════════
# 5) 驱动–TIA 协同（200G 档 · 复用 M1 → 复用 eic_behavioral）
# ═════════════════════════════════════════════════════════════════════════════
def driver_tia_200g(n_lanes: Optional[int] = None, baud_gbd: Optional[float] = None
                    ) -> Dict[str, Any]:
    """复用 M1 `driver_tia_cosim`，注入 **M2 的 200G 档参数**（驱动 τ / TIA R_f、C_f）。"""
    p = OI_M2_PROCESS
    return _M1.driver_tia_cosim(
        n_lanes=(p["n_lanes"] if n_lanes is None else n_lanes),
        tau_driver_s=p["tau_driver_ps"] * 1e-12,
        baud_gbd=(p["baud_gbd"] if baud_gbd is None else baud_gbd),
        r_f_ohm=p["r_f_ohm"], c_f_fF=p["c_f_fF"] * 1e-15)


# ═════════════════════════════════════════════════════════════════════════════
# 6) 接收噪声预算（闭式 · 与 M1「SNR 假设」**方法学独立**的交叉核对）
# ═════════════════════════════════════════════════════════════════════════════
_Q_E = 1.602176634e-19
_K_B = 1.380649e-23


def tia_noise_snr_db(responsivity_a_w: float = 0.8, oma_dbm: float = -6.0,
                     r_f_ohm: Optional[float] = None, bw_ghz: Optional[float] = None,
                     t_kelvin: float = 300.0) -> Dict[str, Any]:
    """接收机**噪声预算闭式**推算的「满幅 SNR」（dB）—— M1「SNR 假设」的独立交叉核对。

      i_n² = 4kT/R_f + 2q·I_avg          [A²/Hz]（热噪声 + 散粒噪声）
      I_pp = R·P_OMA                      [A]（OMA 全摆幅）
      σ    = i_n·√BW ; SNR = 20·log10(I_pp/σ)   （与 M1 `σ = 6/10^(snr/20)` 同口径）

    🔴 **诚实边界（必读）**：这是**乐观上界** —— 只含热 + 散粒 + TIA 输入参考，
      **不含** RIN / 反射（ORLT）/ 模式噪声 / 信道串扰 / 老化 / 温度漂移 ⇒
      **不得**把其绝对值当灵敏度规格宣称；其价值在**方法**与「噪声是否瓶颈」的判定。
    """
    p = OI_M2_PROCESS
    rf = p["r_f_ohm"] if r_f_ohm is None else r_f_ohm
    bw = (eo_f3db_ghz("fast") if bw_ghz is None else bw_ghz) * 1e9
    p_oma_w = 10.0 ** (oma_dbm / 10.0) * 1e-3
    i_pp = responsivity_a_w * p_oma_w
    i_avg = 0.5 * i_pp
    i_thermal = 4.0 * _K_B * t_kelvin / rf
    i_shot = 2.0 * _Q_E * i_avg
    i_n = math.sqrt(i_thermal + i_shot)        # A/√Hz
    sigma = i_n * math.sqrt(bw)                # A rms
    snr = 20.0 * math.log10(i_pp / sigma) if sigma > 0 else float("inf")
    return {"snr_db": snr, "i_pp_a": i_pp, "i_n_a_per_rt_hz": i_n,
            "noise_sigma_a": sigma, "bw_ghz": bw / 1e9,
            "i_thermal_a2_per_hz": i_thermal, "i_shot_a2_per_hz": i_shot,
            "oma_dbm": oma_dbm, "responsivity_a_w": responsivity_a_w,
            "r_f_ohm": rf}


# ═════════════════════════════════════════════════════════════════════════════
# 7) 单设计点预算（两种形态 · 复用 M1 `required_snr_db`）
# ═════════════════════════════════════════════════════════════════════════════
def _sim_kw(spec: Dict[str, Any]) -> Dict[str, Any]:
    """设计点 → `pam4_link_sim` 参数（工艺档 + 波长/色散/跨度 + 200G 波特率）。"""
    proc = "fast" if spec.get("process", "fast") == "fast" else "legacy"
    p = OI_M2_PROCESS if proc == "fast" else OI_M2_LEGACY_PROCESS
    return {
        "baud_gbd": OI_M2_PROCESS["baud_gbd"],
        "f_mod_ghz": p["f_mod_ghz"], "f_pd_ghz": p["f_pd_ghz"],
        "f_tia_ghz": p["f_tia_ghz"],
        "d_ps_nm_km": spec["d_ps_nm_km"], "L_km": spec["reach_km"],
        "wl_nm": spec["wl_nm"], "seed": 0,
        "sigma_tx_frac": OI_M2_PROCESS["tx_sigma_frac"],
    }


def _limiting_factor(spec: Dict[str, Any], mode: str = "concatenated") -> Dict[str, Any]:
    """判定不可达的**成因**：关掉色散重算 ⇒ 仍不可达 = 带宽受限；关掉后可达 = 色散受限。

    🔴 必须**分因**：把色散受限误报成带宽受限会指向错误的整改方向
    （前者改波段/加 EDC，后者换更高带宽器件）。
    """
    ber = fec_pre_fec_ber(mode)
    kw = _sim_kw(spec)
    kw_nodisp = dict(kw)
    kw_nodisp["d_ps_nm_km"] = 0.0
    r_disp = _M1.required_snr_db(ber, **kw)
    r_nodisp = _M1.required_snr_db(ber, **kw_nodisp)
    if r_nodisp["reachable"] and not r_disp["reachable"]:
        cause = "disp_limited"
    elif not r_nodisp["reachable"]:
        cause = "bw_limited"
    else:
        cause = "pass"
    return {"cause": cause,
            "required_snr_nodisp_reachable": bool(r_nodisp["reachable"]),
            "ber_at_snr_hi_nodisp": r_nodisp["ber_at"]}


def point_budget(spec: Dict[str, Any], snr_db: Optional[float] = None) -> Dict[str, Any]:
    """给定设计点，逐**形态**（retimed / LPO）算所需 SNR 与设计裕量。

    · `required_snr_db`：达该形态 pre-FEC 门限所需的接收 SNR（含带宽/色散 ISI 代价）。
    · `margin_db` = 设计假设 SNR − 所需 SNR（>0 通过）。
    · `lpo_penalty_db` = margin(retimed) − margin(LPO)（LPO 相对重定时的裕量缩水）。
    · `verdict_point` / `limiting_cause`：分因判定（pass / disp_limited / bw_limited），
      由**关掉色散重算**独立判定（防把色散受限误归因成带宽受限）。
    """
    p = OI_M2_PROCESS
    snr = p["snr_db"] if snr_db is None else snr_db
    kw = _sim_kw(spec)
    proc = "fast" if spec.get("process", "fast") == "fast" else "legacy"
    out: Dict[str, Any] = {
        "key": spec["key"], "band": spec["band"], "wl_nm": spec["wl_nm"],
        "reach_km": spec["reach_km"], "process": proc,
        "eo_f3db_ghz": eo_f3db_ghz(proc),
        "nyquist_ghz": kw["baud_gbd"] / 2.0,
        "snr_assumed_db": snr, "expect": spec["expect"], "note": spec["note"],
    }
    out["bandwidth_headroom_ghz"] = out["eo_f3db_ghz"] - out["nyquist_ghz"]
    for form in ("retimed", "lpo"):
        mode = mode_for_form_factor(form)
        req = _M1.required_snr_db(fec_pre_fec_ber(mode), **kw)
        ideal = required_snr_ideal_db(mode)
        reachable = bool(req["reachable"])
        out[form] = {
            "fec_mode": mode, "pre_fec_ber": fec_pre_fec_ber(mode),
            "required_snr_ideal_db": ideal,
            "required_snr_db": (req["snr_db"] if reachable else None),
            "required_snr_reachable": reachable,
            "ber_at_snr_hi": req["ber_at"],
            "isi_penalty_db": ((req["snr_db"] - ideal) if reachable else None),
            "margin_db": ((snr - req["snr_db"]) if reachable else None),
        }
    _r, _l = out["retimed"], out["lpo"]
    out["lpo_penalty_db"] = ((_r["margin_db"] - _l["margin_db"])
                             if (_r["required_snr_reachable"]
                                 and _l["required_snr_reachable"]) else None)
    # 结论标签（门禁消费的声明式判定；与 spec["expect"] 对照）—— 按**成因**分因
    lf = _limiting_factor(spec, mode=mode_for_form_factor("retimed"))
    out["limiting_cause"] = lf["cause"]
    out["required_snr_nodisp_reachable"] = lf["required_snr_nodisp_reachable"]
    if not _r["required_snr_reachable"]:
        out["verdict_point"] = lf["cause"]      # disp_limited | bw_limited
    elif not _l["required_snr_reachable"]:
        out["verdict_point"] = "lpo_limited"
    else:
        out["verdict_point"] = "pass"
    return out


def m2_budget_all_points(snr_db: Optional[float] = None) -> Dict[str, Any]:
    """按 `SPEC_POINTS_M2` 逐点跑 M2 预算（reurl：同一 200G 波特率只换波段/跨度/工艺档）。"""
    return {sp["key"]: point_budget(sp, snr_db=snr_db) for sp in SPEC_POINTS_M2}


def aggregate_gbps(n_lanes: Optional[int] = None) -> float:
    """净聚合速率（Gb/s）= 通道数 × 200G。"""
    n = OI_M2_PROCESS["n_lanes"] if n_lanes is None else n_lanes
    return n * NET_PER_LANE_GBPS


# ═════════════════════════════════════════════════════════════════════════════
# 8) 波长栅 / 环规划（复用 M1 `plan_lwdm_channels`，切到 M2 的 O-band 栅）
# ═════════════════════════════════════════════════════════════════════════════
def m2_channels(n_lanes: Optional[int] = None,
                wl0_nm: Optional[float] = None) -> List[float]:
    """M2 LWDM 信道栅（O-band 起 1311 nm · 4.5 nm ≈ 800 GHz 间隔）。"""
    p = OI_M2_PROCESS
    n = p["n_lanes"] if n_lanes is None else n_lanes
    w0 = p["wl0_nm"] if wl0_nm is None else wl0_nm
    return [round(w0 + p["spacing_nm"] * i, 4) for i in range(n)]


def plan_m2_rings() -> Dict[str, Any]:
    """复用 M1 的**梳齿规避**信道规划，切到 M2 的 O-band 栅。"""
    return _M1.plan_lwdm_channels(
        n_lanes=OI_M2_PROCESS["n_lanes"],
        spacing_nm=OI_M2_PROCESS["spacing_nm"],
        wl0_nm=OI_M2_PROCESS["wl0_nm"])


# ═════════════════════════════════════════════════════════════════════════════
# 9) 诚实对标（体例照 oi_m1 / photonic_compute_benchmarks）
# ═════════════════════════════════════════════════════════════════════════════
PUBLIC_LANDMARKS_M2: List[Dict[str, Any]] = [
    {"name": "1.6T-DR8（8×200G PAM4 · O-band · 500 m）", "family": "pluggable_optics",
     "dimension": "aggregate_rate", "value": 1600.0, "unit": "Gb/s",
     "source": "IEEE P802.3dj / OIF CEI-224G 公开规格族", "verified": False,
     "note": ("架构族对齐项（8×200G 并行）；**非 LDA 成就**，仅作同族维度参照。"
              "仓库既有对标锚 `golden_product_benchmarks.GC-CPO-OIO-8CH` 同族。")},
    {"name": "200G/lane PAM4 符号率 106.25 GBd", "family": "pluggable_optics",
     "dimension": "baud_rate", "value": 106.25, "unit": "GBd",
     "source": "IEEE P802.3dj 公开规格（Jabil 1.6T DR8 数据表）", "verified": False,
     "note": "M2 每通道符号率设计点来源。"},
    {"name": "802.3dj 200G/lane 级联 FEC pre-FEC 门限 ≈ 4.8e-3", "family": "pluggable_optics",
     "dimension": "pre_fec_ber", "value": 4.8e-3, "unit": "1",
     "source": ("Signal Integrity Journal (DesignCon 2024) / Netnod 802.3dj 提案 / "
                "Vitex 1.6T 指南 / Ethernet Alliance（802.3dj 主席）"),
     "verified": False,
     "note": "外部标准限值（第 ④ 层）；RS-only 模式仍为 2.4e-4。**非 LDA 成就**。"},
]

LDA_CAPABILITIES_M2: List[Dict[str, Any]] = [
    {"capability": "200G/lane（106.25 GBd PAM4）链路预算：眼/Q/BER 与**所需 SNR**",
     "level": "design_budget",
     "note": "闭式 Q 函数 golden；不含 SerDes/DSP/FEC 实现/均衡/CDR。"},
    {"capability": "**LPO 无 DSP 线性形态**预算（FEC 门限收紧 + 裕量缩水量化）",
     "level": "design_budget",
     "note": "形态为「模块内无 DSP」的设计约束；内码增益损失由闭式 Q 差给出。"},
    {"capability": "级联 FEC 双模式规格锚（RS-only 2.4e-4 / 级联 4.8e-3）",
     "level": "external_standard",
     "note": "外部标准限值（非 LDA 成就）；改错值必红（探针 P7）。"},
    {"capability": "接收噪声预算闭式推算（热+散粒）与「SNR 假设」独立交叉核对",
     "level": "design_budget",
     "note": "乐观上界（不含 RIN/反射/串扰/老化）；不作灵敏度规格宣称。"},
    {"capability": "该收发器拓扑**专用真 GDS builder**（Tx/Rx 双侧 + 单次主权 DRC/LVS）",
     "level": "design_signoff",
     "note": "设计期签核（D4 同口径）；非流片、非实测签核。"},
]

NON_CLAIMED_M2: List[str] = [
    "不宣称任何 TOPS / TOPS-W / fJ/op / pJ/bit / 能效（既无功耗模型亦无实测硅）。",
    "不做数值超越比较：LDA 是设计&验证 EDA，非收发器芯片；对比仅在架构族与设计质量方法论维度。",
    "BER 为**光通道预算级**闭式估计，**非**实测误码率；FEC/均衡/时钟恢复**只作门限口径**，不做编解码实现。",
    "LPO 形态为**模块内无 DSP** 的预算口径；不含 host SerDes 通道建模/链路训练（ILT）实现。",
    "接收 SNR 为**设计输入假设**（另有热+散粒上界交叉核对）；器件为 L0/L1 解析/行为模型，参数非 PDK，无实测锚。",
    "真 GDS 版图为**设计期签核**（层规为公开工艺近似，非 Foundry PDK 标定值）；未流片、未实测。",
]

OI_M2_DISCLOSURE: Dict[str, str] = {
    "level": "A 档闭式 / 行为级（红线 §四 A 档授权同族）：带宽 · 色散 · 眼/Q/BER · 噪声预算均为闭式物理律。",
    "not_redline": "不碰电-光耦合增益真值（T2 锁）· 不用 A 级商业工具 · 不流片。",
    "form_lpo": ("🔴 **LPO = 模块内无 DSP**（host SerDes 直接驱动）：级联 FEC 的**内码在模块 DSP 内**"
                 "⇒ LPO 只能用 **RS-only（2.4e-4）** ⇒ 相对重定时（级联 4.8e-3）所需 SNR 上升 "
                 "**2.744 dB**。该值是**设计约束**而非免责声明。"),
    "ber_layer": ("🔴 BER = **光链路预算级闭式估计**（golden = 闭式 Q 函数）。与 "
                  "`eic_behavioral.EIC_DISCLOSURE`（排除 **EIC 电路级** SerDes/DSP/BER）**显式分层**："
                  "本模块只含**光通道**带宽 + 色散 + 接收噪声，**不含** SerDes/DSP/FEC 实现/均衡/CDR。"),
    "snr_is_input": ("🔴 **接收 SNR 是设计输入假设**（`OI_M2_PROCESS['snr_db']`）；"
                     "`tia_noise_snr_db` 给出**热+散粒上界**作独立交叉核对（不含 RIN/反射/串扰/老化）"
                     "—— 该上界远高于所需 ⇒ **接收噪声不是 200G/lane 的瓶颈，带宽/ISI 才是**。"),
    "spec_anchor": ("🔴 200G/lane 的 FEC 门限与符号率取自**外部标准**（802.3dj，四源独立一致）；"
                    "与 M1 的 100G/lane KP4（2.4e-4）**不是同一口径** ⇒ 各配规格锚判据 + 改错值必红探针。"),
    "no_energy": "🔴 **零能效数字**：不报 TOPS / TOPS-W / fJ/op / pJ/bit。",
    "verdict": "恒 `DESIGN_BUDGET`（真 GDS 为设计期签核）；非流片实测、非实测签核。",
    "params": "参数为公开文献典型量级占位（非 PDK）；器件 L0/L1，无实测锚。",
}


def honest_boundary_ok() -> bool:
    """护栏：**能力宣称面**（`LDA_CAPABILITIES_M2` + `PUBLIC_LANDMARKS_M2`）不得含能效/TOPS 字样。

    体例照 `oi_m1.honest_boundary_ok`：只守「能力宣称」面；`NON_CLAIMED_M2` /
    `OI_M2_DISCLOSURE` 是**否定语境** ⇒ 不参与本判据（否则正确的自我否定会被误判违规）。
    突变探针 = 向 `LDA_CAPABILITIES_M2` 注入 "76 TOPS/W" ⇒ 本判据必红。
    """
    blob = repr(LDA_CAPABILITIES_M2) + repr(PUBLIC_LANDMARKS_M2)
    for tok in ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "pJ/bit", "W/op"):
        if tok in blob:
            return False
    return True


# ═════════════════════════════════════════════════════════════════════════════
# 10) 自检
# ═════════════════════════════════════════════════════════════════════════════
def oi_m2_self_check(verbose: bool = True) -> Dict[str, Any]:
    checks: List[Tuple[str, bool]] = []

    # 1) 规格锚：200G/lane 符号率落在公开窗口
    lo, hi = _BAUD_ANCHOR_BAND_GBD
    checks.append((f"规格锚: 200G/lane 符号率 {PAM4_BAUD_200G_GBD} GBd ∈ [{lo},{hi}]",
                   lo <= PAM4_BAUD_200G_GBD <= hi))
    # 2) 规格锚：两 FEC 模式门限各自落在公开窗口
    for mode, (a, b) in _FEC_BER_ANCHOR_BAND.items():
        v = fec_pre_fec_ber(mode)
        checks.append((f"规格锚: {mode} pre-FEC {v:.2e} ∈ [{a:.1e},{b:.1e}]",
                       a <= v <= b))
    # 3) LPO 内码增益落在合理窗口
    gain = lpo_inner_code_gain_db()
    g_lo, g_hi = _LPO_INNER_GAIN_BAND_DB
    checks.append((f"LPO 内码增益 {gain:.3f} dB ∈ [{g_lo},{g_hi}]",
                   g_lo <= gain <= g_hi))
    # 4) LPO 内码增益 ⟷ 两模式闭式 SNR 差（同源自洽，防两处各写一份）
    d = required_snr_ideal_db("rs_only") - required_snr_ideal_db("concatenated")
    checks.append(("LPO 内码增益 ≡ 闭式 SNR(RS-only)−SNR(级联)",
                   abs(gain - d) < 1e-12))
    # 5) 形态 → FEC 模式映射（LPO 不得拿级联）
    checks.append(("LPO ⇒ RS-only（拿不到模块内码）",
                   mode_for_form_factor("lpo") == "rs_only"
                   and mode_for_form_factor("retimed") == "concatenated"))
    # 6) 200G 档 EO f_3dB ≥ Nyquist（设计充分性）
    hr = bandwidth_headroom_ghz("fast")
    checks.append((f"200G 档 EO f_3dB {eo_f3db_ghz('fast'):.2f} GHz ≥ Nyquist "
                   f"{NYQUIST_200G_GHZ:.3f}（余量 {hr:+.2f}）", hr > 0.0))
    # 7) 🔴 吃狗粮：M1 档常量在 200G/lane **不足**（带宽墙真存在）
    hr_legacy = bandwidth_headroom_ghz("legacy")
    checks.append((f"吃狗粮: M1 档 EO f_3dB {eo_f3db_ghz('legacy'):.2f} GHz < Nyquist "
                   f"（缺 {-hr_legacy:.2f} GHz）", hr_legacy < 0.0))
    # 8) 三点设计：verdict_point ≡ 声明 expect（防「新成员静默进盲区」）
    pts = m2_budget_all_points()
    for sp in SPEC_POINTS_M2:
        k = sp["key"]
        checks.append((f"设计点 {k}: verdict {pts[k]['verdict_point']} ≡ 声明 {sp['expect']}",
                       pts[k]["verdict_point"] == sp["expect"]))
    # 9) 主设计点：LPO 裕量 > 0 且 < retimed 裕量（LPO 真收紧）
    o2 = pts["O_2km"]
    checks.append((f"O_2km: LPO 裕量 {o2['lpo']['margin_db']:+.2f}dB ∈ (0, retimed "
                   f"{o2['retimed']['margin_db']:+.2f})",
                   0.0 < o2["lpo"]["margin_db"] < o2["retimed"]["margin_db"]))
    checks.append((f"O_2km: LPO 代价 {o2['lpo_penalty_db']:.2f} dB ≈ 内码增益 "
                   f"{gain:.2f} dB（±1.5）",
                   abs(o2["lpo_penalty_db"] - gain) < 1.5))
    # 10) 色散边界：C-band 2km 不可达，而 O-band 可达（两法同向）
    c2, o2p = pts["C_2km"], pts["O_2km"]
    checks.append(("C_2km 不可达 且 O_2km 可达（色散主导结论）",
                   (not c2["retimed"]["required_snr_reachable"])
                   and o2p["retimed"]["required_snr_reachable"]))
    # 11) 噪声预算闭式：上界 > 设计假设（⇒ 假设保守，噪声非瓶颈）
    nz = tia_noise_snr_db()
    checks.append((f"接收噪声上界 {nz['snr_db']:.1f} dB > 设计假设 "
                   f"{OI_M2_PROCESS['snr_db']:.1f} dB（噪声非瓶颈）",
                   nz["snr_db"] > OI_M2_PROCESS["snr_db"]))
    # 12) 驱动–TIA（200G 档）：闭式 ⟷ RK4 一致 + 上升 UI + TIA 余量
    dt_ = driver_tia_200g()
    checks.append((f"驱动 t90: 闭式⟷RK4 一致（rel<1e-3，τ={OI_M2_PROCESS['tau_driver_ps']}ps）",
                   dt_["t90_abs_diff_s"] is not None
                   and dt_["t90_abs_diff_s"] / dt_["t90_closed_form_s"] < 1e-3))
    checks.append((f"驱动上升 {dt_['rise_10_90_ui']:.2f} UI<0.5 且 TIA "
                   f"{dt_['tia_over_nyquist']:.2f}×Nyquist",
                   dt_["driver_fast_enough"] and dt_["tia_wide_enough"]))
    # 13) 聚合 = 8×200G = 1.6 Tb/s
    checks.append((f"聚合净速率 {aggregate_gbps():.0f} Gb/s = 8×200G",
                   abs(aggregate_gbps() - 1600.0) < 1e-9))
    # 14) 波长栅 / 环规划（复用 M1 能力切 O-band）
    plan = plan_m2_rings()
    bp = plan["best"] or {}
    checks.append((f"M2 O-band 环规划: {plan['n_solutions']} 解, best m={bp.get('m')} "
                   f"minXT={bp.get('min_xt_db')}dB", plan["n_solutions"] > 0))
    # 14b) 🔴 搜索解 ⟷ 设计常量互锁（照 M1 `oi_m1_self_check` #9 体例；M2 原缺此判据
    #      ⇒ `ring_m` 曾静默抄成 M1 的 C-band 解 129 而门禁全绿）
    checks.append((f"环常量互锁: 搜索解 m={bp.get('m')} ⟷ 常量 m={OI_M2_PROCESS['ring_m']}"
                   f"（gap {bp.get('gap_um')} ⟷ {OI_M2_PROCESS['ring_gap_um']}）",
                   bool(bp) and int(bp.get("m")) == int(OI_M2_PROCESS["ring_m"])
                   and abs(float(bp.get("gap_um", -1.0))
                           - float(OI_M2_PROCESS["ring_gap_um"])) < 1e-9))
    checks.append(("M2 波长栅 O-band 起 1311 nm · 8 通道",
                   abs(m2_channels()[0] - 1311.0) < 1e-9 and len(m2_channels()) == 8))
    # 15) 诚实护栏
    checks.append(("诚实护栏无 TOPS/能效字样", honest_boundary_ok()))

    ok = all(v for _, v in checks)
    if verbose:
        print("=== OI M2 自检 ===")
        for name, v in checks:
            print(f"  [{'PASS' if v else 'FAIL'}] {name}")
        print(f"  1.6T: 8×{NET_PER_LANE_GBPS:.0f}G = {aggregate_gbps():.0f} Gb/s · "
              f"baud {PAM4_BAUD_200G_GBD} GBd · EO f_3dB {eo_f3db_ghz('fast'):.2f} GHz")
        print(f"  LPO 代价(FEC) = {gain:.3f} dB · 接收噪声上界 {nz['snr_db']:.1f} dB")
        for sp in SPEC_POINTS_M2:
            pt = pts[sp["key"]]
            rm = pt["retimed"]["margin_db"]
            lm = pt["lpo"]["margin_db"]
            r_txt = "不可达" if rm is None else f"{rm:+.2f}dB"
            l_txt = "不可达" if lm is None else f"{lm:+.2f}dB"
            print(f"  {sp['key']:13s} {pt['verdict_point']:12s} "
                  f"EO={pt['eo_f3db_ghz']:.2f}GHz retimed={r_txt} LPO={l_txt}")
    return {"ok": ok, "checks": checks, "points": pts,
            "lpo_inner_code_gain_db": gain, "noise_bound": nz}


if __name__ == "__main__":
    r = oi_m2_self_check()
    raise SystemExit(0 if r["ok"] else 1)
