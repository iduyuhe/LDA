"""超导 transmon 单元 门禁 smoke（D-133 · S1 · 几何 DRC/LVS 签核）。

═══ 为什么要有这个 smoke ═══
D-133 把「超导芯片能设计出来」补成闭环（gds_export 注册 kind=Transmon +
几何 DRC/LVS）。这类「新增版图原语 + 签核」半年后最易被悄悄降级（例如把 JJ
桥接检查删掉、把限值改成好看），必须钉成常驻断言：

  ① **合法单元 DRC/LVS 双 ACCEPT**（默认参数）
  ② **DRC 各规则可触发 REJECT**（CPW 太细 / 地与 qubit 短接）
  ③ **LVS 各判据可触发 REJECT**（JJ 不桥接 / 悬空导体 / 地短接）
  ④ **诚实标注 + 红线**（限值为设计规则 · 零量子 SDK · 判决死标量）
  ⑤ **GDS round-trip**（真出 GDS → parse_gds 读回含 SC 层 10/11/12）
  ⑥ **跨模块物理**（复用 D-35 transmon_solver：Koch ↔ 严格对角化 rel≤3%）

运行：python run_schip_s1_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_SCHIP_TMP = os.path.join(_HERE, "reports", "schip_tmp")
os.makedirs(_SCHIP_TMP, exist_ok=True)

from lda_qeda import sc_layout as SCD                           # noqa: E402
import lda_solver.transmon_solver as TS                         # noqa: E402
from lda_harness.smoke_kit import make_check                    # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)


def main() -> int:
    print("=" * 78)
    print("超导 transmon 单元 门禁 smoke（D-133 · S1 · 几何 DRC/LVS）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 ════════════════
    print("── A 模块自检 ──")
    try:
        ok_a = SCD.run_selfchecks(verbose=False)
    except Exception as e:                                       # noqa: BLE001
        ok_a = False
        print(f"  run_selfchecks 异常：{type(e).__name__}: {e}")
    check("A1 D-133 模块自检 7/7 PASS（合法 ACCEPT/ACCEPT · 四类违规各 REJECT）",
          ok_a, "合法双 ACCEPT + CPW过细/JJ不桥接/悬空/地短接 各 REJECT")

    # ════════════════ B 节：DRC 规则可触发 ════════════════
    print("── B 超导 DRC 规则 ──")
    base = SCD.transmon_cell({})
    check("B1 合法单元 DRC ACCEPT（4 规则全过）",
          SCD.run_sc_drc(base)["verdict"] == "ACCEPT",
          f"verdict={SCD.run_sc_drc(base)['verdict']}")
    thin = SCD.transmon_cell({"cpw_w": 0.1})
    vt = SCD.run_sc_drc(thin)
    check("B2 CPW 太细(0.1<0.2) ⇒ DRC REJECT（SCD-MIN-WIDTH）",
          vt["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-WIDTH" for v in vt["violations"]),
          f"violations={[v['rule'] for v in vt['violations']]}")
    short = SCD.transmon_cell({"ground_gap": -0.5})
    vs = SCD.run_sc_drc(short)
    check("B3 地与 qubit 短接(ground_gap<0) ⇒ DRC REJECT（SCD-QUBIT-GROUND-SHORT）",
          vs["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-QUBIT-GROUND-SHORT" for v in vs["violations"]),
          f"violations={[v['rule'] for v in vs['violations']]}")
    smallgap = SCD.transmon_cell({"ground_gap": 0.1})
    vg = SCD.run_sc_drc(smallgap)
    check("B4 地间隙 0.1<0.5 ⇒ DRC REJECT（SCD-MIN-GROUND-GAP）",
          vg["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-GROUND-GAP" for v in vg["violations"]),
          f"violations={[v['rule'] for v in vg['violations']]}")
    jjbad = SCD.transmon_cell({"jj_len": 0.1})
    vj = SCD.run_sc_drc(jjbad)
    check("B5 JJ 太薄(0.1<0.15) ⇒ DRC REJECT（SCD-MIN-JJ）",
          vj["verdict"] == "REJECT"
          and any(v["rule"] == "SCD-MIN-JJ" for v in vj["violations"]),
          f"violations={[v['rule'] for v in vj['violations']]}")
    check("B6 规则名 / n_rules 稳定（SCD_RULES=4 条 · n_rules=4）",
          len(SCD.SCD_RULES) == 4 and SCD.run_sc_drc(base)["n_rules"] == 4,
          f"SCD_RULES={len(SCD.SCD_RULES)}")

    # ════════════════ C 节：LVS 连接性可触发 ════════════════
    print("── C 超导 LVS 连接性 ──")
    check("C1 合法单元 LVS ACCEPT（qubit 连通 · JJ 桥接 · 地与 qubit 不重叠）",
          SCD.sc_lvs_signoff(base)["verdict"] == "ACCEPT",
          f"netlist={SCD.sc_lvs_signoff(base)['netlist']}")
    nobridge = SCD.transmon_cell({"jj_len": 0.1})
    vnb = SCD.sc_lvs_signoff(nobridge)
    check("C2 JJ 不桥接 ⇒ LVS REJECT（SCD-LVS-JJ-NOT-BRIDGING）",
          vnb["verdict"] == "REJECT"
          and any("JJ-NOT-BRIDGING" in i for i in vnb["issues"]),
          f"issues={vnb['issues']}")
    floating = base + [{"kind": "boundary", "layer": SCD.LIB_LAYER_SC_FILM,
                        "net": "qubit",
                        "rings_um": [[(40, 40), (42, 40), (42, 42), (40, 42)]]}]
    vf = SCD.sc_lvs_signoff(floating)
    check("C3 悬空导体 ⇒ LVS REJECT（SCD-LVS-FLOATING-QUBIT）",
          vf["verdict"] == "REJECT"
          and any("FLOATING" in i for i in vf["issues"]),
          f"issues={vf['issues']}")
    vsh = SCD.sc_lvs_signoff(short)
    check("C4 地短接 ⇒ LVS REJECT（SCD-LVS-QUBIT-GROUND-SHORT）",
          vsh["verdict"] == "REJECT"
          and any("GROUND-SHORT" in i for i in vsh["issues"]),
          f"issues={vsh['issues']}")
    nonet = base + [{"kind": "boundary", "layer": SCD.LIB_LAYER_SC_FILM,
                     "rings_um": [[(40, 40), (42, 40), (42, 42), (40, 42)]]}]
    vnn = SCD.sc_lvs_signoff(nonet)
    check("C5 无 net 标签导体 ⇒ LVS REJECT（SCD-LVS-NO-NET）",
          vnn["verdict"] == "REJECT"
          and any("NO-NET" in i for i in vnn["issues"]),
          f"issues={vnn['issues']}")
    check("C6 LVS n_checks=5（连通性/桥接/地/端口/无net 五判据）",
          SCD.sc_lvs_signoff(base)["n_checks"] == 5,
          f"n_checks={SCD.sc_lvs_signoff(base)['n_checks']}")

    # ════════════════ D 节：诚实标注 + 红线 ════════════════
    print("── D 诚实标注 + 红线 ──")
    disc = SCD.RED_LINE_DISCLOSURE
    check("D1 披露齐备：role/layers/limits/lvs/red_line 五键",
          all(k in disc for k in ("role", "layers", "limits", "lvs", "red_line")),
          f"键={sorted(disc)}")
    check("D2 限值为设计规则 · 非实测 golden（明确标注 D5 外部依赖）",
          "设计规则" in disc["limits"] and "非实测 golden" in disc["limits"]
          and "D5" in disc["limits"], "默认限值为设计规则口径")
    src = open(os.path.join(_HERE, "lda_qeda", "sc_layout.py"), encoding="utf-8").read()
    banned = ("qiskit", "cirq", "pennylane", "strawberryfields", "thewalrus", "qutip")
    hits = [b for b in banned if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("D3 红线：D-133 零量子 SDK 依赖（纯几何 + 平台，C 级自主）",
          not hits, f"命中={hits or '无'}")
    drc_v = SCD.run_sc_drc(base)
    check("D4 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          drc_v["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in drc_v["violations"]),
          "rule/detail 二元组 · 纯限值比对")

    # ════════════════ E 节：GDS round-trip ════════════════
    print("── E GDS 真出 + 解析 round-trip ──")
    data = SCD.transmon_gds({}, os.path.join(_SCHIP_TMP, "_sc_s1_tmp.gds"))
    parsed = SCD.G.parse_gds(data)
    layers = set()
    total_elems = 0
    for st in parsed.get("structures", {}).values():
        layers |= set(st.get("layers", []))
        total_elems += st.get("elements", 0)
    check("E1 真出 GDSII（含 SC 层 10/11/12）",
          bool(data) and {10, 11, 12}.issubset(layers),
          f"layers={sorted(layers)} · bytes={len(data)}")
    check("E2 parse_gds 读回：结构数≥1 · 元素数>0 · 含 SC 层 10/11/12",
          parsed.get("n_structures", 0) >= 1 and total_elems > 0
          and {10, 11, 12}.issubset(layers),
          f"structs={parsed.get('n_structures')} · elems={total_elems} · layers={sorted(layers)}")

    # ════════════════ F 节：跨模块物理（复用 D-35）═══════════════
    print("── F 跨模块物理（D-35 transmon_solver）──")
    ej, ec = 11.3, 0.30
    sol = TS.solve_transmon(ej, ec)
    f_an = TS.koch_f01(ej, ec)
    rel = abs(sol["f01"] - f_an) / f_an
    check("F1 Koch 解析 ↔ 严格对角化 rel≤3%（E_J=11.3,E_C=0.30）",
          rel <= 0.03, f"f01_diag={sol['f01']:.4f} · koch={f_an:.4f} · rel={rel:.2%}")
    check("F2 物理产出合理：f01∈[4,6] GHz · α<0（transmon 工作区）",
          4.0 <= sol["f01"] <= 6.0 and sol["alpha"] < 0,
          f"f01={sol['f01']:.3f} · α={sol['alpha']:.3f}")

    print()
    print(f"超导 transmon 单元 门禁 smoke（D-133）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
