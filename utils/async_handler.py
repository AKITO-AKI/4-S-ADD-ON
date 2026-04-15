"""
Phase 3 – 非同期ハンドラー
============================
bpy.app.timers を使って ComfyUI の生成進捗を Blender の N パネルへ
反映させる仕組み。生成中も Blender を操作できるようにします（フリーズ対策）。

使い方:
    handler = AsyncGenerationHandler(scene.solo_studio)
    handler.start(prompt_id, client_id)
    # bpy.app.timers.register 済みのため、Blender のメインスレッドで
    # プロパティが自動更新されます。
    # 完了・エラー時は自動的にタイマーを停止します。
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

# Blender 依存は実行時に遅延インポートする
# （テスト環境で bpy が存在しない場合にモジュールレベルのエラーを避けるため）


# ---------------------------------------------------------------------------
# スレッドセーフなメッセージキュー
# ---------------------------------------------------------------------------

class _MessageQueue:
    """スレッド間で状態更新メッセージを受け渡す FIFO キュー"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[dict] = []

    def put(self, msg: dict) -> None:
        with self._lock:
            self._items.append(msg)

    def get_all(self) -> list[dict]:
        with self._lock:
            items = list(self._items)
            self._items.clear()
        return items


# ---------------------------------------------------------------------------
# 非同期生成ハンドラー
# ---------------------------------------------------------------------------

class AsyncGenerationHandler:
    """
    ComfyUI WebSocket 進捗を Blender のメインスレッドへ中継するハンドラー。

    Parameters
    ----------
    props : SoloStudioProperties
        bpy.context.scene.solo_studio
    on_complete : Callable[[list[str]], None] | None
        生成完了時のコールバック（メインスレッドで呼ばれる）
    on_error : Callable[[str], None] | None
        エラー時のコールバック（メインスレッドで呼ばれる）
    """

    # タイマー間隔（秒）
    TIMER_INTERVAL: float = 0.5

    def __init__(
        self,
        props: object,
        on_complete: Callable[[list[str]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._props = props
        self.on_complete = on_complete
        self.on_error = on_error
        self._queue: _MessageQueue = _MessageQueue()
        self._listener: Optional[object] = None  # ProgressListener
        self._timer_registered = False

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def start(self, host: str, port: int, prompt_id: str, client_id: str) -> None:
        """非同期リスナーを開始し、bpy.app.timers へ登録する"""
        from .comfyui_api import ProgressListener

        self._listener = ProgressListener(
            host=host,
            port=port,
            prompt_id=prompt_id,
            client_id=client_id,
            on_progress=self._on_progress,
            on_complete=self._on_complete,
            on_error=self._on_error,
        )
        self._listener.start()
        self._register_timer()

    def stop(self) -> None:
        """リスナーとタイマーを停止する"""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._unregister_timer()

    # ------------------------------------------------------------------
    # コールバック（バックグラウンドスレッドから呼ばれる）
    # ------------------------------------------------------------------

    def _on_progress(self, ratio: float) -> None:
        self._queue.put({"type": "progress", "value": ratio})

    def _on_complete(self, files: list[str]) -> None:
        self._queue.put({"type": "complete", "files": files})

    def _on_error(self, message: str) -> None:
        self._queue.put({"type": "error", "message": message})

    # ------------------------------------------------------------------
    # bpy.app.timers コールバック（メインスレッド）
    # ------------------------------------------------------------------

    def _timer_callback(self) -> Optional[float]:
        """
        Blender のメインスレッドで定期的に呼ばれ、キューを処理する。
        None を返すとタイマーが停止する。
        """
        import bpy  # メインスレッドでのみインポート可能

        messages = self._queue.get_all()
        props = self._props

        for msg in messages:
            msg_type = msg["type"]

            if msg_type == "progress":
                props.generation_progress = msg["value"]
                props.generation_status = (
                    f"生成中... {int(msg['value'] * 100)}%"
                )
                # UI を強制再描画
                for area in bpy.context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()

            elif msg_type == "complete":
                props.generation_progress = 1.0
                props.generation_status = "生成完了"
                self._timer_registered = False
                if self._listener:
                    self._listener.stop()
                    self._listener = None
                if self.on_complete:
                    self.on_complete(msg["files"])
                # None を返すことでタイマーを停止
                return None

            elif msg_type == "error":
                props.generation_status = f"エラー: {msg['message']}"
                self._timer_registered = False
                if self._listener:
                    self._listener.stop()
                    self._listener = None
                if self.on_error:
                    self.on_error(msg["message"])
                return None

        return self.TIMER_INTERVAL

    # ------------------------------------------------------------------
    # タイマー登録ヘルパー
    # ------------------------------------------------------------------

    def _register_timer(self) -> None:
        import bpy

        if not self._timer_registered:
            bpy.app.timers.register(
                self._timer_callback,
                first_interval=self.TIMER_INTERVAL,
                persistent=False,
            )
            self._timer_registered = True

    def _unregister_timer(self) -> None:
        import bpy

        if self._timer_registered:
            try:
                bpy.app.timers.unregister(self._timer_callback)
            except Exception:
                pass
            self._timer_registered = False
