#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QS-M4（G6 阵列/集成）· 量子传感器 **2×N 磁力计阵列** 门禁（v0.9.221）。

═══ 判什么（分节）═══
A 阵列布局与**单一真源**（柱心坐标现算 / 居中对称 / 节距单调 / 通道号连续唯一 /
  **柱径委派 primitives**（不复制数值）· 版图复用 QS-M3b NVPillar 单器件本体 ·
  馈线数 = 行数 · descs ↔ positions 同源）·
B 串扰物理（闭式 X=(d_crit/r)³ ∧ **数值链点偶极积分** 一致 · 立方律 X(2r)=X(r)/8 ·
  r=d_crit ⇒ X=1 · 随 r 单调降 · 对称阵各通道 X_tot 相同 · **按所有对累计不截断** ·
  串扰恶化灵敏度 η_eff=η√(1+X_tot²) ≥ η_single）·
C 多通道读出 mux（思路**复用 sc_readout_mux（D-140）** · 同馈线音唯一 · 音间隔 ≥ 下限 ·
  音落带 · 音数 = 通道数）·
D 梯度计（闭式 CMRR=20log₁₀(1/ε) ∧ **数值链** 一致 · ε↓⇒CMRR↑ · 边界 ε=1⇒0 dB /
  ε=0.01⇒40 dB · 基线短 ⇒ 梯度灵敏度差）·
E 阵列 DRC / LVS（默认档 ACCEPT · LVS 四判据 · 物理签核三合一）·
F 反向探针（密阵列串扰超限 / 音域过窄 / 失配过大 CMRR 不达标 / 音重复 / 通道缺失
  ⇒ 各自**必红**且红在**期望判据**）·
G 自入 CI core（防静默漏接 · **G2 golden 分派必含四锚**（防漏登⇒假自证桩））·
H 模块自检直连（qs_m4.selfcheck_qs_m4 全项 PASS）。

═══ 🔴 锚账本口径（本档**净增 4 道锚** B478–B481）═══
QS-M4 交付**新物理量**（非既有锚的重复）：
  · **B478** 磁偶极近场串扰系数 X=(d_crit/r)³（阵列专属物理量）；
  · **B479** 串扰恶化灵敏度倍率 √(1+X_tot²)；
  · **B480** 梯度计共模抑制比 CMRR=20log₁₀(1/ε)；
  · **B481** 梯度计差模灵敏度 η_grad=η√2/baseline。
QS-M3b 的器件本体 / QS-M3 的深度 / QS-M1 的灵敏度均**不重复登记**。

═══ 诚实边界 ═══
· 阵列节距（1.2 µm = 4× 柱径）为**设计示例**；串扰 d_crit 取柱径为**建模标度**，
  非任何 foundry 的真实金刚石阵列 deck；音间隔 / 失配 ε 为设计规则（非 golden）。
· 🔴 本档**不做**器件级/系统级性能宣称；报告为**建模值**。
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


def main() -> int:
    from lda_l2 import qs_m4 as M
    from lda_l2 import primitives as PR

    # ══ A 阵列布局与单一真源 ══════════════════════════════════════════════
    pos = M.array_positions({"rows": 2, "cols": 4})
    check("A1 2×4 阵列柱心坐标现算（8 通道）",
          len(pos) == 8 and sorted(d["ch"] for d in pos) == list(range(8)),
          "ch = %s" % sorted(d["ch"] for d in pos))

    xs = sorted({round(d["x_um"], 6) for d in pos})
    check("A2 阵列**居中对称**（x 坐标关于 0 对称）",
          abs(xs[0] + xs[-1]) < 1e-9,
          "x ∈ [%.3f, %.3f]" % (xs[0], xs[-1]))

    row0 = sorted([d for d in pos if d["row"] == 0], key=lambda d: d["col"])
    check("A3 节距随列号**单调**（布局非退化）",
          all(row0[i + 1]["x_um"] - row0[i]["x_um"] > 0 for i in range(len(row0) - 1)),
          "Δx = %.3f µm" % (row0[1]["x_um"] - row0[0]["x_um"]))

    check("A4 🔴 柱径**委派** primitives 单一真源（非复制数值）",
          abs(M.pillar_diameter_um()
              - PR.qs_device_geometry("NVPillar", {})["dia"]) < 1e-12,
          "dia = %.4f µm" % M.pillar_diameter_um())

    el = M.array_layout({"rows": 2, "cols": 4})
    _nets = {e.get("net") for e in el}
    check("A5 版图复用 QS-M3b NVPillar 本体 + 阵列级馈线（net = pillar/feedline）",
          _nets == {"pillar", "feedline"},
          "nets = %s" % _nets)

    _n_feed = len({e["row"] for e in el if e.get("net") == "feedline"})
    check("A6 馈线数 = 行数（每行一条读出馈线）",
          _n_feed == 2, "feedlines = %d" % _n_feed)

    _n_chlayout = len({e["ch"] for e in el if e.get("net") == "pillar"})
    check("A7 descs 通道数 ↔ positions 同源（8 = rows×cols）",
          _n_chlayout == len(pos) == 8,
          "layout ch = %d vs pos = %d" % (_n_chlayout, len(pos)))

    # ══ B 串扰物理 ═══════════════════════════════════════════════════════
    r_pts = [0.3, 0.5, 1.0, 2.0, 5.0]
    check("B1 🔴 串扰闭式 X=(d_crit/r)³ ↔ **数值链点偶极积分** 一致（相对残差 <1e-3）",
          all(abs(M.crosstalk_coefficient_numeric(r, 1.0)
                  - M.crosstalk_coefficient(r, 1.0))
              / M.crosstalk_coefficient(r, 1.0) < 1e-3 for r in r_pts),
          "r 点 = %s" % r_pts)

    check("B2 立方律（X(2r) = X(r)/8）",
          abs(M.crosstalk_coefficient(2.0, 1.0)
              / M.crosstalk_coefficient(1.0, 1.0) - 0.125) < 1e-12,
          "比值 = %.6f" % (M.crosstalk_coefficient(2.0, 1.0)
                           / M.crosstalk_coefficient(1.0, 1.0)))

    check("B3 边界 r = d_crit ⇒ X = 1（满串扰）",
          abs(M.crosstalk_coefficient(1.0, 1.0) - 1.0) < 1e-12)

    _xs = [M.crosstalk_coefficient(r, 1.0) for r in r_pts]
    check("B4 串扰随间距**单调降**",
          all(_xs[i] > _xs[i + 1] for i in range(len(_xs) - 1)),
          "X = %s" % ["%.4g" % v for v in _xs])

    _ct22 = M.array_crosstalk({"rows": 2, "cols": 2,
                               "pitch_x_um": 1.2, "pitch_y_um": 1.2})
    check("B5 对称阵（2×2）各通道 X_tot 相同（几何对称 ⇒ 串扰对称）",
          len({round(d["x_total"], 9) for d in _ct22["per_channel"]}) == 1,
          "X_tot = %.6f" % _ct22["per_channel"][0]["x_total"])

    _ct = M.array_crosstalk({"rows": 2, "cols": 4})
    # 按所有对累计：X_tot 必须 > 最近邻单对（含对角邻居贡献）
    _multi_ok = all(d["x_total"] > d["x_max_pair"] - 1e-15 for d in _ct["per_channel"])
    check("B6 🔴 串扰**按所有对**累计（X_tot ≥ 最大单对；对角邻居如实计入不截断）",
          _multi_ok,
          "max X_tot = %.5f vs max pair = %.5f"
          % (_ct["max_x_total"], _ct["max_x_pair"]))

    check("B7 串扰恶化灵敏度 η_eff=η√(1+X_tot²) ≥ η_single；X=0 ⇒ 恰等",
          M.crosstalk_sensitivity_eta(1e-9, 0.0) == 1e-9
          and M.crosstalk_sensitivity_eta(1e-9, 0.5) > 1e-9,
          "η(0.5)=%.4f nT" % (M.crosstalk_sensitivity_eta(1e-9, 0.5) * 1e9))

    # ══ C 多通道读出 mux ═════════════════════════════════════════════════
    plan = M.readout_mux_plan({"rows": 2, "cols": 4})
    _by_feed = {}
    for r in plan["per_channel"]:
        _by_feed.setdefault(r["feedline"], []).append(r["tone_ghz"])
    check("C1 同馈线音**互异**（FDM 可分辨）",
          all(len(v) == len({round(t, 9) for t in v}) for v in _by_feed.values()),
          "feedlines = %s" % {k: len(v) for k, v in _by_feed.items()})

    check("C2 音数 = 通道数（每通道一音）",
          plan["unique_tones"] == 8, "unique = %d" % plan["unique_tones"])

    check("C3 默认音规划 ACCEPT（音间隔 ≥ 下限 + 落带）",
          plan["verdict"] == "ACCEPT" and plan["spacing_ok"] and plan["band_ok"],
          "min_spacing = %s MHz" % plan["min_tone_spacing_mhz"])

    # 思路复用 sc_readout_mux（D-140）：同馈线音唯一 + 音间隔两条核心判据
    check("C4 🔴 读出 mux 思路**复用 sc_readout_mux（D-140）**（同馈线音唯一 + 最小音间隔）",
          hasattr(M.readout_mux_plan, "__doc__")
          and "sc_readout_mux" in M.readout_mux_plan.__doc__
          and plan["tone_dup"] is False
          and plan["spacing_ok"] is True,
          "doc 提及 = %s" % ("sc_readout_mux" in M.readout_mux_plan.__doc__))

    check("C5 不同馈线**可复用**音（每行独立端口，cols 音/馈线）",
          plan["tones_per_feedline"] == 4 and plan["feedlines"] == 2,
          "tones/feed = %d · feedlines = %d"
          % (plan["tones_per_feedline"], plan["feedlines"]))

    # ══ D 梯度计 ═════════════════════════════════════════════════════════
    _eps = (0.01, 0.05, 0.1, 0.5)
    check("D1 🔴 梯度计 CMRR 闭式 20log₁₀(1/ε) ↔ **数值链** 一致（绝对差 <1e-4 dB）",
          all(abs(M.gradiometer_cmrr_db(e) - M.gradiometer_cmrr_numeric(e)) < 1e-4
              for e in _eps),
          "ε 点 = %s" % (_eps,))

    _c = [M.gradiometer_cmrr_db(e) for e in (0.5, 0.1, 0.05, 0.01)]
    check("D2 ε↓ ⇒ CMRR↑（单调）",
          all(_c[i] < _c[i + 1] for i in range(len(_c) - 1)),
          "CMRR = %s dB" % ["%.2f" % v for v in _c])

    check("D3 边界：ε=1 ⇒ 0 dB；ε=0.01 ⇒ 40 dB",
          abs(M.gradiometer_cmrr_db(1.0)) < 1e-12
          and abs(M.gradiometer_cmrr_db(0.01) - 40.0) < 1e-9,
          "CMRR(1)=%.3f · CMRR(0.01)=%.3f"
          % (M.gradiometer_cmrr_db(1.0), M.gradiometer_cmrr_db(0.01)))

    check("D4 梯度灵敏度 η_grad=η√2/baseline 随基线**变短而变差**",
          M.gradiometer_eta(1e-9, 100.0)["eta_grad_per_um"]
          > M.gradiometer_eta(1e-9, 200.0)["eta_grad_per_um"],
          "η(100)=%.4g vs η(200)=%.4g"
          % (M.gradiometer_eta(1e-9, 100.0)["eta_grad_per_um"],
             M.gradiometer_eta(1e-9, 200.0)["eta_grad_per_um"]))

    # ══ E 阵列 DRC / LVS ═════════════════════════════════════════════════
    drc = M.run_array_drc(params={"rows": 2, "cols": 4})
    check("E1 默认档阵列 DRC ACCEPT（0 违规）",
          drc["verdict"] == "ACCEPT" and not drc["violations"],
          "violations = %s" % drc["violations"])

    lvs = M.array_lvs({"rows": 2, "cols": 4})
    check("E2 默认档阵列 LVS ACCEPT（通道/馈线/音唯一 四判据）",
          lvs["verdict"] == "ACCEPT" and lvs["n_checks"] == 4,
          "issues = %s" % lvs["issues"])

    check("E3 阵列物理签核三合一（串扰 + 读出 + 梯度计 CMRR）ACCEPT",
          M.array_physics({"rows": 2, "cols": 4})["verdict"] == "ACCEPT",
          "verdict = %s" % M.array_physics({"rows": 2, "cols": 4})["verdict"])

    check("E4 四情景阵列表可现算（baseline/dense/large/mismatch）",
          set(M.array_table()) == {"baseline", "dense", "large", "mismatch"},
          "scenarios = %s" % sorted(M.array_table()))

    # ══ F 反向探针（各自必红且红在期望判据）═══════════════════════════════
    _dense = M.run_array_drc(params={"rows": 2, "cols": 4,
                                     "pitch_x_um": 0.31, "pitch_y_um": 0.31})
    _hit_d = {v["rule"] for v in _dense["violations"]}
    check("F1 密阵列（节距 0.31 µm ⇒ 净距 0.01、X≈0.91）⇒ DRC 必红且红在串扰/间距",
          _dense["verdict"] == "REJECT"
          and bool(_hit_d & {"QS-ARR-CROSSTALK", "QS-ARR-PILLAR-SEP"}),
          "rules = %s" % _hit_d)

    _tight = M.readout_mux_plan({"rows": 2, "cols": 12, "f_min_ghz": 2.80,
                                 "f_max_ghz": 2.85, "tone_spacing_ghz": 0.001})
    check("F2 音间隔过密（12 音按 1 MHz 阶梯 ⇒ 低于 30 MHz 下限）⇒ 规划 REJECT",
          _tight["verdict"] == "REJECT" and not _tight["spacing_ok"],
          "spacing_ok=%s · min_spacing=%s MHz" % (_tight["spacing_ok"],
                                                  _tight["min_tone_spacing_mhz"]))

    _mm = M.array_physics({"rows": 2, "cols": 4, "scale_mismatch": 0.5})
    check("F3 标度失配过大（ε=0.5 ⇒ CMRR=6 dB < 40）⇒ 物理签核 REJECT",
          _mm["verdict"] == "REJECT" and not _mm["cmrr_ok"],
          "CMRR = %.2f dB" % _mm["gradiometer"]["cmrr_db"])

    # 音重复探针（直接构造重复音 ⇒ 唯一性判据必红）
    _pb = M.readout_mux_plan({"rows": 2, "cols": 4})
    for r in _pb["per_channel"]:
        if r["row"] == 0:
            r["tone_ghz"] = _pb["per_channel"][0]["tone_ghz"]
    _bf = {}
    for r in _pb["per_channel"]:
        _bf.setdefault(r["feedline"], []).append(r["tone_ghz"])
    _dup = any(len(v) != len({round(t, 9) for t in v}) for v in _bf.values())
    check("F4 同馈线音重复 ⇒ 唯一性判据必红（判据有鉴别力，非恒真）", _dup,
          "tone_dup = %s" % _dup)

    _drift = [e for e in M.array_layout({"rows": 2, "cols": 4})
              if not (e.get("net") == "pillar" and e.get("ch") == 0)]
    check("F5 通道缺失（删 ch=0 图元）⇒ LVS 必拒",
          M.array_lvs(_drift, {"rows": 2, "cols": 4})["verdict"] == "REJECT")

    # 几何漂移探针：柱径真源篡改 ⇒ 柱径委派判据必变
    _dia_saved = PR.NV_PILLAR_DEFAULTS["dia_um"]
    PR.NV_PILLAR_DEFAULTS["dia_um"] = _dia_saved + 0.20
    _dia_drift = abs(M.pillar_diameter_um()
                     - PR.qs_device_geometry("NVPillar", {})["dia"]) < 1e-12
    _dia_changed = abs(M.pillar_diameter_um() - _dia_saved) > 1e-9
    PR.NV_PILLAR_DEFAULTS["dia_um"] = _dia_saved
    check("F6 🔴 柱径真源漂移必被检出（判据读现算值；复原后一致）",
          _dia_drift and _dia_changed
          and abs(M.pillar_diameter_um() - _dia_saved) < 1e-12,
          "dia 复原 = %.4f µm" % M.pillar_diameter_um())

    check("F7 异常输入必抛错（r ≤ 0 / ε ∉ (0,1]）",
          M._raises(lambda: M.crosstalk_coefficient(0.0, 1.0))
          and M._raises(lambda: M.gradiometer_cmrr_db(0.0))
          and M._raises(lambda: M.crosstalk_sensitivity_eta(1e-9, -1.0)))

    # ══ G 自入 CI core ════════════════════════════════════════════════════
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as f:
        _ci = f.read()
    check("G1 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_qs_m4_smoke.py" in _ci)

    # 🔴 G2（v0.9.221 补）：B478–B481 的 golden 必须在 _GOLDEN_DISPATCH 内有定义。
    # 根因：本档四锚虽已登记进 BENCHMARK_ORDER + benchmark_defs/part7，
    # 但 golden.py 的 _GOLDEN_DISPATCH 是**手工维护的硬编码字典** ⇒ 漏登
    # ⇒ 全量照妖镜路径②报「无黄金参考定义: B478」、且四锚被判**自证桩**
    # （CLI verified 473 ≠ 端点 477）。定向门禁当初不解析 golden ⇒ 漏抓
    # ⇒ **又一例「定向全绿≠无债」**。本判据把「账本成员必在 golden 分派内」
    # 钉成常驻门禁（与全量照妖镜同源的最前置一道）。
    from lda_harness.golden import _GOLDEN_DISPATCH as _GD
    _missing_golden = [b for b in ("B478", "B479", "B480", "B481")
                       if b not in _GD]
    check("G2 🔴 B478–B481 golden 必在 _GOLDEN_DISPATCH 内有定义（防漏登⇒假自证桩）",
          not _missing_golden,
          "缺失 = %s" % _missing_golden)

    # ══ H 模块自检直连 ════════════════════════════════════════════════════
    _sc = M.selfcheck_qs_m4()
    check("H1 qs_m4.selfcheck_qs_m4 全项 PASS（%d 项）" % len(_sc),
          all(_sc.values()),
          "FAIL = %s" % [k for k, v in _sc.items() if not v])

    print("")
    print("门禁 smoke：%d PASS / %d FAIL"
          % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
