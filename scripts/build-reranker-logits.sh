#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PREFIX=${LLAMA_CPP_PREFIX:-/opt/homebrew}
OUTPUT=${1:-"$ROOT/build/qwen-reranker-logits"}

mkdir -p "$(dirname -- "$OUTPUT")"
clang++ -std=c++17 -O2 -Wall -Wextra -Werror \
  -I"$PREFIX/include" \
  "$ROOT/scripts/qwen-reranker-logits.cpp" \
  -L"$PREFIX/lib" -Wl,-rpath,"$PREFIX/lib" -lllama \
  -o "$OUTPUT"
printf '%s\n' "$OUTPUT"
