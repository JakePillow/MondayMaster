from app.audits.rules import audit_model
from app.models.normalised import NormalisedAccount
from app.storage.artefact_store import ArtefactStore


class AuditEngine:
    def __init__(self, store: ArtefactStore):
        self.store = store

    def run(self):
        data = self.store.read_json(self.store.normalised_root / "normalised_schema.json")
        model = NormalisedAccount.model_validate(data)
        findings = audit_model(model)
        path = self.store.normalised_root / "audit_findings.json"
        self.store.write_json(path, {"findings": [f.model_dump() for f in findings]})
        return path
