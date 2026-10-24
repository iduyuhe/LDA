"""D-88 QEDA 求解器级补强 smoke：3 例（标准工作点 + 不同参数 + 色散区失效负例）。

运行：python run_qubit_resonator_smoke.py（managed python，纯 numpy）
"""
import sys
sys.path.insert(0, ".")

from lda_agent.qubit_resonator_design import design_qubit_resonator  # noqa: E402


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
ASSERTED_ANCHORS = ('B12',)
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
    cases = []



    def run(name, fn, expect_ok):
        try:
            r = fn()
            ok = bool(r.get("ok")) and bool(r.get("acceptance", {}).get("passed"))
            status = "PASS" if ok == expect_ok else "FAIL"
            cases.append((name, status, ok,
                          r.get("verdict", r.get("error", ""))[:110]))
        except Exception as e:  # noqa: BLE001
            status = "PASS" if (not expect_ok) else "FAIL"
            cases.append((name, status, False, f"异常: {str(e)[:80]}"))


    # 1) 正例：标准 transmon 工作点（f_q=5.0, α=-0.3, f_r=f_q+1.0, g=0.1, κ=0.005）
    run("正例-标准工作点", lambda: design_qubit_resonator(
        f_q=5.0, alpha=-0.3, f_r=6.0, g=0.1, kappa=0.005), True)

    # 2) 正例：不同参数（Δ=0.8 失谐更近、耦合更弱 g=0.08）仍过
    run("正例-不同参数", lambda: design_qubit_resonator(
        f_q=5.2, alpha=-0.25, f_r=6.0, g=0.08, kappa=0.01), True)

    # 3) 负例：色散区失效（Δ/g=2 < 5，强耦合区三能级解析近似不适用）→ 优雅 FAIL
    run("负例-色散区失效", lambda: design_qubit_resonator(
        f_q=5.0, alpha=-0.3, f_r=5.2, g=0.1, kappa=0.005), False)

    # ── N2（v0.9.282）：账本锚真跑 + 运行时登记（H7 双向锁死）──
    _sp, _res, _cv, _ov = _run_ledger_anchor('B12')
    if bool(_res.passed):
        _RUNTIME_ASSERTED.append('B12')
    _h7 = tuple(_RUNTIME_ASSERTED) == tuple(ASSERTED_ANCHORS)
    print("  [%s] 账本锚 %s 真跑：残差=%.3e tol=%s"
          % ("PASS" if _res.passed else "FAIL", 'B12',
             abs(_cv - _ov), _sp.tol))
    print("  [%s] H7 声明面 ≡ 运行时断言集 —— 声明=%s 运行=%s"
          % ("PASS" if _h7 else "FAIL", ASSERTED_ANCHORS, tuple(_RUNTIME_ASSERTED)))
    _n2_ok = bool(_res.passed) and _h7
    all_pass = all(c[1] == "PASS" for c in cases) and _n2_ok
    for name, status, ok, verdict in cases:
        print(f"[{status}] {name}: ok={ok}")
        print(f"      {verdict}")
    print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
          f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
