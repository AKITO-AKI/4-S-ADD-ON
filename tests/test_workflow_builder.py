"""
Tests for utils/workflow_builder.py

These tests run without Blender by mocking the bpy dependency.
"""

import sys
import types
import unittest

# ---------------------------------------------------------------------------
# Mock bpy so workflow_builder can be imported outside Blender
# ---------------------------------------------------------------------------

bpy_mock = types.ModuleType("bpy")


def _abspath(path: str) -> str:
    return path.lstrip("/")


bpy_mock.path = types.SimpleNamespace(abspath=_abspath)
# Force-set so this mock's 'path' attribute is present even when other test
# modules have already registered a simpler bpy mock earlier in the session.
sys.modules["bpy"] = bpy_mock

# Now import the module under test
import importlib, pathlib, sys as _sys

# Ensure the repo root is on sys.path
_repo_root = str(pathlib.Path(__file__).resolve().parents[1])
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

from utils.workflow_builder import (  # noqa: E402
    WorkflowParams,
    build_workflow,
    params_from_scene_props,
)


class TestBuildWorkflow(unittest.TestCase):
    """build_workflow() returns a well-formed ComfyUI API dict"""

    def setUp(self) -> None:
        self.params = WorkflowParams()
        self.workflow = build_workflow(self.params)

    # --- Basic structure -------------------------------------------------

    def test_returns_dict(self) -> None:
        self.assertIsInstance(self.workflow, dict)

    def test_has_checkpoint_node(self) -> None:
        node = self._find_node("CheckpointLoaderSimple")
        self.assertIsNotNone(node, "CheckpointLoaderSimple node not found")

    def test_has_ksampler_node(self) -> None:
        node = self._find_node("KSampler")
        self.assertIsNotNone(node, "KSampler node not found")

    def test_has_animatediff_node(self) -> None:
        node = self._find_node("ADE_AnimateDiffLoaderWithContext")
        self.assertIsNotNone(node, "AnimateDiff node not found")

    def test_has_video_output_node(self) -> None:
        node = self._find_node("VHS_VideoCombine")
        self.assertIsNotNone(node, "VHS_VideoCombine node not found")

    def test_has_ip_adapter_node(self) -> None:
        node = self._find_node("IPAdapterAdvanced")
        self.assertIsNotNone(node, "IPAdapterAdvanced node not found")

    def test_has_three_controlnet_apply_nodes(self) -> None:
        nodes = self._find_all_nodes("ControlNetApplyAdvanced")
        self.assertEqual(
            len(nodes),
            3,
            f"Expected 3 ControlNetApplyAdvanced nodes, got {len(nodes)}",
        )
    
    def test_has_freeu_node(self) -> None:
        node = self._find_node("FreeU")
        self.assertIsNotNone(node, "FreeU node not found")

    # --- Sampler params --------------------------------------------------

    def test_ksampler_uses_params_steps(self) -> None:
        ksampler = self._find_node("KSampler")
        self.assertEqual(ksampler["inputs"]["steps"], self.params.steps)

    def test_ksampler_uses_params_cfg(self) -> None:
        ksampler = self._find_node("KSampler")
        self.assertEqual(ksampler["inputs"]["cfg"], self.params.cfg_scale)

    def test_seed_random_when_negative(self) -> None:
        params = WorkflowParams(seed=-1)
        wf = build_workflow(params)
        ksampler = self._find_node_in("KSampler", wf)
        # Seed must be a non-negative integer
        self.assertGreaterEqual(ksampler["inputs"]["seed"], 0)

    def test_seed_fixed_when_positive(self) -> None:
        params = WorkflowParams(seed=42)
        wf = build_workflow(params)
        ksampler = self._find_node_in("KSampler", wf)
        self.assertEqual(ksampler["inputs"]["seed"], 42)

    # --- AnimateDiff params ----------------------------------------------

    def test_animatediff_context_length(self) -> None:
        params = WorkflowParams(context_length=24, context_overlap=6)
        wf = build_workflow(params)
        node = self._find_node_in("ADE_AnimateDiffLoaderWithContext", wf)
        ctx = node["inputs"]["context_options"]
        self.assertEqual(ctx["context_length"], 24)
        self.assertEqual(ctx["context_overlap"], 6)

    # --- ControlNet strengths -------------------------------------------

    def test_depth_controlnet_strength(self) -> None:
        params = WorkflowParams(depth_strength=0.9)
        wf = build_workflow(params)
        nodes = self._find_all_nodes_in("ControlNetApplyAdvanced", wf)
        # First apply node corresponds to depth
        depth_node = nodes[0]
        self.assertAlmostEqual(depth_node["inputs"]["strength"], 0.9)
    
    def test_controlnet_end_percent_defaults_to_0_8(self) -> None:
        wf = build_workflow(WorkflowParams())
        nodes = self._find_all_nodes_in("ControlNetApplyAdvanced", wf)
        for node in nodes:
            self.assertAlmostEqual(node["inputs"]["end_percent"], 0.8)

    # --- All node ids are unique -----------------------------------------

    def test_node_ids_unique(self) -> None:
        ids = list(self.workflow.keys())
        self.assertEqual(len(ids), len(set(ids)), "Duplicate node IDs found")

    # --- Helpers ---------------------------------------------------------

    def _find_node(self, class_type: str) -> dict | None:
        return self._find_node_in(class_type, self.workflow)

    def _find_node_in(self, class_type: str, wf: dict) -> dict | None:
        for node in wf.values():
            if node.get("class_type") == class_type:
                return node
        return None

    def _find_all_nodes(self, class_type: str) -> list[dict]:
        return self._find_all_nodes_in(class_type, self.workflow)

    def _find_all_nodes_in(self, class_type: str, wf: dict) -> list[dict]:
        return [n for n in wf.values() if n.get("class_type") == class_type]


class TestParamsFromSceneProps(unittest.TestCase):
    """params_from_scene_props() correctly maps Blender properties"""

    def _make_props(self, **kwargs) -> types.SimpleNamespace:
        defaults = dict(
            positive_prompt="test positive",
            negative_prompt="test negative",
            cfg_scale=8.5,
            steps=30,
            seed=123,
            context_length=16,
            context_overlap=4,
            char_ref_path="",
            auto_context_overlap=False,
            camera_velocity_threshold=0.1,
            context_overlap_high_motion=8,
            controlnet_start_percent=0.0,
            controlnet_end_percent=0.8,
            use_ip_adapter_mask=True,
            use_freeu=True,
            freeu_b1=1.1,
            freeu_b2=1.2,
            freeu_s1=0.6,
            freeu_s2=0.4,
        )
        defaults.update(kwargs)
        return types.SimpleNamespace(**defaults)

    def test_positive_prompt_mapped(self) -> None:
        props = self._make_props(positive_prompt="anime girl")
        params = params_from_scene_props(props)
        self.assertEqual(params.positive_prompt, "anime girl")

    def test_cfg_scale_mapped(self) -> None:
        props = self._make_props(cfg_scale=9.0)
        params = params_from_scene_props(props)
        self.assertAlmostEqual(params.cfg_scale, 9.0)

    def test_seed_mapped(self) -> None:
        props = self._make_props(seed=999)
        params = params_from_scene_props(props)
        self.assertEqual(params.seed, 999)

    def test_default_char_ref_when_empty(self) -> None:
        props = self._make_props(char_ref_path="")
        params = params_from_scene_props(props)
        self.assertEqual(params.char_ref_image, "char_ref.png")

    def test_char_ref_basename_extracted(self) -> None:
        props = self._make_props(char_ref_path="//my_char.png")
        params = params_from_scene_props(props)
        self.assertEqual(params.char_ref_image, "my_char.png")

    def test_controlnet_window_mapped(self) -> None:
        props = self._make_props(controlnet_start_percent=0.2, controlnet_end_percent=0.7)
        params = params_from_scene_props(props)
        self.assertAlmostEqual(params.controlnet_start, 0.2)
        self.assertAlmostEqual(params.controlnet_end, 0.7)

    def test_controlnet_window_sanitized(self) -> None:
        props = self._make_props(controlnet_start_percent=0.9, controlnet_end_percent=0.2)
        params = params_from_scene_props(props)
        self.assertAlmostEqual(params.controlnet_start, 0.9)
        self.assertAlmostEqual(params.controlnet_end, 0.9)


class TestWorkflowParams(unittest.TestCase):
    """WorkflowParams dataclass defaults are sane"""

    def test_default_checkpoint(self) -> None:
        p = WorkflowParams()
        self.assertIn("animagine", p.checkpoint.lower())

    def test_default_motion_module(self) -> None:
        p = WorkflowParams()
        self.assertTrue(p.animatediff_motion_module)

    def test_context_length_range(self) -> None:
        # AnimateDiff works best with multiples of 8
        p = WorkflowParams()
        self.assertGreaterEqual(p.context_length, 8)
        self.assertLessEqual(p.context_length, 32)


if __name__ == "__main__":
    unittest.main()
