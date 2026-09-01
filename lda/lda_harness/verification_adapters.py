"""LDA · 四套裁判到统一验证契约的适配器（D-04）。

把项目内四套裁判（harness B1-B11 / waveguide_loop / coupler_loop / solver_writer）
各自的目标描述、ORACLE 接入、容差语义、候选求解器统一到 VerificationSpec，
使全量回归可经统一入口（run_all_specs.py）执行并输出统一报告。

每个 build_*_specs 返回 (specs, cand_map)：
  specs     : List[VerificationSpec]（统一契约，含 oracle_fn/compare_fn/tol/source）
  cand_map  : Dict[spec_id, candidate_fn(spec, oracle_value) -> 候选值]
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .verification_spec import (
    VerificationSpec, cmp_abs, cmp_rel, cmp_abs_balance,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_SOLVER_DIR = os.path.join(os.path.dirname(_HERE), "lda_solver")
_AGENT_DIR = os.path.join(os.path.dirname(_HERE), "lda_agent")


def _ensure_paths():
    for p in (_SOLVER_DIR, _AGENT_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# 1. harness（B1-B18 物理定律 + E1-E7 实证语料锚 · D-62 双 ground）
# ---------------------------------------------------------------------------
def build_harness_specs(defs: Optional[Dict] = None
                        ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    from .benchmarks import BENCHMARK_DEFS
    from .golden import golden_with_source
    from .empirical_bank import EmpiricalCorpus, EmpiricalAnchor

    defs = defs or BENCHMARK_DEFS
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}
    # D-62 实证锚：加载实测语料（seed + 社区落库增量），供 E1-E7 实证锚题取 golden
    anchor = None
    for bid in sorted(defs.keys()):
        d = defs[bid]
        params = dict(d["default_params"])

        # D-63 溯源分级：empirical=A 级可公开溯源（计入实证锚）；
        #   empirical_unverified=B 级待溯源（同走死标量判决，但单独标注、不计入可溯源计数）
        if d.get("anchor") in ("empirical", "empirical_unverified"):
            if anchor is None:
                anchor = _load_empirical_anchor()
            eid = d.get("empirical_id")
            unverified = (d.get("anchor") == "empirical_unverified")

            # A 级（empirical）：强制要求可公开溯源，B 级语料一律挡在判决之外；
            # B 级（empirical_unverified）：显式放行取值但标注，且不计入可溯源计数
            _req_trace = (not unverified)

            def _emp_oracle(p, eid=eid, anchor=anchor, _req=_req_trace):
                val, _src, _note = anchor.resolve(eid, require_traceable=_req)
                if val is None:
                    raise ValueError(
                        f"实证语料不可用: {eid} —— {_note}"
                        f"（B 级语料无公开溯源定位符，禁止作 golden；"
                        f"须补 DOI/URL 后升级 A 级）")
                return val

            specs.append(VerificationSpec(
                spec_id=bid,
                metric=d["metric"],
                oracle_kind="empirical_measurement",
                oracle_fn=_emp_oracle,
                compare_fn=cmp_abs,
                tol=d["tol"],
                tol_mode="abs",
                target_desc=d.get("title", ""),
                params=params,
                source=(d.get("oracle", "empirical-measurement")
                        + (" ⚠️B级·待溯源（无 DOI/URL，不计入可溯源实证锚）"
                           if unverified else "")),
                candidate_desc=(
                    "FDFD 本征模 n_eff(λ) 中心差分（独立频域求解，非 golden 自证）"
                    if d.get("candidate") == "fdfd_ng"
                    else "harness 参考候选（占位自证：candidate≡golden，恒 PASS，无验证价值）")))
            cand_map[bid] = (_fdfd_ng_candidate
                             if d.get("candidate") == "fdfd_ng"
                             else _harness_reference_candidate)
            continue

        def _oracle(p, bid=bid):
            val, _src, _note = golden_with_source(bid, p)
            return val

        specs.append(VerificationSpec(
            spec_id=bid,
            metric=d["metric"],
            oracle_kind="physical_law",
            oracle_fn=_oracle,
            compare_fn=cmp_abs,
            tol=d["tol"],
            tol_mode="abs",
            target_desc=d.get("title", ""),
            params=params,
            source=d.get("oracle", "physical_law"),
            candidate_desc="harness 候选求解器",
        ))
        cand_map[bid] = _harness_reference_candidate
    return specs, cand_map


def _load_empirical_anchor():
    """加载实证语料锚（seed_empirical.json + 社区落库增量 empirical_contributions.json）。

    语料=真实测量事实（文献/PDK 公开量级 + 社区经「具名人工评审→落地」流入），
    构成验证的第二道非 AI ground；LLM 永不进判决路径。
    """
    from .empirical_bank import EmpiricalCorpus, EmpiricalAnchor
    _here = os.path.dirname(os.path.abspath(__file__))
    corpus = EmpiricalCorpus()
    seed = os.path.join(_here, "seed_empirical.json")
    if os.path.exists(seed):
        for m in EmpiricalCorpus.load(seed)._items.values():
            corpus.add(m, contributor="seed", source_file=seed, overwrite=True)
    contrib = os.path.join(os.path.dirname(_here), "lda_pdk", "empirical_contributions.json")
    if os.path.exists(contrib):
        try:
            for m in EmpiricalCorpus.load(contrib)._items.values():
                corpus.add(m, contributor="community", source_file=contrib,
                           overwrite=True)
        except Exception:  # 增量文件损坏时优雅降级（诚实：以 seed 为准）
            pass
    return EmpiricalAnchor(corpus)


def _harness_reference_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """参考候选：返回 ORACLE 真值本身（正确求解器语义，同 ReferenceCandidate）。

    ⚠️ 占位语义：|candidate − golden| ≡ 0 ⇒ 恒 PASS，**不产生验证价值**
    （D-64 实测：E1-E7 七道 |diff| 全为 0.0）。任何宣称「锚题 PASS」的结论，
    若走的是本候选，都只能算「自洽」而不能算「验证」。
    需要真验证的锚题须在 benchmarks.py 里显式指定 `candidate` 字段（如 fdfd_ng）。
    """
    return oracle_value


def _fdfd_ng_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """独立候选：标量亥姆霍兹 FDFD 本征模算 n_eff(λ) → 中心差分得 n_g。

    与实测 golden **完全独立**（不读取任何测量数据），构成真交叉验证：
        实测侧：OFDR 环腔群延迟 / MZI 传输谱（实验）
        计算侧：频域本征值 + 数值微分（独立物理求解）

    ⚠️ 网格 dl 必须由**中心波长**固定：若 dl 随扫描波长变化，差分测到的是
    网格伪变化而非物理色散（实测曾致 n_g 乱跳 5.93 / 1.85 / 1.61）。
    """
    _ensure_paths()
    from fdtd3d_waveguide import build_waveguide_field_3d
    from .oracle_mode import fdfd_mode_field   # oracle_mode 在 lda_harness 包内（非 lda_solver）

    p = spec.params
    wl = float(p["wl_um"])
    dl = wl / float(p.get("dl_factor", 24.0))    # 固定网格（关键）
    clad = float(p.get("clad_um", 3.0))
    Lz = float(p.get("Lz_um", 8.0))
    d = float(p.get("d_wl_um", 0.02))            # 差分半步长（默认 ±20nm）

    def _neff(w):
        eps3, meta = build_waveguide_field_3d(
            float(p["w_um"]), float(p["h_um"]),
            float(p["n_core"]), float(p["n_clad"]),
            w, dl=dl, clad_um=clad, Lz_um=Lz)
        return fdfd_mode_field(eps3, meta["dl"], w)[0]

    n1 = _neff(wl - d)
    n2 = _neff(wl + d)
    # n_g = n_eff − λ·dn_eff/dλ（中心差分）
    return (n1 + n2) / 2.0 - wl * (n2 - n1) / (2.0 * d)


def harness_perturbed_candidate(rel_err: float):
    """扰动候选：golden·(1+rel_err)——用于演示 fail 检测（同 PerturbedCandidate）。"""
    def _cand(spec: VerificationSpec, oracle_value: Any) -> float:
        return oracle_value * (1.0 + rel_err)
    return _cand


# ---------------------------------------------------------------------------
# 2. waveguide_loop（真 2D 波导 neff · FDFD 本征 ORACLE）
# ---------------------------------------------------------------------------
def build_waveguide_specs(cases: Optional[List] = None
                          ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    _ensure_paths()
    from waveguide_loop import WaveguideTarget, _default_cases
    from fdtd3d_waveguide import build_waveguide_field_3d, solve_waveguide_neff_3d
    from oracle_mode import fdfd_mode_field

    cases = cases if cases is not None else _default_cases()
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}
    for i, t in enumerate(cases):
        sid = f"WG-{t.label[:14]}"
        params = {
            "w_um": t.w_um, "h_um": t.h_um, "n_core": t.n_core,
            "n_clad": t.n_clad, "wl_um": t.wl_um,
            "dl": t.wl_um / t.dl_factor, "clad_um": t.clad_um,
            "Lz_um": t.Lz_um, "label": t.label, "tol": t.tolerance_abs,
        }

        def _oracle(p):
            eps3, meta = build_waveguide_field_3d(
                p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
            ne, _mode = fdfd_mode_field(eps3, meta["dl"], p["wl_um"])
            return ne

        def _cand(spec, oracle_value):
            p = spec.params
            eps3, meta = build_waveguide_field_3d(
                p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
            ne_oracle, mode2d = fdfd_mode_field(eps3, meta["dl"], p["wl_um"])
            ne = solve_waveguide_neff_3d(
                eps3, meta["dl"], p["wl_um"], n_clad=p["n_clad"],
                n_core=p["n_core"], mode_source=mode2d)
            return ne

        specs.append(VerificationSpec(
            spec_id=sid, metric="neff", oracle_kind="fdfd_eigen",
            oracle_fn=_oracle, compare_fn=cmp_abs,
            tol=params["tol"], tol_mode="abs",
            target_desc=t.label, params=params,
            source="fdfd 标量亥姆霍兹本征值（独立频域）",
            candidate_desc="标量 3D FDTD（独立时域）"))
        cand_map[sid] = _cand
    return specs, cand_map


# ---------------------------------------------------------------------------
# 3. coupler_loop（方向耦合器 κ / 对称分束器平衡度）
# ---------------------------------------------------------------------------
def build_coupler_specs(cases: Optional[List] = None
                        ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    _ensure_paths()
    from coupler_loop import CouplerTarget, _default_cases
    from fdtd3d_coupler import (
        build_coupler_field_3d, build_ybranch_field_3d,
        solve_supermode_projection_3d_torch, solve_port_powers_3d_torch,
    )
    from oracle_coupler import fdfd_coupler_supermodes, ybranch_oracle
    from oracle_mode import fdfd_mode_field

    cases = cases if cases is not None else _default_cases()
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}

    for i, t in enumerate(cases):
        dl = t.wl_um / t.dl_factor
        if t.kind == "dc":
            sid = f"DC-gap{t.gap_um}"
            params = {
                "kind": "dc", "w_um": t.w_um, "h_um": t.h_um,
                "gap_um": t.gap_um, "n_core": t.n_core, "n_clad": t.n_clad,
                "wl_um": t.wl_um, "dl": dl, "clad_um": t.clad_um,
                "Lz_um": t.dc_Lz_um, "label": t.label,
            }

            def _oracle(p):
                eps3, meta = build_coupler_field_3d(
                    p["w_um"], p["h_um"], p["gap_um"], p["n_core"], p["n_clad"],
                    p["wl_um"], dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
                o = fdfd_coupler_supermodes(eps3[:, :, 0], meta["dl"], p["wl_um"],
                                            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
                return o["kappa"]

            def _cand(spec, oracle_value):
                p = spec.params
                from coupler_loop import _beta_from_recurrence
                eps3, meta = build_coupler_field_3d(
                    p["w_um"], p["h_um"], p["gap_um"], p["n_core"], p["n_clad"],
                    p["wl_um"], dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
                o = fdfd_coupler_supermodes(eps3[:, :, 0], meta["dl"], p["wl_um"],
                                            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
                # 波导 A 单波导基模作源
                Nx, Ny = meta["Nx"], meta["Ny"]
                xs = (np.arange(Nx) - Nx / 2.0) * meta["dl"]
                ys = (np.arange(Ny) - Ny / 2.0) * meta["dl"]
                X, Y = np.meshgrid(xs, ys, indexing="ij")
                core_a = (np.abs(X - meta["xa_um"]) <= p["w_um"] / 2.0) & \
                         (np.abs(Y) <= p["h_um"] / 2.0)
                eps2_a = np.full((Nx, Ny), p["n_clad"] ** 2)
                eps2_a[core_a] = p["n_core"] ** 2
                _, src = fdfd_mode_field(eps2_a, meta["dl"], p["wl_um"])
                # 瞬态测量窗（与 coupler_loop 相同参数）
                sponge_z = max(8, min(60, meta["Nz"] // 4))
                src_um = meta["dl"] * (sponge_z + max(8, int(0.12 * (meta["Nz"] - 2 * sponge_z))))
                z_samp = src_um + 2.0 + 0.25 * np.arange(12)
                k0 = 2.0 * math.pi / p["wl_um"]
                dt_f = meta["dl"] * 0.95 / math.sqrt(3.0)
                period = int(round(2.0 * math.pi / (o["neff_s"] * k0 * dt_f)))
                prop = int(round((z_samp[0] - src_um) * o["neff_s"] / dt_f))
                transient = 400 + prop + 5 * period
                Os, Oa, zu = solve_supermode_projection_3d_torch(
                    eps3, meta["dl"], p["wl_um"], p["n_clad"], p["n_core"], src,
                    o["mode_s"], o["mode_a"], src_um=src_um, z_sample_um=z_samp,
                    M_cycles=20, transient=transient)
                bs = _beta_from_recurrence(Os, zu)
                ba = _beta_from_recurrence(Oa, zu)
                if bs is None or ba is None:
                    return float("nan")
                return (bs - ba) / 2.0

            specs.append(VerificationSpec(
                spec_id=sid, metric="kappa", oracle_kind="fdfd_supermode",
                oracle_fn=_oracle, compare_fn=cmp_rel,
                tol=t.tol_kappa, tol_mode="rel",
                target_desc=t.label, params=params,
                source="FDFD 超模法（对称/反对称超模 → κ）",
                candidate_desc="标量 3D FDTD 超模投影递推（独立时域）"))
            cand_map[sid] = _cand
        else:  # ybranch
            sid = "YB-1x2"
            params = {
                "kind": "ybranch", "w_um": t.w_um, "h_um": t.h_um,
                "n_core": t.n_core, "n_clad": t.n_clad, "wl_um": t.wl_um,
                "dl": dl, "clad_um": t.clad_um, "sep_um": t.sep_um,
                "l_in_um": t.l_in_um, "l_trans_um": t.l_trans_um,
                "l_out_um": t.l_out_um, "label": t.label,
                "tol_balance": t.tol_balance,
            }

            def _oracle(p):
                return ybranch_oracle()["target_frac"]

            def _cand(spec, oracle_value):
                p = spec.params
                eps3, meta = build_ybranch_field_3d(
                    p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                    sep_um=p["sep_um"], l_in_um=p["l_in_um"],
                    l_trans_um=p["l_trans_um"], l_out_um=p["l_out_um"],
                    dl=p["dl"], clad_um=p["clad_um"])
                Nx, Ny = meta["Nx"], meta["Ny"]
                xs = (np.arange(Nx) - Nx / 2.0) * p["dl"]
                ys = (np.arange(Ny) - Ny / 2.0) * p["dl"]
                X, Y = np.meshgrid(xs, ys, indexing="ij")
                inp_core = (np.abs(X) <= p["w_um"] / 2.0) & (np.abs(Y) <= p["h_um"] / 2.0)
                eps2_in = np.full((Nx, Ny), p["n_clad"] ** 2)
                eps2_in[inp_core] = p["n_core"] ** 2
                _, mode_in = fdfd_mode_field(eps2_in, p["dl"], p["wl_um"])
                src_um = p["l_in_um"] * 0.7
                z_out = meta["l_out_start_um"] + np.linspace(0.6, 4.2, 7)
                neff_avg = 0.5 * (p["n_core"] + p["n_clad"])
                dt_f = p["dl"] * 0.95 / math.sqrt(3.0)
                period = int(round(2.0 * math.pi / (neff_avg * 2.0 * math.pi / p["wl_um"] * dt_f)))
                prop = int(round((z_out[0] - src_um) * neff_avg / dt_f))
                transient = 400 + prop + 5 * period
                fa, fb, _zu, _pa, _pb, _srcz = solve_port_powers_3d_torch(
                    eps3, meta["dl"], p["wl_um"], p["n_clad"], p["n_core"], mode_in,
                    meta["mask_a"], meta["mask_b"], src_um=src_um,
                    z_sample_um=z_out, M_cycles=20, transient=transient, debug=True)
                n_avg = max(2, len(fa) // 2)
                return float(np.mean(fa[-n_avg:]))

            specs.append(VerificationSpec(
                spec_id=sid, metric="power_frac", oracle_kind="symmetry_theorem",
                oracle_fn=_oracle, compare_fn=cmp_abs_balance,
                tol=params["tol_balance"], tol_mode="abs_balance",
                target_desc=t.label, params=params,
                source="对称性定理（几何完全对称 ⇒ P1=P2=0.5·P_in）",
                candidate_desc="标量 3D FDTD 能流功率测量（独立时域）"))
            cand_map[sid] = _cand
    return specs, cand_map


# ---------------------------------------------------------------------------
# 4. solver_writer（AI-dev 自举写核 · tmm 解析 ORACLE）
# ---------------------------------------------------------------------------
def cmp_max_abs_err(candidate, oracle) -> float:
    """逐用例最大绝对误差（oracle/candidate 为 list[list[float]]，每用例多波长）。"""
    if not isinstance(candidate, list) or len(candidate) != len(oracle):
        return float("inf")
    errs = []
    for c, o in zip(candidate, oracle):
        if isinstance(o, (list, tuple)):
            if not isinstance(c, (list, tuple)) or len(c) != len(o):
                return float("inf")
            errs.append(max(abs(float(g) - float(oo)) for g, oo in zip(c, o)))
        else:
            errs.append(abs(float(c) - float(o)))
    return max(errs)


def build_solver_writer_specs(spec, candidate_code: str
                              ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    """把 solver_writer 的一个 SolverSpec + 候选代码适配成统一契约（单 spec）。

    oracle = 各测试用例 ORACLE 真值列表；candidate = 沙箱执行候选代码后的逐用例输出；
    compare = cmp_max_abs_err（同 solver_writer.Verifier 语义，max_abs_err ≤ tol）。
    """
    from .verification_spec import VerificationSpec

    # 序列化 test_cases（oracle 真值 + 输入）到 params
    cases_data = [{
        "name": c.name, "inputs": c.inputs,
        "oracle": list(c.oracle_value) if isinstance(c.oracle_value, (list, tuple))
                  else c.oracle_value,
        "tol": c.tol,
    } for c in spec.test_cases]

    def _oracle(p):
        return [c["oracle"] for c in p["cases"]]

    def _cand(spec_obj, oracle_value):
        p = spec_obj.params
        from solver_writer import SandboxExecutor
        # 构造临时 SolverSpec 以复用沙箱执行（只取 test_cases 的输入）
        from solver_writer import SolverSpec, TestCase
        tmp_cases = [TestCase(name=c["name"], inputs=c["inputs"],
                              oracle_value=c["oracle"], tol=c["tol"])
                     for c in p["cases"]]
        tmp_spec = SolverSpec(spec_id=spec.spec_id,
                              problem_statement=spec.problem_statement,
                              entrypoint=spec.entrypoint,
                              io_contract=spec.io_contract,
                              test_cases=tmp_cases,
                              oracle_kind=spec.oracle_kind)
        res = SandboxExecutor(timeout=120.0).run(p["code"], tmp_spec)
        if not res.get("ok"):
            return None
        out = []
        by_name = {r["name"]: r for r in res.get("results", [])}
        for c in p["cases"]:
            r = by_name.get(c["name"])
            out.append(r["value"] if r and r.get("ok") else None)
        return out

    specs = [VerificationSpec(
        spec_id=spec.spec_id, metric="transmission", oracle_kind="tmm_analytic",
        oracle_fn=_oracle, compare_fn=cmp_max_abs_err,
        tol=0.05, tol_mode="abs",
        target_desc=f"AI-dev 写核：{spec.entrypoint}（{len(spec.test_cases)} 用例）",
        params={"cases": cases_data, "code": candidate_code},
        source="tmm.py 解析透射谱（外部物理定律锚）",
        candidate_desc="AI-dev 候选求解核（沙箱执行）")]
    return specs, {spec.spec_id: _cand}
