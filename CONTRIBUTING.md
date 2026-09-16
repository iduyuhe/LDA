# 贡献指南（CONTRIBUTING）

感谢关注 **LDA**——一个 Agent-native 的光子芯片（PDA）+ 量子芯片（QEDA）开源设计软件，核心是 **AI agent 递归自举主权求解器**，人类做架构与验证，AI 不进判决路径。

当前版本：**v0.9.85** · 账本：**22 引擎（光子 15 + 量子 7）+ 11 包 = 33 类端到端 · 122 道锚（严格独立 101 / 降级 3 / 自证桩 18）· CI core 178 条**。

> ⚠️ 账本以 `README.md` 顶行权威账本为准。如与本页不一致，以 README 为准，并欢迎提 PR 修正本页。

## 三条不可逾越的红线（红线即护城河）

1. **主权求解器**：FDTD / FDFD / Mie / TMM / 严格对角化等核心数值内核**不依赖** GPL/Meep/Tidy3D 等外部求解器，必须可独立运行、可逐位验证。
2. **LLM 不进判决路径**：大模型只负责"写代码 / 提方案"，**绝不**参与数值正确性判决。所有判分由确定性 ORACLE（物理定律锚 + 实测语料锚）完成。
3. **可验证优先**：任何新求解器 / 新器件模型，必须带可复现的自测（golden 物理定律锚 + 开放对抗题），否则不进主线。

## 如何参与（阶段 B · 生态播种）

- **⭐ Star 仓库**：<https://github.com/iduyuhe/LDA>——你的 Star 是社区信号，也是对外可达性的杠杆。
- **🐛 认领 Good First Issue**：见 [Issues · good first issue 标签](https://github.com/iduyuhe/LDA/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)。挑一个、评论认领、按本指南提 PR。
- **📐 提交实测语料 / 对抗题**：见 `BOUNTY.md` 反向悬赏机制（实证大数据锚是验证的第二道非 AI ground）。
- **📖 技术叙事**：我们在公众号「工业5点0产业生态联盟」与知乎持续发布 LDA 设计哲学与闭环演示。

## 本地自测（CI core 门禁）

```bash
# 用项目 venv（Python 3.13），不要系统 3.14
cd lda
python run_ci_regression.py --tag core      # CI core 全量（141 条 smoke）
python run_count_consistency_smoke.py        # 计数守护：账本与 pyproject 一致性
python run_parasitic_rc_smoke.py             # 几何寄生估算
```

> 新增代码必须带自测并让 CI core 全绿（FAIL=0 即绿）。计数守护会校验「当前账本」与 `pyproject` 版本，改动账本请同步 README 与 `pyproject.toml`。

## P0-2 计数护栏同步纪律（PR 必查 · 固化必查项）

> 🔴 **任何加 `degraded_ordinal` / 严格独立锚的 PR，必须全仓同步所有硬编码计数护栏。**
> 加锚只改 `lda/lda_harness/benchmarks.py` 的 `BENCHMARK_DEFS`（登记 `candidate` + `candidate_status`），
> 三分类（严格 / 降级 / 自证桩）**自动跟随、逻辑无需手改**；但下列含**硬编码数字**的陈述必须手动同步，
> 否则会静默失真（历史血案：v0.9.74 计数护栏欠账、`ci_core=82` 漂移、`run_three_class_consistency_smoke` 红 4+1 条）。

**必查四处护栏（grep 同步）：**

1. **README 当前账本三分类** —— `## 当前账本` 段 + `验证三分类（...）：严格独立 N 道 · 降级量级参考 M 道 · 自证桩 K 道`
   机器守护：`run_three_class_consistency_smoke.py` C2（README ≡ harness ≡ `/api/verification_ledger`）。
2. **ledger smoke 文档串** —— `lda/run_webui_verification_ledger_smoke.py` 模块 docstring 中的三分类数字
   机器守护：`run_p0_count_guard_sync_smoke.py`（grep 校验必须等于动态真值，会响）。
3. **three_class smoke** —— `lda/run_three_class_consistency_smoke.py`（README ≡ harness ≡ 端点）。
4. **count_consistency smoke** —— `lda/run_count_consistency_smoke.py`（引擎 / 包 / 题库 / CI core 条数 ≡ 代码）。

**PR 自查命令（必跑，FAIL=0 即绿）：**

```bash
cd lda
grep -rn "degraded_ordinal" . | grep -v "candidate_status"   # 定位降级锚登记点
grep -rn "strict_independent" .                              # 定位严格独立陈述
python run_p0_count_guard_sync_smoke.py                      # 机器校验四处硬编码护栏 ≡ 动态真值
python run_three_class_consistency_smoke.py                  # README ≡ harness ≡ 端点
python run_count_consistency_smoke.py                        # CI core / 引擎 / 包 / 题库计数
```

> 动态真值源（唯一真相）：`BENCHMARK_DEFS` + `BENCHMARK_CANDIDATES` 按「先判 `degraded_ordinal`、再查登记表、否则自证桩」推导。
> 当前真值（v0.9.85 / P1-1 B-5 扩基）：**严格独立 101 · 降级 3（E9 + E10 + B21）· 自证桩 18 · 三类和 122**。
> 改完锚后，若 README 当前账本数字或 CI core 条数滞后，上述 smoke 会**当场红**拦截。

## PR 约定

- 一个 PR 做一件事；描述说明它守住哪条红线、动了哪些计数。
- 提交必须带 `Signed-off-by`（用 `git commit -s` 生成，取自你的 `git config user.name / user.email`），否则 CI 的 DCO 闸门会拦截 PR。详见下方「开发者来源证书（DCO）」。
- 命名参考：`[GFI] ...` / `[fix] ...` / `[feat] ...`。
- 不 `git add -A`：运行产物（`lda/reports/*`）不入库，避免阻塞生产 `git pull`。
- 生成物的诚实边界（如"非 foundry 工艺级 deck"）必须在代码与文档中显式标注。

## 开发者来源证书（DCO）与贡献授权

本项目采用 **DCO 1.1（Developer Certificate of Origin）** 作为最轻量的贡献准入机制。
每条提交必须在末尾包含一行签名——直接用 `git commit -s` 即可自动添加：

    Signed-off-by: 你的真名 <你的邮箱>

DCO 1.1 全文见仓库根目录 [`DCO`](DCO) 文件。CI 会对每个 PR / 推送提交做签名闸门检查，
缺签名的提交将被拦截（这正是「来源自证」要挡的）。

**贡献授权（保全未来双许可 / 商业授权权）：**
除 DCO 1.1 的认证外，你理解并同意：通过提交贡献（含 Signed-off-by 行），你授予项目
维护者（杜玉河 / iduyuhe）一项**永久、全球、非独占、免版税**的许可，得以**任何许可
条款**（包括但不限于本项目的 MIT 许可，以及任何专有 / 商业许可）分发、再许可
（relicense）及 sublicense 你的贡献。本授权仅为维护者保留未来按需提供商业授权的能力，
不影响你对自己贡献的其他权利。

> 说明：本条款为工程落地措辞，正式法律效力建议由法律顾问复核。当前项目以 MIT 许可
> 开源，版权 100% 归杜玉河所有；引入此条款是为了在未来接纳外部贡献时，持续保全
> 维护者的双许可 / 商业授权自由，避免被外部贡献稀释。

可选：运行 `git config commit.template .github/commit_template.txt`，让提交模板常驻提醒（仍须用 `git commit -s` 才会真正写入签名行）。

## 许可

本项目以 MIT 许可开源（见 `LICENSE`）。贡献者依据上述 DCO 与授权条款提交代码。
