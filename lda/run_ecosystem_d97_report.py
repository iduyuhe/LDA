"""D-97 生态共建 · 评审门槛再扩展（ReviewPolicy）+ 多提案批量评审 —— 报告生成。

产出 lda/reports/ecosystem_d97.json：策略预检 / 白名单 / 最短源码 / 严格防重 /
批量评审 / 批量落地 / policy_info。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal, policy_info
from lda_pdk.review import (review_proposal, review_proposals_batch,
                            land_proposals_batch)

TMP = tempfile.mkdtemp(prefix="lda_d97r_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports",
                   "ecosystem_d97.json")


def sub(payload, overrides=None):
    return submit_benchmark_proposal(payload, contrib_path=CP,
                                     policy_override=overrides)


# ---- 策略预检 ----
r_tol = sub({"id": "B90", "title": "t", "metric": "M", "formula": "M=n*L",
             "oracle_fn_name": "b90", "tol": 0.0, "default_params": {"L": 1.0}})
r_params = sub({"id": "B91", "title": "t", "metric": "M", "formula": "M=n*L",
                "oracle_fn_name": "b91", "tol": 0.5})
r_bounds = sub({"id": "B92", "title": "t", "metric": "M", "formula": "M=n*L",
                "oracle_fn_name": "b92", "tol": 0.5, "default_params": {"L": 1.0},
                "value_min": 5.0, "value_max": 1.0})
r_envbounds = sub({"id": "B93", "title": "t", "metric": "M", "formula": "M=n*L",
                   "oracle_fn_name": "b93", "tol": 0.5, "default_params": {"L": 1.0}},
                  {"enforce_value_bounds": True})

# ---- 白名单 ----
sub({"id": "B94", "title": "t", "metric": "M", "formula": "M=n*L",
     "oracle_fn_name": "b94", "tol": 0.5, "default_params": {"L": 1.0}})
r_wl_reject = review_proposal("B94", "approve", "评审人甲", "x",
                              "def b94(L):\n    return L", contrib_path=CP,
                              policy_override={"authorized_reviewers": frozenset({"杜玉河"})})
r_wl_ok = review_proposal("B94", "approve", "杜玉河", "ok",
                          "def b94(L):\n    return L", contrib_path=CP,
                          policy_override={"authorized_reviewers": frozenset({"杜玉河"})})

# ---- 最短源码 ----
sub({"id": "B95", "title": "t", "metric": "M", "formula": "M5 = n*L",
     "oracle_fn_name": "b95", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
SRC95 = "def b95(L, n_g):\n    # 确定性物理定律：M = n_g * L（测试用）\n    return n_g * L\n"
r_short = review_proposal("B95", "approve", "杜玉河", "ok",
                          "def b95(L):\n    return L", contrib_path=CP,
                          policy_override={"min_source_length": 60})
r_long = review_proposal("B95", "approve", "杜玉河", "ok", SRC95, contrib_path=CP,
                         policy_override={"min_source_length": 40})

# ---- 严格防重 ----
sub({"id": "B96", "title": "t", "metric": "M", "formula": "M = c/(n_g·L)",
     "oracle_fn_name": "b96", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
r_strict = sub({"id": "B97", "title": "t2", "metric": "M",
                "formula": "M = c / (L * n_g)", "oracle_fn_name": "b97",
                "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}},
               {"strict_dedup": True})

# ---- 批量评审 ----
sub({"id": "B99", "title": "a", "metric": "M", "formula": "A = n*L",
     "oracle_fn_name": "b99", "tol": 0.5, "default_params": {"L": 1.0}})
sub({"id": "B100", "title": "b", "metric": "M", "formula": "B = n*L",
     "oracle_fn_name": "b100", "tol": 0.5, "default_params": {"L": 1.0}})
rb = review_proposals_batch([
    {"id": "B99", "decision": "reject", "reviewer": "杜玉河", "rationale": "与B3重复"},
    {"id": "B100", "decision": "reject", "reviewer": "杜玉河", "rationale": "与B4重复"},
], contrib_path=CP)

sub({"id": "B101", "title": "c", "metric": "M", "formula": "C = n_g*L",
     "oracle_fn_name": "b101", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
sub({"id": "B102", "title": "d", "metric": "M", "formula": "D = n_g*L",
     "oracle_fn_name": "b102", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
ra = review_proposals_batch([
    {"id": "B101", "decision": "approve", "reviewer": "杜玉河", "rationale": "ok",
     "oracle_fn_source": "def b101(L, n_g):\n    return n_g * L\n"},
    {"id": "B102", "decision": "approve", "reviewer": "杜玉河", "rationale": "ok",
     "oracle_fn_source": "def b102(L, n_g):\n    return n_g * L\n"},
], contrib_path=CP)

lb = land_proposals_batch(["B101", "B102"], contrib_path=CP, landed_path=LP)

pi = policy_info()

acceptance = [
    {"name": "策略预检：tol<=0 → 拒", "ok": r_tol["status"] == "rejected",
     "detail": r_tol.get("reason", "")[:40]},
    {"name": "策略预检：空 params → 拒", "ok": r_params["status"] == "rejected",
     "detail": r_params.get("reason", "")[:40]},
    {"name": "策略预检：value_min>max → 拒", "ok": r_bounds["status"] == "rejected",
     "detail": r_bounds.get("reason", "")[:40]},
    {"name": "策略：enforce_value_bounds 缺界 → 拒",
     "ok": r_envbounds["status"] == "rejected", "detail": r_envbounds.get("reason", "")[:45]},
    {"name": "策略：白名单外评审人 → 拒 / 白名单内 → approved",
     "ok": r_wl_reject["status"] == "error" and r_wl_ok["status"] == "approved",
     "detail": f"reject={r_wl_reject['status']} ok={r_wl_ok['status']}"},
    {"name": "策略：源码过短 → 拒 / 足长 → approved",
     "ok": r_short["status"] == "error" and r_long["status"] == "approved",
     "detail": f"short={r_short['status']} long={r_long['status']}"},
    {"name": "严格防重：token 级公式重复 → 拒",
     "ok": r_strict["status"] == "rejected" and "token" in r_strict.get("reason", ""),
     "detail": r_strict.get("reason", "")[:45]},
    {"name": "批量拒绝 2/2",
     "ok": rb["summary"]["ok"] == 2 and [x["status"] for x in rb["results"]] == ["rejected", "rejected"],
     "detail": str(rb["summary"])},
    {"name": "批量批准 2/2 → 批量落地 2/2（自动纳入回归）",
     "ok": ra["summary"]["ok"] == 2 and lb["summary"]["landed"] == 2
           and all(r.get("value") == 4.0 for r in lb["results"]),
     "detail": f"approve={str(ra['summary'])} land={str(lb['summary'])}"},
    {"name": "policy_info 快照", "ok": pi["enforce_positive_tol"] is True
     and pi["min_quorum"] == 2, "detail": str(pi)},
]

report = {
    "d": "D-97",
    "title": "生态共建进一步 · 评审门槛再扩展（ReviewPolicy）+ 多提案批量评审",
    "policy": pi,
    "policy_checks": {
        "tol_nonpositive": r_tol, "empty_params": r_params,
        "bounds_inverted": r_bounds, "enforce_bounds_missing": r_envbounds,
        "whitelist_reject": r_wl_reject, "whitelist_ok": r_wl_ok,
        "source_short": r_short, "source_ok": r_long,
        "strict_dedup": r_strict,
    },
    "batch": {
        "review_reject": {"summary": rb["summary"], "results": rb["results"]},
        "review_approve": {"summary": ra["summary"], "results": ra["results"]},
        "land": {"summary": lb["summary"], "results": lb["results"]},
    },
    "honest_boundary": "全部门槛为确定性门禁（LLM 不进判决路径）：策略预检（tol>0/params 非空/值界一致/强制值界）、评审人白名单、ORACLE 最短源码、严格防重（token 集）、批量评审/批量落地逐条复用同一门禁；策略可经 env LDA_REVIEW_* 或显式 overrides 配置，默认保持 D-95/D-96 行为不变；真实晶圆厂 NDA-PDK 仍属发动期 D-62 暂缓；权威 ORACLE 以维护者 git 提交为准。",
    "acceptance": {"passed": all(c["ok"] for c in acceptance),
                   "checks": acceptance},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("=" * 58)
print("D-97 评审门槛再扩展（ReviewPolicy）+ 批量评审 报告")
print("=" * 58)
for c in acceptance:
    print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']:<44} {c['detail']}")
print("-" * 58)
ap = report["acceptance"]
print(f"ACCEPTANCE: {len([c for c in ap['checks'] if c['ok']])}/{len(ap['checks'])} PASS")
print("written:", OUT)
sys.exit(0 if ap["passed"] else 1)
