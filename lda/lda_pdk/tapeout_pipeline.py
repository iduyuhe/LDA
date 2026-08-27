"""LDA 流片级验证管道（tapeout pipeline · 门3 接口细化 · v0.8.24 +S5 LVS）。

把「PDK → DRC → 工艺角 → **LVS** → 流片实测回流」串成一条可运行的
**流片级验证管道**。真实晶圆厂 PDK 对接属发动期（外联延期）；本模块先把
管道接口建好，用公开工艺参数（典型 SOI 180nm / Al-AlOx 量子工艺）示例
驱动，保证：

  1. 管道完整可运行（不依赖真实 PDK 也可全链路执行——诚实用示例参数）
  2. 真实 PDK 就位后**零改动接入**（数据驱动，非硬编码）
  3. 每个环节都是死标量判定，LLM 不进判决路径

五段管道：
  S1 PDK 装载     ：PDK 工艺参数 + DRC 设计规则（rules_from_pdk）
  S2 DRC 全器件自查：对设计中的每个器件跑 drc_check_device（可制造性）
  S3 工艺角扫描     ：SS/TT/FF 三角落的器件参数偏差 → 各角落 DRC 复检
                    （工艺波动下设计仍可制造 = 良率窗口）
  S3.5 几何寄生估算：版图 GDSII → 几何级 R/C 寄生估算（v0.8.31 主权几何级，
                    非 foundry 工艺级；提供 gds 实跑，缺省诚实跳过）
  S4 LVS 签核       ：版图 vs 原理图一致性（v0.8.24 新增，签核级）——
                    传入 link/placement/routes 实跑 run_lvs；
                    缺省诚实标注「未提供版图，本次跳过」（不造假）
  S5 流片实测回流   ：把「假设流片后实测数据」经实证语料评审流提交
                    （empirical.py → harness E1-E7 实证锚题实时生效）

诚实边界：S1-S3 用公开工艺参数示例（非真实 NDA-PDK）；S3.5 几何寄生估算
为几何级量级洞察（主权 RC 表，非 foundry 工艺级 deck），不进入签核硬门；
S4 LVS 需要版图输入（link+placement+routes），无输入时诚实跳过；S5 的
实测数据在真实流片前为占位（真实测量属发动期晶圆厂对接后）；管道接口
完整、判定规则完整。

运行：python -m lda_pdk.tapeout_pipeline --devices '{"RingAddDrop":{"R":10.0,"gap":0.3}}'
"""
from __future__ import annotations

import json
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

# 工艺角：对关键尺寸/折射率的偏差因子（公开文献典型，真实 PDK 覆盖）
PROCESS_CORNERS: Dict[str, Dict[str, float]] = {
    "SS": {"w_scale": 0.95, "n_scale": 0.99, "gap_scale": 1.05},   # 慢-慢（线宽偏小、损耗偏大）
    "TT": {"w_scale": 1.00, "n_scale": 1.00, "gap_scale": 1.00},   # 典型
    "FF": {"w_scale": 1.05, "n_scale": 1.01, "gap_scale": 0.95},   # 快-快（线宽偏大）
}


@dataclass
class CornerResult:
    """单个工艺角的 DRC 复检结果。"""

    corner: str
    passed: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    note: str = ""


@dataclass
class ParasiticResult:
    """版图几何级 RC 寄生估算结果（v0.8.31 · 主权几何级）。"""

    passed: bool                      # 是否越过主权几何护栏（非签核门）
    by_structure: Dict[str, Any] = field(default_factory=dict)
    total_r_ohm: float = 0.0
    total_c_ff: float = 0.0
    violations: List[str] = field(default_factory=list)
    honest_note: str = ""


@dataclass
class TapeoutResult:
    """流片级验证管道整体结果。"""

    pdk_key: str
    pdk_summary: Dict[str, Any]
    drc_passed: bool
    drc_violations: List[Dict[str, Any]]
    corners: List[CornerResult]
    corners_all_pass: bool
    lvs_result: Optional[Dict[str, Any]]
    parasitic_result: Optional[ParasiticResult]
    empirical_submission: Optional[Dict[str, Any]]
    accepted: bool
    honest_note: str


def _load_pdk(pdk_key: Optional[str] = None):
    """装载 PDK（示例 registry；真实 PDK 就位后同接口）。"""
    from lda_l2.pdk import get_default_registry
    reg = get_default_registry()
    pdks = reg.list_pdks()
    if not pdks:
        raise RuntimeError("无可用 PDK registry")
    key = pdk_key if pdk_key and pdk_key in pdks else pdks[0]
    return reg.get(key)


def _scale_params(params: Dict[str, float], corner: Dict[str, float]
                  ) -> Dict[str, float]:
    """按工艺角缩放器件参数（宽度/gap/折射率族）。"""
    out = dict(params)
    for k, v in params.items():
        if k in ("width", "wg_width"):
            out[k] = v * corner["w_scale"]
        elif k == "gap":
            out[k] = v * corner["gap_scale"]
        elif k in ("n_core", "n_si", "n_eff"):
            out[k] = v * corner["n_scale"]
    return out


def run_tapeout_pipeline(devices: Dict[str, Dict[str, float]],
                         pdk_key: Optional[str] = None,
                         submit_empirical: bool = False,
                         link=None, placement=None, routes=None,
                         gds: Optional[bytes] = None) -> TapeoutResult:
    """流片级验证管道主入口。

    devices   : {kind: params}，如 {"RingAddDrop": {"R": 10.0, "gap": 0.3}}
    pdk_key   : PDK key（缺省取 registry 第一个）
    submit_empirical : 是否把假想流片实测提交实证语料流（默认 False——
                      真实流片前不做占位提交，诚实标注）
    link/placement/routes : （v0.8.24 S4）LVS 签核输入——提供则实跑
                      run_lvs（版图-原理图一致性），缺省 None 诚实跳过。
    gds       : （v0.8.31 S3.5）版图 GDSII 字节——提供则实跑几何级 RC 寄生
                      估算（parasitic_rc）；缺省 None 诚实跳过（不造假）。
    """
    from lda_l2.drc import drc_check_device, rules_from_pdk
    pdk = _load_pdk(pdk_key)
    rules = rules_from_pdk(pdk)

    # S1+S2：DRC 全器件自查（TT 典型）
    violations: List[Dict[str, Any]] = []
    drc_ok = True
    for kind, params in devices.items():
        r = drc_check_device(kind, params, rules)
        if not r.passed:
            drc_ok = False
            for c in r.violations():
                violations.append({
                    "device": kind, "rule": c.rule, "param": c.param,
                    "value": c.value, "required": c.required,
                })

    # S3：工艺角扫描
    corners: List[CornerResult] = []
    corners_ok = True
    for cname, cscale in PROCESS_CORNERS.items():
        c_violations = []
        c_ok = True
        for kind, params in devices.items():
            p_scaled = _scale_params(params, cscale)
            r = drc_check_device(kind, p_scaled, rules)
            if not r.passed:
                c_ok = False
                for c in r.violations():
                    c_violations.append({
                        "device": kind, "rule": c.rule, "param": c.param,
                        "value": round(c.value, 4), "required": c.required,
                    })
        corners_ok = corners_ok and c_ok
        corners.append(CornerResult(
            corner=cname, passed=c_ok,
            checks=c_violations,
            note=f"{cname}: {'通过' if c_ok else '有违规'}"))

    # S3.5：几何级 RC 寄生估算（v0.8.31 · 设计侧主权闭环收口）
    # 语义：提供版图 GDS → 实跑（主权几何级 R/C 估算 + 护栏守门）；
    # 未提供 → SKIP 不阻断但诚实标注（与 S4 LVS 一致的不造假原则）。
    # 注意：寄生估算为设计侧深度洞察（几何护栏），不进入 accepted 硬门
    # （不替代 foundry 签核），但如实写进报告供设计者参考。
    para_res: Optional[ParasiticResult] = None
    if gds is not None:
        from lda_l2.gds_export import parse_gds_polygons
        from lda_l2.parasitic_rc import (
            estimate_parasitics, check_parasitic, parasitic_rc_markdown,
        )
        structs = parse_gds_polygons(gds).get("structures", {})
        para_rep = estimate_parasitics(structs)
        para_chk = check_parasitic(para_rep)
        para_res = ParasiticResult(
            passed=para_chk["all_pass"],
            by_structure=para_rep["by_structure"],
            total_r_ohm=para_rep["totals"]["R_series_ohm"],
            total_c_ff=para_rep["totals"]["C_total_ff"],
            violations=para_chk["violations"],
            honest_note=para_rep["honest_note"],
        )
    else:
        para_res = ParasiticResult(
            passed=True, by_structure={}, total_r_ohm=0.0, total_c_ff=0.0,
            violations=[],
            honest_note="S3.5 几何寄生估算未提供版图 GDS 输入，本次诚实跳过"
                       "——不造假。传 gds 字节即实跑。",
        )

    # S4：LVS 签核（版图 vs 原理图一致性，v0.8.24）
    # 语义：提供版图 → 实跑（REJECT 阻断签核）；未提供 → SKIP 不阻断但
    # 诚实标注（不造假声明已验，兼容既有器件级 DRC+角扫接口）。
    lvs_res = None
    if link is not None and placement is not None and routes is not None:
        from lda_l2.lvs import run_lvs
        lvs_res = run_lvs(link, placement, routes)
    else:
        lvs_res = {
            "verdict": "SKIP",
            "honest_note": "S4 LVS 未提供版图输入（link+placement+routes），"
                           "本次诚实跳过——不造假。传齐三输入即实跑签核。",
            "n_violations": 0,
        }
    lvs_ok = (lvs_res.get("verdict") != "REJECT")  # ACCEPT 通过 / SKIP 不阻断

    # S5：流片实测回流（仅当显式要求；真实流片前不占位）
    emp_sub = None
    if submit_empirical:
        from lda_pdk.empirical import submit_measurement
        # 示例：把设计目标作为「假想流片实测」提案（citation 必填占位）
        first_kind = next(iter(devices))
        emp_sub = submit_measurement({
            "id": f"tapeout-sim-{first_kind.lower()}",
            "device": first_kind,
            "metric": "drc_pass",
            "measured_value": 1.0 if drc_ok else 0.0,
            "uncertainty_abs": 0.0,
            "fab_source": pdk.foundry,
            "citation": "LDA tapeout pipeline 示例（真实流片前占位，非实测）",
            "method": "simulated",
            "proposed_by": "tapeout-pipeline",
        })

    accepted = bool(drc_ok and corners_ok and lvs_ok)
    para_v = "实跑" if gds is not None else "跳过（未提供版图 GDS）"
    honest = (
        f"流片级验证管道（门3 接口就绪）：PDK={pdk.foundry}::{pdk.node}；"
        f"S1-S3 用公开工艺参数示例（真实 NDA-PDK 属发动期）；"
        f"S3.5 几何寄生估算={para_v}（主权几何级，非 foundry 工艺级）；"
        f"S4 LVS={'实跑 ACCEPT' if lvs_res.get('verdict') == 'ACCEPT' else ('实跑 REJECT' if lvs_res.get('verdict') == 'REJECT' else '跳过（未提供版图输入）')}；"
        f"S5 实测回流在真实流片前不占位提交。判定死标量，LLM 不进判决路径。"
    )
    return TapeoutResult(
        pdk_key=pdk.foundry + "::" + pdk.node,
        pdk_summary=pdk.to_summary(),
        drc_passed=drc_ok,
        drc_violations=violations,
        corners=corners,
        corners_all_pass=corners_ok,
        lvs_result=lvs_res,
        parasitic_result=para_res,
        empirical_submission=emp_sub,
        accepted=accepted,
        honest_note=honest,
    )


def tapeout_to_dict(res: TapeoutResult) -> Dict[str, Any]:
    """TapeoutResult → JSON 可序列化 dict。"""
    return {
        "pdk_key": res.pdk_key,
        "pdk_summary": res.pdk_summary,
        "drc_passed": res.drc_passed,
        "drc_violations": res.drc_violations,
        "corners": [{"corner": c.corner, "passed": c.passed,
                     "checks": c.checks, "note": c.note} for c in res.corners],
        "corners_all_pass": res.corners_all_pass,
        "lvs_result": res.lvs_result,
        "parasitic_result": (None if res.parasitic_result is None else {
            "passed": res.parasitic_result.passed,
            "by_structure": res.parasitic_result.by_structure,
            "total_r_ohm": res.parasitic_result.total_r_ohm,
            "total_c_ff": res.parasitic_result.total_c_ff,
            "violations": res.parasitic_result.violations,
            "honest_note": res.parasitic_result.honest_note,
        }),
        "empirical_submission": res.empirical_submission,
        "accepted": res.accepted,
        "honest_note": res.honest_note,
        "verdict": "ACCEPT" if res.accepted else "REJECT",
    }


def _devices_from_arg(s: str) -> Dict[str, Dict[str, float]]:
    try:
        d = json.loads(s)
    except json.JSONDecodeError:
        raise ValueError("--devices 须为 JSON 对象，如 "
                         '{\\"RingAddDrop\\":{\\"R\\":10.0,\\"gap\\":0.3}}')
    return {k: {kk: float(vv) for kk, vv in v.items()} for k, v in d.items()}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="LDA 流片级验证管道（门3 接口）")
    ap.add_argument("--devices", default='{"RingAddDrop":{"R":10.0,"gap":0.3}}',
                    help="器件字典 JSON")
    ap.add_argument("--pdk", default=None, help="PDK key（缺省取 registry 第一个）")
    ap.add_argument("--submit-empirical", action="store_true",
                    help="提交假想流片实测（默认不提交，诚实标注）")
    ap.add_argument("--gds", default=None,
                    help="版图 GDSII 路径（v0.8.31 S3.5 几何寄生估算输入）")
    ap.add_argument("--out", default=None, help="报告输出路径")
    args = ap.parse_args(argv)

    gds_bytes = None
    if args.gds:
        with open(args.gds, "rb") as f:
            gds_bytes = f.read()

    devices = _devices_from_arg(args.devices)
    res = run_tapeout_pipeline(devices, pdk_key=args.pdk,
                               submit_empirical=args.submit_empirical,
                               gds=gds_bytes)
    d = tapeout_to_dict(res)

    print("=" * 64)
    print("LDA 流片级验证管道（门3 接口就绪）")
    print("=" * 64)
    print(f"  PDK            : {res.pdk_key}")
    print(f"  DRC 全器件自查 : {'PASS' if res.drc_passed else 'FAIL'}"
          f"  违规 {len(res.drc_violations)} 条")
    for v in res.drc_violations:
        print(f"      [violation] {v['device']} {v['rule']}: "
              f"{v['value']} vs 要求 {v['required']}")
    for c in res.corners:
        print(f"  工艺角 {c.corner:>2}        : {'PASS' if c.passed else 'FAIL'}"
              f"  {c.note}  违规 {len(c.checks)} 条")
    print(f"  三角落全过     : {res.corners_all_pass}")
    para = res.parasitic_result
    if para is not None:
        pv = "实跑" if para.by_structure else "跳过"
        print(f"  几何寄生估算   : {pv}"
              + (f"  R≈{para.total_r_ohm:.3f}Ω C≈{para.total_c_ff:.3f}fF"
                 if para.by_structure else "")
              + (f"  护栏触发 {len(para.violations)} 项" if para.violations else ""))
    lvs_r = res.lvs_result or {}
    lvs_v = lvs_r.get("verdict", "SKIP")
    print(f"  LVS 签核       : {lvs_v}"
          + (f"  {lvs_r.get('match', {}).get('n_nets_match', 0)}/"
             f"{lvs_r.get('match', {}).get('n_nets_total', 0)} 网一致"
             if lvs_v == "ACCEPT" else "")
          + (f"  违规 {lvs_r.get('n_violations', 0)} 项"
             if lvs_v == "REJECT" else ""))
    print(f"  实测回流       : "
          f"{'已提交(示例)' if res.empirical_submission else '未提交（真实流片前不占位）'}")
    print(f"  验收           : {d['verdict']}")
    print(f"  诚实声明       : {res.honest_note}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"  报告           : {args.out}")
    print("=" * 64)
    return 0 if res.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
