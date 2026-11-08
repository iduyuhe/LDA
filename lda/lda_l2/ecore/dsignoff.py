"""B3 · 签核级提取/时序 —— 提取加 C + 多角（tt/ff/ss）+ IR/EM。

═══════════════════════════════════════════════════════════════════════════════
B3 补的是什么（相对 B1/B2）
───────────────────────────────────────────────────────────────────────────────
B1 给了**电阻**（`dcells.extract_r`：栅/扩散/接触/金属段），B2 给了**布通 + DRC 干净**。
但仍有三件事缺着，缺了就不能称「设计期签核」：

 ① **没有电容** ⇒ 只有 R 就没有延迟，RC = ∞ 或 = 0 都说得通；
 ② **只有单点（tt）** ⇒ 工艺波动完全不可见，"过签核"可能只是恰好压在标称点；
 ③ **没有 IR / EM** ⇒ 电源网在签核里根本不存在（真实失效大头之一）。

本模块给出这三件的一阶、**可两法互证**的实现：

| 项 | 模型（一阶 · 全部显式假设） |
|---|---|
| 电容 | 平板对衬底 `ε₀ε_r·A/h` × 边缘因子 `(1+2t/w)`；按走线段逐段求和 |
| 延迟 | Elmore：`R·(C_wire/2 + C_load)`；另给 N 段梯形网络的**离散解**做互证。🔴 单位 = **fs**（`Ω·fF = 1e-15 s`）|
| 多角 | ff/ss 对 R、C 各乘一套系数，给出**延迟区间**（不是单点） |
| IR | 均匀抽流的均匀轨：末端压降 `I·R/2`；另给离散节点方程解做互证 |
| EM | `J = I/(w·t)` 对 **`J_max(T)`**（Black 温度标度，`T_ref` 显式）判定 |

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何引用一起给）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **不是 signoff**：这仍是一阶解析模型。真实签核需要 foundry 的 ITF/RC tech file、
   3D 场求解、SPEF、以及**实测校准** —— 本项目一个都没有（C 级自主 + 无 PDK + 无硅）。
   本模块的作用是把「签核需要哪几件事」变成**可机核的最小骨架**，并显式列出还差什么。
2. 🔴 多角系数（ff 0.85/0.90、ss 1.15/1.10）是**演示量级**，不是任何工艺的 PVT 数据。
3. 🔴 电容只到一阶平板 + 边缘修正；耦合电容只按**相邻同层间距**估，不做全场求解。
4. 🔴 IR 用**均匀抽流**假设；EM 的 `J_MAX` 是公开量级的假设值，非工艺认证。
5. 🔴 不报 TOPS/fJ/能效（未流片）；`claimable=False`，**净增 0 锚**（门禁形态）。
"""
from __future__ import annotations

import math

# ---- 物理常数与一阶工艺假设（全部显式，便于外部替换）----
EPS0 = 8.854e-12          # F/m
EPSR_ILD = 4.0            # SiO₂ 相对介电常数
H_ILD_UM = 0.6            # M3 到衬底的有效介质厚度
T_METAL_UM = 0.14         # 金属厚度（M3/M4）
CPP_FRINGE = 0.02         # 边缘电容系数（每边，按 w 归一）—— 一阶修正

RSH = {"M3": 0.12, "M4": 0.10}      # Ω/□（演示量级）
C_LOAD_FF = 1.0                     # 典型扇出负载电容（假设）
TIME_UNIT = "fs"                    # 🔴 Ω·fF = 1e-15 s = 1 fs（延迟量的真实量纲）
J_MAX_A_M2 = 1.0e10                 # 1e6 A/cm²（**在 T_REF_C 下**的公开量级假设，非工艺认证）
# ---- EM 的温度标度（Black 方程 · v0.9.385）----
# 🔴 常量 `J_MAX_A_M2` 是**某个温度下**的值，但此前没写是哪个温度 —— 这是隐藏假设。
#    本版把它显式化为 `T_REF_C`，并按 Black 方程把温度依赖补上：
#        MTTF = A · J^-n · exp(Ea/(k·T))
#    同一 MTTF 目标下 ⇒  J_max(T) = J_ref · exp( (Ea/(n·k)) · (1/T − 1/T_ref) )
#    即：温度越高，允许电流密度越低（Ea>0 ⇒ 指数递减），这是本式唯一的方向性结论。
K_B_EV = 8.617333262e-5             # eV/K（玻尔兹曼常数）
EA_EV = 0.9                         # Cu 互连激活能（公开量级假设，非工艺认证）
N_EXP = 1.1                         # 电流密度指数 n（Black 方程，公开量级假设）
T_REF_C = 125.0                     # 🔴 **假设**：`J_MAX_A_M2` 的标定基准温度（°C）

#: 多角（R 缩放, C 缩放）—— 演示量级，非 PVT 数据
CORNERS = {"ff": (0.85, 0.90), "tt": (1.00, 1.00), "ss": (1.15, 1.10)}


# ═══════════════════════════════════════════════════════════════════════════
# ① 单段 RC
# ═══════════════════════════════════════════════════════════════════════════
def wire_r(length_um: float, width_um: float, layer: str = "M3") -> float:
    """方块电阻：`Rsh · L / W`（Ω）。"""
    return RSH[layer] * length_um / width_um


def wire_c(length_um: float, width_um: float) -> float:
    """一阶电容（fF）：平板 `ε₀ε_r·A/h` × 边缘因子 `(1+2·t/w·CPP_FRINGE_ratio)`。

    单位换算：F → fF ×1e15；长度/宽度以 µm 传入。
    """
    a_m2 = (length_um * 1e-6) * (width_um * 1e-6)
    h_m = H_ILD_UM * 1e-6
    c_plate = EPS0 * EPSR_ILD * a_m2 / h_m
    fringe = 1.0 + 2.0 * (T_METAL_UM / width_um) * CPP_FRINGE
    return c_plate * fringe * 1e15


def net_rc(shapes: list, layer_of, net: str) -> dict:
    """把某网的全部走线段按段累加 R 与 C（`layer_of` 提供层名映射）。"""
    r_tot = 0.0
    c_tot = 0.0
    n_seg = 0
    for s in shapes:
        if getattr(s, "net", None) != net or getattr(s, "kind", "") != "metal":
            continue
        lay = layer_of(s.layer)
        if lay not in RSH:
            continue
        length = max(s.x1 - s.x0, s.y1 - s.y0)
        width = min(s.x1 - s.x0, s.y1 - s.y0)
        if width <= 0 or length <= 0:
            continue
        r_tot += wire_r(length, width, lay)
        c_tot += wire_c(length, width)
        n_seg += 1
    return {"r_ohm": r_tot, "c_ff": c_tot, "n_seg": n_seg}


# ═══════════════════════════════════════════════════════════════════════════
# ② Elmore 延迟（闭式 ⇄ 离散梯形网络互证）
# ═══════════════════════════════════════════════════════════════════════════
def elmore_closed(r_ohm: float, c_ff: float, c_load_ff: float = C_LOAD_FF) -> float:
    """分布式 RC 线 + 集中负载的一阶 Elmore 延迟：`R·(C/2 + C_load)`。

    🔴 **单位是 fs 不是 ps**：`Ω × fF = 1e-15 s = 1 fs`。
    （v0.9.345 的文档把该量标成 ps —— 标签错、数值不错；v0.9.346 修正标签，
    并新增 `TIME_UNIT` 常量与 E43 的量纲判据。）
    """
    return r_ohm * (c_ff / 2.0 + c_load_ff)


def elmore_ladder(r_ohm: float, c_ff: float, n: int, c_load_ff: float = C_LOAD_FF) -> float:
    """把线切成 n 段：每段 R/n、C/n，末段带负载 C_load，按 Elmore 求和（**fs**）。

    逐节点延迟和 = Σ_k (R/n) · (C·(n-k)/n + C_load)。
    ⇒ 解析和 = R·C·(n+1)/(2n) + R·C_load ⇒ n→∞ 收敛到 `R·(C/2 + C_load)`。
    """
    r_seg = r_ohm / n
    c_seg = c_ff / n
    tot = 0.0
    for k in range(n):
        tot += r_seg * (c_seg * (n - k) + c_load_ff)
    return tot


# ═══════════════════════════════════════════════════════════════════════════
# ③ 多角
# ═══════════════════════════════════════════════════════════════════════════
def delay_at_corner(rc: dict, corner: str, c_load_ff: float = C_LOAD_FF,
                    use_ladder_n: int = 0) -> float:
    """某角下的延迟（**fs**）。`use_ladder_n>0` 时改用离散梯形解（互证用）。"""
    if corner not in CORNERS:
        raise KeyError("unknown corner: %r" % (corner,))
    kr, kc = CORNERS[corner]
    r = rc["r_ohm"] * kr
    c = rc["c_ff"] * kc
    if use_ladder_n:
        return elmore_ladder(r, c, use_ladder_n, c_load_ff)
    return elmore_closed(r, c, c_load_ff)


def corner_table(rc: dict) -> dict:
    """三角延迟表 + 区间（min/max）+ 相对 tt 的散布。🔴 键名带 `_fs`：单位是 fs。"""
    d = {k: round(delay_at_corner(rc, k), 6) for k in CORNERS}
    lo, hi = min(d.values()), max(d.values())
    return {"delay_fs": d, "min_fs": round(lo, 6), "max_fs": round(hi, 6),
            "spread_pct": round((hi - lo) / d["tt"] * 100.0, 6) if d["tt"] else None}


# ═══════════════════════════════════════════════════════════════════════════
# ④ IR drop（闭式 ⇄ 离散节点方程互证）
# ═══════════════════════════════════════════════════════════════════════════
def ir_drop_closed(i_total_a: float, rsh: float, length_um: float, width_um: float) -> float:
    """均匀抽流的均匀轨：末端（最远点）压降 = `I·R_rail/2`（V）。

    推导：单位长度电流 i=I/L，距注入端 x 处的电流为 I(1−x/L)，压降
    ∫₀^L ρ(I(1−x/L))/W dx = I·(Rsh·L/W)/2。
    """
    r_rail = rsh * length_um / width_um
    return i_total_a * r_rail / 2.0


def ir_drop_ladder(i_total_a: float, rsh: float, length_um: float, width_um: float,
                   n: int) -> float:
    """把轨切成 n 段，每段电阻 R/n、节点抽流 I/n，逐段累加压降（V）。

    V_k = Σ_{j≥k} (R/n)·I·(n-j)/n ⇒ 末端压降 = (R·I/n²)·Σ_{m=1..n} m = R·I·(n+1)/(2n)。
    """
    r_seg = (rsh * length_um / width_um) / n
    i_node = i_total_a / n
    v = 0.0
    for k in range(n):
        v += r_seg * i_node * (n - k)
    return v


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ EM（电流密度）
# ═══════════════════════════════════════════════════════════════════════════
def j_max_at(t_c: float, t_ref_c: float = T_REF_C,
             ea_ev: float = EA_EV, n_exp: float = N_EXP) -> float:
    """给定结温（°C）⇒ 允许电流密度（A/m²）。Black 方程的温度标度。

    `J_max(T) = J_ref · exp( (Ea/(n·k)) · (1/T − 1/T_ref) )`，T 用 Kelvin。

    🔴 **退化性质（机核）**：`T == T_ref` 时指数项恰为 `exp(0) == 1.0`
    ⇒ 返回值**逐位等于** `J_MAX_A_M2`。这保证本函数是旧常数的**严格推广**，
    不是「换了一套数」。
    """
    t = t_c + 273.15
    tr = t_ref_c + 273.15
    return J_MAX_A_M2 * math.exp(ea_ev / (n_exp * K_B_EV) * (1.0 / t - 1.0 / tr))


def em_check(i_a: float, width_um: float, t_um: float = T_METAL_UM,
             t_c: float = T_REF_C, ea_ev: float = EA_EV, n_exp: float = N_EXP,
             j_max: float | None = None) -> dict:
    """`J = I/(w·t)`（A/m²）对 **`J_max(T)`** 判定，返回电流密度、裕量与是否通过。

    参数（K0 完备性要求：EM 的 6 个物理自变量全部可为输入）
        `i_a` 电流 · `width_um` 线宽 · `t_um` 金属厚度
        `t_c` 结温 · `ea_ev` 激活能 · `n_exp` 电流密度指数

    🔴 `j_max` 保留为**显式覆盖**（默认 `None` ⇒ 由温度算）。给值时行为与旧版一致
    （旧测试若直接传该参数不受影响），但**正常路径不再使用常数**。
    """
    jm = j_max_at(t_c, ea_ev=ea_ev, n_exp=n_exp) if j_max is None else float(j_max)
    area_m2 = (width_um * 1e-6) * (t_um * 1e-6)
    j = i_a / area_m2
    return {"j_a_m2": j, "margin_x": jm / j if j > 0 else float("inf"),
            "ok": j <= jm, "j_max": jm, "t_c": t_c,
            "t_ref_c": T_REF_C, "ea_ev": ea_ev, "n_exp": n_exp,
            "j_max_overridden": j_max is not None}


# ---- 每网电流 → 每网 EM 的「接线层」（v0.9.387 · B2b）----------------------
# 🔴 这一层解决的是**「EM 从来没有输入」**，不是「EM 算错了」：
#    上面的 `em_check` 一直是纯函数，但主链从未给它电流 ⇒ 它对外等于不存在。
#    接线后**判定结果一位也不会变**（实测 c17 违例 0/7、最小裕量 101×），
#    因为 EM 是给 mA~A 级电流（电源网/时钟树/大扇出）用的判据，而 c17 是 6 个门、
#    0.24 µm 线、动态电流仅 µA 级 ⇒ **该判据在这个设计上天生没有判别力**。
#    诚实做法不是「假装它会响」，而是把它接成**带量纲的裕量 + 不可判清单**，
#    并用反向探针证明「换个参数它真的会响」。
ALPHA_DYN = 0.1              # 翻转率 α（假设，与 `dsta.switching_power_nw` 默认一致）
EM_SCOPE = "JUDGED_SUBSET_ONLY"   # 🔴 与 DRC 的 ROUTED_SUBSET_ONLY 同源纪律


def _finite_or_none(x):
    """🔴 端点必须严格 JSON：`inf`/`nan` 会写成裸字面量（非标准 JSON，JS `JSON.parse` 直接抛）。

    `I=0` 时裕量是数学上的 `inf`，语义上等于「此处不适用」⇒ 对外给 `None`，
    绝不给 `Infinity`（那既非法又会被读成「无穷大的好」）。
    """
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)) and math.isfinite(float(x)):
        return x
    return None


def net_current_a(c_total_ff: float, f_hz: float, vdd: float,
                  alpha: float = ALPHA_DYN) -> float:
    """每网**平均**动态电流（A）：`I = α · C_total · VDD · f`。

    `C_total` 必须是**该网总负载**（走线电容 + 扇出栅电容），不是只算线载 ——
    只算线载会把电流低估 1.5~2.7×（c17 实测 C_wire 1.2 fF vs C_tot 3.2 fF）。

    🔴 **这是平均电流，不是峰值**：EM 的 `J_max` 本身是对平均电流密度的限值，
    用平均是自洽的；但开关瞬间的峰值电流会更高，本模型**不覆盖**（见 disclosure）。

    退化性质（机核）：`C=0` 或 `f=0` ⇒ 返回**恰为 0.0** ⇒ 下游裕量 `inf`、不判 FAIL。
    这是对的：没有电流就没有电迁移，`inf` 不是「无穷大裕量的好消息」，
    而是「这个量在此处不适用」——与「不可判」等价，不能当通过计入覆盖率。
    """
    return alpha * (float(c_total_ff) * 1e-15) * float(vdd) * float(f_hz)


def f_from_comb_delay(t_comb_ps: float, half_period: bool = True) -> float:
    """由组合关键路径延时反推**翻转频率**（Hz）。

    🔴 c17 是**纯组合**电路 ⇒ `dsta` 给不出 `fmax`（无时钟域，`fmax_mhz=None`）。
    EM 又必须有频率输入 ⇒ 只能由延时反推，并且**必须声明这是假设**。

    `half_period=True` ⇒ `f = 1/(2·t)`（默认，保守）；`False` ⇒ `1/t`（吞吐上限）。
    这个选择**会改变裕量 2 倍**（c17 实测 101× vs 50×），所以它是显式参数、不是内部常量。
    """
    t = float(t_comb_ps)
    if not (t > 0.0):
        raise ValueError("组合延时必须为正才能反推频率（得 %r）" % (t_comb_ps,))
    return 1.0 / ((2.0 if half_period else 1.0) * t * 1e-12)


def em_net_signoff(length_um: dict, c_wire_ff: dict, c_total_ff: dict,
                   nets_all, f_hz: float, vdd: float, width_um: float,
                   t_um: float = T_METAL_UM, t_c: float = T_REF_C,
                   alpha: float = ALPHA_DYN, ea_ev: float = EA_EV,
                   n_exp: float = N_EXP) -> dict:
    """逐网 EM 裕量汇总（**诊断段**：不进 `claimable` 的 blocking 列表）。

    参数全部显式（K0 完备性）：每网线长 / 线载 / 总负载 · 频率 · VDD · 线宽 ·
    金属厚度 · 结温 · 翻转率 · 激活能 · 指数。

    🔴 **可判性必须与结论同行**：
    · 只有「有金属的网」才判 —— 无布线的网**不是通过、是不可判**（`undecidable`）；
    · `scope = JUDGED_SUBSET_ONLY`，`n_fail=0` 只对 `n_nets_judged` 成立；
    · `in_blocking=False` 明确「本段不参与签核阻塞」，避免被读成「EM 合规」。

    🔴 **不做的事**（写在这里，避免下次误以为已覆盖）：不含电源/地网（PDN 未建模）、
    不含时钟树、不含 via 许用电流、不含峰值 di/dt、不含 AC 频率修正。
    """
    nets = set(nets_all or ())
    judged = []
    per_net = {}
    raw_margin = {}          # 🔴 排序用原始值（可能是 inf）；对外输出走 `_finite_or_none`
    jm = j_max_at(t_c, ea_ev=ea_ev, n_exp=n_exp)
    for net in sorted(nets):
        c_wire = float(c_wire_ff.get(net, 0.0))
        if c_wire <= 0.0:
            continue                      # 无金属 ⇒ 不可判（下面单独列名）
        c_tot = float(c_total_ff.get(net, c_wire))
        i_a = net_current_a(c_tot, f_hz, vdd, alpha)
        r = em_check(i_a, width_um, t_um=t_um, t_c=t_c,
                     ea_ev=ea_ev, n_exp=n_exp)
        per_net[net] = {
            "length_um": round(float(length_um.get(net, 0.0)), 3),
            # 🔴 `c_wire_ff` / `c_total_ff` **不 round**：它们是电流公式的输入，
            #    round 会让「独立复算 I=α·C·V·f」变成永远差一点 ⇒ 判据只能放宽容差 ⇒ 判别力下降。
            "c_wire_ff": c_wire,
            "c_total_ff": c_tot,
            "i_a": i_a,
            "j_a_m2": r["j_a_m2"],
            # 🔴 严格 JSON：`I=0` ⇒ 裕量 `inf` ⇒ 对外 `None`（不写裸 `Infinity`）
            #    裕量是**比值**，取 3 位与 `timing`/`area` 段同口径（判据两侧都走此口径 ⇒ 可逐位比）
            "margin_x": (None if _finite_or_none(r["margin_x"]) is None
                         else round(r["margin_x"], 3)),
            "ok": bool(r["ok"]),
        }
        judged.append(net)
        raw_margin[net] = r["margin_x"]

    undecidable = sorted(nets - set(judged))
    fails = [n for n in judged if not per_net[n]["ok"]]
    best = min(judged, key=lambda n: raw_margin[n]) if judged else None
    _min_margin = None if best is None else _finite_or_none(raw_margin[best])
    return {
        "chain": "dpnr",
        "scope": EM_SCOPE,
        # ---- 输入假设（全部显式，供外部核验；缺一项就等于回到「隐藏假设」）----
        "assumptions": {
            "f_hz": f_hz, "vdd": vdd, "alpha": alpha,
            "width_um": width_um, "t_um": t_um, "t_c": t_c,
            "ea_ev": ea_ev, "n_exp": n_exp, "t_ref_c": T_REF_C,
            "j_max_a_m2": jm,
        },
        # ---- 可判性（结论必须跟着它读）----
        "n_nets_total": len(nets),
        "n_nets_judged": len(judged),
        "n_nets_undecidable": len(undecidable),
        "undecidable_nets": undecidable,
        "undecidable_reason": "无布线金属（未布通）⇒ 不可判，不等于通过",
        # ---- 结果 ----
        "n_fail": len(fails),
        "fail_nets": fails,
        "all_pass_on_judged": (len(fails) == 0 and len(judged) > 0),
        "min_margin_x": (None if _min_margin is None else round(_min_margin, 3)),
        "min_margin_net": best,
        "per_net": per_net,
        # ---- 边界（对外必须一起给）----
        "in_blocking": False,
        "coverage_note": ("只判有金属的信号网；不含电源/地网（PDN 未建模）、时钟树、"
                          "via 许用电流、峰值 di/dt 与 AC 频率修正"),
    }



# ═══════════════════════════════════════════════════════════════════════════
# ⑤b EC-B3.1：几何 / 量纲诊断（只报谱与不变式，不判违规、不进 blocking）
#   🔴 与门禁 `run_ecore_s13_smoke` 的独立复算走**不同算法路径**（K2）：
#      门禁 = 扫描线坐标压缩（`_ec_union`）+ 逐窗二维裁剪（`_ec_dens`）；
#      本侧 = 增量矩形差集 + 可分离一维累积函数差分。
#      两侧结果必须逐位一致，且源码互不引用 —— 「两实现」≠「两条独立路径」。
#   🔴 段内**不设** `n_fail` / `ok` / `pass` —— 本段是诊断，不是判决。
# ═══════════════════════════════════════════════════════════════════════════
B3_SCALES = (1, 2, 4, 8, 16, 32)
B3_SCOPE = "DIAGNOSTIC_ONLY"
B3_UNION_METHOD = "incremental_rect_subtraction"
B3_DENSITY_METHOD = "separable_1d_cdf_difference"


def b3_subtract_rect(r, o):
    """从矩形 r 中减去 o，返回最多 4 块互不重叠的碎片（增量差集）。"""
    x0, y0, x1, y1 = r
    ox0, oy0, ox1, oy1 = o
    ix0, iy0 = max(x0, ox0), max(y0, oy0)
    ix1, iy1 = min(x1, ox1), min(y1, oy1)
    if ix0 >= ix1 or iy0 >= iy1:
        return [r]
    out = []
    if y0 < iy0:
        out.append((x0, y0, x1, iy0))
    if iy1 < y1:
        out.append((x0, iy1, x1, y1))
    if x0 < ix0:
        out.append((x0, iy0, ix0, iy1))
    if ix1 < x1:
        out.append((ix1, iy0, x1, iy1))
    return out


def b3_union_rects(rects):
    """增量差集求并集碎片：**不同于**门禁的扫描线全局坐标压缩。"""
    accepted, out = [], []
    for r in rects:
        frags = [r]
        for o in accepted:
            nxt = []
            for f in frags:
                nxt.extend(b3_subtract_rect(f, o))
            frags = nxt
            if not frags:
                break
        out.extend(frags)
        accepted.append(r)
    return out


def b3_union_area(rects):
    return sum((f[2] - f[0]) * (f[3] - f[1]) for f in b3_union_rects(rects))


def b3_window_density(rects, n, die_w, die_h):
    """可分离一维累积函数差分：窗覆盖面积 = ΔFx · ΔFy。

    **不同于**门禁的逐窗二维裁剪（`max(0, min−max)` 两轴相交累加）。
    """
    cw, ch = float(die_w) / n, float(die_h) / n
    acc = [[0.0] * n for _ in range(n)]
    for x0, y0, x1, y1 in rects:
        def fx(t):
            return max(0.0, min(x1, t) - x0)

        def fy(t):
            return max(0.0, min(y1, t) - y0)

        for i in range(n):
            dx = fx((i + 1) * cw) - fx(i * cw)
            if dx <= 0.0:
                continue
            for j in range(n):
                dy = fy((j + 1) * ch) - fy(j * ch)
                if dy > 0.0:
                    acc[i][j] += dx * dy
    return [acc[i][j] / (cw * ch) for i in range(n) for j in range(n)]


def ec_b3_signoff(shapes, die_w_um, die_h_um, width_um, g_values,
                  scales=B3_SCALES) -> dict:
    """逐层密度谱 + 四口径比值谱（**诊断段**：不判违规、不进 blocking）。

    输入全部显式（K0 完备性）：几何 / die 尺寸 / 唯一线宽 / 尺度集合 / 四个分母口径。
    所有 `g` 均为**代理量与假设**（门总面积、单门、单管、单元外框），非工艺认证。
    """
    metals = [s for s in shapes if getattr(s, "kind", None) == "metal"]
    layers = sorted({int(s.layer) for s in metals})
    die_area = float(die_w_um) * float(die_h_um)
    by_layer = {L: [(s.x0, s.y0, s.x1, s.y1) for s in metals if int(s.layer) == L]
                for L in layers}
    uni = {L: b3_union_rects(by_layer[L]) for L in layers}
    area = {L: sum((f[2] - f[0]) * (f[3] - f[1]) for f in uni[L]) for L in layers}
    rho = {L: area[L] / die_area for L in layers}

    inv = {"i1_conservation": True, "i2_monotone": True,
           "i3_limit": True, "i4_upper_bound": True}
    layer_out = {}
    for L in layers:
        drho, rmax = [], []
        for n in scales:
            v = b3_window_density(uni[L], n, die_w_um, die_h_um)
            drho.append(round(max(v) - min(v), 6))
            rmax.append(round(max(v), 6))
            if abs(sum(v) / (n * n) - rho[L]) > 1e-5:
                inv["i1_conservation"] = False
        if any(x > 1.0 + 1e-9 for x in rmax):
            inv["i4_upper_bound"] = False
        if any(drho[k] + 1e-9 < drho[k - 1] for k in range(1, len(scales))):
            inv["i2_monotone"] = False
        if abs(drho[0]) > 1e-9:
            inv["i3_limit"] = False
        # 🔴 严格 JSON：任何非有限量落成 None，不写裸 Infinity / NaN
        layer_out[str(L)] = {
            "area_um2": _finite_or_none(round(area[L], 6)),
            "rho": _finite_or_none(round(rho[L], 6)),
            "drho": [_finite_or_none(x) for x in drho],
            "rho_max": [_finite_or_none(x) for x in rmax],
        }

    by_net = {}
    for s in metals:
        by_net.setdefault(getattr(s, "net", None), {}).setdefault(
            int(s.layer), []).append((s.x0, s.y0, s.x1, s.y1))
    net_area = {net: sum(b3_union_area(rs) for rs in ld.values())
                for net, ld in by_net.items()}

    ratios, max_raw = {}, {}
    for g, gv in g_values.items():
        vals = {net: a / float(gv) for net, a in net_area.items()}
        max_raw[g] = max(vals.values())
        ratios[g] = {
            "max": _finite_or_none(round(max_raw[g], 6)),
            "min": _finite_or_none(round(min(vals.values()), 6)),
            "sum": _finite_or_none(round(sum(vals.values()), 6)),
            "per_net": {k: _finite_or_none(round(v, 6))
                        for k, v in sorted(vals.items())},
        }
    g0 = next(iter(g_values))
    inv["i8_homogeneity"] = all(
        abs(max_raw[g] / max_raw[g0] - float(g_values[g0]) / float(g_values[g])) < 1e-9
        for g in g_values)
    inv["i_scale_upper_bound"] = bool(
        float(die_w_um) / scales[-1] >= float(width_um)
        > float(die_w_um) / (2 * scales[-1]))

    return {
        "chain": "dpnr",
        "scope": B3_SCOPE,
        "in_blocking": False,
        "assumptions": {
            "die_w_um": round(float(die_w_um), 6),
            "die_h_um": round(float(die_h_um), 6),
            "width_um": float(width_um),
            "scales": list(scales),
            "scale_upper_bound": "die_w/n >= width_um ⇒ 再细分即像素化（上界反解，非拍常数）",
            "g_values": {k: round(float(v), 6) for k, v in g_values.items()},
            "g_basis": ("netlist 门总面积 / 单门 / 单管 / 单元外框 w*h —— "
                        "均为代理量与假设，非 foundry 栅氧面积"),
            "union_method": B3_UNION_METHOD,
            "density_method": B3_DENSITY_METHOD,
        },
        "layers": layer_out,
        "net_area_um2": {k: _finite_or_none(round(v, 6))
                         for k, v in sorted(net_area.items())},
        "ratio_by_g": ratios,
        "ratio_semantics": {
            "meaning": ("ratio_by_g = 每网金属同层并集面积 / 栅面积代理量 g，"
                        "即**天线比的几何代理**（无量纲面积比）"),
            "not_physics": ("不含电荷积分 Q、Fowler-Nordheim 隧穿、等离子体充电、"
                            "栅氧厚度与栅氧退化、via 许用电流与峰值 di/dt"),
            "g_is_proxy": True,
            "scope": B3_SCOPE,
        },
        "invariants": inv,
        # I9（数值锁定）由门禁 P13 对拍 v2 §4；本段**不复制冻结值**，避免自证
        "lock_basis": "EC-B3.0 v2 §4 · gated by run_ecore_s13_smoke P13",
        "coverage_note": ("逐层同层矩形并集后的密度谱 + 四口径比值谱；"
                          "只报带量纲的谱与不变式，不设窗口阈值、不挑单一分母、不判违规"),
        "not_included": [
            "不是 CMP / 天线签核，DRC 规则集仍不含密度 / 天线规则",
            "不含电源/地网（PDN 未建模）、时钟树、via 许用电流、栅氧厚度、峰值 di/dt",
            "die 仅 7.8 µm，远小于真实工艺平坦化长度 ⇒ 窗口是离散化尺度，非真实工艺窗口",
            "规则集为自建教科书尺度、非 foundry PDK ⇒ 不作可制造性 / 性能宣称",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑤c EC-B4.1：稳态热链诊断（傅里叶 1D 网络 · 只报谱与不变式，**不回灌 t_c**）
# ═══════════════════════════════════════════════════════════════════════════
B4_T_AMB_C = 25.0          # 🔴 假设：环境温度（°C），非封装/散热边界真值
B4_R_TH_K_W = 1.0          # 🔴 假设：链总热阻（K/W）**归一化占位**，非工艺真值
B4_SCOPE = "DIAGNOSTIC_ONLY"


def b4_cell_power_w(nl, loads_ff, f_hz, alpha, vdd):
    """逐门动态功率 `P = α·C(out)·V²·f`（W）。

    C 取自 `dsta.loads_of`（网负载）；`α` / `f` 均为**显式假设**（c17 纯组合 ⇒
    `f` 由组合延时反推半周期）。逐门之和与 `dsta.switching_power_nw` 逐位守恒。
    """
    return {g.name: float(alpha) * float(loads_ff.get(g.out, 0.0)) * 1e-15
            * float(vdd) ** 2 * float(f_hz) for g in nl.gates}


def b4_thermal_chain(powers, r_th_k_w=B4_R_TH_K_W, t_amb_c=B4_T_AMB_C):
    """1D 稳态热链：n 节点串联，每段 `r = r_th/n`，环境在左端。

    通过第 k 段的热流 `Q_k = Σ_{j>=k} P_j`；温升 `ΔT_i = Σ_{k<=i} r·Q_k`。
    🔴 与 RC / IR ladder 同构：均匀功率时 `ΔT_end = r_th·P_total·(n+1)/(2n)`；
    `n=1` 退化为集总闭式 `T = T0 + P·R`。
    🔴 产品侧算法 = **单次递推**（末端回累加 Q，再左到右积分 ΔT）；
       门禁侧须用另一条路径（显式双重求和）独立复算并对拍（K2）。
    """
    n = len(powers)
    if n == 0:
        return {"r_seg_k_w": 0.0, "q_k_w": [], "delta_t_k": [], "t_c": []}
    r_seg = float(r_th_k_w) / n
    q = [0.0] * (n + 1)
    acc = 0.0
    for k in range(n, 0, -1):
        acc += float(powers[k - 1])
        q[k] = acc
    dt, cum = [], 0.0
    for i in range(1, n + 1):
        cum += r_seg * q[i]
        dt.append(cum)
    return {"r_seg_k_w": r_seg, "q_k_w": q[1:], "delta_t_k": dt,
            "t_c": [float(t_amb_c) + x for x in dt]}


def b4_thermal_signoff(cells, r_th_k_w=B4_R_TH_K_W, t_amb_c=B4_T_AMB_C,
                       assumptions=None) -> dict:
    """稳态热诊断段（DIAGNOSTIC_ONLY）：逐单元功率 / 温升谱 / 不变式 / 显式假设。

    `cells`: `[{"name", "p_w", "area_um2"}, ...]`，顺序即热链节点顺序（确定性）。
    🔴 只报带量纲的谱与不变式，**不判违规、不设温度阈值、不进 blocking**；
    🔴 **不回灌 `em_net_signoff` 的 `t_c`**（EM 仍用 `T_REF_C=125°C` 假设）。
    """
    powers = [float(c["p_w"]) for c in cells]
    ch = b4_thermal_chain(powers, r_th_k_w, t_amb_c)
    n = len(powers)
    p_total = sum(powers)
    dt = ch["delta_t_k"]
    # 均匀功率闭式（与 IR ladder 同构）；n=1 时即集总 T=T0+P·R
    p_cell_uniform = p_total / n if n else 0.0
    uniform_closed = (float(r_th_k_w) * p_cell_uniform
                      * (n + 1) / 2.0) if n else 0.0
    # 🔴 合成均匀对照链（独立于真实 dt）⇒ 非均匀输入时判据仍可证伪，不是恒真装饰
    ch_uniform = b4_thermal_chain([p_cell_uniform] * n, r_th_k_w, t_amb_c) if n else None
    ch_homo = b4_thermal_chain(powers, float(r_th_k_w) * 1.3, t_amb_c) if n else None
    inv = {
        "i_energy_conservation": (abs(ch["q_k_w"][0] - p_total) < 1e-18
                                  if n else True),
        "i_p0_limit": all(abs(x) < 1e-18 for x in dt) if p_total == 0.0 else True,
        "i_monotone": all(dt[i] + 1e-18 >= dt[i - 1]
                          for i in range(1, n)),
        "i_uniform_closed": (abs(ch_uniform["delta_t_k"][-1] - uniform_closed) < 1e-15
                             if ch_uniform else True),
        "i_homogeneity": all(
            math.isclose(ch_homo["delta_t_k"][i] / dt[i], 1.3, rel_tol=1e-12)
            if abs(dt[i]) > 1e-30 else abs(ch_homo["delta_t_k"][i]) < 1e-30
            for i in range(n)),
    }
    per_cell = {}
    for c, d in zip(cells, dt):
        a = float(c["area_um2"])
        per_cell[c["name"]] = {
            "p_w": float(c["p_w"]),
            "area_um2": a,
            "power_density_w_per_um2": (float(c["p_w"]) / a) if a else None,
            "delta_t_k": float(d),
            "t_c": float(t_amb_c) + d,
        }
    return {
        "chain": "dpnr",
        "scope": B4_SCOPE,
        "in_blocking": False,
        "assumptions": dict(assumptions or {}, **{
            "t_amb_c": float(t_amb_c),
            "r_th_k_w": float(r_th_k_w),
            "n_nodes": n,
            "model": "1D steady-state resistor chain (Fourier / Elmore-isomorphic)",
            "algorithm": "single-pass backward-Q accumulation + forward ΔT integration",
            "power_basis": ("dsta.loads_of(nl) per gate output — SAME basis as dsta.switching_power_nw (no wire load); alpha/f are assumptions"),
        }),
        "per_cell": per_cell,
        "q_k_w": [float(x) for x in ch["q_k_w"]],
        "delta_t_k": [float(x) for x in dt],
        "p_total_w": float(p_total),
        "delta_t_max_k": (float(max(dt)) if dt else 0.0),
        "uniform_closed_k": float(uniform_closed),
        "invariants": inv,
        "coverage_note": ("逐门功率（含 3 个零负载门）与一维稳态热链温升谱；"
                          "热阻为归一化占位假设 ⇒ 只报谱与不变式，不报绝对温度结论、不判违规"),
        "not_included": [
            "**不回灌 t_c**：EM 仍用 T_REF_C=125°C 假设，本段与 EM 未接线",
            "不含瞬态 C_th、封装/散热边界真值、3D 热耦合、热点极限判据",
            "r_th / t_amb / alpha / f 均为假设或归一化占位，非 foundry PDK / 非工艺认证",
            "die 仅 7.8 µm、规则集自建教科书尺度 ⇒ 不作可制造性 / 可靠性 / 性能宣称",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑤d EC-B4.2：U7 策略选择器（纯逻辑诊断段，**不回灌任何物理量**）
# ═══════════════════════════════════════════════════════════════════════════
B42_SCOPE = "DIAGNOSTIC_ONLY"


def b42_log_sens(f, x_ref, rel_step=1e-6):
    """产品路径：中心有限差分 `∂ln f/∂ln x`（对数灵敏度，无量纲）。

    🔴 `x_ref` / `f` 的参考点与单位必须由调用方**显式登记为 E5 假设**；
       门禁侧用解析闭式导数独立复算（K2 两条不同算法路径）。
    """
    xp, xm = float(x_ref) * (1.0 + rel_step), float(x_ref) * (1.0 - rel_step)
    fp, fm = float(f(xp)), float(f(xm))
    return (math.log(fp) - math.log(fm)) / (math.log(xp) - math.log(xm))


def b42_rho2(m):
    """2×2 矩阵谱半径（闭式 λ=(tr±√(tr²−4det))/2）。"""
    a, b, c, d = float(m[0][0]), float(m[0][1]), float(m[1][0]), float(m[1][1])
    tr, det = a + d, a * d - b * c
    rt = math.sqrt(max(0.0, tr * tr - 4.0 * det))
    return max(abs((tr + rt) / 2.0), abs((tr - rt) / 2.0))


def b42_kappa(a_fwd, a_rev, a11=1.0, a22=1.0):
    """κ = |∂f_B/∂x_A · ∂f_A/∂x_B| / (|∂f_B/∂x_B|·|∂f_A/∂x_A|)。

    🔴 **κ 天然无量纲**：x_A / x_B 换单位时分子分母同步缩放、完全抵消
       （EC-B4.2 立项实测差 2.22e-16），**不需要也不应该再「归一化 κ」**。
    """
    return abs(float(a_rev) * float(a_fwd)) / (abs(float(a22)) * abs(float(a11)))


def b42_strategy(one_way, kappa):
    if one_way:
        return "EXPLICIT"
    return "ITERATE" if float(kappa) < 1.0 else "MONOLITHIC"


def b42_conflict_status(kappas, rho_global):
    """κ（逐对）与 ρ（全局）冲突消解：只登记，**不改逐对策略、不静默**。"""
    if rho_global is None:
        return "NOT_APPLICABLE"
    return ("INCONSISTENT" if (any(k is not None and k < 1.0 for k in kappas)
                              and float(rho_global) >= 1.0) else "CONSISTENT")


def b42_u7_signoff(pairs, assumptions=None) -> dict:
    """U7 诊断段：逐对 κ 选策略 + 单位缩放自检 + 不可判/不做显式登记。

    `pairs`: 每项须含 `name/a_fwd/a_rev/x_ref/f_ref/unit/source/status`，
    `status` ∈ {DECIDABLE, UNDECIDABLE, NOT_MODELED}。
    🔴 稀疏 Ã（无完整双向闭环）⇒ `rho_status=NOT_MEANINGFUL`，**不输出数值 ρ 冒充判定**。
    🔴 `ρ≥1` 只表示「在该假设矩阵下需整体求解」，不作物理判决、也不报「算不出」。
    """
    out_pairs = []
    for p in pairs:
        st = p.get("status")
        fwd, rev = p.get("a_fwd"), p.get("a_rev")
        if st == "DECIDABLE" and fwd is not None and rev is not None:
            k = b42_kappa(fwd, rev)
            one_way = False
        elif st == "DECIDABLE":
            k, one_way = 0.0, True       # 单向：反向导数不存在 ⇒ κ=0
        else:
            k, one_way = None, None
        out_pairs.append({
            "name": p["name"], "status": st,
            "a_fwd": fwd, "a_rev": rev,
            "x_ref": p.get("x_ref"), "f_ref": p.get("f_ref"),
            "unit": p.get("unit"), "source": p.get("source"),
            "evidence_level": "E5",
            "kappa": k,
            "strategy": (None if st != "DECIDABLE" else b42_strategy(one_way, k)),
            "reason": ("单向耦合，显式求解" if st == "DECIDABLE" and one_way else
                       "双向闭环，按 κ 选策略" if st == "DECIDABLE" else
                       "无 ∂f/∂x 可算 ⇒ 不可判（≠ 通过）" if st == "UNDECIDABLE" else
                       "明确不做：无应力模型，登记为边界"),
        })

    # ── M1 合成反例：单位缩放自检（**不是 c17 数据**，只用于机核判据会不会响）──
    raw = ((0.9, 2000.0), (0.0005, 0.9))
    scaled = ((0.9, 2.0), (0.0005, 0.0009))     # 🔴 只缩第 2 列（x₂ µm→nm）
    r_raw, r_scaled = b42_rho2(raw), b42_rho2(scaled)
    k_raw = b42_kappa(raw[1][0], raw[0][1], raw[1][1], raw[0][0])
    k_scaled = b42_kappa(scaled[1][0], scaled[0][1], scaled[1][1], scaled[0][0])
    a12, x2ref, f1ref = 2000.0, 1.0, 1.0
    a21, x1ref, f2ref = 0.0005, 1.0, 1.0
    tilde = ((0.9, a12 * x2ref / f1ref), (a21 * x1ref / f2ref, 0.9))
    tilde_scaled = ((0.9, (a12 / 1000) * (x2ref * 1000) / f1ref),
                    (a21 * x1ref / f2ref, 0.9))
    r_tilde, r_tilde_scaled = b42_rho2(tilde), b42_rho2(tilde_scaled)
    norm = {
        "kind": "SYNTHETIC_M1_NOT_C17",
        "raw_matrix": raw, "column_scaled_matrix": scaled,
        "rho_raw": r_raw, "rho_column_scaled": r_scaled,
        "kappa_raw": k_raw, "kappa_column_scaled": k_scaled,
        "rho_tilde": r_tilde, "rho_tilde_unit_scaled": r_tilde_scaled,
        "unit_scale": 1000.0,
        "note": ("未归一化的 A 求 ρ 会随单位翻盘；κ 天然无量纲；"
                 "Ã=(∂f/∂x)·x_ref/f_ref 单位无关"),
    }

    n_dec = sum(1 for p in out_pairs if p["status"] == "DECIDABLE")
    n_und = sum(1 for p in out_pairs if p["status"] == "UNDECIDABLE")
    n_nm = sum(1 for p in out_pairs if p["status"] == "NOT_MODELED")
    two_way = [p for p in out_pairs if p["status"] == "DECIDABLE" and p["a_rev"] is not None]
    rho_status = "MEANINGFUL" if two_way else "NOT_MEANINGFUL"
    inv = {
        "i_unit_flip": (r_raw >= 1.0 > r_scaled),
        "i_kappa_unit_free": (abs(k_raw - k_scaled) < 1e-12),
        "i_normalized_invariant": (abs(r_tilde - r_tilde_scaled) < 1e-12),
        "i_one_way_explicit": all(
            p["strategy"] == "EXPLICIT" for p in out_pairs
            if p["status"] == "DECIDABLE" and p["a_rev"] is None),
        "i_no_false_verdict": all(
            p["strategy"] is None and p["kappa"] is None for p in out_pairs
            if p["status"] in ("UNDECIDABLE", "NOT_MODELED")),
    }
    return {
        "chain": "dpnr", "scope": B42_SCOPE, "in_blocking": False,
        "assumptions": dict(assumptions or {}, **{
            "evidence_level": "E5 (input assumptions, not physical conclusions)",
            "normalization": "Ã_ij = (∂f_i/∂x_j)·x_ref_j/f_ref_i — MUST be dimensionless",
            "kappa_is_dimensionless": True,
            "rho_policy": "逐对 κ 选策略；全局 ρ 仅登记；稀疏 Ã ⇒ NOT_MEANINGFUL",
            "conflict_policy": "κ 与 ρ 冲突 ⇒ 登记 INCONSISTENT，不静默、不改逐对策略",
        }),
        "pairs": out_pairs,
        "n_pairs": len(out_pairs), "n_decidable": n_dec,
        "n_undecidable": n_und, "n_not_modeled": n_nm,
        "rho_status": rho_status,
        # 🔴 当前无完整双向闭环 ⇒ 不输出数值 ρ（稀疏 Ã 的 ρ 无意义，不许冒充判定）
        "rho_global": None,
        "conflict_status": b42_conflict_status(
            [x["kappa"] for x in out_pairs], None),
        "normalization_check": norm,
        "invariants": inv,
        "coverage_note": ("U7 是逻辑/数学自检、非物理能力；只报逐对策略与单位缩放自检，"
                          "不判设计稳定性、不进 blocking、不改任何对外主链数字"),
        "not_included": [
            "**ρ≥1 只表示在该假设矩阵下需 MONOLITHIC 整体求解**：不代表物理设计不稳定，",
            "也不得报「算不出 / 工具失败」把数值发散包装成工具问题",
            "不含 IR→时序实际串联（产品未接线）、瞬态 C_th / 3D 热耦合 / 应力模型",
            "Ã 全部元素为 E5 输入假设（x_ref/f_ref/单位/来源逐元素登记），非 foundry PDK",
            "不作可制造性 / 可靠性 / 性能宣称；稀疏 Ã 的 ρ 无意义，不输出数值冒充判定",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 诚实清单（对外必须一起给）
# ═══════════════════════════════════════════════════════════════════════════
B3_DISCLOSURE = {
    "what": "一阶签核骨架：RC 提取（含 C）+ 多角延迟区间 + IR + EM",
    "claimable": False,
    "not_signoff": True,
    "missing_for_real_signoff": [
        "foundry RC tech file（ITF）与**经校准**的 SPEF 提取（E43 已给未校准的 SPEF 子集，缺 ITF 与硅校准）",
        "3D 场求解器（耦合电容、衬底网络）",
        "SPICE 级时序（真实器件 I-V、串扰、噪声）",
        "完整 PVT 角 + OCV/AOCV 降额",
        "动态/封装级 IR（E44 已给**静态 DC** 全域网格解；仍缺 di/dt 动态压降、decap 电荷供给、封装与板级阻抗）",
        "EM 规则表（各层 J_max、通孔许用电流）来自工艺认证",
        ("EM 的 `J_max(T)` 用 Black 温度标度，但 **`T_ref=125°C` 与 `Ea=0.9eV`/`n=1.1` "
         "均为假设** —— 标定基准未由工艺给出，基准若挪到 85°C，允许值会缩约 14×"),
        "硅实测校准（本项目无流片）",
    ],
    "corner_note": "ff/ss 的 R/C 缩放是演示量级（0.85/0.90 与 1.15/1.10），非 PVT 数据",
}
