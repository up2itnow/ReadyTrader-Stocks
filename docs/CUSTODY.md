## Key Custody & Rotation (Phase 5)

This document describes recommended custody patterns for ReadyTrader-Crypto when operating in live mode.

### CEX API keys (least privilege)
- Create **trade-only** keys when possible
- Disable withdrawal permissions
- Restrict IPs (if your exchange supports it)
- Rotate regularly and immediately upon suspicion

### EVM signing options

#### 1) `SIGNER_TYPE=env_private_key` (dev only)
- Uses `PRIVATE_KEY` in the environment.
- Fast for local testing, **not recommended** for production.

#### 2) `SIGNER_TYPE=keystore` (baseline production)
- Uses `KEYSTORE_PATH` + `KEYSTORE_PASSWORD`.
- Keeps key encrypted at rest; still protect the passphrase.

#### 3) `SIGNER_TYPE=remote` (enterprise-friendly)
- Uses `SIGNER_REMOTE_URL` to sign via HTTP.
- Recommended for HSM/KMS-backed signing proxies.
- ReadyTrader-Crypto includes explicit `intent` in signing requests (Phase 5) to enable safer signer-side policy.

### Defense in depth
Use both layers when possible:
- **PolicyEngine** allowlists:
  - `ALLOW_SIGNER_ADDRESSES`
  - signer-intent guardrails: `ALLOW_SIGN_CHAIN_IDS`, `ALLOW_SIGN_TO_ADDRESSES`, `MAX_SIGN_*`
- **Signer policy wrapper** (local, defense-in-depth):
  - `SIGNER_POLICY_ENABLED=true`
  - `SIGNER_ALLOWED_CHAIN_IDS`, `SIGNER_ALLOWED_TO_ADDRESSES`, `SIGNER_MAX_*`

### Rotation procedure (high level)
- Set `TRADING_HALTED=true`
- Rotate secrets (CEX keys / keystore / signer endpoint)
- Restart the container/service to ensure in-memory state is reset
- Validate with:
  - `get_health()`
  - `get_metrics_snapshot()`
  - small paper-mode dry run (if applicable)
- Re-enable trading only after controlled validation

