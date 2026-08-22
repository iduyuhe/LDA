"""LDA · 端到端设计闭环（agent-native 设计代理）。

证明 thesis：agent 产出「可用的设计结果（design outcome）」，不是"帮人设计"的辅助软件。
人机分工（见协作哲学）：agent 负责操作执行（调内核/跑仿真/跑验证/迭代），
人负责决策（定方向/验收结果/担责任）。人是结果责任人，不是操作工。

闭环（对应 L0 IR §5 角色链）：
  Interpreter → 解析设计意图为 DesignTarget
  loop (有界):
    Designer   → 按当前周期数生成 L0IR（布拉格四分之一波堆）
    SolverAgent→ 跑已验证 FDTD 核（numba-cpu），得透射谱
    Verifier   → 对 TMM 物理定律锚比对，判 R 是否达标 + 误差是否达标
    if 达标 → break（设计结果已出）
    else   → 周期数 +1，继续
  → 输出 DesignOutcomeReport（给「人」的决策摘要）

本闭环是阶段1 任务「L1 agent + 端到端闭环」的最小可运行首稿：先打通
「设计目标 → 迭代 → 验证 → 出结果」的 agent 操作链路，证明开放内核可被
agent 直接驱动；器件级（voxel_field + GDSII）、多 agent 并发编排为后续迭代。
"""
from __future__ import annotations

import time
from typing import Dict, Any, List, Optional

from lda_agent.l1_protocol import (
    DesignTarget, L0IR, DesignOutcomeReport, InterpreterAgent,
    DesignerAgent, SolverAgent, VerifierAgent,
)


class DesignAgent:
    """编排器：把四个 L1 角色串成有界闭环。"""

    def __init__(self, backend: str = "numpy",
                 dl_factor: float = 60.0, sponge: int = 60, ramp: int = 200,
                 geo_kind: str = "stack"):
        self.backend = backend
        self.dl_factor = dl_factor
        self.sponge = sponge
        self.ramp = ramp
        self.geo_kind = geo_kind

    def run(self, intent: Dict[str, Any]) -> DesignOutcomeReport:
        t0 = time.time()
        target = InterpreterAgent.parse(intent)
        # D-70：伴随梯度拓扑逆设计走专用闭环（目标 → 梯度优化 → 双验证 → PASS）
        if target.method == "adjoint":
            return self._run_adjoint(target)
        # D-72 深化：3D 端口 S 参数验收闭环（mmi/dc/ring → 3D FDTD S 谱 → 死标量验收）
        if target.method == "sparams3d":
            return self._run_sparams3d(target)
        # 把数值/后端偏好注入 target.extra，供 Designer 生成 L0IR 时取用
        target.extra.setdefault("backend", self.backend)
        target.extra.setdefault("dl_factor", self.dl_factor)
        target.extra.setdefault("sponge", self.sponge)
        target.extra.setdefault("ramp", self.ramp)

        trace: List[Dict[str, Any]] = []
        periods = target.initial_periods
        final_doc: Optional[L0IR] = None
        final_verify = None
        accepted = False

        for it in range(1, target.max_iterations + 1):
            doc = DesignerAgent.propose(
                target, periods=periods, doc_id=f"bragg-N{periods}-it{it}",
                geo_kind=self.geo_kind)
            final_doc = doc

            res = SolverAgent.solve(doc)
            verify = VerifierAgent.verify(doc, res, target.threshold)
            final_verify = verify

            trace.append({
                "iteration": it,
                "periods": periods,
                "R_fdtd": round(verify.metric_value, 5),
                "R_tmm": round(verify.oracle_value, 5),
                "metric_err": f"{verify.metric_abs_err:.2e}",
                "meets_target": verify.meets_target,
                "within_tolerance": verify.within_tolerance,
                "passed": verify.passed,
                "backend": res.backend,
            })

            if verify.passed:
                accepted = True
                break
            # 真 2D 波导：验收以"与 ORACLE 一致"为准，设计由 width 唯一确定，
            # 单次验证即通过（方法一致性），不随周期数变化 → 仅跑一次，避免空转
            if self.geo_kind == "waveguide_2d":
                break
            # 未达标：周期数 +1（布拉格 R 随周期数单调升，必然收敛到有界内）
            periods += 1

        elapsed = time.time() - t0
        report = DesignOutcomeReport(
            target=target.__dict__,
            accepted=accepted,
            iterations=len(trace),
            final_doc_id=final_doc.doc_id,
            final_layers=[[ref, th] for ref, th in final_doc.layers],
            final_metric=final_verify.metric_value,
            final_oracle_metric=final_verify.oracle_value,
            final_metric_err=final_verify.metric_abs_err,
            final_max_metric_err=final_verify.max_metric_abs_err,
            loop_trace=trace,
            verdict=self._verdict(accepted, final_verify, elapsed),
        )
        return report

    def _run_adjoint(self, target: DesignTarget) -> DesignOutcomeReport:
        """D-70：伴随梯度拓扑逆设计闭环（method="adjoint"）。

        目标泛化：设计区/监视孔径/材料对比度/波长/网格分辨率全部由 intent 的
        extra 指定（AdjointProblem 几何透传）——"设计目标"从布拉格周期数泛化为
        "把某孔径内的收集场能最大化"。

        闭环（LLM 不进判决路径，PASS 由死标量比对决定）：
          (a) 数值/物理自洽锚：adjoint vs 中心有限差分方向对拍 max_rel_err ≤ 0.15；
          (b) 目标达成：improvement = final_FOM / initial_FOM ≥ 1.5（M4）。
        优化器 = 密度投影（beta 延拓二值化）+ 回溯线搜索梯度上升（FOM 单调不降）。
        FOM 语义诚实标注：脉冲源监视器孔径收集场能，聚焦增益可致 T>1，非功率透射。
        """
        import numpy as np
        from lda_solver.adjoint_fdtd import (
            AdjointProblem, verify_adjoint, optimize_topology,
        )

        t0 = time.time()
        ex = target.extra
        geo = {k: v for k, v in ex.items()
               if k in ("Nx", "Ny", "dl_factor", "sponge", "i_src", "i_mon",
                        "y_src0", "y_src1", "y_mon0", "y_mon1",
                        "di0", "di1", "dj0", "dj1", "eps_min", "eps_max",
                        "wl_um", "courant", "target_exp", "ramp",
                        "periods_factor")}
        if isinstance(ex.get("geo"), dict):
            geo.update(ex["geo"])
        problem = AdjointProblem(**geo)

        # 空设计区：优雅 FAIL（非异常）
        if problem.design_mask.sum() == 0:
            return DesignOutcomeReport(
                target=target.__dict__, accepted=False, iterations=0,
                final_doc_id="adjoint-topology-none", final_layers=[],
                final_metric=0.0, final_oracle_metric=0.0, final_metric_err=0.0,
                loop_trace=[],
                verdict=("逆设计 FAIL：设计区为空（di0/di1 或 dj0/dj1 无效），"
                         "无优化自由度。"))

        # 1) 均匀平板初值（设计区 = 中间折射率）
        eps0 = np.full((problem.Nx, problem.Ny), problem.eps_min)
        eps0[problem.design_mask] = (problem.eps_min + problem.eps_max) / 2.0

        # 2) 验证锚：adjoint 梯度 vs 中心有限差分（方向对拍）
        nsamples = int(ex.get("nsamples", 8))
        delta = float(ex.get("delta", 0.05))
        vr = verify_adjoint(problem, eps0, nsamples=nsamples, delta=delta)

        # 3) 梯度拓扑优化（回溯线搜索，FOM 单调不降）
        iters = int(ex.get("iters", 50))
        step0 = float(ex.get("step0", 0.5))
        beta_max = float(ex.get("beta_max", 14.0))
        opt = optimize_topology(problem, eps0, iters=iters, step0=step0,
                                beta_max=beta_max)

        # 4) 死标量验收
        ok_anchor = bool(vr["passed"])
        ok_gain = bool(opt["passed"])
        accepted = ok_anchor and ok_gain
        fom0, fomf = opt["initial_FOM"], opt["final_FOM"]
        trace = [{"iteration": h["iter"], "FOM": round(h["FOM"], 4),
                  "T": round(h["T"], 4), "beta": h["beta"], "alpha": h["alpha"]}
                 for h in opt["history"]]

        if accepted:
            verdict = (f"逆设计 PASS：FOM {fom0:.1f} → {fomf:.1f} "
                       f"（improvement={opt['improvement']:.2f}× ≥ 1.5），"
                       f"adjoint 对拍 max_rel_err={vr['max_rel_err']:.4f} "
                       f"（≤0.15）；设计区 "
                       f"{int(problem.design_mask.sum())} 体素，孔径 "
                       f"y∈[{problem.y_mon0},{problem.y_mon1}]。"
                       f"闭环耗时 {time.time() - t0:.1f}s。结果已可由「人」验收。")
        else:
            fails = []
            if not ok_anchor:
                fails.append(f"adjoint 对拍 max_rel_err={vr['max_rel_err']:.4f} 超 0.15")
            if not ok_gain:
                fails.append(f"improvement={opt['improvement']:.2f}× 未达 1.5")
            verdict = (f"逆设计未全过：" + "；".join(fails) +
                       f"。闭环耗时 {time.time() - t0:.1f}s。")

        return DesignOutcomeReport(
            target=target.__dict__,
            accepted=accepted,
            iterations=len(trace),
            final_doc_id="adjoint-topology-d70",
            final_layers=[],                       # voxel 设计：分布见 loop_trace/verdict
            final_metric=float(fomf),
            final_oracle_metric=float(fom0),       # oracle = 均匀平板初值基线
            final_metric_err=float(vr["max_rel_err"]),
            final_max_metric_err=float(vr["max_rel_err"]),
            loop_trace=trace,
            verdict=verdict,
        )

    def _run_sparams3d(self, target: DesignTarget) -> DesignOutcomeReport:
        """D-72 深化：3D 端口 S 参数验收闭环（method="sparams3d"）。

        目标泛化：kind（mmi/dc/ring）+ 几何（设计区/耦合区/环参数）全部由
        意图 extra 指定 → 3D FDTD 端口 S 参数谱（SOI 220nm，复用已验证
        numba 核）→ 死标量验收（kind 判据：mmi 平衡度 / dc cross_frac
        端点趋势 / ring drop 谐振峰，均 + 仿真有效 + 透射）→
        DesignOutcomeReport 兼容输出（iterations=波长数、loop_trace 每波长
        S11/S21/S31、final_metric=中心波长 T_total）。

        依赖 numba（python envs/default venv）；当前环境无 numba 时优雅
        FAIL（报告错误，不崩）。LLM 不进判决路径。
        """
        t0 = time.time()
        ex = target.extra
        kind = str(ex.get("kind", "mmi")).lower()
        params = {k: float(v) for k, v in ex.items()
                  if k not in ("kind", "iters", "step0", "beta_max")
                  and isinstance(v, (int, float))}
        try:
            from lda_solver.port_sparams_3d import verify_s_params_3d
        except ImportError as e:  # noqa: BLE001
            return DesignOutcomeReport(
                target=target.__dict__, accepted=False, iterations=0,
                final_doc_id="sparams3d-none", final_layers=[],
                final_metric=0.0, final_oracle_metric=0.0,
                final_metric_err=0.0, loop_trace=[],
                verdict=(f"3D 端口验收 FAIL：当前环境缺 numba（{e}）——"
                         f"请用 `python envs/default/Scripts/python.exe` 运行。"))
        try:
            vr = verify_s_params_3d(
                kind, params,
                transient_cycles=int(ex.get("transient_cycles", 800)),
                dl_factor=float(ex.get("dl_factor", 12.0)))
        except (ValueError, KeyError) as e:  # noqa: BLE001
            return DesignOutcomeReport(
                target=target.__dict__, accepted=False, iterations=0,
                final_doc_id="sparams3d-invalid", final_layers=[],
                final_metric=0.0, final_oracle_metric=0.0,
                final_metric_err=0.0, loop_trace=[],
                verdict=f"3D 端口验收 FAIL：参数无效（{e}）。")
        pts = vr["spectrum"]["points"]
        trace = [{"iteration": i, "wl_um": p["wl_um"],
                  "S11": round(p["S11_2"], 4), "S21": round(p["S21_2"], 4),
                  "S31": round(p["S31_2"], 4),
                  "T_total": round(p["T_total"], 4)}
                 for i, p in enumerate(pts)]
        accepted = bool(vr["acceptance"]["passed"])
        # final_metric = 中心波长（最接近 wl0）T_total
        wl0 = float(params.get("wl0_um", 1.55))
        ctr = min(pts, key=lambda p: abs(p["wl_um"] - wl0))
        verdict = (vr["verdict"] +
                   f"（闭环 method=sparams3d，耗时 {time.time() - t0:.1f}s，"
                   f"结果已可由「人」验收。）" if accepted else
                   vr["verdict"] + f"（闭环耗时 {time.time() - t0:.1f}s。）")
        return DesignOutcomeReport(
            target=target.__dict__,
            accepted=accepted,
            iterations=len(trace),
            final_doc_id=f"sparams3d-{kind}",
            final_layers=[],
            final_metric=float(ctr["T_total"]),
            final_oracle_metric=float(ctr["S11_2"]),  # oracle 参考 = 回波
            final_metric_err=float(min(p["T_total"] for p in pts)),
            final_max_metric_err=float(max(p["T_total"] for p in pts)),
            loop_trace=trace,
            verdict=verdict,
        )

    @staticmethod
    def _verdict(accepted: bool, verify, elapsed: float) -> str:
        if verify.metric == "neff":
            # 真 2D 波导验收：以"对 slab ORACLE 的 neff 相对误差"为准
            if accepted:
                return (f"真2D 波导验收达标：neff(FDTD)={verify.metric_value:.4f}，"
                        f"对 slab ORACLE neff={verify.oracle_value:.4f}，"
                        f"相对误差 {verify.max_rel_T:.2%} 在公差内；"
                        f"闭环耗时 {elapsed:.1f}s。结果已可由「人」验收。")
            return (f"真2D 波导未达验收：相对误差 {verify.max_rel_T:.2%} 超公差；"
                    f"请提高分辨率后重跑。闭环耗时 {elapsed:.1f}s。")
        if accepted:
            return (f"设计达标：R(FDTD)={verify.metric_value:.4f} ≥ 阈值，"
                    f"且对 TMM 物理定律锚 |ΔR|={verify.metric_abs_err:.2e} 在公差内；"
                    f"闭环耗时 {elapsed:.1f}s。结果已可由「人」验收。")
        return (f"未在迭代上限内达标：R(FDTD)={verify.metric_value:.4f}；"
                f"请放宽阈值 / 增 material 对比度 / 提高分辨率后重跑。"
                f"闭环耗时 {elapsed:.1f}s。")


# ---------------------------------------------------------------------------
# 命令行入口（确定性、批处理、无交互）
# ---------------------------------------------------------------------------
def main(intent: Optional[Dict[str, Any]] = None) -> DesignOutcomeReport:
    if intent is None:
        # 默认演示目标：λ0=1.55µm、Si/SiO2 布拉格镜，R ≥ 0.99
        intent = {
            "geometry_type": "bragg_mirror",
            "materials": {"air": 1.0, "sih": 3.48, "silo": 1.44},
            "target_wavelength_um": 1.55,
            "target_metric": "R",
            "threshold": 0.99,
            "tolerance_rel": 0.02,
            "max_iterations": 12,
            "initial_periods": 1,
        }
    agent = DesignAgent(backend="numpy", geo_kind=intent.get("geo_kind", "stack"),
                        dl_factor=60.0, sponge=60, ramp=200)
    return agent.run(intent)


if __name__ == "__main__":
    rep = main()
    print(json_report(rep))


def json_report(rep: DesignOutcomeReport) -> str:
    import json
    return json.dumps(rep.to_dict(), ensure_ascii=False, indent=2)
