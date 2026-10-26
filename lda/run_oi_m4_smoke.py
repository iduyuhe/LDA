# -*- coding: utf-8 -*-
"""M4（CPO 形态深化 · 热-光-电协同设计空间）门禁。

🔴 本门禁的判据纪律（本项目反复血的）：
  · **golden = 闭式物理律**（热光+热膨胀的材料闭式 / 高斯模场交叠 / FSR∝λ² /
    Pareto 非支配定义）。第二通道（M3 标定链 / M1 规划器 / M2b 热解）**只互验，不是 golden**。
  · 判据必须**咬语义不咬字面**；「同源相等」单独用是**假判据** ⇒ 每条 golden 都配
    第二独立通道或**退化/边界/双向**判据。
  · **探针先证「能变红」再信判据**；探针落点必须打在**被门禁真正消费的那份引用**上
    （模块级函数 → patch `lda_l2.oi_m4` / `lda_l2.oi_m3` 的属性，不能只改调用方）。
  · 还原后基线门禁**必须重新全绿**（探针不得污染真判据）。

判据（共 46 项，来自 `oi_m4.oi_m4_self_check`）：
  C01–C03  🔴 波段一致性（**断口 D4**：M4≡M2 且 ≠M1 默认 C-band）
  C04–C07  规格锚窗口（VπL / Si CTE / 玻璃 CTE / 模场）
  C08–C10  dλ/dT **双通路互锁**（标定链 ⟷ 材料闭式；含热膨胀项；用 n_eff 非 n_g）
  C11–C14  ① 热-光-电耦合链（Δλ 与 M3 残余同源 / 红移方向 / 单向加热器不可行 / 未跨模）
  C15–C21  ② 固化点预偏移（残余与补偿功率**由公式算出** / 一阶与②同源 / T_eq 代数一致）
  C22–C25  ③ 热态重规划（FSR 随 λ² 变 / 解仍有效 / 波长由 M4 波段派生）
  C26–C29  ④ 三形态矩阵（热耦合随距离递减 / 电损耗随总线递增 / 三域冲突 / θ 互异）
  C30–C33  ⑤ CTE 失准（漂移亚微米 / **反直觉诚实结论**：CTE 非主因 / 退化自检）
  C34–C41  ⑥ Pareto + VπL（全点非支配 / 两条约束真起作用 / 单调性 / 断口如实报出）
  C42–C44  ⑥b 可行性墙（公开 VπL 下**收缩** / 公开口径窄于 M3 隐含 / 最优 L ≠ M3 点）
  C45–C46  红线（honest_boundary_ok）

探针（**先证能变红**）：
  P1  材料闭式的热光系数错 2× ⇒ 双通路互锁必红
  P2  预偏移**忽略 ASIC 自热**（T_eq 退化为 T_amb）⇒ 残余/补偿功率归零判据必红
  P3  把「单向加热器不可行」**粉饰成可行** ⇒ ①链判据必红（防上游结论被抹平）
  P4  热致偏移置 0 ⇒ 热态重规划**温度白算** ⇒ FSR 缩放判据必红
  P5  🔴 M4 波段改成 1550（跨波段混用）⇒ 波段互锁必红
  P6  CTE 失配置 0 ⇒ 耦合损耗恒 0 ⇒ CTE 判据必红
  P7  CMOS 摆幅限值放到 1000 V ⇒ 摆幅约束失效 ⇒ ⑥ Pareto 判据必红
  P8  三形态 θ **全设相同** ⇒ 热耦合单调性判据必红
  P9  🔴 禁词扫描双向探针（肯定式必抓 / 否定式必豁免 / 嵌套必豁免）
  P10 **均匀缩放** vpi_l ×2 ⇒ Pareto **结构**判据**不应**翻红（证明咬语义不咬字面）
  R   探针还原后基线**必须重新全绿**（探针不污染真判据）
"""
from __future__ import annotations

import importlib
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')


def section(title: str) -> None:
    print("-" * 74)
    print("  " + title)


def report() -> int:
    n_pass = globals().get("PASS", 0)
    n_fail = globals().get("FAIL", 0)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / 共 {n_pass + n_fail} 项")
    return 0 if (n_pass and not n_fail) else 1


_M4 = "lda_l2.oi_m4"
_M3 = "lda_l2.oi_m3"

# 🔴 禁词（与 oi_case 同口径）：只扫**肯定式宣称面**
_BANNED = ("TOPS", "TOPS-W", "TOPS/W", "fJ/bit", "fJ/op", "fJ-op",
           "pJ/bit", "pJ-bit", "W/op")


def _mod(name: str = _M4):
    return importlib.import_module(name)


def base_checks() -> dict:
    """跑全量判据，返回 `{判据名: bool}`。"""
    M = _mod()
    return {name: bool(ok) for name, ok in M.oi_m4_self_check(verbose=False)["checks"]}


def _red(chk: dict, key: str) -> bool:
    """探针断言：名字**含** `key` 的判据（们）**必须全为 False**（先证能变红）。"""
    hits = [v for k, v in chk.items() if key in k]
    return bool(hits) and not any(hits)


def _surface(obj):
    """复用 `oi_case._positive_surface`（禁词只扫肯定式面），避免第二份实现漂移。"""
    from lda_webui import oi_case as _OC
    return _OC._positive_surface(obj)


def _banned_hits(obj) -> list:
    s = _surface(obj)
    return [t for t in _BANNED if t in s]


# ═════════════════════════════════════════════════════════════════════════════
# 突变探针
# ═════════════════════════════════════════════════════════════════════════════
def run_probes() -> dict:
    M = _mod()
    M3 = _mod(_M3)
    orig_fn = {k: getattr(M, k) for k in (
        "optical_thermal_slope_closed", "co_design_chain",
        "pareto_front_l_electrode", "_form_theta")}
    orig_m3 = {k: getattr(M3, k) for k in (
        "die_thermal_stack", "closed_loop_thermal_steady")}
    orig_proc = dict(M.OI_M4_PROCESS)
    res: dict = {}

    def restore_fns() -> None:
        for k, v in orig_fn.items():
            setattr(M, k, v)

    def restore_m3() -> None:
        for k, v in orig_m3.items():
            setattr(M3, k, v)
        M.OI_M4_PROCESS.clear()
        M.OI_M4_PROCESS.update(orig_proc)

    # ── P1：材料闭式的热光系数错 2× ⇒ 双通路互锁必红 ──────────────────────
    _good_slope = orig_fn["optical_thermal_slope_closed"]

    def _bad_slope(n_eff=None, dn_dt=None, alpha_si=None, wl_nm=None):
        return _good_slope(n_eff=n_eff,
                           dn_dt=(3.72e-4 if dn_dt is None else dn_dt),
                           alpha_si=alpha_si, wl_nm=wl_nm)

    M.optical_thermal_slope_closed = _bad_slope
    res["P1"] = _red(base_checks(), "独立通路")
    restore_fns()

    # ── P2：预偏移**忽略 ASIC 自热**（T_eq 退化为 T_amb）⇒ 残余非零 ➜ 必红 ─
    _good_stack = orig_m3["die_thermal_stack"]

    def _stack_no_selfheat():
        r = dict(_good_stack())
        r["t_photon_c"] = r["t_amb_c"]          # 🔴 忽略自热 ⇒ T_eq = T_amb
        return r

    M3.die_thermal_stack = _stack_no_selfheat
    _b2 = base_checks()
    res["P2"] = _red(_b2, "预偏移后残余") and _red(_b2, "预偏移后热调功耗")
    restore_m3()

    # ── P3：把「单向加热器不可行」粉饰成可行 ⇒ ①链判据必红 ────────────────
    def _stack_fake_bidi():
        r = dict(_good_stack())
        r["unidirectional_heater_feasible"] = True
        r["actuator_direction"] = "heat"
        return r

    _good_closed = orig_m3["closed_loop_thermal_steady"]

    def _closed_fake():
        r = dict(_good_closed())
        r["unidirectional_heater_feasible"] = True
        r["actuator_direction"] = "heat"
        r["p_heater_supplyable_mw_per_lane"] = 99.0
        return r

    M3.die_thermal_stack = _stack_fake_bidi
    M3.closed_loop_thermal_steady = _closed_fake
    res["P3"] = _red(base_checks(), "单向加热器在 CPO 里")
    restore_m3()

    # ── P4：热致偏移置 0 ⇒ 热态重规划**温度白算** ⇒ FSR 缩放判据必红 ────────
    _good_chain = orig_fn["co_design_chain"]

    def _chain_no_shift(p_asic_w=None):
        r = dict(_good_chain(p_asic_w=p_asic_w))
        r["d_lambda_self_nm"] = 0.0
        return r

    M.co_design_chain = _chain_no_shift
    res["P4"] = _red(base_checks(), "热态 FSR 与冷态")
    restore_fns()

    # ── P5：🔴 M4 波段改成 1550（跨波段混用）⇒ 波段互锁必红 ────────────────
    M.OI_M4_PROCESS["wl0_nm"] = 1550.0
    res["P5"] = _red(base_checks(), "M4 波段")
    M.OI_M4_PROCESS.clear()
    M.OI_M4_PROCESS.update(orig_proc)

    # ── P6：CTE 失配置 0 ⇒ 耦合损耗恒 0 ⇒ CTE 判据必红 ────────────────────
    M.OI_M4_PROCESS["cte_glass_fau_per_k"] = M.OI_M4_PROCESS["cte_si_per_k"]
    res["P6"] = _red(base_checks(), "CTE：失配漂移")
    M.OI_M4_PROCESS.clear()
    M.OI_M4_PROCESS.update(orig_proc)

    # ── P7：CMOS 摆幅限值放到 1000 V ⇒ 摆幅约束失效 ⇒ ⑥ 必红 ─────────────
    M.OI_M4_PROCESS["vpp_cmos_limit_v"] = 1000.0
    res["P7"] = _red(base_checks(), "CMOS 摆幅约束")
    M.OI_M4_PROCESS.clear()
    M.OI_M4_PROCESS.update(orig_proc)

    # ── P8：三形态 θ **全设相同** ⇒ 热耦合单调性判据必红 ──────────────────
    M._form_theta = lambda d_um: 1.0
    res["P8"] = _red(base_checks(), "热耦合随 die 距离")
    restore_fns()

    # ── P9：🔴 禁词扫描双向探针（肯定式必抓 / 否定式必豁免 / 嵌套必豁免）──
    pos = "M4 提供 TOPS 级算力与 fJ/bit 能效比，且不做 TOPS-W 换算"
    pos_caught = len(_banned_hits(pos)) > 0
    neg = "本项目**不报** TOPS / TOPS-W / fJ/bit / pJ/bit 能效比，不折算 fJ/op"
    neg_clean = len(_banned_hits(neg)) == 0
    nested = {"honest_note_m4": neg, "p_heat_mw_per_lane": 16.5}
    nested_clean = len(_banned_hits(nested)) == 0
    res["P9"] = bool(pos_caught and neg_clean and nested_clean)

    # ── P10：**均匀缩放** vpi_l ×2 ⇒ Pareto **结构**判据**不应**翻红 ───────
    def _struct_ok() -> bool:
        p = M.pareto_front_l_electrode()
        return bool(p["all_points_non_dominated"])

    before = _struct_ok()
    M.OI_M4_PROCESS["vpi_l_v_cm"] = orig_proc["vpi_l_v_cm"] * 2.0
    after_scale = _struct_ok()
    M.OI_M4_PROCESS.clear()
    M.OI_M4_PROCESS.update(orig_proc)
    res["P10"] = bool(before and after_scale)      # 两侧都不该红

    # ── P11：真禁词落进**模块真实输出**时必被抓（防只看合成字符串）────────
    M.OI_M4_PROCESS["_probe_note"] = "本模块达成 3.2T 与 fJ/bit 能效比"
    out = M.co_design_chain()
    out["injected"] = M.OI_M4_PROCESS["_probe_note"]
    res["P11"] = len(_banned_hits(out)) > 0
    M.OI_M4_PROCESS.clear()
    M.OI_M4_PROCESS.update(orig_proc)

    return res


def main() -> int:
    base = base_checks()
    section("M4 门禁 · 基线判据（46 项）")
    for k in sorted(base):
        check("  %s" % k, base[k])
    # 判据数自行锁住：门禁只管看得见的集合 ⇒ 新判据静默进盲区
    # v0.9.310：47（+1 = FAU 装配公差落窗 —— 该公差已从函数体字面量搬进参数表）
    check("R0 判据集合规模 == 47（新增判据必须同步本门禁与定稿索引）", len(base) == 47)

    section("M4 真实输出禁词扫描（肯定式宣称面）")
    M = _mod()
    real_out = {
        "co_design_chain": M.co_design_chain(),
        "setpoint_prebias_design": M.setpoint_prebias_design(),
        "thermal_channel_replan": M.thermal_channel_replan(),
        "package_form_factor_compare": M.package_form_factor_compare(),
        "fau_cte_misalignment": M.fau_cte_misalignment(),
        "pareto_front_l_electrode": M.pareto_front_l_electrode(),
        "feasibility_wall": M.feasibility_wall(),
        "band_lock": M.band_lock(),
    }
    check("R1 M4 全部函数真实输出**零禁词**（TOPS / TOPS-W / fJ·pJ 能量比等）",
          len(_banned_hits(real_out)) == 0)

    section("M4 突变探针（先证能变红）")
    probes = run_probes()
    for k in sorted(probes):
        check("  %s" % k, bool(probes[k]))

    section("S `G-OI7a` FAU 装配公差的**分布口径**（v0.9.310）")
    # 缺口原文：「FAU 公差无分布」。分布→损耗的传播是**纯建模活** ⇒ 本节把它做掉，
    # 并把「±tol 这句话本身不确定」这件事摊开成判据。
    from lda_l2 import oi_fau_yield as FY

    _p, _t, _ = FY.run_selfchecks(verbose=False)
    check("S1 `oi_fau_yield` 自检全过（%d 项：口径钉死 / 退化 / MC / 互洽 / 反演 / 单调 / 反向）"
          % _t, _p == _t, "PASS=%d/%d" % (_p, _t))

    _W = float(M.OI_M4_PROCESS["mfd_w_um"])

    # S2 门禁**自己跑** MC ⇄ 闭式（不转调模块自检）：E[η] 与良率各 2 组，4σ
    _z = []
    for _sig, _l0 in ((0.1667, 0.05), (0.3, 0.10)):
        _mc = FY.mc_statistics(_W, _sig, _l0, trials=2500, seed=int(100 * _sig * 100 + _l0 * 1000))
        _ce = FY.expected_eta_closed(_W, _sig)
        _z.append((_mc["mean_eta"] - _ce) / (0.5 / math.sqrt(_mc["trials"])))
        _cy = FY.yield_closed(_l0, _W, _sig)
        _z.append((_mc["yield"] - _cy) / math.sqrt(max(_cy * (1 - _cy), 1e-12) / _mc["trials"]))
    check("S2 MC ⇄ 闭式（E[η] 与良率各 2 组）：4 组全部 |z| ≤ 4（max=%.2f）"
          % max(abs(x) for x in _z), all(abs(x) <= 4.0 for x in _z),
          "z=%s" % [round(x, 2) for x in _z])

    # S3 🔴 口径钉死：**功率 = 振幅重叠的模方**，w 取 1/e² 强度半径 ⇒ η = exp(−(d/w)²)
    _ov = FY.mode_overlap_2d(0.8, _W)
    _d1 = abs(_ov["eta_numeric"] - _ov["eta_exp_1_over_w2"])
    _d2 = abs(_ov["eta_numeric"] - _ov["eta_exp_1_over_2w2"])
    check("S3 口径钉死：2D 数值重叠 ⇄ exp(−(d/w)²) 差 %.1e ∧ ⇄ exp(−d²/2w²) 差 %.1e"
          " ⇒ 指数系数由计算定，不靠注释" % (_d1, _d2),
          _d1 < 1e-6 and _d2 > 1e-3)

    # S4 🔴 诚实面：同一句「±tol」跨约定差多少 —— 不选一个，全给出来
    _tol = float(M.OI_M4_PROCESS["fau_assembly_tol_um"])
    _tab = FY.convention_table(_W, _tol)
    _losses = [r["loss_db"] for r in _tab]
    _spread = max(_losses) / min(_losses)
    check("S4 「±%.2f µm」在 %d 种约定下跨 %.2f 倍（%.4f … %.4f dB）⇒ 这句话单独不成立"
          % (_tol, len(_tab), _spread, min(_losses), max(_losses)), _spread >= 5.0,
          "表=%s" % [(r["convention"], round(r["loss_db"], 4)) for r in _tab])

    # S5 🔴 本版标题：把带边缘当位移 ⇒ 角点是 ±3σ 期望的 ≥4 倍
    _cv = FY.corner_vs_expected(_W, _tol, "gauss_3sigma")
    check("S5 角点 %.4f dB 是 ±3σ 期望 %.4f dB 的 %.2f 倍（≥4）⇒ 原文那个数是被放大的"
          % (_cv["corner_loss_db"], _cv["expected_loss_db"], _cv["ratio"]),
          _cv["ratio"] >= 4.0)

    # S6 🔴 单一真源：公差在参数表里 ∧ 有窗口 ∧ 函数输出与之逐位相等
    _in_tab = "fau_assembly_tol_um" in M.OI_M4_PROCESS
    _banded = "fau_assembly_tol_um" in M._BANDS
    _same_src = (_in_tab and float(M.fau_cte_misalignment()["assembly_tol_um"])
                 == float(M.OI_M4_PROCESS["fau_assembly_tol_um"]))
    check("S6 公差单一真源：进 `OI_M4_PROCESS` ∧ 有窗口 ∧ `fau_cte_misalignment()` 输出逐位相等",
          bool(_in_tab and _banded and _same_src),
          "入表=%s 有窗口=%s 同源=%s" % (_in_tab, _banded, _same_src))

    # S7 反演：良率目标 → σ 上限，回代须**恰**命中（1e-12）
    _ok7 = all(abs(FY.yield_closed(0.05, _W, FY.sigma_max_for_yield(0.05, _W, y)) - y) < 1e-12
               for y in (0.9, 0.99))
    check("S7 反演（良率目标 → σ 上限）回代 90% / 99% 恰命中（1e-12）", _ok7)

    # S8 🔴 措辞判据：CTE 仍非主因（方向不变），但「远小于」在 3σ 口径下不成立
    _ca = FY.cte_vs_assembly(convention="gauss_3sigma")
    check("S8 CTE ⇄ 装配：角点口径 1/%.1f（可称「远小于」）↔ 3σ 期望 1/%.2f ⇒ 方向不变、措辞须改"
          % (_ca["ratio_corner"], _ca["ratio_expected"]),
          _ca["cte_is_dominant"] is False and 3.0 < _ca["ratio_expected"] < 6.0,
          "CTE=%.5f dB 装配期望=%.5f dB" % (_ca["il_cte_db"], _ca["il_assembly_expected_db"]))

    section("M4 探针还原后基线复检")
    after = base_checks()
    same = after == base
    check("R2 探针还原后判据集合与原基线逐项一致（探针不污染真判据）", same)
    check('R3 探针还原后基线仍**全部 PASS**（不是「全变绿/全变红」的假还原）',
          bool(after) and all(after.values()))
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
