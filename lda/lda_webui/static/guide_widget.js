/*
 * LDA 用户侧 3 分钟上手引导浮窗（Craft 模式生成）
 * 聚光灯式分步引导：欢迎 → 顶部状态卡 → 设计 → 版图/仿真 → 验证 → 智能体客服 → 完成。
 * 自包含、零依赖、暗色面板跨主题可读；不依赖页面 CSS 变量。
 * 触发：① 首次访问自动弹（localStorage lda_onboard_v1_done 未设）② ?guide=1 强制开
 *       ③ 左下角常驻「🎯 3分钟引导」按钮可随时重开（给投资人 demo 用）。
 */
(function () {
  "use strict";
  var KEY = "lda_onboard_v1_done";
  // 自包含配色（暗底浅字，明/暗主题页均清晰）
  var C = {
    panel: "#0e1525", panel2: "#16203a", line: "#2a3658",
    txt: "#e8eefb", mut: "#9fb0d4", accent: "#38bdf8", accent2: "#3b82f6",
    dim: "rgba(8,12,24,.66)"
  };

  function el(tag, style, html) {
    var e = document.createElement(tag);
    if (style) e.setAttribute("style", style);
    if (html != null) e.innerHTML = html;
    return e;
  }

  // ============================ 引导步骤 ============================
  // sel: 要聚光灯高亮的元素选择器；parent:true 表示向上找最近 .sec 整体高亮
  var STEPS = [
    {
      title: "欢迎使用 LDA · 3 分钟上手",
      body: "<p>这是一次 <b>3 分钟上手引导</b>。LDA 是开源、Agent 原生的<b>光子 + 量子芯片设计软件</b>，"
          + "核心红线：<b>LLM 不进判决路径</b>，是否 PASS 由物理定律锚的死标量比对决定。</p>"
          + "<p>我们带你走完一条主线：<b>设计 → 仿真/版图 → 验证</b>。途中卡住，随时点右下角蓝色气泡找智能体客服。</p>",
      sel: null
    },
    {
      title: "① 一眼看懂系统健康",
      body: "<p>顶部四张实时卡：验证 harness 通过数、AI 内核候选、锚覆盖（S1–S12）、已落地真地基层。"
          + "它们由后端<b>实时真跑</b>，不是装饰。</p><p>👉 你看到的就是 LDA 当前的真面目。</p>",
      sel: "#cards"
    },
    {
      title: "② 设计：给目标，出统一设计包",
      body: "<p>在「旗舰流程 · 设计闭环端到端」里选器件类型、填目标值，点 <b>运行设计闭环 → 出设计包</b>。"
          + "LDA 生成候选、用物理锚即提即验、确定性排序，最后给出可下载的统一设计包 JSON。</p>"
          + "<p>这就是「生成与判决分离」：AI 生成候选，物理定律当法官。</p>",
      sel: "#runDesignOutcome", parent: true
    },
    {
      title: "③ 版图 → DRC → 仿真 流水线",
      body: "<p>「版图 → DRC → 仿真 流水线」一键贯通：器件参数 → GDS 版图（SVG 预览）→ 可制造性 DRC 自查 "
          + "→ FDTD 仿真 neff → 物理锚验收。</p>"
          + "<p>从设计意图到「可制造 + 已仿真验收」的版图，一条命令走完。</p>",
      sel: "#runLp", parent: true
    },
    {
      title: "④ 验证：物理定律当法官",
      body: "<p>「验证裁判控制台」选候选求解器、点 <b>运行验证</b>：真调 LDA harness，用物理定律锚逐题比对，"
          + "给出 PASS / FAIL 死标量。</p>"
          + "<p>🔴 这是 LDA 的护城河——判决落非 AI ground，可被外部 curl 复现验货。</p>",
      sel: "#runVerify", parent: true
    },
    {
      title: "⑤ 智能体客服：随时提问 + 留资",
      body: "<p>右下角蓝色气泡是 <b>LDA 智能体客服</b>：解答产品定位、验证红线、光子/量子能力、上手方式、"
          + "开源与商用、能力边界等问题；也能留姓名+公司+邮箱安排专人对接。</p>"
          + "<p>卡住时，直接问它。</p>",
      sel: "div[title=\"LDA 智能体客服\"]"
    },
    {
      title: "完成 · 你已走完主线",
      body: "<p>✅ <b>设计 → 仿真/版图 → 验证</b>，这条闭环你已经看到了。</p>"
          + "<p>想深入了解：点底部「技术白皮书」下载，或访问 <b>关于 LDA</b> 看完整产品说明与验证账本；"
          + "右下角蓝色气泡随时帮你。</p>"
          + "<p style='color:" + C.mut + ";font-size:12px'>提示：本引导可重复观看——点左下角「🎯 3分钟引导」随时重开。</p>",
      sel: null
    }
  ];

  // ============================ 状态 / DOM ============================
  var active = false, idx = 0;
  var blk, hole, tip, tipHead, tipTitle, tipBody, bar, dotsBox, prevBtn, nextBtn;

  function resolve(s) {
    if (!s.sel) return null;
    var e = document.querySelector(s.sel);
    if (!e) return null;
    if (s.parent && e.closest) {
      var p = e.closest(".sec");
      return p || e;
    }
    return e;
  }

  function build() {
    if (blk) return;
    blk = el("div", "position:fixed;inset:0;z-index:2147482999;background:transparent;");
    hole = el("div", "position:fixed;z-index:2147483001;pointer-events:none;display:none;" +
      "border:2px solid " + C.accent + ";box-shadow:0 0 0 9999px " + C.dim + ";");
    tip = el("div", "position:fixed;z-index:2147483002;width:344px;max-width:calc(100vw - 20px);" +
      "display:none;background:" + C.panel + ";border:1px solid " + C.line + ";border-radius:14px;" +
      "box-shadow:0 12px 48px rgba(4,10,30,.6);color:" + C.txt + ";" +
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;font-size:13px;");
    tip.innerHTML =
      '<div style="padding:10px 14px;border-bottom:1px solid ' + C.line + ';display:flex;align-items:center;justify-content:space-between">' +
        '<span id="gHead" style="color:' + C.mut + ';font-size:11px"></span>' +
        '<span id="gClose" style="cursor:pointer;color:' + C.mut + ';font-size:18px;line-height:1">&times;</span>' +
      '</div>' +
      '<div style="height:3px;background:' + C.line + '"><div id="gBar" style="height:100%;width:0;background:' + C.accent + ';transition:width .25s"></div></div>' +
      '<div style="padding:14px 16px">' +
        '<div id="gTitle" style="font-size:15px;font-weight:700;margin-bottom:8px;color:' + C.txt + '"></div>' +
        '<div id="gBody" style="line-height:1.65;color:' + C.txt + '"></div>' +
      '</div>' +
      '<div style="padding:10px 14px 14px;display:flex;align-items:center;gap:8px;border-top:1px solid ' + C.line + '">' +
        '<span id="gDots" style="display:flex;gap:6px"></span>' +
        '<span style="flex:1"></span>' +
        '<button id="gSkip" style="background:transparent;color:' + C.mut + ';border:0;cursor:pointer;font-size:12px;padding:6px 8px">跳过</button>' +
        '<button id="gPrev" style="background:' + C.panel2 + ';color:' + C.txt + ';border:1px solid ' + C.line + ';border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer">上一步</button>' +
        '<button id="gNext" style="background:' + C.accent2 + ';color:#04122a;border:0;border-radius:8px;padding:6px 14px;font-weight:700;font-size:13px;cursor:pointer">下一步 →</button>' +
      '</div>';
    document.body.appendChild(blk);
    document.body.appendChild(hole);
    document.body.appendChild(tip);

    tipHead = tip.querySelector("#gHead");
    tipTitle = tip.querySelector("#gTitle");
    tipBody = tip.querySelector("#gBody");
    bar = tip.querySelector("#gBar");
    dotsBox = tip.querySelector("#gDots");
    prevBtn = tip.querySelector("#gPrev");
    nextBtn = tip.querySelector("#gNext");

    tip.querySelector("#gClose").onclick = skip;
    tip.querySelector("#gSkip").onclick = skip;
    prevBtn.onclick = function () { if (idx > 0) showStep(idx - 1); };
    nextBtn.onclick = function () { if (idx < STEPS.length - 1) showStep(idx + 1); else finish(); };

    document.addEventListener("keydown", function (e) {
      if (!active) return;
      if (e.key === "Escape") skip();
      else if (e.key === "ArrowRight") { if (idx < STEPS.length - 1) showStep(idx + 1); }
      else if (e.key === "ArrowLeft" && idx > 0) showStep(idx - 1);
    });

    var rp = function () { if (active) position(); };
    window.addEventListener("scroll", rp, true);
    window.addEventListener("resize", rp);
  }

  function renderContent(s) {
    tipHead.textContent = "第 " + (idx + 1) + " / " + STEPS.length + " 步 · 约 3 分钟";
    tipTitle.textContent = s.title;
    tipBody.innerHTML = s.body;
    bar.style.width = ((idx + 1) / STEPS.length * 100) + "%";
    dotsBox.innerHTML = "";
    STEPS.forEach(function (_, k) {
      var d = el("span", "width:8px;height:8px;border-radius:50%;display:inline-block;" +
        (k === idx ? "background:" + C.accent : "background:" + C.line), "");
      dotsBox.appendChild(d);
    });
    prevBtn.style.visibility = idx === 0 ? "hidden" : "visible";
    nextBtn.textContent = idx === STEPS.length - 1 ? "完成 ✓" : "下一步 →";
  }

  function position() {
    if (!active || !tip) return;
    var s = STEPS[idx];
    var target = resolve(s);
    var rect = null;
    if (target) {
      var r = target.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) rect = r;
    }
    if (rect) {
      var pad = 8;
      hole.style.display = "block";
      hole.style.top = (rect.top - pad) + "px";
      hole.style.left = (rect.left - pad) + "px";
      hole.style.width = (rect.width + pad * 2) + "px";
      hole.style.height = (rect.height + pad * 2) + "px";
      hole.style.borderRadius = "14px";
    } else {
      hole.style.display = "none";
    }
    tip.style.visibility = "hidden";
    tip.style.display = "block";
    var tw = tip.offsetWidth, th = tip.offsetHeight;
    var vw = window.innerWidth, vh = window.innerHeight;
    var top, left;
    if (rect) {
      top = rect.bottom + 14;
      if (top + th > vh - 10) top = rect.top - th - 14;
      if (top < 10) top = 10;
      left = rect.left + rect.width / 2 - tw / 2;
    } else {
      top = vh / 2 - th / 2;
      left = vw / 2 - tw / 2;
    }
    left = Math.max(10, Math.min(left, vw - tw - 10));
    top = Math.max(10, Math.min(top, vh - th - 10));
    tip.style.top = top + "px";
    tip.style.left = left + "px";
    tip.style.visibility = "visible";
  }

  function showStep(i) {
    idx = i;
    var s = STEPS[i];
    renderContent(s);
    var target = resolve(s);
    if (target) {
      try { target.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (e) {}
      setTimeout(position, 120);
      setTimeout(position, 440);
    } else {
      setTimeout(position, 30);
    }
  }

  function start() {
    active = true;
    build();
    blk.style.display = "block";
    hole.style.display = "none";
    tip.style.display = "block";
    showStep(0);
  }

  function finish() {
    active = false;
    if (blk) blk.style.display = "none";
    if (hole) hole.style.display = "none";
    if (tip) tip.style.display = "none";
    try { localStorage.setItem(KEY, "1"); } catch (e) {}
  }

  function skip() { finish(); }

  function buildLauncher() {
    var b = el("div", "position:fixed;left:18px;bottom:18px;z-index:2147482998;" +
      "background:" + C.accent2 + ";color:#04122a;font:700 13px Arial,'Microsoft YaHei',sans-serif;" +
      "padding:9px 14px;border-radius:999px;cursor:pointer;box-shadow:0 6px 20px rgba(20,40,90,.35);user-select:none");
    b.textContent = "🎯 3分钟引导";
    b.title = "重新观看 LDA 上手引导";
    b.onclick = function () { start(); };
    document.body.appendChild(b);
  }

  // ============================ 启动 ============================
  function boot() {
    buildLauncher();
    var forced = /[?&]guide=1\b/.test(location.search);
    var done = false;
    try { done = localStorage.getItem(KEY) === "1"; } catch (e) {}
    if (forced || !done) setTimeout(start, forced ? 300 : 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
