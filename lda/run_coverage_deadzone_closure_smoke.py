"""覆盖死角闭合护栏 smoke（v0.9.51 · 任务②corpus 失真区升格在前；本护栏源于 v0.9.50 任务①：补锚题覆盖死角）。

把「PhaseShifter / 4 个包」的覆盖死角收口从「文档散文」变成**机器可验证的死标量断言**：

  · B29（热光相移）已在 BENCHMARK_ORDER 且 strict ⇒ PhaseShifter 引擎覆盖闭合
  · B30（读出保真度）已在 BENCHMARK_ORDER 且 strict ⇒ readout_fidelity 包覆盖闭合
  · 3 个装配级弱复合包（mixed_system / wdm_coupler / splitter_readout）的组成器件严格锚
    （B14/B4/B22/B26）均在位 + S 层系统锚（S1-S13）在位 + GC-* 整芯片对标覆盖
    link / quantum_fidelity 系统类型 ⇒ 稀疏是装配级预期，非真死角
  · 零覆盖集恰为这 3 个复合包（PhaseShifter / readout_fidelity 已不再零覆盖）
  · 🔴 反向：撤掉 B29 后 phaseshifter 必须重新落入零覆盖集（护栏会响）

运行：python run_coverage_deadzone_closure_smoke.py（~2s，无重依赖）
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" —— {detail}" if detail else ""))


def _hosts_of(kind: str, kind_anchors: dict) -> set:
    return set(kind_anchors.get(kind, {}).keys())


def main() -> int:
    print("=" * 72)
    print("覆盖死角闭合护栏（PhaseShifter / readout_fidelity / 3 复合包）")
    print("=" * 72)

    from lda_harness.benchmarks import BENCHMARK_ORDER, BENCHMARK_DEFS
    from lda_harness.verification_adapters import BENCHMARK_CANDIDATES as CAND
    import run_anchor_coverage_matrix as m

    strict = {b for b in BENCHMARK_ORDER
               if BENCHMARK_DEFS[b].get("candidate") in CAND}
    kind_anchors = m.build_kind_anchors()

    # ------------------------------------------------ ① B29/B30 真·已接线
    for aid, cand_key, host in (
        ("B29", "thermal_phase_fdm", "engine_phaseshifter"),
        ("B30", "readout_fidelity_quad", "readout_fidelity"),
    ):
        present = aid in BENCHMARK_ORDER
        is_strict = aid in strict
        hosted = aid in _hosts_of(host, kind_anchors)
        check(f"{aid} 在 BENCHMARK_ORDER 且 strict（candidate={cand_key}）",
              present and is_strict,
              "present=%s strict=%s" % (present, is_strict))
        check(f"{aid} 已登记宿主 → {host}", hosted,
              "hosts=%s" % sorted(_hosts_of(host, kind_anchors)))

    # ------------------------------------------------ ② 3 复合包组成严格锚在位
    for aid in ("B4", "B14", "B22", "B26"):
        check(f"组成严格锚 {aid} 在 BENCHMARK_ORDER 且 strict",
              aid in strict, "strict=%s" % (aid in strict))
    for s in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
              "S9", "S10", "S11", "S12", "S13"):
        check(f"系统层锚 {s} 在 BENCHMARK_ORDER", s in BENCHMARK_ORDER,
              "present=%s" % (s in BENCHMARK_ORDER))

    # ------------------------------------------------ ③ GC-* 整芯片对标覆盖
    from lda_l2.golden_product_benchmarks import DEFAULT_CHIP_BENCHMARKS
    # GC-* 整芯片对标条目即 ChipBenchmark（含 system_type 字段）；GP-* 为 ProductBenchmark 无该字段
    gc_types = {b.system_type for b in DEFAULT_CHIP_BENCHMARKS}
    check("GC-* 覆盖 system_type=link", "link" in gc_types,
          "types=%s" % sorted(gc_types))
    check("GC-* 覆盖 system_type=quantum_fidelity", "quantum_fidelity" in gc_types,
          "types=%s" % sorted(gc_types))

    # ------------------------------------------------ ④ 零覆盖集恰为 3 复合包
    zc = m.compute_zero_coverage()
    expected = ["mixed_system", "wdm_coupler", "splitter_readout"]
    check("零覆盖集恰为 3 个装配级复合包", zc == expected,
          "actual=%s" % zc)
    check("PhaseShifter 已不再零覆盖（B29 生效）",
          "engine_phaseshifter" not in zc, "zc=%s" % zc)
    check("readout_fidelity 已不再零覆盖（B30 生效）",
          "readout_fidelity" not in zc, "zc=%s" % zc)

    # ------------------------------------------------ ⑤ 🔴 反向：撤 B29 必回落
    # 复刻 build_kind_anchors 的轻量分组（仅读注册表，非候选数学），验证守卫脆弱性
    modified = {k: list(v) for k, v in m.ANCHOR_HOSTS.items() if k != "B29"}
    ka2 = {}
    for aid, hostlist in modified.items():
        for host in hostlist:
            if host[0] in m.PSEUDO:
                continue
            ka2.setdefault(host[0], {})[aid] = ka2.get(host[0], {}).get(aid, []) + [host[1]]
    eng_rows, pkg_rows = [], []
    for dom in m._DOMAIN_ORDER:
        for k in m.ENGINE_KINDS:
            if m.ENGINE_DOMAIN[m.ENGINE_KIND_MAP[k]] == dom:
                eng_rows.append(k)
    pkg_rows = list(m.PACKAGE_KINDS)
    rows = [(k, "engine") for k in eng_rows] + [(k, "package") for k in pkg_rows]
    zc2 = [k for (k, _t) in rows if not ka2.get(k)]
    check("🔴 反向：撤 B29 后 phaseshifter 必重新落入零覆盖",
          "engine_phaseshifter" in zc2, "zc_without_B29=%s" % zc2)

    print("=" * 72)
    if FAIL:
        print(f"覆盖死角闭合护栏：{PASS} PASS / {FAIL} FAIL —— 🔴 收口回退")
        return 1
    print(f"覆盖死角闭合护栏：{PASS} PASS / 0 FAIL —— 全绿（5 类死角已闭合）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
