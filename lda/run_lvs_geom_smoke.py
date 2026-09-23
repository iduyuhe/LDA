"""v0.9.128 G4 · LVS 器件参数几何回提 smoke（版图↔原理图**尺寸**一致性）。

验证 `lda_l2.lvs_geom` + `lvs.run_lvs(with_geom_check=True)`：
  1. 合法必过：一致版图 → 零违规、测量值 == 声明值（机器精度）
  2. 反向护栏（**两反例**）：篡改**几何**（改波导长度 / 改环半径）→
     `device_param_mismatch` 必报，measured == 篡改值
  3. 判据升级实证：同一篡改版图，`with_geom_check=False` → ACCEPT（旧口径
     **漏检**）/ `=True` → REJECT ⇒ 新判据**实质有效**，不是恒真自证
  4. 合法必过（多类）：7 类可回提器件全部 `ok`
  5. 独立重算：smoke 自己从几何算环半径，与模块自报值逐位一致
  6. 测量独立性：测量器源码**不读 params**（只读几何）
  7. 不误报：几何不可生成的 kind（MZI/MMIC/PhaseShifter）→ 登记
     `geom_failed` 且**不报违规**
  8. 诚实性：不可回提参数逐条登记原因；覆盖率口径分「表内 / 声明」两档
  9. 既有零影响：S9 五案例在**不启用**几何回提时判决与既有口径一致
 10. 红线：`lvs_geom.py` 源码零 LLM 引用（判决全死标量）
 11. 多层入口：`run_lvs_multilayer` 与单层共用同一助手（同样支持）

运行：python run_lvs_geom_smoke.py
"""
from __future__ import annotations

import inspect
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_chain.link_model import LinkModel
from lda_harness.lvs_anchor import build_lvs_case, s9_lvs_verdict
from lda_harness.smoke_kit import make_check
from lda_l2.chip_layout_export import device_geom_of
from lda_l2.lvs import run_lvs
from lda_l2.lvs_geom import (MEASURER_NAMES, PARAM_MEASURERS,
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


def _tamper_dc(c, placement, wg_width, Lc_new: float = 25.0):
    g = device_geom_of(c, placement, wg_width)
    return _set_path_span(g, Lc_new) if c.kind == "DirectionalCoupler" else g


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
    check("① 覆盖率两档口径均 =1.0（本 case 全参数可回提）",
          rep["coverage_by_table"] == 1.0 and rep["coverage_declared"] == 1.0,
          f"table={rep['coverage_by_table']} decl={rep['coverage_declared']}")

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

    # ⑥ 合法必过（多类）：7 类可回提器件全部 ok
    multi = [
        ("Waveguide", {"length": 12.0}),
        ("GratingCoupler", {"L": 10.0}),
        ("DirectionalCoupler", {"Lc": 10.0}),
        ("RingResonator", {"R": 10.0}),
        ("RingAddDrop", {"R": 10.0}),
        ("MMI", {"L_mmi": 20.0}),
        ("SymmetricYBranch", {"arm_length": 5.0}),
    ]
    all_ok = True
    detail = []
    for kind, params in multi:
        lm = LinkModel(name=f"g4_{kind}")
        lm.add_device("d0", kind, params)
        rr = extract_layout_params(lm, {"d0": (0.0, 0.0, 0.0)})
        d = rr["devices"]["d0"]
        ok = (rr["violations"] == [] and all(d["ok"].values())
              and len(d["ok"]) == 1)
        all_ok = all_ok and ok
        detail.append(f"{kind}:{'ok' if ok else 'BAD'}")
    check("⑥ 合法必过（多类）：7 类器件测量值 == 声明值",
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

    # ⑨ 不误报：几何不可生成的 kind → 登记 geom_failed 且零违规
    lm2 = LinkModel(name="g4_unsupported")
    lm2.add_device("mzi0", "MZI", {"Lu": 20.0, "dy": 4.0})
    lm2.add_device("wg0", "Waveguide", {"length": 10.0})
    pl2 = {"mzi0": (0.0, 0.0, 0.0), "wg0": (50.0, 0.0, 0.0)}
    r9 = extract_layout_params(lm2, pl2)
    check("⑨ 不误报：MZI 无几何 → geom_failed 有它、违规为零",
          "mzi0" in r9["geom_failed"] and r9["violations"] == []
          and r9["n_params_checked"] == 1,
          f"failed={list(r9['geom_failed'])} viol={len(r9['violations'])}"
          f" checked={r9['n_params_checked']}")

    # ⑩ 诚实性：不可回提参数逐条登记原因
    lm3 = LinkModel(name="g4_unrec")
    lm3.add_device("r0", "RingResonator", {"R": 10.0, "gap": 0.3,
                                           "wg_width": 0.5})
    r10 = extract_layout_params(lm3, {"r0": (0.0, 0.0, 0.0)})
    unrec = {(k, p) for k, p, _r in r10["unrecoverable"]}
    check("⑩ 不可回提参数逐条登记（含原因），且不计入通过",
          ("RingResonator", "gap") in unrec
          and ("RingResonator", "wg_width") in unrec
          and r10["n_params_checked"] == 1
          and all(_r for _k, _p, _r in r10["unrecoverable"]),
          f"unrec={sorted(unrec)} checked={r10['n_params_checked']}")
    check("⑩ 覆盖率诚实：coverage_declared < 1（3 声明仅 1 可回提）",
          abs(r10["coverage_declared"] - 1.0 / 3.0) < 1e-12
          and r10["coverage_by_table"] == 1.0,
          f"table={r10['coverage_by_table']} decl={r10['coverage_declared']:.4f}")

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
    check("⑬ PARAM_MEASURERS 测量器可调用（7 类 / 7 参数）",
          ok_tbl and len(PARAM_MEASURERS) == 7
          and sum(len(v) for v in PARAM_MEASURERS.values()) == 7,
          f"kinds={len(PARAM_MEASURERS)} "
          f"params={sum(len(v) for v in PARAM_MEASURERS.values())}")
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

    print(f"\nG4 几何回提 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
