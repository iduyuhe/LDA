"""LDA · D-12 已验证器件库 smoke（注册表 + 契约 + 分层验收）。

验证器件库把已验证器件（D-01 DC/YB、D-11 Ring、Waveguide、D-03 Bragg）
固化为可复用资产：
  1. 注册表完整性（5 器件、ir_kinds 映射、params_schema、契约字段）；
  2. verify_all(contract)：注册表 + 契约 + 管道验证全 PASS（快，CI 用）；
  3. verify_all(live)：跑真实 ORACLE + 已验证求解器（light 项；需 GPU 项
     无 GPU 时诚实 SKIP；heavy 项默认跳过并标注）；
  4. 断言：contract 全过；live 中可运行项全过（SKIP 不算失败）。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.device_library import get_default_library


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-12 已验证器件库 smoke ===")
    lib = get_default_library()
    ok = True

    # 1) 注册表完整性
    names = lib.list()
    for expect in ("DirectionalCoupler", "SymmetricYBranch", "RingResonator",
                   "Waveguide", "BraggMirror"):
        ok &= check(expect in names, f"器件库注册 {expect}")
    ok &= check(lib.by_ir_kind("DirectionalCoupler").name == "DirectionalCoupler",
                "IR kind → 器件映射（DirectionalCoupler）")
    ok &= check(lib.by_ir_kind("RingResonator").name == "RingResonator",
                "IR kind → 器件映射（RingResonator）")
    ok &= check(lib.by_ir_kind("Waveguide").name == "Waveguide",
                "IR kind → 器件映射（Waveguide）")
    ok &= check(lib.by_ir_kind("SymmetricYBranch").name == "SymmetricYBranch",
                "IR kind → 器件映射（SymmetricYBranch）")
    for name in names:
        dev = lib.get(name)
        ok &= check(bool(dev.params_schema) and dev.verify_spec.spec_id,
                    f"{name}: params_schema + 契约 spec_id 齐全")
        ok &= check(bool(dev.description), f"{name}: description 非空")

    # 2) contract 模式：注册表 + 契约 + 管道全 PASS
    print("--- verify_all(contract) ---")
    outs, skipped = lib.verify_all(mode="contract")
    ok &= check(not skipped, "contract 模式无跳过")
    for name, out in outs.items():
        ok &= check(out.passed, f"contract[{name}] PASS（{out.diagnostics}）")
    print("--- summary ---")
    for k, v in lib.to_summary().items():
        print(f"    {k:<20} ir_kinds={v['ir_kinds']} metric={v['metric']:<12} "
              f"gpu={v['requires_gpu']} weight={v['live_weight']}")

    # 3) live 模式：真实 ORACLE + 已验证求解器（light 项；GPU 缺失诚实 SKIP）
    print("--- verify_all(live) ---")
    outs_l, skipped_l = lib.verify_all(mode="live")
    for name in skipped_l:
        print(f"    [HEAVY SKIP] {name}（重项，verify_one('{name}', mode='live') 单跑）")
    for name, out in outs_l.items():
        if out.extra.get("skipped"):
            print(f"    [SKIP] {name}: {out.diagnostics}")
            continue
        flag = "PASS" if out.passed else "FAIL"
        print(f"    [{flag}] {name}: cand={out.candidate} oracle={out.oracle_value} "
              f"err={out.err:.4f} tol={out.tol}")
        ok &= check(out.passed, f"live[{name}] PASS")

    # 4) 断言：light 可运行项至少 Ring 真跑 PASS；DC/YB 有 GPU 则必须 PASS
    ring_out = outs_l.get("RingResonator")
    ok &= check(ring_out is not None and ring_out.passed,
                "live RingResonator 真跑 PASS（解析，无需 GPU）")
    if any(not o.extra.get("skipped") for o in outs_l.values()):
        ok &= check(any(o.passed for o in outs_l.values()),
                    "live 至少一个真实候选 PASS")

    print("\n=== D-12 已验证器件库 smoke: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
