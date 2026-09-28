"""G4「几何回提」门禁的**突变探针**（v0.9.141 · M4 攻关）。

铁律 8：**没被验证过的护栏不算护栏**。本探针对 `run_lvs_geom_smoke.py`
及其真相源（`lda_l2/lvs_geom.py`、`primitives.py`、`gds_export.py`、
`chip_layout_export.py`）做**文件级变异**，逐条证明门禁会响：

  每组变异 = 改工作区文件 → 跑门禁 → 必须 rc≠0 → **按原字节还原** → sha256 复核 → 基线复绿。

变异集（覆盖 ⑬⑭⑮⑯⑰⑱⑲⑳ 全部新增判据 + ③④⑧ 既有判据）：
  M1  器件类清单塞入未知 kind（MZI→MZIx）      ⇒ ⑮ 类覆盖 13/14 红
  M2  器件类清单改名（RingAddDrop→…X）          ⇒ ⑮ 与 link_model 对表红
  M3  删除 MMIC 回提条目                        ⇒ ⑬ 双向量红（清单留孤儿）
  M4  `_m_ring_gap` 恒返回 None                 ⇒ ⑯⑱ 红（声明的几何量测不出）
  M5  MZI.gap 错标 geometric                    ⇒ ⑰ 红（几何不敏感 ⇔ 类别矛盾）
  M6  gds_export 不再路由 MZI                   ⇒ ⑮ 红（几何不可生成）
  M7  规范声明塞入未分类参数                    ⇒ ⑰ 零未分类红
  M8  测量器读 `.params`（破坏独立性）           ⇒ ⑧ 红
  M9  `NO_NAMED_ADD_DEVICE` 造假（+MZI）        ⇒ ⑲ 红
  M10 lvs_geom 注入 LLM 引用                    ⇒ ⑭ 红线红
  M11 mzi_descs 丢 dy（两臂重合）               ⇒ ⑯⑰ 红
  M12 取消 PhaseShifter 几何左端对齐            ⇒ ⑳ 端口锚点越界红
  M13 `if not ok:` 恒假（不报违规）             ⇒ ③④⑱ 红

不进 CI core（与 p2–p6 / dmm 探针同纪律）；运行：
  `PYTHONPATH=lda python scripts/g4_probe.py`
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, "lda")
PY = sys.executable
ENV = dict(os.environ)
ENV["PYTHONPATH"] = ROOT
ENV["PYTHONDONTWRITEBYTECODE"] = "1"

LG = "lda/lda_l2/lvs_geom.py"
PR = "lda/lda_l2/primitives.py"
GE = "lda/lda_l2/gds_export.py"
CE = "lda/lda_l2/chip_layout_export.py"


def b_(s: str) -> bytes:
    """🔴 血案防复现：**bytes 字面量含中文会 SyntaxError**（本仓二犯）
    ⇒ 凡含非 ASCII 的锚点一律用 str 写、运行时 encode('utf-8')。"""
    return s.encode("utf-8")


MUTATIONS = [
    ("M1 器件类清单塞入未知 kind（MZI→MZIx）", LG,
     '"Splitter", "MZI", "PhaseShifter",',
     '"Splitter", "MZIx", "PhaseShifter",'),

    ("M2 器件类清单改名（RingAddDrop→X）", LG,
     '    "RingAddDrop", "MMI", "MMIC", "Splitter", "MZI", "PhaseShifter",',
     '    "RingAddDropX", "MMI", "MMIC", "Splitter", "MZI", "PhaseShifter",'),

    ("M3 删除 MMIC 回提条目（清单留孤儿）", LG,
     '''    "MMIC": {"L_mmi": _m_body_rect_x, "W_mmi": _m_body_rect_y,
             "L_tap": _m_lead_len_single, "L_out": _m_lead_len_array,
             "out_gap": _m_lead_gap, "n_in": _m_lead_count_array,
             "width": _m_lead_width},
''',
     "    # MUTATED-AWAY\n"),

    ("M4 _m_ring_gap 恒返回 None", LG,
     "    return off - R - wg / 2.0", "    return None"),

    ("M5 MZI.gap 错标 geometric", LG,
     '''        "gap": ("not_encoded",
                "耦合发生在**相邻** MZI 之间；单元自身不含耦合器几何"),''',
     '''        "gap": ("geometric",
                "耦合发生在**相邻** MZI 之间；单元自身不含耦合器几何"),'''),

    ("M6 gds_export 不再路由 MZI", GE,
     '                  "BraggMirror", "Splitter", "MMIC", "MZI",',
     '                  "BraggMirror", "Splitter", "MMIC",'),

    ("M7 规范声明塞入未分类参数", LG,
     '    "Splitter": {"length": 5.0, "width": 2.0},',
     '    "Splitter": {"length": 5.0, "width": 2.0, "mystery_um": 1.0},'),

    ("M8 测量器读 .params（破坏独立性）", LG,
     "    off = min((abs(p[1]) for g in buses for p in g[3]), default=None)",
     '    _decl = "z".params  # probe\n'
     "    off = min((abs(p[1]) for g in buses for p in g[3]), default=None)"),

    ("M9 NO_NAMED_ADD_DEVICE 造假（+MZI）", LG,
     '''NO_NAMED_ADD_DEVICE: Tuple[str, ...] = (
    "BraggMirror", "DirectionalCoupler", "MziModulator", "Photodetector",''',
     '''NO_NAMED_ADD_DEVICE: Tuple[str, ...] = (
    "MZI", "BraggMirror", "DirectionalCoupler", "MziModulator", "Photodetector",'''),

    ("M10 lvs_geom 注入 LLM 引用", LG,
     "import math\nfrom typing import Any, Dict, List, Optional, Sequence, Tuple",
     "import math\nimport openai  # violation\n"
     "from typing import Any, Dict, List, Optional, Sequence, Tuple"),

    ("M11 mzi_descs 丢 dy（两臂重合）", PR,
     '         "points_um": [(0.0, dy), (Lu, dy)]},',
     '         "points_um": [(0.0, 0.0), (Lu, 0.0)]},'),

    ("M12 取消 PhaseShifter 几何左端对齐", CE,
     "        return [_shift_geom(g, ox - dx, oy) for g in local]",
     "        return [_shift_geom(g, ox, oy) for g in local]"),

    ("M13 `if not ok:` 恒假（不报违规）", LG,
     "            if not ok:", "            if False:"),
]


def _abs(rel: str) -> str:
    return os.path.join(REPO, rel.replace("/", os.sep))


def sha(p: str) -> str:
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_smoke() -> int:
    p = subprocess.run([PY, os.path.join(ROOT, "run_lvs_geom_smoke.py")],
                       cwd=REPO, env=ENV, capture_output=True, text=True,
                       timeout=600)
    return p.returncode


def main() -> int:
    print("=" * 78)
    print("G4 几何回提门禁 · 突变探针（文件级变异 → 门禁必红 → 原字节还原）")
    print("=" * 78)

    base = run_smoke()
    print("基线：G4 门禁 rc=%d（应为 0）" % base)
    if base != 0:
        print("🔴 基线非绿 ⇒ 探针结论无效，先修基线")
        return 2

    caught, missed, noop = [], [], []
    for label, rel, old, new in MUTATIONS:
        old = b_(old) if isinstance(old, str) else old
        new = b_(new) if isinstance(new, str) else new
        p = _abs(rel)
        with open(p, "rb") as fh:
            blob = fh.read()
        if blob.count(old) != 1:
            print("  [SKIP] %-44s 锚点命中 %d 次（期望 1）"
                  % (label, blob.count(old)))
            missed.append(label)
            continue
        before = sha(p)
        with open(p, "wb") as fh:
            fh.write(blob.replace(old, new))
        if sha(p) == before:
            noop.append(label)
            with open(p, "wb") as fh:
                fh.write(blob)
            print("  [NOOP] %-44s 字节未变（变异无效）" % label)
            continue
        rc = run_smoke()
        with open(p, "wb") as fh:                    # 按原字节还原
            fh.write(blob)
        ok_restore = sha(p) == before
        if rc != 0 and ok_restore:
            caught.append(label)
            print("  [RED ] %-44s 门禁 rc=%d ✅（已还原 sha 一致）" % (label, rc))
        elif not ok_restore:
            print("  [FAIL] %-44s 还原失败！" % label)
            return 3
        else:
            missed.append(label)
            print("  [GREEN] %-44s 门禁 rc=0 ❌（未被抓住）" % label)

    after = run_smoke()
    print()
    print("还原后基线：rc=%d（应为 0）" % after)
    print("=" * 78)
    print("突变探针：%d/%d 会响 · 锚点未命中 %d · 无效变异 %d · 还原后基线 %s"
          % (len(caught), len(MUTATIONS), len(missed), len(noop),
             "绿 ✅" if after == 0 else "红 🔴"))
    for m in missed:
        print("   未抓住:", m)
    ok = (len(caught) == len(MUTATIONS)) and after == 0 and not noop
    print("RESULT:", "ALL_MUTATIONS_CAUGHT" if ok else "INCOMPLETE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
