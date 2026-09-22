# 幅度均衡 PDK 绑定框架（D1 联动，主权光子计算投产前置）

**日期**：2026-09-22 ｜ **模块**：`lda/lda_layout/mesh_pnr.py`（`amplitude_equalization_manifest`）
**路线**：B+C 自研（主权光电接口 + light-EIC 光子核）｜ **来源**：D3 收官用户指令「把幅度均衡 PDK 的绑定框架搭出来」
**红线**：A 级永不外借 · C 级自主零依赖 · LLM 不进判决路径 · 零外部求解器依赖。

---

## 一、裁定（结论先行）

D1 已证明 grid2d 总线传播损耗 + 抽头插入损耗随 N **线性增长**，且**方差由抽头损耗主导**
（≈9–10× 传播项），相位校准无法补偿幅度失衡 ⇒ 有效传输矩阵偏离酉 ⇒ 重构保真度塌方。
本框架把 D1 的**参数化损耗预算**绑定为**每输出端口可执行的幅度均衡 PDK 需求**：

- 新增 `amplitude_equalization_manifest(build_result, pdk) -> dict`：从 grid2d 真实几何
  （总线长 `x_max_um`、列距 `pitch_um`、每轨抽头度 `deg[k]` 由 `ops` 累积）按 D1 损耗模型
  估算每端口被动损耗，以最弱端口为参考算出每端口需衰减量，输出判定。
- `build_mesh_pnr(..., pdk=pdk)` 已挂该 manifest（返回 dict 键 `amplitude_eq`），
  主权版图 build 与 PDK 需求**一次产出**。
- 判定与 D1 §六规模建议**逐字一致**：N≤128 免幅度均衡（α_prop≤2+α_tap≤0.02）；
  N=256 需 α_tap≤0.01 + 评估均衡；N=512 必幅度均衡（见 §四 实测表）。

**不阻塞布局**：幅度均衡属 **P2 PDK**（逐 MZI 可变衰减器 / 幅度感知标定，V→幅度闭环），
是投产工艺层事项；grid2d 主权 P&R（酉分解/版级保真度/DRC/LVS）正确性不受损。

---

## 二、函数接口（mesh_pnr.py）

```python
def amplitude_equalization_manifest(build_result: dict, pdk: dict) -> dict:
    """D1 总线损耗 → 每端口幅度均衡 PDK 需求。"""
    # build_result: build_mesh_pnr 返回 dict（取 N / ops / x_max_um / pitch_um）
    # pdk: {alpha_prop_db_cm, alpha_tap_db, eq_threshold_db=3.0, eq_range_db=20.0}
    # 返回: {per_port:[{port,k,L_path_um,n_tap,IL_db,IL_linear,att_db,needs_eq}],
    #        IL_var_ports, IL_var_io, IL_var_binding, eq_required, eq_feasible, verdict, ...}
```

**模型（直总线 · 所有端口 L_path=L_bus，方差来自每轨抽头度展布）**
```
IL_k      = alpha_prop · L_bus/1e4 + deg[k]·alpha_tap      (dB)
att_k     = IL_ref − IL_k   (IL_ref = max IL_k，最弱端口为参考；强端口衰减至最弱 ⇒ 恢复酉性)
IL_var_p  = max IL_k − min IL_k                            (每端口失衡，直总线模型)
IL_var_io = D1 保守 io_pair (全路 L_bus+⟨deg⟩抽头 vs 最短 col_pitch+1抽头)
IL_var_b  = max(IL_var_p, IL_var_io)                       (取保守)
verdict   = 'phase_only'            if IL_var_b ≤ eq_threshold
          = 'requires_amp_eq_pdk'   elif max att ≤ eq_range
          = 'amp_eq_infeasible'      else (均衡器动态范围不足)
```
- `deg[k]`：端口 k 所在轨被多少 MZI 耦合（每 MZI 耦 rails j,j+1 各 +1），直总线穿越抽头数。
- `eq_range_db`：均衡器（VOA / MZI 可变衰减器）动态范围，默认 20 dB。

**集成**：`build_mesh_pnr(U_target, layout_mode='grid2d', pdk=pdk)` 返回 dict 含
`amplitude_eq`（未传 `pdk` 时为 `None`，零开销）。

---

## 三、复算脚本与产物

| 文件 | 内容 |
|------|------|
| `examples/budget_amp_eq_pdk.py` | 三场景（A/B/C）× 五规模（4/16/128/256/512）判定 + 每端口明细 |
| `examples/_amp_eq_pdk_out.txt` | 判定表（stdout 落盘） |
| `examples/amp_eq_pdk_summary.csv` | 汇总（每行一 (N,场景)：IL/方差/req/feas/verdict） |
| `examples/amp_eq_pdk_N256_B_detail.csv` | N=256 场景 B 每端口 att_db 分布（边际案例） |

复算：`python examples/budget_amp_eq_pdk.py`（需 `D:/agent_LDA/lda` 在 sys.path）。

---

## 四、实测判定表（D1 三场景 × N=4..512）

```
   N scn a_prop  a_tap  ILmean   var_p  var_io   var_b  maxatt  req? feas?              verdict
   4   A    1.0  0.020    0.07    0.04    0.05    0.05    0.04 False  True           phase_only
  16   A    1.0  0.020    0.36    0.16    0.33    0.33    0.16 False  True           phase_only
 128   A    1.0  0.020    3.00    1.28    2.97    2.97    1.28 False  True           phase_only   ← N≤128 安全区
  16   B    2.0  0.050    0.86    0.40    0.80    0.80    0.40 False  True           phase_only
 128   B    2.0  0.050    7.26    3.20    7.20    7.20    3.20  True  True  requires_amp_eq_pdk
  16   C    3.0  0.100    1.67    0.80    1.56    1.56    0.80 False  True           phase_only
 128   C    3.0  0.100   14.07    6.40   13.96   13.96    6.40  True  True  requires_amp_eq_pdk
 256   A    1.0  0.020    6.01    2.56    5.99    5.99    2.56  True  True  requires_amp_eq_pdk   ← 需 α_tap≤0.01+均衡
 256   B    2.0  0.050   14.57    6.40   14.51   14.51    6.40  True  True  requires_amp_eq_pdk
 256   C    3.0  0.100   28.23   12.80   28.12   28.12   12.80  True  True  requires_amp_eq_pdk
 512   A    1.0  0.020   12.04    5.12   12.02   12.02    5.12  True  True  requires_amp_eq_pdk   ← 必幅度均衡
 512   B    2.0  0.050   29.19   12.80   29.13   29.13   12.80  True  True  requires_amp_eq_pdk
 512   C    3.0  0.100   56.56   25.60   56.45   56.45   25.60  True False    amp_eq_infeasible   ← 均衡器动态不足
```

**与 D1 §三/§六一致性核对**
- 阈值 `eq_threshold=3 dB`（D1 §四：「IL_var > ~3 dB 即进入需幅度均衡区」）⇒ `var_b` 越阈即 `requires_amp_eq_pdk`，完全对齐。
- N=128 场景 A（α_tap=0.02）`var_b=2.97 < 3` ⇒ `phase_only`，与 D1「N≤128 可流片（α_prop≤2+α_tap≤0.02）」一致。
- N=256 场景 A `var_b=5.99 > 3` ⇒ `requires_amp_eq_pdk`，与 D1「256 需 α_tap≤0.01 + 评估幅度均衡」一致（优耦合器把 var 压到 ~3.7 dB 仍临界）。
- N=512 场景 C `max_att=25.6 > 20` ⇒ `amp_eq_infeasible`：劣耦合器 + 512 超出 20 dB 均衡器动态 ⇒ 须换绝热耦合器（α_tap≤0.01）方可均衡，正是 D1「512 必须幅度均衡」的边界条件。

---

## 五、诚实边界（防纸糊楼）

1. **L3 参数化估算**：每端口 IL 用直总线模型（所有端口 L_path=L_bus，方差来自 `deg` 展布×α_tap）；
   `IL_var_io` 另计 D1 保守 io_pair 传播项。二者取大作绑定指标，偏保守。
2. **未含项**：弯曲损耗（直总线极少）、模场失配、偏振/温度漂移、热串扰（见 D2）、截面散射；
   不推翻「线性随 N + 抽头主导」结论，只微调常数。
3. **真值须 foundry 回填**：α_prop / α_tap 取公开区间代表值；幅度均衡器（`eq_range`）为工艺指标，
   真值由 foundry PDK + 圆片表征（弯曲/截面/耦合器实测 IL）回填。
4. **框架不阻塞布局主权 P&R**：输出的是「投产 PDK 需求清单」，不是版图修改；grid2d 酉分解/
   版级保真度/DRC/LVS 判决不变。
5. **幅度均衡实现属 P2 PDK**：逐 MZI 可变衰减器（VOA）/ 幅度感知标定（V→幅度闭环）为后续工艺层，
   本框架只产出需求与判定，不实现硬件。

---

## 六、与系列报告联动

- **D1**（总线损耗预算）：本框架是 D1 §六「缓解与路线图」中「幅度均衡」杠杆的**可执行绑定**。
- **D2**（热串扰）：幅度均衡与热串扰标定同属「控制/工艺层」，均不阻塞布局；投产时一并纳入标定流程。
- **D3**（规模再上探）：本框架闭合 D3 §九「D1 幅度均衡 PDK 绑定」开放项——规模天花板由 D1
  （幅度均衡）决定：256/512 主权版图已绿，投产须先有幅度均衡 PDK。
- **收官**：P0+P1-A+P1-B+P1-B续+系统级代价(D1/D2/D3)+幅度均衡 PDK 绑定框架 全链路闭合，
  主权光子计算「编译→版图→系统级代价→投产 PDK 需求」主链路对外可演示。
