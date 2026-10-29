"""D-221 · 超导薄膜**动力学电感**门禁（能力层 · 净增 0 锚）。

## 门禁守什么

`cpw_quasi_static` 自曝「动力学电感未建模」。本轮实测：Al/Nb 只差 ~0.7%，
但 **NbTiN 3.82% / TiN 9.59%**（t=200 nm）⇒ 高动力学电感材料上纯几何 n_eff 会错到
远超 FDM 频率规划容差。所以这层能力**必须建**。

但「必须建」不等于「可锚」——门禁同时守住**不可锚的实测证据**：

  A 组  物理正确性（温度依赖、两个极限、单调性、反比律）
  X 组  与 SSOT / CPW 的串联恒等（ε_eff 不在此处重算）
  G 组  守卫：**不可锚实测**（两条理论路径被材料不确定度淹没）
        + 反例（忽略薄膜因子 / 材料不敏感 / 设计常量 2.5 有推导）
  H 组  诚实边界（材料参数 provenance、未登记材料必抛、负结果三条理由）
  Z 组  零增量

判据标签避开 B/E/S 前缀（锚号前缀，会被 K4 文本代理误判成覆盖）。

纯 stdlib · 零子进程 · 零落盘。
"""
from __future__ import annotations

import math
import os
import sys

from lda_qeda import kinetic_inductance as KI
from lda_qeda import substrate_caliber as CAL
from lda_harness.smoke_kit import make_check

_CNT = {"PASS": 0, "FAIL": 0}
# 🔴 v0.9.275：本文件的 `check` 改用 `smoke_kit` 单一实现（`run_helper_dup_ratchet_smoke`
#   J3/J4 要求「不得再添本地 `def check`」—— 本版把 .271~.275 新增的 5 道门禁全部归一）。
check = make_check(_CNT, ok_key="PASS", bad_key="FAIL", indent="  ",
                   detail_fmt="  |  {d}", detail_on="both", return_ok=True)




def _raises(fn, *a) -> bool:
    """「必抛」判据：捕 Exception 全集（突变可能引入 TypeError/complex，不能只捕窄类）。"""
    try:
        fn(*a)
        return False
    except Exception:                                        # noqa: BLE001
        return True


def main() -> int:
    _CNT["PASS"] = _CNT["FAIL"] = 0
    print("超导薄膜动力学电感 门禁 smoke（D-221）")

    LAM0, TC = 50.0, 1.20
    W, T_FILM = 10e-6, 200e-9
    lam = KI.lambda_l(LAM0, TC, KI.T_OP_K)

    # ---------------- A 组：物理正确性 ----------------
    check("A1 λ_L(T→0) = λ_L(0)（rel<1e-12）",
          abs(KI.lambda_l(LAM0, TC, 1e-12) - LAM0 * 1e-9) <= 1e-12 * LAM0 * 1e-9,
          "λ(0)=%.6f nm" % (KI.lambda_l(LAM0, TC, 1e-12) * 1e9))
    check("A2 λ_L(T) 随 T 单调增（3 组相邻）",
          all(KI.lambda_l(LAM0, TC, a) < KI.lambda_l(LAM0, TC, b)
              for a, b in ((0.02, 0.2), (0.2, 0.5), (0.5, 1.0))))
    check("A3 T ≥ Tc 必抛（超导态不存在，不许静默返回 inf/nan）",
          _raises(KI.lambda_l, LAM0, TC, TC) and _raises(KI.lambda_l, LAM0, TC, 2.0))

    # A4 厚膜极限：t/λ=40 ⇒ coth≈1 ⇒ L_k = μ0λ/w
    check("A4 厚膜极限 t/λ=40 ⇒ L_k → μ0λ/w（rel<1e-9）",
          abs(KI.l_kin_per_length(lam, 40 * lam, W) - KI.MU0 * lam / W)
          / (KI.MU0 * lam / W) < 1e-9,
          "实测 %.6e vs 极限 %.6e" % (KI.l_kin_per_length(lam, 40 * lam, W),
                                      KI.MU0 * lam / W))

    # A5 薄膜极限：coth(x)=1/x+x/3+… ⇒ 相对偏差恰为 x²/3（x=t/λ=0.1）
    x = 0.1
    lk_thin = KI.l_kin_per_length(lam, x * lam, W)
    ref_thin = KI.MU0 * lam ** 2 / (W * (x * lam))
    rel_thin = (lk_thin - ref_thin) / ref_thin
    pred_thin = x ** 2 / 3.0
    check("A5 薄膜极限 t/λ=0.1 ⇒ 偏差恰为 coth 展开二阶项 (t/λ)²/3（实测 %.3e / 解析 %.3e）"
          % (rel_thin, pred_thin), abs(rel_thin - pred_thin) < 0.1 * pred_thin)

    check("A6 L_k 随膜厚 t 单调减（越薄电感越大）",
          KI.l_kin_per_length(lam, 50e-9, W) > KI.l_kin_per_length(lam, 100e-9, W)
          > KI.l_kin_per_length(lam, 400e-9, W))
    _a = KI.l_kin_per_length(lam, T_FILM, W)
    _b = KI.l_kin_per_length(lam, T_FILM, 2 * W)
    check("A7 L_k 与宽度 w 严格反比（w×L 守恒）", abs(_a * W - _b * 2 * W) <= 1e-15 * _a * W)

    # ---------------- X 组：串联恒等 ----------------
    rep = KI.cpw_kinetic_report("Al", t_film_nm=200.0)
    check("X1 n_eff' = n_geom·√(1+α)（恒等，rel<1e-14）",
          abs(rep["n_eff_with_kin"] - rep["n_eff_geom"] * math.sqrt(1 + rep["alpha_kin"]))
          <= 1e-14 * rep["n_eff_with_kin"],
          "α=%.6f%% n'=%.6f" % (rep["alpha_kin"] * 100, rep["n_eff_with_kin"]))
    check("X2 ε_eff 取自 substrate_caliber 单一真源（本模块不重算口径）",
          abs(rep["eps_eff_geom"] - CAL.TL_EPS_EFF_REF) <= 1e-15 * CAL.TL_EPS_EFF_REF,
          "ε=%.6f" % rep["eps_eff_geom"])
    check("X3 L_mag = μ0ε0/C_air（与 C_air 乘积守恒，rel<1e-14）",
          abs(rep["l_mag_h_per_m"] * rep["c_air_f_per_m"] - KI.MU0 * KI.EPS0)
          <= 1e-14 * KI.MU0 * KI.EPS0,
          "L_mag=%.6e H/m" % rep["l_mag_h_per_m"])
    # X4 λ0→0 极限 ⇒ α→0 ⇒ n_eff' 退化回纯几何
    _lam_tiny = KI.l_kin_per_length(1e-30, T_FILM, W)      # 人为极小 λ ⇒ α≈0
    check("X4 退化：α→0 时 n_eff' 严格回到纯几何（构造 λ→0）",
          _lam_tiny / rep["l_mag_h_per_m"] < 1e-20
          and abs(rep["n_eff_geom"] - CAL.TL_N_EFF_REF) <= 1e-15 * CAL.TL_N_EFF_REF,
          "α(λ→0)=%.2e" % (_lam_tiny / rep["l_mag_h_per_m"]))
    _len = 6008.239471034628
    _f = KI.f0_with_kin(_len, "Al", 200.0)
    _f_ref = 2.99792458e8 / (4.0 * _len * 1e-6) / rep["n_eff_with_kin"] / 1e9
    check("X5 f0_with_kin = c0/(4·L·n_eff')（与闭式一致，rel<1e-14）",
          abs(_f - _f_ref) <= 1e-14 * _f, "f0=%.9f GHz" % _f)

    # ---------------- G 组：守卫（含不可锚实测） ----------------
    pr = KI.anchorability_probe("Al", 200.0, 10.0)
    check("G1 🔴 不可锚实测：工作点(20mK)两路径差 %.2e 被 λ_L(0) 的 ±50%% 分散淹没 %.0f 倍"
          % (pr["rel_at_operating_point"], pr["swamp_ratio_at_op"]),
          pr["verdict"] == "NOT_ANCHORABLE" and pr["swamp_ratio_at_op"] >= 1e6
          and pr["swamp_ratio_worst"] >= 100,
          "高温段最大差 %.2e（淹没 %.0f 倍）"
          % (pr["worst_rel_at_T_lessthan_0p3Tc"], pr["swamp_ratio_worst"]))
    check("G2 物理证据：Al @20 mK 的 exp(−Δ/kBT) = %.2e < 1e-40 ⇒ 理论本身重合"
          % pr["exp_minus_delta_over_kbt_at_20mk"],
          pr["exp_minus_delta_over_kbt_at_20mk"] < 1e-40)
    # G3 反例：把 coth(t/λ) 误写成 1（忽略薄膜因子）⇒ t/λ=0.1 时偏差应 >10%
    _wrong = KI.MU0 * lam / W
    _dev = abs(_wrong - lk_thin) / lk_thin
    check("G3 反例在场：忽略薄膜因子（coth→1）在 t/λ=0.1 时偏差 %.1f%%（>10%%）"
          % (_dev * 100), _dev > 0.10)
    _ti = KI.cpw_kinetic_report("TiN", t_film_nm=200.0)["alpha_kin"]
    _al = rep["alpha_kin"]
    check("G4 材料敏感性真实：TiN(200nm) α=%.4f%% > 10×Al(200nm) α=%.4f%%"
          % (_ti * 100, _al * 100), _ti > 10 * _al)
    pos = KI.design_constant_position("Al", 200.0)
    check("G5 设计常量 2.5 **无推导**：纯几何 %.4f%% 在下、含 L_kin %+.4f%% 在上（两侧分居，"
          "故动力学电感解释不了此前那个偏低 0.2%% 的偏差）"
          % (pos["geom_vs_2p5_pct"], pos["kin_vs_2p5_pct"]),
          pos["geom_vs_2p5_pct"] < 0 < pos["kin_vs_2p5_pct"])

    # ---------------- H 组：诚实边界 ----------------
    check("H1 材料 provenance 逐条登记且明写「非实测」",
          all(k in KI.MATERIAL_PROVENANCE and "非实测" in KI.MATERIAL_PROVENANCE[k]
              for k in KI.MATERIALS),
          "%d 种材料" % len(KI.MATERIALS))
    check("H2 未登记材料必抛（不猜默认材料）",
          _raises(KI.lambda_l_material, "Unobtainium", 0.02))
    wna = KI.why_not_anchored()
    check("H3 负结果机器化：三条理由齐备 + 重评条件 + anchorable=False",
          wna["anchorable"] is False and len(wna["three_reasons"]) == 3
          and bool(wna["revisit_condition"]) and bool(wna["replacement"]))

    # ---------------- Z 组：零增量 ----------------
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from lda_harness.benchmarks import BENCHMARK_DEFS as D
        n = len(D)
        check("Z1 零增量：账本锚数 = %d（能力层，不加锚）" % n, n == 546)
    except Exception as e:                                   # noqa: BLE001
        check("Z1 零增量：账本锚数不变", False, "不可读：%s" % e)

    n_pass = _CNT["PASS"]
    print("\n门禁 smoke：%d PASS / %d FAIL（共 %d 项）"
          % (n_pass, _CNT["FAIL"], n_pass + _CNT["FAIL"]))
    return 0 if _CNT["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
