# -*- coding: utf-8 -*-
"""U3 常驻门禁：微环 κ_c FDTD 标定层 + 网格可信度（含「不达标」机器化）。

判据分组
--------
A 契约 / 参数校验（含「合法必过」）
B `classify_trust` 纯函数穷举（正向 + 边界 + 反例）
C `convergence_report` 合成序列（**复现本轮真实血案**：残差非单调 ⇒ 不声称收敛）
D 解析对比（含独立重算）
E 取数接口（analytic / fdtd-table / 越界必 raise）
F 端到端 FDTD（dl=(16,20,25)，实测 ~30s）：离散度超预算 + 收敛不成立被如实报出
G 回填入口 `calibrated_ring_anchor`：几何逐位一致 + k_ring 独立重算
H 突变探针友好性（反向护栏：把模块自报值伪造 ⇒ 判据必须能红）

🔴 本 smoke 的立场：**「不达标」是结论，不是失败** —— F6/F7 断言的是
「跨网格离散度 > 10% 预算」与「残差不单调」这两件**事实**必须被如实报出；
若有人把模块改成「总是达标 / 总是收敛」，F6/F7 与 C2 立刻变红。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.ring_kappa_calib import (  # noqa: E402
    CF_SATURATION,
    DEFAULT_DL_FACTORS,
    RING_KAPPA_DISCLOSURE,
    UNCERTAINTY_BUDGET_REL,
    RingKappaCalibError,
    analytic_kappa,
    analytic_vs_fdtd,
    calibrated_ring_anchor,
    classify_trust,
    convergence_report,
    kappa_c_from_table,
    kappa_c_lookup,
    kappa_c_series,
)

PASS = 0
FAIL = 0
check = make_check(globals(), return_ok=True, detail_on="fail")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _rejects(fn, exc: type = Exception) -> bool:
    """fn() 必须抛 exc（且不是别的异常）⇒ True。"""
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def _pt(dlf: int, k: float, c1: float = 0.2, c2: float = 0.7,
        trusted: bool = True, reason: str = "ok") -> dict:
    return {"dl_factor": dlf, "dl_um": round(1.55 / dlf, 5),
            "kappa_c_rad_um": k, "cf1": c1, "cf2": c2,
            "winding": reason == "winding", "trusted": trusted, "reason": reason}


def _mk_series(points) -> dict:
    return {"points": list(points), "n_points": len(points),
            "n_trusted": sum(1 for p in points if p["trusted"])}


# 本轮实测真实数据（gap=0.30µm · λ=1.55µm）—— 用于血案复现
REAL_KAPPAS_30 = [0.026324, 0.024114, 0.010492]


def main():  # noqa: C901
    # ------------------------------------------------------------------ A 契约
    need_keys = {"scope", "mesh_convergence_not_established",
                 "root_cause_staircase_gap", "analytic_is_placeholder",
                 "budget_not_met", "no_3d_and_no_vertical_confinement",
                 "fdtd_too_slow_for_runtime"}
    check("A1 披露项键齐全（7 项，防被悄悄删）",
          need_keys.issubset(set(RING_KAPPA_DISCLOSURE)),
          "missing=%s" % sorted(need_keys - set(RING_KAPPA_DISCLOSURE)))
    check("A2 披露项值均为非空字符串",
          all(isinstance(v, str) and v.strip() for v in RING_KAPPA_DISCLOSURE.values()))
    check("A3 设计预算口径 == 10%（§4.2 U3）",
          abs(UNCERTAINTY_BUDGET_REL - 0.10) < 1e-12, "=%.4f" % UNCERTAINTY_BUDGET_REL)
    check("A4 饱和阈值口径 == 0.6（与 D-60 winding 判据同口径）",
          abs(CF_SATURATION - 0.6) < 1e-12, "=%.3f" % CF_SATURATION)
    check("A5 默认网格档刻意排除 dl30（实测 95s，不进 smoke）",
          30 not in DEFAULT_DL_FACTORS, "dl=%s" % (DEFAULT_DL_FACTORS,))
    check("A6 gap 越界（0）必 raise",
          _rejects(lambda: kappa_c_series(0.0, 1.55, dl_factors=(16,)),
                   RingKappaCalibError))
    check("A7 gap 越界（3µm）必 raise",
          _rejects(lambda: kappa_c_series(3.0, 1.55, dl_factors=(16,)),
                   RingKappaCalibError))
    check("A8 λ 越界（0.5µm）必 raise",
          _rejects(lambda: kappa_c_series(0.30, 0.5, dl_factors=(16,)),
                   RingKappaCalibError))
    check("A9 dl_factors 空 ⇒ 必 raise",
          _rejects(lambda: kappa_c_series(0.30, 1.55, dl_factors=()),
                   RingKappaCalibError))
    check("A10 dl_factor 越界（1 / 999）必 raise",
          _rejects(lambda: kappa_c_series(0.30, 1.55, dl_factors=(1,)),
                   RingKappaCalibError)
          and _rejects(lambda: kappa_c_series(0.30, 1.55, dl_factors=(999,)),
                       RingKappaCalibError))
    check("A11 🔴 合法输入必过（单档最小 FDTD，~3s）",
          isinstance(kappa_c_series(0.30, 1.55, dl_factors=(16,)), dict))

    # ------------------------------------------------- B classify_trust 穷举
    check("B1 winding 点 ⇒ 不可信 + reason=winding",
          classify_trust(0.02, 0.2, 0.5, True) == (False, "winding"))
    check("B2 独立复核饱和：winding=False 但 cf1>0.6 ⇒ cf_saturated",
          classify_trust(0.02, 0.9, 0.5, False) == (False, "cf_saturated"))
    check("B3 cf2≈1.0 ⇒ cf_saturated",
          classify_trust(0.02, 0.2, 0.999, False) == (False, "cf_saturated"))
    check("B4 κ=0 ⇒ nonfinite",
          classify_trust(0.0, 0.2, 0.5, False) == (False, "nonfinite"))
    check("B5 cf1=1.0（不满足 ∈(0,1)）⇒ nonfinite",
          classify_trust(0.02, 1.0, 0.5, False) == (False, "nonfinite"))
    check("B6 合法点 ⇒ 可信 + reason=ok",
          classify_trust(0.02, 0.2, 0.7, False) == (True, "ok"))
    check("B7 §边界 cf1=0.6 整（不 > 阈）⇒ 仍可信",
          classify_trust(0.02, 0.6, 0.7, False) == (True, "ok"))
    check("B8 §边界 cf1=0.600001 ⇒ 判饱和（严格大于才拦）",
          classify_trust(0.02, 0.600001, 0.7, False) == (False, "cf_saturated"))
    check("B9 非有限 κ（nan）⇒ nonfinite",
          classify_trust(float("nan"), 0.2, 0.5, False) == (False, "nonfinite"))

    # ------------------------------------------- C convergence_report（合成）
    mono = _mk_series([_pt(12, 0.03000), _pt(16, 0.02900), _pt(20, 0.02890),
                       _pt(25, 0.02889)])
    cv = convergence_report(mono)
    check("C1 残差单调下降 + 小离散 ⇒ converged=True 且 budget_met=True",
          cv["converged"] and cv["budget_met"],
          "res=%s spread=%.4f" % (cv["residuals"], cv["spread_rel"]))

    # 🔴 本轮真实血案复现：残差 [0.002210, 0.013622] —— 先降后升，非单调
    realr = _mk_series([_pt(16, REAL_KAPPAS_30[0]),
                        _pt(20, REAL_KAPPAS_30[1]),
                        _pt(25, REAL_KAPPAS_30[2])])
    rc = convergence_report(realr)
    check("C2 🔴 血案复现：残差非单调 ⇒ monotone=False 且 converged=False",
          rc["monotone_decreasing_residual"] is False and rc["converged"] is False,
          "res=%s" % (rc["residuals"],))
    # 独立重算残差（不读模块自报）
    ind_res = [abs(a - b) for a, b in zip(REAL_KAPPAS_30, REAL_KAPPAS_30[1:])]
    check("C3 独立重算残差 == 模块自报（不读自报值）",
          all(abs(a - b) < 1e-12 for a, b in zip(ind_res, rc["residuals"])),
          "ind=%s got=%s" % (ind_res, rc["residuals"]))
    check("C4 残差非单调 ⇒ reasons 含「判据 D 不成立」",
          any("判据 D" in r for r in rc["reasons"]), "reasons=%s" % rc["reasons"])

    big = _mk_series([_pt(16, 0.030), _pt(20, 0.030), _pt(25, 0.020)])
    bc = convergence_report(big)
    check("C5 离散度超预算（33%）⇒ budget_met=False",
          (not bc["budget_met"]) and bc["spread_rel"] > UNCERTAINTY_BUDGET_REL,
          "spread=%.4f" % bc["spread_rel"])
    # 独立重算 spread
    ks = [0.030, 0.030, 0.020]
    ind_spread = (max(ks) - min(ks)) / (sum(ks) / len(ks))
    check("C6 独立重算离散度 == 模块自报",
          abs(ind_spread - bc["spread_rel"]) < 1e-12,
          "ind=%.6f got=%.6f" % (ind_spread, bc["spread_rel"]))

    few = _mk_series([_pt(16, 0.030), _pt(20, 0.028, trusted=False, reason="winding")])
    fc = convergence_report(few)
    check("C7 可信档 <2 ⇒ reasons 点明且不声称收敛",
          (len(fc["trusted_kappas"]) == 1) and (not fc["converged"])
          and any("不足 2" in r for r in fc["reasons"]),
          "reason=%s" % fc["reasons"])
    check("C8 不可信档被剔除（不进 trusted_kappas）",
          fc["trusted_kappas"] == [0.030], "got=%s" % fc["trusted_kappas"])

    allbad = _mk_series([_pt(16, 0.03, trusted=False, reason="winding"),
                         _pt(20, 0.02, trusted=False, reason="cf_saturated")])
    ac = convergence_report(allbad)
    check("C9 全不可信 ⇒ spread=inf 且 finest=None 且不收敛",
          math.isinf(ac["spread_rel"]) and ac["finest_trusted_kappa"] is None
          and not ac["converged"])
    check("C10 无残差可算（<2 可信）⇒ monotone 为 None（不假装单调）",
          ac["monotone_decreasing_residual"] is None)

    # ------------------------------------------------------------ D 解析对比
    av = analytic_vs_fdtd(0.30, 0.024114)
    check("D1 独立重算倍数 == 模块自报",
          abs((analytic_kappa(0.30) / 0.024114) - av["ratio_analytic_over_fdtd"]) < 1e-9,
          "ratio=%.4f" % av["ratio_analytic_over_fdtd"])
    check("D2 偏差远超预算 ⇒ analytic_over_budget=True（如实报出）",
          av["analytic_over_budget"] and av["rel_dev_analytic_vs_fdtd"] > 1.0,
          "rel=%.2f" % av["rel_dev_analytic_vs_fdtd"])
    check("D3 analytic_kappa 复用 D-37 gap_to_kappa（逐位一致，不重写公式）",
          abs(analytic_kappa(0.25) - 0.4884635) < 1e-6,
          "=%.7f" % analytic_kappa(0.25))
    check("D4 κ_fdtd ≤ 0 ⇒ 必 raise",
          _rejects(lambda: analytic_vs_fdtd(0.30, 0.0), RingKappaCalibError)
          and _rejects(lambda: analytic_vs_fdtd(0.30, -1.0), RingKappaCalibError))
    check("D5 偏差随 gap 变化（解析模型对 gap 的敏感度与 FDTD 不同）",
          abs(analytic_vs_fdtd(0.25, 0.022434)["ratio_analytic_over_fdtd"]
              - analytic_vs_fdtd(0.40, 0.003810)["ratio_analytic_over_fdtd"]) > 5.0)

    # -------------------------------------------------------- E 取数接口
    a_hit = kappa_c_lookup(0.30)
    check("E1 backend='analytic' ⇒ 标 it 为占位",
          a_hit["backend"] == "analytic-placeholder"
          and abs(a_hit["kappa_c_rad_um"] - analytic_kappa(0.30)) < 1e-12)
    tab = kappa_c_from_table(0.30, 1.55)
    check("E2 标定表命中（gap=0.30 λ=1.55 在已签发表内）",
          tab is not None and tab["backend"] == "fdtd-table"
          and abs(tab["kappa_c_rad_um"] - 0.01505) < 1e-9,
          "got=%s" % (tab or {}).get("kappa_c_rad_um"))
    check("E3 🔴 越界必 raise（**不静默回退解析模型**）",
          _rejects(lambda: kappa_c_lookup(0.10, 1.55, backend="fdtd-table"),
                   RingKappaCalibError))
    check("E4 未知 backend ⇒ 必 raise",
          _rejects(lambda: kappa_c_lookup(0.30, 1.55, backend="magic"),
                   RingKappaCalibError))
    check("E5 表值与已签发 JSON 逐位一致（不重算、不插值误差）",
          abs(kappa_c_from_table(0.35, 1.60)["kappa_c_rad_um"] - 0.007234) < 1e-9,
          "got=%s" % kappa_c_from_table(0.35, 1.60)["kappa_c_rad_um"])
    check("E6 表查询显式标 uncertainty_rel=None（表不带跨网格离散度）",
          tab["uncertainty_rel"] is None)

    # ------------------------------------------------- F 端到端 FDTD（~30s）
    ser = kappa_c_series(0.30, 1.55, dl_factors=(16, 20, 25))
    check("F1 三档序列返回 3 点且 n_points 自洽",
          ser["n_points"] == 3 and len(ser["points"]) == 3)
    check("F2 所有点 κ 有限且 > 0",
          all(math.isfinite(p["kappa_c_rad_um"]) and p["kappa_c_rad_um"] > 0
              for p in ser["points"]))
    check("F3 所有点 cf ∈ (0,1)（能流比物理带内）",
          all(0.0 < p["cf1"] < 1.0 and 0.0 < p["cf2"] < 1.0 for p in ser["points"]))
    check("F4 至少 1 档可信", ser["n_trusted"] >= 1, "n_trusted=%d" % ser["n_trusted"])
    conv = convergence_report(ser)
    check("F5 残差个数 == 可信档数 − 1",
          len(conv["residuals"]) == max(conv["n_trusted"] - 1, 0),
          "res=%s n_trusted=%d" % (conv["residuals"], conv["n_trusted"]))
    check("F6 🔴 跨网格离散度 > 10% 预算 ⇒ budget_met=False（把「不达标」机器化）",
          (not conv["budget_met"]) and conv["spread_rel"] > UNCERTAINTY_BUDGET_REL,
          "spread=%.4f budget_met=%s" % (conv["spread_rel"], conv["budget_met"]))
    check("F7 🔴 残差非单调 ⇒ converged=False（**不**声称 FDTD 已收敛）",
          conv["monotone_decreasing_residual"] is False and not conv["converged"],
          "res=%s" % (conv["residuals"],))
    check("F8 离散度 == 独立重算（不读自报值）",
          abs(conv["spread_rel"]
              - (max(conv["trusted_kappas"]) - min(conv["trusted_kappas"]))
              / (sum(conv["trusted_kappas"]) / len(conv["trusted_kappas"]))) < 1e-12)
    check("F9 最细可信档 = dl25（序列末位）",
          conv["finest_trusted_dl_factor"] == 25,
          "finest_dl=%s" % conv["finest_trusted_dl_factor"])

    # ---------------------------------------- G 粗档扰动 + λ 依赖（各 ~3s）
    coarse = kappa_c_series(0.25, 1.55, dl_factors=(16,))
    cc = convergence_report(coarse)
    check("G1 🔴 反向：粗档 gap=0.25/dl16 必被判 winding（假结果被挡住）",
          coarse["n_trusted"] == 0 and coarse["points"][0]["reason"] == "winding",
          "pt=%s" % coarse["points"][0])
    k30 = kappa_c_series(0.30, 1.55, dl_factors=(16,))["points"][0]["kappa_c_rad_um"]
    k25 = coarse["points"][0]["kappa_c_rad_um"]
    check("G2 反向：扰动 gap ⇒ κ_c 必变（且未收盘前不声称方向）",
          abs(k30 - k25) > 1e-6, "k(0.30)=%.6f k(0.25)=%.6f" % (k30, k25))
    lam50 = kappa_c_series(0.30, 1.50, dl_factors=(16,))["points"][0]["kappa_c_rad_um"]
    lam60 = kappa_c_series(0.30, 1.60, dl_factors=(16,))["points"][0]["kappa_c_rad_um"]
    check("G3 λ 依赖：κ_c(λ=1.60) > κ_c(λ=1.50)（与 D-57/D-59 同向）",
          lam60 > lam50, "k(1.50)=%.6f k(1.60)=%.6f" % (lam50, lam60))

    # ------------------------------------ H 回填入口（几何不动，只换 κ_c）
    from lda_layout.wdm_mesh_pnr import wdm_ring_anchor  # noqa: E402
    base = wdm_ring_anchor(1550.0, n_g=2.45, m=30, gap=0.30)
    anch = calibrated_ring_anchor(1550.0, n_g=2.45, m=30, gap=0.30,
                                 dl_factors=(16, 20))
    check("H1 几何逐位一致（R / L_couple / FSR 不由 κ_c 改动而漂移）",
          anch["R_um"] == base["R_um"]
          and anch["L_couple_um"] == base["L_couple_um"]
          and anch["FSR_nm"] == base["FSR_nm"],
          "R=%s|%s Lc=%s|%s" % (anch["R_um"], base["R_um"],
                                anch["L_couple_um"], base["L_couple_um"]))
    check("H2 backend 标记为 fdtd-2d-calibrated",
          anch["kappa_backend"] == "fdtd-2d-calibrated")
    kc = anch["kappa_c_rad_um"]
    _ind_kring = math.sin(kc * anch["L_couple_um"])
    check("H3a k_ring == 独立重算 sin(κ_c·L_couple)（容 6 位报告精度）",
          abs(anch["k_ring"] - _ind_kring) <= 1e-6,
          "k_ring=%.6f ind=%.9f" % (anch["k_ring"], _ind_kring))
    check("H3b k_ring 相对误差 ≤ 1e-5（防 6 位精度掩盖量级错误）",
          abs(anch["k_ring"] - _ind_kring) / max(abs(_ind_kring), 1e-30) <= 1e-5,
          "rel=%.3e" % (abs(anch["k_ring"] - _ind_kring) / max(abs(_ind_kring), 1e-30)))
    check("H4 κ_c 已从解析占位切到 FDTD（与基版不同）",
          kc is not None and abs(kc - base["kappa_c_rad_um"]) > 1e-6,
          "fdtd=%.6f analytic=%.6f" % (kc, base["kappa_c_rad_um"]))
    _ks_t = [p["kappa_c_rad_um"] for p in anch["kappa_series"] if p["trusted"]]
    _ind_spread = ((max(_ks_t) - min(_ks_t)) / (sum(_ks_t) / len(_ks_t))
                   if _ks_t else float("inf"))
    check("H5 不确定度已报出且 == 序列独立重算（容 4 位报告精度）",
          anch["kappa_uncertainty_rel"] is not None
          and anch["kappa_uncertainty_rel"] > 0.0
          and abs(anch["kappa_uncertainty_rel"] - _ind_spread) <= 1e-4,
          "got=%s ind=%.6f" % (anch["kappa_uncertainty_rel"], _ind_spread))
    check("H6 解析 vs FDTD 偏差被写入返回（不隐藏占位误差）",
          "analytic_vs_fdtd" in anch
          and anch["analytic_vs_fdtd"]["ratio_analytic_over_fdtd"] > 10.0,
          "ratio=%.2f" % (anch.get("analytic_vs_fdtd") or {})
          .get("ratio_analytic_over_fdtd", -1))
    check("H7 honest_note 明写预算达标与否",
          ("达标" in anch["honest_note"]) or ("未达标" in anch["honest_note"]))
    check("H8 收敛子报告字段齐全（residuals / mono / spread / reasons）",
          all(k in anch["kappa_convergence"]
              for k in ("residuals", "monotone_decreasing_residual",
                        "spread_rel", "budget_met", "reasons")))
    check("H9 几何字段仍在（回填不删原锚字段）",
          all(k in anch for k in ("R_um", "L_couple_um", "FSR_nm", "kappa_c_rad_um",
                                  "k_ring", "wl_nm", "n_g", "m", "gap_um")))

    # ------------------------------------------------------------------ 汇总
    total = PASS + FAIL
    print("-" * 74)
    print("ring_kappa_calib smoke：%d PASS / %d FAIL / 共 %d 项" % (PASS, FAIL, total))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
