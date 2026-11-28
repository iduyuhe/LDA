# -*- coding: utf-8 -*-
"""MEM1 / MEM1.1 对外物料生成器（**唯一**严格消费者）。

口径：物料全文只写「设计期闭式核对·非流片实测」+ 一张自动生成的核对表；
      数字不手抄（来自 `memif.verdict_for`），生成前全文过 `dclaim.check_claim`；
      不合规**拒绝写盘**（fail-closed）。

🔴 消费者范围说明：历史物料脚本（build_schip_intro_html / build_pchip_materials）
   原文案本就含「对标」「非流片实测」「可复现」等行业/边界措辞，**全文严格门禁会误伤**
   （实施期实测 hits=['复现','对标','流片实测']）。按"不放宽门禁换绿"的纪律，
   不改禁语表，改为**只对本次 HBM 议题的专项物料做全文严格门禁**，历史物料不动。
   本脚本 = `dclaim` 与 `memif` 的非门禁下游（R3 要求）。

用法：
  python scripts/build_mem1_material.py              # 生成合规物料
  python scripts/build_mem1_material.py --selftest   # 只验证 fail-closed，不写盘
"""
from __future__ import annotations

import io
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "lda"))

from lda_l2.ecore import dclaim, memif  # noqa: E402

OUT = os.path.join(_REPO, "docs", "LDA_MEM1_对外投影_设计期闭式核对.html")

_CLAIM = "设计期闭式核对·非流片实测"
_BAD_INJECT = "我们平台复现了华为 HBM，达到 4TB/s，已完成流片实测签核。"

# A 级公开来源（照录 · 未验证 · 仅作核对输入 · 不用于计算 LDA 成就值）
_INPUTS = (
    ("ISSCC 2027 议程草案（IEEE 2026-11-23 公布）定制 HBM",
     dict(dq_total=4096, n_ch=64, dq_per_ch=64, bw_tbps=4.000, r_gtps=7.8125)),
    ("HBM4 标准位宽 2048 DQ @ 8 GT/s",
     dict(dq_total=2048, n_ch=32, dq_per_ch=64, bw_tbps=2.048, r_gtps=8.0)),
    ("昇腾 950PR（HiBL 1.0 · 128 GB / 1.6 TB/s）按 4096 DQ 反解",
     dict(dq_total=4096, n_ch=64, dq_per_ch=64, bw_tbps=1.600, r_gtps=3.125)),
)


def _row(name: str, v: dict) -> str:
    vd = memif.verdict_for(**v)
    note = ("口径不适用（非同款方案）" if vd["verdict"] == "NOT_APPLICABLE"
            else "量级自洽" if vd["verdict"] == "PASS" else "数据/单位不自洽")
    ui = memif.ui_ps(vd["r_implied_GTps"])
    per_ch = memif.bw_per_ch_gbs(vd["bw_tbps"], vd["n_ch"])
    return ("<tr><td>%s</td><td>%d DQ · %d ch × %d DQ</td><td>%.3f TB/s</td>"
            "<td>%.4f GT/s</td><td>%.1f ps</td><td>%.1f GB/s</td>"
            "<td><b>%s</b></td><td>%s</td></tr>") % (
        name, vd["dq_total"], vd["n_ch"], vd["dq_per_ch"], vd["bw_tbps"],
        vd["r_implied_GTps"], ui, per_ch, vd["verdict"], note)


def _reads_table() -> str:
    rows = "".join(
        "<tr><td>%s</td><td>%.0f GB</td><td>%.3f TB/s</td><td>%.1f ms</td></tr>"
        % (name, cap, bw, memif.read_ms(cap, bw))
        for name, cap, bw in memif.PUBLIC_READS)
    return ("<table><tr><th>公开产品（容量/带宽同源）</th><th>容量</th>"
            "<th>带宽</th><th>全片读时间</th></tr>" + rows + "</table>")


def _ratio_text() -> str:
    ratio = memif.ratio_chain(4096, 2048, 7.8125, 8.0)
    return ("<p>代际口径：位宽是 HBM4 标准的两倍；"
            "带宽是 HBM4 标准的 %.6f 倍（速率 7.8125 对 8 GT/s 折减）。</p>") % ratio


def build_html(bad: bool = False) -> str:
    rows = "".join(_row(n, v) for n, v in _INPUTS)
    text = _BAD_INJECT if bad else (
        "<p>" + _CLAIM + "：按公开参数计算，带宽 = DQ × 速率 ÷ 8，"
        "下表逐项复算；核对只验证量级自洽，不构成设计能力或性能结论。</p>"
    )
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='color-scheme' content='light'>"
            "<title>LDA MEM1 · 设计期闭式核对</title>"
            "<style>:root{color-scheme:light}"
            "html,body{background:#ffffff;color:#1f2328}"
            "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;"
            "max-width:1040px;margin:2rem auto;padding:0 1rem;line-height:1.7;"
            "font-size:15px}table{border-collapse:collapse;width:100%;table-layout:fixed}"
            "th,td{border:1px solid #d0d7de;padding:.55rem .7rem;font-size:.9rem;"
            "vertical-align:top;overflow-wrap:anywhere;text-align:left}"
            "th{background:#f2f4f7;color:#1f2328;font-weight:600}"
            "td b{color:#0969da}</style></head><body>"
            "<h1>超宽并行内存接口 · 闭式核对投影</h1>" + text
            + "<table><tr><th>公开输入</th><th>结构</th><th>带宽</th>"
            "<th>反解速率</th><th>单位间隔 UI</th><th>每通道带宽</th>"
            "<th>判决</th><th>说明</th></tr>" + rows + "</table>"
            + _reads_table() + _ratio_text()
            + "<p>边界：非流片实测；无 foundry PDK；不报吞吐/能效；"
            "NOT_APPLICABLE 不计入 PASS 率。</p></body></html>\n")


def main() -> int:
    if "--selftest" in sys.argv:
        bad_verdict = dclaim.check_claim(build_html(bad=True))
        ok_verdict = dclaim.check_claim(build_html())
        print("fail-closed 违规注入: verdict=%s hits=%s" %
              (bad_verdict["verdict"], bad_verdict["hits"]))
        print("合规样板: verdict=%s" % ok_verdict["verdict"])
        return 0 if (not bad_verdict["ok"] and ok_verdict["ok"]) else 1

    html = build_html()
    verdict = dclaim.check_claim(html)
    if not verdict["ok"]:
        raise SystemExit("声明门禁拒绝写盘：%s" % verdict)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("已生成 %s（门禁 PASS，数字自动来自 memif）" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
