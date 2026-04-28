"""
Depth / Lineart Export Script
=============================
シーンの Depth (Mist) と輪郭線 (Freestyle) を自動で書き出します。
"""

from __future__ import annotations

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


def export_depth_lineart(output_root: str | None = None) -> None:
    scene = bpy.context.scene
    view_layer = scene.view_layers[0]

    project_dir = bpy.path.abspath("//")
    base_dir = output_root or project_dir
    base_dir = bpy.path.abspath(base_dir)

    depth_dir = _ensure_dir(os.path.join(base_dir, "depth"))
    lineart_dir = _ensure_dir(os.path.join(base_dir, "lineart"))

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


def _parse_output_root(argv: list[str]) -> str | None:
    if "--" not in argv:
        return None
    idx = argv.index("--")
    if idx + 1 >= len(argv):
        return None
    return argv[idx + 1]


if __name__ == "__main__":
    export_depth_lineart(_parse_output_root(sys.argv))
