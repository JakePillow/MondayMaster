# Privacy and data-minimisation boundary

This Phase 1 application operates in `technical_metadata_only` mode. The mode is mandatory; there is no CLI switch that enables content export or external transmission.

## Data requested from Monday

- Object IDs, used only in memory and converted to run-scoped one-way references before storage
- Workspace kind and state
- Board kind and state
- Group and column existence
- Column technical types
- Item IDs, used only in memory to calculate a sample count

## Data not requested or stored

- Names, emails, profile details, descriptions, updates, comments, item or subitem names
- Column values, free text, files, assets, status labels, or raw column settings
- Monday IDs, API tokens, OpenAI keys, or ClickUp keys

Every JSON write is checked by a deny-list validator. Names used in normalised data and reports are generated pseudonyms. A `privacy_manifest.json` accompanies each raw run. `python -m app.cli privacy-check` scans existing JSON and text artefacts and exits non-zero when it finds a violation.

The OpenAI client cannot transmit data. Its only available preparation path produces an allowlisted structure containing pseudonymous references, counts, column-type counts, and deterministic finding codes. Any unexpected field is rejected.

## Operational responsibilities

These controls reduce application-level exposure; they do not by themselves establish GDPR compliance. The deploying organisation must still determine its lawful basis and roles, apply access control and disk encryption, set retention/deletion periods, maintain processing records, manage processor agreements and transfers, and assess whether a DPIA or breach-response procedure is required. Existing exports made by an older version must be checked and securely handled separately.
