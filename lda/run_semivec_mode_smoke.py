"""2D 半矢量本征模求解器 smoke（v0.9.23 · P0 自证 · E2 升 strict 的凭据守护）。

═══ 为什么要有这个 smoke ═══
E2（Si₃N₄ 波导群折射率实证锚）在 v0.9.23 从「降级量级参考」升为「严格独立
候选」，候选求解器由标量 FDFD（fdfd_ng）换成 2D 半矢量本征模（semivec_ng）。
升级的**唯一凭据**是两条实测：

  ① 窗口散射从 ±0.04~0.08 降到 < 1e-5（FDFD 的 PASS 可能只是窗口挑得好，
     半矢量不会）；
  ② 精度由 A 级实证对照端到端校准到 8.4e-5（自校锚③）。

🔴 **没被验证过的护栏不算护栏**：这两条凭据若只写在 note 散文里，下次有人改
网格/窗口/ARPACK 参数就会静默失效 ⇒ 必须钉成常驻断言。本 smoke 就是干这个。

═══ 判什么 ═══
  ① 求解器三道自校锚全 PASS（可分离极限 ×2 + A 级实证对照 ×1）
  ② E2 判定窗口鲁棒：L ∈ {5.0, 6.0, 8.0} µm 三窗口 n_g 散射 < 1e-3
     （对比 FDFD 的 ±0.04~0.08；且三窗口必须都出有限解，不出=nan 即 FAIL）
  ③ E2 正向：|候选 − golden| < tol（求解器没坏）
  ④ E2 判据窗口（铁律）：baseline |Δ| < tol < 扰动信号
     —— n_core ±10% 两个方向都要**超出** tol（证明 tol 没放水到什么都抓不住）
  ⑤ 判据窗口不退化：baseline 必须**非零**（回落 golden 即穿帮，同自证桩陷阱）

═══ 诚实边界（写在这里，不掩盖）═══
  · 本 smoke **不**宣称 E2 精度已验证：baseline |Δ|=0.0652 的主成分是
    「ring golden vs 直波导候选」的对象不对齐 + 制造公差（见 benchmarks.py E2 note）。
  · 灵敏度网格（最小可检出扰动）由 run_benchmark_falsifiability_smoke ④ 覆盖，
    此处不重复跑（省 8 次本征解 ≈ 90s）。

运行：python run_semivec_mode_smoke.py（cwd=lda/）
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
    from lda.lda_solver import semivec_mode_solver as sv
except ImportError:                             # 以 cwd=lda/ 直跑时
    sys.path.insert(0, os.path.join(_HERE, "lda_solver"))
    import semivec_mode_solver as sv            # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")
    return bool(ok)


# E2 锚题参数（与 benchmarks.py BENCHMARK_DEFS["E2"]["default_params"] 同源）
E2_GOLDEN = 1.892
E2_TOL = 0.10
E2_W, E2_H, E2_WL = 1.0, 0.3, 1.55
E2_NC, E2_NCL = 2.0, 1.44
# 判定窗口扫描：5.0 是「墙离模场 2 µm」的下探点，8.0 是上探点，6.0 是生产档位
WINDOWS = (5.0, 6.0, 8.0)
SCATTER_MAX = 1e-3      # 三窗口 n_g 极差上界（实测 <1e-5，留 100× 余量）
# 反向测试扰动键：n_core（实测信号最强：±10% 分别 0.3600 / 0.2239，均 > tol 0.10）
PERTURB_KEY = "n_core"
PERTURB_REL = 0.10


def _e2_ng(n_core=E2_NC, n_clad=E2_NCL, w=E2_W, h=E2_H, L=None):
    return sv.group_index(w, h, E2_WL, n_core=n_core, n_clad=n_clad,
                          core_material="Si3N4", clad_material="SiO2",
                          h_grid=sv.H_GRID, L=(L or sv.L_WIN))


def _tol_from_defs():
    """从 BENCHMARK_DEFS 取 E2 的 tol（写死会漂移 ⇒ 读真源）。"""
    try:
        from lda_harness.benchmarks import BENCHMARK_DEFS
        return float(BENCHMARK_DEFS["E2"]["tol"])
    except Exception:                            # noqa: BLE001 —— 取不到即暴露
        return None


def main() -> int:
    print("=" * 72)
    print("2D 半矢量本征模求解器 smoke（E2 升 strict 的凭据守护）")
    print("=" * 72)

    # ① 求解器自校锚（可分离极限 ×2 + A 级实证对照 ×1）
    try:
        ok_sc, rows = sv.run_selfchecks(verbose=True)
    except Exception as e:                       # noqa: BLE001
        ok_sc, rows = False, []
        print(f"  自校异常：{type(e).__name__}: {e}")
    check("半矢量求解器三道自校锚全 PASS（可分离极限×2 + SiN 实证对照×1）",
          ok_sc and len(rows) == 5,
          f"{sum(1 for r in rows if r[5])}/{len(rows)} 通过")

    # tol 与生产档位一致性：smoke 里的 E2_TOL 必须等于 BENCHMARK_DEFS 真值
    tol_defs = _tol_from_defs()
    check("E2 tol 读自 BENCHMARK_DEFS（不写死，防漂移）",
          tol_defs is not None and abs(tol_defs - E2_TOL) < 1e-12,
          f"BENCHMARK_DEFS tol={tol_defs} · smoke 常量={E2_TOL}")

    # ② 判定窗口鲁棒性（E2 升级的**核心凭据**）
    ngs = {}
    for L in WINDOWS:
        try:
            ngs[L] = _e2_ng(L=L)
        except Exception as e:                   # noqa: BLE001
            ngs[L] = float("nan")
            print(f"  窗口 L={L} 求解异常：{type(e).__name__}: {e}")
    finite = [v for v in ngs.values() if math.isfinite(v)]
    spread = (max(finite) - min(finite)) if len(finite) >= 2 else float("nan")
    check(f"E2 判定窗口鲁棒（{len(WINDOWS)} 个窗口均出有限解且散射 < {SCATTER_MAX:g}）",
          len(finite) == len(WINDOWS) and spread < SCATTER_MAX,
          " ".join(f"L{L}={v:.6f}" for L, v in ngs.items())
          + f" | 散射={spread:.2e}"
          + "（对比 FDFD 候选 ±0.04~0.08 ⇒ PASS 非窗口凑巧）")

    # ③ 正向：候选必须落在 tol 内（求解器没坏）
    base = finite[0] if finite else float("nan")
    d_base = abs(base - E2_GOLDEN) if math.isfinite(base) else float("nan")
    check("E2 正向 PASS（|候选 − 实测 golden| ≤ tol，求解器未坏）",
          math.isfinite(d_base) and d_base <= E2_TOL,
          f"候选={base:.6f} golden={E2_GOLDEN} |Δ|={d_base:.4f} tol={E2_TOL}")

    # ⑤ 判据窗口不退化：baseline 必须非零（回落 golden = 自证桩陷阱）
    check("E2 baseline |Δ| 非零（未静默回落 golden，非自证桩）",
          math.isfinite(d_base) and d_base > 1e-9,
          f"|Δ|={d_base:.6f}（判据 1e-9；≡0 即假独立）")

    # ④ 判据窗口铁律：baseline < tol < 扰动信号（两个方向都要超出 tol）
    check("E2 判据窗口下界成立（baseline |Δ| < tol，否则 tol 放水）",
          math.isfinite(d_base) and d_base < E2_TOL,
          f"baseline={d_base:.4f} < tol={E2_TOL}"
          f"（余量 {(E2_TOL - d_base) / E2_TOL:.0%}）")
    for sgn, tag in ((+1.0, "+10%"), (-1.0, "-10%")):
        try:
            v = _e2_ng(n_core=E2_NC * (1.0 + sgn * PERTURB_REL))
            sig = abs(v - E2_GOLDEN)
        except Exception as e:                   # noqa: BLE001
            v, sig = float("nan"), float("nan")
            print(f"  n_core{tag} 求解异常：{type(e).__name__}: {e}")
        check(f"E2 判据窗口上界成立（n_core{tag} 扰动信号 > tol，tol 未放水）",
              math.isfinite(sig) and sig > E2_TOL,
              f"n_g={v:.6f} 信号={sig:.4f} > tol={E2_TOL}"
              f"（{sig / E2_TOL:.1f}× 余量）")

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print(f"半矢量本征模求解器 smoke：{len(CHECKS) - n_fail}/{len(CHECKS)} PASS")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
