やってないこと
・フロントエンド部分の制作
・(完了) インストーラー作成して導入手軽にする







# 4-S-ADD-ON
Solo Studio SystemS = 4S (FORCE) ADD-ON

## Blender アドオン導入インストーラー

`install_blender_addons.py` で、以下 2 つのアドオンをまとめて導入できます。

- `solo_studio_director`
- `four_s_addon`

### 使い方

```bash
python install_blender_addons.py --blender-version 4.0
```

既定では OS ごとの Blender ユーザーアドオンディレクトリへ導入し、同時に `dist/` に ZIP も作成します。

### 主なオプション

- `--addons-dir <path>`: 導入先を明示指定
- `--zip-only`: ZIP 作成のみ（導入はしない）
- `--dry-run`: 導入先と対象のみ確認（実際にはコピーしない）
- `--dist-dir <path>`: ZIP 出力先を変更

導入時に同名アドオンが既に存在する場合は自動でバックアップしてから置き換えます。

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

## バックエンド API (4'S Cloud Studio)

`backend/` ディレクトリに FastAPI ベースのバックエンド API 雛形があります。

### セットアップ

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 必要な値を編集
```

### 開発サーバー起動

```bash
uvicorn main:app --reload
```

Swagger UI は `http://localhost:8000/docs` で確認できます。

### 主なエンドポイント

| メソッド | パス | 説明 |
|--------|------|------|
| POST | `/auth/register` | ユーザー登録 |
| POST | `/auth/login` | JWT アクセストークン取得 |
| GET | `/models/{user_id}/lora` | LoRA モデル一覧取得（Blender アドオン用） |
| POST | `/models/{user_id}/lora` | LoRA モデルファイルアップロード |
| GET | `/models/{user_id}/lora/{filename}` | LoRA モデルファイルダウンロード |
| DELETE | `/models/{user_id}/lora/{filename}` | LoRA モデルファイル削除 |
| POST | `/snapshots/` | 生成パラメータスナップショット保存 |
| GET | `/snapshots/` | スナップショット一覧取得 |
| GET | `/snapshots/{id}` | スナップショット取得 |
| PUT | `/snapshots/{id}` | スナップショット更新 |
| DELETE | `/snapshots/{id}` | スナップショット削除 |

> S3 互換ストレージ（AWS S3, MinIO など）の認証情報と PostgreSQL の接続情報を `.env` に設定してください。

---

## Depth / Lineart 書き出し

Blender の N パネル (SoloStudio) から「Depth/Lineart をバックグラウンド出力」を実行すると、
プロジェクトフォルダ直下に depth/ と lineart/ が作成され、フレーム番号付きで保存されます。

コマンドラインから実行する場合:

```bash
blender -b your_scene.blend --python utils/depth_lineart_export.py
```
