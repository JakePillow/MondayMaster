from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.audit import AuditResult
from app.models.normalized import NormalizedAccount
from app.privacy.policy import validate_text_artifact
from app.storage.artifact_store import ArtifactStore


class MarkdownReporter:
    def __init__(self, store: ArtifactStore):
        self.store = store
        self.env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=select_autoescape(default=False))

    def generate(self) -> list[Path]:
        model = NormalizedAccount.model_validate(self.store.read_json(self.store.normalized_root / "normalized_schema.json"))
        findings = AuditResult.model_validate(self.store.read_json(self.store.normalized_root / "audit_findings.json"))
        by_board = defaultdict(list)
        for f in findings.findings:
            by_board[f.object_id].append(f)
        severity_counts = Counter(f.severity for f in findings.findings)
        paths = []
        for template_name, output_name in [("schema_inventory.md.j2", "schema_inventory.md"), ("audit_report.md.j2", "audit_report.md")]:
            text = self.env.get_template(template_name).render(model=model, findings=findings.findings, by_board=by_board, severity_counts=severity_counts)
            validate_text_artifact(text)
            path = self.store.reports_root / output_name
            path.write_text(text, encoding="utf-8")
            paths.append(path)
        return paths
