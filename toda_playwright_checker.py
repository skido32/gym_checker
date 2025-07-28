#!/usr/bin/env python3
"""
戸田市施設予約システム チェッカー
Playwrightを使用してWebスクレイピングを行い、空き状況を確認します。
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

from playwright.async_api import async_playwright
from dotenv import load_dotenv

class TodaPlaywrightChecker:
    def __init__(self):
        self.base_url = "https://yoyaku.city.toda.saitama.jp/yoyaku/"
        self.logger = self._setup_logger()
        self.config = self.load_config()
        
    def load_config(self):
        """設定ファイルを読み込みます"""
        # .envファイルの存在を確認
        env_file_path = Path('.env')
        if env_file_path.exists():
            self.logger.info(".envファイルが見つかりました")
            load_dotenv()
        else:
            self.logger.info(".envファイルが見つかりません")
        
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            self.logger.warning("config.jsonが見つかりません。デフォルト設定を使用します。")
            config = {
                "notification": {
                    "slack_webhook_url": "",
                    "notify_on_available": True,
                    "notify_on_error": False,
                    "min_advance_notice_hours": 24
                }
            }
        
        # 環境変数からSlack Webhook URLを取得（.envファイルまたはシステム環境変数から）
        slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        if slack_webhook_url:
            config["notification"]["slack_webhook_url"] = slack_webhook_url
            self.logger.info("環境変数からSlack Webhook URLを設定しました")
        else:
            self.logger.warning("⚠️  SLACK_WEBHOOK_URLが設定されていません")
            self.logger.info("環境変数で設定するか、.envファイルを作成してください")
            self.logger.info("例: export SLACK_WEBHOOK_URL='your_webhook_url_here'")
            if env_file_path.exists():
                self.logger.info("または、.envファイルに以下を追加してください:")
                self.logger.info("SLACK_WEBHOOK_URL=your_webhook_url_here")
        
        return config

    def _setup_logger(self):
        """ロガーを設定します"""
        # 既存のロガーをクリア
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # 新しいロガーを作成
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # コンソール出力のみのハンドラーを追加
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger

    async def set_search_conditions(self, page):
        """検索条件を設定します"""
        self.logger.info("検索条件を設定中...")
        
        try:
            # ステップ1: 入力フォームをクリックして検索オプションUIを表示
            self.logger.info("ステップ1: 入力フォームをクリックして検索オプションUIを表示")
            await page.click('input[placeholder="施設名・曜日などを入力"]', timeout=30000)
            await page.wait_for_timeout(5000)  # より長い待機時間
            
            # ステップ2: 曜日選択（土曜、日曜、祝日）
            self.logger.info("ステップ2: 曜日選択")
            try:
                # 土曜を選択
                saturday_button = page.get_by_text('土')
                await saturday_button.click()
                await page.wait_for_timeout(1500)
                self.logger.info("土曜を選択しました")
                
                # 日曜を選択
                sunday_button = page.get_by_text('日', exact=True)
                await sunday_button.click()
                await page.wait_for_timeout(1500)
                self.logger.info("日曜を選択しました")
                
                # 祝日を選択
                holiday_button = page.get_by_text('祝')
                await holiday_button.click()
                await page.wait_for_timeout(1500)
                self.logger.info("祝日を選択しました")
                
            except Exception as e:
                self.logger.warning(f"曜日選択でエラーが発生しました: {e}")
                self.logger.info("曜日選択をスキップして続行します")
            
            # ステップ3: 検索ボタンをクリック
            self.logger.info("ステップ3: 検索ボタンをクリック")
            await page.click('button:has-text("検索")')
            await page.wait_for_timeout(3000)  # より長い待機時間
            
            # ステップ4: スポーツセンターを選択
            self.logger.info("ステップ4: スポーツセンターを選択")
            await page.get_by_role('button', name='スポーツセンター').click()
            await page.wait_for_timeout(3000)  # より長い待機時間
            
            # ステップ5: 第1競技場1/8面を選択
            self.logger.info("ステップ5: 第1競技場1/8面を選択")
            await page.get_by_role('button', name='第１競技場１／８面').click()
            await page.wait_for_timeout(5000)  # より長い待機時間

            # ステップ6: HTML構造の詳細分析
            self.logger.info("ステップ6: HTML構造の詳細分析")
            await page.wait_for_selector('table', timeout=10000)
            await page.wait_for_timeout(5000)  # より長い待機時間
            
            # テーブルが完全に読み込まれるまで待機
            await page.wait_for_function("""
                () => {
                    const table = document.querySelector('table');
                    if (!table) return false;
                    const rows = table.querySelectorAll('tr');
                    return rows.length >= 2;
                }
            """, timeout=10000)
            
            # HTML構造を分析
            structure_info = await page.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    if (!table) return { error: 'テーブルが見つかりません' };
                    
                    const allRows = table.querySelectorAll('tr');
                    if (allRows.length < 2) return { error: 'テーブル行が不足しています' };
                    
                    const headerRow = allRows[0];
                    const dataRows = Array.from(allRows).slice(1);
                    const headerCells = headerRow.querySelectorAll('th, td');
                    
                    const dates = [];
                    headerCells.forEach((cell, index) => {
                        const text = cell.textContent.trim();
                        if (text) {
                            // 日付形式を正規化（例: "07/26 土" -> "07/26"）
                            const dateMatch = text.match(/(\\d{2}\\/\\d{2})/);
                            if (dateMatch) {
                                dates.push(dateMatch[1]);
                            } else {
                                dates.push(text);
                            }
                        }
                    });
                    
                    console.log('HTML構造分析 - 取得した日付:', dates);
                    console.log('HTML構造分析 - 日付数:', dates.length);
                    
                    return {
                        headerCells: headerCells.length,
                        rows: dataRows.length,
                        dates: dates,
                        totalCells: headerCells.length * dataRows.length
                    };
                }
            """)
            
            self.logger.info(f"HTML構造分析結果: {structure_info}")
            
        except Exception as e:
            self.logger.error(f"検索条件設定でエラーが発生しました: {e}")
            raise

    async def get_availability_data(self, page):
        """空き状況データを取得します"""
        self.logger.info("ステップ6: データ取得")
        
        try:
            # テーブルが完全に読み込まれるまで待機
            await page.wait_for_selector('table', timeout=15000)
            await page.wait_for_timeout(8000)  # より長い待機時間
            
            # テーブルが完全に読み込まれるまで待機
            await page.wait_for_function("""
                () => {
                    const table = document.querySelector('table');
                    if (!table) return false;
                    const rows = table.querySelectorAll('tr');
                    return rows.length >= 2;
                }
            """, timeout=15000)
            
            # JavaScriptでデータを取得
            table_data = await page.evaluate("""
                () => {
                    const table = document.querySelector('table');
                    if (!table) return null;
                    
                    const allRows = table.querySelectorAll('tr');
                    if (allRows.length < 2) return null;
                    
                    const headerRow = allRows[0];
                    const dataRows = Array.from(allRows).slice(1);
                    const headerCells = headerRow.querySelectorAll('th, td');
                    
                    const data = [];
                    const dates = [];
                    
                    // ヘッダーから日付を取得（すべてのセルを対象）
                    headerCells.forEach((cell, index) => {
                        const text = cell.textContent.trim();
                        if (text) {
                            // 日付形式を正規化（例: "07/26 土" -> "07/26"）
                            const dateMatch = text.match(/(\\d{2}\\/\\d{2})/);
                            if (dateMatch) {
                                dates.push(dateMatch[1]);
                            } else {
                                dates.push(text);
                            }
                        }
                    });
                    
                    console.log('取得した日付:', dates);
                    console.log('日付数:', dates.length);
                    console.log('ヘッダーセル数:', headerCells.length);
                    console.log('データ行数:', dataRows.length);
                    
                    // 各行のデータを取得
                    dataRows.forEach((row, rowIndex) => {
                        const cells = row.querySelectorAll('td, th');
                        
                        cells.forEach((cell, colIndex) => {
                            if (colIndex < dates.length) {
                                const date = dates[colIndex];
                                
                                // セルのテキストから直接判定（spanの有無に関わらず）
                                const cellText = cell.textContent.trim();
                                let status, statusText;
                                
                                if (cellText.includes('―')) {
                                    status = 'unavailable';
                                    statusText = '予約不可';
                                } else if (cellText.includes('△')) {
                                    status = 'available';
                                    statusText = '予約可能';
                                } else if (cellText.includes('×')) {
                                    status = 'booked';
                                    statusText = '予約済み';
                                } else {
                                    status = 'unknown';
                                    statusText = cellText || '不明';
                                }
                                
                                console.log(`セル[${rowIndex},${colIndex}]: "${cellText}" -> ${status} (${statusText})`);
                                
                                // 時間部分を抽出（三角記号などを除去）
                                let timeText = cellText.split(' ')[0] || '';
                                // 三角記号、×、―などの記号を除去
                                timeText = timeText.replace(/[△×―]/g, '').trim();
                                
                                data.push({
                                    date: date,
                                    time: timeText,
                                    status: status,
                                    status_text: statusText,
                                    raw_text: cellText,
                                    row: rowIndex,
                                    col: colIndex
                                });
                            }
                        });
                    });
                    
                    console.log('取得したデータ数:', data.length);
                    return data;
                }
            """)
            
            if table_data:
                self.logger.info(f"データ取得成功: {len(table_data)}件")
                return table_data
            else:
                self.logger.warning("テーブルデータが取得できませんでした")
                return []
                
        except Exception as e:
            self.logger.error(f"データ取得でエラーが発生しました: {e}")
            return []

    def send_slack_notification(self, available_count, slots_info):
        """Slack通知を送信します"""
        webhook_url = self.config.get("notification", {}).get("slack_webhook_url", "")
        self.logger.info(f"Slack Webhook URL設定状況: {'設定済み' if webhook_url else '未設定'}")
        
        if not webhook_url:
            self.logger.info("Slack Webhook URLが設定されていません")
            return
            
        if available_count == 0:
            self.logger.info("空きがないためSlack通知を送信しません")
            return
            
        try:
            webhook_url = self.config["notification"]["slack_webhook_url"]
            self.logger.info("Slack通知を送信します")
            
            # 空き状況の詳細を作成
            available_slots = []
            for slot in slots_info:
                if slot.get("status") == "available":
                    # 時間から改行文字を除去してクリーンアップ
                    clean_time = slot['time'].replace('\n', '').replace('\r', '').strip()
                    # 日付と時間を組み合わせて表示
                    available_slots.append(f"● {slot['date']} {clean_time}")
            
            # 日時で昇順ソート
            available_slots.sort()
            
            # Block Kitを使用したSlack通知
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🏸 バドミントン空き情報",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*施設:*\n戸田市スポーツセンター 第1競技場1/8面\n\n*空き件数:*\n{available_count}件"
                    },
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*確認日時:*\n{(datetime.now(timezone(timedelta(hours=9)))).strftime('%Y-%m-%d %H:%M:%S')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": "*期間:*\n1週間"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*空き状況:*\n{chr(10).join(available_slots[:10])}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{self.base_url}|戸田市施設予約システム>"
                    }
                }
            ]
            
            payload = {"blocks": blocks}
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.logger.info(f"Slack通知を送信しました: {available_count}件の空き情報")
            else:
                self.logger.error(f"Slack通知の送信に失敗しました: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Slack通知でエラーが発生しました: {e}")

    def send_slack_error_notification(self, error_message):
        """エラー時のSlack通知を送信します"""
        if not self.config.get("notification", {}).get("notify_on_error", False):
            return
            
        if not self.config.get("notification", {}).get("slack_webhook_url"):
            return
            
        try:
            webhook_url = self.config["notification"]["slack_webhook_url"]
            
            message = f""":warning: 戸田市施設予約システム エラー通知
エラー内容:
{error_message}
発生時刻:
{(datetime.now(timezone(timedelta(hours=9)))).strftime('%Y-%m-%d %H:%M:%S')}

<{self.base_url}|戸田市施設予約システム>
"""
            
            payload = {"text": message}
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("エラー通知をSlackに送信しました")
            else:
                self.logger.error(f"エラー通知の送信に失敗しました: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"エラー通知でエラーが発生しました: {e}")

    def print_results(self, data):
        """結果を表示します"""
        if not data:
            print("😔 データが取得できませんでした")
            return
            
        print("=" * 60)
        print("🏸 戸田市スポーツセンター バドミントン空き情報")
        print("=" * 60)
        print(f"施設: 戸田市スポーツセンター 第1競技場1/8面")
        print(f"確認日時: {(datetime.now(timezone(timedelta(hours=9)))).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"期間: 1週間")
        print("-" * 60)
        print()
        
        # 日付ごとにグループ化
        date_groups = {}
        for item in data:
            date = item['date']
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(item)
        
        # 日付順にソート
        sorted_dates = sorted(date_groups.keys())
        
        available_count = 0
        
        for date in sorted_dates:
            print(f"📅 {date}")
            slots = date_groups[date]
            slots.sort(key=lambda x: x['time'])
            
            for slot in slots:
                time = slot['time']
                status_text = slot['status_text']
                status_emoji = "✅" if slot['status'] == 'available' else "❌"
                
                print(f"  {time} {status_emoji} {status_text}")
                
                if slot['status'] == 'available':
                    available_count += 1
            
            print()
        
        print("-" * 60)
        
        if available_count > 0:
            print(f"🎉 空きが見つかりました: {available_count}件")
            # Slack通知を送信
            self.send_slack_notification(available_count, data)
        else:
            print("😔 空きが見つかりませんでした")
        
        print("=" * 60)

    def save_results(self, data):
        """結果をJSONファイルに保存します"""
        if not data:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/toda_results_{timestamp}.json"
        
        result = {
            "facility": "戸田市スポーツセンター 第1競技場1/8面",
            "sport": "バドミントン",
            "check_date": (datetime.now(timezone(timedelta(hours=9)))).strftime("%Y-%m-%d %H:%M:%S"),
            "period": "1週間",
            "total_slots": len(data),
            "slots": data
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            self.logger.info(f"結果を保存しました: {filename}")
        except Exception as e:
            self.logger.error(f"結果の保存でエラーが発生しました: {e}")

    async def test_network_connection(self):
        """ネットワーク接続をテストします"""
        import socket
        import requests
        import os
        
        self.logger.info("ネットワーク接続をテスト中...")
        
        # Docker環境の診断
        self.logger.info("=== Docker環境診断 ===")
        self.logger.info(f"コンテナ内のホスト名: {os.uname().nodename}")
        self.logger.info(f"コンテナ内のユーザー: {os.getuid()}")
        
        # ネットワーク設定の確認
        try:
            with open('/etc/resolv.conf', 'r') as f:
                dns_config = f.read()
                self.logger.info(f"DNS設定:\n{dns_config}")
        except Exception as e:
            self.logger.warning(f"DNS設定の確認でエラー: {e}")
        
        # サーバー状態を確認
        self.logger.info("戸田市サーバーの状態を確認中...")

        # DNS解決テスト
        try:
            hostname = "yoyaku.city.toda.saitama.jp"
            ip = socket.gethostbyname(hostname)
            self.logger.info(f"DNS解決成功: {hostname} -> {ip}")

            # IPアドレスが0.0.0.0の場合は警告
            if ip == "0.0.0.0":
                self.logger.warning("⚠️  IPアドレスが0.0.0.0です。DNS設定に問題がある可能性があります。")
                return False

        except Exception as e:
            self.logger.error(f"DNS解決失敗: {e}")
            return False

        # HTTP接続テスト
        try:
            self.logger.info(f"HTTP接続テスト中: {self.base_url}")
            response = requests.get(self.base_url, timeout=30, verify=True)
            self.logger.info(f"HTTP接続テスト成功: ステータスコード {response.status_code}")
            return True
        except requests.exceptions.SSLError as e:
            self.logger.error(f"SSL証明書エラー: {e}")
            # SSL証明書エラーの場合は、検証を無効にして再試行
            try:
                response = requests.get(self.base_url, timeout=30, verify=False)
                self.logger.info(f"SSL検証を無効にしてHTTP接続テスト成功: ステータスコード {response.status_code}")
                return True
            except Exception as e2:
                self.logger.error(f"SSL検証無効でもHTTP接続テスト失敗: {e2}")
                return False
        except requests.exceptions.ConnectTimeout as e:
            self.logger.error(f"接続タイムアウト: {e}")
            self.logger.info("サーバーが重い可能性があります。処理を続行します。")
            return True  # タイムアウトでも続行
        except Exception as e:
            self.logger.error(f"HTTP接続テスト失敗: {e}")
            self.logger.info("接続に問題がありますが、処理を続行します。")
            return True  # エラーでも続行

    async def run(self):
        """メイン実行関数"""
        self.logger.info("=== 戸田市施設予約システム チェッカー開始 ===")

        # ネットワーク接続テスト（オプション）
        try:
            if not await self.test_network_connection():
                self.logger.warning("ネットワーク接続に問題がありますが、処理を続行します。")
        except Exception as e:
            self.logger.warning(f"ネットワーク接続テストでエラーが発生しましたが、処理を続行します: {e}")

        # 日本時間で現在時刻を取得
        jst_now = datetime.now(timezone(timedelta(hours=9)))
        current_hour = jst_now.hour

        # 9:00~23:59以外の場合は処理をスキップ
        if current_hour < 9 or current_hour >= 24:
            self.logger.info(f"現在時刻（JST）: {jst_now.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info("営業時間外（9:00~23:59以外）のため処理をスキップします")
            return
        
        self.logger.info(f"現在時刻（JST）: {jst_now.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor'
                    ]
                )
                page = await browser.new_page()

                # ページのタイムアウト設定
                page.set_default_timeout(120000)  # 120秒に延長
                page.set_default_navigation_timeout(120000)  # 120秒に延長

                # ページにアクセス（タイムアウト時間を延長）
                self.logger.info(f"予約システムにアクセス中: {self.base_url}")
                try:
                                        # ネットワーク接続をテスト
                    self.logger.info("ネットワーク接続をテスト中...")
                    response = await page.goto(self.base_url, timeout=120000)  # 120秒に延長
                    self.logger.info(f"HTTPステータスコード: {response.status}")
                    
                    if response.status != 200:
                        self.logger.warning(f"HTTPステータスコードが異常です: {response.status}")
                    
                    await page.wait_for_load_state('networkidle', timeout=120000)
                    self.logger.info("ページの読み込みが完了しました")
                except Exception as e:
                    self.logger.warning(f"ページ読み込みでタイムアウトが発生しました: {e}")
                    self.logger.info("DOMContentLoaded状態で続行を試みます")
                    try:
                        await page.wait_for_load_state('domcontentloaded', timeout=30000)
                        self.logger.info("DOMContentLoaded状態で読み込み完了")
                    except Exception as e2:
                        self.logger.error(f"DOMContentLoadedでもタイムアウトが発生しました: {e2}")
                        raise

                # 検索条件を設定
                await self.set_search_conditions(page)
                self.logger.info("検索条件の設定が完了しました")
                
                # 空き状況データを取得
                self.logger.info("空き状況データを取得中...")
                data = await self.get_availability_data(page)
                self.logger.info(f"空き状況データを取得しました: {len(data)}件")
                
                # 結果を表示
                self.print_results(data)
                
                await browser.close()

        except Exception as e:
            self.logger.error(f"実行中にエラーが発生しました: {e}")
            import traceback
            self.logger.error(f"詳細なエラー情報: {traceback.format_exc()}")
            self.send_slack_error_notification(str(e))
            raise

async def main():
    """メイン関数"""
    checker = TodaPlaywrightChecker()
    await checker.run()

if __name__ == "__main__":
    asyncio.run(main()) 
