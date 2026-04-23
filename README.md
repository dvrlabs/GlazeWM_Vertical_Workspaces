# GlazeWM Vertical Workspaces

A small Python daemon — plus a tiny Rust helper — that extends [GlazeWM](https://github.com/glzr-io/glazewm) with **vertical workspace navigation**. Up/down keybindings become a smooth flow between tiled windows *and* the active workspaces stacked above and below them on the same monitor.

## Why

I wanted the same vertical workspaces as used by the [Cosmic Desktop Environment](https://github.com/pop-os/cosmic-epoch).

## The Concept

GlazeWM's workspaces are a flat, named list. This project layers a *vertical* mental model on top: when a directional action would hit the edge of the current workspace, it spills over into the prev/next active workspace on the same monitor.

Two actions are supported, each with fallback behavior:

| Trigger                  | Primary action                             | Fallback (when the primary is a no-op)                                                 |
| ------------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------- |
| `up` / `down`            | Focus the window in that direction         | Focus prev/next active workspace on monitor                                            |
| `move_up` / `move_down`  | Move the focused window in that direction  | Move the window to prev/next active workspace on monitor, then follow it with focus    |

So pressing `down` at the bottom of a vertical split *jumps focus* to the next workspace. Pressing `move_down` in the same spot *carries the window with you*.

Left/right are intentionally not handled — they stay as native GlazeWM bindings, since horizontal flow doesn't map to the workspace-stack idea.

## Architecture

```
[GlazeWM keybinding]
        │
        │  shell_exec focus.exe <trigger>
        ▼
  [focus.exe]  (tiny Rust UDP sender)
        │
        ▼
   [UDP :7744]
        │
        ▼
    [daemon] ── WebSocket ──► [GlazeWM IPC :6123]
```

The daemon listens on UDP `127.0.0.1:7744` for short text commands (`up`, `down`, `move_up`, `move_down`), translates them into GlazeWM IPC commands over WebSocket, and decides whether to run the fallback based on whether the primary command actually did anything.

`focus.exe` is a ~10-line Rust binary whose only job is to fire one UDP packet and exit. It uses `#![windows_subsystem = "windows"]` so no console window flashes on each keypress, and it starts much faster than spawning PowerShell.

### How the "did it move?" check works

- **Focus:** after the directional focus command, query the focused container. If its id equals the `subjectContainerId` of the command we just ran, focus didn't move → run the workspace fallback.
- **Move:** since focus stays on the same window during a move, snapshot the window's `(x, y)` *and* `parentId` before the command, then again after. If both are unchanged, the move was a no-op → run the workspace fallback, then issue a matching focus command so the viewport follows.

## Requirements

- Windows with GlazeWM v3+ (the `--next/prev-active-workspace-on-monitor` flags landed in [PR #990](https://github.com/glzr-io/glazewm/pull/990))
- Python 3.9+ (uses `str.removeprefix`)
- `websockets` package
- A Rust toolchain to build `focus.exe` (only needed once)

```powershell
pip install websockets
```

## Setup

### 1. Build the UDP trigger helper

```powershell
rustc -O -C opt-level=z -C strip=symbols -C debuginfo=0 -C link-arg=/DEBUG:NONE focus.rs
```

This produces `focus.exe`. Drop it somewhere on your `PATH` (or use the full path in your keybindings).

### 2. Run the daemon

For a visible terminal (useful while debugging):

```powershell
python glazewm_focus_daemon.py
```

For day-to-day use you want it running silently in the background on login. The cleanest way is `pythonw.exe` — the windowless Python launcher that ships alongside `python.exe` — wired into GlazeWM's `startup_commands`. In `config.yaml`:

```yaml
general:
  startup_commands:
    - "shell_exec pythonw C:\\path\\to\\glazewm_focus_daemon.py"
```

`pythonw` runs the script with no console window, no taskbar presence, and no flash on startup. If the script crashes there's nothing to see — which is why you keep the `python` (not `pythonw`) invocation handy for troubleshooting. Windows Task Scheduler works too if you'd rather not couple the daemon's lifetime to GlazeWM's.

### 3. Add keybindings to your GlazeWM config

Edit `%userprofile%/.glzr/glazewm/config.yaml`:

```yaml
keybindings:
  # Vertical focus (with workspace fallback)
  - commands: ["shell_exec focus.exe up"]
    bindings: ["alt+k"]
  - commands: ["shell_exec focus.exe down"]
    bindings: ["alt+j"]

  # Vertical move (carries window across workspaces at the edge)
  - commands: ["shell_exec focus.exe move_up"]
    bindings: ["alt+shift+k"]
  - commands: ["shell_exec focus.exe move_down"]
    bindings: ["alt+shift+j"]
```

Swap the key combos for whatever you prefer. If `focus.exe` isn't on your `PATH`, use the full path, e.g. `shell_exec C:\Tools\focus.exe up`.

## Configuration

The daemon has a couple of constants at the top of the file:

- `GLAZE_URI` — GlazeWM IPC endpoint, default `ws://localhost:6123`
- `TRIGGER_ADDR` — UDP listen address, default `127.0.0.1:7744`

If you change the UDP port, update `focus.rs` to match (the target address is hardcoded) and rebuild.

## Troubleshooting

Keybinding fires but nothing happens? Run the daemon in a visible terminal and add `print` calls around the UDP and IPC paths. The three failure modes are:

1. **No UDP arrives** — GlazeWM isn't invoking `focus.exe`. Confirm it's on `PATH` (open a new terminal and run `focus.exe up` manually — the daemon should react), or hard-code the full path in the keybinding.
2. **UDP arrives but nothing reaches the IPC** — the argument passed to `focus.exe` doesn't match one of the known triggers (`up`, `down`, `move_up`, `move_down`).
3. **IPC runs but the fallback never fires** — the position/parent snapshot shape may have changed in your GlazeWM version; inspect what `query focused` actually returns and adjust `get_pos`.

## My config, as an example

```yaml
general:
  # Commands to run when the WM has started. This is useful for running a
  # script or launching another application.
  # Example: The below command launches Zebar.
  startup_commands:
    [
      "shell-exec zebar",
      "shell-exec pythonw C:\\Users\\JoeUser\\.glzr\\glazewm\\glazewm_focus_daemon.py",
    ]
```

```yaml
  # - commands: ["move --direction up"]
  #   bindings: ["alt+shift+k", "alt+shift+up"]
  #
  # - commands: ["move --direction down"]
  #   bindings: ["alt+shift+j", "alt+shift+down"]

  - commands:
      ["shell-exec C:\\Users\\JoeUser\\.glzr\\glazewm\\focus.exe move_up"]
    bindings: ["alt+shift+k", "alt+shift+up"]

  - commands:
      ["shell-exec C:\\Users\\JoeUser\\.glzr\\glazewm\\focus.exe move_down"]
    bindings: ["alt+shift+j", "alt+shift+down"]
```

```yaml
  # - commands: ["focus --direction up"]
  #   bindings: ["alt+k", "alt+up"]
  #
  # - commands: ["focus --direction down"]
  #   bindings: ["alt+j", "alt+down"]
  #
  - commands: ["shell-exec C:\\Users\\JoeUser\\.glzr\\glazewm\\focus.exe up"]
    bindings: ["alt+k", "alt+up"]

  - commands: ["shell-exec C:\\Users\\JoeUser\\.glzr\\glazewm\\focus.exe down"]
    bindings: ["alt+j", "alt+down"]
```
