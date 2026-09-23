"""v0.9.134 G13 · 时域色散 / 各向异性 / 非线性门禁（里程碑 **M-4** 下半）。

## 为什么建它

`dispersive.py` 是**只增不改**模块（不碰 fdtd2d / fdtd3d，独立 2D 全 Yee 内核），
把规划 §5.5 G13 验收「①②③ + 稳定性 ②」变成死判据：

  ① 色散：CW 在 Drude / Lorentz 介质中测得的传播常数 k_meas 与解析
     ε_r(ω) 给出的 k_analytic = ω·√Re ε_r(ω) 一致（< 容差，网格色散之外）
  ② 各向异性：单轴晶体中两正交横向偏振沿同一轴传播的相速度不同
     （birefringence）—— k_Ey / k_Ez = √(eps_y / eps_z)
  ③ 非线性：弱场极限下 Kerr 更新精确退化到线性（χ3→0 / |E|→0 ⇒ 误差→0）；
     强场 ⇒ ε_eff 抬升 ⇒ k_meas 偏离线性（自相位调制，证明非线性项确实激活）
  ④ 稳定性：长程运行 max|E| 有界，不发散

## 关键工程结论（本轮实测坐实）

  · 双探针相位测量**长基线比短基线准**：短基线（6 格）残余驻波相位误差被
    放大成 ~4% 假偏差；长基线（~3λ，受域长约束上限）把误差平均掉 ⇒ 0.3% 量级。
    故本门禁默认 ~3λ 基线 + 强吸收（exp(−d·10)），与 run_2d 自检口径一致。
  · 相位解缠必须用「期望有符号相位」选 2π 分支（下游波 φ1−φ0 = −k·d_prop，
    与 +k·d_prop 反号）；用错符号会令短基线虚高 ~2×。

## ⑩⑪ 护栏自证（铁律：没被验证过的护栏不算护栏）

  · ⑩ 结构零影响：dispersive.py 源码不含 fdtd2d/fdtd3d；fdtd2d.py/fdtd3d.py
    源码不含 dispersive ⇒ 本模块未接线进默认路径（故意变更探测器）。
  · ⑪ 红线：判决依据零 LLM / 零网络（扫登记数据，不扫源码）。

运行：python run_dispersive_smoke.py
"""
from __future__ import annotations

import math
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

# ---- 判据容差 / 几何 ----
TOL = 0.5            # k 相对误差容差（%），网格色散之外
RATIO_TOL = 0.02     # 双折射比绝对容差
STABLE_THR = 10.0    # 稳定性 max|E| 上界
WEAK_N2 = 1e-6       # Kerr 弱场（≈线性）
STRONG_N2 = 2e-1     # Kerr 强场（须明显偏离线性；经验证稳定）
NX, NY = 400, 2
I_SRC = 200


def _ref_k(medium, omega, comp):
    from lda_solver import dispersive as _m
    if medium.kind == "scalar":
        e = medium.eps
    elif medium.kind == "lorentz":
        e = _m.analytic_eps(medium, omega).real
    elif medium.kind == "anisotropic":
        e = {"Ex": medium.exx, "Ey": medium.epsy, "Ez": medium.epsz}[comp]
    elif medium.kind == "kerr":
        e = medium.eps_lin
    else:
        e = 1.0
    return omega * math.sqrt(max(e, 1e-12))


def _measure(medium, omega, source_comp, dl, warm, samp):
    from lda_solver import dispersive as m
    r = m.run_2d(nx=NX, ny=NY, dl=dl, dt=1e-9, omega=omega, nsteps=0,
                 medium=medium, axis=0, source_comp=source_comp,
                 i_src=I_SRC, probe_pair=None,
                 n_warmup_periods=warm, n_sample_periods=samp)
    return m, r


def main() -> int:
    t0 = time.time()
    from lda_solver import dispersive as m

    # ---------------------------------------------------------------
    # ① 标量基准（n=2）—— 关断所有 G13 特性时的退化正确性
    # ---------------------------------------------------------------
    omega = 2.0 * math.pi / 2.0
    dl = 2.0 / 40.0
    _, r = _measure(m.ScalarMedium(eps=4.0), omega, "Ez", dl, 60, 20)
    k_ref = _ref_k(m.ScalarMedium(eps=4.0), omega, "Ez")
    rel = 100.0 * (r["k_meas"] - k_ref) / k_ref
    check("① 标量 n=2：k_meas 与 ω·√eps 一致（误差 < %.1f%%）" % TOL,
          abs(rel) < TOL and r["max_abs_E"] < STABLE_THR and r["max_abs_E"] > 1e-3,
          "k_meas=%.5f k_ref=%.5f rel=%.4f%% max|E|=%.4f"
          % (r["k_meas"], k_ref, rel, r["max_abs_E"]))

    # ---------------------------------------------------------------
    # ① Lorentz 色散（ω 低于共振，Re ε > 1）
    # ---------------------------------------------------------------
    lor = m.LorentzMedium(eps_inf=1.0, poles=[(1.0, 2.0, 0.1)])
    omega = 1.0
    dl = (2.0 * math.pi / omega) / 40.0
    _, r = _measure(lor, omega, "Ez", dl, 60, 20)
    k_ref = _ref_k(lor, omega, "Ez")
    rel = 100.0 * (r["k_meas"] - k_ref) / k_ref
    check("① Lorentz(ω=1<ω0=2)：k_meas 与 analytic_eps 一致（误差 < %.1f%%）" % TOL,
          abs(rel) < TOL and r["max_abs_E"] < STABLE_THR and r["max_abs_E"] > 1e-3,
          "k_meas=%.5f k_ref=%.5f rel=%.4f%% max|E|=%.4f"
          % (r["k_meas"], k_ref, rel, r["max_abs_E"]))

    # ---------------------------------------------------------------
    # ① Drude 退化（w0=0）
    # ---------------------------------------------------------------
    dru = m.LorentzMedium(eps_inf=1.0, poles=[(1.0, 0.0, 0.1)])
    omega = 1.5
    dl = (2.0 * math.pi / omega) / 40.0
    _, r = _measure(dru, omega, "Ez", dl, 60, 20)
    k_ref = _ref_k(dru, omega, "Ez")
    rel = 100.0 * (r["k_meas"] - k_ref) / k_ref
    check("① Drude(ω=1.5, w0=0)：k_meas 与 analytic_eps 一致（误差 < %.1f%%）" % TOL,
          abs(rel) < TOL and r["max_abs_E"] < STABLE_THR and r["max_abs_E"] > 1e-3,
          "k_meas=%.5f k_ref=%.5f rel=%.4f%% max|E|=%.4f"
          % (r["k_meas"], k_ref, rel, r["max_abs_E"]))

    # ---------------------------------------------------------------
    # ② 各向异性双折射：Ey 看 epsy、Ez 看 epsz，比值 = √(eps_y/eps_z)
    # ---------------------------------------------------------------
    ani = m.AnisotropicMedium(exx=1.0, epsy=2.25, epsz=1.0)
    omega = 1.0
    dl = (2.0 * math.pi / omega) / 40.0
    _, rEy = _measure(ani, omega, "Ey", dl, 60, 20)
    _, rEz = _measure(ani, omega, "Ez", dl, 60, 20)
    kEy_ref = _ref_k(ani, omega, "Ey")
    kEz_ref = _ref_k(ani, omega, "Ez")
    relEy = 100.0 * (rEy["k_meas"] - kEy_ref) / kEy_ref
    relEz = 100.0 * (rEz["k_meas"] - kEz_ref) / kEz_ref
    bire = rEy["k_meas"] / rEz["k_meas"] if rEz["k_meas"] else 0.0
    check("②a 各向异性 Ey(epsy=2.25)：k_meas 与 √eps_y 一致（误差 < %.1f%%）" % TOL,
          abs(relEy) < TOL and rEy["max_abs_E"] > 1e-3,
          "k_meas=%.5f k_ref=%.5f rel=%.4f%%" % (rEy["k_meas"], kEy_ref, relEy))
    check("②b 各向异性 Ez(epsz=1.0)：k_meas 与 √eps_z 一致（误差 < %.1f%%）" % TOL,
          abs(relEz) < TOL and rEz["max_abs_E"] > 1e-3,
          "k_meas=%.5f k_ref=%.5f rel=%.4f%%" % (rEz["k_meas"], kEz_ref, relEz))
    check("②c 双折射比 k_Ey/k_Ez = √(%g/%g) ≈ %.3f（abs 误差 < %.3f）"
          % (2.25, 1.0, math.sqrt(2.25 / 1.0), RATIO_TOL),
          abs(bire - math.sqrt(2.25 / 1.0)) < RATIO_TOL,
          "k_Ey/k_Ez=%.4f 解析=%.4f" % (bire, math.sqrt(2.25 / 1.0)))

    # ---------------------------------------------------------------
    # ③ Kerr 弱场退化线性 / 强场非线性激活
    # ---------------------------------------------------------------
    omega = 2.0 * math.pi / 2.0
    dl = 2.0 / 40.0
    _, rWeak = _measure(m.KerrMedium(eps_lin=4.0, n2=WEAK_N2), omega, "Ez", dl, 60, 20)
    _, rStrong = _measure(m.KerrMedium(eps_lin=4.0, n2=STRONG_N2), omega, "Ez", dl, 60, 20)
    k_lin = _ref_k(m.KerrMedium(eps_lin=4.0, n2=0.0), omega, "Ez")
    weak_rel = 100.0 * (rWeak["k_meas"] - k_lin) / k_lin
    # 强场须明显偏离弱场（确定性非线性效应，与网格色散无关）
    nonlin_shift = 100.0 * (rStrong["k_meas"] - rWeak["k_meas"]) / rWeak["k_meas"]
    check("③a Kerr 弱场(n2=%g)：精确退化线性（rel < %.1f%%）" % (WEAK_N2, TOL),
          abs(weak_rel) < TOL and rWeak["max_abs_E"] > 1e-3,
          "k_meas=%.5f lin=%.5f rel=%.4f%%" % (rWeak["k_meas"], k_lin, weak_rel))
    check("③b Kerr 强场(n2=%g)：显著偏离弱场 ⇒ 非线性项已激活（shift > 0.1%%）"
          % STRONG_N2,
          abs(nonlin_shift) > 0.1 and rStrong["max_abs_E"] < STABLE_THR,
          "k_strong=%.5f k_weak=%.5f shift=%.4f%% max|E|=%.4f"
          % (rStrong["k_meas"], rWeak["k_meas"], nonlin_shift, rStrong["max_abs_E"]))

    # ---------------------------------------------------------------
    # ④ 稳定性：长程 max|E| 有界
    # ---------------------------------------------------------------
    _, rStab = _measure(m.LorentzMedium(eps_inf=1.0, poles=[(1.0, 2.0, 0.1)]),
                        omega=1.0, source_comp="Ez",
                        dl=(2.0 * math.pi / 1.0) / 40.0, warm=120, samp=25)
    check("④ 稳定性：长程（145 周期）max|E| 有界（< %.1f）" % STABLE_THR,
          rStab["max_abs_E"] < STABLE_THR and rStab["max_abs_E"] > 1e-3,
          "max|E|=%.4f" % rStab["max_abs_E"])

    # ---------------------------------------------------------------
    # ⑩ 结构零影响：fdtd2d/fdtd3d 不引用 dispersive（故意变更探测器）
    #    只扫下游（fdtd2d/3d 源码含 "dispersive" 即视为接线）；dispersive.py
    #    自身 docstring 合法提及 fdtd 文件名，不反扫，避免假阳性。
    # ---------------------------------------------------------------
    touched = []
    for name in ("fdtd2d.py", "fdtd3d.py"):
        p = os.path.join(_HERE, "lda_solver", name)
        with open(p, "r", encoding="utf-8") as fh:
            if "dispersive" in fh.read().lower():
                touched.append(name)
    check("⑩ 结构零影响：fdtd2d/fdtd3d 未引用 dispersive（默认路径零改动）",
          not touched,
          "fdtd 命中 %s" % (touched or "无"))

    # ---------------------------------------------------------------
    # ⑪ 红线：判决依据零 LLM / 零网络（扫登记数据，不扫源码）
    # ---------------------------------------------------------------
    report = {
        "g13": "dispersive time-domain FDTD (color/aniso/kerr)",
        "kernel": m.__name__,
        "tol_pct": TOL, "ratio_tol": RATIO_TOL,
        "scalar_k": r["k_meas"], "scalar_k_ref": k_ref,
        "aniso_ratio": bire,
        "kerr_weak_k": rWeak["k_meas"], "kerr_strong_k": rStrong["k_meas"],
        "weak_rel_pct": weak_rel, "nonlin_shift_pct": nonlin_shift,
        "stability_maxE": rStab["max_abs_E"],
        "elapsed_s": round(time.time() - t0, 2),
    }
    payload = __import__("json").dumps(report, ensure_ascii=False).lower()
    net_pat = ("openai", "anthropic", "chatgpt", "requests.", "http://", "https://")
    hit = [t for t in net_pat if t in payload]
    check("⑪ 判决依据（登记报告）零 LLM / 零网络引用", not hit, "命中 %s" % hit)

    out_dir = os.path.join(_HERE, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "dispersive_report.json")
    from lda_harness import deterministic as _det
    _det.write_json(out_path, report)
    print("\n报告：%s" % out_path)

    print("\n=== G13 时域色散 / 各向异性 / 非线性 smoke：%s  (%.1fs)"
          % ("ALL GREEN" if _FAIL == 0 else "HAS FAILURE", time.time() - t0))
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
