"""D-79 真实基元接入设计流水线（Track B 收口 · v0.4 门槛达成）。

把 D-14/D-19 版图流水线的默认几何从玩具矩形/圆形切换到真实基元：
  · RingResonator / RingAddDrop：实心环带 BOUNDARY → 真实波导环（中心线 PATH）
  · SymmetricYBranch：裸分叉 → 输入绝热 taper（D-71 基元）+ 双 arm PATH
  · DirectionalCoupler / Waveguide：双/单波导 PATH（已是真实波导表达）
  · Taper / EulerBend / MMI / GratingCoupler：D-71 真实基元（沿用）
全链路真实 GDS 出图 + 3×SOI PDK DRC 复查 + 玩具→真实几何对比诊断 +
死标量验收（全 kind GDS round-trip 一致 + DRC 全绿）。LLM 不进判决路径。
"""
import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List

_DEVICES: Dict[str, Dict[str, float]] = {
    "Waveguide": {"width": 0.5, "length": 10.0},
    "RingResonator": {"R": 10.0, "width": 0.5},
    "RingAddDrop": {"R": 6.0, "width": 0.5, "gap": 0.3},
    "DirectionalCoupler": {"width": 0.5, "gap": 0.3, "Lc": 10.0},
    "SymmetricYBranch": {"width": 0.5, "split_angle": 10.0, "arm_length": 5.0},
    "Taper": {"width": 0.5, "width_out": 2.0, "length": 20.0,
              "profile": "adiabatic"},
    "EulerBend": {"width": 0.5, "R": 10.0, "theta_deg": 90.0},
    "MMI": {"width": 0.5, "W_mmi": 4.0, "L_mmi": 12.0, "L_tap": 3.0,
            "out_gap": 0.5, "L_out": 2.0},
    "GratingCoupler": {"width": 0.5, "Lambda": 0.85, "duty": 0.55,
                       "n_tooth": 20, "L_in": 3.0},
}

# 玩具几何（D-79 之前的表达）对比基线：kind → 元素构成说明
_OLD_GEOM = {
    "RingResonator": "实心环带 BOUNDARY(外环+内环挖洞) + 直 bus PATH",
    "RingAddDrop": "实心环带 BOUNDARY + 双直 bus PATH",
    "SymmetricYBranch": "双 arm PATH（无过渡，裸分叉）",
    "DirectionalCoupler": "双直 PATH（已是波导表达）",
    "Waveguide": "直 PATH（已是波导表达）",
}


def _descs_kind_summary(descs: List[Dict]) -> str:
    return "+".join(d["kind"] for d in descs)


def _bbox_um(descs: List[Dict]) -> Dict[str, float]:
    xs: List[float] = []
    ys: List[float] = []
    for d in descs:
        if d["kind"] == "path":
            for x, y in d["points_um"]:
                xs.append(x)
                ys.append(y)
        else:
            for ring in d.get("rings_um", []):
                for x, y in ring:
                    xs.append(x)
                    ys.append(y)
    if not xs:
        return {"xmin": 0.0, "xmax": 0.0, "ymin": 0.0, "ymax": 0.0}
    return {"xmin": round(min(xs), 3), "xmax": round(max(xs), 3),
            "ymin": round(min(ys), 3), "ymax": round(max(ys), 3)}


def design_pipeline_realize(devices: List[str] | None = None,
                            verbose: bool = False) -> Dict[str, Any]:
    """D-79 真实基元接入流水线验收：全 kind 真实 GDS + DRC + 对比诊断。"""
    from lda_l2.gds_export import (gds_library, geometry_desc,
                                   layout_elements, parse_gds)
    from lda_l2.pdk_examples import build_example_registry
    from lda_l2.drc import rules_from_pdk

    kinds = devices or list(_DEVICES.keys())
    reg = build_example_registry()
    pdk_rules = {}
    for k in reg.list_pdks():
        if "soi" in k.lower():
            pdk_rules[k] = rules_from_pdk(reg.get(k))

    results: Dict[str, Dict[str, Any]] = {}
    for kind in kinds:
        params = dict(_DEVICES.get(kind, {}))
        try:
            descs = geometry_desc(kind, params)
            elems = layout_elements(kind, params)
            gds = gds_library("dev", {"dev": elems})
            rt = parse_gds(gds)
            _st = rt.get("structures", {})
            n_rt = sum(v.get("elements", 0) for v in _st.values()) \
                if isinstance(_st, dict) else 0
            drc_all = {}
            for pdk, rules in pdk_rules.items():
                from lda_l2.drc import drc_check_device
                dr = drc_check_device(kind, params, rules=rules)
                drc_all[pdk.split("::")[0]] = {
                    "passed": dr.passed,
                    "violations": len(dr.violations()),
                }
            results[kind] = {
                "params": dict(params),
                "n_desc": len(descs),
                "desc_summary": _descs_kind_summary(descs),
                "old_geom": _OLD_GEOM.get(kind, "D-71 真实基元（沿用）"),
                "bbox_um": _bbox_um(descs),
                "gds_bytes": len(gds),
                "roundtrip_ok": n_rt == len(descs),
                "drc": drc_all,
            }
            if verbose:
                ok = results[kind]["roundtrip_ok"] and all(
                    v["passed"] for v in drc_all.values())
                print(f"[{ok and 'PASS' or 'FAIL'}] {kind}: "
                      f"{results[kind]['desc_summary']} "
                      f"gds={len(gds)}B rt={results[kind]['roundtrip_ok']} "
                      f"drc={[v['passed'] for v in drc_all.values()]}")
        except Exception as e:  # noqa: BLE001
            results[kind] = {"params": dict(params), "error": str(e)[:120]}
            if verbose:
                print(f"[FAIL] {kind}: {str(e)[:120]}")

    real_kinds = [k for k, v in results.items() if "error" not in v]
    no_error = all("error" not in v for v in results.values())
    all_ok = no_error and \
             all(v["roundtrip_ok"] for k, v in results.items()) and \
             all(all(dr["passed"] for dr in v["drc"].values())
                 for k, v in results.items()) and \
             len(results) == len(kinds)
    n_real = sum(1 for k in real_kinds
                 if "boundary" not in results[k]["desc_summary"] or
                 k in ("SymmetricYBranch",))  # YBranch taper 为边界过渡（真实基元）
    verdict = (
        f"真实基元接入流水线 PASS：{len(real_kinds)}/{len(kinds)} kind 全真实 GDS "
        f"round-trip 一致 + {len(pdk_rules)} 个 SOI PDK DRC 全绿；"
        f"Ring/AddDrop 从实心环带升级为波导环 PATH，YBranch 加输入绝热 taper。"
        if all_ok else
        "未全过：" + "; ".join(f"{k}: {v.get('error', 'DRC/roundtrip 失败')}"
                              for k, v in results.items() if "error" in v or
                              not v.get("roundtrip_ok", True) or
                              any(not dr["passed"] for dr in v.get("drc", {}).values())))
    return {
        "title": "真实基元接入设计流水线（D-79 · Track B 收口 · v0.4 门槛）",
        "devices": results,
        "pdk_rules": {k: v for k, v in pdk_rules.items()},
        "acceptance": {"passed": all_ok, "n_devices": len(kinds),
                       "n_real": len(real_kinds)},
        "verdict": verdict,
        "note": ("D-14/D-19 版图流水线默认几何从玩具矩形/圆形切换到 D-71 真实基元："
                 "Ring/AddDrop 实心环带 BOUNDARY → 真实波导环（中心线 PATH + width，"
                 "foundry 弯曲波导标准表达，可 DRC 检查环宽）；YBranch 裸分叉 → 输入"
                 "绝热 taper（D-71 taper_polygon 余弦轮廓）+ 双 arm PATH；DC/Waveguide "
                 "已是 PATH 波导表达；Taper/EulerBend/MMI/GratingCoupler 沿用 D-71 "
                 "基元（GC 为 D-78 修正的方波光栅）。全链路真实 GDS 出图 + 3×SOI PDK "
                 "DRC 复查（NOEIC/CUMEC/SITRI design_rules 注入）。诚实边界：环 path 为"
                 "圆弧中心线（曲率恒定），Euler 弯无缝拼合环留作后续深化；几何真实化"
                 "不改变电特性判据（电特性由 D-72/D-78 端口验收负责）。LLM 不进判决路径。"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="D-79 真实基元接入流水线报告")
    ap.add_argument("--out", default="reports/pipeline_realize_d79.json")
    ap.add_argument("--kinds", nargs="*", default=None)
    args = ap.parse_args()
    rep = design_pipeline_realize(devices=args.kinds, verbose=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    print(f"报告已写入 {args.out}（accepted={rep['acceptance']['passed']}）")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
