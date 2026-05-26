


# 4-S-ADD-ON
Solo Studio SystemS = 4S (FORCE) ADD-ON

Blender × ComfyUI を連携させ、アニメーションを半自動生成する「一人アニメスタジオ」アドオン。
3D モーションデータと ローカル AI（AnimateDiff / IP-Adapter）を組み合わせ、  
プロンプト＋参照画像から高品質なアニメーションを生成します。

---

## ⚡ クイックスタート（最短 3 分）

> **前提**: Blender 4.0 以上 ／ ComfyUI がローカルで起動済みであること

### 1. アドオンをインストールする

```bash
python install_blender_addons.py --blender-version 4.0
```

または Windows の場合は `dist/4-S-ADD-ON-setup.exe` を使ったインストーラー形式もあります。

Blender を起動し、**編集 → プリファレンス → アドオン** で  
「SoloStudio Director」を有効化してください。

### 2. N パネルを開く

3D ビューポートで `N` キーを押し、「**SoloStudio**」タブを選択します。  
初回起動時はセットアップガイドが自動表示されます。

### 3. 基本フローを実行する

| ステップ | パネル | 操作 |
|---------|--------|------|
| ① | ComfyUI 接続設定 | ホスト `127.0.0.1`・ポート `8188` を確認 |
| ② | キャラクター設定 | `char_ref.png`（参照画像）を指定 |
| ③ | レンダリングパス設定 | 出力先を指定し「マルチパスレンダリング」を実行 |
| ④ | AI 生成設定 | プロンプトを入力 |
| ⑤ | 実行 / 進捗 | 「▶ ComfyUI へ送信」を押す |
| ⑥ | ポストプロセス (VSE) | 完了後に動画を確認・編集 |

> 💡 **N パネルの「ヘルプ / ガイド」セクション**からいつでもセットアップガイドを再表示できます。

---

## 🗂 パネルリファレンス

### キャラクター設定
IP-Adapter に使用するキャラクター参照画像（`char_ref.png`）を指定します。  
ComfyUI へ自動アップロードされ、キャラクターの外見一貫性を維持します。

### レンダリングパス設定
生成に必要な素材をマルチパスで出力します。

| パス | 用途 |
|------|------|
| Depth | 奥行き情報。ControlNet Depth で構図を維持 |
| Lineart | 輪郭線。Lineart ControlNet でアニメ調の線画を保持 |
| Normal | 法線マップ。カメラ移動時の陰影を正確に再現 |
| Character Mask | IP-Adapter の影響範囲をキャラクター領域に限定 |
| Base Color | Workbench フラットカラー。色彩情報の基準 |

### AI 生成設定
ComfyUI に送るプロンプトとサンプリングパラメータを設定します。

| 項目 | 説明 |
|------|------|
| ポジティブプロンプト | 生成したい映像の内容（例: `anime style, high quality`） |
| ネガティブプロンプト | 除外したい要素（例: `lowres, blurry`） |
| CFG スケール | プロンプトへの従順度（7〜8 が標準） |
| ステップ数 | 品質と速度のトレードオフ（20〜30 推奨） |
| シード値 | `-1` でランダム、固定値で再現可能 |

### AnimateDiff 設定（上級）
アニメーション生成に使う AnimateDiff の Sliding Window を調整します。  
**通常はデフォルト値（コンテキスト長 16・重複 4）で問題ありません。**

### ComfyUI 接続設定
ComfyUI サーバーのホストとポートを指定します。  
デフォルト `127.0.0.1:8188` でローカル実行の場合はそのままで使えます。

### 実行 / 進捗
「▶ ComfyUI へ送信」を押すと生成が始まります。  
プログレスバーで進捗を確認でき、生成中は「×」でキャンセルできます。

### バッチ処理（フレームシーケンス生成）
複数フレームを連続して自動生成します。  
フレーム範囲・出力先を指定して「▶ バッチ処理開始」を押します。

### ポストプロセス（VSE）
生成完了後に動画を Blender の Video Sequence Editor へ自動インポートします。  
「生成後に VSE へ自動インポート」を有効にしておくと手動操作不要です。

### ヘルプ / ガイド
基本フロー・トラブルシュート・オンラインドキュメントリンクにアクセスできます。  
セットアップガイドの再表示もここから行えます。

---

## 🔧 トラブルシュート

| 症状 | 原因 | 対処 |
|------|------|------|
| 「ComfyUI への送信に失敗」 | ComfyUI が起動していない | `http://127.0.0.1:8188` にアクセスして起動確認 |
| 画像のアップロード警告 | `char_ref.png` のパスが無効 | キャラクター設定パネルでパスを再設定 |
| 進捗バーが動かない | WebSocket 接続が切れている | ComfyUI を再起動して再度送信 |
| レンダリングパスが出力されない | 出力先フォルダが存在しない / パスの誤り | `//solo_studio_passes/` などの有効なパスを指定 |
| バッチ処理が止まる | 途中のフレームで ComfyUI がタイムアウト | ステップ数を下げるか ComfyUI の GPU メモリを確認 |
| VSE に動画が表示されない | 自動インポートが無効 | ポストプロセスパネルで「自動インポート」を有効化 |

---

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

### .exe スタイル (Windows GUI) インストーラー

Windows で配布しやすい `.exe` インストーラーは、Inno Setup 用スクリプト
`installer/windows/4s_addon_installer.iss` で作成できます。

1. Inno Setup 6 をインストール
2. Inno Setup Compiler (`ISCC.exe`) で `installer/windows/4s_addon_installer.iss` をビルド
3. `dist/4-S-ADD-ON-setup.exe` が生成される

インストーラーは `%APPDATA%\Blender Foundation\Blender\` 配下の既存バージョンを検出して
既定の `addons` ディレクトリを自動設定し、必要に応じて変更できます。
既存の `solo_studio_director` / `four_s_addon` がある場合は自動でバックアップします。

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
