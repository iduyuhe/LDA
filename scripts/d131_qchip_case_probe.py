#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D-131 光量子计算芯片案例卡门禁 · 突变探针（十条突变各必红 + 还原复绿）。

每条突变只破坏**一个**语义，验证门禁的对应判据确实能变红：
  M1  矩形深度谎报 N−1        ⇒ A1/A2/A3/B1 应红
  M2  η 闭式篡改（rect_eta=1） ⇒ A1(⑧) 应红
  M3  输出空间维数谎报（300）  ⇒ A1(⑨) 应红
  M4  verdict 冒充 PASS        ⇒ A1(⑫)/D1 应红
  M5  诚实边界删「非流片后实测」⇒ A1(⑫)/D2 应红
  M6  G_Q9 谎报闭合            ⇒ A1(⑪)/D5 应红
  M7  跨源漂移（矩形 dB +1）   ⇒ A1(④)/B2 应红
  M8  路由未注册（删 GET_ROUTES 行）⇒ C1/F2 应红
  M9  面板删「设计预算口径」    ⇒ D3 应红
  M10 端点误入登录闸门          ⇒ F1 应红
  M11 B档 拓扑对照谎报（reck=N）⇒ A1(⑮)/A5 应红
  M12 B档 浅前沿谎报（D=32 通用）⇒ A1(⑯)/A6 应红
  M13 B档 前端删拓扑控件        ⇒ C6 应红

运行：python scripts/d131_qchip_case_probe.py
"""
from __future__ import annotations

import io
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_qchip_case_smoke as SMOKE          # noqa: E402
from lda_webui import qchip_case as QC        # noqa: E402

_IDX = os.path.join(_LDA, "lda_webui", "static", "index.html")
_RT = os.path.join(_LDA, "lda_webui", "routes.py")

_ORIG = {
    "mesh_depth_closed_form": QC.mesh_depth_closed_form,
    "loss_account_closed_form": QC.loss_account_closed_form,
    "hilbert_log2_dim": QC.hilbert_log2_dim,
    "topology_report": QC.topology_report,
    "shallow_frontier": QC.shallow_frontier,
    "case_card": QC.case_card,
    "GAPS": QC.GAPS,
    "QCHIP_HONEST_NOTE": QC.QCHIP_HONEST_NOTE,
}


def run_smoke():
    """in-process 跑门禁 main()，返回 (退出码, FAIL 行列表)。"""
    SMOKE.PASS = 0
    SMOKE.FAIL = 0
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = SMOKE.main()
    except SystemExit as e:                       # pragma: no cover
        rc = e.code
    except Exception as e:                        # noqa: BLE001
        rc = 99
        buf.write("[CRASH] %r\n" % (e,))
    finally:
        sys.stdout = old
    fails = [l.strip() for l in buf.getvalue().splitlines() if "[FAIL]" in l]
    crashes = [l for l in buf.getvalue().splitlines() if "[CRASH]" in l]
    return (rc, fails, crashes)


def _restore():
    for k, v in _ORIG.items():
        setattr(QC, k, v)


class _TextMut:
    """临时替换文件文本（try/finally 保证还原）。"""

    def __init__(self, path, pairs):
        self.path, self.pairs = path, pairs

    def __enter__(self):
        self.orig = io.open(self.path, encoding="utf-8").read()
        t = self.orig
        for old, new in self.pairs:
            assert old in t, "锚点缺失：%r" % (old[:60],)
            t = t.replace(old, new)          # 全替换：须让该字样在文件中**彻底消失**
        io.open(self.path, "w", encoding="utf-8", newline="").write(t)
        return self

    def __exit__(self, *exc):
        io.open(self.path, "w", encoding="utf-8", newline="").write(self.orig)
        return False


def main():
    rows = []

    # 基线（须全绿）
    rc0, f0, c0 = run_smoke()
    rows.append(("基线（须全绿 exit=0）", rc0, f0, c0))

    # ---- M1 矩形深度谎报 N−1 ----
    def _m1(n_modes, *a, **k):
        d = _ORIG["mesh_depth_closed_form"](n_modes, *a, **k)
        d = dict(d)
        d["depth_rectangular_clements"] = d["n_modes"] - 1
        d["depth_saving_vs_reck"] = d["depth_triangular_reck"] - d["n_modes"] + 1
        d["tight_bound_reachable"] = False
        return d
    QC.mesh_depth_closed_form = _m1
    rows.append(("M1 矩形深度谎报 N−1", *run_smoke()))
    _restore()

    QC.mesh_depth_closed_form = _ORIG["mesh_depth_closed_form"]

    # ---- M2 η 闭式篡改 ----
    def _m2(n_modes, *a, **k):
        d = dict(_ORIG["loss_account_closed_form"](n_modes, *a, **k))
        d["rect_eta"] = 1.0
        return d
    QC.loss_account_closed_form = _m2
    rows.append(("M2 η 闭式篡改（rect_eta=1）", *run_smoke()))
    _restore()

    # ---- M3 输出空间维数谎报 ----
    QC.hilbert_log2_dim = lambda n, p=125: 300.0
    rows.append(("M3 输出空间维数谎报（300.0）", *run_smoke()))
    _restore()

    # ---- M4 verdict 冒充 PASS ----
    def _m4(*a, **k):
        c = dict(_ORIG["case_card"](*a, **k))
        c["verdict"] = "PASS"
        return c
    QC.case_card = _m4
    rows.append(("M4 verdict 冒充 PASS", *run_smoke()))
    _restore()

    # ---- M5 诚实边界删条 ----
    QC.QCHIP_HONEST_NOTE = "本案例已完成。"
    rows.append(("M5 诚实边界删「非流片后实测」", *run_smoke()))
    _restore()

    # ---- M6 G_Q9 谎报闭合 ----
    QC.GAPS = [dict(g, closed=True) for g in QC.GAPS]
    rows.append(("M6 G_Q9 谎报闭合", *run_smoke()))
    _restore()

    # ---- M7 跨源漂移（矩形 dB +1）----
    def _m7(n_modes, *a, **k):
        d = dict(_ORIG["loss_account_closed_form"](n_modes, *a, **k))
        d["rectangular_static_db"] = d["rectangular_static_db"] + 1.0
        return d
    QC.loss_account_closed_form = _m7
    rows.append(("M7 跨源漂移（矩形 dB +1）", *run_smoke()))
    _restore()

    # ---- M8 路由未注册 ----
    with _TextMut(_RT, [('    "/api/qchip_demo": h_qchip_demo,\n', "")]):
        rows.append(("M8 路由未注册（删 GET_ROUTES 行）", *run_smoke()))

    # ---- M9 面板删诚实标注 ----
    with _TextMut(_IDX, [("设计预算口径", "预算口径")]):
        rows.append(("M9 面板删「设计预算口径」", *run_smoke()))

    # ---- M10 端点误入登录闸门 ----
    with _TextMut(_RT, [("HEAVY_POST_PATHS = {\n", 'HEAVY_POST_PATHS = {\n    "/api/qchip_demo",\n')]):
        rows.append(("M10 端点误入登录闸门", *run_smoke()))

    # ---- M11 B档：拓扑对照谎报（reck 深度冒充 N）----
    def _m11(n_modes, per_mzi_db=2.4, per_step_db=2.6):
        rows_ = []
        for r in _ORIG["topology_report"](n_modes, per_mzi_db=per_mzi_db,
                                          per_step_db=per_step_db):
            r = dict(r)
            if r["id"] == "reck":
                r["per_mode_depth"] = int(n_modes)
                r["tight_bound_reached"] = True
            rows_.append(r)
        return rows_
    QC.topology_report = _m11
    rows.append(("M11 B档 拓扑对照谎报（reck=N）", *run_smoke()))
    _restore()

    # ---- M12 B档：浅电路前沿谎报（D=32 冒充通用）----
    def _m12(n_modes, per_step_db=2.6):
        out_ = []
        for r in _ORIG["shallow_frontier"](n_modes, per_step_db=per_step_db):
            r = dict(r)
            if r["depth"] == 32:
                r["universal"] = True
            out_.append(r)
        return out_
    QC.shallow_frontier = _m12
    rows.append(("M12 B档 浅电路前沿谎报（D=32 通用）", *run_smoke()))
    _restore()

    # ---- M13 B档：前端删拓扑控件 ----
    with _TextMut(_IDX, [('id="qchipTopo"', 'id="qchipTopoX"')]):
        rows.append(("M13 B档 前端删拓扑控件", *run_smoke()))

    # ---- 还原后复绿 ----
    _restore()
    rows.append(("还原后（须复绿）", *run_smoke()))

    print("=" * 78)
    print("%-34s %-6s %-8s %s" % ("突变", "exit", "FAIL数", "命中的判据"))
    print("-" * 78)
    bad = []
    for name, rc, fails, crashes in rows:
        if crashes:
            tag = "CRASH!"
        elif name.startswith("基线") or name.startswith("还原后"):
            tag = "OK" if (rc == 0 and not fails) else "NOT-GREEN!"
            if tag != "OK":
                bad.append(name)
        else:
            tag = "OK" if (rc != 0 and fails) else "NOT-RED!"
            if tag != "OK":
                bad.append(name)
        hit = ", ".join(f.split("]")[-1].strip().split(" ")[0] for f in fails[:6])
        print("%-34s %-6s %-8d %-6s %s" % (name, rc, len(fails), tag, hit))

    print("=" * 78)
    ok = not bad
    print("探针结论：%s" % ("ALL OK（13 突变各必红 + 基线/还原复绿）" if ok
                          else "存在问题 -> %s" % bad))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
