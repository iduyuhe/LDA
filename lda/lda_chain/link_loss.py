"""LDA 链路损耗增强层（Merge-1a · v0.8.13）。

把「器件内损耗」注入链路传播，并产出损耗预算报告。

设计（最小侵入，与 chip_layout_export 同纪律）：
  - 不改 simulate 核心——损耗在 registry 响应层按器件 params 生效
    （Waveguide: loss_db_cm×length_um；MZI: il_db；Grating 响应已含耦合效率）；
  - 本模块只做「声明」与「报告」：
      with_link_loss(link, wg_loss_db_cm=3.0, ...) → 返回带损耗参数的链路副本
      link_loss_budget(link, wl_um)             → 逐器件损耗预算（人可读）
  - 兼容性：未注入损耗参数的链路 = 既有理想透射行为（零破坏，链路 smoke 全绿）。

损耗语义（物理）：
  - 传播损耗：T = 10^(−α·L/10)，α 正数 dB/cm（与 S1 预算锚同符号约定）；
  - 器件插损：T = 10^(−IL/10)，均匀作用于所有端口传递（C 锚泄漏=IL 合法）。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

# 损耗参数注入约定（registry 响应读取同一键名）
WG_LOSS_KEY = "loss_db_cm"
WG_LEN_KEY = "length_um"
MZI_IL_KEY = "il_db"

DEFAULT_WG_LOSS_DB_CM = 3.0      # SOI 波导典型（与 S1 同源，可被参数覆盖）
DEFAULT_MZI_IL_DB = 0.5          # 文献典型插损


def with_link_loss(link: Any,
                   wg_loss_db_cm: float = DEFAULT_WG_LOSS_DB_CM,
                   mzi_il_db: float = DEFAULT_MZI_IL_DB,
                   ring_il_db: float = 0.0,
                   ) -> Any:
    """返回注入损耗参数的链路副本（原 link 不动）。

    - Waveguide 组件：加 loss_db_cm（length_um 已存在则保留，缺省 1000µm）
    - MZI 组件：加 il_db
    返回副本供 simulate/acceptance 使用。
    """
    cloned = copy.deepcopy(link)
    for comp in cloned.ir.components:
        if comp.kind == "Waveguide":
            comp.params.setdefault(WG_LEN_KEY, 1000.0)   # 默认 1mm 段
            comp.params[WG_LOSS_KEY] = wg_loss_db_cm
        elif comp.kind == "MZI":
            comp.params[MZI_IL_KEY] = mzi_il_db
        elif comp.kind == "RingResonator" and ring_il_db > 0:
            # Ring 响应已含弯曲损耗（adddrop_spectrum alpha_bend）；
            # ring_il_db 为额外 through 插损注入（默认 0 关闭）
            comp.params.setdefault("il_db", ring_il_db)
    return cloned


def link_loss_budget(link: Any,
                     wl_um: float = 1.55,
                     wg_loss_db_cm: float = DEFAULT_WG_LOSS_DB_CM,
                     ) -> Dict[str, Any]:
    """逐器件损耗预算（人可读报告 + 总量）。

    返回：
      rows    : [{device, kind, loss_db, source}]
      total_db: 器件损耗合计（dB）
      note    : 诚实边界（光栅耦合效率在响应内未计入；Ring 弯曲损耗在响应内）
    """
    rows: List[Dict[str, Any]] = []
    total = 0.0
    for comp in link.ir.components:
        loss = 0.0
        src = "—"
        if comp.kind == "Waveguide":
            a = float(comp.params.get(WG_LOSS_KEY, wg_loss_db_cm))
            L_um = float(comp.params.get(WG_LEN_KEY, 0.0))
            loss = a * L_um / 1e4
            src = f"α={a}dB/cm × L={L_um}µm"
        elif comp.kind == "MZI":
            il = float(comp.params.get(MZI_IL_KEY, 0.0))
            loss = il
            src = f"IL={il}dB（excess）"
        if loss > 0:
            rows.append({"device": comp.id, "kind": comp.kind,
                         "loss_db": round(loss, 4), "source": src})
            total += loss
    return {
        "rows": rows,
        "total_db": round(total, 4),
        "wl_um": wl_um,
        "note": ("器件内损耗（传播/插损）；光栅耦合效率与环形弯曲损耗在响应内"
                 "已计，未重复计入本预算。"),
    }
