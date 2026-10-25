"""
Underworld - Observer UI
Polls GET /world/state every 500ms and displays the grid.
Uses walk_count > 5 for trail display: '+' else '.' (handled by API).
"""

import os
import sys
import time

import requests

BASE_URL = os.environ.get("UNDERWORLD_API_URL", "http://127.0.0.1:8000")
POLL_INTERVAL = 0.5


def fetch_world() -> dict | None:
    """Fetch full world state from server."""
    try:
        r = requests.get(f"{BASE_URL}/world/state", timeout=2)
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

            # Grid on left (API returns pre-computed chars: @ ! + .)
            for y, row in enumerate(grid):
                if y >= h - 1:
                    break
                line = "".join(row[:grid_width])
                try:
                    stdscr.addstr(y, 0, line)
                except curses.error:
                    pass

            try:
                stdscr.addstr(h - 1, 0, "@ agent  ! resource  + trail  . empty")
            except curses.error:
                pass

            log_x = grid_width + 2
            log_lines = event_log[-h:] if event_log else ["No events yet"]
            for i, msg in enumerate(reversed(log_lines)):
                if i >= h - 1:
                    break
                line = msg[: log_width - 1] if len(msg) > log_width - 1 else msg
                try:
                    stdscr.addstr(i, log_x, line)
                except curses.error:
                    pass

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

        print("\033[2J\033[H", end="")
        grid = data.get("grid", [])
        event_log = data.get("event_log", [])

        print("Underworld ASCII - Grid")
        print("-" * 24)
        for row in grid:
            print("".join(row))
        print("-" * 24)
        details = data.get("agent_details", {})
        if details:
            print("Active Entities:")
            for aid, a in details.items():
                status = "ACTIVE" if a.get("is_active") else "EXHAUSTED"
                print(f"  @{aid}: Energy={a.get('energy')}/100 | Crystals={a.get('inventory_count', 0)} | [{status}]")
            print()

        print("Global Event Log")
        print("-" * 40)
        for msg in event_log[-15:]:
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
