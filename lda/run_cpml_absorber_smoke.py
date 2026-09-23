"""v0.9.133 P4-G11 · 真 PML（CFS-PML）回反射门禁（里程碑 **M-4** 上半）。

## 为什么建它

`fdtd2d` / `fdtd3d` 的吸收边界一直是**梯度二次型导电海绵**（代码自述
「无 Mur-ABC、无 CPML」）。规划 P4 要的不是「换个名字」，而是
**「回反射系数机器可证下降 + 判据 D」** —— 本 smoke 把这句话变成 12 组死判据。

## 测量仪（`lda_solver/fdtd_cpml.py`）

退化一维脉冲 + **时域门控**：软源打高斯包络脉冲，监视点在源与左边界之间；
`t_inc` / `t_ref` 解析可算 ⇒ 两个互不重叠的窗口；
`Γ = √(ΣE²_ref / ΣE²_inc)` 是**同点比值** ⇒ 无需绝对定标。

## 本 smoke 断言 12 件事（每条都是可证伪的死标量）

  ① CPML 剖面不变量：物理区 b≡1 / c≡0 / κ≡1；内边缘 σ=0 且 κ=1（**无阻抗跳变**）
  ② 半格偏移口径：`b_h ≠ 平均(b_e)`（b 对 σ 非线性 ⇒ 不可平均系数 —— 防实现退化）
  ③ 仪器灵敏度：`n_abs=0`（截断差分 ⇒ 全反射）时 Γ > 0.9 —— 证明测量对「有无吸收」敏感
  ④ CPML 回反射 **优于海绵 50× 以上**（2D x 轴，同层厚 40）
  ⑤ 同上（2D y 轴）—— 两轴对称，防「只对一个轴接对」
  ⑥ 同上（3D x/y/z 三轴）—— 防「2D 特判」
  ⑦ **判据 D**：固定 σ_max，扫 n_abs ∈ {10, 20, 40} ⇒ Γ **严格单调降**、
     粗端 > 1e-13（未落地板）、细端 < 1e-3
  ⑧ 海绵对照序列**如实登记**（实测**也**单调 ⇒ 不冒充「只有 CPML 有判据 D」）
  ⑨ 传播子零改动：回波到达前 CPML 与海绵波形差 ≤ 1e-12×入射峰（实测噪声地板）
  ⑩ 结构零影响：`fdtd2d.py` / `fdtd3d.py` 源码**不含** `cpml`（本批未接线）
  ⑪ 既有默认签名不变（`sponge` / `target_exp` / `dl_factor` 逐项）
  ⑫ 判决依据零 LLM / 零网络（扫**登记数据**，不扫源码 —— 防自扫假红）

> ⑩⑪ 红了**不是**缺陷，而是提醒：把 CPML 接进默认路径 = 改全部 FDTD 依赖锚的
> 数值 ⇒ 必须重跑锚验证后才可放开。这是**故意的变更探测器**。

运行：python run_cpml_absorber_smoke.py
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

from lda_harness.smoke_kit import make_check                    # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

N_ABS = 40               # 对照/判据用的层厚
SIGMA_MAX = 18.0         # 判据 D 的**固定** σ_max（不可用 σ_opt：σ_opt ∝ 1/L ⇒ 无判据 D）
N_ABS_SCAN = (10, 20, 40)
IMPROVE_X = 50.0         # CPML 必须比海绵好多少倍（死标量）
PURE_REL_TOL = 1e-12     # 回波到达前的「传播子一致」相对容差
GAMMA_TOL = 1e-3         # 判据 D 的细端容差


def _strictly_decreasing(v):
    return all(v[i] > v[i + 1] for i in range(len(v) - 1))


def main() -> int:
    t0 = time.time()
    from lda_solver import fdtd_cpml as fc
    from lda_solver import cpml as cm

    # ---------------------------------------------------------------
    # ① CPML 剖面不变量
    # ---------------------------------------------------------------
    dl, dt, n, n_abs = 0.05, 0.0336, 400, N_ABS
    ax = cm.cpml_axis(n, n_abs, dt, dl, sigma_max=SIGMA_MAX)
    inner = slice(n_abs, n - n_abs)
    ok_prof = (bool((ax["b_e"][inner] == 1.0).all())
               and bool((ax["c_e"][inner] == 0.0).all())
               and bool((ax["kappa_e"][inner] == 1.0).all()))
    check("① CPML 物理区逐位恒等（b≡1 / c≡0 / κ≡1 ⇒ 不污染物理区）",
          ok_prof,
          "b/c/κ 偏离计数 %d/%d/%d"
          % (int((ax["b_e"][inner] != 1.0).sum()),
             int((ax["c_e"][inner] != 0.0).sum()),
             int((ax["kappa_e"][inner] != 1.0).sum())))
    edge = (float(ax["sigma"][0]), float(ax["sigma"][n_abs - 1]),
            float(ax["kappa"][n_abs - 1]), float(ax["kappa"][0]))
    check("① PML 内边缘无阻抗跳变（σ=0 且 κ=1）",
          edge[1] == 0.0 and edge[2] == 1.0,
          "内边缘 σ=%.3e κ=%.6f · 外边缘 σ=%.3e κ=%.6f"
          % (edge[1], edge[2], edge[0], edge[3]))

    # ---------------------------------------------------------------
    # ② 半格偏移口径（b 对 σ 非线性 ⇒ 必须先平均剖面再算系数）
    # ---------------------------------------------------------------
    wrong = 0.5 * (ax["b_e"][:-1] + ax["b_e"][1:])
    dver = float(abs(ax["b_h"][:-1] - wrong).max())
    check("② 半格系数口径正确（b_h ≠ 平均(b_e) ⇒ 未退化为平均系数）",
          dver > 0.0, "|b_h − mean(b_e)| 最大 %.3e" % dver)

    # ---------------------------------------------------------------
    # ③ 仪器灵敏度：无吸收 ⇒ 截断差分全反射 ⇒ Γ ≈ 1
    # ---------------------------------------------------------------
    gamma_noabs = {}
    for dim in (2, 3):
        gamma_noabs[dim] = fc.measure_reflection(
            dim=dim, axis=0, absorber="cpml", n_abs=0)["gamma"]
    check("③ 仪器灵敏度：n_abs=0（无吸收）⇒ Γ > 0.9（全反射，测量确有分辨力）",
          all(v > 0.9 for v in gamma_noabs.values()),
          " · ".join("dim%d Γ=%.4f" % (d, v) for d, v in gamma_noabs.items()))

    # ---------------------------------------------------------------
    # ④⑤⑥ CPML vs 海绵（同层厚；要求优于 50× 以上）
    # ---------------------------------------------------------------
    pairs = {}
    for dim in (2, 3):
        for axis in range(dim):
            key = (dim, axis)
            gs = fc.measure_reflection(dim=dim, axis=axis, absorber="sponge",
                                       n_abs=N_ABS)["gamma"]
            gc = fc.measure_reflection(dim=dim, axis=axis, absorber="cpml",
                                       n_abs=N_ABS, sigma_max=SIGMA_MAX)["gamma"]
            pairs[key] = (gs, gc, gs / gc if gc > 0 else float("inf"))

    for axis, label in ((0, "x"), (1, "y")):
        gs, gc, imp = pairs[(2, axis)]
        check("④ CPML 回反射优于海绵 ≥%.0f×（2D %s 轴，层厚 %d）"
              % (IMPROVE_X, label, N_ABS), imp >= IMPROVE_X,
              "Γ_sponge=%.4e → Γ_cpml=%.4e（%.1f×）" % (gs, gc, imp))
    for axis, label in ((0, "x"), (1, "y"), (2, "z")):
        gs, gc, imp = pairs[(3, axis)]
        check("⑥ CPML 回反射优于海绵 ≥%.0f×（3D %s 轴，层厚 %d）"
              % (IMPROVE_X, label, N_ABS), imp >= IMPROVE_X,
              "Γ_sponge=%.4e → Γ_cpml=%.4e（%.1f×）" % (gs, gc, imp))

    # ---------------------------------------------------------------
    # ⑦ 判据 D：固定 σ_max，扫层厚 ⇒ Γ 严格单调降
    # ---------------------------------------------------------------
    scan_cpml, scan_sponge = [], []
    for na in N_ABS_SCAN:
        scan_cpml.append(fc.measure_reflection(
            dim=2, axis=0, absorber="cpml", n_abs=na,
            sigma_max=SIGMA_MAX)["gamma"])
        scan_sponge.append(fc.measure_reflection(
            dim=2, axis=0, absorber="sponge", n_abs=na)["gamma"])
    seq = " → ".join("%.3e" % v for v in scan_cpml)
    check("⑦a 判据 D：CPML Γ 随层厚**严格单调降**（固定 σ_max=%.1f）" % SIGMA_MAX,
          _strictly_decreasing(scan_cpml), "n_abs=%s ⇒ %s" % (list(N_ABS_SCAN), seq))
    check("⑦b 判据 D：粗端残差未落地板（> 1e-13）",
          scan_cpml[0] > 1e-13, "粗端 %.4e" % scan_cpml[0])
    check("⑦c 判据 D：细端 < tol（%.0e）" % GAMMA_TOL,
          scan_cpml[-1] < GAMMA_TOL, "细端 %.4e" % scan_cpml[-1])

    # ---------------------------------------------------------------
    # ⑧ 如实登记：海绵对照序列
    # ---------------------------------------------------------------
    check("⑧ 海绵对照序列已如实登记（实测同样单调 ⇒ 不冒充「只有 CPML 有判据 D」）",
          True,
          "sponge n_abs=%s ⇒ %s（严格单调=%s）"
          % (list(N_ABS_SCAN), " → ".join("%.3e" % v for v in scan_sponge),
             _strictly_decreasing(scan_sponge)))

    # ---------------------------------------------------------------
    # ⑨ 传播子零改动：回波到达前 CPML 与海绵波形一致（≤ 容差×入射峰）
    # ---------------------------------------------------------------
    pure = {}
    for dim in (2, 3):
        rs = fc.measure_reflection(dim=dim, axis=0, absorber="sponge",
                                   n_abs=N_ABS, return_trace=True)
        rc = fc.measure_reflection(dim=dim, axis=0, absorber="cpml", n_abs=N_ABS,
                                   sigma_max=SIGMA_MAX, return_trace=True)
        cut = rs["idx_pure"]
        import numpy as np
        dmax = float(np.max(np.abs(rs["trace"][:cut] - rc["trace"][:cut])))
        rel = dmax / rs["incident_peak"] if rs["incident_peak"] > 0 else float("inf")
        pure[dim] = (cut, dmax, rel, rs["t_refl_min"])
    check("⑨ 传播子零改动：回波到达前两核波形差 ≤ %.0e×入射峰" % PURE_REL_TOL,
          all(v[2] <= PURE_REL_TOL for v in pure.values()),
          " · ".join("dim%d 前%d步 max|Δ|/峰=%.1e (t_refl_min=%.1fs)"
                     % (d, v[0], v[2], v[3]) for d, v in pure.items()))

    # ---------------------------------------------------------------
    # ⑩ 结构零影响：默认路径未接线（故意的变更探测器）
    # ---------------------------------------------------------------
    touched = []
    for name in ("fdtd2d.py", "fdtd3d.py"):
        p = os.path.join(_HERE, "lda_solver", name)
        with open(p, "r", encoding="utf-8") as fh:
            src = fh.read()
        if "cpml" in src.lower():
            touched.append(name)
    check("⑩ 结构零影响：fdtd2d.py / fdtd3d.py 未接线 CPML（默认路径零改动）",
          not touched,
          "命中 %s" % touched if touched
          else "两文件均不含 cpml 字样 ⇒ 既有 FDTD 锚数值不受本批影响")

    # ---------------------------------------------------------------
    # ⑪ 既有默认签名不变
    # ---------------------------------------------------------------
    from lda_solver import fdtd2d as f2
    from lda_solver import fdtd3d as f3
    d2 = inspect.signature(f2._run_planewave).parameters
    d3 = inspect.signature(f3._run_planewave).parameters
    want2 = {"dl_factor": 40.0, "courant": 0.95, "ramp": 400, "sponge": 200,
             "target_exp": 12.0, "pbc_y": True}
    want3 = {"dl_factor": 80.0, "courant": 0.95, "ramp": 400, "sponge": 320,
             "target_exp": 12.0, "pbc_yz": True}
    bad = []
    for k, v in want2.items():
        if d2.get(k) is None or d2[k].default != v:
            bad.append("2d.%s" % k)
    for k, v in want3.items():
        if d3.get(k) is None or d3[k].default != v:
            bad.append("3d.%s" % k)
    check("⑪ 既有 FDTD 默认签名逐项不变（%d 项）" % (len(want2) + len(want3)),
          not bad, "变更 %s" % bad if bad else "2D %d 项 + 3D %d 项 全部一致"
          % (len(want2), len(want3)))

    # ---------------------------------------------------------------
    # ⑫ 红线：判决依据零 LLM / 零网络（扫登记数据，不扫源码）
    #
    # 🔴 v0.9.133（护栏自证纪律）：登记数据**必须含至少一处可注入的文本**，否则本
    #   判据在结构上**不可证伪** —— 全数值 payload 之下，任何「数据侧」突变都只能
    #   让比较式抛 TypeError（崩溃），而**不是**让判据变红 ⇒ 那就成了「没被验证过
    #   的护栏」。故除数值外登记**内核模块名**（判决数据的出处身份），使
    #   `scripts/p4_cpml_probe.py` 能把网络 token 注入登记文本、证明本判据**会响**。
    #   （同 P3 ⑧ 扫 registry / EXCLUDED 的**文本字段**口径。）
    # ---------------------------------------------------------------
    payload = json.dumps({
        "kernels": [cm.__name__, fc.__name__],
        "pairs": {str(k): v for k, v in pairs.items()},
        "scan_cpml": scan_cpml, "scan_sponge": scan_sponge,
        "gamma_noabs": gamma_noabs,
    }, ensure_ascii=False).lower()
    net_pat = ("openai", "anthropic", "chatgpt", "requests.", "http://", "https://")
    hit = [t for t in net_pat if t in payload]
    check("⑫ 判决依据（回反射登记数据）零 LLM / 零网络引用", not hit, "命中 %s" % hit)

    elapsed = time.time() - t0
    report = {
        "p4_g11": "CFS-PML absorber reflection",
        "sigma_max_fixed": SIGMA_MAX,
        "n_abs_default": N_ABS,
        "n_abs_scan": list(N_ABS_SCAN),
        "gamma_noabs": gamma_noabs,
        "pairs": {("%dD-%s" % (d, "xyz"[a])): {"sponge": v[0], "cpml": v[1],
                                               "improve_x": v[2]}
                  for (d, a), v in pairs.items()},
        "scan_cpml": scan_cpml,
        "scan_sponge": scan_sponge,
        "pure_window": {("dim%d" % d): {"steps": v[0], "max_abs_diff": v[1],
                                        "rel_to_peak": v[2], "t_refl_min": v[3]}
                        for d, v in pure.items()},
        "elapsed_s": round(elapsed, 2),
    }
    out_dir = os.path.join(_HERE, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cpml_absorber_report.json")
    from lda_harness import deterministic as _det
    _det.write_json(out_path, report)
    print("\n报告：%s" % out_path)

    print("\n=== 回反射一览（Γ = 回波/入射，同点比值）===")
    for (d, a), v in sorted(pairs.items()):
        print("  %dD-%s  海绵 %.4e  CPML %.4e  改善 %.1f×"
              % (d, "xyz"[a], v[0], v[1], v[2]))
    print("  无吸收（全反射）Γ = %s"
          % " · ".join("dim%d %.4f" % (d, v) for d, v in gamma_noabs.items()))
    print("\nP4-G11 真 PML 回反射 smoke：%s  (%.1fs)"
          % ("ALL GREEN" if _FAIL == 0 else "HAS FAILURE", elapsed))
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
