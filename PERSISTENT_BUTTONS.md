# Persistent Buttons Implementation

## Overview
This Discord bot now implements **dynamically persistent buttons** that survive bot restarts. This means users can interact with menu navigation buttons even after the bot has been restarted, which is crucial for daily menu posts.

## How It Works

### 1. Database Storage
The bot uses SQLite to store persistent button states in `bot_data.db`:
- **Message ID**: The unique Discord message ID containing the buttons
- **Guild ID**: The server where the message was posted
- **Channel ID**: The channel where the message was posted
- **Menu Data**: The complete menu information (stored as JSON)
- **Current Day**: The currently displayed day index
- **Timestamp**: When the message was created

### 2. Custom Button IDs
All buttons use namespaced custom IDs to avoid conflicts:
- `menu:previous_day` - Navigate to previous day
- `menu:next_day` - Navigate to next day
- `menu:refresh_menu` - Refresh menu data

### 3. View Registration on Startup
When the bot starts (`on_ready` event):
1. Loads all persistent menu views from the database
2. Recreates `MenuView` objects with the stored data
3. Registers them with Discord using `bot.add_view(view, message_id=message_id)`
4. Cleans up old menu views (older than 7 days by default)

### 4. State Updates
When users interact with buttons:
- The bot updates the current day index
- If it's a persistent view, the state is saved to the database
- This ensures the correct day is shown even after a restart

## Implementation Details

### MenuView Class
```python
class MenuView(discord.ui.View):
    def __init__(self, menu_data, current_day=0, guild_id=None, 
                 persistent=True, message_id=None):
        timeout = None if persistent else 900  # No timeout for persistent views
        super().__init__(timeout=timeout)
        # ...
```

**Key Parameters:**
- `persistent=True`: Makes the view persistent (no timeout)
- `message_id`: Links the view to a specific message for database updates

### Database Operations

**Save a persistent menu:**
```python
button_db.save_menu_view(
    message_id=sent_message.id,
    guild_id=guild_id,
    channel_id=channel.id,
    menu_data=menu_data,
    current_day=0
)
```

**Load all persistent menus (on startup):**
```python
persistent_menus = button_db.get_all_persistent_menus()
for message_id, menu_info in persistent_menus:
    view = MenuView(menu_info['menu_data'], ...)
    bot.add_view(view, message_id=message_id)
```

**Cleanup old menus:**
```python
button_db.cleanup_old_menus(days=7)  # Remove menus older than 7 days
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS persistent_menus (
    message_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    menu_data TEXT NOT NULL,  -- JSON string
    current_day INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Usage

### Automatic Persistence
- **Daily Menu Posts**: Automatically saved to database when posted
- **Bot Restart**: All persistent views are automatically re-registered
- **Auto Cleanup**: Old views (7+ days) are cleaned up on bot startup

### Admin Commands

**Manual Cleanup:**
```
/cleanup_old_menus [days]
```
- Removes persistent menu views older than specified days (default: 7)
- Admin only

### User Experience

**Before Implementation:**
- Buttons would stop working after bot restart
- Users would see "This interaction failed" errors

**After Implementation:**
- Buttons continue working even after bot restarts
- Seamless user experience
- State is preserved (e.g., which day was being viewed)

## Best Practices

### 1. Persistent vs Non-Persistent Views
- **Daily Posts**: Use `persistent=True` (no timeout)
- **User Commands**: Use `persistent=False` (15-minute timeout)

### 2. Database Maintenance
- Regular cleanup prevents database bloat
- Automatic cleanup runs on bot startup
- Manual cleanup available via command

### 3. Error Handling
- Database errors are logged but don't crash the bot
- Missing messages/channels are handled gracefully
- Invalid stored data is skipped during registration

## Technical Notes

### Why Custom IDs Matter
Discord uses custom IDs to identify which button was clicked. By using consistent, namespaced custom IDs (`menu:next_day`, etc.), Discord can route button interactions to the correct view even after the bot restarts.

### Timeout Behavior
- `timeout=None`: View never expires (persistent)
- `timeout=900`: View expires after 15 minutes (user commands)
- Expired views are automatically removed by Discord

### Message ID as Database Key
The Discord message ID is used as the primary key because:
- It's guaranteed to be unique
- It directly links the view to the message
- It's required for `bot.add_view()` registration

## Troubleshooting

### Buttons Not Working After Restart
1. Check if the message was saved to database
2. Verify `bot.add_view()` was called in `on_ready`
3. Check for database errors in console logs

### Database Too Large
1. Run `/cleanup_old_menus` with appropriate days
2. Consider reducing retention period in auto-cleanup
3. Check for orphaned messages (deleted messages still in DB)

### "Unknown Interaction" Errors
- Usually means the view wasn't properly registered
- Check that custom IDs match between registration and callbacks
- Ensure `message_id` is correctly passed to `bot.add_view()`

## Files Modified/Created

### New Files
- `database.py`: Database handler for persistent button storage

### Modified Files
- `main.py`: 
  - Import `ButtonDatabase`
  - Updated `MenuView` class with persistence support
  - Updated `on_ready` to register persistent views
  - Updated `daily_menu_post` to save views to database
  - Added `/cleanup_old_menus` command

## References
- [Stack Overflow: Dynamic Persistent Buttons](https://stackoverflow.com/questions/76350295/how-do-i-make-dynamically-persistant-buttons)
- [Discord.py Views Documentation](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.ui.View)
- [Discord.py Persistent Views Example](https://github.com/Rapptz/discord.py/blob/master/examples/views/persistent.py)
