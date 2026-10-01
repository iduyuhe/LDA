# -*- coding: utf-8 -*-
"""LDA · D4 扩面案例卡门禁（W5-2 · /api/d4_demo · ecore / 量子侧）。

============================================================================
守什么（v0.9.172 · CI core 263→264）
----------------------------------------------------------------------------
案例卡三纪律（与 qchip/schip/pchip/ecore/accel 同族）：
  ① 只读可达：路由登记 GET_ROUTES · 不进 HEAVY_POST_PATHS · 免登录；
  ② 诚实边界：verdict 恒 DESIGN_BUDGET（非实测签核）· 层规声明为公开工艺近似 ·
     主张面无「流片/实测」宣称 · gaps 逐条登记且计数自洽；
  ③ 跨源一致：卡内逐域 GDS 字节数/sha256/verdict 与 `d4_domains` 现算逐位同源 ·
     前端（sec-d4 / runD4 / CASE_MAP / 按钮接线）齐 · API 参考含本端点。

🔴 突变探针（进程内 patch.object，防死断言）：
  ① 伪装 ACCEPT 的域事实（sha256 造假）⇒ 跨源一致判据必红；
  ② 主张面注入「流片验证」字样 ⇒ 诚实边界扫描必红；
  ③ 注入未接 onclick 的按钮 ⇒ 前端反向完备判据必红（血案 #18 防再犯）。
"""
from __future__ import annotations

import os
import re
import sys
import unittest.mock as mock

from lda_webui import d4case as dc
from lda_webui import routes as _routes

# 🔴 锚到 __file__ 而非 cwd 相对串：门禁不得依赖调用目录（CI 是 cwd=lda/ 跑的，
#   但本地/其他入口从仓库根跑会 FileNotFoundError —— 判据没跑起来 ≠ 判据通过）。
_FRONTEND = __file__.replace("\\", "/").rsplit("/", 1)[0] + "/lda_webui/static/index.html"

_RE_BTN_ID = re.compile(r'<button[^>]*?\sid="([A-Za-z0-9_]+)"')
_RE_WIRED = re.compile(r"\$\('([A-Za-z0-9_]+)'\)\.onclick")


def unwired_static_buttons(src: str) -> list:
    """页面有静态按钮但 JS 从未 $(id).onclick 接线（反向完备判据）。"""
    return sorted(set(_RE_BTN_ID.findall(src)) - set(_RE_WIRED.findall(src)))


def _unsynced(card: dict) -> list:
    """卡内域事实 vs `d4_domains` 现算：返回不同步的域（空表 = 逐位同源）。

    逐字段取 `.get()` 而非硬下标——被探针换掉的卡可能根本没有该域键，
    硬下标会抛 KeyError 而非「判据变红」（假红 ≠ 真判据）。
    """
    from lda_l2 import d4_domains as dm

    bad = []
    for d in dm.D4_DOMAINS:
        r = dm.deliver_report(d)                    # 对外标量面（含 sha256 摘要）
        f = card.get("domains", {}).get(d) or {}
        if not (f.get("verdict") == r["verdict"] == "ACCEPT"
                and f.get("sha256") == r["gds"]["sha256"]
                and f.get("n_bytes") == r["gds"]["n_bytes"]
                and f.get("n_elements") == r["n_elements"]):
            bad.append(d)
    return bad


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} :: {detail}")
            fails.append(name)

    print("=== LDA · D4 扩面案例卡门禁（/api/d4_demo）===")
    card = dc.case_card(use_cache=False)

    # —— ① 只读可达 ——
    check("①a 路由已登记 GET_ROUTES（/api/d4_demo）",
          "/api/d4_demo" in _routes.GET_ROUTES)
    check("①b 不进 HEAVY_POST_PATHS（免登录只读纪律）",
          not any("d4_demo" in str(x) for x in getattr(_routes, "HEAVY_POST_PATHS", [])))

    # —— ② 诚实边界 ——
    check("②a verdict 恒 DESIGN_BUDGET + 口径文案含非流片实测",
          card["verdict"] == "DESIGN_BUDGET" and "非流片实测" in card["verdict_label"])
    blob = repr(card["claim"]) + repr(card["honest_note"]) + repr(card["disclosure"])
    check("②b 主张面无「流片/实测」肯定表述 · 声明不报 TOPS（🔴 只扫肯定表述："
          "明文含「非实测签核/非流片结果」属否定式，不能当禁词扫）",
          not any(w in blob for w in ("已流片", "已实测", "流片验证", "实测验证"))
          and "非实测签核" in card["honest_note"]
          and "非流片结果" in card["honest_note"]
          and "不报 TOPS" in card["honest_note"])
    gd = next((g for g in card["gaps"] if g["id"] == "G-D"), {})
    check("②c gaps 计数自洽 + 逐条有说明（G-D 已闭合，其余仍是诚实边界）",
          card["gaps_total"] == len(card["gaps"]) == 4
          and gd.get("closed") is True
          and all(g.get("note") for g in card["gaps"])
          and sum(1 for g in card["gaps"] if g["closed"] is False) == 3,
          "gaps=%d 未闭合=%d" % (card["gaps_total"],
                                 sum(1 for g in card["gaps"] if g["closed"] is False)))
    check("②d honest_note 含公开工艺近似 + LLM 不进判决路径",
          "公开工艺近似" in card["honest_note"] and "LLM 不进判决路径" in card["honest_note"])

    # —— ③ 跨源一致 ——
    from lda_l2 import d4_domains as dm
    check("③a 卡内域列表 ≡ d4_domains 注册域（域完备反向）",
          set(card["domain_list"]) == set(dm.D4_DOMAINS))
    sync_bad = _unsynced(card)
    check("③b 卡内逐域字节数/sha256/verdict 与模块现算逐位同源",
          sync_bad == [], str(sync_bad))
    check("③c 逐域 sha256 为 64 位十六进制（确定性交付物标识）",
          all(re.fullmatch(r"[0-9a-f]{64}", card["domains"][d]["sha256"])
              for d in card["domain_list"]))
    check("③d 征程/结论/缺口三段在场（6 里程碑 · 6 结论 · 4 缺口）",
          len(card["milestones"]) == 6 and len(card["findings"]) == 6
          and len(card["gaps"]) == 4)

    # —— 前端三件 + 接线 ——
    src = open(_FRONTEND, encoding="utf-8").read()
    check("③e 前端 sec-d4 段 + runD4 按钮 + 本端点引用齐",
          'id="sec-d4"' in src and "runD4" in src and "/api/d4_demo" in src)
    check("③f 前端 hash 自动运行映射含 #sec-d4",
          '"#sec-d4": "runD4"' in src)
    check("③g 全站反向完备：每个静态按钮 id 都有 $()*.onclick 接线",
          unwired_static_buttons(src) == [], f"无接线: {unwired_static_buttons(src)}")
    # 🔴 前端取值路径门禁（血案 #19）：renderD4 访问的**属性名**必须在卡 JSON 里真存在。
    #   本次就是靠浏览器实测抓出「前端读 f.gds.n_bytes，而域事实是扁平结构 ⇒ 渲染成 -」。
    #   🔴 判据咬语义不咬字面：JS 里变量可改名（f./s.），只抽「访问了哪些属性名」。
    js = src[src.find("function renderD4(d)"): src.find("if($('runD4'))")]
    # 🔴 先剥注释：注释里的示例串（如「曾误写成 f.gds.n_bytes」）会被属性扫描当真，
    #   造成自己写的判据被自己绊倒（该死的咬文嚼字，但必须机器化）
    js_code = "\n".join(ln.split("//")[0] for ln in js.splitlines())
    props = set(re.findall(r"\b(?:f|s)\.([A-Za-z_][A-Za-z0-9_]*)", js_code))
    facts_keys = set()
    for d in card["domain_list"]:
        v = card["domains"][d]
        facts_keys |= set(v)
        for nest in ("drc", "lvs"):
            if isinstance(v.get(nest), dict):
                facts_keys |= {nest + "." + k for k in v[nest]}
    missing_js = sorted(p for p in props if p not in facts_keys and p not in ("length",))
    check("③i renderD4 访问的属性名逐键存在于卡 JSON（防 f.gds.* 式幽灵路径）",
          not missing_js, f"前端读但卡里无: {missing_js}")
    check("③j 域事实为扁平结构（无嵌套 gds 键，前端按 f.* 取值）",
          ".gds." not in js_code
          and {"label", "verdict", "n_bytes", "sha256", "n_elements", "drc", "lvs"}
          <= facts_keys)

    # —— ③k/③l 下载闭环（G-D 收口本体：卡里给的 URL 必须真能下到同一份字节）——
    dl_bad = []
    for d in card["domain_list"]:
        f = card["domains"][d]
        body, meta = dm.deliver_download(d)
        if not (f.get("download_url") == "/api/d4_gds?domain=%s" % d
                and body is not None
                and meta.get("sha256") == f.get("sha256")
                and meta.get("n_bytes") == f.get("n_bytes")
                and meta.get("verdict") == f.get("verdict")):
            dl_bad.append(d)
    check("③k 逐域下载端点可真下载且 sha256 ≡ 卡内登记值（交付闭环互证）",
          dl_bad == [], f"不同步: {dl_bad}")
    # 🔴 锚 __file__ 同级（不是 _FRONTEND 往上两级——那会落到 lda_webui/ 下，
    #   判据读了个不存在的文件 ⇒ `os.path.exists` 短路成空串 ⇒ 假绿而非真绿）
    _api_smoke = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "run_webui_api_smoke.py")
    _api_src = open(_api_smoke, encoding="utf-8").read() if os.path.exists(_api_smoke) else ""
    check("③l 下载路由已登记 GET_ROUTES + 已在 run_webui_api_smoke.BINARY_GET 豁免"
          "（二进制响应不被通用 GET 循环误判）",
          "/api/d4_gds" in _routes.GET_ROUTES
          and '"d4_gds_ecore"' in _api_src and '"/api/d4_gds?domain=ecore"' in _api_src)

    # —— 缓存纪律 ——
    check("③h 同配置缓存命中（同一对象 · 秒回）", dc.case_card() is dc.case_card())

    # —— 🔴 突变探针 ——
    # 🔴 探针必须返回**域事实 dict**（不是整卡）：返回整卡会让 `case_card` 再套一层，
    #   判据红起来是因为「域根本不存在」而非「sha256 造假」——理由不对的探针是假探针。
    def fabricated_facts(*a, **kw):
        return {d: dict(v, verdict="ACCEPT", sha256="0" * 64)
                for d, v in card["domains"].items()}

    with mock.patch.object(dc, "_domain_facts", fabricated_facts):
        bad_card = dc.case_card(use_cache=False)
    fake_bad = _unsynced(bad_card)
    check("🔴 ④ 探针①: 域事实被换成伪造 sha256 ⇒ 跨源一致判据必红",
          fake_bad == list(dm.D4_DOMAINS), str(fake_bad))

    def fabricated_note(*a, **kw):
        bad = dict(card)
        bad["honest_note"] = card["honest_note"] + "（已流片验证）"
        return bad

    with mock.patch.object(dc, "case_card", fabricated_note):
        bad2 = dc.case_card(use_cache=False)
    check("🔴 ⑤ 探针②: honest_note 注入「流片验证」⇒ 诚实边界扫描必红",
          "流片" in repr(bad2["honest_note"]))

    tampered = src + '\n<button class="btn" id="runD4Broken">探针</button>\n'
    check("🔴 ⑥ 探针③: 注入无接线按钮 runD4Broken ⇒ 前端反向完备判据必红",
          unwired_static_buttons(tampered) == ["runD4Broken"])

    # 探针④：卡里把下载 URL 指向未注册域 ⇒ ③k 闭环互证必红
    def wrong_dl(*a, **kw):
        return {d: dict(v, download_url="/api/d4_gds?domain=ghost")
                for d, v in card["domains"].items()}

    with mock.patch.object(dc, "_domain_facts", wrong_dl):
        bad3 = dc.case_card(use_cache=False)
    wrong_domains = [d for d in bad3["domain_list"]
                     if bad3["domains"][d].get("download_url")
                     != "/api/d4_gds?domain=%s" % d]
    check("🔴 ⑦ 探针④: 域事实下载 URL 指向未注册域 ⇒ 下载闭环判据必红",
          wrong_domains == list(bad3["domain_list"]), str(wrong_domains))

    print()
    if fails:
        print(f"D4 案例卡门禁: {len(fails)} FAIL :: {fails}")
        return 1
    print("D4 案例卡门禁: ALL GREEN（只读可达 + 诚实边界 + 跨源一致 + 接线反向完备 + 3 突变探针）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
