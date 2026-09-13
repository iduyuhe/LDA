"""LDA · MZI 网格矩阵乘 MVP demo（四层系统 L1+L2 对外可演示）。

CLI：
    python lda/run_mzi_mesh_matmul_demo.py --N 4 --out mzi_mesh_matmul_demo.html

产出：结构化控制台摘要 + 自包含 HTML（可离线打开，无外部依赖）。
HTML 含：目标酉（默认 DFT-N）、Reck 分解、重构保真度、级联插损预算、
MZI 单元物理映射（CMT 耦合长度 / Vπ·L 电压）、红线自检 GateReport、诚实边界披露。

纪律：纯 numpy 死标量；无 wall-clock；浮点按 9 位有效数字展示（deterministic 纪律）。
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np

from lda.lda_l2.mzi_mesh_matmul import (
    run_mzi_mesh_matmul_demo as _run_demo,
    dft_matrix,
    RED_LINE_DISCLOSURE,
)
from lda.lda_l2.four_layer_redline_gate import run_four_layer_redline_gate

# 9 位有效数字（确定性展示，吸收末位抖动）
def _fmt(x) -> str:
    if isinstance(x, complex):
        return f"{x.real:.6g}{'+' if x.imag >= 0 else '-'}{abs(x.imag):.6g}j"
    if isinstance(x, float):
        return f"{x:.9g}"
    return str(x)


def _target_matrix(name: str, N: int) -> np.ndarray:
    if name == "dft":
        return dft_matrix(N)
    if name == "identity":
        return np.eye(N, dtype=complex)
    if name == "hadamard":
        # 仅 N=2 精确；N>2 用 DFT-2 块对角近似演示
        h = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
        out = np.eye(N, dtype=complex)
        for k in range(0, N - 1, 2):
            out[k:k + 2, k:k + 2] = h
        if N % 2 == 1:
            pass
        return out
    raise ValueError(f"未知 target={name}")


def build_html(rep: dict, gate, target_name: str, N: int) -> str:
    ops = rep["ops"]
    y = rep["demo_output_amplitudes"]
    amps = [abs(v) for v in y]
    max_amp = max(amps) if amps else 1.0

    # 输出幅值条形（SVG）
    bars = []
    for idx, a in enumerate(amps):
        h = 120.0 * (a / max_amp) if max_amp > 0 else 0.0
        bars.append(
            f'<g><rect x="{30 + idx * 70}" y="{170 - h:.1f}" width="36" height="{h:.1f}" '
            f'fill="#2563eb" rx="3"/>'
            f'<text x="{48 + idx * 70}" y="{188:.1f}" font-size="11" fill="#475569" '
            f'text-anchor="middle">{a:.3f}</text>'
            f'<text x="{48 + idx * 70}" y="200" font-size="11" fill="#475569" '
            f'text-anchor="middle">port {idx}</text></g>')
    bars_svg = ("<svg viewBox='0 0 520 215' width='100%' style='max-width:560px'>"
                + "".join(bars) + "</svg>")

    # MZI 单元表
    rows = []
    for k, (i, j, th, ph) in enumerate(ops):
        rows.append(
            f"<tr><td>{k + 1}</td><td>{i},{j}</td>"
            f"<td>{_fmt(th)}</td><td>{_fmt(ph)}</td>"
            f"<td>{_fmt(math.sin(th / 2.0) ** 2)}</td></tr>")
    ops_table = ("<table><thead><tr><th>#</th><th>行(i,j)</th><th>θ(rad)</th>"
                 "<th>φ(rad)</th><th>分束比 sin²(θ/2)</th></tr></thead><tbody>"
                 + "".join(rows) + "</tbody></table>")

    # Gate 报告表
    g = gate.to_dict()
    g_rows = []
    for gid in ("G1", "G2", "G3", "G4", "G5"):
        gv = g["gates"][gid]
        g_rows.append(
            f"<tr><td>{gid}</td><td><b>{gv['status']}</b></td>"
            f"<td style='text-align:left'>{gv['verdict']}</td></tr>")
    gate_table = ("<table><thead><tr><th>闸门</th><th>状态</th><th>判词</th></tr></thead>"
                  "<tbody>" + "".join(g_rows) + "</tbody></table>")

    # 各层 VMM 成熟度表（建议 A：每层 ≥ self_certified）
    l_rows = []
    for name, ly in g["gates"]["G3"]["layers"].items():
        a = ly["anchor"]
        l_rows.append(
            f"<tr><td style='text-align:left'>{name}</td>"
            f"<td>{a.get('anchor_id', '')}</td>"
            f"<td>{ly['maturity_tier']}</td><td><b>{ly['status']}</b></td></tr>")
    layer_table = ("<table><thead><tr><th>四层系统</th><th>VMM 锚</th>"
                   "<th>成熟度 tier</th><th>准入</th></tr></thead><tbody>"
                   + "".join(l_rows) + "</tbody></table>")

    tag_cls = "ok" if gate.overall == "PASS" else "warn"

    disclosure = "".join(
        f"<li><b>{k}</b>：{v}</li>" for k, v in RED_LINE_DISCLOSURE.items())

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LDA · MZI 网格矩阵乘 MVP demo</title>
<style>
 body{{font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;
   margin:0;background:#f8fafc;color:#0f172a;line-height:1.6}}
 .wrap{{max-width:880px;margin:0 auto;padding:32px 20px}}
 h1{{font-size:24px;margin:0 0 4px}}
 .sub{{color:#64748b;font-size:14px;margin-bottom:20px}}
 .card{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin:14px 0}}
 .metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
 .m{{background:#eff6ff;border-radius:8px;padding:10px;text-align:center}}
 .m .v{{font-size:20px;font-weight:700;color:#2563eb}}
 .m .l{{font-size:11px;color:#475569}}
 table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}
 th,td{{border:1px solid #e2e8f0;padding:6px 8px;text-align:center}}
 th{{background:#f1f5f9}}
 .dis{{background:#f1f5f9;border-left:4px solid #2563eb;border-radius:6px;padding:12px 16px;font-size:13px}}
 .dis ul{{margin:6px 0 0;padding-left:18px}}
 .tag{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700}}
 .ok{{background:#dcfce7;color:#166534}} .warn{{background:#fef9c3;color:#854d0e}}
 .gate{{background:#fff7ed;border-left:4px solid #f59e0b}}
 h2{{font-size:16px;margin:0 0 8px}}
 .foot{{color:#94a3b8;font-size:12px;margin-top:18px}}
</style></head>
<body><div class="wrap">
<h1>LDA · MZI 网格矩阵乘 MVP</h1>
<div class="sub">四层系统 S9 · L1 被动前端 + L2 编译映射 · 对外可演示 · C 级自主（纯 numpy）</div>

<div class="card">
 <div class="metrics">
  <div class="m"><div class="v">{rep['N']}</div><div class="l">维度 N</div></div>
  <div class="m"><div class="v">{rep['n_mzi']}</div><div class="l">MZI 单元数</div></div>
  <div class="m"><div class="v">{rep['fidelity']:.6f}</div><div class="l">重构保真度</div></div>
  <div class="m"><div class="v">{rep['cascade_loss_db']:.2f}</div><div class="l">级联插损(dB)</div></div>
  <div class="m"><div class="v">{rep['L_3dB_um']:.3f}</div><div class="l">50/50 耦合长(µm)</div></div>
  <div class="m"><div class="v">{rep['first_phase_voltage_V']:.2f}</div><div class="l">首相移电压(V)</div></div>
  <div class="m"><div class="v">{_fmt(rep['recon_err_fro'])}</div><div class="l">重构误差(‖·‖_F)</div></div>
  <div class="m"><div class="v">{target_name.upper()}</div><div class="l">目标酉</div></div>
 </div>
</div>

<div class="card">
 <h2>光学矩阵乘演示（输入端口 {rep['demo_input_port']} 单热 → 输出幅值）</h2>
 {bars_svg}
</div>

<div class="card">
 <h2>Reck 分解 · MZI 网格（{rep['n_mzi']} 单元）</h2>
 {ops_table}
 <p style="font-size:12px;color:#64748b">每个 MZI 单元 = 50/50 定向耦合器（CMT 耦合长度由 B14 锚定）
 + 相移器（Vπ·L 物理定律）。网格精确重构目标酉（数学定理，机器精度）。</p>
</div>

<div class="card gate">
 <h2>红线闸门自检 · GateReport = <span class="tag {tag_cls}">{gate.overall}</span></h2>
 {gate_table}
 {layer_table}
 <p style="font-size:12px;color:#64748b">建议 A：四层系统每层各挂 VMM 锚且成熟度 ≥ self_certified。
 L1(B14 方法学独立) / L2(Reck 定理) 高于门槛；L3/L4 为 <b>Tier-1 自证桩</b>（非已验证，
 明确升级路径与验证责任方）——自证桩是合法的第一验证阶段（VMM, v0.9.62）。</p>
</div>

<div class="card">
 <h2>诚实边界披露（防纸糊楼 / 不虚报）</h2>
 <div class="dis"><ul>{disclosure}</ul></div>
</div>

<div class="foot">LDA 开源 Agent 原生光子/量子芯片设计软件 · 四层系统 S9 立项前红线自检 demo ·
本页为确定性生成（无 wall-clock），浮点 9 位有效数字。</div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="MZI 网格矩阵乘 MVP demo")
    ap.add_argument("--N", type=int, default=4, help="酉矩阵维度（默认 4）")
    ap.add_argument("--target", default="dft", choices=["dft", "identity", "hadamard"])
    ap.add_argument("--crossings", type=int, default=0, help="网格拓扑波导交叉数（插损预算）")
    ap.add_argument("--out", default=None, help="输出 HTML 路径（默认 mzi_mesh_matmul_demo.html）")
    args = ap.parse_args()

    U = _target_matrix(args.target, args.N)
    rep = _run_demo(U, n_crossings=args.crossings)
    gate = run_four_layer_redline_gate()

    # 控制台摘要
    print(f"[MZI demo] N={rep['N']} target={args.target} n_mzi={rep['n_mzi']}")
    print(f"  重构保真度 = {rep['fidelity']:.9f}  (fro_err={rep['recon_err_fro']:.3e})")
    print(f"  级联插损   = {rep['cascade_loss_db']:.3f} dB")
    print(f"  50/50 耦合长 = {rep['L_3dB_um']:.3f} µm  首相移电压 = {rep['first_phase_voltage_V']:.3f} V")
    print(f"[红线闸门] 整体 = {gate.overall}")
    for gid in ("G1", "G2", "G3", "G4", "G5"):
        print(f"  {gid}: {gate.gates[gid]['status']}")

    out = args.out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "mzi_mesh_matmul_demo.html")
    html = build_html(rep, gate, args.target, args.N)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print(f"[HTML] 已写 {out}")


if __name__ == "__main__":
    main()
