#!/usr/bin/env python3
"""
ComfyUI API モードでワークフローを HTTP POST し、JSON で指定した
プロンプト等を上書きして 10 回連続実行するサンプルスクリプト。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from typing import Any

from utils.comfyui_api import get_history, queue_prompt
from utils.workflow_builder import WorkflowParams, build_workflow


DEFAULT_RUNS = 10
DEFAULT_TIMEOUT = 1800.0
DEFAULT_POLL_INTERVAL = 1.0
BACKOFF_MULTIPLIER = 1.5
MAX_POLL_INTERVAL = 10.0
CFG_COMPARE_REL_TOL = 1e-6
CFG_COMPARE_ABS_TOL = 1e-6


def _load_override_params(args: argparse.Namespace) -> dict[str, Any]:
    if args.params_file:
        with open(args.params_file, "r", encoding="utf-8") as f:
            return json.load(f)
    if args.params:
        return json.loads(args.params)
    return {}


def _apply_overrides(params: WorkflowParams, overrides: dict[str, Any]) -> None:
    cfg_value = overrides.get("cfg")
    cfg_scale_value = overrides.get("cfg_scale")
    if cfg_value is not None and cfg_scale_value is not None:
        cfg_value = float(cfg_value)
        cfg_scale_value = float(cfg_scale_value)
        if not math.isclose(
            cfg_value,
            cfg_scale_value,
            rel_tol=CFG_COMPARE_REL_TOL,
            abs_tol=CFG_COMPARE_ABS_TOL,
        ):
            print(
                "警告: 'cfg' と 'cfg_scale' が同時指定されています。"
                " 'cfg_scale' を優先します。",
                file=sys.stderr,
            )
        params.cfg_scale = cfg_scale_value
    if "prompt" in overrides:
        params.positive_prompt = str(overrides["prompt"])
    if "negative_prompt" in overrides:
        params.negative_prompt = str(overrides["negative_prompt"])
    if cfg_scale_value is not None and cfg_value is None:
        params.cfg_scale = float(cfg_scale_value)
    if cfg_value is not None and cfg_scale_value is None:
        params.cfg_scale = float(cfg_value)
    if "steps" in overrides:
        params.steps = int(overrides["steps"])
    if "seed" in overrides:
        params.seed = int(overrides["seed"])


def _collect_output_files(history: dict, prompt_id: str) -> list[str]:
    outputs = history.get(prompt_id, {}).get("outputs", {})
    files: list[str] = []
    for node_output in outputs.values():
        for key in ("videos", "images", "gifs"):
            for item in node_output.get(key, []):
                filename = item.get("filename")
                if filename:
                    files.append(filename)
    return files


def _wait_for_completion(
    host: str,
    port: int,
    prompt_id: str,
    poll_interval: float = 1.0,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[str]:
    start = time.monotonic()
    current_interval = poll_interval
    while True:
        history = get_history(host, port, prompt_id)
        files = _collect_output_files(history, prompt_id)
        if files:
            return files
        if time.monotonic() - start > timeout:
            raise TimeoutError("生成がタイムアウトしました。")
        time.sleep(current_interval)
        current_interval = min(current_interval * BACKOFF_MULTIPLIER, MAX_POLL_INTERVAL)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ComfyUI API モードでワークフローを複数回連続実行します。"
    )
    parser.add_argument("--host", default="127.0.0.1", help="ComfyUI ホスト")
    parser.add_argument("--port", type=int, default=8188, help="ComfyUI ポート")
    parser.add_argument("--params", help="上書き用 JSON 文字列")
    parser.add_argument("--params-file", help="上書き用 JSON ファイルパス")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="実行回数")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="タイムアウト秒")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help="ポーリング間隔",
    )
    args = parser.parse_args()

    overrides = _load_override_params(args)

    params = WorkflowParams()
    _apply_overrides(params, overrides)
    workflow = build_workflow(params)

    print(f"JSON 上書き内容: {json.dumps(overrides, ensure_ascii=False)}")
    print(f"実行回数: {args.runs}")

    for run_number in range(1, args.runs + 1):
        start = time.perf_counter()
        response = queue_prompt(args.host, args.port, workflow)
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"prompt_id が取得できません: {response}")

        output_files = _wait_for_completion(
            args.host,
            args.port,
            prompt_id,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        elapsed = time.perf_counter() - start
        output_count = len(output_files)
        if output_count == 0:
            print(
                f"{run_number:02d}/{args.runs} 回目: 出力なし "
                f"(生成時間: {elapsed:.2f} 秒)"
            )
        else:
            per_image = elapsed / output_count
            print(
                f"{run_number:02d}/{args.runs} 回目: 1枚あたり {per_image:.2f} 秒 "
                f"(合計: {elapsed:.2f} 秒, 出力: {', '.join(output_files)})"
            )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        sys.exit(1)
