"""
Event Tips System for Whiteout Survival
Converted from JavaScript to Python with enhanced functionality

This module provides comprehensive event information including:
- Event guides and video tutorials
- Difficulty ratings and duration information
- Category-based event organization
- Search and filtering capabilities
- Rewards information and strategic tips

Version: 2025-07-30-b5c6d7e8-1234-5678-abcd-8901234abcde (Python)
"""

print('[INFO] Loading event_tips.py version: 2025-07-30-b5c6d7e8-1234-5678-abcd-8901234abcde (Python)')

# Event image URLs - converted from images.js
EVENT_IMAGES = {
    'bear': 'https://i.postimg.cc/Xq0GQvXM/bear-event.png',
    'foundry': 'https://i.postimg.cc/QCpGRRKP/foundry-event.png',
    'crazyjoe': 'https://i.postimg.cc/Jz0Tz3Ht/crazy-joe-event.png',
    'alliancemobilization': 'https://i.postimg.cc/Pf9Hs0Ld/alliance-mobilization.png',
    'alliancechampionship': 'https://i.postimg.cc/QMnDnzGH/alliance-championship.png',
    'canyonclash': 'https://i.postimg.cc/Vk9Hn7Lj/canyon-clash.png',
    'fishingtournament': 'https://i.postimg.cc/QdQJXLnK/fishing-tournament.png',
    'frostfiremine': 'https://i.postimg.cc/Fzq03CJf/a463d7c7-7fc7-47fc-b24d-1324383ee2ff-removebg-preview.png'
}

# Event categories with emojis
EVENT_CATEGORIES = {
    "PvE Event": "🐲",
    "PvP Event": "⚔️",
    "Development Event": "🏗️",
    "Alliance Event": "🤝",
    "Competitive PvP": "🏆",
    "Territory Control": "⛰️",
    "Leisure Event": "🎣",
    "Resource Event": "⛏️"
}

# Difficulty color mapping for Discord embeds
DIFFICULTY_COLORS = {
    "Easy": 0x00ff00,      # Green
    "Medium": 0xffff00,    # Yellow
    "Hard": 0xff9900,      # Orange
    "Very Hard": 0xff0000  # Red
}

# Comprehensive event information database
EVENT_TIPS = {
    'bear': {
        'name': 'Bear Hunt',
        'guide': 'https://www.whiteoutsurvival.wiki/events/bear-hunt/',
        'video': 'https://youtu.be/d4EMZhb-S30?si=pNrSsVLgRZbsrVU2',
        'tips': 'please wait🙏- working on it.....',
        'image': 'https://i.postimg.cc/Fzq03CJf/a463d7c7-7fc7-47fc-b24d-1324383ee2ff-removebg-preview.png',
        'difficulty': 'Medium',
        'duration': '3 days',
        'rewards': 'Hero EXP, Equipment Materials, Bear Hunt Tokens, Gold',
        'category': 'PvE Event'
    },
    
    'foundry': {
        'name': 'Foundry Battle',
        'guide': 'https://www.whiteoutsurvival.wiki/events/foundry-battle/',
        'video': 'https://youtu.be/8A1tMTkbdNU?si=i2EPvoVG2ikyXbsO',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['foundry'],
        'difficulty': 'Hard',
        'duration': '7 days',
        'rewards': 'Alliance Coins, Equipment Blueprints, Hero Fragments, Building Materials',
        'category': 'Alliance Event'
    },
    
    'crazyjoe': {
        'name': 'Crazy Joe',
        'guide': 'https://www.whiteoutsurvival.wiki/events/crazy-joe/',
        'video': 'https://youtu.be/KHf7f5wHtu0?si=iRt0MtI9GeJIb6Qc',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['crazyjoe'],
        'difficulty': 'Easy',
        'duration': '5 days',
        'rewards': 'Joe Tokens, Hero Fragments, Exclusive Equipment, Speed-ups',
        'category': 'Development Event'
    },
    
    'alliancemobilization': {
        'name': 'Alliance Mobilization',
        'guide': 'https://www.whiteoutsurvival.wiki/events/alliance-mobilization/',
        'video': 'https://youtu.be/Ni8XMLyVhxQ?si=fBEWoKDTf3EBswNu',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['alliancemobilization'],
        'difficulty': 'Medium',
        'duration': '5 days',
        'rewards': 'Alliance Tech Points, Member Rewards, Exclusive Blueprints, Alliance Coins',
        'category': 'Alliance Event'
    },
    
    'alliancechampionship': {
        'name': 'Alliance Championship',
        'guide': 'https://www.whiteoutsurvival.wiki/events/alliance-championship/',
        'video': 'https://youtu.be/KVZndZ1n1L4?si=0B-V1aQluvK3cSxa',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['alliancechampionship'],
        'difficulty': 'Very Hard',
        'duration': '14 days',
        'rewards': 'Championship Trophies, Exclusive Titles, Premium Equipment, Alliance Fame',
        'category': 'Competitive PvP'
    },
    
    'canyonclash': {
        'name': 'Canyon Clash',
        'guide': 'https://www.whiteoutsurvival.wiki/events/canyon-clash/',
        'video': 'https://youtu.be/jPJFye8ftJQ?si=yWnHIWMm8POy1LWT',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['canyonclash'],
        'difficulty': 'Hard',
        'duration': '10 days',
        'rewards': 'Territory Tokens, Strategic Resources, Military Equipment, Canyon Medals',
        'category': 'Territory Control'
    },
    
    'fishingtournament': {
        'name': 'Fishing Tournament',
        'guide': 'https://www.whiteoutsurvival.wiki/events/fishing-tournament/',
        'video': 'https://youtu.be/LYqKLI1FS7M?si=8suV3mDK5bzCVcku',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['fishingtournament'],
        'difficulty': 'Easy',
        'duration': '7 days',
        'rewards': 'Fishing Tokens, Decorative Items, Relaxation Points, Special Fish',
        'category': 'Leisure Event'
    },
    
    'frostfiremine': {
        'name': 'Frostfire Mine',
        'guide': 'https://www.whiteoutsurvival.wiki/events/frostfire-mine/',
        'video': 'https://youtu.be/uZq97I-tc5Q?si=JGdoD1c8qjxKfM0e',
        'tips': 'please wait🙏- working on it.....',
        'image': EVENT_IMAGES['frostfiremine'],
        'difficulty': 'Medium',
        'duration': '8 days',
        'rewards': 'Rare Minerals, Mining Equipment, Trade Tokens, Industrial Materials',
        'category': 'Resource Event'
    }
}

def get_event_list():
    """
    Get a list of all available event keys
    
    Returns:
        list: List of event keys/identifiers
    """
    return list(EVENT_TIPS.keys())

def get_event_info(event_key):
    """
    Get detailed information about a specific event
    
    Args:
        event_key (str): The event identifier (e.g., 'bear', 'foundry')
    
    Returns:
        dict: Event information dictionary or None if not found
    """
    return EVENT_TIPS.get(event_key.lower())

def search_events(query):
    """
    Search for events based on a query string
    
    Args:
        query (str): Search term to match against event names, tips, or categories
    
    Returns:
        list: List of tuples containing (event_key, event_info) for matching events
    """
    results = []
    query_lower = query.lower()
    
    for event_key, event_info in EVENT_TIPS.items():
        # Search in event name, tips, and category
        if (query_lower in event_info['name'].lower() or 
            query_lower in event_info['tips'].lower() or
            query_lower in event_info['category'].lower() or
            query_lower in event_key.lower()):
            results.append((event_key, event_info))
    
    return results

def get_events_by_category(category):
    """
    Get all events in a specific category
    
    Args:
        category (str): Event category to filter by
    
    Returns:
        list: List of tuples containing (event_key, event_info) for events in the category
    """
    results = []
    
    for event_key, event_info in EVENT_TIPS.items():
        if event_info['category'] == category:
            results.append((event_key, event_info))
    
    return results

def get_events_by_difficulty(difficulty):
    """
    Get all events with a specific difficulty level
    
    Args:
        difficulty (str): Difficulty level to filter by ('Easy', 'Medium', 'Hard', 'Very Hard')
    
    Returns:
        list: List of tuples containing (event_key, event_info) for events with the difficulty
    """
    results = []
    
    for event_key, event_info in EVENT_TIPS.items():
        if event_info['difficulty'] == difficulty:
            results.append((event_key, event_info))
    
    return results

def get_events_by_duration(max_days=None, min_days=None):
    """
    Get events filtered by duration
    
    Args:
        max_days (int, optional): Maximum duration in days
        min_days (int, optional): Minimum duration in days
    
    Returns:
        list: List of tuples containing (event_key, event_info) for matching events
    """
    results = []
    
    for event_key, event_info in EVENT_TIPS.items():
        duration_str = event_info['duration']
        # Extract number from duration string (e.g., "3 days" -> 3)
        try:
            duration_days = int(duration_str.split()[0])
            
            include_event = True
            if max_days is not None and duration_days > max_days:
                include_event = False
            if min_days is not None and duration_days < min_days:
                include_event = False
            
            if include_event:
                results.append((event_key, event_info))
                
        except (ValueError, IndexError):
            # If we can't parse the duration, include the event
            results.append((event_key, event_info))
    
    return results

def get_recommended_events_for_player(player_level=None, alliance_participation=True, pvp_preference=None):
    """
    Get recommended events based on player preferences and level
    
    Args:
        player_level (int, optional): Player's current level
        alliance_participation (bool): Whether player actively participates in alliance
        pvp_preference (str, optional): 'love', 'neutral', or 'avoid'
    
    Returns:
        list: List of recommended (event_key, event_info, reason) tuples
    """
    recommendations = []
    
    for event_key, event_info in EVENT_TIPS.items():
        reasons = []
        
        # Difficulty-based recommendations
        if player_level:
            if player_level < 20 and event_info['difficulty'] in ['Easy', 'Medium']:
                reasons.append("Good for your current level")
            elif player_level >= 40 and event_info['difficulty'] in ['Hard', 'Very Hard']:
                reasons.append("Challenging content for experienced players")
        
        # Alliance participation
        if alliance_participation and 'Alliance' in event_info['category']:
            reasons.append("Great for active alliance members")
        elif not alliance_participation and 'Alliance' not in event_info['category']:
            reasons.append("Solo-friendly event")
        
        # PvP preference
        if pvp_preference == 'love' and 'PvP' in event_info['category']:
            reasons.append("Perfect for PvP enthusiasts")
        elif pvp_preference == 'avoid' and 'PvP' not in event_info['category']:
            reasons.append("Non-PvP content")
        
        # Special recommendations
        if event_info['category'] == 'Leisure Event':
            reasons.append("Relaxing gameplay experience")
        elif event_info['category'] == 'Resource Event':
            reasons.append("Great for resource gathering")
        
        if reasons:
            recommendations.append((event_key, event_info, reasons))
    
    return recommendations

# Additional utility functions
def get_all_categories():
    """Get all available event categories"""
    return list(EVENT_CATEGORIES.keys())

def get_all_difficulties():
    """Get all available difficulty levels"""
    return list(DIFFICULTY_COLORS.keys())

def get_category_emoji(category):
    """Get the emoji for a specific category"""
    return EVENT_CATEGORIES.get(category, "📅")

def get_difficulty_color(difficulty):
    """Get the Discord color code for a difficulty level"""
    return DIFFICULTY_COLORS.get(difficulty, 0x3498db)

# Export the main data structures for use in other modules
__all__ = [
    'EVENT_TIPS', 'EVENT_CATEGORIES', 'DIFFICULTY_COLORS', 'EVENT_IMAGES',
    'get_event_list', 'get_event_info', 'search_events',
    'get_events_by_category', 'get_events_by_difficulty', 'get_events_by_duration',
    'get_recommended_events_for_player', 'get_all_categories', 'get_all_difficulties',
    'get_category_emoji', 'get_difficulty_color'
]

if __name__ == "__main__":
    # Simple test when run directly
    print(f"[STATS] Event Tips System loaded with {len(EVENT_TIPS)} events")
    print(f"[TAGS] Categories: {', '.join(EVENT_CATEGORIES.keys())}")
    print(f"[DIFF] Difficulties: {', '.join(DIFFICULTY_COLORS.keys())}")
    
    # Show a sample event
    sample_event = get_event_info('bear')
    if sample_event:
        print(f"\n[SAMPLE] Event: {sample_event['name']}")
        print(f"   Difficulty: {sample_event['difficulty']}")
        print(f"   Duration: {sample_event['duration']}")
        print(f"   Category: {sample_event['category']}")
