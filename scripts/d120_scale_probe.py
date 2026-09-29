"""D-120 突变探针（scratch · 不入 CI）：证明 run_quantum_scale_bench_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 规模律：n_mzi 由 N(N−1)/2 篡改为 N² ⇒ A2/A4/B1/B3/B4 应红
  · M2 损耗墙：per_path_transmissivity 恒 1.0（无视指数衰减）⇒ C4/C5 应红
  · M3 尺度盲：calibration_fidelity_law 篡改为「随 N 下降」的伪律
             ⇒ C1/C2/F4 应红（★这条最关键：尺度盲是本模块的核心结论）
  · M4 输出空间：hilbert_dim 由 C(N+k−1,k) 篡改为 N^k ⇒ D3 应红
  · M5 架构：time_multiplexed_architecture 环数由 log_a N 篡改为 N ⇒ E1/E2 应红
  · M6 对标：BOREALIS_REF.squeezed_modes 216→128（篡改外部事实）⇒ E3 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.SBM）——门禁走双路兜底可能绑成
   top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_quantum_scale_bench_smoke as S      # noqa: E402

SBM = S.SBM                                    # 同一模块对象（见文件头教训）


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

    # M1 规模律：元件数公式改为 N²（错公式）
    _laws = SBM.mesh_scaling_laws
    SBM.mesh_scaling_laws = lambda n: {
        **_laws(n), "n_mzi": int(n) * int(n), "loss_total_db": float(int(n) * int(n) * SBM.PER_MZI_LOSS_DB)}
    rows.append(("M1 规模律 n_mzi=N²（错公式）", *run_smoke()))
    SBM.mesh_scaling_laws = _laws

    # M2 损耗墙：透射率恒 1.0（无视指数衰减）
    _eta = SBM.per_path_transmissivity
    SBM.per_path_transmissivity = lambda n, per_mzi_db=None: 1.0
    rows.append(("M2 损耗墙 透射率恒 1.0", *run_smoke()))
    SBM.per_path_transmissivity = _eta

    # M3 尺度盲：伪律「保真度随 N 下降」（推翻核心结论）
    _law = SBM.calibration_fidelity_law
    SBM.calibration_fidelity_law = (
        lambda sigma, n: max(0.0, 1.0 - float(sigma) * float(n) / 100.0))
    rows.append(("M3 尺度盲 伪律随 N 下降", *run_smoke()))
    SBM.calibration_fidelity_law = _law

    # M4 输出空间：维数公式改为 N^k（错组合）
    _hd = SBM.hilbert_dim
    SBM.hilbert_dim = lambda n, k: int(n) ** int(k)
    rows.append(("M4 输出空间 dim=N^k（错组合）", *run_smoke()))
    SBM.hilbert_dim = _hd

    # M5 架构：时间复用环数改为 N（而非 log_a N）
    _tm = SBM.time_multiplexed_architecture
    SBM.time_multiplexed_architecture = lambda n, **kw: {
        **_tm(n), "n_loops": int(n), "n_modes_realized": int(n),
        "loss_per_mode_db": int(n) * SBM.PER_LOOP_LOSS_DB,
        "per_path_eta": 10.0 ** (-(int(n) * SBM.PER_LOOP_LOSS_DB) / 10.0)}
    rows.append(("M5 架构 时间复用环数=N", *run_smoke()))
    SBM.time_multiplexed_architecture = _tm

    # M6 对标：篡改外部事实（Borealis 模数 216→128）
    _orig_modes = SBM.BOREALIS_REF["squeezed_modes"]
    SBM.BOREALIS_REF["squeezed_modes"] = 128
    rows.append(("M6 对标 Borealis 模数篡改", *run_smoke()))
    SBM.BOREALIS_REF["squeezed_modes"] = _orig_modes

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：量子规模对标门禁（D-120 · M4 规模律与瓶颈）")
    print("=" * 74)
    for name, rc, nf in rows:
        print(f"  {name:40s} exit={rc}  [FAIL]×{nf}")

    n_probe = len(rows) - 2
    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in range(1, 1 + n_probe))
          and rows[-1][1] == 0 and rows[-1][2] == 0)
    print()
    print(f"探针结论：{'PASS —— %d 条突变各必红，还原复绿' % n_probe if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
