"""D-96 生态共建 · 评审门槛扩展 + 评审流 UI 支撑 —— smoke 测试（临时库）。

覆盖：签名完备性 / 数值界限 / core 双评审 quorum（含同评审人去重）/
提交期防重（landed 公式与 fn 双通道）/ 被拒重提（保留审计）/ review_stats。
验收红线不变：LLM 不进判决路径，全部门槛为确定性门禁。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal
from lda_pdk.review import (review_proposal, land_proposal, resubmit_proposal,
                            review_stats, get_audit)

TMP = tempfile.mkdtemp(prefix="lda_d96s_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")

SRC_FSR = (
    "def b19_micro_ring_fsr(L_um, n_g):\n"
    "    c_um_s = 2.99792458e14\n"
    "    return c_um_s / (n_g * L_um) / 1e9\n"
)

ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append((name, cond, detail))


# 1) core + 值界 提案提交
r = submit_benchmark_proposal({
    "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
    "core": True, "value_min": 500.0, "value_max": 1000.0,
}, contrib_path=CP)
check("core+值界 提案提交", r["status"] == "accepted_pending", str(r))

# 2) core quorum：第 1 票 → pending 1/2
r = review_proposal("B19", "approve", "评审人甲", "1/2", SRC_FSR, contrib_path=CP)
check("core 第1票 → pending votes 1/2", r["status"] == "pending"
      and r.get("votes") == "1/2", str(r))

# 3) 同评审人重复投票不推进 quorum
r = review_proposal("B19", "approve", "评审人甲", "重复票", SRC_FSR, contrib_path=CP)
check("同评审人重复票不推进(仍 1/2)", r["status"] == "pending"
      and r.get("votes") == "1/2", str(r))

# 4) 第 2 位评审人 → approved
r = review_proposal("B19", "approve", "评审人乙", "2/2", SRC_FSR, contrib_path=CP)
check("core 第2票 → approved", r["status"] == "approved", str(r))

# 5) 数值界限门槛：value_max 过小 → 拒
r = submit_benchmark_proposal({
    "id": "B20", "title": "微环FSR2", "metric": "FSR_GHz",
    "formula": "FSR2 = c/(n_g·L)", "oracle_fn_name": "b20_fsr2",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
    "value_min": 100.0, "value_max": 200.0,
}, contrib_path=CP)
r = review_proposal("B20", "approve", "杜玉河", "界",
                    SRC_FSR.replace("b19_micro_ring_fsr", "b20_fsr2"),
                    contrib_path=CP)
check("数值界限门槛(749>max200) → 拒", r["status"] == "error"
      and "数值界限" in r.get("reason", ""), r.get("reason", "")[:60])

# 6) 签名完备性门槛：ORACLE 缺必填参数 → 拒
r = submit_benchmark_proposal({
    "id": "B21", "title": "缺参题", "metric": "M",
    "formula": "M = n_g * L", "oracle_fn_name": "b21_missing",
    "tol": 0.1, "default_params": {"L_um": 100.0},   # 缺 n_g
}, contrib_path=CP)
r = review_proposal("B21", "approve", "杜玉河", "x",
                    "def b21_missing(L_um, n_g):\n    return n_g * L_um",
                    contrib_path=CP)
check("签名完备性门槛(缺 n_g) → 拒", r["status"] == "error", r.get("reason", "")[:60])

# 7) 落地 B19（双票已过）
r = land_proposal("B19", contrib_path=CP, landed_path=LP)
check("落地 B19 → landed", r["status"] == "landed", str(r.get("value")))

# 8) 提交期防重：同公式（含 landed）→ 拒；同 fn 名 → 拒
r = submit_benchmark_proposal({
    "id": "B22", "title": "重复公式", "metric": "X",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b22_dup",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
}, contrib_path=CP)
check("防重：landed 同公式 → 拒", r["status"] == "rejected"
      and "防重" in r.get("reason", ""), r.get("reason", "")[:50])
r = submit_benchmark_proposal({
    "id": "B23", "title": "重复fn", "metric": "Y",
    "formula": "Y = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
}, contrib_path=CP)
check("防重：landed 同 fn → 拒", r["status"] == "rejected"
      and "防重" in r.get("reason", ""), r.get("reason", "")[:50])

# 9) 被拒重提：B20 reject → resubmit → pending（审计保留）
r = review_proposal("B20", "reject", "评审员丁", "界限不符", contrib_path=CP)
check("B20 reject → rejected", r["status"] == "rejected", str(r))
aud_before = len(get_audit("B20", contrib_path=CP))
r = resubmit_proposal("B20", {"by": "community"}, contrib_path=CP)
aud_after = len(get_audit("B20", contrib_path=CP))
check("resubmit → pending", r["status"] == "pending", str(r))
check("resubmit 保留审计并追加", aud_after == aud_before + 1
      and get_audit("B20", contrib_path=CP)[-1]["op"] == "resubmit",
      f"{aud_before}→{aud_after}")

# 10) review_stats 自洽（B19 landed / B20 resubmitted pending / B21 pending = 3 提案）
s = review_stats(contrib_path=CP)
check("review_stats 自洽", s["total"] == 3
      and s["by_status"]["landed"] == 1 and s["by_status"]["pending"] == 2
      and s["approvals"] >= 1 and s["quorum_votes"] == 2,
      str(s))

print("=" * 58)
print("D-96 评审门槛扩展 + 评审流 UI 支撑 smoke")
print("=" * 58)
for name, cond, detail in ok:
    print(f"[PASS] {name:<36} {detail}")
for name, cond, detail in fail:
    print(f"[FAIL] {name:<36} {detail}")
print("-" * 58)
print(f"PASS={len(ok)} FAIL={len(fail)}")
print("全部通过 ✅" if not fail else "存在失败 ❌")
sys.exit(1 if fail else 0)
