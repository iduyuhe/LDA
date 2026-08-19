"""LDA · 真 2D 波导验收脚本（独立方法互验 + dual-PASS 判决）。

目的：证明「agent 设计结果侧（时域 FDTD）」与「物理定律锚 ORACLE（频域闭式 slab）」
对**同一几何**给出一致的基模 neff —— 两套方法、两套代码、两个独立实现交叉校验，
排除单一实现 bug；LLM 不进判决路径（见 L0 IR §5 / 排雷①②）。

几何约定：条形波导 (x,z) slab —— x∈[-w/2,w/2] 受限、y 均匀、z 传播，TE 极化。
  · FDTD 侧 ：lda_solver/fdtd2d_waveguide（2D-TE 时域，双监视点 DFT 相位差）
  · ORACLE 侧：lda_harness/oracle_mode._slab_te_neff（对称 slab TE 基模闭式特征方程）
  · FDFD 侧  ：oracle_mode.fdfd_neff 为**全横截面**(x,y 双受限)本征模，属不同几何，
              仅作旁证，不作为本 slab 几何的验收锚（其 neff 天然低于 slab）。

dual-PASS 判据（每项独立）：
  PASS-1  物理合法性：n_clad < neff_fdtd < n_core（时域解未发散 / 未退化）
  PASS-2  方法一致性：|neff_fdtd − neff_oracle| / neff_oracle ≤ tolerance_rel
两项皆 PASS ⇒ 该器件「真 2D 器件验收闭环」成立。
"""
from __future__ import annotations

import os
import sys
import math

_HERE = os.path.dirname(os.path.abspath(__file__))
_SOLVER = os.path.join(_HERE, "..", "lda_solver")
_HARNESS = os.path.join(_HERE, "..", "lda_harness")
for _p in (_SOLVER, _HARNESS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fdtd2d_waveguide import build_waveguide_field, solve_waveguide_neff  # noqa: E402
from oracle_mode import _slab_te_neff, fdfd_neff                           # noqa: E402


# (label, w_um, n_core, n_clad, wl_um)
BENCHMARKS = [
    ("Si/SiO2 紧约束 0.5µm", 0.5, 3.48, 1.44, 1.55),
    ("SiN/SiO2 松约束 0.5µm", 0.5, 2.00, 1.44, 1.55),
    ("Si/SiO2 宽波导 1.0µm", 1.0, 3.48, 1.44, 1.55),
]

TOLERANCE_REL = 0.02   # 2% 相对误差验收公差


def verify_one(label, w, n_co, n_cl, wl, dl_factor=32):
    eps2, dl = build_waveguide_field(w, n_co, n_cl, wl, dl=wl / dl_factor)
    ne_fdtd, beta, m, snr = solve_waveguide_neff(
        eps2, dl, wl, n_clad=n_cl, n_core=n_co, debug=True)
    ne_oracle = _slab_te_neff(n_co, n_cl, w / 2.0, wl)     # a = 半厚
    # FDFD：全横截面（x,y 双受限），几何不同 → 仅旁证
    ne_fdfd = fdfd_neff(w, w, n_co, n_cl, wl, wl / dl_factor)

    rel = abs(ne_fdtd - ne_oracle) / ne_oracle
    pass1 = (n_cl * 1.001 < ne_fdtd < n_co * 0.999)
    pass2 = rel <= TOLERANCE_REL
    dual = pass1 and pass2
    return {
        "label": label, "w": w, "n_co": n_co, "n_cl": n_cl, "wl": wl,
        "ne_fdtd": ne_fdtd, "ne_oracle": ne_oracle, "ne_fdfd": ne_fdfd,
        "rel_err": rel, "snr": snr, "m": m,
        "pass1": pass1, "pass2": pass2, "dual": dual,
    }


def main():
    print("=" * 78)
    print("LDA · 真 2D 波导验收（时域 FDTD × 频域 slab ORACLE 独立互验）")
    print("=" * 78)
    print(f"{'器件':<24}{'neff FDTD':>11}{'slab ORACLE':>13}{'FDFD*':>9}"
          f"{'rel err':>10}{'snr':>7}  verdict")
    print("-" * 78)
    all_pass = True
    for args in BENCHMARKS:
        r = verify_one(*args)
        verdict = ("DUAL-PASS ✅" if r["dual"]
                   else ("PASS-1 ✅ / PASS-2 ❌" if r["pass1"] else "发散 ❌"))
        if not r["dual"]:
            all_pass = False
        print(f"{r['label']:<24}{r['ne_fdtd']:>11.5f}{r['ne_oracle']:>13.5f}"
              f"{r['ne_fdfd']:>9.5f}{r['rel_err']:>9.2%}{r['snr']:>7.3f}  {verdict}")
    print("-" * 78)
    print("* FDFD 为全横截面(x,y 双受限)本征模，几何不同于本 slab 验收几何，"
          "仅作旁证（其 neff 天然低于 slab，不代表误差）。")
    print("=" * 78)
    verdict_txt = ("全部 DUAL-PASS，真 2D 器件验收闭环成立 ✅"
                   if all_pass else "存在未通过项 ❌")
    print(f"总体结论 : {verdict_txt}")
    print("=" * 78)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
