"""LDA 验证 harness · 核心框架。

职责：把 L0 IR（或内置默认）的 verification.benchmarks 与确定性黄金参考
挂钩，运行候选求解器输出，按 tol 判定 pass/fail，产出结果供人验收。
黄金参考 = 非 AI 的物理定律锚（见 golden.py / 《白皮书》§11）。
"""
from .golden import golden_value, golden_with_source


class BenchmarkResult:
    def __init__(self, bid, metric, golden, candidate, tol, oracle, passed,
                 note="", source=""):
        self.bid = bid
        self.metric = metric
        self.golden = golden
        self.candidate = candidate
        self.tol = tol
        self.oracle = oracle
        self.passed = passed
        self.note = note
        self.source = source  # 黄金参考事实来源（physical-law / meep-fdtd / ...）


class VerificationHarness:
    def __init__(self, defs):
        self.defs = defs

    def resolve_specs(self, l0_ir=None):
        """解析 benchmark 规格。

        若给定 L0 IR 且含 verification.benchmarks，则以其为准（target/tol/oracle
        可被 L0 覆盖）；否则用内置 BENCHMARK_DEFS 默认规格。
        返回规格列表：{id, metric, target, tol, oracle, params, golden_fn, resolved}
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
                target = b.get("target", d["golden_fn"](**params))
                specs.append({
                    "id": bid, "metric": b.get("metric", d["metric"]),
                    "target": target, "tol": b.get("tol", d["tol"]),
                    "oracle": b.get("oracle", d["oracle"]),
                    "params": params, "golden_fn": d["golden_fn"], "resolved": True,
                })
        else:
            for bid in sorted(self.defs.keys()):
                d = self.defs[bid]
                params = dict(d["default_params"])
                specs.append({
                    "id": bid, "metric": d["metric"],
                    "target": d["golden_fn"](**params), "tol": d["tol"],
                    "oracle": d["oracle"], "params": params,
                    "golden_fn": d["golden_fn"], "resolved": True,
                })
        return specs

    def run(self, specs, candidate):
        """运行候选求解器并与黄金参考比对。

        candidate: callable(spec, golden, params) -> float
        返回 BenchmarkResult 列表。
        """
        results = []
        for s in specs:
            if not s.get("resolved"):
                results.append(BenchmarkResult(
                    s["id"], s.get("metric"), None, None, s.get("tol"),
                    s.get("oracle"), False, "未解析：缺少黄金参考定义",
                    s.get("oracle")))
                continue
            golden, source, src_note = golden_with_source(s["id"], s["params"])
            candidate_val = candidate(s, golden, s["params"])
            passed = abs(candidate_val - golden) <= s["tol"]
            results.append(BenchmarkResult(
                s["id"], s["metric"], golden, candidate_val, s["tol"],
                s["oracle"], passed, src_note, source))
        return results


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
