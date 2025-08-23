# Copilot Instructions for `jamix-active-discord`

## Project Overview
This is a Discord bot that fetches and displays daily food menus from an API. The bot features interactive navigation between different days using Discord UI components and automated daily posting functionality.

## Key Architecture Components
- **Discord.py Framework**: Uses discord.py with commands extension for bot functionality
- **Interactive UI**: Custom `MenuView` class with Discord UI buttons for day navigation
- **Async HTTP Client**: aiohttp for API requests to fetch menu data
- **Scheduled Tasks**: discord.ext.tasks for automated daily menu posting
- **Environment Configuration**: python-dotenv for managing sensitive credentials

## Key Files and Structure
- `main.py`: Main bot file containing all commands, UI components, and core logic
- `.env`: Environment variables (Discord token, API keys, channel IDs)
- `requirements.txt`: Python dependencies (discord.py, aiohttp, python-dotenv)
- `README.md`: Comprehensive setup and usage documentation

## Critical Developer Workflows

### Bot Setup and Configuration
1. Configure Discord bot in Developer Portal and get token
2. Set up `.env` file with `DISCORD_BOT_TOKEN`, `FOOD_API_KEY`, `DAILY_MENU_CHANNEL_ID`
3. Install dependencies: `pip install -r requirements.txt`
4. Run with: `python main.py`

### API Integration Pattern
- `fetch_menu_data()` function handles all API communication
- Currently uses mock data; replace with actual API endpoint
- Expected data format: `{day: {meal_category: [items]}}`
- Error handling for API failures with fallback behavior

## Project-Specific Conventions
- **Command Prefix**: All bot commands use `!` prefix (`!menu`, `!today`)
- **UI Interaction**: 5-minute timeout on interactive buttons
- **Daily Scheduling**: 24-hour loop for automatic posting
- **Permission Checks**: Admin-only commands use `@commands.has_permissions(administrator=True)`
- **Error Handling**: Graceful fallbacks with user-friendly error messages

## Key Integration Points
- **Discord API**: Bot commands, embeds, UI components, scheduled tasks
- **Food Menu API**: HTTP requests in `fetch_menu_data()` (currently mocked)
- **Environment Variables**: Critical for bot token and channel configuration
- **Database**: Not implemented but recommended for persistent channel settings

## Development Guidelines
- **UI Components**: Extend `MenuView` class for new interactive features
- **Commands**: Add new bot commands using `@bot.command()` decorator
- **API Changes**: Modify `fetch_menu_data()` function for different APIs
- **Scheduling**: Use discord.ext.tasks for any time-based features
- **Error Handling**: Always provide user feedback for failures

## Common Patterns
- Embed creation follows consistent styling with timestamps and footers
- Button interactions use `interaction.response.edit_message()` for updates
- Async/await pattern throughout for Discord and HTTP operations
- Environment variable validation before bot startup
