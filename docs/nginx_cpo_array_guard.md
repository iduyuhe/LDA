# 生产止血 · `/api/cpo_array` nginx 护栏

## 背景（为什么需要）

`GET /api/cpo_array` 是**无鉴权 + 每次实跑十万级器件**（build+DRC+LVS ~4–8s）的重计算端点，运行在
`ThreadingHTTPServer`（每请求一线程）下。一旦被并发请求打中（外部扫描 / 监控轮询 / 反复自测），
多个重计算会并行吃满 CPU/内存，把生产服务器打爆。

根治 = 部署 **v0.9.4**（端点自带「输入硬上限 + 全局串行锁 + 默认缓存」三护栏，commit `e1ba13a`）。
在 v0.9.4 部署前，先用下面 nginx 规则在**网关层**掐掉并发暴露，立即止血。

---

## 方案 A · 硬阻断（立即止血，验证功能暂不可用）

最稳。把该端点直接 403，nginx 根本不转发到后端。

在站点 server 块内、**通用的 `/` proxy 规则之前**插入：

```nginx
    # 临时止血：阻断无鉴权重计算端点，防并发打爆（v0.9.4 部署后可删）
    location = /api/cpo_array {
        deny all;
        return 403;
    }
```

---

## 方案 B · 限流（保留验证能力，但限并发）

若想保留「外部可 curl 验货」能力，用 `limit_req` 把单 IP 限到 ~1 req/s、突发 2：

**http 上下文（nginx.conf 或 conf.d 顶层，只能写一次）：**

```nginx
limit_req_zone $binary_remote_addr zone=cpo_zone:10m rate=1r/s;
```

**server 块内（通用 proxy 之前）：**

```nginx
    location = /api/cpo_array {
        limit_req zone=cpo_zone burst=2 nodelay;
        proxy_pass http://127.0.0.1:3006;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
```

> 注意：`limit_req_zone` 必须在 **http** 上下文，不能写在 server 内；`location` 块在 server 内。

---

## 应用步骤

```bash
# 1)（可选）若服务器已因在飞重计算卡死，先杀光在飞进程
systemctl restart lda-webui

# 2) 校验 nginx 配置语法
nginx -t

# 3) 热重载（不中断现有连接）
systemctl reload nginx
```

## 长期

部署 v0.9.4 后，端点自身已带三护栏（输入上限 / 串行锁 / 缓存），上述 nginx 规则可移除：

```bash
python C:/Users/Administrator/.workbuddy/skills/lda-prod-deploy/scripts/remote_deploy.py <密码> --expect-head e1ba13a
```
