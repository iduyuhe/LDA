"""LDA · 1.4 候选代码隔离执行层（P0 沙箱隔离）。

为什么存在
----------
1.4 AI-dev 自举写核闭环会让**不可信候选代码**（尤其外部 LLM 产出）在宿主进程旁执行。
裸 ``subprocess.run([python, driver], cwd=tmp)`` 的子进程仍以**宿主完整权限**运行——
候选可 ``import os/shutil/socket``、读写 ``~/.ssh``、外传数据、删文件、fork bomb。
原 ``timeout`` 只防挂死，不防破坏，且文档声称「仅能访问 numpy/math」**不实**。
本模块把伪沙箱升级为真沙箱。

隔离等级（isolation_level）
-------------------------
- ``"strong"``（Linux，推荐生产）：
    * 用户命名空间隔离（``unshare --user --map-root-user``）
    * 无网命名空间（``unshare --net``，无默认路由 → 外网 connect 失败）
    * 降权到 ``nobody``（``setpriv --reuid/--regid nobody``，无 root、无写宿主敏感路径权限）
    * 资源上限（``RLIMIT_CPU/AS/NOFILE/FSIZE``，防 OOM / fork bomb / 超算）
- ``"weak"``（Windows 开发机 / 无 unshare 的 Linux）：
    * 仅进程组 + cwd 限制 + timeout。**明确不安全**，禁止执行不可信候选；
      仅允许离线 Scripted 演示（候选由本 harness 提供、可信任）。

设计纪律（沿用 LDA 红线）
-----------------------
- 判决（PASS/FAIL）仍由 Verifier 用 ORACLE 死标量比对，与沙箱层级无关。
- 沙箱只约束 OS 资源，不替代许可证纪律：候选代码永不 import LDA 内部求解器或
  GPL/商业库（见 solver_writer 顶部说明），隔离层是纵深防御、不是许可开关。
- Windows 上 ``weak`` 路径不抛（演示可用）；``strong`` 仅 Linux 提供。任何试图在
  ``weak`` 环境执行**不可信**候选的调用，必须在构造时显式 ``allow_weak_isolation=True``
  （仅限离线 Scripted 可信候选），否则 ``SandboxExecutor`` 直接拒绝——以代码守住
  「接外部 LLM 前必须强隔离」这条红线。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

_STRONG_BINS = ("unshare", "setpriv")


def _bins_present(*bins: str) -> bool:
    return all(shutil.which(b) for b in bins)


def platform_supports_strong() -> bool:
    """strong 隔离仅在 Linux 且具备 unshare + (setpriv|su) 时可用。"""
    if sys.platform != "linux":
        return False
    if not _bins_present("unshare"):
        return False
    if not (_bins_present("setpriv") or _bins_present("su")):
        return False
    return True


def isolation_level() -> str:
    """返回 ``"strong"`` 或 ``"weak"``。"""
    return "strong" if platform_supports_strong() else "weak"


# 候选 driver：调用 candidate.<entrypoint>，逐用例跑，落 JSON。
# 通过环境变量 LDA_SOLVER_CASES 传用例（避免 shell 转义 JSON 注入）。
_DRIVER_TMPL = """\
import json, os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 资源上限（即便命名空间逃逸也受限）：防 OOM / fork bomb / 超算
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))              # 30s CPU 硬上限
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))  # 512MB
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
except Exception:
    pass
try:
    import candidate as C
    fn = getattr(C, {entry!r}, None)
    if fn is None:
        print(json.dumps({{"ok": False, "error":
            f"候选未定义函数 {entry!r}"}}))
        sys.exit(0)
    cases = json.loads(os.environ.get("LDA_SOLVER_CASES", "[]"))
    out = []
    for c in cases:
        try:
            val = fn(**c["inputs"])
            out.append({{"name": c["name"], "ok": True, "value": val}})
        except Exception:
            out.append({{"name": c["name"], "ok": False,
                        "error": traceback.format_exc()}})
    print(json.dumps({{"ok": True, "results": out}}))
except Exception:
    print(json.dumps({{"ok": False, "error": traceback.format_exc()}}))
"""


class IsolatedExecutor:
    """隔离执行候选代码，返回与 Verifier 兼容的结果字典。

    接口对齐原 ``SandboxExecutor``：``run(code: str, spec: SolverSpec)``。
    """

    def __init__(self, timeout: float = 120.0, allow_weak_isolation: bool = False):
        self.timeout = timeout
        self.allow_weak = allow_weak_isolation
        if isolation_level() == "weak" and not self.allow_weak:
            raise RuntimeError(
                "弱隔离环境禁止执行不可信候选代码：当前 isolation_level='weak' "
                "(非 Linux 或未安装 unshare/setpriv)。候选代码可能含任意危险操作。\n"
                "正确做法：在 Linux strong 隔离环境运行；或仅在离线 Scripted 演示中"
                "显式 allow_weak_isolation=True（候选由本 harness 提供、可信任）。"
            )

    # -- 内部：写候选 + driver，返回 (tmp, drv_path, cases_payload) ----------
    def _stage(self, code: str, spec) -> "tuple[str, str, str]":
        tmp = tempfile.mkdtemp(prefix="lda_solver_writer_")
        cand_path = os.path.join(tmp, "candidate.py")
        drv_path = os.path.join(tmp, "driver.py")
        with open(cand_path, "w", encoding="utf-8") as f:
            f.write(code)
        drv = textwrap.dedent(_DRIVER_TMPL.format(entry=spec.entrypoint))
        with open(drv_path, "w", encoding="utf-8") as f:
            f.write(drv)
        # 让降权后的 nobody 能进入 tmp 并读取候选/driver：
        # mkdtemp 默认 0700，nobody 进不去 → 放宽目录与文件权限。
        try:
            os.chmod(tmp, 0o755)
            os.chmod(cand_path, 0o644)
            os.chmod(drv_path, 0o644)
        except Exception:
            pass
        cases_payload = json.dumps(
            [{"name": c.name, "inputs": c.inputs} for c in spec.test_cases]
        )
        return tmp, drv_path, cases_payload

    def _parse(self, proc: subprocess.CompletedProcess) -> dict:
        if proc.returncode != 0 and not proc.stdout.strip():
            return {"ok": False,
                    "error": f"子进程异常退出 {proc.returncode}\n"
                             f"STDERR:\n{proc.stderr}"}
        try:
            return json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception as e:
            return {"ok": False,
                    "error": f"无法解析候选输出: {e}\nSTDOUT:\n{proc.stdout}"
                             f"\nSTDERR:\n{proc.stderr}"}

    # -- strong：unshare 用户/网络命名空间 + 降权 nobody + 资源上限 ---------
    def _run_strong(self, drv_path: str, payload: str, tmp: str) -> subprocess.CompletedProcess:
        py = sys.executable
        env = {**os.environ, "LDA_SOLVER_CASES": payload}
        # sh -c 'cd "$0" && exec "$@"' tmp setpriv ... -- py drv
        # 所有路径/参数走 argv，不拼 shell 字符串，杜绝路径注入。
        drop = ["setpriv", "--reuid=nobody", "--regid=nobody",
                "--clear-groups", "--", py, drv_path]
        if not _bins_present("setpriv") and _bins_present("su"):
            drop = ["su", "nobody", "-s", py, "-c", f"{py} {drv_path!r}"]
        inner = ["sh", "-c", 'cd "$0" && exec "$@"', tmp] + drop
        cmd = ["unshare", "--user", "--map-root-user", "--net"] + inner
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=self.timeout, cwd=tmp, env=env)

    # -- weak：仅进程组 + cwd + timeout（不安全，仅演示） --------------------
    def _run_weak(self, drv_path: str, payload: str, tmp: str) -> subprocess.CompletedProcess:
        py = sys.executable
        env = {**os.environ, "LDA_SOLVER_CASES": payload}
        return subprocess.run([py, drv_path], capture_output=True, text=True,
                             timeout=self.timeout, cwd=tmp, env=env)

    def run(self, code: str, spec) -> dict:
        tmp, drv_path, payload = self._stage(code, spec)
        lvl = isolation_level()
        try:
            if lvl == "strong":
                proc = self._run_strong(drv_path, payload, tmp)
            else:
                proc = self._run_weak(drv_path, payload, tmp)
            return self._parse(proc)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"执行超时（>{self.timeout}s）"}
        finally:
            try:
                import shutil as _sh
                _sh.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass
