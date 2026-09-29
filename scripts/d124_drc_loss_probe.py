"""D-124 突变探针（scratch · 不入 CI）：证明 run_drc_loss_per_mode_smoke.py 能变红。

惯例：scripts/*_probe.py 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块函数（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 每模口径删掉（per_mode_optical_depth 恒 0）⇒ A1/A2/A5/B2/B3/B5/C2/E2/E3/F1 应红
             （★这正是「只留总级联口径」的退化形态）
  · M2 每模深度用 len(ops) 冒充 ⇒ A2/A5/B2/E2/E3/F1 应红（三角 2N−3 被报成 N(N−1)/2）
  · M3 默认每模限值抹成 25（= 总口径）⇒ B2/B3 应红（每模口径不再是绑定判据）
  · M4 detail 不标口径（笼统「损耗超限」）⇒ B1/B2/B5 应红（不可追责）
  · M5 per_mode_optical_depth 返回常量 ⇒ A2/A3/A5/E2/F1 应红
  · M6 删掉 3 元组（矩形展平）支持 ⇒ A4 应红
  · M7 披露抹掉（删 loss_basis）⇒ D1 应红
  · M8 QDR_RULES 加一条（破坏兼容性声明）⇒ C5 应红
  · M9 显式 limits 覆盖被忽略 ⇒ C2/C3 应红（限值不可覆盖）
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.QDR）——门禁走双路兜底可能绑成
   top-level 模块，另起 `from lda_qeda import ...` 会拿到不同实例 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_drc_loss_per_mode_smoke as S      # noqa: E402

QDR = S.QDR                                  # 同一模块对象（见文件头教训）


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

    _pd = QDR.per_mode_optical_depth
    _drc = QDR.run_quantum_drc
    _rules = QDR.QDR_RULES
    _disc = QDR.RED_LINE_DISCLOSURE
    _limits = QDR.DEFAULT_DRC_LIMITS

    # M1 每模口径删掉（恒 0 ⇒ 永不违规）
    QDR.per_mode_optical_depth = lambda ops, n_modes=None: 0
    rows.append(("M1 每模口径删掉（恒 0）", *run_smoke()))
    QDR.per_mode_optical_depth = _pd

    # M2 每模深度用 len(ops) 冒充
    QDR.per_mode_optical_depth = lambda ops, n_modes=None: len(ops)
    rows.append(("M2 每模深度 = len(ops)（冒充）", *run_smoke()))
    QDR.per_mode_optical_depth = _pd

    # M3 默认每模限值抹成 25（= 总口径）
    QDR.DEFAULT_DRC_LIMITS = dict(_limits, max_loss_per_mode_db=25.0)
    rows.append(("M3 每模限值抹成 25（= 总口径）", *run_smoke()))
    QDR.DEFAULT_DRC_LIMITS = _limits

    # M4 detail 不标口径（笼统「损耗超限」⇒ 不可追责）
    def _drc_vague(design, limits=None):
        d = _drc(design, limits=limits) if limits is not None else _drc(design)
        for v in d.get("violations", []):
            if v.get("rule") == "QDR-LOSS-BUDGET":
                v["detail"] = "损耗超限"
        return d

    QDR.run_quantum_drc = _drc_vague
    rows.append(("M4 detail 不标口径（不可追责）", *run_smoke()))
    QDR.run_quantum_drc = _drc

    # M5 per_mode_optical_depth 返回常量
    QDR.per_mode_optical_depth = lambda ops, n_modes=None: 7
    rows.append(("M5 每模深度返回常量 7", *run_smoke()))
    QDR.per_mode_optical_depth = _pd

    # M6 删掉 3 元组（矩形展平）支持
    def _pd_no3(ops, n_modes=None):
        if any(len(op) == 3 for op in ops):
            raise ValueError("仅支持 4 元组")
        return _pd(ops, n_modes)

    QDR.per_mode_optical_depth = _pd_no3
    rows.append(("M6 删掉 3 元组支持", *run_smoke()))
    QDR.per_mode_optical_depth = _pd

    # M7 披露抹掉
    QDR.RED_LINE_DISCLOSURE = {"role": "x"}
    rows.append(("M7 披露抹掉（缺 loss_basis）", *run_smoke()))
    QDR.RED_LINE_DISCLOSURE = _disc

    # M8 QDR_RULES 加一条（破坏兼容性声明）
    QDR.QDR_RULES = tuple(_rules) + ("QDR-LOSS-PER-MODE",)
    rows.append(("M8 QDR_RULES 加一条", *run_smoke()))
    QDR.QDR_RULES = _rules

    # M9 显式 limits 覆盖被忽略
    QDR.run_quantum_drc = lambda design, limits=None: _drc(design)
    rows.append(("M9 显式 limits 覆盖被忽略", *run_smoke()))
    QDR.run_quantum_drc = _drc

    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 74)
    print("突变探针：DRC 损耗每模口径门禁（D-124）")
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
