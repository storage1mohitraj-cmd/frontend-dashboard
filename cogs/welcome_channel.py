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
                    if bg_image_url.startswith('/api/static/'):
                        # Load from local filesystem
                        filename = bg_image_url.split('/')[-1]
                        filepath = os.path.join("data", "uploads", filename)
                        img = Image.open(filepath)
                        img = img.convert('RGB')
                        img = img.resize((width, height))
                    else:
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
                        avatar = Image.open(io.BytesIO(avatar_data)).convert('RGBA')
                        
                        # Use anti-aliasing via supersampling for high-quality circles
                        scale = 3
                        
                        # 1. Prepare Avatar (220x220)
                        avatar_large = avatar.resize((220 * scale, 220 * scale), Image.Resampling.LANCZOS)
                        mask = Image.new('L', (220 * scale, 220 * scale), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, 220 * scale, 220 * scale), fill=255)
                        
                        avatar_large.putalpha(mask)
                        avatar_scaled = avatar_large.resize((220, 220), Image.Resampling.LANCZOS)
                        
                        # 2. Prepare Border (240x240)
                        border = Image.new('RGBA', (240 * scale, 240 * scale), (255, 255, 255, 0))
                        border_draw = ImageDraw.Draw(border)
                        border_draw.ellipse((0, 0, 240 * scale, 240 * scale), fill=(255, 255, 255, 255))
                        border_scaled = border.resize((240, 240), Image.Resampling.LANCZOS)
                        
                        # Paste white circle onto main image
                        img.paste(border_scaled, (40, 30), border_scaled)
                        
                        # Paste avatar over it
                        img.paste(avatar_scaled, (50, 40), avatar_scaled)
            
            # Prepare text content
            def _resolve_img(template: str) -> str:
                ordinal_sfx = lambda n: f"{n}{'th' if 10<=n%100<=20 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"
                return (template
                    .replace('{mention}',      member.display_name)
                    .replace('{username}',     member.display_name)
                    .replace('{server}',       member.guild.name)
                    .replace('{member_count}', ordinal_sfx(member.guild.member_count))
                    .replace('{date}',         datetime.utcnow().strftime('%B %d, %Y')))

            raw_title = settings.get('embed_title') if settings else None
            raw_subtitle = settings.get('embed_subtitle') if settings else None
            
            if not raw_title:
                raw_title = 'Welcome {username} to {server}'
            if not raw_subtitle:
                raw_subtitle = 'you are the {member_count} member!'

            welcome_text = _resolve_img(raw_title)
            count_text = _resolve_img(raw_subtitle)

            text_x = 300
            max_text_width = width - text_x - 30  # 30px padding on the right
            
            # Determine which font path to use
            current_font_path = None
            try:
                font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts', 'VarelaRound.ttf')
                if os.path.exists(font_path):
                    current_font_path = font_path
                else:
                    raise Exception("VarelaRound not found")
            except Exception as e:
                logger.warning(f"Failed to load VarelaRound: {e}")
                try:
                    current_font_path = "arialbd.ttf"
                    ImageFont.truetype(current_font_path, 48)  # Test load
                except Exception:
                    try:
                        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts', 'unifont-16.0.04.otf')
                        if os.path.exists(font_path):
                            current_font_path = font_path
                    except:
                        current_font_path = None

            font_large, font_medium = None, None
            w1, h1, w2, h2 = 0, 0, 0, 0
            
            if current_font_path:
                # Dynamically scale large font (Line 1)
                for size in range(48, 16, -2):
                    font_large = ImageFont.truetype(current_font_path, size)
                    try:
                        bbox = draw.textbbox((0, 0), welcome_text, font=font_large)
                        w1, h1 = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except AttributeError:
                        w1, h1 = draw.textsize(welcome_text, font=font_large)
                    if w1 <= max_text_width:
                        break
                        
                # Dynamically scale medium font (Line 2)
                for size in range(42, 14, -2):
                    font_medium = ImageFont.truetype(current_font_path, size)
                    try:
                        bbox = draw.textbbox((0, 0), count_text, font=font_medium)
                        w2, h2 = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except AttributeError:
                        w2, h2 = draw.textsize(count_text, font=font_medium)
                    if w2 <= max_text_width:
                        break
            else:
                logger.warning("All font loading failed, using default font")
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                try:
                    bbox1 = draw.textbbox((0, 0), welcome_text, font=font_large)
                    bbox2 = draw.textbbox((0, 0), count_text, font=font_medium)
                    w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
                    w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
                except AttributeError:
                    w1, h1 = draw.textsize(welcome_text, font=font_large)
                    w2, h2 = draw.textsize(count_text, font=font_medium)

            # Enhanced text styling
            text_color = (255, 255, 255)  # Pure white
            
            # Helper function to draw text with heavy stroke
            def draw_text_with_effects(xy, text, font):
                x, y = xy
                # Dynamically adjust stroke width based on scaled font size
                stroke_width = max(2, int(getattr(font, 'size', 32) * 0.08)) if current_font_path else 2
                draw.text((x, y), text, fill=text_color, font=font,
                         stroke_width=stroke_width, stroke_fill=(0, 0, 0))

            spacing = 15
            total_text_height = h1 + h2 + spacing
            
            # Vertically center text block
            start_y = (height - total_text_height) // 2
            
            # Draw Line 1
            draw_text_with_effects((text_x, start_y), welcome_text, font_large)
            
            # Draw Line 2
            current_y = start_y + h1 + spacing
            draw_text_with_effects((text_x, current_y), count_text, font_medium)

            

            
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

            # ── Resolve custom text fields ──────────────────────────────
            def _resolve(template: str) -> str:
                """Replace {variables} with real values."""
                ordinal = lambda n: f"{n}{'th' if 10<=n%100<=20 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"
                today = datetime.utcnow().strftime('%B %d, %Y')
                return (template
                    .replace('{mention}',      member.mention)
                    .replace('{username}',     member.display_name)
                    .replace('{server}',       member.guild.name)
                    .replace('{member_count}', ordinal(member.guild.member_count))
                    .replace('{date}',         today))

            raw_welcome_text  = settings.get('welcome_text',  'Hi {mention} Welcome to the {server}🥳')
            raw_footer_text   = settings.get('footer_text',   'Member joined • {date}')
            raw_embed_color   = settings.get('embed_color',   '#3b82f6')

            welcome_content = _resolve(raw_welcome_text)
            footer_content  = _resolve(raw_footer_text)

            # Parse hex color → discord.Color
            try:
                color_int = int(raw_embed_color.lstrip('#'), 16)
                embed_color = discord.Color(color_int)
            except Exception:
                embed_color = discord.Color.blue()

            # Create embed
            embed = discord.Embed(description=welcome_content, color=embed_color)
            embed.set_image(url="attachment://welcome.png")
            embed.set_footer(text=footer_content)

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
    


async def setup(bot):
    await bot.add_cog(WelcomeChannel(bot))