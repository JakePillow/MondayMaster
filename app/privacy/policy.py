from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PRIVACY_MODE = "technical_metadata_only"
POLICY_VERSION = "1.0"

_FORBIDDEN_KEYS = {
    "authorization",
    "api_key",
    "token",
    "email",
    "phone",
    "address",
    "description",
    "text",
    "value",
    "column_values",
    "subitems",
    "settings_str",
    "creator",
    "owner",
}
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}")
_OPAQUE_RE = re.compile(r"^(?:account|workspace|board|group|column|item|user)_[0-9a-f]{12}$")
_SYNTHETIC_NAME_RE = re.compile(
    r"^(?:Account|Workspace|Board|Group|Column|Item|User) "
    r"(?:account|workspace|board|group|column|item|user)_[0-9a-f]{12}$"
)
_REFERENCE_KEYS = {"id", "workspace_id", "object_id", "column_id"}
_REFERENCE_LIST_KEYS = {"board_ids", "relationship_targets"}


class PrivacyViolation(ValueError):
    """Raised when an artefact contains data outside the technical allowlist."""


def is_opaque_reference(value: Any, kind: str | None = None) -> bool:
    if not isinstance(value, str) or not _OPAQUE_RE.fullmatch(value):
        return False
    return kind is None or value.startswith(f"{kind}_")


class TechnicalDataSanitiser:
    """Convert Monday identifiers to run-scoped opaque references and drop content."""

    def __init__(self, salt: bytes | None = None):
        self._salt = salt or secrets.token_bytes(32)

    def ref(self, kind: str, value: Any) -> str | None:
        if value is None or value == "":
            return None
        digest = hashlib.sha256(self._salt + str(value).encode("utf-8")).hexdigest()[:12]
        return f"{kind}_{digest}"

    @staticmethod
    def synthetic_name(ref: str) -> str:
        kind = ref.split("_", 1)[0].capitalize()
        return f"{kind} {ref}"

    def account(self, raw: dict[str, Any]) -> dict[str, Any]:
        account_ref = self.ref("account", raw.get("id"))
        return {"id": account_ref} if account_ref else {}

    def workspace(self, raw: dict[str, Any]) -> dict[str, Any]:
        ref = self.ref("workspace", raw.get("id"))
        return {
            "id": ref,
            "name": self.synthetic_name(ref),
            "kind": raw.get("kind"),
            "state": raw.get("state"),
        }

    def board_index(self, raw: dict[str, Any]) -> dict[str, Any]:
        ref = self.ref("board", raw.get("id"))
        return {
            "id": ref,
            "name": self.synthetic_name(ref),
            "state": raw.get("state"),
            "board_kind": raw.get("board_kind"),
            "workspace_id": self.ref("workspace", raw.get("workspace_id")),
        }

    def board_schema(self, raw: dict[str, Any]) -> dict[str, Any]:
        board = self.board_index(raw)
        board["groups"] = []
        for group in raw.get("groups", []):
            ref = self.ref("group", group.get("id"))
            item_count = group.get("items_count", group.get("item_count", 0))
            board["groups"].append({"id": ref, "title": self.synthetic_name(ref), "item_count": int(item_count or 0)})
        board["columns"] = []
        for column in raw.get("columns", []):
            ref = self.ref("column", column.get("id"))
            board["columns"].append(
                {
                    "id": ref,
                    "title": self.synthetic_name(ref),
                    "type": str(column.get("type") or "unknown"),
                    "locked": bool(column.get("locked", False)),
                    "settings": {},
                    "labels": [],
                    "relationship_targets": [],
                }
            )
        board["automations"] = self.automations(raw.get("automations", []))
        return board

    _KNOWN_TRIGGER_TYPES = {"button_click", "status_change", "item_created", "date_arrives", "column_change"}
    _KNOWN_ACTION_TYPES = {"create_item", "notify", "move_item", "change_column"}

    def automations(self, raw_automations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Structural-only: trigger/action type and a pseudonymous target board ref.

        `raw_description` (a human-authored recipe label) is deliberately dropped — this
        pipeline never persists free text, per PRIVACY.md.
        """
        sanitised = []
        for automation in raw_automations:
            trigger_type = str(automation.get("trigger_type") or "unknown")
            action_type = str(automation.get("action_type") or "unknown")
            target_board_id = automation.get("target_board_id")
            sanitised.append(
                {
                    "trigger_type": trigger_type if trigger_type in self._KNOWN_TRIGGER_TYPES else "unknown",
                    "action_type": action_type if action_type in self._KNOWN_ACTION_TYPES else "unknown",
                    "target_board_id": self.ref("board", target_board_id) if target_board_id else None,
                }
            )
        return sanitised

    def item_sample_summary(self, items: list[dict[str, Any]], limit: int) -> dict[str, Any]:
        return {
            "sample_count": len(items),
            "sample_limit": limit,
            "content_exported": False,
            "identifiers_exported": False,
        }

    @staticmethod
    def manifest() -> dict[str, Any]:
        return {
            "policy_version": POLICY_VERSION,
            "privacy_mode": PRIVACY_MODE,
            "generated_at": datetime.now(UTC).isoformat(),
            "external_transmission_enabled": False,
            "identifier_strategy": "run_scoped_one_way_references",
            "collected_categories": [
                "object_counts",
                "object_types",
                "state_flags",
                "hierarchy_relationships",
            ],
            "excluded_categories": [
                "names_and_titles_from_monday",
                "emails_and_user_profiles",
                "descriptions_and_updates",
                "item_and_subitem_content",
                "column_values_and_free_text",
                "files_and_assets",
                "raw_column_settings_and_labels",
                "api_credentials",
            ],
        }


def _walk(value: Any, path: str, violations: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lower = str(key).lower()
            child_path = f"{path}.{key}"
            if lower in _FORBIDDEN_KEYS:
                violations.append(f"{child_path}: forbidden field")
            if (lower in {"name", "title", "object_name"} or lower.endswith("_name")) and isinstance(child, str):
                if child and not _SYNTHETIC_NAME_RE.fullmatch(child):
                    violations.append(f"{child_path}: non-synthetic name/title")
            if lower in {"settings"} and child not in ({}, None):
                violations.append(f"{child_path}: raw settings are not permitted")
            if lower in {"users"} and child not in ([], None):
                violations.append(f"{child_path}: user records are not permitted")
            if lower in _REFERENCE_KEYS and child is not None:
                if not is_opaque_reference(child):
                    violations.append(f"{child_path}: raw identifier")
            if lower in _REFERENCE_LIST_KEYS and isinstance(child, list):
                if any(not is_opaque_reference(item) for item in child):
                    violations.append(f"{child_path}: raw identifier list")
            _walk(child, child_path, violations)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", violations)
        return
    if isinstance(value, str):
        if _EMAIL_RE.search(value):
            violations.append(f"{path}: email-like content")
        if _BEARER_RE.search(value):
            violations.append(f"{path}: credential-like content")


def validate_artefact(data: Any) -> None:
    violations: list[str] = []
    _walk(data, "$", violations)
    if violations:
        raise PrivacyViolation("Privacy validation failed: " + "; ".join(violations[:10]))


def validate_text_artefact(text: str) -> None:
    if _EMAIL_RE.search(text):
        raise PrivacyViolation("Privacy validation failed: email-like content in text artefact")
    if _BEARER_RE.search(text):
        raise PrivacyViolation("Privacy validation failed: credential-like content in text artefact")


def scan_export_tree(root: Path) -> list[str]:
    violations: list[str] = []
    if not root.exists():
        return violations
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".json":
                validate_artefact(json.loads(path.read_text(encoding="utf-8")))
            elif path.suffix.lower() in {".md", ".txt", ".log"}:
                validate_text_artefact(path.read_text(encoding="utf-8"))
        except (PrivacyViolation, json.JSONDecodeError, UnicodeDecodeError) as exc:
            violations.append(f"{path}: {exc}")
    return violations
