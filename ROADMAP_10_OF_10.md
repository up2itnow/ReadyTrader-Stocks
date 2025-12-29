## ReadyTrader — Roadmap to “10/10” across Professionalism, Docs, Usability, Marketability, Feature Depth

This roadmap is intentionally ambitious. The goal is to turn ReadyTrader from “high-quality OSS MCP trading server” into a **trusted, distribution-grade** product that is safe to operate and easy to adopt.

### Scoring rubric (what “10/10” means)
- **Professionalism**: reproducible builds, clean packaging, strong governance, stable APIs, thoughtful architecture, no foot-guns.
- **Docs**: complete, accurate, and easy to navigate; includes tool catalog, configuration, runbooks, and examples.
- **Usability**: minimal setup, sensible defaults, operator-friendly controls, clear error messages, fast feedback loops.
- **Marketability**: strong differentiation with credible claims; polished messaging; easy to demo.
- **Feature depth**: robust execution lifecycle, broad exchange coverage, high-quality market data, and secure custody patterns.

---

## Phase 0 — Distribution polish (1–2 days)
**Objective**: Make the repo feel “ship-ready” and reduce adoption friction.

Deliverables:
- Split deps: runtime vs dev (`requirements.txt` + `requirements-dev.txt`)
- CI installs dev deps deterministically and audits runtime deps
- Add `env.example` and keep it synced with code
- Add **complete tool catalog** docs (`docs/TOOLS.md`) and link from README
- Tighten Docker build context (`.dockerignore`) and align Python version
- Add basic thread-safety for in-memory stores used by websocket threads

Acceptance criteria:
- Fresh clone → `docker build` succeeds
- Fresh clone → `pip install -r requirements-dev.txt` + checks pass
- README points to a complete tool catalog and config template

---

## Phase 1 — Reliability & operational confidence (3–7 days)
**Objective**: Make ReadyTrader stable under long-running workloads and multi-tool concurrency.

Deliverables:
- Concurrency hardening: locks / thread-safe stores / bounded queues
- Persistent option for critical safety state (optional; still safe-by-default):
  - approvals/proposals
  - idempotency keys
  - audit log of executions (paper + live)
- Better “operator feedback”:
  - clearer health breakdown
  - error codes for major subsystems (marketdata, execution, signer, policy)

Acceptance criteria:
- Soak test: websocket streams + repeated tool calls for 1–4 hours without memory growth or crashes
- Deterministic failure behavior: reconnection backoff, graceful stop/start

---

## Phase 2 — Exchange breadth & execution depth (1–3 weeks)
**Objective**: Be best-in-class among “MCP trading connectors”.

Deliverables:
- Broaden CCXT venue presets + capabilities discovery (spot/swap/future)
- Stronger order lifecycle primitives:
  - partial fills and fill aggregation
  - replace/modify semantics across exchanges
  - consistent order state model + timestamps
- Private websocket order updates beyond Binance (where supported)

Acceptance criteria:
- For top exchanges (Binance/Coinbase/Kraken/Bybit/OKX):
  - place → monitor → fill/partial → cancel → replace flows are reliable

---

## Phase 3 — Market data quality & “bring your own feeds” (1–2 weeks)
**Objective**: High-quality market data routing with user-provided feeds as first-class.

Deliverables:
- MarketDataBus extensions:
  - freshness scoring
  - source prioritization per symbol/timeframe
  - normalization rules (symbols, timestamps)
- Plug-in interface for external feeds (including other MCP servers)
- Validation + sanity checks (outlier detection, stale data handling)

Acceptance criteria:
- Operators can reliably run in “ws-first + ingest fallback + rest fallback” mode
- Clear introspection: what source is being used and why

---

## Phase 4 — Production operator layer (1–2 weeks)
**Objective**: Observability that matches real ops expectations.

Deliverables:
- Structured logs already exist → add:
  - correlation IDs propagation
  - log levels and redaction rules
- Metrics upgrades:
  - optional Prometheus export mode (off by default)
  - alerting guidance (README/RUNBOOK)
- Runbooks:
  - incident scenarios (rate limiting, ws disconnect storms, exchange outage)

Acceptance criteria:
- Operator can answer: “what’s running, what’s failing, and why” in <5 minutes

---

## Phase 5 — Security & custody “enterprise grade” (2–4 weeks)
**Objective**: Make key custody and signing policies first-class.

Deliverables:
- Remote signer hardening:
  - spend limits
  - chain allowlists
  - address allowlists
  - explicit signing intent formats
- Encrypted keystore UX improvements and documented rotation procedures
- Optional integrations:
  - HSM-backed signer (where feasible)
  - cloud secret manager patterns

Acceptance criteria:
- Clear “production reference deployment” guidance for secure key custody

---

## Phase 6 — Productization & ecosystem (ongoing)
**Objective**: Make ReadyTrader easy to find, evaluate, and adopt.

Deliverables:
- “Quick demo” scripts and screenshots (paper mode)
- Smithery (or equivalent) install path
- A minimal docs site structure (even if just `/docs`)
- Crisp positioning and messaging (see `docs/POSITIONING.md`)

Acceptance criteria:
- A new user can evaluate and run a paper-mode demo in <10 minutes

