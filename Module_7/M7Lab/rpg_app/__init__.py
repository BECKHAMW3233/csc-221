"""Flask web version of the Dungeon RPG (started in CSC-121, built up in CTS-285).

The game rules (characters, combat, dungeons, world map, merchants, quests)
are the original code in rpg_app/game/. GameController (controller.py)
replaces the old Tkinter windows; this module turns browser clicks and key
presses into controller actions and draws the result as HTML.

It's a single-player game running on the player's own computer, so the app
keeps one GameController in memory for as long as it runs.
"""

import logging

from flask import Flask, redirect, render_template, request

from app_paths import resource_path
from web_exit import add_exit_route

from .controller import (
    EQUIPPABLE_TYPES,
    GameController,
    describe_item,
)
from .game.config import COMBAT_MAX_DISTANCE, dungeon_recommended_level

APP_TITLE = "Dungeon RPG (CSC-121 → CTS-285)"
ABILITIES = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']


def _index(form, field='index'):
    """Read an inventory index from the form, raising ValueError if it isn't a number."""
    try:
        return int(form.get(field, ''))
    except ValueError:
        raise ValueError("Pick an item from the list.") from None


def dispatch(game: GameController, form) -> None:
    """Apply one form submission (a button press or key press) to the game.

    Raises ValueError for anything the player did that isn't allowed.
    """
    action = form.get('action', '')
    actions = {
        'new_game': lambda: game.new_game(form.get('name', ''), form.get('age', ''), form.get('class_key', '')),
        'open_load': lambda: game.open_panel('load'),
        'load': lambda: game.load_game(form.get('file', '')),
        'save': game.save_game,
        'move': lambda: game.move(form.get('dir', '')),
        'interact': game.interact,
        'leave': lambda: game.confirm_leave_dungeon(form.get('answer') == 'yes'),
        'camp': game.camp,
        'scout': game.scout,
        'panel': lambda: game.open_panel(form.get('name', '')),
        'close': game.close_panel,
        'equip': lambda: game.equip(_index(form)),
        'use': lambda: game.use(_index(form)),
        'sell': lambda: game.sell(_index(form)),
        'buy': lambda: game.buy(form.get('item', '')),
        'quest': lambda: game.attempt_quest(form.get('quest', '')),
        'tab': lambda: game.set_merchant_tab(form.get('tab', '')),
        'unlock': lambda: game.unlock_skill(form.get('skill', '')),
        'combat': lambda: game.combat_action(form.get('op', ''), form.get('value', '')),
        'combat_close': game.finish_combat,
        'quit_to_title': game.quit_to_title,
    }
    if action not in actions:
        raise ValueError(f"Unknown action '{action}'.")
    actions[action]()


def create_app(game: GameController = None):
    """Build the Dungeon RPG Flask app (optionally around an existing GameController)."""
    game = game or GameController()
    app = Flask(__name__, template_folder=str(resource_path("templates")))
    add_exit_route(app, "Dungeon RPG")
    app.jinja_env.globals.update(
        describe_item=describe_item,
        equippable_types=EQUIPPABLE_TYPES,
        abilities=ABILITIES,
        combat_max_distance=COMBAT_MAX_DISTANCE,
        recommended_level=dungeon_recommended_level,
    )

    @app.get("/")
    def play():
        return render_template("rpg/game.html", app_title=APP_TITLE, game=game,
                               screen=game.screen)

    @app.post("/act")
    def act():
        game.notices = []
        try:
            dispatch(game, request.form)
        except ValueError as error:
            game.notify(str(error), 'error')
        except Exception as error:  # keep the game running no matter what
            logging.exception("Unexpected error handling %r", dict(request.form))
            game.notify(f"Something went wrong: {error}", 'error')
        return redirect("/", code=303)

    return app
