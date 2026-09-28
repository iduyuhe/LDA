"""M6 实证锚指标（T5.3）—— pytest 侧的同一份判据。

判据定义与达标线**不在这里**：全部来自 `lda_harness.empirical_m6`
（`audit_m6` + `gate_m6`），CI core 的 `run_empirical_anchor_smoke` 判据⑩
调的是同一个函数。本文件只负责「把它也变成 pytest 用例」，因此**不会**出现
「pytest 绿而 core 红」的双口径。

除此之外，本文件额外钉两条只属于 pytest 侧的**对抗性判据**：
* **独立性**：`independent` 档引擎的输出必须对「被比较条的实测值」与
  「由测量反演的 geometry 字段（n_g）」**逐位不敏感** —— 否则该条其实是自证桩；
* **可分账**：标定锚必须被排除在 M6 计数之外（防用 rel≡0 刷对照数）。
"""
from __future__ import annotations

import copy

import pytest


@pytest.fixture(scope="module")
def m6():
    from lda_harness import empirical_m6

    return empirical_m6


@pytest.fixture(scope="module")
def report(m6):
    return m6.audit_m6()


def _fail_lines(report, m6):
    return [f"{c['name']} — {c['detail']}"
            for c in m6.gate_m6(report) if not c["ok"]]


def test_m6_gate_all_checks_pass(report, m6):
    """M6 全部门禁通过（语料 ≥60 / 对照 ≥12 / 全 A 级 / 质量地板）。"""
    bad = _fail_lines(report, m6)
    assert not bad, "M6 未达标：\n" + "\n".join(bad)


def test_m6_corpus_entries_have_locator_geometry_sigma(report):
    """每条语料必须带「公开定位符 + geometry + σ」（对照可复算的前提）。"""
    assert not report["missing_locator"], report["missing_locator"]
    assert not report["missing_geometry"], report["missing_geometry"]
    assert not report["missing_sigma"], report["missing_sigma"]


def test_calibration_anchors_are_excluded_from_m6_count(report, m6):
    """标定锚（引擎常数取自本条实测 ⇒ rel≡0、零信息量）**不计入** M6 对照数。

    反向断言：标定锚确实存在且确实被排除 —— 若哪天有人把 rel==0 的条目
    混进计数，对照数会虚增而这条不会响，故显式核对三类之和与总数一致。
    """
    assert report["comparisons_calibration"] >= 1, "标定锚分账已失效（应为 ≥1 条）"
    total = (report["comparisons_independent"] + report["comparisons_cross"]
             + report["comparisons_calibration"])
    assert total == report["comparisons_total"]
    assert report["comparisons_counted"] == total - report["comparisons_calibration"]
    for r in report["rows"]:
        if r["kind"] == "calibration_anchor":
            assert r["rel_pct"] == 0.0, f"标定锚 {r['id']} 的 rel 应为 0"


def test_independent_comparisons_do_not_read_measured_value(m6):
    """🔴 独立性对抗判据：扰动「被比较条的实测值 + 由测量反演的 n_g」，
    `independent` 档引擎输出必须**逐位不动**。

    这是 M6 的核心护栏 —— 没有它，「实测对照」会退化成「引擎参数里藏了答案」
    （自证桩的现代变体）。扰动只发生在内存副本上，**不落盘、不改语料**。
    """
    base = m6.run_comparisons()
    by_id = {r["id"]: r for r in base}

    corpus, raw = m6.load_seed()
    mutated = copy.deepcopy(raw)
    for x in mutated["corpus"]:
        x["measured_value"] = float(x["measured_value"]) * 1.37 + 0.11
        g = x.get("geometry") or {}
        if "n_g" in g:                      # 由测量反演的派生字段
            g["n_g"] = float(g["n_g"]) * 1.37

    import json
    import os
    import tempfile

    tmp = tempfile.mkdtemp(prefix="lda_m6_probe_")
    mp = os.path.join(tmp, "seed_mutated.json")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(mutated, f, ensure_ascii=False)
    try:
        probe = {r["id"]: r for r in m6.run_comparisons(mp)}
    finally:
        os.remove(mp)

    moved = []
    for eid, r in by_id.items():
        if r["kind"] != "independent" or not r.get("ok"):
            continue
        p = probe.get(eid, {})
        if not p.get("ok") or p.get("computed") != r.get("computed"):
            moved.append((eid, r.get("computed"), p.get("computed")))
    assert not moved, (
        "independent 档对被测/派生量敏感 ⇒ 实为自证桩："
        f"{moved}")


def test_cross_measurement_comparisons_read_only_other_entries(m6):
    """`cross_measurement` 档只允许读**另一条**语料的实测值。

    读数范围由登记表 `loss_from` 静态限定；这里断言 `loss_from` 存在、
    指向真实语料、且**不等于自身**（同条自读即为自证）。
    """
    corpus, raw = m6.load_seed()
    ids = {x["id"] for x in raw["corpus"]}
    for eid, spec in m6.comparison_targets().items():
        if spec["kind"] != "cross_measurement":
            continue
        src = spec["loss_from"]
        assert src in ids, f"{eid} 的 loss_from={src} 不在语料库"
        assert src != eid, f"{eid} 的 loss_from 指向自己 ⇒ 自证"
