"""D-105 · L1 agent 协议层全链路 smoke（维护门禁，覆盖 run_agent.py 的 KernelGateway 路径）。

此前 L1 协议层仅有 run_mcp_smoke.py 覆盖 MCP 工具路径（verify_design/list_benchmarks）；
run_agent.py 的 CLI 演示路径（KernelGateway 直接调用 + L0 IR 驱动 + 三种 candidate +
benchmarks 过滤）无 smoke 覆盖。本 smoke 以库方式走同一 KernelGateway 全链路：

  1) reference 候选 → 46/46 PASS（B1-B27 物理定律 + E1-E7 实证锚 + S1-S12 系统锚，D-104 注入实证锚后；
     B19 为 P1-M4 新增链路级无源无增益物理定律锚；B20-B27 为 v0.8 内核纵深新增；
     E4-E7 为 v0.8.11 实证语料扩充：crossing IL/XT + MMI EL + SiN 传播损耗；
     S9 为 v0.8.24 LVS 签核锚）；
  2) perturbed(rel=0.10) 候选 → 抓 FAIL（passed < total，死标量）；
  3) l3_ai 候选 → 法官抓 FAIL（passed < total，流程成功）；
  4) list_benchmarks → 46 题；
  5) benchmarks 过滤（B1,B2,B4）→ 3/3；
  6) L0 IR 驱动（examples/l0_demo_ring.json）→ 流程成功（IR 携带设计参数覆盖默认）。

全程确定性：LLM 不进判决路径（l3_ai 仅为候选生成器，判决=死标量比对）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l1.protocol import AgentRequest, KernelGateway

PASS = "PASS"
FAIL = "FAIL"
checks: list = []


def check(name: str, ok: bool, detail: str = ""):
    checks.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ·  {detail}" if detail else ""))


def main() -> int:
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports_l1")
    gw = KernelGateway(out_dir=out_dir)

    def run(action, payload):
        return gw.handle(AgentRequest(action=action, payload=payload,
                                      meta={"requester": "smoke"}))

    # 1) reference → 46/46（物理定律 + 实证锚双 ground；B1-B27 + E1-E7 + S1-S12）
    r = run("verify_design", {"candidate": {"type": "reference"}})
    s = r.result["summary"]
    check("verify_design(reference) 46/46",
          r.status == "ok" and s.get("passed") == s.get("total") == 46,
          f"{s.get('passed')}/{s.get('total')} PASS")

    # 2) perturbed(rel=0.10) → 抓 FAIL（死标量）
    r = run("verify_design", {"candidate": {"type": "perturbed", "rel_err": 0.10}})
    s = r.result["summary"]
    check("verify_design(perturbed) 抓 FAIL",
          r.status == "fail" and s.get("passed", 99) < s.get("total", 0),
          f"{s.get('passed')}/{s.get('total')} (扰动被试出)")

    # 3) l3_ai → 法官抓 FAIL（流程成功，仅判决 fail）
    r = run("verify_design", {"candidate": {"type": "l3_ai"}})
    s = r.result["summary"]
    check("verify_design(l3_ai) 法官抓 FAIL",
          r.status == "fail" and s.get("passed", 99) < s.get("total", 0),
          f"{s.get('passed')}/{s.get('total')} (LLM 候选被死标量驳回)")

    # 4) list_benchmarks → 46 题（B27 + E7 + S12）
    r = run("list_benchmarks", {})
    bm = r.result.get("benchmarks", [])
    ids = [b.get("id") for b in bm] if bm else []
    check("list_benchmarks 46 题",
          len(ids) == 46 and "B27" in ids and "E7" in ids and "S11" in ids and "S12" in ids,
          f"{len(ids)} 题（B1-B27 + E1-E7 + S1-S12）")

    # 5) benchmarks 过滤（B1,B2,B4）→ 3/3
    r = run("verify_design", {"candidate": {"type": "reference"},
                              "benchmarks": ["B1", "B2", "B4"]})
    s = r.result["summary"]
    check("verify_design(过滤 B1,B2,B4) 3/3",
          r.status == "ok" and s.get("passed") == s.get("total") == 3,
          f"{s.get('passed')}/{s.get('total')} PASS")

    # 6) L0 IR 驱动（examples/l0_demo_ring.json）→ 流程成功
    l0_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "examples", "l0_demo_ring.json")
    if os.path.exists(l0_path):
        with open(l0_path, "r", encoding="utf-8") as f:
            l0_ir = json.load(f)
        r = run("verify_design", {"candidate": {"type": "reference"},
                                  "l0_ir": l0_ir})
        s = r.result["summary"]
        check("verify_design(L0 IR 驱动) 流程成功",
              r.status == "ok" and s.get("passed") == s.get("total"),
              f"{s.get('passed')}/{s.get('total')} PASS（L0 参数覆盖默认）")
    else:
        check("verify_design(L0 IR 驱动) 流程成功", False, f"缺失 {l0_path}")

    # 汇总
    npass = sum(1 for _, ok, _ in checks if ok)
    print(f"\nL1 agent 协议层全链路 smoke：{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
