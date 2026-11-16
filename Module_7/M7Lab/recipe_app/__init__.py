"""Flask web version of the M3Pro Recipe Management System.

Each page matches one option from the original console menu and reuses the
Recipe classes, load_recipes(), and the menu.py functions.
"""

from flask import Flask, render_template, request

from app_paths import resource_path

from .app_logger import get_logger
from .data_loader import load_recipes
from .menu import (
    FILTER_OPTIONS,
    adjust_recipe_level,
    filter_recipes,
    find_recipes_by_name,
    get_recipe_by_name,
    normalize,
    parse_adjust_amount,
)
from .recipe import DessertRecipe, MainCourseRecipe
from .table import _recipe_columns

APP_TITLE = "Recipe Manager (M3Pro)"
DATA_FILE = resource_path("recipe_app", "data", "recipe_data.xlsx")

logger = get_logger(__name__)


def recipe_type_label(recipe):
    """Return 'Dessert', 'Main Course' or 'Recipe' for display."""
    if isinstance(recipe, DessertRecipe):
        return "Dessert"
    if isinstance(recipe, MainCourseRecipe):
        return "Main Course"
    return "Recipe"


def create_app(data_file=DATA_FILE):
    """Load the recipes and build the Recipe Manager Flask app.

    Raises FileNotFoundError, KeyError or ValueError if the recipe data
    can't be loaded, so the launcher can report it instead of crashing.
    Level adjustments are kept in memory while the app runs (the Excel
    file is not changed).
    """
    recipes = load_recipes(data_file)
    app = Flask(__name__, template_folder=str(resource_path("templates")))
    app.jinja_env.globals["type_label"] = recipe_type_label

    def show(**result):
        """Render the main page, with an optional result section."""
        return render_template("recipe/index.html", app_title=APP_TITLE,
                               form=request.args, recipes=recipes,
                               filter_options=FILTER_OPTIONS, **result)

    @app.route("/")
    def index():
        return show()

    @app.route("/all")
    def view_all():
        logger.info("Web: view_all (%d recipe(s))", len(recipes))
        if not recipes:
            return show(heading="All Recipes", error="No recipes loaded.")
        return show(heading="All Recipes", grid=_recipe_columns(recipes))

    @app.route("/search")
    def search():
        raw = request.args.get("name", "")
        try:
            matches = find_recipes_by_name(recipes, raw)
        except ValueError as error:
            return show(heading="Search by Name", error=str(error))
        if not matches:
            return show(heading="Search by Name",
                        error=f"No recipe found matching '{normalize(raw)}'.")
        return show(heading=f"Recipes matching '{raw.strip()}'", cards=matches)

    @app.route("/filter")
    def filter_view():
        choice = request.args.get("type", "")
        try:
            matches = filter_recipes(recipes, choice)
        except ValueError as error:
            return show(heading="Filter by Type", error=str(error))
        label = FILTER_OPTIONS[choice.strip().lower()]
        if not matches:
            return show(heading=f"Filter: {label}", error="No recipes match that filter.")
        return show(heading=f"Filter: {label}", cards=matches)

    @app.route("/adjust")
    def adjust():
        try:
            recipe = get_recipe_by_name(recipes, request.args.get("name", ""))
            amount = parse_adjust_amount(request.args.get("amount", ""))
            level_name, _ = adjust_recipe_level(recipe, amount)
        except ValueError as error:
            return show(heading="Adjust Sweetness / Spice Level", error=str(error))
        return show(heading="Adjust Sweetness / Spice Level",
                    summary=[f"{recipe.name}: {level_name} level is now {recipe.level_text()}."],
                    cards=[recipe])

    return app
