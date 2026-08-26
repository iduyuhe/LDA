"""v0.8.11d 芯片级版图导出增强 smoke：可测芯片版图三要素。

验证 `lda_l2/chip_layout_export`：
  1. IO 光栅耦合器接入：链路外部端口自动放置光栅齿区几何（GDS 显著增大、
     IO 端口清单正确）；
  2. 版图统计：器件/net/IO 数、bbox/面积、GDS 可 round-trip 解析；
  3. 芯片级 DRC：链路 RingResonator R 单位归一（mm→µm）后 3/3 全 PASS；
     正负例——合规版图 ACCEPT、违规参数（gap 过小）REJECT。

全部死标量（LLM 不进判决路径）；零依赖（纯标准库 + lda 内部模块）。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_agent.orchestrator import Orchestrator
from lda_l2.chip_layout_export import export_chip_gds

CHECKS = []


def check(name: str, ok: bool, detail: str = ""):
    CHECKS.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


def _run_wdm(gap_um: float = 0.3):
    spec = {"type": "wdm", "channels_um": [1.53, 1.55, 1.57],
            "R_um": 10.0, "gap_um": gap_um, "kappa": 0.05}
    ctx = Orchestrator().run(spec)
    return ctx


def main() -> int:
    # ① IO 光栅接入 + 版图统计（合规案例）
    ctx = _run_wdm()
    r = export_chip_gds(ctx.link, ctx.placement, ctx.routes)
    st = r["gds_stats"]
    check("IO 光栅接入：IO 端口 ≥ 2 且 GDS 含光栅齿区（体积显著）",
          st["n_io"] >= 2 and st["gds_bytes"] > 3000,
          f"IO={st['n_io']} gds={st['gds_bytes']}B")
    check("版图统计：器件/net/bbox/面积齐备",
          st["n_devices"] >= 1 and st["n_nets"] >= 1
          and len(st["bbox_um"]) == 4 and st["area_um2"] > 0,
          f"dev={st['n_devices']} net={st['n_nets']} area={st['area_um2']}µm²")
    check("GDS round-trip 可解析", isinstance(r["gds_parse"], dict)
          and r["gds_parse"].get("n_structures", 0) >= 1,
          str(r["gds_parse"])[:80])
    check("芯片级 DRC 合规案例全 PASS（R 单位归一 mm→µm）",
          r["drc_report"]["all_pass"] and r["drc_report"]["n_pass"] >= 1,
          f"{r['drc_report']['n_pass']}/{r['drc_report']['n_checked']}")
    check("IO 端口清单含源与汇", any(".drop" in p for p in r["io_ports"]),
          f"ports={r['io_ports']}")

    # ② 负例：gap 过小 → DRC 抓违规（min_space）
    ctx2 = _run_wdm(gap_um=0.05)
    r2 = export_chip_gds(ctx2.link, ctx2.placement, ctx2.routes)
    check("负例：gap=0.05µm 被 DRC 抓违规",
          not r2["drc_report"]["all_pass"],
          f"pass={r2['drc_report']['n_pass']}/{r2['drc_report']['n_checked']}")

    npass = sum(1 for c in CHECKS if c[1])
    print("-" * 60)
    print(f"芯片版图导出 smoke：{npass}/{len(CHECKS)} PASS")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
