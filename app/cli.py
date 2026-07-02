from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv

from app.audits.engine import AuditEngine
from app.clients.monday_client import MondayClient
from app.exporters.monday_exporter import MondayExporter
from app.normalizers.monday_normalizer import MondayNormalizer
from app.reports.markdown_reporter import MarkdownReporter
from app.storage.artifact_store import ArtifactStore

app = typer.Typer(help="Read-only Monday.com schema audit and migration-readiness CLI.")


def _store() -> ArtifactStore:
    load_dotenv()
    return ArtifactStore(os.getenv("EXPORT_ROOT", "exports"))


def _client() -> MondayClient:
    load_dotenv()
    return MondayClient(os.getenv("MONDAY_API_TOKEN", ""))


@app.command("test-connection")
def test_connection():
    """Verify the Monday API token can read basic account data."""
    typer.echo(_client().test_connection())


@app.command("export-account")
def export_account():
    store = _store(); run = store.new_run_dir(); store.write_json(run / "account.json", _client().get_account()); typer.echo(run)


@app.command("export-workspaces")
def export_workspaces():
    store = _store(); run = store.new_run_dir(); store.write_json(run / "workspaces.json", _client().get_workspaces()); typer.echo(run)


@app.command("export-boards")
def export_boards():
    store = _store(); run = store.new_run_dir(); store.write_json(run / "boards_index.json", _client().get_boards()); typer.echo(run)


@app.command("export-board")
def export_board(board_id: str = typer.Option(...), sample_items: int = typer.Option(100)):
    path = MondayExporter(_client(), _store()).export_board(board_id, sample_items)
    typer.echo(f"Exported board {board_id} to {path}")


@app.command("export-all")
def export_all(sample_items: int = typer.Option(100, help="Maximum item sample per board.")):
    path = MondayExporter(_client(), _store()).export_all(sample_items)
    typer.echo(f"Exported Monday account to {path}")


@app.command("normalize")
def normalize():
    path = MondayNormalizer(_store()).normalize_latest()
    typer.echo(f"Wrote normalized schema to {path}")


@app.command("audit")
def audit():
    path = AuditEngine(_store()).run()
    typer.echo(f"Wrote audit findings to {path}")


@app.command("report")
def report():
    paths = MarkdownReporter(_store()).generate()
    for path in paths:
        typer.echo(f"Wrote report {path}")


if __name__ == "__main__":
    app()
