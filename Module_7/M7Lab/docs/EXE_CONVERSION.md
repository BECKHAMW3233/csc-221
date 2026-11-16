# M7Lab: Converting the Program Launcher to an .exe with PyInstaller

**William Beckham · CSC-221 Advanced Python Programming**

This document records every step of turning `launcher.py` into a stand-alone
executable, with a screenshot for each step.

- **Part 1:** the program being converted, and its unit tests
- **Part 2:** creating the virtual environment, installing PyInstaller and building
- **Part 3:** building and running the Windows `.exe`, and making the submission zip

> **Note on screenshots:** the terminal images in Parts 1 and 2 are the real
> output of each command, captured as it ran. Part 3 uses screenshots taken on
> Windows.

---

## Part 1: The program being converted

### 1.1 Launcher menu (input, results, Goodbye message)

The launcher asks the user to pick one of three programs, rejects invalid
input, starts the chosen Flask app, and says **Goodbye!** before closing.

![Launcher console](screenshots/02a_launcher_console.png)

### 1.2 Vet Services (M5Pro) Flask app

**Option 1: OWNER table** (also saved to `output/owner.csv`)

![Vet owners](screenshots/02b_vet_owners.png)

**Option 4: Total charge by owner**

![Vet charges](screenshots/02c_vet_charges.png)

**Option 5: Pets by breed (total and average charge)**

![Vet breed](screenshots/02d_vet_breed.png)

**Exception handling: invalid OwnerId**

![Vet error](screenshots/02e_vet_error.png)

### 1.3 Recipe Manager (M3Pro) Flask app

**View all recipes.** Caesar Salad's missing spice level is now reported
instead of showing 1 (instructor feedback #1).

![All recipes](screenshots/02f_recipe_all.png)

**Search ignores punctuation:** "veggie stir fry" finds "Veggie Stir-fry" (feedback #3).

![Recipe search](screenshots/02g_recipe_search.png)

**New option: adjust sweetness/spice** uses `adjust_sweetness()` / `adjust_spice()` (feedback #2).

![Recipe adjust](screenshots/02h_recipe_adjust.png)

**Exception handling: a recipe with no level to adjust**

![Recipe error](screenshots/02i_recipe_error.png)

### 1.4 Dungeon RPG (started in CSC-121, built up in CTS-285) Flask app

The Tkinter desktop game was rewritten as web pages. The game rules are the
original code; only the screens changed. Keyboard controls (W/A/S/D, E, I,
K, C, R, Esc) work in the browser.

**Create a character.** Bad input (blank name, an age that isn't 1-100) shows an error.

![RPG title](screenshots/04_01_rpg_title.png)

**World map:** villages, towns, dungeons (with tier and level) and encounters.

![RPG world map](screenshots/04_02_rpg_world.png)

**Village: quest board** (a d20 ability check vs DC) **and shop**

![RPG quests](screenshots/04_03_rpg_village_quests.png)

![RPG shop](screenshots/04_04_rpg_village_shop.png)

**Dungeon:** limited vision, doors, enemies, treasure, merchant and boss vault.

![RPG dungeon](screenshots/04_05_rpg_dungeon.png)

**Combat:** range bands, attack, advance/retreat, spells, abilities, items and flee.

![RPG combat](screenshots/04_06_rpg_combat.png)

![RPG victory](screenshots/04_07_rpg_combat_end.png)

**Inventory, skill tree and pause menu (save/load)**

![RPG inventory](screenshots/04_08_rpg_inventory.png)

![RPG skills](screenshots/04_09_rpg_skills.png)

![RPG pause](screenshots/04_10_rpg_pause.png)

**Phone-width layout**

![RPG on a phone](screenshots/04_11_rpg_phone.png)

### 1.5 Exception handling: missing database (M5Pro instructor feedback)

With `vet_serv.db` deleted on purpose, the launcher reports the problem and
returns to the menu instead of crashing.

![Missing database handled](screenshots/02k_missing_db_handled.png)

### 1.6 Unit tests (63 tests, all passing)

![Unit tests](screenshots/02j_unit_tests.png)

---

## Part 2: Virtual environment, PyInstaller and the build

This part was done on Linux to prove the whole process works before building
on Windows. PyInstaller always builds for the operating system it runs on, so
this produces a Linux program. Part 3 repeats the same steps on Windows to
make the `.exe`.

### 2.1 Create and activate a virtual environment

The venv keeps PyInstaller and the project's packages separate from the
system Python. `which python` shows we're now using the venv's Python.

![Create venv](screenshots/03_01_venv.png)

### 2.2 Install PyInstaller and the project's packages into the venv

`requirements.txt` lists flask, pandas, openpyxl and pyinstaller.

![pip install](screenshots/03_02_pip_install.png)

### 2.3 Run the unit tests inside the venv

All the unit tests pass, which confirms the program works in the venv before converting it.

![Tests in venv](screenshots/03_03_tests_in_venv.png)

### 2.4 Build the executable with PyInstaller

| Option | Why |
|---|---|
| `--onefile` | Packs everything into a single executable file |
| `--console` | Keeps a console window, because the launcher menu needs typed input |
| `--clean --noconfirm` | Starts from a clean build and overwrites old output without asking |
| `--name M7Lab_Launcher` | Names the output file |
| `--add-data "templates:templates"` | Bundles the HTML pages (Flask needs them at run time) |
| `--add-data "vet_app/data:vet_app/data"` | Bundles `vet_serv.db` |
| `--add-data "recipe_app/data:recipe_app/data"` | Bundles `recipe_data.xlsx` |
| `--add-data "rpg_app/game/data:rpg_app/game/data"` | Bundles the Dungeon RPG's game data (classes, items, enemies, spells, skills, quests: 7 JSON files) |
| `--hidden-import openpyxl` | pandas loads openpyxl in a way PyInstaller can't see, so we name it |
| `launcher.py` | The entry point, the file whose menu the user sees |

The two `WARNING` lines are about `user32` and `msvcrt`, which are Windows
system libraries that don't exist on Linux. They don't affect the program.

![PyInstaller build](screenshots/03_04_pyinstaller_build.png)

### 2.5 The result in `dist/`

PyInstaller creates `build/` (temporary work files), `dist/` (the finished
program) and `M7Lab_Launcher.spec` (the saved build settings).

![dist folder](screenshots/03_05_dist_folder.png)

### 2.6 Run the executable on its own

The executable was copied **by itself** into an empty folder and run with no
venv and no Python. It shows the menu, rejects an invalid choice (`9`), runs
all three Flask apps, and says **Goodbye!** before closing.

![Running the executable](screenshots/03_06_exe_run.png)

While it ran, both apps were opened in a browser. These pages were served by
the executable:

![Vet app from the executable](screenshots/03_06b_exe_vet_breed.png)

![Recipe app from the executable](screenshots/03_06c_exe_recipe_all.png)

![Dungeon RPG from the executable, just after saving](screenshots/03_06d_exe_rpg_world.png)

### 2.7 Files the executable created

The CSV output, the RPG save game and the log files are written **next to the
executable**, not inside PyInstaller's temporary folder, so they're still there
after the program closes. Each program keeps its own log file.

![Files created by the executable](screenshots/03_07_exe_output_files.png)

**Automated check of the built program: 14 of 14 passed.**

| Program | Checks |
|---|---|
| Vet Services | home page; OWNER table and CSV save; total charge for owner 1011 ($80.00); breed average ($50.00); bad-OwnerId error |
| Recipe Manager | missing level reported; punctuation-insensitive search; level adjustment |
| Dungeon RPG | title screen; bad age rejected; new game shows the world map; moving; inventory panel; saving a game |

The program exited with code 0.

---

## Part 3: Windows .exe

PyInstaller builds for the operating system it runs on, so the Windows `.exe`
has to be built on Windows. These are the same steps as Part 2. Command
Prompt uses `venv\Scripts\activate` instead of `source venv/bin/activate`,
and `;` instead of `:` inside `--add-data`.

**You need:** Windows 10 or 11 and Python from python.org. Tick **"Add
python.exe to PATH"** in the installer.

> 📸 **Screenshots:** for each step, press **Win + Shift + S**, capture the
> window, and save it into `docs\screenshots\` with the file name shown.
> The image then appears in this document automatically.

> ⚡ **Shortcut:** `build_exe.bat` runs steps 3.2 to 3.6 in one go.
> Double-click it, or type `build_exe.bat` in Command Prompt. For the
> screenshots, typing each command yourself, as shown below, gives the
> clearest picture of every step.

### 3.1 Open Command Prompt in the project folder

In File Explorer, open the `M7Lab_beckhamwilliam` folder, click the address
bar, type `cmd` and press Enter.

📸 `05_01_win_cmd.png`

![Windows: Command Prompt in the project folder](screenshots/05_01_win_cmd.png)

### 3.2 Create the virtual environment

```bat
python --version
python -m venv venv
```

📸 `05_02_win_venv.png`

![Windows: create venv](screenshots/05_02_win_venv.png)

### 3.3 Activate it

The prompt starts with `(venv)` once it's active.

```bat
venv\Scripts\activate
where python
```

📸 `05_03_win_activate.png`

![Windows: activate venv](screenshots/05_03_win_activate.png)

### 3.4 Install PyInstaller and the program's packages

```bat
pip install -r requirements.txt
pyinstaller --version
```

📸 `05_04_win_pip_install.png` (the end, showing "Successfully installed ..." and the version)

![Windows: pip install](screenshots/05_04_win_pip_install.png)

### 3.5 Run the unit tests

```bat
python -m unittest discover -s tests
```

It should end with `Ran 63 tests` and `OK`.

📸 `05_05_win_tests.png`

![Windows: unit tests](screenshots/05_05_win_tests.png)

### 3.6 Build the .exe

Copy and paste the whole command. The `^` at the end of each line continues
it onto the next line in Command Prompt.

```bat
pyinstaller --onefile --console --clean --noconfirm --name M7Lab_Launcher ^
    --add-data "templates;templates" ^
    --add-data "vet_app\data;vet_app\data" ^
    --add-data "recipe_app\data;recipe_app\data" ^
    --add-data "rpg_app\game\data;rpg_app\game\data" ^
    --hidden-import openpyxl ^
    launcher.py
```

It takes about a minute and should end with `Build complete!`.

📸 `05_06_win_build.png` (the end of the output)

![Windows: PyInstaller build](screenshots/05_06_win_build.png)

### 3.7 The .exe in `dist\`

Open the `dist` folder in File Explorer.

📸 `05_07_win_dist.png`

![Windows: dist folder with M7Lab_Launcher.exe](screenshots/05_07_win_dist.png)

### 3.8 Run the .exe

Double-click `dist\M7Lab_Launcher.exe`. The first start takes a few seconds
while it unpacks.

> If Windows shows **"Windows protected your PC"**, click **More info → Run
> anyway**. PyInstaller programs aren't digitally signed, so SmartScreen
> warns about them. This is normal.

Pick each program, look at it in the browser, press Enter in the launcher
window to stop it, and finish with `4` (Exit).

📸 `05_08_win_exe_menu.png` (the launcher menu)

![Windows: launcher menu](screenshots/05_08_win_exe_menu.png)

📸 `05_09_win_exe_vet.png` (Vet Services in the browser)

![Windows: Vet Services from the exe](screenshots/05_09_win_exe_vet.png)

📸 `05_10_win_exe_recipe.png` (Recipe Manager in the browser)

![Windows: Recipe Manager from the exe](screenshots/05_10_win_exe_recipe.png)

📸 `05_11_win_exe_rpg.png` (Dungeon RPG in the browser)

![Windows: Dungeon RPG from the exe](screenshots/05_11_win_exe_rpg.png)

📸 `05_12_win_exe_goodbye.png` (the "Goodbye!" message after choosing 4)

![Windows: Goodbye message](screenshots/05_12_win_exe_goodbye.png)

### 3.9 Files the .exe created

Next to `M7Lab_Launcher.exe` in `dist\` you'll now see `output\` (CSV
files), `logs\` and, if you saved a game, `saves\`.

📸 `05_13_win_exe_files.png`

![Windows: files created next to the exe](screenshots/05_13_win_exe_files.png)

### 3.10 Make the submission zip (code + exe, no venv)

```bat
python make_submission_zip.py
```

This creates `M7Lab_beckhamwilliam.zip` next to the project folder. It
contains the Python code, data, tests, docs and `dist\M7Lab_Launcher.exe`,
and leaves out `venv\`, `build\`, saves, logs and caches.

📸 `05_14_win_zip.png`

![Windows: submission zip created](screenshots/05_14_win_zip.png)

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Reinstall Python from python.org and tick **Add python.exe to PATH**, then open a new Command Prompt. |
| `Python was not found; run without arguments to install from the Microsoft Store` | Windows is using its Store shortcut instead of real Python. Install Python from python.org (tick **Add python.exe to PATH**), or turn off **Settings → Apps → Advanced app settings → App execution aliases → python.exe / python3.exe**. |
| `pip install` fails building **pandas** or **numpy** | Your Python is too new for the available pre-built packages. Install **Python 3.13** from python.org, delete the `venv` folder, and start again from 3.2. |
| Antivirus deletes or quarantines the .exe | PyInstaller one-file programs sometimes trigger false alarms. Restore the file, or add an exception for the `dist` folder. |
| The browser doesn't open | Copy the `http://127.0.0.1:...` address shown in the launcher window into your browser. |
| `Could not create the zip ... not found` | The .exe hasn't been built yet. Run step 3.6 (or `build_exe.bat`) first. |
