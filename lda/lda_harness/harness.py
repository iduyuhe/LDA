"""LDA 验证 harness · 核心框架。

职责：把 L0 IR（或内置默认）的 verification.benchmarks 与确定性黄金参考
挂钩，运行候选求解器输出，按 tol 判定 pass/fail，产出结果供人验收。
黄金参考 = 非 AI 的物理定律锚（见 golden.py / 《白皮书》§11）+ 实证大数据锚
（D-62：E 题 golden 来自真实测量语料，见 empirical_bank.py）。
"""
import os

from .golden import golden_value, golden_with_source


def _default_empirical_anchor():
    """加载默认实证语料锚（seed_empirical.json + 社区落库增量）。

    供 VerificationHarness 默认注入；语料缺失时返回 None（E 题诚实降级）。
    """
    try:
        from .empirical_bank import EmpiricalCorpus, EmpiricalAnchor
    except Exception:  # noqa: BLE001 —— empirical_bank 依赖缺失时降级
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    seed = os.path.join(here, "seed_empirical.json")
    corpus = EmpiricalCorpus.load(seed)
    contrib = os.path.join(os.path.dirname(here), "lda_pdk",
                           "empirical_contributions.json")
    if os.path.exists(contrib):
        try:
            extra = EmpiricalCorpus.load(contrib)
            corpus._items.update(extra._items)
        except Exception:  # noqa: BLE001 —— 增量损坏不阻断默认语料
            pass
    if not corpus._items:
        return None
    return EmpiricalAnchor(corpus)


class BenchmarkResult:
    def __init__(self, bid, metric, golden, candidate, tol, oracle, passed,
                 note="", source="", independent=None):
        self.bid = bid
        self.metric = metric
        self.golden = golden
        self.candidate = candidate
        self.tol = tol
        self.oracle = oracle
        self.passed = passed
        self.note = note
        self.source = source  # 黄金参考事实来源（physical-law / meep-fdtd / ...）
        # v0.9.15（P0-2）：该项是否由**独立候选求解器**判出。
        #   True  = 走独立候选（真可证伪，计入 verified）
        #   False = 走占位自证候选（candidate≡golden，|diff|≡0，零验证价值）
        #   None  = 未标注（旧路径，如 L3 AI / Perturbed 候选）→ 报告沿用旧的整体判定
        # 三态设计是为渐进式改造：只有显式路由的候选才改变 verified 语义，
        # 其余路径行为完全不变（避免一次性改动波及 MCP/L1/CLI 各调用方）。
        self.independent = independent


class VerificationHarness:
    def __init__(self, defs, anchor=None):
        self.defs = defs
        # D-62 实证大数据锚（EmpiricalAnchor）——第二道非 AI ground。
        # anchor 未显式注入时默认加载内置语料（seed_empirical.json + 社区落库
        # empirical_contributions.json），使 E 题在 CLI/默认路径真实生效；
        # 显式传 None 的场景可自行控制（如纯物理定律演示）。
        if anchor is None:
            anchor = _default_empirical_anchor()
        self.anchor = anchor

    def resolve_specs(self, l0_ir=None):
        """解析 benchmark 规格。

        若给定 L0 IR 且含 verification.benchmarks，则以其为准（target/tol/oracle
        可被 L0 覆盖）；否则用内置 BENCHMARK_DEFS 默认规格。
        返回规格列表：{id, metric, target, tol, oracle, params, golden_fn, resolved}

        D-62 实证锚题（anchor=empirical，golden_fn=None）：target 不在此解析——
        由 run() 经 EmpiricalAnchor 从实测语料实时取（第二道非 AI ground，死标量比对）。
        """
        specs = []
        benchmarks = []
        if l0_ir:
            benchmarks = (l0_ir.get("verification") or {}).get("benchmarks") or []
        if benchmarks:
            for b in benchmarks:
                bid = b["id"]
                d = self.defs.get(bid)
                if not d:
                    specs.append({"id": bid, "metric": b.get("metric"),
                                  "tol": b.get("tol"), "oracle": b.get("oracle"),
                                  "params": {}, "golden_fn": None, "resolved": False})
                    continue
                params = dict(d["default_params"])
                if b.get("params"):        # L0 IR 携带设计实际几何参数 → 覆盖默认
                    params.update(b["params"])
                anchor = d.get("anchor")
                cmp = b.get("cmp", d.get("cmp", "abs"))
                # D-63：empirical_unverified（B 级待溯源）同走实证锚分支，单独标注
                if anchor in ("empirical", "empirical_unverified"):
                    specs.append({
                        "id": bid, "metric": b.get("metric", d["metric"]),
                        "target": None, "tol": b.get("tol", d["tol"]),
                        "oracle": b.get("oracle", d["oracle"]),
                        "params": params, "golden_fn": None,
                        "anchor": anchor, "empirical_id": d.get("empirical_id"),
                        "cmp": cmp, "resolved": True})
                    continue
                target = b.get("target", d["golden_fn"](**params))
                specs.append({
                    "id": bid, "metric": b.get("metric", d["metric"]),
                    "target": target, "tol": b.get("tol", d["tol"]),
                    "oracle": b.get("oracle", d["oracle"]),
                    "params": params, "golden_fn": d["golden_fn"],
                    "cmp": cmp, "resolved": True,
                })
        else:
            for bid in sorted(self.defs.keys()):
                d = self.defs[bid]
                params = dict(d["default_params"])
                anchor = d.get("anchor")
                cmp = d.get("cmp", "abs")
                # D-63：empirical_unverified（B 级待溯源）同走实证锚分支，单独标注
                if anchor in ("empirical", "empirical_unverified"):
                    specs.append({
                        "id": bid, "metric": d["metric"],
                        "target": None, "tol": d["tol"],
                        "oracle": d["oracle"], "params": params,
                        "golden_fn": None, "anchor": anchor,
                        "empirical_id": d.get("empirical_id"),
                        "cmp": cmp, "resolved": True})
                    continue
                specs.append({
                    "id": bid, "metric": d["metric"],
                    "target": d["golden_fn"](**params), "tol": d["tol"],
                    "oracle": d["oracle"], "params": params,
                    "golden_fn": d["golden_fn"], "cmp": cmp, "resolved": True,
                })
        return specs

    def run(self, specs, candidate):
        """运行候选求解器并与黄金参考比对。

        candidate: callable(spec, golden, params) -> float
        返回 BenchmarkResult 列表。

        D-62：实证锚题（spec.anchor=empirical）的 golden 经 self.anchor.resolve
        （EmpiricalAnchor）从实测语料取——来源='empirical-measurement'（真实测量，
        非 AI 意见）。anchor 未注入时实证锚题按未解析处理（诚实降级）。
        """
        results = []
        for s in specs:
            # P0-2：若候选对象能自证独立性（IndependentCandidateRouter），按题标注；
            # 否则保持 None，报告沿用旧的整体判定（对既有路径零影响）。
            _probe = getattr(candidate, "is_independent", None)
            _indep = bool(_probe(s["id"])) if callable(_probe) else None
            if not s.get("resolved"):
                results.append(BenchmarkResult(
                    s["id"], s.get("metric"), None, None, s.get("tol"),
                    s.get("oracle"), False, "未解析：缺少黄金参考定义",
                    s.get("oracle")))
                continue
            if s.get("anchor") in ("empirical", "empirical_unverified"):
                if self.anchor is None:
                    results.append(BenchmarkResult(
                        s["id"], s["metric"], None, None, s["tol"],
                        s["oracle"], False,
                        "实证锚未注入（语料库未加载）——诚实降级不判 PASS",
                        "empirical-missing"))
                    continue
                # 溯源门禁：A 级（empirical）强制要求可公开溯源；
                # B 级（empirical_unverified）显式放行取值但标注，不计入可溯源计数
                golden, source, src_note = self.anchor.resolve(
                    s.get("empirical_id"),
                    require_traceable=(s.get("anchor") == "empirical"))
                if golden is None:
                    results.append(BenchmarkResult(
                        s["id"], s["metric"], None, None, s["tol"],
                        s["oracle"], False, src_note, source))
                    continue
                candidate_val = candidate(s, golden, s["params"])
                passed = abs(candidate_val - golden) <= s["tol"]
                results.append(BenchmarkResult(
                    s["id"], s["metric"], golden, candidate_val, s["tol"],
                    s["oracle"], passed, src_note, source,
                    independent=_indep))
                continue
            golden, source, src_note = golden_with_source(s["id"], s["params"])
            candidate_val = candidate(s, golden, s["params"])
            passed = _cmp_ok(candidate_val, golden, s["tol"], s.get("cmp", "abs"))
            results.append(BenchmarkResult(
                s["id"], s["metric"], golden, candidate_val, s["tol"],
                s["oracle"], passed, src_note, source,
                independent=_indep))
        return results


def _cmp_ok(candidate_val, golden, tol, cmp):
    """判定算子。

    - 'abs'（默认）：|candidate - golden| ≤ tol（解析标定锚，B1-B19）
    - 'le'：candidate ≤ golden + tol（物理定律不等式锚，如 B19 无源无增益）
    - 'ge'：candidate ≥ golden - tol（物理定律下界锚，如设计守则下限）
    """
    if cmp == "le":
        return candidate_val <= golden + tol
    if cmp == "ge":
        return candidate_val >= golden - tol
    return abs(candidate_val - golden) <= tol


# ------------------------- 候选求解器（stand-in） -------------------------
class ReferenceCandidate:
    """参考求解器：返回黄金参考值本身——代表一个正确的求解器。

    真实场景中应由 L3 的 AI 写内核替代；此处用于演示 harness 闭环（pass）。
    """

    def __call__(self, spec, golden, params):
        return golden


class PerturbedCandidate:
    """扰动求解器：golden·(1+rel_err)——用于演示 harness 的 fail 检测能力。"""

    def __init__(self, rel_err):
        self.rel_err = rel_err

    def __call__(self, spec, golden, params):
        return golden * (1.0 + self.rel_err)


class _SpecShim:
    """把 harness 的 dict spec 适配成独立候选所需的最小对象接口。

    路径①（build_harness_specs）的候选函数吃 VerificationSpec（需 .spec_id /
    .params）；路径②（VerificationHarness.run）传的是 dict。此 shim 让同一批
    独立候选函数**零改动复用**于两条路径，避免同一物理求解器写两份。
    """
    __slots__ = ("spec_id", "params")

    def __init__(self, spec_id, params):
        self.spec_id = spec_id
        self.params = params


class IndependentCandidateRouter:
    """按 spec_id 把锚题路由到独立候选求解器（v0.9.15 · P0-2）。

    背景（D-64 / 战略审计 R1）：`ReferenceCandidate` 直接返回 golden ⇒
    |cand−golden|≡0 恒 PASS、零验证价值。项目里其实**已有**严格数值求解器
    （电荷基对角化、多能级+Fock 对角化），只是没接到 CLI/报告这条路径。

    设计原则（诚实优先）：
    - **未登记的锚题仍落回参考候选**，|diff|≡0 —— 不假装已独立。
    - **候选求解失败一律抛异常上浮**，绝不静默回退 golden（否则又变自证桩）。
    - 独立性按题标注（BenchmarkResult.independent），报告据此**按题**统计
      verified，而不是沿用"全自证 / 全独立"的整体布尔（混合态下会失真）。
    """

    def __init__(self, fallback=None):
        self._fallback = fallback or ReferenceCandidate()

    def resolve_key(self, bid):
        from .benchmarks import BENCHMARK_DEFS
        return (BENCHMARK_DEFS.get(bid) or {}).get("candidate")

    def is_independent(self, bid):
        """该锚题是否具备**已登记**的独立候选。"""
        from .verification_adapters import BENCHMARK_CANDIDATES
        key = self.resolve_key(bid)
        return bool(key) and key in BENCHMARK_CANDIDATES

    def __call__(self, spec, golden, params):
        from .verification_adapters import BENCHMARK_CANDIDATES
        bid = spec.get("id")
        key = self.resolve_key(bid)
        fn = BENCHMARK_CANDIDATES.get(key) if key else None
        if fn is None:
            return self._fallback(spec, golden, params)
        return fn(_SpecShim(bid, params), golden)

    def describe(self):
        """供报告 meta 显示：本次路由覆盖了多少道独立候选。"""
        from .benchmarks import BENCHMARK_DEFS
        ind = [b for b in sorted(BENCHMARK_DEFS) if self.is_independent(b)]
        return ind
