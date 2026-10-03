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
1. **标准 JSON 出口**：7 张公开只读 demo 卡（`oi` / `qchip` / `schip` / `pchip` /
   `accel` / `ecore` / `d4`）全部 `json.dumps(..., allow_nan=False)` 通过。
2. **无非有限值**：7 张卡卡内不存在 `NaN` / `±inf`（逐值递归定位到 JSON 路径）。
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
    """载入 7 张公开只读 demo 卡的构建器（延迟 import，失败即红而非崩）。"""
    from lda_webui import (accel_case, d4case, ecore_case, oi_case, pchip_case,
                           qchip_case, schip_case)
    return {
        "oi":    lambda: oi_case.case_card(),
        "qchip": lambda: qchip_case.case_card(12, topology="rect"),
        "schip": lambda: schip_case.case_card(),
        "pchip": lambda: pchip_case.case_card(),
        "accel": lambda: accel_case.case_card(phase_bits=4, dac_bits=6, adc_bits=6),
        "ecore": lambda: ecore_case.case_card(),
        "d4":    lambda: d4case.case_card(),
    }, oi_case


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
    check("J1-a 7 张公开只读 demo 卡的**标准 JSON 出口**（dumps allow_nan=False 全过）",
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
    check("K1 本门禁已登记进 CORE_SMOKES（防静默漏接 · 血案 #28 同族）",
          "run_webui_json_hard_smoke.py" in _ci)

    npass = globals().get("PASS", 0)
    nfail = globals().get("FAIL", 0)
    print()
    print("RESULT: %d PASS / %d FAIL" % (npass, nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
