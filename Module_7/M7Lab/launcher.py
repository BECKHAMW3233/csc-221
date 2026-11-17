"""
M7Lab - Program Launcher
Author: William Beckham
Course: CSC-221 Advanced Python Programming

Lets the user pick one of three Flask web programs:
    1) Vet Services (M5Pro)            - CSC-221
    2) Recipe Manager (M3Pro)          - CSC-221
    3) Dungeon RPG                     - started in CSC-121, built up in CTS-285

Pseudocode:
    Display the launcher menu (1-4)
    While the user has not chosen Exit (4):
        Validate the choice (invalid -> show an error and redisplay the menu)
        1, 2 or 3 -> build that Flask app
                  start it on a free local port in a background thread
                  open it in the web browser
                  wait until the user presses Enter here OR clicks
                  "Exit app" in the browser, then stop the server
        If the app can't start (missing data file, etc.) -> show the error
    4 -> display "Goodbye!", wait for Enter, then close
"""

import logging
import queue
import socket
import sqlite3
import sys
import threading
import time
import webbrowser

from werkzeug.serving import make_server

from web_exit import EXIT_CONFIG_KEY

HOST = "127.0.0.1"
EXIT_CHOICE = "4"
PROGRAMS = {
    "1": "Vet Services (M5Pro)",
    "2": "Recipe Manager (M3Pro)",
    "3": "Dungeon RPG (CSC-121 -> CTS-285)",
}
STOP_PROMPT = ("Press Enter here (or click 'Exit app' in the browser) "
               "to stop this app and return to the menu... ")


class ConsoleInput:
    """Reads lines typed in the console on one background thread.

    Waiting with input() would block until Enter is pressed, so the launcher
    couldn't also notice the browser's Exit button. Reading on a background
    thread lets read() wait for whichever happens first, and a line typed
    later is never lost - it is simply returned by the next read().
    """

    _EOF = object()

    def __init__(self, stream=None):
        self._stream = stream if stream is not None else sys.stdin
        self._lines = queue.Queue()
        self._thread = None

    def _reader(self):
        while True:
            line = self._stream.readline()
            if not line:
                self._lines.put(self._EOF)
                return
            self._lines.put(line)

    def read(self, prompt="", stop_event=None):
        """Show prompt and return the next typed line (without the newline).

        Returns None if stop_event is set before a line arrives. Raises
        EOFError if the input stream has ended.
        """
        if self._thread is None:
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()
        print(prompt, end="", flush=True)
        while True:
            try:
                line = self._lines.get(timeout=0.1)
            except queue.Empty:
                if stop_event is not None and stop_event.is_set():
                    print()
                    return None
                continue
            if line is self._EOF:
                self._lines.put(self._EOF)  # keep reporting end-of-input
                raise EOFError
            return line.rstrip("\r\n")


def display_menu():
    """Print the launcher menu."""
    print("\n=== M7Lab Program Launcher ===")
    for key, name in PROGRAMS.items():
        print(f"{key}) {name} - Flask web app")
    print(f"{EXIT_CHOICE}) Exit")


def parse_menu_choice(text):
    """Return the cleaned menu choice, raising ValueError if it isn't on the menu."""
    choice = str(text).strip()
    if choice not in PROGRAMS and choice != EXIT_CHOICE:
        raise ValueError(f"'{choice}' is not a valid option. Please enter a number from 1 to {EXIT_CHOICE}.")
    return choice


def find_free_port():
    """Ask the operating system for an unused local port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def build_app(choice):
    """Create the Flask app for a menu choice ("1", "2" or "3")."""
    if choice == "1":
        from vet_app import create_app
    elif choice == "2":
        from recipe_app import create_app
    else:
        from rpg_app import create_app
    return create_app()


def run_web_app(app, name, console, open_browser=True):
    """Serve a Flask app until the user presses Enter or clicks "Exit app".

    Returns "enter" or "browser" to say which one stopped it.
    """
    stop_event = threading.Event()
    app.config[EXIT_CONFIG_KEY] = stop_event.set
    server = make_server(HOST, find_free_port(), app, threaded=True)
    url = f"http://{HOST}:{server.server_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"\n{name} is running at {url}")
    if open_browser:
        print("Opening it in your web browser...")
        webbrowser.open(url)
    try:
        typed = console.read(STOP_PROMPT, stop_event)
        stopped_by = "enter" if typed is not None else "browser"
        if stopped_by == "browser":
            print(f"'Exit app' was clicked in the browser - closing {name}.")
            time.sleep(0.5)  # let the browser receive the "app closed" page first
    finally:
        server.shutdown()
        thread.join(timeout=5)
        print(f"{name} stopped.")
    return stopped_by


def launch(choice, console, open_browser=True):
    """Build and run the chosen program, reporting startup errors instead of crashing.

    Returns True if the app ran, False if it couldn't start.
    """
    name = PROGRAMS[choice]
    print(f"\nStarting {name}...")
    try:
        app = build_app(choice)
        run_web_app(app, name, console, open_browser)
    except (FileNotFoundError, KeyError, ValueError, sqlite3.Error, OSError) as error:
        print(f"Could not start {name}: {error}")
        return False
    return True


def main(console=None, open_browser=True):
    """Run the launcher menu until the user chooses Exit."""
    console = console or ConsoleInput()
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keep the console tidy
    choice = ""
    while choice != EXIT_CHOICE:
        display_menu()
        try:
            choice = parse_menu_choice(console.read(f"Enter your choice (1-{EXIT_CHOICE}): "))
        except ValueError as error:
            print(f"Error: {error}")
        else:
            if choice != EXIT_CHOICE:
                launch(choice, console, open_browser)
    print("\nGoodbye! Thanks for using the M7Lab Program Launcher.")


def wait_before_closing(console):
    """Keep the window open so the user can read the goodbye message."""
    try:
        console.read("Press Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # show each line right away, even when piped
    console_input = ConsoleInput()
    try:
        main(console_input)
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye! Thanks for using the M7Lab Program Launcher.")
    wait_before_closing(console_input)
