#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E48 门禁：**M2 逃逸走线 —— 间距回收被证伪，但 M3 短路被消除**（D-240）。

## 这一版想做什么，结果是什么

**假设**（v0.9.349 留下的）：单元间距 0.36 → 0.46µm 是为了让全库引脚落在同一列网格上，
好让 M3 不需要横向跳线。若允许 **M2 承担「引脚 → 列」的横向偏移**（真实设计做法），
间距应该能退回 0.36µm，把上一版付出去的 ≈8% 面积赚回来。

**结果：假设被**证伪**，而且能给出几何必然性：

| 配置 | 路由层(M3) DRC | 全量 DRC | 结论 |
|---|---|---|---|
| gap 0.46 + M3 跳线（v0.9.350） | 0 | 0 | 基线 |
| gap 0.46 + **M2 逃逸条** | 0 | **0** | ✅ M3 跳线 8→0，层级更干净 |
| gap 0.36 + M3 跳线 | **4** | 6 | 旧形态，间距一退就红 |
| gap 0.36 + **M2 逃逸条** | **0** | **4** | ⚠️ M3 短路消掉了，但撞到 **M2 自己** |

**为什么必然撞**（闭式，判据 C4 守）：同一 y 带上两个相邻引脚，x 恰差一个 pitch `P=0.36`，
引脚 pad 边长 `VIA+2·ENC = 0.24` ⇒ 两 pad 之间只剩 `P − 0.24 = 0.12µm`。
M2 逃逸条比 pad 宽出 `2·hp = 0.242`，两条要共存须留 `S_MIN = 0.10`
⇒ **内向逃逸的总余量只有 0.12 − 0.10 = 0.02µm，即每条 ≤0.01µm** —— 实际上等于 0。
外向逃逸在单元内部可行，但**在单元边界上两相邻单元的对向逃逸又撞上**（间距同样是 0.36）。
⇒ 在现有单元几何（A/B 同 y、x 恰一个 pitch）下，**两条 M2 逃逸条不可能共存**。

⇒ **0.46µm 不是保守取值，是必要代价**（判据 C5 用间距扫描钉住：0.36/0.40/0.44 恒 4 条，
只有 ≥0.46 才为 0）。要真正回收，唯一路径是把同 y 的引脚 y 带分开 ⇒ 需要加单元高度，
而 NAND2 的 gap 只有 520nm、三个 240nm 带 + 60nm 间距需要 660nm ⇒ **+140nm（面积 +9.3%）**，
比省下的 8% 还多 ⇒ **不划算，不做**。

| # | 守护 | 金标 |
|---|---|---|
| C1 | 默认配置（gap 0.46 + M2 逃逸） | 路由 DRC 0 ∧ 全量 DRC 0 ∧ **M3 跳线数 0** |
| C2 | M3 短路确被消除 | gap 0.36 下路由层 DRC **4 → 0** |
| C3 | **不得宣称零 DRC** | gap 0.36 下全量 DRC > 0，且残差**全在 M2 层** |
| C4 | 几何必然性（闭式） | `P − pad` 余量 vs `S_MIN` 的差 ≤0.02µm，且实测最差 M2 间隙 < S_MIN |
| C5 | **间距不可回收** | 0.36/0.40/0.44 全量 DRC 恒 >0；≥0.46 才为 0 ⇒ 0.46 是必要值 |
| C6 | 反向探针 | 关掉 M2 逃逸 ⇒ gap 0.36 路由 DRC 必回 4（证明 M2 真起作用） |
| C7 | trunk 缩短 | M2 版的 M3 trunk 总长 < 旧版（trunk 只覆盖列，不覆盖引脚） |
| C8 | 确定性 | 两次路由几何逐位一致 |
| C0 | 耗时 | < 阈值 |

## 诚实口径
- 🔴 本版的净收益是**层级更干净（M3 跳线归零）+ 一个被证伪的假设**，**不是**面积回收。
- 🔴 0.46µm 的必要性依赖**当前单元几何**（A/B 同 y）。若将来把引脚 y 带分开或加高单元，
  这条结论要重测 —— 判据 C5 会把「0.46 是必要值」钉住，改了单元就该红。
- 🔴 规则集仍是 LDA-DEMO45（自建教科书尺度），非 foundry PDK。
- 🔴 净增 **0 锚**（整数几何 + 组合 ⇒ resid≡0）⇒ 门禁形态。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dpnr as PN          # noqa: E402
from lda_l2.ecore import dctrl as CT         # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL      # noqa: E402
from lda_l2.ecore import ddetail as DD       # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 120.0
CASE_N = 12
CASE_COLS = 4
GAP_LOOSE = 0.46        # 当前默认（必要值）
GAP_TIGHT = 0.36        # 想回收到的目标值
SCAN = (0.36, 0.40, 0.44, 0.46)

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _route(nl, gap, m2_jog=True):
    pl = PN.place_real(nl, max_cells=CASE_N, cols=CASE_COLS, cell_gap=gap)
    rt = PN.route_block(nl, pl, m2_jog=m2_jog)
    vr = DL.run_drc(PN.routing_only(rt))["violations"]
    va = DL.run_drc(PN.all_routing(rt))["violations"]
    return pl, rt, vr, va


def _trunk_len(rt: dict) -> float:
    """M3 trunk 的总长（只统计走线层里跨该网全部列的横条）。"""
    tot = 0.0
    for s in rt["shapes_route"]:
        if s.layer == DD.L_M3 and abs((s.y1 - s.y0) - PN.W) < 1e-6 and (s.x1 - s.x0) > 2 * PN.EXT:
            tot += s.x1 - s.x0
    return round(tot, 4)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E48 · M2 逃逸走线：间距回收被证伪，M3 跳线被消除")
    print("=" * 78)

    nl = CT.build()["netlist"]
    pl_l, rt_l, vr_l, va_l = _route(nl, GAP_LOOSE, True)
    pl_t, rt_t, vr_t, va_t = _route(nl, GAP_TIGHT, True)
    _, rt_t_off, vr_off, _ = _route(nl, GAP_TIGHT, False)
    _, rt_l_off, _, _ = _route(nl, GAP_LOOSE, False)

    # ── C1 默认配置：零 DRC ∧ M3 跳线归零 ──────────────────────
    check("C1 默认（gap %.2f + M2 逃逸）：路由 DRC 0 ∧ 全量 DRC 0 ∧ M3 跳线数 0"
          % GAP_LOOSE,
          not vr_l and not va_l and rt_l["n_m3_jog"] == 0,
          "路由 %d / 全量 %d · M2 绕行 %d · M3 跳线 %d（旧形态为 %d）"
          % (len(vr_l), len(va_l), rt_l["n_m2_jog"], rt_l["n_m3_jog"], rt_l_off["n_m3_jog"]))

    # ── C2 M3 短路确被消除（gap 0.36）───────────────────────────
    check("C2 M2 逃逸把路由层(M3)的短路消掉：gap %.2f 下路由 DRC 4 → 0" % GAP_TIGHT,
          len(vr_t) == 0 and len(vr_off) > 0,
          "M2 版 %d 条 vs 旧形态 %d 条 · 布通 %d"
          % (len(vr_t), len(vr_off), len(rt_t["routed"])))

    # ── C3 不得宣称零 DRC：残差全在 M2 ─────────────────────────
    layers = sorted({v[1] for v in va_t})
    check("C3 🔴 不得宣称零 DRC：gap %.2f 下全量 DRC > 0，且残差**全在 M2 层**"
          % GAP_TIGHT,
          len(va_t) > 0 and layers == [DD.L_M2],
          "全量 %d 条 · 涉及层 %s（M2=%d）" % (len(va_t), layers, DD.L_M2))

    # ── C4 几何必然性（闭式余量）──────────────────────────────
    pad = DD.VIA + 2.0 * DL.ENC               # 0.24
    room = PN.PITCH - pad                     # 两 pad 之间的净空
    inward = room - DL.S_MIN                  # 扣掉间距后可用于「内向逃逸」的总量
    # 实测最差 M2 间隙（同 y 带上两个不同网的 M2 条之间的最大重叠/最近距离）
    metals = [s for s in PN.all_routing(rt_t) if s.kind == "metal" and s.layer == DD.L_M2]
    worst = None
    for i in range(len(metals)):
        for j in range(i + 1, len(metals)):
            a, b = metals[i], metals[j]
            if a.net == b.net:
                continue
            if max(a.y0, b.y0) > min(a.y1, b.y1):     # y 不重叠
                continue
            gap = max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1))
            worst = gap if worst is None else min(worst, gap)
    check("C4 几何必然性：同 y 两引脚净空 %.3fµm，扣 S_MIN 后内向逃逸总量只有 %.3fµm ⇒ 两条 M2 条无法共存"
          % (room, inward),
          inward <= 0.03 and worst is not None and worst < DL.S_MIN - 1e-9,
          "P−pad=%.3f · 可内向总量 %.3f · 实测最差 M2 间隙 %.4f < S_MIN %.2f"
          % (room, inward, worst if worst is not None else -1, DL.S_MIN))

    # ── C5 间距不可回收（扫描）──────────────────────────────────
    scan = []
    for gap in SCAN:
        _pl, _rt, _vr, _va = _route(nl, gap, True)
        scan.append((gap, len(_vr), len(_va)))
    ok_scan = all(va > 0 for (g, vr, va) in scan if g < GAP_LOOSE - 1e-9) \
        and all(va == 0 for (g, vr, va) in scan if g >= GAP_LOOSE - 1e-9)
    check("C5 间距不可回收：%.2f/%.2f/%.2f 全量 DRC 恒 >0，只有 ≥%.2f 才为 0 ⇒ %.2f 是**必要值**"
          % (SCAN[0], SCAN[1], SCAN[2], GAP_LOOSE, GAP_LOOSE),
          ok_scan, "扫描 (gap, 路由, 全量) = %s" % (scan,))

    # ── C6 反向探针：关掉 M2 逃逸 ⇒ gap 0.36 路由 DRC 必回 4 ──────
    check("C6 反向探针：关掉 M2 逃逸（退回 M3 跳线）⇒ gap %.2f 的路由 DRC 必回 >0"
          % GAP_TIGHT,
          len(vr_off) > 0 and len(vr_t) == 0,
          "旧形态 %d 条 vs M2 形态 %d 条" % (len(vr_off), len(vr_t)))

    # ── C7 trunk 缩短（trunk 只覆盖列，不覆盖引脚）───────────────
    t_on, t_off = _trunk_len(rt_l), _trunk_len(rt_l_off)
    check("C7 trunk 缩短：M2 版的 M3 trunk 总长 < 旧形态（trunk 只覆盖列，不再延伸到引脚）",
          t_on < t_off - 1e-9,
          "M2 版 %.3f µm vs 旧形态 %.3f µm（−%.1f%%）"
          % (t_on, t_off, (1 - t_on / t_off) * 100.0))

    # ── C8 确定性 ─────────────────────────────────────────────
    rt2 = PN.route_block(nl, pl_l, m2_jog=True)
    same = ([tuple((s.layer, s.x0, s.y0, s.x1, s.y1, s.net)) for s in rt_l["shapes"]] ==
            [tuple((s.layer, s.x0, s.y0, s.x1, s.y1, s.net)) for s in rt2["shapes"]])
    check("C8 确定性：两次路由几何逐位一致", same,
          "shapes %d vs %d" % (len(rt_l["shapes"]), len(rt2["shapes"])))

    dt = time.time() - t0
    check("C0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("  [结果] 假设**被证伪**：间距 %.2f 退回 %.2f 会省钱，但 M2 逃逸条必然互撞"
          % (GAP_LOOSE, GAP_TIGHT))
    print("  [真收益] M3 跳线 %d → 0 · trunk 总长 −%.1f%% · 层级更干净（不是面积）"
          % (rt_l_off["n_m3_jog"], (1 - t_on / t_off) * 100.0))
    print("  [诚实边界] 0.46µm 的必要性依赖当前单元几何（A/B 同 y）；改了单元必须重测")
    print("-" * 78)
    print("E48 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E48 有红色：见上方 [FAIL] 行")
        return 1
    print("E48 全绿 · M2 逃逸：M3 跳线归零、trunk 缩短；**间距回收被证伪**（几何必然，"
          "0.46µm 是必要代价）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
