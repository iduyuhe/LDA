#!/usr/bin/env python
"""报告确定性护栏（v0.9.75 · 「根治提交噪声」的正向 + 反向测试）。

## 背景

`reports*/` 下的报告是**受版本控制的验证证据**。v0.9.74 及之前，每次跑 harness /
smoke 都会把它们重写成带 wall-clock 时间戳、耗时、浮点末位抖动的新内容 ⇒
`git status` 常红，提交时要么误带噪声、要么每次手动 checkout 掩盖。

v0.9.75 定为铁律：**受跟踪报告必须是输入的确定性函数** —— 相同输入 ⇒ 字节一致。

## 本 smoke 测什么（正反两面）

1. `deterministic.canon` 剔除 volatile 键（顶层 / 嵌套 dict / list 内）。
2. `canon` 浮点归一：末位抖动被吸收（1.0000000000000002 ≡ 1.0）。
3. `dumps` 幂等且稳定。
4. `report.format_json` 两次（其间 wall-clock 前进 + 浮点抖动）⇒ **字节一致**。
5. 输出**不含** volatile 键（generated_at / elapsed_s / …）。
6. `report.format_markdown` 两次 ⇒ 字节一致，且无「生成时间」/ ISO 时间戳。
7. **反向（可证伪）**：改一个真实 golden 值 ⇒ 输出字节**必须变化**
   —— 否则就是把真变化一起「归一化」掉了，比噪声更危险。
8. 源码 lint：**全部报告写入器**（core 中 21 个入口 + 报告格式化模块）不得再出现
   wall-clock 标记（生成时间 / 裁决时间 / 闭环耗时 / datetime.now / time.strftime），
   且必须走 `deterministic` 唯一口径。
9. `write_text` / `write_json` 落盘恒为 LF（跨平台不翻 CRLF）。
10. **线程环境确定性**：`threads.thread_env_overrides()` 必须显式关闭动态线程调整
   （`OMP_DYNAMIC`/`MKL_DYNAMIC`=FALSE）。否则 Intel OpenMP（torch 在 Windows 上
   随包的 libiomp5md.dll）会**按系统负载**伸缩线程数 ⇒ 归约顺序漂移 ⇒ float32
   结果抖动（D-23 实测被 κ=(βs−βa)/2 放大到 ~1e-5）。反向测试见注释。
11. **报告写入者「精确发现式判据」（v0.9.119 · 波次 6 T6.4）** —— 白名单型护栏
   的固有漏报面是「**漏登记**」：`lint_spec` 自述「没登记 = 门禁缺口」，却无从
   知道有没有漏。⑪ 用 **AST + 写上下文 + def-use** 反推「谁在写**受跟踪**报告」，
   再与 `lint_spec` 做**双向**断言：
     · 发现集 − 已登记集 必须**恰好等于**显式基线 `_KNOWN_UNREGISTERED`（只减不增）
     · 反向：⑫ 用合成源码证明发现器**真会报**（非空转）
   为什么不直接做粗扫判据：粗扫（含 `reports` 字面 + 写盘动作）实测 55 候选 / 30
   不在表内，其中多数**不是**报告写入者（`deterministic.py` 自身、`ci_regression`、
   计数护栏…）⇒ 会变「狼来了」被关停。故精确化到：**写上下文**（排除只读）+
   **受跟踪报告 basename**（排除自造名）+ **`reports` 目录语义**（排除 tmpdir 撞名）+
   **def-use 展开**（排除把变量路径漏掉）。
   ⚠️ 诚实边界：本判据只覆盖**字面量可推出**的路径。用 `--out`/`out_dir` 参数拼出
   输出目录、或文件名由 f-string/循环变量拼成的写入者**不在发现范围**（如
   `run_harness.py`、`lda_l1/protocol.py` 经 `args.out`/`self.out_dir` 落盘）——
   它们靠既有登记 + ⑧b 兜底；此类漏网正是 `_KNOWN_UNREGISTERED` 存在的原因之一。

纯标准库、秒级、零外部依赖 ⇒ 必进 core。
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "lda_harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_harness import deterministic as det      # noqa: E402
from lda_harness import report as rep             # noqa: E402

_FAILS = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        _FAILS.append(name)


class _R:
    """最小结果桩（模拟 harness 的 AnchorResult 属性面）。"""

    def __init__(self, bid, golden, candidate, passed=True, cls="strict_independent", ind=True):
        self.bid = bid
        self.metric = "metric_" + bid
        self.oracle = "analytical"
        self.source = "analytical"
        self.golden = golden
        self.candidate = candidate
        self.tol = 1e-3
        self.passed = passed
        self.note = None
        self.independent = ind
        self.candidate_class = cls


def _mk(jitter=0.0):
    """构造一组结果；jitter 只在浮点末位制造抖动。"""
    return [
        _R("B1", 0.9967000000000000 + jitter, 0.9967000000000000 + jitter * 0.5),
        _R("B2", 1.3571000000000000 + jitter, 1.3571000000000000 + jitter * 0.3),
        _R("B3", 2.8342000000000000 + jitter, 2.8342000000000000 + jitter * 0.7,
           passed=False, cls="self_consistent_stub", ind=False),
    ]


_META = {"candidate": "IndependentCandidateRouter(demo)", "self_consistent": True}


# ============================================================ T6.4 精确发现器
# 「谁在写受跟踪报告」—— AST + 写上下文 + def-use，纯函数、无 I/O、可反向测试。
_RW_WRITE_ATTRS = frozenset({"write_text", "write_json", "write_bytes",
                             "writestr", "savetxt", "savefig"})
_RW_SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".pytest_cache",
                           "lda_cuda_venv", ".venv", "venv", "dist", "build"})


class _DefUse:
    """轻量 def-use：把路径表达式里的**变量**展开回它被赋的值（限定作用域）。"""

    def __init__(self, tree):
        self.tree = tree
        self._funcs = [n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self._mod_env = self._env_of(tree.body)
        self._fn_env = {id(f): self._env_of(f.body) for f in self._funcs}

    @staticmethod
    def _env_of(body):
        env = {}
        for st in body:
            for node in ast.walk(st):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                val = node.value
                if val is None:
                    continue
                tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in tgts:
                    if isinstance(t, ast.Name):
                        env.setdefault(t.id, []).append(val)
        return env

    def _env_at(self, lineno):
        best, best_span = None, None
        for f in self._funcs:
            end = getattr(f, "end_lineno", f.lineno)
            if f.lineno <= lineno <= end:
                span = end - f.lineno
                if best_span is None or span < best_span:
                    best, best_span = f, span
        if best is None:
            return self._mod_env
        merged = dict(self._mod_env)
        merged.update(self._fn_env[id(best)])
        return merged

    def literals(self, node, env, depth=0):
        """递归取表达式里的字符串字面量（含变量展开 / BinOp / Call 参数）。"""
        if node is None or depth > 6:
            return []
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.Name):
            out = []
            for v in env.get(node.id, []):
                out += self.literals(v, env, depth + 1)
            return out
        if isinstance(node, ast.BinOp):
            return (self.literals(node.left, env, depth + 1)
                    + self.literals(node.right, env, depth + 1))
        if isinstance(node, ast.Attribute):
            return self.literals(node.value, env, depth + 1)
        if isinstance(node, ast.Call):
            out = []
            for a in node.args:
                out += self.literals(a, env, depth + 1)
            for kw in node.keywords:
                out += self.literals(kw.value, env, depth + 1)
            return out
        return []

    def write_path_literals(self):
        """所有**写**调用路径表达式里的字面量（每条 = 一个 list）。"""
        sites = []
        for n in ast.walk(self.tree):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else "")
            env = self._env_at(n.lineno)
            if name == "open":
                mode = ""
                kw = {k.arg: k.value for k in n.keywords}
                if isinstance(kw.get("mode"), ast.Constant):
                    mode = kw["mode"].value or ""
                if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
                    mode = n.args[1].value or mode
                # 无 mode 参数 = 只读 ⇒ **不算写**（`open(p, encoding=...)` 是读）
                if any(ch in str(mode) for ch in "wax") and n.args:
                    sites.append(self.literals(n.args[0], env))
            elif name in _RW_WRITE_ATTRS and n.args:
                sites.append(self.literals(n.args[0], env))
        return sites


def held_report_literals(src: str, tracked_basenames) -> set:
    """源码 ⇒ 命中的**受跟踪报告字面量**集合（纯函数 · 反向测试的靶点）。

    命中 = 存在一条**写路径**表达式，其字面量同时满足：
      ① 某个字面量的 basename ∈ `tracked_basenames`，且
      ② 同一条路径的字面量里有 `reports` 组件（目录语义 ⇒ 排除 tmpdir 撞名）
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    hits = set()
    for lits in _DefUse(tree).write_path_literals():
        if not any("reports" in x.lower() for x in lits):
            continue
        for s in lits:
            if os.path.basename(s) in tracked_basenames:
                hits.add(s)
    return hits


def tracked_report_basenames(repo: str) -> set:
    """受版本控制的报告产物 basename 集合（`git ls-files` ∩ reports*/ ∩ .json|.md）。"""
    out = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError("git ls-files 失败：%s"
                           % out.stderr.decode("utf-8", "replace")[:200])
    names = set()
    for p in out.stdout.decode("utf-8", "replace").splitlines():
        if not p.endswith((".json", ".md")) or "reports" not in p.lower():
            continue
        names.add(os.path.basename(p))
    return names


def discover_report_writers(repo: str, tracked_basenames) -> list:
    """扫描**受跟踪** `.py` ⇒ 报告写入者清单（仓库相对路径，已排序）。"""
    out = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True)
    found = []
    for p in out.stdout.decode("utf-8", "replace").splitlines():
        if not p.endswith(".py"):
            continue
        if set(p.split("/")[:-1]) & _RW_SKIP_DIRS:
            continue
        try:
            src = open(os.path.join(repo, p), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if held_report_literals(src, tracked_basenames):
            found.append(p)
    return sorted(found)


_REPO = os.path.dirname(HERE)

# 🔴 T6.4 显式基线：**已确认是受跟踪报告写入者、但尚未登记进 `lint_spec`** 的模块。
#    语义 = **棘轮基线（只减不增）**：
#      · 新出现的未登记写入者 ⇒ ⑪ 红（必须登记，或在此说明为何不算）
#      · 从本表移除**必须**同时把它登记进 `lint_spec` ⇒ 否则 ⑪ 红（保证不"偷偷放行"）
#    为什么不一次全登记：它们是 D-93~D-98 时代的**一次性证据生成器**（写
#    `ecosystem_d9*.json` / `perf_*.json`），登记即触发 ⑧b ⇒ 必须同时改写成
#    `det.write_json` ⇒ 会重写这些**历史证据报告**的字节。收益低而 blast radius 大，
#    故本轮只登记**CI core 内**的（会在 CI 里反复重写、有真风险），其余钉基线待专项。
_KNOWN_UNREGISTERED = frozenset({
    "lda/run_ecosystem_d94_report.py",
    "lda/run_ecosystem_d95_report.py",
    "lda/run_ecosystem_d96_report.py",
    "lda/run_ecosystem_d97_report.py",
    "lda/run_ecosystem_d98_report.py",
    "lda/run_ecosystem_report.py",          # 写 reports/ecosystem_d93.json
    "lda/run_perf_adjoint3d.py",
    "lda/run_perf_bench.py",                # 写 reports/perf_baseline.json
})


def main() -> int:
    print("=== 报告确定性护栏 ===")

    # 1) canon 剔除 volatile 键（顶层 / 嵌套 / list 内）
    src = {"a": 1, "generated_at": "2026-09-13T00:00:00", "elapsed_s": 3.14,
           "nested": {"timestamp": "x", "keep": 2},
           "rows": [{"bid": "B1", "elapsed_s": 9.9, "v": 1.0}]}
    c = det.canon(src)
    check("① canon 剔除顶层 volatile 键",
          "generated_at" not in c and "elapsed_s" not in c)
    check("① canon 剔除嵌套 dict 的 volatile 键",
          "timestamp" not in c["nested"] and c["nested"]["keep"] == 2)
    check("① canon 剔除 list 内 dict 的 volatile 键",
          "elapsed_s" not in c["rows"][0] and c["rows"][0]["bid"] == "B1")

    # 2) 浮点归一：末位抖动被吸收
    check("② canon 浮点归一吸收末位抖动",
          det.canon({"v": 1.0000000000000002}) == det.canon({"v": 1.0}),
          "1.0000000000000002 ≡ 1.0")
    check("② canon 不吞真实差异",
          det.canon({"v": 1.001}) != det.canon({"v": 1.0}))

    # 3) dumps 幂等
    check("③ dumps 幂等（同对象两次一致）",
          det.dumps(src) == det.dumps(src))

    # 4) format_json 双跑字节一致（wall-clock 前进 + 浮点抖动）
    js1 = rep.format_json(_mk(0.0), _META)
    js2 = rep.format_json(_mk(1e-15), _META)
    check("④ format_json 双跑字节一致（含浮点抖动）", js1 == js2,
          f"len={len(js1)}")

    # 5) 输出不含 volatile 键
    leaked = [k for k in det.VOLATILE_KEYS if f'"{k}"' in js1]
    check("⑤ format_json 输出无 volatile 键", not leaked, f"leaked={leaked}")

    # 6) format_markdown 双跑字节一致 + 无时间戳
    md1 = rep.format_markdown(_mk(0.0), _META)
    md2 = rep.format_markdown(_mk(1e-15), _META)
    check("⑥ format_markdown 双跑字节一致", md1 == md2, f"len={len(md1)}")
    iso = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", md1)
    check("⑥ format_markdown 无「生成时间」/ISO 时间戳",
          iso is None and "生成时间" not in md1, f"iso={iso.group(0) if iso else None}")

    # 7) 反向（可证伪）：改真值必须产生 diff，否则「归一化」成了「掩盖」
    js_changed = rep.format_json(_mk_golden_changed(), _META)
    check("⑦ 反向：改真实 golden ⇒ 输出必变（不可过度归一）",
          js_changed != js1)
    md_changed = rep.format_markdown(_mk_golden_changed(), _META)
    check("⑦ 反向：markdown 同样可证伪", md_changed != md1)

    # 8) 源码 lint：写入器不得再出现 wall-clock 标记。
    #    例外：`crosscheck_report.py` 的 `time.strftime` 只用于**被 .gitignore 的**
    #    历史归档**文件名**（`crosscheck_history/crosscheck_<ts>.json`），不进受跟踪
    #    报告内容，故不列入其禁用表（逐个文件显式声明，避免"一刀切"误伤）。
    _WALL = ("生成时间", "裁决时间", "闭环耗时", "datetime.now",
             "datetime.datetime.now", "time.strftime")
    _WALL_NO_STRFTIME = tuple(t for t in _WALL if t != "time.strftime")
    # v0.9.75 扩展：**core 中所有「写受跟踪报告」的入口**都必须走 deterministic
    # 唯一口径。前 10 项为报告格式化/聚合模块；其余为各 smoke / demo / bank 入口
    # ——它们原先自带 `json.dump(...)`（= 每次重写带 elapsed/浮点抖动 ⇒ 提交噪声）。
    # 🔴 在此显式登记 = 「没登记 = 门禁缺口」：新增报告写入者必须补进本表。
    lint_spec = {
        "lda_harness/report.py": _WALL,
        "lda_harness/benchmark_report.py": _WALL,
        "lda_harness/crosscheck_report.py": _WALL_NO_STRFTIME,
        "lda_agent/design_loop.py": _WALL,
        "lda_l1/protocol.py": _WALL,
        "run_harness.py": _WALL,
        "run_agent_loop.py": _WALL,
        "run_redteam_adjudication_smoke.py": _WALL,
        "run_redteam_anchor_fuzz_smoke.py": _WALL,
        "run_coupler_band_smoke.py": _WALL,
        # ——— v0.9.75 扩展：core 其余报告写入者 ———
        "run_agent_loop_smoke.py": _WALL,
        "run_benchmark_crosscheck_report.py": _WALL,
        "run_chip_scale_demo.py": _WALL,
        "run_dc_transmission_smoke.py": _WALL,
        "run_device_fdtd_smoke.py": _WALL,
        "run_drc_fix_smoke.py": _WALL,
        "run_drc_pdk_smoke.py": _WALL,
        "run_drc_smoke.py": _WALL,
        "run_ir_d05_smoke.py": _WALL,
        "run_layout_sim_smoke.py": _WALL,
        "run_pipeline_multidevice_smoke.py": _WALL,
        "run_quantum_design_smoke.py": _WALL,
        "run_quantum_devices_smoke.py": _WALL,
        "run_readout_chain_smoke.py": _WALL,
        "run_ring_double_verify_smoke.py": _WALL,
        "run_ring_fdtd_smoke.py": _WALL,
        "run_spectrum_loop_smoke.py": _WALL,
        "run_wdm_depth_smoke.py": _WALL,
        "run_wdm_system_smoke.py": _WALL,
        "run_golden_product_smoke.py": _WALL,
        "lda_harness/run_empirical_bank.py": _WALL,
        # ——— v0.9.116：补登漏网项 ———
        #   `run_empirical_d62_report.py` 自 D-62（v0.9.x）起就是报告写入者，但
        #   v0.9.75 建本表时**漏登记**（自述「没登记 = 门禁缺口」当场成立），且用
        #   裸 `json.dump` 落盘 + 把含 `landed_at`（wall-clock）的 provenance 整串
        #   写进 detail ⇒ `lda/reports/empirical_d62.json` **每次重跑字节必变**
        #   （实测连跑两次仅秒数不同：17:37:14 vs 17:37:15）。与 v0.9.116 主项
        #   （秒级 id）同族根因：wall-clock 非确定性。
        #   如实测：本表**只防「已登记项违规」，不防「漏登记」**（白名单型固有
        #   漏报面）—— 全仓粗扫有 30 个"含 reports 字面 + 写盘动作"的模块待甄别，
        #   其中多数非真报告写入者 ⇒ 精确发现式判据留待专门一轮（见 workplan backlog）。
        "run_empirical_d62_report.py": _WALL,
        # ——— v0.9.119（波次 6 T6.4）：**精确发现式判据 ⑪ 抓出的漏登记项** ———
        #   这 3 项此前从未登记、也未走 deterministic 唯一口径，全部用裸
        #   `json.dump(..., ensure_ascii=False, indent=2)` 写**受跟踪**报告：
        #     · run_design_package_smoke.py  → reports/design_packages_d44.json（CI core）
        #     · run_inverse_design_smoke.py  → reports/inverse_design_d38.json（CI core）
        #     · lda_design/design_package.py → reports/packages/*.json（**被上面那个
        #       smoke 通过 out_dir 参数调用**；文件名由 f-string 拼 ⇒ 旧粗扫与
        #       本判据的**字面量**面都看不见，属本轮手工复核抓出，如实披露）
        #   处置：登记 + 改走 `det.write_json`（两件必须同时做，否则 ⑧b 红）。
        "run_design_package_smoke.py": _WALL,
        "run_inverse_design_smoke.py": _WALL,
        "lda_design/design_package.py": _WALL,
    }
    lint_bad = []
    no_det = []
    for rel, forbidden in lint_spec.items():
        p = os.path.normpath(os.path.join(HERE, rel))
        try:
            s = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            lint_bad.append((rel, "MISSING"))
            continue
        for tok in forbidden:
            if tok in s:
                lint_bad.append((rel, tok))
        # 只有**实际落盘**的文件才必须走 deterministic（纯格式化器不必）。
        writes = bool(re.search(r"(json\.dump\(|open\([^)]*[\"']w[\"']|\.write\()", s))
        if writes and "deterministic" not in s:
            no_det.append(rel)
    check("⑧ 写入器源码无 wall-clock 标记", not lint_bad, f"violations={lint_bad}")
    check("⑧b 全部「落盘」报告写入者走 deterministic 唯一口径",
          not no_det, f"not-using-deterministic={no_det}")

    # 9) 落盘 EOL 恒为 LF
    with tempfile.TemporaryDirectory() as td:
        jp = os.path.join(td, "sub", "x.json")
        tp = os.path.join(td, "x.md")
        det.write_json(jp, src)
        det.write_text(tp, "line1\nline2")
        bj = open(jp, "rb").read()
        bt = open(tp, "rb").read()
        check("⑨ write_json/write_text 落盘恒 LF（无 CR）",
              b"\r" not in bj and b"\r" not in bt,
              f"cr_in_json={b'\r' in bj} cr_in_md={b'\r' in bt}")
        check("⑨ 目录自动创建 + 末尾恰一换行",
              os.path.exists(jp) and bt.endswith(b"\n") and not bt.endswith(b"\n\n"))

    # 10) 线程环境确定性：动态线程调整必须显式关闭。
    #     🔴 反向可证伪：删掉 threads._ENV_FLAGS 里的 OMP_DYNAMIC ⇒ 本判据必 FAIL。
    try:
        from lda_solver.threads import thread_env_overrides, _ENV_KEYS
        ov = thread_env_overrides()
        ok_thr = (ov.get("OMP_DYNAMIC") == "FALSE"
                  and ov.get("MKL_DYNAMIC") == "FALSE"
                  and all(k in ov for k in _ENV_KEYS)
                  and "LDA_FDTD_THREADS" in ov)
        check("⑩ 线程环境关闭动态调整（OMP_DYNAMIC/MKL_DYNAMIC=FALSE）",
              ok_thr, f"OMP_DYNAMIC={ov.get('OMP_DYNAMIC')} "
                      f"MKL_DYNAMIC={ov.get('MKL_DYNAMIC')} n={ov.get('LDA_FDTD_THREADS')}")
    except Exception as e:                                    # noqa: BLE001
        check("⑩ 线程环境关闭动态调整（OMP_DYNAMIC/MKL_DYNAMIC=FALSE）",
              False, f"探测失败：{e}")

    # 11) 报告写入者「精确发现式判据」（T6.4）--- 白名单型护栏的漏报面闭合。
    #     🔴 门禁依赖缺失 = 红，不静默跳过（与 ⑩① 反例同理）。
    disc, disc_err = [], ""
    try:
        tbn = tracked_report_basenames(_REPO)
        disc = discover_report_writers(_REPO, tbn)
    except Exception as e:                                    # noqa: BLE001
        disc_err = "%s" % e
    if disc_err:
        check("⑪ 报告写入者精确发现（受跟踪报告 basename + 写上下文 + def-use）",
              False, f"发现器不可用（门禁依赖缺失=红，不静默跳过）：{disc_err}")
    else:
        # lint_spec 的键相对 `lda/`；发现集的路径相对仓库根 ⇒ 归一化到仓库根
        registered = {("lda/" + k) if not k.startswith("lda/") else k
                      for k in lint_spec}
        unregistered = sorted(set(disc) - registered)
        # 双向断言：未登记集必须**恰好**等于显式基线 ⇒ 新漏项红 · 偷放行红
        new_leak = sorted(set(unregistered) - _KNOWN_UNREGISTERED)
        smuggle = sorted(_KNOWN_UNREGISTERED - set(disc))
        check("⑪ 报告写入者精确发现：未登记集 == 显式基线（只减不增）",
              not new_leak and not smuggle,
              f"新漏登记 {new_leak} ｜ 基线里已不再被发现的（须同时从基线删并登记）"
              f" {smuggle}" if (new_leak or smuggle)
              else f"发现 {len(disc)} 个写入者 · 已登记 {len(disc) - len(unregistered)} · "
                   f"基线钉住 {len(unregistered)}")
        # 反向（可证伪）：合成一个「写受跟踪报告 + 未登记」的模块 ⇒ 发现器必报。
        # 🔴 同时给**反证对照**：只读同一文件 / 写到 tmpdir 撞名 ⇒ 必须**不报**
        #    （证明判据不是"见到 reports 就报"的粗扫）。
        _probe = ('import json, os\n'
                  'OUT = os.path.join(_HERE, "reports", "probe_synth.json")\n'
                  'def w():\n'
                  '    with open(OUT, "w", encoding="utf-8") as f:\n'
                  '        json.dump(1, f)\n')
        _probe_read = ('import json, os\n'
                       'OUT = os.path.join(_HERE, "reports", "probe_synth.json")\n'
                       'def r():\n'
                       '    with open(OUT, encoding="utf-8") as f:\n'
                       '        return json.load(f)\n')
        _probe_tmp = ('import json, os, tempfile\n'
                      'OUT = os.path.join(tempfile.gettempdir(), "probe_synth.json")\n'
                      'def w():\n'
                      '    with open(OUT, "w", encoding="utf-8") as f:\n'
                      '        json.dump(1, f)\n')
        _grab = {os.path.basename("probe_synth.json")}
        _hit = bool(held_report_literals(_probe, _grab))
        _neg_read = held_report_literals(_probe_read, _grab)
        _neg_tmp = held_report_literals(_probe_tmp, _grab)
        check("⑫ 反向：合成「写受跟踪报告」模块 ⇒ 发现器必报；"
              "只读 / 临时目录撞名两反例必不报（证明非粗扫）",
              _hit and not _neg_read and not _neg_tmp,
              f"正例报={_hit} 只读反例={bool(_neg_read)} tmp 反例={bool(_neg_tmp)}")

    print(f"\n=== 结果：{'全部通过' if not _FAILS else 'FAIL %d 项' % len(_FAILS)} ===")
    if _FAILS:
        for f in _FAILS:
            print("  FAIL:", f)
        return 1
    print("  ✅ 报告确定性 12 项判据全绿（相同输入 ⇒ 字节一致；真变更仍可证伪；"
          "报告写入者无漏登记）")
    return 0


def _mk_golden_changed():
    """真值改变（非末位抖动）——用于反向可证伪测试。"""
    r = _mk(0.0)
    r[0].golden = 0.9000   # 从 0.9967 → 0.9000，显著变化
    r[0].candidate = 0.9000
    return r


if __name__ == "__main__":
    raise SystemExit(main())
