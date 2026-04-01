#!/bin/bash

# Defaults
PORT=8080
MODEL=""
VENDOR_DIR="$(dirname "$0")/../vendor"
SERVER_BIN="$VENDOR_DIR/llama.cpp/build/bin/llama-server"

# Help
function usage() {
    echo "Usage: $0 --model <path_to_gguf> [--port <port>]"
    exit 1
}

# Parse args
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --model) MODEL="$2"; shift ;;
        --port) PORT="$2"; shift ;;
        *) usage ;;
    esac
    shift
done

if [ -z "$MODEL" ]; then usage; fi

# Fallback to PATH if vendor bin doesn't exist
if [ ! -f "$SERVER_BIN" ]; then
    SERVER_BIN="llama-server"
fi

echo "[backend] llama.cpp | starting server on port $PORT..."
"$SERVER_BIN" -m "$MODEL" --port "$PORT" --api
