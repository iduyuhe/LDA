"""目标 → 设计包 → 版图 → GDS + 签核 的单命令装配层（P1-T1.2）。

为什么需要
----------
M1（端到端单命令率）在本项之前 = **0**：从「一句话目标」到「GDS + 签核报告」
**没有路径**，因为两端各自只走了一半：

  · `lda check <spec.json>` 收的是**参数已由人写死**的链路（`_build_link`），
    它不设计、只装配 —— 参数从哪来它不管；
  · `lda design <kind> --target <float>` 只出**器件候选**（params + verdict），
    不出版图、也不喂给版图链路。

中间缺的那一层就是本模块：把「目标」经 `DesignEngine` **真实闭环**解出参数，
再按**版图口径**的键名装配成 `LinkModel`，落进既有
`layout_only → export_chip_gds`（DRC + LVS 双闸，v0.9.128 起 LVS 默认含 G4
几何回提）。

本模块的边界（🔴 与 `cli.py` 的同一红线）
-----------------------------------------
只做**装配 + 键名桥接 + 诚实登记**：不引入新求解器、不引入新判决逻辑、
不改任何判据。所有数值都来自既有引擎；本层只决定「哪些数字喂给谁」。

🔴 为什么「引擎 kind → 版图 kind」是一张**显式白名单**而不是自动推断
----------------------------------------------------------------
实测（22 类引擎 kind 全扫 + 逐项跑通「目标 → 版图 → GDS」）：只有 **2 类**
能真正桥到版图（见 `BRIDGEABLE`）。其余 20 类里：

  · 一部分是**量子域 / 有源 / 无 2D 版图表达**的器件（`MziInterferometer` /
    `PhCavity` / `Transmon` / `PhaseShifter` …）—— `gds_export.geometry_desc`
    对它们直接 `raise ValueError`，这是**物理事实**（没有版图表达就没有 GDS），
    不是接线缺失；
  · 一部分是**同名不同物**的引擎器件类（`DirectionalCoupler2` / `Mmi1x2` /
    `GratingCoupler2` vs 版图的 `DirectionalCoupler` / `MMI` / `GratingCoupler`）
    —— 把它们**假设**为等价物等于凭空造一条「看起来能跑、其实没证据」的通路；
  · 🔴 还有一类**最隐蔽**：引擎 kind 有对应版图 kind、也跑得通，**但它的设计
    输出到不了版图**。《`EXCLUDED_ENGINE_KINDS` 里的 `engine_waveguide` 就是
    实测抓到的这一类》—— 故本表**按"输出真的落到几何"验收**，而不是按
    "名字对得上"验收。

本层**拒绝**自动配对，只登记为不可桥接并给出原因；要新增桥接项，必须
**逐个给出「设计输出确实进入版图几何」的证据**（`run_cli_build_smoke` 的
④a/④c 就是这条证据的机器化形式）。

诚实边界（写进返回值 `honest_notes`，不藏）
------------------------------------------
① 本层只把参数**装配**进版图；链路级**光学性能**不在此重新验证 —— 每类器件
   的「目标 → 参数」由 `DesignEngine` 闭环（含真实求解器双重验证）负责，
   装配后的**整链**性能未做光学仿真（版图链交付的是几何 + 可制造性 + 一致性）。
② DRC 是**主权几何子集**（最小线宽 / 间距 / 面积），**不是** foundry 工艺级
   全量 deck（那属 D5，必须外部）。
③ LVS 的"尺寸一致"是**代码路径级独立**（版图几何独立测量 vs IR 声明），
   不是物理方法级独立（`lvs_geom` docstring 已明示）。
④ 无可桥接引擎的器件**不会被悄悄丢掉**：goal 里出现了却解不出来 ⇒ 整条
   命令**失败并指名道姓**（静默丢弃会造出"与目标不符的 GDS"）。参数已知时
   仍可用 `params` 直接给定（该路径不受桥接表限制）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 引擎 kind → 版图 kind + 参数键名映射（显式白名单 · 见模块 docstring）
# ---------------------------------------------------------------------------
# 每条 = 引擎 kind: (版图 kind, {引擎参数键: 版图参数键})
# 准入门槛：**该设计输出真的进入版图几何**（不是"名字对得上"）。
BRIDGEABLE: Dict[str, Tuple[str, Dict[str, str]]] = {
    # 实测引擎输出 {'R_um': 12.0}；`device_geom_of` 的环特例读 params['R']
    # ⇒ 改 R ⇒ 环半径几何随动（run_cli_build_smoke ④a 实测敏感）
    "engine_ringresonator": ("RingResonator", {"R_um": "R"}),
    # 实测引擎输出 {'periods': 5}；`device_geom_of` 通用分支委托
    # geometry_desc → primitives，读 params['periods'] ⇒ 周期数进几何（④a 实测敏感）
    "engine_braggmirror": ("BraggMirror", {"periods": "periods"}),
}

# 🔴 被**主动排除**的引擎 kind + 逐条原因（"跑得通但输出落不到几何"类）
EXCLUDED_ENGINE_KINDS: Dict[str, str] = {
    "engine_waveguide": (
        "唯一设计输出 `width_um` 在**芯片级没有自由度** —— 芯片级波导宽度是"
        "**全局参数**：`chip_layout_export.device_geom_of` 对 Waveguide 用 `wg_width`"
        "（忽略 `params['width']`），且 `route_geoms` 的全部布线也用 `wg_width`；"
        "器件若改用别的宽度会与布线**端口不连续**。⇒ 该设计输出对芯片版图无效，"
        "不得登记为可桥接。⚠️ 附带登记一处**口径分歧**（需立项裁定，本层不擅自改）："
        "**器件级** `gds_export.geometry_desc` 读 `params['width']`（器 DRC / "
        "tapeout 管道走它），与**芯片级** `device_geom_of` 的取值不一致 —— "
        "`run_cli_build_smoke` ④c 把该分歧钉成判据：一旦被修（改 width 会动几何），"
        "该判据变红 ⇒ 必须重新评估是否把 engine_waveguide 纳入桥接。"),
}

# 反向表（版图 kind → 引擎 kind）。🔴 必须唯一，否则 goal 里只写 kind 时
# 无法确定用哪个引擎 —— 本模块在 import 期断言唯一性（见 _assert_bijection）。
LAYOUT_TO_ENGINE: Dict[str, str] = {v[0]: k for k, v in BRIDGEABLE.items()}

# 不可桥接的引擎 kind + 原因（**逐条登记，不写"其它"**）
_NOT_BRIDGEABLE_REASON = {
    "no_2d_layout": ("量子域 / 有源 / 无 2D 版图表达 —— "
                     "gds_export.geometry_desc 对其 raise ValueError（物理事实，非接线缺失）"),
    "distinct_device_class": ("引擎器件类与版图器件**同名不同物**（如 "
                              "DirectionalCoupler2 vs DirectionalCoupler）—— 等价性无证据，"
                              "拒绝自动配对（须逐个给证据后手工登记）"),
}


def _assert_bijection() -> None:
    """反向表必须唯一（import 期自检，避免同版图 kind 对应多引擎时静默选错）。"""
    rev: Dict[str, List[str]] = {}
    for ek, (lk, _km) in BRIDGEABLE.items():
        rev.setdefault(lk, []).append(ek)
    dup = {lk: eks for lk, eks in rev.items() if len(eks) > 1}
    if dup:
        raise RuntimeError(f"BRIDGEABLE 反向表不唯一（同一版图 kind 多引擎）：{dup}")


_assert_bijection()


def bridgeable_engine_kinds() -> List[str]:
    """可桥接的引擎 kind 清单（排序 · 供 CLI/文档/门禁对账）。"""
    return sorted(BRIDGEABLE)


def layout_kinds_supported_by_layout_layer() -> List[str]:
    """`geometry_desc` 支持导出的版图 kind（实测枚举，不猜）。

    ⚠️ 与 `BRIDGEABLE` **不是同一张表**：这张是「版图层能画什么」，
    `BRIDGEABLE` 是「引擎能设计什么且版图层能画什么」。两者刻意分开，
    因为后者是**交集**结论，改一处不影响另一处。
    """
    return ["Waveguide", "RingResonator", "RingAddDrop", "DirectionalCoupler",
            "SymmetricYBranch", "Taper", "EulerBend", "MMI", "GratingCoupler",
            "BraggMirror"]


def unbridgeable_engine_kinds() -> List[str]:
    """当前**未**桥接的引擎 kind（用于诚实报告覆盖率，不是"忽略清单"）。

    `bridgeable ∪ unbridgeable == ENGINE_KINDS` 且互斥（门禁断言）——
    保证「没有任何引擎 kind 被悄悄遗忘」。
    """
    from lda_design.design_package import ENGINE_KINDS
    return sorted(k for k in ENGINE_KINDS if k not in BRIDGEABLE)


def excluded_engine_kinds() -> Dict[str, str]:
    """**主动排除**的引擎 kind → 原因（"跑得通但设计输出落不到几何"类）。"""
    return dict(EXCLUDED_ENGINE_KINDS)


# ---------------------------------------------------------------------------
# 单器件：目标 → 引擎闭环 → 版图口径参数
# ---------------------------------------------------------------------------
def resolve_engine_kind(kind: str, explicit: Optional[str] = None) -> str:
    """把 goal 里的 `kind`（版图口径）解析成引擎 kind。

    explicit（`design.engine`）优先；否则查反向表。解析不出 ⇒ raise ValueError
    （**不猜**：猜错会产生"看起来对、其实另一个器件"的版图）。
    """
    if explicit:
        if explicit not in BRIDGEABLE:
            raise ValueError(
                f"引擎 {explicit!r} 未登记为可桥接（可桥接：{bridgeable_engine_kinds()}）")
        lk = BRIDGEABLE[explicit][0]
        if lk != kind:
            raise ValueError(
                f"design.engine={explicit!r} 对应版图器件 {lk!r}，与 devices[].kind="
                f"{kind!r} 不一致（拒绝按不一致的声明装配）")
        return explicit
    ek = LAYOUT_TO_ENGINE.get(kind)
    if not ek:
        raise ValueError(
            f"器件 {kind!r} 无对应可桥接引擎（无法由目标解出参数）。"
            f"可桥接：{sorted(LAYOUT_TO_ENGINE)}；"
            f"若该器件参数已知，请改用 params 显式给定")
    return ek


def map_engine_params(engine_kind: str, engine_params: Dict[str, Any]
                      ) -> Dict[str, Any]:
    """引擎参数键 → 版图参数键（按 `BRIDGEABLE` 的键名表）。

    引擎输出里**未登记**的键一律丢弃并如实返回被丢弃清单（不静默）——
    不认识的键说明桥接表已过期，宁可让调用方看见。
    """
    km = BRIDGEABLE[engine_kind][1]
    out, dropped = {}, []
    for k, v in (engine_params or {}).items():
        if k in km:
            out[km[k]] = v
        else:
            dropped.append(k)
    return {"layout_params": out, "dropped_keys": dropped}


def design_device(kind: str, target: Optional[float] = None,
                  engine: Optional[str] = None, top_k: int = 3) -> Dict[str, Any]:
    """单个器件的「目标 → 设计包（引擎闭环）→ 版图口径参数」。

    返回 dict：
      ok / kind / engine_kind / engine_params / layout_params /
      dropped_keys / package(统一 DesignPackage) / error
    """
    try:
        ek = resolve_engine_kind(kind, engine)
    except ValueError as e:
        return {"ok": False, "kind": kind, "engine_kind": engine,
                "error": str(e), "layout_params": {}}
    from lda_design.design_package import package_from_engine
    pkg = package_from_engine(ek, target, top_k=top_k)
    if not pkg.get("ok"):
        return {"ok": False, "kind": kind, "engine_kind": ek,
                "error": f"引擎闭环失败：{pkg.get('error', 'unknown')}",
                "layout_params": {}}
    ep = (pkg.get("design") or {}).get("params") or {}
    m = map_engine_params(ek, ep)
    return {"ok": True, "kind": kind, "engine_kind": ek,
            "engine_params": dict(ep),
            "layout_params": m["layout_params"],
            "dropped_keys": m["dropped_keys"],
            "verification_passed": bool((pkg.get("verification") or {}).get("passed")),
            "package": pkg, "error": None}


# ---------------------------------------------------------------------------
# 整条 goal：装配 link
# ---------------------------------------------------------------------------
def assemble_goal(goal: Dict[str, Any], top_k: int = 3
                  ) -> Dict[str, Any]:
    """goal（一句话目标 + 器件目标 + 互连）→ LinkModel + 设计包清单。

    goal schema：
      {
        "domain": "photon",
        "name":   "goal_xxx",
        "goal":   "（人读的一句话目标，仅作记录/报告标题）",
        "devices": [
          {"id": "wg1", "kind": "Waveguide"},                     # 参数走默认
          {"id": "ring", "kind": "RingResonator",
           "design": {"target": 17.5, "engine": "engine_ringresonator"}},  # 引擎解
          {"id": "dc", "kind": "DirectionalCoupler",
           "params": {"gap": 0.3, "Lc": 10.0}}                    # 参数已知
        ],
        "nets":    [{"net":"n1","from":["wg1","out"],"to":["ring","in"]}],
        "io":      [{"net":"e1","device":"wg1","port":"in"}],
        "sources": [{"device":"wg1","port":"in"}]
      }

    🔴 任一器件解不出来 ⇒ **整体失败**（`ok=False` + `errors` 指名道姓），
    绝不静默丢弃 —— 静默丢弃等于交出一份**与目标不符的 GDS**。
    """
    from lda_chain.link_model import LinkModel

    domain = goal.get("domain", "photon")
    link = LinkModel(domain=domain, name=goal.get("name", "goal-link"))
    designs: List[Dict[str, Any]] = []
    errors: List[str] = []

    if not goal.get("devices"):
        # 空 goal（缺键 / devices 为空）⇒ 给可用指引，而不是让下游在布局期抛异常
        return {"ok": False, "link": link, "designs": [], "domain": domain,
                "name": link.ir.name,
                "errors": ["goal 未声明任何 devices（空目标无法装配版图）"]}

    for d in goal.get("devices", []):
        did = d.get("id")
        kind = d.get("kind")
        if not did or not kind:
            errors.append(f"器件缺少 id/kind：{d!r}")
            continue
        spec = d.get("design")
        if spec:
            res = design_device(kind, spec.get("target"),
                                spec.get("engine"), top_k=top_k)
            if not res.get("ok"):
                errors.append(f"器件 {did!r}（{kind}）：{res.get('error')}")
                continue
            if res.get("dropped_keys"):
                errors.append(
                    f"器件 {did!r}（{kind}）：引擎参数键 {res['dropped_keys']} "
                    f"不在桥接表内 ⇒ 拒绝静默丢弃（桥接表可能已过期）")
                continue
            params = res["layout_params"]
            designs.append({"id": did, "kind": kind, "mode": "engine",
                            "engine_kind": res["engine_kind"],
                            "engine_params": res["engine_params"],
                            "layout_params": params,
                            "verification_passed": res["verification_passed"],
                            "package": res["package"]})
        else:
            params = d.get("params") or {}
            designs.append({"id": did, "kind": kind, "mode": "params",
                            "engine_kind": None, "engine_params": None,
                            "layout_params": dict(params),
                            "verification_passed": None, "package": None})
        link.add_device(did, kind, params=params)

    for nt in goal.get("nets", []):
        try:
            f, t = nt["from"], nt["to"]
            link.connect(nt["net"], f[0], f[1], t[0], t[1])
        except Exception as e:                                   # noqa: BLE001
            errors.append(f"net {nt.get('net')!r} 连接失败：{str(e)[:120]}")
    for io in goal.get("io", []):
        try:
            link.external_io(io["net"], io["device"], io["port"])
        except Exception as e:                                   # noqa: BLE001
            errors.append(f"IO {io.get('net')!r} 声明失败：{str(e)[:120]}")
    for s in goal.get("sources", []):
        try:
            link.mark_source(s["device"], s["port"])
        except Exception as e:                                   # noqa: BLE001
            errors.append(f"source {s.get('device')}.{s.get('port')} 声明失败：{str(e)[:120]}")

    return {"ok": not errors, "link": link, "designs": designs, "errors": errors,
            "domain": domain, "name": link.ir.name}


# ---------------------------------------------------------------------------
# 端到端：goal → 版图 → GDS + 签核报告（写盘）
# ---------------------------------------------------------------------------
def signoff_summary(rep: Dict[str, Any], out: Dict[str, Any]) -> Dict[str, Any]:
    """**单一来源**的签核摘要（JSON 与 Markdown 都由它渲染 ⇒ 天然同口径）。"""
    drc, lvs = rep["drc_report"], rep["lvs_report"]
    gc = lvs.get("geom_check") or {}
    ok = bool(drc.get("all_pass")) and lvs.get("verdict") == "ACCEPT" \
        and not (gc.get("violations") or [])
    return {
        "verdict": "ACCEPT" if ok else "REJECT",
        "drc_all_pass": bool(drc.get("all_pass")),
        "drc_n_pass": drc.get("n_pass"), "drc_n_checked": drc.get("n_checked"),
        "lvs_verdict": lvs.get("verdict"),
        "n_nets_match": (lvs.get("match") or {}).get("n_nets_match"),
        "n_nets_total": (lvs.get("match") or {}).get("n_nets_total"),
        "geom_params_checked": gc.get("n_params_checked"),
        "geom_params_declared": gc.get("n_params_declared"),
        "geom_violations": list(gc.get("violations") or []),
        "geom_failed_kinds": list(gc.get("geom_failed") or []),
        "gds_bytes": rep["gds_stats"].get("gds_bytes"),
        "n_devices": rep["gds_stats"].get("n_devices"),
        "n_nets": rep["gds_stats"].get("n_nets"),
        "bbox_um": rep["gds_stats"].get("bbox_um"),
        "out_dir": str(out.get("out_dir", "")),
        "gds_path": str(out.get("gds_path", "")),
    }


def signoff_from_link(link: Any, designs: List[Dict[str, Any]],
                      wg_width: float = 0.5, goal_text: str = "",
                      meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """**唯一**的「已装配链路 → 版图 → GDS → 签核结构」链（**不落盘**）。

    为什么必须收口成一处：本链原本只存在于 `build_goal` 里；WebUI 的
    「设计包 → GDS + 签核」（T1.1）需要**同一条链**，若在 `lda_webui` 再抄一份
    `layout_only → export_chip_gds → signoff_summary` 序列，就正好复刻
    P0-0 血案的结构（「同一段逻辑抄两遍、错得一样」—— 见
    `chip_layout_export._desc_geoms` 的记载）。⇒ 写盘版（`build_goal`）与
    内存版（`signoff_single_device` / WebUI）**共用本函数**。

    返回 {ok, verdict, stage, summary, signoff, gds_bytes, errors}。
    `ok` 语义：**双闸 ACCEPT**（DRC 全过 + LVS ACCEPT + G4 几何回提零违规）。
    """
    from lda_chain.route_sim import layout_only
    from lda_l2.chip_layout_export import export_chip_gds

    meta = dict(meta or {})
    try:
        lay = layout_only(link, wg_width=wg_width)
        rep = export_chip_gds(link, lay["placement"], lay["routes"],
                              wg_width=wg_width)
    except Exception as e:                                       # noqa: BLE001
        # 版图层拒绝（无 2D 版图表达 / 参数越界）⇒ 如实失败并指名，不产出半成品
        return {"ok": False, "verdict": "REJECT", "stage": "layout",
                "errors": [f"版图 / GDS 导出失败：{type(e).__name__}: {str(e)[:200]}"],
                "summary": None, "signoff": None, "gds_bytes": b""}

    summ = signoff_summary(rep, meta)
    signoff = {
        "schema": "lda.goal_signoff/1",
        "goal": {"name": link.ir.name, "domain": meta.get("domain", "photon"),
                 "goal_text": goal_text, "wg_width_um": float(wg_width)},
        "summary": summ,
        "designs": [_design_record(d) for d in designs],
        "drc_report": rep["drc_report"],
        "lvs_report": _jsonable_lvs(rep["lvs_report"]),
        "gds_stats": rep["gds_stats"],
        "hierarchy": rep["hierarchy"],
        "io_ports": rep["io_ports"],
        "honest_notes": _HONEST_NOTES,
    }
    return {"ok": summ["verdict"] == "ACCEPT", "verdict": summ["verdict"],
            "stage": "signoff", "summary": summ, "signoff": signoff,
            "gds_bytes": rep["gds_bytes"], "errors": []}


def signoff_single_device(kind: str, params: Dict[str, Any],
                          wg_width: float = 0.5, name: str = "design",
                          top_k: int = 3) -> Dict[str, Any]:
    """单器件（**版图口径参数已给定**）→ 芯片级 GDS + 签核（**不落盘**）。

    供 WebUI「设计包 → GDS + 签核」（P1-T1.1）使用：设计包里的参数已由
    `DesignEngine` 解出，此处**不再跑引擎**（零求解器开销），只走
    `assemble_goal(params 模式) → signoff_from_link` —— 与 `lda build` 同链。

    ⚠️ 参数口径是**版图口径**（如 `RingResonator.R` / `BraggMirror.periods`），
    **不是**引擎口径（`R_um`）；引擎口径请先用 `map_engine_params` 桥接。
    """
    goal = {"domain": "photon", "name": name,
            "devices": [{"id": "d0", "kind": kind, "params": dict(params)}]}
    asm = assemble_goal(goal, top_k=top_k)
    if not asm["ok"]:
        return {"ok": False, "verdict": "REJECT", "stage": "assemble",
                "errors": asm["errors"], "summary": None, "signoff": None,
                "gds_bytes": b""}
    res = signoff_from_link(asm["link"], asm["designs"], wg_width=wg_width,
                            goal_text=goal.get("goal", ""),
                            meta={"domain": asm["domain"]})
    res["designs"] = asm["designs"]
    return res


def build_goal(goal: Dict[str, Any], out_dir: Any, wg_width: float = 0.5,
               top_k: int = 3) -> Dict[str, Any]:
    """端到端单命令主流程：goal → 设计包 → 版图 → GDS + 签核报告（落盘）。

    返回 {ok, verdict, summary, signoff(JSON 结构), markdown, gds_path,
          report_paths, designs, errors, honest_notes}。
    `ok` 表示**整条命令成功且双闸 ACCEPT**；`ok=False` 时 `errors` 非空
    （goal 层问题）或 `verdict=REJECT`（签核层问题），二者语义不同、如实区分。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    asm = assemble_goal(goal, top_k=top_k)
    if not asm["ok"]:
        return {"ok": False, "verdict": "REJECT", "stage": "assemble",
                "errors": asm["errors"], "designs": asm["designs"],
                "summary": None, "signoff": None, "markdown": "",
                "report_paths": {}, "gds_path": None,
                "honest_notes": _HONEST_NOTES}

    link = asm["link"]
    name = link.ir.name or "chip"
    gds_path = out / f"{name}.gds"
    # 🔴 装配之后的链**只有一处定义**（signoff_from_link）—— 本函数只负责落盘。
    res = signoff_from_link(link, asm["designs"], wg_width=wg_width,
                            goal_text=goal.get("goal", ""),
                            meta={"domain": asm["domain"], "out_dir": out,
                                  "gds_path": gds_path})
    if res["stage"] != "signoff":
        return {"ok": False, "verdict": "REJECT", "stage": res["stage"],
                "errors": res["errors"], "designs": asm["designs"],
                "summary": None, "signoff": None, "markdown": "",
                "report_paths": {}, "gds_path": None,
                "honest_notes": _HONEST_NOTES}

    summ, signoff = res["summary"], res["signoff"]
    gds_path.write_bytes(res["gds_bytes"])

    jpath = out / f"{name}.signoff.json"
    jpath.write_text(json.dumps(signoff, ensure_ascii=False, indent=2, default=str)
                     + "\n", encoding="utf-8")
    mpath = out / f"{name}.signoff.md"
    mpath.write_text(goal_markdown(signoff), encoding="utf-8")
    ppath = None
    pkgs = [d["package"] for d in asm["designs"] if d.get("package")]
    if pkgs:
        ppath = out / f"{name}.design_packages.json"
        ppath.write_text(json.dumps(pkgs, ensure_ascii=False, indent=2, default=str)
                         + "\n", encoding="utf-8")

    paths = {"gds": str(gds_path), "signoff_json": str(jpath),
             "signoff_md": str(mpath), "design_packages": str(ppath) if ppath else None}
    return {"ok": summ["verdict"] == "ACCEPT", "verdict": summ["verdict"],
            "stage": "signoff", "summary": summ, "signoff": signoff,
            "markdown": goal_markdown(signoff), "gds_path": str(gds_path),
            "report_paths": paths, "designs": asm["designs"], "errors": [],
            "honest_notes": _HONEST_NOTES}


def _design_record(d: Dict[str, Any]) -> Dict[str, Any]:
    """签核报告里的逐器件设计记录（**剔除**体积大的 package 全文）。"""
    return {"id": d["id"], "kind": d["kind"], "mode": d["mode"],
            "engine_kind": d["engine_kind"],
            "engine_params": d["engine_params"],
            "layout_params": d["layout_params"],
            "verification_passed": d["verification_passed"]}


def _jsonable_lvs(lvs: Dict[str, Any]) -> Dict[str, Any]:
    """LVS 报告轻量化：丢 bytes/大对象，保留判决与几何回提明细。"""
    out = {k: v for k, v in lvs.items() if k not in ("gds", "layout_netlist", "schematic_netlist")}
    return out


_HONEST_NOTES = [
    "单一来源：GDS/DRC/LVS 全部由既有 export_chip_gds 计算；本层只装配参数，"
    "不重算、不改判据（JSON 与 Markdown 由同一份 signoff dict 渲染 ⇒ 同口径）。",
    "装配后的**整链光学性能**未做验证 —— 每类器件的「目标→参数」由 DesignEngine "
    "闭环（真实求解器双重验证）负责；本命令交付几何 + 可制造性 + 一致性。",
    "DRC 是**主权几何子集**（最小线宽/间距/面积），不是 foundry 工艺级全量 deck"
    "（D5 起必须外部 deck）。",
    "LVS 的尺寸一致是**代码路径级独立**（版图几何独立测量 vs IR 声明），"
    "非物理方法级独立（详见 lda_l2/lvs_geom.py docstring）。",
    f"引擎 kind 仅 {len(BRIDGEABLE)} 类通过准入门槛（设计输出**确实进入版图几何**）："
    f"{bridgeable_engine_kinds()}；其余引擎 kind 或无 2D 版图表达、或与版图器件"
    "同名不同物、或**设计输出在芯片级没有自由度**（如 engine_waveguide 的 width）"
    "⇒ 本命令**拒绝**登记，goal 里出现即报错（不静默丢弃）。"
    "参数已知的器件仍可用 params 直接给定（不受桥接表限制）。",
]


def goal_markdown(signoff: Dict[str, Any]) -> str:
    """把 signoff dict 渲染成 markdown（**同一来源**，非第二套计算）。"""
    g, s = signoff["goal"], signoff["summary"]
    L = ["# LDA 单命令签核报告（目标 → 设计包 → 版图 → GDS）", ""]
    if g.get("goal_text"):
        L.append(f"- **目标**：{g['goal_text']}")
    L.append(f"- 设计名：`{g['name']}` · 域：{g['domain']} · 波导宽：{g['wg_width_um']} µm")
    L.append("")
    L.append("## 逐器件（设计包 → 版图参数）")
    L.append("")
    L.append("| 器件 | kind | 来源 | 引擎 | 设计参数 | 版图参数 |")
    L.append("|---|---|---|---|---|---|")
    for d in signoff["designs"]:
        src = "引擎闭环" if d["mode"] == "engine" else "goal 显式 params"
        L.append("| `%s` | %s | %s | %s | %s | %s |" % (
            d["id"], d["kind"], src, d["engine_kind"] or "—",
            json.dumps(d["engine_params"] or {}, ensure_ascii=False),
            json.dumps(d["layout_params"] or {}, ensure_ascii=False)))
    L.append("")
    L.append("## 签核结论")
    L.append("")
    L.append(f"- 判决：**{s['verdict']}**")
    L.append(f"- DRC：{s['drc_n_pass']}/{s['drc_n_checked']} 器件通过"
             f"（{'✅' if s['drc_all_pass'] else '❌'}）")
    L.append(f"- LVS：**{s['lvs_verdict']}** · {s['n_nets_match']}/{s['n_nets_total']} 网一致")
    L.append(f"- 几何回提（G4）：核对 {s['geom_params_checked']}/"
             f"{s['geom_params_declared']} 参数 · 违规 {len(s['geom_violations'])}")
    for v in s["geom_violations"]:
        L.append(f"  - ❌ {v}")
    L.append(f"- GDS：`{s['gds_path']}`（{s['gds_bytes']} B）· "
             f"bbox {s['bbox_um']} µm · {s['n_devices']} 器件 / {s['n_nets']} net")
    L.append("")
    L.append("## 诚实边界")
    L.append("")
    for n in signoff["honest_notes"]:
        L.append(f"- {n}")
    L.append("")
    return "\n".join(L)
