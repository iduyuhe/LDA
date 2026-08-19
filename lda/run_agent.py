"""LDA L1 · agent 协议层 CLI 演示。

演示：一个 agent 通过 L1 协议（KernelGateway）发出 verify_design 请求，协议层把
请求翻译为「L0 IR → L3 candidate → harness → AgentResponse」的确定性调用链。
这就是《白皮书》§12 说的「人操作壳 → agent 操作接口」翻译层的最小可跑实证。

用法：
  python run_agent.py --candidate reference
  python run_agent.py --candidate l3_ai --l0 examples/l0_demo_ring.json
  python run_agent.py --candidate perturbed --rel 0.10
  python run_agent.py --action list_benchmarks
  python run_agent.py --candidate reference --benchmarks B1,B2,B4
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l1.protocol import AgentRequest, KernelGateway


def main():
    ap = argparse.ArgumentParser(description="LDA L1 agent 协议层演示")
    ap.add_argument("--action", default="verify_design",
                    choices=["verify_design", "run_candidate", "list_benchmarks"])
    ap.add_argument("--l0", default=None, help="L0 IR JSON 路径")
    ap.add_argument("--candidate", default="reference",
                    choices=["reference", "perturbed", "l3_ai"])
    ap.add_argument("--rel", type=float, default=0.0, help="perturbed 相对扰动")
    ap.add_argument("--benchmarks", default=None, help="逗号分隔，如 B1,B2")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "reports_l1"))
    args = ap.parse_args()

    l0_ir = None
    if args.l0:
        with open(args.l0, "r", encoding="utf-8") as f:
            l0_ir = json.load(f)

    payload = {"candidate": {"type": args.candidate, "rel_err": args.rel}}
    if l0_ir is not None:
        payload["l0_ir"] = l0_ir
    if args.benchmarks:
        payload["benchmarks"] = [b.strip() for b in args.benchmarks.split(",")]

    gw = KernelGateway(out_dir=args.out)
    req = AgentRequest(action=args.action, payload=payload,
                       meta={"requester": "demo-agent"})
    resp = gw.handle(req)
    print(resp.to_json())


if __name__ == "__main__":
    main()
