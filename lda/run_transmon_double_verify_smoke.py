"""LDA L2 · transmon 真实数值物理双验证 smoke（量子域实质推进：Koch ↔ 严格对角化）。

与光子栈 run_ring_double_verify_smoke.py 同构：量子侧用「Koch 解析近似 ↔
Josephson 电路严格数值对角化」两种独立路径交叉验证 f01，零 GPU、纯 numpy
（维度 ≤41）、LLM 不进判决路径。

退出码 0=全绿；非 0=有失败（便于 CI / 自动化）。
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_l2"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_solver"))

from device_library import DeviceLibrary  # noqa: E402


# ===========================================================================
# N2 · 超导域判据深度：门禁运行时登记（v0.9.282）
# ---------------------------------------------------------------------------
# 本门禁**真的执行**账本锚（harness 统一判决：闭式 golden vs 已注册候选），
# 不是"为刷覆盖写锚号"（见 N2 规划 §1.3 的反例）。
# 登记面走 `asserted_anchor_ids()`（scripts/gate_manifest.py 消费），
# 由末尾 H7 **双向锁死**：声明集 ≡ 本次运行实际断言集 ⇒ 删掉执行代码必红。
# 🔴 本段只用 print + 退出码，**不增加门禁判据数**（护住 `run_webui_*` 的
#    「N PASS == span.gate_checks」自洽判据）。
# ===========================================================================
ASSERTED_ANCHORS = ('B9',)
_RUNTIME_ASSERTED: list = []


def asserted_anchor_ids():
    """本门禁运行时实际断言的锚集（未运行则回落到声明面）。"""
    return tuple(_RUNTIME_ASSERTED) or tuple(ASSERTED_ANCHORS)


def _run_ledger_anchor(bid):
    """真跑一条账本锚（golden 与已注册候选均由 harness 解析）。"""
    from lda_harness.verification_adapters import build_harness_specs
    from lda_harness.verification_spec import run_verification
    specs, cand = build_harness_specs()
    sp = [s for s in specs if s.spec_id == bid][0]
    ov = sp.oracle_fn(sp.params)
    cv = cand[bid](sp, ov)
    return sp, run_verification(sp, cand[bid], oracle_value=ov), float(cv), float(ov)


def main() -> int:
    lib = DeviceLibrary()
    print("=== Transmon 双验证 (Koch 解析 ↔ 严格对角化) ===")

    # contract：Koch 量级物理 + 目标反解可达
    c = lib.verify_transmon(mode="contract")
    print(f"contract: passed={c['passed']} | {c['verdict']}")

    # live：B9 Koch 命中 + 严格对角化自洽
    r = lib.verify_transmon(mode="live")
    ac = r["analytic_contract"]
    num = r["numerical"]
    print(f"live: passed={r['passed']}")
    print(f"  B9 解析契约: target={ac['target_f01_ghz']}GHz -> E_J={ac['ej_hit']} "
          f"(in_bounds={ac['ej_in_bounds']}, hit_err={ac['b9_hit_err']})")
    print(f"  真实对角化: f01_diag={num['f01_diag']}GHz <-> Koch={num['f01_koch']}GHz "
          f"rel={num['rel_err']:.4%} (tol {num['tol_rel']:.0%}, accepted={num['accepted']})")
    print(f"  anharmonicity: diag={num['alpha_diag']} vs -E_C={num['alpha_koch']} "
          f"(rel {num['alpha_rel_err']:.2%}, informational)")
    print(f"  levels_ghz={num['levels_ghz']}")
    print(f"verdict: {r['verdict']}")

    # ── N2（v0.9.282）：账本锚真跑 + 运行时登记（H7 双向锁死）──
    _sp, _res, _cv, _ov = _run_ledger_anchor('B9')
    if bool(_res.passed):
        _RUNTIME_ASSERTED.append('B9')
    _h7 = tuple(_RUNTIME_ASSERTED) == tuple(ASSERTED_ANCHORS)
    print("  [%s] 账本锚 %s 真跑：残差=%.3e tol=%s"
          % ("PASS" if _res.passed else "FAIL", 'B9',
             abs(_cv - _ov), _sp.tol))
    print("  [%s] H7 声明面 ≡ 运行时断言集 —— 声明=%s 运行=%s"
          % ("PASS" if _h7 else "FAIL", ASSERTED_ANCHORS, tuple(_RUNTIME_ASSERTED)))
    _n2_ok = bool(_res.passed) and _h7
    ok = bool(c["passed"] and r["passed"]) and _n2_ok
    print("\n=== Transmon 双验证 smoke: " + ("ALL GREEN" if ok else "FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
