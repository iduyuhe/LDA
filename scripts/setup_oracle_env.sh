#!/usr/bin/env bash
# =============================================================================
# LDA 外部 ORACLE（Meep）隔离环境一键安装脚本
# -----------------------------------------------------------------------------
# 背景（2026-08-30 战略审计 R2/R20）：
#   LDA 声称「物理定律锚 + 实证大数据锚」双 ground，但外部 ORACLE 默认不通——
#   `oracle_field.py` 需环境变量 LDA_MEEP_PY 指向一个装了 Meep 的**隔离**解释器，
#   未配置时直接 return None。结果是「双 ground 交叉验证」这条核心卖点，
#   外部技术买家来验货时无法现场演示。本脚本把这条链路变成一条命令。
#
# 🔴 红线：Meep 是 GPL 软件（B 级「借今踢后」依赖）。它**必须**装在隔离环境，
#    绝不进 LDA 主环境、绝不进依赖清单、其源码绝不并入本仓库——
#    LDA 只通过子进程 JSON 契约调用它取真值，主仓库保持 MIT 纯净。
#
# 用法：
#   bash scripts/setup_oracle_env.sh                 # 自动选择方式（推荐 conda）
#   bash scripts/setup_oracle_env.sh --method conda  # 指定 conda/mamba/micromamba
#   bash scripts/setup_oracle_env.sh --method docker # 用官方镜像
#   bash scripts/setup_oracle_env.sh --method manual --meep-py /path/to/python
#   bash scripts/setup_oracle_env.sh --self-test-only  # 只跑自测（已装好时）
#
# 成功后会生成 `.oracle_env`（不入库），内容形如：
#   export LDA_MEEP_PY=/path/to/isolated/python
# 使用前：`source .oracle_env`
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORACLE_SCRIPT="$REPO_ROOT/lda/ext_oracle/meep_oracle.py"
ENV_NAME="${LDA_MEEP_ENV:-lda-meep}"
ENV_FILE="$REPO_ROOT/.oracle_env"

METHOD="auto"
MEEP_PY=""
SELF_TEST_ONLY=0

log()  { printf '\033[1;34m[LDA-ORACLE]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

usage() {
    sed -n '12,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --method)        METHOD="$2"; shift 2 ;;
        --meep-py)       MEEP_PY="$2"; shift 2 ;;
        --self-test-only) SELF_TEST_ONLY=1; shift ;;
        -h|--help)       usage ;;
        *) err "未知参数: $1"; usage; exit 2 ;;
    esac
done

have() { command -v "$1" >/dev/null 2>&1; }

# -----------------------------------------------------------------------------
# 1. 探测安装方式
# -----------------------------------------------------------------------------
detect_method() {
    if [[ "$METHOD" != "auto" ]]; then echo "$METHOD"; return; fi
    if have micromamba; then echo micromamba
    elif have mamba;    then echo mamba
    elif have conda;    then echo conda
    elif have docker;   then echo docker
    else echo none; fi
}

install_with_conda() {
    local tool="$1"
    log "使用 $tool 创建隔离环境 '$ENV_NAME' 并安装 pymeep（conda-forge）"
    log "此过程需下载数百 MB，可能需要 10-30 分钟，请耐心等待…"

    case "$tool" in
        conda)
            # shellcheck disable=SC1091
            eval "$(conda shell.bash hook 2>/dev/null || true)"
            conda create -y -n "$ENV_NAME" -c conda-forge python=3.11 pymeep
            ;;
        mamba|micromamba)
            "$tool" create -y -n "$ENV_NAME" -c conda-forge python=3.11 pymeep
            ;;
    esac

    # 定位隔离环境的 python 解释器
    local prefix
    if [[ "$tool" == "micromamba" ]]; then
        prefix="$(micromamba info --json 2>/dev/null | grep -o '"base environment": *"[^"]*"' | cut -d'"' -f4)/envs/$ENV_NAME"
    else
        prefix="$(conda info --base 2>/dev/null)/envs/$ENV_NAME"
    fi

    if [[ -x "$prefix/bin/python" ]]; then
        MEEP_PY="$prefix/bin/python"
    else
        err "未能定位隔离环境解释器（期望 $prefix/bin/python）"
        err "请手动指定：bash $0 --method manual --meep-py /path/to/python"
        return 1
    fi
}

install_with_docker() {
    log "使用 Docker 拉取 Meep 官方镜像（隔离性最好）"
    docker pull choganp/meep || docker pull hsorby/meep
    warn "Docker 方式需自行挂载仓库并暴露解释器路径，本脚本不自动接管。"
    warn "装好后请用 --method manual --meep-py <容器内 python 路径> 完成配置。"
    return 1
}

# -----------------------------------------------------------------------------
# 2. 自测：确认 Meep 可用且 ORACLE 能返回真值
# -----------------------------------------------------------------------------
self_test() {
    local py="$1"
    log "自测 1/2：确认隔离环境可导入 meep"
    if ! "$py" -c "import meep; print('meep', meep.__version__)" 2>/dev/null; then
        err "该解释器无法 import meep：$py"
        return 1
    fi

    log "自测 2/2：通过 JSON 契约调用 ORACLE（B7 波导交叉串扰）"
    local out
    out=$("$py" "$ORACLE_SCRIPT" --bid B7 \
          --params '{"w_core":0.4,"h_core":0.22,"n_si":3.48,"n_clad":1.44,"wl":1.55}' \
          --json 2>&1) || { err "ORACLE 调用失败："; echo "$out"; return 1; }
    echo "    返回: $out"

    if echo "$out" | grep -q '"value": *null'; then
        warn "ORACLE 返回 value=null（B7 未给出真值）——请检查 meep_oracle.py 的 B7 实现"
        return 1
    fi
    log "自测通过：外部 ORACLE（Meep）已能返回场级真值"
}

write_env_file() {
    cat > "$ENV_FILE" <<EOF
# 由 scripts/setup_oracle_env.sh 生成（不入库，见 .gitignore）
# 使用前执行：source .oracle_env
export LDA_MEEP_PY="$MEEP_PY"
EOF
    log "已写入 $ENV_FILE"
    log "生效方式：source $ENV_FILE"
}

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------
main() {
    if [[ ! -f "$ORACLE_SCRIPT" ]]; then
        err "找不到 ORACLE 脚本：$ORACLE_SCRIPT"
        exit 1
    fi

    if [[ $SELF_TEST_ONLY -eq 1 ]]; then
        [[ -n "$MEEP_PY" ]] || { err "--self-test-only 需配合 --meep-py"; exit 2; }
        self_test "$MEEP_PY"
        exit $?
    fi

    if [[ -z "$MEEP_PY" ]]; then
        local m
        m="$(detect_method)"
        log "检测到可用方式：$m"
        case "$m" in
            conda|mamba|micromamba) install_with_conda "$m" ;;
            docker)                 install_with_docker ;;
            none)
                err "未检测到 conda/mamba/micromamba/docker。"
                err "请任选其一后重试，或直接指定已有环境："
                err "  bash $0 --method manual --meep-py /path/to/python"
                exit 1
                ;;
            *) err "未知方式：$m"; exit 1 ;;
        esac
    fi

    self_test "$MEEP_PY" || exit 1
    write_env_file

    log "完成。现在可以复现「双 ground 交叉验证」："
    log "  source $ENV_FILE"
    log "  cd lda && LDA_MEEP_PY=\$LDA_MEEP_PY python -c \"from lda_harness.oracle_field import resolve_field_oracle; print(resolve_field_oracle('B7', {'w_core':0.4,'h_core':0.22,'n_si':3.48,'n_clad':1.44,'wl':1.55}))\""
}

main "$@"
