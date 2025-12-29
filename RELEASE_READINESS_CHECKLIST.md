## ReadyTrader — Release Readiness Checklist

This checklist is meant to be used before any public release or major announcement. It focuses on trust, safety, and reproducibility.

### 1) Scope & versioning
- [ ] **Define release scope** (features included, features explicitly excluded)
- [ ] **Version bump** in `pyproject.toml` (and/or tag strategy documented)
- [ ] **Changelog entry** created (what changed, what broke, what to watch)

### 2) Repo hygiene & governance
- [ ] **License present** (`LICENSE`)
- [ ] **Prominent disclaimer** present (`README.md` + `DISCLAIMER.md`)
- [ ] **Security policy** present (`SECURITY.md`)
- [ ] **Contributing guide** present (`CONTRIBUTING.md`)
- [ ] **CI is required** for PRs (branch protection recommended)
- [ ] **No secrets in repo** (scan git history if needed)

### 3) Build & install reproducibility
- [ ] `requirements.txt` is **runtime-only** and pinned
- [ ] `requirements-dev.txt` exists for **tests + lint + security tooling**
- [ ] `Dockerfile` builds cleanly from scratch (no missing files)
- [ ] `.dockerignore` excludes secrets/tests/CI-only artifacts
- [ ] `python-version` matches `pyproject.toml` (`>=3.12`)

### 4) Documentation completeness (minimum viable trust)
- [ ] **README is accurate** (features, limitations, supported venues, safety model)
- [ ] **Full tool catalog** exists and is up-to-date (`docs/TOOLS.md`)
- [ ] **Configuration template** exists (`env.example`) and matches code
- [ ] **Runbook** exists and is practical (`RUNBOOK.md`)
- [ ] “How to run checks locally” documented (`CONTRIBUTING.md`)

### 5) Safety & live-trading governance
- [ ] **Safe default**: `PAPER_MODE=true` (no live execution by default)
- [ ] **Live gating works**:
  - [ ] `LIVE_TRADING_ENABLED=true` required
  - [ ] `TRADING_HALTED=true` halts execution
  - [ ] Risk disclosure consent required (per process)
- [ ] **Approval mode works**:
  - [ ] `EXECUTION_APPROVAL_MODE=approve_each` returns proposals
  - [ ] replay protection (single-use token) and TTL enforced
- [ ] **Policy engine rules** documented and verified (allowlists/limits)
- [ ] **Signer abstraction** documented (env key / keystore / remote signer)

### 6) Quality gates (must be green)
- [ ] Lint: `ruff check .`
- [ ] Tests: `pytest -q`
- [ ] Security static scan: `bandit -q -r . -c bandit.yaml`
- [ ] Dependency audit: `pip-audit -r requirements.txt`
- [ ] GitHub Actions CI run is green on `main`

### 7) Operator readiness (minimum)
- [ ] `get_health()` returns healthy state in paper mode
- [ ] `get_metrics_snapshot()` returns sane counters/timers after tool usage
- [ ] Websocket streams can be started/stopped without crashing the process
- [ ] Clear troubleshooting steps exist in `RUNBOOK.md`

### 8) Release packaging & distribution
- [ ] Tag release (or document why tags aren’t used yet)
- [ ] GitHub Release notes include:
  - [ ] upgrade steps
  - [ ] breaking changes
  - [ ] safety reminders (paper first)
- [ ] Announcement copy uses “safe claims” (see `docs/POSITIONING.md`)

