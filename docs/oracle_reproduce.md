# 外部 ORACLE（Meep）复现指南

> 版本：v0.9.1（2026-08-30）· 脚本：`scripts/setup_oracle_env.sh`
> 目的：把「双 ground 交叉验证」从声明变成**外部可现场复现**的事实
> 红线：Meep 为 GPL 软件，必须装在隔离环境，绝不并入本仓库（MIT 纯净）

---

## 一、为什么需要这个

LDA 的核心主张是「AI 写求解器、但 LLM 不进判决路径」，判决落在**非 AI ground** 上。
要让外部技术买家信服，光有声明不够——得让他能亲手跑一遍对照。

### 当前状态（2026-08-30 实测）

| 题 | 离线 ORACLE | 外部 Meep 对照 |
|---|---|---|
| **B5** Y 分支插损 | ✅ `numpy-overlap-offline` = **3.9 dB** | 待接入 |
| **B7** 波导交叉串扰 | ✅ `numpy-fdtd-offline` = **-10.08 dB** | 待接入 |
| **B6** 光栅耦合效率 | ❌ 返回 None（Tidy3D 预留，需 API key） | 待接入 |

**一个需要说清的关键点**：B5/B7 在离线状态下**是通的**——LDA 自研的 numpy 求解器能给出场级真值。
但这两者都属于**自证**（自研求解器验证自研求解器）。

真正缺的是**外部独立对照**。Meep 是业界公认的开源 FDTD 参照实现，用它跑同一几何、
比对两者结果，才能把「自证」升级为「互证」——这正是本脚本要打通的链路。

---

## 二、一键安装

```bash
bash scripts/setup_oracle_env.sh
```

脚本会自动探测 conda / mamba / micromamba / docker，创建**隔离环境**并装 `pymeep`。

### 指定方式

```bash
# 指定安装方式
bash scripts/setup_oracle_env.sh --method conda
bash scripts/setup_oracle_env.sh --method docker

# 已有装好 Meep 的环境，直接指定解释器
bash scripts/setup_oracle_env.sh --method manual --meep-py /path/to/venv/bin/python

# 只跑自测（环境已装好时）
bash scripts/setup_oracle_env.sh --self-test-only --meep-py /path/to/python
```

### 完成后

脚本会生成 `.oracle_env`（**不入库**，含本机绝对路径）：

```bash
source .oracle_env     # export LDA_MEEP_PY=/path/to/isolated/python
```

---

## 三、验证步骤

### 步骤 1：确认外部 ORACLE 返回真值

```bash
source .oracle_env
python lda/ext_oracle/meep_oracle.py \
  --bid B7 \
  --params '{"w_core":0.4,"h_core":0.22,"n_si":3.48,"n_clad":1.44,"wl":1.55}' \
  --json
```

**预期输出**（字段结构；数值以实际 Meep 版本为准）：

```json
{"value": -2x.xx, "source": "meep-2d-fdtd", "note": "Meep 2D FDTD 场级真值…"}
```

判据：`value` 不为 `null`，且 `source` 含 `meep`。

### 步骤 2：与 LDA 离线结果对照（这就是「互证」）

```bash
source .oracle_env
cd lda && python -c "
from lda_harness.oracle_field import resolve_field_oracle
p = {'w_core':0.4,'h_core':0.22,'n_si':3.48,'n_clad':1.44,'wl':1.55}
print('B7 离线(自研 numpy):', resolve_field_oracle('B7', p))
"
```

对照基线（未配 Meep 时）：

| 题 | 离线自研值 | 来源 |
|---|---|---|
| B7 | **-10.083406 dB** | `numpy-fdtd-offline` |
| B5 | **3.9 dB** | `numpy-overlap-offline` |

配好 Meep 后，`resolve_field_oracle` 会优先走子进程调用 Meep（返回值 `source` 含 `meep`），
此时即可把两者并列——**这是给外部验货者看的对照表**。

### 步骤 3：跑锚回归确认未破

```bash
source .oracle_env
python lda/run_harness.py     # 应 47/47 通过
```

---

## 四、红线：为什么必须隔离

Meep 采用 **GPL** 许可，而 LDA 主仓库是 **MIT**。按项目主权依赖政策：

- Meep 属于 **B 级「借今踢后」**依赖——可以借来做真值对照，但绝不并入
- 它**只能**存在于隔离环境，通过子进程 JSON 契约调用
- LDA 主环境、依赖清单、源码树中**不得出现任何 Meep 代码或依赖**

调用契约保证了这一点：

```
LDA 主进程  --(subprocess + JSON)-->  meep_oracle.py  --(import meep)-->  隔离环境
                    ↑
        只传 JSON 参数、只收 JSON 结果，无代码耦合
```

即使隔离环境不存在，LDA 也只会优雅降级到离线自研求解器，`return None` 而非崩溃。

---

## 五、诚实边界与实测状态（2026-08-30 更新）

### 本机实测结论（Windows 开发机）
- **离线 numpy 真值链路已本机验证通过**（用本地 CI venv + numpy 实跑 `oracle_field.resolve_field_oracle`）：
  - B7 波导交叉串扰 = **-10.083406 dB**（`source=numpy-fdtd-offline`），与本文档第三节基线一致
  - B5 Y 分支插损 = **3.9 dB**（`source=numpy-overlap-offline`）
  - → **离线 ground 确认活着、数值可复现**，这是「双 ground」中自研侧的可演示部分。
- **外部 Meep 真值 + 互证：本机无法验证**。已实证限制：
  - `pip install meep-base` → `Could not find a version that satisfies the requirement (from versions: none)`（PyPI 无 Windows 兼容的 Meep 编译扩展 wheel）
  - WSL 被本机安全策略禁用；Docker Desktop 引擎管道未运行（CLI 在但 daemon 不可达）；无 conda/mamba/micromamba
  - → 本台 Windows 开发机物理上跑不了 Meep，**端到端 meep 互证需在 Linux/WSL/Docker 可用环境执行**。

### P0-3 真实交付状态
- ✅ 一键脚本 `scripts/setup_oracle_env.sh`（conda/mamba/micromamba/manual 探测 + 自测 + 写 `.oracle_env`）逻辑完整
- ✅ `meep_oracle.py` 真值实现完整：B5/B7 的 Meep 2D-FDTD 求解已写好（非占位），B6 预留 Tidy3D
- ✅ `oracle_field.py` 子进程集成契约经代码审查 + 离线降级实测正确
- ✅ 离线 numpy 真值本机实测可复现（见上）
- ⚠️ **外部 Meep 真值 + 互证**：待在 Linux/WSL/Docker 环境按计划执行（见第二节）。验证者无需改任何代码，跑通即接通。

### 其余边界
1. **B6 光栅耦合仍不可用**：`_sim_grating` 目前是 `return None` 占位，预留 Tidy3D（3D 求解，需 API key）。
2. **Meep 版本差异**：不同 Meep 版本的场级结果可能有数值差异，对照时记录 Meep 版本号，判据用相对偏差而非绝对等值。
3. **B5/B7 离线值属自研性质**：它们是 LDA 自研 numpy 求解器的输出；引入 Meep 对照后才构成「互证」——这也是本脚本存在的全部意义。

---

## 六、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 提示未检测到 conda/mamba/docker | 无任何可用环境管理器 | 先装 [micromamba](https://mamba.readthedocs.io/)（最轻量），或 `--method manual` 指定已有环境 |
| 自测 1 失败「无法 import meep」 | 指定的解释器没装 meep | 换解释器路径，或先用 conda 方式装 |
| ORACLE 返回 `value: null` | B7 实现未取到真值 | 检查 `meep_oracle.py` 的 `_sim_crossing`，或看是否命中 B6（B6 本就返回 null） |
| 装到一半超时 | pymeep 包较大（数百 MB） | 换 conda-forge 镜像源，或改用 Docker 镜像 |
