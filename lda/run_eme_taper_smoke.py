"""EME 锥度求解器 smoke（v0.9.26 · B8 接线的凭据守护）。

═══ 为什么要有这个 smoke ═══
B8（绝热锥度传输效率）在 v0.9.26 从自证桩接成真独立候选 `taper_eme`
（严格独立 19 → 20）。这次接线**连撞三次证否**，每一条的教训都必须钉成常驻
断言，否则下次改数值档位就会静默退化：

  ① **BPM（分步傅里叶）整条路线被证否**：旁轴展开参数在窄端（w=0.2 µm 的局部
     基模 n_eff≈1.90 vs 脊区 2.44）达 **65%** ⇒ 伪辐射随长度累积 ⇒ T 随 L 增大
     反而**下降**（0.9936@25µm → 0.9729@200µm），且**减小 dz 不收敛**（模型误差，
     非离散误差）。教训：**模型不适用时，加细网格救不了**。
  ② **EME 固定 n_slices ⇒ 判据零判别力**：Δw=(w2−w1)/n_slices 与 L 无关，且
     L=200 时 dz=1 µm 使 Δβ·dz 达 ~5 rad/片**严重欠采样** ⇒ T 在 L=2 与 L=200
     **同值**（0.996）。必须按 **dz** 推切片数。
  ③ **折射率剖面硬判据 ⇒ 锥度被离散成 8 次突跳**：dx=0.02 µm 时半宽只从 0.1
     走到 0.25 µm（**7.5 个网格**）⇒ 无论 z 切多少片，横向剖面只有 ~8 个可取值。
     必须做**亚网格面积加权**（对 n² 做格心覆盖平均）。
  ④ **倏逝模 sqrt 取主值 +i|β| ⇒ exp(+|β|dz) 指数增长**：L=5 µm 就溢出到 4e30。
     衰减分支必须是 **Im(β)<0**。

═══ 判什么 ═══
  ① 求解器九条自校锚全 PASS（含"模式解算器 O(dx²) 收敛到解析 TE0"这一**非自证**锚）
  ② B8 tol / golden / candidate 读自 BENCHMARK_DEFS（写死会漂移 ⇒ 读真源）
  ③ 接线护栏：candidate 必须是 taper_eme（防改回 ReferenceCandidate 自证桩）
  ④ 正向 PASS：|候选 − golden| ≤ tol（求解器没坏）
  ⑤ 判据窗口下界：1−T **严格非零**且 < tol（恒 0 = 回落 golden = 自证桩）
  ⑥ 反向：非绝热（w2=3.0/L=1.0 µm）⇒ |T−1| ≫ tol 必被抓
  ⑦ 数值档位防漂移：DEFAULT_DZ/MMODES/DX/WINDOW 必须是标定值
  ⑧ 突变结下界：T_abrupt ≤ T ≤ 1（渐变不可能比直接对接更差）

═══ 诚实边界（写在这里，不掩盖）═══
  · **判据余量仅 4.65e-5**（占 tol 1e-2 的 0.47%）。本锚只回答「是否进入绝热
    极限」，不回答精度。⑤ 因此只断言「严格非零」。
  · **0.2→0.5 µm 几何的损耗上限仅 ~1.5%**（突变结重叠 0.9853）⇒ **单独扰动 L
    无法击穿 tol**（L 缩到 0.2 µm 也只到 0.993）。⑥ 因此用 w2=3.0/L=1.0 µm。
  · **短锥度区（L≲2 µm）未收敛**（箱模谱在 Δβ·L≪1 时欠采样，窗口 8/16/32 相差
    4e-3，且 EME 值 0.993 **高于**突变结下界 0.9853）。单调性自校锚只取 L≥5 µm。
  · **EIM 降维 + 单向近似**：不含垂向辐射与极化耦合，不算背向反射。
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
    from lda.lda_solver import eme_taper as eme
except ImportError:                             # 以 cwd=lda/ 直跑时
    sys.path.insert(0, os.path.join(_HERE, "lda_solver"))
    import eme_taper as eme                     # noqa: E402

try:
    from lda.lda_harness.benchmarks import BENCHMARK_DEFS
except ImportError:
    sys.path.insert(0, _HERE)
    from lda_harness.benchmarks import BENCHMARK_DEFS  # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")
    return bool(ok)


# B8 锚题参数（与 benchmarks.py BENCHMARK_DEFS["B8"]["default_params"] 同源）
B8_P = dict(w1=0.2, w2=0.5, L=200.0, wl=1.55, n_eff=2.44, n_clad=1.44)
# ⑦ 数值档位标定值（🔴 改这里 = 改判据，必须同步重跑收敛扫描并更新 eme_taper.py
#    的标定记录。为提速调粗 ⇒ ④ 会假绿、⑤ 会失效）
CAL_DZ, CAL_MMODES, CAL_DX, CAL_WINDOW = 0.4, 32, 0.02, 16.0
# ⑤ 判据窗口下界：实测 1−T = 4.65e-5，只断言严格 > 0
BASELINE_NONZERO_MIN = 0.0
# ⑥ 反向用例（同一参数空间内的"粗暴突变结"）
REV_W2, REV_L = 3.0, 1.0


def main() -> int:
    print("=" * 70)
    print("EME 锥度求解器 smoke（B8 接线凭据守护）")
    print("=" * 70)

    # ① 求解器自校锚全 PASS（verbose 直出分项，便于失败时定位到具体哪一条）
    try:
        ok_self = eme.selfcheck(verbose=True)
        detail = "9 条（直波导恒等/解析TE0收敛/基线/dz·模式数·窗口收敛/单调/反向/下界）"
    except Exception as e:                          # noqa: BLE001
        ok_self, detail = False, f"{type(e).__name__}: {e}"
    check("① 求解器自校锚全 PASS", ok_self, detail)

    # ② tol / golden / candidate 读自 BENCHMARK_DEFS（防写死漂移）
    b8 = BENCHMARK_DEFS.get("B8", {})
    b8_tol = float(b8.get("tol", -1))
    check("② B8 tol 读自 BENCHMARK_DEFS（=0.01，防写死漂移）",
          math.isclose(b8_tol, 0.01, rel_tol=0, abs_tol=1e-12),
          f"tol={b8_tol:g}")
    # 🔴 golden_fn 是**位置参数**签名（w1,w2,L,wl,n_eff,n_core,n_clad），
    #    不是 params-dict 风格 ⇒ 必须按名展开，且 n_core 只有 golden 用（EME 的
    #    横向 EIM 问题不吃它，见 eme_taper.taper_transmission 的 n_core 兼容位）。
    _b8p_full = {**B8_P, "n_core": b8.get("default_params", {}).get("n_core", 3.48)}
    golden = b8.get("golden_fn", lambda **p: float("nan"))(**_b8p_full)
    check("② golden = 绝热极限常量上界 1.0",
          math.isclose(float(golden), 1.0, rel_tol=0, abs_tol=1e-12),
          f"golden={float(golden):g}")

    # ③ 接线护栏：不得回退成自证桩
    check("③ B8 已接独立候选 taper_eme（防改回 ReferenceCandidate 自证桩）",
          b8.get("candidate") == "taper_eme",
          f"candidate={b8.get('candidate')!r}")

    # ④ 正向 PASS
    try:
        T = eme.taper_transmission(**B8_P)
        d = abs(T - float(golden))
        ok_fwd = d <= b8_tol
        detail = f"T={T:.9f} |T−1|={d:.3e} ≤ tol={b8_tol:g}（余量 {b8_tol/max(d,1e-30):.0f}×）"
    except Exception as e:                          # noqa: BLE001
        ok_fwd, T, d = False, float("nan"), float("nan")
        detail = f"{type(e).__name__}: {e}"
    check("④ 正向 PASS：|候选 − golden| ≤ tol（求解器没坏）", ok_fwd, detail)

    # ⑤ 判据窗口下界：严格非零（恒 0 ⇒ 回落 golden ⇒ 自证桩）
    gap = 1.0 - T
    check("⑤ 判据窗口下界：1−T 严格非零（恒 0 = 回落 golden = 自证桩）",
          math.isfinite(gap) and gap > BASELINE_NONZERO_MIN
          and gap < b8_tol,
          f"1−T={gap:.4e}（>0 且 < tol={b8_tol:g}）")

    # ⑥ 反向：非绝热必被抓
    try:
        Trev = eme.taper_transmission(**{**B8_P, "w2": REV_W2, "L": REV_L})
        ok_rev = abs(Trev - float(golden)) > b8_tol
        detail = (f"w2={REV_W2}/L={REV_L}µm ⇒ T={Trev:.5f} "
                  f"|T−1|={abs(Trev-1.0):.4f} > tol={b8_tol:g} ✅")
    except Exception as e:                          # noqa: BLE001
        ok_rev, detail = False, f"{type(e).__name__}: {e}"
    check("⑥ 反向：破坏绝热（w2=3.0/L=1.0µm）⇒ 必被抓（tol 未放水）",
          ok_rev, detail)

    # ⑦ 数值档位防漂移
    got = (eme.DEFAULT_DZ, eme.DEFAULT_MMODES, eme.DEFAULT_DX,
           eme.DEFAULT_WINDOW_UM)
    want = (CAL_DZ, CAL_MMODES, CAL_DX, CAL_WINDOW)
    check("⑦ 数值档位未漂移（dz=0.4/M=32/dx=0.02/window=16µm，标定值）",
          got == want, f"实测={got} 标定={want}")

    # ⑧ 突变结下界
    try:
        Tab = eme.abrupt_overlap(0.2, 0.5, 1.55, 2.44, 1.44)
        check("⑧ 突变结下界 T_abrupt ≤ T(L) ≤ 1（渐变不可能比直接对接更差）",
              Tab <= T <= 1.0 + 1e-9,
              f"T_abrupt={Tab:.6f} ≤ T={T:.6f} ≤ 1")
    except Exception as e:                          # noqa: BLE001
        check("⑧ 突变结下界 T_abrupt ≤ T(L) ≤ 1", False,
              f"{type(e).__name__}: {e}")

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print(f"EME 锥度求解器 smoke：{len(CHECKS) - n_fail}/{len(CHECKS)} PASS")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
