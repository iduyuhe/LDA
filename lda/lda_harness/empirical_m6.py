"""M6 实证锚审计与「实测对照」注册表（T5.3）。

指标 M6 = **A 级实证锚数** = `empirical_bank` 入库数 / 实测对照数。
本模块是该指标的**唯一机器判据来源**：`run_empirical_anchor_smoke.py`（CI core）
与 `tests/test_m6_empirical.py`（pytest 第二入口）都调它，避免两处口径漂移。

「实测对照」的判据（刻意写死，防事后放宽）
----------------------------------------
一条语料算**一条对照**，当且仅当：存在一条**被真实执行**的计算路径，它对该语料
产出同量纲数值，并与实测值算出 rel% 且**登记在案**。分三档，**只有前两档计入 M6**：

* `independent`      —— 计算路径只吃「几何 + 物理常数」，**不读被比较条的任何
  测量量**（含 geometry 里由测量反演出来的字段，如 `n_g`）。rel% 是真预测误差。
* `cross_measurement`—— 计算路径读的是**另一条语料**的实测值（同平台跨器件
  一致性对照，例：直波导测的损耗 → 预测微环的内禀 Q）。被比较条自身的测量值
  仍不被读。
* `calibration_anchor`—— 引擎的标定常数**取自本条的实测值** ⇒ rel% 近零但
  **零信息量**。登记在案以求透明，但**不计入 M6 对照数**（与 P3/T3.2 的
  「同后端对照不列入独立格，防虚假繁荣」同一纪律）。

所有分档由**静态登记 + 突变探针**双向守护：探针会改动某条的实测值/派生字段，
断言 `independent` 档的输出**逐位不动**（见 `scripts/p5_probe.py`）。

红线：本模块只读语料与引擎，**不做拟合**、不修改任何语料数值，LLM 不进判决。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
SEED_PATH = os.path.join(_HERE, "seed_empirical.json")

# ---------------------------------------------------------------- M6 达标线
#: 语料入库条数下限（计划 §4 M6：30 → ≥60）
M6_CORPUS_MIN = 60
#: 「实测对照」条数下限（计划 §4 M6：5 → ≥12；含 cross_measurement，不含标定锚）
M6_COMPARISON_MIN = 12
#: 其中 `independent` 档下限（防「全用跨器件一致性凑数」）
M6_INDEPENDENT_MIN = 8
#: 每个公开定位符**平均**至少覆盖多少条语料 —— 即 distinct 定位符数下限。
#: 防「一个 URL 灌 30 条」把条数刷上去（30 条旧语料约 20 个定位符）。
M6_DISTINCT_LOCATOR_MIN = 40
#: 对照质量地板：rel% 中位数上限 与 「rel ≤ 25%」的条数下限。
#: 地板定得比实测略松是有意的——它的作用是拦「模型退化成噪声」这类事故，
#: 不是拦「诚实但不准的半解析模型」；后者应当以 FAIL 如实留在牌面上。
M6_MEDIAN_REL_MAX = 30.0
M6_WITHIN_25_MIN = 7


# ------------------------------------------------------------------ 登记表
#: 🔴 既有 loss/效率族（6 条）**不在此重复登记** —— 直接由
#: `lda_design.loss_engines.CORPUS_ENGINE_MAP` 派生，保证单一来源。
#: 下列三条的引擎常数**取自本条实测**（`engine_crossing` 的 c1/c2+2.5w 恰好
#: 复现 0.18 dB；`engine_mmi_el` 的基础值 0.05 dB；`engine_sin_pl` 的 PL0=0.087
#: dB/cm 标定在 800x800 厚 SiN 点）⇒ 一律标 `calibration_anchor`，不计入 M6。
CALIBRATION_ANCHORS = {"E-SOI-CROSS-IL", "E-MMI-1X2-EL", "E-SIN-PL-800"}

#: 新增对照：语料 id → {engine, metric, kind, ...}
#: `assumed` 是**显式声明的缺失几何补全**（语料未声明宽度时），不是拟合——
#: 每项都必须带 `assume_note` 说明取值依据。
_NEW_COMPARISONS: Dict[str, Dict[str, Any]] = {
    # ---- 独立档：几何 + 材料常数 → 数值 ----
    "E-SIN-NG-300": {"engine": "engine_wg_ng", "metric": "n_g",
                     "kind": "independent", "pol": "TE"},
    "E-SOI-NG-220": {"engine": "engine_wg_ng", "metric": "n_g",
                     "kind": "independent", "pol": "TE"},
    "E-RING-FSR": {"engine": "engine_ring_fsr", "metric": "FSR_nm",
                   "kind": "independent", "pol": "TE"},
    "E-TBOX-FSR-TE": {"engine": "engine_ring_fsr", "metric": "FSR_nm",
                      "kind": "independent", "pol": "TE"},
    "E-TBOX-FSR-TM": {"engine": "engine_ring_fsr", "metric": "FSR_nm",
                      "kind": "independent", "pol": "TM"},
    "E-GC-APOD-81": {"engine": "engine_grating_apod",
                     "metric": "coupling_efficiency", "kind": "independent"},
    "E-GE-PD-RESP": {"engine": "engine_pd_responsivity_ideal",
                     "metric": "responsivity_A_per_W", "kind": "independent"},
    "E-GE-PD-RESP-MCGILL": {"engine": "engine_pd_responsivity_ideal",
                            "metric": "responsivity_A_per_W", "kind": "independent"},
    # ---- 跨器件一致性档：读**另一条**语料的实测损耗 ----
    "E-RING-Q42": {"engine": "engine_ring_intrinsic_q", "metric": "intrinsic_Q",
                   "kind": "cross_measurement", "loss_from": "E-RING-PL-25",
                   "assumed": {"w_core_um": 0.5},
                   "assume_note": "语料未声明环宽；取 SOI 单模条波导典型 500 nm"},
    "E-TBOX-QI-TE": {"engine": "engine_ring_intrinsic_q", "metric": "intrinsic_Q",
                     "kind": "cross_measurement", "loss_from": "E-TBOX-PL-TE"},
    "E-TBOX-QL-TM": {"engine": "engine_ring_intrinsic_q", "metric": "loaded_Q",
                     "kind": "cross_measurement", "loss_from": "E-TBOX-PL-TM"},
    "E-SIN-Q37": {"engine": "engine_ring_intrinsic_q", "metric": "intrinsic_Q",
                  "kind": "cross_measurement", "loss_from": "E-SIN-PL-800",
                  "assumed": {"w_core_um": 1.35},
                  "assume_note": "语料未声明环宽；取与膜厚同值 1.35 µm（大截面厚 SiN 微环典型）"},
    "E-RING-Q-2UM": {"engine": "engine_ring_intrinsic_q", "metric": "intrinsic_Q",
                     "kind": "cross_measurement", "loss_from": "E-SOI-PL-2UM"},
}


def comparison_targets() -> Dict[str, Dict[str, Any]]:
    """全部对照目标（既有 loss 族派生 + 新登记），单一来源。"""
    from lda_design.loss_engines import CORPUS_ENGINE_MAP

    targets: Dict[str, Dict[str, Any]] = {}
    for eid, m in CORPUS_ENGINE_MAP.items():
        targets[eid] = {
            "engine": m["engine"], "metric": m["metric"],
            "kind": ("calibration_anchor" if eid in CALIBRATION_ANCHORS
                     else "independent"),
            "via": "loss_engines",
        }
    targets.update({k: dict(v, via="empirical_models")
                    for k, v in _NEW_COMPARISONS.items()})
    return targets


# ------------------------------------------------------------------ 语料加载
def load_seed(seed_path: Optional[str] = None):
    """加载语料（返回 EmpiricalCorpus + 原始 dict 列表）。"""
    from lda_harness.empirical_bank import EmpiricalCorpus

    path = seed_path or SEED_PATH
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return EmpiricalCorpus(raw.get("corpus", [])), raw


# ------------------------------------------------------------------ 执行对照
def _evaluate(eid: str, spec: Dict[str, Any], corpus, raw_by_id) -> Dict[str, Any]:
    """执行一条对照，返回带 rel% 的行（**永不抛**：缺件记 error 行）。"""
    from lda_design import empirical_models as EM
    from lda_design.loss_engines import resolve_corpus_engine

    m = corpus.get(eid)
    row: Dict[str, Any] = {
        "id": eid, "metric": spec["metric"], "kind": spec["kind"],
        "engine": spec["engine"], "via": spec.get("via", ""),
    }
    if m is None:
        row.update({"ok": False, "error": f"语料库无此条：{eid}"})
        return row
    geom = dict(m.geometry)
    for k, v in (spec.get("assumed") or {}).items():
        geom.setdefault(k, v)
    if spec.get("assume_note"):
        row["assumed"] = spec["assumed"]
        row["assume_note"] = spec["assume_note"]

    row["measured"] = float(m.measured_value)
    row["sigma"] = float(m.uncertainty_abs)
    row["source_url"] = m.source_url
    try:
        if spec.get("via") == "loss_engines":
            out = resolve_corpus_engine(eid, geom)
            row["computed"] = out.get("value")
            row["model"] = out.get("detail", "")
        elif spec["engine"] == "engine_ring_intrinsic_q":
            src = spec["loss_from"]
            loss_val = float(raw_by_id[src]["measured_value"])
            out = EM.engine_ring_intrinsic_q(geom, loss_val, spec.get("pol", "TE"))
            row["computed"] = out["value"]
            row["model"] = out["model"]
            row["loss_from"] = src
        else:
            fn = EM.ENGINE_FUNCS[spec["engine"]]
            out = fn(geom, spec["pol"]) if "pol" in spec else fn(geom)
            row["computed"] = out["value"]
            row["model"] = out.get("model", "")
    except Exception as e:  # noqa: BLE001  求解器不可用 ⇒ 显式登记，不静默放过
        row.update({"ok": False, "error": f"{type(e).__name__}: {e}"})
        return row

    if row.get("computed") is None:
        row.update({"ok": False, "error": "引擎未产出数值"})
        return row
    row["ok"] = True
    row["rel_pct"] = round(
        abs(float(row["computed"]) - row["measured"])
        / max(abs(row["measured"]), 1e-12) * 100.0, 2)
    return row


def run_comparisons(seed_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """执行全部登记的对照，逐条返回 {id, measured, computed, rel_pct, kind, ...}。"""
    corpus, raw = load_seed(seed_path)
    raw_by_id = {x["id"]: x for x in raw.get("corpus", [])}
    targets = comparison_targets()
    return [_evaluate(eid, spec, corpus, raw_by_id)
            for eid, spec in sorted(targets.items())]


# ------------------------------------------------------------------ M6 审计
def audit_m6(seed_path: Optional[str] = None) -> Dict[str, Any]:
    """M6 全量审计：语料侧（条数/溯源/字段完备）+ 对照侧（条数/分档/rel 分布）。"""
    from lda_harness.provenance import audit_items, extract_locators

    corpus, raw = load_seed(seed_path)
    items = raw.get("corpus", [])
    prov = audit_items(corpus._items.values())

    ids = [x["id"] for x in items]
    dup_ids = sorted({i for i in ids if ids.count(i) > 1})

    locators = set()
    missing_url, missing_geo, missing_sigma = [], [], []
    for x in items:
        loc = extract_locators(x.get("citation", ""), x.get("source_url", ""))
        key = loc["doi"] or loc["arxiv"] or loc["public_url"]
        if key:
            locators.add(key)
        else:
            missing_url.append(x["id"])
        if not (x.get("geometry") or {}):
            missing_geo.append(x["id"])
        if x.get("uncertainty_abs") in (None, ""):
            missing_sigma.append(x["id"])

    rows = run_comparisons(seed_path)
    ok_rows = [r for r in rows if r.get("ok")]
    counted = [r for r in ok_rows if r["kind"] != "calibration_anchor"]
    independent = [r for r in ok_rows if r["kind"] == "independent"]
    rels = sorted(r["rel_pct"] for r in counted)
    median = rels[len(rels) // 2] if rels else None

    return {
        "corpus_total": len(items),
        "ids_unique": not dup_ids,
        "duplicate_ids": dup_ids,
        "by_tier": prov["by_tier"],
        "traceable_ratio": round(prov["traceable_ratio"], 4),
        "distinct_locators": len(locators),
        "missing_locator": missing_url,
        "missing_geometry": missing_geo,
        "missing_sigma": missing_sigma,
        "comparisons_total": len(ok_rows),
        "comparisons_counted": len(counted),
        "comparisons_independent": len(independent),
        "comparisons_cross": sum(1 for r in ok_rows
                                 if r["kind"] == "cross_measurement"),
        "comparisons_calibration": sum(1 for r in ok_rows
                                       if r["kind"] == "calibration_anchor"),
        "comparison_errors": [(r["id"], r.get("error")) for r in rows
                              if not r.get("ok")],
        "rel_median_pct": median,
        "rel_max_pct": rels[-1] if rels else None,
        "n_within_25": sum(1 for r in counted if r["rel_pct"] <= 25.0),
        "rows": rows,
        "targets": {"corpus_min": M6_CORPUS_MIN,
                    "comparison_min": M6_COMPARISON_MIN,
                    "independent_min": M6_INDEPENDENT_MIN,
                    "distinct_locator_min": M6_DISTINCT_LOCATOR_MIN,
                    "median_rel_max": M6_MEDIAN_REL_MAX,
                    "within_25_min": M6_WITHIN_25_MIN},
    }


def gate_m6(rep: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把审计结果转成判据列表（`{"name", "ok", "detail"}`），供 smoke/pytest 共用。"""
    t = rep["targets"]
    return [
        {"name": f"M6-1 语料入库数 ≥ {t['corpus_min']}（A 级实证锚）",
         "ok": rep["corpus_total"] >= t["corpus_min"],
         "detail": f"corpus={rep['corpus_total']}"},
        {"name": "M6-2 语料 id 唯一（无重复计入）",
         "ok": rep["ids_unique"],
         "detail": f"dupes={rep['duplicate_ids']}"},
        {"name": "M6-3 全库 A 级可公开溯源（B/X 级零容忍）",
         "ok": rep["traceable_ratio"] >= 1.0,
         "detail": f"A={rep['by_tier']['A']} B={rep['by_tier']['B']} "
                   f"X={rep['by_tier']['X']} 占比={rep['traceable_ratio']*100:.1f}%"},
        {"name": f"M6-4 公开定位符去重数 ≥ {t['distinct_locator_min']}"
                 "（防一个 URL 灌多条刷条数）",
         "ok": rep["distinct_locators"] >= t["distinct_locator_min"],
         "detail": f"distinct={rep['distinct_locators']} 缺定位符={rep['missing_locator']}"},
        {"name": "M6-5 每条带 geometry（对照可复算的前提）",
         "ok": not rep["missing_geometry"],
         "detail": f"缺 geometry：{rep['missing_geometry']}"},
        {"name": "M6-6 每条带 σ（不确定度）",
         "ok": not rep["missing_sigma"],
         "detail": f"缺 σ：{rep['missing_sigma']}"},
        {"name": f"M6-7 实测对照数 ≥ {t['comparison_min']}"
                 "（independent + cross_measurement；标定锚不计）",
         "ok": rep["comparisons_counted"] >= t["comparison_min"],
         "detail": f"计入={rep['comparisons_counted']}（独立 "
                   f"{rep['comparisons_independent']} + 跨器件 "
                   f"{rep['comparisons_cross']}）；标定锚 "
                   f"{rep['comparisons_calibration']} 条不计"},
        {"name": f"M6-8 其中 independent 档 ≥ {t['independent_min']}"
                 "（防全用跨器件一致性凑数）",
         "ok": rep["comparisons_independent"] >= t["independent_min"],
         "detail": f"independent={rep['comparisons_independent']}"},
        {"name": "M6-9 全部登记对照均可执行（无 error 行）",
         "ok": not rep["comparison_errors"],
         "detail": f"errors={rep['comparison_errors']}"},
        {"name": f"M6-10 对照质量地板：rel 中位数 ≤ {t['median_rel_max']}%"
                 f" 且 rel ≤25% 的条数 ≥ {t['within_25_min']}",
         "ok": (rep["rel_median_pct"] is not None
                and rep["rel_median_pct"] <= t["median_rel_max"]
                and rep["n_within_25"] >= t["within_25_min"]),
         "detail": f"median={rep['rel_median_pct']}% max={rep['rel_max_pct']}% "
                   f"≤25% 者 {rep['n_within_25']}/{rep['comparisons_counted']}"},
    ]


if __name__ == "__main__":  # 手动体检：打印 M6 全表
    _rep = audit_m6()
    print("=" * 74)
    print(f"M6 审计：语料 {_rep['corpus_total']} 条 · 对照 {_rep['comparisons_counted']} 条"
          f"（独立 {_rep['comparisons_independent']} / 跨器件 {_rep['comparisons_cross']}"
          f" / 标定锚 {_rep['comparisons_calibration']}）")
    print("-" * 74)
    for _r in _rep["rows"]:
        if _r.get("ok"):
            print(f"  [{_r['kind']:<18}] {_r['id']:<18} {_r['metric']:<22} "
                  f"实测={_r['measured']:<12g} 算得={_r['computed']:<12g} "
                  f"rel={_r['rel_pct']:>7.2f}%")
        else:
            print(f"  [ERROR             ] {_r['id']:<18} {_r.get('error')}")
    print("-" * 74)
    for _c in gate_m6(_rep):
        print(f"  [{'PASS' if _c['ok'] else 'FAIL'}] {_c['name']} — {_c['detail']}")
