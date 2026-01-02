import os
from typing import Any, Dict, Optional

import requests


class WebhookManager:
    """
    Handles delivery of notifications to external services like Discord and Telegram.
    """
    
    @staticmethod
    def send_discord_notification(message: str, embed: Optional[Dict[str, Any]] = None):
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            return
            
        payload = {"content": message}
        if embed:
            payload["embeds"] = [embed]
            
        try:
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception: # nosec
            pass # Silent failure for observability

    @staticmethod
    def send_telegram_notification(message: str):
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not bot_token or not chat_id:
            return
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception: # nosec
            pass

    @classmethod
    def notify_approval_required(cls, kind: str, amount: float, symbol: str, request_id: str):
        """
        Send a notification that a trade requires manual approval.
        """
        msg = f"🛡️ **ReadyTrader: Approval Required**\nKind: {kind}\nAmount: {amount}\nSymbol: {symbol}\nRequest ID: `{request_id}`"
        
        # Discord Embed
        embed = {
            "title": "Action Required: Trade Approval",
            "color": 0xFFCC00,
            "fields": [
                {"name": "Kind", "value": kind, "inline": True},
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Amount", "value": str(amount), "inline": True},
                {"name": "Request ID", "value": request_id, "inline": False}
            ],
            "footer": {"text": "ReadyTrader-Stocks Guardian Mode"}
        }
        
        cls.send_discord_notification(msg, embed=embed)
        cls.send_telegram_notification(msg)
