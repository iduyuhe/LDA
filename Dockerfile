# syntax=docker/dockerfile:1
# ============================================================
# LDA WebUI · 自托管部署镜像（P2.1）
# 零强云绑定：本地 Docker / 私有云 / 边缘机均可跑。
# 镜像仅含核心依赖（numpy/scipy/jsonschema），保持小体积、主权可控。
# ============================================================

# ---- builder：从源码构建可复现 wheel ----
FROM python:3.11-slim AS builder
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /src
COPY . /src
RUN pip install --quiet --upgrade pip build \
    && python -m build --wheel --outdir /dist

# ---- runtime：仅核心依赖 + 安装 wheel ----
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    LDA_WEBUI_PORT=8787 \
    DEPLOY_MODE=selfhost \
    LDA_HOME=/data
WORKDIR /app

# 核心运行依赖（可选重依赖 numba/torch 不进默认镜像，保持轻量）
RUN pip install --no-cache-dir numpy scipy jsonschema

# 安装构建产物 wheel（含 lda_webui/static + examples 数据）
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# 数据持久化卷（P2.2 数据库、报告、设计结果将落此）
VOLUME ["/data"]
EXPOSE 8787

# 前台运行：进程即服务进程，便于容器探针与健康检查
# 用 -c 显式导入并调用 main()，对 namespace 包（lda/ 无 __init__.py）更稳健
CMD ["python", "-c", "from lda.lda_webui import app; app.main()"]
