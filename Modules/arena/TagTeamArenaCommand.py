import time
from utils.base_command import CommandBase
from utils.click_handler import ClickHandler

class TagTeamArenaCommand(CommandBase):
    def __init__(self, app, logger, click_handler):
        super().__init__(app, logger, click_handler)
        self.tag_team_battles = 0

    def execute(self):
        try:
            self.logger.info("Starting Daily Ten Classic Arena task.")
            self.click_handler.delete_popup()

            # 1. Navigate to Tag Team Arena
            if not self.navigate_to_tag_team_arena():
                self.logger.error("Failed to navigate to Tag Team Arena. Exiting task.")
                return

            # 2. Fight Tag Team Battles
            self.fight_tag_team_battles()

            # 3. Back to Bastion
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
            self.logger.info(f"{self.tag_team_battles} total classic arena battles fought")
            self.logger.info("Completed Daily Ten Classic Arena task.")

        except Exception as e:
            self.logger.error(f"Error in TagTeamArenaCommand: {e}", exc_info=True)
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

    def navigate_to_tag_team_arena(self):
        """Navigates to the Tag Team Arena screen."""
        if not self.click_handler.click_image("battleBTN.png", "Battle Button"):
            return False
        if not self.click_handler.click_image("arenaTab.png", "Arena Tab"):
            return False
        if not self.click_handler.click_image("TagTeamArena.png", "Tag Team Arena"):
            return False
        return True

    
    def fight_tag_team_battles(self):
        """Fights Tag Team battles by scrolling and searching for the battle button."""
        scroll_distances = [0, 200, 200]
        battle_count = 0
        max_battles = 5

        while battle_count < max_battles:
            for scroll in scroll_distances:
                self.logger.info(f"Scrolling by {scroll}.")
                self.click_handler.swipe_up(distance=scroll)

                # Look for the battle button
                if self.click_handler.wait_for_image("tagArenaBattle.png", "Tag Arena Battle", timeout=3):
                    self.logger.info("Found battle button.")
                    self.handle_battle()
                    battle_count += 1
                    self.logger.info(f"Battle {battle_count}/{max_battles} completed.")
                    time.sleep(2)
                    break
            else:
                # If no battle button is found in all positions, stop the loop
                self.logger.info("No battle button found in any position. Exiting.")
                break

    def handle_battle(self):
        """Handles the battle sequence (confirmation, start, wait for completion)."""
        # Click the battle button
        self.click_handler.click_image("tagArenaBattle.png", "Tag Arena Battle")

        # Confirm battle and handle token replenishment
        if not self.handle_battle_confirmation():
            return  # Exit if out of tokens

        # Start battle
        self.click_handler.click_image("tagArenaStart.png", "Tag Arena Start")

        # Wait for battle completion and click 'Tap to Continue'
        self.wait_for_battle_completion()

    def handle_battle_confirmation(self):
        """Handles the battle confirmation screen and token replenishment."""
        while self.click_handler.wait_for_image("arenaConfirm.png", "Arena Confirm", timeout=2):
            self.click_handler.click_image("arenaConfirm.png", "Arena Confirm")
            self.logger.info("Confirmed arena tokens.")
            time.sleep(2)
            self.click_handler.click_image("tagArenaBattle.png", "Tag Arena Battle")


        if self.click_handler.wait_for_image("ArenaRefillGems.png", "Tag Arena Refill", timeout=2):
            self.logger.info("Ran out of arena coins. Exiting task.")
            return False
        
        return True

    def wait_for_battle_completion(self):
        """Waits for the battle to complete and handles the 'Tap to Continue' screen."""
        self.logger.debug("Waiting for 'Tap to Continue' screen.")
        while not self.click_handler.wait_for_image("tapToContinue.png", "Tap to Continue", timeout=2):
            time.sleep(5)
        while self.click_handler.wait_for_image("tapToContinue.png", "Tap to Continue", timeout=2):
            self.click_handler.click_image("tapToContinue.png", "Tap to Continue")
            self.click_handler.press_key("esc")
            self.tag_team_battles += 1
            self.logger.info(f"Completed an arena battle. Total battles: {self.tag_team_battles}")
            return