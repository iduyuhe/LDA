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
from lda_agent.design_loop import DesignAgent
from lda_agent.run_demo import build_intent
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
    """真跑 agent 自迭代设计闭环（复用 run_demo 的布拉格镜意图）。

    用真实 design_loop API（DesignAgent.run(intent)），后端 numpy 已实证。
    """
    backend = payload.get("backend", "numpy")
    geo = payload.get("geo", "stack")
    threshold = float(payload.get("threshold", 0.99))
    intent = build_intent(threshold, geo)
    intent["geo_kind"] = geo
    intent["extra"] = {"backend": backend, "dl_factor": 60.0, "sponge": 60, "ramp": 200}
    agent = DesignAgent(backend=backend, geo_kind=geo,
                        dl_factor=60.0, sponge=60, ramp=200)
    rep = agent.run(intent)
    return rep.to_dict()


def run_band_loop(payload):
    """D-03 多波长/宽带设计闭环（设计→仿真→验收 可视化）。

    复用 multiband_loop.BandDesignAgent：agent 增减布拉格周期数，使整个
    λ 扫描范围阻带达标（R≥threshold）且与 TMM 物理定律锚全波段谱形一致
    （max|ΔR|≤tol）。返回逐波长 R 曲线供前端绘图。
    """
    from lda_agent import multiband_loop as mb

    intent = {
        "geometry_type": "bragg_mirror",
        "materials": {"air": 1.0, "sih": 3.48, "silo": 1.44},
        "target_wavelength_um": float(payload.get("lam0", 1.55)),
        "target_metric": "R",
        "threshold": float(payload.get("threshold", 0.99)),
        "tolerance_rel": float(payload.get("tol", 0.02)),
        "max_iterations": int(payload.get("max_iter", 12)),
        "initial_periods": int(payload.get("periods", 6)),
        "extra": {
            "band_span_um": float(payload.get("band_span", 0.12)),
            "band_points": int(payload.get("band_points", 11)),
            "backend": "numpy",   # CI/演示机纯 numpy 可跑；GPU 机可改 torch
        },
    }
    rep = mb.main_band(intent)
    return rep


def run_ring_loop(payload):
    """D-11 环形谱形逆设计闭环（设计→仿真→验收 可视化）。

    复用 RingBandAgent：调 R 使 drop 谱 FSR 命中目标谱形（解析环形传递函数
    + 洛伦兹梳谱提取双判据）。返回逐波长洛伦兹梳谱曲线 + 收敛轨迹。纯解析，
    快、无 GPU 依赖。
    """
    from lda_agent.ring_loop import RingBandAgent

    ex = payload
    intent = {
        "geometry_type": "ring",
        "target_wavelength_um": float(ex.get("lam0", 1.55)),
        "target_metric": "spectrum_match",
        "tolerance_rel": float(ex.get("tol", 0.02)),
        "max_iterations": int(ex.get("max_iter", 40)),
        "extra": {
            "R_um": float(ex.get("R", 10.0)),
            "R_bounds": [float(v) for v in ex.get("R_bounds", [8.0, 12.0])],
            "n_g": float(ex.get("n_g", 4.2)),
            "Q": float(ex.get("Q", 1.0e4)),
            "kappa": float(ex.get("kappa", 0.05)),
            "target_fsr_nm": float(ex.get("target_fsr_nm", 9.15)),
            "wl0_um": float(ex.get("lam0", 1.55)),
            "target_tol": float(ex.get("target_tol", 0.03)),
            "backend": "numpy",
        },
    }
    return RingBandAgent().run(intent)


def _svg_item_from_desc(d):
    """geometry_desc → svg_preview item（boundary 多环展平）。"""
    layer = d.get("layer", 1)
    if d["kind"] == "boundary":
        rings = d.get("rings_um", [d.get("points_um", [])])
        pts = []
        for r in rings:
            pts.extend(r)
            pts.append(r[0])
        return ("boundary", {"points_um": pts, "layer": layer})
    return (d["kind"], {"points_um": d.get("points_um", []),
                        "width_um": d.get("width_um", 0.5), "layer": layer})


def run_layout_pipeline(payload):
    """D-17 版图流水线：器件/IR → GDS 版图 SVG + DRC 自查 + FDTD 仿真验收。

    三合一可视化：把 D-14 版图出口 + D-15 DRC + D-16 仿真串成一条命令，
    浏览器可看"设计→版图→DRC→仿真→验收"全自动闭环。参数从 D-12 器件库
    取默认窗口（可覆盖）。
    """
    from lda_l2 import drc as drc_mod
    from lda_l2 import gds_export as ge
    from lda_l2 import layout_sim as ls
    from lda_l2.device_library import get_default_library

    kind = payload.get("kind", "Waveguide")
    lib = get_default_library()
    if kind not in lib.list():
        return {"error": f"未知器件 kind={kind}（可用：{lib.list()}）", "passed": False}
    dev = lib.get(kind)
    params = {k: (lo + hi) / 2.0 for k, (lo, hi) in dev.params_schema.items()}
    params.update({k: float(v) for k, v in (payload.get("params") or {}).items()})

    desc_list = ge.geometry_desc(kind, params)
    svg = ge.svg_preview({kind: [_svg_item_from_desc(d) for d in desc_list]})
    drc_result = drc_mod.drc_check_device(kind, params)
    sim = ls.simulate_layout(desc_list, 3.48, 1.44, 1.55)
    return {
        "kind": kind,
        "params": params,
        "layout_svg": svg,
        "drc": drc_result.to_dict(),
        "sim": sim,
        "passed": bool(drc_result.passed and sim.get("passed", False)),
        "verdict": ("版图→DRC→仿真 全链路 PASS" if (drc_result.passed and sim.get("passed"))
                    else "链路未全过（见 DRC/仿真 详情）"),
    }


def run_design_pipeline(payload):
    """D-19/D-20/D-26 一键设计流水线（webui ⑨ 面板）。

    输入设计意图（器件 kind + 目标 FSR / 目标 neff / 参数覆盖），自动完成
    逆设计 → 版图 → DRC → 自动整改 → FDTD 仿真验收 → 设计包。返回完整报告
    + 版图 SVG。D-26：支持全部 4 器件（Ring target_fsr / Waveguide
    target_neff / DC / YBranch）。
    """
    from lda_agent.design_pipeline import run_pipeline

    kind = payload.get("kind", "RingResonator")
    params = {k: float(v) for k, v in (payload.get("params") or {}).items()} or None
    target_fsr = None
    if payload.get("target_fsr"):
        target_fsr = float(payload["target_fsr"])
    target_neff = None
    if payload.get("target_neff"):
        target_neff = float(payload["target_neff"])
    return run_pipeline(kind, params=params, target_fsr_nm=target_fsr,
                        target_neff=target_neff)


def run_ring_fdtd_demo(payload=None):
    """D-27/D-28 环形 FDTD 透射谱（webui ⑪ 面板）。

    加载预计算演示数据 reports/ring_fdtd_spectrum.json（D-27 核 CW 稳态逐波长，
    21 点 GPU ~6min 一次；webui 秒回完整 drop/thru 谱 + 谐振峰 + FSR 对拍）。
    实时重算需 GPU 且慢，不阻塞 HTTP——诚实标注为预计算演示数据。
    """
    path = os.path.join(LDA_ROOT, "reports", "ring_fdtd_spectrum.json")
    if not os.path.exists(path):
        return {"available": False, "error":
                "ring_fdtd_spectrum.json 缺失（需在 GPU 机预计算 D-27 环形 FDTD 谱）"}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["available"] = True
    return data


def run_dc_transmission_demo(payload=None):
    """D-29/D-30 DC 全场透射谱（webui ⑫ 面板）。

    加载预计算演示数据 reports/dc_transmission_spectrum.json（D-29 核 2D FDTD
    CW 稳态逐波长，numpy ~1min 一次；webui 秒回 cross/thru 谱 + κ_fdtd 反解）。
    诚实标注为预计算演示数据。
    """
    path = os.path.join(LDA_ROOT, "reports", "dc_transmission_spectrum.json")
    if not os.path.exists(path):
        return {"available": False, "error":
                "dc_transmission_spectrum.json 缺失（需先预计算 D-29 DC 透射谱）"}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["available"] = True
    return data


def run_device_library_demo(payload=None):
    """D-12/D-32/D-33 器件库验收（webui ⑬ 面板）。

    返回：器件库全景（5 器件：验收锚 / 参数窗口 / live_weight / 需 GPU /
    IR kind）+ 每器件 contract 快验收状态 + Ring 真实 FDTD 双验证（预计算
    D-32 smoke live 结果：解析契约 + FDTD drop 谱 4 峰 / FSR 对拍）+ WG/Bragg
    真实 FDTD 双验证（D-34 预计算）+ 量子 Transmon 双验证（D-35：Koch 解析
    契约 + 严格对角化自洽，现场跑，纯 numpy 秒级）。
    """
    from lda_l2.device_library import get_default_library
    lib = get_default_library()
    summary = lib.to_summary()
    # 每器件 contract 快验收（秒级）
    contracts = {}
    for name in lib.list():
        try:
            o = lib.verify_one(name, mode="contract")
            contracts[name] = {
                "passed": bool(o.passed), "spec_id": o.spec_id,
                "metric": o.metric, "oracle_kind": o.oracle_kind,
                "tol": o.tol, "tol_mode": o.tol_mode,
                "source": (o.source or "")[:70],
            }
        except Exception as e:  # noqa: BLE001
            contracts[name] = {"passed": False, "error": str(e)[:80]}
    # Ring FDTD 双验证：FDTD 谱用 D-28 预计算数据（独立产物，R=6 完整谱 +
    # peaks + FSR 对拍），解析契约现场快跑（RING-fsr，秒级）
    ring_fdtd = None
    path = os.path.join(LDA_ROOT, "reports", "ring_fdtd_spectrum.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                ring_fdtd = json.load(f)
        except Exception:  # noqa: BLE001
            ring_fdtd = None
    ring_analytic = None
    try:
        o = lib.verify_one("RingResonator", mode="live")
        ring_analytic = {
            "passed": bool(o.passed),
            "candidate_fsr_nm": o.candidate,
            "oracle_fsr_nm": o.oracle_value,
            "err": o.err, "tol": o.tol,
        }
    except Exception as e:  # noqa: BLE001
        ring_analytic = {"passed": False, "error": str(e)[:80]}
    # WG/Bragg 真实 FDTD 双验证（D-34）：FDTD 层用预计算 JSON（秒回），
    # 解析契约层现场跑 contract（秒级）—— 与 Ring 处理对称
    wg_bragg_fdtd = None
    wb_path = os.path.join(LDA_ROOT, "reports", "device_fdtd_wg_bragg.json")
    if os.path.exists(wb_path):
        try:
            with open(wb_path, encoding="utf-8") as f:
                wg_bragg_fdtd = json.load(f)
        except Exception:  # noqa: BLE001
            wg_bragg_fdtd = None
    wg_analytic, bragg_analytic = None, None
    try:
        o = lib.verify_waveguide_fdtd(mode="contract", width_um=0.5)
        wg_analytic = {"passed": bool(o["passed"]),
                       "slab_neff": o["checks"]["analytic_slab_neff"]["slab_neff"],
                       "physical": o["checks"]["analytic_slab_neff"]["physical"]}
    except Exception as e:  # noqa: BLE001
        wg_analytic = {"passed": False, "error": str(e)[:80]}
    try:
        o = lib.verify_bragg_fdtd(mode="contract")
        bragg_analytic = {"passed": bool(o["passed"]),
                         "tmm_import": o["checks"]["tmm_import"],
                         "fdtd3d_import": o["checks"]["fdtd3d_import"]}
    except Exception as e:  # noqa: BLE001
        bragg_analytic = {"passed": False, "error": str(e)[:80]}
    # 量子域 Transmon 双验证（D-35 实质推进）：现场跑 Koch 解析契约 + 严格对角化
    # 自洽（纯 numpy 对角化 <1s，零 GPU），与光子 D-32/D-34 同构
    transmon = None
    transmon_contract = None
    try:
        transmon = lib.verify_transmon(mode="live")
    except Exception as e:  # noqa: BLE001
        transmon = {"passed": False, "error": str(e)[:80]}
    try:
        transmon_contract = lib.verify_transmon(mode="contract")
    except Exception as e:  # noqa: BLE001
        transmon_contract = {"passed": False, "error": str(e)[:80]}
    # 量子域 D-39：Resonator / Coupler 双验证（闭式 ↔ 严格数值，纯 numpy 秒级）
    resonator = None
    resonator_contract = None
    coupler = None
    coupler_contract = None
    try:
        resonator = lib.verify_resonator(mode="live")
    except Exception as e:  # noqa: BLE001
        resonator = {"passed": False, "error": str(e)[:80]}
    try:
        resonator_contract = lib.verify_resonator(mode="contract")
    except Exception as e:  # noqa: BLE001
        resonator_contract = {"passed": False, "error": str(e)[:80]}
    try:
        coupler = lib.verify_coupler(mode="live")
    except Exception as e:  # noqa: BLE001
        coupler = {"passed": False, "error": str(e)[:80]}
    try:
        coupler_contract = lib.verify_coupler(mode="contract")
    except Exception as e:  # noqa: BLE001
        coupler_contract = {"passed": False, "error": str(e)[:80]}
    return {
        "available": True,
        "devices": summary,
        "contracts": contracts,
        "ring_fdtd": ring_fdtd,
        "ring_analytic": ring_analytic,
        "wg_fdtd": (wg_bragg_fdtd or {}).get("waveguide") if wg_bragg_fdtd else None,
        "bragg_fdtd": (wg_bragg_fdtd or {}).get("bragg") if wg_bragg_fdtd else None,
        "wg_analytic": wg_analytic,
        "bragg_analytic": bragg_analytic,
        "transmon_fdtd": transmon,
        "transmon_contract": transmon_contract,
        "resonator_fdtd": resonator,
        "resonator_contract": resonator_contract,
        "coupler_fdtd": coupler,
        "coupler_contract": coupler_contract,
        "note": "Ring/WG/Bragg 真实 FDTD 双验证：FDTD 层用预计算演示数据"
                "（D-28 Ring / D-34 WG-Bragg，纯 numpy 离线生成），"
                "解析契约层现场快跑（秒级）；量子 Transmon 双验证（D-35）"
                "现场跑 Koch 解析 + 严格对角化自洽（纯 numpy，<1s，零 GPU）；"
                "实时重算 Ring 需 GPU 不阻塞 HTTP",
    }


def run_design_loop(payload=None):
    """D-36 设计→验证闭环（webui ⑭ 面板）。

    输入 {kind, target, top_k?}：在参数网格用物理定律 ORACLE 快速搜索目标，
    仅对 top-K 候选跑真实求解器双重验证（解析契约 + 真实数值物理自洽，纯 numpy
    零 GPU），返回最优已验证设计。Ring 用解析锚（诚实标注 FDTD 抽检需 GPU）。
    LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_design.design_engine import DesignEngine
    try:
        eng = DesignEngine()
        return eng.design_request(payload or {})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_ring_package(payload=None):
    """D-37 环形 add-drop 完整产品链路（webui ⑮ 面板）。

    输入 {target_fsr?|R?|gap?|wg_width?}：一键产出可制造设计包——
    逆设计(R) → 双 bus 版图 GDS/SVG → DRC → bus FDTD 验收 + FSR 契约 +
    FDTD 锚点对拍 → 耦合/损耗预算（κ/Q/弯曲损耗/drop IL/消光比）→ 验收判决。
    现场跑（bus FDTD ~7s 纯 numpy），LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.ring_adddrop import build_package
    payload = payload or {}
    params = {}
    for k in ("R", "gap", "wg_width"):
        if payload.get(k) is not None:
            try:
                params[k] = float(payload[k])
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为数值"}
    target_fsr = None
    if payload.get("target_fsr") is not None:
        try:
            target_fsr = float(payload["target_fsr"])
        except (TypeError, ValueError):
            return {"ok": False, "error": "target_fsr 须为数值"}
    try:
        rep = build_package(target_fsr_nm=target_fsr, params=params or None)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_inverse_design_demo(payload=None):
    """D-38 agent 逆设计通用框架（webui ⑯ 面板）。

    输入 {kind?|target?}：经声明式注册表统一派发到 SpectrumInverseDesignAgent
    （D-24），落地 4 个真实器件（Ring/Bragg/Transmon/RingAddDrop，跨光子/量子、
    跨 match/threshold、跨连续/离散）。kind="all"（默认）跑全部。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.inverse_design import run_all_designs, run_inverse_design
    payload = payload or {}
    kind = payload.get("kind", "all")
    target = payload.get("target")
    extra = payload.get("extra") or {}
    try:
        if kind == "all":
            return run_all_designs(extra=extra)
        return run_inverse_design(kind,
                                  target_metric=float(target) if target is not None
                                  else None,
                                  extra=extra)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_quantum_design(payload=None):
    """D-41 量子 agent 逆设计最小闭环（webui ⑰ 面板）。

    输入 {kind, target, extra?}：目标频率/耦合 → D-40 量子 IR（PhysicsAnchor +
    objective）→ 校验 → 闭式物理反解 → D-39 严格数值双验证 → 报告。
    现场跑（纯 numpy 秒级，零 GPU），LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.quantum_design import design_quantum
    payload = payload or {}
    kind = payload.get("kind", "Transmon")
    target = payload.get("target")
    if target is None:
        return {"ok": False, "error": "需指定 target（目标 f01/f0/J，GHz）"}
    try:
        target = float(target)
    except (TypeError, ValueError):
        return {"ok": False, "error": "target 须为数值"}
    extra = {k: float(v) for k, v in (payload.get("extra") or {}).items()}
    try:
        return design_quantum(kind, target, extra)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_wdm_design(payload=None):
    """WDM 多环级联系统设计（webui ⑱ 面板，系统级纵深）。

    输入 {channels, gap?}：IR 网表（N 环 + bus 链）→ 信道逆设计（谐振对齐）
    → 级联传递 → 系统验收（drop IL / 串扰 XT / DRC / 单 FSR 防混叠）→
    N 环级联 GDS+SVG + 报告。纯解析模型秒级，LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.wdm_system import design_wdm, design_wdm_advanced
    payload = payload or {}
    ch_raw = payload.get("channels", "1550,1552.5,1555,1557.5")
    channels = None
    if ch_raw:
        try:
            channels = [float(x) for x in str(ch_raw).split(",") if x.strip()]
        except (TypeError, ValueError):
            return {"ok": False, "error": "channels 须为逗号分隔的波长(nm)列表"}
    gap = payload.get("gap", 0.3)
    try:
        gap = float(gap)
    except (TypeError, ValueError):
        return {"ok": False, "error": "gap 须为数值"}
    xt_target = payload.get("xt_target")
    if xt_target is not None:
        try:
            xt_target = float(xt_target)
        except (TypeError, ValueError):
            return {"ok": False, "error": "xt_target 须为数值"}
    try:
        if xt_target is not None:
            # XT 指标优先：强制反解 gap（忽略用户固定 gap）
            rep = design_wdm_advanced(channels_nm=channels or None,
                                      xt_target_db=xt_target, gap=None)
        else:
            rep = design_wdm(channels or [1550.0, 1552.5, 1555.0, 1557.5],
                             gap=gap)
        rep.setdefault("ok", True)
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_readout_chain(payload=None):
    """D-43 光子-量子混合链路：芯片级 dispersive readout（webui ⑲ 面板）。

    输入 {f01, delta?, g?, kappa_r?}：qubit ↔ readout 谐振器 ↔ 读出力线
    系统设计——闭式反解（E_J / l / Cc / Q_ext）→ 三器件双验证（D-39）+
    JC 精确对角化 ↔ 色散近似（χ=g²/Δ）交叉验证 → 系统验收（Δ/g、χ≥κ_r、
    Q_ext）→ 混合 IR 网表（domain=hybrid）。秒级零 GPU，LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.qubit_readout_chain import design_chain
    payload = payload or {}
    try:
        f01 = float(payload.get("f01", 5.0))
    except (TypeError, ValueError):
        return {"ok": False, "error": "f01 须为数值"}
    kw = {"f01": f01}
    for k in ("delta", "g", "kappa_r"):
        if payload.get(k) is not None:
            try:
                kw[k] = float(payload[k])
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为数值"}
    try:
        rep = design_chain(**kw)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_multiqubit_readout(payload=None):
    """D-46 N-qubit 频率复用读出（webui ㉑ 面板）。

    输入 {f01s?, delta?, g?, kappa_ext?}：N qubit → 各自 readout 谐振器沿
    公共力线频率错开（间隔≥3×κ_r）→ 逐 qubit 双验证 + JC ↔ 色散 χ →
    力线 hanger 级联透射（dip 可分辨判据）→ 系统验收 → 混合 IR 网表。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.multiqubit_readout import design_multiqubit_readout
    payload = payload or {}
    raw = payload.get("f01s", "4.8,5.0,5.2")
    if isinstance(raw, str):
        raw = raw.split(",")
    try:
        f01s = [float(x) for x in raw if str(x).strip()]
    except (TypeError, ValueError):
        return {"ok": False, "error": "f01s 须为逗号分隔的 qubit 频率(GHz)列表"}
    kw = {}
    for k in ("delta", "g", "kappa_ext"):
        if payload.get(k) is not None:
            try:
                kw[k] = float(payload[k])
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为数值"}
    try:
        rep = design_multiqubit_readout(f01s, **kw)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_readout_fidelity(payload=None):
    """D-47 单发读出保真度预算（webui ㉒ 面板）。

    输入 {f01?, delta?, g?, kappa_r?, T1_us?, nbar?, eta?, N_amp?}：
    相位积分 SNR(t_m) 模型 + T1 弛豫污染 → 最优读出时间 t_m* 扫描 →
    死标量验收（SNR/F/F1/污染预算/非破坏性/可分辨/色散区）。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.readout_fidelity import design_fidelity
    payload = payload or {}
    kw = {}
    for k in ("f01", "delta", "g", "kappa_r", "T1_us", "nbar", "eta", "N_amp"):
        if payload.get(k) is not None:
            try:
                kw[k] = float(payload[k])
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为数值"}
    try:
        rep = design_fidelity(**kw)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_multiqubit_fidelity(payload=None):
    """D-51 N-qubit 复用读出逐 qubit 保真度（webui ㉓ 面板）。

    输入 {f01s?, delta?, g?, T1_us?, nbar?}：频率复用（D-46）× 逐 qubit
    保真度（D-47）集成——readout 错开 + dip 可分辨 + 每 qubit 独立
    t_m*/SNR/F（T1/n̄ 可逐 qubit 不同）→ 系统级联合验收。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.multiqubit_fidelity import design_multiqubit_fidelity
    payload = payload or {}
    raw = payload.get("f01s", "4.8,5.0,5.2")
    if isinstance(raw, str):
        raw = raw.split(",")
    try:
        f01s = [float(x) for x in raw if str(x).strip()]
    except (TypeError, ValueError):
        return {"ok": False, "error": "f01s 须为逗号分隔的 qubit 频率(GHz)列表"}
    kw = {}
    for k in ("delta", "g"):
        if payload.get(k) is not None:
            try:
                kw[k] = float(payload[k])
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为数值"}
    for k in ("T1_us", "nbar"):
        raw_l = payload.get(k)
        if raw_l is not None:
            if isinstance(raw_l, str):
                raw_l = raw_l.split(",")
            try:
                kw[k + "_list"] = [float(x) for x in raw_l if str(x).strip()]
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为逗号分隔数值列表"}
    try:
        rep = design_multiqubit_fidelity(f01s, **kw)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_mixed_system(payload=None):
    """D-52 多环 WDM × 量子读出混合巨型系统（webui ㉔ 面板）。

    输入 {wdm_channels?, f01s?, gap?, T1_us?}：光子 WDM 分波（D-42）×
    量子读出（D-51）同一网表——信道↔qubit 1:1 映射 + 联合验收。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.mixed_system import design_mixed_system
    payload = payload or {}

    def _num_list(v, name):
        if isinstance(v, str):
            v = v.split(",")
        try:
            return [float(x) for x in v if str(x).strip()]
        except (TypeError, ValueError):
            return None
    ch = _num_list(payload.get("wdm_channels", "1550,1553,1556"),
                   "wdm_channels")
    f01s = _num_list(payload.get("f01s", "4.8,5.0,5.2"), "f01s")
    if ch is None or f01s is None:
        return {"ok": False, "error": "wdm_channels / f01s 须为逗号分隔数值列表"}
    kw = {}
    try:
        kw["wdm_gap_um"] = float(payload.get("gap", 0.3))
    except (TypeError, ValueError):
        return {"ok": False, "error": "gap 须为数值"}
    t1 = payload.get("T1_us")
    if t1 is not None:
        t1l = _num_list(t1, "T1_us")
        if t1l is None:
            return {"ok": False, "error": "T1_us 须为逗号分隔数值列表"}
        kw["T1_us_list"] = t1l
    try:
        rep = design_mixed_system(ch, f01s, **kw)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_coupler_design(payload=None):
    """D-55 方向耦合器设计闭环（webui ㉕ 面板）。

    输入 {target_cross?, gap?, w?}：目标分束比 → 2D FDTD 双点标定 κ →
    CMT 反解耦合长度（物理长度=有效长度+offset）→ 实测-修正迭代 →
    死标量验收。秒级-数十秒（2D FDTD 真实求解器）。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.directional_coupler import design_coupler
    payload = payload or {}
    kw = {}
    for k in ("target_cross", "gap", "w"):
        if payload.get(k) is not None:
            try:
                kw[k] = float(payload[k])
            except (TypeError, ValueError):
                return {"ok": False, "error": f"{k} 须为数值"}
    try:
        rep = design_coupler(transient_cycles=600, **kw)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_wdm_coupler(payload=None):
    """D-57 耦合器×WDM 组合（webui ㉖ 面板）。

    输入 {channels?, gap_scan?}：FDTD 标定 κ_c(gap) PDK 文件驱动 WDM 环
    bus 耦合段 gap 选择 → WDM 系统验收 + 诚实偏差报告（秒级，标定文件
    为一次性后台 FDTD 实测产物）。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.wdm_coupler import design_wdm_with_coupler
    payload = payload or {}

    def _num_list(v, name):
        if isinstance(v, str):
            v = v.split(",")
        try:
            return [float(x) for x in v if str(x).strip()]
        except (TypeError, ValueError):
            return None
    ch = _num_list(payload.get("channels", "1550,1553,1556"), "channels")
    gs = _num_list(payload.get("gap_scan", "0.25,0.30,0.35"), "gap_scan")
    if ch is None or gs is None or len(ch) < 2 or not gs:
        return {"ok": False,
                "error": "channels(≥2) / gap_scan 须为逗号分隔数值列表"}
    wl = bool(payload.get("wavelength", False))
    grid = bool(payload.get("grid", False))
    try:
        rep = design_wdm_with_coupler(ch, gap_scan=gs,
                                      wavelength_calibrated=wl,
                                      grid_calibrated=grid)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_splitter_readout(payload=None):
    """D-63 方向耦合器×量子读出（webui ㉗ 面板）。

    输入 {f01s?, weights?}：光子二叉树级联 DC 分束网络（每级 D-55 真实
    FDTD 设计闭环）供电量子读出控制线——功率按 FDTD 实测分束比缩放 n̄ →
    每 qubit SNR/保真度预算 + 统一 IR 网表 + 联合验收。光↔微波拓扑同构、
    物理独立（诚实标注）。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.splitter_readout import design_splitter_readout
    payload = payload or {}

    def _num_list(v, name):
        if isinstance(v, str):
            v = v.split(",")
        try:
            return [float(x) for x in v if str(x).strip()]
        except (TypeError, ValueError):
            return None
    f01s = _num_list(payload.get("f01s", "4.8,5.0,5.2"), "f01s")
    ws = _num_list(payload.get("weights", ""), "weights")
    if f01s is None or len(f01s) < 1:
        return {"ok": False, "error": "f01s 须为逗号分隔数值列表"}
    try:
        rep = design_splitter_readout(
            f01s, weights=ws or None,
            nbar0=float(payload.get("nbar0", 30.0)),
            delta=float(payload.get("delta", 1.0)),
            g=float(payload.get("g", 0.10)),
            kappa_r=float(payload.get("kappa_r", 0.005)),
            T1_us=float(payload.get("T1_us", 25.0)),
            eta=float(payload.get("eta", 0.5)),
            N_amp=float(payload.get("N_amp", 1.0)),
            calibrated=bool(payload.get("calibrated", False)),
            grid=payload.get("grid"))
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_wdm_splitter(payload=None):
    """D-67 分束网络×WDM（webui ㉘ 面板）。

    输入 {channels?, calibrated?, grid?}：WDM 解复用（D-42/D-57 标定库驱动
    gap）→ 每信道 drop 口接 DC 分束树（D-63 复用，D-55 真实 FDTD 设计）
    → 每信道分束命中 + 统一 IR 网表（Ring×N + DC×M）+ 联合验收。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.wdm_splitter import design_wdm_splitter
    payload = payload or {}

    def _num_list(v, name):
        if isinstance(v, str):
            v = v.split(",")
        try:
            return [float(x) for x in v if str(x).strip()]
        except (TypeError, ValueError):
            return None
    ch = _num_list(payload.get("channels", "1550,1553,1556"), "channels")
    if ch is None or len(ch) < 2:
        return {"ok": False, "error": "channels(≥2) 须为逗号分隔数值列表"}
    try:
        rep = design_wdm_splitter(
            ch,
            calibrated=bool(payload.get("calibrated", False)),
            grid_calibrated=bool(payload.get("grid", False)))
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_design_package(payload=None):
    """D-44 统一设计包规范（webui ⑳ 面板）。

    输入 {kind, params?}：把 4 类设计结果（add_drop/quantum/wdm/readout_chain）
    统一为同一 DesignPackage schema（ir + design + verification + artifacts +
    honest_notes），机器可校验。kind 省略 → 构建全部。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_design.design_package import (build_all, build_package,
                                           validate_package)
    payload = payload or {}
    kind = payload.get("kind")
    try:
        if kind in (None, "", "all"):
            out = build_all()
            out["ok"] = True
            return out
        params = payload.get("params") or {}
        pkg = build_package(kind, params=params)
        errs = validate_package(pkg)
        pkg["schema_ok"] = not errs
        pkg["schema_errors"] = errs
        pkg["ok"] = True
        return pkg
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_drc_fix_demo(payload):
    """D-18/D-21/D-22 可制造性面板：agent 自动整改 + 跨厂工艺规则对比。

    输入器件 + 参数（默认给违规初值演示自动整改）+ foundry（选择工艺规则），
    返回：整改轨迹（violation 单调降）+ 整改后参数在 3 个光子 foundry 规则下
    的跨厂可制造性对比 + 版图 SVG。
    """
    from lda_agent.drc_fix_loop import DrcFixAgent
    from lda_l2.drc import drc_check_device, rules_from_pdk
    from lda_l2.pdk import get_default_registry

    kind = payload.get("kind", "RingResonator")
    params = {k: float(v) for k, v in (payload.get("params") or {}).items()}
    if not params:
        # 默认违规初值（演示 agent 自动整改）
        _defaults = {
            "RingResonator": {"R": 2.0, "wg_width": 0.3},
            "Waveguide": {"width": 0.2},
            "DirectionalCoupler": {"gap": 0.1, "width": 0.5},
            "SymmetricYBranch": {"width": 0.5, "split_angle": 45.0},
        }
        params = _defaults.get(kind, {})

    reg = get_default_registry()
    photon = [k for k in reg.list_pdks() if "量子" not in k]
    fk = payload.get("foundry") or photon[0]
    rules = rules_from_pdk(reg.get(fk))

    fix = DrcFixAgent(rules=rules).run(kind, params)
    # 跨厂对比：整改后参数在 3 个光子 foundry 规则下可制造性
    cross = {}
    for k in photon:
        r = drc_check_device(kind, fix["final_params"],
                             rules=rules_from_pdk(reg.get(k)))
        cross[k.split("::")[0]] = {"passed": r.passed,
                                   "violations": [c.brief() for c in r.violations()]}
    fix["cross_foundry"] = cross
    fix["foundry"] = fk
    return fix


def run_coupler_loop(payload):
    """D-01 多端口耦合器件验收锚（设计→仿真→验收 可视化）。

    方向耦合器（DC）：FDFD 超模法 ORACLE（κ、Lc）↔ FDTD 超模投影 κ_fdtd 交叉对拍；
    对称 Y 分支分束器（YB）：对称性定理 ORACLE（50/50）↔ FDTD 两臂能流功率平衡度。

    实时 FDTD 仅 torch CUDA 可跑（3D 大规模网格纯 numpy 在 CPU 上不可行/会挂起）；
    无 GPU 时诚实退回「ORACLE 真值演示」：仍展示物理定律锚的真实数值，标注
    “实时 FDTD 交叉对拍需在 GPU 演示机运行”。LLM 不进判决路径。
    """
    from lda_agent import coupler_loop as cl

    kind = payload.get("kind", "ybranch")
    if kind not in ("dc", "ybranch"):
        return {"error": "kind 必须是 dc 或 ybranch", "passed": False}
    gap = float(payload["gap"]) if payload.get("gap") is not None else None
    sep = float(payload["sep"]) if payload.get("sep") is not None else None

    use_torch = False
    try:
        import torch
        use_torch = bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        use_torch = False

    if use_torch:
        t = cl.CouplerTarget(kind=kind, backend="torch")
        if kind == "dc" and gap is not None:
            t.gap_um = gap
        if kind == "ybranch" and sep is not None:
            t.sep_um = sep
        out = cl.CouplerAgent().run(t)
        d = out.to_dict()
        d["mode"] = "live_fdtd"
        return d

    # ---- 无 GPU：ORACLE 真值演示（快速、不挂起、诚实标注）----
    if kind == "dc":
        w, h, nc, ncl, wl = 0.5, 0.22, 3.48, 1.44, 1.55
        g = gap if gap is not None else 0.3
        dl = wl / 24.0
        eps3, meta = cl.build_coupler_field_3d(
            w, h, g, nc, ncl, wl, dl=dl, clad_um=3.0, Lz_um=24.0)
        orc = cl.fdfd_coupler_supermodes(
            eps3[:, :, 0], meta["dl"], wl,
            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
        return {
            "kind": "dc", "mode": "oracle_only", "passed": None,
            "label": "DC Si 500x220 gap=%.2fµm（FDFD 超模法 ORACLE）" % g,
            "metrics": {
                "gap_um": g,
                "kappa_oracle": round(orc["kappa"], 5),
                "Lc_oracle_um": round(orc["Lc_um"], 2),
                "neff_s": round(orc["neff_s"], 4),
                "neff_a": round(orc["neff_a"], 4),
            },
            "note": "无 GPU：仅展示 FDFD 超模法 ORACLE 真值（κ、Lc）。"
                    "实时 FDTD 超模投影 κ_fdtd 交叉对拍需在 GPU 演示机运行。",
        }
    # ybranch
    s = sep if sep is not None else 1.6
    orc = cl.ybranch_oracle()
    return {
        "kind": "ybranch", "mode": "oracle_only", "passed": None,
        "label": "YB Si 对称分束器 1x2（sep=%.1fµm，对称性定理 ORACLE）" % s,
        "metrics": {
            "sep_um": s,
            "target_frac": orc["target_frac"],
            "balance_abs": 0.0,
        },
        "note": "对称性定理 ORACLE：P1=P2=0.5·P_in（精确 50/50）。"
                "实时 FDTD 两臂能流平衡度对拍需在 GPU 演示机运行。",
    }


def run_ir_demo(payload):
    """D-05 L0 统一 IR（v0.2）真实渲染：用已落地的 lda_ir 构造器件 IR，
    导出 DSL（机器优先中间表示）并跑静态校验，证明 IR 即设计事实源。

    不跑 GPU 逆设计（逆设计闭环见上方 band/coupler 接口）；此处只展示
    “同一套 IR 机器语言如何精确表达光子与量子器件”。
    """
    from lda_ir import (
        DirectionalCoupler, SymmetricYBranch, RingResonator, Transmon,
        Resonator, Coupler,
        IRModel, ObjectiveSpec, validate, to_dsl,
    )

    def build(kind_name, comp, bid):
        # 包一个最小 IRModel：器件 + 一个合法 objective（满足 IR 必须含设计意图）
        m = IRModel(components=[comp], nets=[],
                    objectives=[ObjectiveSpec(bid=bid, target=0.99)])
        try:
            dsl = to_dsl(m)
        except Exception as e:  # noqa: BLE001
            dsl = "(DSL 序列化失败: %s)" % e
        try:
            errs = validate(m)
        except Exception as e:  # noqa: BLE001
            errs = ["校验异常: %s" % e]
        return {
            "kind": kind_name,
            "dsl": dsl,
            "validate_errors": errs,
            "params": dict(comp.params),
        }

    examples = [
        build("DirectionalCoupler（方向耦合器·D-01 验收锚）",
              DirectionalCoupler(), "B2"),
        build("SymmetricYBranch（对称 Y 分支分束器·D-01 验收锚）",
              SymmetricYBranch(), "B2"),
        build("RingResonator（环形谐振器·多波长闭环主器件）",
              RingResonator(), "B11"),
        build("Transmon（超导量子比特·量子频率骨架）",
              Transmon(), "B9"),
        build("Resonator（超导谐振器 λ/4 · D-40 物理锚 B12）",
              Resonator(), "B12"),
        build("Coupler（双 transmon 电容耦合 · D-40 物理锚 B13）",
              Coupler(), "B13"),
    ]
    all_ok = all(len(e["validate_errors"]) == 0 for e in examples)
    return {
        "schema_version": IRModel().schema_version,
        "all_valid": all_ok,
        "examples": examples,
        "note": "上述 IR 由 lda_ir（D-05 v0.2 / D-40 v0.3）实时构造并校验；"
                "耦合器/分束器 IR 是 D-01 验收锚的事实源，环形 IR 是 D-03 多波长"
                "闭环的事实源，Transmon/Resonator/Coupler 量子 IR 带 PhysicsAnchor "
                "（B9/B12/B13）——同一 IR 表达两种物理。",
    }


def run_adjoint_design(payload=None):
    """D-69 伴随法拓扑逆设计（webui ㉙ 面板）。

    输入 {iters?, step?, beta?, nsamples?, Nx?, Ny?, dl_factor?, sponge?,
    y_mon0?, y_mon1?, di0?, di1?, dj0?, dj1?}：主权 2D adjoint FDTD 核
    （高斯脉冲源 + 窄孔径收集场能 FOM）→ 验证锚（adjoint vs 中心有限差分
    方向对拍 ≤0.15）→ 密度投影 + 回溯线搜索梯度拓扑逆设计
    （improvement ≥1.5）→ 死标量验收。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.adjoint_design import design_adjoint
    payload = payload or {}
    geo = {}
    for k in ("Nx", "Ny", "dl_factor", "sponge", "y_mon0", "y_mon1",
              "di0", "di1", "dj0", "dj1"):
        if k in payload and payload[k] not in (None, ""):
            geo[k] = int(float(payload[k]))
    try:
        rep = design_adjoint(
            iters=int(payload.get("iters", 50)),
            step0=float(payload.get("step", 0.5)),
            beta_max=float(payload.get("beta", 14.0)),
            nsamples=int(payload.get("nsamples", 8)),
            **geo)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_adjoint_loop(payload=None):
    """D-70 逆设计目标泛化接入 D-36 引擎（webui ㉚ 面板）。

    输入 {iters?, step?, beta?, nsamples?, delta?, Nx?, Ny?, dl_factor?,
    sponge?, di0?, di1?, dj0?, dj1?, y_mon0?, y_mon1?}：DesignAgent
    method="adjoint" 闭环 = 目标解析（extra 几何透传）→ 均匀平板初值 →
    FD 对拍锚（max_rel_err≤0.15）→ 密度投影 + 回溯线搜索梯度拓扑优化
    （improvement≥1.5）→ 死标量验收，输出 DesignOutcomeReport 兼容格式
    （target/accepted/iterations/loop_trace/verdict）。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.design_loop import DesignAgent
    payload = payload or {}
    extra = {}
    for k in ("Nx", "Ny", "dl_factor", "sponge", "di0", "di1", "dj0", "dj1",
              "y_mon0", "y_mon1", "i_src", "i_mon", "eps_min", "eps_max",
              "wl_um"):
        if k in payload and payload[k] not in (None, ""):
            try:
                v = float(payload[k])
                extra[k] = int(v) if k in (
                    "Nx", "Ny", "sponge", "di0", "di1", "dj0", "dj1",
                    "i_src", "i_mon") else v
            except (TypeError, ValueError):
                extra[k] = payload[k]
    intent = {
        "method": "adjoint",
        "geometry_type": payload.get("geometry_type", "adjoint_focuser"),
        "extra": {
            **extra,
            "iters": int(payload.get("iters", 50)),
            "step0": float(payload.get("step", 0.5)),
            "beta_max": float(payload.get("beta", 14.0)),
            "nsamples": int(payload.get("nsamples", 8)),
            "delta": float(payload.get("delta", 0.05)),
        },
    }
    try:
        rep = DesignAgent().run(intent)
        out = rep.to_dict()
        out["ok"] = True
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_primitives(payload=None):
    """D-71 真实版图基元库（webui ㉛ 面板）。

    输入 {Taper?: {w1,w2,length,profile}, EulerBend?: {width,R,theta_deg},
    MMI?: {width,W_mmi,L_mmi,L_tap,out_gap,L_out},
    GratingCoupler?: {width,Lambda,duty,n_tooth,L_in}}：四个基元 → GDS
    编码（round-trip 回读一致）+ DRC 可制造性自查（min_width/min_space/
    min_bend_R，典型 SOI 规则）+ SVG 预览。诚实边界：只交付 foundry 可接受
    的几何；电特性（分束比/透射谱）归 D-72 2D FDTD 端口 S 参数验收。
    LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.primitives_design import design_primitives
    payload = payload or {}
    overrides = {}
    for kind in ("Taper", "EulerBend", "MMI", "GratingCoupler"):
        ov = payload.get(kind) or {}
        if isinstance(ov, dict) and ov:
            clean = {}
            for k, v in ov.items():
                if v in (None, ""):
                    continue
                try:
                    clean[k] = float(v)
                except (TypeError, ValueError):
                    clean[k] = v          # 字符串参数（如 profile）
            if clean:
                overrides[kind] = clean
    try:
        rep = design_primitives(**overrides)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_sparams(payload=None):
    """D-72 端口 S 参数验收（webui ㉜ 面板）。

    输入 {width?, W_mmi?, L_mmi?, L_tap?, out_gap?, L_out?, wl0_um?,
    n_wl?, span_um?}：MMI 1×2 对称分束器全 2D FDTD 端口透反射谱——输入 CW
    激励 → 输出/回波端口 DFT 收集 → 输入功率归一 → S 参数（|S11|²/|S21|²/
    |S31|²）→ 死标量验收（仿真有效 + 平衡度≤0.15 + 透射≥0.05，自成像对称
    ORACLE）+ DRC 规则从真实 SOI 180nm PDK 注入。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.sparams_design import design_sparams
    payload = payload or {}
    mmi = {}
    for k in ("width", "W_mmi", "L_mmi", "L_tap", "out_gap", "L_out",
              "wl0_um", "n_wl", "span_um"):
        if k in payload and payload[k] not in (None, ""):
            mmi[k] = float(payload[k])
    try:
        rep = design_sparams(mmi=mmi or None)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_sparams_3d(payload=None):
    """D-72 深化 3D 端口 S 参数验收（webui ㉝ 面板）。

    输入 {kind? (mmi/dc/ring), width?, W_mmi?, L_mmi?, L_tap?, out_gap?,
    L_out?, gap?, Lc?, R?, wl0_um?, n_wl?, span_um?, h_si_um?}：器件全 3D
    FDTD 端口透反射谱（SOI 220nm，复用已验证 numba 3D 核）——3D 截面匹配
    源注入 → 多端口 DFT 收集 → 输入功率归一 → S 参数谱 → 死标量验收
    （mmi: 平衡度≤0.15；dc: cross_frac 端点趋势；ring: drop 谐振峰；均 +
    透射≥0.05）+ 2D↔3D 对拍诊断。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.sparams_3d_design import design_sparams_3d
    payload = payload or {}
    kind = str(payload.get("kind", "mmi")).lower()
    if kind not in ("mmi", "dc", "ring"):
        kind = "mmi"
    mmi = {}
    for k in ("width", "W_mmi", "L_mmi", "L_tap", "out_gap", "L_out",
              "gap", "Lc", "R", "wl0_um", "n_wl", "span_um", "h_si_um"):
        if k in payload and payload[k] not in (None, ""):
            mmi[k] = float(payload[k])
    try:
        rep = design_sparams_3d(mmi=mmi or None, kind=kind)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_gc_sparams(payload=None):
    """D-78 光栅耦合器端口验收（webui ㉞ 面板）。

    输入 {width?, Lambda?, duty?, n_tooth?, n_wl?}：GC 2D FDTD 透射谱 +
    光栅方程 ORACLE 验收（谷检出 / 谷位置 vs λ_rad=Λ·n_eff 对拍 / Λ 扫描
    趋势锚 dλ/dΛ=neff_gc）。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.gc_design import design_gc
    payload = payload or {}
    gc = {}
    for k in ("width", "Lambda", "duty", "n_tooth", "L_in", "L_out",
              "wl0_um", "n_wl"):
        if k in payload and payload[k] not in (None, ""):
            gc[k] = float(payload[k])
    try:
        rep = design_gc(gc or None)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_pipeline_realize(payload=None):
    """D-79 真实基元接入设计流水线（webui ㉟ 面板）。

    输入 {kinds? (list)}：全 kind 真实 GDS 出图 + 3×SOI PDK DRC 复查 +
    玩具→真实几何对比诊断。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.pipeline_realize import design_pipeline_realize
    payload = payload or {}
    kinds = payload.get("kinds") or None
    try:
        rep = design_pipeline_realize(devices=kinds)
        rep["ok"] = True
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_tunable_wdm(payload=None):
    """D-73 热光可调 WDM（webui ㊱ 面板）。

    输入 {channels? (csv), target? (csv), R_th?, n_eff?, P_max?}：静态 WDM
    （D-42/D-57）+ 每环热光调谐（Δλ/λ=(dn/dT)·R_th·P/n_eff 物理定律锚）+
    信道重分配验收（|P|≤P_max 且 |Δλ|≤FSR/2 无混叠）。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.tunable_wdm import design_tunable_wdm
    payload = payload or {}
    ch = payload.get("channels")
    channels = ([float(x) for x in str(ch).split(",") if x.strip()]
                if ch else None)
    tgt = payload.get("target")
    target = ([float(x) for x in str(tgt).split(",") if x.strip()]
              if tgt else None)
    kw = {}
    for k in ("R_th", "n_eff", "P_max"):
        if payload.get(k) not in (None, ""):
            kw[k] = float(payload[k])
    try:
        rep = design_tunable_wdm(channels_nm=channels,
                                 target_channels_nm=target, **kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_qeda_topology(payload=None):
    """D-74 量子门/纠错拓扑（webui ㊲ 面板）。

    输入 {d?, p_phys?, J?, delta?, alpha?, T2?, target?}：量子门库（幺正性+通用性
    死标量锚）+ rotated surface code（全对易+k=1+阈值标度）+ cross-resonance 门
    （有效模型+退相干预算）组合为容错拓扑 spec 并死标量验收。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.qeda_topology import design_qeda_topology
    payload = payload or {}
    kw = {}
    for k in ("d", "p_phys", "J", "delta", "alpha", "T2_us", "target"):
        if payload.get(k) not in (None, ""):
            kw[k] = float(payload[k]) if k != "d" else int(payload[k])
    try:
        rep = design_qeda_topology(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_large_scale_bench(payload=None):
    """D-75 大规模系统基准（webui ㊳ 面板）。

    输入 {n_wdm?, n_qubit?, wdm_spacing?, wdm_gap?, qubit_spacing?}：
    WDM N≥8 信道 + N≥8 qubit 联合压测 + 性能/精度边界扫描
    （容量自洽 / IL 级联余量 / qubit 间隔临界 / 标定网格分辨率）。
    LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.large_scale_bench import run_large_scale_bench as _run
    payload = payload or {}
    kw = {}
    for k, cast in (("n_wdm", int), ("n_qubit", int),
                    ("wdm_spacing", float), ("wdm_gap", float),
                    ("qubit_spacing", float)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    try:
        rep = _run(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_ir_spec(payload=None):
    """D-76 L0 IR 开放标准零漂移校验（webui ㊴ 面板）。

    校验 docs/ir_spec.md + docs/ir_schema.json 与 lda_ir 代码三方零漂移：
    kind 注册表 9 kind / JSON Schema draft-07 合法 / 全 kind conforms /
    0.2 向后兼容 / physics 物理锚 round-trip（D-76 修复）。LLM 不进判决。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_ir.spec_check import run_ir_spec_check
    try:
        rep = run_ir_spec_check()
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


# WebUI 回归演示子集（~15s，避免全量 6min 阻塞）
_WEBUI_SUBSET = [
    "run_harness.py", "run_ir_smoke.py", "run_ir_quantum_smoke.py",
    "run_gds_smoke.py", "run_drc_smoke.py", "run_device_library_smoke.py",
    "run_tunable_wdm_smoke.py", "run_qeda_topology_smoke.py",
    "run_large_scale_smoke.py",
]


def run_ci_regression(payload=None):
    """D-77 验证合约工业化回归（webui ㊵ 面板）。

    输入 {tag?: "webui"|"core"|"all", timeout?}：统一入口跑 smoke 回归
    （webui=快速子集 ~15s；core=CI 安全集 ~6min；all=全量含重 FDTD/GPU）。
    LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    payload = payload or {}
    tag = payload.get("tag", "webui")
    timeout = float(payload.get("timeout") or 120.0)
    from run_ci_regression import run_ci_regression as _run
    if tag == "webui":
        # 只跑内置演示子集（逐项 subprocess）
        import subprocess as _sp, time as _t
        results = []
        for script in _WEBUI_SUBSET:
            t0 = _t.perf_counter()
            try:
                p = _sp.run([_sys.executable, script], cwd=_lda,
                            capture_output=True, text=True, timeout=timeout)
                rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
                st = "PASS" if rc == 0 else "FAIL"
                if rc != 0 and any(m in out for m in
                                   ("SKIP", "无 GPU", "未安装", "SKIPPED")):
                    st = "SKIP"
                results.append({"script": script, "rc": rc, "status": st,
                                "elapsed_s": round(_t.perf_counter() - t0, 2),
                                "tail": "\n".join(out.splitlines()[-2:])})
            except Exception as e:  # noqa: BLE001
                results.append({"script": script, "rc": -1, "status": "ERROR",
                                "elapsed_s": round(_t.perf_counter() - t0, 2),
                                "tail": str(e)[:100]})
        n_pass = sum(1 for r in results if r["status"] == "PASS")
        n_skip = sum(1 for r in results if r["status"] == "SKIP")
        n_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
        passed = n_fail == 0
        return {"ok": True, "tag": tag, "results": results,
                "summary": {"pass": n_pass, "skip": n_skip, "fail": n_fail,
                            "total_s": round(sum(r["elapsed_s"] for r in results), 2)},
                "acceptance": {"passed": passed,
                               "checks": [{"name": "WebUI 回归子集",
                                           "ok": passed,
                                           "detail": f"{n_pass} PASS / "
                                                     f"{n_skip} SKIP / {n_fail} FAIL"}]},
                "verdict": (f"WebUI 回归子集 {n_pass} PASS / {n_skip} SKIP / "
                            f"{n_fail} FAIL"
                            + (" —— 全绿" if passed else " —— 有失败"))}
    try:
        rep = _run(tag=tag if tag in ("core", "all") else "core",
                   timeout=timeout)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_perf_bench(payload=None):
    """D-77 性能基准（webui ㊵ 面板 · quick 模式 ~80s）。

    输入 {quick?}：greens numpy→numba 加速比 + 物理一致 + GPU（CUDA 可用时）
    bit-equivalent + 历史基线漂移监控。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from run_perf_bench import run_perf_bench as _run
    payload = payload or {}
    quick = payload.get("quick") not in (None, "", False)
    try:
        rep = _run(compare_baseline=True, quick=quick)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_spectral_design(payload=None):
    """D-80 谱形目标逆设计（webui ㊶ 面板）。

    输入 {target_type?, target_ratio?, wavelengths?, Nx?, Ny?, iters?}：
    伴随梯度拓扑逆设计目标泛化——field_energy（收集场能）/ split_ratio
    （分束比）/ mode_match（模式匹配）/ spectrum（多波长谱形）。死标量验收：
    FD 对拍 ≤0.15 + improvement + 分束比命中。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.spectral_inverse_design import design_spectral
    payload = payload or {}
    kw = {}
    for k, cast in (("target_ratio", float), ("Nx", int), ("Ny", int),
                    ("iters", int), ("dl_factor", float),
                    ("nsamples", int), ("delta", float)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    ttype = payload.get("target_type") or "split_ratio"
    wls = payload.get("wavelengths")
    try:
        rep = design_spectral(target_type=ttype, wavelengths=wls, **kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_shape_design(payload=None):
    """D-81 形状逆设计 + 多目标联合（webui ㊷ 面板）。

    输入 {mode?: shape|multi, wavelengths?, n_controls?, iters?}：
    shape=宽度曲线形状逆设计（K 控制点 + 可制造性 DRC）；multi=多波长
    加权联合 + Pareto 前端。死标量验收：形状梯度 FD 对拍 + improvement +
    DRC。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.multi_objective_design import (design_shape,
                                                  design_multi_objective)
    payload = payload or {}
    kw = {}
    for k, cast in (("n_controls", int), ("iters", int), ("Nx", int),
                    ("Ny", int)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    mode = payload.get("mode") or "shape"
    try:
        if mode == "multi":
            rep = design_multi_objective(
                wavelengths=payload.get("wavelengths"), **kw)
        else:
            rep = design_shape(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_hybrid_design(payload=None):
    """D-82 形状+拓扑混合逆设计（webui ㊸ 面板）。

    输入 {n_controls?, iters?, topo_band?}：形状主干（宽度曲线）+ 拓扑
    微调带联合优化 + 纯形状基线对比。死标量验收：混合梯度 FD 对拍 +
    improvement + 混合≥纯形状 + DRC。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.hybrid_design import design_hybrid
    payload = payload or {}
    kw = {}
    for k, cast in (("n_controls", int), ("iters", int), ("Nx", int),
                    ("Ny", int)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    if payload.get("topo_band"):
        kw["topo_band"] = str(payload["topo_band"])
    try:
        rep = design_hybrid(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_hybrid_multi(payload=None):
    """D-83 混合参数化 × 多波长加权联合（webui ㊹ 面板）。

    输入 {wavelengths?, n_controls?, iters?, pareto?}：形状主干 + 拓扑
    微调带 × 多波长谱形目标加权联合 + 纯形状多波长基线对比 + Pareto 前端。
    死标量验收：联合梯度 FD 对拍 + 加权 improvement + 各波长 ≥1.2 +
    混合≥纯形状 + DRC。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.hybrid_design import design_hybrid_multi
    payload = payload or {}
    kw = {}
    for k, cast in (("n_controls", int), ("iters", int), ("Nx", int),
                    ("Ny", int)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    if payload.get("wavelengths"):
        kw["wavelengths"] = str(payload["wavelengths"])
    if payload.get("topo_band"):
        kw["topo_band"] = str(payload["topo_band"])
    if payload.get("pareto") is not None:
        kw["pareto"] = bool(payload["pareto"])
    try:
        rep = design_hybrid_multi(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_adjoint3d(payload=None):
    """D-84/85/87 3D adjoint 形状逆设计（webui ㊺/㊻/㊽ 面板）。

    输入 {mode?: shape|section|spectral, Nx?, Ny?, Nz?, n_controls?, iters?}：
    shape=宽度曲线平板（D-84），section=宽度×厚度截面（D-85），
    spectral=截面 × 多波长加权联合（D-87）。
    死标量验收：3D adjoint FD 对拍 + 形状梯度链式对拍 + improvement + DRC。
    LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.adjoint3d_design import (design_shape3d, design_section3d,
                                            design_spectral3d)
    payload = payload or {}
    kw = {}
    for k, cast in (("Nx", int), ("Ny", int), ("Nz", int),
                    ("n_controls", int), ("iters", int)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    mode = payload.get("mode", "shape")
    if payload.get("wavelengths") and mode == "spectral":
        kw["wavelengths_um"] = [float(x) for x in payload["wavelengths"]]
    try:
        if mode == "section":
            rep = design_section3d(**kw)
        elif mode == "spectral":
            rep = design_spectral3d(**kw)
        else:
            rep = design_shape3d(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_port_acceptance(payload=None):
    """D-86 3D 逆设计 × 3D 端口 S 参数联合验收（webui ㊼ 面板）。

    输入 {Nx?, Ny?, Nz?, n_controls?, iters?, w_min?, init_w?}：3D adjoint
    场能优化设计 → 独立 3D CW 端口核测量 S11/S21 → 双独立确认验收
    （FOM imp ≥1.5 且 S21 imp ≥1.5）。LLM 不进判决路径。
    """
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    if str(_lda) not in _sys.path:
        _sys.path.insert(0, str(_lda))
    from lda_agent.port_acceptance import design_port_acceptance
    payload = payload or {}
    kw = {}
    for k, cast in (("Nx", int), ("Ny", int), ("Nz", int),
                    ("n_controls", int), ("iters", int)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    for k, cast in (("w_min", float), ("init_w", float)):
        if payload.get(k) not in (None, ""):
            kw[k] = cast(payload[k])
    try:
        rep = design_port_acceptance(**kw)
        rep["ok"] = bool(rep.get("ok"))
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def run_adjoint3d_perf(payload=None):
    """D-89 3D adjoint numba 性能基准（webui ㊾ 面板）。

    输入 {}：测量 44/64/80 三域 forward/梯度加速比 + FOM bit-level 一致性 +
    优化链路加速。死标量验收：最大域 forward ≥20× 且 FOM rel ≤1e-10。
    无 numba 环境自动跳过加速测量（回退本身即验收项）。
    """
    import subprocess as _sp
    import sys as _sys
    from pathlib import Path as _P
    _lda = _P(__file__).resolve().parent.parent  # lda/
    _py = _sys.executable
    try:
        r = _sp.run([_py, str(_P(_lda) / "run_perf_adjoint3d.py")],
                    capture_output=True, text=True, timeout=240)
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout)[-200:]}
        import json as _json
        rep = _json.loads(
            _P(_lda / "reports" / "perf_adjoint3d_d89.json").read_text(
                encoding="utf-8"))
        rep["ok"] = bool(rep["acceptance"]["passed"])
        rep["stdout"] = r.stdout[-500:]
        return rep
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


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
        "pdks_registered": len(get_default_registry().list_pdks()),
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
            elif path == "/api/band_loop":
                self._send(200, run_band_loop(payload))
            elif path == "/api/ring_loop":
                self._send(200, run_ring_loop(payload))
            elif path == "/api/ring_fdtd":
                self._send(200, run_ring_fdtd_demo(payload))
            elif path == "/api/device_library":
                self._send(200, run_device_library_demo(payload))
            elif path == "/api/dc_transmission":
                self._send(200, run_dc_transmission_demo(payload))
            elif path == "/api/layout_pipeline":
                self._send(200, run_layout_pipeline(payload))
            elif path == "/api/design_pipeline":
                self._send(200, run_design_pipeline(payload))
            elif path == "/api/design_loop":
                self._send(200, run_design_loop(payload))
            elif path == "/api/ring_package":
                self._send(200, run_ring_package(payload))
            elif path == "/api/inverse_design":
                self._send(200, run_inverse_design_demo(payload))
            elif path == "/api/quantum_design":
                self._send(200, run_quantum_design(payload))
            elif path == "/api/wdm_design":
                self._send(200, run_wdm_design(payload))
            elif path == "/api/readout_chain":
                self._send(200, run_readout_chain(payload))
            elif path == "/api/multiqubit_readout":
                self._send(200, run_multiqubit_readout(payload))
            elif path == "/api/readout_fidelity":
                self._send(200, run_readout_fidelity(payload))
            elif path == "/api/multiqubit_fidelity":
                self._send(200, run_multiqubit_fidelity(payload))
            elif path == "/api/mixed_system":
                self._send(200, run_mixed_system(payload))
            elif path == "/api/coupler_design":
                self._send(200, run_coupler_design(payload))
            elif path == "/api/wdm_coupler":
                self._send(200, run_wdm_coupler(payload))
            elif path == "/api/splitter_readout":
                self._send(200, run_splitter_readout(payload))
            elif path == "/api/wdm_splitter":
                self._send(200, run_wdm_splitter(payload))
            elif path == "/api/design_package":
                self._send(200, run_design_package(payload))
            elif path == "/api/drc_fix_demo":
                self._send(200, run_drc_fix_demo(payload))
            elif path == "/api/coupler_loop":
                self._send(200, run_coupler_loop(payload))
            elif path == "/api/ir_demo":
                self._send(200, run_ir_demo(payload))
            elif path == "/api/adjoint_design":
                self._send(200, run_adjoint_design(payload))
            elif path == "/api/adjoint_loop":
                self._send(200, run_adjoint_loop(payload))
            elif path == "/api/primitives":
                self._send(200, run_primitives(payload))
            elif path == "/api/sparams":
                self._send(200, run_sparams(payload))
            elif path == "/api/sparams_3d":
                self._send(200, run_sparams_3d(payload))
            elif path == "/api/gc_sparams":
                self._send(200, run_gc_sparams(payload))
            elif path == "/api/pipeline_realize":
                self._send(200, run_pipeline_realize(payload))
            elif path == "/api/tunable_wdm":
                self._send(200, run_tunable_wdm(payload))
            elif path == "/api/qeda_topology":
                self._send(200, run_qeda_topology(payload))
            elif path == "/api/large_scale_bench":
                self._send(200, run_large_scale_bench(payload))
            elif path == "/api/ir_spec":
                self._send(200, run_ir_spec(payload))
            elif path == "/api/ci_regression":
                self._send(200, run_ci_regression(payload))
            elif path == "/api/perf_bench":
                self._send(200, run_perf_bench(payload))
            elif path == "/api/spectral_design":
                self._send(200, run_spectral_design(payload))
            elif path == "/api/shape_design":
                self._send(200, run_shape_design(payload))
            elif path == "/api/hybrid_design":
                self._send(200, run_hybrid_design(payload))
            elif path == "/api/hybrid_multi":
                self._send(200, run_hybrid_multi(payload))
            elif path == "/api/adjoint3d":
                self._send(200, run_adjoint3d(payload))
            elif path == "/api/port_acceptance":
                self._send(200, run_port_acceptance(payload))
            elif path == "/api/adjoint3d_perf":
                self._send(200, run_adjoint3d_perf(payload))
            elif path == "/api/pdk_design":
                self._send(501, {"error": "not_implemented",
                                 "message": "PDK 驱动逆设计依赖 DesignProblem 抽象层，规划于 D-09；"
                                            "当前可用：/api/verify、/api/agent_loop、/api/band_loop、"
                                            "/api/coupler_loop、/api/ir_demo。"})
            elif path == "/api/pdk_compare":
                self._send(501, {"error": "not_implemented",
                                 "message": "PDK 跨厂对比依赖 DesignProblem 抽象层，规划于 D-09；"
                                            "当前可用：上方已落地的闭环接口。"})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})

    def log_message(self, *a):
        pass


def _local_ips() -> list:
    """本机内网 IPv4 地址（供访问提示）。"""
    import socket
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:  # noqa: BLE001
        pass
    return ips or ["127.0.0.1"]


def main():
    port = int(os.environ.get("LDA_WEBUI_PORT", "8787"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("=" * 58, flush=True)
    print("LDA WebUI 内网演示服务已启动", flush=True)
    for ip in _local_ips():
        print("  内网访问  http://%s:%d   演示机本机  http://127.0.0.1:%d"
              % (ip, port, port), flush=True)
    print("  健康检查  GET /api/status", flush=True)
    print("  停止服务  python lda_webui/deploy.py stop（或 Ctrl+C）", flush=True)
    print("=" * 58, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
