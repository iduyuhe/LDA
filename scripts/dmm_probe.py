"""DMM 打分表门禁的**突变探针**（v0.9.140 · 2026-09-28）。

铁律 8：**没被验证过的护栏不算护栏**。本探针对 `run_dmm_scorecard_smoke.py`
及其真相源 `lda_harness/dmm_scorecard.py` 做**文件级变异**，逐条证明门禁会响：

  每组变异 = 改工作区文件 → 跑门禁 → 必须 rc≠0 → **按原字节还原** → sha256 复核 → 基线复绿。

变异集（覆盖 A/B/C/D/E/F/G 六组判据）：
  M1 伪造准入 kind（引擎不在 BRIDGEABLE）     ⇒ D4 数降 ⇒ F2 门禁红
  M2 门禁名改成不存在                          ⇒ B3 红
  M3 入口符号改成不存在                        ⇒ B2 红（本轮真实抓到的错，最有说服力）
  M4 证据门禁改成不存在                        ⇒ B5 红
  M5 G4_TOCKEN 口径改掉（不再硬开）            ⇒ D1 红 + D4 全降
  M6 M2 出口判据抬到 4                         ⇒ F2 红（闸门确实在判）
  M7 level_of 去掉事实门控（恒判 D3）          ⇒ C1 审计红（越级谎报必被抓）
  M8 手改生成文档（加一行）                    ⇒ G2 红（防手改漂移）
  M9 scorecard 注入 LLM 引用                   ⇒ H1 红（红线）

不进 CI core（与 p6/t62/t63/t64 探针同纪律）；运行：
  `PYTHONPATH=lda python scripts/dmm_probe.py`
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

SCORE = "lda/lda_harness/dmm_scorecard.py"
SMOKE = "lda/run_dmm_scorecard_smoke.py"
DOC = "docs/design_maturity_model.md"

def b_(s: str) -> bytes:
    """🔴 血案防复现：**bytes 字面量含中文会 SyntaxError**（本仓二犯）
    ⇒ 凡含非 ASCII 的锚点一律用 str 写、运行时 encode('utf-8')。"""
    return s.encode("utf-8")


MUTATIONS = [
    ("M1 伪造准入 kind（不在 BRIDGEABLE）",
     SCORE, b'"engine_ringresonator"', b'"engine_no_such_kind"'),
    ("M2 门禁名改成不存在", SCORE,
     b'smoke="run_lvs_smoke.py"', b'smoke="run_no_such_smoke_zzz.py"'),
    ("M3 入口符号改成不存在", SCORE,
     b'symbol="design_device"', b'symbol="design_device_zzz"'),
    ("M4 证据门禁白名单里一项改成不存在", SCORE,
     '"run_cross_solver_matrix_smoke.py",      # 内部异源交叉（9 格）',
     '"run_no_such_guard_zzz.py",             # 内部异源交叉（9 格）'),
    ("M5 G4 不再硬开（口径 token 改掉）", SCORE,
     b'G4_TOKEN = "with_geom_check=True"', b'G4_TOKEN = "with_geom_check=False"'),
    ("M6 M2 出口判据抬到 4", SCORE, b"M2_D4_MIN = 3", b"M2_D4_MIN = 4"),
    ("M7 level_of 去掉事实门控（恒判 D3）", SCORE,
     b'    if f["has_reverse_evidence"] and f["independence_guard_in_core"]:',
     b'    if True:'),
    ("M8 手改生成文档（加一行）", DOC,
     b_("# LDA 设计能力成熟度模型"), b_("# LDA 设计能力成熟度模型（手改）")),
    ("M9 scorecard 注入 LLM 引用", SCORE, b"import os\nimport re\n",
     b"import os\nimport re\nimport openai  # violation\n"),
]


def _abs(rel: str) -> str:
    return os.path.join(REPO, rel.replace("/", os.sep))


def sha(p: str) -> str:
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run_smoke() -> int:
    p = subprocess.run([PY, os.path.join(ROOT, "run_dmm_scorecard_smoke.py")],
                       cwd=REPO, env=ENV, capture_output=True, text=True, timeout=600)
    return p.returncode


def main() -> int:
    print("=" * 78)
    print("DMM 打分表门禁 · 突变探针（文件级变异 → 门禁必红 → 原字节还原）")
    print("=" * 78)

    base = run_smoke()
    print("基线：DMM 门禁 rc=%d（应为 0）" % base)
    if base != 0:
        print("🔴 基线非绿 ⇒ 探针结论无效，先修基线")
        return 2

    caught, missed, noop = [], [], []
    for label, rel, old, new in MUTATIONS:
        # 锚点可为 bytes（ASCII）或 str（含中文）——统一在此归一，避免 bytes 字面量坑
        old = b_(old) if isinstance(old, str) else old
        new = b_(new) if isinstance(new, str) else new
        p = _abs(rel)
        with open(p, "rb") as fh:
            blob = fh.read()
        if blob.count(old) != 1:
            print("  [SKIP] %-40s 锚点命中 %d 次（期望 1）" % (label, blob.count(old)))
            missed.append(label)
            continue
        before = sha(p)
        with open(p, "wb") as fh:
            fh.write(blob.replace(old, new))
        if sha(p) == before:
            noop.append(label)
            with open(p, "wb") as fh:
                fh.write(blob)
            print("  [NOOP] %-40s 字节未变（变异无效）" % label)
            continue
        rc = run_smoke()
        with open(p, "wb") as fh:                    # 按原字节还原
            fh.write(blob)
        ok_restore = sha(p) == before
        if rc != 0 and ok_restore:
            caught.append(label)
            print("  [RED ] %-40s 门禁 rc=%d ✅（已还原 sha 一致）" % (label, rc))
        elif not ok_restore:
            print("  [FAIL] %-40s 还原失败！" % label)
            return 3
        else:
            missed.append(label)
            print("  [GREEN] %-40s 门禁 rc=0 ❌（未被抓住）" % label)

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
