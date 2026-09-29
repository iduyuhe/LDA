"""D-122 突变探针（scratch · 不入 CI）：证明 run_rect_mesh_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 桥朝向错：`_apply_bridged` 改成不拆对角相位层（直接 mzi_unit_cell(θ,−φ)）
             ⇒ A1/A3/A4/C2 应红（★血案：裸门嵌入后注入逐模相位 ⇒ 网格错，fid 0.005/0.66）
  · M2 深度谎报：rect_mesh_profile 把 depth 报成三角 Reck 的 2N−3 ⇒ A1/B1/B4/B6/C1/C4 应红
  · M3 元件数谎报：rect_mesh_profile 报 n_mzi=1 ⇒ B5 应红
  · M4 光学深度谎报：optical_depth 报 N+1 ⇒ B3 应红
  · M5 可达性谎报：tight_bound_reachable_report 报 depth=2N−3 且 reachable=False
             ⇒ B4/F2 应红（★「紧界可达」这条落点的判据）
  · M6 紧界谎报：tight_depth_lower_bound 抹回参数界（偶 N ⇒ N−1）⇒ B1/B4 应红
  · M7 披露抹掉：RED_LINE_DISCLOSURE 删键 ⇒ D1 应红
  · M8 平台原语篡改：mzi_unit_cell 乘一个全局相位 ⇒ A1/A2/A4 应红
             （★证明「约定桥恒等式」判据真会响，不是区间外恒真）
  · M9 匹配性谎报：rect_mesh_profile 报 layers_are_matchings=False ⇒ B2 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.RMB / S.TMB / S.MMM）——门禁走双路
   兜底可能绑成 top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_rect_mesh_smoke as S      # noqa: E402

RMB = S.RMB                          # 同一模块对象（见文件头教训）
TMB = S.TMB
MMM = S.MMM


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

    # M1 桥朝向错：不拆对角相位层（直接 mzi_unit_cell(θ,−φ)）
    _ab = RMB._apply_bridged

    def _ab_bad(T, j, theta_mzi, phi_diag):
        G = MMM.mzi_unit_cell(float(theta_mzi), -float(phi_diag))
        r0, r1 = T[j].copy(), T[j + 1].copy()
        T[j] = G[0, 0] * r0 + G[0, 1] * r1
        T[j + 1] = G[1, 0] * r0 + G[1, 1] * r1

    RMB._apply_bridged = _ab_bad
    rows.append(("M1 桥朝向错（丢对角相位层）", *run_smoke()))
    RMB._apply_bridged = _ab

    # M2 深度谎报：报成三角 Reck 的 2N−3
    _prf = RMB.rect_mesh_profile

    def _prf_reck(n_modes, *, target="dft", seed=0):
        d = _prf(n_modes, target=target, seed=seed)
        d["depth"] = 2 * int(n_modes) - 3
        d["n_layers"] = d["depth"]
        return d

    RMB.rect_mesh_profile = _prf_reck
    rows.append(("M2 深度谎报 2N−3", *run_smoke()))
    RMB.rect_mesh_profile = _prf

    # M3 元件数谎报：n_mzi=1
    def _prf_mzi(n_modes, *, target="dft", seed=0):
        d = _prf(n_modes, target=target, seed=seed)
        d["n_mzi"] = 1
        return d

    RMB.rect_mesh_profile = _prf_mzi
    rows.append(("M3 元件数谎报 1", *run_smoke()))
    RMB.rect_mesh_profile = _prf

    # M4 光学深度谎报：N+1
    def _prf_opt(n_modes, *, target="dft", seed=0):
        d = _prf(n_modes, target=target, seed=seed)
        d["optical_depth"] = int(n_modes) + 1
        return d

    RMB.rect_mesh_profile = _prf_opt
    rows.append(("M4 光学深度谎报 N+1", *run_smoke()))
    RMB.rect_mesh_profile = _prf

    # M5 可达性谎报：报告 depth=2N−3 且 reachable=False
    _tbr = RMB.tight_bound_reachable_report

    def _tbr_lie(n_modes):
        d = _tbr(n_modes)
        d["rectangular_mesh_depth"] = 2 * int(n_modes) - 3
        d["tight_bound_reachable"] = False
        return d

    RMB.tight_bound_reachable_report = _tbr_lie
    rows.append(("M5 可达性谎报（不可达）", *run_smoke()))
    RMB.tight_bound_reachable_report = _tbr

    # M6 紧界谎报：抹回参数界（偶 N ⇒ N−1）
    _tdlb = TMB.tight_depth_lower_bound
    TMB.tight_depth_lower_bound = lambda n: max(1, int(n) - 1)
    rows.append(("M6 紧界谎报（回 N−1）", *run_smoke()))
    TMB.tight_depth_lower_bound = _tdlb

    # M7 披露抹掉：删 RED_LINE_DISCLOSURE 键
    _disc = RMB.RED_LINE_DISCLOSURE
    RMB.RED_LINE_DISCLOSURE = {"role": "x"}
    rows.append(("M7 披露抹掉（缺键）", *run_smoke()))
    RMB.RED_LINE_DISCLOSURE = _disc

    # M8 平台原语篡改：mzi_unit_cell 乘全局相位 ⇒ 桥恒等式应失效
    _mzi = MMM.mzi_unit_cell

    def _mzi_bad(theta, phi):
        return np.exp(1j * 0.3) * _mzi(theta, phi)

    MMM.mzi_unit_cell = _mzi_bad
    rows.append(("M8 平台原语篡改（全局相位）", *run_smoke()))
    MMM.mzi_unit_cell = _mzi

    # M9 匹配性谎报：layers_are_matchings=False
    def _prf_nomatch(n_modes, *, target="dft", seed=0):
        d = _prf(n_modes, target=target, seed=seed)
        d["layers_are_matchings"] = False
        return d

    RMB.rect_mesh_profile = _prf_nomatch
    rows.append(("M9 匹配性谎报（假）", *run_smoke()))
    RMB.rect_mesh_profile = _prf

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：矩形 Clements 网格门禁（D-122 · M5）")
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
