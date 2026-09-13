"""E10 微环 FSR 独立 n_g 闭式交叉验证护栏 smoke（v0.9.76 · U3 接线）。

守护五件事：
  ① harness 正向：E10 候选必须 PASS（独立 n_g 闭式 FSR 与实测 8.6nm 残差 ≪ tol）
  ② candidate 登记必须是 ring_fsr_independent_ng（防回退自证桩）+ candidate_status=degraded_ordinal（诚实降级）
  ③ 🔴 判据 D（C4 防火墙）：候选 FSR 必须≠由 8.6nm 反演的环形 n_g=4.18 算出的
     循环值（8.59nm）—— 证明 n_g 由求解器独立算出、非循环自证；且基线残差严格非零
     （cand 不是恒等 return golden 的自证桩）
  ④ 🔴 判据 D（几何可证伪）：候选对环长 L 必须响应 —— L=90µm 时 FSR 显著偏离基线，
     且判决翻转为 FAIL（|cand−gold|≫tol），证明候选是真计算、对器件几何敏感

运行：python run_e10_ring_fsr_smoke.py（~3s，纯 numpy/scipy）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    print("=" * 72)
    print("E10 微环 FSR 独立 n_g 闭式交叉验证护栏（ring_fsr_independent_ng）")
    print("=" * 72)

    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
    from lda_harness.verification_adapters import (
        build_harness_specs, BENCHMARK_CANDIDATES,
    )
    from lda_harness.verification_spec import run_verification

    # ------------------------------------------------ ② 登记防回退 + 诚实降级
    e10 = BENCHMARK_DEFS["E10"]
    check("E10 已登记进 BENCHMARK_DEFS", "E10" in BENCHMARK_DEFS)
    check("E10 已登记进 BENCHMARK_ORDER", "E10" in BENCHMARK_ORDER)
    check("candidate 登记 = ring_fsr_independent_ng",
          e10.get("candidate") == "ring_fsr_independent_ng",
          "实际=%s（防回退自证桩）" % e10.get("candidate"))
    check("candidate_status = degraded_ordinal（诚实降级，不进死标量判决列）",
          e10.get("candidate_status") == "degraded_ordinal",
          "实际=%s" % e10.get("candidate_status"))
    check("ring_fsr_independent_ng 已注册进 BENCHMARK_CANDIDATES",
          "ring_fsr_independent_ng" in BENCHMARK_CANDIDATES,
          "未注册=回退自证桩")

    # ------------------------------------------------ ① harness 正向
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == "E10"][0]
    fn = cand["E10"]
    ov = sp.oracle_fn(sp.params)          # 实测 8.6 nm（来自 seed_empirical.json，非硬编码）
    cv = fn(sp, ov)                       # 独立 n_g 闭式 FSR
    res = run_verification(sp, fn, oracle_value=ov)
    tol = float(sp.tol)
    check("E10 正向 PASS（独立 n_g 闭式 FSR 与实测残差 ≪ tol）",
          bool(res.passed),
          "cand=%.4f gold=%.4f 残差=%.4f tol=%s" % (cv, ov, abs(cv - ov), tol))
    # tol / golden 必须从 BENCHMARK_DEFS 派生，不得硬编码
    check("tol 取自 BENCHMARK_DEFS（=0.6）", abs(tol - 0.6) < 1e-9,
          "tol=%s" % tol)
    check("golden(实测) 取自语料（=8.6）", abs(ov - 8.6) < 1e-9,
          "gold=%.4f" % ov)

    # ------------------------------------------------ ③ 判据 D：C4 防火墙
    # 由 8.6nm 反演的环形 n_g=4.18 算出的循环值（须 ≠ 候选，否则即循环自证）
    seed = json.loads((HERE / "lda_harness" / "seed_empirical.json").read_text(encoding="utf-8"))
    ng_inv = next(e for e in seed["corpus"] if e["id"] == "E-RING-FSR")["geometry"]["n_g"]
    wl_nm = float(sp.params["wl_um"]) * 1000.0
    L_nm = float(sp.params["L_um"]) * 1000.0
    fsr_circular = wl_nm * wl_nm / (ng_inv * L_nm)   # ≈ 8.59 nm
    check("🔴 C4 防火墙：候选 FSR ≠ 由 8.6nm 反演的循环值（n_g=4.18→%.4f）"
          % fsr_circular,
          abs(cv - fsr_circular) > 1e-3,
          "cand=%.4f 循环值=%.4f 差=%.4f（证明 n_g 由求解器独立算出）"
          % (cv, fsr_circular, abs(cv - fsr_circular)))
    check("判据D：基线残差严格非零（候选非恒等 return golden 自证桩）",
          abs(cv - ov) > 1e-6, "残差=%.4f" % abs(cv - ov))

    # ------------------------------------------------ ④ 判据 D：几何可证伪
    p2 = dict(sp.params)
    p2["L_um"] = 90.0                      # 明显错误的环长（基线 66.8µm）

    class _S:                             # 最小 spec shim
        spec_id = "E10"
        params = p2

    cv2 = fn(_S(), ov)
    d2 = abs(cv2 - ov)
    check("判据D：候选对环长 L 响应（L:66.8→90µm 值明显移动）",
          abs(cv2 - cv) > 1e-3,
          "L=66.8→%.4f  L=90→%.4f" % (cv, cv2))
    check("🔴 反自证桩：L=90µm 时判决翻转 FAIL（|cand−gold|≫tol）",
          d2 > tol, "越界 %.4f ≫ tol %s" % (d2, tol))

    print("=" * 72)
    if FAIL:
        print(f"E10 环 FSR 护栏：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"E10 环 FSR 护栏：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
