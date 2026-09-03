"""LDA · 统一验证契约 VerificationSpec（D-04：三套裁判范式统一）。

D-04 目标：让项目内**四套裁判**（harness B1-B11 / waveguide_loop / coupler_loop /
solver_writer）共用同一套验证契约 —— 统一 ORACLE 接入、容差语义、报告格式，
降低外部协作门槛，为 G1→G2 显式宣告和 D-09 PDK 接入铺路。

本模块是**统一契约层**（不重构四套内部实现）：
  VerificationSpec      —— 描述「一个待验目标」：ORACLE 真值怎么算、候选怎么比、
                           容差怎么解释、事实来源是什么。
  VerificationOutcome   —— 统一验收结果（报告格式 / JSON 序列化）。
  run_verification()    —— 统一执行器：算 ORACLE → 跑候选 → 比对 → 出 Outcome。

独立性红线：ORACLE 全部为确定性物理定律锚（fdfd 本征 / 超模 / tmm 解析 /
对称性定理 / 死代码黄金参考），LLM 不进判决路径；候选求解器独立实现。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


# ---------------------------------------------------------------------------
# 统一验证契约
# ---------------------------------------------------------------------------
@dataclass
class VerificationSpec:
    spec_id: str                     # 唯一标识，如 "B1" / "WG-500x220" / "DC-gap0.3"
    metric: str                      # 指标名：neff / kappa / transmission / power_frac / ...
    oracle_kind: str                 # 'physical_law' | 'fdfd_eigen' | 'fdfd_supermode'
                                     # | 'symmetry_theorem' | 'tmm_analytic'
    oracle_fn: Callable              # oracle_fn(params) -> 真值（确定性物理锚）
    compare_fn: Callable             # compare_fn(candidate, oracle) -> err
    tol: float                       # 容差
    tol_mode: str = "abs"            # 'abs' | 'rel' | 'abs_balance'
    target_desc: str = ""            # 人类可读的目标描述（几何/参数）
    params: Dict[str, Any] = field(default_factory=dict)
    source: str = ""                 # 黄金参考事实来源
    candidate_desc: str = ""         # 候选求解器描述（谁在跑）

    def err_ok(self, err: float) -> bool:
        return err <= self.tol


# ---------------------------------------------------------------------------
# 统一验收结果
# ---------------------------------------------------------------------------
@dataclass
class VerificationOutcome:
    spec_id: str
    passed: bool
    metric: str
    oracle_kind: str
    candidate: Optional[float]
    oracle_value: Optional[float]
    err: float
    tol: float
    tol_mode: str
    target_desc: str = ""
    source: str = ""
    candidate_desc: str = ""
    diagnostics: str = ""
    elapsed_s: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """统一 JSON 报告格式（四套裁判一致对外）。"""
        return {
            "spec_id": self.spec_id,
            "metric": self.metric,
            "oracle_kind": self.oracle_kind,
            "passed": self.passed,
            "candidate": self.candidate,
            "oracle": self.oracle_value,
            "err": round(float(self.err), 6) if self.err is not None else None,
            "tol": self.tol,
            "tol_mode": self.tol_mode,
            "target_desc": self.target_desc,
            "source": self.source,
            "candidate_desc": self.candidate_desc,
            "diagnostics": self.diagnostics,
            "elapsed_s": round(self.elapsed_s, 1),
            "extra": self.extra,
        }

    def brief(self) -> str:
        """单行摘要（CLI 输出用）。"""
        flag = "PASS" if self.passed else "FAIL"
        return (f"[{flag}] {self.spec_id:<16} {self.metric:<12} "
                f"{self.oracle_kind:<18} "
                f"cand={self.candidate} oracle={self.oracle_value} "
                f"err={self.err:.6f} tol={self.tol} ({self.tol_mode})")


# ---------------------------------------------------------------------------
# 统一执行器
# ---------------------------------------------------------------------------
def run_verification(spec: VerificationSpec,
                     candidate_fn: Callable[[VerificationSpec, Any], Any],
                     oracle_value: Any = None) -> VerificationOutcome:
    """统一执行：算 ORACLE 真值 → 跑候选 → 比对 → 出统一 Outcome。

    candidate_fn : callable(spec, oracle_value) -> 候选输出
    oracle_value  : 可预传（例如已算过避免重复）；否则调 spec.oracle_fn(spec.params)。
    """
    t0 = time.time()
    diagnostics = ""
    try:
        if oracle_value is None:
            oracle_value = spec.oracle_fn(spec.params)
        cand = candidate_fn(spec, oracle_value)
        err = spec.compare_fn(cand, oracle_value)
        if err is None or err != err:      # None 或 NaN
            passed, err = False, float("inf")
            diagnostics = "比对失败：候选/真值非法"
        else:
            passed = spec.err_ok(err)
    except Exception as e:                 # 诚实标注失败原因，不吞
        passed, err = False, float("inf")
        diagnostics = f"执行异常：{type(e).__name__}: {e}"
        cand, oracle_value = None, oracle_value
    dt = time.time() - t0
    return VerificationOutcome(
        spec_id=spec.spec_id, passed=passed, metric=spec.metric,
        oracle_kind=spec.oracle_kind, candidate=cand,
        oracle_value=oracle_value, err=err, tol=spec.tol,
        tol_mode=spec.tol_mode, target_desc=spec.target_desc,
        source=spec.source, candidate_desc=spec.candidate_desc,
        diagnostics=diagnostics, elapsed_s=dt)


# ---------------------------------------------------------------------------
# 常用比对函数（按 tol_mode 语义统一）
# ---------------------------------------------------------------------------
def cmp_abs(candidate: float, oracle: float) -> float:
    """绝对误差。"""
    return abs(float(candidate) - float(oracle))


def cmp_rel(candidate: float, oracle: float) -> float:
    """相对误差（oracle=0 时退化为绝对误差）。"""
    o = float(oracle)
    return abs(float(candidate) - o) / (abs(o) + 1e-30)


def cmp_abs_balance(candidate: float, oracle: float) -> float:
    """平衡度：candidate 为某端口占比，oracle 为理想占比（0.5）。"""
    return abs(float(candidate) - float(oracle))


def cmp_le(candidate: float, oracle: float) -> float:
    """不等式锚（上界）：candidate ≤ oracle 的**越界量**。

    返回 0 = 满足（candidate ≤ oracle）；正值 = 超出上界的幅度。
    与 `err_ok(err) = err <= tol` 配合 ⇒ 判定 `candidate ≤ oracle + tol`。

    用途：物理定律不等式锚（如 B19 无源无增益 |T| ≤ 1），损耗合法、
    增益判 FAIL。cmp_abs 会把这个「单向合法」误判成绝对误差。
    """
    return max(0.0, float(candidate) - float(oracle))


def cmp_ge(candidate: float, oracle: float) -> float:
    """不等式锚（下界）：candidate ≥ oracle 的**缺口量**。

    返回 0 = 满足（candidate ≥ oracle）；正值 = 低于下界的幅度。
    与 `err_ok(err) = err <= tol` 配合 ⇒ 判定 `candidate ≥ oracle - tol`。
    """
    return max(0.0, float(oracle) - float(candidate))


# 比较函数按 cmp 语义分发（build_harness_specs 等适配器消费）。
# 🔴 cmp='le'/'ge' 是**单向**不等式，绝不能用 cmp_abs 替代——B19（无源上界）
# 的 candidate=0.9999 在 cmp_abs 下 |0.9999−1.0|=1e-4 > tol=1e-9 会假 FAIL。
_CMP_FN_MAP = {
    "abs": cmp_abs,
    "rel": cmp_rel,
    "abs_balance": cmp_abs_balance,
    "le": cmp_le,
    "ge": cmp_ge,
}


def compare_fn_for(cmp_mode: str) -> Callable:
    """按 cmp 语义取比较函数；未知值回落 cmp_abs（向后兼容）。"""
    return _CMP_FN_MAP.get(cmp_mode, cmp_abs)
