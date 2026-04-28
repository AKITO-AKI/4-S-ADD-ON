# 4-S-ADD-ON
Solo Studio SystemS = 4S (FORCE) ADD-ON

## ComfyUI API モード 実行例

`comfyui_api_mode_runner.py` を使うと、HTTP POST でワークフローを送信し、
JSON でプロンプト等を上書きしたうえで 10 回連続実行できます。

```bash
python comfyui_api_mode_runner.py \
  --host 127.0.0.1 \
  --port 8188 \
  --params '{"prompt":"demo","negative_prompt":"bad","cfg":7.5,"steps":20,"seed":1234}'
```

JSON ファイル指定も可能です。

```bash
python comfyui_api_mode_runner.py --params-file overrides.json
```

## Depth / Lineart 書き出し

Blender の N パネル (SoloStudio) から「Depth/Lineart をバックグラウンド出力」を実行すると、
プロジェクトフォルダ直下に depth/ と lineart/ が作成され、フレーム番号付きで保存されます。

コマンドラインから実行する場合:

```bash
blender -b your_scene.blend --python utils/depth_lineart_export.py
```
