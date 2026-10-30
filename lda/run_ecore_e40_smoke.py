#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E40 门禁：**B1 标准单元内部几何**（晶体管级）—— 真实 DRC / LVS / 寄生 R。

## 本门禁守什么
E36 的「真实单元几何」实际只有：有源标记方块 + 引脚焊垫 + 通孔栈（`ddetail.real_cell_geom`
自述「画不下真实晶体管」）。B1 把标准单元做成**晶体管级几何**（DIFF/POLY/CONT/M1/NWELL），
于是 DRC / LVS / R 提取第一次有真对象可查。

| # | 守护 | 金标 |
|---|---|---|
| B1 | 几何↔器件互证 | 每单元由几何**抽出**器件数 == 期望（INV 2 / NAND2 4），W/L 逐值相等 |
| B2 | 真实 DRC | 全部单元 DRC **零违规**；且每单元含 poly/contact/diff 三层几何（防空跑） |
| B3 | DRC 判别力 | 4 条突变各**必红**且报的规则名正确（孔包围 / 线宽 / poly 间距 / nwell 包围） |
| B4 | 真实 LVS | 全部单元 LVS **零失配**（含内部节点匹配：NAND 串联中间节点） |
| B5 | LVS 判别力 | 删栅 / 短路 / 改 W / 删接触孔 / 删 nwell（器件类型翻转）各**必红** |
| B6 | 面积口径 | 几何 bbox 面积与每管面积（`area/tr`）落在合理带，并与符号模型（0.266µm²/tr）比较 |
| B7 | 寄生 R | 栅 R>0 · 两法互证（逐段串联 ≡ 闭式）· S/D 含接触电阻 · 金属段 R>0 |
| B8 | 确定性 | 两次构建 + 两次检测 ⇒ 几何与结论逐字节一致 |
| B0 | 耗时 | < 阈值（纯整数几何，亚秒级） |

## 诚实口径
- 规则集是**自建 LDA-DEMO45**（45nm 量级教科书尺度），**非任何 foundry PDK 真值** ⇒
  不得作制造/性能宣称（见 `dcells.B1_DISCLOSURE`）。
- **不是 SPICE**：器件只有 W/L + 方块电阻，无 I-V/C/温度/噪声。
- **净增 0 锚**：几何/连通/电阻是确定性整数与闭式算术，做成 ledger 锚会 `resid≡0` 判自证桩
  ⇒ 本判据以**门禁形态**落地（与 E39 同口径）。
- 面积结论只用于「设计期面积口径」，**不报 TOPS/fJ/能效**（未流片）。
"""

import copy
import dataclasses
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dcells as CL        # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 60.0
SYMBOLIC_AREA_PER_TR = 0.266      # E38c 符号模型（µm²/tr），用于对照"真实几何是否更大"

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)


def _mut(cell, fn):
    c = copy.deepcopy(cell)
    fn(c)
    return c


def _set(idx, **kw):
    return lambda c: c.rects.__setitem__(idx, dataclasses.replace(c.rects[idx], **kw))


def _find(cell, role, layer=None, pred=None):
    for i, r in enumerate(cell.rects):
        if r.role == role and (layer is None or r.layer == layer) and (pred is None or pred(r)):
            return i
    raise LookupError("no rect role=%s" % role)


def main():
    t0 = time.time()
    print("=" * 78)
    print("E40 · B1 标准单元内部几何（晶体管级）—— 真实 DRC / LVS / 寄生 R")
    print("=" * 78)

    cells = {n: f() for n, f in CL.CELLS.items()}
    drc = {n: CL.run_drc(c) for n, c in cells.items()}
    lvs = {n: CL.run_lvs(c) for n, c in cells.items()}
    rp = {n: CL.extract_r(c) for n, c in cells.items()}

    print("  [info] 单元: %s" % ", ".join(
        "%s %.4fµm² %d管 %.4fµm²/管" % (n, c.area_um2, len(lvs[n]["devices"]),
                                       c.area_um2 / max(1, len(lvs[n]["devices"])))
        for n, c in cells.items()))

    # ── B1 几何 ↔ 器件互证 ────────────────────────────────────────────
    dev_ok, dev_detail = True, []
    for n, c in cells.items():
        got = sorted((d["kind"], d["w"], d["l"]) for d in lvs[n]["devices"])
        exp = sorted((k, w, l) for (k, w, l, *_rest) in c.devices_expected)
        if got != exp:
            dev_ok = False
            dev_detail.append((n, got, exp))
    check("B1 几何↔器件互证：抽出器件 (kind,W,L) 多重集 == 期望（INV 2 / NAND2 4）",
          dev_ok, dev_detail or "all match")

    # ── B2 真实 DRC 零违规 + 几何非空 ────────────────────────────────
    bad = [(n, drc[n]["violations"][:3]) for n in cells if drc[n]["n"]]
    layers_ok = all(
        any(r.layer == CL.L_POLY for r in c.rects)
        and any(r.layer == CL.L_CONT for r in c.rects)
        and any(r.layer == CL.L_DIFF for r in c.rects)
        for c in cells.values())
    check("B2 真实 DRC：全部单元零违规 ∧ 每单元含 DIFF/POLY/CONT 三层（防空跑）",
          not bad and layers_ok, bad or ("layers_ok=%s" % layers_ok))

    # ── B3 DRC 判别力（4 条突变各必红，且报对规则名）─────────────────
    inv = cells["INV_X1"]
    i_cg = _find(inv, "cont_gate")
    i_rail = _find(inv, "rail")
    i_nw = _find(inv, "nwell")
    probes = [
        ("cont_enc_poly", _set(i_cg, x0=inv.rects[i_cg].x0 - 10)),        # 栅孔包围 15→11
        ("min_width", _set(i_rail, y1=inv.rects[i_rail].y0 + 50)),        # M1 轨高 70→50
        ("nwell_enc", _set(i_nw, x0=inv.rects[i_nw].x0 + 40)),            # nwell 包围 80→40
        ("min_space_L21", lambda c: c.rects.append(
            CL.R(CL.L_POLY, 360, 700, 410, 1000, role="gate"))),          # 加贴太近的 poly
    ]
    p_res = []
    for want, fn in probes:
        d = CL.run_drc(_mut(inv, fn))
        p_res.append((want, d["n"], want in [v[0] for v in d["violations"]]))
    check("B3 DRC 判别力：孔包围／线宽／nwell 包围／poly 间距 四改必红且报对规则名",
          all(n > 0 and hit for (_w, n, hit) in p_res), p_res)

    # ── B4 真实 LVS 零失配 ──────────────────────────────────────────
    badl = [(n, lvs[n]["mismatches"][:3]) for n in cells if lvs[n]["n"]]
    check("B4 真实 LVS：全部单元零失配（含内部节点匹配 · NAND 串联中间节点 n1）",
          not badl, badl or "all match")

    # ── B5 LVS 判别力（删栅/短路/改W/删孔/删nwell）───────────────────
    i_gate = _find(inv, "gate")
    i_y = _find(inv, "strap", pred=lambda r: r.x0 == 410)
    i_pdiff = [i for i, r in enumerate(inv.rects) if r.layer == CL.L_DIFF][1]
    i_csd = _find(inv, "cont_sd")
    lp = [
        ("del_gate", lambda c: c.rects.pop(i_gate)),
        ("short_Y_VDD", _set(i_y, x0=140, y1=1000)),
        ("w_300_200", _set(i_pdiff, y1=inv.rects[i_pdiff].y1 - 100)),
        ("del_sd_cont", lambda c: c.rects.pop(i_csd)),
        ("del_nwell", lambda c: c.rects.pop(i_nw)),
    ]
    lp_res = []
    for tag, fn in lp:
        m = _mut(inv, fn)
        lp_res.append((tag, CL.run_lvs(m)["n"]))
    check("B5 LVS 判别力：删栅／短 Y-VDD／改 W／删源漏孔／删 nwell（类型翻转）五改必红",
          all(n > 0 for (_t, n) in lp_res), lp_res)

    # ── B6 面积口径（真实几何 vs 符号模型）──────────────────────────
    per = []
    for n, c in cells.items():
        ntr = max(1, len(lvs[n]["devices"]))
        per.append((n, round(c.area_um2, 4), ntr, round(c.area_um2 / ntr, 4)))
    band_ok = all(0.15 <= a_tr <= 0.80 for (_n, _a, _t, a_tr) in per)
    greater = all(a_tr > SYMBOLIC_AREA_PER_TR for (_n, _a, _t, a_tr) in per)
    check("B6 面积口径：area/tr 落在 [0.15,0.80]µm² 且 > 符号模型 %.3f（真实几何更大）"
          % SYMBOLIC_AREA_PER_TR,
          band_ok and greater, per)

    # ── B7 寄生 R（两法互证 + 非零 + 含接触）────────────────────────
    r_problems = []
    for n, c in cells.items():
        for k, dv in enumerate(rp[n]["devices"]):
            seg_sum = sum(s["r_ohm"] for s in dv["sd"])
            closed = sum(CL._seg_r(CL.RSH["diff"], s["dist_nm"], dv["w_nm"])
                         + CL.R_CONTACT * s["n_cont"] for s in dv["sd"])
            if dv["gate_ohm"] <= 0:
                r_problems.append((n, k, "gate<=0"))
            if len(dv["sd"]) != 2:
                r_problems.append((n, k, "sd!=2"))
            if abs(seg_sum - closed) > 1e-9 * max(1.0, closed):
                r_problems.append((n, k, "seg!=closed", seg_sum, closed))
            if any(s["n_cont"] <= 0 for s in dv["sd"]):
                r_problems.append((n, k, "no_cont_r"))
        if not (rp[n]["metal"] and all(v > 0 for v in rp[n]["metal"].values())):
            r_problems.append((n, "metal<=0"))
    check("B7 寄生 R：栅 R>0 ∧ 两法互证（逐段串联≡闭式）∧ S/D 含接触电阻 ∧ 金属段 R>0",
          not r_problems, r_problems[:5] or "ok")

    # ── B8 确定性（两次构建 + 两次检测逐字节一致）────────────────────
    def sig():
        out = []
        for n, f in CL.CELLS.items():
            c = f()
            dd = [(r.layer, r.x0, r.y0, r.x1, r.y1, r.role) for r in c.rects]
            out.append((n, c.w, c.h, tuple(dd),
                        CL.run_drc(c)["n"], CL.run_lvs(c)["n"],
                        tuple(round(d["gate_ohm"], 9) for d in CL.extract_r(c)["devices"])))
        return tuple(out)
    check("B8 确定性：两次构建 + 两次检测 ⇒ 几何/DRC/LVS/R 逐字节一致",
          sig() == sig())

    # ── B0 耗时 ────────────────────────────────────────────────────
    dt = time.time() - t0
    check("B0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, dt)

    print("-" * 78)
    print("E40 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("FAIL — E40 标准单元内部几何（DRC/LVS/R）出现问题，按上方 [FAIL] 项修复")
        return 1
    print("E40 全绿 · 晶体管级单元几何：DRC 零违规（自建 LDA-DEMO45 规则集）· "
          "LVS 零失配（含内部节点）· 寄生 R 两法互证 · 真实面积较符号模型更大 · 净增 0 锚")
    return 0


if __name__ == "__main__":
    sys.exit(main())
