"""出处判决（T3 / Q3）—— 三张登记表 + 数值安全量分类 + **支配约束报表**。

> 判据 U-0：一个旧值可以保留，当且仅当它能被**独立重算**且与原值相符。

本模块只回答两个问题，都不改任何产品行为（**纯数据 + 纯函数**）：

1. **这个数从哪来？**（`derivable` / `unattr` / `dead_rules` / `num_eps` 四分类）
   - `derivable`：有出处，且能**现算**复核 ⇒ 表里存的值必须等于 `recompute()`。
   - `unattr`：**没有出处**（值算不出来），必须有 `owner_step`（哪个批次消灭它）。
     🔴 棘轮：**只减不增**，且**逐名登记**（不是只看条数 —— 换一个同样条数的集合也算新增）。
   - `dead_rules`：阈值**永不触发**的规则（`0.10 < 线宽 0.24` 那种）。T2 把 `W_MIN` 改成
     派生自 `W_ROUTE` 之后本表为**空**；将来再出现只能当登记错误处理。
   - `num_eps`：**数值安全量**（浮点容差）。它与 `unattr` 的区别是：**能算出下界**
     （浮点分辨率 × 量级），只是取了个整齐的保守值。混进 `unattr` 会把「三种余量」煮成一锅。

2. **这个数由哪条约束判定、裕量多少、是绿是红？**（`constraint_report`）
   - 🔴 旧系统**只报数字不报颜色**：`drc = 0` 与 `slack = −21.163` 在报告里长得一样。
   - 五态，不是三态 —— 因为「有约束且满足」「有约束且不满足」「**没有约束**」
     「有门槛但当前网表不触发」「有约束但缺输入」是五件不同的事，
     **把「没人管」说成「合格」是本征程最容易犯的错**。

五态的判据（每一条都有对应的反向构造，见 `self_check()`）：

| verdict | 含义 | 典型 |
|---|---|---|
| `PASS` | 有支配约束且满足 | `drc=0`、`em=133.665×` |
| `FAIL` | 有支配约束且不满足 | `slack(wired) = −21.163 ps` |
| `UNCONSTRAINED` | **无支配约束**（不算合格） | 面积、DEF 字节数 |
| `REGISTERED_ONLY` | 有门槛，但本网表上**无判别力** | `max_fanout=3`（实际最大 2）、`max_transition` |
| `UNDECIDABLE` | 有约束但**缺输入** | hold（c17 无 DFF） |
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lda_l2.ecore import dcells as CL
from lda_l2.ecore import dcell as DC
from lda_l2.ecore import ddetail as DET
from lda_l2.ecore import ddrc_lvs as DL
from lda_l2.ecore import dpnr as PN
from lda_l2.ecore import dsta as ST

# ── 五态 ───────────────────────────────────────────────────────────────
PASS = "PASS"
FAIL = "FAIL"
UNCONSTRAINED = "UNCONSTRAINED"
REGISTERED_ONLY = "REGISTERED_ONLY"
UNDECIDABLE = "UNDECIDABLE"
_VERDICTS = (PASS, FAIL, UNCONSTRAINED, REGISTERED_ONLY, UNDECIDABLE)


class _SkipProbes(Exception):
    """`self_check()` 未拿到 `netlist`/`report` ⇒ 报表探针显式跳过（**不等价于通过**）。"""

#: `unattr` 每个条目必须指明**哪个批次消灭它**（U-0 防滥用条款：无 owner 的条目不合法）。
#: 只有这四批能消灭出处缺口 —— 写别的值即判非法（防「owner 写成永远到不了的步」）。
VALID_OWNER_STEPS = ("T4", "T5", "T6", "T7")

#: `unattr` 棘轮上限（只许变短）。初值 = 实测 7 条，与规划 §0.4-4.1 逐条对应。
UNATTR_MAX = 7

#: `dead_rules` 棘轮上限。T2 后为 0（`W_MIN` 已派生自 `W_ROUTE`）。
DEAD_RULES_MAX = 0


# ── 表 A：derivable（有出处，可现算） ──────────────────────────────────
def derivable_table() -> Dict[str, Dict[str, Any]]:
    """可重算量：`recorded` 必须等于 `recompute()`（不等 ⇒ 表已过期，审计必红）。

    🔴 存 `recompute` 而不是只存公式字符串：字符串没法执行，「有出处」就变成一句声明。
    这也是本表与「注释里写了公式」的区别 —— 后者删了代码照样绿。
    """
    return {
        "geom.pitch": {
            "recorded": PN.PITCH,
            "unit": "µm",
            "formula": "W + S_MIN + DELTA_ESCAPE",
            "depends_on": ("ddetail.W_ROUTE", "ddrc_lvs.S_MIN", "dpnr.DELTA_ESCAPE"),
            "recompute": lambda: PN.W + DL.S_MIN + PN.DELTA_ESCAPE,
        },
        "geom.ch": {
            "recorded": PN.CH_UM,
            "unit": "µm",
            "formula": "(TRACKS_TARGET - 1) * PITCH + W + DELTA_ESCAPE",
            "depends_on": ("dpnr.TRACKS_TARGET", "dpnr.PITCH", "ddetail.W_ROUTE"),
            "recompute": lambda: ((PN.TRACKS_TARGET - 1) * PN.PITCH
                                  + PN.W + PN.DELTA_ESCAPE),
        },
        "geom.gap": {
            "recorded": PN.CELL_GAP_UM,
            "unit": "µm",
            "formula": "GAP_K * PITCH - CELL_W_UM",
            "depends_on": ("dpnr.GAP_K", "dpnr.PITCH", "dcells.CELLS"),
            # 🔴 独立重算：单元宽从 `dcells` **现取**，不读 `PN.CELL_W_UM`（那是对同一量的第二份副本）
            "recompute": lambda: (PN.GAP_K * PN.PITCH
                                  - max(f().w for f in CL.CELLS.values()) / 1000.0),
        },
        "geom.pad_half": {
            "recorded": PN.pad_half(),
            "unit": "µm",
            "formula": "VIA / 2 + ENC（唯一真源；旧的三份副本已在 Q2 删除）",
            "depends_on": ("ddetail.VIA", "ddrc_lvs.ENC"),
            "recompute": lambda: DET.VIA / 2.0 + DL.ENC,
        },
        "rule.w_min": {
            "recorded": DL.W_MIN,
            "unit": "µm",
            "formula": "= ddetail.W_ROUTE（规则说「不小于当前线宽」）",
            "depends_on": ("ddetail.W_ROUTE",),
            "recompute": lambda: DET.W_ROUTE,
        },
        "timing.port_load": {
            "recorded": ST.FO_PORT * DC.DEFAULT_TECH.cin_ff,
            "unit": "fF",
            "formula": "FO_PORT * Tech.cin_ff",
            "depends_on": ("dsta.FO_PORT", "Tech.cin_ff"),
            "recompute": lambda: ST.FO_PORT * DC.DEFAULT_TECH.cin_ff,
        },
        "timing.t_ref": {
            "recorded": None,     # 依赖网表，由 `t_ref_for()` 现算；此处只登记公式
            "unit": "ps",
            "formula": ("Σ_{i∈L_top}( t_intr + ln2·max(s_n·ρ_n·L/W_n, s_p·ρ_p·L/W_p)"
                        "·FO_target·cin_ff )"),
            "depends_on": ("Tech.t_intr_ps", "Tech.r_on_ohm", "Tech.r_sheet_p_over_n",
                           "Tech.cin_ff", "dsta.FO_TARGET",
                           "dcell.Cell.w_n_nm", "dcell.Cell.w_p_nm", "dcell.Cell.l_nm"),
            "recompute": None,    # 需要网表参数 ⇒ 见 `t_ref_for(nl)`
        },
        "geom.scales_max": {
            "recorded": None,     # 依赖 die 尺寸；由 `scales_for()` 现算
            "unit": "-",
            "formula": "2 ** floor(log2(die_w / W_ROUTE))",
            "depends_on": ("dpnr 布局尺寸", "ddetail.W_ROUTE"),
            "recompute": None,
        },
    }


def t_ref_for(netlist) -> float:
    """`T_ref` 的**独立重算路径** —— 不调 `constraint_layer`，自己按定义式求和。

    🔴 这条是 U-0 的要求：出处必须能**独立重算**。直接返回 `constraint_layer()["clock_period_ps"]`
    等于用被检验者证明被检验者（`slack` 自证的同一形态）。
    """
    # 🔴 v0.9.405 改口：延时不再走 `k_drive · r_on`，改成 `R_cell · ln2 · C`。
    #   本条是**独立重算路径**（K2），所以这里自己按定义式再写一遍，
    #   **不调** `dcell.cell_delay_ps` / `cell_r_ohm` —— 否则就是用被检验者证明被检验者。
    rho_n = DC.DEFAULT_TECH.r_on_ohm * DC.R_REF_W_NM / DC.R_REF_L_NM
    rho_p = rho_n * DC.DEFAULT_TECH.r_sheet_p_over_n
    c_load = ST.FO_TARGET * DC.DEFAULT_TECH.cin_ff
    total = 0.0
    for g in ST.longest_path_gates(netlist):
        c = DC.CELLS[g.cell]
        s_pd, s_pu = DC.series_counts(c)          # 最坏路径串联数（下拉 / 上拉）
        r_pd = s_pd * rho_n * c.l_nm / c.w_n_nm
        r_pu = s_pu * rho_p * c.l_nm / c.w_p_nm
        total += (DC.DEFAULT_TECH.t_intr_ps
                  + max(r_pd, r_pu) * DC.LN2 * c_load * DC.OHM_FF_TO_PS)
    return total


def scales_for(die_w_um: float, width_um: float) -> Tuple[int, ...]:
    """`scales` 的独立重算路径（与 `dsignoff.b3_scales` 同式、**不同实现**）。"""
    if die_w_um < width_um:
        return (1,)
    s_max = 2 ** int(math.floor(math.log2(die_w_um / width_um) + 1e-12))
    return tuple(s for s in (2 ** k for k in range(12)) if s <= s_max)


# ── 表 B：unattr（无出处，必须有 owner） ────────────────────────────────
def unattr_table() -> Dict[str, Dict[str, Any]]:
    """无出处量。**7 条，与规划 §0.4-4.1 逐条对应**；每条都必须有 `owner_step`。

    🔴 为什么它们是 `unattr` 而不是 `derived`：**值算不出来**。
    `r_on = 5000 Ω` 不是从任何物理量推出来的，是「教科书量级的估计」；
    `via = 200 nm` 同。把它们写成 `derived` 就是编一个公式来给已有数字盖章。

    🔴 注意 `w_min / pitch / pad` **不在这里** —— 它们归 `derivable`（T-2 已证两节点都精确等于公式值）。
    这正是「出处本来就在，只是没写出来」与「出处根本不在」的区别。
    """
    return {
        "geom.via": {
            "value": DET.VIA, "unit": "µm", "owner_step": "T4",
            "why": "教科书 28nm 量级的通孔尺寸；无 foundry 数据支撑",
            "consumed_by": ("dpnr.pad_half", "ddetail 通孔绘制", "ddrc_lvs.VIA_BRIDGE"),
        },
        "geom.enc": {
            "value": DL.ENC, "unit": "µm", "owner_step": "T4",
            "why": "包围余量取整值，无 rule deck 出处",
            "consumed_by": ("dpnr.pad_half", "ddrc_lvs 包围规则"),
        },
        "geom.s_min": {
            "value": DL.S_MIN, "unit": "µm", "owner_step": "T4",
            "why": "最小间距取整值，无 rule deck 出处（`pitch` 直接依赖它）",
            "consumed_by": ("dpnr.PITCH", "ddrc_lvs 间距规则"),
        },
        "tech.area_per_tr_um2": {
            "value": DC.DEFAULT_TECH.area_per_tr_um2, "unit": "µm²", "owner_step": "T4",
            "why": "与实测算出的单元面积差 9.4×（规划 §2-D1 已登记）；等 Liberty `area` 接线",
            "consumed_by": ("（当前无消费路径 ⇒ Q0 判 dead）",),
        },
        "tech.r_on_ohm": {
            "value": DC.DEFAULT_TECH.r_on_ohm, "unit": "Ω", "owner_step": "T5",
            "why": "通导电阻教科书量级估计，未标定；`T_ref` 与所有延时都乘在它上面",
            "consumed_by": ("dsta 延时闭式", "dprovenance.t_ref_for"),
        },
        "tech.t_intr_ps": {
            "value": DC.DEFAULT_TECH.t_intr_ps, "unit": "ps", "owner_step": "T5",
            "why": "本征延时取整值，未标定",
            "consumed_by": ("dsta 延时闭式",),
        },
        "cell.k_drive": {
            "value": tuple((n, c.k_drive) for n, c in sorted(DC.CELLS.items())),
            "unit": "-", "owner_step": "T5",
            "why": "18 个驱动能力系数按门类型赋值（1.0…3.6），无器件仿真支撑",
            "consumed_by": ("dsta 延时闭式", "dprovenance.t_ref_for"),
        },
    }


# ── 表 C：dead_rules（阈值永不触发） ────────────────────────────────────
def dead_rules_table() -> Dict[str, Dict[str, Any]]:
    """死规则。**T2 后为空** —— `W_MIN` 已由 `W_ROUTE` 派生（阈值随线宽走，不再恒不触发）。

    🔴 空表 ≠ 「以前没有问题」：T1a 时本表有 1 条（`W_MIN=0.10 < W_ROUTE=0.24`），
    是 Q2 把它消灭的。表空只能证明**现在**没有登记在册的死规则。
    """
    return {}


# ── 表 D：num_eps（数值安全量，可算下界） ───────────────────────────────
def num_eps_table() -> Dict[str, Dict[str, Any]]:
    """数值安全量。与 `unattr` 的分界：**能算出下界**。

    🔴 `SPACE_EPS = 1e-6 µm` 不是「不知道所以随便取」：
    float64 在 µm 量级（~10）上的绝对分辨率是 `2^-52 · 10 ≈ 2.2e-15 µm`，
    取 1e-6 是 **9 个数量级的保守余量**。所以它有出处（浮点分辨率），只是取值是整齐化后的。
    """
    eps = getattr(DL, "SPACE_EPS", None)
    abs_res = 2.0 ** -52 * 10.0        # float64 eps × µm 量级上界
    return {
        "ddrc_lvs.SPACE_EPS": {
            "value": eps, "unit": "µm",
            "bound": abs_res,
            "derivation": ("float64 相对精度 2^-52 × 量级 10 µm ≈ %.3e µm；"
                           "取 1e-6 ⇒ 保守余量 %.1e×"
                           % (abs_res, (eps / abs_res) if eps else float("nan"))),
            "owner_step": None,      # 不是缺口：下界已算出，取值合法
            "why_not_unattr": "有可算下界；`unattr` 的定义是「值算不出来」",
        },
    }


# ── 审计（三表 + 棘轮 + 数值锁定） ──────────────────────────────────────
def provenance_audit(netlist=None, *, tables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """一次审计：三表齐全性 + `derivable` 现算复核 + `unattr` 棘轮 + `num_eps` 下界。

    返回 `{"ok": bool, "problems": [...], ...}`。`problems` 里每条都是**可定位的**字符串，
    不写「审计失败」这种没法修的话。

    `tables` 用于**注入坏表**（反向探针）—— 参数注入而不是改模块全局：
    后者会让「探针跑过之后表就回不来了」变成一类新 bug。
    """
    problems: List[str] = []
    _t = tables or {}

    # ① derivable：登记的 recorded 必须等于现算值
    der = _t.get("derivable") or derivable_table()
    mism: List[Tuple[str, Any, Any]] = []
    for key, row in der.items():
        rc = row.get("recompute")
        if rc is None:
            continue                       # 依赖网表的量（t_ref / scales）单独核
        got = rc()
        want = row["recorded"]
        if want is None or abs(float(got) - float(want)) > 1e-12:
            mism.append((key, want, got))
    if mism:
        problems.append("derivable_mismatch:%r" % (mism,))

    # ①b 两个依赖网表的量：独立重算路径必须与产品侧逐位一致（两侧都算，不许抄）
    if netlist is not None:
        c = ST.constraint_layer(netlist)
        got = t_ref_for(netlist)
        if abs(got - c["clock_period_ps"]) > 1e-9:
            problems.append("t_ref_recompute_mismatch:%.12f vs %.12f"
                            % (got, c["clock_period_ps"]))

    # ② unattr：条数棘轮 + 每条有合法 owner + 逐名登记
    una = _t.get("unattr") or unattr_table()
    if len(una) > UNATTR_MAX:
        problems.append("unattr_count_%d_gt_%d" % (len(una), UNATTR_MAX))
    for key, row in una.items():
        owner = row.get("owner_step")
        if owner not in VALID_OWNER_STEPS:
            problems.append("unattr_no_valid_owner:%s=%r" % (key, owner))
        if not row.get("why"):
            problems.append("unattr_no_reason:%s" % key)

    # ③ dead_rules：只减不增
    dead = _t.get("dead_rules")
    if dead is None:
        dead = dead_rules_table()
    if len(dead) > DEAD_RULES_MAX:
        problems.append("dead_rules_%d_gt_%d" % (len(dead), DEAD_RULES_MAX))

    # ④ num_eps：下界必须真的算出来且余量 ≥1（否则就是 `unattr` 假冒）
    eps_rows = _t.get("num_eps") or num_eps_table()
    for key, row in eps_rows.items():
        v, b = row.get("value"), row.get("bound")
        if b is None or b <= 0:
            problems.append("num_eps_no_bound:%s" % key)
        elif v is not None and v < b:
            problems.append("num_eps_below_bound:%s %.3e < %.3e" % (key, v, b))
        if row.get("owner_step") is not None:
            problems.append("num_eps_should_not_have_owner:%s" % key)

    return {
        "ok": not problems,
        "problems": problems,
        "counts": {"derivable": len(der), "unattr": len(una),
                   "dead_rules": len(dead), "num_eps": len(eps_rows)},
        "unattr_ids": sorted(una),
        "dead_rule_ids": sorted(dead),
        "ratchet": {"unattr_max": UNATTR_MAX, "dead_rules_max": DEAD_RULES_MAX},
    }


# ── 支配约束报表 ────────────────────────────────────────────────────────
def _verdict(ok: bool) -> str:
    return PASS if ok else FAIL


def constraint_report(report: Dict[str, Any], netlist=None) -> Dict[str, Any]:
    """**支配约束报表**：逐数字给「哪条约束判定 · 裕量多少 · 什么颜色 · 什么范围」。

    `report` = `db3_trunk.run_trunk_from_verilog(...)` 的返回。

    🔴 三条硬规则：
    1. **颜色必须从实算派生**，不许手填：`PASS/FAIL` 由 `margin` 的符号 + 门槛现算。
    2. **无约束的量写 `UNCONSTRAINED`，不得写 `PASS`** —— 「没人管」不是「合格」。
    3. `max_fanout` / `max_transition` 必须是 `REGISTERED_ONLY`：
       本网表上**无判别力**（实际最大扇出 2 < 3；slew 不传播 ⇒ 恒真）。
       严禁把它们计入「已具备约束能力」（规划 §0.4-4.6）。
    """
    st = {n: d for n, d in report["stages"]}
    place, route, drc_lvs = st["place"], st["route"], st["drc_lvs"]
    timing, em = st["timing"], st["em"]

    cl = (ST.constraint_layer(netlist,
                              comb_delay_ideal_ps=st["timing"]["comb_delay_ideal_ps"],
                              comb_delay_wired_ps=st["timing"]["comb_delay_wired_ps"])
          if netlist is not None else None)
    sl_i = cl["slack_ideal_ps"] if cl else None
    sl_w = cl["slack_wired_ps"] if cl else None

    rows: List[Dict[str, Any]] = []

    def add(**kw):
        rows.append(kw)

    # ① 面积 —— **无约束**
    add(id="area", label="芯片面积", value=place["die_area_um2"], unit="µm²",
        governing=None, governing_kind="NONE", threshold=None, margin=None,
        verdict=UNCONSTRAINED, scope="N/A",
        note="系统无面积约束（G6 无目标函数）⇒ 这个数只能说「是什么」，不能说「好不好」")

    # ② 布通率 —— 支配约束 = 可用布线容量（E38：布不通是贪心缝出的口袋）
    routed, total = route["nets_with_segments"], route["nets_touched"]
    add(id="routed", label="布通率", value="%d/%d" % (routed, total), unit="-",
        governing="容量律 T≥d（通道轨道数 ≥ 需跨网数）", governing_kind="CAPACITY",
        threshold="%d/%d" % (total, total), margin=routed - total,
        verdict=_verdict(routed == total), scope="FULL_CHIP",
        note="未布 %d 条；唯一杠杆是加面积或加层（E38 已收敛）" % (total - routed))

    # ③ nets_failed —— 路由器主动放弃数
    add(id="nets_failed", label="路由放弃网数", value=route["nets_failed"], unit="-",
        governing="路由完整性（不得静默放弃）", governing_kind="COMPLETENESS",
        threshold=0, margin=-(route["nets_failed"]),
        verdict=_verdict(route["nets_failed"] == 0), scope="FULL_CHIP",
        note="未布的网走 `DANGLING` 归因，不算 failed")

    # ④ DRC —— 规则集判定；**子集结论**
    add(id="drc", label="DRC 违规", value=drc_lvs["drc_violations"], unit="条",
        governing="DRC 规则集（S_MIN / W_MIN / ENC）", governing_kind="RULE_SET",
        threshold=0, margin=-(drc_lvs["drc_violations"]),
        verdict=_verdict(drc_lvs["drc_violations"] == 0),
        scope=drc_lvs.get("lvs_scope") or "ROUTED_SUBSET_ONLY",
        note="只对**已布网**成立；规则集是自建教科书尺度，非 foundry PDK")

    # ⑤ LVS —— 连通性
    add(id="lvs", label="LVS 问题", value=drc_lvs["lvs_problems"], unit="条",
        governing="连通性（几何连通 ⇔ 同网）", governing_kind="CONNECTIVITY",
        threshold=0, margin=-(drc_lvs["lvs_problems"]),
        verdict=_verdict(drc_lvs["lvs_problems"] == 0),
        scope=drc_lvs.get("lvs_scope") or "ROUTED_SUBSET_ONLY",
        note="T2 后已布网 0 条（旧链 183 条仍全在，属另一条链）")

    # ⑥ ideal 延时 —— 支配约束 = T_ref
    add(id="delay_ideal", label="组合延时（理想互连）",
        value=timing["comb_delay_ideal_ps"], unit="ps",
        governing="T_ref（Tech + 拓扑最长路径 + FO_target）", governing_kind="CLOCK",
        threshold=cl and cl["clock_period_ps"], margin=sl_i,
        verdict=(UNDECIDABLE if sl_i is None else _verdict(sl_i >= 0)),
        scope="FULL_CHIP",
        note="理想互连不计线载 ⇒ 与 wired 的差就是线载代价")

    # ⑦ wired 延时 —— **本征程唯一的红**
    add(id="delay_wired", label="组合延时（含线载）",
        value=timing["comb_delay_wired_ps"], unit="ps",
        governing="T_ref（Tech + 拓扑最长路径 + FO_target）", governing_kind="CLOCK",
        threshold=cl and cl["clock_period_ps"], margin=sl_w,
        verdict=(UNDECIDABLE if sl_w is None else _verdict(sl_w >= 0)),
        scope="FULL_CHIP",
        note="🔴 违例：口径修正（含端口负载）后**首次暴露**，不是性能下降")

    # ⑧ hold —— **本征程未实现 hold 检查**，且 c17 无 DFF ⇒ 两重缺输入，恒 `UNDECIDABLE`。
    #   🔴 不写「若检查了就 PASS」的分支：那支既没有判据支撑（`t_clk_min_ps` 恒 None），
    #   又会被 AST 判据视为**手填颜色**（`else PASS` 不是实算派生）。缺就说缺。
    add(id="hold", label="保持时间", value=timing.get("t_clk_min_ps"), unit="ps",
        governing="t_hold（Tech）", governing_kind="HOLD",
        threshold=DC.DEFAULT_TECH.t_hold_ps, margin=None,
        verdict=UNDECIDABLE, scope="N/A",
        note="① `hold_checked=False`（检查器未实现）② n_dff=%d ⇒ 无 clk→Q 路径可查。"
             "**不是「通过」**，是「没有东西可查」" % timing.get("n_dff", 0))

    # ⑨ EM —— 电流密度
    add(id="em", label="电迁移最小裕量", value=em["min_margin_x"], unit="×",
        governing="min_margin ≥ 1（每网最大电流密度 / 限值）",
        governing_kind="EM", threshold=1.0, margin=em["min_margin_x"] - 1.0,
        verdict=_verdict(em["min_margin_x"] >= 1.0),
        scope=("ALL_JUDGED" if em.get("all_pass_on_judged") else "PARTIAL"),
        note="最紧网 = %s；`f = 1/(2·t_comb)` ⇒ EM 经线长依赖几何"
             % em.get("min_margin_net"))

    # ⑩ DEF 字节数 —— **无约束**
    add(id="def_bytes", label="DEF 文件大小", value=st["def_write"]["bytes"], unit="B",
        governing=None, governing_kind="NONE", threshold=None, margin=None,
        verdict=UNCONSTRAINED, scope="N/A",
        note="无体积约束；此列只为「导出非空 + 可回读」留痕")

    # ⑪⑫ 两个**登记但无判别力**的约束
    add(id="max_fanout", label="最大扇出上限",
        value=(cl["max_fanout"] if cl else ST.FO_TARGET), unit="-",
        governing="max_fanout = FO_target（与 T_ref 同源）", governing_kind="FANOUT",
        threshold=(cl["max_fanout"] if cl else ST.FO_TARGET), margin=None,
        verdict=REGISTERED_ONLY, scope="N/A",
        note="🔴 **登记，c17 上无判别力**：实际最大扇出 < 上限 ⇒ 永不触发；"
             "禁计入「已具备约束能力」")
    add(id="max_transition", label="最大转换时间上限",
        value=(cl["max_transition_ps"] if cl else ST._DEFAULT_SLEW_PS), unit="ps",
        governing="max_transition = _DEFAULT_SLEW_PS（**显式假设**，slew 不传播）",
        governing_kind="TRANSITION",
        threshold=(cl["max_transition_ps"] if cl else ST._DEFAULT_SLEW_PS), margin=None,
        verdict=REGISTERED_ONLY, scope="N/A",
        note="🔴 **登记，无判别力**：slew 不传播 ⇒ 判据恒真；"
             "真正值要等 Liberty `default_max_transition`（T4）")

    # ── 汇总：颜色分开数，绝不用「总绿」这种话
    by: Dict[str, List[str]] = {v: [] for v in _VERDICTS}
    for r in rows:
        by[r["verdict"]].append(r["id"])
    subset = [r["id"] for r in rows if r.get("scope") == "ROUTED_SUBSET_ONLY"]

    return {
        "rows": rows,
        "summary": {v: by[v] for v in _VERDICTS},
        "counts": {v: len(by[v]) for v in _VERDICTS},
        "subset_only_ids": subset,
        "n_rows": len(rows),
        "claimable": bool(report.get("claimability", {}).get("claimable")),
        "disclosure": (
            "五态：PASS 有约束且满足 / FAIL 有约束且不满足 / UNCONSTRAINED **无约束**（不是合格）/ "
            "REGISTERED_ONLY 有门槛但本网表无判别力 / UNDECIDABLE 缺输入。"
            "`ROUTED_SUBSET_ONLY` 的量只对已布网成立，不得读成全片干净。"
        ),
        "not_claimable": (
            "本报表**不给签核结论**：`claimable=False`（n10 悬空），"
            "且面积/DEF 两项本就无约束。成立的只有「每个对外数字都有支配约束或显式声明无约束」。"
        ),
    }


# ── 自检（每条都带反向构造） ────────────────────────────────────────────
def self_check(netlist=None, report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """报表与审计的**自检**：正向一条 + 每条规则的**反向构造**（改坏必红）。

    🔴 只测正向等于没测 —— 「五态分得清」这句话必须由「把 PASS 改成 UNCONSTRAINED 就报错」来证明。

    🔴 `netlist` / `report` 由**调用方传入**，本模块**不 import** `db3_trunk` / `dverilog`：
    一度在函数内 import 过，结果静态依赖图里出现 `dprovenance → db3_trunk` 这条**只为自检服务**的边，
    直接把 `run_ecore_reuse_metrics_smoke` 的 M13「ecore 内部 db3_trunk 无消费者」反证前提打掉。
    ⇒ 探针要用的输入由门禁给；模块不制造假依赖。

    ⚠️ `report_probes` 三态显式（`RAN` / `SKIPPED_NO_INPUT`）：
    **跳过 ≠ 通过**，调用方必须断言它是 `RAN`（否则探针静默失靶）。
    """
    problems: List[str] = []
    report_probes = "RAN" if (netlist is not None and report is not None) else "SKIPPED_NO_INPUT"

    # ① unattr 条数 == 规划登记的 7 条（逐名，不看条数）
    want_unattr = {"geom.via", "geom.enc", "geom.s_min", "tech.area_per_tr_um2",
                   "tech.r_on_ohm", "tech.t_intr_ps", "cell.k_drive"}
    got_unattr = set(unattr_table())
    if got_unattr != want_unattr:
        problems.append("unattr_ids_drift:+%r -%r"
                        % (sorted(got_unattr - want_unattr),
                           sorted(want_unattr - got_unattr)))

    # ② derivable 里**不许**出现 unattr 的量（两表互斥）
    overlap = got_unattr & set(derivable_table())
    if overlap:
        problems.append("unattr_and_derivable_overlap:%r" % (sorted(overlap),))

    # ③ dead_rules 必须空（T2 修完 `W_MIN`）
    if dead_rules_table():
        problems.append("dead_rules_not_empty:%r" % (sorted(dead_rules_table()),))

    # ④ 反向：伪造一个「有出处的」via（写进 derivable）⇒ 互斥检查必须能报
    fake_der = dict(derivable_table())
    fake_der["geom.via"] = {"recorded": DET.VIA, "unit": "µm", "formula": "伪造",
                            "depends_on": (), "recompute": lambda: DET.VIA}
    if not (set(unattr_table()) & set(fake_der)):
        problems.append("control_fake_derivable_silent")

    # ⑤ 反向：给 unattr 条目去掉 owner ⇒ 审计必须报
    bad = {k: dict(v) for k, v in unattr_table().items()}
    bad["geom.via"]["owner_step"] = None
    if provenance_audit(tables={"unattr": bad})["ok"]:
        problems.append("control_unattr_no_owner_silent")

    # ⑤b 反向：把 owner 写成「永远到不了的步」⇒ 必须报（防 owner 变成一句安慰话）
    bad_o = {k: dict(v) for k, v in unattr_table().items()}
    bad_o["geom.via"]["owner_step"] = "T99"
    if provenance_audit(tables={"unattr": bad_o})["ok"]:
        problems.append("control_unattr_bogus_owner_silent")

    # ⑥ 反向：把 num_eps 写成「没有下界」⇒ 必须报（防 unattr 假冒 num_eps）
    bad2 = {k: dict(v) for k, v in num_eps_table().items()}
    for _k in bad2:
        bad2[_k]["bound"] = None
    if not any("num_eps_no_bound" in x
               for x in provenance_audit(tables={"num_eps": bad2})["problems"]):
        problems.append("control_num_eps_no_bound_silent")

    # ⑥b 反向：num_eps 的取值低于下界 ⇒ 必须报
    bad2b = {k: dict(v) for k, v in num_eps_table().items()}
    for _k in bad2b:
        if bad2b[_k]["value"] is not None:
            bad2b[_k]["bound"] = float(bad2b[_k]["value"]) * 10.0
    if not any("num_eps_below_bound" in x
               for x in provenance_audit(tables={"num_eps": bad2b})["problems"]):
        problems.append("control_num_eps_below_bound_silent")

    # ⑦ 反向：derivable 的 recorded 改坏 ⇒ 必须报
    bad3 = {k: dict(v) for k, v in derivable_table().items()}
    bad3["geom.pitch"]["recorded"] = float(derivable_table()["geom.pitch"]["recorded"]) + 0.01
    if not any("derivable_mismatch" in x
               for x in provenance_audit(tables={"derivable": bad3})["problems"]):
        problems.append("control_derivable_mismatch_silent")

    # ⑧ 反向：dead_rules 塞一条进去 ⇒ 必须报（棘轮方向：只能变短）
    if not any("dead_rules" in x
               for x in provenance_audit(
                   tables={"dead_rules": {"__fake__": {"why": "伪造"}}})["problems"]):
        problems.append("control_dead_rules_grow_silent")

    # ⑨ 报表侧四条反向探针 —— **颜色必须随数变**，否则它就是手填的
    #    输入由调用方注入（见 docstring：本模块不 import 产品链）。
    try:
        _nl, _rep = netlist, report
        if _nl is None or _rep is None:
            raise _SkipProbes()
        _base = constraint_report(_rep, _nl)
        _by = {r["id"]: r for r in _base["rows"]}

        # 正向基线：本网表上必须**恰好**两个红（布通 + wired 时序），且无约束项不得算 PASS
        if sorted(_base["summary"][FAIL]) != ["delay_wired", "routed"]:
            problems.append("baseline_fail_set_drift:%r" % (_base["summary"][FAIL],))
        for _u in ("area", "def_bytes"):
            if _by[_u]["verdict"] != UNCONSTRAINED or _u in _base["summary"][PASS]:
                problems.append("unconstrained_counted_as_pass:%s" % _u)

        def _mutate(**changes):
            """深拷一份 report 并改指定 stage 的字段（不改原报告）。"""
            import copy as _c
            r = _c.deepcopy(_rep)
            for stage, kv in changes.items():
                for idx, (name, d) in enumerate(r["stages"]):
                    if name == stage:
                        d = dict(d)
                        d.update(kv)
                        r["stages"][idx] = (name, d)
            return constraint_report(r, _nl)

        # ⑨a 把 wired 延时压到 T_ref 以内 ⇒ 同一行必须从 FAIL 翻成 PASS
        if _mutate(timing={"comb_delay_wired_ps": 10.0})["summary"][FAIL] == ["routed"]:
            pass
        else:
            problems.append("control_delay_wired_not_flippable")
        # ⑨b 注入 DRC 违规 ⇒ drc 行必须 FAIL（证明 PASS 不是常量）
        if "drc" not in _mutate(drc_lvs={"drc_violations": 3})["summary"][FAIL]:
            problems.append("control_drc_injection_silent")
        # ⑨c 布通补满 ⇒ routed 行必须 PASS（证明 FAIL 也不是常量）
        if "routed" not in _mutate(route={"nets_with_segments": 11})["summary"][PASS]:
            problems.append("control_routed_full_not_pass")
        # ⑨d EM 裕量压到 1 以下 ⇒ em 行必须 FAIL
        if "em" not in _mutate(em={"min_margin_x": 0.5})["summary"][FAIL]:
            problems.append("control_em_injection_silent")
    except _SkipProbes:
        pass                                # 无输入 ⇒ 显式跳过（report_probes 已标 SKIPPED）
    except Exception as exc:                       # noqa: BLE001 — 自检失败要报出来，不能吞
        problems.append("constraint_report_selfcheck_error:%s" % (exc,))

    return {
        "ok": not problems,
        "problems": problems,
        "report_probes": report_probes,
        "n_unattr": len(unattr_table()),
        "n_derivable": len(derivable_table()),
        "n_dead_rules": len(dead_rules_table()),
        "n_num_eps": len(num_eps_table()),
    }
