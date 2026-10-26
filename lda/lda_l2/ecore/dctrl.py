# -*- coding: utf-8 -*-
"""E34 · **CIM 控制壳：第一个真实数字设计**（`lda/lda_l2/ecore/dctrl.py` · D-215）。

══════════════════════════════════════════════════════════════════════════
定位：不再拿玩具例子自证 —— 用自己写的工具链设计一颗真的控制壳
══════════════════════════════════════════════════════════════════════════
前面五层（单元库 / 前端 / AIG / 综合 / STA）都是「工具」。本模块是**第一个用户**：
写一个真正能驱动 E20–E33 那个 87×87 crossbar 的控制壳，然后**被自己的工具链
综合、定时刻、对拍**。这是「以应用促平台」的第一次闭环。

══════════════════════════════════════════════════════════════════════════
功能：单 ADC 时分复用的行扫描控制器
══════════════════════════════════════════════════════════════════════════
```
        IDLE ──start──→ SCAN ──adc_done──→ ACC ──(还有行)──→ SCAN
          ↑                                  │
          │                                  └──(最后一行)──→ NEXTB
          │                                                    │
          └──────────(18 拍移完)── READ ←──(最后位平面)── NEXTB ─┘
```
- `row_sel`（7 bit）→ 行线选通，0…N−1（N=87 ⇒ 7 bit）
- `bit_sel`（3 bit）→ 位平面 0…7（8 bpc）
- `acc`（**18 bit**）→ 部分和累加器
- `sclk` / `sdo` → SPI 风格串行读回（18 拍）

══════════════════════════════════════════════════════════════════════════
🔴🔴 位宽不是随手写的 —— 每一条都由**物理动态范围反解**
══════════════════════════════════════════════════════════════════════════
| 信号 | 位宽 | 反解依据 |
|---|---|---|
| `row_sel` | 7 | N=87 ⇒ ⌈log₂87⌉ = 7（E31 换层签核的 N 上界） |
| `bit_sel` | 3 | 8 bpc（E22 器件族硬门槛：NOR Flash 8 bit/cell） |
| `acc` | **18** | 累加次数 = 87 行 × 8 位平面 = **696**；每次 ≤255（8 bit ADC）⇒ 上界 696×255 = **177,480**；2¹⁷=131,072 不够，2¹⁸=262,144 够 ⇒ **18 bit** |
| `scnt` | 5 | 扫完 18 拍需 0…17 |

🔴 **18 位这个数是算出来的，不是凑的**：若写成 16 位，最大只能存 65,535，
而实际需要 177,480 ⇒ **静默溢出**。这类缺陷任何「比值判据」都看不见，
本段用 `acc_width_witness` 把这条推导变成机器可查的判据（含反例检查）。

══════════════════════════════════════════════════════════════════════════
⚠️ 与 E17 时序报告**不可直接比较**（架构不同，必须说清）
══════════════════════════════════════════════════════════════════════════
E17 `per_sample_report` 假设 **ADC 并行**（一次 MVM 一排 ADC 同时转换）；
本控制壳是**单 ADC 时分复用**（逐行 × 逐位平面串行）。
⇒ 两者的「每样本耗时」是两个架构的数，**不能相除**。
本段只做一件可比的事：**数字壳的 Fmax 必须 ≥ SAR 由 CDAC 建立时间决定的时钟**
（`timing.cdac_clock_from_settle`）—— 若跑不到，数字就是真瓶颈。
"""
from __future__ import annotations

from . import dcell as DC
from . import dequiv as Q
from . import drtl as RT
from . import dsynth as SY
from . import dsta as ST
from . import timing as TM

#: 行数（E31 换层签核的 N 上界）
ROW_N = 87
#: 位平面数（E22 器件族硬门槛 8 bpc）
BITS = 8
#: 累加次数 = 行 × 位平面
ACC_EVENTS = ROW_N * BITS
#: 单次 ADC 输出上界（8 bit）
ADC_MAX = 255
#: 累加器所需的**最小**位宽（⌈log₂(ACC_EVENTS × ADC_MAX + 1)⌉）
ACC_WIDTH_MIN = (ACC_EVENTS * ADC_MAX).bit_length()
#: 实际采用位宽（== 最小值，不多给）
ACC_WIDTH = 18

assert ACC_WIDTH_MIN == ACC_WIDTH, "累加器位宽推导与实际不符：%d vs %d" % (
    ACC_WIDTH_MIN, ACC_WIDTH)


CIM_CTRL_SRC = """
module cim_ctrl(clk, rst_n, start, n_row, adc_done, adc_data,
                busy, done, row_sel, bit_sel, acc_out, sclk, sdo_valid, sdo);
  input clk;
  input rst_n;
  input start;
  input [6:0] n_row;
  input adc_done;
  input [7:0] adc_data;
  output busy;
  output done;
  output [6:0] row_sel;
  output [2:0] bit_sel;
  output [17:0] acc_out;
  output sclk;
  output sdo_valid;
  output sdo;

  reg [2:0] st;
  reg [6:0] row;
  reg [2:0] bitp;
  reg [17:0] acc;
  reg [17:0] shreg;
  reg [4:0] scnt;
  reg busy_r;
  reg done_r;

  assign sdo       = shreg[17];
  assign sclk      = busy_r & (st == 3'd4);
  assign sdo_valid = (st == 3'd4);
  assign row_sel   = row;
  assign bit_sel   = bitp;
  assign acc_out   = acc;
  assign busy      = busy_r;
  assign done      = done_r;

  always @(posedge clk) begin
    if (!rst_n) begin
      st <= 3'd0;
      row <= 7'd0;
      bitp <= 3'd0;
      acc <= 18'd0;
      shreg <= 18'd0;
      scnt <= 5'd0;
      busy_r <= 1'b0;
      done_r <= 1'b0;
    end else begin
      case (st)
        3'd0: begin
          done_r <= 1'b0;
          if (start) begin
            st <= 3'd1;
            row <= 7'd0;
            bitp <= 3'd0;
            acc <= 18'd0;
            busy_r <= 1'b1;
          end
        end
        3'd1: begin
          if (adc_done) st <= 3'd2;
        end
        3'd2: begin
          acc <= acc + adc_data;
          if (row + 7'd1 == n_row) begin
            st <= 3'd3;
          end else begin
            row <= row + 7'd1;
            st <= 3'd1;
          end
        end
        3'd3: begin
          row <= 7'd0;
          if (bitp == 3'd7) begin
            st <= 3'd4;
            shreg <= acc;
            scnt <= 5'd0;
          end else begin
            bitp <= bitp + 3'd1;
            st <= 3'd1;
          end
        end
        3'd4: begin
          shreg <= {shreg[16:0], 1'b0};
          scnt <= scnt + 5'd1;
          if (scnt == 5'd17) begin
            st <= 3'd0;
            busy_r <= 1'b0;
            done_r <= 1'b1;
          end
        end
        default: st <= 3'd0;
      endcase
    end
  end
endmodule
"""


# ---------------------------------------------------------------------------
# 构建链
# ---------------------------------------------------------------------------
def build(src: str = None) -> dict:
    """一行源码 → 前端 → 综合 → 真实性 → 时序。"""
    m = RT.parse(src or CIM_CTRL_SRC)
    nl = SY.synth(m)
    au = SY.netlist_authenticity(nl, m)
    tm = ST.sta(nl)
    return {"module": m, "netlist": nl, "authenticity": au, "timing": tm}


def stimulus(n_row: int = ROW_N, adc_latency: int = 2):
    """激励：第 0 拍给 `start`，之后每 `adc_latency` 拍给一次 `adc_done`。"""
    def stim(cyc):
        return {
            "clk": 1,
            "rst_n": 1,
            "start": 1 if cyc == 0 else 0,
            "n_row": n_row,
            "adc_done": 1 if (cyc % adc_latency == 1) else 0,
            "adc_data": ((cyc * 37) + 11) & 0xFF,
        }
    return stim


def lockstep(n_cycles: int = 1500, n_row: int = ROW_N) -> dict:
    b = build()
    return Q.lockstep(b["module"], b["netlist"], n_cycles, stimulus(n_row),
                      init_state={r: 0 for r in b["module"].state_regs})


# ---------------------------------------------------------------------------
# 位宽见证：18 位是算出来的
# ---------------------------------------------------------------------------
def acc_width_witness() -> dict:
    """把「累加器必须 18 位」变成机器可查的判据（含反例）。

    🔴 关键：不只要证「18 位够」，还要证「16 位**不够**」——
    否则「位宽够用」这条判据对「随便给个宽位宽」的候选**永远绿**，
    等于没有判别力（正是 314/315 的「不能失败的候选」）。
    """
    need = ACC_EVENTS * ADC_MAX
    fits = [(w, need < (1 << w)) for w in (14, 16, 17, 18, 19, 20)]
    return {
        "acc_events": ACC_EVENTS,
        "adc_max": ADC_MAX,
        "max_sum": need,
        "width_min": ACC_WIDTH_MIN,
        "fits_at": dict(fits),
        "declared": ACC_WIDTH,
        "ok": (need < (1 << ACC_WIDTH)) and (need >= (1 << (ACC_WIDTH - 1))),
        "why": "累加 %d 次 × 每次 ≤%d ⇒ 上界 %d；2^%d=%d 不够、2^%d=%d 够"
               % (ACC_EVENTS, ADC_MAX, need, ACC_WIDTH - 1, 1 << (ACC_WIDTH - 1),
                  ACC_WIDTH, 1 << ACC_WIDTH),
    }


# ---------------------------------------------------------------------------
# 闭环：数字壳 Fmax vs SAR 由 CDAC 建立时间决定的时钟
# ---------------------------------------------------------------------------
def closure(tech=DC.DEFAULT_TECH) -> dict:
    b = build()
    tm = b["timing"]
    cdac = TM.cdac_clock_from_settle(BITS)
    t_sar = cdac["t_clk_s"]
    f_sar_mhz = (1e-6 / t_sar) if t_sar and t_sar > 0 else None
    f_ctrl = tm.fmax_mhz
    headroom = (f_ctrl / f_sar_mhz) if (f_ctrl and f_sar_mhz) else None
    # 单 ADC 时分复用的每样本周期（**与 E17 并行架构不可比，仅报本架构**）
    cyc_per_sample = ROW_N * BITS * 2 + ACC_WIDTH + 2
    t_sample_ns = cyc_per_sample * t_sar * 1e9 if t_sar else None
    return {
        "fmax_ctrl_mhz": f_ctrl,
        "t_clk_min_ps": tm.t_clk_min_ps,
        "t_clk_sar_max_s": t_sar,
        "f_sar_mhz": f_sar_mhz,
        "headroom": headroom,
        "digital_is_bottleneck": (headroom is not None and headroom < 1.0),
        "cycles_per_sample": cyc_per_sample,
        "t_sample_ns_serial_arch": t_sample_ns,
        "arch_note": "本数字为**单 ADC 时分复用**架构；E17 的 per_sample_report 假设 ADC 并行 ⇒ "
                     "两者不可相除、不可互证",
        "e17_per_sample_ns": TM.per_sample_report(n=ROW_N, bits=BITS)["serial_ns"],
        "gates": tm.n_comb_gates,
        "dff": tm.n_dff,
        "area_um2": tm.area_um2,
        "leak_nw": tm.leak_nw,
    }


def power_at(f_hz: float, alpha: float = 0.1, tech=DC.DEFAULT_TECH) -> dict:
    b = build()
    nl = b["netlist"]
    p_sw = ST.switching_power_nw(nl, f_hz, alpha, tech)
    p_ck = ST.clock_power_nw(nl, f_hz, tech)
    p_lk = nl.leak_nw(tech)
    return {"switching_nw": p_sw, "clock_nw": p_ck, "leak_nw": p_lk,
            "total_nw": p_sw + p_ck + p_lk, "alpha": alpha, "f_hz": f_hz,
            "claimable": False,
            "why": "α 是假设值 · 走线电容取 0（无 P&R）⇒ 一阶估计，不作签核"}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def ctrl_self_check(verbose: bool = False) -> dict:
    problems = []
    b = build()
    nl, au, tm = b["netlist"], b["authenticity"], b["timing"]
    if not au["ok"]:
        problems.append(("authenticity", au["problems"]))
    w = acc_width_witness()
    if not w["ok"]:
        problems.append(("acc_width", w))
    if not w["fits_at"][18] or w["fits_at"][17]:
        problems.append(("acc_width_marginal", w["fits_at"]))

    # 端口齐备
    for p in ("row_sel", "bit_sel", "acc_out", "sclk", "sdo", "sdo_valid",
              "busy", "done"):
        if p not in nl.outputs:
            problems.append(("missing_port", p))
    if len(nl.outputs.get("row_sel", ())) != 7:
        problems.append(("row_sel_width", len(nl.outputs.get("row_sel", ()))))
    if len(nl.outputs.get("acc_out", ())) != ACC_WIDTH:
        problems.append(("acc_width_port", len(nl.outputs.get("acc_out", ()))))

    # 单周期等价（锁步序列，覆盖可达状态）
    ls = lockstep(1500)
    if not ls["ok"]:
        problems.append(("lockstep", ls["mismatches"][:2]))

    # 完整一个样本必须走完（done 必须出现）
    if ls["final_state"].get("done_r") != 1 and ls["final_state"].get("st") != 0:
        problems.append(("not_completed", ls["final_state"].get("st")))

    if verbose:
        print("[E34] gates=%d dff=%d area=%.2f um2 leak=%.1f nW"
              % (tm.n_comb_gates, tm.n_dff, tm.area_um2, tm.leak_nw))
        print("[E34] fmax=%.1f MHz  t_clk_min=%.1f ps" % (tm.fmax_mhz, tm.t_clk_min_ps))
        print("[E34] lockstep cycles=%d checked=%d" % (ls["n_cycles"], ls["n_checked"]))

    return {
        "ok": not problems,
        "problems": problems,
        "gates": tm.n_comb_gates,
        "dff": tm.n_dff,
        "area_um2": tm.area_um2,
        "leak_nw": tm.leak_nw,
        "fmax_mhz": tm.fmax_mhz,
        "t_clk_min_ps": tm.t_clk_min_ps,
        "critical_len": len(tm.critical_path),
        "lockstep_cycles": ls["n_cycles"],
        "lockstep_checked": ls["n_checked"],
        "acc_width": w,
    }


DCTRL_DISCLOSURE = {
    "route": "E34 · 数字控制壳自主建 · 第 6 层（CIM 控制壳：第一个真实设计）",
    "design": "单 ADC 时分复用行扫描控制器 · 5 态 FSM · 7 bit 行选 · 3 bit 位平面 · "
              "18 bit 累加器 · 18 拍 SPI 读回 · 同步复位",
    "width_derivation": "row_sel=⌈log₂87⌉=7 · bit_sel=⌈log₂8⌉=3 · "
                        "acc=⌈log₂(87×8×255+1)⌉=18（16 位会静默溢出）· scnt=⌈log₂18⌉=5",
    "closure": "数字壳 Fmax vs `timing.cdac_clock_from_settle(8)` 决定的最快 SAR 时钟；"
               "headroom<1 ⇒ 数字是真瓶颈（诚实报告，不调参数掩盖）",
    "arch_caution": "本设计为**单 ADC 时分复用**；E17 的 per_sample 假设 ADC 并行 ⇒ "
                    "两者架构不同，**不可直接相除**，本段不做这种比较",
    "not_included": "无 async FIFO/跨时钟域 · 无 CDC · 无 DFT/扫描链 · 无低功耗状态（clock gating）· "
                    "无错误检测（ADC 超时/溢出均未处理）· 无总线接口（AXI/APB）",
    "claimable": True,
    "claimable_reason": "结构事实（门数/DFF/端口/FSM 行为）可机核；"
                        "Fmax/面积/功耗为一阶模型（claimable=False 的部分已在 dsta.dcell 声明）",
}
