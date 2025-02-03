from logging import Logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.pyAutoRaid import AutoRaider
    from utils.click_handler import ClickHandler

class CommandBase:
    def __init__(self, app: 'AutoRaider', logger: 'Logger', click_handler: 'ClickHandler'):
        self.app = app
        self.logger = logger
        self.click_handler = click_handler

    def execute(self):
        raise NotImplementedError("Subclasses must implement the execute method.")
