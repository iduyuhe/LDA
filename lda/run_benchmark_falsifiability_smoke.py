"""锚题可证伪性 smoke（v0.9.14 · P0-1 · 战略审计 R1 第一刀）。

背景（2026-09-02 战略审计实测）：48 锚实跑 48 PASS，其中 **47 道是自证桩**
——candidate 走 `_harness_reference_candidate`（直接返回 golden），
|cand−golden| ≡ 0 恒 PASS、零验证价值。全绿不等于可证伪。

本 smoke 是**反自证桩的常驻护栏**，判三件事：

  ① 独立性普查：48 锚中有多少道真走独立候选（|cand−golden| > 0）
  ② 正向：独立候选锚必须在各自 tol 内 PASS（证明求解器没坏）
  ③ 反向（关键）：注入参数扰动 ⇒ **必须 FAIL**
     —— 证明 tol 没有放水到"什么都抓不住"，护栏真能抓错

为什么③比②重要：②只能证明"没坏"，③才能证明"坏了能发现"。
只做②不做③，等于把「放宽容差」变成「取消验证」——这正是自证桩的翻版。

⚠️ 诚实边界（实测发现，2026-09-02）：
  B26 在 g 扰动 +1% 处 diff=1.68e-6，反而**小于**未扰动时的 4.57e-5
  ——参数扰动与（闭式↔数值）近似误差发生**偶然抵消**。这是物理上的正常
  现象，但意味着**小幅系统误差存在检测盲点**。故反向测试采用 10% 扰动
  （该档位 4 道全 FAIL，稳健），并额外登记「最小可检出扰动」作为灵敏度
  指标，把验证强度显式化，而不是藏在一句"PASS"后面。

运行：python run_benchmark_falsifiability_smoke.py
出口：全部 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
from lda_harness.verification_adapters import (
    build_harness_specs, BENCHMARK_CANDIDATES,
)
from lda_harness.verification_spec import VerificationSpec, run_verification

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


# 独立候选锚题的**反向测试配置**：(锚题, 扰动参数, 扰动方式)
# 扰动幅度：10%（实测该档位 4 道全部 FAIL，稳健；更小幅度存在抵消盲点）
PERTURB_SPEC = [
    ("B9", "E_J", "mul"),
    ("B25", "phi_frac", "add"),
    ("B26", "g_ghz", "mul"),
    ("B27", "g_ghz", "mul"),
]
PERTURB_REL = 0.10          # 反向测试扰动幅度（10%）
SENSITIVITY_GRID = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20)
SENSITIVITY_MAX = 0.10      # 灵敏度上界断言：10% 扰动必须可检出

# 独立候选数下限（随 P0-1 推进递增：v0.9.14 起步 = 4）
MIN_INDEPENDENT = 4


def _clone_with(sp: VerificationSpec, key: str, value: float) -> VerificationSpec:
    """克隆 spec 并替换单个参数（oracle 仍取原 golden，模拟「求解器算错」）。"""
    p2 = dict(sp.params)
    p2[key] = value
    return VerificationSpec(
        spec_id=sp.spec_id, metric=sp.metric, oracle_kind=sp.oracle_kind,
        oracle_fn=sp.oracle_fn, compare_fn=sp.compare_fn, tol=sp.tol,
        tol_mode=sp.tol_mode, target_desc=sp.target_desc, params=p2,
        source=sp.source, candidate_desc=sp.candidate_desc,
    )


def _perturb(base: float, rel: float, mode: str) -> float:
    """扰动取值：非零参数按比例（mul），零值参数用加法（add，避免乘 0 无效）。"""
    return base * (1.0 + rel) if mode == "mul" else base + rel


def main() -> int:
    print("=" * 70)
    print("LDA 锚题可证伪性 smoke（反自证桩护栏）")
    print("=" * 70)

    specs, cand_map = build_harness_specs()
    by_id = {s.spec_id: s for s in specs}

    # ① 独立性普查：区分「真独立求解」与「自证桩」
    independent, stub = [], []
    for sp in specs:
        try:
            ov = sp.oracle_fn(sp.params)
            cv = cand_map[sp.spec_id](sp, ov)
            is_stub = (isinstance(cv, (int, float))
                       and isinstance(ov, (int, float))
                       and abs(cv - ov) < 1e-12)
        except Exception:
            is_stub = True
        (stub if is_stub else independent).append(sp.spec_id)

    # 独立候选中，**进死标量判决**的才算数：candidate_status="degraded_ordinal"
    # 的锚（如 E2，FDFD 直波导候选 vs 环器件 golden 几何不同源）仅作量级参考，
    # 不计入独立强度——避免用一个已降级的锚充数（诚实边界 C，R16 证伪）。
    degraded = [b for b in independent
                if BENCHMARK_DEFS.get(b, {}).get("candidate_status")
                == "degraded_ordinal"]
    strict = [b for b in independent if b not in degraded]
    n_ind = len(strict)

    check(f"进判决的独立候选锚题数 ≥ {MIN_INDEPENDENT}（脱离自证桩）",
          n_ind >= MIN_INDEPENDENT,
          f"严格独立={n_ind} {sorted(strict)} · 降级量级参考={degraded} "
          f"· 自证桩={len(stub)}/{len(specs)}")

    check("已登记候选类型与实测独立锚一致（无登记未接线）",
          set(BENCHMARK_CANDIDATES) <= {
              d.get("candidate") for d in BENCHMARK_DEFS.values()
              if d.get("candidate")},
          f"登记表={sorted(BENCHMARK_CANDIDATES)}")

    # ② 正向：独立候选锚必须在各自 tol 内 PASS（只查进判决的严格独立锚）
    ok_pos, detail_pos = [], []
    for bid in strict:
        sp, ov = by_id[bid], None
        try:
            ov = sp.oracle_fn(sp.params)
            cv = cand_map[bid](sp, ov)
            out = run_verification(sp, cand_map[bid], oracle_value=ov)
            rel = abs(cv - ov) / abs(ov) * 100 if ov else 0.0
            ok_pos.append(out.passed)
            detail_pos.append(f"{bid}:{rel:.3f}%")
        except Exception as e:
            ok_pos.append(False)
            detail_pos.append(f"{bid}:ERR {str(e)[:30]}")
    check("独立候选锚正向全部 PASS（求解器未坏）",
          all(ok_pos) and len(ok_pos) > 0, " ".join(detail_pos))

    # ③ 反向（核心）：10% 参数扰动 ⇒ 必须 FAIL
    ok_neg, detail_neg = [], []
    for bid, key, mode in PERTURB_SPEC:
        if bid not in by_id:
            ok_neg.append(False)
            detail_neg.append(f"{bid}:缺失")
            continue
        sp = by_id[bid]
        try:
            ov = sp.oracle_fn(sp.params)
            base = float(sp.params[key])
            sp2 = _clone_with(sp, key, _perturb(base, PERTURB_REL, mode))
            cv = cand_map[bid](sp2, ov)
            out = run_verification(sp2, cand_map[bid], oracle_value=ov)
            caught = (not out.passed)
            ok_neg.append(caught)
            detail_neg.append(f"{bid}@{key}{PERTURB_REL:+.0%}:"
                              f"{'FAIL✅' if caught else 'PASS❌'}"
                              f"(d={abs(cv - ov):.3e}/tol={sp.tol:.3g})")
        except Exception as e:
            ok_neg.append(False)
            detail_neg.append(f"{bid}:ERR {str(e)[:30]}")
    check(f"反向测试：{PERTURB_REL:.0%} 参数扰动必被抓（tol 未放水）",
          all(ok_neg) and len(ok_neg) > 0, " ".join(detail_neg))

    # ④ 灵敏度登记：最小可检出扰动（把验证强度显式化）
    sens_rows = []
    for bid, key, mode in PERTURB_SPEC:
        if bid not in by_id:
            continue
        sp = by_id[bid]
        min_detectable = None
        for rel in SENSITIVITY_GRID:
            try:
                ov = sp.oracle_fn(sp.params)
                sp2 = _clone_with(sp, key, _perturb(float(sp.params[key]), rel, mode))
                out = run_verification(sp2, cand_map[bid], oracle_value=ov)
                if not out.passed:
                    min_detectable = rel
                    break
            except Exception:
                continue
        sens_rows.append((bid, key, min_detectable))
        print(f"      灵敏度 {bid}（扰动 {key}）："
              f"{'≤%.1f%%' % (min_detectable * 100) if min_detectable else '>20% 未检出'}")

    worst = max((r[2] for r in sens_rows if r[2] is not None), default=None)
    check(f"灵敏度上界：最小可检出扰动 ≤ {SENSITIVITY_MAX:.0%}",
          worst is not None and worst <= SENSITIVITY_MAX,
          f"最差={worst:.1%}" if worst else "无锚题可测")

    # ⑤ 无回归：全 48 锚仍全绿（独立化不得弄坏任何一道）
    n_pass = 0
    for sp in specs:
        try:
            ov = sp.oracle_fn(sp.params)
            if run_verification(sp, cand_map[sp.spec_id], oracle_value=ov).passed:
                n_pass += 1
        except Exception:
            pass
    check(f"全量 {len(specs)} 锚无回归（{BENCHMARK_ORDER[0]}–{BENCHMARK_ORDER[-1]}）",
          n_pass == len(specs) == len(BENCHMARK_DEFS),
          f"PASS={n_pass}/{len(specs)}")

    # ⑥ 诚实披露剩余自证桩（不构成失败，但必须可见）
    print()
    print(f"  [披露] 剩余自证桩 {len(stub)}/{len(specs)} 道"
          f"（candidate≡golden，恒 PASS、零验证价值）：")
    print(f"         {', '.join(stub)}")

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print(f"锚题可证伪性 smoke：{len(CHECKS) - n_fail}/{len(CHECKS)} PASS · "
          f"严格独立 {n_ind} 道 · 降级量级参考 {len(degraded)} 道 · "
          f"自证桩 {len(stub)}/{len(specs)} 道")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
