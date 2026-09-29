"""D-126 突变探针（scratch · 不入 CI）：证明 run_il_basis_platform_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 `il_basis_from_stats` 自动排序（抹平序护栏）⇒ A4 应红
  · M2 `il_basis_from_values` 报 max=min（spread 归零）⇒ B2/E2 应红 · F1（manifest 护栏当场 raise）
  · M3 `PER_MODE_REQUIRED_KEYS` 缩到 5（词汇缩水）⇒ A2 应红
  · M4 总线每模 max 抹成 mean（最坏冒充均值）⇒ B2/B5 应红
  · M5 瓦片每模 max 抹成 mean ⇒ C3/C5 应红
  · M6 `tile_geometry` deg_max 抹成 deg_min（抹掉最坏模）⇒ C2/C3 应红
  · M7 瓦片每模式总量抹成均值口径 ⇒ D2 应红
  · M8 Pareto 损耗轴换成**最好模**（min）⇒ E1 应红
  · M9 `assert_basis_consistency` 恒过（护栏空转）⇒ A5/F3 应红
  · M10 `il_basis_manifest` 只回 3 通道（漏一通道）⇒ F1 应红
  · M11 披露删 `no_physics`（偷算物理/边界失守）⇒ A3/F5 应红
  · M12 `mesh_per_mode_optical_depth_stats` depth_max 抹成 depth_mean ⇒ G1 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.ILB / S.LAC / S.MT / S.MMM / S.OP）——
   另起 `from lda_l2 import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿；
   门禁内**按名导入**的函数（`from x import f`）无法被 patch 模块属性影响 ⇒
   本门禁一律用 `MMM.foo(...)` 形式访问（见 G1）。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_il_basis_platform_smoke as S      # noqa: E402

ILB = S.ILB
LAC = S.LAC
MT = S.MT
MMM = S.MMM
OP = S.OP


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                     # 突变致病态 ⇒ 崩溃也算红（exit≠0）
        rc = 99
        buf.write(f"[FAIL] 门禁异常：{type(e).__name__}: {e}")
    out = buf.getvalue()
    return rc, out.count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _from_stats = ILB.il_basis_from_stats
    _from_values = ILB.il_basis_from_values
    _req_keys = ILB.PER_MODE_REQUIRED_KEYS
    _bus = LAC.il_per_port_direct_bus
    _d1 = MT.d1_bus_budget
    _tgeom = MT.tile_geometry
    _p3 = MT.p3_tiling_ceiling
    _ometrics = OP.optical_metrics
    _consist = ILB.assert_basis_consistency
    _manifest = ILB.il_basis_manifest
    _disc = ILB.IL_BASIS_DISCLOSURE
    _stats = MMM.mesh_per_mode_optical_depth_stats

    # M1 序护栏被抹平（自动排序）
    def _stats_sorted(il_min_db, il_mean_db, il_max_db, **kw):
        a = sorted([il_min_db, il_mean_db, il_max_db])
        return _from_stats(a[0], a[1], a[2], **kw)

    ILB.il_basis_from_stats = _stats_sorted
    rows.append(("M1 序护栏抹平（自动排序）", *run_smoke()))
    ILB.il_basis_from_stats = _from_stats

    # M2 from_values 报 max=min（spread 归零）
    def _values_flat(values_db, **kw):
        d = dict(_from_values(values_db, **kw))
        d["il_max_db"] = d["il_min_db"]
        d["il_spread_db"] = 0.0
        return d

    ILB.il_basis_from_values = _values_flat
    rows.append(("M2 每模 max 抹成 min（spread=0）", *run_smoke()))
    ILB.il_basis_from_values = _from_values

    # M3 词汇缩水
    ILB.PER_MODE_REQUIRED_KEYS = tuple(_req_keys[:5])
    rows.append(("M3 必备键缩到 5（词汇缩水）", *run_smoke()))
    ILB.PER_MODE_REQUIRED_KEYS = _req_keys

    # M4 总线每模 max 抹成 mean
    def _bus_mean_max(br, pdk=None, rail_pitch=LAC.RAIL_PITCH_DEFAULT,
                      gap=LAC.GAP_DEFAULT):
        d = dict(_bus(br, pdk, rail_pitch, gap))
        b = dict(d["il_basis_per_mode"])
        b["il_max_db"] = b["il_mean_db"]
        b["il_spread_db"] = b["il_max_db"] - b["il_min_db"]
        d["il_basis_per_mode"] = b
        d["IL_max_db"] = b["il_max_db"]
        return d

    LAC.il_per_port_direct_bus = _bus_mean_max
    rows.append(("M4 总线最坏模抹成均值", *run_smoke()))
    LAC.il_per_port_direct_bus = _bus

    # M5 瓦片每模 max 抹成 mean
    def _d1_mean_max(N_tile, scenario="B", layout_mode=MT.LAYOUT_MODE_DEFAULT,
                     rail_switch_margin=MT.RAIL_SWITCH_MARGIN, **kw):
        d = dict(_d1(N_tile, scenario=scenario, layout_mode=layout_mode,
                     rail_switch_margin=rail_switch_margin, **kw))
        b = dict(d["il_basis_per_mode"])
        b["il_max_db"] = b["il_mean_db"]
        b["il_spread_db"] = b["il_max_db"] - b["il_min_db"]
        d["il_basis_per_mode"] = b
        d["IL_max_db"] = b["il_max_db"]
        return d

    MT.d1_bus_budget = _d1_mean_max
    rows.append(("M5 瓦片最坏模抹成均值", *run_smoke()))
    MT.d1_bus_budget = _d1

    # M6 瓦片 deg_max 抹成 deg_min
    def _tgeom_wrong(N_tile, **kw):
        d = dict(_tgeom(N_tile, **kw))
        d["deg_max"] = d["deg_min"]
        d["deg_span"] = 0
        return d

    MT.tile_geometry = _tgeom_wrong
    rows.append(("M6 瓦片 deg_max 抹成 deg_min", *run_smoke()))
    MT.tile_geometry = _tgeom

    # M7 瓦片每模式总量抹成均值口径
    def _p3_mean(N_tile, scenario="B", **kw):
        d = dict(_p3(N_tile, scenario=scenario, **kw))
        new_rows = []
        for r in d["rows"]:
            r2 = dict(r)
            r2["IL_total_per_mode_db"] = r2["IL_total_db"]
            new_rows.append(r2)
        d["rows"] = new_rows
        d["ceiling_per_mode_eq_N"] = d["ceiling_eq_N"]
        d["ceiling_per_mode_rx_N"] = d["ceiling_rx_N"]
        return d

    MT.p3_tiling_ceiling = _p3_mean
    rows.append(("M7 每模式天花板退化为均值口径", *run_smoke()))
    MT.p3_tiling_ceiling = _p3

    # M8 Pareto 损耗轴换成最好模
    def _ometrics_min(N, K, arch=OP.ARCH_SHARED, **kw):
        d = dict(_ometrics(N, K, arch=arch, **kw))
        d["il_worst_db"] = d["il_basis_per_mode"]["il_min_db"]
        return d

    OP.optical_metrics = _ometrics_min
    rows.append(("M8 Pareto 轴换成最好模（min）", *run_smoke()))
    OP.optical_metrics = _ometrics

    # M9 一致性护栏空转
    ILB.assert_basis_consistency = lambda entry, **kw: entry
    rows.append(("M9 一致性护栏恒过（空转）", *run_smoke()))
    ILB.assert_basis_consistency = _consist

    # M10 manifest 漏一通道
    def _manifest3(N=8, **kw):
        m = dict(_manifest(N, **kw))
        m["channels"] = {k: v for k, v in m["channels"].items() if k != "pareto"}
        m["n_channels"] = 3
        return m

    ILB.il_basis_manifest = _manifest3
    rows.append(("M10 manifest 漏一通道", *run_smoke()))
    ILB.il_basis_manifest = _manifest

    # M11 披露删 no_physics
    ILB.IL_BASIS_DISCLOSURE = {k: v for k, v in _disc.items() if k != "no_physics"}
    rows.append(("M11 披露删 no_physics", *run_smoke()))
    ILB.IL_BASIS_DISCLOSURE = _disc

    # M12 mesh 每模 stats 的 depth_max 抹成 depth_mean
    def _stats_mean(ops, n_modes=None):
        d = dict(_stats(ops, n_modes=n_modes))
        d["depth_max"] = int(d["depth_mean"])
        return d

    MMM.mesh_per_mode_optical_depth_stats = _stats_mean
    rows.append(("M12 mesh stats depth_max 抹成 mean", *run_smoke()))
    MMM.mesh_per_mode_optical_depth_stats = _stats

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：每模口径平台门禁（D-126）")
    print("=" * 74)
    for name, rc, nf in rows:
        print(f"  {name:36s} exit={rc}  [FAIL]×{nf}")

    n_probe = len(rows) - 2
    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in range(1, 1 + n_probe))
          and rows[-1][1] == 0 and rows[-1][2] == 0)
    print()
    print(f"探针结论：{'PASS —— %d 条突变各必红，还原复绿' % n_probe if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
