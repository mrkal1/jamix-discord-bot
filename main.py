import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from datetime import datetime, time, date, timedelta
import zoneinfo
import os
from dotenv import load_dotenv
from config import ServerConfig
from database import ButtonDatabase

# Load environment variables
load_dotenv()

# Initialize server configuration
server_config = ServerConfig()

# Initialize database for persistent buttons
button_db = ButtonDatabase()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API configuration
FOOD_API_KEY = os.getenv('FOOD_API_KEY')  # Add your API key to .env file

class MenuView(discord.ui.View):
    """Interactive view for switching between menu days (and optionally between sources)"""
    
    def __init__(self, menu_data, current_day=0, guild_id=None, persistent=True, message_id=None,
                 all_menus_data=None, current_source=0):
        # Use no timeout for daily messages (persistent), 15 minutes for user commands
        timeout = None if persistent else 900  # 15 minutes for user interactions
        super().__init__(timeout=timeout)
        self.guild_id = guild_id
        self.persistent = persistent
        self.message_id = message_id  # Store message_id for database updates

        # Multi-source support
        self.all_menus_data = all_menus_data  # {source_name: {day: {cat: [items]}}} | None
        self.current_source = current_source
        self.sources: list = list(all_menus_data.keys()) if all_menus_data else []

        # Derive active menu_data from current source (or use the passed-in single-source data)
        if all_menus_data and self.sources:
            src_name = self.sources[current_source % len(self.sources)]
            self.menu_data = all_menus_data[src_name]
        else:
            self.menu_data = menu_data

        self.current_day = current_day
        self.days = list(self.menu_data.keys()) if self.menu_data else []

        # Dynamically add a source-selector dropdown when there are multiple sources
        if all_menus_data and len(all_menus_data) > 1:
            options = [
                discord.SelectOption(
                    label=name[:100],
                    value=str(i),
                    default=(i == current_source)
                )
                for i, name in enumerate(self.sources[:25])  # Discord allows max 25 options
            ]
            select = discord.ui.Select(
                placeholder="🍴 Valitse ravintola…",
                options=options,
                custom_id="menu:select_source",
                min_values=1,
                max_values=1,
            )
            select.callback = self._select_source_callback
            self.add_item(select)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _current_source_name(self) -> str:
        if self.sources and self.current_source < len(self.sources):
            return self.sources[self.current_source]
        return ""

    def _save_to_db(self, message_id: int, channel_id: int):
        """Persist the current view state to the database."""
        button_db.save_menu_view(
            message_id,
            self.guild_id,
            channel_id,
            self.menu_data,
            self.current_day,
            self.all_menus_data,
            self.current_source,
        )

    async def _select_source_callback(self, interaction: discord.Interaction):
        """Called when the user picks a different source from the dropdown."""
        source_idx = int(interaction.data["values"][0]) % max(len(self.sources), 1)
        self.current_source = source_idx
        src_name = self.sources[source_idx]
        self.menu_data = self.all_menus_data[src_name]
        self.days = list(self.menu_data.keys())
        self.current_day = 0

        # Update the Select to reflect the new default
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id == "menu:select_source":
                for opt in item.options:
                    opt.default = (opt.value == str(source_idx))
                break

        embed = self.create_menu_embed()
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral

        if is_ephemeral:
            if self.persistent and self.message_id and interaction.channel_id:
                self._save_to_db(self.message_id, interaction.channel_id)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    # ------------------------------------------------------------------ #
    #  Buttons                                                             #
    # ------------------------------------------------------------------ #

    @discord.ui.button(label='◀️ Edellinen Päivä', style=discord.ButtonStyle.secondary, custom_id="menu:previous_day")
    async def previous_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_day = (self.current_day - 1) % len(self.days)
        embed = self.create_menu_embed()
        
        # Update database if this is a persistent view
        if self.persistent and self.message_id and interaction.guild and interaction.channel_id:
            self._save_to_db(self.message_id, interaction.channel_id)
        
        # Check if this is an ephemeral message by looking at message flags
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral
        
        if is_ephemeral:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.button(label='▶️ Seuraava Päivä', style=discord.ButtonStyle.secondary, custom_id="menu:next_day")
    async def next_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_day = (self.current_day + 1) % len(self.days)
        embed = self.create_menu_embed()
        
        # Update database if this is a persistent view
        if self.persistent and self.message_id and interaction.guild and interaction.channel_id:
            self._save_to_db(self.message_id, interaction.channel_id)
        
        # Check if this is an ephemeral message by looking at message flags
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral
        
        if is_ephemeral:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label='🔄 Päivitä', style=discord.ButtonStyle.primary, custom_id="menu:refresh_menu")
    async def refresh_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Fetch fresh menu data using the guild_id
        guild_id = self.guild_id or (interaction.guild.id if interaction.guild else None)
        
        # Check if this is an ephemeral message by looking at message flags
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral
        
        if is_ephemeral:
            await interaction.response.defer()
            new_all_menus = await fetch_all_menus_data(guild_id)
            if new_all_menus:
                # Preserve source selection if available
                new_source = 0
                if self.sources:
                    src_name = self._current_source_name()
                    new_sources = list(new_all_menus.keys())
                    new_source = new_sources.index(src_name) if src_name in new_sources else 0
                new_view = MenuView(
                    menu_data=None, current_day=0, guild_id=guild_id,
                    persistent=self.persistent, message_id=self.message_id,
                    all_menus_data=new_all_menus, current_source=new_source,
                )
                embed = new_view.create_menu_embed()
                await interaction.edit_original_response(embed=embed, view=new_view)
            else:
                await interaction.edit_original_response(content="❌ Failed to refresh menu data.")
        else:
            await interaction.response.defer(ephemeral=True)
            new_all_menus = await fetch_all_menus_data(guild_id)
            if new_all_menus:
                user_view = MenuView(
                    menu_data=None, current_day=0, guild_id=guild_id, persistent=False,
                    all_menus_data=new_all_menus, current_source=0,
                )
                embed = user_view.create_menu_embed()
                await interaction.followup.send(embed=embed, view=user_view, ephemeral=True)
            else:
                await interaction.followup.send("Failed to refresh menu data.", ephemeral=True)
    
    # ------------------------------------------------------------------ #
    #  Embed builder                                                       #
    # ------------------------------------------------------------------ #

    def create_menu_embed(self):
        """Create an embed for the current day's menu"""
        if not self.days:
            return discord.Embed(title="No Menu Available", color=0xff0000)
        
        current_day_name = self.days[self.current_day]
        day_menu = self.menu_data[current_day_name]

        # Include source name in title when there are multiple sources
        source_name = self._current_source_name()
        if source_name and len(self.sources) > 1:
            title = f"🍽️ {source_name} — {current_day_name}"
        else:
            title = f"🍽️ Ruokalista — {current_day_name}"
        
        embed = discord.Embed(
            title=title,
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        # Add menu items by category
        for category, items in day_menu.items():
            if items:
                items_text = "\n".join([f"• {item}" for item in items])
                embed.add_field(name=f"**{category}**", value=items_text, inline=False)
        
        footer_text = f"Day {self.current_day + 1} of {len(self.days)} | Click buttons to navigate"
        if not self.persistent:
            footer_text += " (personal view)"
        embed.set_footer(text=footer_text)
        
        return embed
    
    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all buttons when timeout occurs
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

def parse_mealdoo_data(mealdoo_data):
    """Parse Mealdoo API data into a format suitable for the Discord bot"""
    parsed_data = {}
    
    if not mealdoo_data or not isinstance(mealdoo_data, list):
        return parsed_data
    
    # Get today's date for filtering
    today = datetime.now().date()
    
    # Process each day in the data
    for day_data in mealdoo_data:
        if not day_data.get('allSuccessful') or not day_data.get('data'):
            continue
        
        date_str = day_data.get('date', '')
        if not date_str:
            continue
        
        try:
            # Parse date string (format: YYYY-MM-DD)
            day_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # Skip dates that are in the past (before today)
            if day_obj < today:
                print(f"Skipping past date: {day_obj}")
                continue
            
            day_name = day_obj.strftime("%A, %B %d")
            
            # Initialize the day's menu
            parsed_data[day_name] = {}
            
            # Process meal options
            meal_options = day_data.get('data', {}).get('mealOptions', [])
            for meal_option in meal_options:
                # Get meal category name (e.g., "Lounas", "Kasvislounas")
                meal_names = meal_option.get('names', [])
                meal_name = 'Unknown'
                for name_obj in meal_names:
                    if name_obj.get('language') == 'fi':
                        meal_name = name_obj.get('name', 'Unknown')
                        break
                
                # Process rows (menu items)
                items = []
                rows = meal_option.get('rows', [])
                for row in rows:
                    # Get item name
                    names = row.get('names', [])
                    for name_obj in names:
                        if name_obj.get('language') == 'fi':
                            item_name = name_obj.get('name', '').strip()
                            if item_name and item_name not in ['ESPANJA', '***']:  # Skip category headers
                                # Get diet info if available
                                diets_info = row.get('diets', [])
                                diet_shorts = []
                                for diet_obj in diets_info:
                                    if diet_obj.get('language') == 'fi':
                                        diet_shorts = diet_obj.get('dietShorts', [])
                                        break
                                
                                # Format item with diet info
                                if diet_shorts:
                                    item_display = f"{item_name} ({', '.join(diet_shorts)})"
                                else:
                                    item_display = item_name
                                
                                items.append(item_display)
                            break
                
                if items:  # Only add if there are actual items
                    parsed_data[day_name][meal_name] = items
                    
        except (ValueError, IndexError) as e:
            print(f"Error parsing Mealdoo date {date_str}: {e}")
            continue
    
    return parsed_data

def parse_jamix_data(jamix_data):
    """Parse Jamix API data into a format suitable for the Discord bot"""
    parsed_data = {}
    
    if not jamix_data or not isinstance(jamix_data, list):
        return parsed_data
    
    # Get the first kitchen (assuming we want the first one)
    kitchen = jamix_data[0] if jamix_data else None
    if not kitchen:
        return parsed_data
    
    # Find the main menu type (usually the first one or "Ravintola Cube")
    main_menu_type = None
    for menu_type in kitchen.get('menuTypes', []):
        if 'Ravintola Cube' in menu_type.get('menuTypeName', ''):
            main_menu_type = menu_type
            break
    
    if not main_menu_type:
        main_menu_type = kitchen.get('menuTypes', [{}])[0]
    
    # Get the first menu from the menu type
    menu = main_menu_type.get('menus', [{}])[0] if main_menu_type else {}
    
    # Get today's date for filtering
    today = datetime.now().date()
    
    # Process each day
    for day_data in menu.get('days', []):
        date_int = day_data.get('date', 0)
        weekday = day_data.get('weekday', 0)
        
        # Convert date integer to readable format
        if date_int:
            try:
                date_str = str(date_int)
                year = int(date_str[:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                
                # Create a datetime object to get the day name
                day_obj = date(year, month, day)
                
                # Skip dates that are in the past (before today)
                if day_obj < today:
                    print(f"Skipping past date: {day_obj}")
                    continue
                
                day_name = day_obj.strftime("%A, %B %d")
                
                # Initialize the day's menu
                parsed_data[day_name] = {}
                
                # Process meal options for this day
                for meal_option in day_data.get('mealoptions', []):
                    meal_name = meal_option.get('name', 'Unknown')
                    
                    # Create a list of menu items for this meal
                    items = []
                    for menu_item in meal_option.get('menuItems', []):
                        item_name = menu_item.get('name', '')
                        if item_name and item_name != '***':  # Skip placeholder items
                            # Clean up the item name
                            item_name = item_name.replace('Lämmin kasvislisäke', 'Seasonal Vegetables')
                            item_name = item_name.replace('Runsas salaattipöytä', 'Salad Bar')
                            items.append(item_name)
                    
                    if items:  # Only add if there are actual items
                        parsed_data[day_name][meal_name] = items
                        
            except (ValueError, IndexError) as e:
                print(f"Error parsing date {date_int}: {e}")
                continue
    
    return parsed_data

def parse_compass_data(compass_data):
    """Parse Compass Group API data into a format suitable for the Discord bot"""
    parsed_data = {}
    
    if not compass_data or not isinstance(compass_data, dict):
        return parsed_data
    
    # Get today's date for filtering
    today = datetime.now().date()
    
    # Process each day's menu
    menus = compass_data.get('menus', [])
    for day_data in menus:
        date_str = day_data.get('date', '')
        if not date_str:
            continue
        
        try:
            # Parse date string (format: YYYY-MM-DDTHH:MM:SS)
            day_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            
            # Skip dates that are in the past (before today)
            if day_obj < today:
                continue
            
            # Format day name
            day_name = day_obj.strftime("%A, %B %d")
            
            # Initialize the day's menu
            parsed_data[day_name] = {}
            
            # Process menu packages (categories like "KASVISLOUNAS", "KEITTOLOUNAS", etc.)
            menu_packages = day_data.get('menuPackages', [])
            for package in sorted(menu_packages, key=lambda p: p.get('sortOrder', 0)):
                category_name = package.get('name', 'Menu')
                # Price is on the package, not on individual meals.
                # Include it in the section heading so identically-named packages
                # at different price points become separate embed fields.
                price_str = package.get('price', '').strip()
                display_key = f"{category_name} — {price_str}" if price_str else category_name
                meals = package.get('meals', [])

                if meals:
                    if display_key not in parsed_data[day_name]:
                        parsed_data[day_name][display_key] = []

                    for meal in meals:
                        meal_name = meal.get('name', '').strip()
                        if not meal_name:
                            continue

                        diets = meal.get('diets', [])
                        diet_codes = [d for d in diets if d != '*'] if diets else []
                        if diet_codes:
                            meal_name = f"{meal_name} ({', '.join(diet_codes)})"

                        parsed_data[day_name][display_key].append(meal_name)
        
        except (ValueError, IndexError) as e:
            print(f"Error parsing Compass date {date_str}: {e}")
            continue
    
    return parsed_data

async def fetch_menu_data(guild_id = None, retry_next_week = True, source_config = None):
    """Fetch menu data from the API (Jamix, Mealdoo, or Compass Group) for a specific server.
    
    Args:
        guild_id: The guild ID to fetch menu for
        retry_next_week: If True, will try next week's menu if current week has no valid dates
        source_config: Optional explicit source config dict (overrides guild_id lookup)
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = {}
            if FOOD_API_KEY:
                headers['Authorization'] = f'Bearer {FOOD_API_KEY}'
            
            # Determine api_type and url
            if source_config:
                api_type = source_config.get("api_type", "jamix")
                api_url = server_config.get_menu_url_for_source(source_config)
            elif guild_id:
                config = server_config.get_server_config(guild_id)
                api_type = config.get("api_type", "jamix")
                api_url = server_config.get_menu_url(guild_id)
            else:
                api_type = "jamix"
                api_url = "https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/12345/12?lang=fi"
            
            print(f"Fetching menu from: {api_url}")
            
            # Fetch data from the API
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    api_data = await response.json()
                    
                    # Detect API type and use appropriate parser
                    parsed_data = None
                    
                    # Check if it's Compass Group format (dict with 'weekNumber' and 'menus')
                    if isinstance(api_data, dict) and 'weekNumber' in api_data and 'menus' in api_data:
                        print(f"Detected Compass Group API format (Guild: {guild_id})")
                        parsed_data = parse_compass_data(api_data)
                    # Check if it's Mealdoo format (has 'allSuccessful' and 'data' keys)
                    elif isinstance(api_data, list) and len(api_data) > 0:
                        first_item = api_data[0]
                        if isinstance(first_item, dict) and 'allSuccessful' in first_item and 'data' in first_item:
                            print(f"Detected Mealdoo API format - {len(api_data)} day(s) (Guild: {guild_id})")
                            parsed_data = parse_mealdoo_data(api_data)
                        # Check if it's Jamix format (has 'menuTypes' or 'days')
                        elif 'menuTypes' in first_item or 'days' in first_item:
                            print(f"Detected Jamix API format (Guild: {guild_id})")
                            parsed_data = parse_jamix_data(api_data)
                        else:
                            print(f"Unknown API format (Guild: {guild_id})")
                            print(f"First item keys: {first_item.keys() if isinstance(first_item, dict) else 'Not a dict'}")
                    
                    # Check if parsed_data is empty (all dates were in the past)
                    if parsed_data and len(parsed_data) == 0 and retry_next_week and (guild_id or source_config):
                        # Retry for Compass (weekly menus) and Mealdoo APIs
                        if api_type == "compass":
                            print(f"Current week menu has no valid dates, trying next week... (Guild: {guild_id})")
                            next_week = datetime.now() + timedelta(days=7)
                            if source_config:
                                next_week_url = server_config.get_menu_url_for_source(source_config, next_week)
                            else:
                                next_week_url = server_config.get_menu_url(guild_id, next_week)
                            
                            print(f"Fetching next week's menu from: {next_week_url}")
                            async with session.get(next_week_url, headers=headers) as next_response:
                                if next_response.status == 200:
                                    next_api_data = await next_response.json()
                                    if isinstance(next_api_data, dict) and 'weekNumber' in next_api_data and 'menus' in next_api_data:
                                        parsed_data = parse_compass_data(next_api_data)
                                        if parsed_data:
                                            print(f"Successfully fetched next week's menu for {len(parsed_data)} days (Guild: {guild_id})")
                        elif api_type == "mealdoo":
                            print(f"Current dates have no valid menu, trying next week... (Guild: {guild_id})")
                            next_week = datetime.now() + timedelta(days=7)
                            if source_config:
                                next_week_url = server_config.get_menu_url_for_source(source_config, next_week)
                            else:
                                next_week_url = server_config.get_menu_url(guild_id, next_week)
                            
                            print(f"Fetching next week's menu from: {next_week_url}")
                            async with session.get(next_week_url, headers=headers) as next_response:
                                if next_response.status == 200:
                                    next_api_data = await next_response.json()
                                    if isinstance(next_api_data, list) and len(next_api_data) > 0:
                                        first_item = next_api_data[0]
                                        if isinstance(first_item, dict) and 'allSuccessful' in first_item and 'data' in first_item:
                                            parsed_data = parse_mealdoo_data(next_api_data)
                                            if parsed_data:
                                                print(f"Successfully fetched next week's menu for {len(parsed_data)} days (Guild: {guild_id})")
                    
                    if parsed_data and len(parsed_data) > 0:
                        print(f"Successfully fetched menu data for {len(parsed_data)} days (Guild: {guild_id})")
                        return parsed_data
                    else:
                        print(f"No menu data found in API response (Guild: {guild_id})")
                        return None
                else:
                    print(f"API request failed with status: {response.status} (Guild: {guild_id})")
                    response_text = await response.text()
                    print(f"Response: {response_text[:500]}...")  # Print first 500 chars
                    return None
            
    except Exception as e:
        print(f"Error fetching menu data for Guild {guild_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

async def fetch_all_menus_data(guild_id) -> dict | None:
    """Fetch menu data for every configured source of a guild.
    
    Returns a dict of {source_name: menu_data}, or None if all sources failed.
    """
    sources = server_config.get_menu_sources(guild_id)
    all_menus: dict = {}

    for source in sources:
        name = source.get("name", "Ruokalista")
        data = await fetch_menu_data(guild_id=guild_id, source_config=source)
        if data:
            all_menus[name] = data
        else:
            print(f"Source '{name}' returned no data for guild {guild_id}")

    return all_menus if all_menus else None


async def handle_menu_navigation(interaction: discord.Interaction, direction: int):
    """Handle navigation button clicks by loading state from database"""
    message_id = interaction.message.id if interaction.message else None
    
    if not message_id:
        await interaction.response.send_message("❌ Could not identify message", ephemeral=True)
        return
    
    # Load menu data from database
    menu_info = button_db.get_menu_view(message_id)
    
    if not menu_info:
        await interaction.response.send_message("❌ Menu data not found. This might be an expired view.", ephemeral=True)
        return
    
    is_ephemeral = interaction.message and interaction.message.flags.ephemeral

    # Resolve the active menu (multi-source or single-source)
    all_menus_data = menu_info.get('all_menus_data')
    current_source = menu_info.get('current_source', 0)
    if all_menus_data:
        sources = list(all_menus_data.keys())
        source_name = sources[current_source % len(sources)]
        active_menu = all_menus_data[source_name]
    else:
        active_menu = menu_info['menu_data']
        source_name = None

    days = list(active_menu.keys())
    new_day = (menu_info['current_day'] + direction) % len(days)
    current_day_name = days[new_day]
    day_menu = active_menu[current_day_name]
    
    # Build title
    if source_name and all_menus_data and len(all_menus_data) > 1:
        title = f"🍽️ {source_name} — {current_day_name}"
    else:
        title = f"🍽️ Ruokalista — {current_day_name}"

    embed = discord.Embed(title=title, color=0x00ff00, timestamp=datetime.now())
    for category, items in day_menu.items():
        if items:
            items_text = "\n".join([f"• {item}" for item in items])
            embed.add_field(name=f"**{category}**", value=items_text, inline=False)
    
    if is_ephemeral:
        embed.set_footer(text=f"Day {new_day + 1} of {len(days)} | Click buttons to navigate (personal view)")
        button_db.save_menu_view(
            message_id, menu_info['guild_id'], menu_info['channel_id'],
            active_menu, new_day, all_menus_data, current_source,
        )
        await interaction.response.edit_message(embed=embed)
    else:
        embed.set_footer(text=f"Day {new_day + 1} of {len(days)} | Click buttons to navigate (personal view)")
        user_view = MenuView(active_menu, new_day, menu_info['guild_id'], persistent=False,
                             all_menus_data=all_menus_data, current_source=current_source)
        await interaction.response.send_message(embed=embed, view=user_view, ephemeral=True)


async def handle_menu_source_select(interaction: discord.Interaction, source_value: str):
    """Handle source-selector dropdown via the persistent view handler."""
    message_id = interaction.message.id if interaction.message else None

    if not message_id:
        await interaction.response.send_message("❌ Could not identify message", ephemeral=True)
        return

    menu_info = button_db.get_menu_view(message_id)

    if not menu_info or not menu_info.get('all_menus_data'):
        await interaction.response.send_message("❌ Multi-source menu data not found.", ephemeral=True)
        return

    all_menus_data = menu_info['all_menus_data']
    sources = list(all_menus_data.keys())

    try:
        source_idx = int(source_value) % len(sources)
    except (ValueError, ZeroDivisionError):
        source_idx = 0

    source_name = sources[source_idx]
    active_menu = all_menus_data[source_name]
    days = list(active_menu.keys())
    current_day_name = days[0] if days else ""

    if len(all_menus_data) > 1:
        title = f"🍽️ {source_name} — {current_day_name}"
    else:
        title = f"🍽️ Ruokalista — {current_day_name}"

    embed = discord.Embed(title=title, color=0x00ff00, timestamp=datetime.now())
    if current_day_name:
        for category, items in active_menu[current_day_name].items():
            if items:
                items_text = "\n".join([f"• {item}" for item in items])
                embed.add_field(name=f"**{category}**", value=items_text, inline=False)

    is_ephemeral = interaction.message and interaction.message.flags.ephemeral
    user_view = MenuView(active_menu, 0, menu_info['guild_id'], persistent=False,
                         all_menus_data=all_menus_data, current_source=source_idx)

    if is_ephemeral:
        embed.set_footer(text=f"Day 1 of {len(days)} | {source_name} (personal view)")
        button_db.save_menu_view(
            message_id, menu_info['guild_id'], menu_info['channel_id'],
            active_menu, 0, all_menus_data, source_idx,
        )
        await interaction.response.edit_message(embed=embed, view=user_view)
    else:
        embed.set_footer(text=f"Day 1 of {len(days)} | {source_name} (personal view)")
        await interaction.response.send_message(embed=embed, view=user_view, ephemeral=True)

async def handle_menu_refresh(interaction: discord.Interaction):
    """Handle refresh button by fetching fresh menu data"""
    message_id = interaction.message.id if interaction.message else None
    
    if not message_id:
        await interaction.response.send_message("❌ Could not identify message", ephemeral=True)
        return
    
    menu_info = button_db.get_menu_view(message_id)
    
    if not menu_info:
        await interaction.response.send_message("❌ Menu data not found", ephemeral=True)
        return
    
    is_ephemeral = interaction.message and interaction.message.flags.ephemeral
    
    await interaction.response.defer(ephemeral=True)
    
    guild_id = menu_info['guild_id']
    new_all_menus = await fetch_all_menus_data(guild_id)
    
    if new_all_menus:
        # Preserve current source selection if possible
        old_all = menu_info.get('all_menus_data')
        current_source = menu_info.get('current_source', 0)
        if old_all:
            old_sources = list(old_all.keys())
            old_name = old_sources[current_source % len(old_sources)] if old_sources else None
            new_sources = list(new_all_menus.keys())
            new_source_idx = new_sources.index(old_name) if old_name and old_name in new_sources else 0
        else:
            new_source_idx = 0

        new_sources = list(new_all_menus.keys())
        active_source_name = new_sources[new_source_idx]
        active_menu = new_all_menus[active_source_name]
        days = list(active_menu.keys())
        current_day_name = days[0] if days else ""

        if len(new_all_menus) > 1:
            title = f"🍽️ {active_source_name} — {current_day_name}"
        else:
            title = f"🍽️ Ruokalista — {current_day_name}"

        embed = discord.Embed(title=title, color=0x00ff00, timestamp=datetime.now())
        if current_day_name:
            for category, items in active_menu[current_day_name].items():
                if items:
                    items_text = "\n".join([f"• {item}" for item in items])
                    embed.add_field(name=f"**{category}**", value=items_text, inline=False)

        if is_ephemeral:
            embed.set_footer(text=f"Day 1 of {len(days)} | Click buttons to navigate | Refreshed (personal view)")
            button_db.save_menu_view(
                message_id, guild_id, menu_info['channel_id'],
                active_menu, 0, new_all_menus, new_source_idx,
            )
            await interaction.edit_original_response(embed=embed)
        else:
            embed.set_footer(text=f"Day 1 of {len(days)} | Click buttons to navigate | Refreshed (personal view)")
            user_view = MenuView(active_menu, 0, guild_id, persistent=False,
                                 all_menus_data=new_all_menus, current_source=new_source_idx)
            await interaction.followup.send(embed=embed, view=user_view, ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to refresh menu data.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Register persistent view handler (without message_id to handle ALL messages)
    # This creates a persistent listener that loads menu data on-demand from the database
    print("Registering persistent view handler...")
    try:
        # Create a special persistent view handler that will be called for any button interaction
        class PersistentMenuView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(label='◀️ Edellinen Päivä', style=discord.ButtonStyle.secondary, custom_id="menu:previous_day")
            async def previous_day(self, interaction: discord.Interaction, button: discord.ui.Button):
                await handle_menu_navigation(interaction, -1)
            
            @discord.ui.button(label='▶️ Seuraava Päivä', style=discord.ButtonStyle.secondary, custom_id="menu:next_day")
            async def next_day(self, interaction: discord.Interaction, button: discord.ui.Button):
                await handle_menu_navigation(interaction, 1)
            
            @discord.ui.button(label='🔄 Päivitä', style=discord.ButtonStyle.primary, custom_id="menu:refresh_menu")
            async def refresh_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
                await handle_menu_refresh(interaction)

            @discord.ui.select(
                custom_id="menu:select_source",
                placeholder="🍴 Valitse ravintola…",
                min_values=1,
                max_values=1,
                options=[discord.SelectOption(label="placeholder", value="0")],
            )
            async def select_source(self, interaction: discord.Interaction, select: discord.ui.Select):
                await handle_menu_source_select(interaction, select.values[0])
        
        bot.add_view(PersistentMenuView())
        print("Registered persistent view handler successfully")
    except Exception as e:
        print(f"Error registering persistent view handler: {e}")
    
    # Start the daily menu posting task
    daily_menu_post.start()
    
    # Start the periodic cleanup task
    cleanup_old_menus_task.start()
    print("Started periodic cleanup task (runs every 24 hours)")

@bot.tree.command(name='menu', description='Show the weekly menu (ephemeral for users, public for admins)')
async def show_menu(interaction: discord.Interaction):
    """Show the weekly menu with interactive navigation"""
    guild_id = interaction.guild.id if interaction.guild else None
    
    is_admin = (isinstance(interaction.user, discord.Member) and 
                interaction.user.guild_permissions.administrator)
    
    await interaction.response.defer(ephemeral=not is_admin)
    
    all_menus = await fetch_all_menus_data(guild_id)
    
    if not all_menus:
        await interaction.followup.send("❌ Ei voitu noutaa ruokalistaa tällä hetkellä. Yritä myöhemmin uudelleen.")
        return
    
    view = MenuView(menu_data=None, guild_id=guild_id, persistent=False,
                    all_menus_data=all_menus, current_source=0)
    embed = view.create_menu_embed()
    
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name='today', description='Show today\'s menu')
async def todays_menu(interaction: discord.Interaction):
    """Show today's menu (or next available menu)"""
    guild_id = interaction.guild.id if interaction.guild else None
    
    await interaction.response.defer(ephemeral=True)
    
    all_menus = await fetch_all_menus_data(guild_id)
    
    if not all_menus:
        await interaction.followup.send("❌ Ei voitu noutaa ruokalistaa tällä hetkellä. Yritä myöhemmin uudelleen.")
        return
    
    today = datetime.now()
    today_str = today.strftime("%A, %B %d")

    # Build one embed per source, showing their first available day
    embeds = []
    for source_name, menu_data in all_menus.items():
        days = list(menu_data.keys())
        if not days:
            continue
        found_day_name = days[0]
        found_menu = menu_data[found_day_name]
        is_today = (found_day_name == today_str)

        if len(all_menus) > 1:
            title = f"🍽️ {source_name} — {found_day_name}"
        else:
            title = f"🍽️ Ruokalista — {found_day_name}"

        embed = discord.Embed(title=title, color=0x00ff00, timestamp=datetime.now())
        if not is_today:
            embed.description = "*Tämän päivän ruokalistaa ei saatavilla. Näytetään seuraava saatavilla oleva ruokalista.*"
        for category, items in found_menu.items():
            if items:
                items_text = "\n".join([f"• {item}" for item in items])
                embed.add_field(name=f"**{category}**", value=items_text, inline=False)
        if not any(found_menu.values()):
            embed.add_field(name="No Menu Available", value="No menu items found for this day.", inline=False)
        embeds.append(embed)

    if embeds:
        await interaction.followup.send(embeds=embeds[:10])  # Discord allows max 10 embeds per message
    else:
        await interaction.followup.send("❌ No menu available for today or upcoming days.")

@tasks.loop(time=time(hour=7, minute=00, tzinfo=zoneinfo.ZoneInfo("Europe/Helsinki")))  # Run daily at 7:00 AM Finnish time (handles DST automatically)
async def daily_menu_post():
    """Post daily menu automatically at 7:00 AM local time for all configured servers (weekdays only)"""
    print("Daily menu posting task triggered...")
    
    # Check if today is a weekday (Monday=0, Sunday=6)
    today = datetime.now(tz=zoneinfo.ZoneInfo("Europe/Helsinki"))
    if today.weekday() >= 5:  # Saturday (5) or Sunday (6)
        print(f"Skipping daily menu post - today is {today.strftime('%A')} (weekend)")
        return
    
    print(f"Starting daily menu posting for {today.strftime('%A')}...")
    
    # Get all configured servers
    servers_config = server_config.list_servers()
    
    for guild_id_str, config in servers_config.items():
        guild_id = int(guild_id_str)
        daily_channel_id = config.get("daily_channel_id")
        
        if not daily_channel_id:
            print(f"No daily channel configured for guild {guild_id}, skipping...")
            continue
        
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"Guild {guild_id} not found, skipping...")
            continue
        
        channel = bot.get_channel(daily_channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            print(f"Channel {daily_channel_id} not found for guild {guild_id}, skipping...")
            continue
        
        try:
            all_menus = await fetch_all_menus_data(guild_id)
            if not all_menus:
                """ await channel.send("❌ Ei voitu noutaa tämän päivän ruokalistaa.") """
                continue
            
            # Use the first source as primary for the shared daily message
            first_source_name = list(all_menus.keys())[0]
            menu_data = all_menus[first_source_name]

            # Since menu_data already has past dates filtered out, just get the first available day
            days = list(menu_data.keys())
            if not days:
                print(f"No menu days available for guild {guild_id}")
                continue
            
            # Get the first available day (which is the earliest future date)
            found_day_name = days[0]
            found_menu = menu_data[found_day_name]
            
            # Check if this is actually today
            local_tz = zoneinfo.ZoneInfo("Europe/Helsinki")
            today = datetime.now(local_tz)
            today_str = today.strftime("%A, %B %d")
            is_today = (found_day_name == today_str)
            
            if found_menu and found_day_name:
                # Find the index of the menu for the view
                day_names = list(menu_data.keys())
                try:
                    current_day_index = day_names.index(found_day_name)
                except ValueError:
                    current_day_index = 0
                
                # Use persistent=True for daily messages so buttons don't expire
                view = MenuView(
                    menu_data=None, current_day=current_day_index, guild_id=guild_id, persistent=True,
                    all_menus_data=all_menus, current_source=0,
                )
                embed = view.create_menu_embed()
                
                if len(all_menus) > 1:
                    message = f"**Ruokalista {found_day_name}:** (käytä valikkoa vaihtaaksesi ravintolaa)"
                else:
                    message = f"**Ruokalista {found_day_name}:**"
                if not is_today:
                    message = f"**Tämän päivän ruokalista ei saatavilla, näytetään {found_day_name}:**"

                sent_message = await channel.send(message, embed=embed, view=view)
                
                # Save to database for persistence across restarts
                view.message_id = sent_message.id
                button_db.save_menu_view(
                    sent_message.id,
                    guild_id,
                    channel.id,
                    menu_data,
                    current_day_index,
                    all_menus,
                    0,
                )
                
                print(f"Posted daily menu for guild {guild_id} ({guild.name})")
            else:
                await channel.send(f"❌ Ruokalistaa ei ole saatavilla.")
                print(f"No menu available for guild {guild_id} ({guild.name})")
                
        except Exception as e:
            print(f"Error posting daily menu for guild {guild_id}: {e}")
            try:
                await channel.send("❌ Virhe julkaistaessa päivittäistä ruokalistaa. Tarkista asetukset.")
            except:
                pass  # Channel might not be accessible

@bot.tree.command(name='test_daily_posting', description='Show today\'s menu')
async def test_daily_posting(interaction: discord.Interaction):
    """Test the daily menu posting"""
    # Check if user has administrator permissions
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    await interaction.response.send_message("Testing daily menu posting...", ephemeral=True)
    await daily_menu_post()

@daily_menu_post.before_loop
async def before_daily_menu_post():
    """Wait until bot is ready before starting the daily task"""
    await bot.wait_until_ready()

@tasks.loop(hours=24)  # Run every 24 hours
async def cleanup_old_menus_task():
    """Periodically clean up old persistent menu views from the database"""
    print("Running periodic database cleanup...")
    try:
        deleted_count = button_db.cleanup_old_menus(days=7)
        if deleted_count > 0:
            print(f"Periodic cleanup: Removed {deleted_count} old menu view(s)")
        else:
            print("Periodic cleanup: No old menus to remove")
    except Exception as e:
        print(f"Error during periodic cleanup: {e}")

@cleanup_old_menus_task.before_loop
async def before_cleanup_task():
    """Wait until bot is ready before starting the cleanup task"""
    await bot.wait_until_ready()

# Admin Commands
@bot.tree.command(name='set_menu_channel', description='Set the channel for daily menu posts')
@app_commands.describe(channel="The channel where daily menus will be posted")
async def set_menu_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the channel for daily menu posts (Admin only)"""
    # Check if user has administrator permissions
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Save to configuration
    server_config.set_daily_channel(interaction.guild.id, channel.id)

    await interaction.followup.send(f"✅ Päivittäinen ruokalista kanava asetettu {channel.mention} tällä palvelimella.")

@bot.tree.command(name='set_menu_id', description='Configure API: Jamix (2 IDs), Mealdoo, or Compass')
@app_commands.describe(
    customer_id='For Jamix: customer ID. For Mealdoo: "mealdoo". For Compass: "compass"',
    kitchen_id="For Jamix: kitchen ID. For Mealdoo: site path. For Compass: cost center",
    source_name="Optional name for this source (default: Ruokalista)"
)
async def set_menu_id(interaction: discord.Interaction, customer_id: str, kitchen_id: str, source_name: str = "Ruokalista"):
    """Set/replace the primary API configuration for this server (Admin only)"""
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    is_mealdoo = customer_id.lower() == "mealdoo"
    is_compass = customer_id.lower() == "compass"
    
    if not is_mealdoo and not is_compass:
        try:
            int(customer_id)
            int(kitchen_id)
        except ValueError:
            await interaction.followup.send('❌ For Jamix: Both IDs must be numeric.\n💡 For Mealdoo: use "mealdoo" as customer_id and site path as kitchen_id\n💡 For Compass: use "compass" as customer_id and cost center as kitchen_id')
            return
    
    server_config.set_server_menu(interaction.guild.id, customer_id, kitchen_id, source_name)
    
    config = server_config.get_server_config(interaction.guild.id)
    api_type = config.get("api_type", "jamix")
    test_url = server_config.get_menu_url(interaction.guild.id)
    
    embed = discord.Embed(title="✅ Menu Configuration Updated", color=0x00ff00, timestamp=datetime.now())
    embed.add_field(name="Source Name", value=source_name, inline=False)
    embed.add_field(name="API Type", value=api_type.upper(), inline=False)
    
    if is_mealdoo:
        embed.add_field(name="Site Path", value=kitchen_id, inline=False)
    elif is_compass:
        embed.add_field(name="Cost Center", value=kitchen_id, inline=False)
    else:
        embed.add_field(name="Customer ID", value=customer_id, inline=True)
        embed.add_field(name="Kitchen ID", value=kitchen_id, inline=True)
    
    embed.add_field(name="API URL Example", value=test_url[:100] + "..." if len(test_url) > 100 else test_url, inline=False)
    embed.set_footer(text="Use /test_api or /list_menu_sources to verify the configuration")
    
    await interaction.followup.send(embed=embed)


@bot.tree.command(name='add_menu_source', description='Add or update a named API source for this server')
@app_commands.describe(
    name="Display name for this source (e.g. \"Ravintola Cube\", \"Kahvila\")",
    customer_id='For Jamix: customer ID. For Mealdoo: "mealdoo". For Compass: "compass"',
    kitchen_id="For Jamix: kitchen ID. For Mealdoo: site path. For Compass: cost center",
)
async def add_menu_source(interaction: discord.Interaction, name: str, customer_id: str, kitchen_id: str):
    """Add or replace a named menu source (Admin only)"""
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return

    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    is_mealdoo = customer_id.lower() == "mealdoo"
    is_compass = customer_id.lower() == "compass"

    if not is_mealdoo and not is_compass:
        try:
            int(customer_id)
            int(kitchen_id)
        except ValueError:
            await interaction.followup.send('❌ For Jamix: Both IDs must be numeric.\n💡 Use "mealdoo" or "compass" as customer_id for those APIs.')
            return

    server_config.add_menu_source(interaction.guild.id, name, customer_id, kitchen_id)
    sources = server_config.get_menu_sources(interaction.guild.id)

    embed = discord.Embed(title=f"✅ Menu Source Added: {name}", color=0x00ff00, timestamp=datetime.now())
    api_type = "mealdoo" if is_mealdoo else ("compass" if is_compass else "jamix")
    embed.add_field(name="API Type", value=api_type.upper(), inline=False)
    if is_mealdoo:
        embed.add_field(name="Site Path", value=kitchen_id, inline=False)
    elif is_compass:
        embed.add_field(name="Cost Center", value=kitchen_id, inline=False)
    else:
        embed.add_field(name="Customer ID", value=customer_id, inline=True)
        embed.add_field(name="Kitchen ID", value=kitchen_id, inline=True)
    embed.add_field(name="Total Sources", value=str(len(sources)), inline=False)
    embed.set_footer(text="Use /list_menu_sources to see all configured sources")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='remove_menu_source', description='Remove a named API source from this server')
@app_commands.describe(name='The display name of the source to remove')
async def remove_menu_source(interaction: discord.Interaction, name: str):
    """Remove a named menu source (Admin only)"""
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return

    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    removed = server_config.remove_menu_source(interaction.guild.id, name)

    if removed:
        sources = server_config.get_menu_sources(interaction.guild.id)
        embed = discord.Embed(title=f"✅ Removed Source: {name}", color=0x00ff00, timestamp=datetime.now())
        embed.add_field(name="Remaining Sources", value=str(len(sources)), inline=False)
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"❌ Source named **{name}** not found. Use `/list_menu_sources` to see configured sources.")


@bot.tree.command(name='list_menu_sources', description='List all configured menu sources for this server')
async def list_menu_sources(interaction: discord.Interaction):
    """List all configured menu sources (Admin only)"""
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return

    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    sources = server_config.get_menu_sources(interaction.guild.id)

    embed = discord.Embed(
        title=f"📋 Menu Sources — {interaction.guild.name}",
        color=0x0099ff,
        timestamp=datetime.now(),
    )

    for i, source in enumerate(sources):
        api_type = source.get("api_type", "jamix").upper()
        if source.get("api_type") == "mealdoo":
            detail = f"Site: `{source.get('site_path', '?')}`"
        elif source.get("api_type") == "compass":
            detail = f"Cost Center: `{source.get('cost_center', '?')}`"
        else:
            detail = f"Customer: `{source.get('customer_id', '?')}`, Kitchen: `{source.get('kitchen_id', '?')}`"
        url = server_config.get_menu_url_for_source(source)
        short_url = url[:80] + "…" if len(url) > 80 else url
        embed.add_field(
            name=f"{i + 1}. {source.get('name', 'Unnamed')} ({api_type})",
            value=f"{detail}\n`{short_url}`",
            inline=False,
        )

    embed.set_footer(text="Use /add_menu_source or /remove_menu_source to manage these sources")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name='show_config', description='Show the current server configuration')
async def show_config(interaction: discord.Interaction):
    """Show the current server configuration (Admin only)"""
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    config = server_config.get_server_config(interaction.guild.id)
    daily_channel_id = config.get("daily_channel_id")
    sources = server_config.get_menu_sources(interaction.guild.id)
    
    embed = discord.Embed(
        title=f"📋 Server Configuration — {interaction.guild.name}",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    
    # List all sources
    for i, source in enumerate(sources):
        api_type = source.get("api_type", "jamix").upper()
        if source.get("api_type") == "mealdoo":
            detail = f"Site: `{source.get('site_path', '?')}`"
        elif source.get("api_type") == "compass":
            detail = f"Cost Center: `{source.get('cost_center', '?')}`"
        else:
            detail = f"Customer: `{source.get('customer_id', '?')}`, Kitchen: `{source.get('kitchen_id', '?')}`"
        embed.add_field(
            name=f"Source {i + 1}: {source.get('name', 'Unnamed')} ({api_type})",
            value=detail,
            inline=False,
        )

    if daily_channel_id:
        channel = bot.get_channel(daily_channel_id)
        channel_name = channel.mention if channel and isinstance(channel, discord.TextChannel) else f"<#{daily_channel_id}> (not found)"
    else:
        channel_name = "Not set"
    
    embed.add_field(name="Daily Post Channel", value=channel_name, inline=False)
    embed.set_footer(text="Use /list_menu_sources for details • /add_menu_source or /remove_menu_source to manage sources")
    
    await interaction.followup.send(embed=embed)


@bot.tree.command(name='test_api', description='Test the API connection and data parsing for all configured sources')
async def test_api(interaction: discord.Interaction):
    """Test the API connection and data parsing for this server"""
    guild_id = interaction.guild.id if interaction.guild else None
    
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send("🔄 Testing API connection(s)...")
    
    all_menus = await fetch_all_menus_data(guild_id)
    
    if all_menus:
        embed = discord.Embed(title="✅ API Test Successful", color=0x00ff00, timestamp=datetime.now())
        for source_name, menu_data in all_menus.items():
            days_count = len(menu_data)
            days_list = list(menu_data.keys())[:3]
            embed.add_field(
                name=f"📍 {source_name} — {days_count} day(s)",
                value="\n".join(days_list) or "No days",
                inline=False,
            )
        await interaction.edit_original_response(content=None, embed=embed)
    else:
        await interaction.edit_original_response(content="❌ API test failed. Check console for error details or verify your sources with `/list_menu_sources`")

@bot.tree.command(name='cleanup_old_menus', description='Remove old persistent menu views from the database')
@app_commands.describe(days="Number of days (default: 7) - menus older than this will be removed")
async def cleanup_old_menus(interaction: discord.Interaction, days: int = 7):
    """Cleanup old persistent menus from the database (Admin only)"""
    # Check if user has administrator permissions
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        deleted_count = button_db.cleanup_old_menus(days)
        
        embed = discord.Embed(
            title="✅ Cleanup Complete",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.add_field(name="Removed Views", value=str(deleted_count), inline=True)
        embed.add_field(name="Older Than", value=f"{days} days", inline=True)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error during cleanup: {e}")

if __name__ == "__main__":
    # Get bot token from environment variable
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables.")
        print("Please create a .env file with your Discord bot token.")
    else:
        bot.run(TOKEN)