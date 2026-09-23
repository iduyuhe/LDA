# -*- coding: utf-8 -*-
"""P4 附属突变探针：证明 `run_polygon_voxel_smoke`（G16 任意几何）的判据**会响**。

人工运行 · **不进 CI** · 零源码突变（只 patch 运行时属性）· 报告字节级还原。

设计要点（与 `p4_cpml_probe.py` 同源）
--------------------------------------
`main()` 内 `from lda_solver import voxel_field as vf` 取的是 `sys.modules` 的**模块
对象** ⇒ patch `voxel_field.rasterize_polygon` 等属性即可注入缺陷，`main()` 里
`vf.rasterize_polygon(...)` 走注入版。`_area` 是本文件的模块级助手（登记数据用），
patch 它可验证「零 LLM/零网络」判据的**可证伪性**（同 G11 的 M7）。

每次只注入**一个**缺陷 ⇒ 断言对应判据变红（允许连带红，但要求目标判据必红）。
另含「合法必过」基线（无注入时 rc=0 / 0 条红）。

运行（仓库根）：python scripts/p4_polygon_probe.py  → 全过则 rc=0
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_ROOT, "lda")
for _p in (_LDA, os.path.join(_LDA, "lda_solver"), os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                             # noqa: E402
import run_polygon_voxel_smoke as S                            # noqa: E402
from lda_solver import voxel_field as vf                       # noqa: E402

REPORT = os.path.join(_LDA, "reports", "polygon_voxel_report.json")


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_gate():
    S._PASS = 0
    S._FAIL = 0
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = S.main()
    out = buf.getvalue()
    red = [ln.strip()[len("[FAIL]"):].strip()
           for ln in out.splitlines() if ln.strip().startswith("[FAIL]")]
    return rc, out, red


class _restorer:
    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        self.undo = self.fn()
        return self

    def __exit__(self, *exc):
        self.undo()
        return False


# ---------------------------------------------------------------------------
def inj_no_validate():
    """M1 畸形反例：拆掉输入验证 ⇒ 畸形输入不再 raise。"""
    orig = vf._validate_polygon
    vf._validate_polygon = lambda *a, **k: None
    return lambda: setattr(vf, "_validate_polygon", orig)


def inj_all_filled():
    """M2 语义反例：栅格化恒返回全 1（放弃 even-odd / 面积语义）。"""
    orig = vf.rasterize_polygon

    def fake(points, nx, ny, dl, subpixel=1):
        return np.ones((nx, ny), dtype=float)
    vf.rasterize_polygon = fake
    return lambda: setattr(vf, "rasterize_polygon", orig)


def inj_eps_drift():
    """M3 管线等价反例：ε 场整体加 1e-12（破坏与 stack 退化路径的逐位一致）。"""
    orig = vf.voxelize_polygons

    def fake(*a, **k):
        return orig(*a, **k) + 1e-12
    vf.voxelize_polygons = fake
    return lambda: setattr(vf, "voxelize_polygons", orig)


def inj_subpixel_noop():
    """M4 判据 D 反例：subpixel 被忽略（细化不改变结果）⇒ 序列不下降。"""
    orig = vf.rasterize_polygon

    def fake(points, nx, ny, dl, subpixel=1):
        return orig(points, nx, ny, dl, 1)
    vf.rasterize_polygon = fake
    return lambda: setattr(vf, "rasterize_polygon", orig)


def inj_orientation_dep():
    """M5 取向反例：顶点顺序反转时返回补集（栅格依赖顶点次序）。"""
    orig = vf.rasterize_polygon

    def fake(points, nx, ny, dl, subpixel=1):
        f = orig(points, nx, ny, dl, subpixel)
        pts = list(points)
        if tuple(pts[0]) > tuple(pts[-1]):
            return 1.0 - f
        return f
    vf.rasterize_polygon = fake
    return lambda: setattr(vf, "rasterize_polygon", orig)


def inj_no_clamp():
    """M6 亚格语义反例：返回不在 [0,1] 的「填充率」⇒ 三类格计数不闭合。"""
    orig = vf.rasterize_polygon

    def fake(points, nx, ny, dl, subpixel=1):
        return orig(points, nx, ny, dl, subpixel) * 2.0
    vf.rasterize_polygon = fake
    return lambda: setattr(vf, "rasterize_polygon", orig)


def inj_ignore_z():
    """M7 z 挤出反例：忽略 z0/z1，整柱都填材料。"""
    orig = vf.voxelize_polygons

    def fake(layers, materials, grid, background_ref="air", subpixel=1):
        fixed = []
        for lay in layers:
            fixed.append(type(lay)(lay.material_ref, lay.points, None, None,
                                   getattr(lay, "comment", None)))
        return orig(fixed, materials, grid, background_ref, subpixel)
    vf.voxelize_polygons = fake
    return lambda: setattr(vf, "voxelize_polygons", orig)


def inj_empty_not_bg():
    """M8 空集反例：空 layers 也返回材料（不再保持全背景）。"""
    orig = vf.voxelize_polygons

    def fake(layers, *a, **k):
        d = orig(layers, *a, **k)
        if not layers:
            d = np.full_like(d, 99.0)
        return d
    vf.voxelize_polygons = fake
    return lambda: setattr(vf, "voxelize_polygons", orig)


def inj_rect_drift():
    """M9 矩形管线反例：矩形路径整体加 1e-12 ⇒ 与多边形路径不再逐位一致。"""
    orig = vf.voxelize_rectangular

    def fake(*a, **k):
        return orig(*a, **k) + 1e-12
    vf.voxelize_rectangular = fake
    return lambda: setattr(vf, "voxelize_rectangular", orig)


def inj_net_token():
    """M10 红线反例：把网络 token 注入登记数据（内核模块名）⇒ ⑨ 必须红。"""
    orig = vf.__name__
    vf.__name__ = "https://example.com/llm"
    return lambda: setattr(vf, "__name__", orig)


MUTATIONS = [
    ("M1  畸形输入不再 raise", inj_no_validate, ["⑤a"], "输入验证守卫"),
    ("M2  栅格化恒全 1（放弃 even-odd）", inj_all_filled,
     ["①a", "①c", "①d", "②a", "③"], "面积/孔洞/自交判据全部绑定"),
    ("M3  ε 场加 1e-12", inj_eps_drift, ["③", "⑧"],
     "同时打断矩形管线逐位一致与 stack 链路一致"),
    ("M4  subpixel 被忽略（判据 D 空转）", inj_subpixel_noop,
     ["②a", "④c"], "细化参数必须真起作用"),
    ("M5  栅格依赖顶点次序", inj_orientation_dep, ["④a"], "取向无关性"),
    ("M6  填充率不落在 [0,1]", inj_no_clamp, ["⑦a"], "亚格平均语义"),
    ("M7  z 区间被忽略", inj_ignore_z, ["⑥b"], "z 挤出语义"),
    ("M8  空 layers 不再全背景", inj_empty_not_bg, ["⑥a"], "空集语义"),
    ("M9  矩形路径整体偏移", inj_rect_drift, ["③"],
     "只红 ③ ⇒ 与 M3 隔离（M3 额外红 ⑧）"),
    ("M10 红线：登记数据注入网络 token", inj_net_token, ["⑨"],
     "证明「零 LLM/零网络」判据**可证伪**"),
]


def main() -> int:
    print("=" * 78)
    print("P4-G16 突变探针：证明 run_polygon_voxel_smoke 的判据会响（零源码突变）")
    print("=" * 78)

    bak = REPORT + ".probe_bak"
    existed = os.path.exists(REPORT)
    if existed:
        shutil.copyfile(REPORT, bak)
    sha0 = _sha(REPORT) if existed else None

    try:
        rc0, out0, red0 = run_gate()
        base_ok = (rc0 == 0 and not red0)
        print("  基线（无注入）：rc=%s · 变红 %d 条 ⇒ %s"
              % (rc0, len(red0), "合法必过 ✅" if base_ok else "基线本身红 ❌"))
        print("-" * 78)

        results = []
        for name, inj, want, why in MUTATIONS:
            with _restorer(inj):
                rc, out, red = run_gate()
            hit = {w: any(l.startswith(w) for l in red) for w in want}
            ok = rc != 0 and all(hit.values())
            results.append((name, ok, red, want, why))
            print("  %-38s rc=%-3s 变红 %2d 条  %s"
                  % (name, rc, len(red), "PASS" if ok else "FAIL"))
            print("      判据命中: %s"
                  % " · ".join("%s=%s" % (w, "红" if h else "**未红**")
                               for w, h in hit.items()))
            if not ok:
                print("      实际变红: %s" % ([x[:52] for x in red] or "（无）"))
            print("      用意: %s" % why)
        print("-" * 78)
    finally:
        if existed:
            shutil.copyfile(bak, REPORT)
            os.remove(bak)
        sha1 = _sha(REPORT) if os.path.exists(REPORT) else None
        print("  报告字节还原：%s（sha256 %s）"
              % ("✅ 一致" if sha0 == sha1 else "❌ 不一致（探针污染了登记报告！）",
                 "n/a" if sha1 is None else sha1[:16]))

    n_ok = sum(1 for r in results if r[1])
    print("=" * 78)
    print("汇总：%d/%d 突变全部被对应判据捕获 —— %s"
          % (n_ok, len(MUTATIONS),
             "判据会响 ✅" if n_ok == len(MUTATIONS) else "存在哑判据 ❌"))
    return 0 if (n_ok == len(MUTATIONS) and base_ok and sha0 == sha1) else 1


if __name__ == "__main__":
    sys.exit(main())
