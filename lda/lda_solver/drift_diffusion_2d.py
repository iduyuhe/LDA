"""LDA · T1 电学/TCAD 数值内核（C 级第一天自主）· 2D p-n 结漂移-扩散+连续性。

🔴 主权边界（T1 分层解锁 · 研发规划 §1.1 / §3 T1-B）：
- 本模块为 T1 数值内核（载流子输运 PDE）的 **2D 扩面**（T1-B-W4），在 W2 的 1D
  自洽泊松-玻尔兹曼内核之上，将离散化从 1D 推广到 2D（5 点有限差分），并新增
  **偏压下的漂移-扩散载流子输运**（Gummel 迭代：准费米势连续性方程 + 线性泊松）
  以解终端 I(V)。
- **零外部依赖**（仅 numpy + scipy）；**不 import 任何 A 级美系商业求解器**
  （Sentaurus / Lumerical DEVICE / COMSOL 半导体），**不 import DEVSIM**
  （B 级，仅作同几何同边界双向标定的外部 ORACLE，见 T1-B-W3）。
- 🔴 **T1 输出不作 ORACLE（红线）**：本模块解出的 n/p/φ(x,y) 与 I(V) 仅为
  **候选（candidate）**，判决仍由物理定律锚 / 教科书闭式 golden（Sze
  耗尽近似 / 理想二极管律）/ foundry 实测 / 公开文献定。
  `T1_OUTPUT_IS_ORACLE=False` 为铁律开关；`guard_t1_not_oracle()` 为反向测试守卫。
- 🔴 **EAR 744.23 成熟节点用途声明**：本内核声明仅用于成熟节点 /
  非先进用途半导体器件设计仿真。见 docs/ 合规件（T1-B-W3）。

物理（Sze《Physics of Semiconductor Devices》§2.2 突变 p-n 结）：
- 平衡：泊松 ∇²φ = −(q/ε)(n − p + N_D − N_A)；电中性 + 质量作用 +
  费米平坦 ⇒ n=n_i·exp(φ/V_T), p=n_i·exp(−φ/V_T)。
- 偏压输运（Gummel）：电子/空穴连续性 ∇·J_n=0, ∇·J_p=0（稳态 G=R），
  J_n=q·μ_n·n·E+q·D_n·∇n，J_p=q·μ_p·p·E−q·D_p·∇p，准费米势 BC 在接触处分裂 V。
- golden（确定性物理定律闭式）：
  耗尽近似 W=√(2ε·V_bi/q·(N_A+N_D)/(N_A·N_D))、E_max=q·N_D·x_n/ε、
  耗尽电荷 Q_dep=q·N_D·x_n（几何无关，由电中性定）、
  理想二极管 I=I_s·(exp(qV/kT)−1)，I_s 由长二极管低注入闭式定。

与 golden 的方法学独立性（判据 D 真数值）：
- golden = 解析耗尽近似（突变结、耗尽区 n,p≈0）/ 理想二极管律（长二极管低注入）
- cand   = 自洽玻尔兹曼统计数值解（耗尽区少数载流子指数衰减，非严格 0）
⇒ |cand−golden| 反映耗尽近似 / 低注入近似的固有截断误差，随网格加密收敛。
LLM 不进判决路径。
"""
from __future__ import annotations

import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

# ---- 物理常数（SI） ----
Q_E = 1.602176634e-19          # 电子电荷 (C)
EPS0 = 8.854187817e-12         # 真空介电 (F/m)
EPS_SI = 11.7 * EPS0          # Si 相对介电
K_B = 1.380649e-23             # 玻尔兹曼 (J/K)
T_KELVIN = 300.0
V_T = K_B * T_KELVIN / Q_E    # 热电压 ≈ 0.02585 V
N_I = 1.0e16                   # Si 本征载流子浓度 (m^-3, ≈1e10 cm^-3)

# 输运参数（Si，文献值；仅用于偏压 Gummel，闭式 I_s 同源）
MU_N = 0.135                   # 电子迁移率 (m^2/V/s, ~1350 cm^2/Vs)
MU_P = 0.048                   # 空穴迁移率 (m^2/V/s, ~480 cm^2/Vs)
D_N = MU_N * V_T              # 爱因斯坦关系 (m^2/s)
D_P = MU_P * V_T
TAU_N = 1.0e-7                # 电子寿命 (s)
TAU_P = 1.0e-7                # 空穴寿命 (s)
L_N = math.sqrt(D_N * TAU_N)  # 电子扩散长度 (m)
L_P = math.sqrt(D_P * TAU_P)

# 🔴 红线开关：T1 输出永不作 ORACLE
T1_OUTPUT_IS_ORACLE = False

# 默认掺杂 / 几何（典型突变结，非对称 p+n；平面结居中）
N_A_DEFAULT = 1.0e23           # 受主 (m^-3, 1e17 cm^-3)
N_D_DEFAULT = 1.0e22           # 施主 (m^-3, 1e16 cm^-3)
LX_DEFAULT = 4.0e-6           # 器件 x 总长 (m, 4 µm)
LY_DEFAULT = 4.0e-6           # 器件 y 总长 (m, 4 µm)
X0_FRAC = 0.5                 # 突变结位置（居中）


def doping_profile_2d(xx: np.ndarray, yy: np.ndarray, N_A: float, N_D: float,
                      x0: float, mesa: bool = False,
                      mesa_y0: float = 1.0e-6, mesa_y1: float = 3.0e-6) -> tuple:
    """2D 突变结掺杂剖面对角。

    - 平面结（mesa=False）：x<x0 受主 p 侧、x>x0 施主 n 侧，y 方向均匀。
    - 台面结（mesa=True）：n 区仅在 y∈[mesa_y0,mesa_y1] 的带窗（接触的几何窗口），
      制造真正的 2D 边缘电场（fringing）。电中性仍保证总耗尽电荷 = q·N_D·x_n·窗长。
    - 🔴 mesa_y0/mesa_y1 为 **绝对 y 坐标（m）**，调用方须将分数 × Ly 后传入。
    """
    NA = np.where(xx < x0, N_A, 0.0)
    ND = np.where(xx > x0, N_D, 0.0)
    if mesa:
        win = (yy >= mesa_y0) & (yy <= mesa_y1)
        ND = np.where(win, ND, 0.0)  # 窗外用绝缘（ND=0），形成 2D 台面
    return NA, ND


def _idx(i: int, j: int, ny: int) -> int:
    return i * ny + j


def _build_laplacian(nx: int, ny: int, dx: float, dy: float) -> sp.csr_matrix:
    """组装离散拉普拉斯算子 L（含 y 方向诺伊曼无通量 BC、x 方向由调用方置 Dirichlet）。

    返回 (nx*ny × nx*ny) CSR。L φ 给出离散 ∇²φ；x=0/nx-1 行由调用方改写为恒等（Dirichlet）。
    """
    n = nx * ny
    rows = []
    cols = []
    vals = []
    ix2 = 1.0 / dx ** 2
    iy2 = 1.0 / dy ** 2
    for i in range(nx):
        for j in range(ny):
            k = _idx(i, j, ny)
            diag = -2.0 * (ix2 + iy2)
            # x 邻居（边界用单侧差近似诺伊曼，此处先按内部；x 边界由 Dirichlet 覆盖）
            if i > 0:
                rows.append(k); cols.append(_idx(i - 1, j, ny)); vals.append(ix2)
            if i < nx - 1:
                rows.append(k); cols.append(_idx(i + 1, j, ny)); vals.append(ix2)
            # y 邻居：诺伊曼 ∂/∂y=0 → 边界侧系数加倍（ghost=邻点），每节点仅加 1 次
            if j == 0:
                rows.append(k); cols.append(_idx(i, 1, ny)); vals.append(2.0 * iy2)
            elif j == ny - 1:
                rows.append(k); cols.append(_idx(i, ny - 2, ny)); vals.append(2.0 * iy2)
            else:
                rows.append(k); cols.append(_idx(i, j - 1, ny)); vals.append(iy2)
                rows.append(k); cols.append(_idx(i, j + 1, ny)); vals.append(iy2)
            rows.append(k); cols.append(k); vals.append(diag)
    L = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    return L


def _solve_with_dirichlet(L: sp.csr_matrix, b: np.ndarray, nx: int, ny: int,
                          phi_left: float, phi_right: float) -> np.ndarray:
    """解 L φ = b，并把 x=0 / x=nx-1 整列钉为 Dirichlet（φ=phi_left/right）。"""
    n = nx * ny
    A = L.tolil()
    b = b.copy()
    # 钉 Dirichlet 列
    for j in range(ny):
        for i, val in ((0, phi_left), (nx - 1, phi_right)):
            k = _idx(i, j, ny)
            A.rows[k] = [k]
            A.data[k] = [1.0]
            b[k] = val
    A = A.tocsr()
    phi = spla.spsolve(A.tocsc(), b)
    return phi


def solve_pn_junction_2d_equilibrium(N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                                     Lx: float = LX_DEFAULT, Ly: float = LY_DEFAULT,
                                     nx: int = 80, ny: int = 80, x0: float | None = None,
                                     eps: float = EPS_SI, n_i: float = N_I,
                                     v_t: float = V_T, mesa: bool = False,
                                     mesa_y0: float = 0.25, mesa_y1: float = 0.75,
                                     max_iter: int = 400, resid_tol: float = 1e-8,
                                     step_cap: float = 0.05) -> dict:
    """2D 自研 p-n 结热平衡载流子分布（T1 内核候选，2D 扩面）。

    返回 dict：xx/yy/phi/n/p/E_mag/x/y 网格 + 中轴线剖面对 / V_bi/W/x_n/x_p/E_max/
                Q_dep(数值积分)/Q_dep_sze / dx/dy / provenance / is_oracle / converged。

    🔴 红线自检：纯 numpy+scipy 自洽泊松求解，无光子有源物理、无 A 级求解器、
    无 DEVSIM import ⇒ 不破主权/验证纪律红线。输出 is_oracle=False。
    """
    if x0 is None:
        x0 = Lx * X0_FRAC
    x = np.linspace(0.0, Lx, nx)
    y = np.linspace(0.0, Ly, ny)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    NA, ND = doping_profile_2d(xx, yy, N_A, N_D, x0, mesa=mesa,
                              mesa_y0=mesa_y0 * Ly, mesa_y1=mesa_y1 * Ly)
    phi_p = -v_t * math.log(N_A / n_i)   # p 侧接触费米势
    phi_n = v_t * math.log(N_D / n_i)    # n 侧接触费米势
    V_bi = phi_n - phi_p
    # 初始猜测：线性插值
    phi = np.linspace(phi_p, phi_n, nx)[:, None] * np.ones((1, ny))
    phi = phi.flatten()
    L = _build_laplacian(nx, ny, dx, dy)
    converged = False
    for _ in range(max_iter):
        n = n_i * np.exp(phi / v_t)
        p = n_i * np.exp(-phi / v_t)
        rho = (Q_E / eps) * (p - n + ND.flatten() - NA.flatten())
        diag_corr = (Q_E / eps) * (-2.0 * n_i / v_t) * np.cosh(phi / v_t)
        # 残差 r = L φ + rho  (与 1D 内核同一符号约定，Lφ = -(q/ε)(p-n+ND-NA))
        r = L.dot(phi) + rho
        # 牛顿雅可比 J = L + diag(diag_corr)
        J = L + sp.diags(diag_corr)
        # 牛顿系统求解的是「修正量 delta」而非 φ 本身 ⇒ Dirichlet 行须置恒等、
        # 右端 b=0（delta=0，BC 钉死），否则 b=val 会令 delta[BC]=val 把边界
        # 条件每轮拉偏 step_cap（这正是 2D 发散的根因；1D 内核靠更新后显式复位 BC）。
        A = J.tolil()
        b = -r
        for j in range(ny):
            for i in (0, nx - 1):
                k = _idx(i, j, ny)
                A.rows[k] = [k]; A.data[k] = [1.0]; b[k] = 0.0
        A = A.tocsr()
        delta = spla.spsolve(A.tocsc(), b)
        delta = np.clip(delta, -step_cap, step_cap)
        phi_new = phi + delta
        # BC 显式钉死（与 1D 内核一致，双重保险）
        for j in range(ny):
            phi_new[_idx(0, j, ny)] = phi_p
            phi_new[_idx(nx - 1, j, ny)] = phi_n
        if np.max(np.abs(phi_new - phi)) < resid_tol:
            phi = phi_new
            converged = True
            break
        phi = phi_new
    n = n_i * np.exp(phi / v_t)
    p = n_i * np.exp(-phi / v_t)
    phi2 = phi.reshape(nx, ny)
    grad = np.gradient(phi2, dx, dy, edge_order=2)
    Ex, Ey = -grad[0], -grad[1]
    E_mag = np.sqrt(Ex ** 2 + Ey ** 2).flatten()
    E_max = float(np.max(E_mag))
    # ---- 电荷法稳健提取耗尽宽度（不依赖阈值探测，粗网格也稳）----
    # n 侧（施主区，含 mesa 窗）净正耗尽电荷 Qn = ∫ q(N_D - N_A + p - n) dV。
    # bulk 区 n≈N_D/p≈N_A ⇒ 该项≈0；仅耗尽区贡献 ⇒ Qn = q·N_D·x_n·Wy_eff。
    nside = ND.flatten() > 0.0
    dA = dx * dy
    Qn = Q_E * float(np.sum((ND.flatten() - NA.flatten()
                             + p.flatten() - n.flatten())[nside])) * dA
    Wy_eff = Ly if not mesa else (Ly * (mesa_y1 - mesa_y0))  # 有效 n 侧 y 窗长（分数×Ly 已绝对化）
    x_n = Qn / (Q_E * N_D * Wy_eff)     # 电荷中性 ⇒ = q·N_D·x_n·Wy_eff
    x_p = Qn / (Q_E * N_A * Wy_eff)
    W = x_n + x_p
    Q_dep_num = Qn
    # Sze 闭式耗尽电荷（每单位 y 长度 q·N_D·x_n_sze；总 = × 有效窗长）
    gold_xn = math.sqrt(2.0 * eps * V_bi / Q_E * (N_A + N_D) / (N_A * N_D)) * N_A / (N_A + N_D)
    Q_dep_sze = Q_E * N_D * gold_xn * Wy_eff
    # 中轴线（j=ny//2）1D 剖面对（供判据 D 比对 Sze 用）
    jmid = ny // 2
    xa = x
    na = n.reshape(nx, ny)[:, jmid]
    return {
        "xx": xx, "yy": yy, "phi": phi2, "n": n.reshape(nx, ny),
        "p": p.reshape(nx, ny), "E_mag": E_mag.reshape(nx, ny),
        "x_axis": xa, "n_axis": na,
        "V_bi": float(V_bi), "W": float(W), "x_n": float(x_n), "x_p": float(x_p),
        "E_max": E_max, "Q_dep_num": float(Q_dep_num), "Q_dep_sze": float(Q_dep_sze),
        "dx": float(dx), "dy": float(dy), "nx": nx, "ny": ny, "mesa": mesa,
        "provenance": "self_authored_t1_candidate",
        "is_oracle": False, "converged": converged,
    }


def sze_pn_junction_2d_closed_form(N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                                   Lx: float = LX_DEFAULT, Ly: float = LY_DEFAULT,
                                   x0: float | None = None, eps: float = EPS_SI,
                                   n_i: float = N_I, v_t: float = V_T) -> dict:
    """Sze 教科书闭式耗尽近似（golden，确定性物理定律锚）+ 理想二极管 I_s 闭式。"""
    if x0 is None:
        x0 = Lx * X0_FRAC
    V_bi = v_t * math.log(N_A * N_D / (n_i * n_i))
    W = math.sqrt(2.0 * eps * V_bi / Q_E * (N_A + N_D) / (N_A * N_D))
    x_n = W * N_A / (N_A + N_D)
    x_p = W * N_D / (N_A + N_D)
    E_max = Q_E * N_D * x_n / eps
    # 理想二极管饱和电流（长二极管低注入，每单位 y 长度）
    J_s = Q_E * (D_N * n_i * n_i / (L_N * N_A) + D_P * n_i * n_i / (L_P * N_D))
    I_s = J_s * Ly
    Q_dep_sze = Q_E * N_D * x_n * Ly
    # 短二极管饱和电流（无复合 / ∇·J=0 数值解对应；准中性区宽 W_p,W_n 替代扩散长度）
    W_p = x0 - x_p
    W_n = (Lx - x0) - x_n
    J_s_short = Q_E * (D_N * n_i * n_i / (N_A * W_p) + D_P * n_i * n_i / (N_D * W_n))
    I_s_short = J_s_short * Ly
    return {
        "V_bi": float(V_bi), "W": float(W), "x_n": float(x_n), "x_p": float(x_p),
        "E_max": float(E_max), "I_s": float(I_s), "J_s": float(J_s),
        "I_s_short": float(I_s_short), "J_s_short": float(J_s_short),
        "W_p": float(W_p), "W_n": float(W_n),
        "Q_dep_sze": float(Q_dep_sze),
        "x_n_pos": float(x0 + x_n), "x_p_pos": float(x0 - x_p),
        "provenance": "design_rule_anchor_sze_depletion",
    }


def _bernoulli(x: np.ndarray) -> np.ndarray:
    """Bernoulli 函数 B(x)=x/(exp(x)-1)，B(0)=1，数值稳定（SG 离散核心）。"""
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    small = np.abs(x) < 1e-10
    out[small] = 1.0 - x[small] / 2.0
    big = ~small
    out[big] = x[big] / np.expm1(x[big])
    return out


def _solve_continuity_sg(flag: str, phi_flat: np.ndarray, nx: int, ny: int,
                         dx: float, dy: float, bc_left: float, bc_right: float) -> np.ndarray:
    """Scharfetter-Gummel 离散解稳态连续性 ∇·J = 0（电子 flag='n' / 空穴 flag='p'）。

    变量 = 载流子密度 n/p（未知）；静电势 φ **固定**（Gummel 解耦，本轮不更新）。
    SG 形式 1：Bernoulli 自变量 = 静电势差 η = φ/V_T（电子/空穴同），
      - φ 有界（~±0.4 V）⇒ η 有界（~±16），SG 对 exp(φ/V_T) 任意量级无条件稳定，
        克服简单 FD 在偏压下系数跨 10^13+ 致矩阵奇异。
      - 电流离散（边 k→m）J = (q·D/h)·[c_k·B(η_k-η_m) − c_m·B(η_m-η_k)]，
        电子/空穴对角 Bernoulli 系数按 flag 分支（扩散项+漂移项符号独立验证）。
    x=0 / nx-1 钉为 Dirichlet（接触载流子密度）；**x 边界入射边的耦合移入右端**
    （已知边界值，符号为正），避免 Dirichlet 行污染矩阵（否则注入伪通量）。
    y 方向无通量（自然 Neumann，y 边正常保留）。
    """
    # SG 形式 1：Bernoulli 自变量 = 静电势差 η=φ/V_T（电子/空穴同）；
    # 电子/空穴的对角 Bernoulli 系数不同（已用扩散项+漂移项独立验证符号）。
    eta = phi_flat / V_T
    mu = MU_N if flag == "n" else MU_P
    g = Q_E * mu * V_T  # q·μ·V_T 前置因子
    n = nx * ny
    rows = []; cols = []; vals = []
    b = np.zeros(n)

    def _val_of(i: int):
        if i == 0:
            return bc_left
        if i == nx - 1:
            return bc_right
        return None

    # 每条内部边 (k→右/上邻 m)，仅访问一次；贡献双方行
    for i in range(nx):
        for j in range(ny):
            k = _idx(i, j, ny)
            for (ni, nj, h) in ((i + 1, j, dx), (i, j + 1, dy)):
                if ni >= nx or nj >= ny:
                    continue
                m = _idx(ni, nj, ny)
                a_km = _bernoulli(eta[k] - eta[m])   # B(η_k-η_m)
                a_mk = _bernoulli(eta[m] - eta[k])   # B(η_m-η_k)
                # 电子：行 k 自 a_km / 邻 −a_mk；行 m 自 a_mk / 邻 −a_km
                # 空穴：行 k 自 a_mk / 邻 −a_km；行 m 自 a_km / 邻 −a_mk
                if flag == "n":
                    ck_self, ck_other = a_km, -a_mk
                    cm_self, cm_other = a_mk, -a_km
                else:
                    # 空穴：正统 SG 电流 J=(g/h)(p_m·B_km − p_k·B_mk)，与电子对称
                    ck_self, ck_other = -a_mk, a_km
                    cm_self, cm_other = -a_km, a_mk
                vk = _val_of(i)
                vm = _val_of(ni)
                if vk is None and vm is None:
                    rows.append(k); cols.append(k); vals.append(g / h * ck_self)
                    rows.append(k); cols.append(m); vals.append(g / h * ck_other)
                    rows.append(m); cols.append(m); vals.append(g / h * cm_self)
                    rows.append(m); cols.append(k); vals.append(g / h * cm_other)
                elif vk is not None and vm is None:
                    # k 已知 ⇒ 已知项移入 m 行右端（+g/h·a_km·val_k）
                    rows.append(m); cols.append(m); vals.append(g / h * cm_self)
                    b[m] += -(g / h * cm_other) * vk
                elif vk is None and vm is not None:
                    # m 已知 ⇒ 已知项移入 k 行右端（+g/h·a_mk·val_m）
                    rows.append(k); cols.append(k); vals.append(g / h * ck_self)
                    b[k] += -(g / h * ck_other) * vm
                # 两端皆 Dirichlet：各自行恒等，无未知耦合
    M = sp.csr_matrix((vals, (rows, cols)), shape=(n, n)).tolil()
    for j in range(ny):
        for i, val in ((0, bc_left), (nx - 1, bc_right)):
            k = _idx(i, j, ny)
            M.rows[k] = [k]; M.data[k] = [1.0]; b[k] = val
    return spla.spsolve(M.tocsc(), b)


def _solve_poisson_drift_diffusion(phi_n_flat: np.ndarray, phi_p_flat: np.ndarray,
                                   ND_flat: np.ndarray, NA_flat: np.ndarray,
                                   nx: int, ny: int, dx: float, dy: float,
                                   phi_left: float, phi_right: float,
                                   eps: float = EPS_SI, n_i: float = N_I,
                                   v_t: float = V_T, max_iter: int = 400,
                                   resid_tol: float = 1e-10, step_cap: float = 0.05) -> np.ndarray:
    """非线性泊松（Gummel 内环）：∇²φ = −(q/ε)(n_i·exp((φ−φ_n)/V_T)
    − n_i·exp((φ_p−φ)/V_T) + N_D − N_A)。φ_n/φ_p 固定（来自连续性求解），
    n/p 随 φ 指数局部化 ⇒ 净电荷集中在耗尽区，解稳定（与平衡 Newton 同结构，
    且 V=0 ↘ φ_n=φ_p=0 即退化为平衡泊松，已验证收敛）。"""
    phi = np.linspace(phi_left, phi_right, nx)[:, None] * np.ones((1, ny))
    phi = phi.flatten()
    L = _build_laplacian(nx, ny, dx, dy)
    converged = False
    for _ in range(max_iter):
        n = n_i * np.exp((phi - phi_n_flat) / v_t)
        p = n_i * np.exp((phi_p_flat - phi) / v_t)
        rho = (Q_E / eps) * (p - n + ND_flat - NA_flat)
        r = L.dot(phi) + rho
        # J = L − diag((Q_E/ε)(n+p)/V_T)，因 dρ/dφ = −(Q_E/ε)(n+p)/V_T
        J = L - sp.diags((Q_E / eps) * (n + p) / v_t)
        A = J.tolil()
        b = -r
        for j in range(ny):
            for i in (0, nx - 1):
                k = _idx(i, j, ny)
                A.rows[k] = [k]; A.data[k] = [1.0]; b[k] = 0.0
        delta = spla.spsolve(A.tocsc(), b)
        delta = np.clip(delta, -step_cap, step_cap)
        phi_new = phi + delta
        for j in range(ny):
            phi_new[_idx(0, j, ny)] = phi_left
            phi_new[_idx(nx - 1, j, ny)] = phi_right
        if np.max(np.abs(phi_new - phi)) < resid_tol:
            phi = phi_new
            converged = True
            break
        phi = phi_new
    return phi


def _terminal_current_sg(flag: str, phi_flat: np.ndarray, carrier_flat: np.ndarray,
                         nx: int, ny: int, dx: float, dy: float) -> float:
    """SG 守恒电流跨接触平面（x=nx-1.5 边，即 (nx-2,j)-(nx-1,j)）沿 y 积分。

    ∇·J=0 ⇒ 电流全 x 守恒，取接触前最后一条内边积分即终端电流（避免 np.gradient
    数值噪声）。形式 1 同 _solve_continuity_sg：电子 J=(g/dx)(n_k·B_km − n_m·B_mk)，
    空穴 J=(g/dx)(p_m·B_km − p_k·B_mk)，B_km=B(Δφ_km/V_T)。返回 I (A)。
    """
    eta = phi_flat / V_T
    mu = MU_N if flag == "n" else MU_P
    g = Q_E * mu * V_T
    i_edge = nx - 2
    tot = 0.0
    for j in range(ny):
        k = _idx(i_edge, j, ny)
        m = _idx(i_edge + 1, j, ny)
        a_km = _bernoulli(eta[k] - eta[m])   # B(Δφ_km/V_T)
        a_mk = _bernoulli(eta[m] - eta[k])   # B(Δφ_mk/V_T)
        if flag == "n":
            Jkm = (g / dx) * (carrier_flat[k] * a_km - carrier_flat[m] * a_mk)
        else:
            Jkm = (g / dx) * (carrier_flat[m] * a_km - carrier_flat[k] * a_mk)
        tot += Jkm * dy
    return float(tot)


def solve_pn_junction_2d_bias(V: float, N_A: float = N_A_DEFAULT, N_D: float = N_D_DEFAULT,
                              Lx: float = LX_DEFAULT, Ly: float = LY_DEFAULT,
                              nx: int = 50, ny: int = 50, x0: float | None = None,
                              eps: float = EPS_SI, n_i: float = N_I, v_t: float = V_T,
                              max_outer: int = 80, damp: float = 0.6,
                              resid_tol: float = 1e-7) -> dict:
    """2D 偏压下漂移-扩散稳态（Gummel 迭代）— 输运候选。

    解耦策略（标准 Gummel）：每轮固定 φ 解载流子连续性（SG 离散），由解出的
    n/p 反推准费米势 φ_n/φ_p，再解**非线性泊松**（电荷随 φ 指数局部化，避免
    线性泊松把铺展电荷放大发散——本项目关键坑），阻尼松弛至自洽。
    BC（低注入理想二极管律）：接触静电势偏压落 n 接触 φ_right=φ_n_eq+V；
    接触载流子密度少数注入 (n_i²/N_A)·exp(V/V_T)、多数钉 bulk（N_D/N_A）。
    I = n 接触处 J_n,x 沿 y 积分；golden = 理想二极管律 I_s·(exp(V/V_T)−1)。
    🔴 红线：纯数值输运，输出 is_oracle=False（仅候选，golden=理想二极管律）。
    """
    if x0 is None:
        x0 = Lx * X0_FRAC
    x = np.linspace(0.0, Lx, nx)
    y = np.linspace(0.0, Ly, ny)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    dx = x[1] - x[0]
    dy = y[1] - y[0]
    NA, ND = doping_profile_2d(xx, yy, N_A, N_D, x0)
    phi_p_eq = -v_t * math.log(N_A / n_i)
    phi_n_eq = v_t * math.log(N_D / n_i)
    # 接触静电势：偏压落 n 接触（φ_right = φ_n_eq + V；φ_left = φ_p_eq 保持）
    phi_left = phi_p_eq
    phi_right = phi_n_eq + V
    # 接触载流子密度（低注入理想二极管律）：少数载流子平衡值 n_i²/N_A（p 侧电子）/
    # n_i²/N_D（n 侧空穴），偏压注入 ×exp(V/V_T)；多数载流子钉 bulk（N_D/N_A）。
    n_min = n_i * n_i / N_A   # 平衡少数电子 @ p 接触
    p_min = n_i * n_i / N_D   # 平衡少数空穴 @ n 接触
    n_left = n_min * math.exp(V / v_t)   # 注入少数电子 @ p 接触
    p_right = p_min * math.exp(V / v_t)  # 注入少数空穴 @ n 接触
    n_right = N_D                       # 多数电子 @ n 接触（钉 bulk）
    p_left = N_A                        # 多数空穴 @ p 接触（钉 bulk）

    # 初值（平衡剖面对，偏压端含 V）
    phi = np.linspace(phi_p_eq, phi_n_eq + V, nx)[:, None] * np.ones((1, ny))
    phi = phi.flatten()
    n = np.linspace(n_left, n_right, nx)[:, None] * np.ones((1, ny))
    n = n.flatten()
    p = np.linspace(p_left, p_right, nx)[:, None] * np.ones((1, ny))
    p = p.flatten()
    L = _build_laplacian(nx, ny, dx, dy)

    converged = False
    for _ in range(max_outer):
        # 由当前 n/p + φ 反推准费米势（有界），供非线性泊松（电荷随 φ 指数
        # 局部化，避免线性泊松把铺展电荷放大导致发散——本项目关键坑）
        phi_n = phi - v_t * np.log(np.maximum(n, 1e-40) / n_i)
        phi_p = phi + v_t * np.log(np.maximum(p, 1e-40) / n_i)
        # 先解非线性泊松得新 φ（φ_n/φ_p 固定）
        phi_new = _solve_poisson_drift_diffusion(
            phi_n, phi_p, ND.flatten(), NA.flatten(), nx, ny, dx, dy,
            phi_left, phi_right, eps, n_i, v_t)
        diff = np.max(np.abs(phi_new - phi))
        phi = phi + damp * (phi_new - phi)
        # 再用更新后的 φ 解载流子连续性（SG 离散，无条件稳定）——关键：最终 n/p
        # 须与最终 φ 自洽，否则 ∇·J 不守恒、终端 I 含寄生偏移（本项目早期坑）
        n = _solve_continuity_sg("n", phi, nx, ny, dx, dy, n_left, n_right)
        p = _solve_continuity_sg("p", phi, nx, ny, dx, dy, p_left, p_right)
        if diff < resid_tol:
            converged = True
            break
    # 收敛保护：用最终 φ 再解一次连续性，确保返回 n/p 与 φ 严格自洽（电流守恒）
    n = _solve_continuity_sg("n", phi, nx, ny, dx, dy, n_left, n_right)
    p = _solve_continuity_sg("p", phi, nx, ny, dx, dy, p_left, p_right)

    n = n.reshape(nx, ny)
    p = p.reshape(nx, ny)
    # 终端电流：SG 守恒电流跨接触平面（x=nx-1.5 边）沿 y 积分，电子+空穴
    I = _terminal_current_sg("n", phi, n.flatten(), nx, ny, dx, dy) \
        + _terminal_current_sg("p", phi, p.flatten(), nx, ny, dx, dy)
    gold = sze_pn_junction_2d_closed_form(N_A, N_D, Lx, Ly, x0, eps, n_i, v_t)
    return {
        "n": n, "p": p, "phi": phi.reshape(nx, ny), "I": I,
        "I_s_short_closed": gold["I_s_short"], "I_s_long_closed": gold["I_s"],
        "V": V, "converged": converged,
        "provenance": "self_authored_t1_candidate", "is_oracle": False,
    }


def guard_t1_not_oracle(solution: dict, force_oracle: bool = False) -> bool:
    """🔴 T1 输出不作 ORACLE 反向测试守卫（同 W2 语义）。"""
    if force_oracle:
        raise RuntimeError(
            "T1 输出禁止作为 ORACLE：数值 n/p/φ/I(V) 仅作候选，"
            "死标量判决须由物理定律锚/文献/foundry 实测定。")
    if solution.get("is_oracle", False):
        raise RuntimeError("T1 解被错误标记为 ORACLE（is_oracle=True）")
    return True


if __name__ == "__main__":
    gold = sze_pn_junction_2d_closed_form()
    print("=== Sze 闭式 golden ===")
    print(f"  V_bi={gold['V_bi']:.4f} V  W={gold['W']*1e9:.3f} nm  "
          f"x_n={gold['x_n']*1e9:.3f} nm  E_max={gold['E_max']/1e5:.3f} kV/cm")
    print("=== 2D 平衡 cand（网格收敛） ===")
    print(f"  {'nx':>4} {'E_max(kV/cm)':>14} {'|dE|/E':>9} {'W(nm)':>9} "
          f"{'|dW|/W':>9} {'Q_dep/Qsze':>11}")
    prev = None
    for ng in (40, 60, 80, 120):
        sol = solve_pn_junction_2d_equilibrium(nx=ng, ny=ng)
        eE = abs(sol["E_max"] - gold["E_max"]) / gold["E_max"]
        eW = abs(sol["W"] - gold["W"]) / gold["W"]
        qratio = sol["Q_dep_num"] / gold["Q_dep_sze"]
        mono = "" if prev is None else ("ok" if eE < prev else "DIV!")
        print(f"  {ng:>4} {sol['E_max']/1e5:>14.3f} {eE:>9.3%} "
              f"{sol['W']*1e9:>9.2f} {eW:>9.3%} {qratio:>11.4f} {mono}")
        prev = eE
    # 偏压 I-V
    print("=== 2D 偏压 I(V) vs 理想二极管律 ===")
    print(f"  {'V(V)':>6} {'I(A)':>14} {'I_s*(exp-1)':>14} {'ln|I|':>9}")
    for v in (0.2, 0.3, 0.4, 0.5):
        s = solve_pn_junction_2d_bias(v)
        Ith = gold["I_s"] * (math.exp(v / v_t) - 1.0)
        print(f"  {v:>6.2f} {s['I']:>14.3e} {Ith:>14.3e} {math.log(abs(s['I'])):>9.3f}")
    guard_t1_not_oracle(sol)
    print("=== T1 不作 ORACLE 守卫：正常通过 ===")
