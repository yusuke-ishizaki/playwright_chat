# Playwright公式イメージを使用（Ubuntu Jammyベース）
# これにより、ブラウザの実行に必要なすべてのシステム依存関係が含まれます
FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

# インストールされるPythonのバージョンはイメージに依存しますが、
# 通常は最新または安定版が含まれています

# uvの導入
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 作業ディレクトリの設定
WORKDIR /app

RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# 設定ファイルのコピー
COPY pyproject.toml uv.lock ./

# Python依存関係のインストール（uvを使用）
RUN uv sync --frozen --no-cache

# 仮想環境のパスをセット
ENV PATH="/app/.venv/bin:$PATH"

# Playwrightブラウザのインストール
# 注: 公式イメージには既にブラウザが含まれていますが、
# Pythonパッケージのバージョンと一致させるために念のため実行します
# RUN playwright install chromium

# アプリケーションコードのコピー
COPY . .

# Streamlitのポート
EXPOSE 8501

# アプリケーションの実行
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
