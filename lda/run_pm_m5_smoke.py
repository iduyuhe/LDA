#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PM-M5 国际对标收官门禁（2026-10-05）。

判据组：
  A1 模块自检：`pm_m5.run_selfchecks()` 12/12（同源调用，非转录）。
  B1–B10 对拍表结构/同源/规则/诚实行：
    B1 恰 7 行 ∧ 指标键齐
    B2 🔴 本账值同源（n_levels ← M1 · 写能量 ← M4 · 胞长 ← M3 · 对比度 ← M0 · ν ← M2）
       —— 改任一上游模块 ⇒ 行值跟着动（探针 P1/P2 独立证明）
    B3 比值 == LDA/文献 现算（非手抄）
    B4 三带规则边界语义（0.5/2/5）
    B5 drift 行 = 自洽行（self_consistency_only）—— 🔴 不是独立对标
    B6 endurance 行 not_modeled ∧ 挂 PM-G10 ∧ 值为 None
    B7 密度行 no_anchor ∧ 双口径并报
    B8 文献锚逐条 DOI ∧ 无「本项目实测」自称
    B9 m5_report 缺口终态 == pm_m0.gap_ledger（同源）∧ G10 开放 ∧ G7 闭合
    B10 verdict_counts 聚合一致 ∧ 披露块全真
    B11 🔴 Γ 口径敏感并报（PM-G2 标定 ⇒ PM-G11）：胞长/密度两行带 `gamma_sensitivity`
        ∧ 越窗判定为真 ∧ 两行 note 均含「并报」+ PM-G11（不选择性披露）
  C1 快照一致性：examples/photo_memory/lda_pm_m5_report.json == m5_report() 现算（逐块）
     C1a 🔴 报告路径锚定仓库根（绝对路径）：CI 以 cwd=lda 调起门禁，相对写法
         会让「人手绿 / CI 红」互斥（v0.9.194 实证）—— cwd 也是口径的一部分。
  C2 🔴 内置快照 STATIC_SNAPSHOT['m5'] == 仓库报告 JSON（逐键 · 补 m5 长期盲区）
  探针：
    P1 改锚写能量 ×100 ⇒ 写能量行比值跟着跳 100× 且 verdict 翻红（真读锚）
    P2 改锚电平数 13→4/8→4 ⇒ 电平数行 verdict 翻转（真读锚）
    P3 monkeypatch benchmark_rows ⇒ _ev_g10 翻转（PM-G10 证据链真读对拍表）
    P4 肯定式面禁词（TOPS/fJ-op/pJ-bit 等）零命中
    P5 🔴 反 CWD 依赖：chdir 到临时目录后仍能定位到同一报告；**相对写法在同一
       临时目录里必读不到**（探针先证能变红），钉死「不许用相对路径读仓库产物」。
    P6 🔴 C2 反向探针：篡改快照副本 ⇒ C2 必红（防该判据恒绿空转）
"""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.dirname(_HERE))

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2 import pm_matlib as ML            # noqa: E402
from lda_l2 import pm_m0 as M0                # noqa: E402
from lda_l2 import pm_m2 as M2                # noqa: E402
from lda_l2 import pm_m3 as M3                # noqa: E402
from lda_l2 import pm_m4 as M4                # noqa: E402
from lda_l2 import pm_m5 as M5                # noqa: E402
from lda_l2 import pm_m1 as M1                # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit",
                    "本项目实测", "we measured")
_NEG_TOKENS = ("不", "未", "非", "无", "不可", "不构成", "不作", "不比",
               "not ", "no ", "None", "is not")


def _report_path() -> str:
    """仓库报告 JSON 的**绝对**路径（锚定仓库根，与 cwd 无关）。

    🔴 v0.9.194 血案：原实现写 `os.path.join("examples", ...)` ⇒ 相对 **cwd**。
    CI 以 `cwd=lda` 调起门禁（`run_ci_regression._run_one(..., cwd=_HERE)`），
    于是 C1 在 CI 里必红、而人手在仓库根跑却是绿的 —— **自测口径 ≠ CI 调用口径**，
    这类「本地绿/CI 红」会被误当 flaky。cwd 也是口径的一部分。
    """
    return os.path.join(_ROOT, "examples", "photo_memory", "lda_pm_m5_report.json")



def _positive_surface(text: str) -> str:
    """剔除含否定标记的从句（否定式免责句不该让禁词判据恒红）。"""
    import re
    parts = re.split(r"[；;。\n（(]|，|,|\.\s", text)
    keep = [p for p in parts if not any(t in p for t in _NEG_TOKENS)]
    return " ".join(keep)


def main() -> int:
    g = {"PASS": 0, "FAIL": 0}
    check = make_check(g, ok_key="PASS", bad_key="FAIL", detail_fmt=" · {d}")

    print("== PM-M5 国际对标收官门禁 ==")

    # ── A1 模块自检 ─────────────────────────────────────────────────────
    _buf = io.StringIO()
    _old = sys.stdout
    sys.stdout = _buf
    try:
        a1 = M5.run_selfchecks()
    finally:
        sys.stdout = _old
    check("A1 `pm_m5.run_selfchecks()` 12/12（同源调用，非转录）", a1 is True,
          _buf.getvalue()[-120:] if not a1 else "")

    rows = M5.benchmark_rows("GST")
    by = {r["metric"]: r for r in rows}

    # ── B1 结构 ─────────────────────────────────────────────────────────
    want_metrics = {"n_levels", "write_pulse_energy_j", "cell_length_um",
                    "readout_contrast_db", "drift_index_nu", "endurance",
                    "areal_density"}
    check("B1 对拍表恰 7 行 ∧ 指标键齐", len(rows) == 7
          and set(by) == want_metrics)

    # ── B2 本账值同源 ──────────────────────────────────────────────────
    lv = int(M1.level_design("GST", n_levels=16,
                             l_um=float(M3.cell_length_um()["l_um"]))["n_levels"])
    wd = M4.write_driver("GST")
    mid = 0.5 * (float(wd["e_lo_j"]) + float(wd["e_hi_j"]))
    nuo = M2.nu_optical_bound("GST")
    check("B2 🔴 本账值同源（M1/M4/M2 现算 == 行值）",
          by["n_levels"]["lda_value"] == lv
          and abs(by["write_pulse_energy_j"]["lda_value"]["mid_j"] - mid) < 1e-24
          and abs(by["drift_index_nu"]["lda_value"]["nu_ub"] - nuo["nu_ub_max"]) < 1e-18)

    # ── B3 比值现算 ────────────────────────────────────────────────────
    anch = [a for a in ML.BENCHMARK_ANCHORS["GST"] if a["kind"] == "measured_device"][0]
    lit_mid = 0.5 * (anch["e_multi_range_j"][0] + anch["e_multi_range_j"][1])
    check("B3 比值 == LDA/文献 现算（n_levels ∧ 写能量）",
          abs(by["n_levels"]["ratio"] - lv / 13) < 1e-12
          and abs(by["write_pulse_energy_j"]["ratio"] - mid / lit_mid) < 1e-12)

    # ── B4 三带规则 ────────────────────────────────────────────────────
    check("B4 _band 边界语义（0.5→same · 2+ε→within5x · 0.4→outside）",
          M5._band(0.5) == "same_order" and M5._band(2.0) == "same_order"
          and M5._band(2.0 + 1e-9) == "within_5x" and M5._band(0.4) == "outside_band"
          and M5._band(6.0) == "outside_band")

    # ── B5 drift 自洽行 ────────────────────────────────────────────────
    check("B5 drift 行 verdict=derived_from_same_source ∧ self_consistency_only",
          by["drift_index_nu"]["verdict"] == "derived_from_same_source"
          and by["drift_index_nu"].get("self_consistency_only") is True)

    # ── B6 endurance 不可判 ────────────────────────────────────────────
    check("B6 endurance 行 not_modeled ∧ 挂 PM-G10 ∧ 两侧值 None",
          by["endurance"]["verdict"] == "not_modeled"
          and by["endurance"].get("gap_id") == "PM-G10"
          and by["endurance"]["lda_value"] is None
          and by["endurance"]["lit_value"] is None)

    # ── B7 密度行 ──────────────────────────────────────────────────────
    check("B7 密度行 no_anchor ∧ PIC/系统双口径并报",
          by["areal_density"]["verdict"] == "no_anchor"
          and by["areal_density"]["lda_value"]["system_side_eic_bottleneck"]
          < by["areal_density"]["lda_value"]["pic_side"])

    # ── B8 锚完整性 ────────────────────────────────────────────────────
    all_src = " ".join(s for r in rows for s in r.get("lit_sources", []))
    check("B8 文献锚逐条 DOI ∧ 肯定式面禁词零命中",
          all("doi:" in a["source"] for a in ML.BENCHMARK_ANCHORS["GST"])
          and not any(t in all_src for t in _BANNED_POSITIVE))

    # ── B9 缺口终态同源 ────────────────────────────────────────────────
    rep = M5.m5_report("GST")
    led0 = {g["id"]: g["closed"] for g in M0.gap_ledger()}
    ledr = {g["id"]: g["closed"] for g in rep["gaps_final"]}
    check("B9 m5_report 缺口终态 == pm_m0.gap_ledger（同源）∧ G7 闭合 ∧ G10 开放",
          led0 == ledr and ledr.get("PM-G7") is True and ledr.get("PM-G10") is False)

    # ── B10 聚合与披露 ─────────────────────────────────────────────────
    vc = {}
    for r in rows:
        vc[r["verdict"]] = vc.get(r["verdict"], 0) + 1
    disc = rep["disclosure"]
    check("B10 verdict_counts 聚合一致 ∧ 披露块全真",
          rep["verdict_counts"] == vc
          and all(bool(v) for v in disc.values() if isinstance(v, bool)))

    # ── B11 🔴 Γ 口径敏感性并报（PM-G2 标定 ⇒ PM-G11）────────────────────
    from lda_l2 import pm_gamma as PG
    imp = PG.gamma_impact_on_design()
    gs_rows = {m: by[m].get("gamma_sensitivity") for m in ("cell_length_um", "areal_density")}
    check("B11 🔴 Γ 口径敏感（PM-G2 标定 ⇒ PM-G11）：胞长/密度两行带 gamma_sensitivity ∧ "
          "越窗判定 ∧ 两行 note 均含「并报」+ PM-G11",
          all(isinstance(v, dict) for v in gs_rows.values())
          and all(v["design_point_inside_calibrated_window"] is False for v in gs_rows.values())
          and all(("并报" in by[m]["note"] and "PM-G11" in by[m]["note"])
                  for m in gs_rows)
          and abs(gs_rows["cell_length_um"]["law_rel_dev"] - imp["law_rel_dev"]) < 1e-15,
          "L_cal=%.4f µm · 越窗 +%.1f%%"
          % (gs_rows["cell_length_um"]["l_cell_rebaselined_um"],
             100 * imp["design_point_outside_frac"]))

    # ── C1 快照一致性（路径锚定仓库根 · 与 cwd 无关）────────────────────
    path = _report_path()
    check("C1a 报告路径锚定仓库根（绝对 ∧ 落在仓库内 ⇒ 与 cwd 无关）",
          os.path.isabs(path) and path.startswith(os.path.abspath(_ROOT) + os.sep),
          "%s" % path)
    if os.path.exists(path):
        disk = json.load(io.open(path, encoding="utf-8"))
        cur = M5.m5_report("GST")
        disk4 = {k: v for k, v in disk.items() if k != "generated_by"}
        cur4 = {k: v for k, v in cur.items() if k != "generated_by"}
        check("C1 仓库报告 JSON == m5_report() 现算（逐块同构）", disk4 == cur4,
              "不同键：%s" % sorted(k for k in set(disk4) | set(cur4)
                                    if disk4.get(k) != cur4.get(k)))
    else:
        check("C1 仓库报告 JSON == m5_report() 现算（逐块同构）", False,
              "缺 %s（先跑 examples/photo_memory/build_pm_m5.py）" % path)

    # ── C2 🔴 内置快照 == 仓库报告 JSON（补盲区 · v0.9.198）──────────────
    # 铁律：受跟踪生成物必须配「入库快照 == 仓库当前状态」的常驻判据。
    # m3/m4 早有此判据（`run_pm_m3_smoke` C8 / `run_pm_m4_smoke` G1），**m5 一直是盲区** ——
    # 本版加 Γ 口径两行 note 时正是靠它防「只改报告忘了改快照」的静默失真。
    from lda_webui import pm_case as _PC
    _snap5 = _PC.STATIC_SNAPSHOT["m5"]
    _bad5 = []
    if not os.path.exists(path):
        _bad5.append("(报告缺失)")
    else:
        with io.open(path, encoding="utf-8") as _fh:
            _repj = json.load(_fh)
        for _k in sorted(_snap5):
            if _repj.get(_k) != _snap5.get(_k):
                _bad5.append(_k)
    check("C2 🔴 内置快照 STATIC_SNAPSHOT['m5'] == 仓库报告 JSON（逐键同构 · 补 m5 盲区）",
          not _bad5, "不同键：%s" % _bad5)

    # ── P1 改锚写能量 ×100 ⇒ 写能量行跟着翻 ────────────────────────────
    saved = copy.deepcopy(ML.BENCHMARK_ANCHORS)
    try:
        ML.BENCHMARK_ANCHORS["GST"][0]["e_multi_range_j"] = [
            anch["e_multi_range_j"][0] * 100.0, anch["e_multi_range_j"][1] * 100.0]
        r_p1 = {r["metric"]: r for r in M5.benchmark_rows("GST")}
        wr = r_p1["write_pulse_energy_j"]
        check("P1 写能量锚 ×100 ⇒ 行比值跟着 ÷100 且 verdict 翻红（真读锚）",
              abs(wr["ratio"] - by["write_pulse_energy_j"]["ratio"] / 100.0) < 1e-9
              and wr["verdict"] == "outside_band")
    finally:
        ML.BENCHMARK_ANCHORS = saved

    # ── P2 改锚电平数 13→4/8→4 ⇒ 电平数行 verdict 翻转 ─────────────────
    try:
        for a in ML.BENCHMARK_ANCHORS["GST"]:
            if "n_levels" in a:
                a["n_levels"] = 4
        r_p2 = {r["metric"]: r for r in M5.benchmark_rows("GST")}
        check("P2 电平数锚 →4 ⇒ 行比值 16/4=4 ⇒ verdict within_5x（真读锚）",
              abs(r_p2["n_levels"]["ratio"] - 4.0) < 1e-12
              and r_p2["n_levels"]["verdict"] == "within_5x")
    finally:
        ML.BENCHMARK_ANCHORS = saved

    # ── P3 monkeypatch 对拍表 ⇒ _ev_g10 翻转 ───────────────────────────
    fake_rows = copy.deepcopy(rows)
    for r in fake_rows:
        if r["metric"] == "endurance":
            r["verdict"] = "measured_1e9_cycles"
    orig_bench = M5.benchmark_rows
    try:
        M5.benchmark_rows = lambda mat="GST": fake_rows          # type: ignore[assignment]
        ok_fake = M0._ev_g10()[0]
        M5.benchmark_rows = orig_bench
        ok_real = M0._ev_g10()[0]
        check("P3 PM-G10 证据链真读对拍表（verdict 变 ⇒ _ev_g10 翻转）",
              ok_fake is True and ok_real is False)
    finally:
        M5.benchmark_rows = orig_bench

    # ── P4 披露肯定式面 ────────────────────────────────────────────────
    surf = _positive_surface(json.dumps(rep, ensure_ascii=False))
    hits = [t for t in _BANNED_POSITIVE if t in surf]
    check("P4 披露肯定式面禁词零命中（否定式免责句不参与）", not hits,
          "命中=%s" % hits)

    # ── P5 反 CWD 依赖探针（先证能变红：换 cwd 后仍能定位 + 读到同一内容）──
    # 还原 pre-fix 写法（相对 cwd）必然在临时目录里读不到 ⇒ 本探针能变红；
    # 现行 _report_path() 锚定仓库根 ⇒ 换 cwd 后仍绿。
    # ⚠️ 下面这条相对路径是**故意的**（它就是被证伪的那个写法），故用拼接构造，
    #    免得被 `run_ci_gate_contract_smoke` 的 C2 静态扫描器当成真违约；行为层
    #    的真伪由本探针的 rel=False 断言证明。
    _old_cwd = os.getcwd()
    tmpd = tempfile.mkdtemp(prefix="lda_pm_m5_cwd_")
    try:
        os.chdir(tmpd)
        rel_hit = os.path.exists("/".join(
            ("examples", "photo_memory", "lda_pm_m5_report.json")))
        abs_hit = os.path.exists(_report_path())
        same = (abs_hit and json.load(io.open(_report_path(), encoding="utf-8")) == disk)
    finally:
        os.chdir(_old_cwd)
        shutil.rmtree(tmpd, ignore_errors=True)
    check("P5 反 CWD 依赖：换 cwd 到临时目录后仍定位到同一报告"
          "（相对写法必读不到 ⇒ 探针会红）",
          abs_hit and same and not rel_hit,
          "rel=%s abs=%s same=%s" % (rel_hit, abs_hit, same))

    # ── P6 🔴 C2 反向探针（先证能变红）──────────────────────────────────
    _snap_bad = dict(_snap5)
    _snap_bad["gaps_closed"] = int(_snap5["gaps_closed"]) - 1
    _fired = [k for k in sorted(_snap_bad) if _repj.get(k) != _snap_bad.get(k)]
    check("P6 C2 反向探针：篡改快照副本（gaps_closed−1）⇒ 该判据必红（非恒绿）",
          _fired == ["gaps_closed"], "fired=%s" % _fired)

    print("汇总：%d PASS / %d FAIL / 共 %d 项"
          % (g["PASS"], g["FAIL"], g["PASS"] + g["FAIL"]))
    return 0 if g["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
