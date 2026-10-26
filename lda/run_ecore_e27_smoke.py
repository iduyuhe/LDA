# -*- coding: utf-8 -*-
"""E27 N×K 联合规模门禁（D-202 · v0.9.323）。

═══════════════════════════════════════════════════════════════════════════
本段审计两个从未被独立验证的东西：列共享 K 的收益、以及"N=64"这个规模
═══════════════════════════════════════════════════════════════════════════
① 🔴 **E23 的列共享 K 收益隐含 β=1（ADC 全静态），物理不成立**。
   `adc_power_w(bits, ceil(n/K), f_s)` = **ADC 数量 ÷K 而 f_s 不变**
   ⇒ 等于假设「一个 ADC 一次转换覆盖 K 列」，而采样率/转换周期必有一个 ×K，两者都没建模。
   正确口径：`P_adc(K) = n·f0·E_dyn + (n/K)·P_static` ⇒ **只有静态部分随 K 除**。
   净值 = `1/(1−β(1−1/K)) × e(K)/e(1)`；β=0.0188 时 **K=64 净亏 0.9918×**。

② 🔴 **E22–E26 的能效都在 N=64 上算，而 5% 预算只允许 N=12**。
   `E_op,adc = E_conv/(2NK)` ∝ 1/N ⇒ **N=12 的 ADC 项是 N=64 的 5.33×**（179.2 vs 33.6 fJ/op）。

③ ⇒ **能效第一杠杆 = 行线电阻**（r↓10× ⇒ N 12→42 ⇒ 能效 ×3.50），不是 K（×1.01）。

判什么
  A 模块自检（`joint_scale.joint_scale_self_check` **13 项**）
  B 关键事实（11 条）：N 上界 4 档 · ADC 摊薄 5.33× · β* 五点 · K 净收益正负两侧 ·
    可及能效 4 档 · vs Mythic 4 档 · 杠杆排序 · 收益矩阵含负 · 归一化分母 · 输出档位
  C 反向可证伪：**6 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import joint_scale as J     # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# 现算锚值（v0.9.323）
AN_N_CEIL = [12, 26, 42, 140]          # 5% 预算 · r_div 1/4/10/100
AN_DILUTION_12 = 5.33                  # N=12 vs N=64
AN_BETA_STAR = [0.00087, 0.00346, 0.01370, 0.02703, 0.06494]   # K=2/8/32/64/160
AN_K64_LOSS = 0.9918                   # β=0.0188 时 K=64 净收益
AN_K64_GAIN_HI = 1.3813                # β=0.30 时 K=64 净收益
AN_ATTAIN = [179.6, 82.9, 51.4, 15.4]  # 可及 N 下的 E_op（fJ/op）
AN_VS_MYTHIC = [21.6, 10.0, 6.2, 1.9]
AN_ROWLINE_BEST = 11.63
AN_K_BEST = 1.01


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else float("inf")


# ---------------------------------------------------------------------------
# B 关键事实
# ---------------------------------------------------------------------------
def _n_ceiling_ok() -> bool:
    return [r["n_max"] for r in J.n_ceiling_table()] == AN_N_CEIL


def _dilution_ok() -> bool:
    return _rel(J.adc_dilution(12)["ratio_vs_n64"], AN_DILUTION_12) < 0.01


def _beta_star_ok() -> bool:
    got = [J.k_breakeven_beta(k)["beta_star"] for k in (2, 8, 32, 64, 160)]
    return all(_rel(g, a) < 0.02 for g, a in zip(got, AN_BETA_STAR))


def _k64_loss_ok() -> bool:
    """B4 · 基准 β 下 K=64 必须**净亏**（守"不得把 K 说成收益"）。"""
    g = J.k_net_gain(64, J.BETA_PLACEHOLDER)
    return _rel(g["net_gain"], AN_K64_LOSS) < 0.01 and g["profitable"] is False


def _k64_gain_ok() -> bool:
    """B5 · 高 β 时 K=64 转正（符号由 β 决定 ⇒ 不可作设计杠杆）。"""
    g = J.k_net_gain(64, 0.30)
    return _rel(g["net_gain"], AN_K64_GAIN_HI) < 0.01 and g["profitable"] is True


def _attain_ok() -> bool:
    got = [r["e_op_fj"] for r in J.attainable_efficiency()]
    return all(_rel(g, a) < 0.02 for g, a in zip(got, AN_ATTAIN))


def _vs_mythic_ok() -> bool:
    got = [r["vs_mythic"] for r in J.attainable_efficiency()]
    return all(_rel(g, a) < 0.03 for g, a in zip(got, AN_VS_MYTHIC))


def _leverage_ok() -> bool:
    """B8 · 行线电阻必须**严格胜出** K，且倍数现算可复现。"""
    lr = J.leverage_ranking()
    r = max(l["gain"] for l in lr["levers"] if l["kind"] == "row_resistance")
    k = max(l["gain"] for l in lr["levers"] if l["kind"] == "column_share")
    return (lr["row_resistance_wins"] is True
            and _rel(r, AN_ROWLINE_BEST) < 0.02 and _rel(k, AN_K_BEST) < 0.02)


def _matrix_ok() -> bool:
    """B9 · K 收益矩阵必须**同时含正负**（守"不得只报正收益"）。"""
    gt = J.k_gain_table()
    return (sum(1 for r in gt if r["profitable"]) == 18
            and sum(1 for r in gt if not r["profitable"]) == 2)


def _normalize_ok() -> bool:
    """B10 · K 收益必须**相对 K=1 归一化**（K=1 本身有 0.043% 基线开销）。"""
    return abs(J.k_net_gain(1, 0.3)["net_gain"] - 1.0) < 1e-15


def main() -> int:
    print("=" * 74)
    print("E27 N×K 联合规模门禁（D-202）")
    print("=" * 74)

    print("\n[A] 模块自检（joint_scale.joint_scale_self_check）")
    ok_mod = J.joint_scale_self_check(verbose=True)
    check("A1 模块自检 13/13 全绿", ok_mod)

    print("\n[B] 关键事实")
    check("B1 5%% 预算 N 上界（r_div 1/4/10/100）= %s 行" % AN_N_CEIL, _n_ceiling_ok())
    check("B2 🔴 N=12 的 ADC 项 = N=64 的 %.2f×（**之前所有能效数字建在 N=64**）"
          % AN_DILUTION_12, _dilution_ok())
    check("B3 盈亏平衡 β*(K=2/8/32/64/160) = %s" % AN_BETA_STAR, _beta_star_ok())
    check("B4 🔴 β=%.4f < β*(64) ⇒ **K=64 净亏 %.4f×**"
          % (J.BETA_PLACEHOLDER, AN_K64_LOSS), _k64_loss_ok())
    check("B5 β=0.30 ⇒ K=64 净收益 %.4f× >1（**符号由 β 决定**）" % AN_K64_GAIN_HI,
          _k64_gain_ok())
    check("B6 可及 N 下能效 = %s fJ/op（N 由预算定 · 非 N=64）" % AN_ATTAIN, _attain_ok())
    check("B7 对应 vs Mythic 8.3 = %s×" % AN_VS_MYTHIC, _vs_mythic_ok())
    check("B8 🔴 能效第一杠杆 = **行线电阻**（%.2f× vs K %.2f×）"
          % (AN_ROWLINE_BEST, AN_K_BEST), _leverage_ok())
    check("B9 K 收益矩阵同时含正负收益（18 正 / 2 负 · **不得只报正收益**）", _matrix_ok())
    check("B10 K 收益**相对 K=1 归一化**（防把 0.043% 基线开销误算成损失）", _normalize_ok())
    check("B11 全部输出恒标 `MODEL_ESTIMATE`",
          J.k_net_gain(8, 0.1)["tier"] == "MODEL_ESTIMATE")

    # ------------------------------------------------------------------
    # C 突变探针（每条都必须变红）
    # ------------------------------------------------------------------
    print("\n[C] 反向可证伪探针")

    # C1：K 收益退回 E23 旧口径（ADC 功耗全除 K ⇒ static_gain ≡ K）⇒ 判据③ 必红
    _real = J.k_net_gain

    def _old_basis(k, beta, n_cols=64):
        r = _real(k, beta, n_cols)
        return {**r, "net_gain": float(k) * r["erosion_rel"],
                "static_gain": float(k)}

    with mock.patch.object(J, "k_net_gain", _old_basis):
        c1 = not _k64_loss_ok()
    check("C1 探针：K 收益退回 E23 口径（ADC 功耗全除 K）⇒ B4 必红", c1)

    # C2：ADC 摊薄改成与 N 无关 ⇒ B2 必红
    with mock.patch.object(J, "adc_dilution",
                           lambda n, anchor="a28_8b", share_k=1: {
                               "n": int(n), "ratio_vs_n64": 1.0,
                               "adc_energy_per_op_fj": 33.6, "tier": "MODEL_ESTIMATE"}):
        c2 = not _dilution_ok()
    check("C2 探针：ADC 摊薄写成与 N 无关（掩盖天花板）⇒ B2 必红", c2)

    # C3：β* 用错公式（e1/ek − 1）⇒ B3 必红
    def _bad_beta_star(k, n_cols=64):
        """**故意用错公式** `e1/ek − 1`（正解是 `1 − ek/e1`）。"""
        from lda_l2.ecore import col_share_dynamic as CD
        e_k = CD.mux_settling_erosion(n_cols, k_adc=k, keep_throughput=True)["erosion_factor"]
        e_1 = CD.mux_settling_erosion(n_cols, k_adc=1, keep_throughput=True)["erosion_factor"]
        return {"k": k, "beta_star": (e_1 / e_k - 1.0) / (1.0 - 1.0 / k),
                "tier": "MODEL_ESTIMATE"}

    with mock.patch.object(J, "k_breakeven_beta", _bad_beta_star):
        c3 = not _beta_star_ok()
    check("C3 探针：β* 改用错公式 `e1/ek − 1`（应 `1 − ek/e1`）⇒ B3 必红", c3)

    # C4：去掉 K=1 归一化（直接用 raw erosion）⇒ B10 必红
    def _raw_gain(k, beta, n_cols=64):
        r = _real(k, beta, n_cols)
        from lda_l2.ecore import col_share_dynamic as CD
        e_k = CD.mux_settling_erosion(n_cols, k_adc=int(k), keep_throughput=True)["erosion_factor"]
        return {**r, "net_gain": r["static_gain"] * e_k}

    with mock.patch.object(J, "k_net_gain", _raw_gain):
        c4 = not _normalize_ok()
    check("C4 探针：去掉 K=1 归一化（用 raw erosion）⇒ B10 必红", c4)

    # C5：宣称"K 是第一杠杆" ⇒ B8 必红
    with mock.patch.object(J, "leverage_ranking",
                           lambda budget_pct=5.0: {
                               "verdict": "K 是第一杠杆", "row_resistance_wins": False,
                               "levers": [{"kind": "row_resistance", "gain": 1.0},
                                          {"kind": "column_share", "gain": 64.0}],
                               "tier": "MODEL_ESTIMATE"}):
        c5 = not _leverage_ok()
    check("C5 探针：宣称「K 是第一杠杆」⇒ B8 必红（守「不得把 K 说成杠杆」）", c5)

    # C6：把可及能效硬写成 N=64（掩盖天花板）⇒ B6 必红
    with mock.patch.object(J, "attainable_efficiency",
                           lambda budget_pct=5.0, anchor="a28_8b", k=1: [
                               {"r_div": d, "label": "x", "n_max": 64, "adc_fj": 33.6,
                                "rest_fj": 0.12, "e_op_fj": 33.7, "vs_mythic": 4.06,
                                "gain_vs_base": 1.0} for d in (1, 4, 10, 100)]):
        c6 = not _attain_ok()
    check("C6 探针：可及能效硬写成 N=64 的值（掩盖天花板）⇒ B6 必红", c6)

    check("C7 全部探针还原后，模块自检与关键事实仍全绿",
          J.joint_scale_self_check() and _n_ceiling_ok() and _leverage_ok())

    # ------------------------------------------------------------------
    print("\n[K] CI 登记")
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e27_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E27 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
