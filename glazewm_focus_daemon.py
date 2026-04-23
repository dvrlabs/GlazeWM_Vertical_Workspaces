# glazewm_focus_daemon.py
import asyncio
import json
import websockets

GLAZE_URI = "ws://localhost:6123"
TRIGGER_ADDR = ("127.0.0.1", 7744)

FOCUS_CMD = {
    "up": "focus --direction up",
    "down": "focus --direction down",
}
FOCUS_WS_FALLBACK = {
    "up": "focus --prev-active-workspace-on-monitor",
    "down": "focus --next-active-workspace-on-monitor",
}
MOVE_CMD = {
    "move_up": "move --direction up",
    "move_down": "move --direction down",
}
MOVE_WS_FALLBACK = {
    "move_up": "move --prev-active-workspace-on-monitor",
    "move_down": "move --next-active-workspace-on-monitor",
}
ALL_CMDS = set(FOCUS_CMD) | set(MOVE_CMD)


async def ipc(ws, request):
    await ws.send(request)
    return json.loads(await ws.recv())


def get_pos(focused_resp):
    f = focused_resp["data"]["focused"]
    if "x" in f and "y" in f:
        return (f["x"], f["y"])
    r = f.get("rect")
    if isinstance(r, dict):
        return (r.get("x"), r.get("y"))
    return (f.get("parentId"), None)


async def handle_focus(ws, direction):
    resp = await ipc(ws, f"command {FOCUS_CMD[direction]}")
    source_id = resp["data"]["subjectContainerId"]
    focused = await ipc(ws, "query focused")
    current_id = focused["data"]["focused"]["id"]
    if current_id == source_id:
        await ipc(ws, f"command {FOCUS_WS_FALLBACK[direction]}")


async def handle_move(ws, direction):
    before = await ipc(ws, "query focused")
    pos_before = get_pos(before)
    parent_before = before["data"]["focused"].get("parentId")

    await ipc(ws, f"command {MOVE_CMD[direction]}")

    after = await ipc(ws, "query focused")
    pos_after = get_pos(after)
    parent_after = after["data"]["focused"].get("parentId")

    moved = (pos_before != pos_after) or (parent_before != parent_after)
    if not moved:
        await ipc(ws, f"command {MOVE_WS_FALLBACK[direction]}")
        # Focus follows — strip "move_" to reuse the focus fallback map.
        await ipc(ws, f"command {FOCUS_WS_FALLBACK[direction.removeprefix('move_')]}")


async def handle(ws, cmd):
    if cmd in FOCUS_CMD:
        await handle_focus(ws, cmd)
    elif cmd in MOVE_CMD:
        await handle_move(ws, cmd)


class TriggerProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue):
        self.queue = queue

    def datagram_received(self, data, _addr):
        cmd = data.decode(errors="ignore").strip().lower()
        if cmd in ALL_CMDS:
            self.queue.put_nowait(cmd)


async def main():
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        lambda: TriggerProtocol(queue),
        local_addr=TRIGGER_ADDR,
    )
    while True:
        try:
            async with websockets.connect(GLAZE_URI) as ws:
                while True:
                    cmd = await queue.get()
                    try:
                        await handle(ws, cmd)
                    except Exception as e:
                        print(f"handle error: {e}")
                        break
        except Exception as e:
            print(f"reconnecting after: {e}")
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
