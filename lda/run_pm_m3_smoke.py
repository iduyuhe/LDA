# -*- coding: utf-8 -*-
"""LDA 光子存储征程 · PM-M3 阵列版图层门禁（判据 + 突变探针）。

判据（全部**重算**，不读字面量）：
  A1 模块自检：`pm_m3.run_selfchecks()` 10/10（同源调用，非转录）
  B1 层号**跨源**一致：`primitives._LAYER_*` == `gds_export.LIB_LAYER_*` == 报告声明
  B2 端口契约**三处同步**：`link_model._DEFAULT_PORTS["PCMCell"]` == `primitives.pcm_cell_pads`
     键集 == `placement.port_anchor` 可解析出的端口集（新增器件类必须一次补齐三处）
  B3 🔴 端口锚点**非退化**：每个端口 `port_abs` 结果 ≠ 器件原点（防框架级缓存毒化回归 ——
     本档曾因 `_port_abs_comp_cache` 仅以 `id()` 为键而命中陈旧索引 ⇒ 51 处 LVS 假红）
  B4 🔴 端口归属**容差纪律**（算出来的）：电极中心 y > LVS 最近邻容差（读 `run_lvs` 默认值），
     否则归属退化为「靠更近取胜」的脆弱判定
  C1 规模档全覆盖：`SCALE_TIERS`（含 1×N 与 R×C 两类）逐档 **DRC PASS + LVS ACCEPT(0 违规)
     + 独立复核 ok**（真跑 P&R→GDS→DRC/LVS→独立解码）
  C2 🔴 独立解码 == 生成端声明：每档 `got_pcm == expected_pcm`（解码器与编码器零共享代码）
  C3 独立解码结构完整性：`n_elements` == `gds_stats.n_elements` ∧ 单结构 ∧ 无 SREF/AREF
  C4 预算恒等式（重算）：阵列总损 ≡ N × 单元损 ∧ 态数 ≡ N × 电平数 ∧ pad 数 ≡ 4N
  C5 pitch 与上游**同源**（重算）：l_cell ≡ M1 demo 设计点 ∧ gap_thermal ≡ k_iso × L_max(M2)
     ∧ binding 由实算 max 决定
  C6 披露守卫：`disclosure` 全真 + 真实输出**肯定式面**禁词零命中 + `pm_case` 层/端口与报告同源
  C7 缺口台账：`pm_case.GAPS` 含「光学域 drift 无锚」与「T1/T2 锁死」两条，如实开放

突变探针（每条**先证能变红**，还原后复绿）：
  P1 `k_iso` 极小 ⇒ 热间距 < 工艺间隙 ⇒ `binding` 翻转为 "process" ⇒ C5 必红
     （证明 pitch/binding 是**算出来的**，不是常数）
  P2 截断 GDS 末 4 字节 ⇒ 独立解码器**必 raise**（完整性护栏，不静默截断）
  P3 单点改层号 `gds_export.LIB_LAYER_PCM` ⇒ C2 的 PCM 恰等判据必红（跨源失配可见）
  P4 用「4 单元」的期望去比对「8 单元」的解码结果 ⇒ C2 必红（期望不是恒真）
  P5 把 `heat_gap` 压到容差内 ⇒ B4 必红（容差纪律判据**可被证伪**，非恒真）
"""
from __future__ import annotations

import inspect
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')

from lda_l2 import pm_m3 as M3          # noqa: E402
from lda_l2 import pm_m1 as M1          # noqa: E402
from lda_l2 import pm_m2 as M2          # noqa: E402
from lda_l2 import primitives as PR     # noqa: E402
from lda_l2 import gds_export as GX     # noqa: E402
from lda_l2 import lvs as LVS           # noqa: E402

_BANNED_POSITIVE = ("TOPS", "TOPS-W", "TOPS/W", "fJ/op", "fJ·op", "pJ/bit")
_NEG_TOKENS = ("不报", "不得报", "禁止", "禁用", "never", "not reported",
               "no efficiency", "不承诺", "不声称", "无")


def _positive_surface(text: str) -> str:
    """只取**肯定式面**：剔除含否定标记的从句（否定式免责句不该让判据恒红）。"""
    parts = []
    for clause in text.replace("；", "。").replace(";", "。").split("。"):
        if any(tok in clause for tok in _NEG_TOKENS):
            continue
        parts.append(clause)
    return "。".join(parts)


def main() -> int:
    print("=" * 74)
    print("LDA 光子存储征程 · PM-M3 阵列版图门禁（真 GDS + DRC/LVS + 独立解码复核）")
    print("=" * 74)

    # ── A1 模块自检（同源调用）────────────────────────────────────────────
    check("A1 `pm_m3.run_selfchecks()` 10/10（同源调用，非转录）",
          M3.run_selfchecks() is True)

    rep = M3.m3_report("GST")

    # ── B1 层号跨源一致 ───────────────────────────────────────────────────
    check("B1 层号跨源一致：primitives ↔ gds_export ↔ 报告声明（SI/PCM/HEATER=1/5/6）",
          int(PR._LAYER_SI) == int(GX.LIB_LAYER_SI)
          and int(PR._LAYER_PCM) == int(GX.LIB_LAYER_PCM)
          and int(PR._LAYER_HEATER) == int(GX.LIB_LAYER_HEATER)
          and (int(GX.LIB_LAYER_SI), int(GX.LIB_LAYER_PCM), int(GX.LIB_LAYER_HEATER))
          == (1, 5, 6),
          "报告声明 = %s" % (rep["device"]["layers"],))

    # ── B2 端口契约三处同步 ───────────────────────────────────────────────
    from lda_chain import link_model as LM
    pads = PR.pcm_cell_pads(PR.PCM_CELL_DEFAULTS)
    lm_ports = LM._DEFAULT_PORTS["PCMCell"]
    check("B2a 端口契约三处同步：link_model ↔ {光 in/out + 电极 pad h1..h4} ↔ 报告声明",
          set(lm_ports) == ({"in", "out"} | set(pads.keys()))
          == set(rep["device"]["ports"]) and len(lm_ports) == 6,
          "link_model=%s pads=%s report=%s"
          % (sorted(lm_ports), sorted(pads.keys()), rep["device"]["ports"]))

    from lda_layout import placement as PL
    anchors = {p: PL.port_anchor("PCMCell", p, PR.PCM_CELL_DEFAULTS) for p in lm_ports}
    check("B2b placement.port_anchor 对 PCMCell 六个端口**全部**可解析（无 KeyError/None）",
          all(v is not None for v in anchors.values())
          and len(anchors) == len(lm_ports) == 6,
          "锚点 = %s" % (anchors,))

    # ── B3 端口锚点非退化（框架级缓存毒化回归守护）───────────────────────
    arr = M3.build_array(8, n_buses=1)
    link, place = arr["link"], arr["placement"]
    dev_ids = [c.id for c in link.ir.components if c.kind == "PCMCell"]
    port_names = list(rep["device"]["ports"])
    degenerate = 0
    for did in dev_ids:
        pts = {tuple(round(v, 6) for v in PL.port_abs(did, p, place, link))
               for p in port_names}
        # 正常时 6 端口落在 6 个不同坐标（in/out/h1..h4 · x 或 y 至少一维不同）；
        # 缓存被 id 复用毒化时全部塌回器件原点 ⇒ 只有 1 个不同点。
        if len(pts) < 6:
            degenerate += 1
    check("B3 🔴 多总线阵列下器件端口锚点**非退化**（6 端口 6 个不同坐标 · 防缓存 id 复用毒化）",
          degenerate == 0 and len(dev_ids) == 8,
          "退化器件 %d / 共 %d" % (degenerate, len(dev_ids)))

    # ── B4 端口归属容差纪律（算出来的）───────────────────────────────────
    tol = float(inspect.signature(LVS.run_lvs).parameters["tol"].default)
    geo = PR.pcm_cell_geometry(PR.PCM_CELL_DEFAULTS)
    check("B4 🔴 电极中心 y (%.4f µm) > LVS 最近邻容差 (%.4f µm) ⇒ 归属无歧义（容差纪律）"
          % (geo["y_heater_um"], tol),
          geo["y_heater_um"] > tol)

    # ── C1 规模档全覆盖（真跑）──────────────────────────────────────────
    tiers = M3.scale_table("GST")
    n_bus_x = sum(1 for t in tiers if t["n_buses"] == 1)
    n_multi = sum(1 for t in tiers if t["n_buses"] > 1)
    check("C1a 规模档覆盖两类拓扑：1×N 串行总线 %d 档 ∧ R×C 多总线 %d 档（≥1）" % (n_bus_x, n_multi),
          n_bus_x >= 3 and n_multi >= 1 and len(tiers) >= 5)
    bad_tier = [t["bus_x_cells"] for t in tiers
                if not (t["drc_pass"] and t["lvs"] == "ACCEPT"
                        and t["lvs_violations"] == 0 and t["independent_ok"])]
    check("C1b 每档 **DRC PASS ∧ LVS ACCEPT(0) ∧ 独立复核 ok**（真跑 P&R→GDS→DRC/LVS）",
          not bad_tier, "未签核档：%s" % bad_tier)

    # ── C2 独立解码 == 生成端声明（逐档）─────────────────────────────────
    bad_dec = ["%s got=%s exp=%s" % (t["bus_x_cells"], t["got_pcm"], t["expected_pcm"])
               for t in tiers if t["got_pcm"] != t["expected_pcm"]]
    check("C2 🔴 独立解码层计数 == 生成端声明（逐档 PCM 恰等 · 解码器与编码器零共享代码）",
          not bad_dec, "失配：%s" % bad_dec)

    # ── C3 独立解码结构完整性 ───────────────────────────────────────────
    so8 = M3.layout_signoff(M3.build_array(8, n_buses=1))
    scan = so8["independent_scan"]
    check("C3 独立解码结构完整：元素数 == gds_stats 声明 ∧ 单结构 ∧ 无 SREF/AREF",
          scan["n_elements"] == so8["gds_stats"]["n_elements"]
          and scan["n_structures"] == 1
          and scan["n_sref"] == 0 and scan["n_aref"] == 0,
          "解码 %d / 声明 %d" % (scan["n_elements"], so8["gds_stats"]["n_elements"]))

    # ── C4 预算恒等式（重算）────────────────────────────────────────────
    bud = rep["budget"]
    n_c, n_lev = bud["n_cells_total"], bud["n_levels"]
    check("C4 预算恒等式：阵列总损 ≡ N×单元损 ∧ 态数 ≡ N×电平数 ∧ pad ≡ 4N",
          all(abs(bud["array_il_db"][st][i] - n_c * bud["single_cell_il_db"][st][i]) < 1e-12
              for st in ("amorphous", "crystalline") for i in (0, 1))
          and bud["array_states"] == n_c * n_lev
          and bud["n_electrode_pads"] == 4 * n_c,
          "N=%d 态=%d pads=%d" % (n_c, bud["array_states"], bud["n_electrode_pads"]))

    # ── C5 pitch 与上游同源（重算）──────────────────────────────────────
    pit = rep["pitch"]
    m1d = M1.m1_report()["demo_design_point"]
    m2q = M2.max_quench_thickness("GST")
    k_iso = float(rep["upstream"]["thermal"]["k_iso"])
    want_gap = k_iso * float(m2q["l_max_diff_max_m"]) * 1e6
    want_bind = "thermal" if pit["gap_thermal_um"] >= pit["gap_process_um"] else "process"
    check("C5 pitch 与上游同源（重算）：l_cell ≡ M1 设计点 ∧ gap_thermal ≡ k_iso×L_max(M2)"
          " ∧ binding 由实算 max 决定",
          abs(pit["l_cell_um"] - float(m1d["l_mid_um"])) < 1e-12
          and abs(pit["gap_thermal_um"] - want_gap) < 1e-12
          and pit["binding"] == want_bind,
          "gap=%.4f want=%.4f bind=%s" % (pit["gap_thermal_um"], want_gap, pit["binding"]))

    # ── C6 披露守卫 ─────────────────────────────────────────────────────
    disc = rep["disclosure"]
    import json as _json
    surf = _positive_surface(_json.dumps(disc, ensure_ascii=False))
    hits = [t for t in _BANNED_POSITIVE if t in surf]
    check("C6a 披露守卫全真 ∧ 肯定式面禁词零命中（否定式免责句不参与）",
          all(bool(v) for v in disc.values() if isinstance(v, bool)) and not hits,
          "禁词命中=%s" % hits)
    from lda_webui import pm_case as PC
    check("C6b 案例卡层/端口与阵列报告**同源**（跨模块一致，非各写一份）",
          PC.PCM_LAYERS == {k: int(v) for k, v in rep["device"]["layers"].items()}
          and PC.PCM_PORTS == rep["device"]["ports"])

    # ── C7 缺口台账如实开放 ─────────────────────────────────────────────
    gt = [g["id"] for g in PC.GAPS]
    check("C7 缺口台账如实开放：含「光学域 drift 无锚」与「T1/T2 锁死」",
          any("光学域 drift" in g["title"] for g in PC.GAPS)
          and any("T1" in g["detail"] for g in PC.GAPS)
          and len(gt) >= 4, "缺口=%s" % gt)

    # ═══════════════ 突变探针（先证能变红）═══════════════
    # P1 k_iso 极小 ⇒ 热间距 < 工艺间隙 ⇒ binding 翻转
    small = M3.cell_pitch_um("GST", k_iso=0.5)
    check("P1 探针：k_iso=0.5 ⇒ 热间距 < 工艺间隙 ⇒ binding 翻转为 'process'"
          "（证明 pitch/binding 是算出来的，非恒真）",
          small["binding"] == "process" and small["pitch_um"] < pit["pitch_um"],
          "binding=%s pitch=%.4f" % (small["binding"], small["pitch_um"]))

    # P2 截断 GDS ⇒ 独立解码器必 raise
    gds = so8["gds_bytes"]
    raised = False
    try:
        M3.independent_gds_scan(gds[:-4])
    except M3.PMM3Error:
        raised = True
    check("P2 探针：截断 GDS 末 4 字节 ⇒ 独立解码器必 raise（不静默截断）", raised)

    # P3 单点改层号（跨源失配可见）
    _old = int(GX.LIB_LAYER_PCM)
    try:
        GX.LIB_LAYER_PCM = _old + 100
        so_bad = M3.layout_signoff(M3.build_array(8, n_buses=1))
        p3 = so_bad["checks"]["pcm_layer_exact"] is False
    finally:
        GX.LIB_LAYER_PCM = _old
    check("P3 探针：单点改 gds_export.LIB_LAYER_PCM ⇒ 'PCM 层恰等' 判据必红（还原后复绿）",
          p3 and M3.layout_signoff(M3.build_array(8, n_buses=1))["checks"]["pcm_layer_exact"] is True)

    # P4 期望与解码错配 ⇒ 必红
    exp4 = M3.expected_layer_counts(M3.build_array(4, n_buses=1))
    got8 = so8["independent_scan"]["layers"].get(int(GX.LIB_LAYER_PCM), 0)
    check("P4 探针：用 4 单元期望比对 8 单元解码 ⇒ 必不相等（期望非恒真）",
          exp4["PCM"] != got8, "exp4=%d got8=%d" % (exp4["PCM"], got8))

    # P5 容差纪律可证伪
    geo_bad = PR.pcm_cell_geometry({"heat_gap": 0.05})
    check("P5 探针：把 heat_gap 压到 0.05 ⇒ 电极中心 y ≤ 容差 ⇒ B4 判据必红（可证伪）",
          geo_bad["y_heater_um"] <= tol,
          "y=%.4f tol=%.4f" % (geo_bad["y_heater_um"], tol))

    # ── C8 🔴 入库快照 == 仓库当前状态（铁律：受跟踪生成物必须配一致性判据）────
    snap = PC.STATIC_SNAPSHOT
    rep_fp = os.path.join(_ROOT, "examples", "photo_memory", "lda_pm_m3_report.json")
    schema_bad = ["(报告缺失: %s)" % rep_fp] if not os.path.exists(rep_fp) else []
    if not schema_bad:
        import json as _json2

        def _dig(o, keys):
            for k in keys:
                o = o[k]
            return o
        with open(rep_fp, encoding="utf-8") as fh:
            repj = _json2.load(fh)
        pairs = (
            (("array_8x1", "stats"), "主阵列版图统计"),
            (("array_8x1", "independent_scan"), "主阵列独立解码"),
            (("array_8x1", "expected"), "期望层计数"),
            (("array_4x8", "stats"), "宽阵列版图统计"),
            (("array_4x8", "independent_scan"), "宽阵列独立解码"),
            (("pitch",), "pitch"),
            (("pitch", "thermal"), "热学（pitch 内副本）"),
            (("budget",), "预算"),
            (("upstream", "cell_length"), "M1 单元长"),
            (("upstream", "levels"), "M1 电平"),
            (("upstream", "thermal"), "M2 热学"),
            (("signoff_checks",), "签核断言"),
            (("scale_tiers", 0), "规模档首元素"),
        )
        for keys, label in pairs:
            ka, kb = set(_dig(snap, keys).keys()), set(_dig(repj, keys).keys())
            if ka != kb:
                schema_bad.append("%s(%s): 快照缺%s 报告多%s"
                                  % (label, ".".join(map(str, keys)),
                                     sorted(ka - kb), sorted(kb - ka)))
    check("C8 🔴 内置快照 schema **逐块 == 仓库报告 JSON**（防「每加一批锚就多一份静默失真」）",
          not schema_bad, "失配：%s" % schema_bad[:3])

    # ── S1 自入 CI core ─────────────────────────────────────────────────
    cut = os.path.join(_HERE, "run_ci_regression.py")
    ck = open(cut, encoding="utf-8").read() if os.path.exists(cut) else ""
    check("S1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28）",
          "run_pm_m3_smoke.py" in ck)

    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (globals().get("PASS", 0), globals().get("FAIL", 0)))
    return 0 if globals().get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
