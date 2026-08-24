"""D-93 生态共建框架 smoke：2 组（harness 题库扩充 B14-B18 + PDK Registry 框架）。

组1 harness 题库：用 build_harness_specs 自动遍历 BENCHMARK_DEFS（B1-B18），
ReferenceCandidate（返回 golden 本身）预期全过；PerturbedCandidate(0.5)
预期全 fail（演示 harness fail 检测能力覆盖新题）。

组2 PDK Registry：lda_pdk 模块可导入 + 主权分级 A/B/C 落地（SOVEREIGN_DEPS）
+ DeviceEntry 注册/查询/统计自洽。

运行：python run_ecosystem_smoke.py（managed python，零外部依赖）
"""
import sys
sys.path.insert(0, ".")

from lda_harness.verification_adapters import (build_harness_specs,
    harness_perturbed_candidate)
from lda_harness.verification_spec import run_verification
from lda_pdk import PDKRegistry, DeviceEntry, SOVEREIGN_DEPS, classify_dependency, by_class


def run(name, fn, expect_pass):
    try:
        ok, info = fn()
    except Exception as e:  # noqa: BLE001
        ok, info = False, "EXC: %s" % e
    status = "PASS" if ok == expect_pass else "FAIL"
    print("[%s] %-46s %s" % (status, name, info))
    return ok == expect_pass


def case_harness_reference():
    specs, cand = build_harness_specs()
    n = len(specs)
    npass = sum(1 for s in specs if run_verification(s, cand[s.spec_id]).passed)
    has_new = all(("B%d" % i) in [s.spec_id for s in specs] for i in range(14, 19))
    return (npass == n and has_new and n >= 18,
            "B1-B18=%d题 全过=%d/%d 含B14-18=%s" % (n, npass, n, has_new))


def case_harness_perturbed():
    # 聚焦于新题 B14-B18：50% 扰动须被 harness fail 检测捕获（验证新题
    # tol 设置足够紧 + harness 判决路径对新题生效）。注：B3/B4 为旧题、
    # tol 按 Airy 近似留宽，不在此用例范围（不改旧题容差）。
    specs, _ = build_harness_specs()
    pert = harness_perturbed_candidate(0.5)
    new_ids = ["B%d" % i for i in range(14, 19)]
    new_specs = [s for s in specs if s.spec_id in new_ids]
    nfail = sum(1 for s in new_specs if not run_verification(s, pert).passed)
    return (nfail == len(new_specs),
            "扰动0.5 新题B14-18 fail检测=%d/%d" % (nfail, len(new_specs)))


def case_pdk_sovereign():
    nA = len(by_class("A"))
    nB = len(by_class("B"))
    nC = len(by_class("C"))
    cls_ok = (classify_dependency("Meep") == "B"
              and classify_dependency("Lumerical (Ansys)") == "A"
              and classify_dependency("L0 IR/DSL") == "C")
    return (nA >= 4 and nB >= 6 and nC >= 4 and cls_ok,
            "A=%d B=%d C=%d 分类OK=%s 总数=%d" % (nA, nB, nC, cls_ok, len(SOVEREIGN_DEPS)))


def case_pdk_registry():
    reg = PDKRegistry()
    e1 = DeviceEntry(id="dc_soi_1x2", name="定向耦合器 1x2", tech="SOI",
                     foundry="NOEIC", sovereign_class="B",
                     layers=["wg", "clad"], params={"L": 15.5}, tags=["coupler"])
    e2 = DeviceEntry(id="ring_noec_10um", name="微环 R=10um", tech="SOI",
                     foundry="NOEIC", sovereign_class="B", tags=["ring"])
    e3 = DeviceEntry(id="transmon_line", name="transmon 线", tech="Transmon",
                     foundry="self", sovereign_class="C", tags=["qubit"])
    added = [reg.add(e1), reg.add(e2), reg.add(e3)]
    conflict = reg.add(e1)  # 重复 id
    q = reg.query(tech="SOI")
    st = reg.stats()
    ok = (added == ["added", "added", "added"] and conflict == "conflict"
          and len(q) == 2 and st["total"] == 3
          and st["by_sovereign_class"].get("B") == 2)
    return (ok, "注册=%s 冲突=%s SOI查询=%d 统计=%s" % (added, conflict, len(q), st))


def main():
    print("=" * 64)
    print("D-93 生态共建框架 smoke")
    print("=" * 64)
    results = [
        run("harness B1-B18 参考候选全过", case_harness_reference, True),
        run("harness 扰动0.5 fail 检测全覆盖", case_harness_perturbed, True),
        run("PDK 主权分级 A/B/C 落地", case_pdk_sovereign, True),
        run("PDK Registry 注册/查询/统计自洽", case_pdk_registry, True),
    ]
    npass = sum(results)
    print("-" * 64)
    print("SMOKE: %d/%d PASS" % (npass, len(results)))
    print("  判定红线：ORACLE 全为确定性物理定律锚，LLM 不进判决路径。")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
