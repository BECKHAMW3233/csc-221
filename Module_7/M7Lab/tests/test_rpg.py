"""Unit tests for the Dungeon RPG web version (controller + Flask pages).

Run from the project folder:
    python -m unittest discover -s tests -v

The tests use a small 40x40 world (instead of the real 500x500 one) so they
run fast, and fix the random seed so dice rolls are repeatable.
"""

import json
import os
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rpg_app import create_app  # noqa: E402
from rpg_app.controller import (  # noqa: E402
    CombatState,
    GameController,
    describe_item,
    safe_save_name,
    validate_save_data,
)
from rpg_app.game.config import SAVE_DIR  # noqa: E402
from rpg_app.game.database import Database  # noqa: E402
from rpg_app.game.models.character import Character  # noqa: E402
from rpg_app.game.models.dungeon import Dungeon  # noqa: E402
from rpg_app.game.models.enemy import Enemy  # noqa: E402
from rpg_app.game.models.world_map import WorldMap  # noqa: E402

SMALL_WORLD = mock.patch("rpg_app.controller.WorldMap", lambda: WorldMap(size=40))


def make_game(class_key="fighter"):
    """A controller with a level-1 character on a small world, ready to play."""
    random.seed(1234)
    game = GameController()
    with SMALL_WORLD:
        game.new_game("Tester", "25", class_key)
    game.notices = []
    return game


def fight_until_over(combat: CombatState, max_turns=200):
    """Attack (advancing first if needed) until the fight ends."""
    for _ in range(max_turns):
        if combat.ended:
            return combat.outcome
        if combat.attack_blocked():
            combat.move(-1)
        else:
            combat.attack()
    raise AssertionError("fight never ended")


# ---------------------------------------------------------------- helpers
class TestHelpers(unittest.TestCase):
    def test_validate_save_data(self):
        good = {"player": {k: 1 for k in ("name", "age", "class_key", "level", "xp",
                                          "current_health", "inventory")},
                "world_map": {"size": 1, "player_pos": [0, 0], "nodes": []}}
        self.assertTrue(validate_save_data(good))
        self.assertFalse(validate_save_data({"player": {}}))
        self.assertFalse(validate_save_data("not a dict"))
        broken = dict(good, world_map={"size": 1})
        self.assertFalse(validate_save_data(broken))

    def test_safe_save_name_blocks_paths(self):
        self.assertEqual(safe_save_name("../../evil name"), "evil_name")
        self.assertEqual(safe_save_name("***"), "hero")

    def test_describe_item(self):
        db = Database()
        self.assertIn("1d8", describe_item(db.get_item("Longsword")))
        self.assertIn("Heals", describe_item(db.get_item("Potion of Healing")))


# ---------------------------------------------------------------- new game
class TestNewGame(unittest.TestCase):
    def setUp(self):
        self.game = GameController()

    def test_invalid_input_is_rejected(self):
        for args, message in ((("", "20", "fighter"), "blank"),
                              (("Bo", "abc", "fighter"), "number"),
                              (("Bo", "0", "fighter"), "between 1 and 100"),
                              (("Bo", "101", "fighter"), "between 1 and 100"),
                              (("Bo", "20", "bard"), "not a valid class")):
            with self.assertRaises(ValueError) as caught:
                self.game.new_game(*args)
            self.assertIn(message, str(caught.exception))
        self.assertIsNone(self.game.player)

    def test_valid_character_starts_on_world_map(self):
        with SMALL_WORLD:
            self.game.new_game("  Aria ", "30", "rogue")
        self.assertEqual(self.game.player.name, "Aria")
        self.assertEqual(self.game.player.class_key, "rogue")
        self.assertEqual(self.game.screen, "play")
        self.assertEqual(self.game.game_state, "world_map")


# ---------------------------------------------------------------- exploring
class TestExploring(unittest.TestCase):
    def setUp(self):
        self.game = make_game()

    def test_bad_direction(self):
        with self.assertRaises(ValueError):
            self.game.move("up")

    def test_settlement_rests_and_opens_shop(self):
        self.game.player.current_health = 1
        self.game.enter_settlement("village")
        self.assertEqual(self.game.player.current_health, self.game.player.max_health)
        self.assertEqual(self.game.screen, "merchant")
        self.assertEqual(self.game.merchant_tab, "quests")

    def test_camp(self):
        self.game.camp()
        self.assertIn("already at full health", self.game.notices[-1]["text"])
        self.game.player.current_health = 1
        self.game.camp()
        self.assertGreater(self.game.player.current_health, 1)

    def test_camp_and_scout_only_outdoors(self):
        self.game.enter_dungeon(1)
        self.game.camp()
        self.assertIn("only make camp", self.game.notices[-1]["text"])
        self.game.scout()
        self.assertIn("only scout", self.game.notices[-1]["text"])

    def test_leave_dungeon_needs_confirmation(self):
        self.game.enter_dungeon(1)
        self.game.interact()  # at the entrance (0, 0)
        self.assertEqual(self.game.screen, "confirm_leave")
        self.game.confirm_leave_dungeon(False)
        self.assertEqual(self.game.game_state, "dungeon")
        self.game.interact()
        self.game.confirm_leave_dungeon(True)
        self.assertEqual(self.game.game_state, "world_map")

    def test_world_and_dungeon_views(self):
        world = self.game.world_view()
        self.assertEqual((len(world), len(world[0])), (15, 15))
        self.assertTrue(world[7][7]["player"])
        self.game.enter_dungeon(1)
        dungeon = self.game.dungeon_view()
        self.assertEqual(len(dungeon), self.game.current_dungeon.size)
        self.assertTrue(dungeon[0][0]["player"])

    def test_inventory_equip_and_use(self):
        potion_index = next(i for i, item in enumerate(self.game.player.inventory)
                            if item["name"] == "Potion of Healing")
        self.game.player.current_health = 1
        self.game.use(potion_index)
        self.assertGreater(self.game.player.current_health, 1)
        with self.assertRaises(ValueError):
            self.game.equip(999)
        with self.assertRaises(ValueError):
            self.game.use(-999)


# ---------------------------------------------------------------- shop & quests
class TestMerchant(unittest.TestCase):
    def setUp(self):
        self.game = make_game()
        self.game.enter_settlement("village")

    def test_buy_and_sell(self):
        stock = sorted((item for kind in self.game.merchant.get_available_types()
                        for item in self.game.merchant.get_inventory_by_type(kind)),
                       key=lambda item: item["price_copper"])
        cheapest = stock[0]
        money = self.game.player.money
        self.game.buy(cheapest["name"])
        self.assertEqual(self.game.player.money, money - cheapest["price_copper"])
        count = len(self.game.player.inventory)
        self.game.sell(count - 1)
        self.assertEqual(len(self.game.player.inventory), count - 1)

    def test_cannot_buy_what_you_cannot_afford(self):
        self.game.player.money = 0
        priced = next(item for kind in self.game.merchant.get_available_types()
                      for item in self.game.merchant.get_inventory_by_type(kind) if item["price_copper"] > 0)
        with self.assertRaises(ValueError):
            self.game.buy(priced["name"])
        with self.assertRaises(ValueError):
            self.game.buy("Excalibur That Doesn't Exist")

    def test_quest_only_once(self):
        quest = self.game.quest_board.quests[0]
        self.game.attempt_quest(quest["id"])
        self.assertIn(quest["title"], self.game.notices[-1]["text"])
        with self.assertRaises(ValueError):
            self.game.attempt_quest(quest["id"])

    def test_shop_actions_need_a_merchant(self):
        self.game.close_panel()
        with self.assertRaises(ValueError):
            self.game.buy("Torch")


# ---------------------------------------------------------------- combat
class TestCombat(unittest.TestCase):
    def setUp(self):
        self.game = make_game()
        self.game.enter_dungeon(1)

    def test_victory_clears_the_room(self):
        self.game.combat_context = "dungeon"
        room = self.game.current_dungeon.get_current_room()
        self.game.start_combat(Enemy.get_random_enemy(1))
        self.game.player.current_health = self.game.player.max_health = 999  # can't lose
        self.assertEqual(fight_until_over(self.game.combat), "victory")
        xp_before = self.game.player.xp
        self.game.finish_combat()
        self.assertIsNone(self.game.combat)
        self.assertTrue(room.is_cleared)
        self.assertGreaterEqual(self.game.player.xp, xp_before)

    def test_defeat_restores_health_and_leaves_dungeon(self):
        self.game.combat_context = "dungeon"
        self.game.start_combat(Enemy.get_boss(8))
        self.game.player.current_health = 1
        self.assertEqual(fight_until_over(self.game.combat), "defeat")
        self.game.finish_combat()
        self.assertEqual(self.game.player.current_health, self.game.player.max_health)
        self.assertEqual(self.game.game_state, "world_map")

    def test_melee_attack_blocked_at_range(self):
        self.game.start_combat(Enemy.get_random_enemy(1))
        combat = self.game.combat
        self.assertGreater(combat.distance, 0)
        self.assertTrue(combat.attack_blocked())  # fighter has a melee weapon, no bow
        with self.assertRaises(ValueError):
            combat.attack()
        combat.move(-1)  # advance; the enemy also closes in
        self.assertLess(combat.distance, 2)

    def test_invalid_combat_actions(self):
        self.game.start_combat(Enemy.get_random_enemy(1))
        for action, value in (("cast", "Fireball"), ("ability", "nope"), ("item", "abc"), ("dance", "")):
            with self.assertRaises(ValueError):
                self.game.combat_action(action, value)
        with self.assertRaises(ValueError):
            self.game.finish_combat()  # not over yet
        with self.assertRaises(ValueError):
            self.game.move("north")  # can't walk away mid-fight

    def test_flee_ends_the_fight(self):
        self.game.combat_context = "dungeon"
        self.game.start_combat(Enemy.get_random_enemy(1))
        self.game.player.current_health = self.game.player.max_health = 999
        for _ in range(50):
            if self.game.combat.ended:
                break
            self.game.combat_action("flee")
        self.assertEqual(self.game.combat.outcome, "fled")
        with self.assertRaises(ValueError):
            self.game.combat_action("attack")  # fight is over
        self.game.finish_combat()
        self.assertEqual(self.game.screen, "play")

    def test_wizard_can_cast(self):
        game = make_game("wizard")
        game.start_combat(Enemy.get_random_enemy(1))
        cantrip = next(s for s in game.combat.known_spells() if s["level"] == 0)
        game.combat_action("cast", cantrip["name"])
        self.assertTrue(any("Spell Cast" in line for line in game.combat.log))


# ---------------------------------------------------------------- save / load
class TestSaveLoad(unittest.TestCase):
    def setUp(self):
        self.game = make_game()
        self.created = []

    def tearDown(self):
        for name in self.created:
            path = os.path.join(SAVE_DIR, name)
            if os.path.exists(path):
                os.remove(path)

    def test_round_trip(self):
        self.game.player.money = 4242
        self.game.enter_dungeon(2)
        filename = self.game.save_game()
        self.created.append(filename)
        loaded = GameController()
        loaded.load_game(filename)
        self.assertEqual(loaded.player.money, 4242)
        self.assertEqual(loaded.game_state, "dungeon")
        self.assertEqual(loaded.current_dungeon.tier, 2)

    def test_cannot_save_mid_fight(self):
        self.game.start_combat(Enemy.get_random_enemy(1))
        with self.assertRaises(ValueError):
            self.game.save_game()

    def test_load_rejects_bad_files(self):
        with self.assertRaises(ValueError):
            self.game.load_game("../../etc/passwd")
        corrupt = "zz_corrupt_test.json"
        self.created.append(corrupt)
        with open(os.path.join(SAVE_DIR, corrupt), "w", encoding="utf-8") as f:
            json.dump({"player": {}}, f)
        with self.assertRaises(ValueError) as caught:
            self.game.load_game(corrupt)
        self.assertIn("Invalid save file", str(caught.exception))


# ---------------------------------------------------------------- Flask pages
class TestRpgWebApp(unittest.TestCase):
    def setUp(self):
        random.seed(99)
        self.game = GameController()
        self.client = create_app(self.game).test_client()

    def post(self, **form):
        response = self.client.post("/act", data=form)
        self.assertEqual(response.status_code, 303)
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        return page.get_data(as_text=True)

    def test_title_and_new_game(self):
        self.assertIn("Create Character", self.client.get("/").get_data(as_text=True))
        page = self.post(action="new_game", name="Web", age="old", class_key="fighter")
        self.assertIn("Age must be a number", page)
        with SMALL_WORLD:
            page = self.post(action="new_game", name="Web", age="20", class_key="cleric")
        self.assertIn('class="map world"', page)
        self.assertIn("Cleric", page)

    def test_every_panel_renders(self):
        with SMALL_WORLD:
            self.post(action="new_game", name="Web", age="20", class_key="wizard")
        for name, marker in (("inventory", "Inventory"), ("skills", "Unspent Skill Points"), ("pause", "Paused")):
            self.assertIn(marker, self.post(action="panel", name=name))
            self.post(action="close")
        self.game.enter_settlement("town")
        self.assertIn("Quest Board", self.client.get("/").get_data(as_text=True))
        self.game.close_panel()
        self.game.enter_dungeon(1)
        self.assertIn('class="map dungeon"', self.client.get("/").get_data(as_text=True))
        self.game.start_combat(Enemy.get_random_enemy(1))
        page = self.post(action="combat", op="choose", value="spell")
        self.assertIn("Cast Spell", page)
        self.assertIn("Combat Log", page)

    def test_bad_requests_show_errors(self):
        self.assertIn("Unknown action", self.post(action="hack"))
        self.assertIn("Start or load a game first", self.post(action="move", dir="north"))
        with SMALL_WORLD:
            self.post(action="new_game", name="Web", age="20", class_key="fighter")
        self.assertIn("Pick an item from the list", self.post(action="use", index="x"))
        self.assertIn("You&#39;re not in a fight", self.post(action="combat", op="attack"))


if __name__ == "__main__":
    unittest.main()
