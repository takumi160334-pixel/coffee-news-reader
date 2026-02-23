import sys
import io

# Force UTF-8 for Windows terminals to support emojis
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import argparse
from dotenv import load_dotenv

import config
from fetchers import RSSFetcher, GmailFetcher
from processor import NewsProcessor
from notifier import EmailNotifier
import time

def main():
    # Setup Argument Parser
    parser = argparse.ArgumentParser(description="Coffee News Aggregator")
    parser.add_argument("--dry-run", action="store_true", help="Run without sending emails.")
    parser.add_argument("--weekly", action="store_true", help="Run in weekly mode (fetches last 7 days).")
    args = parser.parse_args()

    # Load environment variables (.env file)
    load_dotenv()
    
    # 1. Check API Keys and Config
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
         print("❌ GEMINI_API_KEY が設定されていません。'.env' ファイルを作成して設定してください。")
         sys.exit(1)
         
    if not config.SENDER_EMAIL or not config.RECEIVER_EMAIL:
         # Fallbacks for testing
         config.SENDER_EMAIL = os.getenv("RECEIVER_EMAIL", "you@example.com")
         config.RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "you@example.com")
         print("⚠️ 送信先/送信元のメールアドレスが未設定です。デモ用にダミーをセットします。")

    print("="*50)
    print("☕ コーヒーニュース 自動収集システム 起動")
    print("="*50)
    
    hours_to_fetch = 24 * 7 if args.weekly else 24
    
    # 2. Fetch News
    print(f"\n📥 1. ニュースを受信中... ({hours_to_fetch}時間以内)")
    all_articles = []
    
    rss_fetcher = RSSFetcher(config.RSS_FEEDS)
    rss_articles = rss_fetcher.fetch_recent(hours_ago=hours_to_fetch)
    print(f"  - RSSから {len(rss_articles)} 件の記事を見つけました。")
    all_articles.extend(rss_articles)
    
    if config.GMAIL_SEARCH_QUERY:
         print("  - Gmailからのニュースレターを検索しています...")
         try:
              gmail_fetcher = GmailFetcher()
              gmail_articles = gmail_fetcher.fetch_recent_newsletters(query=config.GMAIL_SEARCH_QUERY, hours_ago=hours_to_fetch)
              print(f"  - Gmailから {len(gmail_articles)} 件のニュースレターを見つけました。")
              all_articles.extend(gmail_articles)
         except Exception as e:
              print(f"  - Gmailの連携をスキップしました (理由は後述の可能性があります: {e})")
              
    if not all_articles:
         print("\n✅ 新しいニュースはありませんでした。終了します。")
         sys.exit(0)
         
    # 3. Process with Gemini
    print(f"\n🧠 2. Gemini AI で記事の要約と分類を開始します... ({len(all_articles)}件)")
    processor = NewsProcessor(api_key=api_key)
    processed_articles = []
    
    for i, article in enumerate(all_articles, 1):
         print(f"  [{i}/{len(all_articles)}] {article['title']}")
         processed = processor.process_article(article)
         processed_articles.append(processed)
         
         # Google Gemini API Free Tier has a limit of 15 Requests Per Minute (RPM)
         if i < len(all_articles):
              time.sleep(6) # 60 seconds / 10 requests = 6 seconds per request. Very safe margin.
         
    # 4. Format and Send Email
    print("\n📧 3. ニュースレターを作成し送信します...")
    try:
         # Initialize Gmail service solely for sending using the fetcher's auth
         gmail_service = GmailFetcher().service
         notifier = EmailNotifier(gmail_service)
         
         html_content = notifier.format_newsletter(processed_articles, is_weekly=args.weekly)
         
         subject = "☕ 【Weekly】コーヒーニュース まとめ" if args.weekly else "☕ 【Daily】今日のコーヒーニュース"
         
         if args.dry_run:
              print("\n=== DRY RUN MODE: メールの内容をHTMLファイルとして保存します ===")
              with open("dry_run_output.html", "w", encoding="utf-8") as f:
                   f.write(html_content)
              print(f"内容を 'dry_run_output.html' に保存しました。ブラウザで開いて確認できます。")
         
         notifier.send_email(subject, html_content, is_dry_run=args.dry_run)
         
    except Exception as e:
         print(f"❌ メールの作成または送信に失敗しました: {e}")
         sys.exit(1)

    print("\n✅ すべての処理が完了しました！")

if __name__ == "__main__":
    main()
