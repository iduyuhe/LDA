#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E43 门禁：**SPEF 级提取** —— 分布式 RC 网络 + IEEE 1481-1998 子集写出/读回。

## 本门禁守什么
B3 的 `net_rc` 只给两个**标量**（R、C）。真实时序工具要的是**网络**：节点 + 地电容 +
节点对电阻 + 耦合电容。没有网络，串扰/屏蔽/局部热点全都不可见，也无法交手复查。
E43 守的是「网络这一层」自洽且可逆：

| # | 守护 | 金标 |
|---|---|---|
| A1 | 网络 Elmore ≡ 闭式 | 单段控制用例（n=1,2,4,8,16）**逐点**等于 `dsignoff.elmore_closed`（相对 <1e-5） |
| A2 | 量化守恒 | 最大余数法：`Σ量化 ≡ 量化总量`（含全零/等分/单值边界）⇒ 网络总量与标量口径可逐位对拍 |
| A3 | 与 B3 标量口径对拍 | 网络 ΣR_metal ≡ `net_rc(合并矩形)` 的 r；ΣC_ground ≡ 其 c（相对 <1e-5） |
| A4 | 网络结构完整性 | 每网单连通 ∧ 无自环 ∧ 所有 R>0 ∧ 所有 C≥0 ∧ 有驱动/负载端口 ∧ via 数与几何一致 |
| B1 | SPEF 文本合规 | 必需头部齐 ∧ `*D_NET` 与 `*END` 配对 ∧ 段序 CONN→CAP→RES |
| B2 | **round-trip 逐位相等** | `parse(write(N))` 与 N 的节点/电容/电阻/耦合/端口**完全一致**（不是近似） |
| B3 | 独立参考档（防自证） | 手写 SPEF（PF + KOHM + NAME_MAP + 跨网耦合 + 字面名）解析出**预期精确值** |
| B4 | 单位换算双向 | C∈{FF,PF,NF} × R∈{OHM,KOHM,MOHM} 九种组合，解析值严格按倍率变 |
| B5 | total 约定自洽 | `*D_NET` 的 total ≡ Σ地 + Σ耦合（全值不折半，约定单点定义） |
| C1 | 判别力（8 类篡改） | 缺 `*END`／RES 未知节点／越界单位／负电容／重复 D_NET／耦合未知节点／缺 `*R_UNIT`／RES 自环 **全部必红** |
| C2 | total 篡改可检出 | 改大 total ⇒ `declared != computed`（不静默通过） |
| C3 | 确定性 | 两次写出**逐字节相同** ∧ DATE 不取墙钟 |
| B0 | 耗时 | < 阈值 |

## 诚实口径
- 🔴 **无第三方回读验证**：格式按 IEEE 1481-1998 常见子集写，但没有商业 STA/提取工具
  回读过 ⇒ 只能宣称「格式合规 + 自解析可逆」，**不能**宣称「与商业流程互通」。
- 🔴 **精度没有提升**：SPEF 只**搬运**运算，不改物理；提取仍是一阶平板+边缘修正。
- 🔴 **净增 0 锚**（整数定点 ⇒ `resid≡0`）⇒ 门禁形态（同 E39–E42）；不报 TOPS/fJ/能效。
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2.ecore import dspef as SP          # noqa: E402
from lda_l2.ecore import dsignoff as SG       # noqa: E402
from lda_l2.ecore import dcroute as RT        # noqa: E402
from lda_l2.ecore import ddetail as DD        # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402

AN_ELAPSED_MAX_S = 60.0

PASS = 0
FAIL = 0
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   detail_fmt="  :: {d}", return_ok=True)

_LAYER = {DD.L_M3: "M3", DD.L_M4: "M4"}

# 独立手写参考档（**不经过本仓的写出器**，用于验证解析器本身）
REF_SPEF = """*SPEF "IEEE 1481-1998"
*DESIGN "REF_HAND"
*DATE "2026-01-01T00:00:00"
*VENDOR "hand"
*PROGRAM "hand"
*VERSION "1.0"
*DESIGN_FLOW "PIN_CAP NONE"
*DIVIDER /
*DELIMITER :
*BUS_DELIMITER [ ]
*T_UNIT 1 PS
*C_UNIT 1 PF
*R_UNIT 1 KOHM
*L_UNIT 1 HENRY
*NAME_MAP
*1 ra
*2 ra:1
*3 ra:2
*4 rb
*5 rb:1
*PORTS
*2 I *1
*3 O *1
*D_NET *1 2.750
*CONN
*P *2 I
*P *3 O
*CAP
1 *2 1.000
2 *3 1.500
3 *2 *5 0.250
*RES
1 *2 *3 2.000
*END
*D_NET *4 0.250
*CONN
*I *5 O
*CAP
1 *5 0.250
*END
*D_NET rc 0.100
*CAP
1 rc:1 0.100
*END
"""


def _build():
    case = RT.build_case()
    routed = RT.route(case)
    ports = {n["name"]: {"in": [n["a"]], "out": [n["b"]]} for n in case["nets"]}
    net = SP.extract_network(routed["shapes"], design="LDA_B2_DEMO",
                             seg_um=1.0, ports=ports)
    return net, routed


def _merged_shapes(net, netname):
    return [DD.Shape(L, a, b, c, d, net=netname, kind="metal")
            for (L, a, b, c, d) in net["merged"][netname]]


def main():
    t0 = time.time()
    print("=" * 78)
    print("E43 · SPEF 级提取（分布式 RC 网络 + IEEE 1481-1998 子集）")
    print("=" * 78)

    net, routed = _build()

    # ── A1 网络 Elmore ≡ 闭式（单段控制用例）──────────────────────────
    r_w = SG.wire_r(5.0, 0.24, "M3")
    c_w = SG.wire_c(5.0, 0.24)
    closed = SG.elmore_closed(r_w, c_w, SG.C_LOAD_FF)
    rows = []
    for nseg in (1, 2, 4, 8, 16):
        wnet = SP.build_wire_network(5.0, 0.24, nseg)["nets"]["w0"]
        el = SP.elmore_network(wnet, c_load_ff=SG.C_LOAD_FF)
        rows.append((nseg, el["max_fs"], abs(el["max_fs"] - closed) / closed))
    worst = max(x[2] for x in rows)
    check("A1 网络 Elmore ≡ 闭式 R(C/2+C_load)：n=1,2,4,8,16 逐点吻合（半分流在任意 n 下精确）",
          worst < 1e-5, "closed=%.9f 最差相对差=%.2e @n=%d · %s"
          % (closed, worst, [x[0] for x in rows if x[2] == worst][0],
             " ".join("n%d:%.6f" % (a, b) for a, b, _c in rows)))

    # ── A2 量化守恒（最大余数法）────────────────────────────────────
    app_cases = [
        ([312.5] * 8, SP.q_r(312.5 * 8)),          # 等分且恰半格
        ([1.0 / 3.0] * 3, SP.q_r(1.0)),            # 无限小数
        ([0.0, 0.0, 0.0], 0),                      # 全零
        ([0.0724847], SP.q_c(0.0724847)),          # 单值
        ([0.1, 0.2, 0.3, 0.9], SP.q_r(1.5)),       # 一般情形
    ]
    app_bad = []
    for vals, target in app_cases:
        got = sum(SP._apportion(vals, target, SP.R_GRID))
        if got != target:
            app_bad.append((vals[:2], target, got))
    check("A2 量化守恒：Σ量化 ≡ 量化总量（最大余数法，含等分/无限小数/全零/单值边界）",
          not app_bad, "样本 %d 组 · 违例 %s" % (len(app_cases), app_bad or "无"))

    # ── A3 与 B3 标量口径对拍 ────────────────────────────────────────
    dr, dc = [], []
    for nm in sorted(net["nets"]):
        rc = SG.net_rc(_merged_shapes(net, nm), lambda L: _LAYER.get(L, "X"), nm)
        tot = SP.net_totals(net["nets"][nm])
        dr.append(abs(rc["r_ohm"] - tot["r_metal_ohm"]) / rc["r_ohm"])
        dc.append(abs(rc["c_ff"] - tot["c_gnd_ff"]) / rc["c_ff"])
    check("A3 网络总量 ≡ B3 标量口径（同一合并几何喂 net_rc）：ΣR_metal、ΣC_ground 均吻合",
          max(dr) < 1e-5 and max(dc) < 1e-5,
          "R 最差 %.2e · C 最差 %.2e（网数 %d）" % (max(dr), max(dc), len(dr)))

    # ── A4 网络结构完整性 ───────────────────────────────────────────
    struct_bad = []
    for nm in sorted(net["nets"]):
        d = net["nets"][nm]
        try:
            el = SP.elmore_network(d, c_load_ff=SG.C_LOAD_FF)
        except ValueError as e:
            struct_bad.append("%s 不连通(%s)" % (nm, e))
            continue
        if el["n_edges"] != el["n_nodes"] - 1:
            struct_bad.append("%s 非树 E=%d V=%d" % (nm, el["n_edges"], el["n_nodes"]))
        if not d["ports"]["in"] or not d["ports"]["out"]:
            struct_bad.append("%s 缺端口" % nm)
        if any(r <= 0 for (_a, _b, r) in d["res"]):
            struct_bad.append("%s 有非正电阻" % nm)
        if any(v["c"] < 0 for v in d["nodes"].values()):
            struct_bad.append("%s 有负电容" % nm)
        if any(a == b for (a, b, _r) in d["res"]):
            struct_bad.append("%s 有自环" % nm)
        n_via_geo = sum(1 for s in routed["shapes"] if s.net == nm and s.layer == DD.L_VIA2)
        if int(d.get("n_via") or 0) != n_via_geo:
            struct_bad.append("%s via %d≠几何 %d" % (nm, d.get("n_via"), n_via_geo))
    check("A4 网络结构完整性：每网单连通树 ∧ 无自环 ∧ R>0 ∧ C≥0 ∧ 端口齐 ∧ via 数与几何一致",
          not struct_bad, "%s" % (struct_bad or "全部通过（%d 网）" % len(net["nets"])))

    # ── B1 SPEF 文本合规 ────────────────────────────────────────────
    txt = SP.spef_write(net)
    lines = [x for x in txt.splitlines() if x.strip()]
    need = ('*SPEF "IEEE 1481-1998"', "*DESIGN", "*DATE", "*T_UNIT", "*C_UNIT",
            "*R_UNIT", "*NAME_MAP", "*PORTS", "*D_NET")
    missing = [h for h in need if not any(x.startswith(h) for x in lines)]
    n_dnet = sum(1 for x in lines if x.startswith("*D_NET"))
    n_end = sum(1 for x in lines if x.strip() == "*END")
    order_bad = []
    for i, x in enumerate(lines):
        if x.startswith("*D_NET"):
            seg = []
            j = i + 1
            while j < len(lines) and not lines[j].startswith("*D_NET"):
                if lines[j].startswith("*CONN") or lines[j].startswith("*CAP") \
                        or lines[j].startswith("*RES") or lines[j] == "*END":
                    seg.append(lines[j])
                j += 1
            idx = {s: k for k, s in enumerate(seg)}
            if "*END" not in idx or "*CAP" not in idx or "*CONN" not in idx:
                order_bad.append(lines[i].split()[1])
            elif not (idx["*CONN"] < idx["*CAP"] < idx.get("*RES", 99) < idx["*END"]):
                order_bad.append(lines[i].split()[1])
    check("B1 SPEF 文本合规：必需头部齐 ∧ *D_NET 与 *END 配对 ∧ 段序 CONN→CAP→RES→END",
          not missing and n_dnet == n_end == len(net["nets"]) and not order_bad,
          "缺头 %s · D_NET=%d END=%d 网=%d · 段序错 %s"
          % (missing or "无", n_dnet, n_end, len(net["nets"]), order_bad or "无"))

    # ── B2 round-trip 逐位相等 ──────────────────────────────────────
    back = SP.spef_parse(txt)
    diffs = SP.compare_networks(net, back)
    check("B2 round-trip 逐位相等：parse(write(N)) 与 N 的节点/电容/电阻/耦合/端口完全一致",
          not diffs, "%d 字节 / %d 行 · 差异 %s" % (len(txt), len(lines), diffs[:3] or "无"))

    # ── B3 独立手写参考档（防自证）──────────────────────────────────
    ref = SP.spef_parse(REF_SPEF)
    base = SP.C_GRID * 1000          # 1 pF 在 C 网格下的单位数 = 1e9
    exp_nodes = {"ra:1": base, "ra:2": base * 3 // 2}
    ref_ok = (
        ref["nets"]["ra"]["nodes"] == {k: {"c": v} for k, v in exp_nodes.items()}
        and ref["nets"]["ra"]["res"] == [["ra:1", "ra:2", SP.R_GRID * 2000]]
        and ref["nets"]["ra"]["coupling"] == [["ra:1", "rb:1", base // 4]]
        and ref["nets"]["ra"]["ports"] == {"in": ["ra:1"], "out": ["ra:2"]}
        and ref["nets"]["rb"]["ports"] == {"in": [], "out": ["rb:1"]}
        and ref["nets"]["rc"]["nodes"] == {"rc:1": {"c": SP.C_GRID * 100}}
    )
    check("B3 独立参考档（手写 PF+KOHM+NAME_MAP+跨网耦合+字面名）解析出预期精确值",
          ref_ok, "ra 节点=%s res=%s cpl=%s · rb ports=%s · rc=%s"
          % (ref["nets"]["ra"]["nodes"], ref["nets"]["ra"]["res"],
             ref["nets"]["ra"]["coupling"], ref["nets"]["rb"]["ports"],
             ref["nets"]["rc"]["nodes"]))

    # ── B4 单位换算双向 ─────────────────────────────────────────────
    c_mult = {"FF": 1, "PF": 1000, "NF": 10 ** 6}
    r_mult = {"OHM": 1, "KOHM": 1000, "MOHM": 10 ** 6}
    unit_bad = []
    for cu, cm in c_mult.items():
        for ru, rm in r_mult.items():
            t = REF_SPEF.replace("*C_UNIT 1 PF", "*C_UNIT 1 " + cu) \
                         .replace("*R_UNIT 1 KOHM", "*R_UNIT 1 " + ru)
            q = SP.spef_parse(t)
            got_c = q["nets"]["ra"]["nodes"]["ra:1"]["c"]
            got_r = q["nets"]["ra"]["res"][0][2]
            if got_c != cm * SP.C_GRID or got_r != 2 * rm * SP.R_GRID:
                unit_bad.append("%s/%s (c=%d r=%d)" % (cu, ru, got_c, got_r))
    check("B4 单位换算双向：C∈{FF,PF,NF} × R∈{OHM,KOHM,MOHM} 九组合按倍率严格变",
          not unit_bad, "九组合 · 违例 %s" % (unit_bad or "无"))

    # ── B5 total 约定自洽 ──────────────────────────────────────────
    tot_bad = ["%s %d≠%d" % (nm, back["nets"][nm]["total_declared"],
                             back["nets"][nm]["total_computed"])
               for nm in sorted(back["nets"])
               if back["nets"][nm]["total_declared"] != back["nets"][nm]["total_computed"]]
    check("B5 *D_NET total ≡ Σ地 + Σ耦合（全值不折半）：约定单点定义且写读一致",
          not tot_bad, "%s" % (tot_bad or "四网全自洽"))

    # ── C1 判别力：8 类篡改必须全部被拒 ────────────────────────────
    muts = [
        ("缺 *END", REF_SPEF.replace("*CAP\n1 rc:1 0.100\n*END\n", "*CAP\n1 rc:1 0.100\n")),
        ("RES 未知节点", REF_SPEF.replace("1 *2 *3 2.000", "1 *2 *9 2.000")),
        ("越界单位", REF_SPEF.replace("*C_UNIT 1 PF", "*C_UNIT 1 XF")),
        ("负电容", REF_SPEF.replace("1 *2 1.000", "1 *2 -1.000")),
        ("重复 D_NET", REF_SPEF + "*D_NET *1 1.000\n*CAP\n1 *2 1.000\n*END\n"),
        ("耦合未知节点", REF_SPEF.replace("3 *2 *5 0.250", "3 *2 *77 0.250")),
        ("缺 *R_UNIT", REF_SPEF.replace("*R_UNIT 1 KOHM\n", "")),
        ("RES 自环", REF_SPEF.replace("1 *2 *3 2.000", "1 *2 *2 2.000")),
    ]
    not_caught = []
    for label, text in muts:
        try:
            SP.spef_parse(text)
            not_caught.append(label)
        except SP.SpefError:
            pass
    check("C1 判别力：缺 END／RES 未知节点／越界单位／负电容／重复 D_NET／耦合未知节点／缺 R_UNIT／自环 八类篡改全部必红",
          not not_caught, "漏抓 %s" % (not_caught or "无（8/8 全抓）"))

    # ── C2 total 篡改可检出 ────────────────────────────────────────
    bad = SP.spef_parse(REF_SPEF.replace("*D_NET *1 2.750", "*D_NET *1 2.900"))
    check("C2 total 篡改可检出：把 *D_NET total 改大 ⇒ declared ≠ computed（不静默通过）",
          bad["nets"]["ra"]["total_declared"] != bad["nets"]["ra"]["total_computed"],
          "declared=%d computed=%d" % (bad["nets"]["ra"]["total_declared"],
                                       bad["nets"]["ra"]["total_computed"]))

    # ── C3 确定性 ──────────────────────────────────────────────────
    t2 = SP.spef_write(net)
    date_line = [x for x in lines if x.startswith("*DATE")][0]
    check("C3 确定性：两次写出逐字节相同 ∧ DATE 取固定常量（不取墙钟）",
          t2 == txt and SP.FIXED_DATE in date_line,
          "%d 字节一致 · %s" % (len(txt), date_line))

    # ── B0 耗时 ────────────────────────────────────────────────────
    dt = time.time() - t0
    check("B0 门禁耗时 %.2f s < %.0f s（阈值留余量）" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S, "%.9f" % dt)

    print("  [诚实边界] %s" % "；".join(SP.SPEF_DISCLOSURE["limits"][:3]))
    print("-" * 78)
    print("E43 · 通过 %d · 失败 %d · 耗时 %.2f s" % (PASS, FAIL, dt))
    if FAIL:
        print("E43 有红色：见上方 [FAIL] 行")
        return 1
    print("E43 全绿 · SPEF 级提取：分布式 RC 网络 · round-trip 逐位可逆 · 单位/约定双向 · 八类篡改必红"
          " · 净增 0 锚（**无第三方工具回读**，见披露清单）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
