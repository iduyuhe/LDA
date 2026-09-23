# LDA · WebUI 部署与运维说明（D-13）

> 文档编号：LDA-DEPLOY-013
> 版本：**v2.0（2026-09-23 · P2-T2.3 全量重写）**
> 上一版 v1.0（2026-08-20）的端点 / 面板 / 题数 / 解释器 / 鉴权清单**已作废**，
> 作废原因见 [§10](#10-作废说明)。本版所有数字取自代码与自动生成产物，不手写。

---

## 1. 两种部署形态

| 形态 | 用途 | 监听 | 鉴权 |
|---|---|---|---|
| **本地 / 内网演示** | 单机起服务，同网段浏览器访问 | `--port`（默认 **8787**） | 见 [§4](#4-鉴权模型重要) |
| **生产（systemd）** | 对外站点 | **3006**（`LDA_WEBUI_PORT`） | `LDA_ADMIN_TOKEN` + 会员会话 |

## 2. 前置条件

- **Python 3.13**（项目 venv；`pyproject.toml` 声明 `requires-python >= 3.12`）。
  ⚠️ 上一版写的「Python 3.11+ / `lda_cuda_venv`」**作废** —— 全仓使用 PEP 701
  跨行 f-string（3.12+ 语法），按 3.11 安装会在 `import` 期直接 SyntaxError。
- 依赖：核心 `numpy` / `scipy` / `jsonschema`；可选 `numba` / `torch`（**缺失自动降级**，不阻断）。
- **不要求 GPU**。无 GPU 时相关面板走解析 / ORACLE 演示并**诚实标注**，不伪装实时 FDTD。
- 端口可达（内网演示机与观众同网段；必要时开端口）。

## 3. 启停（推荐 `deploy.py`，零外部依赖）

```bash
cd <仓库根>

# 启动（默认端口 8787，后台守护）
<venv>/Scripts/python.exe lda/lda_webui/deploy.py start
# 指定端口
<venv>/Scripts/python.exe lda/lda_webui/deploy.py start --port 9000
# 前台运行（容器 / 无守护场景）
<venv>/Scripts/python.exe lda/lda_webui/deploy.py start --foreground

# 状态 + 健康检查（内部调 GET /api/status）
<venv>/Scripts/python.exe lda/lda_webui/deploy.py status

# 停止 / 重启
<venv>/Scripts/python.exe lda/lda_webui/deploy.py stop
<venv>/Scripts/python.exe lda/lda_webui/deploy.py restart
```

> Linux / macOS 用 `<venv>/bin/python`。
> 不借助脚本手动跑（调试用）：`LDA_WEBUI_PORT=8787 <venv>/.../python lda/lda_webui/app.py`

浏览器访问 `http://<主机IP>:8787/`。查本机 IP：Linux/macOS `hostname -I`、Windows `ipconfig`。

## 4. 鉴权模型（重要）

| 面 | 规则 |
|---|---|
| **GET 验货端点**（`/api/status`、`/api/verification_ledger`、`/api/cpo_array`、`/api/shelf` …） | **匿名可访问** —— 保留「外部可独立验货」战略可达性 |
| **重计算 POST 端点**（`HEAVY_POST_PATHS`，当前 **60** 条） | **须登录**：会员会话令牌 **或** `Authorization: Bearer <LDA_ADMIN_TOKEN>` |
| 未登录访问重计算端点 | **401** + JSON 指引（`需登录后才能触发重计算…`），**不占并发 / 不占缓存** |
| 会话令牌载体 | **HttpOnly Cookie**（`lda_store_token` / `lda_admin_token`），前端不落 localStorage |

并发护栏（重计算端点）：每端点独立串行锁 + 全局并发上限（`min(cpu, 4)`）+ 入参体积上限
256 KiB + TTL 缓存；冲突返回 **429** 并给出 `retry_after`。

## 5. 运维

| 项 | 位置 / 取值 |
|---|---|
| pid 文件 | `lda/lda_webui/webui.pid` |
| 日志 | `lda/lda_webui/webui.log`（stdout/stderr 追加） |
| 端口 | 环境变量 `LDA_WEBUI_PORT` 或 `deploy.py --port`（默认 **8787**） |
| 健康检查 | `GET /api/status`（`deploy.py status` 自动调） |
| 系统状态 | `GET /api/health` |

**环境变量**（`LDA_ADMIN_TOKEN` / `LDA_WEBUI_PORT` / `DEPLOY_MODE` / `LDA_CS_LLM_*` /
`LDA_STORE_EMAIL_PASS` / `LDA_LICENSE_KEY` / `LDA_DB_URL`）的集中口径见
**`docs/ENVIRONMENT.md`**（含默认值与影响面）。

## 6. 端点一览

**本文件不再手写端点清单。** 见自动生成的 **`docs/API_REFERENCE.md`**：

- 生成器：`scripts/gen_api_reference.py`（真相源 = `lda/lda_webui/routes.py`）
- 当前规模：**132 个端点**（精确 120 + 前缀/后缀 12）· 描述覆盖 **100%** · 需登录 60
- 漂移防护：`lda/run_p2_usability_smoke.py` 断言「重新生成 == 磁盘文件」，手改即红

> 上一版 §5 手写的 12 条清单停更于 2026-08-20（漏掉全部 120 条），已删除。

## 7. 生产部署（systemd）

生产站点以 systemd 服务常驻，由仓库内 `lda-webui.service` 拉起 `app.py`，
端口走 `LDA_WEBUI_PORT`（**3006**），上游反向代理到域名。变更流程：

1. 本地跑完门禁（`cd lda && python run_ci_regression.py --tag core`，FAIL=0 即绿）；
2. 推送到远端后，用部署脚本按**提交号**对齐并校验：`remote_deploy.py --expect-head <sha>`
   （脚本内做 fast-forward + 服务重启 + 健康检查 + HEAD 比对）；
3. 健康检查须**内外网各一次**，并确认题库数 / 版本号与本地一致；
4. `store.json`（会员与订单数据）**不在部署覆盖范围内**，不得被覆盖。

## 8. 安全与边界（诚实声明）

- **内网演示默认绑 `0.0.0.0`** ⇒ 勿直接暴露公网；公网演示须前置 VPN / 反向代理 + 鉴权。
- **LLM 不进判决路径**：所有 PASS/FAIL 由死代码标量比对（物理定律锚）决定；WebUI 不调 LLM 判决。
- **无 GPU 时诚实降级**：显示解析 / ORACLE 真值并标注，不伪装实时 FDTD。
- **研究级演示，非商业签核工具**；几何 DRC 为**主权子集**（最小线宽/间距/面积），非晶圆厂官方 deck 全量。
- **已知瑕疵（如实披露）**：`_send` 对所有响应无条件追加 `charset=utf-8`，故 8 个非文本
  `Content-Type`（zip ×3 / png·jpeg ×2 / docx ×1 / 本次新增的 `application/octet-stream` ×1）
  带上了 `charset`。不影响解析，但不够严谨；属独立收口项（统一非文本 ctype + 8 处回归），
  已记入 backlog。

## 9. 验收清单（部署后）

1. `deploy.py status` ⇒ 运行中（pid）且健康检查 PASS。
2. 浏览器打开 `http://<主机IP>:8787/` ⇒ 控制台可见（面板数口径以 `README.md` 当前账本为准）。
3. 匿名点击任一**重计算**面板 ⇒ 应得到 **401 + 登录指引**（而非挂起或静默失败）。
4. `deploy.py stop` ⇒ 停止；`deploy.py restart` ⇒ 恢复。

## 10. 作废说明

v1.0（2026-08-20）以下内容**作废**，本版全部替换：

| v1.0 原文 | 实际 | 处置 |
|---|---|---|
| §5 端点清单 12 条 | 精确路由 **120** 条 + 前缀 12 条 | 删除，改指自动生成的 `docs/API_REFERENCE.md` |
| §1 面板表「七面板 ①–⑦」 | README 账本口径 **五十七面板** | 删除表格 |
| §1 题数「B1–B11」 | **469** 道锚（B1–B451 + E1–E10 + S1–S13） | 更新口径 |
| §2「Python 3.11+ / `lda_cuda_venv`」 | **Python 3.13** 项目 venv（`>=3.12`） | 更新 |
| §6「未做鉴权」 | **v0.9.7 起有登录闸门**（重计算端点 60 条，401 语义） | 更新 |
| §7「`deploy.py status` → layers=8 pdks=5」 | 以实际响应为准（`GET /api/status`） | 改为不写死数字 |

> 本版由 P2-T2.3 重写，并纳入 `lda/run_p2_usability_smoke.py` 门禁：文中引用的仓库内路径
> 必须真实存在，引用的数字口径必须与 README 账本一致，否则门禁判红。
