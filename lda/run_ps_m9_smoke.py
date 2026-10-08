#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PS-M9（G2 器件本体）· 高灵敏几何器件（slot / suspended × 波导 / 谐振环）门禁（v0.9.211）。

═══ 判什么（分节）═══
A 几何与**单一真源**（四器件 geometry 派生量由主参数算出 / descs 图元数与几何自洽 /
  释放层仅在 suspended 类出现 / **层号跨源一致** / descs ↔ geometry 同源 /
  释放开孔**不得覆盖锚定块**）·
B DRC 规则（六条新检查项 · 四器件默认点 0 违规 · 狭缝走**专用**规则名而非通用
  min_width（防「口径错 ⇒ 结论反向」）· **既有器件零影响** · 报告自描述）·
C PDK 器件本体（四条内置条目 · `params` **恒空**（防数值副本漂移）· layers / tags /
  note 真源指针）·
D 🔴 **harness ↔ L2 单一真源对拍**（`_batch_b38_numeric._DEFAULTS` 逐键 == `primitives.
  WAVEGUIDE_XS_DEFAULTS`；harness 顶层 **scipy-free**（子进程实测）；真源漂移反向探针）·
E **灵敏度如实口径**（诚实梯度：suspended ≫ slot；狭缝**不**天然高灵敏；10³ nm/RIU 门槛
  在本参数空间**不可达** —— 均现算 golden）·
F 反向探针（狭缝过窄 / rail 过窄 / 支撑过窄 / 悬空跨度过长 / 锚定过短 /
  释放开孔开穿锚定块 ⇒ 各自**必红**）·
G 自入 CI core（防静默漏接）。

═══ 🔴 锚账本口径（本档**零净增锚**）═══
PS-M9 是**器件本体 / 工艺规则**里程碑，不是新物理锚：三种几何的折射率灵敏度早已由
B469（thin-wire）/ B470（slot）/ B471（suspended）锚定（golden = 一阶本征值微扰闭式 ×
FV-FD 重解差商候选，方法学独立）。因此本档**不动账本**（490 / strict 468 / 桩 19 不变），
只 +1 条 CI core 门禁。

═══ 编号说明（防误挂）═══
PS 征程 M0–M8 已全部落地（M0 基线 / M1 开窗工艺 / M2 指标框架 / M3 灵敏度物理链 /
M4 功能化 / M5 微流控 / M6 规模 / M7 WebUI 面板 / M8 几何半锚）；本档为 **M9**，
专补 M8 遗留的「真实 slot/suspended **PDK 器件本体**」。

═══ 诚实边界 ═══
· 器件几何为**设计示例**（L=20 µm / R=10 µm / rail=0.22 / gap=0.05 / h=0.22），
  支撑与释放开孔为**可制造性常识建模**，非任何 foundry 的真实悬浮工艺 deck。
· 🔴 **灵敏度口径**：本族 S = dn_eff/dn_a（**bulk** 灵敏度），国际先进 100–500 nm/RIU。
  常被宣传的「slot/suspended ≥10³ nm/RIU」是 **surface / Vernier 口径**，量纲不同
  **禁止混比**（路线图 §5 已警告）。本门禁**不做**任何器件级性能宣称。
· 10³ 门槛的换算需 n_g（色散）；本门禁取 n_g=4.2 作**导出系数**并如实标注为量级参考。
"""
from __future__ import annotations

import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

KINDS = ("SlotWaveguide", "SuspendedWaveguide", "SlotRing", "SuspendedRing")
SLOT_KINDS = ("SlotWaveguide", "SlotRing")
SUSP_KINDS = ("SuspendedWaveguide", "SuspendedRing")


def _parity(b38, xs) -> bool:
    """harness `_DEFAULTS` 与 L2 真源逐键一致（`Lhalf_um` 是求解窗口，不属截面真源）。"""
    for k in ("strip", "thinwire", "slot", "suspended"):
        a = {kk: vv for kk, vv in b38._DEFAULTS[k].items() if kk != "Lhalf_um"}
        if a != dict(xs[k]):
            return False
    return True


def main() -> int:
    from lda_l2 import drc as DRC
    from lda_l2 import gds_export as GX
    from lda_l2 import primitives as PR
    from lda_pdk.registry import BUILTIN_DEVICE_ENTRIES, builtin_registry
    from lda_harness import _batch_b38_numeric as B38

    # ══ A 几何与单一真源 ══════════════════════════════════════════════════
    g = {k: PR.high_sens_geometry(k, {}) for k in KINDS}
    d = {k: PR.high_sens_descs(k, {}) for k in KINDS}
    check("A1 四器件几何可生成（geometry + descs 均非空）",
          all(g[k] and d[k] for k in KINDS),
          "descs 图元数 = %s" % {k: len(d[k]) for k in KINDS})

    check("A2 派生量由主参数算出（release_extent = L + 2·anchor_len）",
          abs(g["SuspendedWaveguide"]["release_extent"]
              - (g["SuspendedWaveguide"]["suspended_span"]
                 + 2 * g["SuspendedWaveguide"]["anchor_len"])) < 1e-12,
          "release_extent=%.3f" % g["SuspendedWaveguide"]["release_extent"])

    check("A3 狭缝 rail_width 与 min_width 同源（不许各自写值）",
          all(g[k]["min_width"] == g[k]["rail_width"] for k in SLOT_KINDS)
          and all(g[k]["min_space"] == g[k]["slot_gap"] for k in SLOT_KINDS))

    _layers = {k: {x["layer"] for x in d[k]} for k in KINDS}
    check("A4 释放层**仅**在 suspended 类出现（狭缝不需要去衬底）",
          all(_layers[k] == {GX.LIB_LAYER_SI, GX.LIB_LAYER_RELEASE} for k in SUSP_KINDS)
          and all(_layers[k] == {GX.LIB_LAYER_SI} for k in SLOT_KINDS),
          "layers = %s" % _layers)

    check("A5 🔴 层号**跨源一致**（primitives._LAYER_RELEASE == gds_export.LIB_LAYER_RELEASE）",
          PR._LAYER_RELEASE == GX.LIB_LAYER_RELEASE,
          "primitives=%s gds_export=%s" % (PR._LAYER_RELEASE, GX.LIB_LAYER_RELEASE))

    _rl = [x for x in d["SuspendedWaveguide"] if x["layer"] == GX.LIB_LAYER_RELEASE]
    _rr = _rl[0]["rings_um"][0]
    _xs = [p[0] for p in _rr]
    _ys = [p[1] for p in _rr]
    check("A6 释放开孔 ↔ geometry **同源**（y 半宽 == release_half_w）",
          len(_rl) == 1
          and abs(max(_ys) - g["SuspendedWaveguide"]["release_half_w"]) < 1e-12
          and abs(min(_ys) + g["SuspendedWaveguide"]["release_half_w"]) < 1e-12,
          "y ∈ [%.3f, %.3f]" % (min(_ys), max(_ys)))

    _al = g["SuspendedWaveguide"]["anchor_len"]
    _L = g["SuspendedWaveguide"]["suspended_span"]
    check("A7 🔴 释放开孔**不得覆盖锚定块**（x 严格落在悬浮段内）",
          abs(min(_xs) - _al) < 1e-12 and abs(max(_xs) - (_al + _L)) < 1e-12,
          "x ∈ [%.3f, %.3f]，锚定段 [0,%.1f] ∪ [%.1f,%.1f]"
          % (min(_xs), max(_xs), _al, _al + _L, 2 * _al + _L))

    _rel = [x for x in d["SuspendedRing"] if x["layer"] == GX.LIB_LAYER_RELEASE]
    _spoke = [x for x in d["SuspendedRing"] if x["layer"] == GX.LIB_LAYER_SI]
    check("A8 SuspendedRing 释放开孔**分段**（4 段弧）且有芯层支撑结构",
          len(_rel) == 4 and len(_spoke) >= 5,
          "release 弧段=%d · Si 图元=%d" % (len(_rel), len(_spoke)))

    # ══ B DRC ═══════════════════════════════════════════════════════════
    _res = {k: DRC.drc_check_device(k, {}) for k in KINDS}
    check("B1 四器件默认档 0 违规（PASS）",
          all(r.passed and not r.violations() for r in _res.values()),
          " · ".join("%s:%d项" % (k, len(_res[k].checks)) for k in KINDS))

    _new_rules = ("min_rail_width", "min_slot_gap", "min_support_width",
                  "max_suspended_span", "min_anchor_len", "min_support_overhang")
    check("B2 CHECK_RULES 含六条新检查项",
          all(r in DRC.CHECK_RULES for r in _new_rules),
          "CHECK_RULES n=%d" % len(DRC.CHECK_RULES))

    _slot_rules = {c.rule for k in SLOT_KINDS for c in _res[k].checks}
    check("B3 🔴 狭缝走**专用**规则名（rail/gap），不落通用 min_width ⇒ 不被误判",
          "min_rail_width" in _slot_rules and "min_slot_gap" in _slot_rules
          and "min_width" not in _slot_rules,
          "rules = %s" % sorted(_slot_rules))

    _base = {k: (DRC.drc_check_device(k, {}).passed,
                 len(DRC.drc_check_device(k, {}).checks))
             for k in ("Waveguide", "RingResonator", "MZI")}
    check("B4 既有器件**零影响**（检查项数不变、仍 PASS）",
          _base == {"Waveguide": (True, 1), "RingResonator": (True, 3),
                    "MZI": (True, 2)},
          "%s" % _base)

    _miss = [c.rule for c in _res["SuspendedWaveguide"].checks if not c.ok]
    check("B5 DRC 报告自描述（无违规 ⇒ 无未豁免红项）", not _miss, "%s" % _miss)

    # ══ C PDK 器件本体 ═══════════════════════════════════════════════════
    _ids = [e.id for e in BUILTIN_DEVICE_ENTRIES]
    check("C1 四条高灵敏器件条目已内置",
          all("lda.%s" % k in _ids for k in KINDS),
          "内置条目 n=%d" % len(_ids))

    _new = [e for e in BUILTIN_DEVICE_ENTRIES if e.id.startswith("lda.Slot")
            or e.id.startswith("lda.Suspended")]
    check("C2 🔴 `params` **恒空**（几何真源在 primitives / 灵敏度真源在账本锚 ⇒ 不复制数值）",
          all(e.params == {} for e in _new), "非空项 = %s" % [e.id for e in _new if e.params])

    check("C3 layers 如实（suspended 类含 RELEASE，狭缝类不含）",
          all("RELEASE" in e.layers for e in _new
              if "Suspended" in e.id)
          and all("RELEASE" not in e.layers for e in _new if "Slot" in e.id))

    _reg = builtin_registry()
    check("C4 tags 可检出（query(tag='ps-m9') 恰 4 条）",
          len(_reg.query(tag="ps-m9")) == 4)

    check("C5 note 给出**真源指针**（primitives + 账本锚号）",
          all(("primitives." in e.note and "B47" in e.note) for e in _new))

    # ══ D harness ↔ L2 单一真源 ═══════════════════════════════════════════
    xs = PR.WAVEGUIDE_XS_DEFAULTS
    check("D1 🔴 harness `_DEFAULTS` 与 L2 真源**逐键相等**（除求解窗口 Lhalf_um）",
          _parity(B38, xs),
          "harness slot = %s" % {kk: vv for kk, vv in B38._DEFAULTS["slot"].items()
                                 if kk != "Lhalf_um"})

    _code = ("import sys, lda_harness._batch_b38_numeric as m; "
             "print('SCIPY' if 'scipy' in sys.modules else 'CLEAN')")
    _env = dict(os.environ)
    _env["PYTHONPATH"] = _HERE + os.pathsep + _env.get("PYTHONPATH", "")
    _p = subprocess.run([sys.executable, "-c", _code], capture_output=True,
                        text=True, env=_env, timeout=120)
    check("D2 harness 顶层 **scipy-free**（子进程实测，闭式门禁依赖隔离）",
          _p.stdout.strip().endswith("CLEAN"), "%s" % _p.stdout.strip()[:40])

    _ok0 = _parity(B38, xs)
    _saved = B38._DEFAULTS["suspended"]["w_um"]
    B38._DEFAULTS["suspended"]["w_um"] = float(xs["suspended"]["w_um"]) + 0.01
    _ok1 = _parity(B38, xs)
    B38._DEFAULTS["suspended"]["w_um"] = _saved
    check("D3 反向探针：真源**漂移**必判红（防「两份副本悄悄分家」）",
          _ok0 and not _ok1 and _parity(B38, xs))

    # ══ E 灵敏度如实口径（现算 golden）═══════════════════════════════════
    s_slot = float(B38.geometry_sensitivity_golden("slot"))
    s_susp = float(B38.geometry_sensitivity_golden("suspended"))
    s_strip = float(B38.geometry_sensitivity_golden("strip"))
    check("E1 诚实梯度：suspended ≫ 狭缝（去衬底是唯一大幅增强杠杆）",
          s_susp > 1.5 * s_slot,
          "suspended=%.6f vs slot=%.6f（%.2f×）" % (s_susp, s_slot, s_susp / s_slot))

    check("E2 🔴 狭缝**不**天然高灵敏（同口径下 slot ≲ strip，与「slot 天生高灵敏」的直觉相反）",
          s_slot <= s_strip * 1.05,
          "slot=%.6f strip=%.6f" % (s_slot, s_strip))

    _coef = 1550.0 / 4.2                      # nm/RIU per unit S（n_g=4.2 外部假设，量级参考）
    _gate = 1000.0 / _coef                    # 10³ nm/RIU ⇔ S ≥ 2.7097
    _s_base = max(s_susp, s_slot, s_strip)    # 基线三档（_DEFAULTS 默认几何）
    # 🔴 「天花板」必须名副其实：suspended 唯一有效增强维 = w_um；7 点扫描（0.25–0.60，
    #    w=0.25 无受限导模 ⇒ nan 已排除）实测最优 w=0.35 ⇒ 现算该点与基线取 max，
    #    使「门槛不可达」的余量按**真实上界**判定（口径错一处 ⇒ 余量判断反向）。
    _p_bound = dict(B38._DEFAULTS["suspended"])
    _p_bound["w_um"] = 0.35
    _s_bound = max(_s_base,
                   float(B38.geometry_sensitivity_golden("suspended", _p_bound)))
    check("E3 🔴 「10³ nm/RIU」门槛在**本参数空间不可达**（扫描上界点 < 门槛）",
          _s_bound < _gate,
          "S_bound=%.4f（=%.0f nm/RIU，达成率 %.1f%%）< 门槛 S=%.4f（=1000 nm/RIU）"
          % (_s_bound, _s_bound * _coef, 100.0 * _s_bound / _gate, _gate))

    # ══ F 反向探针（各自必红）═════════════════════════════════════════════
    # 🔴 每条探针**断言命中的具体规则**（不只「有违规」）—— 否则「红对了但红在别的规则上」
    #    这种事会被漏过（本档初版 F3 即如此：标称支撑过窄，实际先被 min_support_overhang 拦下）。
    _cases = [
        ("F1 狭缝 gap 过窄（0.01 < 0.04）", "SlotWaveguide", {"gap_um": 0.01},
         "min_slot_gap"),
        ("F2 狭缝 rail 过窄（0.10 < 0.15）", "SlotWaveguide", {"w_rail_um": 0.10},
         "min_rail_width"),
        ("F3 支撑块过窄（0.45 < 0.50）", "SuspendedWaveguide", {"support_w_um": 0.45},
         "min_support_width"),
        ("F4 悬空跨度过长（80 > 50）", "SuspendedWaveguide", {"L_um": 80.0},
         "max_suspended_span"),
        ("F5 锚定段过短（0.3 < 1.0）", "SuspendedWaveguide", {"anchor_len_um": 0.3},
         "min_anchor_len"),
        ("F6 释放开孔**开穿锚定块**（support_w=0.9 ⇒ 支撑外扩为负）",
         "SuspendedWaveguide", {"support_w_um": 0.90}, "min_support_overhang"),
    ]
    _bad = []
    for _desc, _k, _p, _rule in _cases:
        _r = DRC.drc_check_device(_k, _p)
        _hit = [c.rule for c in _r.violations()]
        if _rule not in _hit:
            _bad.append("%s（期望 %s，实得 %s）" % (_desc, _rule, _hit))
        check(_desc + " ⇒ 必红且红在 " + _rule, _rule in _hit, "违规 = %s" % _hit)
    check("F7 六条反向探针**全部**命中**期望规则**（判据有鉴别力）", not _bad, "%s" % _bad)

    # ══ G 自入 CI core ════════════════════════════════════════════════════
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as f:
        _ci = f.read()
    check("G1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ps_m9_smoke.py" in _ci)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
