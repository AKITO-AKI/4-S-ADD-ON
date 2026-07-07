"""
Tests for operators/auto_import.py
"""

import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest

from unittest import mock

_PATCHED_MODULES = [
    "bpy",
    "bpy.types",
    "bpy.props",
    "operators",
    "operators.auto_import",
    "four_s_addon",
    "four_s_addon.operators",
    "four_s_addon.utils",
    "four_s_addon.utils.comfyui_api",
]
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _PATCHED_MODULES}


def _restore_patched_modules() -> None:
    for name, original in _ORIGINAL_MODULES.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


# ---------------------------------------------------------------------------
# Minimal bpy mock
# ---------------------------------------------------------------------------

bpy_mock = types.ModuleType("bpy")
bpy_mock.types = types.SimpleNamespace(
    Operator=object,
    Context=object,
    Event=object,
    Scene=object,
)
bpy_mock.props = types.SimpleNamespace(
    StringProperty=lambda **kw: None,
)
bpy_mock.data = types.SimpleNamespace(scenes=[])

sys.modules["bpy"] = bpy_mock
sys.modules["bpy.types"] = bpy_mock.types
sys.modules["bpy.props"] = bpy_mock.props

operators_pkg = types.ModuleType("operators")
sys.modules.setdefault("operators", operators_pkg)

four_s_pkg = types.ModuleType("four_s_addon")
sys.modules.setdefault("four_s_addon", four_s_pkg)
sys.modules.setdefault("four_s_addon.operators", operators_pkg)

comfyui_api_mod = types.ModuleType("four_s_addon.utils.comfyui_api")
comfyui_api_mod.get_history = lambda *args, **kwargs: {}
sys.modules.setdefault("four_s_addon.utils", types.ModuleType("four_s_addon.utils"))
sys.modules["four_s_addon.utils.comfyui_api"] = comfyui_api_mod

_auto_import_spec = importlib.util.spec_from_file_location(
    "operators.auto_import",
    str(pathlib.Path(__file__).resolve().parent.parent / "operators" / "auto_import.py"),
)
auto_import = importlib.util.module_from_spec(_auto_import_spec)
auto_import.__package__ = "four_s_addon.operators"
sys.modules["operators.auto_import"] = auto_import
_auto_import_spec.loader.exec_module(auto_import)

SOLOSTUDIO_OT_AutoImportVSE = auto_import.SOLOSTUDIO_OT_AutoImportVSE


class TestAutoImportResolveFilepath(unittest.TestCase):
    def _make_props(self, **kwargs):
        base = {
            "prompt_id": "pid-1",
            "comfyui_host": "127.0.0.1",
            "comfyui_port": 8188,
            "vse_channel": 1,
        }
        base.update(kwargs)
        return types.SimpleNamespace(**base)

    def test_resolve_filepath_uses_history_result(self):
        op = SOLOSTUDIO_OT_AutoImportVSE()
        op.output_filename = ""
        props = self._make_props()

        history = {
            "pid-1": {
                "outputs": {
                    "node1": {
                        "videos": [
                            {"filename": "video.mp4", "subfolder": "", "type": "output"}
                        ]
                    }
                }
            }
        }
        expected = "/home/test/ComfyUI/output/video.mp4"

        with mock.patch.object(auto_import, "get_history", return_value=history):
            with mock.patch.object(auto_import.os.path, "expanduser", return_value="/home/test"):
                with mock.patch.object(
                    auto_import.os.path,
                    "isfile",
                    side_effect=lambda p: p == expected,
                ):
                    result = op._resolve_filepath(props)

        self.assertEqual(result, expected)

    def test_resolve_filepath_falls_back_to_latest_output(self):
        op = SOLOSTUDIO_OT_AutoImportVSE()
        op.output_filename = ""
        props = self._make_props(prompt_id="")

        with mock.patch.object(op, "_find_latest_output", return_value="/tmp/fallback.mp4"):
            with mock.patch.object(auto_import.os.path, "isfile", return_value=True):
                result = op._resolve_filepath(props)

        self.assertEqual(result, "/tmp/fallback.mp4")


class TestAutoImportSceneResolution(unittest.TestCase):
    def test_get_or_create_vse_scene_returns_context_scene(self):
        op = SOLOSTUDIO_OT_AutoImportVSE()
        scene = types.SimpleNamespace(name="Scene")
        context = types.SimpleNamespace(scene=scene)
        self.assertIs(op._get_or_create_vse_scene(context), scene)

    def test_get_or_create_vse_scene_creates_when_missing(self):
        class _SceneList(list):
            def new(self, name):
                scene = types.SimpleNamespace(name=name)
                self.append(scene)
                return scene

        old_scenes = auto_import.bpy.data.scenes
        auto_import.bpy.data.scenes = _SceneList()
        try:
            op = SOLOSTUDIO_OT_AutoImportVSE()
            context = types.SimpleNamespace(scene=None)
            scene = op._get_or_create_vse_scene(context)
            self.assertIsNotNone(scene)
            self.assertEqual(scene.name, "VSE")
        finally:
            auto_import.bpy.data.scenes = old_scenes


def tearDownModule():
    _restore_patched_modules()


if __name__ == "__main__":
    unittest.main()
