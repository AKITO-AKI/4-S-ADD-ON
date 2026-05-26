"""
4-S-ADD-ON  –  SoloStudio Director
====================================
Blenderの3DモーションデータとローカルAI（ComfyUI）をAPIで連携させ、
キャラクターの演技とカメラワークを活かした高品質アニメーションを生成する
「一人アニメスタジオ」アドオン。

開発ロードマップ:
  Phase 1  核となるAIパイプライン (ComfyUI ワークフロー確定)
  Phase 2  Blender データ抽出エンジン (マルチパス書き出し)
  Phase 3  API 連携と非同期通信 (フリーズ対策 / WebSocket 進捗)
  Phase 4  ポストプロセスと UI のブラッシュアップ (VSE 自動インポート)
"""

bl_info = {
    "name": "4-S-ADD-ON: SoloStudio Director",
    "author": "AKITO-AKI",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > SoloStudio",
    "description": (
        "BlenderモーションデータとComfyUIを連携させた一人アニメスタジオ。"
        "マルチパスレンダリング、ComfyUI API送信、VSE自動インポートを提供します。"
    ),
    "category": "Animation",
    "doc_url": "https://github.com/AKITO-AKI/4-S-ADD-ON",
    "tracker_url": "https://github.com/AKITO-AKI/4-S-ADD-ON/issues",
}

import bpy
from bpy.props import BoolProperty
from bpy.types import AddonPreferences

from . import properties
from .operators import (
    render_passes,
    send_to_comfyui,
    auto_import,
    batch_processor,
    tutorial,
)
from .panels import main_panel


# ---------------------------------------------------------------------------
# アドオンプリファレンス（初回チュートリアル状態管理）
# ---------------------------------------------------------------------------

class SoloStudioAddonPreferences(AddonPreferences):
    """SoloStudio Director のアドオンプリファレンス"""

    bl_idname = __name__

    tutorial_completed: BoolProperty(
        name="セットアップガイド完了",
        description="初回セットアップガイドを完了済みかどうか",
        default=False,
    )

    def draw(self, context) -> None:
        layout = self.layout
        layout.label(text="SoloStudio Director プリファレンス", icon="FUND")
        row = layout.row(align=True)
        row.prop(self, "tutorial_completed")
        row.operator(
            "solo_studio.open_tutorial",
            text="セットアップガイドを開く",
            icon="HELP",
        )


# ---------------------------------------------------------------------------
# 初回起動チュートリアルタイマー
# ---------------------------------------------------------------------------

def _show_first_run_tutorial() -> None:
    """アドオン登録後に一度だけ実行し、初回ならチュートリアルを開く。"""
    try:
        addon_entry = bpy.context.preferences.addons.get(__name__)
        if addon_entry is not None and not addon_entry.preferences.tutorial_completed:
            bpy.ops.solo_studio.open_tutorial("INVOKE_DEFAULT")
    except Exception:
        pass
    return None  # タイマーを再登録しない


# ---------------------------------------------------------------------------
# 登録 / 解除
# ---------------------------------------------------------------------------

def register() -> None:
    bpy.utils.register_class(SoloStudioAddonPreferences)
    properties.register()
    render_passes.register()
    send_to_comfyui.register()
    auto_import.register()
    batch_processor.register()
    tutorial.register()
    main_panel.register()

    # 初回起動チュートリアルを 0.5 秒後に表示（UI 描画完了後に確実に開くため）
    bpy.app.timers.register(_show_first_run_tutorial, first_interval=0.5, persistent=False)


def unregister() -> None:
    main_panel.unregister()
    tutorial.unregister()
    batch_processor.unregister()
    auto_import.unregister()
    send_to_comfyui.unregister()
    render_passes.unregister()
    properties.unregister()
    bpy.utils.unregister_class(SoloStudioAddonPreferences)
