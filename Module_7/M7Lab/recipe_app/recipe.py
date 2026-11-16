"""Recipe classes for the Recipe Management System."""

NOT_SPECIFIED = "Not specified"

from .app_logger import get_logger

logger = get_logger(__name__)


class Recipe:
    """Base recipe with shared attributes and display/formatting behavior."""

    def __init__(self, name, ingredients, steps, is_vegetarian):
        self._name = self._format_name(name)
        self._ingredients = self._parse_ingredients(ingredients)
        self._steps = str(steps).strip()
        self._is_vegetarian = bool(is_vegetarian)

    @staticmethod
    def _format_name(name):
        """Strip and collapse whitespace in a recipe name."""
        return " ".join(str(name).strip().split())

    @staticmethod
    def _parse_ingredients(ingredients):
        """Split a comma-separated ingredient string into a clean, title-cased list.

        .title() keeps every word capitalized ("Ground Beef", not "Ground beef").
        """
        items = ingredients if isinstance(ingredients, (list, tuple)) else str(ingredients).split(",")
        return [item.strip().title() for item in items if item.strip()]

    @staticmethod
    def _validate_level(level, low, high):
        """Return level as an int (or None if missing), raising ValueError if outside [low, high]."""
        if level is None:
            return None
        level = int(level)
        if not low <= level <= high:
            logger.warning("Level validation failed: %d not in [%d, %d]", level, low, high)
            raise ValueError(f"Level must be between {low} and {high}, got {level}")
        return level

    @property
    def name(self):
        """The recipe's display name."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = self._format_name(value)

    @property
    def ingredients(self):
        """The recipe's ingredient list."""
        return self._ingredients

    @ingredients.setter
    def ingredients(self, value):
        self._ingredients = self._parse_ingredients(value)

    @property
    def steps(self):
        """The recipe's preparation steps."""
        return self._steps

    @steps.setter
    def steps(self, value):
        self._steps = str(value).strip()

    @property
    def is_vegetarian(self):
        """Whether the recipe is vegetarian."""
        return self._is_vegetarian

    @is_vegetarian.setter
    def is_vegetarian(self, value):
        self._is_vegetarian = bool(value)

    def display_recipe(self):
        """Print the recipe's name, vegetarian status, ingredients, and steps."""
        veg = "Yes" if self._is_vegetarian else "No"
        print(f"\n{self._name}")
        print("-" * len(self._name))
        print(f"Vegetarian: {veg}")
        print("Ingredients:")
        for item in self._ingredients:
            print(f"  - {item}")
        print(f"Steps: {self._steps}")


class DessertRecipe(Recipe):
    """A dessert recipe with a sweetness level (1-10), or None if not specified."""

    def __init__(self, name, ingredients, steps, is_vegetarian, sweetness_level=None):
        super().__init__(name, ingredients, steps, is_vegetarian)
        self._sweetness_level = self._validate_level(sweetness_level, 1, 10)

    @property
    def sweetness_level(self):
        """The dessert's sweetness level, 1-10, or None if not specified."""
        return self._sweetness_level

    @sweetness_level.setter
    def sweetness_level(self, value):
        self._sweetness_level = self._validate_level(value, 1, 10)

    def adjust_sweetness(self, amount):
        """Adjust sweetness level by amount, clamped to 1-10.

        Raises ValueError if this recipe has no sweetness level to adjust.
        """
        if self._sweetness_level is None:
            raise ValueError(f"'{self._name}' has no sweetness level to adjust.")
        old_level = self._sweetness_level
        self._sweetness_level = max(1, min(10, old_level + amount))
        logger.debug(
            "'%s' sweetness_level %d -> %d (amount=%d)",
            self._name, old_level, self._sweetness_level, amount,
        )
        return self._sweetness_level

    def display_recipe(self):
        """Print the base recipe details plus the sweetness level."""
        super().display_recipe()
        print(f"Sweetness Level: {self.level_text()}")

    def level_text(self):
        """Return the sweetness level for display, or a not-specified notice."""
        if self._sweetness_level is None:
            return f"{NOT_SPECIFIED} in the recipe data"
        return f"{self._sweetness_level}/10"


class MainCourseRecipe(Recipe):
    """A main course recipe with a spice level (1-5), or None if not specified."""

    def __init__(self, name, ingredients, steps, is_vegetarian, spice_level=None):
        super().__init__(name, ingredients, steps, is_vegetarian)
        self._spice_level = self._validate_level(spice_level, 1, 5)

    @property
    def spice_level(self):
        """The main course's spice level, 1-5, or None if not specified."""
        return self._spice_level

    @spice_level.setter
    def spice_level(self, value):
        self._spice_level = self._validate_level(value, 1, 5)

    def adjust_spice(self, amount):
        """Adjust spice level by amount, clamped to 1-5.

        Raises ValueError if this recipe has no spice level to adjust.
        """
        if self._spice_level is None:
            raise ValueError(f"'{self._name}' has no spice level to adjust.")
        old_level = self._spice_level
        self._spice_level = max(1, min(5, old_level + amount))
        logger.debug(
            "'%s' spice_level %d -> %d (amount=%d)",
            self._name, old_level, self._spice_level, amount,
        )
        return self._spice_level

    def display_recipe(self):
        """Print the base recipe details plus the spice level."""
        super().display_recipe()
        print(f"Spice Level: {self.level_text()}")

    def level_text(self):
        """Return the spice level for display, or a not-specified notice."""
        if self._spice_level is None:
            return f"{NOT_SPECIFIED} in the recipe data"
        return f"{self._spice_level}/5"
