#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOGGLE_COMMAND="$ROOT_DIR/run.sh toggle"
DESKTOP="${XDG_CURRENT_DESKTOP:-unknown}"
ACTION="${1:-install}"

install_gnome() {
  local schema="org.gnome.settings-daemon.plugins.media-keys"
  local item_schema="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
  local path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/light/"

  if ! command -v gsettings >/dev/null 2>&1; then
    echo "gsettings is required for GNOME shortcut installation." >&2
    exit 1
  fi

  local current updated
  current="$(gsettings get "$schema" custom-keybindings)"
  updated="$(CURRENT="$current" PATH_TO_ADD="$path" python3 - <<'PY'
import ast
import os

try:
    values = list(ast.literal_eval(os.environ["CURRENT"]))
except (SyntaxError, ValueError):
    values = []
path = os.environ["PATH_TO_ADD"]
if path not in values:
    values.append(path)
print(repr(values))
PY
)"

  gsettings set "$schema" custom-keybindings "$updated"
  gsettings set "$item_schema:$path" name "Light Launcher"
  gsettings set "$item_schema:$path" command "$TOGGLE_COMMAND"
  gsettings set "$item_schema:$path" binding "<Alt>space"

  echo "Installed GNOME/Wayland shortcut: Alt+Space"
  echo "Command: $TOGGLE_COMMAND"
}

uninstall_gnome() {
  local schema="org.gnome.settings-daemon.plugins.media-keys"
  local path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/light/"
  local current updated

  current="$(gsettings get "$schema" custom-keybindings)"
  updated="$(CURRENT="$current" PATH_TO_REMOVE="$path" python3 - <<'PY'
import ast
import os

try:
    values = list(ast.literal_eval(os.environ["CURRENT"]))
except (SyntaxError, ValueError):
    values = []
path = os.environ["PATH_TO_REMOVE"]
print(repr([value for value in values if value != path]))
PY
)"
  gsettings set "$schema" custom-keybindings "$updated"
  echo "Removed Light's GNOME shortcut."
}

manual_instructions() {
  cat <<EOF
Automatic shortcut installation is currently supported on GNOME.

For $DESKTOP, add a custom global shortcut in System Settings:
  Name: Light Launcher
  Command: $TOGGLE_COMMAND
  Shortcut: Alt+Space

This desktop-native shortcut works under Wayland because the compositor owns
the key binding; Light does not read keyboard devices directly.
EOF
}

case "${DESKTOP,,}" in
  *gnome*|*ubuntu*)
    if [[ "$ACTION" == "uninstall" ]]; then
      uninstall_gnome
    else
      install_gnome
    fi
    ;;
  *)
    manual_instructions
    ;;
esac
