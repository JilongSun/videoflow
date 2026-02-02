"""
Configuration handling for TikHub Downloader
"""

import os
import json
from downloader.utils.logger import logger_instance


class Config:
    """Configuration manager"""

    def __init__(self, config_file="config.json"):
        """Initialize configuration

        Args:
            config_file: Path to configuration file
        """
        # Set the logger
        self.logger = logger_instance

        # Set the configuration file path
        self.config_file = config_file
        self.config = {}

        # Load configuration from file
        self._load_config()

    def _load_config(self):
        """Load configuration from file"""

        # Set default configuration if file doesn't exist
        default_config = {
            # Default API Base URL
            "api_base_url": "https://api.tikhub.io",
            "update_check_url": "https://api.tikhub.io/api/v1/tikhub/downloader/version",
            "api_key": "",
            "proxy": "",
            "theme": "system",  # Options: "light", "dark", "system"
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Merge default config with loaded config
                    self.config = {**default_config, **loaded_config}

                    # Remove auto_check_update if it exists
                    if "auto_check_update" in self.config:
                        del self.config["auto_check_update"]
            else:
                # Create default config file if it doesn't exist
                self.config = default_config
                self.save()
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            self.config = default_config

    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")

    def get(self, key, default=None):
        """Get a configuration value

        Args:
            key: Configuration key
            default: Default value if key doesn't exist

        Returns:
            The configuration value
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
        # Optionally save immediately after setting
        self.save()
