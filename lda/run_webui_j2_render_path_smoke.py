# -*- coding: utf-8 -*-
"""WebUI J2（超导 transmon QPU 物理比特层）案例卡 前端取值路径 + 反向完备 + **跨源一致性** 门禁
（v0.9.234 · J2 征程收官「面板落地」的常驻护栏）。

═══════════════════════════════════════════════════════════════════════════
为什么存在
═══════════════════════════════════════════════════════════════════════════
J2 章程 §2.4 / §3-M4 **明文要求**交付 `/api/j2_qpu` WebUI 面板（含三入口面 + 常驻
render-path 门禁 + 抬 `CASE_PANELS_MIN`）。M0–M4 四档把**后端**（能力层 + 账本锚 +
`run_j2_qpu_smoke` 37 判据）做完了，面板却**全档未交付**且落地记录未披露 —— 本文件
与 `j2_case.py` / `routes.py` / `index.html` 一起补齐该缺口。

后端侧门禁（`run_j2_qpu_smoke` / `j2_case.run_selfchecks`）**只保证 JSON 里有值**，
**不保证前端问对了地方**；而 J2 卡的数字是**闭式复刻**（顶层零依赖 ⇒ 不 import 求解器），
⇒ 多一层「复刻公式是否与真源同口径」的风险。本门禁正是这两格的守卫：

  · **取值路径**：`renderJ2` 的每条 `X.a.b` 引用在真实 `case_card()` JSON 上逐条解析；
  · **反向完备**：顶层键 + 全部嵌套块 + 全部 `[]` 项目块，**每个字段都被前端引用**
    （防「后端加了字段、前端从不显示」的静默盲区）；
  · **🔴 跨源一致性（本门禁的核心价值）**：卡内每个物理量都与 `lda_qeda` / `lda_agent`
    的**真源模块**（`physical_error_model` / `qpu_error_budget` / `sc_readout` /
    `topology_qec_bridge` / `j2_to_j1_calibration` / `readout_fidelity`）**现算值逐值对拍**
    —— 闭式复刻**不得漂移**；
  · **里程碑 gate 机械对照**：卡内逐档 `gate` == `run_j2_qpu_smoke` 实跑 `[PASS]` 行按
    **判据字母带**分档计数（A–E+R / F / G / H）⇒ 手写数字上机器对照；
  · **诚实边界与免登录**：`verdict=DESIGN_BUDGET` / 边界关键词 / 路由登记 ∧ 不在
    `HEAVY_POST_PATHS` / 顶层 import 白名单（零重计算）。

───────────────────────────────────────────────────────────────────────────
判什么（分节 · **53 判据**）
───────────────────────────────────────────────────────────────────────────
  A 前端接线（onclick / DOM 契约 / 首屏直达 / 函数定义 / apiGet / 十段 / 抽屉映射）  7
  B 🔴 取值路径存在性                                                                1
  C 🔴 反向完备（顶层 / 嵌套块 / `[]` 项目块 / 零豁免）                              4
  D 🔴 **跨源一致性**（10 组物理量逐值对拍 `lda_qeda`/`lda_agent` 真源）            10
  E 🔴 里程碑 gate 机械对照（总数 / 字母带分档 / 模块自检 + 探针）                   4
  F 真实性与护栏（verdict / 边界关键词 / 路由 / 免登录 / 零重计算 / 缺口 / 自入 CI）  7
  G 🔴 突变探针 19 条 + 条数自洽（机器数出的探针数 == 卡内 `span.probe_mutations`）  20

🔴 **诚实边界**：本门禁是**静态 + 对拍**检查，不执行 JS、不看渲染好不好看。
「值对不对」由 `run_j2_qpu_smoke`（闭式 ⇄ 数值）守，「问对没问对 + 复刻没漂移」由本门禁守。
"""
from __future__ import annotations

import ast
import io
import contextlib
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

from lda_harness.webui_js_ref import (  # noqa: E402
    render_body, alias_timeline, scan_refs, bad_refs, js_ref_ok,
)

INDEX = os.path.join(_HERE, "lda_webui", "static", "index.html")
ROUTES = os.path.join(_HERE, "lda_webui", "routes.py")
CASE_PY = os.path.join(_HERE, "lda_webui", "j2_case.py")
CI = os.path.join(_HERE, "run_ci_regression.py")

API = "/api/j2_qpu"
SEG = "sec-j2"
BTN = "runJ2"
MILESTONE_SMOKE = "run_j2_qpu_smoke.py"

#: 顶层 import 白名单（与 `j2_case.run_selfchecks` ⑮ 同口径）
_TOP_IMPORT_ALLOW = {"math", "os", "typing", "__future__"}


# ═════════════════ 纯函数（参数化 ⇒ 探针可喂变异体） ═════════════════
def _bad_paths(card, body):
    tl, tb = alias_timeline(body)
    return [x.split(" → ")[0]
            for x in bad_refs(card, scan_refs(body, set(tb.keys()), tl))]


def _ref_data(body):
    tl, tb = alias_timeline(body)
    refs = scan_refs(body, set(tb.keys()), tl)
    return refs, {f[0] for f in _fulls(refs) if f}


def _fulls(refs):
    return [tuple(base) + tuple(p.split(".")) for _a, p, base in refs]


def _ref_segs(refs, prefix):
    out = set()
    for _a, path, base in refs:
        full = tuple(base) + tuple(path.split("."))
        if len(full) > len(prefix) and full[:len(prefix)] == prefix:
            out.add(full[len(prefix)])
    return out


def _block_keys(card, prefix):
    """取 JSON 路径 `prefix` 处的键集（**列表取首元素**；支持 `a.b[]` 点分形式）。

    🔴 `[]` 前缀必须**按 `.` 切分 + 可选 `[]` 后缀归一化** —— 否则 `for seg in
    "milestones[]"` 会逐字符迭代 ⇒ 恒返空集 ⇒ 反向完备**假绿**（PM 门禁血案）。
    """
    parts = prefix.split(".") if isinstance(prefix, str) else list(prefix)
    cur = card
    for part in parts:
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or key not in cur:
                return set()
            cur = cur[key]
            if not isinstance(cur, list) or not cur:
                return set()
            cur = cur[0]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return set()
            cur = cur[part]
    if isinstance(cur, dict):
        return set(cur.keys())
    if isinstance(cur, list) and cur and isinstance(cur[0], dict):
        return set(cur[0].keys())
    return set()


# ── 嵌套块反向完备：`(JSON 前缀元组, 说明)` ──
_BLOCKS = (
    (("identity",), "案例身份"),
    (("span",), "征程跨度"),
    (("loop",), "J1↔J2 复利闭环"),
    (("errors",), "物理错误率链"),
    (("readout",), "色散读出链"),
    (("budget",), "QPU 误差预算"),
    (("topology",), "拓扑↔表面码"),
    (("positioning",), "对标准星与诚实限制"),
)

# ── `[]` 项目块反向完备：`(JSON 前缀, 标签, {JS 字面量: 相对字段})` ──
_ITEM_BLOCKS = (
    ("milestones[]", "征程档", {
        "m.id": "id", "m.code": "code", "m.title": "title",
        "m.gate": "gate", "m.gate_total": "gate_total",
        "m.bands": "bands", "m.result": "result",
    }),
    ("loop.curve[]", "闭环曲线", {"c.d": "d", "c.p_logic": "p_logic"}),
    ("budget.components[]", "预算分量", {
        "c.key": "key", "c.label": "label", "c.eps": "eps",
        "c.count": "count", "c.subtotal": "subtotal",
    }),
    ("findings[]", "关键结论", {"fn.title": "title", "fn.detail": "detail"}),
    ("gaps[]", "缺口", {
        "gp.id": "id", "gp.title": "title", "gp.status": "status",
        "gp.detail": "detail",
    }),
)

#: 显式豁免表（**本卡设计为零豁免**：每个字段都能被引用 ⇒ C2/C3 是真覆盖）。
#: 留此机制以便未来需要时显式登记，并由 C4 判据守「豁免表必须为空」。
_DUP_SUBTREES = {}


# ── 里程碑 gate 机械对照 ──
def _pass_letters(sname):
    """实跑某后端门禁 ⇒ (总 `[PASS]` 行数, {判据字母: 条数})。

    判据名形如 `A1 …` ⇒ 字母 = 首个 token 的首字符。**按行首锚定**计数
    （不用 `stdout.count`，防 detail 文本里的 `[PASS]` 字面污染 ⇒ 度量工具自身漂移）。
    """
    p = os.path.join(_HERE, sname)
    r = subprocess.run([sys.executable, p], cwd=_HERE, capture_output=True,
                       text=True, timeout=600)
    total = 0
    letters: dict = {}
    for ln in (r.stdout or "").splitlines():
        s = ln.lstrip()
        if not s.startswith("[PASS"):
            continue
        total += 1
        rest = s[len("[PASS]"):].strip() if s.startswith("[PASS]") else s[6:].strip()
        m = re.match(r"([A-Za-z])", rest)
        if m:
            k = m.group(1).upper()
            letters[k] = letters.get(k, 0) + 1
    return total, letters


def _band_drift(milestones, letters):
    """逐档字母带计数 == 卡内 `gate`；另返回「无归属字母」（新判据带未登记 ⇒ 红）。"""
    drift = []
    for m in milestones:
        n = sum(letters.get(b, 0) for b in m.get("bands", []))
        if n != m.get("gate"):
            drift.append((m.get("id"), m.get("gate"), n))
    covered = {b for m in milestones for b in m.get("bands", [])}
    orphan = sorted(set(letters) - covered)
    return drift, orphan


def _selfcheck_counts(mods):
    """逐模块实跑 `run_selfchecks(verbose=True)` ⇒ {模块: 行首 `[PASS]` 行数}。"""
    import importlib
    out = {}
    for name in mods:
        try:
            m = importlib.import_module("lda_qeda." + name)
        except Exception:                                    # noqa: BLE001
            out[name] = None
            continue
        fn = getattr(m, "run_selfchecks", None)
        if fn is None:
            out[name] = None
            continue
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                fn(verbose=True)
        except Exception:                                    # noqa: BLE001
            out[name] = None
            continue
        out[name] = sum(1 for ln in buf.getvalue().splitlines()
                        if ln.lstrip().startswith("[PASS"))
    return out


def _top_imports(path):
    """ast 真遍历模块**顶层** import（不用源码字符串 in ⇒ 不误命中 docstring）。"""
    tree = ast.parse(open(path, encoding="utf-8").read())
    mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    return mods


#: 诚实边界关键词（F2 与探针 G17 共用**同一判定函数** ⇒ 探针打在被消费的引用上）
_HONEST_KWS = ("非流片后实测", "非任何 foundry", "零量子 SDK", "LLM 不进判决路径")


def _verdict_ok(card):
    """不伪装实测：判决位必须是 DESIGN_BUDGET，且**不得**是 PASS/ACCEPT。"""
    return card["verdict"] == "DESIGN_BUDGET" and card["verdict"] not in ("PASS", "ACCEPT")


def _honest_ok(card):
    return all(k in card["honest_note"] for k in _HONEST_KWS)


def _imports_ok(mods):
    return mods <= _TOP_IMPORT_ALLOW


# ── 🔴 跨源一致性：卡内闭式复刻 ⇄ 真源模块现算值 ──
def _cross_source(card, jc):
    """返回 `{判据标签: [不符项]}` —— 空列表 = 该项与真源**口径一致**。"""
    from lda_qeda import physical_error_model as PEM
    from lda_qeda import qpu_error_budget as QB
    from lda_qeda import sc_readout as S4
    from lda_qeda import topology_qec_bridge as TQ
    from lda_qeda import sc_topology_core as TOPO
    from lda_qeda import j2_to_j1_calibration as CAL
    from lda_agent import readout_fidelity as RF

    out = {}

    def near(tag, label, a, b, tol=1e-12):
        """绝对∨相对**并列**：|Δ| ≤ tol·max(1, |truth|)（小量级走绝对、大量级走相对）。"""
        try:
            d = abs(float(a) - float(b))
            s = abs(float(b))
            if not (d <= tol * max(1.0, s)):
                out.setdefault(tag, []).append(
                    "%s ours=%.12g truth=%.12g |Δ|=%.2e" % (label, a, b, d))
        except Exception as e:                               # noqa: BLE001
            out.setdefault(tag, []).append("%s EXC %s" % (label, e))

    def same(tag, label, a, b):
        if a != b:
            out.setdefault(tag, []).append("%s ours=%r truth=%r" % (label, a, b))

    er, ro, bg, tp, lp = (card["errors"], card["readout"], card["budget"],
                          card["topology"], card["loop"])

    # D1 单比特门退相干极限（B10 族）
    near("D1", "errors.eps_1q", er["eps_1q"],
         PEM.gate_error_decoherence(jc.T_1Q_S, jc.T1_S, jc.T2_S))

    # D2 CR 门有效模型（门时间 + 有效耦合）
    crt = QB.cr_gate_time_us(jc.J_MHZ, jc.DELTA_MHZ, jc.ALPHA_MHZ)
    near("D2", "errors.t_cr_us", er["t_cr_us"], crt["t_CR_us"])
    near("D2", "errors.g_cr_mhz", er["g_cr_mhz"], crt["g_CR_mhz"])

    # D3 两比特 CR 门退相干错误率（B506 同律）
    near("D3", "errors.eps_2q", er["eps_2q"],
         QB.cr_gate_error_2q(crt["t_CR_us"], jc.T1_S, jc.T2_S, jc.T1_S, jc.T2_S))

    # D4 残余 ZZ（B507 同律）
    near("D4", "errors.eps_zz", er["eps_zz"],
         QB.residual_zz_error(crt["t_CR_us"], jc.ZETA_ZZ_MHZ))

    # D5 色散读出链（B30/D-47 同律）
    near("D5", "readout.snr", ro["snr"],
         RF.readout_snr(jc.CHI_GHZ, jc.KAPPA_R_GHZ, jc.NBAR, jc.ETA_READOUT,
                        jc.N_AMP, jc.T_RO_S))
    near("D5", "readout.eps", ro["eps"],
         RF.readout_fidelity(jc.CHI_GHZ, jc.KAPPA_R_GHZ, jc.NBAR, jc.ETA_READOUT,
                             jc.N_AMP, jc.T_RO_S, jc.T1_S)["eps"])

    # D6 QPU 每周期误差预算集成（签核口径 = 每操作平均）
    qb = QB.qpu_cycle_error_budget(QB.DEFAULT_QPU_BUDGET)
    near("D6", "budget.p_cycle_sum", bg["p_cycle_sum"], qb["p_cycle_sum"])
    near("D6", "budget.p_op_avg", bg["p_op_avg"], qb["p_op_avg"])
    near("D6", "budget.p_op_max", bg["p_op_max"], qb["p_op_max"])
    near("D6", "budget.p_th", bg["p_th"], qb["p_th"])
    near("D6", "budget.threshold_margin", bg["threshold_margin"], qb["threshold_margin"])
    same("D6", "budget.signoff", bg["signoff"], qb["verdict"])
    near("D6", "budget.n_ops", bg["n_ops"], qb["n_ops"])

    # D7 静态杂散 ZZ 常量副本 + 上限（S 分支真源 · 卡内为副本 ⇒ 必须逐位一致）
    xt = S4.crosstalk_budget()
    near("D7", "errors.zeta_zz_mhz", er["zeta_zz_mhz"], xt["max_nearest_zz_mhz"])
    near("D7", "ZETA_ZZ_MHZ(模块常量)", jc.ZETA_ZZ_MHZ, xt["max_nearest_zz_mhz"])
    near("D7", "zeta_limit_mhz", er["zeta_limit_mhz"], S4.ZZ_STRAY_LIMIT_MHZ)
    same("D7", "budget.zz_within_limit", bg["zz_within_limit"],
         bool(xt["max_nearest_zz_mhz"] <= S4.ZZ_STRAY_LIMIT_MHZ))

    # D8 λ₂ 谱定理闭式 ⇄ 嵌套 Krylov Rayleigh–Ritz（B509 golden ⇄ candidate）
    #    tol 按**数值方法精度**标定（Krylov m=32 实测 rel ≈1.2e-9 ⇒ 取 1e-6 留 3 位余量）
    topo = TOPO.grid_topology(jc.ROWS, jc.COLS)
    near("D8", "topology.lambda2_closed", tp["lambda2_closed"],
         TQ.topology_lambda2(topo, m=32), 1e-6)

    # D9 拓扑↔表面码对接（嵌入判定 + 资源核算）
    bv = TQ.bridge_verdict(topo, d=3, m=32)
    same("D9", "topology.embedding", tp["embedding"], bv["embedding"])
    same("D9", "topology.resource_ok", tp["resource_ok"], bv["resource_ok"])
    near("D9", "topology.n_logical_capacity", tp["n_logical_capacity"],
         bv["n_logical_capacity"])
    same("D9", "topology.n_qubits", tp["n_qubits"], topo["n_qubits"])

    # D10 J1↔J2 复利闭环（**注入口径 = 去极化参数 2ε**，非 ε 本身）
    p_phys = PEM.depolarizing_parameter(jc.T_1Q_S, jc.T1_S, jc.T2_S)
    near("D10", "loop.p_phys_used", lp["p_phys_used"], p_phys)
    near("D10", "loop.orders_below", lp["orders_below"], CAL.orders_below_threshold(p_phys))
    for row in lp["curve"]:
        near("D10", "loop.curve[d=%s].p_logic" % row["d"], row["p_logic"],
             CAL.logical_error_rate_ideal(p_phys, int(row["d"])))
    same("D10", "loop.target_met", lp["target_met"], CAL.j2_hard_target_met(p_phys))
    near("D10", "loop.p_th", lp["p_th"], CAL.P_TH_DEFAULT)
    near("D10", "loop.a_scale", lp["a_scale"], CAL.A_SCALE_DEFAULT)

    return out


def main() -> int:
    print("=" * 74)
    print("WebUI J2（超导 transmon QPU 物理比特层）案例卡 取值路径 + 反向完备 + 跨源一致性 门禁")
    print("=" * 74)

    html = open(INDEX, encoding="utf-8").read()
    rsrc = open(ROUTES, encoding="utf-8").read()

    from lda_webui import j2_case as JC

    card = JC.case_card()

    try:
        rbody = render_body(html, "renderJ2")
    except ValueError as e:
        check("A0 renderJ2 函数在场（花括号配对可抽出函数体）", False, str(e))
        rbody = ""
    try:
        ubody = render_body(html, "runJ2")
    except ValueError as e:
        check("A0b runJ2 函数在场", False, str(e))
        ubody = ""

    # ── A 前端接线 ──────────────────────────────────────────────────────
    check("A1 onclick 接线：$('runJ2').onclick = runJ2 在场（防「能力上线却点不动」）",
          "$('runJ2').onclick = runJ2" in html)
    dom = all(('id="%s"' % i) in html for i in
              (SEG, BTN, "j2Summary", "j2Body", "j2Conclusion"))
    check("A2 面板 DOM 契约：sec-j2 / runJ2 / j2Summary / j2Body / j2Conclusion 齐备", dom)
    check("A3 首屏案例直达条 #sec-j2 在场（入口可达性 · 三入口面之一）",
          'href="#sec-j2"' in html)
    check("A4 runJ2 / renderJ2 在 index.html 内定义（非空壳）",
          "function runJ2(" in html and "function renderJ2(" in html)
    check("A5 runJ2 调 apiGet('/api/j2_qpu') 并转交 renderJ2",
          API in ubody and "renderJ2(" in ubody)
    heads = ("① 案例身份", "② 征程四档", "③ 物理错误率链", "④ 色散读出链",
             "⑤ QPU 误差预算集成", "⑥ 拓扑 ↔ 表面码对接", "⑦ J1↔J2 复利闭环",
             "⑧ 关键结论", "⑨ 对标准星", "⑩ 缺口登记")
    miss_h = [h for h in heads if h not in rbody]
    check("A6 renderJ2 真渲染 ①–⑩ 十段（防「后端加了段、前端还是空壳」）", not miss_h,
          "缺段：%s" % miss_h)
    check("A7 抽屉目录自动运行映射含 '\"#sec-j2\": \"runJ2\"'",
          '"#sec-j2": "runJ2"' in html)

    # ── B 取值路径存在性 ────────────────────────────────────────────────
    refs, top_ref = _ref_data(rbody)
    bad = _bad_paths(card, rbody)
    check("B1 🔴 **取值路径存在性**：%d 条引用路径逐条在真实 `case_card()` JSON 上解析 ⇒ 全部存在"
          % len(refs), not bad, "坏路径 %d 条：%s" % (len(bad), bad[:4]))

    # ── C 反向完备 ──────────────────────────────────────────────────────
    top_backend = set(card.keys())
    miss_top = sorted(top_backend - top_ref)
    check("C1 🔴 反向完备（顶层）：`case_card()` 全部 %d 个顶层键都被前端引用"
          % len(top_backend), not miss_top, "未被引用：%s" % miss_top)

    miss_blocks = []
    for prefix, label in _BLOCKS:
        bk = {k for k in _block_keys(card, prefix) if (prefix + (k,)) not in _DUP_SUBTREES}
        d = sorted(bk - _ref_segs(refs, prefix))
        if d:
            miss_blocks.append("%s(%s)缺%s" % (".".join(prefix), label, d))
    check("C2 🔴 反向完备（%d 个嵌套块）：每块每个字段都被前端引用" % len(_BLOCKS),
          not miss_blocks, "盲区：%s" % miss_blocks[:4])

    all_lits = [lit for _p, _l, m in _ITEM_BLOCKS for lit in m]
    miss_items, bad_items = [], []
    for prefix, label, mapping in _ITEM_BLOCKS:
        bk = _block_keys(card, prefix)
        d = sorted(bk - set(mapping.values()))
        if d:
            miss_items.append("%s(%s)缺%s" % (prefix, label, d))
        for lit in mapping:
            if not js_ref_ok(rbody, lit, all_lits):
                bad_items.append(lit)
    check("C3 🔴 反向完备（%d 个 `[]` 项目块）：字段全覆盖 ∧ 每条 JS 字面量真在场"
          % len(_ITEM_BLOCKS), not miss_items and not bad_items,
          "缺字段=%s 缺字面量=%s" % (miss_items[:3], bad_items[:3]))

    check("C4 🔴 零豁免：本卡反向完备无需任何豁免（豁免表为空 ⇒ C2/C3 是真覆盖）",
          not _DUP_SUBTREES, "豁免表非空 ⇒ 须复审：%s" % sorted(_DUP_SUBTREES))

    # ── D 🔴 跨源一致性（本门禁核心价值）────────────────────────────────
    cs = _cross_source(card, JC)
    _d_tags = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10"]
    _d_names = {
        "D1": "单比特门错误率 ε_1q ⇄ physical_error_model.gate_error_decoherence",
        "D2": "CR 门时间 t_CR / 有效耦合 g_CR ⇄ qpu_error_budget.cr_gate_time_us",
        "D3": "两比特 CR 门错误率 ε_2q ⇄ qpu_error_budget.cr_gate_error_2q（B506 同律）",
        "D4": "残余 ZZ 错误率 ε_ZZ ⇄ qpu_error_budget.residual_zz_error（B507 同律）",
        "D5": "读出 SNR / 误判率 ⇄ lda_agent.readout_fidelity（B30/D-47 同律）",
        "D6": "QPU 预算 3 量 + 阈值余量 + 签核 + n_ops ⇄ qpu_error_budget.qpu_cycle_error_budget",
        "D7": "静态杂散 ZZ 常量副本 + 上限 ⇄ lda_qeda.sc_readout（S 分支真源 · 逐位）",
        "D8": "λ₂ 谱定理闭式 ⇄ topology_qec_bridge.topology_lambda2（Krylov · B509）",
        "D9": "拓扑嵌入判定 / 资源核算 / 比特数 ⇄ topology_qec_bridge.bridge_verdict",
        "D10": "J1↔J2 标度（p_phys=2ε 去极化口径 + p_L(d) 曲线 + 硬指标）⇄ j2_to_j1_calibration",
    }
    for tag in _d_tags:
        check("D%s 🔴 跨源一致：%s" % (tag[1:], _d_names[tag]),
              not cs.get(tag), "不符：%s" % cs.get(tag, [])[:3])

    # ── E 🔴 里程碑 gate 机械对照 ───────────────────────────────────────
    total, letters = _pass_letters(MILESTONE_SMOKE)
    span = card["span"]
    last_total = card["milestones"][-1]["gate_total"]
    check("E1 🔴 `%s` 实跑 [PASS] 总数 == span.gate_checks == 末档 gate_total" % MILESTONE_SMOKE,
          total == span["gate_checks"] == last_total,
          "实跑=%d 卡内 gate_checks=%d 末档 gate_total=%d" % (total, span["gate_checks"], last_total))

    drift, orphan = _band_drift(card["milestones"], letters)
    check("E2 🔴 卡内逐档 `gate` == 实跑按**判据字母带**分档计数 ∧ 无未登记字母",
          not drift and not orphan,
          "漂移=%s 未登记字母=%s 实跑分档=%s" % (drift, orphan, letters))

    sc = _selfcheck_counts(JC.SELFCHECK_MODULES)
    sc_total = sum(v for v in sc.values() if v)
    check("E3 🔴 能力层模块自检实跑和 == span.module_selfchecks（逐模块 %s）"
          % sorted(JC.SELFCHECK_MODULES), sc_total == span["module_selfchecks"],
          "实跑=%s 合计=%d 卡内=%d" % (sc, sc_total, span["module_selfchecks"]))

    # E4 突变探针：计数变 / 卡内 gate 变 / 未登记字母 / 自检和不符 四改必红
    _ms_bad = [dict(m) for m in card["milestones"]]
    _ms_bad[-1]["gate"] = _ms_bad[-1]["gate"] + 1
    _letters_bad = dict(letters)
    _letters_bad["Z"] = 1
    _p_e = [
        _band_drift(card["milestones"], letters) == ([], []),          # 原样绿
        _band_drift(card["milestones"], dict(letters, H=letters.get("H", 0) + 1))[0] != [],
        _band_drift(_ms_bad, letters)[0] != [],
        _band_drift(card["milestones"], _letters_bad)[1] == ["Z"],
        (sc_total + 1) != span["module_selfchecks"],
    ]
    check("E4 突变探针：原样绿 ∧ 实跑分档变 / 卡内 gate 变 / 未登记字母 / 自检和不符 四改必红",
          all(_p_e), "p_e=%s" % _p_e)

    # ── F 真实性与护栏 ──────────────────────────────────────────────────
    check("F1 🔴 不伪装实测：verdict == DESIGN_BUDGET ∧ ∉ {PASS, ACCEPT}", _verdict_ok(card))
    note = card["honest_note"]
    check("F2 🔴 诚实边界：honest_note 含 %s" % list(_HONEST_KWS), _honest_ok(card),
          "缺：%s" % [k for k in _HONEST_KWS if k not in note])

    get_block = rsrc.split("GET_ROUTES = {")[1].split("\n}")[0] if "GET_ROUTES = {" in rsrc else ""
    heavy = rsrc.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rsrc else ""
    check("F3 路由接线：`%s` 登记进 GET_ROUTES 且 handler = h_j2_qpu_demo" % API,
          '"/api/j2_qpu": h_j2_qpu_demo,' in get_block and "def h_j2_qpu_demo(" in rsrc)
    check("F4 🔴 `%s` **不在** HEAVY_POST_PATHS（零重计算 ⇒ 免登录、无 DoS 面）" % API,
          API not in heavy)

    top_mods = _top_imports(CASE_PY)
    check("F5 🔴 零重计算：j2_case.py 顶层 import ⊆ %s（ast 真遍历 · 零求解器 / 零量子 SDK）"
          % sorted(_TOP_IMPORT_ALLOW), _imports_ok(top_mods),
          "越界：%s" % sorted(top_mods - _TOP_IMPORT_ALLOW))

    gaps = card["gaps"]
    # ⚠️ v0.9.300：原判据要求「全部 status=未闭合」—— 它**本身就是跨卡口径冲突的产物**
    #    （同一句「无流片 / 无 PDK」在 ecore/pchip 记边界声明、在 j2 记未闭合）。
    #    改判后不能简单放宽成「任意状态都行」（那就成死判据），故**三向收紧**：
    #      ① 每条必须是四值之一（不接受自由文本 / 空）
    #      ② 至少 1 条真欠债（防空集合：不许把整卡都判成边界来清债）
    #      ③ 每条边界声明**必须写明判定依据**（`非流片`/`须 NDA`/`实验台`/`专卡`/`不重复计债`）
    _FOUR = ("已闭合", "已结算", "未闭合", "边界声明")
    #   ⚠️ 词表必须覆盖**数据里实际出现的写法**（v0.9.286 纪律）：「实测台」与「实验台」同类，
    #      本仓两种写法都出现过 ⇒ 都认（否则一条合规的边界声明会被误判成「无依据」）。
    _BADGE = ("非流片", "须 NDA", "实验台", "实测台", "专卡", "不重复计债")
    _bad_stat = [g.get("id") for g in gaps
                 if not any(str(g.get("status") or "").startswith(x) for x in _FOUR)]
    _bad_field = [g.get("id") for g in gaps
                  if not (g.get("id") and g.get("title") and g.get("detail"))]
    _n_open = sum(1 for g in gaps if str(g.get("status") or "").startswith("未闭合"))
    _bad_bd = [g.get("id") for g in gaps
               if str(g.get("status") or "").startswith("边界声明")
               and not any(k in str(g.get("status")) for k in _BADGE)]
    check("F6 缺口登记：状态全为四值之一 ∧ 每条含 id/title/detail ∧ **至少 1 条真欠债** ∧ "
          "每条边界声明写明判定依据（不粉饰）",
          bool(gaps) and not _bad_stat and not _bad_field and _n_open >= 1 and not _bad_bd,
          "缺口=%s 非法状态=%s 缺字段=%s 无依据边界=%s 真欠债=%d"
          % ([(g.get("id"), str(g.get("status"))[:6]) for g in gaps],
             _bad_stat, _bad_field, _bad_bd, _n_open))

    # 🔴 F6b（v0.9.279 · D-227 · F-6 收口）：**台账不得与已交付实现脱钩**。
    #    血案：J2-G-C 长期写「不做量子线路编译/噪声仿真」，而 D-218 早已交付
    #    `ft_compiler`、D-226 又交付 `noise_aware_schedule` ⇒ 台账把已完成的说成"不做"。
    #    只靠人工同步会反复脱钩，故让**模块存在性**反过来咬台账文字：
    #    若编译/核算模块可 import，则 detail 不得再声称"不做…编译/噪声仿真"。
    def _importable(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:                              # noqa: BLE001
            return False

    _cap = {"lda_qeda.ft_compiler": "编译", "lda_qeda.noise_aware_schedule": "资源核算"}
    _have = {m: _importable(m) for m in _cap}
    _gc = next((g for g in gaps if g.get("id") == "J2-G-C"), {})
    _detail = str(_gc.get("detail", ""))
    _stale = [w for w in ("不做量子线路编译", "不做噪声仿真", "不含线路级仿真")
              if w in _detail]
    check("F6b 🔴 台账与实现不脱钩：编译/核算模块在册 ⇒ J2-G-C 不得再声称「不做」",
          not (_have.get("lda_qeda.ft_compiler") and _stale),
          "在册=%s 过期表述=%s" % (_have, _stale))
    # 🔴 v0.9.301：原判据钉死 `status == "未闭合"` —— 它本身就是口径冲突的产物
    #    （本条原把「线路级仿真（纯模型活）」与「解码器实测（硬件）」压在一起）。
    #    拆开后保留**原意图**（不许虚报闭合、不许抹掉已交付），只把状态约束改成
    #    「**不得**以「已闭合」开头」：本条剩的都是须实测的部分，任何「已闭合」都是虚报。
    check("F6c J2-G-C 如实分列「已有 / 仍缺」∧ status **不得**以「已闭合」开头"
          "（既不许虚报闭合，也不许抹掉已交付）",
          "已有" in _detail and "仍缺" in _detail
          and not str(_gc.get("status") or "").startswith("已闭合"),
          "status=%r 有已有=%s 有仍缺=%s" % (str(_gc.get("status"))[:24],
                                             "已有" in _detail, "仍缺" in _detail))

    ck = open(CI, encoding="utf-8").read() if os.path.exists(CI) else ""
    check("F7 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_webui_j2_render_path_smoke.py" in ck)

    # ── G 🔴 突变探针（先证能变红）──────────────────────────────────────
    #: 逐条登记 ⇒ 末尾 G20 用**机器数出的条数**与卡内 `span.probe_mutations` 自洽核对
    #: （防「卡内写 18、实际 19」这类两处手写漂移）。
    _probe_n = []

    def probe(name, cond, detail=""):
        _probe_n.append(name)
        return check(name, cond, detail)

    assert not _bad_paths(card, rbody), "前置：原体应无坏路径"

    # G1 改真实路径 ⇒ B1 必红
    p1 = _bad_paths(card, rbody.replace("idf.physics", "idf.physicsX", 1))
    probe("G1 改真实路径（idf.physics→…X）⇒ B1 取值路径存在性必红",
          len(p1) >= 1, "命中 %d 条：%s" % (len(p1), p1[:2]))

    # G2 抹掉别名绑定 ⇒ C1 顶层反向完备必红
    #    🔴 必须**整段删除**绑定（与 PM 门禁 W6-P2 同机制）：若只改名（`idf→idf2`），
    #    绑定语句里的 `d.identity` 文本仍在 ⇒ 该顶层键**仍被引用** ⇒ 探针假绿。
    assert "idf=d.identity||{}," in rbody, "前置：别名块含 `idf=d.identity||{},`（探针锚点）"
    _refs2, top2 = _ref_data(rbody.replace("idf=d.identity||{},", "", 1))
    probe("G2 抹掉 `idf=d.identity||{},` 绑定 ⇒ C1 顶层反向完备必红（假盲区回归）",
          "identity" not in top2)

    import copy as _copy
    # G3 注入顶层新字段 ⇒ C1 必红
    c3 = _copy.deepcopy(card)
    c3["brand_new_top"] = 1
    probe("G3 后端注入顶层新字段 ⇒ C1 必红（防「后端加了、前端不显示」）",
          "brand_new_top" in sorted(set(c3.keys()) - top_ref))

    # G4 注入嵌套块新字段 ⇒ C2 必红
    c4 = _copy.deepcopy(card)
    c4["errors"]["brand_new_field"] = 1
    _bk4 = _block_keys(c4, ("errors",))
    probe("G4 后端往 `errors` 注入新字段 ⇒ C2 必红",
          sorted(_bk4 - _ref_segs(refs, ("errors",))) == ["brand_new_field"])

    # G5 注入 `[]` 项目块新字段 ⇒ C3 必红
    c5 = _copy.deepcopy(card)
    c5["budget"]["components"][0]["brand_new_item"] = 1
    _bk5 = _block_keys(c5, "budget.components[]")
    probe("G5 后端往 `budget.components[0]` 注入新字段 ⇒ C3 必红",
          sorted(_bk5 - set(_ITEM_BLOCKS[2][2].values())) == ["brand_new_item"])

    # G6 改 `[]` 项目块 JS 字面量 ⇒ C3 必红
    probe("G6 项目块 JS 字面量被改（`c.subtotal`→`c.subtotalX`）⇒ C3 必红",
          not js_ref_ok(rbody, "c.subtotalX", all_lits) and "c.subtotal" in rbody)

    # G7 `_block_keys` 假绿复现（修复前 `for seg in prefix` 逐字符 ⇒ 恒返空集）
    def _buggy_block_keys(c, prefix):
        cur = c
        for seg in prefix:
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                return set()
        return set(cur.keys()) if isinstance(cur, dict) else set()

    _ci = _copy.deepcopy(card)
    _ci["milestones"][0]["brand_new_item_field"] = 1
    probe("G7 🔴 假绿复现：**修复前** `_block_keys(card, \"milestones[]\")` 恒为**空集**"
          "（⇒ C3 字段覆盖半边恒绿）——这就是被修掉的那个假判据",
          _buggy_block_keys(_ci, "milestones[]") == set()
          and len(_block_keys(_ci, "milestones[]")) >= 2)

    # G8 跨源：改卡内 ε_1q ⇒ D1 必红
    c8 = _copy.deepcopy(card)
    c8["errors"]["eps_1q"] = c8["errors"]["eps_1q"] * 2.0
    probe("G8 改卡内 `errors.eps_1q`（×2）⇒ D1 跨源一致必红（闭式复刻漂移）",
          bool(_cross_source(c8, JC).get("D1")))

    # G9 跨源：改卡内 ζ 副本 ⇒ D7 必红
    c9 = _copy.deepcopy(card)
    c9["errors"]["zeta_zz_mhz"] = c9["errors"]["zeta_zz_mhz"] + 0.1
    probe("G9 改卡内 `errors.zeta_zz_mhz`（+0.1）⇒ D7 跨源一致必红（常量副本漂移）",
          bool(_cross_source(c9, JC).get("D7")))

    # G10 跨源：改卡内 λ₂ ⇒ D8 必红
    c10 = _copy.deepcopy(card)
    c10["topology"]["lambda2_closed"] = c10["topology"]["lambda2_closed"] + 1e-3
    probe("G10 改卡内 `topology.lambda2_closed`（+1e-3）⇒ D8 跨源一致必红",
          bool(_cross_source(c10, JC).get("D8")))

    # G11 跨源：改卡内预算签核 ⇒ D6 必红
    c11 = _copy.deepcopy(card)
    c11["budget"]["signoff"] = "REJECT"
    probe("G11 改卡内 `budget.signoff`（ACCEPT→REJECT）⇒ D6 跨源一致必红",
          bool(_cross_source(c11, JC).get("D6")))

    # G12 跨源：改卡内 J1 注入量（去极化口径）⇒ D10 必红
    c12 = _copy.deepcopy(card)
    c12["loop"]["p_phys_used"] = c12["loop"]["p_phys_used"] / 2.0   # 退回 ε 口径
    probe("G12 改卡内 `loop.p_phys_used`（÷2 ⇒ 退回 ε 而非 2ε 口径）⇒ D10 必红",
          bool(_cross_source(c12, JC).get("D10")))

    # G13 跨源：改卡内读出误判率 ⇒ D5 必红
    c13 = _copy.deepcopy(card)
    c13["readout"]["eps"] = c13["readout"]["eps"] * 3.0
    probe("G13 改卡内 `readout.eps`（×3）⇒ D5 跨源一致必红",
          bool(_cross_source(c13, JC).get("D5")))

    # G14 gate 对照：实跑分档计数变 ⇒ E2 必红
    probe("G14 实跑分档计数变（H +1）⇒ E2 必红（卡内 gate 漂移检测）",
          _band_drift(card["milestones"], dict(letters, H=letters.get("H", 0) + 1))[0] != [])

    # G15 gate 对照：未登记字母出现 ⇒ E2 必红
    probe("G15 出现未登记字母带（Z）⇒ E2 必红（新增判据带未登记 ⇒ 统计口径漏洞）",
          _band_drift(card["milestones"], dict(letters, Z=1))[1] == ["Z"])

    # G16 真实性：verdict 改 ACCEPT ⇒ F1 必红
    c16 = _copy.deepcopy(card)
    c16["verdict"] = "ACCEPT"
    probe("G16 把 verdict 改成 ACCEPT ⇒ F1 必红（不伪装实测）", not _verdict_ok(c16))

    # G17 诚实边界：honest_note 去关键词 ⇒ F2 必红
    c17 = _copy.deepcopy(card)
    c17["honest_note"] = note.replace("零量子 SDK", "")
    probe("G17 honest_note 抹掉「零量子 SDK」⇒ F2 必红", not _honest_ok(c17))

    # G18 零重计算：往 j2_case.py 顶层注入 `import numpy` ⇒ F5 必红
    probe("G18 顶层注入 `import numpy` ⇒ F5 必红（零重计算红线）",
          not _imports_ok({"numpy"} | top_mods))

    # G19 还原完整性
    probe("G19 还原完整性：探针退出后复跑仍无坏路径 ∧ 别名绑定仍在 ∧ CASE_MAP 仍在",
          _bad_paths(card, rbody) == [] and "idf=d.identity||{}" in rbody
          and '"#sec-j2": "runJ2"' in html)

    # 🔴 G20 探针条数自洽：**机器数出的**探针数 == 卡内 `span.probe_mutations`
    check("G20 探针条数自洽：实际登记 %d 条 == 卡内 span.probe_mutations=%d（防两处手写漂移）"
          % (len(_probe_n), span["probe_mutations"]),
          len(_probe_n) == span["probe_mutations"],
          "登记：%s" % [n.split()[0] for n in _probe_n])

    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
