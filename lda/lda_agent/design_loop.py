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

from l1_protocol import (
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
