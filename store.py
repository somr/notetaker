import json
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DATA_DIR = Path.home() / ".notetaker"
KEY_FILE = DATA_DIR / "key"
NOTES_DIR = DATA_DIR / "notes"
NONCE_SIZE = 12


@dataclass
class Note:
    id: str
    date: str          # ISO: "YYYY-MM-DD"
    title: str
    body: str
    tags: list
    url: str           # optional URL attachment
    created_at: str
    updated_at: str

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "url": self.url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(d):
        return Note(
            id=d["id"],
            date=d["date"],
            title=d["title"],
            body=d.get("body", ""),
            tags=d.get("tags", []),
            url=d.get("url", ""),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )


class Store:
    def __init__(self):
        self._setup_dirs()
        self._key = self._load_key()
        self._aesgcm = AESGCM(self._key)
        self.notes: dict[str, Note] = {}
        self._load_all()

    def _setup_dirs(self):
        DATA_DIR.mkdir(mode=0o700, exist_ok=True)
        NOTES_DIR.mkdir(mode=0o700, exist_ok=True)

    def _load_key(self) -> bytes:
        if KEY_FILE.exists():
            return KEY_FILE.read_bytes()
        key = secrets.token_bytes(32)
        KEY_FILE.write_bytes(key)
        KEY_FILE.chmod(0o600)
        return key

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        return nonce + self._aesgcm.encrypt(nonce, plaintext, None)

    def decrypt(self, data: bytes) -> bytes:
        nonce, ct = data[:NONCE_SIZE], data[NONCE_SIZE:]
        return self._aesgcm.decrypt(nonce, ct, None)

    def _load_all(self):
        for path in NOTES_DIR.glob("*.enc"):
            try:
                raw = self.decrypt(path.read_bytes())
                note = Note.from_dict(json.loads(raw))
                self.notes[note.id] = note
            except Exception:
                pass  # corrupt / tampered file, skip silently

    def save_note(self, note: Note):
        note.updated_at = datetime.now().isoformat(timespec="seconds")
        raw = json.dumps(note.to_dict()).encode()
        path = NOTES_DIR / f"{note.id}.enc"
        path.write_bytes(self.encrypt(raw))
        path.chmod(0o600)
        self.notes[note.id] = note

    def delete_note(self, note_id: str):
        path = NOTES_DIR / f"{note_id}.enc"
        if path.exists():
            path.unlink()
        self.notes.pop(note_id, None)

    def all_tags(self) -> list:
        tags = set()
        for note in self.notes.values():
            tags.update(note.tags)
        return sorted(tags)

    def notes_sorted(self) -> list:
        return sorted(self.notes.values(), key=lambda n: (n.date, n.created_at), reverse=True)

    def new_note(self, date: str, title: str) -> Note:
        now = datetime.now().isoformat(timespec="seconds")
        note = Note(
            id=str(uuid.uuid4()),
            date=date,
            title=title,
            body="",
            tags=[],
            url="",
            created_at=now,
            updated_at=now,
        )
        self.save_note(note)
        return note

    def duplicate_note(self, source: Note, new_date: str) -> Note:
        now = datetime.now().isoformat(timespec="seconds")
        note = Note(
            id=str(uuid.uuid4()),
            date=new_date,
            title=source.title,
            body=source.body,
            tags=list(source.tags),
            url=source.url,
            created_at=now,
            updated_at=now,
        )
        self.save_note(note)
        return note
