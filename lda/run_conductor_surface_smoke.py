"""D-222 · 有限导体厚度 / 表面阻抗门禁（能力层 · 净增 0 锚）。

## 门禁守什么

`cpw_quasi_static` 自曝「**不含导体厚度 / 不含表面阻抗**」，`kinetic_inductance`（D-221）
只补了**电感侧**；损耗侧全仓精确检索 `skin_depth` 零命中，`sc_readout` 的
`tan_delta_surface=1e-6` 是**手填参数、无物理来源**。所以这层能力必须建。

但「必须建」不等于「可锚」，而且 D-222 的判死理由与 D-221 **不同**（更危险的那种）：

  A 组  物理正确性 —— **四个解析极限**（正常/超导 × 厚膜/薄膜），全部有闭式可真值
  X 组  跨模块/跨物理 —— 与 D-221 的 L_k 对拍、与 SSOT 的串联、与 TLS 损耗的口径分界
  G 组  几何标度 —— α∝R_s、α∝√f、α∝√ρ、α 随 w 单调降（**固定内缩量**才严格）
  H 组  诚实边界 —— 零厚度必抛、未知材料必抛、厚度三区判定、Wheeler 失效标记、
        非平衡准粒子未建模
  Z 组  负结果 + 零增量 —— 三条理由齐备、账本不变

判据标签避开 B/E/S 前缀（锚号前缀，会被 K4 文本代理误判成覆盖那些锚）。

纯 stdlib · 零子进程 · 零落盘。
"""
from __future__ import annotations

import math
import sys

from lda_qeda import conductor_surface as CS
from lda_qeda import cpw_quasi_static as CQS
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
    print("有限导体厚度 / 表面阻抗 门禁 smoke（D-222）")

    RHO = 1.0e-9
    F = 5.0e9
    d = CS.skin_depth(RHO, F)
    zs_inf = complex(RHO / d, RHO / d)          # (ρ/δ)(1+j)
    DN = 0.05                                    # 固定内缩量（µm），标度判据专用

    # ---------------- A 组：四个解析极限 ----------------
    print("\n[A] 四个解析极限（每个都有闭式真值，不是拍阈值）")

    z100 = CS.zs_normal(RHO, F, 100.0 * d)
    relA1 = abs(z100 - zs_inf) / abs(zs_inf)
    check("A1 正常态厚膜 t/δ=100 ⇒ Z_s = (ρ/δ)(1+j)", relA1 < 1e-15,
          "残差 %.3e（coth 在 |x|=141 时已 =1 到 1e-123）" % relA1)

    u = 0.01
    zthin = CS.zs_normal(RHO, F, u * d)
    # 🔴 除零保护：突变可能让 Re→0（如 k 漏 j ⇒ Z_s 纯虚）⇒ 此处必须**判红**而非崩溃
    _re2 = zthin.real if abs(zthin.real) > 1e-300 else 1e-300
    ratio = abs(zthin.imag) / _re2
    pred = (2.0 / 3.0) * u * u
    check("A2 正常态薄膜 t/δ=0.01 ⇒ Im/Re = (2/3)(t/δ)²", abs(ratio - pred) / pred < 1e-3,
          "实测 %.6e vs 解析 %.6e" % (ratio, pred))

    u2 = 1e-3
    prod2 = CS.zs_normal(RHO, F, u2 * d).real * u2 * d / RHO
    check("A3 正常态薄膜 Re·t/ρ → 1（首项恰为 ρ/t）",
          abs(prod2 - 1.0) < 1e-6 if math.isfinite(prod2) else False,
          "u=1e-3 时残差 %.3e" % abs(prod2 - 1.0))

    lam = KI.lambda_l_material("Al", CS.T_OP_K)
    zsup = CS.zs_super("Al", CS.T_OP_K, F, 20.0 * lam)
    ref_im = 2.0 * math.pi * F * CS.MU0 * lam       # >0 恒成立（λ>0）
    check("A4 超导厚膜 t/λ=20 ⇒ Im Z_s/(ωμ0λ) = 1（即 L_k^□ = μ0λ）",
          abs(zsup.imag / ref_im - 1.0) < 1e-9, "实测 %.12f" % (zsup.imag / ref_im))

    # A5：超导薄膜 Im Z_s/(ωμ0λ) 必须 = coth(t/λ)（与 D-221 同式，独立实现）
    wf = 0.0
    for tr in (0.5, 1.0, 2.0, 5.0):
        s2 = 1.0 / (CS.MU0 * 2 * math.pi * F * lam * lam)
        zz = CS.surface_impedance(complex(0.0, -s2), F, tr * lam)
        got = zz.imag / ref_im
        want = 1.0 / math.tanh(tr)
        wf = max(wf, abs(got - want) / want)
    check("A5 超导薄膜 Im Z_s/(ωμ0λ) = coth(t/λ)（4 组，最差 %.3e）" % wf, wf < 1e-12)

    # ---------------- X 组：跨模块 / 跨物理 ----------------
    print("\n[X] 跨模块对拍（两条独立实现必须逐位重合）")

    w_m = 10e-6
    worst_x1 = 0.0
    for t_nm in (50, 100, 200, 400):
        t_m = t_nm * 1e-9
        s2 = 1.0 / (CS.MU0 * 2 * math.pi * F * lam * lam)
        zz = CS.surface_impedance(complex(0.0, -s2), F, t_m)
        l_zs = zz.imag / (2 * math.pi * F)
        l_ki = KI.l_kin_per_length(lam, t_m, w_m) * w_m
        worst_x1 = max(worst_x1, abs(l_zs - l_ki) / l_ki)
    check("X1 与 D-221 的 L_k 对拍：Im Z_s/ω ≡ L_k^□（4 组）", worst_x1 < 1e-14,
          "最差 %.3e ⇒ 表面阻抗闭式与 London coth 是同一条物理的两个独立写法" % worst_x1)

    # X2：与 substrate_caliber 的 SSOT 串联 —— ε_eff 必须取自真源，不得在此重算
    tl = CAL.TL_EPS_EFF_REF
    got_ee = CQS.cpw_closed_form(10.0, 6.0, h_um=500.0, eps_r=11.45)["eps_eff"]
    check("X2 ε_eff 取自 SSOT 真源（此处不重算）",
          abs(got_ee - tl) / tl < 1e-15,
          "CQS=%.12f vs CAL.TL_EPS_EFF_REF=%.12f" % (got_ee, tl))

    # X3：导体损耗 ≠ TLS 介质损耗（量级分离，证明不是同一个物理通道）
    sep = CS.loss_channel_separation("Al", 200.0, F)
    check("X3 导体 tanδ_eff = %.2e ≪ TLS 手填 1e−6（分离 %.2e 倍）"
          % (sep["tan_delta_eff_super"], sep["separation_super"]),
          sep["separation_super"] > 1e3,
          "⇒ sc_readout 的 tan_delta_surface 描述的是 TLS，不是导体")

    # ---------------- G 组：几何标度 ----------------
    print("\n[G] 几何标度（固定内缩量时数学上严格）")

    a1 = CS.alpha_c_cpw(zs_inf, F, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
    a2 = CS.alpha_c_cpw(zs_inf * 2.0, F, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
    a4 = CS.alpha_c_cpw(zs_inf * 4.0, F, 10.0, 6.0, 500.0, 11.45, dn_um=DN)["alpha_c_np_per_m"]
    check("G1 α_c ∝ R_s（2×/4× ⇒ 2×/4×）",
          abs(a2 / a1 - 2.0) < 1e-12 and abs(a4 / a1 - 4.0) < 1e-12,
          "比值 %.15f / %.15f" % (a2 / a1, a4 / a1))

    vals = []
    for ff in (1e9, 5e9, 20e9):
        zz = CS.zs_normal(RHO, ff, 100.0 * CS.skin_depth(RHO, ff))
        vals.append(CS.alpha_c_cpw(zz, ff, 10.0, 6.0, 500.0, 11.45,
                                   dn_um=DN)["alpha_c_np_per_m"] / math.sqrt(ff))
    # 🔴 vals 可能全 0（突变让 α≡0）⇒ 除零保护，此处必须判红而非崩溃
    _spread = (max(vals) / min(vals) - 1.0) if min(vals) > 0 else float("inf")
    check("G2 正常态 α_c ∝ √f（3 频点 α/√f 恒定）", _spread < 1e-12,
          "散布 %.3e" % _spread)

    vals = []
    for rho in (1e-9, 4e-9, 1.6e-8, 1e-6):
        zz = CS.zs_normal(rho, F, 100.0 * CS.skin_depth(rho, F))
        vals.append(CS.alpha_c_cpw(zz, F, 10.0, 6.0, 500.0, 11.45,
                                   dn_um=DN)["alpha_c_np_per_m"] / math.sqrt(rho))
    _spread3 = (max(vals) / min(vals) - 1.0) if min(vals) > 0 else float("inf")
    check("G3 正常态 α_c ∝ √ρ（4 个电阻率 α/√ρ 恒定）", _spread3 < 1e-12,
          "散布 %.3e" % _spread3)

    aa = [CS.alpha_c_cpw(zs_inf, F, w, 6.0, 500.0, 11.45,
                         dn_um=DN)["alpha_c_np_per_m"] for w in (2.0, 5.0, 10.0, 20.0, 40.0)]
    check("G4 α_c 随 w 严格单调下降（2→40 µm）",
          all(aa[i] > aa[i + 1] for i in range(len(aa) - 1)),
          "α: " + " > ".join("%.4f" % v for v in aa))

    # 🔴 G5/G6 守 α_c 的**绝对量级**（G1–G4 全是比值 ⇒ 乘任何常数都不会咬）
    #    G5 用无源性：无源导体的 tanδ_eff = 2α/β 必须 ∈ (0,1)。
    #    漏掉真空波阻抗 η0 会让 α 乘 377 ⇒ tanδ_eff = 3.11 > 1（实测）⇒ 必然咬住。
    cases = [("Al", "normal"), ("Nb", "normal"), ("Cu", "normal"), ("Al", "super")]
    bad = []
    for mat, st in cases:
        r = CS.alpha_with_thickness(mat, 200.0, F, state=st)
        td = CS.equivalent_tan_delta(r["alpha_c_np_per_m"], r["beta_rad_per_m"])
        if not (0.0 <= td < 1.0):
            bad.append("%s/%s tanδ=%.3e" % (mat, st, td))
    check("G5 无源性：tanδ_eff = 2α/β ∈ [0,1)（4 个材料/态组合）",
          not bad, "违反：" + ", ".join(bad) if bad else
          "Al/正常 8.27e−3 · Nb/正常 1.21e−2 · Cu/正常 1.32e−1 · Al/超导 ≈7.6e−50")

    #    G6 用物理量级窗口（**不是 golden**，只守数量级不跑偏）
    q_al = CS.alpha_with_thickness("Al", 200.0, F, state="normal")["q_conductor"]
    q_cu = CS.alpha_with_thickness("Cu", 200.0, F, state="normal")["q_conductor"]
    check("G6 正常态 Q_c 量级窗口：Al∈[50,500] 且 Cu<Al（Cu 300K 更差）",
          50.0 <= q_al <= 500.0 and q_cu < q_al,
          "Al %.2f · Cu %.2f（量级校验，非 golden）" % (q_al, q_cu))

    # ---------------- H 组：诚实边界 ----------------
    print("\n[H] 诚实边界（这些不是「能跑通」，是「必须拒绝」）")

    check("H1 t=0 必抛（零厚度表面阻抗无定义，不得返 inf/默认）",
          _raises(CS.surface_impedance, CS.sigma_normal(RHO), F, 0.0))
    check("H2 未知导体材料必抛（不猜 ρ/λ 默认）",
          _raises(CS.sigma_super, "Unobtainium", CS.T_OP_K, F))
    check("H3 T ≥ Tc 必抛（超导态不存在）",
          _raises(CS.sigma_super, "Al", 1.20, F))

    regs = [CS.thickness_regime(x * d, d)["regime"] for x in (0.05, 0.5, 2.0)]
    check("H4 厚度三区判定 t/δ=0.05/0.5/2.0 ⇒ thin/transition/thick",
          regs == ["thin", "transition", "thick"], str(regs))

    # 🔴 H5：薄膜区等效内缩恒为 **t/3**（与材料无关）——由 coth 展开
    #    Im/Re = (2/3)u²、Re = ρ/t 推出 δ_eff = t·(2u²/3)·(δ²/(2t²)) = t/3。
    #    这是跨材料的解析恒等式，比"Wheeler 是否失效"更有判别力。
    wf5 = 0.0
    for mat in ("NbTiN", "TiN"):
        r = CS.alpha_with_thickness(mat, 200.0, F, state="normal")
        wf5 = max(wf5, abs(r["inset_um"] * 1000.0 - 200.0 / 3.0) / (200.0 / 3.0))
    check("H5 薄膜区等效内缩 δ_eff ≡ t/3（NbTiN/TiN 两种材料，最差 %.3e）" % wf5,
          wf5 < 1e-3, "实测 66.667 nm = 200/3 ⇒ 与材料参数无关")

    # 🔴 H6：薄膜区若误用半无限 ρ/δ，R_s 会被**低估几十倍** ⇒ t 是必需参数不是精度旋钮
    ratios = {}
    for mat in ("NbTiN", "TiN", "Nb", "Al"):
        ratios[mat] = CS.alpha_with_thickness(mat, 200.0, F, state="normal")["rs_ratio_vs_infinite"]
    check("H6 薄膜区半无限 ρ/δ 低估 R_s：NbTiN **%.2f×** / TiN **%.2f×**（均 >10×）"
          % (ratios["NbTiN"], ratios["TiN"]),
          ratios["NbTiN"] > 10.0 and ratios["TiN"] > 10.0,
          "Al %.2f× / Nb %.2f×（近厚膜区，偏差小属正常）"
          % (ratios["Al"], ratios["Nb"]))
    check("H6b 厚膜区半无限近似收敛（Al t/δ=0.89 ⇒ 比值 %.3f ∈ [1.0, 1.5]）"
          % ratios["Al"], 1.0 <= ratios["Al"] <= 1.5)

    db = CS.design_boundary()
    check("H7 「零厚度无定义」+「非平衡准粒子未建模」+「薄膜惩罚」边界处登记齐备",
          db["zero_thickness_undefined"] is True and
          ("发散" in db["why"]) and ("准粒子" in CS.__doc__) and
          ("43.59" in db["thin_film_penalty"]),
          "边界在 docstring + design_boundary() 双处登记")

    # H8：材料库为文献值，不得读成实测
    check("H8 %d 种导体材料的 provenance 全部登记为「非实测」"
          % len(CS.CONDUCTOR_MATERIALS),
          all("非实测" in v for v in CS.MATERIAL_PROVENANCE.values())
          and set(CS.MATERIAL_PROVENANCE) == set(CS.CONDUCTOR_MATERIALS))

    # ---------------- Z 组：负结果 + 零增量 ----------------
    print("\n[Z] 负结果与零增量")

    pr = CS.anchorability_probe()
    check("Z1 三条 R_s 写法最大相对差 %.3e < 1e-12（resid ≡ 0）"
          % pr["three_ways_worst_rel"], pr["three_ways_worst_rel"] < 1e-12)
    check("Z2 两流体在 R_s 上失效：20 mK 差 %.3e 倍 > 1e3"
          % pr["ratio_at_20mk"], pr["ratio_at_20mk"] > 1e3,
          "⇒ 不是「两条路径重合」，是「另一条路径物理不成立」")

    wn = CS.why_not_anchored()
    check("Z3 负结果机器化：anchorable=False ∧ 三理由 ∧ replacement ∧ 重评条件",
          wn["anchorable"] is False and len(wn["three_reasons"]) == 3
          and bool(wn["replacement"]) and bool(wn["revisit_condition"]))

    try:
        sys.path.insert(0, "D:/agent_LDA/lda")
        from lda_harness.benchmarks import BENCHMARK_DEFS as D
        n = len(D)
        check("Z4 零增量：账本锚数 = %d（能力层，不加锚）" % n, n == 541)
    except Exception as e:                                   # noqa: BLE001
        check("Z4 零增量：账本锚数不变", False, "不可读：%s" % e)

    n_pass = _CNT["PASS"]
    print("\n门禁 smoke：%d PASS / %d FAIL（共 %d 项）"
          % (n_pass, _CNT["FAIL"], n_pass + _CNT["FAIL"]))
    return 0 if _CNT["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
