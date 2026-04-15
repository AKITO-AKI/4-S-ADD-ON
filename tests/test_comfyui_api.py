"""
Tests for utils/comfyui_api.py (pure-Python portions)

Tests for build_base_url and the _MinimalWSClient frame parsing logic.
Network calls (queue_prompt, get_history, upload_image) are not tested here
to avoid requiring a live ComfyUI server.
"""

import struct
import sys
import types
import unittest

# Mock bpy before importing our modules
bpy_mock = types.ModuleType("bpy")
sys.modules.setdefault("bpy", bpy_mock)

import pathlib

_repo_root = str(pathlib.Path(__file__).resolve().parents[1])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from utils.comfyui_api import (  # noqa: E402
    _MinimalWSClient,
    build_base_url,
    ProgressListener,
)


class TestBuildBaseUrl(unittest.TestCase):

    def test_plain_host_gets_http_prefix(self) -> None:
        url = build_base_url("127.0.0.1", 8188)
        self.assertTrue(url.startswith("http://"))

    def test_port_appended(self) -> None:
        url = build_base_url("127.0.0.1", 8188)
        self.assertIn(":8188", url)

    def test_existing_http_prefix_not_doubled(self) -> None:
        url = build_base_url("http://localhost", 8188)
        self.assertFalse(url.startswith("http://http://"))

    def test_https_prefix_preserved(self) -> None:
        url = build_base_url("https://example.com", 443)
        self.assertTrue(url.startswith("https://"))

    def test_strips_whitespace_from_host(self) -> None:
        url = build_base_url("  127.0.0.1  ", 8188)
        self.assertNotIn(" ", url)


class TestMinimalWSClientFrameParsing(unittest.TestCase):
    """Test _recv_exact and frame parsing using a fake socket"""

    def _make_text_frame(self, payload: str) -> bytes:
        """Build a minimal unmasked WebSocket text frame"""
        data = payload.encode("utf-8")
        length = len(data)
        if length < 126:
            header = bytes([0x81, length])
        elif length < 65536:
            header = struct.pack(">BBH", 0x81, 126, length)
        else:
            header = struct.pack(">BBQ", 0x81, 127, length)
        return header + data

    def _make_binary_frame(self, payload: bytes) -> bytes:
        """Build a minimal unmasked WebSocket binary frame"""
        length = len(payload)
        header = bytes([0x82, length])
        return header + payload

    def _make_close_frame(self) -> bytes:
        return bytes([0x88, 0])

    def _make_fake_client(self, raw_bytes: bytes) -> _MinimalWSClient:
        """Create a _MinimalWSClient with a fake socket that reads raw_bytes"""
        client = _MinimalWSClient.__new__(_MinimalWSClient)
        buf = bytearray(raw_bytes)

        class _FakeSock:
            def recv(self_, n: int) -> bytes:
                chunk = bytes(buf[:n])
                del buf[:n]
                return chunk

        client._sock = _FakeSock()
        return client

    def test_recv_text_frame(self) -> None:
        frame = self._make_text_frame('{"type":"progress"}')
        client = self._make_fake_client(frame)
        ftype, payload = client.recv_message()
        self.assertEqual(ftype, "text")
        self.assertEqual(payload, '{"type":"progress"}')

    def test_recv_binary_frame(self) -> None:
        data = b"\x00\x01\x02\x03"
        frame = self._make_binary_frame(data)
        client = self._make_fake_client(frame)
        ftype, payload = client.recv_message()
        self.assertEqual(ftype, "binary")
        self.assertEqual(payload, data)

    def test_recv_close_frame(self) -> None:
        frame = self._make_close_frame()
        client = self._make_fake_client(frame)
        ftype, payload = client.recv_message()
        self.assertEqual(ftype, "close")

    def test_empty_socket_raises(self) -> None:
        class _EmptySock:
            def recv(self_, n: int) -> bytes:
                return b""

        client = _MinimalWSClient.__new__(_MinimalWSClient)
        client._sock = _EmptySock()
        with self.assertRaises(ConnectionError):
            client.recv_message()


class TestProgressListenerMessageHandling(unittest.TestCase):
    """Test ProgressListener._handle_message() logic"""

    def _make_listener(self) -> tuple[ProgressListener, list, list, list]:
        progress_calls: list[float] = []
        complete_calls: list[list] = []
        error_calls: list[str] = []

        listener = ProgressListener(
            host="127.0.0.1",
            port=8188,
            prompt_id="test-id-123",
            client_id="client-abc",
            on_progress=lambda v: progress_calls.append(v),
            on_complete=lambda f: complete_calls.append(f),
            on_error=lambda m: error_calls.append(m),
        )
        return listener, progress_calls, complete_calls, error_calls

    def test_progress_message_normalised(self) -> None:
        listener, progress_calls, _, _ = self._make_listener()
        listener._handle_message({"type": "progress", "data": {"value": 5, "max": 20}})
        self.assertEqual(len(progress_calls), 1)
        self.assertAlmostEqual(progress_calls[0], 0.25)

    def test_progress_max_zero_does_not_divide_by_zero(self) -> None:
        listener, progress_calls, _, _ = self._make_listener()
        # max=0 should be treated as 1
        listener._handle_message({"type": "progress", "data": {"value": 0, "max": 0}})
        self.assertEqual(len(progress_calls), 1)

    def test_execution_error_triggers_error_callback(self) -> None:
        listener, _, _, error_calls = self._make_listener()
        listener._handle_message({
            "type": "execution_error",
            "data": {
                "prompt_id": "test-id-123",
                "exception_message": "CUDA OOM",
            },
        })
        self.assertEqual(len(error_calls), 1)
        self.assertIn("CUDA OOM", error_calls[0])

    def test_execution_error_wrong_id_ignored(self) -> None:
        listener, _, _, error_calls = self._make_listener()
        listener._handle_message({
            "type": "execution_error",
            "data": {
                "prompt_id": "other-id",
                "exception_message": "ignored",
            },
        })
        self.assertEqual(len(error_calls), 0)

    def test_unknown_message_type_ignored(self) -> None:
        listener, progress_calls, complete_calls, error_calls = self._make_listener()
        listener._handle_message({"type": "crystals", "data": {}})
        self.assertEqual(progress_calls, [])
        self.assertEqual(complete_calls, [])
        self.assertEqual(error_calls, [])


if __name__ == "__main__":
    unittest.main()
