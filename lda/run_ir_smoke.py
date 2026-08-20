"""LDA L0 · IR 真跑 smoke 测试（光子 Waveguide 端到端 agent 闭环）。

证明"机器优先 IR"能端到端驱动真实 agent 设计闭环。注：DesignProblem 抽象已
随 webui 修复移除，DesignAgent 现只消费 intent dict，bridge 输出 intent：
  1. 构造 Waveguide IR（真 2D 波导，foundry 工艺窗口注入 n_si）；
  2. validate 通过（IR 层先过验证门，技术复利）；
  3. to_dict → from_dict round-trip 零损失；to_dsl 可读渲染；
  4. ir_to_multifoundry 跨光子 foundry 派生 intent（domain 过滤，不误派量子厂）；
  5. 每个 foundry 真跑 DesignAgent（geo_kind=waveguide_2d：FDTD neff ↔
     slab ORACLE）→ accepted；
  6. 断言全部 foundry PASS，并展示不同 n_si 工艺窗口 → 不同 neff 落点。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations

import sys

from lda_ir import (FoundryPlan, IRModel, ObjectiveSpec, Waveguide, dumps,
                    from_dict, to_dict, to_dsl, validate)
from lda_ir.bridge import ir_to_multifoundry
from lda_l2.pdk import get_default_registry
from lda_agent.design_loop import DesignAgent


def build_waveguide_ir() -> IRModel:
    """构造一个"真 2D 波导"IR：跨全部光子 foundry 落点（n_si 工艺窗口差异）。

    objective 用 B2（波导 n_eff 标准题）作为设计意图——满足 IR 层"至少一个
    意图"的门禁；waveguide_2d 验收本身由 DesignAgent 对 slab ORACLE 完成。
    """
    m = IRModel(
        domain="photon",
        name="wg-neff",
        components=[Waveguide(id="wg", width=0.5, width_bounds=(0.35, 0.75))],
        objectives=[ObjectiveSpec(bid="B2", target=2.62, tol=0.02)],
        foundry_plan=FoundryPlan(mode="all"),
        notes="L0 IR：真 2D 波导验收闭环（FDTD neff ↔ slab ORACLE）",
    )
    return m


def main() -> int:
    print("=== L0 IR 光子 smoke (Waveguide) ===")
    registry = get_default_registry()

    # 1) 构造 + 校验
    m = build_waveguide_ir()
    errs = validate(m)
    if errs:
        print("FAIL IR 校验：")
        for e in errs:
            print("  -", e)
        return 1
    print("OK  IR 校验通过（component/net/objective/spectrum/foundry_plan 均合法）")

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

    # 4) 多 foundry 桥接（domain=photon → 仅光子 foundry，派生 intent dict）
    plans = ir_to_multifoundry(m, registry)
    if not plans:
        print("FAIL 未派生出任何光子 foundry intent")
        return 1
    print(f"OK  派生 {len(plans)} 个光子 foundry intent：")
    for k, intent in plans:
        print(f"     - {k}  (n_si={intent['materials']['sih']})")

    # 5) 真跑每个 foundry 逆设计（waveguide_2d 单次验证即判定）
    agent = DesignAgent(backend="numpy", geo_kind="waveguide_2d")
    rs = {}
    for k, intent in plans:
        rep = agent.run(intent)
        ok = rep.accepted
        rs[k] = (rep.final_metric, rep.final_oracle_metric, ok)
        flag = "PASS" if ok else "FAIL"
        print(f"   [{flag}] {k}: neff(FDTD)={rep.final_metric:.4f} "
              f"slab={rep.final_oracle_metric:.4f} "
              f"|Δneff|={abs(rep.final_metric - rep.final_oracle_metric):.2e}")

    # 6) 全部 PASS + 工艺窗口驱动差异
    if not all(v[2] for v in rs.values()):
        print("FAIL 部分 foundry 未过验收")
        return 1
    print("OK  全部 foundry PASS（FDTD neff 对 slab ORACLE 在公差内）")
    if len(plans) >= 2:
        neffs = {round(v[0], 4) for v in rs.values()}
        if len(neffs) >= 2:
            print(f"OK  不同 foundry n_si 工艺窗口 → 不同 neff 落点 {sorted(neffs)}")
        else:
            print("WARN 各 foundry neff 落点相同（n_si 近似一致），仍判通过")

    print("\n=== L0 IR smoke: ALL GREEN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
