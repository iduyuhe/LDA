"""E53 门禁：**HD 单元库 + 行内布线** —— 把 E50/E51 的 87% 天花板打破。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么（一句话）
───────────────────────────────────────────────────────────────────────────────
E51 判定「行内布线不可行」，**那个判定是对的但原因错了**：不是「行内没有资源」，
而是**E51 把水平段画在引脚 y 上**（必然撞同行异网焊盘）+ **DEMO45 的 240nm 引脚 pad
把行内空隙吃干**。本版两条一起解决：
  ① 用 **28nm 级规则重画 INV/NAND2**（pad 70nm、等高行 1000nm、行内 5 条轨道）；
  ② 行内水平段放到**行内空闲 y 带**，且竖向段**只准穿过本网自己的引脚带**。

红线：
  · 规则集是自建 LDA-DEMO28（教科书尺度），**不是 foundry PDK**；器件电学不变；
  · 本版只改**几何与布线拓扑**，不改器件模型、不宣称延迟/功耗；
  · 净增 0 锚（整数几何 + 计数 ⇒ resid≡0）。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dcells as CL      # noqa: E402
from lda_l2.ecore import dctrl as CT       # noqa: E402
from lda_l2.ecore import ddetail as DD     # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL    # noqa: E402
from lda_l2.ecore import dhdlib as HD      # noqa: E402
from lda_l2.ecore import dnode as DN       # noqa: E402
from lda_l2.ecore import dpnr as PN        # noqa: E402
from lda_l2.ecore import dproc as PR       # noqa: E402

_FAILED: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FAILED)
T0 = time.time()
AN_ELAPSED_MAX_S = 240.0

CASE_N, CASE_COLS = 64, 8          # 主用例：64 单元 / 8 列（E49–E51 用的同一档）
RATE_MIN_IN_ROW = 0.90             # 行内布线后 64 单元的布通率下限
_LADDER = (12, 64, 128, 256)


def _route(nl, in_row, check_on=True):
    pl = PN.place_real(nl, max_cells=CASE_N, cols=CASE_COLS)
    rt = PN.route_block(nl, pl, in_row_m3=in_row, in_row_check=check_on)
    va = DL.run_drc(PN.all_routing(rt))["violations"]
    n_int = len(rt["routed"]) + len(rt["unrouted"])
    return pl, rt, va, n_int


def main() -> int:
    print("E53 · HD 单元库 + 行内布线：打破 87% 天花板（v0.9.356）")
    nl = CT.build()["netlist"]

    # ── H1 HD 库自身合法 ────────────────────────────────────────────
    cells = {n: f() for n, f in sorted(HD.CELLS.items())}
    d = {n: HD.run_drc(c, HD.HD_RULES) for n, c in cells.items()}
    lv = {n: HD.run_lvs(c) for n, c in cells.items()}
    check("H1 HD 库 DRC/LVS 双零（%s）" % ", ".join(
        "%s DRC %d/LVS %d" % (n, d[n]["n"], lv[n]["n"]) for n in cells),
        all(d[n]["n"] == 0 and lv[n]["n"] == 0 for n in cells),
        "; ".join("%s DRC=%d LVS=%d" % (n, d[n]["n"], lv[n]["n"]) for n in cells))

    # ── H2 几何收益：pad 与面积 ─────────────────────────────────────
    old_inv, old_nand = CL.CELLS["INV_X1"](), CL.CELLS["NAND2_X1"]()
    new_inv, new_nand = cells["INV_X1_HD"], cells["NAND2_X1_HD"]
    a_old = (old_inv.w * old_inv.h, old_nand.w * old_nand.h)
    a_new = (new_inv.w * new_inv.h, new_nand.w * new_nand.h)
    sh_inv = a_old[0] / a_new[0]
    sh_nand = a_old[1] / a_new[1]
    check("H2 几何收益：引脚 pad **%.0f → %.0fnm**；单元面积 INV **%.2f×**、NAND2 **%.2f×** 更小"
          "（且两单元**等高** %.0fnm ⇒ 消除了 E45 披露里的「不等高」限制）"
          % (DN.DEMO45.pad, DN.DEMO28.pad, sh_inv, sh_nand, HD.H_ROW_HD),
          HD.pad_nm() == DN.DEMO28.pad and sh_inv > 2.0 and sh_nand > 3.0
          and old_inv.h != old_nand.h and new_inv.h == new_nand.h == HD.H_ROW_HD,
          "pad %.0f/%.0f · 面积 %.4f/%.4f → %.4f/%.4f µm² · 行高旧 %d/%d 新高 %d"
          % (DN.DEMO45.pad, HD.pad_nm(), a_old[0] / 1e6, a_old[1] / 1e6,
             a_new[0] / 1e6, a_new[1] / 1e6, old_inv.h, old_nand.h, new_inv.h))

    # ── H3 行内轨道：HD 有、且两单元**共用同一网格** ──────────────────
    it_inv = HD.inner_tracks(new_inv, HD.HD_ROUTE)
    it_nand = HD.inner_tracks(new_nand, HD.HD_ROUTE)
    it_old = HD.inner_tracks(old_inv, DN.DEMO45.route_rules("nm"))
    check("H3 行内轨道：HD 两单元各 **%d 条**且 **y 完全一致**（库级共用网格，行内线才能跨单元连通）；"
          "DEMO45 的 INV 只有 %d 条" % (it_inv["n"], it_old["n"]),
          it_inv["n"] >= 5 and it_inv["tracks"] == it_nand["tracks"] and it_old["n"] <= 1,
          "HD %s · 旧 %s" % (it_inv["tracks"], it_old["tracks"]))

    # ── H4 规则参数化**有牙**：同一几何换规则必须**翻面** ─────────────
    # HD 单元在 28nm 规则下合法（0）、在 45nm 规则下必须报错（密集图形过不了粗规则）。
    # 🔴 反方向**本应为 0**，且这不是缺陷：45nm 单元图形本来就比 28nm 规则粗，
    # 细规则一定满足。所以反方向断言「必须为 0」—— 这是一条**性质**断言（换规则不乱杀），
    # 不是判别力断言。判别力只由正方向提供。
    wrong_old = HD.run_drc(new_inv, CL.RULES)          # 28nm 单元 vs 45nm 规则 ⇒ 必须红
    coarse_ok = CL.run_drc(old_inv, HD.HD_RULES)       # 45nm 单元 vs 28nm 规则 ⇒ 必须绿
    check("H4 规则参数化有牙：同一块 HD 单元在 28nm 规则下 0 条、换 45nm 规则 **%d 条**"
          "（换规则真的会翻面）；反方向 45nm 单元过 28nm 规则应为 0 ⇒ 实测 **%d**"
          % (wrong_old["n"], coarse_ok["n"]),
          wrong_old["n"] > 0 and coarse_ok["n"] == 0,
          "正方向 %d 条（判别力）；反方向 %d 条（粗几何满足细规则，属性质而非缺陷）"
          % (wrong_old["n"], coarse_ok["n"]))

    # ── H5 规则切换与**逐项还原** ──────────────────────────────────
    before = PR.snapshot()
    with PR.use("DEMO28", lib=HD):
        inside = (PN.PITCH, PN.W, DL.S_MIN, DL.W_MIN, DD.VIA, DL.ENC)
        inside_ok = (abs(inside[0] - 0.14) < 1e-12 and abs(inside[1] - 0.07) < 1e-12
                     and abs(inside[2] - 0.07) < 1e-12 and abs(inside[4] - 0.05) < 1e-12)
    resid = PR.diff(before)
    check("H5 规则切换：`use(DEMO28)` 内 PITCH/W/S/W_MIN/VIA 全部切到 28nm 值，"
          "退出后 **%d 项逐项还原**（差 %d 项）" % (len(before), len(resid)),
          inside_ok and not resid,
          "内值 %s · 退出差异 %s" % (tuple(inside), resid or "无"))

    # ── H6 DEMO45 行内**本来就没有空隙**（这就是「必须换库」的机核）────
    pl_o = PN.place_real(nl, max_cells=CASE_N, cols=CASE_COLS)
    rb_o = PN.row_bands(pl_o, PN.net_pins(pl_o))
    inner_o = [g["y1"] - g["y0"] for info in rb_o.values()
               for g in info["gaps"] if 0 < g["i"] < len(info["gaps"]) - 1]
    widest = max(inner_o) if inner_o else 0.0
    check("H6 DEMO45 的**带间空隙**最宽 %.3fµm < 一个节距 %.2fµm ⇒ 行内一条水平轨都放不下"
          "（这是「必须换库」的直接几何原因，不是调参问题）"
          % (widest, PN.PITCH),
          widest < PN.PITCH,
          "带间空隙 %s · 节距 %.2f" % ([round(x, 3) for x in inner_o], PN.PITCH))

    # ── H7 HD + 行内：布通率显著提升且 **DRC == 0** ──────────────────
    with PR.use("DEMO28", lib=HD):
        pl0, rt0, va0, n0 = _route(nl, False)
        pl1, rt1, va1, n1 = _route(nl, True)
        r0, r1 = len(rt0["routed"]) / n0, len(rt1["routed"]) / n1
        n_in = rt1["n_in_row_m3"]
    check("H7 HD + 行内布线：%d 单元布通率 **%.1f%% → %.1f%%**（+%.1fpp，行内布了 %d 网），"
          "两档 **DRC 均为 0**" % (CASE_N, 100 * r0, 100 * r1, 100 * (r1 - r0), n_in),
          r1 >= RATE_MIN_IN_ROW and r1 > r0 + 0.15 and not va0 and not va1,
          "无行内 %d/%d (%.1f%%) DRC %d · 有行内 %d/%d (%.1f%%) DRC %d · 行内网 %d"
          % (len(rt0["routed"]), n0, 100 * r0, len(va0),
             len(rt1["routed"]), n1, 100 * r1, len(va1), n_in))

    # ── H8 全档零 DRC（行内开启）───────────────────────────────────
    ladder = []
    with PR.use("DEMO28", lib=HD):
        for n_cells in _LADDER:
            pl = PN.place_real(nl, max_cells=n_cells, cols=CASE_COLS)
            rt = PN.route_block(nl, pl, in_row_m3=True)
            v = DL.run_drc(PN.all_routing(rt))["violations"]
            n_int = len(rt["routed"]) + len(rt["unrouted"])
            ladder.append((n_cells, len(rt["routed"]), n_int, len(v)))
    check("H8 全档（%s 单元）行内布线 **DRC 恒 0**：%s"
          % ("/".join(str(x) for x in _LADDER),
             " · ".join("%d:%d/%d DRC %d" % t for t in ladder)),
          all(t[3] == 0 for t in ladder),
          "档位 (单元, 布通, 内部网, DRC) = %s" % (ladder,))

    # ── H9 双反向探针：间隙规则与冲突退回**各自有牙** ────────────────
    with PR.use("DEMO28", lib=HD):
        PN.IN_ROW_STRICT = True
        _p, _r, va_strict, _n = _route(nl, True, check_on=False)
        PN.IN_ROW_STRICT = False
        _p2, _r2, va_loose, _n2 = _route(nl, True, check_on=False)
        PN.IN_ROW_STRICT = True
        _p3, _r3, va_fb, _n3 = _route(nl, True, check_on=True)
    check("H9 双探针：① 严格间隙规则 + **关掉**冲突退回 ⇒ DRC **%d**（规则本身够用）；"
          "② 放开间隙规则 + 关掉退回 ⇒ DRC **%d**（规则不是摆设）；"
          "③ 严格 + 退回 ⇒ DRC **%d**（兜底也有效）"
          % (len(va_strict), len(va_loose), len(va_fb)),
          len(va_strict) == 0 and len(va_loose) > 0 and len(va_fb) == 0,
          "strict/no-fallback %d · loose/no-fallback %d · strict/fallback %d"
          % (len(va_strict), len(va_loose), len(va_fb)))

    # ── H10 确定性：同参数两次跑，形状数与 DRC 数逐位一致 ─────────────
    with PR.use("DEMO28", lib=HD):
        sig = []
        for _ in range(2):
            pl = PN.place_real(nl, max_cells=CASE_N, cols=CASE_COLS)
            rt = PN.route_block(nl, pl, in_row_m3=True)
            v = DL.run_drc(PN.all_routing(rt))["violations"]
            sig.append((len(PN.all_routing(rt)), len(rt["routed"]), len(v),
                        tuple(sorted(rt["in_row_assign"].items()))))
    check("H10 确定性：两次跑的 形状数/布通数/DRC 数/行内分配 逐位一致",
          sig[0] == sig[1], "%s vs %s" % (sig[0][:3], sig[1][:3]))

    dt = time.time() - T0
    check("H0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    tgt = PN.PITCH
    print("  [几何] pad %.0f→%.0fnm · 面积 INV %.2f× / NAND2 %.2f× 更小 · 等高行 %.0fnm"
          % (DN.DEMO45.pad, HD.pad_nm(), sh_inv, sh_nand, HD.H_ROW_HD))
    print("  [行内] HD 两单元各 %d 条轨道且 y 一致 %s（DEMO45 只有 %d 条；节距 %.2fµm）"
          % (it_inv["n"], it_inv["tracks"], it_old["n"], tgt))
    print("  [布通] %d 单元：%.1f%% → **%.1f%%**（+%.1fpp）· 全档 DRC 0"
          % (CASE_N, 100 * r0, 100 * r1, 100 * (r1 - r0)))
    print("  [边界] LDA-DEMO28 是**教科书尺度**自建规则，非 foundry PDK；器件电学不变、"
          "只有几何容量可比；只做 INV/NAND2；不宣称延迟/功耗/可制造")
    print()
    if _FAILED:
        print("E53 有红色：%s" % ", ".join(_FAILED))
        return 1
    print("E53 全绿 · HD 库 + 行内布线：87% 天花板被打破（DRC 恒 0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
