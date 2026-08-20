"""LDA · D-18 DRC 回读整改闭环（agent 自适应可制造性修复）。

LDA 差异化：agent 不只做"设计→版图→DRC 自查"，还能**读取 DRC violation
自动整改参数**直至可制造——设计代理自主解决可制造性问题的演示（阶段 3 核心
卖点：给一个违规初值，agent 自己改到可制造）。

闭环（死代码判定，LLM 不进判决路径）：
  DrcFixAgent.run(kind, params)
    for it in 1..max_iter:
      drc = drc_check_device(kind, params)        # D-15 可制造性自查
      if drc.passed: break
      params = apply_fixes(kind, params, drc)     # 读 violation 按规则调整
    → 版图 SVG + 最终 DRC PASS 报告 + 整改轨迹（violation 数逐轮下降）

修复规则（margin 默认 1.1× 留余量）：
  min_width  → 增大 width / wg_width
  min_bend_R → 增大 R
  min_space  → 增大 gap
  max_split  → 减小 split_angle

零外部依赖（复用 lda_l2.drc / gds_export）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lda_l2.drc import DEFAULT_RULES, drc_check_device
from lda_l2.gds_export import geometry_desc, svg_preview


# ---------------------------------------------------------------------------
# 整改轨迹
# ---------------------------------------------------------------------------
@dataclass
class FixStep:
    iteration: int
    params: Dict[str, float]
    n_violations: int
    violations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"iteration": self.iteration, "params": self.params,
                "n_violations": self.n_violations,
                "violations": self.violations}


# ---------------------------------------------------------------------------
# DRC 回读整改 agent
# ---------------------------------------------------------------------------
class DrcFixAgent:
    """编排器：DRC 自查 → 读 violation → 调参整改 → 重查，直至可制造。"""

    def __init__(self, margin: float = 1.1, rules: Optional[Dict[str, float]] = None):
        self.margin = margin
        self.rules = rules or DEFAULT_RULES

    def run(self, kind: str, params: Dict[str, float],
            max_iter: int = 12) -> Dict:
        cur = {k: float(v) for k, v in params.items()}
        trace: List[FixStep] = []
        final_drc = None

        for it in range(1, max_iter + 1):
            drc = drc_check_device(kind, cur, self.rules)
            violations = drc.violations()
            trace.append(FixStep(it, dict(cur), len(violations),
                                 [c.brief() for c in violations]))
            final_drc = drc
            if drc.passed:
                break
            cur = self._apply_fixes(kind, cur, violations)

        accepted = bool(final_drc and final_drc.passed)
        return {
            "kind": kind,
            "accepted": accepted,
            "iterations": len(trace),
            "final_params": cur,
            "trace": [s.to_dict() for s in trace],
            "drc": final_drc.to_dict() if final_drc else {},
            "layout_svg": self._svg(kind, cur),
            "verdict": self._verdict(kind, cur, accepted, len(trace)),
        }

    # ---- 读 violation 按规则调整（margin 留余量）----
    def _apply_fixes(self, kind: str, params: Dict[str, float],
                     violations) -> Dict[str, float]:
        for c in violations:
            if c.rule == "min_width" and c.param in ("width", "wg_width", "w_core"):
                params[c.param] = c.required * self.margin
            elif c.rule == "min_bend_R" and c.param == "R":
                params["R"] = c.required * self.margin
            elif c.rule == "min_space" and c.param == "gap":
                params["gap"] = c.required * self.margin
            elif c.rule == "max_split" and c.param == "split_angle":
                params["split_angle"] = c.required / self.margin
        return params

    @staticmethod
    def _svg(kind: str, params: Dict[str, float]) -> str:
        """整改后版图 SVG 预览（供 webui / 报告展示）。"""
        descs = geometry_desc(kind, params)
        items = []
        for d in descs:
            layer = d.get("layer", 1)
            if d["kind"] == "boundary":
                rings = d.get("rings_um", [d.get("points_um", [])])
                pts = []
                for r in rings:
                    pts.extend(r)
                    pts.append(r[0])
                items.append(("boundary", {"points_um": pts, "layer": layer}))
            else:
                items.append((d["kind"], {"points_um": d.get("points_um", []),
                                          "width_um": d.get("width_um", 0.5),
                                          "layer": layer}))
        return svg_preview({kind: items})

    @staticmethod
    def _verdict(kind: str, params: Dict[str, float], accepted: bool,
                 iters: int) -> str:
        if accepted:
            return (f"agent 自动整改 {iters} 轮使 {kind} 可制造："
                    f"最终参数 {params}，DRC 全 PASS。")
        return (f"整改 {iters} 轮未全过（可能规则矛盾/超出工艺窗口）："
                f"最终参数 {params}。请放宽工艺规则或人工介入。")


def demo_fix(kind: str = "RingResonator", bad_params: Optional[Dict] = None
             ) -> Dict:
    """演示：给一个 DRC 违规初值，agent 自动整改到可制造。

    默认构造一个违规环形（R=2µm < 最小弯曲半径 5µm）。
    """
    defaults = {
        "RingResonator": {"R": 2.0, "wg_width": 0.3},   # R 与宽度都违规
        "Waveguide": {"width": 0.2},
        "DirectionalCoupler": {"gap": 0.1, "width": 0.5},
        "SymmetricYBranch": {"width": 0.5, "split_angle": 45.0},
    }
    return DrcFixAgent().run(kind, bad_params or defaults[kind])
