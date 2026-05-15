"""
Music State Storage
Saves and restores music playback state for persistence across bot restarts
"""

import sqlite3
from typing import Optional, Dict, List, Any
from datetime import datetime
import os


class MusicStateStorage:
    """Manages music playback state persistence"""
    
    def __init__(self, db_path: str = "data/music_states.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_states (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                text_channel_id INTEGER,
                persistent_channel_id INTEGER,
                current_track_uri TEXT,
                current_track_title TEXT,
                current_track_author TEXT,
                current_track_position INTEGER DEFAULT 0,
                loop_mode TEXT DEFAULT 'off',
                volume INTEGER DEFAULT 100,
                playlist_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS music_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                uri TEXT NOT NULL,
                title TEXT,
                author TEXT,
                requester_id INTEGER,
                requester_name TEXT,
                FOREIGN KEY (guild_id) REFERENCES music_states(guild_id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_state(
        self,
        guild_id: int,
        channel_id: int,
        text_channel_id: Optional[int] = None,
        current_track: Optional[Dict[str, Any]] = None,
        queue: Optional[List[Dict[str, Any]]] = None,
        loop_mode: str = "off",
        volume: int = 100,
        playlist_name: Optional[str] = None
    ) -> bool:
        """Save music state for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Save main state
            cursor.execute("""
                INSERT OR REPLACE INTO music_states 
                (guild_id, channel_id, text_channel_id, current_track_uri, 
                 current_track_title, current_track_author, current_track_position,
                 loop_mode, volume, playlist_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                guild_id,
                channel_id,
                text_channel_id,
                current_track.get('uri') if current_track else None,
                current_track.get('title') if current_track else None,
                current_track.get('author') if current_track else None,
                current_track.get('position', 0) if current_track else 0,
                loop_mode,
                volume,
                playlist_name,
                datetime.now()
            ))
            
            # Clear old queue
            cursor.execute("DELETE FROM music_queue WHERE guild_id = ?", (guild_id,))
            
            # Save queue
            if queue:
                for position, track in enumerate(queue):
                    cursor.execute("""
                        INSERT INTO music_queue 
                        (guild_id, position, uri, title, author, requester_id, requester_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        guild_id,
                        position,
                        track.get('uri'),
                        track.get('title'),
                        track.get('author'),
                        track.get('requester_id'),
                        track.get('requester_name')
                    ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error saving music state: {e}")
            return False
    
    def load_state(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Load music state for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Load main state
            cursor.execute("""
                SELECT * FROM music_states WHERE guild_id = ?
            """, (guild_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            state = dict(row)
            
            # Load queue
            cursor.execute("""
                SELECT uri, title, author, requester_id, requester_name
                FROM music_queue
                WHERE guild_id = ?
                ORDER BY position ASC
            """, (guild_id,))
            
            queue_rows = cursor.fetchall()
            state['queue'] = [dict(row) for row in queue_rows]
            
            # Build current track dict
            if state['current_track_uri']:
                state['current_track'] = {
                    'uri': state['current_track_uri'],
                    'title': state['current_track_title'],
                    'author': state['current_track_author'],
                    'position': state['current_track_position']
                }
            else:
                state['current_track'] = None
            
            conn.close()
            return state
            
        except Exception as e:
            print(f"Error loading music state: {e}")
            return None
    
    def delete_state(self, guild_id: int) -> bool:
        """Delete music state for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM music_states WHERE guild_id = ?", (guild_id,))
            cursor.execute("DELETE FROM music_queue WHERE guild_id = ?", (guild_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error deleting music state: {e}")
            return False
    
    def get_all_states(self) -> List[Dict[str, Any]]:
        """Get all saved music states"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT guild_id FROM music_states")
            rows = cursor.fetchall()
            
            states = []
            for row in rows:
                state = self.load_state(row['guild_id'])
                if state:
                    states.append(state)
            
            conn.close()
            return states
            
        except Exception as e:
            print(f"Error getting all states: {e}")
            return []
    
    def set_persistent_channel(self, guild_id: int, channel_id: int) -> bool:
        """Set persistent voice channel for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if guild has existing state
            cursor.execute("SELECT guild_id FROM music_states WHERE guild_id = ?", (guild_id,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing record
                cursor.execute("""
                    UPDATE music_states 
                    SET persistent_channel_id = ?, updated_at = ?
                    WHERE guild_id = ?
                """, (channel_id, datetime.now(), guild_id))
            else:
                # Create new record with minimal data
                cursor.execute("""
                    INSERT INTO music_states 
                    (guild_id, channel_id, persistent_channel_id, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (guild_id, channel_id, channel_id, datetime.now()))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error setting persistent channel: {e}")
            return False
    
    def get_persistent_channel(self, guild_id: int) -> Optional[int]:
        """Get persistent voice channel for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT persistent_channel_id FROM music_states WHERE guild_id = ?
            """, (guild_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                return row[0]
            return None
            
        except Exception as e:
            print(f"Error getting persistent channel: {e}")
            return None
    
    def clear_persistent_channel(self, guild_id: int) -> bool:
        """Clear persistent voice channel for a guild"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE music_states 
                SET persistent_channel_id = NULL, updated_at = ?
                WHERE guild_id = ?
            """, (datetime.now(), guild_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error clearing persistent channel: {e}")
            return False


# Global instance
music_state_storage = MusicStateStorage()
