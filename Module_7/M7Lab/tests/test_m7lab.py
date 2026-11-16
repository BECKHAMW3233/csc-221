"""Unit tests for the M7Lab launcher and both Flask programs.

Run from the project folder:
    python -m unittest discover -s tests -v
"""

import io
import logging
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import launcher  # noqa: E402
import make_submission_zip  # noqa: E402
from recipe_app import create_app as create_recipe_app  # noqa: E402
from recipe_app.data_loader import load_recipes  # noqa: E402
from recipe_app.menu import (  # noqa: E402
    adjust_recipe_level,
    filter_recipes,
    find_recipes_by_name,
    get_recipe_by_name,
    normalize,
    parse_adjust_amount,
)
from recipe_app.recipe import DessertRecipe, MainCourseRecipe, Recipe  # noqa: E402
from vet_app import create_app as create_vet_app  # noqa: E402
from vet_app.m5pro_functions import (  # noqa: E402
    DB_PATH,
    breed_charge_stats,
    configure_logging,
    parse_owner_id,
    sanitize_filename_component,
)
from vet_app.vet_classes import VetServiceManager  # noqa: E402

RECIPE_FILE = Path(__file__).resolve().parents[1] / "recipe_app" / "data" / "recipe_data.xlsx"


# ---------------------------------------------------------------- launcher
class TestLauncher(unittest.TestCase):
    def test_parse_menu_choice_accepts_valid_options(self):
        for choice in ("1", "2", "3", "4", " 2 "):
            self.assertEqual(launcher.parse_menu_choice(choice), choice.strip())

    def test_parse_menu_choice_rejects_invalid_options(self):
        for bad in ("", "0", "5", "abc", "1.5"):
            with self.assertRaises(ValueError):
                launcher.parse_menu_choice(bad)

    def test_build_app_for_each_program(self):
        names = {"1": "vet_app", "2": "recipe_app", "3": "rpg_app"}
        for choice, package in names.items():
            with redirect_stdout(io.StringIO()):
                app = launcher.build_app(choice)
            self.assertEqual(app.import_name, package, choice)

    def test_menu_says_goodbye_on_exit(self):
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=["7", "4"]), redirect_stdout(output):
            launcher.main()
        self.assertIn("not a valid option", output.getvalue())
        self.assertIn("Goodbye!", output.getvalue())

    def test_launch_reports_startup_error_instead_of_crashing(self):
        output = io.StringIO()
        with mock.patch("launcher.build_app", side_effect=FileNotFoundError("missing db")), \
                redirect_stdout(output):
            self.assertFalse(launcher.launch("1", open_browser=False))
        self.assertIn("Could not start", output.getvalue())

    def test_run_web_app_serves_pages_until_stopped(self):
        """Start the real server, fetch the home page, then 'press Enter'."""
        import urllib.request

        pages = []

        def fetch_then_stop(_prompt):
            pages.append(urllib.request.urlopen(url_holder[0], timeout=5).read().decode())

        url_holder = []
        app = create_vet_app()
        with mock.patch("launcher.find_free_port", return_value=launcher.find_free_port()) as port:
            url_holder.append(f"http://{launcher.HOST}:{port.return_value}/")
            with redirect_stdout(io.StringIO()):
                launcher.run_web_app(app, "Vet", open_browser=False, wait_for_stop=fetch_then_stop)
        self.assertIn("Vet Services", pages[0])


# ---------------------------------------------------------------- submission zip
class TestSubmissionZip(unittest.TestCase):
    def test_should_include(self):
        include = make_submission_zip.should_include
        for keep in ("launcher.py", "vet_app/data/vet_serv.db", "dist/M7Lab_Launcher.exe",
                     "docs/screenshots/03_01_venv.png", "build_exe.bat"):
            self.assertTrue(include(keep), keep)
        for skip in ("venv/Scripts/python.exe", "build/M7Lab_Launcher/PYZ-00.pyz", "M7Lab_Launcher.spec",
                     "vet_app/__pycache__/x.pyc", "saves/hero.json", "logs/a.log", "dist/other.exe"):
            self.assertFalse(include(skip), skip)

    def test_missing_exe_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                make_submission_zip.make_zip(Path(folder))


# ---------------------------------------------------------------- M5Pro functions
class TestVetFunctions(unittest.TestCase):
    def test_parse_owner_id_valid(self):
        self.assertEqual(parse_owner_id("1011"), 1011)
        self.assertEqual(parse_owner_id("  1017 "), 1017)

    def test_parse_owner_id_invalid(self):
        for bad in ("", "abc", "10.5", "9" * 30):
            with self.assertRaises(ValueError):
                parse_owner_id(bad)

    def test_sanitize_filename_component(self):
        self.assertEqual(sanitize_filename_component("o'brien/../x"), "o_brien____x")

    def test_breed_charge_stats(self):
        db = VetServiceManager(str(DB_PATH))
        try:
            pets = db.get_all_pets()
        finally:
            db.close()
        matches, total, average = breed_charge_stats(pets, "BEAGLE")
        self.assertEqual(len(matches), 1)
        self.assertEqual(total, 50.0)
        self.assertEqual(average, 50.0)
        none, total, average = breed_charge_stats(pets, "no such breed")
        self.assertTrue(none.empty)
        with self.assertRaises(ValueError):
            breed_charge_stats(pets, "   ")

    def test_missing_database_raises_file_not_found(self):
        """Instructor feedback: a missing database must not crash the program."""
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "nope.db"
            with self.assertRaises(FileNotFoundError):
                VetServiceManager(str(missing))
            self.assertFalse(missing.exists(), "should not create an empty database")

    def test_bad_query_raises_sqlite_error(self):
        db = VetServiceManager(str(DB_PATH))
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute_query("SELECT * FROM NO_SUCH_TABLE")
        finally:
            db.close()

    def test_vet_logging_keeps_its_own_log_file(self):
        """Vet logging must not take over the root logger (the RPG logs there)."""
        root_handlers = list(logging.getLogger().handlers)
        vet_logger = logging.getLogger("vet_app")
        before = list(vet_logger.handlers)
        log_path = configure_logging()
        try:
            self.assertEqual(logging.getLogger().handlers, root_handlers)
            self.assertFalse(vet_logger.propagate)
            self.assertEqual(len(vet_logger.handlers), len(before) + 1)
        finally:
            for handler in vet_logger.handlers[len(before):]:
                vet_logger.removeHandler(handler)
                handler.close()
            Path(log_path).unlink(missing_ok=True)

    def test_owner_charges_total(self):
        db = VetServiceManager(str(DB_PATH))
        try:
            df = db.get_owner_charges(1011)
        finally:
            db.close()
        self.assertEqual(len(df), 2)
        self.assertGreater(df["Charge"].sum(), 0)


# ---------------------------------------------------------------- M3Pro functions
class TestRecipeFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipes = load_recipes(RECIPE_FILE)

    def test_load_recipes(self):
        self.assertEqual(len(self.recipes), 10)

    def test_load_recipes_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_recipes("does_not_exist.xlsx")

    def test_normalize_ignores_punctuation(self):
        """Instructor feedback #3."""
        self.assertEqual(normalize("Veggie Stir-fry"), "veggie stir fry")
        self.assertEqual(normalize("  VEGGIE   stir fry! "), "veggie stir fry")

    def test_search_finds_punctuated_name(self):
        names = [r.name for r in find_recipes_by_name(self.recipes, "veggie stir fry")]
        self.assertEqual(names, ["Veggie Stir-fry"])

    def test_search_partial_and_empty(self):
        self.assertEqual(len(find_recipes_by_name(self.recipes, "cake")), 1)
        with self.assertRaises(ValueError):
            find_recipes_by_name(self.recipes, " - ")

    def test_filter_recipes(self):
        self.assertTrue(all(isinstance(r, DessertRecipe) for r in filter_recipes(self.recipes, "a")))
        self.assertTrue(all(isinstance(r, MainCourseRecipe) for r in filter_recipes(self.recipes, "B")))
        self.assertTrue(all(r.is_vegetarian for r in filter_recipes(self.recipes, "c")))
        with self.assertRaises(ValueError):
            filter_recipes(self.recipes, "z")

    def test_missing_level_is_reported_not_defaulted(self):
        """Instructor feedback #1: Caesar Salad has no spice level in the data."""
        salad = get_recipe_by_name(self.recipes, "caesar salad")
        self.assertIsNone(salad.spice_level)
        self.assertIn("Not specified", salad.level_text())

    def test_ingredients_use_title_case(self):
        """Instructor feedback #5."""
        self.assertEqual(Recipe("x", "ground beef, olive oil", "", False).ingredients,
                         ["Ground Beef", "Olive Oil"])

    def test_adjust_recipe_level(self):
        """Instructor feedback #2: adjust_sweetness / adjust_spice are now used."""
        cake = DessertRecipe("Cake", "flour", "bake", False, 8)
        self.assertEqual(adjust_recipe_level(cake, 5), ("Sweetness", 10))   # clamped
        chili = MainCourseRecipe("Chili", "beans", "cook", False, 3)
        self.assertEqual(adjust_recipe_level(chili, -1), ("Spice", 2))
        with self.assertRaises(ValueError):
            adjust_recipe_level(MainCourseRecipe("Salad", "lettuce", "toss", True), 1)
        with self.assertRaises(ValueError):
            adjust_recipe_level(Recipe("Toast", "bread", "toast", True), 1)

    def test_parse_adjust_amount(self):
        self.assertEqual(parse_adjust_amount(" -2 "), -2)
        with self.assertRaises(ValueError):
            parse_adjust_amount("two")

    def test_validate_level_out_of_range(self):
        with self.assertRaises(ValueError):
            DessertRecipe("Too Sweet", "sugar", "mix", True, 11)


# ---------------------------------------------------------------- Flask pages
class TestVetWebApp(unittest.TestCase):
    def setUp(self):
        self.client = create_vet_app().test_client()

    def test_all_pages_load(self):
        for url in ("/", "/owners", "/pets", "/owner?owner_id=1011",
                    "/charges?owner_id=1011", "/breed?breed=beagle"):
            with redirect_stdout(io.StringIO()):
                response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_results(self):
        with redirect_stdout(io.StringIO()):
            self.assertIn(b"Total charge for OwnerId 1011", self.client.get("/charges?owner_id=1011").data)
            self.assertIn(b"Average charge for &#39;beagle&#39;: $50.00",
                          self.client.get("/breed?breed=beagle").data)

    def test_bad_input_shows_error_not_crash(self):
        for url, message in (("/owner?owner_id=abc", b"must be a whole number"),
                             ("/charges?owner_id=99999", b"No owner found"),
                             ("/breed?breed=", b"Breed cannot be blank")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn(message, response.data)

    def test_missing_database_page(self):
        with mock.patch("vet_app.DB_PATH", Path("missing.db")):
            response = self.client.get("/owners")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Database file not found", response.data)


class TestRecipeWebApp(unittest.TestCase):
    def setUp(self):
        self.client = create_recipe_app().test_client()

    def test_all_pages_load(self):
        for url in ("/", "/all", "/search?name=veggie+stir+fry", "/filter?type=a",
                    "/adjust?name=Apple+Pie&amount=-2"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_results(self):
        self.assertIn(b"Veggie Stir-fry", self.client.get("/search?name=veggie+stir+fry").data)
        self.assertIn(b"Sweetness level is now 7/10", self.client.get("/adjust?name=Apple+Pie&amount=-2").data)
        self.assertIn(b"Not specified", self.client.get("/all").data)

    def test_bad_input_shows_error_not_crash(self):
        for url, message in (("/search?name=", b"cannot be empty"),
                             ("/filter?type=z", b"not a valid filter option"),
                             ("/adjust?name=Caesar+Salad&amount=1", b"has no spice level"),
                             ("/adjust?name=Apple+Pie&amount=lots", b"not a whole number")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertIn(message, response.data)

    def test_missing_data_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            create_recipe_app("missing.xlsx")


if __name__ == "__main__":
    unittest.main()
