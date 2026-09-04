"""CPO 250k 层次化导出全量验证（v0.9.33 · P0-1）。

验证三件事：
  ① 降幅：flat 897,600 元素 / 97.45 MB → 层次化应 ≈ 331 元素 / 36 KB
  ② 几何零丢失：展开后的几何数 ≡ flat 元素数
  ③ 抽样等价：随机抽若干实例，其展开几何与 flat 对应几何逐元素数值
     等价（≤1 DBU）—— 全量比对在 250k 上要 8s+，产品化改用抽样

跑法：python assess_p01_hierarchy_250k.py
"""
from __future__ import annotations

import random
import sys
import time
from collections import Counter

sys.path.insert(0, "D:/agent_LDA/lda")
sys.path.insert(0, "D:/agent_LDA/lda/lda_harness")

from lda_harness import cpo_array as CA                      # noqa: E402
from lda_l2 import chip_layout_export as CLE                 # noqa: E402
from lda_l2 import hierarchy as H                            # noqa: E402
from lda_l2.gds_export import parse_gds_polygons             # noqa: E402

BASE_ELEMENTS = 897_600
BASE_BYTES = 97.45e6


def main() -> int:
    cfg = CA.CPOArrayConfig(n_oe=40, n_ch=68, n_lane=8)
    t0 = time.time()
    link, placement, routes, _meta = CA.build_cpo_array_case(cfg)
    print(f"构建 {len(link.ir.components):,} 器件 · {time.time() - t0:.1f}s",
          flush=True)

    # ── flat 基线
    t0 = time.time()
    rf = CLE.export_chip_gds(link, placement, routes, with_hierarchy=False)
    t_flat = time.time() - t0
    nf = rf["gds_stats"]["n_elements"]
    bf = rf["gds_stats"]["gds_bytes"]
    print(f"flat    {t_flat:6.2f}s · {nf:,} 元素 · {bf / 1e6:.2f} MB",
          flush=True)

    # ── 层次化
    t0 = time.time()
    rh = CLE.export_chip_gds(link, placement, routes)
    t_hier = time.time() - t0
    nh = rh["gds_stats"]["n_elements"]
    bh = rh["gds_stats"]["gds_bytes"]
    hier = rh["hierarchy"]
    print(f"层次化  {t_hier:6.2f}s · {nh:,} 元素 · {bh / 1e3:.1f} KB",
          flush=True)
    print(f"  {hier}", flush=True)

    ok = True

    # ① 降幅
    c1 = hier["applied"] and nh < 1000 and bh < 1e6
    ok &= c1
    print(f"\n[{'PASS' if c1 else 'FAIL'}] ① 降幅：{nf:,}→{nh:,} 元素 "
          f"（{(1 - nh / nf) * 100:.2f}%）· "
          f"{bf / 1e6:.2f}→{bh / 1e3:.1f} KB（{(1 - bh / bf) * 100:.2f}%）")

    # ② 与 POC 基线一致（元素数应 ≈ 331）
    c2 = abs(nh - 331) <= 5
    ok &= c2
    print(f"[{'PASS' if c2 else 'FAIL'}] ② 与 POC 基线一致（331±5）"
          f"（{nh}）")

    # ②b 与 POC 基线一致（flat 897,600 / 97.45 MB）
    c2b = nf == BASE_ELEMENTS and abs(bf - BASE_BYTES) < 0.02 * BASE_BYTES
    ok &= c2b
    print(f"[{'PASS' if c2b else 'FAIL'}] ②b flat 基线未漂移"
          f"（{nf:,} 元素 / {bf / 1e6:.2f} MB）")

    # ③ 几何零丢失：解析展开后的顶层几何数 ≡ flat 元素数
    t0 = time.time()
    pg = parse_gds_polygons(rh["gds_bytes"])
    n_geo = sum(len(pg["structures"][n]) for n in pg["top_structures"])
    t_parse = time.time() - t0
    c3 = n_geo == nf
    ok &= c3
    print(f"[{'PASS' if c3 else 'FAIL'}] ③ 展开几何 ≡ flat 元素数"
          f"（{n_geo:,} vs {nf:,}）· 解析 {t_parse:.1f}s")

    # ④ 抽样等价：随机实例 vs flat 对应几何（≤1 DBU）
    plan = H.detect_hierarchy(link, placement, routes, 0.5)
    flat_geoms = (CLE.device_geoms(link, placement, 0.5)
                  + CLE.route_geoms(routes, 0.5)
                  + CLE.io_grating_geoms(link, placement, 0.5))
    fk = Counter(CLE._geom_key(g) for g in flat_geoms)
    origins = plan.instance_origins()
    random.seed(20260904)
    picks = [0, 1, len(origins) - 1] + random.sample(
        range(len(origins)), min(6, len(origins)))
    worst = 0
    n_checked = 0
    for k in sorted(set(picks)):
        ox, oy = origins[k]
        for g in plan.cell_geoms:
            abs_g = CLE._shift_geom(g, ox, oy)
            key = CLE._geom_key(abs_g)
            n_checked += 1
            if fk.get(key):
                continue
            # 1 DBU 容差：在 flat 键中找最近邻
            hit = False
            for cand in fk:
                if (cand[:3] == key[:3]
                        and len(cand[3]) == len(key[3])):
                    d = max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                            for a, b in zip(cand[3], key[3]))
                    if d <= 1:
                        worst = max(worst, d)
                        hit = True
                        break
            if not hit:
                print(f"    !! 实例 {k} 有几何在 flat 中找不到匹配")
                ok = False
                break
    c4 = ok
    print(f"[{'PASS' if c4 else 'FAIL'}] ④ 抽样等价（≤1 DBU）"
          f"：{len(set(picks))} 个实例 / {n_checked:,} 个几何 · "
          f"最大偏差 {worst} nm")

    print("-" * 64)
    print("CPO 250k 层次化验证：", "ALL PASS" if ok else "有 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
