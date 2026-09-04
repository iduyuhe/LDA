"""v0.9.2 CPO 阵列规模纵深守护（阶段2 · 25 万级真实器件样例）。

把阶段2 生成器推到 **250,240 器件（2.5× 默认 100,096）** 实跑全链，
守护「十万级不是运气、规模墙真的没了」——任何把阵列构建/放置/布线/
DRC/LVS 退化回 O(n²) 的改动都会让总耗时越过预算，CI 立刻红。

与 `run_cpo_array_smoke.py`（秒级小样，11 断言）分工：
  - smoke  ：正确性 + 物理自洽 + 几何策略 + 红线（快，CI 秒级）
  - scale  ：规模纵深 + 近线性预算守卫（慢，~25s，守回归）

运行：python run_cpo_array_scale_smoke.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.cpo_array import (CPOArrayConfig, build_cpo_array_case,
                                   inject_fault)
from lda_l2.chip_layout_export import chip_drc_report, export_chip_gds
from lda_l2.lvs import run_lvs

# 规模配置：40 引擎 × 68 通道 × 8 波长 = 250,240 器件 / 5,440 光路
SCALE_OE = 40
SCALE_CH = 68
SCALE_LANE = 8
SCALE_CH_PER_ROW = 4
TOTAL_BUDGET_SEC = 60.0   # 近线性守卫：慢机 2× 缓冲仍远低于此

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main() -> int:
    cfg = CPOArrayConfig(n_oe=SCALE_OE, n_ch=SCALE_CH, n_lane=SCALE_LANE,
                         ch_per_row=SCALE_CH_PER_ROW)
    cfg.validate()
    expect = cfg.n_devices
    print(f"CPO 阵列规模纵深守护（{cfg.n_oe} 引擎 × {cfg.n_ch} 通道 × "
          f"{cfg.n_lane} 波长 = {expect:,} 器件 / {2 * cfg.n_channels:,} 光路）")

    t_start = time.perf_counter()

    # ① 构建 + 放置 + 布线
    link, placement, routes, meta = build_cpo_array_case(cfg)
    t_build = time.perf_counter() - t_start
    check("① 器件数 = 配置推导值（死标量）",
          len(link.ir.components) == expect == meta["n_devices"],
          f"{len(link.ir.components):,} == {expect:,}")
    check("① 光路数 = 2 × 通道数（每通道 1 发 1 收）",
          meta["n_chains"] == 2 * cfg.n_channels,
          f"{meta['n_chains']:,} == {2 * cfg.n_channels:,}")
    n_route = len(routes)
    check("① 布线网 = 器件 − 光路（链内串行）",
          n_route == expect - meta["n_chains"],
          f"{n_route:,} == {expect:,} - {meta['n_chains']:,}")
    check("① 几何：全部行内连接为水平段（端口线对齐 · 零回折）",
          sum(1 for rr in routes.values()
              if abs(rr.points_um[0][1] - rr.points_um[-1][1]) > 1e-6) == 0,
          f"非水平 0/{n_route:,}")
    print(f"  [计时] 构建+放置+布线: {t_build:.2f}s")

    # ② DRC（全器件可制造性）
    t0 = time.perf_counter()
    drc = chip_drc_report(link, placement)
    t_drc = time.perf_counter() - t0
    check("② DRC：全部器件通过（死标量）",
          drc["all_pass"] and drc["n_pass"] == expect,
          f"{drc['n_pass']:,}/{drc['n_checked']:,}")
    print(f"  [计时] DRC: {t_drc:.2f}s")

    # ③ LVS 正例（版图-原理图一致）
    t0 = time.perf_counter()
    lvs = run_lvs(link, placement, routes)
    t_lvs = time.perf_counter() - t0
    nm = lvs["match"]
    check("③ LVS：正例 ACCEPT（0 违规）",
          lvs["verdict"] == "ACCEPT" and lvs["n_violations"] == 0,
          f"{lvs['verdict']} viol={lvs['n_violations']}")
    check("③ LVS：网表全匹配（布线网全覆盖）",
          nm["n_nets_match"] == nm["n_nets_total"] == n_route,
          f"{nm['n_nets_match']:,}/{nm['n_nets_total']:,}")
    print(f"  [计时] LVS: {t_lvs:.2f}s")

    # ④ GDS 导出
    t0 = time.perf_counter()
    g = export_chip_gds(link, placement, routes)
    st = g["gds_stats"]
    t_gds = time.perf_counter() - t0
    # 🔴 v0.9.33 断言语义修正：层次化后 `n_elements` 是**压缩后**的编码元素数
    #    （250k 器件 → 331），不再 ≥ 器件数。原断言隐含 flat 假设，必然假红。
    #    改为按 **展开后的几何数** 判决（flat 与层次化同一判据）。
    from lda_l2.gds_export import parse_gds_polygons
    pg = parse_gds_polygons(g["gds_bytes"])
    n_geo = sum(len(pg["structures"][n]) for n in pg["top_structures"])
    check("④ GDS round-trip 可解析（按展开几何计数，兼容层次化）",
          isinstance(g["gds_parse"], dict)
          and g["gds_parse"].get("n_structures", 0) >= 1
          and n_geo >= expect,
          f"struct={st.get('n_structures')} 编码元素={st['n_elements']:,} "
          f"展开几何={n_geo:,}")
    # ④b 层次化降幅守护：250k 是收益最大的场景（99.96%），必须守住
    n_flat_elem = g["hierarchy"].get("n_elements_flat") or expect
    if g["hierarchy"]["applied"]:
        check("④b 层次化降幅 > 99%（250k 器件）",
              st["n_elements"] < n_flat_elem * 0.01,
              f"{st['n_elements']:,} vs flat {n_flat_elem:,} "
              f"（降 {(1 - st['n_elements'] / n_flat_elem) * 100:.2f}%）")
    else:
        check("④b 层次化未触发时元素数 ≡ flat",
              st["n_elements"] == n_flat_elem,
              f"reason={g['hierarchy']['reason']}")
    print(f"  [计时] GDS: {t_gds:.2f}s "
          f"({st['gds_bytes'] / 1e6:.1f} MB / {st['n_elements']:,} 元素)")

    # ⑤ 反例：注入断路 → 必须 REJECT
    r_dis = dict(routes)
    inject_fault(r_dis, "disconnect")
    lvs_dis = run_lvs(link, placement, r_dis)
    check("⑤ 反例-断路：REJECT（判决抓得住）",
          lvs_dis["verdict"] == "REJECT", f"{lvs_dis['verdict']}")

    # ⑥ 近线性预算守卫（O(n²) 回归会爆预算）
    t_total = time.perf_counter() - t_start
    check(f"⑥ 规模墙守护：25 万全链 ≤ {TOTAL_BUDGET_SEC:.0f}s（近线性，"
          f"非 O(n²)）",
          t_total <= TOTAL_BUDGET_SEC,
          f"全链 {t_total:.2f}s（构建 {t_build:.2f} / DRC {t_drc:.2f} / "
          f"LVS {t_lvs:.2f} / GDS {t_gds:.2f}）")

    print(f"\nCPO 阵列规模纵深守护：{_PASS} PASS / {_FAIL} FAIL · "
          f"25 万全链 {t_total:.2f}s")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
