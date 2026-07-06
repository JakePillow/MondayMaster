# Technical Spec: Model Extension + Audit Rule Implementation

**Target files:** `app/models/monday_raw.py`, `app/models/normalized.py` (or equivalent), `app/audits/rules.py`
**Depends on:** `docs/PROJECT_CONTEXT.md`
**Goal:** carry three new pieces of data through the pipeline (automations, column lock state, per-group item counts) and implement the four audit rules from the case study against them.

---

## 1. Scope

Three model gaps block three of the four target rules. This spec defines:

1. Exact field-level additions to the raw model
2. Exact field-level additions to the normalized model
3. Extraction methodology — where each new field comes from, for both the future API path and the current browser-scrape path
4. A fixture matching the real Hacksaw case study, precise enough to write and test rules against today
5. The four rules as concrete, implementable logic — inputs, thresholds, output shape
6. Sequencing and acceptance criteria per step

Non-goals (explicitly out of scope for this pass): full automation recipe config, GPT analysis layer, ClickUp write-side mapping, fix executor.

---

## 2. Raw model extensions (`monday_raw.py`)

### 2.1 New: `RawAutomation`

Captures only what Rule 1 needs — enough to detect a cross-board trigger, not the full recipe.

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class AutomationTriggerType(str, Enum):
    BUTTON_CLICK = "button_click"
    STATUS_CHANGE = "status_change"
    ITEM_CREATED = "item_created"
    DATE_ARRIVES = "date_arrives"
    COLUMN_CHANGE = "column_change"
    UNKNOWN = "unknown"

class AutomationActionType(str, Enum):
    CREATE_ITEM = "create_item"
    NOTIFY = "notify"
    MOVE_ITEM = "move_item"
    CHANGE_COLUMN = "change_column"
    UNKNOWN = "unknown"

class RawAutomation(BaseModel):
    automation_id: Optional[str] = None          # None if scraped, not from API
    board_id: str                                 # board the automation lives on
    trigger_type: AutomationTriggerType
    action_type: AutomationActionType
    target_board_id: Optional[str] = None          # populated only if action creates/moves an item cross-board
    raw_description: Optional[str] = None          # human-readable text as a fallback (e.g. "Create AGM Ticket")
```

**Why `target_board_id` is optional and separate from a full recipe object:** Rule 1 only needs to know *whether* an automation's action touches a different board than the one it's defined on. Storing the full condition/action tree is extra surface area with no consumer yet — add it later if a rule actually needs it.

### 2.2 Extend: `RawColumn`

Add one field to whatever the existing column model looks like:

```python
class RawColumn(BaseModel):
    # ...existing fields (id, title, type, settings, etc.)...
    locked: bool = False   # monday.com "column is locked" state
```

If the existing model uses a generic `settings: dict` passthrough instead of typed fields, `locked` should still be promoted to a first-class field — it's a governance signal three rules care about (directly for Rule 4, indirectly it corroborates confidence for Rules 1 and 2), so it shouldn't be buried in an untyped blob.

### 2.3 Extend: `RawGroup`

```python
class RawGroup(BaseModel):
    # ...existing fields (id, title, color, etc.)...
    item_count: int   # count of items belonging to this group at export time
```

**Check before adding a new field:** if `RawBoard.items` is a flat list with a `group_id` back-reference, `item_count` is a derived value, not raw data — compute it in the normalizer (Section 3), don't duplicate it as stored raw state that can drift from the actual item list. Only add it to the raw model if the export process captures groups and items as genuinely separate API calls where recomputing later is expensive.

### 2.4 Extend: `RawBoard`

```python
class RawBoard(BaseModel):
    # ...existing fields (id, name, groups, columns, items, etc.)...
    automations: list[RawAutomation] = []
```

---

## 3. Normalized model extensions

The normalized model is where cross-board rules (like Rule 1) become answerable in one place instead of requiring a full-account join at rule-evaluation time.

### 3.1 Extend: `NormalizedColumn`

```python
class NormalizedColumn(BaseModel):
    # ...existing fields...
    is_locked: bool
```

Straight passthrough from `RawColumn.locked`.

### 3.2 Extend: `NormalizedGroup`

```python
class NormalizedGroup(BaseModel):
    # ...existing fields...
    item_count: int
```

Computed as `len([i for i in board.items if i.group_id == group.id])` at normalization time — this is the recommended approach per 2.3 unless the raw export genuinely can't cheaply recompute it.

### 3.3 New: `NormalizedAutomation`

```python
class NormalizedAutomation(BaseModel):
    board_id: str
    board_name: str                # denormalized for report readability
    trigger_type: AutomationTriggerType
    action_type: AutomationActionType
    target_board_id: Optional[str] = None
    target_board_name: Optional[str] = None   # denormalized; None if same-board or unresolvable
    is_cross_board: bool           # derived: target_board_id is not None and target_board_id != board_id
```

`is_cross_board` should be computed once during normalization, not recomputed inside the rule — the rule should just filter on it.

### 3.4 Extend: `NormalizedBoard`

```python
class NormalizedBoard(BaseModel):
    # ...existing fields...
    automations: list[NormalizedAutomation] = []
```

---

## 4. Extraction methodology

Two extraction paths need to populate the same fields. Document both since the API path isn't available yet but the fixture/browser path is in use today.

### 4.1 API path (future — once admin token exists)

GraphQL query additions needed on top of whatever the exporter already pulls:

```graphql
query {
  boards(ids: [BOARD_ID]) {
    columns {
      id
      title
      type
      archived
    }
    groups {
      id
      title
      items_count
    }
  }
  # Automations are NOT exposed on the standard boards query.
  # Use the dedicated endpoint:
}
```

```graphql
query {
  boards(ids: [BOARD_ID]) {
    id
    name
  }
}
```

**Important caveat to flag to whoever implements this:** monday's GraphQL API does **not** expose automation recipes through the standard `boards` query. Automation/recipe read access requires the `automations` API (currently more limited, and in some plan tiers requires the "Automations Center" app-level API rather than the board API). This needs a spike before assuming it's a simple query addition — budget time to confirm current API surface rather than treating this as done once the schema fields exist.

**Column lock state**: confirm the exact field name in the current API version (`archived` guards deletion state, not lock state — verify whether monday exposes lock via `settings_str` JSON on the column rather than a first-class field; historically this has moved around monday's schema versions).

### 4.2 Browser-scrape path (current, used for the Hacksaw case study)

Since this is what actually produced Section 6 of the context doc, document how each field maps to something visible in the UI so the same manual methodology used for the case study can be repeated consistently by anyone (or any agent) doing this by hand:

| Field | Where to find it in the UI |
|---|---|
| `column.locked` | Lock icon (🔒) rendered next to the column header |
| `group.item_count` | Number shown next to group name when group is expanded (e.g. "56 Items") |
| `automation.trigger_type` / `action_type` | Board's "Automate" panel (top bar, shows automation count and recipe list) — recipes are human-readable sentences like "When button clicked, create item in board X" |
| `automation.target_board_id` | Only resolvable from the recipe's plain-language description in the scrape path (e.g. parse "create item in board X" text) — this is inherently less reliable than the API path and should be flagged as `automation_id: None` / lower-confidence in output |

This asymmetry (API path = structured, scrape path = text-parsed) should be preserved as a `source: Literal["api", "scrape"]` field on `RawAutomation` if scraping remains in use for any length of time, so downstream rules/reports can express confidence accordingly. Not required for the first implementation pass, but worth flagging now rather than discovering it's needed after rules are already relying on scraped automation data silently.

---

## 5. Fixture

A minimal fixture shaped exactly like the real Access & Grant Management case study, small enough to reason about by hand but structurally complete enough to trigger all four rules.

```json
{
  "board_id": "tmpl-001",
  "name": "Access and Grant Management - Templates",
  "columns": [
    {"id": "team", "title": "Team", "type": "text", "locked": true},
    {"id": "spec", "title": "Specification", "type": "long_text", "locked": true}
  ],
  "groups": [
    {"id": "g1", "title": "MT - Account Management", "item_count": 15}
  ],
  "automations": [
    {
      "board_id": "tmpl-001",
      "trigger_type": "button_click",
      "action_type": "create_item",
      "target_board_id": "prog-002",
      "raw_description": "Create AGM Ticket"
    }
  ]
}
```

```json
{
  "board_id": "prog-002",
  "name": "Access and Grant Management - In Progress",
  "columns": [
    {"id": "approver", "title": "Approver", "type": "person", "locked": true},
    {"id": "tool_admin", "title": "Tool Admin", "type": "person", "locked": true},
    {"id": "status", "title": "Status", "type": "status", "locked": true},
    {"id": "personnel_group", "title": "Personnel Group", "type": "text", "locked": true}
  ],
  "groups": [
    {"id": "all", "title": "All", "item_count": 56}
  ],
  "automations": []
}
```

```json
{
  "board_id": "comp-003",
  "name": "Access and Grant Management - Completed",
  "columns": [
    {"id": "approver", "title": "Approver", "type": "person", "locked": true}
  ],
  "groups": [
    {"id": "all", "title": "All", "item_count": 3798}
  ],
  "automations": []
}
```

Sample data value for `personnel_group` cells (needed for Rule 2 — put this in the fixture's item-level test data, not the board schema above): `"MT - Data & Analytics"`, `"SE - Development - Platform"`, `"UK - Account Management"` — note the consistent `"XX - Department[ - Team]"` delimiter pattern.

---

## 6. Rule specifications

Common output shape for all rules — define once, reuse:

```python
class Severity(str, Enum):
    INFO = "info"
    ADVISORY = "advisory"
    WARNING = "warning"

class AuditFinding(BaseModel):
    rule_id: str
    board_id: str
    board_name: str
    severity: Severity
    message: str
    detail: Optional[dict] = None   # rule-specific structured payload for the report generator
```

### Rule 1 — `cross_board_automation_trigger`

- **Input:** `NormalizedBoard.automations`
- **Logic:** for each automation where `is_cross_board == True`, emit a finding.
- **Severity:** `WARNING` — this is a migration blocker requiring manual redesign, not just a note.
- **Message template:** `"Automation on '{board_name}' ({trigger_type} → {action_type}) creates/modifies items on a different board ('{target_board_name}'). ClickUp has no direct equivalent for cross-List/cross-Space automation triggers of this kind — this logic must be manually rebuilt, not auto-mapped."`
- **Detail payload:** `{"target_board_id": ..., "trigger_type": ..., "action_type": ...}`

### Rule 2 — `flat_text_org_taxonomy`

- **Input:** all `NormalizedColumn` of type `text` (or long_text) across a board, plus a sample of cell values for that column (item-level data, sampled — not full extraction).
- **Logic:** flag a text column if a threshold percentage (suggest **≥80%**) of sampled non-empty values match a delimiter-structured pattern, e.g. regex `^[A-Z]{2,4}\s*-\s*[\w &]+(\s*-\s*[\w &]+)?$`. This catches `"MT - Data & Analytics"`, `"SE - Development - Platform"` style values without hardcoding Hacksaw's specific department names.
- **Severity:** `ADVISORY` — a normalization suggestion, not a hard blocker.
- **Message template:** `"Column '{column_title}' on '{board_name}' stores structured, delimiter-separated values ({sample_values}) as plain text rather than a relation to another board. Consider modeling this as a board_relation for the migration target."`
- **Detail payload:** `{"column_id": ..., "match_rate": ..., "sample_values": [...]}`
- **Note:** this rule needs a small amount of item-level sampling, which is a scope increase versus rules 1/3/4 (schema-only). Cap the sample (e.g. first 50 non-empty values) rather than scanning full boards — this keeps it cheap and keeps the tool's "schema-first" posture intact; it's sampling for a signal, not doing a full data extract.

### Rule 3 — `single_group_mega_board`

- **Input:** `NormalizedBoard.groups`
- **Logic:** flag if `len(groups) == 1` AND `groups[0].item_count > 500` (threshold configurable; 500 is a starting default, not a hard constant — expose as a config value).
- **Severity:** `ADVISORY`
- **Message template:** `"Board '{board_name}' has {item_count} items in a single flat group. Consider archiving/sub-grouping (e.g. by year or status) before migration to keep the destination List manageable."`
- **Detail payload:** `{"group_id": ..., "item_count": ..., "threshold": 500}`
- **Note:** this is already implementable today per the current codebase status — the existing `too_many_groups` rule checks the opposite failure mode (too many groups); this is a new, separate rule, not a threshold tweak to that one.

### Rule 4 — `governance_signal_locked_columns`

- **Input:** `NormalizedColumn.is_locked` across a board
- **Logic:** compute `locked_ratio = locked_count / total_columns`. If `locked_ratio >= 0.7`, emit a positive/informational finding (not a problem to fix).
- **Severity:** `INFO`
- **Message template:** `"{locked_count}/{total_columns} columns on '{board_name}' are locked ({locked_ratio:.0%}). This indicates intentional schema governance — treat as a low-risk board for migration, and consider it a reference pattern for auditing less-disciplined boards elsewhere in the account."`
- **Detail payload:** `{"locked_count": ..., "total_columns": ..., "locked_ratio": ...}`
- **Note:** this is the one rule that should actively suppress/downweight other advisory findings on the same board in the eventual report layer — a highly-governed board's other minor flags (e.g. Rule 2 on one column) carry less urgency. Not required for this implementation pass; just don't design the `AuditFinding` schema in a way that makes that cross-referencing impossible later (i.e. keep `board_id` on every finding, which the schema above already does).

---

## 7. Sequencing & acceptance criteria

| Step | Deliverable | Done when |
|---|---|---|
| 1 | `RawAutomation`, `RawColumn.locked`, `RawGroup`/`RawBoard` extensions | Models import cleanly; existing exporter output (if any real export exists) still parses without validation errors |
| 2 | Normalizer extensions (`NormalizedAutomation`, `is_locked`, `item_count`, `is_cross_board` derivation) | Fixture from Section 5 normalizes into valid `NormalizedBoard` objects for all 3 boards |
| 3 | Fixture files committed under `tests/fixtures/access_grant_management/` | Three JSON files match Section 5 exactly (plus item-level sample data for Rule 2) |
| 4 | Rule 3 (`single_group_mega_board`) | Fires on the Completed fixture board, does not fire on Templates/In Progress |
| 5 | Rule 4 (`governance_signal_locked_columns`) | Fires `INFO` on all three fixture boards (all have high lock ratios per the case study) |
| 6 | Rule 1 (`cross_board_automation_trigger`) | Fires exactly once, on the Templates board, pointing at In Progress |
| 7 | Rule 2 (`flat_text_org_taxonomy`) | Fires on the In Progress board's `personnel_group` column given sample values from Section 5 |
| 8 | Integration test | Running the full rule set against all three fixtures produces exactly 4 findings (1+1+1+1) with correct `rule_id`s — this is the regression test that protects the case study from silently breaking as the tool evolves |

Steps 1–3 are the "model extension" work item from the previous message; steps 4–8 are "writing rules against fixture data." Doing them in this order means step 3's fixture is authored once, against the final model shape, instead of being reauthored if the rules step reveals the models need adjusting.

---

## 8. Open questions to resolve before/during implementation

1. Does the current exporter (if one exists beyond stubs) have *any* automation data today, even partial? If yes, check its shape against `RawAutomation` before finalizing the field names.
2. Confirm monday's current API surface for automations (Section 4.1 caveat) — this affects whether Rule 1 is ever fully API-drivable or permanently scrape-assisted for now.
3. Decide the `source: "api" | "scrape"` provenance field now or defer — recommend deferring to avoid scope creep, but Section 4.2 flags it explicitly so it isn't forgotten.
4. Confirm the 500-item and 80%-match-rate and 70%-lock-ratio thresholds with whoever owns the audit report's intended audience — these are reasonable starting defaults from the case study, not empirically tuned numbers.

---

## Implementation status (2026-07-06)

- **Rules 1, 3, 4: implemented.** See `app/models/monday_raw.py`, `app/models/normalized.py`, `app/normalizers/monday_normalizer.py`, `app/audits/rules.py`, and the regression test in `tests/test_hacksaw_case_study_rules.py`.
- **Rule 2: blocked.** See `docs/BACKLOG_rule2_flat_text_org_taxonomy.md` for the conflict, options, and recommendation.
- Deviations from this spec as implemented, and why:
  - Reused the existing `AuditFinding`/`Severity` (`low`/`medium`/`high`/`critical`) model from `app/models/audit.py` instead of introducing this spec's separate `Severity` (`info`/`advisory`/`warning`) enum, to avoid two incompatible finding schemas. Mapping used: `WARNING → high`, `ADVISORY → medium`, `INFO → low`.
  - Fixture top-level board key is `id`, not `board_id` as shown in Section 5 — matches the real sanitizer/normalizer's existing field name (`schema.get("id")`).
  - Step 8's "exactly 4 findings" undercounts: Rule 4 fires once per board (3 boards → 3 findings), not once overall, matching this section's own Rule 4 row ("fires on all three fixture boards"). The regression test asserts the corrected counts (1 cross-board, 1 mega-board, 3 governance).
  - Client/exporter/sanitizer (§4.1 API wiring) intentionally not touched this pass — no live API token exists to validate field names against, and automations aren't confirmed to be on the standard `boards` query at all (§4.1's own caveat).
