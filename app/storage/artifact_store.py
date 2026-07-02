from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, export_root: str = "exports"):
        self.export_root = Path(export_root)
        self.raw_root = self.export_root / "raw"
        self.normalized_root = self.export_root / "normalized"
        self.reports_root = self.export_root / "reports"
        for path in (self.raw_root, self.normalized_root, self.reports_root, self.export_root / "logs"):
            path.mkdir(parents=True, exist_ok=True)

    def new_run_dir(self) -> Path:
        stamp = datetime.utcnow().strftime("run_%Y-%m-%d_%H%M%S")
        path = self.raw_root / stamp
        suffix = 1
        while path.exists():
            path = self.raw_root / f"{stamp}_{suffix}"
            suffix += 1
        (path / "boards").mkdir(parents=True)
        return path

    def latest_raw_run(self) -> Path:
        runs = sorted([p for p in self.raw_root.glob("run_*") if p.is_dir()])
        if not runs:
            raise FileNotFoundError("No raw export runs found. Run export-all first.")
        return runs[-1]

    def write_json(self, path: Path, data: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
