#!/usr/bin/env bash
# ============================================================
# LDA · B级依赖「本地主权根」镜像脚本
# ------------------------------------------------------------
# 用途：在杜先生【本地网络稳定、可访问 github.com】的机器上，
#       直接将 5 个 B 级开源依赖 clone --mirror 到本地，作为
#       「主权根（root of truth）+ 离线冷备」；并可选同步到
#       Gitee 公开门面（社区入口）。
#
# 策略：本地为根、Gitee 为门面（双轨）。纯本地无开源入口，
#       纯 Gitee 不够彻底；两者并存才是真·主权 + 真·开源。
#
# 用法：
#   LOCAL_ROOT=~/.lda_mirror GITEE_TOKEN=xxxx GITEE_USER=i4hub \
#     bash LDA_本地镜像一键脚本.sh
#
#   - LOCAL_ROOT : 本地镜像根目录（默认 ~/.lda_mirror）
#   - GITEE_TOKEN: 可选；填了才同步到 Gitee 门面
#   - GITEE_USER : Gitee 账号（默认 i4hub）
# ============================================================
set -euo pipefail

LOCAL_ROOT="${LOCAL_ROOT:-$HOME/.lda_mirror}"
GITEE_TOKEN="${GITEE_TOKEN:-}"
GITEE_USER="${GITEE_USER:-i4hub}"

# 本地仓名 | GitHub 上游 | 许可证
REPOS=(
  "gdsfactory|gdsfactory/gdsfactory|MIT"
  "sax|gdsfactory/sax|Apache-2.0"
  "mpb|NanoComp/mpb|GPL-2.0"
  "meep|NanoComp/meep|GPL-2.0"
  "klayout|KLayout/klayout|GPL-3.0"
)

mkdir -p "$LOCAL_ROOT"

for entry in "${REPOS[@]}"; do
  IFS='|' read -r name up lic <<< "$entry"
  echo "=== [$name] 本地主权根 clone --mirror github.com/$up ==="
  rm -rf "$LOCAL_ROOT/$name.git"
  git clone --mirror "https://github.com/$up.git" "$LOCAL_ROOT/$name.git"

  # 清掉 GitHub 的 pull refs（PR 临时引用，非源码，避免噪音）
  git -C "$LOCAL_ROOT/$name.git" for-each-ref --format='delete %(refname)' refs/pull/ 2>/dev/null \
    | git -C "$LOCAL_ROOT/$name.git" update-ref --stdin 2>/dev/null

  # 可选：同步到 Gitee 门面（公开社区入口）
  if [ -n "$GITEE_TOKEN" ]; then
    echo "=== [$name] 同步到 Gitee 门面 (gitee.com/$GITEE_USER/$name) ==="
    git -C "$LOCAL_ROOT/$name.git" push --mirror \
      "https://oauth2:$GITEE_TOKEN@gitee.com/$GITEE_USER/$name.git" 2>&1 | tail -3 \
      || echo "  (push 失败不影响本地主权根)"
  fi
  echo "=== [$name] DONE (license=$lic) ==="
done

echo
echo "本地主权根完成： $LOCAL_ROOT"
echo "离线构建验证示例："
echo "  git -C $LOCAL_ROOT/gdsfactory.git archive HEAD | tar -t   # 抽查文件树"
echo "后续：接 PyPI wheel 冷备(--no-index) + SBOM 扫描(美原产占比)。"
