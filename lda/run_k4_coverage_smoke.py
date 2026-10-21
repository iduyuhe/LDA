# -*- coding: utf-8 -*-
"""K 征程 · K4 门禁×锚覆盖矩阵 **常驻门禁**（闭环缺口 G-K-6）。

判据分节（**判据数实跑现数**）：
  A 表结构与守恒：文件存在 · 顶层字段齐备 · schema 精确 ·
    **`anchors` 键集 ≡ 账本全集（新增锚必被登记）** · 计数守恒（l2+blind=total · l1≤total · l3≤l2）
  B 受跟踪生成物三件套：**子进程重跑 ≡ 磁盘（逐字节）** · 幂等 · LF only
  C 事实性（**独立重算**）：`gates` 锚集 ≡ 门禁**独立重扫** · L1 集 ≡ `verification_report` 现算 ·
    l2/l3 计数 ≡ 从 `anchors` 现算 · `by_gate_count` 分布求和 ≡ l2 · blind 集 ≡ total−l2 ·
    `blind_by_band` 求和 ≡ blind 总数 · **C7 L2 ≡ 文本 ∪ manifest（逐元素）**
  D 覆盖下限棘轮（**只升不降**）：l2 ≥ ratchet.l2_min · l3 ≥ ratchet.l3_min ·
    ratchet 不得低于**硬编码历史下限**（防「偷偷下调棘轮」）
  E 反向探针（**先证能变红**）：删一个锚 · 改某锚 `l2_gates` · 下调 ratchet · 篡改 blind 列表 ·
    删 manifest 一条 ⇒ C7 必红
  M manifest 运行时登记（v0.9.258 BL-M4）：schema 精确 · 门禁 ⊆ CORE ∧ 锚 ⊆ 账本 ∧ count 自洽 ·
    **coverage.manifest ≡ gate_anchor_manifest（两副本逐元素 · 防漂移）**
  F 红线：生成器零手写证据（`deterministic` + `det.write_text` + 零时钟/随机）· 本门禁 ∈ `CORE_SMOKES`

🔴 `main()` 返回「真值」而非恒 0。
🔴 一律走 `smoke_kit.make_check`（助手单一来源棘轮 J3）。
🔴 本门禁**只读**产品代码 + 读台账；不改任何产品面。
"""

from __future__ import annotations

import importlib.util
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

_LEDGER = os.path.join(_HERE, "reports", "anchor_gate_coverage.json")
_VERIF = os.path.join(_HERE, "reports", "verification_report.json")
_MANIFEST = os.path.join(_HERE, "reports", "gate_anchor_manifest.json")
_GEN = os.path.join(_ROOT, "scripts", "k4_coverage.py")
_PY = sys.executable
_SCHEMA = "lda_anchor_gate_coverage_v1"
_MAN_SCHEMA = "lda_gate_anchor_manifest_v1"

# 🔵 硬编码历史下限（只许上调；用于防「下调棘轮」）
# 🔴 v0.9.258 BL-M4：L2 口径升「文本 ∪ manifest」⇒ 124 → 520，硬下限同步抬到 520。
_HARD_L2_MIN = 522
_HARD_L3_MIN = 65

# 🔴 门禁侧**独立**登记的排除集（不 import 生成器常量 ⇒ 双向锁死）。
#   只允许排除「判决覆盖矩阵本身」的那一个门禁；G1 判据断言两侧集合相等。
_EXCLUDED = {"run_k4_coverage_smoke.py"}

_ANCHOR_RE = re.compile(r"\bB(\d{3})\b")


def _ledger_ids():
    from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
    return set(BENCHMARK_DEFS) | set(BENCHMARK_ORDER)


def _core_smokes():
    path = os.path.join(_HERE, "run_ci_regression.py")
    spec = importlib.util.spec_from_file_location("_ci_k4s", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return list(getattr(m, "CORE_SMOKES", []))


def _indep_gate_scan():
    """门禁侧**独立**重扫（不复用生成器代码路径）：gate → 锚集。"""
    ids = _ledger_ids()
    out = {}
    for name in _core_smokes():
        if name in _EXCLUDED:
            continue
        p = os.path.join(_HERE, name)
        if not os.path.exists(p):
            out[name] = []
            continue
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        keep = []
        for ln in txt.split("\n"):
            if ln.lstrip().startswith("#"):
                continue
            keep.append(ln)
        found = {"B" + n for n in _ANCHOR_RE.findall("\n".join(keep))}
        out[name] = sorted(found & ids)
    return out


def _indep_l1():
    with open(_VERIF, encoding="utf-8") as f:
        d = json.load(f)
    return {r["id"] for r in d.get("results", [])} & _ledger_ids()


def load():
    with open(_LEDGER, encoding="utf-8", newline="") as f:
        raw = f.read()
    return json.loads(raw), raw


def _load_manifest():
    if not os.path.exists(_MANIFEST):
        return None
    with open(_MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def _validate(led):
    r = {}
    ids = _ledger_ids()
    anch = led.get("anchors") or {}
    sm = led.get("summary") or {}
    rat = led.get("ratchet") or {}
    blind = led.get("blind_anchors") or []
    gates = led.get("gates") or {}

    r["A4 anchors 键集 ≡ 账本全集（新增锚必被登记）"] = set(anch) == ids
    total = len(anch)
    l2 = sum(1 for v in anch.values() if (v.get("l2_count") or 0) > 0)
    l3 = sum(1 for v in anch.values() if v.get("l3") is True)
    r["A5 计数守恒（l2+blind=total ∧ l1≤total ∧ l3≤l2）"] = (
        sm.get("anchors_total") == total
        and sm.get("l2_bespoke_covered", 0) + sm.get("l2_blind", 0) == total
        and sm.get("l1_unified_covered", 0) <= total
        and l3 <= l2
        and len(blind) == sum(1 for v in anch.values() if not (v.get("l2_count") or 0)))

    # C 组：独立重算
    ind = _indep_gate_scan()
    r["C1 gates 锚集 ≡ 门禁独立重扫"] = (
        {k: sorted(v) for k, v in gates.items() if v} ==
        {k: v for k, v in ind.items() if v})
    r["C2 L1 集 ≡ verification_report 现算"] = (
        {a for a, v in anch.items() if v.get("l1")} == _indep_l1())
    r["C3 l2/l3 计数 ≡ 从 anchors 现算"] = (
        sm.get("l2_bespoke_covered") == l2 and sm.get("l3_multi_covered") == l3
        and all((v.get("l2_count") or 0) == len(v.get("l2_gates") or [])
                for v in anch.values())
        and all((v.get("l3") is True) == ((v.get("l2_count") or 0) >= 2)
                for v in anch.values()))
    byc = sm.get("by_gate_count") or {}
    r["C4 by_gate_count 分布求和 ≡ l2"] = (
        sum(byc.values()) == l2
        and byc == {k: byc[k] for k in sorted(byc, key=int)})
    r["C5 blind 集 ≡ total − l2（逐元素）"] = (
        set(blind) == {a for a, v in anch.items() if not (v.get("l2_count") or 0)})
    band = sm.get("blind_by_band") or {}
    r["C6 blind_by_band 求和 ≡ blind 总数"] = sum(band.values()) == len(blind)

    # ── C7：L2 = 文本 ∪ manifest（M4 口径真实化）──
    text_anchor_set = set()
    for gs in gates.values():
        text_anchor_set |= set(gs or [])
    man_anchors = set()
    for gs in (led.get("manifest") or {}).values():
        man_anchors |= set(gs or [])
    l2_set = {a for a, v in anch.items() if (v.get("l2_count") or 0) > 0}
    r["C7 L2 ≡ 文本 gates ∪ manifest（逐元素）∧ blind ≡ total − L2"] = (
        l2_set == (text_anchor_set | man_anchors) & ids
        and set(blind) == ids - l2_set
        and sm.get("l2_text_covered") == len(text_anchor_set & ids)
        and sm.get("l2_manifest_covered") == len(man_anchors & ids))

    # D 组：棘轮
    r["D1 l2 ≥ ratchet.l2_min"] = l2 >= int(rat.get("l2_min", 10 ** 9))
    r["D2 l3 ≥ ratchet.l3_min"] = l3 >= int(rat.get("l3_min", 10 ** 9))
    r["D3 ratchet 不低于硬编码历史下限（防下调）"] = (
        int(rat.get("l2_min", 0)) >= _HARD_L2_MIN
        and int(rat.get("l3_min", 0)) >= _HARD_L3_MIN)
    return r


def main():
    print("=" * 78)
    print("K4 门禁×锚覆盖矩阵门禁（缺口 G-K-6）")
    print("=" * 78)

    # ── A 表结构 ──────────────────────────────────────────────────
    check("A1 台账文件存在", os.path.exists(_LEDGER),
          "path=%s" % os.path.relpath(_LEDGER, _ROOT))
    led, raw = load()
    need = ("schema", "generated_by", "roadmap", "subject", "method",
            "summary", "ratchet", "anchors", "gates", "blind_anchors",
            "excluded_gates")
    check("A2 顶层字段齐备", all(k in led for k in need),
          "缺=%s" % [k for k in need if k not in led])
    check("A3 schema 精确", led.get("schema") == _SCHEMA,
          "got=%r" % led.get("schema"))
    # 🔴 计数一律**现读台账**打印，不写死（写死的横幅会随加锚静默过期）
    _sm = led.get("summary") or {}
    print("  · 现读台账：%s 锚 × %s 门禁 · L2 %s · L3 %s · 盲区 %s"
          % (_sm.get("anchors_total"), _sm.get("gates_scanned"),
             _sm.get("l2_bespoke_covered"), _sm.get("l3_multi_covered"),
             _sm.get("l2_blind")))
    r = _validate(led)
    check("A4 anchors 键集 ≡ 账本全集（新增锚必被登记）", r["A4 anchors 键集 ≡ 账本全集（新增锚必被登记）"],
          "表内=%d 账本=%d" % (len(led.get("anchors") or {}), len(_ledger_ids())))
    check("A5 计数守恒（l2+blind=total ∧ l1≤total ∧ l3≤l2）",
          r["A5 计数守恒（l2+blind=total ∧ l1≤total ∧ l3≤l2）"],
          "summary=%s" % json.dumps(led.get("summary") or {}, ensure_ascii=False)[:150])

    # ── B 三件套 ──────────────────────────────────────────────────
    p = subprocess.run([_PY, _GEN], cwd=_ROOT, capture_output=True, text=True,
                       errors="replace")
    check("B1 子进程重跑生成器 ≡ 磁盘台账（逐字节）",
          p.returncode == 0 and p.stdout == raw,
          "rc=%d len(gen)=%d vs len(ledger)=%d" % (p.returncode, len(p.stdout), len(raw)))
    p2 = subprocess.run([_PY, _GEN], cwd=_ROOT, capture_output=True, text=True,
                        errors="replace")
    check("B2 生成器幂等（两次重跑逐字节相同）",
          p2.returncode == 0 and p2.stdout == p.stdout,
          "same=%s" % (p2.stdout == p.stdout))
    with open(_LEDGER, "rb") as f:
        binraw = f.read()
    check("B3 台账 LF only（无 CR）", b"\r" not in binraw,
          "CR=%d" % binraw.count(b"\r"))

    # ── C 事实性 ───────────────────────────────────────────────────
    for k in ("C1 gates 锚集 ≡ 门禁独立重扫", "C2 L1 集 ≡ verification_report 现算",
              "C3 l2/l3 计数 ≡ 从 anchors 现算", "C4 by_gate_count 分布求和 ≡ l2",
              "C5 blind 集 ≡ total − l2（逐元素）", "C6 blind_by_band 求和 ≡ blind 总数",
              "C7 L2 ≡ 文本 gates ∪ manifest（逐元素）∧ blind ≡ total − L2"):
        check(k, r[k], "")

    # ── D 棘轮 ────────────────────────────────────────────────────
    for k in ("D1 l2 ≥ ratchet.l2_min", "D2 l3 ≥ ratchet.l3_min",
              "D3 ratchet 不低于硬编码历史下限（防下调）"):
        check(k, r[k], "")

    # ── M manifest 运行时登记（v0.9.258 BL-M4）──────────────────────
    manj = _load_manifest()
    check("M1 gate_anchor_manifest.json 存在 ∧ schema 精确",
          manj is not None and manj.get("schema") == _MAN_SCHEMA,
          "schema=%r" % ((manj or {}).get("schema")))
    regs = (manj or {}).get("registries") or {}
    core_names = set(_core_smokes())
    man_gate_ok = bool(regs) and all(g in core_names for g in regs)
    man_anch_ok = all(set(v.get("anchors") or []) <= _ledger_ids() for v in regs.values())
    man_cnt_ok = all(v.get("count") == len(v.get("anchors") or []) for v in regs.values())
    check("M2 manifest 门禁 ⊆ CORE_SMOKES ∧ 锚 ⊆ 账本 ∧ count ≡ len(anchors)",
          man_gate_ok and man_anch_ok and man_cnt_ok,
          "gates=%s gate_ok=%s anch_ok=%s cnt_ok=%s"
          % (sorted(regs), man_gate_ok, man_anch_ok, man_cnt_ok))
    cov_man = {k: sorted(v) for k, v in (led.get("manifest") or {}).items()}
    file_man = {k: sorted(v.get("anchors") or []) for k, v in regs.items()}
    check("M3 coverage.manifest ≡ gate_anchor_manifest.registries（两副本逐元素 · 防漂移）",
          cov_man == file_man,
          "coverage=%d file=%d" % (len(cov_man), len(file_man)))

    # ── E 反向探针 ────────────────────────────────────────────────
    def mutated(fn):
        clone = json.loads(json.dumps(led))
        fn(clone)
        rr = _validate(clone)
        return [k for k, v in rr.items() if not v]

    def m_drop(x):
        k = sorted((x.get("anchors") or {}).keys())[0]
        x["anchors"].pop(k)

    def m_gates(x):
        for a, v in (x.get("anchors") or {}).items():
            if (v.get("l2_count") or 0) > 0:
                v["l2_gates"] = v["l2_gates"][:-1]
                v["l2_count"] = len(v["l2_gates"])
                return

    def m_ratchet(x):
        x["ratchet"]["l2_min"] = 1
        x["ratchet"]["l3_min"] = 1

    def m_blind(x):
        x["blind_anchors"] = (x.get("blind_anchors") or [])[:-1]

    red1 = mutated(m_drop)
    check("E1 反向探针：删一个锚 ⇒ A4 必红", "A4 anchors 键集 ≡ 账本全集（新增锚必被登记）" in red1,
          "红项=%s" % red1[:3])
    red2 = mutated(m_gates)
    check("E2 反向探针：改某锚 l2_gates ⇒ C3 必红",
          "C3 l2/l3 计数 ≡ 从 anchors 现算" in red2, "红项=%s" % red2[:3])
    red3 = mutated(m_ratchet)
    check("E3 反向探针：下调 ratchet ⇒ D3 必红",
          "D3 ratchet 不低于硬编码历史下限（防下调）" in red3, "红项=%s" % red3[:3])
    red4 = mutated(m_blind)
    check("E4 反向探针：篡改 blind 列表 ⇒ C5 必红",
          "C5 blind 集 ≡ total − l2（逐元素）" in red4, "红项=%s" % red4[:3])

    def m_manifest(x):
        man = x.get("manifest") or {}
        for g in sorted(man):
            if man[g]:
                man[g] = man[g][:-1]
                return

    red5 = mutated(m_manifest)
    check("E5 反向探针：删 manifest 一条 ⇒ C7 必红（M4 双向锁的负向验证）",
          "C7 L2 ≡ 文本 gates ∪ manifest（逐元素）∧ blind ≡ total − L2" in red5,
          "红项=%s" % red5[:3])

    # ── G 排除面锁死（防「为绿而扩大排除」） ────────────────────────
    exg = led.get("excluded_gates") or {}
    check("G1 生成器 excluded_gates 键集 ≡ 门禁独立登记（只许排除自身）",
          set(exg) == _EXCLUDED and len(exg) == 1,
          "生成器=%s 门禁=%s" % (sorted(exg), sorted(_EXCLUDED)))
    check("G2 summary 计数与排除面自洽（core = scanned + excluded）",
          (led.get("summary") or {}).get("core_smokes")
          == (led.get("summary") or {}).get("gates_scanned", -1) + len(_EXCLUDED),
          "summary=%s" % json.dumps({k: (led.get("summary") or {}).get(k)
                                     for k in ("core_smokes", "gates_scanned",
                                               "gates_excluded")}, ensure_ascii=False))

    # ── F 红线 ────────────────────────────────────────────────────
    with open(_GEN, encoding="utf-8") as f:
        gsrc = f.read()
    wall = ("datetime.now", "time.strftime", "time.time", "random.",
            "uuid4", "json.dump(", "mkdtemp")
    hits = [t for t in wall if t in gsrc]
    check("F1 生成器零手写证据（走 deterministic · 零时钟/随机）",
          "deterministic" in gsrc and "det.write_text" in gsrc and not hits,
          "hits=%s" % hits)
    in_core = "run_k4_coverage_smoke.py" in _core_smokes()
    check("F2 本门禁自身 ∈ CORE_SMOKES（自食其规则）", in_core, "in_core=%s" % in_core)

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("K4 覆盖矩阵门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
