"""
4'S Add-on Skeleton (Blender 4.x)
=================================
"""

from __future__ import annotations

import bpy
from bpy.props import (
    StringProperty,
    FloatProperty,
    EnumProperty,
    BoolProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

from . import operators, panels

bl_info = {
    "name": "4'S Add-on Skeleton",
    "author": "AKITO-AKI",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > 4'S",
    "description": "4'S panel with ComfyUI WebSocket async skeleton",
    "category": "Animation",
}


class FourSProperties(PropertyGroup):
    generation_prompt: StringProperty(
        name="プロンプト",
        description="生成プロンプト",
        default="",
    )
    style_strength: FloatProperty(
        name="スタイル強度",
        description="スタイル強度",
        default=0.7,
        min=0.0,
        max=1.0,
    )
    lora: EnumProperty(
        name="LoRA",
        description="LoRA を選択",
        items=[
            ("none", "なし", "LoRA を使用しない"),
            ("lineart", "Lineart", "Lineart LoRA"),
            ("anime", "Anime", "Anime LoRA"),
        ],
        default="none",
    )
    status_message: StringProperty(
        name="ステータス",
        description="通信ステータス",
        default="待機中",
    )
    is_running: BoolProperty(
        name="実行中",
        description="生成が進行中かどうか",
        default=False,
    )


def register() -> None:
    bpy.utils.register_class(FourSProperties)
    bpy.types.Scene.four_s = PointerProperty(type=FourSProperties)
    operators.register()
    panels.register()


def unregister() -> None:
    panels.unregister()
    operators.unregister()
    del bpy.types.Scene.four_s
    bpy.utils.unregister_class(FourSProperties)
