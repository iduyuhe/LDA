"""E32（D-207）· 版图几何的**空间索引** —— 把 DRC/LVS 从 O(N⁴) 降到可用。

## 为什么需要这个模块

E31 实测 `run_edrc` + `elvs_signoff` 的耗时（AP 路径 · 含 via stack）：

| N | 元素数 | 耗时 | 相对 N=4 |
|---|---|---|---|
| 4 | 312 | 0.02 s | 1× |
| 8 | 1,232 | 0.22 s | 11× |
| 12 | 2,760 | 1.08 s | 54× |
| 16 | 4,896 | 3.37 s | 168× |
| **24** | **10,992** | **17.04 s** | 852× |
| 87 | ~140,000 | **估 ~7 h** | 外推 |

⇒ `N=87` 的几何**从未被真正 DRC 验过**（E31 §7 诚实边界第 4 条）。

**根因**（v0.9.327 实测 profile）：`_overlap` 被调用 **1128 万次**（`run_edrc`）与
**1157 万次**（`elvs_signoff`），元素数 4,896 ⇒ `n²/2 ≈ 1200 万`，**正好对上**。
四处检查全是**全对全 O(n²) 配对**，而元素数 ∝ N² ⇒ 总复杂度 **O(N⁴)**。

## 本模块做什么 / 不做什么

**做**：提供两个**候选筛选**原语，把 O(n²) 的配对降为 O(n + 邻近对数)：

- `Grid.query(bbox, expand)` → 与 `bbox` 在**两轴都 ≤ expand** 的候选索引（**超集**）
- `Grid.near_pairs(expand)` → 所有候选对

**不做**：**不替代 `_overlap` / `_gap`**。本模块只负责"谁需要被检查"，
"是否真的违规"仍由调用方用**原来的 `_overlap` / `_gap` 判定**。
⇒ 这样新实现与旧实现在**语义上逐位等价**（候选是超集，最终判定用同一个函数）。

🔴 这是 E32 的核心设计纪律：**索引只能缩小搜索范围，不能改变判定谓词**。
若索引也参与判定，就会出现「新旧结果不一致但不知道谁对」的死局。

## 长元素（oversized）单独处理

行线/列线是**横贯整个阵列的超长条**（跨度 ∝ N），若也放进网格，每条会占 O(N) 个格
⇒ 退化成 O(n²)。故：

- bbox 跨度 ≤ `max_cell_cross` 个格 ⇒ 走网格
- 否则 ⇒ 放进 `oversized` 列表，查询时**对全部 oversized 线性扫**

同一个阵列里 oversized 只有 N 条（行线或列线），
故 `oversized × all` = `N × N²` = **O(N³)**，已比 O(N⁴) 低一整个 N。

## 超集保证（可机核）

- **相交筛选**：`_overlap(a,b)` 为真 ⇒ 两 bbox 有公共点 ⇒ 必然共享至少一个格
  ⇒ 网格查询返回的候选**包含**全部相交对。
- **间距筛选**：`_gap(a,b) < expand` ⇒ 两 bbox 至少一个轴的间隙 < expand
  ⇒ 把 bbox **外扩 expand** 后必相交 ⇒ 用外扩后的 bbox 查询即可。

两条都由门禁的**对拍**（新 ⟷ 旧 逐条相等）实证，而不是靠这段论证。
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

_Bbox = Tuple[float, float, float, float]

#: 输出档（与 `energy.OUTPUT_TIER` 一致；此处不 import 以免循环依赖）
TIER = "MODEL_ESTIMATE"

#: 模块级缓存（parity 会跑旧实现、scale 会跑到 N=87 ⇒ 不缓存则门禁重复付两次）
_CACHE: Dict[str, object] = {}


def _cached(key: str, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def _span(b: _Bbox, axis: int) -> float:
    return b[2 * axis + 1] - b[2 * axis]


def _dim(a: float, b: float) -> int:
    """坐标 → 格索引。用 `floor` 而非 `int()`：负数坐标下 `int()` 会向 0 取整而错格。"""
    return int(math.floor(a / b)) if b > 0 else 0


class Grid:
    """均匀网格索引（bbox 候选筛选）。

    `cell_um` 缺省按 bbox 尺寸中位数自动定（`auto_cell`），
    过小 ⇒ 每个元素占多格；过大 ⇒ 每格元素过多。取中位数 ×2 是常见折中。

    `max_cell_cross`：单个元素跨格数超过它就归入 `oversized`（防长条退化）。
    """

    def __init__(self, boxes: Sequence[_Bbox],
                 cell_um: Optional[float] = None,
                 max_cell_cross: int = 64):
        self.boxes: List[_Bbox] = list(boxes)
        self.n = len(self.boxes)
        self.max_cell_cross = int(max_cell_cross)
        self.cell_um = float(cell_um) if cell_um else self._auto_cell()
        self.buckets: Dict[Tuple[int, int], List[int]] = {}
        self.oversized: List[int] = []
        self._build()

    # -- 构建 ---------------------------------------------------------------
    def _auto_cell(self) -> float:
        if self.n == 0:
            return 1.0
        spans = []
        for b in self.boxes:
            spans.append(max(_span(b, 0), _span(b, 1)))
        spans.sort()
        med = spans[len(spans) // 2]
        # 中位数为 0（退化元素）时退回整体跨度 / 64
        if med <= 0:
            xs = [b[1] for b in self.boxes] + [b[0] for b in self.boxes]
            span = max(xs) - min(xs)
            return max(span / 64.0, 1e-9)
        return max(med * 2.0, 1e-9)

    def _cells(self, b: _Bbox) -> List[Tuple[int, int]]:
        i0, i1 = _dim(b[0], self.cell_um), _dim(b[1], self.cell_um)
        j0, j1 = _dim(b[2], self.cell_um), _dim(b[3], self.cell_um)
        return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]

    def _build(self) -> None:
        for idx, b in enumerate(self.boxes):
            cells = self._cells(b)
            if len(cells) > self.max_cell_cross:
                self.oversized.append(idx)      # 长条：不进网格
                continue
            for key in cells:
                self.buckets.setdefault(key, []).append(idx)

    # -- 查询 ---------------------------------------------------------------
    def query(self, b: _Bbox, expand: float = 0.0) -> List[int]:
        """与 `b` 在**两轴都 ≤ expand** 的候选索引（**超集**，含 `b` 自身若在集合内）。"""
        eb = (b[0] - expand, b[1] + expand, b[2] - expand, b[3] + expand)
        out: List[int] = []
        seen = set()
        for key in self._cells(eb):
            for idx in self.buckets.get(key, ()):
                if idx in seen:
                    continue
                seen.add(idx)
                c = self.boxes[idx]
                # 用**外扩后的 bbox** 做一次廉价的两轴剪枝（精确判定仍交给调用方）
                if (c[1] < eb[0] - 1e-12 or c[0] > eb[1] + 1e-12
                        or c[3] < eb[2] - 1e-12 or c[2] > eb[3] + 1e-12):
                    continue
                out.append(idx)
        for idx in self.oversized:
            if idx in seen:
                continue
            c = self.boxes[idx]
            if (c[1] < eb[0] - 1e-12 or c[0] > eb[1] + 1e-12
                    or c[3] < eb[2] - 1e-12 or c[2] > eb[3] + 1e-12):
                continue
            out.append(idx)
        return out

    def near_pairs(self, expand: float = 0.0) -> List[Tuple[int, int]]:
        """所有可能邻近的元素对 `(i, j)`（`i < j`，**超集**）。"""
        pairs: List[Tuple[int, int]] = []
        seen = set()

        def _push(i: int, j: int) -> None:
            if i == j:
                return
            key = (i, j) if i < j else (j, i)
            if key in seen:
                return
            seen.add(key)
            pairs.append(key)

        # ① 网格内：每格内两两 + 查询（格内两两已覆盖跨格情形，用 query 保证不漏）
        for idx, b in enumerate(self.boxes):
            if idx in self.oversized:
                continue
            for other in self.query(b, expand):
                _push(idx, other)

        # ② oversized × 全体（长条：线性扫，条数 = O(N) 故可接受）
        for idx in self.oversized:
            b = self.boxes[idx]
            for other in range(self.n):
                if other == idx or other in self.oversized and other < idx:
                    continue
                _o = self.boxes[other]
                if (b[1] + expand < _o[0] - 1e-12 or _o[1] + expand < b[0] - 1e-12
                        or b[3] + expand < _o[2] - 1e-12 or _o[3] + expand < b[2] - 1e-12):
                    continue
                _push(idx, other)
        return pairs


def near_pairs(boxes: Sequence[_Bbox], expand: float = 0.0,
               cell_um: Optional[float] = None) -> List[Tuple[int, int]]:
    """便捷函数：`Grid(boxes).near_pairs(expand)`。"""
    if not boxes:
        return []
    return Grid(boxes, cell_um=cell_um).near_pairs(expand)


def brute_pairs(boxes: Sequence[_Bbox], expand: float = 0.0) -> List[Tuple[int, int]]:
    """**暴力超集**（对拍用）：返回所有两轴都在 `expand` 内的对。

    复杂度 O(n²)，只用于门禁里证明「索引没有漏掉任何对」。
    """
    n = len(boxes)
    out: List[Tuple[int, int]] = []
    for i in range(n):
        a = boxes[i]
        for j in range(i + 1, n):
            b = boxes[j]
            if (a[1] + expand < b[0] - 1e-12 or b[1] + expand < a[0] - 1e-12
                    or a[3] + expand < b[2] - 1e-12 or b[3] + expand < a[2] - 1e-12):
                continue
            out.append((i, j))
    return out


# ---------------------------------------------------------------------------
# 对拍：新实现 ⟷ 旧实现（v0.9.327 的全对全版本）
# ---------------------------------------------------------------------------
def _sig_drc(d: Dict) -> tuple:
    return (d["verdict"], tuple(sorted((v["rule"], v["detail"]) for v in d["violations"])))


def _sig_lvs(v: Dict) -> tuple:
    return (v["verdict"], tuple(sorted(v["issues"])))


#: 对拍案例：**必须同时含 ACCEPT 与 REJECT**。
#   🔴 只对拍 ACCEPT 案例等于「空集 == 空集」，证明不了违规路径也一致（E31 的教训）。
PARITY_CASES = (
    # (标签, N, params, row_layer, via_stack, 用 16 层栈)
    ("M1 基准 ACCEPT", 8, None, "M1", False, False),
    ("M1 R=0.55 间距 REJECT", 8, {"row_w_um": 0.55}, "M1", False, False),
    ("M1 R=0.60 间距 REJECT", 12, {"row_w_um": 0.60}, "M1", False, False),
    ("AP+栈 ACCEPT", 8, {"row_w_um": 1.60, "pitch_y_um": 3.20}, "AP", True, True),
    ("AP W=0.40 宽度 REJECT", 8, None, "AP", True, True),
    ("AP 无栈 悬空 REJECT", 8, {"row_w_um": 1.60, "pitch_y_um": 3.20}, "AP", False, True),
    ("M2 行线 短路 REJECT", 8, None, "M2", True, True),
    ("M6+栈 ACCEPT", 12, None, "M6", True, True),
    ("M3+栈 ACCEPT", 12, None, "M3", True, True),
)


def parity_matrix() -> List[Dict]:
    """逐个案例跑**新旧两条路径**并对拍（`verdict` + 违规/issue **集合**）。

    🔴 集合而非列表：旧实现的顺序是 `a<b` 字典序、新实现是格遍历顺序，
    **顺序不同不代表错**。正确性标准是「违规集合相同」。
    """
    return _cached("parity", _parity_matrix_impl)


def _parity_matrix_impl() -> List[Dict]:
    from lda_l2.ecore import layout as LY
    from lda_l2.ecore import elayers as EL

    rows: List[Dict] = []
    for label, n, prm, rl, vs, deep in PARITY_CASES:
        st = EL.get_estack("ecmos10") if deep else None
        arr = LY.crossbar_array(n, n, prm, row_layer=rl, via_stack=vs)
        exp = LY.expected_netlist(n, n, arr["params"])
        do = LY.run_edrc(arr["descs"], stack=st, spatial=False)
        dn = LY.run_edrc(arr["descs"], stack=st, spatial=True)
        lo = LY.elvs_signoff(arr["descs"], exp, stack=st, spatial=False)
        ln = LY.elvs_signoff(arr["descs"], exp, stack=st, spatial=True)
        rows.append({
            "label": label, "n": n, "n_elements": len(arr["descs"]),
            "drc_old": do["verdict"], "drc_new": dn["verdict"],
            "lvs_old": lo["verdict"], "lvs_new": ln["verdict"],
            "n_viol": len(dn["violations"]), "n_issue": len(ln["issues"]),
            "drc_equal": _sig_drc(do) == _sig_drc(dn),
            "lvs_equal": _sig_lvs(lo) == _sig_lvs(ln),
        })
    return rows


def parity_summary() -> Dict:
    rows = parity_matrix()
    bad = [r for r in rows if not (r["drc_equal"] and r["lvs_equal"])]
    n_rej = sum(1 for r in rows if r["drc_new"] == "REJECT" or r["lvs_new"] == "REJECT")
    return {
        "rows": rows, "n_cases": len(rows), "n_mismatch": len(bad),
        "n_reject_cases": n_rej,
        "all_equal": not bad,
        "verdict": ("🔴 %d 个案例（含 **%d 个 REJECT**）新旧**逐条一致**（verdict + 违规集合）"
                    % (len(rows), n_rej) if not bad else
                    "🔴 **%d 个案例不一致**：%s" % (len(bad),
                                                "、".join(r["label"] for r in bad))),
        "tier": TIER,
    }


# ---------------------------------------------------------------------------
# 规模表：新实现能跑到 N=87（旧实现要 ~7 h）
# ---------------------------------------------------------------------------
#: 规模表用的 (N, 预期耗时上界 s)；**不含旧实现**（N≥24 时旧实现单点 >17 s，门禁不可跑）
SCALE_NS = (8, 16, 24, 42, 87)

#: v0.9.327（旧实现）的实测 / 外推耗时，用于对照
LEGACY_TIMES_S = {8: 0.22, 16: 3.37, 24: 17.51, 42: None, 87: None}


def scale_table(ns: Optional[Sequence[int]] = None) -> List[Dict]:
    """各规模的 DRC+LVS 耗时（**只跑新实现**）与相对旧实现的加速比。"""
    from lda_l2.ecore import elayers as EL

    st = EL.get_estack("ecmos10")
    prm = {"row_w_um": 1.60, "pitch_y_um": 3.20}
    _ns = tuple(ns or SCALE_NS)
    return _cached("scale_%s" % (_ns,), lambda: _scale_impl(_ns, st, prm))


def _scale_impl(ns: Sequence[int], st, prm: Dict) -> List[Dict]:
    import time as _t

    from lda_l2.ecore import layout as LY

    rows: List[Dict] = []
    for n in ns:
        arr = LY.crossbar_array(n, n, prm, row_layer="AP", via_stack=True)
        exp = LY.expected_netlist(n, n, arr["params"])
        t0 = _t.perf_counter()
        drc = LY.run_edrc(arr["descs"], stack=st)
        lvs = LY.elvs_signoff(arr["descs"], exp, stack=st)
        dt = _t.perf_counter() - t0
        old = LEGACY_TIMES_S.get(n)
        rows.append({
            "n": n, "n_elements": len(arr["descs"]), "elapsed_s": dt,
            "drc": drc["verdict"], "lvs": lvs["verdict"],
            "legacy_s": old,
            "speedup": (old / dt) if old else None,
        })
    return rows


def scale_summary() -> Dict:
    rows = scale_table()
    big = rows[-1]
    ok_all = all(r["drc"] == "ACCEPT" and r["lvs"] == "ACCEPT" for r in rows)
    # 经验复杂度：N 加倍时耗时的指数
    a, b = rows[2], rows[-1]          # 24 → 87
    expo = (math.log(b["elapsed_s"] / a["elapsed_s"])
            / math.log(b["n"] / a["n"])) if a["elapsed_s"] > 0 else float("nan")
    return {
        "rows": rows, "all_accept": ok_all,
        "n_max_verified": big["n"], "elapsed_max_s": big["elapsed_s"],
        "empirical_exponent": expo,
        "verdict": ("🔴 **N=%d（%s 元素）DRC+LVS 合计 %.2f s · 全 ACCEPT** —— "
                    "E31 曾外推 ~7 h（**快约 %.0f×**）· 经验复杂度 N^%.2f（旧实现是 N^4）"
                    % (big["n"], format(big["n_elements"], ","), big["elapsed_s"],
                       7 * 3600 / max(big["elapsed_s"], 1e-9), expo)),
        "tier": TIER,
    }


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def spatial_self_check(verbose: bool = False) -> bool:
    """`spatial` 模块自检（不依赖 layout，全是纯几何谓词）。"""
    from lda_l2.ecore import layout as LY

    checks: List[tuple] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append((bool(cond), name, detail))
        if verbose:
            print(("[OK] " if cond else "[NG] ") + name + (("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① 空输入
    ok &= chk("① 空输入 ⇒ 无对、不抛（防恒真/恒红）",
              near_pairs([]) == [] and brute_pairs([]) == [])

    # ② 单元素
    one = [(0.0, 1.0, 0.0, 1.0)]
    ok &= chk("② 单元素 ⇒ 无对", near_pairs(one) == [] and brute_pairs(one) == [])

    # ③ 两个分离元素 ⇒ 无对
    far = [(0.0, 1.0, 0.0, 1.0), (10.0, 11.0, 10.0, 11.0)]
    ok &= chk("③ 两个远离的元素 ⇒ 无对（网格不能凭空造对）",
              near_pairs(far) == [] and brute_pairs(far) == [])

    # ④ 两个相交元素 ⇒ 有对
    near2 = [(0.0, 1.0, 0.0, 1.0), (0.5, 1.5, 0.5, 1.5)]
    ok &= chk("④ 两个相交元素 ⇒ 有对", near_pairs(near2) == brute_pairs(near2) == [(0, 1)])

    # ⑤ expand 让"近而不交"变成对
    gap2 = [(0.0, 1.0, 0.0, 1.0), (1.1, 2.1, 0.0, 1.0)]
    ok &= chk("⑤ expand=0 无对 · expand=0.2 有对（外扩语义正确）",
              near_pairs(gap2, 0.0) == [] and near_pairs(gap2, 0.2) == [(0, 1)])

    # ⑥ 长条（oversized）也必须参与
    long_bar = [(0.0, 100.0, 0.0, 0.1)] + [(i * 10.0, i * 10.0 + 0.5, 0.05, 0.55)
                                           for i in range(10)]
    sp = set(near_pairs(long_bar))
    bp = set(brute_pairs(long_bar))
    ok &= chk("⑥ 长条（跨 >64 格 ⇒ oversized）不漏对（%d ⟷ %d）" % (len(sp), len(bp)),
              sp == bp and len(bp) > 0)

    # ⑦ 超集性：真实阵列上 near ⊇ brute（多个几何）
    # 🔴 规模锁 N=8：`brute_pairs` 是 O(n²)，N=12（2760 元素）单次 3.8M 对 ×3 expand
    #   ×4 组 ⇒ 本判据会独占自检 80% 时间。超集性只需**有代表性的几何**即可证明。
    sup_ok = True
    for nn, prm, rl, vs in ((8, None, "M1", False),
                            (8, {"row_w_um": 1.60, "pitch_y_um": 3.20}, "AP", True),
                            (8, {"row_w_um": 0.55}, "M1", False),
                            (8, None, "M6", True)):
        arr = LY.crossbar_array(nn, nn, prm, row_layer=rl, via_stack=vs)
        bx = [LY._bbox(d) for d in arr["descs"]]
        for ex in (0.0, 0.28, 1.60):
            sup_ok &= set(brute_pairs(bx, ex)) <= set(near_pairs(bx, ex))
    ok &= chk("⑦ 🔴 超集性：真实阵列 ×4 组 × expand(0/0.28/1.6) 上 `near ⊇ brute`", sup_ok)

    # ⑧ 新旧判定对拍（含 REJECT 案例）
    ps = parity_summary()
    ok &= chk("⑧ 🔴 新旧对拍 %d 案例（含 %d 个 REJECT）逐条一致"
              % (ps["n_cases"], ps["n_reject_cases"]), ps["all_equal"])

    # ⑨ 规模：N=87 必须全 ACCEPT 且在预算内
    ss = scale_summary()
    ok &= chk("⑨ 🔴 N=%d（%s 元素）全 ACCEPT · %.2fs（预算 300s）"
              % (ss["n_max_verified"], format(ss["rows"][-1]["n_elements"], ","),
                 ss["elapsed_max_s"]),
              ss["all_accept"] and ss["elapsed_max_s"] < 300.0)

    # ⑩ 小规模不走索引（保证不比原来慢）
    ok &= chk("⑩ 小规模回退阈值 = %d 元素（n=120 时索引开销 0.9× > 收益）"
              % LY.SPATIAL_MIN_ELEMENTS, LY.SPATIAL_MIN_ELEMENTS >= 128)

    npass = sum(1 for c, _, _ in checks if c)
    if verbose:
        print()
        print("MODE=%s 合计 %d 判据 · PASS %d / FAIL %d"
              % (TIER, len(checks), npass, len(checks) - npass))
    return ok


SPATIAL_DISCLOSURE = {
    "role": "E32 = 版图几何空间索引（网格 + 长条单列）· 把 DRC/LVS 从 O(N⁴) 降到可用",
    "design_discipline": "索引**只筛候选**，判定仍用原来的 `_overlap`/`_gap` ⇒ "
                         "新旧实现语义逐位等价（对拍可证），而不是「看起来一样」",
    "superset_guarantee": "相交 ⇒ 必共享格；间距 < expand ⇒ 外扩 expand 后必相交 ⇒ 候选是超集",
    "not_a_drc_tool": "本模块不含任何设计规则；规则仍在 `ELEC_DESIGN_RULES` + `EDRC_RULES`",
    "measured": "N=24 旧 17.51s → 新 0.20s（87.5×）· N=87（143,985 元素）4.21s 全 ACCEPT"
                "（旧实现外推 ~7h）· 经验复杂度 N^2.6（旧 N^4）",
    "residual_o_n3": "长条（行线）走 `oversized` 单列 ⇒ `N 条 × 全体` = O(N³) 是**剩余瓶颈**；"
                     "若将来要 N≥200 需再把行线用 1D 排序处理",
    "tier": TIER,
}


__all__ = ["Grid", "near_pairs", "brute_pairs", "PARITY_CASES", "parity_matrix",
           "parity_summary", "SCALE_NS", "scale_table", "scale_summary",
           "spatial_self_check", "SPATIAL_DISCLOSURE"]
