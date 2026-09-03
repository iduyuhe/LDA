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


# 候选三分类（v0.9.16 · P0-3）：与对外账本 /api/verification_ledger 同一判序，
# 全库唯一定义处。判序固定为「先判降级 → 再查登记表 → 否则自证桩」。
#   strict_independent   = 走方法学不同源的独立求解，|diff|≠0，计入 verified
#   degraded_ordinal     = 有独立候选但与 golden 几何不同源/精度不足，仅量级参考，
#                          **不计入 verified**（否则接线越多越假绿）
#   self_consistent_stub = candidate≡golden，|diff|≡0 恒 PASS，零验证价值
CANDIDATE_CLASS_STRICT = "strict_independent"
CANDIDATE_CLASS_DEGRADED = "degraded_ordinal"
CANDIDATE_CLASS_STUB = "self_consistent_stub"


class BenchmarkResult:
    def __init__(self, bid, metric, golden, candidate, tol, oracle, passed,
                 note="", source="", independent=None, candidate_class=None):
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
        # v0.9.16（P0-3）：细粒度三分类（strict/degraded/stub），None=旧路径未标注。
        # 有了它，报告不必再靠「independent 的补集」去猜自证桩数量
        # （此前 E2 是 degraded 却被算进 stub，导致路径② stub=44、三分类 stub=43
        # 两套口径打架，只能靠注释解释；现在三分类本身就是一等公民）。
        self.candidate_class = candidate_class


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
            # P0-3：优先消费**三分类** API（candidate_class）——只有它才能把
            # degraded 与 stub 分开；旧对象（L3 AI / Perturbed）只有 is_independent，
            # 退化为二态、candidate_class 留 None，行为与 v0.9.15 完全一致。
            _cls_probe = getattr(candidate, "candidate_class", None)
            _ind_probe = getattr(candidate, "is_independent", None)
            if callable(_cls_probe):
                _cls = _cls_probe(s["id"])
                _indep = (_cls == CANDIDATE_CLASS_STRICT)
            elif callable(_ind_probe):
                _cls = None
                _indep = bool(_ind_probe(s["id"]))
            else:
                _cls, _indep = None, None
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
                # 🔴 v0.9.25：empirical 分支曾硬编码 abs——与 path①/empirical smoke
                # 同根的 cmp_abs 副本（latent，当前 E 锚全为 abs 故未炸）。统一走
                # _cmp_ok 分发（cmp 字段语义与 path① 一致）。
                passed = _cmp_ok(candidate_val, golden, s["tol"], s.get("cmp", "abs"))
                results.append(BenchmarkResult(
                    s["id"], s["metric"], golden, candidate_val, s["tol"],
                    s["oracle"], passed, src_note, source,
                    independent=_indep, candidate_class=_cls))
                continue
            golden, source, src_note = golden_with_source(s["id"], s["params"])
            candidate_val = candidate(s, golden, s["params"])
            passed = _cmp_ok(candidate_val, golden, s["tol"], s.get("cmp", "abs"))
            results.append(BenchmarkResult(
                s["id"], s["metric"], golden, candidate_val, s["tol"],
                    s["oracle"], passed, src_note, source,
                    independent=_indep, candidate_class=_cls))
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


def candidate_responds(spec, cand_fn, oracle_value, rel=0.10,
                       thresh=1e-12) -> bool:
    """候选是否对参数扰动有**物理响应** —— 真候选 vs 自证桩的**行为判据**。

    🔴🔴🔴 **全库唯一权威定义处**（v0.9.24）。`run_harness.py`（路径②）与
    `run_benchmark_falsifiability_smoke.py`（路径①⑧）**必须都调这里**，
    否则两处判据漂移会当场打架（v0.9.24 实测：只升 smoke 没升 CLI ⇒
    smoke 8/8 全绿而 `run_harness.py` 断言 AssertionError 报 `假独立=['B10']`）。

    **为什么需要它**（v0.9.24 · 由 B10 触发）：
    原判据 `|cand − golden| < 1e-12 ⇒ 自证桩` 在 B10 上**误判**。B10 的候选是
    真的 4×4 Liouvillian 超算子 RK4 积分（三条**可标定**自校锚 + 六路反向扰动
    全部抓住，信号 1.5e-5），但生产档位 t_gate=0.02 µs、T1/T2~60-80 µs ⇒
    无量纲演化量 |L|·t ≈ 2.5e-4 ⇒ RK4 从 N=5 到 N=400 残差**恒为 1.11e-16**、
    与步数无关。即**该锚的残差物理上不可标定**，必然落在 1e-12 以内。

    **自证桩的充要特征其实不是「残差小」，而是「跟着 golden 走」**：
    `ReferenceCandidate.__call__` 直接 `return golden`、**完全不看 params**
    ⇒ 扰动参数后候选值纹丝不动（|cand − golden(原)| ≡ 0）。

    新判据 =「**残差 ≡0 且 扰动无响应** ⇒ 自证桩」，比旧判据**严格更严**：
    旧判据既会**误伤**「残差恰好小」的真候选（B10），也会**漏过**「残差恰好
    大」的自证桩（例如某个桩被加了常数扰动）。

    🔴🔴🔴 **v0.9.25 再升级：响应必须相对「候选自己的基线」，不是相对 golden**
    上一版（v0.9.24）比的是 `|cand(p·(1±rel)) − **golden**| > thresh`。这在
    等式型锚上碰巧对（真候选 ≈ golden，残差 ≲1e-12），但在**不等式型锚**
    （`cmp='le'`，如 B19 无源上界 golden=1.0）上是**漏的**：
        cand(任何 params) = golden × 0.99988   ← 常量缩放候选，完全不看 params
    它每个扰动下都返回同一个数，与 golden 差 1.2e-4 ≫ thresh ⇒ 旧版判
    「有响应」⇒ **常量桩被放行**。
    实测攻击演示（v0.9.25）：常量缩放 old=**True（漏过）** / new=**False（抓到）**；
    纯自证桩 `return golden` 两版都 False。且 18 道现有独立锚（B1/B3/B4/B9/B10/
    B12-B15/B20/B22-B27/E2/S13）在新旧判据下**结果完全一致 ⇒ 零回归**。
    代价：多算一次基线 `base = cand_fn(spec, oracle_value)`（每个锚 +1 次求解）。

    参数
    ----
    spec : 有 `.params` 映射的对象（VerificationSpec 或 _SpecShim）
    cand_fn : 候选函数，签名 (spec, oracle_value) -> float
    oracle_value : 原 golden 值（扰动后不再重算 golden，模拟「求解器算错」）
    rel : 相对扰动幅度，默认 ±10%
    thresh : 判定「有响应」的阈值，默认 1e-12

    返回
    ----
    True = 候选对参数有物理响应（真候选）；False = 纹丝不动（自证桩特征）。
    """
    params = getattr(spec, "params", None)
    if not isinstance(params, dict):
        return False
    # 🔴 基线必须自己算（v0.9.25）：响应 = 候选**自己**在扰动下的变化量，
    # 不是「候选与 golden 的差」。否则常量缩放候选会靠 |cand−golden|≠0 蒙混过关。
    try:
        base = cand_fn(spec, oracle_value)
    except Exception:  # noqa: BLE001 —— 基线就抛异常的不按桩处理（上游判据会抓）
        return True
    if not isinstance(base, (int, float)):
        return True   # 非标量结果无法用残差判，放行（与 run_harness 口径一致）
    for key, val in params.items():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        for direction in (+rel, -rel):
            try:
                p2 = dict(params)
                p2[key] = float(val) * (1.0 + direction)
                sp2 = _SpecShim(getattr(spec, "spec_id", ""), p2)
                cv2 = cand_fn(sp2, oracle_value)
            except Exception:  # noqa: BLE001 —— 扰动后求解器报错=有响应
                return True
            if isinstance(cv2, (int, float)) and abs(cv2 - base) > thresh:
                return True
    return False


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

    def candidate_class(self, bid):
        """候选三分类（v0.9.16 · P0-3）——全库唯一判序，与对外账本同源。

        判序**必须**先判 `candidate_status=degraded_ordinal` 再查登记表：
        E2 的 fdfd_ng 一旦登记，若先查表就会被判成 strict ⇒ verified 从 4
        虚报成 5（**假绿**）。降级锚「有候选、跑了真求解器」，但不进死标量判决。
        """
        from .verification_adapters import BENCHMARK_CANDIDATES
        from .benchmarks import BENCHMARK_DEFS
        d = BENCHMARK_DEFS.get(bid) or {}
        if d.get("candidate_status") == CANDIDATE_CLASS_DEGRADED:
            return CANDIDATE_CLASS_DEGRADED
        key = d.get("candidate")
        if key and key in BENCHMARK_CANDIDATES:
            return CANDIDATE_CLASS_STRICT
        return CANDIDATE_CLASS_STUB

    def is_independent(self, bid):
        """该锚题是否由**进死标量判决**的独立候选判出（= strict，不含降级）。"""
        return self.candidate_class(bid) == CANDIDATE_CLASS_STRICT

    def describe_trichotomy(self):
        """供报告 meta 显示三分类明细（strict / degraded / stub 各有哪些题）。"""
        from .benchmarks import BENCHMARK_DEFS
        out = {CANDIDATE_CLASS_STRICT: [], CANDIDATE_CLASS_DEGRADED: [],
               CANDIDATE_CLASS_STUB: []}
        for b in sorted(BENCHMARK_DEFS):
            out[self.candidate_class(b)].append(b)
        return out

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
