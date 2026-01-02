# Custody & API Management (ReadyTrader-Stocks)

ReadyTrader-Stocks does not manage private keys or "custody" in the crypto sense. Instead, it manages access to your retail brokerage account via API keys.

## 🛡️ API Key Security
When operating in live mode, ReadyTrader-Stocks uses your brokerage credentials to execute trades. Protecting these keys is your primary security responsibility.

### 1. Minimal Permissions
Most modern brokerages (Alpaca, Tradier) allow you to create API keys with specific scopes. 
- **Required**: Trade execution, Account data (read-only).
- **Prohibited**: Account funding, Withdrawals, Password changes.

### 2. Secret Management
- **Never** commit your `.env` file to version control (GitHub/GitLab).
- Use a dedicated secrets manager (e.g., AWS Secrets Manager, GitHub Secrets) if deploying to the cloud.

---

## 🤝 Human-in-the-Loop (HITL)
For maximum safety, ReadyTrader-Stocks supports a "Guardian" mode where the agent can propose a trade, but a human must click a button or send a command to confirm it.

To enable this, set your environment variable:
```bash
EXECUTION_APPROVAL_MODE=approve_each
```

This ensures that while the AI has the "Intelligence" to find opportunities, you retain the final "Hands" on the actual capital.
