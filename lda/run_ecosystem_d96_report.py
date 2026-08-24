"""D-96 生态共建 · 评审门槛扩展 + 评审流 UI 支撑 —— 报告生成（临时库）。

产出 lda/reports/ecosystem_d96.json：门槛验收（签名完备性 / 数值界限 /
core 双评审 quorum / 提交期防重 / 被拒重提 / 评审统计）。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal
from lda_pdk.review import (review_proposal, land_proposal, resubmit_proposal,
                            review_stats, get_audit, list_proposals)

TMP = tempfile.mkdtemp(prefix="lda_d96r_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports",
                   "ecosystem_d96.json")

SRC_FSR = (
    "def b19_micro_ring_fsr(L_um, n_g):\n"
    "    c_um_s = 2.99792458e14\n"
    "    return c_um_s / (n_g * L_um) / 1e9\n"
)

# ---- 流程 ----
s_core = submit_benchmark_proposal({
    "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
    "core": True, "value_min": 500.0, "value_max": 1000.0,
}, contrib_path=CP)
v1 = review_proposal("B19", "approve", "评审人甲", "1/2", SRC_FSR, contrib_path=CP)
v1b = review_proposal("B19", "approve", "评审人甲", "重复票", SRC_FSR, contrib_path=CP)
v2 = review_proposal("B19", "approve", "评审人乙", "2/2", SRC_FSR, contrib_path=CP)
land = land_proposal("B19", contrib_path=CP, landed_path=LP)

s_bound = submit_benchmark_proposal({
    "id": "B20", "title": "微环FSR2", "metric": "FSR_GHz",
    "formula": "FSR2 = c/(n_g·L)", "oracle_fn_name": "b20_fsr2",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
    "value_min": 100.0, "value_max": 200.0,
}, contrib_path=CP)
r_bound = review_proposal("B20", "approve", "杜玉河", "界",
                          SRC_FSR.replace("b19_micro_ring_fsr", "b20_fsr2"),
                          contrib_path=CP)
r_rej = review_proposal("B20", "reject", "评审员丁", "界限不符", contrib_path=CP)
r_sub = resubmit_proposal("B20", {"by": "community"}, contrib_path=CP)

s_sig = submit_benchmark_proposal({
    "id": "B21", "title": "缺参题", "metric": "M",
    "formula": "M = n_g * L", "oracle_fn_name": "b21_missing",
    "tol": 0.1, "default_params": {"L_um": 100.0},
}, contrib_path=CP)
r_sig = review_proposal("B21", "approve", "杜玉河", "x",
                        "def b21_missing(L_um, n_g):\n    return n_g * L_um",
                        contrib_path=CP)

r_dup1 = submit_benchmark_proposal({
    "id": "B22", "title": "重复公式", "metric": "X",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b22_dup",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
}, contrib_path=CP)
r_dup2 = submit_benchmark_proposal({
    "id": "B23", "title": "重复fn", "metric": "Y",
    "formula": "Y = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
}, contrib_path=CP)

stats = review_stats(contrib_path=CP)
aud_b20 = get_audit("B20", contrib_path=CP)
props = list_proposals(contrib_path=CP)

acceptance = [
    {"name": "core 提案提交（带值界）→ accepted_pending",
     "ok": s_core.get("status") == "accepted_pending", "detail": str(s_core)},
    {"name": "core 双评审 quorum：第1票 pending 1/2",
     "ok": v1.get("status") == "pending" and v1.get("votes") == "1/2",
     "detail": f"votes={v1.get('votes')}"},
    {"name": "同评审人重复票不推进 quorum（仍 1/2）",
     "ok": v1b.get("status") == "pending" and v1b.get("votes") == "1/2",
     "detail": f"votes={v1b.get('votes')}"},
    {"name": "第2位评审人 → approved（quorum 达成）",
     "ok": v2.get("status") == "approved", "detail": f"reviewer={v2.get('reviewer')}"},
    {"name": "数值界限门槛（749 > value_max 200）→ 拒",
     "ok": r_bound.get("status") == "error" and "数值界限" in r_bound.get("reason", ""),
     "detail": r_bound.get("reason", "")[:60]},
    {"name": "签名完备性门槛（缺 n_g）→ 拒",
     "ok": r_sig.get("status") == "error", "detail": r_sig.get("reason", "")[:60]},
    {"name": "提交期防重：landed 同公式 → 拒",
     "ok": r_dup1.get("status") == "rejected" and "防重" in r_dup1.get("reason", ""),
     "detail": r_dup1.get("reason", "")[:50]},
    {"name": "提交期防重：landed 同 fn → 拒",
     "ok": r_dup2.get("status") == "rejected" and "防重" in r_dup2.get("reason", ""),
     "detail": r_dup2.get("reason", "")[:50]},
    {"name": "被拒重提：rejected → pending（审计保留+追加）",
     "ok": r_sub.get("status") == "pending"
           and aud_b20[-1].get("op") == "resubmit" and len(aud_b20) >= 2,
     "detail": f"audit_ops={[a['op'] for a in aud_b20]}"},
    {"name": "review_stats 自洽",
     "ok": stats["total"] == 3 and stats["by_status"]["landed"] == 1
           and stats["quorum_votes"] == 2 and stats["rejections"] == 1,
     "detail": str(stats)},
]

report = {
    "d": "D-96",
    "title": "生态共建进一步 · 评审流 UI 增强 + 评审门槛扩展",
    "thresholds": {
        "core_quorum": {"vote1": v1, "vote1_dup": v1b, "vote2": v2},
        "value_bounds": r_bound,
        "signature": r_sig,
        "dedup_formula": r_dup1,
        "dedup_fn": r_dup2,
        "resubmit": r_sub,
    },
    "landed": {"bid": land.get("id"), "value": land.get("value")},
    "review_stats": stats,
    "audit_b20": aud_b20,
    "proposals": [{"id": p["id"], "status": p["status"],
                   "core": p.get("core"), "votes": len(p.get("approvals", []))}
                  for p in props],
    "honest_boundary": "全部门槛为确定性门禁：签名完备性(inspect)/数值界限(死标量比对)/core 双评审 quorum（2 位不同具名评审人）/提交期防重（landed 权威公式与 fn 双通道）/被拒重提（rejected→pending 保留审计）；评审=具名人工，LLM 不进判决路径；真实晶圆厂 NDA-PDK 仍属发动期 D-62 暂缓。",
    "acceptance": {"passed": all(c["ok"] for c in acceptance),
                   "checks": acceptance},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("=" * 58)
print("D-96 评审门槛扩展 + 评审流 UI 支撑 报告")
print("=" * 58)
for c in acceptance:
    print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']:<38} {c['detail']}")
print("-" * 58)
ap = report["acceptance"]
print(f"ACCEPTANCE: {len([c for c in ap['checks'] if c['ok']])}/{len(ap['checks'])} PASS")
print("written:", OUT)
sys.exit(0 if ap["passed"] else 1)
