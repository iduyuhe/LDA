"""LDA · L2 开放 PDK / 器件本体 Registry（生态共建地基，D-93）+ 社区提交入口（D-94）
+ 社区评审流与提案落地（D-95）。

L2 = 开放 PDK/器件本体 Registry（社区共建）。本模块提供：
  - PDKRegistry：器件本体注册（id/name/tech/foundry/sovereign_class/
    layers/params/tags），add/query/stats/to_json/load。
  - SOVEREIGN_DEPS：主权依赖分级清单（A/B/C，来自战略审计 LDA-ST-001）。
  - submit：社区提交入口（D-94）—— submit_device / submit_devices_batch /
    BenchmarkProposal / ProposalStore / submit_benchmark_proposal /
    list_contributions，贡献库持久化于 contributions.json（gitignore）。
  - review：社区评审流 + 提案→golden 落地（D-95）—— review_proposal /
    land_proposal / reload_landed / list_proposals / get_audit / list_landed，
    落地注册于 landed.json（gitignore），并生成补丁供维护者 git 提交。

作用边界（诚实标注）：
  - 本模块是生态共建的「地基接口 + 提交入口 + 评审落地流」——定义 Registry
    结构与主权清单，并让社区/退休专家/晶圆厂经统一入口流入真实 PDK 数据与
    harness 提案；
  - **不实际对接晶圆厂 NDA-PDK**（属发动期事项，D-62 联动，暂缓）；
    真实 PDK 数据只经提交入口登记，不在此硬编码；
  - harness 提案经「具名人工评审（LLM 不进判决路径）→ 确定性自测门禁 →
    落地注册」闭环；落库(live) ≠ 进版本控制，权威 ORACLE 以维护者 git 提交
    （开放评审流）为准。

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
]
