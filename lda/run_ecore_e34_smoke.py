#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E34 门禁（D-216）：**数字控制壳自主建** —— 六层自主数字链 + 一条真实设计。

## 本门禁守什么

E34 之前电子域**完全不存在数字链**（不是「薄」而是「0」）。本段自建六层：
单元库 → Verilog 前端 → AIG → 综合 → STA → 等价性，并用它们设计一颗 CIM 控制壳。

| # | 守护对象 | 为什么必须单独守 |
|---|---|---|
| B1 | 单元库拓扑锚（`n_tr` 公式 · 族内 `k_drive` 单调 · 真值表长度） | 面积/延时全靠它，它错全错 |
| B2 | 前端三条语义（`~0`=32 位 · 位宽上下文 · 非阻塞读旧值） | 三条都是 E34 自己踩过的坑 |
| B3 | 五个构造用例**全穷举**等价比对 | 唯一不依赖任何工艺参数的绝对判据 |
| B4 | **响应率 ρ ≥ 0.8**（单门扰动被抓住的比例） | ρ 低 = 判据没判别力，绿也不算数 |
| B5 | 三个对照组**必须打红**（常数/直通/单门） | 证明判据不是恒绿 |
| B6 | STA 三条独立路径逐位相等（<1e-12） | 图传播 vs 逐级累加 vs 代数相乘 |
| B7 | 控制壳锁步 1500 拍零失配（24000 次输出比对） | 随机向量对 70 位输入等于零覆盖 |
| B8 | 累加器 18 位**双向**判据（18 够 ∧ 17 不够） | 只证「够」对「随便给宽位」永远绿 |
| B9 | 数字壳 Fmax vs SAR 时钟的闭环 | 应用促平台：数字会不会成为真瓶颈 |
| B10 | 两次综合逐位一致（确定性） | 图遍历/集合序/哈希序的隐式不确定 |

## 探针要求

4 个突变探针（C1–C4），**每个都必须打红**。它们对应的都是本段**真实发生过**的缺陷：
C1 = 改拓扑锚；C2 = 砍掉位宽上下文；C3 = 反向比较器；C4 = 非阻塞退化成阻塞。
把踩过的坑变成探针，是为了不再犯第二次 —— 也为了证明判据**有判别力**。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dcell as DC          # noqa: E402
from lda_l2.ecore import dctrl as CT          # noqa: E402
from lda_l2.ecore import dequiv as Q          # noqa: E402
from lda_l2.ecore import drtl as RT           # noqa: E402
from lda_l2.ecore import dsta as ST           # noqa: E402
from lda_l2.ecore import dsynth as SY         # noqa: E402
from lda_l2.ecore.daig import Aig             # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

# ---------------------------------------------------------------------------
# 关键事实锚（**全部现算可复现**；`==` 只用于精确已知量）
# ---------------------------------------------------------------------------
AN_DFF = 56                    # 控制壳状态位总数 = 3+7+3+18+18+5+1+1（声明决定，精确）
AN_ACC_WIDTH = 18              # 累加器位宽（⌈log2(177480+1)⌉，精确）
AN_MAX_SUM = 177480            # 87×8×255（精确）
AN_ZERO = 0.0                  # 0 级链延时（「本应恰好为 0」的对照组）
AN_REL_TOL = 1e-12             # 三条路径金标相对误差上限
AN_RHO_MIN = 0.80              # 响应率下限
AN_GATES_MIN = 1000            # 控制壳组合门数下界（防「综合器什么都没做」）
AN_LOCKSTEP = 1500             # 锁步拍数
AN_ELAPSED_MAX_S = 600.0       # 本门禁耗时上界（实测见末行，留 5× 余量）

#: 🔴 **不写本地 `def check`**：`run_helper_dup_ratchet_smoke` 的 J3 明确要求新门禁
#: 复用 `smoke_kit.make_check`（本地重复实现正是它红了 5 版无人知的根因）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


_T0 = time.perf_counter()


def elapsed():
    return time.perf_counter() - _T0


# ---------------------------------------------------------------------------
# B1 单元库拓扑锚
# ---------------------------------------------------------------------------
def b1_library():
    r = DC.library_self_check()
    check("B1  单元库结构自检（真值表长度 / n_tr 拓扑公式 / k_drive 族内单调 / "
          "PMOS 劣于 NMOS）", r["ok"], r["problems"][:3])
    # 拓扑必然锚：4 个数字逐位钉死（不是拟合）
    check("B1a 拓扑锚 INV=2T / NAND2=4T / NOR2=4T / DFF=24T",
          (DC.CELLS["INV"].n_tr, DC.CELLS["NAND2"].n_tr,
           DC.CELLS["NOR2"].n_tr, DC.CELLS["DFF"].n_tr) == (2, 4, 4, 24))
    check("B1b 金标 0 级链延时恰为 0（本应恰好为 0 的对照组）",
          DC.chain_golden_ps("INV", 0, 4.0) == AN_ZERO)

    # 🔴 C1 探针：把 NAND2 的 n_tr 从 4 改成 40 ⇒ 拓扑锚判据**必须**红
    old = DC.CELLS["NAND2"]
    DC.CELLS["NAND2"] = DC.Cell(name="NAND2", n_in=2, n_tr=40,
                                table=old.table, n_series=2, k_drive=old.k_drive,
                                pins=old.pins, family=old.family)
    try:
        r2 = DC.library_self_check()
        check("C1  探针：NAND2 的 n_tr 4→40 ⇒ 拓扑锚**必须打红**", not r2["ok"],
              r2["problems"][:2])
    finally:
        DC.CELLS["NAND2"] = old


# ---------------------------------------------------------------------------
# B2 前端三条语义
# ---------------------------------------------------------------------------
def b2_frontend():
    r = RT.drtl_self_check()
    check("B2  Verilog 子集前端自检（~0 是 32 位 / 位宽上下文 / 非阻塞读旧值）",
          r["ok"], r["problems"][:3])

    # 🔴 C2 探针：砍掉位宽上下文传播 ⇒ 4 位加法的进位必须丢（15+1 得 0）
    orig = RT.ev

    def no_ctx(a, env, widths, ctx=0):
        return orig(a, env, widths, 0)

    RT.ev = no_ctx
    try:
        bad = RT.drtl_self_check()
        check("C2  探针：丢掉位宽上下文传播 ⇒ 加法器进位丢失**必须打红**",
              not bad["ok"], bad["problems"][:2])
    finally:
        RT.ev = orig


# ---------------------------------------------------------------------------
# B3/B4/B5 等价性绝对判据 + 响应率 + 对照组
# ---------------------------------------------------------------------------
def b3_equiv():
    rows = []
    for name, src in Q._CASES.items():
        m = RT.parse(src)
        nl = SY.synth(m)
        au = SY.netlist_authenticity(nl, m)
        check("B3  用例 %-10s 网表真实性（单元驱动 / DFF 数 / 无前向引用）" % name,
              au["ok"], au["problems"][:2])
        r = Q.equiv(m, nl)
        check("B3  用例 %-10s 双引擎穷举/抽样等价（%d 向量 · exhaustive=%s）"
              % (name, r["n_vectors"], r["exhaustive"]), r["ok"],
              r["mismatches"][:1])
        rr = Q.rho(m, nl)
        rows.append((name, r["n_vectors"], r["exhaustive"], rr["rho"]))
        check("B4  用例 %-10s 响应率 ρ=%.3f ≥ %.2f（判据有判别力）"
              % (name, rr["rho"], AN_RHO_MIN), rr["rho"] >= AN_RHO_MIN, rr)
    # 至少有一个用例是**真穷举**
    check("B3c 至少三个用例是真穷举（不是全靠随机抽样）",
          sum(1 for x in rows if x[2]) >= 3,
          [(x[0], x[1], x[2]) for x in rows])

    # ---- 三个对照组必须打红 ----
    m = RT.parse(Q._CASES["adder4"])
    nl = SY.synth(m)
    i0 = [i for i, g in enumerate(nl.gates) if g.cell == "NAND2"][0]
    check("B5a 对照组：输出全接常数 0 ⇒ 等价性**必须红**",
          not Q.equiv(m, Q.Netlist(name="c0", inputs=nl.inputs,
                                   in_nets=dict(nl.in_nets),
                                   outputs={p: ("TIE0",) * len(nl.outputs[p])
                                            for p in nl.outputs},
                                   gates=[Q.Gate("TIE0", "TIELO", (), "TIE0")],
                                   clocks=nl.clocks))["ok"])
    check("B5b 对照组：输出直通输入 ⇒ 等价性**必须红**",
          not Q.equiv(m, Q.Netlist(name="pt", inputs=nl.inputs,
                                   in_nets=dict(nl.in_nets),
                                   outputs={"y": tuple("in_a_%d" % i for i in range(4))
                                            + ("TIE0",)},
                                   gates=[Q.Gate("TIE0", "TIELO", (), "TIE0")],
                                   clocks=nl.clocks))["ok"])
    check("B5c 对照组：单门扰动（NAND2→NOR2）⇒ 等价性**必须红**",
          not Q.equiv(m, Q._mutate(nl, i0, "NOR2"))["ok"])


# ---------------------------------------------------------------------------
# B6 STA 三条独立路径
# ---------------------------------------------------------------------------
def b6_sta():
    r = ST.sta_self_check()
    check("B6  STA 三条独立路径逐位相等（图传播 / 逐级累加 / 代数相乘 · rel<%.0e）"
          % AN_REL_TOL, r["ok"], r["problems"][:2])
    # 显式再算一次绝对值（防「三条都错但错得一样」——它们不共享代码，但仍并报绝对值）
    n = 17
    nl = ST.build_chain_nl("INV", n, 1.0)
    t = ST.sta(nl, port_load_ff=1.0)
    each = DC.cell_delay_ps("INV", 1.0)
    check("B6a 17 级 INV 链：STA=%.6f ps = 17×%.6f ps（绝对量级并报）"
          % (t.comb_delay_ps, each),
          abs(t.comb_delay_ps - n * each) < 1e-9,
          (t.comb_delay_ps, n * each))
    check("B6b 关键路径节点数 = 级数+1（路径回溯没漏段）",
          len(t.critical_path) == n + 1, len(t.critical_path))


# ---------------------------------------------------------------------------
# B7 控制壳：锁步序列对拍
# ---------------------------------------------------------------------------
def b7_ctrl():
    r = CT.ctrl_self_check()
    check("B7  控制壳自检（真实性 / 端口 / 位宽 / 锁步 / 完成）", r["ok"],
          r["problems"][:3])
    check("B7a DFF 数 == 状态位总数（%d · 声明决定，精确）" % AN_DFF,
          r["dff"] == AN_DFF, r["dff"])
    check("B7b 组合门数 ≥ %d（防综合器退化成空网表）" % AN_GATES_MIN,
          r["gates"] >= AN_GATES_MIN, r["gates"])
    ls = CT.lockstep(AN_LOCKSTEP)
    check("B7c 锁步 %d 拍零失配（%d 次输出比对）"
          % (ls["n_cycles"], ls["n_checked"]),
          ls["ok"] and ls["n_cycles"] == AN_LOCKSTEP, ls["mismatches"][:2])
    # 🔴 「完成」不能只看末拍：回到 IDLE 后 done_r 下一拍就被清 0。
    #    ⇒ 用**历史最大值**证明 done 真的起过、busy 真的落过（末态只证明回了 IDLE）。
    hist = ls["max_of"]
    check("B7d 完整一个样本走完（done 起过 1 / busy 落过 0 / 末态回 IDLE）",
          hist.get("done") == 1 and hist.get("busy") == 1
          and ls["final_state"].get("busy_r") == 0
          and ls["final_state"].get("st") == 0,
          (hist.get("done"), hist.get("busy"), ls["final_state"].get("st")))


# ---------------------------------------------------------------------------
# B8 累加器位宽：双向判据
# ---------------------------------------------------------------------------
def b8_width():
    w = CT.acc_width_witness()
    check("B8  累加器最大和 = 87×8×255 = %d（精确）" % AN_MAX_SUM,
          w["max_sum"] == AN_MAX_SUM, w["max_sum"])
    check("B8a 声明位宽 == %d（⌈log2(上界+1)⌉）" % AN_ACC_WIDTH,
          w["width_min"] == AN_ACC_WIDTH and w["declared"] == AN_ACC_WIDTH,
          (w["width_min"], w["declared"]))
    check("B8b **17 位不够**（这一半才让判据有判别力）",
          w["fits_at"][17] is False, w["fits_at"])
    check("B8c 18 位够", w["fits_at"][18] is True, w["fits_at"])


# ---------------------------------------------------------------------------
# B9 闭环：数字壳 Fmax vs SAR 时钟
# ---------------------------------------------------------------------------
def b9_closure():
    c = CT.closure()
    check("B9  闭环可算（Fmax 与 SAR 时钟都有值）",
          c["fmax_ctrl_mhz"] is not None and c["f_sar_mhz"] is not None, c)
    check("B9a 数字壳不是瓶颈（headroom %.2f× ≥ 1）" % (c["headroom"] or 0),
          not c["digital_is_bottleneck"], c["headroom"])
    check("B9b 架构差异已显式记录（不与 E17 相除）",
          "不可相除" in c["arch_note"], c["arch_note"][:40])
    return c


# ---------------------------------------------------------------------------
# B10 确定性
# ---------------------------------------------------------------------------
def b10_determinism():
    a = SY.synth(RT.parse(CT.CIM_CTRL_SRC))
    b = SY.synth(RT.parse(CT.CIM_CTRL_SRC))
    same = ([(g.name, g.cell, g.ins, g.out) for g in a.gates]
            == [(g.name, g.cell, g.ins, g.out) for g in b.gates])
    check("B10 两次综合逐位一致（网表确定性）", same and a.n_gates() == b.n_gates(),
          (a.n_gates(), b.n_gates()))


# ---------------------------------------------------------------------------
# C3/C4 探针：反向比较器 / 非阻塞退化成阻塞
# ---------------------------------------------------------------------------
def c3_c4_probes():
    from lda_l2.ecore import daig

    orig = daig.ult_bits

    def reversed_lt(g, x, y):
        lt = daig.C0
        for i in range(len(x) - 1, -1, -1):
            lt = g.OR(g.AND(x[i] ^ 1, y[i]), g.AND(g.XNOR(x[i], y[i]), lt))
        return lt

    daig.ult_bits = reversed_lt
    # dsynth 用的是 `from .daig import ...` 的本地名，需要一并替换
    old_sy = SY.ult_bits
    SY.ult_bits = reversed_lt
    try:
        m = RT.parse(Q._CASES["cmp_mix"])
        nl = SY.synth(m)
        r = Q.equiv(m, nl)
        check("C3  探针：比较器累积方向翻转 ⇒ 等价性**必须打红**", not r["ok"],
              r["mismatches"][:1])
    finally:
        daig.ult_bits = orig
        SY.ult_bits = old_sy

    # C4：非阻塞退化成阻塞（读新值）
    orig_nb = RT._exec_nb

    def blocking(st, rd, wr, widths):
        RT.exec_stmt(st, wr, widths)

    RT._exec_nb = blocking
    try:
        bad = RT.drtl_self_check()
        check("C4  探针：非阻塞退化成阻塞（读新值）⇒ 前端自检**必须打红**",
              not bad["ok"], bad["problems"][:2])
    finally:
        RT._exec_nb = orig_nb


# ---------------------------------------------------------------------------
# 主
# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("E34 门禁 · 数字控制壳自主建（六层自主数字链 + CIM 控制壳）")
    print("=" * 78)

    b1_library()
    b2_frontend()
    b3_equiv()
    b6_sta()
    b7_ctrl()
    b8_width()
    c9 = b9_closure()
    b10_determinism()
    c3_c4_probes()

    # AIG 结构性事实（防「AIG 只是个壳」）
    g = Aig()
    x = g.inp()
    y = g.inp()
    z = g.AND(x, y)
    check("B0a AIG 常数传播：AND(x, NOT(x)) 必须是常数 0",
          g.AND(z, z ^ 1) == 0)
    check("B0b AIG 结构哈希：同一 (x,y) 只建一个节点",
          g.AND(x, y) == z and g.n_ands == 1, g.stats())

    dt = elapsed()
    check("B11 门禁耗时 %.1f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)
    print("-" * 78)
    print("E34 · %d 项判据 · 通过 %d · 失败 %d · 耗时 %.1f s"
          % (PASS + FAIL, PASS, FAIL, dt))
    if FAIL:
        print("FAIL — 数字链出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E34 全绿 · 数字链六层自主 · 控制壳 %d 门 / %d DFF · 锁步 %d 拍零失配"
          % (c9["gates"], AN_DFF, AN_LOCKSTEP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
