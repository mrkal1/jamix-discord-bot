# Multi-Server Setup Guide

This Discord bot now supports multiple servers with different Jamix menu configurations!

## 🏢 **Multi-Server Features**

### Per-Server Configuration
- Each Discord server can have its own Jamix Customer ID and Kitchen ID
- Separate daily posting channels for each server
- Server-specific menu data and API endpoints
- Automatic configuration persistence
- Daily menu posting at 7:00 AM Finnish time (weekdays only)

### Admin Commands (Require Administrator Permission)

#### `/set_menu_id <customer_id> <kitchen_id>`
Set the Jamix API configuration for your server.
```
/set_menu_id customer_id:93077 kitchen_id:61
```

#### `/set_menu_channel #channel`
Set the channel where daily menus will be posted automatically.
```
/set_menu_channel channel:#daily-menu
```

#### `/show_config`
Display the current configuration for your server.
```
/show_config
```

#### `/test_api`
Test your API configuration to ensure it works correctly.
```
/test_api
```

## 🎯 **Setup for New Servers**

1. **Invite the bot** to your Discord server with appropriate permissions
2. **Find your Jamix IDs** from your restaurant's Jamix URL
3. **Configure the bot** using admin commands:
   ```
   /set_menu_id customer_id:YOUR_CUSTOMER_ID kitchen_id:YOUR_KITCHEN_ID
   /set_menu_channel channel:#your-menu-channel
   /test_api
   ```

## 🔍 **Finding Your Jamix IDs**

Your Jamix URL looks like: `https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/CUSTOMER_ID/KITCHEN_ID`

Example: `https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/93077/61`
- Customer ID: `93077`
- Kitchen ID: `61`

## 📅 **Daily Posting**

- Automatic posting at 7:00 AM daily for all configured servers
- Each server gets its own menu based on their configuration
- Graceful handling of API errors per server

## 🧪 **Testing**

Use these commands to verify your setup:
- `!test_api` - Test API connection with current server config
- `!menu` - Browse the weekly menu interactively
- `!today` - Show today's menu
- `!show_config` - View current server settings

## 📁 **Configuration Storage**

Server configurations are stored in `server_config.json` with this structure:
```json
{
  "servers": {
    "GUILD_ID": {
      "customer_id": "93077",
      "kitchen_id": "61",
      "daily_channel_id": 123456789,
      "language": "fi"
    }
  }
}
```

This file is automatically created and managed by the bot.
