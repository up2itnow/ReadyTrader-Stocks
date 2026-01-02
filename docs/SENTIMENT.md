# Market Intelligence & Sentiment Guide (ReadyTrader-Stocks)

ReadyTrader-Stocks empowers AI agents with "Eyes" (intelligence) to navigate the stock market. This document explains how to configure and use the various sentiment and news feeds.

## 🌟 Overview of Sentiment Sources

| Source | Target | Cost | Required Credentials | 
| :--- | :--- | :--- | :--- |
| **RSS Market News** | General | Free | None (MarketWatch, Yahoo Finance) |
| **Fear & Greed Index** | Market | Free | None |
| **Reddit** | Social | Free | Client ID + Secret (/r/wallstreetbets) |
| **NewsAPI** | Financial | Free (Trial) | API Key (Bloomberg, Reuters) |

---

## 🛠️ Configuration Instructions

### 1. Free News & Sentiment
Work **out-of-the-box**. Agents use `fetch_rss_news` and `get_market_sentiment` without any keys.

### 2. Reddit Sentiment (High Alpha)
Great for detecting retail buzz and "meme stock" momentum.
1.  Go to [Reddit App Preferences](https://www.reddit.com/prefs/apps).
2.  Click "Create another app..." -> select **script**.
3.  Add credentials to `.env`:
    ```bash
    REDDIT_CLIENT_ID=your_id
    REDDIT_CLIENT_SECRET=your_secret
    ```

### 3. Financial News (Institutional)
For high-signal news from major financial outlets via NewsAPI.
1.  Get a key at [NewsAPI.org](https://newsapi.org/).
2.  Add to `.env`:
    ```bash
    NEWSAPI_KEY=your_key
    ```

---

## 🤖 Agent Tool Reference

- `fetch_rss_news(symbol="")`: Aggregates public RSS feeds. Best for general context.
- `get_market_sentiment()`: Returns the Stock Market Fear & Greed Index.
- `get_social_sentiment(symbol)`: Queries Reddit for specific stock discussions.
- `get_financial_news(symbol)`: Queries high-tier publications (Bloomberg, Reuters).
