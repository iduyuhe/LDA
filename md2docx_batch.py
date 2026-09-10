# -*- coding: utf-8 -*-
"""Batch convert LDA resource census markdown files to Word (.docx).
Handles: headings, tables, blockquotes, ordered/unordered lists (nested),
horizontal rules, fenced code blocks, inline bold/italic/code, links.
Sets CJK fonts (黑体 for headings, 宋体 for body) for correct Chinese rendering.
"""
import os, re, glob, sys
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC_DIR = r"D:\agent_LDA"

FILES = [
    "design_alliance_census.md",
    "design_alliance_census_academia.md",
    "census_academic_leaders.md",
    "census_industry_leaders.md",
    "census_exhibitions.md",
    "census_policies.md",
    "census_ecosystem_others.md",
    "census_investors.md",
    "census_policies_project_fit.md",
    "design_alliance_resources_index.md",
    "design_alliance_resources_master.md",
    "design_alliance_resource_planning_report.md",
    "design_alliance_visit_package.md",
    "policy_application_war_map.md",
    "lda_product_plan_2027.md",
    "lda_production_system_design.md",
]

CJK_BODY = "宋体"
CJK_HEAD = "黑体"


def set_run_font(run, latin="Calibri", cjk=CJK_BODY, size=None, bold=None, italic=None, color=None):
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), cjk)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color


def add_runs(paragraph, text):
    """Parse inline **bold**, *italic*, `code`, [text](url) and add runs."""
    # Normalize: protect code spans first
    pattern = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`|\[.+?\]\(.+?\))")
    pos = 0
    for m in pattern.finditer(text):
        if pos < m.start():
            r = paragraph.add_run(text[pos:m.start()])
            set_run_font(r)
        tok = m.group(0)
        if tok.startswith("**"):
            r = paragraph.add_run(tok[2:-2])
            set_run_font(r, bold=True)
        elif tok.startswith("`"):
            r = paragraph.add_run(tok[1:-1])
            set_run_font(r, latin="Consolas", cjk="宋体")
        elif tok.startswith("*"):
            r = paragraph.add_run(tok[1:-1])
            set_run_font(r, italic=True)
        elif tok.startswith("["):
            # [text](url) -> keep text
            inner = re.match(r"\[(.+?)\]\((.+?)\)", tok)
            if inner:
                r = paragraph.add_run(inner.group(1))
                set_run_font(r)
            else:
                r = paragraph.add_run(tok)
                set_run_font(r)
        else:
            r = paragraph.add_run(tok)
            set_run_font(r)
        pos = m.end()
    if pos < len(text):
        r = paragraph.add_run(text[pos:])
        set_run_font(r)


def is_table_row(line):
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 1


def is_sep_row(line):
    s = line.strip().strip("|")
    s = s.replace(" ", "")
    return bool(re.fullmatch(r":?-+:?(\|:?-+:?)*", s)) and "-" in s


def split_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def add_table(doc, rows):
    # rows: list of cell-lists; first is header
    ncol = max(len(r) for r in rows)
    t = doc.add_table(rows=1, cols=ncol)
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    # header
    hdr = rows[0]
    for i in range(ncol):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        txt = hdr[i] if i < len(hdr) else ""
        add_runs(p, txt)
        for r in p.runs:
            set_run_font(r, cjk=CJK_HEAD, bold=True, size=9)
    # body
    for row in rows[1:]:
        cells = t.add_row().cells
        for i in range(ncol):
            cell = cells[i]
            cell.text = ""
            p = cell.paragraphs[0]
            txt = row[i] if i < len(row) else ""
            add_runs(p, txt)
            for r in p.runs:
                set_run_font(r, size=9)
    # column widths: distribute evenly
    try:
        width = Inches(6.5)
        for row in t.rows:
            for cell in row.cells:
                cell.width = width / ncol
    except Exception:
        pass
    doc.add_paragraph()


def set_hr(paragraph):
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "999999")
    pbdr.append(bottom)
    pPr.append(pbdr)


def convert(md_path, docx_path):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    doc = Document()
    # base style CJK
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), CJK_BODY)

    title_set = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # blank
        if stripped == "":
            i += 1
            continue

        # fenced code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            set_hr(p) if False else None
            r = p.add_run("\n".join(code_lines))
            set_run_font(r, latin="Consolas", cjk="宋体", size=9)
            # light shading
            pPr = p._p.get_or_add_pPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:fill"), "F2F2F2")
            pPr.append(shd)
            continue

        # horizontal rule
        if re.fullmatch(r"-{3,}|={3,}|\*{3,}", stripped):
            p = doc.add_paragraph()
            set_hr(p)
            i += 1
            continue

        # table
        if is_table_row(line) and i + 1 < n and is_sep_row(lines[i + 1]):
            rows = [split_cells(line)]
            i += 1  # skip header
            i += 1  # skip sep
            while i < n and is_table_row(lines[i]):
                rows.append(split_cells(lines[i]))
                i += 1
            add_table(doc, rows)
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if not title_set and level == 1:
                # first H1 -> Title style, centered
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                add_runs(p, text)
                for r in p.runs:
                    set_run_font(r, cjk=CJK_HEAD, bold=True, size=20)
                title_set = True
            else:
                p = doc.add_paragraph()
                p.style = doc.styles["Heading %d" % min(level, 6)] if ("Heading %d" % min(level, 6)) in [s.name for s in doc.styles] else doc.styles["Normal"]
                add_runs(p, text)
                for r in p.runs:
                    set_run_font(r, cjk=CJK_HEAD, bold=True, size=max(12, 18 - level * 1.5))
            i += 1
            continue

        # blockquote (consecutive > lines)
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i].strip()))
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.right_indent = Inches(0.2)
            add_runs(p, "  ".join(quote_lines))
            for r in p.runs:
                set_run_font(r, italic=True, size=9.5, color=RGBColor(0x55, 0x55, 0x55))
            continue

        # list (ordered / unordered), support nesting by indent
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            list_items = []
            while i < n and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                indent = len(lm.group(1))
                content = lm.group(3)
                ordered = bool(re.match(r"\d+\.", lm.group(2)))
                list_items.append((indent, ordered, content))
                i += 1
            # group by indent level
            for indent, ordered, content in list_items:
                level = indent // 2
                p = doc.add_paragraph(style="List Number" if ordered else "List Bullet")
                try:
                    p.level = level
                except Exception:
                    pass
                p.paragraph_format.left_indent = Inches(0.3 + 0.3 * level)
                add_runs(p, content)
                for r in p.runs:
                    set_run_font(r, size=10)
            continue

        # normal paragraph
        p = doc.add_paragraph()
        add_runs(p, stripped)
        for r in p.runs:
            set_run_font(r, size=10.5)
        i += 1

    doc.save(docx_path)


def main():
    ok, fail = [], []
    for fn in FILES:
        src = os.path.join(SRC_DIR, fn)
        if not os.path.exists(src):
            print("MISSING", fn)
            fail.append(fn)
            continue
        out = os.path.join(SRC_DIR, fn[:-3] + ".docx")
        try:
            convert(src, out)
            print("OK", fn, "->", os.path.basename(out))
            ok.append(fn)
        except Exception as e:
            print("FAIL", fn, repr(e))
            fail.append(fn)
    print("\nDONE: %d ok, %d fail" % (len(ok), len(fail)))
    if fail:
        print("FAILED:", fail)


if __name__ == "__main__":
    main()
