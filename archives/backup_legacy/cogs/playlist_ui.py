"""
Playlist Management UI Components
Interactive views, modals, and buttons for playlist management
"""

import discord

from discord.ext import commands
from typing import Optional, List
from datetime import datetime
import wavelink

from playlist_storage import playlist_storage


class SavePlaylistModal(discord.ui.Modal):
    """Modal for entering playlist name"""

    playlist_name = discord.ui.TextInput(
        label="Playlist Name",
        placeholder="Enter a name for this playlist...",
        max_length=50,
        required=True
    )

    def __init__(self, player, user_id: int, guild_id: int):
        super().__init__()
        self.player = player
        self.user_id = user_id
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.ApplicationContext):
        try:
            await interaction.response.defer()

            # Check if queue is empty
            if self.player.queue.is_empty and not self.player.current:
                await interaction.followup.send("❌ Queue is empty! Add some tracks first.", ephemeral=True)
                return

            # Collect all tracks (current + queue)
            tracks = []

            # Add current track if playing
            if self.player.current:
                track = self.player.current
                tracks.append({
                    'title': track.title,
                    'author': track.author,
                    'uri': track.uri,
                    'length': track.length
                })

            # Add queued tracks
            for track in list(self.player.queue):
                tracks.append({
                    'title': track.title,
                    'author': track.author,
                    'uri': track.uri,
                    'length': track.length
                })

            # Save to database
            name = self.playlist_name.value.strip()
            success = await playlist_storage.save_playlist(
                self.guild_id,
                self.user_id,
                name,
                tracks
            )

            if success:
                await interaction.followup.send(
                    f"✅ Saved playlist **{name}** with **{len(tracks)}** tracks!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to save playlist. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


class PlaylistSelect(discord.ui.Select):
    """Dropdown for selecting a playlist"""

    def __init__(self, playlists: List[dict], action: str):
        self.action = action  # "load" or "delete"

        options = []
        for playlist in playlists[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=playlist['name'],
                description=f"{playlist['track_count']} tracks",
                value=playlist['name']
            ))

        super().__init__(
            placeholder=f"Select playlist to {action}...",
            options=options,
            custom_id=f"playlist_select_{action}"
        )

    async def callback(self, interaction: discord.ApplicationContext):
        # This will be handled by the parent view
        pass


class PlaylistListView(discord.ui.View):
    """View for displaying and managing saved playlists"""

    def __init__(self, user_id: int, guild_id: int, player, page: int = 0):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.player = player
        self.page = page
        self.per_page = 10
        self.playlists = []
        self.total_count = 0

    async def load_playlists(self):
        """Load playlists from database"""
        self.total_count = await playlist_storage.count_playlists(self.guild_id, self.user_id)
        self.playlists = await playlist_storage.list_playlists(
            self.guild_id,
            self.user_id,
            limit=self.per_page,
            offset=self.page * self.per_page
        )

    def get_embed(self) -> discord.Embed:
        """Generate playlist list embed"""
        total_pages = max(1, (self.total_count + self.per_page - 1) // self.per_page)

        embed = discord.Embed(
            title="📋 My Playlists",
            color=0x00CED1,
            description=f"You have **{self.total_count}** saved playlist(s)"
        )

        if not self.playlists:
            embed.add_field(
                name="No Playlists",
                value="You haven't saved any playlists yet!\nUse the **Save Current Queue** button to create one.",
                inline=False
            )
        else:
            playlist_text = ""
            for i, playlist in enumerate(self.playlists, start=1):
                created = datetime.fromisoformat(playlist['created_at']).strftime("%Y-%m-%d")
                playlist_text += f"`{i}.` **{playlist['name']}**\n"
                playlist_text += f"   └ {playlist['track_count']} tracks • Created: {created}\n\n"

            embed.add_field(
                name="Your Playlists",
                value=playlist_text,
                inline=False
            )

        embed.set_footer(text=f"Page {self.page + 1}/{total_pages}")
        return embed

    async def update_view(self, interaction: discord.ApplicationContext):
        """Refresh the view with current data"""
        await self.load_playlists()

        # Clear existing items
        self.clear_items()

        # Add select menus if there are playlists
        if self.playlists:
            load_select = PlaylistSelect(self.playlists, "load")
            load_select.callback = self.load_playlist_callback
            self.add_item(load_select)

            delete_select = PlaylistSelect(self.playlists, "delete")
            delete_select.callback = self.delete_playlist_callback
            self.add_item(delete_select)

        # Add navigation buttons
        total_pages = max(1, (self.total_count + self.per_page - 1) // self.per_page)

        prev_button = discord.ui.Button(
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == 0),
            custom_id="prev_page"
        )
        prev_button.callback = self.previous_page
        self.add_item(prev_button)

        next_button = discord.ui.Button(
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page >= total_pages - 1),
            custom_id="next_page"
        )
        next_button.callback = self.next_page
        self.add_item(next_button)

        back_button = discord.ui.Button(
            emoji="🔙",
            label="Back",
            style=discord.ButtonStyle.secondary,
            custom_id="back"
        )
        back_button.callback = self.back_to_main
        self.add_item(back_button)

        # Check if this is the first response or an edit
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.get_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def load_playlist_callback(self, interaction: discord.ApplicationContext):
        """Handle playlist loading"""
        loading_message = None
        try:
            await interaction.response.defer()

            playlist_name = interaction.data['values'][0]

            # Show loading animation
            loading_embed = discord.Embed(
                title="⏳ Loading Playlist",
                description=f"Loading **{playlist_name}**...\n\n🔄 Please wait while we load your tracks",
                color=0x5865F2
            )
            loading_embed.set_footer(text="This may take a moment depending on playlist size")
            loading_message = await interaction.followup.send(embed=loading_embed, ephemeral=True)

            # Load playlist from database
            playlist = await playlist_storage.load_playlist(
                self.guild_id,
                self.user_id,
                playlist_name
            )

            if not playlist:
                # Delete loading message
                if loading_message:
                    try:
                        await loading_message.delete()
                    except:
                        pass
                await interaction.followup.send("❌ Playlist not found!", ephemeral=True)
                return

            # Clear current queue
            self.player.queue.clear()
            self.player.current_playlist_name = playlist_name

            # Add tracks to queue
            loaded_count = 0
            total_tracks = len(playlist['tracks'])

            for idx, track_data in enumerate(playlist['tracks'], 1):
                try:
                    # Update loading message periodically (every 5 tracks)
                    if idx % 5 == 0 or idx == total_tracks:
                        try:
                            loading_embed.description = f"Loading **{playlist_name}**...\n\n🔄 Loading tracks: {idx}/{total_tracks}"
                            await loading_message.edit(embed=loading_embed)
                        except:
                            pass  # Ignore edit errors

                    # Search for track by URI
                    tracks = await wavelink.Playable.search(track_data['uri'])
                    if tracks:
                        track = tracks[0] if isinstance(tracks, list) else tracks
                        track.extras.requester_id = self.user_id
                        track.extras.requester_name = str(interaction.user)
                        self.player.queue.put(track)
                        loaded_count += 1
                except Exception as e:
                    print(f"Failed to load track {track_data['title']}: {e}")
                    continue

            # Start playing if not already playing
            if not self.player.playing and not self.player.queue.is_empty:
                next_track = self.player.queue.get()
                await self.player.play(next_track)

            # Delete loading message
            if loading_message:
                try:
                    await loading_message.delete()
                except:
                    pass  # Ignore if already deleted

            # Create interactive view with options
            embed = discord.Embed(
                title="✅ Playlist Loaded",
                description=f"Successfully loaded **{playlist_name}**",
                color=0x57F287
            )
            embed.add_field(
                name="📊 Stats",
                value=f"**Tracks Loaded:** {loaded_count}/{len(playlist['tracks'])}\\n**Queue Size:** {self.player.queue.count}",
                inline=False
            )
            embed.add_field(
                name="🎵 Now Playing",
                value=self.player.current.title if self.player.current else "Starting playback...",
                inline=False
            )
            embed.set_footer(text="Use the buttons below to manage your playlist")

            # Create view with action buttons
            view = PlaylistLoadedView(self.player, playlist_name)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            # Delete loading message on error
            if loading_message:
                try:
                    await loading_message.delete()
                except:
                    pass
            await interaction.followup.send(f"❌ Error loading playlist: {e}", ephemeral=True)

    async def delete_playlist_callback(self, interaction: discord.ApplicationContext):
        """Handle playlist deletion"""
        try:
            playlist_name = interaction.data['values'][0]

            # Delete from database
            success = await playlist_storage.delete_playlist(
                self.guild_id,
                self.user_id,
                playlist_name
            )

            if success:
                await interaction.response.send_message(
                    f"🗑️ Deleted playlist **{playlist_name}**",
                    ephemeral=True
                )
                # Refresh the view
                await self.update_view(interaction)
            else:
                await interaction.response.send_message(
                    "❌ Failed to delete playlist",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    async def previous_page(self, interaction: discord.ApplicationContext):
        """Go to previous page"""
        if self.page > 0:
            self.page -= 1
            await self.update_view(interaction)
        else:
            await interaction.response.send_message("Already on first page", ephemeral=True)

    async def next_page(self, interaction: discord.ApplicationContext):
        """Go to next page"""
        total_pages = max(1, (self.total_count + self.per_page - 1) // self.per_page)
        if self.page < total_pages - 1:
            self.page += 1
            await self.update_view(interaction)
        else:
            await interaction.response.send_message("Already on last page", ephemeral=True)

    async def back_to_main(self, interaction: discord.ApplicationContext):
        """Return to main playlist manager"""
        view = PlaylistManagementView(self.user_id, self.guild_id, self.player)
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view)



class PlaylistLoadedView(discord.ui.View):
    """View shown after successfully loading a playlist"""

    def __init__(self, player, playlist_name: str):
        super().__init__(timeout=180)
        self.player = player
        self.playlist_name = playlist_name

    @discord.ui.button(emoji="📋", label="View Queue", style=discord.ButtonStyle.primary, row=0)
    async def view_queue(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Show the current queue"""
        # Import here to avoid circular imports
        from cogs.music import QueuePaginationView

        view = QueuePaginationView(self.player, page=0)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

    @discord.ui.button(emoji="🔁", label="Loop Off", style=discord.ButtonStyle.secondary, row=0)
    async def loop_off(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Set loop mode to off"""
        self.player.loop_mode = "off"
        await interaction.response.send_message("🔁 Loop mode: **Off**", ephemeral=True)

    @discord.ui.button(emoji="🔂", label="Loop Track", style=discord.ButtonStyle.secondary, row=0)
    async def loop_track(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Set loop mode to track"""
        self.player.loop_mode = "track"
        await interaction.response.send_message("🔂 Loop mode: **Track** (current song will repeat)", ephemeral=True)

    @discord.ui.button(emoji="🔁", label="Loop Queue", style=discord.ButtonStyle.success, row=1)
    async def loop_queue(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Set loop mode to queue"""
        self.player.loop_mode = "queue"
        await interaction.response.send_message("🔁 Loop mode: **Queue** (playlist will repeat)", ephemeral=True)

    @discord.ui.button(emoji="🎵", label="Now Playing", style=discord.ButtonStyle.primary, row=1)
    async def now_playing(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Show now playing info"""
        from cogs.music import Music, PlayerControlView

        if not self.player.current:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return

        # Create a temporary Music instance to use create_now_playing_embed
        music_cog = interaction.client.get_cog('Music')
        if music_cog:
            embed = music_cog.create_now_playing_embed(self.player)
            view = PlayerControlView(self.player)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Music cog not found!", ephemeral=True)


class PlaylistManagementView(discord.ui.View):

    def __init__(self, user_id: int, guild_id: int, player):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.player = player

    def get_embed(self) -> discord.Embed:
        """Generate main playlist manager embed"""
        queue_count = self.player.queue.count
        current_playing = self.player.current.title if self.player.current else "Nothing"

        embed = discord.Embed(
            title="🎵 Playlist Manager",
            color=0x5865F2,  # Discord blurple color
            description=""
        )

        # Current status section
        status_text = f"**Queue:** {queue_count} tracks\n"
        status_text += f"**Now Playing:** {current_playing}\n"

        if self.player.current_playlist_name:
            status_text += f"**Loaded Playlist:** 📁 {self.player.current_playlist_name}"

        embed.add_field(
            name="📊 Current Status",
            value=status_text,
            inline=False
        )

        # Instructions
        embed.add_field(
            name="💡 Quick Actions",
            value="• **Save Current Queue** - Save your current queue as a playlist\n"
                  "• **My Playlists** - View and manage your saved playlists",
            inline=False
        )

        embed.set_footer(text="💾 Save • 📋 View • ❌ Close", icon_url="https://cdn.discordapp.com/emojis/852881450667081728.gif")
        return embed

    @discord.ui.button(emoji="💾", label="Save Current Queue", style=discord.ButtonStyle.primary, custom_id="save_queue", row=0)
    async def save_queue(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Open modal to save current queue"""
        if self.player.queue.is_empty and not self.player.current:
            await interaction.response.send_message("❌ Queue is empty! Add some tracks first.", ephemeral=True)
            return

        modal = SavePlaylistModal(self.player, self.user_id, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(emoji="📋", label="My Playlists", style=discord.ButtonStyle.secondary, custom_id="my_playlists", row=0)
    async def my_playlists(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Show saved playlists"""
        view = PlaylistListView(self.user_id, self.guild_id, self.player)
        await view.load_playlists()
        await view.update_view(interaction)

    @discord.ui.button(emoji="❌", label="Close", style=discord.ButtonStyle.danger, custom_id="close", row=0)
    async def close(self, interaction: discord.ApplicationContext, button: discord.ui.Button):
        """Close the playlist manager"""
        embed = discord.Embed(
            description="✅ Playlist manager closed",
            color=0x57F287
        )
        await interaction.response.edit_message(embed=embed, view=None)
