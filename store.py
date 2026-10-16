"""Run store: idempotent, deterministic artifact ingestion.

Layout under <store>/::

    runs/<run_id>.json   canonical summary JSON (sorted keys, indent 2)
    manifest.json        sorted list of {run_id, tool, ts, headline, status}

Idempotent + deterministic: ingesting the same artifact twice writes
byte-identical files, so the store state never changes under re-ingest.
Missing run_id? Derived from sha256 of the canonical report bytes -- also
deterministic.
"""

from __future__ import annotations

import hashlib
import json
import os

from adapters import extract

RUNS_DIR = "runs"
MANIFEST = "manifest.json"


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)


def artifact_sha(envelope: dict) -> str:
    """Stable content id for an envelope (used when run_id is absent)."""
    blob = canonical({"tool": envelope.get("tool"), "report": envelope.get("report")})
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _write_if_changed(path: str, text: str) -> None:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            if fh.read() == text:
                return  # idempotent: byte-identical, leave it alone
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Store:
    def __init__(self, path: str):
        self.path = path
        self.runs_dir = os.path.join(path, RUNS_DIR)
        os.makedirs(self.runs_dir, exist_ok=True)

    def ingest(self, envelope: dict) -> dict:
        """Ingest one artifact envelope; return its run summary."""
        envelope = dict(envelope)  # never mutate the caller's dict
        envelope.setdefault("run_id", artifact_sha(envelope))
        summary = extract(envelope)
        text = canonical(summary) + "\n"
        _write_if_changed(os.path.join(self.runs_dir, f"{summary['run_id']}.json"), text)
        self._rewrite_manifest()
        return summary

    def _rewrite_manifest(self) -> None:
        rows = []
        for name in sorted(os.listdir(self.runs_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(self.runs_dir, name), encoding="utf-8") as fh:
                s = json.load(fh)
            rows.append(
                {
                    "run_id": s["run_id"],
                    "tool": s["tool"],
                    "ts": s["ts"],
                    "headline": s["headline"],
                    "status": s["status"],
                }
            )
        rows.sort(key=lambda r: (r["tool"], r["ts"], r["run_id"]))
        _write_if_changed(
            os.path.join(self.path, MANIFEST), canonical(rows) + "\n"
        )

    def manifest(self) -> list:
        path = os.path.join(self.path, MANIFEST)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def get(self, run_id: str) -> dict:
        path = os.path.join(self.runs_dir, f"{run_id}.json")
        if not os.path.exists(path):
            raise KeyError(f"unknown run_id: {run_id}")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def runs_for(self, tool: str) -> list:
        """All summaries for a tool, oldest first."""
        rows = [r for r in self.manifest() if r["tool"] == tool]
        return [self.get(r["run_id"]) for r in rows]

    def store_md5(self) -> str:
        """Fingerprint of the whole store state (deterministic)."""
        h = hashlib.sha256()
        base = os.path.abspath(self.path)
        for root, _dirs, files in os.walk(base):
            for f in sorted(files):
                p = os.path.join(root, f)
                h.update(os.path.relpath(p, base).encode())
                with open(p, "rb") as fh:
                    h.update(fh.read())
        return h.hexdigest()
