# -*- coding: utf-8 -*-
"""LDA · D4 交付闭环扩面门禁（W5-1 · ecore / 量子侧 · 2026-10-02）。

============================================================================
守什么（v0.9.173 · CI core 263）
----------------------------------------------------------------------------
W2 已实测贯通光子侧「设计 → GDS → 签核 → 下载」。本门禁守的是**扩面后的三条新产线**
（电子 ecore 交叉阵列 + 超导 transmon 阵列 + 光量子 LOQC 可编程 MZI 网格）不掉回
「能算对但交不出去」：

  ① 域完备：D4_DOMAINS 与门禁显式表逐位相等（🔴 反向完备——新域必须进门禁，
     否则静默进盲区）；
  ② 真 GDS：字节非空 + 头魔数 `00 06 00 02`（与光子 D4 同口径）+ sha256 形状；
  ③ 双闸 ACCEPT：DRC + LVS 皆 ACCEPT 且整体 verdict 与之咬合（不看单一闸）；
  ④ 确定性：同参数两次 sha256 逐位一致，**且不同参数必须不同**
     （防「常数假确定性」：恒定 sha256 会同时骗过两侧判据）；
  ⑤ 对外只给标量：deliver_report 不含 gds 字节面；
  ⑥ 未知域快失败：不注册即红，不静默 fallback；
  ⑦ 诚实边界：honest_notes 在场且含「非实测」声明、无 TOPS 主张；
  ⑧ 对外限幅：每个注册域都有条目，且**枚举型参数**（loqc.layout_mode）必须
     命中白名单（防「传了不存在的布局模式却被静默当成默认 ⇒ 交付假货」）。

🔴 突变探针（进程内 patch.object，防死断言）：
  ① 量子域 GDS 伪造为空字节 ⇒ 真-GDS 判据必红；
  ② ecore 域 DRC 伪造成 REJECT ⇒ 双闸判据必红；
  ③ 注册域里塞入 ghost 域（模拟「新域没接门禁」）⇒ 域完备判据必红；
  ④ 字节面被换成「另一份真字节」⇒ 下载⇄标量互证必红；
  ⑤ 下载取到与报告不同的 raw（DRC 不一致）⇒ 元信息同口径必红；
  ⑥ LOQC 域 GDS 伪造为空字节 ⇒ 真-GDS 判据必红；
  ⑦ LOQC 的枚举参数被静默忽略 ⇒ 「换参数 sha 必变」判据必红。
"""
from __future__ import annotations

import hashlib
import sys
import unittest.mock as mock

from lda_l2 import d4_domains as dm

# 🔴 门禁显式表（反向完备的锚：D4_DOMAINS 必须与本表逐位相等）
EXPECTED_DOMAINS = ("ecore", "quantum_sc", "loqc")


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
    # ④c：LOQC 的**枚举型参数**（layout_mode）也必须真正进构建链——
    # 若 `_build_loqc` 把它静默丢掉，两种布局会产出同一份字节 ⇒ 交付「假货」还好看。
    _l1 = dm.build_domain("loqc")
    _l2 = dm.build_domain("loqc", {"layout_mode": "grid2d"})
    _l3 = dm.build_domain("loqc", {"n": 8})
    check("④c loqc 换枚举参数/换模数 sha256 必须变化（反「枚举被静默忽略」）",
          _l1["gds"]["sha256"] != _l2["gds"]["sha256"]
          and _l1["gds"]["sha256"] != _l3["gds"]["sha256"]
          and _l2["gds"]["sha256"] != _l3["gds"]["sha256"],
          "恒等 sha ⇒ 枚举参数被丢弃")

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
    # ⑦b：逐域专属注记必须真的带上了（「逐域口径不同 ⇒ 不能只挂全局一份」）
    _loqc_h = dm.deliver_report("loqc").get("honest_notes", "")
    check("⑦b loqc 专属诚实注记在场（展开布局非压实芯片 + 未流片未实测）",
          "展开" in _loqc_h and "未流片" in _loqc_h, _loqc_h[-80:])

    # —— ⑧ 下载字节面 ⇄ 标量面互证（G-D 收口本体）——
    for d in dm.D4_DOMAINS:
        rep = dm.build_domain(d)
        b1, b2 = dm.deliver_gds_bytes(d), dm.deliver_gds_bytes(d)
        sha1, sha2 = hashlib.sha256(b1 or b""), hashlib.sha256(b2 or b"")
        check(f"⑧ {d}: 下载字节面与标量面互证（两次逐位一致 + sha ≡ build_domain）",
              bool(b1) and bool(b2) and sha1.digest() == sha2.digest()
              and sha1.hexdigest() == rep["gds"]["sha256"]
              and len(b1) == rep["gds"]["n_bytes"]
              and bytes(b1[:4]) == dm.GDS_HEADER_MAGIC,
              f"sha(字节)={sha1.hexdigest()[:12]} vs 报告={str(rep['gds']['sha256'])[:12]}")

    # —— ⑨ 下载元信息自洽（路由层只挂头，不重算摘要）——
    for d in dm.D4_DOMAINS:
        body, meta = dm.deliver_download(d)
        rep = dm.build_domain(d)
        check(f"⑨ {d}: deliver_download 元信息自洽（附件名/头 sha/双闸与报告同口径）",
              bool(body) and meta.get("ok") is True
              and str(meta.get("filename", "")).endswith(".gds")
              and meta["sha256"] == hashlib.sha256(body).hexdigest()
              and meta["n_bytes"] == len(body)
              and meta.get("verdict") == rep.get("verdict")
              and meta.get("drc") == rep.get("drc") and meta.get("lvs") == rep.get("lvs"),
              f"meta={ {k: meta.get(k) for k in ('filename','sha256','verdict')} }")

    # —— ⑩ 对外限幅（免登录端点可被单请求 OOM，必须硬拦）——
    check("⑩a 限幅表反向完备：每个注册域都有 DOMAIN_PARAM_LIMITS 条目（新域不进盲区）",
          set(dm.DOMAIN_PARAM_LIMITS) == set(dm.D4_DOMAINS),
          "限幅=%s 注册=%s" % (sorted(dm.DOMAIN_PARAM_LIMITS), sorted(dm.D4_DOMAINS)))
    _shapes_ok = all(isinstance(v, tuple) and len(v) == 2
                     for lim in dm.DOMAIN_PARAM_LIMITS.values() for v in lim.values())
    _enum_ok = all(isinstance(v[0], str) and isinstance(v[1], str)
                   for lim in dm.DOMAIN_PARAM_LIMITS.values()
                   for k, v in lim.items() if k == "layout_mode")
    _num_ok = all(isinstance(v[0], (int, float)) and isinstance(v[1], (int, float))
                  for lim in dm.DOMAIN_PARAM_LIMITS.values()
                  for k, v in lim.items() if k != "layout_mode")
    check("⑩c 限幅表形状合法：每条目都是 2 元组，且枚举键两端为 str / 数值键两端为数值",
          _shapes_ok and _enum_ok and _num_ok,
          "shapes=%s enum=%s num=%s" % (_shapes_ok, _enum_ok, _num_ok))
    for badp in ({"n": "999999"}, {"n": "abc"}, {"junk": "1"}, {"n": "0"}):
        body, meta = dm.deliver_download("ecore", badp)
        check(f"⑩b 越界/非数值/非登记键 {badp} ⇒ 拒绝（ok=False + 错误说明）",
              body is None and meta.get("ok") is False and bool(meta.get("errors")),
              str(meta)[:120])
    # ⑩d：枚举型参数白名单反向（loqc）——报文必须说清是「不在白名单」而非「不是数」
    _enum_bad = ({"layout_mode": "bogus"}, {"layout_mode": 1}, {"layout_mode": True})
    for badp in _enum_bad:
        body, meta = dm.deliver_download("loqc", badp)
        check(f"⑩d {badp} ⇒ 白名单拒绝（报文点名『不在白名单』）",
              body is None and meta.get("ok") is False
              and "不在白名单" in "".join(meta.get("errors") or []),
              str(meta.get("errors"))[:120])
    _body_ok, _meta_ok = dm.deliver_download("loqc", {"layout_mode": "grid2d", "n": 6})
    check("⑩e loqc 合法枚举参数放行（出真字节 + 附件名带布局模式）",
          bool(_body_ok) and str(_meta_ok.get("filename", "")).startswith("loqc_mzi_")
          and "grid2d" in str(_meta_ok.get("filename", ""))
          and _meta_ok.get("verdict") == "ACCEPT",
          str(_meta_ok)[:120])

    # —— ⑪ 未知域下载快失败 ——
    _gb, _gm = dm.deliver_download("ghost_domain")
    check("⑪ 未知域下载快失败（字节→None + 报错说明含该域 + 给出已注册域白名单）",
          dm.deliver_gds_bytes("ghost_domain") is None
          and _gb is None and _gm.get("ok") is False
          and "ghost_domain" in "".join(_gm.get("errors") or [])
          and list(dm.D4_DOMAINS) == list(_gm.get("registered") or []),
          str(_gm)[:160])

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
        p10 = set(dm.DOMAIN_PARAM_LIMITS) == set(dm.D4_DOMAINS)
    check("🔴 ⑪ 探针③: 注册域塞入未接门禁的 ghost ⇒ 域完备判据必红", p3 is False)
    check("🔴 ⑫ 探针④: 限幅表掉一个域 ⇒ 反向完备判据必红（新域静默进盲区）", p10 is False)

    # 探针⑤：字节面被换成「另一份真字节」⇒ ⑧ 互证判据必红（不只看是否为空）
    _orig_e2 = dm._build_ecore
    def swapped_gds(params=None):
        raw = _orig_e2(params)
        raw["gds_bytes"] = raw["gds_bytes"] + b"\x00\x00\x00\x00"
        return raw
    with mock.patch.object(dm, "_build_ecore", swapped_gds):
        _sb, _sm = dm.deliver_download("ecore")
    check("🔴 ⑬ 探针⑤: 字节面被换成另一份真字节 ⇒ 下载⇄标量互证必红",
          _sb is None or _sm.get("sha256") != dm.build_domain("ecore")["gds"]["sha256"])

    # 探针⑥：让**同一次进程内**的两次构建产出不同 DRC ⇒ ⑨「下载元信息 ≡ 报告」
    # 判据必红。
    # 🔴 踩坑记录：最初打 `dm._report_of`（恒 ACCEPT）——但 build_domain 与
    #    deliver_download 都走它 ⇒ 打桩后两边同值 ⇒ 判据恒绿、探针恒绿（假绿）。
    #    ⇒ 探针必须制造**真实分歧**（同一 fn 第二次调用返回不同 raw），
    #      否则测的是「两个函数是否长得一样」，不是「是否同一条构建链」。
    _calls = {"n": 0}
    _orig_bf = dm._builder_for

    def flaky_builder(domain):
        fn_inner = _orig_bf(domain)

        def one_shot(params=None):
            _calls["n"] += 1
            raw = fn_inner(params)
            if _calls["n"] > 1:                       # 第二次构建 ⇒ DRC 伪造成 REJECT
                raw = dict(raw, drc=dict(raw.get("drc") or {}, verdict="REJECT"))
            return raw
        return one_shot

    _true = dm.build_domain("ecore")                 # 先跑：真 raw（DRC ACCEPT）
    _calls["n"] = 1
    with mock.patch.object(dm, "_builder_for", flaky_builder):
        _db, _dm_ = dm.deliver_download("ecore")     # 再跑：第 2 次 ⇒ REJECT
    check("🔴 ⑭ 探针⑥: 下载与报告取到不同 raw（DRC 不一致）⇒ ⑨ 元信息同口径必红",
          _db is not None and _dm_.get("drc", {}).get("verdict")
          != _true.get("drc", {}).get("verdict"),
          "download.drc=%s vs report.drc=%s" % (_dm_.get("drc"), _true.get("drc")))

    # 探针⑦：LOQC 域 GDS 伪造为空字节 ⇒ ② 真-GDS 判据必红
    _orig_l = dm._build_loqc

    def empty_loqc(params=None):
        raw = _orig_l(params)
        raw["gds_bytes"] = b""
        return raw

    with mock.patch.object(dm, "_build_loqc", empty_loqc):
        p7 = dm.build_domain("loqc")
    check("🔴 ⑮ 探针⑦: LOQC 域 GDS 伪造为空字节 ⇒ ② 真-GDS 判据必红",
          p7["gds"]["n_bytes"] == 0 and p7["gds"]["header_ok"] is False)

    # 探针⑧：枚举参数被静默丢弃（构建时不管 layout_mode）⇒ ④c 必红
    # 🔴 这类「参数吞掉不报错」的假绿最难看：交付的仍是 ACCEPT 真 GDS，只是
    # 永远默认布局——④c 是唯一能咬住它的判据，故探针必须造出「同参数不同请求」
    # 产出同字节的现象。
    def drop_enum(params=None):
        p = dict(params or {})
        return _orig_l({"n": p.get("n", 4)})          # 🔴 故意丢掉 layout_mode

    with mock.patch.object(dm, "_build_loqc", drop_enum):
        p8 = dm.build_domain("loqc", {"layout_mode": "grid2d"})
    check("🔴 ⑯ 探针⑧: LOQC 枚举参数被静默丢弃 ⇒ ④c『换枚举 sha 必变』必红",
          p8["gds"]["n_bytes"] > 0 and p8["verdict"] == "ACCEPT"
          and p8["gds"]["sha256"] == dm.build_domain("loqc")["gds"]["sha256"],
          "grid2d 却与默认 serpentine 同 sha ⇒ 枚举被吞")

    print()
    if fails:
        print(f"D4 扩面门禁: {len(fails)} FAIL :: {fails}")
        return 1
    print("D4 扩面门禁: ALL GREEN"
          "（域完备 + 真 GDS + 双闸 + 双向确定性 + 下载互证 + 限幅 + 8 突变探针）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
