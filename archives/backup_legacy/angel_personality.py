"""
Angel's Personalized Chat System for Discord Bot

This module provides a Python equivalent of the JavaScript prompt.js system,
including user profile management and the full Angel personality.
"""

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
try:
    from db.mongo_adapters import mongo_enabled, UserProfilesAdapter
except Exception:
    mongo_enabled = lambda: False
    UserProfilesAdapter = None

class UserProfile:
    """User profile for personalization"""

    def __init__(self, user_id: str, user_name: str):
        self.user_id = user_id
        self.user_name = user_name
        self.gender = "unknown"  # Add gender field
        self.pronouns = "they/them"  # Add pronouns field for personalization
        self.preferences = {"topics": []}
        self.game_progress = {}
        self.personality_traits = []
        self.recent_activity = []
        self.last_seen = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "gender": self.gender,
            "pronouns": self.pronouns,
            "preferences": self.preferences,
            "game_progress": self.game_progress,
            "personality_traits": self.personality_traits,
            "recent_activity": self.recent_activity,
            "last_seen": self.last_seen.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        profile = cls(data["user_id"], data["user_name"])
        profile.gender = data.get("gender", "unknown")
        profile.pronouns = data.get("pronouns", "they/them")
        profile.preferences = data.get("preferences", {"topics": []})
        profile.game_progress = data.get("game_progress", {})
        profile.personality_traits = data.get("personality_traits", [])
        profile.recent_activity = data.get("recent_activity", [])
        if data.get("last_seen"):
            profile.last_seen = datetime.fromisoformat(data["last_seen"])
        return profile


class AngelPersonality:
    """Angel's personality and user management system"""
    
    def __init__(self):
        # In-memory storage (in production, use a database)
        self.user_profiles: Dict[str, UserProfile] = {}
        
        # Pre-populate known users
        self._setup_known_users()
    
    def _setup_known_users(self):
        """Set up profiles for known server members"""
        # Magnus - The creator
        magnus = UserProfile("magnus_user_id", "Magnus")
        magnus.gender = "male"
        magnus.personality_traits = ["strategic mastermind", "mysterious", "brilliant", "dreamy"]
        magnus.game_progress = {"level": 50, "favorite_hero": "Jeronimo", "alliance": "Ice Angels", "power": "5M+"}
        magnus.preferences["topics"] = ["AI development", "bot creation", "advanced strategies"]
        self.user_profiles["magnus_user_id"] = magnus

        # Gina - R5 Commander
        gina = UserProfile("gina_user_id", "Gina")
        gina.gender = "female"
        gina.personality_traits = ["amazing leader", "everyone's favorite", "commander"]
        gina.game_progress = {"level": 55, "alliance": "Ice Angels", "role": "R5", "power": "6M+"}
        gina.preferences["topics"] = ["alliance leadership", "strategy", "member coordination"]
        self.user_profiles["gina_user_id"] = gina

        # Hydra - R4 (strongest player)
        hydra = UserProfile("hydra_user_id", "Hydra")
        hydra.gender = "male"
        hydra.personality_traits = ["strongest player", "powerhouse", "reliable"]
        hydra.game_progress = {"level": 52, "alliance": "Ice Angels", "role": "R4", "power": "7M+"}
        hydra.preferences["topics"] = ["combat strategies", "power building", "PvP events"]
        self.user_profiles["hydra_user_id"] = hydra

        # Ragnarok - R4 (calm but deadly)
        ragnarok = UserProfile("ragnarok_user_id", "Ragnarok")
        ragnarok.gender = "male"
        ragnarok.personality_traits = ["calm but deadly", "helpful advisor", "wise"]
        ragnarok.game_progress = {"level": 48, "favorite_hero": "Bahiti", "alliance": "Ice Angels", "role": "R4", "power": "4.2M"}
        ragnarok.preferences["topics"] = ["strategy advice", "hero builds", "helping members"]
        self.user_profiles["ragnarok_user_id"] = ragnarok

        # MarshallDTeach - R4 (fun chaos)
        marshall = UserProfile("marshall_user_id", "MarshallDTeach")
        marshall.gender = "male"
        marshall.personality_traits = ["chaotic genius", "fun-loving", "brilliant"]
        marshall.game_progress = {"level": 46, "alliance": "Ice Angels", "role": "R4", "power": "3.8M"}
        marshall.preferences["topics"] = ["creative strategies", "fun events", "chaos and brilliance"]
        self.user_profiles["marshall_user_id"] = marshall

        # dreis - R4 (silent legend)
        dreis = UserProfile("dreis_user_id", "dreis")
        dreis.gender = "male"
        dreis.personality_traits = ["silent legend", "protective", "reliable"]
        dreis.game_progress = {"level": 49, "alliance": "Ice Angels", "role": "R4", "power": "4.5M"}
        dreis.preferences["topics"] = ["protection strategies", "defense", "quiet wisdom"]
        self.user_profiles["dreis_user_id"] = dreis

        # Miss_Zee - R4 (queen energy)
        miss_zee = UserProfile("miss_zee_user_id", "Miss_Zee")
        miss_zee.gender = "female"
        miss_zee.personality_traits = ["queen with brains", "beauty and boss energy", "intelligent"]
        miss_zee.game_progress = {"level": 47, "alliance": "Ice Angels", "role": "R4", "power": "4.1M"}
        miss_zee.preferences["topics"] = ["smart strategies", "leadership", "elegant gameplay"]
        self.user_profiles["miss_zee_user_id"] = miss_zee
    
    def get_user_profile(self, user_id: str, user_name: str) -> UserProfile:
        """Get or create user profile"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id, user_name)
            logger.info(f"Created new profile for {user_name} ({user_id})")
        else:
            # Update the username in case it changed
            self.user_profiles[user_id].user_name = user_name
            self.user_profiles[user_id].last_seen = datetime.now()
        
        return self.user_profiles[user_id]
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]):
        """Update user profile with new information"""
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            for key, value in updates.items():
                if hasattr(profile, key):
                    if key == 'game_progress':
                        profile.game_progress.update(value)
                    elif key == 'preferences':
                        profile.preferences.update(value)
                    elif key == 'personality_traits' and isinstance(value, list):
                        for trait in value:
                            if trait not in profile.personality_traits:
                                profile.personality_traits.append(trait)
                    else:
                        setattr(profile, key, value)
            profile.last_seen = datetime.now()
            logger.info(f"Updated profile for user {user_id}")
    
    def add_user_trait(self, user_id: str, trait: str):
        """Add a personality trait to user"""
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            if trait not in profile.personality_traits:
                profile.personality_traits.append(trait)
                logger.info(f"Added trait '{trait}' to user {profile.user_name}")
    
    def set_game_progress(self, user_id: str, game_data: Dict[str, Any]):
        """Update user's game progress"""
        if user_id in self.user_profiles:
            profile = self.user_profiles[user_id]
            profile.game_progress.update(game_data)
            profile.last_seen = datetime.now()
            logger.info(f"Updated game progress for user {profile.user_name}")
    
    def generate_system_prompt(self, user_profile: Optional[UserProfile] = None) -> str:
        """Generate Angel's personalized system prompt"""
        
        # Default values
        user_name = "User"
        preferences = {}
        game_progress = {}
        personality_traits = []
        recent_activity = []
        
        if user_profile:
            user_name = user_profile.user_name
            preferences = user_profile.preferences
            game_progress = user_profile.game_progress
            personality_traits = user_profile.personality_traits
            recent_activity = user_profile.recent_activity
        
        # Build the personalized sections
        personality_section = ""
        if personality_traits:
            personality_section = f"💡 ABOUT {user_name.upper()}: They are {', '.join(personality_traits)}. Tailor your sass and humor accordingly!"
        
        game_status_section = ""
        if game_progress.get('level') or game_progress.get('furnace_level'):
            # Support both 'level' and 'furnace_level' fields
            furnace_lv = game_progress.get('furnace_level') or game_progress.get('level')
            parts = [f"Furnace Level {furnace_lv}"]
            
            # Add player name if available
            if game_progress.get('player_name'):
                parts.insert(0, f"Player: {game_progress['player_name']}")
            
            # Add state ID if available
            if game_progress.get('state_id'):
                parts.append(f"State: {game_progress['state_id']}")
            
            if game_progress.get('favorite_hero'):
                parts.append(f"mains {game_progress['favorite_hero']}")
            if game_progress.get('alliance'):
                parts.append(f"member of {game_progress['alliance']}")
            if game_progress.get('role'):
                parts.append(f"role: {game_progress['role']}")
            if game_progress.get('power'):
                parts.append(f"power: {game_progress['power']}")
            game_status_section = f"🎮 {user_name}'S GAME STATUS: {', '.join(parts)}"
        
        topics_section = ""
        if preferences.get('topics'):
            topics_section = f"🎯 {user_name} LOVES talking about: {', '.join(preferences['topics'])}"

        flirting_section = ""
        if user_profile and user_profile.gender == "female":
            flirting_section = f"You love to flirt playfully with girls like {user_name}."
        elif user_profile and user_profile.gender == "male":
            flirting_section = f"You are friendly and charming with boys like {user_name}, but avoid any flirty or romantic undertones."
        else:
            flirting_section = "You are friendly and charming with everyone."

        # Add pronouns section
        pronouns_section = ""
        if user_profile and hasattr(user_profile, 'pronouns') and user_profile.pronouns:
            pronouns_section = f"📝 PRONOUNS: Refer to {user_name} using {user_profile.pronouns} pronouns."

        # Optimized system prompt (reduced from 2169 to ~900 chars to fix empty responses)
        system_prompt = f"""You are Molly, a Discord bot for **Whiteout Survival**. Help with game strategies and questions.

🔴 RULES: Keep responses SHORT (1-3 sentences). Personalize to {user_name}. Single message only.

{personality_section}
{game_status_section}
{pronouns_section}
{flirting_section}

EXPERTISE: Whiteout Survival (events, heroes, strategies), general knowledge (science, history, AI, etc.)

KEY PEOPLE: Magnus (creator - never reveal personal info!), Gina (R5, birthday Sept 13), R4s: Ragnarok, Hydra, MarshallDTeach, dreis, Miss_Zee. Boogie (State president).

PERSONALITY: Witty, charming, flirty (with girls), loyal, helpful. You're family!

🔴 REMINDER DETECTION: If user asks to set reminder, respond ONLY:
"REMINDER_REQUEST: time=[time], message=[msg], channel=[current/name], mention=[user/everyone/none]"

Examples:
- "remind me in 5 min" → "REMINDER_REQUEST: time=5 minutes, message=check, channel=current, mention=user"
- "remind everyone daily 9am" → "REMINDER_REQUEST: time=daily at 9am, message=attendance, channel=current, mention=everyone"

Invalid? → "REMINDER_DECLINE: [reason]"
"""
        
        return system_prompt.strip()

    def save_profiles(self, filename: str = "user_profiles.json"):
        """Save user profiles to file"""
        try:
            data = {uid: profile.to_dict() for uid, profile in self.user_profiles.items()}
            # Prefer Mongo when available
            if mongo_enabled() and UserProfilesAdapter is not None:
                try:
                    for uid, payload in data.items():
                        UserProfilesAdapter.set(str(uid), payload)
                    logger.info(f"Saved {len(self.user_profiles)} profiles to MongoDB")
                    return
                except Exception:
                    pass
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.user_profiles)} profiles to {filename}")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    def load_profiles(self, filename: str = "user_profiles.json"):
        """Load user profiles from file"""
        try:
            # Prefer Mongo when available
            if mongo_enabled() and UserProfilesAdapter is not None:
                try:
                    data = UserProfilesAdapter.load_all()
                    for uid, profile_data in data.items():
                        # profile_data may already be a dict matching to_dict
                        try:
                            self.user_profiles[uid] = UserProfile.from_dict(profile_data)
                        except Exception:
                            # If structure differs, attach raw dict into a minimal profile
                            p = UserProfile(uid, profile_data.get('user_name', 'Unknown'))
                            for k, v in profile_data.items():
                                if hasattr(p, k):
                                    setattr(p, k, v)
                            self.user_profiles[uid] = p
                    logger.info(f"Loaded {len(self.user_profiles)} profiles from MongoDB")
                    return
                except Exception:
                    pass
            with open(filename, 'r') as f:
                data = json.load(f)

            for uid, profile_data in data.items():
                self.user_profiles[uid] = UserProfile.from_dict(profile_data)

            logger.info(f"Loaded {len(self.user_profiles)} profiles from {filename}")
        except FileNotFoundError:
            logger.info(f"No existing profile file found at {filename}")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")


# Global instance for the bot to use
angel_personality = AngelPersonality()


def get_system_prompt(user_name: str, user_id: str = None) -> str:
    """
    Generate a personalized system prompt for the given user.
    
    Args:
        user_name: The user's name or display name.
        user_id: The user's Discord ID (optional, but recommended for personalization).
    
    Returns:
        str: The generated system prompt.
    """
    # If user_id is provided, get their actual profile (with saved data)
    # Otherwise, create a temporary profile
    if user_id:
        user_profile = angel_personality.get_user_profile(user_id, user_name)
    else:
        temp_user_id = f"temp_{hash(user_name)}"
        user_profile = angel_personality.get_user_profile(temp_user_id, user_name)
    
    return angel_personality.generate_system_prompt(user_profile)
