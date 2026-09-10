# -*- coding: utf-8 -*-
import math

W, H = 1560, 1120
cx, cy = W // 2, H // 2

# 九层资源（中心 LDA 为设计入口，每层精选 P0/P1 节点）
dims = [
    ("地方集聚地", "#2563eb", ["武汉·中国光谷", "上海张江·硅光芯源", "重庆·CUMEC"]),
    ("龙头企业", "#dc2626", ["中际旭创 300308", "光迅科技 002281", "华工科技 000988"]),
    ("院校平台", "#16a34a", ["华科·光电国研", "上交 CHIPX", "中科院半导体所"]),
    ("学术带头人", "#9333ea", ["郑婉华(半导体所)", "金贤敏(上交)", "张新亮(华科)"]),
    ("产业带头人", "#ea580c", ["刘圣·中际旭创", "黄宣泽·光迅", "韩建忠/王涛·CUMEC"]),
    ("展会窗口", "#0891b2", ["CIOE深圳(9月)", "SiPC光谷(5月)", "OFC美国(3月)"]),
    ("产业专项政策", "#ca8a04", ["工信部稳增长(光子/CPO)", "上海硅光专项", "大基金三期"]),
    ("项目对口政策", "#db2777", ["首版次软件(2026.1截止)", "政府首购(财库13号)", "国发8号EDA税优"]),
    ("资本/协会/标准", "#64748b", ["中科创星(米磊)", "华为哈勃(白熠)", "NOEIC+CCSA TC6"]),
]

n = len(dims)
step = 2 * math.pi / n
start = -math.pi / 2

P = []
P.append(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">')
P.append(f'<rect width="{W}" height="{H}" fill="#0f172a"/>')

# 中心节点
P.append(f'<circle cx="{cx}" cy="{cy}" r="82" fill="#1e3a8a" stroke="#60a5fa" stroke-width="3"/>')
P.append(f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#ffffff" font-size="26" font-weight="bold">LDA</text>')
P.append(f'<text x="{cx}" y="{cy+18}" text-anchor="middle" fill="#bfdbfe" font-size="13">开源 EDA · 设计入口</text>')
P.append(f'<text x="{cx}" y="{cy+38}" text-anchor="middle" fill="#93c5fd" font-size="11">谁掌握设计入口谁就是链主</text>')

for i, (name, color, leaves) in enumerate(dims):
    ang = start + i * step
    R1 = 480
    tx = cx + R1 * math.cos(ang)
    ty = cy + R1 * math.sin(ang)
    # 主枝连线
    P.append(f'<line x1="{cx}" y1="{cy}" x2="{tx}" y2="{ty}" stroke="{color}" stroke-width="3" opacity="0.65"/>')
    # 主枝标题圈
    P.append(f'<circle cx="{tx}" cy="{ty}" r="52" fill="{color}" opacity="0.95"/>')
    P.append(f'<text x="{tx}" y="{ty+6}" text-anchor="middle" fill="#ffffff" font-size="15" font-weight="bold">{name}</text>')
    m = len(leaves)
    for j, leaf in enumerate(leaves):
        frac = (j + 1) / (m + 1)
        Rl = 155 + frac * (R1 - 185)
        off = (1 if j % 2 == 0 else -1) * 0.05
        la = ang + off
        lx = cx + Rl * math.cos(la)
        ly = cy + Rl * math.sin(la)
        P.append(f'<line x1="{tx}" y1="{ty}" x2="{lx}" y2="{ly}" stroke="{color}" stroke-width="1.3" opacity="0.5"/>')
        anchor = "end" if math.cos(la) < 0 else "start"
        dx = -13 if anchor == "end" else 13
        P.append(f'<g><title>{leaf}</title><circle cx="{lx}" cy="{ly}" r="7.5" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
                 f'<text x="{lx+dx}" y="{ly+4}" text-anchor="{anchor}" fill="#e2e8f0" font-size="13.5">{leaf}</text></g>')

P.append('</svg>')
svg = "\n".join(P)

html = f'''<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>光子产业设计联盟 · 资源图谱</title>
<style>
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif; }}
  svg text {{ font-family:'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:24px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .sub {{ font-size:13px; color:#94a3b8; margin-bottom:14px; }}
  details {{ margin-top:18px; background:#1e293b; padding:12px 16px; border-radius:8px; }}
  summary {{ cursor:pointer; font-weight:bold; color:#cbd5e1; }}
  table {{ border-collapse:collapse; width:100%; margin-top:10px; font-size:13px; }}
  th,td {{ border:1px solid #334155; padding:6px 9px; text-align:left; }}
  th {{ background:#334155; }}
  a {{ color:#60a5fa; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>光子产业设计联盟 · 资源图谱（九层 · 以 LDA 设计入口为中心）</h1>
  <div class="sub">深色背景便于投屏/投影。悬停任意节点查看名称。完整条目见各分册（见整合主册 design_alliance_resources_master.md）。</div>
  {svg}
  <details>
    <summary>九层资源 × 政策双维度叠加 说明</summary>
    <p>资源地图共九层：地方集聚地、龙头企业、院校平台、学术带头人、产业带头人、展会窗口、产业专项政策（光子下游）、项目对口政策（工业智能体/开源/工业软件/中小企业）、资本/协会/标准/投资人。</p>
    <p><b>政策双维度叠加</b>：LDA 同时命中「光子产业下游专项政策」(<a href="census_policies.md">census_policies.md</a>, 46项) 与「项目本体对口政策」(<a href="census_policies_project_fit.md">census_policies_project_fit.md</a>, 41项)，等于<b>五口并行</b>——工业智能体 + 开源 + 工业软件 + 中小企业 + 光电子产业。</p>
    <table>
      <tr><th>层</th><th>对应分册</th><th>规模</th></tr>
      <tr><td>地方集聚地</td><td>design_alliance_census.md</td><td>10 处 + 30+ 龙头</td></tr>
      <tr><td>院校平台</td><td>design_alliance_census_academia.md</td><td>7 区域 + 5 国家级平台</td></tr>
      <tr><td>学术带头人</td><td>census_academic_leaders.md</td><td>32 位（18 院士）</td></tr>
      <tr><td>产业带头人</td><td>census_industry_leaders.md</td><td>30 位 / 6 赛道</td></tr>
      <tr><td>展会窗口</td><td>census_exhibitions.md</td><td>14 个</td></tr>
      <tr><td>产业专项政策</td><td>census_policies.md</td><td>46 项</td></tr>
      <tr><td>项目对口政策</td><td>census_policies_project_fit.md</td><td>41 项</td></tr>
      <tr><td>资本/协会/标准</td><td>census_ecosystem_others.md</td><td>10+7+6</td></tr>
      <tr><td>资本/投资人</td><td>census_investors.md</td><td>34 机构 + 38 人</td></tr>
    </table>
  </details>
</div>
</body>
</html>'''

with open(r"D:/agent_LDA/design_alliance_resource_map.html", "w", encoding="utf-8") as f:
    f.write(html)
print("OK written design_alliance_resource_map.html")
