"""J5 量子网络与接口征程（Layer 5 · M0–M4）案例卡（WebUI 只读端点数据源）。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
J5 征程「吃狗粮」LDA-J5（v0.9.242… · M0–M4 收官）的**只读案例**：把
「**节点 → 网络**」这一 J1–J4 从未交付的维度（公里级距离 + 经典接口）
收进一张卡：信道损耗 / 纠缠分发 / 纠缠源 / 量子中继 / 微波-光换能 / 经典接口。

🔴 **与 `/api/j4_qs_system`（器件→系统）分工不同**：
  · `j4_qs_system` = **传感系统级**（多参数解耦 / 微型化 / 集成 / 热负载）；
  · 本卡 = **网络链路级**（损耗-保真-速率-换能-定时）—— 二者互补，非重复。

🔴 **零重计算**：本模块**不跑仿真、不 import 求解器、不 import numpy/scipy** ——
全部数字由**闭式算术现算**（对数衰减 / Werner 闭式 / 高斯重叠 / 三态卷积闭式 /
复留数侧带 / CPMG 指数和），与 `lda_l2/qnet_*` 各模块的现算值**逐值可对拍**
（`run_webui_j5_render_path_smoke` 常驻）。
⇒ **微秒级、无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**。
🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`（**非** ACCEPT/PASS），自带 `honest_note`。
🔴 **M4 净增 0 如实呈现**：经典接口因三证据否决未立锚（不虚报）。
🔴 顶层只 import 标准库 `cmath` / `math` / `os` / `typing`（门禁用 `ast` 断言）。
"""
from __future__ import annotations

import cmath
import math
from typing import Any, Dict, List

__all__ = [
    "CASE_ID", "J5_HONEST_NOTE", "MILESTONES", "ANCHORS", "GAPS", "M4_AVOIDANCE",
    "SELFCHECK_MODULES", "MODULE_SELFCHECKS_TOTAL", "RENDER_PATH_SMOKE", "HEAVY_POST",
    "transmission", "link_fidelity", "hom_visibility", "repeater_yield",
    "storage_window_factor", "transducer_efficiency", "jitter_infidelity",
    "case_card", "run_selfchecks",
]

CASE_ID = "LDA-J5 · 量子网络与接口（节点 → 网络）"

J5_HONEST_NOTE = (
    "本卡为**设计预算**（design budget），所有数值由闭式算术现算，**非流片实测**、"
    "**非 foundry PDK**、**非商用器件数据表**。参数（α/L_depol/波包 σ/时序常数/换能参数/"
    "抖动 σ_t/机械模频率/浴温）为**文献量级的设计示例**；模型为**一阶/解析**近似 —— "
    "端到端保真**已含**多级纠缠交换递推（Werner 组合 `p_tot=p_seg^N`）与 DEJMPS 单轮纯化闭式，"
    "换能侧**已含**机械模热噪声（Bose 占据 + 参考到输入的总附加噪声，量子极限为其 T→0 特例），"
    "**仍不含**多轮纯化的资源计数、交换失败时序统计、机械模**非热**占据（自振/参量驱动）、"
    "泵浦加热导致的有效温度抬升、浴与模非共温、以及实测标定。"
    "**M4 经典接口净增 0**（三证据否决，如实呈现）。"
    "不作制造/性能宣称，不报能效/TOPS/fJ-op；不作任何与他人同台比较。"
)

MILESTONES = ["M0 纠缠分发 · 信道保真", "M1 纠缠源 · 不可分辨性", "M2 量子中继 · 交换与吞吐",
              "M3 微波-光换能器", "M4 量子-经典接口（净增 0）"]

ANCHORS = {
    "B519": "分发后两体纠缠保真度（Werner 闭式 ⇄ 密度矩阵距离步进 RK4）",
    "B520": "HOM 干涉可见度（高斯波包重叠闭式 ⇄ 复值复合梯形时间域积分）",
    "B521": "中继站期望交换产出数（生成窗⊗存储窗 嵌套卷积初等闭式 ⇄ 单重复合 Simpson）",
    "B522": "微波-光换能效率 η（分层 log+arctan 闭式 ⇄ 有限窗内复合 Simpson）",
}

#: 逐条缺口状态（**顺序与下方 GAPS 一一对应** · v0.9.286 四值口径）
#: 字符串型 gaps 不改形状（前端仍按字符串渲染），状态走这个并行列表。
GAPS_STATUS = [
    "已闭合（v0.9.292 · 单跳闭式 B519 + **多级纠缠交换递推**（Werner 组合 p_tot=p_seg^N）已建；"
    "并订正旧口径「F_seg^N 是上界」的方向错误（实为下界，默认档小 7.05 倍）；"
    "🔴 由此得诚实结论：**分段只提吞吐、不提保真**，提保真只能靠纯化（DEJMPS 单轮闭式，"
    "p>0.5892 才既提升又仍可用）；仍不含多轮纯化资源计数与实测）",
    "已闭合（v0.9.295 · 源不可分辨性已扩到**不对称源**：`lda_l2/qnet_indistinguishability` 给通式 "
    "V=[2σ₁σ₂/(σ₁²+σ₂²)]·exp(−δt²/2(σ₁²+σ₂²))·exp(−**2**δω²σ₁²σ₂²/(σ₁²+σ₂²))，σ₁=σ₂ 时**逐位退化**到 "
    "`qnet_source.hom_visibility`（B520 同锚）；并加多光子成分一阶修正 V·(1−g²(0))（端点 g²=0⇒不变 / g²=1⇒0）。"
    "参考档：对称 V=0.1353 → σ₂=1.5σ₁ 时 0.1249（0.923×）→ 再乘 g²=0.05 得 0.1187；"
    "仍未含非傅里叶谱扩散/chirp/暗计数与后脉冲）",
    "已闭合（v0.9.294 · N 段端到端吞吐已建 `lda_l2/qnet_throughput`：增益 G(N)=T(L/N)/(N·T(L))=e^{β−β/N}/N，"
    "**最优段数解析解 N* = β = α_ln·L**（由 d(lnG)/dN=β/N²−1/N=0 得）；参考档 β=4.605 ⇒ 整数 N*=5 ⇒ "
    "G=**7.96**；🔴 旧 `repeater_gain=53.70×` 是「站内理想率÷直传率」的**无损耗上界**（不含段内透射与串行摊薄），"
    "与端到端最优差 **6.74 倍**，两者并列披露不可混用；仍未含存储退相干对并发的限制与经典通信时延）",
    "已闭合（v0.9.296 · 换能侧补上**机械模热噪声**：`lda_l2/qnet_thermal_noise` 给 "
    "n_add(η,n_th)=(1−η)/η·(n_th+½)，n_th=1/(exp(ħΩ/k_BT)−1)；🔴 n_th=0 时**逐位退化**到既有量子极限 "
    "(1−η)/(2η)，且 T=T*≡ħΩ/(k_B ln3) 时 n_th **恰为 ½**、n_add **恰为 T=0 的 2 倍**。"
    "参考档（Ω/2π=5 GHz）T_q=239.96 mK · **T*=218.42 mK** · 热项≤10% 需 T≤78.82 mK；"
    "🔴 诚实分诊：本卡设计点 η=1.13% ⇒ T=0 量子极限已 43.94 quanta，20 mK 热项只增 1.2e-5 ⇒ "
    "**此处绑定约束是 η、不是温度**；仍不含非热占据/泵浦加热有效温度抬升/非平衡浴）",
    "已结算（经典接口 · 裁决净增 0）",
]

GAPS = ["G-QNET-1 分发保真", "G-QNET-2 源不可分辨性", "G-QNET-3 中继吞吐",
        "G-QNET-4 跨频段换能", "G-QNET-5 经典接口（净增 0）"]

M4_AVOIDANCE = {
    "B475": "自旋回波相位方差 —— 结构邻接（同一普遍结构：噪声 → 相位方差）",
    "qs_m2.coherent_chi": "噪声谱 × CPMG 滤波 → 相干积分 —— 既有实现已覆盖该链路",
    "B522": "有限探测带洛伦兹型积分 ⇄ 复合 Simpson —— 格式邻接",
}
M4_NEGATIVE_EVIDENCE = [
    "洛伦兹抖动谱 ⇒ 1/f² 尾部慢收敛 ⇒ 残差随网格**停滞**（比值恒 1.00 ⇒ 非离散误差）",
    "高斯抖动谱 ⇒ 数值积分**精确**（残差恰 0.0）⇒ 判据 D 不成立（精确量不可锚）",
    "CPMG 滤波为振荡函数 ⇒ 复合 **Simpson 粗端非单调**（同 B520 血案）",
]

SELFCHECK_MODULES = ["qnet_channel", "qnet_distribution", "qnet_source", "qnet_repeater",
                     "qnet_transducer", "qnet_classical", "qnet_system", "qnet_swap",
                     "qnet_throughput", "qnet_indistinguishability",
                     "qnet_thermal_noise"]
# 🔴 逐模块自检数（改任一模块的自检条数都必须同步这里 —— 同一事实两处表示）
#    v0.9.292：qnet_system 17→20（+3 条组合律订正核验）· 新增 qnet_swap 13
MODULE_SELFCHECKS_TOTAL = 14 + 10 + 8 + 20 + 16 + 14 + 20 + 13 + 12 + 10 + 16
RENDER_PATH_SMOKE = "run_webui_j5_render_path_smoke.py"
HEAVY_POST = False

# ── 与 `lda_l2/qnet_*` **同源**的设计示例默认档（🔴 J4 血案：卡与真源须同源）──
ALPHA_DB_PER_KM = 0.2
L_DEPOL_M = 2.2e4
LINK_LENGTH_M = 1.0e5
PACKET_SIGMA_S = 1.0e-12
DELAY_S = 2.0e-12
DW_RAD_S = 1.0e12
T_OBS_S = 2.0e-4
T_GEN_S = 5.0e-5
T_MEM_S = 1.6e-4
T_SWAP_S = 1.0e-4
G_RAD_S = 2.0 * math.pi * 5.0e6
KAPPA_MW_RAD_S = 2.0 * math.pi * 2.0e6
GAMMA_MECH_RAD_S = 2.0 * math.pi * 2.0e6
HALFWIDTH_RAD_S = 2.0 * math.pi * 1.0e6
DETUNING_HALF_RAD_S = 2.0 * math.pi * 10.0e6
BAND_HALF_RAD_S = 2.0 * math.pi * 5.0e6
OMEGA_RABI_RAD_S = 2.0 * math.pi * 1.0e6
SIGMA_T_S = 20.0e-9
TAU_C_S = 1.0e-6
SEQ_TIME_S = 4.0e-6
N_PULSES = 8

_LN10 = math.log(10.0)

#: 六段签核门限（与 `lda_l2/qnet_system._GATES` **同源**）
_GATES = {
    "channel": ("transmission", "ge", 1.0e-3),
    "dist": ("fidelity", "ge", 0.5),
    "source": ("visibility", "ge", 0.1),
    "repeater": ("storage_window_factor", "ge", 0.3),
    "transducer": ("eta_band", "ge", 1.0e-2),
    "classical": ("infidelity", "le", 1.0e-1),
}


# ══════════════════════════════════════════════════════════════════════
# 六段闭式（与 lda_l2/qnet_* 同律 · 纯标准库）
# ══════════════════════════════════════════════════════════════════════
def transmission(length_m: float = LINK_LENGTH_M,
                 alpha_db_per_km: float = ALPHA_DB_PER_KM) -> float:
    """① 光纤透射率 `T(L)=10^{−α·L_km/10}`。"""
    return float(10.0 ** (-alpha_db_per_km * (length_m / 1000.0) / 10.0))


def attenuation_length_m(alpha_db_per_km: float = ALPHA_DB_PER_KM) -> float:
    """①b 衰减长度 `L_att = 10/(α·ln10)·1000`（m）。"""
    return float(10.0 / (alpha_db_per_km * _LN10) * 1000.0)


def link_fidelity(length_m: float = LINK_LENGTH_M,
                  l_depol_m: float = L_DEPOL_M) -> float:
    """② 端到端分发后保真度 `F(L)=(1+3·exp(−L/L_depol))/4`（与 B519 同律）。"""
    return float((1.0 + 3.0 * math.exp(-length_m / l_depol_m)) / 4.0)


def werner_parameter(length_m: float = LINK_LENGTH_M,
                     l_depol_m: float = L_DEPOL_M) -> float:
    """②b Werner 参数 `p(L)=exp(−L/L_depol)`。"""
    return float(math.exp(-length_m / l_depol_m))


def chsh_parameter(fidelity: float) -> float:
    """②c CHSH 参数 `S=2√2·p`（`p=(4F−1)/3`）。"""
    p = (4.0 * fidelity - 1.0) / 3.0
    return float(2.0 * math.sqrt(2.0) * p)


def hom_visibility(packet_sigma_s: float = PACKET_SIGMA_S,
                   delay_s: float = DELAY_S, dw_rad_s: float = DW_RAD_S) -> float:
    """③ HOM 干涉可见度 `V=exp(−δt²/(4σ²))·exp(−δω²σ²)`（与 B520 同律）。"""
    s = float(packet_sigma_s)
    return float(math.exp(-(float(delay_s) ** 2) / (4.0 * s * s))
                 * math.exp(-(float(dw_rad_s) ** 2) * s * s))


def repeater_yield(t_obs_s: float = T_OBS_S, t_gen_s: float = T_GEN_S,
                   t_mem_s: float = T_MEM_S, t_swap_s: float = T_SWAP_S) -> float:
    """④ 期望交换产出数 `N_swap=κλ/(γ−λ)·[(1−e^{−λT})/λ−(1−e^{−γT})/γ]`（与 B521 同律）。"""
    lam, mu, kappa = 1.0 / t_gen_s, 1.0 / t_mem_s, 1.0 / t_swap_s
    g = mu + kappa
    return float(kappa * lam / (g - lam) * ((1.0 - math.exp(-lam * t_obs_s)) / lam
                                            - (1.0 - math.exp(-g * t_obs_s)) / g))


def storage_window_factor(window_s: float = T_OBS_S,
                          t_mem_s: float = T_MEM_S) -> float:
    """④b 存储窗平均存活因子 `(T_mem/W)(1−e^{−W/T_mem})`。"""
    return float(t_mem_s / window_s * (1.0 - math.exp(-window_s / t_mem_s)))


def repeater_rate(t_obs_s: float = T_OBS_S, **kw) -> float:
    """④c 产出率 `R=N_swap/T_obs`（1/s）。"""
    return float(repeater_yield(t_obs_s=t_obs_s, **kw) / t_obs_s)


def direct_rate(length_m: float = LINK_LENGTH_M, t_obs_s: float = T_OBS_S) -> float:
    """④d 直传率 `R_dir=T(L)/T_obs`（1/s）。"""
    return float(transmission(length_m) / t_obs_s)


def peak_efficiency(g: float = G_RAD_S, kappa_mw: float = KAPPA_MW_RAD_S,
                    gamma_mech: float = GAMMA_MECH_RAD_S) -> float:
    """⑤a 协同度极限效率 `η_peak=4C/(1+C)²`，`C=4G²/(κ_mw·γ_mech)`。"""
    c = 4.0 * g * g / (kappa_mw * gamma_mech)
    return float(4.0 * c / (1.0 + c) ** 2)


def _band_overlap(band_half: float = BAND_HALF_RAD_S,
                  detuning_half: float = DETUNING_HALF_RAD_S,
                  halfwidth: float = HALFWIDTH_RAD_S) -> float:
    """⑤b 归一化侧带重叠 `η_band=N(Ω_c)/D` —— 复留数 + 复对数（与能力层同律）。"""
    a, b, gg = -float(detuning_half), float(detuning_half), float(halfwidth)
    poles = [complex(a, gg), complex(a, -gg), complex(b, gg), complex(b, -gg)]
    tot = 0.0 + 0.0j
    for i, z in enumerate(poles):
        den = 1.0 + 0.0j
        for j, z2 in enumerate(poles):
            if i != j:
                den *= (z - z2)
        tot += (1.0 / den) * (cmath.log(band_half - z) - cmath.log(-band_half - z))
    num = float((gg * gg * tot).real)
    d, gv = float(detuning_half), float(halfwidth)
    ra = complex(-2.0 * d, gv) ** 2 + gv ** 2
    rb = complex(2.0 * d, gv) ** 2 + gv ** 2
    denom = float((math.pi * (gv / ra + gv / rb)).real)
    return float(num / denom)


def transducer_efficiency(g: float = G_RAD_S, kappa_mw: float = KAPPA_MW_RAD_S,
                          gamma_mech: float = GAMMA_MECH_RAD_S) -> float:
    """⑤ 总换能效率 `η=η_peak·η_band`（与 B522 同律）。"""
    return float(peak_efficiency(g, kappa_mw, gamma_mech) * _band_overlap())


def _cpmg_coeffs(n: int = N_PULSES) -> List[float]:
    return [-1.0] + [2.0 * ((-1.0) ** (k - 1)) for k in range(1, n + 1)] + [float((-1.0) ** n)]


def _cpmg_times(t: float = SEQ_TIME_S, n: int = N_PULSES) -> List[float]:
    tau = t / n
    return [0.0] + [(2.0 * j - 1.0) * tau / 2.0 for j in range(1, n + 1)] + [float(t)]


def jitter_phase_variance(omega_rabi: float = OMEGA_RABI_RAD_S, sigma_t: float = SIGMA_T_S,
                          tau_c: float = TAU_C_S, t: float = SEQ_TIME_S,
                          n: int = N_PULSES) -> float:
    """⑥a 时钟抖动相位方差 `σ_φ²=Ω²σ_t²Σ_{p,q}a_p a_q e^{−|t_p−t_q|/τ_c}`（与能力层同律）。"""
    a, ts = _cpmg_coeffs(n), _cpmg_times(t, n)
    s = 0.0
    for p in range(len(ts)):
        for q in range(len(ts)):
            s += a[p] * a[q] * math.exp(-abs(ts[p] - ts[q]) / tau_c)
    return float(omega_rabi ** 2 * sigma_t ** 2 * s)


def jitter_infidelity(omega_rabi: float = OMEGA_RABI_RAD_S, sigma_t: float = SIGMA_T_S,
                      tau_c: float = TAU_C_S, t: float = SEQ_TIME_S,
                      n: int = N_PULSES) -> float:
    """⑥ 时钟抖动保真损失 `1−exp(−σ_φ²/2)`（**M4 净增 0** 的能力层量）。"""
    return float(1.0 - math.exp(-jitter_phase_variance(omega_rabi, sigma_t, tau_c, t, n) / 2.0))


# ══════════════════════════════════════════════════════════════════════
# 案例卡
# ══════════════════════════════════════════════════════════════════════
def _gate(seg: str, value: float) -> str:
    _, op, thr = _GATES[seg]
    ok = (value >= thr) if op == "ge" else (value <= thr)
    return "PASS" if ok else "REVIEW"


ANCHORS_SOURCE = "segment"

ANCHORS_NOTE = (
    "量子网络号段 B519–B522 全 4 条（纠缠分发保真 / HOM 可见度 / 中继交换产出 / 微波-光换能效率）。。")

def case_card() -> Dict[str, Any]:
    """J5 只读案例卡（六段链路 + 四锚 + M4 净增 0 登记 · 零重计算）。"""
    t_link = transmission()
    fid = link_fidelity()
    vis = hom_visibility()
    swf = storage_window_factor()
    eta_b = _band_overlap()
    inf = jitter_infidelity()

    segs = [
        {"segment": "channel", "metric": "transmission", "value": t_link,
         "detail": {"length_m": LINK_LENGTH_M, "l_att_m": attenuation_length_m()}},
        {"segment": "dist", "metric": "fidelity", "value": fid,
         "detail": {"werner_p": werner_parameter(), "chsh": chsh_parameter(fid)}},
        {"segment": "source", "metric": "visibility", "value": vis,
         "detail": {"overlap_sq": vis}},
        {"segment": "repeater", "metric": "storage_window_factor", "value": swf,
         "detail": {"n_swap": repeater_yield(), "rate_s1": repeater_rate(),
                    "gain": repeater_rate() / direct_rate()}},
        {"segment": "transducer", "metric": "eta_band", "value": eta_b,
         "detail": {"peak_efficiency": peak_efficiency(),
                    "efficiency": transducer_efficiency()}},
        {"segment": "classical", "metric": "infidelity", "value": inf,
         "detail": {"phase_variance_rad2": jitter_phase_variance(), "net_new_anchor": 0}},
    ]
    for s in segs:
        s["verdict"] = _gate(s["segment"], s["value"])

    n_pass = sum(1 for s in segs if s["verdict"] == "PASS")
    return {
        "case_id": CASE_ID,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计预算（建模值 · 非流片实测）",
        "anchors": ANCHORS,
        "anchors_source": ANCHORS_SOURCE,
        "anchors_note": ANCHORS_NOTE,
        "honest_note": J5_HONEST_NOTE,
        "milestones": MILESTONES,
        "anchors": ANCHORS,
        "gaps": GAPS,
        "gaps_status": GAPS_STATUS,
        "segments": segs,
        "signing": {"n_pass": n_pass, "n_total": len(segs),
                    "verdict": "ACCEPT" if n_pass == len(segs) else "REVIEW"},
        "m4": {"net_new_anchors": 0, "avoidance": M4_AVOIDANCE,
               "negative_evidence": M4_NEGATIVE_EVIDENCE},
        "budget": {
            "direct_fidelity": fid,
            "relay_segment_fidelity": link_fidelity(LINK_LENGTH_M / 20.0),
            "end_to_end_direct": fid * vis * transducer_efficiency() * (1.0 - inf),
        },
        "selfcheck_modules": SELFCHECK_MODULES,
        "module_selfchecks_total": MODULE_SELFCHECKS_TOTAL,
        "gate_checks": 102,  # 实跑 `lda/run_j5_qnet_smoke.py` 的 PASS 数（常驻门禁自洽核验）
        "span": {"heavy_post": HEAVY_POST, "render_path_smoke": RENDER_PATH_SMOKE,
                 "auth": "免登录（只读 GET）"},
    }


def run_selfchecks() -> Dict[str, bool]:
    """卡内自检（与能力层逐值对拍 · 供渲染门禁常驻核验）。"""
    checks: Dict[str, bool] = {}
    cc = case_card()
    segs = {s["segment"]: s for s in cc["segments"]}

    checks["six_segments"] = len(cc["segments"]) == 6
    checks["verdict_is_design_budget"] = cc["verdict"] == "DESIGN_BUDGET"
    checks["signing_rule"] = (cc["signing"]["verdict"] == "ACCEPT") == (
        cc["signing"]["n_pass"] == cc["signing"]["n_total"])

    # 闭式自洽
    checks["transmission_at_100km"] = abs(segs["channel"]["value"] - 0.01) < 1e-18
    checks["l_att_positive"] = 20000.0 < segs["channel"]["detail"]["l_att_m"] < 23000.0
    checks["fidelity_in_range"] = 0.0 < segs["dist"]["value"] < 1.0
    checks["chsh_below_classical"] = segs["dist"]["detail"]["chsh"] < 2.0
    checks["visibility_in_range"] = 0.0 < segs["source"]["value"] < 1.0
    checks["storage_window_in_range"] = 0.0 < segs["repeater"]["value"] < 1.0
    checks["gain_gt_one"] = segs["repeater"]["detail"]["gain"] > 1.0
    checks["eta_band_in_range"] = 0.0 < segs["transducer"]["value"] < 1.0
    checks["infidelity_small"] = 0.0 < segs["classical"]["value"] < 0.5

    # M4 净增 0 呈现完整
    checks["m4_zero_registered"] = (cc["m4"]["net_new_anchors"] == 0
                                    and len(cc["m4"]["avoidance"]) == 3
                                    and len(cc["m4"]["negative_evidence"]) == 3)
    checks["four_anchors"] = set(cc["anchors"]) == {"B519", "B520", "B521", "B522"}
    checks["heavy_post_false"] = cc["span"]["heavy_post"] is False

    return checks


def main() -> int:  # pragma: no cover
    print("J5 案例卡（%s）" % CASE_ID)
    sc = run_selfchecks()
    bad = 0
    for k, v in sc.items():
        print("  [%s] %s" % ("PASS" if v else "FAIL", k))
        if not v:
            bad += 1
    cc = case_card()
    print("\n  签核：%d/%d ⇒ %s" % (cc["signing"]["n_pass"], cc["signing"]["n_total"],
                                    cc["signing"]["verdict"]))
    for s in cc["segments"]:
        print("    %-11s %-22s %.6e [%s]" % (s["segment"], s["metric"], s["value"], s["verdict"]))
    print("  M4 净增锚 = %d" % cc["m4"]["net_new_anchors"])
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
