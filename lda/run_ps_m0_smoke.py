"""PS-M0 烟雾测试：跑通「指标计算 + 平台流片链路 + 反向探针」并落盘交付物。

光子传感器新征程（PS-M0）v0 环谐振折射率传感器基线常驻门禁：
selfcheck_ps_m0 全项判据（8 项——差商互验 central vs fwd ×2 / 灵敏度正值+区间 ×2 /
LOD 有限正 ×1 / Δn 符号反向探针 ×1 / 「抹平断口」S=0 ⇒ LOD=∞ 反向探针 ×1 /
主权流片链路 DRC 全过 + LVS 存在 ×1）+ 落盘 GDS/报告交付物。

🔴 一次现算：`design_sensor_v0(out_dir=…)` 的返回 rep 直接喂给 `selfcheck_ps_m0(rep=…)`
——判据复核与交付物共用**同一次**主权流片链（DRC/LVS 单次实测 ~26s），不重复跑。
纯 stdlib，单次 27.28s（3 轮 max，本机 @1T）⇒ 入 CI core 集（run_ci_regression.py）；
timeout 300s 留 ≥11× 余量。

退出码 0=PASS，非 0=FAIL（CI 契约：rc==0?PASS:FAIL，绝不允许 main() 恒 0 假绿）。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_l2.ps_m0 import design_sensor_v0, selfcheck_ps_m0  # noqa: E402


def main(out_dir: str | None = None) -> int:
    # ① 一次现算：指标 + 主权流片链（GDS/DRC/LVS）；out_dir 非空时落盘 GDS
    rep = design_sensor_v0(out_dir=out_dir)

    # ② 守卫复核（复用同一 rep，不重复跑流片链；含反向探针）
    rep = selfcheck_ps_m0(rep=rep)
    sc = rep["selfcheck"]
    print("=" * 64)
    print("PS-M0 自校结果：", "PASS" if sc["all_pass"] else "FAIL")
    for k, v in sc["checks"].items():
        if k.endswith("_note"):
            print(f"  [----] {k}: {v}")
            continue
        # 行首 [PASS]/[FAIL] 口径 —— 供 W10 README「当前版本」行判据数机器对照
        # （run_webui_pm_render_path_smoke `_pass_count` 按行首数 [PASS）。
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    if not sc["all_pass"]:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 1

    # ③ 落盘报告（含 selfcheck 结论），供客户/审阅查看
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "ps_m0_report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)

    s = rep["sensitivity"]
    ring = rep["ring_metrics"]
    lc = rep["layout_chain"]
    print("-" * 64)
    print(f"  波导 {s['w_um']}×{s['h_um']} µm  TE 基模 n_eff={s['neff']:.4f}  n_g={s['n_g']:.4f}")
    print(f"  顶部暴露体灵敏度 S = {s['S_nm_per_riu_top']:.2f} nm/RIU "
          f"（整包层上限 {s['S_nm_per_riu_whole']:.2f} nm/RIU）")
    print(f"  微环 R={ring['R_um']} µm  Q={ring['Q']:.0e}  FSR={ring['FSR_nm']:.3f} nm")
    print(f"  谐振线宽受限 LOD ≈ {ring['LOD_riu']:.3e} RIU")
    if "error" in lc:
        print(f"  流片链路：异常 ⇒ {lc['error']}")
    else:
        print(f"  流片链路：GDS {lc['gds_bytes']} B / {lc['n_elements']} 元素 / "
              f"DRC 全过={lc['drc_all_pass']} / LVS 存在={lc['lvs_present']}")
    print(f"  交付物：{out_dir}")
    return 0


if __name__ == "__main__":
    _out = os.path.join(_HERE, "..", "outputs", "ps_m0")
    raise SystemExit(main(out_dir=_out))
