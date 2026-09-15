"""
Depth / Lineart Export Script
=============================
シーンの Depth (Mist) と輪郭線 (Freestyle) を自動で書き出します。
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
import sys

import bpy

COLOR_MODE_BW = "BW"


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _configure_render_output(
    scene: bpy.types.Scene,
    filepath: str,
    color_mode: str,
) -> None:
    render = scene.render
    render.filepath = filepath
    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = color_mode
    render.use_file_extension = True


def _setup_depth_nodes(scene: bpy.types.Scene) -> None:
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    normalize = tree.nodes.new("CompositorNodeNormalize")
    composite = tree.nodes.new("CompositorNodeComposite")

    tree.links.new(rl.outputs["Mist"], normalize.inputs[0])
    tree.links.new(normalize.outputs[0], composite.inputs["Image"])


def _ensure_freestyle_lines(view_layer: bpy.types.ViewLayer) -> None:
    freestyle = view_layer.freestyle_settings
    if freestyle.linesets:
        lineset = freestyle.linesets[0]
    else:
        lineset = freestyle.linesets.new("LineSet")
        lineset.select_by_visibility = True

    linestyle = lineset.linestyle
    if hasattr(linestyle, "color"):
        linestyle.color = (1.0, 1.0, 1.0)
    if hasattr(linestyle, "thickness"):
        linestyle.thickness = 1.0


def _setup_lineart_nodes(scene: bpy.types.Scene) -> None:
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rgb = tree.nodes.new("CompositorNodeRGB")
    rgb.outputs[0].default_value = (0.0, 0.0, 0.0, 1.0)

    alpha_over = tree.nodes.new("CompositorNodeAlphaOver")
    alpha_over.inputs[0].default_value = 1.0

    composite = tree.nodes.new("CompositorNodeComposite")

    tree.links.new(rgb.outputs[0], alpha_over.inputs[1])
    tree.links.new(rl.outputs["Freestyle"], alpha_over.inputs[2])
    tree.links.new(alpha_over.outputs[0], composite.inputs["Image"])


def _collect_collection_objects(
    collection: bpy.types.Collection,
) -> set[bpy.types.Object]:
    collected: set[bpy.types.Object] = set()
    stack = [collection]
    while stack:
        current = stack.pop()
        collected.update(current.objects)
        stack.extend(current.children)
    return collected


def _renderable_target_objects(
    target_collection: bpy.types.Collection,
) -> set[bpy.types.Object]:
    return {
        obj for obj in _collect_collection_objects(target_collection)
        if getattr(obj, "type", None) not in {"CAMERA", "LIGHT"}
    }


@contextmanager
def _temporary_target_filter(
    scene: bpy.types.Scene,
    target_collection: bpy.types.Collection | None,
):
    if target_collection is None:
        yield
        return

    target_objects = _collect_collection_objects(target_collection)
    if not target_objects:
        yield
        return

    hidden_states: list[tuple[bpy.types.Object, bool]] = []
    for obj in scene.objects:
        if obj in target_objects or obj.type in {"CAMERA", "LIGHT"}:
            continue
        hidden_states.append((obj, obj.hide_render))
        obj.hide_render = True

    try:
        yield
    finally:
        for obj, original_hide in hidden_states:
            obj.hide_render = original_hide


def _resolve_camera(
    scene: bpy.types.Scene,
    camera_name: str | None,
) -> bpy.types.Object | None:
    if camera_name:
        camera = bpy.data.objects.get(camera_name)
        if camera is None or camera.type != "CAMERA":
            return None
        return camera
    return scene.camera


def export_depth_lineart(
    output_root: str | None = None,
    camera_name: str | None = None,
    target_collection_name: str | None = None,
) -> int:
    scene = bpy.context.scene
    view_layer = scene.view_layers[0]
    projection_camera = _resolve_camera(scene, camera_name)
    if projection_camera is None:
        print("[SoloStudio] ERROR: 投影カメラが見つかりません。")
        return 1

    target_collection = None
    if target_collection_name:
        target_collection = bpy.data.collections.get(target_collection_name)
        if target_collection is None:
            print(f"[SoloStudio] ERROR: Target Collection が見つかりません: {target_collection_name}")
            return 1
        if not _renderable_target_objects(target_collection):
            print("[SoloStudio] ERROR: Target Collection が空です。レンダリング対象を追加してください。")
            return 1

    project_dir = bpy.path.abspath("//")
    base_dir = output_root or project_dir
    base_dir = bpy.path.abspath(base_dir)

    try:
        depth_dir = _ensure_dir(os.path.join(base_dir, "depth"))
        lineart_dir = _ensure_dir(os.path.join(base_dir, "lineart"))
    except OSError as exc:
        print(f"[SoloStudio] ERROR: 出力ディレクトリの作成に失敗しました: {exc}")
        return 1

    # Depth -> Lineart の順でフルアニメーションを連続レンダリング
    print(f"[SoloStudio] Rendering frames {scene.frame_start} - {scene.frame_end}")
    original_camera = scene.camera
    scene.camera = projection_camera
    try:
        with _temporary_target_filter(scene, target_collection):
            view_layer.use_pass_mist = True
            _setup_depth_nodes(scene)
            _configure_render_output(scene, os.path.join(depth_dir, "depth_"), COLOR_MODE_BW)
            bpy.ops.render.render(animation=True, write_still=False)

            scene.render.use_freestyle = True
            if hasattr(view_layer, "use_freestyle"):
                view_layer.use_freestyle = True
            if hasattr(view_layer, "use_pass_freestyle"):
                view_layer.use_pass_freestyle = True
            scene.render.film_transparent = True
            _ensure_freestyle_lines(view_layer)
            _setup_lineart_nodes(scene)
            _configure_render_output(scene, os.path.join(lineart_dir, "lineart_"), COLOR_MODE_BW)
            bpy.ops.render.render(animation=True, write_still=False)
    finally:
        scene.camera = original_camera

    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root", nargs="?", default=None)
    parser.add_argument("--camera", dest="camera_name", default=None)
    parser.add_argument("--target-collection", dest="target_collection_name", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    cli_args = []
    if "--" in sys.argv:
        cli_args = sys.argv[sys.argv.index("--") + 1 :]
    parsed = _parse_args(cli_args)
    raise SystemExit(
        export_depth_lineart(
            output_root=parsed.output_root,
            camera_name=parsed.camera_name,
            target_collection_name=parsed.target_collection_name,
        ),
    )
