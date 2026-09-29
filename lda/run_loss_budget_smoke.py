"""真实损耗预算 门禁 smoke（D-123 · M5 延伸：**把「每模光学深度」接进 dB 账**）。

═══ 为什么要有这个 smoke ═══
D-123 是量子征程里第一块**把网格深度兑现成损耗 dB**的模块，它给出一条极易被后人
"改回好看数字"的口径结论，必须钉成常驻断言：

  ① **列口径 ≠ 每模口径**：D-120 `mesh_scaling_laws.n_stages = N−1` 是**列/阶段数**
     （对 `reck_decompose` 抽象网格恰好 = 每模深度），但平台**邻耦合三角网格**
     （M1/M2 实测 0 交叉）的**每模光学深度 = 2N−3**（同一列内相邻对共享模 = 链）。
     有人把 `(N−1)·per` 当三角网格的真实每模损耗 ⇒ 低估约 2× ⇒ 必须变红。
  ② **M5 的收益在真实 dB 账上兑现**：矩形（Clements）每模深度 max = **N**
     ⇒ N=216 三角 1029.6 dB → 矩形 518.4 dB（省 511.2）；而元件数**不变**
     （两种网格同为 N(N−1)/2）⇒ 收益纯在深度。有人写成"矩形更省元件" ⇒ 变红。
  ③ **通用仍不省损，浅电路才越墙**：通用时间复用（矩形调度 N）561.6 dB
     —— 优于三角静态、但贵于矩形静态 43.2 dB（= N·延迟）⇒ D-121 结论 3 在
     **可达基线 N** 上成立；只有浅电路（D=32 ⇒ 83.2 dB）越墙但**非通用**。

═══ 判什么（分六节 · 27 条）═══
A 每模深度口径 5 · B M5 接进 dB 账 5 · C 时间复用对比 7 ·
D 诚实标注+红线 4 · E 护栏 3 · F 与 D-120/D-121/D-122 口径一致性 3。

运行：python run_loss_budget_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from lda_qeda import loss_budget as LB
    from lda_qeda import temporal_mesh as TMB
    from lda_qeda import rect_mesh as RMB
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import loss_budget as LB                             # noqa: E402
    import temporal_mesh as TMB                          # noqa: E402
    import rect_mesh as RMB                              # noqa: E402

from lda_qeda import scale_bench as SBM                  # noqa: E402
from lda_harness.smoke_kit import make_check             # noqa: E402

# 计数写进模块命名空间；助手复用公共 `smoke_kit`，不另建局部 `def check`
# （防「助手重复棘轮」劣化 · **名字在前**！写反成 check(cond, name) ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("真实损耗预算 门禁 smoke（D-123 · M5 延伸：每模光学深度接进 dB 账）")
    print("=" * 78)

    # ════════════════ A 节：每模深度口径（构造 vs 闭式）════════════════
    print("── A 每模光学深度口径（列口径 vs 每模口径）──")
    try:
        ok_a = LB.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_a = False
        print(f"  损耗预算模块自检异常：{type(e).__name__}: {e}")
    check("A1 损耗预算模块自检 14/14 PASS", ok_a,
          "每模深度三网格/口径区分/M5收益/元件数/时间复用/下界/交叉敏感性/下界≠可达/护栏/无LLM")

    # 抽象 Reck（reck_decompose）每模深度 = N−1（列口径来源）
    ok_a2 = True
    detail_a2 = []
    for n_ in (4, 8, 16, 64):
        d = LB.abstract_reck_optical_depth(n_)
        detail_a2.append(f"N={n_}:{d['per_mode_max']}")
        if not (d["per_mode_max"] == n_ - 1 and d["closed_form_ok"]
                and d["needs_crossings"] is True):
            ok_a2 = False
    check("A2 抽象 Reck（reck_decompose·需交叉）每模深度 = N−1 ⇒ D-120 列口径有据",
          ok_a2, " · ".join(detail_a2))

    # ★ 三角（邻耦合）每模深度 = 2N−3（构造实测），且 ≠ 列数 N−1
    ok_a3 = True
    detail_a3 = []
    for n_ in (4, 5, 8, 16, 32, 64):
        d = LB.triangular_optical_depth(n_)
        detail_a3.append(f"N={n_}:{d['n_columns']}→{d['per_mode_max']}")
        if not (d["per_mode_max"] == 2 * n_ - 3 and d["per_mode_min"] == 1
                and d["n_columns"] == n_ - 1 and d["per_mode_max"] != d["n_columns"]
                and d["closed_form_ok"] and d["needs_crossings"] is False):
            ok_a3 = False
    check("A3 ★口径★ 三角邻耦合（0 交叉）每模深度 = 2N−3 ≠ 列数 N−1（构造实测）",
          ok_a3, " · ".join(detail_a3))

    # ★ 矩形（M5）每模深度 = N · min = ⌊N/2⌋ · 每层真匹配
    ok_a4 = True
    detail_a4 = []
    for n_ in (4, 5, 8, 16, 32, 64):
        d = LB.rectangular_optical_depth(n_)
        detail_a4.append(f"N={n_}:d={d['n_layers']}/max={d['per_mode_max']}")
        if not (d["per_mode_max"] == n_ and d["per_mode_min"] == n_ // 2
                and d["n_layers"] == n_ and d["layers_are_matchings"]
                and d["closed_form_ok"]):
            ok_a4 = False
    check("A4 ★M5★ 矩形每模深度 max = N · min = ⌊N/2⌋ · 每层真匹配（构造实测）",
          ok_a4, " · ".join(detail_a4))

    # 元件数不变（两种网格同为 N(N−1)/2）
    ok_a5 = True
    for n_ in (4, 16, 64, 216):
        if not (LB.triangular_optical_depth(n_)["n_mzi"] == n_ * (n_ - 1) // 2
                and LB.rectangular_optical_depth(n_)["n_mzi"] == n_ * (n_ - 1) // 2):
            ok_a5 = False
    check("A5 元件数不变：三角/矩形同为 N(N−1)/2（Clements 必要性定理）",
          ok_a5, "N=4/16/64/216 逐点核验")

    # ════════════════ B 节：M5 接进 dB 账 ════════════════
    print("── B ★M5 矩形接进真实 dB 账★──")
    tri216 = LB.static_mesh_loss_budget(216, mesh="tri")
    rect216 = LB.static_mesh_loss_budget(216, mesh="rect")
    check("B1 ★核心★ N=216 最坏模损耗：三角 (2N−3)·per=1029.6 → 矩形 N·per=518.4",
          abs(tri216["loss_per_mode_max_db"] - 429 * LB.PER_MZI_LOSS_DB) < 1e-9
          and abs(rect216["loss_per_mode_max_db"] - 216 * LB.PER_MZI_LOSS_DB) < 1e-9
          and rect216["depth_max"] == 216 and tri216["depth_max"] == 429,
          f"省 {tri216['loss_per_mode_max_db']-rect216['loss_per_mode_max_db']:.1f} dB"
          f"（= (N−3)·per_mzi）")

    # 列口径低估（血案护栏）
    col216 = LB.column_basis_loss(216)
    check("B2 ★口径血案★ D-120 列口径 516.0 dB 低估三角真账 1029.6 dB（差 513.6）",
          col216["n_stages"] == 215
          and abs(tri216["loss_per_mode_max_db"] - col216["loss_per_mode_db"] - 513.6) < 1e-6,
          "把 (N−1)·per 当邻耦合三角网格的每模损耗 ⇒ 低估约 2× ⇒ 必须变红")

    # 账表 5 行自洽
    tab = LB.loss_account_table(216)
    ok_b3 = (len(tab["rows"]) == 5
             and abs(tab["rect_vs_tri_saving_db"] + 511.2) < 1e-6
             and abs(tab["rect_vs_temporal_saving_db"] + 43.2) < 1e-6)
    check("B3 账表 5 行自洽：矩形省三角 511.2 dB · 矩形省时间复用 43.2 dB",
          ok_b3, f"rows={len(tab['rows'])}")

    # 每模深度闭式核对（构造 = 闭式）
    ok_b4 = True
    for n_ in (4, 8, 32, 64):
        if not (LB.triangular_optical_depth(n_)["closed_form_ok"]
                and LB.rectangular_optical_depth(n_)["closed_form_ok"]):
            ok_b4 = False
    check("B4 每模深度闭式核对：三角 max=2N−3/min=1 · 矩形 max=N/min=⌊N/2⌋",
          ok_b4, "构造实测 ≡ 闭式（非仿真、非拟合）")

    # 透射率闭式 η = 10^(−dB/10)
    eta = rect216["per_mode_eta_at_max_loss"]
    check("B5 透射率闭式 η = 10^(−dB/10)：矩形 N=216 ⇒ η=1.45e−52",
          abs(eta - 10.0 ** (-518.4 / 10.0)) < 1e-60 and 1e-53 < eta < 1e-51,
          f"η={eta:.2e}")

    # ════════════════ C 节：时间复用对比 ════════════════
    print("── C 时间复用（通用 / 浅电路）对比 ──")
    tm_rect = LB.temporal_universal_loss_budget(216, schedule="rect")
    tm_reck = LB.temporal_universal_loss_budget(216, schedule="reck")
    check("C1 时间复用通用：矩形调度深度 N=216 ⇒ 561.6 dB · Reck 调度 2N−3=429 ⇒ 1115.4",
          tm_rect["depth"] == 216 and abs(tm_rect["loss_per_mode_db"] - 561.6) < 1e-6
          and tm_reck["depth"] == 429 and abs(tm_reck["loss_per_mode_db"] - 1115.4) < 1e-6,
          "= 深度 × per_step(2.6)")

    pen = tm_rect["loss_per_mode_db"] - rect216["loss_per_mode_max_db"]
    check("C2 ★通用不省损★ 时间复用(矩形调度) 贵于矩形静态 43.2 dB = N·延迟(0.2)",
          abs(pen - 216 * LB.DELAY_LOSS_DB) < 1e-9 and pen > 0.0,
          "D-121 结论 3 在**可达基线 N**（非不可达 N−1）上成立")

    check("C3 时间复用（矩形调度）优于三角静态（561.6 < 1029.6）——继承矩形化收益",
          tm_rect["loss_per_mode_db"] < tri216["loss_per_mode_max_db"],
          f"省 {tri216['loss_per_mode_max_db']-tm_rect['loss_per_mode_db']:.1f} dB")

    sh32 = LB.temporal_shallow_loss_budget(216, 32)
    check("C4 ★浅电路越墙★ D=32 ⇒ 83.2 dB（越损墙）但参数 3456 ≪ 23220 ⇒ 非通用",
          abs(sh32["loss_per_mode_db"] - 83.2) < 1e-6 and sh32["universal"] is False
          and sh32["reachable_params"] == 3456,
          f"省 {rect216['loss_per_mode_max_db']-sh32['loss_per_mode_db']:.1f} dB 但放弃通用性")

    fl = LB.universality_loss_floor(216)
    check("C5 通用性每模损耗下界 = 矩形静态 N·per = 518.4 dB（跨四实现取最小）",
          fl["floor_kind"] == "rect_static"
          and abs(fl["floor_db"] - 216 * LB.PER_MZI_LOSS_DB) < 1e-9,
          f"候选={[f'{k}:{v:.0f}' for k, v in fl['candidates_db'].items()]}")

    eq = LB.equal_loss_frontier(216)
    check("C6 等损耗前沿：同预算时间复用浅电路参数 = 93% 矩形通用 ⇒ 仍非通用（维度计数判死）",
          eq["temporal_universal_at_equal_loss"] is False
          and 0.9 < eq["param_fraction_vs_rect"] < 1.0,
          f"depth={eq['temporal_depth_at_equal_loss']} 参数={eq['temporal_reachable_params']}")

    # ★下界≠可达★ D=N−1 参数口径"够"但紧界未达 ⇒ 不通用（与 D-121/D-122 同一条紧界）
    sh215 = LB.temporal_shallow_loss_budget(216, 215)
    sh216 = LB.temporal_shallow_loss_budget(216, 216)
    check("C7 ★下界≠可达★ 浅电路 D=N−1：参数口径够(23220)但紧界未达 ⇒ 不通用（D≥N 才通用）",
          sh215["parametric_universal"] is True and sh215["achievable_universal"] is False
          and sh215["universal"] is False and sh216["universal"] is True
          and sh215["tight_universal_depth"] == 216,
          "紧界口径复用 D-121 tight_depth_lower_bound（单一口径）")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = LB.RED_LINE_DISCLOSURE
    check("D1 诚实边界齐备：口径区分 / 复用而非重造 / golden / 主权 / 边界",
          all(k in disc for k in ("role", "basis_separation", "reuse_not_reinvent",
                                  "golden", "sovereignty", "honest_boundary"))
          and "设计预算口径" in disc.get("honest_boundary", ""),
          f"键={sorted(disc)}")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    src = open(os.path.join(_HERE, "lda_qeda", "loss_budget.py"), encoding="utf-8").read()
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D2 红线：D-123 零量子 SDK 依赖（纯 numpy + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")

    v = LB.loss_budget_verdict(216)
    check("D3 判决无 LLM：深度/参数为 int · 损耗为 float · 判决位为 bool（死标量）",
          isinstance(v["n_modes"], int) and isinstance(v["rect_static_loss_db"], float)
          and isinstance(v["temporal_still_worse_than_rect_static"], bool),
          "零模型调用")

    cb = LB.crossing_breakeven(216)
    check("D4 交叉缺口如实披露：不含交叉损耗 · 含敏感性（抹平需 ≈1e4 交叉/模）",
          rect216["crossing_loss_included"] is False
          and cb["breakeven_crossings_per_mode"] > 9000.0
          and "交叉" in disc.get("honest_boundary", ""),
          f"breakeven={cb['breakeven_crossings_per_mode']:.0f} 交叉/模")

    # ════════════════ E 节：护栏 ════════════════
    print("── E 护栏（非法输入必须抛错）──")
    guard = True
    for bad in ((lambda: LB.triangular_optical_depth(1)),
                (lambda: LB.rectangular_optical_depth(0)),
                (lambda: LB.static_mesh_loss_budget(8, mesh="rect", per_mzi_db=-0.1)),
                (lambda: LB.temporal_universal_loss_budget(8, schedule="nope")),
                (lambda: LB.temporal_shallow_loss_budget(8, 0)),
                (lambda: LB.optical_depth_profile(8, mesh="unknown")),
                (lambda: LB.loss_wall_n_per_mode(1.5))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    check("E1 护栏：非法 N / 负 per_mzi / 未知 mesh / 未知调度 / depth<1 / 非法阈值",
          guard, "七类非法输入全抛 ValueError")

    # 反证：mesh 参数真的生效（rect ≠ tri），防"恒返回同一常量"
    d_rect = LB.rectangular_optical_depth(16)["per_mode_max"]
    d_tri = LB.triangular_optical_depth(16)["per_mode_max"]
    d_abs = LB.abstract_reck_optical_depth(16)["per_mode_max"]
    check("E2 反证：mesh 参数生效 —— 三网格每模深度互不相同（16/29/15 @N=16）",
          d_rect == 16 and d_tri == 29 and d_abs == 15,
          f"rect={d_rect} · tri={d_tri} · abstract={d_abs}")

    # 反证：per_mzi_db 参数生效（单调）
    l0 = LB.static_mesh_loss_budget(16, mesh="rect", per_mzi_db=0.0)["loss_per_mode_max_db"]
    l1 = LB.static_mesh_loss_budget(16, mesh="rect", per_mzi_db=2.0)["loss_per_mode_max_db"]
    check("E3 反证：per_mzi_db 参数生效（per=0 ⇒ 损耗 0；per=2 ⇒ 32 dB @N=16）",
          abs(l0) < 1e-12 and abs(l1 - 32.0) < 1e-9,
          "零损耗 / 单调，证明非硬编码")

    # ════════════════ F 节：与 D-120 / D-121 / D-122 口径一致性 ════════════════
    print("── F 与 D-120 / D-121 / D-122 口径一致性 ──")
    check("F1 复用而非重造：per_mzi == D-120 · per_step(2.6) == D-121 · per 同源",
          abs(LB.PER_MZI_LOSS_DB - SBM.PER_MZI_LOSS_DB) < 1e-12
          and abs(LB.PER_STEP_LOSS_DB - TMB.PER_ROUNDTRIP_LOSS_DB) < 1e-12
          and abs(LB.DELAY_LOSS_DB - TMB.DELAY_LOSS_DB) < 1e-12,
          "单一口径，不另建常数")

    check("F2 列口径 == D-120 mesh_scaling_laws.loss_per_path_db（不另算）",
          abs(col216["loss_per_mode_db"] - SBM.mesh_scaling_laws(216)["loss_per_path_db"]) < 1e-9,
          f"{col216['loss_per_mode_db']:.1f} dB")

    # 三角每模深度 2N−3 ≡ D-121 浅调度深度（两条独立推导互证）+ 矩形深度 ≡ D-122
    ok_f3 = True
    detail_f3 = []
    for n_ in (4, 8, 16, 64):
        sh = TMB.temporal_shallow_profile(n_, target="dft")
        d_tri_ = LB.triangular_optical_depth(n_)["per_mode_max"]
        d_rect_ = RMB.rect_mesh_profile(n_, target="dft")["depth"]
        detail_f3.append(f"N={n_}:tri{d_tri_}=sh{sh['shallow_depth']}/rect{d_rect_}")
        if not (d_tri_ == sh["shallow_depth"] == 2 * n_ - 3
                and d_rect_ == LB.rectangular_optical_depth(n_)["per_mode_max"] == n_):
            ok_f3 = False
    check("F3 跨模块互证：三角每模深度 ≡ D-121 浅调度(2N−3) · 矩形深度 ≡ D-122",
          ok_f3, " · ".join(detail_f3))

    print()
    print(f"真实损耗预算 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
