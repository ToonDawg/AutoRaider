import time
import pyautogui
import random
import pygetwindow
from utils.base_command import CommandBase
from Modules.arena import DailyTenArenaCommand
        
class DailyQuestsCommand(CommandBase):
    def __init__(self, py_auto_raid_instance, logger, click_handler):
        super().__init__(py_auto_raid_instance, logger, click_handler)
        self.arena_battles = DailyTenArenaCommand.ClassicArenaCommand(self.app, self.logger, self.click_handler)
        self.steps = {}
        self.MS_bought = 0
        self.classic_battles = 0
        self.AS_bought=0
        self.MS_bought=0
        self.GR_upgrades=0
        self.quests_completed=0
        self.summoned_champs=0

    def execute(self):
        try:
            self.logger.info("Starting Daily Quests task.")

            # Step 1: Close popups
            self.click_handler.delete_popup()

            # Step 2: Execute all daily tasks
            self.daily_seven_boss_battles()
            self.daily_summon_three()
            self.daily_tavern_upgrade()
            self.daily_artifact_upgrade()
            self.arena_battles.execute(5)

            #TODO: Tag Team
            #TODO: 3 Artifacts From Dungeon
            #TODO: DT Silver Keys
            #TODO: Glyph
            #TODO: Live Arena
            #TODO: Forge
            #TODO: Sell Artifact
            #TODO: Craft Epic Artifact
            #TODO: Ascend Piece of gear


            # Final step: Return to bastion
            self.click_handler.back_to_bastion()
            self.logger.info("Daily Quests task completed successfully.")
        except Exception as e:
            self.logger.error(f"An error occurred while executing Daily Quests: {e}", exc_info=True)
            self.click_handler.back_to_bastion()

    def daily_seven_boss_battles(self):
        campaign_images = ["battleBTN.png", "campaignButtonJump.png", "campaignStart.png"]
        self.campaignreached = 0

        # Navigate through campaign images
        for image in campaign_images:
            if self.click_handler.click_image(image, f"Clicking {image.split('.')[0]}"):
                self.campaignreached += 1
                time.sleep(2)

        if self.campaignreached == 3:
            for _ in range(6):
                # Wait for replay button to appear
                self.click_handler.wait_for_image("replayCampaign.png", "Waiting for Replay Campaign button")
                
                # Click replay button while it is visible
                while self.click_handler.click_image("replayCampaign.png", "Clicking Replay Campaign button"):
                    time.sleep(2)
                    
            self.click_handler.wait_for_image("replayCampaign.png", "Waiting for Replay Campaign button")
            time.sleep(2)

            # Return to bastion if necessary
            if self.click_handler.click_image("bastion.png", "Returning to Bastion"):
                time.sleep(2)

            # Update steps and handle fallback
            self.steps["7_campaign_battles"] = "Accessed"
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
            
    
    def daily_summon_three(self):
        self.logger.info("Starting daily summon task.")
        try:
            # Locate and click the portal
            if self.click_handler.click_image("portal.png", "Clicking on portal"):
                time.sleep(2)
            else:
                # Manual fallback using swipe logic
                self.logger.error("Failed to locate portal. Performing manual swipe.")
                self.click_handler.swipe_down() 
                self.click_handler.swipe_right()
                self.click_handler.click((800, 600), "Manual click at fallback location")
                time.sleep(2)

            # Check for daily Ancient Shard summon availability
            if self.click_handler.click_image("dailyAS.png", "Opening daily Ancient Shard summon"):
                self.summoned_champs = 0
                time.sleep(2)

                # Perform initial summon
                if self.click_handler.click_image("summonOne.png", "Performing first summon"):
                    self.summoned_champs += 1
                    self.logger.info("Performed first summon.")
                    self.click_handler.wait_for_image("summonOneMore.png", "Waiting for Summon One More button", timeout=10)

                    # Perform additional summons
                    for _ in range(2):  # Perform two more summons for a total of three
                        if self.click_handler.click_image("summonOneMore.png", "Performing additional summon"):
                            self.summoned_champs += 1
                            self.logger.info(f"Performed additional summon. Total summons: {self.summoned_champs}.")
                            self.click_handler.wait_for_image("summonOneMore.png", "Waiting for Summon One More button", timeout=10)
                        else:
                            self.logger.warning("Summon One More button not found. Stopping further summons.")
                            break

                time.sleep(1)

            # Update task status
            self.steps["Daily_summon"] = "Accessed"
            self.logger.info(f"Summoning task completed. Total champions summoned: {self.summoned_champs}.")
        except Exception as e:
            self.logger.error(f"Error during daily summon task: {e}", exc_info=True)
        finally:
            # Cleanup and return to bastion
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()




    def daily_artifact_upgrade(self):
        self.logger.info("Starting daily artifact upgrade task.")
        try:
            # Activate the game window
            pygetwindow.getWindowsWithTitle("Raid: Shadow Legends")[0].activate()
            time.sleep(1)

            # Open champion artifact upgrade screen
            pyautogui.hotkey('c')
            time.sleep(1)
            self.logger.info("Opened champion menu.")

            # Navigate through the UI to locate an artifact
            self.click_handler.click((1218, 400), "Selecting a champion")
            time.sleep(1)
            self.click_handler.click((1069, 411), "Opening gear tab")
            self.logger.info("Navigating to artifact selection.")
            time.sleep(1)

            # Hide set filters
            if self.click_handler.click_image("filterButton.png", "Filter Button"):
                self.logger.info("Filter button clicked.")
                self.click_handler.swipe_up(moveFromX=600)
                self.click_handler.click_image("hideSetFilters.png", "Hiding Set Filters")

            # Scroll to view more artifacts
            self.click_handler.swipe_up(distance=400, duration=1)
            time.sleep(2)

            # Find and select an artifact that can be upgraded
            while True:
                x, y = random.randint(770, 1130), random.randint(370, 700)
                self.click_handler.click((x, y), "Selecting a random artifact for upgrade")
                self.click_handler.click_image("upgradeArtifact.png", "Clicking Upgrade Artifact Button")

                if self.click_handler._locate_image("canUpgradeItem.png", "Checking if artifact can be upgraded"):
                    self.logger.info("Found an artifact that can be upgraded.")
                    break  # Exit the loop once an upgradable artifact is found

                # If the artifact cannot be upgraded, go back to the list
                self.logger.debug("Selected artifact cannot be upgraded. Returning to item list.")
                if self.click_handler.click_image("artifactUpgradeScreen.png", "Artifact Upgrade Screen"):
                    pyautogui.press('esc')
                time.sleep(1)

            # Perform upgrades
            while self.click_handler.click_image("upgradeArtifact.png", "Clicking Upgrade Button"):
                self.logger.info("Clicked upgrade button.")
                time.sleep(2)

            # Repeat upgrades up to 6 times
            for _ in range(6):
                if self.click_handler.click_image("upgrade.png", "Performing an artifact upgrade"):
                    self.logger.info("Performed an artifact upgrade.")
                    time.sleep(4)

            # Update task completion status
            self.steps["Artifact_upgrades"] = "True"
            self.logger.info("Artifact upgrades completed successfully.")
        except Exception as e:
            self.logger.error(f"Error during artifact upgrade task: {e}", exc_info=True)
        finally:
            # Return to bastion and cleanup
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
            self.logger.info("Returned to bastion and cleared popups.")



    def daily_tavern_upgrade(self):
        self.logger.info("Starting daily tavern upgrade task.")
        try:
            # Open the tavern menu
            if self.click_handler.click_image("tav.png", "Opening tavern menu"):
                time.sleep(2)
            else:
                # Manual swipe fallback if tavern menu image is not found
                self.logger.warning("Tavern menu image not found. Attempting manual swipe.")
                self.logger.info("Swiping all the way to the right.")
                self.click_handler.swipe_left()
                self.click_handler.swipe_down()
                time.sleep(1)
                self.click_handler.click_image("tavern2.png", "Manual Tavern Click")

            # Check for the descending sort option in the tavern
            if self.click_handler.click_image("tavern_descending.png", "Selecting descending sort in tavern"):
                time.sleep(2)

                # Interact with champions in the tavern
                self.click_handler.click((560, 390), "Selecting champion for upgrade")
                self.logger.info("Preparing to select champions for upgrade.")

                # Click on Green Potion
                self.click_handler.click_image("tavernPotion.png", "Clicking Green Potion")

                # Perform tavern upgrades
                if self.click_handler.click_image("tavernUpgrade.png", "Performing tavern upgrade"):
                    self.logger.info("Performed tavern upgrade.")
                    time.sleep(2)

                # Final sacrifice action if applicable
                if self.click_handler.click_image("sacrifice.png", "Performing final sacrifice"):
                    self.logger.info("Final sacrifice completed.")
                    time.sleep(2)

            # Update task status
            self.steps["Tavern_upgrades"] = "True"
            self.logger.info("Tavern upgrades completed successfully.")
        except Exception as e:
            self.logger.error(f"Error during tavern upgrade task: {e}", exc_info=True)
        finally:
            # Cleanup and return to bastion
            self.click_handler.delete_popup()
            self.click_handler.back_to_bastion()
            self.logger.info("Returned to bastion and cleared popups.")



