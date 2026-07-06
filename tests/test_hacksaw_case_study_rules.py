from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.audits.rules import audit_model
from app.models.normalised import NormalisedAccount, NormalisedBoard
from app.normalisers.monday_normaliser import build_normalised_board

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "access_grant_management"


def _load_case_study_boards() -> list[NormalisedBoard]:
    schemas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURE_DIR.glob("*.json"))]
    board_names = {str(s["id"]): str(s["name"]) for s in schemas}
    return [build_normalised_board(schema, board_names) for schema in schemas]


class HacksawCaseStudyAuditTests(unittest.TestCase):
    """Regression test for the four case-study findings in docs/PROJECT_CONTEXT.md section 6.

    Rule 2 (flat_text_org_taxonomy) is intentionally not covered here — it requires sampling
    column values, which conflicts with this project's no-content-ever privacy boundary and is
    pending a decision before implementation.
    """

    def setUp(self):
        self.boards = _load_case_study_boards()
        self.by_name = {b.name: b for b in self.boards}

    def test_normalises_locked_columns_item_counts_and_automations(self):
        templates = self.by_name["Access and Grant Management - Templates"]
        self.assertTrue(all(c.is_locked for c in templates.columns))
        self.assertEqual(templates.groups[0].item_count, 15)
        self.assertEqual(len(templates.automations), 1)
        automation = templates.automations[0]
        self.assertTrue(automation.is_cross_board)
        self.assertEqual(automation.target_board_id, "board_prog002")
        self.assertEqual(automation.target_board_name, "Access and Grant Management - In Progress")

        completed = self.by_name["Access and Grant Management - Completed"]
        self.assertEqual(completed.groups[0].item_count, 3798)

    def test_case_study_rules_fire_as_expected(self):
        model = NormalisedAccount(boards=self.boards)
        findings = audit_model(model)
        by_rule: dict[str, list] = {}
        for f in findings:
            by_rule.setdefault(f.rule_id, []).append(f)

        cross_board = by_rule.get("cross_board_automation_trigger", [])
        self.assertEqual(len(cross_board), 1)
        self.assertEqual(cross_board[0].object_name, "Access and Grant Management - Templates")

        mega_board = by_rule.get("single_group_mega_board", [])
        self.assertEqual(len(mega_board), 1)
        self.assertEqual(mega_board[0].object_name, "Access and Grant Management - Completed")

        governance = by_rule.get("governance_signal_locked_columns", [])
        self.assertEqual({f.object_name for f in governance}, {b.name for b in self.boards})


if __name__ == "__main__":
    unittest.main()
