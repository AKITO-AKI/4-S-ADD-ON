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

from . import properties
from .operators import render_passes, send_to_comfyui, auto_import
from .panels import main_panel


def register() -> None:
    properties.register()
    render_passes.register()
    send_to_comfyui.register()
    auto_import.register()
    main_panel.register()


def unregister() -> None:
    main_panel.unregister()
    auto_import.unregister()
    send_to_comfyui.unregister()
    render_passes.unregister()
    properties.unregister()
