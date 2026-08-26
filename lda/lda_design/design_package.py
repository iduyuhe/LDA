"""LDA · D-44 统一设计包规范（design outcome 的统一交付格式）。

把 D-37（环形 add-drop）/ D-41（量子逆设计）/ D-42（WDM 系统）/
D-43（readout 混合链路）四类设计结果统一成**同一份 DesignPackage**——
无论设计什么，交付物格式一致、可机器校验、可汇总对比：

  DesignPackage = {
    package_id, schema_version, kind, domain, title, created_at,
    ir        : 设计意图（D-40 IR：schema 版本 / 器件数 / 网表 / 校验）
    design    : targets（目标）+ params（设计参数）+ inverse_design（反解）
    verification : checks[]（死标量比对明细）+ passed + verdict
    artifacts : layout_svg / spectrum / gds / report（按 kind 可缺省）
    honest_notes : 模型/数据来源诚实标注
  }

设计包规范要点：
  - verification.passed 是唯一验收门（LLM 不进判决路径）；
  - ir 字段保证"每个包都回溯到设计意图 IR"；
  - honest_notes 强制记录模型假设与数据来源（诚实优先）。

CLI：python -m lda_design.design_package --all（构建全部 4 类包到 reports/packages/）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)   # lda/
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

SCHEMA_VERSION = "0.1"
PACKAGE_KINDS = ("add_drop", "quantum", "wdm", "readout_chain", "multiqubit",
                 "readout_fidelity", "multiqubit_fidelity", "mixed_system",
                 "coupler", "wdm_coupler", "splitter_readout")

# ---------------------------------------------------------------------------
# 引擎闭环入口（设计→验证闭环引擎，target-based 网格搜索 + 真实求解器双重验证）
# 这些 kind 不走 _BUILDERS/build_all（避免批量构建时跑 FDTD），单独作为"设计包"
# 的一等公民，把闭环结果包成统一 schema，供端到端面板"给目标→出设计包"使用。
# ---------------------------------------------------------------------------
ENGINE_KINDS = ("engine_waveguide", "engine_braggmirror",
                "engine_transmon", "engine_ringresonator", "engine_mzi",
                "engine_phc", "engine_qres", "engine_fluxonium",
                "engine_tcoup", "engine_mmi", "engine_gcoupler",
                "engine_dcoupler", "engine_tuntransmon",
                "engine_readoutpair", "engine_czgate",
                # v0.8.11e：loss/效率类引擎（实证锚判决路径）
                "engine_ybranchloss", "engine_gratingeff",
                "engine_crossing", "engine_mmiel", "engine_sinpl")
ENGINE_KIND_MAP = {
    "engine_waveguide": "Waveguide",
    "engine_braggmirror": "BraggMirror",
    "engine_transmon": "Transmon",
    "engine_ringresonator": "RingResonator",
    "engine_mzi": "MziInterferometer",
    "engine_phc": "PhCCavity",
    "engine_qres": "ReadoutResonator",
    "engine_fluxonium": "Fluxonium",
    "engine_tcoup": "TunableCoupler",
    "engine_mmi": "Mmi1x2",
    "engine_gcoupler": "GratingCoupler2",
    "engine_dcoupler": "DirectionalCoupler2",
    "engine_tuntransmon": "TunableTransmon",
    "engine_readoutpair": "ReadoutPair",
    "engine_czgate": "CzGate",
    "engine_ybranchloss": "YbranchLoss",
    "engine_gratingeff": "GratingEff",
    "engine_crossing": "Crossing",
    "engine_mmiel": "MmiEl",
    "engine_sinpl": "SinPl",
}
ENGINE_DOMAIN = {
    "Waveguide": "photon", "BraggMirror": "photon",
    "Transmon": "quantum", "RingResonator": "photon",
    "MziInterferometer": "photon", "PhCCavity": "photon",
    "ReadoutResonator": "quantum", "Fluxonium": "quantum",
    "TunableCoupler": "quantum",
    "Mmi1x2": "photon", "GratingCoupler2": "photon",
    "DirectionalCoupler2": "photon",
    "TunableTransmon": "quantum", "ReadoutPair": "quantum",
    "CzGate": "quantum",
    "YbranchLoss": "photon", "GratingEff": "photon",
    "Crossing": "photon", "MmiEl": "photon", "SinPl": "photon",
}
_ENGINE_DEFAULT_TARGET = {
    "engine_waveguide": 3.25,      # 目标 neff
    "engine_braggmirror": 0.999,   # 目标 R_min ≥ 0.999
    "engine_transmon": 5.0,        # 目标 f01 (GHz)
    "engine_ringresonator": 9.0,   # 目标 FSR (nm)
    "engine_mzi": 20.0,            # 目标 FSR (nm) · 干涉型
    "engine_phc": 2200.0,          # 目标共振波长 λ_res (nm)
    "engine_qres": 7.5,            # 目标基模频率 f0 (GHz)
    "engine_fluxonium": 6.0,       # 目标 f01 (GHz)
    "engine_tcoup": 0.005,         # 目标 |g_eff| (GHz)
    "engine_mmi": 100.0,           # 目标 L_mmi (um)
    "engine_gcoupler": 2.38,       # 目标 λ_B (um)
    "engine_dcoupler": 20.0,       # 目标 L_3dB (um)
    "engine_tuntransmon": 6.0,     # 目标 f01 (GHz)
    "engine_readoutpair": 0.002,   # 目标 |χ| (GHz)
    "engine_czgate": 700.0,        # 目标 t_CZ (ns)
    "engine_ybranchloss": 3.4,     # 目标 split_loss (dB，实证锚)
    "engine_gratingeff": 0.45,     # 目标 coupling_eff（实证锚）
    "engine_crossing": 0.18,       # 目标 IL (dB，实证锚)
    "engine_mmiel": 0.05,          # 目标 excess_loss (dB，实证锚)
    "engine_sinpl": 0.087,         # 目标 PL (dB/cm，实证锚)
}
_ENGINE_TITLE = {
    "engine_waveguide": "直波导 · 目标有效折射率 neff",
    "engine_braggmirror": "布拉格镜 · 目标反射率 R_min（最少周期）",
    "engine_transmon": "Transmon 量子比特 · 目标频率 f01",
    "engine_ringresonator": "环形谐振器 · 目标 FSR（解析锚）",
    "engine_mzi": "MZI 马赫曾德尔干涉仪 · 目标 FSR（解析干涉谱）",
    "engine_phc": "光子晶体腔 · 目标共振波长 λ_res（2D FDTD + 布拉格带边锚）",
    "engine_qres": "CPW λ/4 读出谐振器 · 目标基模频率 f0（1D 传输线 FDTD + 传输线锚）",
    "engine_fluxonium": "Fluxonium 超导量子比特 · 目标频率 f01（相位对角化 + 双基对拍）",
    "engine_tcoup": "可调耦合器 · 目标有效耦合 |g_eff|（三模对角化 + 二阶微扰锚）",
    "engine_mmi": "MMI 1×2 · 目标自映像长 L_mmi（多模干涉 + B16 锚）",
    "engine_gcoupler": "光栅耦合器 · 目标 Bragg 波长 λ_B（一阶衍射 + Bragg 锚）",
    "engine_dcoupler": "方向耦合器 · 目标 3dB 长 L_3dB（超模拍频 + B14 锚）",
    "engine_tuntransmon": "可调 transmon · 目标 f01（SQUID 磁通调谐 + B25 锚）",
    "engine_readoutpair": "比特-读出配对 · 目标 |χ|（严格对角化 + B26 锚）",
    "engine_czgate": "色散 CZ 门 · 目标 t_CZ（条件相位 π + B27 锚）",
    "engine_ybranchloss": "Y-branch 分束损耗 · 实证锚 E-YBRANCH-LOSS 判决",
    "engine_gratingeff": "光栅耦合效率 · 实证锚 E-GRATING-EFF 判决",
    "engine_crossing": "crossing 插入损耗+串扰 · 实证锚 E-SOI-CROSS-IL/XT 判决",
    "engine_mmiel": "MMI 1×2 过量损耗 · 实证锚 E-MMI-1X2-EL 判决",
    "engine_sinpl": "SiN 传播损耗 · 实证锚 E-SIN-PL-800 判决",
}


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 4 类打包器（各包装一个已交付设计闭环的产物为统一 schema）
# ---------------------------------------------------------------------------
def package_from_add_drop(target_fsr: float = 17.5, gap: float = 0.3,
                          **kw) -> Dict[str, Any]:
    """D-37 环形 add-drop 产品链路 → 统一设计包。"""
    from lda_agent.ring_adddrop import build_package
    r = build_package(target_fsr_nm=target_fsr, params={"gap": gap})
    acc = r["acceptance"]
    return {
        "package_id": f"add-drop-fsr{target_fsr}",
        "schema_version": SCHEMA_VERSION,
        "kind": "add_drop", "domain": "photon",
        "title": "环形 add-drop 可制造设计包",
        "created_at": _now_iso(),
        "ir": {"schema_version": "0.3", "domain": "photon",
               "n_components": 1, "n_nets": 0,
               "validate_errors": []},
        "design": {"targets": {"fsr_nm": target_fsr},
                   "params": r["params"],
                   "inverse_design": r.get("inverse_design")},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"layout_svg": r.get("layout_svg"),
                      "spectrum": r.get("spectrum"),
                      "gds": r.get("gds"),
                      "budgets": {"coupling": r.get("coupling_budget"),
                                  "q": r.get("q_budget"),
                                  "loss": r.get("loss_budget")}},
        "honest_notes": r.get("note", ""),
    }


def package_from_quantum(kind: str = "Transmon", target: float = 5.0,
                         **kw) -> Dict[str, Any]:
    """D-41 量子 agent 逆设计闭环 → 统一设计包。"""
    from lda_agent.quantum_design import design_quantum
    r = design_quantum(kind, target, kw.get("extra"))
    v = r["verification"]
    return {
        "package_id": f"quantum-{kind.lower()}-{target}",
        "schema_version": SCHEMA_VERSION,
        "kind": "quantum", "domain": "quantum",
        "title": f"量子逆设计包（{kind}）",
        "created_at": _now_iso(),
        "ir": {"schema_version": (r.get("ir") or {}).get("schema_version", "0.3"),
               "domain": "quantum", "n_components": 1, "n_nets": 0,
               "validate_errors": (r.get("ir") or {}).get("validate_errors", [])},
        "design": {"targets": {kind.lower(): target},
                   "params": r["inverse_design"]["params"],
                   "inverse_design": {"formula": r["inverse_design"]["formula"]}},
        "verification": {"checks": [{"name": "严格数值双验证",
                                     "ok": bool(r["passed"]),
                                     "detail": v["verdict"]}],
                         "passed": bool(r["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"numerical": v.get("numerical"),
                      "analytic": v.get("analytic")},
        "honest_notes": "量子闭式反解 + D-39 严格数值双验证（LLM 不进判决）。",
    }


def package_from_wdm(channels: Optional[List[float]] = None, gap: float = 0.3,
                     **kw) -> Dict[str, Any]:
    """D-42 WDM 多环级联系统设计 → 统一设计包。"""
    from lda_agent.wdm_system import design_wdm
    channels = channels or [1550.0, 1552.5, 1555.0, 1557.5]
    r = design_wdm(channels, gap=gap)
    acc = r["acceptance"]
    return {
        "package_id": f"wdm-{len(channels)}ch",
        "schema_version": SCHEMA_VERSION,
        "kind": "wdm", "domain": "photon",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"], "domain": "photon",
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"channels_nm": r["channels_nm"]},
                   "params": {"ring_radii_um": r["ring_radii_um"],
                              "gap_um": r["gap_um"], "wg_width_um": r["wg_width_um"]},
                   "inverse_design": r.get("inverse_design"),
                   "metrics": r.get("metrics")},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"layout_svg": r.get("layout_svg"),
                      "spectrum": r.get("spectrum"),
                      "gds": r.get("gds")},
        "honest_notes": r.get("note", ""),
    }


def package_from_readout(f01: float = 5.0, delta: float = 1.0, g: float = 0.10,
                         kappa_r: float = 0.005, **kw) -> Dict[str, Any]:
    """D-43 光子-量子混合链路（dispersive readout）→ 统一设计包。"""
    from lda_agent.qubit_readout_chain import design_chain
    r = design_chain(f01=f01, delta=delta, g=g, kappa_r=kappa_r)
    acc = r["acceptance"]
    return {
        "package_id": f"readout-f01{f01}-d{delta}",
        "schema_version": SCHEMA_VERSION,
        "kind": "readout_chain", "domain": "hybrid",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"],
               "domain": r["ir"]["domain"],
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"f01_ghz": f01, "f_r_ghz": r["f_r_ghz"],
                               "g_ghz": g, "kappa_r_ghz": kappa_r},
                   "params": r["params"],
                   "inverse_design": {"formula": "E_J/l/Cc/Q_ext 闭式反解"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"verification_detail": r["verification"]},
        "honest_notes": r.get("note", ""),
    }


def package_from_multiqubit(f01s: Optional[List[float]] = None, **kw) -> Dict[str, Any]:
    """D-46 N-qubit 频率复用读出（光子-量子混合系统）→ 统一设计包。"""
    from lda_agent.multiqubit_readout import package_from_multiqubit as _p
    return _p(f01s=f01s, **kw)


def package_from_readout_fidelity(f01: float = 5.0, **kw) -> Dict[str, Any]:
    """D-47 单发读出保真度预算 → 统一设计包。"""
    from lda_agent.readout_fidelity import package_from_readout_fidelity as _p
    return _p(f01=f01, **kw)


def package_from_multiqubit_fidelity(
        f01s: Optional[List[float]] = None, **kw) -> Dict[str, Any]:
    """D-51 N-qubit 复用读出逐 qubit 保真度 → 统一设计包。"""
    from lda_agent.multiqubit_fidelity import package_from_multiqubit_fidelity as _p
    return _p(f01s=f01s, **kw)


def package_from_mixed_system(
        wdm_channels_nm: Optional[List[float]] = None,
        qubit_f01s_ghz: Optional[List[float]] = None, **kw) -> Dict[str, Any]:
    """D-52 多环 WDM × 量子读出混合巨型系统 → 统一设计包。"""
    from lda_agent.mixed_system import package_from_mixed_system as _p
    return _p(wdm_channels_nm=wdm_channels_nm, qubit_f01s_ghz=qubit_f01s_ghz,
              **kw)


def package_from_coupler(target_cross: float = 0.5, **kw) -> Dict[str, Any]:
    """D-55 方向耦合器设计闭环 → 统一设计包。"""
    from lda_agent.directional_coupler import package_from_coupler as _p
    return _p(target_cross=target_cross, **kw)


def package_from_wdm_coupler(
        channels_nm: Optional[List[float]] = None, **kw) -> Dict[str, Any]:
    """D-57 耦合器×WDM 组合（FDTD 标定驱动 gap）→ 统一设计包。"""
    from lda_agent.wdm_coupler import package_from_wdm_coupler as _p
    return _p(channels_nm=channels_nm, **kw)


def package_from_splitter_readout(
        f01s: Optional[List[float]] = None, **kw) -> Dict[str, Any]:
    """D-63 方向耦合器×量子读出（分束网络供电控制线）→ 统一设计包。"""
    from lda_agent.splitter_readout import (
        package_from_splitter_readout as _p,
    )
    return _p(f01s=f01s, **kw)


_BUILDERS = {
    "add_drop": package_from_add_drop,
    "quantum": package_from_quantum,
    "wdm": package_from_wdm,
    "readout_chain": package_from_readout,
    "multiqubit": package_from_multiqubit,
    "readout_fidelity": package_from_readout_fidelity,
    "multiqubit_fidelity": package_from_multiqubit_fidelity,
    "mixed_system": package_from_mixed_system,
    "coupler": package_from_coupler,
    "wdm_coupler": package_from_wdm_coupler,
    "splitter_readout": package_from_splitter_readout,
}

_DEFAULTS = {
    "add_drop": {"target_fsr": 17.5, "gap": 0.3},
    "quantum": {"kind": "Transmon", "target": 5.0},
    "wdm": {"channels": [1550.0, 1552.5, 1555.0, 1557.5], "gap": 0.3},
    "readout_chain": {"f01": 5.0, "delta": 1.0, "g": 0.10, "kappa_r": 0.005},
    "multiqubit": {"f01s": [4.8, 5.0, 5.2]},
    "readout_fidelity": {"f01": 5.0},
    "multiqubit_fidelity": {"f01s": [4.8, 5.0, 5.2],
                            "T1_us_list": [20.0, 15.0, 25.0]},
    "mixed_system": {"wdm_channels_nm": [1550.0, 1553.0, 1556.0],
                     "qubit_f01s_ghz": [4.8, 5.0, 5.2]},
    "coupler": {"target_cross": 0.5, "transient_cycles": 400},
    "wdm_coupler": {"channels_nm": [1550.0, 1553.0, 1556.0],
                    "gap_scan": [0.25, 0.30, 0.35]},
    "splitter_readout": {"f01s": [4.8, 5.0, 5.2]},
}


def build_package(kind: str, params: Optional[Dict[str, Any]] = None,
                  **kw) -> Dict[str, Any]:
    """统一派发：kind + 参数 → 统一 DesignPackage。

    params 为 dict（含子 kind 等键，不与包 kind 冲突）；kw 为显式键值。
    """
    if kind not in _BUILDERS:
        return {"ok": False, "error": f"未知设计包 kind={kind}（可选 {list(_BUILDERS)}）"}
    p = dict(_DEFAULTS.get(kind, {}))
    if params:
        p.update({k: v for k, v in params.items() if v is not None})
    p.update({k: v for k, v in kw.items() if v is not None})
    try:
        pkg = _BUILDERS[kind](**p)
        pkg["ok"] = True
        return pkg
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120], "kind": kind}


# ---------------------------------------------------------------------------
# 设计包 schema 校验（机器可校验的统一格式）
# ---------------------------------------------------------------------------
_REQUIRED = ("package_id", "schema_version", "kind", "domain", "title",
             "created_at", "design", "verification", "honest_notes")


def validate_package(pkg: Dict[str, Any]) -> List[str]:
    """校验 DesignPackage 是否符合统一规范。返回错误列表（空=合法）。"""
    errs: List[str] = []
    for f in _REQUIRED:
        if f not in pkg:
            errs.append(f"缺必填字段 '{f}'")
    if pkg.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version 应为 {SCHEMA_VERSION}，got {pkg.get('schema_version')}")
    if pkg.get("kind") not in (PACKAGE_KINDS + ENGINE_KINDS):
        errs.append(f"kind 未知：'{pkg.get('kind')}'")
    if pkg.get("domain") not in ("photon", "quantum", "hybrid"):
        errs.append(f"domain 未知：'{pkg.get('domain')}'")
    v = pkg.get("verification") or {}
    if "passed" not in v:
        errs.append("verification 缺 'passed' 验收门")
    if not pkg.get("honest_notes"):
        errs.append("honest_notes 为空（诚实标注必填）")
    return errs


def summarize(pkg: Dict[str, Any]) -> str:
    """人类可读摘要（供汇总/面板展示）。"""
    v = pkg.get("verification", {})
    d = pkg.get("design", {})
    return (f"[{'PASS' if v.get('passed') else 'FAIL'}] {pkg.get('kind')} · "
            f"{pkg.get('title')} · domain={pkg.get('domain')} · "
            f"目标 {d.get('targets')} · 参数 {d.get('params')} · "
            f"{str(v.get('verdict'))[:80]}")


# ---------------------------------------------------------------------------
# 引擎闭环 → 统一设计包（端到端"给目标 → 出设计包"桥接）
# ---------------------------------------------------------------------------
def package_from_engine(kind: str, target: Optional[float] = None,
                        top_k: int = 5, **kw) -> Dict[str, Any]:
    """把 DesignEngine 真实设计闭环结果包成统一 DesignPackage。

    kind 为 ENGINE_KINDS 之一（映射到 DesignEngine 的 4 类器件）。
    内部真跑：物理定律 ORACLE 网格搜索 + 仅对 top-K 跑真实求解器双重验证，
    返回的 verdict / passed 全部来自求解器死标量比对（LLM 不进判决路径）。
    不在此重写任何验证逻辑——只把已验证结果按统一 schema 包装成可下载交付物。
    """
    ek = ENGINE_KIND_MAP.get(kind, kind)
    if target is None:
        target = _ENGINE_DEFAULT_TARGET.get(kind, 5.0)
    from lda_design.design_engine import DesignEngine
    eng = DesignEngine()
    res = eng.design(ek, float(target), top_k=int(top_k))
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "design failed"),
                "kind": kind}
    best = res.get("best")
    passed = (res.get("passed", 0) or 0) > 0
    domain = ENGINE_DOMAIN.get(ek, "photon")
    checks = [{
        "name": "闭环搜索 + 真实求解器双重验证",
        "ok": passed,
        "detail": (f"搜索 {res.get('searched')} 点 → 验证 {res.get('verified')} "
                   f"候选 → 通过 {res.get('passed')}"),
    }]
    if best:
        checks.append({
            "name": "最优候选已验证",
            "ok": bool(best.get("passed")),
            "detail": best.get("verdict", ""),
        })
    pkg = {
        "package_id": f"dp-{kind}-t{target}",
        "schema_version": SCHEMA_VERSION,
        "kind": kind, "domain": domain,
        "title": f"设计闭环包 · {res.get('title', _ENGINE_TITLE.get(kind, ek))}",
        "created_at": _now_iso(),
        "ir": {"schema_version": "0.3", "domain": domain, "n_components": 1,
               "n_nets": 0, "validate_errors": []},
        "design": {
            "targets": {"target": float(target),
                        "metric": res.get("metric_name"),
                        "unit": res.get("target_unit", "")},
            "params": (best or {}).get("params", {}),
            "inverse_design": {"mode": "网格搜索 + 物理定律 ORACLE 引导"},
            "metrics": {"searched": res.get("searched"),
                        "verified": res.get("verified"),
                        "passed": res.get("passed"),
                        "best_metric": (best or {}).get("metric"),
                        "best_err": (best or {}).get("err")},
        },
        "verification": {
            "checks": checks,
            "passed": passed,
            "verdict": (best or {}).get("verdict") or res.get("note", ""),
        },
        "artifacts": {"engine_result": res},
        "honest_notes": (res.get("note") or "")
            + " · 闭环结果包成统一 DesignPackage（LLM 不进判决路径）。",
    }
    pkg["ok"] = True
    return pkg


def engine_catalog() -> List[Dict[str, Any]]:
    """端到端面板用的闭环器件目录（硬编码元数据，避免每次 GET 实例化引擎）。

    返回 4 类闭环器件：kind / 引擎 kind / 标题 / 指标名 / 目标单位 / 默认目标 /
    域 / 是否仅解析锚（诚实标注 FDTD 抽检需 GPU）。
    """
    return [{
        "kind": pk,
        "engine_kind": ek,
        "title": _ENGINE_TITLE.get(pk, ek),
        "metric_name": {
            "Waveguide": "neff (FDTD)", "BraggMirror": "R_min (FDTD)",
            "Transmon": "f01 (对角化, GHz)", "RingResonator": "FSR (解析, nm)",
            "MziInterferometer": "FSR (干涉谱, nm)",
            "PhCCavity": "cavity_wl (2D FDTD, nm)",
            "ReadoutResonator": "f0 (1D TL-FDTD, GHz)",
            "Fluxonium": "f01 (相位对角化, GHz)",
            "TunableCoupler": "|g_eff| (三模对角化, GHz)",
            "Mmi1x2": "L_mmi (模式叠加, um)",
            "GratingCoupler2": "λ_B (Bragg, um)",
            "DirectionalCoupler2": "L_3dB (超模拍频, um)",
            "TunableTransmon": "f01 (koch+SQUID, GHz)",
            "ReadoutPair": "|χ| (严格对角化, GHz)",
            "CzGate": "t_CZ (条件相位 π, ns)",
            "YbranchLoss": "split_loss (dB, 实证锚)",
            "GratingEff": "coupling_eff (实证锚)",
            "Crossing": "IL (dB, 实证锚)",
            "MmiEl": "excess_loss (dB, 实证锚)",
            "SinPl": "PL (dB/cm, 实证锚)",
        }.get(ek, ""),
        "target_unit": {"Waveguide": "", "BraggMirror": "",
                        "Transmon": "GHz", "RingResonator": "nm",
                        "MziInterferometer": "nm",
                        "PhCCavity": "nm",
                        "ReadoutResonator": "GHz",
                        "Fluxonium": "GHz",
                        "TunableCoupler": "GHz",
                        "Mmi1x2": "um", "GratingCoupler2": "um",
                        "DirectionalCoupler2": "um",
                        "TunableTransmon": "GHz", "ReadoutPair": "GHz",
                        "CzGate": "ns",
                        "YbranchLoss": "dB", "GratingEff": "",
                        "Crossing": "dB", "MmiEl": "dB",
                        "SinPl": "dB/cm"}.get(ek, ""),
        "default_target": _ENGINE_DEFAULT_TARGET.get(pk),
        "domain": ENGINE_DOMAIN.get(ek, "photon"),
        "analytic_only": ek == "RingResonator",
    } for pk, ek in ENGINE_KIND_MAP.items()]


_KIND_TITLES = {
    "add_drop": "环形 add-drop 可制造设计包",
    "quantum": "量子逆设计包（Transmon）",
    "wdm": "WDM 多环级联系统",
    "readout_chain": "光子-量子混合读出链路",
    "multiqubit": "N-qubit 频率复用读出",
    "readout_fidelity": "单发读出保真度预算",
    "multiqubit_fidelity": "N-qubit 复用读出保真度",
    "mixed_system": "WDM×量子读出混合巨型系统",
    "coupler": "方向耦合器设计闭环",
    "wdm_coupler": "耦合器×WDM 组合",
    "splitter_readout": "分束网络供电读出",
}


def package_catalog() -> List[Dict[str, Any]]:
    """端到端面板用的统一设计包目录（11 类 param-based 包，附默认参数）。"""
    return [{"kind": k, "title": _KIND_TITLES.get(k, k),
             "defaults": _DEFAULTS.get(k, {})}
            for k in _DEFAULTS]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_all(out_dir: Optional[str] = None) -> Dict[str, Any]:
    """构建全部 4 类设计包并落盘 reports/packages/。"""
    out = {"schema_version": SCHEMA_VERSION, "packages": {}}
    for kind in PACKAGE_KINDS:
        pkg = build_package(kind)
        errs = validate_package(pkg)
        out["packages"][kind] = {
            "package_id": pkg.get("package_id"),
            "passed": pkg.get("verification", {}).get("passed"),
            "schema_ok": not errs,
            "schema_errors": errs,
        }
    out["all_schema_ok"] = all(
        v["schema_ok"] for v in out["packages"].values())
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        for kind in PACKAGE_KINDS:
            pkg = build_package(kind)
            with open(os.path.join(out_dir, f"{kind}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(pkg, f, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA D-44 统一设计包")
    ap.add_argument("--all", action="store_true", help="构建全部 4 类包")
    ap.add_argument("--kind", default=None, choices=list(PACKAGE_KINDS))
    args = ap.parse_args()
    if args.kind:
        pkg = build_package(args.kind)
        print(json.dumps({k: pkg[k] for k in
                          ("package_id", "kind", "domain", "design",
                           "verification", "honest_notes")},
                         ensure_ascii=False, indent=2))
        return 0 if pkg.get("verification", {}).get("passed") else 1
    out = build_all(os.path.join(_LDA, "reports", "packages"))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["all_schema_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
