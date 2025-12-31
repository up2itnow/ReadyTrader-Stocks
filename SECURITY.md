## Security Policy

### Reporting a Vulnerability
If you believe you have found a security vulnerability, **do not** open a public issue.

Please report details privately with:
- **Description** of the issue
- **Reproduction steps**
- **Impact** assessment
- Any relevant **logs** or **screenshots** (redact secrets)

### Scope Notes
- This project can be configured for **live trading** (`PAPER_MODE=false`). Keep API keys and secrets out of source control.
- This project uses a **credential provider abstraction**; prefer environment-based or vault-based secrets over raw credentials in code.
- For live trading deployments, review `docs/THREAT_MODEL.md` and follow least-privilege patterns.

### Secret scanning guidance
- See `.github/secret-scanning.md` for recommended GitHub settings and local hygiene.

