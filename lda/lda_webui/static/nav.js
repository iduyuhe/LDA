/*
 * LDA 统一站点导航（Craft 模式生成）
 * 注入到 index.html / store.html / admin.html，提供跨页导航 + 实时会员态。
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
    if (p.endsWith("store.html")) return "store";
    if (p.endsWith("admin.html")) return "admin";
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
      link("/index.html", "首页", "home") +
      link("/store.html", "创新超市", "store") +
      link("/admin.html", "管理后台", "admin") +
      "</div>" +
      '<div id="lda-nav-auth" style="display:flex;gap:8px;align-items:center"></div>';
    document.body.insertBefore(nav, document.body.firstChild);
  }

  function authButtons() {
    // 若页面已自带登录/注册逻辑（store.html），复用之；否则给一个跳转链接
    if (typeof window.showLogin === "function" && typeof window.showRegister === "function") {
      return (
        '<button onclick="showLogin()" style="background:transparent;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px">登录</button>' +
        '<button onclick="showRegister()" style="background:var(--accent);color:#fff;border:0;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px">注册</button>'
      );
    }
    return (
      '<a href="/store.html" style="color:var(--accent);text-decoration:none;font-size:13px">登录 / 注册</a>'
    );
  }

  var TIER_LABELS = { standard: "标准个人", academic: "学术个人", institution: "机构席位" };

  function renderAuth() {
    var box = document.getElementById("lda-nav-auth");
    if (!box) return;
    var token = localStorage.getItem(STORE_TOKEN_KEY) || "";
    if (!token) {
      box.innerHTML = authButtons();
      return;
    }
    fetch("/api/store/me", { headers: { Authorization: "Bearer " + token } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.user) {
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
          localStorage.removeItem(STORE_TOKEN_KEY);
          box.innerHTML = authButtons();
        }
      })
      .catch(function () { box.innerHTML = authButtons(); });
  }

  window.navLogout = function () {
    localStorage.removeItem(STORE_TOKEN_KEY);
    location.reload();
  };

  // ESC 关闭弹窗（若页面有 authModal）
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      var m = document.getElementById("authModal");
      if (m) m.classList.remove("show");
    }
  });

  buildNav();
  renderAuth();
  // 多标签页同步：一处登录/退出，其余页面导航即时刷新
  window.addEventListener("storage", renderAuth);
})();
