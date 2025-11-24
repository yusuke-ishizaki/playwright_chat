# Playwright ブラウザAIエージェント

Streamlitを使用したブラウザ自動化AIエージェントです。JSONで定義されたシナリオを実行し、Gemini AIを使用してシナリオを修正できます。

## 機能

- JSONファイルからブラウザ自動化シナリオを読み込み
- Gemini AIを使用してシナリオを自然言語で修正
- Playwrightを使用したブラウザ自動化の実行
- 実行プロセスのビデオ録画とスクリーンショット

## ローカル開発

### 必要要件

- Python 3.13+
- uv (推奨) または pip

### セットアップ

1. リポジトリをクローン
2. 依存関係をインストール:
   ```bash
   uv sync
   ```
3. Playwrightブラウザをインストール:
   ```bash
   playwright install chromium
   ```
4. `.env`ファイルを作成し、Google API Keyを設定:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

### 実行

```bash
streamlit run main.py
```

## Streamlit Cloudへのデプロイ

### 1. リポジトリの準備

このリポジトリをGitHubにプッシュします。

### 2. Streamlit Cloudでアプリを作成

1. [Streamlit Cloud](https://streamlit.io/cloud)にアクセス
2. "New app"をクリック
3. リポジトリ、ブランチ、メインファイル(`main.py`)を選択

### 3. Secretsの設定

Streamlit Cloudのアプリ設定で、以下のシークレットを追加:

```toml
GOOGLE_API_KEY = "your_google_api_key_here"
```

### 4. デプロイ

"Deploy"をクリックしてアプリをデプロイします。

## 注意事項

- Streamlit Cloudでは、Playwrightはヘッドレスモードでのみ動作します
- ビデオ録画とスクリーンショットは正常に機能します
- シナリオファイルはアプリ内でアップロードする必要があります

## ライセンス

MIT
