/*
 * LDA 智能体客服前台组件（Craft 模式生成）
 * 浮动气泡 + 对话面板；调用 /api/agent/chat（解答问题 + 收集线索）。
 * 自带配色（深底浅字），在明/暗主题页均清晰；不依赖页面 CSS 变量。
 * 引导型升级：面板内置「🚀 引导」入口 + 引导 banner（对话式带路），
 * 并与 guide_widget.js 的 window.LDA_GUIDE 联动打开对应步聚光灯。
 */
(function () {
  "use strict";
  var API = "/api/agent/chat";
  // 配色（自包含，跨主题可读）
  var C = {
    panel: "#0e1525", panel2: "#16203a", line: "#2a3658",
    txt: "#e8eefb", mut: "#9fb0d4", accent: "#3b82f6", green: "#22c55e",
    bubble: "#3b82f6"
  };

  function el(tag, style, html) {
    var e = document.createElement(tag);
    if (style) e.setAttribute("style", style);
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  var history = [];
  var guideState = { active: false, step: 0, total: 7 };
  var GUIDE_CTA = "🚀 带我 3 分钟上手";

  function buildWidget() {
    // 呼吸脉冲动画（提升可见性，避免被忽略）
    try {
      var st = document.createElement("style");
      st.textContent = "@keyframes csPulse{0%{box-shadow:0 0 0 0 rgba(59,130,246,.55)}" +
        "70%{box-shadow:0 0 0 18px rgba(59,130,246,0)}100%{box-shadow:0 0 0 0 rgba(59,130,246,0)}}";
      document.head.appendChild(st);
    } catch (e) {}

    // 气泡（z-index 拉到极大值，确保不被任何页面浮层/遮罩遮挡）
    var bubble = el("div",
      "position:fixed;right:18px;bottom:18px;z-index:2147483000;width:56px;height:56px;" +
      "border-radius:50%;background:" + C.bubble + ";color:#fff;cursor:pointer;" +
      "display:flex;align-items:center;justify-content:center;font-size:24px;" +
      "box-shadow:0 6px 20px rgba(20,40,90,.35);user-select:none;animation:csPulse 2.4s infinite");
    bubble.textContent = "💬";
    bubble.title = "LDA 智能体客服";

    // 面板
    var panel = el("div",
      "position:fixed;right:18px;bottom:86px;z-index:2147483000;width:340px;max-width:calc(100vw - 36px);" +
      "height:460px;max-height:calc(100vh - 110px);background:" + C.panel +
      ";border:1px solid " + C.line + ";border-radius:14px;overflow:hidden;" +
      "display:none;flex-direction:column;box-shadow:0 10px 40px rgba(10,20,40,.45);" +
      "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif");
    panel.innerHTML =
      '<div style="padding:12px 14px;background:' + C.panel2 + ';border-bottom:1px solid ' + C.line + ';' +
      'display:flex;align-items:center;justify-content:space-between">' +
      '<b style="color:' + C.txt + ';font-size:14px">LDA 智能体客服</b>' +
      '<span style="color:' + C.mut + ';font-size:11px">解答 · 留资</span>' +
      '<span id="csGuideCta" style="cursor:pointer;color:' + C.accent + ';font-size:12px;margin-left:6px">🚀 引导</span>' +
      '<span id="csClose" style="cursor:pointer;color:' + C.mut + ';font-size:18px">&times;</span></div>' +
      '<div id="csGuideBanner" style="display:none;padding:10px 12px;border-bottom:1px solid ' + C.line + ';background:' + C.panel2 + '">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">' +
      '<b id="csGuideTitle" style="color:' + C.txt + ';font-size:13px">引导</b>' +
      '<span id="csGuideProg" style="color:' + C.mut + ';font-size:11px">1/7</span></div>' +
      '<div id="csGuideIntro" style="color:' + C.txt + ';font-size:12px;line-height:1.55;white-space:pre-wrap;max-height:128px;overflow:auto"></div>' +
      '<div id="csGuideTip" style="color:' + C.mut + ';font-size:11px;margin-top:6px;line-height:1.5"></div>' +
      '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">' +
      '<button id="csGuideVisual" style="background:' + C.accent + ';color:#fff;border:0;border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer">🎯 可视化引导</button>' +
      '<button id="csGuidePrev" style="background:' + C.panel + ';color:' + C.txt + ';border:1px solid ' + C.line + ';border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer">上一步</button>' +
      '<button id="csGuideNext" style="background:' + C.accent + ';color:#fff;border:0;border-radius:8px;padding:6px 12px;font-weight:700;font-size:12px;cursor:pointer">下一步 →</button>' +
      '<button id="csGuideExit" style="background:transparent;color:' + C.mut + ';border:0;cursor:pointer;font-size:12px;padding:6px 8px">退出</button>' +
      '</div></div>' +
      '<div id="csBody" style="flex:1;overflow:auto;padding:12px 14px;color:' + C.txt + ';font-size:13px;line-height:1.6"></div>' +
      '<div id="csSug" style="display:flex;gap:6px;flex-wrap:wrap;padding:0 12px 8px"></div>' +
      '<div id="csLead" style="display:none;padding:0 12px 8px;border-top:1px solid ' + C.line + ';margin-top:2px;padding-top:8px">' +
      '<div style="color:' + C.mut + ';font-size:12px;margin-bottom:6px">留个联系方式，我们安排专人对接：</div>' +
      '<input id="csName" placeholder="姓名 *" style="' + _IN() + '">' +
      '<input id="csCompany" placeholder="公司/单位" style="' + _IN() + '">' +
      '<input id="csEmail" placeholder="邮箱 *" style="' + _IN() + '">' +
      '<input id="csPhone" placeholder="电话/微信" style="' + _IN() + '">' +
      '<input id="csNeed" placeholder="需求（选填）" style="' + _IN() + '">' +
      '<button id="csLeadSubmit" style="margin-top:6px;width:100%;background:' + C.accent +
      ';color:#fff;border:0;border-radius:8px;padding:8px;font-size:13px;cursor:pointer">提交联系</button>' +
      '</div>' +
      '<div style="display:flex;gap:8px;padding:8px 12px;border-top:1px solid ' + C.line + '">' +
      '<input id="csInput" placeholder="输入问题，或点「留资」…" style="' + _IN() + ';flex:1">' +
      '<button id="csSend" style="background:' + C.accent + ';color:#fff;border:0;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer">发送</button>' +
      '</div>' +
      '<div style="padding:0 12px 8px;display:flex;justify-content:space-between">' +
      '<span id="csLeadToggle" style="color:' + C.accent + ';font-size:12px;cursor:pointer">留个联系方式 ▸</span>' +
      '<span style="color:' + C.mut + ';font-size:11px">LDA · 开源 Agent 原生</span></div>';

    document.body.appendChild(bubble);
    document.body.appendChild(panel);

    function _IN() {
      return "background:" + C.panel2 + ";color:" + C.txt + ";border:1px solid " + C.line +
        ";border-radius:8px;padding:7px 9px;font-size:13px;margin:4px 0;width:100%;box-sizing:border-box";
    }

    var body = panel.querySelector("#csBody");
    function addMsg(role, text) {
      var m = el("div",
        "margin:8px 0;padding:8px 10px;border-radius:10px;max-width:88%;" +
        (role === "user"
          ? "margin-left:auto;background:" + C.accent + ";color:#fff"
          : "background:" + C.panel2 + ";color:" + C.txt + ";border:1px solid " + C.line),
        esc(text));
      body.appendChild(m);
      body.scrollTop = body.scrollHeight;
    }

    function showSug(sugs) {
      var box = panel.querySelector("#csSug");
      box.innerHTML = "";
      (sugs || []).forEach(function (s) {
        var c = el("span",
          "font-size:12px;padding:4px 9px;border-radius:999px;background:" + C.panel2 +
          ";border:1px solid " + C.line + ";color:" + C.accent + ";cursor:pointer", esc(s));
        c.onclick = function () { send(s); };
        box.appendChild(c);
      });
    }

    function send(text) {
      text = (text || "").trim();
      if (text === GUIDE_CTA) { startGuide(); return; }
      var input = panel.querySelector("#csInput");
      if (!text && input) text = input.value.trim();
      if (!text) return;
      if (input) input.value = "";
      addMsg("user", text);
      history.push({ role: "user", content: text });
      // 乐观占位
      var wait = addMsg("bot", "…");
      var payload = { message: text, history: history.slice(-6) };
      if (guideState.active) payload.guide_step = guideState.step;
      fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          body.removeChild(wait);
          addMsg("bot", d.reply || "（无回复）");
          history.push({ role: "assistant", content: d.reply || "" });
          showSug(d.suggestions);
          if (d.lead_captured) {
            var lt = panel.querySelector("#csLeadToggle");
            if (lt) lt.textContent = "✓ 已收到您的联系方式";
          }
        })
        .catch(function () {
          body.removeChild(wait);
          addMsg("bot", "网络异常，请稍后重试。");
        });
    }

    function submitLead() {
      var g = function (id) { return panel.querySelector(id).value.trim(); };
      var name = g("#csName"), email = g("#csEmail");
      if (!name && !email) {
        alert("请至少填写姓名或邮箱");
        return;
      }
      var payload = {
        name: name, company: g("#csCompany"), email: email,
        phone: g("#csPhone"), need: g("#csNeed"), history: history.slice(-6)
      };
      addMsg("user", "（提交联系：）" + (name || email));
      var wait = addMsg("bot", "…");
      fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          body.removeChild(wait);
          addMsg("bot", d.reply || "已收到，我们会尽快联系您。");
          history.push({ role: "assistant", content: d.reply || "" });
          panel.querySelector("#csLead").style.display = "none";
        })
        .catch(function () {
          body.removeChild(wait);
          addMsg("bot", "提交失败，请稍后重试或直接邮件到开源仓库。");
        });
    }

    // 引导模式（智能体做成引导型）：对话式带路 + 与 guide_widget 聚光灯联动
    function startGuide() {
      guideState.active = true; guideState.step = 0;
      fetch(API, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guide_cmd: "start", history: [] })
      }).then(function (r) { return r.json(); })
        .then(function (d) { if (d.guide) renderGuide(d.guide); })
        .catch(function () { addMsg("bot", "引导加载失败，请稍后重试。"); });
    }
    function renderGuide(g) {
      guideState.step = g.step; guideState.total = g.total;
      var banner = panel.querySelector("#csGuideBanner");
      if (banner) banner.style.display = "block";
      var t = panel.querySelector("#csGuideTitle"); if (t) t.textContent = g.title;
      var p = panel.querySelector("#csGuideProg"); if (p) p.textContent = (g.step + 1) + "/" + g.total;
      var intro = panel.querySelector("#csGuideIntro"); if (intro) intro.textContent = g.intro;
      var tip = panel.querySelector("#csGuideTip"); if (tip) tip.textContent = g.tip;
      var prev = panel.querySelector("#csGuidePrev"); if (prev) prev.style.visibility = g.step === 0 ? "hidden" : "visible";
      var next = panel.querySelector("#csGuideNext"); if (next) next.textContent = g.step === g.total - 1 ? "完成 ✓" : "下一步 →";
    }
    function fetchGuideStep(step) {
      fetch(API, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guide_step: step, message: "", history: history.slice(-6) })
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.guide) renderGuide(d.guide);
          if (d.reply) addMsg("bot", d.reply);
          if (d.lead_captured) { var lt = panel.querySelector("#csLeadToggle"); if (lt) lt.textContent = "✓ 已收到您的联系方式"; }
        })
        .catch(function () { addMsg("bot", "引导加载失败，请稍后重试。"); });
    }
    function guideNext() {
      if (guideState.step >= guideState.total - 1) { exitGuide(); return; }
      fetchGuideStep(guideState.step + 1);
    }
    function guidePrev() { if (guideState.step > 0) fetchGuideStep(guideState.step - 1); }
    function exitGuide() {
      guideState.active = false;
      var banner = panel.querySelector("#csGuideBanner"); if (banner) banner.style.display = "none";
    }
    function openVisual() {
      if (window.LDA_GUIDE && window.LDA_GUIDE.goTo) window.LDA_GUIDE.goTo(guideState.step);
    }

    // 事件
    bubble.onclick = function () {
      panel.style.display = panel.style.display === "flex" ? "none" : "flex";
      if (panel.style.display === "flex" && !body.dataset.greeted) {
        body.dataset.greeted = "1";
        if (window.LDA_ONBOARD) window.LDA_ONBOARD.markStep(3);
        addMsg("bot", "您好，我是 LDA 智能体客服 👋 可解答产品定位、验证红线、光子/量子能力、"
          + "上手方式、开源与商用、能力边界等问题；也可直接留姓名+公司+邮箱安排专人对接。");
        showSug(["产品是什么", "验证为什么可信", "光子能力", "量子能力",
          "如何快速上手", "价格与商用", "能力边界", "留个联系方式", "🚀 带我 3 分钟上手"]);
      }
    };
    panel.querySelector("#csClose").onclick = function () { panel.style.display = "none"; };
    panel.querySelector("#csSend").onclick = function () { send(""); };
    panel.querySelector("#csInput").addEventListener("keydown", function (e) {
      if (e.key === "Enter") send("");
    });
    panel.querySelector("#csLeadToggle").onclick = function () {
      var ld = panel.querySelector("#csLead");
      ld.style.display = ld.style.display === "none" ? "block" : "none";
    };
    panel.querySelector("#csLeadSubmit").onclick = submitLead;
    panel.querySelector("#csGuideCta").onclick = startGuide;
    panel.querySelector("#csGuideVisual").onclick = openVisual;
    panel.querySelector("#csGuidePrev").onclick = guidePrev;
    panel.querySelector("#csGuideNext").onclick = guideNext;
    panel.querySelector("#csGuideExit").onclick = exitGuide;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildWidget);
  } else {
    buildWidget();
  }
})();
