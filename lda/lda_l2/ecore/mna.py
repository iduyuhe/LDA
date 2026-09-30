# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E1 · 改进节点法（MNA）电路仿真器。

============================================================================
设计定位（吃狗粮：平台此前**只能生成网表、不能仿真电路**——`spice_netlist.py`
只导出 SPICE/Spectre 文本，无求解器）
----------------------------------------------------------------------------
本模块填补平台**电路仿真**空白：一个纯 numpy 的 MNA 求解器，支持
  · R / C（瞬态用后向欧拉）/
  · 独立电压源 Vsrc / 独立电流源 Isrc /
  · 压控电压源 VCVS（理想运放建模为超大增益 VCVS）/
  · 非线性 NMOS（牛顿迭代伴随模型，见 `mosfet.id_gm_gds`）。
三种分析：DC 工作点（牛顿）、瞬态（后向欧拉时间步进）、AC 小信号（复数）。

主权纪律（全平台同源）：C 级自主（纯 numpy），不借任何商业 SPICE 引擎；
LLM 不进判决路径；golden 须为闭式物理律（分压 / 平方律 / RC 一阶响应）。

🔴 诚实边界：本仿真器是**电路级教学/设计验证引擎**，不是签核级 SPICE（无温度/
噪声/非线性收敛增强/稀疏矩阵）。结论用于平台能力与架构验证，不宣称签核精度。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .mosfet import NmosParams, id_gm_gds


# ---------------------------------------------------------------------------
# 参考地钉扎（修正 MNA 规范自由度 / gauge）：节点 0 = 地，恒为参考、不进未知量。
# 若不解钉扎，整个解可整体平移常数 ⇒ 矩阵奇异。钉扎后 V(0)=0，其余节点方程非奇异。
# 节点集含 0 且经 sorted 后 0 恒为最小索引 ⇒ 地行索引恒为 0。
# ---------------------------------------------------------------------------
def _pin_ground(A: np.ndarray, b: np.ndarray) -> None:
    A[0, :] = 0.0
    A[0, 0] = 1.0
    b[0] = 0.0


# ---------------------------------------------------------------------------
# 电路组装器
# ---------------------------------------------------------------------------
class Circuit:
    """改进节点法电路：节点用整数（0 = 地）。牛顿迭代处理 NMOS。

    元素类型：
      R  : 电阻（线性）
      C  : 电容（瞬态/AC）
      V  : 独立电压源（线性，增广一行）
      I  : 独立电流源（线性，进 RHS）
      E  : 压控电压源 VCVS（线性，增益 A，增广一行）
      M  : NMOS（非线性，3 端 d/g/s，源=体参考，牛顿伴随模型）
    """

    def __init__(self, name: str = "ckt"):
        self.name = name
        self._elems: List[dict] = []
        self._nodes: set = {0}

    def _nid(self, n: int) -> int:
        self._nodes.add(n)
        return n

    # —— 构建 API ——
    def resistor(self, n1: int, n2: int, r: float, tag: str = "") -> "Circuit":
        if r <= 0:
            raise ValueError("电阻必须 > 0")
        self._elems.append({"type": "R", "a": self._nid(n1), "b": self._nid(n2),
                            "r": float(r), "tag": tag})
        return self

    def capacitor(self, n1: int, n2: int, c: float, tag: str = "") -> "Circuit":
        if c <= 0:
            raise ValueError("电容必须 > 0")
        self._elems.append({"type": "C", "a": self._nid(n1), "b": self._nid(n2),
                            "c": float(c), "tag": tag})
        return self

    def vsource(self, n1: int, n2: int, v: float, tag: str = "") -> "Circuit":
        """独立电压源，n1 为正端、n2 为负端，电压 = v（DC）。"""
        self._elems.append({"type": "V", "a": self._nid(n1), "b": self._nid(n2),
                            "v": float(v), "tag": tag})
        return self

    def isource(self, n1: int, n2: int, i: float, tag: str = "") -> "Circuit":
        """独立电流源，电流从 n1 流向 n2（DC / AC 幅值）。"""
        self._elems.append({"type": "I", "a": self._nid(n1), "b": self._nid(n2),
                            "i": complex(i), "tag": tag})
        return self

    def vcvs(self, out_p: int, out_n: int, ctl_p: int, ctl_n: int, gain: float,
             tag: str = "") -> "Circuit":
        """压控电压源：V(out_p)−V(out_n) = gain·(V(ctl_p)−V(ctl_n))。

        用于建模**理想运放**（gain 很大，如 1e6）；线性元素。
        """
        self._elems.append({"type": "E", "op": self._nid(out_p), "on": self._nid(out_n),
                            "cp": self._nid(ctl_p), "cn": self._nid(ctl_n),
                            "gain": float(gain), "tag": tag})
        return self

    def nmos(self, drain: int, gate: int, source: int, p: Optional[NmosParams] = None,
             tag: str = "") -> "Circuit":
        """NMOS：d/g/s 三端（源=体参考）。非线性，DC 用牛顿伴随模型。"""
        self._elems.append({"type": "M", "d": self._nid(drain), "g": self._nid(gate),
                            "s": self._nid(source),
                            "p": p or NmosParams(), "tag": tag})
        return self

    # —— 节点 / 增广维度 ——
    def _setup(self) -> Tuple[int, int]:
        nodes = sorted(self._nodes)
        n_node = len(nodes)
        node_idx = {n: i for i, n in enumerate(nodes)}   # 含 0
        n_branch = sum(1 for e in self._elems if e["type"] in ("V", "E"))
        return n_node, n_branch, node_idx

    # ------------------------------------------------------------------
    # DC 工作点（牛顿迭代，含 NMOS 伴随模型）
    # ------------------------------------------------------------------
    def solve_dc(self, v0: Optional[Dict[int, float]] = None, tol: float = 1e-10,
                 max_iter: int = 200) -> np.ndarray:
        n_node, n_branch, nidx = self._setup()
        m = n_node + n_branch
        # 初始猜测：所有节点 0（地已为 0）；可给 v0 覆盖
        x = np.zeros(m)
        if v0:
            for n, v in v0.items():
                if n in nidx:
                    x[nidx[n]] = v

        branch_elems = [e for e in self._elems if e["type"] in ("V", "E")]
        # 分支电流变量从 n_node 开始
        for k, e in enumerate(branch_elems):
            e["_bix"] = n_node + k

        for _ in range(max_iter):
            A = np.zeros((m, m))
            b = np.zeros(m)
            for e in self._elems:
                self._stamp_dc(A, b, e, x, nidx)
            _pin_ground(A, b)
            try:
                x_new = np.linalg.solve(A, b)
            except np.linalg.LinAlgError:
                raise RuntimeError("MNA DC 矩阵奇异（电路定义可能缺参考/开路）")
            dx = np.max(np.abs(x_new - x))
            x = x_new
            if dx < tol:
                return x
        raise RuntimeError("MNA DC 牛顿迭代未收敛（%d 步）" % max_iter)

    def _stamp_dc(self, A, b, e, x, nidx) -> None:
        t = e["type"]
        if t == "R":
            g = 1.0 / e["r"]
            a, bb = nidx[e["a"]], nidx[e["b"]]
            A[a, a] += g; A[bb, bb] += g; A[a, bb] -= g; A[bb, a] -= g
        elif t == "V":
            a, bb = nidx[e["a"]], nidx[e["b"]]
            ix = e["_bix"]
            A[a, ix] += 1.0; A[bb, ix] -= 1.0
            A[ix, a] += 1.0; A[ix, bb] -= 1.0
            b[ix] = e["v"]
        elif t == "I":
            a, bb = nidx[e["a"]], nidx[e["b"]]
            # 电流源从 a 流向 b（离开 a）= i；KCL 离开=0 ⇒ 离开 a 含 +i ⇒ 移右：b[a] -= i
            b[a] -= complex(e["i"]).real
            b[bb] += complex(e["i"]).real
        elif t == "E":
            op, on = nidx[e["op"]], nidx[e["on"]]
            cp, cn = nidx[e["cp"]], nidx[e["cn"]]
            ix = e["_bix"]
            A[op, ix] += 1.0; A[on, ix] -= 1.0
            A[ix, op] += 1.0; A[ix, on] -= 1.0
            # Vout − A·(Vcp − Vcn) = 0 ⇒ 移到 LHS：A[ix][cp] += A_gain; A[ix][cn] -= A_gain
            A[ix, cp] += e["gain"]; A[ix, cn] -= e["gain"]
        elif t == "M":
            self._stamp_mosfet_dc(A, b, e, x, nidx)

    def _stamp_mosfet_dc(self, A, b, e, x, nidx) -> None:
        d, g, s = nidx[e["d"]], nidx[e["g"]], nidx[e["s"]]
        vg = x[g]; vd = x[d]; vs_node = x[s]
        vgs = vg - vs_node
        vds = vd - vs_node
        p = e["p"]
        id0, gm, gds = id_gm_gds(vgs, vds, p)
        # 伴随模型（源=体参考，Vsb=0）：Id 随 Vg/Vd/Vs 的线性化
        # 漏极 KCL（离开漏极 = Id）：+gds·Vd + gm·Vg − (gm+gds)·Vs + 常量
        A[d, d] += gds
        A[d, g] += gm
        A[d, s] += -(gm + gds)
        rhs_d = -id0 + gm * vg + gds * vd - (gm + gds) * vs_node
        b[d] += rhs_d
        # 源极 KCL（离开源极 = −Id）：与上反号
        A[s, d] += -gds
        A[s, g] += -gm
        A[s, s] += (gm + gds)
        b[s] += -rhs_d

    def node_voltages(self, x: np.ndarray, nidx: Optional[Dict[int, int]] = None) -> Dict[int, float]:
        if nidx is None:
            _, _, nidx = self._setup()
        return {n: float(x[nidx[n]]) for n in nidx}

    def branch_currents(self, x: np.ndarray) -> Dict[str, float]:
        """分支电流（V / E 元素）：{tag: I}。

        电流符号约定：**从元素 a 端流向 b 端为正**。电压源/VCVS 的电流是 MNA 的
        增广未知量，`solve_dc` / `solve_transient` / `solve_ac` 后可直接读出。
        典型用法（E7 后仿）：把某节点经 `vsource(node, 0, 0.0)` 接地作**0 V 电流表**
        （理想 TIA 虚地），分支电流即流入该节点的电流。

        🔴 须在 solve_* **之后**调用（分支索引在求解时写入）；无 tag 的元素以
        `br{index}` 命名。
        """
        out: Dict[str, float] = {}
        for e in self._elems:
            if e["type"] in ("V", "E") and "_bix" in e:
                key = e.get("tag") or f"br{e['_bix']}"
                out[key] = float(x[e["_bix"]])
        return out

    # ------------------------------------------------------------------
    # 瞬态（后向欧拉）
    # ------------------------------------------------------------------
    def solve_transient(self, t_end: float, n_steps: int, dt: Optional[float] = None,
                        v0: Optional[Dict[int, float]] = None, tol: float = 1e-10,
                        max_iter: int = 200) -> Tuple[np.ndarray, np.ndarray]:
        if dt is None:
            dt = t_end / n_steps
        n_node, n_branch, nidx = self._setup()
        m = n_node + n_branch
        branch_elems = [e for e in self._elems if e["type"] in ("V", "E")]
        for k, e in enumerate(branch_elems):
            e["_bix"] = n_node + k
        # 电容初始电压（来自 v0 或 0）
        v_prev = np.zeros(m)
        if v0:
            for nn, vv in v0.items():
                if nn in nidx:
                    v_prev[nidx[nn]] = vv
        times = np.linspace(0.0, t_end, n_steps + 1)
        out = np.zeros((n_steps + 1, n_node))
        out[0] = v_prev[:n_node]
        for step in range(1, n_steps + 1):
            x = v_prev.copy()
            for _ in range(max_iter):
                A = np.zeros((m, m))
                b = np.zeros(m)
                for e in self._elems:
                    self._stamp_transient(A, b, e, x, v_prev, dt, nidx)
                _pin_ground(A, b)
                try:
                    x_new = np.linalg.solve(A, b)
                except np.linalg.LinAlgError:
                    raise RuntimeError("MNA 瞬态矩阵奇异")
                if np.max(np.abs(x_new - x)) < tol:
                    x = x_new
                    break
                x = x_new
            else:
                raise RuntimeError("MNA 瞬态牛顿未收敛（步 %d）" % step)
            v_prev = x
            out[step] = x[:n_node]
        return times, out

    def _stamp_transient(self, A, b, e, x, v_prev, dt, nidx) -> None:
        t = e["type"]
        if t == "C":
            # 电容：后向欧拉伴随模型（Geq + 历史电流源）
            geq = e["c"] / dt
            a, bb = nidx[e["a"]], nidx[e["b"]]
            A[a, a] += geq; A[bb, bb] += geq; A[a, bb] -= geq; A[bb, a] -= geq
            # 伴随电流源（从 a 流向 b 的等效电流）Ieq = −geq·(Vprev_a − Vprev_b)
            # （后向欧拉：i_cap = geq·(Va−Vb) − geq·Vc_old，故离开 a 的等效电流源 = −geq·Vc_old）
            # ⇒ b[a] -= Ieq, b[bb] += Ieq
            ieq = -geq * (v_prev[a] - v_prev[bb])
            b[a] -= ieq; b[bb] += ieq
        else:
            # 非电容元素：瞬态每步同 DC 线性化（电阻/源为定常，MOSFET 牛顿伴随）
            self._stamp_dc_noncap(A, b, e, x, nidx)


    def _stamp_dc_noncap(self, A, b, e, x, nidx) -> None:
        """瞬态专用：仅作非电容类的 DC stamp（避免 _stamp_dc 误处理电容）。"""
        t = e["type"]
        if t == "R":
            g = 1.0 / e["r"]; a, bb = nidx[e["a"]], nidx[e["b"]]
            A[a, a] += g; A[bb, bb] += g; A[a, bb] -= g; A[bb, a] -= g
        elif t == "V":
            a, bb = nidx[e["a"]], nidx[e["b"]]; ix = e["_bix"]
            A[a, ix] += 1.0; A[bb, ix] -= 1.0; A[ix, a] += 1.0; A[ix, bb] -= 1.0
            b[ix] = e["v"]
        elif t == "I":
            a, bb = nidx[e["a"]], nidx[e["b"]]
            b[a] -= complex(e["i"]).real; b[bb] += complex(e["i"]).real
        elif t == "E":
            op, on = nidx[e["op"]], nidx[e["on"]]; cp, cn = nidx[e["cp"]], nidx[e["cn"]]
            ix = e["_bix"]
            A[op, ix] += 1.0; A[on, ix] -= 1.0; A[ix, op] += 1.0; A[ix, on] -= 1.0
            A[ix, cp] += e["gain"]; A[ix, cn] -= e["gain"]
        elif t == "M":
            self._stamp_mosfet_dc(A, b, e, x, nidx)

    # ------------------------------------------------------------------
    # AC 小信号（复数线性化 around DC 工作点）
    # ------------------------------------------------------------------
    def solve_ac(self, freq_hz: float, dc_x: Optional[np.ndarray] = None,
                 ac_sources: Optional[Dict[Tuple[int, int], complex]] = None) -> Tuple[np.ndarray, np.ndarray]:
        """AC 小信号：在 DC 工作点线性化，电容导纳 = jωC。

        ac_sources：{(n1,n2): 复幅值}，作为独立 AC 电流源注入（n1→n2）。
        返回 (freq, V_complex)，V 按节点序。
        """
        n_node, n_branch, nidx = self._setup()
        m = n_node + n_branch
        branch_elems = [e for e in self._elems if e["type"] in ("V", "E")]
        for k, e in enumerate(branch_elems):
            e["_bix"] = n_node + k
        if dc_x is None:
            dc_x = self.solve_dc()
        w = 2.0 * math.pi * freq_hz
        A = np.zeros((m, m), dtype=complex)
        b = np.zeros(m, dtype=complex)
        for e in self._elems:
            self._stamp_ac(A, b, e, dc_x, w, nidx)
        if ac_sources:
            for (n1, n2), amp in ac_sources.items():
                a, bb = nidx[n1], nidx[n2]
                b[a] -= amp; b[bb] += amp
        # 🔴 钉扎必须在 AC 电流源注入之后：注入若落在地节点(0)须被参考钉扎吸收，
        # 否则 b[0]≠0 会污染参考、错位传导到其他节点。
        _pin_ground(A, b)
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            raise RuntimeError("MNA AC 矩阵奇异")
        return w, x[:n_node]

    def _stamp_ac(self, A, b, e, dc_x, w, nidx) -> None:
        t = e["type"]
        if t == "R":
            g = 1.0 / e["r"]; a, bb = nidx[e["a"]], nidx[e["b"]]
            A[a, a] += g; A[bb, bb] += g; A[a, bb] -= g; A[bb, a] -= g
        elif t == "C":
            y = 1j * w * e["c"]; a, bb = nidx[e["a"]], nidx[e["b"]]
            A[a, a] += y; A[bb, bb] += y; A[a, bb] -= y; A[bb, a] -= y
        elif t == "V":
            a, bb = nidx[e["a"]], nidx[e["b"]]; ix = e["_bix"]
            A[a, ix] += 1.0; A[bb, ix] -= 1.0; A[ix, a] += 1.0; A[ix, bb] -= 1.0
        elif t == "I":
            a, bb = nidx[e["a"]], nidx[e["b"]]
            b[a] -= complex(e["i"]); b[bb] += complex(e["i"])
        elif t == "E":
            op, on = nidx[e["op"]], nidx[e["on"]]; cp, cn = nidx[e["cp"]], nidx[e["cn"]]
            ix = e["_bix"]
            A[op, ix] += 1.0; A[on, ix] -= 1.0; A[ix, op] += 1.0; A[ix, on] -= 1.0
            A[ix, cp] += e["gain"]; A[ix, cn] -= e["gain"]
        elif t == "M":
            # 小信号：在 DC 工作点取 gm/gds，以电导 stamp（同 DC 伴随，但复矩阵）
            d, g, s = nidx[e["d"]], nidx[e["g"]], nidx[e["s"]]
            vg, vd, vs_node = dc_x[g], dc_x[d], dc_x[s]
            _, gm, gds = id_gm_gds(vg - vs_node, vd - vs_node, e["p"])
            A[d, d] += gds; A[d, g] += gm; A[d, s] += -(gm + gds)
            A[s, d] += -gds; A[s, g] += -gm; A[s, s] += (gm + gds)
