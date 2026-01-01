import os
import time
from typing import Any, Dict, Optional

import requests

# Optional imports for Real APIs
try:
    import tweepy
except ImportError:
    tweepy = None

try:
    import praw
except ImportError:
    praw = None

try:
    from newsapi import NewsApiClient
except ImportError:
    NewsApiClient = None

try:
    import feedparser
except ImportError:
    feedparser = None

def get_market_sentiment() -> str:
    """
    Fetch market sentiment (Fear & Greed) for Stocks.
    """
    try:
        # Using a reliable unofficial endpoint for CNN Fear & Greed index
        # This provides the current value and the human-readable rating.
        url = "https://production.dataviz.cnn.io/index/fearandgreed/static/latest"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        value = data.get("fear_and_greed", {}).get("rating", "Unknown")
        score = data.get("fear_and_greed", {}).get("now", 0.0)
        
        return f"CNN Fear & Greed: {value.upper()} ({round(score, 1)})"
    except Exception as e:
        return f"Market Sentiment: Error fetching CNN Fear & Greed: {str(e)}. (Zero-Mock Policy: No simulated fallback provided)."

def get_market_news() -> str:
    """
    Fetch aggregated equity market news using Alpha Vantage.
    """
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        return "Market News: ALPHAVANTAGE_API_KEY missing. News unavailable."
    
    try:
        # Alpha Vantage News Sentiment endpoint
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={api_key}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'feed' in data:
            headlines = [f"{i+1}. {p['title']} ({p['source']})" for i, p in enumerate(data['feed'][:5])]
            return "Alpha Vantage news:\n" + "\n".join(headlines)
        return "Error: No news found via Alpha Vantage."
    except Exception as e:
        return f"Error fetching news: {str(e)}"

def fetch_rss_news(symbol: str = "") -> str:
    """
    Fetch free market news from RSS feeds.
    """
    if not feedparser:
        return "Error: feedparser library not installed. Cannot fetch RSS news."
    
    feeds = [
        ("MarketWatch", "https://www.marketwatch.com/rss/marketupdate"),
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex")
    ]
    
    all_headlines = []
    
    for name, url in feeds:
        try:
            feed = feedparser.parse(url)
            # Take top 3 from each
            count = 0
            for entry in feed.entries:
                if count >= 3:
                    break
                # If symbol is provided, check if it's in the title/summary (case-insensitive)
                if symbol and symbol.lower() not in entry.title.lower() and symbol.lower() not in (getattr(entry, 'summary', '')).lower():
                    continue
                
                all_headlines.append(f"{entry.title} ({name})")
                count += 1
        except Exception as e:
            all_headlines.append(f"Error fetching {name} feed: {str(e)}")
            
    if not all_headlines:
        return f"No RSS news found matching '{symbol}' or feeds unavailable."
        
    return "Market News (Free RSS):\n" + "\n".join([f"{i+1}. {h}" for i, h in enumerate(all_headlines[:6])])


class SentimentCache:
    def __init__(self, ttl: int = 3600):
        self.cache = {}
        self.ttl = ttl

    def get(self, symbol: str) -> Optional[Dict[str, Any]]:
        if symbol in self.cache:
            entry = self.cache[symbol]
            if time.time() - entry['time'] < self.ttl:
                return entry
        return None

    def set(self, symbol: str, score: float, rationales: list[str]):
        self.cache[symbol] = {
            'time': time.time(),
            "score": round(score, 2),
            "rationales": rationales,
            "explainability_string": f"AI Sentiment of {round(score, 2)} based on: {'; '.join(rationales)}"
        }

_sentiment_cache = SentimentCache()

def get_cached_sentiment_score(symbol: str) -> float:
    """Return cached sentiment score or 0.0 if missing."""
    entry = _sentiment_cache.get(symbol)
    if entry:
        return entry['score']
    return 0.0

def analyze_social_sentiment(symbol: str) -> str:
    """
    Analyze social sentiment using Tweepy (X) or PRAW (Reddit) if configured.
    """
    # Check cache first (optional, but good for speed)
    # But usually this tool is called explicitly to Refresh.
    # Let's refresh every time this tool is CALLED, but get_cached_sentiment_score uses what's there.
    
    score = 0.0
    rationales = []
    
    # 1. Twitter / X Analysis
    twitter_bearer = os.getenv("TWITTER_BEARER_TOKEN")
    twitter_result = "Twitter: Not Configured."
    
    if twitter_bearer and tweepy:
        try:
            client = tweepy.Client(bearer_token=twitter_bearer)
            # Simple search for recent tweets (read-only)
            query = f"{symbol} -is:retweet lang:en"
            tweets = client.search_recent_tweets(query=query, max_results=10)
            if tweets.data:
                texts = [t.text for t in tweets.data]
                preview = " | ".join([t[:50] + "..." for t in texts[:2]])
                twitter_result = f"Twitter: Found {len(texts)} recent tweets. Preview: {preview}"
                rationales.append(f"Twitter volume alert for {symbol}")
                score += 0.2
            else:
                twitter_result = "Twitter: No recent tweets found."
        except Exception as e:
            twitter_result = f"Twitter Error: {str(e)}"

    # 2. Reddit Analysis
    reddit_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_secret = os.getenv("REDDIT_CLIENT_SECRET")
    reddit_result = "Reddit: Not Configured."
    
    if reddit_id and reddit_secret and praw:
        try:
            reddit = praw.Reddit(
                client_id=reddit_id,
                client_secret=reddit_secret,
                user_agent="readytrader_stocks/1.0"
            )
            # Search r/stocks or r/wallstreetbets
            subreddit = reddit.subreddit("stocks+wallstreetbets")
            posts = subreddit.search(symbol, limit=5, time_filter="day")
            titles = [p.title for p in posts]
            if titles:
                preview = " | ".join(titles[:2])
                reddit_result = f"Reddit: Found {len(titles)} posts. Preview: {preview}"
                rationales.append("Reddit active discussion in r/stocks")
                score += 0.2
            else:
                reddit_result = "Reddit: No recent posts found."
        except Exception as e:
            reddit_result = f"Reddit Error: {str(e)}"
            
    # Combine
    final_output = f"{twitter_result}\n{reddit_result}"
    
    if "Not Configured" in twitter_result and "Not Configured" in reddit_result:
        return "Social Sentiment: No providers configured (Twitter/Reddit API keys missing). (Zero-Mock Policy)."
    
    # Update Cache
    _sentiment_cache.set(symbol, score, rationales)
    
    return final_output


def fetch_financial_news(symbol: str) -> str:
    """
    Fetch financial news using NewsAPI.
    """
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key or not NewsApiClient:
         return "Financial News: NEWSAPI_KEY missing or NewsApiClient not installed. (Zero-Mock Policy)."
         
    try:
        newsapi = NewsApiClient(api_key=api_key)
        # Search for symbol + stocks or finance
        articles = newsapi.get_everything(q=f"{symbol} stock", language='en', sort_by='relevancy', page_size=3)
        
        if articles['status'] == 'ok' and articles['articles']:
            headlines = [f"{i+1}. {a['title']} ({a['source']['name']})" for i, a in enumerate(articles['articles'])]
            return "Financial Headlines (NewsAPI):\n" + "\n".join(headlines)
        return "NewsAPI: No articles found."
    except Exception as e:
        return f"NewsAPI Error: {str(e)}"

