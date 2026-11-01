"""E54 门禁：**DFF 进 HD 库**（22T · 正沿触发 · 版图 DRC/LVS 双零）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
E53 之后库里只有 INV/NAND2 —— 那还不足以证明「按规则生成单元」这条路可复用。
DFF 是网表里唯一的时序单元（约占 4.2%），器件数是 INV 的 11 倍，**能不能画出来、
能不能过 LVS、功能对不对**，是这条路的真正验收。

三件事分开证，互不代替：
  ① **功能**：对 `DFF_COLS` 声明的拓扑做开关级仿真（含传输门），必须正沿采样；
  ② **版图 ≡ 声明**：`run_lvs_pos` 双射校验（22 器件 / 13 网），DRC 双零；
  ③ **代价**：面积、行内轨道、引脚数与抽象模型的差异。

🔴 诚实边界（随任何引用一起给）：
  · 没有晶体管级电路仿真（本仓无 SPICE）—— 功能证据来自**开关级**模型，不是时序/噪声；
  · 22T ≠ 抽象模型 24T（口径差 2 管），面积按**实测几何**报，不套抽象模型；
  · 单元内部用了 **M2**（M1 水平总线 + M2 竖直跨层），而布线器只认引脚 ⇒ **本版不接入布线**；
  · 规则集是自建 LDA-DEMO28（教科书尺度），非 foundry PDK。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dcell as DC        # noqa: E402
from lda_l2.ecore import dcells as CL       # noqa: E402
from lda_l2.ecore import ddrc_lvs as DL     # noqa: E402
from lda_l2.ecore import dhdlib as HD       # noqa: E402

_FAILED: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FAILED)
T0 = time.time()
AN_ELAPSED_MAX_S = 180.0


# ── 开关级仿真器（传输门 + 反相器；pass 优先，反相器不覆盖被 pass 驱动的网）──
def _step(v: dict, clk: int, d: int) -> None:
    v["CLK"], v["D"] = clk, d
    for _ in range(60):
        passdrv = set()
        for kind, a, b, pg, ng in HD.DFF_COLS:
            if kind != "tg":
                continue
            if (v[pg] == 0) or (v[ng] == 1):
                src, dst = (a, b) if v[a] is not None else (b, a)
                if v[src] is not None and v[dst] != v[src]:
                    v[dst] = v[src]
                if v[a] is not None:
                    passdrv.add(b)
        ch = False
        for kind, a, b, _pg, _ng in HD.DFF_COLS:
            if kind != "inv":
                continue
            if v[a] is not None and b not in passdrv and v[b] != (1 - v[a]):
                v[b] = 1 - v[a]
                ch = True
        if not ch:
            break


def _fresh() -> dict:
    v = {k: None for k in ("ckb", "ckbb", "m", "mb", "s", "sb", "q1", "QN")}
    v["Q"] = 0
    return v


def _run(seq, cols=None):
    """跑一串 (CLK, D)，返回每步的 Q。`cols` 可替换拓扑（反向探针用）。"""
    saved = HD.DFF_COLS
    if cols is not None:
        HD.DFF_COLS = cols
    try:
        v = _fresh()
        out = []
        for (clk, d) in seq:
            _step(v, clk, d)
            out.append(v["Q"])
        return out
    finally:
        HD.DFF_COLS = saved


def _ideal(seq):
    """理想正沿 DFF 的参考模型（独立实现，避免「用被测物证被测物」）。"""
    q, prev = 0, 0
    out = []
    for (clk, d) in seq:
        if clk == 1 and prev == 0:
            q = d
        out.append(q)
        prev = clk
    return out


def main() -> int:
    print("E54 · DFF 进 HD 库：22T 正沿触发（版图 DRC/LVS 双零）· v0.9.357")
    cell = HD.build_dff_hd()

    # ── J1 功能：正沿采样（含「非沿不跟随」与「主从隔离」）────────────
    seq = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0), (0, 1), (1, 1), (1, 0),
           (0, 0), (0, 1), (1, 0), (1, 1), (0, 1), (1, 1), (0, 0), (1, 0)]
    got, exp = _run(seq), _ideal(seq)
    # 「非沿不跟随」单独取证：CLK 保持 1 时改 D，Q 必须不动
    hold = [(0, 0), (1, 0), (1, 1), (1, 0)]
    hold_q = _run(hold)
    check("J1 功能（开关级）：%d 拍序列的 Q 与理想正沿 DFF **逐拍一致**；"
          "且 CLK 停在 1 时改 D（0→1→0）Q 恒为 %d（非沿不跟随）" % (len(seq), hold_q[1]),
          got == exp and hold_q[1] == hold_q[2] == hold_q[3],
          "got=%s exp=%s" % (got, exp))

    # ── J2 器件数口径：声明 22 = 抽取 22，与抽象模型 24 差 2 ────────────
    n_exp = len(cell.devices_expected)
    n_got = len(CL.extract_devices(cell))
    n_model = DC.CELLS["DFF"].n_tr
    check("J2 器件数口径：**声明 %d = 抽取 %d**，与抽象模型 `dcell.DFF.n_tr=%d` 差 %d 管"
          "（本版无第二级输出缓冲）⇒ 面积按实测几何报、不套抽象模型"
          % (n_exp, n_got, n_model, n_model - n_exp),
          n_exp == n_got == 22 and n_model - n_exp == 2,
          "声明 %d · 抽取 %d · 模型 %d" % (n_exp, n_got, n_model))

    # ── J3 两张通孔表必须一致（同一物理事实的两种用途，不许第二份真源）──
    tbl_cell = {k: set(v) for k, v in CL._VIA_BRIDGE.items()}
    tbl_drc = {k: set(v) for k, v in DL.VIA_BRIDGE.items()}
    shared = set(tbl_cell) & set(tbl_drc)
    same = all(tbl_cell[k] == tbl_drc[k] for k in shared)
    extra = set(tbl_cell) - set(tbl_drc)
    check("J3 通孔桥接表一致：`dcells._VIA_BRIDGE` 与 `ddrc_lvs.VIA_BRIDGE` 在 %d 个共有通孔层上"
          "**逐项相同**（连通性与孔包围是同一事实）；单元侧只多 %s（接触孔不算布线通孔）"
          % (len(shared), sorted(extra)),
          same and len(shared) >= 2 and extra <= {CL.L_CONT},
          "共有 %d 层 · 一致=%s · 单元侧多出 %s" % (len(shared), same, sorted(extra)))

    # ── J4 总线电平不重叠（同一 y 上的两个网必须 x 不相交）─────────────
    by_lv = {}
    for net, (lv, xa, xb) in HD.DFF_BUS.items():
        by_lv.setdefault(lv, []).append((xa, xb, net))
    bad = []
    for lv, items in by_lv.items():
        items.sort()
        for i in range(1, len(items)):
            if items[i][0] < items[i - 1][1]:
                bad.append((lv, items[i - 1][2], items[i][2]))
    check("J4 总线电平自洽：%d 个网共享 %d 条电平，同一电平上的网 **x 两两不相交**（无短路）"
          % (len(HD.DFF_BUS), len(by_lv)),
          not bad, "冲突 %s · 电平占用 %s"
          % (bad, {k: [n for (_a, _b, n) in v] for k, v in sorted(by_lv.items())}))

    # ── J5 版图合法：DRC 0 / LVS 0；并机核「旧 LVS 为何不行」──────────
    d = HD.run_drc(cell, HD.HD_RULES)
    lvp = HD.run_lvs_pos(cell)
    lvo = CL.run_lvs(cell)
    check("J5 版图合法：DRC **%d** / 双射 LVS **%d**；而既有 `dcells.run_lvs`（规范形排序依赖网名）"
          "在 22 器件上**必然误报 %d 条** ⇒ 口径问题不是版图问题" % (d["n"], lvp["n"], lvo["n"]),
          d["n"] == 0 and lvp["n"] == 0 and lvo["n"] > 0,
          "DRC %d · LVS(pos) %d（%d 器件/%d 网）· LVS(canon) %d"
          % (d["n"], lvp["n"], lvp["n_got"], lvp.get("nodes", 0), lvo["n"]))

    # ── J6 代价：面积 / 等高 / 行内轨道 / 引脚 ────────────────────────
    inv = HD.build_inv_hd()
    nand = HD.build_nand2_hd()
    it = HD.inner_tracks(cell, HD.HD_ROUTE)
    it_inv = HD.inner_tracks(inv, HD.HD_ROUTE)
    ratio = cell.w * cell.h / (inv.w * inv.h)
    check("J6 代价如实报：面积 **%.4f µm²** = **%.2f× INV** / %.2f× NAND2（等高 %.0fnm）；"
          "行内可用轨道 **%d 条**（INV 有 %d 条 —— 4 个引脚把行内空隙吃掉更多）"
          % (cell.w * cell.h / 1e6, ratio, cell.w * cell.h / (nand.w * nand.h),
             cell.h, it["n"], it_inv["n"]),
          cell.h == inv.h == HD.H_ROW_HD and it["n"] >= 1 and 5.0 <= ratio <= 12.0,
          "w=%d h=%d · 轨道 %s · 引脚 %s"
          % (cell.w, cell.h, it["tracks"], sorted(cell.pins)))

    # ── J7 反向探针（两条，各自打不同的检查器）────────────────────────
    # ① 删掉一个 V1（输出竖带→总线的唯一通路）⇒ 该网断开 ⇒ 双射 LVS 必须报
    vias = [r for r in cell.rects if r.role == "via1"]
    victim = max(vias, key=lambda r: (r.y0, r.x0))
    broken = CL.Cell(cell.name, cell.w, cell.h,
                     [r for r in cell.rects if r is not victim], cell.pins,
                     cell.devices_expected)
    lv_bad = HD.run_lvs_pos(broken)["n"]
    # ② 把一条总线压成 10nm 高 ⇒ 线宽违规
    bus = [r for r in cell.rects if r.role == "bus"][0]
    pinch = CL.Cell(cell.name, cell.w, cell.h,
                    [CL.R(r.layer, r.x0, r.y0, r.x1, r.y0 + 10, net=r.net, role=r.role)
                     if r is bus else r for r in cell.rects], cell.pins, cell.devices_expected)
    drc_bad = HD.run_drc(pinch, HD.HD_RULES)["n"]
    check("J7 双反向探针：① 删一个 V1 ⇒ 双射 LVS **%d** 条（连通性判据有牙）；"
          "② 总线压到 10nm ⇒ DRC **%d** 条（线宽判据有牙）" % (lv_bad, drc_bad),
          lv_bad > 0 and drc_bad > 0,
          "删孔后 LVS %d · 压窄后 DRC %d" % (lv_bad, drc_bad))

    # ── J8 功能反向探针：把 TG2 的控制相位对调 ⇒ 必须不再是正沿触发 ────
    wrong = tuple((k, a, b, (ng if k == "tg" and i == 5 else pg),
                   (pg if k == "tg" and i == 5 else ng))
                  for i, (k, a, b, pg, ng) in enumerate(HD.DFF_COLS))
    bad_seq = _run(seq, cols=wrong)
    check("J8 功能反向探针：把 TG2 的 P/N 栅对调（控制相位反）⇒ 输出 %d/%d 拍不符理想 DFF"
          "（说明 J1 不是恒绿）" % (sum(1 for x, y in zip(bad_seq, exp) if x != y), len(exp)),
          bad_seq != exp,
          "对调后 Q=%s" % (bad_seq,))

    # ── J9 确定性 ────────────────────────────────────────────────────
    c2 = HD.build_dff_hd()
    same_geom = ([(r.layer, r.x0, r.y0, r.x1, r.y1) for r in c2.rects]
                 == [(r.layer, r.x0, r.y0, r.x1, r.y1) for r in cell.rects])
    check("J9 确定性：两次构建的版图矩形**逐位一致**（%d 个矩形）" % len(cell.rects),
          same_geom, "%d vs %d" % (len(cell.rects), len(c2.rects)))

    dt = time.time() - T0
    check("J0 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [功能] 正沿采样 %d 拍逐拍一致 · 非沿不跟随 · 相位反了就失效（J8）" % len(seq))
    print("  [版图] DRC 0 / 双射 LVS 0 · %d 器件 · %d 网 · %.4f µm²（%.2f× INV）"
          % (n_got, lvp.get("nodes", 0), cell.w * cell.h / 1e6, ratio))
    print("  [边界] 无 SPICE（功能只到开关级）· 22T≠模型 24T · 单元内部用 M2 且**本版不接入布线** · "
          "LDA-DEMO28 非 foundry PDK")
    print()
    if _FAILED:
        print("E54 有红色：%s" % ", ".join(_FAILED))
        return 1
    print("E54 全绿 · DFF 进 HD 库：22T 正沿触发，DRC/LVS 双零，功能开关级验证")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
