import base64
from email.message import EmailMessage
from typing import List, Dict, Any
from googleapiclient.discovery import build
import config

class EmailNotifier:
    def __init__(self, gmail_service):
        self.service = gmail_service

    def format_newsletter(self, articles: List[Dict[str, Any]], is_weekly: bool = False) -> str:
        """Format the categorized articles into an HTML email body."""
        title = "☕ Weekly Coffee Digest" if is_weekly else "☕ Daily Coffee News"
        
        # Group articles by category
        grouped_articles = {category: [] for category in config.CATEGORIES}
        for article in articles:
            # Fallback if category is missing
            cat = article.get('category', config.CATEGORIES[0])
            if cat in grouped_articles:
                grouped_articles[cat].append(article)
            else:
                grouped_articles[config.CATEGORIES[0]].append(article)
                
        # Build HTML
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #4a3b32; border-bottom: 2px solid #8b7355; padding-bottom: 10px; }}
                h2 {{ color: #8b7355; margin-top: 30px; font-size: 1.2em; border-left: 4px solid #d2b48c; padding-left: 10px; }}
                .article {{ margin-bottom: 25px; background: #fff8f0; padding: 15px; border-radius: 8px; }}
                .article-title {{ font-size: 1.1em; font-weight: bold; margin-bottom: 5px; }}
                .article-title a {{ color: #b87333; text-decoration: none; }}
                .article-source {{ font-size: 0.8em; color: #888; margin-bottom: 10px; display: inline-block; background: #eee; padding: 2px 6px; border-radius: 4px; }}
                .article-summary {{ font-size: 0.95em; }}
                .footer {{ margin-top: 40px; font-size: 0.8em; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            <p>おはようございます！最新のコーヒーニュースをお届けします。</p>
        """

        has_news = False
        for category in config.CATEGORIES:
            cat_articles = grouped_articles[category]
            if not cat_articles:
                continue
                
            has_news = True
            html += f"<h2>{category}</h2>"
            
            for article in cat_articles:
                html += f"""
                <div class="article">
                    <div class="article-title">
                        <a href="{article['link']}">{article['title']}</a>
                    </div>
                    <span class="article-source">{article['source']}</span>
                    <div class="article-summary">
                        {article['summary'].replace(chr(10), '<br>')}
                    </div>
                </div>
                """
                
        if not has_news:
             html += "<p>本日は新しいニュースがありませんでした。</p>"
             
        html += """
            <div class="footer">
                Automated by Gemini AI & Antigravity
            </div>
        </body>
        </html>
        """
        
        return html

    def send_email(self, subject: str, html_content: str, is_dry_run: bool = False):
        """Send the formatted email using the Gmail API."""
        if not config.SENDER_EMAIL or not config.RECEIVER_EMAIL:
             print("⚠️ Sender or Receiver email is not set in config/env variables.")
             if not is_dry_run:
                  return

        message = EmailMessage()
        message.set_content("HTML対応のメールクライアントでご覧ください。")
        message.add_alternative(html_content, subtype='html')
        
        message['To'] = config.RECEIVER_EMAIL
        message['From'] = config.SENDER_EMAIL
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        if is_dry_run:
            print(f"\n[DRY RUN] Would send an email with subject: '{subject}'")
            print(f"[DRY RUN] To: {config.RECEIVER_EMAIL}")
            return
            
        try:
            send_message = self.service.users().messages().send(userId="me", body=create_message).execute()
            print(f"✅ ニュースレターを送信しました！ Message Id: {send_message['id']}")
        except Exception as e:
            print(f"❌ メール送信中にエラーが発生しました: {e}")
