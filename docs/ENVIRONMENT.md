# LDA 环境变量参考

> **口径：唯一真相源 = 代码。** 本表由 `lda/run_p2_usability_smoke.py` 守护 ——
> 它用 `ast` 穷举 `lda/**/*.py` 与 `scripts/**/*.py` 中**由进程环境读取**的
> `LDA_*` 变量（识别 `os.environ.get` / `os.getenv` / `os.environ[...]`），
> 任一变量未在本文件出现即判红（防「加了变量却没人写文档」）。
> **当前共 29 个**（并集）：`lda/` 侧 25 个 + `scripts/` 侧 6 个，其中两侧都读的 2 个
> （`LDA_ADMIN_TOKEN`、`LDA_FDTD_THREADS`）。
>
> ⚠️ 规划文档曾按「7 个变量」立项，实际代码为 29 个 —— 本表以代码为准（差额已如实登记）。
> 数量由门禁断言：本文件必须出现扫描到的变量总数，数字漂了即红。

## 速查：生产必设 / 常改

| 变量 | 默认 | 何时必须设置 |
|---|---|---|
| `LDA_ADMIN_TOKEN` | （空） | ✅ **生产必设**（否则管理员接口不可用，fail-closed） |
| `LDA_WEBUI_PORT` | `8787` | 生产用 `3006` |
| `LDA_DB_URL` | （空 ⇒ 内存后端） | 需要数据持久化时 |
| `LDA_STORE_EMAIL_PASS` | （空 ⇒ 回退 `.env`） | 需要给会员发邮件时 |
| `DEPLOY_MODE` | `selfhost` | 否（仅响应里的形态标签） |

## §1 部署与运维

| 变量 | 默认 | 作用 | 读取点 |
|---|---|---|---|
| `LDA_ADMIN_TOKEN` | `""` | 管理员令牌。**仅从环境变量读取**，未配置即空串 ⇒ 管理员鉴权 **fail-closed**（任何令牌都不通过，含历史 dev 默认串）；生产经 systemd drop-in（`admin-token.conf`）注入 | `lda_webui/app.py:296`、`lda_webui/store.py:438` |
| `LDA_WEBUI_PORT` | `"8787"` | WebUI 监听端口（`0.0.0.0:<port>`） | `lda_webui/app.py:3748`、`lda_webui/deploy.py:92` |
| `DEPLOY_MODE` | `"selfhost"` | 部署形态标签（`selfhost` / `saas`），出现在状态响应里；**不影响任何判决** | `lda_webui/app.py` |
| `LDA_WEBUI_URL` | `http://127.0.0.1:3006` | 仅运维脚本（`scripts/redteam_cron.py`）：告警巡检目标 URL | 同上 |
| `LDA_ADMIN_DROPIN` | `/etc/systemd/system/lda-webui.service.d/admin-token.conf` | 仅运维脚本：从该 drop-in 解析 `LDA_ADMIN_TOKEN`（环境变量优先） | 同上 |
| `LDA_CRON_PY` | （拼接得到的默认解释器路径） | 仅运维脚本（`redteam_anchor_fuzz_cron.py`）：调用 WebUI 用的解释器 | 同上 |
| `LDA_ROOT` | （由脚本自身位置推出的仓库根） | 仅运维脚本（`redteam_anchor_fuzz_cron.py`）：定位仓库根，使脚本在**任意 cwd** 下都能找到 `logs/`、`lda/` 与报告路径 | 同上 |

## §2 数据后端

| 变量 | 默认 | 作用 |
|---|---|---|
| `LDA_DB_URL` | `""` | 存储后端选择：空 / `memory` / `sqlite://:memory:` ⇒ **内存后端**（零依赖，默认）；`sqlite:///<path>` ⇒ SQLite 文件后端；`postgresql://` ⇒ **显式 `NotImplementedError`**（未实装，不静默降级） |
| `LDA_HOME` | `"."` | 相对形式 `sqlite:///rel.db` 的解析基准目录 |

> 读取点：`lda_data/backend.py:158 get_backend()` —— docstring 即契约，与上表同源。

## §3 商业闭环（会员 / 订单 / 邮件 / 许可）

| 变量 | 默认 | 作用 |
|---|---|---|
| `LDA_STORE_EMAIL_PASS` | （无；回退 `lda_webui/.env`） | 会员邮件（许可证下发、密码重置）发信口令。**优先环境变量**，其次读同目录 `.env`（gitignored，明文不入仓库） |
| `LDA_LICENSE_KEY` | `""` | 商业许可密钥。**空 ⇒ 开源版（全功能、无限额）**；校验失败 ⇒ **诚实降级为开源功能集**（不谎报商业能力） |

## §4 生态提案审核策略（`lda_pdk/submit.py:74 get_policy`）

| 变量 | 默认 | 生效条件 | 作用 |
|---|---|---|---|
| `LDA_REVIEW_ENFORCE_BOUNDS` | 关闭 | `1` / `true` / `True` | 开启「参数值域」校验（`enforce_value_bounds`） |
| `LDA_REVIEW_AUTH_REVIEWERS` | 空集合 | 非空字符串 | 具名评审白名单，逗号分隔（`authorized_reviewers`） |
| `LDA_REVIEW_MIN_SOURCE_LEN` | `0` | 纯数字字符串 | `source` 最短长度要求（`min_source_length`） |
| `LDA_REVIEW_STRICT_DEDUP` | 关闭 | `1` / `true` / `True` | 防重用严格去重（`n_g·L` 与 `n_g*L` 视为同题） |

> 该策略在提案准入（评审前）生效，属**工程准入**而非判决 —— 判据仍由 `harness` 死标量给出。

## §5 Agent / LLM（**全部可选，且不参与判决**）

| 变量 | 默认 | 作用 |
|---|---|---|
| `LDA_CS_LLM_BASE_URL` | `""` | 智能体客服 LLM 基址。**空 ⇒ 回退内置 FAQ 知识库**（零外部依赖可跑）；非空时请求 `<base>/v1/chat/completions` |
| `LDA_CS_LLM_API_KEY` | `""` | 客服 LLM 凭据（空则不带头） |
| `LDA_CS_LLM_MODEL` | `"gpt-3.5-turbo"` | 客服 LLM 模型名 |
| `LDA_LLM_BASE` | `""` | 设计 / 求解器提案 Agent 的 LLM 基址（`llm_proposer` / `solver_writer` / `l3_ai_solver`） |
| `LDA_LLM_KEY` | `""` | 同上凭据 |
| `LDA_LLM_MODEL` | `""` | 同上模型名 |
| `LDA_REDTEAM_BASE` | 回落 `LDA_LLM_BASE` | 红队提案 Agent LLM 基址 |
| `LDA_REDTEAM_KEY` | 回落 `LDA_LLM_KEY` | 红队凭据 |
| `LDA_REDTEAM_MODEL` | 回落 `LDA_LLM_MODEL` | 红队模型名 |
| `LDA_MEEP_PY` | （未设） | **B 级 GPL 隔离 Meep 解释器路径**（可选外部场级 ORACLE）。未设 ⇒ 不启动子进程场级求解 |

> 红队 / 提案 Agent 生成的候选**只作为待判决输入**；通过与否由物理定律锚判定。

## §6 测试 / CI 专用（普通使用者无需设置）

| 变量 | 默认 | 作用 |
|---|---|---|
| `LDA_FDTD_THREADS` | （未设 ⇒ 平台默认） | 线程预算；超时预算棘轮据此标定「运行时线程 == 标定线程」 |
| `LDA_SOLVER_CASES` | `"[]"` | 沙箱求解用例注入（`lda_agent/sandbox.py` 构造最小 env 时写入） |
| `LDA_SKIP_LIVE` | （未设 ⇒ 跑实况） | 跳过需要实况资源的用例（无网 / 无 GPU 环境） |
| `LDA_FORCE_RING_FDTD` | `""` | 强制走环形 FDTD 路径（默认空 ⇒ 按可用性自动选择） |
| `LDA_PY` | （受管解释器绝对路径） | 子进程调用用的解释器（`run_cli_smoke.py` 等） |

## §7 红线与诚实边界

1. **LLM 不进判决路径**：§5 全部变量**只影响「写代码 / 提方案 / 客服」的 Agent 层**；
   PASS/FAIL 恒由确定性死标量比对（物理定律锚）决定。关掉所有 LLM 变量，验证能力**不减**。
2. **`LDA_ADMIN_TOKEN` 不设即管理员不可用，是刻意的 fail-closed**（历史血案：
   dev 默认弱令牌曾导致「漏设环境变量 = 公开弱令牌登录」的 fail-open 漏洞）。
3. **`LDA_DB_URL` 指向 Postgres 会显式报错**，不会静默退回内存 —— 「配置看起来生效了，
   其实数据没落盘」比报错危险。
4. **P2-5 起会话令牌走 HttpOnly Cookie**（`lda_store_token` / `lda_admin_token`），
   不是环境变量，也不该被前端 localStorage 保存。

## 附：运维告警脚本的 `REDTEAM_*` 变量（非 `LDA_` 前缀，不在本门禁扫描范围）

`REDTEAM_ALERT_LOG` / `REDTEAM_STATE_FILE` / `REDTEAM_ALERT_WEBHOOK` / `REDTEAM_PROBE_N` /
`REDTEAM_GENERATOR` / `REDTEAM_COOLDOWN_SEC` —— 见 `scripts/redteam_cron.py` 头部「配置」段。
