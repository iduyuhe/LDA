"""v0.9.131 P2「让别人能用」smoke（指标 M5 · M8 · 里程碑 M-2「外部可用」）。

P2 的四件（T2.1 修文档致命错 / T2.2 零基础上手 / T2.3 API 参考 / T2.4 环境变量）
都是**文档与可用性**工作 —— 这类工作最容易「写完就漂移」。本门禁把它们钉成判据：

  ① **文档里的仓库内路径必须真实存在**（T2.1）
     历史致命错：README/一页纸 写 `examples/cli_check_example.json`，实为
     `lda/examples/cli_check_example.json` ⇒ 照抄首条命令即失败。
  ② **文档里的 `lda <子命令>` 必须与 argparse 真实子命令一致**，且 `lda design`
     的签名是 `<kind> --target <float>`（旧文档写成 `--kind X --params '{...}'` 照抄必错）。
  ③ **解释器口径唯一**：不得再出现第二口径（3.14.3 等）；`pyproject.toml` 的
     `requires-python` 与 classifiers 不得自相矛盾。
  ④ **零基础教程存在且步骤 ≤5**（T2.2 · M5 ≤5 步）：QUICKSTART 的步骤按标题机器可数，
     每步必须有可复制的命令块。
  ⑤ **API 参考与代码同源**（T2.3）：重跑生成器 `--check` 必须零漂移 ⇒ 杜绝手改。
  ⑥ **M8 ≥ 80%**：端点描述覆盖率**由端点逐条重算**（不信 json 里的 `counts` 自述块），
     并反向断言 `counts` ≡ 重算值 —— 突变探针实测：抹空 30/138 条描述而 `counts` 仍
     自称 138 时，读自述块的写法会照样绿（判据被「自称数字」骗过）。含描述来源分布，
     未描述项如实计入缺口。
  ⑦ **端点集合双向一致**：参考里的路由集合 ≡ `routes.py` 的 `GET/POST_ROUTES`
     + `GET/POST_PREFIX`（新增端点没进参考即红；参考里凭空多出路由也红）。
  ⑧ **环境变量文档完整性**（T2.4）：`ast` 穷举 `lda/**/*.py` + `scripts/**/*.py` 中
     从进程环境读取的 `LDA_*` 变量，任一在 `docs/ENVIRONMENT.md` 里**没有表格行**即红
     （只「文中提过一句」不算 —— 不告诉读者默认值与作用等于没有文档）。
  ⑨ **过期清单已被替换**（T2.3）：部署说明不得再写「B1–B11 / 七面板 / 未做鉴权」，
     且必须指向自动生成的参考。
  ⑩ **入口提示存在**（T2.2）：未登录时页面须给出**事前**提示（而非只等 401）。
  ⑪ **无作者机器路径**（本轮新增的防复发判据）：`lda/**/*.py` 的**代码字面量**
     （非 docstring）不得含 `C:/Users/Administrator` / `D:/agent_LDA` ——
     旧 `run_cli_smoke.py` 把作者解释器绝对路径写成默认值，外部贡献者跑
     `--tag core` 会直接假红（「别人不能用」的典型硬阻塞）。
  ⑫ **红线**：生成器零 LLM 依赖；模板化产物不得把 LLM 说成判决者。

运行：python run_p2_usability_smoke.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check       # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

_REPO = os.path.dirname(_HERE)
_PY = sys.executable

# 受门禁守护的「面向外部」文档（CHANGELOG 属历史记录，不在口径扫描范围）
_EXT_DOCS = [
    "README.md", "QUICKSTART.md", "CONTRIBUTING.md",
    "examples/README.md", "examples/sovereign_evidence/README.md",
    "LDA_一页纸_概览.md", "LDA_D-13_WebUI内网部署说明.md",
    "docs/ENVIRONMENT.md", "docs/API_REFERENCE.md",
]
# 生成的产物目录（文档里出现属正常，不做存在性要求）
_GENERATED_PREFIX = ("reports/", "outputs/", "dist/", "build/", ".workbuddy/")


def _read(rel):
    p = os.path.join(_REPO, rel)
    if not os.path.isfile(p):
        return ""
    return open(p, encoding="utf-8", errors="replace").read()


def _exists(rel):
    return os.path.exists(os.path.join(_REPO, rel))


# 「披露段」：只交代历史 / 旧版错在哪，**必然逐字引用旧错词**，不能按现役口径判。
_DISCLOSURE_HEAD = re.compile(
    r"^\s*#{1,6}\s*(?:\d+[.、]?\s*)?(?:作废说明|变更记录|更新日志|修订记录|历史)")


def _active_lines(src):
    """只留**当前口径**的行，剥掉三类「披露性内容」。

    🔴 为什么必须剥（三条都是实测踩出来的假红）：

    * **行首 `>` 引用块** —— 本仓 `README.md` 的引用块是**逐版 changelog**，如实引述
      当时的文案：含已被修正的旧口径（`requires-python 3.11` / `CI 3.13.14` /
      已随 vendor 清理移除的 `vendor/INSTALL.md`）。把历史引述当现役承诺判，
      等于要求「删掉变更记录」才能过门禁。
    * **`## 作废说明` 小节** —— 整节的作用就是交代上一版哪儿错了，必然逐字写出旧错词
      （`B1–B11` / `七面板` / `未做鉴权` / `lda_cuda_venv`）。若不豁免，门禁会逼着把
      **披露**删掉 —— 那比留着旧错更糟。
    * **含「作废」的单行** —— 正文里的就地披露（§2 注「上一版写的 Python 3.11 作废」）。

    剥掉后剩下的就是「读者会照着做」的部分；真正的口径回归（正文里写 3.11 要求、
    正文里列旧端点表）仍会被抓住。
    """
    out, dropping = [], False
    for raw in src.splitlines():
        if raw.lstrip().startswith("#"):
            dropping = bool(_DISCLOSURE_HEAD.match(raw))
        if dropping or raw.lstrip().startswith(">") or "作废" in raw:
            continue
        out.append(raw)
    return out


def _load_generator():
    """加载 `scripts/gen_api_reference.py`（拿 `wildcard_patterns` 等唯一真相源定义）。

    不在这儿重抄一遍通配渲染规则 —— 两处口径必然分裂，正是本仓铁律「判据与生产
    必须共用同一定义」要防的。
    """
    import importlib.util
    p = os.path.join(_REPO, "scripts", "gen_api_reference.py")
    spec = importlib.util.spec_from_file_location("_gen_api_ref_for_smoke", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- ① 路径真实性
_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:lda|examples|docs|scripts|vendor)/[\w./\-]+"
    r"\.(?:json|py|md|gds|csv|toml|service|html|txt))")


def check_doc_paths():
    """扫描文档里引用的仓库内路径（只扫**当前口径**行，见 `_active_lines`）。

    真正的「照抄必失败」路径都在正文与代码块里，仍被覆盖。
    """
    bad, scanned = [], 0
    for doc in _EXT_DOCS:
        src = _read(doc)
        if not src:
            bad.append("%s(缺文件)" % doc)
            continue
        for raw in _active_lines(src):
            for m in _PATH_RE.finditer(raw):
                rel = m.group(1)
                if rel.startswith(_GENERATED_PREFIX) or "<" in rel or "*" in rel:
                    continue
                scanned += 1
                if not _exists(rel):
                    bad.append("%s -> %s" % (doc, rel))
    check("① 文档引用的仓库内路径全部真实存在", not bad,
          "扫 %d 处，坏 %d：%s" % (scanned, len(bad), bad[:5]))


def check_doc_path_regressions():
    """把两个血案路径钉死：错的形态不得再出现，对的形态必须出现。"""
    joined = {d: _read(d) for d in _EXT_DOCS}
    wrong = [d for d, s in joined.items()
             if re.search(r"(?<!lda/)\bexamples/cli_check_example\.json", s)]
    right = [d for d, s in joined.items() if "lda/examples/cli_check_example.json" in s]
    check("① 血案路径 `examples/cli_check_example.json` 已绝迹", not wrong,
          "仍出现于 %s" % wrong)
    check("① 正确路径 `lda/examples/cli_check_example.json` 已就位", bool(right),
          "出现于 %s" % right)
    old_sig = [d for d, s in joined.items()
               if re.search(r"lda\s+design\s+--kind", s)]
    check("① 血案签名 `lda design --kind X` 已绝迹", not old_sig, "仍出现于 %s" % old_sig)


# ---------------------------------------------------------------- ② 命令签名
def _cli_help(args):
    r = subprocess.run([_PY, os.path.join(_HERE, "lda_design", "cli.py")] + args,
                       capture_output=True, text=True, errors="replace", cwd=_HERE,
                       timeout=180)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def check_commands():
    rc, out = _cli_help(["--help"])
    subs = set()
    m = re.search(r"\{([a-z,]+)\}", out)
    if m:
        subs = set(m.group(1).split(","))
    check("② `lda` 子命令可枚举且含 build/design/check/report/gf",
          rc == 0 and {"build", "design", "check", "report", "gf"} <= subs,
          "rc=%d 子命令=%s" % (rc, sorted(subs)))

    used = set()
    for doc in _EXT_DOCS:
        for mm in re.finditer(r"(?<![\w.-])lda[ \t]+([a-z_]+)\b", _read(doc)):
            used.add(mm.group(1))
    unknown = sorted(used - subs - {"build", "design", "check", "report", "gf"})
    check("② 文档中出现的 `lda <子命令>` 全在真实子命令集内",
          not unknown, "未知=%s" % unknown)

    rc2, out2 = _cli_help(["design", "--help"])
    ok_sig = ("<kind>" in out2 or "kind" in out2) and "--target" in out2
    check("② `lda design` 真实签名是 `<kind> --target <float>`",
          rc2 == 0 and ok_sig, "rc=%d" % rc2)
    wrong_use = [d for d in _EXT_DOCS
                 if re.search(r"lda\s+design\s+--", _read(d))]
    check("② 文档没有 `lda design --xxx` 形式的错误用法", not wrong_use,
          "出现于 %s" % wrong_use)


# ---------------------------------------------------------------- ③ 解释器口径
def check_interpreter():
    bad = []
    for doc in _EXT_DOCS:
        s = "\n".join(_active_lines(_read(doc)))
        for ver in ("3.14", "3.11"):
            if re.search(r"Python\s*%s|%s[/\\\\]" % (ver, ver), s):
                bad.append("%s 提到 %s" % (doc, ver))
    check("③ 面向外部文档无第二解释器口径（不出现 3.14 / 3.11 要求）",
          not bad, "%s" % bad[:4])

    pp = _read("pyproject.toml")
    m = re.search(r'requires-python\s*=\s*"([^"]+)"', pp)
    req = m.group(1) if m else ""
    cls = re.findall(r'"Programming Language :: Python :: (3\.\d+)"', pp)
    ok = req.replace(" ", "") in (">=3.12", ">=3.13", ">=3.12,<4") and "3.11" not in cls
    check("③ pyproject `requires-python` 与 classifiers 不自相矛盾",
          ok, "requires-python=%r classifiers=%s" % (req, cls))


# ---------------------------------------------------------------- ④ QUICKSTART
def check_quickstart():
    src = _read("QUICKSTART.md")
    if not src:
        check("④ QUICKSTART.md 存在", False, "缺文件")
        return
    steps = re.findall(r"^##\s*步骤\s*(\d+)", src, re.M)
    nums = [int(x) for x in steps]
    check("④ 零基础教程步骤数 ≤5（M5）", 0 < len(nums) <= 5,
          "步骤 = %s" % nums)
    check("④ 步骤编号连续从 1 开始", nums == list(range(1, len(nums) + 1)),
          "步骤 = %s" % nums)
    # 每步都要有可复制命令块
    blocks = src.count("```bash")
    check("④ 每步都有可复制命令块（```bash）", blocks >= len(nums),
          "bash 块 %d 个 / 步骤 %d 个" % (blocks, len(nums)))
    check("④ 教程覆盖 P1 的单命令 `lda build`（M1 能力要能被外部用到）",
          "lda build" in src and "cli_build_goal.json" in src)
    # 使用者的第一批产物要能对上
    check("④ 教程给出预期产物名（.gds + 签核报告）",
          ".gds" in src and "signoff" in src)


# ---------------------------------------------------------------- ⑤⑥⑦ API 参考
def check_api_reference():
    rc = subprocess.run([_PY, os.path.join(_REPO, "scripts", "gen_api_reference.py"),
                         "--check"], capture_output=True, text=True,
                        errors="replace", cwd=_REPO, timeout=600).returncode
    check("⑤ API 参考与代码同源（重跑生成器零漂移 ⇒ 不许手改）", rc == 0,
          "gen --check rc=%d" % rc)

    jp = os.path.join(_REPO, "docs", "api_reference.json")
    if not os.path.isfile(jp):
        check("⑥ M8 端点描述覆盖率 ≥80%", False, "缺 api_reference.json")
        return
    ref = json.load(open(jp, encoding="utf-8"))
    eps = ref["endpoints"]
    c = ref["counts"]
    # 🔴 覆盖率**由端点逐条重算**，不信 json 里的 `counts` 自述块 —— 突变探针实测：
    #   把 30/138 条端点的 description 抹空、而 `counts.described` 仍写 138 ⇒
    #   旧判据读自述块照样绿（**判据被「自称数字」骗过**，典型「标签≠行为」）。
    n_total = len(eps)
    n_described = sum(1 for e in eps if e["description"] and e["source"] != "none")
    cov = (n_described / n_total) if n_total else 0.0
    check("⑥ M8 端点描述覆盖率 ≥80%（由端点逐条重算，不信 counts 自述）",
          cov >= 0.80,
          "%.1f%% (%d/%d) · 未描述 %d" % (cov * 100, n_described, n_total,
                                          n_total - n_described))
    check("⑥ counts 块 ≡ 端点逐条重算（防「自称 100%」）",
          c.get("total") == n_total and c.get("described") == n_described
          and c.get("undescribed") == n_total - n_described,
          "counts.total=%s described=%s 重算 total=%d described=%d"
          % (c.get("total"), c.get("described"), n_total, n_described))
    # 描述来源必须全部可溯源到代码（不许出现空描述却被计入）
    srcs = {e["source"] for e in ref["endpoints"]}
    check("⑥ 每条描述都有代码来源（无 none / 无编造）",
          "none" not in srcs and all(e["description"] for e in ref["endpoints"]),
          "来源分布=%s" % sorted(srcs))

    from lda_webui import routes as R       # noqa: E402
    G = _load_generator()
    want = ({("GET", p) for p in R.GET_ROUTES}
            | {("POST", p) for p in R.POST_ROUTES}
            | {("PATCH", p) for p in R.PATCH_ROUTES})
    want_wild = {(m, w)
                 for m, tab in (("GET", R.GET_PREFIX), ("POST", R.POST_PREFIX))
                 for mode, pat, _h in tab for w in G.wildcard_patterns(mode, pat)}
    got_precise = {(e["method"], e["path"]) for e in ref["endpoints"]
                   if not e["wildcard"]}
    got_wild = {(e["method"], e["path"]) for e in ref["endpoints"] if e["wildcard"]}
    missing = sorted(want - got_precise)
    extra = sorted(got_precise - want)
    missing_w = sorted(want_wild - got_wild)
    extra_w = sorted(got_wild - want_wild)
    check("⑦ 参考覆盖路由表**全部**端点（含 PATCH，无漏登记）", not missing,
          "漏 %d：%s" % (len(missing), missing[:4]))
    check("⑦ 参考里没有路由表之外的多余端点", not extra,
          "多 %d：%s" % (len(extra), extra[:4]))
    check("⑦ 前缀/后缀路由逐条进了参考（渲染口径复用生成器函数）", not missing_w,
          "漏 %d：%s" % (len(missing_w), missing_w[:4]))
    check("⑦ 参考里没有路由表之外的多余通配项", not extra_w,
          "多 %d：%s" % (len(extra_w), extra_w[:4]))
    # 鉴权标记必须与闸门集合一致
    heavy = set(R.HEAVY_POST_PATHS)
    mismatch = [e["path"] for e in ref["endpoints"]
                if e["wildcard"] is False
                and ((e["path"] in heavy) != (e["auth"] == "login"))]
    check("⑦ 鉴权标记 ≡ HEAVY_POST_PATHS（重计算闸门口径一致）",
          not mismatch, "不一致 %s" % mismatch[:4])


# ---------------------------------------------------------------- ⑧ 环境变量
def _env_names(root):
    out = set()
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "node_modules", ".cache")]
        for f in fs:
            if not f.endswith(".py"):
                continue
            p = os.path.join(d, f)
            try:
                tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                key = None
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr in ("get", "getenv") and n.args
                        and isinstance(n.args[0], ast.Constant)):
                    key = n.args[0].value
                elif (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                        and isinstance(n.slice.value, str)):
                    key = n.slice.value
                if isinstance(key, str) and key.startswith("LDA_"):
                    out.add(key)
    return out


def check_env_doc():
    names = _env_names(os.path.join(_REPO, "lda")) | _env_names(os.path.join(_REPO, "scripts"))
    doc = _read("docs/ENVIRONMENT.md")
    # 要求「有**表格行**」而非「文中提过」—— 只提一句不告诉读者默认值与作用，
    # 对使用者等于没有文档（突变探针实测：把表格行里的变量名改掉后，
    # 旧判据因「名字在别处（如说明文字）出现过」而漏判）。
    rows = set()
    for ln in doc.splitlines():
        if not ln.lstrip().startswith("|"):
            continue
        for m in re.finditer(r"`(LDA_[A-Z0-9_]+)`", ln):
            rows.add(m.group(1))
    no_row = sorted(n for n in names if n not in rows)
    no_any = sorted(n for n in names if n not in doc)
    check("⑧ 代码里读到的 LDA_* 环境变量全部有**表格行**（含默认值与作用）",
          not no_row,
          "共 %d 个 · 无表格行 %d：%s｜其中文中完全未提及 %d：%s"
          % (len(names), len(no_row), no_row[:6], len(no_any), no_any[:6]))
    check("⑧ 文档声明了扫描口径与数量（防「数字漂了没人管」）",
          "ast" in doc and str(len(names)) in doc,
          "扫描 %d 个 · 文档含「ast」口径=%s · 含总量声明=%s"
          % (len(names), "ast" in doc, str(len(names)) in doc))


# ---------------------------------------------------------------- ⑨ 过期清单
def check_stale_doc():
    d13 = _read("LDA_D-13_WebUI内网部署说明.md")
    body = "\n".join(_active_lines(d13))       # 只判现役口径，不判「作废说明」披露
    stale = [k for k in ("B1–B11", "B1-B11", "七面板", "未做鉴权", "lda_cuda_venv")
             if k in body]
    check("⑨ 部署说明**现役口径**已无过期清单（作废说明段内的披露豁免）",
          not stale, "残留 %s" % stale)
    check("⑨ 部署说明指向**自动生成**的 API 参考（不再手写端点表）",
          "API_REFERENCE.md" in d13 and "gen_api_reference.py" in d13)
    check("⑨ 部署说明有「作废说明」段（说明旧版哪里错、怎么处置）",
          "作废说明" in d13)


# ---------------------------------------------------------------- ⑩ 入口提示
def check_entry_hint():
    h = _read("lda/lda_webui/static/index.html")
    check("⑩ 页面存在未登录入口提示元素（#authHint）", 'id="authHint"' in h)
    check("⑩ 提示由登录态驱动（未登录才显示，非常年挂着）",
          "!LDA_AUTHED" in h and "$('authHint')" in h)
    check("⑩ 提示给出登录去处（可点击 /store.html 链接）",
          'href="/store.html"' in h)
    check("⑩ 提示说明「哪些公开端点免登录」（不是只说需登录）",
          "公开验货端点" in h)


# ---------------------------------------------------------------- ⑪ 作者机器路径
def check_no_author_paths():
    bad = []
    root = os.path.join(_REPO, "lda")
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "node_modules")]
        for f in fs:
            if not f.endswith(".py"):
                continue
            if f == os.path.basename(__file__):
                # 门禁**自身**必须写下被禁字面量才能判它（`"C:/Users/Administrator"`），
                # 否则就是自指假红 —— 自我豁免，并在此显式声明。
                continue
            p = os.path.join(d, f)
            try:
                tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
            except SyntaxError:
                continue
            docstrings = set()
            for n in ast.walk(tree):
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                    ds = ast.get_docstring(n, clean=False)
                    if ds:
                        docstrings.add(ds)
            for n in ast.walk(tree):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    v = n.value
                    if v in docstrings:
                        continue          # docstring 里的示例路径不算「写死」
                    if "C:/Users/Administrator" in v or "D:/agent_LDA" in v:
                        bad.append("%s:%d" % (os.path.relpath(p, _REPO), n.lineno))
    check("⑪ 代码字面量无作者机器路径（外部 clone 不会找不到解释器/路径）",
          not bad, "命中 %s" % bad[:6])
    cs = _read("lda/run_cli_smoke.py")
    check("⑪ run_cli_smoke 的解释器默认值 = 当前解释器（不是写死路径）",
          "os.environ.get(\"LDA_PY\") or sys.executable" in cs)


# ---------------------------------------------------------------- ⑫ 红线
def check_redline():
    g = _read("scripts/gen_api_reference.py")
    ok = ("openai" not in g) and ("lda_agent" not in g) and ("LDA_LLM" not in g) \
        and ("LDA_CS_LLM" not in g)
    check("⑫ 参考生成器零 LLM / 零 Agent 依赖（判决路径外）", ok)
    en = _read("docs/ENVIRONMENT.md")
    check("⑫ 环境变量文档显式声明「LLM 不进判决路径」", "LLM 不进判决路径" in en)
    qs = _read("QUICKSTART.md")
    if qs:
        check("⑫ 上手教程不改写判决口径（不得出现「LLM 判对错」式表述）",
              not re.search(r"LLM[^。\n]{0,12}(判|决定)(对错|正确)", qs))


def main():
    print("=" * 72)
    print("LDA P2「让别人能用」smoke · 文档/可用性判据（M5 · M8）")
    print("=" * 72)
    check_doc_paths()
    check_doc_path_regressions()
    check_commands()
    check_interpreter()
    check_quickstart()
    check_api_reference()
    check_env_doc()
    check_stale_doc()
    check_entry_hint()
    check_no_author_paths()
    check_redline()
    print("\nlda p2 usability smoke：%d PASS / %d FAIL" % (_PASS, _FAIL))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
