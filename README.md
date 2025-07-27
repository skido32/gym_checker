# 戸田市施設予約システム バドミントン空き状況チェッカー

戸田市の施設予約システムからバドミントンの空き情報を自動取得するプログラムです。

## 機能

- 🏸 戸田市スポーツセンター 第1競技場1/2面の空き状況を自動チェック
- 📅 1週間分の予約状況を取得
- 🔔 Slack通知機能（空きが見つかった場合）
- 📊 結果をJSONファイルで保存
- 📝 詳細なログ出力

## 必要な環境

- Docker Desktop
- docker-compose

または

- Python 3.11+
- GitHub Actions（定期実行用）

## インストール

1. Docker Desktopをインストール
2. リポジトリをクローン
3. ローカル実行時は環境変数を設定：

```bash
# 一時的に環境変数を設定
export SLACK_WEBHOOK_URL="your_webhook_url_here"
```

## 使用方法

### GitHub Actions（推奨）
- 自動的に定期実行されます
- 設定不要で即座に使用可能

### ローカル実行

#### 1. 環境変数の設定
```bash
# 一時的に環境変数を設定
export SLACK_WEBHOOK_URL="your_webhook_url_here"

# または、1行で実行
SLACK_WEBHOOK_URL="your_webhook_url_here" ./docker-run.sh run
```

#### 2. 実行
```bash
# 初回セットアップ（イメージビルド）
./docker-run.sh build

# 1回実行
./docker-run.sh run

# 30分ごとに自動実行
./docker-run.sh schedule

# 停止
./docker-run.sh stop

# ログ確認
./docker-run.sh logs

# クリーンアップ
./docker-run.sh clean

# ヘルプ
./docker-run.sh help
```

### 設定のカスタマイズ

`config.json`ファイルを編集して設定を変更できます：

```json
{
  "facility": {
    "name": "戸田市スポーツセンター",
    "facility_type": "第１競技場１／２面",
    "sport": "バドミントン"
  },
  "search_settings": {
    "period": "1週間",
    "check_times": ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]
  }
}
```

### Slack通知の設定

1. SlackでIncoming Webhookを作成
2. 以下のいずれかの方法でWebhook URLを設定：

#### 方法1: .envファイルを使用（推奨）
```bash
# .envファイルを作成
echo "SLACK_WEBHOOK_URL=your_webhook_url_here" > .env
```

#### 方法2: config.jsonで設定
```json
{
  "notification": {
    "slack_webhook_url": "your_webhook_url_here"
  }
}
```

#### 方法3: 環境変数で設定
```bash
export SLACK_WEBHOOK_URL="your_webhook_url_here"
```

### GitHub Actionsでの定期実行設定

1. **Slack Webhook URLの設定**:
   - GitHubリポジトリの「Settings」→「Secrets and variables」→「Actions」
   - 「New repository secret」をクリック
   - Name: `SLACK_WEBHOOK_URL`
   - Value: あなたのSlack Webhook URL
   - 「Add secret」をクリック

2. **ワークフローの有効化**:
   - `.github/workflows/toda-checker.yml`が自動的に定期実行されます
   - 毎日9:00, 11:00, 13:00, 15:00, 17:00, 19:00（JST）に実行
   - 手動実行も可能（Actionsタブから「Run workflow」）
   - **Docker環境で実行されるため、環境依存が少なく安定しています**

3. **実行時間の変更**:
   - `.github/workflows/toda-checker.yml`の`cron`設定を編集
   - 現在: `'0 0,2,4,6,8,10 * * *'`（UTC時間、JST-9時間）

## 出力例

```
============================================================
🏸 戸田市スポーツセンター バドミントン空き情報
============================================================
施設: 戸田市スポーツセンター 第1競技場1/2面
確認日時: 2025-01-27 15:30:00
期間: 1週間
------------------------------------------------------------

📅 07/26 土
  09:00 ✅ 利用可能
  17:00 ⚠️ 空きあり

📅 07/29 火
  09:00 ⚠️ 空きあり

------------------------------------------------------------
🎉 空きが見つかりました: 3件
============================================================
```

## ファイル構成

```
gem_checker/
├── toda_playwright_checker.py    # メインプログラム
├── docker-run.sh                # Docker実行スクリプト
├── requirements.txt              # Python依存関係
├── config.json                   # 設定ファイル
├── Dockerfile                    # Dockerイメージ定義
├── docker-compose.yml           # Docker Compose設定
├── .dockerignore                # Docker除外ファイル
├── .github/workflows/           # GitHub Actions設定
│   └── toda-checker.yml         # 定期実行ワークフロー
├── logs/                         # ログディレクトリ
│   ├── toda_playwright_YYYYMMDD.log
│   └── toda_results_YYYYMMDD_HHMMSS.json
└── README.md                     # このファイル
```

## ステータス記号の意味

- ✅ **利用可能** (―): 即座に予約可能
- ⚠️ **空きあり** (△): 抽選の可能性あり
- ❌ **予約済み** (×): 既に予約されている
- ❓ **不明** (その他): ステータスが不明

## 定期実行

```bash
# 30分ごとに自動実行を開始
./docker-run.sh schedule

# バックグラウンドで実行
docker-compose up -d toda-scheduler

# 停止
./docker-run.sh stop
```

## トラブルシューティング

### よくある問題

1. **Dockerがインストールされていない**
   - Docker Desktopをインストールしてください

2. **権限エラー**
   ```bash
   chmod +x docker-run.sh
   ```

3. **ログディレクトリが存在しない**
   ```bash
   mkdir -p logs
   ```

### ログの確認

```bash
# Dockerログを確認
./docker-run.sh logs

# 結果ファイルを確認
ls -la logs/toda_results_*.json
```

## 注意事項

- このプログラムは戸田市の公式サービスではありません
- 過度なアクセスは避けてください
- 予約システムの仕様変更により動作しなくなる可能性があります
- 取得した情報の正確性は保証されません

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 更新履歴

- 2025-01-27: 初回リリース
  - Playwrightを使用した自動チェック機能
  - Slack通知機能
  - JSON形式での結果保存 
