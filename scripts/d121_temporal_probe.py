"""D-121 突变探针（scratch · 不入 CI）：证明 run_temporal_mesh_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 装配方向：时间表门强制用**正向**块（丢掉 G†）⇒ A1/B1/B2/B4/E1 应红
             （本轮真实血案：装配方向错 ⇒ fid 掉到 ~0.58 而非 1.0）
  · M2 深度下界：universality_depth_lower_bound 篡改为 N/2（伪 o(N) 下界）
             ⇒ A1/C1/C3/D1 应红（★这条最关键：下界是「不省损耗」结论的地基）
  · M3 假通用：schedule_unitary 恒返回单位阵（假装能重建任意酉）⇒ A1/B1/B2 应红
  · M4 抹掉省元件：static_mesh_resources 物理 MZI 数改为 1 ⇒ A1/C2 应红
  · M5 结论反转：temporal_mesh_verdict 谎称「时间复用省损耗」⇒ A1/D1 应红
  · M6 假通用晶格：fixed_lattice_programmability 可及参数改为 M²（判它通用）
             ⇒ A1/C4 应红
  · M7 浅调度退化：critical_path_layers 退化为「一门一层」⇒ 深度 = n_mzi（O(N²)）
             ⇒ A1/G1/G5 应红（★浅调度的存在性判据）
  · M8 紧界谎报：tight_depth_lower_bound 抹成参数界（偶 N 回 N−1，谎称 N−1 可达）
             ⇒ A1/G3 应红（★「N−1 不可达」这条收紧结论的判据）
  · M9 唯一最大匹配谎报：adjacency_max_matching 对偶 N 谎报「非唯一」
             ⇒ A1/G3 应红（去掉唯一性 ⇒ 紧界论证失效）
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.TMB）——门禁走双路兜底可能绑成
   top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_temporal_mesh_smoke as S      # noqa: E402

TMB = S.TMB                              # 同一模块对象（见文件头教训）


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

    # M1 装配方向：门强制正向（丢掉 G† 的共轭转置语义）
    _su = TMB.schedule_unitary

    def _su_forward(schedule, n_modes):
        fixed = []
        for st in schedule:
            if st["kind"] == "gates":
                fixed.append({"kind": "gates",
                              "gates": [(i, th, ph, False)
                                        for (i, th, ph, _inv) in st["gates"]]})
            else:
                fixed.append(st)
        return _su(fixed, n_modes)

    TMB.schedule_unitary = _su_forward
    rows.append(("M1 装配方向错（丢 G†）", *run_smoke()))
    TMB.schedule_unitary = _su

    # M2 深度下界：伪 o(N)（N/2）
    _dlb = TMB.universality_depth_lower_bound
    TMB.universality_depth_lower_bound = lambda n: max(1, int(n) // 2)
    rows.append(("M2 深度下界伪 o(N)=N/2", *run_smoke()))
    TMB.universality_depth_lower_bound = _dlb

    # M3 假通用：重建恒返回单位阵
    TMB.schedule_unitary = lambda schedule, n_modes: np.eye(int(n_modes), dtype=complex)
    rows.append(("M3 假通用（重建=单位阵）", *run_smoke()))
    TMB.schedule_unitary = _su

    # M4 抹掉省元件：静态网格物理 MZI 数谎报为 1
    _smr = TMB.static_mesh_resources

    def _smr_one(n_modes):
        d = _smr(n_modes)
        d["n_physical_mzi"] = 1
        return d

    TMB.static_mesh_resources = _smr_one
    rows.append(("M4 抹掉省元件（静态=1 片）", *run_smoke()))
    TMB.static_mesh_resources = _smr

    # M5 结论反转：谎称时间复用省损耗
    _tmv = TMB.temporal_mesh_verdict

    def _tmv_lie(n_modes=216):
        d = _tmv(n_modes)
        d["loss_saving_strictly_negative"] = False
        d["loss_saved_db_by_time_multiplexing"] = abs(
            d["loss_saved_db_by_time_multiplexing"])
        return d

    TMB.temporal_mesh_verdict = _tmv_lie
    rows.append(("M5 结论反转（谎称省损）", *run_smoke()))
    TMB.temporal_mesh_verdict = _tmv

    # M6 假通用晶格：可及参数谎报为 M²（据此判其通用）
    _flp = TMB.fixed_lattice_programmability

    def _flp_fake(n_modes, lattice_a=6):
        d = _flp(n_modes, lattice_a=lattice_a)
        d["reachable_params_model"] = d["n_modes_realized"] ** 2
        d["universal"] = True
        return d

    TMB.fixed_lattice_programmability = _flp_fake
    rows.append(("M6 假通用晶格（可及=M²）", *run_smoke()))
    TMB.fixed_lattice_programmability = _flp

    # M7 浅调度退化：关键路径分层抹成「一门一层」⇒ 深度 = n_mzi（O(N²) 假最优）
    _cpl = TMB.critical_path_layers

    def _cpl_serial(seq):
        return [[g] for g in seq], len(seq)

    TMB.critical_path_layers = _cpl_serial
    rows.append(("M7 浅调度退化（一头一层）", *run_smoke()))
    TMB.critical_path_layers = _cpl

    # M8 紧界谎报：抹成参数界（偶 N 回 N−1）⇒ 谎称 N−1 可达
    _tdlb = TMB.tight_depth_lower_bound
    TMB.tight_depth_lower_bound = lambda n: TMB.universality_depth_lower_bound(n)
    rows.append(("M8 紧界谎报（回 N−1）", *run_smoke()))
    TMB.tight_depth_lower_bound = _tdlb

    # M9 唯一最大匹配谎报：对偶 N 谎报「非唯一」⇒ 紧界论证失效
    _amm = TMB.adjacency_max_matching

    def _amm_lie(n_modes):
        d = _amm(n_modes)
        d["unique_max_matching"] = False
        return d

    TMB.adjacency_max_matching = _amm_lie
    rows.append(("M9 唯一性谎报（偶 N 非唯一）", *run_smoke()))
    TMB.adjacency_max_matching = _amm

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：量子时间复用可编程酉门禁（D-121 · M4 延伸）")
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
