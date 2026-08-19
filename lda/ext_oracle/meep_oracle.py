"""LDA 外部场级 ORACLE（GPL 隔离，子进程调用）。

=====================================================================
许可证红线（见《LDA 技术白皮书》§11）：
  Meep / Tidy3D / MPB 均为 **GPL** 代码。LDA 核心是 Apache-2.0，
  二者许可证不兼容——GPL 求解器**绝不能被 import 进 LDA 核心**。
  本文件是"外部 ORACLE"：在装有 Meep 的**隔离 venv/容器**中运行，
  只把标量 metric 以 JSON 回传，LDA 核心只用其数值，永不触碰其代码。

运行方式（在 GPL 隔离环境，不要混进核心 venv）：
  pip install meep
  python meep_oracle.py --bid B7 --params '{"w_core":0.4,...}' --json
  输出： {"value": -32.1, "source": "meep-fdtd", "note": "..."}

LDA 核心调用（oracle_field.py 内，子进程，不 import）：
  out = subprocess.run([MEEP_PY, "meep_oracle.py", "--bid", bid,
                        "--params", json.dumps(params), "--json"], ...)
  return json.loads(out.stdout)
=====================================================================

本脚本对 B5(Y 分支)、B7(波导交叉) 做 **2D FDTD 场级求解**；B6(光栅耦合器)
为 3D 问题，预留 Tidy3D 接口（需 API key，单独脚本）。
"""

import sys
import json
import argparse


def _sim_crossing(params):
    """B7 波导交叉串扰(dB) — Meep 2D FDTD 场级真值。

    两条等宽波导在中心 90° 交叉。从西端口注入基模，测量四端口功率：
      through(东) / cross(北) / bar-左(西反射) / bar-右(南)。
    串扰 = 10·log10(P_cross / P_through)。越负越好。
    """
    import meep as mp

    wl = params.get("wl", 1.55)
    w = params.get("w_core", 0.4)
    h = params.get("h_core", 0.22)
    n_si = params.get("n_si", 3.48)
    n_clad = params.get("n_clad", 1.44)

    # 2D 近似：用有效折射率把 3D 条形波导压成 2D 平板（厚度方向已积分）。
    # 这里直接用 n_si 作平板折射率（保守近似；如需更准可先算 n_eff）。
    eps_core = n_si ** 2
    eps_clad = n_clad ** 2

    sx = sy = 8.0  # 仿真域(um)
    cell = mp.Vector3(sx, sy, 0)
    resolution = 30  # 网格/um -> dx≈0.033um

    # 十字波导几何：水平 + 垂直两条
    waveguide_material = mp.Medium(epsilon=eps_core)
    bg = mp.Medium(epsilon=eps_clad)
    geometry = [
        mp.Block(size=mp.Vector3(sx, w, mp.inf),
                 center=mp.Vector3(0, 0, 0),
                 material=waveguide_material),  # 水平
        mp.Block(size=mp.Vector3(w, sy, mp.inf),
                 center=mp.Vector3(0, 0, 0),
                 material=waveguide_material),  # 垂直
    ]

    fcen = 1.0 / wl
    df = fcen * 0.2
    src_pt = mp.Vector3(-sx / 2 + 0.6, 0, 0)
    sources = [mp.EigenModeSource(
        src=mp.GaussianSource(fcen, fwidth=df),
        center=src_pt, size=mp.Vector3(0, 2 * w, 0),
        direction=mp.X, eig_band=1, eig_parity=mp.ODD_Z,
    )]

    # 四端口通量监视器
    d = 0.6
    flux_regions = {
        "through": mp.FluxRegion(center=mp.Vector3(sx / 2 - d, 0, 0),
                                 size=mp.Vector3(0, 2 * w, 0)),
        "cross": mp.FluxRegion(center=mp.Vector3(0, sy / 2 - d, 0),
                               size=mp.Vector3(2 * w, 0, 0)),
        "bar_left": mp.FluxRegion(center=mp.Vector3(-sx / 2 + d, 0, 0),
                                  size=mp.Vector3(0, 2 * w, 0)),
        "bar_right": mp.FluxRegion(center=mp.Vector3(0, -sy / 2 + d, 0),
                                   size=mp.Vector3(2 * w, 0, 0)),
    }
    flux_objs = {k: mp.Flux(fcen, 0, 1, r) for k, r in flux_regions.items()}

    sim = mp.Simulation(cell_size=cell, resolution=resolution,
                        geometry=geometry, sources=sources,
                        boundary_layers=[mp.PML(1.0)],
                        default_material=bg)
    sim.run(until=400)
    fluxes = {k: mp.get_fluxes(v) for k, v in flux_objs.items()}
    p_in = abs(fluxes["through"][0]) + abs(fluxes["bar_left"][0])  # 入/反
    p_thr = abs(fluxes["through"][0])
    p_cr = abs(fluxes["cross"][0])
    if p_thr <= 1e-12:
        return {"value": -10.0, "source": "meep-fdtd",
                "note": "through 端口功率过低，结果不可靠"}
    crosstalk_dB = 10.0 * (p_cr / p_thr).real if False else 10.0 * __import__("math").log10(max(p_cr / p_thr, 1e-12))
    return {"value": float(crosstalk_dB), "source": "meep-fdtd",
            "note": f"2D FDTD; P_through={p_thr:.4g} P_cross={p_cr:.4g}"}


def _sim_ybranch(params):
    """B5 Y 分支 1×2 分束插入损耗(dB) — Meep 2D FDTD 场级真值。

    单输入波导在分叉点分成两条夹角 theta 的臂。注入基模，测两臂通量之和
    （已相对输入归一化），插入损耗 = -10·log10(P_arm1 + P_arm2)。
    """
    import meep as mp

    wl = params.get("wl", 1.55)
    w = params.get("w_core", 0.4)
    theta_deg = params.get("theta_deg", 15.0)
    n_si = params.get("n_si", 3.48)
    n_clad = params.get("n_clad", 1.44)

    eps_core = n_si ** 2
    eps_clad = n_clad ** 2
    sx = sy = 8.0
    cell = mp.Vector3(sx, sy, 0)
    resolution = 25
    theta = __import__("math").radians(theta_deg)
    half_len = 3.0
    waveguide_material = mp.Medium(epsilon=eps_core)
    bg = mp.Medium(epsilon=eps_clad)

    # 输入臂（沿 +X）+ 两条分叉臂（旋转 ±theta）
    geometry = [
        mp.Block(size=mp.Vector3(half_len, w, mp.inf),
                 center=mp.Vector3(-half_len / 2, 0, 0),
                 material=waveguide_material),
        mp.Block(size=mp.Vector3(half_len, w, mp.inf),
                 center=mp.Vector3(half_len / 2 * __import__("math").cos(theta),
                                   half_len / 2 * __import__("math").sin(theta), 0),
                 e1=mp.Vector3(__import__("math").cos(theta), __import__("math").sin(theta), 0),
                 e2=mp.Vector3(-__import__("math").sin(theta), __import__("math").cos(theta), 0),
                 material=waveguide_material),
        mp.Block(size=mp.Vector3(half_len, w, mp.inf),
                 center=mp.Vector3(half_len / 2 * __import__("math").cos(theta),
                                   -half_len / 2 * __import__("math").sin(theta), 0),
                 e1=mp.Vector3(__import__("math").cos(theta), -__import__("math").sin(theta), 0),
                 e2=mp.Vector3(__import__("math").sin(theta), __import__("math").cos(theta), 0),
                 material=waveguide_material),
    ]

    fcen = 1.0 / wl
    df = fcen * 0.2
    sources = [mp.EigenModeSource(
        src=mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx / 2 + 0.6, 0, 0),
        size=mp.Vector3(0, 2 * w, 0),
        direction=mp.X, eig_band=1, eig_parity=mp.ODD_Z,
    )]
    d = 0.6
    arm1 = mp.FluxRegion(center=mp.Vector3(half_len * __import__("math").cos(theta),
                                           half_len * __import__("math").sin(theta), 0),
                         size=mp.Vector3(0, 2 * w, 0))
    arm2 = mp.FluxRegion(center=mp.Vector3(half_len * __import__("math").cos(theta),
                                           -half_len * __import__("math").sin(theta), 0),
                         size=mp.Vector3(0, 2 * w, 0))
    fin = mp.FluxRegion(center=mp.Vector3(-sx / 2 + d, 0, 0),
                        size=mp.Vector3(0, 2 * w, 0))
    f_arm1 = mp.Flux(fcen, 0, 1, arm1)
    f_arm2 = mp.Flux(fcen, 0, 1, arm2)
    f_in = mp.Flux(fcen, 0, 1, fin)
    sim = mp.Simulation(cell_size=cell, resolution=resolution,
                        geometry=geometry, sources=sources,
                        boundary_layers=[mp.PML(1.0)],
                        default_material=bg)
    sim.run(until=500)
    p_in = abs(mp.get_fluxes(f_in)[0])
    p_out = abs(mp.get_fluxes(f_arm1)[0]) + abs(mp.get_fluxes(f_arm2)[0])
    if p_in <= 1e-12:
        return {"value": 3.0, "source": "meep-fdtd",
                "note": "input flux 过低"}
    split_loss_dB = -10.0 * __import__("math").log10(max(p_out / p_in, 1e-12))
    return {"value": float(split_loss_dB), "source": "meep-fdtd",
            "note": f"2D FDTD; P_in={p_in:.4g} P_out={p_out:.4g}"}


def _sim_grating(params):
    """B6 光栅耦合器峰值效率 — 预留 Tidy3D（3D，需 API key）。

    当前返回 None；真实实现应在 Tidy3D 云环境扫光纤角度/周期取峰值效率。
    """
    return None


DISPATCH = {"B5": _sim_ybranch, "B6": _sim_grating, "B7": _sim_crossing}


def run(bid, params):
    fn = DISPATCH.get(bid)
    if fn is None:
        return {"value": None, "source": "none", "note": f"未实现 bid={bid}"}
    try:
        return fn(params)
    except Exception as e:  # 隔离环境内异常不外泄到核心
        return {"value": None, "source": "error", "note": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bid", required=True)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    params = json.loads(args.params)
    res = run(args.bid, params)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
