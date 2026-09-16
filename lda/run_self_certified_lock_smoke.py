"""P1-1 自证桩锁定护栏 smoke（四判据）。

把 `P1-1_self_certified_discipline.md` 的「PR 必接独立候选」纪律机器化——
恰好覆盖纪律 §2 的两条触发条件：
  (a) **新增**自证桩          -> 由「棘轮上限」判据拦截（计数只减不增）；
  (b) **修改**既有自证桩抹掉锁定原因 -> 由「无锁定原因 = 0」判据拦截。

  ① harness 三分类推导有效（和 = 题数），self_certified 集合可列
  ② 棘轮上限：self_certified 计数 <= MAX_SELF_CERTIFIED（新增自证桩必被拦）
  ③ 无锁定原因 = 0：每道 self_certified 的（有效 provenance + upgrade_path）
     必须归入四类锁定类型之一（terminal_tier1 / design_rule_anchor /
     t2_blocked / re_review）——分类器不做模糊兜底，认不出即判「无锁定原因」
  ④ 反向测试：分类器对空/无关输入必须返回 None、对四类标记必须可识别
     （证明 ③ 不是假绿）

自食其规则：本 smoke 自身须登记在 `CORE_SMOKES`（由 `run_ci_coverage_gate_smoke`
复查「无静默缺口」）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LDA = os.path.dirname(HERE)
if LDA not in sys.path:
    sys.path.insert(0, LDA)

from lda_harness import benchmarks as B

# 棘轮上限：self_certified 计数「只减不增」。
# 每当有锚从 self_certified 毕业（升 strict_independent），须由该 PR 同步下调此常数。
MAX_SELF_CERTIFIED = 18

# 四类锁定原因（纪律 §2-B）。只用显式语义标记，不做模糊兜底。
_LOCK_MARKERS = (
    ("terminal_tier1", ("terminal tier-1", "terminal_tier1")),
    ("t2_blocked", ("t2 实测", "t2 实证", "t2 通道", "t2 数据集")),
    ("design_rule_anchor", ("设计守则", "design_rule")),
    ("re_review", ("重审", "re_review")),
)


def _lock_type(provenance, upgrade_path):
    """把（provenance, upgrade_path）归入四类锁定原因之一；认不出返回 None。"""
    up = (upgrade_path or "").lower()
    prov = (provenance or "").lower()
    if not up and not prov:
        return None
    for name, markers in _LOCK_MARKERS:
        for m in markers:
            if m in up or m in prov:
                return name
    return None


checks = []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print("[%s] %s  %s" % ("PASS" if ok else "FAIL", name, detail))


# ① 三分类推导有效
all_defs = B.BENCHMARK_DEFS
n_total = len(all_defs)
classes = {}
for _k, _d in all_defs.items():
    _c = B._vmm_classify(_d)
    classes[_c] = classes.get(_c, 0) + 1
sc = sorted(k for k, d in all_defs.items() if B._vmm_classify(d) == "self_certified")
check("① 三分类推导有效（和 = 题数）", sum(classes.values()) == n_total,
      "total=%d strict=%d degraded=%d self_certified=%d"
      % (n_total, classes.get("strict_independent", 0),
         classes.get("degraded", 0), classes.get("self_certified", 0)))

# ② 棘轮上限（新增自证桩必被拦）
check("② 棘轮上限：self_certified <= %d（只减不增）" % MAX_SELF_CERTIFIED,
      len(sc) <= MAX_SELF_CERTIFIED,
      "self_certified=%d（%s）" % (len(sc), ",".join(sc)))

# ③ 无锁定原因 = 0（修改既有桩抹掉锁原因必被拦）
buckets, unlocked = {}, []
for k in sc:
    d = all_defs[k]
    lt = _lock_type(B._vmm_provenance(k, d), B._vmm_upgrade_path(k, d))
    if lt is None:
        unlocked.append(k)
    else:
        buckets[lt] = buckets.get(lt, 0) + 1
check("③ 无锁定原因 = 0（每桩带四类锁之一）", not unlocked,
      "分布=%s unlocked=%s" % (dict(sorted(buckets.items())), unlocked))

# ④ 反向测试：分类器必须拒绝无锁定语义输入、识别四类标记
_neg = [("self_authored_closed_form", ""), ("", ""), (None, None),
        ("external_empirical", "待后续处理"), ("", "TODO")]
_pos = [("self_authored_closed_form", "本就不升：定义同义反复（terminal Tier-1）"),
        ("external_empirical", "T2 实测数据集（光子 PDA 实证锚）升 Tier-3"),
        ("design_rule_anchor", "设计守则边界，待场级 ORACLE"),
        ("", "待重审后升级")]
_ok_neg = all(_lock_type(p, u) is None for p, u in _neg)
_ok_pos = all(_lock_type(p, u) is not None for p, u in _pos)
check("④ 反向测试：无锁语义->None、四类标记->可识别", _ok_neg and _ok_pos,
      "neg_ok=%s pos_ok=%s" % (_ok_neg, _ok_pos))

npass = sum(1 for _, ok, _ in checks if ok)
nfail = len(checks) - npass
print("\n自证桩锁定护栏：%d/%d PASS" % (npass, len(checks)))
sys.exit(1 if nfail else 0)
