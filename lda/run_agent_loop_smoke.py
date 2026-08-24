"""D-106 · agent 自迭代设计闭环 smoke（维护门禁，覆盖 DesignAgent「AI for AI」最小实证）。

此前 run_agent_loop.py（agent 自迭代闭环演示）import 断链不可运行（引用了
design_loop.py 中从未存在的 ring_fsr_problem 函数），且非 _smoke.py 命名不被
CI 捕获——维护深审发现的真实断链。D-106 修复 run_agent_loop.py 并补本门禁：

  1) DesignAgent 收敛闭环（bragg_mirror，truth 真求解器）：accepted=True、
     有限迭代、final_metric_err ≤ tolerance_rel（死标量）；
  2) 双判据全绿：verdict 含「对物理定律锚（TMM ORACLE）在公差内」（双重验证语义）；
  3) 报告可序列化（JSON 落盘 + 关键字段存在）。

全程确定性：LLM 不进判决路径（FDTD 真内核 vs TMM 物理定律锚死标量比对）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_agent.design_loop import DesignAgent, main as design_main

PASS = "PASS"
FAIL = "FAIL"
checks: list = []


def check(name: str, ok: bool, detail: str = ""):
    checks.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ·  {detail}" if detail else ""))


def main() -> int:
    # 1) 收敛闭环：accepted=True + 有限迭代 + 误差在公差内
    rep = design_main()
    d = rep.to_dict()
    check("agent 闭环收敛 accepted",
          d.get("accepted") is True and 0 < d.get("iterations", 0) <= 12,
          f"iterations={d.get('iterations')}")

    err = d.get("final_metric_err")
    check("误差在公差内（死标量）",
          err is not None and err <= 0.02,
          f"|ΔR|={err:.4g} ≤ tol 2%")

    # 2) 双判据全绿：对 TMM 物理定律锚在公差内
    verdict = d.get("verdict", "")
    check("双判据（FDTD + 物理定律锚）全绿",
          "在公差内" in verdict and ("达标" in verdict or "验收" in verdict),
          verdict[:50] + "...")

    # 3) 报告可序列化 + 关键字段
    keys = set(d.keys())
    need = {"accepted", "iterations", "final_metric", "final_oracle_metric",
            "final_metric_err", "verdict", "loop_trace"}
    check("报告字段完整", need <= keys, f"{len(keys)} 字段")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports_agent")
    os.makedirs(out, exist_ok=True)
    jp = os.path.join(out, "agent_loop_report.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    check("报告 JSON 落盘", os.path.exists(jp) and os.path.getsize(jp) > 0,
          os.path.basename(jp))

    npass = sum(1 for _, ok, _ in checks if ok)
    print(f"\nagent 自迭代设计闭环 smoke：{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
