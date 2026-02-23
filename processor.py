import os
from google import genai
from google.genai import types
from typing import Dict, Any
import time
import config

class NewsProcessor:
    def __init__(self, api_key: str):
        """Initialize the Gemini client."""
        # Using the new google-genai SDK 
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-1.5-flash'  # Use 1.5-flash for generous 1500 RPD free tier limit

    def process_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize and summarize a single article."""
        title = article.get('title', '')
        content = article.get('content', '')
        
        # If content is too long, truncate it to save tokens (first ~3000 chars)
        if len(content) > 3000:
            content = content[:3000] + "..."

        prompt = f"""
        以下のコーヒーに関するニュース記事を分析してください。

        【タイトル】
        {title}

        【本文】
        {content}

        【指示】
        1. この記事の内容を日本語で2〜3行（最大150文字程度）で要約してください。
        2. この記事は、指定された7つのテーマのうちどれに最も適していますか？最も適したテーマの「番号（1〜7の半角数字）」だけで答えてください。
        
        【出力フォーマット】
        (テーマの番号)
        (要約テキスト)
        
        例:
        4
        新しい焙煎機の熱風制御システムが発表されました。これにより焙煎のプロファイルがより精密になり、特に浅煎りでの風味が向上すると期待されています。
        """

        max_retries = 3
        base_delay = 35 # Google's rate limit often requires at least a 30-second wait

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=config.GEMINI_SYSTEM_PROMPT,
                        temperature=0.2, # Low temperature for more deterministic categorization
                    )
                )
                
                result_text = response.text.strip().split("\n")
                
                category_index = 0  # Default to 0 (Uncategorized if fails)
                summary = "要約に失敗しました。"
                
                if len(result_text) >= 1:
                    # Try to parse the first line as a number between 1 and 7
                    try:
                        cat_num = int(result_text[0].strip())
                        if 1 <= cat_num <= 7:
                            # 0-indexed for our config list
                            category_index = cat_num - 1 
                    except ValueError:
                        print(f"Failed to parse category from: {result_text[0]}")
                        
                if len(result_text) >= 2:
                    # Join the rest of the lines as the summary
                    summary = "\n".join(result_text[1:]).strip()
                    
                # Add processed data to the article dict
                article['category'] = config.CATEGORIES[category_index]
                article['summary'] = summary
                
                return article
                
            except Exception as e:
                print(f"⚠️ Gemini processing error for '{title}' (Attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (attempt + 1) # 35s, 70s...
                    print(f"   API制限に到達しました。{sleep_time}秒 待機してから再試行します...")
                    time.sleep(sleep_time)
                else:
                    print(f"❌ Gemini processing failed after {max_retries} attempts.")
                    
        # Fallback return if all retries fail
        article['category'] = config.CATEGORIES[0] # Default to top news
        article['summary'] = "Gemini APIエラーのため要約できませんでした。"
        return article
