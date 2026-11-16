"""Loads recipe records from an Excel workbook into Recipe objects."""

from pathlib import Path

import pandas as pd

from .app_logger import get_logger
from .recipe import DessertRecipe, MainCourseRecipe, Recipe

REQUIRED_COLUMNS = ("Name", "Ingredients", "Steps", "Type", "Is_Vegetarian")

logger = get_logger(__name__)


def load_recipes(path):
    """Read the Excel file at `path` and return a list of Recipe objects.

    Raises FileNotFoundError if the file is missing, KeyError if a required
    column is missing, and ValueError if a row has an invalid level value.
    """
    logger.info("Loading recipes from '%s'", path)

    if not Path(path).is_file():
        logger.error("Recipe data file not found: %s", path)
        raise FileNotFoundError(f"Recipe data file not found: {path}")

    data_frame = pd.read_excel(path)
    logger.debug("Excel file read: %d row(s), columns=%s", len(data_frame), list(data_frame.columns))

    missing = [col for col in REQUIRED_COLUMNS if col not in data_frame.columns]
    if missing:
        logger.error("Missing required column(s) in %s: %s", path, ", ".join(missing))
        raise KeyError(f"Missing required column(s) in {path}: {', '.join(missing)}")

    recipes = []
    for row_number, row in enumerate(data_frame.to_dict(orient="records"), start=2):
        if pd.isna(row.get("Name")):
            logger.debug("Row %d skipped: no Name value", row_number)
        else:
            recipe = _build_recipe(row)
            logger.debug("Row %d -> built %s '%s'", row_number, type(recipe).__name__, recipe.name)
            recipes.append(recipe)

    logger.info("Loaded %d recipe(s) from '%s'", len(recipes), path)
    return recipes


def _build_recipe(row):
    """Build a Recipe (or DessertRecipe/MainCourseRecipe) from one data row."""
    def get(col, default=None):
        value = row.get(col, default)
        return default if pd.isna(value) else value

    name = get("Name")
    ingredients = get("Ingredients", "")
    steps = get("Steps", "")
    recipe_type = str(get("Type", "")).strip()
    is_vegetarian = bool(get("Is_Vegetarian", False))

    if recipe_type == "Dessert":
        level = get("Sweetness_Level")
        if level is None:
            logger.warning("'%s' has no Sweetness_Level in the data; showing it as not specified", name)
        return DessertRecipe(name, ingredients, steps, is_vegetarian, level)
    if recipe_type == "Main Course":
        level = get("Spice_Level")
        if level is None:
            logger.warning("'%s' has no Spice_Level in the data; showing it as not specified", name)
        return MainCourseRecipe(name, ingredients, steps, is_vegetarian, level)
    return Recipe(name, ingredients, steps, is_vegetarian)
