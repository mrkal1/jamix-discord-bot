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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                all_menus_json TEXT,
                current_source INTEGER DEFAULT 0
            )
        ''')

        # Migrate: add new columns to existing databases that don't have them yet
        existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(persistent_menus)").fetchall()]
        if "all_menus_json" not in existing_columns:
            cursor.execute("ALTER TABLE persistent_menus ADD COLUMN all_menus_json TEXT")
            print("Database migrated: added all_menus_json column")
        if "current_source" not in existing_columns:
            cursor.execute("ALTER TABLE persistent_menus ADD COLUMN current_source INTEGER DEFAULT 0")
            print("Database migrated: added current_source column")
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    
    def save_menu_view(self, message_id: int, guild_id: int, channel_id: int,
                       menu_data: dict, current_day: int = 0,
                       all_menus_data: Optional[Dict] = None, current_source: int = 0):
        """Save a persistent menu view to the database.
        
        all_menus_data: dict of {source_name: {day: {category: [items]}}} for multi-source views.
        current_source: index of the currently-selected source.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        menu_json = json.dumps(menu_data)
        all_menus_json = json.dumps(all_menus_data) if all_menus_data is not None else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO persistent_menus 
            (message_id, guild_id, channel_id, menu_data, current_day, all_menus_json, current_source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, guild_id, channel_id, menu_json, current_day, all_menus_json, current_source))
        
        conn.commit()
        conn.close()
        print(f"Saved persistent menu view for message {message_id}")
    
    def get_menu_view(self, message_id: int) -> Optional[Dict]:
        """Retrieve a menu view from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT guild_id, channel_id, menu_data, current_day, all_menus_json, current_source
            FROM persistent_menus 
            WHERE message_id = ?
        ''', (message_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            guild_id, channel_id, menu_json, current_day, all_menus_json, current_source = result
            menu_data = json.loads(menu_json)
            all_menus_data = json.loads(all_menus_json) if all_menus_json else None
            return {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'menu_data': menu_data,
                'current_day': current_day,
                'all_menus_data': all_menus_data,
                'current_source': current_source or 0,
            }
        return None
    
    def get_all_persistent_menus(self) -> List[Tuple[int, Dict]]:
        """Get all persistent menus for bot startup"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message_id, guild_id, channel_id, menu_data, current_day, all_menus_json, current_source
            FROM persistent_menus
        ''')
        
        results = []
        for row in cursor.fetchall():
            message_id, guild_id, channel_id, menu_json, current_day, all_menus_json, current_source = row
            menu_data = json.loads(menu_json)
            all_menus_data = json.loads(all_menus_json) if all_menus_json else None
            results.append((message_id, {
                'guild_id': guild_id,
                'channel_id': channel_id,
                'menu_data': menu_data,
                'current_day': current_day,
                'all_menus_data': all_menus_data,
                'current_source': current_source or 0,
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
