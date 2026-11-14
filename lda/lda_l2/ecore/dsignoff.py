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
#: 🔴 **v0.9.416 标定（F5 前置）**：60nm 宽 M1 的线电容应为 **~0.2 fF/µm**（45nm 量级工艺的
#: 业界经验量级，也正是 `dextract.C_WIRE_FF_PER_UM` 用的那个量级）。而「对衬底平板」在
#: `H_ILD_UM=0.6` 下只有 **3.542e-3 fF/µm**（60nm 宽）⇒ 差 **56×** 的部分来自
#: **侧壁/边缘场**（60nm 的线只有 60nm 底板，却有 2×0.14µm 侧壁）。
#: 原值 `0.02` 是**凭空的**：它让 `wire_c` 比经验值小 **51.7×**（60nm）/ **13.8×**（240nm），
#: 也使 `dspef` 抽出的总电容比主链集总模型小 **8.95×** —— 两个模型不可互换。
#: 标定：`wire_c(1µm, 0.06µm) == 0.200000 fF/µm` ⇒ `CPP_FRINGE = 11.8868`。
#: ⚠️ 标定后 60–240nm 落在 **0.200–0.211（±5%）**，这恰恰是 `dextract` 敢用「与宽度无关
#: 的常数 0.2」的物理依据（平板 ∝ w 与侧壁 ∝ 1/w 相乘近似抵消）；宽线（>1µm）升到
#: 0.26–0.49（物理上合理：宽线由平板主导）。
#: 🔴 **主链数字不受影响**：`timing` 段用 `dextract.C_WIRE_FF_PER_UM`，**不经过本函数**
#: （A/B 实测：改 `CPP_FRINGE` 前后 `timing` 段 **逐字节相同**）。
#: 🔴 v0.9.417（F5 主体）**改口更严**：`spef` / `pvt` 两段**现在真的消费**本函数
#: ⇒ 旧说法「`run_trunk(c17)` 全报告 20126 B 逐字节相同」**已不成立**（当前 23526 B）。
#: 新口径：改 `CPP_FRINGE` ⇒ **只有 `spef`/`pvt` 变，其余 12 段逐字节不变**
#: （由 s13 的 EC-G49 / EC-G53 双条机核）。这正是「新段真在消费、且耦合面被限制」的证据。
CPP_FRINGE = 11.8868      # 标定：使 wire_c(1µm, 0.06µm) == 0.2000 fF/µm

#: 标定记录（供判据机核 + 外部复核）。改任何一项都必须同步改本字典。
WIRE_C_CALIBRATION = {
    "anchor_width_um": 0.06,
    "anchor_c_ff_per_um": 0.2,
    "plate_only_ff_per_um": 0.003542,
    "cpp_fringe": CPP_FRINGE,
    "sidewall_share": "0.196458 / 0.200000 = 98.2% 来自侧壁/边缘场",
    "flatness": "w=0.06..0.24 µm ⇒ 0.200000..0.210625（±5%）",
    "wide_line_trend": "w=1/2/5 µm ⇒ 0.255/0.315/0.492 fF/µm（平板主导，物理合理）",
    "residual_vs_dextract": ("SPEF Σc=13.7156 fF vs 主链 15.812 fF = −13.3%"
                             "（dextract 不分层；宽线 wire_c 更高，故差额不是单调的）"),
    "changes_main_chain": False,
    "prior_value": 0.02,
    "prior_was": "凭空的（无出处），导致 wire_c 比经验值小 51.7×@60nm / 13.8×@240nm",
}

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
    """一阶线电容（fF）：平板 `ε₀ε_r·A/h` ×（`1 + 2·t/w·CPP_FRINGE`）。

    🔴 `CPP_FRINGE` 在本仓是「**侧壁 + 边缘场的总系数**」，不是「每边一个小修正」——
    v0.9.416 标定后它使 60nm 线命中 0.2 fF/µm（侧壁占 98.2%），见 `WIRE_C_CALIBRATION`。
    原值 0.02 让侧壁项贡献不足 1%，等于把「线电容」错当成「对衬底平板电容」。

    单位换算：F → fF ×1e15；长度/宽度以 µm 传入。`wire_c(1.0, w)` 就是 fF/µm。
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
# ④b T3：签核台账（把「数字」变成「数字 + 判定状态」）
#   🔴 为什么放在 `dsignoff`：签核的第一个问题就是「这个数过不过」。
#      在此之前，`drc=0` 与 `slack(wired)=−21.163 ps` 在报告里长得一样 ——
#      读者只能自己判断哪个是达标、哪个是违例、哪个**根本没人管**。
#   🔴 判定逻辑在 `dprovenance.constraint_report`（那边有 12 条反向构造自检）；
#      本函数只负责「签核语境」：进 blocking 的口径仍由 `claimability` 决定，**不在这里**。
# ═══════════════════════════════════════════════════════════════════════════
def signoff_ledger(report, netlist=None):
    """签核台账：逐数字给出「支配约束 / 裕量 / 五态颜色 / 适用范围」。

    🔴 函数内 import `dprovenance`：顶层 import 会让 `dsignoff` 在 `dpnr` 之前拉入整条
    几何链（`dpnr → dcroute/dmtrack/...`），依赖顺序变脆；而 AST 扫描**能看见**函数内
    import ⇒ 依赖图照旧记边，不是"藏起来"。

    ⚠️ 返回的是**判定状态**，不是签核结论：`claimable` 仍由 `claimability()` 六条决定。
    """
    from . import dprovenance as PV
    out = PV.constraint_report(report, netlist)

    # 🔴 P5（v0.9.401）：单元版图覆盖 —— **只加顶层键、绝不动 `rows`**。
    #   `rows` 的行数与 `verdict` 取值叶子数被 `EC-W01`（12 个叶子）与 `EC-W06`
    #   （area/def_bytes 必须 UNCONSTRAINED）锁定；往 rows 里塞一行会把那两条判据打红。
    #   签核台账里"这颗单元有没有版图"本来就是一等问题，所以放在台账顶层。
    try:
        from . import dcelltpl as TP
        cov = TP.coverage()
        out["cell_layout_coverage"] = {
            "n_templated": cov["n_templated"],
            "n_total": cov["n_total"],
            "status": ("PARTIAL" if 0 < cov["n_templated"] < cov["n_total"] else
                       ("FULL" if cov["n_templated"] == cov["n_total"] else "NONE")),
            "why_missing": {k: v["status"] for k, v in cov["cells"].items()
                            if v["status"] != "TEMPLATED"},
            "scope": "DIAGNOSTIC_ONLY",
            "not_claimed": ("模板覆盖 ≠ 可造性覆盖：2/18 有「逐位等价模板」，"
                            "不等于另外 16 个不可造 —— 它们只是还没有版图"),
        }
    except Exception as exc:                       # noqa: BLE001 — 覆盖算不出来不能拖垮台账
        out["cell_layout_coverage"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    # 🔴 P2（v0.9.402）：驱动能力的**结构可算性** —— 同样只加顶层键、不动 `rows`。
    #   结论是「形状可算、绝对值不可算」，所以 `k_drive` **仍在 unattr 表**（DoD② 未达成）。
    try:
        from . import dkdrive as KD
        rep = KD.deviation_report()
        out["drive_model"] = {
            "n_cells": rep["n_cells"],
            "median_abs_dev": rep["median_abs_dev"],
            "max_abs_dev": rep["max_abs_dev"],
            "by_class": rep["by_class"],
            "k_drive_source": "hand_filled（模型只判形状，不改值）",
            "scope": "DIAGNOSTIC_ONLY",
            "not_claimed": ("不改 `k_drive`/`t_intr`，主链 9 数一位未动；"
                            "「截距独立算出」不成立（缺 W/L 与 μ 标定）"),
        }
    except Exception as exc:                       # noqa: BLE001
        out["drive_model"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    # 🔴 v0.9.403（W/L 数据层）：几何模型 + 代数上限定理 + 反解 μ —— 同样只加顶层键。
    #   结论是**手填表与均匀几何不相容**（3 个值超上限），所以 `k_drive` 仍在 unattr。
    try:
        from . import dkdrive as KD
        from . import dcell as DC
        _wl = DC.wl_provenance_summary()
        _cr = KD.ceiling_report()
        _ir = KD.implied_mu_report()
        _bl = KD.balance_report()
        out["drive_geometry"] = {
            "w_l_provenance": _wl,
            "n_in_scope": _cr["n_in_scope"],
            "ceiling_violations": _cr["violations"],
            "ceiling_statement": ("均匀 W ⇒ k ≤ max(s_n, s_p)（与 μ、与 W 的绝对量无关；"
                                  "机核：`ceiling_bound_check` 扫 2D 网格不越界）"),
            "implied_mu": {"by_status": _ir["by_status"],
                           "range": _ir["mu_range"], "textbook": _ir["textbook_mu"]},
            "pmos_balanced": _bl["balanced"],
            "pmos_ratio": _bl["pn_ratio"],
            "k_drive_source": "hand_filled（几何模型只判不改）",
            "scope": "DIAGNOSTIC_ONLY",
            "not_claimed": ("不改 `k_drive`，主链 9 数一位未动；"
                            "16/18 个单元的 W 是规则外推不是实测；"
                            "「补了 W/L ⇒ k 可算」**不成立**（3 个值超代数上限）"),
        }
    except Exception as exc:                       # noqa: BLE001
        out["drive_geometry"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    # 🔴 v0.9.409（F0-1）：**漏电入报表** —— `ileak_na_per_tr` 此前**零消费**
    #   （审计脚本 E08 实测：产品链里只有 `dcell.py` 的定义处，没有任何消费者）。
    #   功耗域因此只有动态功耗、没有静态功耗，而「1340 门控制壳的漏电」是必答项。
    #   归因：`dsignoff` 只报 switching/clock，漏电被写成「一阶估计、不参与判决」之后就没人用了 ——
    #   **「有参数、有注释、无消费者」是一种静默的能力缺口**，任何只查定义不查调用的判据都发现不了。
    try:
        _lk = {}
        for g in netlist.gates:
            _lk[g.cell] = _lk.get(g.cell, 0.0) + DC.cell_leak_nw(g.cell)
        _lk_total = sum(_lk.values())
        out["leakage"] = {
            "scope": "DIAGNOSTIC_ONLY",
            "in_blocking": False,
            "unit": "nW",
            "by_cell": {k: round(v, 9) for k, v in sorted(_lk.items())},
            "total_nw": round(_lk_total, 9),
            "per_gate_nw": (round(_lk_total / len(netlist.gates), 9)
                            if netlist.gates else 0.0),
            "n_gates": len(netlist.gates),
            "basis": ("SYMBOLIC · n_tr × ileak_na_per_tr × vdd（一阶，"
                      "claimable=False）"),
            "not_claimed": ("室温单管估计：无 stacking effect、无温度/工艺依赖、"
                            "无多阈值单元，也不与动态功耗合并成总能效"),
        }
    except Exception as exc:                       # noqa: BLE001
        out["leakage"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    # 🔴 v0.9.407：pMOS 平衡**买到了多少延时** —— 只加顶层键、不动 `rows`。
    #   为什么必须给：v0.9.404 的 README 曾把「单元级 2.50×」写得像链级收益，
    #   而 c17 实测只有 1.50×（拓扑路径）/ 1.25×（延迟关键路径）。
    #   这两个数必须**同时**出现在签核台账里，否则「加宽 pMOS」看起来像白拿 2.5×。
    try:
        from . import dsta as _ST          # 同包内相对导入（ 在 cwd 下解析不到）
        _path = [g.cell for g in _ST.longest_path_gates(netlist)]
        _rep = _ST.sizing_gain_chain(_path)
        _gains = {n: DC.pmos_sizing_gain(c) for n, c in DC.CELLS.items() if c.w_n_nm}
        _dom = {}
        for n, c in DC.CELLS.items():
            if c.w_n_nm:
                _dom.setdefault(DC.sizing_dominance(c), []).append(n)
        out["pmos_sizing"] = {
            "scope": "DIAGNOSTIC_ONLY",
            "in_blocking": False,
            "cell_gain": _gains,
            "by_dominance": {k: sorted(v) for k, v in _dom.items()},
            "path_cells": _path,
            "path_gain": _rep["gain"],
            "path_uniform_load": _rep["uniform_load"],
            "path_delay_ps": [_rep["delay_bal_ps"], _rep["delay_1to1_ps"]],
            "unit_gain_max": max(_gains.values()) if _gains else None,
            "why_path_lt_unit": (
                "链级收益 = Σ R(1:1)·w / Σ R(平衡)·w（w=ln2·(C_self+C_load)）；"
                "负载均匀时 w 可约 ⇒ = ΣR 比（纯几何，与 FO 无关）。"
                "c17 拓扑路径 = %r，逐级 %r ⇒ %.4f×，**不是**单元级的 %.2f×："
                "下拉主导的单元在 1:1 下本来就是下拉限制，加宽 p 侧救不了它"
                % (_path, [round(r["cell_gain"], 4) for r in _rep["cells"]],
                   _rep["gain"], max(_gains.values()) if _gains else 0.0)),
            "not_claimed": (
                "① 只看延时，不含面积代价（面积已在 v0.9.404 计入 +13.0%）；"
                "② 「延迟关键路径」与「拓扑路径」组成不同，两者的收益不同（c17: 1.25× vs 1.50×）；"
                "③ 上拉主导的 testcase 只到**时序级**（`PHYSICALLY_MODELED` 仍只有 INV/NAND2，"
                "建不出 NOR 版图）；④ 绝对延时仍 `claimable=False`"),
        }
    except Exception as exc:                       # noqa: BLE001
        out["pmos_sizing"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    return out


# ═══════════════════════════════════════════════════════════════════════════
# ⑤b EC-B3.1：几何 / 量纲诊断（只报谱与不变式，不判违规、不进 blocking）
#   🔴 与门禁 `run_ecore_s13_smoke` 的独立复算走**不同算法路径**（K2）：
#      门禁 = 扫描线坐标压缩（`_ec_union`）+ 逐窗二维裁剪（`_ec_dens`）；
#      本侧 = 增量矩形差集 + 可分离一维累积函数差分。
#      两侧结果必须逐位一致，且源码互不引用 —— 「两实现」≠「两条独立路径」。
#   🔴 段内**不设** `n_fail` / `ok` / `pass` —— 本段是诊断，不是判决。
# ═══════════════════════════════════════════════════════════════════════════
def b3_scales(die_w_um, width_um):
    """密度谱的尺度集合 —— **由尺寸反解，不写死**（Q2/v0.9.396）。

    🔴 旧实现是死常量 `(1,2,4,8,16,32)`：几何一缩，`n=32` 时窗口宽 `die_w/32`
    会比一条线（0.24µm）还窄 —— 那个尺度**失去定义**（实测 Q2 后 7.590/32 = 0.2372 < 0.24）。
    死常量在这种情形下只有两种结局：要么崩（`i_scale_upper_bound` 判假），要么被人
    偷偷放宽判据。正解是**反解上界**：`s_max = 2^⌊log2(die_w/width)⌋`，
    再细分一档就装不下一条线 ⇒ 谱到 `s_max` 为止。
    """
    import math as _m
    ratio = float(die_w_um) / float(width_um)
    if ratio < 1.0:
        return (1,)
    s_max = 2 ** int(_m.floor(_m.log2(ratio) + 1e-12))
    return tuple(s for s in (2 ** k for k in range(0, 12)) if s <= s_max)
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
                  scales=None) -> dict:
    """逐层密度谱 + 四口径比值谱（**诊断段**：不判违规、不进 blocking）。

    输入全部显式（K0 完备性）：几何 / die 尺寸 / 唯一线宽 / 尺度集合 / 四个分母口径。
    所有 `g` 均为**代理量与假设**（门总面积、单门、单管、单元外框），非工艺认证。
    """
    metals = [s for s in shapes if getattr(s, "kind", None) == "metal"]
    layers = sorted({int(s.layer) for s in metals})
    # 🔴 Q2：尺度谱按**本片尺寸反解**（缺省即派生；显式传入仍被尊重，供反向探针用）
    if scales is None:
        scales = b3_scales(die_w_um, width_um)
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
            # EC-B4.6：证据维度与可判性维度分开（§16.2 不许合标量）。
            # 只有声明了 evidence_status 的对才带这两个字段；旧字段语义与取值全不动。
            **({"evidence_status": p["evidence_status"],
                "evidence_source": p["evidence_source"]}
               if "evidence_status" in p else {}),
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
