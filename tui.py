import curses

from markdown import body_to_lines

MSG_PANEL_LINES = 6
HEADER_LINES = 1
INPUT_LINES = 1
MIN_NOTE_LINES = 3

EDIT_CURSOR_CHAR = "· "


class TUI:
    def __init__(self, stdscr):
        self._scr = stdscr
        self._handler = None
        self._input_buf = []   # list of chars
        self._cur_pos = 0      # cursor position in _input_buf
        self._completions = []
        self._comp_idx = -1
        self._pre_tab_buf = None
        self._note_scroll = 0
        self._displayed_note_id = None
        self._setup_curses()
        self._build_windows()

    def _setup_curses(self):
        curses.curs_set(1)
        curses.use_default_colors()
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, -1)    # header / borders
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # note title / date
        curses.init_pair(3, curses.COLOR_GREEN, -1)   # tags
        curses.init_pair(4, curses.COLOR_WHITE, -1)   # body / messages
        curses.init_pair(5, curses.COLOR_MAGENTA, -1) # edit cursor line
        self._scr.keypad(True)
        self._scr.timeout(100)

    def _build_windows(self):
        rows, cols = self._scr.getmaxyx()
        note_rows = max(MIN_NOTE_LINES, rows - HEADER_LINES - MSG_PANEL_LINES - INPUT_LINES - 3)

        self._rows = rows
        self._cols = cols

        header_y = 0
        note_y   = HEADER_LINES + 1
        msg_y    = note_y + note_rows + 1
        input_y  = msg_y + MSG_PANEL_LINES + 1

        self._header_win = curses.newwin(HEADER_LINES, cols, header_y, 0)
        self._note_win   = curses.newwin(note_rows, cols, note_y, 0)
        self._msg_win    = curses.newwin(MSG_PANEL_LINES, cols, msg_y, 0)
        self._input_win  = curses.newwin(INPUT_LINES, cols, input_y, 0)

        self._note_rows = note_rows
        self._input_y   = input_y

        self._draw_chrome()

    def _draw_chrome(self):
        cols = self._cols
        self._scr.attron(curses.color_pair(1))
        try:
            self._scr.hline(HEADER_LINES, 0, curses.ACS_HLINE, cols)
            msg_y = HEADER_LINES + 1 + self._note_rows
            self._scr.hline(msg_y, 0, curses.ACS_HLINE, cols)
            self._scr.hline(msg_y + MSG_PANEL_LINES + 1, 0, curses.ACS_HLINE, cols)
        except curses.error:
            pass
        self._scr.attroff(curses.color_pair(1))
        self._scr.noutrefresh()

    # ------------------------------------------------------------------ #
    # Public drawing API                                                   #
    # ------------------------------------------------------------------ #

    def draw_header(self, count: int):
        w = self._header_win
        w.erase()
        edit_mode = self._handler.edit_mode if self._handler else False
        title = "NOTETAKER -- EDIT MODE --" if edit_mode else "NOTETAKER"
        info = f"[{count} note{'s' if count != 1 else ''}]"
        padding = max(0, self._cols - len(title) - len(info) - 2)
        try:
            w.addstr(0, 1, title, curses.color_pair(1) | curses.A_BOLD)
            w.addstr(0, 1 + len(title) + padding, info, curses.color_pair(1))
        except curses.error:
            pass
        w.noutrefresh()

    def update_note_panel(self, note):
        w = self._note_win
        w.erase()
        rows, cols = w.getmaxyx()
        edit_mode   = self._handler.edit_mode   if self._handler else False
        edit_cursor = self._handler.edit_cursor if self._handler else 0

        # Reset scroll when switching to a different note
        note_id = note.id if note else None
        if note_id != self._displayed_note_id:
            self._note_scroll = 0
            self._displayed_note_id = note_id

        if note is None:
            try:
                w.addstr(0, 1, "No active note. Type /create [date] <title> to start.",
                         curses.color_pair(4))
            except curses.error:
                pass
            w.noutrefresh()
            curses.doupdate()
            return

        # Fixed header: title + optional tags + blank line (always visible, never scrolls)
        row = 0
        date_title = f" {note.date} | {note.title} "
        try:
            w.addstr(row, 1, date_title[:cols - 2], curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass
        row += 1

        if note.tags and row < rows:
            try:
                w.addstr(row, 0, (" Tags: " + ", ".join(note.tags))[:cols - 1],
                         curses.color_pair(3))
            except curses.error:
                pass
            row += 1

        row += 1  # blank separator
        body_start_row = row
        available = max(0, rows - body_start_row)

        if edit_mode:
            body_lines = note.body.splitlines() if note.body else []
            dot_line   = (EDIT_CURSOR_CHAR * (cols // 2))[:cols - 1]

            # Build flat list of visual items: ('cursor',) or ('line', text)
            items = []
            for i, line in enumerate(body_lines):
                if i == edit_cursor:
                    items.append(('cursor',))
                items.append(('line', line))
            if edit_cursor >= len(body_lines):
                items.append(('cursor',))

            # Auto-scroll so the cursor line stays in view
            if edit_cursor < self._note_scroll:
                self._note_scroll = edit_cursor
            elif edit_cursor >= self._note_scroll + available:
                self._note_scroll = edit_cursor - available + 1
            self._note_scroll = max(0, min(self._note_scroll,
                                           max(0, len(items) - available)))

            for item in items[self._note_scroll : self._note_scroll + available]:
                if row >= rows:
                    break
                if item[0] == 'cursor':
                    try:
                        w.addstr(row, 0, dot_line, curses.color_pair(5) | curses.A_DIM)
                    except curses.error:
                        pass
                else:
                    try:
                        w.addstr(row, 1, item[1][:cols - 2], curses.color_pair(4))
                    except curses.error:
                        pass
                row += 1

        else:
            # Normal mode: markdown rendering with scroll
            all_lines = body_to_lines(note.body, cols) if note.body else []
            total = len(all_lines)
            self._note_scroll = max(0, min(self._note_scroll,
                                           max(0, total - available)))

            for vline in all_lines[self._note_scroll : self._note_scroll + available]:
                if row >= rows:
                    break
                for col, text, attr in vline:
                    try:
                        w.addstr(row, col, text, attr)
                    except curses.error:
                        pass
                row += 1

            # Scroll indicators
            ind_attr = curses.color_pair(1) | curses.A_DIM
            if self._note_scroll > 0 and body_start_row < rows:
                try:
                    w.addstr(body_start_row, cols - 8, ' ↑ more', ind_attr)
                except curses.error:
                    pass
            if self._note_scroll + available < total and rows > 1:
                try:
                    w.addstr(rows - 1, cols - 8, ' ↓ more', ind_attr)
                except curses.error:
                    pass

        w.noutrefresh()
        curses.doupdate()

    def show_message(self, lines: list):
        w = self._msg_win
        w.erase()
        rows, cols = w.getmaxyx()
        for i, line in enumerate(lines[:rows]):
            try:
                w.addstr(i, 1, line[:cols - 2], curses.color_pair(4))
            except curses.error:
                pass
        w.noutrefresh()
        curses.doupdate()

    def set_input(self, text: str):
        self._input_buf = list(text)
        self._cur_pos = len(self._input_buf)

    def _redraw_input(self):
        w = self._input_win
        w.erase()
        cols = self._cols
        prompt = "> "
        buf_str = "".join(self._input_buf)
        visible_width = cols - len(prompt) - 1
        start = max(0, self._cur_pos - visible_width + 1)
        visible = buf_str[start:start + visible_width]
        try:
            w.addstr(0, 0, prompt, curses.color_pair(1) | curses.A_BOLD)
            w.addstr(0, len(prompt), visible, curses.color_pair(4))
            cursor_x = len(prompt) + (self._cur_pos - start)
            w.move(0, min(cursor_x, cols - 1))
        except curses.error:
            pass
        w.noutrefresh()
        curses.doupdate()

    def _full_redraw(self, note, count):
        self._draw_chrome()
        self.draw_header(count)
        self.update_note_panel(note)
        self.show_message([])
        self._redraw_input()

    # ------------------------------------------------------------------ #
    # Tab completion                                                       #
    # ------------------------------------------------------------------ #

    def _do_tab(self):
        if self._handler is None:
            return
        text = "".join(self._input_buf)
        if self._pre_tab_buf is None:
            self._pre_tab_buf = text
            self._completions = self._handler.completions_for(text)
            self._comp_idx = -1

        if not self._completions:
            self._pre_tab_buf = None
            return

        self._comp_idx = (self._comp_idx + 1) % len(self._completions)
        completion = self._completions[self._comp_idx]

        if " " in self._pre_tab_buf:
            prefix = self._pre_tab_buf.rsplit(" ", 1)[0] + " "
        else:
            prefix = ""
        new_text = prefix + completion
        self._input_buf = list(new_text)
        self._cur_pos = len(self._input_buf)

    # ------------------------------------------------------------------ #
    # Main run loop                                                        #
    # ------------------------------------------------------------------ #

    def run(self, handler):
        self._handler = handler
        handler.set_tui(self)
        self._full_redraw(handler.active, len(handler.store.notes))

        while True:
            self._redraw_input()
            try:
                ch = self._scr.get_wch()
            except curses.error:
                continue

            # Reset tab state on any non-TAB keystroke
            if ch != "\t" and ch != curses.KEY_BTAB:
                self._pre_tab_buf = None
                self._completions = []
                self._comp_idx = -1

            if ch == curses.KEY_RESIZE:
                self._build_windows()
                self._full_redraw(handler.active, len(handler.store.notes))

            elif ch == "\x1b":  # Escape — exit edit mode
                if handler.edit_mode:
                    handler.exit_edit_mode()
                    self.draw_header(len(handler.store.notes))

            elif ch in ("\n", "\r", curses.KEY_ENTER):
                line = "".join(self._input_buf).strip()
                self._input_buf = []
                self._cur_pos = 0
                if line:
                    keep_going = handler.dispatch(line)
                    self.draw_header(len(handler.store.notes))
                    if not keep_going:
                        break

            elif ch == "\t":
                self._do_tab()

            elif ch == curses.KEY_UP:
                if handler.edit_mode:
                    handler.edit_cursor_move(-1)
                    self.draw_header(len(handler.store.notes))
                else:
                    self._note_scroll = max(0, self._note_scroll - 1)
                    self.update_note_panel(handler.active)

            elif ch == curses.KEY_DOWN:
                if handler.edit_mode:
                    handler.edit_cursor_move(1)
                    self.draw_header(len(handler.store.notes))
                else:
                    self._note_scroll += 1  # clamped inside update_note_panel
                    self.update_note_panel(handler.active)

            elif ch == curses.KEY_PPAGE:  # Page Up
                self._note_scroll = max(0, self._note_scroll - max(1, self._note_rows // 2))
                self.update_note_panel(handler.active)

            elif ch == curses.KEY_NPAGE:  # Page Down
                self._note_scroll += max(1, self._note_rows // 2)
                self.update_note_panel(handler.active)

            elif ch in ("\x7f", "\x08", curses.KEY_BACKSPACE):
                if self._cur_pos > 0:
                    self._input_buf.pop(self._cur_pos - 1)
                    self._cur_pos -= 1

            elif ch == curses.KEY_DC:  # Delete key
                if self._cur_pos < len(self._input_buf):
                    self._input_buf.pop(self._cur_pos)

            elif ch == curses.KEY_LEFT:
                self._cur_pos = max(0, self._cur_pos - 1)

            elif ch == curses.KEY_RIGHT:
                self._cur_pos = min(len(self._input_buf), self._cur_pos + 1)

            elif ch == curses.KEY_HOME or ch == "\x01":  # Home / Ctrl-A
                self._cur_pos = 0

            elif ch == curses.KEY_END or ch == "\x05":   # End / Ctrl-E
                self._cur_pos = len(self._input_buf)

            elif ch == "\x03":  # Ctrl-C
                break

            elif isinstance(ch, str) and ch.isprintable():
                self._input_buf.insert(self._cur_pos, ch)
                self._cur_pos += 1

            elif isinstance(ch, int) and 32 <= ch < 127:
                self._input_buf.insert(self._cur_pos, chr(ch))
                self._cur_pos += 1
