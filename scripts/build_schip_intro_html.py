"""一次性：生成对外宣传用单文件 HTML《LDA 超导量子计算芯片介绍》。

事实源 = LDA_超导量子计算芯片设计与成果总结_2026-09-30.md（本脚本为派生包装，
数字与之一致；改数字先改事实源）。
版图 SVG 直接内嵌（读自 examples/），暗色主题。
"""
from __future__ import annotations

import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根（本脚本在 scripts/ 下）
EX = ("examples", "lda/examples")


def svg(name: str) -> str:
    """读版图 SVG（跨目录找）并返回内联片段。"""
    for d in EX:
        p = os.path.join(ROOT, d, name)
        if os.path.isfile(p):
            s = io.open(p, encoding="utf-8").read().strip()
            # 白底 + 圆角保留（暗色页里当版图卡片）
            s = s.replace('width="680" height="680"', 'viewBox="0 0 680 680" width="100%"')
            s = s.replace('width="520" height="520"', 'viewBox="0 0 520 520" width="100%"')
            return s
    return ""


def figure(name: str, cap: str, note: str = "") -> str:
    s = svg(name)
    if not s:
        return ""
    n = f'<div class="fignote">{note}</div>' if note else ""
    return f'<figure class="fig">{s}<figcaption>{cap}{n}</figcaption></figure>'


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
h1 small{display:block;font-size:17px;font-weight:500;color:var(--mut);margin-top:10px;letter-spacing:0}
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
pre{background:#0a1120;border:1px solid var(--line);border-radius:12px;padding:18px 20px;
  overflow:auto;font-size:13.5px;line-height:1.7}
pre code{background:none;border:0;padding:0}
.fig{margin:22px 0;background:#fff;border-radius:14px;padding:14px;border:1px solid var(--line)}
.fig svg{display:block;border-radius:8px}
.fig figcaption{color:#334155;font-size:13.5px;margin-top:10px;font-weight:600}
.fignote{color:#64748b;font-weight:400;margin-top:3px}
.two{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.callout{border-radius:12px;padding:16px 20px;margin:18px 0;border:1px solid}
.callout.warn{border-color:rgba(251,191,36,.45);background:rgba(251,191,36,.08)}
.callout.ok{border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.07)}
.callout.acc{border-color:rgba(79,140,255,.45);background:rgba(79,140,255,.08)}
.callout b{color:#fff}
ol,ul{padding-left:24px}
li{margin:7px 0}
.crumb{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0 6px}
.crumb i{color:var(--mut);font-style:normal}
.pill{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:6px 12px;font-size:14px;color:#d8e3f7}
.pill.hot{border-color:var(--acc);color:#fff;background:rgba(79,140,255,.16);font-weight:700}
.foot{margin-top:64px;padding-top:22px;border-top:1px solid var(--line);color:var(--mut);font-size:13.5px}
a{color:var(--acc2)}
.diff .lda{color:#d9f7e9}
"""

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LDA 超导量子计算芯片 · 设计与成果介绍</title>
<style>%s</style>
</head>
<body>
<div class="wrap">
"""

HERO = """
<header class="hero">
  <div class="kicker">LDA · 开源 Agent-native EDA（MIT）· 量子芯片征程</div>
  <h1>超导量子计算芯片 LDA-S
    <small>transmon 微波 QEDA · 从单比特单元到 1024 比特阵列版图 · P&amp;R 与全链路签核闭环</small>
  </h1>
  <div style="margin-top:18px">
    <span class="badge ok">真 GDSII 已出</span>
    <span class="badge ok">200 条门禁判据全绿</span>
    <span class="badge acc">零量子 SDK</span>
    <span class="badge">判决路径无 LLM</span>
    <span class="badge">设计期签核 · 非流片实测</span>
  </div>
  <p class="lead" style="margin-top:22px">
    <b>用 LDA 从零设计一颗超导 transmon 量子计算芯片：从单比特单元到 1024 比特阵列版图（32×32，10244 个版图元素），
    走完 <code>P&amp;R → 布线路由 → 几何 DRC/LVS → 频率避撞 → 串扰/损耗预算</code>全链路签核，并出真 GDSII。</b>
  </p>
  <p class="mut">这不是一次器件仿真，而是一次「平台能不能真的画出一颗芯片」的体检——用 LDA 亲手设计，吃自己的狗粮。</p>
</header>
"""

METRICS = """
<div class="grid">
  <div class="card"><div class="k">旗舰规模（版图容量）</div><div class="v">1024<span>qubit</span></div>
    <div class="mut" style="font-size:13px">32×32 · 10244 版图元素</div></div>
  <div class="card"><div class="k">门禁判据（五段征程）</div><div class="v">200<span>条</span></div>
    <div class="mut" style="font-size:13px">S1 21 · S2 24 · S3 28 · S4 31 · S5 96</div></div>
  <div class="card"><div class="k">f01 双验证一致性</div><div class="v">0.42<span>%</span></div>
    <div class="mut" style="font-size:13px">严格对角化 ↔ Koch 闭式</div></div>
  <div class="card"><div class="k">可调耦合器可关比</div><div class="v">54.3<span>×</span></div>
    <div class="mut" style="font-size:13px">J_on 0.400 MHz / J_off 0.0074 MHz</div></div>
  <div class="card"><div class="k">最坏杂散 ZZ</div><div class="v">0.39<span>MHz</span></div>
    <div class="mut" style="font-size:13px">上限 1.0 MHz · N=1024</div></div>
  <div class="card"><div class="k">最小 T1（N≤1024）</div><div class="v">41.2<span>µs</span></div>
    <div class="mut" style="font-size:13px">目标 20 µs · 良率 100%</div></div>
  <div class="card"><div class="k">heavy-hex 最大度</div><div class="v">3<span>度</span></div>
    <div class="mut" style="font-size:13px">91 qubit · 对标 IBM · 无 4 邻居</div></div>
  <div class="card"><div class="k">真产出物</div><div class="v">29<span>件</span></div>
    <div class="mut" style="font-size:13px">8 组配置的 .gds / .svg / report</div></div>
</div>
"""

SEC_WHAT = """
<h2><span class="no">01</span>这颗芯片是什么</h2>
<table>
<tr><th>维度</th><th>内容</th></tr>
<tr><td><b>物理载体</b></td><td>超导 transmon（固定频率 + 可调频率）· 微波量子电动力学（circuit QED）</td></tr>
<tr><td><b>比特单元</b></td><td>十字形岛 + Josephson 结（JJ）+ 孪生读出焊盘</td></tr>
<tr><td><b>耦合</b></td><td>静态耦合器 + <b>flux 可调耦合器</b>（SQUID 环，含结不对称）</td></tr>
<tr><td><b>读出</b></td><td>λ/4 谐振腔 + 馈线，支持 <b>FDM 频分复用</b>（每行一条馈线挂多只腔）</td></tr>
<tr><td><b>控制</b></td><td><b>三线分离</b>：XY 驱动 · Z 磁通 · coupler-flux</td></tr>
<tr><td><b>拓扑</b></td><td>两种：<b>方阵</b>（4 邻居）与 <b>heavy-hex</b>（最大度 3，对标 IBM）</td></tr>
<tr><td><b>版图层</b></td><td>FILM = 10 · JJ = 11 · GROUND = 12（平台自写 GDSII 编码器，零外部依赖）</td></tr>
<tr><td><b>外部依赖</b></td><td><b>零量子 SDK</b>（不依赖 Qiskit / Cirq / PennyLane）；物理内核平台自研</td></tr>
</table>
"""

SEC_ROAD = """
<h2><span class="no">02</span>五段征程（S1 → S5）</h2>
<table>
<tr><th>段</th><th>编号</th><th>标题</th><th>门禁</th><th>关键结果</th></tr>
<tr><td><b>S1</b></td><td>D-133</td><td>单 transmon 单元 · 全闭环</td><td>21</td>
<td>真 GDS（596 B）+ 几何 DRC 4 规则 + LVS 5 判据；f01 严格对角化 <b>4.887 GHz</b> ↔ Koch 闭式 rel <b>0.42%</b>；α = −0.356 GHz</td></tr>
<tr><td><b>S2</b></td><td>D-134</td><td>耦合 transmon 对 · 全闭环</td><td>24</td>
<td>耦合对版图 + 复用 S1 签核 + 多网连通 LVS 6 判据；<b>J 双验证 rel ≤ 5%</b>；g_CR = 2.59 MHz · t_CR = 1.21 µs · σ_zz = 0.21 MHz</td></tr>
<tr><td><b>S3</b></td><td>D-135</td><td>N 比特阵列 P&amp;R · 全闭环</td><td>28</td>
<td>网格 P&amp;R + 最近邻耦合（行内 + 行间）；专用规模 DRC 5 规则 + LVS 6 判据；逐边 J 双验证 max rel <b>4.37%</b></td></tr>
<tr><td><b>S4</b></td><td>D-136</td><td>读出/控制线路 + 串扰/损耗预算</td><td>31</td>
<td>DRC <b>10 规则</b> + LVS <b>9 判据</b>；全 pair 杂散 ZZ ≤ <b>1.0 MHz</b>；per-qubit T1（内部 + Purcell）≥ 20 µs</td></tr>
<tr><td><b>S5</b></td><td>D-137…D-145</td><td>规模压力 + 真实架构要素 + 统一拓扑框架</td><td><b>96</b></td>
<td>大 N 布线路由 · 频率避撞分配 · 规模压力 53/127/433/<b>1024</b> · 可调耦合器 · 读出 FDM · 控制多线 · 阵列+封装损耗 · heavy-hex · 批量签核 · 统一拓扑框架</td></tr>
</table>

<h3>S5 展开（四个波次 + 完善）</h3>
<table>
<tr><th>项</th><th>编号</th><th>模块</th><th>结果</th></tr>
<tr><td><b>G1</b> 大 N P&amp;R + 布线路由沟道</td><td>D-137</td><td><code>sc_routing.py</code></td>
<td>确定性「梳状」Manhattan 单层路由；路由 DRC 四则 + S4 十则 = <b>14 条</b>；段感知 LVS <b>11 判据</b>；规模自洽 pitch 重算</td></tr>
<tr><td><b>G6</b> 频率避撞分配器</td><td>D-142</td><td><code>sc_freq_alloc.py</code></td>
<td>阶梯贪心 / 二维模着色；约束含<b>避 ZZ 极点</b> <code>‖Δ‖≈|α|</code>；向量化闭式 ↔ S4 逐对 ZZ 交叉复核 rel 12.7%；N=1024 用 <b>0.17 s</b></td></tr>
<tr><td><b>G7</b> 规模压力门禁</td><td>D-143</td><td><code>run_schip_s5_smoke.py</code></td>
<td>四档 <b>53 / 127 / 433 / 1024</b> 路由 + 频率 + 损耗全 ACCEPT</td></tr>
<tr><td><b>G3</b> 可调耦合器</td><td>D-139</td><td><code>sc_coupler.py</code> 扩</td>
<td>SQUID <b>精确闭式</b>（含结不对称）· J_on 0.400 MHz · J_off 0.0074 MHz · <b>可关比 54.3</b> · 双验证 rel 4.60%</td></tr>
<tr><td><b>G4</b> 读出频分复用</td><td>D-140</td><td><code>sc_readout_mux.py</code></td>
<td>每馈线多音互异；λ/4 闭式绑几何↔频率；腔高按音高编码；2×2→32×32 全 ACCEPT</td></tr>
<tr><td><b>G5</b> 控制多线</td><td>D-141</td><td><code>sc_control.py</code></td>
<td>XY/Z/coupler-flux 三线分离；逐线 fringe 串扰闭式；XY↔Z 隔离 ≤ 1e−3</td></tr>
<tr><td><b>G8</b> 阵列 + 封装损耗</td><td>D-144</td><td><code>sc_readout.py</code> 扩</td>
<td>封装参与比 + <b>封装腔模规避</b> + 阵列良率；N=4…1024 <b>yield = 1.0</b> · min T1 41.2 µs</td></tr>
<tr><td><b>G2</b> heavy-hex 拓扑</td><td>D-138</td><td><code>sc_topology.py</code></td>
<td>蜂窝两子格 + 边中点 ⇒ <b>最大度恒 3</b>（无 4 邻居）；91 qubit · 102 耦合</td></tr>
<tr><td><b>G9</b> 批量签核</td><td>—</td><td><code>examples/lda_schip_s5.py</code></td>
<td>单元 + 方阵族 + heavy-hex 族 <b>8 配置全闭环</b>，产出 GDS/SVG + report.json</td></tr>
<tr><td><b>统一拓扑框架</b></td><td>D-145</td><td><code>sc_topology_core.py</code></td>
<td>拓扑抽为<b>数据</b>（含<b>度上限自声明</b>）⇒ 方阵与 heavy-hex <b>共用同一份 DRC/LVS 引擎</b></td></tr>
</table>
"""

SEC_RESULTS = """
<h2><span class="no">03</span>四大技术结果（可复核）</h2>

<h3>3.1 物理内核方法学独立（不是自证）</h3>
<table>
<tr><th>物理量</th><th>路径 A（闭式 / 解析）</th><th>路径 B（数值 / 严格对角化）</th><th>一致性</th></tr>
<tr><td>f01（比特频率）</td><td>Koch 闭式 √(8E_J E_C) − E_C</td><td><code>coupler_solver</code> 严格对角化</td><td><b>rel 0.42%</b></td></tr>
<tr><td>耦合强度 J</td><td>解析闭式 J_c</td><td>严格对角化（441 维）</td><td><b>rel ≤ 5%</b></td></tr>
<tr><td>可调耦合器 E_J(Φ)</td><td>SQUID <b>精确闭式</b>（含结不对称）</td><td>数值提取（近共振有效区）</td><td><b>rel 4.60%</b></td></tr>
</table>
<div class="callout acc">
<b>判决全部为死标量比对，LLM 不进判决路径</b>；物理定律（能量守恒、幺正性、λ/4 关系）作<b>红线锚</b>。
</div>

<h3>3.2 规模自洽：版图比例随 N 自动重算</h3>
<p>大 N 时最容易出现的断层是「控制线误桥邻居」——9 比特能排、1024 比特排不动。根因是行 pitch 没跟着走：</p>
<pre><code>pitch_y_eff = max(pitch_y_user,
                  (cols−1)·routing_pitch + drop + feed_zone + clearance)</code></pre>
<p>实测旗舰档 <code>pitch_y_eff = 141.0 µm</code>，控制信号线 <b>1056</b> 条，版图元素 <b>10244</b> 个，DRC + LVS 全 ACCEPT。</p>

<h3>3.3 频率避撞：显式规避 ZZ 极点</h3>
<ul>
<li>近邻 / 相邻对 |Δ| ≥ <b>10 MHz</b></li>
<li>最近邻 |Δ| ≥ <b>40 MHz</b></li>
<li><b>|‖Δ‖ − |α|| ≥ 30 MHz</b>（避开 ZZ 相互作用极点 Δ = −α）</li>
</ul>
<p>再用<b>向量化闭式</b>与 S4 的逐对 ZZ 计算交叉复核（rel 12.7%，容差 20%）⇒ 大 N 可算：
N=1024 规划只用 <b>0.17 s</b>，最坏杂散 ZZ <b>0.39 MHz ≤ 1.0 MHz</b> 上限。</p>

<h3>3.4 拓扑可切换：一份签核引擎服务两种架构</h3>
<table>
<tr><th>拓扑</th><th>度上限</th><th>3×3 规模</th><th>备注</th></tr>
<tr><td>方阵（grid）</td><td><b>4</b></td><td>9 qubit / 12 耦合</td><td>与 S3 同拓扑，耦合数 = r(c−1) + c(r−1)</td></tr>
<tr><td>heavy-hex</td><td><b>3</b></td><td>39 qubit / 42 耦合</td><td>对标 IBM，<b>无 4 邻居</b>（定义式）</td></tr>
</table>
<p>引擎按<b>拓扑自报的度上限</b>判 ⇒ 若写死「≤3」，方阵会被误判 REJECT。同一份
<code>run_topology_drc</code> / <code>topology_lvs</code> / <code>topology_physics</code> 服务两者。</p>
"""

SEC_FIGS_HEAD = """
<h2><span class="no">04</span>真实版图（平台直出）</h2>
<p class="mut">以下全部为 LDA 自写 GDSII 编码器输出的 SVG 预览（同一份 GDS 的几何），非示意图。
深蓝 = 超导膜（层 10）· 红 = Josephson 结（层 11）· 灰 = 地（层 12）。</p>
"""

SEC_CAP = """
<h2><span class="no">05</span>平台能力增量（吃狗粮的意义）</h2>
<ol>
<li><b>微波域器件原语</b>：从 0 到 transmon 单元 / 耦合器 / 读出腔 / 控制线（10 个 <code>sc_*</code> 模块，5633 行）。</li>
<li><b>规模自洽的 P&amp;R</b>：布线路由沟道与 pitch 联动——这是「设计能不能扩」的分水岭。</li>
<li><b>两类新 DRC 语义</b>：几何规则（线宽 / 间隙 / JJ 尺寸）+ <b>架构规则</b>（最大度、节点间距、音唯一性）。</li>
<li><b>频率域签核</b>：平台第一次把「频谱规划」作为<b>一道可签核的工序</b>（避撞 + 保护带 + 杂散上限）。</li>
<li><b>拓扑抽象</b>：把「器件怎么连」从代码抽成数据，两种架构共用一份引擎。</li>
</ol>
"""

SEC_ADV = """
<h2><span class="no">06</span>先进性定位（诚实版）</h2>
<div class="callout warn">
⚠️ 下表产业界数字为 2026 年<b>公开报道的「已交付芯片」</b>，仅作背景坐标。
<b>本案例是设计期签核，两者不同台比较。</b>
</div>
<h3>公开坐标</h3>
<table>
<tr><th>主体</th><th>公开进展</th></tr>
<tr><td><b>IBM</b></td><td>Heron r2/r3 <b>156 qubit</b>（固定频率 transmon + 可调耦合器）；Condor <b>1,121 qubit</b>（2023，缩放里程碑）；<b>Nighthawk 120 qubit 方格 4-度连通</b>；2026 Kookaburra 路线（qLDPC 量子存储 + 逻辑处理单元，目标 ≤360 qubit / 7,500 门）；Starling（2028–29）目标 200 逻辑比特 / 10,000 物理比特</td></tr>
<tr><td><b>Google</b></td><td>Willow <b>105 qubit</b>；2024-12 首次 <b>below-threshold</b> 纠错（3×3→5×5→7×7 surface code 指数抑制）</td></tr>
<tr><td><b>中国</b></td><td>祖冲之 3.2 <b>107 qubit</b>（全微波控制，低于阈值纠错）；祖冲之 3.0 105 qubit / 182 耦合器</td></tr>
<tr><td><b>Fujitsu + RIKEN</b></td><td><b>256 qubit</b> 超导（2025-04），目标 1,000 qubit</td></tr>
<tr><td><b>Rigetti / IQM</b></td><td>Ankaa-3 84 qubit · Cepheus-1 108 qubit；Radiance 150 qubit（二比特门保真 99.91%）</td></tr>
</table>
<h3>本案例的差异点（不做数值同台比较）</h3>
<table class="diff">
<tr><th>维度</th><th>产业界</th><th>本案例</th></tr>
<tr><td><b>交付物</b></td><td>已制备芯片 + 云访问</td><td class="lda"><b>设计期签核</b>：真 GDSII + DRC/LVS + 预算，可复现、可审计</td></tr>
<tr><td><b>工具链</b></td><td>各自闭源 CAD/PDK + Qiskit 等 SDK</td><td class="lda"><b>开源（MIT）· Agent-native · 零量子 SDK</b>，物理内核自研</td></tr>
<tr><td><b>判决路径</b></td><td>实验标定 + 数值仿真混合</td><td class="lda"><b>LLM 不进判决路径</b>；判决为死标量比对；红线为物理定律</td></tr>
<tr><td><b>拓扑</b></td><td>heavy-hex（Heron）→ Nighthawk 改方格 4-度</td><td class="lda"><b>两种拓扑共用一份 DRC/LVS 引擎</b>（度上限自声明）</td></tr>
<tr><td><b>规模口径</b></td><td>已交付比特数（156 / 105 / 107）</td><td class="lda"><b>版图容量</b>（1024 可排布且可签核）——口径不同</td></tr>
</table>
<div class="callout ok">
<b>我们的自我评价（不夸张）</b><br/>
✅ 做对了：把「量子芯片设计」完整走通到版图与签核，且<b>规模可扩、规则可切拓扑、物理可双验证</b>。<br/>
⚠️ 不在同一赛道比大小：我们做的是<b>设计工具链的能力证明</b>，不是「又造了一颗更快的量子芯片」。
把 1024 读成「已制备 1024 比特」即为失真。
</div>
"""

SEC_UI = """
<h2><span class="no">07</span>在 LDA UI 里能找到吗？</h2>
<div class="callout ok">
<b>能——已接线。</b>（此前 UI 只有器件仿真面板 + 光量子案例卡；本轮补齐超导芯片级案例卡。）
</div>
<div class="crumb">
  <span class="pill">lda.weomnitech.com.cn</span><i>›</i>
  <span class="pill">免登录</span><i>›</i>
  <span class="pill">验证实力（accept 阶段）</span><i>›</i>
  <span class="pill hot">★ 超导量子计算芯片案例（transmon · 微波 QEDA）</span><i>→</i>
  <span class="pill">点「运行超导芯片案例」</span>
</div>
<table>
<tr><th>项</th><th>位置</th></tr>
<tr><td><b>页面</b></td><td><code>https://lda.weomnitech.com.cn/</code>（免登录）</td></tr>
<tr><td><b>分区</b></td><td><b>「验证实力」（accept 阶段）</b>区</td></tr>
<tr><td><b>卡片</b></td><td><b>★ 超导量子计算芯片案例（transmon · 微波 QEDA）</b></td></tr>
<tr><td><b>操作</b></td><td>点「<b>运行超导芯片案例</b>」按钮 → 现场拉取只读案例</td></tr>
<tr><td><b>端点</b></td><td><code>GET /api/schip_demo</code>（公开只读 · 免登录 · 零重计算 · 微秒级）</td></tr>
<tr><td><b>同行卡片</b></td><td>紧邻「★ 光量子计算芯片案例（LOQC 通用处理器）」（<code>/api/qchip_demo</code>）</td></tr>
</table>
<p>卡片呈现：五段征程表 · 旗舰规模表 · 关键物理双验证表 · 规模档表 · 关键结论 · 先进性定位 · 诚实限制 · 未闭合项 · 产出物清单。</p>
<h3>另有一组互补的量子面板（此前就在）</h3>
<ul>
<li>㊿ QEDA 求解器级补强 · transmon-resonator 色散读出（三能级严格求解）</li>
<li>51 QEDA 纵深三件套（多能级展开 · 驱动场 Rabi/AC Stark · 读出串扰 ZZ 耦合）</li>
</ul>
<p class="mut">口径说明：这些面板覆盖<b>器件物理仿真</b>；本案例卡覆盖<b>芯片级 P&amp;R 与签核</b>，二者互补。</p>
"""

SEC_CASE = """
<h2><span class="no">08</span>可以作为平台设计案例吗？</h2>
<p class="lead">可以，且已经从「可以」变成「是」。</p>
<table>
<tr><th>判据</th><th>状态</th></tr>
<tr><td>有独立可访问入口</td><td>✅ <code>/api/schip_demo</code> + UI 卡片</td></tr>
<tr><td>有真产出物（可查）</td><td>✅ <b>29 个文件</b>：8 组配置的 <code>.gds</code> + <code>.svg</code> + <code>report.json</code></td></tr>
<tr><td>有机器可判的门禁</td><td>✅ 5 段 <b>200 判据</b> + 18 组突变探针</td></tr>
<tr><td>有可复现脚本</td><td>✅ <code>examples/lda_schip_s5.py</code> 一键批量签核</td></tr>
<tr><td>有诚实边界</td><td>✅ 返回体自带 <code>honest_note</code>（六条），verdict 明标 <code>DESIGN_SIGNOFF</code></td></tr>
<tr><td>与其他案例并列不冲突</td><td>✅ 与光量子案例卡同构（不同物理、同一平台问题）</td></tr>
</table>
<div class="callout acc">
<b>它作为案例的独特价值</b>：证明「<b>同一条设计链路，换一种物理（微波/超导），是否还站得住？</b>」——
答案是站得住，而且规模从 1 比特扩到 1024 比特。
</div>
"""

SEC_HONEST = """
<h2><span class="no">09</span>诚实边界（逐条）</h2>
<div class="callout warn">
<ol>
<li><b>非流片后实测</b>：全部为设计期签核；<b>无低温实测 T1/T2、无实测保真度、无 foundry 回片</b>。</li>
<li><b>非 foundry PDK</b>：DRC 限值为自建设计规则，<b>未对接任何工艺厂 deck</b>（属外部依赖）。</li>
<li><b>物理量分两类</b>：<b>方法学可复核</b>（Koch f01、耦合 J、SQUID E_J(Φ)、色散 χ——闭式 ↔ 严格对角化双验证）；
<b>设计预算口径</b>（损耗/串扰：参与比、Purcell、ZZ 杂散——参数为设计输入，非实测）。</li>
<li><b>规模 = 版图容量</b>：1024 是「可排布且可签核的比特数」，<b>不等于已制备器件数</b>；与 IBM/Google 的「已交付芯片」<b>不同台比较</b>。</li>
<li><b>不含纠错码层</b>：surface code / qLDPC 逻辑比特、解码器、阈值分析<b>不在范围</b>（属版本级 pre-QEC 物理层设计能力）。</li>
<li><b>不含量子线路级能力</b>：不做脉冲级 Rabi/Ramsey 标定流程、不做线路编译与噪声仿真、不做门保真实测。</li>
<li><b>封装/低温布线未落地</b>：封装只做到「腔模规避 + 参与比预算」；倒装焊、TSV、低温衰减链未实现。</li>
<li><b><code>J_eff = J_qc²/Δ_c</code> 的适用区</b>：二阶虚交换要求耦合器频率<b>全程低于</b> qubit，否则在穿越点发散（已在工作区设计中规避）。</li>
</ol>
</div>
"""

SEC_REPRO = """
<h2><span class="no">10</span>复现命令</h2>
<pre><code>cd D:/agent_LDA/lda
export PYTHONPATH=D:/agent_LDA/lda

# 单段门禁（200 判据）
python run_schip_s1_smoke.py     # 21
python run_schip_s2_smoke.py     # 24
python run_schip_s3_smoke.py     # 28
python run_schip_s4_smoke.py     # 31
python run_schip_s5_smoke.py     # 96（S5 全波次）

# 批量签核 + 产出 GDS/SVG/report
python examples/lda_schip_s5.py
S5_TIERS="2x2,7x8,13x13,21x21" S5_HEX_TIERS="3x3,4x5" python examples/lda_schip_s5.py

# 案例卡自检（UI 数据源）
python -c "from lda_webui import schip_case as S; print(S.run_selfchecks(verbose=True))"</code></pre>
"""

FOOT = """
<div class="foot">
  <p><b>LDA</b>（开源 Agent-native EDA · MIT）· 超导量子计算芯片 LDA-S · 版本 0.9.144 · 2026-09-30</p>
  <p>平台账本：CI core 226 条回归成员 · 验证锚 <b>476</b>（严格独立 455 / 降级 3 / 自证桩 18）· 独立率 95.59%</p>
  <p>本征程门禁：<code>run_schip_s1..s5_smoke.py</code> 共 <b>200</b> 判据 · 突变探针 <code>scripts/d_sc_s5_probe.py</code> 18 组</p>
  <p class="mut">本页为《LDA_超导量子计算芯片设计与成果总结_2026-09-30.md》的派生包装；数字以事实源为准。</p>
</div>
"""


def main() -> None:
    figs = (
        SEC_FIGS_HEAD
        + '<div class="two">'
        + figure("lda_schip_s5_tunable.svg", "① 可调耦合器单元（SQUID 环 + flux 偏置线）",
                 "G3 · D-139 · 2 JJ + 2 lead + 左右 bar；E_J(Φ) 精确闭式，可关比 54.3")
        + figure("lda_schip_s5_2x2.svg", "② 方阵 2×2（4 比特 · 读出 + 控制 + 布线焊盘）",
                 "G1/G4/G5 · D-137/D-140/D-141 · 控制线 L 形梳状路由")
        + figure("lda_schip_s5_hh3x3.svg", "③ heavy-hex 3×3（39 比特 · 最大度 3 · 对标 IBM）",
                 "G2 · D-138 · 蜂窝两子格 + 每边中点比特 ⇒ 无 4 邻居")
        + figure("lda_schip_s5_tfg3x3.svg", "④ 统一拓扑框架 · 方阵实例（与 heavy-hex 共用一份 DRC/LVS）",
                 "D-145 · 度上限由拓扑自声明（方阵 4 / hex 3）")
        + figure("lda_schip_s5_7x8.svg", "⑤ 方阵 7×8（56 比特 · 规模档）",
                 "G7 · 规模压力档之一；行 pitch 自洽重算，控制线不误桥邻居")
        + "</div>"
    )
    html = (
        HTML_HEAD % CSS
        + HERO + METRICS
        + SEC_WHAT + SEC_ROAD + SEC_RESULTS
        + figs
        + SEC_CAP + SEC_ADV + SEC_UI + SEC_CASE + SEC_HONEST + SEC_REPRO
        + FOOT
        + "</div></body></html>\n"
    )
    out = os.path.join(ROOT, "LDA_超导量子计算芯片介绍.html")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("已生成 %s（%.1f KB）" % (out, len(html.encode("utf-8")) / 1024.0))


if __name__ == "__main__":
    main()
