# 对拍参考实测 Runbook（OpenROAD / OpenSTA）

> 状态：**待启用（用户 2026-11-04 决定「维持 unavailable，不冒充」）** · 适用版本：v0.9.364+
> 相关代码：`lda_l2/ecore/dxcheck.py` · 门禁：`lda/run_ecore_s7_smoke.py`、`lda/run_xcheck_isolation_smoke.py`
> 关联决策：`CHANGELOG.md` v0.9.364 · 本仓纪律：外部工具**只作候选（candidate），永不作 golden**

---

## 0. 这份文档解决什么

B4 差异表里 `reference` 列目前恒为 `unavailable`（本机没有 OpenROAD/OpenSTA）。
这不是「漏做」，而是**如实降级**：`evidence_level=SELF_CONSISTENCY_ONLY`、`claimable=False`。

本 runbook 记录**把它变成实测**的三步、每步的验收判据、以及必须守住的红线。
照着做不会再返工，也不会误以为「装上就等于能对拍」——装上只是第一步。

---

## 1. 为什么现在做不到（2026-11-04 实测，避免重复尝试）

| 路径 | 结论 | 证据 |
|---|---|---|
| WSL2 | **被程序黑名单禁用，不可绕** | 安全策略直接拦截 `wsl.exe`，提示「不可批准/绕过」 |
| Docker Desktop | **起不来** | ① Linux 引擎依赖 WSL2（同上）；② `~/.docker/config.json`、`daemon.json` 被沙箱拒写 |
| Docker Hub 官方 registry | 不可达 | 代理 502 / 直连 20 s 超时 |
| **镜像源** | **可达**（备选） | `docker.m.daocloud.io/v2/` → 401（正常鉴权挑战）、`dockerproxy.net/v2/` → 200 |
| 本机 VM | 无 | 无 VirtualBox、VMware 目录空、无 Hyper-V cmdlet |
| conda / apt | 无 | 均未安装 |
| 生产机 `115.191.20.92` | **容量不足** | CentOS Stream 9 · 4 核 · **3 GB 内存（已用 2 GB）** · 无 docker/conda；OpenROAD 链接期内存远超此值，且会饿死线上 `lda-webui` |

> 结论：本机装不了；要实测必须先在**别处**拿到一个能跑 Linux 二进制的环境。

---

## 2. Step 1 —— 拿到能跑 Linux 二进制的环境（三选一）

### 1A. 解禁 WSL（本机，最快）

1. 安全中心 → 命令安全 → 程序黑名单，移除 `wsl.exe`；再允许 `~/.docker` 配置写入。
2. 启动 Docker Desktop，确认引擎可用：
   ```bash
   docker info --format '{{.ServerVersion}} / {{.OSType}}'
   ```
3. 走镜像源拉 ORFS（官方 registry 不通，**必须**用镜像）：
   ```bash
   docker pull docker.m.daocloud.io/openroad/orfs:latest
   docker run --rm docker.m.daocloud.io/openroad/orfs:latest \
       bash -lc 'openroad -version; sta -version'
   ```
   > `openroad` 与 `sta`（OpenSTA）都在该镜像里；OpenSTA 是 **GPL-3.0** ⇒ 只允许这样
   > **独立进程黑盒调用**，禁链接、禁 vendored（本仓 `SOVEREIGN_DEPS` 已登记）。

### 1B. 一台非生产 Linux（推荐用于「录制回放」）

建议 **≥ 16 GB 内存 / ≥ 4 核 / 40 GB 盘**（OpenROAD 编译与链接吃内存；只跑二进制则 4 GB 也够）。
在该机安装（任选其一，视发行版）：

```bash
# 方式一：官方镜像（推荐，免编译）
docker pull docker.m.daocloud.io/openroad/orfs:latest

# 方式二：conda（litex-hub 频道，OpenROAD + OpenSTA 预编译）
conda create -n orfs -c litex-hub -c conda-forge openroad -y

# 方式三：源码编译（1–2 小时，仅当上面两条不可用时）
#   见 OpenROAD-flow-scripts 的 setup 脚本；需要 boost/eigen/tcl/spdlog 等
```

### 1C. 远端一次性执行（不落地）

若只是要一次数字，可在任一台有工具的机器上跑完、把**文本输出**带回；
本仓的差异表只需要文本（P3），不要求工具存在于 CI 机器上（见 Step 3 的「录制」分支）。

**Step 1 验收**：`openroad -version` 与 `sta -version` 都能输出（或 docker 一行 `docker run ...` 能跑通）。

---

## 3. Step 2 —— 让 `probe_reference()` 看得到它

现状：`dxcheck.probe_reference()` 用 `shutil.which(t.lower()) or shutil.which(t)` 判断在场
（**只看 PATH，不 import、不执行**）。所以有两种接法：

### 2A. PATH 垫片（最小改动，推荐）

把下面这种 wrapper 放到 PATH 上的某个目录（例如 `~/bin`），并确保 CI 进程 PATH 含它：

```bash
#!/usr/bin/env bash
# ~/bin/openroad —— 只做转发，不含任何逻辑（黑盒）
exec docker run --rm -i -v "$PWD":/work -w /work \
     docker.m.daocloud.io/openroad/orfs:latest openroad "$@"
```

同理做 `~/bin/sta`（把末段换成 `sta`）。
> 好处：`dxcheck` **一行不用改**，`probe_reference()` 立刻返回 `present=True`。
> 注意：wrapper 不进仓库（它是本机环境，不是代码）；如需入库请放 `tools/` 并加 `.gitignore` 讨论。

### 2B. runner 前缀（支持远端/容器）

在 `dxcheck` 里新增一个 `runner` 概念，让 `run_reference_text()` 支持前缀命令，例如
`LDA_XCHECK_RUNNER_OPENROAD="docker run --rm -i -v ... openroad/orfs openroad"`。
> 改动面：`probe_reference()` + `run_reference_text()` 两处；必须补**反向探针**
> 「runner 指向不存在的程序 ⇒ 仍降级为 `unavailable`」，否则会出现「以为在场」的假绿。

**Step 2 验收**：`python -c "from lda_l2.ecore import dxcheck as X; print(X.probe_reference())"`
里 `present` 为 `True`（且此时 `reference.status` 仍应是 `not_run`，**不是** `measured`）。

---

## 4. Step 3 —— 生成 c17 输入 + 把 `reference` 推到 `measured`

### 3A. 需要四个输入（都能从本仓现有能力取）

| 输入 | 来源 | 备注 |
|---|---|---|
| Verilog 网表 | `dverilog.SAMPLE_VERILOG`（c17：5×NAND2 + 1×INV） | 已是可信样本 |
| LEF | `dlef.SAMPLE_LEF`（INVX1 / NAND2X1 几何） | 单元几何逐字读入 |
| DEF | 由 LDA 布局生成 ⇒ **需补一个 `Placement → DefDesign` 适配器** | 现只有 `ddef.serialize_def(DefDesign)`；`ddef.SAMPLE_DEF` 仅 2 实例，不够 |
| Liberty | `dliberty.SAMPLE_LIBERTY`（合成子集，**非 foundry PDK**）或公开 PDK 的 `.lib` | OpenSTA 需要它算延时 |

> 缺口明确：**DEF 写出器**是 Step 3 唯一需要新写的代码（约 40–60 行，按 `ddef` 的
> `DefComponent/DefNet/DefRoute` 组装，再调 `serialize_def`）。

### 3B. 跑参考工具（Tcl 骨架）

> ⚠️ 命令名随版本变动：**先 `openroad -no_init -exit` 进交互执行 `help`** 确认，
> 再写进脚本。下表给出的是常见形态，不保证每个版本都有。

```tcl
# openroad_area.tcl —— 面积 + 线长
read_lef  sample.lef
read_def  c17_placed.def
# 面积（OpenROAD 常见命令）
report_design_area
# 线长（版本差异较大：report_wire_length / report_grt_wirelength / 走 ORFS flow 的 report_wire_length）
report_wire_length
exit
```

```tcl
# opensta_wns.tcl —— WNS
read_liberty sample.lib
read_verilog c17.v
link_design c17
read_sdc     c17.sdc          # 至少 create_clock 一条
report_worst_slack -max       # 输出形如: worst slack max  -12.34
exit
```

```bash
openroad -exit openroad_area.tcl  > area.txt
sta      -exit opensta_wns.tcl    > wns.txt
```

### 3C. 接进差异表（今天就能用的两个解析器）

```python
from lda_l2.ecore import dxcheck as X

chan = X.run_reference_text("openroad", ["-exit", "openroad_area.tcl"])   # 独立进程 + 只取文本
area = X.parse_openroad_area_text(chan["text"])                            # "Design area 1234.56 u^2"
wns  = X.parse_opensta_wns_text(X.run_reference_text("sta", ["-exit", "opensta_wns.tcl"])["text"])
```

**还差一处代码**：`xcheck()` 目前只调 `_ref_status()`（永远拿不到 `measured`）。需要新增一个
`ref_measured: dict[str, dict]` 入参（或 `attach_reference(row, tool, value)`），把
`{"status": "measured", "value": <float>}` 注入到对应行，并把 `baseline_used` 改成 `"reference"`。

**注入后必须同时成立**（`validate_table` 已机核）：
- `evidence_level == "EXTERNAL_CROSSCHECK"`
- `baseline_used == "reference"` 且 `exceeds` **不得为 `null`**（有基线就必须判）
- `delta = lda − reference`；`band` 按需给（面积/线长可给 `pct_tol`，WNS 给 `abs_tol` 且单位 ps）

### 3D. 「录制回放」分支（Step 1B/1C 时用）

若参考只在别的机器上跑一次，把**文本 + 出处**落成一份语料再消费：

```json
{
  "tool": "OpenROAD", "version": "…", "command": "openroad -exit openroad_area.tcl",
  "output_sha256": "…", "captured_at": "2026-11-xx", "host": "<非生产机>",
  "text": "Design area 1234.56 u^2 …"
}
```
→ 新增 `status="recorded"`（与 `measured` 区分：**不是本次执行**），`evidence_level` 仍可升
`EXTERNAL_CROSSCHECK`，但 `meta` 里必须写 `reproduced_here=False`。
> 这条分支的价值：CI 保持 hermetic（P4 不破），同时对拍证据是真的。

**Step 3 验收**（三条必须同时）：
1. `reference.status == "measured"`（或 `recorded`），`evidence_level == "EXTERNAL_CROSSCHECK"`；
2. `exceeds` 是 `true`/`false`，且 `delta` 与手算一致（逐值核对，不看比值）；
3. 关掉工具（把 PATH 上的 wrapper 移走）后，`run_ecore_s7_smoke` **仍全绿** —— 缺席必须可跑。

---

## 5. 变化前后对照

| 字段 | 现在（C 决定） | 实测后 |
|---|---|---|
| `reference.status` | `unavailable` | `measured`（或 `recorded`） |
| `reference.value` | `null` | 工具给出的数 |
| `evidence_level` | `SELF_CONSISTENCY_ONLY` | `EXTERNAL_CROSSCHECK` |
| `baseline_used` | `golden` / `target` / `none` | 有参考时优先 `reference` |
| `delta` | `null` 或 `0`（同定义自检） | `lda − reference` |
| `meta.reference_available` | `False` | `True` |
| `claimable` | `False` | **仍为 `False`**（对拍 ≠ 签核） |

---

## 6. 红线（一条都不能破）

1. **P1 角色位**：外部工具只进 `reference`（= candidate），**永不进 `golden`**。
   golden 只能是闭式几何/物理律。`validate_table` 会拦，`run_xcheck_isolation_smoke` 的 P1 也会拦。
2. **P3 只读文本**：`dxcheck` 不得 `import openroad/opensta/odb/sax/...`；只经独立进程 + 文本。
   门禁有 AST 判据 + 合成 `import opensta` 反证。
3. **P4 缺席可运行**：对拍脚本**不得**进 `CORE_SMOKES`；工具缺席时全量 CI 必须仍全绿。
4. **授权与许可**：OpenSTA 是 **GPL-3.0** ⇒ 只允许独立可执行文件黑盒调用，禁链接/禁 vendored；
   不得把镜像或二进制提交进仓库（只允许文档写「怎么获取」）。
5. **不冒充**：`measured` 只能来自真跑；未跑就写 `measured` 会被 P5 / X11 反向探针判红。

---

## 7. 验证清单（改完必跑）

```bash
cd lda
python run_ecore_s7_smoke.py            # 23 判据：表结构/三态/归因/可复现/降级
python run_xcheck_isolation_smoke.py    # P1/P2/P3/P4/P5
python run_pyflakes_ratchet_smoke.py    # 改过 .py 必跑
python run_timeout_budget_ratchet_smoke.py
python run_count_consistency_smoke.py   # 若动过 README 判据数/版本
```
另外：**凡新增/改动 `lda/**/*.py`，发布前必须跑全量**（`run_ci_regression.py --tag core`），
子集全绿不等于全量绿（本仓已四次实证）。

---

## 8. 诚实边界（写进对外口径）

- 即使 `reference` 变成 `measured`，**对拍 ≠ 签核**：面积/线长是几何量，一致性只能证明
  「同一份 DEF 上两边算的是同一件事」；WNS 的差异由**延时模型**主导（我们无 SPEF、单角、
  一阶 STA），所以 WNS 差多少都要**归因**，不能拿来宣称「与 OpenSTA 一致 ⇒ 正确」。
- 面积/线长的 golden 与平台实现**同定义**（`independent=False`）——独立性只能来自外部实测。
- 参考工具版本必须随证据记录；换版本可能改变数字，故 `tool` + `version` 是证据的一部分。
- 本仓规则集/单元库是**自建教科书尺度，非 foundry PDK**；不得据此作制造或性能宣称。

---

## 9. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-04 | 初版：记录环境硬阻（WSL 黑名单 / Docker 不可用 / 生产机 3 GB）、三步启用路径、成功判据与红线 |
