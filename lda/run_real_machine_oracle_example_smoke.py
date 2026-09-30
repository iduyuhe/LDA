"""真机 ORACLE 接入示例 smoke（P2.4 · 2026-09-30 · ≥1 接入示例，机器验证）。

零真实 foundry / 流片真值：示例复用 P1.3 扩容后的 M6 实证语料（公开可溯源 A 级
实测），演示「literature_measured 语料 → 真机 ORACLE 契约」的**活流转**，并固化
四道判据（1 正向 + 3 反向）：

  1. 正向（合法必过）：A 级可溯源 literature_measured 语料经示例流转注册成功，
     值可回读、kind 可作 golden、来源 tier=A。
  2. 反向 A（不拟合回算）：声明 no_fitting_back=False ⇒ 注册必拒。
  3. 反向 B（非方法学独立）：method_independent=False ⇒ 注册必拒。
  4. 数据源门（仅 A 级）：B/X 级（不可溯源）语料 resolve(require_traceable=True)
     返回 None ⇒ 不得作 golden 进真机 ORACLE。

本 smoke 不污染全局单例（real_machine_oracle.REAL_MACHINE_ORACLE 仍 is_empty）。
"""
import os
import sys

_LDA = os.path.dirname(os.path.abspath(__file__))
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness.empirical_bank import (  # noqa: E402
    EmpiricalAnchor,
    EmpiricalCorpus,
    EmpiricalMeasurement,
)
from lda_harness.real_machine_oracle import (  # noqa: E402
    OracleGuardError,
    OracleKind,
    RealMachineMeasurement,
    RealMachineOracleRegistry,
    RealMachineProvenance,
)
from real_machine_oracle_example import (  # noqa: E402
    first_traceable_item,
    load_corpus,
    onboard_literature_measured,
    reject_fitting_back_demo,
)


def _expect_raise(fails, name, fn):
    try:
        fn()
    except OracleGuardError:
        return
    fails.append(name)


def main() -> int:
    fails = []

    corpus = load_corpus()
    fid = first_traceable_item(corpus) or "E-SIN-NG-300"
    if fid not in corpus._items:
        # 兜底：取首条任意条目（理论上 first_traceable_item 已给 A 级）
        fid = next(iter(corpus._items))

    # 1. 正向（合法必过）：示例流转成功
    try:
        r = onboard_literature_measured(fid, corpus)
    except OracleGuardError as e:
        fails.append("正向失败：A 级语料接入示例竟被拒 - %s" % e)
    else:
        if not r.get("ok"):
            fails.append("正向失败：onboard 返回 ok=False")
        if r.get("registered_value") != r.get("value"):
            fails.append("正向失败：注册值不可回读（%s != %s）"
                        % (r.get("registered_value"), r.get("value")))
        if r.get("kind") != OracleKind.LITERATURE_MEASURED.value:
            fails.append("正向失败：kind 非 literature_measured（%s）" % r.get("kind"))
        if not r.get("is_eligible_kind"):
            fails.append("正向失败：kind 不在可作 golden 集合（违背数据源门）")
        if r.get("source_tier") != "A":
            fails.append("正向失败：数据源 tier 非 A（%s）" % r.get("source_tier"))

    # 2. 反向 A（不拟合回算）：no_fitting_back=False ⇒ 必拒
    if not reject_fitting_back_demo(fid, corpus):
        fails.append("反向 A 失效：no_fitting_back=False 竟被注册为 golden")

    # 3. 反向 B（非方法学独立）：method_independent=False ⇒ 必拒
    m = corpus.get(fid)
    _expect_raise(
        fails, "反向 B 失效：method_independent=False 竟被注册为 golden",
        lambda: RealMachineOracleRegistry().register(
            RealMachineMeasurement(
                fid, _metric_q(m.metric), float(m.measured_value),
                provenance_ref=fid, kind=OracleKind.LITERATURE_MEASURED,
                method_independent=False, no_fitting_back=True),
            RealMachineProvenance(ref=fid, report_ref=m.source_url),
        ),
    )

    # 4. 数据源门（仅 A 级）：B/X 级不可溯源语料 ⇒ resolve 返回 None ⇒ 不得进 ORACLE
    b_item = EmpiricalMeasurement(
        id="DEMO-UNTraceable", device="demo", metric="n_g",
        measured_value=1.9, uncertainty_abs=0.03, fab_source="x",
        citation="某文献量级参考（无公开可解析定位符）", source_url="",
        geometry={"w_core_um": 1.0})
    b_corpus = EmpiricalCorpus([b_item])
    val, tag, _ = EmpiricalAnchor(b_corpus).resolve(
        "DEMO-UNTraceable", require_traceable=True)
    if val is not None:
        fails.append("数据源门失效：B 级语料竟被 resolve 为 golden（tag=%s）" % tag)
    # 且该 B 级语料经示例流转必被拒
    try:
        onboard_literature_measured("DEMO-UNTraceable", b_corpus)
        fails.append("数据源门失效：B 级语料竟经示例接入真机 ORACLE")
    except OracleGuardError:
        pass  # 期望

    if fails:
        print("FAIL")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS · 真机 ORACLE 接入示例流转自洽"
          "（正向 A 级接入 + 不拟合回算/非独立/不可溯源 三道反向全拒，零真实数据）")
    return 0


def _metric_q(metric: str):
    """示例模块的 metric→quantity 映射副本（避免跨 import 形状耦合）。"""
    from lda_harness.real_machine_oracle import MeasurementQuantity
    return {
        "n_g": MeasurementQuantity.EFFECTIVE_INDEX,
        "n_eff": MeasurementQuantity.EFFECTIVE_INDEX,
        "FSR_nm": MeasurementQuantity.FSR,
        "intrinsic_Q": MeasurementQuantity.QUALITY_FACTOR,
        "loaded_Q": MeasurementQuantity.QUALITY_FACTOR,
        "coupling_efficiency": MeasurementQuantity.COUPLING_EFFICIENCY,
        "responsivity_A_per_W": MeasurementQuantity.RESPONSIVITY,
        "excess_loss_dB": MeasurementQuantity.INSERTION_LOSS,
        "insertion_loss_dB": MeasurementQuantity.INSERTION_LOSS,
    }.get(metric, MeasurementQuantity.OTHER)


if __name__ == "__main__":
    sys.exit(main())
