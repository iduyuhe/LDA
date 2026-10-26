"""端到端 SOC 流程编排（E33 · D-208）：**从规格到 GDS 的一条可执行链**。

E20–E32 十三段全是单点（口径 / 器件 / ADC / 行线 / 版图 / 签核），**从没串成一次完整设计流程**。
本模块把十三个模块串成 8 个 Stage，每步 fail-fast，产物是**一份带口径的签核报告**。

## 为什么"串起来"本身会产生新结论

单点各自正确，不等于串起来正确。本模块在串接时抓到两类**只在跨模块才显形**的缺陷：

### ① 面积口径混用：把"规模收益"记成了"换层代价"

`e32.signed_off_stack.best_layer()` 报「**面积 ×74.28**」，但 74.28 的构成是：

```
74.28 = 52.56（N 12→87 的 N² 规模因子，**这是收益**）× 1.41（换层因子，**这才是代价**）
```

而换层代价的真实值是 **1.33×**（同 N=87 下 `pitch_y` 2.40→3.20）。
⇒ 74.28 这个数字**同时混入了收益与代价**，读者会误以为「换层要付 74 倍面积」。

🔴 **本模块纪律**：面积必须**两个都报**且各自标注性质 ——
`area_same_n_ratio`（换层代价，与规模无关）· `area_total_ratio`（含规模，主要是收益的副产品）。

### ② 能效有两个口径，相差 3.27×，而只有一个能对外

| 来源 | N=87 | E25 的裁决 |
|---|---|---|
| `energy.system_energy_report`（自算 CDAC 开关能量） | **7.555 fJ/op** | 🔴 **下界**：CDAC 只占 ADC 总能耗 0.6~3.6% ⇒ 漏掉 96%+ 主体 ⇒ **不可对外** |
| `adc_calibration`（三条实测 FOM 锚反推） | **24.717 fJ/op** | ✅ **可信**（口径是实测外锚） |

**流程若不知道这个，就会把 7.555 当结果报出去 —— 那正好是 E25 花一整段纠正的错误。**

🔴 **本模块纪律**：每个数值都带 `basis` + `claimable`，**"哪个能对外"是机器可查的，不是注释里的约定**。

## Stage 序列

```
device ─→ scale ─→ stack ─→ layout ─→ drc ─→ lvs ─→ gds ─→ report
 器件族    基线能力   换层选型   版图生成   DRC    LVS   导出    带口径汇总
```

**fail-fast 语义**：任一步 `ok=False` ⇒ 立即停，后续标 `SKIPPED`，`halted_at` 记录停点。
**反向完备**：只有 `stages_completed == 8` 才 `flow_ok=True` —— 少一步都不算跑通。

## fail 与"未达标"是两件事（本模块的边界）

- **fail** 只留给**物理/工具不可行**：无族可行 · 基线不可用 · 无层可签核 · DRC/LVS/GDS 不通过。
- **未达能效目标**（`vs_target > 1`）**不 fail** —— 那是「差距」，不是「不可行」。

把两者混在一起，就会为了让流程"绿"而放宽判据，或为了"诚实"而把差距当失败。

## 保护性约束

纯标准库 · **只读消费** E7/E15/E21/E25/E26/E27/E28/E30/E31/E32，不改任何默认值 ·
器件族与工艺参数为**公开 A 级来源照录（非 PDK）** · 输出恒 `MODEL_ESTIMATE` ·
**净增 0 锚**（流程产物是设计期验证，不是实测语料）。
"""

from typing import Dict, List, Optional, Sequence, Tuple

from lda_l2.ecore import adc_calibration as C
from lda_l2.ecore import device_family as D
from lda_l2.ecore import elayers as EL
from lda_l2.ecore import energy as E
from lda_l2.ecore import layout as LY
from lda_l2.ecore import row_metal as RM
from lda_l2.ecore import signed_off_stack as S

#: 输出档（与 `energy.OUTPUT_TIER` 一致）
TIER = E.OUTPUT_TIER

#: Stage 序列（顺序即依赖顺序 · **反向完备判据的基准**）
STAGES: Tuple[str, ...] = ("device", "scale", "stack", "layout", "drc", "lvs", "gds", "report")

#: 每条 Stage 的职责（写进报告，防"跑了但不知道跑了什么"）
STAGE_ROLE: Dict[str, str] = {
    "device": "按必要条件筛器件族（8 bit/cell 是硬门槛）",
    "scale": "基线（M1 单端）在给定预算下的可及规模 —— **换层前的 before 值**",
    "stack": "在可签核的层中选规模最大者 —— **换层后的 after 值**",
    "layout": "生成带 via stack 的阵列几何",
    "drc": "几何 DRC（16 层栈 · 空间索引）",
    "lvs": "几何连通性签核（16 层栈 · 空间索引）",
    "gds": "GDSII 导出 + 层次化 roundtrip 回读",
    "report": "能效与代价汇总 —— **每个数字带 basis 与 claimable**",
}

#: 默认规格
SPEC_DEFAULT: Dict[str, object] = {
    "budget_pct": 5.0,          # 输出误差预算（%）
    "target_fj_per_op": 8.3,    # 能效目标（Mythic 120 TOPS/W 档）
    "bits": 8,                  # 权重精度（E22：8 bpc 是硬门槛）
    "share_k": 1,               # ADC 列共享（E27：β 未知 ⇒ 缺省不共享）
    "adc_anchor": "a28_8b",     # 能效可信口径的实测锚（E25）
    "verify_gds": True,         # 是否跑 GDS 导出（大阵列关闭可省 ~2.5s）
}

#: 低于这个规模就没有 MVM 意义 ⇒ `scale` 步 fail（不是"未达标"）
MIN_N = 2

#: 器件**读电流量级**的代表值（S）—— 用于第 ⑧ 步"自算能效"的内部对照。
#: 🔴 这**不是器件规格**，是从各族 `read_current_note` 照录的量级代表值；
#:   集中放一处是为了不让第二份口径散落在流程代码里。
#:   它只喂给 `energy.system_energy_report`（E25 已判定那条路径是**下界**），
#:   **不参与任何可对外数字**。
G_READ_TYP_S: Dict[str, float] = {
    "nor_flash": 2.0e-8,      # SST 官方：单比特读电流 <10 nA @0.3~0.5 V
    "rram": 5.0e-6,           # Weebit IMW2024：~5 µA
    "pcm": 1.0e-5,            # IBM PCM：~10 µA 量级
    "sram_analog": 5.0e-5,    # 模拟 SRAM CIM：~50 µA 量级
}

#: 器件族的**精度与耐久硬门槛**（E22 的 C2/C3）—— 与能效目标**无关**
MIN_BITS_PER_CELL = 8
MIN_ENDURANCE = 1.0e5


# ---------------------------------------------------------------------------
# Stage 实现
# ---------------------------------------------------------------------------
def _ok(name: str, metrics: Dict, verdict: str, elapsed_s: float = 0.0,
        aux: object = None) -> Dict:
    """成功结果。`aux` 是**不参与对拍、不进报告**的内部载荷（如已生成的几何）。"""
    return {"stage": name, "ok": True, "status": "PASS",
            "metrics": metrics, "verdict": verdict,
            "elapsed_s": round(elapsed_s, 4), "aux": aux}


def _fail(name: str, metrics: Dict, verdict: str, elapsed_s: float = 0.0) -> Dict:
    return {"stage": name, "ok": False, "status": "FAIL",
            "metrics": metrics, "verdict": verdict,
            "elapsed_s": round(elapsed_s, 4)}


def _skip(name: str, halted_at: str) -> Dict:
    return {"stage": name, "ok": False, "status": "SKIPPED",
            "metrics": {}, "verdict": "上游 %s 已停 ⇒ 本步未执行" % halted_at,
            "elapsed_s": 0.0}


def stage_device(bits: int) -> Dict:
    """① 器件族：只按**与能效无关的硬门槛**筛（C2 精度 / C3 耐久 / C4 工艺）。

    🔴 **本步不看能效目标** —— 这是「fail 与未达标分开」的第一处硬约束。
    v0.9.329 第一版把 `recommend_family(target_fj)` 放在这里，结果默认目标 8.3 fJ/op
    （低于任何族的物理地板）让流程**第 1 步就 fail** —— 那等于说「达不到理想水平 = 器件不存在」，
    正是本模块要禁止的混同。（E22 的真实结论是「8.3 目标下无族可行」，那是**差距**，
    应在第 ⑧ 步如实报 `vs_target`，不该让流程停摆。）

    能效可达性留在第 ⑧ 步：`family_feasibility(target)` 报「目标下是否可达」。
    """
    import time
    t0 = time.perf_counter()
    fams = list(D.DEVICE_FAMILIES)
    # C2 精度 + C3 耐久（E22 判定的两条硬门槛）
    # 🔴 门槛就是需求的 `bits`，**不取 min** —— v0.9.329 第一版写成
    #   `min(bits, MIN_BITS_PER_CELL)`，等于「要 10 bit 也按 8 bit 放行」，
    #   把硬门槛抹平了（8bpc 器件做不出 10 bit/cell）。MIN_BITS_PER_CELL 只是
    #   说明「E22 判定的门槛值」，不是上限。
    fit = [f for f in fams
           if int(f.get("bits_per_cell") or 0) >= int(bits)
           and float(f.get("endurance_cycles") or 0.0) >= MIN_ENDURANCE]
    if not fit:
        return _fail("device",
                     {"n_family": len(fams), "n_feasible": 0,
                      "need_bits": bits, "need_endurance": MIN_ENDURANCE},
                     "🔴 **无族满足 %d bit/cell + 耐久 ≥%.0e** ⇒ 设计不可成立"
                     % (bits, MIN_ENDURANCE), time.perf_counter() - t0)
    # 取电导裕度最大者（g_min 最小 ⇒ 器件项最容易压到 0）
    best = sorted(fit, key=lambda f: f.get("g_min_s") or 1.0)[0]
    rejected = [f for f in fams if f not in fit]
    reason = {}
    for f in rejected:
        if int(f.get("bits_per_cell") or 0) < int(bits):
            reason[f["id"]] = "精度 %d<%d bit/cell" % (int(f.get("bits_per_cell") or 0), int(bits))
        else:
            reason[f["id"]] = "耐久不足"
    return _ok("device",
               {"n_family": len(fams), "n_feasible": len(fit),
                "chosen": best["id"], "chosen_name": best.get("name", ""),
                "bits_per_cell": best.get("bits_per_cell"),
                "endurance_cycles": best.get("endurance_cycles"),
                "g_min_s": best.get("g_min_s"), "g_max_s": best.get("g_max_s"),
                "maturity": best.get("maturity"),
                "g_typ_s": G_READ_TYP_S.get(best["id"]),
                "rejected": reason},
               "器件族 = **%s**（%d/%d 族过精度+耐久门槛 · %s）· 被否：%s"
               % (best.get("name", best["id"]), len(fit), len(fams),
                  best.get("maturity", ""),
                  "；".join("%s(%s)" % (k, v) for k, v in reason.items())),
               time.perf_counter() - t0)


def stage_scale(budget_pct: float) -> Dict:
    """② 基线能力：**M1 单端**在预算下的可及规模（换层前的 before 值）。

    🔴 本步**不因规模小而 fail** —— 它的职责是给出 before，
    能不能做得更大由第 ③ 步（换层）决定。这是「fail 与未达标分开」的第一处体现。
    """
    import time
    t0 = time.perf_counter()
    r0 = RM.seg_rc("m1", LY.DEFAULT_CELL_PARAMS["row_w_um"],
                   LY.DEFAULT_CELL_PARAMS["pitch_x_um"])["r_seg_ohm"]
    nc = RM.n_ceiling_for(r0, budget_pct=budget_pct)
    n = nc["n_max"]
    if n < MIN_N:
        return _fail("scale",
                     {"r_seg_ohm": r0, "n_max": n, "budget_pct": budget_pct},
                     "🔴 基线在 %.1f%% 预算下只能做 **%d 行**（< MIN_N=%d）⇒ 任何阵列都不可用"
                     % (budget_pct, n, MIN_N), time.perf_counter() - t0)
    return _ok("scale",
               {"r_seg_ohm": r0, "n_max": n, "n_max_ir_only": nc.get("n_max_ir_only"),
                "budget_pct": budget_pct, "saturated": nc.get("saturated", False)},
               "基线（M1 单端 · r=%.4f Ω/段）⇒ N ≤ **%d** 行" % (r0, n),
               time.perf_counter() - t0)


def stage_stack(budget_pct: float) -> Dict:
    """③ 换层选型：在**可签核**的层里选规模最大者（E31 实测 6/7 层通过）。"""
    import time
    t0 = time.perf_counter()
    mx = S.signoff_matrix()
    signed = [r for r in mx if r.get("signoff")]
    if not signed:
        return _fail("stack",
                     {"n_layer": len(mx), "n_signed_off": 0},
                     "🔴 7 个目标层**无一通过** DRC+LVS ⇒ 无层可选",
                     time.perf_counter() - t0)
    tab = S.attainable_table(budget_pct)
    signed_names = {r["row_layer"] for r in signed}
    cand = [r for r in tab if r["row_layer"] in signed_names]
    best = max(cand, key=lambda r: r["n_max"])
    return _ok("stack",
               {"chosen": best["row_layer"], "w_um": best["w_um"],
                "pitch_y_um": best["pitch_y_um"], "r_seg_ohm": best["r_seg_ohm"],
                "r_ratio": best["r_ratio"], "n_max": best["n_max"],
                "adc_fj": best["adc_fj"], "vs_mythic": best["vs_mythic"],
                "area_mm2": best["area_mm2"],
                "n_layer_total": len(mx), "n_layer_signed_off": len(signed),
                "signed_off_layers": sorted(signed_names),
                "rejected_layers": sorted({r["row_layer"] for r in mx
                                           if not r.get("signoff")})},
               "换层到 **%s**（W=%.2f · pitch_y=%.2f）⇒ N 上界 **%d** 行 · "
               "1/7 层被否：%s"
               % (best["row_layer"], best["w_um"], best["pitch_y_um"], best["n_max"],
                  ",".join(sorted({r["row_layer"] for r in mx if not r.get("signoff")}))),
               time.perf_counter() - t0)


def stage_layout(n: int, row_layer: str, w_um: float, pitch_y_um: float) -> Dict:
    """④ 版图生成：带 via stack 的阵列几何（E31 的 `via_stack_descs`）。"""
    import time
    t0 = time.perf_counter()
    prm = {"row_w_um": float(w_um), "pitch_y_um": float(pitch_y_um)}
    arr = LY.crossbar_array(n, n, prm, row_layer=row_layer, via_stack=True)
    descs = arr["descs"]
    # 🔴 via 必须**两个口径**（E31 把它们混成一个，导致良率高估 2×）：
    #   · `n_via_geom`      = 几何里的 VIA* 图元总数（含单元自带源极 VIA1）⇒ 面积/DRC 用
    #   · `n_via_in_path`   = **漏极到行线的串联 via 数**（= ROW_STACK_CHAIN 里 kind=='via' 的个数）
    #                         ⇒ **良率必须用这个**：串联链路任一失效即通路失效
    n_via_geom = sum(1 for d in descs
                     if LY._NAME_OF_LAYER.get(d["layer"], "").startswith("VIA"))
    st10 = EL.get_estack("ecmos10")
    n_via_in_path = sum(1 for nm in LY.ROW_STACK_CHAIN
                        if st10.layers[nm].kind == "via")
    n_via = n_via_in_path * n * n          # 用于良率：串联数 × 单元数
    fw, fh = arr["footprint_um"]
    if not descs:
        return _fail("layout", {"n_elements": 0},
                     "🔴 几何为空", time.perf_counter() - t0)
    return _ok("layout",
               {"n": n, "n_elements": len(descs), "n_via": n_via,
                "n_via_in_path": n_via_in_path, "n_via_geom": n_via_geom,
                "footprint_um": [fw, fh], "area_mm2": fw * fh / 1e6,
                "row_layer": row_layer, "params": prm,
                "via_stack": arr.get("via_stack")},
               "N=%d ⇒ **%s 元素** · via **串联 %d 个/单元**（几何图元 %s 个）· 足迹 %.1f×%.1f µm"
               % (n, format(len(descs), ","), n_via_in_path,
                  format(n_via_geom, ","), fw, fh),
               time.perf_counter() - t0, aux=descs)


def stage_drc(descs: Sequence[Dict]) -> Dict:
    """⑤ DRC（16 层栈 + 空间索引 · E32）。"""
    import time
    t0 = time.perf_counter()
    st = EL.get_estack("ecmos10")
    d = LY.run_edrc(descs, stack=st)
    ok = d["verdict"] == "ACCEPT"
    met = {"verdict": d["verdict"], "n_violations": len(d["violations"]),
           "n_checked": d.get("checked")}
    out = (_ok if ok else _fail)("drc", met,
                                 ("DRC **ACCEPT**（0 违规）" if ok else
                                  "🔴 DRC **REJECT**（%d 处 · 首条：%s）"
                                  % (len(d["violations"]),
                                     (d["violations"][0]["detail"][:64]
                                      if d["violations"] else "—"))),
                                 time.perf_counter() - t0)
    return out


def stage_lvs(descs: Sequence[Dict], n: int,
              params: Optional[Dict[str, float]] = None) -> Dict:
    """⑥ LVS 连通性签核（16 层栈 + 空间索引）。

    🔴 `params` **必须**传实际几何参数：期望网表若用缺省 `pitch_y=2.40`
    而几何用 `3.20`，单元位置会整体错位 ⇒ LVS 报大量假悬空
    （E31 开发时当场踩到过一次，本步把它固化成参数）。
    """
    import time
    t0 = time.perf_counter()
    st = EL.get_estack("ecmos10")
    exp = LY.expected_netlist(n, n, dict(params or {}))
    lv = LY.elvs_signoff(descs, exp, stack=st)
    ok = lv["verdict"] == "ACCEPT"
    met = {"verdict": lv["verdict"], "n_issues": len(lv["issues"])}
    return (_ok if ok else _fail)("lvs", met,
                                  ("LVS **ACCEPT**（0 issue）" if ok else
                                   "🔴 LVS **REJECT**（%d 条 · 首条：%s）"
                                   % (len(lv["issues"]),
                                      (lv["issues"][0][:64] if lv["issues"] else "—"))),
                                  time.perf_counter() - t0)


def stage_gds(n: int, row_layer: str, w_um: float, pitch_y_um: float,
              n_elements_expected: int) -> Dict:
    """⑦ GDS 导出 + 层次化 roundtrip。

    🔴 **`flat_elements ≡ len(descs)` 是"GDS 没丢元素"的机核**
    —— 不等就说明有几何进了 DRC 却没进文件（E31 修过这类静默丢失）。
    """
    import time
    t0 = time.perf_counter()
    prm = {"row_w_um": float(w_um), "pitch_y_um": float(pitch_y_um)}
    g = LY.to_gds(n, n, prm, row_layer=row_layer, via_stack=True)
    rt = LY.gds_roundtrip_check(n, n, prm, row_layer=row_layer, via_stack=True)
    met = {"n_bytes": g["n_bytes"], "flat_elements": g["flat_elements"],
           "n_elements_expected": n_elements_expected,
           "roundtrip_match": bool(rt["match"]),
           "expanded_top_elements": rt["expanded_top_elements"]}
    ok = (met["flat_elements"] == n_elements_expected) and met["roundtrip_match"]
    return (_ok if ok else _fail)(
        "gds", met,
        ("GDS **%s 字节** · flat %s ≡ 几何元素数 · roundtrip match"
         % (format(g["n_bytes"], ","), format(g["flat_elements"], ","))) if ok else
        ("🔴 GDS 不完备：flat %d ⟷ 几何 %d · roundtrip %s"
         % (g["flat_elements"], n_elements_expected, rt["match"])),
        time.perf_counter() - t0)


def stage_report(n: int, row_layer: str, g_typ_s: float, adc_anchor: str,
                 share_k: int, bits: int, target_fj: float,
                 area_mm2: float, n_via: int, n_via_per_cell: int, base_n: int,
                 base_area_mm2: float, pitch_y_um: float = 2.40) -> Dict:
    """⑧ 汇总：**每个数字带 basis + claimable**（本模块的核心纪律）。

    🔴 三类数字必须分开，混在一起就是把 E25 的教训又忘一次：

    | 数值 | basis | claimable | 理由 |
    |---|---|---|---|
    | 可信能效 | `measured_adc_anchor` | ✅ | 用三条实测 FOM 外锚，E25 口径 |
    | 自算能效 | `self_calc_cdac_only` | ❌ | CDAC 只占 ADC 0.6~3.6% ⇒ 下界 |
    | 换层面积代价 | `same_n_pitch_ratio` | ✅ | 同 N 下比，与规模无关 |
    | 总面积比 | `abs_area_ratio` | 🟡 | **含规模收益**，不能当代价读 |
    """
    import time
    t0 = time.perf_counter()

    # ── 能效：两个口径都算，但只有实测锚那一个 claimable ──
    e_trust = C.adc_energy_per_op_from_anchor(adc_anchor, n, share_k)
    e_self = E.system_energy_report(n, bits=bits, col_share_k=share_k, g_s=g_typ_s)
    energy_metrics = [
        {"name": "energy_per_op_fj", "value": e_trust["adc_energy_per_op_fj"],
         "basis": "measured_adc_anchor(%s)" % adc_anchor, "claimable": True,
         "note": "E25 口径：用实测 ADC FOM 反推 ⇒ 唯一可对外的能效值"},
        {"name": "energy_per_op_fj_selfcalc", "value": e_self["energy_per_op_fj"],
         "basis": "self_calc_cdac_only", "claimable": False,
         "note": "E25 判为**下界**：只算 CDAC 开关能量（占实测 ADC 0.6~3.6%）（漏 96%+）"},
    ]
    e_claim = e_trust["adc_energy_per_op_fj"]
    vs_target = e_claim / target_fj

    # ── 面积：两个口径，性质不同 ──
    # 🔴 `same_n_ratio` **必须真同 N 比**：直接算两次 `array_footprint(n, n)`。
    #   v0.9.329 第一版写成 `area_mm2 / (base_area × (n/base_n)²)` —— 那是**跨 N 除法**，
    #   footprint 里的**常数边距项**（端帽/边）不随 N² 缩放 ⇒ 归一化不干净，
    #   得到 1.40 而不是真实的 1.3333（N=12 的边距占比比 N=48 大得多）。
    #   教训与 E20「跨口径比较必须同口径」同型，只是这次发生在**面积**上。
    fw_a, fh_a = LY.array_footprint(n, n)                       # 同 N · 基线 pitch_y
    fw_b, fh_b = LY.array_footprint(n, n, {"pitch_y_um": pitch_y_um})   # 同 N · 本方案
    same_n_ratio = (fw_b * fh_b) / (fw_a * fh_a) if fw_a * fh_a else None
    total_ratio = area_mm2 / base_area_mm2 if base_area_mm2 else None
    area_metrics = [
        {"name": "area_mm2", "value": area_mm2, "basis": "absolute", "claimable": True,
         "note": "本设计（N=%d）的绝对面积" % n},
        {"name": "area_same_n_ratio", "value": same_n_ratio,
         "basis": "same_n_pitch_ratio", "claimable": True,
         "note": "🔴 **换层代价**（同 N 下两次 footprint 直接比 · 与规模无关）"
                 "—— 这才是设计选择付出的面积"},
        {"name": "area_total_ratio", "value": total_ratio,
         "basis": "abs_area_ratio_vs_baseline", "claimable": False,
         "note": "🔴 **不可当代价读**：主要成分是 N %d→%d 的规模因子 %.2f×（那是收益）"
                 % (base_n, n, (n / float(base_n)) ** 2)},
    ]

    rep = {
        "n": n, "row_layer": row_layer,
        "energy_per_op_fj": e_claim,
        "vs_target": vs_target,
        "target_fj_per_op": target_fj,
        "energy_metrics": energy_metrics,
        "area_metrics": area_metrics,
        "via_count": n_via,
        "via_yield_risk": {
            "modeled": False,
            "n_via_in_path_per_cell": int(n_via_per_cell),
            "n_via_total": n_via,
            "note": "🔴 **良率完全未建模**：漏极通路 **串联 %s 个 via** × %s 单元 = %s 个串联节点，"
                    "1 ppm/节点 ⇒ 整体 ~%.2f%% 失效"
                    % (format(n_via_per_cell, ","), format(n * n, ","),
                       format(n_via, ","), n_via * 1e-6 * 100.0),
        },
        "tier": TIER,
    }
    return _ok("report", rep,
               "🔴 可对外能效 **%.2f fJ/op**（%s · vs 目标 %.1f ⇒ **%.2f×**）· "
               "换层面积代价 **×%.2f**（同 N）· 总面积 ×%.1f（含规模，不可当代价）· "
               "via 串联 %d 个/单元（共 %s 个 · 良率未建模）"
               % (e_claim, adc_anchor, target_fj, vs_target,
                  same_n_ratio or 0.0, total_ratio or 0.0,
                  n_via_per_cell, format(n_via, ",")),
               time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# 编排器
# ---------------------------------------------------------------------------
def run_flow(n_target: Optional[int] = None,
             spec: Optional[Dict] = None,
             verify_gds: Optional[bool] = None) -> Dict:
    """跑完整 8 步流程。**任一步 FAIL ⇒ 立即停**，后续标 `SKIPPED`。

    `n_target`：若给定，则**按此规模出图**（用于验证指定规模可签核）；
    缺省用第 ③ 步（换层）给出的 N 上界。
    """
    import time
    sp = dict(SPEC_DEFAULT)
    if spec:
        sp.update(spec)
    if verify_gds is not None:
        sp["verify_gds"] = bool(verify_gds)

    t_all = time.perf_counter()
    stages: List[Dict] = []
    halted_at: Optional[str] = None

    def _run(name: str, fn, *a, **k) -> Optional[Dict]:
        """执行一步；失败则记录 halt 并返回 None（调用者立即退后续）。"""
        nonlocal halted_at
        if halted_at is not None:
            stages.append(_skip(name, halted_at))
            return None
        try:
            r = fn(*a, **k)
        except Exception as e:                      # 例外也必须变成"停"，不许静默
            r = _fail(name, {"exception": type(e).__name__},
                      "🔴 异常终止：%s: %s" % (type(e).__name__, str(e)[:110]))
        stages.append(r)
        if not r["ok"]:
            halted_at = name
            return None
        return r

    # ① 器件族
    r = _run("device", stage_device, sp["bits"])
    if r is None:
        return _pack(stages, halted_at, sp, t_all, n_target)
    g_typ = r["metrics"]["g_typ_s"]

    # ② 基线能力
    r = _run("scale", stage_scale, sp["budget_pct"])
    if r is None:
        return _pack(stages, halted_at, sp, t_all, n_target)
    base_n = r["metrics"]["n_max"]
    # 基线面积（同参数、同 N，用于第 8 步的"同 N 归一化"）
    fw0, fh0 = LY.array_footprint(base_n, base_n)
    base_area = fw0 * fh0 / 1e6

    # ③ 换层选型
    r = _run("stack", stage_stack, sp["budget_pct"])
    if r is None:
        return _pack(stages, halted_at, sp, t_all, n_target)
    st_m = r["metrics"]
    row_layer = st_m["chosen"]
    w_um, py_um = st_m["w_um"], st_m["pitch_y_um"]
    n_use = int(n_target) if n_target else int(st_m["n_max"])
    if n_use < MIN_N:
        halted_at = "stack"
        stages[-1] = _fail("stack", st_m,
                           "🔴 换层后规模 %d < MIN_N=%d" % (n_use, MIN_N))
        return _pack(stages, halted_at, sp, t_all, n_target)

    # ④ 版图
    r = _run("layout", stage_layout, n_use, row_layer, w_um, py_um)
    if r is None:
        return _pack(stages, halted_at, sp, t_all, n_target)
    lay = r["metrics"]
    descs = r["aux"]          # 🔴 复用第 ④ 步已生成的几何，不重建（N=87 重建要 0.29s）

    # ⑤ DRC
    if _run("drc", stage_drc, descs) is None:
        return _pack(stages, halted_at, sp, t_all, n_target)

    # ⑥ LVS
    if _run("lvs", stage_lvs, descs, n_use, lay["params"]) is None:
        return _pack(stages, halted_at, sp, t_all, n_target)

    # ⑦ GDS（可关：大阵列能省 ~2.5s）
    if sp["verify_gds"]:
        if _run("gds", stage_gds, n_use, row_layer, w_um, py_um,
                lay["n_elements"]) is None:
            return _pack(stages, halted_at, sp, t_all, n_target)
    else:
        stages.append({"stage": "gds", "ok": False, "status": "DISABLED",
                       "metrics": {}, "verdict": "`verify_gds=False` ⇒ 未导出",
                       "elapsed_s": 0.0})
        halted_at = "gds"        # 关掉也算"没跑通" ⇒ flow_ok=False（不许静默当通过）
        for nm in ("report",):
            stages.append(_skip(nm, halted_at))
        return _pack(stages, halted_at, sp, t_all, n_target)

    # ⑧ 汇总
    _run("report", stage_report, n_use, row_layer, g_typ, sp["adc_anchor"],
         sp["share_k"], sp["bits"], sp["target_fj_per_op"],
         lay["area_mm2"], lay["n_via"], lay["n_via_in_path"], base_n, base_area,
         lay["params"]["pitch_y_um"])

    return _pack(stages, halted_at, sp, t_all, n_target)


def _pack(stages: List[Dict], halted_at: Optional[str],
          spec: Dict, t_all: float, n_target: Optional[int]) -> Dict:
    """把 Stage 列表打包成流程结果（含反向完备判定）。

    🔴 **必须补齐未执行的 Stage**（本段实测抓到的缺陷）：
    `run_flow` 在某步 FAIL 时**直接 return**，后面那些 Step **根本不会被 append** ⇒
    报告里只看到 1 步 FAIL，读者不知道流程截断了多少。
    「停下」不等于「报告完整」—— 未跑的步骤必须显式标 `SKIPPED` 才能算诚实。
    """
    import time
    if halted_at is not None:
        seen = {s["stage"] for s in stages}
        for nm in STAGES:
            if nm not in seen:
                stages.append(_skip(nm, halted_at))
        stages.sort(key=lambda s: STAGES.index(s["stage"]))

    done = [s for s in stages if s["status"] == "PASS"]
    names_done = {s["stage"] for s in done}
    missing = [s for s in STAGES if s not in names_done]
    flow_ok = (halted_at is None) and (len(names_done) == len(STAGES))
    rep_stage = next((s for s in stages if s["stage"] == "report"), None)
    return {
        "stages": stages,
        "stage_names": list(STAGES),
        "halted_at": halted_at,
        "stages_completed": len(names_done),
        "stages_total": len(STAGES),
        "missing_stages": missing,
        "flow_ok": flow_ok,
        "n_completed_ok": len(names_done) == len(STAGES),
        "spec": {k: spec[k] for k in ("budget_pct", "target_fj_per_op", "bits",
                                      "share_k", "adc_anchor")},
        "n_target": n_target,
        "report": (rep_stage["metrics"] if rep_stage and rep_stage["ok"] else None),
        # 🔴 必须减起点：`t_all` 是 `perf_counter()` 的**读数**（开机以来的秒数，
        #   本机可能是 16621），不是耗时。v0.9.329 第一版直接 `round(t_all, 3)`
        #   ⇒ 报告写「16621.5 s」，而实跑 9.3 s（**差 1787×**）。
        "elapsed_s": round(time.perf_counter() - t_all, 3),
        "tier": TIER,
        "verdict": ("🔴 **全链跑通**：%d/%d 步 PASS（device→scale→stack→layout→drc→lvs→gds→report）"
                    % (len(names_done), len(STAGES)) if flow_ok else
                    "🔴 **流程在 `%s` 停下**：%d/%d 步 PASS · 未跑：%s"
                    % (halted_at, len(names_done), len(STAGES),
                       ",".join(missing) if missing else "—")),
    }


# ---------------------------------------------------------------------------
# 流程级机核（这是本段区别于"手写脚本"的地方）
# ---------------------------------------------------------------------------
def report_text(flow: Optional[Dict] = None) -> str:
    """把流程结果渲染成**人可读的签核报告**（Markdown）。

    🔴 报告必须显式带三类信息，缺一即读者无法判断可信度：
    ① 每步 status（PASS/FAIL/SKIPPED）② 每个数字的 basis + claimable ③ 停点与未跑步
    """
    f = flow or run_flow()
    L: List[str] = []
    L.append("# LDA 电子计算 SOC · 端到端签核报告")
    L.append("")
    L.append("> 输出档 **%s** · 无流片、无 PDK · **DRC/LVS 过 ≠ 可制造**" % f["tier"])
    L.append("")
    L.append("## 规格")
    L.append("")
    for k, v in f["spec"].items():
        L.append("- `%s` = %s" % (k, v))
    L.append("")
    L.append("## 流程（%d/%d 步）" % (f["stages_completed"], f["stages_total"]))
    L.append("")
    L.append("| # | Stage | 职责 | 状态 | 耗时 | 结论 |")
    L.append("|---|---|---|---|---|---|")
    for i, s in enumerate(f["stages"], 1):
        L.append("| %d | `%s` | %s | **%s** | %.2fs | %s |"
                 % (i, s["stage"], STAGE_ROLE.get(s["stage"], ""),
                    s["status"], s["elapsed_s"], s["verdict"]))
    L.append("")
    if f["halted_at"]:
        L.append("🔴 **流程停在 `%s`**；未执行：%s"
                 % (f["halted_at"], ", ".join(f["missing_stages"]) or "—"))
        L.append("")
    rep = f["report"]
    if rep:
        L.append("## 结果（每个数字带口径）")
        L.append("")
        L.append("| 量 | 值 | basis | 可对外 | 说明 |")
        L.append("|---|---|---|---|---|")
        for m in rep["energy_metrics"] + rep["area_metrics"]:
            val = m["value"]
            vs = ("%.4g" % val) if isinstance(val, float) else str(val)
            L.append("| `%s` | %s | %s | %s | %s |"
                     % (m["name"], vs, m["basis"],
                        "✅" if m["claimable"] else "🔴 否", m["note"]))
        L.append("")
        L.append("🔴 **对外只允许引用 `claimable=True` 的那几行**。"
                 "`energy_per_op_fj_selfcalc` 与 `area_total_ratio` **都不可对外** —— "
                 "前者是下界（E25 判），后者含规模收益（E28/E31 口径混用）。")
        L.append("")
        L.append("## 未建模项（必须与结果同屏）")
        L.append("")
        L.append("- %s" % rep["via_yield_risk"]["note"])
        L.append("- ADC 能耗的实测锚只覆盖 ADC 子模块，**不是 CIM 芯片能效锚**（E25 边界）")
        L.append("- 无 CMP / OPC / 天线 / 密度规则；DRC/LVS 通过**不等于**可制造")
    L.append("")
    L.append("## 流程结论")
    L.append("")
    L.append(f["verdict"])
    return "\n".join(L)


def flow_parity(flow_a: Dict, flow_b: Dict) -> Dict:
    """**可复现性对拍**：两次跑必须给出**逐位相同**的 metrics（时间字段除外）。

    🔴 为什么这条重要：流程编排最容易引入"隐式顺序依赖"（缓存命中顺序、
    集合遍历顺序、浮点累加顺序）。两次跑一致是最便宜、也最有效的检测。
    """
    def _strip(f: Dict) -> Dict:
        out = []
        for s in f["stages"]:
            out.append((s["stage"], s["status"],
                        tuple(sorted((k, repr(v)) for k, v in s["metrics"].items()))))
        return tuple(out)

    a, b = _strip(flow_a), _strip(flow_b)
    diffs = []
    for (na, sa, ma), (nb, sb, mb) in zip(a, b):
        if na != nb or sa != sb:
            diffs.append("%s: status %s→%s" % (na, sa, sb))
        elif ma != mb:
            ka = {k: v for k, v in ma}
            kb = {k: v for k, v in mb}
            keys = sorted(set(ka) | set(kb))
            bad = [k for k in keys if ka.get(k) != kb.get(k)]
            diffs.append("%s: metrics 差 %s" % (na, ",".join(bad[:4])))
    return {"identical": (a == b) and not diffs,
            "n_stages": len(a), "diffs": diffs,
            "verdict": ("🔴 两次跑 **逐位一致**（%d 步）" % len(a) if not diffs else
                        "🔴 **不可复现**：%s" % "；".join(diffs[:4]))}


def fail_semantics_check() -> List[Dict]:
    """**fail vs 未达标** 的语义机核：4 个场景，逐一验证「该停的停、不该停的不停」。

    这是本模块最容易被做错的地方 —— 把「差距」当「失败」，或把「失败」当「未达标」。
    v0.9.329 第一版就错了：把 `recommend_family(target_fj)` 放在第 ① 步，
    默认目标 8.3 fJ/op（低于任何族地板）让流程**第 1 步就 fail**。
    """
    rows: List[Dict] = []

    # ① 真物理不可行：要 10 bit/cell，而所有族最多 8 ⇒ device 必须 FAIL
    f = run_flow(spec={"bits": 10})
    rows.append({"case": "需求 10 bit/cell（所有族最多 8）",
                 "expect": "device FAIL", "halted_at": f["halted_at"],
                 "flow_ok": f["flow_ok"], "detail": f["verdict"][:56],
                 "ok": f["halted_at"] == "device" and not f["flow_ok"]})

    # ② 预算过紧：0.1% ⇒ 基线 < MIN_N ⇒ scale 或 stack 必须 FAIL
    f = run_flow(spec={"budget_pct": 0.1})
    rows.append({"case": "预算 0.1%（基线 < MIN_N）",
                 "expect": "scale/stack FAIL", "halted_at": f["halted_at"],
                 "flow_ok": f["flow_ok"], "detail": f["verdict"][:56],
                 "ok": f["halted_at"] in ("scale", "stack") and not f["flow_ok"]})

    # ③ 🔴 目标远低于物理地板 ⇒ **不许 fail**（这是差距，不是不可行）
    f = run_flow(n_target=12, spec={"target_fj_per_op": 1.0})
    rep = f["report"]
    rows.append({"case": "目标 1.0 fJ/op（远低于任何族地板）",
                 "expect": "不 fail · vs_target ≫ 1", "halted_at": f["halted_at"],
                 "flow_ok": f["flow_ok"],
                 "detail": ("vs_target=%.1f×" % rep["vs_target"]) if rep else "无 report",
                 "ok": f["flow_ok"] and rep is not None and rep["vs_target"] > 10.0})

    # ④ 目标宽松 ⇒ 达标，且不许因为「达标了」就跳过任何步骤
    f = run_flow(n_target=12, spec={"target_fj_per_op": 500.0})
    rep = f["report"]
    rows.append({"case": "目标 500 fJ/op（宽松 ⇒ 达标）",
                 "expect": "flow_ok 且 vs_target < 1", "halted_at": f["halted_at"],
                 "flow_ok": f["flow_ok"],
                 "detail": ("vs_target=%.2f×" % rep["vs_target"]) if rep else "无 report",
                 "ok": f["flow_ok"] and rep is not None and rep["vs_target"] < 1.0})
    return rows


# ---------------------------------------------------------------------------
# 披露
# ---------------------------------------------------------------------------
SOC_FLOW_DISCLOSURE = {
    "what": "把 E20–E32 十三段串成 8 步可执行流程（device→scale→stack→layout→drc→lvs→gds→report），"
            "fail-fast + 每数字带 basis/claimable + 可复现对拍",
    "why_not_script": "手写脚本只能证明「跑过」；本模块把三件事变成机核："
                      "① 少一步就不算跑通（反向完备）② 每个数字哪个能对外（basis/claimable）"
                      "③ 两次跑逐位一致（无隐式顺序依赖）",
    "fixed_by_this_module": [
        "面积口径混用：best_layer 报「×74.28」= 规模 52.56×（收益）× 换层 1.41×（代价）"
        "⇒ 拆成 area_same_n_ratio(1.33, 代价) 与 area_total_ratio(含规模, 不可当代价)",
        "能效双口径：energy 自算 7.555 fJ/op（下界）⟷ adc_calibration 实测锚 24.717 fJ/op（可信），"
        "差 3.27× ⇒ 只有后者 claimable",
    ],
    "not_a_chip": "产物是**设计期签核报告**，不是流片芯片；DRC/LVS 过 ≠ 可制造（无 CMP/OPC/天线/密度）",
    "not_a_yield_model": "漏极通路 6 个串联 via × 单元数 = 45,414 个串联节点（N=87）的良率完全未建模（1 ppm/节点 ⇒ ~4.5% 失效）",
    "no_digital_shell": "🔴 流程里**没有数字控制壳**（E21 三红线第二条「数字链借不借」至今未决）"
                        "⇒ 这是 CIM 阵列的签核，不是 SoC 的签核",
    "fail_vs_shortfall": "fail 只留给物理/工具不可行；未达能效目标不算 fail（那是差距）",
    "tier": TIER,
}


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def soc_flow_self_check(verbose: bool = False) -> bool:
    """流程级自检。**每次都要真跑流程**（不是读缓存）—— 流程的价值就在"跑过"。"""
    checks: List[tuple] = []

    def chk(name: str, cond: bool, detail: str = "") -> bool:
        checks.append((bool(cond), name, detail))
        if verbose:
            print(("[OK] " if cond else "[NG] ") + name + (("  :: " + detail) if detail else ""))
        return bool(cond)

    ok = True

    # ① Stage 序列与职责表必须一一对应（防加了 Stage 忘记写职责）
    ok &= chk("① Stage 序列 %d 步，与职责表一一对应" % len(STAGES),
              len(STAGES) == 8 and set(STAGES) == set(STAGE_ROLE))

    # ② 完整流程真跑通（小规模 · 关 GDS 省时）
    f = run_flow(n_target=12, verify_gds=False)
    # 关 GDS ⇒ device/scale/stack/layout/drc/lvs 共 **6** 步 PASS，
    #   gds 标 DISABLED（不算 PASS）、report 标 SKIPPED
    ok &= chk("② 🔴 关 GDS ⇒ 6/8 PASS · 停在 gds（关掉也必须算「没跑通」，不许静默当通过）",
              f["halted_at"] == "gds" and f["stages_completed"] == 6,
              "completed=%d/8 · halted=%s" % (f["stages_completed"], f["halted_at"]))

    # ③ 开 GDS 必须 8/8 全通
    f_full = run_flow(n_target=12)
    ok &= chk("③ 🔴 开 GDS ⇒ **8/8 全 PASS**（flow_ok=True）",
              f_full["flow_ok"] and f_full["stages_completed"] == 8,
              "%d/8 · halted=%s" % (f_full["stages_completed"], f_full["halted_at"]))

    # ④ 反向完备：少一步必须 flow_ok=False
    ok &= chk("④ 反向完备：关 GDS 后 `flow_ok` 必为 False（不许静默当通过）",
              run_flow(n_target=12, verify_gds=False)["flow_ok"] is False)

    # ⑤ fail-fast：某步 fail ⇒ 后续全 SKIPPED
    #   🔴 场景必须是**真物理不可行**（bits=10 > 所有族的 8），
    #   不能用"目标太严"—— 那是差距，不该让流程停（见 `fail_semantics_check` 场景 ③）
    fb = run_flow(spec={"bits": 10})
    skipped = [s for s in fb["stages"] if s["status"] == "SKIPPED"]
    ok &= chk("⑤ 🔴 fail-fast + 报告完整：device FAIL（bits=10 无族可达）⇒ "
              "后续 %d 步**全部显式标 SKIPPED**（停下 ≠ 报告可以缺步）" % len(skipped),
              fb["halted_at"] == "device" and len(skipped) == 7
              and len(fb["stages"]) == len(STAGES))

    # ⑥ 可复现：两次跑逐位一致
    fa = run_flow(n_target=12, verify_gds=False)
    fb2 = run_flow(n_target=12, verify_gds=False)
    par = flow_parity(fa, fb2)
    ok &= chk("⑥ 🔴 可复现：同一规格跑两次 **metrics 逐位一致**", par["identical"],
              par["verdict"][:70])

    # ⑦ 能效双口径：自算必须 < 可信，且自算不可 claimable
    rep = f_full["report"]
    m_claim = [m for m in rep["energy_metrics"] if m["claimable"]]
    m_self = [m for m in rep["energy_metrics"] if not m["claimable"]]
    ok &= chk("⑦ 🔴 能效双口径：claimable 只有 1 个（实测锚）· 自算标不可对外 · "
              "自算(%.2f) < 可信(%.2f)"
              % (m_self[0]["value"], m_claim[0]["value"]),
              len(m_claim) == 1 and len(m_self) == 1
              and m_self[0]["value"] < m_claim[0]["value"])

    # ⑧ 面积双口径：必须用**规模差明显**的案例（12→48），否则 base_n==n_use
    #   ⇒ 规模因子=1 ⇒ 两个口径数值几乎相等，判据退化成"比较自己"
    #   （v0.9.329 第一版用 n_target=12 跑，正好踩到这个退化）
    f_scale = run_flow(n_target=48)      # 必须开 GDS，否则 report 步 SKIPPED ⇒ 无 area_metrics
    rep_s = f_scale["report"]
    a_claim = [m for m in rep_s["area_metrics"] if m["name"] == "area_same_n_ratio"][0]
    a_total = [m for m in rep_s["area_metrics"] if m["name"] == "area_total_ratio"][0]
    ok &= chk("⑧ 🔴 面积双口径分离（N 12→48）：同 N 代价 ×%.2f（claimable）⟷ 总比 ×%.1f"
              "（不可当代价 · 差 %.1f× 全是规模因子）"
              % (a_claim["value"], a_total["value"], a_total["value"] / a_claim["value"]),
              a_claim["claimable"] is True and a_total["claimable"] is False
              and a_total["value"] / a_claim["value"] > 10.0)

    # ⑨ GDS 完备性：flat ≡ 几何元素数（防"进了 DRC 没进文件"）
    g_stage = [s for s in f_full["stages"] if s["stage"] == "gds"][0]
    ok &= chk("⑨ 🔴 GDS 完备：flat %s ≡ 几何元素数 · roundtrip match"
              % format(g_stage["metrics"]["flat_elements"], ","),
              g_stage["metrics"]["flat_elements"] == g_stage["metrics"]["n_elements_expected"]
              and g_stage["metrics"]["roundtrip_match"])

    # ⑨b via 双口径：串联数（良率用）必须 < 几何图元数（含单元自带源极 via）
    ly_m = [s for s in f_full["stages"] if s["stage"] == "layout"][0]["metrics"]
    ok &= chk("⑨b 🔴 via 双口径分离：串联 **%d 个/单元**（良率用）< 几何图元 %.0f 个/单元"
              % (ly_m["n_via_in_path"], ly_m["n_via_geom"] / float(ly_m["n"] ** 2)),
              ly_m["n_via_in_path"] == 6
              and ly_m["n_via_geom"] > ly_m["n_via_in_path"] * ly_m["n"] ** 2,
              "几何每单元 %.2f 个（含单元自带源极 VIA1）"
              % (ly_m["n_via_geom"] / float(ly_m["n"] ** 2)))

    # ⑩ fail vs 未达标 的语义
    rows = fail_semantics_check()
    bad = [r for r in rows if not r["ok"]]
    ok &= chk("⑩ 🔴 fail 与「未达标」分离（%d 场景：该停的停、不该停的不停）" % len(rows),
              not bad, "；".join(r["case"] for r in bad) if bad else "")

    # ⑪ 报告渲染：必须含"不可对外"的警告
    txt = report_text(f_full)
    ok &= chk("⑪ 报告含三类必备信息（status / basis / claimable）+ 不可对外警告",
              "claimable" in txt and "不可对外" in txt
              and txt.count("| **PASS** |") >= 6)

    # ⑫ 披露：必须承认"没有数字壳"
    ok &= chk("⑫ 🔴 披露明写「流程里没有数字控制壳」（这是 CIM 阵列签核，不是 SoC 签核）",
              "没有数字控制壳" in SOC_FLOW_DISCLOSURE["no_digital_shell"])

    npass = sum(1 for c, _, _ in checks if c)
    if verbose:
        print()
        print("MODE=%s 合计 %d 判据 · PASS %d / FAIL %d"
              % (TIER, len(checks), npass, len(checks) - npass))
    return ok


__all__ = ["STAGES", "STAGE_ROLE", "SPEC_DEFAULT", "MIN_N",
           "stage_device", "stage_scale", "stage_stack", "stage_layout",
           "stage_drc", "stage_lvs", "stage_gds", "stage_report",
           "run_flow", "report_text", "flow_parity", "fail_semantics_check",
           "soc_flow_self_check", "SOC_FLOW_DISCLOSURE"]
