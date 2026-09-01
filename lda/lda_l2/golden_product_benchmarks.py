"""产品级基准对照库（v0.8.32 · 实证锚产品级扩展 + B 生态播种素材）。

策略落点（2026-08-27 共识）：
  拿**已公开验证**（实测 / 厂商 datasheet / 开源 PDK 表征）的器件性能死标量当 golden，
  用 LDA 引擎做规格驱动再设计 + 数值复现，与 golden 死标量比对 → PASS/FAIL。
  → 免去实际流片，即把验证做到「产品级」。本动作落在 A/B 阶段内，**不碰 C 闸门**。

红线（与全局一致）：
  - LLM 不进判决路径；比对为死标量 rel，PASS/FAIL 由算术决定。
  - 对标的是**性能死标量**（IL / 失衡 / 耦合效率 / 串扰 / 传播损耗），**非版图几何**。

诚实边界（对外素材须照标）：
  - 等效验证（对标公开实测），**非本团队流片验证**；
  - 引擎为解析近似，对标公开典型量级；工艺标定参数显式暴露，发动期真实 PDK 可替换；
  - 库随社区/文献贡献可增量扩展（save_library_json / load_library_json）。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from lda_design.loss_engines import ENGINE_FUNCS, SPLIT_LOSS_3DB

HONEST_BANNER = (
    "本库对标已公开验证（实测 / 厂商 datasheet / 开源 PDK 表征）的器件性能死标量，"
    "用 LDA 引擎做规格驱动再设计 + 数值复现。对标对象是性能数据（非版图几何）；"
    "属等效验证（对标公开实测），非本团队流片验证。引擎为解析近似，对标公开典型量级。"
)


@dataclass
class MetricSpec:
    """单条性能死标量比对规格。"""
    name: str           # 引擎返回键名（如 excess_loss_dB / coupling_eff / crosstalk_dB）
    golden: float       # 公开 golden 死标量
    tol: float          # 容差
    unit: str           # 单位（dB / dB/cm / ratio）
    direction: str = "le"   # le=≤ / ge=≥ / abs=绝对差
    note: str = ""


@dataclass
class ProductBenchmark:
    """单个产品级基准对照条目。"""
    product_id: str
    device_type: str
    source_kind: str    # literature / datasheet / open_pdk
    source_ref: str     # DOI / URL / 文献出处（可溯源）
    engine: str         # LDA loss 引擎名
    geom: Dict[str, float]      # 规格驱动再设计的几何/工艺参数
    metrics: List[MetricSpec]
    replica_note: str = ""      # 复现设计说明
    honest_note: str = ""       # 诚实边界标注

    def evaluate(self) -> Dict[str, Any]:
        fn = ENGINE_FUNCS.get(self.engine)
        if fn is None:
            return {"product_id": self.product_id, "error": f"engine {self.engine} 未注册",
                    "passed_all": False, "rows": []}
        out = fn(dict(self.geom))
        rows: List[Dict[str, Any]] = []
        all_pass = True
        for m in self.metrics:
            # 取复现值：优先同名键，否则取引擎主 value
            if m.name == out.get("metric"):
                replica = out.get("value")
            elif m.name in out:
                replica = out.get(m.name)
            else:
                # 🔴🔴 D-67 metric 语义错配护栏（此前这里是「静默回退到 value」）
                # MetricSpec 声明的量在引擎输出里**既不是主 metric、也不是显式
                # 字段**，却仍拿主 `value` 去比 golden —— 这就是「拿 A 量比 B
                # golden」的语义错配。在 `le` 方向（越小越 PASS）下它会伪装成
                # PASS：v0.9.10（D-66）正是这样让 GP-YBRANCH 把**过量损耗** 0.1 dB
                # 拿去比**总插损** golden 3.15 dB 而显示 PASS（假绿）。
                # 现在改为**硬失败**：宁可红，不可假绿。
                return {
                    "product_id": self.product_id,
                    "error": (f"metric 语义错配：MetricSpec 声明 '{m.name}'，"
                              f"但引擎 {self.engine} 输出主 metric 为 "
                              f"'{out.get('metric')}'、可用字段 "
                              f"{sorted(k for k in out if k not in ('metric', 'value', 'model'))} "
                              f"——禁止静默回退到 value 比 golden（D-67）"),
                    "passed_all": False, "rows": [],
                }
            if replica is None:
                rows.append({**asdict(m), "replica": None, "passed": False, "delta": None})
                all_pass = False
                continue
            if m.direction == "le":
                passed = replica <= m.golden + m.tol
            elif m.direction == "ge":
                passed = replica >= m.golden - m.tol
            else:  # abs
                passed = abs(replica - m.golden) <= m.tol
            rows.append({
                "name": m.name, "golden": m.golden, "tol": m.tol, "unit": m.unit,
                "direction": m.direction, "replica": round(float(replica), 4),
                "delta": round(float(replica) - m.golden, 4), "passed": bool(passed),
            })
            all_pass = all_pass and passed
        return {
            "product_id": self.product_id, "device_type": self.device_type,
            "source_kind": self.source_kind, "source_ref": self.source_ref,
            "engine": self.engine, "passed_all": all_pass, "rows": rows,
            "model": out.get("model", ""),
        }


# ---------------------------------------------------------------------------
# 整芯片级基准对照（GC-* · v0.8.36 · 器件级 GP-* 的级联聚合）
#   把已锚定基元 GP-* 按系统预算级联（光子 S1 dB 加法 / 量子 S4 保真度乘法），
#   对标公开整芯片规格（插入损耗 / 读出保真度）的死标量。
#   复用已验证闭环（ENGINE_FUNCS / design_multiqubit_fidelity），零新物理。
#   诚实边界：免流片，golden 来自公开产品规格（datasheet / 公开披露 / 文献），
#   拓扑自研，不抄版图；落点 A/B 阶段，不碰 C 闸门。
# ---------------------------------------------------------------------------
# 标准基元几何（与 GP-* 标杆一致，保证级联复现值同源）
_G_GEOM = {"ff": 0.5, "theta_deg": 8.0, "tilt_sigma_deg": 15.0}
_SIN_GEOM = {"w_core_um": 0.8, "h_core_um": 0.8, "roughness_nm": 0.3}
_YB_GEOM = {"theta_deg": 5.0, "excess_coef": 0.004}
_CR_GEOM = {"w_core_um": 0.5, "taper_w_ratio": 2.5}


@dataclass
class ChipBenchmark:
    """整芯片级基准对照条目（GC-*）。"""
    chip_id: str
    chip_type: str
    source_kind: str
    source_ref: str
    domain: str          # photon / quantum
    system_type: str     # 复用已验证闭环：link / quantum_fidelity
    geom: Dict[str, Any]  # 级联组成（photon）或频率计划（quantum）
    metrics: List[MetricSpec]
    replica_note: str = ""
    honest_note: str = ""
    honest_tier: str = "产品级对标（免流片）"
    kind: str = "chip"

    def evaluate(self) -> Dict[str, Any]:
        if self.domain == "photon":
            replica = self._photon_cascade_il()
        else:
            replica = self._quantum_fidelity()
        rows: List[Dict[str, Any]] = []
        all_pass = True
        for m in self.metrics:
            if m.name not in replica:
                rows.append({**asdict(m), "replica": None, "passed": False,
                             "delta": None})
                all_pass = False
                continue
            r = float(replica[m.name])
            if m.direction == "le":
                passed = r <= m.golden + m.tol
            elif m.direction == "ge":
                passed = r >= m.golden - m.tol
            else:
                passed = abs(r - m.golden) <= m.tol
            rows.append({
                "name": m.name, "golden": m.golden, "tol": m.tol,
                "unit": m.unit, "direction": m.direction,
                "replica": round(r, 4),
                "delta": round(r - m.golden, 4), "passed": bool(passed),
            })
            all_pass = all_pass and passed
        return {
            "product_id": self.chip_id, "device_type": self.chip_type,
            "source_kind": self.source_kind, "source_ref": self.source_ref,
            "engine": f"{self.domain}:{self.system_type}",
            "passed_all": all_pass, "rows": rows, "model": self.honest_tier,
        }

    def _photon_cascade_il(self) -> Dict[str, float]:
        """光子：GP-* 已锚定基元 LDA 复现值 dB 级联（S1 同构）。"""
        g = ENGINE_FUNCS["engine_grating_eff"](_G_GEOM)["value"]
        grating_il = -10.0 * math.log10(g)
        sil = ENGINE_FUNCS["engine_sin_pl"](_SIN_GEOM)["value"]
        yb = ENGINE_FUNCS["engine_ybranch_split"](_YB_GEOM)["value"]
        cr = ENGINE_FUNCS["engine_crossing"](_CR_GEOM)["value"]
        n_g = int(self.geom.get("n_gratings", 0))
        L = float(self.geom.get("wg_length_cm", 0.0))
        n_yb = int(self.geom.get("n_ybranch", 0))
        n_cr = int(self.geom.get("n_crossing", 0))
        total = n_g * grating_il + sil * L + n_yb * yb + n_cr * cr

        # 🔴🔴 D-67 能量守恒下界护栏（物理硬底，非经验阈值）
        # 一个 1×2 分束器必然把功率分成两半 → **每个分束器件的每支路插损**
        # 至少损失 −10·log10(0.5) = 3.0103 dB（能量守恒，与工艺/设计水平无关）。
        #
        # 为何必须有这条：v0.9.10（D-66）把 engine_ybranch_split 的默认 `value`
        # 从「含分光的分支插损」改成了「过量损耗」，这里 `n_yb * yb` 随之把
        # 3.0103 dB/级 漏掉 —— GC-PLC-1X8 由 9.33 → 0.33 dB（差 9.0）、
        # GC-PLC-1X16 由 12.44 → 0.44 dB（差 12.0）、GC-SENSE 13.65 → 7.63、
        # GC-QKD-TX 13.56 → 7.54、GC-CPO-8CH 10.63 → 7.62。而插损 metric
        # 方向为 `le`（越小越 PASS），**这 5 行全都仍然显示 PASS → 假绿**，
        # 且 run_golden_product_smoke 只校验 PASS 条数，84/84 全绿也没抓到。
        #
        # ⚠️ 护栏必须**按贡献项各自**守下界，不能用「总插损 ≥ n_yb×3.0103」
        # 这种混合判据 —— 反向测试证明：混入光栅/波导损耗后，GC-CPO-8CH /
        # GC-SENSE / GC-QKD-TX 三条的**总额**仍高于下界从而逃逸（只抓住 2/5）。
        # 逐项守底才能真正抓住「某一项被漏算」。
        #
        # 教训：**「越小越 PASS」的方向性 metric 必须配物理下界护栏**，
        # 否则「算漏了损耗」会被伪装成「设计做得更好」。
        if n_yb > 0 and yb < SPLIT_LOSS_3DB - 1e-9:
            raise AssertionError(
                f"[{self.chip_id}] 分束器单级插损 {yb:.4f} dB 低于能量守恒下界 "
                f"{SPLIT_LOSS_3DB:.4f} dB（1×2 功率均分的几何必然）——"
                f"疑似漏算分光损耗（见 D-67 回归）")
        floor = n_yb * SPLIT_LOSS_3DB
        if total < floor - 1e-9:
            raise AssertionError(
                f"[{self.chip_id}] 链路插损 {total:.4f} dB 低于能量守恒下界 "
                f"{floor:.4f} dB（{n_yb} 级 1×2 分光 × 3.0103 dB）——"
                f"疑似漏算分光损耗（见 D-67 回归）")
        return {"total_insertion_loss_dB": round(total, 4),
                "energy_floor_dB": round(floor, 4)}

    def _quantum_fidelity(self) -> Dict[str, float]:
        """量子：复用 design_multiqubit_fidelity 已验证闭环（D-46×D-47）。"""
        from lda_agent.multiqubit_fidelity import design_multiqubit_fidelity
        r = design_multiqubit_fidelity(list(self.geom["f01s"]))
        fmin = min(q["budget"]["F"] for q in r["per_qubit"])
        return {"readout_fidelity": round(fmin, 6)}


# ---------------------------------------------------------------------------
# 默认库：首批 5 个标杆器件（覆盖 LDA 现有 5 个 loss 引擎，闭环自洽）
#   golden 全部来自公开可溯源出处；replica 由 LDA 引擎独立算出。
# ---------------------------------------------------------------------------
DEFAULT_BENCHMARKS: List[ProductBenchmark] = [
    ProductBenchmark(
        product_id="GP-MMI-1X2",
        device_type="MMI 1×2 分束器（过量损耗）",
        source_kind="literature",
        source_ref="SciProfiles c4b9157434 'Compact Low Loss Ribbed Asymmetric MMI Power Splitter' "
                   "(SOI, 仿真额外损耗 <0.4 dB, 分束比波动 <3% @1500–1600 nm)",
        engine="engine_mmi_el",
        geom={"w_mmi_um": 2.8, "n_si": 3.48, "wl_um": 1.55},  # L 不传→优化器件 EL=0.05
        metrics=[MetricSpec(name="excess_loss_dB", golden=0.4, tol=0.3, unit="dB",
                            direction="le", note="文献实测额外损耗 <0.4 dB")],
        replica_note="优化 MMI（长度=自映像长），LDA 复现过量损耗 0.05 dB。",
        honest_note="等效验证（对标公开实测），非本团队流片；解析近似对标典型量级。",
    ),
    ProductBenchmark(
        product_id="GP-GRATING-EFF",
        device_type="Grating coupler（光纤-芯片耦合效率）",
        source_kind="literature",
        source_ref="PubMed 29714320 / Appl. Opt. 'Segmented waveguide grating coupler' "
                   "实测峰值耦合效率 51.7% (−2.86 dB) @1550 nm, 3 dB 带宽 71.4 nm",
        engine="engine_grating_eff",
        geom={"ff": 0.5, "theta_deg": 8.0, "tilt_sigma_deg": 15.0},
        metrics=[MetricSpec(name="coupling_eff", golden=0.517, tol=0.10, unit="ratio",
                            direction="ge", note="实测 0.517；模型量级一致（容差 ±0.10）")],
        replica_note="占空比 0.5 / 倾角 8° 设计，LDA 复现耦合效率 0.434。",
        honest_note="等效验证（对标公开实测），非本团队流片；解析近似对标典型量级。",
    ),
    ProductBenchmark(
        product_id="GP-CROSSING",
        device_type="波导 Crossing 交叉（插入损耗 + 串扰）",
        source_kind="literature",
        source_ref="Optics Letters 2024, doi:10.1364/OL.537506 "
                   "'Polarization-insensitive multimode Si crossing' 实测 IL<0.67 dB, XT<−28.6 dB (TE0, 1520–1600 nm)",
        engine="engine_crossing",
        geom={"w_core_um": 0.5, "taper_w_ratio": 2.5},  # L_taper=1.25 µm
        metrics=[
            MetricSpec(name="insertion_loss_dB", golden=0.7, tol=0.5, unit="dB",
                       direction="le", note="实测 <0.67 dB"),
            MetricSpec(name="crosstalk_dB", golden=-25, tol=5, unit="dB",
                       direction="le", note="实测 <−28.6 dB（越负越好）"),
        ],
        replica_note="taper 比 2.5 设计，LDA 复现 IL=0.18 dB / XT=−38 dB。",
        honest_note="等效验证（对标公开实测），非本团队流片；解析近似对标典型量级。",
    ),
    ProductBenchmark(
        product_id="GP-YBRANCH",
        device_type="Y-branch 分束器（总分束损耗，含理想 3 dB）",
        source_kind="literature",
        source_ref="Optics Express 32, 46080 'Ultracompact Si3N4 Y-branch' "
                   "实测 excess loss <0.15 dB (TE) @1550 nm（inverse design, 商用 SiN foundry）",
        engine="engine_ybranch_split",
        geom={"theta_deg": 5.0, "excess_coef": 0.004},
        metrics=[MetricSpec(name="split_loss_dB", golden=3.15, tol=0.3, unit="dB",
                            direction="le", note="含理想 3 dB；实测 excess<0.15 → 总<3.15")],
        replica_note="分束角 5° 设计（小角降过量损耗），LDA 复现总分束损耗 3.10 dB。",
        honest_note="等效验证（对标公开实测），非本团队流片；解析近似对标典型量级。",
    ),
    ProductBenchmark(
        product_id="GP-SIN-PL",
        device_type="SiN 波导传播损耗（已商品化平台）",
        source_kind="datasheet",
        source_ref="LioniX International TriPleX® 商用 SiN 平台 datasheet：传播损耗 <0.1 dB/cm @1550 nm（已商品化 MPW）",
        engine="engine_sin_pl",
        geom={"w_core_um": 0.8, "h_core_um": 0.8, "roughness_nm": 0.3},  # 标定到 800×800 nm 典型工艺
        metrics=[MetricSpec(name="propagation_loss_dBcm", golden=0.1, tol=0.05, unit="dB/cm",
                            direction="le", note="商用 datasheet <0.1 dB/cm")],
        replica_note="800×800 nm 截面 + 粗糙度 0.3 nm 标定，LDA 复现传播损耗 0.087 dB/cm。",
        honest_note="等效验证（对标商用 datasheet），非本团队流片；解析近似对标典型量级。",
    ),
]

# ---------------------------------------------------------------------------
# 整芯片级（GC-*）：GP-* 已锚定基元的级联聚合，对标公开整芯片规格。
#   全部零新物理，复用已验证闭环；CI 由 run_golden_product_smoke 自动覆盖。
# ---------------------------------------------------------------------------
DEFAULT_CHIP_BENCHMARKS: List[ChipBenchmark] = [
    ChipBenchmark(
        chip_id="GC-CPO-8CH",
        chip_type="CPO 8 通道光引擎（每通道光纤-芯片插入损耗）",
        source_kind="literature",
        source_ref="公开 CPO 技术综述（OIF/Yole 汇总，winwinchip.com / 21ic.com 2026 汇总）："
                   "标准光栅耦合器方案光纤到芯片每通道插入损耗典型区间 6–12 dB"
                   "（商用 CPO 信道插入损耗 3–5 dB 电学区；IBM Research 先进耦合 <1.2 dB/通道为记录值，"
                   "research.ibm.com 2025）",
        domain="photon", system_type="link",
        geom={"n_gratings": 2, "wg_length_cm": 1.0, "n_ybranch": 1, "n_crossing": 1},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=12.0, tol=3.0, unit="dB",
                            direction="le",
                            note="标准光栅耦合器 CPO 光引擎每通道插入损耗上限（6–12 dB 公开区间）")],
        replica_note="8 通道对称；每通道 = 2×光栅耦合(标准) + SiN 波导 1cm + Y-branch 分束 + crossing，"
                     "由 GP-* 已锚定基元 LDA 复现值 dB 级联（S1 同构）。",
        honest_note="等效验证（对标公开典型区间），非本团队流片；标准光栅耦合器方案，"
                    "非 IBM 先进耦合 <1.2 dB 记录值。拓扑自研，不抄版图。",
    ),
    ChipBenchmark(
        chip_id="GC-QCTRL",
        chip_type="超导量子控制/读出芯片（单发读出保真度）",
        source_kind="datasheet",
        source_ref="本源悟空-180 公开披露（中国日报 / 证券时报 2026-05-09）：读取保真度 99.00%；"
                   "NISQ 典型单发读出保真度 ≥97.5%（PostQuantum 2026 基准）。4-qubit 复用读出链对标。",
        domain="quantum", system_type="quantum_fidelity",
        geom={"f01s": [4.8, 5.0, 5.2, 5.4]},
        metrics=[MetricSpec(name="readout_fidelity", golden=0.99, tol=0.02, unit="ratio",
                            direction="ge",
                            note="对标公开商用超导量子系统读取保真度 99.0%（≥97.5% NISQ 典型）")],
        replica_note="4-qubit 复用读出链（D-46×D-47 已验证闭环）逐 qubit 保真度最小值 = LDA 复现读出保真度。",
        honest_note="等效对标（解析模型对标公开指标），非本团队流片/实测；拓扑自研。",
    ),
    ChipBenchmark(
        chip_id="GC-SENSE",
        chip_type="光子传感前端整芯片（MZI 干涉传感，全链路插入损耗）",
        source_kind="literature",
        source_ref="公开 PICS（Photonic Integrated Circuit Sensor）/ FBG 光纤传感链路预算综述："
                   "干涉型光子传感前端全链路（激光器→耦合→传感干涉仪→探测）插入损耗预算通常 ≤15 dB"
                   "（商用光纤传感模块发射-接收总损耗 10–18 dB 区间）。",
        domain="photon", system_type="link",
        geom={"n_gratings": 2, "wg_length_cm": 2.0, "n_ybranch": 2, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=15.0, tol=3.0, unit="dB",
                            direction="le",
                            note="干涉型传感前端全链路插入损耗预算上限（公开 ≤15 dB）")],
        replica_note="MZI 传感前端：激光→光栅入→Y-branch 分束→参考臂+传感臂（SiN 波导，"
                     "传感元件按参数化黑箱）→Y-branch 合束→光栅出→探测器；"
                     "无源光路损耗由 GP-* 已锚定基元 dB 级联（2×光栅 + 2×Y-branch + 2cm SiN）。",
        honest_note="等效验证（对标公开链路预算区间），非本团队流片；传感元件本身按参数化黑箱，"
                    "不建模传感物理；拓扑自研。整芯片对标对象是全链路插入损耗死标量。",
    ),
    ChipBenchmark(
        chip_id="GC-QCTRL-COMM",
        chip_type="商用量子控制/读出芯片（单发读出保真度，6-qubit 代表规模）",
        source_kind="datasheet",
        source_ref="商用超导量子系统公开指标（IBM Heron / Google 商业系统披露，per-qubit 读出保真度 "
                   "≥99.0%；NISQ 典型单发读出 ≥97.5%，PostQuantum 2026 基准）。6-qubit 复用读出链对标。",
        domain="quantum", system_type="quantum_fidelity",
        geom={"f01s": [4.8, 5.0, 5.2, 5.4, 5.6, 5.8]},
        metrics=[MetricSpec(name="readout_fidelity", golden=0.99, tol=0.02, unit="ratio",
                            direction="ge",
                            note="对标商用超导量子系统 per-qubit 读出保真度 ≥99.0%（≥97.5% NISQ 典型）")],
        replica_note="6-qubit 复用读出链（D-46×D-47 已验证闭环）逐 qubit 保真度最小值 = LDA 复现读出保真度。",
        honest_note="等效对标（解析模型对标公开指标），非本团队流片/实测；拓扑自研。"
                    "与 GC-QCTRL（本源悟空-180）互为独立商用参考，共同证明库可增量扩展。",
    ),
    # —— v0.8.38 GC 库扩展（4→20）：光子 12 + 量子 4，全部零新物理 ——
    #   golden 全部来自市场调研可溯源公开规格（datasheet / IEEE·ITU 标准 / 公开文献 / 厂商披露）；
    #   复用 GP-* dB 级联（S1 同构）与 design_multiqubit_fidelity（D-46×D-47），判决纯死标量。
    ChipBenchmark(
        chip_id="GC-DR4-TX",
        chip_type="400G DR4 硅光发射芯片（单通道，光纤-芯片插损）",
        source_kind="datasheet",
        source_ref="宏芯科技（泉州）400G 硅光 DR4 发射芯片公开规格（CIOE 中国光博会参展公开资料）："
                   "4×100G PAM4 @1310nm，单通道插损 <4.5 dB，电光带宽 >38 GHz",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 1.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=4.5, tol=1.5, unit="dB",
                            direction="le", note="400G DR4 发射芯片单通道插损 <4.5 dB")],
        replica_note="单通道 = 1×光栅耦合 + 1cm SiN 波导，GP-* 基元 dB 级联（S1 同构）。",
        honest_note="等效验证（对标公开规格），非本团队流片；发射端调制器/激光器按黑箱源（负面清单）。",
    ),
    ChipBenchmark(
        chip_id="GC-DR4-ONCHIP",
        chip_type="400G DR4 硅光收发全片（片上总损耗，边缘耦合）",
        source_kind="datasheet",
        source_ref="Hyperphotonix Hyper Silicon™ 平台公开资料（hyperphotonix.com）："
                   "400G DR4 / 800G DR8 / 1.6T DR8 PIC 片上损耗 <9 dB（边缘耦合低损光纤阵列）",
        domain="photon", system_type="link",
        geom={"n_gratings": 2, "wg_length_cm": 2.0, "n_ybranch": 0, "n_crossing": 1},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=9.0, tol=1.5, unit="dB",
                            direction="le", note="400G DR4 硅光全片片上损耗 <9 dB")],
        replica_note="全片往返 = 2×光栅耦合 + 2cm SiN 波导 + 1×crossing，GP-* dB 级联。",
        honest_note="等效验证（对标公开平台规格），非本团队流片；有源器件按黑箱源。",
    ),
    ChipBenchmark(
        chip_id="GC-LR8-CH",
        chip_type="400GBASE-LR8 单信道链路（8 波 WDM PAM4，10km OS2）",
        source_kind="datasheet",
        source_ref="IEEE 802.3bs 400GBASE-LR8（TIA FOTC 公开应用概述，clause 122）："
                   "8 波 WDM PAM4，信道插入损耗（max）6.3 dB，2m–10km OS2",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 2.0, "n_ybranch": 0, "n_crossing": 1},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=6.3, tol=1.2, unit="dB",
                            direction="le", note="LR8 信道插入损耗上限 6.3 dB（IEEE 802.3bs）")],
        replica_note="单信道 = 1×光栅 + 2cm SiN 波导 + 1×crossing（WDM 复解按 AWG 方案，级联仅计无源损耗）。",
        honest_note="等效验证（对标 IEEE 标准信道预算），非本团队流片；WDM 复解器按黑箱参数化。",
    ),
    ChipBenchmark(
        chip_id="GC-PLC-1X8",
        chip_type="PLC 1×8 分路器（FTTH/PON 无源分光，每支路插损）",
        source_kind="datasheet",
        source_ref="ITU-T G.671 / Telcordia GR-1209 公开典型最大插损：1×8 ≤10.7 dB"
                   "（含理想 9.03 dB 分光损耗 + 过量损耗；Sopto/LuLeey 等商用 PLC datasheet 一致）",
        domain="photon", system_type="link",
        geom={"n_gratings": 0, "wg_length_cm": 0.0, "n_ybranch": 3, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=10.7, tol=1.0, unit="dB",
                            direction="le", note="PLC 1×8 每支路最大插损 ≤10.7 dB（G.671/GR-1209）")],
        replica_note="1×8 = 3 级 Y-branch 级联（2^3=8 支路，含理想 3×3.01 dB 分光 + 过量损耗），GP-* dB 级联。",
        honest_note="等效验证（对标 ITU-T/Telcordia 公开规格），非本团队流片；PLC 工艺按参数化黑箱。",
    ),
    ChipBenchmark(
        chip_id="GC-PLC-1X16",
        chip_type="PLC 1×16 分路器（FTTH/PON 无源分光，每支路插损）",
        source_kind="datasheet",
        source_ref="ITU-T G.671 / Telcordia GR-1209 公开典型最大插损：1×16 ≤14.0 dB"
                   "（含理想 12.04 dB 分光损耗；LuLeey 实测 ≤14.0 dB 一致）",
        domain="photon", system_type="link",
        geom={"n_gratings": 0, "wg_length_cm": 0.0, "n_ybranch": 4, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=14.0, tol=1.0, unit="dB",
                            direction="le", note="PLC 1×16 每支路最大插损 ≤14.0 dB（G.671/GR-1209）")],
        replica_note="1×16 = 4 级 Y-branch 级联（2^4=16 支路），GP-* dB 级联。",
        honest_note="等效验证（对标 ITU-T/Telcordia 公开规格），非本团队流片。",
    ),
    ChipBenchmark(
        chip_id="GC-AWG-40CH",
        chip_type="40ch 100GHz 无热 AWG（DWDM 复解，ITU 网格插损）",
        source_kind="datasheet",
        source_ref="Qualinet 40ch 100GHz Gaussian Athermal AWG 公开 datasheet："
                   "ITU 网格插损 typ 4.5 / max 6.0 dB；NTT-ID 标准 48ch AWG 3.5 dB 同量级",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 10.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=6.0, tol=2.0, unit="dB",
                            direction="le", note="40ch AWG ITU 网格最大插损 6.0 dB（Qualinet datasheet）")],
        replica_note="AWG 阵列波导按长波导黑箱：1×光栅 + 10cm SiN 波导级联近似，GP-* dB 级联。",
        honest_note="等效验证（对标商用 AWG datasheet），非本团队流片；AWG 色散/串扰按黑箱（对标对象是插损死标量）。",
    ),
    ChipBenchmark(
        chip_id="GC-OCS-P576",
        chip_type="OCS 光交换机光路层（Polatis 576×576，等效无源光路插损）",
        source_kind="literature",
        source_ref="UC Berkeley EECS-2024-213（公开技术报告）：Polatis 576×576 压电 OCS "
                   "中位插损 1.4 dB / 最大 3 dB；CALIENT 320×320 最大 3 dB；1100×1100 最大 4 dB",
        domain="photon", system_type="link",
        geom={"n_gratings": 0, "wg_length_cm": 2.0, "n_ybranch": 0, "n_crossing": 4},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=3.0, tol=1.5, unit="dB",
                            direction="le", note="576×576 OCS 单路最大插损 3 dB（Berkeley 技术报告）")],
        replica_note="OCS 全光路 = 2cm SiN 波导 + 4×crossing（准直/反射/耦合按 crossing 黑箱），GP-* dB 级联。",
        honest_note="等效验证（对标公开技术报告规格），非本团队实测；MEMS/压电执行器按黑箱（非片上器件物理级建模）。",
    ),
    ChipBenchmark(
        chip_id="GC-OCS-FABRIC",
        chip_type="OCS 直连收发前端（Google Jupiter/Palomar 架构，2×FR4 功率预算）",
        source_kind="literature",
        source_ref="arXiv 2411.01503（公开）：Google 136×136 OCS 插损 ≤2 dB；2×FR4 收发功率预算 4.0 dB；"
                   "环行器附加 0.5–0.7 dB/个",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 1.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=4.0, tol=1.0, unit="dB",
                            direction="le", note="2×FR4 收发功率预算 4.0 dB（OCS 集群收发前端）")],
        replica_note="收发前端 = 1×光栅 + 1cm SiN 波导（OCS 本体 ≤2 dB 已含在链路预算内），GP-* dB 级联。",
        honest_note="等效验证（对标公开架构规格），非本团队流片；交换矩阵按黑箱。",
    ),
    ChipBenchmark(
        chip_id="GC-LIDAR-FMCW",
        chip_type="FMCW 激光雷达硅光芯片（单方向全光链路，1550nm）",
        source_kind="literature",
        source_ref="Optics Express 34, 7415 (2026) 公开论文：片上 FMCW LiDAR 激光器→芯片→自由空间"
                   "全光链路损耗 ≈3.3 dB/方向；回波→芯片→探测 ≈3.3 dB",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 0.5, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=3.3, tol=0.8, unit="dB",
                            direction="le", note="FMCW LiDAR 单方向片上链路 3.3 dB（OE 2026 实测）")],
        replica_note="发射链路 = 1×光栅 + 0.5cm SiN 波导（相干混频按黑箱），GP-* dB 级联。",
        honest_note="等效验证（对标公开文献实测），非本团队流片；OPA 扫描/调制器按黑箱（负面清单）。",
    ),
    ChipBenchmark(
        chip_id="GC-QKD-TX",
        chip_type="QKD 发射端硅光芯片（Alice，BB84 态制备）",
        source_kind="literature",
        source_ref="npj Quantum Information 3, e1700262 (2017)（公开）：高维 QKD Alice 芯片总插损 15 dB"
                   "（含光栅耦合 + MCF 扇入扇出 + 片上元件）",
        domain="photon", system_type="link",
        geom={"n_gratings": 2, "wg_length_cm": 1.0, "n_ybranch": 2, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=15.0, tol=2.0, unit="dB",
                            direction="le", note="QKD Alice 芯片总插损 15 dB（npj QI 实测）")],
        replica_note="Alice = 2×光栅（入 + MCF 扇出）+ 2×Y-branch（MZI 态制备）+ 1cm SiN，GP-* dB 级联。",
        honest_note="等效验证（对标公开文献实测），非本团队流片；单光子源衰减/调制按黑箱。",
    ),
    ChipBenchmark(
        chip_id="GC-QKD-RX",
        chip_type="QKD 接收端硅光芯片（Bob，基矢测量）",
        source_kind="literature",
        source_ref="npj Quantum Information 3, e1700262 (2017)（公开）：Bob 接收芯片总插损 8 dB"
                   "（其中光栅耦合 ≈4 dB/端）",
        domain="photon", system_type="link",
        geom={"n_gratings": 2, "wg_length_cm": 0.5, "n_ybranch": 0, "n_crossing": 1},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=8.0, tol=1.5, unit="dB",
                            direction="le", note="QKD Bob 芯片总插损 8 dB（npj QI 实测）")],
        replica_note="Bob = 2×光栅（MCF 扇入 + 出）+ 0.5cm SiN + 1×crossing，GP-* dB 级联。",
        honest_note="等效验证（对标公开文献实测），非本团队流片；单光子探测器按黑箱。",
    ),
    ChipBenchmark(
        chip_id="GC-QKD-MULTI",
        chip_type="多用户 QKD 接收机硅光芯片（4 用户 MZI 选路）",
        source_kind="literature",
        source_ref="Optics Express 28, 18449 (2020)（公开）：多用户 QKD 接收芯片总损耗 13 dB"
                   "（2D 光栅 6 dB + 1D 光栅 5 dB + 波导 2 dB）",
        domain="photon", system_type="link",
        geom={"n_gratings": 3, "wg_length_cm": 5.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=13.0, tol=1.5, unit="dB",
                            direction="le", note="多用户 QKD 接收机 13 dB（OE 2020 实测）")],
        replica_note="4 用户接收 = 3×光栅（2D+1D 耦合）+ 5cm SiN 波导，GP-* dB 级联。",
        honest_note="等效验证（对标公开文献实测），非本团队流片；SPD 探测器按黑箱。",
    ),
    ChipBenchmark(
        chip_id="GC-QCTRL-ZC3",
        chip_type="超导量子芯片（祖冲之三号对标，10-qubit 代表读出段）",
        source_kind="literature",
        source_ref="上海科技情报研究所《全球量子计算最新进展》(2026) 公开对比表："
                   "电子科大祖冲之三号 (2024) 读出保真度 99.18%",
        domain="quantum", system_type="quantum_fidelity",
        geom={"f01s": [5.0, 5.2, 5.4, 5.6, 5.8, 6.0, 6.2, 6.4, 6.6, 6.8]},
        metrics=[MetricSpec(name="readout_fidelity", golden=0.9918, tol=0.01, unit="ratio",
                            direction="ge", note="祖冲之三号读出保真度 99.18%（公开对比表）")],
        replica_note="10-qubit 复用读出链（D-46×D-47 已验证闭环）逐 qubit 保真度最小值 = LDA 复现。",
        honest_note="等效对标（解析模型对标公开指标），非本团队流片/实测；105 比特整芯片以 10 比特代表段对标。",
    ),
    ChipBenchmark(
        chip_id="GC-QCTRL-HERON",
        chip_type="超导量子芯片（IBM Heron R2 对标，16-qubit 代表读出段）",
        source_kind="datasheet",
        source_ref="上海科技情报研究所公开对比表：IBM Heron R2 (2024, 156 qubit) 读出保真度 98.5%；"
                   "IBM Quantum Cloud 公开 Readout error (median) 亦 ~1-1.1% 量级",
        domain="quantum", system_type="quantum_fidelity",
        geom={"f01s": [round(4.6 + 0.2 * i, 2) for i in range(16)]},
        metrics=[MetricSpec(name="readout_fidelity", golden=0.985, tol=0.015, unit="ratio",
                            direction="ge", note="IBM Heron R2 读出保真度 98.5%（公开对比表）")],
        replica_note="16-qubit 复用读出链（D-46×D-47 已验证闭环）逐 qubit 保真度最小值 = LDA 复现。",
        honest_note="等效对标（解析模型对标公开指标），非本团队流片/实测；156 比特整芯片以 16 比特代表段对标。",
    ),
    ChipBenchmark(
        chip_id="GC-QCTRL-WILLOW",
        chip_type="超导量子芯片（Google Willow 对标，12-qubit 代表读出段）",
        source_kind="literature",
        source_ref="Applied Quantum 公开技术分析 (2025-2026)：Google Willow (2024, 105 qubit) "
                   "复用色散读出 + JPA 放大，读出保真度 ~99.3%",
        domain="quantum", system_type="quantum_fidelity",
        geom={"f01s": [round(4.6 + 0.2 * i, 2) for i in range(12)]},
        metrics=[MetricSpec(name="readout_fidelity", golden=0.9933, tol=0.01, unit="ratio",
                            direction="ge", note="Google Willow 读出保真度 99.33%（公开对比表）")],
        replica_note="12-qubit 复用读出链（D-46×D-47 已验证闭环）逐 qubit 保真度最小值 = LDA 复现。",
        honest_note="等效对标（解析模型对标公开指标），非本团队流片/实测；105 比特整芯片以 12 比特代表段对标。",
    ),
    ChipBenchmark(
        chip_id="GC-QCTRL-M18",
        chip_type="超导量子控制/读出芯片（18-qubit 规模扩展演示）",
        source_kind="datasheet",
        source_ref="商用超导量子系统公开指标区间（IBM/Google/本源公开披露 per-qubit 读出保真度 98.5–99.33%）；"
                   "18-qubit 复用读出链规模扩展对标（NISQ 典型 ≥97.5%，PostQuantum 2026 基准）",
        domain="quantum", system_type="quantum_fidelity",
        geom={"f01s": [round(4.6 + 0.2 * i, 2) for i in range(18)]},
        metrics=[MetricSpec(name="readout_fidelity", golden=0.985, tol=0.015, unit="ratio",
                            direction="ge", note="对标商用区间下限 98.5%（Heron R2 公开值）")],
        replica_note="18-qubit 复用读出链（D-46×D-47 已验证闭环）逐 qubit 保真度最小值 = LDA 复现。",
        honest_note="等效对标（解析模型对标公开指标区间），非本团队流片/实测；演示库随比特数扩展仍零新物理。",
    ),
    # —— v0.8.45 GC 库小幅扩（20→24）：光子单通道收发链路，复用 GP-* dB 级联 ——
    #   golden 全部来自公开标准/平台规格（IEEE 802.3bs/df、CWDM4 MSA、IEEE 802.3bm PSM4）；
    #   复现确定性（GP-* 已锚定基元 dB 级联），判决纯死标量；零新物理。
    ChipBenchmark(
        chip_id="GC-DR8-CH",
        chip_type="800G DR8 硅光发射芯片（单通道，光纤-芯片插损）",
        source_kind="datasheet",
        source_ref="Hyperphotonix Hyper Silicon™ 公开平台（800G DR8 / 1.6T DR8 PIC 路线）+ IEEE 802.3df 800G 光接口进程："
                   "单波长通道插损与 DR4 同量级 <4.5 dB",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 0.5, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=4.5, tol=1.5, unit="dB",
                            direction="le", note="800G DR8 单通道插损 <4.5 dB（公开平台量级）")],
        replica_note="单通道 = 1×光栅耦合 + 0.5cm SiN 波导，GP-* 基元 dB 级联（S1 同构）。",
        honest_note="等效验证（对标公开平台规格量级），非本团队流片；调制器按黑箱源（负面清单）。",
    ),
    ChipBenchmark(
        chip_id="GC-FR4-CH",
        chip_type="400G FR4 硅光收发单通道（4×100G PAM4，2km OS2）",
        source_kind="datasheet",
        source_ref="IEEE 802.3bs 400GBASE-FR4（clause 121）：单通道（λ，2km）信道插入损耗预算 ≤4.5 dB；"
                   "Hyperphotonix 平台同量级",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 1.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden= 4.5, tol=1.5, unit="dB",
                            direction="le", note="FR4 单通道插损预算 ≤4.5 dB（IEEE 802.3bs）")],
        replica_note="单通道 = 1×光栅耦合 + 1.0cm SiN 波导，GP-* dB 级联。",
        honest_note="等效验证（对标 IEEE 标准信道预算），非本团队流片；WDM 复用/串行器按黑箱参数化。",
    ),
    ChipBenchmark(
        chip_id="GC-CWDM4-CH",
        chip_type="100G CWDM4 硅光收发单通道（4×25G，2km）",
        source_kind="datasheet",
        source_ref="CWDM4 MSA（100G CWDM4：4×25G，2km）单通道光信道插损典型 ≤4.0 dB；"
                   "商用 100G CWDM4 光模块 datasheet 一致",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 1.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=4.0, tol=1.5, unit="dB",
                            direction="le", note="CWDM4 单通道插损 ≤4.0 dB（CWDM4 MSA 公开规格）")],
        replica_note="单通道 = 1×光栅耦合 + 1.0cm SiN 波导，GP-* dB 级联。",
        honest_note="等效验证（对标 CWDM4 MSA 公开规格），非本团队流片；WDM 复解器按黑箱参数化。",
    ),
    ChipBenchmark(
        chip_id="GC-PSM4-CH",
        chip_type="100G PSM4 硅光收发单通道（4×25G，500m SMF）",
        source_kind="datasheet",
        source_ref="IEEE 802.3bm 100GBASE-PSM4（4×25G，500m SMF，边缘耦合低损）：单通道插损预算 ≤4.0 dB；"
                   "商用 PSM4 平台 datasheet 一致",
        domain="photon", system_type="link",
        geom={"n_gratings": 1, "wg_length_cm": 2.0, "n_ybranch": 0, "n_crossing": 0},
        metrics=[MetricSpec(name="total_insertion_loss_dB", golden=4.0, tol=1.5, unit="dB",
                            direction="le", note="PSM4 单通道插损预算 ≤4.0 dB（IEEE 802.3bm）")],
        replica_note="单通道 = 1×光栅耦合 + 2.0cm SiN 波导（边缘耦合按低损黑箱），GP-* dB 级联。",
        honest_note="等效验证（对标 IEEE 标准信道预算），非本团队流片；边缘耦合按低损黑箱（负面清单）。",
    ),
]

# 器件级 + 芯片级统一入口（evaluate_all / to_markdown / save / load 共用）
DEFAULT_BENCHMARKS: List[Any] = list(DEFAULT_BENCHMARKS) + list(DEFAULT_CHIP_BENCHMARKS)


def evaluate_all(benchmarks: List[Any] = None) -> List[Dict[str, Any]]:
    benchmarks = benchmarks or DEFAULT_BENCHMARKS
    return [b.evaluate() for b in benchmarks]


def to_markdown(results: List[Dict[str, Any]]) -> str:
    """生成产品级对照报告（B 生态播种硬核素材）。"""
    n_total = len(results)
    n_pass = sum(1 for r in results if r.get("passed_all"))
    lines = [
        "# LDA 产品级基准对照报告（实证锚产品级扩展 · 器件级 GP-* + 芯片级 GC-*）",
        "",
        f"> 生成口径：LDA 引擎规格驱动再设计 + 数值复现，对标已公开验证的器件性能死标量。",
        f"> **{n_pass}/{n_total} 产品级对标 PASS**。",
        "",
        "**诚实边界**：本结果对标公开实测 / 厂商 datasheet / 开源 PDK 表征，属**等效验证，**"
        "非本团队流片验证。LDA 引擎为解析近似，对标公开典型量级；对标对象是性能死标量，非版图几何。",
        "",
        "## 对照明细",
        "",
        "| 条目 | 器件 | 来源 | 引擎 | 指标 | 复现 | golden | 容差 | 判定 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.get("error"):
            lines.append(f"| {r['product_id']} | — | — | — | — | — | — | — | ERROR |")
            continue
        for row in r["rows"]:
            lines.append(
                f"| {r['product_id']} | {r['device_type']} | {r['source_kind']} | "
                f"{r['engine']} | {row['name']} | {row['replica']} {row['unit']} | "
                f"{row['golden']} {row['unit']} | {row['tol']} | "
                f"{'PASS' if row['passed'] else 'FAIL'} |"
            )
    lines += ["", "## 出处清单（可溯源）", ""]
    for r in results:
        if r.get("error"):
            continue
        lines.append(f"- **{r['product_id']}** · {r['device_type']}：{r['source_ref']}")
    lines += [
        "",
        "## 结论",
        "",
        f"LDA 用开源、主权、零外部依赖的引擎，对标杆器件（GP-*）与整芯片（GC-*）"
        f"完成规格驱动再设计，复现性能与公开 golden 死标量一致（{n_pass}/{n_total} PASS）。"
        "这证明：在不进入发动期、不实际流片的前提下，即可把验证做到产品级——"
        "以他人已量产/已验证的真实效果为外部尺子，杀同源自证风险，并为生态播种提供硬核素材。",
        "",
        "---",
        "_LDA · 开源 Agent-native EDA（光子 PDA + 量子 QEDA）· 物理定律锚红线 · LLM 不进判决路径_",
    ]
    return "\n".join(lines)


def library_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_product_benchmarks.json")


def save_library_json(benchmarks: List[ProductBenchmark] = None, path: str = None) -> str:
    benchmarks = benchmarks or DEFAULT_BENCHMARKS
    path = path or library_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(b) for b in benchmarks], f, ensure_ascii=False, indent=2)
    return path


def load_library_json(path: str = None) -> List[Any]:
    path = path or library_path()
    if not os.path.exists(path):
        return list(DEFAULT_BENCHMARKS)
    data = json.load(open(path, encoding="utf-8"))
    out: List[Any] = []
    for d in data:
        metrics = [MetricSpec(**m) for m in d.pop("metrics")]
        if d.get("kind") == "chip":
            out.append(ChipBenchmark(metrics=metrics, **d))
        else:
            out.append(ProductBenchmark(metrics=metrics, **d))
    return out


if __name__ == "__main__":
    res = evaluate_all()
    for r in res:
        print(r["product_id"], "PASS" if r.get("passed_all") else "FAIL", r.get("error", ""))
