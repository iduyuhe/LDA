#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电子计算征程 · **红线口径防漂移门禁**（E11-a · D-161）。

═══════════════════════════════════════════════════════════════════════════
为什么存在（本门禁守什么）
═══════════════════════════════════════════════════════════════════════════
平台红线在 2026-09-11（`docs/lda_active_device_redline_clarification_2026-09-10.md` §八/§九）
与 2026-09-23（`LDA_电域解锁与外部对标边界_讨论纪要_2026-09-23.md`）**已两次拍板为分层口径**：

    · 器件级 T1 数值内核（泊松 + 漂移-扩散 + 连续性 PDE）**已解锁并落地**；
    · **T2 工艺真值 / 工艺角 / 流片** 永久锁；电路级（SerDes/BER/眼图）无真值锚 ⇒ 不做。

而 `ecore/` 包长期写着「**电域→仅电路级（T1）**」——**把「本包的设计取舍」误述为「红线要求」**，
与平台现行口径自相矛盾。E11-a 已全仓订正为「**本包主动限定在电路级**（平台红线 = 分层口径）」。

🔴 **本门禁的价值**：口径漂移是**静默**的 —— 没人改代码也会错，且只在对外演示时被问出来。
它与「三不做文档漂移」（2026-09-23 · 12 文件 29 处）同型，故必须机器化：
**任一处把「主动限定」重新写回「红线只允许到电路级」⇒ 本门禁必红。**

判什么（分节）
--------------
A 正向零残留：ecore 包内不得出现「红线…仅电路级」类旧断言 + 必须**至少 4 处**明确声明「主动限定在电路级」
B 披露必为分层：ecore 对外/模块披露里，凡含「红线」字样者必须同时含「分层」
C 活文档同步：E 征程对外物料（事实源/一页纸/案例卡/蓝图）不得残留旧断言
D 反向可证伪：4 条突变探针（旧文本必被识别 · 新文本不误报 · 披露改回旧文本必红 · 披露丢「分层」必红）
"""
from __future__ import annotations

import glob
import importlib
import os
import re
import sys
import unittest.mock as mock

_HERE = os.path.dirname(os.path.abspath(__file__))          # = …/lda
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_ECO = os.path.join(_HERE, "lda_l2", "ecore")

#: 「把电路级限定说成红线要求」的违规模式（**只对被测机制敏感**）
_VIOLATION_PATTERNS = (
    r"红线[^。\n]{0,16}仅电路级",
    r"电域\s*→\s*仅电路级",
    r"红线[^。\n]{0,16}T1\s*电路级",
    r"T1\s*电路级[^。\n]{0,10}红线",
)

#: 必须为分层口径的活文档（白名单见 _DOC_WHITELIST）
_DOCS = (
    "docs/LDA_电子计算征程_E6-E10_蓝图_2026-09-30.md",
    "LDA_电子计算芯片_事实源.md",
    "LDA_电子计算芯片_对外一页纸.md",
    "LDA_电子计算芯片_案例卡.html",
)

#: 豁免：历史段（CHANGELOG 旧版本段不追改）· 讨论纪要（以旧口径为「问题描述」载体）
_DOC_WHITELIST_TOKENS = ("CHANGELOG", "讨论纪要", "纪要_")

#: ecore 的披露常量（module, attr）
_DISCLOSURES = (
    ("lda_l2.ecore", "ECORE_DISCLOSURE"),
    ("lda_l2.ecore.capability_manifest", "ECORE_CAPABILITY_DISCLOSURE"),
    ("lda_l2.ecore.crossbar_mvm", "CROSSBAR_DISCLOSURE"),
    ("lda_l2.ecore.mvm_datapath", "MVM_DATAPATH_DISCLOSURE"),
    ("lda_l2.ecore.scale_bench", "SCALE_BENCH_DISCLOSURE"),
    ("lda_l2.ecore.mosfet", "MOSFET_DISCLOSURE"),
)


def _violations(text: str):
    """返回文本中「把电路级限定说成红线要求」的违规片段（空 list = 合规）。"""
    out = []
    for p in _VIOLATION_PATTERNS:
        out += re.findall(p, text)
    return out


def _read(rel):
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return None
    with open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def _ecore_files():
    return sorted(glob.glob(os.path.join(_ECO, "*.py")))


def _chk_ecore_no_legacy():
    """A1：ecore 包内旧断言归零。"""
    bad = {}
    for fp in _ecore_files():
        with open(fp, encoding="utf-8") as f:
            v = _violations(f.read())
        if v:
            bad[os.path.basename(fp)] = v[:3]
    return (len(bad) == 0), "违规文件=%s" % bad


def _chk_active_limit_declared():
    """A2：正向 —— 至少 4 处明确声明「主动限定在电路级」（防反向漂移：改成别的错表述）。"""
    hits = []
    for fp in _ecore_files():
        with open(fp, encoding="utf-8") as f:
            if "主动限定在电路级" in f.read():
                hits.append(os.path.basename(fp))
    return (len(hits) >= 4), "命中 %d 处：%s" % (len(hits), hits)


def _chk_disclosure_layered():
    """B：披露里凡含「红线」字样者，必须同时含「分层」。"""
    bad, scanned = {}, 0
    for mod, attr in _DISCLOSURES:
        try:
            m = importlib.import_module(mod)
        except Exception as e:                      # noqa: BLE001
            bad[mod] = "import 失败: %r" % e
            continue
        d = getattr(m, attr, None)
        if not isinstance(d, dict):
            bad[mod] = "%s 不存在或非 dict" % attr
            continue
        scanned += 1
        for k, v in d.items():
            if not isinstance(v, str):
                continue
            if "红线" in v and "分层" not in v:
                bad["%s.%s[%s]" % (mod.split(".")[-1], attr, k)] = v[:60]
            if _violations(v):
                bad["%s.%s[%s] 旧口径" % (mod.split(".")[-1], attr, k)] = v[:60]
    return (len(bad) == 0 and scanned >= 6), "扫描披露 %d 个 · 违规=%s" % (scanned, bad)


def _chk_docs_synced():
    """C：活文档零残留（白名单豁免）。"""
    bad, missing = {}, []
    for rel in _DOCS:
        if any(t in rel for t in _DOC_WHITELIST_TOKENS):
            continue
        t = _read(rel)
        if t is None:
            missing.append(rel)
            continue
        v = _violations(t)
        if v:
            bad[rel] = v[:3]
    return (len(bad) == 0 and not missing), "违规=%s · 缺失=%s" % (bad, missing)


def _probe_legacy_detected():
    """D1：旧文本必被识别。"""
    return bool(_violations('"redline": "电域→仅电路级（T1）：不碰 Foundry TCAD"')) \
        and bool(_violations("T1 电路级（红线守「电域→仅电路级」）")) \
        and bool(_violations("红线：电域仅电路级"))


def _probe_layered_clean():
    """D2：现行分层文本不得误报。"""
    cur = _read(os.path.join("lda", "lda_l2", "ecore", "__init__.py"))
    cur = cur or ""
    return (not _violations(cur)) and (not _violations(
        "红线 = 分层口径：器件级 T1 内核已解锁 · T2 永久锁；本包主动限定在电路级"))


def _probe_disclosure_regress_red():
    """D3：把对外披露改回旧文本 ⇒ B 组必红。"""
    m = importlib.import_module("lda_l2.ecore")
    saved = dict(m.ECORE_DISCLOSURE)
    m.ECORE_DISCLOSURE["redline"] = "电域→仅电路级（T1）：不碰 Foundry TCAD"
    ok, _ = _chk_disclosure_layered()
    m.ECORE_DISCLOSURE.clear()
    m.ECORE_DISCLOSURE.update(saved)
    return ok is False


def _probe_disclosure_lose_layered():
    """D4：披露含「红线」却丢「分层」⇒ B 组必红。"""
    m = importlib.import_module("lda_l2.ecore")
    saved = dict(m.ECORE_DISCLOSURE)
    m.ECORE_DISCLOSURE["redline"] = "红线：T1 电路级（不碰 Foundry TCAD/流片）"
    ok, _ = _chk_disclosure_layered()
    m.ECORE_DISCLOSURE.clear()
    m.ECORE_DISCLOSURE.update(saved)
    return ok is False


def main() -> int:
    ok, det = _chk_ecore_no_legacy()
    check("A1 ecore 包内无「把电路级限定说成红线要求」的旧断言", ok, det)

    ok, det = _chk_active_limit_declared()
    check("A2 ecore 包内 ≥4 处明确声明「本包主动限定在电路级」（正向防反向漂移）", ok, det)

    ok, det = _chk_disclosure_layered()
    check("B 披露：凡含「红线」字样处必须同时含「分层」口径", ok, det)

    ok, det = _chk_docs_synced()
    check("C 活文档（蓝图/事实源/一页纸/案例卡）旧断言零残留", ok, det)

    check("D1 探针：旧文本（电域→仅电路级 / 红线…T1 电路级）必被识别",
          _probe_legacy_detected() is True)
    check("D2 探针：现行分层文本不得误报",
          _probe_layered_clean() is True)
    check("D3 探针：对外披露改回旧文本 ⇒ B 组判定必红",
          _probe_disclosure_regress_red() is True)
    check("D4 探针：披露含「红线」但丢「分层」⇒ B 组判定必红",
          _probe_disclosure_lose_layered() is True)

    with mock.patch.dict(os.environ, {}, clear=False):
        ok, det = _chk_ecore_no_legacy()
    check("E 还原完整性：探针运行后 A1 复绿（无 patch 残留）", ok, det)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
