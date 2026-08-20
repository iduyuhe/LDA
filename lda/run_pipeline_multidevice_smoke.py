"""LDA · D-25 一键设计流水线多器件扩展 smoke。

验证 design_pipeline 扩展后覆盖全部已验证器件：
  1. Waveguide + target_neff → 逆设计 width + FDTD 验收 PASS（D-25 新）
  2. SymmetricYBranch → 分束验收（GPU live / 无 GPU 诚实 ORACLE 演示，D-25 新）
  3. Waveguide / RingResonator / DirectionalCoupler 默认参数全链路 PASS（回归）
  4. CLI 入口 --target_neff 可用
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.design_pipeline import run_pipeline  # noqa: E402


def check(cond: bool, msg: str, report: dict, key: str) -> bool:
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {msg}")
    report["checks"].append({"key": key, "ok": bool(cond), "msg": msg})
    return bool(cond)


def main() -> int:
    report: dict = {"d25": "pipeline multi-device", "checks": []}
    ok = True

    # 1) Waveguide 逆设计（D-25 新）
    r = run_pipeline("Waveguide", target_neff=3.2)
    ok &= check(r["accepted"], f"Waveguide target_neff=3.2 PASS：{r['verdict'][:80]}",
                report, "wg_inverse")
    ok &= check(r["inverse_design"] is not None
                and abs(r["inverse_design"]["target_neff"] - 3.2) < 1e-9,
                f"逆设计记录：{r['inverse_design']}", report, "wg_inverse_rec")
    ok &= check(r["final_params"]["width"] > 0.35 and r["final_params"]["width"] < 0.75
                and r["sim"]["rel_err"] <= 0.02,
                f"width={r['final_params']['width']}µm（窗口内），"
                f"FDTD neff={r['sim']['neff_fdtd']:.4f} rel={r['sim']['rel_err']:.3%} ≤ 2%",
                report, "wg_accept")

    # 2) SymmetricYBranch（D-25 新：分束验收，GPU live / ORACLE 演示）
    ry = run_pipeline("SymmetricYBranch")
    mode = ry["sim"].get("mode")
    ok &= check(ry["accepted"] and ry["sim"]["passed"],
                f"SymmetricYBranch PASS（sim mode={mode}）：{ry['verdict'][:70]}",
                report, "yb_pipeline")
    if mode == "live_fdtd":
        ok &= check(ry["sim"]["balance_abs"] <= 0.10,
                    f"FDTD 分束 balance={ry['sim']['balance_abs']} ≤ 0.1", report, "yb_live")
    else:
        ok &= check(mode == "oracle_demo",
                    "无 GPU → 诚实 ORACLE 真值演示（对称性定理 50/50）", report, "yb_demo")

    # 3) 默认参数回归（Ring / DC / Waveguide）
    for kind in ("RingResonator", "DirectionalCoupler", "Waveguide"):
        rd = run_pipeline(kind)
        ok &= check(rd["accepted"],
                    f"{kind} 默认参数全链路 PASS（{len(rd['steps'])} 步）",
                    report, f"default_{kind}")
        ok &= check(len(rd["steps"]) >= 2 and "<svg" in rd["layout_svg"],
                    f"{kind} 步骤完整（{len(rd['steps'])} 步）+ SVG 版图",
                    report, f"steps_{kind}")

    # 4) CLI 入口存在性（argparse 定义）
    import subprocess
    cli = subprocess.run(
        [sys.executable, "-m", "lda_agent.design_pipeline", "Waveguide",
         "--target_neff", "3.2", "--help"],
        capture_output=True, text=True, cwd=_HERE)
    ok &= check(cli.returncode == 0 and "--target_neff" in cli.stdout,
                "CLI --target_neff 参数可用", report, "cli")

    out_path = os.path.join(_HERE, "reports", "pipeline_multidevice_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告：{out_path}")
    print("D-25 一键设计流水线多器件扩展 smoke:", "ALL GREEN" if ok else "HAS FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
