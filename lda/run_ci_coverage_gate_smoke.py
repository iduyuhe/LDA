"""CI 门禁覆盖防漏 smoke（v0.9.41 · 血案驱动）。

防什么
------
`lda/` 下每个 `run_*_smoke.py` 必须**要么进 CI core 门禁、要么在豁免表里
写明理由**——除此之外即为「写了 smoke 却没接线」的静默缺口，本 smoke 判 FAIL。

血案（v0.9.41）
--------------
`run_production_smoke.py` 自 M3（v0.9.39）建成起从未进过任何回归集，而
设计文档 `lda_production_system_design.md`、`production_plan.py` 注释与项目
memory 三处均记载「进 CI 防回归」⇒ **研发生产系统四赛道 17 个任务长期裸奔，
坏了不响**。同批审计另查出 18 条「纯 numpy、<1.3s、失败会 return 1」的真门禁
同样从未接线，其中 4 条是**锚 smoke**（锚失真恰是最危险的失败模式）。

根因：`_discover_all()` 只负责发现，无人强制分类 ⇒ 漏接线成为静默默认。

判据（死标量，LLM 不进判决路径）
--------------------------------
  ① lda/ 下每个 run_*_smoke.py ∈ CORE_SMOKES ∪ NON_CORE_SMOKES
  ② NON_CORE_SMOKES 每项理由非空（禁止空洞豁免）
  ③ CORE_SMOKES 内不得有重复项
  ④ 本 smoke 自身必须在 CORE_SMOKES 内（自食其规则，防门禁自己被漏接）
  ⑤ 反向测试：临时移除一项登记 ⇒ 必须判 FAIL（护栏必须会响，不得纸上谈兵）

运行：python lda/run_ci_coverage_gate_smoke.py
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

import run_ci_regression as R  # noqa: E402

_SELF = "run_ci_coverage_gate_smoke.py"

CHECKS: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def _classify() -> tuple[List[str], List[str], List[str]]:
    """返回 (未登记项, 空洞理由项, core 重复项)。"""
    core: List[str] = list(R.CORE_SMOKES)
    noncore: Dict[str, str] = dict(getattr(R, "NON_CORE_SMOKES", {}))
    discovered = R._discover_all()

    core_set = set(core)
    orphans = [f for f in discovered if f not in core_set and f not in noncore]
    hollow = [f for f, why in noncore.items() if not str(why).strip()]
    dupes = sorted({f for f in core if core.count(f) > 1})
    return orphans, hollow, dupes


def main() -> int:
    print("=" * 74)
    print("CI 门禁覆盖防漏 smoke — 每个 smoke 必须在门禁内或显式豁免")
    print("=" * 74)

    discovered = R._discover_all()
    noncore = getattr(R, "NON_CORE_SMOKES", {})
    print(f"  发现 smoke = {len(discovered)} · core = {len(R.CORE_SMOKES)} "
          f"· 豁免 = {len(noncore)}")

    rc = 0

    # ① 未登记项（核心判据）
    orphans, hollow, dupes = _classify()
    rc |= not check("① 每个 run_*_smoke.py 均已登记（进 core 或豁免）",
                    not orphans,
                    f"未登记 {len(orphans)} 项 {orphans[:5]}" if orphans
                    else f"覆盖 {len(discovered)}/{len(discovered)}")

    # ② 豁免理由不得为空
    rc |= not check("② 豁免项均附非空理由（禁止空洞豁免）",
                    not hollow,
                    f"空洞 {hollow}" if hollow else f"{len(noncore)} 项理由齐备")

    # ③ core 内无重复
    rc |= not check("③ CORE_SMOKES 无重复项", not dupes,
                    f"重复 {dupes}" if dupes else "")

    # ④ 自食其规则：本 smoke 必须在 core 内
    rc |= not check("④ 本 smoke 自身在 CORE_SMOKES 内（自食其规则）",
                    _SELF in R.CORE_SMOKES,
                    "" if _SELF in R.CORE_SMOKES else "门禁自己被漏接！")

    # ⑤ 反向测试：护栏必须会响（铁律：没被验证过的护栏不算护栏）
    saved = R.CORE_SMOKES
    try:
        victim = "run_b30_readout_smoke.py"
        if victim in R.CORE_SMOKES:
            R.CORE_SMOKES = [f for f in R.CORE_SMOKES if f != victim]
            o2, _, _ = _classify()
            hit = victim in o2
            check("⑤ 反向测试：撤掉一项登记 ⇒ 判据必须报缺口",
                  hit, f"撤 {victim} → 报未登记 {len(o2)} 项")
            rc |= not hit
        else:
            rc |= not check("⑤ 反向测试：基准项存在", False, f"缺 {victim}")
    finally:
        R.CORE_SMOKES = saved

    # 收尾：恢复后必须重新全绿（防测试污染真实判据）
    o3, h3, d3 = _classify()
    rc |= not check("⑥ 反向测试后状态复原（测试不污染真判据）",
                    not o3 and not h3 and not d3, "")

    n_pass = sum(1 for c in CHECKS if c["ok"])
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {len(CHECKS) - n_pass} FAIL / 共 {len(CHECKS)} 项")
    if rc == 0:
        print("ALL PASS — 门禁无静默缺口（每个 smoke 都在门禁内或有书面豁免）")
    else:
        print("FAIL — 存在未接线 smoke，请补登 CORE_SMOKES 或在 NON_CORE_SMOKES 写明理由")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
