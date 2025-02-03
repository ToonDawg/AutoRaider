import configparser
import os
from utils.command_factory import CommandKeys
from datetime import datetime, time, timedelta


class ConfigHandler:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            self._create_default_config()
        else:
            self.config.read(config_file)

        # Ensure all CommandKeys enums are present in the Settings section
        self._initialize_enum_settings()
        self._reset_actuals_if_new_period()


    def _create_default_config(self):
        """Creates a default configuration file if it doesn't exist."""
        self.config['Settings'] = {
            'utc_today': datetime.utcnow().strftime('%d/%m/%Y'),
            'rewards': 'True',
            'clanboss': 'False',
            'automated_mode': 'False',
            'daily_ten_classic_arena': 'True',
        }
        self.config['PlannedClanBossFightsToday'] = {
            'easy': '0',
            'normal': '0',
            'hard': '0',
            'brutal': '0',
            'nightmare': '1',
            'ultra-nightmare': '1',
        }
        self.config['ActualClanBossFightsToday'] = {
            'easy': '0',
            'normal': '0',
            'hard': '0',
            'brutal': '0',
            'nightmare': '0',
            'ultra-nightmare': '0',
        }
        self.save_config()
        

    def _reset_actuals_if_new_period(self):
        """Resets ActualClanBossFightsToday if the current time is beyond the reset period."""
        now = datetime.utcnow()
        last_reset = self.config.get('Settings', 'last_reset', fallback=None)

        # Parse the last reset time or default to a distant past
        last_reset_datetime = datetime.strptime(last_reset, '%Y-%m-%d %H:%M:%S') if last_reset else datetime.min

        # Calculate the most recent reset time (11:00 UTC today or yesterday)
        reset_time = time(11, 0)
        today_reset = datetime.combine(now.date(), reset_time)
        last_reset_time = today_reset if now >= today_reset else today_reset - timedelta(days=1)

        # Perform reset if last reset occurred before the most recent reset time
        if last_reset_datetime < last_reset_time:
            self.config.set('Settings', 'last_reset', now.strftime('%Y-%m-%d %H:%M:%S'))

            if self.config.has_section('ActualClanBossFightsToday'):
                for key in self.config['ActualClanBossFightsToday']:
                    self.config.set('ActualClanBossFightsToday', key, '0')

            self.save_config()
            print(f"Resetting ActualClanBossFightsToday at {now.strftime('%H:%M')} UTC.")



    def _initialize_enum_settings(self):
        """Ensures all CommandKeys enums are present in the Settings section."""
        if not self.config.has_section("Settings"):
            self.config.add_section("Settings")

        for command_key in CommandKeys:
            key = command_key.value
            if not self.config.has_option("Settings", key):
                self.config.set("Settings", key, "False") 
        self.save_config()

    def save_config(self):
        """Writes the current configuration to the file."""
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def read_setting(self, section, key, fallback=None):
        """Reads a specific setting or entire section with an optional fallback."""
        if not self.config.has_section(section):
            return fallback
        if key is None:
            return dict(self.config.items(section))
        if self.config.has_option(section, key):
            return self.config.get(section, key)
        return fallback

    def update_setting(self, section, key, value):
        """Updates or adds a setting."""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        self.save_config()

    def delete_setting(self, section, key):
        """Deletes a specific setting."""
        if self.config.has_section(section) and self.config.has_option(section, key):
            self.config.remove_option(section, key)
            self.save_config()
        else:
            raise KeyError(f"'{key}' not found in section '{section}'")

    def delete_section(self, section):
        """Deletes an entire configuration section."""
        if self.config.has_section(section):
            self.config.remove_section(section)
            self.save_config()
        else:
            raise KeyError(f"Section '{section}' not found")
        
    def clear_section(self, section):
        """Clear all settings in a given section."""
        if self.config.has_section(section):
            self.config.remove_section(section)
            self.config.add_section(section)
            self.save_config()

    def list_settings(self, section):
        """Lists all settings in a section."""
        if self.config.has_section(section):
            return dict(self.config.items(section))
        else:
            raise KeyError(f"Section '{section}' not found")
