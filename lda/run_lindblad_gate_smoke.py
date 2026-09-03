"""Lindblad 门保真度求解器 smoke（v0.9.24 · P0 自证 · B10 接线 + golden 修正的凭据守护）。

═══ 为什么要有这个 smoke ═══
B10（单比特门保真度）在 v0.9.24 一次性做了两件大事，两件都**必须**有常驻护栏：

  ① **golden 语义修正（D-66 第 8 例）**：旧式 F=exp(−t·(1/T1+1/(2T2))) 被证否
     —— 它不对应任何标准保真度定义，一阶系数是 Lindblad 严格解的 2.727×
     （比值恰为 30/11，无物理来源），与严格解差 2.638e-4。
  ② **tol 收紧 1e6 倍**（0.01 → 1e-8）+ 接入独立候选 lindblad_gate_f。

🔴 **没被验证过的护栏不算护栏**：这两条若只写在 note 散文里，下次有人把 golden
改回旧式、或把 tol 放宽，就会静默失效 ⇒ 必须钉成常驻断言。本 smoke 干这个。

═══ 判什么 ═══
  ① 求解器四道自校锚全 PASS（PTM 结构 / 敏感 regime O(h⁴) / 稳态 / 非物理输入）
  ② B10 tol 读自 BENCHMARK_DEFS（写死会漂移 ⇒ 读真源）
  ③ golden 语义护栏：现行 golden 必须**不等于**已证否的旧经验式（防改回）
  ④ 正向 PASS：|候选 − golden| ≤ tol（求解器没坏）
  ⑤ baseline 严格非零且 < tol（判据窗口下界；恒 0 = 回落 golden = 自证桩）
  ⑥-⑪ 判据窗口上界：T1/T2/t_gate 各 ±10% 共六路，信号都必须 > tol
      —— 这是「tol 没放水到什么都抓不住」的硬证据（旧 tol=0.01 时六路全抓不住）

═══ 诚实边界（写在这里，不掩盖）═══
  · **生产档位残差落在机器精度**：t_gate=0.02 µs、T1/T2~60-80 µs ⇒ |L|·t≈2.5e-4，
    RK4 从 N=5 到 N=400 残差恒为 1.11e-16 且与步数无关 ⇒ 该残差**不可标定**。
    「候选真在工作」由自校锚①的可标定证据证明（PTM 非对角元 Λ_Z,I≈−2.5e-4 逐
    元素比对 / 敏感 regime 残差 5.6e-9 且 N 加倍降 16.3× / t→∞ 稳态 F→0.5），
    **不是**靠生产档位的残差。本 smoke ⑤ 因此只断言「严格非零」，不假装
    「残差大小证明了精度」。
  · 物理边界：T=0 热库（未含 n_th 热激发）；H=0 idle 门口径（未含脉冲形状
    误差/泄漏/串扰）⇒ 是退相干极限上界，非实测门保真度。

运行：python run_lindblad_gate_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 双路兜底（项目铁律：包内模块导入不得只依赖单一路径）
try:                                            # 仓库根在 sys.path 时
    from lda.lda_solver import lindblad_gate_fidelity as lg
except ImportError:                             # 以 cwd=lda/ 直跑时
    sys.path.insert(0, os.path.join(_HERE, "lda_solver"))
    import lindblad_gate_fidelity as lg         # noqa: E402

try:
    from lda.lda_harness.golden import b10_gate_fidelity
except ImportError:
    sys.path.insert(0, _HERE)
    from lda_harness.golden import b10_gate_fidelity  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")
    return bool(ok)


# B10 锚题参数（与 benchmarks.py BENCHMARK_DEFS["B10"]["default_params"] 同源）
B10_T1, B10_T2, B10_TG = 80.0, 60.0, 0.02
B10_TOL = 1e-8
# ③ golden 语义护栏的判据：现行 golden 与已证否旧经验式的差（默认参数下 2.638e-4）
LEGACY_GAP_MIN = 1e-4
# ⑤ baseline 非零判据：生产档位实测 1.11e-16，只断言严格 > 0（不可标定的事实）
BASELINE_NONZERO_MIN = 0.0
# 反向测试扰动键（全部三键六路，实测信号 3.787e-6 ~ 1.527e-5，均 ≫ tol 1e-8）
PERTURB_KEYS = ("T1", "T2", "t_gate")
PERTURB_REL = 0.10


def _cand(T1=B10_T1, T2=B10_T2, t_gate=B10_TG):
    return lg.average_gate_fidelity(T1, T2, t_gate, n_steps=lg.N_STEPS)


def _legacy_golden(T1=B10_T1, T2=B10_T2, t_gate=B10_TG):
    """已证否的 v0.9.23 旧经验式 F=exp(−t(1/T1+1/(2T2)))（D-66 第 8 例）。

    保留在此**只作护栏靶子**：③ 断言现行 golden 与它的差 > 1e-4，防止有人
    把 golden 改回这个没有任何标准依据的式子。
    """
    return math.exp(-t_gate * (1.0 / T1 + 1.0 / (2.0 * T2)))


def _tol_from_defs():
    """从 BENCHMARK_DEFS 取 B10 的 tol（写死会漂移 ⇒ 读真源）。"""
    try:
        from lda_harness.benchmarks import BENCHMARK_DEFS
        return float(BENCHMARK_DEFS["B10"]["tol"])
    except Exception:                            # noqa: BLE001 —— 取不到即暴露
        return None


def main() -> int:
    print("=" * 74)
    print("Lindblad 门保真度 smoke（B10 接线 + golden 语义修正的凭据守护）")
    print("=" * 74)

    # ① 求解器自校锚（PTM 结构 / 敏感 regime O(h⁴) / 稳态 / 非物理输入护栏）
    try:
        ok_sc = lg.run_selfchecks(verbose=True)
    except Exception as e:                       # noqa: BLE001
        ok_sc = False
        print(f"  自校异常：{type(e).__name__}: {e}")
    check("Lindblad 求解器四道自校锚全 PASS（PTM结构/敏感regime O(h⁴)/稳态/护栏）",
          ok_sc, "含 PTM 非对角元 Λ_Z,I 逐元素比对（生产档位残差不可标定的补偿证据）")

    # ② tol 与生产档位一致性
    tol_defs = _tol_from_defs()
    check("B10 tol 读自 BENCHMARK_DEFS（不写死，防漂移）",
          tol_defs is not None and abs(tol_defs - B10_TOL) < 1e-15,
          f"BENCHMARK_DEFS tol={tol_defs} · smoke 常量={B10_TOL}")

    # ③ golden 语义护栏：现行 golden 必须显著偏离已证否的旧经验式
    g_now = b10_gate_fidelity(B10_T1, B10_T2, B10_TG)
    g_old = _legacy_golden()
    gap = abs(g_now - g_old)
    check("B10 golden 未回落已证否旧经验式 exp(−t(1/T1+1/(2T2)))（D-66 第 8 例）",
          gap > LEGACY_GAP_MIN,
          f"现行={g_now:.12f} 旧式={g_old:.12f} |差|={gap:.4e} > {LEGACY_GAP_MIN:g}"
          "（旧式一阶系数是严格解的 2.727×，比值 30/11 无物理来源）")

    # ④ 正向：候选必须落在 tol 内（求解器没坏）
    base = _cand()
    d_base = abs(base - g_now)
    check("B10 正向 PASS（|候选 − golden| ≤ tol，求解器未坏）",
          math.isfinite(d_base) and d_base <= B10_TOL,
          f"候选={base:.15f} golden={g_now:.15f} |Δ|={d_base:.3e} tol={B10_TOL:g}")

    # ⑤ 判据窗口下界 + baseline 严格非零（回落 golden 即穿帮）
    check("B10 baseline |Δ| 严格非零（未静默回落 golden，非自证桩）",
          math.isfinite(d_base) and d_base > BASELINE_NONZERO_MIN,
          f"|Δ|={d_base:.3e}（生产档位 |L|·t≈2.5e-4 ⇒ 残差落在机器精度，"
          "**不可标定**；非自证桩由自校锚①的可标定证据 + ⑥-⑪ 反向扰动证明）")
    check("B10 判据窗口下界成立（baseline |Δ| < tol，否则 tol 放水）",
          math.isfinite(d_base) and d_base < B10_TOL,
          f"baseline={d_base:.3e} < tol={B10_TOL:g}"
          f"（下界余量 {B10_TOL / d_base:.1e}×）")

    # ⑥-⑪ 判据窗口上界：三键六路扰动信号都必须 > tol
    for key in PERTURB_KEYS:
        for sgn, tag in ((+1.0, "+10%"), (-1.0, "-10%")):
            p = {"T1": B10_T1, "T2": B10_T2, "t_gate": B10_TG}
            p[key] = p[key] * (1.0 + sgn * PERTURB_REL)
            try:
                v = _cand(**p)
                sig = abs(v - g_now)
            except Exception as e:               # noqa: BLE001
                v, sig = float("nan"), float("nan")
                print(f"  {key}{tag} 求解异常：{type(e).__name__}: {e}")
            check(f"B10 判据窗口上界成立（{key}{tag} 扰动信号 > tol，tol 未放水）",
                  math.isfinite(sig) and sig > B10_TOL,
                  f"F={v:.12f} 信号={sig:.4e} > tol={B10_TOL:g}"
                  f"（{sig / B10_TOL:.0f}× 余量）")

    # 非物理输入护栏（golden 侧也必须有，否则非物理参数会产出看似合法的值）
    try:
        b10_gate_fidelity(80.0, 200.0, 0.02)    # T2=200 > 2·T1=160
        ok_guard, d_guard = False, "未抛错（护栏缺失）"
    except ValueError as e:
        ok_guard, d_guard = True, f"ValueError: {str(e)[:60]}…"
    check("B10 golden 拒绝非物理输入 T2 > 2·T1（不静默 clamp）",
          ok_guard, d_guard)

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print(f"Lindblad 门保真度 smoke：{len(CHECKS) - n_fail}/{len(CHECKS)} PASS")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
