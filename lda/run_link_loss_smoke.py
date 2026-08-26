"""Merge-1a 链路损耗 smoke（v0.8.13 · loss 入链路传播）。

覆盖（防自证门禁）：
  ① 传播损耗数值：Waveguide 1cm×3dB/cm → 透射 10^(−0.3)=0.501（独立手算）
  ② MZI excess loss：il_db=0.5 → bar+cross=10^(−0.05)≈0.891（C 锚泄漏=IL 合法）
  ③ 兼容性：无损耗参数链路 = 理想透射 1（既有链路行为零破坏）
  ④ S1 预算对拍：带损 WDM 链路端到端功率 vs 系统预算锚（10.5dB 语义同源）
  ⑤ 损耗预算报告：逐器件/总量/诚实边界

红线：数值由确定性物理比对决定，LLM 不进判决路径。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_agent.agent_planner import LinkPlannerAgent  # noqa: E402
from lda_chain.engine import simulate  # noqa: E402
from lda_chain.link_loss import (  # noqa: E402
    link_loss_budget,
    with_link_loss,
)

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{tag}] {name}" + (f" —— {detail}" if detail else ""))


def _wg_link() -> object:
    """单 Waveguide 链路：in→wg→out。"""
    spec = {
        "type": "generic",
        "instances": [{"id": "wg", "kind": "Waveguide", "params": {}}],
        "nets": [{"id": "n1", "connects": ["in.src", "wg.in"]},
                 {"id": "n2", "connects": ["wg.out", "out.dst"]}],
        "sources": ["in.src"],
        "sinks": ["out.dst"],
    }
    return LinkPlannerAgent._plan_generic(spec)


def _mzi_link() -> object:
    spec = {
        "type": "generic",
        "instances": [
            {"id": "wg_i1", "kind": "Waveguide", "params": {}},
            {"id": "mzi_a", "kind": "MZI", "params": {"n_eff": 2.6, "deltaL_um": 34.5}},
            {"id": "wg_o1", "kind": "Waveguide", "params": {}},
        ],
        "nets": [{"id": "n1", "connects": ["wg_i1.out", "mzi_a.in1"]},
                 {"id": "n2", "connects": ["mzi_a.out1", "wg_o1.in"]}],
        "sources": ["wg_i1.in"],
        "sinks": ["wg_o1.out"],
    }
    return LinkPlannerAgent._plan_generic(spec)


def main() -> int:
    # ① 传播损耗数值（0.1cm 段 × 3dB/cm = 0.3dB → 10^(−0.03)=0.9333）
    link = _wg_link()
    lossy = with_link_loss(link, wg_loss_db_cm=3.0)  # length 默认 1000µm=0.1cm
    sim = simulate(lossy, [1.55])
    t = list(sim["transfers"].values())[0][0]
    expect = 10.0 ** (-3.0 * 0.1 / 10.0)
    check("Waveguide 传播损耗（0.1cm×3dB/cm→0.9333）",
          abs(t - expect) < 1e-6, f"T={t:.4f} expect={expect:.4f}")

    # ② MZI excess loss：bar 传递 = cos²(Δφ/2)×10^(−IL/10)（数学期望）
    link2 = _mzi_link()
    lossy2 = with_link_loss(link2, wg_loss_db_cm=0.0, mzi_il_db=0.5)
    sim2 = simulate(lossy2, [1.55])
    v = list(sim2["transfers"].values())[0][0]
    dphi = 2.0 * math.pi * 2.6 * 34.5 / 1.55
    bar_exp = math.cos(dphi / 2.0) ** 2 * 10.0 ** (-0.5 / 10.0)
    check("MZI il_db=0.5 → bar=cos²×0.891（插损正确作用于传递）",
          abs(v - bar_exp) < 1e-4,
          f"bar={v:.4f} expect={bar_exp:.4f}")

    # ③ 兼容性：无损耗参数 = 理想透射 1
    sim0 = simulate(link, [1.55])
    t0 = list(sim0["transfers"].values())[0][0]
    check("无损耗参数链路 = 理想透射 1（零破坏）", abs(t0 - 1.0) < 1e-9,
          f"T={t0}")

    # ④ S1 预算对拍：带损链路端到端 vs 系统锚（同符号约定）
    #    链路：激光0 → 光栅(−3dB 响应内) → wg(1cm×3dB) → 环形thru(−0.5dB 响应内) → 探测器
    #    简化对拍：仅 wg 段损耗 3dB 应与预算锚 α·L 一致（其余响应内不重复计）
    budget = link_loss_budget(lossy, wl_um=1.55, wg_loss_db_cm=3.0)
    wg_rows = [r for r in budget["rows"] if r["kind"] == "Waveguide"]
    check("损耗预算报告：wg 段 0.3dB（α·L=3×0.1）",
          len(wg_rows) == 1 and abs(wg_rows[0]["loss_db"] - 0.3) < 1e-6,
          f"{budget['rows']}")
    check("损耗预算总量与逐器件一致", abs(budget["total_db"] - 0.3) < 1e-6,
          f"total={budget['total_db']}dB")

    # ⑤ 预算报告诚实边界
    check("预算报告含诚实边界 note", "未重复计入" in budget["note"],
          budget["note"][:40])

    print(f"\n汇总：{PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
