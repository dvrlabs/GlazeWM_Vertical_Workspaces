# GlazeWM Vertical Workspaces

A small Python daemon that extends [GlazeWM](https://github.com/glzr-io/glazewm) with **vertical workspace navigation** — treating up/down keybindings as a smooth flow between tiled windows *and* the active workspaces stacked above and below them on the same monitor.

## The Concept

GlazeWM's workspaces are a flat, named list. This daemon layers a *vertical* mental model on top: when a directional action would hit the edge of the current workspace, it spills over into the prev/next active workspace on the same monitor.

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
        │  shell_exec powershell → UDP send
        ▼
   [UDP :7744]
        │
        ▼
    [daemon] ── WebSocket ──► [GlazeWM IPC :6123]
```

The daemon listens on UDP `127.0.0.1:7744` for short text commands (`up`, `down`, `move_up`, `move_down`), translates them into GlazeWM IPC commands over WebSocket, and decides whether to run the fallback based on whether the primary command actually did anything.

### How the "did it move?" check works

- **Focus:** after the directional focus command, query the focused container. If its id equals the `subjectContainerId` of the command we just ran, focus didn't move → run the workspace fallback.
- **Move:** since focus stays on the same window during a move, snapshot the window's `(x, y)` *and* `parentId` before the command, then again after. If both are unchanged, the move was a no-op → run the workspace fallback, then issue a matching focus command so the viewport follows.

## Requirements

- Windows with GlazeWM v3+ (the `--next/prev-active-workspace-on-monitor` flags landed in [PR #990](https://github.com/glzr-io/glazewm/pull/990))
- Python 3.9+ (uses `str.removeprefix`)
- `websockets` package

```powershell
pip install websockets
```

## Setup

### 1. Run the daemon

```powershell
python glazewm_focus_daemon.py
```

For day-to-day use, launch it on login — either via GlazeWM's `startup_commands` or Windows Task Scheduler.

### 2. Add keybindings to your GlazeWM config

Edit `%userprofile%/.glzr/glazewm/config.yaml`:

```yaml
keybindings:
  # Vertical focus (with workspace fallback)
  - commands: ["shell_exec powershell -NoProfile -NonInteractive -Command \"$u=New-Object Net.Sockets.UdpClient;$u.Send([Text.Encoding]::ASCII.GetBytes('up'),2,'127.0.0.1',7744)|Out-Null\""]
    bindings: ["alt+k"]

  - commands: ["shell_exec powershell -NoProfile -NonInteractive -Command \"$u=New-Object Net.Sockets.UdpClient;$u.Send([Text.Encoding]::ASCII.GetBytes('down'),2,'127.0.0.1',7744)|Out-Null\""]
    bindings: ["alt+j"]

  # Vertical move (carries window across workspaces at the edge)
  - commands: ["shell_exec powershell -NoProfile -NonInteractive -Command \"$u=New-Object Net.Sockets.UdpClient;$u.Send([Text.Encoding]::ASCII.GetBytes('move_up'),2,'127.0.0.1',7744)|Out-Null\""]
    bindings: ["alt+shift+k"]

  - commands: ["shell_exec powershell -NoProfile -NonInteractive -Command \"$u=New-Object Net.Sockets.UdpClient;$u.Send([Text.Encoding]::ASCII.GetBytes('move_down'),2,'127.0.0.1',7744)|Out-Null\""]
    bindings: ["alt+shift+j"]
```

Swap the key combos for whatever you prefer.

## Configuration

The daemon has a couple of constants at the top of the file:

- `GLAZE_URI` — GlazeWM IPC endpoint, default `ws://localhost:6123`
- `TRIGGER_ADDR` — UDP listen address, default `127.0.0.1:7744`

Change them if you have a conflicting service or want to run multiple instances.

## Troubleshooting

Keybinding fires but nothing happens? Run the daemon in a visible terminal and add `print` calls around the UDP and IPC paths. The three failure modes are:

1. **No UDP arrives** — GlazeWM isn't actually firing the PowerShell command. Check the keybinding syntax in `config.yaml`.
2. **UDP arrives but nothing reaches the IPC** — the string doesn't match one of the known triggers (`up`, `down`, `move_up`, `move_down`).
3. **IPC runs but the fallback never fires** — the position/parent snapshot shape may have changed in your GlazeWM version; inspect what `query focused` actually returns and adjust `get_pos`.
