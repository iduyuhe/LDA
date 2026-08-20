"""LDA L2 · 已验证器件库（D-12 固化）。

把已验证器件沉淀为**可复用资产**——设计者/上层（agent / webui / PDK 接入 /
阶段 3 版图生成）按名字取用，无需重写接线：

  方向耦合器 DirectionalCoupler   —— D-01：FDFD 超模 κ ↔ FDTD 超模投影（torch GPU）
  对称 Y 分支 SymmetricYBranch    —— D-01：对称性定理 50/50 ↔ FDTD 能流平衡（torch GPU）
  环形谐振器 RingResonator       —— D-11：解析环形传递函数 FSR ↔ 洛伦兹梳谱提取（解析，快）
  真 2D 波导 Waveguide           —— FDFD 本征 ↔ FDTD neff（numpy，重项）
  布拉格镜   BraggMirror         —— D-03：TMM 阻带 ↔ FDTD 宽带谱形（numpy，重项）

每个器件固化为 DeviceSpec：参数 schema（可调窗口）+ 标准验收契约（复用 D-04
VerificationSpec，ORACLE 全部为确定性物理定律锚，LLM 不进判决路径）+ 已验证
候选求解器（懒加载）。

验收分层：
  mode="contract" —— 注册表 + 契约 + 管道验证（快，CI 用；候选自洽不跑数值）
  mode="live"     —— 跑真实 ORACLE + 已验证求解器（本机用；需 GPU 项无 GPU 诚实 SKIP；
                     重项 waveguide/bragg 默认跳过，可 verify_one(force_heavy=True) 单跑）

零顶层外部依赖：verification_spec / 求解器 / ORACLE 均在调用时懒加载。
"""
from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# 延迟导入 lda_harness / lda_agent / lda_solver，避免编译期强耦合
_SOLVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_solver")


def _ensure_solver_on_path() -> None:
    if _SOLVER_DIR not in sys.path:
        sys.path.insert(0, _SOLVER_DIR)


def _self_consistent(spec, oracle_value):
    """契约模式候选：返回 ORACLE 自洽（仅验证注册表 + 管道，不跑数值）。"""
    return oracle_value


# ---------------------------------------------------------------------------
# 器件规格
# ---------------------------------------------------------------------------
@dataclass
class DeviceSpec:
    name: str                                   # 唯一名（如 "DirectionalCoupler"）
    ir_kinds: List[str]                         # 对应的 L0 IR kind（photon.py）
    params_schema: Dict[str, Tuple[float, float]]  # 参数 → 可调/工艺窗口
    description: str
    verify_spec: Any                            # VerificationSpec（D-04 统一契约）
    candidate_fn: Optional[Callable] = None     # 已验证求解器（懒加载真实实现）
    candidate_desc: str = ""
    requires_gpu: bool = False                  # live 候选是否需 torch CUDA
    live_weight: str = "light"                  # 'light'（live 默认跑）| 'heavy'（可选）
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 已验证器件库
# ---------------------------------------------------------------------------
class DeviceLibrary:
    """已验证器件库：把 D-01/D-03/D-11/waveguide 固化为可复用资产。"""

    def __init__(self):
        self._devices: Dict[str, DeviceSpec] = {}
        self._register_all()

    # ---- 注册 ----
    def _register_all(self):
        self._register_coupler()    # DirectionalCoupler + SymmetricYBranch（D-01）
        self._register_waveguide()  # Waveguide
        self._register_ring()       # RingResonator（D-11）
        self._register_bragg()      # BraggMirror（D-03）

    def _register_coupler(self):
        from lda_harness.verification_adapters import build_coupler_specs
        specs, cand_map = build_coupler_specs()
        for sp in specs:
            if sp.spec_id.startswith("DC"):
                self.register(DeviceSpec(
                    name="DirectionalCoupler",
                    ir_kinds=["DirectionalCoupler"],
                    params_schema={"gap": (0.10, 0.60), "Lc": (1.0, 60.0),
                                   "kappa_target": (0.0, 0.5)},
                    description="方向耦合器（D-01 验收锚：FDFD 超模 κ ↔ FDTD 超模投影）",
                    verify_spec=sp,
                    candidate_fn=cand_map[sp.spec_id],
                    candidate_desc="标量 3D FDTD 超模投影递推（torch GPU）",
                    requires_gpu=True, live_weight="light"))
            else:
                self.register(DeviceSpec(
                    name="SymmetricYBranch",
                    ir_kinds=["SymmetricYBranch"],
                    params_schema={"width": (0.30, 1.00),
                                   "split_angle": (1.0, 30.0),
                                   "arm_length": (1.0, 20.0)},
                    description="对称 Y 分支分束器（D-01：对称性定理 50/50 ↔ FDTD 能流平衡）",
                    verify_spec=sp,
                    candidate_fn=cand_map[sp.spec_id],
                    candidate_desc="标量 3D FDTD 能流功率测量（torch GPU）",
                    requires_gpu=True, live_weight="light"))

    def _register_waveguide(self):
        from lda_harness.verification_adapters import build_waveguide_specs
        specs, cand_map = build_waveguide_specs()
        sp = specs[0]  # 标准契约取首例（真 2D 波导 neff）
        self.register(DeviceSpec(
            name="Waveguide",
            ir_kinds=["Waveguide"],
            params_schema={"width": (0.35, 0.75)},
            description="真 2D 波导（FDFD 本征 ORACLE ↔ FDTD neff）",
            verify_spec=sp,
            candidate_fn=cand_map[sp.spec_id],
            candidate_desc="标量 3D FDTD 双监视点相位差（numpy，重项）",
            requires_gpu=False, live_weight="heavy"))

    def _register_ring(self):
        from lda_harness.verification_spec import VerificationSpec, cmp_rel
        from lda_agent.ring_loop import (ring_fsr_analytic_nm,
                                         ring_transfer_spectrum,
                                         _extract_fsr_nm)

        def _oracle(p):
            return ring_fsr_analytic_nm(p["R_um"], p["n_g"], p["wl0_um"])

        def _cand(spec, oracle_value):
            p = spec.params
            fsr = ring_fsr_analytic_nm(p["R_um"], p["n_g"], p["wl0_um"])
            span = 4.0 * fsr / 1000.0
            wls = [p["wl0_um"] + (i / 80.0 - 0.5) * span for i in range(81)]
            drop = ring_transfer_spectrum(p["R_um"], p["n_g"], p["wl0_um"],
                                          p["Q"], p["kappa"], wls)
            return _extract_fsr_nm(wls, drop)

        spec = VerificationSpec(
            spec_id="RING-fsr", metric="fsr_nm", oracle_kind="physical_law",
            oracle_fn=_oracle, compare_fn=cmp_rel,
            tol=0.02, tol_mode="rel",
            target_desc="环形谐振器 FSR（解析环形传递函数 ↔ 洛伦兹梳谱提取）",
            params={"R_um": 9.95, "n_g": 4.2, "wl0_um": 1.55,
                    "Q": 1.0e4, "kappa": 0.05},
            source="解析环形传递函数 FSR=λ²/(n_g·2πR)",
            candidate_desc="洛伦兹梳谱峰提取 FSR（独立谱形计算）")
        self.register(DeviceSpec(
            name="RingResonator",
            ir_kinds=["RingResonator"],
            params_schema={"R": (8.0, 12.0), "Q": (1.0e3, 1.0e5),
                           "kappa": (0.0, 0.5)},
            description="环形谐振器谱形（D-11：解析 FSR ↔ 洛伦兹梳谱提取）",
            verify_spec=spec, candidate_fn=_cand,
            candidate_desc="洛伦兹梳谱峰提取（解析）",
            requires_gpu=False, live_weight="light"))

    def _register_bragg(self):
        from lda_harness.verification_spec import VerificationSpec, cmp_abs
        _ensure_solver_on_path()

        def _spec_dict(p):
            lam = p["wl0_um"]
            qw_hi, qw_lo = lam / (4.0 * p["n_si"]), lam / (4.0 * p["n_sio"])
            layers = [(float("inf"), 1.0)]
            for _ in range(p["periods"]):
                layers.append((qw_hi, p["n_si"]))
                layers.append((qw_lo, p["n_sio"]))
            layers.append((float("inf"), 1.0))
            span = 0.12
            wls = [round(lam + (i / (p["n_points"] - 1) - 0.5) * 2.0 * span, 4)
                   for i in range(p["n_points"])]
            return {"layers": layers, "wavelengths_um": wls}

        def _oracle(p):
            import tmm
            return min(1.0 - t
                       for t in tmm.solve_spectrum(_spec_dict(p))["transmission"])

        def _cand(spec, oracle_value):
            import fdtd3d
            p = spec.params
            res = fdtd3d.solve_spectrum(_spec_dict(p), dl_factor=p.get("dl_factor", 60.0),
                                        sponge=60, ramp=200)
            return min(1.0 - t for t in res["transmission"])

        spec = VerificationSpec(
            spec_id="BRAGG-band", metric="R_min_band", oracle_kind="tmm_analytic",
            oracle_fn=_oracle, compare_fn=cmp_abs,
            tol=0.02, tol_mode="abs",
            target_desc="布拉格镜宽带阻带底线 R（D-03：TMM ↔ FDTD 全波段谱形）",
            params={"wl0_um": 1.55, "n_si": 3.48, "n_sio": 1.44,
                    "periods": 6, "n_points": 11, "dl_factor": 60.0},
            source="tmm.py 解析透射谱（外部物理定律锚）",
            candidate_desc="自写 FDTD 宽带谱形（numpy，重项）")
        self.register(DeviceSpec(
            name="BraggMirror",
            ir_kinds=[],
            params_schema={"periods": (1, 12)},
            description="布拉格镜宽带谱形（D-03：TMM 阻带 ↔ FDTD 全波段验收）",
            verify_spec=spec, candidate_fn=_cand,
            candidate_desc="自写 FDTD 宽带谱形（numpy，重项）",
            requires_gpu=False, live_weight="heavy"))

    def register(self, dev: DeviceSpec) -> None:
        self._devices[dev.name] = dev

    # ---- 查询 ----
    def list(self) -> List[str]:
        return list(self._devices.keys())

    def get(self, name: str) -> DeviceSpec:
        if name not in self._devices:
            raise KeyError(f"器件库无 '{name}'（已知：{self.list()}）")
        return self._devices[name]

    def by_ir_kind(self, kind: str) -> Optional[DeviceSpec]:
        for dev in self._devices.values():
            if kind in dev.ir_kinds:
                return dev
        return None

    def specs(self) -> List[Any]:
        return [d.verify_spec for d in self._devices.values()]

    # ---- 验收 ----
    def verify_one(self, name: str, mode: str = "contract") -> Any:
        """验收单个器件。contract=注册表+管道（快）；live=真实 ORACLE+求解器。"""
        from lda_harness.verification_spec import run_verification
        dev = self.get(name)
        spec = dev.verify_spec
        if mode == "contract":
            out = run_verification(spec, _self_consistent, oracle_value=1.0)
            out.diagnostics = ("contract 模式：注册表 + 契约 + 管道验证"
                               "（数值验收请用 live 模式）")
            out.extra["device"] = dev.name
            out.extra["ir_kinds"] = dev.ir_kinds
            return out
        # live
        if dev.candidate_fn is None or dev.requires_gpu and not self._cuda_ok():
            return self._skipped(dev, "live 候选需 torch CUDA（当前无 GPU）→ 诚实 SKIP")
        return run_verification(spec, dev.candidate_fn)

    def verify_all(self, mode: str = "contract",
                   live_heavy: bool = False) -> Tuple[Dict[str, Any], List[str]]:
        """验收全部器件。返回 (outcomes, skipped)。

        contract 全部跑；live 默认只跑 light（DC/YB 无 GPU 时 SKIP），
        heavy（waveguide/bragg）需 live_heavy=True 才跑。
        """
        outcomes: Dict[str, Any] = {}
        skipped: List[str] = []
        for name in self.list():
            dev = self.get(name)
            if mode == "live" and dev.live_weight == "heavy" and not live_heavy:
                skipped.append(name)
                continue
            outcomes[name] = self.verify_one(name, mode=mode)
        return outcomes, skipped

    def to_summary(self) -> dict:
        return {
            name: {
                "ir_kinds": dev.ir_kinds,
                "params_schema": {k: list(v) for k, v in dev.params_schema.items()},
                "metric": dev.verify_spec.metric,
                "oracle_kind": dev.verify_spec.oracle_kind,
                "requires_gpu": dev.requires_gpu,
                "live_weight": dev.live_weight,
            }
            for name, dev in self._devices.items()
        }

    @staticmethod
    def _cuda_ok() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def _skipped(self, dev: DeviceSpec, reason: str) -> Any:
        from lda_harness.verification_spec import VerificationOutcome
        spec = dev.verify_spec
        return VerificationOutcome(
            spec_id=dev.name, passed=None, metric=spec.metric,
            oracle_kind=spec.oracle_kind, candidate=None, oracle_value=None,
            err=float("inf"), tol=spec.tol, tol_mode=spec.tol_mode,
            target_desc=spec.target_desc, source=spec.source,
            candidate_desc=dev.candidate_desc, diagnostics=reason,
            extra={"skipped": True})


def get_default_library() -> DeviceLibrary:
    """返回（惰性构建并缓存）默认器件库实例。"""
    global _DEFAULT_LIBRARY
    if _DEFAULT_LIBRARY is None:
        _DEFAULT_LIBRARY = DeviceLibrary()
    return _DEFAULT_LIBRARY


_DEFAULT_LIBRARY: Optional[DeviceLibrary] = None
