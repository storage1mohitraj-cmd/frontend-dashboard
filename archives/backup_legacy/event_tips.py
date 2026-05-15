
"""
Event Tips Module - Provides tips for Whiteout Survival events
"""
import discord
from typing import Dict, Optional, List

# Event tips database
EVENT_TIPS: Dict[str, Dict] = {
    "svs": {
        "name": "State vs State",
        "category": "pvp",
        "difficulty": "hard",
        "guide": "https://whiteoutsurvival.fandom.com/wiki/State_vs_State",
        "description": "Large-scale PvP event between states",
        "tips": "Save speedups and resources. Focus on gathering and training."
    },
    "ke": {
        "name": "Kingdom Confrontation",
        "category": "pvp",
        "difficulty": "medium",
        "description": "Kingdom-wide competition event",
        "tips": "Complete daily tasks. Stockpile resources."
    },
    "bear": {
        "name": "Bear Trap",
        "category": "alliance",
        "difficulty": "easy",
        "description": "Alliance boss event",
        "tips": "Call rallies. Use high damage heroes."
    },
    "foundry": {
        "name": "Foundry Battle",
        "category": "alliance",
        "difficulty": "hard",
        "description": "Alliance vs Alliance battle",
        "tips": "Capture buildings. Coordinate movements."
    },
    "crazyjoe": {
        "name": "Crazy Joe",
        "category": "alliance",
        "difficulty": "medium",
        "description": "Defense event",
        "tips": "Send reinforcements to weaker members."
    }
}

def get_event_info(event_key: str) -> Optional[Dict]:
    return EVENT_TIPS.get(event_key.lower())

def get_all_categories() -> List[str]:
    return ["pvp", "alliance", "growth", "daily"]

def get_difficulty_color(difficulty: str) -> discord.Color:
    colors = {
        "easy": discord.Color.green(),
        "medium": discord.Color.gold(),
        "hard": discord.Color.red(),
        "insane": discord.Color.purple()
    }
    return colors.get(difficulty.lower(), discord.Color.blue())

def get_category_emoji(category: str) -> str:
    emojis = {
        "pvp": "⚔️",
        "alliance": "🛡️",
        "growth": "📈",
        "daily": "📅"
    }
    return emojis.get(category.lower(), "🎫")

__all__ = ['EVENT_TIPS', 'get_event_info', 'get_all_categories', 'get_difficulty_color', 'get_category_emoji']
