"""D-77 · 验证合约工业化 —— 求解器性能基准（numba-cpu / GPU 加速比监控）。

把 L2-B 求解核的性能做成**可监控的基准**（对齐 D-50 GPU 激活验收 + 既有
benchmark_fdtd3d）：同一规格下纯 numpy / numba-cpu / cuda(可用时) 计时，
输出加速比 + 物理一致性（bit-equivalence 铁律），并与历史基线
（reports/perf_baseline.json）对比，报告漂移（性能回归预警）。

基准项：
  ① 3D FDTD greens 球面波：numpy(N=48) vs numba-cpu(N=48) —— 加速比 +
     逐点 rel diff（物理一致铁律 ≤1e-2）；
  ② 3D FDTD 透射谱（3 case）：numpy vs numba —— 加速比 + rel diff；
  ③ GPU（torch.cuda 可用时）：cuda greens(N=48) 计时 + cuda↔cpu fp64
     bit-equivalent（≤1e-9，换设备不换物理）；
  ④ 历史基线：与 reports/perf_baseline.json 对比（首跑生成基线），
     numba 加速比漂移 ≥±30% 预警。

验收（死标量）：numpy↔numba rel diff ≤1e-2（物理一致）；numba 加速比 ≥5×
（D-50 实测 43× 的保守下限）；GPU bit-equivalent ≤1e-9（若可用）。
LLM 不进判决路径。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = _HERE          # 本脚本位于 lda/（包根）
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)
# fdtd3d_numba 内部 `from fdtd3d import ...` 需 lda_solver 目录在 path
_LDA_SOLVER = os.path.join(_HERE, "lda_solver")
if _LDA_SOLVER not in sys.path:
    sys.path.insert(0, _LDA_SOLVER)

_BASELINE = os.path.join(_LDA_ROOT, "reports", "perf_baseline.json")
_SPEEDUP_MIN = 5.0           # numba 加速比保守下限（D-50 实测 43×）
_REL_TOL = 1e-2              # numpy↔numba 物理一致（透射/场量级）
_BIT_EQ_TOL = 1e-9           # cuda↔cpu fp64 bit-equivalence
_DRIFT_WARN = 0.30           # 加速比漂移预警 ±30%


def _rel(a, b):
    import numpy as np
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = max(float(np.abs(b).max()), 1e-12)
    return float(np.max(np.abs(a - b) / denom))


def _timeit(fn, reps: int = 1) -> float:
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def bench_greens() -> Dict[str, Any]:
    """① 3D FDTD greens 球面波：numpy vs numba-cpu。"""
    from lda_solver import fdtd3d as npb
    from lda_solver import fdtd3d_numba as nb
    kwargs = dict(wl=2.0, n=1.0, N=48, sponge=12, dl_factor=20.0, ramp=300)
    # numpy 先跑（含首次 JIT 预热后）——numba 预热
    nb.run_greens_test_numba(**kwargs)          # warm-up JIT
    t_np = _timeit(lambda: npb.run_greens_test(**kwargs), reps=2)
    t_nb = _timeit(lambda: nb.run_greens_test_numba(**kwargs), reps=3)
    rn = npb.run_greens_test(**kwargs)
    rb = nb.run_greens_test_numba(**kwargs)
    an = [x[1] for x in rn]
    ab = [x[1] for x in rb]
    rel = _rel(an, ab)
    return {"case": "greens-N48", "numpy_s": round(t_np, 3),
            "numba_s": round(t_nb, 3),
            "speedup": round(t_np / t_nb, 2) if t_nb > 0 else None,
            "rel_diff": rel, "ok": rel <= _REL_TOL}


def bench_spectrum(quick: bool = False) -> Dict[str, Any]:
    """② 3D FDTD 透射谱：numpy vs numba-cpu（quick=只跑 1 case 提速验证）。"""
    from lda_solver import fdtd3d as npb
    from lda_solver import fdtd3d_numba as nb
    cases = {
        "matched": {"layers": [(float('inf'), 1.0), (float('inf'), 1.0)],
                    "wavelengths_um": [1.2, 1.5, 1.8]},
        "iface": {"layers": [(float('inf'), 1.0), (float('inf'), 1.5)],
                  "wavelengths_um": [1.2, 1.5, 1.8]},
        "fp": {"layers": [(float('inf'), 1.0), (2.0, 2.5), (float('inf'), 1.0)],
               "wavelengths_um": [1.4, 1.6, 1.8]},
    }
    if quick:
        cases = {"fp": cases["fp"]}
    kwargs = dict(dl_factor=80.0, sponge=160, ramp=300)
    nb.solve_spectrum_numba(list(cases.values())[0], **kwargs)  # warm-up
    rows: List[Dict[str, Any]] = []
    total_np = total_nb = 0.0
    for name, spec in cases.items():
        t_np = _timeit(lambda: npb.solve_spectrum(spec, **kwargs))
        t_nb = _timeit(lambda: nb.solve_spectrum_numba(spec, **kwargs), reps=2)
        rn = npb.solve_spectrum(spec, **kwargs)["transmission"]
        rb = nb.solve_spectrum_numba(spec, **kwargs)["transmission"]
        rel = _rel(rn, rb)
        total_np += t_np; total_nb += t_nb
        rows.append({"case": name, "numpy_s": round(t_np, 3),
                     "numba_s": round(t_nb, 3),
                     "speedup": round(t_np / t_nb, 2) if t_nb > 0 else None,
                     "rel_diff": rel, "ok": rel <= _REL_TOL})
    return {"cases": rows,
            "total_numpy_s": round(total_np, 3),
            "total_numba_s": round(total_nb, 3),
            "overall_speedup": round(total_np / total_nb, 2) if total_nb > 0 else None,
            "ok": all(r["ok"] for r in rows)}


def bench_gpu() -> Dict[str, Any]:
    """③ GPU（cuda 可用时）：greens 计时 + cuda↔cpu fp64 bit-equivalent。"""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"available": False,
                    "note": "CUDA 不可用（GPU 项 SKIP，非失败）"}
    except ImportError:
        return {"available": False, "note": "torch 未安装（GPU 项 SKIP）"}
    from lda_solver import fdtd3d as npb
    from lda_solver import fdtd3d_torch as torch_solver
    kwargs = dict(wl=2.0, n=1.0, N=48, sponge=12, dl_factor=20.0, ramp=300)
    # torch cuda 预热
    torch_solver.run_greens_test_torch(**kwargs, device="cuda")
    t_cuda = _timeit(
        lambda: torch_solver.run_greens_test_torch(**kwargs, device="cuda"),
        reps=2)
    t_cpu = _timeit(
        lambda: torch_solver.run_greens_test_torch(**kwargs, device="cpu"),
        reps=2)
    rc = torch_solver.run_greens_test_torch(**kwargs, device="cuda")
    rp = npb.run_greens_test(**kwargs)
    ac = [x[1] for x in rc]
    ap = [x[1] for x in rp]
    rel = _rel(ac, ap)
    return {"available": True,
            "device": torch.cuda.get_device_name(0),
            "cuda_s": round(t_cuda, 3), "cpu_torch_s": round(t_cpu, 3),
            "cuda_vs_cpu_speedup": round(t_cpu / t_cuda, 2) if t_cuda > 0 else None,
            "cuda_vs_numpy_rel": rel,
            "bit_equiv": rel <= _BIT_EQ_TOL,
            "ok": rel <= _BIT_EQ_TOL}


def run_perf_bench(compare_baseline: bool = True,
                   quick: bool = False) -> Dict[str, Any]:
    """性能基准主入口。返回 {benchmarks, baseline, acceptance, verdict}。"""
    g = bench_greens()
    s = bench_spectrum(quick=quick)
    gpu = bench_gpu()
    benchs = {"greens": g, "spectrum": s, "gpu": gpu}

    # ④ 历史基线对比
    prev = None
    drift = None
    if compare_baseline and os.path.exists(_BASELINE):
        with open(_BASELINE, encoding="utf-8") as f:
            prev = json.load(f)
        prev_speed = prev.get("greens", {}).get("speedup")
        cur_speed = g.get("speedup")
        if prev_speed and cur_speed:
            rel = (cur_speed - prev_speed) / prev_speed
            drift = {"metric": "greens numba speedup",
                     "prev": prev_speed, "now": cur_speed,
                     "rel_change": round(rel, 4),
                     "warn": abs(rel) > _DRIFT_WARN}

    checks: List[Dict[str, Any]] = [
        {"name": "numpy↔numba 物理一致（greens rel≤1e-2）",
         "ok": bool(g["ok"]), "detail": f"rel={g['rel_diff']:.2e}"},
        {"name": f"numba 加速比 ≥{_SPEEDUP_MIN}×（greens）",
         "ok": bool(g["speedup"] and g["speedup"] >= _SPEEDUP_MIN),
         "detail": f"{g['speedup']}×（numpy {g['numpy_s']}s → numba {g['numba_s']}s）"},
        {"name": "透射谱 3 case numpy↔numba 一致",
         "ok": bool(s["ok"]),
         "detail": f"overall speedup {s['overall_speedup']}×"
                   f"（{'/'.join(str(c['rel_diff']) for c in s['cases'])}）"},
    ]
    if gpu.get("available"):
        checks.append({"name": "GPU cuda↔cpu fp64 bit-equivalent（≤1e-9）",
                       "ok": bool(gpu["bit_equiv"]),
                       "detail": f"rel={gpu['cuda_vs_numpy_rel']:.2e}"
                                 f"（cuda {gpu['cuda_s']}s vs cpu {gpu['cpu_torch_s']}s）"})
    else:
        checks.append({"name": "GPU 基准（SKIP：CUDA 不可用）",
                       "ok": True, "detail": gpu["note"]})
    if drift:
        # 漂移监控为"预警信息"（黄灯），非硬判据——numpy 计时方差可达 ±40%，
        # 单次波动不代表性能回归；硬判据=物理一致+加速比下限+GPU bit-equiv。
        checks.append({"name": "性能漂移监控（greens numba 加速比）",
                       "ok": True,
                       "detail": (f"{drift['metric']} {drift['prev']}× → "
                                  f"{drift['now']}×（Δ{drift['rel_change'] * 100:.1f}%"
                                  + ("，⚠ 预警：偏离基线 >±30%，建议重跑确认"
                                     if drift["warn"] else "，基线内）"))})

    passed = all(c["ok"] for c in checks)
    verdict = (
        f"求解器性能基准 PASS：greens numpy→numba {g['speedup']}×（物理一致 "
        f"rel={g['rel_diff']:.1e}）；透射谱 overall {s['overall_speedup']}×；"
        + (f"GPU cuda↔cpu bit-equivalent rel={gpu['cuda_vs_numpy_rel']:.1e}；"
           if gpu.get("available") else "GPU SKIP（CUDA 不可用）；")
        + (f"基线对比 Δ{drift['rel_change'] * 100:.1f}%"
           if drift else "无历史基线（本跑生成基线）")
        + "。LLM 不进判决路径。"
        if passed else
        "性能基准未全过：" + "; ".join(c["name"] for c in checks if not c["ok"]))
    return {
        "ok": True,
        "title": "求解器性能基准（numba-cpu / GPU 加速比监控）",
        "benchmarks": benchs,
        "baseline": prev,
        "drift": drift,
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": verdict,
        "note": ("D-77 性能基准：同一规格 numpy/numba/cuda 计时 + 物理一致/"
                 "bit-equivalence 铁律 + 历史基线漂移监控（±30% 预警）。"
                 "诚实边界：消费卡 GPU fp64≈1/64（D-50），生产默认 numba-cpu；"
                 "本基准为求解核级性能，非端到端设计闭环。"),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-77 求解器性能基准")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--quick", action="store_true", help="spectrum 只跑 1 case 提速")
    a = ap.parse_args()
    r = run_perf_bench(compare_baseline=not a.no_baseline, quick=a.quick)
    print(json.dumps({k: r[k] for k in
                      ("title", "benchmarks", "drift", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:4000])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"[written] {a.out}")
    # 生成/更新基线（仅 PASS 时固化）
    if r["acceptance"]["passed"] and not a.no_baseline:
        bl = {"greens": {"speedup": r["benchmarks"]["greens"]["speedup"],
                         "numpy_s": r["benchmarks"]["greens"]["numpy_s"],
                         "numba_s": r["benchmarks"]["greens"]["numba_s"]},
              "spectrum": {"overall_speedup":
                           r["benchmarks"]["spectrum"]["overall_speedup"]},
              "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(_BASELINE, "w", encoding="utf-8") as f:
            json.dump(bl, f, ensure_ascii=False, indent=2)
        print(f"[baseline updated] {_BASELINE}")
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
