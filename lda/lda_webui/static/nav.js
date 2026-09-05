/*
 * LDA 统一站点导航（Craft 模式生成）
 * 注入到 index.html / insights.html / store.html / mine.html / admin.html，
 * 提供跨页导航 + 实时会员态 + 全局登录/注册弹窗（任何页面点登录直接弹窗，
 * 不再跳转到 store.html 二次点击——历史缺陷修复）。
 * 依赖页面已定义的 CSS 变量（--panel/--line/--txt/--mut/--accent），自动跟随主题。
 */
(function () {
  "use strict";

  var STORE_TOKEN_KEY = "lda_store_token";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function currentKey() {
    var p = location.pathname.split("?")[0];
    if (p.endsWith("insights.html")) return "insights";
    if (p.endsWith("store.html")) return "store";
    if (p.endsWith("mine.html")) return "mine";
    if (p.endsWith("admin.html")) return "admin";
    if (p.endsWith("stats.html")) return "stats";
    if (p.endsWith("public.html")) return "public";
    return "home";
  }

  function link(href, label, key) {
    var on = currentKey() === key;
    var color = on ? "var(--accent)" : "var(--mut)";
    var weight = on ? "700" : "400";
    return (
      '<a href="' + href + '" style="color:' + color +
      ";text-decoration:none;font-weight:" + weight +
      ';font-size:14px">' + label + "</a>"
    );
  }

  function buildNav() {
    var nav = document.createElement("div");
    nav.id = "lda-nav";
    nav.setAttribute(
      "style",
      "position:sticky;top:0;z-index:60;" +
        "display:flex;align-items:center;justify-content:space-between;gap:16px;" +
        "padding:12px 18px;background:var(--panel);border-bottom:1px solid var(--line)"
    );
    nav.innerHTML =
      '<div style="display:flex;gap:18px;align-items:center">' +
      '<span style="font-weight:800;color:var(--accent);font-size:16px;letter-spacing:.5px">LDA</span>' +
      '<span id="lda-nav-ver" style="font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:999px;padding:1px 7px;margin-left:2px">v…</span>' +
      link("/index.html", "首页", "home") +
      link("/insights.html", "能力展示", "insights") +
      link("/public.html", "验证实力", "public") +
      link("/store.html", "创新超市", "store") +
      '<a id="lda-nav-mine" href="/mine.html" style="display:none;text-decoration:none;font-size:14px">我的</a>' +
      link("/admin.html", "管理后台", "admin") +
      (localStorage.getItem("lda_admin_logged_in") ? link("/stats.html", "数据看板", "stats") : "") +
      "</div>" +
      '<div id="lda-nav-auth" style="display:flex;gap:8px;align-items:center"></div>';
    document.body.insertBefore(nav, document.body.firstChild);
    // 版本号实时填充（来自 /api/about，公开端点，零鉴权）
    fetch("/api/about", { headers: { "Content-Type": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var v = document.getElementById("lda-nav-ver");
        if (v && d && d.version) v.textContent = "v" + d.version;
      })
      .catch(function () {});
  }

  function authButtons() {
    // 始终显示真实登录/注册按钮：navAuth 会复用 store.html 自带弹窗，
    // 其余页面使用 nav.js 全局弹窗——彻底消除「先跳创新超市再点一次登录」。
    return (
      '<button onclick="navAuth(\'login\')" style="background:transparent;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px">登录</button>' +
      '<button onclick="navAuth(\'register\')" style="background:var(--accent);color:#fff;border:0;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px">注册</button>'
    );
  }

  var TIER_LABELS = { standard: "标准个人", academic: "学术个人", institution: "机构席位" };

  function renderAuth() {
    var box = document.getElementById("lda-nav-auth");
    if (!box) return;
    // P2-5：不再用 JS 可读令牌判断登录态；直接凭 HttpOnly Cookie 探活 /api/store/me
    fetch("/api/store/me", { headers: { "Content-Type": "application/json" }, credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.user) {
          var mine = document.getElementById("lda-nav-mine");
          if (mine) {
            mine.style.display = "inline";
            mine.style.color = currentKey() === "mine" ? "var(--accent)" : "var(--mut)";
            mine.style.fontWeight = currentKey() === "mine" ? "700" : "400";
          }
          var tier = TIER_LABELS[d.user.user_type] || "标准个人";
          var org = d.user.organization ? (" · " + esc(d.user.organization)) : "";
          box.innerHTML =
            '<span style="color:var(--mut);font-size:13px;margin-right:6px">' +
            esc(d.user.name || d.user.email) +
            ' <span style="color:var(--accent)">' + esc(tier) + "</span>" + esc(org) +
            "</span>" +
            '<a href="/store.html#orders" style="color:var(--accent);text-decoration:none;font-size:13px;margin-right:8px">我的订单</a>' +
            '<button onclick="navLogout()" style="background:transparent;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px">退出</button>';
        } else {
          box.innerHTML = authButtons();
        }
      })
      .catch(function () { box.innerHTML = authButtons(); });
  }

  window.navLogout = function () {
    // P2-5：清除服务端 HttpOnly Cookie
    fetch("/api/store/logout", { method: "POST", credentials: "include" })
      .catch(function () {})
      .finally(function () { location.reload(); });
  };

  // —— 全局登录/注册弹窗（非 store 页使用；store 页复用其自身 showLogin/showRegister）——
  var _IN = 'background:var(--panel);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:9px 11px;font-size:13px;margin:4px 0 10px;width:100%;box-sizing:border-box';
  var _LB = 'font-size:13px;color:var(--mut);display:block;margin-top:8px';
  var navAuthMode = "login";
  var navAuthType = "standard";

  function buildAuthModal() {
    var d = document.createElement("div");
    d.id = "navAuthModal";
    d.setAttribute("style",
      "position:fixed;inset:0;background:rgba(15,20,35,.55);display:none;align-items:center;justify-content:center;z-index:200;padding:16px");
    d.innerHTML =
      '<div style="background:var(--panel);border-radius:14px;max-width:420px;width:100%;padding:20px;position:relative;max-height:90vh;overflow:auto">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">' +
      '<b id="navAuthTitle" style="font-size:16px">登录</b>' +
      '<span id="navAuthClose" style="cursor:pointer;font-size:20px;color:var(--mut)">&times;</span></div>' +
      '<label style="' + _LB + '">邮箱 *</label>' +
      '<input id="navAuthEmail" placeholder="you@company.com" style="' + _IN + '">' +
      '<div id="navAuthNameWrap">' +
      '<label style="' + _LB + '">姓名 *</label>' +
      '<input id="navAuthName" placeholder="您的称谓" style="' + _IN + '"></div>' +
      '<label style="' + _LB + '">密码 *（至少 6 位）</label>' +
      '<input id="navAuthPass" type="password" placeholder="设置或输入密码" style="' + _IN + '">' +
      '<div id="navAuthPhoneWrap">' +
      '<label style="' + _LB + '">手机号（选填）</label>' +
      '<input id="navAuthPhone" placeholder="选填" style="' + _IN + '"></div>' +
      '<div id="navAuthTypeWrap">' +
      '<label style="' + _LB + '">账户身份 *</label>' +
      '<div style="display:flex;gap:6px;margin:6px 0 10px">' +
      '<button type="button" data-v="standard" onclick="navSetType(this)" style="flex:1;background:#eef2ff;color:#4338ca;border:0;border-radius:8px;padding:8px;font-size:12px;cursor:pointer;font-weight:600">标准个人</button>' +
      '<button type="button" data-v="academic" onclick="navSetType(this)" style="flex:1;background:#eef2ff;color:#4338ca;border:0;border-radius:8px;padding:8px;font-size:12px;cursor:pointer">学术个人</button>' +
      '<button type="button" data-v="institution" onclick="navSetType(this)" style="flex:1;background:#eef2ff;color:#4338ca;border:0;border-radius:8px;padding:8px;font-size:12px;cursor:pointer">机构席位</button>' +
      '</div></div>' +
      '<div id="navAuthOrgWrap" style="display:none">' +
      '<label style="' + _LB + '">机构 / 单位名称（机构席位必填）</label>' +
      '<input id="navAuthOrg" placeholder="例如：某某大学光电实验室" style="' + _IN + '"></div>' +
      '<div id="navAuthMsg" style="font-size:13px;color:var(--red);min-height:16px;margin-top:2px"></div>' +
      '<div style="display:flex;gap:8px;margin-top:10px">' +
      '<button id="navAuthCancel" style="flex:1;background:transparent;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:9px;cursor:pointer;font-size:13px">取消</button>' +
      '<button id="navAuthSubmit" onclick="navSubmitAuth()" style="flex:1;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px;cursor:pointer;font-size:13px;font-weight:600">登录</button>' +
      '</div>' +
      '<div id="navAuthSwitch" style="text-align:center;font-size:12px;color:var(--mut);margin-top:10px"></div>' +
      '</div>';
    document.body.appendChild(d);
    document.getElementById("navAuthClose").onclick = navCloseAuth;
    document.getElementById("navAuthCancel").onclick = navCloseAuth;
    d.addEventListener("click", function (e) { if (e.target === d) navCloseAuth(); });
  }

  function navCloseAuth() {
    var m = document.getElementById("navAuthModal");
    if (m) m.style.display = "none";
  }
  window.navCloseAuth = navCloseAuth;

  window.navAuth = function (mode) {
    // store.html 自带登录/注册弹窗（与购买流程联动）→ 复用页面弹窗
    if (typeof window.showLogin === "function" && typeof window.showRegister === "function") {
      if (mode === "register") window.showRegister();
      else window.showLogin();
      return;
    }
    if (!document.getElementById("navAuthModal")) buildAuthModal();
    navAuthMode = mode === "register" ? "register" : "login";
    var isReg = navAuthMode === "register";
    document.getElementById("navAuthTitle").textContent = isReg ? "注册" : "登录";
    document.getElementById("navAuthNameWrap").style.display = isReg ? "" : "none";
    document.getElementById("navAuthPhoneWrap").style.display = isReg ? "" : "none";
    document.getElementById("navAuthTypeWrap").style.display = isReg ? "" : "none";
    document.getElementById("navAuthOrgWrap").style.display = "none";
    document.getElementById("navAuthMsg").textContent = "";
    document.getElementById("navAuthSubmit").textContent = isReg ? "注册" : "登录";
    document.getElementById("navAuthSubmit").disabled = false;
    document.getElementById("navAuthSwitch").innerHTML = isReg
      ? '已有账号？<a style="color:var(--accent);cursor:pointer" onclick="navAuth(\'login\')">去登录</a>'
      : '没有账号？<a style="color:var(--accent);cursor:pointer" onclick="navAuth(\'register\')">去注册</a>';
    var m = document.getElementById("navAuthModal");
    m.style.display = "flex";
  };

  window.navSetType = function (btn) {
    navAuthType = btn.getAttribute("data-v");
    var btns = btn.parentNode.querySelectorAll("button");
    btns.forEach(function (b) {
      b.style.background = b === btn ? "var(--accent)" : "#eef2ff";
      b.style.color = b === btn ? "#fff" : "#4338ca";
      b.style.fontWeight = b === btn ? "600" : "400";
    });
    document.getElementById("navAuthOrgWrap").style.display =
      navAuthType === "institution" ? "" : "none";
  };

  function navMsg(t) {
    document.getElementById("navAuthMsg").innerHTML = t;
  }

  window.navSubmitAuth = function () {
    var email = document.getElementById("navAuthEmail").value.trim();
    var pass = document.getElementById("navAuthPass").value;
    var isReg = navAuthMode === "register";
    if (!email || !pass) { navMsg("邮箱、密码均为必填"); return; }
    if (isReg) {
      var name = document.getElementById("navAuthName").value.trim();
      if (!name) { navMsg("请填写姓名/称谓"); return; }
      var org = document.getElementById("navAuthOrg").value.trim();
      if (navAuthType === "institution" && !org) { navMsg("机构席位需填写机构/单位名称"); return; }
    }
    if (pass.length > 200) { navMsg("密码过长（上限 200 字符）"); return; }
    var body = { email: email, password: pass };
    if (isReg) {
      body.name = document.getElementById("navAuthName").value.trim();
      body.phone = document.getElementById("navAuthPhone").value.trim();
      body.user_type = navAuthType;
      if (document.getElementById("navAuthOrg").value.trim()) body.organization = document.getElementById("navAuthOrg").value.trim();
    }
    var btn = document.getElementById("navAuthSubmit");
    btn.disabled = true;
    fetch("/api/store/" + (isReg ? "register" : "login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body)
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btn.disabled = false;
        if (!d.ok) {
          var tip = isReg ? "" : '<div style="font-size:11px;color:var(--mut);margin-top:4px">忘记密码？请联系管理员重置</div>';
          navMsg(esc(d.error || "失败") + tip);
          return;
        }
        navCloseAuth();   // P2-5：后端已下发 HttpOnly Cookie，前端无需持有令牌
        renderAuth();
        if (d.must_change_password) {
          alert("你当前使用的是管理员发放的临时密码。\n为保障账户安全，请先修改密码。");
          location.href = "/mine.html#pwd";
        }
      })
      .catch(function () { btn.disabled = false; navMsg("网络异常，请重试"); });
  };

  // ESC 关闭弹窗（页面自带 authModal 或 nav 全局 navAuthModal）
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      var a = document.getElementById("authModal");
      if (a) a.classList.remove("show");
      var b = document.getElementById("navAuthModal");
      if (b) b.style.display = "none";
    }
  });

  buildNav();
  renderAuth();
  // 多标签页同步：一处登录/退出，其余页面导航即时刷新
  window.addEventListener("storage", renderAuth);
})();
