"""LDA L0 IR v0.2 增补 smoke（静态，不跑 GPU 逆设计）。

验证 D-05 字段补全（光子子集 + 量子骨架推进）：
  - 光子：DirectionalCoupler（D-01 方向耦合器验收锚）、SymmetricYBranch
    （D-01 对称分束器验收锚）、RingResonator 扩展（Q / kappa / target_fsr_nm）；
  - 量子：Transmon.target_f01 骨架字段（从"预留"推进为"骨架定义"）；
  - schema_version == 0.2；
  - 序列化 round-trip 零损失、to_dsl 渲染、导出示例 JSON（IR = 事实源）。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations

import json
import os
import sys

# 让 `lda/` 在 sys.path（与 design_loop.py / run_ir_smoke.py 同约定）
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_ir import (DirectionalCoupler, SymmetricYBranch, RingResonator,
                    Transmon, Waveguide, IRModel, FoundryPlan, SpectrumSpec,
                    ObjectiveSpec, dumps, from_dict, to_dict, to_dsl, validate)
from lda_ir.photon import KNOWN_KINDS
from lda_ir.bridge import ir_to_intent  # 轻量：仅构造 intent dict，不跑逆设计


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== L0 IR v0.2 增补 smoke (D-05) ===")
    ok = True

    # 0) schema 版本 + 词汇表
    ok &= check(IRModel().schema_version == "0.2", "默认 schema_version == 0.2")
    ok &= check("DirectionalCoupler" in KNOWN_KINDS, "KNOWN_KINDS 含 DirectionalCoupler")
    ok &= check("SymmetricYBranch" in KNOWN_KINDS, "KNOWN_KINDS 含 SymmetricYBranch")

    # 1) 方向耦合器（D-01 验收锚）：构造 + 字段 + round-trip + DSL
    dc = DirectionalCoupler(id="dc1", gap=0.30, Lc=12.0, kappa_target=0.035)
    ok &= check(dc.kind == "DirectionalCoupler", "DirectionalCoupler kind 正确")
    ok &= check(dc.params.get("gap") == 0.30 and dc.params.get("kappa_target") == 0.035,
                "DirectionalCoupler 字段(gap/kappa_target)正确")
    ok &= check([p.name for p in dc.ports] == ["in1", "in2", "thru1", "thru2"],
                "DirectionalCoupler 四端口正确")
    m_dc = IRModel(domain="photon", name="dc-demo", components=[dc])
    r1 = from_dict(to_dict(m_dc))
    ok &= check(dumps(m_dc) == dumps(r1), "DirectionalCoupler IR round-trip 零损失")
    ok &= check("gap=0.3" in to_dsl(m_dc), "to_dsl 渲染含 gap 字段")

    # 2) 对称 Y 分支分束器（D-01 验收锚）
    yb = SymmetricYBranch(id="yb1", width=0.5, split_angle=10.0, arm_length=5.0)
    ok &= check(yb.params.get("split_angle") == 10.0, "SymmetricYBranch 字段正确")
    m_yb = IRModel(domain="photon", name="yb-demo", components=[yb])
    r2 = from_dict(to_dict(m_yb))
    ok &= check(dumps(m_yb) == dumps(r2), "SymmetricYBranch IR round-trip 零损失")

    # 3) RingResonator 扩展字段（Q/kappa/target_fsr_nm）+ 完整 validate
    ring = RingResonator(id="ring1", R=10.0, Q=1.0e4, kappa=0.05, target_fsr_nm=9.15)
    ok &= check(ring.params.get("Q") == 1.0e4 and ring.params.get("kappa") == 0.05
                and ring.params.get("target_fsr_nm") == 9.15,
                "RingResonator v0.2 字段(Q/kappa/target_fsr_nm)正确")
    m_ring = IRModel(domain="photon", name="ring-demo", components=[ring],
                     spectrum=SpectrumSpec(kind="ring_fsr", target_fsr_nm=9.15,
                                           wl0_um=1.55, n_g=4.2, primary_param="R"),
                     foundry_plan=FoundryPlan(mode="all"))
    errs = validate(m_ring)
    ok &= check(not errs, f"RingResonator(v0.2) IR 过 validate（扩字段不破坏校验） errs={errs}")
    r3 = from_dict(to_dict(m_ring))
    ok &= check(dumps(m_ring) == dumps(r3), "RingResonator(v0.2) IR round-trip 零损失")

    # 4) 量子 Transmon.target_f01 骨架字段
    q = Transmon(id="q1", E_J=20.0, E_C=0.30, target_f01=5.0)
    ok &= check(q.params.get("target_f01") == 5.0, "Transmon.target_f01 骨架字段正确")
    m_q = IRModel(domain="quantum", name="q-demo", components=[q],
                  objectives=[ObjectiveSpec(bid="B9", target=5.0, tol=0.1)])
    errs_q = validate(m_q)
    ok &= check(not errs_q, f"Transmon(target_f01) IR 过 validate errs={errs_q}")
    r4 = from_dict(to_dict(m_q))
    ok &= check(dumps(m_q) == dumps(r4), "Transmon(v0.2) IR round-trip 零损失")

    # 5) bridge 轻量构造（不跑逆设计）：Waveguide → intent；RingResonator 诚实 NotImplemented
    try:
        from lda_l2.pdk import get_default_registry
        registry = get_default_registry()
        fk = [k for k in registry.list_pdks() if "量子" not in k][0]
        m_wg = IRModel(domain="photon", name="wg-bridge",
                       components=[Waveguide(id="wg", width=0.5)])
        intent = ir_to_intent(m_wg, registry, fk)
        ok &= check(intent["geometry_type"] == "waveguide_2d"
                    and intent["materials"]["sih"] == registry.get(fk).n_si,
                    "bridge 由 Waveguide IR 构造 waveguide_2d intent（foundry n_si 注入）")
        try:
            ir_to_intent(m_ring, registry, fk)
            ok &= check(False, "RingResonator 应诚实 NotImplementedError")
        except NotImplementedError:
            ok &= check(True,
                        "RingResonator 桥接诚实 NotImplementedError"
                        "（当前 DesignAgent 仅支持 Waveguide，谱形逆设计规划 D-09）")
    except Exception as e:  # 环境差异不致命（CI 无 lda_agent 依赖）
        print("WARN bridge 检查跳过：", e)

    # 6) 导出示例 JSON（IR = 事实源，机器语言落盘）
    out = {
        "directional_coupler": to_dict(m_dc),
        "symmetric_y_branch": to_dict(m_yb),
        "ring_resonator_v02": to_dict(m_ring),
        "transmon_target_f01": to_dict(m_q),
    }
    rep_dir = os.path.join(_HERE, "reports")
    os.makedirs(rep_dir, exist_ok=True)
    with open(os.path.join(rep_dir, "ir_d05_examples.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("OK  导出示例 IR JSON -> lda/reports/ir_d05_examples.json")

    print("\n=== L0 IR v0.2 smoke: " + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
