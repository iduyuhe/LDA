# -*- coding: utf-8 -*-
"""WebUI 公开只读端点**标准 JSON 出口**门禁（2026-10-03 · v0.9.185 事故修）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（v0.9.185 生产事故 · 用户实测截图）
═══════════════════════════════════════════════════════════════════════════
用户点「运行 光联接模块 M0 – M4 案例」⇒ 只回一行：

    错误: No number after minus sign in JSON at position 16230 (line 1 column 16231)

根因：`lda_l2/oi_m3.xtalk_next_db(k=0)` 返回 `float("-inf")`；`json.dumps` 把非有限
float 序列化成 **`-Infinity`** —— 这**不是标准 JSON**（ECMA-404 / RFC 8259 只认
`Infinity` 的非数字写法？不：标准 JSON **没有** Infinity/NaN 字面）。浏览器
`JSON.parse` 遇到 `-` 后跟非数字 ⇒ 抛 "No number after minus sign" ⇒ 整张案例卡崩。

🔴🔴 **假绿是怎么发生的（本条最重要）**：我上一轮发布后用 `python -m json.tool` /
`json.load` 验收生产 `/api/oi_demo`，**Python 的 `json.load` 默认接受 `-Infinity`**
⇒ 全绿通过 ⇒ 发布。而浏览器一律崩。**验收器与浏览器口径不一致 ⇒ 验收是假的。**
通法：验收公开 JSON 端点**必须**用 `json.dumps(..., allow_nan=False)`（拒绝非标准
字面）或 `json.loads(s, parse_constant=raise)`，绝不能用默认 `json.load`。

───────────────────────────────────────────────────────────────────────────
判什么
───────────────────────────────────────────────────────────────────────────
1. **标准 JSON 出口**：8 张公开只读 demo 卡（`oi` / `qchip` / `schip` / `pchip` /
   `accel` / `ecore` / `d4` / `pm`）全部 `json.dumps(..., allow_nan=False)` 通过。
2. **无非有限值**：8 张卡卡内不存在 `NaN` / `±inf`（逐值递归定位到 JSON 路径）。
3. **oi 专项**：`m3.next.xtalk_at_zero_coupling_db` == `oi_m3.NEG_INF_DB`（真 −∞ 的
   **字符串 tag**），且 **≠ −3000**（防「假 clamp」复活 —— 首版 clamp 把零耦合判成
   巨大耦合，本判据就是为抓它而生的）。
4. **出口字段**：oi 卡 `json_hard_ok=True` 且 `json_hard_bad` 为空。
5. **HTTP 出口守卫**：`app.py` 的 `_send` 用 `allow_nan=False` 且带 `_json_safe` 兜底
   （纵深防御：任何**新端点**漏网非有限值 ⇒ 服务端红，而不是前端整页崩）。
6. **突变探针**（先证能变红，再信判据）：
   · P1 往 oi 卡灌 `float("-inf")` ⇒ `json_hard_ok` **必 False**；
   · P2 把真 −∞ tag 换成 −3000 clamp ⇒ 本门禁的 oi 专项判据 **必红**；
   · P3 `_json_safe` 走真实现 ⇒ `inf/-inf/NaN` 都得到 tag / 字符串；
   · P4 抹掉 `app.py` 的 `allow_nan=False` ⇒ ⑤ 的 HTTP 出口守卫判据 **必红**。
7. 自入 CI core（防静默漏接 · 血案 #28 同族）。

🔴 诚实边界：本门禁只管「JSON 机器能不能解析」，**不**判数值语义对不对；
语义仍由 `oi_case.run_selfchecks` + 各 `run_oi_*_smoke` 的「卡内数字 ≡ 模块现算」
判据守。二者互补：**那些守「值对不对」，本门禁守「前端能不能打开」。**
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

APP = os.path.join(_HERE, "lda_webui", "app.py")
CI = os.path.join(_HERE, "run_ci_regression.py")


def _load_modules():
    """载入 8 张公开只读 demo 卡的构建器（延迟 import，失败即红而非崩）。"""
    from lda_webui import (accel_case, d4case, ecore_case, oi_case, pchip_case,
                           pm_case, qchip_case, schip_case)
    return {
        "oi":    lambda: oi_case.case_card(),
        "qchip": lambda: qchip_case.case_card(12, topology="rect"),
        "schip": lambda: schip_case.case_card(),
        "pchip": lambda: pchip_case.case_card(),
        "accel": lambda: accel_case.case_card(phase_bits=4, dac_bits=6, adc_bits=6),
        "ecore": lambda: ecore_case.case_card(),
        "d4":    lambda: d4case.case_card(),
        "pm":    lambda: pm_case.case_card(),
    }, oi_case


def _signing_cards():
    """N3（v0.9.283）：载入签核 schema 覆盖的 **18 张**案例卡（只取 verdict，便宜）。

    实测 11 张未在上述 builders 内的卡合计 **0.06s**（均为硬编码/缓存，零重算），
    故可全量对拍而不拖垮本门禁 120s 预算。
    """
    from lda_webui import (accel_case, d1_case, d2_case, d4case, ecore_case,
                           j1_case, j2_case, j3_case, j4_case, j5_case, oi_case,
                           pchip_case, pm_case, qchip_case, qs_case, schip_case,
                           sensor_case, soc_case)
    return {
        "accel": lambda: accel_case.case_card(phase_bits=4, dac_bits=6, adc_bits=6),
        "d1": d1_case.case_card, "d2": d2_case.case_card, "d4": d4case.case_card,
        "ecore": ecore_case.case_card,
        "j1": j1_case.case_card, "j2": j2_case.case_card, "j3": j3_case.case_card,
        "j4": j4_case.case_card, "j5": j5_case.case_card,
        "oi": oi_case.case_card,
        "pchip": pchip_case.case_card, "pm": pm_case.case_card,
        "qchip": lambda: qchip_case.case_card(12, topology="rect"),
        "qs": qs_case.case_card, "schip": schip_case.case_card,
        "sensor": sensor_case.case_card, "soc": soc_case.case_card,
    }


def main() -> int:
    builders, oi_case = _load_modules()

    cards, errs = {}, []
    for name, fn in builders.items():
        try:
            cards[name] = fn()
        except Exception as e:                              # noqa: BLE001
            errs.append("%s: %s: %s" % (name, type(e).__name__, e))
            cards[name] = None

    # ── 1. 标准 JSON 出口（allow_nan=False ⇒ 非标准字面直接 ValueError）──
    _std = {}
    for name, card in cards.items():
        if card is None:
            _std[name] = False
            continue
        try:
            json.dumps(card, allow_nan=False)
            _std[name] = True
        except ValueError:
            _std[name] = False
    check("J1-a 8 张公开只读 demo 卡的**标准 JSON 出口**（dumps allow_nan=False 全过）",
          len(errs) == 0 and all(_std.values()))
    if errs:
        for e in errs:
            check("J1-b 卡构建异常：%s" % e, False)

    # ── 2. 无非有限值（递归定位）──
    from lda_webui.oi_case import _nonfinite_scan
    _nf = {}
    for name, card in cards.items():
        _nf[name] = _nonfinite_scan(card) if card is not None else ["<未构建>"]
    check("J2 卡内不存在非有限 float（NaN / ±inf → 非标准 JSON ⇒ 前端崩）",
          all(not _v for _v in _nf.values()))
    for _name, _v in _nf.items():
        if _v:
            check("J2-%s 非有限值路径：%s" % (_name, _v[:4]), False)

    # ── 3. oi 专项：真 −∞ tag（≠ −3000 假 clamp）──
    from lda_l2 import oi_m3
    _card = cards.get("oi")
    _tag = None
    if _card is not None:
        _tag = (_card.get("m3", {}).get("next", {}) or {}).get("xtalk_at_zero_coupling_db")
    check("J3 oi 卡 m3.next.xtalk_at_zero_coupling_db == oi_m3.NEG_INF_DB（真 −∞ tag）",
          _tag == oi_m3.NEG_INF_DB and oi_m3.NEG_INF_DB == "-∞")
    check("J4 oi 卡该值 ≠ −3000（防「假 clamp」把零耦合判成巨大耦合）",
          not isinstance(_tag, (int, float)) or _tag != -3000.0)

    # ── 4. 出口判据字段 ──
    check("J5 oi 卡 json_hard_ok=True 且 json_hard_bad 为空（出口判据自报状态）",
          bool(_card and _card.get("json_hard_ok") is True
               and not (_card.get("json_hard_bad") or [])))

    # ── 5. HTTP 出口守卫（app.py _send：allow_nan=False + _json_safe 兜底）──
    _app_src = ""
    try:
        _app_src = open(APP, encoding="utf-8").read()
    except Exception:                                      # noqa: BLE001
        _app_src = ""
    check("J6 app.py HTTP 出口走 allow_nan=False（非标准 JSON ⇒ 服务端先红，不坑前端）",
          "allow_nan=False" in _app_src)
    check("J7 app.py 出口带 _json_safe 兜底（漏网非有限值 ⇒ tag 化而非崩前端）",
          "_json_safe" in _app_src)

    # ── 6. 突变探针：先证能变红 ──
    import copy as _copy
    # P1：灌非有限值 ⇒ json_hard_ok 必 False
    _p1 = False
    try:
        _bad = _copy.deepcopy(_card)
        _bad["m3"]["next"]["xtalk_db"] = float("-inf")
        # 双向：判据**变红**（False）且扫描**抓得到**（定位到路径）—— 只查一半会放
        # 「判据红了但扫不出来」（假红）或「扫得出但判据恒绿」（假绿）过关。
        _p1 = (oi_case.json_hard_ok(_bad) is False) and bool(_nonfinite_scan(_bad))
    except Exception:                                      # noqa: BLE001
        _p1 = False
    check("🔴 探针P1：往 oi 卡灌 float('-inf') ⇒ json_hard_ok 变 False（判据能变红自证）", _p1)

    # P2：假 clamp 复活 ⇒ J3 判据必红
    _p2 = False
    try:
        _bad2 = _copy.deepcopy(_card)
        _bad2["m3"]["next"]["xtalk_at_zero_coupling_db"] = -3000.0
        _p2 = (_bad2["m3"]["next"]["xtalk_at_zero_coupling_db"] != oi_m3.NEG_INF_DB)
    except Exception:                                      # noqa: BLE001
        _p2 = False
    check("🔴 探针P2：把真 −∞ tag 换成 −3000 clamp ⇒ J3 判据必红（防 clamp 复活）", _p2)

    # P3：_json_safe 真实现（inf / -inf / NaN → tag 字符串）
    _p3 = (oi_case._json_safe(float("inf")) == "∞"
           and oi_case._json_safe(float("-inf")) == oi_m3.NEG_INF_DB
           and isinstance(oi_case._json_safe(float("nan")), str))
    check("🔴 探针P3：_json_safe 走真实现（inf → ‘∞’ · -inf → NEG_INF_DB · NaN → 字符串）", _p3)

    # P4：抹掉 app.py 的 allow_nan=False ⇒ J6 必红
    _p4 = ("allow_nan=False" not in _app_src.replace("allow_nan=False", ""))
    check("🔴 探针P4：'allow_nan=False' 被抹掉 ⇒ J6 必红（静态守卫有判别力）", _p4)

    # ── 6b. 探针无副作用（探针只喂 deepcopy 副本，真卡不受污染）──
    check("R1 探针跑完后**真卡**仍满足 J1/J2/J3（探针只喂 deepcopy 副本 · 无副作用）",
          bool(_card is not None and _card.get("json_hard_ok") is True
               and (_card.get("m3", {}).get("next", {}) or {}).get("xtalk_at_zero_coupling_db")
                    == oi_m3.NEG_INF_DB))

    # ── 7. 自入 CI core ──
    try:
        _ci = open(CI, encoding="utf-8").read() if os.path.exists(CI) else ""
    except Exception:                                      # noqa: BLE001
        _ci = ""
    # ══════════════════════════════════════════════════════════════════════
    # N3 签核 schema（v0.9.283 · D-231）：四域用**同一套话**回答
    #   「这一张卡，到底是什么级别的签核？」
    # 三维正交：grade（工程链深度）× evidence（证据强度）× deck（可信等级）。
    # 🔴 拆维度的理由：`ecore` 的 DESIGN_VERIFIED（工程链到后仿）与 `schip` 的
    #    DESIGN_SIGNOFF（走完版图+DRC/LVS）**不是同一维度上的强弱**；而"有没有可
    #    复核的锚"是第三件事（电子域 0 锚）。压进一个字符串会得出错误结论。
    # ══════════════════════════════════════════════════════════════════════
    from lda_harness import signing_schema as SS
    _signed = _signing_cards()
    _au = SS.audit()

    check("S1 签核 schema 覆盖 ≡ 案例卡全集（18 张）",
          set(_signed) == set(SS.CASES),
          "卡=%d schema=%d 差=%s" % (len(_signed), len(SS.CASES),
                                     sorted(set(_signed) ^ set(SS.CASES))))

    _drift = []
    for _k in sorted(SS.CASES):
        if _k not in _signed:
            continue
        _card = _signed[_k]() or {}
        _v = _card.get("verdict")
        _d = SS.CASES[_k]["declared_grade"]
        if _v != _d:
            _drift.append((_k, _d, _v))
    check("S1b 注册 declared_grade ≡ 卡上 verdict（逐卡防漂移）",
          not _drift, "漂移=%s" % (_drift[:4] or "无"))

    # 🔴 N3-b（v0.9.283）：**拆维度** —— deck 限制不再判"违规"，也不再降 grade。
    #    改前 `min(grade, ceiling)` 把 soc 判成 AUDIT_ONLY，读起来像"工程深度比
    #    13 张设计预算卡还浅"（AUDIT_ONLY 在旧序列里 rank 1 < DESIGN_BUDGET 2）。
    #    改后：`grade` 保留事实、`claimable_grade` 表达限制，两者各说各的事。
    check("S2 违规 0 ∧ 对外口径压制登记 == 棘轮 %d（soc：公开近似 deck ⇒ 只可审计）"
          % SS.CLAIM_DOWNGRADED_CASES,
          _au["violations"] == SS.CEILING_VIOLATIONS
          and _au["claim_downgraded"] == ["soc"],
          "violations=%s downgraded=%s detail=%s"
          % (_au["violations"], _au["claim_downgraded"], _au["violation_detail"]))

    # S2b：**防"拆维度"被用来偷偷降级** —— grade 必须保留事实，claimable 才是限制
    _soc = SS.CASES["soc"]
    check("S2b 拆维度未偷偷降级：soc grade 仍 DESIGN_SIGNOFF（事实）∧ "
          "claimable=AUDIT_ONLY（限制）",
          _soc["grade"] == "DESIGN_SIGNOFF"
          and _soc["claimable_grade"] == "AUDIT_ONLY"
          and _soc["claim_downgraded"] is True,
          "grade=%s claimable=%s downgraded=%s"
          % (_soc["grade"], _soc["claimable_grade"], _soc["claim_downgraded"]))

    # S2c：无 NDA deck ⇒ **零对外**。这是防自封的另一侧：
    #     有人把某卡 deck 改成 foundry_nda 而不带 attestation，R2 会红；
    #     而若真有人拿到 NDA，这里会从 [] 变非空 —— 必须人决策，不得静默。
    check("S2c 无任何卡 allow_external（18 张全无 NDA deck ⇒ 零对外签核）",
          _au["allow_external_cases"] == [],
          "可对外=%s" % (_au["allow_external_cases"] or "无"))

    _noanc = [k for k, r in SS.CASES.items()
              if r["evidence"] in ("STRICT", "EMPIRICAL") and not r["anchors"]]
    check("S3 声称 STRICT/EMPIRICAL 的卡必须有锚号（防「无锚也称强证据」）",
          not _noanc, "缺锚=%s" % (_noanc or "无"))

    _fab = [k for k, r in SS.CASES.items()
            if r["capacity_basis"] == "fabricated_devices"]
    check("S4 无卡声称 fabricated_devices（四域均无实测回流 ⇒ 规模一律版图容量）",
          not _fab, "越级=%s" % (_fab or "无"))

    check("S5 卡上未登记 anchors 的卡数 == 棘轮 %d（只降不升）"
          % SS.ANCHOR_UNREGISTERED_CASES,
          len(_au["anchors_unregistered"]) == SS.ANCHOR_UNREGISTERED_CASES,
          "实得=%d 已登记=%d 张" % (len(_au["anchors_unregistered"]),
                                    len(_au["anchors_on_card"])))

    # ── S5b/S5c（v0.9.283 N3-a）：登记面 ⇄ 卡上实况 双向锁死 ──────────────
    # 🔴 为什么必须运行时对拍：上一版 `anchors_on_card` 是 make_record 的**手填 bool**，
    #    等于自证。N3-a 改成 audit() 运行时读卡；对拍当场抓出 3 处漂移
    #    （pchip 多登 B1/B21 无据 · oi 漏登 B19 有实测 · qchip 漏登 S4）。
    check("S5b 登记 anchors ≡ 卡上 anchors（逐卡运行时对拍 · 漂移即红）",
          not _au["anchors_drift"],
          "漂移=%s" % (_au["anchors_drift"] or "无"))

    _src = _au["anchors_source_by_case"]
    _bad_src = [k for k, v in _src.items() if v not in ("runtime", "segment", "none")]
    _selfcontra = [k for k, v in _src.items()
                   if (v == "none" and SS.CASES[k]["anchors"])
                   or (v == "runtime" and not SS.CASES[k]["anchors"])]
    check("S5c anchors_source 三档合法 ∧ 自洽（none⇒空锚 · runtime⇒非空锚）",
          not _bad_src and not _selfcontra,
          "非法=%s 自相矛盾=%s 分布=%s"
          % (_bad_src or "无", _selfcontra or "无", _au["by_anchors_source"]))

    # 反向探针：每条规则各必红，且合规写法必绿（两侧都验）
    # 🔴 N3-b：`claimable_grade` 现在是 R1 的校验对象 ⇒ 探针必须**跟着重算**，
    #    否则"合规化后必绿"会因 claimable_mismatch 误红（反向探针随真值一起反向）。
    _p6 = [
        SS.validate(dict(SS.CASES["ecore"], declared_grade="FOUNDRY_SIGNOFF",
                         attestation="")),                       # 自封必红
        SS.validate(dict(SS.CASES["ecore"],
                         capacity_basis="fabricated_devices")),  # 容量无据必红
        SS.validate(dict(SS.CASES["j1"], evidence="STRICT", anchors=())),  # 强证据无锚必红
        # 合规化：deck 换 NDA **且 claimable 重算** ⇒ 必绿
        SS.validate(dict(SS.CASES["soc"], deck="foundry_nda", attestation="NDA-001",
                         claimable_grade="DESIGN_SIGNOFF",
                         claim_ceiling="FOUNDRY_SIGNOFF",
                         allow_external=True, claim_downgraded=False)),
        # 只换 deck 不重算 claimable ⇒ 必红（拆维度后的新失败通道）
        SS.validate(dict(SS.CASES["schip"], deck="foundry_public")),
        # grade 落回 AUDIT_ONLY（旧"压扁"行为）⇒ 必红（它不在 GRADES 里）
        SS.validate(dict(SS.CASES["soc"], grade="AUDIT_ONLY", declared_grade="AUDIT_ONLY")),
    ]
    check("S6 反向探针：自封／容量无据／强证据无锚／只换deck不重算／grade落回AUDIT_ONLY "
          "四改必红 ∧ 合规必绿",
          bool(_p6[0]) and bool(_p6[1]) and bool(_p6[2]) and not _p6[3]
          and bool(_p6[4]) and bool(_p6[5]),
          "自封=%d 容量=%d 无锚=%d 合规=%d 只换deck=%d 旧压扁=%d"
          % (len(_p6[0]), len(_p6[1]), len(_p6[2]), len(_p6[3]),
             len(_p6[4]), len(_p6[5])))

    # S6b：对拍器本身的探针（**两侧都验** —— 不一致必非空、一致必空）
    _p6b = [
        SS.anchors_diff(("B1", "B2"), ("B2", "B3")),   # 两侧各有差 ⇒ 必非空
        SS.anchors_diff(("B2",), ("B2",)),             # 完全一致 ⇒ 必空
    ]
    check("S6b 反向探针：anchors_diff 不一致必非空 ∧ 一致必空（防对拍器恒绿）",
          bool(_p6b[0]) and not _p6b[1],
          "不一致=%s 一致=%s" % (_p6b[0], _p6b[1] or "空"))

    # ── N3-d：诚实边界统一读取（S7/S7b/S7c）────────────────────────────
    # 🔴 收敛点放在**对外契约**（`case_card()["honest_note"]`）而非 Python 变量名：
    #    18 个模块实际是 **4 张 `HONEST_NOTE` + 12 张 `XXX_HONEST_NOTE` + 2 张内联**
    #    （`oi`/`accel` 无模块级常量）。改名会连带改 7 个「改模块变量 ⇒ case_card
    #    必红」的突变探针；而加**别名**是快照 —— 突变后统一入口会给过期值。
    _nt = _au["honest_note_by_case"]
    _nt_miss = sorted(k for k, v in _nt.items() if not str(v).strip())
    check("S7 18 张卡 honest_note 全非空（统一从卡上取 · 不看变量名）",
          len(_nt) == len(SS.CASES) and not _nt_miss,
          "卡数=%d 空=%s" % (len(_nt), _nt_miss or "无"))

    from importlib import import_module as _im
    _bad_cov = sorted(set(SS.CASES) ^ set(SS.NOTE_ATTR))
    _bad_attr = []
    for _k, _a in sorted(SS.NOTE_ATTR.items()):
        if _a is None or _k not in SS.CARD_MODULE:
            continue
        if not hasattr(_im("lda_webui." + SS.CARD_MODULE[_k]), _a):
            _bad_attr.append((_k, _a))
    check("S7b note_attr 覆盖 == 18 ∧ 登记的模块级常量真存在（防表过期/漏登记）",
          not _bad_cov and not _bad_attr,
          "覆盖差=%s 不存在=%s" % (_bad_cov or "无", _bad_attr or "无"))

    # S7c 反向探针（两侧都验）：表少一条必红 · 常量名写错必红
    _t1 = dict(SS.NOTE_ATTR)
    _t1.pop("soc")
    _t2 = dict(SS.NOTE_ATTR)
    _t2["soc"] = "SOC_HONEST_NOTE_TYPO"
    _miss_one = set(_t1) != set(SS.CASES)
    _typo = not hasattr(_im("lda_webui." + SS.CARD_MODULE["soc"]), _t2["soc"])
    check("S7c 反向探针：note_attr 少一条必红 ∧ 常量名写错必红",
          _miss_one and _typo, "少一条=%s 写错=%s" % (_miss_one, _typo))

    # ── N5：对外口径（S8/S8b）────────────────────────────────────────
    # 🔴 **扫描面只含"对外宣称"，不含 `honest_note`** —— `honest_note` 的性质是
    #    「我不能做什么」，天然满篇「不报 TOPS/W」「不产出 fJ/op」。扫它必然大量误报，
    #    而"为了过判据去改诚实边界"是本项目最不能做的事（判据反过来鼓励说谎）。
    from lda_harness import outward_claim as OC
    _lbl = _au["verdict_label_by_case"]
    _lbl_empty = sorted(k for k, v in _lbl.items() if not str(v).strip())
    _bad_claim = []
    for _k in sorted(SS.CASES):
        _card = SS.read_card(_k)
        _line = OC.claim_line(_card)["line"]
        _hits = OC.scan(_line)
        if _hits:
            _bad_claim.append((_k, [h["term"] for h in _hits]))
    check("S8 18 卡 verdict_label 全非空 ∧ 对外一句话无禁忌词"
          "（流片/量子优势/TOPS·fJ-op/CLM）",
          not _lbl_empty and not _bad_claim,
          "label 空=%s · 禁忌=%s" % (_lbl_empty or "无", _bad_claim or "无"))

    # S8b：扫描器**两侧都验** —— 正面宣称必红、免责声明必绿、禁令陈述必绿
    _p8 = [
        bool(OC.scan("已流片并量产")),            # 正面宣称 ⇒ 必红
        bool(OC.scan("实现量子优势")),            # 正面宣称 ⇒ 必红
        bool(OC.scan("TOPS/W 达到 100")),         # 正面宣称 ⇒ 必红
        bool(OC.scan("CLM 18/24")),               # CLM 对外 ⇒ 必红
        not OC.scan("本卡非流片实测"),            # 免责声明 ⇒ 必绿
        not OC.scan("不报任何 TOPS/W"),           # 免责声明 ⇒ 必绿
        not OC.scan("CLM（闭环成熟度，仅内部）"),  # 禁令陈述 ⇒ 必绿
    ]
    check("S8b 反向探针：正面宣称必红 ∧ 免责/禁令陈述必绿（防「一刀切禁字」误伤诚实边界）",
          all(_p8), "p8=%s" % _p8)

    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28 同族）",
          "run_webui_json_hard_smoke.py" in _ci)

    npass = globals().get("PASS", 0)
    nfail = globals().get("FAIL", 0)
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
