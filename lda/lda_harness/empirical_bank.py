"""LDA 实证大数据锚（阶段1 任务 1.6 · 缓解雷③）。

提供两类资产的注册 / 校验 / 查询框架，二者共同构成「实证大数据锚」：

1. EmpiricalCorpus —— 真实器件**实测语料**（器件 + 几何 + 实测 metric +
   可追溯来源 + 不确定度）。这是对抗「纯 AI 互证循环论证」的事实地基：
   求解器输出须对照真实测量，而非另一套 AI 意见。

2. AdversarialBenchmarkBank —— **开放对抗性题库**，征集「让 AI 求解器
   翻车」的题（社区 / 退休专家 / 晶圆厂提交），作为信任墙的公开对抗层
   （见《白皮书》雷③缓解）。

与 harness 对接：EmpiricalAnchor.resolve(id) 返回 (value, uncertainty,
source)，与 golden.golden_with_source 同构，可作为 harness 的 golden 来源
之一。**红线守住**：比对仍是标量 |candidate - measured| ≤ tol，LLM 永不进
判决路径。

许可证纪律：实测语料为事实数据，不依赖任何 GPL 求解器；登记时可选的
ORACLE 交叉校验仅作参考、不进判决。
"""
import json
from dataclasses import dataclass, field, asdict


# ============================ 实测语料 ============================
@dataclass
class EmpiricalMeasurement:
    id: str
    device: str
    metric: str
    measured_value: float
    uncertainty_abs: float
    fab_source: str
    citation: str
    method: str = ""
    geometry: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)

    def validate(self):
        if not self.id or not self.device:
            raise ValueError("id/device 必填")
        if not isinstance(self.measured_value, (int, float)):
            raise ValueError("measured_value 须为数值")
        if self.uncertainty_abs < 0:
            raise ValueError("uncertainty_abs 须 ≥0")
        if not self.citation:
            raise ValueError("citation 必填（实证锚必须有可追溯来源）")
        return True


class EmpiricalCorpus:
    """真实器件实测语料库。"""

    def __init__(self, items=None):
        self._items = {}
        for it in (items or []):
            m = it if isinstance(it, EmpiricalMeasurement) else EmpiricalMeasurement(**it)
            self.add(m)

    def add(self, m: EmpiricalMeasurement):
        m.validate()
        self._items[m.id] = m
        return m

    def get(self, mid):
        return self._items.get(mid)

    def query(self, metric=None, device=None, tag=None):
        out = []
        for m in self._items.values():
            if metric and m.metric != metric:
                continue
            if device and device.lower() not in m.device.lower():
                continue
            if tag and tag not in m.tags:
                continue
            out.append(m)
        return out

    def stats(self):
        by_metric = {}
        for m in self._items.values():
            by_metric[m.metric] = by_metric.get(m.metric, 0) + 1
        return {"total": len(self._items), "by_metric": by_metric}

    def to_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(m) for m in self._items.values()], f,
                      indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("corpus", data) if isinstance(data, dict) else data
        return cls(items)


# ============================ 对抗性题库 ============================
@dataclass
class AdversarialBenchmark:
    id: str
    title: str
    desc: str
    target_metric: str
    oracle_type: str
    tol: float
    submitted_by: str = "community"
    geometry: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)

    def validate(self):
        if not self.id or not self.title:
            raise ValueError("id/title 必填")
        if not self.target_metric:
            raise ValueError("target_metric 必填")
        if self.tol is None or self.tol < 0:
            raise ValueError("tol 须 ≥0")
        return True


class AdversarialBenchmarkBank:
    """开放对抗性题库（征集让 AI 求解器翻车的题）。"""

    def __init__(self, items=None):
        self._items = {}
        for it in (items or []):
            b = it if isinstance(it, AdversarialBenchmark) else AdversarialBenchmark(**it)
            self.add(b)

    def add(self, b: AdversarialBenchmark):
        b.validate()
        self._items[b.id] = b
        return b

    def get(self, bid):
        return self._items.get(bid)

    def stats(self):
        by_tag = {}
        for b in self._items.values():
            for t in b.tags:
                by_tag[t] = by_tag.get(t, 0) + 1
        return {"total": len(self._items), "by_tag": by_tag}

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("adversarial", data) if isinstance(data, dict) else data
        return cls(items)


# ====================== 实证锚接入（与 harness golden 同构） ======================
class EmpiricalAnchor:
    """把 corpus 中某条实测作为 golden 来源，与 golden.golden_with_source 同构。

    调用方（harness / solver_writer Verifier）可将其作为 golden 之一：
        value, source, note = anchor.resolve(mid)
    比对 = abs(candidate - value) <= tol  （tol 默认取 uncertainty_abs）
    LLM 永不进判决路径。
    """

    def __init__(self, corpus: EmpiricalCorpus):
        self.corpus = corpus

    def resolve(self, mid, tol=None):
        m = self.corpus.get(mid)
        if not m:
            return (None, "empirical-missing", f"无实测语料: {mid}")
        tol = tol if tol is not None else m.uncertainty_abs
        return (float(m.measured_value), "empirical-measurement",
                f"{m.fab_source} | {m.citation} | σ={m.uncertainty_abs} | tol={tol}")
