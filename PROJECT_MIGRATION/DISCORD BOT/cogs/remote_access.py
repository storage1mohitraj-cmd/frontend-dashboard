import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from admin_utils import is_bot_owner

class RemoteAccess(commands.Cog):
    def __init__(self, bot, conn):
        self.bot = bot
        self.conn = conn
        self.settings_db = sqlite3.connect('db/settings.sqlite', check_same_thread=False)
        self.settings_cursor = self.settings_db.cursor()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if not interaction.type == discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id == "remote_access":
            try:
                # Check if user is global admin
                self.settings_cursor.execute("SELECT is_initial FROM admin WHERE id = ?", (interaction.user.id,))
                result = self.settings_cursor.fetchone()
                
                if (not result or result[0] != 1) and not await is_bot_owner(self.bot, interaction.user.id):
                    await interaction.response.send_message(
                        "❌ Only global administrators can use Remote Access.",
                        ephemeral=True
                    )
                    return

                # Get all servers where the bot is present
                guilds = self.bot.guilds
                
                if not guilds:
                    await interaction.response.send_message(
                        "❌ Bot is not in any servers.",
                        ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title="🌐 Remote Access Control Panel",
                    description=(
                        "**Manage Channels Across All Servers**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 **Connected Servers:** `{len(guilds)}`\n"
                        f"👥 **Total Members:** `{sum(g.member_count for g in guilds)}`\n\n"
                        "**Available Actions:**\n"
                        "• 📋 View server channels\n"
                        "• ➕ Create new channels\n"
                        "• ✏️ Edit existing channels\n"
                        "• 🗑️ Delete channels\n"
                        "• 📨 Send messages to any channel\n"
                        "• 🎵 Play music remotely\n"
                        "• 🛡️ Start alliance monitoring\n"
                        "• 🔒 Manage permissions\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "Select a server below to begin managing its channels."
                    ),
                    color=0x00D9FF
                )
                
                embed.set_footer(
                    text=f"Remote Access • Requested by {interaction.user.display_name}",
                    icon_url=interaction.user.display_avatar.url
                )

                # Create server selection dropdown
                if len(guilds) <= 25:
                    # Single dropdown if 25 or fewer servers
                    options = [
                        discord.SelectOption(
                            label=f"{guild.name[:90]}",
                            value=str(guild.id),
                            description=f"Members: {guild.member_count} • Channels: {len(guild.channels)}",
                            emoji="🏰"
                        )
                        for guild in sorted(guilds, key=lambda g: g.name)
                    ]

                    select = discord.ui.Select(
                        placeholder="Select a server to manage...",
                        options=options,
                        custom_id="remote_access_server_select"
                    )

                    async def server_selected(select_interaction: discord.Interaction):
                        guild_id = int(select_interaction.data["values"][0])
                        guild = self.bot.get_guild(guild_id)
                        
                        if not guild:
                            await select_interaction.response.send_message(
                                "❌ Server not found.",
                                ephemeral=True
                            )
                            return
                        
                        await self.show_server_management(select_interaction, guild)

                    select.callback = server_selected

                    view = discord.ui.View(timeout=300)
                    view.add_item(select)
                    
                    # Add back button
                    back_button = discord.ui.Button(
                        label="◀ Back to Bot Operations",
                        emoji="🤖",
                        style=discord.ButtonStyle.secondary,
                        custom_id="bot_operations"
                    )
                    view.add_item(back_button)

                    await interaction.response.edit_message(embed=embed, view=view)
                
                else:
                    # Paginated server list for more than 25 servers
                    await self.show_paginated_servers(interaction, guilds)

            except Exception as e:
                print(f"Remote Access error: {e}")
                import traceback
                traceback.print_exc()
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An error occurred while loading Remote Access.",
                        ephemeral=True
                    )

    async def show_server_management(self, interaction: discord.Interaction, guild: discord.Guild):
        """Show management options for a specific server"""
        try:
            # Check bot permissions in this guild
            bot_member = guild.get_member(self.bot.user.id)
            has_manage_channels = bot_member.guild_permissions.manage_channels if bot_member else False
            
            # Get channel counts
            text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
            voice_channels = [c for c in guild.channels if isinstance(c, discord.VoiceChannel)]
            categories = [c for c in guild.channels if isinstance(c, discord.CategoryChannel)]
            
            embed = discord.Embed(
                title=f"🏰 Managing: {guild.name}",
                description=(
                    f"**Server Information**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👥 **Members:** `{guild.member_count}`\n"
                    f"📝 **Text Channels:** `{len(text_channels)}`\n"
                    f"🔊 **Voice Channels:** `{len(voice_channels)}`\n"
                    f"📁 **Categories:** `{len(categories)}`\n\n"
                    f"🔑 **Bot Permissions:**\n"
                    f"{'✅' if has_manage_channels else '❌'} Manage Channels\n"
                    f"{'✅' if bot_member.guild_permissions.administrator else '❌'} Administrator\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Select an action below to manage channels in this server."
                ),
                color=0x5865F2
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.set_footer(
                text=f"Server ID: {guild.id}",
                icon_url=interaction.user.display_avatar.url
            )

            view = discord.ui.View(timeout=300)
            
            # View Channels button
            view.add_item(discord.ui.Button(
                label="View Channels",
                emoji="📋",
                style=discord.ButtonStyle.primary,
                custom_id=f"remote_view_channels_{guild.id}",
                row=0
            ))
            
            # Create Channel button
            view.add_item(discord.ui.Button(
                label="Create Channel",
                emoji="➕",
                style=discord.ButtonStyle.success,
                custom_id=f"remote_create_channel_{guild.id}",
                disabled=not has_manage_channels,
                row=0
            ))
            
            # Edit Channel button
            view.add_item(discord.ui.Button(
                label="Edit Channel",
                emoji="✏️",
                style=discord.ButtonStyle.primary,
                custom_id=f"remote_edit_channel_{guild.id}",
                disabled=not has_manage_channels,
                row=0
            ))
            
            # Delete Channel button
            view.add_item(discord.ui.Button(
                label="Delete Channel",
                emoji="🗑️",
                style=discord.ButtonStyle.danger,
                custom_id=f"remote_delete_channel_{guild.id}",
                disabled=not has_manage_channels,
                row=1
            ))
            
            # Manage Permissions button
            view.add_item(discord.ui.Button(
                label="Manage Permissions",
                emoji="🔒",
                style=discord.ButtonStyle.primary,
                custom_id=f"remote_manage_perms_{guild.id}",
                disabled=not has_manage_channels,
                row=1
            ))
            
            
            # Send Message button
            view.add_item(discord.ui.Button(
                label="Send Message",
                emoji="📨",
                style=discord.ButtonStyle.success,
                custom_id=f"remote_send_message_{guild.id}",
                row=1
            ))
            
            
            # Play Music button (new feature)
            view.add_item(discord.ui.Button(
                label="Play Music",
                emoji="🎵",
                style=discord.ButtonStyle.success,
                custom_id=f"remote_play_music_{guild.id}",
                row=2
            ))
            
            # Remote Alliance Monitor button
            view.add_item(discord.ui.Button(
                label="Alliance Monitor",
                emoji="🛡️",
                style=discord.ButtonStyle.success,
                custom_id=f"remote_alliance_monitor_{guild.id}",
                row=2
            ))
            
            # Stop Alliance Monitor button
            view.add_item(discord.ui.Button(
                label="Stop Monitor",
                emoji="🛑",
                style=discord.ButtonStyle.danger,
                custom_id=f"remote_stop_alliance_monitor_{guild.id}",
                row=2
            ))
            
            # Back button
            view.add_item(discord.ui.Button(
                label="◀ Back to Server List",
                emoji="🌐",
                style=discord.ButtonStyle.secondary,
                custom_id="remote_access",
                row=3
            ))

            # Set up callbacks for buttons
            for item in view.children:
                if isinstance(item, discord.ui.Button) and item.custom_id:
                    if item.custom_id.startswith("remote_view_channels_"):
                        item.callback = lambda i, g=guild: self.view_channels(i, g)
                    elif item.custom_id.startswith("remote_create_channel_"):
                        item.callback = lambda i, g=guild: self.create_channel(i, g)
                    elif item.custom_id.startswith("remote_edit_channel_"):
                        item.callback = lambda i, g=guild: self.edit_channel(i, g)
                    elif item.custom_id.startswith("remote_delete_channel_"):
                        item.callback = lambda i, g=guild: self.delete_channel(i, g)
                    elif item.custom_id.startswith("remote_manage_perms_"):
                        item.callback = lambda i, g=guild: self.manage_permissions(i, g)
                    elif item.custom_id.startswith("remote_send_message_"):
                        item.callback = lambda i, g=guild: self.send_message(i, g)
                    elif item.custom_id.startswith("remote_play_music_"):
                        item.callback = lambda i, g=guild: self.play_music(i, g)
                    elif item.custom_id.startswith("remote_alliance_monitor_"):
                        item.callback = lambda i, g=guild: self.start_alliance_monitor(i, g)
                    elif item.custom_id.startswith("remote_stop_alliance_monitor_"):
                        item.callback = lambda i, g=guild: self.stop_alliance_monitor(i, g)

            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Show server management error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while loading server management.",
                ephemeral=True
            )

    async def view_channels(self, interaction: discord.Interaction, guild: discord.Guild):
        """View all channels in a server"""
        try:
            await interaction.response.defer()
            
            # Organize channels by category
            categories_data = {}
            uncategorized_channels = []
            
            for channel in sorted(guild.channels, key=lambda c: c.position):
                if isinstance(channel, discord.CategoryChannel):
                    categories_data[channel.id] = {
                        'name': channel.name,
                        'channels': []
                    }
                elif channel.category:
                    if channel.category.id not in categories_data:
                        categories_data[channel.category.id] = {
                            'name': channel.category.name,
                            'channels': []
                        }
                    categories_data[channel.category.id]['channels'].append(channel)
                elif not isinstance(channel, discord.CategoryChannel):
                    uncategorized_channels.append(channel)
            
            # Build embed
            embed = discord.Embed(
                title=f"📋 Channels in {guild.name}",
                description=f"Total channels: {len([c for c in guild.channels if not isinstance(c, discord.CategoryChannel)])}",
                color=0x5865F2
            )
            
            # Add uncategorized channels first
            if uncategorized_channels:
                channel_list = ""
                for channel in uncategorized_channels[:10]:  # Limit to prevent embed size issues
                    emoji = "📝" if isinstance(channel, discord.TextChannel) else "🔊" if isinstance(channel, discord.VoiceChannel) else "📢"
                    channel_list += f"{emoji} {channel.mention if isinstance(channel, discord.TextChannel) else channel.name}\n"
                
                if channel_list:
                    embed.add_field(
                        name="📌 Uncategorized",
                        value=channel_list,
                        inline=False
                    )
            
            # Add categorized channels
            for cat_id, cat_data in list(categories_data.items())[:5]:  # Limit categories
                if cat_data['channels']:
                    channel_list = ""
                    for channel in cat_data['channels'][:10]:
                        emoji = "📝" if isinstance(channel, discord.TextChannel) else "🔊" if isinstance(channel, discord.VoiceChannel) else "📢"
                        channel_list += f"{emoji} {channel.mention if isinstance(channel, discord.TextChannel) else channel.name}\n"
                    
                    if channel_list:
                        embed.add_field(
                            name=f"📁 {cat_data['name']}",
                            value=channel_list,
                            inline=False
                        )
            
            embed.set_footer(text=f"Server ID: {guild.id}")
            
            # Back button
            view = discord.ui.View(timeout=300)
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary,
                custom_id=f"back_to_server_{guild.id}"
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception as e:
            print(f"View channels error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                "❌ An error occurred while viewing channels.",
                ephemeral=True
            )

    async def create_channel(self, interaction: discord.Interaction, guild: discord.Guild):
        """Create a new channel in the server"""
        try:
            # Create modal for channel creation
            from discord.ui import Modal, TextInput
            
            class CreateChannelModal(Modal, title="Create New Channel"):
                channel_name = TextInput(
                    label="Channel Name",
                    placeholder="Enter channel name...",
                    required=True,
                    min_length=1,
                    max_length=100
                )
                
                channel_type = TextInput(
                    label="Channel Type (text/voice/category)",
                    placeholder="text",
                    required=True,
                    min_length=4,
                    max_length=8,
                    default="text"
                )
                
                channel_topic = TextInput(
                    label="Channel Topic (optional, text only)",
                    placeholder="Enter channel topic...",
                    required=False,
                    max_length=1024,
                    style=discord.TextStyle.paragraph
                )
                
                def __init__(self, parent_cog, target_guild):
                    super().__init__()
                    self.parent_cog = parent_cog
                    self.target_guild = target_guild
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        channel_type_str = self.channel_type.value.lower().strip()
                        name = self.channel_name.value.strip()
                        topic = self.channel_topic.value.strip() if self.channel_topic.value else None
                        
                        # Validate channel type
                        if channel_type_str not in ['text', 'voice', 'category']:
                            await modal_interaction.response.send_message(
                                "❌ Invalid channel type. Use: text, voice, or category",
                                ephemeral=True
                            )
                            return
                        
                        await modal_interaction.response.defer(ephemeral=True)
                        
                        # Create the channel
                        created_channel = None
                        if channel_type_str == 'text':
                            created_channel = await self.target_guild.create_text_channel(
                                name=name,
                                topic=topic
                            )
                        elif channel_type_str == 'voice':
                            created_channel = await self.target_guild.create_voice_channel(
                                name=name
                            )
                        elif channel_type_str == 'category':
                            created_channel = await self.target_guild.create_category(
                                name=name
                            )
                        
                        if created_channel:
                            success_embed = discord.Embed(
                                title="✅ Channel Created",
                                description=(
                                    f"**Channel Name:** {created_channel.mention if hasattr(created_channel, 'mention') else created_channel.name}\n"
                                    f"**Type:** {channel_type_str.title()}\n"
                                    f"**Server:** {self.target_guild.name}\n"
                                    f"**Channel ID:** `{created_channel.id}`"
                                ),
                                color=0x57F287
                            )
                            
                            await modal_interaction.followup.send(embed=success_embed, ephemeral=True)
                        else:
                            await modal_interaction.followup.send(
                                "❌ Failed to create channel.",
                                ephemeral=True
                            )
                    
                    except discord.Forbidden:
                        await modal_interaction.followup.send(
                            "❌ I don't have permission to create channels in this server.",
                            ephemeral=True
                        )
                    except Exception as e:
                        print(f"Create channel modal error: {e}")
                        await modal_interaction.followup.send(
                            f"❌ An error occurred: {str(e)}",
                            ephemeral=True
                        )
            
            modal = CreateChannelModal(self, guild)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            print(f"Create channel error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while creating the channel.",
                ephemeral=True
            )

    async def edit_channel(self, interaction: discord.Interaction, guild: discord.Guild):
        """Edit an existing channel in the server"""
        try:
            # Get all editable channels (text and voice, not categories)
            channels = [
                c for c in guild.channels 
                if isinstance(c, (discord.TextChannel, discord.VoiceChannel))
            ]
            
            if not channels:
                await interaction.response.send_message(
                    "❌ No editable channels found in this server.",
                    ephemeral=True
                )
                return
            
            # Create channel selection dropdown
            options = [
                discord.SelectOption(
                    label=f"{channel.name[:90]}",
                    value=str(channel.id),
                    description=f"{'Text' if isinstance(channel, discord.TextChannel) else 'Voice'} • Category: {channel.category.name if channel.category else 'None'}",
                    emoji="📝" if isinstance(channel, discord.TextChannel) else "🔊"
                )
                for channel in sorted(channels, key=lambda c: c.position)[:25]
            ]
            
            select = discord.ui.Select(
                placeholder="Select a channel to edit...",
                options=options,
                custom_id="select_channel_to_edit"
            )
            
            async def channel_selected(select_interaction: discord.Interaction):
                channel_id = int(select_interaction.data["values"][0])
                channel = guild.get_channel(channel_id)
                
                if not channel:
                    await select_interaction.response.send_message(
                        "❌ Channel not found.",
                        ephemeral=True
                    )
                    return
                
                # Create modal for editing
                from discord.ui import Modal, TextInput
                
                class EditChannelModal(Modal, title=f"Edit: {channel.name}"):
                    new_name = TextInput(
                        label="Channel Name",
                        placeholder="Enter new channel name...",
                        required=False,
                        min_length=1,
                        max_length=100,
                        default=channel.name
                    )
                    
                    new_topic = TextInput(
                        label="Channel Topic (text channels only)",
                        placeholder="Enter new topic...",
                        required=False,
                        max_length=1024,
                        style=discord.TextStyle.paragraph,
                        default=channel.topic if isinstance(channel, discord.TextChannel) and channel.topic else ""
                    )
                    
                    async def on_submit(self, modal_int: discord.Interaction):
                        try:
                            await modal_int.response.defer(ephemeral=True)
                            
                            changes = []
                            if self.new_name.value and self.new_name.value != channel.name:
                                await channel.edit(name=self.new_name.value)
                                changes.append(f"**Name:** `{channel.name}` → `{self.new_name.value}`")
                            
                            if isinstance(channel, discord.TextChannel) and self.new_topic.value != (channel.topic or ""):
                                await channel.edit(topic=self.new_topic.value if self.new_topic.value else None)
                                changes.append(f"**Topic:** Updated")
                            
                            if changes:
                                success_embed = discord.Embed(
                                    title="✅ Channel Updated",
                                    description=f"**Changes made to {channel.mention}:**\n" + "\n".join(changes),
                                    color=0x57F287
                                )
                                await modal_int.followup.send(embed=success_embed, ephemeral=True)
                            else:
                                await modal_int.followup.send(
                                    "ℹ️ No changes made.",
                                    ephemeral=True
                                )
                        
                        except discord.Forbidden:
                            await modal_int.followup.send(
                                "❌ I don't have permission to edit this channel.",
                                ephemeral=True
                            )
                        except Exception as e:
                            print(f"Edit channel error: {e}")
                            await modal_int.followup.send(
                                f"❌ An error occurred: {str(e)}",
                                ephemeral=True
                            )
                
                modal = EditChannelModal()
                await select_interaction.response.send_modal(modal)
            
            select.callback = channel_selected
            
            view = discord.ui.View(timeout=300)
            view.add_item(select)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            embed = discord.Embed(
                title=f"✏️ Edit Channel in {guild.name}",
                description="Select a channel to edit from the dropdown below.",
                color=0x5865F2
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Edit channel error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while editing the channel.",
                ephemeral=True
            )

    async def delete_channel(self, interaction: discord.Interaction, guild: discord.Guild):
        """Delete a channel from the server"""
        try:
            # Get all deletable channels
            channels = [
                c for c in guild.channels 
                if isinstance(c, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel))
            ]
            
            if not channels:
                await interaction.response.send_message(
                    "❌ No channels found in this server.",
                    ephemeral=True
                )
                return
            
            # Create channel selection dropdown
            options = [
                discord.SelectOption(
                    label=f"{channel.name[:90]}",
                    value=str(channel.id),
                    description=f"{'Text' if isinstance(channel, discord.TextChannel) else 'Voice' if isinstance(channel, discord.VoiceChannel) else 'Category'}",
                    emoji="📝" if isinstance(channel, discord.TextChannel) else "🔊" if isinstance(channel, discord.VoiceChannel) else "📁"
                )
                for channel in sorted(channels, key=lambda c: c.position)[:25]
            ]
            
            select = discord.ui.Select(
                placeholder="Select a channel to delete...",
                options=options,
                custom_id="select_channel_to_delete"
            )
            
            async def channel_selected(select_interaction: discord.Interaction):
                channel_id = int(select_interaction.data["values"][0])
                channel = guild.get_channel(channel_id)
                
                if not channel:
                    await select_interaction.response.send_message(
                        "❌ Channel not found.",
                        ephemeral=True
                    )
                    return
                
                # Confirmation prompt
                confirm_embed = discord.Embed(
                    title="⚠️ Confirm Channel Deletion",
                    description=(
                        f"Are you sure you want to delete this channel?\n\n"
                        f"**Channel:** {channel.mention if hasattr(channel, 'mention') else channel.name}\n"
                        f"**Type:** {channel.__class__.__name__}\n"
                        f"**Server:** {guild.name}\n\n"
                        f"⚠️ **This action cannot be undone!**"
                    ),
                    color=0xED4245
                )
                
                confirm_view = discord.ui.View(timeout=60)
                
                async def confirm_delete(confirm_int: discord.Interaction):
                    try:
                        channel_name = channel.name
                        await channel.delete()
                        
                        success_embed = discord.Embed(
                            title="✅ Channel Deleted",
                            description=f"Successfully deleted **{channel_name}** from **{guild.name}**",
                            color=0x57F287
                        )
                        
                        await confirm_int.response.edit_message(embed=success_embed, view=None)
                    
                    except discord.Forbidden:
                        await confirm_int.response.send_message(
                            "❌ I don't have permission to delete this channel.",
                            ephemeral=True
                        )
                    except Exception as e:
                        print(f"Delete channel error: {e}")
                        await confirm_int.response.send_message(
                            f"❌ An error occurred: {str(e)}",
                            ephemeral=True
                        )
                
                async def cancel_delete(cancel_int: discord.Interaction):
                    cancel_embed = discord.Embed(
                        title="❌ Deletion Cancelled",
                        description="Channel deletion has been cancelled.",
                        color=0x5865F2
                    )
                    await cancel_int.response.edit_message(embed=cancel_embed, view=None)
                
                confirm_button = discord.ui.Button(
                    label="Confirm Delete",
                    style=discord.ButtonStyle.danger,
                    emoji="🗑️"
                )
                confirm_button.callback = confirm_delete
                
                cancel_button = discord.ui.Button(
                    label="Cancel",
                    style=discord.ButtonStyle.secondary,
                    emoji="❌"
                )
                cancel_button.callback = cancel_delete
                
                confirm_view.add_item(confirm_button)
                confirm_view.add_item(cancel_button)
                
                await select_interaction.response.edit_message(embed=confirm_embed, view=confirm_view)
            
            select.callback = channel_selected
            
            view = discord.ui.View(timeout=300)
            view.add_item(select)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            embed = discord.Embed(
                title=f"🗑️ Delete Channel in {guild.name}",
                description="⚠️ Select a channel to delete. **This action cannot be undone!**",
                color=0xED4245
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Delete channel UI error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while preparing channel deletion.",
                ephemeral=True
            )


    async def send_message(self, interaction: discord.Interaction, guild: discord.Guild):
        """Send a message to any channel in the server"""
        try:
            # Get all text channels where bot can send messages
            channels = [
                c for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ]
            
            if not channels:
                await interaction.response.send_message(
                    "❌ No accessible text channels found in this server where I can send messages.",
                    ephemeral=True
                )
                return
            
            # Create channel selection dropdown
            options = [
                discord.SelectOption(
                    label=f"{channel.name[:90]}",
                    value=str(channel.id),
                    description=f"Category: {channel.category.name if channel.category else 'None'} • {channel.topic[:50] if channel.topic else 'No topic'}",
                    emoji="📝"
                )
                for channel in sorted(channels, key=lambda c: c.position)[:25]
            ]
            
            select = discord.ui.Select(
                placeholder="Select a channel to send message...",
                options=options,
                custom_id="select_channel_for_message"
            )
            
            async def channel_selected(select_interaction: discord.Interaction):
                channel_id = int(select_interaction.data["values"][0])
                channel = guild.get_channel(channel_id)
                
                if not channel:
                    await select_interaction.response.send_message(
                        "❌ Channel not found.",
                        ephemeral=True
                    )
                    return
                
                # Show message type selection
                await self.show_message_type_selection(select_interaction, channel, guild)
            
            select.callback = channel_selected
            
            view = discord.ui.View(timeout=300)
            view.add_item(select)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            embed = discord.Embed(
                title=f"📨 Send Message in {guild.name}",
                description=(
                    "**Select a channel to send a message**\n\n"
                    "You'll be able to:\n"
                    "• Send plain text messages\n"
                    "• Create rich embeds\n"
                    "• Send messages with custom formatting\n\n"
                    "Select a channel from the dropdown below."
                ),
                color=0x57F287
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Send message error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while preparing to send message.",
                ephemeral=True
            )

    async def show_message_type_selection(self, interaction: discord.Interaction, channel: discord.TextChannel, guild: discord.Guild):
        """Show message type selection (plain text or embed)"""
        try:
            embed = discord.Embed(
                title="📨 Choose Message Type",
                description=(
                    f"**Sending to:** {channel.mention}\n"
                    f"**Server:** {guild.name}\n\n"
                    "Select the type of message you want to send:"
                ),
                color=0x5865F2
            )
            
            view = discord.ui.View(timeout=300)
            
            # Plain Text button
            plain_button = discord.ui.Button(
                label="Plain Text Message",
                emoji="📝",
                style=discord.ButtonStyle.primary,
                custom_id="send_plain_text"
            )
            
            async def send_plain_text(button_int: discord.Interaction):
                from discord.ui import Modal, TextInput
                
                class PlainMessageModal(Modal, title=f"Send to #{channel.name}"):
                    message_content = TextInput(
                        label="Message Content",
                        placeholder="Type your message here...",
                        required=True,
                        max_length=2000,
                        style=discord.TextStyle.paragraph
                    )
                    
                    async def on_submit(self, modal_int: discord.Interaction):
                        try:
                            await modal_int.response.defer(ephemeral=True)
                            
                            # Send the message
                            sent_message = await channel.send(self.message_content.value)
                            
                            success_embed = discord.Embed(
                                title="✅ Message Sent",
                                description=(
                                    f"**Channel:** {channel.mention}\n"
                                    f"**Server:** {guild.name}\n"
                                    f"**Message ID:** `{sent_message.id}`\n\n"
                                    f"**Content Preview:**\n{self.message_content.value[:500]}"
                                ),
                                color=0x57F287
                            )
                            
                            success_embed.add_field(
                                name="🔗 Jump to Message",
                                value=f"[Click here]({sent_message.jump_url})",
                                inline=False
                            )
                            
                            await modal_int.followup.send(embed=success_embed, ephemeral=True)
                            
                        except discord.Forbidden:
                            await modal_int.followup.send(
                                "❌ I don't have permission to send messages in this channel.",
                                ephemeral=True
                            )
                        except Exception as e:
                            print(f"Send message error: {e}")
                            await modal_int.followup.send(
                                f"❌ An error occurred: {str(e)}",
                                ephemeral=True
                            )
                
                modal = PlainMessageModal()
                await button_int.response.send_modal(modal)
            
            plain_button.callback = send_plain_text
            view.add_item(plain_button)
            
            # Embed Message button
            embed_button = discord.ui.Button(
                label="Embed Message",
                emoji="🎨",
                style=discord.ButtonStyle.primary,
                custom_id="send_embed"
            )
            
            async def send_embed_message(button_int: discord.Interaction):
                from discord.ui import Modal, TextInput
                
                class EmbedMessageModal(Modal, title=f"Embed for #{channel.name}"):
                    embed_title = TextInput(
                        label="Embed Title",
                        placeholder="Enter embed title...",
                        required=True,
                        max_length=256
                    )
                    
                    embed_description = TextInput(
                        label="Embed Description",
                        placeholder="Enter embed description...",
                        required=True,
                        max_length=4000,
                        style=discord.TextStyle.paragraph
                    )
                    
                    embed_color = TextInput(
                        label="Embed Color (hex, e.g., 5865F2)",
                        placeholder="5865F2",
                        required=False,
                        max_length=6,
                        default="5865F2"
                    )
                    
                    footer_text = TextInput(
                        label="Footer Text (optional)",
                        placeholder="Enter footer text...",
                        required=False,
                        max_length=2048
                    )
                    
                    async def on_submit(self, modal_int: discord.Interaction):
                        try:
                            await modal_int.response.defer(ephemeral=True)
                            
                            # Parse color
                            try:
                                color_hex = self.embed_color.value.strip().lstrip('#')
                                color = int(color_hex, 16) if color_hex else 0x5865F2
                            except:
                                color = 0x5865F2
                            
                            # Create embed
                            message_embed = discord.Embed(
                                title=self.embed_title.value,
                                description=self.embed_description.value,
                                color=color
                            )
                            
                            if self.footer_text.value:
                                message_embed.set_footer(text=self.footer_text.value)
                            
                            # Send the embed
                            sent_message = await channel.send(embed=message_embed)
                            
                            success_embed = discord.Embed(
                                title="✅ Embed Sent",
                                description=(
                                    f"**Channel:** {channel.mention}\n"
                                    f"**Server:** {guild.name}\n"
                                    f"**Message ID:** `{sent_message.id}`\n\n"
                                    f"**Title:** {self.embed_title.value}"
                                ),
                                color=0x57F287
                            )
                            
                            success_embed.add_field(
                                name="🔗 Jump to Message",
                                value=f"[Click here]({sent_message.jump_url})",
                                inline=False
                            )
                            
                            await modal_int.followup.send(embed=success_embed, ephemeral=True)
                            
                        except discord.Forbidden:
                            await modal_int.followup.send(
                                "❌ I don't have permission to send messages in this channel.",
                                ephemeral=True
                            )
                        except Exception as e:
                            print(f"Send embed error: {e}")
                            await modal_int.followup.send(
                                f"❌ An error occurred: {str(e)}",
                                ephemeral=True
                            )
                
                modal = EmbedMessageModal()
                await button_int.response.send_modal(modal)
            
            embed_button.callback = send_embed_message
            view.add_item(embed_button)
            
            # Announcement button (with @everyone mention if bot has permission)
            announcement_button = discord.ui.Button(
                label="Announcement",
                emoji="📢",
                style=discord.ButtonStyle.danger,
                custom_id="send_announcement"
            )
            
            async def send_announcement(button_int: discord.Interaction):
                from discord.ui import Modal, TextInput
                
                class AnnouncementModal(Modal, title="Create Announcement"):
                    announcement_title = TextInput(
                        label="Announcement Title",
                        placeholder="IMPORTANT ANNOUNCEMENT",
                        required=True,
                        max_length=256
                    )
                    
                    announcement_content = TextInput(
                        label="Announcement Content",
                        placeholder="Enter your announcement message...",
                        required=True,
                        max_length=4000,
                        style=discord.TextStyle.paragraph
                    )
                    
                    mention_role = TextInput(
                        label="Mention (@everyone/@here/role name/empty)",
                        placeholder="@everyone",
                        required=False,
                        max_length=100,
                        default="@everyone"
                    )
                    
                    async def on_submit(self, modal_int: discord.Interaction):
                        try:
                            await modal_int.response.defer(ephemeral=True)
                            
                            # Create announcement embed
                            announcement_embed = discord.Embed(
                                title=f"📢 {self.announcement_title.value}",
                                description=self.announcement_content.value,
                                color=0xED4245
                            )
                            
                            announcement_embed.set_footer(
                                text=f"Sent by {modal_int.user.display_name}",
                                icon_url=modal_int.user.display_avatar.url
                            )
                            
                            # Prepare mention
                            mention_text = ""
                            if self.mention_role.value:
                                mention_value = self.mention_role.value.strip()
                                if mention_value.lower() == "@everyone":
                                    mention_text = "@everyone"
                                elif mention_value.lower() == "@here":
                                    mention_text = "@here"
                                else:
                                    # Try to find role
                                    role = discord.utils.get(guild.roles, name=mention_value)
                                    if role:
                                        mention_text = role.mention
                            
                            # Send the announcement
                            try:
                                if mention_text in ["@everyone", "@here"]:
                                    sent_message = await channel.send(
                                        content=mention_text,
                                        embed=announcement_embed,
                                        allowed_mentions=discord.AllowedMentions(everyone=True)
                                    )
                                else:
                                    content = mention_text if mention_text else None
                                    sent_message = await channel.send(
                                        content=content,
                                        embed=announcement_embed
                                    )
                                
                                success_embed = discord.Embed(
                                    title="✅ Announcement Posted",
                                    description=(
                                        f"**Channel:** {channel.mention}\n"
                                        f"**Server:** {guild.name}\n"
                                        f"**Mention:** {mention_text if mention_text else 'None'}\n"
                                        f"**Message ID:** `{sent_message.id}`"
                                    ),
                                    color=0x57F287
                                )
                                
                                success_embed.add_field(
                                    name="🔗 Jump to Announcement",
                                    value=f"[Click here]({sent_message.jump_url})",
                                    inline=False
                                )
                                
                                await modal_int.followup.send(embed=success_embed, ephemeral=True)
                                
                            except discord.Forbidden:
                                await modal_int.followup.send(
                                    "❌ I don't have permission to send announcements or mention everyone/here.",
                                    ephemeral=True
                                )
                            
                        except Exception as e:
                            print(f"Send announcement error: {e}")
                            await modal_int.followup.send(
                                f"❌ An error occurred: {str(e)}",
                                ephemeral=True
                            )
                
                modal = AnnouncementModal()
                await button_int.response.send_modal(modal)
            
            announcement_button.callback = send_announcement
            view.add_item(announcement_button)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back to Channel Selection",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.send_message(i, guild)
            view.add_item(back_button)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Show message type error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while loading message options.",
                ephemeral=True
            )


    async def play_music(self, interaction: discord.Interaction, guild: discord.Guild):
        """Play music in a voice channel on the selected server"""
        try:
            # Get the music cog
            music_cog = self.bot.get_cog('Music')
            
            if not music_cog:
                await interaction.response.send_message(
                    "❌ Music system is not loaded.",
                    ephemeral=True
                )
                return
            
            # Get all voice channels in the guild
            voice_channels = guild.voice_channels
            
            if not voice_channels:
                await interaction.response.send_message(
                    "❌ No voice channels found in this server.",
                    ephemeral=True
                )
                return
            
            # Check bot permissions
            bot_member = guild.get_member(self.bot.user.id)
            accessible_channels = [
                vc for vc in voice_channels
                if vc.permissions_for(bot_member).connect and vc.permissions_for(bot_member).speak
            ]
            
            if not accessible_channels:
                await interaction.response.send_message(
                    "❌ Bot doesn't have permission to connect or speak in any voice channels.",
                    ephemeral=True
                )
                return
            
            # Create voice channel selection dropdown
            options = [
                discord.SelectOption(
                    label=f"{vc.name[:90]}",
                    value=str(vc.id),
                    description=f"Members: {len(vc.members)} • Category: {vc.category.name if vc.category else 'None'}",
                    emoji="🔊"
                )
                for vc in sorted(accessible_channels, key=lambda c: c.position)[:25]
            ]
            
            select = discord.ui.Select(
                placeholder="Select a voice channel to play music...",
                options=options,
                custom_id="select_voice_channel_for_music"
            )
            
            async def voice_channel_selected(select_interaction: discord.Interaction):
                channel_id = int(select_interaction.data["values"][0])
                voice_channel = guild.get_channel(channel_id)
                
                if not voice_channel:
                    await select_interaction.response.send_message(
                        "❌ Voice channel not found.",
                        ephemeral=True
                    )
                    return
                
                # Show song search modal
                from discord.ui import Modal, TextInput
                
                class SongSearchModal(Modal, title=f"Play in {voice_channel.name}"):
                    song_query = TextInput(
                        label="Song Name or URL",
                        placeholder="Enter song name, artist, or YouTube/Spotify URL...",
                        required=True,
                        max_length=500,
                        style=discord.TextStyle.paragraph
                    )
                    
                    def __init__(self, parent_cog, target_voice_channel, target_guild):
                        super().__init__()
                        self.parent_cog = parent_cog
                        self.voice_channel = target_voice_channel
                        self.guild = target_guild
                    
                    async def on_submit(self, modal_int: discord.Interaction):
                        try:
                            await modal_int.response.defer(ephemeral=True)
                            
                            query = self.song_query.value.strip()
                            
                            # Try to connect to voice channel
                            try:
                                # Import wavelink for music playback
                                import wavelink
                                
                                # Import CustomPlayer from music cog
                                from cogs.music import CustomPlayer
                                
                                # Check if bot is already connected to a voice channel in this guild
                                player = self.guild.voice_client
                                
                                if player:
                                    # Bot is already connected
                                    if player.channel.id != self.voice_channel.id:
                                        # Move to the target channel
                                        await player.move_to(self.voice_channel)
                                    # Player already exists, we'll use it
                                else:
                                    # Bot is not connected, connect now
                                    player = await self.voice_channel.connect(cls=CustomPlayer, self_deaf=True)
                                
                                # Verify we have a valid player
                                if not player:
                                    await modal_int.followup.send(
                                        "❌ Failed to establish voice connection.",
                                        ephemeral=True
                                    )
                                    return
                                
                                # Set text channel for the player
                                if hasattr(player, 'text_channel'):
                                    player.text_channel = modal_int.channel
                                
                                # Get the music cog
                                music_cog = self.parent_cog.bot.get_cog('Music')
                                
                                if not music_cog:
                                    await modal_int.followup.send(
                                        "❌ Music system not available.",
                                        ephemeral=True
                                    )
                                    return
                                
                                # Try to play the song
                                try:
                                    # Search for tracks
                                    tracks = await wavelink.Playable.search(query)
                                    
                                    if not tracks:
                                        await modal_int.followup.send(
                                            f"❌ No results found for: `{query}`",
                                            ephemeral=True
                                        )
                                        return
                                    
                                    track = tracks[0]
                                    
                                    # Add track to queue
                                    await player.queue.put_wait(track)
                                    
                                    # If not playing, start playback
                                    if not player.playing:
                                        await player.play(player.queue.get())
                                    
                                    # Create success embed
                                    success_embed = discord.Embed(
                                        title="🎵 Music Playing Remotely",
                                        description=(
                                            f"**Song:** {track.title}\n"
                                            f"**Artist:** {track.author}\n"
                                            f"**Duration:** {self.format_duration(track.length)}\n"
                                            f"**Voice Channel:** {self.voice_channel.mention}\n"
                                            f"**Server:** {self.guild.name}\n\n"
                                            f"{'▶️ Now Playing' if player.playing and not player.queue.is_empty else '📋 Added to Queue'}"
                                        ),
                                        color=0x57F287
                                    )
                                    
                                    if track.artwork:
                                        success_embed.set_thumbnail(url=track.artwork)
                                    
                                    success_embed.set_footer(
                                        text=f"Requested by {modal_int.user.display_name}",
                                        icon_url=modal_int.user.display_avatar.url
                                    )
                                    
                                    await modal_int.followup.send(embed=success_embed, ephemeral=True)
                                    
                                except Exception as play_error:
                                    print(f"Music playback error: {play_error}")
                                    import traceback
                                    traceback.print_exc()
                                    await modal_int.followup.send(
                                        f"❌ Error playing music: {str(play_error)}",
                                        ephemeral=True
                                    )
                            
                            except discord.Forbidden:
                                await modal_int.followup.send(
                                    "❌ Bot doesn't have permission to connect to this voice channel.",
                                    ephemeral=True
                                )
                            except Exception as connect_error:
                                print(f"Voice connect error: {connect_error}")
                                await modal_int.followup.send(
                                    f"❌ Error connecting to voice channel: {str(connect_error)}",
                                    ephemeral=True
                                )
                        
                        except Exception as e:
                            print(f"Song search error: {e}")
                            import traceback
                            traceback.print_exc()
                            await modal_int.followup.send(
                                f"❌ An error occurred: {str(e)}",
                                ephemeral=True
                            )
                    
                    def format_duration(self, milliseconds):
                        """Format duration from milliseconds to MM:SS"""
                        seconds = milliseconds // 1000
                        minutes = seconds // 60
                        seconds = seconds % 60
                        return f"{minutes}:{seconds:02d}"
                
                modal = SongSearchModal(self, voice_channel, guild)
                await select_interaction.response.send_modal(modal)
            
            select.callback = voice_channel_selected
            
            view = discord.ui.View(timeout=300)
            view.add_item(select)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            embed = discord.Embed(
                title=f"🎵 Play Music in {guild.name}",
                description=(
                    "**Remote Music Control**\n\n"
                    "Select a voice channel where you want to play music.\n\n"
                    "**Supported:**\n"
                    "• YouTube URLs\n"
                    "• Spotify URLs\n"
                    "• Song names\n"
                    "• Artist + Song search\n\n"
                    "The bot will connect to the voice channel and play your requested song!"
                ),
                color=0x5865F2
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Play music error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while setting up music playback.",
                ephemeral=True
            )


    async def start_alliance_monitor(self, interaction: discord.Interaction, guild: discord.Guild):
        """Start alliance monitoring for the selected server"""
        try:
            # Get the alliance cog
            alliance_cog = self.bot.get_cog('Alliance')
            
            if not alliance_cog:
                await interaction.response.send_message(
                    "❌ Alliance system is not loaded.",
                    ephemeral=True
                )
                return
            
            # Import ServerAllianceAdapter to get available alliances
            try:
                from db.mongo_adapters import ServerAllianceAdapter, mongo_enabled
            except:
                await interaction.response.send_message(
                    "❌ MongoDB not enabled. Alliance monitoring requires MongoDB.",
                    ephemeral=True
                )
                return
            
            # Get the current server's assigned alliance
            current_alliance = ServerAllianceAdapter.get_alliance(guild.id)
            
            # Get all available alliances from the alliance database
            available_alliances = []
            try:
                # Import the database connection function
                from db_utils import get_db_connection
                
                with get_db_connection('alliance.sqlite') as alliance_db:
                    cursor = alliance_db.cursor()
                    cursor.execute("SELECT alliance_id, name FROM alliance_list ORDER BY name")
                    available_alliances = cursor.fetchall()
            except Exception as db_error:
                print(f"Error fetching alliances: {db_error}")
            
            if not available_alliances:
                await interaction.response.send_message(
                    "❌ No alliances found in the database.\n\nPlease ensure alliances have been synced first.",
                    ephemeral=True
                )
                return
            
            # Create alliance selection dropdown
            alliance_options = [
                discord.SelectOption(
                    label=f"{name[:90]}",
                    value=str(alliance_id),
                    description=f"ID: {alliance_id}" + (" (Currently assigned)" if str(alliance_id) == str(current_alliance) else ""),
                    emoji="🏰"
                )
                for alliance_id, name in available_alliances[:25]
            ]
            
            alliance_select = discord.ui.Select(
                placeholder="Select an alliance to monitor...",
                options=alliance_options,
                custom_id="select_alliance_to_monitor"
            )
            
            async def alliance_selected(select_interaction: discord.Interaction):
                selected_alliance_id = select_interaction.data["values"][0]
                
                # Get alliance name
                alliance_name = "Unknown Alliance"
                try:
                    from db_utils import get_db_connection
                    with get_db_connection('alliance.sqlite') as alliance_db:
                        cursor = alliance_db.cursor()
                        cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (selected_alliance_id,))
                        result = cursor.fetchone()
                        if result:
                            alliance_name = result[0]
                except:
                    pass
                
                # Now show channel selection for this alliance
                text_channels = [c for c in guild.text_channels if c.permissions_for(guild.me).send_messages]
                
                if not text_channels:
                    await select_interaction.response.send_message(
                        "❌ No accessible text channels found in this server.",
                        ephemeral=True
                    )
                    return
                
                # Create channel selection dropdown
                channel_options = [
                    discord.SelectOption(
                        label=f"{channel.name[:90]}",
                        value=str(channel.id),
                        description=f"Category: {channel.category.name if channel.category else 'None'}",
                        emoji="📝"
                    )
                    for channel in sorted(text_channels, key=lambda c: c.position)[:25]
                ]
                
                channel_select = discord.ui.Select(
                    placeholder="Select channel for monitoring updates...",
                    options=channel_options,
                    custom_id="select_monitor_channel"
                )
                
                async def channel_selected(channel_interaction: discord.Interaction):
                    channel_id = int(channel_interaction.data["values"][0])
                    monitor_channel = guild.get_channel(channel_id)
                    
                    if not monitor_channel:
                        await channel_interaction.response.send_message(
                            "❌ Channel not found.",
                            ephemeral=True
                        )
                        return
                    
                    # Save monitoring configuration
                    try:
                        await channel_interaction.response.defer(ephemeral=True)
                        
                        # Import database utilities
                        from db_utils import get_db_connection
                        
                        # Get member count for this alliance
                        members = []
                        if hasattr(alliance_cog, '_get_monitoring_members'):
                            members = alliance_cog._get_monitoring_members(selected_alliance_id)
                        member_count = len(members) if members else 0
                        
                        # Save to database
                        with get_db_connection('settings.sqlite') as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT OR REPLACE INTO alliance_monitoring 
                                (guild_id, alliance_id, channel_id, enabled, updated_at)
                                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                            """, (guild.id, selected_alliance_id, channel_id))
                            conn.commit()
                        
                        # Save to MongoDB if enabled
                        if mongo_enabled():
                            try:
                                from db.mongo_adapters import AllianceMonitoringAdapter
                                AllianceMonitoringAdapter.upsert_monitor(guild.id, selected_alliance_id, channel_id, enabled=1)
                            except:
                                pass
                        
                        # Initialize member history if available
                        if members:
                            with get_db_connection('settings.sqlite') as conn:
                                cursor = conn.cursor()
                                for fid, nickname, furnace_lv in members:
                                    cursor.execute("""
                                        INSERT OR REPLACE INTO member_history 
                                        (fid, alliance_id, nickname, furnace_lv, last_checked)
                                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                                    """, (str(fid), selected_alliance_id, nickname, furnace_lv))
                                conn.commit()
                        
                        # Create success embed
                        success_embed = discord.Embed(
                            title="✅ Alliance Monitoring Started",
                            description=(
                                f"**Alliance:** {alliance_name}\n"
                                f"**Alliance ID:** `{selected_alliance_id}`\n"
                                f"**Channel:** {monitor_channel.mention}\n"
                                f"**Server:** {guild.name}\n"
                                f"**Members Tracked:** {member_count}\n\n"
                                f"**Monitoring Active** ✅\n"
                                f"The system will check for changes every 4 minutes.\n\n"
                                f"**Tracked Changes:**\n"
                                f"• 👤 Name changes\n"
                                f"• 🔥 Furnace level changes\n"
                                f"• 🖼️ Avatar changes"
                            ),
                            color=0x57F287
                        )
                        
                        await channel_interaction.followup.send(embed=success_embed, ephemeral=True)
                        
                        # Send notification to the monitoring channel
                        try:
                            channel_embed = discord.Embed(
                                title="🛡️ Alliance Monitoring Started",
                                description=(
                                    f"Now monitoring **{alliance_name}** (ID: `{selected_alliance_id}`)\n\n"
                                    f"**Check Frequency:** Every 4 minutes\n"
                                    f"**Started by:** {channel_interaction.user.mention}\n\n"
                                    f"Updates will be posted here automatically."
                                ),
                                color=0x5865F2
                            )
                            await monitor_channel.send(embed=channel_embed)
                        except:
                            pass  # Not critical if this fails
                        
                        print(f"Remote alliance monitoring configured: Alliance {selected_alliance_id} in channel {channel_id} for guild {guild.id}")
                        
                    except Exception as save_error:
                        print(f"Error saving monitoring config: {save_error}")
                        import traceback
                        traceback.print_exc()
                        await channel_interaction.followup.send(
                            f"❌ Error saving monitoring configuration: {str(save_error)}",
                            ephemeral=True
                        )
                
                channel_select.callback = channel_selected
                
                channel_view = discord.ui.View(timeout=300)
                channel_view.add_item(channel_select)
                
                # Back button
                back_button = discord.ui.Button(
                    label="◀ Back",
                    emoji="🏰",
                    style=discord.ButtonStyle.secondary
                )
                back_button.callback = lambda i: self.show_server_management(i, guild)
                channel_view.add_item(back_button)
                
                channel_embed = discord.Embed(
                    title=f"🛡️ Monitor: {alliance_name}",
                    description=(
                        f"**Selected Alliance:** {alliance_name}\n"
                        f"**Alliance ID:** `{selected_alliance_id}`\n\n"
                        "Now select the channel where monitoring updates should be posted.\n\n"
                        "**What will be monitored:**\n"
                        "• 👤 Player name changes\n"
                        "• 🔥 Furnace level changes\n"
                        "• 🖼️ Avatar changes\n\n"
                        "Select a channel from the dropdown below."
                    ),
                    color=0x5865F2
                )
                
                await select_interaction.response.edit_message(embed=channel_embed, view=channel_view)
            
            alliance_select.callback = alliance_selected
            
            view = discord.ui.View(timeout=300)
            view.add_item(alliance_select)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            embed = discord.Embed(
                title=f"🛡️ Alliance Monitor for {guild.name}",
                description=(
                    "**Remote Alliance Monitoring Setup**\n\n"
                    "**Step 1:** Select the alliance you want to monitor\n"
                    "**Step 2:** Choose the channel for updates (next screen)\n\n"
                    "**Features:**\n"
                    "• Monitor alliance member changes\n"
                    "• Track name, furnace, and avatar changes\n"
                    "• Automatic updates every 4 minutes\n"
                    "• Real-time notifications\n\n"
                    "Select an alliance from the dropdown below to continue."
                ),
                color=0x5865F2
            )
            
            if current_alliance:
                embed.add_field(
                    name="📌 Current Server Alliance",
                    value=f"This server is currently assigned to alliance `{current_alliance}`",
                    inline=False
                )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Start alliance monitor error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while setting up alliance monitoring.",
                ephemeral=True
            )

    async def stop_alliance_monitor(self, interaction: discord.Interaction, guild: discord.Guild):
        """Stop alliance monitoring for the selected server"""
        try:
            # Get the alliance cog
            alliance_cog = self.bot.get_cog('Alliance')
            
            if not alliance_cog:
                await interaction.response.send_message(
                    "❌ Alliance system is not loaded.",
                    ephemeral=True
                )
                return
            
            # Import database utilities
            try:
                from db_utils import get_db_connection
                from db.mongo_adapters import mongo_enabled, AllianceMonitoringAdapter
            except:
                await interaction.response.send_message(
                    "❌ Database utilities not available.",
                    ephemeral=True
                )
                return
            
            # Get active monitors for this guild
            active_monitors = []
            try:
                with get_db_connection('settings.sqlite') as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT alliance_id, channel_id, enabled
                        FROM alliance_monitoring
                        WHERE guild_id = ? AND enabled = 1
                    """, (guild.id,))
                    active_monitors = cursor.fetchall()
            except Exception as db_error:
                print(f"Error fetching active monitors: {db_error}")
            
            if not active_monitors:
                await interaction.response.send_message(
                    "❌ No active alliance monitors found for this server.\n\nUse the **Alliance Monitor** button to start monitoring an alliance.",
                    ephemeral=True
                )
                return
            
            # Get alliance names for the monitors
            monitor_options = []
            for alliance_id, channel_id, enabled in active_monitors:
                alliance_name = "Unknown Alliance"
                channel_name = "Unknown Channel"
                
                # Get alliance name
                try:
                    with get_db_connection('alliance.sqlite') as alliance_db:
                        cursor = alliance_db.cursor()
                        cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                        result = cursor.fetchone()
                        if result:
                            alliance_name = result[0]
                except:
                    pass
                
                # Get channel name
                try:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        channel_name = channel.name
                except:
                    pass
                
                monitor_options.append(
                    discord.SelectOption(
                        label=f"{alliance_name[:50]}",
                        value=f"{alliance_id}_{channel_id}",
                        description=f"Channel: #{channel_name[:40]} • ID: {alliance_id}",
                        emoji="🛡️"
                    )
                )
            
            # Create dropdown for monitor selection
            if not monitor_options:
                await interaction.response.send_message(
                    "❌ No valid monitors found to stop.",
                    ephemeral=True
                )
                return
            
            monitor_select = discord.ui.Select(
                placeholder="Select a monitor to stop...",
                options=monitor_options[:25],  # Discord limit
                custom_id="select_monitor_to_stop"
            )
            
            async def monitor_selected(select_interaction: discord.Interaction):
                selected_value = select_interaction.data["values"][0]
                alliance_id, channel_id = selected_value.split("_")
                alliance_id = int(alliance_id)
                channel_id = int(channel_id)
                
                # Get details for confirmation
                alliance_name = "Unknown Alliance"
                try:
                    with get_db_connection('alliance.sqlite') as alliance_db:
                        cursor = alliance_db.cursor()
                        cursor.execute("SELECT name FROM alliance_list WHERE alliance_id = ?", (alliance_id,))
                        result = cursor.fetchone()
                        if result:
                            alliance_name = result[0]
                except:
                    pass
                
                channel = guild.get_channel(channel_id)
                channel_mention = channel.mention if channel else f"<#{channel_id}>"
                
                # Create confirmation view
                confirm_view = discord.ui.View(timeout=60)
                
                async def confirm_stop(button_int: discord.Interaction):
                    try:
                        await button_int.response.defer(ephemeral=True)
                        
                        # Stop monitoring by setting enabled = 0
                        with get_db_connection('settings.sqlite') as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE alliance_monitoring 
                                SET enabled = 0, updated_at = CURRENT_TIMESTAMP
                                WHERE guild_id = ? AND alliance_id = ? AND channel_id = ?
                            """, (guild.id, alliance_id, channel_id))
                            conn.commit()
                        
                        # Update MongoDB if enabled
                        if mongo_enabled():
                            try:
                                AllianceMonitoringAdapter.upsert_monitor(guild.id, alliance_id, channel_id, enabled=0)
                            except:
                                pass
                        
                        # Create success embed
                        success_embed = discord.Embed(
                            title="✅ Alliance Monitoring Stopped",
                            description=(
                                f"**Alliance:** {alliance_name}\n"
                                f"**Alliance ID:** `{alliance_id}`\n"
                                f"**Channel:** {channel_mention}\n"
                                f"**Server:** {guild.name}\n\n"
                                f"**Status:** ❌ Monitoring Disabled\n\n"
                                f"You can restart monitoring at any time using the **Alliance Monitor** button."
                            ),
                            color=0xED4245  # Red color
                        )
                        
                        await button_int.followup.send(embed=success_embed, ephemeral=True)
                        
                        # Send notification to the channel
                        if channel:
                            try:
                                channel_embed = discord.Embed(
                                    title="🛑 Alliance Monitoring Stopped",
                                    description=(
                                        f"Monitoring for **{alliance_name}** (ID: `{alliance_id}`) has been stopped.\n\n"
                                        f"**Stopped by:** {button_int.user.mention}\n\n"
                                        f"To restart monitoring, use the `/settings` command or Remote Access."
                                    ),
                                    color=0xED4245
                                )
                                await channel.send(embed=channel_embed)
                            except:
                                pass  # Not critical if this fails
                        
                        print(f"Remote alliance monitoring stopped: Alliance {alliance_id} in channel {channel_id} for guild {guild.id}")
                        
                    except Exception as stop_error:
                        print(f"Error stopping monitor: {stop_error}")
                        import traceback
                        traceback.print_exc()
                        await button_int.followup.send(
                            f"❌ Error stopping monitor: {str(stop_error)}",
                            ephemeral=True
                        )
                
                async def cancel_stop(button_int: discord.Interaction):
                    cancel_embed = discord.Embed(
                        title="❌ Action Cancelled",
                        description="Alliance monitoring has not been stopped.",
                        color=0x95A5A6
                    )
                    await button_int.response.edit_message(embed=cancel_embed, view=None)
                
                # Add buttons to confirmation view
                confirm_button = discord.ui.Button(
                    label="Stop Monitoring",
                    emoji="🛑",
                    style=discord.ButtonStyle.danger
                )
                confirm_button.callback = confirm_stop
                
                cancel_button = discord.ui.Button(
                    label="Cancel",
                    emoji="❌",
                    style=discord.ButtonStyle.secondary
                )
                cancel_button.callback = cancel_stop
                
                confirm_view.add_item(confirm_button)
                confirm_view.add_item(cancel_button)
                
                # Create confirmation embed
                confirm_embed = discord.Embed(
                    title="⚠️ Confirm Stop Monitoring",
                    description=(
                        f"Are you sure you want to stop monitoring this alliance?\n\n"
                        f"**Alliance:** {alliance_name}\n"
                        f"**Alliance ID:** `{alliance_id}`\n"
                        f"**Channel:** {channel_mention}\n"
                        f"**Server:** {guild.name}\n\n"
                        f"**Note:** You can restart monitoring anytime."
                    ),
                    color=0xF39C12  # Orange warning color
                )
                
                await select_interaction.response.edit_message(embed=confirm_embed, view=confirm_view)
            
            monitor_select.callback = monitor_selected
            
            view = discord.ui.View(timeout=300)
            view.add_item(monitor_select)
            
            # Back button
            back_button = discord.ui.Button(
                label="◀ Back",
                emoji="🏰",
                style=discord.ButtonStyle.secondary
            )
            back_button.callback = lambda i: self.show_server_management(i, guild)
            view.add_item(back_button)
            
            embed = discord.Embed(
                title=f"🛑 Stop Alliance Monitor for {guild.name}",
                description=(
                    f"**Active Monitors:** {len(active_monitors)}\n\n"
                    "Select an alliance monitor to stop from the dropdown below.\n\n"
                    "**What happens when you stop:**\n"
                    "• Monitoring will be disabled\n"
                    "• No more change notifications will be sent\n"
                    "• You can restart monitoring anytime\n\n"
                    "Select a monitor to stop it."
                ),
                color=0xED4245
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Stop alliance monitor error: {e}")
            import traceback
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while loading the stop monitor menu.",
                ephemeral=True
            )

    async def manage_permissions(self, interaction: discord.Interaction, guild: discord.Guild):
        """Manage permissions for channels"""
        await interaction.response.send_message(
            "🔒 **Manage Permissions**\n\nThis feature is coming soon! It will allow you to:\n"
            "• View channel permissions\n"
            "• Modify role permissions\n"
            "• Set user-specific overrides\n"
            "• Copy permissions between channels",
            ephemeral=True
        )

    async def show_paginated_servers(self, interaction: discord.Interaction, guilds: list):
        """Show paginated server list for servers > 25"""
        await interaction.response.send_message(
            "📊 **Paginated Server List**\n\nThis feature will be implemented for bots in more than 25 servers.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(RemoteAccess(bot, None))
