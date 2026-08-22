"""LDA · L1 agent 协议层 — agent 与内核之间的「机器优先」操作接口。

L1 的职责（见 L0 IR 草案 §5）：把"人操作壳"翻译成"agent 操作接口"——确定性、
批处理、可验证、无交互。本模块定义：

  1. 各 L1 agent 角色的消息 schema（JSON 可序列化）—— agent 间 / agent 与内核间的
     机器语言，不是给人看的 GUI。凡"给人操作方便"的壳一律不在此层。
  2. L0 IR → 求解器 spec 的适配器：把 L0 文档的 stack / sources / solver 段
     编译成已验证求解核（fdtd3d / fdtd3d_numba / fdtd3d_torch）直接消费的 spec。
  3. 后端一行切换：numpy / numba-cpu / torch-cpu / torch-cuda，算法由内核决定，
     L1 只转发 `backend` 字段。

角色边界（对应 L0 IR §5 表，此处落成确定性函数而非自由 LLM）：
  - Interpreter：自然语言/半结构化意图 → DesignTarget
  - Designer   ：DesignTarget + 迭代状态 → L0IR（geometry / sources）
  - SolverAgent：L0IR → SolveResult（调内核，产出透射谱）
  - Verifier   ：L0IR + SolveResult → VerifyResult（对 TMM 物理定律锚比对）

铁律：L1 只消费/产出 L0 结构化字段；判据由死代码执行（标量比对），LLM 不进
判决路径（排雷①② 已排空）。
"""
from __future__ import annotations

import os
import sys
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 路径与后端加载（机器优先：直接 import 已验证内核，不经 GUI 壳）
# ---------------------------------------------------------------------------
_SOLVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_solver")


def _ensure_solver_on_path() -> None:
    if _SOLVER_DIR not in sys.path:
        sys.path.insert(0, _SOLVER_DIR)


def load_solver(backend: str):
    """按 backend 名返回 (module, solve_fn)。

    backend ∈ {numpy, numba_cpu, torch_cpu, torch_cuda}
    所有内核 solve_spectrum 同签名：solve_spectrum(spec, dl_factor=..., sponge=..., ramp=...)
    返回 {wavelengths_um, transmission, source, note}。

    后端不可用时（当前沙箱仅装 numpy）自动回退 numpy 并打印，保证闭环可在
    任意环境复现；不在判决路径引入不确定性。
    """
    _ensure_solver_on_path()
    if backend == "numpy":
        import fdtd3d
        return fdtd3d, fdtd3d.solve_spectrum
    if backend == "numba_cpu":
        try:
            import fdtd3d_numba
            return fdtd3d_numba, fdtd3d_numba.solve_spectrum_numba
        except Exception as e:
            import fdtd3d
            print(f"[L1] backend={backend} 不可用（{type(e).__name__}），回退 numpy")
            return fdtd3d, fdtd3d.solve_spectrum
    if backend in ("torch_cpu", "torch_cuda"):
        try:
            import fdtd3d_torch
            return fdtd3d_torch, fdtd3d_torch.solve_spectrum_torch
        except Exception as e:
            import fdtd3d
            print(f"[L1] backend={backend} 不可用（{type(e).__name__}），回退 numpy")
            return fdtd3d, fdtd3d.solve_spectrum
    raise ValueError(f"unknown backend: {backend}")


def load_oracle():
    """物理定律锚 ORACLE：TMM 解析解（非 AI 判决，方程必然）。"""
    _ensure_solver_on_path()
    import tmm
    return tmm


# ---------------------------------------------------------------------------
# 真 2D 波导 ORACLE（lda_harness/oracle_mode.py）：slab 闭式 + FDFD 特征模
# ---------------------------------------------------------------------------
_HARNESS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_harness")


def _ensure_harness_on_path() -> None:
    if _HARNESS_DIR not in sys.path:
        sys.path.insert(0, _HARNESS_DIR)


def load_oracle_mode():
    """真 2D 波导物理定律锚 ORACLE：slab 闭式特征方程 + FDFD 本征模（频域、解析/确定性）。"""
    _ensure_harness_on_path()
    import oracle_mode
    return oracle_mode


# ---------------------------------------------------------------------------
# 消息 schema（JSON 可序列化；dataclass 便于静态结构 + asdict 落盘）
# ---------------------------------------------------------------------------
@dataclass
class DesignTarget:
    """Interpreter 产出：人类设计意图的结构化表达。"""
    geometry_type: str                 # "bragg_mirror" | "ar_coating" | "adjoint_focuser" | ...
    materials: Dict[str, float]        # ref -> 折射率 n
    target_wavelength_um: float        # 设计中心波长
    target_metric: str = "R"           # 验收度量（反射率 / FOM_gain）
    threshold: float = 0.99            # 目标阈值（R >= threshold 即达标）
    tolerance_rel: float = 0.02        # FDTD 对 TMM 的最大相对误差（物理定律锚）
    max_iterations: int = 12           # 迭代上限（防失控）
    initial_periods: int = 1           # Designer 起始周期数
    method: str = "scan"               # 设计方法："scan"=参数扫描（布拉格/波导）
                                       #        "adjoint"=伴随梯度拓扑逆设计（D-70）
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class L0IR:
    """Designer 产出：一份遵循 L0 IR 草案（光子子集）的机器优先设计文档。

    此处为「窄但可落地」子集：stack 几何 + plane_wave 源 + transmission 监视器。
    """
    schema: str = "lda.ir.photon.v0"
    geo_kind: str = "stack"              # "stack" | "voxel_field" | "waveguide_2d"（机器优先版图）
    doc_id: str = "design-auto"
    author: str = "agent"
    dimensionality: int = 3
    dl_factor: float = 60.0            # 数值分辨率（粗→快；生产用 80）
    sponge: int = 60                   # PML 吸收厚度（单元）
    ramp: int = 200                    # 软源上升步数
    backend: str = "numba_cpu"         # 求解后端（一行切换）
    materials: List[Dict[str, float]] = field(default_factory=list)   # [{ref,n}]
    layers: List[Tuple[str, float]] = field(default_factory=list)     # [(material_ref, thickness_um)]
    wavelengths_um: List[float] = field(default_factory=list)
    oracle_type: str = "tmm_analytic"
    tolerance_rel: float = 0.02
    # ---- 真 2D 波导（waveguide_2d）专属字段 ----
    w_um: float = 0.0                    # 波导芯宽（沿 x，y 均匀 ⇒ slab）
    n_core_wg: float = 0.0               # 波导芯折射率
    n_clad_wg: float = 0.0               # 包层折射率

    def to_solver_spec(self) -> Dict[str, Any]:
        """L0 IR → 求解器 spec 适配器（机器优先，无 GUI 翻译损耗）。"""
        n_by_ref = {m["ref"]: m["n"] for m in self.materials}
        spec_layers = []
        for ref, th in self.layers:
            n = n_by_ref[ref]
            spec_layers.append((float("inf") if math.isinf(th) else float(th), float(n)))
        return {
            "layers": spec_layers,
            "wavelengths_um": [float(w) for w in self.wavelengths_um],
        }

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # 把 tuple 层转成可 JSON 的 [ref, th] 列表
        d["layers"] = [[ref, th] for ref, th in self.layers]
        return d


@dataclass
class SolveResult:
    backend: str
    spectrum: Dict[str, Any]           # {wavelengths_um, transmission, source, note}
    nsteps_est: int = 0


@dataclass
class VerifyResult:
    metric: str                        # "R"
    metric_value: float                # FDTD 算出的 R（在 target_wavelength）
    oracle_value: float                # TMM 同波长 R
    metric_abs_err: float              # 中心波长（设计度量）|R_fdtd - R_tmm|（验收判据）
    max_metric_abs_err: float          # 全波长最大 |ΔR|（诊断量；显示用）
    max_rel_T: float                   # FDTD-T 对 TMM-T 的最大相对误差（诊断量；高 R 时 T→0 会失真）
    meets_target: bool                 # metric_value >= threshold
    within_tolerance: bool             # metric_abs_err <= tolerance_rel
    passed: bool                       # 两者皆满足
    per_wavelength: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class DesignOutcomeReport:
    """闭环最终产出：给「人（结果责任人）」看的决策摘要，非操作手册。"""
    target: Dict[str, Any]
    accepted: bool
    iterations: int
    final_doc_id: str
    final_layers: List[List[Any]]
    final_metric: float
    final_oracle_metric: float
    final_metric_err: float
    final_max_metric_err: float = 0.0
    loop_trace: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# L1 角色：确定性函数（非自由 LLM —— 排雷① 已排空 AI 裁判进判决路径）
# ---------------------------------------------------------------------------
class InterpreterAgent:
    """半结构化意图 → DesignTarget。当前以结构化 dict 输入（接口已留自然语言扩展点）。"""

    @staticmethod
    def parse(intent: Dict[str, Any]) -> DesignTarget:
        return DesignTarget(
            geometry_type=intent.get("geometry_type", "bragg_mirror"),
            materials=intent.get("materials", {"air": 1.0, "sih": 3.48, "silo": 1.44}),
            target_wavelength_um=float(intent.get("target_wavelength_um", 1.55)),
            target_metric=intent.get("target_metric", "R"),
            threshold=float(intent.get("threshold", 0.99)),
            tolerance_rel=float(intent.get("tolerance_rel", 0.02)),
            max_iterations=int(intent.get("max_iterations", 12)),
            initial_periods=int(intent.get("initial_periods", 1)),
            method=intent.get("method", "scan"),
            extra=intent.get("extra", {}),
        )


class DesignerAgent:
    """DesignTarget + 迭代状态 → L0IR。当前支持布拉格镜（四分之一波堆）。"""

    @staticmethod
    def propose(target: DesignTarget, periods: int, doc_id: str,
                wavelengths_um: Optional[List[float]] = None,
                geo_kind: str = "stack") -> L0IR:
        # ---- 真 2D 波导：芯宽/芯/包层折射率为设计变量，与 stack 分支正交 ----
        if geo_kind == "waveguide_2d":
            w = float(target.extra.get("width_um", 0.5))
            core_ref = target.extra.get("core_ref", "sih")
            clad_ref = target.extra.get("clad_ref", "silo")
            n_core = target.materials.get(core_ref, max(target.materials.values()))
            n_clad = target.materials.get(clad_ref, min(target.materials.values()))
            wl = target.target_wavelength_um
            return L0IR(
                doc_id=doc_id,
                geo_kind="waveguide_2d",
                materials=[
                    {"ref": core_ref, "n": n_core},
                    {"ref": clad_ref, "n": n_clad},
                ],
                wavelengths_um=[wl],
                backend=target.extra.get("backend", "numpy"),
                dl_factor=target.extra.get("dl_factor", 60.0),
                sponge=target.extra.get("sponge", 80),
                tolerance_rel=target.tolerance_rel,
                oracle_type="slab_analytic",
                w_um=w, n_core_wg=n_core, n_clad_wg=n_clad,
            )

        lam = target.target_wavelength_um
        hi = target.materials["sih"] if "sih" in target.materials else max(target.materials.values())
        lo = target.materials["silo"] if "silo" in target.materials else min(target.materials.values())
        # 四分之一波厚度
        qw_hi = lam / (4.0 * hi)
        qw_lo = lam / (4.0 * lo)
        # 层序：入射 air(inf) | (hi, lo) × periods | 出射 air(inf)
        layers: List[Tuple[str, float]] = [("air", float("inf"))]
        for _ in range(periods):
            layers.append(("sih" if "sih" in target.materials else _hi_ref(target), qw_hi))
            layers.append(("silo" if "silo" in target.materials else _lo_ref(target), qw_lo))
        layers.append(("air", float("inf")))

        if wavelengths_um is None:
            # 默认在中心波长附近做 5 点扫描以展示阻带
            span = 0.18 * lam
            wavelengths_um = [round(lam + s * span, 4) for s in (-1, -0.5, 0, 0.5, 1)]

        return L0IR(
            doc_id=doc_id,
            geo_kind=geo_kind,
            materials=[
                {"ref": "air", "n": target.materials.get("air", 1.0)},
                {"ref": "sih", "n": hi},
                {"ref": "silo", "n": lo},
            ],
            layers=layers,
            wavelengths_um=wavelengths_um,
            backend=target.extra.get("backend", "numba_cpu"),
            dl_factor=target.extra.get("dl_factor", 60.0),
            sponge=target.extra.get("sponge", 60),
            ramp=target.extra.get("ramp", 200),
            tolerance_rel=target.tolerance_rel,
            oracle_type="tmm_analytic",
        )


def _hi_ref(target: DesignTarget) -> str:
    # 兜底：若 materials 不用 sih/silo 命名，取最大 n 的 ref
    return max(target.materials, key=target.materials.get)


def _lo_ref(target: DesignTarget) -> str:
    return min(target.materials, key=target.materials.get)


class LayoutAgent:
    """L0 IR §5：把 geometry 意图转成体素场（机器优先版图 → 体素）。

    当前 v0：stack 退化（沿 x 的矩形层序列，y/z 全宽）经 voxel_field.voxelize_stack
    体素化；真 2D 矩形掩模（voxelize_rectangular）为器件雏形，下一步接真 2D ORACLE。
    闭环实跑的 per-wavelength 精确体素化封装在 SolverAgent 的 voxel 分支
    （solve_spectrum_field_stack），此处提供预览/调试用的单波长体素化。
    """

    @staticmethod
    def voxelize(doc: "L0IR"):
        from voxel_field import voxelize_stack
        _ensure_solver_on_path()
        wl0 = doc.wavelengths_um[len(doc.wavelengths_um) // 2]
        dl = wl0 / doc.dl_factor
        buf = max(20, int(round(3.0 / dl)))
        layers = doc.to_solver_spec()["layers"]
        eps, meta = voxelize_stack(layers, dl, buf, doc.sponge)
        return eps, meta


class SolverAgent:
    """L0IR → SolveResult。调已验证内核；backend 一行切换。"""

    @staticmethod
    def solve(doc: L0IR) -> SolveResult:
        spec = doc.to_solver_spec()
        if doc.geo_kind == "waveguide_2d":
            # 真 2D 波导：时域独立求解核（双监视点 DFT 相位差），与 ORACLE 方法/代码均不同
            _ensure_solver_on_path()
            from fdtd2d_waveguide import build_waveguide_field, solve_waveguide_neff
            wl = doc.wavelengths_um[0] if doc.wavelengths_um else 1.55
            eps2, dl = build_waveguide_field(doc.w_um, doc.n_core_wg, doc.n_clad_wg, wl)
            neff = solve_waveguide_neff(
                eps2, dl, wl, n_clad=doc.n_clad_wg, n_core=doc.n_core_wg)
            spectrum = {
                "wavelengths_um": [wl],
                "neff": neff,
                "source": "2d-te-fdtd",
                "note": "双监视点整数周期 DFT 相位差法（与 slab ORACLE 独立）",
            }
            return SolveResult(backend="numpy-wg", spectrum=spectrum)
        if doc.geo_kind == "voxel_field":
            # 机器优先版图 → 体素 → FDTD：经 solve_spectrum_field_stack
            # （per-wavelength 体素化 + 已验证核心），当前仅 numpy 内核
            _ensure_solver_on_path()
            import fdtd3d
            spectrum = fdtd3d.solve_spectrum_field_stack(
                spec["layers"], doc.wavelengths_um,
                dl_factor=doc.dl_factor, sponge=doc.sponge, ramp=doc.ramp)
            return SolveResult(backend="numpy-voxel", spectrum=spectrum)
        mod, fn = load_solver(doc.backend)
        if doc.backend in ("torch_cpu", "torch_cuda"):
            device = "cuda" if doc.backend == "torch_cuda" else "cpu"
            spectrum = fn(spec, device=device, dl_factor=doc.dl_factor,
                          sponge=doc.sponge, ramp=doc.ramp)
        else:
            spectrum = fn(spec, dl_factor=doc.dl_factor,
                          sponge=doc.sponge, ramp=doc.ramp)
        return SolveResult(backend=doc.backend, spectrum=spectrum)


class VerifierAgent:
    """L0IR + SolveResult → VerifyResult。对 TMM 物理定律锚比对（死代码判）。"""

    @staticmethod
    def verify(doc: L0IR, result: SolveResult, threshold: float) -> VerifyResult:
        # ---- 真 2D 波导：对 slab 闭式 ORACLE 比对（基模 neff）----
        if doc.geo_kind == "waveguide_2d":
            om = load_oracle_mode()
            wl = doc.wavelengths_um[0]
            # slab ORACLE 的 a 为「半厚」：条形波导全宽 w ⇒ 半厚 a = w/2
            oracle_neff = om._slab_te_neff(doc.n_core_wg, doc.n_clad_wg, doc.w_um / 2.0, wl)
            fdtd_neff = result.spectrum["neff"]
            abs_err = abs(fdtd_neff - oracle_neff)
            rel_err = abs_err / oracle_neff
            within = rel_err <= doc.tolerance_rel
            # 波导验收以"与物理定律锚一致"为准（无 R 阈值概念），故 meets_target 恒 True
            return VerifyResult(
                metric="neff",
                metric_value=fdtd_neff,
                oracle_value=oracle_neff,
                metric_abs_err=abs_err,
                max_metric_abs_err=abs_err,
                max_rel_T=rel_err,
                meets_target=True,
                within_tolerance=within,
                passed=within,
                per_wavelength=[{
                    "wl": wl, "fdtd_neff": fdtd_neff,
                    "oracle_neff": oracle_neff, "rel_err": rel_err,
                }],
            )

        tmm = load_oracle()
        oracle_spec = doc.to_solver_spec()
        oracle = tmm.solve_spectrum(oracle_spec)

        wls = result.spectrum["wavelengths_um"]
        fdtd_T = result.spectrum["transmission"]
        tmm_T = oracle["transmission"]

        per = []
        max_rel_T = 0.0
        max_metric_abs_err = 0.0
        for w, t_f, t_o in zip(wls, fdtd_T, tmm_T):
            rel = abs(t_f - t_o) / max(t_o, 1e-9)
            max_rel_T = max(max_rel_T, rel)
            # 设计度量 R 的绝对误差（高 R 场景下 T→0，R 才是稳定可比量）
            err_R = abs((1.0 - t_f) - (1.0 - t_o))
            max_metric_abs_err = max(max_metric_abs_err, err_R)
            per.append({"wl": w, "fdtd_T": t_f, "tmm_T": t_o, "rel_err": rel})

        # 验收度量：在 target_wavelength 处的反射率 R = 1 - T（无损介质 R+T=1）
        target_lam = doc.wavelengths_um[len(doc.wavelengths_um) // 2] if doc.wavelengths_um else wls[0]
        best_i = min(range(len(wls)), key=lambda i: abs(wls[i] - target_lam))
        R_fdtd = 1.0 - fdtd_T[best_i]
        R_tmm = 1.0 - tmm_T[best_i]
        metric_abs_err = abs(R_fdtd - R_tmm)   # 中心波长（设计度量）绝对误差 = 验收判据

        meets = R_fdtd >= threshold
        # 验收判据用设计度量 R 的绝对误差（高反射镜 T→0，rel_T 失真不可用）
        within = metric_abs_err <= doc.tolerance_rel
        return VerifyResult(
            metric="R",
            metric_value=R_fdtd,
            oracle_value=R_tmm,
            metric_abs_err=metric_abs_err,
            max_metric_abs_err=max_metric_abs_err,
            max_rel_T=max_rel_T,
            meets_target=meets,
            within_tolerance=within,
            passed=meets and within,
            per_wavelength=per,
        )


# ---------------------------------------------------------------------------
# 工具：落盘
# ---------------------------------------------------------------------------
def dump_json(obj: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
