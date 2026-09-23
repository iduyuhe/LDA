"""v0.9.130 P1-T1.1 · 「设计包 → GDS 贯通」smoke（指标 M2 · 可交付 D4 第一条）。

验证 `lda_webui.app` 的两个新端点函数（真身，非副本）——

  `run_design_tapeout(payload)`  POST /api/design_tapeout
  `run_design_gds(query)`        GET  /api/design_gds（**唯一二进制响应端点**）

即「UI 一次点击 ⇒ 可下载 .gds + DRC/LVS 签核报告」，把 P1-T1.1 的两条验收判据
钉成判据：

  ① **可下载 .gds + 双闸签核**：芯片级 `verdict == ACCEPT`（DRC 全过 + LVS ACCEPT
     + G4 几何回提零违规），且 `gds.available` 且字节数 > 0
  ② **报告与 /api/tapeout 同源（不得双口径）**：`resp["tapeout"]` 与
     `run_tapeout_check({"devices": {kind: params}})` 的 **canonical JSON
     逐字节相等**（同一函数、同一入参）

外加 6 组补充判据：

  ③ **下载与报告同一来源**：从响应 `gds.download_url` 取回 query（**不手写**）
     ⇒ `run_design_gds` 重建的字节 sha256 == 报告登记 sha256；两次调用同值
     （无状态确定性）；改 `R` ⇒ 变（非常量）；改 `name` ⇒ **不变**
     （文件名不得污染几何）；改 `wg` ⇒ 变（全局参数真的进链路）
  ④ **桥接正确**：`engine_kind=engine_ringresonator{R_um:10}` 与
     `kind=RingResonator{R:10}` 产出**同一份 GDS**（sha256 相等）
  ⑤ **诚实拒绝**：排除项 / 不可桥接 / 越界 / 非数 / 多器件 / 空 payload /
     下载端无 kind / 下载端非数 / 下载端未知 kind —— 每条都 `ok=False` 或
     返回 `(None, meta)` 且**理由指名**，绝不返回空文件或半成品
  ⑥ **诚实边界**：honest_notes 含 5 条关键边界（含「两条路径键检查强度不同」
     与「declared > checked 是已知边界」）；**每个拒绝分支也必须带边界**；
     并实测「加未知键 ⇒ GDS sha256 不变」把「直连路径静默忽略无效键」钉死
  ⑦ **红线**：T1.1 源码段零 LLM 引用（判决全死标量）
  ⑧ **接线完备**：routes.py 三表登记 + `h_design_gds` 是二进制（`body=` +
     octet-stream + 失败 400）；index.html 六个接线名齐 + 前端真的送
     `engine_kind` 口径；`run_webui_api_smoke` 把该端点登记进 `BINARY_GET`
     （豁免必须配专项断言，不得只豁免）

运行：python run_design_tapeout_smoke.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from urllib.parse import parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_design import goal_build as gb            # noqa: E402
from lda_harness.smoke_kit import make_check       # noqa: E402
from lda_webui import app                          # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

_REPO = os.path.dirname(_HERE)
_KIND = "RingResonator"
_PARAMS = {"R": 10.0}


def _canon(obj):
    """canonical JSON（排序键；同源断言用，逐字节比较）。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _sha(b):
    return hashlib.sha256(b or b"").hexdigest()


def _payload(params=None, **kw):
    p = {"kind": _KIND, "params": dict(_PARAMS if params is None else params)}
    p.update(kw)
    return p


def _section(src, start_marker):
    """取源码中一段顶层区域（start_marker → 下一个顶层 def 之前）。"""
    i0 = src.index(start_marker)
    i1 = src.index("\ndef ", i0)
    return src[i0:i1]


def main() -> int:                                  # noqa: C901
    # ---------------- ① 可下载 .gds + 双闸签核 ----------------
    t0 = time.time()
    resp = app.run_design_tapeout(_payload(name="d1"))
    dt = time.time() - t0
    summ = (resp.get("chip") or {}).get("summary") or {}
    check("① POST 设计包 ⇒ ok（芯片级双闸 ACCEPT）",
          resp.get("ok") is True, f"ok={resp.get('ok')} errors={resp.get('errors')}")
    check("① chip.verdict == ACCEPT",
          (resp.get("chip") or {}).get("verdict") == "ACCEPT",
          f"verdict={(resp.get('chip') or {}).get('verdict')}")
    check("① DRC 全过 + LVS ACCEPT",
          summ.get("drc_all_pass") is True and summ.get("lvs_verdict") == "ACCEPT",
          f"drc_all_pass={summ.get('drc_all_pass')} lvs={summ.get('lvs_verdict')}")
    check("① G4 几何回提真的跑了（n_params_checked > 0）",
          (summ.get("geom_params_checked") or 0) > 0,
          f"declared={summ.get('geom_params_declared')} checked={summ.get('geom_params_checked')}")
    gds = resp.get("gds") or {}
    check("① gds.available 且字节数 > 0",
          gds.get("available") is True and (gds.get("bytes") or 0) > 0,
          f"gds={ {k: gds.get(k) for k in ('available', 'bytes', 'filename')} }")
    check("① 单次调用耗时 < 10s（无引擎求解，纯装配+导出）", dt < 10.0, f"{dt:.2f}s")

    # ---------------- ② 同源：报告 ≡ /api/tapeout ----------------
    ref = app.run_tapeout_check({"devices": {_KIND: dict(_PARAMS)}})
    check("② tapeout 报告与 run_tapeout_check(同一入参) canonical JSON 逐字节相等",
          _canon(resp.get("tapeout")) == _canon(ref),
          "同源（同一函数、同一入参）")
    want_to = (resp.get("tapeout") or {}).get("verdict")
    check("② 芯片级双闸与流片报告口径不冲突（都 ACCEPT/通过 ≠ 互相冒名）",
          want_to in ("ACCEPT", "PASS", "OK", True) or want_to is None,
          f"tapeout.verdict={want_to!r}（两份几何各自签核，见 honest_notes）")
    check("② design 回显与入参一致（kind/params/wg）",
          (resp.get("design") or {}).get("kind") == _KIND
          and (resp.get("design") or {}).get("params") == _PARAMS,
          f"design={resp.get('design')}")

    # ---------------- ③ 下载与报告同一来源 ----------------
    url = gds.get("download_url") or ""
    q = parse_qs(url.split("?", 1)[1]) if "?" in url else {}
    body, meta = app.run_design_gds({k: v[0] for k, v in q.items()})
    check("③ 下载端点按响应登记的 download_url 重建成功（不手写 query）",
          isinstance(body, (bytes, bytearray)) and "kind" in q,
          f"url={url!r}")
    check("③ 下载字节 sha256 == 报告登记 sha256（同一来源，不是另算一份）",
          _sha(bytes(body or b"")) == (gds.get("sha256") or "-"),
          f"下载 {_sha(bytes(body or b''))[:12]}… vs 报告 {(gds.get('sha256') or '-')[:12]}…")
    check("③ GDSII 魔数正确（真 GDS，不是空文件/占位）",
          bytes(body or b"")[:4] == b"\x00\x06\x00\x02",
          f"head={bytes(body or b'')[:4]!r}")
    b2, _ = app.run_design_gds({k: v[0] for k, v in q.items()})
    check("③ 无状态确定性：两次重建同值（无临时文件即无清理问题）",
          _sha(bytes(b2 or b"")) == _sha(bytes(body or b"")),
          f"len={len(bytes(body or b''))}")
    b3, _ = app.run_design_gds({"kind": _KIND, "R": "9.0"})
    check("③ 反向：改 R ⇒ sha256 变（不是常量/缓存）",
          _sha(bytes(b3 or b"")) != _sha(bytes(body or b"")),
          f"R=9 {_sha(bytes(b3 or b''))[:12]}…")
    r_name = app.run_design_tapeout(_payload(name="d1"))
    r_name2 = app.run_design_tapeout(_payload(name="other_name_long"))
    check("③ name 只影响文件名，**不污染几何**（sha256 不变）",
          (r_name.get("gds") or {}).get("sha256") == (r_name2.get("gds") or {}).get("sha256"),
          f"d1={(r_name.get('gds') or {}).get('sha256', '-')[:12]}… other={((r_name2.get('gds') or {}).get('sha256') or '-')[:12]}…")
    check("③ 文件名随 name 变（否则浏览器总下同名文件）",
          (r_name.get("gds") or {}).get("filename") != (r_name2.get("gds") or {}).get("filename"),
          f"{(r_name.get('gds') or {}).get('filename')} vs {(r_name2.get('gds') or {}).get('filename')}")
    r_wg = app.run_design_tapeout(_payload(wg=0.6))
    check("③ 全局参数 wg 真的进链路（改 wg ⇒ sha256 变）",
          (r_wg.get("gds") or {}).get("sha256") != (r_name.get("gds") or {}).get("sha256"),
          f"wg=0.6 {(r_wg.get('gds') or {}).get('sha256', '-')[:12]}…")

    # ---------------- ④ 桥接（引擎口径 → 版图口径） ----------------
    b_eng = app.run_design_tapeout({"engine_kind": "engine_ringresonator",
                                    "params": {"R_um": 10.0}})
    b_lay = app.run_design_tapeout(_payload())
    check("④ engine_kind 桥接 ⇒ 与直连版图口径产出**同一份 GDS**",
          (b_eng.get("gds") or {}).get("sha256")
          == (b_lay.get("gds") or {}).get("sha256")
          and (b_eng.get("gds") or {}).get("sha256") is not None,
          f"eng={((b_eng.get('gds') or {}).get('sha256') or '-')[:12]}… lay={((b_lay.get('gds') or {}).get('sha256') or '-')[:12]}…")
    check("④ 桥接后 design 回显**版图口径**（R，不是 R_um）+ 登记 engine_kind",
          (b_eng.get("design") or {}).get("params") == _PARAMS
          and (b_eng.get("design") or {}).get("engine_kind") == "engine_ringresonator",
          f"design={b_eng.get('design')}")

    # ---------------- ⑤ 诚实拒绝（9 条） ----------------
    def _reject(tag, fn, kw):
        r = fn()
        errs = " ".join(r.get("errors") or [])
        check("⑤ 拒绝 %s：ok=False 且理由指名" % tag,
              r.get("ok") is False and bool(errs) and any(k in errs for k in kw),
              f"errors={errs[:110]!r}")

    _reject("被主动排除的引擎", lambda: app.run_design_tapeout(
        {"engine_kind": "engine_waveguide", "params": {"width_um": 0.93}}),
        ["主动排除"])
    ub = gb.unbridgeable_engine_kinds()[0]
    _reject("不可桥接引擎 %s" % ub, lambda: app.run_design_tapeout(
        {"engine_kind": ub, "params": {}}), ["无对应可桥接版图器件"])
    _reject("参数越界 R=1e5", lambda: app.run_design_tapeout(_payload({"R": 1.0e5})),
            ["越界"])
    _reject("参数非数 R='abc'", lambda: app.run_design_tapeout(_payload({"R": "abc"})),
            ["不是数"])
    _reject("多器件 devices（两个键）", lambda: app.run_design_tapeout(
        {"devices": {_KIND: dict(_PARAMS), "Waveguide": {}}}), ["单个"])
    _reject("空 payload（无 kind/engine_kind/devices）",
            lambda: app.run_design_tapeout({}), ["缺少 kind"])

    db, dmeta = app.run_design_gds({})
    check("⑤ 下载端无 kind ⇒ (None, 400 用法) 而**不是**空文件/500",
          db is None and dmeta.get("ok") is False
          and isinstance(dmeta.get("usage"), str) and "reserved_keys" in dmeta,
          f"meta={str(dmeta)[:90]}")
    db2, dmeta2 = app.run_design_gds({"kind": _KIND, "R": "x"})
    check("⑤ 下载端非数 ⇒ (None, 指名理由)",
          db2 is None and "不是数" in str(dmeta2.get("error", "")),
          f"meta={str(dmeta2)[:80]}")
    db3, dmeta3 = app.run_design_gds({"kind": "NoSuchKind"})
    check("⑤ 下载端未知 kind ⇒ (None, 指名 kind)（不 500、不空文件）",
          db3 is None and "NoSuchKind" in str(dmeta3.get("error", "")),
          f"meta={str(dmeta3)[:90]}")

    # ---------------- ⑥ 诚实边界 ----------------
    notes = resp.get("honest_notes") or []
    must = ["原样返回", "不是同一个文件", "主权几何子集",
            "两条路径的键检查强度不同", "已知边界"]
    missing = [m for m in must if not any(m in n for n in notes)]
    check("⑥ honest_notes 含 5 条关键边界（同源/两份几何/主权子集/双路径/declared>checked）",
          not missing, f"缺失={missing}")
    reject_notes = app.run_design_tapeout(_payload({"R": 1.0e5})).get("honest_notes") or []
    check("⑥ **拒绝分支也带完整边界**（不能只在成功时才披露）",
          len(reject_notes) == len(notes) == 5, f"{len(reject_notes)} 条")
    check("⑥ 边界条目是真·叙述（非空串、无占位符）",
          all(len(n) > 30 and "TODO" not in n for n in notes),
          f"len={[len(n) for n in notes]}")
    # 🔴 实测把「直连路径静默忽略无效键」钉死（防它某天变成静默生效却无人知）
    r_bogus = app.run_design_tapeout(_payload({"R": 10.0, "bogus": 999.0}))
    check("⑥ 直连 kind 路径：未知键对几何**零影响**（实测敏感度=0，已披露）",
          (r_bogus.get("gds") or {}).get("sha256") == (b_lay.get("gds") or {}).get("sha256"),
          "加 bogus=999 ⇒ sha256 不变（该键被静默忽略，见 honest_notes 第 4 条）")
    bs = (r_bogus.get("chip") or {}).get("summary") or {}
    check("⑥ declared(2) > checked(1) 如实上报，且不被算作违规",
          bs.get("geom_params_declared") == 2 and bs.get("geom_params_checked") == 1
          and not bs.get("geom_violations"),
          f"declared={bs.get('geom_params_declared')} checked={bs.get('geom_params_checked')}")

    # ---------------- ⑦ 红线：T1.1 源码段零 LLM ----------------
    asrc = open(os.path.join(_HERE, "lda_webui", "app.py"), encoding="utf-8").read()
    seg = _section(asrc, "_DESIGN_GDS_RESERVED_KEYS")
    hits = [t for t in ("openai", "anthropic", "llm", "qwen", "prompt")
            if t in seg.lower()]
    check("⑦ 红线：T1.1 源码段零 LLM 引用（判决全死标量）", not hits, f"hits={hits}")

    # ---------------- ⑧ 接线完备 ----------------
    rsrc = open(os.path.join(_HERE, "lda_webui", "routes.py"), encoding="utf-8").read()
    check("⑧ routes.py GET_ROUTES 登记 /api/design_gds",
          '"/api/design_gds": h_design_gds' in rsrc)
    check("⑧ routes.py POST_ROUTES 登记 /api/design_tapeout",
          '"/api/design_tapeout": h_design_tapeout' in rsrc)
    check("⑧ routes.py HEAVY_POST_PATHS 含 /api/design_tapeout（重计算走登录闸门）",
          rsrc.count('"/api/design_tapeout"') >= 2,
          f'"/api/design_tapeout" 出现 {rsrc.count(chr(34) + "/api/design_tapeout" + chr(34))} 次（POST_ROUTES + HEAVY_POST_PATHS）')
    gds_fn = _section(rsrc, "def h_design_gds(")
    check("⑧ h_design_gds 走**二进制**通道（body= + octet-stream）",
          "body=body" in gds_fn and "application/octet-stream" in gds_fn)
    check("⑧ h_design_gds 失败返回 400（不返回空文件）",
          "if body is None" in gds_fn and "(400, meta)" in gds_fn)
    check("⑧ h_design_gds 带 sha256 响应头（下载可被外部校验）",
          "X-LDA-GDS-Sha256" in gds_fn)

    hsrc = open(os.path.join(_HERE, "lda_webui", "static", "index.html"),
                encoding="utf-8").read()
    want_ui = ["doTapeout", "doGdsLink", "doTapeoutOut", "runDesignTapeout",
               "renderDesignTapeout", "/api/design_tapeout", "/api/design_gds"]
    absent = [w for w in want_ui if w not in hsrc]
    check("⑧ index.html 接线名齐（按钮/下载链/渲染/两个端点）",
          not absent, f"缺={absent}")
    check("⑧ 前端真的送 **engine_kind 口径**（不是版图口径裸参）",
          "engine_kind:_outcomeBest.engine_kind" in hsrc
          and "params:_outcomeBest.params" in hsrc)
    check("⑧ 下载链绑定的是服务端返回的 download_url（不前端拼 URL）",
          "a.href=g.download_url" in hsrc)
    check("⑧ 按钮默认禁用（无最优参数不得点）",
          'id="doTapeout" disabled' in hsrc and "!$('doTapeout').disabled" not in hsrc)

    asrc2 = open(os.path.join(_HERE, "run_webui_api_smoke.py"), encoding="utf-8").read()
    check("⑧ run_webui_api_smoke 把该端点登记进 BINARY_GET（通用循环豁免）",
          'BINARY_GET = {' in asrc2 and '"design_gds"' in asrc2)
    check("⑧ 豁免**配了专项断言**（_check_binary_get 被实跑调用，不是只豁免）",
          "def _check_binary_get(" in asrc2
          and asrc2.count("_check_binary_get(") >= 2)

    print(f"\nlda design tapeout smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
