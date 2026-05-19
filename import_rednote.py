"""Import RednoteBook journal files into notetaker.

Usage:
    python3 import_rednote.py [--folder PATH] [--dry-run]

Each YYYY-MM.txt file is parsed as YAML. Every day-entry becomes one encrypted
note. Re-running is safe: notes whose title already exists are skipped.
"""

import argparse
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from store import Note, Store


def extract_tags(text: str) -> list[str]:
    found = re.findall(r"#(\w+)", text)
    tags = list(dict.fromkeys(found))  # deduplicate, preserve order
    if "rednote" not in tags:
        tags.append("rednote")
    return tags


def parse_month_file(path: Path) -> list[tuple[str, str]]:
    """Return list of (date_str, body_text) pairs from a YYYY-MM.txt file."""
    year_month = path.stem  # "YYYY-MM"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"  WARNING: could not parse {path.name}: {e}", file=sys.stderr)
        return []
    if not isinstance(data, dict):
        return []
    entries = []
    for day, content in sorted(data.items(), key=lambda kv: int(kv[0])):
        if not isinstance(content, dict) or "text" not in content:
            continue
        text = content["text"] or ""
        if not isinstance(text, str):
            text = str(text)
        date_str = f"{year_month}-{int(day):02d}"
        entries.append((date_str, text.strip()))
    return entries


def main():
    parser = argparse.ArgumentParser(description="Import RednoteBook notes into notetaker")
    parser.add_argument(
        "--folder",
        default=str(Path.home() / "_docs" / "journal"),
        help="Path to folder containing YYYY-MM.txt files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing anything",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: folder not found: {folder}", file=sys.stderr)
        sys.exit(1)

    txt_files = sorted(folder.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {folder}", file=sys.stderr)
        sys.exit(1)

    store = Store()
    existing_titles = {n.title for n in store.notes.values()}

    now_ts = datetime.now().isoformat(timespec="seconds")
    imported = 0
    skipped = 0

    for path in txt_files:
        entries = parse_month_file(path)
        for date_str, body in entries:
            title = f"Legacy Rednote {date_str}"
            if title in existing_titles:
                skipped += 1
                continue
            tags = extract_tags(body)
            created_at = f"{date_str}T00:00:00"
            note = Note(
                id=str(uuid.uuid4()),
                date=date_str,
                title=title,
                body=body,
                tags=tags,
                created_at=created_at,
                updated_at=now_ts,
            )
            if args.dry_run:
                print(f"  [dry-run] would import: {title}  tags={tags}")
            else:
                store.save_note(note)
                existing_titles.add(title)
            imported += 1

    label = "Would import" if args.dry_run else "Imported"
    print(f"\n{label}: {imported}  |  Skipped (already exist): {skipped}  |  Total entries: {imported + skipped}")


if __name__ == "__main__":
    main()
