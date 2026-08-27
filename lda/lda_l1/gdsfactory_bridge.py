"""LDA L1 · gdsfactory 兼容桥（v0.8.30 · B 级借用、主权合规）。

让 LDA 与 gdsfactory 生态互通，两种方式：
  ① `lda check --gds <gf_exported.gds>`：导入任意 GDSII（含 gdsfactory 导出），
     跑 LDA 主权几何 DRC 快查（gds_drc）+ 版图摘要，输出报告。
  ② `lda gf <gdsfactory_component_spec>`：把 gdsfactory 组件描述转成 LDA
     链路 spec（IR 兼容 JSON），再走 LDA 官方设计—验证闭环 + DRC/LVS 双闸。
     —— 这是《下一步方案》里"开发者钩子 `lda check <gdsfactory_component>`"
        的落地：对接最大开源光子生态，且不引入 gdsfactory 为硬依赖（B 级可选）。

主权纪律（来自 sovereign_deps.py）：
  - gdsfactory 内核 = B 级（MIT），可按"借今踢后" fork 主权副本；本桥**不**
    把 gdsfactory 列为 LDA 核心依赖（仅 optional import，缺失时优雅降级）。
  - 若用户装了 gdsfactory：桥可调用 `gf.Component` 几何 → 导出 GDS → LDA 读回
    验证；若未装：桥给出明确指引（pip 装 gdsfactory 或用 --gds 直接喂 GDS 文件），
    不阻断 LDA 自有链路 JSON 路径。
  - 红线：判决全部来自 LDA 主权几何 DRC + L0 IR 双验证，gdsfactory 仅作"几何
    来源/互通层"，不进判决路径。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# gdsfactory kind（gf.Component 常用名）→ LDA IR kind 映射（光子子集）
GF_TO_LDA_KIND = {
    "straight": "Waveguide",
    "bend_euler": "Waveguide",
    "bend_circular": "Waveguide",
    "mmi1x2": "Mmi1x2",
    "mmi2x2": "Mmi1x2",
    "coupler": "DirectionalCoupler2",
    "grating_coupler": "GratingCoupler2",
    "ring": "RingResonator",
    "mzi": "MziInterferometer",
    "y_splitter": "SymmetricYBranch",
    "taper": "Waveguide",
}


def gdsfactory_available() -> bool:
    try:
        import gdsfactory  # noqa: F401
        return True
    except Exception:
        return False


def gf_component_to_spec(component: Any, name: Optional[str] = None,
                         domain: str = "photon") -> Dict[str, Any]:
    """把 gdsfactory Component 转成 LDA 链路 spec（IR 兼容 JSON）。

    - 每个 gdsfactory 实例（references/子组件）映射为一个 LDA device；
    - 端口（gf ports）尽量映射为 LDA 外部 IO；
    - 互连（gf nets）在 LDA 侧用默认 nets 近似（不强行解析 gf 网表——
      诚实：LDA 自有链路 JSON 才是权威互连来源；gdsfactory 桥聚焦"几何互通 +
      主权校验"，互连由用户显式给出或 LDA 自动布线补全）。

    返回 LDA cli `_build_link` 兼容的 spec dict。
    """
    spec_devices: List[Dict[str, Any]] = []
    spec_io: List[Dict[str, Any]] = []
    rid = 0
    # gf.Component 的 references（实例化的子 Component）或自身 polygons
    refs = getattr(component, "references", None) or []
    if refs:
        for ref in refs:
            cname = getattr(getattr(ref, "component", None), "name", "device") or "device"
            lda_kind = GF_TO_LDA_KIND.get(cname, "Waveguide")
            did = f"d{rid}"
            rid += 1
            spec_devices.append({"id": did, "kind": lda_kind, "params": {}})
            # 端口尝试转 IO
            ports = getattr(ref, "ports", None) or {}
            for pname in list(ports)[:2]:
                spec_io.append({"net": f"{did}_{pname}", "device": did,
                                "port": "in" if "in" in str(pname) else "out"})
    else:
        # 单组件（无 references）：整体作为一个 device
        cname = getattr(component, "name", "device") or "device"
        lda_kind = GF_TO_LDA_KIND.get(cname, "Waveguide")
        spec_devices.append({"id": "d0", "kind": lda_kind, "params": {}})
        ports = getattr(component, "ports", None) or {}
        for pname in list(ports)[:2]:
            spec_io.append({"net": f"d0_{pname}", "device": "d0",
                            "port": "in" if "in" in str(pname) else "out"})

    return {
        "domain": domain,
        "name": name or getattr(component, "name", "gf_import"),
        "devices": spec_devices,
        "nets": [],
        "io": spec_io,
        "sources": [io["device"] for io in spec_io if io.get("port") == "in"][:1]
        or ([{"device": spec_devices[0]["id"], "port": "in"}] if spec_devices else []),
        "_note": ("gdsfactory 桥：几何互通 + 主权校验；互连由用户显式补或 "
                  "LDA 自动布线补全（gf 网表非权威来源）"),
    }


def export_gf_component(component: Any, path: str) -> str:
    """把 gdsfactory Component 导出为 GDS 文件（gdsfactory 可用时）。"""
    if not gdsfactory_available():
        raise RuntimeError("gdsfactory 未安装；请 `pip install gdsfactory` 或改用 `lda check --gds <file.gds>`")
    component.write_gds(path)
    return path
