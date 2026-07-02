from app.audits.rules import audit_model
from app.models.normalized import NormalizedAccount
from app.storage.artifact_store import ArtifactStore


class AuditEngine:
    def __init__(self, store: ArtifactStore):
        self.store = store

    def run(self):
        data = self.store.read_json(self.store.normalized_root / "normalized_schema.json")
        model = NormalizedAccount.model_validate(data)
        findings = audit_model(model)
        path = self.store.normalized_root / "audit_findings.json"
        self.store.write_json(path, {"findings": [f.model_dump() for f in findings]})
        return path
