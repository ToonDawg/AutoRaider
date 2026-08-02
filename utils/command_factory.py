from enum import Enum
from logging import Logger
from typing import TYPE_CHECKING
from utils.click_handler import ClickHandler

if TYPE_CHECKING:
    from app.pyAutoRaid import AutoRaider
    
class CommandKeys(Enum):
    REWARDS = "rewards"
    DAILY_TEN_CLASSIC_ARENA = "daily_ten_classic_arena"
    CLANBOSS = "clanboss"
    FACTION_WARS = "faction_wars"
    IRON_TWINS = "iron_twins"
    DOOM_TOWER = "doom_tower"
    DAILY_QUESTS = "daily_quests"
    TAG_TEAM_ARENA = "tag_team_arena"
    # v2 engine keys — registered alongside v1 rather than replacing them.
    # Off by default in every preset; run manually from the V2 Engine tab.
    CLASSIC_ARENA_V2 = "classic_arena_v2"
    IRON_TWINS_V2 = "iron_twins_v2"
    TAG_TEAM_ARENA_V2 = "tag_team_arena_v2"
    FACTION_WARS_V2 = "faction_wars_v2"
    CLANBOSS_V2 = "clanboss_v2"
    DOOM_TOWER_V2 = "doom_tower_v2"
    REWARDS_V2 = "rewards_v2"
    DAILY_QUESTS_V2 = "daily_quests_v2"
    
    @staticmethod
    def from_string(value: str):
        return next((member for member in CommandKeys if member.value == value), None)

class CommandFactory:
    def __init__(self, daily_instance: 'AutoRaider', logger: Logger, click_handler: 'ClickHandler'):
        self.app = daily_instance
        self.logger = logger
        self.click_handler = click_handler
        self.registry = {}

    def register_command(self, key, display_name, command_class):
        self.logger.info(f"Registering command: {key}, Class: {command_class}")
        self.registry[key] = {
            "display_name": display_name,
            "command_class": command_class
        }


    def get_command(self, key):
        if isinstance(key, str):
            key = CommandKeys.from_string(key)
        
        if isinstance(key, CommandKeys) and key in self.registry:
            command_info = self.registry[key]
            self.logger.info(f"Fetching command: {key}, Class: {command_info['command_class']}")
            return command_info["command_class"](self.app, self.logger, self.click_handler)

        self.logger.warning(f"Command key not found: {key}")
        return None

    def get_display_names(self):
        return [(key, info["display_name"]) for key, info in self.registry.items()]
