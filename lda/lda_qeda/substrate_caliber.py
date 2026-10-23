"""D-220 · 超导微波的**介电口径单一真源**（caliber SSOT）—— 能力层 · 净增 0 锚。

## 为什么需要这个模块

同一个符号 `eps_eff` 在量子侧曾有 **4 个互不相同、互相零引用** 的取值：

| 位置 | 值 | 用途 |
|---|---|---|
| `sc_control._fringe_x` | 6.0 | 线间 fringe 电容 `C_x = ε·ε0·L·t/gap` |
| `sc_readout._control_xtalk` | 6.0 | 同上（逐桩串扰） |
| `sc_readout_mux.DEFAULT_MUX_PLAN` | 6.5 | 传播速度 `v_ph = c/√ε` |
| 设计常量（`n_eff = 2.5`） | 6.25 | 既有 CPW 锚的给定参数 |

而由几何反提的真值是 **6.224562**（`w=10 / g=6 / Si h=500 / εr=11.45`）。
6.0 ↔ 6.5 互差 **8.333%** ⇒ λ/4 腔长互差 **240.080 µm（3.996%）**
⇒ 腔长固定时频率从 **5.0927 GHz 漂到 4.8929 GHz，峰峰 199.8 MHz**。
超导 FDM 读出音间隔典型 10–50 MHz ⇒ 这个偏差会让一只谐振器落到隔壁**四到二十个音**上。

## 🔴 但这**不是**「抄错了」，所以**不能**统一成一个数

这四处 ε 在物理语义上并不相同：

- `sc_readout_mux` 用它算**传播速度** ⇒ 指的是**全截面填充**的有效介电常数（ε_eff）；
- `sc_control` / `sc_readout` 用它算**线间 fringe 电容** ⇒ 指的是**相邻两线之间那段 fringe 场**
  的平均介电常数。二者的场分布区域不同，数值**本来就可以不同**。

真正的病灶是：**四个值都没有来源、没有交叉引用、没有任何地方声明它们「允许不同」以及差多少**。
这属于**口径漂移（caliber drift）**，不是复制错误。

所以本模块的做法是 —— **建单一真源 + 显式声明偏离**，而不是「统一成一个数」：

1. **可反提的口径，必须反提**：`TL_EPS_EFF_REF` 直接调 `cpw_quasi_static` 从版图几何算，
   **不写字面量**。谁要改这个值，必须改几何或改物理，改不了常量。
2. **不可反提的口径，必须登记**：平台没有 fringe 场求解器 ⇒ `FRINGE_EPS_DESIGN` 只能标为
   **设计参数**，附「它是什么 / 它不是什么 / 偏离理由 / 敏感度」，并出现在 `caliber_register()` 里。
3. **允许不等，但必须可见**：`why_not_unified()` 给出机器化的理由 + 两者差值，
   门禁断言「两者都登记 且 差值被量化」，防别人日后悄悄「统一」或悄悄漂移。

## 敏感度（`sensitivity_margin()`）

fringe 口径当前 **不是瓶颈**：`C_x ∝ ε` 是线性的，而当前 `max_control_xtalk = 1.52e-05`
对上限 `0.05` 有 **约 3300×** 余量 ⇒ fringe ε 偏 ±50% 也翻不了判。
把它标成设计参数是**诚实的**，不是偷懒——但它的余量必须**可算**，不能靠嘴说。

## 红线

纯 stdlib + 平台闭式（`cpw_quasi_static` 保角映射）。零量子 SDK、LLM 不进判决路径、
不新增锚（既有 CPW 锚把 n_eff 当给定参数，本模块只是**给那个参数一个可反提的来源**）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from lda_qeda import cpw_quasi_static as CQS

ROLE = ("D-220 · 超导微波介电口径单一真源（caliber SSOT）—— 把『全截面填充 ε_eff』与"
        "『线间 fringe 场填充 ε』显式分开：可反提的必须反提，不可反提的必须登记，"
        "两者允许不等但差值必须可见。能力层，不新增锚。")
ANCHORABLE = False

# ---------------------------------------------------------------------------
# ① 可反提口径：传输线全截面填充 ε_eff（权威来源 = 保角映射闭式）
# ---------------------------------------------------------------------------
#: 参考版图几何（与既有 CPW 锚的 n_eff=2.5 同一量级口径；Si 高阻衬底）
TL_REF_GEOM: Dict[str, float] = {
    "w_um": 10.0,     # 中心导体宽
    "g_um": 6.0,      # 共面间隙
    "h_um": 500.0,    # 衬底厚度
    "eps_r": 11.45,   # Si 相对介电常数
}


def tl_eps_eff(geom: Optional[Dict[str, float]] = None) -> float:
    """传输线**全截面填充**有效介电常数 —— 从版图几何反提，不写字面量。

    物理：准 TEM 下 `v_ph = c/√ε_eff`，ε_eff 由 Ghione–Naldi 保角映射给出
    （含有限衬底厚度）。改这个值的唯一正当方式是改几何或改物理，
    **不是**改一个常量。
    """
    g = dict(TL_REF_GEOM)
    if geom:
        g.update({k: v for k, v in geom.items() if k in TL_REF_GEOM})
    fin = CQS.cpw_closed_form(float(g["w_um"]), float(g["g_um"]),
                              h_um=float(g["h_um"]), eps_r=float(g["eps_r"]))
    return float(fin["eps_eff"])


def tl_n_eff(geom: Optional[Dict[str, float]] = None) -> float:
    """传输线有效折射率 `n_eff = √ε_eff`（与既有 CPW 锚同口径）。"""
    return math.sqrt(tl_eps_eff(geom))


#: **权威值**（导入时算一次，确定性；参考几何下的全截面填充 ε_eff）
TL_EPS_EFF_REF: float = tl_eps_eff()
TL_N_EFF_REF: float = math.sqrt(TL_EPS_EFF_REF)

# ---------------------------------------------------------------------------
# ② 不可反提口径：线间 fringe 场填充 ε（设计参数 · 必须登记）
# ---------------------------------------------------------------------------
#: **设计参数**（非反提、非实测）。平台无 fringe 场求解器 ⇒ 只能登记，不能反提。
#: 它**不是** `TL_EPS_EFF_REF`，也**不应该**被统一成那个值（场分布区域不同）。
FRINGE_EPS_DESIGN: float = 6.0

FRINGE_DISCLOSURE: Dict[str, Any] = {
    "symbol": "eps_eff（fringe 口径）",
    "is": "相邻两线之间 fringe 场的平均相对介电常数，用于平行板型 fringe 电容 "
          "C_x = ε·ε0·L·t/gap（t = 膜厚，gap = 线间距）",
    "is_not": "不是传输线全截面填充 ε_eff；后者的场分布覆盖整个 CPW 截面，"
              "二者**本来就可以不同**",
    "derivable": False,
    "why_not_derivable": "平台没有 fringe 场（边缘场）求解器；解它需要二维静电场边界值问题，"
                         "与本平台的准静态保角映射不是同一类边值问题 ⇒ 如实标为设计参数",
    "deviation_vs_tl_pct": (FRINGE_EPS_DESIGN - TL_EPS_EFF_REF) / TL_EPS_EFF_REF * 100.0,
    "sensitivity": "C_x 与 ε 呈**线性** ⇒ ε 的相对误差等量传到 X=C_x/C_q；"
                   "而 X 对限值有约 3300× 余量（见 sensitivity_margin()）⇒ 不构成判决瓶颈",
    "revisit": "将来若引入二维 fringe 场求解（或用 foundry 给出的 fringe 电容表），"
               "可把本参数升级为反提量；届时须同步登记 provenance 变更",
}

# ---------------------------------------------------------------------------
# ③ 口径登记表（门禁据此断言「每一处使用都被登记」，防第 5 个值悄悄出现）
# ---------------------------------------------------------------------------
def caliber_register() -> List[Dict[str, Any]]:
    """返回所有介电口径的登记表。每个使用点必须能落到其中一条。"""
    return [
        {
            "id": "TL",
            "quantity": "全截面填充 ε_eff",
            "value": TL_EPS_EFF_REF,
            "derivable": True,
            "source": "反提：cpw_quasi_static.cpw_closed_form（保角映射 Ghione–Naldi）",
            "used_by": [
                "sc_readout_mux.resonator_length_um",
                "sc_readout_mux.resonator_freq_ghz",
                "sc_readout_mux.DEFAULT_MUX_PLAN['eps_eff']",
            ],
            "note": "唯一权威来源；不许在调用处写字面量",
        },
        {
            "id": "FRINGE",
            "quantity": "线间 fringe 场填充 ε",
            "value": FRINGE_EPS_DESIGN,
            "derivable": False,
            "source": "设计参数登记（平台无 fringe 场求解器）",
            "used_by": [
                "sc_control._fringe_x",
                "sc_readout._control_xtalk",
            ],
            "note": "与 TL **允许不等**；差值见 FRINGE_DISCLOSURE['deviation_vs_tl_pct']",
        },
    ]


def caliber_values() -> Dict[str, float]:
    """口径 id → 值（供门禁做集合比对）。"""
    return {r["id"]: float(r["value"]) for r in caliber_register()}


def why_not_unified() -> Dict[str, Any]:
    """**为什么不把两个口径统一成一个数** —— 机器化的理由（防日后被「简化」掉）。

    一句话：统一会让二者之一变错。取 TL 值算 fringe 电容，等于假设线间场与全截面场
    填充相同；取 fringe 值算传播速度，等于假设整个截面只填了 fringe 那部分介质。
    """
    tl, fr = TL_EPS_EFF_REF, FRINGE_EPS_DESIGN
    return {
        "unified": False,
        "reason_if_unified_to_TL": (
            "把 fringe 电容的 ε 换成 %.6f ⇒ 假设线间 fringe 场与全截面填充相同；"
            "二者场分布区域不同，属物理上不成立的替换" % tl),
        "reason_if_unified_to_FRINGE": (
            "把传播速度的 ε 换成 %.6f ⇒ 假设整个 CPW 截面只填了 fringe 那部分介质；"
            "会让 λ/4 腔长偏 %.3f%%" % (fr, (fr - tl) / tl * 100.0)),
        "deviation_pct": (fr - tl) / tl * 100.0,
        "deviation_abs": fr - tl,
        "decision": "保留两口径 + 显式登记偏离（本模块），不做数值统一",
        "gate": "run_substrate_caliber_smoke 断言：两者都登记 ∧ 差值被量化 ∧ 调用处无字面量",
    }


def sensitivity_margin(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """fringe 口径的**余量证明**：证明它当前不是判决瓶颈（否则「标成设计参数」就是偷懒）。

    做法：把 fringe ε 在 ±50% 内扰动，看 `sc_readout.crosstalk_budget` 的
    `control_xtalk_ok` 判决会不会翻。
    """
    from lda_qeda import sc_readout as S4

    p = {"rows": 2, "cols": 2}
    if params:
        p.update(params)

    base = S4.crosstalk_budget(dict(p, eps_eff=FRINGE_EPS_DESIGN))
    x0 = float(base["max_control_xtalk"])
    lim = float(base["control_xtalk_limit"])
    rows = []
    for factor in (0.5, 0.75, 1.0, 1.25, 1.5):
        if factor == 1.0:
            # 复用 base：`crosstalk_budget` 内部要跑 `solve_coupler`（数值求解），
            # 重复算同一点纯属浪费 —— 实测占本函数 ~1/6 耗时。
            rows.append({"factor": 1.0, "eps_eff": FRINGE_EPS_DESIGN,
                         "max_control_xtalk": x0, "ok": bool(base["control_xtalk_ok"])})
            continue
        e = FRINGE_EPS_DESIGN * factor
        r = S4.crosstalk_budget(dict(p, eps_eff=e))
        rows.append({"factor": factor, "eps_eff": e,
                     "max_control_xtalk": float(r["max_control_xtalk"]),
                     "ok": bool(r["control_xtalk_ok"])})
    worst = max(r["max_control_xtalk"] for r in rows)
    return {
        "base_eps_eff": FRINGE_EPS_DESIGN,
        "base_max_control_xtalk": x0,
        "limit": lim,
        "margin_x": (lim / x0) if x0 > 0 else float("inf"),
        "scan": rows,
        "all_ok": all(r["ok"] for r in rows),
        "worst_max_control_xtalk": worst,
        "verdict": "NOT_BINDING" if all(r["ok"] for r in rows) else "BINDING",
        "note": ("余量 = 限值/实测；若 >=10× 则 fringe 口径的精度不构成判决瓶颈，"
                 "标为设计参数是诚实的；若 <10× 则必须升级为反提量"),
    }


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    chk("① TL 口径 = cpw_quasi_static 反提（同值再算一次，rel<1e-15）",
        abs(tl_eps_eff() - TL_EPS_EFF_REF) <= 1e-15 * TL_EPS_EFF_REF)
    chk("② n_eff = √ε_eff（自洽）",
        abs(TL_N_EFF_REF ** 2 - TL_EPS_EFF_REF) <= 1e-12 * TL_EPS_EFF_REF)
    chk("③ 参考几何反提值落在 (6.0, 6.5) 之间（6.0/6.5 都是拍的，真值在中间）",
        6.0 < TL_EPS_EFF_REF < 6.5)
    chk("④ 真空极限：εr=1 ⇒ ε_eff = 1（保角映射退化正确）",
        abs(tl_eps_eff({"eps_r": 1.0}) - 1.0) <= 1e-12)
    chk("⑤ ε_eff 随 εr 单调增（物理正确）",
        tl_eps_eff({"eps_r": 4.0}) < tl_eps_eff({"eps_r": 11.45}) < tl_eps_eff({"eps_r": 12.9}))
    chk("⑥ 两口径差值被量化（|deviation| 与重算一致）",
        abs(FRINGE_DISCLOSURE["deviation_vs_tl_pct"]
            - (FRINGE_EPS_DESIGN - TL_EPS_EFF_REF) / TL_EPS_EFF_REF * 100.0) <= 1e-12)
    chk("⑦ 两口径【允许不等】且确实不等（防有人把它们悄悄统一）",
        abs(TL_EPS_EFF_REF - FRINGE_EPS_DESIGN) > 1e-6)
    chk("⑧ 登记表覆盖两口径且 derived 标注正确",
        {r["id"] for r in caliber_register()} == {"TL", "FRINGE"}
        and all(r["derivable"] == (r["id"] == "TL") for r in caliber_register()))
    chk("⑨ why_not_unified 给出双向理由 + 差值",
        (not why_not_unified()["unified"])
        and why_not_unified()["reason_if_unified_to_TL"]
        and why_not_unified()["reason_if_unified_to_FRINGE"])
    sm = sensitivity_margin()
    chk("⑩ fringe 口径余量 >= 10×（当前 %.1f×）⇒ 标为设计参数是诚实的"
        % sm["margin_x"], sm["margin_x"] >= 10.0)
    chk("⑪ 负结果机器化：不可锚（本模块只统一来源，不产生新物理量）", ANCHORABLE is False)

    if verbose:
        for n, v in msgs:
            print(("  [PASS] " if v else "  [FAIL] ") + n)
    return ok


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print("---")
    print("substrate_caliber 自检:", "ALL PASS" if ok else "FAIL")
    print("TL eps_eff = %.6f | n_eff = %.6f | FRINGE = %.1f | 偏离 = %+.3f%%"
          % (TL_EPS_EFF_REF, TL_N_EFF_REF, FRINGE_EPS_DESIGN,
             FRINGE_DISCLOSURE["deviation_vs_tl_pct"]))
