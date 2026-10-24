"""D-215 突变探针（scratch · 不入 CI）：证明 run_quantum_deck_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件** ⇒ 无需文件还原/哈希复核），
逐条造假后重跑门禁，确认 exit≠0 且 [FAIL] 计数 > 0。全绿门禁无此反证 = 不可信。

人工记录（改动 → 应红判据）：
  · M1 `deck_limits` 无视 deck 实值、回默认限值      ⇒ D1 应红（篡改不生效）
  · M2 `signoff_ceiling` 恒回 FOUNDRY_SIGNOFF/对外    ⇒ D3 / E2 应红（自封签核）
  · M3 `validate_deck` 缺键时自动补默认（静默默认）   ⇒ A1 应红（缺键不再拒绝）
  · M4 `domain_limit_keys` 漏掉一个键（键集缩水）     ⇒ B1 应红
  · M5 `drc_with_deck` 忽略 deck 限值、用默认         ⇒ D1 应红（限值不真进判决）
  · M6 `drc_with_deck` 把 foundry 名写进 verdict 串   ⇒ D2 应红（元信息进判决）
  · M7 `build_deck` 放行 NDA 无凭据                   ⇒ E1 应红（防自封通道被破）
  · M8 `drc_with_deck` 不校验 rule_check 与域一致性   ⇒ E3 应红（错配域被放行）
  · M9 `self_built_deck` 允许 provenance 覆盖         ⇒ A1 应红
  · M10 加载器把 sha256 写成常量（虚报来源）          ⇒ G2 / A2 应红（v0.9.277 · D-225）
  · M11 加载器吞掉坏 deck（缺键/坏 JSON 都补默认）     ⇒ G5 / G3 应红（键集守恒被绕开）
  · M12 env 通道无视 LDA_QUANTUM_DECK（恒返 None）    ⇒ G6 / A2 应红
🔴 教训：探针必须 patch 门禁**同一模块对象**（S.QD）——
   另起 `from lda_qeda import quantum_deck` 会拿到不同实例 ⇒ patch 打空 ⇒ 假绿。
   门禁内一律 `QD.foo(...)` 模块属性访问，故本探针可命中。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_quantum_deck_smoke as S      # noqa: E402
from lda_qeda import quantum_deck as QD  # noqa: E402  同一 sys.modules 实例
from lda_qeda import quantum_deck_io as QDI   # noqa: E402  同一 sys.modules 实例


def run_smoke():
    S.PASS = 0
    S.FAIL = 0
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                     # 突变致病态 ⇒ 崩溃也算红
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    out = buf.getvalue()
    return rc, out.count("[FAIL]")


def main() -> int:
    rows = []
    rows.append(("baseline 无突变（须全绿）", *run_smoke()))

    _deck_limits = QD.deck_limits
    _signoff = QD.signoff_ceiling
    _validate = QD.validate_deck
    _keys = QD.domain_limit_keys
    _drc = QD.drc_with_deck
    _build = QD.build_deck
    _self_built = QD.self_built_deck

    # M1 deck_limits 无视实值
    def _m1(deck):
        dom = (deck or {}).get("domain", "photonic")
        return dict(QD._default_limits(dom))

    QD.deck_limits = _m1
    rows.append(("M1 deck_limits 回默认限值（篡改失效）", *run_smoke()))
    QD.deck_limits = _deck_limits

    # M2 签核档自封
    def _m2(deck):
        return {"tag": "FOUNDRY_SIGNOFF", "scope": "自封", "allow_external": True,
                "provenance": (deck or {}).get("provenance", "self_built")}

    QD.signoff_ceiling = _m2
    rows.append(("M2 signoff_ceiling 恒对外签核（自封）", *run_smoke()))
    QD.signoff_ceiling = _signoff

    # M3 缺键静默默认
    def _m3(deck):
        d = dict(deck)
        lim = dict(d.get("limits") or {})
        for k in QD.domain_limit_keys(d.get("domain", "photonic")):
            lim.setdefault(k, 1.0)
        d["limits"] = lim
        return _validate(d)

    QD.validate_deck = _m3
    rows.append(("M3 validate_deck 缺键自动补默认（静默默认）", *run_smoke()))
    QD.validate_deck = _validate

    # M4 键集缩水
    QD.domain_limit_keys = lambda dom: _keys(dom)[:-1]
    rows.append(("M4 domain_limit_keys 漏一键（键集缩水）", *run_smoke()))
    QD.domain_limit_keys = _keys

    # M5 限值不真进判决
    def _m5(target, deck, *, rule_check="auto"):
        d = _validate(deck)
        base = dict(QD._default_limits(d["domain"]))
        fake = dict(d)
        fake["limits"] = base
        return _drc(target, fake, rule_check=rule_check)

    QD.drc_with_deck = _m5
    rows.append(("M5 drc_with_deck 忽略 deck 限值（用默认）", *run_smoke()))
    QD.drc_with_deck = _drc

    # M6 元信息注入判决
    def _m6(target, deck, *, rule_check="auto"):
        out = _drc(target, deck, rule_check=rule_check)
        out["violations"] = list(out.get("violations") or []) + [
            {"rule": "DECK-META", "detail": "foundry=%s" % out["deck"]["foundry"]}]
        out["verdict"] = "REJECT"
        return out

    QD.drc_with_deck = _m6
    rows.append(("M6 drc_with_deck 把厂名注入 violations（元信息进判决）", *run_smoke()))
    QD.drc_with_deck = _drc

    # M7 放行 NDA 无凭据
    def _m7(deck):
        d = dict(deck)
        if d.get("provenance") == "foundry_nda" and not d.get("attestation"):
            d["attestation"] = "SELF-DECLARED"
        return _validate(d)

    QD.validate_deck = _m7
    rows.append(("M7 validate_deck 放行 NDA 无凭据（自封通道）", *run_smoke()))
    QD.validate_deck = _validate

    # M8 不校验域错配
    def _m8(target, deck, *, rule_check="auto"):
        return _drc(target, deck, rule_check=None)

    QD.drc_with_deck = _m8
    rows.append(("M8 drc_with_deck 不校验域错配", *run_smoke()))
    QD.drc_with_deck = _drc

    # M9 self_built 允许覆盖
    def _m9(domain, **kw):
        kw.pop("provenance", None)
        kw.setdefault("note", "x")
        return _build(domain, None, provenance="self_built", **kw)

    QD.self_built_deck = _m9
    rows.append(("M9 self_built_deck 允许 provenance 覆盖", *run_smoke()))
    QD.self_built_deck = _self_built

    # ── M10–M12 · v0.9.277（D-225）导入链的反向证据 ──
    _qdi_load = QDI.load_quantum_deck
    _qdi_env = QDI.load_quantum_deck_from_env

    # M10 加载器虚报 sha256（写成常量）
    def _load_fake_sha(x, **kw):
        d = _qdi_load(x, **kw)
        d["loader"] = dict(d.get("loader") or {})
        d["loader"]["sha256"] = "0" * 64
        return d

    QDI.load_quantum_deck = _load_fake_sha
    rows.append(("M10 加载器虚报 sha256（恒常量）", *run_smoke()))
    QDI.load_quantum_deck = _qdi_load

    # M11 加载器吞掉坏 deck：任何错误都补成自建 deck（静默回退）
    def _load_swallow(x, **kw):
        try:
            return _qdi_load(x, **kw)
        except Exception:                       # noqa: BLE001 — 故意吞，模拟"静默回落"
            d = dict(QD.self_built_deck("photonic"))
            d["loader"] = {"schema": QDI.LOADER_SCHEMA, "source": "file",
                           "basename": "swallowed", "sha256": None,
                           "env_var": None, "domain_checked": False}
            return d

    QDI.load_quantum_deck = _load_swallow
    rows.append(("M11 加载器吞掉坏 deck（静默补默认）", *run_smoke()))
    QDI.load_quantum_deck = _qdi_load

    # M12 env 通道失效（恒返 None，等于永远读不到外部 deck）
    QDI.load_quantum_deck_from_env = lambda **kw: None
    rows.append(("M12 env 通道无视 %s" % QDI.ENV_DECK_VAR, *run_smoke()))
    QDI.load_quantum_deck_from_env = _qdi_env

    print("=" * 78)
    bad = 0
    for name, rc, nfail in rows:
        if name.startswith("baseline"):
            good = (rc == 0 and nfail == 0)
        else:
            good = (rc != 0 and nfail > 0)
        if not good:
            bad += 1
        print("%-6s %-52s rc=%-3d FAIL=%d" % ("[OK]" if good else "[BAD]", name, rc, nfail))
    print("=" * 78)
    print("突变探针：%d 条，%d 条未按预期变红" % (len(rows) - 1, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
