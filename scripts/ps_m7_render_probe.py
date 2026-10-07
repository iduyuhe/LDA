#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PS-M7 传感器面板 · 同源渲染断言（比截图更精确）。

抽 `index.html` 里**真渲染代码**（`_qcTbl` + `renderSensor` 段）→ 注入**真 JSON**
（`sensor_case.case_card()` 现算）→ 在 node 里执行 → 断言产出的 HTML **不含 NaN / undefined**
且含关键数值。防「前端取值路径问错地方 ⇒ 面板静默显示 0.0 / NaN」（血案 #32）。

无 node 时**软跳过**（返回 0 并注明），不阻塞无 node 环境。

用法：PYTHONPATH=lda python scripts/ps_m7_render_probe.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "lda")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NODE_CANDIDATES = [
    r"C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-6/node.exe",
    "node",
]


def _node():
    for c in NODE_CANDIDATES:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        elif shutil.which(c):
            return c
    return None


def main() -> int:
    idx = open(os.path.join(_ROOT, "lda/lda_webui/static/index.html"),
               encoding="utf-8").read()

    # 抽 _qcTbl（真实现）
    i = idx.find("function _qcTbl")
    j = idx.find("</script>", i)
    qct = idx[i:j].split("\n}")[0] + "\n}"

    # 抽传感器渲染段（真实现）
    k = idx.find("function _sxF")
    m = idx.find("if($('runSensor')) $('runSensor').onclick = runSensor;", k)
    sensor_js = idx[k:m + len("if($('runSensor')) $('runSensor').onclick = runSensor;")]

    from lda_webui import sensor_case as SC
    card = SC.case_card()

    # 也跑一个「氧化包层 + 非默认旋钮」组合，覆盖参数分支
    card2 = SC.case_card(arch_id="slab_hf_oxide", R_um=25, Q=5e4, delta_n=0.003)

    harness = f"""
const _els = {{}};
function $(id) {{
  if (!_els[id]) _els[id] = {{innerHTML:'', textContent:'', value:'', min:'', max:'', step:'',
    title:'', disabled:false, options:{{length:0}}, style:{{}},
    addEventListener:function(){{}}, set innerHTML2(v){{}}}};
  return _els[id];
}}
{qct}
{sensor_js}

function run(card) {{
  for (const k2 in _els) delete _els[k2];
  renderSensor(card);
  return ($('sensorSummary').innerHTML || '') + ($('sensorBody').innerHTML || '')
       + ($('sensorConclusion').innerHTML || '');
}}

const out1 = run({json.dumps(card)});
const out2 = run({json.dumps(card2)});
console.log('__OUT__' + JSON.stringify({{
  len1: out1.length, len2: out2.length,
  nan1: /NaN/.test(out1), nan2: /NaN/.test(out2),
  undef1: /undefined/.test(out1), undef2: /undefined/.test(out2),
  has_FSR: out1.indexOf('10.65') >= 0,
  has_LOD: out1.indexOf('9.300e-7') >= 0,
  has_gds: out1.indexOf('684') >= 0,
  has_verdict: out1.indexOf('DESIGN_BUDGET') >= 0,
  has_temp: out1.indexOf('温漂') >= 0,
  has_milestone: out1.indexOf('PS-M6') >= 0,
  has_archid: out1.indexOf('slab_hf_water') >= 0
}}));
"""
    nj = os.path.join(_ROOT, "_ps_m7_render_harness.js")
    open(nj, "w", encoding="utf-8", newline="").write(harness)

    node = _node()
    if not node:
        print("[SKIP] 未找到 node ⇒ 同源渲染断言软跳过")
        return 0

    r = subprocess.run([node, nj], capture_output=True, text=True, timeout=120)
    line = next((x for x in (r.stdout or "").splitlines() if x.startswith("__OUT__")), None)
    if not line:
        print("[ERR] node 未产出断言行"); print(r.stdout[-1500:]); print(r.stderr[-1500:])
        return 2
    d = json.loads(line[len("__OUT__"):])
    print("[render] %s" % d)

    checks = [
        ("R1 两组合均产出非空 HTML", d["len1"] > 500 and d["len2"] > 500),
        ("R2 无 NaN（两组）", not d["nan1"] and not d["nan2"]),
        ("R3 无 undefined（两组）", not d["undef1"] and not d["undef2"]),
        ("R4 含 FSR 值（10.65）", d["has_FSR"]),
        ("R5 含 LOD_real 科学计数", d["has_LOD"]),
        ("R6 含签核 GDS 字节（684）", d["has_gds"]),
        ("R7 含判决口径 DESIGN_BUDGET", d["has_verdict"]),
        ("R8 含「温漂」主导标注", d["has_temp"]),
        ("R9 含里程碑 PS-M6", d["has_milestone"]),
        ("R10 含架构 id（下拉同源）", d["has_archid"]),
    ]
    bad = 0
    for name, ok in checks:
        bad += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print("")
    print(f"同源渲染断言：{len(checks) - bad} / {len(checks)} 通过")
    try:
        os.remove(nj)
    except OSError:
        pass
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
