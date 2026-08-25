"""LDA P1-M3 · 器件综合 Agent（synthesis）。

对每个链路实例，确保存在「器件传递模型」：
  - registry 已知 kind（RingResonator/Waveguide/GratingCoupler 等）：
    解析模型由 lda_chain.registry 在仿真时提供，synthesis 仅登记可用性，
    不重造轮子（继承 M1 资产）。
  - registry 未知 kind：委托单器件闭环 design_pipeline.run_pipeline 合成
    （确定性、物理锚验收），作为「器件综合」的真实后端。

产出：ctx.device_models（inst_id -> model 描述）；未知且无法合成者诚实记录。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .agents import AgentMsg, BaseAgent, DesignContext
from lda_chain.registry import get_response


# registry 已知（解析模型直供）的 kind —— 与 lda_chain.registry.get_response 同步
_REGISTRY_KNOWN = ("RingResonator", "RingAddDrop", "Waveguide", "GratingCoupler")


class DeviceSynthesisAgent(BaseAgent):
    NAME = "synthesis"
    ACTIONS = ["synthesize"]

    def _run(self, msg: AgentMsg, ctx: DesignContext) -> Dict[str, Any]:
        if ctx.link is None:
            raise RuntimeError("链路规划未执行：ctx.link 为空")
        link = ctx.link
        wls = _wavelengths(msg, link)

        ok, missing, delegated = [], [], []
        for comp in link.ir.components:
            if comp.kind in _REGISTRY_KNOWN:
                r = get_response(comp.kind, comp, wls, link.link_params)
                if r is None:
                    missing.append(comp.id)
                else:
                    ctx.device_models[comp.id] = {
                        "kind": comp.kind, "source": "registry-analytical",
                        "ports": sorted({p for (_, p) in r.keys()}),
                    }
                    ok.append(comp.id)
            else:
                # 未知 kind → 委托单器件闭环合成（best-effort）
                delegated.append(comp.id)
                try:
                    model = self._delegate(comp.kind, dict(comp.params))
                    ctx.device_models[comp.id] = model
                except Exception as e:
                    missing.append(comp.id)
                    ctx.device_models[comp.id] = {
                        "kind": comp.kind, "source": "unsynthesized",
                        "error": str(e),
                    }

        summary = (f"器件综合：registry 直供 {len(ok)} / 委托合成 {len(delegated)}"
                   f" / 缺失 {len(missing)}")
        ctx.append_step(self.NAME, msg.action, summary,
                        {"registry": ok, "delegated": delegated,
                         "missing": missing})
        return {"status": "ok" if not missing else "partial",
                "registry": ok, "delegated": delegated, "missing": missing}

    @staticmethod
    def _delegate(kind: str, params: Dict[str, float]) -> Dict[str, Any]:
        """委托单器件闭环（design_pipeline）合成未知 kind 的 transfer 模型。"""
        from lda_agent.design_pipeline import run_pipeline
        rep = run_pipeline(kind, params=params)
        return {
            "kind": kind, "source": "design_pipeline-closed-loop",
            "accepted": rep.get("accepted"),
            "params": rep.get("final_params"),
        }


def _wavelengths(msg: AgentMsg, link) -> List[float]:
    wl = msg.payload.get("wavelengths_um")
    if wl:
        return wl
    lp = link.link_params or {}
    wl0 = lp.get("wl0_um", 1.55)
    span = lp.get("span_um", 0.06)
    n = int(lp.get("n_samples", 61))
    return [wl0 - span / 2.0 + span * i / (n - 1) for i in range(n)]
