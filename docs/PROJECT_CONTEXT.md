# MondayMaster — Project Context

> Drop this file into the repo (e.g. `docs/PROJECT_CONTEXT.md`) so any session — human or agent — has the background without needing prior chat history.

## 1. What this project is

A tool to audit Hacksaw Gaming's monday.com account structure and evaluate migrating to ClickUp. It is **not** a generic "compare two PM tools" exercise — it's a schema-first systems audit, treating monday.com as a database/workflow engine that needs to be exported, normalized, validated, and only then interpreted (by rules first, GPT second).

**Owner intent, in their own words:** they work better with schema/technical data than with narrative descriptions, and want something closer to a PowerShell-style surgical tool — export everything, inspect it as data, make targeted fixes — rather than a black-box migration wizard.

## 2. Pipeline architecture

```
Monday Export → Normalization → Deterministic Audit → GPT Analysis →
Migration Mapping → Report Generation → (optional) Safe Fixes
```

Design principles, in priority order:

1. **Schema first** — structure before interpretation.
2. **Artifacts before interpretation** — every stage writes a durable, inspectable artifact (raw export → normalized model → audit results) before anything touches an LLM.
3. **Deterministic validation before AI** — rule-based checks run first; GPT only analyzes what rules can't decide.
4. **Local-first, CLI-first** — no hosted service assumption; runs from the command line against local files.
5. **Safe-by-default mutations** — write/fix operations are deferred behind dry-run support; nothing mutates monday.com until validated.
6. **Platform-neutral intermediate model** — the normalized schema is not monday-shaped or ClickUp-shaped; both are mapped onto/from it.

## 3. monday.com data model (reference)

Hierarchy, top to bottom: **Account → Workspace → Folder → Board → Group → Item → Column**, with optional **Subitems** under Items.

- **Workspace**: access-control boundary. Folders inside it are cosmetic only (no permission effect).
- **Board**: the actual unit of work. Two functional archetypes matter for auditing:
  - *Intake boards* — low friction, high volume, minimal required fields (requests, tickets, ideas).
  - *Processing boards* — mandatory owners, enforced statuses, automations that maintain consistency (active projects, pipelines).
- **Anti-pattern to flag in audits**: automations whose only job is keeping duplicated data in sync across boards. That's a modeling problem wearing an automation costume, not a legitimate automation use.
- **Column types** that need special handling in an exporter: `mirror`, `formula`, `board_relation`, `connect_boards`, `status`/label columns, `people`, `subitems`. These don't have a clean 1:1 target type on the other platform.

## 4. ClickUp data model (reference)

Hierarchy: **Workspace → Space → Folder → List → Task → Subtask** (+ nested subtasks).

- Recommended: **one Workspace per org.** Spaces = departments/major functions. Folders = clients or major projects.
- **Anti-pattern to flag**: giving every client/team its own Space instead of a Folder under one Space — breaks cross-entity reporting because Space-level settings (statuses, custom fields) don't stay consistent across Spaces.

## 5. Concept mapping (monday.com → ClickUp)

This table should seed the tool's comparison/mapping engine directly — don't reinvent it in code.

| monday.com | ClickUp | Notes |
|---|---|---|
| Workspace | Space (usually) | monday "Workspace" is closer to ClickUp's "Space," not its "Workspace" |
| Folder | Folder | Direct match |
| Board | List (or Folder, if large) | A board with many active groups often becomes a Folder of Lists |
| Group | List, or a status/custom field | Depends whether the group represents a phase or a category |
| Item | Task | Direct match |
| Column | Custom Field | Direct match, but types don't map 1:1 — mirror/formula/board_relation columns need explicit rebuild logic |
| Subitem | Subtask | Direct match |
| Automation (recipe) | Automation | Logic must be rebuilt, not just re-pointed; cross-board triggers have no direct ClickUp equivalent (see case study below) |

## 6. Real-data case study: Hacksaw "Access & Grant Management"

This is the first (and so far only) real-world validation of the framework above, done via read-only, member-level browsing — no admin access or API token available yet. **Schema only was captured; no personnel/PII data was extracted or should be reproduced from this document.**

**Location:** Hacksaw Gaming workspace → "Access & Grant Management" folder → 3 boards forming one pipeline.

| Board | Role | Grouping | Automations |
|---|---|---|---|
| Access and Grant Management – Templates | Intake/trigger library: one row per Office+Team combo; a button column fires an automation that creates a new item on the In Progress board | Dynamic, grouped by a "Team" field | 2 |
| Access and Grant Management – In Progress | Active processing board | Single flat group ("All") | 6 |
| Access and Grant Management – Completed | Archive (3,798 items) | Single flat group + filtered views "Revoke Access" / "Temp" | n/a |

**Column schema (In Progress board, the fullest of the three):**

| Column | Type |
|---|---|
| Item | Name (default) |
| Approver | Person 🔒 |
| Tool Admin | Person 🔒 |
| Status | Status label 🔒 |
| Resolution | Status label 🔒 |
| Personnel | Text / linked reference |
| Request Type | Status label (Grant access / Revoke access) 🔒 |
| Access Level | Status label (e.g. User/Admin) 🔒 |
| Specification | Long text 🔒 |
| Justification | Long text 🔒 |
| Office | Dropdown 🔒 |
| Personnel Group | Text, flat taxonomy ("Office - Department - Team") 🔒 |
| Personnel Email Address | Text/email 🔒 |
| Creation log | Auto column |
| Item ID | Auto column |

Templates and Completed boards mirror this core column set — schema discipline is consistent across the pipeline.

**Audit findings this tool's rule engine should be able to detect automatically:**

1. **Cross-board automation trigger with no destination-platform equivalent.** The Templates board's button column exists only to create items on a different board (In Progress). ClickUp has no native cross-board button trigger — this must surface as a manual-redesign flag in the migration report, not a silent 1:1 mapping.
2. **Flat-text org taxonomy instead of a relation.** "Personnel Group" stores values like `"MT - Data & Analytics"` as plain text rather than relating to a real personnel/org-chart board. Flag as a normalization candidate — a `board_relation` would be more useful.
3. **Single-group mega-board.** The Completed archive has ~3,800 items in one flat group. Flag boards past a size threshold (e.g. >500 items, 1 group) as archiving/reorganization candidates.
4. **Heavy column locking** (🔒 on nearly every field) is a *positive* signal — treat as evidence of intentional governance, not something to flag.

## 7. What's NOT done yet

- No admin access / API token acquired yet — everything above came from manual browsing, not the GraphQL API.
- No other workspace folders have been audited — this is one folder out of the full account.
- No actual code has been written against real data yet; `models/monday_raw.py` and the rest of the pipeline should be built to ingest data shaped like what's described in Section 6, but currently only has whatever scaffolding exists in-repo.
- ClickUp-side data has not been touched at all — no ClickUp workspace has been inspected yet, only ClickUp's public documentation/best-practice model (Section 4).

## 8. Immediate next steps (from the audit side, feeding into code)

1. Get API token access (admin) to replace manual browsing with a real GraphQL export.
2. Encode Section 5's mapping table as the seed ruleset for the comparison engine.
3. Encode the four audit findings in Section 6 as the first deterministic rules (before any GPT analysis layer is invoked).
4. Extend the schema audit to the rest of the Hacksaw workspace, one folder at a time, using the same schema-only methodology (no personnel/record data leaves the audit process).
