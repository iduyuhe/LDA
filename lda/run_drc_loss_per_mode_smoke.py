"""DRC 损耗每模口径 门禁 smoke（D-124 · 把「每模口径」接进 D-118 `QDR-LOSS-BUDGET`）。

═══ 为什么要有这个 smoke ═══
D-124 把 D-118 的损耗判据从「总级联口径」升级为**两口径并行**（新增**每模口径**）。
这类「口径升级」最容易在半年后被改回好看样子，必须钉成常驻断言：

  ① **每模深度 ≠ 门的总片数**：每模深度 = max over 模 of（触及该模的门片数）——
     三角网格为 **2N−3**，而门总片数是 **N(N−1)/2**（N=8：13 vs 28）。有人用
     `len(ops)` 冒充每模深度 ⇒ 三角网格会把 2N−3 报成 N(N−1)/2 ⇒ 必须变红。
  ② **每模口径严格于总级联口径**（默认限值）：N=5 在总口径下合法（10 门 ×2.4 = 24 ≤ 25），
     但在每模口径下拒绝（深度 7 ×2.4 = 16.8 > 15）⇒ 判定迁移（★重判更严★）。
  ③ **既有参考设计不误伤**：N=4 两口径皆合法（14.4 / 12）⇒ ACCEPT 不变（无假阳）。
  ④ **限值是设计规则**（可覆盖 · 非实测 golden）：收紧 10 dB ⇒ N=4 也拒绝；
     放宽 20 dB ⇒ 通过。同预算下**矩形网格可签更大的 N**（深度 N < 2N−3）。

═══ 判什么（分六节 · 25 条）═══
A 每模深度口径 5 · B 两口径判据 5 · C 限值/灵敏度/收益 5 ·
D 诚实标注+红线 4 · E 护栏+反证 3 · F 跨模块同源 3。

运行：python run_drc_loss_per_mode_smoke.py（cwd=lda/）
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
    from lda_qeda import quantum_drc_lvs as QDR
    from lda_qeda import loss_budget as LB
    from lda_qeda import rect_mesh as RMB
    from lda_qeda import temporal_mesh as TMB
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import quantum_drc_lvs as QDR                        # noqa: E402
    import loss_budget as LB                             # noqa: E402
    import rect_mesh as RMB                              # noqa: E402
    import temporal_mesh as TMB                          # noqa: E402

from lda_l2 import mzi_mesh_matmul as MMM                # noqa: E402
from lda_qeda import scale_bench as SBM                  # noqa: E402
from lda_harness.smoke_kit import make_check             # noqa: E402

# 计数写进模块命名空间；助手复用公共 `smoke_kit`，不另建局部 `def check`
# （防「助手重复棘轮」劣化 · **名字在前**！写反成 check(cond, name) ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)

LIM_PM = QDR.DEFAULT_DRC_LIMITS["max_loss_per_mode_db"]      # 15.0
LIM_TOT = QDR.DEFAULT_DRC_LIMITS["max_loss_db"]              # 25.0


def _tri_ops(n):
    return MMM.reck_triangular_mesh(MMM.dft_matrix(n))[0]


def _rect_flat(n):
    """矩形（Clements）网格展平为 3 元组 (j, θ, φ)。"""
    layers, _D = RMB.rectangular_mesh_layers(MMM.dft_matrix(n))
    return [(int(j), float(t), float(p)) for L in layers for (j, t, p) in L]


def main() -> int:
    print("=" * 78)
    print("DRC 损耗每模口径 门禁 smoke（D-124 · QDR-LOSS-BUDGET 两口径）")
    print("=" * 78)

    # ════════════════ A 节：每模深度口径 ════════════════
    print("── A 每模光学深度（由提交的 ops 直接数出 · mesh-agnostic）──")
    try:
        ok_a = QDR.run_selfchecks(verbose=False)
    except Exception as e:                                # noqa: BLE001
        ok_a = False
        print(f"  D-118 自检异常：{type(e).__name__}: {e}")
    check("A1 D-118 模块自检 11/11 PASS（含 ★重判更严★ 与限值可覆盖）", ok_a,
          "双路装配/零扰动/量化/噪声/九规则/阈值/反自证桩/护栏/⑩迁移/⑪可覆盖")

    ok_a2 = True
    detail_a2 = []
    for n_ in (4, 5, 8, 16, 32):
        d = QDR.per_mode_optical_depth(_tri_ops(n_))
        detail_a2.append(f"N={n_}:{d}")
        if d != 2 * n_ - 3:
            ok_a2 = False
    check("A2 三角（邻耦合）每模深度 = 2N−3（由 ops 数出，构造实测）", ok_a2, " · ".join(detail_a2))

    ok_a3 = True
    detail_a3 = []
    for n_ in (4, 5, 8, 16):
        d = QDR.per_mode_optical_depth(_rect_flat(n_))
        detail_a3.append(f"N={n_}:{d}")
        if d != n_:
            ok_a3 = False
    check("A3 矩形（Clements·M5）每模深度 = N（由 ops 数出）", ok_a3, " · ".join(detail_a3))

    ops4 = _tri_ops(4)
    o4 = [(c, p, th, ph) for (c, p, th, ph) in ops4]
    o3 = [(p, th, ph) for (c, p, th, ph) in ops4]
    check("A4 形态无关：4 元组 (c,p,θ,φ) 与 3 元组 (j,θ,φ) 对同网格给出同深度",
          QDR.per_mode_optical_depth(o4) == QDR.per_mode_optical_depth(o3) == 5,
          f"4元组={QDR.per_mode_optical_depth(o4)} · 3元组={QDR.per_mode_optical_depth(o3)}")

    ops8 = _tri_ops(8)
    check("A5 ★深度 ≠ 门总片数★ N=8：每模深度 13（=2N−3）≠ 门总片数 28（=N(N−1)/2）",
          QDR.per_mode_optical_depth(ops8) == 13 and len(ops8) == 28
          and QDR.per_mode_optical_depth(o4) == 5 and len(o4) == 6,
          "用 len(ops) 冒充会把三角深度 2N−3 报成 N(N−1)/2（两口径真不同）")

    # ════════════════ B 节：两口径判据 ════════════════
    print("── B QDR-LOSS-BUDGET 两口径判据 ──")

    def drc(n, ops=None, **kw):
        d = {"ops": ops if ops is not None else _tri_ops(n), "N": n, "n_crossings": 0}
        return QDR.run_quantum_drc(d, **kw)

    d6 = drc(6)
    det6 = [v["detail"] for v in d6["violations"] if v["rule"] == "QDR-LOSS-BUDGET"]
    check("B1 总级联口径仍在：N=6（15 门 ×2.4 = 36 dB > 25）⇒ REJECT 且 detail 标口径",
          d6["verdict"] == "REJECT"
          and any("总级联口径" in x for x in det6),
          f"detail={det6[:1]}")

    d5 = drc(5)
    det5 = [v["detail"] for v in d5["violations"] if v["rule"] == "QDR-LOSS-BUDGET"]
    check("B2 每模口径新增：N=5（深度 7 ×2.4 = 16.8 dB > 15）⇒ REJECT 且 detail 标口径",
          d5["verdict"] == "REJECT" and len(det5) == 1
          and "每模口径" in det5[0] and "光学深度 7" in det5[0],
          f"detail={det5}")

    check("B3 ★核心·重判更严★ N=5：总级联口径 24 dB ≤ 25 通过、每模口径 16.8 dB > 15 拒绝",
          MMM.mesh_cascade_loss_db(10, n_crossings=0) <= LIM_TOT
          and 7 * LB.PER_MZI_LOSS_DB > LIM_PM and d5["verdict"] == "REJECT",
          "同一设计由「总口径通过」翻为「每模口径拒绝」⇒ 判定更严")

    d4 = drc(4)
    check("B4 既有参考设计不误伤：N=4 两口径皆合法（14.4 / 12）⇒ ACCEPT（无假阳）",
          d4["verdict"] == "ACCEPT"
          and MMM.mesh_cascade_loss_db(6, n_crossings=0) <= LIM_TOT
          and 5 * LB.PER_MZI_LOSS_DB <= LIM_PM,
          "D-118 自检⑤ / 标定基准 B5,D2,D3 / m3c 演示 均不受影响")

    check("B5 detail 可追责：含「每模口径」+ 光学深度 + 限值（不是笼统一句损耗超限）",
          "每模口径" in det5[0] and "光学深度 7" in det5[0] and "15.0" in det5[0],
          det5[0][:60])

    # ════════════════ C 节：限值 / 灵敏度 / 收益 ════════════════
    print("── C 限值（设计规则 · 可覆盖）与矩形收益 ──")
    check("C1 默认每模限值 = 15.0 dB（总级联仍 25.0 dB · 两键并存）",
          abs(LIM_PM - 15.0) < 1e-12 and abs(LIM_TOT - 25.0) < 1e-12,
          f"max_loss_per_mode_db={LIM_PM} · max_loss_db={LIM_TOT}")

    dt = drc(4, limits={"max_loss_per_mode_db": 10.0})
    check("C2 收紧到 10 dB（η≥10%）⇒ N=4 也拒绝（证明每模口径是绑定判据）",
          dt["verdict"] == "REJECT"
          and any("每模口径" in v["detail"] for v in dt["violations"]),
          "12 dB > 10 dB")

    dl_ = drc(4, limits={"max_loss_per_mode_db": 20.0})
    check("C3 放宽到 20 dB ⇒ N=4 通过（限值可覆盖 · 非硬编码）",
          dl_["verdict"] == "ACCEPT", "12 dB ≤ 20 dB")

    tri_ok = max(n for n in range(3, 13) if (2 * n - 3) * LB.PER_MZI_LOSS_DB <= LIM_PM)
    rect_ok = max(n for n in range(3, 13) if n * LB.PER_MZI_LOSS_DB <= LIM_PM)
    check("C4 ★矩形收益（呼应 M5/D-123）★ 同预算 15 dB：矩形可签 N≤6 · 三角仅 N≤4",
          tri_ok == 4 and rect_ok == 6
          and LB.triangular_optical_depth(6)["per_mode_max"] == 9
          and LB.rectangular_optical_depth(6)["per_mode_max"] == 6,
          f"tri N≤{tri_ok}（深度 2N−3）· rect N≤{rect_ok}（深度 N）")

    full = {"ops": _tri_ops(3), "N": 3, "n_crossings": 0, "source_g2": 0.03,
            "hom_visibility": 0.96, "detector_eta": 0.85,
            "calib_residual_rad": 1e-3, "phase_bits": 12}
    dfull = QDR.run_quantum_drc(full)
    check("C5 兼容性：规则名 / QDR_RULES / n_rules 全不变（仍 `QDR-LOSS-BUDGET` · 9 条 · 9 查）",
          len(QDR.QDR_RULES) == 9 and "QDR-LOSS-BUDGET" in QDR.QDR_RULES
          and dfull["n_rules"] == 9,
          f"QDR_RULES={len(QDR.QDR_RULES)} · n_rules={dfull['n_rules']}")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = QDR.RED_LINE_DISCLOSURE
    check("D1 披露齐备：loss_basis 键说明两口径 + 每模深度来源 + 「严于总口径」",
          "loss_basis" in disc and "每模口径" in disc.get("loss_basis", "")
          and "2N−3" in disc.get("loss_basis", ""),
          f"键={sorted(disc)}")

    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    src = open(os.path.join(_HERE, "lda_qeda", "quantum_drc_lvs.py"), encoding="utf-8").read()
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D2 红线：D-118/D-124 零量子 SDK 依赖（纯 numpy + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")

    check("D3 判决无 LLM：violation 为 dict · verdict 为 str 死标量（零模型调用）",
          all(isinstance(v, dict) and set(v) == {"rule", "detail"} for v in d5["violations"])
          and d5["verdict"] in ("ACCEPT", "REJECT"),
          "rule/detail 二元组 · 全是限值比对")

    check("D4 限值明标「设计规则 · 可覆盖」：与文件内其它 DEFAULT_DRC_LIMITS 同性质",
          "设计规则" in src and "可覆盖" in src and "非实测 golden" in src,
          "注释与模块 docstring 双处标注")

    # ════════════════ E 节：护栏 + 反证 ════════════════
    print("── E 护栏 + 反证 ──")
    guard = True
    for bad in ((lambda: QDR.per_mode_optical_depth([])),
                (lambda: QDR.per_mode_optical_depth([(0, 1)])),
                (lambda: QDR.per_mode_optical_depth([(-1, 0.3, 0.1)])),
                (lambda: QDR.per_mode_optical_depth(_tri_ops(4), n_modes=3))):
        try:
            bad()
            guard = False
        except ValueError:
            pass
    check("E1 护栏：空 ops / 非法元数 / 负模索引 / N 越界 ⇒ 抛 ValueError",
          guard, "四类非法输入全抛错")

    tri_d = LB.triangular_optical_depth(8)["per_mode_max"]
    rect_d = LB.rectangular_optical_depth(8)["per_mode_max"]
    abs_d = LB.abstract_reck_optical_depth(8)["per_mode_max"]
    check("E2 反证：per_mode_optical_depth 非常量 —— 三角/矩形/抽象 三网格互不相同（13/8/7 @N=8）",
          QDR.per_mode_optical_depth(_tri_ops(8)) == tri_d == 13
          and QDR.per_mode_optical_depth(_rect_flat(8)) == rect_d == 8
          and abs_d == 7,
          f"tri={tri_d} · rect={rect_d} · abs={abs_d}")

    check("E3 反证：每模深度 = 模真正穿过的门片数（单门 1 · 同门 3 遍 ⇒ 3）≠ 门总片数（5≠6 @N=4）",
          QDR.per_mode_optical_depth([(0, 0, 0.3, 0.1)]) == 1
          and QDR.per_mode_optical_depth([(0, 0, 0.3, 0.1)] * 3) == 3
          and QDR.per_mode_optical_depth(o4) == 5 and len(o4) == 6,
          "防「用 len(ops) 冒充每模深度」")

    # ════════════════ F 节：跨模块同源 ════════════════
    print("── F 跨模块同源（与 D-120 / D-123 口径一致）──")
    ok_f1 = True
    detail_f1 = []
    for n_ in (4, 8, 16):
        a = QDR.per_mode_optical_depth(_tri_ops(n_))
        b = LB.triangular_optical_depth(n_)["per_mode_max"]
        c = QDR.per_mode_optical_depth(_rect_flat(n_))
        e = LB.rectangular_optical_depth(n_)["per_mode_max"]
        detail_f1.append(f"N={n_}:tri{a}={b}/rect{c}={e}")
        if not (a == b == 2 * n_ - 3 and c == e == n_):
            ok_f1 = False
    check("F1 与 D-123 同源：DRC 数出的每模深度 ≡ loss_budget.optical_depth_profile",
          ok_f1, " · ".join(detail_f1))

    check("F2 与 D-120 同源：每模损耗 = 深度 × per_mzi（DRC 引自 D-123 单一真源）",
          abs(LB.PER_MZI_LOSS_DB - SBM.PER_MZI_LOSS_DB) < 1e-12
          and abs(7 * LB.PER_MZI_LOSS_DB - 7 * SBM.PER_MZI_LOSS_DB) < 1e-12,
          f"per_mzi={LB.PER_MZI_LOSS_DB}")

    check("F3 与 D-118 自检⑩互证：三角每模深度 ≡ D-121 浅调度（2N−3）· 迁移结论一致",
          QDR.per_mode_optical_depth(_tri_ops(8)) == TMB.temporal_shallow_profile(8, target="dft")["shallow_depth"] == 13,
          "13 = 2·8−3")

    print()
    print(f"DRC 损耗每模口径 门禁 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
