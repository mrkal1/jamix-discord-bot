"""
Configuration management for multi-server Discord bot
"""
import json
import os
from typing import Dict, Optional

class ServerConfig:
    def __init__(self, config_file: str = "server_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
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
                "customer_id": "12345",
                "kitchen_id": "12",
                "daily_post_time": "07:00",
                "daily_channel_id": None,
                "language": "fi"
            }
        }
    
    def save_config(self) -> None:
        """Save configuration to file"""
        try:
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
        """Set menu IDs for a server"""
        guild_str = str(guild_id)
        server_config = self.get_server_config(guild_id)
        server_config["customer_id"] = customer_id
        server_config["kitchen_id"] = kitchen_id
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
        """Get the Jamix API URL for a server"""
        config = self.get_server_config(guild_id)
        customer_id = config.get("customer_id", "12345")
        kitchen_id = config.get("kitchen_id", "12")
        language = config.get("language", "fi")
        
        return f"https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/{customer_id}/{kitchen_id}?lang={language}"
    
    def get_daily_channel(self, guild_id: int) -> Optional[int]:
        """Get daily posting channel for a server"""
        config = self.get_server_config(guild_id)
        return config.get("daily_channel_id")
    
    def list_servers(self) -> Dict:
        """List all configured servers"""
        return self.config["servers"]
