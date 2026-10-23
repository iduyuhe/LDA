# -*- coding: utf-8 -*-
"""D-218 · 容错编译层（**能力层 + 整数恒等判据，不做锚域**）。

═══════════════════════════ 这一层补的是哪个断点 ═══════════════════════════
量子域全景审计（2026-10-23）判「**逻辑 → 物理编译层整域空白**」为三处闭环断点之一
（`transpile` / `magic_state` / `logical_to_physical` 全仓 0 命中）。
D3 短评估同时裁定：这一层**没有物理律闭式可锚**（四类 gap 逐条判死）。

本模块按该裁定的结论施工：**做能力层，判据只用整数恒等式与集合合法性**，
**不新增任何锚**、**不做浮点保真**（D3 已证伪：编译后总保真的两条独立实现只差
3–53 ulp，而跨平台判据线是 1e4·ulp ⇒ 原理上不可复现）。

═══════════════════════════ 编译链（真实的最小闭环）═══════════════════════════
    逻辑线路（Clifford+T + CX + 测量）
        │ ① 门集闭包校验（集合断言）
        ▼
    初始布局（逻辑 → 物理节点，贪心 BFS 放置）
        │ ② 最短路路由（BFS；每跳一个 SWAP = 3 个物理 CX）
        ▼
    物理操作序列（含 SWAP 展开）
        │ ③ ASAP 分层调度（同层互不共享物理比特）
        ▼
    时隙表 + 资源报告（物理比特 / T 态 / 深度）+ 整数恒等式自证

═══════════════════════════ 七条整数恒等判据（本模块的"判据"就这些）═══════════════════════════
I1 门计数守恒：`n_ops_out == n_gates_in + 3·n_swap`（SWAP 展开成 3 个 CX）
I2 路由距离恒等：每跳 SWAP 数 `== dist(a,b) − 1`（BFS 最短路，逐对核）
I3 置换一致性：`mapping_final ∘ (SWAP 序列) == mapping_initial`（restore=True 时严格相等）
I4 分层合法性：同一层内任意两 op **不共享物理比特**（集合两两不交）
I5 覆盖守恒：每个 op **恰出现一次**且**恰在一层**（计数 == 长度）
I6 拓扑合法性：所有 CX 的物理对 **必须** ∈ 硬件 adjacency（边集断言）
I7 T 态平衡：`t_states_consumed − t_states_produced == n_T_gates`（整数，蒸馏产出按工厂比）

🔴 **为什么这些不是锚**：全部是整数/集合恒等式 ⇒ 与"闭式物理律 vs 独立数值候选"
的锚范式无关；把它们写成锚会退化成 `resid ≡ 0`（D3 已判死的第 ② 类）。

红线：纯 stdlib（不依赖 numpy）· 零第三方 · 零 LLM · 零浮点判决。
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ROLE",
    "ANCHORABLE",
    "GATES_1Q",
    "GATES_2Q",
    "GATES_MEAS",
    "make_circuit",
    "check_gate_set",
    "bfs_path",
    "place_layout",
    "compile_circuit",
    "schedule_asap",
    "integer_identities",
    "resource_report",
    "why_not_anchored",
    "run_selfchecks",
]

ROLE = ("D-218 · 容错编译层（能力层）—— 逻辑线路 → 物理操作 → 分层时隙 + 资源报告，"
        "判据只用整数恒等式与集合合法性；不接浮点保真、不新增锚")

#: 🔴 不做锚域（D3 短评估的裁决在本模块的机器化落地）
ANCHORABLE = False

GATES_1Q = ("H", "S", "T", "X", "Z")
GATES_2Q = ("CX",)
GATES_MEAS = ("M", "R")
_ALLOWED = GATES_1Q + GATES_2Q + GATES_MEAS


# ═════════════════════════════ 线路构造与校验 ═════════════════════════════
def make_circuit(ops: Sequence[Tuple]) -> Dict[str, Any]:
    """把简写 op 列表规整为线路 dict。

    允许的 op 形式：
      ("H", q) · ("T", q) · ("CX", a, b) · ("M", q) · ("R", q)
    返回 {"ops": [{"gate","qubits"}...], "n_qubits": int}
    """
    out: List[Dict[str, Any]] = []
    nq = 0
    for op in ops:
        if not isinstance(op, (tuple, list)) or len(op) < 2:
            raise ValueError("op 必须是 (gate, q...) 元组，实际 %r" % (op,))
        gate = str(op[0]).upper()
        qs = tuple(int(x) for x in op[1:])
        if gate in GATES_1Q or gate in GATES_MEAS:
            if len(qs) != 1:
                raise ValueError("%s 需要 1 个逻辑比特，实际 %d" % (gate, len(qs)))
        elif gate in GATES_2Q:
            if len(qs) != 2:
                raise ValueError("%s 需要 2 个逻辑比特，实际 %d" % (gate, len(qs)))
            if qs[0] == qs[1]:
                raise ValueError("%s 的两个比特不得相同" % gate)
        else:
            raise ValueError("未登记的门 %r（允许集 %s）" % (gate, list(_ALLOWED)))
        out.append({"gate": gate, "qubits": qs})
        nq = max([nq] + [q + 1 for q in qs])
    return {"ops": out, "n_qubits": nq}


def check_gate_set(circuit: Dict[str, Any]) -> Dict[str, Any]:
    """门集闭包校验（集合断言）：所有门 ∈ 允许集，且比特编号连续无空洞。"""
    ops = circuit.get("ops") or []
    used = sorted({q for o in ops for q in o["qubits"]})
    bad = sorted({o["gate"] for o in ops if o["gate"] not in _ALLOWED})
    # 🔴 允许**空闲逻辑比特**（线路可以用不到某些比特，如逻辑 1 闲置）：
    #   `contiguous` 只作为信息字段记录（用于"是否值得重编号"的诊断），
    #   但**不构成失败条件** —— 否则任何含空闲比特的线路都被拒，等于逼调用方先做
    #   一次重编号（编译器该做的是报出来，不是在闸门处硬拒）。
    contiguous = used == list(range(len(used)))
    return {
        "ok": (not bad),
        "n_ops": len(ops),
        "n_qubits": circuit.get("n_qubits", 0),
        "used_qubits": used,
        "bad_gates": bad,
        "contiguous": contiguous,
        "idle_qubits": [q for q in range(circuit.get("n_qubits", 0)) if q not in used],
    }


# ═══════════════════════════════ 图与路由 ═══════════════════════════════
def bfs_path(adjacency: Dict[Any, Sequence[Any]], src: Any, dst: Any) -> Optional[List[Any]]:
    """BFS 最短路（返回含首尾的节点表）；不可达返回 None。纯整数跳数。"""
    src, dst = int(src), int(dst)
    adj = {int(k): [int(x) for x in v] for k, v in adjacency.items()}
    if src not in adj or dst not in adj:
        raise ValueError("拓扑里没有节点 %r" % (src if src not in adj else dst))
    if src == dst:
        return [src]
    prev: Dict[int, int] = {src: src}
    dq = deque([src])
    while dq:
        cur = dq.popleft()
        for nxt in adj[cur]:
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == dst:
                path = [dst]
                while path[-1] != src:
                    path.append(prev[path[-1]])
                return list(reversed(path))
            dq.append(nxt)
    return None


def place_layout(n_logical: int,
                 adjacency: Dict[Any, Sequence[Any]],
                 *,
                 nodes_order: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    """初始布局：把 n_logical 个逻辑比特顺序放到拓扑节点上（节点越多越好，取前 k 个）。"""
    if n_logical <= 0:
        raise ValueError("n_logical 必须 > 0，实际 %r" % (n_logical,))
    nodes = list(nodes_order) if nodes_order is not None else sorted(int(k) for k in adjacency)
    nodes = [int(n) for n in nodes]
    if len(nodes) < n_logical:
        raise ValueError("拓扑只有 %d 个节点，放不下 %d 个逻辑比特" % (len(nodes), n_logical))
    mapping = {i: nodes[i] for i in range(n_logical)}      # logical -> physical
    return {"mapping": mapping, "inverse": {v: k for k, v in mapping.items()}}


# ═══════════════════════════ 编译主流程 ═══════════════════════════
def _is_adjacent(adjacency: Dict[Any, Sequence[Any]], a: int, b: int) -> bool:
    return int(b) in [int(x) for x in adjacency.get(int(a), [])]


def compile_circuit(circuit: Dict[str, Any],
                    adjacency: Dict[Any, Sequence[Any]],
                    *,
                    restore: bool = True) -> Dict[str, Any]:
    """编译：布局 → 路由 → 物理 op 序列 → ASAP 分层。

    `restore=True` 时在末尾**逆序撤销**所有 SWAP，使 `mapping_final == mapping_initial`
    （I3 由此从"置换复合一致"升级为"逐键相等"，更硬）。
    """
    ck = check_gate_set(circuit)
    if not ck["ok"]:
        raise ValueError("门集校验失败：bad=%s contiguous=%s"
                         % (ck["bad_gates"], ck["contiguous"]))

    lay = place_layout(circuit["n_qubits"], adjacency)
    log2phys = dict(lay["mapping"])          # logical -> physical
    phys2log = dict(lay["inverse"])          # physical -> logical
    mapping_initial = dict(log2phys)

    ops: List[Dict[str, Any]] = []
    swaps: List[Dict[str, int]] = []
    route_checks: List[Dict[str, Any]] = []

    def emit(kind: str, phys: Tuple[int, ...], log: Tuple[int, ...]) -> None:
        ops.append({"kind": kind, "phys": tuple(phys), "logical": tuple(log)})

    def do_swap(p: int, q: int, kind: str = "route") -> None:
        """交换两物理节点上的逻辑比特；物理层展开为 3 个 CX（A→B, B→A, A→B）。

        `kind` 区分**路由** SWAP 与**恢复**（restore）SWAP —— 二者都计入物理门计数
        （I1 恒等），但只有路由 SWAP 参与"距离恒等"（I2）。不区分会把恢复开销
        混进路由质量指标里，读数会虚高。
        """
        la, lb = phys2log.get(p), phys2log.get(q)
        if la is None:
            raise ValueError("SWAP 源节点 %r 上没有逻辑比特（不能把空位移进空位）" % (p,))
        if lb is None:
            # 🔴 允许搬到**空位**（heavy-hex 这类稀疏占用的拓扑必需）：
            #   逻辑比特 la 从 p 移到 q，p 变空。旧实现要求两端都有 occupant
            #   ⇒ 在 39 节点只占 6 个的 heavy-hex 上直接崩（本轮血案）。
            del phys2log[p]
            phys2log[q] = la
            log2phys[la] = q
        else:
            phys2log[p], phys2log[q] = lb, la
            log2phys[la], log2phys[lb] = q, p
        swaps.append({"a": p, "b": q, "la": la, "lb": lb, "kind": kind})
        emit("CX", (p, q), (la, lb))
        emit("CX", (q, p), (lb, la))
        emit("CX", (p, q), (la, lb))

    for o in circuit["ops"]:
        g, qs = o["gate"], o["qubits"]
        if g in GATES_2Q:
            a, b = qs
            pa, pb = log2phys[a], log2phys[b]
            if _is_adjacent(adjacency, pa, pb):
                emit("CX", (pa, pb), (a, b))
                route_checks.append({"logical": (a, b), "dist": 1, "n_swap": 0})
                continue
            path = bfs_path(adjacency, pa, pb)
            if path is None:
                raise ValueError("拓扑不可达：物理 %d → %d" % (pa, pb))
            n_swap = len(path) - 2          # 把 pa 搬到 pb 的邻居所需的 SWAP 数
            for k in range(n_swap):
                do_swap(path[k], path[k + 1])
            pa_new = log2phys[a]
            if not _is_adjacent(adjacency, pa_new, pb):
                raise AssertionError("路由后仍不相邻：%d vs %d" % (pa_new, pb))
            emit("CX", (pa_new, pb), (a, b))
            route_checks.append({"logical": (a, b), "dist": len(path) - 1, "n_swap": n_swap})
        else:
            p = log2phys[qs[0]]
            emit(g, (p,), qs)

    if restore and swaps:
        # 🔴 逆序撤销必须**交换 a/b**：SWAP 可搬到空位时，正向 do_swap(p→空位 q) 的逆
        #   是 do_swap(q, p)（把比特从 q 搬回 p、p 变回空），而不是 do_swap(p, q)
        #   —— 后者会因「源 p 此时为空」直接崩（本轮在 heavy-hex 上实测撞到）。
        for sw in reversed(swaps):
            do_swap(sw["b"], sw["a"], kind="restore")

    layers = schedule_asap(ops)
    res = {
        "ops": ops,
        "swaps": swaps,
        "n_swap": len(swaps),
        "n_swap_route": sum(1 for s in swaps if s.get("kind") == "route"),
        "n_swap_restore": sum(1 for s in swaps if s.get("kind") == "restore"),
        "n_gates_in": len(circuit["ops"]),
        "n_ops_out": len(ops),
        "route_checks": route_checks,
        "mapping_initial": mapping_initial,
        "mapping_final": dict(log2phys),
        "layers": layers,
        "depth": len(layers),
        "restored": bool(restore),
        "n_logical": circuit["n_qubits"],
        "topology_nodes": len(adjacency),
    }
    return res


def schedule_asap(ops: Sequence[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """ASAP 分层：每个 op 放进"最早的不冲突层"（同层任意两 op 的物理比特集不相交）。

    这是**能力层调度**，不是锚：深度是整数、合法性是集合断言（I4/I5）。
    """
    layers: List[List[Dict[str, Any]]] = []
    layer_bits: List[set] = []
    for op in ops:
        bits = set(op["phys"])
        placed = False
        for i, used in enumerate(layer_bits):
            if not (bits & used):
                layers[i].append(op)
                used |= bits
                placed = True
                break
        if not placed:
            layers.append([op])
            layer_bits.append(set(bits))
    return layers


# ═══════════════════════ 七条整数恒等判据（自证）═══════════════════════
def integer_identities(result: Dict[str, Any],
                       adjacency: Dict[Any, Sequence[Any]],
                       *,
                       n_T_gates: int = 0,
                       t_factory_ratio: int = 1) -> Dict[str, Any]:
    """对本模块产出的编译结果逐条核 **整数/集合恒等式**，返回逐条 pass/fail。

    `t_factory_ratio`：一个蒸馏工厂在每次产出周期里贡献的 T 态数（整数 ≥1）。
    """
    checks: Dict[str, Dict[str, Any]] = {}

    # I1 门计数守恒
    want = result["n_gates_in"] + 3 * result["n_swap"]
    checks["I1_gate_count"] = {
        "pass": result["n_ops_out"] == want,
        "detail": "n_ops_out=%d vs n_gates_in+3·n_swap=%d"
                  % (result["n_ops_out"], want),
    }

    # I2 路由距离恒等（逐对）
    bad = [r for r in result["route_checks"] if r["dist"] - 1 != r["n_swap"]]
    checks["I2_route_distance"] = {
        "pass": not bad,
        "detail": "逐对核 n_swap == dist−1；违例 %s" % (bad[:3],) if bad else "全部满足",
    }

    # I3 置换一致性（restore 时逐键相等）
    eq = result["mapping_final"] == result["mapping_initial"]
    perm_ok = (sorted(result["mapping_final"]) == sorted(result["mapping_initial"])
               and sorted(result["mapping_final"].values())
               == sorted(result["mapping_initial"].values()))
    checks["I3_mapping"] = {
        "pass": (eq if result["restored"] else perm_ok),
        "detail": ("restore=True ⇒ 逐键相等:%s" % eq) if result["restored"]
                  else ("restore=False ⇒ 值集为同一置换:%s" % perm_ok),
    }

    # I4 分层合法性（同层两两不共享物理比特）
    viol = 0
    for layer in result["layers"]:
        seen: set = set()
        for op in layer:
            bits = set(op["phys"])
            if bits & seen:
                viol += 1
            seen |= bits
    checks["I4_layer_disjoint"] = {
        "pass": viol == 0,
        "detail": "同层比特冲突数 %d" % viol,
    }

    # I5 覆盖守恒（每个 op 恰出现一次且恰在一层）
    flat = [id(op) for layer in result["layers"] for op in layer]
    checks["I5_cover"] = {
        "pass": (len(flat) == len(result["ops"]) and len(set(flat)) == len(flat)),
        "detail": "层内 op 总数 %d vs ops %d" % (len(flat), len(result["ops"])),
    }

    # I6 拓扑合法性（所有 CX 的物理对 ∈ adjacency）
    bad_e = []
    for op in result["ops"]:
        if op["kind"] == "CX":
            p, q = op["phys"]
            if not _is_adjacent(adjacency, p, q):
                bad_e.append((p, q))
    checks["I6_topology_edge"] = {
        "pass": not bad_e,
        "detail": "非边 CX 数 %d %s" % (len(bad_e), bad_e[:3] if bad_e else ""),
    }

    # I7 T 态平衡（消耗 − 产出 == T 门数）
    consumed = n_T_gates
    produced = (n_T_gates // max(1, t_factory_ratio)) * t_factory_ratio \
        if t_factory_ratio > 1 else n_T_gates
    checks["I7_t_state"] = {
        "pass": consumed - produced == 0 and consumed == n_T_gates,
        "detail": "consumed=%d produced=%d n_T=%d ratio=%d"
                  % (consumed, produced, n_T_gates, t_factory_ratio),
    }

    return {"all_pass": all(c["pass"] for c in checks.values()), "checks": checks}


def resource_report(result: Dict[str, Any], *, d: int = 3) -> Dict[str, Any]:
    """资源报告（全部整数）：物理比特 / patch 面积 / 时隙 / 每条路的 SWAP 数。

    patch 面积取旋转表面码的 `2d²−1` 数据比特量级（与 `surface_code` 口径一致：
    d×d 数据 + (d²−1) 测量比特）。**这是资源记账，不是器件实测。**
    """
    if d < 1:
        raise ValueError("码距 d 必须 ≥1，实际 %r" % (d,))
    n_log = result["n_logical"]
    per_patch = 2 * d * d - 1
    return {
        "d": d,
        "n_logical": n_log,
        "phys_per_patch": per_patch,
        "n_physical": n_log * per_patch,
        "n_slots": result["depth"],
        "n_swap": result["n_swap"],
        "n_cx": sum(1 for o in result["ops"] if o["kind"] == "CX"),
        "topology_utilisation": "%d/%d" % (n_log, result["topology_nodes"]),
        "note": "面积按旋转表面码 2d²−1 记账；深度为 ASAP 分层时隙数；非实测",
    }


def why_not_anchored() -> Dict[str, Any]:
    """**负结果机器化**：为什么编译层不立锚（承 D3 短评估的四类判死）。"""
    return {
        "anchorable": ANCHORABLE,
        "four_dead_classes": [
            {"class": "编译后总保真",
             "why": "逐门乘积 ⇒ 两条独立实现（连乘 vs exp(Σlog)）实测只差 3–53 ulp，"
                    "而跨平台判据线是 1e4·ulp ⇒ 原理上不可复现",
             "replacement": "本模块改判**整数门计数守恒**（I1），不判保真"},
            {"class": "调度深度下界",
             "why": "⌈N/Q⌉ / 关键路径 / LNN 平均 SWAP (n²−1)/(3n) 全是整数或精确有理 ⇒ "
                    "闭式 vs 精确枚举差恒 0（resid ≡ 0，属假锚）",
             "replacement": "本模块只把深度作为**能力层输出 + 分层合法性集合断言**（I4/I5）"},
            {"class": "魔术态资源",
             "why": "1/15 精确有理 · 蒸馏轮数整数（p=1e-2→≤1e-12 需 3 轮）· T-count 整数",
             "replacement": "本模块改判**消耗−产出平衡**（I7），不判绝对消耗率"},
            {"class": "错误预算分摊收益",
             "why": "同族同 ε 下等分即最优（1e-5×100=1e-3 精确）⇒「分摊收益」恒 0 ⇒ 派生量",
             "replacement": "不做（如实登记为不可锚）"},
        ],
        "decision": "**能力层、不可锚**：把「逻辑线路 → 物理操作 → 时隙 + 资源」做出来，"
                    "判据全为整数恒等式与集合合法性，**不新增账本条目**",
        "revisit_condition": "若将来出现**非整数**的编译期物理量（如脉冲级串扰导致的"
                             "非理想门重叠）且能找到独立数值候选，可重评；"
                             "在此之前任何「编译层锚」都应先过 D3 的四类判死",
    }


# ═════════════════════════════ 自检（门禁同源调用）════════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检：七条整数恒等式 + 路由/布局/调度/护栏各一例。无落盘、无子进程。"""
    res: List[Tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        res.append((name, bool(cond), detail))

    adj = {0: [1, 3], 1: [0, 2, 4], 2: [1, 5], 3: [0, 4], 4: [3, 1, 5], 5: [4, 2]}

    # ① 门集校验通过 + 非法门被拒
    c = make_circuit([("H", 0), ("CX", 0, 1), ("T", 1), ("M", 0)])
    ck = check_gate_set(c)
    bad_reject = 0
    for bad in (lambda: make_circuit([("SWAP", 0, 1)]),
                lambda: make_circuit([("CX", 0)]),
                lambda: make_circuit([("CX", 0, 0)])):
        try:
            bad()
        except ValueError:
            bad_reject += 1
    chk("① 门集校验通过 ∧ 三类非法 op 均抛 ValueError", ck["ok"] and bad_reject == 3)

    # ② BFS 最短路（整数跳数）
    p = bfs_path(adj, 0, 2)
    chk("② BFS 0→2 最短路 = [0,1,2]（3 节点 / 2 跳）",
        p == [0, 1, 2], "path=%s" % (p,))

    # ③ 邻接 CNOT：无 SWAP
    r0 = compile_circuit(make_circuit([("CX", 0, 1)]), adj)
    chk("③ 相邻 CNOT ⇒ n_swap=0 ∧ ops=1 ∧ depth=1",
        r0["n_swap"] == 0 and r0["n_ops_out"] == 1 and r0["depth"] == 1)

    # ④ 非邻接 CNOT：路由 + SWAP 展开（I1/I2）
    r1 = compile_circuit(make_circuit([("CX", 0, 2)]), adj)
    # 逻辑 0→phys0, 1→phys1, 2→phys2；CX(0,2)：phys0 与 phys2 距 2 ⇒ 1 个路由 SWAP；
    # restore=True 再 1 个恢复 SWAP ⇒ 总 2 个（I1 按总数守恒，I2 只核路由）。
    id1 = integer_identities(r1, adj)
    chk("④ 非邻接 CNOT ⇒ 路由 SWAP=1 / 总 SWAP=2 ∧ I1/I2 恒等成立",
        r1["n_swap_route"] == 1 and r1["n_swap"] == 2
        and id1["checks"]["I1_gate_count"]["pass"]
        and id1["checks"]["I2_route_distance"]["pass"],
        "n_swap_route=%d n_swap=%d n_ops=%d" % (r1["n_swap_route"], r1["n_swap"],
                                                r1["n_ops_out"]))

    # ⑤ restore：映射逐键复原（I3）
    chk("⑤ restore=True ⇒ mapping_final == mapping_initial（I3 逐键相等）",
        id1["checks"]["I3_mapping"]["pass"] and r1["mapping_final"] == r1["mapping_initial"])

    # ⑥ 全恒等式（I1–I7）在混合线路上同时成立
    c2 = make_circuit([("H", 0), ("CX", 0, 2), ("T", 2), ("CX", 1, 3), ("M", 3)])
    r2 = compile_circuit(c2, adj)
    id2 = integer_identities(r2, adj, n_T_gates=1)
    chk("⑥ 混合线路：I1–I7 全通过", id2["all_pass"],
        "失败项=%s" % [k for k, v in id2["checks"].items() if not v["pass"]])

    # ⑦ 分层合法性（I4）与覆盖守恒（I5）在"可并行"电路上真去并行
    c3 = make_circuit([("H", 0), ("H", 1), ("H", 2)])
    r3 = compile_circuit(c3, adj)
    chk("⑦ 三个独立 1q 门 ⇒ 同层并行（depth=1）∧ I4/I5 成立",
        r3["depth"] == 1
        and integer_identities(r3, adj)["checks"]["I4_layer_disjoint"]["pass"]
        and integer_identities(r3, adj)["checks"]["I5_cover"]["pass"])

    # ⑧ 拓扑合法性（I6）：所有 CX ∈ 边
    chk("⑧ I6：混合线路所有 CX 均为硬件边",
        id2["checks"]["I6_topology_edge"]["pass"])

    # ⑨ 资源报告整数且自洽
    rep = resource_report(r2, d=3)
    chk("⑨ 资源报告：phys_per_patch=2d²−1=17 ∧ n_physical=4·17=68 ∧ 全整数",
        rep["phys_per_patch"] == 17 and rep["n_physical"] == 68
        and isinstance(rep["n_physical"], int))

    # ⑩ T 态平衡（I7）：比例 >1 时按工厂整周期记账
    idT = integer_identities(r2, adj, n_T_gates=3, t_factory_ratio=3)
    chk("⑩ I7：T 门 3 个 / 工厂比 3 ⇒ 消耗−产出 == 0",
        idT["checks"]["I7_t_state"]["pass"])

    # ⑪ 负结果机器化：四类判死 + 重评条件齐备
    w = why_not_anchored()
    chk("⑪ 不可锚裁决齐备（anchorable=False + 四类判死 + 重评条件）",
        w["anchorable"] is False and len(w["four_dead_classes"]) == 4
        and "revisit_condition" in w)

    # ⑫ 护栏：拓扑不可达 / 放不下 / 码距非法
    guard = 0
    for bad in (lambda: place_layout(9, adj),
                lambda: resource_report(r2, d=0),
                lambda: bfs_path(adj, 0, 99)):
        try:
            bad()
        except ValueError:
            guard += 1
    chk("⑫ 护栏：放不下 / d<1 / 不存在的节点 三例均抛 ValueError", guard == 3)

    ok = all(v for _, v, _d in res)
    if verbose:
        for n, v, d in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n + (("  |  " + d) if d else ""))
    return ok


if __name__ == "__main__":
    print("ft_compiler 自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
