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
  ⑦ LOQC 的枚举参数被静默忽略 ⇒ 「换参数 sha 必变」判据必红；
  ⑧ 光子互联域 GDS 伪造为空字节 ⇒ 真-GDS 判据必红。
"""
from __future__ import annotations

import hashlib
import sys
import unittest.mock as mock

from lda_l2 import d4_domains as dm
from lda_l2.ecore import elayers as EL                 # 层号单一真源（L_DIFF 等）
from lda_l2.ecore import layout as EL_LAYOUT
from lda_webui import d4case as d4c

# 🔴 门禁显式表（反向完备的锚：D4_DOMAINS 必须与本表逐位相等）
EXPECTED_DOMAINS = ("ecore", "quantum_sc", "loqc", "photonic_interconnect",
                    "oi_transceiver")


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
    # ④d：oi_transceiver 的**通道数**必须真进构建链（同 ④c 的反向完备思路）——
    # 若 `_build_oi_transceiver` 把 n_lanes 静默丢掉（恒建 8 通道），两个规模的
    # 请求会产出同一份字节 ⇒ 交付「假货」还好看（最难看的假绿形态）。
    _t1 = dm.build_domain("oi_transceiver")
    _t2 = dm.build_domain("oi_transceiver", {"n_lanes": 4})
    _t3 = dm.build_domain("oi_transceiver", {"n_lanes": 12})
    check("④d oi_transceiver 换通道数 sha256 必须变化（反「n_lanes 被静默忽略」）",
          _t1["gds"]["sha256"] != _t2["gds"]["sha256"]
          and _t1["gds"]["sha256"] != _t3["gds"]["sha256"]
          and _t2["gds"]["sha256"] != _t3["gds"]["sha256"],
          "恒等 sha ⇒ 通道数被丢弃")

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
    # ⑦c：photonic_interconnect 专属诚实注记必须带上（K×N WDM 网格 + 未流片未实测）
    _oi_h = dm.deliver_report("photonic_interconnect").get("honest_notes", "")
    check("⑦c photonic_interconnect 专属诚实注记在场（WDM 网格 + 未流片未实测）",
          "WDM" in _oi_h and "未流片" in _oi_h and "未实测" in _oi_h, _oi_h[-120:])
    # ⑦d：oi_transceiver 专属诚实注记必须带上（片外 fiber + MMIC 自成像未建模 +
    #     「非计算核不报能效」——这三条是该域**独有**的口径，不能只靠全局一份兜底）
    _tr_h = dm.deliver_report("oi_transceiver").get("honest_notes", "")
    check("⑦d oi_transceiver 专属诚实注记在场（片外 fiber 不落版图 + MMIC 自成像未建模 + 非计算核）",
          "片外" in _tr_h and "自成像" in _tr_h and "非计算核" in _tr_h, _tr_h[-140:])

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
    # ⑩f：oi_transceiver 限幅（免登录端点 ⇒ 通道数必须封顶；合法值放行 + 附件名可辨）
    _tb, _tm = dm.deliver_download("oi_transceiver", {"n_lanes": 99})
    _ob, _om = dm.deliver_download("oi_transceiver", {"n_lanes": 4})
    _xb, _xm = dm.deliver_download("oi_transceiver", {"lanes": 4})
    check("⑩f oi_transceiver 限幅：越界/非登记键拒绝，合法值放行且附件名可辨",
          _tb is None and _tm.get("ok") is False and bool(_tm.get("errors"))
          and _xb is None and _xm.get("ok") is False
          and bool(_ob) and _om.get("verdict") == "ACCEPT"
          and _om.get("filename") == "oi_transceiver_4x200G.gds",
          "越界=%s 非登记=%s 合法名=%s" % (str(_tm.get("errors"))[:60],
                                          str(_xm.get("errors"))[:60],
                                          _om.get("filename")))

    # —— ⑪ 未知域下载快失败 ——
    _gb, _gm = dm.deliver_download("ghost_domain")
    check("⑪ 未知域下载快失败（字节→None + 报错说明含该域 + 给出已注册域白名单）",
          dm.deliver_gds_bytes("ghost_domain") is None
          and _gb is None and _gm.get("ok") is False
          and "ghost_domain" in "".join(_gm.get("errors") or [])
          and list(dm.D4_DOMAINS) == list(_gm.get("registered") or []),
          str(_gm)[:160])

    # —— ⑬ 层规/几何口径单一真源（G-P / G-B 机器化的第一半）——
    # 🔴 血案 #10 的极端形态：案例卡 disclosure 三字段此前是**第二份手写副本**，且
    #   全仓无任何消费 ⇒ 改成「已通过 Foundry 层规」也全绿。现改为派生
    #   LAYOUT_DISCLOSURE 的短口径键，结构上不可能漂移；跨源再由 honest_note / GAPS note
    #   咬住（只比同源不算守：同源必然相等 ⇒ 探针恒绿）。
    _ld = EL_LAYOUT.LAYOUT_DISCLOSURE
    _card = d4c.case_card()
    _dis = _card["disclosure"]
    _gp = next(g for g in _card["gaps"] if g["id"] == "G-P")["note"]
    _gb = next(g for g in _card["gaps"] if g["id"] == "G-B")["note"]
    check("⑬ 层规/几何口径单一真源（LAYOUT_DISCLOSURE ⇄ 案例卡 disclosure ⇄ honest_note ⇄ GAPS）",
          _dis["layer_rules"] == _ld["layer_rules_short"]
          and _dis["drc_precision"] == _ld["geom_short"]
          and _dis["signoff_class"] == _ld["signoff_short"]
          and "公开工艺近似" in _ld["layer_rules_short"]
          and "非 Foundry PDK" in _ld["layer_rules_short"]
          and "bbox" in _ld["geom_short"]
          and "公开工艺近似" in _card["honest_note"]
          and "bbox" in _card["honest_note"]
          and "公开工艺近似" in _gp and "bbox" in _gb,
          "disclosure=%s short=%s" % (_dis.get("layer_rules"), _ld["layer_rules_short"]))

    # —— ⑭ bbox 保守性实证（G-B 的第二半：从「一句免责」升级为「有机器守着的事实」）——
    # 两条算例都走**真实** run_edrc（不 mock 几何）：
    #   A 真重叠矩形（不同 net）⇒ 必报                ⇒ 零漏报（安全侧：真冲突必被抓）
    #   B 两个 L 形：外接 bbox 重叠、本体不相交
    #     ⇒ bbox 报「间距 0.000」而精确多边形最小间距 0.5 µm > 阈值 0.4 µm（精确判定
    #       应 ACCEPT）⇒ 证明 bbox 宁可多报（保守）而非漏报。
    _lim = {"diff_min_width_um": 0.1, "diff_min_space_um": 0.4, "diff_min_area_um2": 0.1}
    _A = EL_LAYOUT.run_edrc([
        {"kind": "boundary", "layer": EL.L_DIFF, "net": "N1",
         "rings_um": [[(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]]},
        {"kind": "boundary", "layer": EL.L_DIFF, "net": "N2",
         "rings_um": [[(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]]},
    ], _lim)
    _B = EL_LAYOUT.run_edrc([
        {"kind": "boundary", "layer": EL.L_DIFF, "net": "M1",
         "rings_um": [[(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]]},                 # Γ 形：底横条 + 左竖条
        {"kind": "boundary", "layer": EL.L_DIFF, "net": "M2",
         "rings_um": [[(3.5, 2.5), (7.5, 2.5), (7.5, 6.5), (5.5, 6.5),
                       (5.5, 4.5), (3.5, 4.5)]]},                                          # ⌐ 形：底横条 + 右竖条
    ], _lim)
    _bd = " ".join(v.get("detail", "") for v in _B["violations"])
    check("⑭ bbox 保守性实证（真重叠必报 + bbox 多报不会漏报）",
          _A["verdict"] == "REJECT" and _B["verdict"] == "REJECT"
          and "间距 0.000" in _bd
          and 0.5 > _lim["diff_min_space_um"] > 0.0,
          "A=%s B=%s detail=%s" % (_A["verdict"], _B["verdict"], _bd[:90]))

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

    # 探针⑧：光子互联域 GDS 伪造为空字节 ⇒ ② 真-GDS 判据必红（与 LOQC 同源逻辑，
    # 但独立验证新域「空字节会被抓住」，而非靠 LOQC 探针顺带覆盖）。
    _orig_w = dm._build_photonic_interconnect

    def empty_wdm(params=None):
        raw = _orig_w(params)
        raw["gds_bytes"] = b""
        return raw

    with mock.patch.object(dm, "_build_photonic_interconnect", empty_wdm):
        p8w = dm.build_domain("photonic_interconnect")
    check("🔴 ⑯ 探针⑧: 光子互联域 GDS 伪造为空字节 ⇒ ② 真-GDS 判据必红",
          p8w["gds"]["n_bytes"] == 0 and p8w["gds"]["header_ok"] is False)

    # 探针⑧：枚举参数被静默丢弃（构建时不管 layout_mode）⇒ ④c 必红
    # 🔴 这类「参数吞掉不报错」的假绿最难看：交付的仍是 ACCEPT 真 GDS，只是
    # 永远默认布局——④c 是唯一能咬住它的判据，故探针必须造出「同参数不同请求」
    # 产出同字节的现象。
    def drop_enum(params=None):
        p = dict(params or {})
        return _orig_l({"n": p.get("n", 4)})          # 🔴 故意丢掉 layout_mode

    with mock.patch.object(dm, "_build_loqc", drop_enum):
        p8 = dm.build_domain("loqc", {"layout_mode": "grid2d"})
    check("🔴 ⑰ 探针⑨: LOQC 枚举参数被静默丢弃 ⇒ ④c『换枚举 sha 必变』必红",
          p8["gds"]["n_bytes"] > 0 and p8["verdict"] == "ACCEPT"
          and p8["gds"]["sha256"] == dm.build_domain("loqc")["gds"]["sha256"],
          "grid2d 却与默认 serpentine 同 sha ⇒ 枚举被吞")

    # 探针⑨：层规短口径被改成「已通过 Foundry 标定」⇒ ⑬ 必红（防免责措辞被悄悄改没）
    _orig_ld = dict(EL_LAYOUT.LAYOUT_DISCLOSURE)
    try:
        EL_LAYOUT.LAYOUT_DISCLOSURE["layer_rules_short"] = "Foundry PDK 层规（真实标定）"
        _p_card = d4c.case_card()
        _p_short = EL_LAYOUT.LAYOUT_DISCLOSURE["layer_rules_short"]
        # 🔴 只打短口径一侧：长版 rules / honest_note / GAPS note 都不跟着变 ⇒
        #    若判据 ⑬ 真的咬住「自然文本侧」而非「同源相等」，此处必红（真实分歧）。
        _p_ok = (_p_card["disclosure"]["layer_rules"] == _p_short
                 and "公开工艺近似" in _p_short)
    finally:
        EL_LAYOUT.LAYOUT_DISCLOSURE.clear()
        EL_LAYOUT.LAYOUT_DISCLOSURE.update(_orig_ld)
    check("🔴 ⑰ 探针⑨: 层规短口径被改成『Foundry 真实标定』 ⇒ ⑬『自然文本侧』必红",
          _p_ok is False, "短口径已变但判据却绿 ⇒ ⑬ 咬的是同源相等，是假判据")

    # 探针⑩：oi_transceiver 域 GDS 伪造为空字节 ⇒ ② 真-GDS 判据必红
    # （与探针⑦/⑧ 同族，但**独立**验证新域「空字节会被抓住」，而非靠光子互联域顺带覆盖）
    _orig_t = dm._build_oi_transceiver

    def empty_trx(params=None):
        raw = _orig_t(params)
        raw["gds_bytes"] = b""
        return raw

    with mock.patch.object(dm, "_build_oi_transceiver", empty_trx):
        p10t = dm.build_domain("oi_transceiver")
    check("🔴 ⑱ 探针⑩: 收发器域 GDS 伪造为空字节 ⇒ ② 真-GDS 判据必红",
          p10t["gds"]["n_bytes"] == 0 and p10t["gds"]["header_ok"] is False)

    # 探针⑪：收发器的**通道数被静默丢弃**（恒建 8 通道）⇒ ④d 必红
    # 与探针⑨（枚举被吞）同族但独立：证明 ④d 真能咬住「交付的仍是 ACCEPT 真 GDS、
    # 只是永远默认规模」这类最难看假绿。
    def drop_lanes(params=None):
        return _orig_t({})                          # 🔴 故意丢掉 n_lanes

    with mock.patch.object(dm, "_build_oi_transceiver", drop_lanes):
        p11t = dm.build_domain("oi_transceiver", {"n_lanes": 4})
    check("🔴 ⑲ 探针⑪: 收发器通道数被静默丢弃 ⇒ ④d『换规模 sha 必变』必红",
          p11t["gds"]["n_bytes"] > 0 and p11t["verdict"] == "ACCEPT"
          and p11t["gds"]["sha256"] == dm.build_domain("oi_transceiver")["gds"]["sha256"],
          "n_lanes=4 却与默认同 sha ⇒ 通道数被吞")

    print()
    if fails:
        print(f"D4 扩面门禁: {len(fails)} FAIL :: {fails}")
        return 1
    print("D4 扩面门禁: ALL GREEN"
          "（域完备 + 真 GDS + 双闸 + 双向确定性 + 下载互证 + 限幅 + 11 突变探针）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
