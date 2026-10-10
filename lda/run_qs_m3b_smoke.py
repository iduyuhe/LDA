#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M3b（G5 器件本体）· 量子传感专用 PDK 器件（NV 柱 / 光子晶体腔 / 微波天线）门禁（v0.9.220）。

═══ 判什么（分节）═══
A 几何与**单一真源**（三器件 geometry 派生量由主参数算出 / descs 图元数与几何自洽 /
  **层号跨源一致** / descs ↔ geometry 同源 / **无释放层**（NV 柱是金刚石膜结构非悬浮膜））·
B DRC 规则（九条新检查项 · 三器件默认点 0 违规 · 柱径走**专用**规则名而非通用
  min_width（防「口径错 ⇒ 结论反向」）· **既有 PS-M9 四器件零影响** · 报告自描述）·
C PDK 器件本体（三条内置条目 · `params` **恒空**（防数值副本漂移）· layers / tags /
  note 真源指针）·
D 🔴 **harness/物理 ↔ L2 单一真源对拍**（NV 柱柱高 h 由 `qs_m3.optimal_depth_closed`
  的**最优色心深度 d\\*** 现算派生；真源漂移反向探针）·
E **单位口径**（腔 web / 孔半径以 µm 与 DRC 限值同单位；防 nm/µm 混比）·
F 反向探针（柱径过小 / 柱过高 / 锥角过陡 / 柱间距过小 / 基底过窄 / 锚定过短 /
  腔壁厚过薄 / 腔孔过小 / 天线间距过小 / 线宽过细 ⇒ 各自**必红**且红在**期望规则**）·
G 自入 CI core（防静默漏接）。

═══ 🔴 锚账本口径（本档**零净增锚**）═══
QS-M3b 是**器件本体 / 工艺规则**里程碑，不是新物理锚：NV 柱柱高由 QS-M3 的
最优色心深度 d\\*（账本锚 B476 的物理量）**现算派生**；腔增强 Purcell 量与账本锚
**B18 同物理量**；微波天线几何与 QS-M1 微波噪声链同源。因此本档**不动账本**
（495 / strict 473 / 降级 3 / 自证桩 19 不变），只 +1 条 CI core 门禁（311→312）。

═══ 诚实边界 ═══
· 器件几何为**设计示例**（柱径 0.30 µm / 柱高 ≈ d\\*+0.12 / 腔周期 320 nm / 环半径 20 µm），
  可制造性规则为**工艺常识建模**，非任何 foundry 的真实金刚石/悬浮工艺 deck。
· 🔴 本档**不做**任何器件级性能宣称（灵敏度 / Purcell 增强 / 自旋相干时间）。
· 🔴 单位红线：孔周期/半径以 nm 输入，可制造性派生量一律换算 µm。
"""
from __future__ import annotations

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

KINDS = ("NVPillar", "NVCavity", "MWAntenna")


def main() -> int:
    from lda_l2 import drc as DRC
    from lda_l2 import gds_export as GX
    from lda_l2 import primitives as PR
    from lda_l2 import qs_m3
    from lda_l2.qs_m3b import (
        pillar_height_consistency,
        selfcheck_qs_m3b,
    )
    from lda_pdk.registry import BUILTIN_DEVICE_ENTRIES, builtin_registry

    # ══ A 几何与单一真源 ══════════════════════════════════════════════════
    g = {k: PR.qs_device_geometry(k, {}) for k in KINDS}
    d = {k: PR.qs_device_descs(k, {}) for k in KINDS}
    check("A1 三器件几何可生成（geometry + descs 均非空）",
          all(g[k] and d[k] for k in KINDS),
          "descs 图元数 = %s" % {k: len(d[k]) for k in KINDS})

    # 派生量由主参数算出（不许各自写值）
    _gc = g["NVCavity"]
    check("A2 派生量由主参数算出（cavity min_web = (period − 2·hole_r)/1000 µm）",
          abs(_gc["min_web"] - (_gc["period"] - 2.0 * _gc["hole_r"]) / 1000.0) < 1e-12,
          "min_web=%.4f µm" % _gc["min_web"])

    _gp = g["NVPillar"]
    check("A3 派生量由主参数算出（pillar base_overhang = (base_w − dia − 2·sidewall)/2）",
          abs(_gp["base_overhang"]
              - (_gp["base_w"] - _gp["dia"] - 2.0 * _gp["sidewall"]) / 2.0) < 1e-12,
          "base_overhang=%.3f µm" % _gp["base_overhang"])

    _layers = {k: {x["layer"] for x in d[k]} for k in KINDS}
    check("A4 天线/柱含金属层，腔仅芯层（层号如实）",
          _layers["MWAntenna"] == {GX.LIB_LAYER_METAL}
          and GX.LIB_LAYER_SI in _layers["NVPillar"]
          and _layers["NVCavity"] == {GX.LIB_LAYER_SI},
          "layers = %s" % _layers)

    check("A5 🔴 层号**跨源一致**（primitives 经 gds_export 取层号，非手写数值）",
          GX.LIB_LAYER_SI == 1 and GX.LIB_LAYER_METAL == 3,
          "SI=%s METAL=%s" % (GX.LIB_LAYER_SI, GX.LIB_LAYER_METAL))

    check("A6 🔴 **无释放层**出现（NV 柱是金刚石膜上结构，非悬浮膜）",
          all(GX.LIB_LAYER_RELEASE not in _layers[k] for k in KINDS),
          "release=%s" % GX.LIB_LAYER_RELEASE)

    check("A7 descs ↔ geometry **同源**（腔 hole_r_um 与版图孔半径一致）",
          abs(_gc["hole_r_um"] - _gc["hole_r"] / 1000.0) < 1e-12,
          "hole_r_um=%.4f µm" % _gc["hole_r_um"])

    # ══ B DRC ═══════════════════════════════════════════════════════════
    _res = {k: DRC.drc_check_device(k, {}) for k in KINDS}
    check("B1 三器件默认档 0 违规（PASS）",
          all(r.passed and not r.violations() for r in _res.values()),
          " · ".join("%s:%d项" % (k, len(_res[k].checks)) for k in KINDS))

    _new_rules = ("min_pillar_dia", "max_pillar_height", "max_taper_angle",
                  "min_pillar_gap", "min_base_overhang", "min_cavity_web",
                  "min_cavity_hole", "min_antenna_gap", "min_antenna_trace")
    check("B2 CHECK_RULES 含九条新检查项",
          all(r in DRC.CHECK_RULES for r in _new_rules),
          "CHECK_RULES n=%d" % len(DRC.CHECK_RULES))

    _pillar_rules = {c.rule for c in _res["NVPillar"].checks}
    check("B3 🔴 柱径走**专用**规则名（min_pillar_dia），不落通用 min_width ⇒ 不被误判",
          "min_pillar_dia" in _pillar_rules and "min_width" not in _pillar_rules,
          "rules = %s" % sorted(_pillar_rules))

    check("B4 🔴 既有 PS-M9 四器件**零影响**（检查项数不变、仍 PASS）",
          {k: (DRC.drc_check_device(k, {}).passed,
               len(DRC.drc_check_device(k, {}).checks))
           for k in ("SlotWaveguide", "SuspendedWaveguide",
                     "SlotRing", "SuspendedRing")}
          == {"SlotWaveguide": (True, 2), "SuspendedWaveguide": (True, 5),
              "SlotRing": (True, 4), "SuspendedRing": (True, 7)},
          "checks = %s" % {k: len(DRC.drc_check_device(k, {}).checks) for k in KINDS})

    _base = {k: (DRC.drc_check_device(k, {}).passed,
                 len(DRC.drc_check_device(k, {}).checks))
             for k in ("Waveguide", "RingResonator", "MZI")}
    check("B5 既有基础器件**零影响**（检查项数不变、仍 PASS）",
          _base == {"Waveguide": (True, 1), "RingResonator": (True, 3),
                    "MZI": (True, 2)},
          "%s" % _base)

    _miss = [c.rule for c in _res["NVPillar"].checks if not c.ok]
    check("B6 DRC 报告自描述（无违规 ⇒ 无未豁免红项）", not _miss, "%s" % _miss)

    # ══ C PDK 器件本体 ═══════════════════════════════════════════════════
    _ids = [e.id for e in BUILTIN_DEVICE_ENTRIES]
    check("C1 三条量子传感器件条目已内置",
          all("lda.%s" % k in _ids for k in KINDS),
          "内置条目 n=%d" % len(_ids))

    _new = [e for e in BUILTIN_DEVICE_ENTRIES
            if e.id in ("lda.NVPillar", "lda.NVCavity", "lda.MWAntenna")]
    check("C2 🔴 `params` **恒空**（几何真源在 primitives / 物理量真源在 qs_m3·qs_m1 ⇒ 不复制数值）",
          all(e.params == {} for e in _new),
          "非空项 = %s" % [e.id for e in _new if e.params])

    check("C3 layers 如实（天线含 METAL；柱含 SI+METAL；腔仅 SI）",
          all("METAL" in e.layers for e in _new if "Antenna" in e.id)
          and all("SI" in e.layers and "METAL" in e.layers
                  for e in _new if "Pillar" in e.id)
          and all(e.layers == ["SI"] for e in _new if "Cavity" in e.id))

    _reg = builtin_registry()
    check("C4 tags 可检出（query(tag='qs-m3b') 恰 3 条）",
          len(_reg.query(tag="qs-m3b")) == 3)

    check("C5 note 给出**真源指针**（primitives + qs_m3/qs_m1 物理量真源）",
          all("primitives." in e.note
              and ("qs_m3" in e.note or "qs_m1" in e.note) for e in _new))

    # ══ D harness/物理 ↔ L2 单一真源 ══════════════════════════════════════
    _c = pillar_height_consistency()
    _d_star = qs_m3.optimal_depth_closed(PR.NV_D0_NM, PR.NV_D_ATT_NM)
    check("D1 🔴 NV 柱柱高 h = qs_m3 最优深度 d\\*（现算）+ 柱顶余量（**同源对拍**）",
          abs(_c["recon_d_star_nm"] - _d_star) < 1e-9
          and abs(_c["h_pillar_um"] - (_d_star / 1000.0 + _c["h_top_um"])) < 1e-12,
          "d*=%.4f nm · h=%.4f µm（h_top=%.4f）"
          % (_d_star, _c["h_pillar_um"], _c["h_top_um"]))

    check("D2 🔴 深度真源常量与 qs_m3 默认形参**同源**（NV_D0_NM/NV_D_ATT_NM == 20/200）",
          (PR.NV_D0_NM, PR.NV_D_ATT_NM) == (20.0, 200.0)
          and abs(qs_m3.optimal_depth_closed(20.0, 200.0)
                  - qs_m3.optimal_depth_closed(PR.NV_D0_NM, PR.NV_D_ATT_NM)) < 1e-12,
          "d0=%.1f d_att=%.1f" % (PR.NV_D0_NM, PR.NV_D_ATT_NM))

    # 真源漂移反向探针：篡改 h_top ⇒ 一致性判据（现算）必变
    _h_ok = abs(_c["h_pillar_um"] - (_d_star / 1000.0 + _c["h_top_um"])) < 1e-12
    _saved = PR.NV_PILLAR_DEFAULTS["h_top_um"]
    PR.NV_PILLAR_DEFAULTS["h_top_um"] = _saved + 0.5
    _c2 = pillar_height_consistency()
    _h_drift = abs(_c2["h_pillar_um"] - (_d_star / 1000.0 + _c2["h_top_um"])) < 1e-12
    PR.NV_PILLAR_DEFAULTS["h_top_um"] = _saved
    check("D3 🔴 反向探针：真源漂移必被检出（柱高与 d* 再次对拍一致）",
          _h_ok and _h_drift
          and abs(pillar_height_consistency()["h_pillar_um"] - _c["h_pillar_um"]) < 1e-12,
          "h 复原 = %.4f µm" % pillar_height_consistency()["h_pillar_um"])

    # ══ E 单位口径 ══════════════════════════════════════════════════════
    check("E1 🔴 腔 web/孔半径以 µm 口径（与 DRC 限值同单位，防 nm/µm 混比）",
          0.0 < _gc["min_web"] < 1.0 and 0.0 < _gc["hole_r_um"] < 1.0,
          "min_web=%.4f µm · hole_r_um=%.4f µm" % (_gc["min_web"], _gc["hole_r_um"]))

    _web_rule = [c for c in _res["NVCavity"].checks if c.rule == "min_cavity_web"]
    check("E2 🔴 DRC 实测 web 值与 geometry 同源（不是 nm 当 µm）",
          bool(_web_rule) and abs(_web_rule[0].value - _gc["min_web"]) < 1e-12,
          "DRC value=%.4f vs geometry=%.4f"
          % (_web_rule[0].value if _web_rule else -1.0, _gc["min_web"]))

    # ══ F 反向探针（各自必红且红在期望规则）═══════════════════════════════
    _cases = [
        ("F1 柱径过小（0.10 < 0.20）", "NVPillar", {"dia_um": 0.10}, "min_pillar_dia"),
        ("F2 柱过高（2.0 > 0.50）", "NVPillar", {"h_um": 2.0, "h_top_um": 1.5},
         "max_pillar_height"),
        ("F3 锥角过陡（35 > 20）", "NVPillar", {"taper_deg": 35.0}, "max_taper_angle"),
        ("F4 柱间距过小（0.20 < 0.40）", "NVPillar", {"gap_um": 0.20}, "min_pillar_gap"),
        ("F5 柱基底过窄（base_w=0.30 ⇒ 外扩为负）", "NVPillar",
         {"base_w_um": 0.30}, "min_base_overhang"),
        ("F6 锚定过短（0.3 < 1.0）", "NVPillar", {"anchor_len_um": 0.3}, "min_anchor_len"),
        ("F7 腔壁厚过薄（hole_r=145nm ⇒ web<0.05）", "NVCavity",
         {"hole_r_nm": 145.0}, "min_cavity_web"),
        ("F8 腔孔过小（30nm < 50nm）", "NVCavity", {"hole_r_nm": 30.0}, "min_cavity_hole"),
        ("F9 天线间距过小（0.30 < 0.60）", "MWAntenna", {"gap_um": 0.30}, "min_antenna_gap"),
        ("F10 天线线宽过细（0.20 < 0.50）", "MWAntenna",
         {"trace_w_um": 0.20}, "min_antenna_trace"),
    ]
    _bad = []
    for _desc, _k, _p, _rule in _cases:
        _r = DRC.drc_check_device(_k, _p)
        _hit = [c.rule for c in _r.violations()]
        if _rule not in _hit:
            _bad.append("%s（期望 %s，实得 %s）" % (_desc, _rule, _hit))
        check(_desc + " ⇒ 必红且红在 " + _rule, _rule in _hit, "违规 = %s" % _hit)
    check("F11 十条反向探针**全部**命中**期望规则**（判据有鉴别力）", not _bad, "%s" % _bad)

    # ══ G 自入 CI core ════════════════════════════════════════════════════
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as f:
        _ci = f.read()
    check("G1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_qs_m3b_smoke.py" in _ci)

    # ══ H 模块自检直连（22 项）════════════════════════════════════════════
    _sc = selfcheck_qs_m3b()
    check("H1 qs_m3b.selfcheck_qs_m3b 全项 PASS（%d 项）" % len(_sc),
          all(_sc.values()),
          "FAIL = %s" % [k for k, v in _sc.items() if not v])

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
