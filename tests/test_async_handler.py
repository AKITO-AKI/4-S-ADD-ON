"""
Tests for utils/async_handler.py (_MessageQueue)

Tests for the thread-safe message queue used by AsyncGenerationHandler.
"""

import sys
import types
import threading
import unittest

# Mock bpy
bpy_mock = types.ModuleType("bpy")
sys.modules.setdefault("bpy", bpy_mock)

import pathlib

_repo_root = str(pathlib.Path(__file__).resolve().parents[1])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from utils.async_handler import _MessageQueue  # noqa: E402


class TestMessageQueue(unittest.TestCase):

    def test_empty_queue_returns_empty_list(self) -> None:
        q = _MessageQueue()
        self.assertEqual(q.get_all(), [])

    def test_put_then_get(self) -> None:
        q = _MessageQueue()
        q.put({"type": "progress", "value": 0.5})
        items = q.get_all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["value"], 0.5)

    def test_get_all_clears_queue(self) -> None:
        q = _MessageQueue()
        q.put({"type": "a"})
        q.get_all()
        self.assertEqual(q.get_all(), [])

    def test_multiple_messages(self) -> None:
        q = _MessageQueue()
        for i in range(5):
            q.put({"n": i})
        items = q.get_all()
        self.assertEqual([item["n"] for item in items], list(range(5)))

    def test_thread_safe_concurrent_puts(self) -> None:
        q = _MessageQueue()
        threads = [
            threading.Thread(target=lambda: q.put({"t": i}))
            for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        items = q.get_all()
        self.assertEqual(len(items), 100)


if __name__ == "__main__":
    unittest.main()
