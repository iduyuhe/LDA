"""LDA L0 IR 逆设计扩面 guard（v0.9.55）：IR → D-38 注册表四类已验证器件闭环。

验证（测生产代码本身，非副本重算）：
  - RingResonator / BraggMirror / RingAddDrop / Transmon 四类 IR 经
    ir_to_inverse_design 真跑通并 accepted（返回真实 final_params，非静默空列表）；
  - BraggMirror 方法一致性误差 < 0.1（C 级自主，3D FDTD vs TMM 终验不借外部求解器）；
  - 反向护栏①：未知 IR kind（如 GratingCoupler）→ 诚实 NotImplementedError；
  - 反向护栏②：篡改 D-38 注册表删去某 kind → 桥接闭环不再 accepted（证明桥接路由到
    真实注册表而非副本，杜绝"标签≠行为"静默漂移）。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations

import os
import sys

# 让 `lda/` 在 sys.path（与 run_ir_d05_smoke.py 同约定）
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_ir import (IRModel, RingResonator, BraggMirror, RingAddDrop, Transmon,
                    GratingCoupler, SpectrumSpec, FoundryPlan)
from lda_ir.bridge import ir_to_inverse_design, ir_to_multifoundry_inverse, _INVERSE_KINDS
from lda_ir.photon import KNOWN_KINDS
from lda_l2.pdk import get_default_registry


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== L0 IR 逆设计扩面 guard (v0.9.55) ===")
    ok = True

    registry = get_default_registry()
    fk = [k for k in registry.list_pdks() if "量子" not in k][0]

    # 0) 词汇表 + 桥接集合完整性
    ok &= check("BraggMirror" in KNOWN_KINDS, "KNOWN_KINDS 含 BraggMirror")
    ok &= check("RingAddDrop" in KNOWN_KINDS, "KNOWN_KINDS 含 RingAddDrop")
    ok &= check(len(_INVERSE_KINDS) >= 4,
                f"桥接 _INVERSE_KINDS 含 4 类（实际 {len(_INVERSE_KINDS)}）")

    # 1) 四类 IR → run_inverse_design 真跑通（accepted + 真实 final_params）
    ring = IRModel(domain="photon", name="r",
                   components=[RingResonator(R=10.0, target_fsr_nm=9.15)],
                   spectrum=SpectrumSpec(target_fsr_nm=9.15, wl0_um=1.55, n_g=4.2))
    rep = ir_to_inverse_design(ring, registry, fk)
    ok &= check(rep.get("accepted") and rep.get("final_params"),
                "RingResonator IR → 逆设计闭环 accepted（真实 final_params）")

    bm = IRModel(domain="photon", name="b", components=[BraggMirror(target_r_min=0.99)])
    rep = ir_to_inverse_design(bm, registry, fk)
    ok &= check(rep.get("accepted") and rep.get("final_params"),
                "BraggMirror IR → 逆设计闭环 accepted（真实 final_params）")
    ok &= check(rep.get("method_err", 9) < 0.1,
                f"BraggMirror 方法一致性误差<0.1（C级自主，实测 {rep.get('method_err')}）")

    rad = IRModel(domain="photon", name="a",
                  components=[RingAddDrop(R=6.0, target_Q=2500.0)])
    rep = ir_to_inverse_design(rad, registry, fk)
    ok &= check(rep.get("accepted") and rep.get("final_params"),
                "RingAddDrop IR → 逆设计闭环 accepted（真实 final_params）")

    q = IRModel(domain="quantum", name="q",
                components=[Transmon(E_J=20.0, E_C=0.30, target_f01=5.0)])
    rep = ir_to_inverse_design(q, registry, fk)
    ok &= check(rep.get("accepted") and rep.get("final_params"),
                "Transmon IR → 逆设计闭环 accepted（真实 final_params）")

    # 2) 多 foundry 对称派发（光子 kind）
    multi = IRModel(domain="photon", name="multi", components=[BraggMirror()],
                   foundry_plan=FoundryPlan(mode="all"))
    outs = ir_to_multifoundry_inverse(multi, registry)
    ok &= check(len(outs) >= 1 and all(r.get("accepted") for _, r in outs),
                f"ir_to_multifoundry_inverse 跨 {len(outs)} foundry 均 accepted")

    # 3) 反向护栏①：未知 kind → 诚实 NotImplementedError（不静默返回假 intent）
    bad = IRModel(domain="photon", name="bad", components=[GratingCoupler(id="gc")])
    try:
        ir_to_inverse_design(bad, registry, fk)
        ok &= check(False, "未知 kind 应诚实 NotImplementedError")
    except NotImplementedError:
        ok &= check(True, "未知 kind（GratingCoupler）诚实 NotImplementedError")

    # 4) 反向护栏②：篡改注册表删某 kind → 桥接闭环不再 accepted（路由到真实注册表）
    import lda_agent.inverse_design as inv
    saved = inv._INVERSE_DESIGNS
    try:
        inv._INVERSE_DESIGNS = {k: v for k, v in saved.items() if k != "BraggMirror"}
        rep = ir_to_inverse_design(bm, registry, fk)
        ok &= check(not rep.get("accepted"),
                    "注册表删 BraggMirror → 桥接闭环不通过（护栏会响，非副本）")
    finally:
        inv._INVERSE_DESIGNS = saved
    ok &= check("BraggMirror" in inv._INVERSE_DESIGNS, "注册表已恢复（teardown 正确）")

    print("\n=== L0 IR 逆设计扩面 guard: " + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
