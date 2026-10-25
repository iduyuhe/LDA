#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""光子传感器案例卡 + 客户自助设计向导门禁（WebUI 只读端点 /api/sensor_demo · PS-M7）。

═══ 判什么（分节）═══
A 模块自检（sensor_case.run_selfchecks **13 项**）·
B 关键事实 name-first **+ 🔴 跨源一致性**（面板常量 ≡ `ps_m3` HF 灵敏度 / `ps_m6` 集成 /
  `ps_m2` 噪声模型 / 结果源 report JSON 现算值 —— 漂移即红）·
C 反向可证伪（**突变探针**：破坏 honest_note / verdict 冒充 ACCEPT / 架构表掏空 /
  集成参考漂移 / 噪声模型口径篡改 / 优雅降级失效 ⇒ 均必红）·
D 🔴 **嵌套块反向完备**（每个展示块的叶子键都必须被前端渲染段引用；含**前缀归一化**
  + **假绿复现探针** + **注入探针**）·
E 免登录 / 零重计算（不进 HEAVY_POST_PATHS · 模块无 numpy/scipy/求解器 import）·
F 路由与面板接线（GET_ROUTES 注册 / 面板属性齐 / 三容器齐 / .sec 总数 / div 配平 /
  按钮 id 以 run 开头）+ API 参考已登记 + **优雅降级**（结果源缺失不抛错）·
S 温漂预算「处方可行性」（v0.9.297 · 闭式已知答案 / 两条处方互为倒数替代 /
  🔴 比值不变性探针 / 两条**各自独立**的物理上限对拍 / 绝对量级锚点 / 跨模块同源）·
K 自入 CI core（防静默漏接）。

🔴 本门禁的核心价值：守「内部能力 ↔ 对外载体」**真拉平** —— 面板数字必须 ≡ 底层模块现算，
而不是卡自证自洽；并守案例卡的**诚实边界**（verdict 恒 DESIGN_BUDGET、温漂主导如实披露、
LLM 不进判决路径）。
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def _read(rel):
    fp = os.path.join(_ROOT, rel)
    if not os.path.exists(fp):
        return ""
    with open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 前端渲染段抽取 + 反向完备工具
# ---------------------------------------------------------------------------
def _sensor_sec(idx=None):
    """抽取 sec-sensor 面板片段（从该 .sec 起点到 footer/下一个 .sec 之前）。"""
    if idx is None:
        idx = _read("lda/lda_webui/static/index.html")
    i = idx.find('id="sec-sensor"')
    if i < 0:
        return ""
    start = idx.rfind('<div class="sec"', 0, i)
    if start < 0:
        start = i
    nxt = [x for x in (idx.find('<div class="sec"', i + 10),
                       idx.find('<div class="footer"', i),
                       len(idx)) if x > i]
    return idx[start:min(nxt)]


def _sensor_js():
    """抽取主 <script> 里新增的传感器渲染段（从 _sxF 到 runSensor 绑定行）。"""
    idx = _read("lda/lda_webui/static/index.html")
    i = idx.find("function _sxF")
    j = idx.find("if($('runSensor')) $('runSensor').onclick = runSensor;", i)
    if i < 0 or j < 0:
        return ""
    return idx[i:j + len("if($('runSensor')) $('runSensor').onclick = runSensor;")]


# JS 内建成员（避免把 DTS.map / x.length 当成 JSON 路径引用）
_JS_MEMBERS = {
    "map", "length", "join", "forEach", "filter", "toFixed", "toExponential",
    "push", "slice", "indexOf", "split", "replace", "trim", "value", "options",
    "innerHTML", "textContent", "min", "max", "step", "title", "disabled", "focus",
    "valueOf", "toString", "includes", "then", "catch", "finally", "json", "ok",
    "status", "apply", "call", "bind", "concat", "pop", "shift", "splice", "sort",
    "keys", "values", "entries", "hasOwnProperty", "addEventListener",
}

_DELIM_AFTER = re.compile(r"[^A-Za-z0-9_$]")


def _all_path_lits(js):
    out = set()
    for m in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)", js):
        a, k = m.group(1), m.group(2)
        if k in _JS_MEMBERS:
            continue
        out.add(a + "." + k)
    return out


def _ref_ok(src, lit):
    """路径引用判定：命中处**收尾字符须为非标识符**（防「同前缀长路径」冒充 · 血案 11）。"""
    i = 0
    while True:
        k = src.find(lit, i)
        if k < 0:
            return False
        nxt = src[k + len(lit):k + len(lit) + 1]
        if nxt == "" or _DELIM_AFTER.fullmatch(nxt):
            return True
        i = k + 1


def _block_keys(card, prefix):
    """取 JSON 路径处的键集（列表取首元素；支持 `a.b[]` 点分形式）。

    🔴 前缀按 `.` 切分（**不是逐字符**）—— 逐字符会让 `_block_keys(card, "metrics")`
    在首字符处就返回空集，使「覆盖完备」退化成「空集 ⊆ 任何集合」**恒真**（血案 #32 第二层）。
    """
    parts = prefix.split(".") if isinstance(prefix, str) else list(prefix)
    cur = card
    for part in parts:
        is_list = part.endswith("[]")
        key = part[:-2] if is_list else part
        if not isinstance(cur, dict) or key not in cur:
            return set()
        cur = cur[key]
        if is_list:
            if not isinstance(cur, list) or not cur:
                return set()
            cur = cur[0]
    return set(cur.keys()) if isinstance(cur, dict) else set()


# 展示块 → 前端别名（渲染段里用于该块的变量名）
_BLOCK_ALIAS = {
    "design": ["d.design"],
    "metrics": ["m"],
    "integration": ["g"],
    "signoff": ["s"],
    "wizard.architectures[]": ["a"],
    "wizard.knobs[]": ["k"],
    "milestones[]": ["x"],
    "gaps[]": ["x"],
    # v0.9.291 · CMR 来源闭式（三档 + 反解 + 可达性）必须被前端渲染 ——
    # 🔴 加块的动机不是「多一个表」，而是**新增展示字段必须被消费**：
    #   本门禁 D5 探针实测「往块里注入假字段 ⇒ 缺字段集合恰为该假键」，
    #   故任何只加后端不加前端的字段都会被 D3 当场判红。
    "referencing": ["rf"],
}
# 纯元数据键（不是展示字段 ⇒ 不纳入反向完备）
_META_KEYS = {"endpoint"}


def _missing_in_block(card, block, js):
    keys = {k for k in _block_keys(card, block) if k not in _META_KEYS}
    miss = set()
    for k in keys:
        if not any(_ref_ok(js, a + "." + k) for a in _BLOCK_ALIAS[block]):
            miss.add(k)
    return miss


def main() -> int:
    from lda_webui import sensor_case as SC

    # ══════════════════════ A 模块自检 ══════════════════════
    ok_a = SC.run_selfchecks(verbose=False)
    check("A1 模块自检 13/13 PASS（零框架 import / verdict 非 PASS·ACCEPT / 诚实边界齐备 / "
          "架构表良构 / 集成参考非空 / 卡可用 / 指标 sane / FSR∝1/R / LOD_intrinsic∝1/Q / "
          "Δλ 符号随 Δn / 零参数红标 / 温漂主导如实 / 优雅降级）", ok_a)

    # ══════════════════════ B 关键事实 + 跨源一致性 ══════════════════════
    card = SC.case_card(repo_root="__nonexistent_root__")
    check("B1 endpoint == /api/sensor_demo", card["endpoint"] == "/api/sensor_demo")
    check("B2 verdict == DESIGN_BUDGET（非 ACCEPT/PASS）",
          card["verdict"] == "DESIGN_BUDGET")
    check("B3 六段征程（PS-M0/M2/M3/M4/M5/M6）· 门禁全登记",
          [m["id"] for m in card["milestones"]]
          == ["PS-M0", "PS-M2", "PS-M3", "PS-M4", "PS-M5", "PS-M6"]
          and all(m["gate"].startswith("run_ps_") for m in card["milestones"]))
    check("B4 向导五步 + 两架构 + 三旋钮",
          len(card["wizard"]["steps"]) == 5
          and len(card["wizard"]["architectures"]) == 2
          and len(card["wizard"]["knobs"]) == 3)
    check("B5 诚实边界 5 条（温漂处方已判死 / 温漂参考通道仍开放 / 非流片实测 / 设计几何 / referencing）",
          len(card["gaps"]) == 5
          and any(g["id"] == "G_temp_drift" for g in card["gaps"])
          and any(g["id"] == "G_temp_drift_ref" for g in card["gaps"]))
    check("B6 honest_note 含关键限定（设计预算 · 非流片实测签核 · LLM 不进判决路径）",
          all(kw in card["honest_note"]
              for kw in ("设计预算", "非流片实测签核", "LLM 不进判决路径")))
    check("B7 默认点物理合理（S>0 · FSR>0 · LOD_intrinsic>0 · LOD_real 有限）",
          card["metrics"]["S_nm_per_riu"] > 0
          and card["metrics"]["FSR_nm"] > 0
          and card["metrics"]["LOD_intrinsic_riu"] > 0
          and 0 < card["metrics"]["LOD_real_riu"] < 1.0)
    check("B8 温漂主导如实（默认点 LOD_temp ≫ 100×LOD_elec）",
          card["metrics"]["LOD_temp_riu"] > 100.0 * card["metrics"]["LOD_elec_riu"]
          and card["metrics"]["dominant_limit"] == "temp")

    # ---- 🔴 B9–B13 跨源一致性：面板常量 ≡ 平台模块现算（漂移即红·真拉平非自洽）----
    from lda_l2 import ps_m2, ps_m3, ps_m6  # noqa: E402

    w = ps_m3.real_waveguide_sensitivity()
    ox = ps_m3.real_waveguide_sensitivity(ps_m3.SCENARIOS["soi_slab_oxide"]["geo"])
    a0, a1 = SC.ARCHITECTURES[0], SC.ARCHITECTURES[1]
    check("B9 🔴 架构常量 ≡ ps_m3 平板 HF 现算（n_eff/Γ/n_g/S 逐位）",
          abs(a0["S_bulk_nm_per_riu"] - w["S_nm_per_riu"]) < 1e-12
          and abs(a0["n_g"] - w["n_g"]) < 1e-12
          and abs(a0["n_eff"] - w["n_eff"]) < 1e-12
          and abs(a0["gamma_clad"] - w["gamma_clad"]) < 1e-12
          and abs(a1["S_bulk_nm_per_riu"] - ox["S_nm_per_riu"]) < 1e-12
          and abs(a1["n_g"] - ox["n_g"]) < 1e-12)

    r6 = ps_m6.selfcheck_ps_m6()
    _pair = [
        ("crosstalk_db", r6["array"]["crosstalk_db"]),
        ("pitch_min_um", r6["array"]["pitch_min_um"]),
        ("v_n_uV", r6["readout"]["v_n_uV"]),
        ("f_3dB_Hz", r6["readout"]["f_3dB_Hz"]),
        ("align_eta", r6["alignment"]["eta"]),
        ("align_il_db", r6["alignment"]["insertion_loss_db"]),
        ("channel_split_loss_db", r6["integration"]["channel_split_loss_db"]),
        ("total_optical_loss_db", r6["integration"]["total_optical_loss_db"]),
        ("frame_rate_hz", r6["integration"]["frame_rate_hz"]),
        ("area_mm2", r6["integration"]["area_mm2"]),
        ("LOD_readout_riu", r6["integration"]["LOD_readout_riu"]),
    ]
    _worst = max(abs(SC.INTEGRATION_REF[k] - v) for k, v in _pair)
    check("B10 🔴 集成参考 ≡ ps_m6 现算（阵列/读出/对准/预算 11 项逐位）",
          _worst < 1e-12, "max|Δ| = %.3e" % _worst)

    _lod = ps_m2.lod_real(w["S_nm_per_riu"], 1e4, 1.55)
    _mine = SC._lod_real(w["S_nm_per_riu"], 1e4, 1.55)
    _worst2 = max(abs(_mine[k] - _lod[k]) for k in
                  ("LOD_elec_riu", "LOD_temp_riu", "LOD_real_riu", "slope_per_nm",
                   "FWHM_nm", "frac_total"))
    _nz = max(abs(SC.DEFAULT_NOISE[k] - ps_m2.DEFAULT_NOISE[k]) for k in SC.DEFAULT_NOISE)
    check("B11 🔴 噪声模型闭式镜像 ≡ ps_m2.lod_real 现算（LOD 分项 + 斜率 + 默认参数 12 项）",
          _worst2 < 1e-15 and _nz == 0.0,
          "max|Δ|(LOD) = %.3e · max|Δ|(noise) = %.3e" % (_worst2, _nz))

    check("B12 🔴 面板 DEFAULT_NOISE 键集 ≡ ps_m2.DEFAULT_NOISE 键集",
          set(SC.DEFAULT_NOISE) == set(ps_m2.DEFAULT_NOISE))

    # ---- B13 结果源报告 ↔ 面板常量 一致（跨源·非自洽）----
    rp = os.path.join(_ROOT, "examples", "photo_sensor", "lda_ps_sensor_report.json")
    rep = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    _arch_by_id = {a["id"]: a for a in rep.get("architectures", [])}
    _ok13 = (set(_arch_by_id) == {a["id"] for a in SC.ARCHITECTURES}
             and all(abs(_arch_by_id[a["id"]]["S_bulk_nm_per_riu"] - a["S_bulk_nm_per_riu"]) < 1e-12
                     for a in SC.ARCHITECTURES))
    check("B13 🔴 结果源 report ↔ 面板 ARCHITECTURES 一致（id 集 + S 逐位）", _ok13)

    # ---- B14 签核 GDS 字节：报告 ↔ 实测文件 getsize ----
    gds = os.path.join(_ROOT, "examples", "photo_sensor", "lda_ps_sensor_ring.gds")
    _rep_bytes = (rep.get("signoff") or {}).get("gds_bytes")
    _file_bytes = os.path.getsize(gds) if os.path.exists(gds) else None
    check("B14 🔴 签核 GDS 字节：report.gds_bytes ≡ 实测 getsize（防「报告与产物脱钩」）",
          _rep_bytes is not None and _file_bytes is not None and _rep_bytes == _file_bytes,
          "report=%s file=%s" % (_rep_bytes, _file_bytes))

    # ---- B15 签核块可用 + 面板严格模式显示真实值 ----
    c_ok = SC.case_card()
    check("B15 正常根下签核可用（available=True · DRC/LVS 有报告 · gds_file_bytes>0）",
          c_ok["signoff"]["available"] is True
          and c_ok["signoff"]["drc_all_pass"] is True
          and c_ok["signoff"]["lvs_present"] is True
          and c_ok["signoff"]["gds_file_bytes"] > 0)

    # ══════════════════════ C 反向可证伪（突变探针）═══════════════════════
    # C1 破坏 honest_note 关键字 ⇒ A1 必红
    _sn = SC.HONEST_NOTE
    SC.HONEST_NOTE = _sn.replace("非流片实测签核", "")
    ok_c1 = SC.run_selfchecks(verbose=False)
    SC.HONEST_NOTE = _sn
    check("C1 反向：移除「非流片实测签核」⇒ A1 必红", ok_c1 is False)

    # C2 verdict 冒充 ACCEPT ⇒ 不伪装实测判据必红
    _scc = SC.case_card

    def _fake(repo_root=None, **_kw):
        c = _scc(repo_root=repo_root)
        c["verdict"] = "ACCEPT"
        return c

    SC.case_card = _fake
    _fake_card = SC.case_card(repo_root="__nonexistent_root__")
    SC.case_card = _scc
    check("C2 反向：verdict 冒充 ACCEPT ⇒ 不伪装实测判据必红",
          _fake_card["verdict"] not in ("DESIGN_BUDGET", "DESIGN_VERIFIED"))

    # C3 掏空架构表 ⇒ A1 必红
    _sa = list(SC.ARCHITECTURES)
    SC.ARCHITECTURES = []
    ok_c3 = SC.run_selfchecks(verbose=False)
    SC.ARCHITECTURES = _sa
    check("C3 反向：清空 ARCHITECTURES ⇒ A1 必红", ok_c3 is False)

    # C4 集成参考漂移（v_n_uV +1）⇒ B10 必红
    _sv = SC.INTEGRATION_REF["v_n_uV"]
    SC.INTEGRATION_REF["v_n_uV"] = _sv + 1.0
    _r6b = ps_m6.selfcheck_ps_m6()
    _drift = abs(SC.INTEGRATION_REF["v_n_uV"] - _r6b["readout"]["v_n_uV"])
    SC.INTEGRATION_REF["v_n_uV"] = _sv
    check("C4 反向：集成参考漂移（v_n_uV+1）⇒ B10 判据必红", _drift >= 1e-12)

    # C5 噪声模型口径篡改 ⇒ B11 必红
    _sdn = SC.DEFAULT_NOISE["dn_dT"]
    SC.DEFAULT_NOISE["dn_dT"] = _sdn * 2.0
    _m2 = SC._lod_real(w["S_nm_per_riu"], 1e4, 1.55)
    _l2 = ps_m2.lod_real(w["S_nm_per_riu"], 1e4, 1.55)
    SC.DEFAULT_NOISE["dn_dT"] = _sdn
    check("C5 反向：篡改噪声模型（dn_dT×2）⇒ B11 判据必红（温漂项必跟着变）",
          abs(_m2["LOD_temp_riu"] - _l2["LOD_temp_riu"]) > 1e-9)

    # C6 架构 S 漂移 ⇒ B9 必红
    _sS = SC.ARCHITECTURES[0]["S_bulk_nm_per_riu"]
    SC.ARCHITECTURES[0]["S_bulk_nm_per_riu"] = _sS + 0.5
    _ws = ps_m3.real_waveguide_sensitivity()["S_nm_per_riu"]
    _dS = abs(SC.ARCHITECTURES[0]["S_bulk_nm_per_riu"] - _ws)
    SC.ARCHITECTURES[0]["S_bulk_nm_per_riu"] = _sS
    check("C6 反向：架构 S 漂移(+0.5) ⇒ B9 判据必红", _dS > 1e-12)

    # C7 优雅降级失效（把降级分支改成 available=True 谎报）⇒ F4 必红
    _slr = SC._load_report
    SC._load_report = lambda repo_root=None: {"signoff": {"artifact": "x", "gds_bytes": 1,
                                                          "n_elements": 1,
                                                          "drc_all_pass": True,
                                                          "n_drc_checked": 1,
                                                          "lvs_present": True,
                                                          "blocked_nets": 0}}
    # 降级路径被伪造 ⇒ 「错误根下 available 必须为 False」的判据应红
    _bad = SC.case_card(repo_root="__nonexistent_root__")
    SC._load_report = _slr
    check("C7 反向：伪造降级分支（错误根下谎报 available=True）⇒ F4 判据必红",
          _bad["signoff"]["available"] is True)   # 判据侧断言「此处应为 False」见 F4

    # ══════════════════════ D 嵌套块反向完备 ══════════════════════
    js = _sensor_js()
    check("D1 前端渲染段可抽取（function _sxF … runSensor 绑定）",
          bool(js) and "function renderSensor" in js)

    # D2 前缀归一的左集合势先打印（为 0 = 假判据）
    _sizes = {b: len(_block_keys(card, b)) for b in _BLOCK_ALIAS}
    check("D2 🔴 各展示块键集势 > 0（左集合为 0 即假判据 · 血案 #32 第二层）",
          all(v > 0 for v in _sizes.values()), str(_sizes))

    # D3 逐块反向完备：每个展示块叶子键都被前端引用
    _all_missing = {}
    for b in _BLOCK_ALIAS:
        mm = _missing_in_block(card, b, js)
        if mm:
            _all_missing[b] = sorted(mm)
    check("D3 🔴 嵌套块反向完备：全部展示块叶子键均被前端渲染段引用",
          not _all_missing, str(_all_missing))

    # D4 假绿复现探针：逐字复刻「前缀按字符迭代」的修复前实现 ⇒ 必须恒返回空集
    def _block_keys_buggy(card_, prefix):
        cur = card_
        for seg in prefix:          # ← 病根：字符串逐字符
            if not isinstance(cur, dict) or seg not in cur:
                return set()
            cur = cur[seg]
        return set(cur.keys()) if isinstance(cur, dict) else set()

    _buggy_sizes = {b: len(_block_keys_buggy(card, b)) for b in ("metrics", "integration")}
    check("D4 假绿复现探针：修复前实现（`for seg in prefix` 逐字符）对 " "前缀恒返回空集",
          all(v == 0 for v in _buggy_sizes.values()), str(_buggy_sizes))

    # D5 注入探针：往 metrics 注入一个前端未引用的字段 ⇒ 缺字段集合必须恰为该字段名
    _bk = dict(card)
    _bk["metrics"] = dict(card["metrics"], zz_injected_probe_key=1.0)
    _inj = sorted(_missing_in_block(_bk, "metrics", js))
    check("D5 注入探针：往 metrics 注入假字段 ⇒ 缺字段集合恰为该假字段（反向判据非死测试）",
          _inj == ["zz_injected_probe_key"], str(_inj))

    # D6 探针：抹掉前端一处引用（删 m.FSR_nm 引用）⇒ D3 必红
    _js_cut = js.replace("m.FSR_nm", "m.__cut__")
    _miss6 = _missing_in_block(card, "metrics", _js_cut)
    check("D6 反向：抹掉前端对 m.FSR_nm 的引用 ⇒ 反向完备必红（覆盖真被引用）",
          "FSR_nm" in _miss6, str(sorted(_miss6)))

    # D7 短路径前缀冒充探针：只剩「前缀长路径」时短路径必须判为「未引用」
    _probe_src = "obj.abcd_ref"
    check("D7 反向：`obj.abc` 不应被 `obj.abcd_ref` 冒充（非标识符边界判定）",
          _ref_ok(_probe_src, "obj.abcd_ref") and not _ref_ok(_probe_src, "obj.abc"))

    # ══════════════════════ E 免登录 / 零重计算 ══════════════════════
    rt = _read("lda/lda_webui/routes.py")
    heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0] if "HEAVY_POST_PATHS = {" in rt else ""
    check("E1 端点不进 HEAVY_POST_PATHS（公开只读 · 零重计算 · 无 DoS 面）",
          "/api/sensor_demo" not in heavy)
    src_sc = _read("lda/lda_webui/sensor_case.py")
    check("E2 🔴 零重计算：sensor_case 不 import 求解器 / numpy / scipy / 网络",
          all(k not in src_sc.split("def run_selfchecks")[0]
              for k in ("import lda_l2", "from lda_l2", "import numpy", "from numpy",
                        "import scipy", "from scipy", "import requests", "import socket")))
    check("E3 模块顶层只 import json/math/os/typing",
          all(k not in src_sc.split("__all__")[0]
              for k in ("import numpy", "import scipy", "import lda_")))

    # ══════════════════════ F 路由 / 面板接线 + 降级 ══════════════════════
    get_block = rt.split("GET_ROUTES = {")[1].split("}")[0] if "GET_ROUTES = {" in rt else ""
    check("F1 GET 端点接线（\"/api/sensor_demo\": h_sensor_demo, 在 GET_ROUTES）",
          '"/api/sensor_demo": h_sensor_demo,' in get_block)
    check("F2 handler 定义存在（def h_sensor_demo）", "def h_sensor_demo(" in rt)
    idx = _read("lda/lda_webui/static/index.html")
    check("F3 面板三容器齐（sensorSummary / sensorBody / sensorConclusion）",
          all(x in idx for x in ('id="sensorSummary"', 'id="sensorBody"',
                                 'id="sensorConclusion"')))
    check("F4 🔴 优雅降级：错误根下 available=False 且不抛错",
          SC.case_card(repo_root="__nonexistent_root__")["signoff"]["available"] is False)
    check("F5 面板按钮 id 以 run 开头（自动进抽屉「能力目录」）",
          'id="runSensor"' in idx)
    check("F6 面板属性齐（data-stage / data-stack / data-roles / id=sec-sensor）",
          'id="sec-sensor"' in idx and 'data-stage="accept"' in idx)
    # div 配平
    check("F7 div 配平（<div> == </div>）",
          len(re.findall(r"<div\b", idx)) == idx.count("</div>"),
          "%d vs %d" % (len(re.findall(r"<div\b", idx)), idx.count("</div>")))

    # F10 🔴 案例卡面板必须可经 hash **深链**直达（CASE_MAP 覆盖）。
    #   教训：`sec-sensor` 面板初版只登记了容器与按钮，**漏登 CASE_MAP** ⇒ 与当时 8 个
    #   `data-stage="accept"` 同族案例卡（qchip/schip/pchip/d4/oi/pm/accel/ecore）不一致，
    #   客户无法用 `#sec-sensor` 一键直达。「能点到」≠「能深链到」——本判据把它机器化。
    #   🔴 棘轮：族随新增面板（sec-soc → sec-qsensor）只增不减，下限随之 9→10→11。
    _cm = re.search(r"var\s+CASE_MAP\s*=\s*\{(.*?)\}\s*;", idx, re.S)
    _cm_pairs = dict(re.findall(r'"(#sec-[A-Za-z0-9_]+)"\s*:\s*"([A-Za-z0-9_]+)"',
                                _cm.group(1) if _cm else ""))
    _accept_ids = sorted(set(
        [m.group(1) for m in re.finditer(r'data-stage="accept"[^>]*id="(sec-[A-Za-z0-9_]+)"', idx)] +
        [m.group(1) for m in re.finditer(r'id="(sec-[A-Za-z0-9_]+)"[^>]*data-stage="accept"', idx)]))
    _missing = [s for s in _accept_ids if ("#" + s) not in _cm_pairs]
    check("F10 🔴 全部 accept 案例卡均登记 CASE_MAP（hash 深链可达 · 曾漏 sec-sensor）",
          len(_accept_ids) >= 11 and not _missing,
          "accept=%d map=%d missing=%s" % (len(_accept_ids), len(_cm_pairs), _missing))
    check("F10b sec-sensor 映射到 runSensor", _cm_pairs.get("#sec-sensor") == "runSensor",
          "got=%r" % _cm_pairs.get("#sec-sensor"))

    # F10c 🔴 首屏 `#wbCaseBar` 直达条目（**第三种入口面**：抽屉按钮 / hash 深链 /
    #   首屏条）。教训（2026-10-08 用户实测「导航条里没有光传感器」）：面板同时要出现在
    #   **首屏案例条**里，否则用户首屏扫不到、只能靠深链/滚动。E1（entry_smoke）已从
    #   族现算覆盖全部案例卡；此处为**面板自带的上线清单**再钉一次（本地即检）。
    _bar = re.search(r'id="wbCaseBar".{0,12000}?</div>', idx, re.S)
    _bar_hrefs = re.findall(r'href="(#[^"]+)"', _bar.group(0)) if _bar else []
    check("F10c 🔴 sec-sensor 已登记首屏案例条 #wbCaseBar（否则首屏扫不到 · 用户实测缺）",
          "#sec-sensor" in _bar_hrefs, "bar 条目=%s" % (_bar_hrefs or "无"))

    # F9 🔴 面板诚实标注不得被静默抹掉（**限定在 sec-sensor 面板内** —— 全文件搜索会被
    #    其他面板的同名标注满足 ⇒ 探针假绿）
    _sec = _sensor_sec(idx)
    check("F9 面板诚实标注齐备（只读·免登录·零重计算 / DESIGN_BUDGET / LLM 不进判决路径）",
          bool(_sec) and all(kw in _sec for kw in ("只读 · 免登录 · 零重计算", "DESIGN_BUDGET",
                                                   "LLM 不进判决路径")),
          "面板片段长 %d" % len(_sec))

    jp = os.path.join(_ROOT, "docs", "api_reference.json")
    try:
        ref = json.load(open(jp, encoding="utf-8"))
        ep = next((e for e in ref["endpoints"] if e["path"] == "/api/sensor_demo"), None)
        check("F8 API 参考已含 /api/sensor_demo 且 auth=public（gen 已跑 · 防双红）",
              bool(ep) and ep["auth"] == "public" and bool(ep["description"]),
              "found=%s" % (ep is not None))
    except Exception as e:  # pragma: no cover
        check("F8 API 参考已含 /api/sensor_demo", False, "读参考失败: %s" % e)

    # ══════════════════════ R CMR 来源闭式（v0.9.291）══════════════════════
    # 🔴 改前：`CMR` 是**手填常数**（本卡 1.0 / `B472_NOISE` 1e4），两处相差 1e4，
    #   且没有任何一处说明「凭什么能有这么大抑制」——与 v0.9.290 的 IL 同型：
    #   一句论证（「平衡双通道可达」）从未被写成可复算的数。
    #   本节把 CMR 钉在**通道失配**上：CMR = 1/δ，并保留一条「闭式已知答案」的对照支路。
    from lda_webui import sensor_case as SCr
    check("R1 CMR 闭式逐位：δ=1% ⇒ CMR 恰为 100（== 判定，不用 isclose）",
          SCr.cmr_from_mismatch(1e-2) == 100.0, "%r" % (SCr.cmr_from_mismatch(1e-2),))
    check("R2 🔴 对照支路（本应恰好为 1）：δ=1（完全失配）⇒ CMR=1.0 = 零抑制",
          SCr.cmr_from_mismatch(1.0) == 1.0, "%r" % (SCr.cmr_from_mismatch(1.0),))
    _ds = [1.0, 0.5, 0.1, 0.03, 0.01, 1e-4]
    _cs = [SCr.cmr_from_mismatch(d) for d in _ds]
    check("R3 单调性：δ 递减 ⇒ CMR 严格递增（6 点）",
          all(_cs[i] < _cs[i + 1] for i in range(len(_cs) - 1)),
          " ".join("%.3g" % c for c in _cs))
    check("R4 反解往返逐位自洽：mismatch_from_cmr(cmr_from_mismatch(δ)) == δ",
          all(abs(SCr.mismatch_from_cmr(SCr.cmr_from_mismatch(d)) - d) <= 1e-18 for d in _ds))
    _rp = card["referencing"]
    _tiers = {t["tag"]: t for t in _rp["tiers"]}
    check("R5 卡内同源：typical 档 CMR ≡ cmr_from_mismatch(REFERENCING_MISMATCH_TYPICAL)（逐位）",
          _tiers["typical"]["CMR"] == SCr.cmr_from_mismatch(SCr.REFERENCING_MISMATCH_TYPICAL)
          and _tiers["typical"]["mismatch"] == SCr.REFERENCING_MISMATCH_TYPICAL)
    check("R6 解析关系：LOD_temp ∝ 1/CMR（off/typical 的温漂比 == CMR 比，相对 1e-12）",
          abs(_rp["temp_suppression_typical"]
              - _tiers["typical"]["CMR"] / _tiers["off"]["CMR"]) <= 1e-12 * _rp["temp_suppression_typical"],
          "%.6f vs %.6f" % (_rp["temp_suppression_typical"],
                            _tiers["typical"]["CMR"] / _tiers["off"]["CMR"]))
    check("R7 🔴 可达性判定：锚区间(1e-4)比工艺典型(3%)小 300× ⇒ 必须判「非设计可达」∧ note 写明",
          _rp["anchor_mismatch_reachable"] is False
          and _rp["anchor_mismatch_roundtrip"] is True
          and ("不可达" in _rp["note"]))
    _b472 = None
    try:
        from lda_harness._batch_b38_numeric import B472_NOISE
        _b472 = B472_NOISE["CMR"]
    except Exception:
        pass
    check("R8 🔴 跨模块同源：卡上反解失配 ≡ mismatch_from_cmr(B472_NOISE['CMR'])（1e4 ⇒ 1e-4）",
          _b472 is not None and abs(_rp["anchor_implied_mismatch"]
                                    - SCr.mismatch_from_cmr(_b472)) <= 1e-18,
          "B472_NOISE.CMR=%r" % (_b472,))
    # R9 反向探针：① 伪造「幅度平衡可达 80 dB」⇒ R6 必红；② δ=0 不得静默给有限值；
    #    ③ 抹掉 note 里的「不可达」⇒ R7 必红
    _fake = dict(_tiers["typical"], CMR=_b472)
    _r6_red = abs((_fake["CMR"] / _tiers["off"]["CMR"]) - _tiers["typical"]["CMR"]) > 1e-9
    _r2_red = SCr.cmr_from_mismatch(0.0) == float("inf")
    _r7_red = "不可达" not in _rp["note"].replace("不可达", "")
    check("R9 反向探针：伪造典型档=1e4（假装幅度平衡可达）⇒ R6 必红 ∧ δ=0 ⇒ inf 不静默 ∧ 删『不可达』⇒ R7 必红",
          _r6_red and _r2_red and _r7_red,
          "r6=%s r2=%s r7=%s" % (_r6_red, _r2_red, _r7_red))

    # ══════════════════════ S 温漂预算：处方可行性（v0.9.297）══════════════════════
    # 🔴 改前：`G_temp_drift` 只写着「须片载温控 / 参考通道」—— 一句**处方**，
    #    从没人算过它要多稳。本层把它算出来，然后判定：**温控这条处方不可行**。
    # ⚠️ 本卡红线 E2 规定 `sensor_case` **顶层不得 import `lda_l2`**（零重计算·请求期零求解器）
    #    ⇒ 温漂预算**不挂进卡片**，只在本门禁里用「卡上现算值 + 模块现算」**对拍**。
    from lda_l2 import sensor_temp_budget as TB

    _sc_tb = TB.selfcheck_sensor_temp_budget()
    check("S1 sensor_temp_budget 自检 %d 项全过（两条闭式 / 两条恒等式 / 绝对量级 / 非法入参）"
          % len(_sc_tb),
          not [k for k, v in _sc_tb.items() if not v],
          "fail=%s" % [k for k, v in _sc_tb.items() if not v])

    _met = card["metrics"]
    _tb = TB.temp_budget_report(
        R_um=float(card["design"]["R_um"]),
        lod_elec_riu=float(_met["LOD_elec_riu"]),
        dn_dT=float(SC.DEFAULT_NOISE["dn_dT"]),
        dT_stab_k=float(SC.DEFAULT_NOISE["dT_stability_K"]),
        cmr=float(SC.DEFAULT_NOISE["CMR"]),
    )
    _dp, _rq, _fs = _tb["design_point"], _tb["requirement"], _tb["feasibility"]

    # S2 🔴 跨源一致：模块现算的温漂项 ≡ 卡上 metrics 现算值（逐位）
    check("S2 🔴 跨源一致：temp_budget.LOD_temp ≡ 卡上 metrics.LOD_temp_riu（逐位 `==`）∧ "
          "温差比 ≡ LOD_temp/LOD_elec（相对 1e-15）",
          _dp["LOD_temp_riu"] == _met["LOD_temp_riu"]
          and abs(_dp["temp_over_elec"] - _met["LOD_temp_riu"] / _met["LOD_elec_riu"])
          <= 1e-15 * _dp["temp_over_elec"],
          "%.6e vs %.6e" % (_dp["LOD_temp_riu"], _met["LOD_temp_riu"]))

    # S3 🔴 跨模块同源：工艺典型 CMR 与卡内 cmr_from_mismatch 口径**逐位**一致
    check("S3 🔴 跨模块同源：CMR_typical_public ≡ cmr_from_mismatch(REFERENCING_MISMATCH_TYPICAL)"
          "（逐位 `==`）",
          _fs["CMR_typical_public"] == SC.cmr_from_mismatch(SC.REFERENCING_MISMATCH_TYPICAL),
          "%r vs %r" % (_fs["CMR_typical_public"],
                        SC.cmr_from_mismatch(SC.REFERENCING_MISMATCH_TYPICAL)))

    # S4 🔴 处方 A（片载温控）反解往返：用 dT_req 代回必须恰好 parity
    check("S4 处方 A 反解往返：LOD_temp(dT_req) == LOD_elec（相对 1e-14）",
          abs(TB.lod_temp_riu(_dp["dn_dT_per_K"], _rq["dT_req_K"], _dp["CMR"])
              - _dp["LOD_elec_riu"]) <= 1e-14 * _dp["LOD_elec_riu"],
          "dT_req=%.4e K" % _rq["dT_req_K"])

    # S5 🔴 处方 B（参考通道）反解往返（退到热力学下限时）
    check("S5 处方 B 反解往返：LOD_temp(δT_floor, CMR_req) == LOD_elec（相对 1e-14）",
          _fs["identity_holds_on_floor"] is True
          and abs(TB.lod_temp_riu(_dp["dn_dT_per_K"], _fs["thermal_floor_K"],
                                  _rq["CMR_req_at_floor"]) - _dp["LOD_elec_riu"])
          <= 1e-14 * _dp["LOD_elec_riu"],
          "CMR_req=%.4f" % _rq["CMR_req_at_floor"])

    # S6 🔴 两条处方互为倒数替代：CMR_req × dT_req ≡ δT（恒等式，不是巧合）
    check("S6 🔴 恒等式 CMR_req × dT_req ≡ δT_floor（相对 1e-12）"
          "—— 温控与参考通道**可任意兑换**",
          abs(_fs["identity_cmr_req_times_dt_req"] - _fs["thermal_floor_K"])
          <= 1e-12 * _fs["thermal_floor_K"],
          "%.6e vs %.6e" % (_fs["identity_cmr_req_times_dt_req"], _fs["thermal_floor_K"]))

    # S7 🔴 比值不变性（老陷阱第五次）：dT×100 且 CMR×100 ⇒ LOD **逐位不变**
    #    ⇒ 只判比值等于什么都没判；故判决必须挂在**两个各自独立的物理上限**上：
    #      温控 ↔ 器件自身热涨落 δT=T√(k_B/C) · 参考 ↔ 工艺失配 CMR=1/δ
    check("S7 🔴 比值不变性：dT×100 且 CMR×100 ⇒ LOD_temp **逐位不变**（`==`）"
          "⇒ 判决必须靠两条独立上限，不能靠比值",
          TB.lod_temp_riu(_dp["dn_dT_per_K"], 100.0 * _dp["dT_stab_K"],
                          100.0 * _dp["CMR"]) == _dp["LOD_temp_riu"])

    # S8 判定是**机核**而非手填 bool
    check("S8 判定机核：温控不可行（缺口 %.1f× > 10×）∧ verdict 与 flag 一致 ∧ 现役点确为温漂主导"
          % _fs["temp_control_shortfall"],
          _fs["temp_control_feasible"] is False
          and _fs["temp_control_shortfall"] > 10.0
          and ((_fs["verdict"] == "temp_control_infeasible_use_referencing")
               == (_fs["temp_control_feasible"] is False))
          and _dp["temp_over_elec"] > 1.0,
          "over_elec=%.1f×" % _dp["temp_over_elec"])

    # S9 🔴 绝对量级锚点（S7 已证比值判据在此恒失效）
    check("S9 🔴 参考档**绝对量级锚点**：C∈[5,30]e-12 J/K ∧ δT_floor∈[0.2,0.5] mK ∧ "
          "dT_req∈[5,10] µK ∧ 温控缺口∈[20,80]×",
          5.0e-12 <= _dp["heat_capacity_J_per_K"] <= 3.0e-11
          and 2.0e-4 <= _fs["thermal_floor_K"] <= 5.0e-4
          and 5.0e-6 <= _rq["dT_req_K"] <= 1.0e-5
          and 20.0 <= _fs["temp_control_shortfall"] <= 80.0,
          "C=%.3e δT=%.3e dT=%.3e 缺口=%.1f"
          % (_dp["heat_capacity_J_per_K"], _fs["thermal_floor_K"],
             _rq["dT_req_K"], _fs["temp_control_shortfall"]))

    # S10 未擅自改现役设计点与对外数字（同 v0.9.293 H7 纪律）
    check("S10 🔴 未擅自改对外数字：现役噪声仍 dT_stab=5e-3 / CMR=1.0 ∧ "
          "卡上 LOD_real 仍由温漂主导（新层只并列披露，不替换设计点）",
          SC.DEFAULT_NOISE["dT_stability_K"] == 5e-3
          and SC.DEFAULT_NOISE["CMR"] == 1.0
          and _met["dominant_limit"] == "temp",
          "dT=%.3g CMR=%.3g" % (SC.DEFAULT_NOISE["dT_stability_K"],
                                SC.DEFAULT_NOISE["CMR"]))

    # S11 反向探针：① 热容 ×10 ⇒ 热涨落下限降 √10（物理必然）
    #                ② 伪造「热涨落下限只有 dT_req 的一半」⇒ 缺口缩到 0.5
    #                   ⇒ S8 的「不可行 ∧ >10×」与 S9 的 [20,80] 区间**双红**
    _c10 = TB.thermal_fluctuation_floor_k(TB.DEFAULT_TEMP_K,
                                          10.0 * _dp["heat_capacity_J_per_K"])
    _faked_shortfall = 0.5 * _rq["dT_req_K"] / _rq["dT_req_K"]
    check("S11 反向探针：C×10 ⇒ δT_floor 降 √10 ∧ 伪造 δT_floor=dT_req/2 ⇒ 缺口 0.5 "
          "⇒ S8（不可行 ∧ >10×）与 S9（[20,80]）**双红**",
          abs(_c10 / _fs["thermal_floor_K"] - 1.0 / math.sqrt(10.0)) < 1e-14
          and _faked_shortfall < 1.0
          and not (20.0 <= _faked_shortfall <= 80.0),
          "δT×%.6f 伪造缺口=%.3f" % (_c10 / _fs["thermal_floor_K"], _faked_shortfall))

    # ══════════════════════ K 自入 CI core ══════════════════════
    try:
        import run_ci_regression as R  # noqa: E402,F401
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）",
              "run_sensor_panel_smoke.py" in R.CORE_SMOKES,
              "len=%d" % len(R.CORE_SMOKES))
    except Exception as e:  # pragma: no cover
        check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False, "import 失败: %s" % e)

    bad = globals().get("FAIL", 0)
    good = globals().get("PASS", 0)
    print("")
    print("门禁 smoke：%d PASS / %d FAIL" % (good, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
