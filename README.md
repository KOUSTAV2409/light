# Light

Linux launcher inspired by Spotlight and Raycast. Built with Python 3 + GTK 3.

## MVP features

- Floating search window (GTK 3)
- Installed application search via freedesktop `.desktop` entries
- File search via `fd`, `find`, or Python fallback
- System actions (sleep, reboot, lock, terminal)
- Web search + URL open
- Calculator with safe evaluation
- Arrow keys, Tab, Enter, Escape navigation
- System tray icon
- Wayland-safe compositor shortcut plus optional `keyboard` fallback
- Streaming OpenAI answers with source citations
- Opt-in local clipboard history and process-isolated extensions

## Requirements

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  gir1.2-ayatanaappindicator3-0.1 xdg-utils fd-find
```

On Ubuntu/Debian, `fd-find` installs the binary as **`fdfind`** (already supported).

## Run

```bash
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

On GNOME/Ubuntu, install it automatically:

```bash
./run.sh install-hotkey
```

On KDE and other compositors, this prints the exact desktop-native command to
bind. The shortcut invokes Light over D-Bus, so it works reliably on Wayland
without reading `/dev/input`.

### Option B — Optional pip package in a venv

```bash
./run.sh setup-hotkey   # creates .venv and installs keyboard
./run.sh start-venv     # run with built-in global hotkey
```

## Config

On first run, config is copied to:

```
~/.config/light/configuration.json
~/.config/light/secrets.json      # recommended place for API keys
~/.config/light/actions.json      # optional user actions
```

## File search

Type any filename fragment — including multiple words:

- `readme`
- `budget report`
- `invoice 2024`

Light matches files whose path contains **all** words (Raycast/Spotlight-style).
Results appear under apps/actions; Google stays as a fallback at the bottom.

AI answers are intentional, not automatic for every multi-word query:

- Questions: `who is the ceo of google`
- Fact lookups: `ceo of google`, `capital of france`
- Explicit AI: `? latest openai news`

For fact lookups, Light shows the **live answer on top**, then matching local
files, then Google — Raycast-style parallel results, not exclusive modes.

Currency conversion is built in (live market rates, ECB fallback, no API key):

- `1 usd to inr`
- `1 usd to rupees`
- `100 euros in usd`

Enter copies the converted amount. Rates may still differ slightly from Google
depending on provider and update timing.


Light can answer questions like Google’s AI Overview using **OpenAI Responses API + `web_search`**.

1. Create secrets file (recommended — do not commit this):

```bash
mkdir -p ~/.config/light
cat > ~/.config/light/secrets.json <<'EOF'
{
  "openai_api_key": "sk-your-key-here"
}
EOF
chmod 600 ~/.config/light/secrets.json
```

Or export once per shell:

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

2. Enable OpenAI in config (`~/.config/light/configuration.json`):

```json
"openai_enabled": true,
"openai_model": "gpt-4o",
"openai_web_search": true
```

3. Restart Light:

```bash
./run.sh stop
./run.sh
```

Then ask: `who is the ceo of whatsapp global`

Flow: OpenAI web search → short answer under the bar → Wikipedia only if OpenAI is off/unavailable.

## Clipboard history

Clipboard history is local-only and disabled by default. Enable it in
`~/.config/light/configuration.json`:

```json
"clipboard_history_enabled": true,
"clipboard_history_limit": 50
```

Type `clipboard` or `clipboard <filter>` in Light. Entries are stored with mode
`0600` in `~/.local/share/light/clipboard_history.json`.

## Extensions

Put extensions in `~/.local/share/light/extensions/<id>/manifest.json`:

```json
{
  "id": "example",
  "name": "Example",
  "prefix": "ex",
  "description": "Run an external extension",
  "command": ["/absolute/path/to/extension"]
}
```

Typing `ex hello` launches the command with `hello` as its final argument and
in the `LIGHT_QUERY` environment variable. Commands are arrays and never run
through a shell.

## Preferences

Open **Tray → Preferences** to configure:

- Theme: **Raycast Dark**, **Spotlight Light**, or **Dracula**
- Keyboard hints under results
- OpenAI live answers and web search
- Clipboard history
- Privacy-safe local metrics
- Search paths
- File index status and refresh guidance

## Optional fast file index

Recommended for other users too, but not required:

```bash
sudo apt install plocate
sudo updatedb
```

Light auto-detects `plocate`/`locate` and falls back to live `fdfind` search.

## Test

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -t . -v
```

## Packages

```bash
./packaging/debian/build-deb.sh 0.1.0
./packaging/flatpak/build-flatpak.sh
```

The Debian artifact is written to `dist/`. Flatpak requires `flatpak-builder`
and the GNOME 48 runtime/SDK.

## Validation metrics

Privacy-safe local counters are disabled by default. Set
`"usage_metrics_enabled": true`, then run `./run.sh metrics`. Queries, paths,
clipboard contents, answers, and API keys are never recorded.

See `VALIDATION.md` for the real-user validation workflow before paid features.

## Project layout

| Area | Path |
|------|------|
| App entry | `light/app.py` |
| Launcher UI | `light/ui/launcher_window.py` |
| Themes | `light/ui/theme.py` |
| Search engine | `light/search/search.py` |
| Config | `light/configuration/configuration.py` |
| Packaging | `packaging/` |

## Known MVP limits

- Wayland layer-shell is used automatically when `gir1.2-gtk-layer-shell-0.1`
  is installed; otherwise Light falls back to a regular always-on-top GTK window
- Automatic Wayland shortcut installation currently targets GNOME; other
  compositors use the command printed by `./run.sh install-hotkey`
- File search without `fd`/`find`/`plocate` is slower on large home folders
- Flatpak build requires `flatpak-builder` and the GNOME 48 runtime locally
- Power actions may need polkit permissions
- OpenAI web search uses your API quota (Responses API + web_search tool)
