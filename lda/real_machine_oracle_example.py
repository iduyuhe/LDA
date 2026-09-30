"""LDA 真机 ORACLE 接入示例（P2.4 · 2026-09-30 · ≥1 接入示例）。

本模块是「**预留清单 → 可选层接口骨架**」的**活流转示例**，证明 P2.4 契约
（C1–C5 + G1–G6 + ② 标定窗口 + 🔴 方法学独立性 / 不拟合回算）不是只停在
守卫自测，而是**真能接住一条实证语料**：

    实证语料(M6, P1.3 扩容 73→122)
        │  EmpiricalAnchor.resolve(require_traceable=True)  ── 数据源门：仅 A 级
        ▼
    RealMachineMeasurement(kind=LITERATURE_MEASURED,
                           method_independent=True, no_fitting_back=True)
        │  RealMachineOracleRegistry().register(meas, provenance)
        ▼
    注册成功 · 值可回读 · 真值只进不出（G4）

红线边界（与 real_machine_oracle.py 同源）：
  - 本模块是**桥接层**（可选层 ↔ 内核实证语料），本身**不进内核**（内核零依赖）。
  - 零真实 foundry / 流片真值；示例用的 M6 语料为公开可溯源（A 级）实测。
  - LLM 不进判决路径；所有声明（method_independent / no_fitting_back / signer）皆
    人类责任方填写，AI 不得代填。

对应文档：docs/LDA_真机ORACLE接入框架预留清单_2026-09-11.md + LDA_P2_实施规划_2026-09-30.md §3 P2.4。
"""
from __future__ import annotations

import os

# 🔴 桥接层允许同时 import 可选层与内核实证语料（这是本模块存在的意义）；
#    但内核模块（golden.py / benchmarks.py / empirical_bank.py / ...）**绝不**
#    反向 import 本模块或 real_machine_oracle（由 run_real_machine_oracle_
#    import_boundary_smoke.py 机器守护）。
from lda_harness.real_machine_oracle import (  # noqa: E402
    GOLDEN_ELIGIBLE_KINDS,
    OracleGuardError,
    OracleKind,
    MeasurementQuantity,
    RealMachineMeasurement,
    RealMachineOracleRegistry,
    RealMachineProvenance,
)
from lda_harness.empirical_bank import EmpiricalAnchor, EmpiricalCorpus  # noqa: E402
from lda_harness.provenance import classify_citation  # noqa: E402


_HERE = os.path.dirname(os.path.abspath(__file__))
_SEED_PATH = os.path.join(_HERE, "lda_harness", "seed_empirical.json")

# 实证语料 metric 名 → 真机 ORACLE 测量量枚举（C1 数据格式契约）。
_METRIC_TO_QUANTITY = {
    "n_g": MeasurementQuantity.EFFECTIVE_INDEX,
    "n_eff": MeasurementQuantity.EFFECTIVE_INDEX,
    "FSR_nm": MeasurementQuantity.FSR,
    "intrinsic_Q": MeasurementQuantity.QUALITY_FACTOR,
    "loaded_Q": MeasurementQuantity.QUALITY_FACTOR,
    "coupling_efficiency": MeasurementQuantity.COUPLING_EFFICIENCY,
    "responsivity_A_per_W": MeasurementQuantity.RESPONSIVITY,
    "excess_loss_dB": MeasurementQuantity.INSERTION_LOSS,
    "insertion_loss_dB": MeasurementQuantity.INSERTION_LOSS,
}

# metric → 单位（仅用于报告可读，不影响任何判据）。
_METRIC_UNIT = {
    "n_g": "", "n_eff": "", "FSR_nm": "nm", "intrinsic_Q": "",
    "loaded_Q": "", "coupling_efficiency": "", "responsivity_A_per_W": "A/W",
    "excess_loss_dB": "dB", "insertion_loss_dB": "dB",
}


def load_corpus(seed_path: str | None = None) -> EmpiricalCorpus:
    """加载 M6 实证语料库（P1.3 扩容 73→122）。"""
    corpus = EmpiricalCorpus.load(seed_path or _SEED_PATH)
    return corpus


def _metric_to_quantity(metric: str) -> MeasurementQuantity:
    return _METRIC_TO_QUANTITY.get(metric, MeasurementQuantity.OTHER)


def onboard_literature_measured(item_id: str,
                                corpus: EmpiricalCorpus | None = None
                                ) -> dict:
    """把一条**可公开溯源（A 级）**的 literature_measured 语料接入真机 ORACLE。

    流转：EmpiricalAnchor.resolve(require_traceable=True) 取实测值（数据源门） →
    组装 RealMachineMeasurement（kind=LITERATURE_MEASURED · 方法学独立 · 不拟合回算）
    → RealMachineProvenance（可溯源 ref）→ 注册进**新** registry 实例（不污染全局单例）。

    返回 dict：{ok, anchor_id, value, unit, quantity, kind, provenance_ref,
                source_tier, source_locator, registered_value}。

    若语料不可溯源（B/X 级）或缺失 ⇒ 抛 OracleGuardError（数据源门生效）。
    """
    corpus = corpus or load_corpus()
    anchor = EmpiricalAnchor(corpus)
    value, tag, note = anchor.resolve(item_id, require_traceable=True)
    if value is None:
        raise OracleGuardError(
            "数据源门生效：语料 %s 不可溯源或缺失（tag=%s）⇒ 不得作 golden 进真机 ORACLE"
            % (item_id, tag))

    m = corpus.get(item_id)
    tr = classify_citation(m.citation, m.source_url)
    meas = RealMachineMeasurement(
        anchor_id=item_id,
        quantity=_metric_to_quantity(m.metric),
        value=float(value),
        unit=_METRIC_UNIT.get(m.metric, ""),
        error_band=float(m.uncertainty_abs),
        node_declaration="成熟节点（mature node · 非先进节点）",
        provenance_ref=item_id,
        kind=OracleKind.LITERATURE_MEASURED,
        # 🔴 两条人类责任方声明（AI 不得代填）：本示例的语料来自第三方公开实测、
        #    且数值为原文报告值（非由 LDA 内核输出回拟合得到）。
        method_independent=True,
        no_fitting_back=True,
        honest_tier="",  # 未声称「已外部标定」⇒ 诚实默认（不进 SIGNED_CALIBRATION_WINDOWS）
    )
    prov = RealMachineProvenance(
        ref=item_id,
        report_ref=(m.source_url or m.citation),
        date="",
        node_declaration="成熟节点（mature node · 非先进节点）",
    )
    reg = RealMachineOracleRegistry()
    reg.register(meas, prov)
    got = reg.get(item_id)
    return {
        "ok": True,
        "anchor_id": item_id,
        "value": float(value),
        "unit": _METRIC_UNIT.get(m.metric, ""),
        "quantity": meas.quantity.value,
        "kind": meas.kind.value,
        "provenance_ref": item_id,
        "source_tier": tr["tier"],
        "source_locator": tr["locator"],
        "registered_value": (float(got.value) if got is not None else None),
        "is_eligible_kind": meas.kind in GOLDEN_ELIGIBLE_KINDS,
    }


def first_traceable_item(corpus: EmpiricalCorpus | None = None) -> str | None:
    """取语料库中第一条 A 级可溯源条目 id（供 smoke 稳健选样）。"""
    corpus = corpus or load_corpus()
    for m in corpus._items.values():
        if classify_citation(m.citation, m.source_url)["traceable"]:
            return m.id
    return None


def reject_fitting_back_demo(item_id: str,
                             corpus: EmpiricalCorpus | None = None) -> bool:
    """演示反向：声明 no_fitting_back=False（由内核回拟合得到）⇒ 注册必被拒。

    返回 True 表示守卫按预期 raise（注入后恢复全局单例现场由调用方负责）。
    """
    corpus = corpus or load_corpus()
    anchor = EmpiricalAnchor(corpus)
    value, tag, _ = anchor.resolve(item_id, require_traceable=True)
    if value is None:
        raise OracleGuardError("数据源门生效：语料 %s 不可溯源" % item_id)
    m = corpus.get(item_id)
    try:
        RealMachineOracleRegistry().register(
            RealMachineMeasurement(
                anchor_id=item_id,
                quantity=_metric_to_quantity(m.metric),
                value=float(value),
                provenance_ref=item_id,
                kind=OracleKind.LITERATURE_MEASURED,
                method_independent=True,
                no_fitting_back=False,  # 🔴 声明「拟合回算」⇒ 必拒
            ),
            RealMachineProvenance(ref=item_id, report_ref=m.source_url),
        )
    except OracleGuardError:
        return True  # 期望：守卫生效
    return False  # 不应达


if __name__ == "__main__":  # pragma: no cover - 人工自测入口
    print("== 真机 ORACLE 接入示例（P2.4 · M6 实证语料 → ORACLE 流转）==")
    c = load_corpus()
    print("语料库总条数: %d" % len(c._items))
    fid = first_traceable_item(c)
    print("首条 A 级可溯源语料: %s" % fid)
    if fid:
        r = onboard_literature_measured(fid, c)
        print("  接入成功: anchor=%s value=%s unit=%s quantity=%s kind=%s"
              % (r["anchor_id"], r["value"], r["unit"], r["quantity"], r["kind"]))
        print("  数据源门: tier=%s locator=%s eligible=%s 回读=%s"
              % (r["source_tier"], r["source_locator"],
                 r["is_eligible_kind"], r["registered_value"]))
        print("  反向（拟合回算声明）守卫生效: %s"
              % reject_fitting_back_demo(fid, c))
