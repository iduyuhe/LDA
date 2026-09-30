"""P1.1 · L1 Agent 协议层开放标准零漂移 smoke（维护门禁，对标 L0 的 run_ir_spec_smoke.py）。

守护 docs/l1_protocol_spec.md（LDA-STD-002 v0.1）与 docs/l1_protocol_schema.json 的
「文档-代码零漂移」：代码（lda/lda_l1/protocol.py 的 KernelGateway + AgentRequest/
AgentResponse + tool_schemas）若漂移出契约，本 smoke 直接红。

判据（name-first，防假绿；含反向反例，防 D-145 重构死断言）：
  1) 契约文件可读且含 contract 块
  2) tool_schemas() 暴露的工具名 == 契约 tool_exposed 名集合（双向，无多无漏）
  3) 每个 tool 的 input_schema.required == 契约该 action 的 payload_required
  4) AgentRequest/AgentResponse 实例字段集合 == 契约声明字段集合（双向）
  5) 反例：未知 action → status=error（死标量抓出）
  6) 反例：非法 candidate.type（"foo"）→ verify_design 返回 error（死标量抓出）
  7) 正向：verify_design(reference) 仍 ok（确认没把正常路径搞坏，防假绿）

运行（venv，含内核依赖）：
  C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe run_l1_spec_smoke.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l1.protocol import AgentRequest, AgentResponse, KernelGateway

PASS = "PASS"
FAIL = "FAIL"
checks: list = []


def check(name: str, ok: bool, detail: str = ""):
    checks.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ·  {detail}" if detail else ""))


def _load_contract():
    here = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(here, "..", "docs", "l1_protocol_schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f), os.path.normpath(schema_path)


def main() -> int:
    contract, schema_path = _load_contract()
    c = contract.get("contract", {})

    # 1) 契约文件可读且含 contract 块
    check("契约文件 LDA-STD-002 可读且含 contract 块",
          bool(c) and "envelope" in c and "actions" in c,
          os.path.basename(schema_path))

    # 2) tool_schemas() 暴露的工具名 == 契约 tool_exposed 名集合（双向）
    gw = KernelGateway(out_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "reports_l1_spec"))
    code_tools = [t["name"].replace("lda.", "", 1) for t in gw.tool_schemas()]
    contract_exposed = [a["name"] for a in c.get("actions", []) if a.get("tool_exposed")]
    set_code, set_contract = set(code_tools), set(contract_exposed)
    missing_in_code = set_contract - set_code      # 契约声明但代码未暴露
    extra_in_code = set_code - set_contract         # 代码暴露但契约未声明
    check("tool_schemas 工具集 == 契约 tool_exposed 集合（双向无漂移）",
          missing_in_code == set() and extra_in_code == set(),
          f"code={sorted(code_tools)}; 缺={sorted(missing_in_code)} 多={sorted(extra_in_code)}")

    # 3) 每个 tool 的 input_schema.required == 契约 payload_required
    req_by_tool = {t["name"].replace("lda.", "", 1): set(t.get("input_schema", {}).get("required", []))
                   for t in gw.tool_schemas()}
    req_by_contract = {a["name"]: set(a.get("payload_required", []))
                       for a in c.get("actions", []) if a.get("tool_exposed")}
    req_drift = {name: (sorted(req_by_contract[name] - req_by_tool.get(name, set())),
                        sorted(req_by_tool.get(name, set()) - req_by_contract.get(name, set())))
                 for name in req_by_contract
                 if req_by_contract[name] != req_by_tool.get(name, set())}
    check("各 tool input_schema.required == 契约 payload_required",
          req_drift == {},
          f"drift={req_drift}" if req_drift else "全部一致")

    # 4) AgentRequest/AgentResponse 实例字段 == 契约声明字段（双向）
    env = c.get("envelope", {})
    req_fields = set(env.get("AgentRequest", {}).get("fields", []))
    resp_fields = set(env.get("AgentResponse", {}).get("fields", []))
    inst_req = set(AgentRequest(action="x", payload={}).to_dict().keys())
    inst_resp = set(AgentResponse(request_id="r", status="ok").to_dict().keys())
    check("AgentRequest 字段 == 契约声明（双向）",
          inst_req == req_fields,
          f"inst={sorted(inst_req)} contract={sorted(req_fields)}")
    check("AgentResponse 字段 == 契约声明（双向）",
          inst_resp == resp_fields,
          f"inst={sorted(inst_resp)} contract={sorted(resp_fields)}")

    def run(action, payload):
        return gw.handle(AgentRequest(action=action, payload=payload,
                                      meta={"requester": "l1-spec-smoke"}))

    # 5) 反例：未知 action → status=error（死标量抓出）
    r = run("no_such_action_xyz", {})
    check("反例-未知 action → status=error",
          r.status == "error" and r.error is not None,
          f"status={r.status}")

    # 6) 反例：非法 candidate.type → verify_design 返回 error（死标量抓出）
    r = run("verify_design", {"candidate": {"type": "foo"}})
    check("反例-非法 candidate.type → status=error",
          r.status == "error",
          f"status={r.status}")

    # 7) 正向：verify_design(reference, B1/B2/B4) 仍 ok（防重构把正常路径弄坏，防假绿）
    r = run("verify_design", {"candidate": {"type": "reference"},
                              "benchmarks": ["B1", "B2", "B4"]})
    s = r.result.get("summary", {})
    check("正向-verify_design(reference, B1/B2/B4) 仍 ok（防假绿）",
          r.status == "ok" and s.get("passed") == s.get("total") == 3,
          f"{s.get('passed')}/{s.get('total')} PASS")

    # 汇总
    npass = sum(1 for _, ok, _ in checks if ok)
    print(f"\nL1 Agent 协议层零漂移 smoke：{npass}/{len(checks)} PASS")
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
