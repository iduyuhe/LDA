# LDA 主权化搬迁清单与操作步骤（方案稿 · 不执行）

> 文档定位：将 B 级（开源可借·须主权化）依赖从「美属 GitHub 托管 + PyPI 分发」搬迁为「国内主权副本 + 离线可构建」，消除中美对抗下的托管层单点风险。
> 状态：**执行中 · 2026-08-14（阶段0 核实完成 / 阶段1 Gitee 建仓完成 / 阶段2 镜像进行中）**。已实际在 Gitee(i4hub) 创建 5 个主权镜像仓并推送镜像。
> 配套：LDA 依赖主权分级地图（A 永不借 / B 借今踢后 / C 第一天自主）、MEMORY.md「主权优先依赖政策」。

---

## 一、目标与三条原则

1. **托管主权化**：在访问畅通时，把 B 级依赖的源码与发布件完整镜像到国内平台，脱离对 GitHub / PyPI 的实时依赖。
2. **可离线构建**：关键 Python 包与二进制一次性拉取、hash 校验、冷备，确保断网/被限后仍能 `pip install` 本地构建。
3. **可见可控**：扫 SBOM 标出「美原产依赖占比」，对 GPL 传染性组件划红线，避免未来商业「认证版」被动开源。

---

## 二、B 级依赖清单（精确仓库 + 许可证 + 主权风险）

| 组件 | GitHub 仓库（已核实 2026-08-14） | 许可证 | 用途 | 主权风险 | 搬迁动作 |
|---|---|---|---|---|---|
| gdsfactory 内核 | `gdsfactory/gdsfactory` | MIT | 版图/DRC/LVS/导出 GDSII | 低（MIT 可 fork） | fork 主权副本 + vendor |
| Meep | `NanoComp/meep` | **GPL-2.0** | 开源 FDTD（MVP 期 ORACLE/基准） | 中（GPL 外部调用） | fork 主权副本，仅作外部进程调用 |
| KLayout | `KLayout/klayout` | GPL-3.0 | 版图查看/布尔运算 | 中（GPL） | fork 主权副本，外部调用 |
| SAX | `gdsfactory/sax`（原 flaport/sax 已迁） | **Apache-2.0** | 频域电路 S 参数仿真 | 低（可 vendor，须保留 NOTICE） | fork + vendor |
| MPB (MIT Photonic Bands) | `NanoComp/mpb` | **GPL-2.0** | 本征模求解 | 中（GPL） | fork 主权副本，外部调用 |
| ~~Nazca Design~~ | 公开上游不存在（已剔除） | — | 参数化版图备选 | — | **已剔除**：gdsfactory 已覆盖版图层；无法合法 fork 之物不镜像 |
| **Tidy3D（ORACLE B6）** | `flexcompute/tidy3d`（前端 GPL 开源） | **GPL** 前端 + 美属云算力 | 真 3D FDTD 验证锚（外部 ORACLE） | **高（算力在美属云、EAR/ITAR 约束）** | fork 前端主权副本（仅做分发/离线可构建）；**云算力永不作 L3 依赖**，仅外部 ORACLE 校验；无 Key 自动回退 Meep/物理定律锚（详见白皮书 §7.3） |

> 说明：上表仓库路径以「待核实」标注者，执行前需先确认当前上游 org 与许可证。**许可证是红线**（见第七节），务必先核后搬。**Tidy3D 特例**：其前端 Python 包 GPL 开源可 fork 做主权分发，但真仿真算力锁定在 Flexcompute 美国云（受 EAR/ITAR），**不可 fork、不可 vendor**——故仅作外部 ORACLE B6 校验锚，核心零硬编码，断供即回退。
> A 级（Lumerical/Ansys/Synopsys/Cadence/Siemens/GDSFactory+ 商业 NDA-PDK）不在本清单——永不借、自己搞。
> C 级（L0 IR/DSL、L1 agent 协议、L3 AI 求解核、物理定律锚）本就是自主代码，无搬迁问题。

---

## 三、托管平台布局（主 + 备 + 兜底）

- **主**：Gitee（码云，华为等背书，国内 5M+ 用户）—— B 级依赖镜像主仓。
- **备**：GitCode（CSDN 出品，GitLab 架构）—— 第二镜像，防单平台风险。
- **兜底**：自托管 GitLab（未来条件允许时）—— 完全脱离任何外部托管，最终形态。
- **策略**：GitHub 仅保留为「只读上游源」，不向 GitHub 提 PR 合并；国内平台为主读写。

---

## 四、fork / mirror 操作步骤（git 命令模板）

> 用 `--mirror` 做全量镜像（含所有分支、tag、PR 引用），保证副本完整。

```bash
# 1. 全量镜像上游到本地裸仓
git clone --mirror https://github.com/gdsfactory/gdsfactory.git
cd gdsfactory.git

# 2. 推到 Gitee 主权仓（先在国内平台建好空仓）
git push --mirror https://gitee.com/<org>/gdsfactory.git

# 3. 推到 GitCode 备仓
git push --mirror https://gitcode.com/<org>/gdsfactory.git

# 4. 定时增量同步（cron / 行动项）：仅同步 release tag，不追 main 滚动
git fetch origin --tags
git push --mirror https://gitee.com/<org>/gdsfactory.git
```

- 对每个 B 级组件重复上述 1–4。
- 记录映射表：`上游URL → Gitee URL → GitCode URL → 最近同步时间 → 锁定版本 tag`。

---

## 五、PyPI / conda 镜像冷备（含 hash 校验、离线构建）

目标：把 LDA 运行所需的 Python 包一次性下载为 wheel，hash 锁定，存本地离线源。

```bash
# 1. 用 requirements 精确锁定版本
pip download -r requirements.txt \
  --dest ./offline_wheels \
  --no-deps            # 先只下顶层，再递归补依赖
  --platform manylinux2014_x86_64 --python-version 3.13 --only-binary=:all:

# 2. 递归补齐传递依赖（同参数，去重）
pip download -r <(pip resolve requirements.txt) --dest ./offline_wheels ...

# 3. 生成 hash 清单（sha256）
cd offline_wheels && sha256sum *.whl *.tar.gz > SHA256SUMS

# 4. 建本地索引，断网可装
pip install --no-index --find-links ./offline_wheels <pkg>
```

- 二进制包（含编译扩展）须按目标平台（linux/x86_64、未来可能 win/arm）分别冷备。
- 加密相关组件（如 OpenSSL/BoringSSL、含 ECC 384+ 算法）按 EAR 734.7b 备案要求单独标注，必要时降级为国密 SM 等价实现。
- 冷备介质：离线磁带库 / 内部对象存储双副本，定期（季度）更新补安全补丁。

---

## 六、SBOM 扫描与「美原产占比」

```bash
# 用 syft 生成 SBOM（SPDX 格式）
syft packages dir:. -o spdx-json > lda.sbom.json

# 标注美原产：按包上游域名/维护者属地统计
# 经验阈值：美原产 >30% 的项目启动降级/替换方案（参考 2025 一线调研口径）
```

- 输出：`美原产包数 / 总包数 = 占比%`，高占比组件列入「替换候补」。
- 纳入 CI：每次依赖变更自动重扫，占比超限告警。

---

## 七、依赖 vendoring 策略 + GPL 传染性红线（关键）

- **MIT（gdsfactory）/ Apache-2.0（SAX = gdsfactory/sax）**：均可 vendor 进闭源商业代码。Apache-2.0 须保留上游 NOTICE 文件并声明修改；MIT 无附加义务。
- **GPL-2.0 / GPL-3.0（Meep、MPB = GPL-2.0；KLayout = GPL-3.0）**：**红线**——不得静态链接 / 直接 import 进闭源商业代码。
  - 正确用法：作为**独立外部进程**调用（subprocess / CLI / 本地 socket），进程边界隔离，GPL 不污染 LDA 主程序。
  - 或：仅在内核研发期用作 ORACLE/基准，生产路径由我们 AI 写的 L3 求解核取代（本就是 B 级「借今踢后」的终点）。
- **结论**：GPL 组件只进「研发工具链 / 外部调用」，不进「产品研发代码」。这条在动手写 L3 求解核前就要定死。

---

## 八、完整性验证（离线构建测试）

执行搬迁后必须验证「断网也能跑」：

1. 断开外网（或屏蔽 github.com / pypi.org）。
2. 从本地 `offline_wheels` + Gitee 镜像仓全新 clone + 构建 LDA MVP。
3. 跑通最小用例：自然语言 → 版图 → 调用本地 Meep 算一个标准考题 → 与解析解比对通过。
4. 任一步失败即回查缺失包 / 缺失仓，补冷备后重测，直至全离线绿灯。

---

## 九、分阶段执行清单（checklist）

- [x] **阶段 0 · 核准**（2026-08-14 完成）：gdsfactory=MIT、meep=GPL-2.0、klayout=GPL-3.0、mpb=GPL-2.0、sax=gdsfactory/sax(Apache-2.0)；Nazca 公开上游不存在，已剔除 B 级清单（版图由 gdsfactory 覆盖）。
- [ ] **阶段 1 · 建仓**：在 Gitee / GitCode 建好 B 级各组件空仓 + 自托管 GitLab 预留。
- [ ] **阶段 2 · 镜像**：对每个 B 级组件执行第四节 1–4，填映射表。
- [ ] **阶段 3 · 冷备**：执行第五节，生成 `offline_wheels` + `SHA256SUMS`。
- [ ] **阶段 4 · SBOM**：执行第六节，输出美原产占比报告。
- [ ] **阶段 5 · 验证**：执行第八节离线构建测试，全绿。
- [ ] **阶段 6 · 制度化**：cron 定时增量同步 + CI 自动 SBOM 扫描 + 季度冷备更新。

优先级：**阶段 0–2 立即做（成本低、不可逆收益高）；3–6 紧随。**

---

## 十、风险与注意

- **镜像时效**：上游仍在演进，主权副本会滞后。对策：只锁 release tag 同步，不追 main；必要安全补丁手动 cherry-pick。
- **GPL 被动开源**：见第七节，商业「认证版」规划前必须先划清进程边界。
- **加密组件 EAR**：含加密算法的包单独备案/降级国密，避免触发 2025.6 EAR 修订预告中的对华审查。
- **人员账号风险**：执行 fork 的账号若被 GitHub 基于 IP/支付判定为受管制地区，可能影响私有仓——用组织公开仓 + 国内平台主读写规避。
- **不要过度投入布局层重写**：gdsfactory 已 MIT + fork，主权化即满足；功能重写排后期（B 级最不急项），火力集中在 A 级求解器与 C 级标准层。

---

*本方案与 MEMORY.md「主权优先依赖政策」、LDA 依赖主权分级地图配套使用。执行前需杜先生批准，并执行阶段 0 许可证核准。*

---

## 十一、本地主权根执行方案（2026-08-14 增补）

杜先生决策：**本地（自有服务器 / workspace）= 主权根（root of truth）+ 离线冷备；Gitee / GitCode = 公开门面（社区入口）。双轨并存——本地为根、Gitee 为门面。**

- **本地为根**：完全自主、物理掌控、断网可构建，是「踢掉依赖」的终极形态。
- **Gitee 为门面**：开源生态需别人能 clone / fork，纯本地无入口，故保留 Gitee 公开同步镜像作社区门面。
- **终态**：本地 → 自托管公网 GitLab（既主权又开源），即本方案原「兜底」层。

### 本 Agent 环境内已完成的动作
- Gitee(i4hub) 建 5 个空仓：gdsfactory / meep / klayout / mpb / sax。
- **gdsfactory**：已从 GitHub 入 Gitee 仓（164 分支 / 1005 tag / 1169 refs）；并示范从 Gitee 拉到本地 `D:/agent_LDA/.lda_mirror/gdsfactory.git`（主权根样本，remote 已清洗 token）。
- **sax / mpb / meep / klayout**：因本 Agent 沙盒对 `github.com:443` 间歇性完全不可达（重试多次均 `Could not connect to server` / `Connection was reset`），未能从 GitHub 取源码。这些仓库的「取源码 → 入 Gitee → 入本地」须在杜先生本地网络稳定的机器执行（见 `LDA_本地镜像一键脚本.sh`）。

### 本地一键脚本
同目录 `LDA_本地镜像一键脚本.sh`：在杜先生本地（Linux / macOS / Git Bash）执行，直接从 GitHub `clone --mirror` 到本地 `LOCAL_ROOT`，并可选同步到 Gitee 门面。

## 十二、环境约束记录（重要）
- 本 Agent 沙盒对 `github.com` HTTPS **间歇性完全不可达**（非限流，是 TCP 重置 / 连接超时）；对 `gitee.com` API 可达，但 git 匿名 clone 被代理拦截、需 token 认证（`oauth2:TOKEN@`）。
- 推论：**「从 GitHub 取源码」动作不应依赖本 Agent 环境**，应交由本地执行；本环境仅适合做 Gitee 中转 / 本地落盘等国内可达的操作。
- **Gitee token 已明文出现在对话，镜像全部完成后须 revoke 并换新**（标准安全动作）。
