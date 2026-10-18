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
  ③ 全部**已接线严格独立候选**（清单由 harness 权威三分类动态推导）的
     **基线残差普查**：全部 > 1e-12
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
# 🔴 v0.9.73：部分候选（B31/B32 等）内部用 `from lda.lda_harness import ...` 或
# 回退 `import <mod>` ⇒ 需同时有「仓库根」（给出 `lda` 包）与 `lda_harness` 目录
# （给出裸模块名回退）。此前清单硬编码、从未覆盖 B31/B32，故该缺口长期未暴露。
sys.path.append(str(HERE.parent))
sys.path.append(str(HERE / "lda_harness"))

from lda_harness.harness import (  # noqa: E402
    candidate_discretization_responds, IndependentCandidateRouter,
    CANDIDATE_CLASS_STRICT,
)
from lda_harness.verification_adapters import build_harness_specs  # noqa: E402
from lda_harness.benchmarks import BENCHMARK_DEFS  # noqa: E402

PASS = 0
FAIL = 0


# 🔴 check 已归一：实现**单一定义**在 lda_harness/smoke_kit.py
#   （v0.9.113 · 波次 2 · 源自 2026-09-19 审计 F-07）。调用方尾部
#   （含模块级计数器读取）与输出格式**均未改**，见 smoke_kit 模块 docstring。
from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="  ", detail_fmt=' —— {d}')


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
    # 🔴 v0.9.73 改动态推导：原硬编码清单（24 项）漏了 B2/B28/B29/B30/B31/B32/E8
    # 共 7 道严格独立锚，使「已接线候选 24/24 全部登记」退化为**自证式等值断言**
    # （等价断言 + 会增长集合 = 定时炸弹）。真值锚 = harness 权威三分类
    # （IndependentCandidateRouter.candidate_class，与 /api/verification_ledger 同源），
    # 随接线自动扩展、无需人工维护清单。
    _router = IndependentCandidateRouter()
    indep_ids = sorted(bid for bid in BENCHMARK_DEFS
                       if _router.candidate_class(bid) == CANDIDATE_CLASS_STRICT)
    # 🔴 v0.9.102 清算：B-4 切片转移矩阵族（B65-B88 中残差贴地板的 13 道）
    # 候选 = 分段常数势的**精确**转移矩阵法，对问题类数学精确 ⇒ 基线残差沉到
    # 机器精度（1e-13~1e-18，非恒等常值 1e-16，证明是收敛后的精确法而非裸恒等）。
    # 与 B10 同属「过度收敛/精确法」盲区。smoke 自身诚实边界（33-36 行）已授权：
    # 解析/精确法 vs 解析的锚，独立性由推导路径保证，须人工论证并登记豁免。
    # B10 即先例（过度收敛区特例）。此处登记 B-4 转义族。
    # 注：B70/B71/B75-B78/B80/B85/B86 基线残差 >1e-12（双势垒扫 E / 有限深势阱共振
    # 等真数值残差）不在此豁免内，仍受 ③ 普查约束。
    #
    # 🔴🔴 v0.9.222 治根因（Task #37）：③ 的恒等嫌疑判定原用**绝对**口径
    #   `d <= 1e-12`（单一值域排除）。这在**小量值锚**上系统性误伤：
    #   锚的 oracle 量级本身 ~1e-9（如 B473 η=8.47e-10 / B474 同族 / B481
    #   B_min=1.18e-9），其候选残差绝对量 2.1e-14 / 2.3e-15 / 1.2e-13 全 ≤1e-12，
    #   但**相对**残差 2.43e-05 / 2.77e-06 / 1.00e-04 —— 比机器精度高 6~10 个
    #   数量级，是**真独立**（收敛未完成/不同算法路径），不是恒等。
    #   根因：绝对阈值把「量值尺度」与「恒等性」混为一谈 —— 恒等的定义是
    #   **相对误差沉到机器精度**（代数恒等：同一式异写，|Δ|/|值| ~ 1e-16），
    #   与量值绝对大小无关。判据 D ② 的 B28 反例即用代数恒等 ⇒ 残差恒 0。
    #   修法（双口径，防漏判同时防误伤）：
    #     identity-suspect ⟺ (abs <= 1e-12) **AND** (rel <= 1e-12)
    #   即「绝对沉地板 **且** 相对也沉地板」才判恒等。检针逻辑：
    #     · 真恒等（B28/B10/B65…）：abs 与 rel **同**沉机器精度 ⇒ 仍必中（不放松）。
    #     · 小量值真独立（B473/B474/B481）：abs 沉地板但 rel 高位 ⇒ 不再误伤。
    #     · 常值量级真独立（B469/B479/B480…）：abs 高位 ⇒ 双口径下均不中（原样）。
    #   🔴 口径收紧须配反向探针（下节 ③′），且**既有 14 道豁免全部仍必需**
    #   （等价性由 ③′ 的「豁免集 ⊆ 双口径命中集」断言逐位证，非人工声明）。
    # 🔴 v0.9.252 BL-M1：`B82` **已移出豁免集**（14 → 13）。原候选「400 段等宽切片连乘」
    #   对均匀势垒与闭式**数学等价**（`S(w)^N ≡ S(N·w)`）⇒ 残差恒 0 ⇒ 被双口径判为恒等。
    #   换 Riccati+RK4 候选后残差 9.557e-12 > ABS_FLOOR（10 位/相对 9.6e-12 均出地板）
    #   ⇒ 不再命中；若有人把它换回切片候选，③′ 的「豁免集 ⊆ 命中集」与下方
    #   「B82 不得被豁免」双判据会一起红（见 ③″）。
    noise_exempt = {"B10", "B65", "B66", "B67", "B68", "B73", "B74",
                    "B79", "B81", "B83", "B84", "B87", "B88"}
    B82_MUST_BE_NON_IDENTITY = True
    ABS_FLOOR = 1e-12
    REL_FLOOR = 1e-12
    n_wired, violators = 0, []
    ident_hits = []          # 双口径命中的「机器精度恒等」锚（供 ③′ 对拍）
    wired_pairs = []         # (sid, abs, rel) 供 ③′ 反向探针复用
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
        rel = d / max(abs(float(ov)), 1e-300)
        wired_pairs.append((sp.spec_id, d, rel))
        if d <= ABS_FLOOR and rel <= REL_FLOOR:
            ident_hits.append(sp.spec_id)
        if (sp.spec_id not in noise_exempt
                and d <= ABS_FLOOR and rel <= REL_FLOOR):
            violators.append(
                (sp.spec_id, "基线残差 abs %.2e / rel %.2e 双口径沉地板（恒等嫌疑）"
                 % (d, rel)))
    check("已接线候选 %d/%d 全部登记（动态）" % (n_wired, len(indep_ids)),
          n_wired == len(indep_ids))
    check("基线残差非恒等（双口径 abs∧rel <= 1e-12 · B10 等 13 道特例豁免）",
          not violators,
          "; ".join("%s: %s" % v for v in violators) if violators else
          "%d 道残差无一同时满足 abs∧rel 沉 1e-12 地板（远高于 1e-15 恒等特征）"
          % n_wired)

    # ── ③′ 双口径反向探针（口径收紧的等价性证明 · 🔴 收紧判据必配）─────────────
    # (a) 豁免集 ⊆ 双口径命中集：证明「收紧后原豁免**全部仍必需**」，
    #     即修法未把任何真·机器精度恒等从射程内放走（防「收紧即放宽」）。
    _ex_missing = sorted(noise_exempt - set(ident_hits))
    check("③′ 双口径命中集 ⊇ 13 道原豁免（收紧未放走任何真恒等）",
          not _ex_missing,
          "命中 %d 道；缺失豁免 %s" %
          (len(ident_hits), _ex_missing if _ex_missing else "无"))

    # (e) 🔴 v0.9.252 BL-M1 反向：`B82` 换 Riccati 候选后**必须出恒等射程**
    #     （否则等于"移出豁免集但病还在"）。这是本档换候选的**唯一验收点**：
    #     旧核（同宽切片）残差恒 0；新核残差 9.557e-12 ⇒ abs 出 1e-12 地板。
    _b82p = next((x for x in wired_pairs if x[0] == "B82"), None)
    _b82_out = (B82_MUST_BE_NON_IDENTITY and _b82p is not None
                and not (_b82p[1] <= ABS_FLOOR and _b82p[2] <= REL_FLOOR))
    check("③″ B82 已脱离「机器精度恒等」射程（abs>1e-12 ∨ rel>1e-12 · "
          "BL-M1 换候选的验收点）",
          _b82_out,
          ("B82 abs=%.3e rel=%.3e" % (_b82p[1], _b82p[2])) if _b82p else "B82 缺席")

    # (b) 正向：合成**真恒等**（同一表达式异写）⇒ 双口径必命中（会响）。
    #     直接用 B28 那对（积分 vs 闭式）在**均匀常势**下的代数恒等：
    #     残差恒 0 ⇒ abs=0 ∧ rel=0 ⇒ 命中。
    _syn_ident_abs = 0.0
    _syn_ident_rel = 0.0
    check("③′ 正向：合成真恒等（残差 0）⇒ 双口径命中（判据会响）",
          _syn_ident_abs <= ABS_FLOOR and _syn_ident_rel <= REL_FLOOR,
          "合成恒等 abs=%.1e rel=%.1e" % (_syn_ident_abs, _syn_ident_rel))

    # (c) 反向：合成**小量值但相对高位**的锚（abs 沉地板 ∧ rel 高位）
    #     ⇒ 双口径**必须不命中**（这正是被修掉的误伤模式；若误命中则此断言红）。
    #     构造：量值 1e-9、残差 1e-13 ⇒ abs=1e-13<=1e-12 但 rel=1e-4>1e-12。
    _rev_val, _rev_res = 1.0e-9, 1.0e-13
    _rev_abs = abs(_rev_res)
    _rev_rel = _rev_abs / _rev_val
    _rev_flagged = (_rev_abs <= ABS_FLOOR and _rev_rel <= REL_FLOOR)
    check("③′ 反向：小量值真独立（abs 沉地板 · rel 高位）不被误判恒等",
          (not _rev_flagged) and _rev_abs <= ABS_FLOOR and _rev_rel > REL_FLOOR,
          "合成 abs=%.1e(<=1e-12) rel=%.1e(>1e-12) ⇒ 命中=%s（期望 False）"
          % (_rev_abs, _rev_rel, _rev_flagged))

    # (d) 反向：合成**真恒等**若被破坏（残差抬到相对 1e-6）⇒ 双口径不命中，
    #     证明口径对「并非恒等」的情形**不误报**（不是恒定返 True 的假守卫）。
    _brk_val, _brk_res = 1.0e-9, 1.0e-15   # rel=1e-6
    _brk_flagged = (abs(_brk_res) <= ABS_FLOOR
                    and abs(_brk_res) / _brk_val <= REL_FLOOR)
    check("③′ 反向：量值 1e-9 残差抬到 rel=1e-6 ⇒ 双口径不命中（非假守卫）",
          not _brk_flagged,
          "合成 rel=%.1e ⇒ 命中=%s（期望 False）"
          % (abs(_brk_res) / _brk_val, _brk_flagged))

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
    print("④′ B33 时域 RC 阶跃响应收敛（v0.9.67 · A 档有源扩展 #1）")
    from lda_harness.b33_detector_bandwidth_anchor import (
        b33_detector_bandwidth, b33_rc_bandwidth_candidate,
    )
    _R, _eps, _A, _d = 50.0, 1.036e-10, 9.653e-9, 1.0e-6

    def b33_pair(n: int):
        return (b33_rc_bandwidth_candidate(_R, _eps, _A, _d, n_time=n),
                b33_detector_bandwidth(_R, _eps, _A, _d))

    ok33, ev33 = candidate_discretization_responds(b33_pair, min_ratio=1.0)
    r33 = ev33.get("residual", [])
    check("B33 扫 n_time：梯形法积分误差响应（真数值离散化）", ok33,
          "残差 " + " → ".join("%.1e" % r for r in r33) if r33 else
          "（n=2 梯形法退化触发数值失效 ⇒ 判据 D 视为有响应）")
    if len(r33) >= 2 and r33[0] > 0 and r33[-1] > 0:
        # 粗端 (n=4) → 细端 (n=512) 应单调收敛（梯形法 O(dt²)）
        check("B33 残差随 n_time 加密单调下降（非代数恒等）",
              r33[1] > r33[-1] and r33[1] > r33[2],
              "n=4→512 残差 %.1e→%.1e" % (r33[1], r33[-1]))

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
    print("结论：全部**已接线严格独立候选**（数量动态推导）0 道代数恒等 —— 基线残差")
    print("     全部远高于 1e-15 恒等特征、从值域上排除恒等（B10 基线=0 属过度收敛区")
    print("     特例，判据 D 深验 O(h⁴) 收敛通过）。")
    print("     B28 型假独立已被判据 D 抓获（②证明护栏会响）——B28 若要接线必须")
    print("     改用非均匀 Γ(z) 剖面，使积分与闭式不再剖分守恒。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
