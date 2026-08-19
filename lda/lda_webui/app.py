#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LDA · 实时 Web 预览界面后端（零依赖）。

把已落地的内核（验证裁判 harness / L1 KernelGateway / agent 设计闭环 /
L2 开放 PDK Registry）通过 HTTP 暴露给一个真正的产品级前端，使
"现场跑 LDA 内核"可被交互式预览。

暴露接口：
  GET  /                 → index.html（产品级控制台）
  GET  /api/status        → 系统落地状态（哪些层已 built / planned）
  GET  /api/benchmarks    → 题库 B1–B11 定义
  GET  /api/pdks          → 已登记 PDK + 器件模板（L2）
  POST /api/verify        → {candidate, perturb?} 真跑 harness，返回逐题判定
  POST /api/agent_loop    → {solver, dual?} 真跑 agent 自迭代设计闭环
  POST /api/pdk_design    → {pdk, template, solver} 用 PDK 驱动 agent 逆设计
  POST /api/pdk_compare   → {device_type, solver} 跨多晶圆厂跑同器件类型逆设计对比

许可证纪律：零外部依赖（仅 Python 标准库），离线可跑、主权可控；
所有内核逻辑复用 lda_harness / lda_l1 / lda_agent / lda_l2，不在此处重写验证逻辑。
"""
import json
import math
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
LDA_ROOT = os.path.dirname(WEBUI_DIR)
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_harness.benchmarks import BENCHMARK_DEFS
from lda_harness.harness import (
    VerificationHarness, ReferenceCandidate, PerturbedCandidate,
)
from lda_harness.l3_ai_solver import L3AISolverCandidate
from lda_l1.protocol import KernelGateway
from lda_agent.design_loop import (
    DesignAgent, ring_fsr_problem, ring_fsr_with_waveguide_problem,
)
from lda_l2.pdk import get_default_registry

HARNESS = VerificationHarness(BENCHMARK_DEFS)
AGENT_OUT = os.path.join(LDA_ROOT, "reports_agent")


# --------------------------------------------------------------------------
# 内核调用（全部复用已落地模块）
# --------------------------------------------------------------------------
def build_results_json(results, meta):
    details = []
    for r in results:
        details.append({
            "id": r.bid, "metric": r.metric, "oracle": r.oracle,
            "source": getattr(r, "source", ""),
            "golden": r.golden, "candidate": r.candidate,
            "tol": r.tol, "passed": r.passed, "note": r.note,
        })
    passed = sum(1 for r in results if r.passed)
    return {
        "meta": meta,
        "summary": {"total": len(results), "passed": passed,
                    "failed": len(results) - passed},
        "details": details,
    }


def run_verify(payload):
    kind = payload.get("candidate", "reference")
    perturb = float(payload.get("perturb", 0.1) or 0.1)
    if kind == "l3_ai":
        cand = L3AISolverCandidate()
        name = "L3AISolverCandidate(llm=%s)" % cand.llm_enabled
    elif kind == "perturb":
        cand = PerturbedCandidate(perturb)
        name = "PerturbedCandidate(%.0f%%)" % (perturb * 100)
    else:
        cand = ReferenceCandidate()
        name = "ReferenceCandidate"
    specs = HARNESS.resolve_specs(None)
    results = HARNESS.run(specs, cand)
    meta = {"candidate": name, "oracle": "确定性物理定律锚（麦克斯韦方程的必然）"}
    return build_results_json(results, meta)


def run_agent_loop(payload):
    solver = payload.get("solver", "truth")
    dual = bool(payload.get("dual", False))
    gw = KernelGateway(out_dir=AGENT_OUT)
    agent = DesignAgent(gw, out_dir=AGENT_OUT)
    problem = (ring_fsr_with_waveguide_problem(target_fsr=9.15, solver=solver)
               if dual else ring_fsr_problem(target_fsr=9.15, solver=solver))
    result = agent.run(problem, max_iter=30)
    return result.to_dict()


def run_pdk_design(payload):
    """用 L2 PDK 模板驱动 agent 逆设计（工艺窗口内反推几何）。"""
    pdk_key = payload.get("pdk") or payload.get("pdk_key")
    template = payload.get("template")
    solver = payload.get("solver", "truth")
    if not pdk_key or not template:
        raise ValueError("需要 pdk 与 template 两个字段")
    reg = get_default_registry()
    problem = reg.derive_problem(pdk_key, template, solver)
    gw = KernelGateway(out_dir=AGENT_OUT)
    agent = DesignAgent(gw, out_dir=AGENT_OUT)
    result = agent.run(problem, max_iter=120)
    result_dict = result.to_dict()
    result_dict["pdk"] = pdk_key
    result_dict["template"] = template
    # 谱形可视化（环形谐振器且有 R 落点时）：纯解析洛伦兹梳，零依赖
    pdk_obj = reg.get(pdk_key)
    tpl = pdk_obj.templates.get(template)
    if (tpl and tpl.device_type == "ring_resonator"
            and "R" in result_dict.get("final_param", {})):
        ng = tpl.fixed_params.get("n_g", 4.2)
        wl0 = tpl.fixed_params.get("wavelength", 1.55)
        result_dict["spectrum"] = ring_spectrum(
            result_dict["final_param"]["R"], ng, wl0)
        result_dict["process"] = {
            "foundry": pdk_obj.foundry, "node": pdk_obj.node,
            "n_si": pdk_obj.n_si, "n_clad": pdk_obj.n_clad,
        }
    return result_dict


def ring_spectrum(R, n_g, wl0=1.55, target_fsr=9.15, npts=401):
    """环形 drop 端口透射谱（洛伦兹梳），给定 R/n_g/wl0。

    返回 {wls, trans, target_wls, target_trans, fsr_nm, target_fsr}。
    纯解析（确定性物理），零依赖——用于 B11 目标谱形可视化。
    """
    fsr_nm = wl0 ** 2 / (n_g * 2.0 * math.pi * R) * 1000.0
    span = max(fsr_nm * 3.0, 1.0)
    lo, hi = wl0 - span / 2.0, wl0 + span / 2.0
    wls = [lo + (hi - lo) * i / (npts - 1) for i in range(npts)]
    gamma = fsr_nm / 40.0  # 线宽（高 Q 近似）

    def comb(spacing):
        out = []
        for wl in wls:
            tot = 0.0
            for m in range(-3, 4):
                res = wl0 + m * spacing
                tot += (gamma / 2.0) ** 2 / ((wl - res) ** 2 + (gamma / 2.0) ** 2)
            out.append(min(tot, 1.5))
        return out

    trans = comb(fsr_nm)
    target_trans = comb(target_fsr)
    return {"wls": wls, "trans": trans, "target_wls": wls,
            "target_trans": target_trans, "fsr_nm": round(fsr_nm, 4),
            "target_fsr": target_fsr}


def run_pdk_compare(payload):
    """跨所有已登记 foundry 跑同一器件类型逆设计，对比工艺窗口差异。

    返回 {device_type, rows:[{foundry, node, n_si, param_window,
    converged, final_param, final_metric, final_passed_all, spectrum, note}]}。
    量子 foundry 无该器件类型时自动跳过——演示 L2「开放 PDK / 多晶圆厂共建」。
    """
    device_type = payload.get("device_type", "ring_resonator")
    solver = payload.get("solver", "truth")
    reg = get_default_registry()
    gw = KernelGateway(out_dir=AGENT_OUT)
    agent = DesignAgent(gw, out_dir=AGENT_OUT)
    rows = []
    for key in reg.list_pdks():
        pdk = reg.get(key)
        tpl = None
        for t in pdk.templates.values():
            if t.device_type == device_type:
                tpl = t
                break
        if tpl is None:
            continue
        problem = reg.derive_problem(key, tpl.name, solver)
        result = agent.run(problem, max_iter=120)
        rd = result.to_dict()
        bounds = (list(tpl.bounds) if tpl.tunable and tpl.bounds
                  else (list(next(iter(tpl.tunables.values())))
                        if tpl.tunables else None))
        ng = tpl.fixed_params.get("n_g", 4.2)
        wl0 = tpl.fixed_params.get("wavelength", 1.55)
        spec = None
        if "R" in rd.get("final_param", {}):
            spec = ring_spectrum(rd["final_param"]["R"], ng, wl0)
        rows.append({
            "foundry": pdk.foundry, "node": pdk.node,
            "template": tpl.name, "n_si": pdk.n_si, "n_clad": pdk.n_clad,
            "param_window": bounds, "device_type": device_type,
            "converged": rd["converged"], "final_param": rd["final_param"],
            "final_metric": rd["final_metric"],
            "final_passed_all": rd["final_passed_all"],
            "spectrum": spec, "note": rd["note"],
        })
    return {"device_type": device_type, "rows": rows}


def _run_ir_plans(m, reg, gw, agent, max_iter=120, solver="truth"):
    """通用：IR → 校验 → 多 foundry 桥接 → 真跑，返回 (errs, rows)。

    同一函数服务光子与量子 IR——证明"统一 IR"对两种 domain 一视同仁。
    """
    from lda_ir.bridge import ir_to_multifoundry
    from lda_ir import validate
    errs = validate(m)
    plans = ir_to_multifoundry(m, reg, solver=solver)
    rows = []
    for key, prob in plans:
        res = agent.run(prob, max_iter=max_iter)
        rows.append({
            "foundry": key,
            "final_param": res.final_param,
            "final_metric": res.final_metric,
            "converged": res.converged,
            "final_passed_all": res.final_passed_all,
            "note": res.note,
        })
    return errs, rows


def run_ir_demo(payload=None):
    """L0 统一 IR / DSL 草案真跑演示：同时构造**光子**与**量子**两段 IR，
    经同一套桥接层 + agent 设计闭环真跑，返回各段结果。证明"统一光子+量子"
    不是口号——同一 IR 机器语言驱动光子谱形逆设计与量子 transmon 频率逆设计。

      - 光子段：环形谐振器目标谱形（B11 FSR）+ 跨多 foundry 落点差异；
      - 量子段：transmon 频率逆设计（B9，调 E_J/E_C 命中 f01）+ 跨量子 foundry。
    """
    from lda_ir import (FoundryPlan, IRModel, ObjectiveSpec, RingResonator,
                        SpectrumSpec, Transmon, to_dsl, validate)
    from lda_ir.bridge import ir_eval
    target_fsr = (payload or {}).get("target_fsr_nm", 9.15)
    solver = (payload or {}).get("solver", "truth")
    reg = get_default_registry()
    gw = KernelGateway(out_dir=AGENT_OUT)
    agent = DesignAgent(gw, out_dir=AGENT_OUT)

    # —— 光子段 IR（目标谱形 + 多 foundry）——
    # n_g 不写死：由 foundry 工艺窗口（n_si）注入，设计者只调几何 R
    m_ph = IRModel(
        domain="photon", name="ring-fsr-B11",
        components=[RingResonator(id="ring", R=10.0, R_bounds=(8.0, 14.0))],
        spectrum=SpectrumSpec(kind="ring_fsr", target_fsr_nm=target_fsr,
                              wl0_um=1.55, primary_param="R"),
        foundry_plan=FoundryPlan(mode="all"),
    )
    ph_errs, ph_rows = _run_ir_plans(m_ph, reg, gw, agent, max_iter=120, solver=solver)

    # —— 量子段 IR（transmon 频率逆设计，复用同一套 IR 地基）——
    # E_C 不写死：由 foundry 量子窗口（ec_default）工艺固定，设计者只调 E_J
    m_q = IRModel(
        domain="quantum", name="transmon-f01-B9",
        components=[Transmon(id="q1", E_J=20.0,
                             EJ_bounds=(5.0, 40.0), EC_bounds=(0.1, 1.0))],
        objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1,
                                  role="objective")],
        foundry_plan=FoundryPlan(mode="all"),  # domain 过滤 → 仅量子 foundry
    )
    q_errs, q_rows = _run_ir_plans(m_q, reg, gw, agent, max_iter=120, solver=solver)

    # —— IR 直接真值演示（L3 直接消费 IR，不经 DesignProblem）——
    # 取光子段首个 foundry 的收敛落点，用 ir_eval 直接算真值 + 判定，
    # 证明"IR 即事实源"：验证裁判与逆设计共用同一份 IR 意图。
    ir_eval_rows = []
    if ph_rows:
        fk = ph_rows[0]["foundry"]
        hit_r = ph_rows[0]["final_param"].get("R")
        if hit_r is not None:
            ev = ir_eval(m_ph, {"R": hit_r}, foundry_key=fk, registry=reg)
            ir_eval_rows.append({
                "foundry": fk, "param": {"R": hit_r},
                "bid": "B11", "value": ev["rows"]["B11"]["candidate"],
                "passed": ev["rows"]["B11"]["passed"],
                "source": ev["rows"]["B11"]["source"],
            })

    return {
        "photon": {
            "ir_name": m_ph.name, "validate_errors": ph_errs,
            "dsl": to_dsl(m_ph), "target_fsr_nm": target_fsr, "rows": ph_rows,
        },
        "quantum": {
            "ir_name": m_q.name, "validate_errors": q_errs,
            "dsl": to_dsl(m_q), "target_f01_ghz": 5.0, "rows": q_rows,
        },
        "ir_eval": ir_eval_rows,
    }


def system_status():
    return {
        "layers": [
            {"id": "L0", "name": "统一 IR / DSL（机器优先·含谱形+多 foundry）", "status": "built"},
            {"id": "L1", "name": "agent 协议层 + 真·MCP", "status": "built"},
            {"id": "L2", "name": "PDK Registry（社区共建）", "status": "built"},
            {"id": "L3", "name": "AI 写求解内核", "status": "built"},
            {"id": "harness", "name": "验证裁判（物理定律锚）", "status": "built"},
            {"id": "field", "name": "B5–B7 场级 ORACLE", "status": "built"},
            {"id": "agent", "name": "agent 自迭代设计闭环", "status": "built"},
            {"id": "ui", "name": "L4 产品级实时 UI", "status": "built"},
        ],
        "benchmarks_total": len(BENCHMARK_DEFS),
    }


# --------------------------------------------------------------------------
# HTTP 处理
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, body=None, ctype="application/json"):
        if body is None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            p = os.path.join(WEBUI_DIR, "static", "index.html")
            with open(p, "rb") as f:
                self._send(200, body=f.read(), ctype="text/html")
        elif path == "/api/status":
            self._send(200, system_status())
        elif path == "/api/benchmarks":
            bm = [{"id": k, "title": v.get("title"), "metric": v.get("metric"),
                   "oracle": v.get("oracle"), "tol": v.get("tol")}
                  for k, v in BENCHMARK_DEFS.items()]
            self._send(200, {"benchmarks": bm})
        elif path == "/api/pdks":
            reg = get_default_registry()
            self._send(200, {"pdks": reg.to_summary(), "keys": reg.list_pdks()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            payload = {}
        try:
            if path == "/api/verify":
                self._send(200, run_verify(payload))
            elif path == "/api/agent_loop":
                self._send(200, run_agent_loop(payload))
            elif path == "/api/pdk_design":
                self._send(200, run_pdk_design(payload))
            elif path == "/api/pdk_compare":
                self._send(200, run_pdk_compare(payload))
            elif path == "/api/ir_demo":
                self._send(200, run_ir_demo(payload))
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})

    def log_message(self, *a):
        pass


def main():
    port = int(os.environ.get("LDA_WEBUI_PORT", "8787"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("LDA webui serving on http://0.0.0.0:%d" % port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
