# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E5 · 平台能力硬化门禁（D-154）。

============================================================================
E5（吃狗粮收尾：把 E1~E4 逼出的平台能力**钉成常驻门禁**，防能力面静默失守）
----------------------------------------------------------------------------
不与各段自身门禁重复：本门禁守的是**"能力面整体"**——清单↔实际的双向完备 + 披露一致
+ 诚实边界。验收（与 CI core 同口径，死标量 + 突变探针）：
  ① 正向完备：清单每条 ⇒ 模块可导入 + 关键符号齐备；
  ② 反向完备：`lda_l2/ecore/` 下每个模块 ⇒ 必须在清单中登记（防隐身模块进盲区）；
  ③ 清单每条 guard smoke 文件真实存在（能力有门禁守着）；
  ④ `ECORE_DISCLOSURE` 含 e1~e9 全部 scope（披露一致）；
  ⑤ 诚实边界：能力面不含 TOPS/TOPS-W 等 fabricated 指标。

🔴 突变探针（防常数假绿 / 防死断言）：
  ⑥ 清单符号名损坏 → ① 必红；
  ⑦ 向能力注入 fabricated 指标（TOPS/W）→ ⑤ 必红；
  ⑧ 从清单移除一个模块登记 → ② 必红（反向完备非假绿）；
  ⑨ 还原后重跑①/②，确无残留漂移。

主权纪律（与全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；T1 电路级。
"""
import os
import sys
from unittest.mock import patch

from lda_l2.ecore import capability_manifest, scale_bench
from lda_l2.ecore import ECORE_DISCLOSURE
from lda_l2.ecore.capability_manifest import (
    ECORE_CAPABILITY_MANIFEST,
    manifest_check,
)
from lda_l2.ecore.scale_bench import honest_boundary_ok

_LDA_ROOT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# 绿色检查
# ---------------------------------------------------------------------------
def chk_forward_complete():
    c = manifest_check()
    ok = (not c["import_fail"]) and (not c["missing_symbols"])
    return ok, f"import_fail={c['import_fail']} missing_symbols={c['missing_symbols']}"


def chk_reverse_complete():
    c = manifest_check()
    ok = not c["undeclared_modules"]
    return ok, f"undeclared={c['undeclared_modules']} all={c['all_modules']}"


def chk_guards_exist():
    miss = []
    for e in capability_manifest.ECORE_CAPABILITY_MANIFEST:
        p = os.path.join(_LDA_ROOT, e["guard"])
        if not os.path.exists(p):
            miss.append(e["guard"])
    return (len(miss) == 0), f"missing_guards={miss}"


def chk_disclosure_scopes():
    need = [f"e{i}_scope" for i in range(1, 10)]
    missing = [k for k in need if k not in ECORE_DISCLOSURE]
    return (len(missing) == 0), f"missing_scopes={missing}"


def chk_honest_boundary():
    ok = honest_boundary_ok()
    return ok, f"honest_boundary_ok={ok}"


# ---------------------------------------------------------------------------
# 突变探针
# ---------------------------------------------------------------------------
def _manifest_with(mutator):
    import copy
    m = copy.deepcopy(ECORE_CAPABILITY_MANIFEST)
    mutator(m)
    return m


def probe_symbol_corrupt():
    def bad(m):
        m[0]["symbols"] = list(m[0]["symbols"]) + ["__nonexistent_symbol__"]
    with patch.object(capability_manifest, "ECORE_CAPABILITY_MANIFEST", _manifest_with(bad)):
        ok, _ = chk_forward_complete()
    return not ok


def probe_inject_fabricated_metric():
    bad = list(scale_bench.LDA_CAPABILITIES) + ["LDA 达到 76 TOPS/W（造假示例）"]
    with patch.object(scale_bench, "LDA_CAPABILITIES", bad):
        ok, _ = chk_honest_boundary()
    return not ok


def probe_module_undeclared():
    def bad(m):
        m.pop(0)                                  # 移除一条 ⇒ 该模块变"隐身"
    with patch.object(capability_manifest, "ECORE_CAPABILITY_MANIFEST", _manifest_with(bad)):
        ok, _ = chk_reverse_complete()
    return not ok


def main():
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA 电子计算征程 E5 · 平台能力硬化门禁（D-154）===")
    print("ECORE_CAPABILITY_DISCLOSURE:", capability_manifest.ECORE_CAPABILITY_DISCLOSURE["route"])
    c = manifest_check()
    print(f"能力清单: {len(ECORE_CAPABILITY_MANIFEST)} 条 · 模块 {c['all_modules']}")

    # —— 绿：能力面双向完备 + 披露一致 + 诚实边界 ——
    ok, det = chk_forward_complete()
    check("① 正向完备: 清单每条 模块可导入 + 符号齐备", ok, det)
    ok, det = chk_reverse_complete()
    check("② 反向完备: ecore 每模块都在清单中登记", ok, det)
    ok, det = chk_guards_exist()
    check("③ 清单每条 guard smoke 文件真实存在", ok, det)
    ok, det = chk_disclosure_scopes()
    check("④ ECORE_DISCLOSURE 含 e1~e9 全部 scope", ok, det)
    ok, det = chk_honest_boundary()
    check("⑤ 诚实边界: 能力面无 TOPS/TOPS-W 指标", ok, det)

    # —— 红：突变探针（必变红，否则为死断言）——
    check("🔴 ⑥ 突变探针: 清单符号名损坏 → ① 必红", probe_symbol_corrupt(),
          "未变红（死断言!）")
    check("🔴 ⑦ 突变探针: 注入 fabricated 指标 → ⑤ 必红",
          probe_inject_fabricated_metric(), "未变红（死断言!）")
    check("🔴 ⑧ 突变探针: 移除模块登记 → ② 必红（反向完备非假绿）",
          probe_module_undeclared(), "未变红（死断言!）")

    # —— 还原完整性 ——
    ok, det = chk_forward_complete()
    check("⑨ 还原重跑: 正向完备无残留漂移", ok, det)
    ok, det = chk_reverse_complete()
    check("⑨ 还原重跑: 反向完备无残留漂移", ok, det)

    if fails:
        print(f"\nE5 门禁: {len(fails)} FAIL -> {fails}")
        sys.exit(1)
    print("\nE5 门禁: ALL GREEN（含 3 道突变探针 + 还原完整性）")


if __name__ == "__main__":
    main()
