const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, PageNumber, PageBreak, TableOfContents
} = require("C:/Users/Administrator/node_modules/docx");

// ---- palette ----
const BLUE = "1F4E79";      // headings
const BLUE_LT = "D9E2F3";   // table header fill
const GREY_LT = "F2F2F2";   // zebra
const ACCENT = "2E75B6";    // thin rules

const border = { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function h1(t){ return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing:{before:280,after:140}, children:[new TextRun({text:t, bold:true, color: BLUE, size:30})] }); }
function h2(t){ return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing:{before:200,after:100}, children:[new TextRun({text:t, bold:true, color: BLUE, size:26})] }); }
function h3(t){ return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing:{before:140,after:80}, children:[new TextRun({text:t, bold:true, color: "404040", size:23})] }); }
function para(t, opts={}){ return new Paragraph({ spacing:{after:120, line:300}, alignment: opts.align||AlignmentType.LEFT, children:[new TextRun({text:t, size:21, ...opts.run})] }); }
function quote(t){ return new Paragraph({ spacing:{before:80,after:160,line:320}, border:{left:{style:BorderStyle.SINGLE,size:18,color:ACCENT,space:12}}, children:[new TextRun({text:t, italics:true, size:22, color:"404040"})] }); }
function bullet(t){ return new Paragraph({ numbering:{reference:"bullets",level:0}, spacing:{after:60,line:280}, children:[new TextRun({text:t, size:21})] }); }
function num(t){ return new Paragraph({ numbering:{reference:"numbers",level:0}, spacing:{after:60,line:280}, children:[new TextRun({text:t, size:21})] }); }

function cell(text, {fill, bold, color, align, width} = {}){
  return new TableCell({
    borders, width:{size:width, type:WidthType.DXA},
    shading: fill ? {fill, type:ShadingType.CLEAR} : undefined,
    margins:{top:70,bottom:70,left:120,right:120},
    verticalAlign:"center",
    children:[ new Paragraph({ alignment: align||AlignmentType.LEFT, spacing:{line:260}, children:[
      new TextRun({ text, bold: bold||false, color: color||"000000", size:20 })
    ]}) ]
  });
}
function table(headers, rows, colWidths){
  const total = colWidths.reduce((a,b)=>a+b,0);
  const head = new TableRow({ tableHeader:true, children: headers.map((h,i)=> cell(h, {fill:BLUE_LT, bold:true, color:BLUE, width:colWidths[i]})) });
  const body = rows.map((r,ri)=> new TableRow({ children: r.map((c,i)=> cell(c, {fill: ri%2? GREY_LT:undefined, width:colWidths[i]})) }));
  return new Table({ width:{size:total, type:WidthType.DXA}, columnWidths:colWidths, rows:[head, ...body] });
}

const content = [];

// ---------- COVER ----------
content.push(new Paragraph({ spacing:{before:600}, alignment:AlignmentType.CENTER, children:[ new TextRun({text:"LDA 产业共建白皮书", bold:true, size:48, color:BLUE}) ]}));
content.push(new Paragraph({ spacing:{before:120}, alignment:AlignmentType.CENTER, children:[ new TextRun({text:"开源 · Agent 原生的光芯片与量子芯片设计底座", size:26, color:"404040"}) ]}));
content.push(new Paragraph({ spacing:{before:40}, alignment:AlignmentType.CENTER, border:{bottom:{style:BorderStyle.SINGLE,size:12,color:ACCENT,space:8}}, children:[ new TextRun({text:""}) ]}));
content.push(new Paragraph({ spacing:{before:360}, alignment:AlignmentType.CENTER, children:[ new TextRun({text:"面向产业界 · 学界 · 投资界的生态共建邀请", size:22, color:"595959"}) ]}));
content.push(new Paragraph({ spacing:{before:200}, alignment:AlignmentType.CENTER, children:[ new TextRun({text:"文档编号：LDA-IW-001   |   版本 v1.0（对外公开）   |   2026-08-16", size:20, color:"808080"}) ]}));
content.push(new Paragraph({ spacing:{before:40}, alignment:AlignmentType.CENTER, children:[ new TextRun({text:"编制：LDA 领域研究室 · 工业5点0产业生态联盟（杜玉河）", size:20, color:"808080"}) ]}));
content.push(new Paragraph({ children:[new PageBreak()] }));

// ---------- TOC ----------
content.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing:{after:160}, children:[new TextRun({text:"目录", bold:true, color:BLUE, size:30})] }));
content.push(new TableOfContents("toc", { hyperlink:true, headingStyleRange:"1-2" }));
content.push(new Paragraph({ children:[new PageBreak()] }));

// ---------- 0 执行摘要 ----------
content.push(h1("0. 执行摘要"));
content.push(para("光芯片（PDA）与量子芯片（QEDA）是未来十年最具战略价值的两条硬科技赛道，但它们的设计工具——EDA——长期被美系商业巨头垄断，且巨头出于自身商业模式，结构性地不会去做“开放内核”。"));
content.push(para("LDA（Light-Driven Architecture）要做的，不是又一个“帮工程师画图”的工具，而是一个开源、自主可控、由 AI 智能体直接编写底层求解内核的设计底座。我们用一个已被验证的事实说明这不是设想："));
content.push(quote("LDA 的 AI 智能体已经自己写出了 1D / 2D / 3D 电磁场求解器（FDTD），并在“物理定律”这一不可辩驳的真值锚上，逐题通过了 5/5 验证。这意味着——“AI 造设计内核”这条路，已经从论文设想，变成了跑通的代码。"));
content.push(para("本白皮书面向产业界、学界与投资界伙伴，说明：我们要解决什么问题、我们已经证明了什么、我们邀请各方以何种方式共建、以及我们需要的关键资源。"));

// ---------- 1 为什么做 ----------
content.push(h1("1. 我们为什么做这件事"));
content.push(h2("1.1 产业在爆发，工具在断供"));
content.push(bullet("光子器件产业正被 AI 数据中心拉动高速增长：800G / 1.6T 光互联需求使硅光器件产业 2025 年增速达 37%+；光子 EDA 软件 2025 年约 13 亿美元、年复合增速约 12%。"));
content.push(bullet("量子芯片进入国产窗口期：国产与海外在 QEDA 上无明显代差，自主可控战略意义极强。"));
content.push(bullet("但工具被“卡”：2025 年起美系 EDA 巨头（Synopsys / Cadence / Siemens）对华断供风险持续；Synopsys 完成对 Ansys 的收购后，光子仿真旗舰 Lumerical 归入其体系，垄断在加深而非减弱。"));
content.push(h2("1.2 巨头的“结构性盲区”"));
content.push(para("巨头（Synopsys / Cadence）的收入根基是可信商业求解器的授权费。一旦由 AI 长出“开放、可验证、免费”的内核，等于击穿自己的收费地基——所以它们只会把 AI 做成商业工具里的“辅助层”，永远不会做开放内核。"));
content.push(quote("这给 LDA 留下一个真实、且巨头结构性不能进入的生态真空：跨光子 + 量子统一的开放标准层（中间表示 IR + 智能体协议）+ AI 自举求解核。"));
content.push(h2("1.3 现有开源“不够”"));
content.push(para("开源的 gdsfactory 已跑通“画版图 / 管 PDK”的布局层——它是我们要站在肩上的基座，但不是护城河。它不占“统一标准层”，更没有“AI 写求解内核”。"));

// ---------- 2 是什么 ----------
content.push(h1("2. LDA 是什么：三个定位"));
content.push(table(
  ["维度","LDA 的定位","我们不做的是什么"],
  [
    ["对标对象","不做巨头的设计工具竞品","不重造商业 EDA"],
    ["技术层次","做 gdsfactory 之上的“开放标准与编排内核”","不重写布局层（已是成熟开源）"],
    ["核心创新","AI 智能体直接编写、并验证底层求解内核","不让人“手调参数”，让 agent 出结果"],
  ],
  [2300, 4200, 2860]
));
content.push(para("一句话：LDA 是光芯片与量子芯片设计领域的“开放标准 + AI 造核”底座——中立、可插拔、能调度所有现存工具，并把研发过程本身也 agent 化。", {run:{bold:true,color:BLUE}}));
content.push(h3("三大支柱"));
content.push(bullet("L0 统一中间表示（IR）：同一套机器语言，表达光子器件与量子器件的设计意图，使“电子-光子-量子协同设计”成为可能——巨头没认真做、gdsfactory 没占的真空格。"));
content.push(bullet("L1 智能体协议层：定义 Interpreter / Designer / Layout / Solver / Verifier 等开放接口，让多个 AI 智能体确定性、可验证地协作。"));
content.push(bullet("L3 AI 自举求解核：用 AI 写手 +（物理定律 + 实证大数据）裁判的闭环，长出可验证的求解器——这一步我们已经跑通。"));

// ---------- 3 已证明 ----------
content.push(h1("3. 我们已证明了什么（核心差异化）"));
content.push(para("这一节是 LDA 区别于“又一个 PPT 项目”的关键。所有结论来自真实运行的自研代码与确定性验证脚本。"));
content.push(h2("3.1 已交付：AI 自写的 FDTD 电磁求解核（1D / 2D / 3D）"));
content.push(table(
  ["维度","交付物","验证方式（非 AI 真值锚）","结果"],
  [
    ["1D","fdtd1d.py（零依赖，AI 自写）","传输矩阵解析解（tmm）","selfcheck 4/4 PASS"],
    ["2D","fdtd2d.py（TEz Yee 网格）","解析解退化极限 + 点源柱面波","selfcheck 5/5 PASS"],
    ["3D","fdtd3d.py（全 Yee 六分量）","解析解退化极限 + 点源球面波","selfcheck 5/5 PASS"],
  ],
  [1200, 3200, 3360, 1600]
));
content.push(quote("1D / 2D / 3D 全维度，透射谱均已无需借任何商业/美系求解器即得——这是“自主可控求解内核”路径第一个可运行、可复核的实证。"));
content.push(h2("3.2 已交付：性能升维（已具备生产级 CPU 性能）"));
content.push(bullet("Numba-CPU JIT 加速：与纯参考实现逐字节等价，同精度 5/5 通过，约 20× 加速（16 分 19 秒 → 0.8 分）。"));
content.push(bullet("PyTorch 可切换 GPU/CPU 张量化后端：复用同一套几何构造、算法完全一致、CPU 上 5/5 逐位一致；device='cuda' 一行即切换 GPU——装上 CUDA 轮子即可点亮。"));
content.push(h2("3.3 我们的“不可妥协”：验证底线"));
content.push(para("AI 写手 + AI 裁判可以最大化，但裁判最终判定必须落“非 AI 真值锚”——这是数学约束，不是保守："));
content.push(bullet("① 物理定律锚：解析解、麦克斯韦方程确定性计算——方程的必然，不是某人的意见。"));
content.push(bullet("② 实证大数据锚：跨多源真实流片 / 测量语料，众人贡献、越用越厚。"));
content.push(quote("没有任何外部真值的“纯 AI 互证”，等于两个 AI 互相点头——错了也被确认。此线不可破。这也是 LDA 赢得产业信任的根本。"));

// ---------- 4 架构护城河 ----------
content.push(h1("4. 架构与护城河"));
content.push(h2("4.1 分层架构（L0–L4）"));
content.push(para("L4 应用与生态（用户层 / 开源社区 / 认证商业版）"));
content.push(para("L3 求解器后端（FDTD/FEM/EME/量子哈密顿 ← AI 自举生成 / 插件调度）"));
content.push(para("L2 开放 PDK / 器件本体 Registry（社区 + 晶圆厂共建）"));
content.push(para("L1 智能体协议层（Interpreter/Designer/Layout/Solver/Verifier 开放接口）"));
content.push(para("L0 开放统一 IR/DSL（光子 + 量子统一中间表示）", {run:{bold:true,color:BLUE}}));
content.push(para("护城河 = 标准 + 生态 + PDK 供给，而非某一段求解器代码。巨头与现有开源都没有占这一层。"));
content.push(h2("4.2 自主可控（主权）策略"));
content.push(table(
  ["级别","含义","实例与处置"],
  [
    ["永久自主（C 级）","第一天就自己掌握","L0 IR / L1 协议 / L3 AI 求解核 / 物理定律锚"],
    ["主权化复用（B 级）","fork + 镜像冷备，离线可构建","gdsfactory、Meep、KLayout、SAX 等开源组件"],
    ["绝不依赖（A 级）","直接不采用","美系商业求解器（Lumerical / Ansys / Synopsys / Cadence）"],
  ],
  [2200, 2400, 4760]
));
content.push(para("GPL 红线：GPL 组件仅作外部进程调用，绝不污染核心代码的许可。"));

// ---------- 5 生态共建 ----------
content.push(h1("5. 生态共建模型：双引擎 + 四大集群"));
content.push(h2("5.1 双引擎人群（LDA 开源生态的人力核心）"));
content.push(table(
  ["引擎","人群","角色","诉求契合点"],
  [
    ["学生引擎","光电 / 微电子 / 量子 / 计算方向硕博与本科生","开源贡献生力军","把“自然语言 → GDSII”做成毕设 / 科研课题 / 竞赛题"],
    ["退休专家引擎","EDA 老炮、光电半导体退休研究员、高校退休博导","顾问 / 导师 / 质量背书","有资源、有情怀、有时间，退休再发挥余热"],
  ],
  [1500, 2600, 2100, 3160]
));
content.push(h2("5.2 四大对接集群"));
content.push(table(
  ["集群","核心机构","主打价值"],
  [
    ["武汉","武汉光电国家研究中心 / NOEIC / 华科","硅光 PDK + 学生密度全国最高"],
    ["重庆","CUMEC（开放硅光工艺平台）","开放 PDK 对接"],
    ["上海","SITRI / 图灵量子 / 芯和 / 华大九天","PDK + 光量子 + EDA 老炮三重富集"],
    ["合肥","中科大 / 本源 / 国盾","量子最强院校 + 量子企业"],
  ],
  [1400, 4200, 3760]
));
content.push(h2("5.3 企业 / 晶圆厂协同"));
content.push(bullet("硅光代工 PDK：NOEIC / CUMEC / SITRI 等——对接本土工艺，共建“自主可控”牌。"));
content.push(bullet("光模块 / 光子计算 / 量子芯片企业：中际旭创、新易盛、曦智、图灵量子、本源、国盾等——既是潜在用户，也是退休专家来源与实测语料来源。"));
content.push(bullet("EDA 企业退休群体：华大九天 / 概伦 / 芯华章等——补足“基准题策展”与“信任墙”两块关键短板。"));

// ---------- 6 资源诉求 ----------
content.push(h1("6. 资源诉求（我们邀请各方共建什么）"));
content.push(para("LDA 已用极小成本证明了技术可行性。要把“可用的内核”变成“产业可用的生态”，需要以下关键资源。我们坚持“开发主权 AI 自举、验证与语料开放协作”的原则——不外包核心开发，但诚挚邀请各方在各自可即插即用的资产上共建。"));
content.push(h2("6.1 关键资源清单"));
content.push(table(
  ["资源类别","具体诉求","用于","回报方"],
  [
    ["算力","自配 GPU 部署机（RTX 50 系 / 数据中心级）","点亮 3D GPU 求解核、攻生产级超大网格","算力提供方（联合研发 / 署名）"],
    ["实测语料","真实流片 / 测量数据（S 参数、n_eff、透射谱）","建“实证大数据锚”，让 AI 裁判可信","晶圆厂 / 器件企业 / 高校"],
    ["顾问与背书","退休 EDA 老炮、光电 / 量子退休研究员入库","把关基准题、为开源内核背书","顾问委员会成员"],
    ["院校合作","毕设 / 竞赛 / 科研课题联合设立","学生引擎开源贡献冷启动","高校实验室"],
    ["晶圆厂 PDK","本土硅光 PDK 对接意向","打通“设计 → 签核 → 流片”闭环","PDK 供给方（生态位卡位）"],
    ["资金 / 商业合作","认证版研发、垂直场景落地、赛事运营","阶段 3 商业试点","战略投资 / 产业合作方"],
  ],
  [1700, 3260, 2500, 1900]
));
content.push(h2("6.2 我们能给出什么"));
content.push(bullet("定义标准的先发卡位：L0/L1 开放标准的共同制定权。"));
content.push(bullet("可信验证基建：公开对抗性基准 + 反向悬赏，共建行业信任。"));
content.push(bullet("自主可控底座：对美系断供风险的结构性对冲，对国产替代的直接支撑。"));
content.push(bullet("成果共享：开源内核免费使用；认证版提供 SLA 与责任兜底（红帽模式）。"));

// ---------- 7 路线图 ----------
content.push(h1("7. 路线图与里程碑"));
content.push(para("阶段0 战略奠基 ✅  →  阶段1 技术验证（进行中）  →  阶段2 生态启动  →  阶段3 商业试点  →  阶段4 规模扩张"));
content.push(table(
  ["阶段","主题","当前状态"],
  [
    ["0","战略奠基","✅ 已完成（战略纪要、主权政策、4 份分析文档）"],
    ["1","技术验证","🔶 进行中：FDTD 1D/2D/3D + 性能升维已实证"],
    ["2","生态启动","⏳ 开源首发 + 基准套件 + 双引擎招募（本白皮书即启动动作之一）"],
    ["3","商业试点","⏳ 认证版 + 首个 PDK 合作 + 垂直场景落地"],
    ["4","规模扩张","⏳ 跨赛道 / 跨区域复制 + 标准话语权"],
  ],
  [1200, 2400, 5760]
));
content.push(para("已固化决策：光子优先、量子后上；先单点垂直场景、后统一。", {run:{bold:true,color:BLUE}}));

// ---------- 8 风险 ----------
content.push(h1("8. 风险与治理"));
content.push(num("验证底线不可破：裁判最终判定强制落物理定律 + 大数据锚——这是信任的来源。"));
content.push(num("主权红线：A 级永借、B 级主权化、C 级自主；GPL 组件仅外部调用。"));
content.push(num("窗口竞速：每个阶段末尾交付“可公开锁定”的资产（标准草案 / 基准 / PDK 意向），用先发筑墙。"));
content.push(num("责任归属：开源 AS-IS 免责 + 认证版 SLA，签核责任落在设计师 + 代工 PDK。"));
content.push(num("诚实边界：主权核以 float64 运行，在消费级 GPU 上加速比可能不及数据中心卡——我们如实标注，绝不夸大。"));

// ---------- 9 行动号召 ----------
content.push(h1("9. 如何参与（行动号召）"));
content.push(bullet("院校 / 学生：认领一个“Good First Issue”，把光子 / 量子设计自动化做成课题。"));
content.push(bullet("退休专家：加入顾问委员会，把关基准、为自主内核背书——退休再发挥一次余热。"));
content.push(bullet("晶圆厂 / 器件企业：提供 PDK 或实测语料，共建“实证大数据锚”，锁定生态位。"));
content.push(bullet("投资 / 产业方：联合点亮 GPU 算力与垂直场景，共享定义标准与自主可控的红利。"));
content.push(quote("联系：工业5点0产业生态联盟 · 杜玉河（微信号：gongyhlw）"));

// ---------- footer note ----------
content.push(new Paragraph({ spacing:{before:200}, border:{top:{style:BorderStyle.SINGLE,size:6,color:"BFBFBF",space:8}}, children:[ new TextRun({text:"本白皮书依据 LDA 前期战略文档包（可行性分析、技术白皮书、市场竞争与赛道分析、发展里程碑与路线图）提炼对外版本，关键技术结论均来自真实运行的自研代码与确定性验证脚本。", size:18, color:"808080", italics:true}) ]}));

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 21 } } },
    paragraphStyles: [
      { id:"Heading1", name:"Heading 1", basedOn:"Normal", next:"Normal", quickFormat:true, run:{size:30,bold:true,color:BLUE,font:"Microsoft YaHei"}, paragraph:{spacing:{before:280,after:140}, outlineLevel:0} },
      { id:"Heading2", name:"Heading 2", basedOn:"Normal", next:"Normal", quickFormat:true, run:{size:26,bold:true,color:BLUE,font:"Microsoft YaHei"}, paragraph:{spacing:{before:200,after:100}, outlineLevel:1} },
      { id:"Heading3", name:"Heading 3", basedOn:"Normal", next:"Normal", quickFormat:true, run:{size:23,bold:true,color:"404040",font:"Microsoft YaHei"}, paragraph:{spacing:{before:140,after:80}, outlineLevel:2} },
    ]
  },
  numbering: {
    config: [
      { reference:"bullets", levels:[{ level:0, format:LevelFormat.BULLET, text:"•", alignment:AlignmentType.LEFT, style:{ paragraph:{ indent:{ left:540, hanging:280 } } } }] },
      { reference:"numbers", levels:[{ level:0, format:LevelFormat.DECIMAL, text:"%1.", alignment:AlignmentType.LEFT, style:{ paragraph:{ indent:{ left:540, hanging:280 } } } }] },
    ]
  },
  sections: [{
    properties: { page: { size:{ width:11906, height:16838 }, margin:{ top:1440, right:1300, bottom:1300, left:1300 } } },
    footers: { default: new Footer({ children:[ new Paragraph({ alignment:AlignmentType.CENTER, children:[
      new TextRun({ text:"LDA 产业共建白皮书 v1.0 · 工业5点0产业生态联盟  ", size:16, color:"808080" }),
      new TextRun({ children:[PageNumber.CURRENT], size:16, color:"808080" }),
    ]}) ]}) },
    children: content
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("D:/agent_LDA/LDA_产业共建白皮书.docx", buf);
  console.log("WROTE docx bytes=", buf.length);
});
