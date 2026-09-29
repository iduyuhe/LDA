"""D-113 突变探针（scratch · 不入 CI）：证明 run_loqc_states_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 分束器去离对角虚数  → 破坏 HOM 相位约定 ⇒ HOM/闭式/相位/芯片级多条应红
  · M2 归一化多一层 sqrt    → 破坏多光子自洽 ⇒ ④双算法/⑤归一 应红
  · M3 可区分 ≡ 不可区分    → 抹掉干涉差异 ⇒ ⑦反自证桩/⑧可见度 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.L）——门禁走双路兜底可能绑成顶层
   `loqc_states`，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
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

import run_loqc_states_smoke as S          # noqa: E402
L = S.L                                    # 同一模块对象（见文件头教训）


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

    _bs = L.bs_unitary

    def bad_bs(theta, phi=0.0):
        c, s = math.cos(theta), math.sin(theta)
        return np.array([[c, s], [s, c]], dtype=complex)

    L.bs_unitary = bad_bs
    rows.append(("M1 分束器去虚数（HOM 约定破坏）", *run_smoke()))
    L.bs_unitary = _bs

    _fp = L._factorial_product

    def bad_fp(occ):
        d = 1.0
        for c in occ:
            d *= math.factorial(int(c))
        return math.sqrt(d)

    L._factorial_product = bad_fp
    rows.append(("M2 归一化多一层 sqrt（复现原 bug）", *run_smoke()))
    L._factorial_product = _fp

    _dd = L.hom_coincidence_distinguishable
    L.hom_coincidence_distinguishable = L.hom_coincidence
    rows.append(("M3 可区分≡不可区分（抹掉干涉）", *run_smoke()))
    L.hom_coincidence_distinguishable = _dd

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 66)
    print("突变探针：LOQC 量子态层门禁（D-113）")
    print("=" * 66)
    for name, rc, nf in rows:
        print(f"  {name:38s} exit={rc}  [FAIL]×{nf}")

    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in (1, 2, 3))
          and rows[4][1] == 0 and rows[4][2] == 0)
    print()
    print(f"探针结论：{'PASS —— 三条突变各必红，还原复绿' if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
