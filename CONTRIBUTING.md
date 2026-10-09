# 贡献指南（CONTRIBUTING）

感谢关注 **LDA**——一个 Agent-native 的光子芯片（PDA）+ 量子芯片（QEDA）开源设计软件，核心是 **AI agent 递归自举主权求解器**，人类做架构与验证，AI 不进判决路径。

当前版本：**v0.9.214** · 账本：**22 引擎（光子 15 + 量子 7）+ 11 包 = 33 类端到端 · 490 道锚（严格独立 468 / 降级 3 / 自证桩 19）· CI core 307 条**
· 实证大数据锚：**70 条 A 级语料（100% 可公开溯源）· 14 条实测对照（独立 10 + 跨器件 4）**。

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

## 本地自测（双入口 · 都是权威）

LDA 有**两个并存的自测入口**，口径同源、互不替代：

```bash
# 用项目 venv（Python 3.13），不要系统 3.14

# ---- 入口①（主入口）：CI 回归 ----
cd lda
python run_ci_regression.py --tag core      # CI core 全量（293 条 smoke）
python run_parasitic_rc_smoke.py             # 几何寄生估算

# ---- 入口②（次入口）：pytest ----
cd ..                                        # 仓库根
pytest                                       # 默认档：契约/单元用例，秒级
pytest -m smoke                              # smoke 档：逐条转发 CI core 成员（分钟级，293 条）
```

> 🔴 **两个入口口径必须一致**：`tests/test_smoke_core.py` 的 smoke 用例**动态派生**自
> `run_ci_regression.CORE_SMOKES`（不手抄清单），逐条调用同一个 `_run_one`，
> 语义与主入口逐位一致。**主入口 `run_ci_regression.py --tag core` 仍是权威**，
> 新 smoke 一律注册进 `CORE_SMOKES`，pytest 侧自动跟随。

**pytest 入口的纪律（由 `tests/test_ci_entry_contract.py` 常驻守护）：**

1. **pytest 永不进 `CORE_SMOKES`** —— 否则 CI 会递归调 pytest，形成双口径漂移。
2. **`CORE_SMOKES` 成员必须真实存在** —— 防「账本 +1、从未执行」的幽灵假绿。
3. **默认档 `-m 'not smoke'`** —— 跑 `pytest` 不该裸起 200+ 子进程；要跑全量须显式 `-m smoke`。
4. **`tests/` 不进发行包** —— 装出去的 `lda` 不带测试。

> `pyproject.toml` 的 `[tool.pytest.ini_options]` 已配好 `testpaths` / 默认档 / `smoke` marker，
> 开箱即用。若你的环境装了会崩的第三方 pytest 插件，可加
> `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`（LDA 的 `tests/` 不依赖任何三方插件）。

> 新增代码必须带自测并让 CI core 全绿（FAIL=0 即绿）。计数守护会校验「当前账本」与 `pyproject` 版本，改动账本请同步 README 与 `pyproject.toml`。

## 安装为包（`pip install -e .`）

```bash
pip install -e .            # 可编辑安装（等价 -e ".[dev]" 见 pyproject）
lda --help                  # 子命令：design / check / build / gf / report
lda build --help            # 端到端单命令（一句话目标 → 设计包 → 版图 → GDS + DRC/LVS 签核）
```

> 打包契约由 `tests/test_packaging_contract.py` 常驻守护：**声明包集 ≡ `lda/` 真实包集**、
> `package-dir` 映射、`[project.scripts] lda` 目标可导入可调用。删/加一个包登记项会让它当场红。
> 若 `pip install -e .` 在受限镜像上因构建隔离失败，可加 `--no-build-isolation`。

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
> 改完锚后，若 README 当前账本数字或 CI core 条数滞后，上述 smoke 会**当场红**拦截。

## P5-3 实证锚纪律（M6 指标 · 语料扩容必读）

**M6 = A 级实证锚数 / 实测对照数**，其判据的**唯一机器来源**是
`lda/lda_harness/empirical_m6.py`（`audit_m6()` / `gate_m6()`），
由 **两入口共调同一份**：`run_empirical_anchor_smoke.py` 判据⑩ 与 `tests/test_m6_empirical.py`。

**语料（`lda/lda_harness/seed_empirical.json`）的准入红线：**

1. **只收 A 级** —— `citation` 或 `source_url` 必须含 **DOI / arXiv / 公开 URL** 定位符
   （由 `provenance.classify_citation` 机器判定，**LLM 不参与分级**）。
   B 级（仅文本描述）**禁止作 golden 进判决路径**，X 级（无来源）直接拒收。
2. **每条必须带 `geometry` + `uncertainty_abs`（σ）** —— 这是「对照可复算」的前提，
   缺任一项会让 M6-5 / M6-6 当场红。补几何时**只补几何、不改既有数值**。
3. **id 唯一**，且新增应让**公开定位符去重数**同步增长（M6-4 防「一个 URL 灌 30 条」刷条数）。
4. **实测 vs 仿真**：ground truth 为仿真值的语料必须在 `note` 显式声明「非实测」。

**「实测对照」的三档分账（写入 `empirical_m6._NEW_COMPARISONS` 或
`lda_design.loss_engines.CORPUS_ENGINE_MAP`）：**

| 档 | 计算路径读什么 | 计入 M6？ |
|---|---|---|
| `independent` | **只吃几何 + 物理常数**，不读被比较条的任何测量量（含派生字段如 `n_g`） | ✅ 真预测误差 |
| `cross_measurement` | 读**另一条**语料的实测值（同平台跨器件一致性，如直波导损耗 → 预测微环 Q） | ✅ |
| `calibration_anchor` | 引擎标定常数**取自本条**实测 ⇒ rel≡0、零信息量 | ❌ 透明登记但不计入 |

> 对照的**独立性由突变探针证明**：`scripts/p5_probe.py` 会扰动实测值，断言
> `independent` 档输出**逐位不动**（见下）。若引擎里藏了答案（`computed := measured`），
> `tests/test_m6_empirical.py::test_independent_comparisons_do_not_read_measured_value` 会红。

**P5 门禁突变探针（人工运行，不进 CI core）：**

```bash
python scripts/p5_probe.py     # 10 反例：每条新门禁都要证明「会响」
```

> 该脚本靠「改工作区文件 → 跑门禁 → 按原字节还原 + sha256 复核」取证，
> 与 `scripts/p2_usability_probe.py` / `p3_matrix_probe.py` 同一纪律。
> ⚠️ **跑探针期间语料文件会被临时改写**（如截断到 59 条），此时**不要**并行跑其它
> 依赖 seed 的 smoke，否则会读到瞬态值而假红。

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
