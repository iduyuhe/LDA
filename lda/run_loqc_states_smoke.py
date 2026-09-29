"""LOQC 量子态层 smoke（D-113 · LOQC 量子态层的凭据守护）。

═══ 为什么要有这个 smoke ═══
D-113 把 M2 的「可编程酉 U」从经典光学层提升到**量子态层**（Fock 基），给出真正的
量子干涉。这里有三件**必须常驻护栏**的事：

  ① **闭式物理律锚**：HOM 干涉（不可区分双光子 → 符合计数 0）、一般分束器闭式
     cos²(2θ)。若有人把分束器相位约定改错（去掉离对角虚数），HOM 就静默变成 1/2
     ⇒ 必须钉成断言。
  ② **方法学独立**：同一输出分布用 permanent（组合计数）与产生算符多项式展开
     （符号展开）两种结构不同算法算，须机器精度一致 ⇒ 防"自证桩"（复制粘贴）。
     🔴 教训：归一化分母若多/少一层开方，2 光子（Πn!=1）掩盖 bug、多光子才暴露
     ⇒ 自检**必须**覆盖多光子多模（≥3 光子）而非只测 HOM 双光子。
  ③ **反自证桩**：不可区分=0 不能是"恒 0"（那证明不了干涉）⇒ 必须同时断言
     **可区分**光子符合概率 = 1/2（有干涉时降到 0）。

═══ 判什么（14 条）═══
模块自检 ⑧ 条 + 闭式跨网格 + 归一 + 双算法 + 经典极限 + 反自证桩 + 双护栏 + 芯片级
量子干涉（把 M2 mesh 的 U 当线性光学变换）。

运行：python run_loqc_states_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 统一命名空间：用 `lda_qeda.*` 导入（与各物理模块内部一致 ⇒ 防同一文件双实例）
try:
    from lda_qeda import loqc_states as L
except ImportError:                                       # 极端兜底
    sys.path.insert(0, os.path.join(_HERE, "lda_qeda"))
    import loqc_states as L  # noqa: E402

from lda_harness.smoke_kit import make_check        # noqa: E402

# 判据计数写进模块命名空间（尾部读 PASS/FAIL）；助手复用公共 `smoke_kit`，
# 不另建局部 `def check`（防「助手重复棘轮」J3/J4 劣化 · 名字在前！写反成
# check(cond, name) ⇒ 字符串恒真 ⇒ 假绿）。
PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def _rand_unitary(M, seed):
    r = np.random.default_rng(seed)
    X = (r.standard_normal((M, M)) + 1j * r.standard_normal((M, M))) / math.sqrt(2.0)
    Q, R = np.linalg.qr(X)
    return Q @ np.diag(np.diag(R) / np.abs(np.diag(R)))


def main() -> int:
    print("=" * 74)
    print("LOQC 量子态层 smoke（D-113 · 闭式 HOM 锚 + 方法学独立 + 反自证桩）")
    print("=" * 74)

    # ① 模块自检 8 条（闭式/归一/双算法/经典极限/反自证桩/护栏）
    try:
        ok_sc = L.run_selfchecks(verbose=False)
    except Exception as e:                        # noqa: BLE001
        ok_sc = False
        print(f"  自检异常：{type(e).__name__}: {e}")
    check("量子态层模块自检 8/8 PASS", ok_sc,
          "HOM=0 · 闭式对齐 · 归一 · 双算法一致 · 经典极限 · 反自证桩 · 护栏")

    # ② HOM 50:50 破坏性干涉：符合概率 = 0（闭式物理律 golden）
    p_hom = L.hom_coincidence(math.pi / 4.0)
    check("HOM 50:50 不可区分双光子符合概率 = 0（闭式 golden）",
          p_hom < 1e-12, f"P={p_hom:.3e} < 1e-12")

    # ③ HOM 闭式锚：跨 θ 网格 |数值振幅 − cos2θ| < 1e-12
    max_d = max(
        abs(abs(L.linear_optics_amplitude(L.bs_unitary(float(th)), (1, 1), (1, 1)))
            - math.sqrt(max(L.hom_coincidence_closed_form(float(th)), 0.0)))
        for th in np.linspace(0.0, math.pi / 2.0, 49)
    )
    check("HOM 闭式锚：|数值振幅 − cos2θ| 全网格 < 1e-12",
          max_d < 1e-12, f"max|Δ|={max_d:.3e}")

    # ④ 方法学独立（多光子多模，防 2 光子掩盖 bug）：永久式 × 多项式逐组态一致
    max_dev = 0.0
    for (M, occ, seed) in ((4, (2, 0, 1, 0), 11), (5, (1, 1, 1, 0, 0), 12),
                           (6, (2, 1, 1, 0, 0, 0), 13)):
        U = _rand_unitary(M, seed)
        poly = L.apply_linear_optics_polynomial(U, occ)
        for out_occ in L._compositions(sum(occ), M):
            max_dev = max(max_dev,
                          abs(L.linear_optics_amplitude(U, occ, out_occ)
                              - poly.get(out_occ, 0.0 + 0.0j)))
    check("方法学独立：永久式 × 产生算符多项式（≥4 光子·多模）逐组态一致",
          max_dev < 1e-10, f"max|Δ|={max_dev:.3e}（2光子掩盖 bug 的教训已覆盖 3+ 光子）")

    # ⑤ 输出分布归一（酉守恒概率）
    max_norm = 0.0
    for (M, occ, seed) in ((4, (1, 1, 1, 1), 21), (6, (2, 1, 1, 0, 0, 0), 22)):
        U = _rand_unitary(M, seed)
        dist = L.output_distribution(U, occ)
        max_norm = max(max_norm, abs(sum(dist.values()) - 1.0))
    check("输出分布归一 Σ P = 1（多光子多模）",
          max_norm < 1e-12, f"max|ΣP−1|={max_norm:.3e}")

    # ⑥ 单光子经典极限：P(j)=|U_{ji}|²
    U = _rand_unitary(5, 31)
    max_cl = max(
        abs(L.prob_of(U, (1, 0, 0, 0, 0), tuple(1 if k == j else 0 for k in range(5)))
            - abs(U[j, 0]) ** 2) for j in range(5)
    )
    check("单光子经典极限 P(j)=|U_{ji}|²（量子→经典退化）",
          max_cl < 1e-12, f"max|Δ|={max_cl:.3e}")

    # ⑦ 反自证桩：可区分=1/2（有干涉时降到 0，证明 0 非"恒 0"）
    p_dist = L.hom_coincidence_distinguishable(math.pi / 4.0)
    check("反自证桩：可区分光子符合概率=1/2 且 ≠ 不可区分=0",
          abs(p_dist - 0.5) < 1e-12 and p_hom < 1e-12,
          f"可区分={p_dist:.6f} 不可区分={p_hom:.3e} ⇒ 干涉真实存在")

    # ⑧ HOM 可见度 = 1（50:50 理想）；病态模块（可区分≡不可区分 ⇒ 0/0）须报 FAIL 不崩溃
    try:
        vis = float(L.hom_visibility(math.pi / 4.0))
    except Exception:                              # noqa: BLE001
        vis = float("nan")
    check("HOM 可见度 V=1 @50:50（理想不可区分）",
          math.isfinite(vis) and abs(vis - 1.0) < 1e-12, f"V={vis:.12f}")

    # ⑨ 分束器相位约定的独立护栏：HOM 与 φ 无关（内部相位不破坏破坏性干涉）
    max_phi_drift = max(
        abs(L.hom_coincidence(math.pi / 4.0, ph) - 0.0)
        for ph in np.linspace(0.0, 2.0 * math.pi, 25)
    )
    check("分束器相位约定护栏：HOM 符合概率与内部相位 φ 无关",
          max_phi_drift < 1e-12, f"max|P(φ)|={max_phi_drift:.3e}")

    # ⑩ 护栏：非方阵 permanent 抛 ValueError
    try:
        L.permanent(np.ones((2, 3), dtype=complex))
        guard1, d1 = False, "未抛错（护栏缺失）"
    except ValueError as e:
        guard1, d1 = True, f"ValueError: {str(e)[:40]}…"
    check("护栏：permanent 拒绝非方阵（不静默）", guard1, d1)

    # ⑪ 护栏：光子数不守恒 ⇒ 振幅恒 0
    amp0 = L.linear_optics_amplitude(np.eye(2, dtype=complex), (2, 0), (1, 1))
    check("护栏：光子数不守恒 Σin≠Σout ⇒ 振幅恒 0", abs(amp0) < 1e-15,
          f"amp={abs(amp0):.3e}")

    # ⑫ 芯片级量子干涉：M2 的 4×4 路径纠缠酉 U 上，玻色子聚束
    #    U4 = 在模(0,2)上 50:50（M1 目标酉），输入 |1,1,0,0⟩
    U4 = np.eye(4, dtype=complex)
    bs = np.array([[1, 1j], [1j, 1]], dtype=complex) / math.sqrt(2.0)
    U4[np.ix_([0, 2], [0, 2])] = bs
    d_perm = L.output_distribution(U4, (1, 1, 0, 0))
    d_poly = L.apply_linear_optics_polynomial(U4, (1, 1, 0, 0))
    max_chip = max(
        abs(d_perm.get(o, 0.0) - abs(d_poly.get(o, 0.0 + 0.0j)) ** 2)
        for o in d_perm
    )
    check("芯片级：M2 4×4 酉上的量子干涉（永久式 × 多项式，片上）",
          max_chip < 1e-12 and abs(sum(d_perm.values()) - 1.0) < 1e-12,
          f"max|ΔP|={max_chip:.3e} ΣP={sum(d_perm.values()):.12f}")

    # ⑬ 芯片级 HOM：光进入模(0,2)的两个束（不可区分）→ 模(0,2)符合概率 = 0
    p_chip = L.coincidence_probability(U4, (1, 0, 1, 0), in_modes=(0, 2),
                                       out_modes=(0, 2))
    check("芯片级 HOM：模(0,2)双光子 → 同模符合概率 = 0",
          p_chip < 1e-12, f"P={p_chip:.3e}")

    # ⑭ 红线守卫：生产模块不得 import 量子 SDK（C 级自主）
    import re
    src = open(os.path.join(_HERE, "lda_qeda", "loqc_states.py"),
               encoding="utf-8").read()
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus")
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("红线：loqc_states 零量子 SDK 依赖（纯 numpy，C 级自主）",
          not hits, f"命中={hits or '无'}")

    print()
    print(f"LOQC 量子态层 smoke：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
