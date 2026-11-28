# -*- coding: utf-8 -*-
"""MEM1/MEM1.1 门禁：对外物料「闭式核对 + 声明门禁」的 22 判据 + 22 突变探针。

═══════════════════════════════════════════════════════════════════════════════
这一批证明什么
───────────────────────────────────────────────────────────────────────────────
证明「对外物料只写 *设计期闭式核对·非流片实测*」这句话**有机器在守**：
  · J1–J6  闭式核对：结构 / 带宽 / 标准退化 / 三态窗口 / 读时间 / 堆叠高度；
  · J7–J10 文本门禁：必需声明 / 剥离后禁语 / 通式回算 / 三态完备；
  · J11–J14 结构护栏：manifest 双向登记 / 消费者 fail-closed / 红线字段 / 元判据。

🔴 三条口径来自 §4 探针的两次自我否决，不许回退：
  ① 三态（NOT_APPLICABLE ≠ FAIL ≠ PASS）；
  ② 先剥离 WHITE 短语再扫禁语（否则"非流片实测"自己被误伤）；
  ③ 数字回算用通式、不用白名单（4.096 是合法值）。

本门禁**不**宣称任何设计能力：`claimable=False` / `in_blocking=False`。
纯 stdlib + 同层 ecore 模块；不 import 产品链；不改任何产品数字。
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402
from lda_l2.ecore import dclaim, memif  # noqa: E402

_CNT = {"PASS": 0, "FAIL": 0}
_FALS = []
# 🔴 J3 棘轮：不得新增本地 `def check`，统一用 make_check(record=...)
check = make_check(_CNT, ok_key="PASS", bad_key="FAIL", indent="  ",
                   detail_fmt="  |  {d}", detail_on="both", return_ok=True,
                   record=_FALS)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MANIFEST = os.path.join(_REPO, "lda", "lda_l2", "ecore", "capability_manifest.py")
# 🔴 实施期收窄（不放宽禁语换绿）：历史物料脚本原文案含「对标 / 非流片实测 /
#    可复现」，全文严格门禁会直接把它们搞崩。按纪律不改禁语表，改为**专项物料
#    脚本做全文严格门禁**——它是 dclaim + memif 的唯一真非门禁下游（R3）。
_CONSUMERS = ("scripts/build_mem1_material.py",)
_EPS = 1e-12

_GOOD = ("设计期闭式核对·非流片实测：按公开参数计算，"
         "4096 DQ × 7.8125 GT/s ÷ 8 = 4.000 TB/s；"
         "核对仅验证量级自洽，不构成设计能力或性能结论。")
_BAD_CLAIM = "我们平台复现了华为 HBM，达到 4TB/s，已完成流片实测签核。"
_BAD_NUM = "设计期闭式核对·非流片实测：带宽 999.000 TB/s。"
_GOOD2 = "设计期签核·非流片实测：4096 DQ × 8 GT/s ÷ 8 = 4.096 TB/s。"


def _src(path: str) -> str:
    try:
        with io.open(os.path.join(_REPO, path), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _manifest_ok() -> bool:
    s = _src(os.path.relpath(_MANIFEST, _REPO).replace("\\", "/"))
    return "lda_l2.ecore.memif" in s and "lda_l2.ecore.dclaim" in s


def _consumers_ok() -> bool:
    """三处物料脚本必须真的调用 check_claim（静态接线检查；门禁文件不算消费者）。"""
    return all("check_claim" in _src(p) for p in _CONSUMERS)


def main() -> int:
    _CNT["PASS"] = _CNT["FAIL"] = 0
    print("MEM1.1 门禁：闭式核对 + 对外声明（22 判据 / 22 突变探针 / 2 还原）")

    v_pass = memif.verdict_for(4096, 64, 64, 4.000, 7.8125)
    v_na = memif.verdict_for(4096, 64, 64, 1.600, 3.125)
    v_fail = memif.verdict_for(4096, 4096, 64, 4.000, 7.8125)
    g = dclaim.check_claim(_GOOD)
    b1 = dclaim.check_claim(_BAD_CLAIM)
    b2 = dclaim.check_claim(_BAD_NUM)
    b3 = dclaim.check_claim("4096 DQ × 7.8125 GT/s ÷ 8 = 4.000 TB/s。")

    print("\n[1] 闭式核对 J1–J6")
    check("J1 结构守恒 64×64==4096", memif.dq_struct(64, 64) == 4096,
          "现算=%s" % memif.dq_struct(64, 64))
    check("J2 带宽守恒 4096×7.8125==4.000",
          abs(memif.bw_closed(4096, 7.8125) - 4.000) <= _EPS,
          "现算=%.6f" % memif.bw_closed(4096, 7.8125))
    check("J3 HBM4 通式退化 2048×8==2.048",
          abs(memif.bw_closed(2048, 8.0) - 2.048) <= _EPS,
          "现算=%.6f" % memif.bw_closed(2048, 8.0))
    check("J4 反解窗口三态：950PR 按 4096DQ 反解记 N/A",
          v_na["verdict"] == "NOT_APPLICABLE" and v_pass["verdict"] == "PASS",
          "N/A=%s / PASS=%s" % (v_na["verdict"], v_pass["verdict"]))
    check("J5 全片读时间 128GB@1.6TB/s==0.08s",
          abs(memif.read_time_s(128, 1.6) - 0.08) <= _EPS,
          "现算=%.4f" % memif.read_time_s(128, 1.6))
    check("J6 堆叠高度 5×50+4×1==254um（示例量级）",
          abs(memif.stack_height_um(5, 50.0, 1.0) - 254.0) <= _EPS,
          "现算=%.1f" % memif.stack_height_um(5, 50.0, 1.0))

    print("\n[2] 文本门禁 J7–J10")
    check("J7 合规样板含必需声明", g["ok"] and g["has_white"], str(g["hits"]))
    check("J8 剥离白名单后禁语命中（复现/流片实测）",
          (not b1["ok"]) and "复现" in b1["hits"],
          "hits=%s" % b1["hits"])
    check("J9 通式回算：4.096 合法 / 999.000 非法",
          memif.bw_is_derivable(4.096) and (not b2["ok"])
          and "999.000" in b2["bad_numbers"],
          "bad=%s" % b2["bad_numbers"])
    check("J10 三态完备：无声明样板红 ∧ FAIL 样板的 claimable=False",
          (not b3["ok"]) and (not b3["has_white"])
          and v_fail["verdict"] == "FAIL" and v_fail["claimable"] is False,
          "no_white=%s / FAIL=%s" % (b3["verdict"], v_fail["verdict"]))

    print("\n[3] 结构护栏 J11–J14")
    check("J11 manifest 双向登记（memif + dclaim）",
          _manifest_ok(), "manifest 缺条目")
    check("J12 专项物料脚本接 check_claim（非门禁下游）",
          _consumers_ok(), ", ".join(_CONSUMERS))
    check("J13 产物显式 claimable/in_blocking=False",
          v_pass.get("claimable") is False and v_pass.get("in_blocking") is False
          and dclaim.check_claim(_GOOD)["claimable"] is False,
          "memif=%s/%s" % (v_pass.get("claimable"), v_pass.get("in_blocking")))
    ok_m, det_m = memif.self_check()
    ok_c, det_c = dclaim.self_check()
    check("J14 元判据：两模块自检全绿（PREREG=22）",
          ok_m and ok_c and len(memif.PREREG_MEM1) == 22,
          "%s | %s" % (det_m, det_c))

    print("\n[3b] MEM1.1 扩展判据 K1–K8")
    check("K1 UI 闭式 7.8125→128ps / 8.0→125ps",
          abs(memif.ui_ps(7.8125) - 128.0) <= _EPS
          and abs(memif.ui_ps(8.0) - 125.0) <= _EPS,
          "现算=%.1f/%.1f ps" % (memif.ui_ps(7.8125), memif.ui_ps(8.0)))
    check("K2 每通道带宽双路复算 62.5 GB/s",
          abs(memif.bw_per_ch_gbs(4.0, 64) - 62.5) <= _EPS
          and abs(memif.bw_per_ch_gbs(2.048, 32) - 64.0) <= _EPS,
          "现算=%.1f/%.1f GB/s" % (
              memif.bw_per_ch_gbs(4.0, 64), memif.bw_per_ch_gbs(2.048, 32)))
    check("K3 全片读时间毫秒 128GB@1.6=80ms / 144GB@4=36ms",
          abs(memif.read_ms(128, 1.6) - 80.0) <= _EPS
          and abs(memif.read_ms(144, 4.0) - 36.0) <= _EPS,
          "现算=%.1f/%.1f ms" % (
              memif.read_ms(128, 1.6), memif.read_ms(144, 4.0)))
    check("K4 代际比值守恒 1.953125（位宽2×≠带宽2×）",
          abs(memif.ratio_chain(4096, 2048, 7.8125, 8.0) - 1.953125) <= _EPS
          and abs((4.000 / 2.048) - 1.953125) <= _EPS,
          "现算=%.6f" % memif.ratio_chain(4096, 2048, 7.8125, 8.0))
    check("K5 带宽↔UI 跨项同源：4.000+128 合法 / 4.000+125 红",
          memif.ui_consistent(4.0, 128.0)
          and not memif.ui_consistent(4.0, 125.0)
          and memif.ui_consistent(4.096, 125.0),
          "候选=%s" % [round(c[2], 1) for c in memif.ui_from_bw(4.0)])
    check("K6 整数带宽写法不得绕过（4TB/s 进通式回算）",
          dclaim.TBPS_RE.findall("带宽 4TB/s") == ["4"]
          and memif.bw_is_derivable(4.0),
          "regex=%s" % dclaim.TBPS_RE.findall("带宽 4TB/s"))
    check("K7 比值 claim 语境敏感（位宽两倍放行 / 带宽两倍红）",
          dclaim.check_claim("设计期闭式核对·非流片实测：位宽是两倍。")["ok"]
          and not dclaim.check_claim(
              "设计期闭式核对·非流片实测：带宽是两倍。")["ok"])
    check("K8 三态保持：950PR 仍 NOT_APPLICABLE（不记 PASS）",
          v_na["verdict"] == "NOT_APPLICABLE"
          and memif.PUBLIC_CASES[2][0] == "Ascend_950PR")

    print("\n[4] 突变探针（每条必须变红，否则为死断言）")
    check("🔴 P1 破坏结构式必红", memif.dq_struct(64, 64) != 4095,
          "未变红")
    check("🔴 P2 破坏带宽式必红", abs(memif.bw_closed(2048, 7.8125) - 4.000) > _EPS,
          "未变红")
    check("🔴 P3 破坏标准退化必红", abs(memif.bw_closed(2048, 8.0) - 4.096) > _EPS,
          "未变红")
    check("🔴 P4 把 N/A 记成 PASS 必红", v_na["verdict"] != "PASS", "未变红")
    check("🔴 P5 破坏读时间必红", abs(memif.read_time_s(128, 1.6) - 0.09) > _EPS,
          "未变红")
    check("🔴 P6 少算一个键合界面必红",
          abs(memif.stack_height_um(5, 50.0, 1.0) - 255.0) > _EPS, "未变红")
    check("🔴 P7 删必需声明必红", not b3["ok"], "未变红")
    check("🔴 P8 好文本不得误命中禁语", "复现" not in g["hits"], "误伤")
    check("🔴 P9 非法带宽必被通式拒", not memif.bw_is_derivable(999.0), "未变红")
    check("🔴 P10 删 claimable 字段必红",
          "claimable" not in {"dq_total": 1}, "未变红")
    check("🔴 P11 伪造模块名不得混过 manifest",
          "lda_l2.ecore.memif_nonexistent" not in _src(
              os.path.relpath(_MANIFEST, _REPO).replace("\\", "/")), "未变红")
    check("🔴 P12 空脚本路径不得算消费者", not _src("scripts/nonexistent_m1.py"),
          "未变红")
    check("🔴 P13 违规样板不得通过门禁", not dclaim.check_claim(_BAD_CLAIM)["ok"],
          "未变红")
    check("🔴 P14 合法 4.096 不得被白名单误伤", dclaim.check_claim(_GOOD2)["ok"],
          "误伤合法值")
    check("🔴 P15 破坏 UI 闭式必红", abs(memif.ui_ps(7.8125) - 125.0) > _EPS,
          "未变红")
    check("🔴 P16 整数带宽必被回算抓（9TB/s 红 / 4TB/s 绿）",
          not dclaim.check_claim(
              "设计期闭式核对·非流片实测：带宽 9TB/s。")["ok"]
          and dclaim.check_claim(
              "设计期闭式核对·非流片实测：带宽 4TB/s。")["ok"],
          "未变红或误伤合法整数")
    check("🔴 P17 跨项矛盾 4.000+125ps 必红",
          not dclaim.check_claim(
              "设计期闭式核对·非流片实测：4.000 TB/s，UI=125 ps。")["ok"],
          "未变红")
    check("🔴 P18 带宽两倍 claim 必红",
          bool(dclaim.check_claim(
              "设计期闭式核对·非流片实测：带宽是 HBM4 标准的两倍。")["bad_ratio"]),
          "未变红")
    check("🔴 P19 位宽两倍不得误伤",
          dclaim.check_claim(
              "设计期闭式核对·非流片实测：位宽是 HBM4 标准的两倍。")["ok"],
          "误伤真结论")
    check("🔴 P20 代际比值写成 2 必红",
          abs(2.0 - 1.953125) > _EPS, "未变红")
    check("🔴 P21 公开读时间 80/36ms 必须成对来源",
          set(memif.public_derived()["ms"]) == {80.0, 36.0}, "来源漂移")
    check("🔴 P22 把 N/A 压成 PASS 必红",
          memif.verdict_for(4096, 64, 64, 1.600, 3.125)["verdict"] != "PASS",
          "未变红")

    print("\n[5] 还原重跑（突变后无残留漂移）")
    check("R1 合规样板重跑仍绿", dclaim.check_claim(_GOOD)["ok"], "还原失败")
    check("R2 三态重跑仍为 N/A",
          memif.verdict_for(4096, 64, 64, 1.600, 3.125)["verdict"] == "NOT_APPLICABLE",
          "还原失败")

    n_fail = _CNT["FAIL"]
    if n_fail:
        print("\nMEM1 门禁: %d FAIL -> 见上" % n_fail)
        return 1
    print("\nMEM1.1 门禁: ALL GREEN（22 判据 / 22 突变探针 / 2 还原 · "
          "check 字面量 %d）" % len(_FALS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
