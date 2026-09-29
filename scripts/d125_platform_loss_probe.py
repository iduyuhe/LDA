"""D-125 突变探针（scratch · 不入 CI）：证明 run_platform_loss_basis_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 平台每模深度用 len(ops) 冒充 ⇒ A1/A3/B2/D1/F1 应红
  · M2 矩形每模深度报 N+1 ⇒ A2 应红
  · M3 交叉损耗计入每模口径 ⇒ A4 应红（交叉只能进总口径）
  · M4 经典 DRC 只判总口径（丢每模口径）⇒ B2/B4/F3 应红
  · M5 经典 DRC 每模限值抹成 25（=总口径）⇒ B2 应红
  · M6 PROP_LENGTH_PARAM 登记一个**不可回提**参数 ⇒ C1 应红
  · M7 回提损耗改用**声明值**（不回提几何）⇒ C2 应红
  · M8 scale_bench 每模口径抹回 (N−1) ⇒ D1/D2/D3/D4/F1 应红
  · M9 旧键语义被改（loss_per_path_db 换成每模口径）⇒ D6 应红
  · M10 lvs_geom 未覆盖类谎报「已算」⇒ C5 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.MMM / S.DRC / S.G / S.SBM）——
   另起 `from lda_l2 import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_platform_loss_basis_smoke as S      # noqa: E402

MMM = S.MMM
DRC = S.DRC
G = S.G
SBM = S.SBM


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

    _pmd = MMM.mesh_per_mode_optical_depth
    _basis = MMM.mesh_loss_basis
    _dml = DRC.drc_check_mesh_loss
    _prop = G.PROP_LENGTH_PARAM
    _rpl = G.recovered_passive_loss
    _laws = SBM.mesh_scaling_laws

    # M1 平台每模深度用 len(ops) 冒充
    MMM.mesh_per_mode_optical_depth = lambda ops, n_modes=None: len(ops)
    rows.append(("M1 每模深度 = len(ops)（冒充）", *run_smoke()))
    MMM.mesh_per_mode_optical_depth = _pmd

    # M2 矩形每模深度报 N+1（用 3 元组判别）
    def _pmd_wrong(ops, n_modes=None):
        v = _pmd(ops, n_modes=n_modes)
        return v + 1 if all(len(o) == 3 for o in ops) else v

    MMM.mesh_per_mode_optical_depth = _pmd_wrong
    rows.append(("M2 矩形每模深度报 N+1", *run_smoke()))
    MMM.mesh_per_mode_optical_depth = _pmd

    # M3 交叉损耗计入每模口径
    def _basis_wrong(ops, n_crossings=0, **kw):
        d = dict(_basis(ops, n_crossings=n_crossings, **kw))
        d["per_mode_db"] = d["per_mode_db"] + d["crossing_loss_db"]
        return d

    MMM.mesh_loss_basis = _basis_wrong
    rows.append(("M3 交叉计入每模口径", *run_smoke()))
    MMM.mesh_loss_basis = _basis

    # M4 经典 DRC 只判总口径（丢每模口径）
    def _dml_total_only(ops, n_crossings=0, rules=None):
        d = _dml(ops, n_crossings=n_crossings, rules=rules)
        d.checks = [c for c in d.checks if c.basis != "每模口径"]
        d.passed = all(c.ok for c in d.checks)
        return d

    DRC.drc_check_mesh_loss = _dml_total_only
    rows.append(("M4 经典 DRC 只判总口径", *run_smoke()))
    DRC.drc_check_mesh_loss = _dml

    # M5 经典 DRC 每模限值抹成 25（= 总口径）
    _orig_limits = dict(DRC.DEFAULT_RULES)
    DRC.DEFAULT_RULES = dict(_orig_limits, max_il_per_mode_db=25.0)
    rows.append(("M5 每模限值抹成 25（=总口径）", *run_smoke()))
    DRC.DEFAULT_RULES = _orig_limits

    # M6 PROP_LENGTH_PARAM 登记一个不可回提参数
    G.PROP_LENGTH_PARAM = dict(_prop, Photodetector="det_L_not_measurable")
    rows.append(("M6 登记不可回提参数", *run_smoke()))
    G.PROP_LENGTH_PARAM = _prop

    # M7 回提损耗改用声明值（返回常量 ⇒ 与几何脱钩）
    def _rpl_const(link, placement, **kw):
        d = dict(_rpl(link, placement, **kw))
        for k, v in d["devices"].items():
            if v["loss_db"] is not None:
                v["loss_db"] = 0.0024
        return d

    G.recovered_passive_loss = _rpl_const
    rows.append(("M7 回提损耗与几何脱钩（常量）", *run_smoke()))
    G.recovered_passive_loss = _rpl

    # M8 scale_bench 每模口径抹回 (N−1)
    def _laws_old(n_modes):
        d = dict(_laws(n_modes))
        d["mzi_per_mode"] = int(n_modes) - 1
        d["loss_per_mode_db"] = (int(n_modes) - 1) * SBM.PER_MZI_LOSS_DB
        return d

    SBM.mesh_scaling_laws = _laws_old
    rows.append(("M8 每模口径抹回 (N−1)", *run_smoke()))
    SBM.mesh_scaling_laws = _laws

    # M9 旧键语义被改（loss_per_path_db 换成每模口径）
    def _laws_rekey(n_modes):
        d = dict(_laws(n_modes))
        d["loss_per_path_db"] = d["loss_per_mode_db"]
        return d

    SBM.mesh_scaling_laws = _laws_rekey
    rows.append(("M9 旧键语义被改（破坏兼容）", *run_smoke()))
    SBM.mesh_scaling_laws = _laws

    # M10 未覆盖类谎报「已算」
    def _rpl_cover(link, placement, **kw):
        d = dict(_rpl(link, placement, **kw))
        d["n_covered"] = d["n_devices"]
        d["uncovered_by_kind"] = {}
        return d

    G.recovered_passive_loss = _rpl_cover
    rows.append(("M10 未覆盖类谎报已算", *run_smoke()))
    G.recovered_passive_loss = _rpl

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：平台级损耗口径门禁（D-125）")
    print("=" * 74)
    for name, rc, nf in rows:
        print(f"  {name:34s} exit={rc}  [FAIL]×{nf}")

    n_probe = len(rows) - 2
    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in range(1, 1 + n_probe))
          and rows[-1][1] == 0 and rows[-1][2] == 0)
    print()
    print(f"探针结论：{'PASS —— %d 条突变各必红，还原复绿' % n_probe if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
