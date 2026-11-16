"""Bordered grid table formatting for displaying recipes, one per column."""

import shutil

from .app_logger import get_logger
from .recipe import DessertRecipe, MainCourseRecipe

FIELDS = ["Type", "Vegetarian", "Level", "Ingredients", "Steps"]

logger = get_logger(__name__)


def _level_label(recipe):
    """Return the sweetness/spice level as a display string, or blank if N/A."""
    if isinstance(recipe, DessertRecipe):
        return f"Sweetness: {recipe.level_text()}"
    if isinstance(recipe, MainCourseRecipe):
        return f"Spice: {recipe.level_text()}"
    return ""


def _recipe_columns(recipes):
    """Build a list of (recipe_name, {field: value}) pairs for the grid."""
    type_labels = {DessertRecipe: "Dessert", MainCourseRecipe: "Main Course"}
    return [
        (
            recipe.name,
            {
                "Type": type_labels.get(type(recipe), "Recipe"),
                "Vegetarian": "Yes" if recipe.is_vegetarian else "No",
                "Level": _level_label(recipe),
                "Ingredients": ", ".join(recipe.ingredients),
                "Steps": recipe.steps,
            },
        )
        for recipe in recipes
    ]


def _grid_border(label_width, col_widths):
    """Build a '+---+---+' style border line sized to each column."""
    segments = [label_width + 2] + [w + 2 for w in col_widths]
    return "+" + "+".join("-" * width for width in segments) + "+"


def _grid_row(label, cells, label_width, col_widths):
    """Build one '| label | cell | cell |' row, padded to column widths."""
    parts = [f" {label.ljust(label_width)} "]
    parts += [f" {cell.ljust(width)} " for cell, width in zip(cells, col_widths)]
    return "|" + "|".join(parts) + "|"


def _column_batches(columns, label_width, terminal_width):
    """Group (name, width) columns into batches that fit the terminal width."""
    batch = []
    width_used = label_width + 3  # leading "| label |" cell
    for name, width in columns:
        added_width = width + 3  # " value |"
        if batch and width_used + added_width > terminal_width:
            yield batch
            batch = []
            width_used = label_width + 3
        batch.append((name, width))
        width_used += added_width
    if batch:
        yield batch


def print_recipe_grid(recipes):
    """Print every recipe as a bordered table, one recipe per column.

    Recipes are split across multiple stacked blocks so each block's grid
    fits within the terminal width instead of wrapping mid-row.
    """
    logger.info("Rendering recipe grid for %d recipe(s)", len(recipes))

    columns = _recipe_columns(recipes)
    values_by_name = dict(columns)

    label_width = max(len("Field"), *(len(field) for field in FIELDS))
    widths_by_name = {
        name: max(len(name), *(len(values[field]) for field in FIELDS))
        for name, values in columns
    }

    terminal_width = shutil.get_terminal_size(fallback=(120, 24)).columns
    logger.debug("Detected terminal width: %d columns", terminal_width)
    name_width_pairs = [(name, widths_by_name[name]) for name, _ in columns]

    print()
    block_number = 0
    for batch in _column_batches(name_width_pairs, label_width, terminal_width):
        block_number += 1
        names = [name for name, _ in batch]
        logger.debug("Grid block %d: %d recipe(s) -> %s", block_number, len(names), names)
        col_widths = [width for _, width in batch]
        border = _grid_border(label_width, col_widths)

        print(border)
        print(_grid_row("Field", names, label_width, col_widths))
        print(border)
        for field in FIELDS:
            cells = [values_by_name[name][field] for name in names]
            print(_grid_row(field, cells, label_width, col_widths))
        print(border)
        print()

    logger.info("Grid rendered in %d block(s)", block_number)
