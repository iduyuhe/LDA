# -*- coding: utf-8 -*-
"""E22 器件族选定 + 可行性反解门禁（D-197 · v0.9.318）。

═══════════════════════════════════════════════════════════════════════════
本门禁守的核心事实（一条会改路线的事实）
═══════════════════════════════════════════════════════════════════════════
E21 说「差距在器件不在架构」—— 那只对 **MOSFET→Flash** 那一段成立。
本段把真实器件族的 g 代进模型，得到：

  MOSFET(g≈1e-3) 4681.7 → RRAM(5e-6) 97.9 → **Flash(2e-8) 75.0** → 理想(g→0) 74.9 fJ/op

🔴 **换到 Flash 级器件后，能效只比「理想零电导」差 0.1% ⇒ 器件不再是瓶颈。**
🔴 地板处功耗构成：**行线驱动 74.3%** · ADC 13.3% · 逻辑 12.3% · 阵列 0.0%。
⇒ **瓶颈从器件迁移到「行线驱动 + ADC + 外围」**，而 Mythic 的 8.3 fJ/op 低于本地板 9 倍。

判什么
  A 模块自检（`device_family.device_family_self_check` **13 项**）
  B 关键事实（9 条）：地板解析⟷数值 · 反解 round-trip · 低于地板**显式无解** ·
    8.3 目标**无族可行** · 80 目标 **Flash 唯一可行** · 瓶颈迁移（阵列→行线）·
    器件族登记完整 · 单调降 · 输出恒标 MODEL_ESTIMATE
  C 反向可证伪：**5 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import capability_manifest as CM  # noqa: E402
from lda_l2.ecore import device_family as D        # noqa: E402
from lda_l2.ecore import energy as E               # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

AN_FLOOR_FJ = 10.125          # g→0 地板（N=64）· 🔴 v0.9.319 修正：
                            #   E22 原报 74.90 是**行线电容口径错**（τ/R 反解偏大 1008×）所致
AN_ADC_SHARE = 98.8         # 地板处 ADC 份额（%）· v0.9.319 起行线仅 0.3%


def _floor_ok() -> bool:
    fl = D.efficiency_floor_fj_per_op()
    z = E.system_energy_report(D.DEFAULT_N, g_s=1e-13)["energy_per_op_fj"]
    return abs(fl["e_floor_fj_per_op"] - z) / fl["e_floor_fj_per_op"] < 1e-7


def _roundtrip_ok() -> bool:
    rt = D.roundtrip_error(80.0)
    return rt["roundtrip_ok"] is True


def _unsolvable_ok() -> bool:
    """🔴 v0.9.319 修正地板为 19.27 后，低于它的是 8.3 与 15（20/50 已可解）。"""
    return (D.conductance_inverse(8.3)["solvable"] is False
            and all(D.conductance_inverse(t)["solvable"] is True for t in (15.0, 20.0, 50.0)))


def _no_family_at_mythic() -> bool:
    return all(not x["feasible"] for x in D.family_feasibility(8.3))


def _flash_only_at_80() -> bool:
    fs = D.family_feasibility(80.0)
    ok_ids = {x["id"] for x in fs if x["feasible"]}
    return ok_ids == {"nor_flash"}


def _shift_ok() -> bool:
    """🔴 v0.9.319 修正后：Flash 级器件下主导项是 **ADC**（不是行线）。"""
    tab = D.dominant_shift_table()
    row = [x for x in tab if x.get("family") == "nor_flash"][0]
    return (row["dominant"] == "adc"
            and row["share_pct"].get("array", 100) < 5.0
            and row["share_pct"].get("row_line", 100) < 2.0
            and row["share_pct"].get("adc", 0) > 90.0)


def main() -> int:
    print("=" * 74)
    print("E22 器件族选定 + 可行性反解门禁（D-197）")
    print("=" * 74)

    print("\n── A 模块自检 ──")
    check("A1 device_family 自检 13/13（地板/反解/round-trip/可行判定/瓶颈迁移）",
          D.device_family_self_check(verbose=True))

    print("\n── B 关键事实 ──")
    fl = D.efficiency_floor_fj_per_op()
    check("B1 🔴 能效地板 = %.2f fJ/op（解析 P_other·T_conv/(2N²) ≡ g→0，<1e-7）"
          % fl["e_floor_fj_per_op"], _floor_ok())
    check("B2 金标：反解 g → 正算回目标（80 fJ/op · round-trip < 1e-12）",
          _roundtrip_ok())
    check("B3 🔴 目标 8.3 fJ/op **低于地板 10.125 ⇒ 显式无解**；15/20/50 可解（不硬凑 · 也不假报无解）",
          _unsolvable_ok())
    check("B4 🔴 8.3 fJ/op（=Mythic 120 TOPS/W）目标下 **无族可行**"
          "（⇒ 换器件到不了，必须改外围）", _no_family_at_mythic())
    check("B5 🔴 80 fJ/op 目标下 **只有 NOR Flash 可行**"
          "（其余族卡在 C2 精度：4~6 bit/cell < 8 bit）", _flash_only_at_80())
    check("B6 🔴 瓶颈迁移：Flash 级器件下主导项 = **ADC（%.1f%%）**，行线 <2%%、阵列 <5%%"
          % AN_ADC_SHARE, _shift_ok())

    check("B7 器件族登记完整性：%d 族全部带 source / read_current_note / g 区间"
          % len(D.DEVICE_FAMILIES),
          all(f.get("source") and f.get("read_current_note")
              and f["g_min_s"] < f["g_max_s"] for f in D.DEVICE_FAMILIES))

    seq = [E.system_energy_report(D.DEFAULT_N, g_s=g)["energy_per_op_fj"]
           for g in (1e-3, 1e-5, 1e-7, 1e-9)]
    check("B8 E_op 随 g 降严格单调降，直到逼近地板",
          all(seq[i] > seq[i + 1] for i in range(len(seq) - 1)),
          " → ".join("%.1f" % x for x in seq))

    mods = [e["module"] for e in CM.ECORE_CAPABILITY_MANIFEST]
    check("B9 能力清单已登记 device_family（%d 条能力）" % len(mods),
          "lda_l2.ecore.device_family" in mods)
    check("B10 输出恒标 MODEL_ESTIMATE（非实测）",
          fl["tier"] == "MODEL_ESTIMATE" and D.DEVICE_FAMILY_DISCLOSURE["tier"] == "MODEL_ESTIMATE")

    print("\n── C 反向可证伪 ──")

    # C1：把地板改小 ⇒ 假装「器件能达标」⇒ B4 必红
    with mock.patch.object(D, "efficiency_floor_fj_per_op",
                           lambda *a, **k: {**fl, "e_floor_fj_per_op": 4.0,
                                            "p_other_w": 1e-6,
                                            "p_other_share_of_floor": {"row_line": 1.0},
                                            "dominant_of_floor": "row_line",
                                            "t_conv_s": fl["t_conv_s"],
                                            "n": 64, "bits": 8, "col_share_k": 1,
                                            "parts_w": {}, "tier": "MODEL_ESTIMATE",
                                            "formula": "x"}):
        c1 = not _no_family_at_mythic()
    check("C1 探针：把地板改小（假装器件能达 Mythic）⇒ B4 必红", c1)

    # C2：把 Flash 的 g_min 改大 ⇒ 电导不足 ⇒ B5 必红
    bad = [dict(f) for f in D.DEVICE_FAMILIES]
    for f in bad:
        if f["id"] == "nor_flash":
            f["g_min_s"] = 1e-3
    with mock.patch.object(D, "DEVICE_FAMILIES", bad):
        c2 = not _flash_only_at_80()
    check("C2 探针：Flash 最小电导改成 1e-3（电导不足）⇒ B5 必红", c2)

    # C3：把 RRAM 的 bits 改成 8 ⇒ 变成两族可行 ⇒ B5（唯一性）必红
    bad3 = [dict(f) for f in D.DEVICE_FAMILIES]
    for f in bad3:
        if f["id"] == "rram":
            f["bits_per_cell"] = 8
    with mock.patch.object(D, "DEVICE_FAMILIES", bad3):
        c3 = not _flash_only_at_80()
    check("C3 探针：把 RRAM 精度抬到 8 bit ⇒ 「Flash 唯一」必红（唯一性是判据）", c3)

    # C4：反解漏掉地板项 ⇒ round-trip 必红
    def _bad_inverse(t, *a, **k):
        v, d, tc = 1.0, 0.1, 9.213525600058347e-08
        return {"target_fj_per_op": t, "e_floor_fj_per_op": 0.0, "solvable": True,
                "g_required_s": 2.0 * t * 1e-15 / (v ** 2 * d * tc),
                "surplus_fj_per_op": t, "v_in_v": v, "duty": d, "t_conv_s": tc,
                "reason": "no floor", "floor": fl}
    with mock.patch.object(D, "conductance_inverse", _bad_inverse):
        c4 = not _roundtrip_ok()
    check("C4 探针：反解漏掉 P_other 地板项 ⇒ round-trip 必红（**地板是承重项**）", c4)

    # C5：把 ADC 功耗抹掉 ⇒ 主导项不再是 ADC ⇒ B6 必红（🔴 v0.9.319：主导项已改为 ADC）
    real_adc = E.adc_power_w
    with mock.patch.object(E, "adc_power_w",
                           lambda *a, **k: {**real_adc(*a, **k), "power_w": 0.0}):
        c5 = not _shift_ok()
    check("C5 探针：抹掉 ADC 功耗 ⇒ 「ADC 主导」必红（**瓶颈结论可证伪**）", c5)

    check("C7 还原完整性：探针退出后 A1 + B1/B3/B4/B5/B6 复绿",
          D.device_family_self_check(verbose=False) and _floor_ok()
          and _unsolvable_ok() and _no_family_at_mythic()
          and _flash_only_at_80() and _shift_ok())

    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e22_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E22 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 5 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
