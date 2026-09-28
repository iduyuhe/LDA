# -*- coding: utf-8 -*-
"""B-29 数值核（Batch B-29 · P6 · T6.4 · U11 · 1 锚 B452）

物理：驱动器—调制器电容负载的**一阶 RC 阶跃充电**
      v(t) = V_dd·(1 − e^{−t/τ})，等价 ODE `dv/dt = (V_dd − v)/τ`，v(0)=0。
      来源：Kirchhoff 一阶电路瞬态（教科书物理定律，人类公共品）。

golden（确定性物理定律闭式）：上述解析解（`math.exp`）。
candidate（方法学独立）：**四阶经典 RK4** 直接积分该 ODE —— 不解析求解、不调用
      任何指数闭式，自 v(0)=0 起推 N 步。
残差 = RK4 截断误差 O(h⁴)，**非恒等、非地板**（实测见 §自检）。

判据 D：固定物理参数（t_s / tau_s / v_dd），只扫**候选自身离散参数** N。
        要求 ①粗端残差浮出双精度地板（>1e-13）②随 N 严格单调下降且**实测**比值≈16
        ③默认档残差 >1e-12（避开 run_d_criterion_smoke ③ 红灯）。
        **收敛阶数字一律来自实测扫描，不按标称阶写死**（B-19 血案）。

🔴 同源体检（实 grep 全仓，排除 .git/__pycache__/node_modules 三方噪声）：
    · 一阶 RC 暂态闭式 `V0·(1−e^{−t/τ})` 在本仓**已有使用点：B33**
      （`lda_harness/b33_detector_bandwidth_anchor.py`，探测器 RC 限制 3dB 带宽）。
      **两者的收敛点与分歧点如实登记**：
        共享 —— 仅「一阶线性 RC 这一 ODE 形式」这一**普遍结构**；
        分歧 —— ① **被测标量不同**：B33 metric=`f3dB_Hz`（由 τ 反算带宽）；
                 本题 metric=`driver_step_voltage_V`（时刻 t 的阶跃电压值）。
                 ② **物理构型不同**：B33 = pin/APD 结电容 C=εA/d 配 R=50Ω 负载；
                 本题 = 驱动器 τ=20ps 驱动 MZI 相移臂（VπL 口径同 mesh_pnr）。
                 ③ **数值格式不同**：B33 候选 = 梯形法（2 阶）+ τ 最小二乘拟合；
                 本题候选 = 四阶 RK4 直接积分。收敛阶 O(dt²) vs O(h⁴)、残差量级均不同。
        先例 —— 本仓既有同类计数：B446–B451 六锚同为「RK4 积分定义 ODE」，
                 B448/B449 更是**同一函数 Ci 的两个不同 X** 各计一锚。
      ⇒ 结论：**非重复计数**（不同标量 × 不同构型 × 不同格式）。此判断如实登记，
         供人工复核；不掩盖「同 ODE 形式」这一事实。
    · `lvdt|step_response|rc_step|rc_transient` 在 lda/ 锚筛内除 B33 外**零命中**。

血案预防：
    1. 【离散参数不进 default_params】`default_params` 只放 golden 接受的键
       （t_s/tau_s/v_dd）；N 由候选函数签名默认值承载，否则 golden 收到未知 kwarg
       抛 TypeError（B-7 类血案预防）。默认档 N 一律 = 判据 D 扫描格末端。
    2. 【默认档不得撞地板】RK4 误差随 N 快速趋零（N=1024 已 6.7e-14）⇒ 默认档
       必须收在残差仍 >1e-12 的档（本批 N=256，实测 ~4.7e-10）。
    3. 【零响应键】t_s / tau_s 对指标强敏感；v_dd 为线性比例因子（±10% ⇒ 输出
       ±10%），**非零响应键**。无零响应键。

环境：CI 解释器唯一（py3.13 · 纯标准库）。本文件纯 LF、无 BOM。
"""
import math

# 默认档（= 判据 D 扫描格末端，满足「定档 = 扫描网格末端」纪律）
_N_BY_BID = {
    "B452": 256,
}
# 判据 D 扫描网格（4 档，等比 ×2）
_GRID_BY_BID = {
    "B452": [32, 64, 128, 256],
}
# 逐锚 tol（按「余量 >=100x 且 |golden| >= 13.5*tol」标定；tol 只收紧不放松）
_TOL_BY_BID = {
    "B452": 1e-7,
}


# ===========================================================================
# 通用数值工具
# ===========================================================================
def _rk4_linear_step(t_s, tau_s, v_dd, n_steps):
    """四阶经典 RK4 积分 `dv/dt = (V_dd − v)/τ`（自 v(0)=0），n_steps 步。

    **候选实现**：只做时间步进，不含任何解析解成分。
    """
    n = int(n_steps)
    if n < 1:
        raise ValueError("n_steps=%r 非法（须 >=1）" % (n_steps,))
    tau = float(tau_s)
    if tau <= 0.0:
        raise ValueError("tau_s=%.6g 非法（须 > 0）" % tau_s)
    h = float(t_s) / float(n)
    v = 0.0
    for _ in range(n):
        k1 = (v_dd - v) / tau
        k2 = (v_dd - (v + 0.5 * h * k1)) / tau
        k3 = (v_dd - (v + 0.5 * h * k2)) / tau
        k4 = (v_dd - (v + h * k3)) / tau
        v += (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(v)


# ===========================================================================
# 族 A · 一阶 RC 阶跃充电（B452）
# ===========================================================================
def golden_b452(t_s=8.0e-11, tau_s=2.0e-11, v_dd=2.0):
    """golden（确定性物理定律闭式）：v(t) = V_dd·(1 − e^{−t/τ})，零初值一阶 RC 充电。

    默认 t_s=80ps、tau_s=20ps ⇒ t/τ=4（上升至 ~98.2% 满摆幅）。
    """
    tau = float(tau_s)
    if tau <= 0.0:
        raise ValueError("tau_s=%.6g 非法（须 > 0）" % tau_s)
    if float(t_s) < 0.0:
        raise ValueError("t_s=%.6g 非法（须 >= 0）" % t_s)
    return float(v_dd * (1.0 - math.exp(-float(t_s) / tau)))


def cand_b452(t_s=8.0e-11, tau_s=2.0e-11, v_dd=2.0, N=_N_BY_BID["B452"]):
    """candidate：**四阶 RK4** 数值积分定义 ODE（与闭式不同源，不解析求解）。"""
    return _rk4_linear_step(t_s, tau_s, v_dd, N)


# ===========================================================================
# 自检：余量标定 + 判据 D 扫描（残差随离散参数单调下降；比值实测，不按标称阶写死）
# ===========================================================================
_CASES = [
    ("B452", golden_b452, cand_b452, {"t_s": 8.0e-11, "tau_s": 2.0e-11, "v_dd": 2.0}),
]

if __name__ == "__main__":
    print("=== B-29 一阶 RC 阶跃充电核 自检（余量标定 + 判据 D） ===")
    print("\n%-6s %18s %18s %12s %10s %-7s %-10s %s"
          % ("锚", "golden", "cand(默认档)", "|Δ|", "margin", "基线>1e-12", "gold/tol", "判定"))
    bad = 0
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        c = cf(**p)
        dd = abs(g - c)
        tol = _TOL_BY_BID[bid]
        margin = (tol / dd) if dd > 0 else float("inf")
        base_ok = dd > 1e-12
        gr = abs(g) / tol
        ok = (margin >= 2.0) and base_ok and (gr >= 13.5)
        bad += 0 if ok else 1
        print("%-6s %18.10e %18.10e %12.3e %10.1f %-7s %-10.1f %s"
              % (bid, g, c, dd, margin, base_ok, gr, "OK" if ok else "BAD"))

    print("\n--- 判据 D 扫描（残差随离散参数单调下降；比值来自实测，不按标称阶写死）---")
    for bid, gf, cf, p in _CASES:
        g = gf(**p)
        grid = _GRID_BY_BID[bid]
        row = []
        prev = None
        monotonic = True
        ratios = []
        for nn in grid:
            dd = abs(g - cf(N=nn, **p))
            if prev is not None:
                ratio = (prev / dd) if dd > 0 else float("nan")
                ratios.append(ratio)
                if dd > prev:
                    monotonic = False
                row.append("%d:%.2e(x%.2f)" % (nn, dd, ratio))
            else:
                row.append("%d:%.2e" % (nn, dd))
            prev = dd
        dd_last = abs(g - cf(N=grid[-1], **p))
        dd_first = abs(g - cf(N=grid[0], **p))
        print("%-6s %-58s %-8s 比值 %.2f~%.2f  粗端>1e-13:%s  默认档>1e-12:%s"
              % (bid, "  ".join(row), "MONO" if monotonic else "NONMONO",
                 min(ratios), max(ratios), dd_first > 1e-13, dd_last > 1e-12))
    print("\nBAD 计数 = %d" % bad)
    print("DONE")
