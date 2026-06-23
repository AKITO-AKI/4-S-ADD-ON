"""
Panels for 4'S Add-on - SoloStudio N パネル
===========================================
"""

from __future__ import annotations

import bpy
from bpy.types import Panel, Context


class SOLOSTUDIO_PT_MainPanel(Panel):
    """メインパネル - コネクション＆基本設定"""

    bl_idname = "SOLOSTUDIO_PT_main_panel"
    bl_label = "SoloStudio Director"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SoloStudio"

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        # --- ComfyUI 接続 ---
        box = layout.box()
        box.label(text="ComfyUI 接続", icon="NETWORK_DRIVE")
        row = box.row()
        row.prop(props, "comfyui_host", text="ホスト")
        row.prop(props, "comfyui_port", text="ポート")

        # --- パス抽出 ---
        box = layout.box()
        box.label(text="マルチパスレンダリング", icon="RENDER_RESULT")
        box.prop(props, "output_dir", text="出力先")
        col = box.column(heading="出力パス")
        col.prop(props, "render_depth", text="Depth")
        col.prop(props, "render_lineart", text="Lineart")
        col.prop(props, "render_normal", text="Normal")
        col.prop(props, "render_mask", text="Mask")
        col.prop(props, "render_base_color", text="BaseColor")

        row = box.row()
        row.enabled = not props.is_running
        row.operator(
            "solo_studio.render_passes",
            text="レンダリング実行",
            icon="PLAY",
        )
        row.operator(
            "solo_studio.render_depth_lineart",
            text="バックグラウンド出力",
            icon="BLANK1",
        )

        # --- AI生成設定 ---
        box = layout.box()
        box.label(text="AI生成設定", icon="IMAGE_DATA")
        box.prop(props, "char_ref_path", text="キャラ参照画像")
        box.prop(props, "positive_prompt", text="ポジティブ")
        box.prop(props, "negative_prompt", text="ネガティブ")

        col = box.column(heading="パラメータ")
        col.prop(props, "cfg_scale", text="CFG Scale", slider=True)
        col.prop(props, "steps", text="ステップ", slider=True)
        col.prop(props, "seed", text="Seed")
        col.prop(props, "context_length", text="フレーム数", slider=True)
        col.prop(props, "context_overlap", text="オーバーラップ", slider=True)

        # --- 生成実行 ---
        row = box.row()
        row.enabled = not props.is_running
        row.operator(
            "solo_studio.send_to_comfyui",
            text="ComfyUI へ送信",
            icon="PLAY",
        )
        if props.is_running:
            row = box.row()
            row.operator(
                "solo_studio.cancel_generation",
                text="キャンセル",
                icon="X",
            )

        # --- VSE 設定 ---
        box = layout.box()
        box.label(text="ビデオシーケンサー", icon="SEQUENCE")
        box.prop(props, "vse_channel", text="チャンネル", slider=True)
        box.prop(props, "auto_import_vse", text="自動インポート")

        # --- ステータス表示 ---
        box = layout.box()
        box.label(text="ステータス", icon="INFO")
        box.label(text=f"状態: {props.generation_status}")
        if props.is_running:
            box.prop(
                props,
                "generation_progress",
                text="進捗",
                slider=True,
            )


class SOLOSTUDIO_PT_DebugPanel(Panel):
    """デバッグ情報パネル"""

    bl_idname = "SOLOSTUDIO_PT_debug_panel"
    bl_label = "デバッグ情報"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SoloStudio"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        layout.label(text=f"Prompt ID: {props.prompt_id}")
        layout.label(text=f"実行中: {'はい' if props.is_running else 'いいえ'}")


def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_PT_MainPanel)
    bpy.utils.register_class(SOLOSTUDIO_PT_DebugPanel)


def unregister() -> None:
    bpy.utils.unregister_class(SOLOSTUDIO_PT_DebugPanel)
    bpy.utils.unregister_class(SOLOSTUDIO_PT_MainPanel)
