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
                  wait for the user to press Enter, then stop the server
        If the app can't start (missing data file, etc.) -> show the error
    4 -> display "Goodbye!", wait for Enter, then close
"""

import logging
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


def run_web_app(app, name, open_browser=True, wait_for_stop=input):
    """Serve a Flask app until the user presses Enter, then shut it down.

    Returns the URL the app was served at.
    """
    server = make_server(HOST, find_free_port(), app, threaded=True)
    url = f"http://{HOST}:{server.server_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"\n{name} is running at {url}")
    if open_browser:
        print("Opening it in your web browser...")
        webbrowser.open(url)
    try:
        wait_for_stop("Press Enter to stop this app and return to the menu... ")
    finally:
        server.shutdown()
        thread.join(timeout=5)
        print(f"{name} stopped.")
    return url


def launch(choice, open_browser=True, wait_for_stop=input):
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


def main():
    """Run the launcher menu until the user chooses Exit."""
    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keep the console tidy
    choice = ""
    while choice != EXIT_CHOICE:
        display_menu()
        try:
            choice = parse_menu_choice(input(f"Enter your choice (1-{EXIT_CHOICE}): "))
        except ValueError as error:
            print(f"Error: {error}")
        else:
            if choice != EXIT_CHOICE:
                launch(choice)
    print("\nGoodbye! Thanks for using the M7Lab Program Launcher.")


def wait_before_closing():
    """Keep the window open so the user can read the goodbye message."""
    try:
        input("Press Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # show each line right away, even when piped
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye! Thanks for using the M7Lab Program Launcher.")
    wait_before_closing()
