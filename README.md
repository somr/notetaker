# notetaker

A terminal note-taking app with an encrypted file store and a Claude Code-style interface.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

- **Split-pane TUI** — note panel (scrollable), message/output panel, command input line
- **Markdown rendering** — headings, bold, italic, inline code, lists, blockquotes, horizontal rules
- **In-app line editor** — move a cursor line through the note body with ↑/↓, insert, delete, or copy-edit lines without leaving the app
- **Encrypted storage** — every note is AES-GCM encrypted on disk; key stored at `~/.notetaker/key`
- **Tag system** — add multiple tags per note with TAB autocomplete
- **Full-text and tag search** — results shown as a numbered list; `/open <n>` to activate
- **Date organisation** — notes are attached to a date; one day can hold any number of notes

## Installation

```bash
pip install cryptography
```

That is the only external dependency. Everything else uses the Python standard library (`curses`, `json`, `hashlib`, `uuid`, `re`, `textwrap`).

## Running

```bash
python3 notetaker.py
```

Notes and the encryption key are stored in `~/.notetaker/`. The key file is created automatically on first run.

> **Security note:** the key and the encrypted notes share the same directory. Encryption protects against casual file access; for stronger protection, encrypt the home directory or the `~/.notetaker/` folder at the OS level.

## Commands

| Command | Description |
|---|---|
| `/create [date] <title>` | Create a note. Date defaults to today. |
| `/list [date]` | List all notes, or notes for a specific date. |
| `/tag <tag>` | Add a tag to the active note (TAB autocomplete). |
| `/untag <tag>` | Remove a tag from the active note. |
| `/search_tag <tag>` | Find all notes with a given tag. |
| `/search_text <text>` | Full-text search across all note titles and bodies. |
| `/open <n>` | Activate search result number *n*. |
| `/edit` | Enter the in-app line editor (Esc to exit). |
| `/delete` | Delete the active note (asks for confirmation). |
| `/show` | Refresh the note panel. |
| `/help` | Show the command list in the message panel. |
| `/exit` or `/quit` | Quit. |
| *(any other text)* | Append the line to the active note body. |

### Date formats

`today`, `yesterday`, `DD-Mon-YYYY` (e.g. `20-May-2026`), `YYYY-MM-DD`.

### Scrolling

| Key | Action |
|---|---|
| ↑ / ↓ | Scroll note panel one line |
| Page Up / Page Down | Scroll note panel half a page |

### In-app editor (`/edit`)

| Key / Input | Action |
|---|---|
| ↑ / ↓ | Move the `· · ·` cursor line up or down |
| text + Enter | Insert the text as a new line above the cursor |
| `/d` | Delete the line above the cursor |
| `/c` | Copy the line above into the input box; Enter replaces it |
| Esc | Exit edit mode |

## File structure

```
notetaker/
├── notetaker.py   # entry point
├── store.py       # encryption, note model, file I/O
├── commands.py    # command dispatcher and handlers
├── tui.py         # curses TUI, input loop, scrolling, edit mode
└── markdown.py    # markdown-to-curses renderer
```

Notes are stored as individually encrypted JSON files under `~/.notetaker/notes/*.enc`. All notes are decrypted into memory at startup; no external database is required.
