"""
Phase 4 – VSE 自動インポートオペレーター
=========================================
ComfyUI が生成した動画ファイルを Blender の Video Sequence Editor (VSE) へ
自動的に読み込みます。

処理フロー:
  1. ComfyUI の /history/<prompt_id> から出力ファイルパスを取得
  2. ComfyUI サーバーの output/ ディレクトリから動画ファイルを特定
  3. VSE シーケンスとして指定チャンネルへ追加
"""

from __future__ import annotations

import os

import bpy
from bpy.props import StringProperty
from bpy.types import Operator, Context

from ..utils.comfyui_api import get_history


class SOLOSTUDIO_OT_AutoImportVSE(Operator):
    """生成された動画を VSE へ自動インポートする"""

    bl_idname = "solo_studio.auto_import_vse"
    bl_label = "VSE へ動画をインポート"
    bl_description = "ComfyUI が生成した動画を VSE チャンネルへ読み込みます"
    bl_options = {"REGISTER", "UNDO"}

    # 動画ファイル名（パスまたはファイル名のみ）
    output_filename: StringProperty(
        name="出力ファイル名",
        description="インポートする動画ファイルのパスまたはファイル名",
        default="",
    )

    def execute(self, context: Context) -> set[str]:
        props = context.scene.solo_studio

        filepath = self._resolve_filepath(props)
        if not filepath:
            self.report(
                {"ERROR"},
                "インポートする動画ファイルが見つかりません。",
            )
            return {"CANCELLED"}

        if not os.path.isfile(filepath):
            self.report(
                {"ERROR"},
                f"ファイルが存在しません: {filepath}",
            )
            return {"CANCELLED"}

        # --- VSE シーンを準備 ---
        vse_scene = self._get_or_create_vse_scene(context)
        if vse_scene is None:
            self.report({"ERROR"}, "VSE シーンの取得に失敗しました。")
            return {"CANCELLED"}

        # --- シーケンスを追加 ---
        channel = props.vse_channel
        frame_start = vse_scene.frame_start

        try:
            vse_scene.sequence_editor_create()
            sequences = vse_scene.sequence_editor.sequences
            sequences.new_movie(
                name=os.path.basename(filepath),
                filepath=filepath,
                channel=channel,
                frame_start=frame_start,
            )
            self.report(
                {"INFO"},
                f"VSE チャンネル {channel} へ動画をインポートしました: {filepath}",
            )
        except Exception as exc:
            self.report(
                {"ERROR"},
                f"VSE インポートエラー: {exc}",
            )
            return {"CANCELLED"}

        return {"FINISHED"}

    # ------------------------------------------------------------------
    # ファイルパス解決
    # ------------------------------------------------------------------

    def _resolve_filepath(self, props: object) -> str:
        """
        動画ファイルの絶対パスを決定する。
        1. output_filename が指定されていれば優先
        2. prompt_id があれば /history から最新出力を解決
        3. 上記で見つからなければローカル output/ から最新動画を探索
        """
        filename = self.output_filename.strip()
        if not filename:
            filename = self._find_from_prompt_history(props)
        if not filename:
            filename = self._find_latest_output(props)

        if not filename:
            return ""

        if os.path.isabs(filename) and os.path.isfile(filename):
            return filename

        # ComfyUI デフォルト出力フォルダを推定（ComfyUI と同一マシン前提）
        # Windows: C:/Users/<User>/ComfyUI/output/
        # Linux/Mac: ~/ComfyUI/output/
        candidates = [
            os.path.join(os.path.expanduser("~"), "ComfyUI", "output", filename),
            os.path.join(os.path.expanduser("~"), "comfyui", "output", filename),
            os.path.join("C:\\", "ComfyUI", "output", filename),
            os.path.join("/", "ComfyUI", "output", filename),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path

        return ""

    def _find_from_prompt_history(self, props: object) -> str:
        """
        直近の prompt_id の /history から出力ファイルを解決する。
        """
        prompt_id = str(getattr(props, "prompt_id", "")).strip()
        if not prompt_id:
            return ""

        host = str(getattr(props, "comfyui_host", "")).strip()
        port = int(getattr(props, "comfyui_port", 8188))
        if not host:
            return ""

        try:
            history = get_history(host, port, prompt_id)
        except Exception:
            return ""

        outputs = history.get(prompt_id, {}).get("outputs", {})
        if not isinstance(outputs, dict):
            return ""

        items: list[dict] = []
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for key in ("videos", "images", "gifs"):
                node_items = node_output.get(key, [])
                if isinstance(node_items, list):
                    for item in node_items:
                        if isinstance(item, dict):
                            items.append(item)

        for item in reversed(items):
            resolved = self._resolve_history_item(item)
            if resolved:
                return resolved

        return ""

    def _resolve_history_item(self, item: dict) -> str:
        """
        /history レスポンスの 1 アイテムから実在ファイルを解決する。
        """
        filename = str(item.get("filename", "")).strip()
        if not filename:
            return ""

        if os.path.isabs(filename) and os.path.isfile(filename):
            return filename

        subfolder = str(item.get("subfolder", "")).strip()
        output_type = str(item.get("type", "output")).strip().lower()
        dir_name = {"input": "input", "temp": "temp"}.get(output_type, "output")

        base_dirs = [
            os.path.join(os.path.expanduser("~"), "ComfyUI"),
            os.path.join(os.path.expanduser("~"), "comfyui"),
            os.path.join("C:\\", "ComfyUI"),
            os.path.join("/", "ComfyUI"),
        ]

        for base in base_dirs:
            path = os.path.join(base, dir_name)
            if subfolder:
                path = os.path.join(path, subfolder)
            path = os.path.join(path, filename)
            if os.path.isfile(path):
                return path

        return ""

    def _find_latest_output(self, props: object) -> str:
        """
        ComfyUI output/ フォルダ内で最も新しい動画ファイルを探す。
        """
        output_dirs = [
            os.path.join(os.path.expanduser("~"), "ComfyUI", "output"),
            os.path.join(os.path.expanduser("~"), "comfyui", "output"),
        ]
        video_extensions = {".mp4", ".webm", ".gif", ".mov", ".avi"}

        latest_file = ""
        latest_mtime = 0.0

        for output_dir in output_dirs:
            if not os.path.isdir(output_dir):
                continue
            for fname in os.listdir(output_dir):
                if os.path.splitext(fname)[1].lower() not in video_extensions:
                    continue
                fpath = os.path.join(output_dir, fname)
                mtime = os.path.getmtime(fpath)
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_file = fpath

        return latest_file

    # ------------------------------------------------------------------
    # VSE シーン取得 / 作成
    # ------------------------------------------------------------------

    def _get_or_create_vse_scene(
        self, context: Context
    ) -> bpy.types.Scene | None:
        """
        現在のシーン、またはシーン名に "VSE" を含むシーンを返す。
        存在しない場合は新規シーンを作成します。
        """
        scene = getattr(context, "scene", None)
        if scene is not None:
            return scene

        scenes = getattr(getattr(bpy, "data", None), "scenes", None)
        if scenes is None:
            return None

        for s in scenes:
            if "VSE" in getattr(s, "name", "").upper():
                return s

        try:
            return scenes.new("VSE")
        except Exception:
            return None


# ---------------------------------------------------------------------------
# 手動インポートオペレーター（ファイルブラウザから選択）
# ---------------------------------------------------------------------------

class SOLOSTUDIO_OT_ManualImportVSE(Operator):
    """ファイルブラウザで選択した動画を VSE へインポートする"""

    bl_idname = "solo_studio.manual_import_vse"
    bl_label = "動画を VSE へインポート"
    bl_description = "ファイルブラウザで動画を選択して VSE へ追加します"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_glob: StringProperty(
        default="*.mp4;*.webm;*.mov;*.gif;*.avi",
        options={"HIDDEN"},
    )

    def invoke(self, context: Context, event: bpy.types.Event) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context: Context) -> set[str]:
        props = context.scene.solo_studio

        if not os.path.isfile(self.filepath):
            self.report({"ERROR"}, f"ファイルが存在しません: {self.filepath}")
            return {"CANCELLED"}

        channel = props.vse_channel
        scene = context.scene
        scene.sequence_editor_create()

        try:
            scene.sequence_editor.sequences.new_movie(
                name=os.path.basename(self.filepath),
                filepath=self.filepath,
                channel=channel,
                frame_start=scene.frame_start,
            )
            self.report(
                {"INFO"},
                f"VSE チャンネル {channel} へインポートしました: {self.filepath}",
            )
        except Exception as exc:
            self.report({"ERROR"}, f"VSE インポートエラー: {exc}")
            return {"CANCELLED"}

        return {"FINISHED"}


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------

def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_OT_AutoImportVSE)
    bpy.utils.register_class(SOLOSTUDIO_OT_ManualImportVSE)


def unregister() -> None:
    bpy.utils.unregister_class(SOLOSTUDIO_OT_ManualImportVSE)
    bpy.utils.unregister_class(SOLOSTUDIO_OT_AutoImportVSE)
