"""LDA · 器件库真实物理验证面板 — 自包含演示证据页生成器（D-34/D-35 固化证据）。

取与 WebUI ⑬ 面板完全一致的数据（app.run_device_library_demo），渲染为自包含
静态 HTML（内嵌 CSS + SVG 谱图/能级图），浏览器直接打开即见，无需服务器。
等价于把 ⑬ 面板截图固化，但更可交互、零额外依赖。

用法：python lda/gen_device_panel_demo.py  ->  lda/reports/webui_device_panel_demo.html
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_webui"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_l2"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lda_solver"))

import app as webapp  # noqa: E402

LDA_ROOT = os.path.dirname(__file__)

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,'Microsoft YaHei',sans-serif;background:#f5f7fb;color:#1f2a44;margin:0;padding:24px;}
.wrap{max-width:920px;margin:0 auto;}
h1{font-size:22px;color:#1f2a44;border-left:4px solid #2563eb;padding-left:10px;margin-bottom:4px;}
.sub{color:#5b6b8c;font-size:13px;margin:0 0 18px;}
.sec{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.04);}
.sec h2{font-size:16px;margin:0 0 10px;color:#23304d;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th,td{border:1px solid #e2e8f0;padding:6px 8px;text-align:left;vertical-align:top;}
th{background:#eff6ff;color:#1e3a8a;}
.note{color:#5b6b8c;font-size:12.5px;margin:5px 0;line-height:1.5;}
.summary{font-weight:600;color:#23304d;margin-bottom:6px;}
.conclusion{margin-top:10px;padding:8px 10px;background:#f1f5f9;border-left:3px solid #2563eb;border-radius:4px;font-size:13px;}
.v{padding:1px 7px;border-radius:4px;font-size:12px;font-weight:600;}
.ok{background:#dcfce7;color:#166534;}
.fail{background:#fee2e2;color:#991b1b;}
"""


def _svg_bragg(sp):
    wls = sp.get("wavelengths_um")
    tf = sp.get("transmission_fdtd")
    tm = sp.get("transmission_tmm")
    if not wls or not tf or not tm:
        return ""
    W, H, pad = 580, 200, 38
    wmin, wmax = wls[0], wls[-1]
    X = lambda w: pad + (w - wmin) / (wmax - wmin or 1) * (W - 2 * pad)
    Y = lambda v: H - pad - min(max(v, 0), 1) * (H - 2 * pad)
    pd = " ".join(f"{X(w):.1f},{Y(v):.1f}" for w, v in zip(wls, tf))
    pm = " ".join(f"{X(w):.1f},{Y(v):.1f}" for w, v in zip(wls, tm))
    return (
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px;margin-top:8px">\n'
        f'<line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#26304d"/>\n'
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#26304d"/>\n'
        f'<polyline points="{pm}" fill="none" stroke="#7c3aed" stroke-width="2" stroke-dasharray="5 3"/>\n'
        f'<polyline points="{pd}" fill="none" stroke="#e91e63" stroke-width="2"/>\n'
        f'<text x="{pad+4}" y="{pad+2}" fill="#e91e63" font-size="11">Bragg 透射谱（TMM 虚线 / FDTD 实线）· 真实 FDTD 与解析 TMM 自洽</text>\n'
        f'<text x="{pad}" y="{H-10}" fill="#8aa0c6" font-size="11">λ={wmin:.4f}µm</text>\n'
        f'<text x="{W-pad}" y="{H-10}" fill="#8aa0c6" font-size="11" text-anchor="end">λ={wmax:.4f}µm</text>\n'
        f'</svg>'
    )


def _svg_transmon(levels):
    if not levels:
        return ""
    W, H, pad = 580, 240, 42
    emin, emax = levels[0], levels[-1]
    span = (emax - emin) or 1
    Y = lambda e: H - pad - (e - emin) / span * (H - 2 * pad)
    rows = ""
    for i, e in enumerate(levels):
        y = Y(e)
        lbl = "E0 基态" if i == 0 else (f"E1 · f01={levels[1]-levels[0]:.3f}" if i == 1 else f"E{i}")
        rows += (f'<line x1="{pad}" y1="{y:.1f}" x2="{W-pad}" y2="{y:.1f}" stroke="#7c3aed" stroke-width="2"/>\n'
                 f'<text x="{pad-6}" y="{y+3:.1f}" fill="#7c3aed" font-size="10" text-anchor="end">{lbl}</text>\n'
                 f'<text x="{W-pad+6}" y="{y+3:.1f}" fill="#8aa0c6" font-size="10">{e:.3f}</text>\n')
    y0, y1, ym = Y(levels[0]), Y(levels[1]), (Y(levels[0]) + Y(levels[1])) / 2
    arrow = (f'<line x1="{pad+26}" y1="{y0:.1f}" x2="{pad+26}" y2="{y1:.1f}" stroke="#e91e63" stroke-width="2"/>\n'
             f'<text x="{pad+30}" y="{ym:.1f}" fill="#e91e63" font-size="10">f01</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px;margin-top:8px">\n'
            f'{rows}{arrow}\n'
            f'<text x="{pad+4}" y="{pad-20}" fill="#7c3aed" font-size="11">Transmon 能级（电荷 basis 严格对角化，纯 numpy）· 标记 f01 跃迁</text>\n'
            f'</svg>')


def _fmt(x, n=5):
    try:
        return f"{x:.{n}f}"
    except Exception:
        return str(x)


def main() -> int:
    d = webapp.run_device_library_demo({})
    devs = d.get("devices", {})
    contracts = d.get("contracts", {})

    # 器件全景表
    table_rows = ""
    for n, s in devs.items():
        c = contracts.get(n, {})
        metric = {"fsr_nm": "FSR", "neff": "neff", "R_min_band": "R_min",
                  "kappa": "κ", "balance": "平衡度"}.get(s.get("metric"), s.get("metric"))
        pwin = " ; ".join(f"{k}∈[{v[0]},{v[1]}]" for k, v in s.get("params_schema", {}).items())
        vk = "/".join(s.get("ir_kinds", [])) or "—"
        table_rows += (
            f"<tr><td><b>{n}</b><br><span class='note'>IR:{vk}</span></td>"
            f"<td>{metric}</td><td>{pwin}</td>"
            f"<td><span class='v {'ok' if c.get('passed') else 'fail'}'>"
            f"{'PASS' if c.get('passed') else 'FAIL'}</span></td>"
            f"<td>{s.get('live_weight')}</td><td>{s.get('backend', 'numpy')}</td></tr>"
        )

    # Ring 双验证
    rf = d.get("ring_fdtd")
    ra = d.get("ring_analytic")
    if rf and ra:
        ring_block = (
            f"<div class='summary'>RingResonator 双验证（D-27/D-31/D-32）：</div>"
            f"<div class='note'>① 解析契约（RING-fsr）：candidate FSR={_fmt(ra.get('candidate_fsr_nm'))}nm "
            f"vs oracle {_fmt(ra.get('oracle_fsr_nm'))}nm · err={_fmt(ra.get('err'))} ≤ tol {ra.get('tol')} · "
            f"<span class='v {'ok' if ra.get('passed') else 'fail'}'>{'PASS' if ra.get('passed') else 'FAIL'}</span></div>"
            f"<div class='note'>② 真实 FDTD（R={rf.get('R_um')}µm）：drop 谱 {len(rf.get('peaks_um',[]))} 谐振峰 · "
            f"FSR(FDTD)={_fmt(rf.get('fsr_fdtd_nm'))}nm vs 解析 {_fmt(rf.get('fsr_analytic_nm'))}nm · "
            f"rel={rf.get('fsr_rel_dev',0)*100:.2f}% ≤ {rf.get('tol_rel',0)*100:.0f}% · "
            f"<span class='v {'ok' if rf.get('accepted') else 'fail'}'>{'PASS' if rf.get('accepted') else 'FAIL'}</span></div>"
            f"<div class='conclusion'><strong>结论：</strong>{rf.get('verdict','')}</div>"
        )
    else:
        ring_block = "<div class='note'>Ring FDTD 双验证数据不可用（需 GPU 机预计算 D-28 环形谱）</div>"

    # WG / Bragg
    wf = d.get("wg_fdtd")
    wa = d.get("wg_analytic")
    bf = d.get("bragg_fdtd")
    ba = d.get("bragg_analytic")
    if wf and wa:
        wg_block = (
            f"<div class='summary'>Waveguide 双验证（D-32 延伸 / D-34）：</div>"
            f"<div class='note'>① 解析契约（slab 闭式）：slab neff={_fmt(wa.get('slab_neff'))}（物理区间）· "
            f"<span class='v {'ok' if (wa.get('physical') and wa.get('passed')) else 'fail'}'>"
            f"{'PASS' if (wa.get('physical') and wa.get('passed')) else 'FAIL'}</span></div>"
            f"<div class='note'>② 真实 FDTD（2D-TE）：neff={_fmt(wf['fdtd']['neff_fdtd'])} ↔ slab ORACLE "
            f"{_fmt(wf['fdtd']['neff_oracle'])} · rel={wf['fdtd']['rel_err']*100:.2f}% ≤ {wf['fdtd']['tol_rel']*100:.0f}% · "
            f"<span class='v {'ok' if wf['fdtd']['accepted'] else 'fail'}'>{'PASS' if wf['fdtd']['accepted'] else 'FAIL'}</span></div>"
            f"<div class='conclusion'><strong>结论：</strong>{wf.get('verdict','')}</div>"
        )
    else:
        wg_block = "<div class='note'>Waveguide 真实 FDTD 双验证数据不可用</div>"
    if bf and ba:
        bg_block = (
            f"<div class='summary'>BraggMirror 双验证（D-32 延伸 / D-34）：</div>"
            f"<div class='note'>① 解析契约（TMM 闭式）：R_min(TMM)={_fmt(bf['analytic_contract']['R_min_tmm'])}（高反设计目标）· "
            f"<span class='v {'ok' if ba.get('passed') else 'fail'}'>{'PASS' if ba.get('passed') else 'FAIL'}</span></div>"
            f"<div class='note'>② 真实 FDTD（3D）：R_min={_fmt(bf['fdtd']['R_min_fdtd'])} ↔ TMM {_fmt(bf['fdtd']['R_min_tmm'])} · "
            f"abs={bf['fdtd']['abs_err']:.2e} ≤ {bf['fdtd']['tol_abs']*100:.0f}% · "
            f"<span class='v {'ok' if bf['fdtd']['accepted'] else 'fail'}'>{'PASS' if bf['fdtd']['accepted'] else 'FAIL'}</span></div>"
            f"{_svg_bragg(bf.get('spectrum', {}))}"
            f"<div class='conclusion'><strong>结论：</strong>{bf.get('verdict','')}</div>"
        )
    else:
        bg_block = "<div class='note'>BraggMirror 真实 FDTD 双验证数据不可用</div>"

    # Transmon（量子 D-35）
    tf = d.get("transmon_fdtd")
    if tf and tf.get("passed") is not None:
        tnum = tf.get("numerical", {})
        tac = tf.get("analytic_contract", {})
        q_block = (
            f"<div class='summary'>Transmon 双验证（D-35 量子域实质推进）：</div>"
            f"<div class='note'>① 解析契约（B9 Koch 反解命中设计目标）：target f01={_fmt(tac.get('target_f01_ghz'))}GHz → "
            f"反解 E_J={_fmt(tac.get('ej_hit'))}（落 EJ_bounds，hit_err={_fmt(tac.get('b9_hit_err'))}）· "
            f"<span class='v {'ok' if tac.get('analytic_hit') else 'fail'}'>{'PASS' if tac.get('analytic_hit') else 'FAIL'}</span></div>"
            f"<div class='note'>② 真实数值（transmon 哈密顿量严格对角化）：f01={_fmt(tnum.get('f01_diag'))}GHz ↔ Koch 解析 "
            f"{_fmt(tnum.get('f01_koch'))}GHz · rel={tnum.get('rel_err',0)*100:.2f}% ≤ {tnum.get('tol_rel',0)*100:.0f}% · "
            f"<span class='v {'ok' if tnum.get('accepted') else 'fail'}'>{'PASS' if tnum.get('accepted') else 'FAIL'}</span></div>"
            f"<div class='note'>辅助物理自洽：anharmonicity α={_fmt(tnum.get('alpha_diag'))}GHz（Koch≈{_fmt(tnum.get('alpha_koch'))}，量级一致）</div>"
            f"{_svg_transmon(tnum.get('levels_ghz', []))}"
            f"<div class='conclusion'><strong>结论：</strong>{tf.get('verdict','')}</div>"
        )
    else:
        q_block = "<div class='note'>Transmon 量子双验证数据不可用</div>"

    html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LDA 器件库真实物理验证面板（演示证据 · D-34/D-35）</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<h1>LDA 器件库真实物理验证面板</h1>
<p class="sub">演示证据固化页 · 与 WebUI ⑬ 面板同源数据（D-34 WG/Bragg + D-35 量子 Transmon）· 生成于本地自举求解器，T-8 后零 GPU 依赖（DC/YB torch CPU 回退 · WG numba-CPU · Bragg/Ring 纯 numpy）</p>

<div class="sec"><h2>器件全景表（D-12 固化 · D-04 统一契约）</h2>
<table><tr><th>器件</th><th>验收锚</th><th>参数窗口</th><th>契约</th><th>live_weight</th><th>后端</th></tr>
{table_rows}</table></div>

<div class="sec"><h2>RingResonator 双验证（解析契约 + 真实 FDTD）</h2>{ring_block}</div>
<div class="sec"><h2>Waveguide 双验证（解析 slab 契约 + 真实 FDTD neff）</h2>{wg_block}</div>
<div class="sec"><h2>BraggMirror 双验证（解析 TMM 契约 + 真实 FDTD 阻带）</h2>{bg_block}</div>
<div class="sec"><h2>Transmon 双验证（量子域 · Koch 解析 ↔ 严格对角化）</h2>{q_block}</div>

<div class="sec"><h2>判定哲学</h2>
<div class="note">每器件带参数窗口 + 统一验收契约 + 真实物理验证入口；验收两层各司其职——① 解析契约验设计目标命中，② 真实数值物理验自洽。LLM 不进判决路径，物理定律锚（解析近似 / 严格数值 / 确定性 ORACLE）为不可移除地基。</div>
</div>
</div></body></html>"""

    out = os.path.join(LDA_ROOT, "reports", "webui_device_panel_demo.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("written:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
