# -*- coding: utf-8 -*-
"""S7 门禁：**B4 对拍框架**（逐项差异表 + 归因 + 可复现）。

═══════════════════════════════════════════════════════════════════════════════
这一版要证明什么
───────────────────────────────────────────────────────────────────────────────
`dxcheck.py` 是「对拍」的**表结构**落地。对拍最容易变成表演的三件事，本门禁逐条钉死：

  X0–X1 **表**：首个对拍对象（ISCAS c17）产出 3 行（面积 / 线长 / WNS），
        **绝对量级锚**（面积 0.88 µm²、线长 0.45 µm）—— 不是比值判据。
  X2–X4 **可复现**：同输入 ⇒ 同结果。同一进程两次 + **跨进程 × 两个
        PYTHONHASHSEED** 三种口径的 digest 必须一致；换输入 digest 必变（有区分度）。
  X5–X6 **golden 角色**：面积 = 闭式 Σ 单元面积（`CLOSED_FORM_GEOMETRY`）；
        线长 = 闭式中心矩（`SAME_DEFINITION_SELF_CHECK`）—— 且 `independent=False`
        **诚实地**标明「同定义自检，不是外部独立性」。
  X7–X9 **P5 归因**：每行 `attribution` 非空 + 在**闭式词表**内；写「参考工具如此」
        或自造码 ⇒ 必红（判决权不得交给参考工具）。
  X10–X11 **参考缺席只降级**：`status=unavailable` + `SELF_CONSISTENCY_ONLY`；
        冒称 `EXTERNAL_CROSSCHECK` ⇒ 必红。
  X12–X13 **三态纪律**：无基线 ⇒ `exceeds` 必须是 `null`（不是 `false`）；
        压扁成 `false` ⇒ 必红。WNS 用 target 判：30 ps ⇒ 不超界、20 ps ⇒ 超界且
        归因切到 `TIMING_TARGET_VIOLATED`。
  X14 **P1 角色位**：`golden.role` 写外部工具名 ⇒ 必红（与隔离门 P1 同一口径）。
  X15–X17 **P3 只读文本**：解析器只吃文本（合成样本，非实测语料）；AST 证明
        `dxcheck` 不 import 任何外部工具包；工具缺席时通道降级为 `unavailable`。
  X18 **WNS 语义**：`wns == target − t_clk_min`（逐值），t_clk_min 落在 (0, 1000) ps。
  X19 **fail-closed**：空表 / 未知归因码 ⇒ 抛 `CrossCheckError`。
  X20 **诚实披露**：`claimable=False`。
  X22–X24 **对外可见**：差异表进 `/api/digital_demo` 卡片（此前 `dxcheck` **只有自己的
        门禁在调它**）—— 卡片逐行 6 字段 + digest 必须 == 门禁**独立重跑**的真值；
        三态对外**不压扁**；反向两向必红（把 `null` 改成 `false` / 参考没跑却报
        `EXTERNAL_CROSSCHECK`）。

诚实边界
────────
· **参考工具缺席**（本机 PATH 无 openroad/opensta）⇒ 本门禁证明的是**框架**与
  **同定义自检**，**不**证明与 OpenROAD/OpenSTA 一致；`evidence_level` 已逐行标明。
· 面积/线长 golden 与平台实现**同定义**（`independent=False`），真正的独立性只能
  来自外部工具实测。
· 合成样本文本仅用于验证「文本解析」通道，**不作为实测语料**引用。
· 不做 P&R、不做 STA 本身；C 级自主（纯标准库），LLM 不进判决路径。
"""
from __future__ import annotations

import ast
import copy
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.smoke_kit import make_check  # noqa: E402

from lda_l2.ecore import dsta as DST                          # noqa: E402
from lda_l2.ecore import dverilog as V                        # noqa: E402
from lda_l2.ecore import dxcheck as X                         # noqa: E402

_FALS: list = []
check = make_check(globals(), ok_key="PASS", bad_key="FAIL", indent="",
                   record=_FALS)
T0 = time.time()
AN_ELAPSED_MAX_S = 30.0

_HERE = os.path.dirname(os.path.abspath(__file__))
_DXC = os.path.join(_HERE, "lda_l2", "ecore", "dxcheck.py")

#: P3：任何外部参考工具的**包名**（顶层 import 名）——出现在 dxcheck 就判红。
_BANNED_PKGS = ("openroad", "opensta", "odb", "sax", "yosys", "nextpnr", "gdstk",
                "gdsfactory", "meep", "tidy3d", "klayout", "devsim", "mpb", "nazca")


def _c17():
    return X.xcheck(V.parse(V.SAMPLE_VERILOG), subject="c17")


def _row(table, metric):
    return next(r for r in table["rows"] if r["metric"] == metric)


def _mutate(table, metric, **changes):
    """造一个变异体并返回 `(变异体, validate 问题列表)` —— 反向探针用。"""
    t = copy.deepcopy(table)
    r = next(x for x in t["rows"] if x["metric"] == metric)
    for k, v in changes.items():
        if k == "attribution_detail":
            r["attribution"]["detail"] = v
        elif k == "attribution_code":
            r["attribution"]["code"] = v
        elif k == "golden_role":
            r["golden"]["role"] = v
        else:
            r[k] = v
    return t, X.validate_table(t)


def main() -> int:
    t = _c17()

    # ── X0 表构建 ───────────────────────────────────────────────────────
    check("X0 c17 差异表：3 行 · schema=lda.b4_diff_table/1 · metric 升序",
          [r["metric"] for r in t["rows"]] == ["area_um2", "hpwl_um", "wns_ps"]
          and t["schema"] == "lda.b4_diff_table/1",
          "metrics=%r" % [r["metric"] for r in t["rows"]])

    # ── X1 绝对量级锚（比值判据抓不住量级错 ⇒ 必须给绝对值）────────────
    area = _row(t, "area_um2")["lda"]["value"]
    hpwl = _row(t, "hpwl_um")["lda"]["value"]
    check("X1 绝对量级锚：area=%.6f um^2 · hpwl=%.6f um" % (area, hpwl),
          abs(area - 0.88) < 1e-12 and abs(hpwl - 0.45) < 1e-12,
          "area=%r hpwl=%r" % (area, hpwl))

    # ── X2 可复现：同进程两次 ───────────────────────────────────────────
    t2 = _c17()
    check("X2 可复现（同进程两次）：serialize 相等 ∧ digest 相等（%s）"
          % X.digest(t)[:12],
          X.serialize(t) == X.serialize(t2) and X.digest(t) == X.digest(t2))

    # ── X3 可复现：跨进程 × 两个 PYTHONHASHSEED ─────────────────────────
    code = ("import sys;sys.path.insert(0,%r);"
            "from lda_l2.ecore import dxcheck as X, dverilog as V;"
            "print(X.digest(X.xcheck(V.parse(V.SAMPLE_VERILOG),subject='c17')))"
            % _HERE)
    digs = []
    for seed in ("0", "12345"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        try:
            p = subprocess.run([sys.executable, "-c", code], cwd=_HERE,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env, timeout=120)
            digs.append((p.stdout or "").strip())
        except (OSError, subprocess.SubprocessError) as ex:      # noqa: BLE001
            digs.append("ERR:%s" % type(ex).__name__)
    check("X3 可复现（跨进程 × 2 个 hash seed）：三口径 digest 一致（%s）"
          % (digs[0][:12] if digs else "-"),
          len(digs) == 2 and digs[0] == digs[1] == X.digest(t)
          and len(digs[0]) == 64,
          "digests=%r" % (digs,))

    # ── X4 反向：换输入 ⇒ digest 必变（digest 有区分度）────────────────
    tq = X.xcheck(X.sample_seq_netlist(), subject="seq", target_period_ps=20.0)
    check("X4 反向：换输入（时序环 + target=20）⇒ digest 必变",
          X.digest(tq) != X.digest(t))

    # ── X5 面积 golden：同定义闭式 ─────────────────────────────────────
    ra = _row(t, "area_um2")
    check("X5 面积 golden：role=CLOSED_FORM_GEOMETRY ∧ |lda−golden|<1e-12 ∧ independent=False",
          ra["golden"]["role"] == "CLOSED_FORM_GEOMETRY"
          and abs(ra["lda"]["value"] - ra["golden"]["value"]) < 1e-12
          and ra["golden"]["independent"] is False,
          "lda=%r golden=%r" % (ra["lda"]["value"], ra["golden"]["value"]))

    # ── X6 线长 golden：同定义自检（诚实标 independent=False）──────────
    rh = _row(t, "hpwl_um")
    check("X6 线长 golden：role=SAME_DEFINITION_SELF_CHECK ∧ |lda−golden|<1e-12 ∧ 非独立",
          rh["golden"]["role"] == "SAME_DEFINITION_SELF_CHECK"
          and abs(rh["lda"]["value"] - rh["golden"]["value"]) < 1e-12
          and rh["golden"]["independent"] is False,
          "lda=%r golden=%r" % (rh["lda"]["value"], rh["golden"]["value"]))

    # ── X7 P5：每行归因非空且在闭式词表 ───────────────────────────────
    bad7 = [(r["metric"], r["attribution"]["code"])
            for r in t["rows"]
            if r["attribution"]["code"] not in X.ATTRIBUTION_CODES
            or not r["attribution"]["detail"].strip()]
    check("X7 P5 每行归因非空 ∧ 在闭式词表（%d 行 / %d 个码）"
          % (len(t["rows"]), len(X.ATTRIBUTION_CODES)), not bad7, "bad=%r" % (bad7,))

    # ── X8 P5 反向：禁用借口必红 ───────────────────────────────────────
    _, p8 = _mutate(t, "area_um2", attribution_detail="参考工具如此，所以算对")
    check("X8 P5 反向：归因写「参考工具如此」⇒ validate 必报（判决权不得交出）",
          bool(p8), "problems=%r" % (p8,))

    # ── X9 反向：自造归因码必红 ────────────────────────────────────────
    _, p9 = _mutate(t, "area_um2", attribution_code="WHATEVER_I_THINK")
    check("X9 反向：归因码不在词表 ⇒ validate 必报（不可枚举 = 不可机核）",
          bool(p9), "problems=%r" % (p9,))

    # ── X10 参考缺席：只降级，不冒充 ───────────────────────────────────
    check("X10 参考缺席降级：status=unavailable ∧ evidence=SELF_CONSISTENCY_ONLY ∧ meta.reference_available=False",
          ra["reference"]["status"] == "unavailable"
          and ra["evidence_level"] == "SELF_CONSISTENCY_ONLY"
          and t["meta"]["reference_available"] is False,
          "ref=%r evidence=%r" % (ra["reference"], ra["evidence_level"]))

    # ── X11 反向：冒称外部对拍必红 ─────────────────────────────────────
    _, p11 = _mutate(t, "area_um2", evidence_level="EXTERNAL_CROSSCHECK")
    check("X11 反向：参考未实测却标 EXTERNAL_CROSSCHECK ⇒ validate 必报"
          "（同定义自检不得冒称对拍）", bool(p11), "problems=%r" % (p11,))

    # ── X12 三态纪律：测不了 ≠ 通过 ────────────────────────────────────
    rw = _row(t, "wns_ps")
    _, p12 = _mutate(t, "wns_ps", exceeds=False)
    check("X12 三态纪律：c17 WNS exceeds=null（无时钟域）∧ 强写成 False ⇒ validate 必报",
          rw["exceeds"] is None and rw["baseline_used"] == "none" and bool(p12),
          "exceeds=%r problems=%r" % (rw["exceeds"], p12))

    # ── X13 超界翻转：target 判 WNS ────────────────────────────────────
    sq = X.sample_seq_netlist()
    ok13 = _row(X.xcheck(sq, subject="seq", target_period_ps=30.0), "wns_ps")
    bad13 = _row(X.xcheck(sq, subject="seq", target_period_ps=20.0), "wns_ps")
    check("X13 超界翻转：target=30 ⇒ wns=%.6f 未超界；target=20 ⇒ wns=%.6f 超界 ∧ 归因=TIMING_TARGET_VIOLATED"
          % (ok13["lda"]["value"], bad13["lda"]["value"]),
          ok13["exceeds"] is False
          and ok13["attribution"]["code"] == "WITHIN_BAND_NO_CAUSE"
          and bad13["exceeds"] is True
          and bad13["attribution"]["code"] == "TIMING_TARGET_VIOLATED",
          "ok=%r bad=%r" % (ok13, bad13))

    # ── X14 P1 角色位：外部工具名永不入 golden ─────────────────────────
    _, p14 = _mutate(t, "area_um2", golden_role="OpenROAD")
    check("X14 角色纪律（与隔离门 P1 同口径）：golden.role 写外部工具名 ⇒ validate 必报",
          bool(p14), "problems=%r" % (p14,))

    # ── X15 P3 文本解析（合成样本，声明非实测）─────────────────────────
    pa = X.parse_openroad_area_text(X.SYNTHETIC_OPENROAD_AREA_TEXT)
    pw = X.parse_opensta_wns_text(X.SYNTHETIC_OPENSTA_WNS_TEXT)
    check("X15 P3 文本解析：OpenROAD area=%.2f ∧ OpenSTA wns=%.2f ∧ 未知文本⇒None（不猜）"
          % (pa or -1, pw or -1),
          pa is not None and abs(pa - 1234.56) < 1e-9
          and pw is not None and abs(pw + 12.34) < 1e-9
          and X.parse_openroad_area_text("garbage") is None
          and X.parse_opensta_wns_text("") is None,
          "pa=%r pw=%r" % (pa, pw))

    # ── X16 P3 AST：不 import 外部工具包 ───────────────────────────────
    with open(_DXC, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
    hit16 = sorted(m for m in mods if m.lower() in _BANNED_PKGS)
    check("X16 P3 AST：dxcheck 不 import 任何外部工具包（顶层 import 名 %d 个）"
          % len(mods), not hit16, "hit=%r mods=%r" % (hit16, sorted(mods)))

    # ── X17 参考通道降级 ───────────────────────────────────────────────
    ch = X.run_reference_text("__no_such_tool__", ["-version"])
    check("X17 参考通道降级：工具缺席 ⇒ status=unavailable ∧ 不回落到猜值",
          ch["status"] == "unavailable" and ch["text"] is None,
          "chan=%r" % (ch,))

    # ── X18 WNS 语义（逐值，不用比值）─────────────────────────────────
    tclk = DST.sta(sq).t_clk_min_ps
    b18 = _row(X.xcheck(sq, subject="seq", target_period_ps=20.0), "wns_ps")
    check("X18 WNS 语义：wns == target − t_clk_min ∧ t_clk_min=%.6f ps ∈ (0,1000)"
          % (tclk or -1),
          tclk is not None and 0.0 < tclk < 1000.0
          and abs(b18["lda"]["value"] - (20.0 - tclk)) < 1e-6,
          "wns=%r" % (b18["lda"]["value"],))

    # ── X19 fail-closed ────────────────────────────────────────────────
    empty_raised = False
    code_raised = False
    try:
        X.build_diff_table("s", [])
    except X.CrossCheckError:
        empty_raised = True
    try:
        X._row("m", "u", 1.0, "src",
               reference={"tool": "OpenROAD", "status": "unavailable",
                          "value": None, "probe": ""},
               golden=None, baseline_used="none", band=X.Band(),
               attribution=("NOT_IN_VOCAB", "x"))
    except X.CrossCheckError:
        code_raised = True
    check("X19 fail-closed：空表必抛 ∧ 未知归因码必抛",
          empty_raised and code_raised,
          "empty=%r code=%r" % (empty_raised, code_raised))

    # ── X20 诚实披露 ───────────────────────────────────────────────────
    d = X.DXCHECK_DISCLOSURE
    check("X20 诚实披露：claimable=False ∧ 含 p3/p5/golden/determinism 四条边界",
          d.get("claimable") is False
          and all(k in d for k in ("p3", "p5", "golden", "determinism")),
          "keys=%r" % sorted(d))

    # ── X22–X24 对外可见：差异表进案例卡（B4 不再只有门禁在看）────────────
    #   🔴 补的是真缺口：`dxcheck` 此前**只有自己的门禁在调它**（R3 债务「差异表进只读
    #      facts，让对拍对外可见」）。现在 `/api/digital_demo` 的卡片承载它。
    from lda_webui import digital_case as DC                  # noqa: E402

    DC.clear_cache()
    card = DC.case_card()
    xc = card["xcheck"]

    _tbl2 = X.xcheck(V.parse(V.SAMPLE_VERILOG), subject="c17")
    _rows2 = [{"metric": r["metric"],
               "lda_value": r["lda"]["value"],
               "reference_status": r["reference"]["status"],
               "exceeds": r["exceeds"],
               "evidence_level": r["evidence_level"],
               "attribution_code": r["attribution"]["code"]} for r in _tbl2["rows"]]
    _rows_card = [{k: r[k] for k in ("metric", "lda_value", "reference_status",
                                    "exceeds", "evidence_level", "attribution_code")}
                  for r in xc["rows"]]
    check("X22 卡片差异表 == 独立重跑 dxcheck 的真值（逐行 6 字段 + digest）—— "
          "**不信卡片自述**",
          _rows_card == _rows2 and xc["digest_sha256"] == X.digest(_tbl2)
          and xc["n_rows"] == len(_tbl2["rows"]),
          "卡片=%r 真值=%r" % (_rows_card, _rows2))
    check("X23 三态对外**不压扁**：WNS 行 lda_value=None ⇒ exceeds 必须 None；"
          "参考未实测 ⇒ 每行 evidence_level == SELF_CONSISTENCY_ONLY",
          all((r["exceeds"] is None) if r["lda_value"] is None else True
              for r in xc["rows"])
          and any(r["metric"] == "wns_ps" and r["exceeds"] is None for r in xc["rows"])
          and all(r["evidence_level"] == "SELF_CONSISTENCY_ONLY" for r in xc["rows"]),
          "rows=%r" % ([r["exceeds"] for r in xc["rows"]],))

    # 反向探针：把三态压扁 / 把参考冒充成实测 ⇒ 卡片自检必红
    _flat = copy.deepcopy(card)
    for _r in _flat["xcheck"]["rows"]:
        if _r["exceeds"] is None:
            _r["exceeds"] = False
    _fake = copy.deepcopy(card)
    for _r in _fake["xcheck"]["rows"]:
        _r["reference_status"] = "measured"
        _r["evidence_level"] = "EXTERNAL_CROSSCHECK"
    check("X24 反向两向必红：① 把 WNS 的 None 压扁成 false ⇒ 自检报「压扁」；"
          "② 参考 unavailable 却报 EXTERNAL_CROSSCHECK ⇒ 自检报证据等级不实",
          any("压扁" in p for p in DC.selfcheck(_flat))
          and any("证据等级" in p for p in DC.selfcheck(_fake)),
          "flat=%r fake=%r" % (DC.selfcheck(_flat)[:2], DC.selfcheck(_fake)[:2]))

    # ── X21 自入 CI core ───────────────────────────────────────────────
    with open(os.path.join(_HERE, "run_ci_regression.py"), encoding="utf-8") as fh:
        ck = fh.read()
    check("X21 本门禁已登记进 CORE_SMOKES（防静默漏接）",
          "run_ecore_s7_smoke.py" in ck)

    # ── X0t 耗时红线 ───────────────────────────────────────────────────
    dt = time.time() - T0
    check("X0t 门禁耗时 %.2f s < %.0f s" % (dt, AN_ELAPSED_MAX_S),
          dt < AN_ELAPSED_MAX_S)

    print("")
    if _FALS:
        print("S7 有红色：%s" % ", ".join(_FALS))
        return 1
    print("  [X22–X24] 对外可见：/api/digital_demo 卡片承载差异表（逐行对拍 · 三态不压扁 · 两向可判红）")
    print("S7 全绿 · B4 对拍框架落地：逐项差异表（面积/线长/WNS）+ 闭式归因词表 + "
          "三态纪律 + 跨进程可复现（参考工具缺席时只到同定义自检，不冒充外部对拍）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
