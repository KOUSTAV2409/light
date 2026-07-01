# Light — Linux Launcher MVP

Prototype launcher inspired by [Snap](../README.md). Built with Python 3 + GTK 3.

## MVP features

- Floating search window (GTK 3)
- File search via `fd`, `find`, or Python fallback
- System actions (sleep, reboot, lock, terminal)
- Web search + URL open
- Calculator with safe evaluation
- Arrow keys, Tab, Enter, Escape navigation
- System tray icon
- Global hotkey via system shortcut or optional `keyboard` package

## Requirements

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 xdg-utils fd-find
```

On Ubuntu/Debian, `fd-find` installs the binary as **`fdfind`** (already supported).

## Run

```bash
cd linux
chmod +x run.sh
./run.sh
```

Or directly:

```bash
python3 -m light
```

The search window should open immediately. A magnifying-glass icon appears in the system tray.

### Harmless warning

This message is safe to ignore:

```
Gtk-Message: Failed to load module "appmenu-gtk-module"
```

## Global hotkey (Alt+Space)

**Do not use `pip install keyboard` system-wide** on Ubuntu 24.04+ — PEP 668 blocks it.

### Option A — System keyboard shortcut (recommended)

1. Keep Light running: `./run.sh`
2. Open **Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts**
3. Add a shortcut:
   - Name: `Light`
   - Command: `/home/koustav/light/linux/run.sh toggle`
   - Shortcut: `Alt+Space`

`--toggle` talks to the already-running app (single-instance).

### Option B — Optional pip package in a venv

```bash
./run.sh setup-hotkey   # creates .venv and installs keyboard
./run.sh start-venv     # run with built-in global hotkey
```

## Config

On first run, config is copied to:

```
~/.config/light/configuration.json
~/.config/light/actions.json   # optional user actions
```

## Project layout (mirrors Snap)

| Snap (macOS) | Light (Linux MVP) |
|--------------|-------------------|
| `Snap.swift` | `light/app.py` |
| `SearchView.swift` | `light/ui/launcher_window.py` |
| `Search.swift` | `light/search/search.py` |
| `SearchItem.swift` | `light/search/search_item.py` |
| `ActionSearch.swift` | `light/search/action_provider.py` |
| `Configuration.swift` | `light/configuration/configuration.py` |
| `Actions.json` | `light/actions/default_actions.json` |

## Known MVP limits

- No Wayland layer-shell overlay yet (regular GTK window)
- Built-in global hotkey needs venv + `keyboard`, or use system shortcut
- File search without `fd`/`find` is shallow and slow
- No clipboard history or snippet expansion yet
- Power actions may need polkit permissions

## Next steps

1. `.desktop` application search
2. Preferences window
3. Wayland overlay via `gtk-layer-shell`
4. Clipboard history
