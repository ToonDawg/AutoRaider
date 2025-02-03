import time

import pyautogui
from utils.base_command import CommandBase

            
class RewardsCommand(CommandBase):
    def __init__(self, daily_instance, logger, click_handler):
        super().__init__(daily_instance, logger, click_handler)
        self.quests_completed = 0
        self.AS_bought = 0
        self.MS_bought = 0
        self.GR_upgrades = 0
         
    def execute(self):
        self.logger.info("Starting Rewards tasks.")
        self.dailyMarketPurchase()
        self.dailyClan()
        self.dailyGemMine()
        self.dailyGuardianRingCommand()
        self.dailyQuestClaims()
        self.dailyShopCommand()
        self.dailyTimedRewards()
        self.dailyInbox()

        self.logger.info("Completed Rewards tasks.")
        
    def dailyGemMine(self):
        try:
            self.logger.info("Starting Daily Gem Mine task.")
            self.click_handler.swipe_up()
            self.click_handler.swipe_right()
            self.click_handler.click((800, 560), "Manually clicking Gem Mine")
            time.sleep(1)
            self.click_handler.click((800, 560), "Manually clicking Gem Mine")
            self.click_handler.press_key("esc")

            self.logger.info("Completed Daily Gem Mine task.")
        except Exception as e:
            self.logger.error(f"Error in DailyGemMineCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

    def dailyMarketPurchase(self):
        try:
            self.logger.info("Starting Daily Market Purchase task.")
            self.click_handler.delete_popup()

            # Navigate to the market
            if not self.click_handler._locate_image("theMarket.png", "Market Icon"):
                self.logger.warning("Market icon not found. Attempting manual navigation.")
                self.click_handler.swipe_up()
                self.click_handler.swipe_right()
                self.click_handler.click((1000, 600), "Manually clicking Market")
            else:
                self.click_handler.click_image("theMarket.png", "Clicking Market")

            # Purchase shards
            def purchase_shards(shop_icon, get_icon, shard_type):
                for _ in range(3):
                    if not self.click_handler._locate_image(shop_icon, f"{shard_type} Shop Icon"):
                        return
                    self.click_handler.click_image(shop_icon, f"Clicking {shard_type} Shop")
                    while self.click_handler._locate_image(get_icon, f"{shard_type} Get Icon"):
                        self.click_handler.click_image(get_icon, f"Clicking {shard_type} Get Icon")
                        if shard_type == "Mystery":
                            self.MS_bought += 1
                        elif shard_type == "Ancient":
                            self.AS_bought += 1

            time.sleep(1)
            purchase_shards("shopShard.png", "getShard.png", "Mystery")
            purchase_shards("marketAS.png", "getAS.png", "Ancient")
            self.click_handler.swipe_left()
            purchase_shards("shopShard.png", "getShard.png", "Mystery")
            purchase_shards("marketAS.png", "getAS.png", "Ancient")
            
            self.logger.info(f"Purchased {self.MS_bought} Mystery Shards and {self.AS_bought} Ancient Shards.")
            self.click_handler.back_to_bastion()
        except Exception as e:
            self.logger.error(f"Error in DailyMarketPurchaseCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()


    def dailyShopCommand(self):
        try:
            self.logger.info("Starting Daily Shop task.")
            self.steps = {"Shop_claimed": []}

            # Check if the Shop Button is available
            if self.click_handler.wait_for_image("shopBTN.png", "Shop Button", timeout=3):
                self.click_handler.click_image("shopBTN.png", "Clicking Shop Button")
                time.sleep(2)

                # Claim Ancient Shard
                def claim_shard(shard_image, shard_type):
                    while self.click_handler._locate_image(shard_image, f"Claim {shard_type}"):
                        self.click_handler.click_image(shard_image, f"Claiming {shard_type}")
                        time.sleep(2)
                        self.click_handler.click_image("defaultClaim.png", "Confirming Claim")
                        self.steps["Shop_claimed"].append(shard_type)
                        self.logger.info(f"Claimed {shard_type} from shop.")
                        time.sleep(3)

                claim_shard("claimAS.png", "Ancient Shard")
                claim_shard("claimMS.png", "Mystery Shard")

                # Claim Free Gifts from Offers
                if self.click_handler._locate_image("offers.png", "Offers Section"):
                    self.click_handler.click_image("offers.png", "Opening Offers Section")
                    time.sleep(2)

                    # Scroll and click through all offers
                    for x_position in range(724, 1400, 40):
                        self.click_handler.click((x_position, 300), "Clicking offer item")
                        if self.click_handler._locate_image("claimFreeGift.png", "Free Gift Icon"):
                            self.click_handler.click_image("claimFreeGift.png", "Claiming Free Gift")
                            self.steps["Shop_claimed"].append("Free Gift")
                            self.logger.info("Claimed Free Gift from offers.")
                            time.sleep(1)
                    time.sleep(1.5)

                self.click_handler.back_to_bastion()
                self.click_handler.delete_popup()
                self.logger.info("Completed Daily Shop task.")
            else:
                self.logger.warning("Shop button not found on screen.")
        except Exception as e:
            self.logger.error(f"Error in DailyShopCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
        
    def dailyGuardianRingCommand(self):
        try:
            self.logger.info("Starting Daily Guardian Ring task.")
            if not self.click_handler._locate_image("guardianRing.png", "Guardian Ring Button"):
                self.click_handler.swipe_left()
                self.click_handler.swipe_up()
                
            
            # Check if Guardian Ring button is available
            if self.click_handler.wait_for_image("guardianRing.png", "Guardian Ring Button", timeout=3):
                self.click_handler.click_image("guardianRing.png", "Clicking Guardian Ring Button")
                time.sleep(2)

                # Perform upgrades while the upgrade button is visible
                while self.click_handler._locate_image("GRupgrade.png", "Guardian Ring Upgrade Button"):
                    self.click_handler.click_image("GRupgrade.png", "Performing Guardian Ring Upgrade")
                    self.GR_upgrades += 1
                    self.logger.info(f"Performed Guardian Ring upgrade. Total upgrades: {self.GR_upgrades}")

                self.logger.info(f"Total Guardian Ring upgrades performed: {self.GR_upgrades}")
            else:
                self.logger.warning("Guardian Ring button not found on screen.")

            # Navigate back and clean up
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()
            self.logger.info("Completed Daily Guardian Ring task.")

        except Exception as e:
            self.logger.error(f"Error in DailyGuardianRingCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()


    def dailyTimedRewards(self):
        try:
            self.logger.info("Starting Daily Timed Rewards task.")

            # Wait for the Time Rewards button
            if self.click_handler.wait_for_image("timeRewards.png", "Time Rewards Button", timeout=2):
                self.click_handler.click_image("timeRewards.png", "Clicking Time Rewards Button")
                time.sleep(1)
                
                # Collect rewards while red notification dots are present
                while self.click_handler._locate_image("playTimeRewardsRedDot.png", "Red Notification Dot"):
                    self.click_handler.click_image("playTimeRewardsRedDot.png", "Clicking Red Notification Dot")

                # Collect rewards while red notification dots are present
                while self.click_handler._locate_image("redNotificationDot.png", "Red Notification Dot"):
                    self.click_handler.click_image("redNotificationDot.png", "Clicking Red Notification Dot")

                self.logger.info("All timed rewards collected.")
            else:
                self.logger.warning("Timed Rewards button not found on screen.")

            # Mark task completion
            self.steps = {
                "Timed_rewards": "Collected",
                "7_campaign_battles": "Not Collected"
            }
            self.logger.info("Completed Daily Timed Rewards task.")

            # Cleanup
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

        except Exception as e:
            self.logger.error(f"Error in DailyTimedRewardsCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

    def dailyClan(self):
        try:
            self.logger.info("Starting Daily Clan task.")

            # Wait for and click the Clan Button
            if self.click_handler.wait_for_image("clanBTN.png", "Clan Button", timeout=3):
                self.click_handler.click_image("clanBTN.png", "Clicking Clan Button")
                time.sleep(1)

                # Check for Clan Members Button and click it
                if self.click_handler._locate_image("clanMembers.png", "Clan Members Button"):
                    self.click_handler.click_image("clanMembers.png", "Clicking Clan Members Button")
                    time.sleep(1)

                # Check in to the clan while the Clan Check-In button is visible
                while self.click_handler._locate_image("clanCheckIn.png", "Clan Check-In Button"):
                    self.click_handler.click_image("clanCheckIn.png", "Clicking Clan Check-In Button")
                    time.sleep(1)

                # Check for Clan Treasure Button and click it
                if self.click_handler._locate_image("clanTreasure.png", "Clan Treasure Button"):
                    self.click_handler.click_image("clanTreasure.png", "Clicking Clan Treasure Button")
                    time.sleep(1)

                self.steps = {"Daily_clan": "Accessed"}
                self.logger.info("Completed Daily Clan task.")

            else:
                self.logger.warning("Clan button not found on screen.")

            # Cleanup
            self.click_handler.back_to_bastion()

        except Exception as e:
            self.logger.error(f"Error in DailyClanCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

    def dailyQuestClaims(self):
        try:
            self.logger.info("Starting Daily Quest Claims task.")

            # Wait for and click on the Quests button
            if self.click_handler.wait_for_image("quests.png", "Quests Button", timeout=10):
                self.click_handler.click_image("quests.png", "Clicking Quests Button")
                time.sleep(2)

                # Claim regular quest rewards
                while self.click_handler._locate_image("questClaim.png", "Quest Claim Button"):
                    self.click_handler.click_image("questClaim.png", "Claiming Quest Reward")
                    self.quests_completed += 1
                    self.logger.info(f"Claimed a quest reward. Total claimed: {self.quests_completed}")
                    time.sleep(1)

                # Navigate to advanced quests
                if self.click_handler._locate_image("advancedQuests.png", "Advanced Quests Button"):
                    self.click_handler.click_image("advancedQuests.png", "Clicking Advanced Quests Button")
                    time.sleep(1)

                # Claim advanced quest rewards
                while self.click_handler._locate_image("questClaim.png", "Advanced Quest Claim Button"):
                    self.click_handler.click_image("questClaim.png", "Claiming Advanced Quest Reward")
                    self.quests_completed += 1
                    self.logger.info(f"Claimed an advanced quest reward. Total claimed: {self.quests_completed}")
                    time.sleep(1)

                # Log total quests completed
                self.logger.info(f"Total quests completed: {self.quests_completed}")

            else:
                self.logger.warning("Quests button not found on screen.")
                self.steps = {"Quests_Completed": "Not Accessed"}

            # Cleanup
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

            self.logger.info("Completed Daily Quest Claims task.")
        except Exception as e:
            self.logger.error(f"Error in DailyQuestClaimsCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()


    def dailyInbox(self):
        try:
            self.logger.info("Starting Daily Inbox task.")
            
            # Open Inbox using hotkey
            self.click_handler.press_key("i", "Opening Inbox")
            time.sleep(1)

            # Define inbox items to collect
            inbox_items = [
                "inbox_brew",
                "inbox_purple_forge",
                "inbox_yellow_forge",
                "inbox_coin",
                "inbox_potion",
            ]

            # Iterate over inbox items and collect
            for item in inbox_items:
                item_image = f"{item}.png"
                while self.click_handler._locate_image(item_image, f"Locating {item} in Inbox"):
                    self.logger.info(f"Found {item}, attempting to collect.")
                    location = self.click_handler._locate_image(item_image)
                    if location:
                        x, y = pyautogui.center(location)
                        # Move to the collect button (250 pixels to the right)
                        self.click_handler.click((x + 250, y), f"Clicking Collect button for {item}")
                        time.sleep(2)
                        self.logger.info(f"Collected inbox item: {item}")

            # Mark inbox as accessed
            self.steps = {"daily_inbox": "Accessed"}
            self.logger.info("Completed Daily Inbox task.")

            # Cleanup
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()

        except Exception as e:
            self.logger.error(f"Error in DailyInboxCommand: {e}")
            self.click_handler.back_to_bastion()
            self.click_handler.delete_popup()