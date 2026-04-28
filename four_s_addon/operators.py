"""
Operators for 4'S Add-on
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from typing import TYPE_CHECKING

import bpy
from bpy.types import Operator, Context

if TYPE_CHECKING:
    from . import FourSProperties

POLL_INTERVAL = 0.2


class ComfyUIWebSocketClient:
    def __init__(self, props: FourSProperties) -> None:
        self._props: FourSProperties = props
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._future: asyncio.Future | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self, host: str, port: int, payload: dict) -> None:
        if self._running:
            return
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=False)
        self._thread.start()
        self._future = asyncio.run_coroutine_threadsafe(
            self._connect_and_listen(host, port, payload),
            self._loop,
        )
        bpy.app.timers.register(self._poll, first_interval=POLL_INTERVAL)

    def stop(self) -> None:
        self._running = False
        if self._future and not self._future.done():
            self._future.cancel()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _run_loop(self) -> None:
        if self._loop is None:
            return
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect_and_listen(self, host: str, port: int, payload: dict) -> None:
        try:
            import websockets
        except ImportError as exc:
            self._queue.put(
                (
                    "error",
                    f"websockets ライブラリがインストールされていません。エラー: {exc}",
                )
            )
            return

        url = f"ws://{host}:{port}/ws"
        try:
            async with websockets.connect(url) as websocket:
                await websocket.send(json.dumps(payload))
                async for message in websocket:
                    self._queue.put(("message", str(message)))
        except (
            websockets.exceptions.WebSocketException,
            OSError,
            asyncio.TimeoutError,
        ) as exc:
            self._queue.put(("error", f"通信エラー: {exc}"))
        finally:
            self._queue.put(("done", "完了"))

    def _poll(self) -> float | None:
        if self._future and self._future.done():
            exc = self._future.exception()
            if exc:
                self._queue.put(("error", f"生成エラー: {exc}"))

        while not self._queue.empty():
            kind, message = self._queue.get()
            if kind == "message":
                self._props.status_message = message
            elif kind == "error":
                self._props.status_message = message
                self._props.is_running = False
                self.stop()
                return None
            elif kind == "done":
                self._props.status_message = message
                self._props.is_running = False
                self.stop()
                return None

        return POLL_INTERVAL


_active_client: ComfyUIWebSocketClient | None = None
_client_lock = threading.Lock()


class FOURS_OT_Generate(Operator):
    """ComfyUI へ WebSocket で送信して生成を開始"""

    bl_idname = "four_s.generate"
    bl_label = "生成開始"
    bl_options = {"REGISTER"}

    def execute(self, context: Context) -> set[str]:
        global _active_client
        props = context.scene.four_s

        with _client_lock:
            if _active_client and _active_client.is_running:
                self.report({"WARNING"}, "すでに生成中です。")
                return {"CANCELLED"}

        payload = {
            "prompt": props.prompt,
            "style_strength": props.style_strength,
            "lora": props.lora,
        }

        props.status_message = "接続中..."
        props.is_running = True

        with _client_lock:
            _active_client = ComfyUIWebSocketClient(props)
            _active_client.start("127.0.0.1", 8188, payload)
        return {"FINISHED"}


def register() -> None:
    bpy.utils.register_class(FOURS_OT_Generate)


def unregister() -> None:
    global _active_client
    with _client_lock:
        if _active_client:
            _active_client.stop()
            _active_client = None
    bpy.utils.unregister_class(FOURS_OT_Generate)
