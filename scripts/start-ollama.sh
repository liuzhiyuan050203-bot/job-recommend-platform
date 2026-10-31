#!/usr/bin/env bash
# ==============================================================================
# 启动本地 Ollama 服务并确保基础模型 (默认 qwen2.5:3b) 准备就绪
# ==============================================================================
set -euo pipefail

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1}"
LOG_FILE="/tmp/ollama-serve.log"
MODELS_DIR="${HOME}/models"
HF_BASE="${HF_ENDPOINT:-https://huggingface.co}"
GGUF_URL="${HF_BASE}/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
GGUF_FILE="${MODELS_DIR}/qwen2.5-3b-instruct-q4_k_m.gguf"
MODELFILE_PATH="${MODELS_DIR}/Modelfile"

# 1. 检查 Ollama 服务是否已在运行
is_ollama_ready() {
    curl -s --connect-timeout 2 "http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1
}

if is_ollama_ready; then
    echo "==> Ollama 服务已在运行 (http://${OLLAMA_HOST}:${OLLAMA_PORT})"
else
    echo "==> 正在后台启动 Ollama 服务并记录日志至 ${LOG_FILE}..."
    nohup ollama serve > "${LOG_FILE}" 2>&1 &

    # 等待服务就绪 (最长等待 30 秒)
    echo -n "==> 等待 Ollama 服务响应"
    READY=0
    for i in $(seq 1 30); do
        if is_ollama_ready; then
            READY=1
            echo " [就绪]"
            break
        fi
        echo -n "."
        sleep 1
    done

    if [ "$READY" -ne 1 ]; then
        echo " [超时失败]"
        echo "错误: Ollama 服务未能成功启动，请查看日志: ${LOG_FILE}" >&2
        exit 1
    fi
fi

# 2. 检查指定模型是否存在
has_model() {
    ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL}[[:space:]]"
}

if has_model; then
    echo "==> 模型 '${OLLAMA_MODEL}' 已就绪"
    exit 0
fi

echo "==> 模型 '${OLLAMA_MODEL}' 未在当前模型列表中，尝试通过 ollama pull 下载..."
if ollama pull "${OLLAMA_MODEL}"; then
    echo "==> 成功拉取模型 '${OLLAMA_MODEL}'"
    exit 0
fi

echo "==> 'ollama pull' 失败或因网络隔离受阻，正在从 HuggingFace 镜像源下载 GGUF 权重并通过 Modelfile 本地创建..."
mkdir -p "${MODELS_DIR}"

if [ ! -f "${GGUF_FILE}" ]; then
    echo "==> 正在从 ${GGUF_URL} 下载 GGUF 权重文件..."
    curl -L -C - --retry 3 -o "${GGUF_FILE}" "${GGUF_URL}"
else
    echo "==> 检测到已有本地 GGUF 权重文件: ${GGUF_FILE}"
fi

# 写入 Modelfile 配置
cat <<EOF > "${MODELFILE_PATH}"
FROM ${GGUF_FILE}
PARAMETER temperature 0.3
PARAMETER num_ctx 4096
EOF

echo "==> 正在执行 'ollama create ${OLLAMA_MODEL} -f ${MODELFILE_PATH}'..."
ollama create "${OLLAMA_MODEL}" -f "${MODELFILE_PATH}"

if has_model; then
    echo "==> 模型 '${OLLAMA_MODEL}' 本地构建成功并已就绪"
    exit 0
else
    echo "错误: 创建模型 '${OLLAMA_MODEL}' 失败" >&2
    exit 1
fi
