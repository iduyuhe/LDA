# LDA P2 产品化外壳 · 开发方案（决策已定，待执行）

> 路线图层：当前(器件级闭环) → P1 芯片级补强 ✅已完成(v0.7.0) → **P2 产品化外壳（本文）** → P3 生态/签核
> 状态：2026-08-26 起草并定稿（5 项决策已拍板），仅方案，**未执行任何代码改动**。
> 代号说明：本文"P2"指杜先生路线图的「产品化外壳」，与战略文档「技术验证三轨」(P0/P1/P2) 是两套体系，勿混。

---

## 0. 定位与边界

P2 的目标 = 把已验证的内核（零依赖 L0 IR / L1 agent 协议 / L3 AI 求解核 / harness 双 ground）从「单机 demo WebUI」升级为「**可自托管的开源产品**」。

**铁律边界（不可破）**：
- 开源内核（L0/L1/L3/harness）保持零外部依赖、可独立 `import` 跑，P2 任何改动**不得绑架内核**。
- 商业化增值（多用户 / 云 / license）作为**独立可选层**，清晰与开源包分离。
- 主权边界（A/B/C 级依赖政策）不被商业化层污染——商业层不引入任何 A 级禁借组件。

---

## 1. 现状盘点（已核实代码，非凭记忆）

| 维度 | 当前真实状态 |
|------|------|
| **WebUI** | `lda/lda_webui/app.py`（105KB）纯标准库 `http.server`+`ThreadingHTTPServer`，**零依赖、单进程、内存态、无认证**；前端 `static/index.html`（57 面板） |
| **部署** | `deploy.py` 内网单机后台启动（默认 `0.0.0.0:8787`，pid+log 管理）；**无 Dockerfile** |
| **数据层** | **无 DB / 无 SQLite**；持久化=散落 json（`reports/`、`empirical_contributions.json`、proposals、`lda_pdk` 落盘文件） |
| **API** | app.py 已有 ~25 个 `/api/*` 端点（事实上的 REST-ish，但**无认证 / 无配额 / 无 license**） |
| **依赖** | `requirements.txt` 固化 `numpy/scipy/jsonschema`；可选 numba/torch/matplotlib/pandas/networkx/tqdm |

**结论**：P2 是从「零依赖内网 demo」到「可自托管产品」的跨越，三大块都是**净增**，不删现有能力（单文件 `app.py` 内网模式保留）。

---

## 2. 设计原则

1. **内核零依赖不被商业化层绑架**：WebUI/数据层/API 商业化脚手架全部走**可选依赖**，核心包 `lda-design` 仍可 `pip install` 后独立跑。
2. **自托管 Docker + SaaS 兼容同时做**：P2.1 既交付自托管 Docker 镜像，也在架构层按「多租户/无状态/配置驱动」构建，使代码 SaaS-ready（`StorageBackend` 可指向托管 Postgres/D1，`DEPLOY_MODE` 配置驱动）；但**不建 SaaS 运营基础设施**（计费系统/弹性编排/运维监控/合规数据出境），待发动期真实用户 + 合规理顺后再上。
3. **数据层可迁移**：SQLite 起步（零运维），抽象层兼容 Postgres / Cloudflare D1（复用智衍 edge-SQLite 经验）。
4. **凭证隔离 + 零真名**：license/secret 走加密 vault（复用智衍「凭证隔离部署」模式），对外不暴露真实主体。
5. **开源版功能完整、商业版只加治理/规模/支持**：避免「开源阉割版」损害生态信任。

---

## 3. 三大模块详细设计

### 3.1 部署外壳（P2.1）

- **Dockerfile（多阶段）**：builder 装可选 numba/torch；runtime 仅 `numpy/scipy/jsonschema` + 数据层依赖。镜像体积可控。
- **docker-compose.yml**：`web` 服务 + 可选 `postgres`（P2.2 数据层用；SQLite 模式下可省）。卷挂载 `.env` 与数据目录。
- **`.env` 配置**：端口、DB 路径/连接串、SECRET_KEY、LICENSE_KEY、是否启用多用户。
- **统一启动入口**：`deploy.py` 升级支持 `local` / `docker` 双模式；保留原内网单机后台行为（零破坏）。
- **健康检查**：复用现有 `/api/status` 增强为 `/api/health`（含 DB 连通、内核版本），供 compose/liveness 探针。
- **反向代理参考文档**：nginx / Caddy 配置片段（HTTPS 终止、静态缓存）。
- **云部署参考**：轻量机自托管 + Cloudflare 边缘加速思路（不引入强云绑定）。
- **SaaS-ready 架构（同时落地，非延后）**：应用层无状态（认证态走 token/DB，不绑本地进程内内存）；`StorageBackend` 抽象支持切换托管云 DB（Postgres/D1）；`deploy.py` 配置驱动部署形态（`DEPLOY_MODE=selfhost|saas`）。SaaS 运营基础设施（计费/弹性编排/运维）**明确不在 P2 范围**，仅预留兼容，避免无用户时空耗。

### 3.2 多用户数据层（P2.2）

- **选型**：**SQLite 起步**（零运维、单机/小团队），通过 `StorageBackend` 抽象兼容 Postgres / D1。
- **数据模型**：
  - `users`（id, email, pw_hash[bCrypt], created）
  - `organizations`（id, name, plan, license_key_hash）
  - `memberships`（user↔org 角色）
  - `projects`（org_id, name, meta）
  - `design_results`（project_id, device_type, params, dual_verify_report[JSON], layout_json, created）
  - `run_logs`（project_id, solver, duration, status）
  - `api_keys`（user_id, key_hash, scopes）
  - `licenses`（org_id, tier, seats, expires, signature）
- **隔离**：组织→项目→设计结果三级，租户隔离（查询强制 `WHERE org_id=?`）；行级权限。
- **历史数据迁移**：现有散落 json（empirical_contributions / proposals / reports）保留为文件备份，元信息入 DB，双写灰度期。
- **认证**：邮箱+密码（bCrypt）+ API Key（Bearer）；session/JWT 可选。
- **凭证隔离**：license/secret 加密存储（vault 模式），**不落明文**（复用智衍纪律）。

### 3.3 API 商业化脚手架（P2.3）

- **API 收敛**：把 app.py 裸端点收敛为正式 REST 路由表（可选引入 FastAPI；或增强 stdlib 路由 + 中间件，保零依赖选项）。
- **认证中间件**：API Key / JWT 校验，未认证返回 401；开源单用户模式下可关闭。
- **配额/计量**：`usage` 表（设计次数、求解器时长、PDK 调用次数）；开源版无限，商业版按 tier 策略可配。
- **License 校验**：独立 `lda_license` 模块（离线签名校验占位，不污染内核），校验失败降级为开源功能集。
- **插件注册**：`ext_oracle`（已有）作为扩展点；定义插件 manifest + 安全加载器（白名单、沙箱）。
- **匿名使用统计（可选）**：需用户显式同意，开源版默认关闭，绝不默认上报。

---

## 4. 任务拆解（建议分 P2.1 / P2.2 / P2.3 三子阶段，逐步可验收）

| ID | 子阶段 | 任务 | 依赖 | 验收判据 | 工期 |
|----|--------|------|------|----------|------|
| P2.1-a | 部署外壳 | 写 Dockerfile + docker-compose + .env 模板 | — | `docker compose up` 起服务，/api/health 200 | 3d |
| P2.1-b | 部署外壳 | deploy.py 双模式(local/docker) + 健康检查增强 | P2.1-a | 本地+容器两种启动均 PASS，端点全绿 | 2d |
| P2.2-a | 数据层 | StorageBackend 抽象 + SQLite schema + 迁移脚本 | — | SQLite 建库、旧 json 元数据导入成功 | 4d |
| P2.2-b | 数据层 | 用户/组织/项目模型 + 认证(bCrypt/API Key) | P2.2-a | 注册/登录/建项目 PASS，密码不落明文 | 4d |
| P2.2-c | 数据层 | 设计结果持久化 + 租户隔离查询 | P2.2-b | 存设计包→检索→隔离验证（跨 org 不可见） | 3d |
| P2.3-a | API 脚手架 | 路由收敛 + 认证中间件 | P2.2-b | 无 Key 401、有 Key 200，现有功能不退化 | 3d |
| P2.3-b | API 脚手架 | 配额/计量表 + license 校验模块 | P2.3-a | 计量写入正确，license 失效降级开源集 | 3d |
| P2.3-c | API 脚手架 | 插件注册 manifest + 加载器 | P2.3-a | ext_oracle 经插件接口加载 PASS | 2d |

**整体工期估算**：P2.1 ≈ 1 周；P2.2 ≈ 2–3 周；P2.3 ≈ 2 周；合计约 **5–6 周**（可并行部分子任务）。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 内核污染（商业化层 import 拖入） | 强制 import 边界 + CI 门禁（开源包独立 import 仍成立） |
| 数据迁移丢失 | 旧 json 保留为备份，双写灰度，迁移脚本可回滚 |
| 认证安全 | bCrypt、rate limit、HTTPS only、API Key 仅存 hash |
| 单进程性能（SQLite 写锁） | 读多写少场景可行；多 worker 时走 Postgres 选项 |
| 主权合规 | 商业层不引入 A 级禁借组件；依赖全 BSD 兼容（numpy/scipy） |

---

## 6. 主权与合规边界

- 开源内核保持 **MIT**、零依赖可独立。
- 商业增值层采用**分层开源**：部署外壳(P2.1) + 数据层基础设施(P2.2) 保持开源（产品化基建、不含商业逻辑，利生态自托管）；仅 P2.3 的 **license 校验 / 配额计量 / 多租户治理** 闭源（收入相关逻辑，守护城河），放独立 repo（如 `lda-cloud/`）。开源版功能完整、永久免费（MIT），商业版订阅为主、按量可选。
- 不引入 GPL 组件（numpy/scipy 为 BSD 兼容，安全）。

---

## 7. 里程碑与验收判据（总）

- **P2.1 收口**：Docker 一键起 + 健康检查 + 现有 57 面板/端点全 PASS（零破坏）。
- **P2.2 收口**：注册/登录/建项目/存设计结果/多用户隔离 全 PASS；密码与 license 不落明文。
- **P2.3 收口**：API Key 认证 + 配额计量 + license 占位 + 插件注册 全 PASS；开源单用户模式功能完整。

---

## 8. 决策结论（杜先生已拍板，2026-08-26）

| # | 决策项 | 结论 |
|---|--------|------|
| 1 | 商业增值层开源 / 闭源 | **分层开源**：部署外壳(P2.1)+数据层基础设施(P2.2) 开源；仅 P2.3 的 license校验/配额计量/多租户治理 闭源（放独立 repo `lda-cloud/`） |
| 2 | 数据层起步 | **SQLite 起步 + `StorageBackend` 抽象兼容 Postgres/D1**（采纳建议） |
| 3 | 自托管 Docker / SaaS | **同时做**：P2.1 交付自托管 Docker 镜像 + 架构层 SaaS-ready（无状态/多租户/配置驱动）；**不建 SaaS 运营基础设施**（计费/编排/运维） |
| 4 | License 模型 | **开源版永久免费完整(MIT) + 商业版订阅为主、按量可选**（采纳建议） |
| 5 | 交付节奏 | **P2.1 → P2.2 → P2.3 三子阶段逐步交付**，每步可验收、可回滚（采纳建议） |

---

*起草 + 定稿：2026-08-26 · 基于代码核实（app.py / deploy.py / requirements.txt / 散落 json 数据层）。5 项决策已定，待杜先生说「开始」后按 P2.1 执行。*
