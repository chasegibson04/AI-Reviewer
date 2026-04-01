#!/bin/bash
set -e

# Configuration
REPO_URL="https://github.com/TurboQuant/llama.cpp.git"
VENDOR_DIR="$(dirname "$0")/../vendor"
TARGET_DIR="$VENDOR_DIR/llama-cpp-turboquant"

mkdir -p "$VENDOR_DIR"

echo "[network] github | clone llama-cpp-turboquant | started"
if [ ! -d "$TARGET_DIR" ]; then
    git clone "$REPO_URL" "$TARGET_DIR"
    echo "[network] github | clone llama-cpp-turboquant | success"
else
    echo "[info] llama-cpp-turboquant already exists. Updating..."
    cd "$TARGET_DIR" && git pull
fi

echo "[info] Starting build process for llama-cpp-turboquant..."
cd "$TARGET_DIR"
mkdir -p build
cd build
cmake ..
cmake --build . --config Release -j $(nproc || sysctl -n hw.ncpu)

echo "[info] Build complete. llama-server is located at $TARGET_DIR/build/bin/llama-server"
