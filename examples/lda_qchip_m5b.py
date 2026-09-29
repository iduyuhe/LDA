"""LDA-Q5b · 真实损耗预算（M5 延伸 · D-123）——「每模深度 N 的 dB 账」
   以及与时间复用浅电路的对比。

承接 LDA-Q5（M5）的落点：M5 坐实了矩形网格**深度 = 紧界 N 可达**。但「层数」只是
结构性数字；光子真正吃掉的损耗取决于它对每一模而言**实际穿过多少片 2 模门**
（= 每模光学深度）。本演示把这笔账算清楚：

  ① **口径分离（本演示第一血案）**
     · 列口径（D-120 `n_stages = N−1`）对 `reck_decompose` 抽象网格恰 = 每模深度；
     · 但平台**邻耦合三角网格**（M1/M2 实测 0 交叉）的每模深度实测 = **2N−3**
       （同一列内相邻对**共享模** ⇒ 是链、不是匹配）⇒ 真实每模损耗约为列口径的 **2 倍**。
  ② **M5 的收益在真实 dB 账上兑现**
     矩形每模深度 max = **N** ⇒ N=216：三角静态 (2N−3)·per = 1029.6 dB →
     矩形 N·per = 518.4 dB（**省 511.2 dB**）；而元件数**不变**（同为 N(N−1)/2）。
  ③ **时间复用：通用不省损，浅电路才越墙**
     · 通用（矩形调度 N）561.6 dB：**优于三角静态**（继承矩形化收益），
       仍**贵于矩形静态 43.2 dB = N·延迟** ⇒ 通用与省损不可兼得（D-121 结论 3，
       在**可达基线 N** 上重述）。
     · 浅电路 D=32 ⇒ 83.2 dB（越墙，省 435.2 dB）但可及参数 3456 ≪ 23220 ⇒ **非通用**。

🔴 红线：纯 numpy + 平台模块（零量子 SDK）；LLM 不进判决路径；闭式/构造实测作 golden。

诚实边界：损耗为**设计预算口径**（非实测 PDK · 属 D5）；本账**不含波导交叉损耗**
   （三角网格 M2 实测 0 交叉；矩形交叉数需 P&R 几何，属 P1-B）—— 附交叉敏感性：
   抹平矩形优势需 ≈1.0e4 个交叉/模，远超平面版图量级 ⇒ 不改结论。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lda_qeda import loss_budget as LB            # noqa: E402

N_SWEEP = (4, 8, 16, 32, 64, 128)                # 每模深度扫频（构造实测）
N_TARGET = 216                                    # 对标 Borealis 的模数


def run() -> dict:
    # ① 每模深度扫频（三网格构造实测）
    depth_sweep = []
    for n in N_SWEEP:
        tri = LB.triangular_optical_depth(n)
        rect = LB.rectangular_optical_depth(n)
        abst = LB.abstract_reck_optical_depth(n)
        depth_sweep.append({
            "n_modes": n,
            "tri_max": tri["per_mode_max"],
            "tri_columns": tri["n_columns"],
            "tri_min": tri["per_mode_min"],
            "rect_max": rect["per_mode_max"],
            "rect_min": rect["per_mode_min"],
            "abstract_max": abst["per_mode_max"],
            "n_mzi": tri["n_mzi"],
            "closed_form_ok": bool(tri["closed_form_ok"] and rect["closed_form_ok"]),
        })

    # ② N=216 的 dB 账
    tab = LB.loss_account_table(N_TARGET)
    rect216 = LB.static_mesh_loss_budget(N_TARGET, mesh="rect")
    tri216 = LB.static_mesh_loss_budget(N_TARGET, mesh="tri")
    col216 = LB.column_basis_loss(N_TARGET)
    tm_rect = LB.temporal_universal_loss_budget(N_TARGET, schedule="rect")
    tm_reck = LB.temporal_universal_loss_budget(N_TARGET, schedule="reck")

    # ③ 时间复用浅电路扫描（深度的函数）
    temporal_sweep = []
    for d in (1, 2, 4, 8, 16, 32, 64, 128, N_TARGET - 1, N_TARGET):
        s = LB.temporal_shallow_loss_budget(N_TARGET, d)
        temporal_sweep.append({
            "depth": d,
            "loss_db": s["loss_per_mode_db"],
            "params": s["reachable_params"],
            "universal": s["universal"],
        })

    floor = LB.universality_loss_floor(N_TARGET)
    cb = LB.crossing_breakeven(N_TARGET)
    eq = LB.equal_loss_frontier(N_TARGET)
    verdict_report = LB.loss_budget_verdict(N_TARGET)

    # 判决：几条必须同时成立的死标量
    diag_ok = (
        abs(tri216["depth_max"] - (2 * N_TARGET - 3)) == 0
        and abs(rect216["depth_max"] - N_TARGET) == 0
        and rect216["loss_per_mode_max_db"] < tri216["loss_per_mode_max_db"]
        and abs((tri216["loss_per_mode_max_db"] - rect216["loss_per_mode_max_db"])
                - (N_TARGET - 3) * LB.PER_MZI_LOSS_DB) < 1e-6
        and tm_rect["loss_per_mode_db"] > rect216["loss_per_mode_max_db"]
        and abs((tm_rect["loss_per_mode_db"] - rect216["loss_per_mode_max_db"])
                - N_TARGET * LB.DELAY_LOSS_DB) < 1e-9
        and tm_rect["loss_per_mode_db"] < tri216["loss_per_mode_max_db"]
        and LB.temporal_shallow_loss_budget(N_TARGET, 32)["universal"] is False
        and floor["floor_kind"] == "rect_static"
        and all(p["closed_form_ok"] for p in depth_sweep)
    )

    return {
        "verdict": "PASS" if diag_ok else "FAIL",
        "n_target": N_TARGET,
        "per_mzi_loss_db": LB.PER_MZI_LOSS_DB,
        "per_step_loss_db": LB.PER_STEP_LOSS_DB,
        "delay_loss_db": LB.DELAY_LOSS_DB,
        "depth_sweep": depth_sweep,
        "loss_account": tab,
        "loss_account_N216": {
            "column_basis_db": col216["loss_per_mode_db"],
            "triangular_static_db": tri216["loss_per_mode_max_db"],
            "rectangular_static_db": rect216["loss_per_mode_max_db"],
            "temporal_rect_schedule_db": tm_rect["loss_per_mode_db"],
            "temporal_reck_schedule_db": tm_reck["loss_per_mode_db"],
            "m5_saving_vs_triangular_db": (tri216["loss_per_mode_max_db"]
                                           - rect216["loss_per_mode_max_db"]),
            "temporal_penalty_vs_rect_db": (tm_rect["loss_per_mode_db"]
                                            - rect216["loss_per_mode_max_db"]),
            "rect_eta": rect216["per_mode_eta_at_max_loss"],
        },
        "temporal_sweep": temporal_sweep,
        "universality_floor": floor,
        "crossing_breakeven": cb,
        "equal_loss_frontier": eq,
        "verdict_report": verdict_report,
        "headline_findings": [
            f"口径分离：D-120 列口径 (N−1)·per = {col216['loss_per_mode_db']:.1f} dB "
            f"低估邻耦合三角网格真账 {tri216['loss_per_mode_max_db']:.1f} dB（每模深度 2N−3 ≠ 列数 N−1）",
            f"M5 收益兑现：矩形每模深度 = N ⇒ {tri216['loss_per_mode_max_db']:.1f} → "
            f"{rect216['loss_per_mode_max_db']:.1f} dB（省 "
            f"{tri216['loss_per_mode_max_db']-rect216['loss_per_mode_max_db']:.1f} dB），"
            f"元件数不变（同为 N(N−1)/2）",
            f"时间复用通用（矩形调度）{tm_rect['loss_per_mode_db']:.1f} dB：优于三角静态、"
            f"贵于矩形静态 {tm_rect['loss_per_mode_db']-rect216['loss_per_mode_max_db']:.1f} dB"
            f"（= N·延迟）⇒ 通用于省损不可兼得（可达基线 N）",
            f"浅电路 D=32 ⇒ {LB.temporal_shallow_loss_budget(N_TARGET,32)['loss_per_mode_db']:.1f} dB "
            f"（越墙）但参数 3456 ≪ 23220 ⇒ 非通用（维度计数判死）",
            f"交叉敏感性：抹平矩形优势需 ≈{cb['breakeven_crossings_per_mode']:.0f} 交叉/模 ⇒ 缺口不改结论",
        ],
    }


# ---------------------------------------------------------------------------
# SVG（四面板 · 浅色）
# ---------------------------------------------------------------------------
def _panel_depth(parts, x0, y0, w, h, sw):
    parts.append(f'<text x="{x0}" y="{y0}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">① 每模光学深度（构造实测）</text>')
    y1 = y0 + h
    parts.append(f'<line x1="{x0}" y1="{y1}" x2="{x0+w}" y2="{y1}" stroke="#cbd5e1"/>')
    parts.append(f'<line x1="{x0}" y1="{y0+16}" x2="{x0}" y2="{y1}" stroke="#cbd5e1"/>')
    nmax = sw[-1]["n_modes"]
    dmax = max(p["tri_max"] for p in sw)
    for p in sw:
        x = x0 + 14 + (w - 28) * (p["n_modes"] / nmax)
        for key, col, lab in (("tri_max", "#dc2626", "三角 2N−3"),
                              ("rect_max", "#2563eb", "矩形 N"),
                              ("abstract_max", "#94a3b8", "抽象 N−1")):
            y = y1 - (h - 30) * (p[key] / dmax)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{col}"/>')
    ytri = y1 - (h - 30) * (sw[-1]["tri_max"] / dmax)
    yrec = y1 - (h - 30) * (sw[-1]["rect_max"] / dmax)
    parts.append(f'<text x="{x0+14}" y="{ytri-6:.1f}" font-family="Arial" font-size="8.5" '
                 f'fill="#dc2626">2N−3 = {sw[-1]["tri_max"]}</text>')
    parts.append(f'<text x="{x0+14}" y="{yrec+13:.1f}" font-family="Arial" font-size="8.5" '
                 f'fill="#2563eb">N = {sw[-1]["rect_max"]}</text>')
    parts.append(f'<text x="{x0}" y="{y1+13}" font-family="Arial" font-size="8.5" '
                 f'fill="#64748b">N=4…{nmax}（实跑构造数门）· 列口径 N−1 ≠ 三角每模 2N−3</text>')


def _panel_bars(parts, x0, y0, w, h, acc):
    parts.append(f'<text x="{x0}" y="{y0}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">② N=216 每模损耗 dB 账</text>')
    rows = [
        ("列口径(N−1)", acc["column_basis_db"], "#94a3b8"),
        ("三角静态", acc["triangular_static_db"], "#dc2626"),
        ("矩形(M5)", acc["rectangular_static_db"], "#2563eb"),
        ("复用矩形调度", acc["temporal_rect_schedule_db"], "#7c3aed"),
        ("复用Reck调度", acc["temporal_reck_schedule_db"], "#a16207"),
    ]
    mx = max(r[1] for r in rows)
    y = y0 + 20
    bw = w - 96
    for name, val, col in rows:
        ln = bw * (val / mx)
        parts.append(f'<text x="{x0}" y="{y+9}" font-family="Arial" font-size="8.5" '
                     f'fill="#334155">{name}</text>')
        parts.append(f'<rect x="{x0+78}" y="{y}" width="{ln:.1f}" height="10" fill="{col}" '
                     f'rx="1.5"/>')
        parts.append(f'<text x="{x0+78+ln+4:.1f}" y="{y+9}" font-family="Arial" '
                     f'font-size="8.5" fill="#334155">{val:.0f}</text>')
        y += 16
    parts.append(f'<text x="{x0}" y="{y+10}" font-family="Arial" font-size="8.5" '
                 f'fill="#16a34a">矩形省三角 {acc["m5_saving_vs_triangular_db"]:.0f} dB · '
                 f'复用贵矩形 {acc["temporal_penalty_vs_rect_db"]:.0f} dB（= N·延迟）</text>')


def _panel_temporal(parts, x0, y0, w, h, sw):
    parts.append(f'<text x="{x0}" y="{y0}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">③ 时间复用：深度 ↔ 损耗 ↔ 通用性</text>')
    y1 = y0 + h
    parts.append(f'<line x1="{x0}" y1="{y1}" x2="{x0+w}" y2="{y1}" stroke="#cbd5e1"/>')
    parts.append(f'<line x1="{x0}" y1="{y0+16}" x2="{x0}" y2="{y1}" stroke="#cbd5e1"/>')
    dmax = max(p["depth"] for p in sw)
    lmax = max(p["loss_db"] for p in sw)
    for p in sw:
        x = x0 + 12 + (w - 24) * (p["depth"] / dmax)
        y = y1 - (h - 30) * (p["loss_db"] / lmax)
        col = "#dc2626" if p["universal"] else "#16a34a"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{col}"/>')
    yD32 = y1 - (h - 30) * (32 * 2.6 / lmax)
    parts.append(f'<text x="{x0+16}" y="{yD32-6:.1f}" font-family="Arial" font-size="8.5" '
                 f'fill="#16a34a">D=32 ⇒ 83.2 dB（浅电路，非通用）</text>')
    parts.append(f'<text x="{x0}" y="{y1+13}" font-family="Arial" font-size="8.5" '
                 f'fill="#64748b">红=通用(D≥N) · 绿=非通用(D&lt;N) · 损耗 = 深度 × 2.6 dB</text>')


def _panel_verdict(parts, x0, y0, w, h, rep):
    acc = rep["loss_account_N216"]
    cb = rep["crossing_breakeven"]
    eq = rep["equal_loss_frontier"]
    parts.append(f'<text x="{x0}" y="{y0}" font-family="Arial" font-size="12" '
                 f'font-weight="bold" fill="#0f172a">④ 判决与诚实边界</text>')
    lines = [
        f'通用性每模损耗下界 = {rep["universality_floor"]["floor_db"]:.0f} dB（矩形静态）',
        f'等损耗下时间复用浅电路参数 = {eq["temporal_reachable_params"]} '
        f'= {eq["param_fraction_vs_rect"]*100:.0f}% 矩形通用 ⇒ 仍非通用',
        f'交叉敏感性：抹平矩形优势需 ≈{cb["breakeven_crossings_per_mode"]:.0f} 交叉/模',
        f'矩形 N=216 每模透射率 η = {acc["rect_eta"]:.2e}',
        '不含交叉损耗（三角 M2 实测 0 交叉；矩形交叉数属 P1-B）',
        '损耗为设计预算口径（非实测 PDK · 属 D5）',
    ]
    y = y0 + 18
    for ln in lines:
        parts.append(f'<text x="{x0}" y="{y}" font-family="Arial" font-size="8.5" '
                     f'fill="#475569">{ln}</text>')
        y += 13


def render_svg(rep: dict) -> str:
    vcol = "#16a34a" if rep["verdict"] == "PASS" else "#dc2626"
    acc = rep["loss_account_N216"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 620" width="680" height="620">',
        '<rect width="680" height="620" fill="#ffffff"/>',
        '<text x="34" y="30" font-family="Arial" font-size="18" font-weight="bold" '
        'fill="#0f172a">LDA-Q5b · 真实损耗预算（M5 延伸 · D-123）</text>',
        '<text x="34" y="48" font-family="Arial" font-size="10.5" fill="#64748b">'
        '每模深度 = N 的 dB 账 · 三角 2N−3 / 矩形 N · 口径分离 · 时间复用通用 vs 浅电路 · '
        '纯 numpy · 闭式/构造实测作 golden</text>',
        '<line x1="34" y1="58" x2="646" y2="58" stroke="#e2e8f0"/>',
    ]
    _panel_depth(parts, 34, 92, 290, 190, rep["depth_sweep"])
    _panel_bars(parts, 356, 92, 290, 190, acc)

    parts.append('<line x1="34" y1="300" x2="646" y2="300" stroke="#e2e8f0"/>')
    _panel_temporal(parts, 34, 316, 290, 150, rep["temporal_sweep"])
    _panel_verdict(parts, 356, 316, 290, 150, rep)

    parts += [
        '<line x1="34" y1="482" x2="646" y2="482" stroke="#e2e8f0"/>',
        f'<text x="34" y="502" font-family="Arial" font-size="9.5" fill="#475569">'
        f'血案（口径）：D-120 列口径 (N−1)·per = {acc["column_basis_db"]:.1f} dB；'
        f'平台邻耦合三角网格每模深度实测 = 2N−3 ⇒ 真账 {acc["triangular_static_db"]:.1f} dB'
        f'（低估 {acc["triangular_static_db"]-acc["column_basis_db"]:.1f} dB）</text>',
        f'<text x="34" y="518" font-family="Arial" font-size="9.5" fill="#475569">'
        f'M5 收益兑现：矩形每模深度 = N ⇒ {acc["triangular_static_db"]:.0f} → '
        f'{acc["rectangular_static_db"]:.0f} dB（省 {acc["m5_saving_vs_triangular_db"]:.0f} dB），'
        f'元件数不变（N(N−1)/2）</text>',
        f'<text x="34" y="534" font-family="Arial" font-size="9.5" fill="#475569">'
        f'时间复用：通用（矩形调度）{acc["temporal_rect_schedule_db"]:.0f} dB 优于三角静态、'
        f'贵于矩形静态 {acc["temporal_penalty_vs_rect_db"]:.0f} dB（= N·延迟）⇒ '
        f'通用于省损不可兼得</text>',
        '<text x="34" y="556" font-family="Arial" font-size="8.8" fill="#94a3b8">'
        '诚实边界：损耗为设计预算口径（非实测 PDK · 属 D5）；不含波导交叉损耗'
        '（三角网格 M2 实测 0 交叉；矩形交叉数属 P1-B）</text>',
        '<text x="34" y="570" font-family="Arial" font-size="8.8" fill="#94a3b8">'
        '「每模深度」由构造实测（跑分解数门数）给出并附闭式核对；'
        '常数复用 D-120(2.4)/D-121(0.2,2.6)/D-122(矩形层)，不另建</text>',
        f'<text x="34" y="596" font-family="Arial" font-size="11" font-weight="bold" fill="{vcol}">'
        f'M5 延伸判决：{rep["verdict"]}（矩形每模省 '
        f'{acc["m5_saving_vs_triangular_db"]:.0f} dB · 通用下界 '
        f'{rep["universality_floor"]["floor_db"]:.0f} dB · 浅电路 D=32 越墙但非通用）</text>',
        '</svg>',
    ]
    return "\n".join(parts)


def main() -> int:
    rep = run()
    with open(os.path.join(_HERE, "lda_q5b_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    with open(os.path.join(_HERE, "lda_q5b_loss.svg"), "w", encoding="utf-8") as f:
        f.write(render_svg(rep))

    print("=" * 84)
    print("LDA-Q5b · 真实损耗预算（M5 延伸 · D-123）")
    print("=" * 84)
    print(f"常数：per_mzi={rep['per_mzi_loss_db']:.1f} dB · per_step={rep['per_step_loss_db']:.1f} dB"
          f" · 每步延迟={rep['delay_loss_db']:.2f} dB")
    print("① 每模光学深度（构造实测）：")
    for p in rep["depth_sweep"]:
        print(f"   N={p['n_modes']:4d}  列={p['tri_columns']:4d}  三角max={p['tri_max']:4d}  "
              f"矩形max={p['rect_max']:4d}(min={p['rect_min']:4d})  抽象max={p['abstract_max']:4d}  "
              f"元件={p['n_mzi']}")
    a = rep["loss_account_N216"]
    print("② N=216 每模损耗 dB 账：")
    print(f"   列口径(N−1)      = {a['column_basis_db']:.1f}")
    print(f"   三角静态 (2N−3)  = {a['triangular_static_db']:.1f}")
    print(f"   矩形静态 (N, M5) = {a['rectangular_static_db']:.1f}   ← 省 "
          f"{a['m5_saving_vs_triangular_db']:.1f} dB")
    print(f"   复用·矩形调度    = {a['temporal_rect_schedule_db']:.1f}   ← 贵矩形 "
          f"{a['temporal_penalty_vs_rect_db']:.1f} dB")
    print(f"   复用·Reck调度    = {a['temporal_reck_schedule_db']:.1f}")
    print("③ 时间复用浅电路（深度 ↔ 损耗 ↔ 通用性）：")
    for p in rep["temporal_sweep"]:
        print(f"   D={p['depth']:4d}  损耗={p['loss_db']:7.1f} dB  参数={p['params']:6d}  "
              f"通用={'是' if p['universal'] else '否'}")
    print("④ 下界 / 敏感性 / 等损耗前沿：")
    print(f"   通用性每模损耗下界 = {rep['universality_floor']['floor_db']:.1f} dB"
          f"（{rep['universality_floor']['floor_kind']}）")
    print(f"   交叉 breakeven = {rep['crossing_breakeven']['breakeven_crossings_per_mode']:.0f} 交叉/模")
    print(f"   等损耗前沿：深度={rep['equal_loss_frontier']['temporal_depth_at_equal_loss']} "
          f"参数={rep['equal_loss_frontier']['temporal_reachable_params']} "
          f"({rep['equal_loss_frontier']['param_fraction_vs_rect']*100:.0f}% 矩形通用)")
    print()
    for h in rep["headline_findings"]:
        print("  • " + h)
    print()
    print(f"M5 延伸判决：{rep['verdict']}")
    print("产物：lda_q5b_report.json · lda_q5b_loss.svg")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
