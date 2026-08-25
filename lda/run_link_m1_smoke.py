"""LDA P1-M1 验证 smoke · 通用链路框架 vs WDM 专用脚本（一致性回放）。

验证目标：lda_chain 通用级联引擎对 WDM 多环链路的结果，须与 wdm_system
的级联公式**逐波长一致**（同一 adddrop_spectrum 模型）。

参考采用 wdm_system._transfer + 同公式级联（不 round，精确），避免
system_metrics 的 round 误差污染对比；同时打印 system_metrics（round 版）
供人读对照。容差 1e-9（浮点运算顺序误差量级）。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)


def _ref_exact(channels_nm, Rs, gap, n_g):
    """精确参考（与 wdm_system.system_metrics 同公式，不 round）。"""
    from lda_agent.wdm_system import _transfer
    wls = [c * 1e-3 for c in channels_nm]
    drop_ij, thru_ij = [], []
    for R in Rs:
        d, t = _transfer(R, gap, wls)
        drop_ij.append(d)
        thru_ij.append(t)
    n = len(Rs)
    il, xt, thru = [], [], []
    for i in range(n):
        v = drop_ij[i][i]
        for k in range(i):
            v *= thru_ij[k][i]
        il.append(-10.0 * math.log10(max(v, 1e-9)))
        xs = []
        for j in range(n):
            if j == i:
                continue
            vv = drop_ij[j][i]
            for k in range(j):
                vv *= thru_ij[k][i]
            xs.append(-10.0 * math.log10(max(vv, 1e-9)))
        xt.append(min(xs))
    for j in range(n):
        v = 1.0
        for k in range(n):
            v *= thru_ij[k][j]
        thru.append(v)
    return il, xt, thru


def main() -> int:
    from lda_agent.wdm_system import (inverse_ring_for_channel, system_metrics)
    from lda_chain import build_wdm_link, simulate

    channels = [1550.0, 1552.5, 1555.0, 1557.5]
    n_g, gap = 4.2, 0.3
    Rs = [inverse_ring_for_channel(c * 1e-3, n_g) for c in channels]

    # 1) 通用框架
    link = build_wdm_link(channels, Rs, gap=gap, n_g=n_g)
    errs = link.validate()
    assert not errs, f"IR validate 失败: {errs}"
    wls = [c * 1e-3 for c in channels]
    sim = simulate(link, wls, sources=[("ring0", "in")])
    assert not sim["missing_models"], f"缺模型: {sim['missing_models']}"
    T = sim["transfers"]
    n = len(channels)

    il_c, xt_c, thru_c = [], [], []
    for i in range(n):
        v = max(T[f"ring0.in->ring{i}.drop"][i], 1e-9)
        il_c.append(-10.0 * math.log10(v))
    for i in range(n):
        xs = [max(T[f"ring0.in->ring{j}.drop"][i], 1e-9)
              for j in range(n) if j != i]
        xt_c.append(min(-10.0 * math.log10(x) for x in xs))
    for j in range(n):
        thru_c.append(T[f"ring0.in->ring{n - 1}.out"][j])

    # 2) 精确参考
    il_r, xt_r, thru_r = _ref_exact(channels, Rs, gap, n_g)

    # 3) 断言（容差 1e-9）
    tol = 1e-9
    checks = []
    for i in range(n):
        checks.append(("il_drop", i, il_c[i], il_r[i],
                       abs(il_c[i] - il_r[i])))
        checks.append(("xt_min", i, xt_c[i], xt_r[i],
                       abs(xt_c[i] - xt_r[i])))
        checks.append(("thru", i, thru_c[i], thru_r[i],
                       abs(thru_c[i] - thru_r[i])))

    max_err = max(c[4] for c in checks)
    ok = max_err <= tol

    # 4) FDTD 钩子接口（预留）可接
    def fake_fdtd(component, wls_um):
        return None
    sim2 = simulate(link, wls, sources=[("ring0", "in")], fdtd_hook=fake_fdtd)
    fdtd_ok = bool(sim2["transfers"])

    # 5) 人读对照（system_metrics round 版）
    sm = system_metrics(channels, Rs, gap, n_g)

    print("=" * 64)
    print("LDA P1-M1 · 通用链路框架 vs WDM 专用脚本（一致性回放）")
    print("=" * 64)
    print(f"信道(nm): {channels}")
    print(f"环半径(µm): {[round(r, 4) for r in Rs]}")
    print(f"IR validate: {'PASS' if not errs else 'FAIL ' + str(errs)}")
    print(f"缺模型器件: {sim['missing_models'] or '无'}")
    print(f"FDTD 钩子接口: {'可接' if fdtd_ok else '异常'}")
    print("-" * 64)
    print(f"{'指标':<10}{'通用引擎':>14}{'精确参考':>14}{'system_metrics':>16}{'max_err':>12}")
    for i in range(n):
        print(f"{'il_drop'+str(i):<10}{il_c[i]:>14.6f}{il_r[i]:>14.6f}"
              f"{sm['il_drop_db'][i]:>16.3f}{abs(il_c[i]-il_r[i]):>12.2e}")
        print(f"{'xt_min'+str(i):<10}{xt_c[i]:>14.6f}{xt_r[i]:>14.6f}"
              f"{sm['xt_min_db'][i]:>16.2f}{abs(xt_c[i]-xt_r[i]):>12.2e}")
        print(f"{'thru'+str(i):<10}{thru_c[i]:>14.6f}{thru_r[i]:>14.6f}"
              f"{sm['thru_at_channels'][i]:>16.5f}{abs(thru_c[i]-thru_r[i]):>12.2e}")
    print("-" * 64)
    print(f"最大误差 max_err = {max_err:.3e}  (容差 {tol:.0e})")
    print(f"结论: {'PASS — 通用框架与 WDM 级联逻辑逐波长一致' if ok else 'FAIL'}")
    print("=" * 64)

    # 额外：拓扑/IO 自检
    print(f"外部 IO 端口: {sim['io_ports']}")
    print(f"输入源: {sim['sources']}")
    print(f"输出 sink: {sim['sinks']}")
    print(f"transfers 键数: {len(sim['transfers'])}")

    return 0 if ok and fdtd_ok else 1


if __name__ == "__main__":
    sys.exit(main())
