# -*- coding: utf-8 -*-
"""smoke 隔离棘轮护栏（v0.9.116 · 源自 `run_tapeout_smoke` 秒级 id 假红血案）。

血案
----
`run_tapeout_smoke.test_empirical_submission_interface` 在 CI 中偶发 `FAILED
(failures=1)`：`AssertionError: 'rejected' != 'accepted_pending'`，reason =
`防重守卫：语料 tapeout-sim-uniq-1789873241 已存在（pending）`。

根因是**两个条件叠加**（缺一不可，已由 2×2 冻结时钟矩阵实测坐实）：

  (R-a) 唯一 id 来自**秒级**时钟 —— `uniq = f"tapeout-sim-uniq-{int(_t.time())}"`；
  (R-b) 防重守卫的 pending 记录**跨进程共享同一个持久库** —— 该 smoke 三处提交
        均**不传 `proposals_path`** ⇒ 落到仓库内 `lda_pdk/empirical_proposals.json`
        （`.gitignore` 忽略的「生态共建社区贡献库」）。

⇒ 同一秒内第二次运行 id 相同 ⇒ 必被防重守卫拒 ⇒ 假红。
⇒ 另有**污染**副作用：实测该文件当日积压 **38 条 pending，100% 为
   `proposed_by="tapeout-smoke"` 的测试残留**（method=simulated，非真实测量）。

🔴 方法论教训（首版证明脚本失败之处）：假红需要 (R-a) 与 (R-b) **同时**成立。
把 store 改成「每跑新建」会切断 (R-b)，旧实现即**不复现**——故证明必须用
「两跑共用同一 store」的真实形态。**复现条件写错 = 证明无效**。

本护栏做什么
------------
把该缺陷的**两个成因**机器化为静态判据（作用域 = `lda/run_*smoke*.py`，
即「测试」而非产品代码：产品可合法使用默认共享库）：

  I1 对 empirical 存储 mutator（`submit_measurement` / `review_measurement` /
     `land_measurement`）的调用**必传**必需 path 关键字 ⇒ 从结构上断绝 R-b
  I2 不得出现 `int(<…>.time())`（**秒级整数时间戳** = 脆弱唯一性来源）⇒ 断绝 R-a
     🔴 只禁「整数化」：`time.time()` 用作**计时差值**（`t0 = time.time()`）合法，
     `time.time_ns()`（纳秒）亦合法 —— 误报会让护栏被绕过或被关停。
  I3 不得调用 `strftime`（秒级字符串时间戳，同族脆弱）
  I6 共享语料库不得含**已知测试署名**的残留（动态）
  I4/I5/I7~I14 扫描自证 / 白名单无悬空 / 反证对照 / 反向测试 / 自食其规则

判据（死标量，LLM 不进判决路径）
--------------------------------
  I1  mutator 缺 path 的调用数 = 0
  I2  `int(<…>.time())` 数 = 0
  I3  `strftime` 调用数 = 0
  I4  扫描非空洞：文件数 ≥ 地板 **且** 本文件确实在扫描结果里（防 glob/walk 失效后
      三项主判据在**空集**上空洞为真 —— 与 v0.9.115 的 G2 同类陷阱）
  I5  豁免登记无悬空项（每条登记必对应一股真实违例；空表 = 零违例）
  I6  共享库中已知测试署名残留 = 0 条
  I7  🔴 **反证对照**：合规样本（显式传 path + `uuid4` + 计时用 `time.time()`）
      ⇒ 必须**零误报**。缺它则「违例判定」恒真即可让全部反向判据假绿
  I8  反向：合成「缺 path」样本 ⇒ I1 必报
  I9  反向：合成 `int(time.time())` 样本 ⇒ I2 必报
  I10 反向：合成 `strftime` 样本 ⇒ I3 必报
  I11 反向：合成含测试署名的库 ⇒ I6 必报
  I12 反证对照：合成仅含合法记录的库 ⇒ I6 必须不报
  I13 自食其规则：本 smoke 自身在 CORE_SMOKES 内
  I14 全量 AST 解析零错误

运行：python run_smoke_isolation_ratchet_smoke.py
"""
from __future__ import annotations

import ast
import glob
import json
import os
import shutil
import tempfile

from lda_harness.smoke_kit import make_check

_HERE = os.path.dirname(os.path.abspath(__file__))       # …/lda
_SELF = "run_smoke_isolation_ratchet_smoke.py"

# empirical 存储 mutator → 其**必需**的 path 关键字（缺则写仓库内共享库）
_MUTATORS = {
    "submit_measurement": ("proposals_path",),
    "review_measurement": ("proposals_path",),
    "land_measurement": ("proposals_path", "corpus_path"),
}

_SHARED_STORE = os.path.join(_HERE, "lda_pdk", "empirical_proposals.json")

# 🔴 已知「只可能来自测试」的署名 ⇒ 共享库中该署名记录数**恒须为 0**。
#    新增测试若用别的署名，请在此登记（I1 已在结构上拦住写入，此处是纵深防御）。
_TEST_AUTHORS = ("tapeout-smoke",)

# 🔴 豁免登记：(rel, kind) → 非空理由。**空表 = 全仓零违例**（v0.9.116 实测）。
#    登记原则：能改成「显式传 path」或「改用 uuid4」的一律改，不登记；
#    确不可改者才登记并写明理由。悬空登记由 I5 判红（防静默放宽）。
_ALLOW: dict = {}

# I4 的**防空洞地板**：只防「globs/walk 失效后判据在空集上空洞为真」，
# 不承担「覆盖度棘轮」职责（smoke 条数的增减由 run_ci_coverage_gate_smoke 管）。
# 取其下界而非精确值，正因它不该在合法增删 smoke 时变红。实测 193（v0.9.116）。
_MIN_SMOKE_FILES = 190

# 🔴 本 smoke **不得**再添本地 `def check`（棘轮精神同 run_helper_dup_ratchet_smoke）
_NP = 0
_NF = 0
check = make_check(globals(), ok_key="_NP", bad_key="_NF", indent="  ",
                   detail_fmt="  —— {d}", detail_on="fail", return_ok=True)


# --------------------------------------------------------------------------- 扫
def _iter_smokes():
    return sorted(glob.glob(os.path.join(_HERE, "run_*smoke*.py")))


def _rel(p):
    return "lda/" + os.path.basename(p)


def _time_calls(node):
    """子树中所有 `<x>.time()` 调用（秒级时间戳来源；`time_ns` 不算）。"""
    for n in ast.walk(node):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "time"):
            yield n


def _violations(rel, src):
    """返回 (违例列表, 解析错误或 None)。违例 = (rel, lineno, kind)。"""
    try:
        tree = ast.parse(src)
    except SyntaxError as ex:
        return [], "SyntaxError: %s" % ex
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = (f.attr if isinstance(f, ast.Attribute)
              else (f.id if isinstance(f, ast.Name) else None))
        if nm in _MUTATORS:
            kw = {k.arg for k in n.keywords if k.arg}
            if any(req not in kw for req in _MUTATORS[nm]):
                out.append((rel, n.lineno, "mutator-no-path"))
        elif nm == "int":
            for t in _time_calls(n):
                out.append((rel, t.lineno, "int-time"))
        elif nm == "strftime":
            out.append((rel, n.lineno, "strftime"))
    return out, None


def scan(paths=None):
    """纯扫描：返回判定所需的全部原始数据（可被反向测试喂合成样本）。"""
    out = {"violations": [], "parse_errs": [], "n_files": 0, "files": [],
           "live_kinds": set()}
    srcs = []
    for p in (_iter_smokes() if paths is None else paths):
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            srcs.append((_rel(p), fh.read()))
    out["files"] = [rel for rel, _s in srcs]
    out["n_files"] = len(srcs)
    for rel, src in srcs:
        vs, err = _violations(rel, src)
        if err:
            out["parse_errs"].append((rel, err))
        out["violations"].extend(vs)
    out["live_kinds"] = {(r, k) for r, _l, k in out["violations"]}
    return out


def judge(sc, allow=None):
    """纯判定：返回 {kind: 违例列表}（已剔除豁免项）。正向/反向共用。"""
    allow = _ALLOW if allow is None else allow
    kept = {}
    for rel, ln, kind in sc["violations"]:
        if (rel, kind) in allow:
            continue
        kept.setdefault(kind, []).append((rel, ln))
    return kept


def shared_residue(path):
    """共享语料库中「已知测试署名」的记录 id 列表。返回 (ids, 说明)。"""
    if not os.path.exists(path):
        return [], "文件不存在（全新工作区 ⇒ 结构上无残留）"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as ex:                                  # noqa: BLE001
        return [], "不可解析：%s" % ex
    items = (data.get("measurements") or []) if isinstance(data, dict) else data
    return [x.get("id") for x in items
            if isinstance(x, dict) and x.get("proposed_by") in _TEST_AUTHORS], "已解析"


# 合成样本（反向测试 + 反证对照共用）
_BAD_NOPATH = (
    "from lda_pdk.empirical import submit_measurement\n"
    "r = submit_measurement({'id': 'x'})\n"
)
_BAD_INTTIME = (
    "import time as _t\n"
    "uniq = 't-%d' % int(_t.time())\n"
)
_BAD_STRFTIME = "import time\nnow = time.strftime('%Y%m%d-%H%M%S')\n"
# 合规样本：显式传 path + uuid4 + **计时用 time.time()**（后者不得误报）
_GOOD = (
    "import os, time, tempfile, uuid\n"
    "from lda_pdk.empirical import submit_measurement, land_measurement\n"
    "tmp = tempfile.mkdtemp()\n"
    "pp = os.path.join(tmp, 'p.json')\n"
    "cp = os.path.join(tmp, 'c.json')\n"
    "uniq = 't-' + uuid.uuid4().hex[:10]\n"
    "submit_measurement({'id': uniq}, proposals_path=pp)\n"
    "land_measurement(uniq, proposals_path=pp, corpus_path=cp)\n"
    "_t0 = time.time()\n"
    "elapsed = time.time() - _t0\n"
)


def main() -> int:
    print("=" * 76)
    print("smoke 隔离棘轮护栏 — 测试不得写共享库 · 不得用秒级时间戳作唯一 id")
    print("=" * 76)

    rc = 0
    sc = scan()
    kept = judge(sc)

    print("  扫描 lda/run_*smoke*.py = %d 个文件 · 原始违例 %d 处 · 豁免 %d 项"
          % (sc["n_files"], len(sc["violations"]), len(_ALLOW)))

    # ---- I1/I2/I3：三项主判据（逐 kind 报） ----
    for kind, label in (
            ("mutator-no-path", "I1 empirical mutator 调用必传 path 关键字"),
            ("int-time", "I2 无 int(<…>.time())（秒级整数时间戳）"),
            ("strftime", "I3 无 strftime 调用（秒级字符串时间戳）")):
        hits = kept.get(kind, [])
        rc |= not check(label, not hits,
                        ("%d 处 %s" % (len(hits), hits[:4])) if hits else "0 处")

    # ---- I4：扫描自证（防空集上空洞为真） ----
    self_seen = ("lda/" + _SELF) in sc["files"]
    rc |= not check("I4 扫描非空洞：文件数 ≥ %d 且本文件确在扫描结果内"
                    % _MIN_SMOKE_FILES,
                    sc["n_files"] >= _MIN_SMOKE_FILES and self_seen,
                    "文件 %d（地板 %d）· 自身在列=%s"
                    % (sc["n_files"], _MIN_SMOKE_FILES, self_seen))

    # ---- I5：豁免登记无悬空项 ----
    stale = [k for k in _ALLOW if k not in sc["live_kinds"]]
    rc |= not check("I5 豁免登记无悬空项（每条登记须对应真实违例）",
                    not stale,
                    ("悬空 %s" % stale) if stale
                    else ("空表（零豁免）" if not _ALLOW else "%d 项均在位" % len(_ALLOW)))

    # ---- I6：共享语料库无已知测试署名残留 ----
    residue, why = shared_residue(_SHARED_STORE)
    rc |= not check("I6 共享语料库无已知测试署名残留（%s）" % "/".join(_TEST_AUTHORS),
                    not residue,
                    ("残留 %d 条 %s" % (len(residue), residue[:4])) if residue
                    else ("%s · 0 条" % why))

    # ---- I7：反证对照（合规样本必须零误报；缺它则反向判据可恒真假绿） ----
    good_vs, gerr = _violations("__good__", _GOOD)
    good_kept = judge({"violations": good_vs})
    rc |= not check("I7 反证对照：合规样本（显式 path + uuid4 + 计时用 time.time）"
                    "零误报",
                    not good_kept and gerr is None,
                    ("误报 %s" % good_kept) if good_kept
                    else "0 处误报（计时用法未误伤）")

    # ---- I8~I10：反向测试（三条合成违例，证明判据真会变红） ----
    for kind, src, label in (
            ("mutator-no-path", _BAD_NOPATH, "I8 反向：缺 proposals_path ⇒ I1 必报"),
            ("int-time", _BAD_INTTIME, "I9 反向：int(time.time()) ⇒ I2 必报"),
            ("strftime", _BAD_STRFTIME, "I10 反向：strftime ⇒ I3 必报")):
        vs, _e = _violations("__syn__", src)
        hit = kind in judge({"violations": vs})
        rc |= not check(label, hit,
                        "合成样本被拦下 ✅" if hit else "!! 未被拦下（判据失效）")

    # ---- I11/I12：共享库残留判据的反向 + 反证对照 ----
    tmpd = tempfile.mkdtemp(prefix="lda_iso_")
    try:
        p_bad = os.path.join(tmpd, "bad.json")
        with open(p_bad, "w", encoding="utf-8") as fh:
            json.dump({"measurements": [
                {"id": "tapeout-sim-uniq-x", "proposed_by": "tapeout-smoke"}]}, fh)
        r_bad, _ = shared_residue(p_bad)
        rc |= not check("I11 反向：库中合成测试署名残留 ⇒ I6 必报",
                        bool(r_bad), ("残留 %s ✅" % r_bad) if r_bad else "!! 未报")

        p_good = os.path.join(tmpd, "good.json")
        with open(p_good, "w", encoding="utf-8") as fh:
            json.dump({"measurements": [
                {"id": "E-REAL-1", "proposed_by": "community"}]}, fh)
        r_good, _ = shared_residue(p_good)
        rc |= not check("I12 反证对照：库中仅合法记录 ⇒ I6 不得误报",
                        not r_good, "0 条（未误报）" if not r_good else "误报 %s" % r_good)
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

    # ---- I13：自食其规则 ----
    try:
        import run_ci_regression as R
        in_core = _SELF in R.CORE_SMOKES
    except Exception as ex:                                  # noqa: BLE001
        in_core = False
        print("    （无法读取 CORE_SMOKES：%s）" % ex)
    rc |= not check("I13 本 smoke 自身在 CORE_SMOKES 内（自食其规则）",
                    in_core, "" if in_core else "门禁自己被漏接！")

    # ---- I14：全量 AST 解析零错误 ----
    rc |= not check("I14 全量 AST 解析零错误", not sc["parse_errs"],
                    ("%d 处 %s" % (len(sc["parse_errs"]), sc["parse_errs"][:2]))
                    if sc["parse_errs"] else "0 处")

    print("-" * 76)
    print("汇总：%d PASS / %d FAIL / 共 %d 项" % (_NP, _NF, _NP + _NF))
    if rc == 0:
        print("ALL PASS — 测试与共享状态已解耦（无秒级唯一性来源、无共享库写入）")
    else:
        print("FAIL — 存在隔离违例：请为 empirical 提交显式传 proposals_path，"
              "并用 uuid4 取代秒级时间戳")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
