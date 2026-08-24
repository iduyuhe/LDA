"""D-97 生态共建 · 评审门槛再扩展（ReviewPolicy）+ 多提案批量评审 —— smoke 测试。

覆盖：策略预检（tol>0 / params 非空 / value_min>max / enforce_value_bounds）/
评审人白名单 / ORACLE 最短源码 / 严格防重（token 级）/ 批量评审 / 批量落地 /
policy_info。验收红线不变：全确定性门禁，LLM 不进判决路径。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal, policy_info
from lda_pdk.review import (review_proposal, review_proposals_batch,
                            land_proposals_batch)

TMP = tempfile.mkdtemp(prefix="lda_d97s_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")

ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append((name, cond, detail))


def sub(payload, overrides=None):
    return submit_benchmark_proposal(payload, contrib_path=CP,
                                     policy_override=overrides)


# 1) 默认策略预检（提交期）
r = sub({"id": "B90", "title": "t", "metric": "M", "formula": "M=n*L",
         "oracle_fn_name": "b90", "tol": 0.0, "default_params": {"L": 1.0}})
check("策略预检：tol<=0 → 拒", r["status"] == "rejected"
      and "tol" in r.get("reason", ""), r.get("reason", "")[:40])
r = sub({"id": "B91", "title": "t", "metric": "M", "formula": "M=n*L",
         "oracle_fn_name": "b91", "tol": 0.5})
check("策略预检：空 params → 拒", r["status"] == "rejected"
      and "params" in r.get("reason", ""), r.get("reason", "")[:40])
r = sub({"id": "B92", "title": "t", "metric": "M", "formula": "M=n*L",
         "oracle_fn_name": "b92", "tol": 0.5, "default_params": {"L": 1.0},
         "value_min": 5.0, "value_max": 1.0})
check("策略预检：value_min>max → 拒", r["status"] == "rejected"
      and "value_min" in r.get("reason", ""), r.get("reason", "")[:40])

# 2) enforce_value_bounds（策略覆盖）
r = sub({"id": "B93", "title": "t", "metric": "M", "formula": "M=n*L",
         "oracle_fn_name": "b93", "tol": 0.5, "default_params": {"L": 1.0}},
        {"enforce_value_bounds": True})
check("策略：enforce_value_bounds 缺界 → 拒", r["status"] == "rejected"
      and "值界" in r.get("reason", ""), r.get("reason", "")[:45])

# 3) 评审人白名单
sub({"id": "B94", "title": "t", "metric": "M", "formula": "M=n*L",
     "oracle_fn_name": "b94", "tol": 0.5, "default_params": {"L": 1.0}})
r = review_proposal("B94", "approve", "评审人甲", "x", "def b94(L):\n    return L",
                    contrib_path=CP,
                    policy_override={"authorized_reviewers": frozenset({"杜玉河"})})
check("策略：白名单外评审人 → 拒", r["status"] == "error"
      and "白名单" in r.get("reason", ""), r.get("reason", "")[:45])
r = review_proposal("B94", "approve", "杜玉河", "ok", "def b94(L):\n    return L",
                    contrib_path=CP,
                    policy_override={"authorized_reviewers": frozenset({"杜玉河"})})
check("策略：白名单内评审人 → approved", r["status"] == "approved", str(r))

# 4) ORACLE 最短源码
sub({"id": "B95", "title": "t", "metric": "M", "formula": "M5 = n*L",
     "oracle_fn_name": "b95", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
r = review_proposal("B95", "approve", "杜玉河", "ok", "def b95(L):\n    return L",
                    contrib_path=CP, policy_override={"min_source_length": 60})
check("策略：源码过短 → 拒", r["status"] == "error"
      and "过短" in r.get("reason", ""), r.get("reason", "")[:45])
SRC95 = "def b95(L, n_g):\n    # 确定性物理定律：M = n_g * L（测试用）\n    return n_g * L\n"
r = review_proposal("B95", "approve", "杜玉河", "ok", SRC95,
                    contrib_path=CP, policy_override={"min_source_length": 40})
check("策略：源码足长 → approved", r["status"] == "approved", str(r))

# 5) 严格防重（token 级）
sub({"id": "B96", "title": "t", "metric": "M", "formula": "M = c/(n_g·L)",
     "oracle_fn_name": "b96", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
r = sub({"id": "B97", "title": "t2", "metric": "M", "formula": "M = c / (L * n_g)",
         "oracle_fn_name": "b97", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}},
        {"strict_dedup": True})
check("严格防重：token 级公式重复 → 拒", r["status"] == "rejected"
      and "token" in r.get("reason", ""), r.get("reason", "")[:45])
r = sub({"id": "B98", "title": "t3", "metric": "M", "formula": "M = c / (n_g * L)",
         "oracle_fn_name": "b98", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
check("非严格模式：同义公式（含空格差异）→ 接受", r["status"] == "accepted_pending", str(r))

# 6) 批量评审（拒绝 2 + 批准 2）
p1 = sub({"id": "B99", "title": "a", "metric": "M", "formula": "A = n*L",
          "oracle_fn_name": "b99", "tol": 0.5, "default_params": {"L": 1.0}})
p2 = sub({"id": "B100", "title": "b", "metric": "M", "formula": "B = n*L",
          "oracle_fn_name": "b100", "tol": 0.5, "default_params": {"L": 1.0}})
rb = review_proposals_batch([
    {"id": "B99", "decision": "reject", "reviewer": "杜玉河", "rationale": "与B3重复"},
    {"id": "B100", "decision": "reject", "reviewer": "杜玉河", "rationale": "与B4重复"},
], contrib_path=CP)
check("批量拒绝 2/2", rb["summary"]["ok"] == 2
      and [x["status"] for x in rb["results"]] == ["rejected", "rejected"],
      str(rb["summary"]))

p3 = sub({"id": "B101", "title": "c", "metric": "M", "formula": "C = n_g*L",
          "oracle_fn_name": "b101", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
p4 = sub({"id": "B102", "title": "d", "metric": "M", "formula": "D = n_g*L",
          "oracle_fn_name": "b102", "tol": 0.5, "default_params": {"L": 1.0, "n_g": 4.0}})
ra = review_proposals_batch([
    {"id": "B101", "decision": "approve", "reviewer": "杜玉河", "rationale": "ok",
     "oracle_fn_source": "def b101(L, n_g):\n    return n_g * L\n"},
    {"id": "B102", "decision": "approve", "reviewer": "杜玉河", "rationale": "ok",
     "oracle_fn_source": "def b102(L, n_g):\n    return n_g * L\n"},
], contrib_path=CP)
check("批量批准 2/2", ra["summary"]["ok"] == 2
      and [x["status"] for x in ra["results"]] == ["approved", "approved"],
      str(ra["summary"]))

# 7) 批量落地（仅 approved）
lb = land_proposals_batch(["B101", "B102"], contrib_path=CP, landed_path=LP)
check("批量落地 2/2（自动纳入回归）", lb["summary"]["landed"] == 2
      and all(r.get("value") == 4.0 for r in lb["results"]),
      str(lb["summary"]))

# 8) policy_info
pi = policy_info()
check("policy_info 快照", pi["enforce_positive_tol"] is True
      and pi["min_quorum"] == 2 and pi["authorized_reviewers"] == [],
      str(pi))

print("=" * 58)
print("D-97 评审门槛再扩展（ReviewPolicy）+ 批量评审 smoke")
print("=" * 58)
for name, cond, detail in ok:
    print(f"[PASS] {name:<38} {detail}")
for name, cond, detail in fail:
    print(f"[FAIL] {name:<38} {detail}")
print("-" * 58)
print(f"PASS={len(ok)} FAIL={len(fail)}")
print("全部通过 ✅" if not fail else "存在失败 ❌")
sys.exit(1 if fail else 0)
