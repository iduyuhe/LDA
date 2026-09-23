"""v0.9.132 P3-T3.1 · 横向交叉验证矩阵 smoke（指标 **M3** · 自证短板闭合）。

## 为什么建它

469 锚纪律里**唯一成体系的空白** = 横向交叉验证网：本仓有 13 项 D3（「算得对」），
但「有多少个「器件 × 物理量」真被**两个方法学独立的求解器**互验过」此前**无人能答**
—— 现有交叉验证散落在各锚内部（golden↔candidate），从未集中登记，也无常驻门禁。

本 smoke 把这件事实**机器化**：集中登记「同一器件 × 同一物理量，≥2 个方法学独立的
自研求解器」的格，逐格实测误差并钉成判据。DAC 2026 的结论（"autonomy scales with
the quality of your verifier"）正指向这里。

## 格的三件套（每格必须有）

  ① **独立性声明**：两求解器的**方法学差异**（非换后端）。排除清单见
     `BACKEND_SWAP_DENYLIST` —— `fdtd3d` ↔ `fdtd3d_numba` ↔ `fdtd3d_torch` 属
     「同算法换后端」，对拍只能验实现一致性，**不构成方法学独立**，不得入矩阵
     （防虚假繁荣；这正是规划 T3.2 ② 的要求）。
  ② **误差如实报出**：每格给出 |cand − ref| 的**相对残差**，FAIL 也登记（不藏）。
  ③ **判据 D**（数值侧精化参数扫描）：`粗端残差 > 1e-13`（未落恒等地板）
     且**严格单调降** 且 `细端 < tol_rel`。

## 🔴 一条实测得出的分类规律（本批血案，勿忘）

「解析/闭式 ↔ 数值」的格**不一定有判据 D**：

  · 若误差由**数值离散化**主导（网格/步长/采样数）⇒ 扫精化参数**误差变** ⇒
    有判据 D。例：Bragg（N）、EME（dz）、读出积分（nx）、谐振器（N）、
    Lindblad RK4（n_steps）、MZM 零点拟合（n_voltage）。
  · 若误差由**解析式的固有近似**主导 ⇒ 扫精化参数**误差不变** ⇒ **无判据 D**。
    例：Transmon f01（Koch 渐近式，N=10..40 残差恒 1.109e-02）、
    χ（Blais 修正式，M=10..40 残差恒 5.6879e-05）。

对后者本 smoke **不冒充**有判据 D：登记为 `kind="model_limited"`，并**必须**附上
「扫参数残差不变」的实测证据（由 `check_cells` 的 model_limited 分支以**相对口径**
`(max−min)/max < 1e-6` 断言）—— 把「无判据 D」也钉成可证伪断言，这样「矩阵 6 格的
判据 D」是实数出来的，不是声称的。

运行：python run_cross_solver_matrix_smoke.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

from lda_harness.smoke_kit import make_check                    # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

# ---------------------------------------------------------------------------
# 🔴 排除清单：「同算法换后端」不算方法学独立（规划 T3.2 ②）
# ---------------------------------------------------------------------------
BACKEND_SWAP_DENYLIST = (
    ("fdtd3d", "fdtd3d_numba"),
    ("fdtd3d", "fdtd3d_torch"),
    ("fdtd3d_numba", "fdtd3d_torch"),
    ("fdtd3d_waveguide", "fdtd3d_waveguide_numba"),
    ("benchmark_fdtd3d", "fdtd3d"),
)
_DENY_TOKENS = ("numba", "torch", "backend")


# ---------------------------------------------------------------------------
# 探针（每格一个；返回 (ref, cand)，门禁只做「误差 + 判据 D」，不参与物理）
# ---------------------------------------------------------------------------
def _p_bragg(param):
    """Bragg 带隙中心 λ_B（µm）。ref=闭式 2·n_eff·Λ（运动学）"""
    from lda_solver.bragg_solver import lambda_B_bloch
    n_eff, period, m = 2.4, 0.323, 0.004
    return 2.0 * n_eff * period, float(lambda_B_bloch(n_eff, period, m, int(param)))


def _p_eme_taper(param):
    """绝热锥度传输率 T（无量纲）。ref=绝热极限 1.0（物理上界）"""
    from lda_solver.eme_taper import taper_transmission
    return 1.0, float(taper_transmission(0.5, 0.3, 200.0, 1.55, 2.2199, 1.44,
                                         dz=float(param)))


def _p_readout(param):
    """单发读出保真度 F（无量纲）。ref=erfc 闭式"""
    from lda_solver.readout_fidelity_quad import readout_fidelity_quad
    from lda_harness.b30_readout_anchor import b30_readout_fidelity
    return float(b30_readout_fidelity()), float(readout_fidelity_quad(nx=int(param)))


def _p_resonator(param):
    """λ/4 谐振器最低模 f0（Hz）。ref=连续极限闭式 1/(4l√(L′C′))"""
    from lda_solver.resonator_solver import f_quarter_wave_closed_form, _discrete_f0
    Lp, Cp, l = 0.4e-6, 1.5e-10, 3000e-6
    return (float(f_quarter_wave_closed_form(Lp, Cp, l)),
            float(_discrete_f0(Lp, Cp, l, int(param))))


def _p_lindblad(param):
    """平均门保真度 F_avg（无量纲）。ref=解析闭式 (3+2e^{-t/T2}+e^{-t/T1})/6"""
    from lda_solver.lindblad_gate_fidelity import average_gate_fidelity, closed_form
    T1, T2, t = 80.0, 80.0, 50.0
    return (float(closed_form(T1, T2, t)),
            float(average_gate_fidelity(T1, T2, t, n_steps=int(param))))


def _p_mzm_vpi(param):
    """MZM 半波电压 Vπ（V）。ref=闭式 λ₀d/(2n³rΓL)"""
    from lda_solver.mzm_vpi_nullfit import mzm_vpi_nullfit
    lam, d, n_eff, r_eff, gamma, L = 1.55e-6, 8.0e-6, 2.2, 30.8e-12, 0.5, 10000e-6
    ref = (lam * d) / (2.0 * (n_eff ** 3) * r_eff * gamma * L)
    return float(ref), float(mzm_vpi_nullfit(n_voltage=int(param)))


def _p_slab_te(param):
    """平板波导 TE0 模 n_eff（无量纲）。ref=解析超越方程（brentq 求根）"""
    import numpy as np
    from lda_solver.mmi_eme import slab_te_neff_analytic, slab_modes
    from lda_solver.mmi_eme import N_CORE_2D, N_CLAD_2D
    n_core, n_clad, d_um, wl = N_CORE_2D, N_CLAD_2D, 0.22, 1.55
    dl = float(param)
    ny = int(round(6.0 / dl))
    ys = (np.arange(ny) - ny / 2.0) * dl
    eps_y = np.where(np.abs(ys) <= d_um / 2.0, n_core ** 2, n_clad ** 2)
    neffs, _modes = slab_modes(eps_y, dl, wl, n_clad)
    return (float(slab_te_neff_analytic(n_core, n_clad, d_um, wl, m=0)),
            float(neffs[0]))


def _p_transmon_koch(param):
    """Transmon f01（GHz）。ref=Koch 解析 —— kind=model_limited（扫 N 残差不变）"""
    from lda_solver.transmon_solver import koch_f01, solve_transmon
    E_J, E_C = 20.0, 0.25
    return float(koch_f01(E_J, E_C)), float(solve_transmon(E_J, E_C, N=int(param))["f01"])


def _p_chi_blais(param):
    """色散读出 χ（GHz）。ref=Blais 三能级修正解析式 —— kind=model_limited"""
    from lda_solver.qubit_resonator_solver import solve_qubit_resonator
    r = solve_qubit_resonator(M=int(param))
    return float(r["chi_3level_ghz"]), float(r["chi_num_ghz"])


def _p_mmi_excess(param):
    """MMI 1×2 过量损耗（dB）。ref=2D-EIM EME —— 跨求解器（FDTD ↔ EME）"""
    from lda_solver.fdtd2d_mmi import cross_check_with_eme
    d = cross_check_with_eme(dl=float(param))
    return float(d["eme_db"]), float(d["fdtd_db"])


# ---------------------------------------------------------------------------
# 矩阵：每格 = 器件 × 物理量 × 求解器A ↔ 求解器B
#   kind="convergent"     ⇒ 有判据 D（扫参数残差严格单调降）
#   kind="model_limited"  ⇒ 无判据 D（解析近似主导）⇒ 必附「残差不变」实测证据
# ---------------------------------------------------------------------------
CELLS = [
    {
        "id": "X1-BRAGG", "device": "波导 Bragg 光栅", "metric": "带隙中心 λ_B (µm)",
        "solver_a": "闭式 2·n_eff·Λ（相位匹配，运动学）",
        "solver_b": "反周期 Bloch 广义本征值（全波谱，动力学）",
        "independence": "闭式运动学 vs 广义本征值对角化（不同物理表述 + 不同数值路径）",
        "kind": "convergent", "param": "N(每周期采样)", "values": (120, 240, 480),
        "tol_rel": 1e-2, "probe": _p_bragg,
        "note": "B15 独立候选；N=960 有 LAPACK 数值地板后反升（同 B22）⇒ 只取收敛段",
    },
    {
        "id": "X2-EME-TAPER", "device": "绝热锥度", "metric": "传输率 T",
        "solver_a": "绝热极限 T→1（物理上界）",
        "solver_b": "EME 本征模展开（逐片模传播 + 重叠积分）",
        "independence": "连续极限上界 vs 分片离散模态展开（后者含非绝热相干项）",
        "kind": "convergent", "param": "dz(片长 µm)", "values": (0.8, 0.4, 0.2),
        "tol_rel": 1e-2, "probe": _p_eme_taper,
        "note": "B8；(1−T) 一阶收敛 ∝ dz（实测 2.9e-5→1.4e-5→7.1e-6）",
    },
    {
        "id": "X3-READOUT", "device": "量子比特单发读出", "metric": "保真度 F",
        "solver_a": "erfc(SNR/√2) 闭式（解析）",
        "solver_b": "两高斯重叠梯形数值积分",
        "independence": "特殊函数闭式 vs 被积函数数值求积（非平凡对称凸起，不退化为恒等）",
        "kind": "convergent", "param": "nx(积分网格)", "values": (2001, 20001, 200001),
        "tol_rel": 1e-6, "probe": _p_readout,
        "note": "B30；残差 9.4e-7→9.4e-9→9.4e-11（O(h²) 梯形）",
    },
    {
        "id": "X4-RESONATOR", "device": "超导 λ/4 谐振器", "metric": "最低模 f0 (Hz)",
        "solver_a": "连续极限闭式 1/(4l√(L′C′))",
        "solver_b": "传输线离散化三对角严格本征值",
        "independence": "连续极限解 vs 离散集总 LC 本征问题（网格色散 O(dx²)）",
        "kind": "convergent", "param": "N(分段数)", "values": (50, 100, 200, 400),
        "tol_rel": 1e-2, "probe": _p_resonator,
        "note": "D-35 同构；N=400 相对残差 1.25e-3（与模块自述 0.125% 一致）",
    },
    {
        "id": "X5-LINDBLAD", "device": "单量子比特门", "metric": "平均门保真度 F_avg",
        "solver_a": "解析闭式 (3+2e^{−t/T2}+e^{−t/T1})/6",
        "solver_b": "Lindblad 主方程 RK4 数值传播 → PTM",
        "independence": "闭式解 vs 主方程数值积分（RK4 截断 O(h⁴)）",
        "kind": "convergent", "param": "n_steps(RK4 步数)", "values": (25, 50, 100, 200),
        "tol_rel": 1e-9, "probe": _p_lindblad,
        "note": "B10；细端 1.33e-13 已近双精度地板 ⇒ 判据 D 只认**粗端** >1e-13",
    },
    {
        "id": "X6-MZM-VPI", "device": "MZM 调制器", "metric": "半波电压 Vπ (V)",
        "solver_a": "闭式 λ₀d/(2n³rΓL)（解析反解）",
        "solver_b": "T(V)=cos²(Δφ) 首个传输零点的数值测量（采样+抛物线定顶）",
        "independence": "对 T(V)=0 解析反解 vs 对模拟观测谱数值测零点（候选从不求值闭式）",
        "kind": "convergent", "param": "n_voltage(电压网格)", "values": (50, 100, 200, 400),
        "tol_rel": 1e-3, "probe": _p_mzm_vpi,
        "note": "B28；零点附近 cos² 含四次修正 ⇒ 顶点误差 O(ΔV³)，N 加倍误差降 ~8×",
    },
    {
        "id": "X7-MMI-EXCESS", "device": "MMI 1×2 分束器", "metric": "过量损耗 (dB)",
        "solver_a": "2D-EIM 本征模展开 EME",
        "solver_b": "2D FDTD 全场（CW 稳态 + 芯区能流积分）",
        "independence": "频域模态展开 vs 时域全波（两套完全不同的场求解器）",
        "kind": "convergent", "param": "dl(网格 µm)", "values": (0.20, 0.15, 0.10),
        "tol_rel": 2e-1, "probe": _p_mmi_excess,
        "note": ("本仓唯一的真跨求解器格（FDTD ↔ EME）；残差 33.96→3.60→0.649 dB 严格"
                 "单调降，但**细端 rel=0.171 ⇒ 两法仅一致到 17%**（2D FDTD 网格限制）"
                 "—— 如实登记，不声称已进 10%"),
    },
    {
        "id": "M1-TRANSMON-KOCH", "device": "Transmon 量子比特", "metric": "f01 (GHz)",
        "solver_a": "Koch2007 解析色散近似 √(8E_JE_C)−E_C",
        "solver_b": "电荷基约瑟夫森哈密顿量严格对角化",
        "independence": "渐近解析式 vs 严格数值对角化（两条独立路径）",
        "kind": "model_limited", "param": "N(电荷基截断)", "values": (10, 20, 30, 40),
        "tol_rel": 3e-3, "probe": _p_transmon_koch,
        "note": ("🔴 实测扫 N 残差**不变**（1.109e-02 恒值）：误差 = Koch 渐近式固有近似，"
                 "非数值离散 ⇒ **无判据 D**，如实登记不冒充"),
    },
    {
        "id": "M2-CHI-BLAIS", "device": "transmon-resonator 色散读出", "metric": "χ (GHz)",
        "solver_a": "Blais 三能级修正解析式",
        "solver_b": "TLS 严格对角化",
        "independence": "修正解析式 vs 严格对角化（α 修正必要性由二者差确认）",
        "kind": "model_limited", "param": "M(截断维)", "values": (10, 20, 30, 40),
        "tol_rel": 3e-2, "probe": _p_chi_blais,
        "note": ("🔴 实测扫 M 残差**不变**（5.6879e-05 恒值）⇒ 误差由解析式固有近似主导，"
                 "**无判据 D**，如实登记"),
    },
]


# ---------------------------------------------------------------------------
# 域标签表（判据 ⑦ 用）
# ---------------------------------------------------------------------------
# 🔴 v0.9.132 修（「标签≠行为」同型）：⑦ 原用 **id 前缀硬编码** 筛域
#   （`startswith(("X1","X2","X7"))` / `("X3","X4","X5","M1","M2")`），而
#   **X6-MZM-VPI（MZM 调制器 · 光子器件）既不在光子组也不在量子组** ——
#   两组都「≥2」照样全绿 ⇒ **域标签与器件事实脱钩**。改为**显式表 + 双向完备**
#   断言：注册格漏标（missing）或表里多出孤儿行（orphan）都立即红。
CELL_DOMAIN = {
    # 光子域（PDA）
    "X1-BRAGG": "photonic",
    "X2-EME-TAPER": "photonic",
    "X6-MZM-VPI": "photonic",
    "X7-MMI-EXCESS": "photonic",
    # 量子域（QEDA）
    "X3-READOUT": "quantum",
    "X4-RESONATOR": "quantum",
    "X5-LINDBLAD": "quantum",
    "M1-TRANSMON-KOCH": "quantum",
    "M2-CHI-BLAIS": "quantum",
}


# ---------------------------------------------------------------------------
# 🔴 实测否决的候选格（本项目最容易被忽略的一类诚实：**没进去的也要留痕**）
# ---------------------------------------------------------------------------
# 下面三项都「看上去像交叉验证格」但对拍**实测不成立**。登记它们的价值：
#   ① 证明矩阵不是「凑数收录」（判据 D 真会拦下来）；
#   ② 把「规划以为能落地、实测落不了地」的事实钉在册上，防下一轮重复踩。
# `auto_repro=True` ⇒ 门禁**每次实跑复现**该否决（必须便宜）；否则只登记实测
# 数字 + 复现命令（对拍成本过高，如 2D FDTD 单次数十秒）。
EXCLUDED_CANDIDATES = [
    {
        "id": "E1-SLAB-TE", "auto_repro": True,
        "candidate": ("平板波导 TE0 n_eff：解析超越方程（brentq 求根）↔ "
                      "有限差分矩阵本征值（eigh）"),
        "why_not": ("扫 dl 残差**不单调**（1.016e-3 → 1.178e-2 → 5.913e-3）：细网格下"
                    "Dirichlet 窗口截断效应与解析式的半无限包层假设不再可比 ⇒ "
                    "**判据 D 不成立**，不得入矩阵"),
        "repro": "见 ⑩：扫 (0.02, 0.01, 0.005)，断言**不**严格单调",
        "measured_on": "2026-09-23",
    },
    {
        "id": "E2-DC-COUPLER", "auto_repro": False,
        "candidate": ("DC 定向耦合器 κ：FDFD 超模（oracle_coupler.coupling_oracle）↔ "
                      "2D FDTD 反解（fdtd2d_coupler.run_dc_transmission）"),
        "why_not": ("**定量对拍不成立**：超模 κ=0.034802 rad/µm vs 2D FDTD 反解 "
                    "κ=0.101610 rad/µm ⇒ rel=**1.92（192%）**。这解释了 `fdtd2d_coupler` "
                    "docstring 自述的「D-23 同款大数小差问题，2D 下更敏感」—— 而该 docstring "
                    "第 15 行承诺的「CMT 定量对拍容差放 40%」**从未实装**（实现只用 FDTD "
                    "自洽趋势判据）⇒ 正是 T3.2 要处置的松容差/文档漂移。"),
        "repro": ("coupling_oracle(0.5,0.22,0.3,3.48,1.44,1.55)['kappa'] vs "
                  "run_dc_transmission(n_points=5, span_um=0.04, dl_factor=12)['kappa_fdtd']"),
        "measured_on": "2026-09-23",
    },
    {
        "id": "E3-RING-FSR", "auto_repro": False,
        "candidate": ("环谐振器 FSR：解析 λ²/(n_g·2πR) ↔ 2D FDTD drop 谱峰间距"),
        "why_not": ("本次档位（n_points=9、dl_factor=12、transient=1200）FDTD 采样不足以"
                    "解析出两个谐振峰 ⇒ `fsr_fdtd=0.0 nm`、rel=1.0、accepted=False。"
                    "**不是物理否定，是参数档位成本问题**（47s/次，且需更多采样点才能出双峰）。"
                    "另注：该格即使出双峰，其判据 `tol_rel=0.30`（30%）也偏松 —— 根因是"
                    "「2D 平板 n_g≈材料 n≠3D 环设计 n_g」的口径差（模块 docstring 已声明），"
                    "故该格入矩阵前须先解决**参照口径**，而非只调网格。"),
        "repro": "verify_ring_fdtd(R_um=10, n_points=9, dl_factor=12, transient_cycles=1200)",
        "measured_on": "2026-09-23",
    },
]


# ---------------------------------------------------------------------------
# 判据
# ---------------------------------------------------------------------------
def _rel_err(ref, cand):
    d = abs(cand - ref)
    return d, (d / abs(ref) if ref else d)


def _strictly_decreasing(vals):
    return all(b < a for a, b in zip(vals, vals[1:]))


def run_matrix():
    print("=== 横向交叉验证矩阵（M3）===")
    print("  格数 %d（convergent %d / model_limited %d），排除清单 %d 项"
          % (len(CELLS),
             sum(1 for c in CELLS if c["kind"] == "convergent"),
             sum(1 for c in CELLS if c["kind"] == "model_limited"),
             len(BACKEND_SWAP_DENYLIST)))

    registry = []
    for c in CELLS:
        rows = []
        for p in c["values"]:
            t0 = time.time()
            ref, cand = c["probe"](p)
            abs_e, rel_e = _rel_err(ref, cand)
            rows.append({"param": p, "ref": ref, "cand": cand,
                         "abs_err": abs_e, "rel_err": rel_e,
                         "seconds": round(time.time() - t0, 3)})
        registry.append({
            "id": c["id"], "device": c["device"], "metric": c["metric"],
            "solver_a": c["solver_a"], "solver_b": c["solver_b"],
            "independence": c["independence"], "kind": c["kind"],
            "param": c["param"], "tol_rel": c["tol_rel"], "note": c["note"],
            "values": list(c["values"]),
            "rows": rows,
            "final_rel_err": rows[-1]["rel_err"],
            "final_abs_err": rows[-1]["abs_err"],
        })
    return registry


def check_cells(registry):
    by_id = {c["id"]: c for c in registry}
    n_conv = 0
    for c in registry:
        rows = c["rows"]
        rels = [r["rel_err"] for r in rows]
        tail = ("%s=%s ⇒ rel_err %s" % (c["param"], list(c["values"]),
                                        " → ".join("%.3e" % r for r in rels)))
        if c["kind"] == "convergent":
            n_conv += 1
            check("⑵ %s 有判据 D：%s" % (c["id"], tail),
                  _strictly_decreasing(rels) and rels[0] > 1e-13 and rels[-1] < c["tol_rel"],
                  "单调降=%s 粗端>1e-13=%s 细端<tol=%s"
                  % (_strictly_decreasing(rels), rels[0] > 1e-13, rels[-1] < c["tol_rel"]))
        else:
            spread = max(rels) - min(rels)
            # 「残差不变」判在**相对口径**：浮点噪声级（<1e-6 相对）才算不变。
            # 🔴 首版用绝对 1e-12 阈值 ⇒ M2（Δ=1.69e-11，纯浮点噪声）被误判为
            #    「变了」而假红（M1 的 9.1e-13 侥幸过）—— 判据阈值必须配口径。
            unchanged = (max(rels) - min(rels)) / max(max(rels), 1e-300) < 1e-6
            check("⑵ %s 如实登记为 model_limited（扫参数残差**不变**，Δrel=%.3e）"
                  % (c["id"], spread / max(max(rels), 1e-300)),
                  unchanged and rels[-1] < c["tol_rel"],
                  "%s；残差不变 ⇒ 误差由解析式固有近似主导，非离散误差 ⇒ 无判据 D" % tail)
    return by_id, n_conv


def main() -> int:
    t0 = time.time()
    registry = run_matrix()
    by_id, n_conv = check_cells(registry)

    # ① 矩阵规模（M3 出口判据：≥6 格，且**有判据 D** 的格 ≥6）
    check("① 矩阵格数 ≥6（M3 出口判据）", len(registry) >= 6,
          "实测 %d 格" % len(registry))
    check("① 其中有判据 D 的格 ≥6", n_conv >= 6,
          "实测 %d 格（model_limited %d 格不计入）" % (n_conv, len(registry) - n_conv))

    # ③ 独立性：每格必须声明方法学差异（非换后端），且不在排除清单内
    for c in registry:
        banned = [t for t in _DENY_TOKENS if t in (c["solver_a"] + c["solver_b"]).lower()]
        check("③ %s 方法学独立声明非空且不含换后端字样" % c["id"],
              bool(c["independence"].strip()) and not banned, "banned=%s" % banned)
    ids = {c["id"] for c in registry}
    dup = len(ids) != len(registry)
    check("③ 格 id 唯一", not dup, "重复 id" if dup else "")

    # ④ 误差全部如实报出（无 NaN/无隐藏）
    bad = [c["id"] for c in registry
           if any((not math.isfinite(r["abs_err"])) for r in c["rows"])]
    check("④ 每格误差都已数值报出（无 NaN/Inf）", not bad, "坏格 %s" % bad)

    # ⑤ FAIL 也登记：报告里每格都有 rows（不论残差大小），且记录 final_rel_err
    miss = [c["id"] for c in registry if not c["rows"] or "final_rel_err" not in c]
    check("⑤ 每格残差均入册（FAIL 也登记，不藏）", not miss, "缺 %s" % miss)

    # ⑥ 排除清单生效：矩阵内不得出现被禁的「同算法换后端」对
    viol = []
    for c in registry:
        pair = (c["solver_a"].lower(), c["solver_b"].lower())
        for a, b in BACKEND_SWAP_DENYLIST:
            if (a in pair[0] and b in pair[1]) or (b in pair[0] and a in pair[1]):
                viol.append(c["id"])
    check("⑥ 矩阵内无「同算法换后端」格（防虚假繁荣）", not viol, "违规 %s" % viol)

    # ⑦ 覆盖面：域标签**双向完备** + 划分互斥 + 光子/量子各 ≥2 格
    ids = [c["id"] for c in registry]
    missing = [i for i in ids if i not in CELL_DOMAIN]
    orphan = [k for k in CELL_DOMAIN if k not in ids]
    check("⑦a 域标签表**双向完备**（无漏标格 / 无孤儿行）",
          not missing and not orphan,
          "漏标 %s / 孤儿 %s" % (missing, orphan))
    photonic = [i for i in ids if CELL_DOMAIN.get(i) == "photonic"]
    quantum = [i for i in ids if CELL_DOMAIN.get(i) == "quantum"]
    check("⑦b 域划分**互斥且并集 == 全部注册格**",
          (not missing) and len(photonic) + len(quantum) == len(ids),
          "光子 %d + 量子 %d vs 总 %d" % (len(photonic), len(quantum), len(ids)))
    check("⑦c 覆盖面：光子域 ≥2 格 且 量子域 ≥2 格",
          len(photonic) >= 2 and len(quantum) >= 2,
          "光子 %d / 量子 %d" % (len(photonic), len(quantum)))

    # ⑨ 实测否决项登记完备（无解也留痕：id / 候选 / 理由 / 复现 / 日期）
    bad_ex = []
    for e in EXCLUDED_CANDIDATES:
        need = ("id", "candidate", "why_not", "repro", "measured_on")
        if any(not str(e.get(k, "")).strip() for k in need):
            bad_ex.append(e.get("id", "?"))
    check("⑨ 实测否决项登记完备（%d 项，各含 候选/理由/复现/日期）"
          % len(EXCLUDED_CANDIDATES), not bad_ex, "缺字段 %s" % bad_ex)

    # ⑩ E1 否决**自动复现**：扫 dl 残差必须**不**严格单调（否则该否决理由失效）
    e1 = [e for e in EXCLUDED_CANDIDATES if e.get("auto_repro")]
    for e in e1:
        dl_scan = []
        for dl in (0.02, 0.01, 0.005):
            ref, cand = _p_slab_te(dl)
            dl_scan.append(abs(cand - ref) / abs(ref))
        check("⑩ %s 否决理由可复现：扫 dl 残差**不**严格单调" % e["id"],
              not _strictly_decreasing(dl_scan),
              "rel_err %s" % " → ".join("%.3e" % v for v in dl_scan))

    # ⑧ 红线：判决依据零 LLM / 零网络。
    # 🔴 扫的是**登记数据**（矩阵 + 否决项）而非本文件源码 —— 首版扫源码会把
    #    本判据自己的 token 列表也扫进去 ⇒ 恒 FAIL（判据扫到自己的血案，同 P2 ⑪）。
    payload = (json.dumps(registry, ensure_ascii=False)
               + json.dumps(EXCLUDED_CANDIDATES, ensure_ascii=False)).lower()
    net_pat = ("openai", "anthropic", "chatgpt", "requests.", "http://", "https://")
    hit = [t for t in net_pat if t in payload]
    check("⑧ 判决依据（矩阵 + 否决项登记文本）零 LLM / 零网络引用", not hit,
          "命中 %s" % hit)

    elapsed = time.time() - t0
    report = {
        "p3_t31": "cross-solver verification matrix",
        "cells_total": len(registry),
        "cells_with_criterion_D": n_conv,
        "backend_swap_denylist": [list(x) for x in BACKEND_SWAP_DENYLIST],
        "excluded_candidates": EXCLUDED_CANDIDATES,
        "cells": registry,
        "elapsed_s": round(elapsed, 2),
    }
    out_dir = os.path.join(_HERE, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cross_solver_matrix_report.json")
    from lda_harness import deterministic as _det
    _det.write_json(out_path, report)
    print("\n报告：%s" % out_path)

    print("\n=== 矩阵一览（%d 格 · 判据 D %d 格）===" % (len(registry), n_conv))
    for c in registry:
        print("  %-16s %-26s %-30s rel_err %.3e (%s)"
              % (c["id"], c["device"], c["metric"], c["final_rel_err"], c["kind"]))
    print("\nP3-T3.1 横向交叉验证矩阵 smoke：%s  (%.1fs)"
          % ("ALL GREEN" if _FAIL == 0 else "HAS FAILURE", elapsed))
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
