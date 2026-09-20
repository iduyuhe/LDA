"""LDA · 四套裁判到统一验证契约的适配器（D-04）。

把项目内四套裁判（harness B1-B11 / waveguide_loop / coupler_loop / solver_writer）
各自的目标描述、ORACLE 接入、容差语义、候选求解器统一到 VerificationSpec，
使全量回归可经统一入口（run_all_specs.py）执行并输出统一报告。

每个 build_*_specs 返回 (specs, cand_map)：
  specs     : List[VerificationSpec]（统一契约，含 oracle_fn/compare_fn/tol/source）
  cand_map  : Dict[spec_id, candidate_fn(spec, oracle_value) -> 候选值]
"""
# ===========================================================================
# 拆分布局（v0.9.117 · 审计 F-08 巨石治理）
# ---------------------------------------------------------------------------
# 本模块**只做装配与对外 re-export**，实现已按原文件顺序连续切分：
#     _adapter_core.py   公共基座（注册表 / 装饰器 / 路径 / 批加载器）
#     _adapter_p1..p6.py 候选实现分片
# 🔴 **装配顺序契约**：`_register_candidate` 按 decorator **执行顺序**写入
#    `BENCHMARK_CANDIDATES`（其插入序即全仓遍历序）。因此 p1→p6 的 import
#    顺序**不可**调整、不可改为按需惰性导入。判据：
#        python scripts/registry_snapshot.py --check <拆前快照>
#    （比对 benchmark_candidates 的**有序** [key, 函数名] 列表）
# ===========================================================================


from __future__ import annotations

from . import (
    _adapter_p1, _adapter_p2, _adapter_p3, _adapter_p4, _adapter_p5, _adapter_p6,
)
from ._adapter_core import BENCHMARK_CANDIDATES
from ._adapter_p1 import (
    _fdfd_ng_candidate,
    _fit_fsr_peak_periodicity,
    _load_empirical_anchor,
    build_harness_specs,
)
from ._adapter_p2 import (
    build_coupler_specs,
    build_solver_writer_specs,
    build_waveguide_specs,
    harness_perturbed_candidate,
)

# 🔴 装配 + re-export 契约（勿删 · 勿「优化」掉）：
#   ① **_adapter_p1..p6 必须全部加载且按此顺序**——`_register_candidate` 按 decorator
#      **执行顺序**写入 `BENCHMARK_CANDIDATES`，其插入序即全仓遍历序。少加载任一片
#      或调换次序，注册表会**静默**少项/改序（判据：`scripts/registry_snapshot.py --check`）。
#   ② 公开名是对外通道：全仓 28 个模块 `from lda_harness.verification_adapters import <name>`；
#      另有**属性取用通道** `scripts/registry_snapshot.py:49` 的
#      `verification_adapters.BENCHMARK_CANDIDATES`（from-import 扫描器**看不见**它）。
#   以下两个元组同时让 pyflakes 不把这些名字判成「未使用导入」。
_ASSEMBLY_CONTRACT = (_adapter_p1, _adapter_p2, _adapter_p3, _adapter_p4, _adapter_p5, _adapter_p6)
_REEXPORT_CONTRACT = (
    BENCHMARK_CANDIDATES, build_harness_specs, harness_perturbed_candidate,
    build_waveguide_specs, build_coupler_specs, build_solver_writer_specs,
    _load_empirical_anchor, _fit_fsr_peak_periodicity, _fdfd_ng_candidate,
)
