# Monday Migration Audit

A local-first schema audit and migration-readiness tool for Monday.com workspaces.

The tool exports privacy-minimised Monday.com technical structure, normalizes boards into a platform-neutral schema model, runs deterministic quality checks, and generates local reports. External GPT analysis and ClickUp transmission are disabled in Phase 1.

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
python -m app.cli privacy-check
```

Phase 1 is read-only and operates exclusively in `technical_metadata_only` mode. Monday names, emails, descriptions, item content, column values, files, labels, raw settings, and credentials are neither requested nor stored. Monday IDs are replaced by run-scoped one-way references. See [PRIVACY.md](PRIVACY.md) for the complete boundary and the remaining organisational responsibilities.
