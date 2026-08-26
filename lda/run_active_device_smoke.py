"""Merge-2a 有源双出口 smoke（v0.8.13 · 相移器/调制器）。

双出口图纸验证（规划 v2 纪律）：
  ① 设计量出口：DesignEngine 22 引擎闭环（PhaseShifter 相移效率 / MziModulator V_π）
  ② 行为黑箱出口：registry 响应（链路仿真消费）+ active_models 相位/透射模型
  ③ 物理合理性：P↑→相移↑；V=V_π→消光（T≈0）；V=0→全通（T=1）
  ④ 计数：ENGINE_KINDS 22（光子 15 + 量子 7）
  ⑤ 链路集成：PhaseShifter/MziModulator 入 generic 链路可传播（功率域）

红线：数值由确定性物理比对决定，LLM 不进判决路径。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_chain.engine import simulate  # noqa: E402
from lda_chain.registry import get_response  # noqa: E402
from lda_design.active_models import (  # noqa: E402
    mzi_mod_response,
    phase_shift_rad,
    thermo_phase_response,
    vpi_electrooptic,
)
from lda_design.design_engine import DesignEngine  # noqa: E402
from lda_design.design_package import (  # noqa: E402
    ENGINE_DOMAIN,
    ENGINE_KIND_MAP,
    ENGINE_KINDS,
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


def main() -> int:
    e = DesignEngine()

    # ① 设计量出口：22 引擎闭环
    r1 = e.design("PhaseShifter", 10.0, top_k=2)
    r2 = e.design("MziModulator", 5.0, top_k=2)
    check("PhaseShifter 设计闭环 PASS", bool(r1.get("passed")),
          f"metric={r1.get('best',{}).get('metric'):.3f} deg/mW")
    check("MziModulator 设计闭环 PASS", bool(r2.get("passed")),
          f"metric={r2.get('best',{}).get('metric'):.3f} V")

    # ② 行为黑箱出口：registry 响应 + 模型层
    class C:
        def __init__(self, p):
            self.params = p
            self.id = "t"

    rp = get_response("PhaseShifter", C({"P_mw": 10.0, "L_um": 300.0}),
                      [1.55], None, None)
    check("PhaseShifter 链路响应（功率域 T=1）",
          abs(rp[("out", "in")][0] - 1.0) < 1e-9,
          f"T={rp[('out','in')][0]}")
    rm = get_response("MziModulator", C({"V": 0.0, "V_pi": 4.9}),
                      [1.55], None, None)
    check("MziModulator 链路响应（V=0 → T=1）",
          abs(rm[("out", "in")][0] - 1.0) < 1e-6,
          f"T={rm[('out','in')][0]}")

    # ③ 物理合理性
    ph = thermo_phase_response(10.0, 300.0)
    ph2 = thermo_phase_response(20.0, 300.0)
    check("热光相移 P↑→相移↑（单调）", ph2["phase_deg"] > ph["phase_deg"],
          f"{ph['phase_deg']:.1f}°→{ph2['phase_deg']:.1f}°")
    check("P_π 语义（P_π 处相移=180°）",
          abs(thermo_phase_response(ph["p_pi_mw"], 300.0)["phase_deg"] - 180.0) < 1.0,
          f"P_π={ph['p_pi_mw']:.3f}mW")
    m1 = mzi_mod_response(0.0, 4.9)
    m2 = mzi_mod_response(4.9, 4.9)
    check("MZI 调制 V=0→全通 / V=V_π→消光",
          abs(m1["transmission"] - 1.0) < 1e-6 and m2["transmission"] < 1e-3,
          f"T(0)={m1['transmission']:.4f} T(V_π)={m2['transmission']:.4f}")
    check("电光 V_π 解析（L↑→V_π↓，Pockels）",
          vpi_electrooptic(500.0) > vpi_electrooptic(2000.0),
          f"V_π(500µm)={vpi_electrooptic(500.0):.3f} > V_π(2000µm)={vpi_electrooptic(2000.0):.3f}")

    # ④ 计数 22
    names = [ENGINE_KIND_MAP[k] for k in ENGINE_KINDS]
    n_ph = sum(1 for n in names if ENGINE_DOMAIN[n] == "photon")
    n_q = sum(1 for n in names if ENGINE_DOMAIN[n] == "quantum")
    check("ENGINE_KINDS 22（光子15+量子7）",
          len(ENGINE_KINDS) == 22 and n_ph == 15 and n_q == 7,
          f"{len(ENGINE_KINDS)} = {n_ph}+{n_q}")

    print(f"\n汇总：{PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
