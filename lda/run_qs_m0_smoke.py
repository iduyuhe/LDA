"""QS-M0 烟雾测试：跑通「NV 色心磁力计基线设计 + 守卫 + 反向探针」并落盘交付物。

量子传感器芯片征程（QS-M0）基线常驻门禁：selfcheck_qs_m0 全项判据
（钉住 8 项——Zeeman 闭式↔精确对角化互验 ×1 / 分裂正值 ×1 / 分裂对 B 线性 ×1 /
灵敏度闭式↔通用式互验 ×1 / η 有限正 ×1 / η 合理区间 ×1 / B=0 ⇒ Δf=0 反向探针 ×1 /
C=0 ⇒ η 病态 反向探针 ×1）+ 落盘报告交付物。

🔴 一次现算：`design_magnetometer_v0()` 的返回 rep 直接喂给 `selfcheck_qs_m0(rep=…)`
——判据复核与交付物共用**同一次**现算（纯 numpy，单次 <1s）。
纯 stdlib + numpy ⇒ 入 CI core 集（run_ci_regression.py）；timeout 120s 留 ≥100× 余量。

退出码 0=PASS，非 0=FAIL（CI 契约：rc==0?PASS:FAIL，绝不允许 main() 恒 0 假绿）。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_l2.qs_m0 import design_magnetometer_v0, selfcheck_qs_m0  # noqa: E402


def main(out_dir: str | None = None) -> int:
    # ① 一次现算：NV 磁力计基线设计（纯 numpy，<1s）
    rep = design_magnetometer_v0(run_layout=False)

    # ② 守卫复核（复用同一 rep，含反向探针）
    rep = selfcheck_qs_m0(rep=rep)
    sc = rep["selfcheck"]
    print("=" * 64)
    print("QS-M0 自校结果：", "PASS" if sc["all_pass"] else "FAIL")
    for k, v in sc["checks"].items():
        if k.endswith("_note"):
            print(f"  [----] {k}: {v}")
            continue
        # 行首 [PASS]/[FAIL] 口径 —— 供 W10 README「当前版本」行判据数机器对照
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    if not sc["all_pass"]:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 1

    # ③ 落盘报告（含 selfcheck 结论），供客户/审阅查看
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "qs_m0_report.json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)

    z = rep["zeeman"]
    s = rep["sensitivity"]
    bm = rep["benchmark"]
    print("-" * 64)
    print(f"  NV 色心磁力计 · T2*={rep['params']['T2star_us']} µs · "
          f"C={rep['params']['contrast']} · n_ph={rep['params']['n_ph_per_s']:.0e}/s")
    print(f"  Zeeman 分裂 @B={rep['params']['B_test_t']:.0e} T : "
          f"闭式 {z['split_closed_form_hz']:.1f} Hz ↔ 数值 {z['split_numeric_hz']:.1f} Hz "
          f"(rel_err={z['abs_rel_err']:.2e})")
    print(f"  磁灵敏度 η（光子散粒极限）= {s['eta_nT_per_sqrtHz']:.3f} nT/√Hz")
    print(f"  国际对标：芯片级 {bm['intl_state_of_art_chip_nT_per_sqrtHz']} nT/√Hz / "
          f"腔最优 {bm['intl_state_of_art_cavity_nT_per_sqrtHz']} nT/√Hz "
          f"(本档 gap={bm['gap_ratio_vs_chip']:.3f})")
    print(f"  交付物：{out_dir}")
    return 0


if __name__ == "__main__":
    _out = os.path.join(_HERE, "..", "outputs", "qs_m0")
    raise SystemExit(main(out_dir=_out))
