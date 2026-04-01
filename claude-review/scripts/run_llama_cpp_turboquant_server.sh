#!/bin/bash

# Defaults
PORT=8080
MODEL=""
VENDOR_DIR="$(dirname "$0")/../vendor"
SERVER_BIN="$VENDOR_DIR/llama-cpp-turboquant/build/bin/llama-server"

# Help
function usage() {
    echo "Usage: $0 --model <path_to_gguf> [--port <port>] [--turbo-cache <type>]"
    exit 1
}

TURBO_FLAG=""

# Parse args
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --model) MODEL="$2"; shift ;;
        --port) PORT="$2"; shift ;;
        --turbo-cache) TURBO_FLAG="--turbo-cache $2"; shift ;;
        *) usage ;;
    esac
    shift
done

if [ -z "$MODEL" ]; then usage; fi

# Verify server bin exists
if [ ! -f "$SERVER_BIN" ]; then
    echo "[error] TurboQuant server not found at $SERVER_BIN. Run scripts/install_llama_cpp_turboquant.sh first."
    exit 1
fi

echo "[backend] llama.cpp-turboquant | starting server on port $PORT..."
if [ ! -z "$TURBO_FLAG" ]; then
    echo "[backend] llama.cpp-turboquant | turbo cache flags detected | ok"
fi

"$SERVER_BIN" -m "$MODEL" --port "$PORT" $TURBO_FLAG --api
