"""LDA · L3 自研 1D FDTD 核 · 物理定律锚（TMM 解析解）交叉校验闭环。

机器优先：跑多个解析可判定的干净结构，FDTD 谱 vs TMM 谱断言一致。
判据用"物理特征是否复现"（禁带/条纹/幅度），不苛求逐点绝对吻合——
因 1D FDTD 归一化 DFT 测量绝对幅度偏保守属已知近似。

关键：测试用例均为解析已知量，排除"对布拉格禁带位置判断错误"这类干扰。
"""
from __future__ import annotations

import math
import os
import sys

# 把 lda 包根目录（D:/agent_LDA）加入搜索路径，支持直接运行脚本
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
from lda.lda_solver.fdtd1d import solve_spectrum
from lda.lda_solver.tmm import solve_spectrum as tmm_solve_spectrum


def _tmm_T(layers, wls):
    out = tmm_solve_spectrum({"layers": layers, "wavelengths_um": wls})
    return list(out["transmission"])


def _report(name, layers, wls, tol):
    print(f"\n=== {name} ===")
    fd = solve_spectrum({"layers": layers, "wavelengths_um": wls})
    tf = fd["transmission"]
    tt = _tmm_T(layers, wls)
    print(f"  {'wl(um)':>8} {'FDTD_T':>9} {'TMM_T':>9} {'delta':>8}")
    for w, a, b in zip(wls, tf, tt):
        print(f"  {w:>8.3f} {a:>9.4f} {b:>9.4f} {abs(a-b):>8.4f}")
    max_err = max(abs(a - b) for a, b in zip(tf, tt))
    # 特征判据：全谱趋势一致（max|ΔT| 在宽容差内）
    ok = max_err < tol
    print(f"  max|ΔT| = {max_err:.4f}  -> {'PASS' if ok else 'FAIL'} (tol={tol})")
    return ok


def main():
    print(">> LDA 自研 1D FDTD 求解（C 级自主，机器优先接口）交叉校验")
    print(">> ORACLE = TMM 多层膜传输矩阵解析解（物理定律锚，非 AI）")

    cases = []

    # 用例 A：匹配介质（无界面）→ 透射应恒为 1.0（sanity）
    wls = [1.3, 1.4, 1.5, 1.6]
    layers_match = [(float('inf'), 1.44), (float('inf'), 1.44)]
    cases.append(("A. 匹配介质 (T≡1.0)", layers_match, wls, 0.02))

    # 用例 B：单界面 空气(1.0)/玻璃(1.5) → R=((1.5-1)/(1.5+1))²=0.04, T=0.96
    layers_iface = [(float('inf'), 1.0), (float('inf'), 1.5)]
    cases.append(("B. 单界面 空气→玻璃 (T≡0.96)", layers_iface, wls, 0.04))

    # 用例 C：法布里-珀罗标准具 —— n=2.5 薄膜 d=2.0µm 夹在空气间，产生条纹
    layers_fp = [(float('inf'), 1.0), (2.0, 2.5), (float('inf'), 1.0)]
    wls_fp = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2]
    cases.append(("C. FP 标准具 n=2.5 d=2.0um (条纹)", layers_fp, wls_fp, 0.06))

    # 用例 D：布拉格光栅（空气包层，高对比 Si/SiO2 周期，禁带应被复现）
    n_h, n_l, period = 3.48, 1.44, 0.50
    lam_b = 2 * ((n_h + n_l) / 2) * period   # 布拉格中心 ≈ 2.46µm
    layers_bg = ([(float('inf'), 1.44)] +
                 [(0.25, n_h), (0.25, n_l)] * 24 +
                 [(float('inf'), 1.44)])
    # 在禁带中心附近采样（1.9~3.0µm），预期 T 普遍偏低
    wls_bg = [1.9, 2.2, 2.46, 2.7, 3.0]
    cases.append((f"D. 布拉格光栅 (中心≈{lam_b:.2f}um 禁带)", layers_bg, wls_bg, 0.10))

    all_ok = True
    for name, layers, wls_c, tol in cases:
        ok = _report(name, layers, wls_c, tol)
        all_ok = all_ok and ok

    print("\n" + "=" * 48)
    print(">> 总判定：", "PASS — 自研核通过物理定律锚校验" if all_ok
          else "FAIL — 自研核未通过校验，需排查")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
