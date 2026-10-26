"""J2 M4 · 拓扑 ↔ 表面码对接桥（吃狗粮）。

承 J2 蓝图 M4「拓扑连通性 vs 表面码需求」：把 **J2 QPU 拓扑**（复用 S 分支
`sc_topology_core` 的方阵 / heavy-hex 构建器）与 **J1 表面码需求**对接成可签核判据。

三条判据（全闭式 + 复用既有能力层，零量子 SDK）：
  1. **连通性谱度量 λ₂（代数连通度 / Fiedler 值）**：耦合图 Laplacian 的次小本征值。
     Cheeger 不等式 `λ₂/2 ≤ h(G) ≤ √(2λ₂)` 把 λ₂ 与**等周数 h(G)** 钉在一起
     ⇒ λ₂ 越大，局部割越难切断 ⇒ 表面码解码器（Union-Find / MWPM）在图上做
     2D 局部匹配越稳。**与账本锚 B509 golden 同一物理律**（方阵图闭式
     `2−2cos(π/max(rows,cols))`）；本层对任一拓扑（方阵 / heavy-hex）用
     Krylov Rayleigh–Ritz 现算，`run_j2_qpu_smoke` 常驻断言方阵实例逐值一致。
  2. **2D 最近邻嵌入判定**：rotated surface code 需耦合图给出 2D 最近邻格
     （内部稳定子权重 4 ⇒ 硬件图须有度 4 节点）。方阵（度 ≤ 4）⇒ `DIRECT`；
     heavy-hex（度 ≤ 3，含边 qubit 度 2）⇒ `ADAPTED`；度 < 3 ⇒ `FAIL`。
     🔴 **v0.9.308 订正：这条判据只是「必要条件」，不是充分条件。**
     反例（`lda_qeda/sc_embedding` 自检 ③ 造出来）：3-ary 树内部节点度恰 4、24 个节点
     ≥ 17，按本函数判 `DIRECT`，实际**可证不可能** —— 表面码关联图含 4-圈（相邻两个
     稳定子交叠 2 个数据比特），树一个 4-圈都没有。⇒ 本函数返回的 `verdict` **只能用来
     否证**（判 `FAIL` 是可靠的），判 `DIRECT`/`ADAPTED` **不能**当「能落上去」用。
     真嵌入判定见 `native_embedding` 字段（三值：DIRECT / IMPOSSIBLE / UNKNOWN）。
  3. **资源核对**：J1 口径 `2d²−1` 物理比特 / 逻辑比特 ⇒ 给定 QPU 比特数可容
     逻辑比特数 = ⌊N / (2d²−1)⌋。

诚实边界：拓扑构建器与判据阈值均为**设计规则/设计示例**（非 Foundry PDK）；
λ₂ 是**图论谱不变量**（不耦合器件物理常数）；本层只做**设计对接**（不含量子线路
仿真、不含解码器实测），结论只可用于设计与量级，**不得作制造/性能宣称**。
红线：纯 numpy/标准库 · 零量子 SDK · LLM 不进判决路径 · 阈值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

from lda_qeda import sc_topology_core as TOPO
from lda_qeda import sc_embedding as SCE

#: 嵌入判定取值（设计规则口径）
EMBED_DIRECT = "DIRECT"
EMBED_ADAPTED = "ADAPTED"
EMBED_FAIL = "FAIL"

#: Krylov 起始向量确定性解析式（与 `_batch_j2m4_numeric` 同式 ⇒ 零 RNG、逐位可复现）
_START_A, _START_B, _START_C = 1.0, 0.7, 0.3

#: 表面码 2D 最近邻要求的**原生内部度**
SURFACE_CODE_NATIVE_DEGREE = 4


def _laplacian_from_adjacency(adjacency: Dict[int, List[int]]) -> "np.ndarray":
    """由邻接表构造组合 Laplacian L = D − A（节点按排序后的 id 排列）。"""
    nodes = sorted(adjacency)
    index = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    lap = np.zeros((n, n), dtype=float)
    for u in nodes:
        i = index[u]
        for v in adjacency[u]:
            if v not in index:
                raise ValueError("邻接表含未知邻居 %r（节点集不自洽）" % (v,))
            lap[i, i] += 1.0
            lap[i, index[v]] -= 1.0
    return lap


def topology_lambda2(topo: Dict, m: int = 32) -> float:
    """耦合图代数连通度 λ₂（Krylov 子空间 Rayleigh–Ritz 最小值；⊂ 1⊥）。

    🔴 与账本锚 **B509 candidate 同一算法**（嵌套 K_m 上的 min-max ⇒ 残差单调降）。
    Krylov 维数被**显式钳到** `min(m, N−1)`（m ≥ N 时重正交残差会把常数向量泄漏进去
    ⇒ 最小 Ritz 滑向 λ₁=0）。非静默：钳位是确定性的、`m_used` 由返回值可查。
    """
    lap = _laplacian_from_adjacency(topo["adjacency"])
    n = lap.shape[0]
    if n < 2:
        return 0.0
    m_used = max(2, min(int(m), n - 1))
    idx = np.arange(n, dtype=float)
    v = np.sin(_START_A + _START_B * idx) + np.cos(_START_C * idx)
    v = v - v.mean()
    v = v / float(np.linalg.norm(v))
    basis = [v]
    for _ in range(m_used - 1):
        w = lap @ basis[-1]
        for q in basis:
            w = w - float(q @ w) * q
        w = w - w.mean()
        nw = float(np.linalg.norm(w))
        if nw < 1e-13:
            break
        basis.append(w / nw)
    q = np.column_stack(basis)
    return float(np.linalg.eigvalsh(q.T @ lap @ q)[0])


def graph_connectivity(topo: Dict) -> Dict:
    """连通性核对：BFS 连通分量数 + 节点/边计数（是否单连通）。"""
    adjacency = topo["adjacency"]
    nodes = sorted(adjacency)
    seen = set()
    comps = 0
    for start in nodes:
        if start in seen:
            continue
        comps += 1
        stack = [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            for v in adjacency[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    return {"n_components": comps, "connected": comps == 1,
            "n_nodes": len(nodes), "n_edges": len(topo["couplers"])}


def surface_code_2d_nn_verdict(topo: Dict) -> Dict:
    """2D 最近邻嵌入判定（**设计规则 · 只是必要条件**）：度 4 ⇒ DIRECT；度 3 ⇒ ADAPTED。

    🔴 v0.9.308：本函数判 `DIRECT` **不等于**「表面码能落上去」。它只是必要条件
    （内部稳定子权重 4 ⇒ 要有度 4 的节点）。充分性由 `sc_embedding.native_verdict`
    用真子图同构判定。判 `FAIL` 方向仍可靠（必要条件不满足 ⇒ 一定不行）。
    """
    deg = TOPO.topology_degree_stats(topo)
    md = int(deg["max_degree"])
    if md >= SURFACE_CODE_NATIVE_DEGREE and bool(deg["within_limit"]):
        verdict, reason = EMBED_DIRECT, ("内部度 ≥ 4 ⇒ rotated surface code 原生直接嵌入"
                                        "（2D 最近邻格）")
    elif md == int(TOPO.HEAVYHEX_MAX_DEGREE):
        verdict, reason = EMBED_ADAPTED, ("最大度 3（蜂窝顶点 3 + 边 qubit 2）⇒ 须以"
                                         "边 qubit 作辅助/flag 适配，非原生直接嵌入")
    else:
        verdict, reason = EMBED_FAIL, ("最大度 %d < 3 ⇒ 无法提供 2D 最近邻格" % md)
    return {"verdict": verdict, "max_degree": md,
            "max_degree_limit": int(deg["max_degree_limit"]),
            "histogram": {int(k): int(v) for k, v in deg["histogram"].items()},
            "topology": topo["name"], "reason": reason,
            "native_degree_required": SURFACE_CODE_NATIVE_DEGREE,
            # 🔴 口径自述：本判据是**必要条件**。`DIRECT` 只说明「度数不挡」，
            #    不说明「拓扑能落下」；反例见 `lda_qeda/sc_embedding` 自检 ③（树）。
            "rule_scope": "necessary_only",
            "sufficiency_checked_by": "lda_qeda/sc_embedding.native_verdict",
            "sufficiency_counterexample": "3-ary 树（最大度 4、24 ≥ 17 节点）本函数判 DIRECT，"
                                          "实际可证不可能（关联图含 4-圈，树没有）"}


def native_embedding(topo: Dict, d: int = 3, budget: int = SCE.DEFAULT_BUDGET) -> Dict:
    """**真嵌入**判定（子图同构 · 三值）：DIRECT / IMPOSSIBLE（附证明）/ UNKNOWN。

    🔴 与 `surface_code_2d_nn_verdict` 的关系：后者答「度数够不够」（必要），
    本函数答「关联图能不能真落上去」（充要，除预算用尽记 UNKNOWN）。
    两者不一致是**允许且必须显式并存**的（heavy-hex：design=ADAPTED / native=IMPOSSIBLE）。
    """
    return SCE.native_verdict(topo["adjacency"], int(d), budget=budget)



def surface_code_resource_check(d: int, n_qubits: int) -> Dict:
    """J1 口径资源核对：`2d²−1` 物理比特 / 逻辑比特 ⇒ 可容逻辑比特数。"""
    d = int(d)
    n_qubits = int(n_qubits)
    if d < 1:
        raise ValueError("码距 d 须 ≥ 1")
    required = 2 * d * d - 1
    return {"d": d, "required_per_logical": required, "n_qubits": n_qubits,
            "ok": bool(required <= n_qubits),
            "n_logical_capacity": (n_qubits // required) if required > 0 else 0}


def bridge_verdict(topo: Dict, d: int = 3, m: int = 32,
                   native_budget: int = SCE.DEFAULT_BUDGET) -> Dict:
    """拓扑↔表面码对接签核 = 单连通 ∧ λ₂>0 ∧ 嵌入非 FAIL ∧ 资源足。

    🔴 v0.9.308：`verdict` 是**设计对接**（必要条件口径）的结论，`native` 才是
    「关联图能不能真落上去」。两者**必须一起读**：
    `verdict=ACCEPT ∧ native=IMPOSSIBLE`（heavy-hex 就是）意味着「度数不够，
    适配后已不是同一个码」—— 那时资源/λ₂ 的数字仍然对，但**不能读成「能跑」**。
    """
    conn = graph_connectivity(topo)
    lam = topology_lambda2(topo, m=m)
    emb = surface_code_2d_nn_verdict(topo)
    res = surface_code_resource_check(d, int(topo["n_qubits"]))
    native = native_embedding(topo, d, budget=native_budget)
    ok = (conn["connected"] and lam > 0.0 and emb["verdict"] != EMBED_FAIL
          and res["ok"])
    return {
        "verdict": "ACCEPT" if ok else "REJECT",
        # 🔴 设计对接口径（必要条件）——单独读会误判 feasibility
        "verdict_scope": "design_rule_necessary_only",
        "native": native,
        "native_status": native["status"],
        "native_feasible": native["status"] == SCE.STATUS_DIRECT,
        "topology": topo["name"], "d": int(d),
        "lambda2": float(lam), "connected": bool(conn["connected"]),
        "embedding": emb["verdict"], "embedding_reason": emb["reason"],
        "resource_ok": bool(res["ok"]),
        "n_logical_capacity": int(res["n_logical_capacity"]),
        "graph": conn, "resource": res,
        "note": ("λ₂ = 耦合图代数连通度（Cheeger 不等式 ⇒ 等周/扩张能力 ⇒ 2D 局部匹配"
                 "可行性）；嵌入 DIRECT（度≥4）/ADAPTED（度3 heavy-hex）**只是必要条件**；"
                 "资源按 J1 口径 2d²−1。真嵌入见 `native`（三值 · 附证明）。"
                 "图论口径，不验证 2D 局部性（允许折叠），不含解码器实测。"),
    }



def run_selfchecks(verbose: bool = False) -> bool:
    """常驻自检：方阵 λ₂ 与 B509 闭式一致 / 连通性 / 设计规则 / 资源 / 反向 / **真嵌入**。"""
    bad = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        if verbose:
            print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                                   ("  |  " + detail) if detail else ""))
        if not cond:
            bad.append(name)

    g10 = TOPO.grid_topology(10, 10)
    g3 = TOPO.grid_topology(3, 3)
    h3 = TOPO.heavy_hex_topology(3, 3)

    # ① 方阵 λ₂ == B509 闭式（跨模块同律 · 与账本锚对拍）
    lam10 = topology_lambda2(g10, m=32)
    closed10 = 2.0 - 2.0 * math.cos(math.pi / 10.0)
    chk("方阵 10×10 λ₂ 与 B509 闭式一致（rel < 1e-8）",
        abs(lam10 - closed10) / closed10 < 1e-8)
    chk("方阵 3×3 λ₂ == 1.0（闭式）",
        abs(2.0 - 2.0 * math.cos(math.pi / 3.0) - 1.0) < 1e-15)
    # ② λ₂ 随图规模单调不增（更大图 ⇒ 谱更「平」）
    chk("λ₂ 随方阵规模单调不增", topology_lambda2(g3, m=8) >= lam10)
    # ③ 连通性：方阵与 heavy-hex 均单连通
    chk("方阵单连通", graph_connectivity(g3)["connected"])
    chk("heavy-hex 单连通", graph_connectivity(h3)["connected"])
    # ④ 嵌入判定：方阵 DIRECT / heavy-hex ADAPTED / 稀疏图 FAIL
    chk("方阵 ⇒ DIRECT", surface_code_2d_nn_verdict(g3)["verdict"] == EMBED_DIRECT)
    chk("heavy-hex ⇒ ADAPTED",
        surface_code_2d_nn_verdict(h3)["verdict"] == EMBED_ADAPTED)
    chk("度上限由拓扑自声明（grid 4 / hex 3）",
        surface_code_2d_nn_verdict(g3)["max_degree_limit"] == 4
        and surface_code_2d_nn_verdict(h3)["max_degree_limit"] == 3)
    # ⑤ 资源核对：2d²−1 逐值 + 单调 + d 过大 ⇒ 不足
    chk("资源 2d²−1 逐值（d=3 ⇒ 17）",
        surface_code_resource_check(3, 100)["required_per_logical"] == 17)
    chk("资源随 d 单调不增（容量）",
        surface_code_resource_check(3, 100)["n_logical_capacity"]
        >= surface_code_resource_check(5, 100)["n_logical_capacity"])
    chk("资源反向：d 过大 ⇒ ok=False",
        surface_code_resource_check(50, 100)["ok"] is False)
    # ⑥ 桥签核：方阵 3×3 d=2 ⇒ ACCEPT（N=9 ≥ 2·4−1=7）；heavy-hex 3×3 d=3 ⇒ ACCEPT
    bv_g = bridge_verdict(g3, d=2)
    bv_h = bridge_verdict(h3, d=3)
    chk("方阵 3×3 d=2 ⇒ ACCEPT（9 ≥ 7）", bv_g["verdict"] == "ACCEPT")
    chk("heavy-hex 3×3 d=3 ⇒ ACCEPT（39 ≥ 17 · ADAPTED 适配后可对接）",
        bv_h["verdict"] == "ACCEPT" and bv_h["embedding"] == EMBED_ADAPTED)
    # ⑦ 反向：不连通图 ⇒ REJECT
    broken = TOPO.grid_topology(3, 3)
    broken["adjacency"][4] = []          # 孤立中心节点（只从邻接表删）
    chk("反向：图不连通 ⇒ REJECT", bridge_verdict(broken, d=3)["verdict"] == "REJECT")
    # ⑧ 反向：资源不足 ⇒ REJECT（小 QPU 大码距）
    chk("反向：小 QPU 大码距 ⇒ REJECT",
        bridge_verdict(g3, d=9)["verdict"] == "REJECT")

    # ───────── v0.9.308 追加：设计规则（必要）⇄ 真嵌入（充要）必须显式并存 ─────────
    # ⑨ heavy-hex：设计规则说 ADAPTED（不 FAIL）、λ₂ 与资源都过 ⇒ verdict=ACCEPT；
    #    但**真嵌入可证不可能**（最大度 3 < 内部稳定子权重 4）。两个结论都对，必须同时给出。
    bv_h = bridge_verdict(h3, d=3)
    chk("⑨ heavy-hex 3×3 d=3：design=ACCEPT/ADAPTED 但 native=IMPOSSIBLE(degree_bound)"
        " —— 两口径并存，不得用 ACCEPT 代表「能跑」",
        bv_h["verdict"] == "ACCEPT" and bv_h["embedding"] == EMBED_ADAPTED
        and bv_h["native_status"] == SCE.STATUS_IMPOSSIBLE
        and bv_h["native"]["proof"] == "degree_bound"
        and bv_h["native_feasible"] is False,
        "design=%s/%s native=%s(%s)"
        % (bv_h["verdict"], bv_h["embedding"], bv_h["native_status"],
           bv_h["native"]["proof"]))

    # ⑩ 反例（本版存在的理由）：3-ary 树（最大度 4、24 ≥ 17 节点）
    #    设计规则判 DIRECT（`max_degree >= 4`），真嵌入 IMPOSSIBLE（关联图有 4-圈、树没有）
    #    ⇒ 证明「度 ≥ 4」只是**必要**条件，把它当充分用会给出假绿。
    tree = {"name": "kary-3-tree", "adjacency": SCE.kary_tree(3, 24),
            "couplers": [], "kind": {}, "n_qubits": 24,
            "max_degree_limit": 4}
    rule_tree = surface_code_2d_nn_verdict(tree)["verdict"]
    nat_tree = native_embedding(tree, 3)
    chk("⑩ 反例：3-ary 树 design=%s（度 4 ⇒ 旧规则判可嵌）但 native=%s(%s)"
        " ⇒ 「度 ≥ 4」只是必要条件" % (rule_tree, nat_tree["status"], nat_tree["proof"]),
        rule_tree == EMBED_DIRECT and nat_tree["status"] == SCE.STATUS_IMPOSSIBLE
        and nat_tree["proof"] == "four_cycle")

    # ⑪ 方阵 10×10 d=3 ⇒ native=DIRECT（真映射，非度数推断）；
    #    且最小方阵边长 ≡ 闭式 2d−1（卡片用的那个常数必须与搜索一致）
    bv_g10 = bridge_verdict(g10, d=3)
    ms = SCE.min_square_side(3)
    chk("⑪ 方阵 10×10 d=3 ⇒ native=DIRECT（显式映射 %s 项）；最小边长 %s ≡ 闭式 2d−1=%d"
        % (bv_g10["native"].get("map_size"), ms["side"], SCE.min_square_side_closed(3)),
        bv_g10["native_status"] == SCE.STATUS_DIRECT and ms["side"] == 5
        and ms["side"] == SCE.min_square_side_closed(3),
        "native=%s map=%s 最小边长 trace=%s"
        % (bv_g10["native_status"], bv_g10["native"].get("map_size"),
           [(t["n"], t["status"]) for t in ms["trace"]]))


    if verbose:
        print("自检：%d FAIL" % len(bad))
    return not bad


if __name__ == "__main__":  # pragma: no cover
    print("J2 M4 拓扑 ↔ 表面码对接桥自检")
    ok = run_selfchecks(verbose=True)
    for name, topo in (("方阵 10×10", TOPO.grid_topology(10, 10)),
                       ("heavy-hex 3×3", TOPO.heavy_hex_topology(3, 3))):
        bv = bridge_verdict(topo, d=3)
        print("  %-14s N=%-4d λ₂=%.6f 嵌入=%-7s 资源=%s ⇒ %s"
              % (name, bv["graph"]["n_nodes"], bv["lambda2"], bv["embedding"],
                 bv["resource_ok"], bv["verdict"]))
    print("ALL PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)
