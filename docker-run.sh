#!/bin/bash

# 戸田市施設予約システム バドミントン空き状況チェッカー（Docker版）

set -e

echo "=== 戸田市施設予約システム チェッカー（Docker版）開始 ==="
echo "実行日時: $(date)"

# ログディレクトリの作成
mkdir -p logs

# .envファイルが存在する場合は読み込み
if [ -f ".env" ]; then
    echo "📄 .envファイルを読み込み中..."
    # コメント行を除外して環境変数を読み込み
    while IFS= read -r line; do
        # 空行、コメント行、空白行をスキップ
        if [[ ! -z "$line" && ! "$line" =~ ^[[:space:]]*# ]]; then
            export "$line"
        fi
    done < .env
fi

# 環境変数の確認（ビルド時以外）
if [ -z "$SLACK_WEBHOOK_URL" ] && [ "${1:-run}" != "build" ]; then
    echo "⚠️  SLACK_WEBHOOK_URLが設定されていません"
    echo "   環境変数で設定するか、.envファイルを作成してください"
    echo "   例: export SLACK_WEBHOOK_URL='your_webhook_url_here'"
    echo "   または、.envファイルに以下を追加してください:"
    echo "   SLACK_WEBHOOK_URL=your_webhook_url_here"
fi

# Docker Composeの確認
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-composeがインストールされていません"
    echo "   Docker Desktopをインストールするか、docker-composeをインストールしてください"
    exit 1
fi

# Dockerの確認
if ! command -v docker &> /dev/null; then
    echo "❌ Dockerがインストールされていません"
    echo "   Docker Desktopをインストールしてください"
    exit 1
fi

# 引数の処理
case "${1:-run}" in
    "build")
        echo "🔨 Dockerイメージをビルド中..."
        docker-compose build --build-arg SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL"
        echo "✅ ビルド完了"
        ;;
    "run")
        echo "🚀 チェッカーを実行中..."
        docker-compose run --rm toda-checker
        echo "✅ チェッカー実行完了"
        ;;
    "schedule")
        echo "⏰ スケジューラーを開始中..."
        echo "   30分ごとに自動チェックを実行します"
        echo "   停止するには: docker-compose stop toda-scheduler"
        docker-compose up toda-scheduler
        ;;
    "stop")
        echo "🛑 サービスを停止中..."
        docker-compose down
        echo "✅ 停止完了"
        ;;
    "logs")
        echo "📋 ログを表示中..."
        docker-compose logs toda-checker
        ;;
    "clean")
        echo "🧹 クリーンアップ中..."
        docker-compose down --rmi all --volumes --remove-orphans
        echo "✅ クリーンアップ完了"
        ;;
    "help")
        echo "使用方法:"
        echo "  $0 [command]"
        echo ""
        echo "コマンド:"
        echo "  build     - Dockerイメージをビルド"
        echo "  run       - チェッカーを1回実行（デフォルト）"
        echo "  schedule  - 30分ごとに自動チェックを実行"
        echo "  stop      - サービスを停止"
        echo "  logs      - ログを表示"
        echo "  clean     - イメージとコンテナを削除"
        echo "  help      - このヘルプを表示"
        echo ""
        echo "環境変数:"
        echo "  SLACK_WEBHOOK_URL - Slack通知用のWebhook URL"
        ;;
    *)
        echo "❌ 不明なコマンド: $1"
        echo "   '$0 help' で使用方法を確認してください"
        exit 1
        ;;
esac

echo "実行終了時刻: $(date)" 
