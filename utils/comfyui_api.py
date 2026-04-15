"""
Phase 3 – ComfyUI API ユーティリティ
======================================
ComfyUI の REST API および WebSocket エンドポイントと通信するための
低レベルヘルパーモジュール。

依存ライブラリは Blender 同梱の Python (websocket-client は別途インストール)
またはフォールバックとして urllib を使用します。
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import urllib.request
import urllib.error
import uuid
from typing import Callable


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_TIMEOUT = 30  # HTTP リクエストのタイムアウト秒数


# ---------------------------------------------------------------------------
# REST API ヘルパー
# ---------------------------------------------------------------------------

def build_base_url(host: str, port: int) -> str:
    """ComfyUI サーバーのベース URL を構築する"""
    host = host.strip()
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    return f"{host}:{port}"


def queue_prompt(
    host: str,
    port: int,
    workflow: dict,
    client_id: str | None = None,
) -> dict:
    """
    ComfyUI の /prompt エンドポイントへワークフローをキューに追加する。

    Parameters
    ----------
    host : str
        ComfyUI ホスト (例: "127.0.0.1")
    port : int
        ComfyUI ポート番号 (例: 8188)
    workflow : dict
        ComfyUI API 形式のワークフロー辞書
    client_id : str | None
        WebSocket クライアント ID（省略時は自動生成）

    Returns
    -------
    dict
        {"prompt_id": "<uuid>", "number": <int>, "node_errors": {...}}
    """
    if client_id is None:
        client_id = str(uuid.uuid4())

    payload = json.dumps(
        {"prompt": workflow, "client_id": client_id}
    ).encode("utf-8")

    base_url = build_base_url(host, port)
    req = urllib.request.Request(
        f"{base_url}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_history(host: str, port: int, prompt_id: str) -> dict:
    """
    指定した prompt_id の実行履歴（出力ファイルパス等）を取得する。

    Returns
    -------
    dict
        ComfyUI の /history/<prompt_id> レスポンス
    """
    base_url = build_base_url(host, port)
    url = f"{base_url}/history/{prompt_id}"
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_queue_info(host: str, port: int) -> dict:
    """
    現在のキュー情報（実行中・待機中のジョブ）を取得する。
    """
    base_url = build_base_url(host, port)
    url = f"{base_url}/queue"
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_image(
    host: str,
    port: int,
    image_path: str,
    overwrite: bool = True,
) -> dict:
    """
    ローカル画像ファイルを ComfyUI の /upload/image エンドポイントへ送信する。

    Returns
    -------
    dict
        {"name": "<filename>", "subfolder": "", "type": "input"}
    """
    import os
    import mimetypes

    base_url = build_base_url(host, port)
    filename = os.path.basename(image_path)
    mime_type, _ = mimetypes.guess_type(image_path)
    mime_type = mime_type or "image/png"

    boundary = uuid.uuid4().hex
    with open(image_path, "rb") as f:
        file_bytes = f.read()

    overwrite_str = "true" if overwrite else "false"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + file_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        f"{overwrite_str}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# WebSocket クライアント (軽量 RFC 6455 実装)
# ---------------------------------------------------------------------------

class _MinimalWSClient:
    """
    外部依存なしの最小限 WebSocket クライアント。
    websocket-client がインストールされていない環境向けのフォールバック。
    テキスト / バイナリフレームの受信のみサポートします。
    """

    def __init__(self, host: str, port: int, client_id: str) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        self._sock = socket.create_connection((self._host, self._port), timeout=60)
        # HTTP Upgrade ハンドシェイク – RFC 6455 に従いランダムな16バイトノンス
        import base64
        import os
        key = base64.b64encode(os.urandom(16)).decode("utf-8")
        self._sock.sendall(
            (
                f"GET /ws?clientId={self._client_id} HTTP/1.1\r\n"
                f"Host: {self._host}:{self._port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode("utf-8")
        )
        # レスポンスヘッダーを読み捨てる
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self._sock.recv(1024)
            if not chunk:
                raise ConnectionError("WebSocket ハンドシェイクに失敗しました")
            response += chunk

    def recv_message(self) -> tuple[str, bytes | str]:
        """
        1 フレームを受信する。

        Returns
        -------
        (frame_type, payload)
            frame_type: "text" | "binary" | "close"
        """
        if self._sock is None:
            raise RuntimeError("接続されていません")

        header = self._recv_exact(2)
        opcode = header[0] & 0x0F
        payload_len = header[1] & 0x7F

        if payload_len == 126:
            payload_len = struct.unpack(">H", self._recv_exact(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", self._recv_exact(8))[0]

        payload = self._recv_exact(payload_len)

        if opcode == 0x1:  # text
            return "text", payload.decode("utf-8")
        if opcode == 0x2:  # binary
            return "binary", payload
        if opcode == 0x8:  # close
            return "close", b""
        return "unknown", payload

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("WebSocket 接続が切断されました")
            buf += chunk
        return buf


# ---------------------------------------------------------------------------
# 進捗リスナー (スレッド)
# ---------------------------------------------------------------------------

class ProgressListener:
    """
    ComfyUI WebSocket から進捗メッセージを受信し、
    コールバック関数へ通知するバックグラウンドスレッド。

    Callbacks
    ---------
    on_progress(value: float, max: float)
        ステップ進捗 (0.0 〜 1.0)
    on_complete(output_files: list[str])
        生成完了時に出力ファイルパスのリストを渡す
    on_error(message: str)
        エラー発生時
    """

    def __init__(
        self,
        host: str,
        port: int,
        prompt_id: str,
        client_id: str,
        on_progress: Callable[[float], None] | None = None,
        on_complete: Callable[[list[str]], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._prompt_id = prompt_id
        self._client_id = client_id
        self.on_progress = on_progress or (lambda v: None)
        self.on_complete = on_complete or (lambda files: None)
        self.on_error = on_error or (lambda msg: None)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        ws = _MinimalWSClient(self._host, self._port, self._client_id)
        try:
            ws.connect()
        except Exception as exc:
            self.on_error(f"WebSocket 接続エラー: {exc}")
            return

        try:
            while not self._stop_event.is_set():
                try:
                    frame_type, payload = ws.recv_message()
                except Exception as exc:
                    self.on_error(f"受信エラー: {exc}")
                    break

                if frame_type == "close":
                    break
                if frame_type != "text":
                    continue

                try:
                    msg = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                self._handle_message(msg)
        finally:
            ws.close()

    def _handle_message(self, msg: dict) -> None:
        msg_type = msg.get("type")
        data = msg.get("data", {})

        if msg_type == "progress":
            value = data.get("value", 0)
            max_val = data.get("max", 1) or 1
            self.on_progress(value / max_val)

        elif msg_type == "executed":
            if data.get("prompt_id") == self._prompt_id:
                # 履歴から出力ファイルを取得
                try:
                    history = get_history(self._host, self._port, self._prompt_id)
                    outputs = history.get(self._prompt_id, {}).get("outputs", {})
                    files: list[str] = []
                    for node_output in outputs.values():
                        for key in ("videos", "images", "gifs"):
                            for item in node_output.get(key, []):
                                if "filename" in item:
                                    files.append(item["filename"])
                    self.on_complete(files)
                except Exception as exc:
                    self.on_error(f"履歴取得エラー: {exc}")
                self._stop_event.set()

        elif msg_type == "execution_error":
            if data.get("prompt_id") == self._prompt_id:
                self.on_error(
                    f"ComfyUI 実行エラー: {data.get('exception_message', '不明')}"
                )
                self._stop_event.set()
