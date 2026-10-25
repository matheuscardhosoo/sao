"""
Underworld ASCII - Observer UI
Renders the 2D grid and Global Event Log using curses.
"""

import sys
import time
from typing import NoReturn

import requests

BASE_URL = "http://127.0.0.1:8000"
POLL_INTERVAL = 0.25


def fetch_world() -> dict | None:
    """Fetch full world state from server."""
    try:
        r = requests.get(f"{BASE_URL}/world", timeout=2)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def run_curses_ui() -> None:
    """Main curses loop: grid left, event log right."""
    import curses

    def draw(stdscr: "curses._CursesWindow") -> None:
        curses.curs_set(0)
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        grid_width = 24
        log_width = w - grid_width - 2

        while True:
            stdscr.erase()
            data = fetch_world()
            if data is None:
                stdscr.addstr(0, 0, "Waiting for server...")
                stdscr.refresh()
                time.sleep(POLL_INTERVAL)
                continue

            grid = data.get("grid", [])
            event_log = data.get("event_log", [])

            # Grid on left
            for y, row in enumerate(grid):
                if y >= h - 1:
                    break
                line = "".join(row[:grid_width])
                try:
                    stdscr.addstr(y, 0, line)
                except curses.error:
                    pass

            # Legend
            try:
                stdscr.addstr(h - 1, 0, "@ agent  ! resource  + trail  . empty")
            except curses.error:
                pass

            # Event log on right
            log_x = grid_width + 2
            log_lines = event_log[-h:] if event_log else ["No events yet"]
            for i, msg in enumerate(reversed(log_lines)):
                if i >= h - 1:
                    break
                line = msg[:log_width - 1] if len(msg) > log_width - 1 else msg
                try:
                    stdscr.addstr(i, log_x, line)
                except curses.error:
                    pass

            # Header for log
            try:
                stdscr.addstr(0, log_x, "Global Event Log", curses.A_BOLD)
            except curses.error:
                pass

            stdscr.refresh()
            time.sleep(POLL_INTERVAL)

    try:
        curses.wrapper(draw)
    except KeyboardInterrupt:
        pass


def run_fallback_ui() -> None:
    """Fallback: terminal-clearing loop when curses unavailable."""
    while True:
        data = fetch_world()
        if data is None:
            print("\rWaiting for server...", end="", flush=True)
            time.sleep(POLL_INTERVAL)
            continue

        # Clear screen (ANSI)
        print("\033[2J\033[H", end="")
        grid = data.get("grid", [])
        event_log = data.get("event_log", [])

        print("Underworld ASCII - Grid")
        print("-" * 24)
        for row in grid:
            print("".join(row))
        print("-" * 24)
        print("@ agent  ! resource  + trail  . empty")
        print()
        print("Global Event Log")
        print("-" * 40)
        for msg in event_log[-20:]:
            print(msg)
        print()
        time.sleep(POLL_INTERVAL)


def main() -> None:
    use_curses = "--no-curses" not in sys.argv
    if use_curses:
        try:
            import curses  # noqa: F401
            run_curses_ui()
        except ImportError:
            run_fallback_ui()
    else:
        run_fallback_ui()


if __name__ == "__main__":
    main()
