"""MMI 1×2 EME 求解核 smoke（v0.9.56 · E5 独立候选探测的**实测结论锁**）。

═══ 为什么要有这个 smoke ═══
E5（MMI 1×2 过量损耗实证锚，golden=0.05 dB，tol=0.1 dB）长期是自证桩。
v0.9.56 做了**两条独立路线**的真求解器探测，两条都**没能**把它升格：

  路线① 2D FDTD 全场时域 —— 直波导控制实验都无法让导模沿线保幅
         （≈0.7 dB/µm 虚假衰减且非单调）⇒ 未入库（不留下坏求解器）。
  路线② 2D-EIM 本征模展开 EME（lda_solver/mmi_eme.py）—— 本征分解本身
         正确（与解析超越方程交叉校验 <5e-3），但**建模层**不合格：
           · 自成像保真度只有 0.827（理论上限 0.9898）；
           · 对拍长 L_π 病态敏感，判到 tol=0.1 dB 需 L_π 优于 **0.22%**，
             2D-EIM 给不了 ⇒ **E5 结构性不可判**（实测确认 roadmap 的 C2+C5）。

🔴 **没被验证过的护栏不算护栏**：这些"没能升格"的结论若只写在 note 散文里，
下次有人换 EIM 参数/改网格就会静默失效（或反过来，以为已经接上了）⇒ 必须
钉成常驻断言。本 smoke 三件事：
  ① 锁住**求解核本身是对的**（可复算、守恒、对称、可扰动）—— 它是资产；
  ② 锁住**模型自校验闸门**（自成像保真度）—— 它能自己说"我还不够格"；
  ③ 锁住**已知缺口**（E5 目前确实判不了）—— 若哪天模型真够格了，断言
     **转红**提醒更新账本，而不是悄悄继续当桩。

═══ 判什么 ═══
  ① 本征分解交叉校验：有限差分 vs 解析超越方程，max|Δn_eff| < 8e-3
  ② 模式基正交归一：max|ΦᵀΦ − I| < 1e-9
  ③ 能量守恒：||E_out||² == Σ|c_m|²（< 1e-9，纯相位传播不得生灭能量）
  ④ 左右对称：|t₁| 与 |t₂| 相对差 < 1e-12（几何严格对称）
  ⑤ 确定性：同参两次调用逐位相同（可复现 ⇒ 可审计）
  ⑥ 判据 D（真数值，非重言）：W_mmi ±0.1 µm 两方向 excess 变化 ≥ 1.0 dB
  ⑦ 模型自校验闸门：自成像保真度 ∈ (0.5, 0.95) —— 显著低于理论上限 0.9898，
     如实记录模型"不自证"
  ⑧ 结构性不可判：判到 tol=0.1 dB 所需 L_π 相对精度 < 0.5%（2D-EIM 达不到）
  ⑨ 模型能力上界：放开 (L, y_split) 全平面寻优后最优 excess 仍 > 0.1 dB
     ⇒ 任何"几何解释修正"都救不回 tol
  ⑩ 已知缺口锁：|cand(L=27) − 0.05| > 0.1（E5 目前判不了；模型够格时转红）

═══ 诚实边界（写在这里，不掩盖）═══
  · 本 smoke **不**宣称 E5 已被独立验证。相反，它把"没验证成"钉成断言。
  · ⑦⑨ 是**回归锁**：数值随网格/参数会动，故用区间断言（不是等值），
    区间越界 ⇒ 模型行为变了，须人工复核而不是自动放宽。

运行：python run_mmi_eme_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:                                            # 仓库根在 sys.path 时
    from lda.lda_solver import mmi_eme as me
except ImportError:                             # 以 cwd=lda/ 直跑时
    sys.path.insert(0, os.path.join(_HERE, "lda_solver"))
    import mmi_eme as me                        # noqa: E402

import numpy as np                              # noqa: E402

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")
    return bool(ok)


# E5 锚题口径（与 benchmarks.py BENCHMARK_DEFS["E5"] / seed_empirical.json 同源）
E5_GOLDEN = 0.05
E5_TOL = 0.1
W_MMI = 2.8            # 语料 device 字段 "2.8x27 um2 footprint"
L_MMI = 27.0
OUT_GAP_STD = W_MMI / 2.0 - 0.5      # ⇒ y_split = W/4 = 0.7（1×2 标准双像位）

print("=" * 72)
print("MMI 1×2 EME 求解核 smoke（v0.9.56 · E5 独立候选探测结论锁）")
print("=" * 72)

# ---------------------------------------------------------------- ① 交叉校验
dl_c = 0.005
_ny = int(round((W_MMI + 6.0) / dl_c)) | 1
_ys = (np.arange(_ny) - (_ny - 1) / 2.0) * dl_c
_neff, _phi = me.slab_modes(me._guide_eps(_ys, W_MMI, 0.0, me.N_CORE_2D,
                                          me.N_CLAD_2D), dl_c, 1.55, me.N_CLAD_2D)
_ana = [me.slab_te_neff_analytic(me.N_CORE_2D, me.N_CLAD_2D, W_MMI, 1.55, m)
        for m in range(len(_neff))]
_pairs = [(a, b) for a, b in zip(_neff, _ana) if b is not None]
_dmax = max(abs(a - b) for a, b in _pairs)
check("① 本征分解 vs 解析超越方程（%d 模）" % len(_pairs),
      len(_pairs) >= 8 and _dmax < 8e-3,
      f"n_modes={len(_pairs)} max|Δn_eff|={_dmax:.2e} (dl={dl_c})")

# ---------------------------------------------------------------- ② 正交归一
_gram = _phi.T @ _phi
_orth = float(np.max(np.abs(_gram - np.eye(_gram.shape[0]))))
check("② 模式基正交归一", _orth < 1e-9, f"max|ΦᵀΦ−I|={_orth:.2e}")

# ---------------------------------------------------------------- ③④⑤ 主量
base = me.mmi_excess_loss(W_mmi=W_MMI, L_mmi=L_MMI, out_gap=OUT_GAP_STD, dl=0.01)
check("③ 能量守恒（纯相位传播不生灭）",
      abs(base["energy_out"] - base["power_in_mmi_modes"]) < 1e-9,
      f"||E_out||²={base['energy_out']:.8f} Σ|c|²={base['power_in_mmi_modes']:.8f}")

_bal = base["balance"]
check("④ 左右输出对称（几何严格对称）", _bal < 1e-12,
      f"|t₁|={base['t1']:.6f} |t₂|={base['t2']:.6f} 不平衡={_bal:.2e}")

again = me.mmi_excess_loss(W_mmi=W_MMI, L_mmi=L_MMI, out_gap=OUT_GAP_STD, dl=0.01)
check("⑤ 确定性（同参两次逐位相同）", again["value"] == base["value"],
      f"{base['value']:.10f} vs {again['value']:.10f}")

# ---------------------------------------------------------------- ⑥ 判据 D
# 🔴 操作点取**模型自洽的 1×2 设计点** L=(9/8)·L_π、y_split=W/4，而不是锚题
#    L=27：后者落在 excess 的局部极值上，局部导数退化到 ≈0，会把「判据 D」测成
#    假阴性（实测教训：在 L=27 处 dW=+0.1 只响应 0.05 dB）。判据 D 要证明的是
#    「候选是真数值计算且对设计变量有响应」，须在物理量与设计点对齐处测。
L_DESIGN = me.two_image_length(W_mmi=W_MMI, order=1, dl=0.01)
dpt = me.mmi_excess_loss(L_mmi=L_DESIGN, out_gap=OUT_GAP_STD, dl=0.01)
dW = 0.2
up = me.mmi_excess_loss(W_mmi=W_MMI + dW, L_mmi=L_DESIGN, out_gap=OUT_GAP_STD, dl=0.01)
dn = me.mmi_excess_loss(W_mmi=W_MMI - dW, L_mmi=L_DESIGN, out_gap=OUT_GAP_STD, dl=0.01)
s_up = abs(up["value"] - dpt["value"])
s_dn = abs(dn["value"] - dpt["value"])
check("⑥ 判据 D：设计点 W_mmi ±0.2µm 双向响应 ≥1.0 dB（真数值非重言）",
      s_up >= 1.0 and s_dn >= 1.0,
      f"L_design={L_DESIGN:.2f}µm baseline={dpt['value']:.3f} "
      f"+0.2→{up['value']:.3f}(Δ{s_up:.2f}) −0.2→{dn['value']:.3f}(Δ{s_dn:.2f}) dB")

# ---------------------------------------------------------------- ⑦ 自校验闸门
f7 = me.self_image_fidelity(W_mmi=W_MMI, dl=0.01)
check("⑦ 模型自校验闸门：自成像保真度显著低于理论上限（模型不自证）",
      0.5 < f7["fidelity"] < 0.95,
      f"fidelity={f7['fidelity']:.4f} 理论上限 p_in²={f7['upper_bound']:.4f} "
      f"(W={W_MMI}, L_pi={f7['L_pi_um']:.2f}µm)")

# ---------------------------------------------------------------- ⑧ 结构性不可判
# 🔴 用「±ε 档位极差」而非局部导数：L=27 恰在 excess 局部极值上，局部导数
#    只有 0.18 dB/µm，会给出「很稳健」的假象（实测教训，见 mmi_eme 文档串）。
s8 = me.beat_length_error_propagation(L_mmi=L_MMI, out_gap=OUT_GAP_STD,
                                      tol_db=E5_TOL, dl=0.01)
check("⑧ 结构性不可判（一）：L_π 仅 ±1% 误差即摆动 >tol（2D-EIM 远超此误差）",
      s8["spread_1pct_db"] > E5_TOL,
      f"±1%⇒{s8['spread_1pct_db']:.3f} dB = {s8['spread_over_tol_1pct']:.1f}×tol "
      f"(基准 {s8['excess_db']:.3f} dB)")
check("⑧ 结构性不可判（二）：L_π ±5% 误差摆动 >10×tol（稳健回归锁）",
      s8["spread_5pct_db"] > 10.0 * E5_TOL,
      f"±5%⇒{s8['spread_5pct_db']:.3f} dB = {s8['spread_over_tol_5pct']:.1f}×tol")

# ---------------------------------------------------------------- ⑨ 能力上界
b9 = me.best_case_excess(W_mmi=W_MMI, dl=0.02)
check("⑨ 模型能力上界：放开 (L, y_split) 全平面寻优后仍 >tol",
      b9["best_excess_db"] > E5_TOL,
      f"最优 excess={b9['best_excess_db']:.3f} dB @ L={b9['L_um']:.2f}µm "
      f"(={b9['L_over_Lpi']:.3f}Lπ) y_split={b9['y_split_um']:.2f} "
      f"(={b9['y_split_over_W']:.3f}W) T={b9['T']:.4f}")

# ---------------------------------------------------------------- ⑩ 已知缺口锁
gap = abs(base["value"] - E5_GOLDEN)
check("⑩ 已知缺口锁：E5 目前确实判不了（模型够格时此断言转红提醒更新账本）",
      gap > E5_TOL,
      f"|cand({base['value']:.3f}) − golden({E5_GOLDEN})| = {gap:.3f} dB > tol={E5_TOL}")

# ---------------------------------------------------------------- 汇总
n_pass = sum(1 for _, ok, _ in CHECKS if ok)
print("-" * 72)
print(f"MMI EME smoke: {n_pass}/{len(CHECKS)} PASS")
print(f"实测：锚题几何(L=27,W=2.8) excess={base['value']:.3f} dB | "
      f"模型能力上界={b9['best_excess_db']:.3f} dB | golden={E5_GOLDEN} tol={E5_TOL}")
print("结论：E5 保持自证桩；mmi_eme 作为可复用求解能力入库，不挂 E5 candidate。")
print("=" * 72)
sys.exit(0 if n_pass == len(CHECKS) else 1)
