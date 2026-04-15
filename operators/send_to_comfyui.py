"""
Phase 3 – ComfyUI 送信オペレーター
=====================================
Blender でのすべての設定を JSON 化して ComfyUI のAPIエンドポイントへ
送信し、非同期で生成進捗を監視します。

処理フロー:
  1. char_ref.png を ComfyUI の /upload/image へアップロード
  2. WorkflowParams をシーンプロパティから生成
  3. build_workflow() でワークフロー JSON を構築
  4. /prompt エンドポイントへ POST してジョブキューに追加
  5. AsyncGenerationHandler を起動して WebSocket で進捗監視
  6. 完了時に auto_import オペレーターを呼び出し（オプション）
"""

from __future__ import annotations

import os
import uuid

import bpy
from bpy.types import Operator, Context

from ..utils.comfyui_api import queue_prompt, upload_image
from ..utils.workflow_builder import build_workflow, params_from_scene_props
from ..utils.async_handler import AsyncGenerationHandler


# ---------------------------------------------------------------------------
# グローバルハンドラー（シングルトン）
# ---------------------------------------------------------------------------
# Blender のモーダルオペレーターに変わって非同期処理を受け持つ
_active_handler: AsyncGenerationHandler | None = None


# ---------------------------------------------------------------------------
# オペレーター
# ---------------------------------------------------------------------------

class SOLOSTUDIO_OT_SendToComfyUI(Operator):
    """シーン設定を ComfyUI へ送信し、アニメーション生成を開始する"""

    bl_idname = "solo_studio.send_to_comfyui"
    bl_label = "ComfyUI へ送信"
    bl_description = (
        "現在のシーン設定とレンダリングパスを ComfyUI へ送信して"
        "アニメーション生成を開始します"
    )
    bl_options = {"REGISTER"}

    def execute(self, context: Context) -> set[str]:
        global _active_handler

        props = context.scene.solo_studio
        host = props.comfyui_host
        port = props.comfyui_port

        # --- 進行中の処理があれば警告 ---
        if _active_handler is not None:
            self.report({"WARNING"}, "すでに生成中です。完了をお待ちください。")
            return {"CANCELLED"}

        # --- char_ref.png のアップロード ---
        char_ref_name = "char_ref.png"
        if props.char_ref_path:
            abs_ref = bpy.path.abspath(props.char_ref_path)
            if os.path.isfile(abs_ref):
                try:
                    result = upload_image(host, port, abs_ref, overwrite=True)
                    char_ref_name = result.get("name", char_ref_name)
                    self.report(
                        {"INFO"},
                        f"キャラクター設定画をアップロードしました: {char_ref_name}",
                    )
                except Exception as exc:
                    self.report(
                        {"WARNING"},
                        f"キャラクター設定画のアップロードに失敗しました: {exc}",
                    )
            else:
                self.report(
                    {"WARNING"},
                    f"キャラクター設定画が見つかりません: {abs_ref}",
                )

        # --- ワークフロー構築 ---
        wf_params = params_from_scene_props(props)
        wf_params.char_ref_image = char_ref_name
        workflow = build_workflow(wf_params)

        # --- ComfyUI へ送信 ---
        client_id = str(uuid.uuid4())
        try:
            response = queue_prompt(host, port, workflow, client_id)
        except Exception as exc:
            self.report({"ERROR"}, f"ComfyUI への送信に失敗しました: {exc}")
            props.generation_status = f"送信エラー: {exc}"
            return {"CANCELLED"}

        prompt_id = response.get("prompt_id", "")
        props.prompt_id = prompt_id
        props.generation_progress = 0.0
        props.generation_status = "生成開始..."

        self.report(
            {"INFO"},
            f"ComfyUI へ送信しました (prompt_id: {prompt_id})",
        )

        # --- 非同期ハンドラー起動 ---
        _active_handler = AsyncGenerationHandler(
            props,
            on_complete=self._make_complete_callback(context, props),
            on_error=self._make_error_callback(props),
        )
        _active_handler.start(host, port, prompt_id, client_id)

        return {"FINISHED"}

    # ------------------------------------------------------------------
    # コールバックファクトリー
    # ------------------------------------------------------------------

    def _make_complete_callback(
        self, context: Context, props: object
    ) -> Callable[[list[str]], None]:
        auto_import = props.auto_import_vse

        def on_complete(output_files: list[str]) -> None:
            global _active_handler
            _active_handler = None

            if not output_files:
                return

            if auto_import:
                # VSE 自動インポート
                try:
                    bpy.ops.solo_studio.auto_import_vse(
                        "INVOKE_DEFAULT",
                        output_filename=output_files[0],
                    )
                except Exception as exc:
                    print(f"[SoloStudio] VSE 自動インポートエラー: {exc}")

        return on_complete

    def _make_error_callback(self, props: object) -> Callable[[str], None]:
        def on_error(message: str) -> None:
            global _active_handler
            _active_handler = None
            print(f"[SoloStudio] 生成エラー: {message}")

        return on_error


# ---------------------------------------------------------------------------
# キャンセルオペレーター
# ---------------------------------------------------------------------------

class SOLOSTUDIO_OT_CancelGeneration(Operator):
    """進行中の ComfyUI 生成処理をキャンセルする"""

    bl_idname = "solo_studio.cancel_generation"
    bl_label = "生成をキャンセル"
    bl_description = "進行中の ComfyUI 生成処理を停止します"
    bl_options = {"REGISTER"}

    def execute(self, context: Context) -> set[str]:
        global _active_handler

        if _active_handler is None:
            self.report({"INFO"}, "生成中の処理はありません。")
            return {"CANCELLED"}

        _active_handler.stop()
        _active_handler = None

        props = context.scene.solo_studio
        props.generation_status = "キャンセルされました"
        props.generation_progress = 0.0

        self.report({"INFO"}, "生成をキャンセルしました。")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------

def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_OT_SendToComfyUI)
    bpy.utils.register_class(SOLOSTUDIO_OT_CancelGeneration)


def unregister() -> None:
    bpy.utils.unregister_class(SOLOSTUDIO_OT_CancelGeneration)
    bpy.utils.unregister_class(SOLOSTUDIO_OT_SendToComfyUI)
