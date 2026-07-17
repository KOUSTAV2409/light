#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

is_running() {
  pgrep -f "[p]ython(3)?( .*)? -m light" >/dev/null 2>&1 \
    || pgrep -f "[.]venv/bin/python(3)? -m light" >/dev/null 2>&1
}

run_light() {
  local mode="${1:-start}"
  shift || true
  if is_running; then
    if [[ "$mode" == "toggle" ]]; then
      echo "Light is already running — toggling launcher..."
      python3 -m light --toggle "$@" || true
    else
      echo "Light is already running — bringing launcher to front..."
      python3 -m light "$@" || true
    fi
    exit 0
  fi
  echo "Starting Light..."
  exec python3 -m light "$@"
}

case "${1:-start}" in
  stop)
    if is_running; then
      pkill -f "[p]ython(3)?( .*)? -m light" || true
      pkill -f "[.]venv/bin/python(3)? -m light" || true
      echo "Light stopped."
    else
      echo "Light is not running."
    fi
    ;;
  status)
    if is_running; then
      echo "Light is running."
    else
      echo "Light is not running."
    fi
    ;;
  install-hotkey)
    exec "$PWD/install-hotkey.sh" install
    ;;
  uninstall-hotkey)
    exec "$PWD/install-hotkey.sh" uninstall
    ;;
  metrics)
    exec python3 -m light.metrics
    ;;
  toggle)
    run_light toggle "${@:2}"
    ;;
  start|"")
    run_light start "${@:2}"
    ;;
  setup-hotkey)
    VENV=".venv"
    if [[ ! -d "$VENV" ]]; then
      python3 -m venv "$VENV"
    fi
    "$VENV/bin/pip" install -q keyboard
    echo "Installed keyboard in $VENV"
    echo "Run with: ./run.sh start-venv"
    ;;
  start-venv)
    shift
    if [[ ! -d ".venv" ]]; then
      echo "Run ./run.sh setup-hotkey first."
      exit 1
    fi
    if is_running; then
      echo "Light is already running — toggling launcher..."
      .venv/bin/python -m light --toggle "$@" || true
      exit 0
    fi
    exec .venv/bin/python -m light "$@"
    ;;
  *)
    run_light start "$@"
    ;;
esac
