"""
SoloStudio Director – Scene Properties
=======================================
Blenderシーンに付加するアドオン専用プロパティ群。
Nパネルで直接編集可能なすべての設定値を一か所で定義します。
"""

import bpy
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


class SoloStudioProperties(PropertyGroup):
    # ------------------------------------------------------------------
    # Phase 2: マルチパス書き出し設定
    # ------------------------------------------------------------------
    output_dir: StringProperty(
        name="出力ディレクトリ",
        description="レンダリングパス素材の保存先フォルダ",
        default="//solo_studio_passes/",
        subtype="DIR_PATH",
    )
    render_depth: BoolProperty(
        name="Depth",
        description="Depthパスをレンダリングする",
        default=True,
    )
    render_lineart: BoolProperty(
        name="Lineart",
        description="Lineartパスをレンダリングする",
        default=True,
    )
    render_normal: BoolProperty(
        name="Normal Map",
        description="法線マップパスをレンダリングする（カメラワーク対策）",
        default=True,
    )
    render_mask: BoolProperty(
        name="Character Mask",
        description="キャラクターマスクをレンダリングする（IP-Adapter影響範囲限定）",
        default=True,
    )
    render_base_color: BoolProperty(
        name="Base Color",
        description="Workbench Base Color パスをレンダリングする",
        default=True,
    )
    depth_near: FloatProperty(
        name="Depth Near (m)",
        description="Depth正規化の近クリップ距離（カメラからの距離）",
        default=2.0,
        min=0.01,
        max=10000.0,
    )
    depth_far: FloatProperty(
        name="Depth Far (m)",
        description="Depth正規化の遠クリップ距離（カメラからの距離）",
        default=10.0,
        min=0.02,
        max=10000.0,
    )
    lineart_ref_distance: FloatProperty(
        name="Lineart基準距離 (m)",
        description="Lineart太さを維持する基準カメラ距離",
        default=5.0,
        min=0.01,
        max=10000.0,
    )
    lineart_base_thickness: FloatProperty(
        name="Lineart基準太さ",
        description="基準距離でのLineart太さ（Freestyle）",
        default=1.0,
        min=0.01,
        max=100.0,
    )
    lineart_min_thickness: FloatProperty(
        name="Lineart最小太さ",
        description="Lineart動的補正の最小値",
        default=0.5,
        min=0.01,
        max=100.0,
    )
    lineart_max_thickness: FloatProperty(
        name="Lineart最大太さ",
        description="Lineart動的補正の最大値",
        default=3.0,
        min=0.01,
        max=100.0,
    )
    lineart_aa_filter_size: FloatProperty(
        name="Lineart AA",
        description="Lineartのアンチエイリアス強度（Filter Size）",
        default=1.5,
        min=0.01,
        max=10.0,
    )
    normal_color_depth: EnumProperty(
        name="Normal深度",
        description="Normalマップの色深度",
        items=[
            ("8", "8-bit", "容量を抑えた通常品質"),
            ("16", "16-bit", "高精度（法線情報の劣化を抑制）"),
        ],
        default="16",
    )

    # ------------------------------------------------------------------
    # Phase 2: ユーザーリファレンス管理
    # ------------------------------------------------------------------
    char_ref_path: StringProperty(
        name="キャラクター設定画",
        description="IP-Adapter に使用するキャラクター参照画像 (char_ref.png)",
        default="",
        subtype="FILE_PATH",
    )

    # ------------------------------------------------------------------
    # Phase 3: ComfyUI 接続設定
    # ------------------------------------------------------------------
    comfyui_host: StringProperty(
        name="ComfyUI ホスト",
        description="ComfyUI サーバーのホスト名または IP アドレス",
        default="127.0.0.1",
    )
    comfyui_port: IntProperty(
        name="ComfyUI ポート",
        description="ComfyUI サーバーのポート番号",
        default=8188,
        min=1,
        max=65535,
    )

    # ------------------------------------------------------------------
    # Phase 1: AI 生成パラメータ（ユーザー向け演出コントロール）
    # ------------------------------------------------------------------
    positive_prompt: StringProperty(
        name="ポジティブプロンプト",
        description="生成する映像の内容を説明するプロンプト",
        default="anime style, high quality, detailed character",
    )
    negative_prompt: StringProperty(
        name="ネガティブプロンプト",
        description="生成から除外したい要素を指定するプロンプト",
        default="lowres, bad anatomy, worst quality, blurry",
    )
    cfg_scale: FloatProperty(
        name="CFG スケール",
        description="プロンプトへの従順度（高いほど忠実、低いほど自由）",
        default=7.0,
        min=1.0,
        max=20.0,
        step=0.5,
    )
    steps: IntProperty(
        name="ステップ数",
        description="デノイズのステップ数（多いほど高品質だが遅い）",
        default=20,
        min=1,
        max=100,
    )
    seed: IntProperty(
        name="シード値",
        description="乱数シード（-1 でランダム）",
        default=-1,
        min=-1,
    )
    controlnet_start_percent: FloatProperty(
        name="ControlNet開始",
        description="ControlNet適用の開始割合",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    controlnet_end_percent: FloatProperty(
        name="ControlNet終了",
        description="ControlNet適用の終了割合（焼き込み防止）",
        default=0.8,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    use_ip_adapter_mask: BoolProperty(
        name="IP-Adapterマスク適用",
        description="キャラクターマスク領域にのみIP-Adapterを適用する",
        default=True,
    )
    use_freeu: BoolProperty(
        name="FreeU有効化",
        description="低周波安定化のためFreeUノードを使用する",
        default=True,
    )
    freeu_b1: FloatProperty(name="FreeU b1", default=1.1, min=0.0, max=3.0)
    freeu_b2: FloatProperty(name="FreeU b2", default=1.2, min=0.0, max=3.0)
    freeu_s1: FloatProperty(name="FreeU s1", default=0.6, min=0.0, max=3.0)
    freeu_s2: FloatProperty(name="FreeU s2", default=0.4, min=0.0, max=3.0)

    # ------------------------------------------------------------------
    # Phase 1: AnimateDiff – Sliding Window Context
    # ------------------------------------------------------------------
    context_length: IntProperty(
        name="コンテキスト長",
        description="AnimateDiff Sliding Window のコンテキスト長（フレーム数）",
        default=16,
        min=8,
        max=32,
    )
    context_overlap: IntProperty(
        name="コンテキスト重複",
        description="Sliding Window のフレーム重複数",
        default=4,
        min=1,
        max=16,
    )
    auto_context_overlap: BoolProperty(
        name="重複を自動調整",
        description="カメラ移動量に応じて Context Overlap を自動補正する",
        default=True,
    )
    camera_velocity_threshold: FloatProperty(
        name="速度しきい値",
        description="この値以上のカメラ移動量で重複を増やす",
        default=0.1,
        min=0.0,
        max=100.0,
    )
    context_overlap_high_motion: IntProperty(
        name="高速時重複",
        description="高移動時に使用する Context Overlap 値",
        default=8,
        min=1,
        max=32,
    )

    # ------------------------------------------------------------------
    # Phase 3: 非同期処理 / 進捗
    # ------------------------------------------------------------------
    generation_status: StringProperty(
        name="ステータス",
        description="現在の生成状態",
        default="待機中",
    )
    generation_progress: FloatProperty(
        name="進捗率",
        description="生成進捗（0.0 〜 1.0）",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )
    prompt_id: StringProperty(
        name="プロンプト ID",
        description="ComfyUI から返却された実行中ジョブの ID",
        default="",
    )

    # ------------------------------------------------------------------
    # Phase 4: VSE 自動インポート設定
    # ------------------------------------------------------------------
    auto_import_vse: BoolProperty(
        name="VSE へ自動インポート",
        description="生成完了時に動画を自動的に VSE へ読み込む",
        default=True,
    )
    vse_channel: IntProperty(
        name="VSE チャンネル",
        description="自動インポート先の VSE チャンネル番号",
        default=1,
        min=1,
        max=32,
    )


def register() -> None:
    bpy.utils.register_class(SoloStudioProperties)
    bpy.types.Scene.solo_studio = PointerProperty(type=SoloStudioProperties)


def unregister() -> None:
    del bpy.types.Scene.solo_studio
    bpy.utils.unregister_class(SoloStudioProperties)
