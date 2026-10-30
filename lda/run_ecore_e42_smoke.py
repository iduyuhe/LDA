#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E42 门禁：**B3 签核级提取/时序骨架** —— 提取加 C + 多角（tt/ff/ss）+ IR/EM。

## 本门禁守什么
B1 只有 R，B2 只有布通。没有 C 就没有延迟；只有 tt 就看不见工艺波动；没有 IR/EM 电源网
在签核里就不存在。B3 把这三件补成一阶、**可两法互证**的骨架：

| # | 守护 | 金标 |
|---|---|---|
| B1 | 电容提取闭合 | C 对长度**严格线性**（L×2 ⇒ C×2）· 逐段求和 ≡ 总长闭式 · 对宽度单调 |
| B2 | 多角（两侧都验） | ff<tt<ss 严格；`C_load=0` 时比值 == `kr·kc`；`C_load≫C` 时比值 == `kr` |
| B3 | Elmore 互证 | 梯形解 n→∞ 收敛到闭式 `R(C/2+C_load)`；n=1 精确等于 `R(C+C_load)`；误差随 n 单调降 |
| B4 | IR 互证 + 标度 | 闭式 `I·R/2` ⇄ 离散解（n=100 相对差 <1%）；L×2⇒×2、W×2⇒×0.5 |
| B5 | EM 判定 + 判别力 | `J=I/(w·t)` 精确；标称通过；电流×2 ⇒ 必红 |
| B6 | 反向探针（抹平必红） | 把三角系数全设为 (1,1) ⇒ 延迟区间宽度归零 ⇒ B2 的判据必红 |
| B7 | 与 B2 集成 | 用 B2 实布形状做真实提取：R>0 ∧ C>0 ∧ 三角严格有序 ∧ 区间宽度>0 |
| B8 | 确定性 | 两次计算逐字节一致 |
| B0 | 耗时 | < 阈值 |

## 诚实口径
- **不是 signoff**：一阶解析模型；真实签核需要 foundry ITF/3D 场/SPEF/PVT/EM 规则表/硅实测，
  这些本项目**一件都没有**（见 `dsignoff.B3_DISCLOSURE.missing_for_real_signoff`）。
- 多角系数与 `J_MAX` 是**演示量级假设**，不是工艺认证数据。
- **净增 0 锚**（闭式算术）⇒ 门禁形态（同 E39/E40/E41）；不报 TOPS/fJ/能效。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dsignoff as SG        # noqa: E402
from lda_l2.ecore import dcroute as RT         # noqa: E402
from lda_l2.ecore import ddetail as DD         # noqa: E402
from lda_harness.smoke_kit import make_check   # noqa: E402

AN_ELAPSED_MAX_S = 60.0

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)

_LAYER = {DD.L_M3: "M3", DD.L_M4: "M4"}


def main():
    t0 = time.time()
    print("=" * 78)
    print("E42 · B3 签核级提取/时序骨架（C 提取 + 多角 + IR + EM）")
    print("=" * 78)

    # ── B1 电容：线性 + 逐段求和 ≡ 总长闭式 + 宽度单调 ────────────────
    c1 = SG.wire_c(5.0, 0.24)
    c2 = SG.wire_c(10.0, 0.24)
    seg_sum = sum(SG.wire_c(L, 0.24) for L in (2.0, 3.0, 5.0))
    whole = SG.wire_c(10.0, 0.24)
    cw1 = SG.wire_c(5.0, 0.24)
    cw2 = SG.wire_c(5.0, 0.48)
    check("B1 电容提取：L×2 ⇒ C×2（严格线性）∧ 逐段求和 ≡ 总长闭式 ∧ 对宽度单调",
          abs(c2 - 2.0 * c1) < 1e-12 * max(1.0, c2)
          and abs(seg_sum - whole) < 1e-12 * max(1.0, whole)
          and cw2 > cw1,
          "c1=%.6f c2=%.6f segsum=%.6f whole=%.6f" % (c1, c2, seg_sum, whole))

    # ── B2 多角：两侧都验（C 主导区 vs C_load 主导区）─────────────────
    rc_wire = {"r_ohm": SG.wire_r(10.0, 0.24), "c_ff": SG.wire_c(10.0, 0.24)}
    tbl = SG.corner_table(rc_wire)
    d = tbl["delay_fs"]
    order_ok = d["ff"] < d["tt"] < d["ss"]
    # ① C_load = 0 ⇒ 延迟 ∝ kr·kc
    kr_ff, kc_ff = SG.CORNERS["ff"]
    r0 = SG.delay_at_corner(rc_wire, "ff", c_load_ff=0.0) / SG.delay_at_corner(
        rc_wire, "tt", c_load_ff=0.0)
    prod_ok = abs(r0 - kr_ff * kc_ff) < 1e-12
    # ② C_load 极大 ⇒ 延迟 ∝ kr（电容被负载淹没）
    big = 1e6
    r1 = SG.delay_at_corner(rc_wire, "ss", c_load_ff=big) / SG.delay_at_corner(
        rc_wire, "tt", c_load_ff=big)
    kr_ss, _kc_ss = SG.CORNERS["ss"]
    load_ok = abs(r1 - kr_ss) < 1e-6
    check("B2 多角：ff<tt<ss 严格 ∧ C 主导区比值==kr·kc ∧ 负载主导区比值==kr（两侧都验）",
          order_ok and prod_ok and load_ok,
          "order=%s ratio0=%.6f want=%.6f ratioBig=%.6f want=%.6f"
          % (order_ok, r0, kr_ff * kc_ff, r1, kr_ss))

    # ── B3 Elmore：n=1 精确、收敛到闭式、误差随 n 单调降 ──────────────
    R, C = rc_wire["r_ohm"], rc_wire["c_ff"]
    cl = SG.C_LOAD_FF
    exact_n1 = SG.elmore_ladder(R, C, 1, cl)
    want_n1 = R * (C + cl)
    closed = SG.elmore_closed(R, C, cl)
    errs = [abs(SG.elmore_ladder(R, C, n, cl) - closed) for n in (1, 2, 4, 8, 16)]
    mono = all(errs[i] > errs[i + 1] for i in range(len(errs) - 1))
    check("B3 Elmore 互证：n=1 精确 == R(C+C_load) ∧ 误差随 n 单调降 ∧ n=16 后 <5%",
          abs(exact_n1 - want_n1) < 1e-12 * max(1.0, want_n1) and mono
          and errs[-1] < 0.05 * closed,
          "n1=%.6f want=%.6f closed=%.6f errs=%s"
          % (exact_n1, want_n1, closed, [round(e, 6) for e in errs]))

    # ── B4 IR：闭式 ⇄ 离散 + L/W 标度 ───────────────────────────────
    i_tot, rsh, L, Wd = 1e-3, 0.12, 100.0, 1.0
    v_closed = SG.ir_drop_closed(i_tot, rsh, L, Wd)
    v_lad = SG.ir_drop_ladder(i_tot, rsh, L, Wd, 200)
    rel = abs(v_lad - v_closed) / v_closed
    scale_ok = (abs(SG.ir_drop_closed(i_tot, rsh, 2 * L, Wd) - 2 * v_closed) < 1e-15
                and abs(SG.ir_drop_closed(i_tot, rsh, L, 2 * Wd) - v_closed / 2) < 1e-15)
    check("B4 IR：闭式 I·R/2 ⇄ 离散 n=200（相对差<1%）∧ L×2⇒×2 ∧ W×2⇒×0.5",
          rel < 0.01 and scale_ok, "closed=%.9f ladder=%.9f rel=%.2e" % (v_closed, v_lad, rel))

    # ── B5 EM：公式精确 + 标称通过 + 电流×2 必红 ────────────────────
    e1 = SG.em_check(2e-4, 0.24)
    e2 = SG.em_check(4e-4, 0.24)
    want_j = 2e-4 / ((0.24e-6) * (SG.T_METAL_UM * 1e-6))
    check("B5 EM：J=I/(w·t) 精确 ∧ 标称通过 ∧ 电流×2 ⇒ 必红",
          abs(e1["j_a_m2"] - want_j) < 1e-6 * want_j and e1["ok"] and not e2["ok"],
          "J=%.4e margin=%.3f ok=%s | 2I ok=%s" % (e1["j_a_m2"], e1["margin_x"], e1["ok"], e2["ok"]))

    # ── B6 反向探针：抹平多角 ⇒ 区间宽度归零（判据有牙）──────────────
    saved = dict(SG.CORNERS)
    try:
        for k in SG.CORNERS:
            SG.CORNERS[k] = (1.0, 1.0)
        flat = SG.corner_table(rc_wire)
    finally:
        SG.CORNERS.clear()
        SG.CORNERS.update(saved)
    check("B6 反向探针：把三角系数抹平 ⇒ 延迟区间宽度归零（多角判据确实有牙）",
          flat["max_fs"] == flat["min_fs"] and flat["spread_pct"] == 0.0,
          "flat spread=%s%% · 恢复后 spread=%s%%" % (flat["spread_pct"], tbl["spread_pct"]))

    # ── B7 与 B2 集成：用真实布出的形状做提取 ───────────────────────
    case = RT.build_case()
    routed = RT.route(case)
    per_net = {}
    for n in case["nets"]:
        per_net[n["name"]] = SG.net_rc(routed["shapes"], lambda L: _LAYER.get(L, "?"), n["name"])
    ok7 = all(v["r_ohm"] > 0 and v["c_ff"] > 0 and v["n_seg"] >= 3 for v in per_net.values())
    tables = {k: SG.corner_table(v) for k, v in per_net.items()}
    tbl_ok = all(t["delay_fs"]["ff"] < t["delay_fs"]["tt"] < t["delay_fs"]["ss"]
                 and t["max_fs"] > t["min_fs"] for t in tables.values())
    worst = max(tables.items(), key=lambda kv: kv[1]["max_fs"])
    check("B7 与 B2 集成：真实布出形状提取 R>0 ∧ C>0 ∧ 三角严格有序 ∧ 区间宽度>0",
          ok7 and tbl_ok,
          "worst=%s max=%.4ffs spread=%.2f%%"
          % (worst[0], worst[1]["max_fs"], worst[1]["spread_pct"]))

    # ── B8 确定性 ─────────────────────────────────────────────────
    def sig():
        c = RT.build_case()
        r = RT.route(c)
        v = SG.net_rc(r["shapes"], lambda L: _LAYER.get(L, "?"), "n0")
        return (round(v["r_ohm"], 12), round(v["c_ff"], 12),
                tuple(round(x, 9) for x in SG.corner_table(v)["delay_fs"].values()))
    check("B8 确定性：两次提取/三角计算逐字节一致", sig() == sig())

    dt = time.time() - t0
    check("B0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)

    # 诚实边界必须写到输出（对外可见）
    miss = SG.B3_DISCLOSURE.get("missing_for_real_signoff") or []
    print("  [诚实边界] 距真正 signoff 仍缺 %d 项：%s" % (len(miss), "；".join(miss[:3]) + " …"))

    print("-" * 78)
    print("E42 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E42 签核骨架（C/多角/IR/EM）出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E42 全绿 · 一阶签核骨架：C 提取（线性+逐段≡闭式）· 多角两侧都验 · Elmore 互证 · "
          "IR 闭式≡离散 · EM 有牙 · 净增 0 锚（**不是 signoff**，见披露清单）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
