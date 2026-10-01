#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_w2_e2e_d4.py — W2 交付闭环（D3→D4）进程内端到端实测（临时脚本，跑完即删）。

链路：/api/design_outcome 目录 → 引擎闭环（真求解器）→ 最优已验证参数
      → /api/design_tapeout（芯片级 GDS + DRC/LVS 双闸 + 流片报告 + download_url）
      → /api/design_gds（按 URL 确定性重建下载）
判据：① outcome ok + 有最优已验证候选 ② chip.verdict == ACCEPT
      ③ tapeout.accepted ④ 下载字节 sha256 == 响应登记 sha256 ⑤ 字节非空。
"""
import hashlib
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lda"))

from lda_webui.app import run_design_outcome, run_design_tapeout, run_design_gds

def main():
    fails = []

    def check(name, cond, detail=""):
        print(("[PASS] " if cond else "[FAIL] ") + name + (("  (" + str(detail) + ")") if detail else ""))
        if not cond:
            fails.append(name)

    # ① 目录模式（不跑求解器）：取一个引擎类 kind 与其 default_target
    cat = run_design_outcome({})
    check("目录模式 ok", bool(cat.get("ok")), str(cat.get("error")))
    engine_cat = (cat.get("catalog") or {}).get("engine") or {}
    items = (engine_cat if isinstance(engine_cat, list)
             else (engine_cat.get("kinds") or engine_cat.get("entries") or []))
    entry = None
    for e in items:
        if isinstance(e, dict) and e.get("kind"):
            entry = e
            break
    check("目录含引擎类条目", entry is not None, str(entry)[:120] if entry else str(engine_cat)[:120])
    if not entry:
        return 1
    kind = entry["kind"]
    target = entry.get("default_target", 5.0)
    # Waveguide 被主动排除出芯片级桥接表（宽度是全局参数）——选可签核器件
    for e in items:
        if e.get("engine_kind") == "RingResonator":
            kind, target = e["kind"], e.get("default_target", 5.0)
            break

    # ② 引擎闭环：目标 → 搜索 → 双重验证 → 统一设计包
    oc = run_design_outcome({"kind": kind, "target": target, "top_k": 3})
    check("设计闭环 ok", bool(oc.get("ok")), str(oc.get("error")))
    er = oc.get("engine_result") or {}
    best = er.get("best")
    check("存在最优已验证候选", bool(best), "metric=%s" % (best or {}).get("metric"))
    if not (oc.get("ok") and best):
        return 1
    pkgv = ((oc.get("package") or {}).get("verification") or {})
    check("统一设计包验收 PASS", bool(pkgv.get("passed")))

    # ③ 设计包 → 芯片级 GDS + 双闸签核 + download_url
    tp = run_design_tapeout({"engine_kind": kind, "params": best["params"],
                             "name": "w2_e2e_%s" % kind})
    check("design_tapeout ok（双闸 ACCEPT）", bool(tp.get("ok")), str(tp.get("errors"))[:160])
    chip = tp.get("chip") or {}
    check("chip.verdict == ACCEPT", chip.get("verdict") == "ACCEPT", chip.get("verdict"))
    tapeout = tp.get("tapeout") or {}
    check("流片报告 accepted", bool(tapeout.get("accepted")), tapeout.get("verdict"))
    g = tp.get("gds") or {}
    check("gds.available", bool(g.get("available")), "bytes=%s" % g.get("bytes"))
    if not g.get("available"):
        return 1

    # ④ 下载端点：按 download_url 确定性重建，sha256 必须同源一致
    q = parse_qs(urlparse(g["download_url"]).query)
    flat = {k: v[0] for k, v in q.items()}
    data, meta = run_design_gds(flat)
    check("下载端点返回字节", isinstance(data, (bytes, bytearray)) and len(data) > 0,
          "len=%s" % (len(data) if data else 0))
    sha = hashlib.sha256(data).hexdigest()
    check("下载 sha256 == 响应登记 sha256", sha == g.get("sha256"),
          "%s… vs %s…" % (sha[:16], str(g.get("sha256"))[:16]))
    check("GDS 头记录（00 06 00 02 = len6·HEADER）", bytes(data[:4]) == b"\x00\x06\x00\x02",
          str(bytes(data[:4])))

    print()
    if fails:
        print("E2E RESULT: %d FAIL: %s" % (len(fails), fails))
        return 1
    print("E2E RESULT: ALL PASS — 设计→GDS→签核→下载 单路径全链贯通（进程内实测）")
    return 0

if __name__ == "__main__":
    sys.exit(main())
