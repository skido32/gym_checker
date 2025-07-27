FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージを更新し、必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Node.jsとnpmをインストール（Playwright用）
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Python依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwrightブラウザをインストール
RUN playwright install chromium

# アプリケーションファイルをコピー
COPY toda_playwright_checker.py .
COPY config.json .

# .envファイルが存在する場合はコピー
COPY .env* ./

# ログディレクトリを作成
RUN mkdir -p logs

# 環境変数を設定
ENV PYTHONUNBUFFERED=1

# ヘルスチェック用のコマンド
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD playwright --version || exit 1

# デフォルトコマンド
CMD ["python", "toda_playwright_checker.py"] 
