"""D-60: κ_c(gap,λ) 全网格 PDK 标定（2D FDTD 双点差分，后台运行）。

9 点网格（gap={0.25,0.30,0.35} × λ={1.50,1.55,1.60}），dl_factor=20。
产出 lda_agent/data/kappa_grid_calibration.json（二维网格 + 元数据），
供 wdm_coupler grid_calibrated 模式双线性插值（替代 D-59 分离变量近似）。
"""

import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lda_solver.fdtd2d_coupler import (  # noqa: E402
    build_dc_field, dc_transmission_spectrum,
)

GAPS = [0.25, 0.30, 0.35]
WLS = [1.50, 1.55, 1.60]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "data", "kappa_grid_calibration.json")


def kappa_fdtd(gap, wl, dl_factor=20):
    """双点差分标定（D-55 方法）。"""
    def measure(Lx):
        spec = dc_transmission_spectrum(0.5, gap, 3.48, 1.44, [wl],
                                        Lx_um=Lx, dl_factor=dl_factor,
                                        transient_cycles=350, M_cycles=45)
        dl = spec["dl_um"]
        _, _, Nx, _, _ = build_dc_field(0.5, gap, 3.48, 1.44, dl, Lx_um=Lx)
        L_eff = (Nx - 2 * 40 - 12) * dl
        cf = min(max(spec["cross_frac"][0], 0.0), 0.999)
        return L_eff, cf

    L1, c1 = measure(26.0)
    L2, c2 = measure(52.0)
    winding = (c2 < c1) or (c1 > 0.6)
    if winding:
        k = math.asin(math.sqrt(c1)) / L1 if c1 > 1e-3 else 0.0
    else:
        k = (math.asin(math.sqrt(c2)) - math.asin(math.sqrt(c1))) / (L2 - L1)
    return k, c1, c2, winding


def main():
    t0 = time.time()
    points = []
    for gap in GAPS:
        for wl in WLS:
            k, c1, c2, w = kappa_fdtd(gap, wl)
            points.append({"gap_um": gap, "wl_um": wl,
                           "kappa_c_rad_um": round(k, 6),
                           "cf1": round(c1, 3), "cf2": round(c2, 3),
                           "winding": w})
            print(f"gap={gap} λ={wl}: κ_c={k:.5f} (cf1={c1:.3f} "
                  f"cf2={c2:.3f} 缠绕={w})", flush=True)
    calib = {
        "name": "LDA kappa_c(gap,λ) 全网格 PDK 标定（2D FDTD 双点差分）",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "w_um": 0.5, "n_core": 3.48, "n_clad": 1.44,
        "dl_factor": 20, "dl_um": 0.0775,
        "gaps_um": GAPS, "wls_um": WLS,
        "method": "kappa_c 双点差分标定（D-55），全网格 (gap×λ) 9 点",
        "note": "二维网格直接查表（双线性插值），替代 D-59 分离变量近似；"
                "诚实标注：dl=0.078µm 分辨 gap≥0.1µm，κ_c 非严格单调（网格"
                "色散噪声）；winding=True 点 κL 越过 π/2（asin 折叠，降级单点）。",
        "points": points,
        "elapsed_s": round(time.time() - t0, 1),
    }
    json.dump(calib, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              indent=2)
    print(f"已保存 {OUT} | {len(points)} 点 | 耗时 {calib['elapsed_s']}s",
          flush=True)


if __name__ == "__main__":
    main()
