"""D-114/115/116 突变探针（scratch · 不入 CI）：证明 run_photon_hardware_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 源：second_order_g2 恒返回 1  → HBT 三态失真 ⇒ A1/A2/A3/A6 应红
  · M2 探测：pnr_prob_closed_form 丢二项系数 → PNR 双路不一致 ⇒ B1/B3 应红
  · M3 开放系统：loss_kraus 误用 |k⟩⟨n|（去相位退化）→ 过程矩阵/多模一致/η=1 全坏 ⇒ C1/C2/C3/C5 应红
  · M4 探测：click_prob_closed_form 用线性 η·n 近似 → on/off 三路/桥/跨模块 ⇒ B1/B2/B6/D2 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.PS/S.DT/S.OS）——门禁走双路兜底可能绑成
   top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
🔴 M3 正是本批真实踩过的 bug（row-major/Kraus 约定），此处把「已知错误」固化为反证靶子。
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

import run_photon_hardware_smoke as S      # noqa: E402

PS, DT, OS = S.PS, S.DT, S.OS              # 同一模块对象（见文件头教训）


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

    # M1 源：g² 恒 1（抹掉反聚束/聚束差异）
    _g2 = PS.second_order_g2
    PS.second_order_g2 = lambda rho, n_max=150: 1.0
    rows.append(("M1 源 second_order_g2≡1（HBT 失真）", *run_smoke()))
    PS.second_order_g2 = _g2

    # M2 探测：PNR 丢二项系数
    _pnr = DT.pnr_prob_closed_form
    DT.pnr_prob_closed_form = lambda n, k, eta: (eta ** k if 0 <= k <= n else 0.0)
    rows.append(("M2 探测 PNR 丢二项系数", *run_smoke()))
    DT.pnr_prob_closed_form = _pnr

    # M3 开放系统：loss_kraus 误用 |k⟩⟨n|（去相位退化，本批真实 bug）
    _lk = OS.loss_kraus

    def bad_loss_kraus(eta, n_max):
        d = int(n_max) + 1
        ks = []
        for k in range(d):
            A = np.zeros((d, d), dtype=complex)
            for n in range(k, d):
                A[k, n] = (math.sqrt(math.comb(n, k))
                           * (1.0 - eta) ** (k / 2.0) * eta ** ((n - k) / 2.0))
            ks.append(A)
        return ks

    OS.loss_kraus = bad_loss_kraus
    rows.append(("M3 开放系统 Kraus 约定错（去相位）", *run_smoke()))
    OS.loss_kraus = _lk

    # M4 探测：on/off 响应线性近似 η·n
    _clk = DT.click_prob_closed_form
    DT.click_prob_closed_form = lambda eta, n, dark=0.0: eta * n
    rows.append(("M4 探测 on/off 线性近似 ηn", *run_smoke()))
    DT.click_prob_closed_form = _clk

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 70)
    print("突变探针：光子硬件物理门禁（D-114/115/116）")
    print("=" * 70)
    for name, rc, nf in rows:
        print(f"  {name:44s} exit={rc}  [FAIL]×{nf}")

    ok = (rows[0][1] == 0 and rows[0][2] == 0
          and all(rows[i][1] != 0 for i in (1, 2, 3, 4))
          and rows[5][1] == 0 and rows[5][2] == 0)
    print()
    print(f"探针结论：{'PASS —— 四条突变各必红，还原复绿' if ok else 'FAIL —— 探针异常'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
