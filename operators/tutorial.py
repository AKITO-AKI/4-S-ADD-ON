"""
SoloStudio Director – セットアップガイド（チュートリアル）
===========================================================
初回起動時に自動表示するオンボーディングダイアログと、
「ヘルプ / ガイド」パネルからいつでも再表示できるオペレーターを提供します。

ダイアログはスクロール可能な 1 ページに全ステップをまとめて表示し、
「OK」を押すと完了状態をアドオンプリファレンスに保存します。
"""

from __future__ import annotations

import bpy
from bpy.types import Operator, Context

# このファイルは solo_studio_director.operators パッケージ内にあるため、
# __package__ は "solo_studio_director.operators" になる。
# AddonPreferences へのアクセスにはトップレベルのパッケージ名が必要。
_ADDON_PKG = __package__.rsplit(".", 1)[0] if "." in __package__ else __package__

# ---------------------------------------------------------------------------
# チュートリアル内容定義
# ---------------------------------------------------------------------------

_STEPS = [
    {
        "label": "① ComfyUI を起動する",
        "icon": "PLAY",
        "lines": [
            "ComfyUI をローカルで起動してください。",
            "デフォルト URL: http://127.0.0.1:8188",
            "「ComfyUI 接続設定」パネルでホスト / ポートを確認してください。",
        ],
        "warning": "ComfyUI が起動していないと「ComfyUI へ送信」が失敗します。",
        "tip": None,
    },
    {
        "label": "② キャラクター参照画像を設定する（推奨）",
        "icon": "IMAGE_DATA",
        "lines": [
            "「キャラクター設定」パネルで char_ref.png を指定します。",
            "IP-Adapter がこの画像を参照してキャラクター外見を維持します。",
            "省略可ですが、設定することで再現性が大幅に向上します。",
        ],
        "warning": None,
        "tip": None,
    },
    {
        "label": "③ レンダリングパスを出力する",
        "icon": "RENDERLAYERS",
        "lines": [
            "「レンダリングパス設定」で出力先フォルダを指定します。",
            "「マルチパスレンダリング」ボタンを押すと",
            "Depth / Lineart / Normal / Mask / BaseColor が自動生成されます。",
        ],
        "warning": None,
        "tip": None,
    },
    {
        "label": "④ プロンプトを設定して AI 生成を開始する",
        "icon": "FUND",
        "lines": [
            "「AI 生成設定」でポジティブ / ネガティブプロンプトを入力します。",
            "「実行 / 進捗」パネルの「▶ ComfyUI へ送信」を押して生成を開始します。",
            "完了後はポストプロセスパネルで VSE に動画をインポートできます。",
        ],
        "warning": None,
        "tip": "N パネルの「ヘルプ / ガイド」からいつでもこのガイドを再表示できます。",
    },
]


# ---------------------------------------------------------------------------
# オペレーター
# ---------------------------------------------------------------------------

class SOLOSTUDIO_OT_OpenTutorial(Operator):
    """SoloStudio Director のセットアップガイドを表示する"""

    bl_idname = "solo_studio.open_tutorial"
    bl_label = "セットアップガイド"
    bl_description = "SoloStudio Director の初期設定手順をステップごとに案内します"
    bl_options = {"REGISTER"}

    def invoke(self, context: Context, event) -> set[str]:
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context: Context) -> None:
        layout = self.layout

        # ヘッダー
        header = layout.box()
        header.label(
            text="SoloStudio Director  –  はじめかたガイド",
            icon="FUND",
        )

        layout.separator(factor=0.5)

        for step in _STEPS:
            box = layout.box()
            col = box.column(align=True)

            # ステップタイトル
            col.label(text=step["label"], icon=step["icon"])
            col.separator(factor=0.3)

            for line in step["lines"]:
                sub = col.row()
                sub.label(text=line)

            if step["warning"]:
                col.separator(factor=0.3)
                warn_row = col.row()
                warn_row.alert = True
                warn_row.label(text=step["warning"], icon="ERROR")

            if step["tip"]:
                col.separator(factor=0.3)
                col.label(text=step["tip"], icon="LIGHT")

        layout.separator(factor=0.5)
        layout.label(
            text="「OK」を押すとガイド完了としてマークします。ヘルプパネルから再表示できます。",
            icon="INFO",
        )

    def execute(self, context: Context) -> set[str]:
        addon_entry = context.preferences.addons.get(_ADDON_PKG)
        if addon_entry is not None:
            addon_entry.preferences.tutorial_completed = True
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------

def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_OT_OpenTutorial)


def unregister() -> None:
    bpy.utils.unregister_class(SOLOSTUDIO_OT_OpenTutorial)
