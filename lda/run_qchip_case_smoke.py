#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""光量子计算芯片案例卡门禁（A 档接入 · D-131）。

═══ 判什么（分六节 · 24 条）═══
A 模块自检与闭式 4 · B 跨源一致性（防文案漂移）5 · C 路由与面板接线 5 ·
D 诚实边界与红线 5 · E 护栏 2 · F 免登录/零重计算 3。

🔴 本门禁的核心价值是 **跨源一致性**：`lda_webui.qchip_case` 是 WebUI 的
**文案+闭式**数据源，极易与工程真值漂移（例如 D-123 改了 per_mzi 而面板没跟）。
故逐项把面板现算值对回 **已提交的 report JSON** 与 **平台模块常量**：
  · `examples/lda_q5_report.json`   —— 深度 / 紧界 / 省层
  · `examples/lda_q5b_report.json`  —— 损耗账（三角/矩形/时间复用/列口径）
  · `lda_qeda.loss_budget`          —— per_mzi / per_step 设计预算常量
  · `lda_qeda.rect_mesh`            —— 矩形深度 = N（紧界可达）
任一处不一致即 FAIL（面板数字必须能被工程真值回溯）。
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check          # noqa: E402

_ROOT = os.path.dirname(_HERE)
_WEBUI = os.path.join(_HERE, "lda_webui")

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _load_json(rel):
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return None
    with io.open(fp, encoding="utf-8") as f:
        return json.load(f)


def _read(rel):
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return ""
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    from lda_webui import qchip_case as QC

    # ═══════════════ A 模块自检与闭式 ═══════════════
    ok_a = QC.run_selfchecks(verbose=False)
    check("A1 模块自检 17/17 PASS", ok_a,
          "旗舰闭式/紧界可达/三口径偏序/损耗账/口径分离/时间复用/地板/η/维数/护栏/组装/"
          "不伪装/无LLM/零重依赖/三拓扑/浅前沿/B档护栏")

    d216 = QC.mesh_depth_closed_form(216)
    check("A2 N=216 闭式：23220 片 · Reck 429 · 矩形 216 · 省 213",
          d216["n_mzi"] == 23220 and d216["depth_triangular_reck"] == 429
          and d216["depth_rectangular_clements"] == 216
          and d216["depth_saving_vs_reck"] == 213,
          "n_mzi=%d reck=%d rect=%d" % (d216["n_mzi"], d216["depth_triangular_reck"],
                                        d216["depth_rectangular_clements"]))

    check("A3 矩形深度 ≡ 紧下界 ≡ N（N=3..128 逐点，紧界可达）",
          all((lambda m: m["depth_rectangular_clements"] == m["tight_adjacency_bound"]
               == m["n_modes"])(QC.mesh_depth_closed_form(k))
              for k in (3, 4, 5, 8, 16, 32, 64, 128)))

    check("A4 三口径偏序：参数界 ≤ 紧界 N ≤ Reck 2N−3",
          all((lambda m: m["parameter_count_bound"] <= m["tight_adjacency_bound"]
               <= m["depth_triangular_reck"])(QC.mesh_depth_closed_form(k))
              for k in (4, 8, 216)),
          "N=216 ⇒ %d ≤ %d ≤ %d" % (d216["parameter_count_bound"],
                                     d216["tight_adjacency_bound"],
                                     d216["depth_triangular_reck"]))

    # ── B 档（D-132）：拓扑对照 + 浅电路前沿 + 参数化 ──
    tops = QC.topology_report(216)
    tmap = {r["id"]: r for r in tops}
    check("A5 B档 三拓扑对照：rect 216 / reck 429 / temporal 1 片物理 MZI",
          len(tops) == 3
          and tmap["rect"]["per_mode_depth"] == 216
          and tmap["reck"]["per_mode_depth"] == 429
          and tmap["temporal"]["n_physical_units"] == 1
          and tmap["rect"]["tight_bound_reached"] is True
          and tmap["reck"]["tight_bound_reached"] is False,
          "rect=%s reck=%s tmx=%s" % (tmap["rect"]["per_mode_depth"],
                                      tmap["reck"]["per_mode_depth"],
                                      tmap["temporal"]["per_mode_depth"]))

    fr = {r["depth"]: r for r in QC.shallow_frontier(216)}
    check("A6 B档 浅电路前沿：D=32 非通用（3456 < 23220）· D=N 通用",
          fr[32]["reachable_params"] == 3456 and fr[32]["universal"] is False
          and fr[216]["universal"] is True,
          "D=32 ⇒ %d 参数 / %.2f%%" % (fr[32]["reachable_params"],
                                       fr[32]["param_fraction_of_unitary"] * 100))

    c_reck = QC.case_card(64, topology="reck", per_mzi_db=1.0)
    check("A7 B档 参数化生效：topology=reck ⇒ 深度 125 · per_mzi=1.0 ⇒ 损耗 125 dB",
          c_reck["selected_topology"]["per_mode_depth"] == 125
          and abs(c_reck["selected_topology"]["per_mode_loss_db"] - 125.0) < 1e-9
          and abs(c_reck["requested"]["per_mzi_db"] - 1.0) < 1e-12,
          "N=64 reck ⇒ 深度 %s / 损耗 %s" % (c_reck["selected_topology"]["per_mode_depth"],
                                             c_reck["selected_topology"]["per_mode_loss_db"]))

    # ═══════════════ B 跨源一致性（防文案漂移）═══════════════
    q5 = _load_json("examples/lda_q5_report.json")
    q5b = _load_json("examples/lda_q5b_report.json")

    if q5 is None:
        check("B1 跨源：lda_q5_report.json 可读", False, "文件缺失")
    else:
        nr = q5.get("n_target_report", {})
        check("B1 跨源 vs lda_q5_report：深度 216 / 紧界 216 / 省 213 / 可达 True",
              int(nr.get("rectangular_mesh_depth", -1)) == d216["depth_rectangular_clements"]
              and int(nr.get("tight_adjacency_bound", -1)) == d216["tight_adjacency_bound"]
              and int(nr.get("depth_reduction_vs_reck", -1)) == d216["depth_saving_vs_reck"]
              and bool(nr.get("tight_bound_reachable")) is True,
              "report: depth=%s bound=%s cut=%s" % (nr.get("rectangular_mesh_depth"),
                                                    nr.get("tight_adjacency_bound"),
                                                    nr.get("depth_reduction_vs_reck")))

    if q5b is None:
        check("B2 跨源：lda_q5b_report.json 可读", False, "文件缺失")
    else:
        la = q5b.get("loss_account_N216", {})
        L = QC.loss_account_closed_form(216)
        check("B2 跨源 vs lda_q5b_report：三角 1029.6 / 矩形 518.4 / 列口径 516.0",
              all(abs(float(la.get(k, -1)) - v) < 1e-6 for k, v in (
                  ("triangular_static_db", L["triangular_static_db"]),
                  ("rectangular_static_db", L["rectangular_static_db"]),
                  ("column_basis_db", L["column_basis_db"])))
              if la else False,
              "report tri=%s rect=%s col=%s" % (la.get("triangular_static_db"),
                                                la.get("rectangular_static_db"),
                                                la.get("column_basis_db")))

        check("B3 跨源 vs lda_q5b_report：时间复用（矩形/Reck 调度）",
              abs(float(la.get("temporal_rect_schedule_db", -1))
                  - L["temporal_rect_schedule_db"]) < 1e-6
              and abs(float(la.get("temporal_reck_schedule_db", -1))
                      - L["temporal_reck_schedule_db"]) < 1e-6,
              "report tmx_rect=%s tmx_reck=%s" % (la.get("temporal_rect_schedule_db"),
                                                  la.get("temporal_reck_schedule_db")))

    # 常量真源：平台模块（设计预算）
    try:
        from lda_qeda import loss_budget as LB
        const_ok = (abs(float(LB.PER_MZI_LOSS_DB) - QC.PER_MZI_LOSS_DB) < 1e-12
                    and abs(float(LB.PER_STEP_LOSS_DB) - QC.PER_STEP_LOSS_DB) < 1e-12)
        detail = "LB per_mzi=%s per_step=%s" % (LB.PER_MZI_LOSS_DB, LB.PER_STEP_LOSS_DB)
    except Exception as e:                                   # noqa: BLE001
        const_ok, detail = False, "import lda_qeda.loss_budget 失败：%r" % (e,)
    check("B4 ★跨源常量★ 面板 per_mzi/per_step ≡ 平台 loss_budget（设计预算真源）",
          const_ok, detail)

    # 平台矩形网格深度 = N（紧界可达的另一独立来源）
    layers = None
    try:
        from lda_qeda import rect_mesh as RM
        import numpy as np
        U = np.fft.fft(np.eye(16)).astype(complex) / 4.0
        layers, _D = RM.rectangular_mesh_layers(U)
        rm_ok = (len(layers) == 16)
    except Exception as e:                                   # noqa: BLE001
        rm_ok = False
        layers = "import 失败：%r" % (e,)
    check("B5 ★跨源★ 平台 rect_mesh 层数 = N（N=16 ⇒ 16 层，与紧界一致）",
          rm_ok, "层数=%s" % (len(layers) if isinstance(layers, list) else layers,))

    # ═══════════════ C 路由与面板接线 ═══════════════
    rt = _read("lda/lda_webui/routes.py")
    idx = _read("lda/lda_webui/static/index.html")

    check("C1 routes.py 定义 h_qchip_demo 且注册进 GET_ROUTES",
          "def h_qchip_demo(h, p, q, path):" in rt
          and '"/api/qchip_demo": h_qchip_demo,' in rt)

    check("C2 面板 sec-qchip 存在（stage=accept · stack=both · roles 齐）",
          bool(re.search(r'<div class="sec"[^>]*id="sec-qchip"[^>]*>', idx))
          and all(a in re.search(r'<div class="sec"[^>]*id="sec-qchip"[^>]*>', idx).group(0)
                  for a in ('data-stage="accept"', 'data-stack="both"', 'data-roles=')))

    check("C3 前端接线：runQChip 按钮 + apiGet('/api/qchip_demo?n=') + 三容器",
          'id="runQChip"' in idx and "$('runQChip').onclick = runQChip;" in idx
          and "apiGet('/api/qchip_demo?n='" in idx
          and all(('id="qchip%s"' % k) in idx for k in ("Summary", "Body", "Conclusion")))

    secs = re.findall(r'<div class="sec"[^>]*>', idx)
    check("C4 面板总数 = 64（新增 1 个，未破坏既有 63）", len(secs) == 64,
          "got %d" % len(secs))
    check("C5 按钮 id 前缀 run ⇒ 自动进入抽屉「能力目录」（collect() 机制）",
          'id="runQChip"' in idx)

    check("C6 B档 前端参数控件齐：N / 拓扑下拉 / 单 MZI 插损 + 请求带三参数",
          all(('id="%s"' % k) in idx for k in ("qchipN", "qchipTopo", "qchipPerMzi"))
          and "&topology='+encodeURIComponent(tp)+'&per_mzi='+pm" in idx
          and 'id="qchipTopo"' in idx and 'value="reck"' in idx,
          "控件 %s" % [k for k in ("qchipN", "qchipTopo", "qchipPerMzi") if ('id="%s"' % k) in idx])

    # ═══════════════ D 诚实边界与红线 ═══════════════
    card = QC.case_card(216, repo_root="__nonexistent__")
    check("D1 🔴 不伪装实测：verdict = DESIGN_BUDGET（非 PASS/ACCEPT）",
          card["verdict"] == "DESIGN_BUDGET" and card["verdict"] not in ("PASS", "ACCEPT"),
          card["verdict"])

    check("D2 诚实边界六条齐（非流片实测/设计预算/只比规模/非国际指标/搜索有界/下界）",
          all(k in card["honest_note"] for k in
              ("非流片后实测", "设计预算", "不比数值", "非国际公认", "N ≤ 8", "下界")))

    check("D3 面板同步标注诚实边界与红线",
          all(k in idx for k in ("设计预算口径", "非流片后实测",
                                 "LLM 不进判决路径", "只读案例", "零重计算")))

    check("D4 🔴 LLM 不进判决：qchip_case 源 AST 无 LLM/网络/数值库 import",
          QC.run_selfchecks(verbose=False))

    check("D5 缺口表如实：9 项中 8 项闭合、G_Q9 明标未闭合（不粉饰）",
          card["gaps_total"] == 9 and card["gaps_closed"] == 8
          and any(g["id"] == "G_Q9" and not g["closed"] for g in card["gaps"]))

    # ═══════════════ E 护栏 ═══════════════
    guard = [False, False]
    try:
        QC.case_card(1)
    except ValueError:
        guard[0] = True
    try:
        QC.mesh_depth_closed_form(0)
    except ValueError:
        guard[1] = True
    check("E1 护栏：N < 2 抛 ValueError（非法输入不静默出数）",
          all(guard), str(guard))

    card_n = QC.case_card(64, repo_root="__nonexistent__")
    check("E2 参数化：N=64 现算与其自身一致（深度 64 · 元件 2016）",
          card_n["spec"]["n_modes"] == 64 and card_n["spec"]["n_mzi"] == 2016
          and card_n["spec"]["depth"] == 64)

    guard_b = [False, False]
    try:
        QC.case_card(216, topology="bogus")
    except ValueError:
        guard_b[0] = True
    try:
        QC.case_card(216, per_mzi_db=0.0)
    except ValueError:
        guard_b[1] = True
    check("E3 B档护栏：非法 topology / 非法 per_mzi 抛 ValueError（不静默出数）",
          all(guard_b), str(guard_b))

    # ═══════════════ F 免登录 / 零重计算 ═══════════════
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0]
    check("F1 /api/qchip_demo 不进 HEAVY_POST_PATHS（不进登录闸门 ⇒ 访客可点）",
          "/api/qchip_demo" not in heavy)

    check("F2 GET 端点（不是 POST）—— 与 verification_ledger 同属公开只读类",
          '"/api/qchip_demo": h_qchip_demo,' in rt.split("GET_ROUTES = {")[1].split("}")[0])

    src_qc = _read("lda/lda_webui/qchip_case.py")
    check("F3 🔴 零重计算：模块不 import 求解器/P&R（无 lda_l2 / lda_layout / lda_qeda）",
          all(k not in src_qc.split("def run_selfchecks")[0]
              for k in ("import lda_l2", "import lda_layout", "import lda_qeda",
                        "import numpy")))

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
