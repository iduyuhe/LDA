"""CPO 250k 全量：验证 P0-0 修复在最大规模上生效（v0.9.32）。

POC 阶段只在小阵列（4~16 端口）上取证。本脚本在 **250,240 器件**全量上复核：
  ① 修复后齿的簇数 == IO 端口数（缺陷态：全部重叠为 1 簇）
  ② 齿总数守恒 == n_io × 16
  ③ GDS 元素数 / 体积与修复前基线（897,600 元素 / 97.45 MB）对比
     —— GDS 坐标固定 4 字节编码，齿移位不应改变字节数与元素数；
        若变了，说明还有别的路径受影响，必须查清再发版。

跑法：python assess_p00_cpo250k_verify.py
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, "D:/agent_LDA/lda")

from lda_harness import cpo_array as CA                      # noqa: E402
from lda_layout.placement import port_abs                    # noqa: E402
from lda_l2.chip_layout_export import (                      # noqa: E402
    export_chip_gds, io_ports_of)
from lda_l2.gds_export import parse_gds_polygons             # noqa: E402

N_TOOTH = 16
# 修复前基线（POC 实测；注意：97.45 MB 是十进制字节，非 MiB）
BASE_ELEMENTS = 897_600
BASE_BYTES = 97.45e6


def main() -> int:
    cfg = CA.CPOArrayConfig(n_oe=40, n_ch=68, n_lane=8)
    t0 = time.time()
    link, placement, routes, _meta = CA.build_cpo_array_case(cfg)
    t_build = time.time() - t0
    print(f"构建 {len(link.ir.components):,} 器件 · {t_build:.1f}s", flush=True)

    t0 = time.time()
    r = export_chip_gds(link, placement, routes)
    t_exp = time.time() - t0
    st = r["gds_stats"]
    print(f"导出 {t_exp:.2f}s · GDS {st['gds_bytes']/1e6:.2f} MB · "
          f"元素 {st['n_elements']:,}", flush=True)

    ports = [port_abs(i, p, placement, link) for i, p in io_ports_of(link)]
    n_io = len(ports)
    print(f"IO 端口 {n_io:,}", flush=True)

    t0 = time.time()
    els = parse_gds_polygons(r["gds_bytes"])["structures"]["CHIP"]
    teeth = []
    for e in els:
        if e["kind"] != "boundary":
            continue
        xs = [p[0] for p in e["points_um"]]
        ys = [p[1] for p in e["points_um"]]
        teeth.append((round((min(xs) + max(xs)) / 2.0, 3),
                      round((min(ys) + max(ys)) / 2.0, 3)))
    t_parse = time.time() - t0
    print(f"解析 {t_parse:.1f}s · boundary {len(teeth):,}（应 "
          f"{n_io * N_TOOTH:,}）", flush=True)

    ok = True

    # ① 齿总数守恒
    c1 = len(teeth) == n_io * N_TOOTH
    ok &= c1
    print(f"\n[{'PASS' if c1 else 'FAIL'}] ① 齿总数 == n_io×{N_TOOTH} "
          f"（{len(teeth):,}/{n_io * N_TOOTH:,}）")

    # ② 去重簇数（缺陷态：全部重叠）
    uniq = len(set(teeth))
    c2 = uniq == n_io * N_TOOTH
    ok &= c2
    print(f"[{'PASS' if c2 else 'FAIL'}] ② 齿位置去重 == n_io×{N_TOOTH} "
          f"（{uniq:,}/{n_io * N_TOOTH:,}）")

    # ③ 与修复前基线对比（元素数 / 体积不应变）
    d_el = st["n_elements"] - BASE_ELEMENTS
    c3 = d_el == 0
    ok &= c3
    print(f"[{'PASS' if c3 else 'FAIL'}] ③ GDS 元素数与修复前基线一致 "
          f"（{st['n_elements']:,} vs {BASE_ELEMENTS:,}，差 {d_el:,}）")

    d_by = st["gds_bytes"] - BASE_BYTES
    c4 = abs(d_by) < 0.02 * BASE_BYTES
    print(f"[{'PASS' if c4 else 'FAIL'}] ④ GDS 体积与修复前基线一致（±2%）"
          f"（{st['gds_bytes']/1e6:.2f}MB vs {BASE_BYTES/1e6:.2f}MB，"
          f"差 {d_by/1e6:+.2f}MB）")
    ok &= c4

    print("-" * 60)
    print("CPO 250k P0-0 复核：", "ALL PASS" if ok else "有 FAIL，须查清")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
