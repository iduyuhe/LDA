"""D-63 方向耦合器 × 量子读出：光子 1×N 分束网络供电量子读出控制线。

物理模型（诚实标注）：
- 光子侧：二叉树级联 DirectionalCoupler（D-55 design_coupler 真实 2D FDTD
  设计闭环）——每级 target_cross = 右子树权重 / 节点总权重；级联后每路实际
  功率 = 路径上各级 **FDTD 实测分束比** 之积（非解析假设）。
- 量子侧：每 qubit 读出保真度预算（D-47 design_fidelity 复用），有效 nbar 按
  实际功率权重缩放（微波功分器标准行为：P ∝ n̄，SNR ∝ √n̄）。
- 光↔微波物理独立：分束网络为光子域器件，功率→读出映射为**拓扑同构 / 接口
  规划**（延续 D-52 诚实标注），不做跨物理域功率传递的物理声称。
  LLM 不进判决路径：是否 PASS 由死标量比对决定。
"""
from typing import Any, Dict, List, Optional

import argparse
import json
import math
import os
import sys

# 默认参数
_DEF_F01S = [4.8, 5.0, 5.2]          # 3 qubit 读出（GHz）
_DEF_NBAR0 = 30.0                    # 单路全额微波光子数
_DEF_DELTA = 1.0
_DEF_G = 0.10
_DEF_KAPPA_R = 0.005
_DEF_T1_US = 25.0
_DEF_ETA = 0.5
_DEF_N_AMP = 1.0
_PWR_TOL = 0.05                      # 分束命中容差（|实际-目标|）
_SNR_MIN = 3.0                       # 缩放后单发 SNR 阈值
_F_MIN = 0.98                        # 缩放后读出保真度阈值
_GRID_CALIB_PATH = None              # 惰性解析（避免循环 import）


def _load_grid_calib() -> Optional[Dict[str, Any]]:
    """加载 κ_c(gap,λ) 全网格标定文件（D-60/D-68，供标定库驱动模式）。"""
    global _GRID_CALIB_PATH
    if _GRID_CALIB_PATH is None:
        _GRID_CALIB_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data", "kappa_grid_calibration.json")
    if not os.path.exists(_GRID_CALIB_PATH):
        return None
    with open(_GRID_CALIB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _pick_gap_from_calib(grid: Dict[str, Any], target_cross: float,
                         wl_um: float = 1.55) -> Optional[float]:
    """从标定库选 gap：扫 gap 网格，κ_c(gap) 反解 L_est=asin(√cross)/κ_c，
    选 L_est ∈ [5,80]µm 的最小 gap（大 gap 工艺友好）；无合适取最接近 20µm。"""
    if not grid or not grid.get("points") or not grid.get("gaps_um"):
        return None
    from lda_agent.wdm_coupler import kappa_c_grid_interp  # noqa: E402
    best, best_key = None, None
    for gap in sorted(grid["gaps_um"]):
        kc = kappa_c_grid_interp(grid, gap, wl_um)
        if kc is None or kc <= 0:
            continue
        L_est = math.asin(math.sqrt(min(max(target_cross, 0.0), 0.999))) / kc
        key = (0, gap) if 5.0 <= L_est <= 80.0 else (1, abs(L_est - 20.0))
        if best_key is None or key < best_key:
            best, best_key = gap, key
    return best


def _split_index(weights: List[float], lo: int, hi: int) -> int:
    """在 [lo,hi) 中找分割点 k：左子树权重最接近一半（近似等功率二分）。"""
    total = sum(weights[lo:hi])
    acc, best, best_diff = 0.0, lo + 1, float("inf")
    for k in range(lo + 1, hi):
        acc += weights[k - 1]
        diff = abs(acc - total / 2.0)
        if diff < best_diff:
            best, best_diff = k, diff
    return best


def _design_dc(target_cross: float, dc_id: str,
               calibrated: bool = False,
               grid: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """单级方向耦合器设计（D-55 design_coupler 真实 FDTD 闭环）。

    calibrated=True：gap 由 κ_c(gap,λ) 全网格标定库选择（D-66 标定库驱动
    ——反解 L_est=asin(√cross)/κ_c 落在合理工艺窗的最小 gap），而非固定 0.3。
    """
    from lda_agent.directional_coupler import design_coupler  # noqa: E402
    extra: Dict[str, Any] = {}
    kwargs: Dict[str, Any] = {}
    if calibrated:
        if grid is None:
            grid = _load_grid_calib()
        if grid is None:
            return {"id": dc_id, "ok": False,
                    "error": "标定库文件缺失（data/kappa_grid_calibration.json）"}
        gap_pick = _pick_gap_from_calib(grid, target_cross)
        if gap_pick is None:
            return {"id": dc_id, "ok": False,
                    "error": "标定库无法为 target_cross 选 gap"}
        kwargs["gap_um"] = gap_pick
        from lda_agent.wdm_coupler import kappa_c_grid_interp  # noqa: E402
        kc = kappa_c_grid_interp(grid, gap_pick, 1.55)
        L_est = (math.asin(math.sqrt(min(max(target_cross, 0.0), 0.999))) / kc
                 if kc and kc > 0 else None)
        extra = {"gap_from_calibration": True,
                 "kappa_c_calib_rad_um": round(kc, 6) if kc else None,
                 "L_est_um": round(L_est, 2) if L_est else None}
    rep = design_coupler(target_cross=target_cross, **kwargs)
    if not rep.get("ok"):
        return {"id": dc_id, "ok": False, "error": rep.get("error")}
    out = {
        "id": dc_id,
        "ok": True,
        "target_cross": round(rep["target_cross"], 5),
        "cross_val_fdtd": rep["cross_val_fdtd"],
        "L_target_um": rep["L_target_um"],
        "gap_um": rep["gap_um"],
        "iteration": rep["iteration"],
    }
    out.update(extra)
    return out


def design_splitter_readout(
    f01s: Optional[List[float]] = None,
    weights: Optional[List[float]] = None,
    nbar0: float = _DEF_NBAR0,
    delta: float = _DEF_DELTA, g: float = _DEF_G,
    kappa_r: float = _DEF_KAPPA_R,
    T1_us: float = _DEF_T1_US, eta: float = _DEF_ETA,
    N_amp: float = _DEF_N_AMP,
    calibrated: bool = False,
    grid: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """方向耦合器 × 量子读出联合设计闭环。

    weights=None → 均匀 1/N。返回分束网络（每级 FDTD 设计）+ 每 qubit 读出
    预算（按实际功率缩放）+ 统一 IR 网表 + 联合验收。
    calibrated=True：每级 DC 的 gap 由 κ_c(gap,λ) 全网格标定库选择
    （D-66 标定库驱动——真实 FDTD 标定替代固定 gap=0.3）。
    """
    if f01s is None:
        f01s = list(_DEF_F01S)
    n_q = len(f01s)
    if weights is None:
        weights = [1.0 / n_q] * n_q
    if len(weights) != n_q or any(w <= 0 for w in weights):
        return {"ok": False, "error": "weights 须与 f01s 等长且全为正"}
    w_sum = sum(weights)
    weights = [w / w_sum for w in weights]

    # 1) 光子侧：二叉树级联 DC 分束网络
    splitters: List[Dict[str, Any]] = []
    leaves: List[Dict[str, Any]] = []
    dc_idx = 0

    def build(lo: int, hi: int, path_power: float) -> None:
        nonlocal dc_idx
        if hi - lo == 1:
            leaves.append({"qubit_index": lo, "w_target": weights[lo],
                           "p_actual": path_power})
            return
        k = _split_index(weights, lo, hi)
        left_w = sum(weights[lo:k])
        right_w = sum(weights[k:hi])
        target_cross = right_w / (left_w + right_w)
        dc_idx += 1
        dc = _design_dc(target_cross, f"dc{dc_idx}",
                        calibrated=calibrated, grid=grid)
        if not dc["ok"]:
            raise RuntimeError(f"DC 设计失败: {dc.get('error')}")
        cross_fdtd = dc["cross_val_fdtd"]
        dc["left_span"] = [lo, k]
        dc["right_span"] = [k, hi]
        dc["left_frac"] = round(1.0 - cross_fdtd, 5)   # thru 分支
        dc["right_frac"] = round(cross_fdtd, 5)        # cross 分支
        splitters.append(dc)
        build(lo, k, path_power * (1.0 - cross_fdtd))
        build(k, hi, path_power * cross_fdtd)

    try:
        build(0, n_q, 1.0)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    # 功率归一化（Σ p_actual = 1，含 FDTD 分束误差）
    p_tot = sum(l["p_actual"] for l in leaves)
    for l in leaves:
        l["p_actual"] = l["p_actual"] / p_tot
        l["delta"] = round(abs(l["p_actual"] - l["w_target"]), 5)

    # 2) 量子侧：每 qubit 读出预算（nbar 按实际功率缩放）
    from lda_agent.readout_fidelity import design_fidelity  # noqa: E402
    per_qubit: List[Dict[str, Any]] = []
    f_list: List[float] = []
    for i, f01 in enumerate(f01s):
        p_act = next(l["p_actual"] for l in leaves
                     if l["qubit_index"] == i)
        nbar_eff = nbar0 * p_act
        rep = design_fidelity(f01=f01, delta=delta, g=g, kappa_r=kappa_r,
                              T1_us=T1_us, nbar=nbar_eff, eta=eta,
                              N_amp=N_amp)
        budget = rep.get("budget", {})
        f_val = budget.get("F", 0.0)
        f_list.append(f_val)
        per_qubit.append({
            "qubit": i + 1, "f01_ghz": f01,
            "p_actual": round(p_act, 5),
            "nbar_eff": round(nbar_eff, 4),
            "snr": round(budget.get("snr", 0.0), 3),
            "F": round(f_val, 5),
            "t_m_star_ns": rep.get("t_m_star_ns"),
            "passed": bool(rep["acceptance"]["passed"]),
        })

    # 3) 统一 IR 网表（光子分束网络 + 量子读出同一网表）
    from lda_ir import (  # noqa: E402
        IRModel, Transmon, Resonator, DirectionalCoupler, Waveguide,
        ObjectiveSpec, validate,
    )
    comps: List[Any] = []
    nets: List[Dict[str, str]] = []
    objectives: List[Any] = []
    # 功率源 + 光子分束网络
    comps.append(Waveguide(id="power"))
    for s in splitters:
        comps.append(DirectionalCoupler(id=s["id"], gap=s["gap_um"],
                                        Lc=s["L_target_um"]))
    for i, f01 in enumerate(f01s):
        f_r = f01 + delta
        l_phy = 1.0 / (4.0 * f_r * 1e9 * math.sqrt(0.4e-6 * 1.5e-10))
        comps.append(Transmon(id=f"q{i + 1}",
                              E_J=(f01 + 0.25) ** 2 / (8.0 * 0.25),
                              E_C=0.25))
        comps.append(Resonator(id=f"r{i + 1}", Lp=0.4e-6, Cp=1.5e-10,
                               l=l_phy,
                               l_bounds=(l_phy * 0.5, l_phy * 1.5)))
        nets.append({"id": f"q{i + 1}r{i + 1}",
                     "ports": [f"q{i + 1}.readout", f"r{i + 1}.in"]})
        objectives.append(ObjectiveSpec(bid="B12",
                                        target=round(f_r, 4),
                                        tol=0.02, role="objective"))
    # 光子分束网络（根输入 power → DC in1 → thru1 左/thru2 右 → 递归 → 叶子接 r_i.in）
    dc_ir = {dc["id"]: dc for dc in splitters}

    def ir_build(lo: int, hi: int, in_net: str) -> None:
        if hi - lo == 1:
            nets.append({"id": f"sp{lo + 1}",
                         "ports": [in_net, f"r{lo + 1}.in"]})
            return
        k = _split_index(weights, lo, hi)
        # 找覆盖 [lo,hi) 的 DC
        d = None
        for s in splitters:
            if s["left_span"][0] == lo and s["right_span"][1] == hi:
                d = s
                break
        if d is None:
            raise RuntimeError(f"IR 构建: 区间 [{lo},{hi}) 无对应 DC")
        nets.append({"id": d["id"] + "_in",
                     "ports": [in_net, d["id"] + ".in1"]})
        ir_build(lo, k, d["id"] + ".thru1")
        ir_build(k, hi, d["id"] + ".thru2")

    ir_build(0, n_q, "power.in")

    model = IRModel(
        domain="hybrid", name="splitter-readout",
        components=comps, objectives=objectives,
        notes=f"{n_q}-qubit 读出 × 光子 {len(splitters)} 级 DC 分束网络："
              f"每 qubit 按实际功率权重缩放读出 n̄（拓扑同构映射，"
              f"光↔微波物理独立——接口规划，诚实标注）",
    )
    for nt in nets:
        model.connect(nt["id"], *nt["ports"])
    ir_errs = validate(model)

    # 4) 联合验收（死标量）
    checks = [
        {"name": f"分束网络命中（|Δ|≤{_PWR_TOL}）",
         "ok": all(l["delta"] <= _PWR_TOL for l in leaves),
         "detail": "; ".join(
             f"q{l['qubit_index'] + 1}: 目标{l['w_target']:.2f} "
             f"实得{l['p_actual']:.2f}(Δ={l['delta']:.3f})"
             for l in leaves)},
        {"name": f"缩放后单发 SNR ≥ {_SNR_MIN}",
         "ok": all(p["snr"] >= _SNR_MIN for p in per_qubit),
         "detail": f"SNR∈[{min(p['snr'] for p in per_qubit):.2f}, "
                   f"{max(p['snr'] for p in per_qubit):.2f}]"},
        {"name": f"缩放后读出保真度 F ≥ {_F_MIN}",
         "ok": all(p["F"] >= _F_MIN for p in per_qubit),
         "detail": f"F∈[{min(f_list):.4f}, {max(f_list):.4f}]"},
        {"name": "混合 IR 网表校验（DC 分束 + 量子读出同一网表）",
         "ok": not ir_errs,
         "detail": f"{len(model.components)} 器件 + {len(model.nets)} 网表"
                   f"{'；' + '；'.join(ir_errs[:3]) if ir_errs else ' 通过'}"},
        {"name": "诚实标注：光↔微波拓扑同构（物理独立）",
         "ok": True,
         "detail": "分束网络为光子域器件（FDTD 实测分束比）；功率→读出映射为"
                   "拓扑同构/接口规划，不做跨物理域功率传递的物理声称"},
    ]
    if calibrated:
        g_from_calib = [s for s in splitters if s.get("gap_from_calibration")]
        checks.append({
            "name": "标定库驱动（gap 由 κ_c(gap,λ) 网格选择，D-66）",
            "ok": bool(g_from_calib) and all(
                s["cross_val_fdtd"] > 0 for s in g_from_calib),
            "detail": "; ".join(
                f"{s['id']}: cross={s['target_cross']} → gap="
                f"{s['gap_um']}µm（κ_c={s['kappa_c_calib_rad_um']} "
                f"L_est={s['L_est_um']}µm → FDTD 实测 "
                f"{s['cross_val_fdtd']}）" for s in g_from_calib)})
    accepted = all(c["ok"] for c in checks)
    verdict = (
        f"方向耦合器×量子读出 PASS：{len(splitters)} 级 DC 分束网络"
        f"（{'标定库驱动 gap' if calibrated else 'FDTD 实测分束'}"
        f"）→ {n_q} qubit 读出（缩放后 F∈"
        f"[{min(f_list):.4f}, {max(f_list):.4f}]）同一网表，功率分配命中"
        if accepted else
        "未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"{n_q}-qubit 读出 × {len(splitters)} 级 DC 分束网络",
        "n_qubits": n_q, "n_splitters": len(splitters),
        "f01s_ghz": f01s,
        "calibrated": calibrated,
        "splitters": splitters,
        "leaves": leaves,
        "per_qubit": per_qubit,
        "ir": {"schema_version": model.schema_version,
               "domain": model.domain,
               "n_components": len(model.components),
               "n_nets": len(model.nets), "validate_errors": ir_errs},
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": "光子侧：二叉树级联 DC（D-55 真实 FDTD 设计闭环，每级分束比取"
                "实测 cross_val_fdtd" +
                ("；gap 由 κ_c(gap,λ) 全网格标定库选择（D-66）"
                 if calibrated else "") +
                "）；量子侧：D-47 读出预算按实际功率权重缩放"
                "n̄（SNR ∝ √n̄）。光↔微波物理独立，拓扑同构映射为接口规划。"
                "LLM 不进判决路径。",
    }


def package_from_splitter_readout(f01s: Optional[List[float]] = None,
                                  **kw: Any) -> Dict[str, Any]:
    """把方向耦合器×量子读出设计包装为 D-44 统一 DesignPackage。"""
    from lda_design.design_package import SCHEMA_VERSION, _now_iso  # noqa: E402
    if f01s is None:
        f01s = list(_DEF_F01S)
    r = design_splitter_readout(f01s=f01s, **kw)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "设计失败"),
                "kind": "splitter_readout"}
    acc = r["acceptance"]
    return {
        "package_id": f"splitter-readout{len(f01s)}q",
        "schema_version": SCHEMA_VERSION,
        "kind": "splitter_readout", "domain": "hybrid",
        "title": r["title"],
        "created_at": _now_iso(),
        "ir": {"schema_version": r["ir"]["schema_version"],
               "domain": "hybrid",
               "n_components": r["ir"]["n_components"],
               "n_nets": r["ir"]["n_nets"],
               "validate_errors": r["ir"]["validate_errors"]},
        "design": {"targets": {"f01s_ghz": f01s},
                   "params": {"nbar0": kw.get("nbar0", _DEF_NBAR0),
                              "splitters": r["splitters"],
                              "leaves": r["leaves"]},
                   "inverse_design": {"formula": "光子二叉树级联 DC 分束网络"
                                                 "（每级 D-55 真实 2D FDTD "
                                                 "设计闭环，分束比取实测 "
                                                 "cross_val_fdtd）+ 每 qubit "
                                                 "读出 n̄ 按功率权重缩放 "
                                                 "（SNR ∝ √n̄）"}},
        "verification": {"checks": acc["checks"], "passed": bool(acc["passed"]),
                         "verdict": r["verdict"]},
        "artifacts": {"per_qubit": r["per_qubit"],
                      "power_budget": r["leaves"]},
        "honest_notes": "光↔微波物理独立：分束网络为光子域器件，功率→读出"
                        "映射为拓扑同构/接口规划（延续 D-52 诚实标注），"
                        "不做跨物理域功率传递的物理声称。"
                        "LLM 不进判决路径：PASS 由死标量比对决定。",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LDA 方向耦合器 × 量子读出组合")
    ap.add_argument("--f01s", default="4.8,5.0,5.2",
                    help="qubit 读出频率(GHz)，逗号分隔")
    ap.add_argument("--weights", default="",
                    help="功率权重(逗号分隔)，空=均匀")
    ap.add_argument("--calibrated", action="store_true",
                    help="标定库驱动：每级 DC 的 gap 由 κ_c(gap,λ) 网格选择")
    args = ap.parse_args()
    f01s = [float(x) for x in args.f01s.split(",") if x.strip()]
    ws = [float(x) for x in args.weights.split(",") if x.strip()] or None
    r = design_splitter_readout(f01s, weights=ws, calibrated=args.calibrated)
    out = {k: r[k] for k in ("title", "n_qubits", "n_splitters", "calibrated",
                             "splitters", "leaves", "per_qubit", "ir",
                             "acceptance", "verdict", "note")}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
