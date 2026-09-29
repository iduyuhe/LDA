"""D-123 突变探针（scratch · 不入 CI）：证明 run_loss_budget_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 ★口径血案★ 三角每模深度抹回列数 N−1（把 2N−3 谎报成 N−1）
             ⇒ A1/A3/B1/B2/F3 应红（这正是 D-120 列口径低估约 2× 的真因）
  · M2 M5 收益抹掉：矩形每模深度谎报成 2N−3 ⇒ A1/A4/B1/F3 应红
  · M3 列口径谎报：column_basis_loss 报 (2N−3)·per ⇒ B2/F2 应红
  · M4 时间复用谎报：per_step 抹成 per_mzi(2.4) ⇒ A1/C1/C2 应红
             （★证明「通用不省损」判据真会响）
  · M5 浅电路谎报通用：temporal_shallow_loss_budget 报 universal=True ⇒ C4 应红
  · M6 通用下界谎报：universality_loss_floor 报 triangular_static 为最优 ⇒ C5 应红
  · M7 披露抹掉：RED_LINE_DISCLOSURE 删键 ⇒ D1/D4 应红
  · M8 元件数谎报：三角/矩形 n_mzi 报 1 ⇒ A1/A5 应红
  · M9 每模深度 min 谎报：矩形 min=N（抹掉 ⌊N/2⌋）⇒ A1/A4 应红
  · M10 ★下界≠可达★ 浅电路 universal 只按参数口径（抹掉紧界）⇒ C7 应红
             （D=N−1 参数已够 23220，但 D-121/D-122 证 N−1 不可达）
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.LB / S.TMB / S.RMB）——门禁走双路
   兜底可能绑成 top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_loss_budget_smoke as S      # noqa: E402

LB = S.LB                              # 同一模块对象（见文件头教训）
TMB = S.TMB                            # noqa: E402


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

    _tri = LB.triangular_optical_depth
    _rect = LB.rectangular_optical_depth
    _col = LB.column_basis_loss
    _shallow = LB.temporal_shallow_loss_budget
    _floor = LB.universality_loss_floor
    _disc = LB.RED_LINE_DISCLOSURE
    _per_step = LB.PER_STEP_LOSS_DB

    # M1 口径血案：三角每模深度抹回列数 N−1
    def _tri_col(n_modes):
        d = dict(_tri(n_modes))
        d["per_mode_max"] = int(n_modes) - 1
        return d

    LB.triangular_optical_depth = _tri_col
    rows.append(("M1 三角每模深度抹回 N−1（口径血案）", *run_smoke()))
    LB.triangular_optical_depth = _tri

    # M2 M5 收益抹掉：矩形每模深度谎报成 2N−3
    def _rect_reck(n_modes):
        d = dict(_rect(n_modes))
        d["per_mode_max"] = 2 * int(n_modes) - 3
        return d

    LB.rectangular_optical_depth = _rect_reck
    rows.append(("M2 矩形每模深度谎报 2N−3", *run_smoke()))
    LB.rectangular_optical_depth = _rect

    # M3 列口径谎报：报 (2N−3)·per
    def _col_lie(n_modes, *, per_mzi_db=None):
        d = dict(_col(n_modes, per_mzi_db=per_mzi_db))
        d["loss_per_mode_db"] = (2 * int(n_modes) - 3) * LB.PER_MZI_LOSS_DB
        return d

    LB.column_basis_loss = _col_lie
    rows.append(("M3 列口径谎报（= 三角每模账）", *run_smoke()))
    LB.column_basis_loss = _col

    # M4 时间复用谎报：per_step 抹成 per_mzi
    LB.PER_STEP_LOSS_DB = float(LB.PER_MZI_LOSS_DB)
    rows.append(("M4 每步损耗抹成 per_mzi（通用不省损失效）", *run_smoke()))
    LB.PER_STEP_LOSS_DB = _per_step

    # M5 浅电路谎报通用
    def _shallow_uni(n_modes, depth):
        d = dict(_shallow(n_modes, depth))
        d["universal"] = True
        return d

    LB.temporal_shallow_loss_budget = _shallow_uni
    rows.append(("M5 浅电路谎报通用", *run_smoke()))
    LB.temporal_shallow_loss_budget = _shallow

    # M6 通用下界谎报：报三角静态为最优
    def _floor_lie(n_modes):
        d = dict(_floor(n_modes))
        d["floor_kind"] = "triangular_static"
        d["floor_db"] = (2 * int(n_modes) - 3) * LB.PER_MZI_LOSS_DB
        return d

    LB.universality_loss_floor = _floor_lie
    rows.append(("M6 通用下界谎报（三角为最优）", *run_smoke()))
    LB.universality_loss_floor = _floor

    # M7 披露抹掉
    LB.RED_LINE_DISCLOSURE = {"role": "x"}
    rows.append(("M7 披露抹掉（缺键）", *run_smoke()))
    LB.RED_LINE_DISCLOSURE = _disc

    # M8 元件数谎报
    def _tri_mzi(n_modes):
        d = dict(_tri(n_modes))
        d["n_mzi"] = 1
        return d

    def _rect_mzi(n_modes):
        d = dict(_rect(n_modes))
        d["n_mzi"] = 1
        return d

    LB.triangular_optical_depth = _tri_mzi
    LB.rectangular_optical_depth = _rect_mzi
    rows.append(("M8 元件数谎报 1", *run_smoke()))
    LB.triangular_optical_depth = _tri
    LB.rectangular_optical_depth = _rect

    # M9 每模深度 min 谎报：矩形 min = N
    def _rect_min(n_modes):
        d = dict(_rect(n_modes))
        d["per_mode_min"] = int(n_modes)
        return d

    LB.rectangular_optical_depth = _rect_min
    rows.append(("M9 矩形每模深度 min 谎报 N", *run_smoke()))
    LB.rectangular_optical_depth = _rect

    # M10 下界≠可达：浅电路 universal 只按参数口径（抹掉紧界）⇒ D=N−1 会谎报通用
    def _shallow_parametric(n_modes, depth):
        d = dict(_shallow(n_modes, depth))
        d["universal"] = d["parametric_universal"]
        d["achievable_universal"] = True
        return d

    LB.temporal_shallow_loss_budget = _shallow_parametric
    rows.append(("M10 浅电路只按参数口径（下界≠可达）", *run_smoke()))
    LB.temporal_shallow_loss_budget = _shallow

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：真实损耗预算门禁（D-123 · M5 延伸）")
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
