"""LDA · 真 2D 器件验收闭环（波导横截面：FDTD 设计结果 vs FDFD ORACLE）。

证明 thesis 在真 2D 器件上的延伸：agent 产出「真 2D 波导设计结果（基模 neff）」，
由独立频域 ORACLE（oracle_mode.fdfd_neff 标量亥姆霍兹本征模）确定性验收，
LLM 不进判决路径。

链路：
  Interpreter  → 解析波导设计意图（w, h, n_core, n_clad, λ）
  SolverAgent  → 跑 3D 标量波动 FDTD（fdtd3d_waveguide）得基模 neff（设计结果）
  Verifier     → 调 FDFD ORACLE 得 neff 真值，比 |Δneff|，判 PASS/FAIL
  → 输出 WaveguideOutcome（给「人」的决策摘要）

与 L0 IR / L1 agent / 布拉格镜闭环（design_loop.py，1D stack + TMM）互补：
此处针对「真 2D 几何（x,y 双向约束）」器件，TMM 不适用，故用 FDFD ORACLE。
两者共同构成阶段1 任务 1.8「真 2D ORACLE + 器件验收闭环」。
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "lda_solver"))
sys.path.insert(0, os.path.join(_HERE, "..", "lda_harness"))

from fdtd3d_waveguide import build_waveguide_field_3d, solve_waveguide_neff_3d
from oracle_mode import fdfd_mode_field


@dataclass
class WaveguideTarget:
    """真 2D 条形波导设计目标（横截面 w×h，芯 n_core，包 n_clad，真空波长 λ）。"""
    w_um: float
    h_um: float
    n_core: float
    n_clad: float
    wl_um: float
    label: str = ""
    tolerance_abs: float = 0.15        # |Δneff| 验收公差（≈6% 相对；含网格数值色散余量）
    clad_um: float = 3.0               # 包层厚度（必须厚：避免模尾打金属壁导致 ORACLE/FDTD 数值震荡；FDTD 与 ORACLE 一致）
    dl_factor: float = 24.0            # dl = λ/dl_factor（稳定支：粗 f≤24 或细 f≥48；中间 f=28~40 有 FDFD 伪模穿越，禁用）
    Lz_um: float = 8.0                 # z 传播长度


@dataclass
class WaveguideOutcome:
    label: str
    target: dict
    neff_fdtd: float
    neff_fdfd: float
    delta: float
    passed: bool
    snr: float
    elapsed: float

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "w_um": self.target["w_um"], "h_um": self.target["h_um"],
            "n_core": self.target["n_core"], "n_clad": self.target["n_clad"],
            "wl_um": self.target["wl_um"],
            "neff_fdtd": round(self.neff_fdtd, 5),
            "neff_fdfd": round(self.neff_fdfd, 5),
            "delta_neff": round(self.delta, 5),
            "passed": self.passed,
            "snr": round(self.snr, 3),
            "elapsed_s": round(self.elapsed, 1),
        }


class WaveguideAgent:
    """编排器：把 SolverAgent（FDTD）+ Verifier（FDFD ORACLE）串成验收闭环。"""

    def run(self, target: WaveguideTarget) -> WaveguideOutcome:
        t0 = time.time()
        dl = target.wl_um / target.dl_factor

        # ---- SolverAgent：FDTD 设计结果（基模 neff，标量 3D 波动，与 ORACLE 同近似层级）----
        # 几何场与 ORACLE 同源（同一 clad/dl），保证公平比对。
        # 注：真 2D 矢量全 Yee 求解器（fdtd3d_waveguide_vec）当前用标量 FDFD 模作 Ey
        # 源会激发错模态（强反差下标量模形状≠真矢量 TE 模 Ey），故验收后端用标量
        # FDTD——与标量 FDFD ORACLE 同一近似层级，独立时域/频域交叉校验，误差为网格
        # 数值色散（dl=λ/24 约 4~5%，已在公差内）。
        eps3, meta = build_waveguide_field_3d(
            target.w_um, target.h_um, target.n_core, target.n_clad, target.wl_um,
            dl=dl, clad_um=target.clad_um, Lz_um=target.Lz_um)

        # ---- Verifier：FDFD ORACLE 真值（标量亥姆霍兹频域本征值，确定性物理锚）----
        # 复用同一 eps3（同一网格/包层），避免几何不一致。mode2d = ORACLE 模态
        # 剖面，仅作 FDTD 激发形状（标量模 = 标量 Ey 场，注入即干净基模），
        # neff 仍由 FDTD 传播相位独立测量，不污染判决。
        ne_oracle, mode2d = fdfd_mode_field(eps3, meta["dl"], target.wl_um)

        ne_fdtd, _beta, _m, snr = solve_waveguide_neff_3d(
            eps3, meta["dl"], target.wl_um, n_clad=target.n_clad,
            n_core=target.n_core, mode_source=mode2d, debug=True)

        delta = abs(ne_fdtd - ne_oracle)
        passed = delta <= target.tolerance_abs

        elapsed = time.time() - t0
        return WaveguideOutcome(
            label=target.label or f"w{target.w_um}_h{target.h_um}",
            target=target.__dict__, neff_fdtd=ne_fdtd, neff_fdfd=ne_oracle,
            delta=delta, passed=passed, snr=snr, elapsed=elapsed)


# ---------------------------------------------------------------------------
# 命令行入口（确定性、批处理、无交互）
# ---------------------------------------------------------------------------
def _default_cases() -> List[WaveguideTarget]:
    return [
        WaveguideTarget(0.5, 0.22, 3.48, 1.44, 1.55,
                        label="Si/SiO2 紧约束 500x220nm", tolerance_abs=0.15),
        WaveguideTarget(0.45, 0.22, 3.48, 1.44, 1.55,
                        label="Si/SiO2 450x220nm", tolerance_abs=0.15),
        WaveguideTarget(0.5, 0.30, 2.00, 1.44, 1.55,
                        label="SiN/SiO2 500x300nm", tolerance_abs=0.15),
    ]


def main(cases: Optional[List[WaveguideTarget]] = None) -> List[WaveguideOutcome]:
    if cases is None:
        cases = _default_cases()
    outcomes: List[WaveguideOutcome] = []
    n_pass = 0
    for c in cases:
        out = WaveguideAgent().run(c)
        outcomes.append(out)
        if out.passed:
            n_pass += 1
        flag = "PASS" if out.passed else "FAIL"
        print(f"[{flag}] {out.label}: FDTD neff={out.neff_fdtd:.5f} "
              f"FDFD neff={out.neff_fdfd:.5f} |Δ|={out.delta:.5f} "
              f"snr={out.snr:.3f} ({out.elapsed:.1f}s)")
    print(f"\n真 2D 器件验收闭环：{n_pass}/{len(outcomes)} PASS")
    return outcomes


if __name__ == "__main__":
    main()
