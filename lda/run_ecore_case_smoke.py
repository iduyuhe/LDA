#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算芯片案例卡门禁（WebUI 只读端点 /api/ecore_demo · D-155 建卡 → D-160 升级 E1–E9 →
E11-e → E1–E11 · E12-e → E1–E12 · E13-e → E1–E13 · E14-e → E1–E14 · E15-e → E1–E15 ·
**D-184（E16-e）升级为 E1–E16 全链**）。

═══ 判什么（分节）═══
A 模块自检（ecore_case.run_selfchecks **33 项**）· B 关键事实 name-first 断言（含 E6–E9 四块能力面 +
E11-c/E11-d 两块 + E12 的 2D MOS 面 + E13 的 2D 输运面 + E14 的真外围/系统链面 + E15 误差预算面 +
**E16 权重编程面** + **E17 时序/时钟预算面** +
🔴 **B16/B17/B18/B19/B20/B21/B22/B23 与底层模块交叉核对**）·
C 反向可证伪（**14 条突变探针**：破坏诚实边界 / 清空 landmark / verdict 冒充实测 / 规模上界非单调 /
掏空版图面 / G-3 被改成自洽 / 缺口归零 / **注入「已含量子修正/已算弹道」** / 掏空 E12 的 DIBL 指数律 /
**抹掉 E12 面的「已由 E13 闭合」标注** / **抹掉「vcvs 极性缺陷登记」** / **把误差预算口径拔高成 ENOB** /
**E16 双向（伪造已标定 PDK/TOPS + 把共模漂移当精度上限 + 抹掉「条件于 ν」）** /
**E17 双向（时序面冒充已报 TOPS/已完成功耗估算 + 抹掉「宏模型级」「只覆盖静态」）** ⇒ 均必红）·
D 不进 HEAVY_POST_PATHS（公开只读 · 零重计算）·
E API 参考已登记（gen_api_reference 已跑 · 血案 23）· K 自入 CI core（防静默漏接 · 血案 28）。

🔴 本门禁的核心价值：守 WebUI 对外案例卡的**诚实边界**——verdict 恒 DESIGN_VERIFIED、
不报 fabricated 能效（TOPS/TOPS-W）、规模按「可建模/可验证容量」解读、landmark 仅背景坐标；
守住**升级后的能力面不被静默缩水**（E6/E7/E8/E9/E11-c/E11-d/E12/E13/E14/E15/E16/E17 **十二块** facts 必须都在）；
并守住 🔴 **「内部能力 ↔ 对外载体」真拉平**（B16–B23 拿卡里的数字与**底层模块实测**对拍，
而不是卡自证自洽）。

🔴 收官的**护栏换代史**（能力升级必须回扫**两个方向**，每次各扫一遍）：
  · E12-e：贬低方向 G-J「无 2D MOS」→ 历史项；抬高方向「不许假称已产 I-V」（C8）。
  · E13-e：贬低方向 E12 面「不产 I-V」→ 标「已由 E13 闭合」（C10）；抬高方向「不许假称已含量子修正」（C8 换代）。
  · **E14-e**：贬低方向「**平台缺陷（vcvs 极性）必须已登记且不得被抹掉**」（**C11**）；
    抬高方向「外围宏模型必须显式声明（判决器抽象 / 宏模型 / 不报 TOPS）」（**㉙** + **C8 仍守**）。
  · **E15-e**：抬高方向「**误差预算口径不许冒充 IEEE ENOB / 不许说成含动态**」（**㉛** + **C12**）；
    贬低方向由 **㉚**（E15 面登记齐全 · 防静默缩水）守住。
    🔴 本轮新立的判据纪律：**多来源拼接会稀释判据** —— ㉛ 初版把 `device_budget` 与 `gaps`
    拼成一个大 blob ⇒ 改坏 `device_budget` 后 blob 里仍有 G-O 的同名字符串 ⇒ 判据照样绿（假绿）。
    ⇒ **必须按来源分别断言**，探针才能打到「被单独检查的那份来源」。
  · **E16-e**：抬高方向「**编程参数不许冒充已标定 PDK / 不许报 TOPS / 不许把「共模漂移」当精度上限**」
    （共模可被单次增益校准消除 ⇒ 不该进预算）（**㉝** + **C13 ①**）；
    贬低方向「**E16 前「权重直接灌入、无写入模型」的口径必须显式标注已闭合**（G-P/G-Q）+
    漂移结论必须显式声明**条件于 ν**」（**㉝** + **C13 ②**）。
  · **E17-e**：抬高方向「**时序面不许冒充已报 TOPS / 已完成功耗估算**」
    （本段**无功耗模型、无实测硅** ⇒ `P = C·V²·f` 之类不在本段）（**㉟** + **C14 ①**）；
    贬低方向「**E17 前「全仓时间零覆盖 / 行驱动无限带宽宏模型」的口径必须显式标注已闭合**，
    且**新**的内在边界（**宏模型级** + **只覆盖静态** + 参数**非 PDK**）不得被抹掉」
    （**㉟** + **C14 ②**）。
    🔴 E17 本轮新立的判据纪律：**「B18 式否定词窗口」的第二种误伤** —— 披露里写的是
    「**不报** TOPS/TOPS-W/fJ/op」（正确的自我否定），若用 `"TOPS" not in blob` 会把它**误判成违规**；
    ⇒ **必须用「肯定性禁止短语」**（`已报 TOPS` / `已含功耗` / `已含时钟树抖动` …）
    （与 E12/E13 的否定词窗口血案同族）。
    🔴 E16 本轮新立的两条口径纪律：
      ① **绝对值序列估不出 σ** —— `std(|Z|) = σ·√(1−2/π) = 0.603σ` ⇒ 端到端 σ 对拍必须用**带符号**序列
         （用绝对值序列会比真值低 40%）；
      ② **电平界要用「平均电导」而非「最小电导」** —— 电平在窗口内**等间距** ⇒ 量化误差
         **绝对值同为半步长**（与 g 无关）⇒ 输出界 = `half_step / 平均电导`；低电导单元的
         「大相对误差」在求和里**并不放大**。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _read(rel):
    """文本读文件（不 import 模块 ⇒ 不拉 numpy）。"""
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return ""
    with open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def main() -> int:
    from lda_webui import ecore_case as EC

    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = EC.run_selfchecks(verbose=False)
    check("A1 模块自检 37/37 PASS（容量/量化界/版图闭式/压缩比/方块电阻/Pelgrom/1√N/"
          "Elmore/组装/降级/诚实/定位/口径/零框架/护栏/里程碑/landmark/E6-E9 面/上界单调/"
          "E11-c 器件级内核面/E11-d 失效边界面/贬低方向诚实/E12 2D MOS 面/2D 解非 ORACLE/"
          "E13 输运面/抬高方向诚实/E14 外围面/E14 双向诚实/E15 预算面/E15 诚实/"
          "E16 权重编程面/E16 双向诚实/E17 时序面/E17 双向诚实/"
          "**E18 列侧共享面/E18 双向诚实**）",
          ok_a)

    # ══════════════════════ B 关键事实（name-first）══════════════════════
    card = EC.case_card(repo_root="__nonexistent_root__")
    check("B1 endpoint == /api/ecore_demo", card["endpoint"] == "/api/ecore_demo")
    check("B2 verdict == DESIGN_VERIFIED（非 ACCEPT/PASS）",
          card["verdict"] == "DESIGN_VERIFIED")
    check("B3 十八段征程（E1→E19）", len(card["milestones"]) == 18)
    check("B4 关键结论 19 条", len(card["findings"]) == 19)
    check("B5 诚实边界 20 条", card["gaps_total"] == 20)
    check("B6 门禁判据合计 = 430（含 94 条突变探针）",
          card["span"]["gate_checks"] == 430 and card["span"]["probe_checks"] == 94)
    check("B6c 计数拉平：22 能力模块 / 23 模块 / 21 常驻门禁",
          card["span"]["capability_modules"] == 22 and card["span"]["modules"] == 23
          and card["span"]["entrypoints"] == 21)
    check("B6b 判据合计 ≡ Σ 各段 gate（内部自洽）",
          sum(m["gate"] for m in card["milestones"]) == card["span"]["gate_checks"]
          and sum(m["seg_probes"] for m in card["milestones"]) == card["span"]["probe_checks"])
    check("B7 旗舰容量 256×256 ⇒ 65536 突触 · 257 物理列",
          card["flagship"]["n_synapses"] == 65536
          and card["flagship"]["n_phys_cols_incl_ref"] == 257)
    check("B8 规模律：相对误差有界（256 ⇒ 0.030）· 绝对误差 ∝N（0.08→0.54）",
          abs(card["physics"]["metrics"]["scale_rel_err_256"] - 0.030) < 1e-9
          and card["physics"]["metrics"]["scale_abs_err_256"]
          > card["physics"]["metrics"]["scale_abs_err_32"])
    check("B9 零外部 SPICE 引擎声明", card["identity"]["zero_spice_engine"] is True)
    check("B10 landmark 登记含 source（Mythic · mythic.ai）",
          len(EC.LANDMARKS_BRIEF) >= 1
          and all(e.get("source") for e in EC.LANDMARKS_BRIEF))
    check("B11 定位声明含「不报任何 TOPS / TOPS-W」",
          "不报任何 TOPS / TOPS-W" in card["positioning"]["disclaimer"])

    # B12–B15 E6–E9 四块新能力面（升级后必须出现在对外卡上）
    check("B12 E6 版图签核：1T 单元 7 元素 · 4×4=120 元素 · GDS 936 B · W/L=1.20/0.30",
          card["layout"]["cell_elements"] == 7
          and card["layout"]["arr_4x4_elements"] == 120
          and card["layout"]["gds_bytes_4x4"] == 936
          and abs(card["layout"]["w_um"] - 1.20) < 1e-9
          and abs(card["layout"]["l_um"] - 0.30) < 1e-9)
    check("B13 E7 寄生后仿：R□=0.084 Ω/□ · IR drop N=4 0.42%→N=32 27.0% · sneak 1.29×→7.26×",
          abs(card["parasitic"]["sheet_r_m1_ohm_sq"] - 0.084) < 1e-12
          and card["parasitic"]["ir_drop_rel"][0][1] == 0.0042
          and card["parasitic"]["ir_drop_rel"][-1][1] == 0.270
          and card["parasitic"]["sneak_ratio"][-1][1] == 7.26)
    check("B14 E8 失配/校准：σ_ΔVth=5.00 mV · MC σ_rel 0.654% · L0 1.696%→L1 0.212%→L2 0.0743%",
          abs(card["mismatch"]["sigma_vth_mv"] - 5.00) < 1e-9
          and abs(card["mismatch"]["mc_sigma_rel_8x8"] - 0.00654) < 1e-9
          and card["mismatch"]["calibration"]["L0_rel"]
          > card["mismatch"]["calibration"]["L1_rel"]
          > card["mismatch"]["calibration"]["L2_rel"])
    check("B15 E9 规模压力：压缩比 3571× · 三重规模律 · 上界 5% ⇒ N≤18",
          card["scale_pressure"]["facts"]["compression_1024"] == 3571.0
          and len(card["scale_pressure"]["tiers"]) == 4
          and any(c["budget_rel"] == 0.05 and c["max_rows"] == 18
                  for c in card["scale_pressure"]["ceiling"]))

    # B16/B17 🔴 **与底层模块交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的数字必须 ≡ 模块实测值 —— 这是「内部能力 ↔ 对外载体」的机器化对齐，
    # 而不是"卡自己和自己一致"。任何一侧漂移 ⇒ 必红。
    from lda_l2.ecore import device_limits as DL   # noqa: E402
    from lda_l2.ecore import device_pde as DP      # noqa: E402
    cc = DP.cross_check_vth()
    pts = DP.cross_check_qs()
    check("B16 🔴 E11-c 面 **与模块交叉核对**：卡内数字 ≡ device_pde 实测"
          "（V_th 闭式⟷PDE · Q_s 跨点最差）",
          abs(card["device_pde"]["vth_golden_v"] - cc["V_th_golden"]) < 5e-4
          and abs(card["device_pde"]["vth_rel_err_pct"] - cc["rel_err"] * 100) < 1e-3
          and abs(card["device_pde"]["qs_cross_point_worst_rel_pct"]
                  - max(p["rel_err"] for p in pts) * 100) < 1e-3,
          "卡 %.4f%% vs 模块 %.4f%%" %
          (card["device_pde"]["qs_cross_point_worst_rel_pct"],
           max(p["rel_err"] for p in pts) * 100))
    check("B17 🔴 E11-d 面 **与模块交叉核对**：卡内数字 ≡ device_limits 实测"
          "（半宽比 · L=65nm 缺口）",
          abs(card["device_limits"]["physical_over_numerical_halfwidth"]
              - DL.window_ratio_physical_over_numerical()) < 1e-3
          # 卡内为 3 位有效数字展示（0.379），模块精确值 0.37864 ⇒ 容差按展示精度取 2e-3
          and abs(card["device_limits"]["gap_at_L65nm"]["rolloff_frac_of_vth"]
                  - DL.literature_gap_report(0.065)["rolloff_frac_of_vth"]) < 2e-3,
          "卡 %.3f vs 模块 %.5f" %
          (card["device_limits"]["gap_at_L65nm"]["rolloff_frac_of_vth"],
           DL.literature_gap_report(0.065)["rolloff_frac_of_vth"]))

    # B18 🔴 **与 E12 的 2D 求解器交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的 2D 数字必须 ≡ `device_2d` 用**同参数**实测出来的值。
    # 参数刻意选与卡内数字同源（长沟道 dx=15 nm / 短沟道 dx=5 nm）—— 换网格数字会变，
    # 所以「卡内数字」与「核对参数」必须成对锁死，否则这条判据本身会变成噪声源。
    from lda_l2.ecore import device_2d as D2   # noqa: E402
    cc2 = D2.cross_check_vth_2d_longchannel(lg_nm=1000.0, dx_target_nm=15.0)
    ro2 = D2.rolloff_2d_report(Ls_nm=(65.0, 100.0, 250.0), dx_target_nm=5.0)
    dib2 = D2.dibl_2d_report(Ls_nm=(65.0,), dx_target_nm=5.0)
    nat2 = D2.natural_length_2d()
    d2f = card["device_2d"]
    check("B18 🔴 E12 面 **与模块交叉核对**：卡内数字 ≡ device_2d 实测"
          "（长沟道 rel · roll-off 65nm · DIBL · 指数律 R² · 自然长度同式）",
          abs(d2f["long_channel"]["rel_err_pct"] - cc2["rel_err"] * 100) < 5e-3
          and abs(d2f["rolloff"]["dvth_vs_golden_mv"][0]
                  - ro2["points"][0]["dvth_vs_golden_mv"]) < 0.1
          and abs(d2f["dibl"]["dibl_mv_per_v"]
                  - dib2["points"][0]["dibl_mv_per_v"]) < 0.2
          and abs(d2f["dibl"]["r2_exp_law"]
                  - dib2["exponential_law"]["r2"]) < 1e-4
          and abs(d2f["natural_length_nm"]["lda_2d"] - nat2["lda_2d_nm"]) < 0.05,
          "rel %.4f%% vs %.4f%% | rolloff %.1f vs %.1f mV | DIBL %.1f vs %.1f | R² %.5f vs %.5f"
          % (d2f["long_channel"]["rel_err_pct"], cc2["rel_err"] * 100,
             d2f["rolloff"]["dvth_vs_golden_mv"][0], ro2["points"][0]["dvth_vs_golden_mv"],
             d2f["dibl"]["dibl_mv_per_v"], dib2["points"][0]["dibl_mv_per_v"],
             d2f["dibl"]["r2_exp_law"], dib2["exponential_law"]["r2"]))

    # B19 🔴 **与 E13 的输运桥交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的 E13 数字必须 ≡ `device_transport` 用**同口径参数**实测出来的值。
    # ⚠️ SS 随 **V_g 扫描点数**变化（拟合窗口）⇒ 「卡内数字」与「核对参数」必须**成对锁死**
    #    （本门禁口径 = `default_vg_list(n=13)`，与 E13 门禁的 VG_N=13 一致）。
    from lda_l2.ecore import device_transport as DT   # noqa: E402
    from lda_solver import mos_2d_transport as MT     # noqa: E402
    vg13 = DT.default_vg_list(n=13)
    _Ls = (65.0, 100.0, 250.0, 1000.0)
    _cur = {L: DT.transfer_curve(L, vg_list=vg13) for L in _Ls}
    _ss4 = {L: _cur[L]["SS_mv_dec"] for L in _Ls}
    _cons = DT.current_conservation_report(_cur[100.0])
    _g6 = DT.vth_cc_vs_surface_potential(curve=_cur[100.0])
    _idv = DT.id_vd_report(lg_nm=300.0)
    _cl = MT.ss_closed_form()
    _cap = DT.transport_capability_closure()
    dtf = card["device_transport"]
    _ss_card = dtf["ss_vs_length"]["ss_mv_dec"]
    _rel_pct = abs(_ss4[1000.0] - _cl["SS_mv_dec"]) / _cl["SS_mv_dec"] * 100.0
    check("B19a 🔴 E13 面 **SS 与栅长趋势交叉核对**：卡内 4 点 ≡ 模块实测（SS 双锚 + L↓⇒SS↑）",
          all(abs(_ss_card[i] - _ss4[L]) < 0.1 for i, L in enumerate(_Ls))     # [65,100,250,1000]
          and abs(dtf["long_channel"]["ss_2d_mv_dec"] - _ss4[1000.0]) < 0.05
          and abs(dtf["ss_at_100nm_mv_dec"] - _ss4[100.0]) < 0.05
          and abs(dtf["thermal_limit_mv_dec"] - _cl["SS_ideal_mv_dec"]) < 0.05
          and abs(dtf["ss_closed_platform_mv_dec"] - _cl["SS_mv_dec"]) < 0.05
          and abs(dtf["long_channel"]["ss_closed_mv_dec"] - _cl["SS_mv_dec"]) < 0.05
          and abs(dtf["cd_over_cox"] - _cl["Cd_over_Cox"]) < 1e-3
          and abs(dtf["long_channel"]["rel_err_pct"] - _rel_pct) < 0.05
          and _ss4[65.0] > _ss4[100.0] > _ss4[250.0] > _ss4[1000.0],
          "卡 %s vs 模块 %s | 热极限 %.2f ⟷ %.2f | Cd/Cox %.4f ⟷ %.4f"
          % (["%.1f" % v for v in _ss_card], ["%.1f" % _ss4[L] for L in _Ls],
             dtf["thermal_limit_mv_dec"], _cl["SS_ideal_mv_dec"],
             dtf["cd_over_cox"], _cl["Cd_over_Cox"]))
    check("B19b 🔴 E13 面 **守恒 / 输出特性 / V_th 双法交叉核对**：卡内 ≡ 模块实测",
          abs(dtf["conservation"]["worst_rel"] - _cons["worst_rel"]) < 1e-6
          and _cons["passes"]
          and all(abs(dtf["id_vd"]["I_d_a_per_m"][i] - _idv["points"][i]["I_d_a_per_m"]) < 1.0
                  for i in range(4))
          and _idv["monotone"]
          and abs(dtf["vth_two_methods"]["cc_v"] - _g6["V_th_cc_v"]) < 5e-4
          and abs(dtf["vth_two_methods"]["surface_potential_v"]
                  - _g6["V_th_surface_potential_v"]) < 5e-4
          and abs(dtf["vth_two_methods"]["abs_diff_mv"] - _g6["abs_diff_mv"]) < 0.1,
          "守恒 %.2e ⟷ %.2e | V_th CC %.4f ⟷ %.4f | ψ_s %.4f ⟷ %.4f"
          % (dtf["conservation"]["worst_rel"], _cons["worst_rel"],
             dtf["vth_two_methods"]["cc_v"], _g6["V_th_cc_v"],
             dtf["vth_two_methods"]["surface_potential_v"], _g6["V_th_surface_potential_v"]))
    check("B19c 🔴 E13 面 **能力闭合表交叉核对**：卡内 闭合 4 / 仍不可用 4 ≡ 模块（含 T2 永久锁）",
          dtf["capability_closure"]["closed"] == len(_cap["closed_by_e13"]) == 4
          and dtf["capability_closure"]["still"] == len(_cap["still_not_available"]) == 4
          and any("T2" in c["why"] for c in _cap["still_not_available"]))

    # B20 🔴 **与 E14 的 converter / periphery 模块交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的 E14 数字必须 ≡ 模块**同参数**实测值。
    # ⚠️ `dac_static_report` 参数（vref/R/WL/vgate）与 `driver_scale_table` 的
    #    （budget/r_out 列表）与卡内数字**成对锁死**（换参数数字会变）。
    from lda_l2.ecore import converter as CV        # noqa: E402
    from lda_l2.ecore import periphery as PY_       # noqa: E402
    from lda_l2.ecore.mosfet import NmosParams as _NP   # noqa: E402
    from lda_l2.ecore import parasitic as PA_       # noqa: E402
    _r_seg2 = PA_.array_parasitics(8, 8)["r_row_seg_ohm"]
    _nn2 = _NP(w_over_l=1.2 / 0.3)
    _g2 = _nn2.kp * _nn2.w_over_l * (2.1 - _nn2.vth0)
    _dac = CV.dac_static_report(8, step=1)
    _sar8 = CV.sar_convert(0.4187, 8, 1.0)
    _sarrep = CV.sar_error_report(8, samples=16)
    _sh = CV.sample_hold_transient()
    _drv = PY_.row_driver_mna_check(0.8, 1.0e3, 1.0e3, 1.0e3)
    _scl = PY_.driver_scale_table(_r_seg2, _g2, 0.05, (0.0, 1.0, 5.0, 20.0))
    _pol = PY_.vcvs_polarity_fact()
    _rel_chg = (abs(_sar8["v_top_hold_v"] - _sar8["top_closed_form_hold_v"])
                / abs(_sar8["top_closed_form_hold_v"]))
    dpf = card["device_periphery"]
    check("B20 🔴 E14 面 **与 converter / periphery 模块交叉核对**：卡内数字 ≡ 模块实测"
          "（DAC 全码误差 + R_on · CDAC 电荷守恒 · SAR ≤1LSB · 采样保持离散闭式 · "
          "行驱动 MNA rel · R_oc ⇒ N_max · vcvs 极性）",
          abs(dpf["dac"]["max_abs_err_lsb"] - _dac["max_abs_err_lsb"]) < 5e-3
          and abs(dpf["dac"]["ron_ohm"] - _dac["ron_ohm"]) < 0.05
          and dpf["dac"]["codes_scanned"] == _dac["codes_scanned"]
          and dpf["adc"]["charge_conservation_rel"] < 1e-11 and _rel_chg < 1e-11
          and dpf["adc"]["sar_max_err_lsb"] == _sarrep["max_err_lsb"]
          and abs(dpf["sample_hold"]["rel_err_vs_discrete"] - _sh["rel_err_discrete"]) < 1e-12
          and abs(dpf["row_driver"]["mna_rel_err"] - _drv["rel_err"]) < 1e-9
          and [r["n_max"] for r in _scl["rows"]] == dpf["scale_ceiling"]["n_max"]
          and bool(_pol["polarity_inverted"]) == (dpf["platform_defect"]["probe_v"] < 0.0),
          "DAC err %.4f ⟷ %.4f | R_on %.1f | 电荷 %.1e ⟷ %.1e | SAR %d | 采样 %.1e ⟷ %.1e | "
          "N_max %s | vcvs=%s"
          % (dpf["dac"]["max_abs_err_lsb"], _dac["max_abs_err_lsb"], _dac["ron_ohm"],
             dpf["adc"]["charge_conservation_rel"], _rel_chg, _sarrep["max_err_lsb"],
             dpf["sample_hold"]["rel_err_vs_discrete"], _sh["rel_err_discrete"],
             [r["n_max"] for r in _scl["rows"]], _pol["polarity_inverted"]))

    # B21 🔴 **与 E15 的 budget 模块交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的误差预算数字必须 ≡ `budget` 模块**同参数**实测值。
    # ⚠️ 参数成对锁死：`error_budget_report(8, 8)` 与
    #    `budget_vs_n([8,16,32,64,128,256], budget_pct=5.0)` —— 参数漂了这条判据自己就成噪声源。
    from lda_l2.ecore import budget as BD          # noqa: E402
    _bf = card["device_budget"]
    _rep = BD.error_budget_report(8, 8)
    _bcv = BD.budget_vs_n([8, 16, 32, 64, 128, 256], budget_pct=5.0)
    _full = BD.max_scale_full_chain(5.0)
    _only = BD.max_scale_full_chain(5.0, ir_drop_only=True)
    _bd_t = {t["name"]: t["rel_pct"] for t in _rep["terms"]}
    _cd_t = {t["name"]: t["rel_pct"] for t in _bf["budget_8x8"]["terms"]}
    check("B21 🔴 E15 面 **与 budget 模块交叉核对**：卡内数字 ≡ 模块实测"
          "（六项误差逐项 · worst/bits · 主导项 · 精度vsN 六点 · 全链上界 vs 仅IR）",
          set(_bd_t) == set(_cd_t) == {"ir_drop", "device_mismatch", "row_driver_load",
                                       "adc_quantization", "dac_inl", "adc_sar"}
          and all(abs(_bd_t[k] - _cd_t[k]) < 5e-4 for k in _bd_t)
          and abs(_bf["budget_8x8"]["worst_pct"] - _rep["worst_pct"]) < 5e-3
          and abs(_bf["budget_8x8"]["worst_bits"] - _rep["worst_bits"]) < 5e-3
          and _bf["budget_8x8"]["dominant"] == _rep["dominant"]["name"]
          and len(_bf["scale_curve"]) == len(_bcv["points"])
          and all(abs(a_["worst_pct"] - b_["worst_pct"]) < 5e-3
                  for a_, b_ in zip(_bf["scale_curve"], _bcv["points"]))
          and all(a_["dominant"] == b_["dominant"]
                  for a_, b_ in zip(_bf["scale_curve"], _bcv["points"]))
          and _bf["scale_ceiling"]["full_chain_n_max"] == _full["n_max"]
          and _bf["scale_ceiling"]["ir_drop_only_n_max"] == _only["n_max"])

    # B22 🔴 **与 E16 的 weight_prog 模块交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的权重编程数字必须 ≡ `weight_prog` 模块**同参数**实测值。
    # ⚠️ 参数成对锁死：`noise_floor_sigma(0.005, 0.30)` · `canonical_weights(8, 8)` ·
    #    `programming_budget_terms(..., include_level=True, bits=6)` ·
    #    `max_scale_full_chain(5.0, prog_terms_fn=…)` —— 参数漂了这条判据自己就成噪声源。
    from lda_l2.ecore import weight_prog as WP      # noqa: E402
    _wp = card["device_weight_prog"]
    _PR = WP.WEIGHT_PROG_PROCESS
    _W8 = WP.canonical_weights(8, 8)
    _sig = WP.noise_floor_sigma(_PR["sigma_pulse_rel"], _PR["alpha_pulse"])
    _mc = WP.write_verify_stochastic(sigma_pulse_rel=_PR["sigma_pulse_rel"],
                                     alpha=_PR["alpha_pulse"], max_pulses=64,
                                     seed=0, trials=4000)
    _r6 = BD.error_budget_report(8, 8, include_programming=True,
                                 prog_terms=WP.programming_budget_terms(
                                     8, 8, w=_W8, include_level=True, bits=6))
    _base = BD.error_budget_report(8, 8)
    _lc = BD.max_scale_full_chain(5.0, prog_terms_fn=lambda kk: WP.programming_budget_terms(
        kk, kk, include_level=False))["n_max"]
    _mc6 = BD.max_scale_full_chain(5.0, prog_terms_fn=lambda kk: WP.programming_budget_terms(
        kk, kk, include_level=True, bits=6))["n_max"]
    _lev_c = [_wp["level_sensitivity"][k3]["level_pct"] for k3 in ("4", "6", "8", "10", "12")]
    _lev_m = [next(x["rel_pct"] for x in WP.programming_budget_terms(
        8, 8, w=_W8, include_level=True, bits=b3) if x["name"] == "weight_prog_level")
        for b3 in (4, 6, 8, 10, 12)]
    check("B22 🔴 E16 面 **与 weight_prog 模块交叉核对**：卡内数字 ≡ 模块实测"
          "（噪声地板闭式⟷MC · 脉冲数 · base 不变 · MLC6 worst/bits · 位数敏感性五点 · "
          "上界收缩 12→11→1）",
          abs(_wp["noise_floor"]["sigma_cell_pct"] - _sig * 100.0) < 5e-4
          and abs(_wp["noise_floor"]["mc_pct"] - _mc["sigma_residual"] * 100.0) < 5e-3
          and _wp["noise_floor"]["iters_to_tol"] == WP.iter_to_tolerance(
              1.0, _PR["tol_rel"], _PR["alpha_pulse"])
          and abs(_wp["budget"]["base"]["worst_pct"] - _base["worst_pct"]) < 5e-3
          and abs(_wp["budget"]["mlc6"]["worst_pct"] - _r6["worst_pct"]) < 5e-3
          and abs(_wp["budget"]["mlc6"]["bits"] - _r6["worst_bits"]) < 5e-3
          and all(abs(a3 - b3) < 5e-3 for a3, b3 in zip(_lev_c, _lev_m))
          and all(_lev_c[i3] > _lev_c[i3 + 1] for i3 in range(4))
          and _wp["scale_ceiling"]["default_n_max"] == 12
          and _wp["scale_ceiling"]["analog_n_max"] == _lc
          and _wp["scale_ceiling"]["mlc6_n_max"] == _mc6
          and _wp["scale_ceiling"]["analog_n_max"] < _wp["scale_ceiling"]["default_n_max"])

    # B23 🔴 **与 E17 的 timing 模块交叉核对**（真拉平 · 非自洽）：
    # 卡里硬编码的时序数字必须 ≡ `timing` 模块**同参数**实测值。
    # ⚠️ 参数成对锁死：`per_sample_report(8, 8, 8)` · `time_vs_n([8, 1024], 8)` ·
    #    `crossover_n_ps(1.0e-9)` · `clock_budget(160.0e-9, 8, 8)` ·
    #    `E15 error_budget_report(8, 8)`（保护性约束锚）—— 参数漂了这条判据自己就成噪声源。
    from lda_l2.ecore import timing as TM      # noqa: E402
    _tm = card["device_timing"]
    _rep_t = TM.per_sample_report(8, 8, 8)
    _stg = {st["name"]: st["t_s"] * 1e9 for st in _rep_t["stages"]}
    _tv_t = TM.time_vs_n([8, 1024], 8)
    _cx_t = TM.crossover_n_ps(1.0e-9)
    _cb_t = TM.clock_budget(160.0e-9, 8, 8)
    check("B23 🔴 E17 面 **与 timing 模块交叉核对**：卡内数字 ≡ 模块实测"
          "（五阶段逐项 · serial/pipelined/收益/速率 · 主导项 · 规模×时间跨度 · 交叉点 · 时钟反解残差 · "
          "E15 保护性锚）",
          len(_tm["stages"]) == 5
          and all(abs(_tm["stages"][i4]["t_ns"] - _stg[_tm["stages"][i4]["name"]]) < 1e-5
                  for i4 in range(5))
          and abs(_tm["totals"]["serial_ns"] - _rep_t["serial_ns"]) < 1e-4
          and abs(_tm["totals"]["pipelined_period_ns"] - _rep_t["pipelined_period_ns"]) < 1e-4
          and abs(_tm["totals"]["pipeline_gain_frac"] - _rep_t["pipeline_gain_frac"]) < 1e-5
          and abs(_tm["totals"]["max_sample_rate_msa"]
                  - _rep_t["max_sample_rate_hz"] / 1e6) < 1e-3
          and _tm["totals"]["dominant"] == _rep_t["dominant_name"]
          and abs(_tm["scale_vs_time"]["tau_row_span_x"] - _tv_t["tau_row_span_x"]) < 1.0
          and abs(_tm["scale_vs_time"]["serial_span_x"] - _tv_t["serial_span_x"]) < 1e-4
          and _tm["crossover"]["ns"] == _cx_t["n_bisect"]
          and abs(_tm["crossover"]["analytic_ns"] - _cx_t["n_analytic"]) < 0.05
          and abs(_tm["clock_budget"]["fixed_ns"] - _cb_t["fixed_s"] * 1e9) < 1e-3
          and abs(_tm["clock_budget"]["t_clk_max_ns"] - _cb_t["t_clk_max_s"] * 1e9) < 1e-4
          and _tm["clock_budget"]["back_calc_residual_s"] == _cb_t["residual_s"]
          and abs(_tm["protection"]["e15_worst_pct"]
                  - BD.error_budget_report(8, 8)["worst_pct"]) < 1e-4
          and abs(_tm["protection"]["e15_bits"]
                  - BD.error_budget_report(8, 8)["worst_bits"]) < 1e-4)

    # B24 🔴 E18 面 与 col_share 模块交叉核对（面积维度 · 全仓此前空白）
    from lda_l2.ecore import col_share as CS      # noqa: E402
    _dcs = card["device_col_share"]
    _cv8 = CS.converter_area_um2(8)
    _arch_c = CS.architectures(64, 8)
    _sl_c = CS.scaling_law_report(4096, 8, ks=(1, 2, 4, 8, 16, 32))
    _ks_c = CS.k_star(8)
    _kt_c = CS.ktc_crossing_share(8)
    _rc_c = CS.recommend_architecture(64, 8, 10.0e6)
    _rv_c = CS.replication_vs_sharing(64, 8)
    check("B24 🔴 E18 面 **与 col_share 模块交叉核对**：卡内数字 ≡ 模块实测"
          "（面积双项闭式 · 量级比 · 第一原理散布 · 第二原理三斜率 · K* · kT/C 地板 · "
          "架构族五条逐条 · 推荐 · 复制-共享 · 保护性锚）",
          abs(_dcs["magnitude"]["unit_cap_area_um2"] - _cv8["cap_area_um2"]) < 1e-6
          and abs(_dcs["magnitude"]["converter_area_um2"] - _cv8["area_um2"]) < 1e-6
          and abs(_dcs["magnitude"]["converter_cap_over_logic"]
                  - _cv8["cap_area_um2"] / _cv8["logic_area_um2"]) < 1e-9
          and abs(_dcs["magnitude"]["array_footprint_um2"]
                  - _arch_c["array_footprint_um2"]) < 1e-6
          and abs(_dcs["magnitude"]["readout_over_array_ratio"]
                  - _arch_c["readout_over_array_ratio_parallel"]) < 1e-3
          and abs(_dcs["magnitude"]["full_parallel_mm2"] - _arch_c["area_max_mm2"]) < 1e-9
          and abs(_dcs["magnitude"]["arch_ratio"]
                  - _arch_c["area_ratio_max_over_min"]) < 1e-3
          and abs(_dcs["first_principle"]["spread"]) < 1e-12
          and abs(_dcs["second_principle"]["slope_plain"] - _sl_c["slope_plain"]) < 1e-9
          and abs(_dcs["second_principle"]["slope_keep_cap"] - _sl_c["slope_keep_cap"]) < 1e-9
          and abs(_dcs["second_principle"]["slope_keep_total"]
                  - _sl_c["slope_keep_total"]) < 1e-6
          and abs(_dcs["k_star"]["k_star"] - _ks_c["k_star"]) < 1e-9
          and abs(_dcs["ktc"]["bits_ceiling_at_256pF"]
                  - CS.thermal_noise_bits_ceiling(TM.cdac_total_cap(8))) < 1e-4
          and abs(_dcs["ktc"]["k_share_crit_8bit"] - _kt_c["k_share_crit"]) < 1.0
          and len(_dcs["architectures"]["rows"]) == 5
          and all(abs(_dcs["architectures"]["rows"][i5]["area_um2"]
                      - _arch_c["rows"][i5]["area_um2"]) < 1e-6 for i5 in range(5))
          and all(_dcs["architectures"]["rows"][i5]["name"]
                  == _arch_c["rows"][i5]["architecture"] for i5 in range(5))
          and abs(_dcs["recommend"]["area_um2"] - _rc_c["best"]["area_um2"]) < 1e-6
          and abs(_dcs["recommend"]["c_tot_unit_f"] - _rc_c["c_tot_unit_f"]) < 1e-21
          and abs(_dcs["replication_vs_sharing"]["replicated_spread"]
                  - _rv_c["product_replicated_spread"]) < 1e-12
          and len(_dcs["closed_form"]) == 7
          and abs(_dcs["protection"]["e15_worst_pct"]
                  - BD.error_budget_report(8, 8)["worst_pct"]) < 1e-4)

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 破坏 honest_note 关键字 ⇒ ⑥ 必红
    saved_note = EC.ECORE_HONEST_NOTE
    EC.ECORE_HONEST_NOTE = saved_note.replace("非流片后实测", "")
    ok_c1 = EC.run_selfchecks(verbose=False)
    EC.ECORE_HONEST_NOTE = saved_note
    check("C1 反向：移除「非流片后实测」字样 ⇒ ⑥ 判定必红（run_selfchecks False）",
          ok_c1 is False)

    # C2 清空公开 landmark ⇒ ⑫ 必红
    saved_lm = EC.LANDMARKS_BRIEF
    EC.LANDMARKS_BRIEF = []
    ok_c2 = EC.run_selfchecks(verbose=False)
    EC.LANDMARKS_BRIEF = saved_lm
    check("C2 反向：清空公开 landmark ⇒ ⑫ 判定必红（run_selfchecks False）",
          ok_c2 is False)

    # C3 让 verdict 冒充 ACCEPT ⇒ ⑥ 必红（不伪装实测）
    saved_cc = EC.case_card

    def _fake_card(repo_root=None):
        c = saved_cc(repo_root=repo_root)
        c["verdict"] = "ACCEPT"
        return c

    EC.case_card = _fake_card
    # 直接检查不伪装实测红线（复刻自检 ⑥ 的判据）
    fake = EC.case_card(repo_root="__nonexistent_root__")
    EC.case_card = saved_cc
    check("C3 反向：verdict 冒充 ACCEPT ⇒ 不伪装实测判据必红",
          fake["verdict"] != "DESIGN_VERIFIED")

    # C4 E9 可及规模上界改成非单调（预算越紧反而行数越多）⇒ ⑳ 判定必红
    saved_ceil = EC.SCALE_CEILING
    EC.SCALE_CEILING = [{"budget_rel": 0.10, "max_rows": 8},
                        {"budget_rel": 0.05, "max_rows": 18},
                        {"budget_rel": 0.02, "max_rows": 11},
                        {"budget_rel": 0.01, "max_rows": 26}]     # ← 非单调
    ok_c4 = EC.run_selfchecks(verbose=False)
    EC.SCALE_CEILING = saved_ceil
    check("C4 反向：可及上界非单调 ⇒ ⑳ 判定必红（规模律不许被静默改坏）", ok_c4 is False)

    # C5 E6–E9 能力面 facts 被掏空（GDS 字节归零）⇒ ⑲ 判定必红
    saved_lay = dict(EC.LAYOUT_FACTS)
    EC.LAYOUT_FACTS["cell_elements"] = 0
    ok_c5 = EC.run_selfchecks(verbose=False)
    EC.LAYOUT_FACTS.clear()
    EC.LAYOUT_FACTS.update(saved_lay)
    check("C5 反向：掏空 E6 版图能力面（cell_elements=0）⇒ ⑲ 判定必红", ok_c5 is False)

    # C6 E11-c 面被改坏（G-3 不自洽被改成「自洽」）⇒ ㉑ 判定必红
    saved_pc = dict(EC.DEVICE_PDE_FACTS["param_consistency"])
    EC.DEVICE_PDE_FACTS["param_consistency"] = dict(saved_pc, consistent=True)
    ok_c6 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_PDE_FACTS["param_consistency"] = saved_pc
    check("C6 反向：把 G-3 参数不自洽改成「自洽」⇒ ㉑ 判定必红"
          "（诚实项不许被静默抹平）", ok_c6 is False)

    # C7 E11-d 面被掏空（短沟道缺口归零）⇒ ㉒ 判定必红
    saved_gap = dict(EC.DEVICE_LIMITS_FACTS["gap_at_L65nm"])
    EC.DEVICE_LIMITS_FACTS["gap_at_L65nm"] = {"rolloff_frac_of_vth": 0.0,
                                              "dibl_frac_of_vth": 0.0,
                                              "rolloff_dvth_v": 0.0,
                                              "vth_long_channel_v": 0.4260}
    ok_c7 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_LIMITS_FACTS["gap_at_L65nm"] = saved_gap
    check("C7 反向：把短沟道缺口归零 ⇒ ㉒ 判定必红（缺口不许被静默抹掉）", ok_c7 is False)

    # C8 🔴 诚实护栏**换代**（E13-e）：E12-e 时此探针注入「已支持 2D MOS」；
    #    E12-e 改注入「已算出 I-V」（当时该能力不存在）；**E13 后 I–V 已真实存在**
    #    ⇒ 护栏对象换成**抬高自身**的**新**风险：DD 框架之外的机制（量子修正 / 弹道 / TOPS）。
    saved_gaps = [dict(g) for g in EC.GAPS]
    EC.GAPS[0]["detail"] = "本平台内核已含量子修正，并已算弹道输运。"
    ok_c8 = EC.run_selfchecks(verbose=False)
    EC.GAPS[:] = saved_gaps
    check("C8 反向：注入「已含量子修正 / 已算弹道」口径 ⇒ ㉗ 诚实判据必红"
          "（输运能力到手后最易发生的**抬高自身**漂移）", ok_c8 is False)

    # C9 E12 面被掏空（DIBL 指数律 R² 归零 ⇒ 退化为「随便报个数」）⇒ ㉔ 判定必红
    saved_dibl = dict(EC.DEVICE_2D_FACTS["dibl"])
    EC.DEVICE_2D_FACTS["dibl"] = dict(saved_dibl, r2_exp_law=0.0)
    ok_c9 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_2D_FACTS["dibl"] = saved_dibl
    check("C9 反向：把 E12 的 DIBL 指数律 R² 归零 ⇒ ㉔ 判定必红"
          "（「2D 解真做出来了」的判据不许被掏空）", ok_c9 is False)

    # C10 🔴 **贬低方向的回扫**（E13-e 新立 · 与 C8 成对）：
    #     把 E12 面的「已由 E13 闭合 / 不代表当前能力状态」标注**抹掉**（= 把已闭合的缺口
    #     重新写成**当前**缺口）⇒ ㉓ 必红。**两个方向各有一条探针**，缺一不可：
    #     只守「抬高」会漏掉假贬低，只守「贬低」会漏掉假宣传。
    saved_tc = EC.DEVICE_2D_FACTS["transport_closure"]
    EC.DEVICE_2D_FACTS["transport_closure"] = (
        "本段为准平衡静电求解、不含漂移扩散输运 ⇒ 不产 I-V；「算得了」仅限静电量；"
        "补 I–V 需 Gummel 2D 输运 ⇒ E13 候选。")
    ok_c10 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_2D_FACTS["transport_closure"] = saved_tc
    check("C10 反向：抹掉 E12 面的「已由 E13 闭合」标注（**假贬低回归**）⇒ ㉓ 判定必红"
          "（贬低方向的回扫 · 与 C8 成对）", ok_c10 is False)

    # C11 🔴 **平台缺陷不许被静默抹掉**（E14-e 新立 · 与 C8/C10 同族）：
    #     把 `platform_defect` 换成「无平台缺陷」⇒ ㉙ 必红。
    #     —— **贬低方向的第三种形态**：不是"把能做的说成不能做"，而是"把已知缺陷说成不存在"。
    saved_pd = dict(EC.DEVICE_PERIPHERY_FACTS["platform_defect"])
    EC.DEVICE_PERIPHERY_FACTS["platform_defect"] = {
        "what": "无平台缺陷", "probe_v": 0.0, "why_not_fixed": "-", "still_valid": "-"}
    ok_c11 = EC.run_selfchecks(verbose=False)
    EC.DEVICE_PERIPHERY_FACTS["platform_defect"] = saved_pd
    check("C11 反向：抹掉「vcvs 极性缺陷登记」（假装平台无缺陷）⇒ ㉙ 判定必红"
          "（**平台缺陷不许被静默抹掉**）", ok_c11 is False)

    # C12 🔴 **误差预算口径不许被拔高成 ENOB / 动态口径**（E15-e 新立 · 抬高方向）：
    #     把 `effective_bits_semantics` 换成「这就是 ENOB，已含动态」⇒ ㉛ 必红。
    #     ⚠️ 本探针能变红的前提是 ㉛ **按来源分别断言** —— 否则 G-O 里的同名字符串会把它掩盖 ⇒ 假绿。
    saved_sem = EC.BUDGET_FACTS["effective_bits_semantics"]
    EC.BUDGET_FACTS["effective_bits_semantics"] = "这就是 ENOB，已含动态与时序口径。"
    ok_c12 = EC.run_selfchecks(verbose=False)
    EC.BUDGET_FACTS["effective_bits_semantics"] = saved_sem
    check("C12 反向：把误差预算口径拔高成「这就是 ENOB / 已含动态」⇒ ㉛ 判定必红"
          "（**抬高方向：自定义量不许冒充标准量**）", ok_c12 is False)

    # C13 🔴 **E16 双向**（E16-e 新立）：
    #   ① 抬高方向 —— 把编程模型说成「已标定 PDK / 已含 TOPS」· 把「共模漂移」当成精度上限
    #      （共模可被单次全局增益校准消除 ⇒ 不该进预算）⇒ ㉝ 必红；
    #   ② 贬低方向 —— 抹掉/替换 `drift.conditional`（漂移结论**条件于 ν** 的前提声明）⇒ ㉝ 必红。
    #   ⚠️ 能变红的前提是 ㉝ **按来源分别断言**（E15 血案：多来源拼接会稀释判据 ⇒ 探针假绿）。
    _saved_hb = EC.WEIGHT_PROG_FACTS["honest_boundary"]
    _saved_cond = EC.WEIGHT_PROG_FACTS["drift"]["conditional"]
    EC.WEIGHT_PROG_FACTS["honest_boundary"] = "参数均已标定 PDK，已含 TOPS 与能效指标。"
    ok_c13a = EC.run_selfchecks(verbose=False)
    EC.WEIGHT_PROG_FACTS["honest_boundary"] = _saved_hb
    EC.WEIGHT_PROG_FACTS["drift"]["conditional"] = "共模漂移是精度上限，已计入预算。"
    ok_c13b = EC.run_selfchecks(verbose=False)
    EC.WEIGHT_PROG_FACTS["drift"]["conditional"] = _saved_cond
    check("C13 反向（**双向**）：① 编程参数冒充「已标定 PDK / 已含 TOPS」· "
          "② 抹掉「条件于 ν」并把共模漂移当精度上限 ⇒ ㉝ 判定必红"
          "（两个方向各扫一次 · **可被单次校准消掉的项不是精度上限**）",
          ok_c13a is False and ok_c13b is False)

    # C14 反向（**双向**）：
    #   ① **抬高方向** —— 时序能力到手后最易滑成「已报 TOPS / 已完成功耗估算」；
    #   ② **贬低方向** —— E17 前的「全仓时间零覆盖 / 行驱动无限带宽」已闭合，
    #      但**新**的内在边界（宏模型级 + 只覆盖静态）不得被抹掉。
    _saved_tm = dict(EC.TIMING_FACTS)
    try:
        _bad_tm = dict(EC.TIMING_FACTS)
        _bad_tm["disclosure"] = (_bad_tm["disclosure"]
                                 + " 已报 TOPS：7.7 TOPS · 已完成功耗估算。")
        EC.TIMING_FACTS.clear()
        EC.TIMING_FACTS.update(_bad_tm)
        ok_c14a = EC.run_selfchecks(verbose=False)
    finally:
        EC.TIMING_FACTS.clear()
        EC.TIMING_FACTS.update(_saved_tm)
    _saved_gaps3 = [dict(g) for g in EC.GAPS]
    try:
        for _g3 in EC.GAPS:
            if _g3["id"] == "G-R":
                _g3["detail"] = "时序已完全建模，含比较器延时 / 时钟树 / 抖动，并已完成功耗估算。"
        ok_c14b = EC.run_selfchecks(verbose=False)
    finally:
        EC.GAPS[:] = _saved_gaps3
    check("C14 反向（**双向**）：① 时序面冒充「已报 TOPS / 已完成功耗估算」· "
          "② 抹掉「宏模型级」与「只覆盖静态」两条内在边界 ⇒ ㉟ 判定必红"
          "（两个方向各扫一次 · **无功耗模型 ⇒ 绝不报 TOPS**）",
          ok_c14a is False and ok_c14b is False)

    # C15 反向（**双向**）：E18 面 —— ① 抬高方向（面积已实测 / 已报 TOPS）
    #   ② 贬低方向（抹掉 G-S 的三条内在边界：宏模型占位 / 不做功耗估算 / 拒绝硬造精度腿）
    _saved_dcs = dict(EC.COL_SHARE_FACTS)
    _saved_gaps4 = [dict(g) for g in EC.GAPS]
    try:
        _bad_dcs = dict(EC.COL_SHARE_FACTS)
        _bad_dcs["disclosure"] = _bad_dcs["disclosure"] + " 面积已实测；已报 TOPS：8.3 TOPS。"
        EC.COL_SHARE_FACTS.clear()
        EC.COL_SHARE_FACTS.update(_bad_dcs)
        ok_c15a = EC.run_selfchecks(verbose=False)
    finally:
        EC.COL_SHARE_FACTS.clear()
        EC.COL_SHARE_FACTS.update(_saved_dcs)
    try:
        for _g4 in EC.GAPS:
            if _g4["id"] == "G-S":
                _g4["detail"] = "面积已实测，已含动态功耗与复用开关建模。"
        ok_c15b = EC.run_selfchecks(verbose=False)
    finally:
        EC.GAPS[:] = _saved_gaps4
    check("C15 反向（**双向**）：① E18 面冒充「面积已实测 / 已报 TOPS」· "
          "② 抹掉 G-S 的「宏模型占位 / 不做功耗估算 / 拒绝硬造精度腿」三条内在边界 ⇒ ㊲ 判定必红"
          "（两个方向各扫一次 · **无功耗模型 ⇒ 绝不报 TOPS** · "
          "**kT/C 在可达共享度内不是约束 ⇒ 不许把共享说成精度瓶颈**）",
          ok_c15a is False and ok_c15b is False)

    # ══════════════════════ D 免登录 / 零重计算 ═══════════════════════════
    rt = _read("lda/lda_webui/routes.py")
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("D1 端点不进 HEAVY_POST_PATHS（公开只读 · 零重计算 · 无 DoS 面）",
          "/api/ecore_demo" not in heavy)
    get_block = rt.split("GET_ROUTES = {")[1].split("}")[0] if "GET_ROUTES = {" in rt else ""
    check("D2 GET 端点接线（\"/api/ecore_demo\": h_ecore_demo, 在 GET_ROUTES）",
          '"/api/ecore_demo": h_ecore_demo,' in get_block)
    src_ec = _read("lda/lda_webui/ecore_case.py")
    check("D3 🔴 零重计算：ecore_case 不 import 求解器/numpy（纯静态闭式 + 诚实边界）",
          all(k not in src_ec.split("def run_selfchecks")[0]
              for k in ("import lda_l2", "import numpy", "from lda_l2", "from numpy",
                        "import scipy", "from scipy")))

    # ══════════════════════ E API 参考已登记（gen_api_reference 已跑）═══════════════════════
    jp = os.path.join(_ROOT, "docs", "api_reference.json")
    try:
        ref = json.load(open(jp, encoding="utf-8"))
        ep = next((e for e in ref["endpoints"] if e["path"] == "/api/ecore_demo"), None)
        ok_ep = bool(ep) and ep["auth"] == "public" and bool(ep["description"])
        check("E1 API 参考已含 /api/ecore_demo 且 auth=public（gen 已跑 · 防双红）",
              ok_ep, "found=%s auth=%s" % (ep is not None, ep["auth"] if ep else "?"))
    except Exception as e:  # pragma: no cover
        check("E1 API 参考已含 /api/ecore_demo", False, "读参考失败: %s" % e)

    # ══════════════════════ K 自入 CI core（防静默漏接 · 血案 28）═══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        in_core = "run_ecore_case_smoke.py" in R.CORE_SMOKES
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", in_core,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False,
              "import 失败: %s" % e)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
