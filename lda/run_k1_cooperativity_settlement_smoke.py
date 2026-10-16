# -*- coding: utf-8 -*-
"""K 征程 · K1 协同度两口径**断口结算门禁**（缺口 G-K-2 · A 金级）。

断口本体（J5 章程 R3b 登记 ⇒ 本档结算）
----------------------------------------
`qs_m3c` 并存两个 `cooperativity` 函数，**二者不是同一个物理量**：
  · `g_form`  `C_g  = 4g²/(κ·γ)`    —— **协同度**（标准形式；语义由第三参数决定）
  · `qv_form` `C_qv = F_P·(γ_rad/γ₁)` —— **非协同度**（Purcell 因子 × 分支比）
且旧注释/账本 note 曾断言 `4g²/(κγ_rad) ≡ (3λ³Q/4π²V)(γ_rad/γ₁)` —— **该等式不成立**
（实测差 `2n·γ₁/γ_rad`），旧门禁只查 `C_g/F_P = 2n` ⇒ **无判据拦截**（假自洽）。

判据分节（**判据数实跑现数**）：
  A 结算面字段与并报（6）· B 闭式恒等式机器精度（4）· C 消费侧并报兑现（4）·
  D 旧断言纠正（3）· E 反向探针「抹平断口必红」（4）· F 红线（2）

🔴 `main()` 返回「真值」而非恒 0；一律走 `smoke_kit.make_check`（棘轮 J3）。
"""

from __future__ import annotations

import copy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # lda/
_ROOT = os.path.dirname(_HERE)                              # 仓库根
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402  # 助手单一来源（棘轮 J3）
from lda_l2 import qnet_transducer as TR  # noqa: E402
from lda_l2 import qs_m3c as M  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

#: 被订正的错误等式（断言两口径相等 · 纠正后全仓必须 0 命中）
_WRONG_FORMS = ("4g²/(κγ_rad)=(3λ³Q/4π²V)(γ_rad/γ₁)",
                "4g²/(κγ_rad) = (3λ³Q/4π²V)(γ_rad/γ₁)")
#: 正确闭式比值的机器标记（纠正后 4 个文件都必须出现）
_MARKER = "2n·γ₁/γ_rad"
_EDITED_FILES = ("lda/lda_l2/qs_m3c.py", "lda/run_qs_m3c_smoke.py",
                 "lda/lda_harness/_batch_qs_m3c_numeric.py",
                 "lda/lda_harness/benchmark_defs/part7.py")


def _read(rel):
    p = os.path.join(_ROOT, rel)
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 校验函数（供正向判据与反向探针共用）
# ---------------------------------------------------------------------------
def validate(cal, rep, notice) -> dict:
    r = {}

    # ── A 结算面字段与并报 ────────────────────────────────────────────
    _need = ("g_form", "qv_form", "ratio_g_over_qv", "ratio_closed_form",
             "is_cooperativity", "main_account", "calibers", "n_r", "purcell_F_P",
             "gamma_rad_s1", "gamma1_s1",
             "identity_2n_resid_rel", "ratio_closed_form_resid_rel")
    r["A1 结算面机读字段齐备"] = all(k in cal for k in _need)
    _ph = M.cavity_qed_physics()
    r["A2 两口径与 cavity_qed_physics 同源（非另算）"] = (
        cal["g_form"] == _ph["cooperativity_g_form"]
        and cal["qv_form"] == _ph["cooperativity_qv_form"])
    r["A3 两口径不相等（比值 > 1e3 ⇒ 确有断口 · 防「以为相等」）"] = (
        cal["ratio_g_over_qv"] > 1e3
        and abs(cal["g_form"] - cal["qv_form"]) / cal["g_form"] > 1e-3)
    r["A4 is_cooperativity 判定：g_form=True / qv_form=False"] = (
        cal["is_cooperativity"] == {"g_form": True, "qv_form": False})
    r["A5 主账口径 = g_form 且与模块常量一致"] = (
        cal["main_account"] == "g_form"
        == getattr(M, "COOPERATIVITY_MAIN_ACCOUNT", None))
    r["A6 口径元组 = (g_form, qv_form)"] = (
        tuple(cal["calibers"]) == ("g_form", "qv_form")
        == tuple(getattr(M, "COOPERATIVITY_CALIBERS", ())))

    # ── B 闭式恒等式（机器精度 · 🔴 **现算**，不读预计算字段） ─────────
    _2nfp = 2.0 * cal.get("n_r", 0.0) * cal.get("purcell_F_P", 0.0)
    r["B1 C_g = 2n·F_P（resid < 1e-12）"] = (
        _2nfp > 0.0
        and abs(cal.get("g_form", 0.0) - _2nfp) / _2nfp < 1e-12)
    _rc = cal.get("ratio_closed_form", 0.0)
    r["B2 C_g/C_qv = 2n·γ₁/γ_rad（resid < 1e-12）"] = (
        _rc > 0.0
        and abs(cal.get("ratio_g_over_qv", 0.0) - _rc) / _rc < 1e-12)
    _n, _g1, _gr = cal["n_r"], cal["gamma1_s1"], cal["gamma_rad_s1"]
    r["B3 比值两个因子可分解复算"] = (
        abs(cal["ratio_closed_form"] - (2.0 * _n) * (_g1 / _gr))
        / cal["ratio_closed_form"] < 1e-15)
    r["B4 C_std=4g²/(κγ₁) 与 C_g·(γ_rad/γ₁) 一致"] = (
        abs(cal["cooperativity_std_total_linewidth"]
            - cal["g_form"] * (_gr / _g1)) / cal["g_form"] < 1e-12)

    # ── C 消费侧并报兑现（G-K-2） ─────────────────────────────────────
    _c1 = ("qs_m3c_cooperativity_g_form", "qs_m3c_cooperativity_qv_form",
           "qs_m3c_cooperativity_ratio", "qs_m3c_cooperativity_ratio_closed_form")
    r["C1 换能层报告含两口径 + 比值四字段"] = all(k in rep for k in _c1)
    _gf, _qf = rep.get("qs_m3c_cooperativity_g_form", 0.0), rep.get("qs_m3c_cooperativity_qv_form", 0.0)
    r["C2 报告内两口径不相等（非选择性披露）"] = (
        bool(_gf) and abs(_gf - _qf) / _gf > 1e-3)
    r["C3 notice 字段齐备 + this_module_caliber == g_form"] = (
        notice.get("this_module_caliber") == "g_form"
        and notice.get("this_module_is_standard_cooperativity") is True
        and all(k in notice for k in ("this_module_cooperativity",
                                      "this_module_denominator")))
    _c_mod = TR.cooperativity()
    r["C4 换能层 C 值与 cooperativity_from_g 逐位一致（结算未改动公式）"] = (
        abs(_c_mod - M.cooperativity_from_g(TR.DEFAULT_G_RAD_S,
                                           TR.DEFAULT_KAPPA_MW_RAD_S,
                                           TR.DEFAULT_GAMMA_MECH_RAD_S)) < 1e-15)

    # ── D 旧断言纠正 ─────────────────────────────────────────────────
    _hits = {f: sum(_read(f).count(w) for w in _WRONG_FORMS) for f in _EDITED_FILES}
    r["D1 错误等式（断言两口径相等）全仓 0 命中"] = all(v == 0 for v in _hits.values())
    _mk = {f: _read(f).count(_MARKER) for f in _EDITED_FILES}
    r["D2 正确闭式比值标记出现在全部 4 个订正文件"] = all(v >= 1 for v in _mk.values())
    _smk = _read("lda/run_qs_m3c_smoke.py")
    r["D3 既有 F2 门禁注释已写明「比值闭式 · K1 已结算」"] = (
        "K1 已结算" in _smk and _MARKER in _smk)
    return r


def main() -> int:
    cal = M.cooperativity_calibers()
    rep = TR.transducer_report()
    notice = TR.cooperativity_caliber_notice()
    res = validate(cal, rep, notice)

    def emit(names):
        for n in names:
            check(n, res.get(n, False))

    print("[A] 结算面字段与并报")
    emit(["A1 结算面机读字段齐备",
          "A2 两口径与 cavity_qed_physics 同源（非另算）",
          "A3 两口径不相等（比值 > 1e3 ⇒ 确有断口 · 防「以为相等」）",
          "A4 is_cooperativity 判定：g_form=True / qv_form=False",
          "A5 主账口径 = g_form 且与模块常量一致",
          "A6 口径元组 = (g_form, qv_form)"])
    print("    C_g=%.12g · C_qv=%.12g · ratio=%.6f"
          % (cal["g_form"], cal["qv_form"], cal["ratio_g_over_qv"]))

    print("\n[B] 闭式恒等式（机器精度）")
    emit(["B1 C_g = 2n·F_P（resid < 1e-12）",
          "B2 C_g/C_qv = 2n·γ₁/γ_rad（resid < 1e-12）",
          "B3 比值两个因子可分解复算",
          "B4 C_std=4g²/(κγ₁) 与 C_g·(γ_rad/γ₁) 一致"])
    print("    identity_2n resid=%.3e · ratio resid=%.3e · C_std=%.12g"
          % (cal["identity_2n_resid_rel"], cal["ratio_closed_form_resid_rel"],
             cal["cooperativity_std_total_linewidth"]))

    print("\n[C] 消费侧并报兑现（G-K-2）")
    emit(["C1 换能层报告含两口径 + 比值四字段",
          "C2 报告内两口径不相等（非选择性披露）",
          "C3 notice 字段齐备 + this_module_caliber == g_form",
          "C4 换能层 C 值与 cooperativity_from_g 逐位一致（结算未改动公式）"])

    print("\n[D] 旧断言纠正")
    emit(["D1 错误等式（断言两口径相等）全仓 0 命中",
          "D2 正确闭式比值标记出现在全部 4 个订正文件",
          "D3 既有 F2 门禁注释已写明「比值闭式 · K1 已结算」"])

    print("\n[E] 反向探针（抹平断口必红 · 先证能变红）")
    t1 = copy.deepcopy(cal)
    t1["qv_form"] = t1["g_form"]                      # 抹平：让两口径相等
    t1["ratio_g_over_qv"] = 1.0
    check("E1 抹平 qv_form == g_form ⇒ A3 必红（确有断口）",
          not validate(t1, rep, notice)["A3 两口径不相等（比值 > 1e3 ⇒ 确有断口 · 防「以为相等」）"])
    t2 = copy.deepcopy(cal)
    t2["ratio_closed_form"] = 2.0 * t2["n_r"]         # 丢 γ₁/γ_rad 因子
    check("E2 比值闭式丢 γ₁/γ_rad 因子 ⇒ B2 必红",
          not validate(t2, rep, notice)["B2 C_g/C_qv = 2n·γ₁/γ_rad（resid < 1e-12）"])
    t3 = copy.deepcopy(cal)
    t3["main_account"] = "qv_form"                    # 主账口径翻转
    check("E3 主账口径翻转到 qv_form ⇒ A5 必红",
          not validate(t3, rep, notice)["A5 主账口径 = g_form 且与模块常量一致"])
    t4 = {k: v for k, v in rep.items() if k != "qs_m3c_cooperativity_qv_form"}
    check("E4 消费侧报告删掉 qv_form 字段 ⇒ C1 必红（防选择性披露）",
          not validate(cal, t4, notice)["C1 换能层报告含两口径 + 比值四字段"])

    print("\n[F] 红线")
    src = _read("lda/lda_l2/qs_m3c.py") + _read("lda/lda_l2/qnet_transducer.py") \
        + _read("lda/run_k1_cooperativity_settlement_smoke.py")
    sdk = [s for s in ("qiskit", "cirq", "pennylane", "qutip") if ("import " + s) in src]
    check("F1 主权边界：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）",
          not sdk, "命中=%s" % (sdk or "无"))
    try:
        import run_ci_regression as R
        in_core = os.path.basename(__file__) in R.CORE_SMOKES
    except Exception as ex:  # pragma: no cover
        in_core = False
        print("    （无法读取 CORE_SMOKES：%s）" % ex)
    check("F2 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core, "in_core=%s" % in_core)

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("K1 断口结算门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
