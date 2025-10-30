# Discord Food Menu Bot

A Discord bot that posts daily food menus from an API with interactive day navigation features and **persistent buttons** that survive bot restarts.

## Features

- 🍽️ **Daily Menu Display**: Automatically posts daily food menus
- 🔄 **Interactive Navigation**: Switch between different days using buttons
- 🔁 **Persistent Buttons**: Buttons continue working even after bot restarts
- ⏰ **Scheduled Posts**: Automatic daily menu posting at 7:00 AM (weekdays only)
- 🎯 **Multiple Commands**: Various commands for different menu views
- 🛡️ **Admin Controls**: Administrator-only commands for bot configuration
- 💾 **Database Storage**: SQLite database for persistent button state

## Commands

- `/menu` - Show the weekly menu with interactive day navigation (ephemeral for users, public for admins)
- `/today` - Show today's menu only (always ephemeral)
- `/set_menu_channel #channel` - Set the channel for daily menu posts (Admin only)
- `/set_menu_id customer_id kitchen_id` - Set the Jamix customer and kitchen IDs (Admin only)
- `/show_config` - Show current server configuration (Admin only)
- `/test_api` - Test the Jamix API connection (Admin only)
- `/cleanup_old_menus [days]` - Remove old persistent menu views from database (Admin only)
- `/test_daily_posting` - Test the daily menu posting (Admin only)

## Setup Instructions

### 1. Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token
4. Invite the bot to your server with the following permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Read Message History

### 2. Environment Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your configuration:
   ```env
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   FOOD_API_KEY=your_food_api_key_here (optional)
   DAILY_MENU_CHANNEL_ID=your_channel_id_here
   ```

### 3. Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the bot:
   ```bash
   python main.py
   ```

## API Integration

The bot is designed to work with any food menu API. To integrate with your API:

1. Replace the `FOOD_API_BASE_URL` in `main.py` with your API endpoint
2. Modify the `fetch_menu_data()` function to match your API's response format
3. Update the data structure to match your menu format

### Expected Data Format

The bot expects menu data in the following format:

```json
{
  "Monday": {
    "Breakfast": ["Item 1", "Item 2", "Item 3"],
    "Lunch": ["Item 1", "Item 2", "Item 3"],
    "Dinner": ["Item 1", "Item 2", "Item 3"]
  },
  "Tuesday": {
    "Breakfast": ["Item 1", "Item 2", "Item 3"],
    "Lunch": ["Item 1", "Item 2", "Item 3"],
    "Dinner": ["Item 1", "Item 2", "Item 3"]
  }
  // ... more days
}
```

## Usage

### Interactive Menu Navigation

When users run `!menu`, they'll get an interactive embed with buttons:
- **◀️ Previous Day**: Navigate to the previous day's menu
- **▶️ Next Day**: Navigate to the next day's menu
- **🔄 Refresh**: Fetch fresh menu data from the API

### Daily Automatic Posts

The bot automatically posts the daily menu at midnight (configurable). Make sure to:
1. Set the `DAILY_MENU_CHANNEL_ID` in your `.env` file
2. Ensure the bot has permissions to post in that channel

### Persistent Buttons

The bot implements **dynamically persistent buttons** that survive bot restarts:
- Daily menu posts maintain interactive buttons even after bot restarts
- Button states are stored in SQLite database (`bot_data.db`)
- Automatic cleanup of old menu views (7+ days)
- Manual cleanup available via `/cleanup_old_menus` command

For detailed implementation information, see [PERSISTENT_BUTTONS.md](PERSISTENT_BUTTONS.md)

## Development

### Project Structure

- `main.py` - Main bot file with all commands and functionality
- `database.py` - Database handler for persistent button storage
- `config.py` - Server configuration management
- `.env` - Environment variables (create from `.env.example`)
- `requirements.txt` - Python dependencies
- `bot_data.db` - SQLite database (auto-created)
- `.gitignore` - Git ignore rules for Python projects

### Customization

- **Menu Categories**: Modify the menu structure in `fetch_menu_data()`
- **Embed Styling**: Customize colors and formatting in `create_menu_embed()`
- **Posting Schedule**: Adjust the `@tasks.loop()` decorator for different intervals
- **Button Labels**: Change button text and emojis in the `MenuView` class
- **Database Retention**: Modify cleanup period in `on_ready` or `/cleanup_old_menus`

## Troubleshooting

### Common Issues

1. **Bot doesn't respond**: Check if the bot token is correct and the bot is online
2. **Permission errors**: Ensure the bot has necessary permissions in the server
3. **Daily posts not working**: Verify `DAILY_MENU_CHANNEL_ID` is set correctly
4. **API errors**: Check your API endpoint and authentication
5. **Buttons not working after restart**: Check database logs and ensure `bot_data.db` exists

### Logs

The bot logs important events to the console. Check for:
- Connection status
- API request failures
- Channel configuration issues
- Database operations (save/load persistent views)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
