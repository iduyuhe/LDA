"""光子传感器案例卡 + 客户自助设计向导（WebUI 只读端点数据源）· PS-M7。

═══════════════════════════════════════════════════════════════════════════
定位
═══════════════════════════════════════════════════════════════════════════
光子传感器征程 PS-M0…PS-M6 **已机器自检通过**的能力的**只读对外窗口**：让客户自助
「**选架构 → 调环半径/品质因数/待测折射率变化 → 读指标 → 看 GDS/DRC/LVS 签核 →
看征程报告**」。与 `/api/pm_demo`（光子存储）、`/api/oi_demo`（光联接）、
`/api/qchip_demo`（光量子）并列，同属「公开只读验货」类。

🔴 **零重计算**（与站内 cpo_array / design_* 等重算端点不同）：本模块**不 import
求解器 / numpy / scipy / P&R、不解析 GDS** —— 全部数字取自
  ① **闭式算术**（微环 FSR / 线宽 / 谐振位移 / LOD_intrinsic / 噪声模型 LOD_real）；
  ② **参考常量**（各架构的 n_eff / Γ_clad / n_g / S 取自 PS-M3 平板 HF 闭式；集成
     预算取自 PS-M6 自检）；
  ③ 对已提交产出物只 `os.path.getsize` / 读一行 JSON 的元信息。
⇒ **无 DoS 面**，故**免登录、不进 HEAVY_POST_PATHS**，与 `/api/verification_ledger`、
`/api/schip_demo` 同属「公开只读验货」类。

🔴 **不伪装实测**：`verdict` 恒为 `DESIGN_BUDGET`（**非** ACCEPT/PASS），返回体自带
`honest_note`；本卡是**设计预算**，不是流片实测签核。

🔴 **LLM 不进判决路径**：本模块不含任何模型/网络调用（门禁以 `ast` 遍历真实 import 断言）。

═══ 跨源一致性 ═══
`ARCHITECTURES` / `INTEGRATION_REF` 是**参考快照**，必须与平台模块现值逐位一致 ——
由门禁 `run_sensor_panel_smoke` 的 B 节对 `lda_l2.ps_m3` / `lda_l2.ps_m6` 现算值做
跨源校验（漂移即红）。结果源见 `examples/photo_sensor/lda_ps_sensor_report.json`。
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

__all__ = [
    "WAVELENGTH_UM",
    "ARCHITECTURES",
    "KNOBS",
    "DEFAULT_NOISE",
    "INTEGRATION_REF",
    "MILESTONES",
    "GAPS",
    "HONEST_NOTE",
    "design_options",
    "compute_metrics",
    "case_card",
    "run_selfchecks",
]


# ---------------------------------------------------------------------------
# 物理常数（与 lda_l2.ps_m2 单一真源一致 —— 门禁 B 节跨源校验）
# ---------------------------------------------------------------------------
WAVELENGTH_UM = 1.55
H_PLANCK = 6.62607015e-34        # J·s
C_LIGHT = 299792458.0            # m/s
E_CHARGE = 1.602176634e-19       # C
DN_DT_SI = 1.86e-4               # Si 热光系数 /K


# 噪声模型默认参数（镜像 ps_m2.DEFAULT_NOISE；门禁 B 节逐项校验）
DEFAULT_NOISE: Dict[str, float] = {
    "power_W": 1e-3,
    "dt_s": 1e-3,
    "eta": 0.8,
    "NEP_W_per_sqrtHz": 1e-12,
    "RIN_per_Hz": 1e-14,
    "Idark_A": 1e-9,
    "R_AW": 1.0,
    "dn_dT": DN_DT_SI,
    "dT_stability_K": 5e-3,
    "CMR": 1.0,
    "T_bg": 1.0,
    "T_min": 0.1,
}


# ---------------------------------------------------------------------------
# 架构参考快照（n_eff / Γ_clad / n_g / S 取自 PS-M3 平板波导 HF 闭式，已 FD 验证）
# 🔴 必须与 examples/photo_sensor/lda_ps_sensor_report.json 的 architectures 逐位一致
# ---------------------------------------------------------------------------
ARCHITECTURES: List[Dict[str, Any]] = [
    {
        "id": "slab_hf_water",
        "label": "微环 · SOI 平板波导（水包层 · 真实传感窗）",
        "source": "PS-M3 · HF 闭式（FD 验证）",
        "n_eff": 2.839070582845509,
        "gamma_clad": 0.1844231876617586,
        "n_g": 3.589250698523721,
        "S_bulk_nm_per_riu": 37.30945285270887,
    },
    {
        "id": "slab_hf_oxide",
        "label": "微环 · SOI 平板波导（氧化包层 · 上限对照）",
        "source": "PS-M3 · HF 闭式（FD 验证）",
        "n_eff": 2.849463699938886,
        "gamma_clad": 0.1895276721215868,
        "n_g": 3.5786963035153545,
        "S_bulk_nm_per_riu": 41.599062797877416,
    },
]


# ---------------------------------------------------------------------------
# 集成参考快照（阵列 / 读出 / 对准 / 预算 —— 取自 PS-M6 自检）
# 🔴 必须与 lda_l2.ps_m6 现算值一致（门禁 B 节跨源校验）
# ---------------------------------------------------------------------------
INTEGRATION_REF: Dict[str, float] = {
    "n_ch": 8.0,
    "crosstalk_db": -6.2457643677770305,
    "pitch_min_um": 2.583514896614207,
    "channel_density_per_mm": 1000.0,
    "v_n_uV": 203.51773878460816,
    "f_3dB_Hz": 159154943.09189534,
    "align_eta": 0.6065306597126334,
    "align_il_db": 2.171472409516259,
    "channel_split_loss_db": 9.030899869919436,
    "total_optical_loss_db": 11.302372279435694,
    "frame_rate_hz": 25000000.0,
    "area_mm2": 0.00047999999999999996,
    "LOD_readout_riu": 3.6666183727421164e-07,
}


# ---------------------------------------------------------------------------
# 向导旋钮（客户可调；闭式现算，微秒级 ⇒ 免登录 GET 安全）
# ---------------------------------------------------------------------------
KNOBS: List[Dict[str, Any]] = [
    {"id": "R_um", "label": "微环半径", "unit": "µm",
     "default": 10.0, "min": 3.0, "max": 50.0},
    {"id": "Q", "label": "品质因数 Q", "unit": "—",
     "default": 10000.0, "min": 1000.0, "max": 1000000.0},
    {"id": "delta_n", "label": "待测折射率变化 Δn", "unit": "RIU",
     "default": 0.001, "min": 1e-5, "max": 0.01},
]


# ---------------------------------------------------------------------------
# 征程里程碑（历史事实；gate = 常驻 CI 门禁；n_checks = 该门禁判据数）
# ---------------------------------------------------------------------------
MILESTONES: List[Dict[str, Any]] = [
    {"id": "PS-M0", "title": "换能器物理链（S/LOD/主权流片链）", "gate": "run_ps_m0_smoke", "n_checks": 8},
    {"id": "PS-M2", "title": "指标框架 + LOD_real 噪声模型", "gate": "run_ps_m2_smoke", "n_checks": 7},
    {"id": "PS-M3", "title": "灵敏度物理链对齐（HF 闭式 ⇄ FD）", "gate": "run_ps_m3_smoke", "n_checks": 9},
    {"id": "PS-M4", "title": "表面功能化 / 生物化学传感", "gate": "run_ps_m4_smoke", "n_checks": 14},
    {"id": "PS-M5", "title": "微流控 / Lab-on-chip 多物理场", "gate": "run_ps_m5_smoke", "n_checks": 18},
    {"id": "PS-M6", "title": "规模与集成（阵列/读出/对准）", "gate": "run_ps_m6_smoke", "n_checks": 30},
]


# ---------------------------------------------------------------------------
# 诚实边界 / 未闭合缺口（非本卡粉饰对象）
# ---------------------------------------------------------------------------
GAPS: List[Dict[str, Any]] = [
    {"id": "G_temp_drift", "status": "开放", "note": "LOD_real 由温漂主导（LOD_temp ≫ LOD_elec）⇒ 须片载温控/referencing"},
    {"id": "G_no_tapeout", "status": "开放", "note": "各里程碑为自研求解器 + 闭式预算，非流片实测签核"},
    {"id": "G_pdk_geometry", "status": "开放", "note": "架构参考几何为设计示例（SOI 平板 220 nm / 水包层 @1550 nm）"},
    {"id": "G_referencing", "status": "开放", "note": "共模抑制（CMR）仅在 PS-M3 情景中作为对照量，未入现役设计点"},
]


HONEST_NOTE = (
    "本卡为**设计预算**（DESIGN_BUDGET），非流片实测签核（无 ACCEPT/PASS 语义）；"
    "指标由闭式物理律现算、参考常量取自 PS-M0…PS-M6 已机器自检通过的求解器链路；"
    "架构为设计示例几何、非特定代工厂 PDK 表征；LOD_real 受温漂主导，"
    "真实器件须片载温控 / referencing 方能逼近 LOD_intrinsic。"
    "LLM 不进判决路径（本模块无任何模型/网络调用）。"
)


# ---------------------------------------------------------------------------
# 结果源装载（优雅降级：生产可能不含 examples/ ⇒ 不可抛错）
# ---------------------------------------------------------------------------
_ARTIFACT_DIRS = (
    os.path.join("examples", "photo_sensor"),
    os.path.join("lda", "examples", "photo_sensor"),
)
_REPORT_NAME = "lda_ps_sensor_report.json"
_GDS_NAME = "lda_ps_sensor_ring.gds"


def _repo_root(repo_root: Optional[str] = None) -> str:
    if repo_root:
        return os.path.abspath(repo_root)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_report(repo_root: Optional[str] = None) -> Dict[str, Any]:
    root = _repo_root(repo_root)
    for d in _ARTIFACT_DIRS:
        fp = os.path.join(root, d, _REPORT_NAME)
        if os.path.isfile(fp):
            try:
                with open(fp, encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return {}
    return {}


def _gds_size(repo_root: Optional[str] = None) -> Optional[int]:
    root = _repo_root(repo_root)
    for d in _ARTIFACT_DIRS:
        fp = os.path.join(root, d, _GDS_NAME)
        if os.path.isfile(fp):
            try:
                return int(os.path.getsize(fp))
            except OSError:
                return None
    return None


# ---------------------------------------------------------------------------
# 闭式：噪声模型（镜像 ps_m2.lod_real —— 门禁 B 节跨源校验）
# ---------------------------------------------------------------------------
def _photon_energy_J(wl_um: float) -> float:
    return H_PLANCK * C_LIGHT / (wl_um * 1e-6)


def _resonance_slope_max(T_bg: float, T_min: float, FWHM_nm: float) -> float:
    """Lorentzian 凹陷陡峭点最大斜率 |dT/dλ|_max = (T_bg−T_min)·(3√3/4)/Γ。"""
    depth = T_bg - T_min
    if FWHM_nm <= 0:
        return float("inf")
    return depth * (3.0 * math.sqrt(3.0) / 4.0) / FWHM_nm


def _electronic_fraction_noise(noise: Dict[str, float]) -> Dict[str, float]:
    """四种电学噪声源平方合成（散粒 / NEP 热 / 激光 RIN / 暗电流）。"""
    power_W = noise["power_W"]
    dt_s = noise["dt_s"]
    eta = noise["eta"]
    NEP = noise["NEP_W_per_sqrtHz"]
    RIN = noise["RIN_per_Hz"]
    Idark = noise["Idark_A"]
    R_AW = noise["R_AW"]

    df = 1.0 / (2.0 * dt_s)
    if power_W > 0 and dt_s > 0:
        n_ph = eta * power_W * dt_s / _photon_energy_J(1.55)
        frac_shot = 1.0 / math.sqrt(n_ph) if n_ph > 0 else float("inf")
    else:
        frac_shot = float("inf")
    sigma_P_thermal = NEP * math.sqrt(df)
    frac_thermal = sigma_P_thermal / power_W if power_W > 0 else float("inf")
    frac_RIN = RIN * math.sqrt(df)
    I = R_AW * power_W
    sigma_I_dark = math.sqrt(2.0 * E_CHARGE * Idark * df)
    frac_dark = sigma_I_dark / I if I > 0 else float("inf")
    frac_total = math.sqrt(frac_shot ** 2 + frac_thermal ** 2
                           + frac_RIN ** 2 + frac_dark ** 2)
    return {
        "df_Hz": df,
        "frac_shot": frac_shot,
        "frac_thermal": frac_thermal,
        "frac_RIN": frac_RIN,
        "frac_dark": frac_dark,
        "frac_total": frac_total,
    }


def _lod_real(S_nm_per_riu: float, Q: float, wl_um: float,
              noise: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """含噪探测极限 LOD_real = √(LOD_elec² + LOD_temp²)（几何无关，与 S 解耦的温漂项）。"""
    if noise is None:
        noise = dict(DEFAULT_NOISE)
    FWHM_nm = wl_um * 1000.0 / Q if Q > 0 else float("inf")
    slope = _resonance_slope_max(noise["T_bg"], noise["T_min"], FWHM_nm)
    enf = _electronic_fraction_noise(noise)
    delta_lambda_elec = enf["frac_total"] / slope if slope > 0 else float("inf")
    LOD_elec = delta_lambda_elec / S_nm_per_riu if S_nm_per_riu > 0 else float("inf")
    dT_eff = noise["dT_stability_K"] / max(noise["CMR"], 1e-30)
    LOD_temp = noise["dn_dT"] * dT_eff
    LOD_real = math.sqrt(LOD_elec ** 2 + LOD_temp ** 2)
    return {
        "FWHM_nm": FWHM_nm,
        "slope_per_nm": slope,
        "frac_total": enf["frac_total"],
        "delta_lambda_elec_nm": delta_lambda_elec,
        "LOD_elec_riu": LOD_elec,
        "dT_eff_K": dT_eff,
        "LOD_temp_riu": LOD_temp,
        "LOD_real_riu": LOD_real,
    }


# ---------------------------------------------------------------------------
# 架构 / 旋钮取值（越界即钳制；非法 id 退回首架构）
# ---------------------------------------------------------------------------
def _pick_arch(arch_id: Optional[str]) -> Dict[str, Any]:
    for a in ARCHITECTURES:
        if a["id"] == arch_id:
            return dict(a)
    if ARCHITECTURES:
        return dict(ARCHITECTURES[0])
    # 空表兜底（门禁依法可变红，而非崩溃）：返回零灵敏度占位 ⇒ 指标退化为 inf ⇒ 红标
    return {"id": "none", "label": "（架构表为空）", "source": "—",
            "n_eff": 0.0, "gamma_clad": 0.0, "n_g": 0.0, "S_bulk_nm_per_riu": 0.0}


def _clamp(v: Optional[float], lo: float, hi: float, default: float) -> float:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(x):
        return float(default)
    return float(min(max(x, lo), hi))


def _design_params(R_um: Optional[float], Q: Optional[float],
                   delta_n: Optional[float]) -> Dict[str, float]:
    k = {k["id"]: k for k in KNOBS}
    return {
        "R_um": _clamp(R_um, k["R_um"]["min"], k["R_um"]["max"], k["R_um"]["default"]),
        "Q": _clamp(Q, k["Q"]["min"], k["Q"]["max"], k["Q"]["default"]),
        "delta_n": _clamp(delta_n, k["delta_n"]["min"], k["delta_n"]["max"],
                          k["delta_n"]["default"]),
    }


# ---------------------------------------------------------------------------
# 指标现算（全闭式）
# ---------------------------------------------------------------------------
def compute_metrics(arch: Dict[str, Any], d: Dict[str, float],
                    wl_um: float = WAVELENGTH_UM) -> Dict[str, Any]:
    """由架构参考常量 + 设计旋钮闭式现算传感器指标。"""
    n_g = float(arch["n_g"])
    S = float(arch["S_bulk_nm_per_riu"])
    R_um = float(d["R_um"])
    Q = float(d["Q"])
    delta_n = float(d["delta_n"])

    # 🔴 非法参数（R≤0 / Q≤0 / S≤0 / n_g≤0）⇒ 如实返回 inf（红标），不静默给假数
    if R_um > 0 and n_g > 0:
        fsr_nm = (wl_um ** 2) / (n_g * 2.0 * math.pi * R_um) * 1000.0
    else:
        fsr_nm = float("inf")
    fwhm_nm = wl_um * 1000.0 / Q if Q > 0 else float("inf")
    shift_nm = S * delta_n
    lod_intrinsic = fwhm_nm / S if S > 0 else float("inf")
    lod = _lod_real(S, Q, wl_um)
    dominant = "temp" if lod["LOD_temp_riu"] >= lod["LOD_elec_riu"] else "elec"
    # 由 S 与 n_g 反推的物理灵敏度 dneff/dn_clad（= S·n_g/λ_nm）
    dneff_dn = S * n_g / (wl_um * 1000.0)

    return {
        "S_nm_per_riu": S,
        "dneff_dn_clad": dneff_dn,
        "n_eff": float(arch["n_eff"]),
        "n_g": n_g,
        "gamma_clad": float(arch["gamma_clad"]),
        "FSR_nm": fsr_nm,
        "FWHM_nm": fwhm_nm,
        "resonance_shift_nm": shift_nm,
        "LOD_intrinsic_riu": lod_intrinsic,
        "slope_per_nm": lod["slope_per_nm"],
        "LOD_elec_riu": lod["LOD_elec_riu"],
        "LOD_temp_riu": lod["LOD_temp_riu"],
        "LOD_real_riu": lod["LOD_real_riu"],
        "dominant_limit": dominant,
    }


# ---------------------------------------------------------------------------
# 向导 / 案例卡
# ---------------------------------------------------------------------------
def design_options() -> Dict[str, Any]:
    """向导结构（步骤 + 架构选择 + 旋钮）。"""
    return {
        "steps": [
            "① 选架构（换能器几何 / 包层口径）",
            "② 调环半径 R / 品质因数 Q / 待测 Δn",
            "③ 读指标（FSR / 线宽 / 谐振位移 / LOD_intrinsic / LOD_real）",
            "④ 看 GDS/DRC/LVS 签核（PS-M0 主权流片链产出的真 GDSII）",
            "⑤ 看征程报告（PS-M0…PS-M6 门禁）",
        ],
        "architectures": [
            {"id": a["id"], "label": a["label"],
             "S_nm_per_riu": a["S_bulk_nm_per_riu"], "n_g": a["n_g"]}
            for a in ARCHITECTURES
        ],
        "knobs": [dict(k) for k in KNOBS],
    }


def case_card(arch_id: Optional[str] = None, R_um: Optional[float] = None,
              Q: Optional[float] = None, delta_n: Optional[float] = None,
              repo_root: Optional[str] = None) -> Dict[str, Any]:
    """传感器案例卡（只读 GET 的数据源）。

    🔴 零重计算：全部数字来自闭式算术 + 参考常量 + 已提交产出物元信息。
    """
    arch = _pick_arch(arch_id)
    d = _design_params(R_um, Q, delta_n)
    metrics = compute_metrics(arch, d)

    rep = _load_report(repo_root)
    sig = rep.get("signoff") if isinstance(rep, dict) else None
    gds_file_bytes = _gds_size(repo_root)
    if isinstance(sig, dict) and sig:
        signoff = {
            "artifact": str(sig.get("artifact") or _GDS_NAME),
            "gds_bytes": int(sig.get("gds_bytes") or 0),
            "n_elements": int(sig.get("n_elements") or 0),
            "drc_all_pass": bool(sig.get("drc_all_pass")),
            "n_drc_checked": int(sig.get("n_drc_checked") or 0),
            "lvs_present": bool(sig.get("lvs_present")),
            "blocked_nets": int(sig.get("blocked_nets") or 0),
            "gds_file_bytes": int(gds_file_bytes or 0),
            "available": True,
        }
    else:
        # 优雅降级：结果源缺失（如生产未随包 examples/）⇒ 如实标注不可用，不抛错
        signoff = {
            "artifact": _GDS_NAME,
            "gds_bytes": 0,
            "n_elements": 0,
            "drc_all_pass": False,
            "n_drc_checked": 0,
            "lvs_present": False,
            "blocked_nets": 0,
            "gds_file_bytes": int(gds_file_bytes or 0),
            "available": False,
        }

    return {
        "endpoint": "/api/sensor_demo",
        "verdict": "DESIGN_BUDGET",
        "honest_note": HONEST_NOTE,
        "design": {
            "arch_id": arch["id"],
            "arch_label": arch["label"],
            "wavelength_um": WAVELENGTH_UM,
            "R_um": d["R_um"],
            "Q": d["Q"],
            "delta_n": d["delta_n"],
        },
        "metrics": metrics,
        "integration": {k: float(v) for k, v in INTEGRATION_REF.items()},
        "signoff": signoff,
        "wizard": design_options(),
        "milestones": [dict(m) for m in MILESTONES],
        "gaps": [dict(g) for g in GAPS],
    }


# ---------------------------------------------------------------------------
# 自检（红线写成自检项；门禁复用）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    import ast

    res: Dict[str, bool] = {}

    # ① 零外部框架 / 无模型调用（ast 遍历真实 import —— 不用源码字符串 in，见血案）
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    banned = {"numpy", "scipy", "torch", "sklearn", "requests", "urllib",
              "socket", "http", "transformers", "openai"}
    res["no_banned_import"] = not (mods & banned)

    # ② verdict 不伪装实测
    res["verdict_not_accept"] = True  # 见下方 card 断言

    # ③ 诚实边界齐备
    res["honest_note_has_boundary"] = all(
        kw in HONEST_NOTE for kw in ("设计预算", "非流片实测签核", "LLM 不进判决路径"))

    # ④ 架构表非空且字段齐
    res["architectures_wellformed"] = bool(ARCHITECTURES) and all(
        {"id", "n_eff", "n_g", "gamma_clad", "S_bulk_nm_per_riu"} <= set(a)
        for a in ARCHITECTURES)

    # ⑤ 集成参考非空
    res["integration_ref_nonempty"] = len(INTEGRATION_REF) >= 10

    # ⑥ 卡可用 + verdict 是 DESIGN_*
    card = case_card()
    res["card_ok"] = bool(card) and card.get("verdict") == "DESIGN_BUDGET"
    res["verdict_not_accept"] = card.get("verdict") not in ("PASS", "ACCEPT", "OK")

    # ⑦ 物理合理：S>0；FSR>0；LOD_intrinsic>0；LOD_real 有限
    m = card["metrics"]
    res["metrics_sane"] = (
        m["S_nm_per_riu"] > 0 and m["FSR_nm"] > 0
        and m["LOD_intrinsic_riu"] > 0 and math.isfinite(m["LOD_real_riu"]))

    # ⑧ 半径↑ ⇒ FSR↓（反向探针：单调性必成立）
    m_big = compute_metrics(_pick_arch(None), _design_params(20.0, None, None))
    m_small = compute_metrics(_pick_arch(None), _design_params(5.0, None, None))
    res["fsr_decreases_with_R"] = m_small["FSR_nm"] > m_big["FSR_nm"]

    # ⑨ Q↑ ⇒ LOD_intrinsic↓（单调）
    q_hi = compute_metrics(_pick_arch(None), _design_params(None, 1e5, None))
    q_lo = compute_metrics(_pick_arch(None), _design_params(None, 1e3, None))
    res["lod_intrinsic_decreases_with_Q"] = (
        q_hi["LOD_intrinsic_riu"] < q_lo["LOD_intrinsic_riu"])

    # ⑩ Δn 符号：Δλ = S·Δn 符号随 Δn（反向探针）
    res["shift_sign_follows_delta_n"] = (
        compute_metrics(_pick_arch(None), _design_params(None, None, 0.01))["resonance_shift_nm"] > 0)

    # ⑪ 非法参数红标：零 Q / 零 S ⇒ 无限大 LOD（不静默给假数）
    res["zero_params_red_flag"] = (
        not math.isfinite(compute_metrics(_pick_arch(None), {"R_um": 10.0, "Q": 0.0, "delta_n": 0.001})["LOD_intrinsic_riu"])
        or compute_metrics(_pick_arch(None), {"R_um": 10.0, "Q": 0.0, "delta_n": 0.001})["LOD_intrinsic_riu"] == float("inf"))

    # ⑫ 温漂主导如实：默认点 LOD_temp ≫ LOD_elec（诚实边界 G_temp_drift 的机器证据）
    res["temp_dominated_by_default"] = m["LOD_temp_riu"] > 100.0 * m["LOD_elec_riu"]

    # ⑬ 优雅降级：错误路径下不抛错、available=False
    bad = case_card(repo_root=os.path.join(os.sep, "__definitely_not_here__"))
    res["graceful_degrade"] = bad["signoff"]["available"] is False

    if verbose:
        for k, v in res.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    return all(res.values())


if __name__ == "__main__":
    print(json.dumps(case_card(), indent=2, ensure_ascii=False))
    print("\nselfcheck:", run_selfchecks(verbose=True))
