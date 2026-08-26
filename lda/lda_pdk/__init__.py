"""LDA · L2 开放 PDK / 器件本体 Registry（生态共建地基，D-93）+ 社区提交入口（D-94）
+ 社区评审流与提案落地（D-95）+ 门槛扩展/策略/批量评审（D-96/D-97）+ 端到端发布（D-98）
+ 实证大数据锚语料评审流（D-62）。

L2 = 开放 PDK/器件本体 Registry（社区共建）。本模块提供：
  - PDKRegistry：器件本体注册（id/name/tech/foundry/sovereign_class/
    layers/params/tags），add/query/stats/to_json/load。
  - SOVEREIGN_DEPS：主权依赖分级清单（A/B/C，来自战略审计 LDA-ST-001）。
  - submit：社区提交入口（D-94）—— submit_device / submit_devices_batch /
    BenchmarkProposal / ProposalStore / submit_benchmark_proposal /
    list_contributions，贡献库持久化于 contributions.json（gitignore）；
    D-96/D-97 提交期防重守卫 + ReviewPolicy 可配置评审策略。
  - review：社区评审流 + 提案→golden 落地（D-95）—— review_proposal /
    land_proposal / reload_landed / list_proposals / get_audit / list_landed /
    resubmit_proposal / review_stats，落地注册于 landed.json（gitignore）；
    D-96 门槛扩展（签名完备性/数值界限/core 双评审 quorum）+ D-97 批量评审/批量落地。
  - publish：端到端发布（D-98）—— publish_proposal（landed→published，生成
    可 git apply 的 golden.py/benchmarks.py 补丁 + Release Notes 草稿于
    reports/patches/）+ list_published。
  - empirical：实证大数据锚语料评审流（D-62）—— submit_measurement /
    review_measurement / land_measurement / list_measurements /
    measurement_stats / list_landed_measurements；实测语料（citation 必填=
    可追溯来源）经「具名人工评审（LLM 不进判决路径）→ 确定性自测门禁 →
    落库 empirical_contributions.json」后，harness E1-E7 实证锚题实时可用
    （第二道非 AI ground，与物理定律锚并列）。

作用边界（诚实标注）：
  - 本模块是生态共建的「地基接口 + 提交入口 + 评审落地流 + 发布 + 实证语料流」；
  - **不实际对接晶圆厂 NDA-PDK**（属发动期事项，联动 D-62，暂缓）；
    真实 PDK 数据只经提交入口登记，不在此硬编码；
  - harness 提案经「具名人工评审 → 确定性自测门禁 → 落地注册 → 发布」端到端
    闭环；实证语料经「具名人工评审 → 落库 → harness E 题实证锚实时生效」；
    落库(live) ≠ 进版本控制、发布(git apply)由维护者执行，权威 ORACLE/语料
    以维护者 git 提交（开放评审流）为准。

许可证纪律：Registry 仅存元数据（器件几何/工艺参数/来源），不依赖
任何 GPL 求解器代码；主权清单用于分发层决策（B 级 fork 到 Gitee/GitCode）。
"""
from .registry import PDKRegistry, DeviceEntry
from .sovereign_deps import (
    SOVEREIGN_DEPS, Dependency, classify_dependency, by_class,
)
from .submit import (
    submit_device, submit_devices_batch,
    BenchmarkProposal, ProposalStore, submit_benchmark_proposal,
    list_contributions, infer_sovereign_class,
    ReviewPolicy, get_policy, policy_info,
)
from .review import (
    review_proposal, land_proposal, reload_landed,
    list_proposals, get_audit, list_landed,
    resubmit_proposal, review_stats,
    review_proposals_batch, land_proposals_batch,
)
from .publish import publish_proposal, list_published
from .empirical import (
    submit_measurement, review_measurement, land_measurement,
    list_measurements, measurement_stats, list_landed_measurements,
)

__all__ = [
    "PDKRegistry", "DeviceEntry",
    "SOVEREIGN_DEPS", "Dependency", "classify_dependency", "by_class",
    "submit_device", "submit_devices_batch",
    "BenchmarkProposal", "ProposalStore", "submit_benchmark_proposal",
    "list_contributions", "infer_sovereign_class",
    "ReviewPolicy", "get_policy", "policy_info",
    "review_proposal", "land_proposal", "reload_landed",
    "list_proposals", "get_audit", "list_landed",
    "resubmit_proposal", "review_stats",
    "review_proposals_batch", "land_proposals_batch",
    "publish_proposal", "list_published",
    "submit_measurement", "review_measurement", "land_measurement",
    "list_measurements", "measurement_stats", "list_landed_measurements",
]
