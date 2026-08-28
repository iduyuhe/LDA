"""LDA 设计商店 · 阶段1 MVP · 货架 → 设计就绪包（zip 交付）。

设计纪律（与 LDA 红线一致）：
  - 只由已锚定基元（GP-*）组合 + 公开信号驱动，零新物理；
  - 交付物来自真实引擎（geometry_desc 真实几何 / drc_check_device 死标量 /
    ShelfItem.evaluate() 真跑 design_pipeline 死锚比对）；
  - 诚实分层：包层级 = design_ready（预研级设计交付），非 foundry 认证、
    非本团队流片；每份包附 HONESTY.md 诚实声明。
  - 不依赖脆弱「自动布线→整芯片 GDS」，改为稳健「组件库 GDS + 逐器件 DRC」
    交付，保证包永远可构建、且内容真实不编造。

生成内容（<id>_design_ready.zip）：
  README.md                包说明 + 层级声明
  HONESTY.md               诚实声明（非 foundry / 非流片 / 经死锚验证）
  LICENSE.md               设计授权协议（使用权，非版权转让）
  report/<id>_sim_report.md    REAL · ShelfItem.evaluate() 死锚比对
  netlist/<id>.sp          REAL · composition → SPICE-like 网表
  layout/<id>_components.gds   REAL · 组件库 GDS（geometry_desc 真实几何）
  geometry/<id>_geometry.json REAL · 逐器件几何参数
  drc_lvs/<id>_drc.json    REAL · 逐器件 DRC（drc_check_device 死标量）
  process/<id>_corner.md   工艺角说明（主权近似，非 foundry）
"""
from __future__ import annotations

import io
import json
import math
import os
import secrets
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

ROOT = os.path.dirname(_LDA)                      # 仓库根（lda/ 上一级）
PKG_DIR = os.path.join(ROOT, "dist", "packages")
LICENSES_PATH = os.path.join(ROOT, "dist", "licenses.json")

# —— GP-* 基元 → 版图/DRC kind 映射（仅映射已支持几何表达的 kind）——
# GP-CROSSING 无标准 kind，走「十字相交波导」真实几何近似（诚实标注）。
GP_KIND_MAP: Dict[str, Dict[str, Any]] = {
    "GP-GRATING-EFF": {"kind": "GratingCoupler", "params": {}},
    "GP-MMI-1X2":     {"kind": "MMI", "params": {}},
    "GP-CROSSING":    {"kind": "__crossing__", "params": {}},
    "GP-YBRANCH":     {"kind": "SymmetricYBranch", "params": {}},
    "GP-SIN-PL":      {"kind": "Waveguide", "params": {"material": "SiN"}},
}

PACKAGE_TIER = "design_ready（预研级设计交付）"
GENERATED_NOTE = (
    "本包由 LDA 设计工厂自动生成：组件库版图（真实几何）+ 逐器件 DRC（死标量）"
    " + 死锚仿真比对。非 foundry 认证版、非本团队流片。"
)

# 阶段1 开放下载白名单（光子主流方向全量开放，覆盖预研企业最密集需求面）。
# 量子相关（QKD×3 + 量子保真度链×5）因出口管制合规红线 + 受众小，暂列「咨询制/即将开放」，不进自动下载白名单。
# 依据：docs/store_launch/04_market_analysis.md。后续放开只需往此集合加货架 id。
# v0.8.48：新增 8 个光子缺口品类（FR4 200G/400G 每通道、400G DR4、100G LR4、50G-PON、
# 可重构光开关、FMCW 接收、环形生物传感），均 composition⊂GP-* 且非出口管制品类。
# v0.8.49：新增 5 个光子缺口品类（相干 ZR、微环调制器、XGS-PON、WSS、VOA），均
# composition⊂GP-* 且非出口管制品类，白名单 25→30。
OPEN_SHELVES = {
    # 高速收发（DR8/FR4 × 400G/800G/1.6T + PSM4/CWDM4/FR4/LPO + 相干 ZR）
    "IM-1.6T-DR8", "IM-1.6T-FR4", "IM-800G-DR8", "IM-800G-FR4", "IM-400G-DR4",
    "IM-PSM4-SHELF", "IM-FR4-SHELF", "IM-CWDM4-SHELF", "IM-LPO-112G",
    "IM-COHERENT-400ZR",
    # WDM 解复用
    "IM-WDM-8CH-1D", "IM-DWDM-40CH", "IM-100G-LR4",
    # CPO / OCS / 可重构光交换
    "IM-CPO-WDM5", "IM-CPO-OCS", "IM-OSW-1X8",
    # 接入网（FTTH PLC + 50G-PON + XGS-PON）
    "IM-FTTH-PLC8", "IM-FTTH-PLC16", "IM-PON-50G", "IM-XGS-PON",
    # 传感（环/MZI/LiDAR TX+RX/生物）
    "IM-SENSE-RING", "IM-SENS-MZI", "IM-LIDAR-TX", "IM-LIDAR-RX", "IM-BIOSENSE",
    # 波长选择开关 / 可变衰减器（ROADM 功率均衡）
    "IM-WSS-1X9", "IM-VOA",
    # 先进封装 / 异质集成
    "IM-CHIPLET-IO", "IM-LASER-INT",
}


def is_download_open(sid: str) -> bool:
    """该货架设计就绪包是否已开放下载（阶段1 仅试点）。"""
    return sid in OPEN_SHELVES


def shelf_by_id(sid: str):
    """按 id 取货架（DEFAULT_SHELF）。"""
    from lda_l2.innovation_market import DEFAULT_SHELF
    for s in DEFAULT_SHELF:
        if s.id == sid:
            return s
    return None


def _translate(descs: List[Dict[str, Any]], ox: float, oy: float) -> List[Dict[str, Any]]:
    """把几何 desc 平移到 (ox, oy)。"""
    out = []
    for d in descs:
        d2 = dict(d)
        if d2["kind"] == "path":
            d2["points_um"] = [(x + ox, y + oy) for (x, y) in d2["points_um"]]
        else:
            d2["rings_um"] = [[(x + ox, y + oy) for (x, y) in ring]
                              for ring in d2.get("rings_um", [])]
        out.append(d2)
    return out


def _crossing_elements(ox: float, oy: float, w: float = 0.5, L: float = 10.0):
    """GP-CROSSING 真实几何近似：十字相交波导（诚实标注非标准 kind）。"""
    from lda_l2.gds_export import path, LIB_LAYER_SI
    return [
        path(LIB_LAYER_SI, w, [(-L + ox, oy), (L + ox, oy)]),
        path(LIB_LAYER_SI, 0.5, [(ox, -L + oy), (ox, L + oy)]),
    ]


def build_component_gds(compositions: List[str]) -> Tuple[bytes, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """composition（GP-* 列表）→ 组件库 GDS 字节 + 几何清单 + DRC 结果。

    返回 (gds_bytes, geometry_list, drc_list)。对每个基元尽力而为：
    成功则真实几何/DRC；失败则诚实记录 status=failed。
    """
    from lda_l2.gds_export import gds_library, geometry_desc, path, boundary, LIB_LAYER_SI
    from lda_l2.drc import drc_check_device

    elements: List[bytes] = []
    geometry_list: List[Dict[str, Any]] = []
    drc_list: List[Dict[str, Any]] = []

    pitch = 44.0
    for i, gp in enumerate(compositions):
        ox = i * pitch
        mapping = GP_KIND_MAP.get(gp, {"kind": "Waveguide", "params": {}})
        kind = mapping["kind"]
        params = mapping.get("params", {}) or {}

        # —— 几何 ——
        status = "ok"
        descs: List[Dict[str, Any]] = []
        try:
            if kind == "__crossing__":
                elements.extend(_crossing_elements(ox, 0.0))
                descs = [{"kind": "path", "layer": LIB_LAYER_SI, "width_um": 0.5,
                          "points_um": [(-10.0, 0.0), (10.0, 0.0)]},
                         {"kind": "path", "layer": LIB_LAYER_SI, "width_um": 0.5,
                          "points_um": [(0.0, -10.0), (0.0, 10.0)]}]
            else:
                descs = geometry_desc(kind, params)
                for d in descs:
                    if d["kind"] == "path":
                        elements.append(path(d["layer"], d["width_um"],
                                             [(x + ox, y) for (x, y) in d["points_um"]]))
                    else:
                        flat = [(x + ox, y) for ring in d.get("rings_um", [])
                                for (x, y) in ring]
                        elements.append(boundary(d["layer"], flat))
        except Exception as e:  # noqa: BLE001 —— 单器件几何失败不阻断整包
            status = "failed:" + str(e)[:60]
            # 诚实兜底：占位矩形边界，保留器件位
            elements.append(boundary(LIB_LAYER_SI, [(ox - 10, -10), (ox + 10, -10),
                                                    (ox + 10, 10), (ox - 10, 10)]))

        geometry_list.append({
            "gp": gp, "kind": kind, "params": params,
            "placed_at_um": [round(ox, 2), 0.0], "geometry_status": status,
            "n_elements": len(descs) if kind != "__crossing__" else 2,
        })

        # —— 逐器件 DRC（死标量）——
        drc_status = "ok"
        passed = None
        try:
            if kind == "__crossing__":
                drc_status = "几何近似交付，DRC 未覆盖（非标准 kind）"
                passed = None
            else:
                r = drc_check_device(kind, params)
                passed = bool(r.passed)
                drc_status = ("DRC 通过" if passed
                              else "DRC 未通过（默认参数几何，需 PDK 适配）")
        except Exception as e:  # noqa: BLE001
            drc_status = "DRC 不支持该 kind（诚实记录）：" + str(e)[:50]
            passed = None
        drc_list.append({"gp": gp, "kind": kind, "passed": passed,
                         "status": drc_status})

    gds_bytes = gds_library("LDA_COMPONENTS", {"COMPONENTS": elements})
    return gds_bytes, geometry_list, drc_list


def _render_sim_report(shelf) -> str:
    """REAL · ShelfItem.evaluate() 真跑 design_pipeline 死锚比对。"""
    try:
        rep = shelf.evaluate()
    except Exception as e:  # noqa: BLE001
        return ("# 仿真报告\n\n- 评估运行异常（已诚实记录）：" + str(e)[:120] + "\n")
    L = []
    L.append("# LDA 设计就绪包 · 死锚仿真比对报告")
    L.append("")
    L.append(f"- 货架：`{rep.get('id')}` · {rep.get('title')}")
    L.append(f"- 系统类型：{rep.get('system_type')} · 层级：{rep.get('honest_tier')}")
    L.append(f"- 可行性：`{'✅' if rep.get('feasible') else '❌'}` · "
             f"接受候选：{rep.get('n_accepted')}")
    L.append("")
    summ = rep.get("summary") or ""
    if summ:
        L.append("## 判决摘要")
        L.append("")
        L.append(summ)
        L.append("")
    scr = rep.get("screening")
    if isinstance(scr, dict):
        L.append("## 死锚比对证据链")
        L.append("")
        for k, v in scr.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            L.append(f"- **{k}**：{v}")
        L.append("")
    if rep.get("error"):
        L.append(f"> 注意：{rep['error']}")
        L.append("")
    L.append("*本报告沿用 LDA 物理定律锚红线：LLM 不进判决路径，PASS/FAIL "
             "由死标量比对决定。*")
    return "\n".join(L)


def _render_netlist(shelf) -> str:
    """REAL · composition → SPICE-like 网表。"""
    L = []
    L.append(f"* LDA 设计就绪包网表 · {shelf.id}")
    L.append(f"* title: {shelf.title}")
    L.append(f"* honest_tier: {shelf.honest_tier}")
    L.append(f"* system_type: {shelf.system_type}")
    L.append(".subckt " + shelf.id.replace("-", "_") + " in out")
    for i, gp in enumerate(shelf.composition):
        kind = GP_KIND_MAP.get(gp, {}).get("kind", "X")
        kind_spice = kind if kind != "__crossing__" else "CROSSING"
        L.append(f"X{i+1} in out {kind_spice}  {{src=GP:{gp}}}")
    L.append(".ends " + shelf.id.replace("-", "_"))
    L.append("* 注：端口语义（in/out）为占位；真实互连由 design_pipeline 闭环生成。")
    return "\n".join(L)


def generate_package(shelf_id: str) -> Dict[str, Any]:
    """生成（或命中缓存）货架设计就绪包，返回 {ok, zip_path, manifest}。"""
    shelf = shelf_by_id(shelf_id)
    if shelf is None:
        return {"ok": False, "error": f"未知货架 {shelf_id}"}

    os.makedirs(PKG_DIR, exist_ok=True)
    zip_name = f"{shelf_id}_design_ready.zip"
    zip_path = os.path.join(PKG_DIR, zip_name)
    if os.path.exists(zip_path):
        return {"ok": True, "zip_path": zip_path,
                "manifest": _read_manifest(zip_path), "cached": True}

    gds_bytes, geometry_list, drc_list = build_component_gds(list(shelf.composition))
    sim_report = _render_sim_report(shelf)
    netlist = _render_netlist(shelf)

    n_pass = sum(1 for d in drc_list if d["passed"] is True)
    n_drc = len(drc_list)

    # —— 工艺角说明（主权近似，非 foundry）——
    corner = (
        "# 工艺角说明（主权近似）\n\n"
        "- 本包几何/DRC 基于 LDA 主权 SOI 近似层（lib layer 1，芯层），非任何商业 "
        "foundry PDK。\n"
        "- 典型参数窗口（示意，非工艺卡）：波导宽 0.5 µm、最小弯曲半径 ≥ 5 µm、"
        "最小间距 ≥ 0.3 µm。\n"
        "- 真实流片前须适配目标 foundry PDK（C 阶段外部晶圆厂外联后提供），"
        "并完成 foundry DRC/LVS 全规则签核。\n"
        "- 标注「design_ready」= 经死锚验证、待 PDK 适配即可流片，**非本团队流片**。\n"
    )

    honesty = (
        "# 诚实声明（HONESTY）\n\n"
        "1. 本包由 LDA 设计工厂自动生成，组件库版图（真实几何）+ 逐器件 DRC（死标量）"
        "+ 死锚仿真比对，**非 foundry 认证版本**。\n"
        "2. **非本团队流片**：LDA 不做流片；本包为「预研级设计交付」，供用户适配/流片/"
        "二次开发。\n"
        "3. 几何与设计基于「主权近似 + 公开标准（IEEE / CWDM4 MSA）」，不宣称任何 "
        "晶圆厂认证。\n"
        "4. 适用层级：为预研、无条件购软件的企业/高校提供设计起点通道。\n"
        "5. 沿用 LDA 红线：LLM 不进判决路径，PASS/FAIL 由死标量比对决定。\n"
    )

    readme = (
        f"# LDA 设计就绪包 · {shelf_id}\n\n"
        f"- 标题：{shelf.title}\n"
        f"- 目标应用：{shelf.target_app}\n"
        f"- 公开信号来源：{shelf.signal_ref}\n"
        f"- 组合基元（已锚定 GP-*）：{', '.join(shelf.composition)}\n"
        f"- 交付层级：`{PACKAGE_TIER}`\n\n"
        "## 包含文件\n"
        "- `report/<id>_sim_report.md` — 死锚仿真比对（REAL）\n"
        "- `netlist/<id>.sp` — 网表（REAL）\n"
        "- `layout/<id>_components.gds` — 组件库 GDS（REAL 几何）\n"
        "- `geometry/<id>_geometry.json` — 逐器件几何（REAL）\n"
        "- `drc_lvs/<id>_drc.json` — 逐器件 DRC（REAL 死标量）\n"
        "- `process/<id>_corner.md` — 工艺角说明\n"
        "- `LICENSE.md` — 设计授权协议（使用权，非版权转让）\n"
        "- `HONESTY.md` — 诚实声明\n\n"
        f"> {GENERATED_NOTE}\n"
    )

    license_md = (
        "# LDA 设计授权协议（单次买断 · 使用权）\n\n"
        "1. **授权范围**：买方获得本设计交付物（含 GDS / 网表 / 报告）的**非独占、"
        "不可转售、不可再分发**的使用权，可用于自身研发、流片适配与二次开发。\n"
        "2. **知识产权**：设计交付物的版权与一切知识产权仍归 LDA / 上海杜特企业管理"
        "咨询有限公司所有，买方仅获前述使用权。\n"
        "3. **禁止项**：禁止转售、再分发、逆向工程、用于涉军或违反出口管制之用途。\n"
        "4. **免责**：本交付物按现状提供，经死锚验证、主权近似、**非 foundry 认证、"
        "非本团队流片**，不担保流片良率与具体性能。\n"
        "5. **责任上限**：以买方已支付费用为限。\n"
        "6. **管辖**：适用中华人民共和国法律。\n"
        "*完整条款以 docs/store_launch/01_EULA_template.md 为准。*\n"
    )

    manifest = {
        "shelf_id": shelf_id,
        "title": shelf.title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_tier": PACKAGE_TIER,
        "composition": list(shelf.composition),
        "files": [
            "README.md", "HONESTY.md", "LICENSE.md",
            f"report/{shelf_id}_sim_report.md", f"netlist/{shelf_id}.sp",
            f"layout/{shelf_id}_components.gds",
            f"geometry/{shelf_id}_geometry.json",
            f"drc_lvs/{shelf_id}_drc.json", f"process/{shelf_id}_corner.md",
        ],
        "drc_summary": {"n_checked": n_drc, "n_pass": n_pass,
                        "all_pass": (n_pass == n_drc)},
        "gds_bytes": len(gds_bytes),
    }

    # —— 组装 zip（不入 git，dist/ 已忽略）——
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{shelf_id}_design_ready/README.md", readme)
        z.writestr(f"{shelf_id}_design_ready/HONESTY.md", honesty)
        z.writestr(f"{shelf_id}_design_ready/LICENSE.md", license_md)
        z.writestr(f"{shelf_id}_design_ready/report/{shelf_id}_sim_report.md", sim_report)
        z.writestr(f"{shelf_id}_design_ready/netlist/{shelf_id}.sp", netlist)
        z.writestr(f"{shelf_id}_design_ready/layout/{shelf_id}_components.gds", gds_bytes)
        z.writestr(f"{shelf_id}_design_ready/geometry/{shelf_id}_geometry.json",
                   json.dumps(geometry_list, ensure_ascii=False, indent=2))
        z.writestr(f"{shelf_id}_design_ready/drc_lvs/{shelf_id}_drc.json",
                   json.dumps(drc_list, ensure_ascii=False, indent=2))
        z.writestr(f"{shelf_id}_design_ready/process/{shelf_id}_corner.md", corner)
        z.writestr(f"{shelf_id}_design_ready/MANIFEST.json",
                   json.dumps(manifest, ensure_ascii=False, indent=2))

    return {"ok": True, "zip_path": zip_path, "manifest": manifest, "cached": False}


def _read_manifest(zip_path: str) -> Optional[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(zip_path) as z:
            name = [n for n in z.namelist() if n.endswith("MANIFEST.json")]
            if not name:
                return None
            return json.loads(z.read(name[0]).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


# —— 兑换码授权（dist/licenses.json）——
def _load_licenses() -> Dict[str, Any]:
    if not os.path.exists(LICENSES_PATH):
        return {}
    try:
        with open(LICENSES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _save_licenses(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(LICENSES_PATH), exist_ok=True)
    with open(LICENSES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def mint_license(shelf_id: str, email: str = "", max_uses: int = 1) -> str:
    """生成兑换码并写入授权表（阶段2 由支付成功触发；阶段1 手动/CLI 用）。"""
    data = _load_licenses()
    code = secrets.token_urlsafe(16)
    data[code] = {
        "shelf_id": shelf_id, "email": email, "max_uses": max_uses,
        "used": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        "revoked": False,
    }
    _save_licenses(data)
    return code


def verify_license(code: str, shelf_id: Optional[str] = None) -> Dict[str, Any]:
    """校验兑换码：存在 / 未在吊销 / 未超限 / （可选）匹配货架。"""
    data = _load_licenses()
    rec = data.get(code)
    if rec is None:
        return {"ok": False, "reason": "invalid_code"}
    if rec.get("revoked"):
        return {"ok": False, "reason": "revoked"}
    if rec.get("used", 0) >= rec.get("max_uses", 1):
        return {"ok": False, "reason": "exhausted"}
    if shelf_id is not None and rec.get("shelf_id") != shelf_id:
        return {"ok": False, "reason": "shelf_mismatch"}
    return {"ok": True, "shelf_id": rec["shelf_id"]}


def consume_license(code: str) -> None:
    """下载成功后自增 used（限次）。"""
    data = _load_licenses()
    rec = data.get(code)
    if rec is None:
        return
    rec["used"] = rec.get("used", 0) + 1
    _save_licenses(data)


def package_info(shelf_id: str) -> Dict[str, Any]:
    """给前端：包是否就绪 + 层级 + 文件清单（不含授权）。"""
    shelf = shelf_by_id(shelf_id)
    if shelf is None:
        return {"ok": False, "error": f"未知货架 {shelf_id}"}
    zip_name = f"{shelf_id}_design_ready.zip"
    zip_path = os.path.join(PKG_DIR, zip_name)
    ready = os.path.exists(zip_path)
    return {
        "ok": True, "shelf_id": shelf_id, "package_tier": PACKAGE_TIER,
        "ready": ready, "open": is_download_open(shelf_id), "zip_name": zip_name,
        "honest_tier_note": "免费看（货架元数据）/ 付费下（设计就绪包）。",
    }


if __name__ == "__main__":
    # CLI：生成指定货架包；缺省生成全部试点。
    targets = sys.argv[1:] or [
        "IM-PSM4-SHELF", "IM-CWDM4-SHELF", "IM-FR4-SHELF",
    ]
    for tid in targets:
        r = generate_package(tid)
        print(f"{tid}: ok={r.get('ok')} cached={r.get('cached')} "
              f"manifest_files={len((r.get('manifest') or {}).get('files', []))}"
              f"{(' err=' + r['error']) if not r.get('ok') else ''}")
