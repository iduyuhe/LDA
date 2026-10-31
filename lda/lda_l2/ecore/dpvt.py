"""多角（PVT）延迟窗口 —— 把主链的「单角单点」升级为 min/typ/max 窗口（E47 · D-239）。

═══════════════════════════════════════════════════════════════════════════════
先说一个定理（讲不清楚它，多角就只是乘系数）
───────────────────────────────────────────────────────────────────────────────
Elmore 延迟在网络上是 `τ = Σ_k R_k · C_down(k)`（k 走遍树的每条边）。
如果**所有** R 乘同一个 kr、**所有** C 乘同一个 kc，则每一项都是
`(kr·R_k)(kc·C_i)` ⇒ **τ_corner = kr·kc·τ_tt，精确成立**（不是近似）。

⇒ 结论两条，都要写进披露：
  ① 「均匀缩放下用乘系数算多角」**是对的**，所以如果模型里只有片电阻，
     多角窗口退化成**一个标量**，所有网的窗口宽度一模一样 —— 这种「多角」
     是空转的，产生不了任何网间结构；
  ② 想让窗口有结构，必须有**不跟片电阻同角的东西**。本模型里那个东西是
     **通孔电阻** `R_via`（接触/通孔电阻与片电阻的工艺灵敏度本就不必同步）。

于是本模块把 τ 拆成两段：
      τ_k = kr_k·kc_k·τ_metal + kv_k·kc_k·τ_via
两项之比随**该网自身的 via/金属构成**变化 ⇒ 每网窗口宽度不同，
via 占比高的网在慢角被拉得更宽。这是可证伪的（见 `run_ecore_e47_smoke` D4：
把 kv 设成与 kr 相同，窗口差异必须**精确消失**，退化为定理形态）。

═══════════════════════════════════════════════════════════════════════════════
口径与单位
───────────────────────────────────────────────────────────────────────────────
· 时间单位 **fs**（`Ω × fF = 1e-15 s`）；角因子无量纲。
· `CORNERS` 与 `dsignoff.CORNERS` **是同一个对象**（引用，不是复制）——
  仓内只允许一份角定义真源。
· 单角 tt（kr=kc=kv=1）与 v0.9.349 的结果**逐位相同** ⇒ 本模块是纯增量，
  不改变任何既有数字。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何引用一起给）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **只做互连线（interconnect）**：不含标准单元延迟/器件角。真实 signoff 的
   路径延迟窗口 = 单元延迟（多角 `.lib`）+ 线延迟（本模块）+ 时序借用/建立检查。
   本仓没有 PDK、没有 `.lib` ⇒ **不得**把本模块的输出叫「路径延迟窗口」。
2. 🔴 **不是 OCV / AOCV / POCV**：没有 derating 系数、没有统计变异、没有 clock。
   这是「角缩放（corner scaling）」，不是「片上变异分析」。
3. 🔴 **角因子是演示假设**：`dsignoff.CORNERS`（片电阻/电容）与 `VIA_CORNERS`
   （通孔电阻）都取自公开量级，**非任何 foundry 的 PVT 数据**。
   `VIA_CORNERS` 之所以比 `CORNERS` 更宽（0.80/1.30 vs 0.85/1.15），是**假设**：
   接触电阻对工艺更敏感 —— 该假设可用判据 D5 的灵敏度扫描检验其影响面。
4. 🔴 只有**一阶 Elmore**，无 RLC、无串扰时延、无温度相关的 R(T)。
5. 🔴 `claimable=False`，**净增 0 锚**（全是浮点组合，resid≡0）⇒ 门禁形态（E47）。
"""
from __future__ import annotations

from . import dsignoff as SG
from . import dspef as SP

# ═══════════════════════════════════════════════════════════════════════════
# ① 角定义（片 RC 引用 B3 的真源；通孔电阻另立，因为物理上不同源）
# ═══════════════════════════════════════════════════════════════════════════
#: 🔴 **同一个对象**，不是副本 —— 仓内只允许一份「角」真源。
CORNERS = SG.CORNERS

#: 通孔电阻的角因子（**演示假设**）：比片电阻更宽。
#: 物理依据：通孔/接触电阻由界面与填充决定，与片电阻（掺杂/线厚）的工艺灵敏度不同源。
VIA_CORNERS = {"ff": 0.80, "tt": 1.00, "ss": 1.30}

#: 角名顺序（tt 必在中间，判据用）
CORNER_ORDER = ("ff", "tt", "ss")

#: 通孔边在 `net["res"]` 里的识别值（与 `dspef` 写边时同一个量化值）
VIA_EDGE_R = SP.q_r(SP.R_VIA_OHM)

#: 浮点比较容差（fs）：拆分加法闭合
TOL_FS = 1e-9


# ═══════════════════════════════════════════════════════════════════════════
# ② τ 的金属/通孔拆分（**两法互证**：拆分和必须回到整体）
# ═══════════════════════════════════════════════════════════════════════════
def _edges_by_kind(net: dict) -> tuple:
    """把 `net["res"]` 分成 (金属边, 通孔边)。通孔边用电阻值精确识别并核对计数。"""
    via, metal = [], []
    for (a, b, r) in net["res"]:
        (via if r == VIA_EDGE_R else metal).append((a, b, r))
    n_decl = int(net.get("n_via") or 0)
    if len(via) != n_decl:
        raise ValueError("通孔边识别不一致：值匹配 %d 条 vs 声明 n_via=%d"
                         % (len(via), n_decl))
    return metal, via


def _tau_keeping(net: dict, kind: str) -> float:
    """只保留某一类边（另一类 R 置 0，**拓扑不变**）后的 Elmore（fs）。

    🔴 语义必须钉死：`kind="metal"` ⇒ 返回**金属段贡献**；`kind="via"` ⇒ 返回**通孔贡献**。
    加法闭合（τ == τ_metal + τ_via）**抓不到把两类写反**（对称），所以判据 D2 另配
    一个本应恰好 0 的对照组：无通孔的直导线必须 τ_via == 0 ∧ τ_metal == τ。
    """
    res = []
    for (a, b, r) in net["res"]:
        is_via = (r == VIA_EDGE_R)
        keep = is_via if kind == "via" else (not is_via)
        res.append((a, b, r if keep else 0))
    probe = dict(net)
    probe["res"] = res
    return SP.elmore_network(probe)["max_fs"]


def split_tau(net: dict) -> dict:
    """把某网的 Elmore 延迟拆成 **金属段贡献 + 通孔贡献**（fs）。

    做法：拓扑不动，只把一类边的 R 置 0 再求一次 ⇒ 因 Elmore 对 R 线性，
    两类贡献之和必须**精确**回到整体（判据 D1 就守这条加法闭合）。
    """
    metal, via = _edges_by_kind(net)
    tau = SP.elmore_network(net)["max_fs"]
    t_metal = _tau_keeping(net, "metal")
    t_via = _tau_keeping(net, "via")
    resid = tau - (t_metal + t_via)
    return {"tau_fs": tau, "tau_metal_fs": t_metal, "tau_via_fs": t_via,
            "additivity_resid_fs": resid,
            "n_via": len(via), "n_edges": len(net["res"]),
            "via_share": (t_via / tau) if tau else 0.0}


# ═══════════════════════════════════════════════════════════════════════════
# ③ 某角下的延迟（两段各自带自己的因子）
# ═══════════════════════════════════════════════════════════════════════════
def corner_tau(parts: dict, corner: str, corners: dict = None,
               via_corners: dict = None) -> float:
    """`τ_k = kr_k·kc_k·τ_metal + kv_k·kc_k·τ_via`（fs）。

    `corners` / `via_corners` 可整体替换 —— 判据 D3 用它把 kv 设成与 kr 相同，
    从而让通式**退化为定理形态**（τ_k 必须精确等于 kr·kc·τ_tt）。
    """
    cr = CORNERS if corners is None else corners
    cv = VIA_CORNERS if via_corners is None else via_corners
    if corner not in cr:
        raise KeyError("unknown corner: %r" % (corner,))
    if corner not in cv:
        raise KeyError("unknown via corner: %r" % (corner,))
    kr, kc = cr[corner]
    kv = cv[corner]
    return kr * kc * parts["tau_metal_fs"] + kv * kc * parts["tau_via_fs"]


def net_window(net: dict, corners: dict = None, via_corners: dict = None) -> dict:
    """单个网的三角窗口。**键名带 `_fs`**（单位是 fs，不是 ps）。"""
    parts = split_tau(net)
    taus = {k: corner_tau(parts, k, corners, via_corners) for k in CORNER_ORDER}
    lo, hi = min(taus.values()), max(taus.values())
    typ = taus.get("tt")
    return {"tau_fs": dict(taus), "min_fs": lo, "max_fs": hi, "typ_fs": typ,
            "spread_x": (hi / lo) if lo else None,
            "spread_pct": ((hi - lo) / typ * 100.0) if typ else None,
            "parts": parts,
            "drift_vs_typ": {k: (taus[k] / typ) if typ else None for k in taus}}


# ═══════════════════════════════════════════════════════════════════════════
# ④ 整块（多网）窗口
# ═══════════════════════════════════════════════════════════════════════════
def block_window(nets: dict, corners: dict = None, via_corners: dict = None) -> dict:
    """每个网一个窗口 + 块级 min/max/最坏网。

    返回里的 `spread_range` 是「各网窗口宽度」的 (最小, 最大) —— 判据 D4 就守
    「这两个数**必须不同**」，否则多角退化成单一标量（定理形态，见模块 docstring）。
    """
    per = {}
    for name in sorted(nets):
        per[name] = net_window(nets[name], corners, via_corners)
    if not per:
        raise ValueError("空网络集")
    spreads = [v["spread_x"] for v in per.values() if v["spread_x"]]
    worst = max(per, key=lambda n: per[n]["max_fs"])
    best = min(per, key=lambda n: per[n]["min_fs"])
    all_min = min(v["min_fs"] for v in per.values())
    all_max = max(v["max_fs"] for v in per.values())
    via_shares = [v["parts"]["via_share"] for v in per.values()]
    return {"nets": per, "n_nets": len(per),
            "block_min_fs": all_min, "block_max_fs": all_max,
            "block_spread_x": (all_max / all_min) if all_min else None,
            "worst_net": worst, "best_net": best,
            "spread_range": (min(spreads), max(spreads)) if spreads else (None, None),
            "via_share_range": (min(via_shares), max(via_shares)) if via_shares else (None, None),
            "additivity_worst_fs": max(abs(v["parts"]["additivity_resid_fs"])
                                       for v in per.values())}


def theorem_check(nets: dict) -> dict:
    """**定理检验**：把通孔角 kv 强制等于片电阻角 kr ⇒ 每网 τ_k 必须精确等于
    `kr·kc·τ_tt`，于是**所有网的窗口宽度完全相同**。

    返回 `max_abs_err_fs`（各网 τ_k 与标量积的最大绝对差）与
    `spread_uniformity`（spread 的最大/最小之比，定理成立时必须 == 1）。
    这条是 D3 的金标：它证明「kv≡kr 时多角没有结构」不是巧合，是数学后果。
    """
    cv = {k: CORNERS[k][0] for k in CORNERS}       # kv := kr
    bw = block_window(nets, via_corners=cv)
    max_err = 0.0
    for v in bw["nets"].values():
        typ = v["typ_fs"]
        for k, tau in v["tau_fs"].items():
            kr, kc = CORNERS[k]
            max_err = max(max_err, abs(tau - kr * kc * typ))
    lo, hi = bw["spread_range"]
    return {"max_abs_err_fs": max_err, "spread_range": bw["spread_range"],
            "spread_uniformity": (hi / lo) if lo else None,
            "block_spread_x": bw["block_spread_x"]}


DPVT_DISCLOSURE = {
    "what": "多角（角缩放）互连线延迟窗口：τ 拆成金属段 + 通孔段，两段各带自己的角因子",
    "claimable": False,
    "not_signoff": True,
    "zero_anchor": True,
    "scope": [
        "只做**互连线**：不含标准单元/器件角，因此**不是**「路径延迟窗口」",
        "是**角缩放**，不是 OCV/AOCV/POCV：无 derating、无统计变异、无 clock",
        "一阶 Elmore：无 RLC、无串扰时延、无 R(T)",
    ],
    "assumptions": {
        "corners_source": "dsignoff.CORNERS（引用同一对象，仓内单份真源）",
        "VIA_CORNERS": dict(VIA_CORNERS),
        "why_via_has_own_corner": "通孔/接触电阻与片电阻工艺灵敏度不同源；"
                                  "若强行让两者同角，多角窗口会退化为单一标量（见 theorem_check）",
        "corner_numbers_are_demo": True,
    },
    "known_gaps": [
        "无标准单元多角时序（.lib）⇒ 门延迟窗口缺失",
        "无 derating / OCV 系数 ⇒ 不能替代 signoff 的时序余量",
        "无温度维度（R(T)/迁移率退化未建模），只有工艺角",
        "耦合电容用「两端各半」约定，多角下未单独处理 Cc 与 Cg 的差异",
    ],
}
