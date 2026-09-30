"""LDA ecore · E8 非理想、失配与噪声（Monte Carlo + 校准层级）（D-158）。

**为什么需要它（E8 逼出的平台接缝）**：
E1–E7 的器件都是**确定性标称值**（同一 W/L、同一 Vth、同一温度）。真实硅片上：
  · **器件失配**（同版图同尺寸的晶体管 Vth/β 仍随机散布）—— Pelgrom 定律；
  · **温度**（Vth 与迁移率随 T 漂移，片内还有热梯度）；
  · **噪声**（沟道热噪声 4kTγg_m + 闪烁噪声）。
三者中**随机项**会在求和里按 1/√N 平均掉，而**系统项**（热梯度、共模偏置）**不会** ——
这正是「要不要校准、校准到哪一层」的判据。平台此前**无失配/噪声/温度通道**，
也无任何**校准层级**的量化。

**本模块做什么**：
  1. **Pelgrom 失配闭式**：`σ_ΔVth = A_VT/√(W·L)` · `σ_Δβ/β = A_β/√(W·L)`（教科书闭式）；
  2. **温度一阶模型**：`Vth(T) = Vth(T0) − k_T·(T−T0)` · 迁移率 `µ(T) ∝ (T/T0)^m`；
  3. **噪声闭式**：热噪声 `i_n² = 4kTγg_m`（γ=2/3 长沟道）· 闪烁 `S_vg = K_f/(C_ox·W·L·f)`
     → 输出电流 `·g_m²`；输入折合 `v_n² = i_n²/g_m²`；
  4. **失配 Monte Carlo**：对 N×M 阵列逐单元抽 ΔVth/Δβ → 重算电导 → 跑 MVM →
     **输出误差分布**（σ / 均值 / P95）；
  5. **校准层级**：L0 原始 / L1 **列增益校准**（消列共模，如热梯度）/ L2 **逐单元校准**
     （受测量噪声限制）——量化各级**残差**；
  6. 统计律自证：**随机失配的输出相对误差 ∝ 1/√N**（独立随机变量求和平均律）。

🔴 **诚实边界**：
  - 失配/噪声/温度参数（A_VT / A_β / k_T / K_f / C_ox）为**公开典型量级占位**，**非 Foundry PDK**；
    真实工艺角/失配 deck 属 D5 外部依赖。
  - **L2「逐单元校准」是理想化模型**：假定能逐单元测量（带测量噪声 σ_est），
    不建模真实编程/读取电路的写-验流程。
  - 噪声只给**谱密度量级**（不建模积分带宽里的 1/f 积分常数与采样折叠）。
  - 不建模失配的空间相关性（假定逐单元独立同分布）。
  - 纯 numpy · LLM 不进判决路径 · 零商业 EDA 依赖。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .mosfet import NmosParams

KB = 1.380649e-23          # 玻尔兹曼常数 J/K
T0_K = 273.15              # 0 °C 开氏

# ---------------------------------------------------------------------------
# 工艺/物理参数（公开典型量级 · 非 PDK · 可覆盖）
# ---------------------------------------------------------------------------
MISMATCH_PROCESS: Dict[str, float] = {
    "a_vt_mv_um": 3.0,          # Pelgrom A_VT（mV·µm）
    "a_beta_pct_um": 1.0,       # Pelgrom A_β/β（%·µm）
    "vth_tc_mv_per_k": -1.0,    # Vth 温度系数（mV/K，负）
    "mu_temp_exponent": -1.5,   # 迁移率温度指数 µ ∝ (T/T0)^m
    "t_ref_c": 25.0,            # 参考温度
    "gamma": 2.0 / 3.0,         # 长沟道热噪声因子
    "cox_f_per_um2": 8.6e-15,   # 栅氧面电容（F/µm²，tox≈4 nm）
    "kf_v2f": 1.0e-25,          # 闪烁噪声系数 K_f（V²·F，公开量级）
}

MISMATCH_DISCLOSURE = {
    "role": "E8 = 非理想/失配/噪声通道 + 失配 Monte Carlo + 校准层级（L0/L1/L2）",
    "process": "A_VT / A_β / k_T / K_f / C_ox = **公开典型量级占位（非 Foundry PDK）**",
    "calibration": "**L2「逐单元校准」是理想化模型**（假定可逐单元测量 + 测量噪声 σ_est）；"
                   "不建模真实写-验编程流程",
    "noise": "只给**谱密度量级**（不建模积分带宽内 1/f 积分常数与采样折叠）",
    "correlation": "假定逐单元**独立同分布**，不建模失配的空间相关性",
    "red_line": "纯 numpy · LLM 不进判决路径 · 零商业 EDA 依赖 · 器件参数非 PDK 标定",
}

# ---------------------------------------------------------------------------
# ① Pelgrom 失配闭式
# ---------------------------------------------------------------------------
def pelgrom_sigma_vth_mv(w_um: float, l_um: float,
                         process: Optional[Dict[str, float]] = None) -> float:
    """Pelgrom 定律：σ_ΔVth = A_VT/√(W·L)（mV）。"""
    p = dict(MISMATCH_PROCESS)
    if process:
        p.update(process)
    area = float(w_um) * float(l_um)
    if area <= 0:
        raise ValueError("W·L 须 > 0")
    return float(p["a_vt_mv_um"]) / math.sqrt(area)


def pelgrom_sigma_beta_rel(w_um: float, l_um: float,
                           process: Optional[Dict[str, float]] = None) -> float:
    """Pelgrom 定律（β 匹配）：σ_Δβ/β = A_β/√(W·L)（相对量）。"""
    p = dict(MISMATCH_PROCESS)
    if process:
        p.update(process)
    area = float(w_um) * float(l_um)
    if area <= 0:
        raise ValueError("W·L 须 > 0")
    return (float(p["a_beta_pct_um"]) / 100.0) / math.sqrt(area)


# ---------------------------------------------------------------------------
# ② 温度一阶模型
# ---------------------------------------------------------------------------
def vth_at(temp_c: float, vth0: float = 0.4,
           process: Optional[Dict[str, float]] = None) -> float:
    """Vth(T) = Vth(T_ref) + k_T·(T − T_ref)（k_T 单位 mV/K，典型为负 ⇒ Vth 随温降）。"""
    p = dict(MISMATCH_PROCESS)
    if process:
        p.update(process)
    return float(vth0) + (float(p["vth_tc_mv_per_k"]) / 1000.0) * (temp_c - p["t_ref_c"])


def mobility_ratio(temp_c: float,
                   process: Optional[Dict[str, float]] = None) -> float:
    """迁移率温度比 µ(T)/µ(T_ref) = ((T+273.15)/(T_ref+273.15))^m（m<0 ⇒ 高温降迁移率）。"""
    p = dict(MISMATCH_PROCESS)
    if process:
        p.update(process)
    t = temp_c + T0_K
    tr = p["t_ref_c"] + T0_K
    return (t / tr) ** float(p["mu_temp_exponent"])


def conductance_at_temperature(vg: float, w_um: float, l_um: float,
                               temp_c: float, params: Optional[NmosParams] = None,
                               process: Optional[Dict[str, float]] = None) -> float:
    """温度下的交叉点电导 g(T) = kp·µ_r(T)·(W/L)·(Vg − Vth(T))。

    🔴 注意：W/L 一律取**几何** `w_um/l_um`（与 E6 版图口径一致）；`params` 只取 kp/vth0/lam。
    """
    pr = dict(MISMATCH_PROCESS)
    if process:
        pr.update(process)
    base = params or NmosParams()
    kp = base.kp
    vth0 = base.vth0
    wl = float(w_um) / float(l_um)
    vth_t = vth_at(temp_c, vth0, pr)
    return kp * mobility_ratio(temp_c, pr) * wl * (float(vg) - vth_t)


# ---------------------------------------------------------------------------
# ③ 噪声闭式
# ---------------------------------------------------------------------------
def thermal_noise_psd(gm: float, temp_c: float = 25.0,
                      process: Optional[Dict[str, float]] = None) -> float:
    """沟道**热噪声**电流谱密度 i_n² = 4·k_B·T·γ·g_m（A²/Hz）。"""
    p = dict(MISMATCH_PROCESS)
    if process:
        p.update(process)
    t = temp_c + T0_K
    return 4.0 * KB * t * float(p["gamma"]) * float(gm)


def flicker_input_noise_psd(w_um: float, l_um: float, freq_hz: float,
                            process: Optional[Dict[str, float]] = None) -> float:
    """**闪烁噪声**输入折合谱密度 S_vg = K_f/(C_ox·W·L·f)（V²/Hz）。"""
    p = dict(MISMATCH_PROCESS)
    if process:
        p.update(process)
    if freq_hz <= 0:
        raise ValueError("频率须 > 0")
    area = float(w_um) * float(l_um)
    return float(p["kf_v2f"]) / (float(p["cox_f_per_um2"]) * area * float(freq_hz))


def flicker_output_noise_psd(gm: float, w_um: float, l_um: float, freq_hz: float,
                             process: Optional[Dict[str, float]] = None) -> float:
    """闪烁噪声**输出电流**谱密度 = S_vg·g_m²（A²/Hz）。"""
    s = flicker_input_noise_psd(w_um, l_um, freq_hz, process)
    return s * float(gm) ** 2


def input_referred_noise_psd(i_n2: float, gm: float) -> float:
    """输入折合噪声 v_n² = i_n²/g_m²（V²/Hz）。"""
    if gm <= 0:
        raise ValueError("g_m 须 > 0")
    return float(i_n2) / float(gm) ** 2


# ---------------------------------------------------------------------------
# ④ 失配 Monte Carlo
# ---------------------------------------------------------------------------
def nominal_conductances(vg, w_um: float, l_um: float,
                         params: Optional[NmosParams] = None):
    """标称交叉点电导 g = kp·(W/L)·(Vg − Vth0)。vg 可为标量或 (n,m) 数组。"""
    p = params or NmosParams(w_over_l=float(w_um) / float(l_um))
    k = p.kp * (float(w_um) / float(l_um))
    return k * (np.asarray(vg, dtype=float) - p.vth0)


def sample_mismatch(n: int, m: int, w_um: float, l_um: float,
                    trials: int = 1, seed: int = 0,
                    process: Optional[Dict[str, float]] = None) -> Dict:
    """抽失配：返回 {'dvth_v': (trials,n,m), 'dbeta_rel': (trials,n,m)}（独立同分布正态）。"""
    pr = dict(MISMATCH_PROCESS)
    if process:
        pr.update(process)
    sig_vth = pelgrom_sigma_vth_mv(w_um, l_um, pr) / 1000.0     # mV → V
    sig_beta = pelgrom_sigma_beta_rel(w_um, l_um, pr)
    rng = np.random.default_rng(seed)
    shape = (int(trials), int(n), int(m))
    return {"dvth_v": rng.normal(0.0, sig_vth, shape),
            "dbeta_rel": rng.normal(0.0, sig_beta, shape),
            "sigma_vth_v": sig_vth, "sigma_beta_rel": sig_beta}


def mismatched_conductances(vg, dvth, dbeta_rel,
                            params: Optional[NmosParams] = None):
    """含失配的电导 g = kp·(W/L)·(1+Δβ)·(Vg − (Vth0+ΔVth))。"""
    p = params or NmosParams(w_over_l=10.0)
    k = p.kp * p.w_over_l
    vg = np.asarray(vg, dtype=float)
    vth = p.vth0 + np.asarray(dvth, dtype=float)
    return k * (1.0 + np.asarray(dbeta_rel, dtype=float)) * (vg - vth)


def mvm_output(g, x) -> np.ndarray:
    """理想互连下的 MVM 输出 y_j = Σ_i g_ij·x_i（列和）。"""
    return np.asarray(g, dtype=float).T @ np.asarray(x, dtype=float)


def mc_output_error(n: int, m: int, vg: float, x: Optional[Sequence] = None,
                    trials: int = 800, seed: int = 0,
                    w_um: float = 1.20, l_um: float = 0.30,
                    params: Optional[NmosParams] = None,
                    process: Optional[Dict[str, float]] = None) -> Dict:
    """失配 Monte Carlo：逐单元抽失配 → 跑 MVM → 输出误差分布（相对标称）。

    返回 {sigma_rel, mean_rel, p95_rel, abs_sigma, trials, sigma_vth_mv,...}。
    """
    x = np.ones(n) if x is None else np.asarray(x, dtype=float)
    p = params or NmosParams(w_over_l=w_um / l_um)
    g0 = nominal_conductances(np.full((n, m), float(vg)), w_um, l_um, p)
    y0 = mvm_output(g0, x)
    s = sample_mismatch(n, m, w_um, l_um, trials=trials, seed=seed, process=process)
    vg_mat = np.full((trials, n, m), float(vg))
    g = mismatched_conductances(vg_mat, s["dvth_v"], s["dbeta_rel"], p)
    y = np.einsum("tij,i->tj", g, x)                 # (trials, m)
    rel = (y - y0) / y0
    return {
        "n": n, "m": m, "trials": trials,
        "sigma_rel": float(np.std(rel)), "mean_rel": float(np.mean(rel)),
        "p95_rel": float(np.percentile(np.abs(rel), 95)),
        "abs_sigma": float(np.std(y, axis=0).mean()),
        "sigma_vth_mv": s["sigma_vth_v"] * 1000.0,
        "sigma_beta_rel": s["sigma_beta_rel"],
        "y0_mean": float(np.mean(y0)),
    }


def sigma_vs_n(n_values: Sequence[int], trials: int = 800, seed: int = 0,
               vg: float = 1.0, w_um: float = 1.20, l_um: float = 0.30,
               process: Optional[Dict[str, float]] = None) -> Dict:
    """统计律自证：输出相对误差 σ **∝ 1/√N**（独立随机变量求和平均律）。"""
    out = []
    for n in n_values:
        r = mc_output_error(int(n), int(n), vg, trials=trials, seed=seed,
                            w_um=w_um, l_um=l_um, process=process)
        out.append({"n": int(n), "sigma_rel": r["sigma_rel"]})
    return {"points": out,
            "sqrt_law_ok": _sqrt_law_monotone(out),
            "sigma0_x_sqrtN": [p["sigma_rel"] * math.sqrt(p["n"]) for p in out]}


def _sqrt_law_monotone(points: List[Dict]) -> bool:
    """σ·√N 近似常值（相对偏差 <35%）且 σ 随 N 单调降。"""
    vals = [p["sigma_rel"] for p in points]
    if any(vals[k] <= vals[k + 1] for k in range(len(vals) - 1)):
        return False
    prod = [p["sigma_rel"] * math.sqrt(p["n"]) for p in points]
    ref = sum(prod) / len(prod)
    return all(abs(v - ref) / ref < 0.35 for v in prod)


# ---------------------------------------------------------------------------
# ⑤ 校准层级
# ---------------------------------------------------------------------------
def calibration_report(n: int, m: int, vg: float, trials: int = 800, seed: int = 0,
                       w_um: float = 1.20, l_um: float = 0.30,
                       thermal_grad_c_per_col: float = 2.0,
                       sigma_est_rel: float = 0.002,
                       x_cal: Optional[Sequence] = None,
                       x_work: Optional[Sequence] = None,
                       params: Optional[NmosParams] = None,
                       process: Optional[Dict[str, float]] = None) -> Dict:
    """三级校准的**残差**对比（含随机失配 + 列间热梯度系统项）。

    L0 原始 —— 随机失配 + 列热梯度系统项；
    L1 **列增益校准** —— 用**测试向量** x_cal 测每列标量增益并归一 ⇒ 消列系统项，留随机项；
    L2 **逐单元校准** —— 逐单元估 `m = (g/g0) + ε`（测量噪声 σ_est）⇒ 残差 ≈ 测量噪声。

    🔴 **x_cal 必须 ≠ x_work**：若校准向量与工作向量相同，L1 会**精确归零**误差
    （测的就是同一个量）——那是**退化情形**，不反映真实校准能力。
    """
    pr = dict(MISMATCH_PROCESS)
    if process:
        pr.update(process)
    p = params or NmosParams(w_over_l=w_um / l_um)
    x_c = np.ones(n) if x_cal is None else np.asarray(x_cal, dtype=float)
    # 工作向量：非均匀（确定性，非随机，保证可复现）
    x_w = (1.0 + 0.5 * np.cos(np.arange(n) * 1.1)) if x_work is None \
        else np.asarray(x_work, dtype=float)

    g0 = nominal_conductances(np.full((n, m), float(vg)), w_um, l_um, p)
    y0_w = mvm_output(g0, x_w)                          # 标称输出（工作向量）

    # 列热梯度（系统项）：中心对称，逐列不同
    grad = float(thermal_grad_c_per_col)
    t_col = pr["t_ref_c"] + grad * (np.arange(m) - (m - 1) / 2.0)
    g_col = np.array([conductance_at_temperature(vg, w_um, l_um, float(t), p, pr)
                      for t in t_col])
    col_gain = g_col / g_col.mean()

    s = sample_mismatch(n, m, w_um, l_um, trials=trials, seed=seed, process=pr)
    rng = np.random.default_rng(seed + 1)
    vg_mat = np.full((trials, n, m), float(vg))
    g = mismatched_conductances(vg_mat, s["dvth_v"], s["dbeta_rel"], p)
    g = g * col_gain[None, None, :]

    y_w = np.einsum("tij,i->tj", g, x_w)                # 工作向量实测输出
    e0 = (y_w - y0_w) / y0_w

    # L1：用**测试向量** x_c 测每列标量增益，再施加到工作向量
    y_c = np.einsum("tij,i->tj", g, x_c)
    y0_c = mvm_output(g0, x_c)
    k1 = y0_c[None, :] / y_c
    e1 = (y_w * k1 - y0_w) / y0_w

    # L2：逐单元校准（测得比 m = g/g0 + ε；校正 g/m）
    eps = rng.normal(0.0, float(sigma_est_rel), (trials, n, m))
    m_meas = g / g0[None, :, :] + eps
    g_corr = g / m_meas
    y2 = np.einsum("tij,i->tj", g_corr, x_w)
    e2 = (y2 - y0_w) / y0_w

    return {
        "n": n, "m": m, "trials": trials,
        "sigma_vth_mv": s["sigma_vth_v"] * 1000.0,
        "thermal_grad_c_per_col": grad,
        "col_gain_spread": float(np.max(np.abs(col_gain - 1.0))),
        "sigma_rel_L0": float(np.std(e0)),
        "sigma_rel_L1": float(np.std(e1)),
        "sigma_rel_L2": float(np.std(e2)),
        "mean_rel_L0": float(np.mean(e0)),
        "mean_rel_L1": float(np.mean(e1)),
        "mean_rel_L2": float(np.mean(e2)),
        "sigma_est_rel": float(sigma_est_rel),
    }


# ---------------------------------------------------------------------------
# 自检（常驻断言）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    msgs: List[Tuple[str, bool]] = []

    def chk(name: str, cond, detail: str = "") -> bool:
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True
    w, l = 1.20, 0.30

    # ① Pelgrom：σ ∝ 1/√(W·L)（面积四倍 ⇒ σ 减半）
    s1 = pelgrom_sigma_vth_mv(w, l)
    s4 = pelgrom_sigma_vth_mv(2 * w, 2 * l)
    ok &= chk("① Pelgrom σ= A/√(WL)（面积 ×4 ⇒ σ 减半）", abs(s4 - s1 / 2.0) < 1e-12)

    # ② MC 实测 σ 与 Pelgrom 闭式一致（±8%）
    smp = sample_mismatch(2000, 1, w, l, trials=1, seed=1)
    emp_mv = float(np.std(smp["dvth_v"])) * 1000.0
    ok &= chk("② MC 实测 σ_ΔVth ≡ Pelgrom 闭式（±8%）",
              abs(emp_mv - s1) / s1 < 0.08, f"实测 {emp_mv:.4f} vs 闭式 {s1:.4f} mV")

    # ③ 温度：Vth 线性、迁移率 < 1（升温）
    ok &= chk("③ Vth(T) 线性（k_T·ΔT）且升温 Vth 降",
              abs((vth_at(85.0) - vth_at(25.0)) - (-1.0) * 0.060) < 1e-9
              and vth_at(85.0) < vth_at(25.0))
    ok &= chk("④ 迁移率比 µ(85°C)/µ(25°C) < 1（升温降迁移率）",
              mobility_ratio(85.0) < 1.0 and abs(mobility_ratio(25.0) - 1.0) < 1e-12)

    # ⑤ 噪声闭式：热噪声 ∝ T、∝ gm；输入折合 = 4kTγ/gm
    gm = 1.0e-3
    ip = thermal_noise_psd(gm, 25.0)
    ip85 = thermal_noise_psd(gm, 85.0)
    ok &= chk("⑤ 热噪声 i_n²=4kTγg_m（∝T 线性 · ∝g_m 线性）",
              abs(ip85 / ip - (85.0 + T0_K) / (25.0 + T0_K)) < 1e-9
              and abs(thermal_noise_psd(2 * gm, 25.0) / ip - 2.0) < 1e-9)
    ok &= chk("⑥ 输入折合噪声 v_n² = i_n²/g_m² = 4kTγ/g_m",
              abs(input_referred_noise_psd(ip, gm) - 4 * KB * (25.0 + T0_K) * (2 / 3) / gm) < 1e-30)
    s_f1 = flicker_input_noise_psd(w, l, 1e3)
    ok &= chk("⑦ 闪烁噪声 ∝ 1/f、∝ 1/(W·L)",
              abs(flicker_input_noise_psd(w, l, 2e3) - s_f1 / 2.0) < 1e-40
              and abs(flicker_input_noise_psd(2 * w, 2 * l, 1e3) - s_f1 / 4.0) < 1e-40)

    # ⑧ 统计律：σ_rel ∝ 1/√N
    law = sigma_vs_n([4, 16, 64], trials=600, seed=3)
    ok &= chk("⑧ 随机失配输出相对误差 ∝ 1/√N（求和平均律）", law["sqrt_law_ok"],
              f"σ·√N = {[round(v, 6) for v in law['sigma0_x_sqrtN']]}")

    # ⑨ 校准层级：残差单调降 L0 ≥ L1 ≥ L2
    cr = calibration_report(8, 8, vg=1.0, trials=600, seed=5)
    ok &= chk("⑨ 校准层级残差单调降（L0 ≥ L1 ≥ L2）",
              cr["sigma_rel_L0"] >= cr["sigma_rel_L1"] >= cr["sigma_rel_L2"],
              f"{cr['sigma_rel_L0']:.5f} ≥ {cr['sigma_rel_L1']:.5f} ≥ {cr['sigma_rel_L2']:.5f}")
    ok &= chk("⑩ L1 消系统项（残差显著小于 L0）",
              cr["sigma_rel_L1"] < cr["sigma_rel_L0"] * 0.8,
              f"系统项 col_gain_spread={cr['col_gain_spread']:.4f}")

    if verbose:
        for nm, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {nm}")
    return bool(ok)
