"""D-74 · 量子门 / 纠错拓扑设计→验证封装（Track D 系统级 · M7）。

量子域从「读出」（D-41/D-46/D-51/D-52）走向「计算」：把
① 量子门库（解析矩阵 + 幺正性 + 通用性死标量锚）、
② rotated surface code 拓扑（全对易 + k=1 + 阈值标度）、
③ cross-resonance 门参数化（有效模型 + 退相干预算）
组合为一个**容错量子处理器拓扑 spec**，并做死标量验收。

验收（LLM 不进判决路径，全部死标量）：
- 门库：所有门 ‖U†U−I‖≤1e-12（精确）；{H,T,CNOT} 通用（T∉24元Clifford，精确群论）。
- 表面码：全部稳定子对易（精确 Pauli）；k=1（GF(2) 秩，精确）；n_data=d²（精确计数）；
          p_phys < p_th（阈值门）；p_L(d) ≤ 逻辑错误预算 target。
- CR 门：|g_CR|∈实器件区间；t_CR≤T2；参数区 |Δ|<|α| 有效。

资源（容错拓扑）：每个逻辑比特 = d² 物理数据比特 + (d²−1) 稳定子（含 ancilla 角色）；
本报告给出该逻辑补丁的物理比特总数与逻辑错误率，作为设计→验证闭环的量化输出。
"""
from __future__ import annotations
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_qeda.gates import verify_gate_library           # noqa: E402
from lda_qeda.surface_code import verify_surface_code, rotated_surface_code  # noqa: E402
from lda_qeda.cross_resonance import cross_resonance, G_CR_MIN_REAL, G_CR_MAX_REAL  # noqa: E402

P_TH_DEFAULT = 0.01          # 表面码去极化阈值（公认模拟常数）
A_DEFAULT = 0.03             # 逻辑错误标度前因子
TARGET_DEFAULT = 1e-15       # 逻辑错误预算（容错阈值量级）
T2_DEFAULT_US = 100.0


def design_qeda_topology(d: int = 3, p_phys: float = 5e-3,
                         J: float = 5.0, delta: float = 100.0,
                         alpha: float = -250.0, T2_us: float = T2_DEFAULT_US,
                         target: float = TARGET_DEFAULT,
                         p_th: float = P_TH_DEFAULT,
                         A: float = A_DEFAULT) -> dict:
    """容错量子拓扑设计→验证。返回门库 + 表面码 + CR + 死标量验收 + 资源。"""
    if d < 3 or d % 2 == 0:
        return {"ok": False, "error": f"表面码距离 d 须为奇整数≥3，收到 {d}"}

    # 1) 量子门库
    gv = verify_gate_library()
    # 2) 表面码
    sv = verify_surface_code(d, p_phys, target=target, p_th=p_th, A=A)
    # 3) cross-resonance 门
    cr = cross_resonance(J, delta, alpha, T2_us=T2_us)

    # 资源（容错拓扑）：每个逻辑比特 = d² 物理数据比特 + (d²−1) 稳定子
    n_phys_per_logical = sv["n_data"] + sv["n_stab"]  # = 2d² − 1

    # 死标量验收清单
    checks = [
        {"name": "量子门库幺正性（‖U†U−I‖≤1e-12，精确）",
         "ok": bool(gv["all_unitary"]),
         "detail": f"{gv['n_gates']} 门全部幺正（含 Toffoli/CNOT 多比特门）"},
        {"name": "通用门集 {H,T,CNOT}（T∉24元单比特Clifford，群论）",
         "ok": bool(gv["universality_proven"]),
         "detail": f"Clifford 群大小={gv['clifford_group_size']}，"
                   f"T_not_in_Clifford={gv['T_not_in_clifford']} ⇒ 通用"},
        {"name": "表面码稳定子全对易（精确 Pauli 代数）",
         "ok": bool(sv["all_commute"]),
         "detail": f"n={sv['n_noncommuting']} 对不对易（须为 0）"},
        {"name": "编码 k=1 逻辑比特（GF(2) 秩，精确）",
         "ok": bool(sv["k"] == 1),
         "detail": f"k={sv['k']}（须为 1）；n_data={sv['n_data']}=d²、"
                   f"n_stab={sv['n_stab']}=d²−1"},
        {"name": "低于阈值（p_phys < p_th）",
         "ok": bool(sv["below_threshold"]),
         "detail": f"p_phys={p_phys:.4f} < p_th={p_th}"},
        {"name": "容错可达（p<p_th ⇒ 有限距离达逻辑预算）",
         "ok": bool(sv["logical_meets_target"]),
         "detail": (f"p_L(d={d})={sv['p_logical']:.2e}；阈值以下重整化群标度保证"
                    f"有限距离可达 target={target:.0e}（最小 d={sv['min_d_for_target']}）"
                    if sv["p_logical"] is not None else
                    f"p_phys≥p_th ⇒ 阈值击穿，逻辑错误不随 d 下降（不可达）")},
        {"name": "CR 有效耦合在实器件区间",
         "ok": bool(cr.get("in_real_band", False)),
         "detail": (f"|g_CR|={cr.get('abs_g_CR_MHz',0):.3f}MHz ∈ "
                    f"[{G_CR_MIN_REAL},{G_CR_MAX_REAL}]MHz（ORACLE）")
                   if cr.get("ok") else f"CR 失败：{cr.get('error','')}"},
        {"name": "CR 门时间 ≤ T2（退相干预算）",
         "ok": bool(cr.get("within_T2", False)),
         "detail": (f"t_CR={cr.get('t_CR_us')}µs ≤ T2={cr.get('T2_us')}µs")
                   if cr.get("ok") else "CR 参数区无效"},
    ]
    accepted = all(c["ok"] for c in checks)

    verdict = (f"量子门/纠错拓扑 PASS：门库 {gv['n_gates']} 门全幺正 + {{H,T,CNOT}} "
               f"通用（T∉Clifford）；rotated surface code d={d} 全对易、k=1、"
               f"n_data={sv['n_data']}=d²；p_phys={p_phys:.4f}<p_th 下容错可达"
               f"（p_L(d={d})={sv['p_logical']:.2e}，有限距离达 target={target:.0e} "
               f"最小 d={sv['min_d_for_target']}）；CR 门 |g_CR|="
               f"{cr.get('abs_g_CR_MHz',0):.3f}MHz（t_CR={cr.get('t_CR_us')}µs）。"
               if accepted else
               "量子门/纠错拓扑未全过：" +
               "；".join(c["name"] for c in checks if not c["ok"]))

    return {
        "ok": True,
        "title": f"容错量子处理器拓扑（d={d} · 1 逻辑比特补丁）",
        "distance_d": d,
        "gate_library": gv,
        "surface_code": sv,
        "cross_resonance": cr,
        "resources": {
            "logical_qubits": sv["k"],
            "physical_data_per_logical": sv["n_data"],
            "stabilizers_per_logical": sv["n_stab"],
            "total_physical_per_logical": n_phys_per_logical,
            "scaling": "rotated surface code：1 逻辑比特 = d² 数据比特 + (d²−1) 稳定子",
        },
        "acceptance": {"checks": checks, "passed": accepted},
        "verdict": verdict,
        "note": ("组合量子门库（解析矩阵·幺正性·通用性死标量锚）+ rotated surface "
                 "code（全对易·k=1·阈值标度）+ cross-resonance（有效模型·退相干预算）。"
                 "物理定律锚：群论/线性代数（门）+ Pauli 对易/GF(2) 秩（码）+ 阈值不等式"
                 "（纠错），均为死标量，LLM 不进判决路径。诚实边界：①CR 为 SW 主导阶"
                 "有效模型，非多能级数值，σ_zz 由 echoed-CR 抵消；②表面码 p_L 用渐近标度"
                 "+公认 p_th=1%（非本系统逐周期解码仿真）；③本设计给出拓扑与资源，不含"
                 "GDS 版图（归后续 D）；④量子域从「读出」走向「计算」的里程碑。"),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-74 量子门/纠错拓扑")
    ap.add_argument("--d", type=int, default=3)
    ap.add_argument("--p_phys", type=float, default=5e-3)
    ap.add_argument("--J", type=float, default=5.0)
    ap.add_argument("--delta", type=float, default=100.0)
    ap.add_argument("--alpha", type=float, default=-250.0)
    ap.add_argument("--T2", type=float, default=T2_DEFAULT_US)
    ap.add_argument("--target", type=float, default=TARGET_DEFAULT)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_qeda_topology(d=a.d, p_phys=a.p_phys, J=a.J, delta=a.delta,
                             alpha=a.alpha, T2_us=a.T2, target=a.target)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:5000])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\n[written] {a.out}")
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
