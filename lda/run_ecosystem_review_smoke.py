"""D-95 生态共建 · 社区评审流 + 提案落地 —— smoke 测试（临时库，不污染真实贡献库）。

验收红线：LLM 不进判决路径——评审=具名人工（缺评审人即拒），自测=死标量门禁
（非法 ORACLE 前置自测即拒）；落地仅登记确定性物理定律并生成补丁供 git 提交。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import submit_benchmark_proposal
from lda_pdk.review import (review_proposal, land_proposal, reload_landed,
                            get_audit)
from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.golden import _GOLDEN_DISPATCH, _PHYSICAL_LAW, golden_with_source

TMP = tempfile.mkdtemp(prefix="lda_d95_")
CP = os.path.join(TMP, "contributions.json")
LP = os.path.join(TMP, "landed.json")

ORACLE_B19 = (
    "def b19_micro_ring_fsr(L_um, n_g):\n"
    "    c_um_s = 2.99792458e14\n"
    "    return c_um_s / (n_g * L_um) / 1e9\n"
)
ORACLE_B20 = (
    "def b20_fabry_perot_fsr_nm(wavelength, n, L):\n"
    "    return wavelength ** 2 / (2.0 * n * L)\n"
)

# 先清掉进程内可能残留的 live 注册（保证可重复运行）
for _bid in ("B19", "B20"):
    _GOLDEN_DISPATCH.pop(_bid, None)
    _PHYSICAL_LAW.discard(_bid)
    BENCHMARK_DEFS.pop(_bid, None)

ok = []
fail = []


def check(name, cond, detail=""):
    (ok if cond else fail).append((name, cond, detail))


# 1) 提交两条提案
r1 = submit_benchmark_proposal({"id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
                                "formula": "FSR = c/(n_g·L)",
                                "oracle_fn_name": "b19_micro_ring_fsr", "tol": 0.5,
                                "default_params": {"L_um": 100.0, "n_g": 4.0}},
                               contrib_path=CP)
check("提案提交 → accepted_pending", r1["status"] == "accepted_pending", str(r1))
r2 = submit_benchmark_proposal({"id": "B20", "title": "FP etalon FSR", "metric": "FSR_nm",
                                "formula": "FSR = λ²/(2nL)",
                                "oracle_fn_name": "b20_fabry_perot_fsr_nm", "tol": 1.0,
                                "default_params": {"wavelength": 1.55, "n": 1.0, "L": 10.0}},
                               contrib_path=CP)
check("提案提交 → accepted_pending", r2["status"] == "accepted_pending", str(r2))

# 2) 缺评审人 → 拒绝（LLM 不进判决路径）
r3 = review_proposal("B19", "approve", "", "无评审人", ORACLE_B19, contrib_path=CP)
check("缺评审人 → error（具名人工红线）", r3["status"] == "error", str(r3))

# 3) 非法 ORACLE → approve 前置自测拒绝（死标量门禁）
r4 = review_proposal("B19", "approve", "评审员甲", "公式实现",
                     "def b19_micro_ring_fsr(L_um, n_g):\n    return 'x'",
                     contrib_path=CP)
check("非法 ORACLE 前置自测拒绝", r4["status"] == "error"
      and "自测" in r4.get("reason", ""), str(r4))

# 4) 有效 approve → approved
r5 = review_proposal("B19", "approve", "杜玉河",
                     "FSR=c/(n_g·L) 为确定性物理定律，公式与实现一致",
                     ORACLE_B19, contrib_path=CP)
check("有效 approve → approved", r5["status"] == "approved", str(r5))

# 5) B20 reject → rejected
r6 = review_proposal("B20", "reject", "评审员乙", "与 B3 重复，无需新增",
                     contrib_path=CP)
check("reject → rejected", r6["status"] == "rejected", str(r6))

# 6) 落地 approved B19 → landed + live 注册
r7 = land_proposal("B19", contrib_path=CP, landed_path=LP)
check("落地 approved → landed", r7["status"] == "landed"
      and isinstance(r7.get("value"), float), str(r7))
check("落地值物理正确(FSR≈749.48GHz)", abs(r7.get("value", 0.0) - 749.481145) < 1e-3,
      str(r7.get("value")))
check("补丁已生成", len(r7.get("patch", "").splitlines()) >= 15, "patch lines")
check("live 注册 BENCHMARK_DEFS", "B19" in BENCHMARK_DEFS, "")
check("live 注册 golden dispatch", "B19" in _GOLDEN_DISPATCH, "")
check("live 注册 physical_law", "B19" in _PHYSICAL_LAW, "")
_src, _kind, _note = golden_with_source("B19", {"L_um": 100.0, "n_g": 4.0})
check("golden_with_source 判为 physical-law",
      abs(_src - 749.481145) < 1e-3 and _kind == "physical-law", _kind)

# 7) 落地非 approved（B20 rejected）→ error
r8 = land_proposal("B20", contrib_path=CP, landed_path=LP)
check("落地 rejected → error", r8["status"] == "error", str(r8))

# 8) landed 后再评审 → error
r9 = review_proposal("B19", "reject", "评审员丙", "已落地", contrib_path=CP)
check("landed 后再评审 → error", r9["status"] == "error", str(r9))

# 9) reload_landed 恢复（先摘除 live 注册）
_GOLDEN_DISPATCH.pop("B19", None)
_PHYSICAL_LAW.discard("B19")
BENCHMARK_DEFS.pop("B19", None)
n, b = reload_landed(LP)
check("reload_landed 恢复", n == 1 and b == ["B19"],
      f"n={n} bids={b}")
check("恢复后 live 注册生效", "B19" in BENCHMARK_DEFS
      and "B19" in _GOLDEN_DISPATCH and "B19" in _PHYSICAL_LAW, "")

# 10) 审计轨迹
aud = get_audit("B19", contrib_path=CP)
check("审计轨迹完整(approve+land)",
      [a["op"] for a in aud] == ["review", "land"]
      and aud[0]["decision"] == "approve", str(aud))

print("=" * 58)
print("D-95 社区评审流 + 提案落地 smoke")
print("=" * 58)
for name, cond, detail in ok:
    print(f"[PASS] {name:<34} {detail}")
for name, cond, detail in fail:
    print(f"[FAIL] {name:<34} {detail}")
print("-" * 58)
print(f"PASS={len(ok)} FAIL={len(fail)}")
print("全部通过 ✅" if not fail else "存在失败 ❌")
sys.exit(1 if fail else 0)
