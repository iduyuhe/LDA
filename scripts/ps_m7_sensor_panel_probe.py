#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PS-M7 传感器面板门禁 · 突变探针（证明门禁真的会响）。

每条探针**只破坏一个语义**（文本级），同进程跑 `run_sensor_panel_smoke.main()`：
  · 突变后 ⇒ 门禁 rc ≠ 0（必红）；
  · 还原后 ⇒ 门禁 rc == 0（复绿）。
🔴 文本替换一律**全替换**（`str.replace(old, new)` 不带 count）—— 否则同一字样出现两处时
「存在性」断言仍成立 ⇒ 探针假绿。

用法：PYTHONPATH=lda python scripts/ps_m7_sensor_panel_probe.py
"""
from __future__ import annotations

import contextlib
import io as _io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "lda")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import run_sensor_panel_smoke as SMOKE  # noqa: E402

IDX = "lda/lda_webui/static/index.html"
RT = "lda/lda_webui/routes.py"
APIREF = "docs/api_reference.json"


@contextlib.contextmanager
def _TextMut(rel, old, new):
    fp = os.path.join(_ROOT, rel)
    bak = open(fp, encoding="utf-8", newline="").read()
    assert old in bak, f"[{rel}] 突变锚不存在：{old[:60]!r}"
    open(fp, "w", encoding="utf-8", newline="").write(bak.replace(old, new))
    try:
        yield
    finally:
        open(fp, "w", encoding="utf-8", newline="").write(bak)


def _run():
    SMOKE.PASS = 0
    SMOKE.FAIL = 0
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = SMOKE.main()
    except Exception:  # noqa: BLE001
        rc = 2
    return rc


def main() -> int:
    base = _run()
    print(f"[base] 未突变 rc={base}（期望 0）")
    if base != 0:
        print("!! 基线门禁自身不绿，探针无意义 ⇒ 中止")
        return 2

    probes = [
        ("P1 删 GET_ROUTES 注册行", RT,
         '    "/api/sensor_demo": h_sensor_demo,\n', ""),
        ("P2 删 handler 定义（def h_sensor_demo）", RT,
         "def h_sensor_demo(h, p, q, path):",
         "def _removed_h_sensor_demo(h, p, q, path):"),
        ("P3 端点误入 HEAVY_POST_PATHS", RT,
         "HEAVY_POST_PATHS = {", 'HEAVY_POST_PATHS = {\n    "/api/sensor_demo",'),
        ("P4 面板删诚实标注（去「零重计算」）", IDX,
         "🔵 <b>只读 · 免登录 · 零重计算</b>", "🔵 <b>只读</b>"),
        ("P5 删面板三容器之一（sensorBody）", IDX,
         '<div id="sensorBody"></div>', '<div id="sensorBodyRemoved"></div>'),
        ("P6 按钮 id 改成不以 run 开头", IDX,
         'id="runSensor"', 'id="sensorRun"'),
        ("P7 抹掉前端对 m.FSR_nm 的引用", IDX,
         "['自由光谱范围 FSR (nm)', _sxF(m.FSR_nm,4), 'λ²/(n_g·2πR)'],",
         "['自由光谱范围 FSR (nm)', '-', 'λ²/(n_g·2πR)'],"),
        ("P8 抹掉前端对 g.v_n_uV 的引用", IDX,
         "['TIA 噪声底 (µV)', _sxF(g.v_n_uV,2), '√(kT/C)'],",
         "['TIA 噪声底 (µV)', '-', '√(kT/C)'],"),
        ("P9 API 参考删 /api/sensor_demo 条目", APIREF,
         '"/api/sensor_demo"', '"/api/sensor_demo_REMOVED"'),
        ("P10 抹掉前端对 s.gds_file_bytes 的引用", IDX,
         "['GDS 文件字节数（实测 getsize）', _sxF(s.gds_file_bytes,0)],",
         "['GDS 文件字节数（实测 getsize）', '-'],"),
        ("P11 删 CASE_MAP 的 #sec-sensor 登记（面板失去 hash 深链直达）", IDX,
         ', "#sec-sensor": "runSensor"', ""),
    ]

    bad = 0
    for name, rel, old, new in probes:
        with _TextMut(rel, old, new):
            rc_mut = _run()
        rc_back = _run()
        ok = (rc_mut != 0) and (rc_back == 0)
        bad += 0 if ok else 1
        print(f"[{'OK ' if ok else 'BAD'}] {name} → 突变 rc={rc_mut}（期望≠0）· 还原 rc={rc_back}（期望 0）")

    print("")
    print(f"突变探针：{len(probes) - bad} / {len(probes)} 通过（每条突变必红 + 还原复绿）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
