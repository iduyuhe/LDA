"""v0.9.128 G4 · LVS 器件参数几何回提 smoke（版图↔原理图**尺寸**一致性）。

v0.9.141（M4 攻关）：把「几何回提」从 7 类器件 / 7 参数扩到**全部 14 类器件 /
44 参数**，并把「覆盖率口径」与「参数分类」机器化。

验证 `lda_l2.lvs_geom` + `lvs.run_lvs(with_geom_check=True)`：
  1. 合法必过：一致版图 → 零违规、测量值 == 声明值（机器精度）
  2. 反向护栏（两反例）：篡改**几何**（改波导长度 / 改环半径）→
     `device_param_mismatch` 必报，measured == 篡改值
  3. 判据升级实证：同一篡改版图，`with_geom_check=False` → ACCEPT（旧口径
     **漏检**）/ `=True` → REJECT ⇒ 新判据**实质有效**，不是恒真自证
  4. 合法必过（多类）：**14 类**可回提器件全部 `ok`
  5. 独立重算：smoke 自己从几何算环半径，与模块自报值逐位一致
  6. 测量独立性：测量器源码**不读 params**（只读几何）
  7. 不误报：几何不可生成的 kind → 登记 `geom_failed` 且**不报违规**
  8. 诚实性：不可回提参数逐条登记**类别 + 原因**（来自 `PARAM_TAXONOMY`）
  9. 既有零影响：S9 五案例在**不启用**几何回提时判决与既有口径一致
 10. 红线：`lvs_geom.py` 源码零 LLM 引用（判决全死标量）
 11. 多层入口：`run_lvs_multilayer` 与单层共用同一助手（同样支持）
 12. **类覆盖（M4 口径）**：`class_coverage() == 14/14`，且 `DEVICE_CLASSES`
     与 `link_model` 认识的器件类**对表**（防两处漂移）
 13. **往返（14 类 × 31 参数）**：每类规范声明逐参数 |delta| < 1e-9
 14. **参数分类机器复核**：敏感性 ↔ 类别三档一致（`geometric` 敏感且可回提 /
     `encoded_not_recovered` 敏感但不可回提 / `not_encoded` 几何**不变**），
     且规范声明与工厂声明的参数**零未分类**
 15. **逐类反向证据（表驱动）**：每个 `geometric` 参数 ⇒ 按「改后声明」绘制
     必报且 measured == 改后值；每个 `encoded_not_recovered` ⇒ 几何变而**零违规**
     （如实登记"越界不会假报"）
 16. 几何量口径：`coverage_geometric == 1.0`，而 `coverage_declared < 1.0`
     **结构性**（物理量/目标量不落在版图几何上）

运行：python run_lvs_geom_smoke.py
"""
from __future__ import annotations

import inspect
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_chain.link_model import LinkModel, _DEFAULT_PORTS
from lda_harness.lvs_anchor import build_lvs_case, s9_lvs_verdict
from lda_harness.smoke_kit import make_check
from lda_l2.chip_layout_export import device_geom_of
from lda_l2.lvs import run_lvs
from lda_l2.lvs_geom import (CANONICAL_PARAMS, CLASS_UNCLASSIFIED,
                             DEVICE_CLASSES, GEOM_UNSUPPORTED_KINDS,
                             MEASURER_NAMES, NO_NAMED_ADD_DEVICE,
                             PARAM_MEASURERS, class_coverage, classify_param,
                             extract_layout_params, measure_device_params)

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)


# ---------------------------------------------------------------------------
# 几何篡改器（反向护栏用）—— 🔴 必须篡改**几何**，不能篡改 params
#   （篡改 params ⇒ 现场生成几何随动 ⇒ 自洽不漏，那测不出判据有效性）
# ---------------------------------------------------------------------------
def _set_path_span(geoms, new_span: float):
    """把全部 PATH 的 x 跨度改为 new_span（保持起点、改终点）。"""
    out = []
    for g in geoms:
        if g[0] == "P":
            x0, y0 = g[3][0]          # 保持起点，只改终点 ⇒ 跨度 = new_span
            out.append(("P", g[1], g[2], ((x0, y0), (x0 + new_span, y0))))
        else:
            out.append(g)
    return out


def _tamper_wg0(c, placement, wg_width):
    g = device_geom_of(c, placement, wg_width)
    return _set_path_span(g, 30.0) if c.id == "wg0" else g


def _tamper_ring0(c, placement, wg_width, R_new: float = 8.0):
    g = device_geom_of(c, placement, wg_width)
    if c.id != "ring0":
        return g
    ox, oy = placement[c.id][0], placement[c.id][1]
    ring = tuple((ox + R_new * math.cos(2 * math.pi * i / 64),
                  oy + R_new * math.sin(2 * math.pi * i / 64))
                 for i in range(64))
    return [("P", g[0][1], g[0][2], ring)] + list(g[1:])


# ---------------------------------------------------------------------------
# ⑮⑯⑰⑱ 通用助手：声明变异 + 几何绘制 + 回提（表驱动，14 类共用一套机制）
# ---------------------------------------------------------------------------
def _mutate(v: float) -> float:
    """声明值的「合法但不同」变异 —— 保持几何仍然可生成。

    整数型（`periods`/`n_out`/`n_in`/`R` 等）用 +3（×1.37 会被 int() 吞掉：
    首版实测 `n_out=2 → int(2.6)=2` ⇒ 假"不敏感"）；浮点用 ×1.37（+3 会把
    `corrugation=0.12` 抬到 3.12 > width ⇒ 几何直接 raise）。
    """
    return v + 3.0 if float(v).is_integer() else v * 1.37


def _geom_of_with(kind: str, params: dict):
    """几何生成回调：按**另一份声明**绘制几何（真 G4 失配场景的合成器）。

    ⚠️ 与「篡改 params」的区别：这里被测组件的**声明不动**，只是拿另一份
    声明去生成版图 —— 正是"版图画成 30µm 而原理图声明 20µm"的机器复刻。
    """
    from lda_ir.core import Component, Port
    fake = Component(id="d0", kind=kind, params=dict(params),
                     ports=[Port("in"), Port("out")])

    def geom_of(_c, placement, wg_width):
        return device_geom_of(fake, placement, wg_width)
    return geom_of


def _rt(kind: str, params: dict) -> dict:
    """单器件：规范声明 → 几何 → 回提报告。"""
    lm = LinkModel(name=f"g4_{kind}")
    lm.add_device("d0", kind, dict(params))
    return extract_layout_params(lm, {"d0": (0.0, 0.0, 0.0)})


def _geom_fp(kind: str, params: dict) -> str:
    """几何**指纹**（用于证明「几何是否随某声明变」）。

    🔴 必须用**几何本身**而非"测量值"来判敏感性：测量器只覆盖回提表内的参数，
    不在表内的参数两次测量都是 None ⇒ 「不敏感」恒真 —— 那是**恒真自证**
    （正是本仓 U 系列血案里的"纯绿不能自证"）。
    """
    lm = LinkModel(name=f"fp_{kind}")
    lm.add_device("d0", kind, dict(params))
    g = device_geom_of(lm.ir.components[0], {"d0": (0.0, 0.0, 0.0)}, 0.5)
    return repr(g)


def main() -> int:
    print("G4 · LVS 器件参数几何回提 smoke（版图↔原理图尺寸一致性）")

    link, placement, routes = build_lvs_case("consistent")

    # ① 合法必过：零违规 + 全器件全参数已比对
    rep = extract_layout_params(link, placement, wg_width=0.5)
    check("① 合法必过：一致版图 → 几何回提零违规",
          rep["violations"] == [] and rep["n_devices_checked"] == 3
          and rep["n_params_checked"] == 3,
          f"viol={len(rep['violations'])} dev={rep['n_devices_checked']}"
          f"/{rep['n_devices']} params={rep['n_params_checked']}")
    check("① 覆盖率三档口径均 =1.0（本 case 全参数可回提）",
          rep["coverage_by_table"] == 1.0 and rep["coverage_declared"] == 1.0
          and rep["coverage_geometric"] == 1.0,
          f"table={rep['coverage_by_table']} decl={rep['coverage_declared']}"
          f" geom={rep['coverage_geometric']}")

    # ② 测量精度：delta 为零（机器精度）
    max_delta = max((abs(d) for v in rep["devices"].values()
                     for d in v["deltas"].values()), default=float("inf"))
    check("② 测量值 == 声明值（|delta| == 0，机器精度）",
          max_delta == 0.0, f"max|delta|={max_delta:.3e}")

    # ③ 反向护栏-1：篡改波导长度（几何 20 → 30 µm）
    r1 = extract_layout_params(link, placement, wg_width=0.5,
                               geom_of=_tamper_wg0)
    v1 = r1["violations"]
    check("③ 反向-改长度：必报 device_param_mismatch（measured=30）",
          len(v1) == 1 and v1[0]["inst"] == "wg0"
          and v1[0]["param"] == "length" and v1[0]["measured"] == 30.0
          and v1[0]["declared"] == 20.0,
          f"viol={v1}")

    # ④ 反向护栏-2：篡改环半径（几何 10 → 8 µm）
    r2 = extract_layout_params(link, placement, wg_width=0.5,
                               geom_of=_tamper_ring0)
    v2 = r2["violations"]
    check("④ 反向-改半径：必报（measured=8，declared=10）",
          len(v2) == 1 and v2[0]["inst"] == "ring0"
          and v2[0]["param"] == "R" and abs(v2[0]["measured"] - 8.0) < 1e-12
          and v2[0]["declared"] == 10.0,
          f"viol={v2}")
    check("④ 改半径不连带误报其它器件（仅 1 项）",
          len(v2) == 1 and r2["n_params_checked"] == 3,
          f"n_viol={len(v2)} checked={r2['n_params_checked']}")

    # ⑤ 判据升级实证：旧口径漏检 / 新口径 REJECT
    old = run_lvs(link, placement, routes)                      # 默认不启用
    new = run_lvs(link, placement, routes, with_geom_check=True,
                  geom_of=_tamper_wg0)
    check("⑤ 旧口径（with_geom_check=False）漏检：仍 ACCEPT",
          old["verdict"] == "ACCEPT" and old.get("geom_check") is None,
          f"verdict={old['verdict']} geom_check={old.get('geom_check')}")
    check("⑤ 新口径（=True）实质有效：REJECT 且含 device_param_mismatch",
          new["verdict"] == "REJECT"
          and "device_param_mismatch" in new["violations"]
          and new["geom_check"]["violations"][0]["measured"] == 30.0,
          f"verdict={new['verdict']} kinds={sorted(new['violations'])}")
    check("⑤ 新口径字段 geom_check 存在且参数对已记录",
          isinstance(new["geom_check"], dict)
          and new["geom_check"]["n_params_checked"] == 3,
          f"n_params_checked={new['geom_check']['n_params_checked']}")

    # ⑥ 合法必过（多类）：**14 类**可回提器件全部 ok
    all_ok = True
    detail = []
    for kind in DEVICE_CLASSES:
        params = dict(CANONICAL_PARAMS[kind])
        rr = _rt(kind, params)
        d = rr["devices"]["d0"]
        tbl_p = [p for p in PARAM_MEASURERS.get(kind, {}) if p in params]
        ok = (rr["violations"] == [] and len(d["ok"]) == len(tbl_p)
              and all(d["ok"].values()))
        all_ok = all_ok and ok
        detail.append(f"{kind}:{'ok' if ok else 'BAD'}")
    check("⑥ 合法必过（14 类）：测量值 == 声明值、零违规",
          all_ok, " ".join(detail))

    # ⑦ 独立重算：smoke 自己从几何算环半径（不调 lvs_geom 的测量器）
    ring_comp = next(c for c in link.ir.components if c.id == "ring0")
    g_ring = device_geom_of(ring_comp, placement, 0.5)
    ring_pts = max((g[3] for g in g_ring if g[0] == "P"), key=len)
    cx = sum(p[0] for p in ring_pts) / len(ring_pts)
    cy = sum(p[1] for p in ring_pts) / len(ring_pts)
    R_indep = sum(math.hypot(p[0] - cx, p[1] - cy)
                  for p in ring_pts) / len(ring_pts)
    R_reported = rep["devices"]["ring0"]["measured"]["R"]
    check("⑦ 独立重算：smoke 自算环半径 == 模块自报值（逐位）",
          R_indep == R_reported and abs(R_indep - 10.0) < 1e-12,
          f"indep={R_indep!r} reported={R_reported!r}")

    # ⑧ 测量独立性（**结构 + 文本双证**）
    # 🔴 不可写成「源码零 'params' 引用」—— `measure_device_params`
    #    **函数名自身**含 'params' ⇒ 该断言对唯一合法路径**恒假红**
    #    （不可满足；同型血案见 U8/U10：守卫键名扫描须豁免自身必需字段名）。
    #    正解 = ① 签名结构证明收不到声明 ② 文本证明不读声明字段。
    # 职责边界：⑧ 只查**表里实际用到**的测量器（`_meas_fns`）；
    #    「清单 vs 表」的一致性由 ⑬ 专管 —— 否则清单里混入孤儿名时
    #    ⑧ 会 `getattr` 崩溃（崩溃掩盖了本该给出的亮红诊断）。
    _meas_fns = [fn for t in PARAM_MEASURERS.values() for fn in t.values()]
    sig_main = list(inspect.signature(measure_device_params).parameters)
    sig_ok = (sig_main == ["kind", "geoms"]) and all(
        list(inspect.signature(fn).parameters) == ["geoms"]
        for fn in _meas_fns)
    src_parts = []
    for fn in _meas_fns:
        try:
            src_parts.append(inspect.getsource(fn))
        except OSError:                     # 动态构造函数无源码 ⇒ 不参与文本判据
            src_parts.append("")
    src = "".join(src_parts)
    decl_tokens = (".params", "declared", "link")
    hits = [t for t in decl_tokens if t in src]
    check("⑧ 测量独立性：签名只收 geoms/kind 且源码零声明字段引用",
          sig_ok and not hits,
          f"sig_main={sig_main} sig_ok={sig_ok} decl_hits={hits}")

    # ⑨ 不误报：几何不可生成的 kind（不在 DEVICE_CLASSES 的未知 kind）
    #    🔴 v0.9.141 起 14 类**全部**有几何 ⇒ 反例必须换成真未知 kind，
    #    否则该判据恒真（旧版用 MZI 作反例，补几何后会自动变成假绿）。
    lm2 = LinkModel(name="g4_unknown")
    lm2.add_device("zz0", "NoSuchKindZZZ", {"L": 20.0})
    lm2.add_device("wg0", "Waveguide", {"length": 10.0})
    pl2 = {"zz0": (0.0, 0.0, 0.0), "wg0": (50.0, 0.0, 0.0)}
    r9 = extract_layout_params(lm2, pl2)
    check("⑨ 不误报：未知 kind 无几何 → geom_failed 有它、违规为零",
          "zz0" in r9["geom_failed"] and r9["violations"] == []
          and r9["n_params_checked"] == 1,
          f"failed={list(r9['geom_failed'])} viol={len(r9['violations'])}"
          f" checked={r9['n_params_checked']}")
    check("⑨ 回退防线：GEOM_UNSUPPORTED_KINDS 已清空（14 类全部有几何）",
          GEOM_UNSUPPORTED_KINDS == (),
          f"{GEOM_UNSUPPORTED_KINDS}")

    # ⑩ 诚实性：不可回提参数逐条登记**类别 + 原因**（来自 PARAM_TAXONOMY）
    #    🔴 必须**显式声明非几何量**（Q/kappa）才能测到这条 —— 只用规范声明
    #    （R/gap/wg_width 全是几何量）时 unrec 恒空、coverage_declared 恒 1.0
    #    ⇒ 该判据会退化成恒真（判据自身也要有反例，见铁律 8）。
    r10 = _rt("RingResonator", {"R": 10.0, "gap": 0.3, "wg_width": 0.5,
                                "Q": 1.0e4, "kappa": 0.05})
    unrec = {(k, p): r for k, p, r in r10["unrecoverable"]}
    check("⑩ 不可回提参数逐条登记（类别 + 原因），且不计入通过",
          all(("[not_encoded]" in r or "[encoded_not_recovered]" in r)
              for r in unrec.values())
          and r10["n_params_checked"] == 3
          and ("RingResonator", "Q") in unrec,
          f"unrec={sorted(unrec)} checked={r10['n_params_checked']}")
    check("⑩ 零未分类参数（新声明参数必须进分类表，防静默漏登记）",
          r10["n_unclassified"] == 0
          and r10["unrecoverable_by_class"].get(
              CLASS_UNCLASSIFIED, 0) == 0,
          f"by_class={r10['unrecoverable_by_class']}")
    check("⑩ 覆盖率诚实：coverage_geometric == 1 而 coverage_declared < 1",
          r10["coverage_geometric"] == 1.0
          and r10["coverage_declared"] < 1.0,
          f"geom={r10['coverage_geometric']} "
          f"decl={r10['coverage_declared']:.4f} "
          f"n_geom={r10['n_params_geometric']}/{r10['n_params_declared']}")

    # ⑪ 既有零影响：S9 五案例（不启用几何回提）判决与既有口径一致
    same = True
    rows = []
    for case in ("consistent", "open", "misconnect", "short", "dangling"):
        lk, pl, rt = build_lvs_case(case)
        rr = run_lvs(lk, pl, rt)
        v = 1.0 if rr["verdict"] == "ACCEPT" else 0.0
        same = same and (v == s9_lvs_verdict(case)) and rr.get("geom_check") is None
        rows.append(f"{case}={rr['verdict']}")
    check("⑪ 既有零影响：S9 五案例不启用回提时判决与既有口径一致",
          same, " ".join(rows))

    # ⑫ 多层入口共用同一助手（同样支持几何回检）
    from lda_harness.lvs_anchor import build_multilayer_case
    from lda_l2.layers import get_stack
    from lda_l2.lvs import run_lvs_multilayer
    mlk, mpl, mrt = build_multilayer_case("consistent")
    mr = run_lvs_multilayer(mlk, mpl, mrt, stack=get_stack("soi"),
                            with_geom_check=True)
    check("⑫ 多层入口：run_lvs_multilayer 支持几何回提（字段存在）",
          isinstance(mr.get("geom_check"), dict)
          and mr["geom_check"]["n_params_checked"] >= 1,
          f"params={mr.get('geom_check', {}).get('n_params_checked')}"
          f" verdict={mr['verdict']}")

    # ⑬ 表/清单一致性：测量器可调用 + 与 MEASURER_NAMES **双向**一致
    #    （单向只查「表里的都在清单」会漏「清单里有孤儿」）
    ok_tbl = all(callable(fn) for fn in _meas_fns)
    used = {fn.__name__ for fn in _meas_fns}
    listed = set(MEASURER_NAMES)
    n_pairs = sum(len(v) for v in PARAM_MEASURERS.values())
    # 🔴 v0.9.191：原为**写死计数** `== 14 / == 44` ⇒ 器件类合法新增（PCMCell）
    #    会把「增长」误判为「破坏」（同族于 v0.9.183 修过的 qchip C4）。改成
    #    「与真源等长（PARAM_MEASURERS ↔ DEVICE_CLASSES）+ 棘轮地板 = 当前实测值」
    #    —— 允许合法新增，但**删类/删参数**仍必红。
    check(f"⑬ PARAM_MEASURERS 测量器可调用（{len(PARAM_MEASURERS)} 类 / "
          f"{n_pairs} 参数 ≥ 15/48 · 类数与 DEVICE_CLASSES 等长）",
          ok_tbl and len(PARAM_MEASURERS) == len(DEVICE_CLASSES)
          and n_pairs >= 48,
          f"kinds={len(PARAM_MEASURERS)} params={n_pairs}")
    check("⑬ MEASURER_NAMES 与 PARAM_MEASURERS **双向**一致（无漏登记/孤儿）",
          used == listed, f"仅表={sorted(used - listed)} "
          f"仅清单={sorted(listed - used)}")

    # ⑭ 红线：lvs_geom.py 源码零 LLM 引用
    from lda_l2 import lvs_geom as _lg
    src_all = inspect.getsource(_lg)
    llm_hits = [k for k in ("openai", "anthropic", "ollama", "transformers",
                            "requests.post") if k in src_all]
    check("⑭ 红线：lvs_geom.py 源码零 LLM 引用（判决全死标量）",
          not llm_hits, f"hits={llm_hits}")

    # ⑮ 类覆盖（M4 口径）：14/14，且与 link_model 认识的器件类**对表**
    cc = class_coverage()
    expect_classes = set(_DEFAULT_PORTS) | {"RingAddDrop", "MMIC"}
    # 🔴 v0.9.191：同 ⑬ —— 写死 `== 14` 改为「与真源等长 + 棘轮地板 15」
    #    （新增器件类合法；删类仍红）。
    check("⑮ 类覆盖（M4）：全类器件「几何可生成 + 可回提 + 参数已分类」· ≥15 类",
          cc["n_ok"] == cc["n_classes"] == len(DEVICE_CLASSES)
          and cc["n_classes"] >= 15 and cc["class_coverage"] == 1.0
          and cc["missing"] == [],
          f"{cc['n_ok']}/{cc['n_classes']} missing={cc['missing']}")
    check("⑮ DEVICE_CLASSES == link_model._DEFAULT_PORTS ∪ {RingAddDrop, MMIC}",
          set(DEVICE_CLASSES) == expect_classes,
          f"仅本表={sorted(set(DEVICE_CLASSES) - expect_classes)} "
          f"仅链路={sorted(expect_classes - set(DEVICE_CLASSES))}")

    # ⑯ 往返（14 类 × 全参数）：每类规范声明逐参数 |delta| < 1e-9
    bad_rt = []
    n_pairs_rt = 0
    for kind in DEVICE_CLASSES:
        rr = _rt(kind, dict(CANONICAL_PARAMS[kind]))
        d = rr["devices"]["d0"]
        for p in sorted(PARAM_MEASURERS.get(kind, {})):
            if p not in CANONICAL_PARAMS[kind]:
                continue
            n_pairs_rt += 1
            if p not in d["deltas"] or abs(d["deltas"][p]) > 1e-9:
                bad_rt.append(f"{kind}.{p}={d['measured'].get(p)}")
    check(f"⑯ 往返：14 类 / {n_pairs_rt} 参数测量值 == 声明值（|delta|<1e-9）",
          not bad_rt, f"不吻合={bad_rt}")

    # ⑰ 参数分类机器复核：几何敏感性 ↔ 类别三档一致 + 零未分类
    tax_bad = []
    unclassified_hits = []
    n_tax = 0
    for kind in DEVICE_CLASSES:
        base = dict(CANONICAL_PARAMS[kind])
        for p, v in sorted(base.items()):
            klass, _why = classify_param(kind, p)
            n_tax += 1
            if klass == CLASS_UNCLASSIFIED:
                unclassified_hits.append(f"{kind}.{p}")
                continue
            sensitive = _geom_fp(kind, base) != _geom_fp(
                kind, {**base, p: _mutate(v)})
            if klass == "geometric" and not sensitive:
                tax_bad.append(f"{kind}.{p} 标 geometric 但几何不随声明变")
            if klass == "not_encoded" and sensitive:
                tax_bad.append(f"{kind}.{p} 标 not_encoded 但几何随声明变")
            if klass == "encoded_not_recovered" and not sensitive:
                tax_bad.append(
                    f"{kind}.{p} 标 encoded_not_recovered 但几何不变"
                    "（应改为 not_encoded）")
            if klass == "encoded_not_recovered" and p in PARAM_MEASURERS.get(
                    kind, {}):
                tax_bad.append(f"{kind}.{p} 标不可回提却在回提表内")
    check(f"⑰ 分类表机器复核：几何敏感性 ↔ 类别一致（{n_tax} 个规范参数）",
          not tax_bad, f"矛盾={tax_bad}")
    check("⑰ 规范参数零未分类（分类表覆盖全部规范声明）",
          not unclassified_hits, f"未分类={unclassified_hits}")
    factory_miss = []
    for mod, fname in (("photon", "RingResonator"), ("photon", "Waveguide"),
                       ("photon", "GratingCoupler"), ("photon", "Splitter"),
                       ("photon", "DirectionalCoupler"),
                       ("photon", "SymmetricYBranch"),
                       ("photon", "BraggMirror"), ("photon", "RingAddDrop")):
        fac = getattr(__import__(f"lda_ir.{mod}", fromlist=[fname]), fname)
        for p in fac().params:
            if classify_param(fname, p)[0] == CLASS_UNCLASSIFIED:
                factory_miss.append(f"{fname}.{p}")
    check("⑰ 工厂（lda_ir.photon）默认声明参数零未分类",
          not factory_miss, f"未分类={factory_miss}")

    # ⑱ 逐类反向证据（表驱动）：geometric ⇒ 必报且 measured == 改后值；
    #    encoded_not_recovered ⇒ 几何变而**零违规**（不越界假报）。
    #    not_encoded 不在此列（几何不变 ⇒ 该场景是空操作，已由 ⑰ 覆盖）。
    rev_bad = []
    n_rev = 0
    for kind in DEVICE_CLASSES:
        base = dict(CANONICAL_PARAMS[kind])
        for p, v in sorted(base.items()):
            klass, _why = classify_param(kind, p)
            if klass not in ("geometric", "encoded_not_recovered"):
                continue
            n_rev += 1
            new_val = _mutate(v)
            lm = LinkModel(name=f"rev_{kind}")
            lm.add_device("d0", kind, base)          # 声明**不动**
            rr = extract_layout_params(
                lm, {"d0": (0.0, 0.0, 0.0)},
                geom_of=_geom_of_with(kind, {**base, p: new_val}))
            vs = rr["violations"]
            if klass == "geometric":
                ok = (len(vs) == 1 and vs[0]["param"] == p
                      and abs(vs[0]["measured"] - new_val) < 1e-9)
                if not ok:
                    rev_bad.append(f"{kind}.{p}: viol={vs}")
            elif vs:
                rev_bad.append(f"{kind}.{p}: 越界假报 {vs}")
    check(f"⑱ 逐类反向证据（{n_rev} 组）：geometric 必报、越界类零假报",
          not rev_bad, f"异常={rev_bad}")

    # ⑲ 具名构造路径扫描：`lda/**` 内**零具名 add_device 调用**的器件类，
    #    必须**恰好**等于 `NO_NAMED_ADD_DEVICE`（双向）—— 把「这些类的回提
    #    能力目前由本门禁演示、尚无流水线使用」变成机器事实；一旦有人接线，
    #    本判据转红，逼着更新登记表（防"过时说明长期误导"）。
    import re as _re
    _pats = (
        _re.compile(r'add_device\(\s*[^,()]*,\s*["\']([A-Za-z_][A-Za-z_0-9]*)["\']'),
        _re.compile(r'add_device\([^)]*\bkind\s*=\s*["\']([A-Za-z_][A-Za-z_0-9]*)["\']'),
    )
    _constructed: set = set()
    _lda_root = os.path.dirname(os.path.abspath(__file__))
    for _r, _dirs, _fs in os.walk(_lda_root):
        for _f in _fs:
            if not _f.endswith(".py"):
                continue
            with open(os.path.join(_r, _f), encoding="utf-8",
                      errors="ignore") as _fh:
                _txt = _fh.read()
            for _p in _pats:
                _constructed.update(_p.findall(_txt))
    _unnamed = set(DEVICE_CLASSES) - _constructed
    check("⑲ 具名构造路径扫描：零具名 add_device 的类 == NO_NAMED_ADD_DEVICE",
          _unnamed == set(NO_NAMED_ADD_DEVICE),
          f"扫描得={sorted(_unnamed)} 登记={sorted(NO_NAMED_ADD_DEVICE)}")

    # ⑳ 几何 ↔ 端口锚点表同源：每类器件**全部**端口锚点必须落在其版图 bbox 内
    #    （防「画的几何」与「布线/LVS 用的端口表」两处各写一套、悄悄错位 ——
    #     PhaseShifter 就是实例：基元几何居中、端口表左端对齐，必须显式对齐）。
    from lda_layout.placement import port_anchor
    bad_port = []
    n_port = 0
    for kind in DEVICE_CLASSES:
        params = dict(CANONICAL_PARAMS[kind])
        lm = LinkModel(name=f"pa_{kind}")
        lm.add_device("d0", kind, params)
        comp = lm.ir.components[0]
        g = device_geom_of(comp, {"d0": (0.0, 0.0, 0.0)}, 0.5)
        xs = [p[0] for gg in g for p in gg[3]]
        ys = [p[1] for gg in g for p in gg[3]]
        for port in comp.ports:
            dx, dy = port_anchor(kind, port.name, params)
            n_port += 1
            inside = (min(xs) - 1e-9 <= dx <= max(xs) + 1e-9
                      and min(ys) - 1e-9 <= dy <= max(ys) + 1e-9)
            if not inside:
                bad_port.append(f"{kind}.{port.name}=({dx},{dy})")
    check(f"⑳ 几何 ↔ 端口锚点同源：{n_port} 个端口锚点全落在版图 bbox 内",
          not bad_port, f"越界={bad_port}")

    print(f"\nG4 几何回提 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
