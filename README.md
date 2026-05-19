# notetaker

A terminal note-taking app with an encrypted file store and a Claude Code-style interface.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

- **Split-pane TUI** — note panel (scrollable), message/output panel, command input line
- **Markdown rendering** — headings, bold, italic, inline code, lists, blockquotes, horizontal rules
- **In-app line editor** — move a cursor line through the note body with ↑/↓, insert, delete, or copy-edit lines without leaving the app
- **Encrypted storage** — every note is AES-GCM encrypted on disk; key stored at `~/.notetaker/key`
- **Tag system** — add multiple tags per note with TAB autocomplete
- **Full-text and tag search** — results shown as a scrollable numbered list with match count; Enter opens the top-visible result
- **Keyboard navigation** — Tab / Shift+Tab cycles through notes (or search results when a search is active)
- **Date organisation** — notes are attached to a date; one day can hold any number of notes
- **RednoteBook importer** — bulk-import legacy journal files (see below)

## Installation

```bash
pip install cryptography pyyaml
```

Those are the only external dependencies. Everything else uses the Python standard library (`curses`, `json`, `uuid`, `re`, `textwrap`). `pyyaml` is only needed for the RednoteBook importer.

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
| `/last` | Clear search filters and open the most recent note. |
| `/tags` | List all tags sorted by note count; Enter searches the top-visible tag. |
| `/tag <tag>` | Add a tag to the active note (TAB autocomplete). |
| `/untag <tag>` | Remove a tag from the active note. |
| `/search_tag <tag> [tag2 ...]` or `/st <tag> [tag2 ...]` | Find notes that have all the given tags (AND). |
| `/search_text <text>` or `/s <text>` | Full-text search across all note titles and bodies. |
| `/rename <title>` | Rename the active note. |
| `/open <n>` | Activate search result number *n*. |
| `/edit` | Enter the in-app line editor (Esc to exit). |
| `/delete` | Delete the active note (asks for confirmation). |
| `/help` | Show the command list in the message panel. |
| `/exit` or `/quit` | Quit. |
| *(any other text)* | Append the line to the active note body. |

### Date formats

`today`, `yesterday`, `DD-Mon-YYYY` (e.g. `20-May-2026`), `YYYY-MM-DD`.

### Keyboard navigation

| Key | Action |
|---|---|
| Tab (empty input) | Open the next note toward a newer date (wraps around) |
| Shift+Tab (empty input) | Open the previous note toward an older date |
| ↑ / ↓ | Scroll search results when visible; otherwise scroll the note panel |
| Page Up / Page Down | Scroll note panel half a page |
| Enter (empty input, results shown) | Open the top-visible result in the message panel |
| Escape (results shown) | Dismiss the result list; restore note-panel scrolling |

Tab/Shift+Tab follow the active search results when a search is in scope, or all notes sorted by date otherwise. The message panel shows the current position, e.g. `[3/481 results]`. Use `/last` to clear search filters and return to full-collection navigation starting from the most recent note.

### In-app editor (`/edit`)

| Key / Input | Action |
|---|---|
| ↑ / ↓ | Move the `· · ·` cursor line up or down |
| text + Enter | Insert the text as a new line above the cursor |
| `/d` | Delete the line above the cursor |
| `/c` | Copy the line above into the input box; Enter replaces it |
| Esc | Exit edit mode |

## Importing from RednoteBook

`import_rednote.py` reads monthly journal files (`YYYY-MM.txt`) exported by RednoteBook and imports them as encrypted notetaker notes.

```bash
# Dry run — prints what would be imported, writes nothing
python3 import_rednote.py --dry-run

# Import from default folder (~/docs/journal)
python3 import_rednote.py

# Import from a custom folder
python3 import_rednote.py --folder /path/to/journal
```

Each day-entry becomes one note titled `Legacy Rednote YYYY-MM-DD`. `#hashtags` in the body are extracted as tags; all imported notes also receive a `rednote` tag. Re-running is safe — notes with an existing title are skipped.

## File structure

```
notetaker/
├── notetaker.py       # entry point
├── store.py           # encryption, note model, file I/O
├── commands.py        # command dispatcher and handlers
├── tui.py             # curses TUI, input loop, scrolling, edit mode
├── markdown.py        # markdown-to-curses renderer
└── import_rednote.py  # RednoteBook bulk importer (standalone script)
```

Notes are stored as individually encrypted JSON files under `~/.notetaker/notes/*.enc`. All notes are decrypted into memory at startup; no external database is required.
