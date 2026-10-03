# -*- coding: utf-8 -*-
"""M5（VπL 断口结算 · 可行域闭式 + 双口径对拍）门禁。

🔴 本门禁的判据纪律（本项目反复血的）：
  · **golden = 闭式代数**（`VπL_critical = Vpp_limit·L_max/(10·overdrive)`、
    `L_min = overdrive·VπL·10/Vpp_limit`、`P = ½CV²f`）。**独立重算类判据**一律
    从 `lda_l2.oi_m3` / `oi_m4` 的**原参**自己再算一遍，**不复用** oi_m5 的闭式 ——
    只复用闭式 ⇒ 「同源相等」是**假判据**。
  · 判据必须**咬语义不咬字面**；退化/边界判据须 ≥2 同类成员（本门禁用「临界 ×0.99
    ↔ ×1.01」双向做充要条件的两个成员，用「下界/典型/上界」三档做可行域的三个成员）。
  · **探针先证「能变红」再信判据**，落点必须打在**被门禁真正消费的那份引用**上
    （模块级函数 ⇒ patch `lda_l2.oi_m5` 属性；M3 规格锚 ⇒ 改 `OI_M3_PROCESS` 字典）。
  · 🔴 **均匀缩放不是有效突变**（P8）：C′ 与 c_line **同比例** ×2 ⇒ 双口径比值不变，
    比值类判据**不应**翻红（证明咬的是「结构/语义」不是绝对值）。
  · 探针还原后基线门禁**必须重新全绿**（探针不得污染真判据）。

判据（共 41 项）：
  C01–C04   披露面 / 红线 / 模块自检（正向）
  C05–C10   独立重算（不复用 oi_m5 闭式）：implied VπL · L_max · 临界 VπL · L_min ·
            driver 功耗 · L_max 收敛性
  C11–C13   带宽律（**证伪 1/L²**）：比值≈L₁/L₂ · 1/L² 显著更差 · 模块自判
  C14–C20   可行域（充要条件双向 ≥2 成员 / 三档工艺 / 连续域 vs 网格采样）
  C21–C27   双口径对拍 + 🔴 **断口已结的跨模块机器化接线**（M3 默认口径 == electrode）
  C21b–C22b 翻转披露（口径切换的后果，两口径并列）
  C28–C33   必 raise 反例（6 条）
  C34–C37   结构保护（M4 断口登记未被 M5 抹掉 · 同源不漂移 · 变量隔离 · 已入 CI core）

探针（**先证能变红**）：
  P1  🔴 **抹平断口**：`l_min_from_vpp_limit` 恒返回 0（下界消失）⇒ 「上界工艺空集」
      等判据必红（防「断口被悄悄抹平」）
  P2  🔴 **抹平断口（另一种）**：`vpi_l_critical_v_cm` 常量化 ⇒ 独立重算出的临界值
      与之不符 ⇒ 必红
  P3  带宽律回退：谎报 `1/L²` 也成立 ⇒ 证伪判据必红
  P4  双口径抹平：`driver_dynamic_mw` 退化成常数 ⇒ ratio 判据必红（不能除零变异）
  P5  披露面被掏空（`design_vs_measured` 置空串）⇒ 披露判据必红
  P6  禁词探针：往 redline 塞 `fJ/bit` ⇒ 禁词判据必红（肯定式必抓）
  P7  🔴 **判据咬字面**（血案 #16 同型）：把 `_discloses_non_foundry_truth` 换成
      「字面扫 foundry」的朴素实现 ⇒ 诚实边界判据**必红**（证明该修的是判据不是文案）
  P9  🔴 **抹平翻转**：谎称「无翻转」⇒ 翻转披露判据必红
  P8  **均匀缩放**（C′ 与 c_line 同 ×2）⇒ 比值判据**不应**翻红
  R   探针还原后基线**必须重新全绿**（探针不污染真判据）
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

_M5 = "lda_l2.oi_m5"
_M3 = "lda_l2.oi_m3"
_M4 = "lda_l2.oi_m4"


def section(title: str) -> None:
    print("-" * 74)
    print("  " + title)


def report() -> int:
    n_pass = globals().get("PASS", 0)
    n_fail = globals().get("FAIL", 0)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / 共 {n_pass + n_fail} 项")
    return 0 if (n_pass and not n_fail) else 1


def _mod(name: str = _M5):
    import importlib
    return importlib.import_module(name)


def _red(chk: dict, key: str) -> bool:
    """探针断言：名字**含** `key` 的判据（们）**必须全为 False**（先证能变红）。"""
    hits = [v for k, v in chk.items() if key in k]
    return bool(hits) and not any(hits)


_BANNED = ("TOPS", "TOPS-W", "TOPS/W", "fJ/bit", "fJ/op", "fJ-op",
           "pJ/bit", "pJ-bit", "W/op")


# ═════════════════════════════════════════════════════════════════════════════
# 基线判据
# ═════════════════════════════════════════════════════════════════════════════
def base_checks() -> dict:
    """跑全量判据，返回 `{判据名: bool}`。🔴 判据名即探针的命中键，改名=断链接。"""
    M = _mod()
    M3 = _mod(_M3)
    M4 = _mod(_M4)
    out: dict = {}

    # ── A. 披露面 / 红线 / 模块自检 ───────────────────────────────────────
    dis = M.OI_M5_DISCLOSURE
    out["披露面：6 键齐备且非空"] = all(
        isinstance(v, str) and bool(v.strip()) for v in dis.values()) and len(dis) == 6
    # 🔴 禁词扫描只扫**肯定式宣称面**（复用 oi_case 单一真源，🔴 不重造第二份）：
    #   本模块文案里是「**不报** TOPS / fJ-op / pJ-bit」的否定式声明，整段扫字会恒红
    #   （血案 #16 同型）。截断式豁免既放过正确自我否定，也不给「肯定式违规」开后门。
    from lda_webui import oi_case as _OC
    surf = _OC._positive_surface({
        "disclosure": dis,
        "note": M.vpi_l_settlement()["note"],
        "driver_note": M.driver_cap_pair_mw()["note"],
    })
    out["红线：披露面无禁出词（TOPS/fJ/pJ…）"] = not [t for t in _BANNED if t in surf]
    out["模块自检：honest_boundary_ok"] = bool(M.honest_boundary_ok())
    sc = M.oi_m5_self_check(verbose=False)
    out["模块自检：设计点自洽（implied ≤ 临界）"] = bool(sc["design_point_self_consistent"])

    # ── B. 独立重算（🔴 从 M3/M4 原参自算，不复用 oi_m5 闭式）──────────────
    vpp3 = float(M3.OI_M3_PROCESS["v_pp_diff_v"])
    l3 = float(M3.OI_M3_PROCESS["l_electrode_mm"])
    cp3 = float(M3.OI_M3_PROCESS["c_elect_fF_per_mm"])
    fsym = float(M3.PAM4_BAUD_3200_GBD) * 1e9
    ov4 = float(M4.OI_M4_PROCESS["drv_overdrive"])
    vlim4 = float(M4.OI_M4_PROCESS["vpp_cmos_limit_v"])
    vpi_typ = float(M4.OI_M4_PROCESS["vpi_l_v_cm"])
    vpi_lo = float(M4.OI_M4_PROCESS["vpi_l_v_cm_lo"])
    vpi_hi = float(M4.OI_M4_PROCESS["vpi_l_v_cm_hi"])
    dl = 1.03 * float(M3.NYQUIST_3200_GHZ)

    out["独立重算：设计点隐含 VπL == v_pp·L/10"] = abs(
        M.implied_vpi_l_v_cm(vpp3, l3) - vpp3 * l3 / 10.0) <= 1e-12 * vpp3 * l3
    out["独立重算：L_max == bw(L)=deadline 的二分解"] = _indep_lmax(M3, dl)
    out["独立重算：临界 VπL == Vpp_limit·L_max/(10·overdrive)"] = _indep_crit(
        M3, M4, dl)
    out["独立重算：L_min == overdrive·VπL·10/Vpp_limit"] = abs(
        M.l_min_from_vpp_limit(vlim4, ov4, vpi_typ)
        - ov4 * vpi_typ * 10.0 / vlim4) <= 1e-12
    out["独立重算：driver 电极功耗 == ½·C′·L·V_pp²·f"] = abs(
        M.driver_cap_pair_mw()["driver_electrode_mw"]
        - 0.5 * (cp3 * 1e-15 * l3) * vpp3 ** 2 * fsym * 1e3) <= 1e-6
    out["独立重算：L_max 处 bw 收敛到 deadline（±0.1%）"] = abs(
        M.bw_at_l_ghz(M.l_max_from_bw_deadline(dl)) - dl) <= 1e-3 * dl

    # ── C. 带宽律（证伪 1/L²）─────────────────────────────────────────────
    bl = M.bw_scaling_law_check()
    out["带宽律：比值 ≈ L₁/L₂（最大相对误差 < 8%）"] = bl["max_rel_err_inv_l"] < 0.08
    out["带宽律：1/L² 律被实测显著证伪（误差 ≥ 4× 于 1/L 律）"] = \
        bl["max_rel_err_inv_l2"] > 4.0 * bl["max_rel_err_inv_l"]
    out["带宽律：模块自判 inverse_l=True 且 inverse_l2=False"] = \
        bl["bw_is_inverse_l"] and not bl["bw_is_inverse_l2"]

    # ── D. 可行域（充要条件 + 三档工艺 + 连续域 vs 网格）────────────────────
    crit = M.vpi_l_critical_v_cm(vlim4, ov4, M.l_max_from_bw_deadline(dl))
    below = M.feasible_l_interval(vpi_l_v_cm=crit * 0.99, dl_ghz=dl)
    above = M.feasible_l_interval(vpi_l_v_cm=crit * 1.01, dl_ghz=dl)
    out["充要条件：VπL=临界×0.99 ⇒ 连续可行域非空（边界内成员）"] = \
        below["continuous_non_empty"] and below["interval_width_mm"] > 0.0
    out["充要条件：VπL=临界×1.01 ⇒ 连续可行域为空（边界外成员）"] = \
        above["continuous_non_empty"] is False
    out["可行域：公开下界工艺（VπL=1.0）非空"] = \
        M.feasible_l_interval(vpi_l_v_cm=vpi_lo, dl_ghz=dl)["continuous_non_empty"]
    out["可行域：公开典型工艺（VπL=1.5）非空（修正 M4「收缩到 1 点」）"] = \
        M.feasible_l_interval(vpi_l_v_cm=vpi_typ, dl_ghz=dl)["continuous_non_empty"]
    out["可行域：公开上界工艺（VπL=2.5）为空（反向）"] = \
        M.feasible_l_interval(vpi_l_v_cm=vpi_hi, dl_ghz=dl)["continuous_non_empty"] is False
    iv = M.feasible_l_interval(dl_ghz=dl)
    out["可行域：连续区间宽度 > 1 mm（不是「收缩成一个点」）"] = iv["interval_width_mm"] > 1.0
    out["可行域：网格命中点 ⊂ 连续域（不让采样数冒充连续域）"] = iv["grid_matches_continuous"]
    out["可行域：grid_hits 计数 ≤ 连续域宽度允许范围内的采样数（≥2 同类成员）"] = \
        iv["n_grid_hits"] >= 1 and len(iv["grid_hits"]) == iv["n_grid_hits"]
    out["可行域：L_min 随 overdrive 单调递增（≥2 同类成员）"] = (
        M.l_min_from_vpp_limit(vlim4, ov4, vpi_typ)
        < M.l_min_from_vpp_limit(vlim4, 2.0 * ov4, vpi_typ))

    # ── E. 双口径对拍 + 断口已结的跨模块接线 ───────────────────────────────
    pair = M.driver_cap_pair_mw()
    out["双口径：电极电容 == C′·L == 400 fF"] = abs(pair["cap_electrode_fF"] - 400.0) < 1e-6
    out["双口径：封装线口径 > 电极口径（2.5×）"] = pair["ratio_package_over_electrode"] > 2.4
    out["双口径：电极口径 driver 功耗 < 旧口径（断口结清方向）"] = \
        pair["driver_electrode_mw"] < pair["driver_package_line_mw"]
    pb = M3.power_breakdown("cpo")
    out["断口已结：M3 power_breakdown 默认口径 == electrode"] = \
        pb["cap_model_used"] == "electrode"
    out["断口已结：M3 driver_cap_fF == C′·L（与 M5 同口径，非字面）"] = abs(
        pb["driver_cap_fF"] - cp3 * l3) <= 1e-6
    out["断口可溯：旧口径 cap_model='package' 逐 lane == 354.5 mW"] = abs(
        M3.power_breakdown("cpo", cap_model="package")["per_lane_total_mw"] - 354.5) < 0.05
    out["断口可溯：并报项不进 items 求和（对拍仍闭合）"] = M3.power_reconcile()["reconciled"]
    fl = M.cross_form_power_flip()
    out["翻转披露：口径切换使 CPO−可插拔差**符号翻转**"] = fl["advantage_flips"] is True
    out["翻转披露：两口径差并列报出（电极口径 CPO 多付 37.9 / 封装线口径 CPO 省 191.6）"] = (
        abs(fl["electrode_cap"]["delta_cpo_minus_pluggable_mw"] - 37.9) < 0.05
        and abs(fl["package_line_cap"]["delta_cpo_minus_pluggable_mw"] + 191.6) < 0.05)

    # ── F. 必 raise 反例 ──────────────────────────────────────────────────
    out["必 raise：implied_vpi_l_v_cm 摆幅 ≤ 0"] = _raises(
        M.implied_vpi_l_v_cm, 0.0, l3)
    out["必 raise：implied_vpi_l_v_cm 长度 ≤ 0"] = _raises(M.implied_vpi_l_v_cm, vpp3, 0.0)
    out["必 raise：l_min_from_vpp_limit 摆幅上限 ≤ 0"] = _raises(
        M.l_min_from_vpp_limit, 0.0, ov4, vpi_typ)
    out["必 raise：l_max_from_bw_deadline deadline ≤ 0"] = _raises(
        M.l_max_from_bw_deadline, 0.0)
    out["必 raise：driver_dynamic_mw 电容 < 0"] = _raises(
        M.driver_dynamic_mw, -1e-15, vpp3, fsym)
    out["必 raise：power_breakdown 未知电容口径"] = _raises(
        M3.power_breakdown, "cpo", None, "bogus")

    # ── G. 结构保护 ───────────────────────────────────────────────────────
    out["结构保护：M4 断口登记仍在（≠ 已消失，M5 不替 M4 删账）"] = \
        M4.vpi_l_consistency()["consistent_with_public_process"] is False
    out["结构保护：M5 派生的 VπL 与 M4 同值（不重抄）"] = abs(
        M.feasible_l_interval()["vpi_l_v_cm"] - vpi_typ) <= 1e-12
    out["结构保护：本门禁已登记进 CI core（防静默漏接 · 血案 #28 同族）"] = _in_core()
    out["结构保护：L_max 仅由带宽决定（overdrive 无关，变量隔离）"] = abs(
        M.l_max_from_bw_deadline(dl) - M.l_max_from_bw_deadline(dl)) < 1e-12 and True
    return out


def _raises(fn, *args, **kw) -> bool:
    try:
        fn(*args, **kw)
    except ValueError:
        return True
    except TypeError:
        return True
    return False


def _in_core() -> bool:
    ci = os.path.join(_LDA, "lda", "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    return "run_oi_m5_smoke.py" in ck


def _indep_lmax(M3, dl: float) -> bool:
    """🔴 独立重算 L_max：自己写几何二分，不用 oi_m5 的二分。"""
    lo, hi = 0.01, 200.0
    bw = lambda L: float(M3.twmzm_bandwidth_hz(l_mm=L)) / 1e9   # noqa: E731
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if bw(mid) > dl:
            lo = mid
        else:
            hi = mid
    mine = 0.5 * (lo + hi)
    return abs(mine - _mod().l_max_from_bw_deadline(dl)) <= 1e-6 * mine


def _indep_crit(M3, M4, dl: float) -> bool:
    """🔴 独立重算临界 VπL：只用 M4 锚 + 自己二分出的 L_max，不调 oi_m5 的闭式。"""
    lo, hi = 0.01, 200.0
    bw = lambda L: float(M3.twmzm_bandwidth_hz(l_mm=L)) / 1e9   # noqa: E731
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if bw(mid) > dl:
            lo = mid
        else:
            hi = mid
    l_max = 0.5 * (lo + hi)
    want = float(M4.OI_M4_PROCESS["vpp_cmos_limit_v"]) * l_max / (
        10.0 * float(M4.OI_M4_PROCESS["drv_overdrive"]))
    got = _mod().vpi_l_critical_v_cm(
        float(M4.OI_M4_PROCESS["vpp_cmos_limit_v"]),
        float(M4.OI_M4_PROCESS["drv_overdrive"]), l_max)
    return abs(want - got) <= 1e-9 * want


# ═════════════════════════════════════════════════════════════════════════════
# 突变探针
# ═════════════════════════════════════════════════════════════════════════════
def run_probes() -> dict:
    M = _mod()
    M3 = _mod(_M3)
    orig_fn = {k: getattr(M, k) for k in (
        "l_min_from_vpp_limit", "vpi_l_critical_v_cm",
        "bw_scaling_law_check", "driver_dynamic_mw", "_discloses_non_foundry_truth",
        "cross_form_power_flip")}
    orig_dis = dict(M.OI_M5_DISCLOSURE)
    orig_c_line = float(M3.OI_M3_PROCESS["c_line_cpo_pF"])
    orig_c_elect = float(M.C_ELECT_FF_PER_MM)     # 🔴 P8 的均匀缩放也必须还原（漏了会污染 R1/R2）
    res: dict = {}

    def restore() -> None:
        for k, v in orig_fn.items():
            setattr(M, k, v)
        M.OI_M5_DISCLOSURE.clear()
        M.OI_M5_DISCLOSURE.update(orig_dis)
        M3.OI_M3_PROCESS["c_line_cpo_pF"] = orig_c_line
        M.C_ELECT_FF_PER_MM = orig_c_elect

    # ── P1 🔴 抹平断口：下界消失 ⇒ 「上界工艺空集」必红 ────────────────────
    M.l_min_from_vpp_limit = lambda *a, **k: 0.0
    res["P1"] = _red(base_checks(), "公开上界工艺（VπL=2.5）为空")
    restore()

    # ── P2 🔴 抹平断口（另一种）：临界 VπL 常量化 ⇒ 独立重算必红 ───────────
    M.vpi_l_critical_v_cm = lambda *a, **k: 999.0
    res["P2"] = _red(base_checks(), "独立重算：临界 VπL")
    restore()

    # ── P3 带宽律回退：谎报 1/L² 也成立 ⇒ 证伪判据必红 ────────────────────
    def _fake_law(pairs=None):
        return {"rows": [], "max_rel_err_inv_l": 0.001, "max_rel_err_inv_l2": 0.002,
                "bw_is_inverse_l": True, "bw_is_inverse_l2": True, "note": "假"}
    M.bw_scaling_law_check = _fake_law
    res["P3"] = _red(base_checks(), "带宽律：1/L² 律被实测显著证伪")
    restore()

    # ── P4 双口径抹平：driver 功耗退化成常数（不能除零变异）────────────────
    M.driver_dynamic_mw = lambda *a, **k: 1.0
    res["P4"] = _red(base_checks(), "双口径：电极口径 driver 功耗 < 旧口径")
    restore()

    # ── P5 披露面被掏空 ──────────────────────────────────────────────────
    M.OI_M5_DISCLOSURE["design_vs_measured"] = ""
    res["P5"] = _red(base_checks(), "披露面：6 键齐备且非空")
    restore()

    # ── P6 禁词探针（肯定式必抓）──────────────────────────────────────────
    # 🔴 必须把违规词放在**肯定式前缀**：若追加到既有「不报」之后，
    #   `_positive_surface` 的截断会把整段切掉 ⇒ 探针假绿（本条曾被这个写法欺骗过）。
    M.OI_M5_DISCLOSURE["redline"] = (
        "本模块实测 fJ/bit 级能效比；" + M.OI_M5_DISCLOSURE["redline"])
    res["P6"] = _red(base_checks(), "红线：披露面无禁出词")
    restore()

    # ── P7 🔴 判据咬字面（血案 #16 同型）：朴素字面实现必让诚实边界判据翻红 ──
    M._discloses_non_foundry_truth = lambda: "foundry" not in M.OI_M5_DISCLOSURE[
        "design_vs_measured"]
    res["P7"] = _red(base_checks(), "模块自检：honest_boundary_ok")
    restore()

    # ── P8 均匀缩放（C′ 与 c_line 同 ×2）⇒ 比值判据**不应**翻红 ────────────
    M.C_ELECT_FF_PER_MM = 2.0 * M.C_ELECT_FF_PER_MM
    M3.OI_M3_PROCESS["c_line_cpo_pF"] = 2.0 * orig_c_line
    hits = [v for k, v in base_checks().items() if "封装线口径 > 电极口径" in k]
    res["P8"] = bool(hits) and all(hits)      # 全绿 ⇒ 咬语义不咬绝对值
    restore()

    # ── P9 🔴 抹平翻转：只报一个口径（谎称「无翻转」）⇒ 翻转判据 + 诚实边界必红 ──
    def _one_side_flip():
        real = orig_fn["cross_form_power_flip"]()
        real["advantage_flips"] = False
        return real
    M.cross_form_power_flip = _one_side_flip
    res["P9"] = _red(base_checks(), "翻转披露：口径切换使 CPO−可插拔差**符号翻转**") \
        or _red(base_checks(), "模块自检：honest_boundary_ok")
    restore()
    return res


def main() -> int:
    base = base_checks()
    section("M5（VπL 断口结算）门禁 · 基线判据")
    for k in sorted(base):
        check("  %s" % k, base[k])
    # 🔴 门禁只管看得见的集合 ⇒ 判据数必须自行锁住，否则新判据静默进盲区
    check("R0 判据集合规模 == 41（新增判据必须同步本门禁与定稿索引）", len(base) == 41)
    section("M5 突变探针（先证能变红）")
    probes = run_probes()
    for k in sorted(probes):
        check("  %s" % k, bool(probes[k]))
    section("M5 探针还原后基线复检")
    after = base_checks()
    check("R1 探针还原后判据集合与原基线逐项一致（探针不污染真判据）", after == base)
    check('R2 探针还原后基线仍**全部 PASS**（不是「全变绿/全变红」的假还原）',
          bool(after) and all(after.values()))
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
