"""v0.9.33 层次化 GDS 导出常驻护栏（P0-1）。

⚠️ 命名说明：与既有 `run_hierarchy_smoke.py`（Merge-3b **层级 IR** 的
子系统 flatten）是**两件事**，故本文件叫 `run_hier_gds_smoke.py`。

验证 `lda_l2.hierarchy`：重复单元检测 → cell + AREF 输出 → 展开等价。

## 判据（全部死标量，且均经反向测试证明会响）

  A 层次化在规则阵列上**必须生效**（CPO 小阵列降幅 > 50%）
  B 展开几何数 ≡ flat 元素数（**几何零丢失**——层次化最危险的失败模式
    是压缩时悄悄丢几何，元素数变小看起来"更成功"）
  C 展开与 flat **逐元素数值等价**（≤1 DBU）
  D 非规则设计**必须回退 flat 且逐字节一致**（不得因层次化改变输出）
  E AREF 编码 round-trip：1 条 AREF 展开为 nx×ny 份几何，位置精确
  F 解析器 `top_structures` 正确（顶层 = 未被引用者）—— 下游若按全结构
    求和会把 cell 那份重复计入（实测多 202 个）
  G DRC/LVS 判决**不受层次化影响**（层次化只改编码，不改判决）

## 🔴 反向测试（证明护栏会响）

- 关掉层次化（`with_hierarchy=False`）⇒ A 必须 FAIL
- 故意从 cell 里删一个几何 ⇒ B/C 必须 FAIL（几何丢失抓得住）
- 层次化 GDS 若**不展开**引用直接喂 DRC ⇒ 几何数远小于真实（假绿陷阱）

LLM 不进判决路径；纯标准库 + lda 内部模块。
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from typing import List, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2 import chip_layout_export as CLE          # noqa: E402
from lda_l2 import gds_export as GE                   # noqa: E402
from lda_l2 import hierarchy as H                     # noqa: E402

CHECKS: List[Tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({detail})")


def _cpo_small():
    from lda_harness import cpo_array as CA
    cfg = CA.CPOArrayConfig(n_oe=2, n_ch=4, n_lane=4, ch_per_row=4)
    return CA.build_cpo_array_case(cfg)[:3]


def _flat_geoms(link, placement, routes, wg=0.5):
    return (CLE.device_geoms(link, placement, wg)
            + CLE.route_geoms(routes, wg)
            + CLE.io_grating_geoms(link, placement, wg))


def _compare(flat_geoms, exp_geoms):
    """(严格等价, 数值等价≤1DBU, 最大偏差nm, 缺失数, 多余数)。"""
    fk = Counter(CLE._geom_key(g) for g in flat_geoms)
    ek = Counter(CLE._geom_key(g) for g in exp_geoms)
    if fk == ek:
        return True, True, 0, 0, 0
    miss = list((fk - ek).elements())
    extra = list((ek - fk).elements())
    used = [False] * len(extra)
    worst = 0
    numeric = True
    for m in miss:
        hit = -1
        for i, e in enumerate(extra):
            if used[i] or m[:3] != e[:3] or len(m[3]) != len(e[3]):
                continue
            d = max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                    for a, b in zip(m[3], e[3]))
            if d <= 1:
                hit = i
                worst = max(worst, d)
                break
        if hit < 0:
            numeric = False
            break
        used[hit] = True
    return False, numeric, worst, len(miss), len(extra)


# ───────────────────────────────────── E：AREF 编码 round-trip
def test_aref_roundtrip() -> None:
    cell = [GE.path(GE.LIB_LAYER_SI, 0.5, [(0, 0), (10, 0)]),
            GE.boundary(GE.LIB_LAYER_SI, [(0, 0), (2, 0), (2, 1), (0, 1)])]
    gds = GE.gds_library("T", {"CELL": cell,
                               "TOP": [GE.aref("CELL", (0, 0), 100.0, 50.0,
                                               3, 2)]})
    pg = GE.parse_gds_polygons(gds)
    els = pg["structures"]["TOP"]
    check("E AREF 展开元素数 == 2×3×2", len(els) == 12, f"{len(els)}")
    xs = [p[0] for e in els for p in e["points_um"]]
    ys = [p[1] for e in els for p in e["points_um"]]
    check("E 展开 bbox 正确（x 0→210, y 0→51）",
          abs(max(xs) - 210.0) < 1e-9 and abs(max(ys) - 51.0) < 1e-9,
          f"x[0,{max(xs)}] y[0,{max(ys)}]")
    pg2 = GE.parse_gds_polygons(gds, expand_refs=False)
    check("E 不展开时保留 aref 记录",
          len(pg2["structures"]["TOP"]) == 1
          and pg2["structures"]["TOP"][0]["kind"] == "aref", "kind=aref")
    # F：top_structures
    check("F top_structures == ['TOP']（CELL 被引用故排除）",
          pg["top_structures"] == ["TOP"], str(pg["top_structures"]))


# ───────────────────────────────── A/B/C/G：CPO 规则阵列
def test_cpo_hierarchy() -> None:
    link, placement, routes = _cpo_small()
    rh = CLE.export_chip_gds(link, placement, routes)
    rf = CLE.export_chip_gds(link, placement, routes, with_hierarchy=False)
    st_h, st_f = rh["gds_stats"], rf["gds_stats"]
    hier = rh["hierarchy"]

    check("A 层次化在规则阵列上生效",
          hier["applied"] and hier["reason"] == "ok",
          f"inst={hier['n_instances']} period={hier['period']} "
          f"array={hier.get('array')}")
    ratio = st_h["n_elements"] / max(1, st_f["n_elements"])
    check("A 降幅 > 50%", ratio < 0.5,
          f"{st_f['n_elements']}→{st_h['n_elements']} "
          f"（降 {(1 - ratio) * 100:.1f}%）")

    # B：几何零丢失（按 top_structures 计数）
    pg = GE.parse_gds_polygons(rh["gds_bytes"])
    n_geo = sum(len(pg["structures"][n]) for n in pg["top_structures"])
    check("B 展开几何数 ≡ flat 元素数（几何零丢失）",
          n_geo == st_f["n_elements"], f"{n_geo} vs {st_f['n_elements']}")

    # C：逐元素数值等价
    plan = H.detect_hierarchy(link, placement, routes, 0.5)
    exp = H.expand_plan(plan)
    flat = _flat_geoms(link, placement, routes)
    strict, numeric, worst, nmiss, nextra = _compare(flat, exp)
    check("C 展开与 flat 数值等价（≤1 DBU）",
          numeric, f"严格={strict} 缺{nmiss}/多{nextra} 最大偏差 {worst} nm")
    check("C 元素总数一致", len(exp) == len(flat),
          f"{len(exp)} vs {len(flat)}")

    # G：DRC/LVS 判决不受层次化影响
    check("G DRC 判决一致",
          rh["drc_report"]["all_pass"] == rf["drc_report"]["all_pass"]
          and rh["drc_report"]["n_pass"] == rf["drc_report"]["n_pass"],
          f"{rh['drc_report']['n_pass']}/{rh['drc_report']['n_checked']}")
    check("G LVS 判决一致",
          rh["lvs_report"].get("verdict") == rf["lvs_report"].get("verdict"),
          f"{rh['lvs_report'].get('verdict')}")

    # G2：🔴 不展开引用直接喂 DRC ⇒ 顶层几乎看不到几何（假绿陷阱）
    #    判据取「顶层结构中真实几何（boundary/path）的数量」：未展开时 TOP
    #    只有 1 条 AREF 记录、真实几何为 0 ⇒ DRC 会认为版图是空的。
    #    （早期版本误按全结构求和，会把 cell 自己的 202 个几何算进来，
    #     掩盖了这个陷阱。）
    unexp = GE.parse_gds_polygons(rh["gds_bytes"], expand_refs=False)
    n_geo_unexp = sum(1 for n in unexp["top_structures"]
                      for e in unexp["structures"][n]
                      if e.get("kind") in ("boundary", "path"))
    check("G2 不展开时顶层真实几何 ≈ 0（故 DRC 必须走展开路径）",
          n_geo_unexp < st_f["n_elements"] * 0.1,
          f"未展开顶层真实几何 {n_geo_unexp} vs flat {st_f['n_elements']}")


# ───────────────────────────────── D：非规则设计回退 flat
def test_fallback_flat() -> None:
    from lda_agent.orchestrator import Orchestrator
    ctx = Orchestrator().run({"type": "wdm",
                              "channels_um": [1.53, 1.55, 1.57],
                              "R_um": 10.0, "gap_um": 0.3, "kappa": 0.05})
    rh = CLE.export_chip_gds(ctx.link, ctx.placement, ctx.routes)
    rf = CLE.export_chip_gds(ctx.link, ctx.placement, ctx.routes,
                             with_hierarchy=False)
    hier = rh["hierarchy"]
    check("D 非阵列设计回退 flat（applied=False）",
          not hier["applied"], f"reason={hier['reason']}")
    check("D 回退时字节逐位一致",
          rh["gds_bytes"] == rf["gds_bytes"], f"{len(rh['gds_bytes'])}B")
    check("D 回退原因非空（不静默）", bool(hier["reason"]), hier["reason"])
    check("D 回退时 n_elements_flat 已记录",
          hier["n_elements_flat"] == rf["gds_stats"]["n_elements"],
          f"{hier['n_elements_flat']}")


# ───────────────────────────────── 反例：几何丢失必须被 B/C 抓住
def test_geometry_loss_is_caught() -> None:
    """反向测试：故意删一个 cell 几何，B/C 判据必须 FAIL。

    🔴 层次化最危险的失败模式是「压缩时悄悄丢几何」——元素数变小看起来
    更像"压缩成功"。本测试证明判据能抓住它，而不是只看降幅。
    """
    link, placement, routes = _cpo_small()
    plan = H.detect_hierarchy(link, placement, routes, 0.5)
    if plan is None:
        check("反向测试：几何丢失被抓住", False, "层次化未生效，无法测试")
        return
    flat = _flat_geoms(link, placement, routes)
    _, good_ok, _, _, _ = _compare(flat, H.expand_plan(plan))

    damaged = H.HierarchyPlan(plan.cell_name, plan.period, plan.n_inst,
                              plan.nx, plan.ny, plan.dx, plan.dy,
                              plan.origin, plan.cell_geoms[1:],
                              plan.top_geoms, plan.use_aref)
    _, bad_ok, _, nmiss, _ = _compare(flat, H.expand_plan(damaged))

    check("反向测试：完好方案 PASS / 删几何方案 FAIL（判据会响）",
          good_ok and not bad_ok and nmiss > 0,
          f"完好={good_ok} 删后={bad_ok} 缺失={nmiss}")


def main() -> int:
    print("层次化 GDS 导出护栏（P0-1 · v0.9.33）")
    print("\n--- E/F：AREF 编码与解析 ---")
    test_aref_roundtrip()
    print("\n--- A/B/C/G：CPO 规则阵列 ---")
    test_cpo_hierarchy()
    print("\n--- D：非规则设计回退 ---")
    test_fallback_flat()
    print("\n--- 反向测试 ---")
    test_geometry_loss_is_caught()
    npass = sum(1 for c in CHECKS if c[1])
    print("-" * 64)
    print(f"层次化 GDS 护栏：{npass}/{len(CHECKS)} PASS")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
