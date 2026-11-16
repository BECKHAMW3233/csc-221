"""Game controller for the web version of the Dungeon RPG.

This is the original Tkinter game's main.py `Game` class and the turn logic
from gui/combat_window.py, ported so it has no GUI code at all. Every
action updates the game state and records messages; the Flask app reads
that state and draws it as HTML.

Pop-up message boxes from the desktop version become `notices` (shown at
the top of the page), and yes/no dialogs become small confirmation panels.
"""

import json
import logging
import os
import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .game.config import (
    COMBAT_DISTANCE_BANDS,
    COMBAT_MAX_DISTANCE,
    COMBAT_START_DISTANCE,
    SAVE_DIR,
    VISIBLE_RANGE,
    XP_BY_LEVEL,
    dungeon_recommended_level,
)
from .game.database import Database
from .game.models.character import Character
from .game.models.combat import CombatAction, CombatSystem
from .game.models.dungeon import Dungeon
from .game.models.enemy import Enemy
from .game.models.merchant import Merchant
from .game.models.quests import QuestBoard
from .game.models.world_map import WorldMap

WORLD_ENCOUNTER_FLAVOR = [
    "You find a quiet clearing and rest a moment. Nothing happens, but it's peaceful.",
    "A merchant's lost coin purse is half-buried in the dirt.",
    "You stumble into brambles. It's not fun, but it's not dangerous either.",
    "Wind carries the sound of distant battle. You press on.",
]
EQUIPPABLE_TYPES = ('weapon', 'ranged', 'armor', 'shield', 'ring', 'necklace')
DIRECTIONS = ('north', 'south', 'east', 'west')
WORLD_VIEW_RANGE = 7
MAX_LOG_LINES = 40


def describe_item(item: Dict) -> str:
    """One-line item description (same wording as the desktop inventory)."""
    info_text = item['name']
    if item['type'] in ('weapon', 'ranged'):
        info_text += f" ({item['damage_dice']} {item.get('damage_type', '')})"
    elif item['type'] == 'armor':
        info_text += f" ({item.get('slot', 'chest').capitalize()}, AC {item['base_ac']})"
    elif item['type'] == 'shield':
        info_text += f" (+{item['base_ac']} AC)"
    elif item['type'] in ('ring', 'necklace') and item.get('ability_bonus'):
        bonuses = ", ".join(f"+{v} {k[:3].upper()}" for k, v in item['ability_bonus'].items())
        info_text += f" ({bonuses})"
    elif item['type'] == 'consumable' and item.get('effect', '').startswith('heal_'):
        info_text += f" (Heals {item['effect'][len('heal_'):]})"
    return info_text


def safe_save_name(name: str) -> str:
    """Turn a character name into something safe to use in a file name."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return cleaned or "hero"


def validate_save_data(save_data: Dict[str, Any]) -> bool:
    """Return True if save_data has every key a save file needs."""
    if not isinstance(save_data, dict):
        return False
    required_keys = {'player', 'world_map'}
    player_keys = {'name', 'age', 'class_key', 'level', 'xp', 'current_health', 'inventory'}
    if not all(key in save_data for key in required_keys):
        return False
    if not all(key in save_data['player'] for key in player_keys):
        return False
    if not all(key in save_data['world_map'] for key in {'size', 'player_pos', 'nodes'}):
        return False
    return True


class CombatState:
    """One fight in progress: the port of the desktop CombatWindow's logic."""

    def __init__(self, character: Character, enemy: Enemy, combat_system: CombatSystem):
        self.character = character
        self.enemy = enemy
        self.combat_system = combat_system
        self.distance = COMBAT_START_DISTANCE
        self.log: List[str] = []
        self.ended = False
        self.outcome: Optional[str] = None
        self.choosing: Optional[str] = None  # 'spell', 'ability' or 'item' sub-menu
        self.log_message(f"Combat initiated between {character.name} and {enemy.name}!")
        if self.distance > 0:
            self.log_message(f"You start at {COMBAT_DISTANCE_BANDS[self.distance]} range - "
                             f"Advance to close the gap or stay back and use a ranged weapon.")

    # ----- display helpers -----
    def log_message(self, message: str) -> None:
        self.log.append(message)

    @property
    def range_name(self) -> str:
        return COMBAT_DISTANCE_BANDS[self.distance]

    def weapon_at_current_range(self) -> Optional[Dict]:
        return self.character.weapon_for_range(self.distance == 0)

    def attack_blocked(self) -> bool:
        """True only when a melee weapon is equipped, there's no ranged
        weapon, and the enemy is out of melee reach."""
        weapon = self.character.weapon_for_range(self.distance == 0)
        return weapon is None and bool(self.character.equipped_melee_weapon)

    def can_advance(self) -> bool:
        return self.distance > 0

    def can_retreat(self) -> bool:
        return self.distance < COMBAT_MAX_DISTANCE

    def known_spells(self) -> List[Dict]:
        db = Database()
        spells = []
        for spell_name in getattr(self.character, 'known_spells', []):
            spell = db.get_spell(spell_name)
            if spell:
                spells.append({**spell,
                               'can_cast': self.character.can_cast(spell_name),
                               'slots_left': self.character.spell_slots.get(spell['level'], 0)})
        return spells

    def usable_items(self) -> List[Dict]:
        return [(index, item) for index, item in enumerate(self.character.inventory)
                if item['type'] == 'consumable']

    # ----- turn flow -----
    def _require_active(self) -> None:
        if self.ended:
            raise ValueError("This fight is already over.")

    def _check_end(self) -> bool:
        is_ended, outcome = self.combat_system.check_combat_status(self.character, self.enemy)
        if is_ended:
            self._finish(outcome)
        return is_ended

    def _finish(self, outcome: str) -> None:
        self.ended = True
        self.outcome = outcome
        self.choosing = None
        self.log_message("=" * 40)
        if outcome == 'victory':
            rewards = self.combat_system.distribute_rewards(self.character, self.enemy)
            self.log_message("Victory!")
            self.log_message(f"Gained {rewards['xp']} XP and {rewards['copper']} copper")
            for item in rewards['items']:
                self.log_message(f"Received item: {item}")
        elif outcome == 'defeat':
            self.log_message("Defeat... You have been slain!")
        elif outcome == 'fled':
            self.log_message("You have escaped from combat!")

    def _enemy_turn(self) -> None:
        self.log_message("=== Enemy Turn ===")
        if self.distance > 0:
            move_result = self.combat_system.process_turn(self.enemy, self.character, CombatAction(type='move'))
            for message in move_result['messages']:
                self.log_message(message)
            if move_result['success']:
                self.distance -= 1
                self.log_message(f"{self.enemy.name} closes in - now at {self.range_name} range.")
            self._check_end()
            return
        result = self.combat_system.process_turn(self.enemy, self.character, CombatAction(type='attack'))
        for message in result['messages']:
            self.log_message(message)
        self._check_end()

    def attack(self) -> None:
        self._require_active()
        if self.attack_blocked():
            raise ValueError("Your melee weapon can't reach from here - advance or use a ranged weapon.")
        self.choosing = None
        result = self.combat_system.process_turn(self.character, self.enemy, CombatAction(type='attack'),
                                                 distance=self.distance)
        self.log_message("=== Player Turn ===")
        for message in result['messages']:
            self.log_message(message)
        if not self._check_end():
            self._enemy_turn()

    def move(self, delta: int) -> None:
        self._require_active()
        if (delta < 0 and not self.can_advance()) or (delta > 0 and not self.can_retreat()):
            raise ValueError("You can't move any further in that direction.")
        verb = "advance" if delta < 0 else "retreat"
        self.choosing = None
        self.log_message("=== Move ===")
        result = self.combat_system.process_turn(self.character, self.enemy, CombatAction(type='move'))
        for message in result['messages']:
            self.log_message(message)
        if result['success']:
            self.distance = max(0, min(COMBAT_MAX_DISTANCE, self.distance + delta))
            self.log_message(f"{self.character.name} {verb}s - now at {self.range_name} range.")
        if not self._check_end():
            self._enemy_turn()

    def cast_spell(self, spell_name: str) -> None:
        self._require_active()
        if spell_name not in getattr(self.character, 'known_spells', []):
            raise ValueError(f"You don't know a spell called '{spell_name}'.")
        if not self.character.can_cast(spell_name):
            raise ValueError(f"You can't cast {spell_name} right now (no spell slots left).")
        self.choosing = None
        result = self.combat_system.process_turn(
            self.character, self.enemy, CombatAction(type='cast_spell', spell_name=spell_name))
        self.log_message("=== Spell Cast ===")
        for message in result['messages']:
            self.log_message(message)
        if not self._check_end():
            self._enemy_turn()

    def use_ability(self, skill_id: str) -> None:
        self._require_active()
        skill = next((s for s in self.character.get_active_skills() if s['id'] == skill_id), None)
        if skill is None:
            raise ValueError("You don't have that ability.")
        self.choosing = None
        had_pending_power_strike = getattr(self.character, 'pending_power_strike', False)
        result = self.character.use_active_skill(skill_id)
        self.log_message(result['message'])
        if result['success'] and had_pending_power_strike and skill['effect'].get('type') != 'active_power_strike':
            self.character.pending_power_strike = False
            self.log_message(f"{self.character.name}'s readied Power Strike fizzles, unused.")
        if not result['success']:
            return
        if skill['effect'].get('type') == 'active_heal_percent':
            self._enemy_turn()

    def use_item(self, index: int) -> None:
        self._require_active()
        try:
            item = self.character.inventory[index]
        except (IndexError, TypeError):
            raise ValueError("That item isn't in your inventory any more.") from None
        if item['type'] != 'consumable':
            raise ValueError(f"{item['name']} can't be used in combat.")
        self.choosing = None
        if getattr(self.character, 'pending_power_strike', False):
            self.character.pending_power_strike = False
            self.log_message(f"{self.character.name}'s readied Power Strike fizzles, unused.")
        health_before = self.character.current_health
        if self.character.use_healing_potion(item):
            heal_amount = self.character.current_health - health_before
            self.log_message(f"{self.character.name} used {item['name']} and healed for {heal_amount} HP!")
            logging.info(f"Combat item use attempt - Item: {item['name']}, Success: True")
            if not self._check_end():
                self._enemy_turn()
        else:
            logging.info(f"Combat item use attempt - Item: {item['name']}, Success: False")
            self.log_message(f"Failed to use {item['name']}!")

    def flee(self) -> None:
        self._require_active()
        self.choosing = None
        self.log_message("=== Flee Attempt ===")
        result = self.combat_system.process_turn(self.character, self.enemy, CombatAction(type='flee'),
                                                 distance=self.distance)
        for message in result['messages']:
            self.log_message(message)
        if result['fled']:
            self.log_message("Escaped successfully!")
            self._finish('fled')
        else:
            self.log_message("Failed to escape!")
            self._enemy_turn()


class GameController:
    """Holds one player's game and applies actions to it (port of main.py `Game`)."""

    def __init__(self):
        self.db = Database()
        self.player: Optional[Character] = None
        self.world_map: Optional[WorldMap] = None
        self.current_dungeon: Optional[Dungeon] = None
        self.merchant: Optional[Merchant] = None
        self.quest_board: Optional[QuestBoard] = None
        self.game_state = 'menu'          # 'menu', 'world_map' or 'dungeon'
        self.combat_system = CombatSystem()
        self.combat: Optional[CombatState] = None
        self.combat_context: Optional[str] = None  # 'dungeon', 'vault_boss' or 'encounter'
        self.panel: Optional[str] = None  # 'merchant', 'inventory', 'skills', 'pause', 'load', 'confirm_leave'
        self.merchant_tab: Optional[str] = None
        self.notices: List[Dict[str, str]] = []
        self.log: List[str] = []

    # ------------------------------------------------------------------
    # messages
    # ------------------------------------------------------------------
    def notify(self, text: str, kind: str = 'info') -> None:
        """Show a message at the top of the page (replaces messagebox pop-ups)."""
        self.notices.append({'text': text, 'kind': kind})
        self.log.append(text)  # one journal entry per message, lines kept in order
        del self.log[:-MAX_LOG_LINES]

    @property
    def screen(self) -> str:
        """Which screen the page should draw right now."""
        if self.player is None:
            return 'load' if self.panel == 'load' else 'title'
        if self.combat is not None:
            return 'combat'
        return self.panel or 'play'

    # ------------------------------------------------------------------
    # new / save / load
    # ------------------------------------------------------------------
    def class_options(self) -> Dict[str, Dict[str, Any]]:
        return self.db.get_all_classes()

    def new_game(self, name: str, age_text: str, class_key: str) -> None:
        name = str(name).strip()
        if not name:
            raise ValueError("Character name can't be blank.")
        if len(name) > 30:
            raise ValueError("Character name must be 30 characters or fewer.")
        try:
            age = int(str(age_text).strip())
        except ValueError:
            raise ValueError("Age must be a number") from None
        if not 1 <= age <= 100:
            raise ValueError("Age must be between 1 and 100")
        if class_key not in self.class_options():
            raise ValueError(f"'{class_key}' is not a valid class.")
        self.player = Character(name=name, age=age, class_key=class_key)
        self.world_map = WorldMap()
        self.current_dungeon = None
        self.combat = None
        self.panel = None
        self.game_state = 'world_map'
        self.log = []
        self.notify(f"{name} the {self.player.title} sets out into the wild. "
                    "Explore with W/A/S/D to find villages and dungeons.")

    def list_saves(self) -> List[str]:
        try:
            files = [f for f in os.listdir(SAVE_DIR) if f.endswith('.json')]
        except OSError:
            return []
        return sorted(files, key=lambda f: os.path.getmtime(os.path.join(SAVE_DIR, f)), reverse=True)

    def save_game(self) -> str:
        if not self.player or not self.world_map:
            raise ValueError("No active game to save")
        if self.combat is not None:
            raise ValueError("You can't save in the middle of a fight.")
        save_data = {
            'player': self.player.to_dict(),
            'game_state': self.game_state,
            'world_map': self.world_map.to_dict(),
            'dungeon': self.current_dungeon.to_dict() if self.current_dungeon else None,
        }
        filename = f"{safe_save_name(self.player.name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(os.path.join(SAVE_DIR, filename), 'w', encoding='utf-8') as f:
                json.dump(save_data, f)
        except OSError as error:
            logging.error(f"Error saving game: {error}")
            raise ValueError(f"Failed to save game: {error}") from None
        logging.info(f"Game saved: {filename}")
        self.panel = None
        self.notify(f"Game saved successfully! ({filename})", 'success')
        return filename

    def load_game(self, filename: str) -> None:
        if filename not in self.list_saves():  # only files we listed - no paths
            raise ValueError("That save file doesn't exist.")
        try:
            with open(os.path.join(SAVE_DIR, filename), 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            if not validate_save_data(save_data):
                raise ValueError("Invalid save file format")
            player = Character(**save_data['player'])
            world_map = WorldMap(**save_data['world_map'])
            dungeon = Dungeon(**save_data['dungeon']) if save_data.get('dungeon') else None
        except (OSError, ValueError, TypeError, KeyError) as error:
            logging.error(f"Error loading game: {error}")
            raise ValueError(f"Failed to load game: {error}") from None
        self.player, self.world_map, self.current_dungeon = player, world_map, dungeon
        self.game_state = save_data.get('game_state', 'world_map')
        if self.game_state == 'dungeon' and self.current_dungeon is None:
            self.game_state = 'world_map'
        self.combat = None
        self.panel = None
        self.log = []
        self.notify(f"Loaded {filename}. Welcome back, {self.player.name}!", 'success')

    def quit_to_title(self) -> None:
        self.__init__()

    # ------------------------------------------------------------------
    # map views (replace the Tkinter canvas drawing)
    # ------------------------------------------------------------------
    def effective_view_range(self) -> int:
        bonus = 2 if self.player.has_item_named('Torch') else 0
        return VISIBLE_RANGE + bonus

    def world_view(self) -> List[List[Dict[str, Any]]]:
        px, py = self.world_map.player_pos
        rows = []
        for y in range(py - WORLD_VIEW_RANGE, py + WORLD_VIEW_RANGE + 1):
            row = []
            for x in range(px - WORLD_VIEW_RANGE, px + WORLD_VIEW_RANGE + 1):
                if not (0 <= x < self.world_map.size and 0 <= y < self.world_map.size):
                    row.append({'edge': True})
                    continue
                node = self.world_map.nodes[y][x]
                label = ''
                if node.kind == 'dungeon':
                    label = 'Cleared' if node.cleared else f"T{node.tier} Lv{dungeon_recommended_level(node.tier)}+"
                elif node.kind == 'encounter' and node.cleared:
                    label = 'Explored'
                elif node.kind == 'encounter' and node.scouted:
                    label = f"T{node.tier}"
                row.append({'terrain': node.terrain, 'kind': node.kind, 'cleared': node.cleared,
                            'label': label, 'player': (x, y) == (px, py)})
            rows.append(row)
        return rows

    def dungeon_view(self) -> List[List[Dict[str, Any]]]:
        dungeon = self.current_dungeon
        dungeon.view_range = self.effective_view_range()
        px, py = dungeon.player_pos
        view = dungeon.view_range
        rows = []
        for y in range(dungeon.size):
            row = []
            for x in range(dungeon.size):
                room = dungeon.rooms[y][x]
                in_range = abs(x - px) <= view and abs(y - py) <= view
                if not (in_range and room.is_visible):
                    row.append({'hidden': True, 'player': (x, y) == (px, py)})
                    continue
                marks = []
                if room.enemies and not room.is_cleared:
                    marks.append(('E', 'enemy'))
                if room.has_treasure and not room.treasure_looted:
                    marks.append(('T', 'treasure'))
                if room.has_merchant and not room.merchant_visited:
                    marks.append(('M', 'merchant'))
                if room.is_end_room:
                    if room.is_locked:
                        marks.append(('V', 'vault-locked'))
                    elif room.boss_defeated:
                        marks.append(('V', 'vault-done'))
                    else:
                        marks.append(('B', 'boss'))
                row.append({'doors': room.doors, 'marks': marks, 'cleared': room.is_cleared,
                            'exit': (x, y) == (0, 0), 'player': (x, y) == (px, py)})
            rows.append(row)
        return rows

    def next_level_xp(self) -> str:
        if self.player.level >= len(XP_BY_LEVEL):
            return "max level"
        return str(XP_BY_LEVEL[self.player.level])

    def location_text(self) -> str:
        if self.game_state == 'dungeon' and self.current_dungeon:
            d = self.current_dungeon
            x, y = d.player_pos
            return f"Tier {d.tier} dungeon - room ({x}, {y})" + (" - the exit" if (x, y) == (0, 0) else "")
        node = self.world_map.get_current_node()
        x, y = self.world_map.player_pos
        place = node.kind if node.kind != 'empty' else node.terrain
        return f"World map ({x}, {y}) - {place}"

    # ------------------------------------------------------------------
    # movement and interaction
    # ------------------------------------------------------------------
    def _require_exploring(self) -> None:
        if self.player is None:
            raise ValueError("Start or load a game first.")
        if self.combat is not None:
            raise ValueError("Finish the fight first.")

    def move(self, direction: str) -> None:
        self._require_exploring()
        if direction not in DIRECTIONS:
            raise ValueError(f"'{direction}' is not a direction.")
        self.panel = None
        if self.game_state == 'world_map' and self.world_map:
            if self.world_map.move_player(direction):
                self._on_world_node_entered()
            else:
                self.notify("You can't go that way.")
        elif self.game_state == 'dungeon' and self.current_dungeon:
            if self.current_dungeon.move_player(direction):
                current_room = self.current_dungeon.get_current_room()
                if current_room.enemies and not current_room.is_cleared:
                    self.combat_context = 'dungeon'
                    self.start_combat(current_room.enemies[0])
            else:
                self.notify("There's no door that way.")

    def _on_world_node_entered(self) -> None:
        node = self.world_map.get_current_node()
        if node.kind in ('village', 'town'):
            self.enter_settlement(node.kind)
        elif node.kind == 'dungeon' and not node.cleared:
            self.enter_dungeon(node.tier)
        elif node.kind == 'encounter' and not node.cleared:
            self.trigger_world_encounter(node.tier)

    def enter_settlement(self, kind: str) -> None:
        was_hurt = self.player.current_health < self.player.max_health
        self.player.long_rest()
        self.merchant = Merchant()
        self.quest_board = QuestBoard()
        self.open_merchant()
        label = "town" if kind == 'town' else "village"
        if was_hurt:
            self.notify(f"You rest at the {label} - HP and spell slots fully restored.", 'success')
        else:
            self.notify(f"You arrive at the {label}.")

    def open_merchant(self) -> None:
        self.panel = 'merchant'
        self.merchant_tab = 'quests' if self.quest_board else None

    def enter_dungeon(self, tier: int) -> None:
        self.current_dungeon = Dungeon(tier=tier)
        self.current_dungeon.view_range = self.effective_view_range()
        self.game_state = 'dungeon'
        self.notify(f"You descend into a Tier {tier} dungeon "
                    f"(recommended level {dungeon_recommended_level(tier)}+). Press E at the entrance to leave.")

    def leave_dungeon(self) -> None:
        self.current_dungeon = None
        self.game_state = 'world_map'
        self.panel = None

    def trigger_world_encounter(self, tier: int) -> None:
        if self.world_map.roll_encounter_is_fight():
            enemy = Enemy.get_random_enemy(tier)
            self.combat_context = 'encounter'
            self.notify(f"A {enemy.name} ambushes you on the road!", 'warning')
            self.start_combat(enemy)
        else:
            self.notify(random.choice(WORLD_ENCOUNTER_FLAVOR))
            self.world_map.get_current_node().cleared = True

    def interact(self) -> None:
        self._require_exploring()
        if self.game_state == 'world_map':
            node = self.world_map.get_current_node()
            if node.kind in ('village', 'town') and self.merchant:
                self.open_merchant()  # web extra: reopen the shop without stepping off and on
            else:
                self.notify("There's nothing to interact with here.")
            return
        room = self.current_dungeon.get_current_room()
        if self.current_dungeon.player_pos == (0, 0):
            self.panel = 'confirm_leave'
        elif room.has_treasure and not room.treasure_looted:
            loot_lines = self._apply_loot(self.current_dungeon.get_treasure_loot())
            room.treasure_looted = True
            self.notify("You found treasure!\n" + "\n".join(loot_lines), 'success')
        elif room.has_merchant and not room.merchant_visited:
            self.merchant = Merchant(max_tier=self.current_dungeon.tier)
            self.quest_board = None
            self.open_merchant()
        elif room.is_end_room and room.is_locked:
            if self.current_dungeon.try_unlock_vault(self.player):
                self.notify("You pick the lock with your Thieves' Tools. The vault creaks open!", 'success')
            else:
                self.notify("This vault is locked. You need Thieves' Tools.", 'warning')
        elif room.is_end_room and not room.boss_defeated:
            boss = self.current_dungeon.get_vault_boss()
            self.combat_context = 'vault_boss'
            self.notify(f"{boss.name} rises to guard the vault!", 'warning')
            self.start_combat(boss)
        elif room.is_end_room and room.boss_defeated:
            self.notify("The vault lies empty, its guardian already defeated.")
        else:
            self.notify("There's nothing to interact with here.")

    def confirm_leave_dungeon(self, leave: bool) -> None:
        if self.panel != 'confirm_leave':
            raise ValueError("There's nothing to confirm.")
        if leave:
            self.leave_dungeon()
            self.notify("You climb back out to the world map.")
        else:
            self.panel = None

    def camp(self) -> None:
        self._require_exploring()
        if self.game_state != 'world_map':
            self.notify("You can only make camp out in the open world.")
            return
        if self.player.current_health >= self.player.max_health:
            self.notify("You're already at full health.")
            return
        healed = self.player.camp_rest()
        self.notify(f"You make camp for the night and recover {healed} HP "
                    f"({self.player.current_health}/{self.player.max_health}). "
                    "A proper bed at a village or town will restore you fully.", 'success')

    def scout(self) -> None:
        self._require_exploring()
        if self.game_state != 'world_map':
            self.notify("You can only scout the surrounding area out in the open world.")
            return
        found = self.world_map.scout_nearby()
        if not found:
            self.notify("You survey the surrounding area and find nothing new of note.")
            return
        tiers = ", ".join(f"Tier {node.tier}" for node in found)
        self.notify(f"You spot {len(found)} potential encounter site(s) nearby: {tiers}.")

    def _apply_loot(self, loot) -> List[str]:
        lines = []
        for drop_type, value in loot:
            if drop_type == 'copper':
                self.player.money += value
                lines.append(f"+ {value} copper")
            else:
                item = self.db.get_item(value)
                if item:
                    self.player.add_item(item)
                    lines.append(f"+ {item['name']}")
        return lines

    # ------------------------------------------------------------------
    # panels: pause, inventory, skills, merchant
    # ------------------------------------------------------------------
    def open_panel(self, panel: str) -> None:
        if panel == 'load':
            self.panel = 'load'
            return
        self._require_exploring()
        if panel not in ('inventory', 'skills', 'pause'):
            raise ValueError(f"Unknown panel '{panel}'.")
        self.panel = None if self.panel == panel else panel

    def close_panel(self) -> None:
        self.panel = None

    def _inventory_item(self, index: int) -> Dict:
        try:
            return self.player.inventory[int(index)]
        except (IndexError, ValueError, TypeError):
            raise ValueError("That item isn't in your inventory any more.") from None

    def equip(self, index: int) -> None:
        self._require_exploring()
        item = self._inventory_item(index)
        if item['type'] not in EQUIPPABLE_TYPES:
            raise ValueError(f"{item['name']} can't be equipped.")
        if self.player.equip_item(item):
            self.notify(f"Equipped {item['name']}.", 'success')
        else:
            self.notify(f"Couldn't equip {item['name']}.", 'warning')

    def use(self, index: int) -> None:
        self._require_exploring()
        item = self._inventory_item(index)
        if item['type'] != 'consumable':
            raise ValueError(f"{item['name']} can't be used.")
        before = self.player.current_health
        if self.player.use_healing_potion(item):
            self.notify(f"You use {item['name']} and recover {self.player.current_health - before} HP.", 'success')
        else:
            self.notify(f"{item['name']} has no effect right now.")

    def skill_tree(self) -> List[Dict[str, Any]]:
        branches = []
        for branch_name, nodes in self.db.get_skill_branches().items():
            rows = []
            for node in sorted(nodes, key=lambda n: n['tier']):
                unlocked = self.player.has_skill(node['id'])
                can_unlock = self.player.can_unlock_skill(node['id'])
                rows.append({**node, 'unlocked': unlocked, 'can_unlock': can_unlock,
                             'status': "Unlocked" if unlocked else ("Available" if can_unlock else "Locked")})
            branches.append({'name': branch_name.title(), 'nodes': rows})
        return branches

    def unlock_skill(self, skill_id: str) -> None:
        self._require_exploring()
        if self.player.unlock_skill(skill_id):
            skill = self.db.get_skill(skill_id)
            self.notify(f"Unlocked {skill['name'] if skill else skill_id}!", 'success')
        else:
            raise ValueError("Can't unlock that skill right now.")

    def merchant_tabs(self) -> List[str]:
        tabs = ['quests'] if self.quest_board else []
        return tabs + (self.merchant.get_available_types() if self.merchant else [])

    def set_merchant_tab(self, tab: str) -> None:
        if tab not in self.merchant_tabs():
            raise ValueError(f"Unknown tab '{tab}'.")
        self.merchant_tab = tab

    def _require_merchant(self) -> None:
        self._require_exploring()
        if self.panel != 'merchant' or not self.merchant:
            raise ValueError("There's no merchant here.")

    def buy(self, item_name: str) -> None:
        self._require_merchant()
        stock = [i for kind in self.merchant.get_available_types()
                 for i in self.merchant.get_inventory_by_type(kind)]
        listing = next((i for i in stock if i['name'] == item_name), None)
        if listing is None:
            raise ValueError(f"The merchant doesn't sell '{item_name}'.")
        if self.player.money < listing['price_copper']:
            raise ValueError("You don't have enough money!")
        if self.merchant.buy_item(self.player, item_name):
            self.notify(f"You bought {item_name}!", 'success')
        else:
            raise ValueError("Failed to complete purchase!")

    def sell(self, index: int) -> None:
        self._require_merchant()
        item = self._inventory_item(index)
        value = self.merchant.get_item_value(item)
        if self.merchant.sell_item(self.player, item):
            self.notify(f"You sold {item['name']} for {value} copper!", 'success')
        else:
            raise ValueError("Failed to complete sale!")

    def attempt_quest(self, quest_id: str) -> None:
        self._require_merchant()
        if not self.quest_board:
            raise ValueError("There's no quest board here.")
        quest = next((q for q in self.quest_board.quests if q['id'] == quest_id), None)
        if quest is None:
            raise ValueError("That quest isn't on the board.")
        if self.quest_board.is_completed(quest):
            raise ValueError("You've already attempted that quest.")
        result = self.quest_board.attempt(self.player, quest)
        outcome = "Success!" if result['success'] else "Failure."
        detail = (f"{quest['title']} - {outcome} Roll: {result['roll']} + {result['modifier']} = "
                  f"{result['total']} vs DC {quest['dc']}.\n{result['text']}")
        if result['success']:
            detail += f"\nReward: {result['copper']} copper, {result['xp']} XP"
        self.notify(detail, 'success' if result['success'] else 'warning')

    # ------------------------------------------------------------------
    # combat
    # ------------------------------------------------------------------
    def start_combat(self, enemy: Enemy) -> None:
        self.player.reset_combat_flags()
        self.panel = None
        self.combat = CombatState(self.player, enemy, self.combat_system)

    def _require_combat(self) -> CombatState:
        if self.combat is None:
            raise ValueError("You're not in a fight.")
        return self.combat

    def combat_action(self, action: str, value: str = '') -> None:
        combat = self._require_combat()
        if action == 'attack':
            combat.attack()
        elif action == 'advance':
            combat.move(-1)
        elif action == 'retreat':
            combat.move(1)
        elif action == 'flee':
            combat.flee()
        elif action == 'cast':
            combat.cast_spell(value)
        elif action == 'ability':
            combat.use_ability(value)
        elif action == 'item':
            try:
                combat.use_item(int(value))
            except ValueError as error:
                if "invalid literal" in str(error):
                    raise ValueError("Pick an item from the list.") from None
                raise
        elif action == 'choose':
            if value not in ('spell', 'ability', 'item', ''):
                raise ValueError("Unknown menu.")
            combat._require_active()
            combat.choosing = value or None
        else:
            raise ValueError(f"Unknown combat action '{action}'.")

    def finish_combat(self) -> None:
        """The 'Close' button after a fight (port of main.py handle_combat_end)."""
        combat = self._require_combat()
        if not combat.ended:
            raise ValueError("The fight isn't over yet.")
        outcome = combat.outcome
        context = self.combat_context
        self.combat = None
        self.combat_context = None

        if context == 'vault_boss' and outcome == 'victory' and self.current_dungeon:
            room = self.current_dungeon.get_current_room()
            room.boss_defeated = True
            room.is_cleared = True
            loot_lines = self._apply_loot(self.current_dungeon.get_treasure_loot())
            self.notify("The vault's guardian falls! The dungeon is cleared.\n" + "\n".join(loot_lines), 'success')
            node = self.world_map.get_current_node()
            if node.kind == 'dungeon':
                node.cleared = True
        elif context == 'dungeon' and self.current_dungeon:
            current_room = self.current_dungeon.get_current_room()
            if outcome == 'victory':
                current_room.is_cleared = True
                current_room.enemies = []
            elif outcome == 'fled':
                self.current_dungeon.move_player_random_adjacent()
        elif context == 'encounter' and self.world_map:
            self.world_map.get_current_node().cleared = True

        if outcome == 'defeat':
            self.notify("You have fallen in battle. Returning to the village to recover.", 'warning')
            self.player.current_health = self.player.max_health
            self.leave_dungeon()
