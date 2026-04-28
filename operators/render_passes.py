"""
Phase 2 – マルチパス書き出しオペレーター
==========================================
Blender から AI に必要な素材を全自動で出力します。

レンダリングパス:
  - Depth    (Z-depth / Mist)
  - Lineart  (Freestyle / Grease Pencil)
  - Normal   (法線マップ – カメラワーク対策)
  - Mask     (キャラクターマスク – IP-Adapter 影響範囲限定)
  - BaseColor (Workbench Flat カラー)

各パスは <output_dir>/<pass_name>/frame_NNNN.png として保存されます。
"""

from __future__ import annotations

import os
import subprocess
import threading
from typing import IO
import bpy
from bpy.types import Operator, Context


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

_active_background_renders: list[tuple[subprocess.Popen, IO[str]]] = []
_background_lock = threading.Lock()


def _cleanup_finished_background_renders() -> None:
    with _background_lock:
        still_active: list[tuple[subprocess.Popen, IO[str]]] = []
        for process, log_file in _active_background_renders:
            if process.poll() is None:
                still_active.append((process, log_file))
            else:
                try:
                    log_file.close()
                except OSError:
                    pass
        _active_background_renders[:] = still_active


def _close_background_renders() -> None:
    with _background_lock:
        for _, log_file in _active_background_renders:
            try:
                log_file.close()
            except OSError:
                pass
        _active_background_renders.clear()


def _ensure_dir(path: str) -> str:
    abs_path = bpy.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def _frame_range(scene: bpy.types.Scene) -> tuple[int, int]:
    return scene.frame_start, scene.frame_end


# ---------------------------------------------------------------------------
# サブオペレーション: パスごとのシーン設定
# ---------------------------------------------------------------------------

def _setup_depth_pass(scene: bpy.types.Scene, out_dir: str) -> None:
    """Mist / Z-depth パス設定"""
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (-300, 0)

    normalize = tree.nodes.new("CompositorNodeNormalize")
    normalize.location = (0, 0)

    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)

    file_out = tree.nodes.new("CompositorNodeOutputFile")
    file_out.location = (300, -150)
    file_out.base_path = os.path.join(out_dir, "depth")
    file_out.format.file_format = "PNG"
    file_out.format.color_mode = "BW"
    file_out.file_slots[0].path = "frame_"

    # Mist パスを有効化
    scene.view_layers["ViewLayer"].use_pass_mist = True

    tree.links.new(rl.outputs["Mist"], normalize.inputs[0])
    tree.links.new(normalize.outputs[0], composite.inputs["Image"])
    tree.links.new(normalize.outputs[0], file_out.inputs[0])


def _setup_normal_pass(scene: bpy.types.Scene, out_dir: str) -> None:
    """Normal (法線) パス設定"""
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (-300, 0)

    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)

    file_out = tree.nodes.new("CompositorNodeOutputFile")
    file_out.location = (300, -150)
    file_out.base_path = os.path.join(out_dir, "normal")
    file_out.format.file_format = "PNG"
    file_out.format.color_mode = "RGB"
    file_out.file_slots[0].path = "frame_"

    scene.view_layers["ViewLayer"].use_pass_normal = True

    tree.links.new(rl.outputs["Normal"], composite.inputs["Image"])
    tree.links.new(rl.outputs["Normal"], file_out.inputs[0])


def _setup_mask_pass(
    scene: bpy.types.Scene,
    out_dir: str,
    char_collection: str | None,
) -> None:
    """キャラクターマスクパス設定 (Object Index / Cryptomatte)"""
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (-300, 0)

    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)

    file_out = tree.nodes.new("CompositorNodeOutputFile")
    file_out.location = (300, -150)
    file_out.base_path = os.path.join(out_dir, "mask")
    file_out.format.file_format = "PNG"
    file_out.format.color_mode = "BW"
    file_out.file_slots[0].path = "frame_"

    scene.view_layers["ViewLayer"].use_pass_object_index = True

    # ID Mask ノードで pass_index=1 のオブジェクトを白く表示
    id_mask = tree.nodes.new("CompositorNodeIDMask")
    id_mask.location = (0, 0)
    id_mask.index = 1
    id_mask.use_antialiasing = True

    tree.links.new(rl.outputs["IndexOB"], id_mask.inputs["ID value"])
    tree.links.new(id_mask.outputs["Alpha"], composite.inputs["Image"])
    tree.links.new(id_mask.outputs["Alpha"], file_out.inputs[0])


def _setup_base_color_pass(scene: bpy.types.Scene, out_dir: str) -> None:
    """Workbench Base Color パス設定"""
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (-300, 0)

    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)

    file_out = tree.nodes.new("CompositorNodeOutputFile")
    file_out.location = (300, -150)
    file_out.base_path = os.path.join(out_dir, "base_color")
    file_out.format.file_format = "PNG"
    file_out.format.color_mode = "RGB"
    file_out.file_slots[0].path = "frame_"

    scene.view_layers["ViewLayer"].use_pass_diffuse_color = True

    tree.links.new(rl.outputs["DiffCol"], composite.inputs["Image"])
    tree.links.new(rl.outputs["DiffCol"], file_out.inputs[0])


def _setup_lineart_pass(scene: bpy.types.Scene, out_dir: str) -> None:
    """Lineart / Freestyle パス設定"""
    scene.use_nodes = True
    scene.render.use_freestyle = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (-300, 0)

    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)

    file_out = tree.nodes.new("CompositorNodeOutputFile")
    file_out.location = (300, -150)
    file_out.base_path = os.path.join(out_dir, "lineart")
    file_out.format.file_format = "PNG"
    file_out.format.color_mode = "RGBA"
    file_out.file_slots[0].path = "frame_"

    tree.links.new(rl.outputs["Image"], composite.inputs["Image"])
    tree.links.new(rl.outputs["Image"], file_out.inputs[0])


# ---------------------------------------------------------------------------
# メインオペレーター
# ---------------------------------------------------------------------------

class SOLOSTUDIO_OT_RenderPasses(Operator):
    """選択したパスを一括レンダリングして出力ディレクトリへ保存する"""

    bl_idname = "solo_studio.render_passes"
    bl_label = "マルチパスレンダリング"
    bl_description = (
        "Depth / Lineart / Normal / Mask / Base Color を一括レンダリングします"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: Context) -> set[str]:
        props = context.scene.solo_studio
        scene = context.scene

        out_dir = _ensure_dir(props.output_dir)
        frame_start, frame_end = _frame_range(scene)

        # --- レンダーエンジン / 設定を保存 ---
        orig_engine = scene.render.engine
        orig_use_nodes = scene.use_nodes
        orig_node_tree = None  # node_tree は直接保存できないため None

        passes_to_render: list[tuple[str, callable]] = []

        if props.render_depth:
            passes_to_render.append(("depth", _setup_depth_pass))
        if props.render_lineart:
            passes_to_render.append(("lineart", _setup_lineart_pass))
        if props.render_normal:
            passes_to_render.append(("normal", _setup_normal_pass))
        if props.render_mask:
            passes_to_render.append(("mask", lambda s, d: _setup_mask_pass(s, d, None)))
        if props.render_base_color:
            passes_to_render.append(("base_color", _setup_base_color_pass))

        if not passes_to_render:
            self.report({"WARNING"}, "レンダリングするパスが選択されていません。")
            return {"CANCELLED"}

        total = len(passes_to_render)
        for idx, (pass_name, setup_fn) in enumerate(passes_to_render):
            self.report(
                {"INFO"},
                f"[{idx + 1}/{total}] {pass_name} パスをレンダリング中...",
            )
            scene.render.engine = "CYCLES"
            setup_fn(scene, out_dir)

            # アニメーションレンダリング実行
            bpy.ops.render.render(animation=True, write_still=False)

        # --- 設定を復元 ---
        scene.render.engine = orig_engine
        scene.use_nodes = orig_use_nodes

        self.report(
            {"INFO"},
            f"マルチパスレンダリング完了: {out_dir}",
        )
        props.generation_status = f"パス書き出し完了: {out_dir}"
        return {"FINISHED"}


class SOLOSTUDIO_OT_RenderDepthLineart(Operator):
    """Depth / Lineart をバックグラウンドでレンダリングして出力する"""

    bl_idname = "solo_studio.render_depth_lineart"
    bl_label = "Depth/Lineart をバックグラウンド出力"
    bl_description = "Blender をバックグラウンド起動して Depth/Lineart を書き出します"
    bl_options = {"REGISTER"}

    def execute(self, context: Context) -> set[str]:
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({"ERROR"}, "Blend ファイルを保存してから実行してください。")
            return {"CANCELLED"}

        blender_bin = bpy.app.binary_path
        if not blender_bin:
            self.report({"ERROR"}, "Blender 実行ファイルが見つかりません。")
            return {"CANCELLED"}

        script_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "utils",
                "depth_lineart_export.py",
            )
        )
        if not os.path.isfile(script_path):
            self.report({"ERROR"}, f"スクリプトが見つかりません: {script_path}")
            return {"CANCELLED"}

        output_root = bpy.path.abspath("//")
        log_path = os.path.join(output_root, "depth_lineart_render.log")
        command = [
            blender_bin,
            "-b",
            blend_path,
            "--python",
            script_path,
            "--",
            output_root,
        ]

        _cleanup_finished_background_renders()
        log_file: IO[str] | None = None
        try:
            # ログはバックグラウンドプロセス存続中に書き込まれるため開いたまま保持する
            log_file = open(log_path, "w", encoding="utf-8")
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            if log_file is not None:
                log_file.close()
            self.report({"ERROR"}, f"バックグラウンド実行に失敗しました: {exc}")
            return {"CANCELLED"}

        with _background_lock:
            _active_background_renders.append((process, log_file))
        self.report(
            {"INFO"},
            f"バックグラウンドで Depth/Lineart を出力しています。 (PID: {process.pid})",
        )
        self.report({"INFO"}, f"ログ出力: {log_path}")
        return {"FINISHED"}


def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_OT_RenderPasses)
    bpy.utils.register_class(SOLOSTUDIO_OT_RenderDepthLineart)


def unregister() -> None:
    _close_background_renders()
    bpy.utils.unregister_class(SOLOSTUDIO_OT_RenderDepthLineart)
    bpy.utils.unregister_class(SOLOSTUDIO_OT_RenderPasses)
