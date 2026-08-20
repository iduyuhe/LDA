"""LDA L2 · 示例 PDK（可制造工艺窗口）。

示例数据来源：公开文献对主流硅光代工（NOEIC / CUMEC / SITRI 等同级 180nm
SOI 工艺）的典型参数近似，仅用于演示"PDK 驱动逆设计"链路，不代表任何
晶圆厂的真实 NDA-PDK。真实对接需与各 foundry 商务签约——那正是主权策略
B 级的"对接点"，而 Registry 本体始终自主。

固定参数名与 bounds 与 lda_harness/benchmarks.py 的 BENCHMARK_DEFS
严格对齐（DesignAgent._evaluate 会把 fixed_params 过滤注入到各题接受的键）。
"""
from __future__ import annotations

from .pdk import PDK, DeviceTemplate, PDKRegistry


def _noeic_soi_180nm() -> PDK:
    pdk = PDK(
        foundry="NOEIC(演示近似)",
        node="SOI 180nm",
        wavelength_band="C-band 1.55um",
        n_si=3.48,
        n_clad=1.44,
        process_notes="220nm 顶硅 / 2um BOX；波导宽度窗口 0.4–0.6um；"
                      "最小弯曲半径约 5um（弯曲损耗可控）。本参数为公开近似，"
                      "非真实 NDA-PDK，仅用于驱动链路演示。",
        design_rules={"min_width_um": 0.40, "min_space_um": 0.20,
                      "min_bend_R_um": 5.0, "max_split_angle_deg": 30.0},
    )
    # 模板1：环形谐振器 FSR 逆设计（B4，单规格）
    pdk.add_template(DeviceTemplate(
        name="环形谐振器 FSR",
        device_type="ring_resonator",
        bids=["B4"],
        objective_bid="B4",
        target_metric="FSR_nm",
        target=9.15,
        target_tol=0.02,
        tunable="R",
        bounds=(5.0, 40.0),       # 工艺允许半径窗口（弯曲损耗可控）
        fixed_params={"wavelength": 1.55, "n_g": 4.2},
        decreasing=True,
        note="FSR=λ²/(n_g·2πR)，调 R 命中目标 FSR；同步验证求解器正确性。",
    ))
    # 模板2：环形谐振器 FSR + 波导 n_eff 双规格（B4+B2）
    pdk.add_template(DeviceTemplate(
        name="环形谐振器 FSR+波导",
        device_type="ring_resonator",
        bids=["B4", "B2"],
        objective_bid="B4",
        target_metric="FSR_nm",
        target=9.15,
        target_tol=0.02,
        tunable="R",
        bounds=(5.0, 40.0),
        fixed_params={"wavelength": 1.55, "n_g": 4.2,
                      "w_core": 0.45, "h_core": 0.22,
                      "n_si": 3.48, "n_clad": 1.44, "pol": "TE"},
        decreasing=True,
        note="双规格：FSR 命中目标，且波导 n_eff 须过物理定律验证；"
             "若 solver=l3_ai，B2 内核缺陷会被法官抓出（双判据分离）。",
    ))
    # 模板3：波导宽度逆设计 n_eff（B2，展示 PDK 工艺边界）
    pdk.add_template(DeviceTemplate(
        name="波导宽度→n_eff",
        device_type="waveguide",
        bids=["B2"],
        objective_bid="B2",
        target_metric="n_eff",
        target=2.62,
        target_tol=0.02,
        tunable="w_core",
        bounds=(0.40, 0.60),       # 工艺宽度窗口
        fixed_params={"h_core": 0.22, "n_si": 3.48,
                      "n_clad": 1.44, "wl": 1.55, "pol": "TE"},
        decreasing=False,           # n_eff 随 w_core 增大而增大（实测单调）
        note="在工艺宽度窗口内反推波导宽度，使 n_eff≈目标；"
             "展示 PDK 提供的真实工艺边界约束逆设计。",
    ))
    # 模板4：环形谐振器双参数逆设计（B4 FSR + B2 n_eff 同时达标）
    pdk.add_template(DeviceTemplate(
        name="环形双参数逆设计(B4+B2)",
        device_type="ring_resonator",
        bids=["B4", "B2"],
        objective_bid="B4",
        target_metric="FSR_nm",
        target=9.15,
        target_tol=0.30,                 # 跟随 B4 真实公差
        tunables={"R": (5.0, 40.0), "w_core": (0.40, 0.60)},
        fixed_params={"wavelength": 1.55, "n_g": 4.2,
                      "h_core": 0.22, "n_si": 3.48,
                      "n_clad": 1.44, "pol": "TE"},
        decreasing=True,                 # 对 B4 FSR 单调（NM 优化不依赖单调性）
        constraint_bids=["B2"],          # 波导 n_eff 须过物理定律验证
        note="N 维逆设计：同时调 R(命中 FSR) 与 w_core(命中 n_eff)，"
             "B2 为硬约束——agent 在工艺窗口内联合反推两个几何量；"
             "若 solver=l3_ai，B2 内核缺陷会被法官抓出（双判据分离）。",
    ))
    # 模板5：环形谐振器双目标加权逆设计（B4 FSR + B2 n_eff 同时达标）
    pdk.add_template(DeviceTemplate(
        name="环形双目标加权(B4+B2)",
        device_type="ring_resonator",
        bids=["B4", "B2"],
        objective_bid="B4",
        target_metric="FSR_nm",
        target=9.15,
        target_tol=0.30,
        objective=[
            {"bid": "B4", "weight": 1.0, "target": 9.15, "tol": 0.30},
            {"bid": "B2", "weight": 1.0, "target": 2.62, "tol": 0.05},
        ],
        tunables={"R": (5.0, 40.0), "w_core": (0.40, 0.60)},
        fixed_params={"wavelength": 1.55, "n_g": 4.2,
                      "h_core": 0.22, "n_si": 3.48,
                      "n_clad": 1.44, "pol": "TE"},
        decreasing=True,
        note="加权多目标逆设计：FSR 与 n_eff 同为软目标（无硬约束），agent 最小"
             "化加权误差联合反推 R 与 w_core；展示'多 benchmark 同时达标 + 权重'。"
             "l3_ai 内核缺陷仍会被法官抓出（双判据分离）。",
    ))
    # 模板6：环形谐振器"目标谱形"逆设计（B11，调 R 使透射谱匹配目标谱形）
    pdk.add_template(DeviceTemplate(
        name="环形谱形匹配(B11)",
        device_type="ring_resonator",
        bids=["B11", "B4"],
        objective_bid="B11",
        target_metric="spectrum_match",
        target=0.0,
        target_tol=0.03,
        tunable="R",
        bounds=(5.0, 40.0),
        fixed_params={"wavelength": 1.55, "n_g": 4.2},
        decreasing=True,                # 占位（梯度法不依赖单调性）
        use_gradient=True,             # 有限差分梯度下降（数值伴随）
        constraint_bids=["B4"],        # 谱形匹配须同时过 FSR 物理定律（双判据）
        note="目标谱形逆设计：调 R 使 drop 端口透射谱 FSR 命中目标梳，用有限差分"
             "梯度下降最小谱形 L2 误差；B4 为硬约束——即便谱形误差收敛，FSR 若不过"
             "物理定律法官仍判 FAIL（双判据分离在谱形域同样成立）。",
    ))
    return pdk


def _cumec_soi_180nm() -> PDK:
    """CUMEC SOI 180nm 示例 PDK（公开近似，区别于 NOEIC 的工艺窗口）。

    演示 L2「社区共建 / 多晶圆厂」架构：不同 foundry 的波导宽度窗口、弯曲
    半径、折射率各不相同，agent 逆设计天然落在对应 foundry 的可制造边界内。
    """
    pdk = PDK(
        foundry="CUMEC(演示近似)",
        node="SOI 180nm",
        wavelength_band="C-band 1.55um",
        n_si=3.47,
        n_clad=1.44,
        process_notes="220nm 顶硅 / 2um BOX；波导宽度窗口 0.35–0.65um；"
                      "最小弯曲半径约 4um。公开近似，非真实 NDA-PDK。",
        design_rules={"min_width_um": 0.35, "min_space_um": 0.20,
                      "min_bend_R_um": 4.0, "max_split_angle_deg": 30.0},
    )
    pdk.add_template(DeviceTemplate(
        name="环形谐振器 FSR", device_type="ring_resonator",
        bids=["B4"], objective_bid="B4", target_metric="FSR_nm",
        target=9.15, target_tol=0.02, tunable="R", bounds=(4.0, 50.0),
        fixed_params={"wavelength": 1.55, "n_g": 4.18}, decreasing=True,
        note="CUMEC 工艺窗口下环形 FSR 逆设计（与 NOEIC 窗口不同）。",
    ))
    pdk.add_template(DeviceTemplate(
        name="波导宽度→n_eff", device_type="waveguide",
        bids=["B2"], objective_bid="B2", target_metric="n_eff",
        target=2.60, target_tol=0.02, tunable="w_core", bounds=(0.35, 0.65),
        fixed_params={"h_core": 0.22, "n_si": 3.47, "n_clad": 1.44,
                      "wl": 1.55, "pol": "TE"}, decreasing=False,
        note="CUMEC 工艺窗口内波导宽度逆设计 n_eff。",
    ))
    return pdk


def _sitri_soi_180nm() -> PDK:
    """SITRI SOI 180nm 示例 PDK（公开近似，区别于 NOEIC/CUMEC 的工艺窗口）。"""
    pdk = PDK(
        foundry="SITRI(演示近似)",
        node="SOI 180nm",
        wavelength_band="C-band 1.55um",
        n_si=3.48,
        n_clad=1.44,
        process_notes="210nm 顶硅 / 2um BOX；波导宽度窗口 0.45–0.75um；"
                      "最小弯曲半径约 6um。公开近似，非真实 NDA-PDK。",
        design_rules={"min_width_um": 0.45, "min_space_um": 0.25,
                      "min_bend_R_um": 6.0, "max_split_angle_deg": 30.0},
    )
    pdk.add_template(DeviceTemplate(
        name="环形谐振器 FSR", device_type="ring_resonator",
        bids=["B4"], objective_bid="B4", target_metric="FSR_nm",
        target=9.15, target_tol=0.02, tunable="R", bounds=(6.0, 60.0),
        fixed_params={"wavelength": 1.55, "n_g": 4.2}, decreasing=True,
        note="SITRI 工艺窗口下环形 FSR 逆设计（与 NOEIC/CUMEC 窗口不同）。",
    ))
    pdk.add_template(DeviceTemplate(
        name="波导宽度→n_eff", device_type="waveguide",
        bids=["B2"], objective_bid="B2", target_metric="n_eff",
        target=2.58, target_tol=0.02, tunable="w_core", bounds=(0.45, 0.75),
        fixed_params={"h_core": 0.21, "n_si": 3.48, "n_clad": 1.44,
                      "wl": 1.55, "pol": "TE"}, decreasing=False,
        note="SITRI 工艺窗口内波导宽度逆设计 n_eff。",
    ))
    return pdk


def _quantum_al_fixed_approx() -> PDK:
    """量子 foundry A：固定频率 transmon（公开典型 Al/AlOx 参数近似）。

    量子侧黄金参考为 ①类确定性物理锚：B9 transmon 频率（Koch2007 解析）、
    B10 门保真度（退相干极限解析）。真实 EPR 哈密顿量对角化(pyEPR/Ansys)属
    A 级美系商业/强依赖，按主权策略只作外部 ORACLE，核心永不 import。

    本厂工艺窗口：氧化层较厚 → 充电能 E_C≈0.30GHz（典型固定频率 transmon）。
    """
    pdk = PDK(
        foundry="量子A(演示近似)",
        node="Al/AlOx 固定频率 transmon",
        wavelength_band="微波 5–7 GHz",
        n_si=0.0,                       # 量子不涉及光学折射率，占位
        n_clad=0.0,
        quantum_window={"ec_default": 0.30, "ec_min": 0.20, "ec_max": 0.45},
        process_notes="固定频率 transmon（Al/AlOx 结）；充电能由氧化层厚度决定，"
                      "本厂典型 E_C≈0.30GHz。E_J/E_C 为约瑟夫森/充电能（GHz）。"
                      "本参数为公开典型近似，非真实代工 NDA-PDK。",
    )
    # Q1：transmon 频率逆设计（B9，调 E_J 命中 f01）
    pdk.add_template(DeviceTemplate(
        name="transmon 频率逆设计(B9)",
        device_type="transmon",
        bids=["B9"],
        objective_bid="B9",
        target_metric="f01_GHz",
        target=6.63,
        target_tol=0.05,
        tunable="E_J",
        bounds=(5.0, 40.0),
        fixed_params={"E_C": 0.30},
        decreasing=False,               # f01 随 E_J 增大而增大
        note="调约瑟夫森能 E_J 命中 f01≈目标（f01=√(8·E_J·E_C)−E_C）；"
             "若 solver=l3_ai，B9 内核漏 sqrt 缺陷使其无法收敛（量子侧双判据）。",
    ))
    # Q2：量子门保真度逆设计（B10 目标）+ transmon 约束（B9）
    pdk.add_template(DeviceTemplate(
        name="量子门保真度+transmon约束(B10+B9)",
        device_type="gate_fidelity",
        bids=["B10", "B9"],
        objective_bid="B10",
        target_metric="F_gate",
        target=0.99,
        target_tol=0.01,
        tunable="t_gate",
        bounds=(0.05, 1.0),
        fixed_params={"T1": 80.0, "T2": 60.0, "E_J": 20.0, "E_C": 0.30},
        decreasing=True,                # F 随 t_gate 增大而减小
        constraint_bids=["B9"],         # transmon 频率须过物理定律验证
        note="调门时长 t_gate 命中保真度 0.99（F=exp(−t_gate·(1/T1+1/2T2))），"
             "且 transmon 频率 B9 须过验证；l3_ai 的 B9 缺陷使约束失败、双判据分离。",
    ))
    return pdk


def _quantum_b_tunable_approx() -> PDK:
    """量子 foundry B：可调耦合 transmon（更薄氧化层 → 更高 E_C≈0.45GHz）。

    与 foundry A 的唯一差异是量子工艺窗口 ec_default 不同（0.30 vs 0.45）——
    这正是"多晶圆厂共建"在量子域的体现：同一 f01 目标因 E_C 工艺窗口不同，
    收敛到不同的 E_J 落点，证明 IR 经 bridge 真驱动"工艺窗口 → 落点差异"。
    """
    pdk = PDK(
        foundry="量子B(演示近似)",
        node="可调耦合 transmon（薄氧化层）",
        wavelength_band="微波 5–8 GHz",
        n_si=0.0,
        n_clad=0.0,
        quantum_window={"ec_default": 0.45, "ec_min": 0.35, "ec_max": 0.60},
        process_notes="可调耦合 transmon（薄 AlOx 结 → 更高充电能 E_C≈0.45GHz）；"
                      "本厂工艺使 E_C 显著高于 foundry A，相同 f01 目标需更小 E_J。",
    )
    pdk.add_template(DeviceTemplate(
        name="transmon 频率逆设计(B9)",
        device_type="transmon",
        bids=["B9"],
        objective_bid="B9",
        target_metric="f01_GHz",
        target=6.63,
        target_tol=0.05,
        tunable="E_J",
        bounds=(5.0, 40.0),
        fixed_params={"E_C": 0.45},
        decreasing=False,
        note="本厂 E_C=0.45GHz（薄氧化层）；调 E_J 命中 f01；与 foundry A 的"
             "E_C=0.30GHz 形成量子多晶圆厂落点差异。",
    ))
    pdk.add_template(DeviceTemplate(
        name="量子门保真度+transmon约束(B10+B9)",
        device_type="gate_fidelity",
        bids=["B10", "B9"],
        objective_bid="B10",
        target_metric="F_gate",
        target=0.99,
        target_tol=0.01,
        tunable="t_gate",
        bounds=(0.05, 1.0),
        fixed_params={"T1": 80.0, "T2": 60.0, "E_J": 20.0, "E_C": 0.45},
        decreasing=True,
        constraint_bids=["B9"],
        note="调 t_gate 命中保真度 0.99 且 transmon 频率 B9 须过验证。",
    ))
    return pdk


def build_example_registry() -> PDKRegistry:
    """构建一个含示例 PDK 的 Registry（应用启动调用）。

    社区/晶圆厂可在此基础上 register() 自己的 PDK，扩展覆盖更多工艺节点——
    本示例已登记 5 个 foundry（NOEIC / CUMEC / SITRI 光子 + 量子A / 量子B），
    演示 L2「开放 PDK / 多晶圆厂共建」架构。光子工艺窗口由 n_si 决定、量子
    由 quantum_window(E_C 窗口) 决定，同类器件在不同 foundry 收敛到不同落点。
    """
    reg = PDKRegistry()
    reg.register(_noeic_soi_180nm())
    reg.register(_cumec_soi_180nm())
    reg.register(_sitri_soi_180nm())
    reg.register(_quantum_al_fixed_approx())
    reg.register(_quantum_b_tunable_approx())
    return reg
