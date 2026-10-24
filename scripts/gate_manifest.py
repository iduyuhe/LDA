# -*- coding: utf-8 -*-
"""BL-M4 · 门禁运行时登记 → 受跟踪 `gate_anchor_manifest.json`（机器生成 · **禁手写**）。

背景（为什么需要它）：
  K4 的 L2 原定义是「CORE 门禁源码（去注释后）**显式出现锚号**」——这是**文本代理**：
  在门禁里写一行锚号就能让 L2 +1，而判据强度一点没变（指标游戏，与「不虚报」红线冲突）。
  BL-M4 把 L2 升为 `文本提及 ∪ manifest`，其中 manifest 由**门禁运行时登记**它实际
  断言过的锚号得到 —— 不是手写清单，也不是扫源码字符串。

机制：
  1. 门禁模块导出 `asserted_anchor_ids()`（本仓 = `run_bl_anchor_guard_smoke.py`，
     从受跟踪 `bl_anchor_audit.json` 的 `rows` 派生，即 B 组**逐锚硬断言**的锚集）。
  2. 本生成器 **import 该门禁模块并调用** `asserted_anchor_ids()` ⇒ 登记面与运行时
     断言集同源。
  3. 写受跟踪 `lda/reports/gate_anchor_manifest.json`。
  4. 双向锁死：门禁侧 H7 判据断言 `manifest[本门禁] ≡ 本次运行实际断言锚集`（删一条必红）；
     K4 门禁再断言 `coverage.manifest ≡ 本文件`（两副本不漂移）+ `L2 ≡ 文本 ∪ manifest`。

确定性：零时间戳 / 零随机 / 零进程依赖；键序固定（sort_keys）；写盘走
`lda_harness.deterministic.write_text`（UTF-8 + LF）。

用法：
    python scripts/gate_manifest.py            # 打印台账正文（供门禁逐字节对拍）
    python scripts/gate_manifest.py --write    # 写回 lda/reports/gate_anchor_manifest.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LDA = os.path.join(_REPO, "lda")
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness import deterministic as det  # noqa: E402  （⑧b：确定性唯一口径）

SCHEMA = "lda_gate_anchor_manifest_v1"
OUT_REL = "lda/reports/gate_anchor_manifest.json"

# 运行时登记门禁：门禁模块名 → (运行时符号, 数据源)
_GATES = {
    "run_bl_anchor_guard_smoke.py": (
        "asserted_anchor_ids",
        "lda/reports/bl_anchor_audit.json",
    ),
    # ─────────────────────────────────────────────────────────────────────
    # N2（v0.9.282）· 超导域判据深度：以下门禁**真的执行**账本锚
    # （`BENCHMARK_DEFS[锚]` / `resolve_specs(only=(...))`），导出运行时断言集。
    # 🔴 接入条件（缺一不可）：① 门禁内确有执行语句 ② 有 H7 双向锁死判据
    #    ③ 不是"为刷覆盖而写的锚号字面量"（见 N2 规划 §1.3 反例）。
    # ─────────────────────────────────────────────────────────────────────
    "run_b30_readout_smoke.py": (
        "asserted_anchor_ids",
        "内联：run_verification(B30) 正向 + nbar 反向",
    ),
    "run_fluxonium_anchor_smoke.py": (
        "asserted_anchor_ids",
        "内联：VerificationHarness.resolve_specs(only=B23,B24) + 引擎对拍",
    ),
    "run_transmon_double_verify_smoke.py": (
        "asserted_anchor_ids",
        "内联：build_harness_specs → run_verification(B9)（Koch ↔ 严格对角化）",
    ),
    "run_qubit_resonator_smoke.py": (
        "asserted_anchor_ids",
        "内联：build_harness_specs → run_verification(B12)（λ/4 谐振器）",
    ),
    "run_j3_ctrl_smoke.py": (
        "asserted_anchor_ids",
        "内联：build_harness_specs → run_verification(B18)（Purcell，**自证锚**）",
    ),
}


def _import_gate(name: str):
    path = os.path.join(_LDA, name)
    spec = importlib.util.spec_from_file_location("_gm_" + name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build():
    registries = {}
    per_gate = {}
    union = set()
    for gate, (sym, src) in sorted(_GATES.items()):
        mod = _import_gate(gate)
        ids = sorted(set(getattr(mod, sym)()))
        registries[gate] = {
            "runtime_symbol": sym,
            "source_rel": src,
            "count": len(ids),
            "anchors": ids,
        }
        per_gate[gate] = len(ids)
        union |= set(ids)

    payload = {
        "schema": SCHEMA,
        "generated_by": "scripts/gate_manifest.py",
        "subject": "gate runtime-registered anchor manifest (L2 union source)",
        "method": ("门禁运行时登记：import 门禁模块 → asserted_anchor_ids()"
                   "（从实际断言行集派生 · 非手写清单 · 非源码字符串扫描）"),
        "excluded_fields": ["时间戳（非确定量）", "git HEAD（每次提交都变）"],
        "registries": registries,
        "summary": {
            "gates": len(registries),
            "anchors_union": len(union),
            "per_gate": per_gate,
        },
    }
    return payload


def render(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="门禁运行时登记 → gate_anchor_manifest.json")
    ap.add_argument("--write", action="store_true", help="写回受跟踪台账")
    args = ap.parse_args(argv)

    payload = build()
    text = render(payload)
    if args.write:
        det.write_text(os.path.join(_REPO, OUT_REL), text)
        s = payload["summary"]
        print("[written] %s（门禁 %d · 锚并集 %d）"
              % (OUT_REL, s["gates"], s["anchors_union"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
