# M7Lab - Program Launcher (PyInstaller)

**William Beckham · CSC-221 Advanced Python Programming**

This project combines three of my programs into one launcher, and all of
them run as **Flask web apps**:

| Choice | Program | Where it came from |
|---|---|---|
| 1 | Vet Services: owners, pets, charges and breed search (SQLite) | CSC-221 M5Pro |
| 2 | Recipe Manager: view, search, filter and adjust levels (Excel) | CSC-221 M3Pro |
| 3 | Dungeon RPG: D&D 5e-style world map, dungeons, combat, shops, quests and skills | Started in **CSC-121**, built up in **CTS-285** (M3A), now converted to Flask |
| 4 | Exit: says **Goodbye!**, then waits for Enter before closing | |

The Dungeon RPG closes the loop on my programming classes. It began as a
CSC-121 project and grew into a Tkinter desktop game in CTS-285. For this lab
its Tkinter screens were rewritten as web pages. The game rules are the
original code: characters, combat, dungeons, the world map, merchants and
quests.

When you pick 1, 2 or 3, the launcher starts that Flask app and opens it in your
web browser. **Every page has a red Exit button** in the top-right corner.
Clicking it closes that program and the launcher goes straight back to its
menu, so you can pick another program or choose 4 to exit. (Pressing
**Enter** in the launcher window also stops the app.) The Dungeon RPG asks
for confirmation first, because unsaved progress would be lost.

## Run from source

Use a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
python launcher.py
```

## Run the unit tests

```bash
python -m unittest discover -s tests -v
```

There are 70 tests covering the launcher, all three programs' functions and every
Flask page, including bad input, missing data files, combat outcomes,
save/load, and each program's Exit button returning to the launcher menu.

## Build the .exe (Windows)

**The Windows `.exe` is already built:** I built `dist/M7Lab_Launcher.exe`
on my own PC (Windows 11, Python 3.14.6, PyInstaller 6.22.3) with
`build_exe.bat`. All 70 unit tests passed during the build, and 20 of 20
checks passed when running the `.exe`. Every step, with screenshots from
my desktop, is in `docs/EXE_CONVERSION.md`. The logs are in `docs/local_build/`.

To build it yourself:

Double-click **`build_exe.bat`**. It creates the venv, installs PyInstaller
and the packages, runs the tests, and builds `dist\M7Lab_Launcher.exe`.
Then make the submission zip (code + exe, no venv):

```bash
python make_submission_zip.py
```

See [`docs/EXE_CONVERSION.md`](docs/EXE_CONVERSION.md) for the step-by-step
conversion with screenshots.

## Project layout

```
M7Lab_beckhamwilliam/
├── launcher.py            entry point (the .exe starts here)
├── build_exe.bat          Windows: venv + install + tests + PyInstaller build
├── make_submission_zip.py makes the submission zip (code + exe, no venv)
├── app_paths.py           file paths that work in Python and inside the .exe
├── vet_app/               M5Pro: Flask app, classes, functions, data/vet_serv.db
├── recipe_app/            M3Pro: Flask app, classes, loader, data/recipe_data.xlsx
├── rpg_app/               Dungeon RPG: Flask app + controller.py (replaces the Tkinter GUI)
│   └── game/              original game rules: models/, dice.py, database.py, config.py, data/*.json
├── templates/             HTML pages for all three apps
├── tests/                 test_m7lab.py (launcher, M5Pro, M3Pro) and test_rpg.py (Dungeon RPG)
├── web_exit.py            the Exit button route shared by all three Flask apps
├── docs/                  EXE_CONVERSION.md, screenshots, local_build/ (build and run logs)
├── dist/M7Lab_Launcher.exe  the Windows .exe (built on my PC with build_exe.bat)
└── requirements.txt
```

The program writes CSV files to `output/`, log files to `logs/` and RPG save
games to `saves/`. These folders are created next to `launcher.py`, or next
to the `.exe` when you run the built program.

**Note on RPG saves:** like the original game, a save stores the whole
500×500 world, so each save file is about 40 MB and takes a couple of seconds
to write.

## Dungeon RPG: what changed in the web version

- **Kept as-is:** `models/` (character, combat, dungeon, enemy, merchant,
  quests, world map), `dice.py`, `database.py` and every `data/*.json` file.
  Only the import lines and the folder paths in `config.py` changed, so the
  game works inside the `.exe`.
- **Replaced:** the Tkinter windows. `rpg_app/controller.py` is a port of the
  old `main.py` `Game` class plus the combat turn logic from
  `gui/combat_window.py`, with no GUI code. Message boxes became on-page
  messages, and yes/no dialogs became confirmation panels.
- **Controls:** W/A/S/D move, E interact, I inventory, K skills, C camp,
  R scout and Esc menu all work in the browser. Every action also has a button.
- **Small web extras:** pressing E on a village or town reopens its shop
  without stepping off and back on. Loading a save picks from a list instead
  of typing the file name, which also blocks file-path tricks.
- **Left out:** the UI zoom buttons and window auto-sizing. The browser's own
  Ctrl +/- zoom does the same job.

## Changes made from instructor feedback

**M5Pro**
- The program no longer crashes when `vet_serv.db` is missing. It now shows a
  clear "Database file not found" message. (Before, `sqlite3.connect()` silently
  created an empty database and the first query crashed.)

**M3Pro**
1. A missing sweetness or spice level now shows as *"Not specified in the
   recipe data"* instead of silently showing 1. Caesar Salad is the example.
2. `adjust_sweetness()` and `adjust_spice()` are now used by a new
   **Adjust sweetness / spice** option.
3. Search ignores punctuation, so "veggie stir fry" finds "Veggie Stir-fry".
4. `recipe_app/uml_class_diagram.png` was redrawn: protected attributes use `#`,
   and one hollow inheritance arrowhead touches the Recipe class.
5. Ingredients use `.title()`, so you get "Ground Beef", not "Ground beef".
6. `load_recipes()` uses if/else instead of `continue`.
