# LDA 设计商店 · 阶段1 MVP 技术方案（下载端点 + 简易授权）

> 目标：在不接入支付的前提下，验证「货架 → 设计就绪包 → 下载」的完整交付链路。先选 2–3 个货架做试点，跑通后再进阶段2（支付闭环）。

## 一、范围与边界

- ✅ 做：选 2–3 货架生成「设计就绪包」；WebUI 新增下载端点 + 简易授权（兑换码 / 邮箱）。
- ❌ 不做：支付（阶段2）、真实 foundry PDK（C 阶段）、量子设计出海。
- 诚实分层：新增 `honest_tier = "design_ready"` 区别于现有 `前瞻预研`；元数据明示层级，避免把预研当成品。

## 二、试点货架

- `IM-PSM4-SHELF`（无源链路，光子）
- `IM-CWDM4-SHELF`（无源链路，光子）
- `GC-CPO-8CH`（系统级，光子；或替换为量子包，视出口管制结论）

## 三、交付包结构（zip）

```
<id>_design_ready.zip
 ├─ layout/<id>.gds            # chip_layout / pipeline_realize 生成
 ├─ netlist/<id>.sp            # 网表
 ├─ report/<id>_sim_report.md  # 仿真报告（含死锚比对）
 ├─ drc_lvs/<id>_drc_lvs.json  # gds_drc / lvs 结果
 ├─ process/<id>_corner.md     # 工艺角说明（主权近似，非 foundry）
 ├─ LICENSE.md                 # EULA（见文档 01_EULA_template.md）
 └─ HONESTY.md                 # 诚实声明（非 foundry 认证 / 非本团队流, 片）
```

## 四、打包流程（新增模块 `lda_l2/ship_package.py`）

1. 取货架 `composition`（⊂ GP-\*）→ 调 `design_pipeline` 真跑。
2. 调 `chip_layout` / `pipeline_realize` 出 GDS；`gds_drc` / `lvs` 出结果。
3. 渲染报告（复用现有报告逻辑）。
4. 组装 zip → 存 `dist/packages/<id>.zip`（**不入 git**，加入 .gitignore）。

## 五、端点设计（复用 app.py 现有 Bearer 分发）

- `GET /api/shelf/{id}/download?token=<code>`：校验兑换码有效性 → 返回 `application/zip` 流。
- 授权表：`dist/licenses.json`（`{code: {id, email, used, created_at, max_uses}}`）；本地 SQLite 亦可。
- 兑换码生成：`secrets.token_urlsafe(16)`，不可猜、限次（默认 1）、可吊销。
- 安全：无效 code → 404；zip 路径白名单，禁止 `..` 穿越；Bearer 鉴权保留。

## 六、前端（insights.html）

- 货架卡片加「下载」按钮（未授权态）→ 输入兑换码 → `fetch` 触发下载。
- 免费预览（看）与下载（授权）双态区分，文案明示层级。

## 七、验证

- 试点包生成成功、zip 可解、GDS / 报告 / DRC-LVS 齐全。
- 端点：有效码 → 200 zip；无效码 → 404；越权路径 → 404。
- 不动 CI core（维持 69）；新增 smoke 仅本地，不进核心守护。

## 八、阶段2 衔接

- 支付：微信支付下单 → 支付成功 → 写 `licenses.json`（生成 code）→ 通知下载。
- 主体 / 税务（文档 02）就绪后启用对外收费。

## 九、与现有红线的一致性

- 设计仍由 GP-\* 级联 + 真实引擎生成，零新物理。
- 诚实声明随包交付，与 LDA「物理定律锚 / LLM 不进判决」红线一致。
- 开源引擎继续免费；付费的是交付物 / 设计授权，不冲突。
