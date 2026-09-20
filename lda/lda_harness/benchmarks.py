"""LDA 验证 harness · 标准题定义（B1–B4、B8，光子子集第一批）。

对应《LDA 领域文献与工具知识基线》模块4 标准题清单；与 L0 IR
`verification.benchmarks` 字段一一对应（id/metric/target/tol/oracle）。
golden_fn 为确定性物理定律锚；target 默认取 golden 计算值（自洽），
可由 L0 IR 覆盖为设计规格目标。
"""

from .benchmark_defs import BENCHMARK_DEFS
from ._vmm_overrides import _VMM_OVERRIDES

# ===========================================================================
# 验证成熟度模型（VMM, v0.9.62）：maturity_tier / provenance / upgrade_path
# ---------------------------------------------------------------------------
# 详见 docs/verification_maturity_model.md。三字段为**作者声明 + 护栏强制**，
# 使「自证是合法第一阶段」可见、可追溯、可升级，且禁止越级谎报。
# 底线 6 条由 run_maturity_baseline_smoke.py 守护。
# ===========================================================================
# Tier-1（自证）的 provenance 与升级路径显式覆盖；其余按 DEFAULT 推导。


# ===========================================================================
# 🔒 终审分级锁（v0.9.66 · 2026-09-10）
# ---------------------------------------------------------------------------
# 目的：对「反复审议、已多方法终审」的锚打永久分级标志。任何人（含 AI）后续
#       想改其分级，必须先读此处结论，避免重复讨论（B2 已反反复复多轮）。
# 字段：verdict / date / methods / rationale / supersedes / no_revisit
_VMM_FINAL_VERDICT = {
    "B2": {
        "verdict": "LOCKED_STRICT_INDEPENDENT",  # 终审：已升 Tier-3 严格独立
        "date": "2026-09-10",
        "methods": [
            "FV-FDM 全矢量有限差分（纯 numpy/scipy，纯物理选模，n_eff=2.644，Δ=0.0069≤tol0.05）★已注册为 harness 独立候选 b2_fvfdm_neff",
            "PWE 平面波展开（傅里叶基，n_eff=2.614，Δ=0.0369≤tol0.05）—— 独立交叉验证",
            "Marcatili 1969 解析近似（n_eff=2.448，系统性低估 0.20）—— 仅作解析降维偏差方向对照，非 ORACLE",
        ],
        "rationale": ("EIM golden=2.6509 落在两个独立全波方法（FV-FDM 2.644 / PWE 2.614）之间，"
                      "二者均满足判据 C5（方法学独立候选在 tol=0.05 内复现 golden）。"
                      "golden 本身为合理中值，可信。B2 由自证桩升 Tier-3 严格独立。"),
        "supersedes": ("推翻 2026-09-10 早间『半矢量 FDM=2.53 证伪不可升 strict』的误判——"
                       "该实现存在折射率索引错位 bug（收敛到错误模式），非真物理结论，已废弃。"),
        "no_revisit": ("除非 tol 收紧至 <0.04，或出现与之矛盾的权威 ORACLE（MPB/FEM 实测），"
                       "否则本锚分级终审锁定，勿反复审议。"),
    },
}


def _vmm_classify(defn: dict) -> str:
    """与 harness（IndependentCandidateRouter.candidate_class）同构的分类。"""
    if defn.get("candidate_status") == "degraded_ordinal":
        return "degraded"
    if "candidate" in defn:
        return "strict_independent"
    return "self_certified"


def _vmm_provenance(bid: str, defn: dict) -> str:
    if bid in _VMM_OVERRIDES:
        return _VMM_OVERRIDES[bid][0]
    tier = _vmm_classify(defn)
    if tier == "strict_independent":
        return "independent_cross_check"
    if tier == "degraded":
        return "external_empirical"
    # self_certified 默认保守诚实：自写闭式（低置信·待 ORACLE）
    return "self_authored_closed_form"


def _vmm_upgrade_path(bid: str, defn: dict) -> str:
    if bid in _VMM_OVERRIDES:
        return _VMM_OVERRIDES[bid][1]
    tier = _vmm_classify(defn)
    if tier in ("strict_independent", "degraded"):
        return ""
    return "接独立候选 / 外部 ORACLE（按环境可用性做专题攻关）"


for _bid, _def in BENCHMARK_DEFS.items():
    _def.setdefault("maturity_tier", _vmm_classify(_def))
    _def.setdefault("provenance", _vmm_provenance(_bid, _def))
    _def.setdefault("upgrade_path", _vmm_upgrade_path(_bid, _def))


# 对齐顺序（报告展示用）
BENCHMARK_ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10",
                   "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18",
                   "B19", "B20", "B21", "B22", "B23", "B24", "B25",
                   "B26", "B27", "B28", "B29", "B30", "B31", "B32", "B33",
                   "B34", "B36", "B37", "B40", "B41",
                   "B42", "B43", "B44", "B45", "B46", "B47", "B48", "B49", "B50", "B51",
                   "B52", "B53", "B54", "B55", "B56", "B57", "B58", "B59", "B60", "B61", "B62", "B63", "B64",
                   "B65", "B66", "B67", "B68", "B70", "B71", "B73", "B74", "B75", "B76", "B77", "B78", "B79", "B80",
                   "B81", "B82", "B83", "B84", "B85", "B86", "B87", "B88",
                   "B89", "B90", "B91", "B92", "B93", "B94", "B95", "B96",
                   "B97", "B98", "B99", "B100", "B101", "B102", "B103", "B104",
                   "B105", "B106", "B107", "B108", "B109", "B110",
                   "B111", "B112", "B113", "B114", "B115", "B116", "B117",
                   "B118", "B119", "B120",
                   "B121", "B122", "B123", "B124", "B125", "B126", "B127", "B128",
                   "B129", "B130", "B131", "B132", "B133", "B134", "B135", "B136",
                   "B137", "B138", "B139", "B140", "B141", "B142", "B143", "B144",
                   "B145", "B146", "B147", "B148", "B149", "B150", "B151", "B152",
                   "B153", "B154", "B155", "B156", "B157", "B158", "B159", "B160",
                   "B161", "B162", "B163", "B164", "B165", "B166", "B167", "B168",
                   "B169", "B170", "B171", "B172", "B173", "B174", "B175", "B176",
                   "B177", "B178", "B179", "B180", "B181", "B182", "B183", "B184",
                   # Batch B-11（v0.9.91 · 腿① 续加锚 · 量子统计积分与 ζ/Kepler 中心力轨道/辐射传热角系数/Voigt 谱线）
                   "B185", "B186", "B187", "B188", "B189", "B190", "B191", "B192",
                   "B193", "B194", "B195", "B196", "B197", "B198", "B199", "B200",
                   # Batch B-12（v0.9.92 · 腿① 续加锚 · 正交多项式高斯求积/连分数有理逼近/Durand–Kerner 求根/₂F₁ 超几何）
                   "B201", "B202", "B203", "B204", "B205", "B206", "B207", "B208",
                   "B209", "B210", "B211", "B212", "B213", "B214", "B215", "B216",
                   # Batch B-13（v0.9.93 · 腿① 续加锚 · 分数阶 GL 微分/矩阵指数 scaling–squaring/变分极值梯度下降/第二类 Volterra 积分方程）
                   "B217", "B218", "B219", "B220", "B221", "B222", "B223", "B224",
                   "B225", "B226", "B227", "B228", "B229", "B230", "B231", "B232",
                   # Batch B-14（v0.9.94 · 腿① 续加锚 · 定常对流–扩散中心差分/第二类 Fredholm 可分核 Nyström/自然三次样条逼近/非线性两点边值打靶法）
                   "B233", "B234", "B235", "B236", "B237", "B238", "B239", "B240",
                   "B241", "B242", "B243", "B244", "B245", "B246", "B247", "B248",
                   # Batch B-15（v0.9.95 · 腿① 续加锚 · 延迟泛函微分方程分步法/双调和薄板 13 点差分/一维输运半拉格朗日特征线/聚焦 NLSE 孤子分裂步 Fourier）
                   "B249", "B250", "B251", "B252", "B253", "B254", "B255", "B256",
                   "B257", "B258", "B259", "B260", "B261", "B262", "B263", "B264",
                   # Batch B-16（v0.9.96 · 腿① 续加锚 · Burgers tanh 行波 RK4+中心差分/广义指数积分 E_n 复合 Simpson/Haar 小波多分辨投影逐层低通）
                   "B265", "B266", "B267", "B268", "B269", "B270",
                   "B271", "B272", "B273", "B274", "B275",
                   "B276", "B277", "B278", "B279", "B280",
                   # Batch B-17（v0.9.97 · 腿① 续加锚 · 线性受迫 ODE 指数时间差分 ETD2/Zernike 圆域 RMS 极坐标中点求积/Duffing 硬化振子四阶组合辛积分）
                   "B281", "B282", "B283", "B284", "B285", "B286",
                   "B287", "B288", "B289", "B290", "B291",
                   "B292", "B293", "B294", "B295", "B296",
                   # Batch B-18（v0.9.98 · 腿① 续加锚 · 振荡积分 Filon 型求积/GL 隐式 RK4/Adams–Bashforth 4 阶多步）
                   "B297", "B298", "B299", "B300", "B301", "B302",
                   "B303", "B304", "B305", "B306", "B307",
                   "B308", "B309", "B310", "B311", "B312",
                   # Batch B-19（v0.9.99 · 腿① 续加锚 · 广义 Lane–Emden 奇异 IVP Taylor+RK4/二维 Laplace 单层位势 BEM/Eikonal 制造解 FMM）
                   "B313", "B314", "B315", "B316", "B317", "B318",
                   "B319", "B320", "B321", "B322", "B323",
                   "B324", "B325", "B326", "B327", "B328",
                   # Batch B-20（v0.9.100 · 腿① 续加锚 · 修正 Bessel I_nu ODE RK4/球谐 Y_l^m 自投影梯形积分/一维 RBF 插值）
                   "B329", "B330", "B331", "B332", "B333", "B334",
                   "B335", "B336", "B337", "B338", "B339",
                   "B340", "B341", "B342", "B343", "B344",
                   "B345", "B346", "B347", "B348", "B349", "B350",
                   "B351", "B352", "B353", "B354", "B355", "B356",
                   "B357", "B358", "B359", "B360",
                   "B361", "B362", "B363", "B364", "B365", "B366", "B367", "B368",
                   "B369", "B370", "B371", "B372", "B373",
                   "B374", "B375", "B376", "B377", "B378", "B379", "B380", "B381",
                   "B382", "B383", "B384", "B385", "B386",
                   "B387", "B388", "B389", "B390", "B391", "B392", "B393", "B394",
                   "B395", "B396", "B397", "B398", "B399",
                   "B400", "B401", "B402", "B403", "B404", "B405", "B406", "B407",
                   "B408", "B409", "B410", "B411", "B412",
                   "B413", "B414", "B415", "B416", "B417", "B418", "B419", "B420",
                   "B421", "B422", "B423", "B424", "B425",  # Batch B-26（v0.9.108 · 腿① 扩基加锚 · 单界面 Fresnel/Snell 光学族）
                   "B426", "B427", "B428", "B429", "B430", "B431", "B432", "B433",
                   "B434", "B435", "B436", "B437", "B438",  # Batch B-27（v0.9.109 · 腿① 扩基加锚 · 色散与群速度族：解析闭式 golden × 中心差分数值微分候选）
                   "B439", "B440", "B441", "B442", "B443", "B444", "B445",
                   "B446", "B447", "B448", "B449", "B450", "B451",  # Batch B-28（v0.9.110 · 腿① 扩基加锚 · 不完全 Beta / 积分正余弦函数族：精确特殊函数 golden × 复合 Simpson·RK4 候选）
                   "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10",
                   "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
                   "S9", "S10", "S11", "S12", "S13"]  # S 系统锚（Phase 0-4；S9=LVS/S10=多层/S11=规模/S12=阵列分布/S13=设计良率）


def register_benchmark(def_dict: dict) -> str:
    """运行时注册一道新 benchmark（社区提案评审→落地用）。

    def_dict 与 BENCHMARK_DEFS 条目同构（title/metric/oracle/tol/default_params/
    golden_fn/note）。golden_fn 必须已是确定性物理定律实现（经具名人工评审的
    ORACLE）。注册后 build_harness_specs 自动纳入统一回归（零接线）。
    """
    bid = str(def_dict.get("bid", "")).strip()
    if not bid:
        raise ValueError("register_benchmark: 缺少 bid")
    if not callable(def_dict.get("golden_fn")):
        raise ValueError(f"register_benchmark: {bid} 的 golden_fn 不可调用")
    item = {k: v for k, v in def_dict.items() if k != "bid"}
    BENCHMARK_DEFS[bid] = item
    if bid not in BENCHMARK_ORDER:
        BENCHMARK_ORDER.append(bid)
    return bid
