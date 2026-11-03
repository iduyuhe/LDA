"""门禁：**对拍隔离**（xcheck isolation）—— 把「自主可控」红线从态度变成机核判据。

═══════════════════════════════════════════════════════════════════════════════
为什么要有这道门禁
───────────────────────────────────────────────────────────────────────────────
要做「可与商业工具对拍」的工具，就必须引入外部参考实现（OpenROAD / OpenSTA /
Yosys / Meep / SAX …）。这件事**本身不损害自主可控** —— 损害自主的是下面四种滑移：

  ① **角色滑移**：把外部工具的结果当 golden / ORACLE 存进账本 ⇒ 判决权实质交出；
  ② **依赖滑移**：主链 import 外部包 ⇒ 环境缺它就跑不动（供应链绑架）；
  ③ **口径滑移**：为了缩小差异去改自己的定义 ⇒ 从「独立实现」变成「模仿」；
  ④ **证据滑移**：报告写「与 X 一致 ⇒ 正确」⇒ 裁判权递出去了。

本门禁把 ① 与 ② 变成**结构性判据**；③ ④ 由 P3 / P5 机器守
（v0.9.364 对拍框架 `lda_l2/ecore/dxcheck.py` 落地后启用，不再是占位）。

🔴 **关键设计：不另造黑名单，直接读既有的主权分级表**（`lda_pdk/sovereign_deps.py`
的 `SOVEREIGN_DEPS`，A/B/C 三级，来自战略审计 LDA-ST-001）。理由：
  · 两份名单必然漂移（本仓已踩过多次「两份真源」的坑）；
  · 既有表已经写明了「B 级借今踢后（先当候选、后自研替换）」的策略，
    门禁要做的是**守住那个策略**，而不是另立一套更严或更松的规矩。

═══════════════════════════════════════════════════════════════════════════════
判据（P1 / P2 / P3 / P4 / P5 全部启用）
───────────────────────────────────────────────────────────────────────────────
**P1 角色判据（账本）**：`lda/reports/*.json` 里，外部工具名若出现在
  `golden / golden_fn / source / evidence / verified_by / provenance` 这类**判定位** ⇒ 违例
  （不论 A 级还是 B 级 —— golden 只能是闭式物理律或公开实测语料）。
  出现在 `candidate` ⇒ 允许（这正是「独立候选路径」的正当用法），但：
    · A 级（永不借）⇒ 违例；
    · B 级若未登记可替换路径（`fork_to` 为空）⇒ 违例；
    · 名字查不到主权分级（"?"）⇒ 违例（点名却未登记 = 漏登记）。
  出现在 `oracle / note / honest_* / disclosure` ⇒ 不判（叙述自由）。

**P2 依赖判据（主链）**：`lda_l2/**` 与 `lda_pdk/**` 不得 `import` 任何外部工具包。

**P4 缺席可运行**：`CORE_SMOKES` 不得包含对拍脚本；若将来加入 `run_xcheck_*.py`，
其源码必须有 **SKIP 分支**（参考工具缺席时 `SKIP` 且 rc=0），否则「不依赖」无法机核。

**P3 对拍只读文本输出（已启用 · v0.9.364）**：对拍框架不得 `import` 任何外部工具包，
  只能经**独立进程 + 文本**交换；工具缺席时通道降级为 `unavailable`（绝不回落到猜值）。
  判据 P3 用 AST 扫 `dxcheck.py` 的顶层 import；P3c 用合成 `import opensta` 反证判据不空转。

**P5 差异表归因非空且非借口（已启用 · v0.9.364）**：差异表每行 `attribution` 必须非空、
  且落在**闭式词表**（`dxcheck.ATTRIBUTION_CODES`）内；写「参考工具如此」这类把判决权
  交给外部工具的「解释」⇒ 必红。P5b 为该禁令的反向探针。

═══════════════════════════════════════════════════════════════════════════════
诚实边界
───────────────────────────────────────────────────────────────────────────────
· 本门禁是**结构/文本判据**，不是语义证明：它能抓「把外部工具写在 golden 位」，
  抓不到「抄了算法但改了变量名」这类实现污染 —— 那要靠代码审查与 §四 的「借规范不借代码」纪律；
· 别名表（`ALIASES`）是人工维护的**规范化映射**（`Tidy3D`→`tidy3d` 这类，不是新名单），
  由 P2c 机核「每个别名都能回查到主权分级」，防止别名成为绕过通道；
· 判据成立的前提是 `SOVEREIGN_DEPS` 本身准确 —— 它的准确性由既有 D-93 报告守（不在本门禁范围）。
"""
from __future__ import annotations

import ast
import glob
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_pdk import sovereign_deps as SD         # noqa: E402

_FAILED: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FAILED)
T0 = time.time()
AN_ELAPSED_MAX_S = 60.0

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

#: 注册表条目名 → 常见写法/包名（**只做规范化，不是第二份名单**；P2c 机核回查）
ALIASES = {
    "Lumerical (Ansys)": ["lumerical", "ansys", "lumapi"],
    "Synopsys": ["synopsys", "dc_shell", "pt_shell", "primetime", "icc2", "ic_compiler"],
    "Cadence": ["cadence", "virtuoso", "innovus", "genus", "spectre", "stratus"],
    "Siemens (Calibre)": ["calibre", "siemens", "questa"],
    "GDSFactory+商业 NDA-PDK": ["nda-pdk", "nda_pdk"],
    "gdsfactory 内核": ["gdsfactory", "gdstk", "gdspy"],
    "Meep": ["meep", "pymeep"],
    "DEVSIM (TCAD 内核)": ["devsim"],
    "KLayout": ["klayout", "pya"],
    "SAX": ["sax"],
    "MPB": ["mpb"],
    "Nazca": ["nazca"],
    "Tidy3D": ["tidy3d"],
    # v0.9.359：数字后端开源参考（对拍用）。这四个条目由 P1e「点名即须登记」逼出来
    # 补进 `SOVEREIGN_DEPS` —— 既有 17 条只覆盖光/量子域。
    "OpenROAD": ["openroad"],
    "OpenSTA": ["opensta"],
    "Yosys": ["yosys"],
    "nextpnr": ["nextpnr"],
}

#: 一旦出现在这些**判定位**，就说明 golden/来源被外部工具占据 ⇒ 违例（A/B 一律）
GOLDEN_FIELDS = ("golden", "golden_fn", "source", "evidence", "verified_by", "provenance")
#: **实际使用位**：B 级允许（这正是「独立候选」的正当用法），A 级与未登记违例
USE_FIELDS = ("candidate", "oracle", "depends_on", "requires", "tool", "uses",
              "imports", "reference")
#: 🔴 其余字段（`note` / `honest_boundary` / `disclosure` / …）**一律不判**。
#: 理由：诚实边界的作用正是声明「**我们不用**某工具」，例如「非 NDA PDK」。
#: 初版把这类字段也判红 ⇒ 4 个 `ecosystem_d9*.json` 的 `honest_boundary` 全报
#: `nda-pdk 是 A 级` —— 那是把**免责声明**当成**依赖证据**，典型的「词出现 ≠ 角色不对」。
#: 判据只认「角色位置」，不认「词出现」，这是本门禁最关键的一条口径。

_ALIAS_TO_NAME = {}
for _name, _als in ALIASES.items():
    for _a in _als:
        _ALIAS_TO_NAME[_a.lower()] = _name


def classify(alias: str) -> str:
    """别名 → 主权分级（A/B/C）；未登记返回 '?'。"""
    nm = _ALIAS_TO_NAME.get(alias.lower())
    if nm is None:
        return "?"
    return SD.classify_dependency(nm)


def registry_name(alias: str):
    return _ALIAS_TO_NAME.get(alias.lower())


def find_aliases(text: str) -> set:
    low = text.lower()
    return {a for a in _ALIAS_TO_NAME if a in low}


def _field_of(path: str) -> str:
    last = path.rsplit("/", 1)[-1]
    return last.split("[")[0].strip().lower()


def scan_report_obj(obj, path="", out=None) -> list:
    """递归扫描一个报告对象，返回违例列表 [(path, alias, cls, 原因)]。"""
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            scan_report_obj(v, path + "/" + str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_report_obj(v, path + "[%d]" % i, out)
    elif isinstance(obj, str):
        field = _field_of(path)
        for a in find_aliases(obj):
            cls = classify(a)
            if field in GOLDEN_FIELDS:
                out.append((path, a, cls, "外部工具出现在判定位 %r" % field))
            elif field in USE_FIELDS:
                if cls == "A":
                    out.append((path, a, cls, "A 级（永不借）出现在 %r" % field))
                elif cls == "?":
                    out.append((path, a, cls, "未在主权注册表中登记"))
                elif cls == "B":
                    nm = registry_name(a)
                    d = next((x for x in SD.SOVEREIGN_DEPS if x.name == nm), None)
                    if d is not None and not d.fork_to:
                        out.append((path, a, cls, "B 级缺可替换路径 fork_to"))
    return out


def scan_reports(root: str) -> list:
    """扫一个目录下的 *.json 报告。"""
    bad = []
    for f in sorted(glob.glob(os.path.join(root, "*.json"))):
        try:
            obj = json.load(io.open(f, encoding="utf-8", errors="replace"))
        except Exception:                       # noqa: BLE001
            continue
        for v in scan_report_obj(obj, ""):
            bad.append((os.path.basename(f),) + v)
    return bad


def scan_imports(roots) -> list:
    """扫一组源码根，找 `import <外部工具包>`。"""
    bad = []
    for root in roots:
        for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
            try:
                tree = ast.parse(io.open(f, encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue
            names = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        names.add(a.name.split(".")[0])
                elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
                    names.add(n.module.split(".")[0])
            for nm in sorted(names & set(_ALIAS_TO_NAME)):
                try:
                    rel = os.path.relpath(f, _REPO)
                except ValueError:                  # 跨盘（临时目录在 C:）⇒ 用绝对路径
                    rel = f
                bad.append((rel, classify(nm), registry_name(nm)))
    return bad


def core_smokes() -> list:
    """从 `run_ci_regression.py` 源码抽 CORE_SMOKES 条目（AST，不执行）。"""
    path = os.path.join(_HERE, "run_ci_regression.py")
    tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read())

    def _elts(val):
        if isinstance(val, (ast.List, ast.Tuple)):
            return [e.value for e in val.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        return None

    for n in ast.walk(tree):
        # 🔴 两种赋值形态都要认：`CORE_SMOKES = [...]`（Assign）与
        # `CORE_SMOKES: List[str] = [...]`（AnnAssign）。首版只认 Assign，
        # 而真源是**带类型注解**的那种 ⇒ 抽到 0 条 ⇒ P4 恒真（空集永不含对拍脚本）、
        # 判据变成假绿。这是「判据恒真」的教科书案例，由 K0b 的下界断言兜住。
        if isinstance(n, ast.AnnAssign):
            tgt = getattr(n.target, "id", "")
            if tgt == "CORE_SMOKES":
                got = _elts(n.value)
                if got is not None:
                    return got
        elif isinstance(n, ast.Assign):
            if any(getattr(t, "id", "") == "CORE_SMOKES" for t in n.targets):
                got = _elts(n.value)
                if got is not None:
                    return got
    return []


#: 🔴 **只认「外部工具对拍」的两种特征，不认 `crosscheck`**：
#: `run_benchmark_crosscheck_report.py` / `run_crosscheck_flywheel_smoke.py` 是
#: **LDA 内部的跨源对照**（两条独立实现互核），那是在**增强**独立性，恰恰该留在 CORE。
#: 首版把 `crosscheck` 也当外部对拍 ⇒ 2 道内部门禁被误判（把「自证独立」当「外部依赖」）。
#: 外部对拍的识别因此依赖两条：① 出现工具名；② 约定前缀 `xcheck_`（写进文档，由 P3 落地时补 AST 判据）。
XCHECK_PAT = ("xcheck", "openroad", "opensta", "yosys", "nextpnr", "meep", "sax",
              "tidy3d", "klayout", "calibre", "innovus", "icc2", "primetime")

#: 本门禁自身（名字里就有 xcheck），不参与自指判定
SELF = "run_xcheck_isolation_smoke.py"


def xcheck_entries(names) -> list:
    out = []
    for nm in names:
        if nm == SELF:
            continue
        low = nm.lower()
        if any(p in low for p in XCHECK_PAT):
            out.append(nm)
    return out


def main() -> int:
    reports_dir = os.path.join(_REPO, "lda", "reports")

    # ── P1 角色判据：现状 ─────────────────────────────────────────────
    bad = scan_reports(reports_dir)
    check("P1 账本角色：外部工具**不出现在 golden/source/evidence 判定位**（扫描 %d 个报告）"
          % len(glob.glob(os.path.join(reports_dir, "*.json"))),
          not bad, "违例 %d：%s" % (len(bad), bad[:3]))

    # 正当用法不误报：B4 锚把 SAX 放在 candidate/oracle、golden 是解析解
    ok_cand = not scan_report_obj(
        {"results": [{"golden": 9.14, "source": "physical-law",
                      "candidate": 9.14760171, "oracle": "analytical(ring)/sax"}]})
    check("P1b 不误报：外部工具作**独立候选**（candidate/oracle）是正当用法，不得判红",
          ok_cand, "误报")

    # 反向探针 1：B 级工具写进 golden ⇒ 必红
    n_b = len(scan_report_obj({"results": [{"golden": 1.0, "source": "meep"}]}))
    check("P1c 反向：B 级工具（Meep）出现在 `source/golden` 位 ⇒ 必红（golden 只能是物理律/实测）",
          n_b > 0, "未报 ⇒ 判据失靶")

    # 反向探针 2：A 级工具当候选 ⇒ 必红
    n_a = len(scan_report_obj({"results": [{"golden": 1.0, "candidate": "calibre 抽取"}]}))
    check("P1d 反向：A 级工具（Calibre，永不借）即便只当候选 ⇒ 必红",
          n_a > 0, "未报 ⇒ A 级豁免被打开")

    # 反向探针 3：点名却未登记 ⇒ 必红。
    # 🔴 探针靠**临时把 SAX 从注册表摘掉**来造，而不是挑一个「恰好没登记」的真实工具：
    # 后者会随登记表变化而失效（本轮就发生了：OpenROAD 一登记，原探针立刻变绿 ⇒ 探针失靶）。
    _saved = SD.SOVEREIGN_DEPS
    try:
        SD.SOVEREIGN_DEPS = [d for d in _saved if d.name != "SAX"]
        n_u = len(scan_report_obj({"results": [{"golden": 1.0, "candidate": "sax 结果"}]}))
    finally:
        SD.SOVEREIGN_DEPS = _saved
    n_u_ok = len(scan_report_obj({"results": [{"golden": 1.0, "candidate": "sax 结果"}]})) == 0
    check("P1e 反向：注册表里查不到的工具名（临时摘掉 SAX）出现在候选位 ⇒ 必红；"
          "还原后不报（证明判据读的是注册表、不是硬编码名单）",
          n_u > 0 and n_u_ok, "未报=%d 还原后误报=%s" % (n_u, not n_u_ok))

    # ── P2 依赖判据 ──────────────────────────────────────────────────
    roots = [os.path.join(_REPO, "lda", "lda_l2"), os.path.join(_REPO, "lda", "lda_pdk")]
    imp = scan_imports(roots)
    check("P2 主链不 import 外部工具包（扫 lda_l2/ + lda_pdk/ 共 %d 个文件）"
          % sum(len(glob.glob(os.path.join(r, "**", "*.py"), recursive=True)) for r in roots),
          not imp, "命中 %d：%s" % (len(imp), imp[:3]))

    # 反向探针：临时文件里的 import 必被扫到
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        with io.open(os.path.join(td, "_probe.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("import sax\n")
        probe = scan_imports([td])
    check("P2b 反向：源码里 `import sax` ⇒ 必被扫到（证明判据不是空转）",
          len(probe) == 1 and probe[0][1] == "B", "probe=%s" % (probe,))

    # P2c 别名表自洽：每个别名都要能回查到主权分级（防别名成为绕过通道）
    unresolved = sorted({a for a in _ALIAS_TO_NAME if classify(a) == "?"})
    bad_fork = sorted({a for a in _ALIAS_TO_NAME
                       if classify(a) == "B"
                       and not getattr(next((x for x in SD.SOVEREIGN_DEPS
                                             if x.name == registry_name(a)), None),
                                       "fork_to", "")})
    check("P2c 别名表自洽：%d 个别名**全部**能回查主权分级（未登记 %d · B 级缺替换路径 %d）"
          % (len(_ALIAS_TO_NAME), len(unresolved), len(bad_fork)),
          not unresolved and not bad_fork,
          "unresolved=%s bad_fork=%s" % (unresolved, bad_fork))

    # ── P4 缺席可运行 ────────────────────────────────────────────────
    core = core_smokes()
    xc = xcheck_entries(core)
    check("P4 CORE_SMOKES（%d 条）**不含**对拍/参考工具脚本 ⇒ 参考工具缺席时全量 CI 仍全绿"
          % len(core), not xc, "命中 %s" % (xc,))

    check("P4a 抽取到 CORE_SMOKES **%d 条**（下界 300）—— 防「抽空 ⇒ 空集永合规 ⇒ 判据恒真」"
          % len(core), len(core) >= 300, "只抽到 %d 条" % len(core))

    inner = [n for n in core if "crosscheck" in n.lower()]
    check("P4c 内部**跨源对照**（两条独立实现互核）留在 CORE（%d 道：%s）—— "
          "那是增强独立性，不是外部依赖" % (len(inner), ", ".join(inner[:3] or ["无"])),
          True, "")

    n_probe = len(xcheck_entries(core + ["run_xcheck_openroad_smoke.py"]))
    check("P4b 反向：名单里塞一个对拍脚本 ⇒ 必红（证明 P4 不是恒真）",
          n_probe > 0, "未报")

    # ── P3 对拍只读文本输出（v0.9.364 启用：对拍框架 dxcheck 落地）────
    from lda_l2.ecore import dxcheck as _X

    def _ext_imports(src):
        """返回源码里命中的外部工具包顶层名（合成源码也走这条，供反向探针）。"""
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return ["<syntax-error>"]
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and not n.level and n.module:
                mods.add(n.module.split(".")[0])
        return sorted(m for m in mods if m.lower() in set(_ALIAS_TO_NAME))

    _dxc_src = io.open(os.path.join(_HERE, "lda_l2", "ecore", "dxcheck.py"),
                       encoding="utf-8", errors="replace").read()
    _hit3 = _ext_imports(_dxc_src)
    check("P3 对拍只读文本输出：框架不 import 任何外部工具包（AST 扫 dxcheck.py）",
          not _hit3, "命中 %r" % (_hit3,))
    _chan = _X.run_reference_text("__no_such_tool__", ["-v"])
    check("P3b 参考通道只经独立进程 + 文本，且缺席 ⇒ unavailable（不回落猜值）",
          _chan["status"] == "unavailable" and _chan["text"] is None,
          "chan=%r" % (_chan,))
    check("P3c 反向：合成源码 `import opensta` ⇒ 扫描器必报（证明判据不空转）",
          bool(_ext_imports("import opensta\n")), "")

    # ── P5 差异表每行归因非空且非借口（v0.9.364 启用）──────────────────
    from lda_l2.ecore import dverilog as _V

    _tbl = _X.xcheck(_V.parse(_V.SAMPLE_VERILOG), subject="c17")
    _rows = _tbl["rows"]
    _bad5 = [r["metric"] for r in _rows
             if r["attribution"]["code"] not in _X.ATTRIBUTION_CODES
             or not r["attribution"]["detail"].strip()]
    check("P5 差异表每行 attribution 非空 ∧ 在闭式词表（%d 行 · %d 个码）"
          % (len(_rows), len(_X.ATTRIBUTION_CODES)),
          bool(_rows) and not _bad5, "bad=%r" % (_bad5,))
    import copy as _copy
    _t2 = _copy.deepcopy(_tbl)
    _t2["rows"][0]["attribution"]["detail"] = "参考工具如此，所以没问题"
    check("P5b 反向：归因写「参考工具如此」⇒ 检测器必报（判决权不得交给参考工具）",
          bool(_X.validate_table(_t2)), "")

    dt = time.time() - T0
    check("P0 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.2f s" % dt)

    print()
    print("  [角色] 外部工具只能当**候选**，不能当 golden（B4 锚即正例：golden=解析解、candidate=SAX）")
    print("  [依赖] 主链零外部工具 import；对拍脚本不得进 CORE（缺席必须可跑）")
    print("  [登记] 未在主权注册表出现的工具名 ⇒ 判红（点名即须登记）")
    print("  [已启用] P3 只读文本输出（框架零外部 import + 只经独立进程）"
          " · P5 差异表归因非空且不得为「参考工具如此」")
    print()
    if _FAILED:
        print("xcheck isolation 有红色：%s" % ", ".join(_FAILED))
        return 1
    print("对拍隔离全绿 · 自主可控红线由机器守：外部工具当尺子，不当裁判")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
