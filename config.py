"""
Configuration management for multi-server Discord bot
Supports both Jamix and Mealdoo API formats
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

class ServerConfig:
    def __init__(self, config_file: str = "config/server_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
        # Create config directory if it doesn't exist
        config_dir = os.path.dirname(self.config_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                print(f"Error loading config file {self.config_file}, creating new one")
        
        # Default configuration
        return {
            "servers": {},
            "default_menu_config": {
                "api_type": "jamix",  # "jamix" or "mealdoo"
                "customer_id": "12345",
                "kitchen_id": "12",
                "site_id": None,  # Deprecated - use site_path for Mealdoo
                "site_path": None,  # For Mealdoo API (e.g., "org/location")
                "daily_post_time": "07:00",
                "daily_channel_id": None,
                "language": "fi"
            }
        }
    
    def save_config(self) -> None:
        """Save configuration to file"""
        try:
            # Create directory if it doesn't exist
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_server_config(self, guild_id: int) -> Dict:
        """Get configuration for a specific server"""
        guild_str = str(guild_id)
        if guild_str not in self.config["servers"]:
            # Create default config for new server
            self.config["servers"][guild_str] = self.config["default_menu_config"].copy()
            self.save_config()
        
        return self.config["servers"][guild_str]
    
    def set_server_menu(self, guild_id: int, customer_id: str, kitchen_id: str) -> None:
        """Set menu IDs for a server (Jamix API or Mealdoo API)"""
        guild_str = str(guild_id)
        server_config = self.get_server_config(guild_id)
        
        # Detect if this is Mealdoo setup (customer_id is "mealdoo")
        if customer_id.lower() == "mealdoo":
            server_config["api_type"] = "mealdoo"
            server_config["site_path"] = kitchen_id  # kitchen_id is actually the path like "org/location"
            server_config["customer_id"] = None
            server_config["kitchen_id"] = None
            server_config["site_id"] = None
        else:
            # Jamix setup
            server_config["api_type"] = "jamix"
            server_config["customer_id"] = customer_id
            server_config["kitchen_id"] = kitchen_id
            server_config["site_id"] = None
            server_config["site_path"] = None
        
        self.config["servers"][guild_str] = server_config
        self.save_config()
    
    def set_daily_channel(self, guild_id: int, channel_id: int) -> None:
        """Set daily posting channel for a server"""
        guild_str = str(guild_id)
        server_config = self.get_server_config(guild_id)
        server_config["daily_channel_id"] = channel_id
        self.config["servers"][guild_str] = server_config
        self.save_config()
    
    def get_menu_url(self, guild_id: int) -> str:
        """Get the API URL for a server (Jamix or Mealdoo)"""
        config = self.get_server_config(guild_id)
        api_type = config.get("api_type", "jamix")
        language = config.get("language", "fi")
        
        if api_type == "mealdoo":
            # Mealdoo API format with query parameters
            site_path = config.get("site_path", "org/location")
            # Get dates for next 7 days as comma-separated string
            today = datetime.now()
            dates = []
            for i in range(7):
                day = today if i == 0 else (today + timedelta(days=i))
                dates.append(f"{day.year}-{day.month:02d}-{day.day:02d}")
            
            dates_param = ",".join(dates)
            return f"https://api.fi.poweresta.com/publicmenu/dates/{site_path}/?menu=Ruokalista&dates={dates_param}"
        else:
            # Jamix API format
            customer_id = config.get("customer_id", "12345")
            kitchen_id = config.get("kitchen_id", "12")
            return f"https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/{customer_id}/{kitchen_id}?lang={language}"
    
    def get_daily_channel(self, guild_id: int) -> Optional[int]:
        """Get daily posting channel for a server"""
        config = self.get_server_config(guild_id)
        return config.get("daily_channel_id")
    
    def list_servers(self) -> Dict:
        """List all configured servers"""
        return self.config["servers"]

