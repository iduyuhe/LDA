#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LDA 技术白皮书 markdown -> PDF 转换器。

依赖：reportlab + Windows 中文字体（msyh / msyhbd / simhei）。
用法：python scripts/whitepaper_md_to_pdf.py
输出：lda/lda_webui/static/lda_whitepaper_v0.9.40.pdf

解析支持：标题(#~######)、引用(>)、无序/有序列表、表格(|..|)、分隔线(---)、
内联加粗(**x**)。中文字体 Microsoft YaHei 作正文/加粗，SimHei 作标题，自动分页。
"""

import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, ListFlowable, ListItem)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "docs", "lda_technical_whitepaper_2026-09-05.md")
OUT = os.path.join(ROOT, "lda", "lda_webui", "static", "lda_whitepaper_v0.9.40.pdf")

FONT_DIR = "C:/Windows/Fonts"
pdfmetrics.registerFont(TTFont("MSYH", os.path.join(FONT_DIR, "msyh.ttc"), subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYHBD", os.path.join(FONT_DIR, "msyhbd.ttc"), subfontIndex=0))
pdfmetrics.registerFont(TTFont("SIMHEI", os.path.join(FONT_DIR, "simhei.ttf")))
registerFontFamily("MSYH", normal="MSYH", bold="MSYHBD", italic="MSYH", boldItalic="MSYHBD")
registerFontFamily("SIMHEI", normal="SIMHEI", bold="SIMHEI", italic="SIMHEI", boldItalic="SIMHEI")

ACCENT = colors.HexColor("#2563eb")
LINE = colors.HexColor("#cbd5e1")
ZEBRA = colors.HexColor("#f1f5f9")
GREY = colors.HexColor("#64748b")
INK = colors.HexColor("#0f172a")


def body_style():
    return ParagraphStyle("body", fontName="MSYH", fontSize=10, leading=15.5,
                          textColor=INK, wordWrap="CJK")


def quote_style():
    return ParagraphStyle("quote", fontName="MSYH", fontSize=9.5, leading=14,
                          textColor=GREY, leftIndent=10, rightIndent=6,
                          spaceBefore=4, spaceAfter=6, wordWrap="CJK")


def cell_style():
    return ParagraphStyle("cell", fontName="MSYH", fontSize=8.3, leading=11,
                          textColor=INK, wordWrap="CJK")


def hcell_style():
    return ParagraphStyle("hcell", fontName="MSYHBD", fontSize=8.3, leading=11,
                          textColor=colors.white, wordWrap="CJK")


def heading_style(level):
    sizes = {1: 20, 2: 15, 3: 12.5, 4: 11, 5: 10.5, 6: 10}
    st = ParagraphStyle("h%d" % level, fontName="SIMHEI", fontSize=sizes.get(level, 10),
                        leading=sizes.get(level, 10) + 5, textColor=ACCENT,
                        spaceBefore=12 if level <= 2 else 8, spaceAfter=5, wordWrap="CJK")
    if level == 1:
        st.alignment = TA_CENTER
    return st


def esc(s):
    """转义 XML 特殊字符并把 **bold** 转成 <b>。"""
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def parse_table(rows):
    data = []
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        data.append(cells)
    header = data[0]
    body = data[2:] if len(data) > 2 else []
    tbl_data = [[Paragraph(c, hcell_style()) for c in header]]
    for row in body:
        tbl_data.append([Paragraph(c, cell_style()) for c in row])
    ncol = max(len(header), 1)
    avail = A4[0] - 36 * mm
    colw = [avail / ncol] * ncol
    t = Table(tbl_data, colWidths=colw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build():
    with open(SRC, encoding="utf-8") as f:
        lines = f.read().split("\n")
    flow = []
    bs = body_style()
    qs = quote_style()
    i = 0
    N = len(lines)
    while i < N:
        line = lines[i]
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lv = len(m.group(1))
            flow.append(Paragraph(esc(m.group(2)), heading_style(lv)))
            i += 1
            continue
        if re.match(r"^\s*-{3,}\s*$", line):
            flow.append(HRFlowable(width="100%", thickness=0.7, color=LINE,
                                   spaceBefore=6, spaceAfter=6))
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < N and \
                re.match(r"^\s*\|?[\s:\-|]+\|", lines[i + 1]):
            tbl = []
            while i < N and lines[i].strip().startswith("|"):
                tbl.append(lines[i])
                i += 1
            real = [tbl[0]] + tbl[2:] if len(tbl) >= 3 else tbl
            flow.append(parse_table(real))
            flow.append(Spacer(1, 6))
            continue
        if line.startswith(">"):
            q = []
            while i < N and lines[i].startswith(">"):
                q.append(lines[i].lstrip(">").strip())
                i += 1
            flow.append(Paragraph("<br/>".join(esc(x) for x in q), qs))
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            items = []
            ordered = False
            while i < N:
                lm = re.match(r"^\s*([-*]|\d+\.)\s+(.*)$", lines[i])
                if not lm:
                    break
                if lm.group(1) not in ("-", "*"):
                    ordered = True
                items.append(esc(lm.group(2)))
                i += 1
            li = [ListItem(Paragraph(it, bs), leftIndent=10) for it in items]
            flow.append(ListFlowable(li, bulletType="1" if ordered else "bullet",
                                     bulletFontName="MSYH", bulletColor=ACCENT,
                                     bulletFontSize=9, leftIndent=14,
                                     spaceBefore=2, spaceAfter=4))
            continue
        if line.strip() == "":
            flow.append(Spacer(1, 3))
            i += 1
            continue
        flow.append(Paragraph(esc(line), bs))
        i += 1

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="LDA 技术白皮书 v0.9.40",
                            author="上海杜特企业管理咨询有限公司")
    doc.build(flow)
    print("WROTE", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    build()
