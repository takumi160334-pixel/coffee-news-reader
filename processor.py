import os
from google import genai
from google.genai import types
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import time
import config

# --- Pydantic Schemas for Structured Output ---

class ProcessedArticle(BaseModel):
    index: int = Field(description="The index ID of the original article this refers to.")
    category_id: int = Field(description="The category ID (1-7) that best fits the article. 1 if none fit perfectly.")
    summary: str = Field(description="A concise 2-3 line Japanese summary of the article. Must not contain PII.")

class BatchResult(BaseModel):
    articles: List[ProcessedArticle] = Field(description="List of processed results for the given articles.")

# --- End Schemas ---

class NewsProcessor:
    def __init__(self, api_key: str):
        """Initialize the Gemini client."""
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.5-flash-lite' 

    def process_articles_in_chunks(self, articles: List[Dict[str, Any]], chunk_size: int = 20) -> List[Dict[str, Any]]:
        """Process a list of articles by chunking them to avoid token limits & hallucinations."""
        processed_articles = []
        
        # Split articles into chunks
        chunks = [articles[i:i + chunk_size] for i in range(0, len(articles), chunk_size)]
        total_chunks = len(chunks)
        
        print(f"📦 記事を {total_chunks} 個のバッチ（チャンク）に分割して一括処理します...")
        
        for i, chunk in enumerate(chunks, 1):
            print(f"  ⏳ バッチ {i}/{total_chunks} を処理中 ({len(chunk)} 件)...")
            processed_chunk = self._process_batch_two_pass(chunk)
            processed_articles.extend(processed_chunk)
            
            # API Quota Rate Limiting (15 RPM for free tier)
            if i < total_chunks:
                time.sleep(10) # Safe delay between batches
                
        return processed_articles

    def _process_batch_two_pass(self, chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """The two-pass architecture: 1. Generate Summaries, 2. Double-Check."""
        
        # 1. Prepare the input payload
        input_payload = ""
        for i, article in enumerate(chunk):
            title = article.get('title', '')
            content = article.get('content', '')
            # Truncate very long articles to respect context window and attention
            if len(content) > 1500:
                content = content[:1500] + "...(truncated)"
            
            input_payload += f"--- ARTICLE INDEX: {i} ---\nTITLE: {title}\nCONTENT: {content}\n\n"

        # --------------------------------------------------------------------
        # PASS 1: Initial Translation and Categorization
        # --------------------------------------------------------------------
        pass1_prompt = f"""
        あなたは優秀なニュース編集者です。以下の複数記事を一括で処理してください。
        
        【厳守事項】
        1. 各記事をカテゴリ番号（1〜7）に分類し、2〜3行の日本語で要約してください。
        2. 個人情報保護: 人名、メールアドレス、電話番号などの個人情報(PII)が含まれている場合は、アスタリスク(***)でマスクして絶対に要約に出力しないでください。
        3. 必須: 出力する各JSONデータの `index` には、入力データの「ARTICLE INDEX」の数値を必ずそのまま設定してください。
        
        【記事データ】
        {input_payload}
        """

        print("     -> [Pass 1] 初期翻訳と要約を実行中...")
        pass1_result = self._call_gemini_structured(pass1_prompt, "Pass 1")
        
        if not pass1_result:
            return self._build_fallback_chunk(chunk)

        # --------------------------------------------------------------------
        # PASS 2: Double-Check & Hallucination Prevention
        # --------------------------------------------------------------------
        pass2_prompt = f"""
        あなたは非常に厳格な「監査役（ファクトチェッカー）」です。
        【元データ】と、AIが一時的に作成した【1回目の出力データ】を比較し、間違いを修正してください。
        
        【監査の基準】
        1. 原文にない事実（ハルシネーション）が含まれていないか？あれば削除・修正。
        2. 個人情報(PII)が漏れていないか？あればマスク(***)する。
        3. 翻訳の精度は適切か？
        4. 要約は冗長になっていないか？
        5. 必須: 最終的なJSONデータの `index` には、必ず【元データ】の「ARTICLE INDEX」と一致する数値を設定すること。
        
        これらの基準ですべての要約を審査し、完璧な最終版のJSONデータを作成してください。
        
        【元データ】
        {input_payload}
        
        【1回目の出力データ】
        {pass1_result.model_dump_json()}
        """
        
        print("     -> [Pass 2] 二重監査（ファクトチェック）を実行中...")
        pass2_result = self._call_gemini_structured(pass2_prompt, "Pass 2")
        
        final_result = pass2_result if pass2_result else pass1_result
        
        if final_result:
            processed_chunk, failed_originals = self._merge_results(chunk, final_result)
            
            # --- AUTO-HEALING RECOVERY SYSTEM ---
            if failed_originals:
                print(f"     ⚠️ {len(failed_originals)}件の記事の要約出力が欠損していました。自動復旧（自己修復リカバリー）を開始します...")
                recovered_chunk = self._recover_failed_articles(failed_originals)
                processed_chunk.extend(recovered_chunk)
                
            return processed_chunk
        else:
            return self._build_fallback_chunk(chunk)

    def _call_gemini_structured(self, prompt: str, stage_name: str) -> BatchResult | None:
        """Call Gemini API utilizing Structured Outputs to ensure perfect JSON matching."""
        max_retries = 3
        base_delay = 15

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=config.GEMINI_SYSTEM_PROMPT,
                        temperature=0.1, # Extremely low for deterministic fact-checking
                        response_mime_type="application/json",
                        response_schema=BatchResult,
                    )
                )
                
                # The response.parsed is an instance of the Pydantic schema
                if hasattr(response, 'parsed') and response.parsed:
                    return response.parsed
                else:
                    raise ValueError("Gemini API returned a successful response, but 'parsed' was missing or empty.")
                
            except Exception as e:
                error_msg = str(e)
                print(f"       ⚠️ {stage_name} Error (Attempt {attempt + 1}/{max_retries}): {error_msg}")
                if attempt < max_retries - 1:
                    sleep_time = 65 if "429" in error_msg else base_delay * (attempt + 1)
                    time.sleep(sleep_time)
                else:
                    print(f"       ❌ {stage_name} completely failed after retries.")
                    return None

    def _merge_results(self, original_chunk: List[Dict[str, Any]], batch_result: BatchResult) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Merge the validated JSON summaries back into the original article dictionaries."""
        
        # Create a lookup dictionary from the structured output
        result_lookup = {item.index: item for item in batch_result.articles}
        
        processed_chunk = []
        failed_originals = []
        
        for i, article in enumerate(original_chunk):
            processed_article = dict(article) # Copy
            
            # Find the corresponding processed data by ID
            if i in result_lookup:
                ai_data = result_lookup[i]
                
                # Category logic (1-based to 0-based index)
                cat_idx = ai_data.category_id - 1
                if 0 <= cat_idx < len(config.CATEGORIES):
                    processed_article['category'] = config.CATEGORIES[cat_idx]
                else:
                    processed_article['category'] = config.CATEGORIES[0]
                    
                processed_article['summary'] = ai_data.summary
                processed_chunk.append(processed_article)
            else:
                 # The AI skipped this article somehow (Hallucination loss)
                 failed_originals.append(article)
            
        return processed_chunk, failed_originals

    def _build_fallback_chunk(self, chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Creates dummy data if API catastrophically fails."""
        processed_chunk = []
        for article in chunk:
            processed_article = dict(article)
            processed_article['category'] = config.CATEGORIES[0]
            processed_article['summary'] = "API制限などにより自動要約に失敗しました。"
            processed_chunk.append(processed_article)
        return processed_chunk

    def _recover_failed_articles(self, failed_chunk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """A dedicated auto-healing process for articles completely dropped by Gemini during batching."""
        input_payload = ""
        for i, article in enumerate(failed_chunk):
            title = article.get('title', '')
            content = article.get('content', '')[:1500]
            input_payload += f"--- ARTICLE INDEX: {i} ---\nTITLE: {title}\nCONTENT: {content}\n\n"

        recovery_prompt = f"""
        あなたはニュース要約修復AIです。前回の処理でAIエラーにより欠落した記事の救済を行います。
        
        【厳守事項】
        1. 各記事をカテゴリ番号（1〜7）に分類し、2〜3行の日本語で要約してください。
        2. 個人情報(PII)が含まれる場合はアスタリスク(***)でマスクしてください。
        3. 必須: 出力する各JSONデータの `index` には、必ず「ARTICLE INDEX」の数値を入力してください。
        
        【救済対象データ】
        {input_payload}
        """

        time.sleep(10) # Delay to respect RPM before rapid recovery
        recovery_result = self._call_gemini_structured(recovery_prompt, "Recovery Pass")
        
        if not recovery_result:
            return self._build_fallback_chunk(failed_chunk)
            
        result_lookup = {item.index: item for item in recovery_result.articles}
        recovered_chunk = []
        
        for i, article in enumerate(failed_chunk):
            processed_article = dict(article)
            if i in result_lookup:
                ai_data = result_lookup[i]
                cat_idx = ai_data.category_id - 1
                processed_article['category'] = config.CATEGORIES[cat_idx] if 0 <= cat_idx < len(config.CATEGORIES) else config.CATEGORIES[0]
                processed_article['summary'] = ai_data.summary
            else:
                # Absolute catastrophic failure (failed even on recovery)
                processed_article['category'] = config.CATEGORIES[0]
                processed_article['summary'] = "自動復旧処理（自己修復リカバリー）でも要約に失敗しました。"
            
            recovered_chunk.append(processed_article)
            
        return recovered_chunk
