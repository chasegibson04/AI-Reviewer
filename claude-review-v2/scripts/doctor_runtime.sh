#!/bin/bash

echo "Running doctor:runtime diagnostics for claude-review-v2..."

echo "[Check] Ollama CLI installed?"
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama could not be found. Please install Ollama."
    exit 1
else
    ollama --version
    echo "✅ Ollama installed."
fi

echo "[Check] Ollama service running?"
OLLAMA_RESPONSE=$(curl -s http://localhost:11434/api/tags || echo "failed")
if [ "$OLLAMA_RESPONSE" = "failed" ]; then
    echo "❌ Could not reach Ollama API at http://localhost:11434. Please run 'ollama serve'."
    exit 1
else
    echo "✅ Ollama service is reachable."
fi

echo "[Check] Local models available?"
MODELS=$(echo "$OLLAMA_RESPONSE" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
if [ -z "$MODELS" ]; then
    echo "⚠️ No local models found. You may need to pull a model (e.g., 'ollama pull mistral-small3.2:latest')."
else
    echo "✅ Local models found:"
    echo "$MODELS"
fi

echo ""
echo "Doctor checks passed. System is ready for local-first review."
exit 0
