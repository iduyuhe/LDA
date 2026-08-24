"""D-98 生态共建 · 评审流端到端 · 发布（Publish）—— smoke 测试（临时库/产物目录）。

覆盖：完整链 propose→approve→land→publish；发布须具名 author（缺即拒）；
仅 landed 可发布（pending 发布→error）；补丁生成（golden.py+benchmarks.py 双段、
含注册行、可 git apply 的 unified diff）；Release Notes 生成；状态 published；
审计含 publish；list_published；review_stats 含 published。
验收红线：LLM 不进判决路径；发布不改源文件、不做 git commit，产出补丁供维护者应用。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal
from lda_pdk.review import review_proposal, land_proposal, get_audit, review_stats
from lda_pdk.publish import publish_proposal, list_published

TMP = tempfile.mkdtemp(prefix="lda_d98s_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")
PD = os.path.join(TMP, "patches")

SRC = ("def b19_micro_ring_fsr(L_um, n_g):\n"
       "    c_um_s = 2.99792458e14\n"
       "    return c_um_s / (n_g * L_um) / 1e9\n")

ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append((name, cond, detail))


# 1) 完整链
r0 = submit_benchmark_proposal({
    "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
    "formula": "FSR = c/(n_g·L)", "oracle_fn_name": "b19_micro_ring_fsr",
    "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
}, contrib_path=CP)
r1 = review_proposal("B19", "approve", "杜玉河", "FSR=c/(n_g·L) 确定性物理定律",
                     SRC, contrib_path=CP)
r2 = land_proposal("B19", contrib_path=CP, landed_path=LP)
check("完整链 submit→approve→land",
      r0["status"] == "accepted_pending" and r1["status"] == "approved"
      and r2["status"] == "landed", f"{r0['status']}/{r1['status']}/{r2['status']}")

# 2) 发布须具名 author
r3 = publish_proposal("B19", "", contrib_path=CP, landed_path=LP, patches_dir=PD)
check("缺发布人 → 拒（git 提交是维护者动作）", r3["status"] == "error"
      and "发布人" in r3.get("reason", ""), r3.get("reason", "")[:40])

# 3) 仅 landed 可发布
submit_benchmark_proposal({
    "id": "B20", "title": "x", "metric": "M", "formula": "M=n*L",
    "oracle_fn_name": "b20", "tol": 0.5, "default_params": {"L": 1.0},
}, contrib_path=CP)
r4 = publish_proposal("B20", "杜玉河", contrib_path=CP, landed_path=LP,
                      patches_dir=PD)
check("非 landed 发布 → 拒", r4["status"] == "error"
      and "landed" in r4.get("reason", ""), r4.get("reason", "")[:45])

# 4) 发布
r5 = publish_proposal("B19", "杜玉河", "社区贡献", contrib_path=CP,
                      landed_path=LP, patches_dir=PD)
check("发布 → published", r5["status"] == "published"
      and r5.get("value") == 749.481145, str(r5.get("value")))
check("补丁与 Release Notes 落盘", bool(r5.get("patch_path"))
      and bool(r5.get("release_path"))
      and os.path.exists(r5["patch_path"]) and os.path.exists(r5["release_path"]),
      r5.get("patch_path", ""))

patch = open(r5["patch_path"], encoding="utf-8").read()
check("补丁含 golden.py + benchmarks.py 双段",
      "a/golden.py" in patch and "a/benchmarks.py" in patch, "双段")
check("补丁含注册行（dispatch + physical_law + BENCHMARK_DEFS）",
      '_GOLDEN_DISPATCH["B19"]' in patch and '_PHYSICAL_LAW.add("B19")' in patch
      and 'BENCHMARK_DEFS["B19"]' in patch, "")
check("补丁为 unified diff（含 +++ 与 hunk）",
      "+++ b/golden.py" in patch and "@@" in patch, "")

rel = open(r5["release_path"], encoding="utf-8").read()
check("Release Notes 含标题/指标/ORACLE/评审人",
      "微环 FSR" in rel and "FSR_GHz" in rel and "b19_micro_ring_fsr" in rel
      and "杜玉河" in rel, "")

# 5) 状态 published + 审计 + 统计
aud = get_audit("B19", contrib_path=CP)
check("状态 published + 审计含 publish",
      [a["op"] for a in aud] == ["review", "land", "publish"], str(aud[-1].get("op")))
stats = review_stats(contrib_path=CP)
check("review_stats 含 published", stats["by_status"].get("published") == 1,
      str(stats["by_status"]))

# 6) list_published
pub = list_published(landed_path=LP)
check("list_published 返回记录",
      len(pub) == 1 and pub[0]["bid"] == "B19"
      and pub[0]["published_by"] == "杜玉河" and bool(pub[0]["patch_path"]),
      str([(x["bid"], x["published_by"]) for x in pub]))

print("=" * 58)
print("D-98 评审流端到端 · 发布 smoke")
print("=" * 58)
for name, cond, detail in ok:
    print(f"[PASS] {name:<42} {detail}")
for name, cond, detail in fail:
    print(f"[FAIL] {name:<42} {detail}")
print("-" * 58)
print(f"PASS={len(ok)} FAIL={len(fail)}")
print("全部通过 ✅" if not fail else "存在失败 ❌")
sys.exit(1 if fail else 0)
