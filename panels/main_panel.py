"""
Phase 4 – SoloStudio Director N パネル UI
==========================================
View3D サイドバー（N パネル）に「SoloStudio」タブとして表示されます。

パネル構成:
  ▸ キャラクター設定    … char_ref.png パス指定
  ▸ レンダリングパス設定 … 出力先 / 各パスの ON/OFF
  ▸ AI 生成設定         … プロンプト / CFG / ステップ / シード
  ▸ AnimateDiff 設定    … コンテキスト長 / 重複
  ▸ ComfyUI 接続設定    … ホスト / ポート
  ▸ 実行               … マルチパスレンダリング → ComfyUI 送信
  ▸ 進捗               … プログレスバー / ステータス
  ▸ ポストプロセス      … VSE 自動インポート設定 / 手動インポート
"""

from __future__ import annotations

import bpy
from bpy.types import Panel, Context


_CATEGORY = "SoloStudio"
_REGION_TYPE = "UI"
_SPACE_TYPE = "VIEW_3D"


# ---------------------------------------------------------------------------
# ベースパネル
# ---------------------------------------------------------------------------

class _SoloStudioPanelBase(Panel):
    bl_space_type = _SPACE_TYPE
    bl_region_type = _REGION_TYPE
    bl_category = _CATEGORY


# ---------------------------------------------------------------------------
# キャラクター設定パネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_Character(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_character"
    bl_label = "キャラクター設定"
    bl_order = 10

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        layout.label(text="キャラクター参照画像 (IP-Adapter):", icon="IMAGE_DATA")
        layout.prop(props, "char_ref_path", text="")


# ---------------------------------------------------------------------------
# レンダリングパス設定パネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_RenderPasses(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_render_passes"
    bl_label = "レンダリングパス設定"
    bl_order = 20
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        layout.prop(props, "output_dir")

        col = layout.column(align=True)
        col.label(text="有効なパス:", icon="RENDERLAYERS")
        row = col.row(align=True)
        row.prop(props, "render_depth", toggle=True)
        row.prop(props, "render_lineart", toggle=True)
        row = col.row(align=True)
        row.prop(props, "render_normal", toggle=True)
        row.prop(props, "render_mask", toggle=True)
        row = col.row(align=True)
        row.prop(props, "render_base_color", toggle=True)

        layout.separator()
        layout.operator(
            "solo_studio.render_passes",
            text="マルチパスレンダリング",
            icon="RENDER_ANIMATION",
        )
        layout.operator(
            "solo_studio.render_depth_lineart",
            text="Depth/Lineart をバックグラウンド出力",
            icon="RENDER_ANIMATION",
        )


# ---------------------------------------------------------------------------
# AI 生成設定パネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_AIGeneration(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_ai_generation"
    bl_label = "AI 生成設定"
    bl_order = 30

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        layout.label(text="プロンプト:", icon="TEXT")
        layout.prop(props, "positive_prompt", text="Positive")
        layout.prop(props, "negative_prompt", text="Negative")

        layout.separator()
        layout.label(text="サンプリング設定:", icon="SETTINGS")

        col = layout.column(align=True)
        col.prop(props, "steps")
        col.prop(props, "cfg_scale")
        col.prop(props, "seed")


# ---------------------------------------------------------------------------
# AnimateDiff 設定パネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_AnimateDiff(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_animatediff"
    bl_label = "AnimateDiff 設定"
    bl_order = 40
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        layout.label(text="Sliding Window Context:", icon="NLA")
        col = layout.column(align=True)
        col.prop(props, "context_length", text="コンテキスト長")
        col.prop(props, "context_overlap", text="重複フレーム数")


# ---------------------------------------------------------------------------
# ComfyUI 接続設定パネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_Connection(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_connection"
    bl_label = "ComfyUI 接続設定"
    bl_order = 50
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        col = layout.column(align=True)
        col.prop(props, "comfyui_host", text="ホスト")
        col.prop(props, "comfyui_port", text="ポート")


# ---------------------------------------------------------------------------
# 実行・進捗パネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_Execute(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_execute"
    bl_label = "実行 / 進捗"
    bl_order = 60

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        # --- 送信ボタン ---
        is_generating = "生成中" in props.generation_status

        row = layout.row(align=True)
        row.scale_y = 1.5
        op_row = row.row(align=True)
        op_row.enabled = not is_generating
        op_row.operator(
            "solo_studio.send_to_comfyui",
            text="▶ ComfyUI へ送信",
            icon="PLAY",
        )

        if is_generating:
            row.operator(
                "solo_studio.cancel_generation",
                text="",
                icon="X",
            )

        # --- プログレスバー ---
        layout.separator()
        layout.label(text=f"ステータス: {props.generation_status}", icon="INFO")

        if props.generation_progress > 0.0:
            layout.progress(
                factor=props.generation_progress,
                text=f"{int(props.generation_progress * 100)}%",
                type="BAR",
            )


# ---------------------------------------------------------------------------
# ポストプロセスパネル
# ---------------------------------------------------------------------------

class SOLOSTUDIO_PT_PostProcess(_SoloStudioPanelBase):
    bl_idname = "SOLOSTUDIO_PT_post_process"
    bl_label = "ポストプロセス (VSE)"
    bl_order = 70
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.solo_studio

        col = layout.column(align=True)
        col.prop(props, "auto_import_vse", text="生成後に VSE へ自動インポート")
        sub = col.column(align=True)
        sub.enabled = props.auto_import_vse
        sub.prop(props, "vse_channel", text="VSE チャンネル")

        layout.separator()
        layout.operator(
            "solo_studio.manual_import_vse",
            text="動画を手動で VSE へインポート",
            icon="SEQUENCE",
        )


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------

_CLASSES = [
    SOLOSTUDIO_PT_Character,
    SOLOSTUDIO_PT_RenderPasses,
    SOLOSTUDIO_PT_AIGeneration,
    SOLOSTUDIO_PT_AnimateDiff,
    SOLOSTUDIO_PT_Connection,
    SOLOSTUDIO_PT_Execute,
    SOLOSTUDIO_PT_PostProcess,
]


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
