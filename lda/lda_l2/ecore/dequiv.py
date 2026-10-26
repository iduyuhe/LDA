# -*- coding: utf-8 -*-
"""E34 · **等价性双引擎穷举对拍 + 判别力（响应率 ρ）**（`lda/lda_l2/ecore/dequiv.py` · D-214）。

══════════════════════════════════════════════════════════════════════════
定位：E34 唯一的**绝对判据** —— 综合器对不对，不靠看，靠穷举
══════════════════════════════════════════════════════════════════════════
引擎 A（`drtl.rtl_eval_all`，Python 整数按位运算）
引擎 B（`dsynth.sim_netlist`，逐单元查真值表）
两者**代码路径零共享** ⇒ 任何一侧的位宽/进位/优先级/极性错误都只能落在一边。

判据形式：**逐位相等，容差 0**。（不是 5%，不是「趋势一致」——比值判据在这里毫无意义。）

══════════════════════════════════════════════════════════════════════════
🔴🔴 E34 的「判据自证」风险，以及为什么必须单列 `ρ`
══════════════════════════════════════════════════════════════════════════
E31/E32 的教训：「8 项判据全放得过不能失败的候选」。等价性检查尤其危险：

| 假绿 | 为什么穷举会绿 | 防线 |
|---|---|---|
| 综合器其实没综合 | 网表 = 输入直通 ⇒ A 与 B 都等于 RTL | `dsynth.netlist_authenticity` + `passthru` 报告 |
| 输出端口漏接 | 只比了「存在的」输出 | `_check_port_alignment`：端口集合与位宽**双向**相等 |
| 模块输出与门无关 | 全部向量都相等（如输出恒 0） | **`ρ` = 单门扰动被抓住的比例**，必须高 |
| 只跑了一个向量 | 单点测试 | 位宽 ≤ 阈值时**全穷举**，且报 `n_vectors` 实际值 |

🔴 `ρ`（响应率）的定义刻意与 314/315 的教训对齐：
    **ρ ≡ 单门扰动中被至少一个向量判红的比例**
ρ ≈ 1 才说明「这个判据对网表的每一处都敏感」；ρ 低 ⇒ 判据本身没判别力，
**绿也不算数**。这是把「测试点太单一」（E13 G4 只跑 L=100nm）变成数值指标。
"""
from __future__ import annotations

import random

from . import drtl as RT
from . import dsynth as SY
from .dsynth import Gate, Netlist

#: 输入位数 ≤ 此值时**全穷举**（2^14 = 16384 向量）
EXHAUSTIVE_MAX_BITS = 14
#: 超过时的随机向量数
RANDOM_VECTORS = 4096
#: 判别力测试使用的向量数（每个扰动都跑一遍）
RHO_VECTORS = 256


class EquivError(Exception):
    pass


# ---------------------------------------------------------------------------
# 向量枚举
# ---------------------------------------------------------------------------
def n_bits(nl) -> int:
    return sum(w for _, w in nl.inputs)


def unpack(vec: int, nl) -> dict:
    pin = {}
    sh = 0
    for port, w in nl.inputs:
        pin[port] = (vec >> sh) & ((1 << w) - 1)
        sh += w
    return pin


def _check_port_alignment(m: RT.Module, nl) -> list:
    """端口集合与位宽**双向**相等 —— 防「漏接一个输出 ⇒ 只看剩下的」。"""
    problems = []
    want_in = list(m.comb_inputs())
    got_in = [p for p, _ in nl.inputs]
    if want_in != got_in:
        problems.append(("inputs_order", want_in, got_in))
    for p, w in nl.inputs:
        src = p[:-2] if p.endswith("@q") else p
        if w != m.widths.get(src, 1):
            problems.append(("input_width", p, w, m.widths.get(src, 1)))
    want_out = list(m.comb_outputs())
    got_out = sorted(nl.outputs)
    if sorted(want_out) != got_out:
        problems.append(("outputs_set", sorted(want_out), got_out))
    for p in want_out:
        src = p[:-2] if p.endswith("@d") else p
        w_want = m.widths.get(src, 1)
        w_got = len(nl.outputs.get(p, ()))
        if w_got != w_want:
            problems.append(("output_width", p, w_got, w_want))
    return problems


def _vectors(nl, seed: int = 1):
    """产出 `(vec, exhaustive_flag)`。位宽小 ⇒ 全穷举；否则随机 + 定向角点。"""
    nb = n_bits(nl)
    if nb <= EXHAUSTIVE_MAX_BITS:
        for v in range(1 << nb):
            yield v
        return
    rng = random.Random(seed)
    seen = set()
    # 定向角点：全 0 / 全 1 / 单比特走 1 —— 覆盖「进位链」「全相等」等边界
    cand = [0, (1 << nb) - 1]
    for i in range(nb):
        cand.append(1 << i)
        cand.append(((1 << nb) - 1) ^ (1 << i))
    for v in cand:
        if v not in seen:
            seen.add(v)
            yield v
    for _ in range(RANDOM_VECTORS):
        v = rng.getrandbits(nb)
        if v not in seen:
            seen.add(v)
            yield v


def compare_on(m: RT.Module, nl, vec: int):
    """单个向量上双引擎比较，返回 `None` 或 `(port, bit, a, b)`。"""
    pin = unpack(vec, nl)
    a = RT.rtl_eval_all(m, pin)
    b = SY.sim_netlist(nl, pin)
    for p in m.comb_outputs():
        va = a.get(p)
        vb = b.get(p)
        if va is None or vb is None:
            return (p, -1, va, vb)
        if va != vb:
            diff = va ^ vb
            bit = (diff & -diff).bit_length() - 1
            return (p, bit, va, vb)
    return None


# ---------------------------------------------------------------------------
# 等价性主判据
# ---------------------------------------------------------------------------
def equiv(m: RT.Module, nl, seed: int = 1, limit_fail: int = 5) -> dict:
    problems = _check_port_alignment(m, nl)
    if problems:
        return {"ok": False, "alignment": problems, "n_vectors": 0,
                "exhaustive": False, "mismatches": [], "n_bits": n_bits(nl)}

    nb = n_bits(nl)
    exhaustive = nb <= EXHAUSTIVE_MAX_BITS
    mism = []
    cnt = 0
    for v in _vectors(nl, seed):
        cnt += 1
        bad = compare_on(m, nl, v)
        if bad is not None:
            mism.append((v,) + bad)
            if len(mism) >= limit_fail:
                break
    return {
        "ok": not mism,
        "alignment": [],
        "n_vectors": cnt,
        "exhaustive": exhaustive,
        "n_bits": nb,
        "space": 1 << nb,
        "coverage": (cnt / float(1 << nb)) if nb <= 62 else None,
        "mismatches": mism,
    }


# ---------------------------------------------------------------------------
# 判别力：响应率 ρ
# ---------------------------------------------------------------------------
_SWAP = {
    "NAND2": "NOR2",
    "NOR2": "NAND2",
    "INV": "BUF",
    "BUF": "INV",
    "NAND3": "NOR3",
    "NOR3": "NAND3",
    "AND2": "OR2",
    "OR2": "AND2",
    "AOI21": "OAI21",
    "OAI21": "AOI21",
}


def _mutate(nl, idx: int, new_cell: str) -> Netlist:
    g = nl.gates[idx]
    gates = list(nl.gates)
    gates[idx] = Gate(g.name, new_cell, g.ins, g.out)
    return Netlist(name=nl.name + "_mut", inputs=nl.inputs,
                   in_nets=dict(nl.in_nets), outputs=dict(nl.outputs),
                   gates=gates, clocks=nl.clocks)


def rho(m: RT.Module, nl, n_probe: int = RHO_VECTORS) -> dict:
    """**响应率 ρ**：单门扰动中被抓到的比例。`ρ≈1` 才说明判据对网表处处敏感。"""
    comb_idx = [i for i, g in enumerate(nl.gates) if g.cell in _SWAP]
    if not comb_idx:
        return {"rho": None, "n_trials": 0, "n_detected": 0,
                "note": "网表内无可扰动组合门"}

    probes = []
    nb = n_bits(nl)
    rng = random.Random(7)
    probes.append(0)
    probes.append((1 << nb) - 1)
    while len(probes) < min(n_probe, max(2, 1 << nb)):
        probes.append(rng.getrandbits(nb))

    base = []
    for v in probes:
        pin = unpack(v, nl)
        base.append(RT.rtl_eval_all(m, pin))

    detected = 0
    flips = 0
    for i in comb_idx:
        nm = _mutate(nl, i, _SWAP[nl.gates[i].cell])
        hit = False
        for k, v in enumerate(probes):
            try:
                got = SY.sim_netlist(nm, unpack(v, nl))
            except Exception:        # noqa: BLE001  — 扰动后结构失效也算「被抓到」
                hit = True
                flips += 1
                break
            if any(got[p] != base[k].get(p) for p in m.comb_outputs()):
                hit = True
                flips += 1
                break
        if hit:
            detected += 1
    return {
        "rho": detected / float(len(comb_idx)),
        "n_trials": len(comb_idx),
        "n_detected": detected,
        "n_flip_vectors": flips,
        "n_probe_vectors": len(probes),
    }


# ---------------------------------------------------------------------------
# 锁步序列对拍（覆盖**可达状态空间**——随机向量对 70 位输入毫无意义）
# ---------------------------------------------------------------------------
def lockstep(m: RT.Module, nl, n_cycles: int, stimulus, init_state=None,
             limit_fail: int = 5) -> dict:
    """**双引擎锁步**：两条引擎各自维护状态轨迹，逐拍比对全部输出与 D 端。

    为什么必须有这一条：完整控制壳的输入位数（主输入 + 51 位状态）远超可穷举范围，
    `equiv` 的随机向量在 2^70 空间里等于零覆盖 —— **绿也不是证据**。
    锁步跑的是**真实可达状态序列**（复位 → 扫描 → 累加 → 换位平面 → 读回），
    这才是 FSM 类设计的有效覆盖。

    🔴 两条轨迹**独立推进**（`st_a` 由引擎 A 推进、`st_b` 由引擎 B 推进），
    任一侧状态先偏，后续输出必然分歧 ⇒ 缺陷不会被「都用同一份状态」掩盖。
    """
    st_a = dict(init_state or {})
    st_b = dict(init_state or {})
    mism = []
    checked = 0
    #: 每个输出的**历史最大值** —— 用来证明「done 真的起过、busy 真的落过」，
    #: 而不是只看最后一拍（回到 IDLE 后 done 会被清，末拍看不出来）。
    hist = {}
    for cyc in range(n_cycles):
        base = dict(stimulus(cyc))
        pa = dict(base)
        pb = dict(base)
        for reg, v in st_a.items():
            pa[reg + "@q"] = v
        for reg, v in st_b.items():
            pb[reg + "@q"] = v
        a = RT.rtl_eval_all(m, pa)
        b = SY.sim_netlist(nl, pb)
        for p in m.comb_outputs():
            checked += 1
            va = a.get(p)
            if isinstance(va, int) and va > hist.get(p, -1):
                hist[p] = va
            if va != b.get(p):
                mism.append((cyc, p, va, b.get(p)))
        for reg in sorted(m.state_regs):
            st_a[reg] = a.get(reg + "@d", 0)
            st_b[reg] = b.get(reg + "@d", 0)
        if len(mism) >= limit_fail:
            break
    return {"ok": not mism, "n_cycles": cyc + 1, "n_checked": checked,
            "mismatches": mism, "final_state": dict(sorted(st_a.items())),
            "max_of": {k: v for k, v in sorted(hist.items()) if not k.endswith("@d")}}


# ---------------------------------------------------------------------------
# 自检（含「必须失败」的对照组）
# ---------------------------------------------------------------------------
_CASES = {
    "adder4": """
module t(a, b, y);
  input [3:0] a; input [3:0] b; output [4:0] y;
  assign y = a + b;
endmodule
""",
    "mux_tree": """
module t(s, a, b, c, d, y);
  input [1:0] s; input [3:0] a; input [3:0] b; input [3:0] c; input [3:0] d;
  output [3:0] y;
  assign y = s[1] ? (s[0] ? d : c) : (s[0] ? b : a);
endmodule
""",
    "cmp_mix": """
module t(a, b, y);
  input [3:0] a; input [3:0] b; output [2:0] y;
  assign y = {a == b, a < b, a[0] ^ b[3]};
endmodule
""",
    "sub_shift": """
module t(a, b, y);
  input [5:0] a; input [5:0] b; output [5:0] y;
  assign y = ((a - b) >> 1) | {a[0], b[5], 4'd0};
endmodule
""",
    "fsm_like": """
module t(clk, go, cnt, out);
  input clk; input go; input [2:0] cnt; output [3:0] out; reg [3:0] out;
  reg [2:0] n;
  always @(*) begin
    n = cnt;
    if (go) n = cnt + 1;
  end
  always @(posedge clk) begin
    case (n)
      3'd0: out <= 4'd1;
      3'd1: out <= 4'd2;
      3'd2, 3'd3: out <= 4'd7;
      default: out <= {1'b0, n};
    endcase
  end
endmodule
""",
}


def equiv_self_check(verbose: bool = False) -> dict:
    """五个结构不同的用例 + 三个**必须打红**的对照组。"""
    problems = []
    rows = []
    for name, src in _CASES.items():
        m = RT.parse(src)
        nl = SY.synth(m)
        au = SY.netlist_authenticity(nl, m)
        if not au["ok"]:
            problems.append((name, "authenticity", au["problems"]))
        r = equiv(m, nl)
        if not r["ok"]:
            problems.append((name, "equiv", r["mismatches"][:2]))
        rr = rho(m, nl)
        rows.append((name, r["n_vectors"], r["exhaustive"], nl.n_gates(),
                     nl.n_dff(), rr["rho"]))
        if verbose:
            print("[CASE] %-10s vec=%-6d exh=%-5s gates=%-4d dff=%-2d rho=%s"
                  % (name, r["n_vectors"], r["exhaustive"], nl.n_gates(),
                     nl.n_dff(), rr["rho"]))
        # 🔴 ρ 必须接近 1（判据对每处都敏感）
        if rr["rho"] is None or rr["rho"] < 0.8:
            problems.append((name, "rho_too_low", rr))

    # ---- 对照组一：网表输出全接常数 0 ⇒ 等价性**必须**红 ----
    m = RT.parse(_CASES["adder4"])
    nl = SY.synth(m)
    bad = Netlist(name="const0", inputs=nl.inputs, in_nets=dict(nl.in_nets),
                  outputs={p: ("TIE0",) * len(nl.outputs[p]) for p in nl.outputs},
                  gates=[Gate("TIE0", "TIELO", (), "TIE0")] + list(nl.gates),
                  clocks=nl.clocks)
    if equiv(m, bad)["ok"]:
        problems.append(("const0_probe_not_red",))

    # ---- 对照组二：输出直通输入 ⇒ **必须**红 ----
    bad2 = Netlist(name="passthru", inputs=nl.inputs, in_nets=dict(nl.in_nets),
                   outputs={"y": tuple("in_a_%d" % i for i in range(4))
                            + ("TIE0",)},
                   gates=[Gate("TIE0", "TIELO", (), "TIE0")] + list(nl.gates),
                   clocks=nl.clocks)
    if equiv(m, bad2)["ok"]:
        problems.append(("passthru_probe_not_red",))

    # ---- 对照组三：单门扰动 ⇒ **必须**红（若某个扰动抓不到，ρ 会低于 1）----
    i0 = [i for i, g in enumerate(nl.gates) if g.cell == "NAND2"][0]
    if equiv(m, _mutate(nl, i0, "NOR2"))["ok"]:
        problems.append(("single_gate_probe_not_red",))

    return {"ok": not problems, "problems": problems, "rows": rows}


DEQUIV_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 5 层（等价性双引擎穷举 + 响应率 ρ）",
    "criterion": "引擎 A vs 引擎 B **逐位相等、容差 0**；端口集合与位宽双向相等",
    "coverage": "输入位宽 ≤ %d 全穷举（2^%d）；更大则定向角点（全 0/全 1/单比特/单比特取反）"
                " + %d 随机向量，且报实际向量数" % (EXHAUSTIVE_MAX_BITS, EXHAUSTIVE_MAX_BITS,
                                                  RANDOM_VECTORS),
    "rho": "ρ ≡ 单门扰动中被至少一个向量判红的比例；ρ < 0.8 视为**判据无判别力**（绿也不算数）",
    "control_groups": "① 输出全接常数 0 ② 输出直通输入 ③ 单门扰动 —— 三者**必须打红**",
    "not_included": "只做**单周期组合等价**（状态已外提为一级输入）· 无多周期复位序列等价 · "
                    "无 SAT 形式化等价（穷举/随机，不是证明）",
    "claimable": True,
    "claimable_reason": "这是本段唯一不依赖任何工艺参数、也不依赖任何拟合系数的判据",
}
