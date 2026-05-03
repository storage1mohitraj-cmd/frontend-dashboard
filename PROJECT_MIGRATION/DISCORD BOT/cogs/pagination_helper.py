import discord
from typing import List


class ResultsPaginationView(discord.ui.View):
    """
    A reusable pagination view for displaying lists of results across multiple pages.
    
    Features:
    - Previous/Next button navigation
    - Automatic button state management
    - Configurable timeout
    - Author-only interaction (optional)
    """
    
    def __init__(self, embeds: List[discord.Embed], author_id: int = None, timeout: int = 300):
        """
        Initialize pagination view with pre-created embeds.
        
        Args:
            embeds: List of Discord embeds (one per page)
            author_id: Optional user ID to restrict interactions (None = anyone can use)
            timeout: Timeout in seconds (default 300 = 5 minutes)
        """
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0
        self.author_id = author_id
        self.message = None
        self.update_buttons()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user is allowed to interact with this view."""
        if self.author_id is None:
            return True
        
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ You cannot use these buttons.",
                ephemeral=True
            )
            return False
        return True
    
    def update_buttons(self):
        """Update button states based on current page."""
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= len(self.embeds) - 1)
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next page."""
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    async def on_timeout(self):
        """Disable all buttons when view times out."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


def create_paginated_embeds(
    title: str,
    description: str,
    results: List[str],
    items_per_page: int = 20,
    color: int = 0x57F287,
    field_name: str = "📋 Details"
) -> List[discord.Embed]:
    """
    Create a list of paginated embeds from a list of result strings.
    
    Args:
        title: Embed title
        description: Embed description (appears on all pages)
        results: List of result strings to paginate
        items_per_page: Number of items per page (default 20)
        color: Embed color (default green)
        field_name: Name for the field containing results
    
    Returns:
        List of Discord embeds (one per page)
    """
    if not results:
        # Return single embed with no results
        embed = discord.Embed(title=title, description=description, color=color)
        return [embed]
    
    # Calculate total pages
    total_pages = (len(results) - 1) // items_per_page + 1
    embeds = []
    
    for page_num in range(total_pages):
        # Get items for this page
        start_idx = page_num * items_per_page
        end_idx = min(start_idx + items_per_page, len(results))
        page_results = results[start_idx:end_idx]
        
        # Create embed for this page
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        # Add results field
        results_text = "\n".join(page_results)
        embed.add_field(
            name=field_name,
            value=results_text,
            inline=False
        )
        
        # Add page footer
        if total_pages > 1:
            embed.set_footer(text=f"Page {page_num + 1}/{total_pages} • Showing {len(page_results)} of {len(results)} total")
        else:
            embed.set_footer(text=f"Showing all {len(results)} results")
        
        embeds.append(embed)
    
    return embeds


def create_alliance_log_embeds(
    alliance_name: str,
    admin_name: str,
    admin_id: int,
    added_count: int,
    error_count: int,
    already_exists_count: int,
    ids_list: List[str],
    items_per_page: int = 20
) -> List[discord.Embed]:
    """
    Create paginated embeds specifically for alliance member add logs.
    
    Args:
        alliance_name: Name of the alliance
        admin_name: Name of the admin who added members
        admin_id: ID of the admin
        added_count: Number of successfully added members
        error_count: Number of failed additions
        already_exists_count: Number of members that already existed
        ids_list: List of FIDs that were added
        items_per_page: Number of FIDs per page (default 20)
    
    Returns:
        List of Discord embeds (one per page)
    """
    from datetime import datetime
    
    if not ids_list:
        # Return single embed with no FIDs
        embed = discord.Embed(
            title="👥 Members Added to Alliance",
            description=(
                f"**Alliance:** {alliance_name}\n"
                f"**Administrator:** {admin_name} (`{admin_id}`)\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"**Results:**\n"
                f"✅ Successfully Added: {added_count}\n"
                f"❌ Failed: {error_count}\n"
                f"⚠️ Already Exists: {already_exists_count}\n\n"
                "**Added FIDs:**\n"
                "```\nNo FIDs to display\n```"
            ),
            color=discord.Color.green()
        )
        return [embed]
    
    # Calculate total pages
    total_pages = (len(ids_list) - 1) // items_per_page + 1
    embeds = []
    
    for page_num in range(total_pages):
        # Get FIDs for this page
        start_idx = page_num * items_per_page
        end_idx = min(start_idx + items_per_page, len(ids_list))
        page_fids = ids_list[start_idx:end_idx]
        
        # Create embed for this page
        embed = discord.Embed(
            title="👥 Members Added to Alliance",
            description=(
                f"**Alliance:** {alliance_name}\n"
                f"**Administrator:** {admin_name} (`{admin_id}`)\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"**Results:**\n"
                f"✅ Successfully Added: {added_count}\n"
                f"❌ Failed: {error_count}\n"
                f"⚠️ Already Exists: {already_exists_count}\n\n"
                f"**Added FIDs (Page {page_num + 1}/{total_pages}):**\n"
                f"```\n{', '.join(page_fids)}\n```"
            ),
            color=discord.Color.green()
        )
        
        # Add page footer
        if total_pages > 1:
            embed.set_footer(text=f"Page {page_num + 1}/{total_pages} • Showing {len(page_fids)} of {len(ids_list)} FIDs")
        
        embeds.append(embed)
    
    return embeds
