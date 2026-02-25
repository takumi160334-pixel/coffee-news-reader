import datetime
import feedparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import base64
from typing import List, Dict, Any

import config

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

class RSSFetcher:
    def __init__(self, urls: List[str]):
        self.urls = urls

    def fetch_recent(self, hours_ago: int = 24) -> List[Dict[str, Any]]:
        """Fetch RSS entries published within the last X hours."""
        news_items = []
        now = datetime.datetime.now(datetime.timezone.utc)
        
        for url in self.urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    published_parsed = entry.get('published_parsed')
                    # Fallback to current time if pubished_parsed is missing or malformed to ensure we still process the article
                    try:
                        if published_parsed:
                            dt = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                        else:
                            dt = now 
                    except (TypeError, ValueError):
                        dt = now
                        
                    if (now - dt).total_seconds() <= hours_ago * 3600:
                        # Try to extract the full summary or description if available
                        content = ""
                        if 'content' in entry and len(entry.content) > 0:
                            content = entry.content[0].value
                        elif 'summary' in entry:
                            content = entry.summary
                            
                        news_items.append({
                            'title': entry.get('title', 'No Title'),
                            'link': entry.get('link', ''),
                            'source': feed.feed.get('title', 'Unknown Source'),
                            'content': content,
                            'type': 'rss'
                        })
            except Exception as e:
                print(f"⚠️ Error fetching from {url}: {e}")
                
        return news_items


class GmailFetcher:
    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.json'):
         self.credentials_file = credentials_file
         self.token_file = token_file
         self.service = self._authenticate()

    def _authenticate(self):
        """Gmail API authentication logic."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"{self.credentials_file} missing. Please download it from Google Cloud Console.")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                # Ensure we strictly run on a standard local port for browser auth
                creds = flow.run_local_server(port=0)
                
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
                
        return build('gmail', 'v1', credentials=creds)

    def fetch_recent_newsletters(self, query: str = "", hours_ago: int = 24) -> List[Dict[str, Any]]:
        """Search Gmail for newsletters matching a query within a timeframe."""
        if not query:
            return []
            
        # Gmail search allows "newer_than:1d"
        # We construct the query
        days = max(1, hours_ago // 24)
        full_query = f"{query} newer_than:{days}d"
        
        news_items = []
        try:
            results = self.service.users().messages().list(userId='me', q=full_query, maxResults=20).execute()
            messages = results.get('messages', [])
            
            for msg in messages:
                try:
                    # Need to fetch the full message payload
                    msg_full = self.service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                    payload = msg_full.get('payload', {})
                    headers = payload.get('headers', [])
                    
                    subject = "Unknown Subject"
                    sender = "Unknown Sender"
                    for header in headers:
                        if header.get('name') == 'Subject':
                            subject = header.get('value')
                        if header.get('name') == 'From':
                            sender = header.get('value')
                            
                    # Attempt to extract body (usually base64 encoded)
                    body = ""
                    parts = payload.get('parts', [])
                    if not parts and payload.get('body', {}).get('data'):
                         # Sometimes there are no parts, just a body structure
                         parts = [payload]
                         
                    for part in parts:
                        if part.get('mimeType') == 'text/plain':
                            data = part.get('body', {}).get('data', '')
                            if data:
                                try:
                                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                                except Exception as decode_err:
                                    print(f"⚠️ Could not decode email body: {decode_err}")
                                    body = "Error decoding email content."
                                break # Prefer plain text over HTML for extraction
                    
                    news_items.append({
                         'title': subject,
                         'link': f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}",
                         'source': sender,
                         'content': body,
                         'type': 'gmail'
                    })
                except Exception as msg_err:
                    print(f"⚠️ Error processing individual Gmail message {msg['id']}: {msg_err}")
                    continue
        except Exception as e:
             print(f"⚠️ Error fetching from Gmail: {e}")
             
        return news_items
