"""
Tests for operators/render_passes.py helper validation logic.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest


def _build_bpy_mock() -> types.ModuleType:
    bpy_mock = types.ModuleType("bpy")
    bpy_mock.path = types.SimpleNamespace(abspath=lambda p: p[2:] if str(p).startswith("//") else str(p))
    bpy_mock.app = types.SimpleNamespace(
        timers=types.SimpleNamespace(
            register=lambda *a, **k: None,
            unregister=lambda *a, **k: None,
            is_registered=lambda *a, **k: False,
        )
    )
    bpy_mock.utils = types.SimpleNamespace(
        register_class=lambda cls: None,
        unregister_class=lambda cls: None,
    )
    bpy_mock.types = types.SimpleNamespace(
        Operator=object,
        Context=object,
        Scene=object,
        Collection=object,
        Object=object,
        PropertyGroup=object,
    )
    return bpy_mock


class TestRenderPassesHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_bpy = sys.modules.get("bpy")
        cls._original_bpy_types = sys.modules.get("bpy.types")

        bpy_mock = _build_bpy_mock()
        sys.modules["bpy"] = bpy_mock
        sys.modules["bpy.types"] = bpy_mock.types

        repo_root = pathlib.Path(__file__).resolve().parents[1]
        module_path = repo_root / "operators" / "render_passes.py"
        spec = importlib.util.spec_from_file_location("render_passes_test_module", str(module_path))
        cls.render_passes = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.render_passes)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._original_bpy is None:
            sys.modules.pop("bpy", None)
        else:
            sys.modules["bpy"] = cls._original_bpy

        if cls._original_bpy_types is None:
            sys.modules.pop("bpy.types", None)
        else:
            sys.modules["bpy.types"] = cls._original_bpy_types

    def test_validate_target_collection_none_is_allowed(self) -> None:
        self.assertIsNone(self.render_passes._validate_target_collection_for_render(None))

    def test_validate_target_collection_rejects_empty_render_targets(self) -> None:
        camera_only_collection = types.SimpleNamespace(
            objects=[types.SimpleNamespace(type="CAMERA")],
            children=[],
        )
        message = self.render_passes._validate_target_collection_for_render(camera_only_collection)
        self.assertIsNotNone(message)
        self.assertIn("Target Objects が空", message)

    def test_validate_target_collection_accepts_mesh_target(self) -> None:
        mesh_collection = types.SimpleNamespace(
            objects=[types.SimpleNamespace(type="MESH")],
            children=[],
        )
        self.assertIsNone(self.render_passes._validate_target_collection_for_render(mesh_collection))

    def test_ensure_dir_rejects_blank_path(self) -> None:
        with self.assertRaises(ValueError):
            self.render_passes._ensure_dir("")

    def test_ensure_dir_creates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = pathlib.Path(tmpdir) / "passes"
            resolved = self.render_passes._ensure_dir(str(target))
            self.assertTrue(target.is_dir())
            self.assertEqual(resolved, str(target))


if __name__ == "__main__":
    unittest.main()
