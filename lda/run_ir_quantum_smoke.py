"""LDA L0 · 量子子集 IR smoke 测试（量子侧真值判定经 ir_eval，B9 物理锚）。

说明（诚实降级）：DesignProblem 抽象已随 webui 修复移除，当前 DesignAgent
仅支持光子真 2D 波导——量子 agent 逆设计闭环未接入（规划 D-09 /
BandDesignAgent 通用化后接入）。量子侧"IR 即事实源"经 ir_eval 走通：
同一量子 IR + 候选 E_J → B9 f01 真值与 PASS 判定（Koch2007 确定性物理锚，
LLM 不进判决路径）。
  1. 构造 Transmon IR：目标 f01=5.0GHz（B9 objective），调 E_J；
  2. validate 通过（量子域同走 IR 层验证门，与光子共用同一套 core）；
  3. to_dict → from_dict round-trip 零损失；to_dsl 可读渲染；
  4. ir_eval：命中目标 E_J → passed_all=True；失配 E_J → FAIL；
  5. 跨量子 foundry：E_C 工艺窗口注入 → 不同厂命中 f01 需不同 E_J 落点。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations

import sys

from lda_ir import (IRModel, ObjectiveSpec, Transmon, dumps, from_dict,
                    to_dict, to_dsl, validate)
from lda_ir.bridge import ir_eval
from lda_l2.pdk import get_default_registry


def build_transmon_ir() -> IRModel:
    """构造一个"transmon 频率逆设计"量子 IR：目标 f01=5.0GHz。"""
    m = IRModel(
        domain="quantum",
        name="transmon-f01-B9",
        components=[Transmon(id="q1", E_J=20.0,
                             EJ_bounds=(5.0, 40.0), EC_bounds=(0.1, 1.0))],
        objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1,
                                  role="objective")],
        notes="L0 IR 量子子集：transmon 频率逆设计（真值判定经 ir_eval/B9）",
    )
    return m


def main() -> int:
    print("=== L0 IR 量子子集 smoke (ir_eval / B9) ===")
    registry = get_default_registry()

    # 1) 构造 + 校验
    m = build_transmon_ir()
    errs = validate(m)
    if errs:
        print("FAIL IR 校验：")
        for e in errs:
            print("  -", e)
        return 1
    print("OK  IR 校验通过（量子域同走 IR 层验证门）")

    # 2) round-trip
    m2 = from_dict(to_dict(m))
    if dumps(m) != dumps(m2):
        print("FAIL round-trip 信息损失")
        return 1
    print("OK  to_dict→from_dict round-trip 零损失")

    # 3) 可读渲染
    print("--- to_dsl() ---")
    print(to_dsl(m))
    print("---------------")

    # 4) ir_eval 真值判定（foundry A：E_C=0.30 工艺窗口）
    q_fk = "量子A(演示近似)::Al/AlOx 固定频率 transmon"
    ec = registry.get(q_fk).quantum_window.get("ec_default")
    # f01 = √(8·E_J·E_C) − E_C = 5.0 → 反解 E_J = (5.0+E_C)²/(8·E_C)
    ej_hit = (5.0 + ec) ** 2 / (8.0 * ec)
    r_hit = ir_eval(m, {"E_J": round(ej_hit, 4)}, foundry_key=q_fk, registry=registry)
    if not r_hit["passed_all"]:
        print(f"FAIL B9 命中目标 E_J={ej_hit:.4f} 时未判 PASS：{r_hit['rows']}")
        return 1
    print(f"OK  B9 命中目标 E_J={ej_hit:.4f} → ir_eval PASS "
          f"(f01={r_hit['rows']['B9']['candidate']:.4f}GHz, tol={r_hit['rows']['B9']['tol']})")

    r_miss = ir_eval(m, {"E_J": 5.0}, foundry_key=q_fk, registry=registry)
    if r_miss["passed_all"]:
        print("FAIL B9 失配 E_J 时仍判 PASS（应为 FAIL）")
        return 1
    print(f"OK  B9 失配 E_J=5.0 → ir_eval FAIL "
          f"(f01={r_miss['rows']['B9']['candidate']:.4f}GHz ≠ 目标 5.0)")

    # 5) 跨量子 foundry 工艺窗口 → 不同 E_J 落点
    q_ks = [k for k in registry.list_pdks() if "量子" in k]
    ej_req = {}
    for k in q_ks:
        ec_k = registry.get(k).quantum_window.get("ec_default")
        ej_req[k] = round((5.0 + ec_k) ** 2 / (8.0 * ec_k), 4)
    print("OK  量子 foundry 工艺窗口驱动的 E_J 落点差异（f01 同目标 5.0GHz）：")
    for k in q_ks:
        ec_k = registry.get(k).quantum_window.get("ec_default")
        print(f"     - {k}: E_C={ec_k} → 需 E_J={ej_req[k]}")
    if len({round(v, 3) for v in ej_req.values()}) >= 2:
        print("OK  不同量子厂 E_C 窗口 → 不同 E_J 落点（工艺窗口驱动差异）")
    else:
        print("WARN 量子 foundry 落点未显现差异（E_C 近似一致）")

    print("\n=== L0 IR 量子子集 smoke: ALL GREEN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
