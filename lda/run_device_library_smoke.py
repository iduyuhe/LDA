"""LDA · D-12 已验证器件库 smoke（T-8 去 GPU · 5 器件 live 全跑 + 全进 CI）。

T-8 前后对比（v0.9.38，实测）：
  前：verify_all(mode="live") 无 GPU 时 **只能演示 1 个（Ring）**，DC/YB 因
      `requires_gpu` 硬门禁 SKIP，WG/Bragg 被判 heavy 默认跳过。
  后：**5 个器件全部真跑 PASS、零 SKIP**，且全部进 CI core。

验收内容：
  1. 注册表完整性（5 器件 + backend 字段 + ir_kinds 映射 + 契约字段）；
  2. verify_all(contract) 全 PASS（快）；
  3. 🔴 verify_all(live) **5/5 真跑、零 SKIP、全 PASS**（T-8 核心断言）；
  4. numba ↔ numpy 同档位交叉验证（WG 后端换核不改物理，判据 ≤1e-9）；
  5. 🔴 反向测试（护栏必须会响，IRONLAWS: 没被验证过的护栏不算护栏）：
       a. 未知 backend ⇒ resolve_backend 必须判为「不可运行」（SKIP 通道会响）；
       b. tol 收紧到 1e-12 ⇒ Ring live 必须 FAIL（PASS 不是白送）；
       c. numba 假装不可用 ⇒ WG 必须仍可运行且回退 numpy（降级通道会响）。

退出码 0=全绿；非 0=有失败。
"""
from __future__ import annotations

import copy
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 线程预算（须在任何数值内核初始化之前）：numba parallel / torch / MKL 一律限到
# 一半核心（上限 10）。依据见 lda_solver/threads.py 的宕机取证说明。
from lda_solver.threads import apply_thread_budget  # noqa: E402
THREAD_INFO = apply_thread_budget(verbose=True)

from lda_l2.device_library import get_default_library  # noqa: E402

ALLOWED_BACKENDS = ("numpy", "torch", "numba→numpy")
EXPECTED_DEVICES = ("DirectionalCoupler", "SymmetricYBranch", "RingResonator",
                    "Waveguide", "BraggMirror")


def check(cond: bool, msg: str) -> bool:
    if cond:
        print("OK  " + msg)
        return True
    print("FAIL " + msg)
    return False


def main() -> int:
    print("=== D-12 已验证器件库 smoke（T-8 去 GPU）===")
    lib = get_default_library()
    ok = True

    # 1) 注册表完整性
    names = lib.list()
    for expect in EXPECTED_DEVICES:
        ok &= check(expect in names, f"器件库注册 {expect}")
    for kind in ("DirectionalCoupler", "RingResonator", "Waveguide",
                 "SymmetricYBranch"):
        d = lib.by_ir_kind(kind)
        ok &= check(d is not None and d.name == kind,
                    f"IR kind → 器件映射（{kind}）")
    for name in names:
        dev = lib.get(name)
        ok &= check(bool(dev.params_schema) and dev.verify_spec.spec_id,
                    f"{name}: params_schema + 契约 spec_id 齐全")
        ok &= check(bool(dev.description), f"{name}: description 非空")
        ok &= check(dev.backend in ALLOWED_BACKENDS,
                    f"{name}: backend={dev.backend!r} ∈ {ALLOWED_BACKENDS}")
        # T-8 语义：requires_gpu 恒 False（GPU 降级为可选加速，不再是门禁）
        ok &= check(dev.requires_gpu is False,
                    f"{name}: requires_gpu=False（T-8：GPU 由必需降为可选加速）")
        ok &= check(dev.live_weight == "light",
                    f"{name}: live_weight=light（T-8：无 heavy 项）")

    # 2) contract 模式：注册表 + 契约 + 管道全 PASS
    print("--- verify_all(contract) ---")
    outs, skipped = lib.verify_all(mode="contract")
    ok &= check(not skipped, "contract 模式无跳过")
    for name, out in outs.items():
        ok &= check(out.passed, f"contract[{name}] PASS")

    # 3) 🔴 T-8 核心：live 5/5 真跑、零 SKIP、全 PASS
    print("--- verify_all(live) ---")
    t_live0 = time.time()
    outs_l, skipped_l = lib.verify_all(mode="live")
    t_live = time.time() - t_live0
    ok &= check(not skipped_l,
                f"live 无 heavy 跳过（实际 skipped={skipped_l}）")
    ok &= check(len(outs_l) == len(EXPECTED_DEVICES),
                f"live 全部 {len(EXPECTED_DEVICES)} 器件进入验收（实际 {len(outs_l)}）")
    n_skipped = 0
    for name in EXPECTED_DEVICES:
        out = outs_l.get(name)
        if out is None:
            ok &= check(False, f"live[{name}] 未产出结果")
            continue
        if out.extra.get("skipped"):
            n_skipped += 1
            ok &= check(False, f"live[{name}] 不应 SKIP（{out.diagnostics}）")
            continue
        backend = out.extra.get("backend")
        device = out.extra.get("device")
        ok &= check(out.passed,
                    f"live[{name}] PASS（backend={backend} device={device} "
                    f"cand={out.candidate} oracle={out.oracle_value} "
                    f"err={out.err:.4g} tol={out.tol}）")
    # ← T-8 之前这行是「只要求至少 1 个跑」；现在必须零 SKIP
    ok &= check(n_skipped == 0,
                f"live 零 SKIP（无 GPU 亦全部可现场演示；实际 SKIP={n_skipped}）")
    print(f"    live 总耗时 {t_live:.1f}s")

    print("--- backend 披露 ---")
    for name in EXPECTED_DEVICES:
        out = outs_l.get(name)
        if out is None:
            continue
        print(f"    {name:<20} backend={out.extra.get('backend'):<12} "
              f"device={out.extra.get('device')}")

    # 4) numba ↔ numpy 交叉验证（同物理、同档位，只换计算内核）
    print("--- WG 后端交叉验证（numba vs numpy，同档位）---")
    try:
        sys.path.insert(0, os.path.join(_HERE, "lda_solver"))
        from fdtd3d_waveguide import (build_waveguide_field_3d,
                                      solve_waveguide_neff_3d)
        from fdtd3d_waveguide_numba import (solve_waveguide_neff_3d_numba,
                                            backend_info)
        from oracle_mode import fdfd_mode_field

        info = backend_info()
        print(f"    numba available={info['have_numba']} {info['import_error']}")
        if info["have_numba"]:
            wl, n_core, n_clad = 1.55, 3.48, 1.44
            dl = wl / 24.0
            eps3, meta = build_waveguide_field_3d(0.5, 0.22, n_core, n_clad,
                                                  wl, dl=dl, clad_um=1.5,
                                                  Lz_um=4.0)
            _ne, mode2d = fdfd_mode_field(eps3, meta["dl"], wl)
            kw = dict(n_clad=n_clad, n_core=n_core, mode_source=mode2d,
                      M_periods=8, transient_min=800)   # 缩窗只为快，物理网格不变
            t0 = time.time()
            ne_np = solve_waveguide_neff_3d(eps3, meta["dl"], wl, **kw)
            t_np = time.time() - t0
            t0 = time.time()
            ne_nb = solve_waveguide_neff_3d_numba(eps3, meta["dl"], wl, **kw)
            t_nb = time.time() - t0
            rel = abs(ne_nb - ne_np) / abs(ne_np)
            ok &= check(rel <= 1e-9,
                        f"numba↔numpy 同档位一致（rel={rel:.3e} ≤ 1e-9；"
                        f"numpy={ne_np:.9f} numba={ne_nb:.9f}）")
            ok &= check(n_clad * 1.001 < ne_nb < n_core * 0.999,
                        f"numba neff={ne_nb:.6f} 落物理区间 ({n_clad}, {n_core})")
            print(f"    计时：numpy={t_np:.1f}s numba={t_nb:.1f}s "
                  f"加速比={t_np / max(t_nb, 1e-9):.1f}x")
        else:
            print("    [SKIP] numba 不可用，交叉验证不适用（器件库已回退 numpy）")
    except Exception as e:  # noqa: BLE001
        ok &= check(False, f"WG 后端交叉验证异常：{type(e).__name__}: {e}")

    # 5) 🔴 反向测试：护栏必须会响
    print("--- 反向测试（证明护栏会响）---")
    # a. 未知 backend ⇒ 必须判为不可运行
    try:
        from lda_l2.device_library import DeviceSpec
        bad = DeviceSpec(name="__probe_unknown_backend__", ir_kinds=[], params_schema={},
                         description="probe", verify_spec=lib.get("RingResonator").verify_spec,
                         candidate_fn=lambda s, o: 1.0, backend="__nope__")
        runnable, used, why = lib.resolve_backend(bad)
        ok &= check((not runnable) and bool(why),
                    f"未知 backend 被判不可运行（runnable={runnable} why={why[:40]}）")
    except Exception as e:  # noqa: BLE001
        ok &= check(False, f"反向测试 a 异常：{type(e).__name__}: {e}")

    # b. tol 收紧到 1e-12 ⇒ live 必须 FAIL（证明 PASS 不是白送）
    try:
        from lda_harness.verification_spec import run_verification
        ring = lib.get("RingResonator")
        tight = copy.copy(ring.verify_spec)
        tight.tol = 1e-12
        out_t = run_verification(tight, ring.candidate_fn)
        ok &= check(not out_t.passed,
                    f"收紧 tol=1e-12 后 Ring 必须 FAIL（实际 passed={out_t.passed}, "
                    f"err={out_t.err:.3g}）")
    except Exception as e:  # noqa: BLE001
        ok &= check(False, f"反向测试 b 异常：{type(e).__name__}: {e}")

    # c. numba 假装不可用 ⇒ WG 必须仍可运行（降级通道会响）
    try:
        wg = lib.get("Waveguide")
        orig = type(lib)._numba_ok
        type(lib)._numba_ok = staticmethod(lambda: False)
        try:
            runnable, used, why = lib.resolve_backend(wg)
        finally:
            type(lib)._numba_ok = orig
        ok &= check(runnable and used == "numpy",
                    f"numba 不可用时 WG 回退 numpy 仍可运行（used={used!r}）")
    except Exception as e:  # noqa: BLE001
        ok &= check(False, f"反向测试 c 异常：{type(e).__name__}: {e}")

    print("\n=== D-12 已验证器件库 smoke（T-8）: "
          + ("ALL GREEN" if ok else "HAS FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
