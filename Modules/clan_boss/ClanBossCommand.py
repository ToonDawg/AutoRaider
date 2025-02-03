import time
from utils.base_command import CommandBase


class ClanBossCommand(CommandBase):
    def execute(self):
        try:
            self.logger.info("Starting Clan Boss task.")

            # Image paths
            battle_btn_image = "battleBTN.png"
            clan_boss_image = "CB.png"

            # Coordinates for the difficulties
            difficulties = {
                "ultra-nightmare": (1200, 650),
                "nightmare": (1200, 550),
                "brutal": (1200, 450),
                "hard": (1200, 450)
            }
            
            self.app.config_handler._reset_actuals_if_new_period()

            # Read planned and actual fights from the config
            planned_fights = self.app.config_handler.list_settings("PlannedClanBossFightsToday")
            actual_fights = self.app.config_handler.list_settings("ActualClanBossFightsToday")

            # Navigate to the Clan Boss screen
            self.click_handler.click_image(battle_btn_image, "Battle button")
            self.click_handler.swipe_left()
            self.click_handler.click_image(clan_boss_image, "Clan Boss option")
            self.click_handler.click_image("demonLord2.png", "Demon Lord")
            self.click_handler.swipe_up(moveFromX=1200)
            time.sleep(1)

            for difficulty, (x, y) in difficulties.items():
                planned = int(planned_fights.get(difficulty, 0))
                actual = int(actual_fights.get(difficulty, 0))

                self.logger.info(f"{difficulty.capitalize()} planned: {planned}, actual: {actual}")

                if actual >= planned:
                    self.logger.info(f"All planned battles for {difficulty.capitalize()} completed. Skipping.")
                    continue

                # Click the difficulty button
                self.logger.info(f"Battling {difficulty.capitalize()} (Remaining: {planned - actual}).")
                self.click_handler.click((x, y), f"Selecting {difficulty.capitalize()} difficulty")
                time.sleep(1)
                
                # Claim CB rewards
                while self.click_handler.click_image("CBclaim.png", "Claim CB Rewards"):
                    time.sleep(1)
                    self.click_handler.press_key("esc", "Accepting Rewards")
                    

                if self._start_battle():
                    self.logger.info(f"Battle started for {difficulty.capitalize()}.")
                    # Update the ActualClanBossFightsToday count
                    new_actual = actual + 1
                    self.app.config_handler.update_setting("ActualClanBossFightsToday", difficulty, new_actual)
                    self.logger.info(f"Updated {difficulty.capitalize()} count: {new_actual}.")
                else:
                    self.logger.warning(f"No keys available for {difficulty.capitalize()}.")
                    break
                # Wait for continue
                if self.click_handler.wait_for_image("resultClanBoss.png", "Waiting for Clan Boss Results"):
                    self.click_handler.press_key("esc", "Return to Clan Boss Battle Screen")
                    self.click_handler.press_key("esc", "Return to Clan Boss Difficulty Screen")

            self.logger.info("Clan Boss task completed.")
        except Exception as e:
            self.logger.error(f"Error in ClanBossCommand: {e}", exc_info=True)
            self.click_handler.back_to_bastion()

    def _start_battle(self):
        """Handles the battle start logic."""
        no_key_image = "CBnokey.png"
        battle_image = "CBbattle.png"
        start_battle_image = "CBstart.png"

        # Check if the battle button is available
        if not self.click_handler._locate_image(battle_image, "Battle button found"):
            return False

        self.click_handler.click_image(battle_image, "Battle button")
        time.sleep(2)

        # Check for no keys
        if self.click_handler._locate_image(no_key_image, "No key image found"):
            self.logger.warning("No keys available for battle.")
            return False

        # Start the battle
        self.click_handler.click_image(start_battle_image, "Start battle button")
        time.sleep(1)
        return True
