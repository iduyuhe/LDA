# -*- coding: utf-8 -*-
"""M2b（G-OI5）门禁：多通道均衡 · 热调 · 热串扰 Γ · 工艺偏差良率 · 封装容差。

🔴 本门禁的判据纪律（本项目反复血的）：
  · **golden = 闭式物理律**（CTLE 解析积分 / 对数热场 / 热网络有限差分 / 闭式 erf /
    高斯重叠解析 / 形态映射约束）。**MC 采样只是第二通道，不是 golden**。
  · 判据必须**咬语义不咬字面**；「同源相等」单独用是**假判据** ⇒ 每条 golden 都配
    **第二独立通道**（数值积分 / 数值扫描 / 网络解 / 回代）或**退化/边界**判据。
  · 存在性断言天然脆弱 ⇒ 凡「扫 X 里有没有 Y」都要问「Y 会不会被 Z 冒充」。
  · 探针**先证「能变红」再信判据**；探针落点必须打在**被门禁真正消费的那份引用**上。
  · 还原后基线门禁**必须重新全绿**（探针不得污染真判据）。

判据索引：
  T1  规格锚窗口（奈奎斯特/λ₀/信道间隔/环区数 落窗）
  T2  🔴 环区数互锁：`oi_m2b.RING_M_2B` ≡ `oi_m2.OI_M2_PROCESS["ring_m"]` 且 ≠ M1 的 129
  T3  形态映射：lpo 只有 CTLE 无 FFE（无 DSP ⇒ 不能数字均衡）· retimed 可 CTLE+FFE
  T4  形态反向完备：三键（ctle/ffe/needs_dsp）全在白名单且被消费
  T5  CTLE：boost 反解 ⟷ 回代幅度互锁
  T6  CTLE：噪声 penalty **解析积分** ⟷ **trapz 数值积分**（第二独立通道）
  T7  CTLE 退化：f_z = f_p（flat）⇒ penalty ≡ 0（判据能落到 0，不是恒绿）
  T8  CTLE 非平凡：penalty ∈ (0, 上限) —— **防「积分上限被改成 0 ⇒ 恒绿」陷阱**
  T9  多通道：各 lane 目标 boost 真不同（不是「单通道均衡 ×N」摆设）
  T10 多通道：**均衡成效**（🔴 独立重算：逐 lane **真信道** ISI 抽头能量拉平；
      首版用 `total_gain ≡ b_nom+loss_ref` 的**往返恒等式** ⇒ 假判据，v0.9.185 修 F3）
  T11 多通道：逐 lane ISI residual 有界 · **per-lane 真信道 ≠ 标量口径**（F4 回归锁）
  T12 热调：P_tune ∝ 剩余失谐（闭式线性）
  T13 热调：只出 mW 功耗，输出面无能效词（honest_boundary）
  T14 Γ 对称（热传导互易 · 非对称布局下仍须成立）
  T15 Γ 对角最大（自身加热最强）
  T16 Γ 随版图距离单调递减
  T17 Γ 随**版图坐标真变化**（版图绑定：坐标动 ⇒ Γ 动，绝不写死）
  T18 Γ：热网络有限差分解 ⟷ 对数解析解**随网格加密收敛**（真收敛判据）
  T19 良率：闭式 erf ⟷ MC 第二通道
  T20 良率：yield 随 σ 单调**递减**（退化探针 P5a 的靶子）
  T21 良率：σ=0 ⇒ yield=1（退化）· tol=0 ⇒ yield=0（边界）—— 同类 ≥2
  T22 良率：MC 同 seed ⇒ 逐位可复现
  T23 封装：闭式反解 dx_max ⟷ 数值扫描（第二独立通道）
  T24 封装：dx_max 回代「对准 IL」== 预算（闭式 ⟷ 回代互锁）
  T25 封装：模场失配底 < 对准预算（预算先扣固有底，容差才可达）
  T26 封装温漂：Δx = gap·Δλ/(Λcosθ) 落在对准容差内
  T27 诚实边界：披露面 / 输出面无禁出词（TOPS-W / fJ / pJ-bit / 能效比）
  T28 热调：FSR 走单一真源 `fsr_nm`（🔴 F7：`spacing_nm` 回退常量 4.5 nm 分支已删，
      真值 4.891789 ⇒ 判据证明「用的不是回退常量」）

探针（**先证能变红**）：
  P1  CTLE 退化：f_z=f_p（关掉频率提升）⇒ T8「非平凡」必红
  P2  积分上限改成 0（空区间 ⇒ penalty 恒 0）⇒ T8 必红（T6 会假绿，靠 T8 兜）
  P3  🔴 让 `equalizer_for_form("lpo")` 也返回 ffe=True（**LPO 拿数字 DSP，自相矛盾**）
      ⇒ T3 必红
  P4  Γ 的距离改成常量（丢物理）⇒ T16 单调必红
  P5  良率：把 `yield_closed_form` 改成与 σ 无关（恒返 1）⇒ T20 必红
  P6  MC 换成随机 seed（不可复现）⇒ T22 必红
  P7  GC：把 `gc_coupling_efficiency` 的 dx 指数 2→1（物理解错）⇒ T24 回代必红
  P8  热调：输出面塞入 `fJ/bit`（触碰红线）⇒ T13 必红
  P11 🔴 把第 0 lane 的 CTLE 零点打偏 1.5× ⇒ T10（**独立重算**的均衡成效）必红
      （证明 T10 不再是对 `f_z_for_boost` 反解自动成立的恒等式）
  P12 🔴 让 `lda_agent.wdm_system.fsr_nm` 恒返回回退常量 `spacing_nm` ⇒ T28 必红
      （真灌故障：patch 真被调用的上游函数，不是直接改判据返回值）
  R  探针还原后基线门禁**必须重新全绿**（探针不污染真判据）
"""
from __future__ import annotations

import importlib
import math
import sys
import os

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

_M2B = "lda_l2.oi_m2b"
_M2 = "lda_l2.oi_m2"


def _mod(name: str = _M2B):
    return importlib.import_module(name)


# ═════════════════════════════════════════════════════════════════════════════
# 判据组
# ═════════════════════════════════════════════════════════════════════════════
def baseline_checks(light: bool = False) -> dict:
    """跑全量判据，返回 {判据号: bool}。探针通过 patch `oi_m2b` 模块属性生效。"""
    M = _mod()
    O2 = _mod(_M2)
    out: dict = {}

    # ── T1 规格锚窗口 ────────────────────────────────────────────────────────
    p = M.OI_M2B_PROCESS
    out["T1a"] = bool(M._in_band("nyquist_ghz", M.NYQUIST_200G_GHZ))
    out["T1b"] = bool(M._in_band("wl0_nm", p["wl0_nm"]))
    out["T1c"] = bool(M._in_band("spacing_nm", p["spacing_nm"]))
    out["T1d"] = bool(M._in_band("ring_m", p["ring_m"]))

    # ── T2 🔴 环区数互锁（M2 血案 #3：跨档抄常量 ⇒ 版图与预算不同参）──────────
    out["T2a"] = int(p["ring_m"]) == int(O2.OI_M2_PROCESS["ring_m"])
    out["T2b"] = int(p["ring_m"]) != 129
    out["T2c"] = int(p["ring_m"]) == int(M.RING_M_2B)

    # ── T3/T4 形态映射（本轮题眼：LPO 无 DSP ⇒ 只能模拟 CTLE）─────────────────
    lpo, ret = M.equalizer_for_form("lpo"), M.equalizer_for_form("retimed")
    out["T3a"] = bool(lpo["ctle"]) and not bool(lpo["ffe"]) and not bool(lpo["needs_dsp"])
    out["T3b"] = bool(ret["ctle"]) and bool(ret["ffe"]) and bool(ret["needs_dsp"])
    out["T4a"] = all(k in M.EQ_PROFILES["lpo"] for k in M._EQ_WHITELIST)
    out["T4b"] = all(lpo[k] == M.EQ_PROFILES["lpo"][k] for k in M._EQ_WHITELIST)

    # ── T5–T8 CTLE ───────────────────────────────────────────────────────────
    F = M.NYQUIST_200G_GHZ * 1e9
    a = float(p["f_tia_ghz"]) * 1e9
    Z = M.f_z_for_boost(F, a, float(p["ctle_boost_db"]))
    got = 10.0 * (0.0 if Z <= 0 else __import__("math").log10(
        (1.0 + (F / Z) ** 2) / (1.0 + (F / a) ** 2)))
    out["T5"] = abs(got - float(p["ctle_boost_db"])) < 1e-6
    pen = M.ctle_noise_penalty_db(Z, a, F)
    _nb = float(M._nbw_numeric(Z, a, F))        # 探针 P2 会把它打成 0 ⇒ 不得让门禁崩
    pen_num = 10.0 * math.log10(_nb / F) if _nb > 0.0 else float("-inf")
    out["T6"] = abs(pen - pen_num) < 1e-3
    out["T7"] = abs(M.ctle_noise_penalty_db(a, a, F)) < 1e-9
    out["T8"] = (pen > 1e-6) and (pen < 20.0)

    if light:
        return out

    # ── T9–T11 多通道均衡 ────────────────────────────────────────────────────
    des = M.lane_ctle_design()
    out["T9"] = bool(des["boost_distinct"])
    _fm = float(p["f_mod_nom_ghz"]) * 1e9
    _pd = float(O2.OI_M2_PROCESS["f_pd_ghz"]) * 1e9
    _bd = M.PAM4_BAUD_200G_GBD * 1e9
    # 🔴 F4：逐 lane **真信道**（f_mod_hz=None ⇒ 取 lane["f_mod_ghz"]）
    iso = M.lane_isi_residual(des["lanes"], None, _pd, a, 0.0, 0.0, _bd)
    # 🔴 F3：均衡**成效** = **独立重算**（逐 lane 真信道的 ISI 抽头能量 spread），
    #    不再用 `total_gain ≡ b_nom+loss_ref` 的往返恒等式（首版 T10 是假判据）
    out["T10"] = bool(M.lane_equalization_flatness()["equalization_flat_ok"])
    out["T11a"] = all(0.0 <= x["isi_residual"] <= 2.0 for x in iso["per_lane"])
    # 🔴 T11b：口径证据 —— 标量口径（8 lane 共用标称信道）与逐 lane 真信道的 spread
    #    **必须不同**（否则「逐 lane」是摆设）；这是 F4 的回归锁
    iso_sc = M.lane_isi_residual(des["lanes"], _fm, _pd, a, 0.0, 0.0, _bd)
    out["T11b"] = bool(abs(iso["isi_spread"] - iso_sc["isi_spread"]) > 1e-6
                       and iso_sc["channel_source"] == "scalar(f_mod_hz)")

    # ── T12–T13 热调（只登记功耗，不动能效）───────────────────────────────────
    tb = M.thermal_tune_budget()
    d0 = tb["residual_detune_nm"]
    p2 = M.thermal_tune_budget(residual_detune_nm=2.0 * d0)["p_tune_mw_per_lane"]
    out["T12"] = abs(p2 - 2.0 * tb["p_tune_mw_per_lane"]) < 1e-12
    out["T13"] = bool(M.honest_boundary_ok()) and isinstance(tb, dict) \
        and "fJ" not in str(tb) and "pJ/bit" not in str(tb) and "TOPS-W" not in str(tb)

    # ── T14–T18 热串扰 Γ（版图绑定）──────────────────────────────────────────
    g = M.crosstalk_gamma()
    out["T14"] = bool(g["symmetric_ok"])
    out["T15"] = bool(g["diagonal_max_ok"])
    out["T16"] = bool(g["monotonic_ok"])

    # T17 版图绑定：版图**真变**（必须非刚体 ⇒ 距离矩阵真变）⇒ Γ 真动（绝不写死）
    #   🔴 首版探针用「整体平移 (x+25, y−15)」= 刚体平移 —— 不改变任何两点距离，
    #      Γ 只依赖距离 ⇒ Γ 逐位相同 ⇒ 判据**永远绿**（假绿，门禁抓出）。
    #      缩放下标（x×1.7）才真改距离矩阵。
    pos0 = M.ring_positions_from_layout()
    scaled_pos = [(x * 1.7, y) for (x, y) in pos0]
    g_scaled = M.crosstalk_gamma(scaled_pos)
    out["T17"] = (g_scaled["gamma_nm_per_mw"] != g["gamma_nm_per_mw"]) \
        and (int(g_scaled["n"]) == int(g["n"]))
    # T17b 平移不变性（真物理律，与 T17 并用 ⇒ 不会「随便动一动就绿」）：
    #   刚体平移不改变热耦合（Γ 只依赖距离），Γ 必须逐位相同。
    moved = [(x + 25.0, y - 15.0) for (x, y) in pos0]
    g_moved = M.crosstalk_gamma(moved)
    out["T17b"] = bool(g_moved["gamma_nm_per_mw"] == g["gamma_nm_per_mw"])
    # T18 有限差分热网络 ⟷ 对数解析解：网格加密 ⇒ 相对误差单调下降（真收敛判据）
    #   🔴 off-diag only：对角是对数场 d→0 处的**钳位值**（self-heating 不在本模型
    #      描述范围），拿它当归一化分母 ⇒ 误差恒 0.503、grid 加密完全不降（假收敛）。
    #   🔴 两者必须描述**同一物理问题**：解析对数场的 d_ref 取网络域半径（见 `_theta_rel_err`）。
    try:
        n0 = int(pos0.__len__())
        e1 = _theta_rel_err(M, n0, 12)
        e2 = _theta_rel_err(M, n0, 24)
        e3 = _theta_rel_err(M, n0, 48)
        out["T18a"] = bool(e2 <= e1 + 1e-9 and e3 <= e2 + 1e-9)
        out["T18b"] = bool(e3 < 0.35)
    except Exception:
        out["T18a"], out["T18b"] = False, False

    # ── T19–T22 良率（MC 不是 golden）────────────────────────────────────────
    yc, ym = M.yield_closed_form(), M.yield_monte_carlo()
    out["T19"] = abs(yc["yield"] - ym["yield"]) < 1e-2
    s_lo = M.yield_closed_form(sigma_dn_eff=p["sigma_dn_eff"] * 0.5)["yield"]
    s_hi = M.yield_closed_form(sigma_dn_eff=p["sigma_dn_eff"] * 2.0)["yield"]
    out["T20"] = s_lo >= yc["yield"] >= s_hi          # σ↑ ⇒ yield↓（单调）
    out["T21a"] = abs(M.yield_closed_form(sigma_dn_eff=0.0)["yield"] - 1.0) < 1e-12
    out["T21b"] = abs(M.yield_closed_form(tol_nm=0.0)["yield"]) < 1e-12
    ym2 = M.yield_monte_carlo()
    # 🔴 seed 必须进断言：否则「换随机 seed」的探针不改任何已比字段 ⇒ 假绿（P6 踩过）
    out["T22"] = bool(ym2["yield"] == ym["yield"] and ym2["n_samples"] == ym["n_samples"]
                      and ym2.get("seed") == ym.get("seed"))

    # ── T23–T26 封装容差 ─────────────────────────────────────────────────────
    ab = M.alignment_tolerance_budget()
    out["T23"] = abs(ab["dx_max_um"] - ab["dx_max_numeric_um"]) < 0.05
    out["T24"] = abs(ab["dx_back_substitute_align_il_db"] - ab["il_budget_db"]) < 1e-6
    out["T25"] = ab["il_mode_mismatch_db"] < ab["il_budget_db"]
    tdb = M.temp_drift_budget()
    out["T26"] = bool(tdb["in_tolerance"])

    # ── T27 诚实边界 ─────────────────────────────────────────────────────────
    txt = " ".join(v for k, v in M.OI_M2B_DISCLOSURE.items() if k != "no_energy")
    out["T27"] = not any(b in txt for b in ("fJ/", "pJ/bit", "TOPS-W", "能效比"))

    # ── T28 FSR 单一真源（🔴 F7：回退常量 4.5 nm 分支已删）────────────────────
    out["T28"] = bool(M.no_fsr_fallback_ok())

    return out


def _theta_rel_err(M, n: int, grid: int, extent_um: float = 520.0) -> float:
    """热网络有限差分解 vs 对数解析解的相对误差（**off-diag**，网格越密越小）。

    🔴 三条纪律（首版都踩了）：
      1. 只取 off-diag：对角是钳位伪值，会污染归一化；
      2. 解析对数场必须取 `d_ref = extent/2`（网络域半径）—— 否则两者描述的是
         **不同的边界问题**，误差永远降不下来（首版恒 0.503）；
      3. 网络热导必须**一步长无关**（`k = 1/(2π·r_th0)`，见 `oi_m2b` 文档串），
         否则解的是随网格改变的连续问题 —— 那不叫「离散化误差」，叫「错题」。
    """
    import math as _m
    pos = M.ring_positions_from_layout(n)
    theta_net = M.thermal_network_coupling(pos, grid=grid, extent_um=extent_um)
    d_ref = extent_um / 2.0
    # 🔴 两边统一在 **Θ（K/mW）** 量纲上比：首版把 ana 乘了 S（nm/mW）而 theta_net 没乘
    #    ⇒ 差一个 S 倍，相对误差恒 ~1（假红）。调谐斜率 S 是后面才乘到 Γ 上的公共因子，
    #    不属于「热场方法差异」的一部分，必须约掉。
    ana = []
    for i in range(n):
        row = []
        for j in range(n):
            row.append(M.thermal_coupling_log(
                _m.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1]),
                d_ref_um=d_ref))
        ana.append(row)
    ana = M.np.array(ana)
    mask = ~M.np.eye(n, dtype=bool)
    den = M.np.max(M.np.abs(ana[mask])) or 1.0
    return float(M.np.max(M.np.abs(theta_net[mask] - ana[mask])) / den)


# ═════════════════════════════════════════════════════════════════════════════
# 探针（先证能变红）
# ═════════════════════════════════════════════════════════════════════════════
def run_probes() -> dict:
    res: dict = {}
    M = _mod()
    # 🔴 必须把**所有被探针改过的名字**都快照：缺一个 ⇒ 探针还原后真判据继续红，
    #    表现为「R1 探针污染真判据」红（首版漏了 _nbw_numeric / thermal_coupling_log /
    #    yield_monte_carlo 三个 ⇒ T6/T16/T22 被 P2/P4/P6 永久污染）。
    orig = {k: getattr(M, k) for k in
            ("f_z_for_boost", "equalizer_for_form", "yield_closed_form",
             "yield_monte_carlo", "thermal_tune_budget", "ctle_noise_penalty_db",
             "_nbw_numeric", "thermal_coupling_log", "lane_ctle_design")}

    # P1：关掉 CTLE 频率提升（f_z = f_p）
    M.f_z_for_boost = lambda F, a, b: float(a)
    M.ctle_noise_penalty_db = lambda z, a, F: 0.0
    res["P1"] = _red(baseline_checks(light=True), "T8")
    _restore(M, orig)

    # P2：数值积分通道被掐断（返回 0）⇒ 解析 ⟷ 数值 对拍（T6）必红
    #   🔴 首版写成「⇒ T8 必红」是**打错靶**：T8 只看解析 penalty 本身（P2 不碰解析），
    #      根本打不红；真正会红的是 T6（解析⟷数值一致性）。改打 T6，且门禁不得崩。
    M._nbw_numeric = lambda z, a, F, n=200001: 0.0
    res["P2"] = _red(baseline_checks(light=True), "T6")
    _restore(M, orig)

    # P3：🔴 让 lpo 也拿到 FFE（无 DSP 却用数字均衡 = 自相矛盾）
    _bak = dict(M.EQ_PROFILES)
    M.EQ_PROFILES = {k: dict(v, ffe=True, needs_dsp=True)
                     for k, v in orig_forms().items()}
    res["P3"] = _red(baseline_checks(light=True), "T3a")
    M.EQ_PROFILES = _bak
    _restore(M, orig)

    # P4：Γ 的距离改成常量（丢物理 ⇒ 单调性崩）
    M.thermal_coupling_log = lambda d, d_ref_um=M._D_REF_UM, r_th0=M._R_TH0_K_PER_MW: 1.0
    res["P4"] = _red(baseline_checks(), "T16")
    _restore(M, orig)

    # P5：良率与 σ / tol 解耦（恒返 1）
    #   🔴 靶子选 T21b（tol=0 ⇒ yield=0 的**边界**判据）：T20（单调性）在恒 1.0 下
    #      仍然 `1.0 >= 1.0 >= 1.0` 成立，**打不红**（首版打错靶 ⇒ P5 假绿）。
    M.yield_closed_form = lambda sigma_dn_eff=None, tol_nm=None: {"yield": 1.0}
    res["P5"] = _red(baseline_checks(), "T21b")
    _restore(M, orig)

    # P6：MC 换随机 seed（不可复现）⇒ T22 必红
    #   🔴 首版把整个 `yield_monte_carlo` 换成恒返函数 ⇒ 判据里**前后两次调用都走坏函数**
    #      （两边 seed 一起变 ⇒ 仍然相等）⇒ 探针打不动自己的靶（假绿）。
    #      真探针只让**第二次**调用换 seed（第一次仍可复现），这才等价于「同流程两次跑
    #      出不同结果 = 不可复现」。
    _st = {"i": 0}

    def _bad_mc(n_samples=20000, seed=None, **kw):
        _st["i"] += 1
        _sd = 20261002 if _st["i"] == 1 else 999
        return dict(orig["yield_monte_carlo"](n_samples=n_samples, seed=_sd))

    M.yield_monte_carlo = _bad_mc
    res["P6"] = _red(baseline_checks(), "T22")
    _restore(M, orig)

    # P7：GC 的 dx 指数 2→1（物理解错 ⇒ 回代不符）
    _fe = M.gc_coupling_efficiency
    M.gc_coupling_efficiency = _with_bad_pow(M, _fe)
    res["P7"] = _red(baseline_checks(), "T24")
    M.gc_coupling_efficiency = _fe
    _restore(M, orig)

    # P8：热调输出面塞入禁出词
    M.thermal_tune_budget = lambda *a, **k: dict(
        orig["thermal_tune_budget"](*a, **k), note="fJ/bit 能效 3.2")
    res["P8"] = _red(baseline_checks(), "T13")
    _restore(M, orig)

    # P11：🔴 把第 0 lane 的 CTLE 零点打偏 1.5× ⇒ **均衡成效**（T10，**独立重算**）必红
    #      （证明 T10 不再是对 `f_z_for_boost` 反解自动成立的往返恒等式）
    def _detuned(n_lanes=None, boost_db=None, f_nyq_ghz=None):
        d = dict(orig["lane_ctle_design"](n_lanes, boost_db, f_nyq_ghz))
        ln = [dict(x) for x in d["lanes"]]
        ln[0]["f_z_hz"] = float(ln[0]["f_z_hz"]) * 1.5
        d["lanes"] = ln
        return d

    M.lane_ctle_design = _detuned
    res["P11"] = _red(baseline_checks(), "T10")
    _restore(M, orig)

    # P12：🔴 让上游 `fsr_nm` 恒返回回退常量（模拟回退分支复活）⇒ T28 必红
    #      （真灌故障：patch **被真调用**的 `lda_agent.wdm_system.fsr_nm`）
    import lda_agent.wdm_system as _ws
    _bak_fsr = _ws.fsr_nm
    _ws.fsr_nm = lambda *a, **k: float(M.OI_M2B_PROCESS["spacing_nm"])
    try:
        res["P12"] = _red(baseline_checks(), "T28")
    finally:
        _ws.fsr_nm = _bak_fsr
    _restore(M, orig)

    return res


def orig_forms() -> dict:
    import copy
    M = _mod()
    return copy.deepcopy(M.EQ_PROFILES)


def _with_bad_pow(M, fn):
    def _bad(dx_um=0.0, theta_rad=0.0, dz_um=0.0, **kw):
        r = fn(dx_um=dx_um, theta_rad=theta_rad, dz_um=dz_um, **kw)
        p = M.OI_M2B_PROCESS
        sm = float(p["w_fiber_um"]) ** 2 + float(p["w_waveguide_um"]) ** 2
        r["eta_dx"] = math_exp(-float(dx_um) ** 2 / sm)   # 错：丢了 2·
        r["eta"] = r["eta_dx"] * r["eta_theta"] * r["eta_mode"] * r["eta_dz"]
        r["il_db"] = -10.0 * (math_log10(r["eta"]) if r["eta"] > 0 else float("inf"))
        return r
    return _bad


from math import exp as math_exp, log10 as math_log10  # noqa: E402


def _restore(M, orig: dict) -> None:
    for k, v in orig.items():
        try:
            setattr(M, k, v)
        except Exception:
            pass


def _red(chk: dict, tag: str) -> bool:
    """探针断言：指定判据**必须为 False**（先证能变红）。"""
    return bool(chk.get(tag, None) is False)


def main() -> int:
    base = baseline_checks()
    section("M2b（G-OI5）门禁 · 基线判据")
    for k in sorted(base):
        check("  %s" % k, bool(base[k]))
    section("M2b 突变探针（先证能变红）")
    probes = run_probes()
    for k in sorted(probes):
        check("  %s" % k, bool(probes[k]))
    section("M2b 探针还原后基线复检")
    after = baseline_checks()
    for k in sorted(after):
        check("  %s" % k, bool(after[k]))
    same = after == base
    check("R1 探针还原后判据集合与原基线逐项一致（探针不污染真判据）", same)
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
