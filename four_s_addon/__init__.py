"""
4'S Add-on Skeleton (Blender 4.x)
=================================
"""

from __future__ import annotations

import bpy
from bpy.props import (
    StringProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
    BoolProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

from . import operators, panels

bl_info = {
    "name": "4'S Add-on - SoloStudio AI Renderer",
    "author": "AKITO-AKI",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > SoloStudio",
    "description": "Blender + ComfyUI V2V コンポジットアドオン",
    "category": "Animation",
}


class SoloStudioProperties(PropertyGroup):
    """SoloStudio N パネルプロパティ"""

    # --- ComfyUI 接続設定 ---
    comfyui_host: StringProperty(
        name="ComfyUI ホスト",
        description="ComfyUI サーバーのホスト (例: 127.0.0.1)",
        default="127.0.0.1",
    )
    comfyui_port: IntProperty(
        name="ComfyUI ポート",
        description="ComfyUI サーバーのポート (例: 8188)",
        default=8188,
        min=1,
        max=65535,
    )

    # --- 出力設定 ---
    output_dir: StringProperty(
        name="出力ディレクトリ",
        description="マルチパスレンダリング結果の出力先",
        default="//renders",
        subtype="DIR_PATH",
    )

    # --- プロンプト設定 ---
    positive_prompt: StringProperty(
        name="ポジティブプロンプト",
        description="生成したい画像の指示",
        default="anime style, detailed background, beautiful lighting",
    )
    negative_prompt: StringProperty(
        name="ネガティブプロンプト",
        description="避けたい要素",
        default="lowres, bad anatomy, worst quality, blurry",
    )

    # --- サンプリングパラメータ ---
    cfg_scale: FloatProperty(
        name="CFG Scale",
        description="プロンプト強度（高いほど従順だが多様性が減る）",
        default=7.0,
        min=1.0,
        max=20.0,
    )
    steps: IntProperty(
        name="サンプリングステップ",
        description="生成ステップ数（多いほど品質向上、時間増加）",
        default=20,
        min=5,
        max=100,
    )
    seed: IntProperty(
        name="Seed",
        description="乱数種（-1 で自動）",
        default=-1,
    )

    # --- AnimateDiff 設定 ---
    context_length: IntProperty(
        name="フレーム数",
        description="一度に生成するフレーム数（AnimateDiff）",
        default=16,
        min=4,
        max=64,
    )
    context_overlap: IntProperty(
        name="オーバーラップ",
        description="Sliding Window コンテキスト重複フレーム数",
        default=4,
        min=0,
        max=16,
    )

    # --- パス出力設定 ---
    render_depth: BoolProperty(
        name="Depth パス出力",
        description="Z深度パスを出力",
        default=True,
    )
    render_lineart: BoolProperty(
        name="Lineart パス出力",
        description="線画パスを出力",
        default=True,
    )
    render_normal: BoolProperty(
        name="Normal パス出力",
        description="法線パスを出力",
        default=True,
    )
    render_mask: BoolProperty(
        name="Mask パス出力",
        description="キャラマスクパスを出力",
        default=False,
    )
    render_base_color: BoolProperty(
        name="BaseColor パス出力",
        description="ベースカラーパスを出力",
        default=False,
    )

    # --- キャラクター参照画像 ---
    char_ref_path: StringProperty(
        name="キャラ参照画像パス",
        description="IP-Adapter 用キャラクター設定画像（PNG）",
        default="",
        subtype="FILE_PATH",
    )

    # --- VSE 設定 ---
    vse_channel: IntProperty(
        name="VSE チャンネル",
        description="生成動画を配置するシーケンサーチャンネル番号",
        default=1,
        min=1,
        max=32,
    )
    auto_import_vse: BoolProperty(
        name="VSE 自動インポート",
        description="生成完了後、自動的に VSE へ動画を取り込む",
        default=True,
    )

    # --- ステータス表示 ---
    generation_status: StringProperty(
        name="生成ステータス",
        description="現在の処理状態",
        default="待機中",
    )
    generation_progress: FloatProperty(
        name="生成進捗 (%)",
        description="生成進捗（0 ~ 100）",
        default=0.0,
        min=0.0,
        max=100.0,
    )
    progress: FloatProperty(
        name="進捗 (%)",
        description="生成進捗（0 ~ 100）",
        default=0.0,
        min=0.0,
        max=100.0,
    )
    is_running: BoolProperty(
        name="生成実行中",
        description="AI生成が進行中かどうか",
        default=False,
    )
    prompt_id: StringProperty(
        name="Prompt ID",
        description="ComfyUI の prompt_id",
        default="",
    )


def register() -> None:
    bpy.utils.register_class(SoloStudioProperties)
    bpy.types.Scene.solo_studio = PointerProperty(type=SoloStudioProperties)
    operators.register()
    panels.register()


def unregister() -> None:
    panels.unregister()
    operators.unregister()
    del bpy.types.Scene.solo_studio
    bpy.utils.unregister_class(SoloStudioProperties)
