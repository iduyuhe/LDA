"""电子计算芯片版图与几何签核 门禁 smoke（E6 · D-156）。

═══ 为什么要有这个 smoke ═══
E6 让电子征程**第一次能出真 GDS**（版图层栈 + 1T 交叉阵列 P&R + 几何 DRC +
段感知 LVS）。这类「新增版图原语 + 签核」半年后最易被悄悄降级（改限值让 DRC 恒绿、
删掉短路判据、把层次化 AREF 弄成只出一个 cell）⇒ 必须钉成常驻断言 + **突变探针**。

  ① **合法阵列 DRC/LVS 双 ACCEPT**（4×4 与 8×8）
  ② **足迹 = 节距闭式**（bbox 与解析式一致）
  ③ **AREF 层次化展开元素数 ≡ flat**（平台 P0-1 纪律：不展开 ⇒ DRC 假绿）
  ④ **W/L 几何回提 ≡ 声明**（版图 → 器件尺寸逆向，逐单元一致）
  ⑤ **各类违规可触发 REJECT**（DRC：线宽/包围；LVS：短路/尺寸失配/悬空桥/缺端口）
  ⑥ **吃狗粮闭环**：回提 W/L → E1 MOSFET 模型 → 饱和电流/跨导可用（版图↔电路一致）
  ⑦ **诚实边界 + 红线**（限值为设计规则 · 零商业 EDA 依赖 · 判决死标量 · 无 TOPS 自夸）
  ⑧ **突变探针**（改限值/改足迹/改回提/退回旧 bbox 各必红 + 还原复绿）

运行：python run_ecore_e6_smoke.py（cwd=lda/）
出口：全 PASS 退 0；任一 FAIL 退 1。**LLM 不进判决路径**。
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))       # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_TMPDIR = tempfile.gettempdir()                          # 临时 GDS 不落仓库

from lda_l2.ecore import elayers as EL                   # noqa: E402
from lda_l2.ecore import layout as LY                    # noqa: E402
from lda_l2.ecore.mosfet import NmosParams               # noqa: E402
from lda_l2.ecore.analog_mvm import mosfet_saturation_bias  # noqa: E402
from lda_harness.smoke_kit import make_check             # noqa: E402

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=" | {d}", return_ok=True)

N, M = 4, 4


# ═══════════════ 绿色判据用的可复用小函数（突变探针复用同一份）═══════════════
def _legal_drc() -> bool:
    arr = LY.crossbar_array(N, M)
    return LY.run_edrc(arr["descs"])["verdict"] == "ACCEPT"


def _legal_lvs() -> bool:
    arr = LY.crossbar_array(N, M)
    return LY.elvs_signoff(arr["descs"], LY.expected_netlist(N, M))["verdict"] == "ACCEPT"


def _footprint_ok() -> bool:
    arr = LY.crossbar_array(N, M)
    bs = [LY._bbox(d) for d in arr["descs"]]
    W = max(b[1] for b in bs) - min(b[0] for b in bs)
    H = max(b[3] for b in bs) - min(b[2] for b in bs)
    fW, fH = LY.array_footprint(N, M)
    return abs(W - fW) < 1e-6 and abs(H - fH) < 1e-6


def _wl_ok() -> bool:
    arr = LY.crossbar_array(N, M)
    wl = LY.extract_wl(arr["descs"])
    e = LY.expected_netlist(N, M)
    return (abs(wl["W_um"] - e["W_um"]) < 1e-6
            and abs(wl["L_um"] - e["L_um"]) < 1e-6 and wl["uniform"])


# ═══════════════ 突变探针（每个都先证「真能变红」）═══════════════
def probe_drc_limits() -> bool:
    """把最小线宽限值抬到天上 ⇒ 合法阵列 DRC 必红（证 DRC 真的读规则表）。"""
    bad = dict(EL.ELEC_DESIGN_RULES)
    for k in list(bad):
        if k.endswith("_min_width_um") or k in ("cont_size_um", "via1_size_um"):
            bad[k] = 1e9
    with mock.patch.object(EL, "ELEC_DESIGN_RULES", bad):
        return not _legal_drc()


def probe_footprint_golden() -> bool:
    """把足迹闭式改错 ⇒ 足迹判据必红（证判据真在比对闭式）。"""
    with mock.patch.object(LY, "array_footprint", lambda n, m, p=None: (99.0, 99.0)):
        return not _footprint_ok()


def probe_wl_backextract() -> bool:
    """篡改 W/L 回提结果 ⇒ W/L 判据必红（证回提真的被消费）。"""
    real = LY.extract_wl

    def bad(descs):
        r = dict(real(descs))
        r["L_um"] = 0.999
        return r

    with mock.patch.object(LY, "extract_wl", bad):
        return not _wl_ok()


def probe_bbox_regression() -> bool:
    """退回「path 两向都加半宽」的旧 bbox ⇒ 足迹判据必红（防该 bug 回归）。"""
    def old_bbox(d):
        if d["kind"] == "path":
            w = float(d.get("width_um", 0.0)) / 2.0
            xs = [p[0] for p in d["points_um"]]
            ys = [p[1] for p in d["points_um"]]
            return (min(xs) - w, max(xs) + w, min(ys) - w, max(ys) + w)
        pts = [p for r in d["rings_um"] for p in r]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), max(xs), min(ys), max(ys))

    with mock.patch.object(LY, "_bbox", old_bbox):
        return not _footprint_ok()


def main() -> int:
    print("=" * 78)
    print("电子计算芯片版图与几何签核 门禁 smoke（E6 · D-156）")
    print("=" * 78)

    # ════════════════ A 节：模块自检 ════════════════
    print("── A 模块自检 ──")
    ok_a1 = EL.run_selfcheck(verbose=False)
    check("A1 elayers 自检 10/10（层序/桥映射/短路谓词/层号/规则）", ok_a1,
          "信号层 M1/M2 · 桥 CONT/VIA1 · 同层判短异层不判短")
    ok_a2 = LY.run_selfchecks(verbose=False)
    check("A2 layout 自检 9/9（DRC/LVS/足迹/AREF/W-L/三类违规各 REJECT）", ok_a2,
          "合法双 ACCEPT + 接触孔小/焊垫搭行线/尺寸失配 各 REJECT")

    # ════════════════ B 节：层栈语义 ════════════════
    print("── B 电子层栈语义 ──")
    st = EL.get_estack()
    check("B1 信号层 [M1,M2] · 桥层 [CONT,VIA1]", 
          st.signal_layers() == ["M1", "M2"]
          and sorted(st.bridge_layers()) == ["CONT", "VIA1"], f"{st.to_summary()['via_map']}")
    check("B2 同层 M1 相交判短 / 异层 M1-M2 垂直重叠不判短",
          st.can_short("M1", "M1") is True and st.can_short("M1", "M2") is False,
          "介质隔离语义")
    check("B3 CONT 多对桥（DIFF↔M1 与 POLY↔M1）· VIA1 桥 M1↔M2",
          st.bridge_connects("CONT", "DIFF", "M1")
          and st.bridge_connects("CONT", "POLY", "M1")
          and st.bridge_connects("VIA1", "M1", "M2"), "via_map 集合语义")
    check("B4 层号 20..25 连续（DIFF/POLY/CONT/M1/VIA1/M2）",
          [n for n in st.order() if n != "PAD"] == ["DIFF", "POLY", "CONT", "M1", "VIA1", "M2"]
          and [st.layers[n].gds_layer for n in st.order() if n != "PAD"]
          == [20, 21, 22, 23, 24, 25], f"layers={st.to_summary()['gds_layers']}")

    # ════════════════ C 节：版图生成 ════════════════
    print("── C 交叉阵列版图生成 ──")
    arr = LY.crossbar_array(N, M)
    check("C1 4×4 元素数 = N·M·7 + N 行线 + M 列线 = 120",
          arr["n_elements"] == N * M * 7 + N + M == 120,
          f"实测 {arr['n_elements']}")
    check("C2 单元元素数 = 7（DIFF_D/DIFF_S/POLY/CONT×2/M1 焊垫/VIA1）",
          len(arr["cell_descs"]) == 7, f"实测 {len(arr['cell_descs'])}")
    check("C3 足迹 = 节距闭式（bbox ≡ array_footprint）", _footprint_ok(),
          f"footprint={arr['footprint_um']}")
    a8 = LY.crossbar_array(8, 8)
    check("C4 8×8 阵列 DRC/LVS 双 ACCEPT（规模不退化为假绿）",
          LY.run_edrc(a8["descs"])["verdict"] == "ACCEPT"
          and LY.elvs_signoff(a8["descs"], LY.expected_netlist(8, 8))["verdict"] == "ACCEPT",
          f"元素 {a8['n_elements']} · 足迹 {tuple(round(v,2) for v in a8['footprint_um'])}")

    # ════════════════ D 节：几何 DRC ════════════════
    print("── D 几何 DRC ──")
    check("D1 合法阵列 DRC ACCEPT（4 规则全过）", _legal_drc(), "")
    bad_cont = LY.crossbar_array(N, M, {"cont_um": 0.05})
    v1 = LY.run_edrc(bad_cont["descs"])
    check("D2 接触孔过小(0.05) ⇒ DRC REJECT（MIN-WIDTH/ENCLOSURE）",
          v1["verdict"] == "REJECT"
          and any(v["rule"] in ("EDR-MIN-WIDTH", "EDR-CONT-ENCLOSURE")
                  for v in v1["violations"]),
          f"violations={sorted({v['rule'] for v in v1['violations']})}")
    bad_row = LY.crossbar_array(N, M, {"row_w_um": 0.10})
    v2 = LY.run_edrc(bad_row["descs"])
    check("D3 行线过窄(0.10<0.23) ⇒ DRC REJECT（EDR-MIN-WIDTH）",
          v2["verdict"] == "REJECT"
          and any(v["rule"] == "EDR-MIN-WIDTH" for v in v2["violations"]),
          f"violations={sorted({v['rule'] for v in v2['violations']})}")
    check("D4 规则名 / n_rules 稳定（EDRC_RULES=4 条）",
          len(LY.EDRC_RULES) == 4 and LY.run_edrc(arr["descs"])["n_rules"] == 4,
          f"EDRC_RULES={len(LY.EDRC_RULES)}")

    # ════════════════ E 节：几何 LVS ════════════════
    print("── E 几何 LVS ──")
    check("E1 合法阵列 LVS ACCEPT（连通/端口/晶体管数/W-L/零悬空）", _legal_lvs(), "")
    el = [dict(d) for d in LY.crossbar_array(1, 1)["descs"]]
    el.append({"kind": "boundary", "layer": EL.L_M1, "net": "col0",
               "rings_um": [[(-0.30, -0.40), (-0.20, -0.40),
                             (-0.20, 0.40), (-0.30, 0.40)]]})   # 横跨行线与源焊垫
    vs = LY.elvs_signoff(el, LY.expected_netlist(1, 1))
    check("E2 额外 M1 几何横跨行线与源焊垫（同层相交）⇒ LVS REJECT（SHORT）",
          vs["verdict"] == "REJECT" and any("SHORT" in i for i in vs["issues"]),
          f"issues={vs['issues'][:2]}")
    bad_e = LY.expected_netlist(N, M)
    bad_e["L_um"] = 0.60
    vm = LY.elvs_signoff(arr["descs"], bad_e)
    check("E3 声明 L 与几何不符 ⇒ LVS REJECT（DEVICE-MISMATCH）",
          vm["verdict"] == "REJECT"
          and any("DEVICE-MISMATCH" in i for i in vm["issues"]),
          f"回提 L={LY.extract_wl(arr['descs'])['L_um']:.3f} vs 声明 0.600")
    el2 = [dict(d) for d in LY.crossbar_array(1, 1)["descs"]]
    for d in el2:
        if d["layer"] == EL.L_DIFF:
            d["rings_um"] = LY._ring_square(0.375, 0.0, 0.05)   # 有源区缩到接触孔内
    vd = LY.elvs_signoff(el2, LY.expected_netlist(1, 1))
    check("E4 有源区缩没 ⇒ LVS REJECT（DANGLING-BRIDGE）",
          vd["verdict"] == "REJECT"
          and any("DANGLING-BRIDGE" in i for i in vd["issues"]),
          f"issues={vd['issues'][:2]}")
    miss = LY.expected_netlist(N, M)
    miss["ports"] = set(miss["ports"]) | {"row99"}
    vn = LY.elvs_signoff(arr["descs"], miss)
    check("E5 声明端口未实现 ⇒ LVS REJECT（MISSING-NET）",
          vn["verdict"] == "REJECT" and any("MISSING-NET" in i for i in vn["issues"]),
          "row99 未在几何中出现")
    check("E6 LVS n_checks=7（标签/短路/桥/端口/悬空/管数/W-L 七判据）",
          LY.elvs_signoff(arr["descs"], LY.expected_netlist(N, M))["n_checks"] == 7,
          f"n_checks={LY.elvs_signoff(arr['descs'], LY.expected_netlist(N, M))['n_checks']}")

    # ════════════════ F 节：GDS 出口 + 层次化 ════════════════
    print("── F GDS 出口 + AREF 层次化 ──")
    g = LY.to_gds(N, M, path=os.path.join(_TMPDIR, "lda_ecore_e6_tmp.gds"))
    parsed = LY.G.parse_gds(g["gds_bytes"])
    layers = set()
    total = 0
    for stt in parsed.get("structures", {}).values():
        layers |= set(stt.get("layers", []))
        total += stt.get("elements", 0)
    check("F1 真出 GDSII（含电子层 20..25）",
          bool(g["gds_bytes"]) and {20, 21, 22, 23, 24, 25}.issubset(layers),
          f"layers={sorted(layers)} · bytes={g['n_bytes']}")
    rt = LY.gds_roundtrip_check(N, M)
    check("F2 AREF 展开元素数 ≡ flat 元素数（不展开 ⇒ DRC 假绿）",
          rt["match"] and rt["expanded_top_elements"] == g["flat_elements"],
          f"展开 {rt['expanded_top_elements']} ≡ flat {g['flat_elements']}")
    check("F3 层次化压缩生效（top 元素 << flat）",
          g["applied"] and g["n_elements_top"] < g["flat_elements"],
          f"top {g['n_elements_top']} vs flat {g['flat_elements']} · cell {g['n_cell_elements']}")

    # ════════════════ G 节：吃狗粮闭环（版图 → 器件模型）════════════════
    print("── G 吃狗粮闭环（版图回提 W/L → E1 器件模型）──")
    wl = LY.extract_wl(arr["descs"])
    ratio = wl["W_um"] / wl["L_um"]
    check("G1 版图回提 W/L = 4.00（1.20/0.30）· 逐单元一致",
          abs(ratio - 4.0) < 1e-6 and wl["uniform"]
          and wl["n_gates"] == N * M, f"W/L={ratio:.4f} · 栅区 {wl['n_gates']}")
    sat = mosfet_saturation_bias(3.3, 10e3, NmosParams(w_over_l=ratio))
    idl = float(sat.get("id_from_load", 0.0))
    idm = float(sat.get("id_from_model", 0.0))
    check("G2 回提 W/L 注入 E1 MOSFET 模型 ⇒ 偏置电流可用（版图↔电路同口径）",
          idl > 0.0 and idm > 0.0 and abs(idl - idm) / max(idl, 1e-30) < 0.05,
          f"Id(负载)={idl:.4e} A · Id(模型)={idm:.4e} A")

    # ════════════════ H 节：诚实边界 + 红线 ════════════════
    print("── H 诚实边界 + 红线 ──")
    disc = LY.LAYOUT_DISCLOSURE
    check("H1 披露齐备：role/cell/channel/rules/geom/red_line 六键",
          all(k in disc for k in ("role", "cell", "channel", "rules", "geom", "red_line")),
          f"键={sorted(disc)}")
    check("H2 限值为设计规则 · 非实测 golden（明确 D5 外部依赖）",
          "设计规则" in EL.ELEC_DISCLOSURE["rules"]
          and "非实测 golden" in EL.ELEC_DISCLOSURE["rules"]
          and "D5" in EL.ELEC_DISCLOSURE["rules"], "限值口径")
    banned = ("ngspice", "pyspice", "ahkab", "ltspice", "xyce", "cadence",
              "synopsys", "gdstk", "gdspy", "gdsfactory", "qiskit", "cirq")
    hits = []
    for fn in ("elayers.py", "layout.py"):
        src = open(os.path.join(_HERE, "lda_l2", "ecore", fn), encoding="utf-8").read()
        hits += [f"{fn}:{b}" for b in banned
                 if re.search(rf"^\s*(import|from)\s+{b}\b", src, re.M)]
    check("H3 红线：E6 零商业 EDA / 零量子 SDK 依赖（纯标准库，C 级自主）",
          not hits, f"命中={hits or '无'}")
    dv = LY.run_edrc(arr["descs"])
    check("H4 判决无 LLM：verdict 为 str 死标量、violation 为 dict（零模型调用）",
          dv["verdict"] in ("ACCEPT", "REJECT")
          and all(isinstance(v, dict) and set(v) == {"rule", "detail"}
                  for v in dv["violations"]), "rule/detail 二元组 · 纯限值比对")
    blob = (str(LY.LAYOUT_DISCLOSURE) + str(EL.ELEC_DISCLOSURE)).upper()
    check("H5 诚实边界：无 TOPS / TOPS-W / fJ-op 类器件性能自夸",
          "TOPS" not in blob and "FJ/OP" not in blob, "设计&验证工具链口径")

    # ════════════════ I 节：突变探针（先证能变红）════════════════
    print("── I 突变探针（每个都必须真能变红）──")
    check("I1 探针：抬升最小线宽限值 ⇒ 合法 DRC 必红", probe_drc_limits() is True,
          "证 run_edrc 真的读规则表")
    check("I2 探针：篡改足迹闭式 ⇒ 足迹判据必红", probe_footprint_golden() is True,
          "证判据真在比对闭式")
    check("I3 探针：篡改 W/L 回提结果 ⇒ W/L 判据必红", probe_wl_backextract() is True,
          "证回提结果真的被消费")
    check("I4 探针：退回旧 bbox（path 两向加半宽）⇒ 足迹判据必红",
          probe_bbox_regression() is True, "防 4×4 足迹 +0.4 µm 的旧 bug 回归")

    # ════════════════ J 节：还原完整性 ════════════════
    print("── J 还原完整性（探针退出后必须复绿）──")
    check("J1 还原后：DRC/LVS/足迹/W-L 四项复绿",
          _legal_drc() and _legal_lvs() and _footprint_ok() and _wl_ok(),
          "无 patch 残留漂移")
    check("J2 还原后：模块自检 10/10 + 9/9 复绿",
          EL.run_selfcheck(verbose=False) and LY.run_selfchecks(verbose=False),
          "无残留")

    print()
    print(f"电子计算芯片版图与几何签核 门禁 smoke（E6）：{PASS}/{PASS + FAIL} PASS")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
