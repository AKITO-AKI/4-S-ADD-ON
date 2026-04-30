"""
Tests for operators/batch_processor.py

Tests run outside Blender by mocking bpy dependencies.
"""

import sys
import types
import unittest
import pathlib

# ---------------------------------------------------------------------------
# Minimal bpy mock
# ---------------------------------------------------------------------------

bpy_mock = types.ModuleType("bpy")

# bpy.path.abspath: strip leading "//"
bpy_mock.path = types.SimpleNamespace(abspath=lambda p: p.lstrip("//"))

# bpy.app.timers stub
_registered_timers: list = []


def _timers_register(fn, first_interval=0.0, persistent=False):
    _registered_timers.append(fn)


def _timers_unregister(fn):
    if fn in _registered_timers:
        _registered_timers.remove(fn)


def _timers_is_registered(fn):
    return fn in _registered_timers


bpy_mock.app = types.SimpleNamespace(
    timers=types.SimpleNamespace(
        register=_timers_register,
        unregister=_timers_unregister,
        is_registered=_timers_is_registered,
    )
)

# bpy.utils stub
_registered_classes: list = []


def _register_class(cls):
    _registered_classes.append(cls)


def _unregister_class(cls):
    if cls in _registered_classes:
        _registered_classes.remove(cls)


bpy_mock.utils = types.SimpleNamespace(
    register_class=_register_class,
    unregister_class=_unregister_class,
)

# bpy.types stubs
bpy_mock.types = types.SimpleNamespace(
    Operator=object,
    Context=object,
    Scene=object,
)

# bpy.props stubs
bpy_mock.props = types.SimpleNamespace(
    StringProperty=lambda **kw: None,
    IntProperty=lambda **kw: None,
    FloatProperty=lambda **kw: None,
    BoolProperty=lambda **kw: None,
)

sys.modules["bpy"] = bpy_mock
sys.modules["bpy.types"] = bpy_mock.types
sys.modules["bpy.props"] = bpy_mock.props

# ---------------------------------------------------------------------------
# Stub out heavy addon dependencies so we can import batch_processor
# ---------------------------------------------------------------------------

# Stub the utils package
utils_pkg = types.ModuleType("utils")
sys.modules.setdefault("utils", utils_pkg)

comfyui_api_mod = types.ModuleType("utils.comfyui_api")
comfyui_api_mod.queue_prompt = lambda *a, **kw: {"prompt_id": "test-id"}
comfyui_api_mod.upload_image = lambda *a, **kw: {"name": "test.png"}
sys.modules["utils.comfyui_api"] = comfyui_api_mod

workflow_builder_mod = types.ModuleType("utils.workflow_builder")


class _FakeParams:
    depth_image = ""
    frame_count = 1
    seed = -1


workflow_builder_mod.build_workflow = lambda p: {}
workflow_builder_mod.params_from_scene_props = lambda props: _FakeParams()
sys.modules["utils.workflow_builder"] = workflow_builder_mod

async_handler_mod = types.ModuleType("utils.async_handler")


class _FakeAsyncGenerationHandler:
    def __init__(self, props, on_complete=None, on_error=None):
        self.on_complete = on_complete
        self.on_error = on_error

    def start(self, host, port, prompt_id, client_id):
        pass

    def stop(self):
        pass


async_handler_mod.AsyncGenerationHandler = _FakeAsyncGenerationHandler
sys.modules["utils.async_handler"] = async_handler_mod

# Ensure the repo root is on sys.path
_repo_root = str(pathlib.Path(__file__).resolve().parents[1])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import importlib

# Provide relative-import stubs so the operators package can be used standalone
operators_pkg = types.ModuleType("operators")
sys.modules.setdefault("operators", operators_pkg)

# Patch relative imports inside batch_processor by pre-populating submodule paths
for key in list(sys.modules):
    pass

# We import the file directly as a top-level module to avoid relative import issues
import importlib.util

_batch_spec = importlib.util.spec_from_file_location(
    "batch_processor",
    str(pathlib.Path(__file__).resolve().parent.parent / "operators" / "batch_processor.py"),
)
batch_processor = importlib.util.module_from_spec(_batch_spec)

# Provide the relative imports that batch_processor needs
sys.modules["batch_processor"] = batch_processor
# Stub the relative-import targets used inside batch_processor
sys.modules.setdefault("operators.batch_processor", batch_processor)

# Replace relative imports in the source with already-registered modules
sys.modules["operators.utils"] = utils_pkg
sys.modules["operators.utils.comfyui_api"] = comfyui_api_mod
sys.modules["operators.utils.workflow_builder"] = workflow_builder_mod
sys.modules["operators.utils.async_handler"] = async_handler_mod

# Temporarily redirect relative imports
_orig_comfyui = sys.modules.get("..utils.comfyui_api")
_orig_workflow = sys.modules.get("..utils.workflow_builder")
_orig_async = sys.modules.get("..utils.async_handler")

# The module uses relative imports like `from ..utils.comfyui_api import ...`
# We load it by patching __package__ to make Python resolve the relative paths.
batch_processor.__package__ = "operators"
batch_processor.__spec__.submodule_search_locations = None

# Register ancestor packages
four_s_pkg = types.ModuleType("four_s_addon")
sys.modules.setdefault("four_s_addon", four_s_pkg)
sys.modules.setdefault("four_s_addon.utils", utils_pkg)
sys.modules.setdefault("four_s_addon.utils.comfyui_api", comfyui_api_mod)
sys.modules.setdefault("four_s_addon.utils.workflow_builder", workflow_builder_mod)
sys.modules.setdefault("four_s_addon.utils.async_handler", async_handler_mod)
sys.modules.setdefault("four_s_addon.operators", operators_pkg)

# Update package name so relative imports resolve correctly
batch_processor.__package__ = "four_s_addon.operators"

_batch_spec.loader.exec_module(batch_processor)

configure_vse_mp4_export = batch_processor.configure_vse_mp4_export
_BatchContext = batch_processor._BatchContext
_resolve_comfyui_output = batch_processor._resolve_comfyui_output


# ---------------------------------------------------------------------------
# Test: configure_vse_mp4_export
# ---------------------------------------------------------------------------

class TestConfigureVseMp4Export(unittest.TestCase):
    """configure_vse_mp4_export() correctly configures scene render settings."""

    def _make_scene(self):
        """Build a minimal mock scene mimicking bpy.types.Scene."""
        ffmpeg = types.SimpleNamespace(
            format=None,
            codec=None,
            constant_rate_factor=None,
            ffmpeg_preset=None,
            audio_codec=None,
        )
        image_settings = types.SimpleNamespace(file_format=None)
        render = types.SimpleNamespace(
            image_settings=image_settings,
            ffmpeg=ffmpeg,
            filepath=None,
        )
        return types.SimpleNamespace(render=render)

    def test_file_format_set_to_ffmpeg(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.image_settings.file_format, "FFMPEG")

    def test_ffmpeg_format_set_to_mpeg4(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.ffmpeg.format, "MPEG4")

    def test_codec_set_to_h264(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.ffmpeg.codec, "H264")

    def test_audio_codec_set_to_aac(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.ffmpeg.audio_codec, "AAC")

    def test_default_output_path(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.filepath, "//output.mp4")

    def test_custom_output_path(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene, output_path="/tmp/my_video.mp4")
        self.assertEqual(scene.render.filepath, "/tmp/my_video.mp4")

    def test_crf_set(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.ffmpeg.constant_rate_factor, "MEDIUM")

    def test_preset_set(self):
        scene = self._make_scene()
        configure_vse_mp4_export(scene)
        self.assertEqual(scene.render.ffmpeg.ffmpeg_preset, "GOOD")


# ---------------------------------------------------------------------------
# Test: _BatchContext
# ---------------------------------------------------------------------------

class TestBatchContext(unittest.TestCase):
    """_BatchContext correctly tracks batch state."""

    def _make_ctx(self, start=1, end=10):
        props = types.SimpleNamespace(batch_status="", batch_progress=0.0)
        return _BatchContext(
            frame_start=start,
            frame_end=end,
            output_dir="/tmp/test_batch",
            vse_channel=1,
            props=props,
        )

    def test_initial_state_is_render_depth(self):
        ctx = self._make_ctx()
        self.assertEqual(ctx.state, "render_depth")

    def test_initial_current_frame_equals_start(self):
        ctx = self._make_ctx(start=5, end=20)
        self.assertEqual(ctx.current_frame, 5)

    def test_total_frames(self):
        ctx = self._make_ctx(start=1, end=10)
        self.assertEqual(ctx.total_frames, 10)

    def test_total_frames_single(self):
        ctx = self._make_ctx(start=7, end=7)
        self.assertEqual(ctx.total_frames, 1)

    def test_initial_progress_is_zero(self):
        ctx = self._make_ctx(start=1, end=10)
        self.assertAlmostEqual(ctx.progress, 0.0)

    def test_progress_after_half(self):
        ctx = self._make_ctx(start=1, end=10)
        ctx.current_frame = 6  # 5 frames completed out of 10
        self.assertAlmostEqual(ctx.progress, 0.5)

    def test_progress_full_when_total_zero(self):
        ctx = self._make_ctx(start=5, end=4)  # invalid range → total=0
        self.assertAlmostEqual(ctx.progress, 1.0)

    def test_completed_frames(self):
        ctx = self._make_ctx(start=1, end=10)
        ctx.current_frame = 4
        self.assertEqual(ctx.completed_frames, 3)

    def test_handler_initially_none(self):
        ctx = self._make_ctx()
        self.assertIsNone(ctx.handler)

    def test_handler_done_initially_false(self):
        ctx = self._make_ctx()
        self.assertFalse(ctx.handler_done)

    def test_generated_images_initially_empty(self):
        ctx = self._make_ctx()
        self.assertEqual(ctx.generated_images, {})


# ---------------------------------------------------------------------------
# Test: _resolve_comfyui_output
# ---------------------------------------------------------------------------

class TestResolveComfyuiOutput(unittest.TestCase):
    """_resolve_comfyui_output returns '' when file does not exist."""

    def test_returns_empty_for_nonexistent_filename(self):
        result = _resolve_comfyui_output("nonexistent_xyz_12345.png")
        self.assertEqual(result, "")

    def test_returns_abs_path_when_file_exists(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        try:
            result = _resolve_comfyui_output(tmp_path)
            self.assertEqual(result, tmp_path)
        finally:
            import os
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
