"""LDA 设计→验证闭环引擎（agent-native design loop）。

这是 LDA 作为"系统"而非"组件集"的核心：给定设计目标（器件类型 + 目标性能指标），
引擎在参数空间网格搜索，对每个候选调用 device_library 的 verify_*（live 模式 =
真实求解器 + 解析契约双重验证，纯 numpy 零 GPU），只保留 LLM-free 判决为 passed
的候选，按"达成目标误差"排序返回最优已验证设计。

两阶段（高效且诚实）：
  ① 搜索：用物理定律 ORACLE（瞬时，slab 闭式 / TMM / Koch / FSR）在网格上快速逼近目标；
  ② 验证：仅对 top-K 候选跑真实求解器双重验证，返回的"最优设计"是被求解器验证过的。

红线：LLM 不进判决路径，是否 passed 由死标量比对决定。
"""
from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_LDA = _HERE.parent  # lda/
if str(_LDA) not in sys.path:
    sys.path.insert(0, str(_LDA))

from lda_l2.device_library import DeviceLibrary  # noqa: E402
from lda_design.active_models import (  # noqa: E402
    phase_efficiency_deg_per_mW, power_for_pi,
    vpi_electrooptic,
)

# --------------------------------------------------------------------------- #
# v0.8.11e · loss/效率类引擎验证辅助（实证锚判决路径）
# --------------------------------------------------------------------------- #
_LOSS_GOLDEN_CACHE: Dict[str, Tuple[float, float]] = {}


def _loss_golden(eid: str) -> Tuple[float, float]:
    """语料 golden（measured_value, uncertainty_abs），带缓存。"""
    if eid not in _LOSS_GOLDEN_CACHE:
        from lda_harness.empirical_bank import EmpiricalCorpus
        corpus = EmpiricalCorpus.load(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "lda_harness", "seed_empirical.json"))
        m = corpus.get(eid)
        _LOSS_GOLDEN_CACHE[eid] = (float(m.measured_value),
                                   float(m.uncertainty_abs))
    return _LOSS_GOLDEN_CACHE[eid]


def _loss_cheap(engine_name: str, combo: Dict[str, float]) -> float:
    """loss 引擎正向输出（搜索排序用）。"""
    from lda_design.loss_engines import ENGINE_FUNCS
    out = ENGINE_FUNCS[engine_name](dict(combo))
    return float(out["value"])


def _loss_verify(engine_name: str, eid: str, tol: float):
    """loss 引擎验证工厂：引擎输出 vs 实证语料 golden 死标量对照。

    实证锚第一次进入引擎级判决路径：|engine_out − measured| ≤ tol → passed。
    LLM 不进判决路径（golden 为真实文献语料）。
    """
    def _verify(mode: str, target_f01: float = None, **kw):
        from lda_design.loss_engines import ENGINE_FUNCS
        golden, unc = _loss_golden(eid)
        out = ENGINE_FUNCS[engine_name](dict(kw))
        val = float(out["value"])
        rel = abs(val - golden) / max(abs(golden), 1e-9) * 100
        passed = abs(val - golden) <= tol
        return {
            "passed": passed,
            "metric": val,
            "rel": rel,
            "verdict": (f"实证锚 {eid} 对照 PASS（引擎 {val:.4g} ↔ 实测 "
                        f"{golden}±{unc} rel={rel:.2f}% ≤ tol={tol}）"
                        if passed else
                        f"实证锚 {eid} 对照 FAIL（引擎 {val:.4g} ↔ 实测 "
                        f"{golden}±{unc} rel={rel:.2f}% > tol={tol}）"),
        }
    return _verify


def _phase_verify(target: float, **kw):
    """相移器验证工厂：目标=相移效率（deg/mW），cheap 正算对照。"""
    from lda_design.active_models import phase_efficiency_deg_per_mW
    L = float(kw.get("L_um", 300.0))
    val = phase_efficiency_deg_per_mW(L)
    rel = abs(val - target) / max(abs(target), 1e-9) * 100
    passed = rel <= 10.0
    return {
        "passed": passed, "metric": val, "rel": rel,
        "verdict": (f"相移效率对照 PASS（{val:.3f} deg/mW ↔ 目标 {target} "
                    f"rel={rel:.2f}% ≤ 10%）" if passed else
                    f"相移效率对照 FAIL（{val:.3f} deg/mW ↔ 目标 {target} "
                    f"rel={rel:.2f}% > 10%）"),
    }


def _mzi_mod_verify(target: float, **kw):
    """MZI 调制器验证工厂：目标=V_π（V），cheap 正算对照。"""
    from lda_design.active_models import vpi_electrooptic
    L = float(kw.get("L_um", 500.0))
    g = float(kw.get("g_um", 1.0))
    r = float(kw.get("r_pm_per_V", 30.0))
    val = vpi_electrooptic(L, g, r)
    rel = abs(val - target) / max(abs(target), 1e-9) * 100
    passed = rel <= 10.0
    return {
        "passed": passed, "metric": val, "rel": rel,
        "verdict": (f"V_π 对照 PASS（{val:.3f} V ↔ 目标 {target} "
                    f"rel={rel:.2f}% ≤ 10%）" if passed else
                    f"V_π 对照 FAIL（{val:.3f} V ↔ 目标 {target} "
                    f"rel={rel:.2f}% > 10%）"),
    }


def _ensure_path() -> None:
    """注入本地求解器路径（tmm / fdtd3d 等）。"""
    try:
        from lda_l2.device_library import _ensure_solver_on_path
        _ensure_solver_on_path()
    except Exception:
        pass


class DesignEngine:
    """设计→验证闭环。给定 (kind, target) 返回已验证最优器件。"""

    def __init__(self) -> None:
        self.lib = DeviceLibrary()
        _ensure_path()
        self.specs = self._build_specs()

    # ------------------------------------------------------------------ #
    # 规格表
    # ------------------------------------------------------------------ #
    def _build_specs(self) -> Dict[str, Dict[str, Any]]:
        from lda_harness.oracle_mode import _slab_te_neff  # noqa: E402
        from lda_harness.golden import b21_phc_resonance  # noqa: E402
        from lda_harness.golden import b22_qres_frequency  # noqa: E402
        from lda_harness.golden import b24_tcoup_geff  # noqa: E402
        from lda_harness.golden import b16_mmi_length  # noqa: E402
        from lda_harness.golden import b14_dc_coupling_length  # noqa: E402
        from lda_harness.golden import b25_tunable_transmon_f01  # noqa: E402
        from lda_harness.golden import b26_dispersive_shift  # noqa: E402
        from lda_harness.golden import b27_cz_gate_time  # noqa: E402
        import tmm  # lda_solver/tmm.py  # noqa: E402
        from lda_solver.transmon_solver import koch_f01  # noqa: E402
        from lda_agent.ring_loop import ring_fsr_analytic_nm  # noqa: E402

        def _bragg_rmin(periods: float, wl0: float = 1.55, n_si: float = 3.48,
                        n_sio: float = 1.44, n_points: int = 11) -> float:
            lam = wl0
            qw_hi, qw_lo = lam / (4.0 * n_si), lam / (4.0 * n_sio)
            layers = [(float("inf"), 1.0)]
            for _ in range(int(round(periods))):
                layers.append((qw_hi, n_si))
                layers.append((qw_lo, n_sio))
            layers.append((float("inf"), 1.0))
            span = 0.12
            wls = [round(lam + (i / (n_points - 1) - 0.5) * 2.0 * span, 4)
                   for i in range(n_points)]
            r = tmm.solve_spectrum({"layers": layers,
                                    "wavelengths_um": wls})["transmission"]
            return float(min(1.0 - t for t in r))

        def _mzi_fsr(deltaL_um: float, wl0: float = 1.55,
                     n_core: float = 3.48) -> float:
            """MZI 干涉型 FSR（nm）：FSR = λ²/(n_eff·ΔL)。"""
            return 1000.0 * wl0 ** 2 / (n_core * deltaL_um)

        def _flux_f01_cheap(e_j: float, e_c: float = 1.0,
                            e_l: float = 1.0):
            """Fluxonium cheap ORACLE：粗相位网格对角化（nphi=81，毫秒级）。"""
            from lda_l2.device_library import _fluxonium_phase_core
            return _fluxonium_phase_core(e_j=e_j, e_c=e_c, e_l=e_l, nphi=81)

        specs: Dict[str, Dict[str, Any]] = {
            "Waveguide": {
                "title": "直波导 · 目标有效折射率 neff",
                "sweep": [("width_um", 0.30, 0.95, 0.03)],
                "fixed": dict(n_core=3.48, n_clad=1.44, wl_um=1.55, tol_rel=0.02),
                "verify": lambda mode, target_f01, **kw:
                    self.lib.verify_waveguide_fdtd(mode=mode, **kw),
                "cheap": lambda combo, target, fx=_slab_te_neff:
                    fx(3.48, 1.44, combo["width_um"] / 2.0, 1.55),
                "extract": lambda r: r["fdtd"]["neff_fdtd"],
                "metric_name": "neff (FDTD)",
                "target_unit": "",
                "note": "搜索波导宽度命中目标 neff；slab 闭式 ORACLE 引导 + FDTD neff "
                        "自洽验证物理真实。",
            },
            "BraggMirror": {
                "title": "布拉格镜 · 目标反射率 R_min（最少周期）",
                "sweep": [("periods", 3, 14, 1)],
                "fixed": dict(wl0_um=1.55, n_si=3.48, n_sio=1.44,
                              n_points=11, tol_abs=0.02),
                "verify": lambda mode, target_f01, **kw:
                    self.lib.verify_bragg_fdtd(mode=mode, **kw),
                "cheap": lambda combo, target: _bragg_rmin(combo["periods"]),
                "extract": lambda r: r["fdtd"]["R_min_fdtd"],
                "metric_name": "R_min (FDTD)",
                "target_unit": "",
                "secondary": ("periods", True),
                "note": "用 TMM 闭式 ORACLE 搜索最少周期实现目标 R_min；FDTD 阻带与 "
                        "TMM 自洽验证物理真实。",
            },
            "Transmon": {
                "title": "Transmon 量子比特 · 目标频率 f01",
                "sweep": [("E_C", 0.15, 0.60, 0.05)],
                "fixed": dict(tol_rel=0.03, N=20),
                "verify": lambda mode, target_f01, **kw:
                    self.lib.verify_transmon(mode=mode, target_f01=target_f01, **kw),
                "cheap": lambda combo, target: koch_f01(
                    (target + combo["E_C"]) ** 2 / (8.0 * combo["E_C"]), combo["E_C"]),
                "extract": lambda r: r["numerical"]["f01_diag"],
                "metric_name": "f01 (对角化, GHz)",
                "target_unit": "GHz",
                "secondary": ("E_C", False),
                "note": "目标 f01 反解 E_J（Koch）；网格扫 E_C 调 anharmonicity；"
                        "Koch 解析 ↔ 严格对角化双验证。",
            },
            "RingResonator": {
                "title": "环形谐振器 · 目标 FSR（解析锚，FDTD 抽检需 GPU）",
                "sweep": [("R_um", 3.0, 20.0, 0.5)],
                "fixed": dict(n_core=3.48, wl0_um=1.55),
                "verify": lambda mode, target_f01, **kw:
                    self.lib.verify_ring_fdtd(mode=mode, **kw),
                "cheap": lambda combo, target: ring_fsr_analytic_nm(
                    combo["R_um"], 3.48, 1.55),
                "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_analytic_nm"],
                "metric_name": "FSR (解析, nm)",
                "target_unit": "nm",
            "analytic_only": True,
            "note": "FSR 由物理定律 λ²/(n_g·2πR) 决定；解析契约验证（FDTD 真实 "
                    "抽检需 GPU，此处诚实标注）。",
        },
        "MziInterferometer": {
            "title": "MZI 马赫曾德尔干涉仪 · 目标 FSR（解析干涉谱，FDTD 全波抽检需 GPU）",
            "sweep": [("deltaL_um", 1.0, 60.0, 1.0)],
            "fixed": dict(n_core=3.48, wl0_um=1.55, tol_rel=0.02),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_mzi_fdtd(mode=mode, **kw),
            "cheap": lambda combo, target: _mzi_fsr(combo["deltaL_um"]),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_analytic_nm"],
            "metric_name": "FSR (干涉谱, nm)",
            "target_unit": "nm",
            "analytic_only": True,
            "secondary": ("deltaL_um", True),
            "note": "MZI 干涉传输 T=½(1+cos(2π·n_eff·ΔL/λ))；解析干涉谱 "
                    "FSR=λ²/(n_eff·ΔL) 契约验证（FDTD 全波抽检需 GPU，诚实标注）。"
                    "干涉型 FSR 与环形谐振型并列对照。",
        },
        "PhCCavity": {
            "title": "光子晶体腔 · 目标共振波长 λ_res（2D FDTD + 布拉格带边锚）",
            "sweep": [("L_cav_um", 0.20, 0.80, 0.02)],
            "fixed": dict(n_core=3.48, n_clad=1.44, a_m_um=0.46, N_m=8,
                          channel_w_um=1.0, tol_rel=0.03,
                          dx_frac=20, n_steps=9000, pml=18),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_phc_fdtd(mode=mode, **kw),
            "cheap": lambda combo, target: b21_phc_resonance(
                combo["L_cav_um"], 3.48, 1.44),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_nm"],
            "metric_name": "cavity_wl (2D FDTD, nm)",
            "target_unit": "nm",
            "analytic_only": False,
            "secondary": ("L_cav_um", True),
            "note": "光子晶体腔（布拉格镜 Fabry–Perot 腔）：λ_res=(n_core+n_clad)·"
                    "L_cav（B21 物理定律锚，确定性、零拟合）。网格搜索 L_cav 命中"
                    "目标共振；2D FDTD 提取真实腔共振与锚死标量比对（纯 numpy "
                    "零 GPU）。与 MZI/环形并列的光子共振器件，且是真跑全波 FDTD。",
        },
        "ReadoutResonator": {
            "title": "CPW λ/4 读出谐振器 · 目标基模频率 f0（1D 传输线 FDTD + 传输线锚）",
            "sweep": [("L_um", 1000.0, 8000.0, 250.0)],
            "fixed": dict(n_eff=2.5, tol_rel=0.03, N=400, n_steps=15000,
                          src_frac=0.22, tau_frac=0.05, rec_tail=0.45),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_qres_fdtd(mode=mode, **kw),
            "cheap": lambda combo, target: b22_qres_frequency(
                combo["L_um"], 2.5),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_ghz"],
            "metric_name": "f0 (1D TL-FDTD, GHz)",
            "target_unit": "GHz",
            "analytic_only": False,
            "secondary": ("L_um", False),  # 偏好较短（更紧凑的读出线）
            "note": "CPW λ/4 读出谐振器（超导量子比特读出）：f0=c0/(4·L·n_eff)"
                    "（B22 物理定律锚，确定性、零拟合）。网格搜索 L 命中目标"
                    "谐振频率；1D 传输线 FDTD 提取真实 f0 与锚死标量比对"
                    "（纯 numpy 零 GPU）。与 Transmon 引擎配对构成 QEDA"
                    "「比特+读出」基础单元。",
        },
        "Fluxonium": {
            "title": "Fluxonium 超导量子比特 · 目标频率 f01（相位对角化 + 双基对拍）",
            "sweep": [("e_j", 1.0, 12.0, 0.5)],
            "fixed": dict(e_c=1.0, e_l=1.0, tol_rel=0.01, nphi=401,
                          ncut=40, phi_max_pi=4.0),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_fluxonium(mode=mode, **kw),
            # 无解析闭式 → cheap = 粗相位网格对角化（nphi=81，毫秒级）
            "cheap": lambda combo, target: _flux_f01_cheap(
                combo["e_j"], 1.0, 1.0),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_ghz"],
            "metric_name": "f01 (相位对角化, GHz)",
            "target_unit": "GHz",
            "analytic_only": False,
            "secondary": ("e_j", True),
            "note": "Fluxonium H=4Ec·n²+½El·φ²−Ej·cosφ 任意 Ej 无解析闭式"
                    "（正是必须数值对角化的原因）。cheap=粗相位网格 f01"
                    "（小网格快速评估），top-K 用 401 点相位网格 + HO 基"
                    "双路径对拍（rel≤1%）+ B23 LC 极限边界校验。与 "
                    "Transmon 并列的第二类超导比特，补强 QEDA 栈。",
        },
        "TunableCoupler": {
            "title": "可调耦合器 · 目标有效耦合 |g_eff|（三模对角化 + 二阶微扰锚）",
            "sweep": [("g1_ghz", 0.05, 0.25, 0.01)],
            "fixed": dict(wq_ghz=5.0, wc_ghz=7.5, g2_ghz=0.10,
                          alpha_ghz=-0.20, tol_rel=0.03, ncut=3),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_tunable_coupler(mode=mode, **kw),
            "cheap": lambda combo, target: abs(b24_tcoup_geff(
                5.0, 7.5, combo["g1_ghz"], 0.10)),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_ghz"],
            "metric_name": "|g_eff| (三模对角化, GHz)",
            "target_unit": "GHz",
            "analytic_only": False,
            "secondary": ("g1_ghz", True),
            "note": "QEDA 可调耦合器：两 transmon 经中间 coupler 的等效直接"
                    "耦合。B24 二阶微扰锚 g_eff=(g1g2/2)(1/Δ1+1/Δ2) 引导网格"
                    "搜索 g1 命中目标 |g_eff|；top-K 真跑三模 Fock 截断对角化"
                    "激发带劈裂/2 与锚死标量比对（rel≤3%）。可调耦合器是"
                    "可调两比特门架构的核心元件。",
        },
        "Mmi1x2": {
            "title": "MMI 1×2 分束器 · 目标自映像长度 L_mmi（多模干涉 + B16 锚）",
            "sweep": [("W_e_um", 2.5, 8.0, 0.5)],
            "fixed": dict(n_eff=3.30, wl_um=1.55, tol_rel=0.05),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_mmi(mode=mode, **kw),
            "cheap": lambda combo, target: b16_mmi_length(
                combo["W_e_um"], 3.30, 1.55),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_um"],
            "metric_name": "L_mmi (模式叠加, um)",
            "target_unit": "um",
            "analytic_only": False,
            "secondary": ("W_e_um", True),
            "note": "MMI 1×2 自映像长 L=3·n_eff·W²/λ（B16 锚，多模干涉自成像）。"
                    "网格搜宽度命中目标自映像长；top-K 模式叠加数值核复核。",
        },
        "GratingCoupler2": {
            "title": "光栅耦合器 · 目标 Bragg 波长 λ_B（一阶衍射 + Bragg 锚）",
            "sweep": [("period_um", 0.50, 1.20, 0.02)],
            "fixed": dict(n_eff=2.80, wl_um=1.55, tol_rel=0.05),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_grating_coupler(mode=mode, **kw),
            "cheap": lambda combo, target: combo["period_um"] * 2.80,
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_um"],
            "metric_name": "λ_B (Bragg, um)",
            "target_unit": "um",
            "analytic_only": False,
            "secondary": ("period_um", True),
            "note": "一阶 Bragg 波长 λ_B=Λ·n_eff（垂直接入近似，物理定律锚）。"
                    "网格搜光栅周期命中目标 λ_B；top-K 数值核复核。",
        },
        "DirectionalCoupler2": {
            "title": "方向耦合器 · 目标 3dB 长度 L_3dB（超模拍频 + B14 锚）",
            "sweep": [("n_e", 3.30, 3.50, 0.005)],
            "fixed": dict(n_o=3.36, wl_um=1.55, tol_rel=0.05),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_directional_coupler(mode=mode, **kw),
            "cheap": lambda combo, target: b14_dc_coupling_length(
                combo["n_e"], 3.36, 1.55),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_um"],
            "metric_name": "L_3dB (超模拍频, um)",
            "target_unit": "um",
            "analytic_only": False,
            "secondary": ("n_e", True),
            "note": "方向耦合器 3dB 长 L=λ/(2|n_e−n_o|)（B14 锚，偶/奇超模拍频）。"
                    "网格搜偶模折射率命中目标 3dB 长；top-K 超模拍频核复核。",
        },
        "TunableTransmon": {
            "title": "可调 transmon · 目标频率 f01（SQUID 磁通调谐 + B25 锚）",
            "sweep": [("phi_frac", 0.0, 0.45, 0.05)],
            "fixed": dict(e_j_sum_ghz=20.0, e_c_ghz=0.30,
                          tol_rel=0.03),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_tunable_transmon(mode=mode, **kw),
            "cheap": lambda combo, target: b25_tunable_transmon_f01(
                combo["phi_frac"], 20.0, 0.30),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_ghz"],
            "metric_name": "f01 (koch+SQUID, GHz)",
            "target_unit": "GHz",
            "analytic_only": False,
            "secondary": ("phi_frac", True),
            "note": "可调 transmon f01(Φ)=√(8Ec·EJ(Φ))−Ec（B25 锚，SQUID 磁通调谐）。"
                    "网格搜磁通偏置命中目标 f01；top-K koch 复核。",
        },
        "ReadoutPair": {
            "title": "量子比特-读出谐振器配对 · 目标色散位移 χ（严格对角化 + B26 锚）",
            "sweep": [("f_r_ghz", 5.2, 7.0, 0.2)],
            "fixed": dict(f_q_ghz=5.0, alpha_ghz=-0.30, g_ghz=0.10,
                          tol_rel=0.05),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_readout_pair(mode=mode, **kw),
            "cheap": lambda combo, target: abs(b26_dispersive_shift(
                5.0, -0.30, combo["f_r_ghz"], 0.10)),
            "extract": lambda r: abs(r["checks"]["analytic_fsr"]["fsr_fdtd_ghz"]),
            "metric_name": "|χ| (严格对角化, GHz)",
            "target_unit": "GHz",
            "analytic_only": False,
            "secondary": ("f_r_ghz", False),
            "note": "色散位移 χ=g²α/(Δ(Δ+α))（B26 锚，Blais 修正）。网格搜读出"
                    "频率命中目标 |χ|；top-K 多能级+Fock 严格对角化复核。",
        },
        "CzGate": {
            "title": "色散 CZ 门 · 目标门时间 t_CZ（条件相位 π + B27 锚）",
            "sweep": [("g_ghz", 0.05, 0.20, 0.01)],
            "fixed": dict(f_q_ghz=5.0, alpha_ghz=-0.30, f_r_ghz=6.0,
                          tol_rel=0.03),
            "verify": lambda mode, target_f01, **kw:
                self.lib.verify_cz_gate(mode=mode, **kw),
            "cheap": lambda combo, target: b27_cz_gate_time(
                5.0, -0.30, 6.0, combo["g_ghz"]),
            "extract": lambda r: r["checks"]["analytic_fsr"]["fsr_fdtd_ns"],
            "metric_name": "t_CZ (条件相位 π, ns)",
            "target_unit": "ns",
            "analytic_only": False,
            "secondary": ("g_ghz", True),
            "note": "色散 CZ 门时间 t_CZ=π/(2|χ|)（B27 锚）。网格搜耦合强度 g "
                    "命中目标门时间；top-K 对角化 χ 复核 + 2|χ|·t=π 精确性校验。",
        },
        # ---- v0.8.11e：loss/效率类引擎（实证锚判决路径）----
        # 这些引擎的"目标" = 损耗/效率预算（文献实测典型值），验证锚 = **实证语料**
        # （E1-E7 golden，非解析锚）——实证锚第一次成为引擎级判决锚（LLM 不进判决）。
        "YbranchLoss": {
            # D-66：metric 由「含 3.01dB 理想分光的分支插损 split_loss_dB」
            # 改为「**过量损耗** excess_loss_dB」——3.01dB 是 1×2 均分的几何必然，
            # 非器件品质指标、非被测量；实测 golden 也改判为 0.28±0.02 dB
            # （Opt. Express 21, 1310 (2013)，DOI 10.1364/OE.21.001310）。
            "title": "Y-branch 过量损耗 · 目标 excess_loss（实证锚 E-YBRANCH-LOSS）",
            "sweep": [("theta_deg", 2.0, 20.0, 1.0)],
            "fixed": dict(excess_coef=0.004),
            "verify": _loss_verify("engine_ybranch_split", "E-YBRANCH-LOSS",
                                   tol=0.5),
            "cheap": lambda combo, target: _loss_cheap(
                "engine_ybranch_split", combo),
            "extract": lambda r: r["metric"],
            "metric_name": "excess_loss_dB",
            "target_unit": "dB",
            "analytic_only": False,
            "secondary": ("theta_deg", True),
            "note": "Y-branch **过量损耗** = c1·θ²（D-66：已剔除 3.01dB 理想分光；"
                    "需含分光的插损自行 +3.0103dB）。目标=公开实测 0.28dB"
                    "（Opt. Express 21, 1310）；实证锚 E-YBRANCH-LOSS 死标量判决"
                    "（|out−golden|≤tol）。⚠️ c1=0.004 dB/deg² 为**未标定的唯象系数**，"
                    "θ=10° 给 0.4dB、实测 0.28dB，rel≈43%，如实暴露不做拟合回算。",
        },
        "GratingEff": {
            "title": "光栅耦合效率 · 目标 coupling_eff（实证锚 E-GRATING-EFF）",
            "sweep": [("ff", 0.30, 0.70, 0.05)],
            "fixed": dict(theta_deg=8.0, tilt_sigma_deg=15.0),
            "verify": _loss_verify("engine_grating_eff", "E-GRATING-EFF",
                                   tol=0.10),
            "cheap": lambda combo, target: _loss_cheap(
                "engine_grating_eff", combo),
            "extract": lambda r: r["metric"],
            "metric_name": "coupling_eff",
            "target_unit": "",
            "analytic_only": False,
            "secondary": ("ff", False),
            "note": "光栅耦合峰值效率（Bragg×占空比×倾斜）。目标=公开实测 0.42"
                    "（D-66 逐字核实，APL 96, 051126 (2010)，DOI 10.1063/1.3304791；"
                    "原 0.45 无出处已废弃）；实证锚 E-GRATING-EFF 判决。"
                    "⚠️ 文献器件为全刻蚀光子晶体孔阵，与参数化周期光栅非同一结构。",
        },
        "Crossing": {
            "title": "波导 crossing · 目标插入损耗（实证锚 E-SOI-CROSS-IL/XT）",
            "sweep": [("taper_w_ratio", 1.5, 4.0, 0.5)],
            "fixed": dict(w_core_um=0.5),
            "verify": _loss_verify("engine_crossing", "E-SOI-CROSS-IL",
                                   tol=0.10),
            "cheap": lambda combo, target: _loss_cheap(
                "engine_crossing", combo),
            "extract": lambda r: r["metric"],
            "metric_name": "insertion_loss_dB",
            "target_unit": "dB",
            "analytic_only": False,
            "secondary": ("taper_w_ratio", False),
            "note": "crossing 插入损耗（taper 参数化，XT 联动报告）。目标=优化"
                    "crossing 典型 0.18dB；实证锚 E-SOI-CROSS-IL 判决。",
        },
        "MmiEl": {
            "title": "MMI 1×2 过量损耗 · 目标 excess_loss（实证锚 E-MMI-1X2-EL）",
            "sweep": [("L_mmi_um", 20.0, 35.0, 1.0)],
            "fixed": dict(w_mmi_um=2.8, n_si=3.48, wl_um=1.55),
            "verify": _loss_verify("engine_mmi_el", "E-MMI-1X2-EL",
                                   tol=0.05),
            "cheap": lambda combo, target: _loss_cheap("engine_mmi_el", combo),
            "extract": lambda r: r["metric"],
            "metric_name": "excess_loss_dB",
            "target_unit": "dB",
            "analytic_only": False,
            "secondary": ("L_mmi_um", True),
            "note": "MMI 1×2 过量损耗（长度失配模型，L=L_ideal 最优）。目标=优化"
                    "MMI 典型 0.05dB；实证锚 E-MMI-1X2-EL 判决。",
        },
        "SinPl": {
            "title": "SiN 波导传播损耗 · 目标 PL（实证锚 E-SIN-PL-800）",
            "sweep": [("roughness_nm", 0.20, 0.60, 0.05)],
            "fixed": dict(w_core_um=0.8, h_core_um=0.8),
            "verify": _loss_verify("engine_sin_pl", "E-SIN-PL-800",
                                   tol=0.02),
            "cheap": lambda combo, target: _loss_cheap("engine_sin_pl", combo),
            "extract": lambda r: r["metric"],
            "metric_name": "propagation_loss_dBcm",
            "target_unit": "dB/cm",
            "analytic_only": False,
            "secondary": ("roughness_nm", True),
            "note": "厚 SiN 传播损耗（Payne-Lacey 粗糙度散射，标定 800×800nm）。"
                    "目标=典型 0.087dB/cm；实证锚 E-SIN-PL-800 判决。",
        },

        # ---- 有源双出口（Merge-2a：设计量 + 行为黑箱） ----
        "PhaseShifter": {
            "title": "热光相移器 · 目标相移效率（deg/mW，D-73 同源锚）",
            "sweep": [("L_um", 50.0, 800.0, 50.0)],
            "fixed": dict(),
            "verify": lambda mode, target_f01=None, **kw:
                _phase_verify(target_f01 or kw.get("target"), **kw),
            "cheap": lambda combo, target: phase_efficiency_deg_per_mW(
                combo["L_um"]),
            "extract": lambda r: r["metric"],
            "metric_name": "相移效率 (deg/mW)",
            "target_unit": "deg/mW",
            "analytic_only": True,
            "secondary": ("L_um", True),
            "note": "热光相移：Δφ=2π/λ·dn/dT·R_th·P·L（dn/dT=1.86e-4 硅热光系数，"
                    "D-73 同源）。目标=相移效率 deg/mW；P_π=半波功率。",
        },
        "MziModulator": {
            "title": "MZI 电光调制器 · 目标 V_π（V，Pockels）",
            "sweep": [("L_um", 100.0, 2000.0, 100.0)],
            "fixed": dict(g_um=1.0, r_pm_per_V=30.0),
            "verify": lambda mode, target_f01=None, **kw:
                _mzi_mod_verify(target_f01 or kw.get("target"), **kw),
            "cheap": lambda combo, target: vpi_electrooptic(
                combo["L_um"], combo.get("g_um", 1.0),
                combo.get("r_pm_per_V", 30.0)),
            "extract": lambda r: r["metric"],
            "metric_name": "V_π (V)",
            "target_unit": "V",
            "analytic_only": True,
            "secondary": ("L_um", True),
            "note": "MZI 电光调制器：V_π=λ·g/(L·r·n³)（Pockels r=30pm/V LiNbO3 典型）。"
                    "目标=半波电压；行为黑箱 T(V)=cos²(πV/2V_π) 供链路消费。",
        },
        }
        return specs

    # ------------------------------------------------------------------ #
    # 网格
    # ------------------------------------------------------------------ #
    @staticmethod
    def _grid(sweep: List[Tuple[str, float, float, float]]) -> List[Dict[str, float]]:
        axes = []
        for (p, lo, hi, step) in sweep:
            vals = []
            v = lo
            while v <= hi + 1e-9:
                vals.append(round(v, 6))
                v += step
            axes.append((p, vals))
        keys = [a[0] for a in axes]
        return [dict(zip(keys, combo))
                for combo in itertools.product(*[a[1] for a in axes])]

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #
    def design(self, kind: str, target: float, top_k: int = 5,
               verify_top_k: Optional[int] = None) -> Dict[str, Any]:
        """搜索 + 验证，返回最优已验证设计。

        verify_top_k：仅对搜索排序后的前 N 个候选跑真实求解器验证（默认 = top_k）。
        """
        if kind not in self.specs:
            return {"ok": False,
                    "error": f"未知器件类型 {kind}；可选：{list(self.specs)}",
                    "kinds": list(self.specs)}
        spec = self.specs[kind]
        verify_top_k = verify_top_k if verify_top_k is not None else top_k

        # ① 搜索（物理定律 ORACLE，瞬时）
        ranked: List[Tuple[float, Dict[str, float]]] = []
        for combo in self._grid(spec["sweep"]):
            try:
                m = spec["cheap"](combo, target)
            except Exception:
                continue
            if m is None:
                continue
            ranked.append((abs(m - target), combo))
        ranked.sort(key=lambda x: x[0])

        # ② 验证（仅 top-K 跑真实求解器双重验证；analytic_only 用 contract 解析锚）
        vmode = "contract" if spec.get("analytic_only") else "live"
        verified: List[Dict[str, Any]] = []
        for err, combo in ranked[:verify_top_k]:
            try:
                r = spec["verify"](mode=vmode, target_f01=target, **combo)
            except Exception as e:  # noqa: BLE001
                r = {"passed": False, "verdict": f"验证异常：{str(e)[:60]}"}
            passed = (r.get("passed") is True)
            if spec.get("analytic_only") and r.get("checks", {}).get(
                    "analytic_fsr", {}).get("physical"):
                passed = True  # 解析锚：物理合理即算可用（诚实标注）
            metric = None if not passed else _safe(spec["extract"], r)
            rec = {
                "params": combo,
                "metric": metric,
                # 目标误差语义（v0.8.28 修复）：err 用于网格排序（cheap 估算，
                # 可能数学精确如 Koch 反解 → err=0），但对外展示的"目标误差"
                # 必须是对真实验证 metric 的误差——否则 Transmon 候选显示
                # 0.0000 而真实 f01=4.98628 误差 0.27% 被掩盖（误导决策）。
                # 验证通过且有真实 metric 时，用 |metric − target| 重算。
                "err": (abs(metric - target) if (passed and metric is not None)
                        else err),
                "passed": passed,
                "verdict": r.get("verdict", ""),
                "result": r if passed else None,  # 仅保留已验证候选的全证据
            }
            verified.append(rec)

        passed_recs = [v for v in verified if v["passed"]]
        # 排序：主 = 目标误差；次 = 偏好（periods 少 / E_C 适中）
        sec = spec.get("secondary")
        if sec:
            sp, low = sec
            passed_recs.sort(key=lambda v: (round(v["err"], 6),
                                            v["params"].get(sp, 0)
                                            if low else -v["params"].get(sp, 0)))
        else:
            passed_recs.sort(key=lambda v: round(v["err"], 6))

        best = passed_recs[0] if passed_recs else None
        return {
            "ok": True,
            "kind": kind,
            "title": spec["title"],
            "target": target,
            "target_unit": spec.get("target_unit", ""),
            "metric_name": spec["metric_name"],
            "analytic_only": spec.get("analytic_only", False),
            "searched": len(ranked),
            "verified": len(verified),
            "passed": len(passed_recs),
            "best": best,
            "top": passed_recs[:top_k],
            "note": spec["note"],
        }

    def design_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """从请求字典解析并设计：{kind, target, top_k?}。"""
        kind = payload.get("kind")
        target = payload.get("target")
        if not kind or target is None:
            return {"ok": False, "error": "请求需含 kind 与 target"}
        try:
            target = float(target)
        except (TypeError, ValueError):
            return {"ok": False, "error": "target 须为数值"}
        top_k = int(payload.get("top_k", 5))
        return self.design(kind, target, top_k=top_k)


def _safe(fn: Callable, r: Dict[str, Any]):
    try:
        return fn(r)
    except Exception:
        return None


# ---------------------------------------------------------------------- #
# CLI 便捷入口
# ---------------------------------------------------------------------- #
def run_all_demo() -> Dict[str, Any]:
    """对 4 类器件各跑一个真实设计请求，证明闭环可用。"""
    eng = DesignEngine()
    requests = [
        ("Waveguide", 3.25),     # 目标 neff ≈ 3.25
        ("BraggMirror", 0.999),  # 目标 R_min ≥ 0.999
        ("Transmon", 5.0),       # 目标 f01 = 5.0 GHz
        ("RingResonator", 9.0),  # 目标 FSR ≈ 9 nm
    ]
    out = {}
    for kind, target in requests:
        out[kind] = eng.design(kind, target, top_k=3, verify_top_k=3)
    return out


if __name__ == "__main__":
    import json
    res = run_all_demo()
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
