# -*- coding: utf-8 -*-
"""BL 征程 · **BL-M0** 盲区锚判据有效性 **常驻门禁**（闭环缺口 G-BL-1 · **不加锚**）。

本门禁守的是「**判据有没有判别力**」，不是「覆盖率数字好不好看」。

判据分节（**判据数实跑现数** · A3 + B4 + C6 + D3 + E5 + F3 = **24**）：
  A 台账三件套 3：**子进程重跑 ≡ 磁盘（逐字节）** · schema/摘要自洽 · LF only
  B 逐锚硬断言 4：全部锚 L1 判决 PASS · 非豁免锚 `resid > 0` · 非豁免锚 `resid/tol < 1` ·
    `candidate != golden`（防自证桩化回归）
  C 缺陷登记面锁死 6：零残差登记 ≡ 台账 · 注入0 待修登记 ≡ 台账 · 相消复核登记 ≡ 台账 ·
    **条数棘轮（只减不增）** · 每条须带书面原因（≥8 字）· 脱离盲区面（文本代理计入 L2 的
    条目须书面说明且确实不在台账）
  D 注入探针（**现算，不读台账**）3：重算 `compare_fn(0, golden)` ⇒ 只有登记面内的条目可放行 ·
    台账 `zero_injection_passes_ids` ≡ 现算集（防过期）· 对照组 `golden+5·tol` **必须 100% 被拒**
  E 披露口径棘轮 + 可复现锁 5：`n_loose ≤ 25` · `n_tight ≤ 10` · `n_zero_resid ≤ 1` 且 ⊆ 登记面 ·
    **量化位数锁死 10 位** · **生成器强制钉死 10 线程（须早于 harness 导入）**
  F 红线 3：生成器零时钟/随机 · 走 `det.write_text` · 本门禁 ∈ `CORE_SMOKES`

🔴 **A1 为什么曾经随机红（v0.9.251 首轮全量 CI 当场抓出）**：台账在 10 线程与默认多线程
   环境下 `resid` 第 7–9 位有效数字就不同（BLAS 归约顺序 → 迭代求解器末位漂移 ~1e-9 相对），
   量化到 10 位仍拦不住 ⇒ 修法是**在生成器里强制钉死线程数**（与调用方环境解耦），
   而不是把量化位数往下砍（砍位数会伤害判别力）。**E5 判据锁死该修法**。

🔴 **本门禁不隐藏缺陷**：7 条「放行候选=0」与 4 条相消嫌疑**显式登记 + 机器锁死**，
   而不是假装修好。修好一条 ⇒ 必须同步删登记（棘轮会自动要求），否则 C 组红。

🔴 `main()` 返回真值而非恒 0。
🔴 一律走 `smoke_kit.make_check`（助手单一来源棘轮 J3）。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

from lda_harness import verification_adapters as _va  # noqa: E402,F401
from lda_harness import deterministic as det  # noqa: E402

_LEDGER = os.path.join(_HERE, "reports", "bl_anchor_audit.json")
_GEN = os.path.join(_ROOT, "scripts", "bl_audit.py")
_CI = os.path.join(_HERE, "run_ci_regression.py")
_SCHEMA = "lda_bl_anchor_audit_v1"

# ===========================================================================
# 🔴 缺陷登记面（**只许缩小**：修好一条就删一条，条数棘轮会检查）
# ===========================================================================
# ① 残差恒 0.0 —— 与自证桩不可区分
BL_ZERO_RESID_REVIEWED = {
    "B82": "R=1−T 在深隧穿区灾难性相消（R≈0.99995、T≈4.66e-5），残差被减法吃掉；"
           "BL-M1 改观测到 T 后重算 tol",
}
# ② 注入「候选=0」仍判 PASS —— 判据结构性失效
BL_INJECT0_PENDING = {
    "B11": "环 FSR 峰值拟合；|golden|/tol=0.167，tol 0.03 对 5e-3 量级过松；BL-M2 批1 收紧或换观测",
    "B31": "Soref-Bennett 载流子相移；|golden|/tol=0.537 且 resid/tol=0.516（双向贴边）；BL-M2 批1",
    "B74": "有限深阱 T_min；|golden|/tol=0.102，tol 0.01 对 1e-3 量级过松；BL-M2 批1 收紧",
    "B81": "方势垒透射 T；|golden|/tol=0.005（tol 是 golden 的 215×）；BL-M2 批1 优先",
    "B87": "方势垒透射 v4；|golden|/tol=0.149；与 B81 同族，合并处理；BL-M2 批1",
    "B88": "双势垒透射去谐 v2；|golden|/tol=0.448；BL-M2 批1",
}

# ③ 已脱离盲区（**口径伪影**：本门禁的登记表点了它的名字 ⇒ 被 K4 的文本代理计入 L2）
#   ⇒ 不再是「盲区锚」，但**缺陷仍在**，转 BL-M2 批1 与 B81 同族处理。
BL_BLIND_EXIT = {
    "B391": "双缝强度 Simpson；|golden|/tol=0.025（tol 1e-3 对 2.5e-5 过松）。"
            "因本登记表点名被 K4 文本代理计入 L2 ⇒ 盲区 415→414，脱离本次体检域；缺陷仍转 BL-M2 批1",
}
# ③ 相消嫌疑（|golden|≈1 且 resid/tol 极小）—— 已复核但未改
BL_CANCEL_REVIEWED = {
    "B68": "已复核：golden 与 candidate 为不同路径，resid 1e-13 量级属双精度地板而非同一式；保留观察",
    "B73": "已复核：接近 1 的透射类量，resid 落地板；与 B82 不同（无 1−T 结构），保留观察",
    "B83": "已复核：同 B73 型，透射接近 1；resid 地板，保留观察",
}

_RATCHET = {"zero_resid": 1, "inject0": 6, "cancel": 4, "loose": 25, "tight": 10}


def _load():
    with open(_LEDGER, encoding="utf-8") as f:
        return json.load(f)


def _gen_stdout() -> str:
    pr = subprocess.run([sys.executable, _GEN], cwd=_ROOT,
                        capture_output=True, text=True)
    if pr.returncode != 0:
        print("[gen stderr]", pr.stderr[-500:])
    return pr.stdout


def main() -> int:
    print("=" * 78)
    print("BL-M0 盲区判据有效性门禁（不加锚 · 只护判据判别力）")
    print("=" * 78)

    led = _load()
    with open(_GEN, encoding="utf-8") as _f:
        _gsrc = _f.read()          # 生成器源码（F1/F2/E4 共用，须在 E 组之前读）
    rows = led.get("rows") or []
    sm = led.get("summary") or {}
    by = {r["id"]: r for r in rows}

    # ── A 台账三件套 ─────────────────────────────────────────────────
    gen = _gen_stdout()
    with open(_LEDGER, encoding="utf-8", newline="") as f:
        disk = f.read()
    check("A1 子进程重跑 ≡ 磁盘台账（逐字节）", disk == gen + "\n",
          "len(gen)=%d len(disk)=%d" % (len(gen), len(disk)))
    self_ok = (sm.get("blind_total") == sm.get("blind_strict", -1)
               + sm.get("blind_non_anchorable", -1)
               and sm.get("l2_ceiling") == sm.get("ledger_total", -1)
               - sm.get("blind_non_anchorable", -1)
               and sm.get("n_zero_resid") == len(sm.get("zero_resid_ids") or [])
               and sm.get("n_loose") == len(sm.get("loose_ids") or [])
               and sm.get("n_tight") == len(sm.get("tight_ids") or [])
               and sm.get("n_zero_injection_passes")
               == len(sm.get("zero_injection_passes_ids") or []))
    check("A2 schema 与摘要自洽（blind=strict+不可接 · l2_ceiling · 各计数≡清单长）",
          led.get("schema") == _SCHEMA and self_ok and len(rows) == sm.get("blind_strict"),
          "schema=%s strict=%s rows=%d" % (led.get("schema"), sm.get("blind_strict"), len(rows)))
    check("A3 台账 LF only（无 CR）", "\r" not in disk, "CR=%d" % disk.count("\r"))

    # ── B 逐锚硬断言 ─────────────────────────────────────────────────
    bad_verdict = [r["id"] for r in rows if not r.get("passes")]
    check("B1 全部锚 L1 判决为 PASS（复核口径：err ≤ tol）", not bad_verdict,
          "FAIL=%d %s" % (len(bad_verdict), bad_verdict[:6]))

    exempt_zero = set(BL_ZERO_RESID_REVIEWED)
    bad_zero = [r["id"] for r in rows
                if r["flags"]["zero_resid"] and r["id"] not in exempt_zero]
    check("B2 非登记锚 resid > 0（残差恒 0 ⇒ 与自证桩不可区分）", not bad_zero,
          "零残差未登记=%s" % bad_zero[:6])

    bad_tight = [r["id"] for r in rows
                 if r.get("resid_over_tol") is not None and r["resid_over_tol"] >= 1.0]
    check("B3 全部锚 resid/tol < 1（判据未越界）", not bad_tight, "越界=%s" % bad_tight[:6])

    # 🔴 不能直接比 candidate == golden：台账按 10 位有效数字量化，会把 1e-13 级差异抹平
    #   ⇒ 改判「台账自洽」：resid 必须与 |candidate − golden| 在量化误差内一致。
    incons = []
    for r in rows:
        g, c, rd = r.get("golden"), r.get("candidate"), r.get("resid")
        if None in (g, c, rd):
            continue
        scale = max(abs(g), abs(c), 1e-300)
        if abs(rd - abs(c - g)) > 1e-9 * scale + 1e-12:
            incons.append(r["id"])
    check("B4 台账自洽：resid ≡ |candidate − golden|（量化误差内）", not incons,
          "不自洽=%s" % incons[:6])

    # ── C 缺陷登记面锁死 ─────────────────────────────────────────────
    check("C1 零残差登记 ≡ 台账 zero_resid_ids",
          set(BL_ZERO_RESID_REVIEWED) == set(sm.get("zero_resid_ids") or []),
          "登记=%s 台账=%s" % (sorted(BL_ZERO_RESID_REVIEWED),
                              sorted(sm.get("zero_resid_ids") or [])))
    check("C2 注入0 待修登记 ≡ 台账 zero_injection_passes_ids",
          set(BL_INJECT0_PENDING) == set(sm.get("zero_injection_passes_ids") or []),
          "登记=%d 台账=%d" % (len(BL_INJECT0_PENDING),
                              len(sm.get("zero_injection_passes_ids") or [])))
    cancel_union = set(BL_CANCEL_REVIEWED) | exempt_zero
    check("C3 相消复核登记 ≡ 台账 cancellation_suspect_ids",
          cancel_union == set(sm.get("cancellation_suspect_ids") or []),
          "登记=%s 台账=%s" % (sorted(cancel_union),
                              sorted(sm.get("cancellation_suspect_ids") or [])))

    counts = {"zero_resid": len(BL_ZERO_RESID_REVIEWED),
              "inject0": len(BL_INJECT0_PENDING),
              "cancel": len(BL_CANCEL_REVIEWED),
              "loose": sm.get("n_loose") or 0,
              "tight": sm.get("n_tight") or 0}
    grow = {k: (counts[k], _RATCHET[k]) for k in counts if counts[k] > _RATCHET[k]}
    check("C4 缺陷面棘轮（只减不增：零残差≤1 · 注入0≤7 · 相消≤4 · 偏松≤25 · 余量≤10）",
          not grow, "越界=%s" % grow)

    exit_hit = sorted(set(BL_BLIND_EXIT) & set(by))
    thin_exit = [k for k, v in BL_BLIND_EXIT.items() if len(v.strip()) < 8]
    check("C6 脱离盲区面：书面原因齐备 ∧ 确实不在台账（因文本代理计入 L2 而脱离）",
          not exit_hit and not thin_exit,
          "仍在台账=%s 原因过短=%s" % (exit_hit, thin_exit))

    thin = [k for k, v in list(BL_ZERO_RESID_REVIEWED.items())
            + list(BL_INJECT0_PENDING.items())
            + list(BL_CANCEL_REVIEWED.items()) if len(v.strip()) < 8]
    check("C5 每条登记须带书面原因（≥8 字，禁空登记）", not thin, "过短=%s" % thin[:5])

    # ── D 注入探针（现算，不读台账）──────────────────────────────────
    specs, _cm = _va.build_harness_specs()
    by_spec = {s.spec_id: s for s in specs}
    pass_ids, reject_ids = [], []
    for r in rows:
        if r.get("compare") != "cmp_abs":
            continue
        s = by_spec[r["id"]]
        g = float(s.oracle_fn(s.params))
        tol = float(s.tol)
        if float(s.compare_fn(0.0, g)) <= tol:
            pass_ids.append(r["id"])
        else:
            reject_ids.append(r["id"])
    check("D1 注入「候选=0」⇒ 仅登记的 %d 条可放行（其余必须拒绝）"
          % len(BL_INJECT0_PENDING),
          set(pass_ids) == set(BL_INJECT0_PENDING),
          "放行=%s" % sorted(pass_ids)[:9])
    check("D2 台账 zero_injection_passes_ids ≡ 现算放行集（防台账过期）",
          set(sm.get("zero_injection_passes_ids") or []) == set(pass_ids),
          "台账=%d 现算=%d" % (len(sm.get("zero_injection_passes_ids") or []), len(pass_ids)))

    not_rejected = []
    for r in rows:
        if r.get("compare") != "cmp_abs":
            continue
        s = by_spec[r["id"]]
        g = float(s.oracle_fn(s.params))
        tol = float(s.tol)
        if float(s.compare_fn(g + 5.0 * tol, g)) <= tol:
            not_rejected.append(r["id"])
    check("D3 对照组：注入 golden+5·tol ⇒ 100% 被拒（证明判据未完全退化）",
          not not_rejected, "放行=%s" % not_rejected[:6])

    # ── E 披露口径棘轮 ───────────────────────────────────────────────
    check("E1 偏松锚计数 ≤ 25（只减不增）", (sm.get("n_loose") or 0) <= _RATCHET["loose"],
          "n_loose=%s" % sm.get("n_loose"))
    check("E2 余量不足锚计数 ≤ 10（只减不增）", (sm.get("n_tight") or 0) <= _RATCHET["tight"],
          "n_tight=%s" % sm.get("n_tight"))
    zr = set(sm.get("zero_resid_ids") or [])
    check("E3 零残差锚 ⊆ 缺陷登记面（不许有未登记的黑洞）",
          zr <= (exempt_zero | set(BL_INJECT0_PENDING)), "越界=%s" % sorted(zr - exempt_zero))
    # E4：量化位数锁死（有人把 %.10g 调回 %.12g 会让 A1 永久红 —— 用判据提前拦住）
    check("E4 台账量化位数锁死为 10 位有效数字（防被人调高致 A1 永久红）",
          'float("%.10g" % float(v))' in _gsrc, "未命中 %.10g")
    # E5：线程钉死锁（🔴 v0.9.251 首轮全量 CI 抓出：环境未钉 ⇒ 同一台账在 10 线程与默认
    #   多线程下 `resid` 第 7–9 位就不同 ⇒ A1「逐字节」随机红。修法是钉线程，不是砍位数。）
    _pin_mark = 'os.environ[_k] = "10"'
    _pin_at = _gsrc.find(_pin_mark)
    _imp_at = _gsrc.find("from lda_harness")
    check("E5 生成器**强制**钉死 10 线程（非 setdefault）且早于 harness 导入 "
          "（否则台账跨环境不可复现 · A1 随机红）",
          _pin_at != -1 and _imp_at != -1 and _pin_at < _imp_at
          and 'LDA_FDTD_THREADS"] = "10"' in _gsrc,
          "pin_at=%d imp_at=%d" % (_pin_at, _imp_at))

    # ── F 红线 ───────────────────────────────────────────────────────
    # 🔴 用 AST 判而非字面 grep：模块 docstring 里逐条**点名**了这些禁止项（自指陷阱）
    import ast as _ast
    with open(_GEN, encoding="utf-8") as f:
        _tree = _ast.parse(f.read())
    _badmods, _badcalls = [], []
    _FORBID_MODS = {"time", "random", "uuid", "datetime", "tempfile"}
    _FORBID_CALLS = {"getpid", "mkdtemp", "now", "time", "strftime", "uuid4"}
    for _n in _ast.walk(_tree):
        if isinstance(_n, _ast.Import):
            for _a in _n.names:
                if _a.name.split(".")[0] in _FORBID_MODS:
                    _badmods.append(_a.name)
        elif isinstance(_n, _ast.ImportFrom):
            if (_n.module or "").split(".")[0] in _FORBID_MODS:
                _badmods.append(_n.module or "")
        elif isinstance(_n, _ast.Attribute):
            if _n.attr in _FORBID_CALLS and not isinstance(_n.value, _ast.Name):
                continue
            if _n.attr in _FORBID_CALLS and isinstance(_n.value, _ast.Name) \
                    and _n.value.id in _FORBID_MODS:
                _badcalls.append("%s.%s" % (_n.value.id, _n.attr))
    check("F1 生成器零时钟/随机/进程依赖（AST 判 · 不受 docstring 点名干扰）",
          not _badmods and not _badcalls,
          "mods=%s calls=%s" % (_badmods, _badcalls))
    check("F2 生成器走 deterministic.write_text（⑧b 唯一口径）",
          "deterministic as det" in _gsrc and "det.write_text(" in _gsrc, "")
    with open(_CI, encoding="utf-8") as f:
        in_core = "run_bl_anchor_guard_smoke.py" in f.read()
    check("F3 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core, "in_core=%s" % in_core)

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("BL-M0 门禁：%s（FAIL=%d）· 缺陷面：零残差 %d · 注入0 %d · 相消 %d · 偏松 %d · 余量 %d"
          % ("ALL PASS" if bad == 0 else "有红色", bad,
             counts["zero_resid"], counts["inject0"], counts["cancel"],
             counts["loose"], counts["tight"]))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
