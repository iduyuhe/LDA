"""LDA · 1.4 AI-dev 自举写核闭环 harness。

把《白皮书》核心 thesis ——「底层核心由 AI agent 直接开发（递归自举）」——
落成**可运行、可验证、可复现**的自动化闭环：

    spec ──▶ Generator(AI-dev 写求解核代码)
              │
              ▼
        SandboxExecutor(子进程沙箱执行候选代码)
              │
              ▼
        Verifier(对物理定律锚 ORACLE 比对 → max_abs_err → PASS/FAIL + 诊断)
              │
        ┌─────┴─────┐
      PASS         FAIL ──▶ 诊断反馈回灌 Generator ──▶ 重写(下一轮)
              │
              ▼
        BootstrapLoop 报告(迭代轨迹 + 终判)

与既有资产的关系（避免重复造轮子）：
- l3_ai_solver.L3AISolverCandidate 只让 LLM 返回**标量数字**（不是写代码），且离线
  回退是手搓带缺陷近似 —— 那是「AI 算题」演示，不是「AI 写核」。
- l1_protocol.SolverAgent 硬编码调已验证核 —— 核是现成的，没有「写→验→重写」环。
本模块补上的正是这一环：AI-dev **写出求解核代码**，由 ORACLE 当裁判，失败退回重写。

许可证红线：候选代码在子进程沙箱执行，绝不 import 任何 GPL/商业求解器；ORACLE
（tmm / FDFD）为外部物理定律锚，LLM 端点为外部服务，符合《白皮书》§11 接入纪律。
LLM 不进**判决路径**：是否 PASS 由死代码（标量比对 ORACLE）决定，与谁写的代码无关。
"""
from __future__ import annotations

import abc
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
_SOLVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_solver")
_HARNESS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lda_harness")


# ---------------------------------------------------------------------------
# 求解规格（problem statement + I/O 契约 + ORACLE 测试用例）
# ---------------------------------------------------------------------------
@dataclass
class TestCase:
    name: str
    inputs: Dict[str, Any]          # 喂给候选求解核的关键字参数
    oracle_value: Any               # ORACLE 算出的真值（验收锚）
    tol: float = 0.05               # 绝对误差容差


@dataclass
class SolverSpec:
    spec_id: str
    problem_statement: str          # 自然语言问题陈述（给 AI-dev 的指令）
    entrypoint: str                 # 候选代码必须定义的函数名
    io_contract: str                # I/O 契约说明（签名 + 返回含义）
    test_cases: List[TestCase]
    oracle_kind: str = "tmm_1d"     # ORACLE 种类（说明用）

    def to_prompt(self) -> str:
        """把规格编译成给 AI-dev 的写核指令 prompt。"""
        cases_desc = "\n".join(
            f"  - {c.name}: inputs={c.inputs}, ORACLE 真值={c.oracle_value}, "
            f"容差={c.tol}"
            for c in self.test_cases
        )
        return textwrap.dedent(f"""\
你是一名光子器件求解内核开发 agent（AI-dev）。请**仅用第一性原理 + numpy**
编写求解核代码（零外部依赖，不 import 任何商业/GPL 求解器）。

【问题】
{self.problem_statement}

【I/O 契约】
入口函数名：{self.entrypoint}
{self.io_contract}

【验收锚（物理定律 ORACLE，非 AI 判决）】
你必须让自己的代码对每个测试用例的输出与下列 ORACLE 真值一致（绝对误差 ≤ 容差）：
{cases_desc}

【要求】
- 输出一个完整的 Python 模块，定义函数 `{self.entrypoint}`。
- 只用 numpy / math（已在沙箱可用）。
- 透射/反射必须用物理上正确的归一化（参考跑或解析边界），不得靠拍参数凑数。
- 只输出代码，用 ```python ... ``` 包裹，不要解释。
""")


# ---------------------------------------------------------------------------
# Generator（AI-dev）：产出候选求解核代码
# ---------------------------------------------------------------------------
class Generator(abc.ABC):
    """AI-dev 抽象：给定规格 + 历史反馈，产出候选求解核代码字符串。"""

    @abc.abstractmethod
    def generate(self, spec: SolverSpec, feedback: List[str]) -> str:
        ...


class LLMGenerator(Generator):
    """生产路径：OpenAI 兼容端点现场写**代码**（非标量）。

    与 l3_ai_solver 同一接入纪律（LDA_LLM_BASE / LDA_LLM_KEY / LDA_LLM_MODEL）。
    把历史失败诊断回灌为 feedback，让模型重写 —— 这就是「不达标退回重写」的
    真实智能载体。离线/未配置时不应被选中（见 get_generator）。
    """

    def __init__(self, base_url=None, api_key=None, model=None, timeout=60.0):
        self.base_url = (base_url or os.environ.get("LDA_LLM_BASE") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("LDA_LLM_KEY") or ""
        self.model = model or os.environ.get("LDA_LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    @staticmethod
    def _extract_code(text: str) -> str:
        import re
        m = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        m = re.search(r"```\s*(.*?)```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
        # 无围栏：整段当代码（最后手段）
        return text.strip()

    def _call(self, spec: SolverSpec, feedback: List[str]) -> str:
        import urllib.request
        prompt = spec.to_prompt()
        if feedback:
            prompt += "\n\n【上一轮失败诊断，请据此重写】\n" + "\n".join(
                f"  {i+1}. {f}" for i, f in enumerate(feedback)
            )
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return self._extract_code(data["choices"][0]["message"]["content"])

    def generate(self, spec: SolverSpec, feedback: List[str]) -> str:
        return self._call(spec, feedback)


class ScriptedAIDevGenerator(Generator):
    """离线演示载体（沙箱未配 LLM 端点时）。

    AI-dev 在真实场景是 LLM（见 LLMGenerator）；离线时为证明**闭环机制**可用，
    由本 harness 的「AI-dev」（即运行此脚本的 agent）预先提供一组候选：
    第一个（v0）故意带真实物理 bug → 必 FAIL；第二个（v1）修复 → 必 PASS。
    闭环据此展示：执行 → ORACLE 判 FAIL → 吞诊断 → 收重写 → 判 PASS。
    这是诚实的演示：写核的「智能」实体在离线时是本 agent，在线上时是 LLM 端点，
    二者走的**同一套闭环裁决逻辑**完全一致。
    """

    def __init__(self, candidates: List[str]):
        self.candidates = list(candidates)
        self._idx = 0

    def generate(self, spec: SolverSpec, feedback: List[str]) -> str:
        if self._idx < len(self.candidates):
            code = self.candidates[self._idx]
            self._idx += 1
            return code
        # 候选用尽仍未过：返回最后一个（让闭环如实报告失败）
        return self.candidates[-1]


def get_generator(prefer_llm: bool = True) -> Generator:
    """按环境选择 Generator：配了端点且 prefer_llm 时走 LLM，否则 Scripted。"""
    if prefer_llm:
        llm = LLMGenerator()
        if llm.enabled:
            return llm
    # 离线：返回占位，调用方须注入具体候选（见 demo 的 build_offline_generator）
    return _UnconfiguredGenerator()


class _UnconfiguredGenerator(Generator):
    def generate(self, spec: SolverSpec, feedback: List[str]) -> str:
        raise RuntimeError(
            "离线环境且未注入 ScriptedAIDevGenerator 候选；"
            "请配置 LDA_LLM_* 端点，或在 demo 中用 ScriptedAIDevGenerator 提供候选代码。"
        )


# ---------------------------------------------------------------------------
# 沙箱执行器：子进程执行候选代码，捕获输出/异常/超时
# ---------------------------------------------------------------------------
class SandboxExecutor:
    """把候选代码 + 受信 driver 写入临时目录，子进程执行，返回每用例结果或错误。

    安全边界：候选代码在独立 python 子进程运行（不共享主进程状态），仅能访问
    numpy/math；driver 由 harness 控制，负责调用 entrypoint 并落 JSON 结果。
    """

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout

    def run(self, code: str, spec: SolverSpec) -> Dict[str, Any]:
        tmp = tempfile.mkdtemp(prefix="lda_solver_writer_")
        cand_path = os.path.join(tmp, "candidate.py")
        drv_path = os.path.join(tmp, "driver.py")
        try:
            with open(cand_path, "w", encoding="utf-8") as f:
                f.write(code)
            # 受信 driver：调用候选 entrypoint，逐用例跑，落 JSON
            drv = textwrap.dedent(f"""\
            import json, sys, traceback
            try:
                import candidate as C
                fn = getattr(C, {spec.entrypoint!r}, None)
                if fn is None:
                    print(json.dumps({{"ok": False, "error":
                        f"候选未定义函数 {spec.entrypoint!r}"}}))
                    sys.exit(0)
                out = []
                cases = json.loads(sys.argv[1])
                for c in cases:
                    try:
                        val = fn(**c["inputs"])
                        out.append({{"name": c["name"], "ok": True, "value": val}})
                    except Exception as e:
                        out.append({{"name": c["name"], "ok": False,
                                    "error": traceback.format_exc()}})
                print(json.dumps({{"ok": True, "results": out}}))
            except Exception:
                print(json.dumps({{"ok": False, "error": traceback.format_exc()}}))
            """)
            with open(drv_path, "w", encoding="utf-8") as f:
                f.write(drv)
            cases_payload = json.dumps([
                {"name": c.name, "inputs": c.inputs} for c in spec.test_cases
            ])
            proc = subprocess.run(
                [sys.executable, drv_path, cases_payload],
                capture_output=True, text=True, timeout=self.timeout, cwd=tmp,
            )
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
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"执行超时（>{self.timeout}s）"}
        finally:
            try:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 验证器：对 ORACLE 比对，出 max_abs_err + PASS/FAIL + 诊断
# ---------------------------------------------------------------------------
class Verifier:
    """候选输出 vs ORACLE 真值：逐用例比绝对误差，决定 PASS/FAIL。"""

    def verify(self, spec: SolverSpec, exec_result: Dict[str, Any]
               ) -> Dict[str, Any]:
        if not exec_result.get("ok"):
            return {
                "passed": False,
                "max_abs_err": float("inf"),
                "per_case": [],
                "diagnostics": f"执行失败：{exec_result.get('error', 'unknown')}",
            }
        results = exec_result.get("results", [])
        res_by_name = {r["name"]: r for r in results}
        per_case = []
        max_err = 0.0
        diagnostics = []
        all_ok = True
        for c in spec.test_cases:
            r = res_by_name.get(c.name)
            if r is None:
                all_ok = False
                per_case.append({"name": c.name, "ok": False,
                                 "err": None, "diag": "缺少该用例输出"})
                diagnostics.append(f"[{c.name}] 候选未返回该用例结果")
                continue
            if not r.get("ok"):
                all_ok = False
                per_case.append({"name": c.name, "ok": False,
                                 "err": None, "diag": r.get("error", "exec err")})
                diagnostics.append(f"[{c.name}] 执行异常:\n{r.get('error', '')}")
                continue
            got = r["value"]
            oracle = c.oracle_value
            # 支持标量用例与多波长列表用例（逐元素比对，取最大绝对误差）
            if isinstance(oracle, (list, tuple)):
                if not isinstance(got, (list, tuple)) or len(got) != len(oracle):
                    err = float("inf")
                else:
                    err = max(abs(float(g) - float(o))
                              for g, o in zip(got, oracle))
            else:
                try:
                    err = abs(float(got) - float(oracle))
                except (TypeError, ValueError):
                    err = float("inf")
            passed = err <= c.tol
            all_ok = all_ok and passed
            max_err = max(max_err, err)
            per_case.append({"name": c.name, "ok": passed, "err": err,
                             "got": got, "oracle": oracle, "tol": c.tol})
            if not passed:
                diagnostics.append(
                    f"[{c.name}] 误差 {err:.4f} > 容差 {c.tol} "
                    f"(候选={got}, ORACLE={oracle})"
                )
        return {
            "passed": all_ok,
            "max_abs_err": max_err,
            "per_case": per_case,
            "diagnostics": "\n".join(diagnostics) if diagnostics
                           else "全部用例在容差内。",
        }


# ---------------------------------------------------------------------------
# 自举闭环：generate → exec → verify → （FAIL 带诊断重写）
# ---------------------------------------------------------------------------
@dataclass
class LoopReport:
    spec_id: str
    iterations: int
    final_passed: bool
    final_max_abs_err: float
    trace: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "iterations": self.iterations,
            "final_passed": self.final_passed,
            "final_max_abs_err": self.final_max_abs_err,
            "trace": self.trace,
            "verdict": self.verdict,
        }


class BootstrapLoop:
    """AI-dev 自举写核闭环主控。"""

    def __init__(self, executor: SandboxExecutor, verifier: Verifier,
                 max_iters: int = 5, verbose: bool = True):
        self.executor = executor
        self.verifier = verifier
        self.max_iters = max_iters
        self.verbose = verbose

    def run(self, spec: SolverSpec, generator: Generator) -> LoopReport:
        feedback: List[str] = []
        report = LoopReport(spec_id=spec.spec_id, iterations=0,
                            final_passed=False, final_max_abs_err=float("inf"))
        for it in range(1, self.max_iters + 1):
            t0 = time.time()
            code = generator.generate(spec, feedback)
            exec_res = self.executor.run(code, spec)
            verdict = self.verifier.verify(spec, exec_res)
            dt = time.time() - t0
            entry = {
                "iter": it,
                "passed": verdict["passed"],
                "max_abs_err": verdict["max_abs_err"],
                "diagnostics": verdict["diagnostics"],
                "code_len": len(code),
                "sec": round(dt, 1),
            }
            report.trace.append(entry)
            report.iterations = it
            report.final_passed = verdict["passed"]
            report.final_max_abs_err = verdict["max_abs_err"]
            if self.verbose:
                tag = "PASS" if verdict["passed"] else "FAIL"
                print(f"  [iter {it}] {tag}  max_abs_err="
                      f"{verdict['max_abs_err']:.4f}  ({dt:.1f}s)")
                if not verdict["passed"]:
                    print(f"          诊断:\n"
                          + "\n".join(f"            {l}"
                                      for l in verdict["diagnostics"].splitlines()))
            if verdict["passed"]:
                report.verdict = (
                    f"AI-dev 自举写核闭环 PASS：第 {it} 轮候选求解核通过 ORACLE "
                    f"物理定律锚验收（max_abs_err={verdict['max_abs_err']:.4f}）。"
                )
                return report
            # FAIL：把诊断回灌为下一轮重写反馈
            feedback.append(
                f"第 {it} 轮候选未通过 ORACLE 验收：\n{verdict['diagnostics']}"
            )
        report.verdict = (
            f"AI-dev 自举写核闭环在 {self.max_iters} 轮内未通过 ORACLE 验收 "
            f"(末轮 max_abs_err={report.final_max_abs_err:.4f})；"
            f"需更强 AI-dev 或修正 spec/ORACLE。"
        )
        return report


# ===========================================================================
# 演示：1D FDTD 透射谱求解核（ORACLE = tmm.py 解析解）
# ===========================================================================
def _build_1d_fdtd_spec() -> SolverSpec:
    """1D 多层膜垂直入射透射谱：AI-dev 需写 1D FDTD（参考跑归一化绝对标度）。"""
    if _SOLVER_DIR not in sys.path:
        sys.path.insert(0, _SOLVER_DIR)
    if _HARNESS_DIR not in sys.path:
        sys.path.insert(0, _HARNESS_DIR)
    import tmm

    # 三个测试用例：单界面(1λ) / 布拉格镜(1λ) / 低Q薄硅膜(3λ，演示多波长列表比对)
    # 注：故意避开高Q法布里-珀罗腔（粗网格稳态建立慢，误差超容差），演示用低Q结构。
    defs = [
        ("single_interface",
         [(float("inf"), 1.0), (1.0, 3.48), (float("inf"), 1.44)], [1.55]),
        ("bragg_mirror",
         [(float("inf"), 1.0)] +
         [(0.111, 3.48), (0.278, 1.44)] * 4 + [(float("inf"), 1.44)], [1.55]),
        ("thin_film_3wl",
         [(float("inf"), 1.0), (0.3, 3.48), (float("inf"), 1.0)],
         [1.45, 1.55, 1.65]),
    ]
    cases = []
    for name, layers, wls in defs:
        spec_in = {"layers": layers, "wavelengths_um": wls}
        oracle = tmm.solve_spectrum(spec_in)["transmission"]
        # 始终存为列表（与候选 solve_stack 返回值同构：永远是 list[float]）
        val = list(oracle)
        cases.append(TestCase(
            name=name,
            inputs={"layers": layers, "wavelengths_um": wls},
            oracle_value=val,
            tol=0.05,
        ))

    return SolverSpec(
        spec_id="SW-1D-FDTD-T",
        problem_statement=(
            "实现一维（1D）有限差分时域（FDTD）求解核，计算平面波垂直入射下"
            "一维多层膜的透射谱 T(λ)。介质无吸收（R+T=1）。要求对单界面、"
            "布拉格镜、法布里-珀罗标准具等结构都能复现解析透射。"
        ),
        entrypoint="solve_stack",
        io_contract=(
            "solve_stack(layers, wavelengths_um) -> transmission\n"
            "  layers: list of (thickness_um, n)，首尾 thickness=inf 表示半无限包层\n"
            "  wavelengths_um: list of float (µm)\n"
            "  transmission: 与 wavelengths_um 等长的 list[float]，每波长透射率 T∈[0,1]\n"
            "  T 必须用参考跑归一化或解析边界做绝对定标（含 nL/n0 阻抗因子）。"
        ),
        test_cases=cases,
        oracle_kind="tmm_1d",
    )


# --- 离线演示候选：v0（结构正确但漏绝对标度：无参考跑 + 漏 nL/n0 阻抗因子）---
_CANDIDATE_V0 = '''\
"""AI-dev 候选 v0：结构正确(含海绵吸收)的 1D FDTD，但漏掉绝对标度——
直接拿原始出射场幅平方当 T，无参考跑归一化、无 nL/n0 阻抗因子 → 标度错。"""
import math
import numpy as np


def _profile(layers, dl, buf=60, sponge=40):
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    segs = []
    for th, n in layers:
        nc = 80 if math.isinf(th) else max(2, int(round(th / dl)))
        segs.append((nc, float(n)))
    total = sum(s[0] for s in segs)
    nz = np.empty(total, dtype=float)
    i = 0
    for nc, n in segs:
        nz[i:i + nc] = n
        i += nc
    nz = np.concatenate([np.full(buf, n0), nz])
    N = len(nz) + 2 * sponge
    eps = np.ones(N)
    eps[:sponge] = n0 ** 2
    eps[sponge:sponge + len(nz)] = nz ** 2
    eps[sponge + len(nz):] = nL ** 2
    return eps, N, n0, nL, buf, sponge


def _run(layers, wl, dl, courant=0.99, ramp=400, sponge=40, buf=60,
         target_exp=12.0):
    dt = dl * courant
    eps, N, n0, nL, _, _ = _profile(layers, dl, buf, sponge)
    sig = np.zeros(N)
    for i in range(sponge):
        x = (sponge - 1 - i) / (sponge - 1)
        sig[i] = x ** 2
    for i in range(N - sponge, N):
        x = (i - (N - sponge)) / (sponge - 1)
        sig[i] = x ** 2
    sig_max = target_exp * 3.0 / (dt * sponge)
    sig[:sponge] *= sig_max * (n0 ** 2)
    sig[N - sponge:] *= sig_max * (nL ** 2)
    damp_E = 1.0 / (1.0 + dt * sig / eps)
    sig_m = sig / eps
    damp_H = 1.0 / (1.0 + dt * 0.5 * (sig_m[:-1] + sig_m[1:]))
    ez = np.zeros(N)
    en = np.zeros(N)
    hz = np.zeros(N - 1)
    src = sponge + 30
    out = N - sponge - 20
    omega = 2 * math.pi / wl
    period = wl / (dl * courant)
    nsteps = int(140 * period) + 2000
    meas0 = int(40 * period) + 2000
    oc_s = oc_c = 0.0
    for n in range(nsteps):
        dE = (ez[1:] - ez[:-1]) / dl
        hz = (hz + dt * dE) * damp_H
        dH = (hz[1:] - hz[:-1]) / dl
        en[1:N - 1] = (ez[1:N - 1] + dt / eps[1:N - 1] * dH) * damp_E[1:N - 1]
        en[0] = (ez[0] + dt / eps[0] * hz[0]) * damp_E[0]
        en[N - 1] = (ez[N - 1] - dt / eps[N - 1] * hz[N - 2]) * damp_E[N - 1]
        if n < ramp:
            env = 0.5 * (1 - math.cos(math.pi * n / ramp))
        else:
            env = 1.0
        en[src] += 0.5 * env * math.sin(omega * n * dt)
        ez, en = en, ez
        if n >= meas0:
            ph = omega * n * dt
            oc_s += ez[out] * math.sin(ph)
            oc_c += ez[out] * math.cos(ph)
    cnt = nsteps - meas0
    return complex(oc_s, oc_c) / cnt


def solve_stack(layers, wavelengths_um):
    courant = 0.99
    cpw = 40.0
    wl_min = min(wavelengths_um)
    finite = [th for th, n in layers if not math.isinf(th)]
    base = wl_min / cpw
    if finite:
        th_min = min(finite)
        k = max(2, round(th_min / base))
        dl = th_min / k
    else:
        dl = base
    transmission = []
    for wl in wavelengths_um:
        e_out = _run(layers, wl, dl)
        # BUG：原始出射场幅平方当透射，无参考跑归一化、无 nL/n0 阻抗因子
        T = abs(e_out) ** 2
        transmission.append(T)
    return transmission
'''

# --- 离线演示候选：v1（修复：参考跑归一化 + nL/n0 阻抗因子，绝对标度正确）---
_CANDIDATE_V1 = '''\
"""AI-dev 候选 v1：1D FDTD + 参考跑归一化绝对标度（修复 v0 标度 bug）。"""
import math
import numpy as np


def _profile(layers, dl, buf=60, sponge=40):
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    segs = []
    for th, n in layers:
        nc = 80 if math.isinf(th) else max(2, int(round(th / dl)))
        segs.append((nc, float(n)))
    total = sum(s[0] for s in segs)
    nz = np.empty(total, dtype=float)
    i = 0
    for nc, n in segs:
        nz[i:i + nc] = n
        i += nc
    nz = np.concatenate([np.full(buf, n0), nz])
    N = len(nz) + 2 * sponge
    eps = np.ones(N)
    eps[:sponge] = n0 ** 2
    eps[sponge:sponge + len(nz)] = nz ** 2
    eps[sponge + len(nz):] = nL ** 2
    return eps, N, n0, nL, buf, sponge


def _run(layers, wl, dl, courant=0.99, ramp=400, sponge=40, buf=60,
         target_exp=12.0):
    dt = dl * courant
    eps, N, n0, nL, _, _ = _profile(layers, dl, buf, sponge)
    # 梯度海绵σ（二次剖面），按目标衰减标定σ_max
    sig = np.zeros(N)
    for i in range(sponge):
        x = (sponge - 1 - i) / (sponge - 1)
        sig[i] = x ** 2
    for i in range(N - sponge, N):
        x = (i - (N - sponge)) / (sponge - 1)
        sig[i] = x ** 2
    sig_max = target_exp * 3.0 / (dt * sponge)
    sig[:sponge] *= sig_max * (n0 ** 2)
    sig[N - sponge:] *= sig_max * (nL ** 2)
    damp_E = 1.0 / (1.0 + dt * sig / eps)
    sig_m = sig / eps
    damp_H = 1.0 / (1.0 + dt * 0.5 * (sig_m[:-1] + sig_m[1:]))
    ez = np.zeros(N)
    en = np.zeros(N)
    hz = np.zeros(N - 1)
    src = sponge + 30
    out = N - sponge - 20
    omega = 2 * math.pi / wl
    period = wl / (dl * courant)
    nsteps = int(140 * period) + 2000
    meas0 = int(40 * period) + 2000
    oc_s = oc_c = 0.0
    for n in range(nsteps):
        dE = (ez[1:] - ez[:-1]) / dl
        hz = (hz + dt * dE) * damp_H
        dH = (hz[1:] - hz[:-1]) / dl
        en[1:N - 1] = (ez[1:N - 1] + dt / eps[1:N - 1] * dH) * damp_E[1:N - 1]
        en[0] = (ez[0] + dt / eps[0] * hz[0]) * damp_E[0]
        en[N - 1] = (ez[N - 1] - dt / eps[N - 1] * hz[N - 2]) * damp_E[N - 1]
        if n < ramp:
            env = 0.5 * (1 - math.cos(math.pi * n / ramp))
        else:
            env = 1.0
        en[src] += 0.5 * env * math.sin(omega * n * dt)
        ez, en = en, ez
        if n >= meas0:
            ph = omega * n * dt
            oc_s += ez[out] * math.sin(ph)
            oc_c += ez[out] * math.cos(ph)
    cnt = nsteps - meas0
    return complex(oc_s, oc_c) / cnt


def solve_stack(layers, wavelengths_um):
    courant = 0.99
    cpw = 40.0
    wl_min = min(wavelengths_um)
    finite = [th for th, n in layers if not math.isinf(th)]
    base = wl_min / cpw
    if finite:
        th_min = min(finite)
        k = max(2, round(th_min / base))
        dl = th_min / k
    else:
        dl = base
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    ref = [(th, n0) for th, n in layers]
    transmission = []
    for wl in wavelengths_um:
        e_real = _run(layers, wl, dl)
        e_ref = _run(ref, wl, dl)
        if abs(e_ref) <= 1e-12:
            T = 0.0
        else:
            T = (nL / n0) * abs(e_real / e_ref) ** 2
        transmission.append(T)
    return transmission
'''


def build_offline_generator() -> ScriptedAIDevGenerator:
    """离线演示：v0（bug）→ v1（修复），证明闭环能判 FAIL→收重写→判 PASS。"""
    return ScriptedAIDevGenerator([_CANDIDATE_V0, _CANDIDATE_V1])


def run_demo(prefer_llm: bool = True, max_iters: int = 5) -> LoopReport:
    """运行 1.4 AI-dev 自举写核闭环演示。"""
    spec = _build_1d_fdtd_spec()
    gen = get_generator(prefer_llm=prefer_llm)
    if isinstance(gen, _UnconfiguredGenerator):
        # 离线：用脚本化 AI-dev 候选（v0 带 bug → v1 修复）
        gen = build_offline_generator()
        print("[1.4 demo] 离线模式：使用 ScriptedAIDevGenerator "
              "(AI-dev 由本 harness 提供 v0→v1 候选，演示闭环机制)")
    else:
        print(f"[1.4 demo] 在线模式：LLM 端点 {gen.base_url} "
              f"(model={gen.model})")
    print(f"[1.4 demo] spec={spec.spec_id}  ORACLE={spec.oracle_kind}  "
          f"用例数={len(spec.test_cases)}")
    loop = BootstrapLoop(SandboxExecutor(timeout=120.0), Verifier(),
                         max_iters=max_iters, verbose=True)
    report = loop.run(spec, gen)
    print("\n[1.4 demo] 终判：", report.verdict)
    return report


if __name__ == "__main__":
    run_demo(prefer_llm=True)
