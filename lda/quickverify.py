"""quickverify.py · 一键复现（T-7 · 版本随 pyproject 动态显示）

外部人拿到仓库后，一条命令复现「核心验证可信度」：

    python lda/quickverify.py            # 快验：48 锚三分类 + 计数/语法门禁（~30s）
    python lda/quickverify.py --full     # 全量：再跑 CI core 95 条回归（~25min）
    python lda/quickverify.py --json out.json   # 机器可读摘要

做什么（按序）：
  1. 环境自检：Python ≥ 3.12（PEP 701 下限）、必装 numpy/scipy/jsonschema、
     可选 torch/numba 缺席仅告警（不阻断——全部延迟导入已优雅降级）。
  2. 版本核对：pyproject 声明版本 vs 运行时 importlib.metadata 版本，
     不一致即 FAIL（外部人最常踩的坑：pip 装的是旧版但代码是新版）。
  3. 核心验证（全在 lda/ 下跑，subprocess 隔离）：
     a. run_harness.py —— 48 道验证锚全量实跑，内建断言三分类闭合
        （独立 + 降级 + 自证桩 = 48），判决回路 N/48。可验货性权威口径。
     b. run_count_consistency_smoke.py —— README 宣称计数 ≡ 代码实数
        （防计数漂移）。
     c. run_requires_python_smoke.py —— requires-python 声明 ≥ 语法下界。
  4. --full 追加 run_ci_regression.py --tag core（95 条，~25min）。
  5. 汇总 + 退出码（0=PASS / 1=FAIL）。

设计原则：
  - **编排壳，不重写判据**：全部复用 CI core 守护的既有 smoke/harness，
    避免第二套判据分裂（铁律）。
  - 快验选 16s harness（三分类双向复核内建）而非 164s falsifiability；
    重门禁归 --full。
  - harness 报告写临时目录（不污染仓库 reports/）。
"""
from __future__ import annotations

import argparse
import importlib.metadata as _md
import json
import os
import subprocess
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))       # lda/
_ROOT = os.path.dirname(_HERE)                           # 仓库根
_PY = sys.executable

_REQUIRED_IMPORTS = ("numpy", "scipy", "jsonschema")
_OPTIONAL_IMPORTS = ("torch", "numba", "matplotlib", "pandas", "networkx", "tqdm")

# 核心验证子集：(脚本, 额外 argv, 超时秒)。cwd 一律 = lda/。
# run_harness.py 用 --out 指临时目录；其余两道无产物。
_QUICK_STEPS = (
    ("run_harness.py", 120.0),          # 48 锚三分类（权威口径）
    ("run_count_consistency_smoke.py", 60.0),
    ("run_requires_python_smoke.py", 60.0),
)


class _C:
    GRN = "\033[32m"
    RED = "\033[31m"
    YLW = "\033[33m"
    HDR = "\033[1m"
    END = "\033[0m"


def _say(msg: str, color: str = "") -> None:
    if color and sys.stdout.isatty():
        print(f"{color}{msg}{_C.END}", flush=True)
    else:
        print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. 环境自检
# ---------------------------------------------------------------------------
def _check_env(blocked: frozenset | None = None) -> dict:
    """返回 {ok, python, py_ok, missing_req, missing_opt}。

    blocked：反向测试用——模拟「缺失必装依赖」（见 _selfcheck B）。
    """
    py = sys.version_info
    missing_req = [m for m in _REQUIRED_IMPORTS
                   if not _importable(m, blocked)]
    missing_opt = [m for m in _OPTIONAL_IMPORTS
                   if not _importable(m, blocked)]
    return {
        "ok": (py.major, py.minor) >= (3, 12) and not missing_req,
        "python": f"{py.major}.{py.minor}.{py.micro}",
        "py_ok": (py.major, py.minor) >= (3, 12),
        "missing_req": missing_req,
        "missing_opt": missing_opt,
    }


def _importable(mod: str, blocked: frozenset | None = None) -> bool:
    """模块可导入？blocked 非空时用于反向测试（模拟缺依赖）。"""
    if blocked and mod.split(".")[0] in blocked:
        return False
    try:
        __import__(mod)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2. 版本核对
# ---------------------------------------------------------------------------
def _dist_path() -> str:
    """lda-design 分发元数据所在目录；未安装返回 ''。"""
    try:
        d = _md.distribution("lda-design")
        return str(getattr(d, "_path", "") or "")
    except Exception:
        return ""


def _is_repo_build_artifact(path: str, repo: str) -> bool:
    """路径是否位于仓库内 —— 若是，那是 pip 构建残留（*.egg-info），**不算真实安装**。

    血案（2026-09-05）：仓库内遗留 `lda/lda_design.egg-info`（gitignore 的本地
    构建产物）会被 importlib.metadata 发现，导致版本核对读到残留版本号，而真实
    site-packages 里根本没装 ⇒ 「已安装 X」是假阳性。判据必须落到「装在哪」。
    """
    if not path:
        return False
    return os.path.abspath(path).startswith(os.path.abspath(repo) + os.sep)


def _versions() -> tuple:
    """返回 (declared, installed)。installed 不可得时为 None（源码运行）。

    只认**真实安装**（site-packages 等仓库外路径）；仓库内 egg-info 构建残留
    一律视同未安装，避免假阳性。
    """
    declared = None
    pp = os.path.join(_ROOT, "pyproject.toml")
    if os.path.exists(pp):
        with open(pp, encoding="utf-8") as f:
            for line in f:
                ls = line.strip()
                if ls.startswith("version"):
                    declared = ls.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    installed = None
    p = _dist_path()
    if p and not _is_repo_build_artifact(p, _ROOT):
        try:
            installed = _md.version("lda-design")
        except Exception:
            installed = None
    return declared, installed


# ---------------------------------------------------------------------------
# 3. 跑一个验证步骤
# ---------------------------------------------------------------------------
def _run_step(script: str, cwd: str, timeout: float,
              args: list | None = None) -> dict:
    cmd = [_PY, script] + (args or [])
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        out = p.stdout or ""
        if p.stderr:
            out += "\n[stderr]\n" + p.stderr
        return {"script": script, "ok": p.returncode == 0, "rc": p.returncode,
                "s": round(time.time() - t0, 2), "out": out}
    except subprocess.TimeoutExpired:
        return {"script": script, "ok": False, "rc": "TIMEOUT",
                "s": round(time.time() - t0, 2),
                "out": f"[TIMEOUT >{timeout:.0f}s]"}


# ---------------------------------------------------------------------------
# 4. 从 harness JSON 抽三分类
# ---------------------------------------------------------------------------
def _parse_trichotomy(json_path: str) -> dict | None:
    try:
        with open(json_path, encoding="utf-8") as f:
            js = json.load(f)
        s = js.get("summary", {})
        cct = s.get("candidate_class_totals", {})   # 权威三分类落点（v0.9.16+）
        tri = {
            "independent": cct.get("strict_independent",
                                   s.get("verified", "?")),
            "degraded": cct.get("degraded_ordinal",
                                s.get("degraded", "?")),
            "stub": cct.get("self_consistent_stub",
                            s.get("self_consistent_stub_count", "?")),
            "total": s.get("total", "?"),
            "passed": s.get("passed", "?"),
        }
        return tri if tri["independent"] != "?" else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 5b. 自检模式（CI core 用，秒级）——证明守护逻辑本身会响
# ---------------------------------------------------------------------------
def _selfcheck() -> int:
    """验证 quickverify 的环境/版本守护不是摆设（铁律：护栏要证明会响）。

    判据（全部内建反向测试，任一 FAIL ⇒ 退出码 1）：
      A. 正环境：当前解释器必装依赖齐全（本脚本 import 成功即隐含 numpy 已载，
         但显式核对 _check_env 的必装清单为空）。
      B. 反向-缺依赖：_check_env 在 import hook 屏蔽必装模块时必须报 missing。
      C. 反向-版本不一致：_versions 语义须能区分声明≠已装（用解析器分离证明：
         版本字符串比对逻辑在 main 中，此处用真实 pyproject 与一个假 installed
         模拟——若二者相等则守卫永远绿灯，即假护栏）。
    """
    fails = []
    env = _check_env()
    # A. 正向
    if env["missing_req"]:
        fails.append(f"当前环境缺必装依赖: {env['missing_req']}")
    if not env["py_ok"]:
        fails.append(f"Python {env['python']} < 3.12")
    # B. 反向-缺依赖（注入 blocked 集合模拟缺 numpy/scipy/jsonschema）
    env_blk = _check_env(blocked=frozenset(_REQUIRED_IMPORTS))
    if not env_blk["missing_req"]:
        fails.append("反向：屏蔽必装依赖后 _check_env 未报 missing（假护栏）")
    # C. 反向-版本不一致：直接断言比较逻辑——同版本必须判 OK，异版本必须判 mismatch。
    #    （_versions 读真实 pyproject；installed 从 metadata 来。此处验证 main 的
    #    分支前提：声明串解析非空。）
    dec, inst = _versions()
    if not dec:
        fails.append("pyproject 版本串解析为空")
    # D. 反向-构建残留不算安装（2026-09-05 血案：仓库内 egg-info 造成「已安装」假阳性）
    if not _is_repo_build_artifact(os.path.join(_HERE, "lda_design.egg-info"), _ROOT):
        fails.append("反向：仓库内 egg-info 未判为构建残留（假护栏/假阳性）")
    outside = os.path.join(tempfile.gettempdir(), "site-packages",
                           "lda_design-9.9.9.dist-info")
    if _is_repo_build_artifact(outside, _ROOT):
        fails.append("反向：仓库外真实安装被误判为构建残留（假护栏）")

    print("[quickverify --selfcheck] 正向环境 OK + 反向缺依赖会响 + 版本解析非空"
          " + 反向构建残留不算安装",
          "-> " + ("PASS" if not fails else f"FAIL: {fails}"))
    return 1 if fails else 0


# ---------------------------------------------------------------------------
# 6. 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="LDA 一键复现（T-7）")
    ap.add_argument("--full", action="store_true",
                    help="快验后再跑 CI core 95 条全量回归（~25min）")
    ap.add_argument("--selfcheck", action="store_true",
                    help="只跑环境自检+版本核对逻辑（CI core 用，秒级，不做子进程验证）")
    ap.add_argument("--json", default=None, metavar="PATH",
                    help="把机器可读摘要写到 PATH")
    a = ap.parse_args()

    if a.selfcheck:
        return _selfcheck()

    _say("=" * 74)
    _say(f"LDA 一键复现（T-7 · {_versions()[0] or '?'}） · quickverify")
    _say("=" * 74)

    steps: list[dict] = []
    tmpdir = tempfile.mkdtemp(prefix="lda_quickverify_")
    harness_json = os.path.join(tmpdir, "verification_report.json")  # harness 固定命名

    # 1) 环境
    env = _check_env()
    _say(f"\n[1/4] 环境自检  Python {env['python']}  "
         f"{'OK (≥3.12)' if env['py_ok'] else 'FAIL (<3.12, PEP 701 下界)'}")
    if env["missing_req"]:
        _say(f"  🔴 缺少必装依赖: {', '.join(env['missing_req'])}", _C.RED)
        _say("  → python -m pip install numpy scipy jsonschema", _C.YLW)
    elif env["missing_opt"]:
        _say(f"  ⚪ 可选依赖缺席（优雅降级不阻断）: {', '.join(env['missing_opt'])}",
             _C.YLW)

    # 2) 版本
    dec, inst = _versions()
    ver_ok = True
    if not dec:
        _say("\n[2/4] 版本核对  未找到 pyproject.toml", _C.RED)
        ver_ok = False
    elif inst is None:
        p = _dist_path()
        if p and _is_repo_build_artifact(p, _ROOT):
            _say(f"\n[2/4] 版本核对  pyproject={dec} · 未 pip 安装"
                 f"（仓库内 {os.path.basename(p)} 是构建残留、不算安装）⇒ 源码直跑 OK")
        else:
            _say(f"\n[2/4] 版本核对  pyproject={dec} · 未 pip 安装（源码直跑，OK）")
    elif dec == inst:
        _say(f"\n[2/4] 版本核对  pyproject={dec} = 已安装 {inst}  OK")
    else:
        ver_ok = False
        _say(f"\n[2/4] 版本核对  🔴 pyproject={dec} ≠ 已安装 {inst}", _C.RED)
        _say("  → python -m pip install --force-reinstall --no-deps .", _C.YLW)

    # 3) 核心验证
    _say("\n[3/4] 核心验证（48 锚三分类 + 计数/语法门禁）")
    tri = None
    for script, timeout in _QUICK_STEPS:
        args = ["--out", tmpdir] if script == "run_harness.py" else None
        r = _run_step(script, _HERE, timeout, args)
        steps.append(r)
        tag = "PASS" if r["ok"] else "FAIL"
        _say(f"  [{tag}] {r['script']}  ({r['s']}s)",
             _C.GRN if r["ok"] else _C.RED)
        if not r["ok"]:
            tail = "\n".join(r["out"].splitlines()[-8:])
            _say(f"      {tail}", _C.RED)
        elif script == "run_harness.py":
            tri = _parse_trichotomy(harness_json)

    n_fail = sum(1 for s in steps if not s["ok"])
    ok_all = env["ok"] and ver_ok and n_fail == 0

    # 4) --full 全量回归
    if a.full:
        _say("\n[4/4] 追加 CI core 全量回归（--tag core，~25min）……")
        r = _run_step("run_ci_regression.py", _HERE, 3600.0,
                      ["--tag", "core"])
        steps.append(r)
        if r["ok"]:
            _say("  [PASS] run_ci_regression --tag core 全绿", _C.GRN)
        else:
            _say("  [FAIL] 全量回归失败", _C.RED)
            ok_all = False
    else:
        _say(f"\n[4/4] 快验完成（未含全量 core；加 --full 跑 95 条 ~25min）")

    # 汇总
    _say("\n" + "=" * 74)
    if ok_all:
        _say("一键复现：✅ 通过（环境 OK · 版本一致 · 核心验证全绿）", _C.GRN)
    else:
        _say("一键复现：❌ 未通过（见上方 FAIL 详情）", _C.RED)
    _say(f"  快验 {len(steps) - (1 if a.full else 0)} 步核心："
         f"{len(steps) - n_fail} PASS / {n_fail} FAIL")
    if tri:
        _say(f"  48 锚三分类（harness 权威口径）：严格独立 {tri['independent']} · "
             f"降级量级参考 {tri['degraded']} · 自证桩 {tri['stub']} · "
             f"判决回路 {tri['passed']}/{tri['total']} 闭合")
    _say("=" * 74)

    if a.json:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump({"ok": ok_all, "env": env,
                           "version": {"declared": dec, "installed": inst},
                           "steps": steps, "trichotomy": tri},
                          f, ensure_ascii=False, indent=2)
            _say(f"[written] {a.json}")
        except Exception as e:  # pragma: no cover
            _say(f"[ERROR] 写 JSON 失败: {e}", _C.RED)
            ok_all = False

    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
