"""
Simple User ID Mapping System for Katabump Deployment
"""

# Simple user mappings - you can customize these later if needed
KNOWN_USERS = {
    # Add Discord user IDs here if you want custom name mapping
    # Example: "123456789012345678": "custom_user_id",
}

def get_known_user_id(discord_user_id: str) -> str:
    """
    Get the known user profile ID for a Discord user ID
    
    Args:
        discord_user_id: The Discord user's ID as a string
        
    Returns:
        The known user profile ID if found, otherwise the original ID
    """
    return KNOWN_USERS.get(discord_user_id, discord_user_id)

def get_known_user_name(discord_user_id: str) -> str:
    """
    Get the proper name for a known user
    
    Args:
        discord_user_id: The Discord user's ID as a string
        
    Returns:
        The proper name if known, None otherwise
    """
    # For now, just return None - you can customize this later
    return None

def is_known_user(discord_user_id: str) -> bool:
    """
    Check if a Discord user ID belongs to a known server member
    
    Args:
        discord_user_id: The Discord user's ID as a string
        
    Returns:
        True if this is a known server member, False otherwise
    """
    return discord_user_id in KNOWN_USERS
