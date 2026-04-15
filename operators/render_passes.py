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
import bpy
from bpy.types import Operator, Context

_LINEART_DISTANCE_DRIVER_EXPR = (
    # 線幅 = base_thickness * (ref_distance / camera-target distance)
    # を最小/最大値でクランプし、遠景で潰れ・近景で太りすぎる問題を抑える。
    "max(line_min, min(line_max, line_base * line_ref / "
    "max(sqrt((cam_x-tgt_x)**2 + (cam_y-tgt_y)**2 + (cam_z-tgt_z)**2), 0.001)))"
)


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _ensure_dir(path: str) -> str:
    abs_path = bpy.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def _frame_range(scene: bpy.types.Scene) -> tuple[int, int]:
    return scene.frame_start, scene.frame_end


# ---------------------------------------------------------------------------
# サブオペレーション: パスごとのシーン設定
# ---------------------------------------------------------------------------

def _setup_depth_pass(scene: bpy.types.Scene, out_dir: str, props: object) -> None:
    """Mist / Z-depth パス設定"""
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (-300, 0)

    map_range = tree.nodes.new("CompositorNodeMapRange")
    map_range.location = (0, 0)
    near = float(getattr(props, "depth_near", 2.0))
    far = float(getattr(props, "depth_far", 10.0))
    if far <= near:
        print("[SoloStudio] Depth正規化設定が不正なため far を自動補正しました。")
        far = near + 0.01
    map_range.inputs[1].default_value = near
    map_range.inputs[2].default_value = far
    map_range.inputs[3].default_value = 0.0
    map_range.inputs[4].default_value = 1.0
    map_range.use_clamp = True

    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)

    file_out = tree.nodes.new("CompositorNodeOutputFile")
    file_out.location = (300, -150)
    file_out.base_path = os.path.join(out_dir, "depth")
    file_out.format.file_format = "PNG"
    file_out.format.color_mode = "BW"
    file_out.file_slots[0].path = "frame_"

    # Mist パスを有効化
    view_layer = scene.view_layers.get("ViewLayer")
    if view_layer is not None:
        view_layer.use_pass_mist = True

    if scene.world is not None and hasattr(scene.world, "mist_settings"):
        mist = scene.world.mist_settings
        mist.use_mist = True
        mist.start = near
        mist.depth = far - near

    tree.links.new(rl.outputs["Mist"], map_range.inputs[0])
    tree.links.new(map_range.outputs[0], composite.inputs["Image"])
    tree.links.new(map_range.outputs[0], file_out.inputs[0])


def _setup_normal_pass(scene: bpy.types.Scene, out_dir: str, props: object) -> None:
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
    file_out.format.color_depth = str(getattr(props, "normal_color_depth", "16"))
    file_out.file_slots[0].path = "frame_"

    view_layer = scene.view_layers.get("ViewLayer")
    if view_layer is not None:
        view_layer.use_pass_normal = True

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


def _setup_lineart_driver(scene: bpy.types.Scene, props: object) -> None:
    """カメラ距離に応じてFreestyleの線幅を補正するドライバーを設定。"""
    if not hasattr(scene.render, "line_thickness"):
        return
    cam = scene.camera
    if cam is None:
        return

    focus_obj = getattr(cam.data, "dof", None)
    focus_obj = getattr(focus_obj, "focus_object", None)
    if focus_obj is None:
        return
    target_loc = focus_obj.matrix_world.translation

    scene["solo_lineart_target_x"] = float(target_loc[0])
    scene["solo_lineart_target_y"] = float(target_loc[1])
    scene["solo_lineart_target_z"] = float(target_loc[2])
    scene["solo_lineart_ref_distance"] = float(getattr(props, "lineart_ref_distance", 5.0))
    scene["solo_lineart_base_thickness"] = float(getattr(props, "lineart_base_thickness", 1.0))
    scene["solo_lineart_min_thickness"] = float(getattr(props, "lineart_min_thickness", 0.5))
    scene["solo_lineart_max_thickness"] = float(getattr(props, "lineart_max_thickness", 3.0))

    scene.render.line_thickness = float(getattr(props, "lineart_base_thickness", 1.0))
    try:
        scene.render.driver_remove("line_thickness")
    except Exception:
        pass
    fcurve = scene.render.driver_add("line_thickness")
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    # 基準距離に対して逆比例で太さを補正し、最小/最大値にクランプする。
    driver.expression = _LINEART_DISTANCE_DRIVER_EXPR

    defs = [
        ("cam_x", cam, "location.x"),
        ("cam_y", cam, "location.y"),
        ("cam_z", cam, "location.z"),
        ("tgt_x", scene, '["solo_lineart_target_x"]'),
        ("tgt_y", scene, '["solo_lineart_target_y"]'),
        ("tgt_z", scene, '["solo_lineart_target_z"]'),
        ("line_ref", scene, '["solo_lineart_ref_distance"]'),
        ("line_base", scene, '["solo_lineart_base_thickness"]'),
        ("line_min", scene, '["solo_lineart_min_thickness"]'),
        ("line_max", scene, '["solo_lineart_max_thickness"]'),
    ]
    for name, target, data_path in defs:
        var = driver.variables.new()
        var.name = name
        # driver target は scene または camera object のみを使う設計。
        if target == scene:
            var.targets[0].id_type = "SCENE"
        elif target == cam:
            var.targets[0].id_type = "OBJECT"
        else:
            continue
        var.targets[0].id = target
        var.targets[0].data_path = data_path


def _setup_lineart_pass(scene: bpy.types.Scene, out_dir: str, props: object) -> None:
    """Lineart / Freestyle パス設定"""
    scene.use_nodes = True
    scene.render.use_freestyle = True
    scene.render.line_thickness_mode = "ABSOLUTE"
    scene.render.filter_size = float(getattr(props, "lineart_aa_filter_size", 1.5))
    _setup_lineart_driver(scene, props)
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

    # SOFTENフィルタをLineartのアンチエイリアス補助として使用。
    lineart_soften_filter = tree.nodes.new("CompositorNodeFilter")
    lineart_soften_filter.location = (20, 0)
    lineart_soften_filter.filter_type = "SOFTEN"

    tree.links.new(rl.outputs["Image"], lineart_soften_filter.inputs["Image"])
    tree.links.new(lineart_soften_filter.outputs["Image"], composite.inputs["Image"])
    tree.links.new(lineart_soften_filter.outputs["Image"], file_out.inputs[0])


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
        orig_view_transform = scene.view_settings.view_transform
        orig_node_tree = None  # node_tree は直接保存できないため None

        passes_to_render: list[tuple[str, callable]] = []

        if props.render_depth:
            passes_to_render.append(("depth", lambda s, d: _setup_depth_pass(s, d, props)))
        if props.render_lineart:
            passes_to_render.append(("lineart", lambda s, d: _setup_lineart_pass(s, d, props)))
        if props.render_normal:
            passes_to_render.append(("normal", lambda s, d: _setup_normal_pass(s, d, props)))
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
            if pass_name == "normal":
                scene.view_settings.view_transform = "Raw"
            else:
                scene.view_settings.view_transform = orig_view_transform

            # アニメーションレンダリング実行
            bpy.ops.render.render(animation=True, write_still=False)

        # --- 設定を復元 ---
        scene.render.engine = orig_engine
        scene.use_nodes = orig_use_nodes
        scene.view_settings.view_transform = orig_view_transform

        self.report(
            {"INFO"},
            f"マルチパスレンダリング完了: {out_dir}",
        )
        props.generation_status = f"パス書き出し完了: {out_dir}"
        return {"FINISHED"}


def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_OT_RenderPasses)


def unregister() -> None:
    bpy.utils.unregister_class(SOLOSTUDIO_OT_RenderPasses)
