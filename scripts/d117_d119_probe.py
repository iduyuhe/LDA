"""D-117/118/119 突变探针（scratch · 不入 CI）：证明 run_quantum_calib_bench_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 标定：phase_from_three_step 符号翻转（−√3 而非 +√3）→ 三点法全错
             ⇒ A1/A2/A3/A5/A6/A7 应红
  · M2 DRC/LVS：_assemble_by_embedding 退化为恒等 ⇒ 版图侧酉错
             ⇒ B1（自检①双路装配）/B2/B3 应红
  · M3 基准：boson_sampling_benchmark 归一化破坏（norm≡0.5）⇒ 概率守恒失真
             ⇒ C1（自检①）/C2 应红
  · M4 基准：sample_from_distribution 退化为均匀采样 ⇒ χ² 会拒绝
             ⇒ C1（自检⑤⑥）/C5 应红
  · M5 标定：voltage_from_phase 斜率篡改 ⇒ 与平台 L2 层执行器不一致
             ⇒ D1（跨层桥）应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.CAL/S.QDR/S.QBM）——门禁走双路兜底可能绑成
   top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
🔴 M2 打的是「方法学独立」的那条腿（嵌入矩阵装配）——正是 D-118 用来交叉验证的路径，
   故它退化时双路一致性判据必须红；否则说明那条独立腿根本没接在判决上。
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "lda"))

import run_quantum_calib_bench_smoke as S      # noqa: E402

CAL, QDR, QBM = S.CAL, S.QDR, S.QBM            # 同一模块对象（见文件头教训）


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

    # M1 标定：三点法符号翻转
    _p3 = CAL.phase_from_three_step
    CAL.phase_from_three_step = (
        lambda i1, i2, i3: math.atan2(-math.sqrt(3.0) * (i1 - i3), 2.0 * i2 - i1 - i3))
    rows.append(("M1 标定 三点法符号翻转", *run_smoke()))
    CAL.phase_from_three_step = _p3

    # M2 DRC/LVS：版图侧装配退化为恒等（打独立腿）
    _asm = QDR._assemble_by_embedding
    QDR._assemble_by_embedding = lambda ops, D, N: np.eye(int(N), dtype=complex)
    rows.append(("M2 DRC/LVS 版图侧装配退化为恒等", *run_smoke()))
    QDR._assemble_by_embedding = _asm

    # M3 基准：玻色采样归一化破坏
    _bsb = QBM.boson_sampling_benchmark
    QBM.boson_sampling_benchmark = (
        lambda U, in_occ: {"norm": 0.5, "entropy_bits": 0.0, "peak": 0.0, "n_outcomes": 0})
    rows.append(("M3 基准 玻色采样归一化破坏", *run_smoke()))
    QBM.boson_sampling_benchmark = _bsb

    # M4 基准：采样退化为均匀
    _sfd = QBM.sample_from_distribution
    QBM.sample_from_distribution = (
        lambda dist, n, seed=0: (list(dist.keys()), np.full(len(dist), n / len(dist))))
    rows.append(("M4 基准 采样退化为均匀", *run_smoke()))
    QBM.sample_from_distribution = _sfd

    # M5 标定：执行器斜率篡改（打跨层桥）
    _vfp = CAL.voltage_from_phase
    CAL.voltage_from_phase = (
        lambda phi, phi0=0.0, vpi_l=25.0, arm_l=1.0, beta2=0.0: float(phi) * 10.0)
    rows.append(("M5 标定 执行器斜率篡改（跨层桥）", *run_smoke()))
    CAL.voltage_from_phase = _vfp

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 70)
    print("突变探针：量子标定/DRC-LVS/基准门禁（D-117/118/119）")
    print("=" * 70)
    for name, rc, nf in rows:
        print(f"  {name:44s} exit={rc}  [FAIL]×{nf}")

    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in range(1, 6))
          and rows[6][1] == 0 and rows[6][2] == 0)
    print()
    print(f"探针结论：{'PASS —— 五条突变各必红，还原复绿' if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
