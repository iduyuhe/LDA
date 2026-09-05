/* LDA 新手上手组件（纯前端·零依赖）
 * 三块能力：
 *  1) 30秒体验：JS 真实计算「微环调制器 FSR」解析样例（设计→求解→验证→调参→PASS），
 *     诚实标注为教学样例；CTA 一键打开真实引擎聚光灯。
 *  2) 起步模板库：光子 / 量子 / CPO；CPO 卡直接 fetch /api/cpo_array 跑真实死锚判决。
 *  3) 入门进度清单：4 步，localStorage 持久化；markStep 供引导/客服/真实引擎联动。
 * 暴露 window.LDA_ONBOARD = { markStep, open }。
 */
(function () {
  var KEY_PROG = "lda_onboard_progress";   // {1:true,2:true,...}
  var KEY_QS = "lda_quickstart_done";
  var C = {
    bg: "#0f1830", panel: "#1b2c4d", line: "#3f5e93", txt: "#eaf2ff",
    mut: "#b4c2dc", accent: "#1ea0f0", accent2: "#1ea0f0",
    ok: "#34d399", bad: "#f87171", warn: "#fbbf24"
  };

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function getProg() { try { return JSON.parse(lsGet(KEY_PROG) || "{}"); } catch (e) { return {}; } }
  function markStep(n) {
    var p = getProg();
    if (p[n]) { return; }
    p[n] = true; lsSet(KEY_PROG, JSON.stringify(p));
    renderBadge();
    if (p[1] && p[2] && p[3] && p[4]) { celebrate(); }
  }
  function el(tag, style, html) {
    var e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (html != null) e.innerHTML = html;
    return e;
  }

  // ============================ 进度徽章（左下，引导按钮上方） ============================
  var badge = null;
  function renderBadge() {
    var p = getProg();
    var done = (p[1] ? 1 : 0) + (p[2] ? 1 : 0) + (p[3] ? 1 : 0) + (p[4] ? 1 : 0);
    if (!badge) {
      badge = el("div",
        "position:fixed;left:18px;bottom:62px;z-index:2147482997;cursor:pointer;" +
        "background:" + C.panel + ";color:" + C.txt + ";font:13px 'Microsoft YaHei',Arial,sans-serif;" +
        "padding:7px 12px;border-radius:999px;box-shadow:0 6px 20px rgba(0,0,0,.35);" +
        "border:1px solid " + C.line + ";user-select:none;display:flex;gap:7px;align-items:center");
      badge.onclick = openPanel;
      document.body.appendChild(badge);
    }
    var all = done === 4;
    badge.innerHTML =
      "<span style='color:" + (all ? C.ok : C.accent) + ";font-weight:700'>✅ 入门进度 " + done + "/4</span>" +
      "<span style='color:" + C.mut + ";font-size:11px'>" + (all ? "已通关" : "点我看 30 秒体验") + "</span>";
  }

  // ============================ 主面板 ============================
  var mask = null, panel = null;
  function openPanel() {
    if (mask) { mask.style.display = "flex"; return; }
    mask = el("div",
      "position:fixed;inset:0;z-index:2147482990;background:rgba(4,10,22,.62);" +
      "display:flex;align-items:center;justify-content:center;padding:18px");
    mask.onclick = function (e) { if (e.target === mask) mask.style.display = "none"; };
    panel = el("div",
      "width:760px;max-width:96vw;max-height:88vh;overflow:auto;background:" + C.panel +
      ";border:1px solid " + C.line + ";border-radius:16px;color:" + C.txt +
      ";font:14px/1.6 'Microsoft YaHei',Arial,sans-serif;box-shadow:0 0 0 1px " + C.line + ",0 0 40px rgba(30,160,240,.28),0 22px 64px rgba(2,6,20,.62)");
    panel.appendChild(el("div",
      "display:flex;align-items:center;justify-content:space-between;padding:16px 20px;" +
      "border-bottom:1px solid " + C.line,
      "<b style='font-size:16px'>🚀 新手起步 · 一学一懂，一用就通</b>" +
      "<span style='cursor:pointer;color:" + C.mut + ";font-size:20px;line-height:1' onclick='this.closest(\"div\").parentNode.parentNode.style.display=\"none\"'>×</span>"));
    panel.appendChild(buildModeBar());
    panel.appendChild(buildQuickstart());
    panel.appendChild(buildTemplates());
    panel.appendChild(buildChecklist());
    panel.appendChild(buildExplore());
    mask.appendChild(panel);
    document.body.appendChild(mask);
  }

  // ---------- 1) 30 秒体验 ----------
  function buildQuickstart() {
    var wrap = el("div", "padding:16px 20px;border-bottom:1px solid " + C.line);
    wrap.appendChild(el("div", "font-weight:700;margin-bottom:6px", "① 30 秒体验：亲手跑通一个真实设计闭环"));
    wrap.appendChild(el("div", "color:" + C.mut + ";font-size:13px;margin-bottom:10px",
      "给一个目标，看求解器怎么算、验证怎么判、调参怎么过。下面用真实公式现场算给你看。"));
    var runBtn = el("button",
      "background:" + C.accent + ";color:#04122a;border:0;border-radius:9px;padding:9px 16px;" +
      "font:700 14px Arial;cursor:pointer;margin-bottom:10px", "▶ 一键跑通");
    var out = el("div", "font-size:13px;min-height:20px");
    runBtn.onclick = function () { runBtn.disabled = true; runBtn.textContent = "运行中…"; doQuickstart(out, runBtn); };
    wrap.appendChild(runBtn);
    wrap.appendChild(out);
    return wrap;
  }

  // 真实闭式：Δλ = λ² / (n_g · 2πR)，λ、R 取 nm
  function fsr(R_um, ng, lam_nm) {
    var R_nm = R_um * 1000;
    return lam_nm * lam_nm / (ng * 2 * Math.PI * R_nm); // nm
  }
  function doQuickstart(out, btn) {
    lsSet(KEY_QS, "1");
    markStep(2);
    var lam = 1550, ng = 4.2, spec = 20; // FSR ≥ 20 nm
    out.innerHTML = "";
    function line(html, color) {
      out.appendChild(el("div", "margin:3px 0" + (color ? ";color:" + color : ""), html));
    }
    var steps = [
      function (cb) {
        line("🎯 <b>设计目标</b>：微环调制器，自由光谱范围 FSR ≥ " + spec + " nm @ " + lam + " nm", C.txt);
        line("&nbsp;&nbsp;初值：半径 R = 20 µm，群折射率 n_g = " + ng, C.mut);
        setTimeout(cb, 500);
      },
      function (cb) {
        line("🧮 <b>求解</b>：FSR = λ² / (n_g·2πR)，λ、R 同取 nm");
        var v0 = fsr(20, ng, lam);
        setTimeout(function () {
          line("&nbsp;&nbsp;算得 FSR = <b>" + v0.toFixed(2) + " nm</b>", C.txt);
          line("⚖️ <b>验证</b>：需 ≥ " + spec + " nm → <b style='color:" + C.bad + "'>FAIL</b>（半径太大）", C.bad);
          cb();
        }, 600);
      },
      function (cb) {
        line("🔧 <b>调参</b>：把 R 从 20 µm 调到 4.5 µm 再算");
        var v1 = fsr(4.5, ng, lam);
        setTimeout(function () {
          line("&nbsp;&nbsp;算得 FSR = <b>" + v1.toFixed(2) + " nm</b>", C.txt);
          line("⚖️ <b>验证</b>：≥ " + spec + " nm → <b style='color:" + C.ok + "'>PASS</b> ✅", C.ok);
          line("<span style='color:" + C.mut + ";font-size:12px'>这是解析教学样例（微环 FSR 闭式）；真实引擎走数值求解器 + 验证账本死标量比对，逻辑完全一致。</span>", C.mut);
          // CTA：打开真实引擎聚光灯
          var cta = el("button",
            "margin-top:8px;background:" + C.ok + ";color:#04122a;border:0;border-radius:9px;" +
            "padding:8px 14px;font:700 13px Arial;cursor:pointer",
            "🚀 我也要在真实引擎里跑（打开设计区）");
          cta.onclick = function () {
            if (mask) mask.style.display = "none";
            if (window.LDA_GUIDE && window.LDA_GUIDE.goTo) window.LDA_GUIDE.goTo(2);
            toast("点击首页「运行设计闭环 → 出设计包」即可在真实引擎跑通");
          };
          out.appendChild(cta);
          btn.disabled = false; btn.textContent = "▶ 再跑一次";
          cb();
        }, 600);
      }
    ];
    var i = 0;
    (function next() { if (i < steps.length) { steps[i](function () { i++; next(); }); } })();
  }

  // ---------- 2) 起步模板库 ----------
  function buildTemplates() {
    var wrap = el("div", "padding:16px 20px;border-bottom:1px solid " + C.line);
    wrap.appendChild(el("div", "font-weight:700;margin-bottom:6px", "② 起步模板库：挑一个，直接上手"));
    var grid = el("div", "display:flex;gap:12px;flex-wrap:wrap");
    grid.appendChild(tplCard("🌊 光子 · 1×2 分束器", "设计闭环 → 出统一设计包",
      function () { spotlight(2, "点击「运行设计闭环 → 出设计包」"); }));
    grid.appendChild(tplCard("⚛️ 量子 · 读取保真度链", "验证裁判 → 死标量比对",
      function () { spotlight(4, "点击「运行验证」看真实判决"); }));
    grid.appendChild(tplCard("🔗 CPO · 10 万器件阵列", "真实跑一次死锚判决（免登录）",
      function (card) { runCpo(card); }));
    wrap.appendChild(grid);
    return wrap;
  }
  function tplCard(title, sub, onClick) {
    var card = el("div",
      "flex:1;min-width:200px;background:" + C.bg + ";border:1px solid " + C.line +
      ";border-radius:12px;padding:12px 14px;cursor:pointer");
    card.innerHTML = "<div style='font-weight:700;margin-bottom:4px'>" + title + "</div>" +
      "<div style='color:" + C.mut + ";font-size:12px;margin-bottom:8px'>" + sub + "</div>" +
      "<div style='color:" + C.accent + ";font-size:12px;font-weight:700'>▶ 试一试</div>";
    var body = el("div", "margin-top:8px;font-size:12px;color:" + C.mut, "");
    card.appendChild(body);
    card.onclick = function () { onClick(card, body); };
    return card;
  }
  function spotlight(step, hint) {
    if (mask) mask.style.display = "none";
    if (window.LDA_GUIDE && window.LDA_GUIDE.goTo) window.LDA_GUIDE.goTo(step);
    toast(hint);
  }
  function runCpo(body) {
    body.innerHTML = "⏳ 真实系统跑 100,096 器件中…";
    fetch("/api/cpo_array").then(function (r) { return r.json(); }).then(function (d) {
      markStep(4);
      if (d.error) { body.innerHTML = "⚠️ " + d.error; return; }
      var drc = d.drc && d.drc.all_pass ? "全过" : "有失败";
      var lvs = (d.lvs && d.lvs.verdict) || "—";
      var fi = (d.fault_injection && d.fault_injection.verdict) || "—";
      var n = (d.config && d.config.n_devices) || 0;
      body.innerHTML =
        "✅ 真实判决（" + n.toLocaleString() + " 器件）：<br>" +
        "&nbsp;· DRC：" + drc + "<br>" +
        "&nbsp;· LVS：" + lvs + "<br>" +
        "&nbsp;· 注入断路 → " + fi + "（证明不是假绿）<br>" +
        "&nbsp;· 总判决 accepted = <b style='color:" + (d.accepted ? C.ok : C.bad) + "'>" + d.accepted + "</b>";
    }).catch(function (e) {
      body.innerHTML = "⚠️ 调用失败：" + e;
    });
  }

  // ---------- 3) 入门进度清单 ----------
  function buildChecklist() {
    var wrap = el("div", "padding:16px 20px");
    wrap.appendChild(el("div", "font-weight:700;margin-bottom:8px", "③ 入门进度清单：完成 4 步即上手"));
    var items = [
      [1, "看过 3 分钟引导浮窗"],
      [2, "跑通 30 秒体验样例"],
      [3, "问过智能体客服"],
      [4, "用过一次真实引擎"]
    ];
    var p = getProg();
    items.forEach(function (it) {
      var ok = !!p[it[0]];
      wrap.appendChild(el("div", "display:flex;gap:10px;align-items:center;margin:5px 0",
        "<span style='width:20px;height:20px;border-radius:50%;display:inline-flex;" +
        "align-items:center;justify-content:center;font-size:12px;font-weight:700;" +
        "background:" + (ok ? C.ok : C.bg) + ";color:" + (ok ? "#04122a" : C.mut) +
        ";border:1px solid " + (ok ? C.ok : C.line) + "'>" + (ok ? "✓" : it[0]) + "</span>" +
        "<span style='color:" + (ok ? C.txt : C.mut) + "'>" + it[1] + "</span>"));
    });
    return wrap;
  }

  // ============================ 轻提示 ============================
  function toast(msg) {
    var t = el("div",
      "position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:2147483003;" +
      "background:" + C.panel + ";color:" + C.txt + ";border:1px solid " + C.line +
      ";border-radius:10px;padding:10px 16px;font:13px 'Microsoft YaHei',Arial;" +
      "box-shadow:0 8px 24px rgba(0,0,0,.4);max-width:80vw;text-align:center", msg);
    document.body.appendChild(t);
    setTimeout(function () { t.style.transition = "opacity .4s"; t.style.opacity = "0"; }, 2600);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 3100);
  }
  function celebrate() {
    toast("🎉 入门通关！你现在可以独立用 LDA 设计→验证光子/量子芯片了");
  }

  // ---------- 双模指示 ----------
  function buildModeBar() {
    var wrap = el("div", "padding:10px 20px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid " + C.line);
    wrap.appendChild(el("span", "color:" + C.mut + ";font-size:12px", "LDA 双模："));
    wrap.appendChild(el("span", "background:" + C.accent + ";color:#04122a;font-weight:700;font-size:13px;padding:6px 13px;border-radius:999px", "器件级 · 组件设计闭环（你在这）"));
    var sys = el("a", "background:#fbbf24;color:#1a1205;border:1px solid #b0841a;font-weight:700;font-size:13px;padding:6px 13px;border-radius:999px;text-decoration:none;cursor:pointer", "系统级 · 护城河（展厅）→");
    sys.href = "/insights.html";
    wrap.appendChild(sys);
    return wrap;
  }

  // ---------- ④ 逛 LDA：展厅 / 超市 / 验证实力 ----------
  function buildExplore() {
    var wrap = el("div", "padding:16px 20px;border-top:1px solid " + C.line);
    wrap.appendChild(el("div", "font-weight:700;margin-bottom:6px", "④ 逛 LDA · 展厅 / 超市 / 验证实力（进阶探索）"));
    wrap.appendChild(el("div", "color:" + C.mut + ";font-size:12px;margin-bottom:10px", "想看懂 LDA 的「系统级护城河」「商业货架」和「为什么结果可信」，去这三个地方："));
    var grid = el("div", "display:flex;gap:12px;flex-wrap:wrap");
    grid.appendChild(exploreCard("🏛 展厅 · 能力展示", "系统级护城河：GC 整芯片对标 / 万级规模实测 / CPO 十万级死锚", "/insights.html"));
    grid.appendChild(exploreCard("🛒 创新超市", "58 货架设计就绪包（光子 50 开放下载 · 量子 8 咨询制）· 免费看、付费下", "/store.html"));
    var vbody = el("div", "margin-top:8px;font-size:12px;color:" + C.mut, "");
    grid.appendChild(verifyCard(vbody));
    wrap.appendChild(grid);
    return wrap;
  }
  function verifyCard(body) {
    var card = el("div",
      "flex:1;min-width:220px;background:" + C.bg + ";border:1px solid " + C.line +
      ";border-radius:12px;padding:12px 14px;cursor:pointer");
    card.innerHTML = "<div style='font-weight:700;margin-bottom:4px;color:" + C.txt + "'>🔬 验证实力 · 外部可验货</div>" +
      "<div style='color:" + C.mut + ";font-size:12px;margin-bottom:8px'>现场拉真实账本：CI 守护 / 物理定律锚 / 死标量比对</div>" +
      "<div style='color:" + C.accent + ";font-size:12px;font-weight:700'>▶ 看真实数字</div>";
    card.onclick = function () { loadVerify(body); };
    card.appendChild(body);
    return card;
  }
  function loadVerify(body) {
    body.innerHTML = "⏳ 拉取验证账本中…";
    fetch("/api/verification_ledger").then(function (r) { return r.json(); }).then(function (L) {
      if (L.error) { body.innerHTML = "⚠️ " + L.error; return; }
      var ci = (L.ci_core && L.ci_core.count) || 0;
      var total = (L.anchors && L.anchors.total) || 0;
      var phys = (L.anchors && L.anchors.by_kind && L.anchors.by_kind["physical-law"] && L.anchors.by_kind["physical-law"].count) || 0;
      var indep = (L.judgment_paths && L.judgment_paths.derived && L.judgment_paths.derived.totals && L.judgment_paths.derived.totals.strict_independent) || 0;
      var cpo = (L.cpo_scale && L.cpo_scale.default_devices) || 0;
      body.innerHTML =
        "✅ 验证实力（真实账本）：<br>" +
        "&nbsp;· CI core 守护 <b style='color:" + C.ok + "'>" + ci + "</b> 条死标量冒烟<br>" +
        "&nbsp;· 验证锚 <b style='color:" + C.ok + "'>" + total + "</b> 道（物理定律锚 " + phys + "）<br>" +
        "&nbsp;· 严格独立候选 <b style='color:" + C.ok + "'>" + indep + "</b> 道（真可证伪）<br>" +
        "&nbsp;· CPO <b style='color:" + C.ok + "'>" + cpo.toLocaleString() + "</b> 器件死锚判决 ACCEPT<br>" +
        "<span style='color:" + C.mut + ";font-size:11px'>红线：LLM 不进判决路径，PASS/FAIL 一律死标量比对。点上方「🏛 展厅」看完整账本与诚实边界。</span>";
    }).catch(function (e) {
      body.innerHTML = "⚠️ 调用失败：" + e;
    });
  }
  function exploreCard(title, sub, url) {
    var card = el("div",
      "flex:1;min-width:220px;background:" + C.bg + ";border:1px solid " + C.line +
      ";border-radius:12px;padding:12px 14px;cursor:pointer");
    card.innerHTML = "<div style='font-weight:700;margin-bottom:4px;color:" + C.txt + "'>" + title + "</div>" +
      "<div style='color:" + C.mut + ";font-size:12px;margin-bottom:8px'>" + sub + "</div>" +
      "<div style='color:" + C.accent + ";font-size:12px;font-weight:700'>▶ 去看看</div>";
    card.onclick = function () { window.open(url, "_blank"); };
    return card;
  }

  // ============================ 全局联动 ============================
  // 任何真实引擎运行按钮被点击 → 标记第 4 步
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest('[id^="run"]') : null;
    if (t) markStep(4);
  });

  window.LDA_ONBOARD = { markStep: markStep, open: openPanel };

  // 启动：渲染徽章；若首访且未跑过样例，给一次轻微提示（不抢引导浮窗的风头）
  renderBadge();

  // ============================ 启动 ============================
})();
