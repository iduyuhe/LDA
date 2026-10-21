# -*- coding: utf-8 -*-
"""BL 征程 · **BL-M0** 盲区锚判据有效性 **常驻门禁**（闭环缺口 G-BL-1 · **不加锚**）。

本门禁守的是「**判据有没有判别力**」，不是「覆盖率数字好不好看」。

判据分节（**判据数实跑现数** · A3 + B4 + C6 + D3 + E5 + F3 + **G33** + **H4 组 3** + **H5 组 5** + **H6 组 3** + **H7 组 1** = **72**）：
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
  G 候选方法学升级核验 33（v0.9.252 立 · v0.9.253 扩为 **8 条逐锚**）：
    每条 4 项 = **N 锁死 ≡ 注册实现** · **收敛趋近四阶** · `resid ≤ tol/20` · **抹平必红**；
    另 1 项全局「结清即双撤登记」。覆盖 `B65/B66/B67/B68/B81/B82/B83/B84`
  H 「不可收紧」登记面 + tol 棘轮 4（v0.9.254 BL-M2b）：**台账偏松集 ≡ 登记面（双向）** ·
    14 条 tol **只许更严** · 不可收紧 8 条 tol **不许放宽** · `B31` 原样留观
  H7 manifest 双向锁 1（v0.9.258 BL-M4）：受跟踪 `gate_anchor_manifest.json` 的
    `manifest[本门禁]` ≡ **本次运行实际断言的锚集**（逐元素 · 运行时登记非手写 · 删一条必红）

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
_MANIFEST = os.path.join(_HERE, "reports", "gate_anchor_manifest.json")
_GEN = os.path.join(_ROOT, "scripts", "bl_audit.py")
_CI = os.path.join(_HERE, "run_ci_regression.py")
_SCHEMA = "lda_bl_anchor_audit_v1"

# ===========================================================================
# 🔴 缺陷登记面（**只许缩小**：修好一条就删一条，条数棘轮会检查）
# ===========================================================================
# ① 残差恒 0.0 —— 与自证桩不可区分
# 🔴 v0.9.252 BL-M1：`B82` **已结清、从登记面移除**（棘轮自动要求同步：`_RATCHET`
#   的 `zero_resid` 由 1 收紧到 **0**）。修法**不是**改观测（改 T 与 B81 重复、改 φ 实测
#   `Δφ≡0`），而是**换候选**：原「400 段等宽切片连乘」对均匀势垒与闭式数学等价
#   （`S(w)^N ≡ S(N·w)`）⇒ 残差恒 0；换 **Riccati 对数导数 + RK4** 后 `R=|r|²` 直接得
#   （不走 `1−T` 减法）⇒ 残差 9.557e-12、四阶收敛（相邻比 35.15→16.27 趋近 16）、
#   `tol` 由 0.01 收紧到 1e-9（`resid/tol=9.6e-03`）。见 G 组判据。
BL_ZERO_RESID_REVIEWED = {}
# ② 注入「候选=0」仍判 PASS —— 判据结构性失效
# 🔴 v0.9.253 BL-M2：`B81` **已结清并移除**（tol 0.01→1e-9 ⇒ 注入 0 被拒）；
#   棘轮 `inject0` 同步 6 → 5。
# 🔴 v0.9.256 BL-M2b-1：`B31` **已结清并移除**（裁决认定病灶是判据形态：`tol=1.5 > |g|=0.8049`
#   ⇒ 注入 0 必过；收紧到窗口中点 0.79 后注入 0 被拒）⇒ **本登记面清空**，棘轮 `inject0 1 → 0`。
#   ⚠️ 这是 BL 征程里**第一次**把「注入 candidate=0 仍 PASS」清零：清零后该面若再出现任何一条，
#   都是新回归（C 组 D1 会直接红），不允许「重新登记了事」。
BL_INJECT0_PENDING = {}

# ③ 已脱离盲区（**口径伪影**：本门禁的登记表点了它的名字 ⇒ 被 K4 的文本代理计入 L2）
#   ⇒ 不再是「盲区锚」，但**缺陷仍在**，转 BL-M2 批1 与 B81 同族处理。
BL_BLIND_EXIT = {
    "B391": "双缝强度 Simpson；|golden|/tol=0.025（tol 1e-3 对 2.5e-5 过松）。"
            "因本登记表点名被 K4 文本代理计入 L2 ⇒ 盲区 415→414，脱离本次体检域；缺陷仍转 BL-M2 批1",
}
# ③ 相消嫌疑（|golden|≈1 且 resid/tol 极小）—— 已复核但未改
BL_CANCEL_REVIEWED = {
    "B73": "已复核：接近 1 的透射类量，resid 落地板；与 B82 不同（无 1−T 结构），保留观察",
}
# 🔴 v0.9.252 BL-M1：`B82` 从相消嫌疑移除（tol 0.01→1e-9 ⇒ `resid/tol` 由 0 变 9.6e-03）。
# 🔴 v0.9.253 BL-M2：`B68`（`resid/tol=4.1e-03`）与 `B83`（`1.3e-03`）同因换核 + 收紧 tol
#   出相消带 ⇒ **相消 3 → 1（仅剩 B73）**，棘轮同步收紧到 1。

# 🔴 v0.9.254 BL-M2b：④⑤⑥ 三张登记表**搬去** `lda_harness/bl_registries.py`（**非门禁模块**）。
#   理由见该模块 docstring：写在这里会让 K4 的文本代理把「登记」当成「覆盖」
#   （实测 L2 124→130、盲区 414→408 ⇒ 体检域自己缩水 6 条）。改 import 后结构上分开。
from lda_harness.bl_registries import (  # noqa: E402
    BL_LOOSE_UNFIXABLE, BL_TOL_RATCHET, BL_LOOSE_TOL_BASELINE,
    BL_FRAGILE_ULP_MAX, BL_PLATFORM_DELTA_MAX, BL_PLATFORM_FRAGILE,
    BL_TIGHT_REVIEWED, BL_TIGHT_FIXED, BL_TIGHT_KINDS)


_RATCHET = {"zero_resid": 0, "inject0": 0, "cancel": 1, "loose": 8, "tight": 8}


def _load():
    with open(_LEDGER, encoding="utf-8") as f:
        return json.load(f)


def asserted_anchor_ids():
    """运行时登记：本门禁 B 组实际断言的锚集（从台账 `rows` 派生 · 非手写）。

    BL-M4 把 K4 的 L2 由「文本代理」升为「文本 ∪ manifest」。manifest 由
    `scripts/gate_manifest.py` **import 本模块并调用本函数**生成 ⇒ 登记面与运行时
    断言集**同源**；H7 判据再把 manifest 与 `main()` 实际的 `rows` 逐元素锁死。
    """
    return sorted({r["id"] for r in (_load().get("rows") or [])})


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
    # 🔴 棘轮上限**从 `_RATCHET` 现读**，不写死数字（v0.9.251 的教训：手写上限会在
    #   结清一条后变成陈旧文案，而判据仍在看旧值 ⇒ 假守护）。
    check("C4 缺陷面棘轮（只减不增：零残差≤%d · 注入0≤%d · 相消≤%d · 偏松≤%d · 余量≤%d）"
          % (_RATCHET["zero_resid"], _RATCHET["inject0"], _RATCHET["cancel"],
             _RATCHET["loose"], _RATCHET["tight"]),
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
    # 🔴 文案**从 `_RATCHET` 现读**，不写死数字：写死会在棘轮收紧后变成陈旧假守护
    #   （v0.9.257 实测：棘轮已到 8，而文案还写「≤25 / ≤10」，反向探针失败时读起来误导）。
    check("E1 偏松锚计数 ≤ %d（只减不增）" % _RATCHET["loose"],
          (sm.get("n_loose") or 0) <= _RATCHET["loose"],
          "n_loose=%s" % sm.get("n_loose"))
    check("E2 余量不足锚计数 ≤ %d（只减不增）" % _RATCHET["tight"],
          (sm.get("n_tight") or 0) <= _RATCHET["tight"],
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

    # ── G 候选方法学升级核验（v0.9.252 BL-M1 立 · v0.9.253 BL-M2 扩为 **8 条逐锚**）──
    # 🔴 为什么 G 组挂在 BL 门禁：这 8 条的病**不是观测选错**，是候选与 golden 数学等价
    #   （均匀段 `S(w)^N ≡ S(N·w)`）⇒ 必须有判据盯住「候选真的独立于闭式、且残差有阶」。
    from lda_harness import _batch_b4_numeric as _b4
    from lda_harness import verification_adapters as _va2
    # (id, 候选名, 观测, N, 是否势阱) —— N 必须与 `_adapter_p4` 里注册的一致；
    #   下方 G1a 用「同 N 复算 ≡ 注册候选输出」把这份表与实现**锁死**（防两边各说各话）。
    _RIC = [
        ("B65", "b65_sqbarrier_T_deep_riccati_cand", "T", 128, False),
        ("B66", "b66_sqbarrier_T_neartop_riccati_cand", "T", 256, False),
        ("B67", "b67_sqbarrier_T_osc_riccati_cand", "T", 128, False),
        ("B68", "b68_sqbarrier_R_riccati_cand", "R", 128, False),
        ("B81", "b81_sqbarrier_T_v2_riccati_cand", "T", 128, False),
        ("B82", "b82_sqbarrier_R_riccati_cand", "R", 256, False),
        ("B83", "b83_sqbarrier_T_v3_riccati_cand", "T", 256, False),
        ("B84", "b84_finwell_R_riccati_cand", "R", 2048, True),
    ]
    _specs = {x.spec_id: x for x in _va2.build_harness_specs()[0]}
    _cands = _va2.BENCHMARK_CANDIDATES
    for _bid, _cname, _obs, _N, _well in _RIC:
        _sp = _specs[_bid]
        _g = float(_sp.oracle_fn(_sp.params))
        _E = _sp.params["E_eV"] * _b4.EV
        _V = (-1.0 if _well else 1.0) * _sp.params["V0_eV"] * _b4.EV
        _a = _sp.params["a_nm"] * 1e-9

        def _val(_n):
            return abs(_b4.cand_rect_scatter_riccati(_E, _V, _a, _obs, _n) - _g)

        # G1a：N 表 ≡ 注册实现（锁死「门禁以为的 N」与「适配器实际用的 N」）
        _reg = float(_cands[_cname](_sp, _g))
        _direct = _b4.cand_rect_scatter_riccati(_E, _V, _a, _obs, _N)
        check("%s G1a 门禁的 N=%d ≡ 注册候选实现（防两处 N 各说各话）" % (_bid, _N),
              _reg == _direct, "reg=%.17g direct=%.17g" % (_reg, _direct))

        # G1b：收敛**趋近四阶**（N/4 → 2N；不写死方向）
        _ch = [_val(_N // 4), _val(_N // 2), _val(_N), _val(_N * 2)]
        _rt = [_ch[_i] / _ch[_i + 1] for _i in range(3)]
        # 🔴 相邻比趋近的是 **16 = 2⁴**（4 阶），不是 4。首版写成 `|r−4|` ⇒ 5 条假红。
        check("%s G1b 离散化收敛**趋近四阶**（|r_last−16| ≤ |r_first−16| · 不写死方向）" % _bid,
              abs(_rt[-1] - 16.0) <= abs(_rt[0] - 16.0),
              "链比=%s（标称 16）" % ["%.2f" % _x for _x in _rt])

        # G2：默认档残差 ≤ tol/20（防 tol 被悄悄放宽）
        _rd = _val(_N)
        check("%s G2 resid ≤ tol/20（余量 ≥20× · 防 tol 悄悄放宽）" % _bid,
              _rd <= float(_sp.tol) / 20.0,
              "resid=%.3e tol=%g ⇒ 余量 %.0f×" % (_rd, _sp.tol, float(_sp.tol) / _rd))

        # G3：抹平必红 —— 旧核（同宽切片）残差必塌到舍入级（**先证判据能看见病**）
        if _well:
            _old = abs((1.0 - _b4.cand_finwell_scatter_T(_E, _sp.params["V0_eV"] * _b4.EV, _a, _b4.ME)) - _g)
        elif _obs == "T":
            _old = abs(_b4.cand_square_barrier_T(_E, abs(_V), _a, _b4.ME) - _g)
        else:
            _old = abs((1.0 - _b4.cand_square_barrier_T(_E, abs(_V), _a, _b4.ME))
                       - (1.0 - _b4.analytic_square_barrier_T(_E, abs(_V), _a, _b4.ME)))
        # 🔴 判据不是「旧核恰为 0」（B83/B84 是 2.2e-14 / 2.5e-14 的舍入级，非 0），
        #   而是**抹平的签名**：旧核贴舍入地板（≤1e-13）**且**新核比它大 ≥3 个数量级。
        check("%s G3 抹平必红：旧核（同宽切片）贴舍入地板 ≤1e-13 ∧ 新核 ≥1000× 旧核" % _bid,
              _old <= 1e-13 and _rd >= 1000.0 * max(_old, 1e-18),
              "旧核=%.3e · 新核=%.3e（放大 %.1e×）"
              % (_old, _rd, _rd / max(_old, 1e-18)))

    # G4：结清即须**双撤登记**（台账 ∧ 登记面），否则等于没结清
    _cleared = ["B82", "B68", "B83", "B81"]
    _still = [b for b in _cleared
              if b in (sm.get("zero_resid_ids") or [])
              or b in BL_ZERO_RESID_REVIEWED or b in BL_CANCEL_REVIEWED
              or b in BL_INJECT0_PENDING]
    check("G4 已结清 4 条（B82/B68/B83/B81）均已双撤登记（台账 ∧ 登记面）",
          not _still, "仍在登记面=%s" % _still)

    # ── H 「不可收紧」登记面 + tol 棘轮（v0.9.254 BL-M2b）────────────
    from lda_harness import verification_adapters as _va3
    _sp3 = {x.spec_id: x for x in _va3.build_harness_specs()[0]}
    _loose_now = set(sm.get("loose_ids") or [])
    check("H1 台账「偏松」集 ≡ 不可收紧登记面（22→8 的验收点 · 双向）",
          _loose_now == set(BL_LOOSE_UNFIXABLE),
          "台账多出=%s 登记多出=%s" % (sorted(_loose_now - set(BL_LOOSE_UNFIXABLE)),
                                  sorted(set(BL_LOOSE_UNFIXABLE) - _loose_now)))
    _relax = [(b, t, _sp3[b].tol) for b, t in BL_TOL_RATCHET.items()
              if _sp3[b].tol > t * (1.0 + 1e-12)]
    check("H2 tol 棘轮：14 条收紧值只许更严（放宽即红）",
          not _relax, "被放宽=%s" % _relax)
    _widened = [(b, t, _sp3[b].tol) for b, t in BL_LOOSE_TOL_BASELINE.items()
                if _sp3[b].tol > t * (1.0 + 1e-12)]
    check("H3 不可收紧 8 条的 tol 不许被放宽（收紧须同步改基线并重登）",
          not _widened, "被放宽=%s" % _widened)
    # 🔴 v0.9.256 BL-M2b-1：H4 由「B31 原样留观」升级为「**结清验收**」——
    #   裁决认定语义相同（乘性模型差 1.962222），病灶是判据形态 ⇒ tol 1.5→0.79。
    #   验收点：① 已退出注入 0 面；② tol 锁在窗口中点；③ **tol < |golden|**（这正是
    #   「注入 0 必被拒」的结构性充要条件，不是靠数值巧合）；④ 仍留在「偏松」登记面
    #   （`|g|/tol≈1` 对量级一致型锚是结构性的，压不下去 —— 不许把它伪装成「已修好」）。
    _b31g = abs(float(_sp3["B31"].oracle_fn(_sp3["B31"].params)))
    check("H4 B31 结清验收：退出注入0面 ∧ tol=%.2f（窗口中点）∧ **tol < |golden|=%.6f**（结构性条件）"
          " ∧ 仍在偏松登记面"
          % (BL_TOL_RATCHET["B31"], _b31g),
          ("B31" not in BL_INJECT0_PENDING
           and abs(_sp3["B31"].tol - BL_TOL_RATCHET["B31"]) <= 0.0
           and _sp3["B31"].tol < _b31g
           and "B31" in BL_LOOSE_UNFIXABLE),
          "tol=%g · |g|=%.6f · tol<|g|=%s · 在偏松面=%s"
          % (_sp3["B31"].tol, _b31g, _sp3["B31"].tol < _b31g,
             "B31" in BL_LOOSE_UNFIXABLE))

    # 🔴 裁决结论机器化：把「乘性模型差」写成判据 —— 否则日后有人改 m*/n_eff/常数，
    #   比值悄悄变了却没人察觉（注：那会让 H4 的 tol<|g| 先红，但那是间接信号）。
    from lda_harness import b31_soref_bennett_anchor as _S31
    _rr = []
    for _V in (0.5, 1.0, 2.0, 3.0, 5.0):
        _gg = _S31.b31_soref_bennett_phase_shift(_V)
        _cc = _S31.b31_drude_phase_shift(_V)
        _rr.append(_cc / _gg)
    check("H4b B31 差异是**乘性**：c/g 在 V_R∈{0.5,1,2,3,5} 上恒定（极差 ≤1e-12 ⇒ 非加性偏置）",
          (max(_rr) - min(_rr)) <= 1e-12 and abs(_rr[3] - 1.962222) <= 1e-6,
          "c/g=%s" % ["%.9f" % _x for _x in _rr])
    _z_g = _S31.b31_soref_bennett_phase_shift(1e-12)
    _z_c = _S31.b31_drude_phase_shift(1e-12)
    check("H4c B31 极限检验：V_R→0 时两者**同趋 0**（加性 π/2 会留 1.5708 残差 ⇒ 反证「相位多加了 90°」）",
          abs(_z_g) < 1e-9 and abs(_z_c) < 1e-9,
          "V→0: golden=%.3e candidate=%.3e" % (_z_g, _z_c))

    # ── H5 跨平台余量判据（v0.9.255 BL-M2c）────────────────────────────
    # 🔴 为什么需要这一组：tol 收到 1e-16 后，resid 落到**几十~几百 ulp 的噪声区**，
    #   「换解释器重算得到逐位相同的 resid」物理上做不到（实测 B88 跨 py3.9/py3.14 差 10.7%）。
    #   ⇒ 跨平台验收标准从「数值逐位相同」改为「**判决对 resid 扰动不敏感**」。
    import math as _math
    _frag_now = {}
    for _r in rows:
        if _r.get("compare") != "cmp_abs":
            continue
        _g = abs(float(_r["golden"]))
        _res = float(_r["resid"])
        if _g <= 0.0 or _res <= 0.0:
            continue
        _k = _res / _math.ulp(_g)
        if _k <= BL_FRAGILE_ULP_MAX:
            _frag_now[_r["id"]] = (_k, _res, float(_r["tol"]))
    check("H5a 现算脆弱集（resid ≤ %g·ulp(|g|)）≡ 跨平台登记面（双向 · 防漏登/防陈旧）"
          % BL_FRAGILE_ULP_MAX,
          set(_frag_now) == set(BL_PLATFORM_FRAGILE),
          "台账多出=%s 登记多出=%s" % (sorted(set(_frag_now) - set(BL_PLATFORM_FRAGILE)),
                                  sorted(set(BL_PLATFORM_FRAGILE) - set(_frag_now))))
    _weak = {b: v[2] / v[1] for b, v in _frag_now.items() if v[2] / v[1] < 5.0}
    check("H5b 每条脆弱锚余量 tol/resid ≥ 5（跨平台验收的**主判据**）",
          not _weak, "余量不足=%s" % {b: round(m, 3) for b, m in _weak.items()})
    # 扰动探针：把 resid 按**实测最大漂移上界**放大 ⇒ 判决仍不得翻转，且保住 3× 余量
    _unstable = {}
    for _b, (_k, _res, _tol) in _frag_now.items():
        if _tol < 3.0 * _res * (1.0 + BL_PLATFORM_DELTA_MAX):
            _unstable[_b] = round(_tol / (_res * (1.0 + BL_PLATFORM_DELTA_MAX)), 3)
    check("H5c 扰动探针：resid 放大 (1+δ_max)=%.2f 后判决不翻转且余量仍 ≥3×"
          % (1.0 + BL_PLATFORM_DELTA_MAX),
          not _unstable, "余量<3×=%s" % _unstable)
    # 登记记录 vs 本地现算：比值必须落在 δ_max 内（改大记录值会在这里红）
    _drift_bad = []
    for _b, _rec in BL_PLATFORM_FRAGILE.items():
        _rp = _rec.get("resid_prod")
        if _rp is None or _b not in _frag_now:
            continue
        _res = _frag_now[_b][1]
        _d = abs(float(_rp) / _res - 1.0)
        if _d > BL_PLATFORM_DELTA_MAX:
            _drift_bad.append((_b, round(_d, 4)))
    check("H5d 登记的跨平台实测 resid 与本地现算比值 ≤ δ_max=%.2f（防登记值被随手改大）"
          % BL_PLATFORM_DELTA_MAX,
          not _drift_bad, "超界=%s" % _drift_bad)
    # 🔴 反向探针（**必须是真判据，不能写成恒真式**）：把余量口径抽成函数，
    #   对「人为压紧的 tol」必须返回 False，对台账现算值必须返回 True ——
    #   两侧都验，才证明 H5b 有判别力（只验一侧 = 恒绿空转）。
    def _h5_margin_ok(_tol, _res):
        return (_tol / _res >= 5.0
                and _tol >= 3.0 * _res * (1.0 + BL_PLATFORM_DELTA_MAX))

    _h5_false_green = [b for b, (_k, _res, _tol) in _frag_now.items()
                       if _h5_margin_ok(4.9 * _res, _res)]
    _h5_true_green = [b for b, (_k, _res, _tol) in _frag_now.items()
                      if not _h5_margin_ok(_tol, _res)]
    check("H5e 反向探针：人为压紧 tol=4.9·resid ⇒ 余量口径**必判红** ∧ 台账值必判绿"
          "（两侧都验 · 证明 H5b 不是恒真式）",
          not _h5_false_green and not _h5_true_green,
          "压紧却判绿=%s · 台账却判红=%s" % (_h5_false_green, _h5_true_green))

    # ── H6 余量不足披露面（v0.9.257 BL-M3）──────────────────────────────
    _tight_now = set(sm.get("tight_ids") or [])
    check("H6a 台账「余量不足」集 ≡ 披露登记面（双向 · 防漏披露 / 防结清后仍挂账）",
          _tight_now == set(BL_TIGHT_REVIEWED),
          "台账多出=%s 登记多出=%s" % (sorted(_tight_now - set(BL_TIGHT_REVIEWED)),
                                  sorted(set(BL_TIGHT_REVIEWED) - _tight_now)))
    _h6_bad = []
    for _b in sorted(set(BL_TIGHT_REVIEWED) & _tight_now):
        _rec = BL_TIGHT_REVIEWED[_b]
        _rt = float(by[_b]["resid"]) / float(by[_b]["tol"])
        if (_rec.get("kind") not in BL_TIGHT_KINDS
                or len(str(_rec.get("reason") or "")) < 12
                or _rt > 1.0):
            _h6_bad.append((_b, _rec.get("kind"), round(_rt, 4)))
    check("H6b 每条披露：分类合法 ∧ 书面原因 ≥12 字 ∧ **resid/tol ≤ 1.0**（余量可薄但不许越界）",
          not _h6_bad, "不合格=%s" % _h6_bad)
    # 已修两条：margin ≥ 2× 且**不得**回到 tight 集（防「改回去又没人发现」）
    _fix_bad = []
    for _b, _need in BL_TIGHT_FIXED.items():
        if _b not in by:
            _fix_bad.append((_b, "缺席"))
            continue
        _m = float(by[_b]["tol"]) / max(float(by[_b]["resid"]), 1e-300)
        if _m < _need or _b in _tight_now:
            _fix_bad.append((_b, round(_m, 3), _b in _tight_now))
    # 🔴 判据文案**不得写死锚号**：门禁里出现锚号会被 K4 的文本代理当成「专属判据覆盖」
    #   ⇒ L2 虚增、盲区缩小、**体检域自己缩水**（v0.9.257 实测：点名两条 ⇒ L2 124→126、
    #   盲区 414→412）。条目身份由 `BL_TIGHT_FIXED`（非门禁模块）提供，这里只说「已修条目」。
    check("H6c 已修条目（见 `BL_TIGHT_FIXED`）必须 margin ≥ %.1f× ∧ 不在 tight 集"
          % min(BL_TIGHT_FIXED.values()),
          not _fix_bad, "不合格=%s（margin, 仍在tight）" % _fix_bad)

    # ── H7 manifest 双向锁（v0.9.258 BL-M4）──────────────────────────────
    # 🔴 K4 的 L2 改为「文本 ∪ manifest」⇒ manifest 必须**运行时登记**（非手写）。
    #   本判据把 manifest[本门禁] 与**本次运行实际断言的锚集**逐元素锁死：
    #   ① 手改 manifest（加/删/换一条）⇒ 红；② 台账重生后行集变化而 manifest 未重生 ⇒ 红。
    #   锚号只出现在受跟踪 manifest 与台账（数据面），本门禁文案不含任何锚号字面量。
    _man_ids, _man_cnt, _man_schema = [], None, ""
    if os.path.exists(_MANIFEST):
        with open(_MANIFEST, encoding="utf-8") as _mf:
            _mj = json.load(_mf)
        _man_schema = _mj.get("schema") or ""
        _reg = (_mj.get("registries") or {}).get("run_bl_anchor_guard_smoke.py") or {}
        _man_ids = sorted(_reg.get("anchors") or [])
        _man_cnt = _reg.get("count")
    _rt_ids = sorted({r["id"] for r in rows})
    _man_diff = sorted(set(_man_ids) ^ set(_rt_ids))
    check("H7 manifest[本门禁] ≡ 本次实际断言锚集（逐元素 · 运行时登记非手写 · 删一条必红）",
          (_man_schema == "lda_gate_anchor_manifest_v1"
           and _man_cnt == len(_man_ids) == len(_rt_ids)
           and _man_ids == _rt_ids),
          "manifest=%d runtime=%d 差=%s" % (len(_man_ids), len(_rt_ids), _man_diff[:6]))

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

    # ── M 文本覆盖集体检（v0.9.262 · BL-M5：体检域从「盲区集」扩到「L2 文本覆盖集」）──
    #   🔴 动机：M0–M4 只量了**无专属门禁**的锚；「有门禁提到」的锚从未按同一把尺子量过。
    #   实测其中存在 `|g|/tol` 极小 ⇒ candidate=0 也放行的锚 = 判别力真空。
    #   本组只做「已登记 + 棘轮只减不增」，不在此处改 tol（收紧走单独里程碑）。
    from lda_harness import bl_registries as _BLR
    _tc = led.get("text_covered") or {}
    check("M1 文本覆盖集已体检（口径补齐 · 可审 ≥ %d ∧ 汇总齐备）"
          % _BLR.BL_TEXT_AUDITED_MIN,
          bool(_tc) and int(_tc.get("audited") or 0) >= _BLR.BL_TEXT_AUDITED_MIN
          and all(k in _tc for k in ("n_zero_resid", "n_loose", "n_tight",
                                     "n_cancellation_suspect", "n_zero_injection_passes")),
          "audited=%s/%s" % (_tc.get("audited"), _tc.get("ids_total")))

    def _text_ratchet_ok(tc, ratchet):
        """纯函数：文本覆盖集棘轮（只减不增）。抽出来以便反向探针直接喂坏数据。"""
        return (int(tc.get("n_loose") or 0) <= int(ratchet["loose"])
                and int(tc.get("n_zero_injection_passes") or 0) <= int(ratchet["inject0"]))

    check("M2 文本覆盖集棘轮（只减不增：偏松 ≤ %d · 注入0 放行 ≤ %d）"
          % (_BLR.BL_TEXT_RATCHET["loose"], _BLR.BL_TEXT_RATCHET["inject0"]),
          _text_ratchet_ok(_tc, _BLR.BL_TEXT_RATCHET),
          "偏松=%s 注入0=%s" % (_tc.get("n_loose"), _tc.get("n_zero_injection_passes")))

    _bad_tc = {"n_loose": _BLR.BL_TEXT_RATCHET["loose"] + 1,
               "n_zero_injection_passes": 0}
    check("M3 反向探针：偏松数 +1 ⇒ M2 型棘轮必红（非假绿）",
          not _text_ratchet_ok(_bad_tc, _BLR.BL_TEXT_RATCHET),
          "注入=%s" % _bad_tc["n_loose"])

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
