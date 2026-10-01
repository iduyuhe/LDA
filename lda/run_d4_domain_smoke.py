# -*- coding: utf-8 -*-
"""LDA · D4 交付闭环扩面门禁（W5-1 · ecore / 量子侧 · 2026-10-02）。

============================================================================
守什么（v0.9.172 · CI core 263）
----------------------------------------------------------------------------
W2 已实测贯通光子侧「设计 → GDS → 签核 → 下载」。本门禁守的是**扩面后的两条新产线**
（电子 ecore 交叉阵列 + 超导 transmon 阵列）不掉回「能算对但交不出去」：

  ① 域完备：D4_DOMAINS 与门禁显式表逐位相等（🔴 反向完备——新域必须进门禁，
     否则静默进盲区）；
  ② 真 GDS：字节非空 + 头魔数 `00 06 00 02`（与光子 D4 同口径）+ sha256 形状；
  ③ 双闸 ACCEPT：DRC + LVS 皆 ACCEPT 且整体 verdict 与之咬合（不看单一闸）；
  ④ 确定性：同参数两次 sha256 逐位一致，**且不同参数必须不同**
     （防「常数假确定性」：恒定 sha256 会同时骗过两侧判据）；
  ⑤ 对外只给标量：deliver_report 不含 gds 字节面；
  ⑥ 未知域快失败：不注册即红，不静默 fallback；
  ⑦ 诚实边界：honest_notes 在场且含「非实测」声明、无 TOPS 主张。

🔴 突变探针（进程内 patch.object，防死断言）：
  ① 量子域 GDS 伪造为空字节 ⇒ 真-GDS 判据必红；
  ② ecore 域 DRC 伪造成 REJECT ⇒ 双闸判据必红；
  ③ 注册域里塞入 ghost 域（模拟「新域没接门禁」）⇒ 域完备判据必红。
"""
from __future__ import annotations

import sys
import unittest.mock as mock

from lda_l2 import d4_domains as dm

# 🔴 门禁显式表（反向完备的锚：D4_DOMAINS 必须与本表逐位相等）
EXPECTED_DOMAINS = ("ecore", "quantum_sc")


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA · D4 交付闭环扩面门禁（ecore / 量子侧）===")

    # —— ① 域完备（反向完备判据：成员集 ≡ 显式表）——
    check("①a 注册域与门禁显式表逐位相等（新域必须进门禁）",
          set(dm.D4_DOMAINS) == set(EXPECTED_DOMAINS)
          and len(dm.D4_DOMAINS) == len(EXPECTED_DOMAINS),
          "注册=%s 期望=%s" % (list(dm.D4_DOMAINS), list(EXPECTED_DOMAINS)))
    check("①b 每域都有对外标签与诚实边界注记",
          all(d in dm.DOMAIN_LABELS and dm.DOMAIN_LABELS[d] for d in dm.D4_DOMAINS)
          and "非实测" in dm.HONEST_NOTES)

    # —— ② 真 GDS ——
    for d in dm.D4_DOMAINS:
        r = dm.build_domain(d)
        g = r.get("gds") or {}
        check(f"② {d}: GDS 非空 + 头魔数 00 06 00 02 + sha256 形状",
              bool(r.get("ok")) and g.get("n_bytes", 0) > 0
              and g.get("header_ok") is True
              and len(str(g.get("sha256", ""))) == 64,
              f"bytes={g.get('n_bytes')} sha={str(g.get('sha256'))[:16]}")

    # —— ③ 双闸 ——
    for d in dm.D4_DOMAINS:
        r = dm.build_domain(d)
        check(f"③ {d}: DRC + LVS 双闸 ACCEPT 且整体 verdict 咬合",
              r.get("verdict") == "ACCEPT"
              and r.get("drc", {}).get("verdict") == "ACCEPT"
              and r.get("lvs", {}).get("verdict") == "ACCEPT",
              f"drc={r.get('drc')} lvs={r.get('lvs')}")

    # —— ④ 确定性（双向）——
    a1 = dm.build_domain("ecore")
    a2 = dm.build_domain("ecore")
    b1 = dm.build_domain("ecore", {"n": 6, "m": 6})
    check("④a 同参数两次 sha256 逐位一致（确定性）",
          a1["gds"]["sha256"] == a2["gds"]["sha256"])
    check("④b 换参数 sha256 必须变化（反「常数假确定性」）",
          b1["gds"]["sha256"] != a1["gds"]["sha256"]
          and b1["gds"]["n_bytes"] != a1["gds"]["n_bytes"],
          "恒等 sha ⇒ 假确定性")

    # —— ⑤ 对外只给标量 ——
    rep = dm.deliver_report("quantum_sc")
    check("⑤ deliver_report 不含字节面（对外只给标量）",
          "gds_bytes" not in rep and "elements" not in rep
          and rep["gds"]["n_bytes"] == dm.build_domain("quantum_sc")["gds"]["n_bytes"])

    # —— ⑥ 未知域快失败 ——
    bad = dm.build_domain("ghost_domain")
    check("⑥ 未知域快失败（ok=False + 提示已注册域）",
          bad.get("ok") is False and "未知交付域" in "".join(bad.get("errors") or []))

    # —— ⑦ 诚实边界 ——
    blob = "".join(dm.deliver_report(d).get("honest_notes", "") for d in dm.D4_DOMAINS)
    check("⑦ 每个域的诚实注记含「非实测签核」+ 声明「不报 TOPS」（只扫肯定表述字段）",
          "非实测签核" in blob and "不报 TOPS" in blob)

    # —— 🔴 突变探针 ——
    _orig_q = dm._build_quantum_sc          # 🔴 先抓原句柄：打桩后 dm._build_* 即 mock 本身
    def empty_gds(params=None):
        raw = _orig_q(params)
        raw["gds_bytes"] = b""
        return raw

    with mock.patch.object(dm, "_build_quantum_sc", empty_gds):
        p1 = dm.build_domain("quantum_sc")
    check("🔴 ⑧ 探针①: 量子域 GDS 伪造为空字节 ⇒ 真-GDS 判据必红",
          p1["gds"]["n_bytes"] == 0 and p1["gds"]["header_ok"] is False)

    _orig_e = dm._build_ecore
    def rejected_drc(params=None):
        raw = _orig_e(params)
        raw["drc"] = dict(raw["drc"], verdict="REJECT")
        return raw

    with mock.patch.object(dm, "_build_ecore", rejected_drc):
        p2 = dm.build_domain("ecore")
    check("🔴 ⑨ 探针②: ecore DRC 伪造成 REJECT ⇒ 双闸判据必红",
          p2["verdict"] == "REJECT" and p2["drc"]["verdict"] == "REJECT")

    with mock.patch.object(dm, "D4_DOMAINS", ("ecore", "quantum_sc", "ghost_domain")):
        p3 = set(dm.D4_DOMAINS) == set(EXPECTED_DOMAINS)
    check("🔴 ⑩ 探针③: 注册域塞入未接门禁的 ghost ⇒ 域完备判据必红", p3 is False)

    print()
    if fails:
        print(f"D4 扩面门禁: {len(fails)} FAIL :: {fails}")
        return 1
    print("D4 扩面门禁: ALL GREEN（域完备 + 真 GDS + 双闸 + 双向确定性 + 3 突变探针）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
