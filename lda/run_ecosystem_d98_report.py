"""D-98 生态共建 · 评审流端到端 · 发布 —— 报告生成（临时库/产物目录）。

产出 lda/reports/ecosystem_d98.json：完整链验收 / 发布门槛 / 补丁与 Release Notes /
状态 published / 审计 / list_published。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal
from lda_pdk.review import review_proposal, land_proposal, get_audit, review_stats
from lda_pdk.publish import publish_proposal, list_published

TMP = tempfile.mkdtemp(prefix="lda_d98r_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")
PD = os.path.join(TMP, "patches")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports",
                   "ecosystem_d98.json")

SRC = ("def b19_micro_ring_fsr(L_um, n_g):\n"
       "    c_um_s = 2.99792458e14\n"
       "    return c_um_s / (n_g * L_um) / 1e9\n")

# ---- 流程 ----
s0 = submit_benchmark_proposal({
    "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
}, contrib_path=CP)
s1 = review_proposal("B19", "approve", "杜玉河", "FSR=c/(n_g·L) 确定性物理定律",
                     SRC, contrib_path=CP)
s2 = land_proposal("B19", contrib_path=CP, landed_path=LP)

s_norev = publish_proposal("B19", "", contrib_path=CP, landed_path=LP,
                           patches_dir=PD)
submit_benchmark_proposal({
    "id": "B20", "title": "x", "metric": "M", "formula": "M=n*L",
    "oracle_fn_name": "b20", "tol": 0.5, "default_params": {"L": 1.0},
}, contrib_path=CP)
s_noland = publish_proposal("B20", "杜玉河", contrib_path=CP, landed_path=LP,
                            patches_dir=PD)
s_pub = publish_proposal("B19", "杜玉河", "社区贡献", contrib_path=CP,
                         landed_path=LP, patches_dir=PD)

patch = open(s_pub["patch_path"], encoding="utf-8").read()
rel = open(s_pub["release_path"], encoding="utf-8").read()
aud = get_audit("B19", contrib_path=CP)
stats = review_stats(contrib_path=CP)
pub = list_published(landed_path=LP)

acceptance = [
    {"name": "完整链 submit→approve→land",
     "ok": s0["status"] == "accepted_pending" and s1["status"] == "approved"
           and s2["status"] == "landed",
     "detail": f"{s0['status']}/{s1['status']}/{s2['status']}"},
    {"name": "发布须具名 author（缺即拒）",
     "ok": s_norev["status"] == "error" and "发布人" in s_norev.get("reason", ""),
     "detail": s_norev.get("reason", "")[:40]},
    {"name": "仅 landed 可发布（pending → 拒）",
     "ok": s_noland["status"] == "error" and "landed" in s_noland.get("reason", ""),
     "detail": s_noland.get("reason", "")[:45]},
    {"name": "发布 → published + 自测值物理正确",
     "ok": s_pub["status"] == "published" and s_pub.get("value") == 749.481145,
     "detail": f"value={s_pub.get('value')}"},
    {"name": "补丁 + Release Notes 落盘",
     "ok": bool(s_pub.get("patch_path")) and bool(s_pub.get("release_path"))
           and os.path.exists(s_pub["patch_path"]) and os.path.exists(s_pub["release_path"]),
     "detail": os.path.basename(s_pub.get("patch_path", ""))},
    {"name": "补丁含 golden.py + benchmarks.py 双段 unified diff",
     "ok": "a/golden.py" in patch and "a/benchmarks.py" in patch
           and "+++ b/golden.py" in patch and "@@" in patch,
     "detail": f"{len(patch.splitlines())} lines"},
    {"name": "补丁含注册行（dispatch/physical_law/BENCHMARK_DEFS）",
     "ok": '_GOLDEN_DISPATCH["B19"]' in patch and '_PHYSICAL_LAW.add("B19")' in patch
           and 'BENCHMARK_DEFS["B19"]' in patch, "detail": ""},
    {"name": "Release Notes 含标题/指标/ORACLE/评审人",
     "ok": "微环 FSR" in rel and "FSR_GHz" in rel and "b19_micro_ring_fsr" in rel
           and "杜玉河" in rel, "detail": ""},
    {"name": "状态 published + 审计 review→land→publish",
     "ok": [a["op"] for a in aud] == ["review", "land", "publish"],
     "detail": f"ops={[a['op'] for a in aud]}"},
    {"name": "list_published + review_stats 含 published",
     "ok": len(pub) == 1 and pub[0]["bid"] == "B19"
           and stats["by_status"].get("published") == 1,
     "detail": f"published={[x['bid'] for x in pub]}"},
]

report = {
    "d": "D-98",
    "title": "生态共建 · 评审流端到端 · 发布（Publish）",
    "flow": {"submit": s0, "review": s1, "land": s2,
             "publish_missing_author": s_norev,
             "publish_non_landed": s_noland,
             "publish": {k: v for k, v in s_pub.items()}},
    "patch": {"lines": len(patch.splitlines()),
              "head": "\n".join(patch.splitlines()[:5]),
              "has_golden_section": "a/golden.py" in patch,
              "has_benchmarks_section": "a/benchmarks.py" in patch},
    "release_notes": {"lines": len(rel.splitlines()),
                      "head": "\n".join(rel.splitlines()[:6])},
    "audit": aud,
    "review_stats": stats,
    "published": pub,
    "honest_boundary": "发布不改源文件、不做 git commit——产出正式补丁（可 git apply 的 unified diff）+ Release Notes 草稿于 reports/patches/，git 合并与正式发布由维护者执行；LLM 不进判决路径（评审=具名人工、发布自检=死标量门禁）；真实晶圆厂 NDA-PDK 仍属发动期 D-62 暂缓。",
    "acceptance": {"passed": all(c["ok"] for c in acceptance),
                   "checks": acceptance},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("=" * 58)
print("D-98 评审流端到端 · 发布 报告")
print("=" * 58)
for c in acceptance:
    print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']:<40} {c['detail']}")
print("-" * 58)
ap = report["acceptance"]
print(f"ACCEPTANCE: {len([c for c in ap['checks'] if c['ok']])}/{len(ap['checks'])} PASS")
print("written:", OUT)
sys.exit(0 if ap["passed"] else 1)
