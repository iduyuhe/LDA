"""D-216 突变探针（scratch · 不入 CI）：证明 run_schip_case_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1 `run_selfchecks` 恒回 False              ⇒ A1 应红（**本条是 F-1 的修复证明：
       门禁真的在跑自检，而不是只 import 了它**）
  · M2 `capacity_closed_form` 的 n_couplings 改错 ⇒ X1 应红（闭式对拍）
  · M3 `heavy_hex_closed_form` 回 90 比特        ⇒ X2 应红（跨源两条引擎对拍）
  · M4 拓扑内核 `max_degree` 改 4（错构型）       ⇒ X3 应红（防 4 邻居）
  · M5 `case_card` verdict 改成 DESIGN_PASS      ⇒ H1 应红（诚实边界）
  · M6 `scale_tiers.note` 去掉「版图容量」        ⇒ H2 应红（规模口径）
🔴 教训：patch 必须打门禁同一模块对象；门禁内以 `SC.foo(...)` 属性访问，故可命中。
   另：给"自检型"门禁配 M1 这类突变是必须的 —— 否则「A1 恒 True」与「A1 真在跑」
   在输出上完全无法区分。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_schip_case_smoke as S        # noqa: E402
from lda_webui import schip_case as SC  # noqa: E402


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    return rc, buf.getvalue().count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _self = SC.run_selfchecks
    _cap = SC.capacity_closed_form
    _hh = SC.heavy_hex_closed_form
    _card = SC.case_card

    SC.run_selfchecks = lambda verbose=False: False
    rows.append(("M1 run_selfchecks 恒 False", *run_smoke()))
    SC.run_selfchecks = _self

    def _cap_bad(rows, cols, **kw):
        out = dict(_cap(rows, cols, **kw))
        out["n_couplings"] = out["n_couplings"] + 1
        return out

    SC.capacity_closed_form = _cap_bad
    rows.append(("M2 capacity_closed_form 耦合数 +1", *run_smoke()))
    SC.capacity_closed_form = _cap

    def _hh_bad(rows, cols):
        out = dict(_hh(rows, cols))
        out["n_qubits"] = out["n_qubits"] - 1
        return out

    SC.heavy_hex_closed_form = _hh_bad
    rows.append(("M3 heavy_hex_closed_form 比特数 −1（跨源失配）", *run_smoke()))
    SC.heavy_hex_closed_form = _hh

    from lda_qeda import sc_topology_core as TC
    _stats = TC.topology_degree_stats

    def _stats_bad(topo):
        out = dict(_stats(topo))
        out["max_degree"] = 4
        out["no_four_neighbor"] = False
        return out

    TC.topology_degree_stats = _stats_bad
    rows.append(("M4 拓扑内核 max_degree=4（错构型）", *run_smoke()))
    TC.topology_degree_stats = _stats

    def _card_bad(repo_root=None):
        c = dict(_card(repo_root))
        c["verdict"] = "DESIGN_PASS"
        c["verdict_label"] = "签核通过"
        return c

    SC.case_card = _card_bad
    rows.append(("M5 verdict 改 DESIGN_PASS（伪装实测）", *run_smoke()))
    SC.case_card = _card

    def _card_note(repo_root=None):
        c = dict(_card(repo_root))
        st = dict(c["scale_tiers"])
        st["note"] = "规模 = 1024 比特（已制备）"
        c["scale_tiers"] = st
        return c

    SC.case_card = _card_note
    rows.append(("M6 规模口径去掉「版图容量」", *run_smoke()))
    SC.case_card = _card

    print("=" * 78)
    bad = 0
    for name, rc, nfail in rows:
        good = (rc == 0 and nfail == 0) if name.startswith("baseline") else (rc != 0 and nfail > 0)
        if not good:
            bad += 1
        print("%-6s %-50s rc=%-3d FAIL=%d" % ("[OK]" if good else "[BAD]", name, rc, nfail))
    print("=" * 78)
    print("突变探针：%d 条，%d 条未按预期变红" % (len(rows) - 1, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
