"""D-93 生态共建框架 smoke：3 组（harness 题库扩充 B14-B18 + PDK Registry 框架
+ 受跟踪报告 `reports/ecosystem_d93.json` 快照同步）。

组1 harness 题库：用 build_harness_specs 自动遍历 BENCHMARK_DEFS（B1-B18），
ReferenceCandidate（返回 golden 本身）预期全过；PerturbedCandidate(0.5)
预期全 fail（演示 harness fail 检测能力覆盖新题）。

组2 PDK Registry：lda_pdk 模块可导入 + 主权分级 A/B/C 落地（SOVEREIGN_DEPS）
+ DeviceEntry 注册/查询/统计自洽。

组3 🔴 v0.9.197（D-93 报告漂移专项）：`reports/ecosystem_d93.json` 是**受跟踪
生成物**，其生成器 `run_ecosystem_report.py` **不在 CI**（一次性证据生成器）
⇒ 必然落后（此前停在 2026-08-24）。本组以「**快照 == 仓库现算**」常驻判据
强制同步：报告的 harness 计数/B14-B18 物理值/主权分级 必须等于**本 smoke 现算**。

运行：python run_ecosystem_smoke.py（managed python，零外部依赖）
"""
import json
import os
import sys
sys.path.insert(0, ".")

from lda_harness import deterministic as det
from lda_harness.golden import (b14_dc_coupling_length, b15_bragg_wavelength,
    b16_mmi_length, b17_jj_critical_current, b18_purcell_factor)
from lda_harness.verification_adapters import (build_harness_specs,
    harness_perturbed_candidate)
from lda_harness.verification_spec import run_verification
from lda_pdk import PDKRegistry, DeviceEntry, SOVEREIGN_DEPS, classify_dependency, by_class

_HERE = os.path.dirname(os.path.abspath(__file__))
_ECO_REPORT = os.path.join(_HERE, "reports", "ecosystem_d93.json")

# 新题 B14-B18 的 golden 函数（判据用**报告内的 params** 现算 ⇒ 验「报告值 == 现算值」；
# golden 若被改而报告未重生成 ⇒ 必红）
_NEW_FNS = {
    "B14": b14_dc_coupling_length,
    "B15": b15_bragg_wavelength,
    "B16": b16_mmi_length,
    "B17": b17_jj_critical_current,
    "B18": b18_purcell_factor,
}

# 模块级缓存：specs 构建 + 参考候选全量是重活（约分钟级），本 smoke 内多处共用
_CACHE = {}


def _specs_and_pass():
    """构建 harness specs 并跑参考候选全量（带模块级缓存）。"""
    if "specs" not in _CACHE:
        specs, cand = build_harness_specs()
        _CACHE["specs"] = specs
        _CACHE["npass"] = sum(
            1 for s in specs if run_verification(s, cand[s.spec_id]).passed)
    return _CACHE["specs"], _CACHE["npass"]


def run(name, fn, expect_pass):
    try:
        ok, info = fn()
    except Exception as e:  # noqa: BLE001
        ok, info = False, "EXC: %s" % e
    status = "PASS" if ok == expect_pass else "FAIL"
    print("[%s] %-46s %s" % (status, name, info))
    return ok == expect_pass


def case_harness_reference():
    specs, npass = _specs_and_pass()
    n = len(specs)
    has_new = all(("B%d" % i) in [s.spec_id for s in specs] for i in range(14, 19))
    return (npass == n and has_new and n >= 18,
            "B1-B18=%d题 全过=%d/%d 含B14-18=%s" % (n, npass, n, has_new))


def case_harness_perturbed():
    # 聚焦于新题 B14-B18：50% 扰动须被 harness fail 检测捕获（验证新题
    # tol 设置足够紧 + harness 判决路径对新题生效）。注：B3/B4 为旧题、
    # tol 按 Airy 近似留宽，不在此用例范围（不改旧题容差）。
    specs, _ = _specs_and_pass()
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


def case_report_snapshot_sync():
    """🔴 受跟踪报告 `reports/ecosystem_d93.json` 必须 == 仓库现算（防漂移）。

    生成器 `run_ecosystem_report.py` **不在 CI** ⇒ 无本判据则必然落后（曾停在
    2026-08-24：harness 18/18 而现算 476/476、B14 15.5 而现算 7.75、主权 16 而
    现算 17）。本判据**复用** `_specs_and_pass` 的现算结果（零额外成本），
    逐字段比对：harness 计数/全过标志 · 主权总数与 A/B/C · B14-B18 物理值。
    """
    specs, npass = _specs_and_pass()
    with open(_ECO_REPORT, encoding="utf-8") as f:
        rep = json.load(f)
    bad = []
    h = rep.get("harness") or {}
    if h.get("total") != len(specs):
        bad.append("harness.total 报告=%s 现算=%d" % (h.get("total"), len(specs)))
    if h.get("passed") != npass:
        bad.append("harness.passed 报告=%s 现算=%d" % (h.get("passed"), npass))
    if bool(h.get("all_pass")) != (npass == len(specs)):
        bad.append("harness.all_pass 报告=%s 现算=%s"
                   % (h.get("all_pass"), npass == len(specs)))
    sov = rep.get("pdk_sovereign") or {}
    if sov.get("sovereign_deps_total") != len(SOVEREIGN_DEPS):
        bad.append("主权总数 报告=%s 现算=%d"
                   % (sov.get("sovereign_deps_total"), len(SOVEREIGN_DEPS)))
    for c in ("A", "B", "C"):
        got = (sov.get("by_class") or {}).get(c)
        if got != len(by_class(c)):
            bad.append("主权%s 报告=%s 现算=%d" % (c, got, len(by_class(c))))
    vals = rep.get("new_benchmark_values") or {}
    for bid, fn in _NEW_FNS.items():
        entry = vals.get(bid) or {}
        got = entry.get("value")
        try:
            want = det.canon(fn(**(entry.get("params") or {})))
        except Exception as e:  # noqa: BLE001
            bad.append("%s 现算异常 %s" % (bid, type(e).__name__))
            continue
        if got != want:
            bad.append("%s.value 报告=%s 现算=%s" % (bid, got, want))
    info = ("报告快照==现算（%d题/%d过 · 主权%d · B14-18值全同）"
            % (len(specs), npass, len(SOVEREIGN_DEPS))
            if not bad else "漂移: %s" % bad[:3])
    return (not bad, info)


def main():
    print("=" * 64)
    print("D-93 生态共建框架 smoke")
    print("=" * 64)
    results = [
        run("harness B1-B18 参考候选全过", case_harness_reference, True),
        run("harness 扰动0.5 fail 检测全覆盖", case_harness_perturbed, True),
        run("PDK 主权分级 A/B/C 落地", case_pdk_sovereign, True),
        run("PDK Registry 注册/查询/统计自洽", case_pdk_registry, True),
        run("报告快照 == 仓库现算（防漂移）", case_report_snapshot_sync, True),
    ]
    npass = sum(results)
    print("-" * 64)
    print("SMOKE: %d/%d PASS" % (npass, len(results)))
    print("  判定红线：ORACLE 全为确定性物理定律锚，LLM 不进判决路径。")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
