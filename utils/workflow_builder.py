"""
Phase 1 / Phase 3 – ComfyUI ワークフロービルダー
==================================================
Animagine XL 3.1 + AnimateDiff + ControlNet (Depth / Lineart / Normal) +
IP-Adapter（キャラクター設定画） の「黄金比」ワークフローを
ComfyUI API 形式の辞書として生成するモジュール。

ユーザーは演出パラメータ（プロンプト / CFG / ステップ数 / シード）だけを
指定すれば良く、複雑な AI 設定はすべてここで隠蔽されます（Phase 4 要件）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# パラメータ定義
# ---------------------------------------------------------------------------

@dataclass
class WorkflowParams:
    """ワークフロー生成に必要なパラメータをまとめたデータクラス"""

    # --- プロンプト ---
    positive_prompt: str = "anime style, high quality, detailed character"
    negative_prompt: str = "lowres, bad anatomy, worst quality, blurry"

    # --- サンプリング ---
    cfg_scale: float = 7.0
    steps: int = 20
    seed: int = -1
    sampler_name: str = "euler_ancestral"
    scheduler: str = "karras"

    # --- 解像度 ---
    width: int = 768
    height: int = 512

    # --- AnimateDiff ---
    frame_count: int = 16
    context_length: int = 16
    context_overlap: int = 4
    fps: int = 8

    # --- ControlNet 強度 ---
    depth_strength: float = 0.75
    lineart_strength: float = 0.65
    normal_strength: float = 0.55

    # --- IP-Adapter ---
    ip_adapter_strength: float = 0.70

    # --- 入力ファイルパス (ComfyUI input/ フォルダからの相対名) ---
    depth_image: str = "depth/frame_0001.png"
    lineart_image: str = "lineart/frame_0001.png"
    normal_image: str = "normal/frame_0001.png"
    char_ref_image: str = "char_ref.png"

    # --- モデル名 ---
    checkpoint: str = "animagineXLV31_v31.safetensors"
    animatediff_motion_module: str = "mm_sdxl_v10_beta.ckpt"
    controlnet_depth: str = "diffusers_xl_depth_full.safetensors"
    controlnet_lineart: str = "control_v11p_sd15_lineart.pth"
    controlnet_normal: str = "control_v11p_sd15_normalbae.pth"
    ip_adapter_model: str = "ip-adapter-plus_sdxl_vit-h.bin"
    clip_vision_model: str = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"


# ---------------------------------------------------------------------------
# ノード ID 割り当てヘルパー
# ---------------------------------------------------------------------------

class _NodeIdAllocator:
    def __init__(self) -> None:
        self._counter = 0

    def next(self) -> str:
        self._counter += 1
        return str(self._counter)


# ---------------------------------------------------------------------------
# ワークフロー生成
# ---------------------------------------------------------------------------

def build_workflow(params: WorkflowParams) -> dict:
    """
    ComfyUI API 形式のワークフロー辞書を生成して返す。

    ノード構成:
      1  CheckpointLoaderSimple      (Animagine XL 3.1)
      2  CLIPTextEncode (positive)
      3  CLIPTextEncode (negative)
      4  LoadImage (depth)
      5  LoadImage (lineart)
      6  LoadImage (normal)
      7  LoadImage (char_ref)
      8  ControlNetLoader (depth)
      9  ControlNetLoader (lineart)
      10 ControlNetLoader (normal)
      11 ControlNetApplyAdvanced (depth)
      12 ControlNetApplyAdvanced (lineart)
      13 ControlNetApplyAdvanced (normal)
      14 CLIPVisionLoader
      15 IPAdapterModelLoader
      16 IPAdapter
      17 ADE_AnimateDiffLoaderWithContext  (AnimateDiff + Sliding Window)
      18 KSampler
      19 VAEDecode
      20 VHS_VideoCombine              (動画出力)
    """
    ids = _NodeIdAllocator()
    n_checkpoint    = ids.next()  # 1
    n_clip_pos      = ids.next()  # 2
    n_clip_neg      = ids.next()  # 3
    n_load_depth    = ids.next()  # 4
    n_load_lineart  = ids.next()  # 5
    n_load_normal   = ids.next()  # 6
    n_load_ref      = ids.next()  # 7
    n_cn_depth      = ids.next()  # 8
    n_cn_lineart    = ids.next()  # 9
    n_cn_normal     = ids.next()  # 10
    n_cn_apply_d    = ids.next()  # 11
    n_cn_apply_l    = ids.next()  # 12
    n_cn_apply_n    = ids.next()  # 13
    n_clip_vision   = ids.next()  # 14
    n_ipa_loader    = ids.next()  # 15
    n_ipa           = ids.next()  # 16
    n_animatediff   = ids.next()  # 17
    n_ksampler      = ids.next()  # 18
    n_vae_decode    = ids.next()  # 19
    n_video_out     = ids.next()  # 20
    n_empty_latent  = ids.next()  # 21

    seed_val = params.seed if params.seed >= 0 else _random_seed()

    workflow: dict = {
        # --- チェックポイントロード ---
        n_checkpoint: {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": params.checkpoint},
        },

        # --- テキストエンコード ---
        n_clip_pos: {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [n_checkpoint, 1],
                "text": params.positive_prompt,
            },
        },
        n_clip_neg: {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [n_checkpoint, 1],
                "text": params.negative_prompt,
            },
        },

        # --- 画像ロード ---
        n_load_depth: {
            "class_type": "LoadImage",
            "inputs": {"image": params.depth_image, "upload": "image"},
        },
        n_load_lineart: {
            "class_type": "LoadImage",
            "inputs": {"image": params.lineart_image, "upload": "image"},
        },
        n_load_normal: {
            "class_type": "LoadImage",
            "inputs": {"image": params.normal_image, "upload": "image"},
        },
        n_load_ref: {
            "class_type": "LoadImage",
            "inputs": {"image": params.char_ref_image, "upload": "image"},
        },

        # --- ControlNet ローダー ---
        n_cn_depth: {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": params.controlnet_depth},
        },
        n_cn_lineart: {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": params.controlnet_lineart},
        },
        n_cn_normal: {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": params.controlnet_normal},
        },

        # --- ControlNet 適用 (Depth) ---
        n_cn_apply_d: {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": [n_clip_pos, 0],
                "negative": [n_clip_neg, 0],
                "control_net": [n_cn_depth, 0],
                "image": [n_load_depth, 0],
                "strength": params.depth_strength,
                "start_percent": 0.0,
                "end_percent": 1.0,
            },
        },

        # --- ControlNet 適用 (Lineart) ---
        n_cn_apply_l: {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": [n_cn_apply_d, 0],
                "negative": [n_cn_apply_d, 1],
                "control_net": [n_cn_lineart, 0],
                "image": [n_load_lineart, 0],
                "strength": params.lineart_strength,
                "start_percent": 0.0,
                "end_percent": 1.0,
            },
        },

        # --- ControlNet 適用 (Normal) ---
        n_cn_apply_n: {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": [n_cn_apply_l, 0],
                "negative": [n_cn_apply_l, 1],
                "control_net": [n_cn_normal, 0],
                "image": [n_load_normal, 0],
                "strength": params.normal_strength,
                "start_percent": 0.0,
                "end_percent": 1.0,
            },
        },

        # --- CLIP Vision / IP-Adapter ---
        n_clip_vision: {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": params.clip_vision_model},
        },
        n_ipa_loader: {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": params.ip_adapter_model},
        },
        n_ipa: {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": [n_checkpoint, 0],
                "ipadapter": [n_ipa_loader, 0],
                "image": [n_load_ref, 0],
                "clip_vision": [n_clip_vision, 0],
                "weight": params.ip_adapter_strength,
                "weight_type": "linear",
                "combine_embeds": "concat",
                "start_at": 0.0,
                "end_at": 1.0,
                "embeds_scaling": "V only",
            },
        },

        # --- AnimateDiff (Sliding Window Context) ---
        n_animatediff: {
            "class_type": "ADE_AnimateDiffLoaderWithContext",
            "inputs": {
                "model": [n_ipa, 0],
                "motion_model": params.animatediff_motion_module,
                "context_options": {
                    "context_length": params.context_length,
                    "context_stride": 1,
                    "context_overlap": params.context_overlap,
                    "context_schedule": "uniform",
                    "closed_loop": False,
                },
                "motion_scale": 1.0,
                "apply_v2_models_properly": True,
            },
        },

        # --- 空の潜在空間 ---
        n_empty_latent: {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": params.width,
                "height": params.height,
                "batch_size": params.frame_count,
            },
        },

        # --- KSampler ---
        n_ksampler: {
            "class_type": "KSampler",
            "inputs": {
                "model": [n_animatediff, 0],
                "positive": [n_cn_apply_n, 0],
                "negative": [n_cn_apply_n, 1],
                "latent_image": [n_empty_latent, 0],
                "seed": seed_val,
                "steps": params.steps,
                "cfg": params.cfg_scale,
                "sampler_name": params.sampler_name,
                "scheduler": params.scheduler,
                "denoise": 1.0,
            },
        },

        # --- VAE デコード ---
        n_vae_decode: {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [n_ksampler, 0],
                "vae": [n_checkpoint, 2],
            },
        },

        # --- 動画出力 ---
        n_video_out: {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": [n_vae_decode, 0],
                "frame_rate": params.fps,
                "loop_count": 0,
                "filename_prefix": "SoloStudio",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }

    return workflow


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _random_seed() -> int:
    import random
    return random.randint(0, 2**32 - 1)


def params_from_scene_props(props: object) -> WorkflowParams:
    """
    Blender シーンの SoloStudioProperties から WorkflowParams を生成する。
    char_ref_image は ComfyUI input/ フォルダへのアップロード後のファイル名
    を想定しているため、ここではパス末尾のファイル名のみを使用します。
    """
    import os

    char_ref = ""
    if props.char_ref_path:
        import bpy
        abs_path = bpy.path.abspath(props.char_ref_path)
        char_ref = os.path.basename(abs_path)

    return WorkflowParams(
        positive_prompt=props.positive_prompt,
        negative_prompt=props.negative_prompt,
        cfg_scale=props.cfg_scale,
        steps=props.steps,
        seed=props.seed,
        frame_count=props.context_length,
        context_length=props.context_length,
        context_overlap=props.context_overlap,
        char_ref_image=char_ref or "char_ref.png",
    )
