#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

is_running() {
  pgrep -f "[p]ython3 -m light" >/dev/null 2>&1
}

run_light() {
  if is_running; then
    echo "Light is already running — bringing launcher to front..."
    python3 -m light "$@" || true
    exit 0
  fi
  echo "Starting Light..."
  exec python3 -m light "$@"
}

case "${1:-start}" in
  stop)
    if is_running; then
      pkill -f "[p]ython3 -m light" || true
      echo "Light stopped."
    else
      echo "Light is not running."
    fi
    ;;
  status)
    if is_running; then
      echo "Light is running (pid $(pgrep -f '[p]ython3 -m light'))."
    else
      echo "Light is not running."
    fi
    ;;
  toggle|start|"")
    run_light "${@:2}"
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
      echo "Light is already running — bringing launcher to front..."
      .venv/bin/python -m light "$@" || true
      exit 0
    fi
    exec .venv/bin/python -m light "$@"
    ;;
  *)
    run_light "$@"
    ;;
esac
