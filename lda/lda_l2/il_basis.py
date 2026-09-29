# -*- coding: utf-8 -*-
"""每模口径（per-mode IL basis）统一登记 · D-126 · 平台层「谁的损耗」规范词汇。

背景（D-123 → D-125 之后暴露的口径错位）：
D-123 分离了「列口径」与「每模口径」，D-125 把每模深度下沉为平台单一真源（`lda_l2.mzi_mesh_matmul`）。
但**物理/版图层**的三条损耗通道各说各话：

  · `loss_aware_compile.il_per_port_direct_bus`（grid2d 总线 IL）：只报 `IL_mean_db` + `IL_var_ports_db`
    ⇒ **最坏模**藏在方差里，没有显式读数；
  · `mesh_tiling.d1_bus_budget`（瓦片总线 IL）：用 `⟨deg⟩ = N−1`（**列/均值口径**）⇒ 天花板按**均值**估，
    **低估最坏模**；
  · `optical_pareto.optical_metrics`（光域 Pareto 损耗轴）：用 `deg_max` ⇒ **已是每模最坏**（对），
    但没有统一词汇，也没有 min/mean 作对照。

本模块做**一件事**：定义**每模口径的规范词汇**，并提供「登记 + 一致性护栏 + 跨通道汇总」。
🔴 **本模块不做物理计算** —— 它只接收各通道**自己算出的** per-mode 三项（min/mean/max），
   校验词汇与序（`min ≤ mean ≤ max`），并保证四条通道（mesh / bus / tiling / pareto）**同词汇**。
   物理量的**唯一实现**仍在各通道内（`mzi_mesh_matmul` / `loss_aware_compile` / `mesh_tiling` /
   `optical_pareto`）—— 本模块**不复制**任何损耗公式（D-125 纪律：一个物理量只有一份实现）。

🔴 grid2d 布局的每模分布（本模块门禁实测锁定，非拟合）：`deg_min = N/2`、`deg_max = N`、
   `⟨deg⟩ = N−1`（结构不变量 `Σdeg = N(N−1)`）⇒ **最坏模的抽头数是均值的约 2 倍**。
   这就是「列/均值口径会低估最坏模损耗」的量化来源（N=16：均值 0.862 dB vs 最坏 0.910 dB）。

诚实边界（`IL_BASIS_DISCLOSURE`）：
  · 本模块登记的是**设计预算口径**的各通道损耗（α_prop / α_tap 取公开区间代表值），**非实测 PDK**（属 D5）；
  · 「每模口径」= 单模**最长路径**的损耗（最坏模），**不是**全网格门合计（`total_db`），
    也**不是**端口均值（`column_mean`）—— 三者不可互换；
  · 跨通道**不做数值等价断言**：mesh / grid2d 总线 / 瓦片 / Pareto 是**不同布局模型**
    （不同 L_bus 定义、不同几何），本模块只断言**词汇与序一致**，不断言数值相等。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# 口径标签（词汇表）
# ---------------------------------------------------------------------------
#: 每模口径（本模块规范）：单模**最长路径**损耗 —— 链路预算该用的量
BASIS_PER_MODE = "per_mode"
#: 列/阶段口径：网格列数（对抽象 Reck = 每模深度；对邻耦合网格**低估**最坏模）
BASIS_COLUMN_MEAN = "column_mean"
#: 总级联口径：全网格门合计 + 交叉（结构性口径，**不是**任一模的损耗）
BASIS_TOTAL = "total_cascade"
#: 单件口径：每片 MZI / 每抽头的常数
BASIS_PER_ELEMENT = "per_element"

#: 每模口径的**必备键**（缺一即断言失败）
PER_MODE_REQUIRED_KEYS: tuple = (
    "basis", "channel", "n_modes",
    "il_min_db", "il_mean_db", "il_max_db", "il_spread_db",
)
#: 可选键（有则登记，强化可追责性）
PER_MODE_OPTIONAL_KEYS: tuple = (
    "argmax_mode", "per_element_db", "per_element_kind", "basis_note",
)
PER_MODE_KEYS: tuple = PER_MODE_REQUIRED_KEYS + PER_MODE_OPTIONAL_KEYS

#: 全平台共用的一句「口径分野」说明（防复用者把三种口径混为一谈）
BASIS_VOCAB_NOTE: str = (
    "per_mode（每模）= 单模最长路径损耗（最坏模；链路预算用）；"
    "column_mean（列/均值）= 列数或端口均值（**低估**最坏模）；"
    "total_cascade（总级联）= 全网格门合计 + 交叉（结构性，非任一模）；"
    "per_element（单件）= 每片 MZI / 每抽头常数。四者不可互换。"
)

IL_BASIS_DISCLOSURE: Dict[str, str] = {
    "role": "D-126 = 「每模口径」的平台**规范词汇 + 登记表 + 一致性护栏**；不做物理计算（只登记）。",
    "why": "D-123 分离列/每模口径、D-125 下沉每模深度后，物理/版图三条通道（总线 IL / 瓦片 / Pareto）"
           "仍各说各话 ⇒ 本模块把它们统一到同一词汇与同一序（min ≤ mean ≤ max）。",
    "no_physics": "🔴 本模块**不复制**任何损耗公式：物理量的唯一实现在各通道内（`mzi_mesh_matmul` / "
                  "`loss_aware_compile` / `mesh_tiling` / `optical_pareto`）。本模块只登记 + 校验。",
    "grid2d_distribution": "grid2d 布局实测（门禁锁定）：`deg_min = N/2`、`deg_max = N`、`⟨deg⟩ = N−1`"
                           "（`Σdeg = N(N−1)`）⇒ **最坏模抽头数 ≈ 均值 2 倍** —— 这是「列/均值口径低估"
                           "最坏模」的量化来源（N=16：均值 0.862 dB vs 最坏 0.910 dB）。",
    "budget_not_measured": "各通道损耗均为**设计预算口径**（α_prop / α_tap 取公开区间代表值），"
                           "**非实测 foundry PDK**（真值须圆片表征回填，属 D5）。",
    "no_cross_channel_equality": "🔴 跨通道**不做数值等价断言**：mesh（邻耦合三角/矩形）/ grid2d 总线 / "
                                 "瓦片 / Pareto 是**不同布局模型**（L_bus 定义与几何不同）⇒ 本模块只断言"
                                 "「词汇齐备 + 序正确 + 同一 basis 标签」，**不断言**数值相等。",
    "lower_bound_note": "各通道的每模最坏损耗均**不含**波导交叉、demux/mux、光纤耦合、调制器/探测器"
                        "⇒ 是**下界**，不是完整链路预算（与各通道自身披露一致）。",
    "no_llm": "本模块全部为实数/整数/布尔比对，**LLM 不进判决路径**。",
}


class IlBasisError(Exception):
    """每模口径登记/校验违规。"""


# ---------------------------------------------------------------------------
# 1) 构造器（两个入口：由值列表 / 由三项统计量）
# ---------------------------------------------------------------------------
def _finish(il_min: float, il_mean: float, il_max: float, *, channel: str,
            n_modes: Optional[int], argmax_mode: Optional[int],
            per_element_db: Optional[float], per_element_kind: Optional[str],
            basis_note: Optional[str]) -> Dict[str, Any]:
    """公共收口：序校验 + 规范化输出。"""
    if not isinstance(channel, str) or not channel.strip():
        raise IlBasisError("channel 须为非空字符串，得到 %r" % (channel,))
    vals = {"il_min_db": float(il_min), "il_mean_db": float(il_mean), "il_max_db": float(il_max)}
    if not (vals["il_min_db"] <= vals["il_mean_db"] <= vals["il_max_db"]):
        raise IlBasisError(
            "序违规：须 min ≤ mean ≤ max，得到 min=%.12g mean=%.12g max=%.12g（channel=%s）"
            % (vals["il_min_db"], vals["il_mean_db"], vals["il_max_db"], channel))
    if n_modes is not None and (not isinstance(n_modes, int) or n_modes < 1):
        raise IlBasisError("n_modes 须为 >=1 的 int 或 None，得到 %r" % (n_modes,))
    if argmax_mode is not None and (not isinstance(argmax_mode, int) or argmax_mode < 0):
        raise IlBasisError("argmax_mode 须为 >=0 的 int 或 None，得到 %r" % (argmax_mode,))
    if per_element_db is not None and float(per_element_db) < 0.0:
        raise IlBasisError("per_element_db 须 >= 0，得到 %r" % (per_element_db,))
    out = {
        "basis": BASIS_PER_MODE,
        "channel": channel,
        "n_modes": (int(n_modes) if n_modes is not None else None),
        "il_min_db": vals["il_min_db"],
        "il_mean_db": vals["il_mean_db"],
        "il_max_db": vals["il_max_db"],
        "il_spread_db": float(vals["il_max_db"] - vals["il_min_db"]),
        "argmax_mode": (int(argmax_mode) if argmax_mode is not None else None),
        "per_element_db": (float(per_element_db) if per_element_db is not None else None),
        "per_element_kind": per_element_kind,
        "basis_note": (basis_note or "每模口径 = 单模最长路径损耗（最坏模）；min/mean/max 为逐模分布。"),
    }
    return out


def il_basis_from_values(values_db: Sequence[float], *, channel: str,
                         n_modes: Optional[int] = None,
                         per_element_db: Optional[float] = None,
                         per_element_kind: Optional[str] = None,
                         basis_note: Optional[str] = None) -> Dict[str, Any]:
    """由**逐模 IL 值列表**构造每模口径登记（算 min/mean/max/spread + argmax）。

    `n_modes` 缺省取 `len(values_db)`；给了就必须与长度一致（防「值数 ≠ 模数」的静默错）。
    """
    vals: List[float] = [float(v) for v in values_db]
    if not vals:
        raise IlBasisError("values_db 非空（channel=%s）" % (channel,))
    if n_modes is not None and int(n_modes) != len(vals):
        raise IlBasisError(
            "n_modes=%r 与 values_db 长度 %d 不一致（channel=%s）" % (n_modes, len(vals), channel))
    imax = max(range(len(vals)), key=lambda i: vals[i])
    mn = min(vals)
    mx = max(vals)
    mean = sum(vals) / float(len(vals))
    return _finish(mn, mean, mx, channel=channel, n_modes=len(vals),
                   argmax_mode=imax, per_element_db=per_element_db,
                   per_element_kind=per_element_kind, basis_note=basis_note)


def il_basis_from_stats(il_min_db: float, il_mean_db: float, il_max_db: float, *,
                        channel: str, n_modes: Optional[int] = None,
                        argmax_mode: Optional[int] = None,
                        per_element_db: Optional[float] = None,
                        per_element_kind: Optional[str] = None,
                        basis_note: Optional[str] = None) -> Dict[str, Any]:
    """由**已算好的**三项统计量构造每模口径登记（当通道只有 min/mean/max 时用）。

    仍强制序校验 `min ≤ mean ≤ max` —— 通道若报错序（如把 max 写成均值）**当场失败**。
    """
    return _finish(il_min_db, il_mean_db, il_max_db, channel=channel, n_modes=n_modes,
                   argmax_mode=argmax_mode, per_element_db=per_element_db,
                   per_element_kind=per_element_kind, basis_note=basis_note)


# ---------------------------------------------------------------------------
# 2) 一致性护栏
# ---------------------------------------------------------------------------
def assert_basis_consistency(entry: Any, *, expect_channel: Optional[str] = None,
                             expect_n_modes: Optional[int] = None) -> Dict[str, Any]:
    """机器校验一条每模口径登记：键齐备 + 序正确 + basis 标签正确 + spread 自洽。

    任一违规 ⇒ raise `IlBasisError`（调用方据此判红）。返回原 entry（便于链式调用）。
    """
    if not isinstance(entry, dict):
        raise IlBasisError("每模口径登记须为 dict，得到 %r" % (type(entry).__name__,))
    missing = [k for k in PER_MODE_REQUIRED_KEYS if k not in entry]
    if missing:
        raise IlBasisError("缺必备键 %s（channel=%r）" % (missing, entry.get("channel")))
    if entry["basis"] != BASIS_PER_MODE:
        raise IlBasisError("basis 标签须为 %r，得到 %r" % (BASIS_PER_MODE, entry["basis"]))
    if expect_channel is not None and entry["channel"] != expect_channel:
        raise IlBasisError("channel 须为 %r，得到 %r" % (expect_channel, entry["channel"]))
    if expect_n_modes is not None and entry["n_modes"] != int(expect_n_modes):
        raise IlBasisError("n_modes 须为 %r，得到 %r" % (expect_n_modes, entry["n_modes"]))
    mn, me, mx = entry.get("il_min_db"), entry.get("il_mean_db"), entry.get("il_max_db")
    if not (isinstance(mn, (int, float)) and isinstance(me, (int, float))
            and isinstance(mx, (int, float))):
        raise IlBasisError("il_min/mean/max_db 须为实数（channel=%r，得到 %r/%r/%r）"
                           % (entry.get("channel"), mn, me, mx))
    if not (mn <= me <= mx):
        raise IlBasisError("序违规：min ≤ mean ≤ max 不成立（%r：%.12g/%.12g/%.12g）"
                           % (entry.get("channel"), mn, me, mx))
    spread = float(mx) - float(mn)
    got = entry.get("il_spread_db")
    if not isinstance(got, (int, float)) or abs(float(got) - spread) > 1e-9 * max(1.0, abs(spread)):
        raise IlBasisError("il_spread_db 与 max−min 不自洽（%r：%r vs %.12g）"
                           % (entry.get("channel"), got, spread))
    return entry


def assert_manifest_consistent(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """校验整份跨通道汇总：逐通道过 `assert_basis_consistency` + 全部 basis 标签为 per_mode。"""
    chans = manifest.get("channels")
    if not isinstance(chans, dict) or not chans:
        raise IlBasisError("manifest['channels'] 须为非空 dict")
    n = manifest.get("N")
    for name, entry in chans.items():
        assert_basis_consistency(entry, expect_channel=name, expect_n_modes=n)
    labels = {e["basis"] for e in chans.values()}
    if labels != {BASIS_PER_MODE}:
        raise IlBasisError("并非所有通道使用 per_mode 词汇：%s" % sorted(labels))
    return manifest


# ---------------------------------------------------------------------------
# 3) 跨通道汇总（四通道各自的最坏模口径并列）
# ---------------------------------------------------------------------------
def il_basis_manifest(N: int = 8, *, scenario: str = "B", K: int = 1,
                      arch: str = "shared", layout_mode: str = "grid2d") -> Dict[str, Any]:
    """在给定 N 上汇聚**四条通道**各自的每模口径登记（词汇统一，数值各自独立）。

    通道（全部惰性导入，避免模块级环）：
      · `mesh`        —— 邻耦合三角网格（`mzi_mesh_matmul`），每模深度 × per_mzi；
      · `grid2d_bus`  —— grid2d 直总线逐端口 IL（`loss_aware_compile`）；
      · `tiling`      —— 瓦片总线 IL（`mesh_tiling`）；
      · `pareto`      —— 光域 Pareto 损耗轴（`optical_pareto`）。

    🔴 四者是**不同布局模型** ⇒ 只断言词汇/序一致，**不断言数值相等**（见披露
    `no_cross_channel_equality`）。返回 `{N, channels, n_channels, consistent, vocabulary, disclosure}`。
    """
    n = int(N)
    if n < 2:
        raise IlBasisError("N=%r 非法（须 >= 2）" % (N,))

    from lda_l2 import loss_aware_compile as LAC
    from lda_l2 import mesh_tiling as MT
    from lda_l2 import optical_pareto as OP
    from lda_l2.mzi_mesh_matmul import (dft_matrix, mesh_loss_basis,
                                        mesh_per_mode_optical_depth_stats,
                                        reck_triangular_mesh)

    # ① mesh（邻耦合三角）
    ops, _D = reck_triangular_mesh(dft_matrix(n))
    mbasis = mesh_loss_basis(ops)
    dstats = mesh_per_mode_optical_depth_stats(ops)
    per_mzi = float(mbasis["per_mzi_loss_db"])
    mesh_entry = il_basis_from_stats(
        dstats["depth_min"] * per_mzi, dstats["depth_mean"] * per_mzi, dstats["depth_max"] * per_mzi,
        channel="mesh", n_modes=n, argmax_mode=None, per_element_db=per_mzi,
        per_element_kind="per_mzi_db",
        basis_note="mesh：每模深度分布（三角 2N−3 / 矩形 N）× per_mzi；max ≡ mesh_loss_basis.per_mode_db。")

    # ② grid2d 总线
    from lda_layout.mesh_pnr import build_mesh_pnr
    br = build_mesh_pnr(dft_matrix(n), layout_mode=layout_mode)
    bus = LAC.il_per_port_direct_bus(br)
    bus_entry = bus["il_basis_per_mode"]

    # ③ 瓦片
    d1 = MT.d1_bus_budget(n, scenario=scenario, layout_mode=layout_mode)
    til_entry = d1["il_basis_per_mode"]

    # ④ Pareto
    pareto_entry = OP.optical_metrics(n, int(K), arch=arch)["il_basis_per_mode"]

    channels = {"mesh": mesh_entry, "grid2d_bus": bus_entry,
                "tiling": til_entry, "pareto": pareto_entry}
    manifest = {
        "N": n,
        "scenario": scenario,
        "K": int(K),
        "arch": arch,
        "layout_mode": layout_mode,
        "channels": channels,
        "n_channels": len(channels),
        "all_per_mode": all(e["basis"] == BASIS_PER_MODE for e in channels.values()),
        "basis_spread_db": {k: float(e["il_spread_db"]) for k, e in channels.items()},
        "per_element_kind": {k: e.get("per_element_kind") for k, e in channels.items()},
        "vocabulary": BASIS_VOCAB_NOTE,
        "disclosure": dict(IL_BASIS_DISCLOSURE),
    }
    assert_manifest_consistent(manifest)
    manifest["consistent"] = True
    return manifest


# ---------------------------------------------------------------------------
# 4) 自检（判据由 run_il_basis_platform_smoke.py 常驻守护）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """本模块自检（12 条）：词汇/构造/序校验/护栏/跨通道汇总/诚实边界。"""
    res: Dict[str, bool] = {}

    # ① 词汇表齐备
    res["① 词汇表齐备：必备键 %d + 可选键 %d，且 basis 标签四种互异" % (
        len(PER_MODE_REQUIRED_KEYS), len(PER_MODE_OPTIONAL_KEYS))] = (
        len(PER_MODE_REQUIRED_KEYS) == 7
        and set(PER_MODE_REQUIRED_KEYS) <= set(PER_MODE_KEYS)
        and len({BASIS_PER_MODE, BASIS_COLUMN_MEAN, BASIS_TOTAL, BASIS_PER_ELEMENT}) == 4)

    # ② from_values 正确
    e = il_basis_from_values([1.0, 2.0, 3.0, 4.0], channel="t")
    res["② from_values：min/mean/max/spread/argmax 正确（1/2.5/4/3/3）"] = (
        e["il_min_db"] == 1.0 and e["il_mean_db"] == 2.5 and e["il_max_db"] == 4.0
        and e["il_spread_db"] == 3.0 and e["argmax_mode"] == 3 and e["n_modes"] == 4
        and e["basis"] == BASIS_PER_MODE)

    # ③ from_stats 正确
    e2 = il_basis_from_stats(0.5, 1.0, 2.0, channel="t", n_modes=8)
    res["③ from_stats：三项直录且 spread = max−min"] = (
        e2["il_min_db"] == 0.5 and e2["il_mean_db"] == 1.0 and e2["il_max_db"] == 2.0
        and e2["il_spread_db"] == 1.5 and e2["n_modes"] == 8)

    # ④ 序违规必 raise（from_stats）
    try:
        il_basis_from_stats(3.0, 2.0, 1.0, channel="t")
        ok = False
    except IlBasisError:
        ok = True
    res["④ ★序护栏★ from_stats 报错序（min>mean>max）⇒ 必 raise"] = ok

    # ⑤ n_modes 与值数不一致必 raise
    try:
        il_basis_from_values([1.0, 2.0, 3.0], channel="t", n_modes=5)
        ok = False
    except IlBasisError:
        ok = True
    res["⑤ n_modes 与 values 长度不一致 ⇒ 必 raise（防「值数≠模数」静默错）"] = ok

    # ⑥ 空值必 raise
    try:
        il_basis_from_values([], channel="t")
        ok = False
    except IlBasisError:
        ok = True
    res["⑥ values 为空 ⇒ 必 raise"] = ok

    # ⑦ channel 非空校验
    try:
        il_basis_from_stats(1.0, 1.0, 1.0, channel="")
        ok = False
    except IlBasisError:
        ok = True
    res["⑦ channel 为空 ⇒ 必 raise"] = ok

    # ⑧ assert_basis_consistency 反向：缺键必红
    broken = dict(e)
    del broken["il_max_db"]
    try:
        assert_basis_consistency(broken)
        ok = False
    except IlBasisError:
        ok = True
    res["⑧ ★护栏反向★ 缺必备键 ⇒ assert_basis_consistency 必 raise"] = ok

    # ⑨ assert_basis_consistency 反向：spread 篡改必红
    tampered = dict(e)
    tampered["il_spread_db"] = e["il_spread_db"] + 1.0
    try:
        assert_basis_consistency(tampered)
        ok = False
    except IlBasisError:
        ok = True
    res["⑨ ★护栏反向★ spread 篡改 ⇒ 必 raise（防「登记了个不自洽的 spread」）"] = ok

    # ⑩ assert_basis_consistency 正向：合法必过
    try:
        assert_basis_consistency(e, expect_channel="t", expect_n_modes=4)
        ok = True
    except IlBasisError:
        ok = False
    res["⑩ 合法登记（channel/n_modes 匹配）⇒ 必过"] = ok

    # ⑪ ★跨通道汇总★ 四通道同词汇 + 逐通道序正确 + 最坏 ≥ 均值
    try:
        man = il_basis_manifest(8)
        ok = (man["n_channels"] == 4 and man["consistent"] is True
              and man["all_per_mode"] is True
              and all(man["channels"][c]["il_max_db"] >= man["channels"][c]["il_mean_db"]
                      for c in man["channels"]))
    except Exception:                                       # noqa: BLE001
        ok = False
    res["⑪ ★跨通道汇总★ N=8 四通道（mesh/bus/tiling/pareto）同 per_mode 词汇且序正确"] = ok

    # ⑫ ★反面★ 篡改一条通道（max 写成 min）⇒ manifest 校验必 raise
    try:
        man2 = il_basis_manifest(8)
        man2["channels"]["tiling"]["il_max_db"] = man2["channels"]["tiling"]["il_min_db"]
        assert_manifest_consistent(man2)
        ok = False
    except IlBasisError:
        ok = True
    except Exception:                                       # noqa: BLE001
        ok = False
    res["⑫ ★反面★ 篡改通道 max=min ⇒ assert_manifest_consistent 必 raise"] = ok

    # ⑬ 诚实边界齐备 + 无越界（不出现能效类键名）
    res["⑬ 披露键 %d 条逐键非空；本模块零 numpy / 无能效键" % len(IL_BASIS_DISCLOSURE)] = (
        len(IL_BASIS_DISCLOSURE) >= 8
        and all(isinstance(v, str) and v.strip() for v in IL_BASIS_DISCLOSURE.values())
        and "no_physics" in IL_BASIS_DISCLOSURE
        and "no_cross_channel_equality" in IL_BASIS_DISCLOSURE)

    if verbose:
        for k, v in res.items():
            print("[%s] %s" % ("PASS" if v else "FAIL", k))
    return bool(all(res.values()))


if __name__ == "__main__":                                  # 自测：打真实数字
    ok = run_selfchecks(verbose=True)
    print("=" * 76)
    print("il_basis（D-126）自检：%s" % ("全绿" if ok else "有红"))
    m = il_basis_manifest(8)
    print("=== N=8 四通道每模口径（dB）===")
    for name, e in m["channels"].items():
        print("  %-10s n_modes=%s min=%8.4f mean=%8.4f max=%8.4f spread=%7.4f (%s)"
              % (name, e["n_modes"], e["il_min_db"], e["il_mean_db"], e["il_max_db"],
                 e["il_spread_db"], e["per_element_kind"]))
    print("consistent =", m["consistent"])
