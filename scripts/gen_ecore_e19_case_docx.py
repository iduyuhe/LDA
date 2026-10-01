# -*- coding: utf-8 -*-
"""生成 E19 案例卡 DOCX（物料第四件）。

源 = docs/ecore_e19_colshare_dyn_preview.html（已通过 run_ecore_case_smoke 门禁的权威口径）。
本脚本用 python-docx 直接生成带中文字体/pt 字号/卡片式 KV 表/彩色注释的专业 DOCX，
绕开 html-to-docx 的 grid 丢弃 / 块级样式不继承 / caption 丢失 三个已知坑。

运行：C:/Users/Administrator/AppData/Local/Programs/Python/Python313-32/python.exe scripts/gen_ecore_e19_case_docx.py
"""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "ecore_e19_colshare_dyn_casecard.docx")

# 调色板（与 HTML 预览一致）
INK = RGBColor(0x0F, 0x17, 0x2A)
SUB = RGBColor(0x47, 0x56, 0x69)
ACC = RGBColor(0x25, 0x63, 0xEB)
TH_TX = RGBColor(0x1E, 0x3A, 0x8A)
WARN = RGBColor(0xB9, 0x1C, 0x1C)
OK = RGBColor(0x15, 0x80, 0x3D)
FONT = "Microsoft YaHei"


def set_run_font(run, size=None, bold=None, color=None, name=FONT):
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), name)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def shade_paragraph(p, hexcolor):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    pPr.append(shd)


def add_bottom_border(p, color="2563EB", sz="10"):
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    pPr.append(pbdr)


def set_cell_bg(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def set_table_borders(table, color="E2E8F0", sz="4"):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement("w:" + edge)
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), sz)
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), color)
        borders.append(e)
    tblPr.append(borders)


def new_para(doc, text="", size=10.5, bold=False, color=INK, before=6, after=6, line=1.6):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if text:
        r = p.add_run(text)
        set_run_font(r, size=size, bold=bold, color=color)
    return p


def add_note(doc, text, fill="EFF6FF", border="BFDFFE", color=TH_TX, bold_prefix=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(8)
    pf.space_after = Pt(10)
    pf.line_spacing = 1.5
    shade_paragraph(p, fill)
    # 左/上/下/右边框
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    for edge, w in (("top", "8"), ("bottom", "8"), ("left", "24"), ("right", "8")):
        e = OxmlElement("w:" + edge)
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), w)
        e.set(qn("w:space"), "6")
        e.set(qn("w:color"), border)
        pbdr.append(e)
    pPr.append(pbdr)
    if bold_prefix:
        rb = p.add_run(bold_prefix)
        set_run_font(rb, size=10.5, bold=True, color=color)
    r = p.add_run(text)
    set_run_font(r, size=10.5, color=color)
    return p


def add_kv_cards(doc, rows):
    """rows: list of (value, label). 渲染为 4 列单行的「卡片」表。"""
    n = len(rows)
    table = doc.add_table(rows=1, cols=n)
    table.autofit = False
    set_table_borders(table, color="E2E8F0", sz="4")
    table.columns  # ensure
    cell_w = 6.5 / n
    for i, (value, label) in enumerate(rows):
        cell = table.cell(0, i)
        set_cell_bg(cell, "FFFFFF")
        cell.width = Inches(cell_w)
        # 值
        p1 = cell.paragraphs[0]
        p1.paragraph_format.space_before = Pt(6)
        p1.paragraph_format.space_after = Pt(2)
        r1 = p1.add_run(value)
        set_run_font(r1, size=17, bold=True, color=ACC)
        # 标签
        p2 = cell.add_paragraph()
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after = Pt(6)
        p2.paragraph_format.line_spacing = 1.3
        r2 = p2.add_run(label)
        set_run_font(r2, size=9.5, color=SUB)
    # 设列宽
    for col in table.columns:
        for c in col.cells:
            c.width = Inches(cell_w)
    return table


def add_grid_table(doc, header, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(header))
    table.autofit = False
    set_table_borders(table, color="E2E8F0", sz="4")
    # 表头
    hdr = table.rows[0].cells
    for i, h in enumerate(header):
        set_cell_bg(hdr[i], "EFF6FF")
        p = hdr[i].paragraphs[0]
        r = p.add_run(h)
        set_run_font(r, size=10, bold=True, color=TH_TX)
    # 数据
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            p = cells[i].paragraphs[0]
            p.paragraph_format.line_spacing = 1.35
            r = p.add_run(val)
            set_run_font(r, size=9.5, color=INK)
    if widths:
        for ci, w in enumerate(widths):
            for c in table.columns[ci].cells:
                c.width = Inches(w)
    return table


def h2(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(16)
    pf.space_after = Pt(6)
    r = p.add_run(text)
    set_run_font(r, size=14, bold=True, color=ACC)
    add_bottom_border(p, color="2563EB", sz="10")
    return p


def build():
    doc = Document()
    # 默认正文样式（中文字体）
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10.5)
    nr = normal.element.get_or_add_rPr()
    nf = nr.find(qn("w:rFonts"))
    if nf is None:
        nf = OxmlElement("w:rFonts")
        nr.append(nf)
    nf.set(qn("w:eastAsia"), FONT)
    nf.set(qn("w:ascii"), FONT)
    nf.set(qn("w:hAnsi"), FONT)
    sec = doc.sections[0]
    sec.left_margin = Inches(0.9)
    sec.right_margin = Inches(0.9)
    sec.top_margin = Inches(0.8)
    sec.bottom_margin = Inches(0.8)

    # 标题
    t = doc.add_paragraph()
    t.paragraph_format.space_after = Pt(2)
    rt = t.add_run("LDA 电子计算征程 · E19 列侧共享的动态代价")
    set_run_font(rt, size=20, bold=True, color=INK)
    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(8)
    rs = sub.add_run("D-194 · v0.9.169 · 闭合 E18（列侧共享与架构权衡）G-S 自点名缺口")
    set_run_font(rs, size=10.5, color=SUB)

    # 诚实边界提示（红色 note）
    add_note(
        doc,
        "开关尺寸 / 重叠 / 抖动 / 信号频率均为公开量级占位（非 PDK）；不做功耗估算 ⇒ 不谈能效；"
        "绝不报 TOPS / TOPS-W / fJ/op。本页为只读设计期验证摘要，非流片后实测。",
        fill="FEF2F2", border="FECACA", color=WARN,
        bold_prefix="🔴 诚实边界：",
    )

    # ①
    h2(doc, "① 复用开关电荷注入 + 时钟馈通")
    new_para(
        doc,
        "开关关断瞬间沟道电荷注入采样电容，且时钟经栅漏重叠耦合。确定性 pedestal "
        "= Q_inj/C_s + ΔV_ft，可由每列/每开关单点失调校准消除（不进精度预算）；"
        "校准后幸存的 Pelgrom 随机残差 σ_ped = α·(C_ox·W·L)/C_s·σ_ΔVth。",
        size=10.5, after=8,
    )
    add_kv_cards(doc, [
        ("119.04 mV", "确定性 pedestal（11.90% FS）· 可校准剔除"),
        ("28.85 µV", "Pelgrom 随机残差（0.0029% FS）"),
        ("≪ 64.4 µV", "残差 ≪ kT/C（E18 地板）"),
        ("≪ 3.906 mV", "残差 ≪ 1 LSB（8 bit）"),
    ])
    add_note(
        doc,
        "真成本不是精度、是校准负担（N 列需 N 次失调校准）；随机残差可忽略 ⇒ 不是精度墙"
        "（与 E16「共模漂移可被单次全局校准消除」同口径）。",
        bold_prefix="🔴 结论：",
    )

    # ②
    h2(doc, "② 采样孔径抖动（最坏口径）")
    new_para(
        doc,
        "σ_v = π·f·V_ref·σ_t（满量程正弦最陡斜率最坏口径），地板仍是 E18 的 σ=√(kT/C_s)。",
        size=10.5, after=8,
    )
    add_kv_cards(doc, [
        ("314.16 µV", "σ_v @ 100 MHz（0.031% FS）"),
        ("20.49 MHz", "越过 kT/C 地板频率 f_ktc"),
        ("1243.4 MHz", "越过 LSB 频率 f_lsb"),
        ("条件性", "非精度限"),
    ])
    add_note(
        doc,
        "孔径抖动在低/中带宽被 kT/C 与 LSB 埋住；仅当输入带宽 >~20 MHz 才越过热噪地板、"
        ">~1.2 GHz 才越 LSB ⇒ 条件性，非墙。且 σ_v 与 C 无关，保吞吐共享抬高了 kT/C 地板"
        "⇒ 抖动相对更显著（反相关于 E18 静态收益）。",
        bold_prefix="说明：",
    )

    # ③
    h2(doc, "③ 多路开关建立时间对吞吐的侵蚀")
    new_para(
        doc,
        "τ_mux = R_on·C_s，t_mux = settle_half_lsb(τ_mux, bits)（复用 E14 同器件 R_on=6.41 Ω · "
        "E17 G-2 建立律）。C_s 是固定绝对采样电容（与共享无关），故 t_mux 不随 K 缩小。",
        size=10.5, after=8,
    )
    add_kv_cards(doc, [
        ("6.41 Ω", "复用 E14 同器件 R_on（W/L=500）"),
        ("39.99 ps", "t_mux（τ=6.41 ps）"),
        ("0.0434%", "plain 共享侵蚀（恒定 · 可忽略）"),
        ("6.944%", "保吞吐共享侵蚀 @ K*=160（∝K）"),
    ])
    add_note(
        doc,
        "plain 共享：侵蚀恒定 0.0434%（可忽略）。保吞吐共享：每列周期 T_conv(1)+K·t_mux "
        "⇒ 侵蚀 ∝ K，K*=160 处 ≈ 6.944% —— 这是 E18 静态模型此前漏计的真实动态代价，"
        "反相关于 E18 面积收益。",
        bold_prefix="🔴 结论：",
    )

    # ④ 动态预算
    h2(doc, "④ 动态预算（接 E15 合成律 · RANDOM · 1σ）")
    add_grid_table(
        doc,
        ["项", "内容", "数值"],
        [
            ["进预算项数", "电荷注入 Pelgrom 残差 + 孔径抖动（确定性 pedestal / 多路开关建立不入预算）", "2"],
            ["worst", "合成后最坏相对误差", "0.0946%"],
            ["≈ 有效位", "log2(1/worst_rel) 口径", "10.045 位"],
        ],
        widths=[1.3, 4.0, 1.2],
    )

    # 总诚实结论
    h2(doc, "E19 总诚实结论（闭合 G-S）")
    add_note(
        doc,
        "在可达共享度内，三项动态代价都不是精度墙：① 电荷注入确定性 pedestal 虽大但可校准"
        "（真成本=校准负担）；② 孔径抖动条件性（高带宽才显著）；③ 多路开关建立在保吞吐共享下"
        "随 K 回升、K* 处 ≈7% —— E18 漏计的真实动态代价。\n"
        "共享的真实新代价 = 保吞吐开关建立开销 + 高带宽孔径抖动；二者反相关于 E18 静态收益，"
        "但都不造新墙（不硬造精度腿 / 不报 TOPS）。E18 主线收口成立。",
        bold_prefix="",
    )

    # 页脚
    f = doc.add_paragraph()
    f.paragraph_format.space_before = Pt(18)
    rf = f.add_run(
        "LDA · agent-native 开源光+量子芯片设计软件 · 杜玉河 / 工业5点0产业生态联盟 · "
        "本页为只读设计期验证摘要，非流片后实测。"
    )
    set_run_font(rf, size=9, color=SUB)

    doc.save(OUT)
    print("WROTE", OUT)


if __name__ == "__main__":
    build()
