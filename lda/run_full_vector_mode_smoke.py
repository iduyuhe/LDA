"""全矢量本征模求解器 smoke（G12-H · 消除 SOI +0.0276 的凭据守护）。

═══ 为什么要有这个 smoke ═══
G12-H 立项的唯一目标：给「SOI 高对比度波导 n_eff」一个**合法**的全矢量求解器，
把半矢量（E_y≡0 约束）在 SOI 上的 **+0.0276** 模型偏置打掉。
「打掉了」这个断言若只写在散文里，下次有人改网格/窗口/系数就会静默失效
⇒ 必须钉成常驻断言。本 smoke 就是干这个。

═══ 实测基线（2026-09-24，本仓自测）═══
  半矢量 SOI 600×220 TE（对齐网格 h=0.010）  2.594456  Δ(FDE)=+0.0285
  半矢量 同题（加密 h=0.0055 对齐）            2.597628  Δ(FDE)=+0.0316  ← 加密变差
  全矢量 同题（h=0.010）                        2.570410  Δ(FDE)=+0.0044
  全矢量 同题（h=0.005）                        2.569920  Δ(FDE)=+0.0039  ← 加密收敛
  🔴 半矢量生产档 H_GRID=0.015 给 2.560384（看似最准）——实为**几何 snap 巧合**：
     0.11/0.015=7.33 非整数 ⇒ 半厚被 snap 到 0.105（真值 0.11）⇒ 尺寸误差 ~−0.029
     恰好抵消 +0.028 的模型偏置。**该巧合随尺寸/波长即翻车**，不构成精度。

═══ 判什么 ═══
  ① 求解器全部自校锚 PASS（含**精确**闭式均匀极限，tol 1e-8）
  ② 回归锁：全矢量 SOI = 2.570410（防实现被改坏）
  ③ 反自证桩：baseline |Δ| 非零
  ④ 方法差非零：全矢量 ≠ 半矢量（>1.5e-2；否则是复制粘贴而非新方法）
  ⑤ 半矢量模型偏置**复现**且**加密变差**（+0.0285 → +0.0316，证其非离散误差）
  ⑥ 全矢量**消除**偏置：|Δ(FDE)| ≤ 5e-3 且 ≤ 1/5 半矢量偏置（外部对标，非 golden）
  ⑦ 低对比度退化：SiN 全矢量 vs 半矢量 |Δ| ≤ 3e-3
  ⑧ 判据窗口上界（反向测试）：n_core ±5% 两方向信号 > 回归锁 tol
  ⑨ 网格收敛：h=0.01→0.005 |Δ| ≤ 2e-3
  ⑩ 红线段：生产模块源码 import 行不得出现第三方求解器

═══ G12-A：任意 2D 截面（2026-09-24 加）═══
既有 13 条全部走「条形波导」便捷封装 `neff_strip`。那意味着**任意形状**
（脊形 / 多层 / 非矩形）根本没有合法入口 ⇒ G12 的能力边界被封装卡死。
G12-A 补三层并逐条钉死：
  ⑪ 入口存在：全矢量 `neff_2d` 与半矢量 `neff_2d` 同名可对拍（同一 n² 场双投）
  ⑫ 退化一致：居中矩形 ε 场经任意截面入口 ⇒ 与 neff_strip **逐位同值**（tol 1e-9）
  ⑬ 低对比度互验：同一 SiN n² 场双投，两法 |Δ| ≤ 3e-3（P3 交叉验证网再加一格）
  ⑭ 物理必然性：脊形平板厚度 t↑ ⇒ n_eff **严格单调↑**（slab 分支真的被读进去）
  ⑮ 反自证桩：高对比度脊形上全矢量 ≠ 半矢量（|Δ| > 1e-4；相同 = 缺陷信号）
  ⑯ 脊形网格收敛：h=0.02→0.01 |Δ| ≤ 2e-3
  ⑰ 反向测试：抹掉 slab 层 ⇒ n_eff 必变（> 1e-3），证明 slab 分支是承重的

═══ G12-B：真 3D 空间全矢量（collocated 3D 向量拉普拉斯 FDFD，2026-09-24 加）═══
G12-H/G12-A 是 **2D 截面**（传播方向 γ 用 β² 编码，N ~ nx·ny）。
G12-B 把空间也离散成 3D：**γ 也离散** ⇒ 真三维本征腔模，N ~ (nx-1)(ny-1)(nz-1)
（墙 DOF 剔除）。算子 = collocated 3D 向量拉普拉斯
（K1 = Lx⊗Iy⊗Iz + Ix⊗Ly⊗Iz + Ix⊗Iy⊗Lz；质量矩阵 = 节点 ε 对角），
广义本征问题 KE E = k0² M E。

🔴 为何非 Yee 交错 curl-curl：原型 v4/v5 证明该 PEC 方案下含 (N-2)³ 维伪 DC 零空间
且最低物理本征值发散（不收敛到闭环金）；collocated 向量拉普拉斯正定、无伪零空间、
h→0 收敛到闭环金（rate=2.00）。详见 scripts/g12b_proto6.py。

判什么（全部闭式/物理律 golden，无任何仿真值作 golden）：
  ⑱ 闭式金：均匀立方腔 k0²(1,1,1) = 3(π/L)²/n²（O(h²) 残差 < 1e-2）
            + 激发模比例 k0²(2,1,1)/k0²(1,1,1) = 2（简并比）
  ⑲ 网格收敛 O(h²)：conv3d 收敛阶 ∈ [1.8, 2.2]
  ⑳ 物理必然性：介质加载腔 k0²_diel < k0²_air（同几何）
  ㉑ 反向测试：压扁 x 维 ⇒ k0² 必变（> 1e-2，几何真被读取）

═══ 诚实边界 ═══
  · FDE 2.566 与 2.570410 都是**仿真值**，按本仓铁律**不作 golden**。
    ⑥ 是**外部对标**（相对比较：全矢量比半矢量更接近 FDE），不是绝对正确性声明。
  · 本模块不宣称「SOI 绝对 n_eff 已精确」：残差 +0.004 是 Fallahkhair 离散
    vs Lumerical 曲线网格的方法差，未进一步归因。

运行：python run_full_vector_mode_smoke.py（cwd=lda/）
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
    from lda.lda_solver import full_vector_mode_solver as fv
    from lda.lda_solver import semivec_mode_solver as sv
except ImportError:                             # 以 cwd=lda/ 直跑时
    sys.path.insert(0, os.path.join(_HERE, "lda_solver"))
    import full_vector_mode_solver as fv        # noqa: E402
    import semivec_mode_solver as sv            # noqa: E402

# 🔴 助手单一来源（F-07 · `run_helper_dup_ratchet_smoke` J3/J4）：复用
# `smoke_kit.make_check`，**不得**再添本地 `def check` —— 本文件初版曾复制一份
# 181 字节的局部 check（与 eme_taper/lindblad/mmi_eme/semivec_mode 逐字同源）
# ⇒ J3 54>53、J4 31>30。归一到公共模块即两条棘轮同时回位。
from lda_harness.smoke_kit import make_check  # noqa: E402

# 🔴 计数 + 打印走公共模块（迁移是单点改动）：`make_check` 把计数写进
# `globals()`，`indent=""` + `detail_fmt=" | {d}"` + `detail_on="both"` 逐字复现
# 本文件原有 stdout（`[PASS] name | detail`），返回值 `bool` 亦一致。
_NP = 0
_NF = 0
check = make_check(globals(), ok_key="_NP", bad_key="_NF", indent="",
                   detail_fmt=" | {d}", detail_on="both", return_ok=True)


# 常量：与生产模块 / 实测基线同源
SOI_W, SOI_H = 0.6, 0.22
SOI_NC, SOI_NCL = 3.4777, 1.4441
SIN_W, SIN_H = 1.2, 0.3
SIN_NC, SIN_NCL = 1.9963, 1.4441
SOI_LOCK = fv.SOI_REF_NEFF          # 2.570410（回归锁值，非 golden）
FDE_SOI = 2.566                     # Lumerical FDE（外部对标值，非 golden）
SIN_SV_NEFF_REF = 1.600320          # 半矢量生产档 SiN n_eff（基线）
REG_TOL = 2e-3                      # 回归锁容差
SV_ALIGNED_H = 0.010                # 0.11/0.01=11 ⇒ 几何对齐
SV_FINE_H = 0.0055                  # 0.11/0.0055=20 ⇒ 几何对齐


def _fv_soi(h=None, **kw):
    return fv.neff_strip(SOI_W, SOI_H, 1.55, SOI_NC, SOI_NCL,
                         core_material="Si", clad_material="SiO2",
                         h_grid=(h or fv.H_GRID), L=1.5, **kw)


def _sv_soi(h):
    return sv.neff_strip(SOI_W, SOI_H, 1.55, n_core=SOI_NC, n_clad=SOI_NCL,
                         core_material="Si", clad_material="SiO2",
                         h_grid=h, L=2.0)


def _sv_sin():
    return sv.neff_strip(SIN_W, SIN_H, 1.55, n_core=SIN_NC, n_clad=SIN_NCL,
                         core_material="Si3N4", clad_material="SiO2",
                         h_grid=sv.H_GRID, L=sv.L_WIN)


def main() -> int:
    print("=" * 74)
    print("全矢量本征模求解器 smoke（G12-H · 消除 SOI +0.0276 的凭据守护）")
    print("=" * 74)

    # ① 自校锚（含精确闭式均匀极限）
    try:
        ok_sc, rows = fv.run_selfchecks(verbose=False)
    except Exception as e:                       # noqa: BLE001
        ok_sc, rows = False, []
        print(f"  自检异常：{type(e).__name__}: {e}")
    check("全矢量求解器自校锚全 PASS（闭式均匀极限 + 边界律 + 实证锚 + 收敛"
          " + G12-A 任意截面 + G12-B 真 3D）",
          ok_sc and len(rows) >= 23 and all(r[5] for r in rows),
          f"{sum(1 for r in rows if r[5])}/{len(rows)} 通过"
          + ("" if len(rows) >= 23
             else f"（登记数 {len(rows)} < 23：有自校锚被摘掉）"))

    # ② 精确闭式均匀极限（最强的一条闭式律，单列）
    uni = [r for r in rows if r[0].startswith("uniform[")]
    check("闭式均匀极限精确（max β² = k0²n² − 2λ1，tol 1e-8）",
          bool(uni) and all(r[5] for r in uni),
          " ".join(f"{r[0]}:Δ={r[3]:+.1e}" for r in uni))

    # ③ 回归锁 + 反自证桩
    ne_soi = _fv_soi()
    d_lock = ne_soi - SOI_LOCK
    check("高对比度回归锁：全矢量 SOI 600x220 TE0 = 2.570410",
          math.isfinite(d_lock) and abs(d_lock) <= REG_TOL,
          f"got={ne_soi:.6f} lock={SOI_LOCK:.6f} Δ={d_lock:+.2e} tol={REG_TOL:g}")
    check("baseline |Δ| 非零（未静默回落锁值，非自证桩）",
          math.isfinite(d_lock) and abs(d_lock) > 1e-9,
          f"|Δ|={abs(d_lock):.2e}")

    # ④ 方法差非零（全矢量 ≠ 半矢量）
    sv_al = _sv_soi(SV_ALIGNED_H)
    d_method = abs(ne_soi - sv_al)
    check("方法差非零：全矢量 ≠ 半矢量（> 1.5e-2，非复制粘贴）",
          math.isfinite(d_method) and d_method > 1.5e-2,
          f"全矢量={ne_soi:.6f} 半矢量={sv_al:.6f} 差={d_method:.4f}")

    # ⑤ 半矢量模型偏置复现 + 加密变差（证明非离散误差）
    d_sv_al = sv_al - FDE_SOI
    sv_fine = _sv_soi(SV_FINE_H)
    d_sv_fine = sv_fine - FDE_SOI
    check("半矢量 SOI 模型偏置复现（对齐网格 ≥ +0.02）",
          math.isfinite(d_sv_al) and d_sv_al >= 2e-2,
          f"h={SV_ALIGNED_H} n={sv_al:.6f} Δ(FDE)={d_sv_al:+.4f}")
    check("半矢量加密更差（|Δ(FDE)| 随 h→0 不降 ⇒ 约束模型误差，非离散误差）",
          math.isfinite(d_sv_fine) and abs(d_sv_fine) >= abs(d_sv_al),
          f"h={SV_FINE_H} n={sv_fine:.6f} Δ(FDE)={d_sv_fine:+.4f} "
          f"≥ h={SV_ALIGNED_H} 的 {d_sv_al:+.4f}")

    # ⑥ 全矢量消除偏置（外部对标，非 golden）
    d_fv = abs(ne_soi - FDE_SOI)
    ratio = (abs(d_sv_al) / d_fv) if d_fv > 0 else float("inf")
    check("全矢量消除偏置：|Δ(FDE)| ≤ 5e-3 且 ≤ 1/5 半矢量偏置",
          math.isfinite(d_fv) and d_fv <= 5e-3 and ratio >= 5.0,
          f"|Δ(FDE)|={d_fv:.4f} vs 半矢量 {abs(d_sv_al):.4f} "
          f"（改善 {ratio:.1f}×）")

    # ⑦ 低对比度退化
    fv_sin = fv.neff_strip(SIN_W, SIN_H, 1.55, SIN_NC, SIN_NCL, L=2.4)
    sv_sin = _sv_sin()
    d_sin = fv_sin - sv_sin
    check("低对比度退化：SiN 全矢量 vs 半矢量 |Δ| ≤ 3e-3",
          math.isfinite(d_sin) and abs(d_sin) <= 3e-3,
          f"全矢量={fv_sin:.6f} 半矢量={sv_sin:.6f} Δ={d_sin:+.2e}")

    # ⑧ 判据窗口上界（反向测试，两个方向）
    for sgn, tag in ((+1.0, "+5%"), (-1.0, "-5%")):
        try:
            v = fv.neff_strip(SOI_W, SOI_H, 1.55, SOI_NC * (1.0 + sgn * 0.05),
                              SOI_NCL, core_material="Si", clad_material="SiO2",
                              h_grid=fv.H_GRID, L=1.5)
            sig = abs(v - SOI_LOCK)
        except Exception as e:                   # noqa: BLE001
            v, sig = float("nan"), float("nan")
            print(f"  n_core{tag} 求解异常：{type(e).__name__}: {e}")
        check(f"判据窗口上界成立（n_core{tag} 信号 > 回归锁 tol，tol 未放水）",
              math.isfinite(sig) and sig > REG_TOL,
              f"n={v:.6f} 信号={sig:.4f} > tol={REG_TOL:g}"
              f"（{sig / REG_TOL:.1f}× 余量）")

    # ⑨ 网格收敛
    conv = [r for r in rows if r[0].startswith("convergence[")]
    check("网格收敛：h=0.010→0.005 |Δ| ≤ 2e-3（加密趋稳）",
          bool(conv) and all(r[5] for r in conv),
          " ".join(f"{r[0]}:Δ={r[3]:.1e}" for r in conv))

    # ⑩ 红线段：生产模块 import 行不得出现第三方求解器
    src = open(os.path.join(_HERE, "lda_solver", "full_vector_mode_solver.py"),
               encoding="utf-8").read()
    bad = [tok for tok in ("modesolver", "gdsfactory", "meep", "tidy3d", "lumapi",
                          "femwell", "sax", "EMpy", "pyGDM")
           if any(tok in ln for ln in src.splitlines()
                  if ln.strip().startswith(("import ", "from ")))]
    check("红线段：生产模块 import 行无第三方求解器（自研，参考实现仅作外部 oracle）",
          not bad, f"命中={bad}" if bad else "无命中")

    # ══════════════ G12-A：任意 2D 截面 ══════════════
    # ⑪ 入口可对拍（成本 0）：全矢量与半矢量都有同名 neff_2d ⇒ 同一 n² 场可双投
    sv_has_same_entry = callable(getattr(sv, "neff_2d", None))
    check("G12-A ⑪ 任意截面入口存在且与半矢量同签名（同一 n² 场可双投 ⇒ 方法学独立）",
          callable(getattr(fv, "neff_2d", None)) and sv_has_same_entry
          and "neff_2d" in getattr(fv, "__all__", []),
          f"fv.neff_2d={'有' if callable(getattr(fv,'neff_2d',None)) else '无'} "
          f"sv.neff_2d={'有' if sv_has_same_entry else '无'}")

    # ⑫ 退化一致（新入口没改坏老路径的机器锁）
    deg = [r for r in rows if r[0].startswith("arb_degenerate[")]
    check("G12-A ⑫ 退化一致：任意截面入口 == 条形封装（tol 1e-9，逐位同值）",
          bool(deg) and all(r[5] for r in deg),
          " ".join(f"{r[0]}:Δ={r[3]:.1e}" for r in deg) or "无该行")

    # ⑬ 低对比度互验（同一份场，两种物理模型）
    alc = [r for r in rows if r[0].startswith("arb_lowcontrast[")]
    check("G12-A ⑬ 同一 n² 场双投：低对比度 SiN 全矢量 vs 半矢量 |Δ| ≤ 3e-3",
          bool(alc) and all(r[5] for r in alc),
          " ".join(f"{r[0]}:Δ={r[3]:.1e}" for r in alc) or "无该行")

    # ⑭ 物理必然性：slab 厚度 ↑ ⇒ n_eff 严格单调 ↑
    mono = [r for r in rows if r[0].startswith("rib_mono[")]
    check("G12-A ⑭ 物理必然性：脊形 slab 厚度↑ ⇒ n_eff 严格单调↑"
          f"（{len(mono)} 段全部 >0）",
          len(mono) >= 3 and all(r[5] for r in mono),
          " ".join(f"{r[0]}:Δ={r[3]:+.2e}" for r in mono) or "无该行")

    # ⑮ 反自证桩：高对比度脊形上两法必须不同
    anti = [r for r in rows if r[0].startswith("rib_antistake[")]
    check("G12-A ⑮ 反自证桩：高对比度脊形上全矢量 ≠ 半矢量（|Δ| > 1e-4）",
          bool(anti) and all(r[5] for r in anti),
          " ".join(f"{r[0]}:|Δ|={r[3]:.2e}（须 > {r[4]:g}）" for r in anti) or "无该行")

    # ⑯ 脊形网格收敛
    rconv = [r for r in rows if r[0].startswith("rib_conv[")]
    check("G12-A ⑯ 脊形网格收敛：h=0.02→0.01 |Δ| ≤ 2e-3",
          bool(rconv) and all(r[5] for r in rconv),
          " ".join(f"{r[0]}:Δ={r[3]:.1e}" for r in rconv) or "无该行")

    # ⑰ 反向测试（读 ⑨b 行，不再另解一次）：slab 分支承重
    load = [r for r in rows if r[0].startswith("rib_slab_load[")]
    check("G12-A ⑰ 反向测试：抹掉 slab 层 ⇒ n_eff 必变（> 1e-3，slab 分支承重）",
          bool(load) and all(r[5] for r in load),
          " ".join(f"{r[0]}:|Δ|={r[3]:.2e}（须 > {r[4]:g}）" for r in load)
          or "无该行")

    # ═══════════════ G12-B：真 3D 空间全矢量本征腔模 ═══════════════
    # ⑱ 闭式物理律（最强）：均匀立方腔 k0²(1,1,1) = 3(π/L)²/n²（O(h²) 残差）+ 激发模比例
    cb = [r for r in rows if r[0].startswith("cubic[")]
    check("G12-B ⑱ 闭式金：立方腔 k0²(1,1,1)=3(π/L)²/n² 且 k0²(2,1,1)/k0²(1,1,1)=2",
          bool(cb) and all(r[5] for r in cb),
          " ".join(f"{r[0]}:d={r[3]:+.2e}" for r in cb) or "无该行")

    # ⑲ 网格收敛 O(h²)
    cb2 = [r for r in rows if r[0].startswith("conv3d[")]
    check("G12-B ⑲ 网格收敛 O(h²)：conv3d 收敛阶 ∈ [1.8, 2.2]",
          bool(cb2) and all(r[5] for r in cb2),
          " ".join(f"{r[0]}:rate={r[3]:.2f}" for r in cb2) or "无该行")

    # ⑳ 物理必然性：介质加载腔 k0² < 同几何空腔
    diel = [r for r in rows if r[0].startswith("diel_lt_air[")]
    check("G12-B ⑳ 物理判据：介质加载腔 k0²_diel < k0²_air（同几何）",
          bool(diel) and all(r[5] for r in diel),
          " ".join(f"{r[0]}:d={r[3]:+.3e}" for r in diel) or "无该行")

    # ㉑ 反向测试：压扁一维 ⇒ 本征值必变（几何真被读取）
    shape = [r for r in rows if r[0].startswith("shape[")]
    check("G12-B ㉑ 反向测试：压扁 x 维 ⇒ k0² 必变（> 1e-2，几何承重）",
          bool(shape) and all(r[5] for r in shape),
          " ".join(f"{r[0]}:|Δ|={r[3]:.2e}" for r in shape) or "无该行")

    n_fail = _NF
    print()
    print(f"全矢量本征模求解器 smoke：{_NP}/{_NP + _NF} PASS")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
