"""
Phase 4 – バッチ処理オペレーター
===================================
フレームシーケンスの生成と VSE（動画シーケンスエディタ）への構成を
完全自動化するバッチ処理モジュール。

処理フロー (フレームごとに繰り返し):
  1. 指定フレームへ移動
  2. 深度マップ（Mist パス）をレンダリングして保存
  3. ComfyUI へアップロードし、単フレーム画像を生成
  4. 生成完了した画像を VSE の対応タイムライン位置へ自動配置
  5. 全フレーム完了後に MP4 (H.264) エクスポート設定を自動構成
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

import bpy
from bpy.types import Operator, Context

from ..utils.comfyui_api import queue_prompt, upload_image
from ..utils.workflow_builder import build_workflow, params_from_scene_props
from ..utils.async_handler import AsyncGenerationHandler


# ---------------------------------------------------------------------------
# VSE MP4 エクスポート設定
# ---------------------------------------------------------------------------

def configure_vse_mp4_export(
    scene: bpy.types.Scene,
    output_path: str = "//output.mp4",
) -> None:
    """
    VSE から MP4 (H.264) 形式で動画を書き出すためのレンダリング設定を構成する。

    Parameters
    ----------
    scene : bpy.types.Scene
        設定を適用する Blender シーン
    output_path : str
        出力ファイルパス（Blender 相対パス可）
    """
    render = scene.render
    render.image_settings.file_format = "FFMPEG"
    render.ffmpeg.format = "MPEG4"
    render.ffmpeg.codec = "H264"
    render.ffmpeg.constant_rate_factor = "MEDIUM"
    render.ffmpeg.ffmpeg_preset = "GOOD"
    render.ffmpeg.audio_codec = "AAC"
    render.filepath = output_path


# ---------------------------------------------------------------------------
# バッチ処理状態管理
# ---------------------------------------------------------------------------

class _BatchContext:
    """
    バッチ処理の進行状態を保持するコンテキストオブジェクト。

    状態遷移:
        render_depth → wait_comfyui → import_to_vse → (次フレームへ) → done
    """

    def __init__(
        self,
        frame_start: int,
        frame_end: int,
        output_dir: str,
        vse_channel: int,
        props: object,
    ) -> None:
        self.frame_start = frame_start
        self.frame_end = frame_end
        self.current_frame = frame_start
        self.output_dir = output_dir
        self.vse_channel = vse_channel
        self.props = props

        # 生成済み画像テーブル: フレーム番号 → 画像ファイルの絶対パス
        self.generated_images: dict[int, str] = {}

        # 現在フレームの非同期ハンドラー
        self.handler: Optional[AsyncGenerationHandler] = None

        # ハンドラーが完了したことをタイマースレッドへ伝えるフラグ
        self.handler_done: bool = False
        self.handler_files: list[str] = []
        self.handler_error: str = ""

        # 状態機械の現在状態
        self.state: str = "render_depth"

        # 現在フレームの深度マップパス（ComfyUI アップロード用）
        self._depth_path: str = ""

    @property
    def total_frames(self) -> int:
        return self.frame_end - self.frame_start + 1

    @property
    def completed_frames(self) -> int:
        return self.current_frame - self.frame_start

    @property
    def progress(self) -> float:
        total = self.total_frames
        if total <= 0:
            return 1.0
        return self.completed_frames / total


# ---------------------------------------------------------------------------
# モジュールレベルのシングルトン
# ---------------------------------------------------------------------------

_active_batch: _BatchContext | None = None
_TIMER_INTERVAL: float = 0.5


# ---------------------------------------------------------------------------
# タイマーコールバック（メインスレッド）
# ---------------------------------------------------------------------------

def _batch_timer_callback() -> Optional[float]:
    """
    bpy.app.timers に登録されるバッチ処理タイマー。
    None を返すとタイマーが停止する。
    """
    global _active_batch

    if _active_batch is None:
        return None

    ctx = _active_batch
    props = ctx.props

    if ctx.state == "render_depth":
        _do_render_depth(ctx)
        # _do_render_depth 内で状態を wait_comfyui か error に遷移させる
        return _TIMER_INTERVAL

    elif ctx.state == "wait_comfyui":
        if ctx.handler_error:
            props.batch_status = (
                f"エラー (フレーム {ctx.current_frame}): {ctx.handler_error}"
            )
            _active_batch = None
            return None
        elif ctx.handler_done:
            _do_handle_comfyui_result(ctx)
            return _TIMER_INTERVAL
        else:
            # 生成完了待ち
            return _TIMER_INTERVAL

    elif ctx.state == "import_to_vse":
        _do_import_to_vse(ctx)
        ctx.current_frame += 1
        if ctx.current_frame > ctx.frame_end:
            ctx.state = "done"
        else:
            ctx.state = "render_depth"
        return _TIMER_INTERVAL

    elif ctx.state == "done":
        props.batch_status = "バッチ処理完了"
        props.batch_progress = 1.0
        _configure_export_on_complete(ctx)
        _active_batch = None
        return None

    elif ctx.state == "error":
        _active_batch = None
        return None

    return _TIMER_INTERVAL


# ---------------------------------------------------------------------------
# 状態ハンドラー
# ---------------------------------------------------------------------------

def _do_render_depth(ctx: _BatchContext) -> None:
    """
    現在フレームの深度マップ（Mist パス）を PNG でレンダリングして保存し、
    その画像を ComfyUI へ送信して非同期生成を開始する。
    """
    props = ctx.props
    frame = ctx.current_frame

    props.batch_status = (
        f"フレーム {frame}/{ctx.frame_end}: 深度マップをレンダリング中..."
    )
    props.batch_progress = ctx.progress

    scene = bpy.context.scene
    scene.frame_set(frame)

    depth_dir = os.path.join(ctx.output_dir, "depth")
    os.makedirs(depth_dir, exist_ok=True)
    depth_path = os.path.join(depth_dir, f"frame_{frame:04d}.png")

    # --- レンダリング設定を退避 ---
    orig_engine = scene.render.engine
    orig_use_nodes = scene.use_nodes
    orig_filepath = scene.render.filepath
    orig_file_format = scene.render.image_settings.file_format
    orig_color_mode = scene.render.image_settings.color_mode
    orig_use_file_ext = scene.render.use_file_extension

    try:
        # Depth (Mist) パス用コンポジターノードを設定
        scene.render.engine = "CYCLES"
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()

        rl = tree.nodes.new("CompositorNodeRLayers")
        rl.location = (-300, 0)

        normalize = tree.nodes.new("CompositorNodeNormalize")
        normalize.location = (0, 0)

        composite = tree.nodes.new("CompositorNodeComposite")
        composite.location = (300, 0)

        scene.view_layers["ViewLayer"].use_pass_mist = True

        tree.links.new(rl.outputs["Mist"], normalize.inputs[0])
        tree.links.new(normalize.outputs[0], composite.inputs["Image"])

        # 出力先を設定して単一フレームをレンダリング
        scene.render.filepath = depth_path
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "BW"
        scene.render.use_file_extension = False

        bpy.ops.render.render(write_still=True)

    finally:
        # レンダリング設定を復元
        scene.render.engine = orig_engine
        scene.use_nodes = orig_use_nodes
        scene.render.filepath = orig_filepath
        scene.render.image_settings.file_format = orig_file_format
        scene.render.image_settings.color_mode = orig_color_mode
        scene.render.use_file_extension = orig_use_file_ext

    ctx._depth_path = depth_path
    _do_send_to_comfyui(ctx, depth_path, frame)


def _do_send_to_comfyui(ctx: _BatchContext, depth_path: str, frame: int) -> None:
    """
    深度マップを ComfyUI へアップロードし、単フレーム画像生成ジョブを投入する。
    """
    props = ctx.props

    # 深度マップをアップロード
    depth_filename = f"depth_frame_{frame:04d}.png"
    try:
        result = upload_image(
            props.comfyui_host,
            props.comfyui_port,
            depth_path,
            overwrite=True,
        )
        depth_filename = result.get("name", depth_filename)
    except Exception as exc:
        ctx.handler_error = f"深度マップのアップロードに失敗しました: {exc}"
        ctx.state = "error"
        props.batch_status = f"エラー: {ctx.handler_error}"
        return

    # フレームごとにシードをオフセットして多様性を確保
    wf_params = params_from_scene_props(props)
    wf_params.depth_image = depth_filename
    wf_params.frame_count = 1  # 単フレーム生成
    if wf_params.seed >= 0:
        wf_params.seed = wf_params.seed + frame
    workflow = build_workflow(wf_params)

    # ComfyUI へ送信
    client_id = str(uuid.uuid4())
    try:
        response = queue_prompt(
            props.comfyui_host,
            props.comfyui_port,
            workflow,
            client_id,
        )
    except Exception as exc:
        ctx.handler_error = f"ComfyUI への送信に失敗しました: {exc}"
        ctx.state = "error"
        props.batch_status = f"エラー: {ctx.handler_error}"
        return

    prompt_id = response.get("prompt_id", "")

    # フラグをリセットしてハンドラーを起動
    ctx.handler_done = False
    ctx.handler_files = []
    ctx.handler_error = ""

    def on_complete(files: list[str]) -> None:
        ctx.handler_done = True
        ctx.handler_files = files
        ctx.handler = None

    def on_error(msg: str) -> None:
        ctx.handler_error = msg
        ctx.handler = None

    ctx.handler = AsyncGenerationHandler(
        props,
        on_complete=on_complete,
        on_error=on_error,
    )
    ctx.handler.start(props.comfyui_host, props.comfyui_port, prompt_id, client_id)

    ctx.state = "wait_comfyui"
    props.batch_status = (
        f"フレーム {frame}/{ctx.frame_end}: ComfyUI 生成中..."
    )


def _do_handle_comfyui_result(ctx: _BatchContext) -> None:
    """
    ComfyUI 生成完了後に出力ファイルパスを解決し、
    import_to_vse 状態へ遷移する。
    """
    frame = ctx.current_frame
    files = ctx.handler_files

    if files:
        image_path = _resolve_comfyui_output(files[0])
        if image_path:
            ctx.generated_images[frame] = image_path

    ctx.state = "import_to_vse"


def _resolve_comfyui_output(filename: str) -> str:
    """
    ComfyUI output フォルダ内のファイルを絶対パスへ解決する。
    """
    if os.path.isabs(filename) and os.path.isfile(filename):
        return filename

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


def _do_import_to_vse(ctx: _BatchContext) -> None:
    """
    生成済み画像を VSE のタイムライン上の対応フレーム位置へ静止画ストリップとして配置する。

    使用 API: bpy.context.scene.sequence_editor
    """
    frame = ctx.current_frame

    image_path = ctx.generated_images.get(frame, "")
    if not image_path or not os.path.isfile(image_path):
        print(
            f"[SoloStudio] VSE インポートスキップ "
            f"(フレーム {frame}): ファイルが見つかりません: {image_path!r}"
        )
        return

    scene = bpy.context.scene
    scene.sequence_editor_create()
    sequences = scene.sequence_editor.sequences

    try:
        strip = sequences.new_image(
            name=f"gen_frame_{frame:04d}",
            filepath=image_path,
            channel=ctx.vse_channel,
            frame_start=frame,
            fit_method="FIT",
        )
        # 1 フレーム分の静止画ストリップとして配置
        strip.frame_final_duration = 1
    except Exception as exc:
        print(f"[SoloStudio] VSE インポートエラー (フレーム {frame}): {exc}")
        return

    props = ctx.props
    props.batch_progress = (frame - ctx.frame_start + 1) / ctx.total_frames
    props.batch_status = (
        f"フレーム {frame}/{ctx.frame_end}: VSE へインポートしました"
    )


def _configure_export_on_complete(ctx: _BatchContext) -> None:
    """
    バッチ完了後に VSE の MP4 (H.264) エクスポート設定を自動構成する。
    """
    scene = bpy.context.scene
    output_path = os.path.join(ctx.output_dir, "output.mp4")
    configure_vse_mp4_export(scene, output_path)
    print(f"[SoloStudio] VSE MP4 エクスポート設定を構成しました: {output_path}")


# ---------------------------------------------------------------------------
# オペレーター
# ---------------------------------------------------------------------------

class SOLOSTUDIO_OT_BatchProcess(Operator):
    """フレームシーケンスのバッチ処理（深度抽出 → ComfyUI 生成 → VSE 配置）を開始する"""

    bl_idname = "solo_studio.batch_process"
    bl_label = "バッチ処理開始"
    bl_description = (
        "指定フレーム範囲に対して「深度マップ抽出→ComfyUI 生成→VSE 自動配置」を"
        "フレームごとに連鎖実行します"
    )
    bl_options = {"REGISTER"}

    def execute(self, context: Context) -> set[str]:
        global _active_batch

        if _active_batch is not None:
            self.report({"WARNING"}, "すでにバッチ処理中です。完了をお待ちください。")
            return {"CANCELLED"}

        props = context.scene.solo_studio
        frame_start = props.batch_frame_start
        frame_end = props.batch_frame_end

        if frame_start > frame_end:
            self.report(
                {"ERROR"},
                "開始フレームは終了フレーム以下に設定してください。",
            )
            return {"CANCELLED"}

        out_dir = bpy.path.abspath(props.batch_output_dir)
        os.makedirs(out_dir, exist_ok=True)

        _active_batch = _BatchContext(
            frame_start=frame_start,
            frame_end=frame_end,
            output_dir=out_dir,
            vse_channel=props.vse_channel,
            props=props,
        )

        props.batch_status = "バッチ処理開始..."
        props.batch_progress = 0.0

        if not bpy.app.timers.is_registered(_batch_timer_callback):
            bpy.app.timers.register(
                _batch_timer_callback,
                first_interval=0.1,
                persistent=False,
            )

        self.report(
            {"INFO"},
            f"バッチ処理を開始しました: フレーム {frame_start} → {frame_end}",
        )
        return {"FINISHED"}


class SOLOSTUDIO_OT_CancelBatch(Operator):
    """実行中のバッチ処理をキャンセルする"""

    bl_idname = "solo_studio.cancel_batch"
    bl_label = "バッチ処理をキャンセル"
    bl_description = "実行中のバッチ処理を停止します"
    bl_options = {"REGISTER"}

    def execute(self, context: Context) -> set[str]:
        global _active_batch

        if _active_batch is None:
            self.report({"INFO"}, "バッチ処理は実行されていません。")
            return {"CANCELLED"}

        if _active_batch.handler is not None:
            _active_batch.handler.stop()
        _active_batch = None

        props = context.scene.solo_studio
        props.batch_status = "キャンセルされました"
        props.batch_progress = 0.0

        self.report({"INFO"}, "バッチ処理をキャンセルしました。")
        return {"FINISHED"}


class SOLOSTUDIO_OT_ConfigureVSEExport(Operator):
    """VSE の MP4 (H.264) エクスポート設定を構成する"""

    bl_idname = "solo_studio.configure_vse_export"
    bl_label = "VSE MP4 エクスポートを設定"
    bl_description = (
        "VSE から MP4 (H.264) 形式で動画を書き出すための"
        "レンダリング設定を構成します"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: Context) -> set[str]:
        props = context.scene.solo_studio
        out_dir = bpy.path.abspath(props.batch_output_dir)
        output_path = os.path.join(out_dir, "output.mp4")
        configure_vse_mp4_export(context.scene, output_path)
        self.report(
            {"INFO"},
            f"VSE MP4 エクスポート設定を構成しました: {output_path}",
        )
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# 登録
# ---------------------------------------------------------------------------

def register() -> None:
    bpy.utils.register_class(SOLOSTUDIO_OT_BatchProcess)
    bpy.utils.register_class(SOLOSTUDIO_OT_CancelBatch)
    bpy.utils.register_class(SOLOSTUDIO_OT_ConfigureVSEExport)


def unregister() -> None:
    global _active_batch
    if _active_batch is not None:
        if _active_batch.handler is not None:
            _active_batch.handler.stop()
        _active_batch = None
    if bpy.app.timers.is_registered(_batch_timer_callback):
        bpy.app.timers.unregister(_batch_timer_callback)
    bpy.utils.unregister_class(SOLOSTUDIO_OT_ConfigureVSEExport)
    bpy.utils.unregister_class(SOLOSTUDIO_OT_CancelBatch)
    bpy.utils.unregister_class(SOLOSTUDIO_OT_BatchProcess)
