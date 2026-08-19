const pptxgen = require("C:/Users/Administrator/node_modules/pptxgenjs");
const React = require("C:/Users/Administrator/node_modules/react");
const ReactDOMServer = require("C:/Users/Administrator/node_modules/react-dom/server");
const sharp = require("C:/Users/Administrator/node_modules/sharp");
const FA = require("C:/Users/Administrator/node_modules/react-icons/fa");

// ---------- palette (Midnight Executive) ----------
const NAVY = "13203A";      // dominant dark
const NAVY2 = "1B2C4F";     // panel
const ICE = "CADCFC";       // light support
const BLUE = "2E75B6";      // accent
const CYAN = "22B8CF";      // bright accent
const WHITE = "FFFFFF";
const GREY = "9FB0C9";      // muted on dark
const LIGHTBG = "F4F7FB";   // light slides
const INK = "1A2230";       // dark text on light

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "LDA 领域研究室";
pres.title = "LDA 产业共建路演";
const PW = 13.3, PH = 7.5;

// ---------- icon helper ----------
async function icon(Comp, color, size=256){
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

// ---------- shared helpers ----------
function darkBg(slide){ slide.background = { color: NAVY }; }
function lightBg(slide){ slide.background = { color: LIGHTBG }; }

function kicker(slide, text, color=BLUE){
  slide.addShape(pres.shapes.RECTANGLE, { x:0.7, y:0.62, w:0.18, h:0.42, fill:{color}, line:{type:"none"} });
  slide.addText(text, { x:0.98, y:0.6, w:9, h:0.46, fontFace:"Calibri", fontSize:14, bold:true, color, charSpacing:2, align:"left", valign:"middle", margin:0 });
}
function titleDark(slide, text, y=1.25){
  slide.addText(text, { x:0.7, y, w:11.9, h:1.1, fontFace:"Georgia", fontSize:34, bold:true, color:WHITE, align:"left", valign:"top", margin:0 });
}
function titleLight(slide, text, y=1.25){
  slide.addText(text, { x:0.7, y, w:11.9, h:1.1, fontFace:"Georgia", fontSize:34, bold:true, color:NAVY, align:"left", valign:"top", margin:0 });
}

function footer(slide, n, dark=true){
  const c = dark ? GREY : "8A99AD";
  slide.addText("LDA · 开源 / 自主可控 / Agent 原生 光·量子芯片设计底座", { x:0.7, y:PH-0.5, w:9, h:0.3, fontFace:"Calibri", fontSize:10, color:c, align:"left", margin:0 });
  slide.addText(String(n), { x:PW-1.1, y:PH-0.5, w:0.6, h:0.3, fontFace:"Calibri", fontSize:10, color:c, align:"right", margin:0 });
}

function card(slide, x,y,w,h, fill, line){
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x,y,w,h, rectRadius:0.08, fill:{color:fill}, line: line?{color:line,width:1}:{type:"none"}, shadow:{type:"outer",color:"000000",blur:8,offset:3,angle:135,opacity:0.18} });
}

async function build(){
  const I = {
    chip: await icon(FA.FaMicrochip, "#"+WHITE),
    bolt: await icon(FA.FaBolt, "#"+WHITE),
    boltC: await icon(FA.FaBolt, "#"+BLUE),
    check: await icon(FA.FaCheckCircle, "#"+CYAN),
    checkC: await icon(FA.FaCheckCircle, "#"+BLUE),
    chartC: await icon(FA.FaChartLine, "#"+BLUE),
    shieldC: await icon(FA.FaShieldAlt, "#"+BLUE),
    shield: await icon(FA.FaShieldAlt, "#"+WHITE),
    layer: await icon(FA.FaLayerGroup, "#"+WHITE),
    users: await icon(FA.FaUsers, "#"+WHITE),
    server: await icon(FA.FaServer, "#"+WHITE),
    flask: await icon(FA.FaFlask, "#"+WHITE),
    handshake: await icon(FA.FaHandshake, "#"+WHITE),
    rocket: await icon(FA.FaRocket, "#"+WHITE),
    chart: await icon(FA.FaChartLine, "#"+WHITE),
    bullseye: await icon(FA.FaBullseye, "#"+WHITE),
    graduation: await icon(FA.FaGraduationCap, "#"+WHITE),
    industry: await icon(FA.FaIndustry, "#"+WHITE),
    arrow: await icon(FA.FaArrowRight, "#"+BLUE),
    quote: await icon(FA.FaQuoteLeft, "#"+BLUE),
  };

  // ============ SLIDE 1 — TITLE ============
  let s = pres.addSlide(); darkBg(s);
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:PW, h:0.12, fill:{color:BLUE}, line:{type:"none"} });
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:PH-0.12, w:PW, h:0.12, fill:{color:CYAN}, line:{type:"none"} });
  // motif: chip icon in ring
  s.addShape(pres.shapes.OVAL, { x:10.4, y:1.0, w:2.0, h:2.0, fill:{color:NAVY2}, line:{color:BLUE,width:1.5} });
  s.addImage({ data:I.chip, x:11.0, y:1.6, w:0.8, h:0.8 });
  s.addText("LDA 产业共建路演", { x:0.9, y:2.1, w:11, h:1.0, fontFace:"Georgia", fontSize:46, bold:true, color:WHITE, align:"left", margin:0 });
  s.addText("开源 · 自主可控 · Agent 原生的光芯片与量子芯片设计底座", { x:0.92, y:3.2, w:11, h:0.6, fontFace:"Calibri", fontSize:22, color:ICE, align:"left", margin:0 });
  s.addText([
    { text:"用 AI 智能体直接编写、并验证底层求解内核 —— 已经被跑通，不是设想。", options:{ italic:true, color:WHITE, fontSize:16, breakLine:true } },
  ], { x:0.92, y:4.1, w:10.5, h:0.6, align:"left", margin:0 });
  s.addText("面向产业界 · 学界 · 投资界   |   工业5点0产业生态联盟 · 杜玉河   |   2026-08", { x:0.92, y:5.9, w:11.5, h:0.4, fontFace:"Calibri", fontSize:13, color:GREY, align:"left", margin:0 });

  // ============ SLIDE 2 — 为什么是现在 (problem) ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "为什么是现在");
  titleDark(s, "产业在爆发，工具在断供", 1.25);
  const prob = [
    { ic:I.industry, t:"光子产业被 AI 拉动高速增长", d:"800G/1.6T 光互联推动硅光器件 2025 增速 37%+；光子 EDA 软件约 13 亿美元、CAGR ~12%" },
    { ic:I.shield, t:"美系 EDA 对华断供风险持续", d:"Synopsys 完成收购 Ansys，光子仿真旗舰 Lumerical 归入其体系，垄断在加深" },
    { ic:I.bolt, t:"量子芯片进入国产窗口期", d:"国产与海外在 QEDA 上无明显代差，自主可控战略意义极强" },
  ];
  let x=0.7; const cw=3.85, gap=0.35;
  for(const p of prob){
    card(s, x, 2.4, cw, 3.4, NAVY2);
    s.addShape(pres.shapes.OVAL, { x:x+0.35, y:2.75, w:0.85, h:0.85, fill:{color:BLUE}, line:{type:"none"} });
    s.addImage({ data:p.ic, x:x+0.55, y:2.95, w:0.45, h:0.45 });
    s.addText(p.t, { x:x+0.3, y:3.8, w:cw-0.6, h:0.7, fontFace:"Georgia", fontSize:18, bold:true, color:WHITE, align:"left", valign:"top", margin:0 });
    s.addText(p.d, { x:x+0.3, y:4.5, w:cw-0.6, h:1.2, fontFace:"Calibri", fontSize:13.5, color:ICE, align:"left", valign:"top", margin:0 });
    x += cw+gap;
  }
  s.addText("结论：被“卡”的设计工具 + 高增长的需求 = 一个必须被填补的真空。", { x:0.7, y:6.1, w:11.9, h:0.5, fontFace:"Calibri", fontSize:15, italic:true, bold:true, color:CYAN, align:"left", margin:0 });
  footer(s,2);

  // ============ SLIDE 3 — 巨头盲区 ============
  s = pres.addSlide(); lightBg(s);
  kicker(s, "结构性机会", BLUE);
  titleLight(s, "巨头不会做的，才是我们的生态位", 1.25);
  s.addText("巨头（Synopsys / Cadence）的收入根基是可信商业求解器的授权费。一旦由 AI 长出“开放、可验证、免费”的内核，等于击穿自己的收费地基 —— 所以它们只会把 AI 做成商业工具里的“辅助层”，永远不会做开放内核。", { x:0.7, y:2.25, w:11.9, h:1.1, fontFace:"Calibri", fontSize:15, color:INK, align:"left", valign:"top", margin:0 });
  // three-position diagram
  const boxes = [
    { t:"巨头商业工具", d:"锁死封闭\n利益冲突，不做开放内核", c:NAVY },
    { t:"gdsfactory 等开源", d:"布局层已成熟\n我们站在肩上", c:NAVY2 },
    { t:"LDA 真空格", d:"跨光子+量子\n开放标准 + AI 造核", c:BLUE, hl:true },
  ];
  let bx=0.7; const bw=3.7, bg=0.4;
  for(let i=0;i<boxes.length;i++){
    const b=boxes[i];
    card(s, bx, 3.7, bw, 2.3, b.hl?BLUE:WHITE, b.hl?null:"D6E0EE");
    s.addText(b.t, { x:bx+0.25, y:4.0, w:bw-0.5, h:0.5, fontFace:"Georgia", fontSize:17, bold:true, color:b.hl?WHITE:NAVY, align:"left", margin:0 });
    s.addText(b.d, { x:bx+0.25, y:4.6, w:bw-0.5, h:1.2, fontFace:"Calibri", fontSize:13.5, color:b.hl?ICE:INK, align:"left", valign:"top", margin:0 });
    if(i<2){ s.addImage({ data:I.arrow, x:bx+bw+0.02, y:4.65, w:0.32, h:0.32 }); }
    bx += bw+bg;
  }
  footer(s,3,false);

  // ============ SLIDE 4 — 我们是什么 ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "我们是什么");
  titleDark(s, "三大支柱：标准 + 协议 + AI 造核", 1.25);
  const pillars = [
    { ic:I.layer, n:"L0", t:"统一中间表示 IR", d:"同一套机器语言，表达光子与量子器件设计意图；巨头没认真做、gdsfactory 没占的真空格" },
    { ic:I.bolt, n:"L1", t:"智能体协议层", d:"Interpreter / Designer / Layout / Solver / Verifier 开放接口，让 AI 智能体确定性、可验证协作" },
    { ic:I.chip, n:"L3", t:"AI 自举求解核", d:"AI 写手 +（物理定律 + 大数据）裁判闭环，长出可验证求解器 —— 这一步我们已经跑通" },
  ];
  let px=0.7; const pw=3.85, pg=0.35;
  for(const p of pillars){
    card(s, px, 2.4, pw, 3.5, NAVY2);
    s.addShape(pres.shapes.RECTANGLE, { x:px, y:2.4, w:pw, h:0.12, fill:{color:CYAN}, line:{type:"none"} });
    s.addShape(pres.shapes.OVAL, { x:px+0.35, y:2.75, w:0.9, h:0.9, fill:{color:BLUE}, line:{type:"none"} });
    s.addImage({ data:p.ic, x:px+0.57, y:2.97, w:0.46, h:0.46 });
    s.addText(p.n, { x:px+pw-1.45, y:2.75, w:1.25, h:0.9, fontFace:"Calibri", fontSize:32, bold:true, color:BLUE, align:"center", valign:"middle", margin:0 });
    s.addText(p.t, { x:px+0.3, y:3.85, w:pw-0.6, h:0.6, fontFace:"Georgia", fontSize:18, bold:true, color:WHITE, align:"left", margin:0 });
    s.addText(p.d, { x:px+0.3, y:4.5, w:pw-0.6, h:1.3, fontFace:"Calibri", fontSize:13.5, color:ICE, align:"left", valign:"top", margin:0 });
    px += pw+pg;
  }
  footer(s,4);

  // ============ SLIDE 5 — PROOF headline ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "已被验证的事实");
  s.addText([
    { text:"AI 已自己写出 1D / 2D / 3D 电磁求解器，", options:{ color:WHITE, breakLine:true } },
    { text:"在“物理定律”真值锚上，逐题 5/5 通过。", options:{ color:CYAN } },
  ], { x:0.7, y:1.35, w:12, h:1.5, fontFace:"Georgia", fontSize:33, bold:true, align:"left", valign:"top", margin:0 });
  // big stat callouts
  const stats = [
    { n:"5/5", l:"1D 透射谱验证通过（解析解锚）" },
    { n:"5/5", l:"2D 透射谱验证通过（双 ORACLE）" },
    { n:"5/5", l:"3D 透射谱验证通过（双 ORACLE）" },
    { n:"0", l:"商业/美系求解器依赖（已自立）" },
  ];
  let stx=0.7; const sw=2.92, sg=0.18;
  for(const st of stats){
    card(s, stx, 3.3, sw, 2.2, NAVY2);
    s.addText(st.n, { x:stx, y:3.55, w:sw, h:1.1, fontFace:"Georgia", fontSize:50, bold:true, color:CYAN, align:"center", valign:"middle", margin:0 });
    s.addText(st.l, { x:stx+0.2, y:4.75, w:sw-0.4, h:0.7, fontFace:"Calibri", fontSize:13, color:ICE, align:"center", valign:"top", margin:0 });
    stx += sw+sg;
  }
  s.addText("1D / 2D / 3D 全维度透射谱，均已无需借任何商业求解器即得 —— 这是“自主可控求解内核”第一个可运行、可复核的实证。", { x:0.7, y:5.8, w:11.9, h:0.6, fontFace:"Calibri", fontSize:14, italic:true, color:WHITE, align:"left", margin:0 });
  footer(s,5);

  // ============ SLIDE 6 — PROOF detail table ============
  s = pres.addSlide(); lightBg(s);
  kicker(s, "证据链", BLUE);
  titleLight(s, "从 1D 到 3D：AI 自写求解核的验证台账", 1.25);
  const rows = [
    [ {text:"维度",options:{bold:true,color:WHITE,fill:{color:NAVY},align:"left"}},
      {text:"交付物",options:{bold:true,color:WHITE,fill:{color:NAVY},align:"left"}},
      {text:"验证方式（非 AI 真值锚）",options:{bold:true,color:WHITE,fill:{color:NAVY},align:"left"}},
      {text:"结果",options:{bold:true,color:WHITE,fill:{color:NAVY},align:"center"}} ],
    [ "1D","fdtd1d.py（零依赖，AI 自写）","传输矩阵解析解 tmm","selfcheck 4/4 PASS" ],
    [ "2D","fdtd2d.py（TEz Yee 网格）","解析解退化极限 + 点源柱面波","selfcheck 5/5 PASS" ],
    [ "3D","fdtd3d.py（全 Yee 六分量）","解析解退化极限 + 点源球面波","selfcheck 5/5 PASS" ],
    [ "性能","Numba-CPU JIT / PyTorch 后端","逐字节 / 逐位等价对照","~20× 加速 · GPU 一行激活" ],
  ];
  s.addTable(rows, { x:0.7, y:2.5, w:11.9, colW:[1.4,4.2,4.3,2.0], rowH:[0.5,0.7,0.7,0.7,0.7], fontSize:14, fontFace:"Calibri", color:INK, valign:"middle", border:{pt:1,color:"D6E0EE"}, align:"left", fill:{color:WHITE} });
  s.addText("验证底线：裁判最终判定强制落“物理定律 + 实证大数据”非 AI 真值锚 —— 纯 AI 互证（两 AI 互相点头）视为无效。这是 LDA 赢得信任的根本。", { x:0.7, y:6.1, w:11.9, h:0.6, fontFace:"Calibri", fontSize:13.5, italic:true, bold:true, color:NAVY, align:"left", margin:0 });
  footer(s,6,false);

  // ============ SLIDE 7 — 架构护城河 ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "护城河");
  titleDark(s, "护城河 = 标准 + 生态 + PDK，而非某段代码", 1.2);
  const layers = [
    { t:"L4 应用与生态", d:"用户层 / 开源社区 / 认证商业版", c:NAVY2 },
    { t:"L3 求解器后端", d:"FDTD / FEM / EME / 量子哈密顿 ← AI 自举生成 / 插件调度", c:NAVY2 },
    { t:"L2 开放 PDK / 器件本体 Registry", d:"社区 + 晶圆厂共建", c:NAVY2 },
    { t:"L1 智能体协议层", d:"Interpreter / Designer / Layout / Solver / Verifier 开放接口", c:NAVY2 },
    { t:"L0 开放统一 IR / DSL", d:"光子 + 量子统一中间表示（核心创新）", c:BLUE, hl:true },
  ];
  let ly=2.05; const lh=0.82, lgap=0.12;
  for(const L of layers){
    s.addShape(pres.shapes.RECTANGLE, { x:0.7, y:ly, w:11.9, h:lh, fill:{color:L.c}, line: L.hl?{color:CYAN,width:1.5}:{color:NAVY2,width:1} });
    s.addShape(pres.shapes.RECTANGLE, { x:0.7, y:ly, w:0.14, h:lh, fill:{color: L.hl?CYAN:BLUE}, line:{type:"none"} });
    s.addText(L.t, { x:1.05, y:ly, w:5.0, h:lh, fontFace:"Georgia", fontSize:17, bold:true, color:WHITE, align:"left", valign:"middle", margin:0 });
    s.addText(L.d, { x:6.1, y:ly, w:6.3, h:lh, fontFace:"Calibri", fontSize:13.5, color:ICE, align:"left", valign:"middle", margin:0 });
    ly += lh+lgap;
  }
  footer(s,7);

  // ============ SLIDE 8 — 主权策略 ============
  s = pres.addSlide(); lightBg(s);
  kicker(s, "自主可控", BLUE);
  titleLight(s, "主权三级：第一天就掌握命门", 1.25);
  const tiers = [
    { ic:I.shield, n:"C 级 · 永久自主", d:"L0 IR / L1 协议 / L3 AI 求解核 / 物理定律锚 —— 第一天自己掌握", c:BLUE },
    { ic:I.flask, n:"B 级 · 主权化复用", d:"gdsfactory / Meep / KLayout / SAX 等开源组件：fork + 镜像冷备，离线可构建、断供不崩", c:CYAN },
    { ic:I.server, n:"A 级 · 绝不依赖", d:"美系商业求解器（Lumerical / Ansys / Synopsys / Cadence）直接不采用", c:NAVY },
  ];
  let tx=0.7; const tw=3.85, tg=0.35;
  for(const t of tiers){
    card(s, tx, 2.4, tw, 3.4, WHITE, "D6E0EE");
    s.addShape(pres.shapes.OVAL, { x:tx+0.3, y:2.75, w:0.85, h:0.85, fill:{color:t.c}, line:{type:"none"} });
    s.addImage({ data:t.ic, x:tx+0.5, y:2.95, w:0.45, h:0.45 });
    s.addText(t.n, { x:tx+0.3, y:3.8, w:tw-0.6, h:0.5, fontFace:"Georgia", fontSize:18, bold:true, color:t.c===NAVY?NAVY:t.c, align:"left", margin:0 });
    s.addText(t.d, { x:tx+0.3, y:4.4, w:tw-0.6, h:1.3, fontFace:"Calibri", fontSize:13.5, color:INK, align:"left", valign:"top", margin:0 });
    tx += tw+tg;
  }
  s.addText("GPL 红线：GPL 组件仅作外部进程调用，绝不污染核心代码的许可。", { x:0.7, y:6.05, w:11.9, h:0.4, fontFace:"Calibri", fontSize:13.5, italic:true, color:NAVY, align:"left", margin:0 });
  footer(s,8,false);

  // ============ SLIDE 9 — 双引擎 ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "生态共建");
  titleDark(s, "双引擎：学生 + 退休专家 = 开源人力核心", 1.25);
  const eng = [
    { ic:I.graduation, t:"学生引擎", sub:"开源贡献生力军", d:"光电 / 微电子 / 量子 / 计算方向硕博与本科生。把“自然语言 → GDSII”做成毕设 / 科研课题 / 竞赛题 —— 契合刚需。" },
    { ic:I.users, t:"退休专家引擎", sub:"顾问 / 导师 / 质量背书", d:"EDA 老炮、光电半导体退休研究员、高校退休博导。有资源、有情怀、有时间，退休再发挥余热，把关基准、为内核背书。" },
  ];
  let ex=0.7; const ew=5.85, eg=0.4;
  for(const e of eng){
    card(s, ex, 2.4, ew, 3.6, NAVY2);
    s.addShape(pres.shapes.RECTANGLE, { x:ex, y:2.4, w:0.14, h:3.6, fill:{color:CYAN}, line:{type:"none"} });
    s.addShape(pres.shapes.OVAL, { x:ex+0.4, y:2.8, w:1.0, h:1.0, fill:{color:BLUE}, line:{type:"none"} });
    s.addImage({ data:e.ic, x:ex+0.65, y:3.05, w:0.5, h:0.5 });
    s.addText(e.t, { x:ex+1.6, y:2.85, w:ew-1.8, h:0.5, fontFace:"Georgia", fontSize:22, bold:true, color:WHITE, align:"left", valign:"middle", margin:0 });
    s.addText(e.sub, { x:ex+1.6, y:3.4, w:ew-1.8, h:0.4, fontFace:"Calibri", fontSize:14, italic:true, color:CYAN, align:"left", valign:"middle", margin:0 });
    s.addText(e.d, { x:ex+0.4, y:4.1, w:ew-0.8, h:1.7, fontFace:"Calibri", fontSize:14.5, color:ICE, align:"left", valign:"top", margin:0 });
    ex += ew+eg;
  }
  footer(s,9);

  // ============ SLIDE 10 — 四大集群 ============
  s = pres.addSlide(); lightBg(s);
  kicker(s, "资源地图", BLUE);
  titleLight(s, "四大对接集群：覆盖光子与量子最强节点", 1.25);
  const clusters = [
    { c:"武汉", d:"武汉光电国家研究中心 / NOEIC / 华科", v:"硅光 PDK + 学生密度全国最高" },
    { c:"重庆", d:"CUMEC（开放硅光工艺平台）", v:"开放 PDK 对接" },
    { c:"上海", d:"SITRI / 图灵量子 / 芯和 / 华大九天", v:"PDK + 光量子 + EDA 老炮三重富集" },
    { c:"合肥", d:"中科大 / 本源 / 国盾", v:"量子最强院校 + 量子企业" },
  ];
  let clx=0.7, cly=2.4; const clw=2.92, clh=2.0, clg=0.18;
  for(let i=0;i<clusters.length;i++){
    const cl=clusters[i];
    card(s, clx, cly, clw, clh, WHITE, "D6E0EE");
    s.addShape(pres.shapes.RECTANGLE, { x:clx, y:cly, w:clw, h:0.6, fill:{color:BLUE}, line:{type:"none"} });
    s.addText(cl.c, { x:clx, y:cly, w:clw, h:0.6, fontFace:"Georgia", fontSize:22, bold:true, color:WHITE, align:"center", valign:"middle", margin:0 });
    s.addText(cl.d, { x:clx+0.2, y:cly+0.7, w:clw-0.4, h:0.8, fontFace:"Calibri", fontSize:13, color:INK, align:"left", valign:"top", margin:0 });
    s.addText(cl.v, { x:clx+0.2, y:cly+1.5, w:clw-0.4, h:0.45, fontFace:"Calibri", fontSize:12.5, italic:true, bold:true, color:BLUE, align:"left", valign:"top", margin:0 });
    clx += clw+clg;
    if(i===1){ clx=0.7; cly=4.15; }
  }
  footer(s,10,false);

  // ============ SLIDE 11 — 资源诉求 ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "资源诉求");
  titleDark(s, "把“可用的内核”变成“产业可用的生态”", 1.2);
  const needs = [
    { ic:I.server, t:"算力", d:"自配 GPU 部署机 → 点亮 3D GPU 求解核、攻生产级超大网格" },
    { ic:I.flask, t:"实测语料", d:"真实流片 / 测量数据 → 建“实证大数据锚”，让 AI 裁判可信" },
    { ic:I.users, t:"顾问与背书", d:"退休 EDA 老炮 / 光电·量子退休研究员入库把关基准" },
    { ic:I.graduation, t:"院校合作", d:"毕设 / 竞赛 / 课题联合设立 → 学生引擎冷启动" },
    { ic:I.industry, t:"晶圆厂 PDK", d:"本土硅光 PDK 对接 → 打通“设计→签核→流片”闭环" },
    { ic:I.handshake, t:"资金 / 商业合作", d:"认证版研发 / 垂直场景落地 / 赛事运营 → 阶段3 试点" },
  ];
  let nx=0.7, ny=2.1; const nw=3.85, nh=1.55, ngx=0.35, ngy=0.25;
  for(const nd of needs){
    card(s, nx, ny, nw, nh, NAVY2);
    s.addShape(pres.shapes.OVAL, { x:nx+0.25, y:ny+0.3, w:0.7, h:0.7, fill:{color:BLUE}, line:{type:"none"} });
    s.addImage({ data:nd.ic, x:nx+0.4, y:ny+0.45, w:0.4, h:0.4 });
    s.addText(nd.t, { x:nx+1.1, y:ny+0.25, w:nw-1.3, h:0.5, fontFace:"Georgia", fontSize:17, bold:true, color:WHITE, align:"left", margin:0 });
    s.addText(nd.d, { x:nx+1.1, y:ny+0.72, w:nw-1.3, h:0.75, fontFace:"Calibri", fontSize:12.5, color:ICE, align:"left", valign:"top", margin:0 });
    nx += nw+ngx;
    if(nx>11.6){ nx=0.7; ny+=nh+ngy; }
  }
  footer(s,11);

  // ============ SLIDE 12 — 回报 ============
  s = pres.addSlide(); lightBg(s);
  kicker(s, "我们能给出什么", BLUE);
  titleLight(s, "共建者回报：先发卡位 + 自主可控底座", 1.25);
  const rets = [
    { ic:I.bullseye, t:"定义标准的先发卡位", d:"L0 / L1 开放标准的共同制定权——规则由共建者一起写" },
    { ic:I.shield, t:"可信验证基建", d:"公开对抗性基准 + 反向悬赏，共建行业信任，对冲美系断供" },
    { ic:I.rocket, t:"自主可控底座", d:"对美系断供风险的结构性对冲，对国产替代的直接支撑" },
    { ic:I.handshake, t:"成果共享", d:"开源内核免费使用；认证版提供 SLA 与责任兜底（红帽模式）" },
  ];
  let rx=0.7; const rw=2.92, rg=0.18;
  for(const r of rets){
    card(s, rx, 2.5, rw, 3.3, WHITE, "D6E0EE");
    s.addShape(pres.shapes.OVAL, { x:rx+rw/2-0.45, y:2.85, w:0.9, h:0.9, fill:{color:BLUE}, line:{type:"none"} });
    s.addImage({ data:r.ic, x:rx+rw/2-0.25, y:3.05, w:0.5, h:0.5 });
    s.addText(r.t, { x:rx+0.2, y:3.95, w:rw-0.4, h:0.6, fontFace:"Georgia", fontSize:16, bold:true, color:NAVY, align:"center", margin:0 });
    s.addText(r.d, { x:rx+0.25, y:4.55, w:rw-0.5, h:1.1, fontFace:"Calibri", fontSize:13, color:INK, align:"center", valign:"top", margin:0 });
    rx += rw+rg;
  }
  footer(s,12,false);

  // ============ SLIDE 13 — 路线图 ============
  s = pres.addSlide(); darkBg(s);
  kicker(s, "路线图");
  titleDark(s, "五年四阶段：从内核跑通到标准话语权", 1.25);
  const phases = [
    { n:"0", t:"战略奠基", st:"✅ 已完成", c:CYAN },
    { n:"1", t:"技术验证", st:"🔶 进行中", c:BLUE, cur:true },
    { n:"2", t:"生态启动", st:"⏳ 开源首发", c:GREY },
    { n:"3", t:"商业试点", st:"⏳ 认证版+PDK", c:GREY },
    { n:"4", t:"规模扩张", st:"⏳ 标准话语权", c:GREY },
  ];
  let phx=0.7; const phw=2.32, phg=0.15;
  for(let i=0;i<phases.length;i++){
    const p=phases[i];
    card(s, phx, 2.6, phw, 2.6, p.cur?BLUE:NAVY2);
    s.addText(p.n, { x:phx, y:2.8, w:phw, h:0.9, fontFace:"Georgia", fontSize:40, bold:true, color:p.cur?WHITE:p.c, align:"center", margin:0 });
    s.addText(p.t, { x:phx, y:3.75, w:phw, h:0.5, fontFace:"Georgia", fontSize:17, bold:true, color:WHITE, align:"center", margin:0 });
    s.addText(p.st, { x:phx, y:4.3, w:phw, h:0.5, fontFace:"Calibri", fontSize:13, italic:true, color:p.cur?ICE:GREY, align:"center", margin:0 });
    if(i<phases.length-1){ s.addImage({ data:I.arrow, x:phx+phw+0.01, y:3.7, w:0.3, h:0.3 }); }
    phx += phw+phg;
  }
  s.addText("已固化决策：光子优先、量子后上；先单点垂直场景、后统一。", { x:0.7, y:5.6, w:11.9, h:0.5, fontFace:"Calibri", fontSize:15, bold:true, italic:true, color:CYAN, align:"left", margin:0 });
  footer(s,13);

  // ============ SLIDE 14 — 风险诚实 ============
  s = pres.addSlide(); lightBg(s);
  kicker(s, "诚实的边界", BLUE);
  titleLight(s, "我们把风险摊在桌面上", 1.25);
  const risks = [
    { ic:I.checkC, t:"验证底线不可破", d:"裁判最终判定强制落物理定律 + 大数据锚 —— 这是信任来源" },
    { ic:I.shieldC, t:"主权红线清晰", d:"A 级永借、B 级主权化、C 级自主；GPL 组件仅外部调用" },
    { ic:I.boltC, t:"窗口竞速", d:"每阶段末交付可公开锁定的资产（标准 / 基准 / PDK 意向），用先发筑墙" },
    { ic:I.chartC, t:"诚实标注性能边界", d:"主权核以 float64 运行，消费级 GPU 加速比可能不及数据中心卡 —— 如实标注，绝不夸大" },
  ];
  let kx=0.7, kyy=2.4; const kw=5.85, kh=1.8, kg=0.4, kr=0.3;
  for(const r of risks){
    card(s, kx, kyy, kw, kh, WHITE, "D6E0EE");
    s.addShape(pres.shapes.OVAL, { x:kx+0.3, y:kyy+0.25, w:0.7, h:0.7, fill:{color:"EAF2FB"}, line:{type:"none"} });
    s.addImage({ data:r.ic, x:kx+0.45, y:kyy+0.4, w:0.4, h:0.4 });
    s.addText(r.t, { x:kx+1.2, y:kyy+0.15, w:kw-1.4, h:0.5, fontFace:"Georgia", fontSize:17, bold:true, color:NAVY, align:"left", margin:0 });
    s.addText(r.d, { x:kx+1.2, y:kyy+0.7, w:kw-1.4, h:0.95, fontFace:"Calibri", fontSize:13.5, color:INK, align:"left", valign:"top", margin:0 });
    kx += kw+kg;
    if(kx>11.6){ kx=0.7; kyy+=kh+kr; }
  }
  footer(s,14,false);

  // ============ SLIDE 15 — CTA ============
  s = pres.addSlide(); darkBg(s);
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:PW, h:0.12, fill:{color:CYAN}, line:{type:"none"} });
  s.addImage({ data:I.quote, x:0.9, y:0.9, w:0.7, h:0.7 });
  s.addText("如何参与", { x:0.9, y:1.7, w:11, h:0.9, fontFace:"Georgia", fontSize:38, bold:true, color:WHITE, align:"left", margin:0 });
  const ctas = [
    { ic:I.graduation, t:"院校 / 学生", d:"认领一个 Good First Issue，把光子 / 量子设计自动化做成课题" },
    { ic:I.users, t:"退休专家", d:"加入顾问委员会，把关基准、为自主内核背书 —— 退休再发挥一次余热" },
    { ic:I.industry, t:"晶圆厂 / 器件企业", d:"提供 PDK 或实测语料，共建“实证大数据锚”，锁定生态位" },
    { ic:I.rocket, t:"投资 / 产业方", d:"联合点亮 GPU 算力与垂直场景，共享定义标准与自主可控的红利" },
  ];
  let ccx=0.9; const cwid=2.85, cg2=0.18;
  for(const c of ctas){
    card(s, ccx, 2.9, cwid, 2.6, NAVY2);
    s.addShape(pres.shapes.OVAL, { x:ccx+cwid/2-0.42, y:3.2, w:0.84, h:0.84, fill:{color:BLUE}, line:{type:"none"} });
    s.addImage({ data:c.ic, x:ccx+cwid/2-0.23, y:3.4, w:0.46, h:0.46 });
    s.addText(c.t, { x:ccx+0.15, y:4.2, w:cwid-0.3, h:0.5, fontFace:"Georgia", fontSize:16, bold:true, color:WHITE, align:"center", margin:0 });
    s.addText(c.d, { x:ccx+0.2, y:4.75, w:cwid-0.4, h:0.7, fontFace:"Calibri", fontSize:12, color:ICE, align:"center", valign:"top", margin:0 });
    ccx += cwid+cg2;
  }
  s.addText("联系：工业5点0产业生态联盟 · 杜玉河（微信号：gongyhlw）", { x:0.9, y:5.9, w:11.5, h:0.5, fontFace:"Calibri", fontSize:16, bold:true, color:CYAN, align:"left", margin:0 });

  await pres.writeFile({ fileName: "D:/agent_LDA/LDA_产业共建路演.pptx" });
  console.log("PPTX written");
}

build().catch(e=>{ console.error(e); process.exit(1); });
