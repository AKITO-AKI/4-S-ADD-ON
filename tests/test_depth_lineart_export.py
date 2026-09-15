"""
Tests for utils/depth_lineart_export.py validation behavior.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest


def _build_bpy_mock() -> types.ModuleType:
    bpy_mock = types.ModuleType("bpy")
    bpy_mock.path = types.SimpleNamespace(abspath=lambda p: str(p))
    bpy_mock.types = types.SimpleNamespace(
        Scene=object,
        ViewLayer=object,
        Collection=object,
        Object=object,
    )
    bpy_mock.data = types.SimpleNamespace(
        objects={},
        collections={},
    )
    scene = types.SimpleNamespace(
        camera=types.SimpleNamespace(type="CAMERA"),
        view_layers=[types.SimpleNamespace()],
    )
    bpy_mock.context = types.SimpleNamespace(scene=scene)
    bpy_mock.ops = types.SimpleNamespace(render=types.SimpleNamespace(render=lambda **k: None))
    return bpy_mock


class TestDepthLineartExportValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_bpy = sys.modules.get("bpy")
        cls._original_bpy_types = sys.modules.get("bpy.types")

        bpy_mock = _build_bpy_mock()
        sys.modules["bpy"] = bpy_mock
        sys.modules["bpy.types"] = bpy_mock.types

        repo_root = pathlib.Path(__file__).resolve().parents[1]
        module_path = repo_root / "utils" / "depth_lineart_export.py"
        spec = importlib.util.spec_from_file_location("depth_lineart_export_test_module", str(module_path))
        cls.depth_export = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.depth_export)

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

    def test_export_fails_when_target_collection_name_is_missing(self) -> None:
        code = self.depth_export.export_depth_lineart(
            output_root="/tmp",
            camera_name=None,
            target_collection_name="missing_collection",
        )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
