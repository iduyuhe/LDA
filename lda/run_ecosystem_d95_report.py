"""D-95 生态共建 · 社区评审流 + 提案落地 —— 报告生成（临时库，不污染真实贡献库）。

产出 lda/reports/ecosystem_d95.json：提案生命周期（提交→评审→落地）、
确定性自测门禁、live 回归接入、补丁生成、启动恢复、审计轨迹、验收结论。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal
from lda_pdk.review import (review_proposal, land_proposal, reload_landed,
                            get_audit, list_proposals)
from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.golden import _GOLDEN_DISPATCH, _PHYSICAL_LAW, golden_with_source

TMP = tempfile.mkdtemp(prefix="lda_d95r_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports",
                   "ecosystem_d95.json")

ORACLE_B19 = (
    "def b19_micro_ring_fsr(L_um, n_g):\n"
    "    c_um_s = 2.99792458e14\n"
    "    return c_um_s / (n_g * L_um) / 1e9\n"
)

for _bid in ("B19", "B20"):
    _GOLDEN_DISPATCH.pop(_bid, None)
    _PHYSICAL_LAW.discard(_bid)
    BENCHMARK_DEFS.pop(_bid, None)

# ---- 流程执行 ----
s_submit = submit_benchmark_proposal({
    "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
    "proposed_by": "community",
}, contrib_path=CP)

s_norev = review_proposal("B19", "approve", "", "无评审人", ORACLE_B19,
                          contrib_path=CP)
s_badoracle = review_proposal("B19", "approve", "评审员甲", "公式实现",
                              "def b19_micro_ring_fsr(L_um, n_g):\n    return 'x'",
                              contrib_path=CP)
s_approve = review_proposal("B19", "approve", "杜玉河",
                            "FSR=c/(n_g·L) 为确定性物理定律，公式与实现一致",
                            ORACLE_B19, contrib_path=CP)
s_land = land_proposal("B19", contrib_path=CP, landed_path=LP)
s_landed_review = review_proposal("B19", "reject", "评审员丙", "已落地",
                                  contrib_path=CP)

# live 回归核对
in_defs = "B19" in BENCHMARK_DEFS
in_dispatch = "B19" in _GOLDEN_DISPATCH
in_phys = "B19" in _PHYSICAL_LAW
g_src, g_kind, _ = golden_with_source("B19", {"L_um": 100.0, "n_g": 4.0})

# 启动恢复核对
_GOLDEN_DISPATCH.pop("B19", None)
_PHYSICAL_LAW.discard("B19")
BENCHMARK_DEFS.pop("B19", None)
n_reload, bids_reload = reload_landed(LP)
reloaded_ok = "B19" in BENCHMARK_DEFS and "B19" in _GOLDEN_DISPATCH

aud = get_audit("B19", contrib_path=CP)
props = list_proposals(contrib_path=CP)
b19 = next((x for x in props if x["id"] == "B19"), {})
patch = s_land.get("patch", "")

acceptance = [
    {"name": "提案提交 → accepted_pending（仅登记不注入）",
     "ok": s_submit.get("status") == "accepted_pending", "detail": str(s_submit)},
    {"name": "缺评审人 → 拒绝（LLM 不进判决路径）",
     "ok": s_norev.get("status") == "error", "detail": s_norev.get("reason", "")[:60]},
    {"name": "非法 ORACLE → 前置自测拒绝（死标量门禁）",
     "ok": s_badoracle.get("status") == "error", "detail": s_badoracle.get("reason", "")[:60]},
    {"name": "有效 approve → approved",
     "ok": s_approve.get("status") == "approved", "detail": str(s_approve)},
    {"name": "落地 → landed + 物理值正确",
     "ok": s_land.get("status") == "landed"
           and abs(s_land.get("value", 0.0) - 749.481145) < 1e-3,
     "detail": f"value={s_land.get('value')}"},
    {"name": "live 回归接入（BENCHMARK_DEFS + dispatch + physical_law）",
     "ok": in_defs and in_dispatch and in_phys,
     "detail": f"defs={in_defs} dispatch={in_dispatch} physical_law={in_phys}"},
    {"name": "golden_with_source 判为 physical-law",
     "ok": g_kind == "physical-law" and abs(g_src - 749.481145) < 1e-3,
     "detail": f"{g_kind} value={g_src:.4f}"},
    {"name": "landed 后不可再评审（状态机锁定）",
     "ok": s_landed_review.get("status") == "error", "detail": str(s_landed_review)},
    {"name": "reload_landed 启动恢复",
     "ok": n_reload == 1 and bids_reload == ["B19"] and reloaded_ok,
     "detail": f"n={n_reload} bids={bids_reload}"},
    {"name": "审计轨迹（review[approve] → land）",
     "ok": [a["op"] for a in aud] == ["review", "land"]
           and aud[0].get("decision") == "approve", "detail": str(aud)},
]

report = {
    "d": "D-95",
    "title": "生态共建 · 社区评审流 + 提案→golden 落地",
    "flow": {
        "submit": s_submit,
        "review_without_reviewer": s_norev,
        "review_bad_oracle": s_badoracle,
        "review_approve": s_approve,
        "land": {k: v for k, v in s_land.items() if k != "patch"},
        "review_after_landed": s_landed_review,
    },
    "live_regression": {
        "B19_in_BENCHMARK_DEFS": in_defs,
        "B19_in_dispatch": in_dispatch,
        "B19_in_physical_law": in_phys,
        "golden_with_source": {"kind": g_kind, "value": g_src},
    },
    "reload": {"count": n_reload, "bids": bids_reload, "re_registered": reloaded_ok},
    "audit": aud,
    "proposal_final": {k: v for k, v in b19.items() if k != "oracle_fn_source"},
    "patch_generated": bool(patch),
    "patch_head": "\n".join(patch.splitlines()[:6]),
    "honest_boundary": "LLM 不进判决路径：评审=具名人工（缺评审人即拒），自测=死标量门禁（非法 ORACLE 即拒）；落地仅登记确定性物理定律并实时接入统一回归；落库(live)≠进版本控制，权威 ORACLE 以维护者 git 提交（开放评审流）为准。",
    "acceptance": {"passed": all(c["ok"] for c in acceptance),
                   "checks": acceptance},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("=" * 58)
print("D-95 生态共建 · 社区评审流 + 提案落地 报告")
print("=" * 58)
for c in acceptance:
    print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']:<38} {c['detail']}")
print("-" * 58)
ap = report["acceptance"]
print(f"ACCEPTANCE: {len([c for c in ap['checks'] if c['ok']])}/{len(ap['checks'])} PASS")
print("written:", OUT)
sys.exit(0 if ap["passed"] else 1)
