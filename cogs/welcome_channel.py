import discord
from discord.ext import commands
from discord import app_commands
import logging
import io
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import aiohttp
import os
from datetime import datetime
import colorsys
import sqlite3
from command_animator import command_animation
from admin_utils import is_bot_owner

try:
    from db.mongo_adapters import mongo_enabled, WelcomeChannelAdapter, AdminsAdapter
except Exception:
    mongo_enabled = lambda: False
    WelcomeChannelAdapter = None
    AdminsAdapter = None

logger = logging.getLogger(__name__)


class BGImageModal(discord.ui.Modal, title="Set Background Image"):
    """Modal for setting background image URL"""
    
    image_url = discord.ui.TextInput(
        label="Image URL",
        placeholder="Enter the image URL (e.g., https://example.com/image.png)",
        required=True,
        style=discord.TextStyle.long,
        max_length=500
    )
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            url = str(self.image_url.value).strip()
            
            # Basic URL validation
            if not url.startswith(('http://', 'https://')):
                await interaction.response.send_message(
                    "❌ Invalid URL. Please enter a valid HTTP or HTTPS URL.",
                    ephemeral=True
                )
                return
            
            # Try to download and validate the image
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            await interaction.response.send_message(
                                f"❌ Failed to download image. HTTP Status: {resp.status}",
                                ephemeral=True
                            )
                            return
                        
                        # Check if it's an image
                        content_type = resp.headers.get('Content-Type', '')
                        if not content_type.startswith('image/'):
                            await interaction.response.send_message(
                                f"❌ URL does not point to an image. Content-Type: {content_type}",
                                ephemeral=True
                            )
                            return
                        
                        # Try to open it as an image
                        image_data = await resp.read()
                        try:
                            Image.open(io.BytesIO(image_data))
                        except Exception:
                            await interaction.response.send_message(
                                "❌ Failed to process the image. Please ensure it's a valid image file.",
                                ephemeral=True
                            )
                            return
            
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Failed to validate image URL: {str(e)}",
                    ephemeral=True
                )
                return
            
            # Save to database
            success = WelcomeChannelAdapter.set_bg_image(interaction.guild.id, url)
            
            if success:
                embed = discord.Embed(
                    title="✅ Background Image Set",
                    description=f"Background image has been updated!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Image URL",
                    value=url[:100] + "..." if len(url) > 100 else url,
                    inline=False
                )
                embed.add_field(
                    name="What happens next?",
                    value="This image will be used as the background for all welcome messages!",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"[WelcomeChannel] Background image set for guild {interaction.guild.id}")
            else:
                await interaction.response.send_message(
                    "❌ Failed to save background image. Please try again.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"[WelcomeChannel] Error in BG image modal: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )


class ChannelSelectView(discord.ui.View):
    """View with channel select dropdown"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select a channel for welcome messages",
        channel_types=[discord.ChannelType.text]
    )
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        """Handle channel selection"""
        try:
            channel = select.values[0]
            
            # Save to database
            success = WelcomeChannelAdapter.set(interaction.guild.id, channel.id, enabled=True)
            
            if success:
                embed = discord.Embed(
                    title="✅ Welcome Channel Set",
                    description=f"Welcome messages will now be sent to {channel.mention}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="What happens next?",
                    value="When a new member joins this server, they'll receive a personalized welcome message with a custom image!",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"[WelcomeChannel] Welcome channel set to {channel.id} for guild {interaction.guild.id}")
            else:
                await interaction.response.send_message(
                    "❌ Failed to set welcome channel. Please try again.",
                    ephemeral=True
                )
        
        except Exception as e:
            logger.error(f"[WelcomeChannel] Error in channel select: {e}")
            await interaction.response.send_message(
                f"❌ An error occurred: {str(e)}",
                ephemeral=True
            )


class WelcomeMenuView(discord.ui.View):
    """View with buttons for welcome configuration"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
    
    @discord.ui.button(label="Set Channel", style=discord.ButtonStyle.primary, emoji="📢")
    async def set_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to set the welcome channel"""
        embed = discord.Embed(
            title="📢 Select Welcome Channel",
            description="Choose the channel where welcome messages will be sent:",
            color=discord.Color.blue()
        )
        view = ChannelSelectView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="BG Image", style=discord.ButtonStyle.secondary, emoji="🖼️")
    async def bg_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to configure background image"""
        modal = BGImageModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Welcome Status", style=discord.ButtonStyle.success, emoji="👁️")
    async def welcome_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to show demo welcome message"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the WelcomeChannel cog
            welcome_cog = self.bot.get_cog('WelcomeChannel')
            if not welcome_cog:
                await interaction.followup.send(
                    "❌ Welcome channel cog not found.",
                    ephemeral=True
                )
                return
            
            # Create demo welcome image using the user who clicked the button
            logger.info(f"[WelcomeChannel] Creating demo welcome image for {interaction.user.name}")
            image_buffer = await welcome_cog.create_welcome_image(interaction.user)
            
            # Create embed
            embed = discord.Embed(
                description=f"Hi {interaction.user.mention} Welcome to the {interaction.guild.name}🥳",
                color=discord.Color.blue()
            )
            embed.set_image(url="attachment://welcome_demo.png")
            embed.set_footer(text=f"Demo Preview • {datetime.utcnow().strftime('%B %d, %Y')}")
            
            # Send demo message
            file = discord.File(image_buffer, filename="welcome_demo.png")
            await interaction.followup.send(
                content="**🎉 Demo Welcome Message Preview:**",
                embed=embed,
                file=file,
                ephemeral=True
            )
            
            logger.info(f"[WelcomeChannel] Demo welcome message sent for {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"[WelcomeChannel] Error creating demo welcome message: {e}")
            await interaction.followup.send(
                f"❌ An error occurred while creating demo: {str(e)}",
                ephemeral=True
            )




class WelcomeChannel(commands.Cog):
    """Cog for managing welcome messages with custom images when members join"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("[WelcomeChannel] Cog initialized")
    
    async def get_dominant_color(self, image_url: str) -> tuple:
        """Extract dominant color from user's avatar"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        img = Image.open(io.BytesIO(image_data))
                        img = img.resize((50, 50))  # Resize for faster processing
                        img = img.convert('RGB')
                        
                        # Get average color
                        pixels = list(img.getdata())
                        r = sum([p[0] for p in pixels]) // len(pixels)
                        g = sum([p[1] for p in pixels]) // len(pixels)
                        b = sum([p[2] for p in pixels]) // len(pixels)
                        
                        # Make it more vibrant
                        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                        s = min(1.0, s * 1.5)  # Increase saturation
                        v = min(1.0, v * 1.2)  # Increase brightness
                        r, g, b = colorsys.hsv_to_rgb(h, s, v)
                        
                        return (int(r * 255), int(g * 255), int(b * 255))
        except Exception as e:
            logger.error(f"Error extracting dominant color: {e}")
        
        # Default to a nice blue color
        return (88, 101, 242)  # Discord blurple
    
    async def create_welcome_image(self, member: discord.Member) -> io.BytesIO:
        """Create a custom welcome image for the member"""
        try:
            # Image dimensions
            width, height = 1000, 300
            
            # Get user's avatar
            avatar_url = member.display_avatar.url
            
            # Check if there's a custom background image
            settings = WelcomeChannelAdapter.get(member.guild.id)
            bg_image_url = settings.get('bg_image_url') if settings else None
            
            if bg_image_url:
                # Use custom background image
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(bg_image_url) as resp:
                            if resp.status == 200:
                                bg_data = await resp.read()
                                img = Image.open(io.BytesIO(bg_data))
                                img = img.convert('RGB')
                                img = img.resize((width, height))
                            else:
                                raise Exception(f"Failed to download background image: {resp.status}")
                except Exception as e:
                    logger.warning(f"Failed to load custom background image, using default: {e}")
                    # Fall back to gradient
                    bg_color = await self.get_dominant_color(avatar_url)
                    img = Image.new('RGB', (width, height), bg_color)
                    draw = ImageDraw.Draw(img)
                    for i in range(height):
                        alpha = i / height
                        darker = tuple(int(c * (1 - alpha * 0.3)) for c in bg_color)
                        draw.rectangle([(0, i), (width, i+1)], fill=darker)
            else:
                # Use default gradient background
                bg_color = await self.get_dominant_color(avatar_url)
                img = Image.new('RGB', (width, height), bg_color)
                draw = ImageDraw.Draw(img)
                for i in range(height):
                    alpha = i / height
                    darker = tuple(int(c * (1 - alpha * 0.3)) for c in bg_color)
                    draw.rectangle([(0, i), (width, i+1)], fill=darker)
            
            # Create draw object (in case it wasn't created above)
            draw = ImageDraw.Draw(img)
            
            # Download and process avatar
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_data = await resp.read()
                        avatar = Image.open(io.BytesIO(avatar_data))
                        avatar = avatar.resize((180, 180))
                        
                        # Create circular mask
                        mask = Image.new('L', (180, 180), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, 180, 180), fill=255)
                        
                        # Create white circle background
                        circle_bg = Image.new('RGB', (190, 190), (255, 255, 255))
                        circle_mask = Image.new('L', (190, 190), 0)
                        circle_draw = ImageDraw.Draw(circle_mask)
                        circle_draw.ellipse((0, 0, 190, 190), fill=255)
                        
                        # Paste white circle onto main image
                        img.paste(circle_bg, (60, 55), circle_mask)
                        
                        # Paste avatar
                        avatar_rgb = avatar.convert('RGB')
                        img.paste(avatar_rgb, (65, 60), mask)
            
            # Load modern fonts with better styling
            try:
                # Try to load Arial Bold for headings - more impactful
                font_large = ImageFont.truetype("arialbd.ttf", 72)  # Larger, bolder server name
                font_medium = ImageFont.truetype("arialbd.ttf", 52)  # Bold welcome text
                font_small = ImageFont.truetype("arial.ttf", 38)  # Regular for member count
            except Exception as e:
                logger.warning(f"Failed to load Arial Bold, trying regular Arial: {e}")
                try:
                    # Fallback to regular arial with increased sizes
                    font_large = ImageFont.truetype("arial.ttf", 70)
                    font_medium = ImageFont.truetype("arial.ttf", 50)
                    font_small = ImageFont.truetype("arial.ttf", 36)
                except Exception as e2:
                    logger.warning(f"Failed to load Arial, trying project font: {e2}")
                    try:
                        # Try project font as last resort before default
                        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts', 'unifont-16.0.04.otf')
                        font_large = ImageFont.truetype(font_path, 70)
                        font_medium = ImageFont.truetype(font_path, 50)
                        font_small = ImageFont.truetype(font_path, 36)
                    except:
                        # Fallback to default font
                        logger.warning("All font loading failed, using default font")
                        font_large = ImageFont.load_default()
                        font_medium = ImageFont.load_default()
                        font_small = ImageFont.load_default()
            
            # Prepare text content - 3 line layout
            text_x = 280
            
            # Line 1: Welcome username (combined)
            welcome_text = f"Welcome {member.name}"
            
            # Line 2: to Server Name (large, bold, main focus)
            server_text = f"to {member.guild.name}"
            
            # Line 3: Member count with ordinal suffix
            member_count = member.guild.member_count
            # Add ordinal suffix (st, nd, rd, th)
            if 10 <= member_count % 100 <= 20:
                suffix = 'th'
            else:
                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(member_count % 10, 'th')
            count_text = f"you are the {member_count:,}{suffix} member!"

            # Enhanced text styling
            text_color = (255, 255, 255)  # Pure white
            
            # Helper function to draw text with shadow and stroke
            def draw_text_with_effects(xy, text, font, is_bold=False):
                x, y = xy
                
                # Draw shadow (offset down and right)
                shadow_offset = 5 if is_bold else 3
                draw.text((x + shadow_offset, y + shadow_offset), text, 
                         fill=(20, 20, 20), font=font)
                
                # Draw strong stroke for better visibility
                stroke_width = 5 if is_bold else 3
                draw.text((x, y), text, fill=text_color, font=font,
                         stroke_width=stroke_width, stroke_fill=(0, 0, 0))

            # Draw text with 3-line layout
            current_y = 60
            
            # Line 1: "Welcome username"
            draw_text_with_effects((text_x, current_y), welcome_text, font_medium, is_bold=True)
            current_y += 70
            
            # Line 2: "to Server name" (large, bold, hero text)
            draw_text_with_effects((text_x, current_y), server_text, font_large, is_bold=True)
            current_y += 90
            
            # Line 3: Member count
            draw_text_with_effects((text_x, current_y), count_text, font_small, is_bold=False)

            

            
            # Save to BytesIO
            output = io.BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error creating welcome image: {e}")
            raise
    
    async def check_admin_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin permissions (Discord, Bot Owner, or Bot Admin)"""
        # 1. Discord Admin
        if interaction.user.guild_permissions.administrator:
            return True
        
        # 2. Bot Owner
        if await is_bot_owner(self.bot, interaction.user.id):
            return True
            
        # 3. MongoDB Admin
        if mongo_enabled() and AdminsAdapter:
            admin = AdminsAdapter.get(interaction.user.id)
            if admin:
                return True
                
        # 4. SQLite Admin
        try:
            with sqlite3.connect('db/settings.sqlite') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM admin WHERE id = ?", (interaction.user.id,))
                if cursor.fetchone():
                    return True
        except Exception as e:
            logger.error(f"SQLite admin check failed: {e}")
            
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Event listener for when a member joins the server"""
        try:
            # Check if MongoDB is enabled
            if not mongo_enabled():
                logger.warning("[WelcomeChannel] MongoDB not enabled, skipping welcome message")
                return
            
            # Get welcome channel settings
            settings = WelcomeChannelAdapter.get(member.guild.id)
            if not settings or not settings.get('enabled'):
                logger.debug(f"[WelcomeChannel] No welcome channel configured for guild {member.guild.id}")
                return
            
            channel_id = settings.get('channel_id')
            logger.info(f"[WelcomeChannel] Retrieved channel ID {channel_id} for guild {member.guild.id}")
            
            channel = member.guild.get_channel(channel_id)
            
            if not channel:
                logger.warning(f"[WelcomeChannel] Channel {channel_id} not found in guild {member.guild.id}")
                return
            
            logger.info(f"[WelcomeChannel] Sending welcome message to channel: {channel.name} ({channel.id})")
            
            # Create welcome image
            logger.info(f"[WelcomeChannel] Creating welcome image for {member.name} in {member.guild.name}")
            image_buffer = await self.create_welcome_image(member)
            
            # Create embed
            embed = discord.Embed(
                description=f"Hi {member.mention} Welcome to the {member.guild.name}🥳",
                color=discord.Color.blue()
            )
            embed.set_image(url="attachment://welcome.png")
            embed.set_footer(text=f"Member joined • {datetime.utcnow().strftime('%B %d, %Y')}")
            
            # Send welcome message
            file = discord.File(image_buffer, filename="welcome.png")
            await channel.send(embed=embed, file=file)
            
            logger.info(f"[WelcomeChannel] Welcome message sent for {member.name}")
            
        except Exception as e:
            logger.error(f"[WelcomeChannel] Error sending welcome message: {e}")
    
    @app_commands.command(name="welcome", description="Configure welcome message settings")
    @command_animation
    async def welcome(self, interaction: discord.Interaction):
        """Main welcome configuration command with button menu"""
        try:
            # Check permissions
            if not await self.check_admin_permission(interaction):
                await interaction.followup.send(
                    "❌ You need administrator permissions to configure welcome settings.",
                    ephemeral=True
                )
                return

            # Check if MongoDB is enabled
            if not mongo_enabled():
                await interaction.followup.send(
                    "❌ MongoDB is not configured. Welcome channel feature requires MongoDB.",
                    ephemeral=True
                )
                return
            
            # Get current settings
            settings = WelcomeChannelAdapter.get(interaction.guild.id)
            current_channel = None
            bg_image_url = None
            if settings:
                if settings.get('channel_id'):
                    current_channel = interaction.guild.get_channel(settings['channel_id'])
                bg_image_url = settings.get('bg_image_url')
            
            # Create embed
            embed = discord.Embed(
                title="🎉 Welcome Message Configuration",
                description="Configure how new members are welcomed to your server!",
                color=discord.Color.blue()
            )
            
            if current_channel:
                embed.add_field(
                    name="📢 Current Welcome Channel",
                    value=f"{current_channel.mention}",
                    inline=False
                )
                embed.add_field(
                    name="✅ Status",
                    value="Enabled" if settings.get('enabled') else "Disabled",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📢 Current Welcome Channel",
                    value="Not configured",
                    inline=False
                )
            
            # Add background image status
            if bg_image_url:
                embed.add_field(
                    name="🖼️ Background Image",
                    value="Custom image configured",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🖼️ Background Image",
                    value="Using default gradient",
                    inline=True
                )
            
            # Create view with buttons
            view = WelcomeMenuView(self.bot)
            
            # Check if interaction was already responded to (deferred)
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"[WelcomeChannel] Error showing welcome menu: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
    
    @app_commands.command(name="removewelcomechannel", description="Remove the welcome channel configuration")
    @command_animation
    async def remove_welcome_channel(self, interaction: discord.Interaction):
        """Remove the welcome channel configuration"""
        try:
            # Check permissions
            if not await self.check_admin_permission(interaction):
                await interaction.followup.send(
                    "❌ You need administrator permissions to remove the welcome channel.",
                    ephemeral=True
                )
                return

            # Check if MongoDB is enabled
            if not mongo_enabled():
                await interaction.followup.send(
                    "❌ MongoDB is not configured.",
                    ephemeral=True
                )
                return
            
            # Check permissions
            if not interaction.user.guild_permissions.administrator:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ You need administrator permissions to remove the welcome channel.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ You need administrator permissions to remove the welcome channel.",
                        ephemeral=True
                    )
                return
            
            # Delete from database
            success = WelcomeChannelAdapter.delete(interaction.guild.id)
            
            if success:
                embed = discord.Embed(
                    title="✅ Welcome Channel Removed",
                    description="Welcome messages have been disabled for this server.",
                    color=discord.Color.orange()
                )
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.info(f"[WelcomeChannel] Welcome channel removed for guild {interaction.guild.id}")
            else:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ No welcome channel was configured for this server.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ No welcome channel was configured for this server.",
                        ephemeral=True
                    )
                
        except Exception as e:
            logger.error(f"[WelcomeChannel] Error removing welcome channel: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )


async def setup(bot):
    await bot.add_cog(WelcomeChannel(bot))
