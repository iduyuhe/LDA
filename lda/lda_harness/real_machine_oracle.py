"""LDA 真机 ORACLE 接入契约骨架（C1–C5，2026-09-11）。

红线边界（杜先生 2026-09-10~11 拍板 §八 Foundry TCAD / §九 电域求解器）：
  - 真机 ORACLE = T2 工艺真值 / 流片实测 / foundry 产线实测，属**永久锁死档**。
  - 本模块**只预留契约与守卫，零真实数据**。
  - 启动条件（路径 B）：资金到位 + foundry 合作 / MPW 流片排期 + 成熟节点
    用途声明通过 EAR 744.23 自审（由杜先生在现实世界推动）。
  - **系统研发不受限 / 验证受限**（杜先生 2026-09-11 07:09 确认）：
      * 本模块所有系统能力（RealMachineOracleRegistry / FoundryPDKClient stub /
        REAL_MACHINE_ANCHOR_BINDING / provenance 校验 / G1–G6 守卫）现在即
        研发完整，仅输入为合成/占位数据，不接真实 foundry / 流片真值。
      * 真机 ORACLE 的**真值标定留空**，等现实条件（路径 B）满足再填；
        当前 REAL_MACHINE_ORACLE 为空（is_empty == True）。
      * 目的：现实机会到来时系统已齐备，不拖现实操作。

对应文档：docs/LDA_真机ORACLE接入框架预留清单_2026-09-11.md
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from lda_pdk.sovereign_deps import classify_dependency


# --------------------------------------------------------------------------
# C1 · 数据格式契约：真机实测数据的标准 schema
# --------------------------------------------------------------------------
class MeasurementQuantity(str, Enum):
    """真机实测量枚举（C1）。"""

    CARRIER_DENSITY = "carrier_density"        # N(x) 载流子浓度分布
    DETECTOR_BANDWIDTH = "detector_bandwidth"  # 探测器带宽
    IV_CURVE = "iv_curve"                      # 电流-电压
    CV_CURVE = "cv_curve"                      # 电容-电压
    NEAR_FIELD = "near_field"                  # 近场
    FAR_FIELD = "far_field"                    # 远场
    # 以下为 T2 锁死档占位（增益类维持禁区，仅声明接口不激活）
    L_I_CURVE = "l_i_curve"                    # 激光 L-I（T2 锁死）
    GAIN = "gain"                              # 增益介质（T2 锁死）


class OracleKind(str, Enum):
    """ORACLE 数据**性质**枚举（2026-09-23 · 杜先生裁定 ① 的机器化）。

    判决 ground 的铁律：**只有「实测事实」可作 golden**。仿真 / 计算值是
    「另一套计算意见」，不是事实（`docs/lda_empirical_source_boundary_2026-09-01.md`
    §一 排除项 + §四·补 坑 1）。本枚举把这条判据从「纪律」下沉为「可判的枚举」。
    """

    FOUNDRY_MEASURED = "foundry_measured"                # foundry 产线实测（T2）
    TAPEOUT_MEASURED = "tapeout_measured"                # MPW 流片实测
    LITERATURE_MEASURED = "literature_measured"          # 公开论文实测（须 A 级可溯源）
    COMMERCIAL_SOLVER_FIELD = "commercial_solver_field"  # 商业求解器场级解（**仿真值**）
    SELF_KERNEL_SOLVED = "self_kernel_solved"            # 自研 T1 内核解（**仿真值**）


# 可作 golden（进判决路径）的种类 —— 仅「实测事实」三类。
GOLDEN_ELIGIBLE_KINDS = frozenset({
    OracleKind.FOUNDRY_MEASURED,
    OracleKind.TAPEOUT_MEASURED,
    OracleKind.LITERATURE_MEASURED,
})

# 🔴 不可作 golden 的种类（仿真 / 计算值）—— 补齐即可自动获得守卫。
GOLDEN_INELIGIBLE_KINDS = frozenset({
    OracleKind.COMMERCIAL_SOLVER_FIELD,
    OracleKind.SELF_KERNEL_SOLVED,
})

# 🔴 杜先生 2026-09-23 裁定 ①：「二级 golden」机制**整体禁用**。
#    理由：一旦允许「商业求解器当二级 golden」，可证伪性退化为
#    「另一个黑盒说它对」——判决链上多了一层不可复验的黑盒，红线即被稀释。
SECONDARY_GOLDEN_ALLOWED = False


@dataclass
class RealMachineMeasurement:
    """单条真机实测记录（C1 数据格式契约）。

    零真实数据：本结构仅为 schema；实例由路径 B 启动时从 PDK 接口 / MPW
    回流填入。value 为单点标量，曲线类量（IV/CV/近远场）另存，留 value=None。
    """

    anchor_id: str                  # 对标锚点（如 "B-3", "B-4"）
    quantity: MeasurementQuantity
    value: Optional[float] = None  # 实测标量（单点）；曲线为 None
    unit: str = ""
    error_band: Optional[float] = None  # 实测不确定度
    node_declaration: str = ""     # 成熟节点用途声明（EAR 744.23）
    provenance_ref: str = ""       # 关联 RealMachineProvenance.ref
    # ── 2026-09-23 新增（杜先生裁定 ①②）────────────────────────────────
    kind: OracleKind = OracleKind.FOUNDRY_MEASURED
    # 数据性质；默认取实测（保守前提：进本注册表者本应实测）。
    # 商业求解器 / 自研内核解**必须显式改写本字段**，否则被 ① 守卫拦下。
    honest_tier: str = ""
    # 诚实层级串（裁定 ② 的载体）。凡声称「已经外部 ORACLE 标定」者，
    # **必须**以下列前缀开头，否则 register() 直接 raise：
    #     f"{CALIBRATED_TIER_PREFIX}[window={anchor_id}]"
    # 且该锚点必须存在**已签字**的 SIGNED_CALIBRATION_WINDOWS 且值落在窗内。
    # 空串 = 未标定（诚实默认，锁死档现状）。


# --------------------------------------------------------------------------
# W · 外部 ORACLE 标定窗口契约（2026-09-23 · 杜先生裁定 ②）
# --------------------------------------------------------------------------
CALIBRATED_TIER_PREFIX = "oracle-calibrated"


@dataclass(frozen=True)
class CalibrationWindow:
    """外部 ORACLE 标定窗口（「借真值」的允许区间）。

    🔴 纪律（裁定 ② ）：外部标定是**最后手段**（反偏修复路径 ④），且只在
    **有限窗口内**借真值 —— 窗口外一律视作未标定。窗口必须**人类签字**
    （signer 由杜先生/指定责任方填写；**AI 不得代签**），并带可复验来源。
    """

    anchor_id: str                 # 被标定锚点
    quantity: MeasurementQuantity  # 标定量
    lo: float                      # 窗口下界（含）
    hi: float                      # 窗口上界（含）
    signer: str                    # 签字人（人类责任方 · 非 AI）
    signed_date: str               # ISO 日期
    source_ref: str                # 标定来源（外部 ORACLE 标识 + provenance ref）
    note: str = ""


# 🔴 已签字窗口登记表 —— **当前为空**：外部标定路径 ④ 尚未启用
#    （反偏修复次序 = ② BC → ① SRH → ④ 标定仅作最后手段，见
#     `docs/lda_reverse_bias_limitation.md` §6）。
#    空表 ⇒ 任何声称 honest_tier 已标定的注册**必被 raise**（不假绿）。
SIGNED_CALIBRATION_WINDOWS: Dict[str, CalibrationWindow] = {}


# --------------------------------------------------------------------------
# C5 · 来源 provenance 契约
# --------------------------------------------------------------------------
@dataclass
class RealMachineProvenance:
    """真机 ORACLE 来源溯源（C5）。无 provenance 数据拒入注册表。"""

    ref: str                  # 唯一溯源引用
    tapeout_id: str = ""      # 流片批次（MPW）
    foundry: str = ""         # foundry 名称
    report_ref: str = ""      # 实测报告引用
    date: str = ""            # ISO 日期
    node_declaration: str = ""  # 成熟节点用途声明


# --------------------------------------------------------------------------
# C3 · 锚点对标契约：哪道锚接哪个真机 ORACLE（空值/占位）
# --------------------------------------------------------------------------
# 键=锚点 id；值=预期测量量。B 启动前为空占位（仅声明绑定意图）。
# B-3 载流子动力学 / B-4 探测器带宽真求解：由 T1-B 内核算出，真机 ORACLE 标定。
REAL_MACHINE_ANCHOR_BINDING: Dict[str, MeasurementQuantity] = {
    # "B-3": MeasurementQuantity.CARRIER_DENSITY,
    # "B-4": MeasurementQuantity.DETECTOR_BANDWIDTH,
}


# --------------------------------------------------------------------------
# C2 · 接口消费契约（只读 / 不泄露）
# --------------------------------------------------------------------------
class FoundryPDKClient:
    """消费 Foundry PDK 接口的只读客户端桩（C2，路径 A）。

    🔴 主权纪律：只读拉取、本地脱敏缓存、禁止将 foundry IP 回写训练集 / 外传。
    当前为 stub：未激活，返回占位；路径 A 待 foundry 合作后接真实接口。
    """

    def __init__(self, foundry: str = "", endpoint: str = ""):
        self.foundry = foundry
        self.endpoint = endpoint
        self._read_only = True  # 常量：永远只读

    def fetch_parameter(self, anchor_id: str) -> RealMachineMeasurement:
        """只读拉取某锚点的 PDK 实测参数。stub：未激活。"""
        raise NotImplementedError(
            "FoundryPDKClient 尚未激活（路径 A 待 foundry 合作）。"
            " 现在仅研发框架，不消费真实 PDK 数据。"
        )


# --------------------------------------------------------------------------
# 守卫异常
# --------------------------------------------------------------------------
class OracleGuardError(Exception):
    """真机 ORACLE 守卫违反（G1/C4/C5/G2/W/①）。CI 应据此报红。"""


def guard_golden_eligibility(kind: OracleKind, role: str = "golden") -> bool:
    """① 守卫：**仿真 / 计算值永不作（二级）golden**（2026-09-23 杜先生裁定）。

    - ``kind`` 为仿真类（商业求解器场级解 / 自研内核解）⇒ 必 raise。
    - ``role == "secondary_golden"`` ⇒ 必 raise（该机制**整体禁用**）。
    - 合法（实测 kind 且非二级 golden 角色）⇒ 返回 True。

    反面理由（裁定原文）：一旦允许「商业求解器当二级 golden」，可证伪性就
    退化为「**另一个黑盒说它对**」——判决链上多一层不可复验的黑盒，红线被稀释。
    这也与 `docs/lda_empirical_source_boundary_2026-09-01.md` §四·补 坑 1 同构：
    「两道 ground 短路 ⇒ 判决即自证」。
    """
    if role == "secondary_golden" and not SECONDARY_GOLDEN_ALLOWED:
        raise OracleGuardError(
            "① 违反：二级 golden 机制**整体禁用**（杜先生 2026-09-23 裁定）—— "
            "否则可证伪性退化为「另一个黑盒说它对」。"
        )
    if kind in GOLDEN_INELIGIBLE_KINDS:
        raise OracleGuardError(
            "① 违反：%s 属仿真 / 计算值（**非实测事实**），不得作为 %s —— "
            "判决 ground 仅限实测事实（foundry 产线 / 流片 / A 级可溯源公开实测）。"
            % (getattr(kind, "value", kind), role)
        )
    return True


# --------------------------------------------------------------------------
# C4 · 标定方向契约 + G1 ORACLE 守卫：真机 ORACLE 注册表
# --------------------------------------------------------------------------
class RealMachineOracleRegistry:
    """真机 ORACLE 注册表（第三档，当前为空）。

    守卫（G1 + C4 + C5 + G4 + W + ①）：
      - register() 强制要求非空 RealMachineProvenance（C5）。
      - 拒绝任何来自 T1-B 求解输出的注册（标定单向，C4）。
      - 🔴 ①（2026-09-23）：拒绝**仿真 / 计算值**注册（商业求解器场级解 /
        自研内核解）——只有实测事实可作 golden；二级 golden 机制整体禁用。
      - 🔴 ②（2026-09-23）：`honest_tier` 声称已外部标定者，必须落在**已签字**
        标定窗口内（未签字 / 量不符 / 无签字人 / 曲线 / 超窗 ⇒ 均 raise）。
      - 真值只进不出（G4）：本类不提供任何导出 / 外传 API。
    """

    # T1-B 真求解锚：其输出禁止反向注册为真机 ORACLE
    _T1B_OUTPUT_ANCHORS = ("B-3", "B-4")

    def __init__(self):
        self._oracles: Dict[str, RealMachineMeasurement] = {}

    @property
    def is_empty(self) -> bool:
        """当前是否零真值（符合锁死档现状）。"""
        return len(self._oracles) == 0

    def register(self, meas: RealMachineMeasurement,
                 provenance: RealMachineProvenance) -> None:
        if not provenance or not provenance.ref:
            raise OracleGuardError(
                "C5 违反：真机 ORACLE 注册必须带非空 provenance（来源溯源）。"
            )
        if meas.provenance_ref and meas.provenance_ref != provenance.ref:
            raise OracleGuardError("C5 违反：provenance_ref 与 provenance 不一致。")
        # G1 + C4：T1-B 输出禁止反向注册为 ORACLE
        self._assert_not_t1b_output(meas.anchor_id)
        # ①（2026-09-23 裁定）：非实测事实（商业求解器 / 自研内核解）禁作 golden
        guard_golden_eligibility(meas.kind, role="真机 ORACLE golden")
        # ②（2026-09-23 裁定）：声称已外部标定 ⇒ 必须落在**已签字**窗口内
        self._assert_within_signed_window(meas)
        self._oracles[meas.anchor_id] = meas

    def _assert_within_signed_window(self, meas: RealMachineMeasurement) -> None:
        """② 守卫：`honest_tier` 声称已标定者，必须落在已签字标定窗口内。

        未声称（honest_tier 不合前缀）⇒ 直接放行（诚实默认 = 未标定）。
        声称 ⇒ 窗口须存在（W1）· 量一致（W2）· 有人类签字（W3）· 标量可判（W4）
        · 值在窗内（W5，超窗必 raise）。
        """
        if not meas.honest_tier.startswith(CALIBRATED_TIER_PREFIX):
            return
        win = SIGNED_CALIBRATION_WINDOWS.get(meas.anchor_id)
        if win is None:
            raise OracleGuardError(
                "W1 违反：honest_tier 声称「%s」，但 %s 无已签字标定窗口"
                "（外部标定须人类签字；登记表为空 ⇒ 一律视作未标定）。"
                % (meas.honest_tier, meas.anchor_id)
            )
        if win.quantity != meas.quantity:
            raise OracleGuardError(
                "W2 违反：标定窗口量 %s ≠ 注册量 %s。"
                % (win.quantity.value, meas.quantity.value)
            )
        if not (win.signer or "").strip():
            raise OracleGuardError(
                "W3 违反：标定窗口缺人类签字人（AI 不得代签）。"
            )
        if meas.value is None:
            raise OracleGuardError(
                "W4 违反：曲线类量（value=None）不得声称已标定（窗口判据为标量）。"
            )
        if not (win.lo <= meas.value <= win.hi):
            raise OracleGuardError(
                "W5 违反（**超窗**）：%s 值 %s 落在已签字窗口 [%s, %s] 之外 ⇒ "
                "窗口外视作未标定，禁止以「%s」记账。"
                % (meas.anchor_id, meas.value, win.lo, win.hi,
                   CALIBRATED_TIER_PREFIX)
            )

    def _assert_not_t1b_output(self, anchor_id: str) -> None:
        """G1/C4：T1-B 求解输出（载流子 N(x) 等）禁止当真值 ORACLE。"""
        if anchor_id in self._T1B_OUTPUT_ANCHORS:
            raise OracleGuardError(
                f"G1/C4 违反：{anchor_id} 为 T1-B 真求解输出，"
                f"禁止反向注册为真机 ORACLE（标定单向：真机 → 标定 T1-B，反之不可）。"
            )

    def get(self, anchor_id: str) -> Optional[RealMachineMeasurement]:
        """取已注册真值（仅内部标定用，不外传）。"""
        return self._oracles.get(anchor_id)


# 全局单例（空，符合锁死档现状）
REAL_MACHINE_ORACLE = RealMachineOracleRegistry()


# --------------------------------------------------------------------------
# G2 · 主权扫描钩子（T1 内核不得为 A 级）
# --------------------------------------------------------------------------
def assert_t1_kernel_sovereign(dep_name: str = "DEVSIM (TCAD 内核)") -> None:
    """G2 主权扫描：T1 内核（DEVSIM fork / 自研）必须非 A 级（永不借）。

    路径 B 系统研发前提： drift-diffusion 载流子内核只能走 B 级（借今踢后 /
    Apache-2.0 fork 主权副本）或 C 级（自研），禁止借入任何 A 级美系商业工具。
    """
    cls = classify_dependency(dep_name)
    if cls == "A":
        raise OracleGuardError(
            f"G2 违反：{dep_name} 为主权 A 级，禁止借入 T1 内核。"
        )
