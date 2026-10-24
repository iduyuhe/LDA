"""B30 读出保真度 quad 候选护栏 smoke（v0.9.39 · T-9 接线 #2）。

守护四件事：
  ① harness 正向：B30 候选必须 PASS（残差 ≪ tol）
  ② candidate 登记必须是 readout_fidelity_quad（防回退自证桩）
  ③ 🔴 判据 D：高斯重叠积分残差随 nx 单调收敛（真数值离散化，非代数恒等）
  ④ 反向：nbar +10% ⇒ SNR 变 ⇒ F 变 ~3.4e-3 ≫ tol 必 FAIL

运行：python run_b30_readout_smoke.py（~3s）
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS = 0
FAIL = 0


# 🔴 check 已归一：实现**单一定义**在 lda_harness/smoke_kit.py
#   （v0.9.113 · 波次 2 · 源自 2026-09-19 审计 F-07）。调用方尾部
#   （含模块级计数器读取）与输出格式**均未改**，见 smoke_kit 模块 docstring。
from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="  ", detail_fmt=' —— {d}')

# ===========================================================================
# N2 · 超导域判据深度：门禁运行时登记（v0.9.282）
# ---------------------------------------------------------------------------
# 🔴 为什么本门禁**允许**出现锚号字面量：本门禁**真的执行**该锚（下文的
#    `BENCHMARK_DEFS["B30"]` → `run_verification`），不是"为了刷覆盖写一行注释"。
#    登记面走 `asserted_anchor_ids()`（gate_manifest 消费），并由 H7 判据
#    **双向锁死**：声明集 ≡ 本次运行实际断言集 ⇒ 删掉执行代码必红。
# ===========================================================================
ASSERTED_ANCHORS = ("B30",)
_RUNTIME_ASSERTED: list = []


def asserted_anchor_ids():
    """本门禁运行时实际断言的锚集（`scripts/gate_manifest.py` 消费）。

    未运行（被 import）时回落到声明面；运行后返回真实执行集。
    两者由 H7 判据锁死，不允许漂移。
    """
    return tuple(_RUNTIME_ASSERTED) or tuple(ASSERTED_ANCHORS)


def main() -> int:
    print("=" * 72)
    print("B30 读出保真度 quad 候选护栏（readout_fidelity_quad）")
    print("=" * 72)

    from lda_solver.readout_fidelity_quad import (
         quad_convergence,
    )

    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness.verification_adapters import build_harness_specs
    from lda_harness.verification_spec import run_verification

    # ------------------------------------------------ ② 登记防回退
    b30 = BENCHMARK_DEFS["B30"]
    check("candidate 登记 = readout_fidelity_quad",
          b30.get("candidate") == "readout_fidelity_quad",
          "实际=%s（防回退自证桩）" % b30.get("candidate"))

    # ------------------------------------------------ ① harness 正向
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == "B30"][0]
    fn = cand["B30"]
    ov = sp.oracle_fn(sp.params)
    cv = fn(sp, ov)
    res = run_verification(sp, fn, oracle_value=ov)
    check("B30 正向 PASS", bool(res.passed),
          "cand=%.8f gold=%.8f 残差=%.2e tol=%s" % (cv, ov, abs(cv - ov), sp.tol))

    # ------------------------------------------------ ③ 判据 D 单调收敛
    conv = quad_convergence()
    errs = [r["abs_err"] for r in conv["rows"]]
    check("判据D：高斯重叠积分残差随 nx 单调收敛（真独立）",
          errs[-1] < errs[len(errs) // 2] < errs[0] and errs[-1] < 1e-6,
          " ".join("%.1e" % e for e in errs))
    check("判据D：基线残差 > 1e-12（非代数恒等反例）",
          abs(cv - ov) > 1e-12, "res=%.2e" % abs(cv - ov))

    # ------------------------------------------------ ④ 反向必被抓
    p2 = dict(sp.params)
    p2["nbar"] = sp.params["nbar"] * 1.1

    class _S:  # 最小 spec shim
        spec_id = "B30"
        params = p2

    cv2 = fn(_S(), ov)
    d2 = abs(cv2 - ov)
    check("反向 nbar+10% 必 FAIL", d2 > float(sp.tol),
          "越界 %.5f ≫ tol %s" % (d2, sp.tol))

    # ------------------------------------------------ H7 N2 登记面双向锁死
    # 只有"真的跑过正向 harness 判决"才登记（放在正向 check 之后复用其结果集）
    _RUNTIME_ASSERTED.append("B30")
    check("H7 声明面 ≡ 运行时断言集（双向锁死）",
          tuple(_RUNTIME_ASSERTED) == tuple(ASSERTED_ANCHORS),
          "声明=%s 运行=%s" % (ASSERTED_ANCHORS, tuple(_RUNTIME_ASSERTED)))
    check("H7 登记的锚确实被判过（防「登记了没跑」）",
          bool(res.passed) and sp.spec_id in ASSERTED_ANCHORS,
          "spec_id=%s passed=%s" % (sp.spec_id, res.passed))

    print("=" * 72)
    if FAIL:
        print(f"B30 quad 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在问题")
        return 1
    print(f"B30 quad 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    return 0


if __name__ == "__main__":
    sys.exit(main())
