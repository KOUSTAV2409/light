#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$ROOT_DIR/packaging/flatpak/com.koustav.light.yml"
BUILD_DIR="$ROOT_DIR/build/flatpak"
REPO_DIR="$ROOT_DIR/build/flatpak-repo"
OUTPUT_DIR="$ROOT_DIR/dist"
OUTPUT="$OUTPUT_DIR/light.flatpak"

command -v flatpak-builder >/dev/null 2>&1 || {
  echo "flatpak-builder is required." >&2
  echo "Ubuntu/Debian: sudo apt install flatpak flatpak-builder" >&2
  exit 1
}

mkdir -p "$OUTPUT_DIR"
flatpak-builder --force-clean --repo="$REPO_DIR" "$BUILD_DIR" "$MANIFEST"
flatpak build-bundle "$REPO_DIR" "$OUTPUT" com.koustav.light

echo "Built: $OUTPUT"
