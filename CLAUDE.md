# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```bash
# Install the one external dependency (first time only)
pip install cryptography

# Run
python3 notetaker/notetaker.py
```

Notes and key are stored in `~/.notetaker/`. The 32-byte AES key lives at `~/.notetaker/key` (created on first run, `chmod 600`). Each note is a separate AES-GCM encrypted JSON file under `~/.notetaker/notes/*.enc`.

## Architecture

Four modules, no framework:

| File | Role |
|------|------|
| `notetaker.py` | Entry point — instantiates `Store`, `CommandHandler`, `TUI` and calls `curses.wrapper` |
| `store.py` | `Store` class: key management, AES-GCM encrypt/decrypt, load-all-notes-at-startup into `self.notes: dict[str, Note]`, save/delete |
| `commands.py` | `CommandHandler`: holds the active note reference and `_search_results`; `dispatch(line)` routes to `_cmd_*` methods; `completions_for(text)` drives TAB completion |
| `tui.py` | `TUI`: curses split-pane (header / note panel / message panel / input line); custom char-by-char input loop; TAB cycling; edit mode rendering with dotted cursor line |

### Data flow

1. `TUI.run()` loops reading `get_wch()`.
2. On Enter: calls `CommandHandler.dispatch(line)`.
3. Handlers call back into `TUI` via `self._msg(...)` / `self._refresh_note()` (set via `handler.set_tui(tui)` after construction).
4. `Store` is the only component that touches the filesystem.

### Key invariants

- All notes are decrypted into memory at startup — no lazy loading.
- `store.save_note()` regenerates a fresh nonce on every write.
- `CommandHandler._pending_delete` is a boolean flag that makes the next dispatched line a y/n confirmation instead of a command.
- Edit mode state lives in `CommandHandler` (`edit_mode`, `edit_cursor`, `_pending_copy_line`). `TUI.update_note_panel()` reads these to render the dotted cursor line. In edit mode, word-wrap is disabled so the cursor index maps 1:1 to visual rows. `/c` sets `_pending_copy_line` and populates the input box via `tui.set_input()`; the next dispatched line replaces that body line.
- TAB completion state (`_pre_tab_buf`, `_completions`, `_comp_idx`) resets on any non-TAB keystroke.

## Commands

| Input | Effect |
|-------|--------|
| `/create [date] <title>` | Create note; date defaults to today |
| `/list [date]` | List notes (date: `today`/`yesterday`/`DD-Mon-YYYY`/`YYYY-MM-DD`) |
| `/tag <tag>` | Add tag to active note (TAB autocomplete) |
| `/untag <tag>` | Remove tag (TAB autocomplete) |
| `/search_tag <tag>` | Filter by tag |
| `/search_text <text>` | Full-text search in title + body |
| `/open <n>` | Activate search result #n |
| `/edit` | Enter in-app line editor (↑↓ move cursor, text+Enter inserts above cursor, `/d` delete line above, `/c` copy line above to input for editing, Esc exits) |
| `/delete` | Delete active note (y/n confirmation) |
| `/show` | Refresh note panel |
| `/help` | List all commands |
| `/exit` / `/quit` | Quit |
| *(any other text)* | Append line to active note body |
