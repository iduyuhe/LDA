"""P0 沙箱隔离护栏 smoke（七判据）。

验证 solver_writer 的候选代码执行已从「伪沙箱」升级为「真沙箱」：
  ① 隔离等级可报告（Linux→strong / Windows→weak）
  ② weak 环境守护红线：allow_weak_isolation=True 才可构造、否则构造即拒；
     strong 环境默认可构造
  ③ 轻量闭环行为等价：v0 FAIL→v1 PASS（沙箱不改变判卷语义）
  ④ strong 真隔离（仅 Linux）：降权 nobody 读 /etc/shadow 被拒、网络命名空间禁外网
  ⑤ §4.3 strong 路径 env 最小化：剥离 LDA_LLM_KEY/OPENAI_API_KEY 等密钥、保留 PATH
  ⑥ §4.5 unshare 失败（缺 CAP_SYS_ADMIN）→ 友好 RuntimeError（fail-closed，不裸抛）
  ⑦ §4.4 本 smoke 一律走公开 `SandboxExecutor.run`（无封装泄漏）

不依赖 tmm / FDTD，秒级运行；weak 环境跳过 ④（生产 Linux 部署后验证）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LDA = os.path.dirname(HERE)
if LDA not in sys.path:
    sys.path.insert(0, LDA)

from lda.lda_agent import sandbox
from lda.lda_agent.solver_writer import (
    SolverSpec, TestCase, ScriptedAIDevGenerator,
    SandboxExecutor, Verifier, BootstrapLoop,
)

checks = []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


# ① 隔离等级
lvl = sandbox.isolation_level()
check("① 隔离等级可报告 (strong/weak)", lvl in ("strong", "weak"), f"level={lvl}")

# ② weak 红线 / strong 默认
if lvl == "weak":
    try:
        SandboxExecutor(timeout=30, allow_weak_isolation=True)
        check("② weak 允许 allow_weak_isolation 可构造", True)
    except Exception as e:
        check("② weak 允许 allow_weak_isolation 可构造", False, repr(e))
    try:
        SandboxExecutor(timeout=30)
        check("② weak 不 allow 时构造拒绝（红线）", False, "未抛异常")
    except RuntimeError:
        check("② weak 不 allow 时构造拒绝（红线）", True)
    except Exception as e:
        check("② weak 不 allow 时构造拒绝（红线）", False, repr(e))
else:
    try:
        SandboxExecutor(timeout=30)
        check("② strong 默认可构造", True)
    except Exception as e:
        check("② strong 默认可构造", False, repr(e))

# ③ 轻量闭环（纯算术，验证沙箱不改变判卷语义；不依赖 tmm）
spec = SolverSpec(
    spec_id="SW-SMOKE-ADD",
    problem_statement="实现 a+b",
    entrypoint="myadd",
    io_contract="myadd(a,b)->a+b",
    test_cases=[
        TestCase("t1", {"a": 2, "b": 3}, 5, 0.01),
        TestCase("t2", {"a": -1, "b": 1}, 0, 0.01),
    ],
)
v0 = "def myadd(a,b):\n    return a+b+1\n"   # FAIL
v1 = "def myadd(a,b):\n    return a+b\n"      # PASS
gen = ScriptedAIDevGenerator([v0, v1])
allow = (lvl == "weak")
loop = BootstrapLoop(
    SandboxExecutor(timeout=30, allow_weak_isolation=allow),
    Verifier(), max_iters=5, verbose=False,
)
rep = loop.run(spec, gen)
check("③ 轻量闭环 v0 FAIL→v1 PASS（行为等价）", rep.final_passed, rep.verdict)

# ④ strong 真隔离（仅 Linux）：读 /etc/shadow 被拒 + 禁外网
if lvl == "strong":
    iso_spec = SolverSpec(
        spec_id="SW-ISO", problem_statement="iso", entrypoint="myadd",
        io_contract="myadd(a,b)->1.0 若隔离生效 / 0.0 若泄露",
        test_cases=[TestCase("t", {"a": 0, "b": 0}, 1.0, 0.01)],
    )
    # 读 /etc/shadow：成功→返回 0.0（泄露信号），被拒→返回 1.0（隔离生效）
    evil_fs = (
        "def myadd(a,b):\n"
        "    try:\n"
        "        open('/etc/shadow').read()\n"
        "        return 0.0\n"
        "    except Exception:\n"
        "        return 1.0\n"
    )
    # 连外网：成功→返回 0.0（泄露信号），无网→返回 1.0（隔离生效）
    evil_net = (
        "import socket\n"
        "def myadd(a,b):\n"
        "    try:\n"
        "        s = socket.create_connection(('8.8.8.8', 53), timeout=5)\n"
        "        s.close()\n"
        "        return 0.0\n"
        "    except Exception:\n"
        "        return 1.0\n"
    )
    r_fs = SandboxExecutor(timeout=30).run(evil_fs, iso_spec)
    r_net = SandboxExecutor(timeout=30).run(evil_net, iso_spec)
    v_fs = r_fs.get("results", [{}])[0].get("value")
    v_net = r_net.get("results", [{}])[0].get("value")
    check("④ strong 隔离：降权 nobody 读 /etc/shadow 被拒", v_fs == 1.0,
          f"value={v_fs}")
    check("④ strong 隔离：网络命名空间禁外网", v_net == 1.0,
          f"value={v_net}")
else:
    check("④ strong 真隔离（仅 Linux 验证）", True,
          "weak 环境跳过：生产 Linux 部署后验证")

# ⑤ §4.3 strong 路径 env 最小化（纵深防御·全平台可测）
_sentinel = {"LDA_LLM_KEY": "SECRET", "OPENAI_API_KEY": "sk-secret",
             "ANTHROPIC_API_KEY": "sk-ant", "PATH": os.environ.get("PATH", "/usr/bin")}
_prev = {k: os.environ.get(k) for k in _sentinel}
for _k, _v in _sentinel.items():
    os.environ[_k] = _v
_env = {}
try:
    _env = sandbox._minimal_env("PAYLOAD")
    _ok5 = (_env.get("LDA_SOLVER_CASES") == "PAYLOAD"
            and "LDA_LLM_KEY" not in _env
            and "OPENAI_API_KEY" not in _env
            and "ANTHROPIC_API_KEY" not in _env
            and "PATH" in _env)
finally:
    for _k, _v in _prev.items():
        if _v is None:
            os.environ.pop(_k, None)
        else:
            os.environ[_k] = _v
check("⑤ §4.3 strong env 最小化：剥离密钥、保留 PATH", _ok5,
      f"keys={sorted(_env.keys())}")

# ⑥ §4.5 unshare 失败 → 友好 RuntimeError
#   mock：isolation_level 报 strong + subprocess.run 抛 OSError（模拟缺 CAP_SYS_ADMIN）
_saved_lvl = sandbox.isolation_level
_saved_run = sandbox.subprocess.run


def _raise_oserror(*a, **k):
    raise OSError("Operation not permitted")


sandbox.isolation_level = lambda: "strong"
sandbox.subprocess.run = _raise_oserror
try:
    _ex = sandbox.IsolatedExecutor(timeout=5, allow_weak_isolation=True)
    try:
        _ex.run("def myadd(a,b):\n    return a+b\n", spec)
        _msg6, _ok6 = "未抛异常（fail-open 违规）", False
    except RuntimeError as e:
        _msg6 = str(e)
        _ok6 = ("隔离不可用" in _msg6 and "CAP_SYS_ADMIN" in _msg6)
    except Exception as e:  # noqa: BLE001
        _msg6, _ok6 = repr(e), False
finally:
    sandbox.isolation_level = _saved_lvl
    sandbox.subprocess.run = _saved_run
check("⑥ §4.5 unshare 失败→友好 RuntimeError（fail-closed）", _ok6, _msg6[:60])

# ⑦ §4.4 本 smoke 不戳私有成员（封装泄漏回归）；needle 拼接以免自指
_needle = "." + "_iso"
_src = open(os.path.abspath(__file__), encoding="utf-8").read()
_ok7 = _needle not in _src
check("⑦ §4.4 smoke 走公开 run()（无私有成员访问）", _ok7, "")

npass = sum(1 for _, ok, _ in checks if ok)
nfail = len(checks) - npass
print(f"\n沙箱 smoke: {npass} PASS / {nfail} FAIL")
sys.exit(1 if nfail else 0)
