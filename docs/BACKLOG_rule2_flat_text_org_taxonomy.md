# Backlog Item: Rule 2 — `flat_text_org_taxonomy` (Blocked on Privacy Policy Decision)

**Status:** Blocked — not implemented this pass
**Blocks:** Nothing (Rules 1, 3, 4 are independent and proceed without this)
**Blocked by:** A decision from whoever owns `PRIVACY.md`, not a code or model limitation
**Related:** `docs/TECHNICAL_SPEC_model_extension_and_rules.md` §6, Rule 2

---

## 1. The conflict

Rule 2 detects flat-text columns that store structured, delimiter-separated org taxonomy (e.g. a `Personnel Group` column holding `"MT - Data & Analytics"`) instead of a proper relation to another board. Detecting this pattern requires inspecting **cell content** — the rule's match logic operates on sampled column values, not schema metadata.

The project's current privacy guarantee is schema-only: no item-level content is ever queried, sampled, or persisted. This is enforced by:

- A deny-list validator (rejects any query touching `column_values`)
- An existing test asserting `column_values` are never requested from the API

Rule 2 as originally specified violates this guarantee by design — there is no schema-only version of "check whether cell values match a delimiter pattern."

## 2. Options

| # | Option | Privacy impact | Detection coverage | Implementation cost |
|---|---|---|---|---|
| 1 | **Skip for now** — document as backlog, require explicit Phase 2 sign-off before revisiting | None — no code changes | None (rule doesn't exist) | Zero |
| 2 | **Title-only heuristic** — flag text columns by title keyword match (`Group`, `Department`, `Team`, `Region`, etc.), never touch cell values | None — stays schema-only | Partial — misses untitled or unconventionally-named taxonomy columns | Low — ship as a distinct rule ID, e.g. `flat_text_org_taxonomy_by_title`, not a silent substitute for Rule 2 |
| 3 | **Full content sampling** — implement exactly as originally specified (in-memory sample, compute match rate, never persist raw values) | Requires querying `column_values` for the first time ever in this codebase | Full — matches the case study finding exactly | High — requires amending `PRIVACY.md`, the deny-list validator, and the existing test that currently asserts this never happens |

## 3. Recommendation

**Option 1**, with **Option 2 optionally shipped alongside it as a separately-named rule** if partial coverage now is worth having. Do not implement Option 2 *as* Rule 2 — a title-keyword heuristic is a materially weaker signal than the spec describes, and reusing the same rule ID would make the audit report claim a check was performed that wasn't.

**Do not implement Option 3 without an explicit decision from the `PRIVACY.md` owner.** This isn't a technical call — a "no content, ever" guarantee is presumably a trust commitment made to whoever approved this audit tool running against production monday.com data, and one advisory-severity rule (this is `ADVISORY`, not `WARNING` — see spec) is not sufficient justification to reopen it unilaterally mid-implementation.

## 4. What "Phase 2 sign-off" should require, if Option 3 is ever pursued

If this comes back onto the roadmap, the decision-maker needs to sign off on all of the following explicitly, not just "yes, add the rule":

1. **Scope of sampling** — confirm the cap (spec suggests first 50 non-empty values per column) and confirm it's enforced at the query level, not just in application logic.
2. **Persistence guarantee** — confirm raw sampled values never reach disk, logs, or the generated report; only the computed `match_rate` and a small number of already-redacted/generic example patterns (not real values) should be report-eligible.
3. **Deny-list validator change** — this needs a narrow, reviewed exception (e.g. allow `column_values` only for columns of type `text`/`long_text`, only for match-rate computation, not general querying) rather than a blanket removal of the guard.
4. **Test change** — the existing test asserting `column_values` are never queried needs to be replaced with a test asserting they're queried *only* under Rule 2's narrow conditions and never persisted — not simply deleted.
5. **Audit trail** — some record that this specific policy exception was deliberately approved (commit message, ADR, or issue reference), so a future reviewer doesn't mistake it for scope creep.

## 5. Interim state (this pass)

- Rules 1, 3, 4: implemented per `TECHNICAL_SPEC_model_extension_and_rules.md`.
- Rule 2: not implemented. `rule_id: "flat_text_org_taxonomy"` should not appear in any rule registry or report output until this is resolved — do not stub it in as disabled/commented code that could accidentally get re-enabled without the sign-off in §4.
- If Option 2 is shipped as a stopgap, it is tracked as its own rule (`flat_text_org_taxonomy_by_title`), independently documented, independently testable, and explicitly described in the audit report as a partial/heuristic check.
