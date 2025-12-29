## Contributing

### Local setup
- Python 3.12+
- Install dev deps (includes runtime + test + security tooling): `pip install -r requirements-dev.txt`

### Checks
- Lint: `ruff check .`
- Tests: `pytest -q`
- Security: `bandit -q -r . -c bandit.yaml`
- Dependency audit: `pip-audit -r requirements.txt`

### Pull requests
- Keep changes focused and well-tested
- Update docs (`README.md`) for any new env vars or MCP tools

