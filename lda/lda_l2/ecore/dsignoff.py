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
| 延迟 | Elmore：`R·(C_wire/2 + C_load)`；另给 N 段梯形网络的**离散解**做互证 |
| 多角 | ff/ss 对 R、C 各乘一套系数，给出**延迟区间**（不是单点） |
| IR | 均匀抽流的均匀轨：末端压降 `I·R/2`；另给离散节点方程解做互证 |
| EM | `J = I/(w·t)` 对 `J_MAX` 判定（含裕量） |

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

# ---- 物理常数与一阶工艺假设（全部显式，便于外部替换）----
EPS0 = 8.854e-12          # F/m
EPSR_ILD = 4.0            # SiO₂ 相对介电常数
H_ILD_UM = 0.6            # M3 到衬底的有效介质厚度
T_METAL_UM = 0.14         # 金属厚度（M3/M4）
CPP_FRINGE = 0.02         # 边缘电容系数（每边，按 w 归一）—— 一阶修正

RSH = {"M3": 0.12, "M4": 0.10}      # Ω/□（演示量级）
C_LOAD_FF = 1.0                     # 典型扇出负载电容（假设）
J_MAX_A_M2 = 1.0e10                 # 1e6 A/cm²（公开量级假设，非工艺认证）

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
    """分布式 RC 线 + 集中负载的一阶 50% 延迟（ps）：`R·(C/2 + C_load)`。"""
    return r_ohm * (c_ff / 2.0 + c_load_ff)


def elmore_ladder(r_ohm: float, c_ff: float, n: int, c_load_ff: float = C_LOAD_FF) -> float:
    """把线切成 n 段：每段 R/n、C/n，末段带负载 C_load，按 Elmore 求和（ps）。

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
    """某角下的延迟（ps）。`use_ladder_n>0` 时改用离散梯形解（互证用）。"""
    if corner not in CORNERS:
        raise KeyError("unknown corner: %r" % (corner,))
    kr, kc = CORNERS[corner]
    r = rc["r_ohm"] * kr
    c = rc["c_ff"] * kc
    if use_ladder_n:
        return elmore_ladder(r, c, use_ladder_n, c_load_ff)
    return elmore_closed(r, c, c_load_ff)


def corner_table(rc: dict) -> dict:
    """三角延迟表 + 区间（min/max）+ 相对 tt 的散布。"""
    d = {k: round(delay_at_corner(rc, k), 6) for k in CORNERS}
    lo, hi = min(d.values()), max(d.values())
    return {"delay_ps": d, "min_ps": round(lo, 6), "max_ps": round(hi, 6),
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
def em_check(i_a: float, width_um: float, t_um: float = T_METAL_UM,
             j_max: float = J_MAX_A_M2) -> dict:
    """`J = I/(w·t)`（A/m²）对 `J_MAX` 判定，返回电流密度、裕量与是否通过。"""
    area_m2 = (width_um * 1e-6) * (t_um * 1e-6)
    j = i_a / area_m2
    return {"j_a_m2": j, "margin_x": j_max / j if j > 0 else float("inf"),
            "ok": j <= j_max, "j_max": j_max}


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 诚实清单（对外必须一起给）
# ═══════════════════════════════════════════════════════════════════════════
B3_DISCLOSURE = {
    "what": "一阶签核骨架：RC 提取（含 C）+ 多角延迟区间 + IR + EM",
    "claimable": False,
    "not_signoff": True,
    "missing_for_real_signoff": [
        "foundry RC tech file（ITF）与经校准的 SPEF 提取",
        "3D 场求解器（耦合电容、衬底网络）",
        "SPICE 级时序（真实器件 I-V、串扰、噪声）",
        "完整 PVT 角 + OCV/AOCV 降额",
        "电源网格全 \(\\mathbf{I\\cdot R}\) 求解（本模块只做均匀抽流一阶）",
        "EM 规则表（各层 J_max、通孔许用电流）来自工艺认证",
        "硅实测校准（本项目无流片）",
    ],
    "corner_note": "ff/ss 的 R/C 缩放是演示量级（0.85/0.90 与 1.15/1.10），非 PVT 数据",
}
