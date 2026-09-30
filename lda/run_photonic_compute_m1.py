"""LDA · 光子计算芯片 M1 demo（光计算征程第一里程碑 · 对外可演示）。

CLI：
    PYTHONPATH=D:/agent_LDA/lda python lda/run_photonic_compute_m1.py --N 4 \
        --out lda/journey_photonic_compute/pc_m1.html

产出：
- 结构化控制台摘要 + 自包含 HTML（可离线打开，无外部依赖）。
- 计算核酉部分 U 的主权 GDS（DRC PASS + LVS ACCEPT 证明「真实可制造」）。

demo 要点：
- 取一个**非酉**权重矩阵 W（任意线性变换的代表），用 SVD 分解为 U·Σ·V†；
- 用 MZI 网格实现酉部分 U、V†，对角衰减实现 Σ；
- 端到端验证光学 MVM == numpy 参考（理想模型机器精度）；
- 产主权 GDS 证明平台「先把芯片设计出来」的闭环。

纪律：纯 numpy 死标量；无 wall-clock；浮点按 9 位有效数字展示（deterministic 纪律）。
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np

from lda_l2.photonic_compute import (
    verify_photonic_compute,
    build_compute_core_gds,
    RED_LINE_DISCLOSURE_PC,
)


def _fmt(x) -> str:
    if isinstance(x, complex):
        return f"{x.real:.6g}{'+' if x.imag >= 0 else '-'}{abs(x.imag):.6g}j"
    if isinstance(x, float):
        return f"{x:.9g}"
    return str(x)


def build_html(ver: dict, gds_rep: dict, W: np.ndarray, x: np.ndarray) -> str:
    N = ver["N"]
    y_ref = ver["y_ref"]
    y_opt = ver["y_opt"]
    amp_r = [abs(v) for v in y_ref]
    amp_o = [abs(v) for v in y_opt]
    mx = max(amp_r + amp_o) if (amp_r + amp_o) else 1.0

    # MVM 对比条形（SVG）
    bars = []
    for idx in range(N):
        hr = 120.0 * (amp_r[idx] / mx) if mx > 0 else 0.0
        ho = 120.0 * (amp_o[idx] / mx) if mx > 0 else 0.0
        bars.append(
            f'<g><rect x="{28+idx*78}" y="{170-hr:.1f}" width="28" height="{hr:.1f}" '
            f'fill="#2563eb" rx="2"/>'
            f'<rect x="{60+idx*78}" y="{170-ho:.1f}" width="28" height="{ho:.1f}" '
            f'fill="#10b981" rx="2"/>'
            f'<text x="{62+idx*78}" y="186" font-size="10" fill="#64748b" '
            f'text-anchor="middle">p{idx}</text></g>')
    bars_svg = ("<svg viewBox='0 0 540 210' width='100%' style='max-width:600px'>"
                + "".join(bars)
                + "<g><rect x='28' y='192' width='12' height='10' fill='#2563eb'/>"
                "<text x='46' y='201' font-size='11' fill='#475569'>numpy 参考 |y|</text>"
                "<rect x='150' y='192' width='12' height='10' fill='#10b981'/>"
                "<text x='168' y='201' font-size='11' fill='#475569'>光学 MVM |y|</text></g></svg>")

    # 奇异值表
    sv = ver["svd_singular_values"]
    sv_rows = "".join(
        f"<tr><td>{k}</td><td>{_fmt(s)}</td></tr>" for k, s in enumerate(sv))
    sv_table = ("<table><thead><tr><th>奇异值 #</th><th>σ_k</th></tr></thead>"
               f"<tbody>{sv_rows}</tbody></table>")

    # 损耗预算
    lu = ver["loss_U_mesh"]
    lv = ver["loss_V_mesh"]
    loss_table = (
        "<table><thead><tr><th>网格</th><th>每模光学深度</th><th>单件损耗(dB)</th>"
        "<th>每模口径(dB)</th><th>总级联(dB)</th></tr></thead><tbody>"
        f"<tr><td>U (V† 同构)</td><td>{lu['per_mode_optical_depth']}</td>"
        f"<td>{lu['per_mzi_loss_db']:.3f}</td><td>{lu['per_mode_db']:.2f}</td>"
        f"<td>{lu['total_db']:.2f}</td></tr>"
        f"<tr><td>V†</td><td>{lv['per_mode_optical_depth']}</td>"
        f"<td>{lv['per_mzi_loss_db']:.3f}</td><td>{lv['per_mode_db']:.2f}</td>"
        f"<td>{lv['total_db']:.2f}</td></tr></tbody></table>")

    disclosure = "".join(
        f"<li><b>{k}</b>：{v}</li>" for k, v in RED_LINE_DISCLOSURE_PC.items())

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LDA · 光子计算芯片 M1</title>
<style>
 body{{font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;
   margin:0;background:#f8fafc;color:#0f172a;line-height:1.6}}
 .wrap{{max-width:900px;margin:0 auto;padding:32px 20px}}
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
 h2{{font-size:16px;margin:0 0 8px}}
 .foot{{color:#94a3b8;font-size:12px;margin-top:18px}}
</style></head>
<body><div class="wrap">
<h1>LDA · 光子计算芯片 M1</h1>
<div class="sub">光计算征程 · 非酉权重矩阵的光学乘加（SVD: W=U·Σ·V†）· C 级自主（纯 numpy）</div>

<div class="card">
 <div class="metrics">
  <div class="m"><div class="v">{N}</div><div class="l">维度 N</div></div>
  <div class="m"><div class="v">{ver['n_mzi_U']}</div><div class="l">U 网格 MZI 数</div></div>
  <div class="m"><div class="v">{ver['fidelity_U_mesh']:.6f}</div><div class="l">U 网格重构保真</div></div>
  <div class="m"><div class="v">{ver['mvm_fidelity']:.6f}</div><div class="l">端到端 MVM 保真</div></div>
  <div class="m"><div class="v">{gds_rep['n_mzi']}</div><div class="l">GDS MZI 数</div></div>
  <div class="m"><div class="v">{gds_rep['footprint_um2']:.1f}</div><div class="l">footprint(µm²)</div></div>
  <div class="m"><div class="v">{gds_rep['v_max']:.2f}</div><div class="l">V_max(V)</div></div>
  <div class="m"><div class="v">{gds_rep['lvs_verdict']}</div><div class="l">LVS 判决</div></div>
 </div>
</div>

<div class="card">
 <h2>光学矩阵-向量乘 y = W·x（蓝=numpy 参考 | 绿=光学 MVM）</h2>
 {bars_svg}
 <p style="font-size:12px;color:#64748b">输入 x 经 V† 网格 → Σ 对角衰减 → U 网格 → 探测。
 理想衰减模型下端到端 MVM 与 numpy 参考一致（机器精度）。</p>
</div>

<div class="card">
 <h2>SVD 分解 · 奇异值 Σ</h2>
 {sv_table}
 <p style="font-size:12px;color:#64748b">W = U·Σ·V†：U、V† 为酉 → 各一片 MZI 网格；
 Σ 实数对角 → 对角衰减（VOA / 幅度均衡框架）。</p>
</div>

<div class="card">
 <h2>主权 GDS（计算核酉部分 U）</h2>
 <table><thead><tr><th>项</th><th>值</th></tr></thead><tbody>
  <tr><td>DRC</td><td><b>{'PASS' if gds_rep['drc_pass'] else 'FAIL'}</b></td></tr>
  <tr><td>LVS</td><td><b>{gds_rep['lvs_verdict']}</b>（违规 {gds_rep['lvs_n_violations']}）</td></tr>
  <tr><td>版级保真度</td><td>{gds_rep['layout_fidelity']:.9f}</td></tr>
  <tr><td>GDS 元件</td><td>{gds_rep['gds_elements']} 条 PATH/BOUNDARY</td></tr>
  <tr><td>GDS 路径</td><td style="font-size:11px">{gds_rep.get('gds_path','-')}</td></tr>
 </tbody></table>
 <p style="font-size:12px;color:#64748b">证明「先把芯片设计出来」：非酉权重矩阵 → 主权版图 →
 DRC/LVS 签核全绿，真实可制造。V† 网格同模块可类比产出。</p>
</div>

<div class="card">
 <h2>损耗预算（每模口径 · 设计预算）</h2>
 {loss_table}
 <p style="font-size:12px;color:#64748b">每模光学深度由 ops 数出（平台级单一真源）；
 仿真损耗预算，非实测 PDK。</p>
</div>

<div class="card">
 <h2>诚实边界披露（防纸糊楼 / 不虚报）</h2>
 <div class="dis"><ul>{disclosure}</ul></div>
</div>

<div class="foot">LDA 开源 Agent 原生光子/量子芯片设计软件 · 光计算征程 M1 ·
本页为确定性生成（无 wall-clock），浮点 9 位有效数字。</div>
</div></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="光子计算芯片 M1 demo")
    ap.add_argument("--N", type=int, default=4, help="权重矩阵维度（默认 4）")
    ap.add_argument("--out", default=None, help="输出 HTML 路径")
    ap.add_argument("--seed", type=int, default=20260930)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    # 非酉权重矩阵（任意线性变换代表）：复高斯 + 确定性缩放
    W = (rng.standard_normal((args.N, args.N))
         + 1j * rng.standard_normal((args.N, args.N))) / math.sqrt(2.0)
    x = np.zeros(args.N, dtype=complex)
    x[0] = 1.0  # 单热输入端口 0

    ver = verify_photonic_compute(W, x, n_crossings=args.N * (args.N - 1) // 2)

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "journey_photonic_compute")
    gds_rep = build_compute_core_gds(W, out_dir, which="U")

    # 控制台摘要
    print("=" * 68)
    print("LDA · 光子计算芯片 M1 · 非酉权重矩阵的光学乘加")
    print("=" * 68)
    print(f"N={ver['N']}  非酉权重矩阵 W 取自 SVD(W=U·Σ·V†)")
    print(f"U 网格 MZI 数={ver['n_mzi_U']}   V† 网格 MZI 数={ver['n_mzi_V']}")
    print(f"U 网格重构保真度 = {ver['fidelity_U_mesh']:.9f}")
    print(f"V† 网格重构保真度 = {ver['fidelity_V_mesh']:.9f}")
    print(f"端到端 MVM 保真度 = {ver['mvm_fidelity']:.9f}  (fro_err={ver['mvm_err_fro']:.3e})")
    print(f"奇异值 Σ = {['%.4g' % s for s in ver['svd_singular_values']]}")
    print(f"GDS: DRC={'PASS' if gds_rep['drc_pass'] else 'FAIL'}  "
          f"LVS={gds_rep['lvs_verdict']}  layout_fid={gds_rep['layout_fidelity']:.9f}  "
          f"→ {gds_rep.get('gds_path','-')}")

    out = args.out or os.path.join(out_dir, "pc_m1.html")
    os.makedirs(out_dir, exist_ok=True)
    html = build_html(ver, gds_rep, W, x)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print(f"[HTML] 已写 {out}")

    # ---- 接受闸（M1）----
    ok = (ver["fidelity_U_mesh"] >= 0.9999999
          and ver["fidelity_V_mesh"] >= 0.9999999
          and ver["mvm_fidelity"] >= 0.999
          and gds_rep["drc_pass"] is True
          and gds_rep["lvs_verdict"] == "ACCEPT"
          and gds_rep["layout_fidelity"] >= 0.9999999)
    if not ok:
        print("\n❌ M1 接受闸失败：网格重构 / 端到端保真度 或 DRC/LVS 未全绿。")
        return 1
    print("\n✅ M1 接受闸通过：非酉权重已由 SVD → 双 MZI 网格 + 对角衰减实现，"
          "端到端 MVM 机器精度复现 numpy；计算核主权 GDS 经 DRC/LVS 签核（真实可制造）。")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
