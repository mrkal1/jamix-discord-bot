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

The bot supports multiple food menu API providers and automatically detects the API format:

### Supported APIs

1. **Jamix API** - Finnish school lunch and restaurant menu system
2. **Mealdoo API** - Modern food service platform (Poweresta/Mealdoo)
3. **Compass Group API** - Compass Group Finland menu system

The bot automatically detects which API format is being used based on the response structure.

### Setting Up Your API

#### For Jamix API:
1. Find your restaurant's customer ID and kitchen ID
2. Use the `/set_menu_id` command to configure: `/set_menu_id <customer_id> <kitchen_id>`
3. The API URL format: `https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/{customer_id}/{kitchen_id}?lang=fi`

#### For Mealdoo/Poweresta API:
1. Find your restaurant's site path (e.g., `org/location`)
2. Use the `/set_menu_id` command: `/set_menu_id mealdoo <site_path>`
3. The API URL format: `https://api.fi.poweresta.com/publicmenu/dates/{site_path}/?menu=Ruokalista&dates=YYYY-MM-DD,YYYY-MM-DD,...`

**Example for Mealdoo:**
```
/set_menu_id mealdoo org/location
```

#### For Compass Group API:
1. Find your restaurant's cost center ID (e.g., `1234`)
2. Use the `/set_menu_id` command: `/set_menu_id compass <cost_center>`
3. The API URL format: `https://www.compass-group.fi/menuapi/week-menus?costCenter={cost_center}&date=YYYY-MM-DD&language=fi`

**Example for Compass Group:**
```
/set_menu_id compass 1234
```

### Custom API Integration

To integrate with your own API:

1. Create a new parser function in `main.py` similar to `parse_jamix_data()` or `parse_mealdoo_data()`
2. Add detection logic in `fetch_menu_data()` to identify your API format
3. Update the data structure to match your menu format

### Expected Data Format (Internal)

After parsing, the bot uses this internal format:

```json
{
  "Monday, November 07": {
    "Lounas": ["Ylikypsää possua (G, L)", "Kermaperunat (G, L)"],
    "Kasvislounas": ["Tomaattinen härkispata (G, L, M)", "Kermaperunat (G, L)"]
  },
  "Tuesday, November 08": {
    "Lounas": ["Item 1", "Item 2"],
    "Kasvislounas": ["Item 1", "Item 2"]
  }
  // ... more days
}
```

**Note:** Diet codes (G=Gluteeniton/Gluten-free, L=Laktoositon/Lactose-free, M=Maidoton/Dairy-free) are automatically included from Mealdoo API.

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
- **Automatic periodic cleanup** runs every 24 hours (removes menus older than 7 days)
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
