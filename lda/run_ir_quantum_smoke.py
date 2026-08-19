"""LDA L0 · 量子子集 IR 真跑 smoke 测试。

证明"统一 IR"对**量子域**同样端到端可用——与光子子集共用同一套 core /
校验器 / 桥接层 / agent 设计闭环，仅 domain="quantum" + 量子 Kinds + B9
确定性物理锚：
  1. 构造一个 Transmon IR：目标 f01=5.0GHz（B9 objective），调 E_J/E_C 命中；
  2. validate 通过（同光子 IR 走同一道 IR 层验证门）；
  3. to_dict → from_dict round-trip 零损失；to_dsl 可读渲染；
  4. ir_to_multifoundry 跨量子 foundry 派生 DesignProblem（domain 过滤自动
     只选"量子" foundry，不会误派光子 foundry）；
  5. 真跑 DesignAgent（N 维 Nelder-Mead 逆设计）→ 收敛 + final_passed_all；
  6. 断言 f01 命中目标（误差 < tol），证明量子侧设计闭环被同一 IR 驱动。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations

import sys

from lda_ir import (FoundryPlan, IRModel, ObjectiveSpec, Transmon, dumps,
                    from_dict, to_dict, to_dsl, validate)
from lda_ir.bridge import ir_to_multifoundry
from lda_l2.pdk import get_default_registry
from lda_l1.protocol import KernelGateway
from lda_agent.design_loop import DesignAgent


def build_transmon_ir() -> IRModel:
    """构造一个"transmon 频率逆设计"量子 IR：目标 f01=5.0GHz，跨量子 foundry。

    不写死 E_C —— 由 bridge 注入各 foundry 的 quantum_window.ec_default，
    使同一 f01 目标在不同量子厂收敛到不同 E_J 落点（量子多晶圆厂共建）。
    """
    m = IRModel(
        domain="quantum",
        name="transmon-f01-B9",
        components=[Transmon(id="q1", E_J=20.0,
                             EJ_bounds=(5.0, 40.0), EC_bounds=(0.1, 1.0))],
        objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1,
                                  role="objective")],
        foundry_plan=FoundryPlan(mode="all"),   # 跨已注册量子 foundry 各跑一遍
        notes="L0 IR 量子子集：transmon 频率逆设计 + 多晶圆厂落点（候选④）",
    )
    return m


def main() -> int:
    print("=== L0 IR 量子子集 smoke ===")
    registry = get_default_registry()
    gw = KernelGateway(out_dir="reports_ir_q")
    agent = DesignAgent(gw, out_dir="reports_ir_q")

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

    # 4) 多 foundry 桥接（domain=quantum → 仅量子 foundry）
    plans = ir_to_multifoundry(m, registry, solver="truth")
    if not plans:
        print("FAIL 未派生出任何量子 foundry 设计问题")
        return 1
    print(f"OK  派生 {len(plans)} 个量子 foundry 设计问题：")
    for k, _ in plans:
        print("   -", k)

    # 5) 真跑每个量子 foundry 逆设计
    rs = {}
    for k, prob in plans:
        res = agent.run(prob, max_iter=120)
        ok = res.converged and res.final_passed_all
        ec = prob.base_params.get("E_C")   # E_C 由工艺窗口固定（非可调）
        rs[k] = (res.final_param, round(res.final_metric, 5), ok, ec)
        flag = "PASS" if ok else "FAIL"
        ej = res.final_param.get("E_J")
        print(f"   [{flag}] {k}: E_J={ej} (固定 E_C={ec}) "
              f"f01={round(res.final_metric,5)} passed={res.final_passed_all}")

    # 6) 收敛 + 命中目标
    converged = [v for v in rs.values() if v[2]]
    if len(converged) < len(plans):
        print("FAIL 部分量子 foundry 未收敛/未过验证")
        return 1
    # 取首个结果校验 f01 命中（误差 < tol=0.1）
    first = next(iter(rs.values()))
    if abs(first[1] - 5.0) > 0.1:
        print(f"FAIL f01 未命中目标 5.0GHz（实际 {first[1]}）")
        return 1
    print("OK  量子设计闭环收敛且 f01 命中目标（同一 IR 驱动光子+量子）")

    # 7) 量子多晶圆厂落点差异：不同 foundry 的 E_C 工艺窗口 → 不同 E_J 落点
    if len(rs) >= 2:
        ejs = [v[0].get("E_J") for v in rs.values() if v[0] and "E_J" in v[0]]
        ecs = [v[3] for v in rs.values()]
        if len(set(map(str, ecs))) >= 2 and len(set(map(str, ejs))) >= 2:
            print(f"OK  量子多晶圆厂落点差异可见（E_C={ecs} → E_J={ejs}），"
                  "工艺窗口驱动设计落点")
        else:
            print(f"WARN 量子多 foundry 落点未显现差异（E_C={ecs}, E_J={ejs}）"
                  "——检查 bridge 量子窗口注入")
    else:
        print("WARN 仅 1 个量子 foundry，无法验证多晶圆厂差异")

    print("\n=== L0 IR 量子子集 smoke: ALL GREEN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
