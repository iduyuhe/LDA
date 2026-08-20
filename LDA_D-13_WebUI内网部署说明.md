# LDA · WebUI 内网演示部署说明（D-13）

> 文档编号：LDA-DEPLOY-013
> 版本：v1.0（2026-08-20）
> 目标：把"设计→仿真→验收"可视化闭环部署到内网演示机，供顾问委 / 晶圆厂 / 社区贡献者现场观看。

---

## 1. 部署目标

把 `lda/lda_webui/app.py`(零依赖 HTTP 服务)跑在内网演示机,**同一内网任意机器浏览器访问**,演示已验证闭环:

| 面板 | 内容 | 内核来源 |
|---|---|---|
| ① 验证裁判 | B1–B11 确定性比对 | harness |
| ② Agent 设计闭环 | 布拉格镜 FDTD↔TMM | design_loop |
| ③ 题库/PDK | B1–B11 + 已登记 PDK | benchmarks / pdk |
| ④ 多端口耦合器件验收锚 | Y 分支能流平衡 / DC κ 对比 | D-01 coupler_loop |
| ⑤ 多波长宽带闭环 | 布拉格全波段谱形 + 收敛轨迹 | D-03 multiband_loop |
| ⑥ L0 统一 IR | 方向耦合器/分束器/微环/Transmon DSL | D-05 lda_ir |
| ⑦ 环形谱形逆设计 | 调 R 命中 FSR 谱形 + 洛伦兹梳图 | D-11 ring_loop |

## 2. 前置条件

- Python 3.11+(推荐 LDA 的 venv:`lda_cuda_venv`,含 numpy/scipy/torch)。
- **GPU(torch CUDA)可选**:有 GPU → ④ 耦合器面板走**实时 FDTD↔ORACLE 交叉对拍**;无 GPU → 诚实退回 **ORACLE 真值演示**(不卡死,标注"实时 FDTD 需在 GPU 演示机运行")。其余面板纯 numpy/解析,无 GPU 亦可。
- 内网可达(演示机与观众同网段;必要时开放端口)。

## 3. 部署步骤(推荐 deploy.py)

```bash
cd <仓库根>
# 1) 启动(默认端口 8787,监听 0.0.0.0)
<venv>/Scripts/python.exe lda/lda_webui/deploy.py start
# 或指定端口
<venv>/Scripts/python.exe lda/lda_webui/deploy.py start --port 9000

# 2) 状态 + 健康检查(GET /api/status)
<venv>/Scripts/python.exe lda/lda_webui/deploy.py status

# 3) 停止 / 重启
<venv>/Scripts/python.exe lda/lda_webui/deploy.py stop
<venv>/Scripts/python.exe lda/lda_webui/deploy.py restart
```

启动后终端会打印内网访问地址(本机 IP 列表);也可手动查:

```bash
# Linux/macOS
hostname -I
# Windows
ipconfig
```

浏览器访问 `http://<演示机IP>:8787/`。

**不借助脚本手动跑**(调试用):

```bash
export LDA_WEBUI_PORT=8787
<venv>/Scripts/python.exe lda/lda_webui/app.py
```

## 4. 运维

| 项 | 位置 |
|---|---|
| pid 文件 | `lda/lda_webui/webui.pid` |
| 日志 | `lda/lda_webui/webui.log`(stdout/stderr 追加) |
| 端口 | 环境变量 `LDA_WEBUI_PORT` 或 `deploy.py --port` |
| 健康检查 | `GET /api/status`(deploy.py status 自动调) |

## 5. 端点一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 控制台页面 |
| GET | `/api/status` | 系统落地状态(层数/PDK 数) |
| GET | `/api/benchmarks` | B1–B11 题库定义 |
| GET | `/api/pdks` | 已登记 PDK + 模板 |
| POST | `/api/verify` | 真跑 harness B1–B11(可 perturb) |
| POST | `/api/agent_loop` | 布拉格镜 agent 闭环 |
| POST | `/api/band_loop` | D-03 多波长宽带闭环 |
| POST | `/api/ring_loop` | **D-11 环形谱形逆设计闭环** |
| POST | `/api/coupler_loop` | D-01 耦合器/分束器验收锚 |
| POST | `/api/ir_demo` | D-05 L0 IR v0.2 构造+DSL+校验 |
| POST | `/api/pdk_design` | 501(依赖 D-09 PDK 接入,规划中) |
| POST | `/api/pdk_compare` | 501(同上) |

## 6. 安全与边界(诚实声明)

- **内网演示用途**:服务绑定 `0.0.0.0` 面向内网,未做鉴权——**勿直接暴露公网**;如需公网演示,前置 VPN / 反向代理 + 鉴权。
- **LLM 不进判决路径**:所有 PASS/FAIL 由死代码标量比对(物理定律锚)决定;webui 不调用 LLM。
- **耦合器面板无 GPU 降级**:显示 ORACLE 真值并诚实标注,不伪装实时 FDTD。
- 研究级演示,非商业签核工具。

## 7. 验收清单(部署后)

1. `deploy.py status` → `运行中 pid=... layers=8 pdks=5`(健康检查 PASS)
2. 内网另一台机器浏览器打开 `http://<演示机IP>:8787/` → 七个面板可见
3. ⑤ 多波长 / ⑦ 环形 / ④ 耦合器 三个闭环面板点"运行" → 出图表与 PASS 报告
4. `deploy.py stop` → 服务停止;`deploy.py restart` → 恢复
