import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from datetime import datetime, time, date
import zoneinfo
import os
from dotenv import load_dotenv
from config import ServerConfig

# Load environment variables
load_dotenv()

# Initialize server configuration
server_config = ServerConfig()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API configuration
FOOD_API_KEY = os.getenv('FOOD_API_KEY')  # Add your API key to .env file

class MenuView(discord.ui.View):
    """Interactive view for switching between menu days"""
    
    def __init__(self, menu_data, current_day=0, guild_id=None, persistent=True):
        # Use no timeout for daily messages, 15 minutes for user commands
        timeout = None if persistent else 900  # 15 minutes for user interactions
        super().__init__(timeout=timeout)
        self.menu_data = menu_data
        self.current_day = current_day
        self.days = list(menu_data.keys())
        self.guild_id = guild_id
        self.persistent = persistent
        
    @discord.ui.button(label='◀️ Edellinen Päivä', style=discord.ButtonStyle.secondary)
    async def previous_day(self, interaction: discord.Interaction, button: discord.ui.Button, custom_id="previous_day"):
        self.current_day = (self.current_day - 1) % len(self.days)
        embed = self.create_menu_embed()
        
        # Check if this is an ephemeral message by looking at message flags
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral
        
        if is_ephemeral:
            # This is a personal ephemeral message - edit it
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # This is the original shared message - create ephemeral response
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    @discord.ui.button(label='▶️ Seuraava Päivä', style=discord.ButtonStyle.secondary, custom_id="next_day")
    async def next_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_day = (self.current_day + 1) % len(self.days)
        embed = self.create_menu_embed()
        
        # Check if this is an ephemeral message by looking at message flags
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral
        
        if is_ephemeral:
            # This is a personal ephemeral message - edit it
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # This is the original shared message - create ephemeral response
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label='🔄 Päivitä', style=discord.ButtonStyle.primary, custom_id="refresh_menu")
    async def refresh_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Fetch fresh menu data using the guild_id
        guild_id = self.guild_id or (interaction.guild.id if interaction.guild else None)
        
        # Check if this is an ephemeral message by looking at message flags
        is_ephemeral = interaction.message and interaction.message.flags.ephemeral
        
        if is_ephemeral:
            # This is a personal ephemeral message - edit it
            await interaction.response.defer()
            new_menu_data = await fetch_menu_data(guild_id)
            if new_menu_data:
                self.menu_data = new_menu_data
                self.days = list(new_menu_data.keys())
                self.current_day = 0  # Reset to first day
                embed = self.create_menu_embed()
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.edit_original_response(content="❌ Failed to refresh menu data.")
        else:
            # This is the original shared message - create ephemeral response
            await interaction.response.defer(ephemeral=True)
            new_menu_data = await fetch_menu_data(guild_id)
            if new_menu_data:
                # Create a new view with fresh data for this user
                user_view = MenuView(new_menu_data, 0, guild_id, persistent=False)  # User interaction, not persistent
                embed = user_view.create_menu_embed()
                await interaction.followup.send(embed=embed, view=user_view, ephemeral=True)
            else:
                await interaction.followup.send("Failed to refresh menu data.", ephemeral=True)
    
    def create_menu_embed(self):
        """Create an embed for the current day's menu"""
        if not self.days:
            return discord.Embed(title="No Menu Available", color=0xff0000)
        
        current_day_name = self.days[self.current_day]
        day_menu = self.menu_data[current_day_name]
        
        embed = discord.Embed(
            title=f"🍽️ Ruokalista - {current_day_name}",
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

async def fetch_menu_data(guild_id = None):
    """Fetch menu data from the Jamix API for a specific server"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {}
            if FOOD_API_KEY:
                headers['Authorization'] = f'Bearer {FOOD_API_KEY}'
            
            # Get the API URL for this specific server
            if guild_id:
                api_url = server_config.get_menu_url(guild_id)
            else:
                # Fallback to default URL if no guild specified
                api_url = "https://fi.jamix.cloud/apps/menuservice/rest/haku/menu/12345/12?lang=fi"
            
            # Fetch data from the actual Jamix API
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    jamix_data = await response.json()
                    parsed_data = parse_jamix_data(jamix_data)
                    
                    if parsed_data:
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
        return None

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Start the daily menu posting task
    daily_menu_post.start()

@bot.tree.command(name='menu', description='Show the weekly menu (ephemeral for users, public for admins)')
async def show_menu(interaction: discord.Interaction):
    """Show the weekly menu with interactive navigation"""
    guild_id = interaction.guild.id if interaction.guild else None
    
    # Check if user is an administrator to determine if response should be public or ephemeral
    is_admin = (isinstance(interaction.user, discord.Member) and 
                interaction.user.guild_permissions.administrator)
    
    # Defer with ephemeral=True for non-admins, public for admins
    await interaction.response.defer(ephemeral=not is_admin)
    
    menu_data = await fetch_menu_data(guild_id)
    
    if not menu_data:
        await interaction.followup.send("❌ Ei voitu noutaa ruokalistaa tällä hetkellä. Yritä myöhemmin uudelleen.")
        return
    
    view = MenuView(menu_data, guild_id=guild_id, persistent=False)  # Non-persistent for user commands
    embed = view.create_menu_embed()
    
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name='today', description='Show today\'s menu')
async def todays_menu(interaction: discord.Interaction):
    """Show today's menu"""
    guild_id = interaction.guild.id if interaction.guild else None
    
    await interaction.response.defer(ephemeral=True)
    
    menu_data = await fetch_menu_data(guild_id)
    
    if not menu_data:
        await interaction.followup.send("❌ Ei voitu noutaa ruokalistaa tällä hetkellä. Yritä myöhemmin uudelleen.")
        return
    
    # Try to find today's menu by matching the exact date
    today = datetime.now()
    today_str = today.strftime("%A, %B %d")  # Format: "Thursday, August 22"
    
    # First try to find an exact match
    found_menu = None
    found_day_name = None
    
    if today_str in menu_data:
        found_menu = menu_data[today_str]
        found_day_name = today_str
    else:
        # If no exact match, look for the next available day starting from today
        for day_name, day_menu in menu_data.items():
            # Parse the day name to get the date
            try:
                # Extract date from "Thursday, August 22" format
                day_parts = day_name.split(", ")
                if len(day_parts) == 2:
                    month_day = day_parts[1]
                    # Create a date string and parse it
                    current_year = today.year
                    day_date_str = f"{month_day}, {current_year}"
                    day_date = datetime.strptime(day_date_str, "%B %d, %Y").date()
                    
                    # If this is today or a future date, use it
                    if day_date >= today.date():
                        found_menu = day_menu
                        found_day_name = day_name
                        break
            except (ValueError, IndexError):
                continue
    
    if found_menu and found_day_name:
        embed = discord.Embed(
            title=f"🍽️ Ruokalista - {found_day_name}",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        
        # Add a note if this isn't actually today
        if found_day_name != today_str:
            embed.description = f"*Today's menu not available. Showing next available menu.*"
        
        for category, items in found_menu.items():
            if items:
                items_text = "\n".join([f"• {item}" for item in items])
                embed.add_field(name=f"**{category}**", value=items_text, inline=False)
        
        if not any(found_menu.values()):
            embed.add_field(name="No Menu Available", value="No menu items found for this day.", inline=False)
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"❌ No menu available for today or upcoming days.")

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
            menu_data = await fetch_menu_data(guild_id)
            if not menu_data:
                await channel.send("❌ Ei voitu noutaa tämän päivän ruokalistaa.")
                continue
            # Use local time for menu matching
            local_tz = zoneinfo.ZoneInfo("Europe/Helsinki")  # Finnish time with DST support
            today = datetime.now(local_tz)
            today_str = today.strftime("%A, %B %d")  # Format: "Thursday, August 22"
            
            found_menu = None
            found_day_name = None
            
            if today_str in menu_data:
                found_menu = menu_data[today_str]
                found_day_name = today_str
            else:
                # If no exact match, look for the next available day
                for day_name, day_menu in menu_data.items():
                    try:
                        day_parts = day_name.split(", ")
                        if len(day_parts) == 2:
                            month_day = day_parts[1]
                            current_year = today.year
                            day_date_str = f"{month_day}, {current_year}"
                            day_date = datetime.strptime(day_date_str, "%B %d, %Y").date()
                            
                            if day_date >= today.date():
                                found_menu = day_menu
                                found_day_name = day_name
                                break
                    except (ValueError, IndexError):
                        continue
            
            if found_menu and found_day_name:
                # Find the index of the menu for the view
                day_names = list(menu_data.keys())
                try:
                    current_day_index = day_names.index(found_day_name)
                except ValueError:
                    current_day_index = 0
                
                # Use persistent=True for daily messages so buttons don't expire
                view = MenuView(menu_data, current_day=current_day_index, guild_id=guild_id, persistent=True)
                embed = view.create_menu_embed()
                
                message = f"**Ruokalista {found_day_name}:**"
                if found_day_name != today_str:
                    message = f"**Tämän päivän ruokalista ei saatavilla, näytetään {found_day_name}:**"

                await channel.send(message, embed=embed, view=view)
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

@bot.tree.command(name='set_menu_id', description='Set the Jamix customer and kitchen IDs for this server')
@app_commands.describe(
    customer_id="The Jamix customer ID for your restaurant",
    kitchen_id="The Jamix kitchen ID for your restaurant"
)
async def set_menu_id(interaction: discord.Interaction, customer_id: str, kitchen_id: str):
    """Set the Jamix customer and kitchen IDs for this server (Admin only)"""
    # Check if user has administrator permissions
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Validate IDs (should be numeric)
    try:
        int(customer_id)
        int(kitchen_id)
    except ValueError:
        await interaction.followup.send("❌ Asiakas-ID ja Keittiö-ID täytyy olla numeerisia arvoja.")
        return
    
    # Save to configuration
    server_config.set_server_menu(interaction.guild.id, customer_id, kitchen_id)
    
    # Test the API with new IDs
    test_url = server_config.get_menu_url(interaction.guild.id)
    
    embed = discord.Embed(
        title="✅ Menu Configuration Updated",
        color=0x00ff00,
        timestamp=datetime.now()
    )
    embed.add_field(name="Customer ID", value=customer_id, inline=True)
    embed.add_field(name="Kitchen ID", value=kitchen_id, inline=True)
    embed.add_field(name="API URL", value=test_url, inline=False)
    embed.set_footer(text="Use /test_api to verify the configuration works")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='show_config', description='Show the current server configuration')
async def show_config(interaction: discord.Interaction):
    """Show the current server configuration (Admin only)"""
    # Check if user has administrator permissions
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sinä tarvitset ylläpitäjäoikeudet käyttääksesi tätä komentoa.", ephemeral=True)
        return
    
    if not interaction.guild:
        await interaction.response.send_message("❌ Tämä komento voidaan käyttää vain palvelimella.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    config = server_config.get_server_config(interaction.guild.id)
    daily_channel_id = config.get("daily_channel_id")
    
    embed = discord.Embed(
        title=f"📋 Server Configuration - {interaction.guild.name}",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    
    embed.add_field(name="Customer ID", value=config.get("customer_id", "Not set"), inline=True)
    embed.add_field(name="Kitchen ID", value=config.get("kitchen_id", "Not set"), inline=True)
    embed.add_field(name="Language", value=config.get("language", "fi"), inline=True)
    
    if daily_channel_id:
        channel = bot.get_channel(daily_channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            channel_name = channel.mention
        else:
            channel_name = f"<#{daily_channel_id}> (not found)"
    else:
        channel_name = "Not set"
    
    embed.add_field(name="Daily Post Channel", value=channel_name, inline=False)
    embed.add_field(name="API URL", value=server_config.get_menu_url(interaction.guild.id), inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name='test_api', description='Test the Jamix API connection and data parsing for this server')
async def test_api(interaction: discord.Interaction):
    """Test the Jamix API connection and data parsing for this server"""
    guild_id = interaction.guild.id if interaction.guild else None
    
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send("🔄 Testing API connection...")
    
    menu_data = await fetch_menu_data(guild_id)
    
    if menu_data:
        days_count = len(menu_data)
        days_list = list(menu_data.keys())[:3]  # Show first 3 days
        
        embed = discord.Embed(
            title="✅ API Test Successful",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.add_field(name="Days Found", value=str(days_count), inline=True)
        embed.add_field(name="Sample Days", value="\n".join(days_list), inline=False)
        
        if interaction.guild:
            config = server_config.get_server_config(interaction.guild.id)
            embed.add_field(name="Using Configuration", 
                          value=f"Customer: {config['customer_id']}, Kitchen: {config['kitchen_id']}", 
                          inline=False)
        
        await interaction.edit_original_response(content=None, embed=embed)
    else:
        await interaction.edit_original_response(content="❌ API test failed. Check console for error details or verify your menu IDs with `/show_config`")

if __name__ == "__main__":
    # Get bot token from environment variable
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables.")
        print("Please create a .env file with your Discord bot token.")
    else:
        bot.run(TOKEN)