"""
Panels for 4'S Add-on
"""

from __future__ import annotations

import bpy
from bpy.types import Panel, Context


class FOURS_PT_MainPanel(Panel):
    bl_idname = "FOURS_PT_main_panel"
    bl_label = "4'S"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "4'S"

    def draw(self, context: Context) -> None:
        layout = self.layout
        props = context.scene.four_s

        layout.prop(props, "prompt", text="プロンプト")
        layout.prop(props, "style_strength", text="スタイル強度", slider=True)
        layout.prop(props, "lora", text="LoRA")

        layout.separator()
        row = layout.row()
        row.enabled = not props.is_running
        row.operator("four_s.generate", text="生成開始", icon="PLAY")

        layout.separator()
        layout.label(text=f"ステータス: {props.status_message}", icon="INFO")


def register() -> None:
    bpy.utils.register_class(FOURS_PT_MainPanel)


def unregister() -> None:
    bpy.utils.unregister_class(FOURS_PT_MainPanel)
