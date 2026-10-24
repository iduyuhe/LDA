"""全局纪律门禁登记表 —— K4 覆盖矩阵的**第三档（形态级）**数据源。

═══════════════════════ 这份文件解决什么问题 ═══════════════════════

K4 的覆盖矩阵原本只有两档，都只认「**逐锚**」：

| 档 | 来源 | 形态 |
|---|---|---|
| L2-text | 门禁源码里的**锚号字面量** | 逐锚 |
| L2-manifest | `gate_anchor_manifest.json` 的**运行时登记** | 逐锚 |

但平台里存在另一类门禁：它们**一个锚号都不写**，而是 `for bid in BENCHMARK_DEFS`
遍历全账本，对**某一类锚**做统一断言。典型是
`run_self_certified_lock_smoke`：「每道 self_certified 锚都必须有锁定原因」。

这类门禁对 K4 是**完全不可见**的 —— 于是像 B18 这样的锚在矩阵里显示
`l2_count == 0`，读起来像「无人看守的裸锚」，而事实是它被一道纪律门禁守着。
**这不是判决错误，是可观测性缺口**：矩阵看不见"纪律级覆盖"这一层。

═══════════════════════ 三条硬纪律（必读）═══════════════════════

① 🔴 **`l2_global` 绝不并入 `l2_count` / `l3` / `blind`。**
   纪律级覆盖只断言「元数据合规」，**不断言任何数值**。
   若把它算进数值覆盖，独立率与覆盖率会**虚高** —— 那是虚报，不是改进。
   本档只作为**平行的诊断列**输出，K4 的 A5 计数守恒判据对此显式设条件。

② 🔴 **登记制，不许静态猜测。**
   不做「源码里有 `for ... in BENCHMARK_DEFS` ⇒ 视为覆盖」的自动推断：
   平台里有 **21 道**门禁遍历全账本，其中多数只是「筛子集做统计」，
   并非「对每个遍历到的锚独立断言」。自动推断会把 21 道全算成覆盖 ⇒ 档位失去判别力。
   故**逐条登记**，每条须写清 `asserts`（断言什么）与 `caliber`（区分度）。

③ 🔴 **每条都要能被反向证伪。**
   `select` 是**活谓词**（读账本现算），不是写死的锚号列表 ——
   于是「新增一道 self_certified 锚 ⇒ 自动纳入本档」。
   `run_k4_coverage_smoke` 的 L3/L4 判据会做**突变**：把一道 strict 锚临时改成
   self_certified，本档必自动多出它；若不多出 ⇒ 谓词是死的 ⇒ 判红。

═══════════════════════ 覆盖力（caliber）两级 ═══════════════════════

| caliber | 含义 | 对「盲区」有无区分度 |
|---|---|---|
| `ALL_LEDGER` | 字段纪律，对**全部**锚恒成立 | **无**（只能证明"不是无人看守"，不能证明"这道锚被特别关注"） |
| `SUBSET` | 只对**某一类**锚成立 | **有**（能说明这道锚属于被纪律专门管住的类别） |

🔴 区分这两级很重要：`maturity_baseline` 的字段检查覆盖全部 541 锚，
若把它当"覆盖"，则所有盲区都变成"已覆盖" ⇒ **盲区计数塌成 0**，这是自欺。
故 K4 分别统计，且 `l2_global_only` 只认 `SUBSET` 作为"有实质纪律覆盖"的证据。

═══════════════════════ 边界 ═══════════════════════

- 这是**可观测性登记**，不产生锚、不改任何判决；
- 「有纪律覆盖」**不等于**「该锚的数值被验证过」——两者必须分开陈述；
- 本模块是**非门禁模块**：K4 只扫 CORE_SMOKES 里的门禁文件，故此处写机制名安全；
  但仍**不写任何锚号字面量**（全用谓词），以免有人复制到门禁里造成 L2 虚高。
"""

from typing import Any, Dict, List

ROLE = ("D-227 · 全局纪律门禁登记表 —— 让 K4 覆盖矩阵看见「按类遍历全账本」的门禁，"
        "把「纪律级覆盖」与「数值级覆盖」分开计量。非门禁模块。")
ANCHORABLE = False

#: 机制类别（门禁断言：用到的每个 class 必须在此登记，防「自造新分类」）
MECHANISM_CLASSES: Dict[str, str] = {
    "TIER_DISCIPLINE":
        "按 VMM 分类遍历账本，断言某分类下的锚都带齐该分类要求的凭据（如锁定原因）",
    "FIELD_DISCIPLINE":
        "遍历全账本，断言每道锚都带齐必备元数据字段（成熟度档 / provenance / 升级路径）",
}

#: 覆盖力（门禁断言：用到的每个 caliber 必须在此登记）
CALIBERS: Dict[str, str] = {
    "ALL_LEDGER": "对全部锚恒成立 ⇒ 对盲区**无区分度**，不可当作\"该锚被特别看守\"",
    "SUBSET": "只对某一类锚成立 ⇒ **有区分度**，可说明该锚属于被纪律专门管住的类别",
}


def _select_self_certified(defs: Dict[str, Any]) -> List[str]:
    """self_certified 分类的全部锚（读 `_vmm_classify` 现算，不写死锚号）。"""
    from lda_harness.benchmarks import _vmm_classify
    return sorted(k for k, v in defs.items() if _vmm_classify(v) == "self_certified")


def _select_all(defs: Dict[str, Any]) -> List[str]:
    """全账本（字段纪律门禁的覆盖面）。"""
    return sorted(defs)


#: 登记面。**逐条**：gate → 机制 / 覆盖面谓词 / 断言内容 / 覆盖力。
GLOBAL_GATES: Dict[str, Dict[str, Any]] = {
    "run_self_certified_lock_smoke.py": {
        "mechanism": "TIER_DISCIPLINE",
        "select": _select_self_certified,
        "asserts": "每道 self_certified 锚都有四类锁定原因之一（provenance + upgrade_path 非空且可归类）",
        "caliber": "SUBSET",
        "note": "F-8 的正解：像 B18 这类锚在数值面是裸的（l2_count=0），"
                "但在纪律面被本门禁 ③ 守着 —— 两件事必须分开陈述",
    },
    "run_maturity_baseline_smoke.py": {
        "mechanism": "FIELD_DISCIPLINE",
        "select": _select_all,
        "asserts": "每道锚都带 maturity_tier / provenance；self_certified 另须带 upgrade_path",
        "caliber": "ALL_LEDGER",
        "note": "对全部锚恒成立 ⇒ **对盲区无区分度**；登记它是为了如实说明"
                "\"盲区锚也不是无人看守\"，但不能据此把它们从盲区里划掉",
    },
}

#: 🔴 已显式**排除**的遍历型门禁（防止后人以为"漏了"而随手补登记）。
#: 判据：遍历全账本但只是「筛子集做统计/求和」，或断言的是聚合量而非逐锚属性。
EXCLUDED_TRAVERSING_GATES: Dict[str, str] = {
    "run_three_class_consistency_smoke.py":
        "遍历全账本，但断言的是**分类标签自洽**（tier 与字段一致）⇒ 对每道锚恒真，"
        "无判别力；算进覆盖会让\"纪律覆盖\"退化成同义反复",
    "run_p0_count_guard_sync_smoke.py":
        "遍历全账本只为**求和核对计数**，不对任何单锚断言",
    "run_provenance_audit.py":
        "只遍历 E 前缀实证锚做引证分级，不构成对量子/B 锚的覆盖",
    "run_statistical_anchor_smoke.py":
        "遍历全账本做**统计分布**断言（聚合量），非逐锚属性",
    "run_benchmark_falsifiability_smoke.py":
        "遍历全账本做**可证伪性抽检**，判据落在抽样结果上，非逐锚独立断言",
}


def global_coverage(defs: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """现算：锚 → 覆盖它的纪律门禁列表（含机制与覆盖力）。

    纯函数、无状态、确定性（同账本 ⇒ 同输出），供 K4 生成器直接调用。
    """
    out: Dict[str, List[Dict[str, str]]] = {}
    for gate in sorted(GLOBAL_GATES):
        spec = GLOBAL_GATES[gate]
        for aid in spec["select"](defs):
            out.setdefault(aid, []).append({
                "gate": gate,
                "mechanism": spec["mechanism"],
                "caliber": spec["caliber"],
            })
    for aid in out:
        out[aid].sort(key=lambda r: (r["caliber"] != "SUBSET", r["gate"]))
    return out


def registry_stats() -> Dict[str, Any]:
    """登记面自述（门禁据此判「登记非空 + 类别全登记」）。"""
    mech = sorted({s["mechanism"] for s in GLOBAL_GATES.values()})
    cal = sorted({s["caliber"] for s in GLOBAL_GATES.values()})
    return {
        "n_gates": len(GLOBAL_GATES),
        "n_excluded": len(EXCLUDED_TRAVERSING_GATES),
        "mechanisms_used": mech,
        "calibers_used": cal,
        "mechanisms_registered": sorted(MECHANISM_CLASSES),
        "calibers_registered": sorted(CALIBERS),
        "subset_gates": sorted(g for g, s in GLOBAL_GATES.items() if s["caliber"] == "SUBSET"),
    }


def run_selfchecks(verbose: bool = True) -> bool:
    """契约自检（8 条）：登记面完整性 + 类别全登记 + 谓词是活的 + 排除面不重叠。"""
    ok = True
    checks = []

    def chk(name, cond, detail=""):
        nonlocal ok
        checks.append((name, bool(cond), detail))
        if not cond:
            ok = False

    st = registry_stats()
    chk("G1 登记面非空（≥1 道全局纪律门禁）", st["n_gates"] >= 1, "n=%d" % st["n_gates"])
    chk("G2 机制类别全登记（用到的 class 都在 MECHANISM_CLASSES）",
        set(st["mechanisms_used"]) <= set(st["mechanisms_registered"]),
        "used=%s" % st["mechanisms_used"])
    chk("G3 覆盖力全登记", set(st["calibers_used"]) <= set(st["calibers_registered"]),
        "used=%s" % st["calibers_used"])
    chk("G4 每条登记都写清了 asserts（不许空口登记）",
        all(str(s.get("asserts", "")).strip() for s in GLOBAL_GATES.values()),
        "n=%d" % st["n_gates"])
    chk("G5 登记面与排除面不相交（同一门禁不能既登记又排除）",
        not (set(GLOBAL_GATES) & set(EXCLUDED_TRAVERSING_GATES)),
        "overlap=%s" % sorted(set(GLOBAL_GATES) & set(EXCLUDED_TRAVERSING_GATES)))

    from lda_harness.benchmarks import BENCHMARK_DEFS as _D
    cov = global_coverage(_D)
    chk("G6 谓词是活的：覆盖结果非空（不是写死空列表）", len(cov) > 0, "n_covered=%d" % len(cov))
    chk("G7 覆盖结果 ⊆ 账本（谓词不许造出账本外的锚）",
        set(cov) <= set(_D), "extra=%s" % sorted(set(cov) - set(_D))[:5])

    # G8 谓词随账本变化（突变一枚合成账本，覆盖面必须跟着变）
    # 🔴 突变方式必须对齐 `_vmm_classify` 的真实判据：它按「candidate 键是否存在」分类，
    #    改 provenance/upgrade_path 是**无效突变**（分类器不看这两个字段）——
    #    这正是「突变必须打在被测判据的判据点上」的实例。
    synth = dict(_D)
    strict_key = next((k for k, v in sorted(_D.items())
                       if _vmm_safe(v) == "strict_independent"), None)
    mutated = False
    detail = "strict_key=None"
    if strict_key is not None:
        flipped = {kk: vv for kk, vv in _D[strict_key].items()
                   if kk not in ("candidate", "candidate_status")}
        synth[strict_key] = flipped
        base = len(global_coverage(_D).get(strict_key, []))
        after = len(global_coverage(synth).get(strict_key, []))
        mutated = (after > base) and _vmm_safe(flipped) == "self_certified"
        detail = "%s 覆盖 %d→%d 条 · 突变后分类=%s" % (
            strict_key, base, after, _vmm_safe(flipped))
    chk("G8 🔴 谓词随账本变化：把一道 strict 锚的 candidate 键摘掉（= 分类器眼中的 self_certified）"
        " ⇒ 本档必自动多出它", mutated, detail)

    if verbose:
        for n, c, d in checks:
            print("  [%s] %s%s" % ("PASS" if c else "FAIL", n, ("  |  " + d) if d else ""))
        print("  全局纪律门禁登记表自检：%d/%d PASS" % (sum(1 for _, c, _ in checks if c), len(checks)))
    return ok


def _vmm_safe(defn: Dict[str, Any]) -> str:
    """`_vmm_classify` 的容错包装（自检用，不让单条坏定义打断整个自检）。"""
    from lda_harness.benchmarks import _vmm_classify
    try:
        return _vmm_classify(defn)
    except Exception:                                  # noqa: BLE001
        return "?"


if __name__ == "__main__":
    raise SystemExit(0 if run_selfchecks() else 1)
