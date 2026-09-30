"""一次性：生成 M5 光计算对标案例卡三件套（HTML / PPTX / Word）。

事实源 = LDA_光计算芯片设计与成果总结_2026-09-30.md（数字以本脚本内的模块拉取为准，
与事实源一致；改数字先改事实源 + photonic_compute_benchmarks.py）。

头部关键指标从 lda_l2.photonic_compute_benchmarks 实时拉取（单一真源），
避免「文档里的数字」与「门禁里的数字」静默漂移（血案 28）。
"""
from __future__ import annotations

import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根
JOURNEY = os.path.join(ROOT, "lda", "journey_photonic_compute")


def _platform_version() -> str:
    try:
        txt = io.open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
        m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def _demo():
    """从模块拉取头部指标（单一真源）。"""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "lda"))
    from lda_l2 import photonic_compute_benchmarks as B
    d = B.lda_demonstrated()
    ext = B.scale_blind_extrapolation(800)
    return d, ext, B.PUBLIC_LANDMARKS


# ═══════════════════════════════ HTML（暗色主题，镜像 schip 体例）══════════════════════════════
CSS = """
:root{
  --bg:#0b1020; --panel:#121a2e; --panel2:#0f1729; --line:#22314f;
  --ink:#e8eefb; --mut:#9aa8c0; --acc:#4f8cff; --acc2:#7aa2ff;
  --ok:#34d399; --warn:#fbbf24; --red:#f87171;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif;}
.wrap{max-width:1100px;margin:0 auto;padding:0 24px 96px}
header.hero{padding:64px 0 32px;border-bottom:1px solid var(--line);
  background:radial-gradient(1200px 400px at 12% -10%,rgba(79,140,255,.18),transparent 60%)}
.kicker{color:var(--acc2);letter-spacing:.18em;font-size:13px;font-weight:700}
h1{font-size:40px;line-height:1.25;margin:12px 0 8px;letter-spacing:-.01em}
h1 small{display:block;font-size:17px;font-weight:500;color:var(--mut);margin-top:10px}
.badge{display:inline-block;padding:5px 12px;border:1px solid var(--warn);color:var(--warn);
  border-radius:999px;font-size:12.5px;font-weight:700;margin-right:8px}
.badge.ok{border-color:var(--ok);color:var(--ok)}
.badge.acc{border-color:var(--acc);color:var(--acc2)}
h2{font-size:24px;margin:56px 0 6px;padding-top:22px;border-top:1px solid var(--line)}
h2 .no{color:var(--acc);font-weight:800;margin-right:10px}
h3{font-size:18px;margin:30px 0 8px;color:#cfdcf5}
p{margin:12px 0}
.lead{font-size:19px;color:#d8e3f7}
.mut{color:var(--mut)}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));margin:20px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.card .k{color:var(--mut);font-size:13px;letter-spacing:.04em}
.card .v{font-size:30px;font-weight:800;color:#fff;line-height:1.2;margin-top:6px}
.card .v span{font-size:15px;font-weight:600;color:var(--acc2);margin-left:4px}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14.5px}
th{text-align:left;padding:10px 12px;border-bottom:2px solid var(--line);color:#cfdcf5;
  background:var(--panel2);font-weight:700;white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid rgba(34,49,79,.75);vertical-align:top}
tr:hover td{background:rgba(79,140,255,.05)}
code{background:#0d1526;border:1px solid var(--line);border-radius:6px;padding:2px 7px;
  font-family:ui-monospace,Consolas,"Cascadia Mono",monospace;font-size:13.5px;color:#bcd0f2}
.callout{border-radius:12px;padding:16px 20px;margin:18px 0;border:1px solid}
.callout.warn{border-color:rgba(251,191,36,.45);background:rgba(251,191,36,.08)}
.callout.ok{border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.07)}
.callout.acc{border-color:rgba(79,140,255,.45);background:rgba(79,140,255,.08)}
.callout b{color:#fff}
.foot{margin-top:64px;padding-top:22px;border-top:1px solid var(--line);color:var(--mut);font-size:13.5px}
a{color:var(--acc2)}
"""


def build_html(d, ext, landmarks, ver):
    hero = """
<header class="hero">
  <div class="kicker">LDA · 开源 Agent-native EDA（MIT）· 光计算芯片征程</div>
  <h1>硅光张量核 / 光神经网络 LDA-P
    <small>MZI mesh 干涉架构 · 从「能算」到「算得准、规模达国际水平」· 设计&验证闭环</small>
  </h1>
  <div style="margin-top:18px">
    <span class="badge ok">N=256 网格保真 0.9932</span>
    <span class="badge ok">scale-blind 真身</span>
    <span class="badge acc">闭环 Vπ 标定</span>
    <span class="badge">零外部光学 SDK</span>
    <span class="badge">判决路径无 LLM</span>
    <span class="badge">设计&验证 · 非流片实测</span>
  </div>
  <p class="lead" style="margin-top:22px">
    <b>用 LDA 从零设计一颗硅光张量核 / 光神经网络芯片：非酉 SVD 分解 → 激活量化标定 →
    光电协同仿真 → 规模扩张 tiling，走完设计&验证闭环，并对标国际公开基准（Lightmatter / MIT / 清华）。</b>
  </p>
  <p class="mut">这不是一次器件仿真，而是一次「平台能不能真的设计一颗光计算芯片并验证其正确性」的体检——吃自己的狗粮。</p>
</header>
"""
    metrics = """
<div class="grid">
  <div class="card"><div class="k">最大已验证矩阵</div><div class="v">%d<span>×%d</span></div>
    <div class="mut" style="font-size:13px">%d MZI（Reck 三角分解）</div></div>
  <div class="card"><div class="k">N=256 网格酉保真度</div><div class="v">%.4f</div>
    <div class="mut" style="font-size:13px">规模盲：1−F 随 N 不塌缩</div></div>
  <div class="card"><div class="k">scale-blind 判定</div><div class="v">True</div>
    <div class="mut" style="font-size:13px">ratio 相对标准差 %.2f%%</div></div>
  <div class="card"><div class="k">tiling 保真增益</div><div class="v">%.1f<span>×</span></div>
    <div class="mut" style="font-size:13px">局部标定相对 monolithic</div></div>
  <div class="card"><div class="k">EO 全精度精度</div><div class="v">%.0f%%</div>
    <div class="mut" style="font-size:13px">Vπ+5%% 未标定 83.3%% → 标定 100%%</div></div>
  <div class="card"><div class="k">设计容量延展</div><div class="v">%d<span>×%d</span></div>
    <div class="mut" style="font-size:13px">文献 MZI-mesh 最大类（理想 fab）</div></div>
</div>
""" % (
        d["max_matrix_verified"], d["max_matrix_verified"], d["mzi_count_at_256"],
        d["grid_fidelity_at_256"], 100 * d["scale_blind_ratio_rel_std"],
        d["tiling_fidelity_gain_x"], 100 * d["eo_full_accuracy"],
        ext["N_target"], ext["N_target"],
    )

    # 对标表
    rows = []
    for k, v in landmarks.items():
        who = v.get("who", "")
        yr = v.get("year", "")
        arch = v.get("arch", "")
        src = v.get("source", "")
        if "tops_w_photonic_core" in v:
            metric = "%.0f TOPS/W（光子核）" % v["tops_w_photonic_core"]
        elif "tops_w" in v:
            metric = "%.0f TOPS/W" % v["tops_w"]
        elif "tops_w_excl_lasers" in v:
            metric = "%.2f TOPS/W（不含激光）" % v["tops_w_excl_lasers"]
        elif "energy_aj_per_mac" in v:
            metric = "%.0f aJ/MAC · %.0f Gsa/s" % (v["energy_aj_per_mac"], v["throughput_gsa"])
        elif "acc_train" in v:
            metric = "训练 %.0f%% / 推理 %.0f%% · <%.1f ns" % (
                100 * v["acc_train"], 100 * v["acc_infer"], 1e9 * v["latency_per_pass_s"])
        else:
            metric = v.get("note", v.get("venue", ""))
        rows.append("<tr><td><b>%s</b><br><span class='mut'>%s</span></td><td>%s</td>"
                    "<td>%s</td><td class='mut' style='font-size:12px'>%s</td></tr>"
                    % (who, yr, arch, metric, src))
    bench_tbl = ("<h2><span class='no'>04</span>对标国际公开基准（A 级 golden）</h2>"
                "<div class='callout warn'>⚠️ 下表为 2024–2026 公开报道的「已交付/已流片光子芯片」数字，"
                "仅作背景坐标；本案例为<b>设计&验证层能力证明</b>，两者不同台比较。</div>"
                "<table><tr><th>主体 / 年份</th><th>架构</th><th>关键指标</th><th>来源</th></tr>"
                + "".join(rows) + "</table>")

    honest = """
<h2><span class='no'>07</span>诚实边界（逐条）</h2>
<div class='callout warn'><ol>
<li><b>非流片 / 非实测芯片</b>：全部为设计期验证；无 foundry 回片、无光学校准实测、无 TOPS/W 实测。</li>
<li><b>不宣称任何 fabricated 能效数字</b>：公开基准的 TOPS/W 是「已交付芯片」的实测/厂商标称；LDA 不报任何 pj/MAC、TOPS/W。</li>
<li><b>比较按架构族 + 设计质量方法论</b>：不按 die 级 benchmark 数字同台比；LDA 的 MZI mesh 与 MIT 学术 lineage 同族。</li>
<li><b>规模 = 设计容量</b>：256 是「可设计且可验证保真度」的矩阵规模，非已制备器件；延展到 800×800 类靠 scale-blind 性质（理想 fab 假设）。</li>
<li><b>EO 链路为行为级（T1 候选，非 ORACLE）</b>：驱动/TIA 用一阶 RC + 单极点模型，不碰晶体管级 DAC/ADC/SerDes/DSP。</li>
<li><b>零能效数字纪律</b>：复用 assert_no_energy_metrics；模块不输出能效指标。</li>
<li><b>Vπ 跨模块口径未统一</b>：光侧 25 V·cm vs EIC 侧 7.5 V·mm（差 ~3.3×），已在 co-sim 层用单一 vpi_v=7.5V 贯穿规避；根因统一留作独立 sprint（任务 #7）。</li>
</ol></div>
"""
    sec_what = """
<h2><span class='no'>01</span>这颗芯片是什么</h2>
<table>
<tr><th>维度</th><th>内容</th></tr>
<tr><td><b>物理载体</b></td><td>硅光子计算（MZI mesh 干涉 · 相干光学线性代数）</td></tr>
<tr><td><b>计算原语</b></td><td>任意酉矩阵（Reck 三角分解）+ 对角衰减 ⇒ 任意实矩阵；复矩阵走 SVD 双网格</td></tr>
<tr><td><b>电子接口</b></td><td>DAC 下发相移 → 一阶 RC 驱动 → 相移器（Vπ） → 光网格 → 光电探测 → 单极点 TIA 读回</td></tr>
<tr><td><b>闭环标定</b></td><td>基于 DAC 下发 + TIA 强度读回<b>反估真实 Vπ</b> 并补偿指令，回收 Vπ 失配精度</td></tr>
<tr><td><b>非线性</b></td><td>relu / sigmoid / tanh 激活（计算后电子侧实现）</td></tr>
<tr><td><b>规模架构</b></td><td>tiling 阵列化：N×N 切 k×k 个 T×T 子块，每块独立标定环 + 块间交叉开关</td></tr>
<tr><td><b>外部依赖</b></td><td><b>零外部光学 SDK</b>（不依赖 Meep / Tidy3D / Lumerical）；物理内核平台自研</td></tr>
</table>
"""
    sec_road = """
<h2><span class='no'>02</span>四段征程（M1 → M4）</h2>
<table>
<tr><th>段</th><th>标题</th><th>关键结果</th></tr>
<tr><td><b>M1</b></td><td>非酉 SVD 光计算路径</td><td>SVD(W=U·Σ·V†) → 双 MZI 网格 + 对角衰减；Reck 三角分解；相移闭环标定</td></tr>
<tr><td><b>M2</b></td><td>激活 + 量化 / 标定 + 精度锚</td><td>relu/sigmoid/tanh；相位量化；Vπ·L 律标定环；端到端精度锚 100%</td></tr>
<tr><td><b>M3</b></td><td>光电协同仿真（光核 + 电子接口）</td><td>DAC→驱动→相移器→光网格→PD→TIA 全链路 co-sim；闭环 Vπ 标定回收精度</td></tr>
<tr><td><b>M4</b></td><td>规模扩张 / tiling 压力测试</td><td>规模盲保真（1−F≈常数，随 N 不塌缩）；tiling 局部标定增益 2.8×；N=256 网格保真 0.9932</td></tr>
</table>
"""
    sec_results = """
<h2><span class='no'>03</span>关键技术结果（可复核）</h2>
<h3>3.1 光电协同仿真（M3）</h3>
<table>
<tr><th>场景</th><th>精度</th><th>权重相对误差</th></tr>
<tr><td>EO 全精度（16-bit）</td><td>100%</td><td>0.0015</td></tr>
<tr><td>2-bit 量化</td><td>66.7%</td><td>1.059</td></tr>
<tr><td>Vπ+5% 未标定</td><td>83.3%</td><td>0.209</td></tr>
<tr><td><b>Vπ+5% 标定为</b></td><td><b>100%</b></td><td><b>0.0017</b></td></tr>
</table>
<p class="mut">DAC 2/4/8/12-bit 相位误差 0.49 / 0.107 / 0.0063 / 0.0011 rad；8-bit 标定残差 0.331%；
TIA z0=2000Ω、z@f3dB=1414Ω、高频滚降 0.141。</p>
<h3>3.2 规模盲 + tiling（M4）</h3>
<table>
<tr><th>指标</th><th>值</th></tr>
<tr><td>规模盲判定</td><td>True（(1−F)/√((N−1)/N) 相对标准差 7.66%）</td></tr>
<tr><td>tiling 收益</td><td>mono 1−F=0.0247 → tiled 0.0088（局部标定再降 2.8×）</td></tr>
<tr><td>路由损耗</td><td>k=1→0 / k=8→33.6 dB / k=32→595.2 dB（单调）</td></tr>
<tr><td>大 N 网格保真度</td><td>N=64 / 128 / 256 ⇒ 0.9967 / 0.9952 / 0.9932</td></tr>
</table>
<div class='callout acc'><b>判决全部为死标量比对，LLM 不进判决路径</b>；物理定律（酉幺正性、Vπ·L 律）作<b>红线锚</b>。</div>
"""
    sec_arch = """
<h2><span class='no'>05</span>架构族对齐（诚实比较的核心）</h2>
<ul>
<li><b>LDA 的 MZI mesh 与 MIT 学术 lineage（Shen/Harris 2017 → 2025 Nature 128×128 PTC）同族</b>；
Lightmatter 商用 Envise 采用「光广播 + 电子加权」口径（AIP AML 表记 0.81 TOPS/W），与纯 MZI mesh 实现为不同子架构。</li>
<li><b>文献 MZI-mesh 最大类 ≤800×800</b>（AIP AML 2024）。LDA 已验证 N=256（32640 MZI）网格保真 0.9932，设计容量可借 scale-blind 性质延展到 800×800 类（理想 fab 假设）。</li>
<li><b>该 lineage 的公开瓶颈</b>正是「MZI mesh 受限于制备误差（fabrication imperfections）」（AIP AML 2024 原文）。
LDA 的 <b>scale-blind 保真 + 闭环 Vπ 标定 + tiling 局部标定</b> 正是对这一瓶颈的工程解。</li>
</ul>
"""
    sec_adv = """
<h2><span class='no'>06</span>先进性定位（诚实版）</h2>
<div class='callout warn'>⚠️ 本案例是<b>设计工具链的能力证明</b>，不是「又造了一颗更快的光子芯片」。把 256 / 800 读成「已制备光子芯片」即为失真。</div>
<h3>本案例的差异点（不做数值同台比较）</h3>
<table>
<tr><th>维度</th><th>产业界</th><th>本案例</th></tr>
<tr><td><b>交付物</b></td><td>已流片 / 已交付光子芯片 + 实测 TOPS/W</td><td><b>设计&验证工具链</b>：MZI mesh 张量核的可设计 + 可验证保真闭环</td></tr>
<tr><td><b>工具链</b></td><td>各自闭源 CAD/PDK + 控制 ASIC</td><td><b>开源（MIT）· Agent-native</b> · 物理内核自研 · 零外部光学 SDK</td></tr>
<tr><td><b>判决路径</b></td><td>实验标定 + 数值仿真混合</td><td><b>LLM 不进判决路径</b>；死标量比对；红线为物理定律</td></tr>
<tr><td><b>能效数字</b></td><td>实测 / 标称 TOPS/W（制造+系统级）</td><td><b>不报任何 fabricated 能效数字</b></td></tr>
<tr><td><b>对标维度</b></td><td>die 级 benchmark</td><td><b>架构族 + 设计质量方法论</b></td></tr>
</table>
"""
    sec_cap = """
<h2><span class='no'>08</span>平台能力增量（吃狗粮的意义）</h2>
<ol>
<li><b>非酉光计算路径</b>：SVD 双网格 + 对角衰减，突破「只能算酉矩阵」的限制。</li>
<li><b>光电协同仿真框架</b>：把既有 EIC 行为级模型与光计算核接成闭环，平台第一次能设计「光核 + 电子接口」的完整芯片。</li>
<li><b>闭环标定（控制环）</b>：用 DAC 下发 + TIA 读回反估真实 Vπ，平台第一次有「读回→补偿」的校准能力。</li>
<li><b>规模可扩展性验证</b>：scale-blind 保真度证明大 N 不塌缩；tiling 架构给出局部标定增益与路由损耗代价模型。</li>
<li><b>对标纪律</b>：用 A 级公开来源登记产业界 landmark，平台第一次把「达国际水平」落到可复核的对标表。</li>
</ol>
"""
    foot = """
<div class="foot">
  <p><b>LDA</b>（开源 Agent-native EDA · MIT）· 光计算芯片 LDA-P · 版本 %s · 2026-09-30</p>
  <p>平台账本：CI core 236 条回归成员 · 验证锚 <b>476</b>（严格独立 455 / 降级 3 / 自证桩 18）· 独立率 95.59%%</p>
  <p>本征程门禁：<code>run_photonic_compute_m1..m5_smoke.py</code> · M5 单文件 33 判据全绿</p>
  <p class="mut">本页为《LDA_光计算芯片设计与成果总结_2026-09-30.md》的派生包装；数字以事实源 + photonic_compute_benchmarks.py 为准。</p>
</div>
""" % ver

    html = ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>LDA 光计算芯片 · 设计与成果介绍</title><style>%s</style></head>"
            "<body><div class='wrap'>" % CSS
            + hero + metrics + sec_what + sec_road + sec_results
            + bench_tbl + sec_arch + sec_adv + honest + sec_cap + foot
            + "</div></body></html>\n")
    out = os.path.join(JOURNEY, "pc_m5.html")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("已生成 HTML：%s（%.1f KB）" % (out, len(html.encode("utf-8")) / 1024.0))


# ═══════════════════════════════ PPTX（路演 10 页）══════════════════════════════
def build_pptx(d, ext, landmarks, ver):
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    SW = prs.slide_width

    BG = RGBColor(0x0B, 0x10, 0x20)
    PANEL = RGBColor(0x12, 0x1A, 0x2E)
    INK = RGBColor(0xE8, 0xEE, 0xFB)
    MUT = RGBColor(0x9A, 0xA8, 0xC0)
    ACC = RGBColor(0x4F, 0x8C, 0xFF)
    OK = RGBColor(0x34, 0xD3, 0x99)
    WARN = RGBColor(0xFB, 0xBF, 0x24)

    blank = prs.slide_layouts[6]

    def add_slide():
        s = prs.slides.add_slide(blank)
        bg = s.background
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG
        return s

    def box(s, l, t, w, h, fill=None):
        from pptx.enum.shapes import MSO_SHAPE
        shp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
        shp.line.fill.background()
        if fill is None:
            shp.fill.background()
        else:
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill
        shp.shadow.inherit = False
        return shp

    def text(s, l, t, w, h, runs, align=PP_ALIGN.LEFT, anchor="top"):
        tb = s.shapes.add_textbox(l, t, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        from pptx.enum.text import MSO_ANCHOR
        tf.vertical_anchor = (MSO_ANCHOR.MIDDLE if anchor == "middle"
                              else MSO_ANCHOR.TOP)
        if isinstance(runs, str):
            runs = [(runs, 18, INK, False)]
        first = True
        for item in runs:
            txt, size, color, bold = (item + (False,))[:4] if len(item) < 4 else item
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = align
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color
            r.font.bold = bold; r.font.name = "Microsoft YaHei"
        return tb

    # 1. 封面
    s = add_slide()
    box(s, 0, 0, SW, Inches(0.18), ACC)
    text(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(1.2),
         [("硅光张量核 / 光神经网络", 40, INK, True)])
    text(s, Inches(0.9), Inches(3.1), Inches(11.5), Inches(1.0),
         [("LDA-P · 用开源 Agent-native EDA 亲手设计的「光计算芯片」（MZI mesh）", 20, MUT, False)])
    text(s, Inches(0.9), Inches(4.3), Inches(11.5), Inches(0.6),
         [("设计&验证能力证明 · 对标国际公开基准（Lightmatter / MIT / 清华）", 16, ACC, False)])
    text(s, Inches(0.9), Inches(6.6), Inches(11.5), Inches(0.5),
         [("LDA（MIT · v%s）· 2026-09-30 · 非流片实测，设计期签核" % ver, 13, MUT, False)])

    # 2. 一句话定位
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("01 · 一句话定位", 26, ACC, True)])
    box(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(2.2), PANEL)
    text(s, Inches(1.2), Inches(1.7), Inches(11.0), Inches(1.8),
         [("用 LDA 从零设计一颗硅光张量核 / 光神经网络芯片（MZI mesh 干涉架构）：", 20, INK, True),
          ("非酉 SVD 分解（M1）→ 激活/量化/标定（M2）→ 光电协同仿真（M3）→ 规模扩张 tiling（M4），", 17, INK, False),
          ("并对标国际公开基准，给出诚实的达国际水平口径。", 17, INK, False)])
    text(s, Inches(0.9), Inches(4.1), Inches(11.5), Inches(2.6),
         [("吃狗粮（dogfooding）：这不是器件仿真，而是「平台能不能真的设计一颗光计算", 16, MUT, False),
          ("芯片并验证其正确性」的体检——平台亲手设计，自身先行使用并检验。", 16, MUT, False),
          ("核心纪律：零外部光学 SDK · LLM 不进判决路径 · 零能效数字 · 判决为死标量比对。", 16, OK, False)])

    # 3. 关键指标
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("02 · 关键指标（M1–M4 已验证）", 26, ACC, True)])
    cards = [
        ("最大已验证矩阵", "%d×%d" % (d["max_matrix_verified"], d["max_matrix_verified"]), "%d MZI" % d["mzi_count_at_256"]),
        ("N=256 网格保真度", "%.4f" % d["grid_fidelity_at_256"], "规模盲：1−F 不塌缩"),
        ("scale-blind", "True", "ratio 相对标准差 %.1f%%" % (100 * d["scale_blind_ratio_rel_std"])),
        ("tiling 保真增益", "%.1f×" % d["tiling_fidelity_gain_x"], "局部标定 vs monolithic"),
        ("EO 全精度", "100%", "Vπ+5%% 未标定 83.3%%→标定 100%%"),
        ("设计容量延展", "%d×%d" % (ext["N_target"], ext["N_target"]), "文献 MZI-mesh 最大类"),
    ]
    cw, ch = Inches(3.7), Inches(2.1)
    gx, gy = Inches(0.35), Inches(0.35)
    x0, y0 = Inches(0.9), Inches(1.6)
    for i, (k, v, sub) in enumerate(cards):
        r, c = divmod(i, 3)
        l = x0 + c * (cw + gx); t = y0 + r * (ch + gy)
        box(s, l, t, cw, ch, PANEL)
        text(s, l + Inches(0.2), t + Inches(0.15), cw - Inches(0.4), Inches(0.5),
             [(k, 14, MUT, False)])
        text(s, l + Inches(0.2), t + Inches(0.6), cw - Inches(0.4), Inches(0.9),
             [(v, 34, INK, True)])
        text(s, l + Inches(0.2), t + Inches(1.5), cw - Inches(0.4), Inches(0.5),
             [(sub, 12, ACC, False)])

    # 4. 四段征程
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("03 · 四段征程（M1 → M4）", 26, ACC, True)])
    rows = [
        ("M1", "非酉 SVD 光计算路径", "SVD 双网格 + 对角衰减；Reck 三角分解；相移闭环标定"),
        ("M2", "激活 + 量化 / 标定 + 精度锚", "relu/sigmoid/tanh；相位量化；Vπ·L 律标定环；端到端精度锚 100%"),
        ("M3", "光电协同仿真（光核 + 电子接口）", "DAC→驱动→相移器→光网格→PD→TIA 全链路 co-sim；闭环 Vπ 标定回收精度"),
        ("M4", "规模扩张 / tiling 压力测试", "规模盲保真（1−F≈常数）；tiling 局部标定增益 2.8×；N=256 保真 0.9932"),
    ]
    y = Inches(1.7)
    for tag, title, res in rows:
        box(s, Inches(0.9), y, Inches(1.1), Inches(1.15), ACC)
        text(s, Inches(0.9), y, Inches(1.1), Inches(1.15),
             [(tag, 22, INK, True)], align=PP_ALIGN.CENTER, anchor="middle")
        box(s, Inches(2.1), y, Inches(10.3), Inches(1.15), PANEL)
        text(s, Inches(2.3), y + Inches(0.1), Inches(10.0), Inches(0.5),
             [(title, 17, INK, True)])
        text(s, Inches(2.3), y + Inches(0.55), Inches(10.0), Inches(0.55),
             [(res, 13, MUT, False)])
        y += Inches(1.3)

    # 5. 关键技术结果
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("04 · 关键技术结果（可复核）", 26, ACC, True)])
    text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(0.5),
         [("光电协同仿真（M3）：闭环 Vπ 标定回收精度", 18, INK, True)])
    eo = [("EO 全精度 16-bit", "100%", "0.0015"),
          ("2-bit 量化", "66.7%", "1.059"),
          ("Vπ+5% 未标定", "83.3%", "0.209"),
          ("Vπ+5% 标定为", "100%", "0.0017")]
    x = Inches(0.9)
    for a, b, c in eo:
        box(s, x, Inches(2.1), Inches(2.8), Inches(1.4), PANEL)
        text(s, x, Inches(2.2), Inches(2.8), Inches(0.5), [(a, 13, MUT, False)], align=PP_ALIGN.CENTER)
        text(s, x, Inches(2.6), Inches(2.8), Inches(0.6), [(b, 24, OK if "标定" in a else INK, True)], align=PP_ALIGN.CENTER)
        text(s, x, Inches(3.2), Inches(2.8), Inches(0.4), [("权重误差 %s" % c, 12, ACC, False)], align=PP_ALIGN.CENTER)
        x += Inches(3.0)
    text(s, Inches(0.9), Inches(3.9), Inches(11.5), Inches(0.5),
         [("规模盲 + tiling（M4）", 18, INK, True)])
    text(s, Inches(0.9), Inches(4.5), Inches(11.5), Inches(2.4),
         [("• 规模盲判定 True：(1−F)/√((N−1)/N) 相对标准差 7.66% —— 大 N 不塌缩", 15, INK, False),
          ("• tiling 收益：mono 1−F=0.0247 → tiled 0.0088（局部标定再降 2.8×）", 15, INK, False),
          ("• 大 N 网格保真度：N=64/128/256 ⇒ 0.9967 / 0.9952 / 0.9932", 15, INK, False),
          ("• 判决为死标量比对，LLM 不进判决路径；物理定律（酉幺正性、Vπ·L 律）作红线锚", 15, OK, False)])

    # 6. 对标国际基准
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("05 · 对标国际公开基准（A 级 golden）", 26, ACC, True)])
    text(s, Inches(0.9), Inches(1.4), Inches(11.5), Inches(0.5),
         [("⚠ 仅为 2024–2026 公开「已交付/已流片光子芯片」背景坐标；本案例为设计&验证层，不同台比较", 13, WARN, False)])
    y = Inches(2.0)
    lm = [
        ("Lightmatter", "Envise（Nature 2025）：4×128×128 PTC，262 TOPS/W，~200ps/MVM，ResNet18 86.4%"),
        ("MIT（Englund）", "2017 可编程纳米光子（MZI 原创 lineage）；2024 全集成>96%/92%；2026 ~20 aJ/MAC"),
        ("清华 Taichi", "Science 2024：160 TOPS/W，分布式广度光计算，支持内容生成"),
        ("AIP AML 2024 表", "MZI-mesh ≤800×800 / ≤9 TOPS/W；B200 9；IBM Hermes 9.76 TOPS/W"),
    ]
    for who, item in lm:
        box(s, Inches(0.9), y, Inches(2.5), Inches(0.95), PANEL)
        text(s, Inches(1.0), y, Inches(2.3), Inches(0.95), [(who, 15, ACC, True)], anchor="middle")
        box(s, Inches(3.5), y, Inches(9.0), Inches(0.95), PANEL)
        text(s, Inches(3.7), y, Inches(8.6), Inches(0.95), [(item, 13, INK, False)], anchor="middle")
        y += Inches(1.05)

    # 7. 架构族对齐
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("06 · 架构族对齐（诚实比较的核心）", 26, ACC, True)])
    text(s, Inches(0.9), Inches(1.6), Inches(11.5), Inches(5.0),
         [("• LDA 的 MZI mesh 与 MIT 学术 lineage（Shen/Harris 2017 → 2025 Nature 128×128 PTC）同族；", 17, INK, False),
          ("  Lightmatter 商用 Envise 采用「光广播 + 电子加权」口径（AIP AML 表记 0.81 TOPS/W），为不同子架构。", 15, MUT, False),
          ("• 文献 MZI-mesh 最大类 ≤800×800（AIP AML 2024）；LDA 已验证 N=256（32640 MZI）保真 0.9932，", 17, INK, False),
          ("  设计容量可借 scale-blind 性质延展到 800×800 类（理想 fab 假设）。", 15, MUT, False),
          ("• 该 lineage 的公开瓶颈正是「MZI mesh 受限于制备误差」（AIP AML 2024 原文）——", 17, INK, False),
          ("  LDA 的 scale-blind 保真 + 闭环 Vπ 标定 + tiling 局部标定 正是对该瓶颈的工程解。", 16, OK, True)])

    # 8. 先进性定位
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("07 · 先进性定位（诚实版）", 26, ACC, True)])
    diff = [("交付物", "已流片光子芯片+实测TOPS/W", "设计&验证工具链：MZI mesh 可设计+可验证保真闭环"),
            ("工具链", "闭源 CAD/PDK + 控制 ASIC", "开源(MIT)·Agent-native·零外部光学 SDK"),
            ("判决路径", "实验标定+数值仿真混合", "LLM 不进判决路径；死标量比对"),
            ("能效数字", "实测/标称 TOPS/W", "不报任何 fabricated 能效数字"),
            ("对标维度", "die 级 benchmark", "架构族+设计质量方法论")]
    y = Inches(1.7)
    for k, a, b in diff:
        text(s, Inches(0.9), y, Inches(2.0), Inches(0.6), [(k, 15, ACC, True)])
        text(s, Inches(3.0), y, Inches(4.4), Inches(0.6), [(a, 13, MUT, False)])
        text(s, Inches(7.6), y, Inches(5.0), Inches(0.6), [("→ " + b, 13, INK, False)])
        y += Inches(0.95)
    text(s, Inches(0.9), Inches(6.6), Inches(11.5), Inches(0.6),
         [("不宣称在 TOPS/W / 延迟 / 准确率上优于任何厂商；做对了「设计工具链能力证明」。", 14, WARN, False)])

    # 9. 诚实边界
    s = add_slide()
    text(s, Inches(0.9), Inches(0.5), Inches(11.5), Inches(0.7),
         [("08 · 诚实边界（逐条）", 26, ACC, True)])
    gaps = [
        "非流片 / 非实测芯片：无 foundry 回片、无光学校准实测、无 TOPS/W 实测。",
        "不宣称任何 fabricated 能效数字：LDA 不报任何 pj/MAC、TOPS/W。",
        "比较按架构族 + 设计质量方法论，不按 die 级 benchmark 同台比。",
        "规模 = 设计容量：256 可设计验证，非已制备；延展 800×800 靠 scale-blind（理想 fab）。",
        "EO 链路为行为级（T1 候选，非 ORACLE）：不碰晶体管级 DAC/ADC/SerDes/DSP。",
        "零能效数字纪律：复用 assert_no_energy_metrics；Vπ 跨模块口径差（任务 #7）已规避。",
    ]
    y = Inches(1.6)
    for g in gaps:
        text(s, Inches(1.1), y, Inches(11.2), Inches(0.8),
             [("• " + g, 15, INK, False)])
        y += Inches(0.85)

    # 10. 收尾
    s = add_slide()
    box(s, 0, 0, SW, Inches(0.18), OK)
    text(s, Inches(0.9), Inches(1.6), Inches(11.5), Inches(1.0),
         [("平台能力增量（吃狗粮的意义）", 28, INK, True)])
    text(s, Inches(0.9), Inches(2.8), Inches(11.5), Inches(3.6),
         [("① 非酉光计算路径：SVD 双网格，突破「只能算酉矩阵」。", 17, INK, False),
          ("② 光电协同仿真框架：第一次能设计「光核 + 电子接口」完整芯片。", 17, INK, False),
          ("③ 闭环标定（控制环）：第一次有「读回 → 补偿」的校准能力。", 17, INK, False),
          ("④ 规模可扩展性验证：scale-blind 不塌缩 + tiling 增益/损耗模型。", 17, INK, False),
          ("⑤ 对标纪律：A 级公开来源登记 landmark，把「达国际水平」落到可复核对标表。", 17, OK, False)])

    out = os.path.join(ROOT, "LDA_光计算芯片介绍_路演.pptx")
    prs.save(out)
    print("已生成 PPTX：%s（%d 页）" % (out, len(prs.slides._sldIdLst)))


# ═══════════════════════════════ Word（结构化文档）══════════════════════════════
def build_docx(d, ext, landmarks, ver):
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Microsoft YaHei"
    st.font.size = Pt(11)
    st.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    def h1(t):
        p = doc.add_heading(t, level=1)
        return p

    def h2(t):
        return doc.add_heading(t, level=2)

    def para(t, bold=False, color=None, size=None):
        p = doc.add_paragraph()
        r = p.add_run(t)
        r.bold = bold
        if color:
            r.font.color.rgb = color
        if size:
            r.font.size = Pt(size)
        return p

    def bullet(t):
        return doc.add_paragraph(t, style="List Bullet")

    title = doc.add_heading("LDA 光计算芯片 · 设计与成果总结（对标国际基准）", level=0)
    para("LDA-P · 硅光张量核 / 光神经网络（光子计算芯片）", bold=True)
    para("版本日期：2026-09-30 · 平台：LDA（开源 Agent-native EDA，MIT）· 版本 %s" % ver)
    para("对外口径：设计&验证能力证明（非流片后实测芯片）")

    h1("一、一句话定位")
    para("用 LDA 从零设计一颗硅光张量核 / 光神经网络芯片（MZI mesh 干涉架构）：从「能算」（M1 非酉 SVD 分解）→"
         "「算得准」（M2 激活/量化/标定）→「能设计完整芯片：光核+电子接口」（M3 光电协同仿真）→"
         "「规模达国际水平」（M4 规模盲+tiling），并对标国际公开基准（Lightmatter / MIT / 清华），给出诚实的达国际水平口径。")
    para("这不是一次器件仿真，而是一次「平台能不能真的设计一颗光计算芯片并验证其正确性」的体检——用 LDA 亲手设计，吃自己的狗粮。")

    h1("二、这颗芯片是什么")
    tbl = doc.add_table(rows=1, cols=2)
    tbl.style = "Light Grid Accent 1"
    tbl.rows[0].cells[0].text = "维度"
    tbl.rows[0].cells[1].text = "内容"
    for k, v in [
        ("物理载体", "硅光子计算（MZI mesh 干涉 · 相干光学线性代数）"),
        ("计算原语", "任意酉矩阵（Reck 三角分解）+ 对角衰减 ⇒ 任意实矩阵；复矩阵走 SVD 双网格"),
        ("电子接口", "DAC 下发相移 → 一阶 RC 驱动 → 相移器（Vπ） → 光网格 → 光电探测 → 单极点 TIA 读回"),
        ("闭环标定", "基于 DAC 下发 + TIA 强度读回反估真实 Vπ 并补偿指令，回收 Vπ 失配精度"),
        ("外部依赖", "零外部光学 SDK（不依赖 Meep / Tidy3D / Lumerical）；物理内核平台自研"),
        ("判决路径", "LLM 不进判决路径；死标量比对；红线为物理定律（酉幺正性、Vπ·L 律）"),
    ]:
        c = tbl.add_row().cells
        c[0].text = k; c[1].text = v

    h1("三、四段征程（M1 → M4）")
    for tag, title, res in [
        ("M1", "非酉 SVD 光计算路径", "SVD(W=U·Σ·V†) → 双 MZI 网格 + 对角衰减；Reck 三角分解；相移闭环标定"),
        ("M2", "激活 + 量化 / 标定 + 精度锚", "relu/sigmoid/tanh；相位量化；Vπ·L 律标定环；端到端精度锚 100%"),
        ("M3", "光电协同仿真（光核 + 电子接口）", "DAC→驱动→相移器→光网格→PD→TIA 全链路 co-sim；闭环 Vπ 标定回收精度"),
        ("M4", "规模扩张 / tiling 压力测试", "规模盲保真（1−F≈常数，随 N 不塌缩）；tiling 局部标定增益 2.8×；N=256 网格保真 0.9932"),
    ]:
        p = doc.add_paragraph()
        p.add_run("%s · %s" % (tag, title)).bold = True
        doc.add_paragraph(res)

    h2("M3 关键技术结果")
    t3 = doc.add_table(rows=1, cols=3); t3.style = "Light Grid Accent 1"
    for i, htext in enumerate(["场景", "精度", "权重相对误差"]):
        t3.rows[0].cells[i].text = htext
    for a, b, c in [("EO 全精度（16-bit）", "100%", "0.0015"), ("2-bit 量化", "66.7%", "1.059"),
                    ("Vπ+5% 未标定", "83.3%", "0.209"), ("Vπ+5% 标定为", "100%", "0.0017")]:
        cells = t3.add_row().cells
        cells[0].text = a; cells[1].text = b; cells[2].text = c
    para("DAC 2/4/8/12-bit 相位误差 0.49 / 0.107 / 0.0063 / 0.0011 rad；8-bit 标定残差 0.331%。", size=10)

    h2("M4 关键技术结果")
    bullet("规模盲判定 True：(1−F)/√((N−1)/N) 相对标准差 7.66%")
    bullet("tiling 收益：mono 1−F=0.0247 → tiled 0.0088（局部标定再降 2.8×）")
    bullet("大 N 网格保真度：N=64 / 128 / 256 ⇒ 0.9967 / 0.9952 / 0.9932")

    h1("四、对标国际公开基准（A 级 golden · 带来源）")
    para("⚠ 以下为 2024–2026 公开报道的「已交付/已流片光子芯片」数字，仅作背景坐标；本案例为设计&验证层能力证明，两者不同台比较。",
         color=RGBColor(0xB0, 0x60, 0x00))
    t4 = doc.add_table(rows=1, cols=3); t4.style = "Light Grid Accent 1"
    for i, htext in enumerate(["主体", "关键指标", "来源"]):
        t4.rows[0].cells[i].text = htext
    for k, v in landmarks.items():
        if "tops_w_photonic_core" in v:
            metric = "%.0f TOPS/W（光子核）" % v["tops_w_photonic_core"]
        elif "tops_w" in v:
            metric = "%.0f TOPS/W" % v["tops_w"]
        elif "tops_w_excl_lasers" in v:
            metric = "%.2f TOPS/W（不含激光）" % v["tops_w_excl_lasers"]
        elif "energy_aj_per_mac" in v:
            metric = "%.0f aJ/MAC · %.0f Gsa/s" % (v["energy_aj_per_mac"], v["throughput_gsa"])
        elif "acc_train" in v:
            metric = "训练 %.0f%% / 推理 %.0f%%" % (100 * v["acc_train"], 100 * v["acc_infer"])
        else:
            metric = v.get("note", v.get("venue", ""))
        cells = t4.add_row().cells
        cells[0].text = "%s (%s)" % (v.get("who", ""), v.get("year", ""))
        cells[1].text = metric
        cells[2].text = v.get("source", "")[:80]

    h2("架构族对齐（诚实比较的核心）")
    bullet("LDA 的 MZI mesh 与 MIT 学术 lineage（Shen/Harris 2017 → 2025 Nature 128×128 PTC）同族；"
           "Lightmatter 商用 Envise 采用「光广播 + 电子加权」口径（AIP AML 0.81 TOPS/W），为不同子架构。")
    bullet("文献 MZI-mesh 最大类 ≤800×800（AIP AML 2024）；LDA 已验证 N=256（32640 MZI）保真 0.9932，"
           "设计容量可借 scale-blind 性质延展到 800×800 类（理想 fab 假设）。")
    bullet("该 lineage 的公开瓶颈正是「MZI mesh 受限于制备误差」（AIP AML 2024）；"
           "LDA 的 scale-blind 保真 + 闭环 Vπ 标定 + tiling 局部标定正是对该瓶颈的工程解。")

    h1("五、先进性定位（诚实版）")
    para("本案例是设计工具链的能力证明，不是「又造了一颗更快的光子芯片」。把 256 / 800 读成「已制备光子芯片」即为失真。")
    t5 = doc.add_table(rows=1, cols=3); t5.style = "Light Grid Accent 1"
    for i, htext in enumerate(["维度", "产业界", "本案例"]):
        t5.rows[0].cells[i].text = htext
    for k, a, b in [("交付物", "已流片光子芯片+实测TOPS/W", "设计&验证工具链：MZI mesh 可设计+可验证保真闭环"),
                    ("工具链", "闭源 CAD/PDK + 控制 ASIC", "开源(MIT)·Agent-native·零外部光学 SDK"),
                    ("判决路径", "实验标定+数值仿真混合", "LLM 不进判决路径；死标量比对"),
                    ("能效数字", "实测/标称 TOPS/W", "不报任何 fabricated 能效数字"),
                    ("对标维度", "die 级 benchmark", "架构族+设计质量方法论")]:
        cells = t5.add_row().cells
        cells[0].text = k; cells[1].text = a; cells[2].text = b

    h1("六、诚实边界（逐条）")
    for g in [
        "非流片 / 非实测芯片：无 foundry 回片、无光学校准实测、无 TOPS/W 实测。",
        "不宣称任何 fabricated 能效数字：LDA 不报任何 pj/MAC、TOPS/W。",
        "比较按架构族 + 设计质量方法论，不按 die 级 benchmark 同台比。",
        "规模 = 设计容量：256 可设计验证，非已制备；延展 800×800 靠 scale-blind（理想 fab）。",
        "EO 链路为行为级（T1 候选，非 ORACLE）：不碰晶体管级 DAC/ADC/SerDes/DSP。",
        "零能效数字纪律：复用 assert_no_energy_metrics；Vπ 跨模块口径差（任务 #7）已规避。",
    ]:
        bullet(g)

    h1("七、平台能力增量（吃狗粮的意义）")
    for g in [
        "非酉光计算路径：SVD 双网格，突破「只能算酉矩阵」。",
        "光电协同仿真框架：第一次能设计「光核 + 电子接口」完整芯片。",
        "闭环标定（控制环）：第一次有「读回 → 补偿」的校准能力。",
        "规模可扩展性验证：scale-blind 不塌缩 + tiling 增益/损耗模型。",
        "对标纪律：A 级公开来源登记 landmark，把「达国际水平」落到可复核对标表。",
    ]:
        bullet(g)

    h1("八、引用与来源")
    para("产业界公开数字（A 级 golden）：Lightmatter（Nature 2025 / whychips 2026）；"
         "MIT（news.mit.edu 2017 / rle.mit.edu 2026）；清华 Taichi（Science 2024）；"
         "AIP AML 2024 性能对比表（pubs.aip.org）。")
    para("平台账本：CI core 236 条 · 验证锚 476（严格独立 455 / 降级 3 / 自证桩 18）· 独立率 95.59%。")
    para("本征程门禁：run_photonic_compute_m1..m5_smoke.py（M5 单文件 33 判据全绿）。")

    out = os.path.join(ROOT, "LDA_光计算芯片介绍.docx")
    doc.save(out)
    print("已生成 DOCX：%s" % out)


def main():
    d, ext, landmarks = _demo()
    ver = _platform_version()
    build_html(d, ext, landmarks, ver)
    build_pptx(d, ext, landmarks, ver)
    build_docx(d, ext, landmarks, ver)
    print("M5 三件套生成完毕。")


if __name__ == "__main__":
    main()
