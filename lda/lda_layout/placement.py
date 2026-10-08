"""LDA L1/L2 · 器件放置（placement）+ 端口锚点 + 包围盒。


P1-M2 配合 router 使用：把 LinkModel 的器件实例映射到芯片坐标，
给出端口绝对坐标（供 router 布线）与器件包围盒（供 router 避障）。

端口锚点（WDM add-drop 约定，与 gds_export.geometry_desc 的 RingAddDrop
同源）：RingResonator 的 in/out 在 through bus（下，y=-off）、drop 在
drop bus（上，y=+off）；off = R + wg_width/2 + gap，half = R*1.5。
"""
from __future__ import annotations

import math
from typing import Dict,  Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型标注用，避免 lda_chain ↔ lda_layout 循环导入
    from lda_chain.link_model import LinkModel

# v0.8.39：port_abs 组件查找缓存（placement → comp_by_id 索引）。
#   每次调用线性扫 link.ir.components 是 O(n·m) 存量低效（scale_anchor 构建
#   与 LVS 锚点表均循环调用）；缓存 {id(placement), id(link)} → {inst: comp}
#   后查表 O(1)。缓存失效条件：新 placement/link 对象（构造器每次新建，
#   规模案例/不同用例天然新对象；原地增删器件走 _port_abs_cache_clear）。
#
# 🔴 v0.9.191 修（**框架级真 bug · 由 PM-M3 同进程多次 build 首次暴露**）：
#   仅以 `id()` 为键，当上一个 placement/link 被 GC 后**新对象复用同一 id**
#   ⇒ 命中**陈旧索引** ⇒ 查不到新器件 ⇒ `port_abs` 静默退回器件原点
#   （实测：`port_abs("b1_c0","out")` 返回 (0,16) 而非 (11.01,16)，随后
#   route 端点被 LVS 归属到错误端口 ⇒ 51 处 `short_port`/`misconnect` 假红）。
#   修法：缓存值里**持有对象强引用**并做 `is` 身份校验（同对象才复用；持有引用
#   亦使 id 不可能在缓存存活期被复用）；另加容量上限防无界增长。
_port_abs_comp_cache: Dict[Tuple[int, int], Tuple["object", "object", int, Dict[str, "object"]]] = {}
_PORT_ABS_CACHE_MAX = 64


def _port_abs_comp_index(placement: dict, link) -> Dict[str, "object"]:
    """按 (placement, link) **对象身份 + 组件数版本**缓存 {inst: comp} 索引。

    命中条件（三者同时成立）：
      ① 缓存对象 `is` 当前对象（防 `id()` 回收复用毒化）；
      ② 缓存的组件数 == 当前组件数（防**同一对象增量 add_device 后索引陈旧**
         —— 这正是 v0.9.191 暴露的第二类误用：P&R 里「边加器件边取端口」会拿到
         缺后加器件的旧索引，`port_abs` 遂静默退回器件原点）。
    ⚠️ 组件数相同但成员被替换的极端场景（一增一删）仍需调用方
    `_port_abs_cache_clear()`。
    """
    key = (id(placement), id(link))
    n_comp = len(link.ir.components)
    hit = _port_abs_comp_cache.get(key)
    if hit is not None and hit[0] is placement and hit[1] is link and hit[2] == n_comp:
        return hit[3]
    idx = {c.id: c for c in link.ir.components}
    if len(_port_abs_comp_cache) >= _PORT_ABS_CACHE_MAX:
        _port_abs_comp_cache.clear()
    _port_abs_comp_cache[key] = (placement, link, n_comp, idx)
    return idx


def _port_abs_cache_clear() -> None:
    """清空 port_abs 组件索引缓存（对象原地增删器件后调用）。"""
    _port_abs_comp_cache.clear()


def port_anchor(kind: str, port: str, params: dict) -> Tuple[float, float]:
    """器件局部坐标下端口锚点 (dx,dy) µm（器件原点 0,0）。"""
    R = float(params.get("R", 10.0))
    wg_w = float(params.get("wg_width", 0.5))
    gap = float(params.get("gap", 0.3))
    if kind in ("RingResonator", "RingAddDrop"):
        half = R * 1.5
        off = R + wg_w / 2.0 + gap
        return {
            "in": (-half, -off),
            "out": (half, -off),
            "drop": (0.0, off),
        }.get(port, (0.0, 0.0))
    if kind == "Waveguide":
        length = float(params.get("length", 10.0))
        return {"in": (0.0, 0.0), "out": (length, 0.0)}.get(port, (0.0, 0.0))
    if kind == "GratingCoupler":
        L = float(params.get("L", 10.0))
        return {"fib": (0.0, 0.0), "wg": (0.0, L)}.get(port, (0.0, 0.0))
    if kind == "DirectionalCoupler":
        # 与 gds_export.geometry_desc 的双波导表达逐点一致：
        # 两臂 y=±off，x∈[0, Lc]；off=(gap+core_w)/2。
        core_w = float(params.get("width", 0.5))
        gap = float(params.get("gap", 0.3))
        Lc = float(params.get("Lc", 10.0))
        off = (gap + core_w) / 2.0
        return {"in1": (0.0, off), "in2": (0.0, -off),
                "out1": (Lc, off), "out2": (Lc, -off)}.get(port, (0.0, 0.0))
    if kind in ("SensingRing", "SensingMZI"):
        # v0.9.210（PS 征程 M1/G4）：端口锚**直接取几何单一真源**
        # `primitives.sensing_window_geometry`（与版图 `sensing_window_descs`
        # 同一函数、同一默认参数）——杜绝「锚点用一套默认值、版图用另一套」
        # 的静默漂移（本版首跑即撞见：wg_width 缺省 0.5 vs 0.45 ⇒ 锚点差 0.025 µm）。
        from lda_l2.primitives import sensing_window_geometry, _sens_p
        sp = _sens_p(kind, params)
        g = sensing_window_geometry(kind, params)
        if kind == "SensingRing":
            half = g["bus_half"]
            off = g["bus_off"]
            return {"in": (-half, -off), "out": (half, -off)}.get(port, (0.0, 0.0))
        Lu, dy = sp["Lu"], sp["dy"]
        return {"in1": (0.0, 0.0), "out1": (Lu, 0.0),
                "in2": (0.0, dy), "out2": (Lu, dy)}.get(port, (0.0, 0.0))
    if kind == "MZI":
        # P0 网格 P&R · 单 MZI 单元局部端口锚（Clements 矩形网格相邻耦合约定）。
        # 局部原点 = 下轨 (rail j) 左端；上轨 (rail j+1) 在 local y=dy（=rail_pitch）。
        # 四端口：in1/out1 在下轨（y=0），in2/out2 在上轨（y=dy）。
        Lu = float(params.get("Lu", 20.0))
        dy = float(params.get("dy", 4.0))   # 下轨→上轨偏移（相邻轨间距）
        return {"in1": (0.0, 0.0), "out1": (Lu, 0.0),
                "in2": (0.0, dy), "out2": (Lu, dy)}.get(port, (0.0, 0.0))
    if kind == "PhaseShifter":
        # 输出相移器（P1-A 物理综合）：短波导段 + 片上加热/载流子相移。
        # 端口 in/out 在局部 (0,0) / (L,0)，与 Waveguide 同向，便于串入 rail 链。
        L = float(params.get("L", 4.0))
        return {"in": (0.0, 0.0), "out": (L, 0.0)}.get(port, (0.0, 0.0))
    if kind == "MMI":
        # 与 primitives.mmi_descs 逐点一致：input=(-L_tap,0)；
        # out1/out2=(L_mmi+L_tap+L_out, ±(w/2+out_gap/2))。
        # v0.9.95 · WDM 网格 P&R：支持 n_out>2 的 1×N 扇出（线性阵列，
        # 居中排布）。N=2 时与旧版逐字节一致（out1=+yo, out2=-yo）。
        w = float(params.get("width", 0.5))
        L = float(params.get("L_mmi", 20.0))
        Lt = float(params.get("L_tap", 4.0))
        gap = float(params.get("out_gap", 0.5))
        Lo = float(params.get("L_out", 3.0))
        yo = w / 2.0 + gap / 2.0
        n_out = int(params.get("n_out", 2))
        if n_out <= 2:
            return {"in": (-Lt, 0.0),
                    "out1": (L + Lt + Lo, yo),
                    "out2": (L + Lt + Lo, -yo)}.get(port, (0.0, 0.0))
        # N>2：out{j}（j=1..N）线性阵列，居中于 y=0
        step = yo * 2.0
        tbl = {"in": (-Lt, 0.0)}
        for j in range(1, n_out + 1):
            tbl[f"out{j}"] = (L + Lt + Lo, (j - (n_out + 1) / 2.0) * step)
        return tbl.get(port, (0.0, 0.0))
    if kind == "MMIC":
        # N×1 合波器（1×N 的镜像）：in1..inN 在左（线性阵列，居中），
        # out 在右（合波输出）。供 WDM 网格 P&R 平面输出端收口用。
        w = float(params.get("width", 0.5))
        L = float(params.get("L_mmi", 20.0))
        Lt = float(params.get("L_tap", 4.0))
        gap = float(params.get("out_gap", 0.5))
        Lo = float(params.get("L_out", 3.0))
        yo = w / 2.0 + gap / 2.0
        n_in = int(params.get("n_in", 2))
        step = yo * 2.0
        tbl = {"out": (Lt, 0.0)}
        for j in range(1, n_in + 1):
            tbl[f"in{j}"] = (-(L + Lt + Lo), (j - (n_in + 1) / 2.0) * step)
        return tbl.get(port, (0.0, 0.0))
    if kind == "SymmetricYBranch":
        # 与 gds_export.geometry_desc 逐点一致：input=(0,0)；
        # 两臂 (tap_len+arm·cos(half), ±arm·sin(half))，half=split_angle/2。
        angle = math.radians(float(params.get("split_angle", 10.0)))
        arm = float(params.get("arm_length", 5.0))
        half = angle / 2.0
        tap_len = min(arm * 0.25, 2.0)
        x0 = tap_len
        return {"in": (0.0, 0.0),
                "out1": (x0 + arm * math.cos(half), arm * math.sin(half)),
                "out2": (x0 + arm * math.cos(half), -arm * math.sin(half))
                }.get(port, (0.0, 0.0))
    if kind == "BraggMirror":
        # 与 primitives.bragg_grating_descs 逐点一致：input=(-L_in,0)；
        # output=(total_len_um - L_in, 0)。段长由 LDA 自有求解器导出，
        # 故惰性调用 bragg_grating_report 取精确末端（避免手写近似值漂移）。
        from lda_l2.primitives import bragg_grating_report as _bgr
        Li = float(params.get("L_in", 2.0))
        try:
            out_x = _bgr(params)["total_len_um"] - Li
        except Exception:
            out_x = 6.0
        return {"in": (-Li, 0.0), "out": (out_x, 0.0)}.get(port, (0.0, 0.0))
    # ── v0.9.178（M2 · G-OI2）：收发器器件端口锚（此前 fallback=(0,0) ────────
    #    ⇒ 收发器 P&R 的 in/out **双双落在器件原点** ⇒ 布线零长、LVS 静默错。
    #    锚点与 `primitives.modulator_descs` / `photodetector_descs` **逐点一致**
    #    （由判据 ⑳「端口锚必须落在版图 bbox 内」守护）。
    if kind == "MziModulator":
        # modulator_descs：双臂矩形 x∈[−arm_L/2, +arm_L/2]，上/下臂中心线 y=±arm_gap/2。
        # 光通路取**上臂**（信号臂）中心线 ⇒ in/out 正落在臂矩形中心。
        La = float(params.get("arm_L", 200.0))
        ag = float(params.get("arm_gap", 4.0))
        y_arm = ag / 2.0
        return {"in": (-La / 2.0, y_arm), "out": (La / 2.0, y_arm)}.get(port, (0.0, 0.0))
    if kind == "Photodetector":
        # photodetector_descs：输入波导 x∈[−8,0]（y=0）→ Ge 吸收区 x∈[0,det_L]。
        Ld = float(params.get("det_L", params.get("L", 20.0)))
        return {"in": (-8.0, 0.0), "out": (Ld, 0.0)}.get(port, (0.0, 0.0))
    # ── v0.9.191（PM 征程 M3）：光子存储单元（PCMCell）端口锚 ────────────────
    # 🔴 **同源**：四个电极 pad 中心由 `primitives.pcm_cell_pads` 给出（与版图
    #    几何 `pcm_cell_descs` 用**同一个函数**），光端口 in/out = 波导两端。
    #    若在此手写坐标，一旦器件几何调整（如 pad 尺寸变化）就会静默错位 ⇒
    #    route 端点悬空 ⇒ LVS 假 open。惰性导入避免加载序耦合。
    if kind == "PCMCell":
        from lda_l2.primitives import pcm_cell_pads as _pads
        L = float(params.get("length", 11.0))
        tbl = {"in": (0.0, 0.0), "out": (L, 0.0)}
        tbl.update({k: (float(v[0]), float(v[1])) for k, v in _pads(params).items()})
        return tbl.get(port, (0.0, 0.0))
    return (0.0, 0.0)


def device_bbox(kind: str, params: dict) -> Tuple[float, float]:
    """器件包围盒半宽半高 (hw,hh) µm（器件原点 0,0）。"""
    R = float(params.get("R", 10.0))
    wg_w = float(params.get("wg_width", 0.5))
    gap = float(params.get("gap", 0.3))
    if kind in ("RingResonator", "RingAddDrop"):
        half = R * 1.5
        off = R + wg_w / 2.0 + gap
        return (half + R * 0.3, off + R * 0.3)
    if kind == "Waveguide":
        length = float(params.get("length", 10.0))
        return (length / 2.0, wg_w)
    if kind == "MZI":
        Lu = float(params.get("Lu", 20.0))
        dy = float(params.get("dy", 4.0))
        return (Lu / 2.0, dy / 2.0 + 2.0)
    if kind == "PhaseShifter":
        L = float(params.get("L", 4.0))
        wg_w = float(params.get("wg", 0.5))
        return (L / 2.0, wg_w / 2.0 + 1.0)
    if kind == "GratingCoupler":
        L = float(params.get("L", 10.0))
        return (max(L / 2.0, 5.0), 5.0)
    # ── v0.9.178（M2 · G-OI2）：收发器器件 bbox（此前 fallback=(5,5)，远小于
    #    调制器 arm_L 的 x 跨度 ⇒ 自动摆放会重叠）。几何量取自同名 descs。
    if kind == "MziModulator":
        La = float(params.get("arm_L", 200.0))
        ag = float(params.get("arm_gap", 4.0))
        w = float(params.get("width", 0.5))
        eg = float(params.get("elec_gap", 1.0))
        ew = float(params.get("elec_w", 3.0))
        return (La / 2.0, ag / 2.0 + w / 2.0 + eg + ew)
    if kind == "Photodetector":
        Ld = float(params.get("det_L", params.get("L", 20.0)))
        Wd = float(params.get("det_w", params.get("W", 5.0)))
        return (max(8.0, Ld) / 2.0 + 4.0, max(wg_w, Wd) / 2.0)
    # ── v0.9.191（PM 征程 M3）：PCM 单元 footprint = 光程长 + 两侧 pad 外扩，
    #    横向 = 加热线中心 + pad 半宽。几何量由 primitives 同源导出（不手写）。
    if kind == "PCMCell":
        from lda_l2.primitives import pcm_cell_geometry as _pg
        L = float(params.get("length", 11.0))
        ps = float(params.get("pad", 4.0))
        g = _pg(params)
        return ((L + ps) / 2.0, g["y_heater_um"] + ps / 2.0)
    return (5.0, 5.0)


def place_row(link: LinkModel, pitch_x: Optional[float] = None,
              origin: Tuple[float, float] = (0.0, 0.0),
              y0: float = 0.0) -> Dict[str, Tuple[float, float, float]]:
    """沿 x 轴等距放置器件实例（按 link.ir.components 顺序）。

    pitch_x 省略时按最大器件半宽自动设定（≥ 2*hw + 余量）。
    返回 {inst: (x, y, rotation)}。
    """
    comps = link.ir.components
    if not comps:
        return {}
    if pitch_x is None:
        max_hw = max(device_bbox(c.kind, dict(c.params))[0] for c in comps)
        pitch_x = 2.0 * max_hw + 8.0
    return {c.id: (origin[0] + i * pitch_x, origin[1] + y0, 0.0)
            for i, c in enumerate(comps)}


def place_2d(link: LinkModel, cols: int = 3,
             origin: Tuple[float, float] = (0.0, 0.0),
             pitch_x: Optional[float] = None,
             pitch_y: Optional[float] = None) -> Dict[str, Tuple[float, float, float]]:
    """2D 网格放置（行优先，器件尺寸感知——第二梯队-2b，审计差距 #3）。

    在 place_row 单行基础上支持多行布局：按 cols 列宽分多行，
    行距/列距由器件包围盒自适应（≥2*hw/hh + 余量），旋转保持 0
    （端口默认左右方向，网格放置与波导布线天然对齐）。

    pitch_x/pitch_y 省略时按最大器件半宽/半高自动设定。
    """
    comps = link.ir.components
    if not comps:
        return {}
    bboxes = {c.id: device_bbox(c.kind, dict(c.params)) for c in comps}
    if pitch_x is None:
        pitch_x = 2.0 * max(hw for hw, _ in bboxes.values()) + 8.0
    if pitch_y is None:
        pitch_y = 2.0 * max(hh for _, hh in bboxes.values()) + 8.0
    cols = max(1, int(cols))
    out = {}
    for i, c in enumerate(comps):
        row, col = divmod(i, cols)
        out[c.id] = (origin[0] + col * pitch_x,
                     origin[1] + row * pitch_y, 0.0)
    return out


def port_abs(inst: str, port: str, placement: dict,
             link: LinkModel) -> Tuple[float, float]:
    """端口绝对坐标 (x,y)。v0.8.39：comp 查找走索引缓存（O(1) 查表）。

    🔴 v0.9.191：`inst` 不在 `link.ir.components` 时**必须 raise** —— 此前静默
    返回 `(ox, oy)`（器件原点，即端口偏移量被丢弃）⇒ 布线端点边界错位、LVS 归属
    到错误端口，而调用方与门禁都看不见（本项目「静默回退」血案同族）。
    """
    ox, oy, _ = placement[inst]
    comp = _port_abs_comp_index(placement, link).get(inst)
    if comp is None:
        raise ValueError(
            "port_abs: 实例 %r 不在 link 内（其端口偏移量无法确定）"
            "—— 拒绝静默回退到器件原点" % (inst,))
    dx, dy = port_anchor(comp.kind, port, dict(comp.params))
    return (ox + dx, oy + dy)
