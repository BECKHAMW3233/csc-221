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
                  wait until the user clicks Exit in the web page
                      OR presses Enter in this window, then stop the server
                  go back to the menu
        If the app can't start (missing data file, etc.) -> show the error
    4 -> display "Goodbye!", wait for Enter, then close
"""

import logging
import queue
import socket
import sqlite3
import sys
import threading
import webbrowser

from werkzeug.serving import make_server

HOST = "127.0.0.1"
EXIT_CHOICE = "4"
PROGRAMS = {
    "1": "Vet Services (M5Pro)",
    "2": "Recipe Manager (M3Pro)",
    "3": "Dungeon RPG (CSC-121 -> CTS-285)",
}


class Keyboard:
    """Reads lines typed in the launcher window on a background thread.

    input() blocks until Enter is pressed, so it can't also notice the Exit
    button being clicked in the browser. Reading on a background thread lets
    the launcher wait for whichever happens first.
    """

    def __init__(self, stream=None):
        self._stream = stream
        self._lines = queue.Queue()
        self._thread = None

    def _read_forever(self):
        stream = self._stream or sys.stdin
        while True:
            line = stream.readline()
            if not line:  # end of input (window closed or input was piped)
                self._lines.put(None)
                return
            self._lines.put(line.rstrip("\r\n"))

    def read_line(self, prompt="", stop_event=None):
        """Show the prompt and return the next line typed.

        Returns None if stop_event is set first (the Exit button was clicked).
        Raises EOFError when there is no more input.
        """
        print(prompt, end="", flush=True)
        if self._thread is None:
            self._thread = threading.Thread(target=self._read_forever, daemon=True)
            self._thread.start()
        while True:
            try:
                line = self._lines.get(timeout=0.1)
            except queue.Empty:
                if stop_event is not None and stop_event.is_set():
                    if prompt:
                        print()  # finish the prompt's line
                    return None
                continue
            if line is None:
                self._lines.put(None)  # keep reporting end of input
                raise EOFError
            return line


KEYBOARD = Keyboard()


def bring_launcher_to_front():
    """Try to bring the launcher window back to the front (Windows only).

    Windows may refuse and only flash the taskbar button, which is fine.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window = ctypes.windll.kernel32.GetConsoleWindow()
        if window:
            ctypes.windll.user32.SetForegroundWindow(window)
    except (AttributeError, OSError):
        pass


def turn_off_quick_edit():
    """Stop a mouse click in the launcher window from freezing the program (Windows only).

    In a Windows console, clicking the window starts "Select" mode, which
    pauses the program until Esc is pressed. A user who clicks the window to
    bring it to the front would think the launcher had hung.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # the keyboard input of this window
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            enable_quick_edit, enable_extended_flags = 0x0040, 0x0080
            kernel32.SetConsoleMode(handle, (mode.value & ~enable_quick_edit) | enable_extended_flags)
    except (AttributeError, OSError):
        pass  # not a real console (for example, input is piped in)


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


def run_web_app(app, name, open_browser=True, wait_for_stop=None):
    """Serve a Flask app until the user clicks Exit in the page or presses Enter here.

    wait_for_stop(prompt, stop_event) must return once the user wants to stop.
    The app's Exit button sets stop_event. Returns the URL the app was served at.
    """
    wait_for_stop = wait_for_stop or KEYBOARD.read_line
    stop_event = threading.Event()
    app.config["ON_EXIT"] = stop_event.set  # used by the Exit button (web_exit.py)
    server = make_server(HOST, find_free_port(), app, threaded=True)
    url = f"http://{HOST}:{server.server_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"\n{name} is running at {url}")
    if open_browser:
        print("Opening it in your web browser...")
        webbrowser.open(url)
    print("When you are done, click the red Exit button in the web page")
    print("(or press Enter here) to close the app and come back to this menu.")
    try:
        wait_for_stop("", stop_event)  # no prompt, so the app's own messages print on clean lines
    finally:
        server.shutdown()
        thread.join(timeout=5)
    if stop_event.is_set():
        print(f"{name} was closed from the web page.")
        bring_launcher_to_front()
    else:
        print(f"{name} stopped.")
    return url


def launch(choice, open_browser=True, wait_for_stop=None):
    """Build and run the chosen program, reporting startup errors instead of crashing.

    Returns True if the app ran, False if it couldn't start.
    """
    name = PROGRAMS[choice]
    print(f"\nStarting {name}...")
    try:
        app = build_app(choice)
        run_web_app(app, name, open_browser, wait_for_stop)
    except (FileNotFoundError, KeyError, ValueError, sqlite3.Error, OSError) as error:
        print(f"Could not start {name}: {error}")
        return False
    return True


def main(read_line=None):
    """Run the launcher menu until the user chooses Exit."""
    read_line = read_line or KEYBOARD.read_line
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keep the console tidy
    choice = ""
    while choice != EXIT_CHOICE:
        display_menu()
        try:
            choice = parse_menu_choice(read_line(f"Enter your choice (1-{EXIT_CHOICE}): "))
        except ValueError as error:
            print(f"Error: {error}")
        else:
            if choice != EXIT_CHOICE:
                launch(choice)
    print("\nGoodbye! Thanks for using the M7Lab Program Launcher.")


def wait_before_closing():
    """Keep the window open so the user can read the goodbye message."""
    try:
        KEYBOARD.read_line("Press Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # show each line right away, even when piped
    turn_off_quick_edit()
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye! Thanks for using the M7Lab Program Launcher.")
    wait_before_closing()
