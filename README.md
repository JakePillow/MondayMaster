# Monday Migration Audit

A local-first schema audit and migration-readiness tool for Monday.com workspaces.

The tool exports Monday.com account structure, normalizes boards into a platform-neutral schema model, runs deterministic quality checks, applies structured GPT analysis, and generates reports for deciding whether the current Monday.com setup should be cleaned, retained, or migrated to ClickUp.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `MONDAY_API_TOKEN` in `.env`, then run:

```bash
python -m app.cli test-connection
python -m app.cli export-all --sample-items 100
python -m app.cli normalize
python -m app.cli audit
python -m app.cli report
```

Phase 1 is read-only. It exports raw Monday JSON, creates normalized schema JSON, runs deterministic audit rules, and generates Markdown reports under `exports/`.
