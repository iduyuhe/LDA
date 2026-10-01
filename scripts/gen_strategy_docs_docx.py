#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_strategy_docs_docx.py — LDA 白皮书 / 商业计划书 A4 DOCX 生成器（python-docx 直生成）。

纪律：
1) 源 markdown 为唯一真源，本脚本只做版式转换，不增删改任何内容词句（数字逐位不漂移）。
2) 生成后自动回读抽验关键口径（见 CHECKS），缺失即非零退出。
3) A4 打印版式：页边距 2.5/2cm、黑体标题、宋体正文、表头底纹、页脚页码。

用法：
  "C:/Users/Administrator/AppData/Local/Programs/Python/Python313-32/python.exe" scripts/gen_strategy_docs_docx.py
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(r"D:/agent_LDA")
DOCS = ROOT / "docs"

BRAND = RGBColor(0x1F, 0x38, 0x64)   # 深蓝
GRAY = RGBColor(0x59, 0x59, 0x59)
HEADER_FILL = "D9E2F3"               # 表头浅蓝底纹
HEI = "微软雅黑"
SONG = "宋体"
MONO = "Consolas"

RICH_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")

DOCS_SPEC = [
    {
        "md": DOCS / "lda_technical_whitepaper_v0.9.169.md",
        "out": DOCS / "LDA_技术白皮书_v0.9.169_2026-10-01.docx",
        "cover_title": "LDA 技术白皮书",
        "cover_sub": "开源 Agent 原生光子 / 量子 / 电子计算芯片设计软件",
        "cover_meta": [
            "版本 v0.9.169 · 2026-10-01 · 许可 MIT（计划）",
            "生产 https://lda.weomnitech.com.cn/",
            "Gitee gitee.com/i4hub/LDA · GitHub github.com/iduyuhe/LDA",
            "上海杜特企业管理咨询有限公司",
        ],
        "keys": ["476", "95.59%", "259", "B458", "E1", "13311602075",
                 "MESH8", "TOPS", "gdsfactory", "上海杜特企业管理咨询有限公司"],
    },
    {
        "md": DOCS / "lda_business_plan_v0.9.169.md",
        "out": DOCS / "LDA_商业计划书_v0.9.169_2026-10-01.docx",
        "cover_title": "LDA 商业计划书",
        "cover_sub": "开源 Agent 原生光子 / 量子 / 电子模拟计算芯片设计自动化平台",
        "cover_meta": [
            "版本 v0.9.169 · 2026-10-01",
            "上海杜特企业管理咨询有限公司",
            "联系人 杜玉河 · 13311602075 · gongyhlw · duyuhe@shdute.cn",
            "Gitee gitee.com/i4hub/LDA · GitHub github.com/iduyuhe/LDA",
        ],
        "keys": ["476", "95.59%", "259", "1000 万", "599", "1999", "4999",
                 "13311602075", "TOPS", "尚无任何真实付费客户", "上海杜特企业管理咨询有限公司"],
    },
]


def _set_run(r, size=10.5, bold=None, italic=None, color=None,
             ea=SONG, ascii_font=None):
    f = r.font
    if ascii_font:
        f.name = ascii_font
    f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color is not None:
        f.color.rgb = color
    rpr = r._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), ea)


def _style_ea(style, ea):
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), ea)


def add_rich(p, text, size=10.5, color=None, ea=SONG):
    for tok in RICH_RE.split(text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            r = p.add_run(tok[2:-2])
            _set_run(r, size=size, bold=True, color=color, ea=HEI)
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            r = p.add_run(tok[1:-1])
            _set_run(r, size=size - 1, ascii_font=MONO, color=color, ea=SONG)
        else:
            r = p.add_run(tok)
            _set_run(r, size=size, color=color, ea=ea)


def add_footer_pagenum(doc, label):
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(label + "    —  ")
    _set_run(r, size=8, color=GRAY, ea=SONG)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    p._p.append(fld)


def shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def render_table(doc, rows):
    # rows: list[list[str]]，首行为表头；分隔行已剔除
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=len(rows), cols=ncol)
    t.style = "Table Grid"
    t.autofit = True
    for ri, row in enumerate(rows):
        for ci in range(ncol):
            cell = t.cell(ri, ci)
            text = row[ci] if ci < len(row) else ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            if ri == 0:
                shade(cell, HEADER_FILL)
                add_rich(p, text, size=9, ea=HEI)
                for r in p.runs:
                    r.font.bold = True
            else:
                add_rich(p, text, size=9)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def render_cover(doc, spec):
    for _ in range(7):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(spec["cover_title"])
    _set_run(r, size=30, bold=True, color=BRAND, ea=HEI)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(spec["cover_sub"])
    _set_run(r, size=14, color=GRAY, ea=HEI)
    doc.add_paragraph()
    for line in spec["cover_meta"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(line)
        _set_run(r, size=11, color=GRAY, ea=SONG)
    doc.add_page_break()


def parse_and_render(doc, md_path):
    lines = md_path.read_text(encoding="utf-8").splitlines()
    first_h1_done = False
    i = 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("|"):
            tbl = []
            while i < n and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                cells = [c.strip() for c in raw.strip("|").split("|")]
                if not set(raw) <= set("|-: "):
                    tbl.append(cells)
                i += 1
            if tbl:
                render_table(doc, tbl)
            continue
        if s.startswith("#"):
            m = re.match(r"^(#{1,4})\s+(.*)$", s)
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                if not first_h1_done:
                    first_h1_done = True   # 封面已承载主标题
                    i += 1
                    continue
                level = 2
            h = doc.add_heading("", level=min(level, 4))
            add_rich(h, text, size={2: 15, 3: 12.5, 4: 11.5}.get(level, 11), ea=HEI)
            for r in h.runs:
                r.font.bold = True
                r.font.color.rgb = BRAND
            i += 1
            continue
        if set(s) <= set("-=—") and len(s) >= 3:
            i += 1
            continue
        if s.startswith(">"):
            body = s.lstrip(">").strip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            add_rich(p, body, size=9.5, color=GRAY)
            i += 1
            continue
        if s.startswith("- ") or s.startswith("* "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.75)
            p.paragraph_format.first_line_indent = Cm(-0.35)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            add_rich(p, "• " + s[2:])
            i += 1
            continue
        m = re.match(r"^(\d+)[\.、]\s+(.*)$", s)
        if m:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.75)
            p.paragraph_format.first_line_indent = Cm(-0.5)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            add_rich(p, m.group(1) + ". " + m.group(2))
            i += 1
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        add_rich(p, s)
        i += 1


def build(spec):
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(10.5)
    _style_ea(normal, SONG)

    render_cover(doc, spec)
    parse_and_render(doc, spec["md"])
    add_footer_pagenum(doc, spec["cover_title"] + " v0.9.169")
    doc.save(str(spec["out"]))
    return spec["out"]


def verify(spec):
    d = Document(str(spec["out"]))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    full = "\n".join(parts)
    missing = [k for k in spec["keys"] if k not in full]
    ntab = len(d.tables)
    npar = len(d.paragraphs)
    print(f"[{spec['out'].name}] paragraphs={npar} tables={ntab} "
          f"keys={len(spec['keys']) - len(missing)}/{len(spec['keys'])} OK")
    if missing:
        print("  MISSING:", missing)
        return False
    return True


def main():
    ok = True
    for spec in DOCS_SPEC:
        out = build(spec)
        print("written:", out)
        ok = verify(spec) and ok
    if not ok:
        sys.exit(1)
    print("ALL DOCX GENERATED & VERIFIED")


if __name__ == "__main__":
    main()
