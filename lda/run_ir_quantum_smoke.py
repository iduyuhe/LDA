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

    # 6) D-40：全部量子 kind（Transmon/Resonator/Coupler）物理锚 + schema v0.3 受控升级
    from lda_ir import Coupler, Resonator  # noqa: E402

    m_r = IRModel(
        domain="quantum", name="resonator-f0-B12",
        components=[Resonator(id="r1")],
        objectives=[ObjectiveSpec(
            bid="B12",
            target=round(1.0 / (4.0 * 3000e-6 * (0.4e-6 * 1.5e-10) ** 0.5) / 1e9, 4),
            tol=0.02, role="objective")],
    )
    m_c = IRModel(
        domain="quantum", name="coupler-J-B13",
        components=[Coupler(id="c1")],
        objectives=[ObjectiveSpec(bid="B13",
                                  target=round(Coupler().params["J_ghz"], 4),
                                  tol=0.10, role="objective")],
    )
    for name, mm in (("Resonator", m_r), ("Coupler", m_c)):
        errs = validate(mm)
        ph = mm.components[0].physics
        if errs or ph is None or not ph.spec_params:
            print(f"FAIL D-40 {name} IR 校验/物理锚：{errs or 'physics 缺失'}")
            return 1
        if mm.schema_version != "0.3":
            print(f"FAIL D-40 {name} schema_version 应为 0.3，got {mm.schema_version}")
            return 1
        mm2 = from_dict(to_dict(mm))
        if dumps(mm) != dumps(mm2):
            print(f"FAIL D-40 {name} round-trip 信息损失")
            return 1
        print(f"OK  D-40 {name}: schema={mm.schema_version} physics.bid={ph.bid} "
              f"({ph.kind}) spec_params={list(ph.spec_params)}")
    # Transmon 也挂物理锚（B9）
    if m.components[0].physics is None or m.components[0].physics.bid != "B9":
        print("FAIL D-40 Transmon 缺 physics 锚 B9")
        return 1
    print("OK  D-40 Transmon: physics.bid=B9 (transmon-f01)")

    # 7) D-40：schema 受控升级——v0.2 遗留模型仍可校验（向后兼容）
    m_legacy = IRModel(schema_version="0.2", domain="quantum",
                       components=[Transmon(id="q1")],
                       objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1)])
    errs_legacy = validate(m_legacy)
    if errs_legacy:
        print(f"FAIL D-40 schema 0.2 遗留模型不再兼容：{errs_legacy}")
        return 1
    print("OK  D-40 schema 受控升级：0.2 遗留模型仍可校验（向后兼容）")

    # 8) D-40：ir_eval B12（resonator f0）/ B13（coupler J）真值判定
    r_hit12 = ir_eval(m_r, {"Lp": 0.4e-6, "Cp": 1.5e-10, "l": 3000e-6})
    if not r_hit12["passed_all"]:
        print(f"FAIL B12 命中未判 PASS：{r_hit12['rows']}")
        return 1
    print(f"OK  B12 ir_eval PASS（f0={r_hit12['rows']['B12']['candidate']:.4f}GHz）")
    r_miss12 = ir_eval(m_r, {"Lp": 0.6e-6, "Cp": 1.5e-10, "l": 3000e-6})
    if r_miss12["passed_all"]:
        print("FAIL B12 失配 Lp 仍判 PASS（应为 FAIL）")
        return 1
    print("OK  B12 失配 Lp → ir_eval FAIL")

    r_hit13 = ir_eval(m_c, {})
    if not r_hit13["passed_all"]:
        print(f"FAIL B13 命中未判 PASS：{r_hit13['rows']}")
        return 1
    print(f"OK  B13 ir_eval PASS（J={r_hit13['rows']['B13']['candidate']:.5f}GHz）")
    r_miss13 = ir_eval(m_c, {"Cc": 0.2})
    if r_miss13["passed_all"]:
        print("FAIL B13 失配 Cc 仍判 PASS（应为 FAIL）")
        return 1
    print("OK  B13 失配 Cc → ir_eval FAIL")

    print("\n=== L0 IR 量子子集 smoke: ALL GREEN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
