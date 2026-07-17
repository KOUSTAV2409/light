#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${1:-0.1.0}"
PACKAGE_VERSION="${VERSION//-/.}"
PACKAGE_NAME="light-launcher"
STAGE="$ROOT_DIR/build/debian/${PACKAGE_NAME}_${PACKAGE_VERSION}_all"
OUTPUT="$ROOT_DIR/dist"

command -v dpkg-deb >/dev/null 2>&1 || {
  echo "dpkg-deb is required (install dpkg-dev)." >&2
  exit 1
}

rm -rf "$STAGE"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/lib/light" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/doc/$PACKAGE_NAME" \
  "$OUTPUT"

cp -a "$ROOT_DIR/light" "$STAGE/usr/lib/light/"
find "$STAGE/usr/lib/light" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE/usr/lib/light" -type f -name '*.py[co]' -delete

install -m 0644 \
  "$ROOT_DIR/packaging/debian/com.koustav.light.desktop" \
  "$STAGE/usr/share/applications/com.koustav.light.desktop"
install -m 0644 "$ROOT_DIR/README.md" "$STAGE/usr/share/doc/$PACKAGE_NAME/README.md"

cat > "$STAGE/usr/bin/light" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/light${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m light "$@"
EOF
chmod 0755 "$STAGE/usr/bin/light"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PACKAGE_NAME
Version: $PACKAGE_VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, xdg-utils
Recommends: fd-find
Maintainer: Light Contributors
Description: AI-first application launcher for Linux
 Light provides application and file search, system actions, calculator,
 web search, and optional web-grounded OpenAI answers.
EOF

dpkg-deb --build --root-owner-group \
  "$STAGE" \
  "$OUTPUT/${PACKAGE_NAME}_${PACKAGE_VERSION}_all.deb"

echo "Built: $OUTPUT/${PACKAGE_NAME}_${PACKAGE_VERSION}_all.deb"
