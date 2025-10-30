import sqlite3
import json
from typing import List, Tuple, Optional, Dict

class ButtonDatabase:
    """Database handler for persistent button storage"""
    
    def __init__(self, db_path: str = "config/bot_data.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for storing persistent menu views
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS persistent_menus (
                message_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                menu_data TEXT NOT NULL,
                current_day INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    
    def save_menu_view(self, message_id: int, guild_id: int, channel_id: int, 
                       menu_data: dict, current_day: int = 0):
        """Save a persistent menu view to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert menu_data to JSON string
        menu_json = json.dumps(menu_data)
        
        cursor.execute('''
            INSERT OR REPLACE INTO persistent_menus 
            (message_id, guild_id, channel_id, menu_data, current_day)
            VALUES (?, ?, ?, ?, ?)
        ''', (message_id, guild_id, channel_id, menu_json, current_day))
        
        conn.commit()
        conn.close()
        print(f"Saved persistent menu view for message {message_id}")
    
    def get_menu_view(self, message_id: int) -> Optional[Dict]:
        """Retrieve a menu view from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT guild_id, channel_id, menu_data, current_day 
            FROM persistent_menus 
            WHERE message_id = ?
        ''', (message_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            guild_id, channel_id, menu_json, current_day = result
            menu_data = json.loads(menu_json)
            return {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'menu_data': menu_data,
                'current_day': current_day
            }
        return None
    
    def get_all_persistent_menus(self) -> List[Tuple[int, Dict]]:
        """Get all persistent menus for bot startup"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message_id, guild_id, channel_id, menu_data, current_day 
            FROM persistent_menus
        ''')
        
        results = []
        for row in cursor.fetchall():
            message_id, guild_id, channel_id, menu_json, current_day = row
            menu_data = json.loads(menu_json)
            results.append((message_id, {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'menu_data': menu_data,
                'current_day': current_day
            }))
        
        conn.close()
        return results
    
    def delete_menu_view(self, message_id: int):
        """Delete a menu view from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM persistent_menus WHERE message_id = ?', (message_id,))
        
        conn.commit()
        conn.close()
        print(f"Deleted menu view for message {message_id}")
    
    def cleanup_old_menus(self, days: int = 7):
        """Remove menu views older than specified days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM persistent_menus 
            WHERE created_at < datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Cleaned up {deleted} old menu views")
        return deleted
