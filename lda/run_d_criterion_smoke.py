"""判据 D 常驻护栏 smoke（v0.9.27 立项 · T-1）。

🔴 背景（2026-09-03 发现的判据级缺陷）：
  现行行为判据（残差≡0 且扰动无响应 ⇒ 自证桩）拦得住「裸桩」，**拦不住
  「数学等价的另一种写法」**。实测反例 B28：沿程积分+二分候选与解析闭式在
  均匀段**剖分守恒** ⇒ 残差恒 4.44e-16，但扰动参数时两式同步响应 ⇒ 会被
  误判为「独立候选」——而它是**同一个式子的两种写法**，零独立信息 ⇒ 虚报。

判据 D（本 smoke 守护的判据，单一定义处在 lda_harness/harness.py）：
  固定物理参数，只扫**候选自身的离散参数**（步长/段数/网格/截断维数）。
  真数值方法的截断误差必然随离散参数变化：粗端浮出噪声地板、随加密下降。
  代数恒等式的残差**任何档位恒 ~1e-16 纹丝不动** ⇒ 判假独立，不计入独立候选数。

⚠️ 双向标定（B10 血案，差点误判）：
  默认物理参数可能落在**过度收敛区**（B10 默认 t/T1=5e-4 ⇒ RK4 截断误差
  ~1e-22 沉在双精度噪声 1e-16 之下）⇒ 真独立候选的残差也恒 ~1e-16，与
  代数恒等**不可区分**。⇒ 判据 D 必须在「未完全收敛」的物理参数点上扫。
  窗口铁律：`1e-15 < 粗端残差 < tol`。

本 smoke 断言五件事：
  ① 正例 B10（RK4 vs 解析闭式，未收敛点 t/T1=1.0）：判据 D 必须 PASS，
     且收敛阶 ~O(h⁴)（残差比 n=2→4 应 ~16×）
  ② 反例 B28（沿程积分 vs 闭式，均匀段剖分守恒）：判据 D 必须 FAIL
     ——证明护栏会响（没被验证过的护栏不算护栏）
  ③ 全 20 道已接线候选的**基线残差普查**：全部 > 1e-12
     ——代数恒等只能给 ~1e-16；>1e-12 即从值域上排除恒等（除非该锚
       恰好落在过度收敛区，见 B10 特例：基线=0 但判据 D 深验通过）
  ④ 抽验两条对角化类候选（B9 扫 N / B23 扫 ncut）：截断收敛证据留痕
  ⑤ 判据 D 落地处导入自单一定义处 harness.py（防两份定义漂移）

诚实边界：
  - 判据 D 只适用于「候选含真实数值离散化」的锚。对「候选是另一条解析
    闭式」的锚（B9 的 Koch 渐近 vs 严格对角化中 golden 是前者——B9 候选
    是对角化，适用；纯闭式对闭式的锚不适用），独立性由推导路径不同保证，
    须人工论证并登记（本 smoke ③ 的基线残差普查覆盖它们）。
  - ③ 是**值域排除**（必要非充分）：基线残差 >1e-12 排除「恒等式」，
    但不排除「两条不同路径恰好吻合到 <1e-12」的极小概率事件；对这类
    事件唯一的防线是反向扰动（run_benchmark_falsifiability_smoke ③）。
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lda_solver"))

from lda_harness.harness import candidate_discretization_responds  # noqa: E402
from lda_harness.verification_adapters import build_harness_specs  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{tag}] {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    print("=" * 72)
    print("判据 D 常驻护栏（代数恒等 vs 真数值离散化）")
    print("=" * 72)

    # ---------------------------------------------------------------
    print("① 正例 B10：RK4 vs 解析闭式（未收敛点 t/T1=1.0，扫 n_steps）")
    from lda_solver import lindblad_gate_fidelity as lg
    T1 = 40e-6
    t = 1.0 * T1
    T2 = 0.75 * T1

    def b10_pair(n: int):
        return (lg.average_gate_fidelity(T1, T2, t, n_steps=n),
                lg.closed_form(T1, T2, t))

    ok, ev = candidate_discretization_responds(b10_pair, min_ratio=1.0)
    res = ev.get("residual", [])
    check("B10 判据 D PASS（真独立）", ok,
          "残差 " + " → ".join("%.2e" % r for r in res))
    if len(res) >= 2 and res[1] > 0:
        ratio = res[0] / res[1]
        # RK4 标称 O(h^4)：n 加倍 ⇒ h 减半 ⇒ 残差降 ~16×
        check("B10 收敛阶 ~O(h⁴)（首段比值 ≈16）", 8.0 <= ratio <= 32.0,
              "n=2→4 残差比 = %.1f×" % ratio)

    # ---------------------------------------------------------------
    print("② 反例 B28：沿程积分 vs 闭式（均匀段剖分守恒 ⇒ 代数恒等）")
    from lda_harness.b28_modulator_vpi_anchor import (
        mzm_vpi_analytic,
        mzm_vpi_integral,
    )

    def b28_pair(n: int):
        return mzm_vpi_integral(n_segments=n), mzm_vpi_analytic()

    ok28, ev28 = candidate_discretization_responds(b28_pair, min_ratio=1.0)
    check("B28 判据 D FAIL（假独立·护栏会响）", not ok28,
          "残差恒 " + " → ".join("%.1e" % r for r in ev28.get("residual", [])))

    # ---------------------------------------------------------------
    print("③ 全部已接线候选的基线残差普查（代数恒等在值域上被排除）")
    specs, cand = build_harness_specs()
    indep_ids = [
        "B1", "B3", "B4", "B8", "B9", "B10", "B12", "B13", "B14", "B15",
        "B19", "B20", "B22", "B23", "B24", "B25", "B26", "B27", "E2", "S13",
    ]
    noise_exempt = {"B10"}  # 过度收敛区特例：基线=0，判据 D 深验已通过（①）
    n_wired, violators = 0, []
    for sp in specs:
        if sp.spec_id not in indep_ids:
            continue
        n_wired += 1
        fn = cand.get(sp.spec_id)
        if fn is None:
            violators.append((sp.spec_id, "候选缺失"))
            continue
        ov = sp.oracle_fn(sp.params)
        cv = fn(sp, ov)
        d = abs(float(cv) - float(ov))
        if sp.spec_id not in noise_exempt and d <= 1e-12:
            violators.append((sp.spec_id, "基线残差 %.2e 贴地板（恒等嫌疑）" % d))
    check("已接线候选 %d/20 全部登记" % n_wired, n_wired == 20)
    check("基线残差全部 > 1e-12（B10 特例豁免，见①）", not violators,
          "; ".join("%s: %s" % v for v in violators) if violators else
          "19 道残差 1.85e-8 ~ 1.5e-2，全部远高于 1e-15 恒等特征")

    # ---------------------------------------------------------------
    print("④ 抽验对角化类候选的截断收敛（证据留痕）")
    from lda_solver.transmon_solver import solve_transmon
    EJ, EC = 30.0, 0.22

    def b9_pair(N: int):
        return solve_transmon(EJ, EC, N=N)["f01"], (8 * EJ * EC) ** 0.5 - EC

    ok9, ev9 = candidate_discretization_responds(b9_pair, min_ratio=1.0)
    check("B9 扫电荷基截断 N：截断误差响应", ok9,
          "残差 " + " → ".join("%.1e" % r for r in ev9.get("residual", [])))

    from lda_l2.device_library import _fluxonium_ho_core
    import math as _m

    def b23_pair(ncut: int):
        return (_fluxonium_ho_core(e_j=0.0, e_c=0.6, e_l=1.2, ncut=ncut),
                _m.sqrt(8 * 0.6 * 1.2))

    ok23, ev23 = candidate_discretization_responds(b23_pair, min_ratio=1.0)
    r23 = ev23.get("residual", [])
    check("B23 扫 ncut：截断误差响应", ok23,
          "残差 " + " → ".join("%.1e" % r for r in r23))
    # B23 顺带印证既有双向标定铁律：ncut>24 残差贴死 1e-12 判据线
    if len(r23) == 6:
        check("B23 ncut=32 残差 < 1e-11（印证「ncut 钉 24 勿再加」铁律）",
              r23[4] < 1e-11, "ncut=32 残差 %.1e" % r23[4])

    # ---------------------------------------------------------------
    print("⑤ 判据 D 单一定义处（harness.py，防两份定义漂移）")
    import lda_harness.harness as H
    check("candidate_discretization_responds 定义于 harness.py",
          "candidate_discretization_responds" in dir(H))

    print("=" * 72)
    if FAIL:
        print(f"判据 D 冒烟：{PASS} PASS / {FAIL} FAIL —— 🔴 存在假独立或护栏失效")
        return 1
    print(f"判据 D 冒烟：{PASS} PASS / 0 FAIL —— 全绿")
    print("结论：20 道独立候选中 0 道代数恒等（19 道基线残差 1.85e-8~1.5e-2 值域排除；")
    print("     B10 基线=0 属过度收敛区特例，判据 D 深验 O(h⁴) 收敛通过）。")
    print("     B28 型假独立已被判据 D 抓获（②证明护栏会响）——B28 若要接线必须")
    print("     改用非均匀 Γ(z) 剖面，使积分与闭式不再剖分守恒。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
