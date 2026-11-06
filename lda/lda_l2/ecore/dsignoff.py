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
