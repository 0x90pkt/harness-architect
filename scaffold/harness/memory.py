"""
File-backed memory — structured note-taking and a progress log.

This is the "agentic memory" pattern: the agent writes durable notes outside the
context window and reads them back later (and, for long-running agents, in a
*new* session). A plain directory is enough; it also makes state human-auditable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class FileMemory:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.notes_dir = self.root / "notes"
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.root / "progress.log"

    # --- key/value notes ---------------------------------------------------- #
    def write_note(self, key: str, text: str) -> None:
        (self.notes_dir / f"{_safe(key)}.md").write_text(text, encoding="utf-8")

    def read_note(self, key: str) -> Optional[str]:
        p = self.notes_dir / f"{_safe(key)}.md"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def list_notes(self) -> list[str]:
        return sorted(p.stem for p in self.notes_dir.glob("*.md"))

    # --- progress log (append-only) ---------------------------------------- #
    def append_progress(self, line: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.progress_file.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {line}\n")

    def read_progress(self) -> str:
        return self.progress_file.read_text(encoding="utf-8") if self.progress_file.exists() else ""

    # --- structured task/feature list (long-running pattern) ---------------- #
    def write_tasklist(self, tasks: list[dict]) -> None:
        """Persist a structured task list (prefer JSON; models rewrite it less)."""
        (self.root / "tasks.json").write_text(json.dumps(tasks, indent=2), encoding="utf-8")

    def read_tasklist(self) -> list[dict]:
        p = self.root / "tasks.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def mark_task(self, task_id: str, passes: bool) -> None:
        tasks = self.read_tasklist()
        for t in tasks:
            if t.get("id") == task_id:
                t["passes"] = passes
        self.write_tasklist(tasks)

    def next_open_task(self) -> Optional[dict]:
        for t in self.read_tasklist():
            if not t.get("passes", False):
                return t
        return None


def _safe(key: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
