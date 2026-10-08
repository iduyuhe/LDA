#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PS-M1（G4）· 传感窗口工艺层 + DRC 工艺例外 + PDK 器件 门禁（v0.9.210）。

═══ 判什么（分节）═══
A 几何与**单一真源**（层号跨源一致 / 窗口矩形 ↔ `sensing_window_geometry` 同源 /
  **端口锚 ↔ 版图 descs 逐点一致** / 窗口覆盖波导芯 / 端留白公式）·
B DRC 工艺规则（四条新规则 · 传感器件默认点 PASS · 开窗区包封=0 被豁免 ·
  非传感器件**零影响** · 报告自描述 · 🔴 `to_dict()` 向后兼容不漂移）·
C 🔴 **工艺例外护栏**（"例外≠消音器"：空 replaced_by / 空 reason / 悬空引用 ⇒
  ValueError；合法但未评估的替代规则 ⇒ RuntimeError；`exceptions=()` 必须**真的**
  让包封规则判红 ⇒ 证明豁免由例外对象在**运行时**施加，而非硬编码）·
D 反向探针（窗口过窄 / 余量不足 / 窗口触及端口 / 环半径过小 ⇒ 各自**必红**）·
E PDK 器件本体（内置条目 + layers + 单一真源纪律 + 工艺规则可被 PDK 覆盖）·
G 自入 CI core（防静默漏接）。

═══ 🔴 锚账本口径（本档**零净增锚**）═══
PS-M1 是**工艺/几何/规则**里程碑，不是新物理锚：开窗带来的灵敏度提升早已由
B469/B470/B471（几何灵敏度，golden=一阶本征值微扰）与 B471（去衬底 2.37×）锚定。
因此本档**不动账本**（490/strict 468/桩 19 不变），只 +1 条 CI core 门禁。

═══ 诚实边界 ═══
· 传感窗口几何为**设计示例**（默认窗口宽 3 µm / 长 8 µm / 余量 0.20 µm），
  非任何 foundry 的真实开窗 deck；DRC 四条新规则同属「可被 PDK 覆盖」的**设计
  规则层**，非实测 golden。
· 本门禁只判**几何合规与例外纪律**；**不**对开窗后的器件做任何灵敏度/损耗宣称
  （那由 B469–B471 与 PS-M2 噪声模型负责）。
"""
from __future__ import annotations

import math
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


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def main() -> int:
    from lda_l2 import primitives as P
    from lda_l2 import gds_export as G
    from lda_l2.drc import (
        DEFAULT_RULES, CHECK_RULES, DRCException, WINDOW_EXCEPTIONS,
        drc_check_device, validate_exceptions,
    )
    from lda_layout.placement import port_anchor

    kinds = ("SensingRing", "SensingMZI")

    # ══════════════════════ A 几何与单一真源 ══════════════════════
    check("A1 层号跨源一致：primitives._LAYER_WINDOW == gds_export.LIB_LAYER_WINDOW == 7",
          P._LAYER_WINDOW == G.LIB_LAYER_WINDOW == 7,
          f"{P._LAYER_WINDOW} vs {G.LIB_LAYER_WINDOW}")

    g_ring = P.sensing_window_geometry("SensingRing", {})
    g_mzi = P.sensing_window_geometry("SensingMZI", {})
    sp = P._sens_p("SensingRing", {})
    check("A2 默认点几何 sane（余量/端留白/窗口高 > 0；Ring 余量 == (window_w − wg)/2）",
          all(g[k] > 0 for k in ("window_margin", "window_end_gap", "window_h")
              for g in (g_ring, g_mzi))
          and abs(g_ring["window_margin"]
                  - (sp["window_w"] - sp["wg_width"]) / 2.0) < 1e-12,
          f"ring margin={g_ring['window_margin']:.4f}")

    # A3 🔴 版图窗口矩形 ≡ 几何量（同一函数导出；不漂移）
    ok3, det3 = True, []
    for k in kinds:
        d = P.sensing_window_descs(k, {})
        g = P.sensing_window_geometry(k, {})
        wrect = [x for x in d if x["layer"] == P._LAYER_WINDOW]
        if len(wrect) != 1 or wrect[0]["kind"] != "boundary":
            ok3 = False
            det3.append(f"{k}: 窗口层元素数={len(wrect)}")
            continue
        x0, y0, x1, y1 = _bbox(wrect[0]["rings_um"][0])
        ok3 = ok3 and abs((x1 - x0) - g["window_len"]) < 1e-9 \
            and abs((y1 - y0) - g["window_h"]) < 1e-9 \
            and abs((x0 + x1) / 2.0 - g["window_center_x"]) < 1e-9 \
            and abs((y0 + y1) / 2.0 - g["window_center_y"]) < 1e-9
        det3.append(f"{k}:{x1 - x0:.3f}x{y1 - y0:.3f}")
    check("A3 🔴 版图窗口矩形 ≡ sensing_window_geometry（宽/高/中心逐值一致）",
          ok3, "; ".join(det3))

    # A4 🔴 端口锚 ≡ 版图 descs 端点（默认 + 非默认参数）
    ok4, det4 = True, []
    for prm in ({}, {"R": 14.0, "wg_width": 0.5, "gap": 0.25},
                {"Lu": 30.0, "dy": 6.0, "wg_width": 0.5}):
        for k in kinds:
            d = P.sensing_window_descs(k, prm)
            paths = [x for x in d if x["kind"] == "path"]
            if k == "SensingRing":
                bus = paths[1]["points_um"]
                ends = {"in": tuple(bus[0]), "out": tuple(bus[-1])}
            else:
                ends = {"in1": tuple(paths[0]["points_um"][0]),
                        "out1": tuple(paths[0]["points_um"][-1]),
                        "in2": tuple(paths[1]["points_um"][0]),
                        "out2": tuple(paths[1]["points_um"][-1])}
            for port, exp in ends.items():
                got = tuple(port_anchor(k, port, prm))
                if max(abs(a - b) for a, b in zip(got, exp)) > 1e-12:
                    ok4 = False
                    det4.append(f"{k}.{port} {got} != {exp}")
    check("A4 🔴 端口锚 ≡ 版图 descs 端点（Ring in/out · MZI in1/out1/in2/out2 · 3 组参数）",
          ok4, "; ".join(det4) or "逐点一致")

    # A5 窗口**覆盖波导芯**（暴露体积 > 0 的几何证据）
    wg = sp["wg_width"]
    r_core_hi = g_ring["R"] + wg / 2.0
    r_win_hi = g_ring["window_center_y"] + g_ring["window_h"] / 2.0
    r_win_lo = g_ring["window_center_y"] - g_ring["window_h"] / 2.0
    ring_arc_half = g_ring["R"] * math.sin(sp["window_len"] / (2.0 * g_ring["R"]))
    m_lo = g_mzi["window_center_y"] - g_mzi["window_h"] / 2.0
    m_hi = g_mzi["window_center_y"] + g_mzi["window_h"] / 2.0
    check("A5 窗口矩形**包含**波导芯（Ring 顶弧径向 ⊆ 窗口 ∧ 弧横向 ⊆ 窗口；"
          "MZI 两臂 y 区间 ⊆ 窗口）",
          r_win_hi >= r_core_hi and r_win_lo <= g_ring["R"] - wg / 2.0
          and ring_arc_half <= sp["window_len"] / 2.0
          and m_lo <= -wg / 2.0 and m_hi >= g_mzi["dy"] + wg / 2.0,
          f"ring arc half={ring_arc_half:.4f}<= {sp['window_len'] / 2.0}")

    # A6 端留白公式现算对照
    exp_ring = (2.0 * math.pi * sp["R"] - sp["window_len"]) / 2.0
    mal = P._sens_p("SensingMZI", {})
    exp_mzi = (mal["Lu"] - mal["window_len"]) / 2.0
    check("A6 端留白 == (总光程 − window_len)/2（Ring 用周长 2πR 现算对照）",
          abs(g_ring["window_end_gap"] - exp_ring) < 1e-9
          and abs(g_mzi["window_end_gap"] - exp_mzi) < 1e-9,
          f"ring {g_ring['window_end_gap']:.6f} vs {exp_ring:.6f}")

    # ══════════════════════ B DRC 工艺规则 ══════════════════════
    win_keys = ("min_window_um", "min_window_margin_um",
                "min_window_end_um", "min_clad_enclosure_um")
    check("B1 四条窗口工艺规则 ∈ DEFAULT_RULES 且 > 0（可被 PDK 覆盖的设计规则层）",
          all(DEFAULT_RULES.get(k, 0) > 0 for k in win_keys), str(win_keys))

    r_ring = drc_check_device("SensingRing", {})
    r_mzi = drc_check_device("SensingMZI", {})
    check("B2 传感器件默认参数 DRC PASS（Ring 7 项 / MZI 6 项检查，0 违规）",
          r_ring.passed and r_mzi.passed
          and len(r_ring.checks) == 7 and len(r_mzi.checks) == 6
          and not r_ring.violations() and not r_mzi.violations(),
          f"ring {len(r_ring.checks)}/{len(r_ring.violations())} · "
          f"mzi {len(r_mzi.checks)}/{len(r_mzi.violations())}")

    enc = [c for c in r_ring.checks if c.rule == "min_clad_enclosure"]
    check("B3 开窗区包封实测 = 0（< 限值）但被**显式豁免**（waived=True · 记录豁免规则名）",
          len(enc) == 1 and enc[0].value == 0.0 and not enc[0].ok
          and enc[0].waived and enc[0].waived_by == "min_clad_enclosure"
          and len(r_ring.exceptions) == 1
          and r_ring.exceptions[0]["replaced_by"]
          == ["min_window_margin", "min_window_end"],
          f"waived={enc[0].waived if enc else None}")

    r_base = drc_check_device("RingResonator", {"R": 10.0})
    r_wg = drc_check_device("Waveguide", {"width": 0.5})
    check("B4 非传感器件**零影响**（RingResonator 3 项 / 无例外；Waveguide 1 项 / 无例外）",
          len(r_base.checks) == 3 and not r_base.exceptions and r_base.passed
          and len(r_wg.checks) == 1 and not r_wg.exceptions and r_wg.passed,
          f"ring {len(r_base.checks)} exc {len(r_base.exceptions)}")

    check("B5 报告自描述：brief 含「1 条工艺例外」；to_dict 含 exceptions 明细",
          "1 条工艺例外" in r_ring.brief()
          and len(r_ring.to_dict().get("exceptions", [])) == 1
          and r_ring.to_dict()["checks"][-1].get("waived") is True)

    d_base = r_base.to_dict()
    check("B6 🔴 向后兼容：非传感 DRC `to_dict()` **不含** exceptions / waived 键"
          "（既有受跟踪报告逐字节不漂移）",
          "exceptions" not in d_base
          and all("waived" not in c and "waived_by" not in c
                  for c in d_base["checks"]),
          f"keys={sorted(d_base.keys())}")

    # ══════════════════════ C 工艺例外护栏（"例外≠消音器"）══════════════════════
    try:
        validate_exceptions(WINDOW_EXCEPTIONS)
        ok_c1 = True
    except Exception:                                       # pragma: no cover
        ok_c1 = False
    check("C1 validate_exceptions 对已登记表通过（模块导入即校验，早失败）", ok_c1)

    def _raises(fn, exc):
        try:
            fn()
            return None
        except exc as e:
            return type(e).__name__
        except Exception as e:                              # pragma: no cover
            return f"WRONG:{type(e).__name__}"

    bad_empty_repl = DRCException(rule="min_clad_enclosure",
                                  scope=("SensingRing",), reason="r", replaced_by=())
    bad_empty_reason = DRCException(rule="min_clad_enclosure",
                                    scope=("SensingRing",), reason="  ",
                                    replaced_by=("min_window_margin",))
    bad_dangling = DRCException(rule="min_clad_enclosure", scope=("SensingRing",),
                                reason="r", replaced_by=("no_such_rule",))
    bad_rule = DRCException(rule="not_a_rule", scope=("SensingRing",),
                            reason="r", replaced_by=("min_window_margin",))
    e1 = _raises(lambda: validate_exceptions((bad_empty_repl,)), ValueError)
    e2 = _raises(lambda: validate_exceptions((bad_empty_reason,)), ValueError)
    e3 = _raises(lambda: validate_exceptions((bad_dangling,)), ValueError)
    e4 = _raises(lambda: validate_exceptions((bad_rule,)), ValueError)
    check("C2 缺 replaced_by（=消音器）⇒ ValueError",
          e1 == "ValueError", str(e1))
    check("C3 缺 reason（无理由豁免）⇒ ValueError", e2 == "ValueError", str(e2))
    check("C4 悬空引用（rule / replaced_by 不在 CHECK_RULES）⇒ ValueError",
          e3 == "ValueError" and e4 == "ValueError", f"{e3}/{e4}")

    # C5：合法但本次**未评估**的替代规则 ⇒ RuntimeError（漏跑不给假绿）
    late = DRCException(rule="min_clad_enclosure", scope=("SensingRing",),
                        reason="r", replaced_by=("min_pad",))
    e5 = _raises(lambda: drc_check_device("SensingRing", {}, exceptions=(late,)),
                 RuntimeError)
    check("C5 替代规则合法但本次未评估（min_pad）⇒ RuntimeError（防漏跑假绿）",
          e5 == "RuntimeError", str(e5))

    # C6：例外可**真的**关闭 —— 关掉后包封规则必须判红
    r_off = drc_check_device("SensingRing", {}, exceptions=())
    check("C6 🔴 `exceptions=()` 必须让包封规则**真的判红**"
          "（证明豁免由例外对象运行时施加，非硬编码 ⇒ 例外可关闭）",
          not r_off.passed
          and [c.rule for c in r_off.violations()] == ["min_clad_enclosure"]
          and not r_off.exceptions,
          f"violations={[c.rule for c in r_off.violations()]}")

    # ══════════════════════ D 反向探针（DRC 能变红）══════════════════════
    p_narrow = drc_check_device("SensingRing", {"window_w": 0.5})
    p_margin = drc_check_device("SensingRing", {"wg_width": 2.6, "window_w": 3.0})
    p_end = drc_check_device("SensingRing", {"window_len": 62.0})
    p_R = drc_check_device("SensingRing", {"R": 1.0})
    check("D1 窗口过窄（0.5 < 1.0）⇒ min_window 必红",
          "min_window" in [c.rule for c in p_narrow.violations()],
          str([c.rule for c in p_narrow.violations()]))
    check("D2 窗口边余量不足（(3.0−2.6)/2=0.2 边界以下）⇒ min_window_margin 必红",
          "min_window_margin" in [c.rule for c in p_margin.violations()],
          str([c.rule for c in p_margin.violations()]))
    check("D3 窗口触及端口（len 62 ≫ 周长）⇒ min_window_end 必红",
          "min_window_end" in [c.rule for c in p_end.violations()],
          str([c.rule for c in p_end.violations()]))
    check("D4 环半径过小（1.0 < 5.0）⇒ 基础规则 min_bend_R 仍必红"
          "（例外只豁免包封一项，不豁免几何）",
          "min_bend_R" in [c.rule for c in p_R.violations()],
          str([c.rule for c in p_R.violations()]))

    # ══════════════════════ E PDK 器件本体 ══════════════════════
    from lda_pdk.registry import (                          # noqa: E402
        BUILTIN_DEVICE_ENTRIES, builtin_registry,
    )
    from lda_l2.pdk_examples import build_example_registry   # noqa: E402
    from lda_l2.drc import rules_from_pdk                    # noqa: E402

    ids = [e.id for e in BUILTIN_DEVICE_ENTRIES]
    reg = builtin_registry()
    e_ring = reg.get("lda.SensingRing")
    check("E1 内置器件本体含 lda.SensingRing / lda.SensingMZI（class=C · layers 含 WINDOW）",
          ids == ["lda.SensingRing", "lda.SensingMZI"]
          and e_ring is not None and e_ring.sovereign_class == "C"
          and "WINDOW" in e_ring.layers
          and reg.get("lda.SensingMZI") is not None,
          str(ids))
    check("E2 🔴 单一真源纪律：内置条目 `params` 空（不复制数值）+ note 指向真源模块",
          all(not e.params for e in BUILTIN_DEVICE_ENTRIES)
          and all("lda_l2.primitives" in e.note and "lda_l2.drc" in e.note
                  for e in BUILTIN_DEVICE_ENTRIES))

    exreg = build_example_registry()
    pdk = exreg.get("NOEIC(演示近似)::SOI 180nm")
    rp = rules_from_pdk(pdk)
    check("E3 工艺规则可被 PDK 覆盖（NOEIC 示例 PDK 给出四条窗口规则，"
          "rules_from_pdk 现算生效）",
          all(abs(rp[k] - DEFAULT_RULES[k]) < 1e-12 for k in win_keys),
          f"{[rp[k] for k in win_keys]}")

    check("E4 CHECK_RULES 收录四条窗口检查项 + 包封项（例外引用域封闭）",
          all(r in CHECK_RULES for r in
              ("min_window", "min_window_margin", "min_window_end",
               "min_clad_enclosure")),
          str(CHECK_RULES))

    # ══════════════════════ G 自入 CI core ══════════════════════
    ci = os.path.join(_HERE, "run_ci_regression.py")
    with open(ci, encoding="utf-8") as f:
        ck = f.read()
    check("G1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ps_m1_smoke.py" in ck)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
