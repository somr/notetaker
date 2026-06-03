from datetime import date, timedelta

from store import Note, Store

COMMANDS = [
    "/create", "/open", "/list", "/last", "/tags", "/tag", "/untag",
    "/search_tag", "/st", "/search_text", "/s", "/rename", "/duplicate",
    "/delete", "/edit", "/help", "/exit", "/quit",
]

DATE_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def parse_date(token: str) -> str:
    t = token.strip().lower()
    today = date.today()
    if t == "today":
        return today.isoformat()
    if t == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    # DD-Mon-YYYY  e.g. 20-May-2026
    parts = t.split("-")
    if len(parts) == 3 and parts[1] in DATE_MONTH_MAP:
        try:
            d, m, y = int(parts[0]), DATE_MONTH_MAP[parts[1]], int(parts[2])
            return f"{y:04d}-{m}-{d:02d}"
        except ValueError:
            pass
    # YYYY-MM-DD
    if len(parts) == 3 and len(parts[0]) == 4:
        try:
            y, m, d2 = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y:04d}-{m:02d}-{d2:02d}"
        except ValueError:
            pass
    raise ValueError(f"Unrecognised date: {token!r}. Use today/yesterday/DD-Mon-YYYY/YYYY-MM-DD")


class CommandHandler:
    def __init__(self, store: Store):
        self.store = store
        self.active: Note | None = None
        self._search_results: list[Note] = []
        self._pending_delete = False
        self._nav_idx: int = -1
        self._tag_list: list[str] = []
        self._tui = None  # set by TUI after construction
        # edit mode state
        self.edit_mode: bool = False
        self.edit_cursor: int = 0
        self._pending_copy_line: int | None = None

    def set_tui(self, tui):
        self._tui = tui

    def _msg(self, *lines):
        if self._tui:
            self._tui.show_message(list(lines))

    def _refresh_note(self):
        if self._tui:
            self._tui.update_note_panel(self.active)

    # ------------------------------------------------------------------ #
    # Dispatcher                                                           #
    # ------------------------------------------------------------------ #

    def dispatch(self, line: str) -> bool:
        """Returns False to signal quit."""
        if self._pending_delete:
            return self._confirm_delete(line.strip().lower())

        if self.edit_mode:
            return self._dispatch_edit(line)

        if not line.startswith("/"):
            self._handle_freetext(line)
            return True

        parts = line.split(None, 2)
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        handler = {
            "/create": self._cmd_create,
            "/open": self._cmd_open,
            "/list": self._cmd_list,
            "/last": self._cmd_last,
            "/tags": self._cmd_tags,
            "/tag": self._cmd_tag,
            "/untag": self._cmd_untag,
            "/search_tag": self._cmd_search_tag,
            "/st":          self._cmd_search_tag,
            "/search_text": self._cmd_search_text,
            "/s":           self._cmd_search_text,
            "/rename": self._cmd_rename,
            "/duplicate": self._cmd_duplicate,
            "/delete": self._cmd_delete,
            "/edit": self._cmd_edit,
            "/help": self._cmd_help,
            "/exit": lambda _: False,
            "/quit": lambda _: False,
        }.get(cmd)

        if handler is None:
            self._msg(f"Unknown command: {cmd}  (type /help for list)")
            return True

        result = handler(args)
        return result if result is not None else True

    # ------------------------------------------------------------------ #
    # Edit mode dispatch                                                   #
    # ------------------------------------------------------------------ #

    def _dispatch_edit(self, line: str) -> bool:
        if self._pending_copy_line is not None:
            idx = self._pending_copy_line
            self._pending_copy_line = None
            lines = self.active.body.splitlines()
            if idx < len(lines):
                lines[idx] = line
            self.active.body = "\n".join(lines) + "\n"
            self.store.save_note(self.active)
            self._refresh_note()
            self._msg("Line replaced.")
            return True

        if line == "/d":
            self._edit_delete()
        elif line == "/c":
            self._edit_copy()
        elif line.startswith("/"):
            self._msg("In edit mode — only /d and /c are allowed. Press Esc to exit.")
        else:
            self._edit_insert(line)
        return True

    def _edit_insert(self, text: str):
        lines = self.active.body.splitlines()
        lines.insert(self.edit_cursor, text)
        self.active.body = "\n".join(lines) + "\n"
        self.store.save_note(self.active)
        self._refresh_note()

    def _edit_delete(self):
        if self.edit_cursor == 0:
            self._msg("No line above cursor.")
            return
        lines = self.active.body.splitlines()
        if self.edit_cursor - 1 < len(lines):
            lines.pop(self.edit_cursor - 1)
            self.edit_cursor -= 1
        self.active.body = "\n".join(lines) + ("\n" if lines else "")
        self.store.save_note(self.active)
        self._refresh_note()

    def _edit_copy(self):
        if self.edit_cursor == 0:
            self._msg("No line above cursor.")
            return
        lines = self.active.body.splitlines()
        idx = self.edit_cursor - 1
        if idx >= len(lines):
            self._msg("No line above cursor.")
            return
        self._pending_copy_line = idx
        if self._tui:
            self._tui.set_input(lines[idx])
        self._msg("Edit the line above and press Enter to replace.")

    def exit_edit_mode(self):
        self.edit_mode = False
        self.edit_cursor = 0
        self._pending_copy_line = None
        self._refresh_note()
        self._msg("Edit mode exited.")

    def nav_next(self):
        self._navigate(-1)

    def nav_prev(self):
        self._navigate(+1)

    def _navigate(self, delta: int):
        lst = self._search_results if self._search_results else self.store.notes_sorted()
        if not lst:
            self._msg("No notes to navigate.")
            return
        if self._nav_idx < 0 or self._nav_idx >= len(lst):
            if self.active:
                ids = [n.id for n in lst]
                self._nav_idx = ids.index(self.active.id) if self.active.id in ids else -1
        self._nav_idx = (self._nav_idx + delta) % len(lst)
        self.active = lst[self._nav_idx]
        self._refresh_note()
        src = "results" if self._search_results else "all notes"
        self._msg(f"[{self._nav_idx + 1}/{len(lst)} {src}]  {self.active.date} | {self.active.title}")

    def edit_cursor_move(self, delta: int):
        if not self.edit_mode or not self.active:
            return
        lines = self.active.body.splitlines()
        self.edit_cursor = max(0, min(len(lines), self.edit_cursor + delta))
        self._refresh_note()

    # ------------------------------------------------------------------ #
    # Normal command implementations                                       #
    # ------------------------------------------------------------------ #

    def _handle_freetext(self, line: str):
        if not self.active:
            self._msg("No active note. Use /create to start one.")
            return
        self.active.body += line + "\n"
        self.store.save_note(self.active)
        self._refresh_note()

    def _cmd_create(self, args):
        if not args:
            self._msg("Usage: /create [date] <title>")
            return
        try:
            date_str = parse_date(args[0])
            title = " ".join(args[1:]) if len(args) > 1 else ""
        except ValueError:
            # first token isn't a date — treat everything as title, use today
            date_str = __import__("datetime").date.today().isoformat()
            title = " ".join(args)

        if not title:
            self._msg("Usage: /create [date] <title>  (title cannot be empty)")
            return

        self.active = self.store.new_note(date_str, title)
        self._search_results = []
        self._nav_idx = -1
        self._refresh_note()
        self._msg(f"Created: [{date_str}] {title}")

    def _cmd_open(self, args):
        if not args or not args[0].isdigit():
            self._msg("Usage: /open <number>  (from search results)")
            return
        idx = int(args[0]) - 1
        if idx < 0 or idx >= len(self._search_results):
            self._msg(f"No result #{args[0]}. Run a search first.")
            return
        self.active = self._search_results[idx]
        self._refresh_note()
        self._msg(f"Opened: [{self.active.date}] {self.active.title}")

    def _cmd_list(self, args):
        notes = self.store.notes_sorted()
        if args:
            try:
                filter_date = parse_date(args[0])
                notes = [n for n in notes if n.date == filter_date]
            except ValueError as e:
                self._msg(str(e))
                return

        if not notes:
            self._msg("No notes found.")
            return

        self._search_results = notes
        self._tag_list = []
        self._nav_idx = -1
        count = len(notes)
        header = f"Found {count} note{'s' if count != 1 else ''}:"
        lines = [header] + [
            f"{i+1}. {n.date} | {n.title}" + (f" [{', '.join(n.tags)}]" if n.tags else "")
            for i, n in enumerate(notes)
        ] + ["↑↓ scroll  —  /open <n> to activate"]
        self._msg(*lines)

    def _cmd_last(self, _args):
        notes = self.store.notes_sorted()
        if not notes:
            self._msg("No notes yet. Use /create to start one.")
            return
        self._search_results = []
        self._nav_idx = 0
        self.active = notes[0]
        self._refresh_note()
        self._msg(f"[most recent]  {self.active.date} | {self.active.title}")

    def _cmd_tags(self, _args):
        from collections import Counter
        counts = Counter(t for n in self.store.notes.values() for t in n.tags)
        if not counts:
            self._msg("No tags found.")
            return
        ordered = sorted(counts, key=lambda t: (-counts[t], t))
        self._search_results = []
        self._nav_idx = -1
        self._tag_list = ordered
        header = f"Found {len(ordered)} tag{'s' if len(ordered) != 1 else ''}:"
        lines = [header] + [
            f"{i+1}. {t} ({counts[t]})"
            for i, t in enumerate(ordered)
        ] + ["↑↓ scroll  —  Enter to search top-visible tag"]
        self._msg(*lines)

    def _cmd_tag(self, args):
        if not self.active:
            self._msg("No active note.")
            return
        if not args:
            self._msg("Usage: /tag <tag>")
            return
        tag = args[0].strip()
        if tag not in self.active.tags:
            self.active.tags.append(tag)
            self.store.save_note(self.active)
            self._refresh_note()
        self._msg(f"Tag '{tag}' added.")

    def _cmd_untag(self, args):
        if not self.active:
            self._msg("No active note.")
            return
        if not args:
            self._msg("Usage: /untag <tag>")
            return
        tag = args[0].strip()
        if tag in self.active.tags:
            self.active.tags.remove(tag)
            self.store.save_note(self.active)
            self._refresh_note()
            self._msg(f"Tag '{tag}' removed.")
        else:
            self._msg(f"Tag '{tag}' not on this note.")

    def _cmd_search_tag(self, args):
        if not args:
            self._msg("Usage: /search_tag <tag> [tag2 ...]  — AND filter")
            return
        tags = " ".join(args).split()
        results = [n for n in self.store.notes_sorted() if all(t in n.tags for t in tags)]
        label = " + ".join(f"'{t}'" for t in tags)
        self._present_results(results, f"tag {label}")

    def _cmd_search_text(self, args):
        if not args:
            self._msg("Usage: /search_text <text>")
            return
        query = " ".join(args).lower()
        results = [
            n for n in self.store.notes_sorted()
            if query in n.title.lower() or query in n.body.lower()
        ]
        self._present_results(results, f"'{query}'")

    def _present_results(self, results: list, label: str):
        if not results:
            self._msg(f"No notes found for {label}.")
            return
        self._search_results = results
        self._tag_list = []
        self._nav_idx = -1
        n = len(results)
        header = f"Found {n} note{'s' if n != 1 else ''} for {label}:"
        lines = [header] + [
            f"{i+1}. {r.date} | {r.title}" + (f" [{', '.join(r.tags)}]" if r.tags else "")
            for i, r in enumerate(results)
        ] + ["↑↓ scroll  —  /open <n> to activate"]
        self._msg(*lines)

    def _cmd_rename(self, args):
        if not self.active:
            self._msg("No active note.")
            return
        new_title = " ".join(args).strip()
        if not new_title:
            self._msg("Usage: /rename <new title>")
            return
        old_title = self.active.title
        self.active.title = new_title
        self.store.save_note(self.active)
        self._refresh_note()
        self._msg(f"Renamed: '{old_title}' → '{new_title}'")

    def _cmd_duplicate(self, args):
        if not self.active:
            self._msg("No active note to duplicate.")
            return
        today = date.today().isoformat()
        new_note = self.store.duplicate_note(self.active, today)
        if args:
            new_note.title = " ".join(args).strip()
            self.store.save_note(new_note)
        self._search_results = []
        self._nav_idx = -1
        self.active = new_note
        self._refresh_note()
        self._msg(f"Duplicated as: [{today}] {new_note.title}")

    def _cmd_delete(self, _args):
        if not self.active:
            self._msg("No active note to delete.")
            return
        self._pending_delete = True
        self._msg(f"Delete '{self.active.title}' ({self.active.date})? [y/n]")

    def _confirm_delete(self, answer: str) -> bool:
        self._pending_delete = False
        if answer == "y":
            title = self.active.title
            self.store.delete_note(self.active.id)
            self.active = None
            self._refresh_note()
            self._msg(f"Deleted '{title}'.")
        else:
            self._msg("Delete cancelled.")
        return True

    def _cmd_edit(self, _args):
        if not self.active:
            self._msg("No active note.")
            return
        self.edit_mode = True
        self.edit_cursor = 0
        self._refresh_note()
        self._msg("Edit mode. ↑↓ move cursor, text+Enter inserts above, /d delete, /c copy. Esc to exit.")

    def _cmd_help(self, _args):
        self._msg(
            "/create [date] <title>  — create note (date: today/yesterday/DD-Mon-YYYY/YYYY-MM-DD)",
            "/list [date]            — list notes",
            "/tags                   — list all tags with note counts",
            "/last                   — clear search, open the most recent note",
            "/tag <tag>              — add tag (TAB autocomplete)",
            "/untag <tag>            — remove tag (TAB autocomplete)",
            "/search_tag <tag> [...] — search by tag, multiple = AND  (alias: /st)",
            "/search_text <text>     — full-text search  (alias: /s)",
            "/rename <title>         — rename the active note",
            "/duplicate [new title]  — duplicate active note to today (optional rename)",
            "/open <n>               — activate search result #n",
            "/edit                   — enter in-app line editor (Esc to exit)",
            "/delete                 — delete active note",
            "/help                   — show this list",
            "/exit | /quit           — quit",
            "(free text)             — append line to active note body",
        )

    # ------------------------------------------------------------------ #
    # Completion helpers (called by TUI)                                   #
    # ------------------------------------------------------------------ #

    def completions_for(self, text: str) -> list:
        """Return completions for current input text."""
        if " " not in text:
            return [c for c in COMMANDS if c.startswith(text)]

        cmd, _, partial = text.partition(" ")
        cmd = cmd.lower()
        if cmd in ("/tag", "/untag", "/search_tag", "/st"):
            tags = self.store.all_tags()
            last = partial.rsplit(" ", 1)[-1]
            return [t for t in tags if t.startswith(last)]
        return []
