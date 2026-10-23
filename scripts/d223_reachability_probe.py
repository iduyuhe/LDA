"""D-223 突变探针（scratch · 不入 CI）：证明 run_reachability_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1  分析器恒返回空死集（假装天下无死函数）        ⇒ R1/R2/Z3 应红
  · M2  分析器把 golden_fn 对象入口丢掉（只扫字符串）   ⇒ R1（多判 ~5 个）+ Z4 应红
  · M3  分析器把模块级引用入口丢掉（路由表假阳性回归）  ⇒ R1（多判 150 个）应红
  · M4  基线删一条（模拟"修好了没删登记"的反面）        ⇒ R1（新增 1）应红
  · M5  基线伪增一条（模拟"登记了不存在的"）            ⇒ R1（消失 1）应红
  · M6  某形态的说明文字清空                            ⇒ R3 应红
  · M7  MUST_BE_REACHABLE 挪掉 v0.9.271 的 bug 函数     ⇒ X2 应红（若该函数恰不可达）
  · M8  谎称可锚（ANCHORABLE=True）                     ⇒ Z2 应红

🔴 教训（D-219/D-221/D-222 同族）：patch 必须打在**门禁实际调用的模块对象**上
   （`lda_harness.reachability` 与 `lda_harness.reachability_registry` 的模块级名字）。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_reachability_smoke as S                 # noqa: E402
from lda_harness import reachability as R          # noqa: E402
from lda_harness import reachability_registry as REG  # noqa: E402


def run_smoke():
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                                     # noqa: BLE001
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    out = buf.getvalue()
    return rc, out.count("[FAIL]"), out


def main() -> int:
    rows = []

    rc, nf, _ = run_smoke()
    rows.append(("baseline（未突变）", rc, nf))

    _analyze = R.analyze
    _entries = R.anchor_entry_names
    _modlvl = R.module_level_ids
    _baseline = dict(REG.DEAD_BASELINE)
    _classes = dict(REG.DEAD_CLASSES)
    _must = list(REG.MUST_BE_REACHABLE)
    _r_anch = R.ANCHORABLE

    # ---------------- M1 恒返空死集 ----------------
    def _an_empty(*a, **k):
        r = _analyze(*a, **k)
        out = dict(r)
        out["dead"] = []
        out["by_module"] = {}
        out["stats"] = dict(r["stats"], dead_total=0, dead_pct=0.0, reachable_total=r["stats"]["public_total"])
        return out
    R.analyze = _an_empty
    rows.append(("M1 分析器恒返空死集", *run_smoke()[:2]))
    R.analyze = _analyze

    # ---------------- M2 丢掉 golden_fn 对象入口 ----------------
    def _entries_nogold(benchmarks):
        names, _gold = _entries(benchmarks)
        # 只保留字符串来源：把 golden_fn 的名字剔除
        _n2, gold = _entries(benchmarks)
        return names - gold, set()
    R.anchor_entry_names = _entries_nogold
    rows.append(("M2 丢掉 golden_fn 对象入口", *run_smoke()[:2]))
    R.anchor_entry_names = _entries

    # ---------------- M3 丢掉模块级引用入口 ----------------
    R.module_level_ids = lambda tree: set()                    # noqa: ARG005
    rows.append(("M3 丢掉模块级引用入口", *run_smoke()[:2]))
    R.module_level_ids = _modlvl

    # ---------------- M4 基线删一条 ----------------
    victim = sorted(_baseline)[0]
    REG.DEAD_BASELINE = {k: v for k, v in _baseline.items() if k != victim}
    rows.append(("M4 基线删一条（%s…）" % victim.split("::")[-1][:16], *run_smoke()[:2]))
    REG.DEAD_BASELINE = _baseline

    # ---------------- M5 基线伪增一条 ----------------
    REG.DEAD_BASELINE = dict(_baseline, **{
        "lda/lda_qeda/nonexistent_mod.py::phantom_fn": "PUBLIC_API_NO_CONSUMER"})
    rows.append(("M5 基线伪增一条", *run_smoke()[:2]))
    REG.DEAD_BASELINE = _baseline

    # ---------------- M6 清空某一类的说明 ----------------
    k0 = sorted(_classes)[0]
    REG.DEAD_CLASSES = dict(_classes, **{k0: ""})
    rows.append(("M6 清空某形态说明文字", *run_smoke()[:2]))
    REG.DEAD_CLASSES = _classes

    # ---------------- M7 挪掉 v0.9.271 的 bug 函数 ----------------
    REG.MUST_BE_REACHABLE = [k for k in _must
                             if not k.endswith("::resonator_freq_ghz")]
    rows.append(("M7 挪掉 MUST_BE 里的 bug 函数", *run_smoke()[:2]))
    REG.MUST_BE_REACHABLE = _must

    # ---------------- M8 谎称可锚 ----------------
    R.ANCHORABLE = True
    rows.append(("M8 谎称可锚（ANCHORABLE=True）", *run_smoke()[:2]))
    R.ANCHORABLE = _r_anch

    print("\n%-40s %4s %6s  %s" % ("突变", "rc", "FAIL", "结论"))
    ok = True
    for name, rc, nf in rows:
        if name.startswith("baseline"):
            good = (rc == 0 and nf == 0)
            verdict = "OK（全绿）" if good else "!! 基线应全绿"
        else:
            good = (rc != 0 and nf > 0)
            verdict = "咬住（%d 条红）" % nf if good else "!! 未咬住（假绿）"
        ok = ok and good
        print("%-40s %4s %6s  %s" % (name, rc, nf, verdict))
    print("\n探针结论：%s（%d/%d 突变被咬住）"
          % ("ALL_CAUGHT" if ok else "HAS_UNCAUGHT",
             sum(1 for n, r, f in rows if not n.startswith("baseline") and r != 0 and f > 0),
             len(rows) - 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
