# LDA 快速上手（零基础 · 5 步走通）

> **本文每个命令、每行输出都来自真实演练**（干净 `git clone` + 隔离环境实跑，2026-09-23），
> 不是示意。目标：从空目录到**第一个 GDS 版图 + 签核报告**。
> 判据由 `lda/run_p2_usability_smoke.py` 守护（步骤数 ≤5、路径必须真实存在、命令必须与
> CLI 真实子命令一致）。

## 你会得到什么

一条命令产出（实测）：

| 产物 | 说明 |
|---|---|
| `reports/goal_ring_fsr.gds` | GDSII 版图，**3,128 字节** |
| `reports/goal_ring_fsr.signoff.md`（+ `.json`） | 签核报告：判决 **ACCEPT** · DRC 3/3 · LVS **ACCEPT** 2/2 |
| `reports/goal_ring_fsr.design_packages.json` | 逐器件的设计参数（引擎闭环解出的） |

**耗时参考**：clone 与装依赖各约 1 分钟；**命令本身实测 1.8 秒**。

**运行前提**：纯 `numpy` + `scipy` 即可 —— **不联网、不需要 GPU、不需要商业许可证**。

## 前置

- **Python 3.12 或以上**（本项目在 3.13 上开发与验收）
- 三个运行时依赖：`numpy` `scipy` `jsonschema`（步骤 2 自动装）
- 磁盘：仓库约 51 MB（其中示例版图 30 MB）；生成物 KB 级

---

## 步骤 1 · 拿到代码

```bash
git clone https://github.com/iduyuhe/LDA.git
cd LDA
```

预期：克隆约 1,130 个文件。`git rev-parse --short HEAD` 会打印当前提交号。
国外网络不畅时可用 Gitee 镜像：`https://gitee.com/i4hub/LDA`。

## 步骤 2 · 准备 Python 环境（两条路，任选其一）

**路 A（推荐 · 需要联网）** —— 装依赖并生成 `lda` 命令：

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/lda --help
```

Windows 用 `.venv/Scripts/…`；Linux / macOS 换成 `.venv/bin/…`。

**路 B（零安装 · 离线可用）** —— 若你的解释器已经装了 `numpy` `scipy` `jsonschema`，
**什么都不用装**，直接跑源码里的入口（它会自己把包根加进 `sys.path`）：

```bash
python lda/lda_design/cli.py --help
```

两条路的预期输出相同（实测）：

```
usage: lda [-h] {design,check,build,gf,report} ...
  design   跑一个器件设计闭环，输出最优已验证候选
  check    把链路 JSON 装配成版图，输出 DRC/LVS 双闸报告 + GDS；或导入 GDSII 做主权几何 DRC
  build    一句话目标 → 设计包 → 版图 → GDS + DRC/LVS 签核（端到端单命令 · M1）
  gf       gdsfactory 组件 → LDA 链路 spec（生态互通桥，可选依赖）
  report   生成基准对照验证闭环报告
```

> 选路 B 的话，下文所有 `lda <子命令>` 等价替换成 `python lda/lda_design/cli.py <子命令>`。
> `python -m lda_design.cli <子命令>` 也可用（需 `PYTHONPATH` 指向仓库的 `lda/` 目录）。

⚠️ **诚实提醒**：路 A 需要联网——`pip install -e .` 要拉取构建依赖 `setuptools` 与
`numpy/scipy/jsonschema`。实测在**无网环境**它会明确失败（`Could not find a version that
satisfies the requirement setuptools>=61`）——这不是代码缺陷，联网即可；无网请走路 B。

## 步骤 3 · 一条命令出 GDS

```bash
lda build lda/examples/cli_build_goal.json --out reports
```

这一条命令做完四件事：读目标 → 引擎闭环解出器件参数 → 装配版图 → 导 GDS 并做 DRC/LVS 签核。

预期（实测 1.8 秒、退出码 0）关键几行：

```
- **目标**：微环 FSR 目标 17.5nm（参数由引擎闭环解出）+ 前后波导，一条命令出 GDS 并签核
| `ring` | RingResonator | 引擎闭环 | engine_ringresonator | {"R_um": 6.5} | {"R": 6.5} |
## 签核结论
- 判决：**ACCEPT**
- DRC：3/3 器件通过（✅）
- LVS：**ACCEPT** · 2/2 网一致
- GDS：`reports/goal_ring_fsr.gds`（3128 B）· bbox [-5.0, -9.0, 67.8, 9.0] µm · 3 器件 / 5 net
```

忘参数也不要紧：单独敲 `lda build` 会打印用法、最小 `goal.json` 结构、以及当前可桥接的
器件清单，退出码 2 —— **不会静默猜一个目标**。

## 步骤 4 · 看产物

```bash
ls reports
```

预期（实测）：

```
goal_ring_fsr.design_packages.json
goal_ring_fsr.gds
goal_ring_fsr.signoff.json
goal_ring_fsr.signoff.md
provenance_audit.json      # clone 自带（语料溯源审计报告），不是本命令产物
```

打开 `reports/goal_ring_fsr.signoff.md`：里面有逐器件「设计参数 → 版图参数」对照、判决结论，
以及一份**诚实边界**（哪些验证做了、哪些没做）。**先读边界，再读结论。**

## 步骤 5 · 换个目标再跑一次

编辑 `lda/examples/cli_build_goal.json` 里的 `design.target`，或者直接跑单器件设计闭环：

```bash
lda design RingResonator --target 20
```

预期（实测、退出码 0）：

```
# LDA 设计闭环 · 环形谐振器 · 目标 FSR（解析锚，FDTD 抽检需 GPU）
- 目标：20.0 nm （指标：FSR (解析, nm)）
- 搜索 35 候选 · 验证 5 · 通过 5
- **最优候选**（err=0.02000）：
    params: {"R_um": 5.5}
    metric: 19.98
```

到这一步，你已经走完「目标 → 设计 → 版图 → 签核」主干。
改版图参数也行：第 3 步加 `--wg 0.45`（实测可用，波导宽 0.5 → 0.45 µm）。

## 下一步去哪

| 你想做什么 | 去哪 |
|---|---|
| 查 WebUI REST 接口（138 个端点，逐条含参数与鉴权） | `docs/API_REFERENCE.md`（自动生成，勿手改） |
| 配环境变量 / 部署到内网或服务器 | `docs/ENVIRONMENT.md` · `LDA_D-13_WebUI内网部署说明.md` |
| 跑全量回归、提 PR | `CONTRIBUTING.md` |
| 看锚题与验证口径（判断「能不能信」） | `README.md` 顶部账本 |

## 卡住了？

| 现象 | 处理 |
|---|---|
| `pip install -e .` 报找不到 `setuptools` | 无网。联网重试，或改走步骤 2 路 B（零安装） |
| `lda` 命令不存在 | 没执行 `pip install -e .` 或没激活 venv。改用 `python lda/lda_design/cli.py …` |
| 报 `SyntaxError`（跨行 f-string） | 解释器太旧。本项目需 **3.12 或以上** |
| `ModuleNotFoundError: numpy` | 依赖没装：`pip install numpy scipy jsonschema` |

## 诚实边界

1. `lda build` 交付的是**几何 + 可制造性 + 一致性**（GDS / DRC / LVS）；**装配后的整链光学
   性能未做端到端验证** —— 每类器件的「目标→参数」由设计引擎闭环（真实求解器双重验证）负责。
2. DRC 是**主权几何子集**（最小线宽 / 间距 / 面积），不是 foundry 工艺级全量 deck。
3. LVS 的尺寸一致是**代码路径级独立**（版图几何独立测量 vs IR 声明），非物理方法级独立。
4. 目前只有 2 类引擎 kind 通过「设计输出**确实进入版图几何**」的准入门槛
   （`engine_ringresonator`、`engine_braggmirror`）；其它 kind 出现在 `goal.json` 里会
   **报错而非静默丢弃**。参数已知的器件可用 `params` 直接给定，不受此限制。
