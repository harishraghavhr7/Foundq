"""Ingestion script: load startups into the Chroma `startups` collection.

Each record stores three structured fields as metadata — startup_name, industry,
description — and Chroma computes + stores the embedding from a combined text
("name / industry / description") via the collection's embedding function.

`upsert` (keyed by a stable id) makes re-runs idempotent: running ingestion again
updates existing rows in place instead of creating duplicates.

Sources:
  --source csv   : read data/startups.csv (default; no DB required)
  --source seed  : read data/seed_startups.json
  --source db    : read the Postgres `ideas` table from Feature 1

Run:
    python -m app.rag.ingestion --source csv
    python -m app.rag.ingestion --source seed
    python -m app.rag.ingestion --source db
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from app.rag.chroma_client import get_collection

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_CSV = _DATA_DIR / "startups.csv"
_DEFAULT_SEED = _DATA_DIR / "seed_startups.json"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _embed_text(name: str, industry: str, description: str) -> str:
    # The text Chroma actually embeds. Including name + industry enriches the
    # semantic signal beyond the raw description alone.
    return f"{name}\n{industry}\n{description}"


def ingest_startups(records: Iterable[dict]) -> int:
    """Upsert startup records into the `startups` collection. Returns the count."""
    collection = get_collection()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for r in records:
        name = r["startup_name"]
        industry = r.get("industry", "") or ""
        description = r["description"]

        ids.append(str(r.get("id") or _slug(name)))
        documents.append(_embed_text(name, industry, description))
        metadatas.append(
            {"startup_name": name, "industry": industry, "description": description}
        )

    if ids:
        # Chroma embeds `documents` with the collection's embedding function.
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def load_seed(path: Path = _DEFAULT_SEED) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_csv(path: Path = _DEFAULT_CSV) -> list[dict]:
    """Load startups from CSV (columns: name, industry, description).

    Mapped to the internal record shape used by `ingest_startups`, where the
    name column becomes `startup_name`.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"startups CSV not found at {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"name", "description"}
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            raise ValueError("startups.csv must have at least 'name' and 'description' columns")
        return [
            {
                "startup_name": row["name"].strip(),
                "industry": (row.get("industry") or "").strip(),
                "description": row["description"].strip(),
            }
            for row in reader
            if row.get("name") and row.get("description")
        ]


def load_from_db() -> list[dict]:
    """Read startups from the Feature 1 `ideas` table."""
    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return [
            {
                "id": str(idea.id),
                "startup_name": idea.title,
                "industry": idea.industry,
                "description": idea.description,
            }
            for idea in db.query(models.Idea).all()
        ]
    finally:
        db.close()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest startups into ChromaDB.")
    parser.add_argument("--source", choices=["csv", "seed", "db"], default="csv")
    parser.add_argument("--file", type=Path, default=None, help="override data file path")
    args = parser.parse_args(argv)

    if args.source == "db":
        records = load_from_db()
    elif args.source == "seed":
        records = load_seed(args.file or _DEFAULT_SEED)
    else:  # csv
        records = load_csv(args.file or _DEFAULT_CSV)
    count = ingest_startups(records)
    print(f"Ingested {count} startups into the 'startups' collection (source={args.source}).")


if __name__ == "__main__":
    main()
