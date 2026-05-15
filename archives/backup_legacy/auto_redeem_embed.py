"""
Professional embed builder for Auto-Redeem registration success messages
"""
import discord
from datetime import datetime


def create_auto_redeem_success_embed(
    player_name: str,
    player_id: str,
    furnace_level: int,
    user_mention: str = None,
    state_id: str = None,
    avatar_url: str = None
) -> discord.Embed:
    """
    Creates a professional, visually appealing embed for auto-redeem registration success.
    
    Args:
        player_name: The player's in-game name
        player_id: The player's 9-digit ID
        furnace_level: The player's furnace level
        user_mention: Optional Discord user mention (e.g., "@pikachu")
        state_id: Optional state ID (e.g., "State #2540")
        avatar_url: Optional player avatar URL
    
    Returns:
        A formatted Discord embed
    """
    # Create the embed with a vibrant green color for success
    embed = discord.Embed(
        title="✅ Auto-Redeem Activated!",
        description=f"**{player_name}** has been successfully registered for automatic gift code redemption.",
        color=0x00ff9c,  # Bright mint green
        timestamp=datetime.utcnow()
    )
    
    # Add player information in a clean, organized way
    player_info = f"```\n"
    player_info += f"🎮 Player:     {player_name}\n"
    player_info += f"🆔 Player ID:  {player_id}\n"
    player_info += f"🔥 Furnace:    Level {furnace_level}\n"
    if state_id:
        player_info += f"🗺️  State:      {state_id}\n"
    player_info += f"```"
    
    embed.add_field(
        name="📋 Registration Details",
        value=player_info,
        inline=False
    )
    
    # Add "What's Next" section with benefits
    whats_next = (
        "🎁 **Automatic Delivery**\n"
        "• All new gift codes will be sent to you automatically\n"
        "• Codes are delivered as soon as they become available\n\n"
        "⚡ **No Action Required**\n"
        "• Sit back and relax - we'll handle everything!\n"
        "• You'll receive instant notifications with each new code"
    )
    
    embed.add_field(
        name="🚀 What Happens Next?",
        value=whats_next,
        inline=False
    )
    
    # Add footer with user mention if provided
    footer_text = "Enjoy your rewards! 🎉"
    if user_mention:
        footer_text = f"{user_mention}, enjoy your rewards! 🎉"
    
    embed.set_footer(
        text=footer_text,
        icon_url="https://em-content.zobj.net/thumbs/120/twitter/348/wrapped-gift_1f381.png"
    )
    
    # Add thumbnail - either player avatar or a success icon
    thumb_url = avatar_url or "https://em-content.zobj.net/thumbs/120/twitter/348/party-popper_1f389.png"
    embed.set_thumbnail(url=thumb_url)
    
    return embed


def create_compact_auto_redeem_success_embed(
    player_name: str,
    player_id: str,
    furnace_level: int,
    user_mention: str = None
) -> discord.Embed:
    """
    Creates a more compact version of the auto-redeem success embed.
    
    Args:
        player_name: The player's in-game name
        player_id: The player's 9-digit ID
        furnace_level: The player's furnace level
        user_mention: Optional Discord user mention
    
    Returns:
        A formatted Discord embed
    """
    embed = discord.Embed(
        title="🎉 Welcome to Auto-Redeem!",
        description=(
            f"**{player_name}** is now registered!\n\n"
            f"🆔 **Player ID:** `{player_id}`\n"
            f"🔥 **Furnace Level:** {furnace_level}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "**🎁 What's Next?**\n"
            "You'll automatically receive all new gift codes as soon as they're available!\n\n"
        ),
        color=0x00ff9c,
        timestamp=datetime.utcnow()
    )
    
    # Footer with mention
    if user_mention:
        embed.set_footer(text=f"{user_mention} Sit back and enjoy the rewards! 🚀")
    else:
        embed.set_footer(text="Sit back and enjoy the rewards! 🚀")
    
    # Thumbnail
    embed.set_thumbnail(url="https://em-content.zobj.net/thumbs/120/twitter/348/party-popper_1f389.png")
    
    return embed


# Example usage:
if __name__ == "__main__":
    # Example of how to use the function
    embed = create_auto_redeem_success_embed(
        player_name="Humbled_Farm",
        player_id="444116047",
        furnace_level=30,
        user_mention="@pikachu",
        state_info="State #2540 x Magnus🚀"
    )
    
    # In your actual bot code, you would send it like this:
    # await channel.send(embed=embed)
    # or
    # await interaction.response.send_message(embed=embed)
