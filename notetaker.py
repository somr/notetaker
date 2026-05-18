#!/usr/bin/env python3
import curses
import sys

from commands import CommandHandler
from store import Store
from tui import TUI


def main():
    store = Store()
    handler = CommandHandler(store)

    def _run(stdscr):
        tui = TUI(stdscr)
        tui.run(handler)

    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
