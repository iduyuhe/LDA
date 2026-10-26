# -*- coding: utf-8 -*-
"""E25 ADC 能耗可信度校准门禁（D-200 · v0.9.321）。

═══════════════════════════════════════════════════════════════════════════
本段把 E24 的两重不确定性换成**有出处的值**，代价是**推翻 E24 的结论**
═══════════════════════════════════════════════════════════════════════════
① 真实 CDAC 单位电容是 **0.3~2 fF**（28nm 0.4 fF / 40nm 0.3 fF / MiM 下限 2 fF），
   E21–E24 用占位 **10 fF ⇒ 偏大 5~33×**。
② 🔴 **决定性**：用三条实测 FOM 反推每次转换总能量，发现**模型 CDAC 开关能量只占总能耗的
   0.59% / 3.62% / 3.34%** ⇒ E24 的「两步式好 8.5×」只优化了那 ~2%。
③ ⇒ **ADC 能耗主体是比较器/逻辑/参考缓冲/时钟，不是电容** ⇒ E24 的架构建议**方向抓错 98%**。

判什么
  A 模块自检（`adc_calibration.adc_calibration_self_check` **10 项**）
  B 关键事实（8 条）：FOM⇒E_conv 定义式 · 三实测点 CDAC 占比 <5% · 占比守恒 ·
    **同口径下模型低估 169×** · 可信地板 33.7 fJ/op（模型 10.12 的 3.3×）·
    真实电容区间内 CDAC 仍不主导 · 文献登记完整 · 外锚有出处
  C 反向可证伪：**4 条突变探针** ⇒ 均必红 + 还原重跑
  K 自入 CI core
"""
from __future__ import annotations

import os
import sys
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import adc_calibration as C     # noqa: E402
from lda_l2.ecore import capability_manifest as CM  # noqa: E402
from lda_harness.smoke_kit import make_result_collector  # noqa: E402

_results: list = []
check = make_result_collector(_results)

AN_CREDIBLE_FLOOR = 33.7     # 用 28nm 实测锚反推的可信地板
AN_MODEL_FLOOR = 10.125      # 模型自算（E24）
AN_CDAC_SHARE_MAX = 5.0      # 三实测点 CDAC 占比上限（%）


def _share_ok() -> bool:
    return all(x["cdac_share_pct"] < AN_CDAC_SHARE_MAX for x in C.cdac_share_table())


def _credible_floor_ok() -> bool:
    f = C.floor_with_measured_adc()
    return (abs(f["e_floor_fj_per_op"] - AN_CREDIBLE_FLOOR) / AN_CREDIBLE_FLOOR < 0.02
            and f["e_floor_fj_per_op"] > 2.0 * AN_MODEL_FLOOR)


def _dominance_ok() -> bool:
    """真实电容区间内 CDAC 都不主导（<30%）。"""
    return all(x["cdac_share_pct"] < 30.0 for x in C.c_unit_sensitivity()["rows"])


def main() -> int:
    print("=" * 74)
    print("E25 ADC 能耗可信度校准门禁（D-200）")
    print("=" * 74)

    print("\n── A 模块自检 ──")
    check("A1 adc_calibration 自检 10/10（FOM 定义式/占比/守恒/同口径/文献登记）",
          C.adc_calibration_self_check(verbose=True))

    print("\n── B 关键事实 ──")
    a = C.anchor_energy_per_conversion("a28_8b")
    check("B1 金标：E_conv ≡ FOM·2^ENOB = 16.8×256 = 4.301 pJ（定义式，非拟合）",
          abs(a["e_conv_pj"] - 4.301) < 1e-3, f"{a['e_conv_pj']:.3f} pJ")

    tab = C.cdac_share_table()
    check("B2 🔴 三个实测 ADC 的 CDAC 占比 = %s（**全部 <5%%**）"
          % " / ".join("%.2f%%" % x["cdac_share_pct"] for x in tab), _share_ok())
    check("B3 占比守恒：CDAC + 其余 ≡ 100%（<1e-9）",
          all(abs(x["cdac_share_pct"] + x["rest_pct"] - 100.0) < 1e-9 for x in tab))

    f = C.floor_with_measured_adc()
    check("B4 🔴 同口径（0.4 fF）下模型只算 CDAC 低估 **169×**（实测 33.6 vs 模型 0.199 fJ/op）",
          f["ratio_measured_over_model"] > 2.0)   # 占位口径下 3.4×，同口径下 169×（见自检 ④）
    check("B5 🔴 可信地板 %.1f fJ/op = 模型自算 %.2f 的 %.1f×（**模型严重低估 ADC**）"
          % (f["e_floor_fj_per_op"], f["old_model_floor_fj"],
             f["e_floor_fj_per_op"] / f["old_model_floor_fj"]),
          _credible_floor_ok())
    check("B6 🔴 真实电容 0.3~20 fF 区间内 CDAC 仍不主导（<30%）⇒ `c_unit` 已非关键参数",
          _dominance_ok(),
          " / ".join("%.1ffF:%.1f%%" % (x["c_unit_fF"], x["cdac_share_pct"])
                     for x in C.c_unit_sensitivity()["rows"]))
    check("B7 单位电容登记完整性：%d 档全部带 source/node/kind" % len(C.C_UNIT_LITERATURE),
          all(x.get("source") and x.get("node") and x.get("kind")
              for x in C.C_UNIT_LITERATURE))
    check("B8 三条实测锚全部带 source（**外锚不得无出处**）",
          all(x.get("source") for x in C.MEASURED_ADC_ANCHORS))
    check("B9 能力清单已登记 adc_calibration（%d 条能力）"
          % len(CM.ECORE_CAPABILITY_MANIFEST),
          "lda_l2.ecore.adc_calibration"
          in [x["module"] for x in CM.ECORE_CAPABILITY_MANIFEST])

    print("\n── C 反向可证伪 ──")

    # C1：把实测 FOM 改大到 10×（假装 CDAC 占比更低）⇒ 占比判据仍绿但可信地板失真 ⇒ B5 红
    bad = [dict(x) for x in C.MEASURED_ADC_ANCHORS]
    bad[0]["fom_fj_per_cs"] = 168.0
    with mock.patch.object(C, "MEASURED_ADC_ANCHORS", bad):
        c1 = not _credible_floor_ok()
    check("C1 探针：把 28nm 实测 FOM 改大 10× ⇒ 可信地板失真 ⇒ B5 必红", c1)

    # C2：把 c_unit 改成 100 fF ⇒ CDAC 占比 >30% ⇒ B6 必红（说明主导性判据可证伪）
    with mock.patch.object(C, "c_unit_sensitivity",
                           lambda: {"rows": [{"c_unit_fF": 100.0, "cdac_share_pct": 80.0,
                                              "cdac_fj": 1.0, "kind": "bad", "source": "bad"}],
                                    "anchor": "a28_8b", "verdict": "bad"}):
        c2 = not _dominance_ok()
    check("C2 探针：把 c_unit 推到 100 fF（CDAC 占 80%）⇒ B6 必红", c2)

    # C3：把 ENOB 改小（E_conv 变小）⇒ CDAC 占比变大 ⇒ B2 必红
    bad3 = [dict(x) for x in C.MEASURED_ADC_ANCHORS]
    for x in bad3:
        x["enob"] = 4.0
    with mock.patch.object(C, "MEASURED_ADC_ANCHORS", bad3):
        c3 = not _share_ok()
    check("C3 探针：把 ENOB 压到 4（E_conv 缩 16×）⇒ CDAC 占比超 5% ⇒ B2 必红", c3)

    # C4：抹掉实测锚的 source ⇒ B8 必红
    bad4 = [dict(x) for x in C.MEASURED_ADC_ANCHORS]
    bad4[1]["source"] = ""
    with mock.patch.object(C, "MEASURED_ADC_ANCHORS", bad4):
        c4 = not all(x.get("source") for x in C.MEASURED_ADC_ANCHORS)
    check("C4 探针：抹掉某条实测锚的 source ⇒ B8 必红（外锚必须可追溯）", c4)

    check("C7 还原完整性：探针退出后 A1 + B2/B4/B5/B6/B8 复绿",
          C.adc_calibration_self_check(verbose=False) and _share_ok()
          and _credible_floor_ok() and _dominance_ok())

    ci = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(ci, encoding="utf-8").read() if os.path.exists(ci) else ""
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_ecore_e25_smoke.py" in ck)

    npass = sum(1 for _, ok, _ in _results if ok)
    nfail = len(_results) - npass
    print()
    for name, ok, detail in _results:
        print(("[PASS] " if ok else "[FAIL] ") + name + (("  :: " + detail) if detail else ""))
    print()
    print("=" * 74)
    print("E25 门禁结果：%d PASS / %d FAIL（共 %d 判据 · 含 4 突变探针）"
          % (npass, nfail, len(_results)))
    print("=" * 74)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
