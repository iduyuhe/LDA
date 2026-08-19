"""LDA · 统一验证回归入口（D-04：四套裁判统一契约）。

把项目内四套裁判（harness B1-B11 / waveguide_loop / coupler_loop / solver_writer）
经 VerificationSpec 统一契约一次性跑全量，输出统一报告：
  - harness   B1-B11（参考候选）        → 预期 11/11 PASS
  - waveguide 3 例 neff（FDFD ORACLE）  → 预期 3/3 PASS（纯 numpy，慢）
  - coupler   3 例（超模/对称性 ORACLE）→ 预期 3/3 PASS（需 torch GPU）
  - solver_writer 1.4 闭环（v1 候选）   → 预期 PASS

用法：
  python run_all_specs.py                       # 全量（waveguide 慢，~15min）
  python run_all_specs.py --skip waveguide      # 跳过慢项
  python run_all_specs.py --perturb 0.1         # 另跑 harness 扰动候选（演示 fail 检测）
  python run_all_specs.py --json reports/unified_verification_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# 统一经包路径导入：lda_harness 内部用相对导入（from .golden 等），须把 lda/ 加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for _p in (os.path.join(_ROOT, "lda_agent"),
           os.path.join(_ROOT, "lda_solver")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_harness.verification_spec import (
    VerificationSpec, run_verification, VerificationOutcome,
)
from lda_harness.verification_adapters import (
    build_harness_specs, harness_perturbed_candidate,
    build_waveguide_specs, build_coupler_specs, build_solver_writer_specs,
)


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return torch.cuda.is_available()
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="LDA 统一验证回归（D-04）")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="跳过项: harness|waveguide|coupler|solver_writer")
    ap.add_argument("--perturb", type=float, default=None,
                    help="另跑 harness 扰动候选（golden·(1+rel_err)），演示 fail 检测")
    ap.add_argument("--json", default="",
                    help="统一报告 JSON 输出路径（缺省不写文件）")
    args = ap.parse_args()

    outcomes: list = []
    started = time.time()

    def run_group(title: str, specs, cand_map, prefix: str = ""):
        if prefix in args.skip:
            print(f"── {title}：已跳过")
            return
        print(f"\n── {title} ────────────────────────")
        for spec in specs:
            out = run_verification(spec, cand_map[spec.spec_id])
            outcomes.append(out)
            print("  " + out.brief())

    # 1) harness B1-B11（参考候选）
    hs, hc = build_harness_specs()
    run_group("harness B1-B11（参考候选，预期 11/11 PASS）", hs, hc, "harness")
    # 1b) 扰动候选（可选，演示 fail 检测）
    if args.perturb is not None:
        print(f"\n── harness 扰动候选（rel_err={args.perturb}，预期 FAIL 检测）──")
        for spec in hs:
            out = run_verification(spec, harness_perturbed_candidate(args.perturb))
            outcomes.append(out)
            print("  " + out.brief())

    # 2) waveguide（纯 numpy，慢）
    if "waveguide" not in args.skip:
        ws, wc = build_waveguide_specs()
        run_group("waveguide 真 2D neff（FDFD ORACLE，预期 3/3 PASS）", ws, wc, "waveguide")

    # 3) coupler（需 torch GPU）
    if "coupler" not in args.skip:
        if _torch_available():
            cs, cc = build_coupler_specs()
            run_group("coupler 方向耦合器/分束器（超模/对称性 ORACLE，预期 3/3 PASS）",
                      cs, cc, "coupler")
        else:
            print("\n── coupler：无 torch GPU，跳过（数值验收在本机 GPU venv 跑）──")

    # 4) solver_writer 1.4 闭环（v1 候选）
    if "solver_writer" not in args.skip:
        from solver_writer import _build_1d_fdtd_spec, _CANDIDATE_V1
        ss, sc = build_solver_writer_specs(_build_1d_fdtd_spec(), _CANDIDATE_V1)
        run_group("solver_writer AI-dev 写核（v1 候选，tmm ORACLE，预期 PASS）",
                  ss, sc, "solver_writer")

    # ---- 统一报告 ----
    total = len(outcomes)
    n_pass = sum(1 for o in outcomes if o.passed)
    elapsed = time.time() - started
    print(f"\n{'=' * 60}")
    print(f"统一验证回归：{n_pass}/{total} PASS  （耗时 {elapsed:.1f}s）")
    print("  判定红线：ORACLE 全为确定性物理定律锚，LLM 不进判决路径。")
    if args.json:
        report = {
            "kind": "unified_verification_report",
            "contract": "VerificationSpec v1 (D-04)",
            "total": total, "passed": n_pass,
            "elapsed_s": round(elapsed, 1),
            "outcomes": [o.to_dict() for o in outcomes],
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print(f"报告已写入：{args.json}")
    return 0 if n_pass == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
