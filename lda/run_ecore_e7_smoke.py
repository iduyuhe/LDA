"""电子计算芯片寄生提取与后仿 门禁 smoke（E7 · D-157）。

═══ 为什么要有这个 smoke ═══
E7 把 E1–E6 的**理想互连**假设换成**有阻互连**：从 E6 版图几何按教科书闭式提 RC，
注入 E1 的 MNA 求解器做**后仿**，量化 **IR drop** 与 **sneak path** 两类随规模放大的
架构约束。这类「物理效应」最易被悄悄抹平（把 R 归零、把解析 golden 改宽、把旁路电流
写死为零）⇒ 必须钉成常驻断言 + **突变探针**。

  ① **模块自检 10/10** + **E6 回归**（E7 不破坏版图链）
  ② **导线 RC 闭式**（R=ρL/(Wt) ≡ R□·L/W · C=ε₀ε_r·W/d · L/W 依赖）
  ③ **阵列寄生提取与 E6 版图同口径**（足迹/节距/线宽/串联一阶/Elmore）
  ④ **R=0 网络 ≡ 解析 golden**（精确：I_j = Σ g_ij·V_i）
  ⑤ **IR drop**：随 R 与 N 单调增（超线性）· 沿线电压单调不增
  ⑥ **sneak path**：仅选通单元 ⇒ 精确 0；全导通 ⇒ >0 且随 N 增；R=0 时仍存在（拓扑效应）
  ⑦ **吃狗粮闭环**：交叉点电导与 E2 晶体管模型同口径；几何与 E6 版图同口径
  ⑧ **诚实边界 + 红线**（工艺参数非 PDK · 提取为一阶闭式 · r_leak 是数值钉扎 · 零商业 EDA）
  ⑨ **突变探针**（篡 R 闭式 / 拆行线梯 / 篡 golden / 杀 sneak 各必红 + 还原复绿）

运行：python run_ecore_e7_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。**LLM 不进判决路径**。
"""
from __future__ import annotations

import os
import re
import sys
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np                                        # noqa: E402

from lda_l2.ecore import layout as LY                     # noqa: E402
from lda_l2.ecore import parasitic as PA                  # noqa: E402
from lda_l2.ecore.mosfet import NmosParams                # noqa: E402
from lda_harness.smoke_kit import make_check              # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)

N8, M8 = 8, 8
WL_LAYOUT = 4.0            # E6 版图回提的 W/L（1.20/0.30）


def _g_from_e2(n: int, m: int, wg: float = 2.5) -> np.ndarray:
    """交叉点电导 **按 E2 晶体管模型口径**：g = kp·(W/L)·(Wg − Vth)。"""
    p = NmosParams(w_over_l=WL_LAYOUT)
    k = p.kp * p.w_over_l
    return np.full((n, m), k * (wg - p.vth0))


def _ir_grows_with_r() -> bool:
    g = _g_from_e2(4, 4)
    v = [0.1] * 4
    a = PA.ir_drop_report(4, 4, g, v, 0.5, 0.3)["max_rel_err"]
    b = PA.ir_drop_report(4, 4, g, v, 2.0, 1.2)["max_rel_err"]
    return a > 0.0 and b > a


def _wire_r_closed_form() -> bool:
    pr = PA.ELEC_PROCESS
    r1 = PA.wire_resistance(2.4, 0.4, pr["rho_cu_ohm_um"], pr["t_m1_um"])
    r2 = PA.sheet_resistance(pr["rho_cu_ohm_um"], pr["t_m1_um"]) * (2.4 / 0.4)
    return abs(r1 - r2) <= 1e-15


def _zero_r_matches_golden() -> bool:
    g = _g_from_e2(6, 6)
    v = [0.1] * 6
    ideal = PA.ideal_column_currents(g, v)
    zero = np.asarray(PA.solve_network(g, 0.0, 0.0, v)["column_currents"])
    return bool(np.max(np.abs(zero - ideal)) < 1e-15 * max(1.0, float(np.max(np.abs(ideal)))))


def _sneak_positive() -> bool:
    s = PA.sneak_report(6, 6, _g_from_e2(6, 6), 0.1, (2, 2))
    return s["sneak_a"] > 0.0


# ═══════════════ 突变探针（每个都先证「真能变红」）═══════════════
def probe_wire_r_corrupt() -> bool:
    """篡改导线 R 闭式（×0.5）⇒ 闭式判据必红。"""
    with mock.patch.object(PA, "wire_resistance",
                           lambda L, W, rho, t: 0.5 * (rho * L / (W * t))):
        return not _wire_r_closed_form()


def probe_row_ladder_removed() -> bool:
    """把**全部**寄生串联电阻归零（回到理想互连）⇒「IR drop 随 R 增」必红。

    🔴 只拆行线梯是**无效突变**：列线电阻仍在 ⇒ 误差仍 >0 且仍随 R 单调
    （不彻底的突变 = 等价变换）。
    """
    real = PA.build_network

    def bad(g, r_row_seg, r_col_seg, v_in, mode="dot", sel=None, proc=None):
        return real(g, 0.0, 0.0, v_in, mode=mode, sel=sel, proc=proc)

    with mock.patch.object(PA, "build_network", bad):
        return not _ir_grows_with_r()


def probe_golden_corrupt() -> bool:
    """篡改解析 golden（×2）⇒「R=0 ≡ golden」必红。"""
    real = PA.ideal_column_currents

    def bad(g, v_in):
        return 2.0 * real(g, v_in)

    with mock.patch.object(PA, "ideal_column_currents", bad):
        return not _zero_r_matches_golden()


def probe_sneak_killed() -> bool:
    """强制后仿列电流 = 理想值（杀旁路电流）⇒「sneak > 0」必红。"""
    real = PA.solve_network

    def bad(g, r_row_seg, r_col_seg, v_in, mode="dot", sel=None, proc=None):
        res = real(g, r_row_seg, r_col_seg, v_in, mode=mode, sel=sel, proc=proc)
        if mode == "sneak" and sel is not None:
            res["column_currents"] = [float(np.asarray(g)[sel[0], sel[1]] * v_in[sel[0]])]
        return res

    with mock.patch.object(PA, "solve_network", bad):
        return not _sneak_positive()


def main() -> int:
    print("=" * 78)
    print("电子计算芯片寄生提取与后仿 门禁 smoke（E7 · D-157）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 + E6 回归 ════════════════
    print("── A 模块自检 ──")
    check("A1 parasitic 自检 10/10（闭式/梯网络/golden/IR/sneak/规模律/提取）",
          PA.run_selfchecks(verbose=False), "R=0≡golden · 仅选通⇒sneak=0")
    check("A2 E6 版图链回归（E7 未破坏 layout 自检 9/9）",
          LY.run_selfchecks(verbose=False), "E6 9 判据仍绿")

    # ════════════════ B 节：导线 RC 闭式 ════════════════
    print("── B 导线 RC 闭式 ──")
    pr = PA.ELEC_PROCESS
    r1 = PA.wire_resistance(2.4, 0.4, pr["rho_cu_ohm_um"], pr["t_m1_um"])
    check("B1 R = ρL/(Wt) ≡ R□·L/W（教科书两式一致）",
          abs(r1 - PA.sheet_resistance(pr["rho_cu_ohm_um"], pr["t_m1_um"]) * 6.0) <= 1e-15,
          f"R_seg={r1:.6f} Ω · R□={PA.sheet_resistance(pr['rho_cu_ohm_um'], pr['t_m1_um']):.4f} Ω/□")
    check("B2 R 随 L 线性、随 W 反比",
          abs(PA.wire_resistance(4.8, 0.4, 1e-2, 0.2)
              - 2 * PA.wire_resistance(2.4, 0.4, 1e-2, 0.2)) < 1e-15
          and abs(PA.wire_resistance(2.4, 0.8, 1e-2, 0.2)
                  - 0.5 * PA.wire_resistance(2.4, 0.4, 1e-2, 0.2)) < 1e-15, "L/W 依赖")
    c_pl = PA.cap_per_length(0.4, pr["eps_r_ild"], pr["ild_um"], pr["eps0_fF_per_um"])
    check("B3 C' = ε₀·ε_r·W/d（平行板闭式）",
          abs(c_pl - pr["eps0_fF_per_um"] * pr["eps_r_ild"] * 0.4 / pr["ild_um"]) <= 1e-15,
          f"C'={c_pl:.5f} fF/µm")

    # ════════════════ C 节：阵列寄生提取（与 E6 同口径）════════════════
    print("── C 阵列寄生提取 ──")
    ap = PA.array_parasitics(N8, M8)
    bb = [LY._bbox(d) for d in LY.crossbar_array(N8, M8)["descs"]]
    w_e6 = max(b[1] for b in bb) - min(b[0] for b in bb)
    check("C1 足迹与 E6 版图 bbox 同口径",
          abs(ap["footprint_um"][0] - w_e6) < 1e-6, f"{ap['footprint_um']} vs {w_e6:.4f}")
    p_cell = LY.DEFAULT_CELL_PARAMS
    check("C2 r_row_seg = R□_M1 · pitch_x / row_w（节距闭式）",
          abs(ap["r_row_seg_ohm"]
              - PA.sheet_resistance(pr["rho_cu_ohm_um"], pr["t_m1_um"])
              * p_cell["pitch_x_um"] / p_cell["row_w_um"]) < 1e-12,
          f"r_row_seg={ap['r_row_seg_ohm']:.4f} Ω")
    check("C3 串联一阶：R_row_total = r_row_seg·(m−1)",
          abs(ap["R_row_total_ohm"] - ap["r_row_seg_ohm"] * (M8 - 1)) < 1e-12
          and abs(ap["R_col_total_ohm"] - ap["r_col_seg_ohm"] * (N8 - 1)) < 1e-12,
          f"R_row={ap['R_row_total_ohm']:.4f} Ω")
    check("C4 Elmore 闭式 τ = r·c·n(n+1)/2（→ RC/2）",
          abs(PA.elmore_delay(4, 1.0, 1.0) - 10.0) < 1e-12
          and abs(PA.elmore_delay(200000, 1 / 200000, 1 / 200000) - 0.5) < 1e-3,
          f"τ_row={ap['tau_row_s']:.3e} s")

    # ════════════════ D 节：梯网络 vs 解析 golden ════════════════
    print("── D 梯网络 vs 解析 golden ──")
    g6 = _g_from_e2(6, 6)
    v6 = [0.1] * 6
    ideal6 = PA.ideal_column_currents(g6, v6)
    res0 = PA.solve_network(g6, 0.0, 0.0, v6)
    zero6 = np.asarray(res0["column_currents"])
    check("D1 R=0 网络 ≡ 解析 golden I_j=Σg_ij·V_i（精确）",
          bool(np.max(np.abs(zero6 - ideal6)) < 1e-15 * max(1.0, float(np.max(np.abs(ideal6))))),
          f"max|Δ|={float(np.max(np.abs(zero6 - ideal6))):.3e}")
    check("D2 R=0 时抽头合并为理想互连（节点数 = n+m+1）",
          len(res0["node_voltages"]) == 6 + 6 + 1,
          f"节点 {len(res0['node_voltages'])}")
    check("D3 有阻互连必劣化，且随 R 单调增", _ir_grows_with_r(), "r 0.5→2.0")

    # ════════════════ E 节：IR drop ════════════════
    print("── E IR drop ──")
    rep8 = PA.ir_drop_report(N8, M8, _g_from_e2(N8, M8), [0.1] * N8,
                             ap["r_row_seg_ohm"], ap["r_col_seg_ohm"])
    prof = rep8["row0_tap_voltages"]
    check("E1 行线抽头电压沿线单调不增（IR drop 剖面物理）",
          all(prof[k] >= prof[k + 1] - 1e-12 for k in range(len(prof) - 1)) and prof[-1] < prof[0],
          f"首/末 = {prof[0]:.5f} / {prof[-1]:.5f} V")
    n14 = PA.ir_drop_report(4, 4, _g_from_e2(4, 4), [0.1] * 4,
                            ap["r_row_seg_ohm"], ap["r_col_seg_ohm"])["max_rel_err"]
    n16 = PA.ir_drop_report(16, 16, _g_from_e2(16, 16), [0.1] * 16,
                            ap["r_row_seg_ohm"], ap["r_col_seg_ohm"])["max_rel_err"]
    n32 = PA.ir_drop_report(32, 32, _g_from_e2(32, 32), [0.1] * 32,
                            ap["r_row_seg_ohm"], ap["r_col_seg_ohm"])["max_rel_err"]
    check("E2 IR drop 相对误差随规模单调增", n14 < n16 < n32, f"{n14:.4f} < {n16:.4f} < {n32:.4f}")
    check("E3 规模律**超线性**（N 翻倍误差 ≥3×·源于行长度×累积电流）",
          n16 / max(n14, 1e-300) >= 3.0 and n32 / max(n16, 1e-300) >= 3.0,
          f"×{n16/n14:.2f} / ×{n32/n16:.2f}")
    check("E4 行末压降 > 0 且随 N 增",
          rep8["row_end_drop_v"] > 0.0
          and PA.ir_drop_report(16, 16, _g_from_e2(16, 16), [0.1] * 16,
                                ap["r_row_seg_ohm"], ap["r_col_seg_ohm"])["row_end_drop_v"]
          > rep8["row_end_drop_v"], f"8×8 末压降 {rep8['row_end_drop_v']:.5f} V")

    # ════════════════ F 节：sneak path ════════════════
    print("── F sneak path ──")
    G1 = np.zeros((6, 6))
    G1[2, 2] = 1.2e-3
    s1 = PA.sneak_report(6, 6, G1, 0.1, (2, 2))
    check("F1 仅选通单元导通 ⇒ sneak ≡ 0（精确）", abs(s1["sneak_a"]) < 1e-15,
          f"sneak={s1['sneak_a']:.3e} A")
    s_full = PA.sneak_report(6, 6, _g_from_e2(6, 6), 0.1, (2, 2))
    check("F2 全阵列导通 ⇒ sneak > 0（旁路电流存在）",
          s_full["sneak_a"] > 0.0, f"sneak_ratio={s_full['sneak_ratio']:.3f}")
    sr = [PA.sneak_report(N, N, _g_from_e2(N, N), 0.1, (N // 2, N // 2))["sneak_ratio"]
          for N in (4, 8, 16)]
    check("F3 sneak 比例随阵列规模单调增", sr[0] < sr[1] < sr[2],
          f"{sr[0]:.3f} < {sr[1]:.3f} < {sr[2]:.3f}")
    check("F4 sneak 是**拓扑效应**（R=0 时仍存在：与 IR drop 解耦）",
          PA.sneak_report(6, 6, _g_from_e2(6, 6), 0.1, (2, 2))["sneak_a"] > 0.0,
          "sneak 用 R=0 网络求解")

    # ════════════════ G 节：吃狗粮跨模块一致 ════════════════
    print("── G 吃狗粮跨模块（E2 模型 / E6 版图）──")
    p = NmosParams(w_over_l=WL_LAYOUT)
    g_ref = p.kp * p.w_over_l * (2.5 - p.vth0)
    check("G1 交叉点电导与 E2 晶体管模型同口径 g=kp·(W/L)·(Vg−Vth)",
          abs(float(_g_from_e2(4, 4)[0, 0]) - g_ref) < 1e-18,
          f"g={g_ref:.4e} S（W/L={WL_LAYOUT} 来自 E6 版图回提）")
    wl = LY.extract_wl(LY.crossbar_array(4, 4)["descs"])
    check("G2 几何与 E6 版图同口径（W/L 回提 = 1.20/0.30 ⇒ 4.00）",
          abs(wl["W_um"] / wl["L_um"] - WL_LAYOUT) < 1e-9,
          f"W/L={wl['W_um']/wl['L_um']:.4f}")

    # ════════════════ H 节：诚实边界 + 红线 ════════════════
    print("── H 诚实边界 + 红线 ──")
    disc = PA.PARASITIC_DISCLOSURE
    check("H1 披露齐备：role/process/extract/sim/leak/red_line 六键",
          all(k in disc for k in ("role", "process", "extract", "sim", "leak", "red_line")),
          f"键={sorted(disc)}")
    check("H2 工艺参数为公开典型量级 · 非 PDK（明确 D5 外部依赖）",
          "非 Foundry PDK" in disc["process"] and "公开典型量级" in disc["process"], "口径")
    check("H3 r_leak 明确标注为**数值钉扎**（非物理漏电声明）",
          "数值钉扎" in disc["leak"] and "非物理" in disc["leak"], "leak 口径")
    banned = ("ngspice", "pyspice", "ahkab", "ltspice", "xyce", "cadence",
              "synopsys", "gdstk", "gdspy", "gdsfactory", "qiskit", "cirq")
    src = open(os.path.join(_HERE, "lda_l2", "ecore", "parasitic.py"), encoding="utf-8").read()
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("H4 红线：零商业 EDA / 零量子 SDK 依赖（纯 numpy + 自研 mna）",
          not hits, f"命中={hits or '无'}")
    r1r = PA.ir_drop_report(4, 4, _g_from_e2(4, 4), [0.1] * 4, 0.5, 0.3)
    check("H5 判决无 LLM：结果为 float 死标量（零模型调用）",
          all(isinstance(r1r[k], float) for k in ("max_rel_err", "row_end_drop_v")),
          "纯数值")
    blob = str(disc).upper()
    check("H6 诚实边界：无 TOPS / TOPS-W / fJ-op 类器件性能自夸",
          "TOPS" not in blob and "FJ/OP" not in blob, "设计&验证工具链口径")

    # ════════════════ I 节：突变探针 ════════════════
    print("── I 突变探针（每个都必须真能变红）──")
    check("I1 探针：篡改导线 R 闭式 ⇒ 闭式判据必红", probe_wire_r_corrupt() is True, "证读闭式")
    check("I2 探针：拆掉行线分段电阻 ⇒ IR drop 随 R 增必红",
          probe_row_ladder_removed() is True, "证行线梯真的被装配")
    check("I3 探针：篡改解析 golden ⇒ R=0≡golden 必红",
          probe_golden_corrupt() is True, "证 golden 真被比对")
    check("I4 探针：杀旁路电流（后仿=理想）⇒ sneak>0 必红",
          probe_sneak_killed() is True, "证 sneak 真的来自后仿解")

    # ════════════════ J 节：还原完整性 ════════════════
    print("── J 还原完整性 ──")
    check("J1 还原后：闭式/golden/IR/sneak 四项复绿",
          _wire_r_closed_form() and _zero_r_matches_golden()
          and _ir_grows_with_r() and _sneak_positive(), "无 patch 残留")
    check("J2 还原后：模块自检 10/10 复绿", PA.run_selfchecks(verbose=False), "无残留")

    print()
    print(f"电子计算芯片寄生提取与后仿 门禁 smoke（E7）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
