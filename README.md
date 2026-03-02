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

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
