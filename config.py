import os
from typing import List, Dict

# The 7 specific categories for coffee news grouping
CATEGORIES: List[str] = [
    "1. 今週の要チェック記事（Top News）",
    "2. 市況・産地・トレード（Market & Origin）",
    "3. カフェ経営・リテール・マーケティング（Retail & Business）",
    "4. 焙煎・抽出・サイエンス（Roasting & Science）",
    "5. テクニカル・機材（Tech & Gear）",
    "6. サステナビリティ・環境・倫理（Sustainability）",
    "7. 競技会・イベント・カルチャー（Events & Culture）"
]

# RSS Feeds to monitor
# Users can add or remove raw feed URLs here
RSS_FEEDS: List[str] = [
    'https://perfectdailygrind.com/feed/',
    'https://dailycoffeenews.com/feed/',
    'https://sprudge.com/feed/'
]

# Gmail settings
# We search for emails matching this query
# e.g., "from:newsletter@example.com OR from:coffee-digest@sample.com"
GMAIL_SEARCH_QUERY: str = ""

# To identify who to send the email to.
SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")  # Add the email you will send FROM
RECEIVER_EMAIL: str = os.getenv("RECEIVER_EMAIL", "")  # Add the email you will send TO

# Gemini System Instructions
GEMINI_SYSTEM_PROMPT = f"""
あなたはプロのコーヒー業界専門ジャーナリスト兼アシスタントです。
与えられた記事（英語または日本語）を読み込み、日本語で簡潔に要約し、以下の7つのテーマのいずれかに最も適した「番号」だけで回答してください。

テーマ:
{chr(10).join(CATEGORIES)}
"""
