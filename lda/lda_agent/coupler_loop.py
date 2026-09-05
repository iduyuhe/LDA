"""LDA · 多端口耦合器件验收闭环（D-01：分束器 / 方向耦合器）。

把 1.8 的「真 2D 波导验收范式」扩展为「含耦合的多端口器件」：
  - 方向耦合器（DC）：ORACLE 用 FDFD 超模法（对称/反对称超模 → κ、L_c），
    FDTD 注入波导 A 基模、多 z 平面做超模投影，用亥姆霍兹递推/相位拟合提取
    超模拍频 → κ_fdtd，与 κ_oracle 交叉对拍。LLM 不进判决路径。
  - 对称 Y 分支分束器（YB）：ORACLE 用对称性定理（P1=P2=0.5·P_in），
    FDTD 注入输入基模、输出段测两臂能流功率，验证平衡度。

验收判据（对应 D-01「3 器件 3/3 PASS」）：
  DC：|κ_fdtd − κ_oracle| / κ_oracle ≤ tol_kappa（默认 0.25，覆盖网格色散）
  YB：|fracA − 0.5| ≤ tol_balance（默认 0.10），且总功率传输为正

后端：默认 GPU（torch.cuda）——大规模网格纯 numpy 不可行；numpy 后端保留
供 CPU 小网格冒烟 / CI。
"""
from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "lda_solver"))
sys.path.insert(0, os.path.join(_HERE, "..", "lda_harness"))

import numpy as np

from fdtd3d_coupler import (
    build_coupler_field_3d, build_ybranch_field_3d,
    solve_port_powers_3d, solve_supermode_projection_3d_torch,
)
from oracle_coupler import (
    coupling_oracle, ybranch_oracle, fdfd_coupler_supermodes,
)


# ---------------------------------------------------------------------------
# β 提取工具（亥姆霍兹递推 + 相位拟合，对反波免疫）
# ---------------------------------------------------------------------------
def _beta_from_bidi_fit(Os: np.ndarray, z_um: np.ndarray) -> Optional[float]:
    """复域双向拟合提取 β：O(z) = A⁺·e^{iβz} + A⁻·e^{−iβz}（最小二乘）。

    末端反射/源产生的同模反波（A⁻）被显式建模，正波 A⁺ 的传播常数 β 仍由拟合
    独立给出——对反波免疫。初值用相位拟合斜率 + 傅里叶分解估计振幅。
    """
    from scipy.optimize import least_squares
    if len(Os) < 5:
        return None
    z = np.asarray(z_um, dtype=float)
    zc = z - z[0]
    # 初值：斜率
    ph = np.unwrap(np.angle(Os))
    beta0 = float(np.polyfit(zc, ph, 1)[0])
    A0 = float(np.mean(np.real(Os * np.exp(-1j * beta0 * zc))))
    Ai0 = float(np.mean(np.imag(Os * np.exp(-1j * beta0 * zc))))
    B0 = float(np.mean(np.real(Os * np.exp(1j * beta0 * zc))))
    Bi0 = float(np.mean(np.imag(Os * np.exp(1j * beta0 * zc))))

    def resid(p):
        b, ar, ai, br, bi = p
        model = (ar + 1j * ai) * np.exp(1j * b * zc) + \
                (br + 1j * bi) * np.exp(-1j * b * zc)
        r = model - Os
        return np.concatenate([r.real, r.imag])

    try:
        res = least_squares(resid, x0=[beta0, A0, Ai0, B0, Bi0],
                            max_nfev=2000, xtol=1e-12, ftol=1e-12)
    except Exception:
        return None
    if not res.success:
        return None
    return float(res.x[0])


def _beta_from_recurrence(Os: np.ndarray, z_um: np.ndarray,
                          return_all: bool = False):
    """亥姆霍兹递推提取 β：cos(β·dz) = Re((O_k+O_{k+2})/(2·O_{k+1}))。

    对前向+后向叠加的投影系数精确成立（1.8 已验证），对反波免疫；但在反波强的
    驻波节点（|O_{k+1}|≈0）处数值 0/0 会爆，故按 |O_{k+1}| 加权平均取中位。
    z_um 需等距。返回 β（rad/µm）或 (β, 逐三重值) when return_all。
    """
    if len(Os) < 3:
        return None
    dz = float(z_um[1] - z_um[0])
    if dz <= 0:
        return None
    triples = []
    for k in range(len(Os) - 2):
        O1, O2, O3 = Os[k], Os[k + 1], Os[k + 2]
        amp = abs(O2)
        if amp < 1e-30:
            continue
        c = float(np.real((O1 + O3) / (2.0 * O2)))
        c = max(-1.0, min(1.0, c))
        triples.append((amp, math.acos(c) / dz, c, k))
    if not triples:
        return None
    if return_all:
        return triples
    # 振幅加权中位数
    amps = np.array([tr[0] for tr in triples])
    betas = np.array([tr[1] for tr in triples])
    w = amps / (amps.sum() + 1e-30)
    return float(np.average(betas, weights=w))


def _beta_from_phase_fit(Os: np.ndarray, z_um: np.ndarray) -> Optional[float]:
    """相位线性拟合提取 β：unwrap(angle(O(z))) = β·z + const（最小二乘斜率）。

    与递推法独立，作交叉参考。间距需保证相位步长 < π（调用方保证）。
    """
    if len(Os) < 3:
        return None
    ph = np.unwrap(np.angle(Os))
    z = np.asarray(z_um, dtype=float)
    if z[-1] == z[0]:
        return None
    zc = z - z[0]
    # 线性最小二乘斜率；DFT 复振幅与复场差共轭，前向传播相位下降，取绝对值
    slope = abs(float(np.polyfit(zc, ph, 1)[0]))
    return slope


# ---------------------------------------------------------------------------
# 目标 / 结果
# ---------------------------------------------------------------------------
@dataclass
class CouplerTarget:
    kind: str                       # 'dc' 方向耦合器 | 'ybranch' 对称分束器
    label: str = ""
    # dc / ybranch 公共几何
    w_um: float = 0.5
    h_um: float = 0.22
    n_core: float = 3.48
    n_clad: float = 1.44
    wl_um: float = 1.55
    dl_factor: float = 24.0         # dl = wl / factor
    dl_um: Optional[float] = None   # 固定网格步长（多波长扫描用：不随 λ 变，保证
                                    # FDFD 离散一致与超模选模稳定；None 则 wl/factor）
    clad_um: float = 3.0
    # dc 专属
    gap_um: float = 0.3
    dc_Lz_um: float = 24.0
    # ybranch 专属
    sep_um: float = 1.6
    l_in_um: float = 3.0
    l_trans_um: float = 6.0
    l_out_um: float = 13.0
    # 判据
    tol_kappa: float = 0.25         # dc：κ 相对偏差容差
    tol_balance: float = 0.10       # yb：平衡度容差
    backend: str = "auto"           # auto|torch|numpy
    oracle_anchor: Optional[Tuple[float, float]] = None  # dc：多波长超模 neff 追踪锚


@dataclass
class CouplerOutcome:
    label: str
    kind: str
    passed: bool
    metrics: dict
    elapsed: float

    def to_dict(self) -> dict:
        d = dict(self.metrics)
        d.update({"label": self.label, "kind": self.kind,
                  "passed": self.passed, "elapsed_s": round(self.elapsed, 1)})
        return d


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------
class CouplerAgent:
    def run(self, t: CouplerTarget) -> CouplerOutcome:
        t0 = time.time()
        dl = t.dl_um if (t.dl_um and t.dl_um > 0) else t.wl_um / t.dl_factor
        backend = t.backend
        if backend == "auto":
            # 🔴 T-8（v0.9.38）修正：原写法 `torch.cuda.is_available()` 把「无 GPU」
            # 直接映射成 numpy 后端，而 DC/YB 的 numpy 路径在本模块里根本没实现
            # （`_run_dc` 直接 raise）⇒ 无 GPU 机器上 CouplerAgent / CouplerBandAgent
            # **整条链路不可用**。实测 torch 后端内部本就有
            # `dev = "cuda" if torch.cuda.is_available() else "cpu"` 回退，
            # 单波长 CPU 实测 DC 15.3s / YB 19.1s 且判据余量充足
            # （err 2.48% vs tol 25%）。故改为：**有 torch 就用 torch**（设备由
            # torch 自己选 cuda/cpu），torch 缺失才退 numpy（小网格兜底）。
            try:
                import torch  # noqa: F401
                backend = "torch"
            except Exception:
                backend = "numpy"
        if t.kind == "dc":
            out = self._run_dc(t, dl, backend)
        elif t.kind == "ybranch":
            out = self._run_ybranch(t, dl, backend)
        else:
            raise ValueError(f"未知 kind: {t.kind}")
        out.elapsed = time.time() - t0
        return out

    # ---- 方向耦合器 ----
    def _run_dc(self, t: CouplerTarget, dl: float, backend: str) -> CouplerOutcome:
        # 几何场
        eps3, meta = build_coupler_field_3d(
            t.w_um, t.h_um, t.gap_um, t.n_core, t.n_clad, t.wl_um,
            dl=dl, clad_um=t.clad_um, Lz_um=t.dc_Lz_um)
        # ORACLE：FDFD 超模法（频域独立真值）
        orc = fdfd_coupler_supermodes(
            eps3[:, :, 0], meta["dl"], t.wl_um,
            mask_a=meta["mask_a"], mask_b=meta["mask_b"],
            neff_anchor=t.oracle_anchor)
        kappa_o = orc["kappa"]
        Lc_o = orc["Lc_um"]
        # 源剖面：波导 A 的独立单波导基模（与 1.8 同源做法，最干净地注入输入通道）
        from oracle_mode import fdfd_mode_field
        Nx, Ny = meta["Nx"], meta["Ny"]
        xs = (np.arange(Nx) - Nx / 2.0) * meta["dl"]
        ys = (np.arange(Ny) - Ny / 2.0) * meta["dl"]
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        core_a = (np.abs(X - meta["xa_um"]) <= t.w_um / 2.0) & \
                 (np.abs(Y) <= t.h_um / 2.0)
        eps2_a = np.full((Nx, Ny), t.n_clad ** 2)
        eps2_a[core_a] = t.n_core ** 2
        _, src = fdfd_mode_field(eps2_a, meta["dl"], t.wl_um)
        # 采样面：等距 12 面，间距 0.25µm（β·dz≈2.6<π，unwrap 安全），源后 2µm 起
        sponge_z = max(8, min(60, meta["Nz"] // 4))
        src_um = meta["dl"] * (sponge_z + max(8, int(0.12 * (meta["Nz"] - 2 * sponge_z))))
        z_start = src_um + 2.0
        dz_sel = 0.25
        z_samp = z_start + dz_sel * np.arange(12)
        # 瞬态测量窗：末端反波未返回前关闭（正波到采样面 + ramp + 5 周期 后开窗，
        # M 周期后关窗；反波路径 = 源→末端海绵起点 + 返回采样面，需 > transient+M）
        period_steps = int(round(2.0 * math.pi / (orc["neff_s"] * 2.0 * math.pi / t.wl_um) /
                                 (meta["dl"] * 0.95 / math.sqrt(3.0))))
        prop_steps = int(round((z_samp[0] - src_um) * orc["neff_s"] /
                               (meta["dl"] * 0.95 / math.sqrt(3.0))))
        transient_steps = 400 + prop_steps + 5 * period_steps
        if backend == "torch":
            Os, Oa, zu = solve_supermode_projection_3d_torch(
                eps3, meta["dl"], t.wl_um, t.n_clad, t.n_core, src,
                orc["mode_s"], orc["mode_a"], src_um=src_um, z_sample_um=z_samp,
                M_cycles=20, transient=transient_steps)
        else:
            raise RuntimeError("方向耦合器需 torch 后端（纯 numpy 大网格不可行）；"
                               "小网格冒烟请走 torch 或缩小 Lz")
        # 提取 β（递推为主——acos 天然正、对反波免疫、瞬态窗下准确；bidi/相位拟合作交叉参考）
        bs_rec = _beta_from_recurrence(Os, zu)
        ba_rec = _beta_from_recurrence(Oa, zu)
        bs_bidi = _beta_from_bidi_fit(Os, zu)
        ba_bidi = _beta_from_bidi_fit(Oa, zu)
        bs_fit = _beta_from_phase_fit(Os, zu)
        ba_fit = _beta_from_phase_fit(Oa, zu)
        kappa_fdtd = None
        method = None
        if bs_rec is not None and ba_rec is not None:
            kappa_fdtd = (bs_rec - ba_rec) / 2.0
            method = "recurrence"
        elif bs_bidi is not None and ba_bidi is not None:
            kappa_fdtd = (abs(bs_bidi) - abs(ba_bidi)) / 2.0
            method = "bidi_fit"
        if kappa_fdtd is None or kappa_fdtd <= 0:
            return CouplerOutcome(t.label or f"dc gap={t.gap_um}", "dc", False, {
                "error": "β 提取失败", "kappa_oracle": kappa_o, "Lc_oracle": Lc_o}, 0.0)
        rel = abs(kappa_fdtd - kappa_o) / kappa_o
        passed = rel <= t.tol_kappa
        metrics = {
            "gap_um": t.gap_um,
            "neff_s": round(float(orc["neff_s"]), 5),
            "neff_a": round(float(orc["neff_a"]), 5),
            "kappa_oracle": round(kappa_o, 5),
            "kappa_fdtd": round(kappa_fdtd, 5),
            "kappa_method": method,
            "kappa_rel_dev": round(rel, 4),
            "Lc_oracle_um": round(Lc_o, 2),
            "Lc_fdtd_um": round(math.pi / (2.0 * kappa_fdtd), 2),
            "bs_bidi": None if bs_bidi is None else round(bs_bidi, 5),
            "ba_bidi": None if ba_bidi is None else round(ba_bidi, 5),
            "bs_rec": None if bs_rec is None else round(bs_rec, 5),
            "ba_rec": None if ba_rec is None else round(ba_rec, 5),
            "bs_fit": None if bs_fit is None else round(bs_fit, 5),
            "ba_fit": None if ba_fit is None else round(ba_fit, 5),
            "tol_kappa": t.tol_kappa,
        }
        return CouplerOutcome(t.label or f"dc gap={t.gap_um}", "dc", passed,
                              metrics, 0.0)

    # ---- 对称 Y 分支分束器 ----
    def _run_ybranch(self, t: CouplerTarget, dl: float, backend: str) -> CouplerOutcome:
        eps3, meta = build_ybranch_field_3d(
            t.w_um, t.h_um, t.n_core, t.n_clad, t.wl_um,
            sep_um=t.sep_um, l_in_um=t.l_in_um, l_trans_um=t.l_trans_um,
            l_out_um=t.l_out_um, dl=dl, clad_um=t.clad_um)
        # ORACLE：对称性定理（解析真值）
        orc = ybranch_oracle()
        # 输入段单波导基模作源（FDFD，独立确定）
        Nx, Ny = meta["Nx"], meta["Ny"]
        xs = (np.arange(Nx) - Nx / 2.0) * dl
        ys = (np.arange(Ny) - Ny / 2.0) * dl
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        inp_core = (np.abs(X) <= t.w_um / 2.0) & (np.abs(Y) <= t.h_um / 2.0)
        eps2_in = np.full((Nx, Ny), t.n_clad ** 2)
        eps2_in[inp_core] = t.n_core ** 2
        from oracle_mode import fdfd_mode_field
        _, mode_in = fdfd_mode_field(eps2_in, dl, t.wl_um)
        # 源在输入段中后部；测量面在输出段前部（远离过渡区与末端海绵）
        src_um = t.l_in_um * 0.7
        z_out = meta["l_out_start_um"] + np.linspace(0.6, 4.2, 7)
        # 瞬态测量窗：末端反波未返回前关闭（正波到采样面 + ramp + 5 周期 后开窗）
        neff_avg = 0.5 * (t.n_core + t.n_clad)
        dt_f = meta["dl"] * 0.95 / math.sqrt(3.0)
        period_steps = int(round(2.0 * math.pi / (neff_avg * 2.0 * math.pi / t.wl_um * dt_f)))
        prop_steps = int(round((z_out[0] - src_um) * neff_avg / dt_f))
        transient_steps = 400 + prop_steps + 5 * period_steps
        if backend == "torch":
            import torch as _torch
            from fdtd3d_coupler import solve_port_powers_3d_torch
            fa, fb, zu, pa, pb, _srcz = solve_port_powers_3d_torch(
                eps3, meta["dl"], t.wl_um, t.n_clad, t.n_core, mode_in,
                meta["mask_a"], meta["mask_b"], src_um=src_um, z_sample_um=z_out,
                M_cycles=20, transient=transient_steps, debug=True)
        else:
            fa, fb, zu, pa, pb, _srcz = solve_port_powers_3d(
                eps3, meta["dl"], t.wl_um, t.n_clad, t.n_core, mode_in,
                meta["mask_a"], meta["mask_b"], src_um=src_um, z_sample_um=z_out,
                M_cycles=20, debug=True)
        # 用输出段后段（远离过渡的稳态面）平均
        n_avg = max(2, len(fa) // 2)
        fracA = float(np.mean(fa[-n_avg:]))
        fracB = float(np.mean(fb[-n_avg:]))
        total_pos = bool(np.mean(pa[-n_avg:]) > 0 and np.mean(pb[-n_avg:]) > 0)
        balance = abs(fracA - 0.5)
        passed = (balance <= t.tol_balance) and total_pos
        metrics = {
            "fracA": round(fracA, 4),
            "fracB": round(fracB, 4),
            "balance_abs": round(balance, 4),
            "total_power_positive": total_pos,
            "target_frac": orc["target_frac"],
            "tol_balance": t.tol_balance,
            "z_out_um": [round(float(x), 2) for x in z_out],
            "fracA_by_z": [round(float(x), 3) for x in fa],
            "fracB_by_z": [round(float(x), 3) for x in fb],
        }
        return CouplerOutcome(t.label or "ybranch", "ybranch", passed,
                              metrics, 0.0)


# ---------------------------------------------------------------------------
# 默认案例（3 器件 3/3 PASS 目标）
# ---------------------------------------------------------------------------
def _default_cases() -> List[CouplerTarget]:
    return [
        CouplerTarget(kind="dc", gap_um=0.3,
                      label="DC Si 500x220 gap=0.3µm（中等耦合）"),
        CouplerTarget(kind="dc", gap_um=0.25,
                      label="DC Si 500x220 gap=0.25µm（强耦合）"),
        CouplerTarget(kind="ybranch", sep_um=1.6,
                      label="YB Si 对称分束器 1x2（sep=1.6µm）"),
    ]


def main(cases: Optional[List[CouplerTarget]] = None) -> List[CouplerOutcome]:
    if cases is None:
        cases = _default_cases()
    outcomes = []
    n_pass = 0
    for c in cases:
        out = CouplerAgent().run(c)
        outcomes.append(out)
        if out.passed:
            n_pass += 1
        flag = "PASS" if out.passed else "FAIL"
        m = out.metrics
        if out.kind == "dc":
            detail = (f"κ_oracle={m.get('kappa_oracle')} "
                      f"κ_fdtd={m.get('kappa_fdtd')} ({m.get('kappa_method')}) "
                      f"rel={m.get('kappa_rel_dev')}")
        else:
            detail = (f"fracA={m.get('fracA')} fracB={m.get('fracB')} "
                      f"balance={m.get('balance_abs')}")
        print(f"[{flag}] {out.label}: {detail}")
    print(f"\n多端口耦合器件验收闭环：{n_pass}/{len(outcomes)} PASS")
    return outcomes


if __name__ == "__main__":
    main()
