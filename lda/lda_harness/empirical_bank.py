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

D-06 增量升级（2026-08-20）：在 1.6 的基础上把语料库升级为**可增量**
资产——支持 csv/JSON 批量导入、去重冲突处理、逐条溯源（provenance：
来源文件 / 贡献者 / 导入时间）。溯源字段不写死在 seed 里，导入时自动填充。
"""
import csv
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


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
    source_url: str = ""
    # D-66（2026-09-01）：溯源核实批注。记录「本条数值是如何被逐字核实的」——
    # 尤其是改判/修正的情形（例：原 golden 有误、原 metric 非直接测量量、
    # 候选来源实为仿真值被排除）。空字符串 = 未经人工核实批注。
    # 判定路径不读本字段（仅作证据链），故不影响任何死标量比较。
    note: str = ""
    geometry: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

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

    def traceability(self) -> dict:
        """返回本条语料的溯源分级（A/B/X），见 lda_harness.provenance。

        A 级 = 含 DOI / arXiv / 公开 URL 等可解析定位符 → 第三方可独立复验；
        B 级 = 仅描述性来源（如「XX 文献量级」）→ 不可独立复验，禁止作 golden。

        D-66 修复（2026-09-01）：`from .provenance import ...` 在**以脚本方式
        直接运行**时（CI: `cd lda/lda_harness && python run_empirical_bank.py`）
        会因 empirical_bank 被当成顶层模块而抛
        `ImportError: attempted relative import with no known parent package`
        → **GitHub Actions ci.yml 主干自 v0.9.8（D-63 引入本方法）起一直红灯**，
        而本地 CORE_SMOKES 未收录该脚本故本地全绿 —— 典型的「宣称全绿、主干红」。
        现改为双路导入（包内相对导入优先，回退顶层绝对导入）。
        """
        try:
            from .provenance import classify_citation
        except ImportError:  # 脚本直跑（无父包）→ 回退绝对导入
            from provenance import classify_citation  # type: ignore[no-redef]
        return classify_citation(self.citation, self.source_url)


@dataclass
class ImportResult:
    """批量导入结果：added=新增 / skipped=去重跳过 / conflicts=id 冲突未覆盖 / errors=解析失败。"""
    added: int = 0
    skipped: int = 0
    conflicts: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def __repr__(self):
        return (f"ImportResult(added={self.added}, skipped={self.skipped}, "
                f"conflicts={len(self.conflicts)}, errors={len(self.errors)})")


class EmpiricalCorpus:
    """真实器件实测语料库（D-06 增量：支持批量导入 / 去重 / 溯源）。"""

    COLUMNS = ["id", "device", "metric", "measured_value", "uncertainty_abs",
               "fab_source", "citation", "method", "geometry", "tags"]

    def __init__(self, items=None):
        self._items = {}
        for it in (items or []):
            m = it if isinstance(it, EmpiricalMeasurement) else EmpiricalMeasurement(**it)
            self.add(m)

    def add(self, m: EmpiricalMeasurement, contributor=None, source_file=None,
            overwrite=False):
        """返回 'added'（新增或覆盖更新）/ 'conflict'（id 已存在且未覆盖）。"""
        m.validate()
        if m.id in self._items and not overwrite:
            # 去重：id 已存在且非覆盖 → 跳过（保留现有，记录冲突）
            return "conflict"
        m.provenance = {
            "source_file": source_file or m.provenance.get("source_file"),
            "contributor": contributor or m.provenance.get("contributor", "seed"),
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        self._items[m.id] = m
        return "added"

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

    def to_json(self, path, wrap=True):
        records = [asdict(m) for m in self._items.values()]
        with open(path, "w", encoding="utf-8") as f:
            if wrap:
                json.dump({"corpus": records}, f, indent=2, ensure_ascii=False)
            else:
                json.dump(records, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("corpus", data) if isinstance(data, dict) else data
        bank = cls()
        for it in items:
            m = it if isinstance(it, EmpiricalMeasurement) else EmpiricalMeasurement(**it)
            bank.add(m, contributor="seed", source_file=path)
        return bank

    # ---------- D-06 批量导入 ----------
    def import_json(self, path, contributor=None, overwrite=False) -> ImportResult:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("corpus", data) if isinstance(data, dict) else data
        res = ImportResult()
        for raw in items:
                try:
                    m = raw if isinstance(raw, EmpiricalMeasurement) else EmpiricalMeasurement(**raw)
                    st = self.add(m, contributor=contributor, source_file=path,
                                  overwrite=overwrite)
                    if st == "added":
                        res.added += 1
                    else:  # conflict
                        res.conflicts.append((m.id, "id 已存在（未覆盖）"))
                except Exception as e:  # noqa: BLE001
                    res.errors.append((str(raw.get("id", "?")), str(e)))
        return res

    def import_csv(self, path, contributor=None, overwrite=False) -> ImportResult:
        res = ImportResult()
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    m = self._row_to_measurement(row)
                    st = self.add(m, contributor=contributor, source_file=path,
                                  overwrite=overwrite)
                    if st == "added":
                        res.added += 1
                    else:  # conflict
                        res.conflicts.append((m.id, "id 已存在（未覆盖）"))
                except Exception as e:  # noqa: BLE001
                    res.errors.append((row.get("id", "?"), str(e)))
        return res

    @staticmethod
    def _row_to_measurement(row: dict) -> EmpiricalMeasurement:
        def g(k):
            v = (row.get(k) or "").strip()
            return v
        mv = float(g("measured_value"))
        ua = float(g("uncertainty_abs"))
        geom = g("geometry")
        geometry = json.loads(geom) if geom else {}
        # 兼容 CSV 模板的「;」与手写「,」分隔（seed JSON 为列表，三者统一）
        tags = [t.strip() for t in re.split(r"[;,]+", g("tags")) if t.strip()]
        return EmpiricalMeasurement(
            id=g("id"), device=g("device"), metric=g("metric"),
            measured_value=mv, uncertainty_abs=ua, fab_source=g("fab_source"),
            citation=g("citation"), method=g("method"), geometry=geometry,
            tags=tags,
        )


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
    provenance: dict = field(default_factory=dict)

    def validate(self):
        if not self.id or not self.title:
            raise ValueError("id/title 必填")
        if not self.target_metric:
            raise ValueError("target_metric 必填")
        if self.tol is None or self.tol < 0:
            raise ValueError("tol 须 ≥0")
        return True


class AdversarialBenchmarkBank:
    """开放对抗性题库（征集让 AI 求解器翻车的题）。D-06 增量：溯源 + 批量导入。"""

    def __init__(self, items=None):
        self._items = {}
        for it in (items or []):
            b = it if isinstance(it, AdversarialBenchmark) else AdversarialBenchmark(**it)
            self.add(b)

    def add(self, b: AdversarialBenchmark, contributor=None, source_file=None,
            overwrite=False):
        b.validate()
        if b.id in self._items and not overwrite:
            return "conflict"
        b.provenance = {
            "source_file": source_file or b.provenance.get("source_file"),
            "contributor": contributor or b.provenance.get("contributor", "seed"),
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        self._items[b.id] = b
        return "added"

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
        bank = cls()
        for it in items:
            b = it if isinstance(it, AdversarialBenchmark) else AdversarialBenchmark(**it)
            bank.add(b, contributor="seed", source_file=path)
        return bank

    def import_json(self, path, contributor=None, overwrite=False) -> ImportResult:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("adversarial", data) if isinstance(data, dict) else data
        res = ImportResult()
        for raw in items:
            try:
                b = raw if isinstance(raw, AdversarialBenchmark) else AdversarialBenchmark(**raw)
                st = self.add(b, contributor=contributor, source_file=path,
                              overwrite=overwrite)
                if st == "added":
                    res.added += 1
                else:
                    res.conflicts.append((b.id, "id 已存在（未覆盖）"))
            except Exception as e:  # noqa: BLE001
                res.errors.append((str(raw.get("id", "?")), str(e)))
        return res


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

    def resolve(self, mid, tol=None, require_traceable=True):
        """取某条实测语料作 golden。

        require_traceable=True（默认，**红线守门**）：仅 A 级（含 DOI/arXiv/公开
        URL 定位符）语料可作 golden 进判决路径；B 级（无定位符、不可独立复验）
        直接拒绝，避免在「实证锚」名下混入无法复验的自证数据。

        历史存量 B 级语料在显式传 require_traceable=False 时仍可取值，但会被
        标注为 empirical-B-untraceable 且不计入可溯源实证锚计数（诚实降级）。
        """
        m = self.corpus.get(mid)
        if not m:
            return (None, "empirical-missing", f"无实测语料: {mid}")
        tr = m.traceability()
        if require_traceable and not tr["traceable"]:
            return (None, "empirical-untraceable",
                    f"语料 {mid} 溯源等级={tr['tier']}（无 DOI/arXiv/公开 URL 定位符）→ "
                    f"按来源边界纪律禁止作 golden 进判决；须补公开可溯源出处后升级 A 级。"
                    f" 当前 citation={m.citation!r}")
        tol = tol if tol is not None else m.uncertainty_abs
        tag = ("empirical-measurement" if tr["traceable"]
               else "empirical-B-untraceable")
        return (float(m.measured_value), tag,
                f"{m.fab_source} | {m.citation} | σ={m.uncertainty_abs} "
                f"| tol={tol} | tier={tr['tier']}")
