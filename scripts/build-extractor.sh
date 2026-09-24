#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .build
swiftc -O -module-cache-path .build/module-cache scripts/extract.swift -o .build/extract
printf '本地 PDF/OCR 提取器已构建。\n'
