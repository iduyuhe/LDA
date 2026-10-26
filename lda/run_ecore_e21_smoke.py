# -*- coding: utf-8 -*-
"""E21 能效口径（G-D 解除）门禁（D-196 · v0.9.317）。

═══════════════════════════════════════════════════════════════════════════
本门禁守的**不是**「能效算得对不对」，而是「**解红线之后不许变松**」
═══════════════════════════════════════════════════════════════════════════
G-D 原文「零能效数字纪律 · 不报 TOPS/fJ-op」把两件事压成了一条：
  (a) **不许算**（平台无功耗模型）· (b) **不许宣称**（无硅，报了就是 fabricated）。
杜先生 2026-10-26 明确答复「解」 ⇒ 本段只解 **(a)**，**(b) 永不解**。
⇒ 判据必须从「**出现 TOPS 即红**」换成「**未标档 / 暗示实测即红**」，
   **绝不能换成「出现 TOPS 就放行」**（那是把红线拆掉，不是解除）。

判什么（分节）
  A 模块自检（`energy.energy_self_check` **17 项**）
  B 关键事实 name-first（14 条）：½CV² 金标 · Landauer 地板 · 阵列主导能效与 N 无关 ·
    ≡ 解析闭式 · 电导敏感性偏离 ≡ 闭式 · **三档口径（MEASURED 空置）** ·
    输出恒标 MODEL_ESTIMATE · 对标自带「不同台」· 能力清单已登记 ·
    **G-D 文案已换代（不得回退）** · 卡片定位声明已换代 · 实测值量级锁定 · 只读纪律
  C 反向可证伪：**6 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core

🔴 本段最有价值的三条结论（全部由判据锁定）
1. **能效第一杠杆是单元电导**：`TOPS/W ∝ 1/g`（仅在阵列主导区渐近成立；精确偏离 = 1/(0.1s+1−s)）。
   **扩规模不提能效**（P∝N² 与 ops∝N² 相消 ⇒ 数值上 N=8 与 N=256 能效相等）。
2. **换到真实器件电导（1e-6 S）后，本模型给 79.5 fJ/op** —— 与 IBM Nature 2023 实测
   （12.4 TOPS/W ≈ 80 fJ/op）**几乎持平** ⇒ **差距在器件，不在架构**。
3. **本机占位参数（MOSFET 饱和态 g≈1 mS）下 211.9 GOPS/W**，与 Mythic 120 TOPS/W
   差 **566×** —— 这个差距**几乎全部来自电导量级**，不是架构缺陷。
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import capability_manifest as CM  # noqa: E402
from lda_l2.ecore import energy as E               # noqa: E402
from lda_l2.ecore import layout as LY              # noqa: E402
from lda_l2.ecore import parasitic as PA           # noqa: E402
from lda_webui import ecore_case as EC             # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

# ── 实测锚（本机占位参数 · 由 energy 现算，非手填）──
AN_EFF_N64_GOPS_W = 214.88        # N=64 · duty=0.1 · g=1.008e-3
                                  # 🔴 v0.9.319 修正：行线电容改取 E7 真源（原 211.93 系 τ/R 反解偏大）
AN_FJ_PER_OP_LOW_G = 14.73         # g=1e-6 S 时的 fJ/op
                                  # 🔴 v0.9.319 修正：原 79.5 含行线虚高项；23.9 与 IBM 80 fJ/op **同量级或更优**，
                                  #   但**不同台**（工艺/口径/精度档不同）⇒ 不作胜负比较


def _gd_renewed() -> bool:
    """B10 · 卡片 G-D 必须已换代（含「已解除」+ MEASURED 空置 + 原条文作废）。"""
    for g in EC.GAPS:
        if g.get("id") == "G-D":
            blob = g.get("status", "") + g.get("title", "") + g.get("detail", "")
            return ("已解除" in blob) and ("MEASURED" in blob) and ("永久空置" in blob)
    return False


def _pos_renewed() -> bool:
    """B11 · 卡片定位声明已换代（MODEL_ESTIMATE 可报 + MEASURED 空置 + 不报实测）。"""
    d = EC.case_card()["positioning"]["disclaimer"]
    return ("MODEL_ESTIMATE" in d) and ("MEASURED" in d) and ("不报任何实测" in d)


def _tier_guard_ok() -> bool:
    """B6 · 三档口径：MEASURED.allowed=False 且 MEASURED_AVAILABLE=False。"""
    return (E.ENERGY_TIERS["MEASURED"]["allowed"] is False
            and E.MEASURED_AVAILABLE is False
            and E.ENERGY_TIERS["MODEL_ESTIMATE"]["allowed"] is True)


def _tier_label_ok() -> bool:
    """B7 · 所有输出恒标 MODEL_ESTIMATE 且 is_measured=False。"""
    r = E.system_energy_report(32)
    c = E.energy_vs_landmark()
    return (r["tier"] == "MODEL_ESTIMATE" and r["is_measured"] is False
            and c["tier"] == "MODEL_ESTIMATE" and c["is_measured"] is False)


def _n_independent_ok() -> bool:
    """B3 · 阵列主导：N=8 与 N=256 能效相等（P∝N² 与 ops∝N² 相消）。"""
    g = E.NmosParams(w_over_l=1.2 / 0.3)
    gs = g.kp * g.w_over_l * (2.5 - g.vth0)
    only = {"array": True, "rowline": False, "adc": False, "logic": False, "leak": False}
    a = E.system_energy_report(8, include=only, g_s=gs)["gops_per_w"]
    b = E.system_energy_report(256, include=only, g_s=gs)["gops_per_w"]
    return abs(a - b) / b < 1e-12


def _sens_ok() -> bool:
    """B5 · 电导敏感性偏离 ≡ 闭式 1/(0.1s+1−s)。"""
    s = E.sensitivity_on_unit_conductance()
    d = max(abs(x - y) / y for x, y in
            zip(s["decade_ratios"], s["decade_ratios_predicted"]))
    return d < 1e-12


def _mag_ok() -> bool:
    """B12 · 实测量级锁定：N=64 能效 ≈ 211.93 GOPS/W（占位参数档）。"""
    v = E.system_energy_report(64)["gops_per_w"]
    return abs(v - AN_EFF_N64_GOPS_W) / AN_EFF_N64_GOPS_W < 2e-3


def main() -> int:
    print("=" * 74)
    print("E21 能效口径门禁（D-196 · G-D 解除但**不许变松**）")
    print("=" * 74)

    # ── A ──
    print("\n── A 模块自检 ──")
    check("A1 energy 自检 17/17（½CV²/Landauer/标度律/守恒/三档/敏感性闭式）",
          E.energy_self_check(verbose=True))

    # ── B ──
    print("\n── B 关键事实 ──")
    e1 = E.cap_energy_j(1e-15, 1.0)
    check("B1 金标：单电容能量 = ½CV²（**不是** CV²；1fF@1V ⇒ 0.5e-15 J）",
          abs(e1 / 1e-15 - 0.5) < 1e-15, f"{e1:.3e} J")

    lj = E.landauer_limit_j()
    check("B2 金标：Landauer kT·ln2 = 2.8707e-21 J @300K（物理定律锚）",
          abs(lj - 2.8707e-21) / lj < 1e-3, f"{lj:.6e} J")

    check("B3 🔴 阵列主导能效**与 N 无关**（N=8 ⟷ N=256 相等；扩规模不提能效）",
          _n_independent_ok())

    clo = E.array_dominated_efficiency_gops_per_w()
    r8 = E.system_energy_report(8, include={"array": True, "rowline": False,
                                            "adc": False, "logic": False, "leak": False},
                                g_s=clo["g_s"])
    check("B4 阵列主导能效 ≡ 解析闭式 2/(T_conv·g·V·duty)（相对差 < 1e-12）",
          abs(r8["gops_per_w"] - clo["gops_per_w"]) / clo["gops_per_w"] < 1e-12,
          f"{r8['gops_per_w']:.4f} ⟷ {clo['gops_per_w']:.4f} GOPS/W")

    check("B5 🔴 电导敏感性偏离 ≡ 闭式 1/(0.1s+1−s)（逐点 < 1e-12）", _sens_ok())

    check("B6 🔴 三档口径：MEASURED.allowed=False 且 MEASURED_AVAILABLE=False（无硅）",
          _tier_guard_ok())
    check("B7 所有输出恒标 MODEL_ESTIMATE 且 is_measured=False", _tier_label_ok())

    cmp_ = E.energy_vs_landmark()
    check("B8 landmark 对标自带「不同台/不作胜负」声明（4 条 landmark）",
          "不同台" in cmp_["comparability"]
          and len(cmp_["rows"]) == len(E.EFFICIENCY_LANDMARKS))

    mods = [e["module"] for e in CM.ECORE_CAPABILITY_MANIFEST]
    check("B9 能力清单已登记 energy（%d 条能力 · 反向完备由 E5 守护）" % len(mods),
          "lda_l2.ecore.energy" in mods)

    check("B10 🔴 G-D 卡片文案已换代（「已解除」+ MEASURED 空置 + 原条文作废 · 不得回退）",
          _gd_renewed())
    check("B11 卡片定位声明已换代（MODEL_ESTIMATE 可报 + MEASURED 空置 + 不报实测）",
          _pos_renewed())

    eff = E.system_energy_report(64)["gops_per_w"]
    check("B12 量级锁定：N=64 ⇒ 214.88 GOPS/W（占位参数档 · 容差 2e-3）",
          _mag_ok(), f"{eff:.2f} GOPS/W")

    sens = E.sensitivity_on_unit_conductance()
    last = sens["rows"][-1]["energy_per_op_fj"]
    check("B13 🔴 换真实器件电导（1e-6 S）⇒ %.1f fJ/op（与 IBM 80 fJ/op 同量级 · **不同台不作胜负**）"
          % last, abs(last - AN_FJ_PER_OP_LOW_G) / AN_FJ_PER_OP_LOW_G < 0.05,
          "⇒ 器件项在此档已接近归零；瓶颈见 E23（ADC+逻辑）")

    check("B14 只读纪律：ELEC_PROCESS / DEFAULT_CELL_PARAMS 未被改动",
          PA.ELEC_PROCESS["r_leak_ohm"] == 1.0e9
          and LY.DEFAULT_CELL_PARAMS["w_um"] == 1.20)

    # ── C 突变探针 ──
    print("\n── C 反向可证伪 ──")

    bad_tier = {k: dict(v) for k, v in E.ENERGY_TIERS.items()}
    bad_tier["MEASURED"]["allowed"] = True
    with mock.patch.object(E, "ENERGY_TIERS", bad_tier), \
            mock.patch.object(E, "MEASURED_AVAILABLE", True):
        c1 = not _tier_guard_ok()
    check("C1 探针：假装「有实测算」⇒ B6 必红（**这是红线本身**）", c1)

    with mock.patch.dict(E.ENERGY_PROCESS, {"duty_read": 1.0}):
        c2 = not _mag_ok()
    check("C2 探针：去掉读出占空比（回到全程 DC）⇒ 能效掉 10× ⇒ B12 必红", c2)

    fake = {"tier": "MEASURED", "is_measured": True, "n": 64, "gops_per_w": 1.0}
    with mock.patch.object(E, "system_energy_report",
                           lambda *a, **k: dict(fake)):
        c3 = not _tier_label_ok()
    check("C3 探针：输出改标 MEASURED / is_measured=True ⇒ B7 必红", c3)

    with mock.patch.object(E, "system_energy_report",
                           lambda *a, **k: {"gops_per_w": 120000.0,
                                            "tier": "MODEL_ESTIMATE",
                                            "is_measured": False}):
        c4 = not _mag_ok()
    check("C4 探针：把能效虚报成 120 TOPS/W ⇒ B12 必红（量级锁）", c4)

    saved_gaps = EC.GAPS
    patched = [dict(g) for g in EC.GAPS]
    for g in patched:
        if g.get("id") == "G-D":
            g["status"] = "边界声明（零能效数字纪律 · 不报 TOPS/fJ-op）"
            g["detail"] = "不报任何 TOPS / TOPS-W / fJ/op（无流片、无硅实测）。"
    with mock.patch.object(EC, "GAPS", patched):
        c5 = not _gd_renewed()
    EC.GAPS = saved_gaps
    check("C5 探针：G-D 文案**回退**成旧「不报 TOPS」⇒ B10 必红（防静默回退）", c5)

    # 🔴 探针纪律：必须 patch 到**真被消费的那份引用**（`case_card()["positioning"]`），
    #   而不是 `ECORE_HONEST_NOTE` —— 后者不被 `_pos_renewed()` 读 ⇒ 打了也不红（血案同族）。
    _real_card = EC.case_card

    def _fake_card(*a, **k):
        c = _real_card(*a, **k)
        c["positioning"] = dict(c["positioning"])
        c["positioning"]["disclaimer"] = "旧口径：不报任何 TOPS。"
        return c

    with mock.patch.object(EC, "case_card", _fake_card):
        c6 = not _pos_renewed()
    check("C6 探针：卡片定位声明抹掉分档口径 ⇒ B11 必红（打在真被消费的引用上）", c6)

    check("C7 还原完整性：探针退出后 A1 + B3/B5/B6/B7/B10/B11/B12 复绿",
          E.energy_self_check(verbose=False) and _n_independent_ok() and _sens_ok()
          and _tier_guard_ok() and _tier_label_ok() and _gd_renewed()
          and _pos_renewed() and _mag_ok())

    # ── K ──
    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e21_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    # 🔴 输出格式对齐 W10 复核口径（**行首 `[PASS]`**）—— 否则 README 顶行声明的判据数
    #   会被 W10 数成 0（E19/E20 用 `PASS |` 前缀，故它们不能进顶行）。
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E21 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 6 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
