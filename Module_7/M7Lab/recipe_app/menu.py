"""Menu actions for the Recipe Management System.

Each action has a "pure" function that takes values and returns results
(used by the Flask web app and the unit tests) and a console wrapper
that prompts with input() and prints the results.
"""

import re

from .app_logger import get_logger
from .recipe import DessertRecipe, MainCourseRecipe
from .table import print_recipe_grid

logger = get_logger(__name__)

FILTER_OPTIONS = {"a": "Dessert", "b": "Main Course", "c": "Vegetarian"}


def normalize(text):
    """Lowercase, drop punctuation, and collapse whitespace so names compare consistently.

    "Veggie Stir-fry" and "veggie  stir fry" both become "veggie stir fry".
    """
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text).lower()).split())


def find_recipes_by_name(recipes, query_text):
    """Return recipes matching query_text (exact match first, then partial).

    Raises ValueError if the query is empty after normalizing.
    """
    query = normalize(query_text)
    if not query:
        logger.warning("find_recipes_by_name: rejected empty query")
        raise ValueError("Search name cannot be empty.")

    matches = [r for r in recipes if normalize(r.name) == query]
    logger.debug("find_recipes_by_name: exact match for '%s' -> %d found", query, len(matches))
    if not matches:
        matches = [r for r in recipes if query in normalize(r.name)]
        logger.debug("find_recipes_by_name: partial match for '%s' -> %d found", query, len(matches))
    logger.info("find_recipes_by_name: '%s' -> %d match(es): %s", query, len(matches), [r.name for r in matches])
    return matches


def filter_recipes(recipes, choice):
    """Return recipes for filter choice a (Dessert), b (Main Course) or c (Vegetarian).

    Raises ValueError for any other choice.
    """
    choice = str(choice).strip().lower()
    if choice == "a":
        matches = [r for r in recipes if isinstance(r, DessertRecipe)]
    elif choice == "b":
        matches = [r for r in recipes if isinstance(r, MainCourseRecipe)]
    elif choice == "c":
        matches = [r for r in recipes if r.is_vegetarian]
    else:
        logger.warning("filter_recipes: rejected invalid option '%s'", choice)
        raise ValueError(f"'{choice}' is not a valid filter option.")
    logger.info("filter_recipes: '%s' -> %d match(es)", choice, len(matches))
    return matches


def get_recipe_by_name(recipes, name):
    """Return the one recipe whose name matches exactly (ignoring case/punctuation).

    Raises ValueError if no recipe has that name.
    """
    query = normalize(name)
    for recipe in recipes:
        if normalize(recipe.name) == query:
            return recipe
    raise ValueError(f"No recipe named '{name}'.")


def parse_adjust_amount(text):
    """Convert text like "2" or "-1" to an int, raising ValueError if it isn't one."""
    try:
        return int(str(text).strip())
    except ValueError:
        raise ValueError(f"'{text}' is not a whole number. Use something like 2 or -1.") from None


def adjust_recipe_level(recipe, amount):
    """Adjust a dessert's sweetness or a main course's spice level by amount.

    Returns (level name, new level). Raises ValueError if the recipe has no
    adjustable level.
    """
    if isinstance(recipe, DessertRecipe):
        new_level = recipe.adjust_sweetness(amount)
        level_name = "Sweetness"
    elif isinstance(recipe, MainCourseRecipe):
        new_level = recipe.adjust_spice(amount)
        level_name = "Spice"
    else:
        raise ValueError(f"'{recipe.name}' has no sweetness or spice level to adjust.")
    logger.info("adjust_recipe_level: '%s' %s by %d -> %s", recipe.name, level_name, amount, new_level)
    return level_name, new_level


# ----- console wrappers (input/print) -----

def view_all(recipes):
    """Print every loaded recipe as a bordered grid table."""
    logger.info("Menu action: view_all (%d recipe(s) loaded)", len(recipes))
    if not recipes:
        logger.warning("view_all: no recipes loaded")
        print("No recipes loaded.")
        return
    print_recipe_grid(recipes)


def search_by_name(recipes):
    """Prompt for a recipe name and print any matches, ignoring case/spacing/punctuation."""
    raw_input_text = input("Enter recipe name to search: ")
    logger.info("Menu action: search_by_name, raw input=%r", raw_input_text)
    matches = find_recipes_by_name(recipes, raw_input_text)
    if not matches:
        print(f"No recipe found matching '{normalize(raw_input_text)}'.")
        return
    for recipe in matches:
        recipe.display_recipe()


def filter_by_type(recipes):
    """Prompt for a category (Dessert/Main Course/Vegetarian) and print matches."""
    print("a) Dessert\nb) Main Course\nc) Vegetarian")
    raw_input_text = input("Choose a filter: ")
    logger.info("Menu action: filter_by_type, raw input=%r", raw_input_text)
    matches = filter_recipes(recipes, raw_input_text)
    if not matches:
        print("No recipes match that filter.")
        return
    for recipe in matches:
        recipe.display_recipe()


def adjust_level(recipes):
    """Prompt for a recipe and an amount, then adjust its sweetness/spice level."""
    name = input("Enter the recipe name to adjust: ")
    recipe = get_recipe_by_name(recipes, name)
    amount = parse_adjust_amount(input("Adjust level by (e.g. 2 or -1): "))
    level_name, _ = adjust_recipe_level(recipe, amount)
    print(f"{recipe.name} {level_name} level is now {recipe.level_text()}.")
