import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import asyncio
import aiohttp
import json
import ssl
import random
import re
from datetime import datetime
import logging

try:
    from db.mongo_adapters import mongo_enabled, GiftCodesAdapter, AutoRedeemSettingsAdapter, AutoRedeemChannelsAdapter, GiftCodeRedemptionAdapter, AutoRedeemMembersAdapter, AutoRedeemedCodesAdapter, _get_db
except Exception:
    mongo_enabled = lambda: False
    GiftCodesAdapter = None
    AutoRedeemSettingsAdapter = None
    AutoRedeemChannelsAdapter = None
    AutoRedeemMembersAdapter = None
    AutoRedeemedCodesAdapter = None
    _get_db = lambda: None
    
    # Fallback stub for GiftCodeRedemptionAdapter
    class GiftCodeRedemptionAdapter:
        @staticmethod
        def track_redemption(guild_id, code, fid, status):
            return False

try:
    from db_utils import get_db_connection
    from admin_utils import is_admin, is_global_admin, is_bot_owner
except ImportError:
    from pathlib import Path
    
    def get_db_connection(db_name: str, **kwargs):
        db_path = Path(__file__).parent.parent / 'db' / db_name
        return sqlite3.connect(str(db_path), **kwargs)
    
    def is_global_admin(user_id):
        return False
    
    def is_admin(user_id):
        return False
    
    async def is_bot_owner(bot, user_id):
        return False


class APISessionPool:
    """Manages multiple API sessions with independent rate limiting"""
    
    def __init__(self, session_count=2, base_delay=2.0, rate_limit_backoff=5.0, max_backoff=60.0):
        self.session_count = session_count
        self.base_delay = base_delay
        self.rate_limit_backoff = rate_limit_backoff
        self.max_backoff = max_backoff
        
        # Track state per session
        self.last_used = [0.0] * session_count
        self.rate_limited_until = [0.0] * session_count
        self.backoff_time = [rate_limit_backoff] * session_count
        self.lock = asyncio.Lock()
    
    async def get_available_session(self):
        """Get the best available session ID (least recently used and not rate-limited)"""
        async with self.lock:
            now = datetime.now().timestamp()
            
            # Find sessions that are not rate-limited
            available = []
            for i in range(self.session_count):
                if now >= self.rate_limited_until[i]:
                    # Reset backoff if rate limit has expired
                    if self.rate_limited_until[i] > 0:
                        self.backoff_time[i] = self.rate_limit_backoff
                        self.rate_limited_until[i] = 0.0
                    available.append(i)
            
            if not available:
                # All sessions are rate-limited, wait for the soonest one
                min_wait_idx = min(range(self.session_count), key=lambda i: self.rate_limited_until[i])
                wait_time = max(0, self.rate_limited_until[min_wait_idx] - now)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self.backoff_time[min_wait_idx] = self.rate_limit_backoff
                self.rate_limited_until[min_wait_idx] = 0.0
                return min_wait_idx
            
            # Return least recently used available session
            session_id = min(available, key=lambda i: self.last_used[i])
            
            # Enforce base delay
            time_since_last = now - self.last_used[session_id]
            if time_since_last < self.base_delay:
                await asyncio.sleep(self.base_delay - time_since_last)
            
            self.last_used[session_id] = datetime.now().timestamp()
            return session_id
    
    async def mark_rate_limited(self, session_id):
        """Mark a session as rate-limited with exponential backoff"""
        async with self.lock:
            now = datetime.now().timestamp()
            self.rate_limited_until[session_id] = now + self.backoff_time[session_id]
            # Exponential backoff, but cap at max_backoff
            self.backoff_time[session_id] = min(self.backoff_time[session_id] * 2, self.max_backoff)
    
    def is_any_available(self):
        """Check if any session is currently available"""
        now = datetime.now().timestamp()
        return any(now >= self.rate_limited_until[i] for i in range(self.session_count))



class ManageGiftCode(commands.Cog):
    """Gift Code Management for /manage command with API integration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.giftcode_db = get_db_connection('giftcode.sqlite', check_same_thread=False)
        self.cursor = self.giftcode_db.cursor()
        self.settings_db = sqlite3.connect('db/settings.sqlite', check_same_thread=False)
        self.settings_cursor = self.settings_db.cursor()
        
        # API Configuration
        self.api_url = "http://gift-code-api.whiteout-bot.com/giftcode_api.php"
        self.api_key = "super_secret_bot_token_nobody_will_ever_find"
        
        # Rate limiting
        self.last_api_call = 0
        self.min_api_call_interval = 3
        
        # SSL context
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Logger (must be initialized before CAPTCHA solver)
        self.logger = logging.getLogger('manage_giftcode')
        self.logger.setLevel(logging.INFO)
        
        # WOS API URLs and Key for gift code redemption
        self.wos_player_info_url = "https://wos-giftcode-api.centurygame.com/api/player"
        self.wos_giftcode_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
        self.wos_captcha_url = "https://wos-giftcode-api.centurygame.com/api/captcha"
        self.wos_encrypt_key = "tB87#kPtkxqOS2"
        
        # Initialize CAPTCHA solver
        try:
            from .gift_captchasolver import GiftCaptchaSolver, ONNX_AVAILABLE
            if ONNX_AVAILABLE:
                self.captcha_solver = GiftCaptchaSolver(save_images=0)
                if self.captcha_solver.is_initialized:
                    self.logger.info("CAPTCHA solver initialized successfully")
                else:
                    self.logger.warning("CAPTCHA solver failed to initialize - model files may be missing")
                    self.captcha_solver = None
            else:
                self.logger.warning("ONNX not available - CAPTCHA solving disabled")
                self.captcha_solver = None
        except Exception as e:
            self.logger.exception(f"Error initializing CAPTCHA solver: {e}")
            self.captcha_solver = None
        
        # Initialize API session pool for concurrent processing
        self.session_pool = APISessionPool(
            session_count=2,           # 2 independent API sessions
            base_delay=3.0,            # 3 seconds between requests per session (more conservative)
            rate_limit_backoff=10.0,   # Initial backoff when rate limited (longer wait)
            max_backoff=60.0           # Maximum backoff duration
        )
        
        # Concurrent processing configuration
        self.concurrent_redemptions = 2  # Process 2 members simultaneously
        
        # Auto-redeem lock to prevent duplicate processing
        self._active_redemptions = set()  # Track active (guild_id, code) pairs
        self._redemption_lock = asyncio.Lock()
        
        # Stop signals for auto-redeem
        self.stop_signals = {}  # {guild_id: boolean}
        

        
        
        self.setup_database()
        
        # Start the API check task
        self.api_check_task.start()
    
    def setup_database(self):
        """Initialize gift code database tables"""
        try:
            # Gift codes table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS gift_codes (
                    giftcode TEXT PRIMARY KEY,
                    date TEXT
                )
            """)
            
            # Add missing columns if they don't exist
            try:
                self.cursor.execute("ALTER TABLE gift_codes ADD COLUMN validation_status TEXT DEFAULT 'pending'")
                self.logger.info("Added validation_status column to gift_codes")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                self.cursor.execute("ALTER TABLE gift_codes ADD COLUMN added_by INTEGER")
                self.logger.info("Added added_by column to gift_codes")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                self.cursor.execute("ALTER TABLE gift_codes ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                self.logger.info("Added added_at column to gift_codes")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                self.cursor.execute("ALTER TABLE gift_codes ADD COLUMN auto_redeem_processed INTEGER DEFAULT 0")
                self.logger.info("Added auto_redeem_processed column to gift_codes")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Gift code channels table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS giftcode_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    auto_post INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Auto-use settings table (legacy - keeping for compatibility)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS giftcode_autouse (
                    guild_id INTEGER,
                    alliance_id INTEGER,
                    enabled INTEGER DEFAULT 1,
                    PRIMARY KEY (guild_id, alliance_id)
                )
            """)
            
            # Auto redeem members table (SQLite fallback)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_redeem_members (
                    guild_id INTEGER,
                    fid TEXT,
                    nickname TEXT,
                    furnace_lv INTEGER DEFAULT 0,
                    avatar_image TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, fid)
                )
            """)
            
            # Migrate existing table - add missing columns if they don't exist
            try:
                self.cursor.execute("ALTER TABLE auto_redeem_members ADD COLUMN furnace_lv INTEGER DEFAULT 0")
                self.logger.info("Added furnace_lv column to auto_redeem_members")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                self.cursor.execute("ALTER TABLE auto_redeem_members ADD COLUMN avatar_image TEXT")
                self.logger.info("Added avatar_image column to auto_redeem_members")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Auto redeem channels table - for monitoring channels for FID codes
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_redeem_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    added_by INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Auto redeem settings table - for enable/disable auto redemption
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_redeem_settings (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    updated_by INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.giftcode_db.commit()
            self.logger.info("Gift code database tables initialized")
        except Exception as e:
            self.logger.error(f"Error setting up gift code database: {e}")
    
    # ===== Auto-Redeem Member Management Helper Class =====
    class AutoRedeemDB:
        """MongoDB/SQLite hybrid storage for auto-redeem members"""
        
        @staticmethod
        def get_members(cog_instance, guild_id):
            """Get all auto-redeem members for a guild (filters out invalid FIDs)"""
            try:
                members = []
                
                # Try MongoDB first
                if mongo_enabled() and AutoRedeemMembersAdapter:
                    try:
                        members = AutoRedeemMembersAdapter.get_members(guild_id)
                    except Exception as e:
                        cog_instance.logger.warning(f"MongoDB get_members failed, using SQLite: {e}")
                        members = []
                
                # Fallback to SQLite if no members from MongoDB
                if not members:
                    cog_instance.cursor.execute("""
                        SELECT fid, nickname, furnace_lv, avatar_image, added_by, added_at
                        FROM auto_redeem_members
                        WHERE guild_id = ?
                        ORDER BY furnace_lv DESC
                    """, (guild_id,))
                    rows = cog_instance.cursor.fetchall()
                    members = [
                        {
                            'fid': row[0],
                            'nickname': row[1],
                            'furnace_lv': row[2] or 0,
                            'avatar_image': row[3] or '',
                            'added_by': row[4],
                            'added_at': row[5]
                        }
                        for row in rows
                    ]
                
                # Filter out members with null/empty/None FIDs
                valid_members = [
                    member for member in members
                    if member.get('fid') and str(member.get('fid', '')).strip() and str(member.get('fid', '')).lower() != 'none'
                ]
                
                # Log if we filtered any invalid members
                filtered_count = len(members) - len(valid_members)
                if filtered_count > 0:
                    cog_instance.logger.warning(f"Filtered out {filtered_count} members with invalid FIDs for guild {guild_id}")
                
                return valid_members
            except Exception as e:
                cog_instance.logger.error(f"Error getting auto-redeem members: {e}")
                return []
        
        @staticmethod
        def cleanup_null_members(cog_instance, guild_id=None):
            """Remove all members with null/empty FIDs from database"""
            try:
                removed_count = 0
                
                # Remove from SQLite
                if guild_id:
                    cog_instance.cursor.execute("""
                        DELETE FROM auto_redeem_members 
                        WHERE guild_id = ? AND (fid IS NULL OR fid = '' OR fid = 'None')
                    """, (guild_id,))
                else:
                    cog_instance.cursor.execute("""
                        DELETE FROM auto_redeem_members 
                        WHERE fid IS NULL OR fid = '' OR fid = 'None'
                    """)
                removed_count = cog_instance.cursor.rowcount
                cog_instance.giftcode_db.commit()
                
                # Remove from MongoDB
                if mongo_enabled() and AutoRedeemMembersAdapter:
                    try:
                        from db.mongo_adapters import _get_db
                        db = _get_db()
                        if db:
                            if guild_id:
                                result = db[AutoRedeemMembersAdapter.COLL].delete_many({
                                    'guild_id': int(guild_id),
                                    '$or': [
                                        {'fid': None},
                                        {'fid': ''},
                                        {'fid': 'None'}
                                    ]
                                })
                            else:
                                result = db[AutoRedeemMembersAdapter.COLL].delete_many({
                                    '$or': [
                                        {'fid': None},
                                        {'fid': ''},
                                        {'fid': 'None'}
                                    ]
                                })
                            removed_count += result.deleted_count
                    except Exception as e:
                        cog_instance.logger.error(f"Error cleaning up null members from MongoDB: {e}")
                
                if removed_count > 0:
                    cog_instance.logger.info(f"🧹 Cleaned up {removed_count} members with null/empty FIDs")
                
                return removed_count
            except Exception as e:
                cog_instance.logger.error(f"Error cleaning up null members: {e}")
                return 0
        
        @staticmethod
        def add_member(cog_instance, guild_id, fid, member_data):
            """Add a member to auto-redeem list"""
            try:
                # Validate FID - reject null, empty, or 'None' values
                if not fid or not str(fid).strip() or str(fid).strip().lower() == 'none':
                    cog_instance.logger.warning(f"Rejected adding member with invalid FID: {fid}")
                    return False
                
                # Ensure fid is a clean string
                fid = str(fid).strip()
                
                member_data['fid'] = fid
                member_data['added_at'] = datetime.now()
                
                # Try MongoDB first
                if mongo_enabled() and AutoRedeemMembersAdapter:
                    try:
                        success = AutoRedeemMembersAdapter.add_member(guild_id, fid, member_data)
                        if success:
                            # Also add to SQLite for consistency
                            cog_instance.cursor.execute("""
                                INSERT OR IGNORE INTO auto_redeem_members 
                                (guild_id, fid, nickname, furnace_lv, avatar_image, added_by, added_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (guild_id, fid, member_data.get('nickname', 'Unknown'),
                                  member_data.get('furnace_lv', 0), member_data.get('avatar_image', ''),
                                  member_data.get('added_by'), member_data['added_at']))
                            cog_instance.giftcode_db.commit()
                            return True
                        return False
                    except Exception as e:
                        cog_instance.logger.warning(f"MongoDB add_member failed, using SQLite: {e}")
                
                # Fallback to SQLite
                cog_instance.cursor.execute("""
                    INSERT OR IGNORE INTO auto_redeem_members 
                    (guild_id, fid, nickname, furnace_lv, avatar_image, added_by, added_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (guild_id, fid, member_data.get('nickname', 'Unknown'),
                      member_data.get('furnace_lv', 0), member_data.get('avatar_image', ''),
                      member_data.get('added_by'), member_data['added_at']))
                cog_instance.giftcode_db.commit()
                return cog_instance.cursor.rowcount > 0
            except Exception as e:
                cog_instance.logger.error(f"Error adding auto-redeem member: {e}")
                return False
        
        @staticmethod
        def remove_member(cog_instance, guild_id, fid):
            """Remove a member from auto-redeem list"""
            try:
                # Try MongoDB first
                if mongo_enabled() and AutoRedeemMembersAdapter:
                    try:
                        success = AutoRedeemMembersAdapter.remove_member(guild_id, fid)
                        if success:
                            # Also remove from SQLite
                            cog_instance.cursor.execute(
                                "DELETE FROM auto_redeem_members WHERE guild_id = ? AND fid = ?",
                                (guild_id, fid)
                            )
                            cog_instance.giftcode_db.commit()
                            return True
                        return False
                    except Exception as e:
                        cog_instance.logger.warning(f"MongoDB remove_member failed, using SQLite: {e}")
                
                # Fallback to SQLite
                cog_instance.cursor.execute(
                    "DELETE FROM auto_redeem_members WHERE guild_id = ? AND fid = ?",
                    (guild_id, fid)
                )
                cog_instance.giftcode_db.commit()
                return cog_instance.cursor.rowcount > 0
            except Exception as e:
                cog_instance.logger.error(f"Error removing auto-redeem member: {e}")
                return False
        
        @staticmethod
        def member_exists(cog_instance, guild_id, fid):
            """Check if member exists in auto-redeem list"""
            try:
                # Try MongoDB first
                if mongo_enabled() and AutoRedeemMembersAdapter:
                    try:
                        return AutoRedeemMembersAdapter.member_exists(guild_id, fid)
                    except Exception as e:
                        cog_instance.logger.warning(f"MongoDB member_exists failed, using SQLite: {e}")
                
                # Fallback to SQLite
                cog_instance.cursor.execute(
                    "SELECT 1 FROM auto_redeem_members WHERE guild_id = ? AND fid = ? LIMIT 1",
                    (guild_id, fid)
                )
                return cog_instance.cursor.fetchone() is not None
            except Exception as e:
                cog_instance.logger.error(f"Error checking auto-redeem member: {e}")
                return False
    
    async def fetch_player_data(self, fid):
        """Fetch player data from WOS API"""
        try:
            # Import login handler
            from cogs.login_handler import LoginHandler
            login_handler = LoginHandler()
            
            # Get player info using fetch_player_data
            player_data = await login_handler.fetch_player_data(fid)
            
            if player_data and player_data.get('data'):
                data = player_data['data']
                return {
                    'nickname': data.get('nickname', 'Unknown'),
                    'furnace_lv': int(data.get('stove_lv', 0)),
                    'avatar_image': data.get('avatar_image', '')
                }
            return None
        except Exception as e:
            self.logger.error(f"Error fetching player data for FID {fid}: {e}")
            return None
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.api_check_task.cancel()
        try:
            self.giftcode_db.close()
            self.settings_db.close()
        except:
            pass
    
    async def check_admin_permission(self, user_id: int) -> bool:
        """Check if user has admin permissions"""
        # Check if user is bot owner
        if await is_bot_owner(self.bot, user_id):
            return True
        
        # Check if user is global admin
        if is_global_admin(user_id):
            return True
        
        # Check if user is admin
        if is_admin(user_id):
            return True
        
        return False
    
    def format_furnace_level(self, furnace_lv):
        """Format furnace level display matching game logic"""
        if not furnace_lv or furnace_lv <= 30:
            return str(furnace_lv) if furnace_lv else "0"
        
        # Level 31-34 = 30-1 to 30-4
        if 31 <= furnace_lv <= 34:
            level_in_tier = furnace_lv - 30
            return f"30-{level_in_tier}"
        
        # Level 35+ follows pattern:
        # 35 = FC 1, 36-39 = FC 1-1 to FC 1-4
        # 40 = FC 2, 41-44 = FC 2-1 to FC 2-4
        # 45 = FC 3, 46-49 = FC 3-1 to FC 3-4
        # etc.
        adjusted_level = furnace_lv - 35  # 35 becomes 0, 36 becomes 1, etc.
        tier = (adjusted_level // 5) + 1
        level_in_tier = adjusted_level % 5
        
        if level_in_tier == 0:
            # Base tier level (35, 40, 45, etc.)
            return f"FC {tier}"
        else:
            # Sub-tier level (36-39, 41-44, etc.)
            return f"FC {tier}-{level_in_tier}"
    
    async def _redeem_for_member(self, guild_id, fid, nickname, furnace_lv, giftcode):
        """
        Process gift code redemption for a single member using session pool.
        Returns: (status, success, already_redeemed, failed)
        
        This method will retry intelligently until success, already_redeemed, or permanent failure.
        """
        RETRY_DELAY_BASE = 2.0
        MAX_RETRY_DELAY = 30.0  # Cap retry delay at 30 seconds
        MAX_LOGIN_RETRIES = 5  # Max times to retry login
        MAX_REDEMPTION_RETRIES = 10  # Max times to retry redemption
        
        try:
            # Phase 1: Login with limited retries
            session = None
            response = None
            login_successful = False
            session_id = None
            login_attempt = 0
            
            while not login_successful and login_attempt < MAX_LOGIN_RETRIES:
                login_attempt += 1
                try:
                    # Get available session from pool
                    session_id = await self.session_pool.get_available_session()
                    
                    # Get player session
                    session, response = await self.get_stove_info_wos(player_id=fid)
                    
                    # Check if login successful
                    try:
                        player_info = response.json()
                        msg = player_info.get("msg", "NO_MSG")
                        
                        if msg == "success":  # Player info API returns lowercase success
                            login_successful = True
                            self.logger.info(f"✅ Login successful for {nickname} (FID: {fid}, attempt {login_attempt})")
                            break
                        else:
                            retry_delay = min(RETRY_DELAY_BASE * login_attempt, MAX_RETRY_DELAY)
                            self.logger.warning(f"Login attempt {login_attempt}/{MAX_LOGIN_RETRIES} failed for {nickname} (FID: {fid}), API returned: {msg}, retrying in {retry_delay:.1f}s")
                            await asyncio.sleep(retry_delay)
                    except Exception as json_err:
                        # Check if HTML error page (rate limited)
                        if response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                            self.logger.warning(f"Login rate limited for {nickname} (FID: {fid}), session {session_id}, attempt {login_attempt}")
                            if session_id is not None:
                                await self.session_pool.mark_rate_limited(session_id)
                            # Wait longer when rate limited
                            retry_delay = min(RETRY_DELAY_BASE * 2 * login_attempt, MAX_RETRY_DELAY)
                            await asyncio.sleep(retry_delay)
                        else:
                            raise json_err
                except Exception as e:
                    retry_delay = min(RETRY_DELAY_BASE * login_attempt, MAX_RETRY_DELAY)
                    self.logger.warning(f"Login attempt {login_attempt}/{MAX_LOGIN_RETRIES} error for {nickname} (FID: {fid}): {e}, retrying in {retry_delay:.1f}s")
                    await asyncio.sleep(retry_delay)
            
            # Check if login failed after all retries
            if not login_successful:
                self.logger.error(f"❌ Login failed for {nickname} after {MAX_LOGIN_RETRIES} attempts")
                return ("LOGIN_FAILED", 0, 0, 1)
            
            # Phase 2: Gift code redemption with limited retries
            redemption_successful = False
            final_status = None
            redemption_attempt = 0
            
            while not redemption_successful and redemption_attempt < MAX_REDEMPTION_RETRIES:
                redemption_attempt += 1
                try:
                    # Get available session from pool
                    session_id = await self.session_pool.get_available_session()
                    
                    # Attempt gift code redemption with CAPTCHA
                    status, img, code, method = await self.attempt_gift_code_with_api(fid, giftcode, session)
                    final_status = status
                    
                    # Check for NOT LOGIN error - need to re-establish session
                    if status == "CAPTCHA_FETCH_ERROR":
                        # Could be due to session expiry, try to re-login
                        self.logger.warning(f"⚠️ CAPTCHA fetch failed for {nickname}, might be session issue, re-logging in...")
                        
                        # Re-establish login
                        session, response = await self.get_stove_info_wos(player_id=fid)
                        try:
                            player_info = response.json()
                            if player_info.get("msg") == "success":
                                self.logger.info(f"✅ Re-login successful for {nickname}")
                                retry_delay = min(RETRY_DELAY_BASE * redemption_attempt, MAX_RETRY_DELAY)
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                self.logger.error(f"❌ Re-login failed for {nickname}: {player_info.get('msg')}")
                                # Treat as permanent failure after 3 re-login attempts
                                if redemption_attempt >= 3:
                                    break
                                retry_delay = min(RETRY_DELAY_BASE * 2 * redemption_attempt, MAX_RETRY_DELAY)
                                await asyncio.sleep(retry_delay)
                                continue
                        except Exception:
                            # Re-login failed critically
                            if redemption_attempt >= 3:
                                break
                            retry_delay = min(RETRY_DELAY_BASE * 2 * redemption_attempt, MAX_RETRY_DELAY)
                            await asyncio.sleep(retry_delay)
                            continue
                    
                    # Check for rate limiting
                    if status in ["RATE_LIMITED", "CAPTCHA_TOO_FREQUENT"]:
                        self.logger.warning(f"Rate limit detected for {nickname}, session {session_id}: {status}, attempt {redemption_attempt}")
                        if session_id is not None:
                            await self.session_pool.mark_rate_limited(session_id)
                        # Wait longer when rate limited
                        retry_delay = min(RETRY_DELAY_BASE * 2 * redemption_attempt, MAX_RETRY_DELAY)
                        self.logger.info(f"⏳ Waiting {retry_delay:.1f}s before retry for {nickname}")
                        await asyncio.sleep(retry_delay)
                        continue
                    
                    # Check if redemption was successful
                    if status in ["SUCCESS", "SAME TYPE EXCHANGE"]:
                        redemption_successful = True
                        self.logger.info(f"✅ Redeemed for {nickname}: {status} (attempt {redemption_attempt})")
                        break
                    elif status == "ALREADY_RECEIVED":
                        # Already redeemed - this is a success condition (user already has reward)
                        self.logger.info(f"ℹ️ Already redeemed for {nickname}")
                        break
                    elif status in ["INVALID_CODE", "EXPIRED", "CDK_NOT_FOUND", "USAGE_LIMIT", "TIME_ERROR"]:
                        # Permanent failures - code itself is bad, not worth retrying
                        self.logger.warning(f"❌ Permanent failure for {nickname}: {status} - code is invalid/expired")
                        break
                    elif "RECHARGE_MONEY_VIP" in status or "VIP" in status:
                        # VIP/Purchase requirement - this code requires the player to have VIP or made purchases
                        self.logger.warning(f"💎 VIP/Purchase required for {nickname}: This gift code requires VIP status or in-game purchases")
                        break
                    elif status.startswith("UNKNOWN_STATUS_"):
                        # Unknown status - likely a permanent error from the API
                        # Extract the actual status message
                        actual_msg = status.replace("UNKNOWN_STATUS_", "")
                        self.logger.warning(f"⚠️ Unknown API status for {nickname}: {actual_msg}")
                        
                        # Treat as permanent failure after 3 attempts to avoid infinite loops
                        if redemption_attempt >= 3:
                            self.logger.error(f"❌ Giving up on {nickname} after {redemption_attempt} attempts with unknown status: {actual_msg}")
                            break
                        
                        # Retry with longer backoff for unknown statuses
                        retry_delay = min(RETRY_DELAY_BASE * 2 * redemption_attempt, MAX_RETRY_DELAY)
                        self.logger.warning(f"Redemption attempt {redemption_attempt} failed for {nickname}: {status}, retrying in {retry_delay:.1f}s")
                        await asyncio.sleep(retry_delay)
                    else:
                        # Temporary failure - retry with backoff
                        retry_delay = min(RETRY_DELAY_BASE * redemption_attempt, MAX_RETRY_DELAY)
                        self.logger.warning(f"Redemption attempt {redemption_attempt}/{MAX_REDEMPTION_RETRIES} failed for {nickname}: {status}, retrying in {retry_delay:.1f}s")
                        await asyncio.sleep(retry_delay)
                except Exception as e:
                    retry_delay = min(RETRY_DELAY_BASE * redemption_attempt, MAX_RETRY_DELAY)
                    self.logger.warning(f"Redemption attempt {redemption_attempt}/{MAX_REDEMPTION_RETRIES} error for {nickname}: {e}, retrying in {retry_delay:.1f}s")
                    await asyncio.sleep(retry_delay)
            
            # Check if redemption failed after all retries
            if not redemption_successful and final_status not in ["ALREADY_RECEIVED"]:
                self.logger.error(f"❌ Redemption failed for {nickname} after {redemption_attempt} attempts, final status: {final_status}")
            
            # Track redemption to MongoDB for history and to prevent duplicates on restart
            if final_status:
                try:
                    # Track in general redemption history
                    if mongo_enabled() and GiftCodeRedemptionAdapter:
                        # Determine tracking status
                        if redemption_successful:
                            tracking_status = "success"
                        elif final_status == "ALREADY_RECEIVED":
                            tracking_status = "already_redeemed"
                        else:
                            tracking_status = "failed"
                        
                        GiftCodeRedemptionAdapter.track_redemption(
                            guild_id=guild_id,
                            code=giftcode,
                            fid=str(fid),
                            status=tracking_status
                        )
                        self.logger.debug(f"Tracked redemption: guild={guild_id}, code={giftcode}, fid={fid}, status={tracking_status}")
                    
                    # CRITICAL: Track in AutoRedeemedCodesAdapter to prevent duplicate redemptions on restart
                    # This tracks which specific members have already redeemed a code
                    if mongo_enabled() and AutoRedeemedCodesAdapter:
                        if redemption_successful or final_status == "ALREADY_RECEIVED":
                            # Mark this specific member as having redeemed this code
                            AutoRedeemedCodesAdapter.mark_code_redeemed_for_member(
                                guild_id=guild_id,
                                code=giftcode,
                                fid=str(fid),
                                status="success" if redemption_successful else "already_redeemed"
                            )
                            self.logger.debug(f"✅ Marked {nickname} (FID: {fid}) as redeemed for code {giftcode} in guild {guild_id}")
                except Exception as e:
                    self.logger.error(f"Error tracking redemption: {e}")
            
            # Return results
            # Treat TIME_ERROR, EXPIRED, and USAGE_LIMIT as "already redeemed" since:
            # - TIME_ERROR: Code has expired (redemption window passed)
            # - EXPIRED: Code is no longer valid
            # - USAGE_LIMIT: Code has been fully used up
            # These aren't failures - they just mean the code is no longer available
            expired_statuses = {"TIME_ERROR", "EXPIRED", "USAGE_LIMIT"}
            
            success = 1 if redemption_successful else 0
            already_redeemed = 1 if final_status == "ALREADY_RECEIVED" or final_status in expired_statuses else 0
            failed = 1 if not redemption_successful and final_status != "ALREADY_RECEIVED" and final_status not in expired_statuses else 0
            
            return (final_status, success, already_redeemed, failed)
            
        except Exception as e:
            self.logger.exception(f"Critical error redeeming for {nickname}: {e}")
            # Even on critical error, return failure
            return ("EXCEPTION", 0, 0, 1)
    
    async def process_auto_redeem(self, guild_id, giftcode, silent_on_skip=False):
        """
        Process automatic gift code redemption for all members with animation.
        
        Args:
            guild_id: Discord guild ID
            giftcode: Gift code to redeem
        """
        # Reset stop signal for this guild
        self.stop_signals[guild_id] = False
        
        # Check if redemption already in progress for this guild/code combination
        redemption_key = (guild_id, giftcode)
        
        async with self._redemption_lock:
            if redemption_key in self._active_redemptions:
                self.logger.warning(f"⚠️ Auto-redeem already in progress for guild {guild_id} with code {giftcode}, skipping duplicate")
                return
            # Mark this redemption as active
            self._active_redemptions.add(redemption_key)
            self.logger.info(f"🔒 Locked auto-redeem for guild {guild_id} with code {giftcode}")
        
        try:
            # Check if auto redeem is enabled - try MongoDB first, fallback to SQLite
            enabled = False
            if mongo_enabled() and AutoRedeemSettingsAdapter:
                try:
                    settings = AutoRedeemSettingsAdapter.get_settings(guild_id)
                    if settings:
                        enabled = settings.get('enabled', False)
                except Exception as e:
                    self.logger.warning(f"Failed to get auto redeem settings from MongoDB: {e}")
            
            # Fallback to SQLite if MongoDB failed or not enabled
            if not mongo_enabled() or not AutoRedeemSettingsAdapter:
                self.cursor.execute(
                    "SELECT enabled FROM auto_redeem_settings WHERE guild_id = ?",
                    (guild_id,)
                )
                result = self.cursor.fetchone()
                enabled = result[0] == 1 if result else False
            
            if not enabled:
                self.logger.info(f"Auto redeem disabled for guild {guild_id}, skipping")
                return
            
            # Get import channel - try MongoDB first, fallback to SQLite
            channel_id = None
            if mongo_enabled() and AutoRedeemChannelsAdapter:
                try:
                    channel_config = AutoRedeemChannelsAdapter.get_channel(guild_id)
                    if channel_config:
                        channel_id = channel_config.get('channel_id')
                except Exception as e:
                    self.logger.warning(f"Failed to get auto redeem channel from MongoDB: {e}")
            
            # Fallback to SQLite if MongoDB failed or not enabled
            if channel_id is None:
                self.cursor.execute(
                    "SELECT channel_id FROM auto_redeem_channels WHERE guild_id = ?",
                    (guild_id,)
                )
                channel_result = self.cursor.fetchone()
                if channel_result:
                    channel_id = channel_result[0]
            
            if not channel_id:
                self.logger.warning(f"No import channel configured for guild {guild_id}")
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                self.logger.warning(f"Import channel {channel_id} not found")
                return
            
            # Get all auto-redeem members using MongoDB-first helper
            members_data = self.AutoRedeemDB.get_members(self, guild_id)
            
            if not members_data:
                self.logger.info(f"No auto-redeem members for guild {guild_id}")
                return
            
            
            # Filter out members who have already redeemed this code (checked via MongoDB)
            # Use batch checking to avoid blocking the event loop with many sequential MongoDB calls
            members_to_process = []
            skipped_count = 0
            
            if mongo_enabled() and AutoRedeemedCodesAdapter:
                try:
                    # Batch check all FIDs at once to prevent event loop blocking
                    self.logger.info(f"🔍 Batch checking {len(members_data)} members for code {giftcode}...")
                    
                    # Extract all FIDs
                    all_fids = [member['fid'] for member in members_data]
                    
                    # Run batch check in thread pool to avoid blocking event loop
                    redeemed_status = await asyncio.to_thread(
                        AutoRedeemedCodesAdapter.batch_check_members,
                        guild_id,
                        giftcode,
                        all_fids
                    )
                    
                    # Filter based on batch check results
                    for member in members_data:
                        fid = str(member['fid'])
                        if redeemed_status.get(fid, False):
                            self.logger.info(f"⏭️ Skipping {member['nickname']} (FID: {fid}) - already redeemed code {giftcode}")
                            skipped_count += 1
                        else:
                            members_to_process.append((fid, member['nickname'], member.get('furnace_lv', 0)))
                    
                    self.logger.info(f"✅ Batch check complete: {len(members_to_process)} to process, {skipped_count} already redeemed")
                except Exception as e:
                    self.logger.warning(f"Error during batch check, falling back to processing all members: {e}")
                    # On error, process all members (better than skipping everyone)
                    members_to_process = [
                        (member['fid'], member['nickname'], member.get('furnace_lv', 0))
                        for member in members_data
                    ]
            else:
                # MongoDB not enabled, process all members
                self.logger.info("MongoDB not enabled, processing all members")
                members_to_process = [
                    (member['fid'], member['nickname'], member.get('furnace_lv', 0))
                    for member in members_data
                ]
            
            # Convert to tuple format for compatibility with existing code
            members = members_to_process
            
            if not members:
                # If silent_on_skip is True, we don't send any message if there's no work to do
                if silent_on_skip:
                    self.logger.info(f"✅ Silent skip: All {len(members_data)} members have already redeemed code {giftcode} for guild {guild_id}")
                    return

                self.logger.info(f"✅ All {len(members_data)} members have already redeemed code {giftcode} for guild {guild_id}")
                # Send a message to the channel
                try:
                    skip_embed = discord.Embed(
                        title="🎁 Auto-Redeem Skipped",
                        description=(
                            f"```ansi\n"
                            f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                            f"\u001b[1;37mGift Code: {giftcode}\u001b[0m\n"
                            f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                            f"```\n"
                            f"✅ **All {len(members_data)} members have already redeemed this code!**\n"
                            f"⏰ **Checked:** <t:{int(datetime.now().timestamp())}:R>\n"
                        ),
                        color=0x57F287
                    )
                    await channel.send(embed=skip_embed)
                except Exception:
                    pass
                return
            
            self.logger.info(f"📊 Processing {len(members)} members (skipped {skipped_count} already redeemed)")
            
            # Send initial animation message
            initial_embed = discord.Embed(
                title="🎁 Auto-Redeem Started",
                description=(
                    f"```ansi\n"
                    f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                    f"\u001b[1;37mGift Code: {giftcode}\u001b[0m\n"
                    f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                    f"```\n"
                    f"👥 **Members:** {len(members)}\n"
                    f"⏭️ **Skipped:** {skipped_count} (already redeemed)\n"
                    f"⏳ **Status:** Processing...\n"
                    f"🏰 **Server:** {channel.guild.name}\n"
                ),
                color=0xFEE75C
            )
            animation_message = await channel.send(embed=initial_embed)
            
            # Shared counters for progress tracking
            success_count = 0
            failed_count = 0
            already_redeemed_count = 0
            completed_count = 0
            progress_lock = asyncio.Lock()
            
            # Semaphore to limit concurrent redemptions
            semaphore = asyncio.Semaphore(self.concurrent_redemptions)
            
            async def process_member_with_semaphore(idx, fid, nickname, furnace_lv):
                """Process a single member with semaphore control"""
                nonlocal success_count, failed_count, already_redeemed_count, completed_count
                
                # Check for stop signal
                if self.stop_signals.get(guild_id):
                    return
                
                async with semaphore:
                    # Double check after acquiring semaphore
                    if self.stop_signals.get(guild_id):
                        return
                    # Process the member
                    status, success, already_redeemed, failed = await self._redeem_for_member(
                        guild_id, fid, nickname, furnace_lv, giftcode
                    )
                    
                    # Update counters
                    async with progress_lock:
                        success_count += success
                        already_redeemed_count += already_redeemed
                        failed_count += failed
                        completed_count += 1
                        
                        # Update progress message after each completion
                        try:
                            # Calculate progress percentage and create visual bar
                            progress_percent = (completed_count / len(members)) * 100
                            bar_length = 20
                            filled_length = int(bar_length * completed_count / len(members))
                            progress_bar = '█' * filled_length + '░' * (bar_length - filled_length)
                            
                            progress_embed = discord.Embed(
                                title="🎁 Auto-Redeem In Progress",
                                description=(
                                    f"```ansi\n"
                                    f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                                    f"\u001b[1;37mGift Code: {giftcode}\u001b[0m\n"
                                    f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                                    f"```\n"
                                    f"**Progress:** `{progress_bar}` **{progress_percent:.1f}%**\n"
                                    f"📊 **Processed:** {completed_count}/{len(members)}\n\n"
                                    f"✅ **Success:** {success_count}\n"
                                    f"ℹ️ **Already Redeemed:** {already_redeemed_count}\n"
                                    f"❌ **Failed:** {failed_count}\n"
                                    f"🏰 **Server:** {channel.guild.name}\n"
                                ),
                                color=0x5865F2
                            )
                            await animation_message.edit(embed=progress_embed)
                        except Exception as e:
                            self.logger.warning(f"Failed to update progress message: {e}")
            
            # Create tasks for all members
            tasks = [
                process_member_with_semaphore(idx, fid, nickname, furnace_lv)
                for idx, (fid, nickname, furnace_lv) in enumerate(members, 1)
            ]
            
            # Process all members concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Send final completion message
            final_embed = discord.Embed(
                title="🎁 Auto-Redeem Complete",
                description=(
                    f"```ansi\n"
                    f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                    f"\u001b[1;37mGift Code: {giftcode}\u001b[0m\n"
                    f"\u001b[2;36m━━━━━━━━━━━━━━━━━━━━━━\u001b[0m\n"
                    f"```\n"
                    f"✅ **Success:** {success_count}\n"
                    f"ℹ️ **Already Redeemed:** {already_redeemed_count}\n"
                    f"❌ **Failed:** {failed_count}\n"
                    f"⏰ **Completed:** <t:{int(datetime.now().timestamp())}:R>\n"
                ),
                color=0x57F287
            )
            await animation_message.edit(embed=final_embed)
            
            self.logger.info(f"Auto-redeem completed for guild {guild_id}: {success_count} success, {already_redeemed_count} already redeemed, {failed_count} failed")
            
        except Exception as e:
            self.logger.exception(f"Error in process_auto_redeem: {e}")
        finally:
            # Always release the lock
            async with self._redemption_lock:
                redemption_key = (guild_id, giftcode)
                if redemption_key in self._active_redemptions:
                    self._active_redemptions.discard(redemption_key)
                    self.logger.info(f"🔓 Unlocked auto-redeem for guild {guild_id} with code {giftcode}")
            
            # NOTE: Code is NOT marked as processed here to allow multiple guilds to process the same code
            # Code will be marked as processed by trigger_auto_redeem_for_new_codes after all guilds finish
    
    def encode_data(self, data_dict):
        """Encode data for WOS API requests"""
        import hashlib
        import urllib.parse
        
        # Sort keys and create form string
        sorted_keys = sorted(data_dict.keys())
        form_parts = [f"{key}={data_dict[key]}" for key in sorted_keys]
        form = "&".join(form_parts)
        
        # Create signature
        sign = hashlib.md5((form + self.wos_encrypt_key).encode('utf-8')).hexdigest()
        
        # Return encoded data
        return f"sign={sign}&{form}"
    
    async def fetch_captcha(self, player_id, session):
        """Fetch CAPTCHA image from WOS API"""
        try:
            import time
            
            data_to_encode = {
                "fid": str(player_id),
                "time": str(int(time.time() * 1000))
            }
            data = self.encode_data(data_to_encode)
            
            # Run synchronous request in thread pool to avoid blocking
            def _fetch():
                try:
                    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                    response = session.post(self.wos_captcha_url, headers=headers, data=data, timeout=10)
                    return response, None
                except Exception as e:
                    return None, str(e)
            
            response, error = await asyncio.to_thread(_fetch)
            
            if error:
                self.logger.error(f"Request error in fetch_captcha for FID {player_id}: {error}")
                return None, f"Request Error: {error}"
            
            # Check for rate limiting (HTTP 429)
            if response.status_code == 429:
                self.logger.warning(f"Rate limited (429) in fetch_captcha for FID {player_id}")
                return None, "RATE_LIMITED"
            
            if response.status_code == 200:
                try:
                    response_json = response.json()
                    if response_json.get("msg") == "SUCCESS":  # API returns uppercase SUCCESS
                        return response_json.get("data"), None
                    elif response_json.get("msg") == "CAPTCHA GET TOO FREQUENT":
                        return None, "CAPTCHA_TOO_FREQUENT"
                    else:
                        self.logger.warning(f"CAPTCHA API returned: {response_json.get('msg', 'Unknown')}")
                        return None, f"API Error: {response_json.get('msg', 'Unknown')}"
                except Exception as json_error:
                    # Check if response is HTML (rate limit error page)
                    if response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                        self.logger.warning(f"Received HTML error page (likely rate limited) for FID {player_id}")
                        return None, "RATE_LIMITED"
                    self.logger.error(f"JSON parse error in fetch_captcha: {json_error}, Response: {response.text[:200]}")
                    return None, "Invalid JSON response"
            else:
                self.logger.error(f"HTTP error in fetch_captcha: {response.status_code}, Response: {response.text[:200]}")
                return None, f"HTTP {response.status_code}"
                
        except Exception as e:
            self.logger.exception(f"Unexpected error in fetch_captcha for FID {player_id}: {e}")
            return None, str(e)
    
    async def attempt_gift_code_with_api(self, player_id, giftcode, session):
        """Attempt to redeem a gift code with CAPTCHA solving"""
        import time
        import base64
        import random
        
        if not self.captcha_solver or not self.captcha_solver.is_initialized:
            return "CAPTCHA_SOLVER_NOT_AVAILABLE", None, None, None
        
        max_ocr_attempts = 4
        
        for attempt in range(max_ocr_attempts):
            self.logger.info(f"Attempt {attempt + 1}/{max_ocr_attempts} to redeem for FID {player_id}")
            
            # Fetch captcha
            captcha_image_base64, error = await self.fetch_captcha(player_id, session)
            
            if error:
                if error == "CAPTCHA_TOO_FREQUENT":
                    return "CAPTCHA_TOO_FREQUENT", None, None, None
                else:
                    return "CAPTCHA_FETCH_ERROR", None, None, None
            
            if not captcha_image_base64:
                return "CAPTCHA_FETCH_ERROR", None, None, None
            
            # Decode captcha image
            try:
                # API returns dict with 'img' key containing base64 data
                if isinstance(captcha_image_base64, dict):
                    img_b64_data = captcha_image_base64.get('img', '')
                    # Strip data:image prefix if present
                    if img_b64_data.startswith("data:image"):
                        img_b64_data = img_b64_data.split(",", 1)[1]
                elif isinstance(captcha_image_base64, str):
                    if captcha_image_base64.startswith("data:image"):
                        img_b64_data = captcha_image_base64.split(",", 1)[1]
                    else:
                        img_b64_data = captcha_image_base64
                else:
                    self.logger.error(f"Unexpected CAPTCHA data type: {type(captcha_image_base64)}")
                    return "CAPTCHA_FETCH_ERROR", None, None, None
                
                if not img_b64_data:
                    self.logger.error("CAPTCHA image data is empty")
                    return "CAPTCHA_FETCH_ERROR", None, None, None
                
                image_bytes = base64.b64decode(img_b64_data)
            except Exception as e:
                self.logger.error(f"Failed to decode base64 image: {e}")
                return "CAPTCHA_FETCH_ERROR", None, None, None
            
            # Solve captcha
            captcha_code, success, method, confidence, _ = await self.captcha_solver.solve_captcha(
                image_bytes, fid=player_id, attempt=attempt)
            
            if not success:
                if attempt == max_ocr_attempts - 1:
                    return "MAX_CAPTCHA_ATTEMPTS_REACHED", None, None, None
                continue
            
            self.logger.info(f"OCR solved: {captcha_code} (method:{method}, conf:{confidence:.2f})")
            
            # Submit gift code with solved captcha
            data_to_encode = {
                "fid": str(player_id),
                "cdk": giftcode,
                "captcha_code": captcha_code,
                "time": str(int(time.time() * 1000))
            }
            data = self.encode_data(data_to_encode)
            
            # Run synchronous request in thread pool
            def _submit():
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                return session.post(self.wos_giftcode_url, headers=headers, data=data)
            
            response = await asyncio.to_thread(_submit)
            
            try:
                response_json = response.json()
                msg = response_json.get("msg", "Unknown Error").strip('.')
                err_code = response_json.get("err_code")
                
                # Check for captcha errors
                captcha_errors = {
                    ("CAPTCHA CHECK ERROR", 40103),
                    ("CAPTCHA GET TOO FREQUENT", 40100),
                    ("CAPTCHA CHECK TOO FREQUENT", 40101),
                    ("CAPTCHA EXPIRED", 40102)
                }
                
                is_captcha_error = (msg, err_code) in captcha_errors
                
                if is_captcha_error:
                    if attempt == max_ocr_attempts - 1:
                        return "CAPTCHA_INVALID", image_bytes, captcha_code, method
                    else:
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                        continue
                
                # Determine final status
                if msg == "SUCCESS":
                    return "SUCCESS", image_bytes, captcha_code, method
                elif msg == "RECEIVED" and err_code == 40008:
                    return "ALREADY_RECEIVED", image_bytes, captcha_code, method
                elif msg == "SAME TYPE EXCHANGE" and err_code == 40011:
                    return "SAME TYPE EXCHANGE", image_bytes, captcha_code, method
                elif msg == "TIME ERROR" and err_code == 40007:
                    return "TIME_ERROR", image_bytes, captcha_code, method
                elif msg == "CDK NOT FOUND" and err_code == 40014:
                    return "CDK_NOT_FOUND", image_bytes, captcha_code, method
                elif msg == "USAGE LIMIT" and err_code == 40009:
                    return "USAGE_LIMIT", image_bytes, captcha_code, method
                else:
                    return f"UNKNOWN_STATUS_{msg}", image_bytes, captcha_code, method
                    
            except Exception as e:
                self.logger.exception(f"Error parsing response: {e}")
                return "RESPONSE_PARSE_ERROR", None, None, None
        
        return "MAX_ATTEMPTS_REACHED", None, None, None
    
    async def get_stove_info_wos(self, player_id):
        """Get player session for WOS API calls"""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        import time
        
        # Run session creation in thread pool to avoid blocking
        def _create_session():
            # Create session with retry strategy
            session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Get player info to establish session
            data_to_encode = {
                "fid": str(player_id),
                "time": str(int(time.time() * 1000))
            }
            data = self.encode_data(data_to_encode)
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = session.post(self.wos_player_info_url, headers=headers, data=data, timeout=10)
            
            return session, response
        
        return await asyncio.to_thread(_create_session)
    
    
    async def _wait_for_rate_limit(self):
        """Enforce rate limiting between API calls"""
        now = datetime.now().timestamp()
        time_since_last_call = now - self.last_api_call
        
        if time_since_last_call < self.min_api_call_interval:
            sleep_time = self.min_api_call_interval - time_since_last_call
            sleep_time += random.uniform(0, 0.5)
            await asyncio.sleep(sleep_time)
            
        self.last_api_call = datetime.now().timestamp()
    
    async def fetch_codes_from_api(self):
        """Fetch gift codes from the API"""
        try:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = {
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                }
                
                await self._wait_for_rate_limit()
                
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status != 200:
                        self.logger.error(f"API request failed with status {response.status}")
                        return []
                    
                    response_text = await response.text()
                    result = json.loads(response_text)
                    
                    if 'error' in result or 'detail' in result:
                        error_msg = result.get('error', result.get('detail', 'Unknown error'))
                        self.logger.error(f"API returned error: {error_msg}")
                        return []
                    
                    api_giftcodes = result.get('codes', [])
                    self.logger.info(f"Fetched {len(api_giftcodes)} codes from API")
                    
                    # Parse codes
                    valid_codes = []
                    for code_line in api_giftcodes:
                        parts = code_line.strip().split()
                        if len(parts) != 2:
                            continue
                        
                        code, date_str = parts
                        if not re.match("^[a-zA-Z0-9]+$", code):
                            continue
                        
                        try:
                            date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                            valid_codes.append((code, date_obj.strftime("%Y-%m-%d")))
                        except ValueError:
                            continue
                    
                    return valid_codes
        except Exception as e:
            self.logger.exception(f"Error fetching codes from API: {e}")
            return []
    
    async def check_giftcode_in_api(self, giftcode: str) -> bool:
        """Check if a gift code exists in the API"""
        try:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = {
                    'X-API-Key': self.api_key
                }
                
                await self._wait_for_rate_limit()
                
                async with session.get(f"{self.api_url}?action=check&giftcode={giftcode}", headers=headers) as response:
                    if response.status == 200:
                        try:
                            result = await response.json()
                            exists = result.get('exists', False)
                            self.logger.info(f"Checked code {giftcode} in API: exists={exists}")
                            return exists
                        except json.JSONDecodeError:
                            self.logger.warning(f"Invalid JSON response when checking code {giftcode}")
                            return False
                    else:
                        self.logger.warning(f"Failed to check code {giftcode}: {response.status}")
                        return False
        except Exception as e:
            self.logger.exception(f"Error checking code {giftcode} in API: {e}")
            return False
    
    async def add_giftcode_to_api(self, giftcode: str) -> bool:
        """Add a gift code to the API"""
        try:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                headers = {
                    'Content-Type': 'application/json',
                    'X-API-Key': self.api_key
                }
                
                date_str = datetime.now().strftime("%d.%m.%Y")
                data = {
                    'code': giftcode,
                    'date': date_str
                }
                
                await self._wait_for_rate_limit()
                
                async with session.post(self.api_url, json=data, headers=headers) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            result = json.loads(response_text)
                            if result.get('success') == True:
                                self.logger.info(f"Successfully added code {giftcode} to API")
                                return True
                            else:
                                self.logger.warning(f"API didn't confirm success for code {giftcode}: {response_text[:200]}")
                                return False
                        except json.JSONDecodeError:
                            self.logger.warning(f"Invalid JSON response when adding code {giftcode}: {response_text[:200]}")
                            return False
                    elif response.status == 409:
                        # Code already exists in API - consider this a success
                        self.logger.info(f"Code {giftcode} already exists in API")
                        return True
                    else:
                        self.logger.warning(f"Failed to add code {giftcode} to API: {response.status}, {response_text[:200]}")
                        if "invalid" in response_text.lower():
                            self.logger.warning(f"Code {giftcode} marked invalid by API")
                        return False
        except Exception as e:
            self.logger.exception(f"Error adding code {giftcode} to API: {e}")
            return False
    
    @tasks.loop(seconds=60)  # Check every minute
    async def api_check_task(self):
        """Periodically check API for new gift codes"""
        try:
            self.logger.info("Starting API check for new gift codes")
            
            # Fetch codes from API
            api_codes = await self.fetch_codes_from_api()
            
            if not api_codes:
                self.logger.warning("No codes fetched from API - API might be empty or down")
                return
            
            self.logger.info(f"Successfully fetched {len(api_codes)} codes from API")
            
            # Get existing codes from database
            self.cursor.execute("SELECT giftcode FROM gift_codes")
            db_codes = {row[0] for row in self.cursor.fetchall()}
            self.logger.info(f"Found {len(db_codes)} existing codes in database")
            
            # Find new codes
            new_codes = []
            for code, date in api_codes:
                if code not in db_codes:
                    new_codes.append((code, date))
            
            if not new_codes:
                self.logger.info(f"No new codes found. All {len(api_codes)} API codes already in database")
                return
            
            self.logger.info(f"Found {len(new_codes)} new gift codes!")
            
            # Add new codes to database with auto_redeem_processed = 0
            for code, date in new_codes:
                try:
                    # Insert into SQLite
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO gift_codes (giftcode, date, validation_status, added_at, auto_redeem_processed) VALUES (?, ?, ?, ?, ?)",
                        (code, date, "validated", datetime.now(), 0)
                    )
                    self.logger.info(f"Added new code to SQLite: {code}")
                    
                    # CRITICAL: Also insert into MongoDB if enabled
                    if mongo_enabled() and GiftCodesAdapter and _get_db:
                        try:
                            # Insert the code with auto_redeem_processed = False
                            db = _get_db()
                            if db:
                                db[GiftCodesAdapter.COLL].update_one(
                                    {'_id': code},
                                    {
                                        '$set': {
                                            'date': date,
                                            'validation_status': 'validated',
                                            'auto_redeem_processed': False,
                                            'created_at': datetime.utcnow().isoformat(),
                                            'updated_at': datetime.utcnow().isoformat()
                                        }
                                    },
                                    upsert=True
                                )
                                self.logger.info(f"✅ Added new code to MongoDB: {code}")
                        except Exception as mongo_err:
                            self.logger.error(f"⚠️ Failed to add code {code} to MongoDB: {mongo_err}")
                            # Continue anyway - SQLite is the fallback
                    
                except Exception as e:
                    self.logger.error(f"Error inserting code {code}: {e}")
            
            self.giftcode_db.commit()
            self.logger.info(f"Committed {len(new_codes)} new codes to database")
            
            # Notify global admins
            await self.notify_admins_new_codes(new_codes)
            
            # CRITICAL: Trigger auto-redeem for the new codes
            self.logger.info(f"🔔 Triggering auto-redeem for {len(new_codes)} new codes from API...")
            await self.trigger_auto_redeem_for_new_codes(new_codes)
            
        except Exception as e:
            self.logger.exception(f"Error in API check task: {e}")
    
    @api_check_task.before_loop
    async def before_api_check(self):
        """Wait for bot to be ready before starting API checks"""
        await self.bot.wait_until_ready()
        self.logger.info("Gift code API check task started")
        
        # Cleanup members with null/empty FIDs from all guilds
        self.logger.info("🧹 Cleaning up members with null/empty FIDs...")
        cleanup_count = self.AutoRedeemDB.cleanup_null_members(self)
        if cleanup_count > 0:
            self.logger.info(f"✅ Removed {cleanup_count} invalid members from auto-redeem lists")
        
        # Sync auto-redeem settings from SQLite to MongoDB (for migration on first startup)
        await self.sync_auto_redeem_settings_to_mongo()
        
        # Sync gift codes from MongoDB to SQLite (CRITICAL for Render persistence)
        # This prevents the bot from thinking all existing codes are "new" on restart
        await self.sync_gift_codes_from_mongo_to_sqlite()
        
        # Process any existing unprocessed codes on startup (mark as processed, don't redeem)
        await self.process_existing_codes_on_startup()
    
    async def sync_auto_redeem_settings_to_mongo(self):
        """
        Sync auto-redeem settings from SQLite to MongoDB on startup.
        This ensures persistence even after SQLite resets on Render.
        """
        try:
            if not mongo_enabled() or not AutoRedeemSettingsAdapter:
                self.logger.info("⏭️ MongoDB not enabled, skipping auto-redeem settings sync")
                return
            
            self.logger.info("🔄 === SYNCING AUTO-REDEEM SETTINGS TO MONGODB ===")
            
            # Read ALL enabled guilds from SQLite
            try:
                self.cursor.execute("""
                    SELECT guild_id, enabled, updated_by, updated_at
                    FROM auto_redeem_settings
                    WHERE enabled = 1
                """)
                sqlite_settings = self.cursor.fetchall()
                self.logger.info(f"📂 SQLite: Found {len(sqlite_settings)} enabled guilds")
            except Exception as e:
                self.logger.error(f"❌ Error reading SQLite settings: {e}")
                sqlite_settings = []
            
            if not sqlite_settings:
                self.logger.info("ℹ️ No enabled guilds in SQLite to sync")
                # Also check MongoDB for existing settings
                try:
                    mongo_settings = AutoRedeemSettingsAdapter.get_all_settings()
                    if mongo_settings:
                        enabled_count = sum(1 for s in mongo_settings if s.get('enabled', False))
                        self.logger.info(f"✅ MongoDB already has {enabled_count} enabled guilds (out of {len(mongo_settings)} total)")
                except Exception as e:
                    self.logger.error(f"❌ Error checking MongoDB settings: {e}")
                return
            
            # Sync each enabled setting to MongoDB
            synced_count = 0
            for row in sqlite_settings:
                guild_id = row[0]
                enabled = bool(row[1])
                updated_by = row[2] if len(row) > 2 else 0
                
                # Check if already exists in MongoDB
                existing = AutoRedeemSettingsAdapter.get_settings(guild_id)
                
                if existing and existing.get('enabled', False):
                    self.logger.debug(f"ℹ️ Guild {guild_id} already enabled in MongoDB, skipping")
                    continue
                
                # Sync to MongoDB
                try:
                    success = AutoRedeemSettingsAdapter.set_enabled(
                        guild_id,
                        enabled,
                        updated_by or 0
                    )
                    if success:
                        synced_count += 1
                        self.logger.info(f"✅ Synced guild {guild_id} auto-redeem settings to MongoDB")
                    else:
                        self.logger.warning(f"⚠️ Failed to sync guild {guild_id} to MongoDB")
                except Exception as e:
                    self.logger.error(f"❌ Error syncing guild {guild_id}: {e}")
            
            self.logger.info(f"🎉 Synced {synced_count} guild(s) to MongoDB")
            self.logger.info("🏁 === AUTO-REDEEM SETTINGS SYNC COMPLETE ===")
        except Exception as e:
            self.logger.exception(f"❌ Error syncing auto-redeem settings: {e}")

    async def sync_gift_codes_from_mongo_to_sqlite(self):
        """
        Sync gift codes from MongoDB to SQLite on startup.
        This ensures that when the bot restarts on a platform like Render (where SQLite is ephemeral),
        it doesn't treat all old codes as 'new' and incorrectly trigger auto-redeem.
        """
        try:
            if not mongo_enabled() or not GiftCodesAdapter:
                self.logger.info("⏭️ MongoDB not enabled or GiftCodesAdapter missing, skipping code sync")
                return

            self.logger.info("🔄 === SYNCING GIFT CODES FROM MONGODB TO SQLITE ===")
            
            # Fetch all codes from MongoDB
            mongo_codes = GiftCodesAdapter.get_all_with_status()
            if not mongo_codes:
                self.logger.info("ℹ️ MongoDB has no gift codes to sync")
                return
            
            self.logger.info(f"📊 Found {len(mongo_codes)} gift codes in MongoDB")
            
            # Get existing codes in SQLite to avoid duplicates/unnecessary writes
            self.cursor.execute("SELECT giftcode FROM gift_codes")
            sqlite_codes = {row[0] for row in self.cursor.fetchall()}
            
            synced_count = 0
            new_count = 0
            
            for code_data in mongo_codes:
                code = code_data.get('giftcode')
                date = code_data.get('date', '')
                validation_status = code_data.get('validation_status', 'validated')
                auto_redeem_processed = code_data.get('auto_redeem_processed', False)
                
                # Convert boolean to integer for SQLite (0/1)
                processed_int = 1 if auto_redeem_processed else 0
                
                if code in sqlite_codes:
                    # Update status of existing code if needed (e.g., if it was processed in Mongo but not SQLite)
                    self.cursor.execute(
                        "UPDATE gift_codes SET auto_redeem_processed = ? WHERE giftcode = ? AND auto_redeem_processed != ?",
                        (processed_int, code, processed_int)
                    )
                    if self.cursor.rowcount > 0:
                        synced_count += 1
                else:
                    # Insert new code into SQLite
                    try:
                        added_at = code_data.get('created_at') or datetime.now()
                        self.cursor.execute(
                            "INSERT INTO gift_codes (giftcode, date, validation_status, added_at, auto_redeem_processed) VALUES (?, ?, ?, ?, ?)",
                            (code, date, validation_status, added_at, processed_int)
                        )
                        new_count += 1
                    except Exception as e:
                        self.logger.error(f"❌ Failed to insert code {code} into SQLite: {e}")
            
            self.giftcode_db.commit()
            
            if new_count > 0 or synced_count > 0:
                self.logger.info(f"✅ Imported {new_count} new codes and updated {synced_count} statuses from MongoDB")
            else:
                self.logger.info("✅ SQLite already in sync with MongoDB")
                
            self.logger.info("🏁 === CODE SYNC COMPLETE ===")
            
        except Exception as e:
            self.logger.exception(f"❌ CRITICAL ERROR syncing codes from MongoDB: {e}")
    
    async def process_existing_codes_on_startup(self):
        """
        Check for existing codes that haven't been marked as processed and mark them.
        NOTE: We intentionally do NOT trigger auto-redeem on startup.
        Auto-redeem should only trigger for truly NEW codes from the API, not on bot restart.
        """
        try:
            # Add a small delay to ensure bot is fully ready
            await asyncio.sleep(5)
            
            self.logger.info("🚀 === STARTUP CODE PROCESSING ===")
            self.logger.info("Marking existing unprocessed gift codes as processed (no auto-redeem on startup)...")
            
            unprocessed_codes = []
            
            # Try MongoDB first - use the new get_all_with_status() method
            mongo_attempted = False
            if mongo_enabled() and GiftCodesAdapter:
                try:
                    mongo_attempted = True
                    self.logger.info("📊 Attempting to fetch codes from MongoDB...")
                    # Get all codes from MongoDB with their auto_redeem_processed status
                    all_codes = GiftCodesAdapter.get_all_with_status()
                    if all_codes:
                        # Filter for unprocessed codes
                        unprocessed_codes = [
                            (code['giftcode'], code.get('date', ''))
                            for code in all_codes
                            if not code.get('auto_redeem_processed', False)
                        ]
                        self.logger.info(f"✅ MongoDB: Found {len(unprocessed_codes)} unprocessed out of {len(all_codes)} total codes")
                        if unprocessed_codes:
                            self.logger.info(f"📝 Unprocessed codes: {[c[0] for c in unprocessed_codes]}")
                    else:
                        self.logger.info("ℹ️ MongoDB: No codes in collection")
                except Exception as e:
                    self.logger.warning(f"⚠️ MongoDB failed: {e}, falling back to SQLite")
            elif mongo_enabled():
                self.logger.warning("⚠️ MongoDB enabled but GiftCodesAdapter unavailable")
            else:
                self.logger.info("ℹ️ MongoDB not enabled, using SQLite")
            
            # Fallback to SQLite if MongoDB failed or not enabled
            if not unprocessed_codes and (not mongo_enabled() or not GiftCodesAdapter or not mongo_attempted):
                try:
                    self.logger.info("📂 Fetching codes from SQLite database...")
                    self.cursor.execute("""
                        SELECT giftcode, date 
                        FROM gift_codes 
                        WHERE auto_redeem_processed = 0 OR auto_redeem_processed IS NULL
                        ORDER BY added_at DESC
                    """)
                    unprocessed_codes = self.cursor.fetchall()
                    self.logger.info(f"✅ SQLite: Found {len(unprocessed_codes)} unprocessed codes")
                    if unprocessed_codes:
                        self.logger.info(f"📝 Unprocessed codes: {[c[0] for c in unprocessed_codes]}")
                except Exception as e:
                    self.logger.error(f"❌ SQLite fetch failed: {e}")
            
            if not unprocessed_codes:
                self.logger.info("✅ No unprocessed codes found (all codes processed or DB empty)")
                self.logger.info("🏁 === STARTUP CODE PROCESSING COMPLETE ===")
                return
            
            self.logger.info(f"📋 FOUND {len(unprocessed_codes)} UNPROCESSED CODES - MARKING AS PROCESSED (no auto-redeem on startup)")
            
            # Mark all unprocessed codes as processed WITHOUT triggering auto-redeem
            # This prevents startup redemption while allowing new codes from API to trigger auto-redeem
            for code, date in unprocessed_codes:
                try:
                    # Mark in MongoDB if available
                    if mongo_enabled() and GiftCodesAdapter:
                        try:
                            GiftCodesAdapter.mark_code_processed(code)
                            self.logger.info(f"✅ Marked {code} as processed in MongoDB")
                        except Exception as e:
                            self.logger.error(f"❌ Failed to mark code in MongoDB: {e}")
                    
                    # Also mark in SQLite for consistency
                    try:
                        self.cursor.execute(
                            "UPDATE gift_codes SET auto_redeem_processed = 1 WHERE giftcode = ?",
                            (code,)
                        )
                        self.giftcode_db.commit()
                        self.logger.info(f"✅ Marked {code} as processed in SQLite")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to mark code in SQLite: {e}")
                except Exception as e:
                    self.logger.error(f"❌ Error marking code {code} as processed: {e}")
            
            self.logger.info(f"✅ Marked {len(unprocessed_codes)} existing codes as processed (auto-redeem skipped on startup)")
            self.logger.info("🏁 === STARTUP CODE PROCESSING COMPLETE ===")
            
        except Exception as e:
            self.logger.exception(f"❌ CRITICAL ERROR in startup auto-redeem check: {e}")
    
    async def notify_admins_new_codes(self, new_codes):
        """Notify global administrators about new gift codes"""
        try:
            # Get global admin IDs
            self.settings_cursor.execute("SELECT id FROM admin WHERE is_initial = 1")
            admin_ids = self.settings_cursor.fetchall()
            
            if not admin_ids:
                self.logger.info("No global admins found to notify")
                return
            
            for code, date in new_codes:
                embed = discord.Embed(
                    title="🎁 New Gift Code Detected!",
                    description=(
                        f"**Gift Code Details**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎁 **Code:** `{code}`\n"
                        f"📅 **Date:** `{date}`\n"
                        f"📝 **Source:** `Bot API`\n"
                        f"⏰ **Detected:** <t:{int(datetime.now().timestamp())}:R>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"\n🤖 **Auto-redeem is now active for enabled servers!**"
                    ),
                    color=discord.Color.green()
                )
                
                for admin_id in admin_ids:
                    try:
                        admin_user = await self.bot.fetch_user(admin_id[0])
                        if admin_user:
                            await admin_user.send(embed=embed)
                            self.logger.info(f"Notified admin {admin_id[0]} about new code {code}")
                    except Exception as e:
                        self.logger.error(f"Error notifying admin {admin_id[0]}: {e}")
            
            # Trigger auto-redeem for all guilds that have it enabled
            await self.trigger_auto_redeem_for_new_codes(new_codes)
        
        except Exception as e:
            self.logger.exception(f"Error notifying admins: {e}")
    
    async def trigger_auto_redeem_for_new_codes(self, new_codes):
        """Trigger auto-redeem for all guilds with auto-redeem enabled"""
        try:
            self.logger.info("🔔 === TRIGGER AUTO-REDEEM ===")
            self.logger.info(f"📥 Received {len(new_codes)} codes to process: {[c[0] for c in new_codes]}")
            
            # Get all guilds with auto-redeem enabled
            enabled_guilds = []
            
            # Try MongoDB first - but check if method exists
            mongo_attempted = False
            if mongo_enabled() and AutoRedeemSettingsAdapter:
                # Check if get_all_settings method exists
                if hasattr(AutoRedeemSettingsAdapter, 'get_all_settings'):
                    try:
                        mongo_attempted = True
                        self.logger.info("📊 Checking MongoDB for enabled guilds...")
                        # Get all guilds with auto-redeem enabled from MongoDB
                        all_settings = AutoRedeemSettingsAdapter.get_all_settings()
                        if all_settings:
                            self.logger.info(f"📋 Found {len(all_settings)} total guild settings in MongoDB")
                            enabled_guilds = [
                                (settings['guild_id'],)
                                for settings in all_settings
                                if settings.get('enabled', False)
                            ]
                            self.logger.info(f"✅ MongoDB: {len(enabled_guilds)} guilds with auto-redeem ENABLED")
                            if enabled_guilds:
                                self.logger.info(f"📝 Enabled guild IDs: {[g[0] for g in enabled_guilds]}")
                            else:
                                self.logger.warning("⚠️ MongoDB: No guilds have auto-redeem enabled!")
                        else:
                            self.logger.warning("⚠️ MongoDB: No settings found (empty collection)")
                    except Exception as e:
                        self.logger.error(f"❌ MongoDB get_all_settings failed: {e}")
                        mongo_attempted = False  # Force SQLite fallback
                else:
                    self.logger.info("ℹ️ MongoDB: get_all_settings() method not available, using SQLite...")
            elif mongo_enabled():
                self.logger.warning("⚠️ MongoDB enabled but AutoRedeemSettingsAdapter unavailable")
            else:
                self.logger.info("ℹ️ MongoDB not enabled, checking SQLite...")
            
            # Fallback to SQLite if MongoDB failed or not enabled
            if not enabled_guilds:
                try:
                    self.logger.info("📂 Checking SQLite for enabled guilds...")
                    self.cursor.execute("""
                        SELECT guild_id FROM auto_redeem_settings WHERE enabled = 1
                    """)
                    enabled_guilds = self.cursor.fetchall()
                    self.logger.info(f"✅ SQLite: {len(enabled_guilds)} guilds with auto-redeem ENABLED")
                    if enabled_guilds:
                        self.logger.info(f"📝 Enabled guild IDs: {[g[0] for g in enabled_guilds]}")
                    else:
                        self.logger.warning("⚠️ SQLite: No guilds have auto-redeem enabled!")
                except Exception as e:
                    self.logger.error(f"❌ SQLite query failed: {e}")
            
            if not enabled_guilds:
                self.logger.error("❌ CRITICAL: No guilds have auto-redeem enabled!")
                self.logger.error("🔍 To enable auto-redeem:")
                self.logger.error("   1. Go to Auto-Redeem Configuration menu")
                self.logger.error("   2. Click 'Enable Auto-Redeem' button")
                self.logger.error("   3. Ensure you have members added to auto-redeem list")
                self.logger.error("🏁 === TRIGGER AUTO-REDEEM COMPLETE (NO GUILDS) ===")
                return
            
            self.logger.info(f"Triggering auto-redeem for {len(enabled_guilds)} guilds with {len(new_codes)} new codes")
            
            # Process each new code for each enabled guild
            for code, date in new_codes:
                # Check if this code has already been processed for auto-redeem
                already_processed = False
                
                # Check MongoDB first
                if mongo_enabled() and GiftCodesAdapter:
                    try:
                        code_data = GiftCodesAdapter.get_code(code)
                        if code_data:
                            already_processed = code_data.get('auto_redeem_processed', False)
                    except Exception as e:
                        self.logger.warning(f"Failed to check code status in MongoDB: {e}")
                
                # Fallback to SQLite
                if not mongo_enabled() or not GiftCodesAdapter:
                    self.cursor.execute(
                        "SELECT auto_redeem_processed FROM gift_codes WHERE giftcode = ?",
                        (code,)
                    )
                    result = self.cursor.fetchone()
                    already_processed = result[0] if result and result[0] else 0
                
                is_recheck = False
                if already_processed:
                    self.logger.info(f"🔄 Triggering silent re-check for code {code} - already marked as processed but might have missed members")
                    is_recheck = True
                    # Don't skip, proceed with silent recheck
                
                self.logger.info(f"🎯 Processing code {code} for {len(enabled_guilds)} guilds... (Recheck: {is_recheck})")
                
                for (guild_id,) in enabled_guilds:
                    try:
                        # Run auto-redeem in background to avoid blocking
                        asyncio.create_task(self.process_auto_redeem(guild_id, code, silent_on_skip=is_recheck))
                        self.logger.info(f"✅ Started auto-redeem task: guild={guild_id}, code={code}")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to start auto-redeem for guild {guild_id}: {e}")
                
                self.logger.info(f"📊 Triggered auto-redeem for code {code} across {len(enabled_guilds)} guilds")
                
                # Mark code as processed after triggering for all guilds
                # This prevents re-processing on restart while allowing all guilds to process the code
                try:
                    self.logger.info(f"🏁 Marking code {code} as processed after dispatching to all guilds...")
                    
                    # Mark in MongoDB if available
                    mongo_marked = False
                    if mongo_enabled() and GiftCodesAdapter:
                        try:
                            GiftCodesAdapter.mark_code_processed(code)
                            mongo_marked = True
                            self.logger.info(f"✅ Marked {code} as processed in MongoDB")
                        except Exception as e:
                            self.logger.error(f"❌ Failed to mark code in MongoDB: {e}")
                    
                    # Also mark in SQLite for consistency
                    sqlite_marked = False
                    try:
                        self.cursor.execute(
                            "UPDATE gift_codes SET auto_redeem_processed = 1 WHERE giftcode = ?",
                            (code,)
                        )
                        self.giftcode_db.commit()
                        sqlite_marked = True
                        self.logger.info(f"✅ Marked {code} as processed in SQLite")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to mark code in SQLite: {e}")
                    
                    if not mongo_marked and not sqlite_marked:
                        self.logger.error(f"❌ CRITICAL: Failed to mark {code} as processed in ANY database!")
                    else:
                        self.logger.info(f"🎉 Successfully marked {code} as processed (MongoDB: {mongo_marked}, SQLite: {sqlite_marked})")
                except Exception as e:
                    self.logger.error(f"❌ Error marking code {code} as processed: {e}")
            
            self.logger.info(f"✅ Processed {len(new_codes)} codes for auto-redeem")
            self.logger.info("🏁 === TRIGGER AUTO-REDEEM COMPLETE ===")
        
        except Exception as e:
            self.logger.exception(f"Error triggering auto-redeem: {e}")
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle gift code management interactions"""
        if not interaction.type == discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        
        # Handle gift code menu button
        if custom_id == "giftcode_menu":
            # Check admin permissions
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can access Gift Code Management.",
                    ephemeral=True
                )
                return
            
            # Create Gift Code Management submenu
            embed = discord.Embed(
                title="🎁 Gift Code Management",
                description=(
                    "```ansi\n"
                    "\u001b[2;36m╔═══════════════════════════════════╗\n"
                    "\u001b[2;36m║  \u001b[1;37mGIFT CODE OPERATIONS\u001b[0m\u001b[2;36m          ║\n"
                    "\u001b[2;36m╚═══════════════════════════════════╝\u001b[0m\n"
                    "```\n"
                    "**Manage gift codes for your server**\n\n"
                    "🔄 **Auto-Fetch:** Checking API every minute\n"
                    "📡 **API Status:** Connected\n\n"
                    "Available operations:\n"
                    "• View active gift codes\n"
                    "• Add new gift codes\n"
                    "• View gift code history\n"
                    "• Configure auto-redeem members\n"
                ),
                color=0x2B2D31
            )
            embed.set_footer(
                text=f"{interaction.guild.name} x Magnus🚀",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="View Codes",
                emoji="👁️",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_view_codes",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Add Code",
                emoji="➕",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_add_code",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Auto Redeem",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="giftcode_auto_redeem",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="History",
                emoji="📜",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_history",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="Refresh API",
                emoji="🔄",
                style=discord.ButtonStyle.primary,
                custom_id="giftcode_refresh_api",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="◀ Back",
                emoji="🏠",
                style=discord.ButtonStyle.secondary,
                custom_id="return_to_manage",
                row=2
            ))
            
            await interaction.response.edit_message(embed=embed, view=view)
            return
        
        # Handle view codes button
        if custom_id == "giftcode_view_codes":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can view gift codes.",
                    ephemeral=True
                )
                return
            
            # Get active gift codes
            try:
                # Try with all columns first
                self.cursor.execute("""
                    SELECT giftcode, 
                           COALESCE(date, 'Unknown') as date, 
                           COALESCE(validation_status, 'pending') as validation_status,
                           COALESCE(added_at, date) as added_at
                    FROM gift_codes
                    WHERE COALESCE(validation_status, 'pending') != 'invalid'
                    ORDER BY COALESCE(added_at, date, giftcode) DESC
                    LIMIT 25
                """)
            except sqlite3.OperationalError:
                # Fallback to basic query if columns don't exist
                self.cursor.execute("""
                    SELECT giftcode, 
                           COALESCE(date, 'Unknown') as date,
                           'validated' as validation_status,
                           COALESCE(date, 'Unknown') as added_at
                    FROM gift_codes
                    LIMIT 25
                """)
            codes = self.cursor.fetchall()
            
            if not codes:
                await interaction.response.send_message(
                    "📋 No active gift codes found. The API check runs every minute.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🎁 Active Gift Codes",
                description=f"Total Active Codes: **{len(codes)}**\n━━━━━━━━━━━━━━━━━━━━━━",
                color=0x5865F2
            )
            
            for code, date, status, added_at in codes:
                status_emoji = "✅" if status == "validated" else "⚠️"
                embed.add_field(
                    name=f"{status_emoji} {code}",
                    value=f"📅 Date: `{date[:10] if date else 'Unknown'}`\n📊 Status: `{status}`",
                    inline=True
                )
            
            if len(codes) >= 25:
                embed.set_footer(text="Showing 25 most recent codes")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Handle history button
        if custom_id == "giftcode_history":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can view gift code history.",
                    ephemeral=True
                )
                return
            
            try:
                from db.mongo_adapters import mongo_enabled, GiftCodeRedemptionAdapter
                
                if not mongo_enabled():
                    await interaction.response.send_message(
                        "📊 **Usage Tracking Unavailable**\n\n"
                        "Gift code usage tracking requires MongoDB to be enabled.\n"
                        "Contact the bot administrator to enable this feature.",
                        ephemeral=True
                    )
                    return
                
                # Get usage statistics for this server
                stats = GiftCodeRedemptionAdapter.get_all_stats(interaction.guild.id)
                
                if not stats:
                    await interaction.response.send_message(
                        "📊 **No Usage Data Yet**\n\n"
                        "No gift code redemptions have been tracked for this server yet.\n"
                        "Usage statistics will appear here after codes are redeemed via auto-redeem.",
                        ephemeral=True
                    )
                    return
                
                # Build embed with statistics
                embed = discord.Embed(
                    title="📊 Gift Code Usage History",
                    description=f"Usage statistics for **{interaction.guild.name}**\n━━━━━━━━━━━━━━━━━━━━━━",
                    color=0x5865F2
                )
                
                # Show top 15 codes
                for idx, code_stats in enumerate(stats[:15], 1):
                    code = code_stats['code']
                    unique_users = code_stats['unique_users']
                    success = code_stats['success']
                    failed = code_stats['failed']
                    total = code_stats['total_attempts']
                    
                    # Calculate success rate
                    success_rate = (success / total * 100) if total > 0 else 0
                    
                    value_text = (
                        f"👥 **{unique_users}** players redeemed\n"
                        f"✅ Success: {success} | ❌ Failed: {failed}\n"
                        f"📊 Success Rate: {success_rate:.1f}%"
                    )
                    
                    embed.add_field(
                        name=f"{idx}. 🎁 {code}",
                        value=value_text,
                        inline=True
                    )
                
                if len(stats) > 15:
                    embed.set_footer(text=f"Showing top 15 of {len(stats)} codes • Sorted by most used")
                else:
                    embed.set_footer(text=f"Total: {len(stats)} codes tracked")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
                
            except Exception as e:
                self.logger.error(f"Error displaying gift code history: {e}")
                import traceback
                traceback.print_exc()
                await interaction.response.send_message(
                    "❌ An error occurred while loading gift code history.",
                    ephemeral=True
                )
                return
        
        # Handle add code button
        if custom_id == "giftcode_add_code":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can add gift codes.",
                    ephemeral=True
                )
                return
            
            class AddCodeModal(discord.ui.Modal, title="Add Gift Code"):
                code = discord.ui.TextInput(
                    label="Gift Code",
                    placeholder="Enter the gift code",
                    required=True,
                    max_length=50
                )
                
                def __init__(self, cog):
                    super().__init__()
                    self.cog = cog
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        gift_code = self.code.value.strip().upper()
                        
                        # Send initial processing message
                        processing_embed = discord.Embed(
                            title="🔄 Validating Gift Code",
                            description=f"Checking `{gift_code}` with API...",
                            color=discord.Color.blue()
                        )
                        await modal_interaction.response.send_message(embed=processing_embed, ephemeral=True)
                        
                        # Check if code already exists in database
                        self.cog.cursor.execute("SELECT validation_status FROM gift_codes WHERE giftcode = ?", (gift_code,))
                        existing = self.cog.cursor.fetchone()
                        
                        if existing:
                            status = existing[0] if existing[0] else 'unknown'
                            error_embed = discord.Embed(
                                title="ℹ️ Code Already Exists",
                                description=f"Gift code `{gift_code}` is already in the database.\n\n**Status:** `{status}`",
                                color=discord.Color.orange()
                            )
                            await modal_interaction.edit_original_response(embed=error_embed)
                            return
                        
                        # Check if code exists in API
                        exists_in_api = await self.cog.check_giftcode_in_api(gift_code)
                        
                        if exists_in_api:
                            # Code exists in API, add it to our database
                            self.cog.cursor.execute("""
                                INSERT INTO gift_codes (giftcode, date, validation_status, added_by, added_at)
                                VALUES (?, ?, ?, ?, ?)
                            """, (gift_code, datetime.now().strftime("%Y-%m-%d"), "validated", modal_interaction.user.id, datetime.now()))
                            self.cog.giftcode_db.commit()
                            
                            success_embed = discord.Embed(
                                title="✅ Gift Code Added",
                                description=(
                                    f"Successfully added gift code: `{gift_code}`\n\n"
                                    f"**Status:** Validated via API\n"
                                    f"**Added by:** {modal_interaction.user.mention}\n"
                                    f"**Date:** {datetime.now().strftime('%Y-%m-%d')}"
                                ),
                                color=discord.Color.green()
                            )
                            await modal_interaction.edit_original_response(embed=success_embed)
                        else:
                            # Code doesn't exist in API, try to add it
                            success = await self.cog.add_giftcode_to_api(gift_code)
                            
                            if success:
                                # Successfully added to API, now add to database
                                self.cog.cursor.execute("""
                                    INSERT INTO gift_codes (giftcode, date, validation_status, added_by, added_at)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (gift_code, datetime.now().strftime("%Y-%m-%d"), "validated", modal_interaction.user.id, datetime.now()))
                                self.cog.giftcode_db.commit()
                                
                                success_embed = discord.Embed(
                                    title="✅ Gift Code Added",
                                    description=(
                                        f"Successfully added new gift code: `{gift_code}`\n\n"
                                        f"**Status:** Added to API and Database\n"
                                        f"**Added by:** {modal_interaction.user.mention}\n"
                                        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}"
                                    ),
                                    color=discord.Color.green()
                                )
                                await modal_interaction.edit_original_response(embed=success_embed)
                            else:
                                # Failed to add to API - code might be invalid
                                error_embed = discord.Embed(
                                    title="❌ Invalid Gift Code",
                                    description=(
                                        f"Gift code `{gift_code}` could not be validated.\n\n"
                                        f"**Possible reasons:**\n"
                                        f"• Code is invalid or expired\n"
                                        f"• Code format is incorrect\n"
                                        f"• API rejected the code\n\n"
                                        f"Please verify the code and try again."
                                    ),
                                    color=discord.Color.red()
                                )
                                await modal_interaction.edit_original_response(embed=error_embed)
                        
                    except Exception as e:
                        self.cog.logger.exception(f"Error adding gift code: {e}")
                        error_embed = discord.Embed(
                            title="❌ Error",
                            description=f"An error occurred while adding the gift code:\n```{str(e)}```",
                            color=discord.Color.red()
                        )
                        try:
                            await modal_interaction.edit_original_response(embed=error_embed)
                        except:
                            await modal_interaction.followup.send(embed=error_embed, ephemeral=True)
            
            await interaction.response.send_modal(AddCodeModal(self))
            return
        
        # Handle history button
        if custom_id == "giftcode_history":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can view gift code history.",
                    ephemeral=True
                )
                return
            
            # Get all gift codes
            try:
                self.cursor.execute("""
                    SELECT giftcode, 
                           COALESCE(date, 'Unknown') as date, 
                           COALESCE(validation_status, 'pending') as validation_status,
                           COALESCE(added_at, date) as added_at
                    FROM gift_codes
                    ORDER BY COALESCE(added_at, date, giftcode) DESC
                    LIMIT 25
                """)
            except sqlite3.OperationalError:
                # Fallback query
                self.cursor.execute("""
                    SELECT giftcode, 
                           COALESCE(date, 'Unknown') as date,
                           'validated' as validation_status,
                           COALESCE(date, 'Unknown') as added_at
                    FROM gift_codes
                    LIMIT 25
                """)
            codes = self.cursor.fetchall()
            
            if not codes:
                await interaction.response.send_message(
                    "📋 No gift code history found.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📜 Gift Code History",
                description=f"Showing last **{len(codes)}** gift codes\n━━━━━━━━━━━━━━━━━━━━━━",
                color=0x5865F2
            )
            
            for code, date, status, added_at in codes:
                status_emoji = "✅" if status == "validated" else "❌" if status == "invalid" else "⚠️"
                embed.add_field(
                    name=f"{status_emoji} {code}",
                    value=f"📅 Date: `{date[:10] if date else 'Unknown'}`\n📊 Status: `{status}`",
                    inline=True
                )
            
            if len(codes) >= 25:
                embed.set_footer(text="Showing 25 most recent codes")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Handle refresh API button
        if custom_id == "giftcode_refresh_api":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can refresh the API.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Manually trigger API check
            try:
                api_codes = await self.fetch_codes_from_api()
                
                if not api_codes:
                    await interaction.followup.send(
                        "⚠️ No codes fetched from API. The API might be down or empty.",
                        ephemeral=True
                    )
                    return
                
                # Get existing codes
                self.cursor.execute("SELECT giftcode FROM gift_codes")
                db_codes = {row[0] for row in self.cursor.fetchall()}
                
                # Find new codes
                new_codes = [code for code, date in api_codes if code not in db_codes]
                
                embed = discord.Embed(
                    title="🔄 API Refresh Complete",
                    description=(
                        f"**Results:**\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📡 **Total API Codes:** `{len(api_codes)}`\n"
                        f"💾 **Already in DB:** `{len(api_codes) - len(new_codes)}`\n"
                        f"✨ **New Codes Found:** `{len(new_codes)}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=0x57F287 if new_codes else 0x5865F2
                )
                
                if new_codes:
                    embed.add_field(
                        name="🎁 New Codes",
                        value="\n".join([f"`{code}`" for code in new_codes[:10]]),
                        inline=False
                    )
                    if len(new_codes) > 10:
                        embed.set_footer(text=f"Showing 10 of {len(new_codes)} new codes")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Error refreshing API: {str(e)}",
                    ephemeral=True
                )
            return
        
        # Handle auto redeem button
        if custom_id == "giftcode_auto_redeem":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can manage auto-redeem settings.",
                    ephemeral=True
                )
                return
            
            # Get current member count
            self.cursor.execute("SELECT COUNT(*) FROM auto_redeem_members WHERE guild_id = ?", (interaction.guild.id,))
            member_count = self.cursor.fetchone()[0]
            
            embed = discord.Embed(
                title="🤖 Auto Redeem Management",
                description=(
                    "```ansi\n"
                    "\u001b[2;36m╔═══════════════════════════════════╗\n"
                    "\u001b[2;36m║  \u001b[1;37mAUTO REDEEM MEMBERS\u001b[0m\u001b[2;36m            ║\n"
                    "\u001b[2;36m╚═══════════════════════════════════╝\u001b[0m\n"
                    "```\n"
                    "**Configure automatic gift code redemption**\n\n"
                    f"👥 **Current Members:** `{member_count}`\n"
                    "🔄 **Status:** Active\n\n"
                    "**How it works:**\n"
                    "• Add members by FID or import from alliance\n"
                    "• New gift codes auto-redeem for all members\n"
                    "• Import from FID channel\n"
                ),
                color=0x2B2D31
            )
            embed.set_footer(
                text=f"{interaction.guild.name} x Magnus🚀",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Add Member",
                emoji="➕",
                style=discord.ButtonStyle.success,
                custom_id="auto_redeem_add_member",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Remove Member",
                emoji="➖",
                style=discord.ButtonStyle.danger,
                custom_id="auto_redeem_remove_member",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="View Members",
                emoji="👁️",
                style=discord.ButtonStyle.secondary,
                custom_id="auto_redeem_view_members",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Configure Auto Redeem",
                emoji="⚙️",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_configure_auto_redeem",
                row=1
            ))
            view.add_item(discord.ui.Button(
                label="◀ Back",
                emoji="🏠",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_menu",
                row=1
            ))
            
            await interaction.response.edit_message(embed=embed, view=view)
            return
        
        # Handle add member button - show submenu
        if custom_id == "auto_redeem_add_member":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can add members.",
                    ephemeral=True
                )
                return
            
            # Get current member count
            self.cursor.execute("SELECT COUNT(*) FROM auto_redeem_members WHERE guild_id = ?", (interaction.guild.id,))
            member_count = self.cursor.fetchone()[0]
            
            embed = discord.Embed(
                title="➕ Add Member to Auto-Redeem",
                description=(
                    "```ansi\n"
                    "\u001b[2;36m╔═══════════════════════════════════╗\n"
                    "\u001b[2;36m║  \u001b[1;37mADD MEMBER OPTIONS\u001b[0m\u001b[2;36m             ║\n"
                    "\u001b[2;36m╚═══════════════════════════════════╝\u001b[0m\n"
                    "```\n"
                    "**Choose how to add members:**\n\n"
                    f"👥 **Current Members:** `{member_count}`\n\n"
                    "**📝 Add via FID**\n"
                    "   ▸ Manually enter player FID and nickname\n"
                    "   ▸ Add one member at a time\n\n"
                    "**🤖 Import from Alliance**\n"
                    "   ▸ Import members from alliance list\n"
                    "   ▸ Multi-select interface\n\n"
                    "**📺 Auto Register**\n"
                    "   ▸ Monitor a channel for FID codes\n"
                    "   ▸ Auto-add players who post their FID\n"
                ),
                color=0x2B2D31
            )
            embed.set_footer(
                text=f"{interaction.guild.name} x Magnus🚀",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Add via FID",
                emoji="📝",
                style=discord.ButtonStyle.success,
                custom_id="auto_redeem_add_via_fid",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Import from Alliance",
                emoji="🤖",
                style=discord.ButtonStyle.primary,
                custom_id="auto_redeem_auto_register",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Auto Register",
                emoji="📺",
                style=discord.ButtonStyle.primary,
                custom_id="auto_redeem_import_from_channel",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="◀ Back",
                emoji="🏠",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_auto_redeem",
                row=1
            ))
            
            await interaction.response.edit_message(embed=embed, view=view)
            return
        
        # Handle add via FID button - show modal with WOS API integration
        if custom_id == "auto_redeem_add_via_fid":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can add members.",
                    ephemeral=True
                )
                return
            
            class AddMemberModal(discord.ui.Modal, title="Add Member to Auto-Redeem"):
                fids_input = discord.ui.TextInput(
                    label="Player ID(s)",
                    placeholder="123456789 or 123456789, 987654321 or 123456789 PlayerName",
                    required=True,
                    style=discord.TextStyle.paragraph,
                    max_length=1000
                )
                
                def __init__(self, cog):
                    super().__init__()
                    self.cog = cog
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        input_text = self.fids_input.value.strip()
                        
                        # Parse FIDs (support multiple formats)
                        fid_entries = []
                        for line in input_text.replace(',', '\n').split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            
                            parts = line.split(None, 1)  # Split on first whitespace
                            fid = parts[0]
                            nickname = parts[1] if len(parts) > 1 else None
                            
                            if fid.isdigit():
                                fid_entries.append((fid, nickname))
                        
                        if not fid_entries:
                            await modal_interaction.response.send_message(
                                "❌ No valid FIDs found. Please enter numeric FIDs.",
                                ephemeral=True
                            )
                            return
                        
                        # Processing animation
                        processing_embed = discord.Embed(
                            title="➕ Adding Members to Auto-Redeem",
                            description=f"Processing **{len(fid_entries)}** member(s)...\n\n```\nFetching player data from WOS API...\n```",
                            color=0x5865F2
                        )
                        await modal_interaction.response.send_message(embed=processing_embed, ephemeral=True)
                        
                        # Process each FID
                        results = []
                        success_count = 0
                        fail_count = 0
                        
                        for fid, custom_nickname in fid_entries:
                            # Check if already exists
                            if self.cog.AutoRedeemDB.member_exists(self.cog, modal_interaction.guild.id, fid):
                                results.append(f"❌ Already exists: `{fid}`")
                                fail_count += 1
                                continue
                            
                            # Fetch player data from WOS API
                            player_data = await self.cog.fetch_player_data(fid)
                            
                            if player_data:
                                # Use custom nickname if provided, otherwise use API nickname
                                if custom_nickname:
                                    player_data['nickname'] = custom_nickname
                                
                                player_data['added_by'] = modal_interaction.user.id
                                
                                # Add to database
                                success = self.cog.AutoRedeemDB.add_member(
                                    self.cog,
                                    modal_interaction.guild.id,
                                    fid,
                                    player_data
                                )
                                
                                if success:
                                    furnace_lv = player_data.get('furnace_lv', 0)
                                    results.append(f"✅ **{player_data['nickname']}** (FC {furnace_lv}) - `{fid}`")
                                    success_count += 1
                                else:
                                    results.append(f"❌ Failed to add: `{fid}`")
                                    fail_count += 1
                            else:
                                results.append(f"❌ Invalid FID or API error: `{fid}`")
                                fail_count += 1
                        
                        # Final result
                        result_embed = discord.Embed(
                            title="➕ Add Members - Complete",
                            description=f"**Results:** {success_count} added, {fail_count} failed\n━━━━━━━━━━━━━━━━━━━━━━",
                            color=0x57F287 if success_count > 0 else 0xED4245
                        )
                        
                        results_text = "\n".join(results[:20])
                        if results_text:
                            result_embed.add_field(name="📋 Details", value=results_text, inline=False)
                        
                        if len(results) > 20:
                            result_embed.set_footer(text=f"Showing 20 of {len(results)} results")
                        
                        await modal_interaction.edit_original_response(embed=result_embed)
                    
                    except Exception as e:
                        self.cog.logger.exception(f"Error adding members: {e}")
                        error_embed = discord.Embed(
                            title="❌ Error",
                            description=f"An error occurred while adding members:\n```{str(e)}```",
                            color=discord.Color.red()
                        )
                        try:
                            await modal_interaction.edit_original_response(embed=error_embed)
                        except:
                            await modal_interaction.followup.send(embed=error_embed, ephemeral=True)
            
            await interaction.response.send_modal(AddMemberModal(self))
            return
        
        # Handle remove member button - show submenu
        if custom_id == "auto_redeem_remove_member":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can remove members.",
                    ephemeral=True
                )
                return
            
            # Get current member count
            self.cursor.execute("SELECT COUNT(*) FROM auto_redeem_members WHERE guild_id = ?", (interaction.guild.id,))
            member_count = self.cursor.fetchone()[0]
            
            embed = discord.Embed(
                title="➖ Remove Member from Auto-Redeem",
                description=(
                    "```ansi\n"
                    "\u001b[2;36m╔═══════════════════════════════════╗\n"
                    "\u001b[2;36m║  \u001b[1;37mREMOVE MEMBER OPTIONS\u001b[0m\u001b[2;36m          ║\n"
                    "\u001b[2;36m╚═══════════════════════════════════╝\u001b[0m\n"
                    "```\n"
                    "**Choose how to remove members:**\n\n"
                    f"👥 **Current Members:** `{member_count}`\n\n"
                    "**📝 Remove via FID**\n"
                    "   ▸ Manually enter player FID(s) to remove\n"
                    "   ▸ Support single or multiple FIDs\n\n"
                    "**🗑️ Bulk Remove from List**\n"
                    "   ▸ Select members from current auto-redeem list\n"
                    "   ▸ Multi-select interface for bulk removal\n"
                ),
                color=0x2B2D31
            )
            embed.set_footer(
                text=f"{interaction.guild.name} x Magnus🚀",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
            )
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Remove via FID",
                emoji="📝",
                style=discord.ButtonStyle.success,
                custom_id="auto_redeem_remove_via_fid",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="Bulk Remove from List",
                emoji="🗑️",
                style=discord.ButtonStyle.primary,
                custom_id="auto_redeem_bulk_remove",
                row=0
            ))
            view.add_item(discord.ui.Button(
                label="◀ Back",
                emoji="🏠",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_auto_redeem",
                row=1
            ))
            
            await interaction.response.edit_message(embed=embed, view=view)
            return
        
        # Handle remove via FID button
        if custom_id == "auto_redeem_remove_via_fid":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can remove members.",
                    ephemeral=True
                )
                return
            
            class RemoveMemberModal(discord.ui.Modal, title="Remove Members"):
                fids_input = discord.ui.TextInput(
                    label="Player ID(s)",
                    placeholder="123456789 or 123456789, 987654321",
                    required=True,
                    style=discord.TextStyle.paragraph,
                    max_length=1000
                )
                
                def __init__(self, cog):
                    super().__init__()
                    self.cog = cog
                
                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        input_text = self.fids_input.value.strip()
                        
                        # Parse FIDs
                        fids = []
                        for line in input_text.replace(',', '\n').split('\n'):
                            fid = line.strip().split()[0] if line.strip() else ""
                            if fid.isdigit():
                                fids.append(fid)
                        
                        if not fids:
                            await modal_interaction.response.send_message(
                                "❌ No valid FIDs found.",
                                ephemeral=True
                            )
                            return
                        
                        # Processing animation
                        processing_embed = discord.Embed(
                            title="➖ Removing Members",
                            description=f"Processing **{len(fids)}** member(s)...\\n\\n```\\nPlease wait...\\n```",
                            color=0xED4245
                        )
                        await modal_interaction.response.send_message(embed=processing_embed, ephemeral=True)
                        
                        results = []
                        success_count = 0
                        fail_count = 0
                        
                        for fid in fids:
                            # Get member data
                            members = self.cog.AutoRedeemDB.get_members(self.cog, modal_interaction.guild.id)
                            member = next((m for m in members if m.get('fid') == fid), None)
                            
                            if not member:
                                results.append(f"❌ Not found: `{fid}`")
                                fail_count += 1
                                continue
                                
                            success = self.cog.AutoRedeemDB.remove_member(
                                self.cog,
                                modal_interaction.guild.id,
                                fid
                            )
                            
                            if success:
                                results.append(f"✅ Removed: **{member.get('nickname', 'Unknown')}** (`{fid}`)")
                                success_count += 1
                            else:
                                results.append(f"❌ Failed to remove: `{fid}`")
                                fail_count += 1
                        
                        # Final result
                        result_embed = discord.Embed(
                            title="➖ Remove Members - Complete",
                            description=f"**Results:** {success_count} removed, {fail_count} failed\\n━━━━━━━━━━━━━━━━━━━━━━",
                            color=0x57F287 if success_count > 0 else 0xED4245
                        )
                        
                        results_text = "\\n".join(results[:20])
                        if results_text:
                            result_embed.add_field(name="📋 Details", value=results_text, inline=False)
                        
                        if len(results) > 20:
                            result_embed.set_footer(text=f"Showing 20 of {len(results)} results")
                        
                        await modal_interaction.edit_original_response(embed=result_embed)
                        
                    except Exception as e:
                        self.cog.logger.exception(f"Error removing members: {e}")
                        await modal_interaction.edit_original_response(content=f"❌ Error: {str(e)}")

            await interaction.response.send_modal(RemoveMemberModal(self))
            return
        
        # Handle view members button
        if custom_id == "auto_redeem_view_members":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can view auto-redeem members.",
                    ephemeral=True
                )
                return
            
            # Get all auto-redeem members for this guild
            members = self.AutoRedeemDB.get_members(self, interaction.guild.id)
            
            if not members:
                await interaction.response.send_message(
                    "📋 **No Members in Auto-Redeem List**\n\n"
                    "Add members using the **Add Member** button to get started!",
                    ephemeral=True
                )
                return
            
            # Pagination settings
            members_per_page = 15
            total_pages = (len(members) + members_per_page - 1) // members_per_page
            
            # Create paginated view
            class MemberPaginationView(discord.ui.View):
                def __init__(self, members_list, cog_instance):
                    super().__init__(timeout=180)
                    self.members = members_list
                    self.cog = cog_instance
                    self.current_page = 0
                    self.update_buttons()
                
                def get_embed(self):
                    start_idx = self.current_page * members_per_page
                    end_idx = min(start_idx + members_per_page, len(self.members))
                    page_members = self.members[start_idx:end_idx]
                    
                    embed = discord.Embed(
                        title="👥 Auto-Redeem Members",
                        description=f"**Total Members:** `{len(self.members)}`\n**Page {self.current_page + 1} of {total_pages}**\n━━━━━━━━━━━━━━━━━━━━━━",
                        color=0x5865F2
                    )
                    
                    for idx, member in enumerate(page_members, start=start_idx + 1):
                        fid = member.get('fid', 'Unknown')
                        nickname = member.get('nickname', 'Unknown')
                        furnace_lv = member.get('furnace_lv', 0)
                        formatted_fc = self.cog.format_furnace_level(furnace_lv)
                        
                        embed.add_field(
                            name=f"{idx}. {nickname}",
                            value=f"🆔 `{fid}`\n⚔️ {formatted_fc}",
                            inline=True
                        )
                    
                    return embed
                
                def update_buttons(self):
                    self.clear_items()
                    
                    # Previous button
                    prev_btn = discord.ui.Button(
                        label="◀ Previous",
                        style=discord.ButtonStyle.secondary,
                        disabled=(self.current_page == 0)
                    )
                    prev_btn.callback = self.previous_page
                    self.add_item(prev_btn)
                    
                    # Page indicator
                    page_btn = discord.ui.Button(
                        label=f"Page {self.current_page + 1}/{total_pages}",
                        style=discord.ButtonStyle.primary,
                        disabled=True
                    )
                    self.add_item(page_btn)
                    
                    # Next button
                    next_btn = discord.ui.Button(
                        label="Next ▶",
                        style=discord.ButtonStyle.secondary,
                        disabled=(self.current_page >= total_pages - 1)
                    )
                    next_btn.callback = self.next_page
                    self.add_item(next_btn)
                
                async def previous_page(self, button_interaction: discord.Interaction):
                    if self.current_page > 0:
                        self.current_page -= 1
                        self.update_buttons()
                        await button_interaction.response.edit_message(embed=self.get_embed(), view=self)
                
                async def next_page(self, button_interaction: discord.Interaction):
                    if self.current_page < total_pages - 1:
                        self.current_page += 1
                        self.update_buttons()
                        await button_interaction.response.edit_message(embed=self.get_embed(), view=self)
            
            view = MemberPaginationView(members, self)
            await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
            return
        
        # Handle configure auto redeem button
        if custom_id == "giftcode_configure_auto_redeem":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can configure auto-redeem settings.",
                    ephemeral=True
                )
                return
            
            # Get current settings - MongoDB first, SQLite fallback
            enabled = 0
            
            # Try MongoDB first
            try:
                use_mongo = mongo_enabled() and AutoRedeemSettingsAdapter
            except (NameError, UnboundLocalError):
                use_mongo = False
            
            if use_mongo:
                try:
                    mongo_settings = AutoRedeemSettingsAdapter.get_settings(interaction.guild.id)
                    if mongo_settings:
                        enabled = 1 if mongo_settings.get('enabled', False) else 0
                    else:
                        # No MongoDB settings, check SQLite
                        self.cursor.execute("""
                            SELECT enabled
                            FROM auto_redeem_settings 
                            WHERE guild_id = ?
                        """, (interaction.guild.id,))
                        settings = self.cursor.fetchone()
                        if settings:
                            enabled = settings[0]
                except Exception as e:
                    self.logger.error(f"Failed to load auto redeem settings from MongoDB: {e}")
                    # Fall back to SQLite
                    self.cursor.execute("""
                        SELECT enabled
                        FROM auto_redeem_settings 
                        WHERE guild_id = ?
                    """, (interaction.guild.id,))
                    settings = self.cursor.fetchone()
                    if settings:
                        enabled = settings[0]
            else:
                # MongoDB not available, use SQLite
                self.cursor.execute("""
                    SELECT enabled
                    FROM auto_redeem_settings 
                    WHERE guild_id = ?
                """, (interaction.guild.id,))
                settings = self.cursor.fetchone()
                if settings:
                    enabled = settings[0]
            
            # Get member count
            members = self.AutoRedeemDB.get_members(self, interaction.guild.id)
            member_count = len(members)
            
            # Get configured channel for FID monitoring - MongoDB first, SQLite fallback
            channel_name = "Not configured"
            channel_id = None
            
            # Try MongoDB first
            try:
                use_mongo = mongo_enabled() and AutoRedeemChannelsAdapter
            except (NameError, UnboundLocalError):
                use_mongo = False
            
            if use_mongo:
                try:
                    mongo_channel = AutoRedeemChannelsAdapter.get_channel(interaction.guild.id)
                    if mongo_channel:
                        channel_id = mongo_channel.get('channel_id')
                    else:
                        # No MongoDB channel, check SQLite
                        self.cursor.execute("""
                            SELECT channel_id 
                            FROM auto_redeem_channels 
                            WHERE guild_id = ?
                        """, (interaction.guild.id,))
                        channel_result = self.cursor.fetchone()
                        if channel_result:
                            channel_id = channel_result[0]
                except Exception as e:
                    self.logger.error(f"Failed to load auto redeem channel from MongoDB: {e}")
                    # Fall back to SQLite
                    self.cursor.execute("""
                        SELECT channel_id 
                        FROM auto_redeem_channels 
                        WHERE guild_id = ?
                    """, (interaction.guild.id,))
                    channel_result = self.cursor.fetchone()
                    if channel_result:
                        channel_id = channel_result[0]
            else:
                # MongoDB not available, use SQLite
                self.cursor.execute("""
                    SELECT channel_id 
                    FROM auto_redeem_channels 
                    WHERE guild_id = ?
                """, (interaction.guild.id,))
                channel_result = self.cursor.fetchone()
                if channel_result:
                    channel_id = channel_result[0]
            
            # Get channel name if we have an ID
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channel_name = f"#{channel.name}"
            
            embed = discord.Embed(
                title="⚙️ Auto-Redeem Configuration",
                description=(
                    "```ansi\n"
                    "\u001b[2;36m╔═══════════════════════════════════╗\n"
                    "\u001b[2;36m║  \u001b[1;37mAUTO-REDEEM SETTINGS\u001b[0m\u001b[2;36m           ║\n"
                    "\u001b[2;36m╚═══════════════════════════════════╝\u001b[0m\n"
                    "```\n"
                    "**Current Configuration:**\n\n"
                    f"🔘 **Status:** {'🟢 Enabled' if enabled else '🔴 Disabled'}\n"
                    f"👥 **Members:** `{member_count}`\n"
                    f"📢 **FID Monitor Channel:** {channel_name}\n\n"
                    "**Features:**\n"
                    "• Automatically redeem new gift codes\n"
                    "• Monitor channel for FID codes\n"
                    "• Track redemption success/failure\n"
                ),
                color=0x57F287 if enabled else 0xED4245
            )
            embed.set_footer(
                text=f"{interaction.guild.name} x Magnus🚀",
                icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
            )
            
            view = discord.ui.View()
            
            # Toggle enable/disable button
            if enabled:
                view.add_item(discord.ui.Button(
                    label="Disable Auto-Redeem",
                    emoji="🔴",
                    style=discord.ButtonStyle.danger,
                    custom_id="auto_redeem_disable",
                    row=0
                ))
            else:
                view.add_item(discord.ui.Button(
                    label="Enable Auto-Redeem",
                    emoji="🟢",
                    style=discord.ButtonStyle.success,
                    custom_id="auto_redeem_enable",
                    row=0
                ))
            
            # Set FID monitor channel button
            view.add_item(discord.ui.Button(
                label="Set FID Monitor Channel",
                emoji="📢",
                style=discord.ButtonStyle.primary,
                custom_id="auto_redeem_import_from_channel",
                row=0
            ))
            
            # Reset code status button (for testing)
            view.add_item(discord.ui.Button(
                label="Reset Code Status",
                emoji="🔄",
                style=discord.ButtonStyle.secondary,
                custom_id="auto_redeem_reset_code",
                row=1
            ))
            
            # Delete code button
            view.add_item(discord.ui.Button(
                label="Delete Code",
                emoji="🗑️",
                style=discord.ButtonStyle.danger,
                custom_id="auto_redeem_delete_code",
                row=1
            ))
            
            # Back button
            view.add_item(discord.ui.Button(
                label="◀ Back",
                emoji="🏠",
                style=discord.ButtonStyle.secondary,
                custom_id="giftcode_auto_redeem",
                row=2
            ))
            
            await interaction.response.edit_message(embed=embed, view=view)
            return


        # Handle bulk remove button
        if custom_id == "auto_redeem_bulk_remove":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can remove members.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                # Get all members
                members = self.AutoRedeemDB.get_members(self, interaction.guild.id)
                
                if not members:
                    await interaction.followup.send(
                        "📋 No members in auto-redeem list to remove.",
                        ephemeral=True
                    )
                    return
                
                # Create multi-select view (similar to AllianceMemberSelectView but for removal)
                class BulkRemoveSelectView(discord.ui.View):
                    def __init__(self, members_data, cog_instance, guild_id):
                        super().__init__(timeout=None)
                        self.members = members_data
                        self.cog = cog_instance
                        self.guild_id = guild_id
                        self.selected_fids = set()
                        self.current_page = 0
                        self.members_per_page = 20
                        self.update_components()
                    
                    def get_total_pages(self):
                        return (len(self.members) - 1) // self.members_per_page + 1
                    
                    def update_components(self):
                        self.clear_items()
                        
                        # Get members for current page
                        start_idx = self.current_page * self.members_per_page
                        end_idx = start_idx + self.members_per_page
                        page_members = self.members[start_idx:end_idx]
                        
                        # Create select menu
                        options = []
                        for member in page_members:
                            fid = member.get('fid', '')
                            nickname = member.get('nickname', 'Unknown')
                            furnace_lv = member.get('furnace_lv', 0)
                            formatted_fc = self.cog.format_furnace_level(furnace_lv)
                            
                            options.append(
                                discord.SelectOption(
                                    label=f"{nickname} (FC {formatted_fc})",
                                    description=f"FID: {fid}",
                                    value=fid,
                                    emoji="✅" if fid in self.selected_fids else "🗑️",
                                    default=(fid in self.selected_fids)
                                )
                            )
                        
                        if options:
                            select = discord.ui.Select(
                                placeholder=f"Select members to remove ({len(self.selected_fids)} selected)",
                                options=options,
                                min_values=0,
                                max_values=len(options)
                            )
                            select.callback = self.member_select
                            self.add_item(select)
                        
                        # Select All / Deselect All buttons
                        if len(self.selected_fids) < len(self.members):
                            select_all_btn = discord.ui.Button(
                                label="Select All",
                                style=discord.ButtonStyle.primary,
                                emoji="☑️"
                            )
                            select_all_btn.callback = self.select_all_callback
                            self.add_item(select_all_btn)
                        
                        if self.selected_fids:
                            deselect_all_btn = discord.ui.Button(
                                label="Deselect All",
                                style=discord.ButtonStyle.secondary,
                                emoji="⬜"
                            )
                            deselect_all_btn.callback = self.deselect_all_callback
                            self.add_item(deselect_all_btn)
                        
                        # Pagination buttons
                        if self.current_page > 0:
                            prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary)
                            prev_btn.callback = self.previous_page
                            self.add_item(prev_btn)
                        
                        if self.current_page < self.get_total_pages() - 1:
                            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                            next_btn.callback = self.next_page
                            self.add_item(next_btn)
                        
                        # Remove selected button
                        if self.selected_fids:
                            remove_btn = discord.ui.Button(
                                label=f"Remove Selected ({len(self.selected_fids)})",
                                style=discord.ButtonStyle.danger,
                                emoji="🗑️"
                            )
                            remove_btn.callback = self.remove_selected_members
                            self.add_item(remove_btn)
                    
                    async def member_select(self, select_interaction: discord.Interaction):
                        selected_values = set(select_interaction.data['values'])
                        
                        # Get all FIDs on current page
                        start_idx = self.current_page * self.members_per_page
                        end_idx = start_idx + self.members_per_page
                        page_fids = {m.get('fid') for m in self.members[start_idx:end_idx]}
                        
                        # Remove deselected from current page
                        self.selected_fids = (self.selected_fids - page_fids) | selected_values
                        
                        self.update_components()
                        await select_interaction.response.edit_message(
                            content=f"**Selected {len(self.selected_fids)} member(s)** - Choose more or click 'Remove Selected'",
                            view=self
                        )
                    
                    async def previous_page(self, btn_interaction: discord.Interaction):
                        if self.current_page > 0:
                            self.current_page -= 1
                            self.update_components()
                            await btn_interaction.response.edit_message(view=self)
                    
                    async def next_page(self, btn_interaction: discord.Interaction):
                        if self.current_page < self.get_total_pages() - 1:
                            self.current_page += 1
                            self.update_components()
                            await btn_interaction.response.edit_message(view=self)
                    
                    async def select_all_callback(self, btn_interaction: discord.Interaction):
                        """Select all members for removal"""
                        for member in self.members:
                            fid = member.get('fid')
                            if fid:
                                self.selected_fids.add(fid)
                        
                        self.update_components()
                        await btn_interaction.response.edit_message(
                            content=f"**✅ Selected all {len(self.selected_fids)} member(s)** - Click 'Remove Selected' to remove them",
                            view=self
                        )
                    
                    async def deselect_all_callback(self, btn_interaction: discord.Interaction):
                        """Deselect all members"""
                        self.selected_fids.clear()
                        self.update_components()
                        await btn_interaction.response.edit_message(
                            content=f"**Deselected all members** - Select members to remove from auto-redeem list",
                            view=self
                        )
                    
                    async def remove_selected_members(self, remove_interaction: discord.Interaction):
                        if not self.selected_fids:
                            await remove_interaction.response.send_message("❌ No members selected.", ephemeral=True)
                            return
                        
                        # Processing animation
                        processing_embed = discord.Embed(
                            title="➖ Removing Members",
                            description=f"Removing **{len(self.selected_fids)}** member(s)...\\n\\n```\\nPlease wait...\\n```",
                            color=0xED4245
                        )
                        await remove_interaction.response.send_message(embed=processing_embed, ephemeral=True)
                        
                        results = []
                        success_count = 0
                        fail_count = 0
                        
                        for fid in self.selected_fids:
                            member = next((m for m in self.members if m.get('fid') == fid), None)
                            nickname = member.get('nickname', 'Unknown') if member else "Unknown"
                            
                            success = self.cog.AutoRedeemDB.remove_member(
                                self.cog,
                                self.guild_id,
                                fid
                            )
                            
                            if success:
                                results.append(f"✅ Removed: **{nickname}** (`{fid}`)")
                                success_count += 1
                            else:
                                results.append(f"❌ Failed: `{fid}`")
                                fail_count += 1
                        
                        # Final result
                        result_embed = discord.Embed(
                            title="➖ Bulk Remove - Complete",
                            description=f"**Results:** {success_count} removed, {fail_count} failed\\n━━━━━━━━━━━━━━━━━━━━━━",
                            color=0x57F287 if success_count > 0 else 0xED4245
                        )
                        
                        results_text = "\\n".join(results[:20])
                        if results_text:
                            result_embed.add_field(name="📋 Details", value=results_text, inline=False)
                        
                        if len(results) > 20:
                            result_embed.set_footer(text=f"Showing 20 of {len(results)} results")
                        
                        await remove_interaction.edit_original_response(embed=result_embed)

                view = BulkRemoveSelectView(members, self, interaction.guild.id)
                await interaction.followup.send(
                    f"**Select members to remove from auto-redeem list:**\n\nTotal members: {len(members)}",
                    view=view,
                    ephemeral=True
                )
                
            except Exception as e:
                self.logger.exception(f"Error in bulk remove: {e}")
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            return
        
        # Handle view members button
        if custom_id == "auto_redeem_view_members":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can view members.",
                    ephemeral=True
                )
                return
            
            # Get all members using MongoDB-first helper
            members_data = self.AutoRedeemDB.get_members(self, interaction.guild.id)
            
            # Convert to tuple format for compatibility with existing view code
            members = [
                (m['fid'], m['nickname'], m.get('added_at'), m.get('furnace_lv', 0))
                for m in members_data
            ]
            
            if not members:
                await interaction.response.send_message(
                    "📋 No members in auto-redeem list.\n\nUse **Add Member** to add players.",
                    ephemeral=True
                )
                return
            
            # Create paginated view
            class MemberListView(discord.ui.View):
                def __init__(self, members_data, cog_instance):
                    super().__init__(timeout=None)
                    self.members = members_data
                    self.cog = cog_instance
                    self.current_page = 0
                    self.members_per_page = 15
                    self.update_buttons()
                
                def get_total_pages(self):
                    return (len(self.members) - 1) // self.members_per_page + 1
                
                def get_embed(self):
                    start_idx = self.current_page * self.members_per_page
                    end_idx = start_idx + self.members_per_page
                    page_members = self.members[start_idx:end_idx]
                    
                    embed = discord.Embed(
                        title="👥 Auto-Redeem Members",
                        description=f"Total Members: **{len(self.members)}** | Page {self.current_page + 1}/{self.get_total_pages()}\n━━━━━━━━━━━━━━━━━━━━━━",
                        color=0x5865F2
                    )
                    
                    for fid, nickname, added_at, furnace_lv in page_members:
                        formatted_fc = self.cog.format_furnace_level(furnace_lv)
                        furnace_text = f" (FC {formatted_fc})" if furnace_lv else ""
                        embed.add_field(
                            name=f"👤 {nickname}{furnace_text}",
                            value=f"**FID:** `{fid}`\n**Added:** <t:{int(datetime.fromisoformat(str(added_at)).timestamp())}:R>",
                            inline=True
                        )
                    
                    return embed
                
                def update_buttons(self):
                    self.clear_items()
                    
                    # Previous button
                    prev_btn = discord.ui.Button(
                        label="",
                        emoji="⬅️",
                        style=discord.ButtonStyle.primary,
                        disabled=(self.current_page == 0)
                    )
                    prev_btn.callback = self.previous_page
                    self.add_item(prev_btn)
                    
                    # Next button
                    next_btn = discord.ui.Button(
                        label="",
                        emoji="➡️",
                        style=discord.ButtonStyle.primary,
                        disabled=(self.current_page >= self.get_total_pages() - 1)
                    )
                    next_btn.callback = self.next_page
                    self.add_item(next_btn)
                
                async def previous_page(self, button_interaction: discord.Interaction):
                    if self.current_page > 0:
                        self.current_page -= 1
                        self.update_buttons()
                        await button_interaction.response.edit_message(embed=self.get_embed(), view=self)
                
                async def next_page(self, button_interaction: discord.Interaction):
                    if self.current_page < self.get_total_pages() - 1:
                        self.current_page += 1
                        self.update_buttons()
                        await button_interaction.response.edit_message(embed=self.get_embed(), view=self)
            
            view = MemberListView(members, self)
            await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
            return
        
        # Handle auto register button - WITH MULTI-SELECT
        if custom_id == "auto_redeem_auto_register":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can import members.",
                    ephemeral=True
                )
                return
            
            try:
                # Defer the interaction to prevent timeout
                await interaction.response.defer(ephemeral=True)
            except discord.errors.NotFound:
                self.logger.error("Interaction expired before defer")
                return
            except Exception as e:
                self.logger.error(f"Error deferring interaction: {e}")
                return
            
            try:
                # Get alliance members from MongoDB - filtered by server's assigned alliance
                from db.mongo_adapters import AllianceMembersAdapter, ServerAllianceAdapter
                
                # Get server's assigned alliance
                alliance_id = ServerAllianceAdapter.get_alliance(interaction.guild.id)
                
                if not alliance_id:
                    await interaction.followup.send(
                        "❌ No alliance assigned to this server.\n\nPlease assign an alliance first using the alliance management features.",
                        ephemeral=True
                    )
                    return
                
                # Get all members and filter by assigned alliance
                all_members = AllianceMembersAdapter.get_all_members()
                members = [m for m in all_members if int(m.get('alliance', 0) or m.get('alliance_id', 0)) == alliance_id]
                
                if not members:
                    await interaction.followup.send(
                        "❌ No members found in your assigned alliance.\n\nPlease ensure alliance monitoring is active and members have been synced.",
                        ephemeral=True
                    )
                    return
                
                # Create multi-select view
                class AllianceMemberSelectView(discord.ui.View):
                    def __init__(self, members_data, cog_instance, guild_id):
                        super().__init__(timeout=300)  # 5 minute timeout
                        self.members = members_data
                        self.cog = cog_instance
                        self.guild_id = guild_id
                        self.selected_fids = set()
                        self.current_page = 0
                        self.members_per_page = 20
                        self.update_components()
                    
                    async def on_timeout(self):
                        """Handle view timeout"""
                        try:
                            for item in self.children:
                                item.disabled = True
                            # Note: We can't edit the message here as we don't have the message reference
                        except Exception as e:
                            self.cog.logger.error(f"Error in view timeout: {e}")
                    
                    def get_total_pages(self):
                        return (len(self.members) - 1) // self.members_per_page + 1
                    
                    def update_components(self):
                        self.clear_items()
                        
                        # Get members for current page
                        start_idx = self.current_page * self.members_per_page
                        end_idx = start_idx + self.members_per_page
                        page_members = self.members[start_idx:end_idx]
                        
                        # BATCH CHECK: Get all FIDs and check existence in one query
                        from db.mongo_adapters import AutoRedeemMembersAdapter
                        all_fids = [m.get('fid') for m in self.members if m.get('fid')]
                        existing_fids_map = AutoRedeemMembersAdapter.batch_member_exists(self.guild_id, all_fids)
                        
                        # Create select menu
                        options = []
                        for member in page_members:
                            fid = member.get('fid', '')
                            nickname = member.get('nickname', 'Unknown')
                            furnace_lv = member.get('furnace_lv', 0)
                            formatted_fc = self.cog.format_furnace_level(furnace_lv)
                            
                            # Check if already in auto-redeem list (from batch result)
                            already_added = existing_fids_map.get(fid, False)
                            
                            options.append(
                                discord.SelectOption(
                                    label=f"{nickname} (FC {formatted_fc})",
                                    description=f"FID: {fid}" + (" - Already added" if already_added else ""),
                                    value=fid,
                                    emoji="✅" if fid in self.selected_fids else "👤",
                                    default=(fid in self.selected_fids)
                                )
                            )
                        
                        if options:
                            select = discord.ui.Select(
                                placeholder=f"Select members to add ({len(self.selected_fids)} selected)",
                                options=options,
                                min_values=0,
                                max_values=len(options)
                            )
                            select.callback = self.member_select
                            self.add_item(select)
                        
                        # Select All / Deselect All buttons
                        # Count total members with valid FIDs (including already added)
                        total_selectable = sum(1 for m in self.members if m.get('fid'))
                        
                        if len(self.selected_fids) < total_selectable:
                            select_all_btn = discord.ui.Button(
                                label="Select All",
                                style=discord.ButtonStyle.primary,
                                emoji="☑️"
                            )
                            select_all_btn.callback = self.select_all_callback
                            self.add_item(select_all_btn)
                        
                        if self.selected_fids:
                            deselect_all_btn = discord.ui.Button(
                                label="Deselect All",
                                style=discord.ButtonStyle.secondary,
                                emoji="⬜"
                            )
                            deselect_all_btn.callback = self.deselect_all_callback
                            self.add_item(deselect_all_btn)
                        
                        # Pagination buttons
                        if self.current_page > 0:
                            prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary)
                            prev_btn.callback = self.previous_page
                            self.add_item(prev_btn)
                        
                        if self.current_page < self.get_total_pages() - 1:
                            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                            next_btn.callback = self.next_page
                            self.add_item(next_btn)
                        
                        # Add selected button
                        if self.selected_fids:
                            add_btn = discord.ui.Button(
                                label=f"Add Selected ({len(self.selected_fids)})",
                                style=discord.ButtonStyle.success,
                                emoji="➕"
                            )
                            add_btn.callback = self.add_selected_members
                            self.add_item(add_btn)
                    
                    async def member_select(self, select_interaction: discord.Interaction):
                        try:
                            # Toggle selected FIDs
                            selected_values = set(select_interaction.data['values'])
                            
                            # Get all FIDs on current page
                            start_idx = self.current_page * self.members_per_page
                            end_idx = start_idx + self.members_per_page
                            page_fids = {m.get('fid') for m in self.members[start_idx:end_idx]}
                            
                            # Remove deselected from current page
                            self.selected_fids = (self.selected_fids - page_fids) | selected_values
                            
                            self.update_components()
                            await select_interaction.response.edit_message(
                                content=f"**Selected {len(self.selected_fids)} member(s)** - Choose more or click 'Add Selected'",
                                view=self
                            )
                        except Exception as e:
                            self.cog.logger.exception(f"Error in member_select: {e}")
                            try:
                                await select_interaction.response.send_message(
                                    f"❌ An error occurred: {str(e)}",
                                    ephemeral=True
                                )
                            except:
                                pass
                    
                    async def previous_page(self, btn_interaction: discord.Interaction):
                        try:
                            if self.current_page > 0:
                                self.current_page -= 1
                                self.update_components()
                                await btn_interaction.response.edit_message(
                                    content=f"**Selected {len(self.selected_fids)} member(s)** - Choose more or click 'Add Selected'",
                                    view=self
                                )
                        except Exception as e:
                            self.cog.logger.exception(f"Error in previous_page: {e}")
                    
                    async def next_page(self, btn_interaction: discord.Interaction):
                        try:
                            if self.current_page < self.get_total_pages() - 1:
                                self.current_page += 1
                                self.update_components()
                                await btn_interaction.response.edit_message(
                                    content=f"**Selected {len(self.selected_fids)} member(s)** - Choose more or click 'Add Selected'",
                                    view=self
                                )
                        except Exception as e:
                            self.cog.logger.exception(f"Error in next_page: {e}")
                    
                    async def select_all_callback(self, btn_interaction: discord.Interaction):
                        """Select all members (including those already in auto-redeem list)"""
                        try:
                            # Select ALL members with valid FIDs
                            for member in self.members:
                                fid = member.get('fid')
                                if fid:  # Only add if FID is not None/empty
                                    self.selected_fids.add(fid)
                            
                            self.update_components()
                            await btn_interaction.response.edit_message(
                                content=f"**✅ Selected all {len(self.selected_fids)} member(s)** - Click 'Add Selected' to import (existing members will be skipped)",
                                view=self
                            )
                        except Exception as e:
                            self.cog.logger.exception(f"Error in select_all_callback: {e}")
                    
                    async def deselect_all_callback(self, btn_interaction: discord.Interaction):
                        """Deselect all members"""
                        try:
                            self.selected_fids.clear()
                            self.update_components()
                            await btn_interaction.response.edit_message(
                                content=f"**Deselected all members** - Select members to add to auto-redeem list",
                                view=self
                            )
                        except Exception as e:
                            self.cog.logger.exception(f"Error in deselect_all_callback: {e}")
                    
                    async def add_selected_members(self, add_interaction: discord.Interaction):
                        try:
                            if not self.selected_fids:
                                await add_interaction.response.send_message("❌ No members selected.", ephemeral=True)
                                return
                            
                            # Processing animation
                            processing_embed = discord.Embed(
                                title="➕ Adding Members to Auto-Redeem",
                                description=f"Adding **{len(self.selected_fids)}** member(s)...\n\n```\nPlease wait...\n```",
                                color=0x5865F2
                            )
                            await add_interaction.response.send_message(embed=processing_embed, ephemeral=True)
                            
                            results = []
                            success_count = 0
                            fail_count = 0
                            
                            for fid in self.selected_fids:
                                # Find member data
                                member = next((m for m in self.members if m.get('fid') == fid), None)
                                if member:
                                    member_data = {
                                        'nickname': member.get('nickname', 'Unknown'),
                                        'furnace_lv': int(member.get('furnace_lv', 0) or 0),
                                        'avatar_image': member.get('avatar_image', ''),
                                        'added_by': add_interaction.user.id
                                    }
                                    
                                    success = self.cog.AutoRedeemDB.add_member(
                                        self.cog,
                                        self.guild_id,
                                        fid,
                                        member_data
                                    )
                                    
                                    if success:
                                        results.append(f"✅ **{member_data['nickname']}** (`{fid}`)")
                                        success_count += 1
                                    else:
                                        results.append(f"❌ Already exists: `{fid}`")
                                        fail_count += 1
                            
                            # Create paginated result view
                            class ResultPaginationView(discord.ui.View):
                                def __init__(self, results_list, success_cnt, fail_cnt):
                                    super().__init__(timeout=180)
                                    self.results = results_list
                                    self.success_count = success_cnt
                                    self.fail_count = fail_cnt
                                    self.current_page = 0
                                    self.items_per_page = 20
                                    self.update_buttons()
                                
                                def get_total_pages(self):
                                    return (len(self.results) - 1) // self.items_per_page + 1 if self.results else 1
                                
                                def get_embed(self):
                                    start_idx = self.current_page * self.items_per_page
                                    end_idx = start_idx + self.items_per_page
                                    page_results = self.results[start_idx:end_idx]
                                    
                                    embed = discord.Embed(
                                        title="➕ Import from Alliance - Complete",
                                        description=f"**Results:** {self.success_count} added, {self.fail_count} failed\n━━━━━━━━━━━━━━━━━━━━━━",
                                        color=0x57F287 if self.success_count > 0 else 0xED4245
                                    )
                                    
                                    if page_results:
                                        results_text = "\n".join(page_results)
                                        embed.add_field(name="📋 Details", value=results_text, inline=False)
                                    
                                    if len(self.results) > self.items_per_page:
                                        embed.set_footer(text=f"Page {self.current_page + 1}/{self.get_total_pages()} • Total: {len(self.results)} members")
                                    
                                    return embed
                                
                                def update_buttons(self):
                                    self.clear_items()
                                    
                                    if self.get_total_pages() > 1:
                                        # Previous button
                                        prev_btn = discord.ui.Button(
                                            label="",
                                            emoji="⬅️",
                                            style=discord.ButtonStyle.primary,
                                            disabled=(self.current_page == 0)
                                        )
                                        prev_btn.callback = self.previous_page
                                        self.add_item(prev_btn)
                                        
                                        # Next button
                                        next_btn = discord.ui.Button(
                                            label="",
                                            emoji="➡️",
                                            style=discord.ButtonStyle.primary,
                                            disabled=(self.current_page >= self.get_total_pages() - 1)
                                        )
                                        next_btn.callback = self.next_page
                                        self.add_item(next_btn)
                                
                                async def previous_page(self, button_interaction: discord.Interaction):
                                    if self.current_page > 0:
                                        self.current_page -= 1
                                        self.update_buttons()
                                        await button_interaction.response.edit_message(embed=self.get_embed(), view=self)
                                
                                async def next_page(self, button_interaction: discord.Interaction):
                                    if self.current_page < self.get_total_pages() - 1:
                                        self.current_page += 1
                                        self.update_buttons()
                                        await button_interaction.response.edit_message(embed=self.get_embed(), view=self)
                            
                            # Show paginated results
                            result_view = ResultPaginationView(results, success_count, fail_count)
                            await add_interaction.edit_original_response(embed=result_view.get_embed(), view=result_view)
                        except Exception as e:
                            self.cog.logger.exception(f"Error in add_selected_members: {e}")
                            try:
                                await add_interaction.response.send_message(
                                    f"❌ An error occurred while adding members: {str(e)}",
                                    ephemeral=True
                                )
                            except:
                                try:
                                    await add_interaction.followup.send(
                                        f"❌ An error occurred while adding members: {str(e)}",
                                        ephemeral=True
                                    )
                                except:
                                    pass
                
                # Show member selection
                member_view = AllianceMemberSelectView(members, self, interaction.guild.id)
                await interaction.followup.send(
                    f"**Select members to add to auto-redeem list:**\n\nTotal alliance members: {len(members)}",
                    view=member_view,
                    ephemeral=True
                )
                
            except discord.errors.NotFound:
                self.logger.error("Interaction expired during auto register")
            except Exception as e:
                self.logger.exception(f"Error in auto register: {e}")
                try:
                    await interaction.followup.send(
                        f"❌ An error occurred: {str(e)}\n\nPlease try again or contact an administrator if the issue persists.",
                        ephemeral=True
                    )
                except:
                    self.logger.error("Could not send error message to user")
            return
        
        # Handle import from channel button
        if custom_id == "auto_redeem_import_from_channel":
            # Import at method level to avoid scope issues
            from db.mongo_adapters import mongo_enabled, AutoRedeemChannelsAdapter
            
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can configure channel monitoring.",
                    ephemeral=True
                )
                return
            
            # Check if channel is already configured - try MongoDB first
            existing_channel_id = None
            
            if mongo_enabled() and AutoRedeemChannelsAdapter:
                try:
                    channel_config = AutoRedeemChannelsAdapter.get_channel(interaction.guild.id)
                    if channel_config:
                        existing_channel_id = channel_config.get('channel_id')
                except Exception as e:
                    self.logger.warning(f"Failed to get channel from MongoDB: {e}")
            
            # Fallback to SQLite if MongoDB didn't return a result
            if existing_channel_id is None:
                self.cursor.execute(
                    "SELECT channel_id FROM auto_redeem_channels WHERE guild_id = ?",
                    (interaction.guild.id,)
                )
                result = self.cursor.fetchone()
                if result:
                    existing_channel_id = result[0]
                    
                    # Sync to MongoDB if found in SQLite but not in MongoDB
                    if mongo_enabled() and AutoRedeemChannelsAdapter:
                        try:
                            AutoRedeemChannelsAdapter.set_channel(
                                interaction.guild.id,
                                existing_channel_id,
                                interaction.user.id
                            )
                            self.logger.info(f"Synced channel config to MongoDB for guild {interaction.guild.id}")
                        except Exception as e:
                            self.logger.warning(f"Failed to sync channel to MongoDB: {e}")
            
            if existing_channel_id:
                # Channel already configured - ask for confirmation
                channel = interaction.guild.get_channel(existing_channel_id)
                channel_mention = channel.mention if channel else f"<#{existing_channel_id}>"
                
                embed = discord.Embed(
                    title="📺 Channel Already Configured",
                    description=(
                        f"**Current monitored channel:** {channel_mention}\n\n"
                        "The bot is currently monitoring this channel for FID codes.\n\n"
                        "Do you want to change to a different channel?"
                    ),
                    color=0xFEE75C
                )
                
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="Change Channel",
                    emoji="🔄",
                    style=discord.ButtonStyle.primary,
                    custom_id="auto_redeem_change_channel"
                ))
                view.add_item(discord.ui.Button(
                    label="Keep Current",
                    emoji="✅",
                    style=discord.ButtonStyle.secondary,
                    custom_id="giftcode_auto_redeem"
                ))
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                # Get all text channels in the guild
                text_channels = [ch for ch in interaction.guild.text_channels if ch.permissions_for(interaction.guild.me).send_messages]
                
                if not text_channels:
                    await interaction.followup.send(
                        "❌ No accessible text channels found in this server.",
                        ephemeral=True
                    )
                    return
                
                # Create channel selection view
                class ChannelSelectView(discord.ui.View):
                    def __init__(self, channels_list, cog_instance, guild_id, user_id):
                        super().__init__(timeout=None)
                        self.channels = channels_list
                        self.cog = cog_instance
                        self.guild_id = guild_id
                        self.user_id = user_id
                        self.current_page = 0
                        self.channels_per_page = 20
                        self.update_components()
                    
                    def get_total_pages(self):
                        return (len(self.channels) - 1) // self.channels_per_page + 1
                    
                    def update_components(self):
                        self.clear_items()
                        
                        # Get channels for current page
                        start_idx = self.current_page * self.channels_per_page
                        end_idx = start_idx + self.channels_per_page
                        page_channels = self.channels[start_idx:end_idx]
                        
                        # Create select menu
                        options = []
                        for channel in page_channels:
                            options.append(
                                discord.SelectOption(
                                    label=f"#{channel.name}",
                                    description=f"ID: {channel.id}",
                                    value=str(channel.id),
                                    emoji="📺"
                                )
                            )
                        
                        if options:
                            select = discord.ui.Select(
                                placeholder="Select a channel to monitor for FIDs",
                                options=options,
                                min_values=1,
                                max_values=1
                            )
                            select.callback = self.channel_select
                            self.add_item(select)
                        
                        # Pagination buttons
                        if self.current_page > 0:
                            prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary)
                            prev_btn.callback = self.previous_page
                            self.add_item(prev_btn)
                        
                        if self.current_page < self.get_total_pages() - 1:
                            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                            next_btn.callback = self.next_page
                            self.add_item(next_btn)
                    
                    async def channel_select(self, select_interaction: discord.Interaction):
                        # Import at method level to avoid scope issues
                        from db.mongo_adapters import mongo_enabled, AutoRedeemChannelsAdapter
                        
                        channel_id = int(select_interaction.data['values'][0])
                        channel = select_interaction.guild.get_channel(channel_id)
                        
                        if not channel:
                            await select_interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                            return
                        
                        # Save to MongoDB first
                        try:
                            if mongo_enabled() and AutoRedeemChannelsAdapter:
                                try:
                                    AutoRedeemChannelsAdapter.set_channel(
                                        self.guild_id,
                                        channel_id,
                                        self.user_id
                                    )
                                except Exception as e:
                                    self.cog.logger.error(f"Failed to save channel to MongoDB: {e}")
                        except ImportError:
                            # MongoDB not available, skip
                            pass
                        
                        # Also save to SQLite for backward compatibility
                        try:
                            self.cog.cursor.execute("""
                                INSERT OR REPLACE INTO auto_redeem_channels 
                                (guild_id, channel_id, added_by, added_at)
                                VALUES (?, ?, ?, ?)
                            """, (self.guild_id, channel_id, self.user_id, datetime.now()))
                            self.cog.giftcode_db.commit()
                            
                            embed = discord.Embed(
                                title="✅ Channel Monitoring Configured",
                                description=(
                                    f"**Channel:** {channel.mention}\n\n"
                                    "**How it works:**\n"
                                    "▸ Bot will monitor this channel for 9-digit FID codes\n"
                                    "▸ Valid FIDs will be automatically added to auto-redeem list\n"
                                    "▸ Players will receive confirmation when added\n\n"
                                    "**Example:** When someone posts `123456789`, the bot will validate and add them."
                                ),
                                color=0x57F287
                            )
                            embed.set_footer(text=f"Configured by {select_interaction.user.name}")
                            
                            await select_interaction.response.edit_message(embed=embed, view=None)
                        except Exception as e:
                            self.cog.logger.error(f"Error saving channel config: {e}")
                            await select_interaction.response.send_message(
                                f"❌ Error saving configuration: {str(e)}",
                                ephemeral=True
                            )
                    
                    async def previous_page(self, btn_interaction: discord.Interaction):
                        if self.current_page > 0:
                            self.current_page -= 1
                            self.update_components()
                            await btn_interaction.response.edit_message(view=self)
                    
                    async def next_page(self, btn_interaction: discord.Interaction):
                        if self.current_page < self.get_total_pages() - 1:
                            self.current_page += 1
                            self.update_components()
                            await btn_interaction.response.edit_message(view=self)
                
                view = ChannelSelectView(text_channels, self, interaction.guild.id, interaction.user.id)
                await interaction.followup.send(
                    f"**Select a channel to monitor for FID codes:**\n\nTotal channels: {len(text_channels)}",
                    view=view,
                    ephemeral=True
                )
                
            except Exception as e:
                self.logger.exception(f"Error in import from channel: {e}")
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            return

        # Handle change channel button (when channel already configured)
        if custom_id == "auto_redeem_change_channel":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can configure channel monitoring.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                # Get all text channels in the guild
                text_channels = [ch for ch in interaction.guild.text_channels if ch.permissions_for(interaction.guild.me).send_messages]
                
                if not text_channels:
                    await interaction.followup.send(
                        "❌ No accessible text channels found in this server.",
                        ephemeral=True
                    )
                    return
                
                # Create channel selection view (reuse the same class from import_channel)
                class ChannelSelectView(discord.ui.View):
                    def __init__(self, channels_list, cog_instance, guild_id, user_id):
                        super().__init__(timeout=300)
                        self.channels = channels_list
                        self.cog = cog_instance
                        self.guild_id = guild_id
                        self.user_id = user_id
                        self.current_page = 0
                        self.channels_per_page = 20
                        self.update_components()
                    
                    def get_total_pages(self):
                        return (len(self.channels) - 1) // self.channels_per_page + 1
                    
                    def update_components(self):
                        self.clear_items()
                        
                        # Get channels for current page
                        start_idx = self.current_page * self.channels_per_page
                        end_idx = start_idx + self.channels_per_page
                        page_channels = self.channels[start_idx:end_idx]
                        
                        # Create select menu
                        options = []
                        for channel in page_channels:
                            options.append(
                                discord.SelectOption(
                                    label=f"#{channel.name}",
                                    description=f"ID: {channel.id}",
                                    value=str(channel.id),
                                    emoji="📺"
                                )
                            )
                        
                        if options:
                            select = discord.ui.Select(
                                placeholder="Select a channel to monitor for FIDs",
                                options=options,
                                min_values=1,
                                max_values=1
                            )
                            select.callback = self.channel_select
                            self.add_item(select)
                        
                        # Pagination buttons
                        if self.current_page > 0:
                            prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary)
                            prev_btn.callback = self.previous_page
                            self.add_item(prev_btn)
                        
                        if self.current_page < self.get_total_pages() - 1:
                            next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                            next_btn.callback = self.next_page
                            self.add_item(next_btn)
                    
                    async def channel_select(self, select_interaction: discord.Interaction):
                        # Import at method level to avoid scope issues
                        from db.mongo_adapters import mongo_enabled, AutoRedeemChannelsAdapter
                        
                        channel_id = int(select_interaction.data['values'][0])
                        channel = select_interaction.guild.get_channel(channel_id)
                        
                        if not channel:
                            await select_interaction.response.send_message("❌ Channel not found.", ephemeral=True)
                            return
                        
                        # Save to MongoDB first
                        try:
                            if mongo_enabled() and AutoRedeemChannelsAdapter:
                                try:
                                    AutoRedeemChannelsAdapter.set_channel(
                                        self.guild_id,
                                        channel_id,
                                        self.user_id
                                    )
                                except Exception as e:
                                    self.cog.logger.error(f"Failed to save channel to MongoDB: {e}")
                        except ImportError:
                            # MongoDB not available, skip
                            pass
                        
                        # Also save to SQLite for backward compatibility
                        try:
                            self.cog.cursor.execute("""
                                INSERT OR REPLACE INTO auto_redeem_channels 
                                (guild_id, channel_id, added_by, added_at)
                                VALUES (?, ?, ?, ?)
                            """, (self.guild_id, channel_id, self.user_id, datetime.now()))
                            self.cog.giftcode_db.commit()
                            
                            embed = discord.Embed(
                                title="✅ Channel Monitoring Updated",
                                description=(
                                    f"**New monitored channel:** {channel.mention}\n\n"
                                    "**How it works:**\n"
                                    "▸ Bot will monitor this channel for 9-digit FID codes\n"
                                    "▸ Valid FIDs will be automatically added to auto-redeem list\n"
                                    "▸ Players will receive confirmation when added\n\n"
                                    "**Example:** When someone posts `123456789`, the bot will validate and add them."
                                ),
                                color=0x57F287
                            )
                            embed.set_footer(text=f"Updated by {select_interaction.user.name}")
                            
                            await select_interaction.response.edit_message(embed=embed, view=None)
                        except Exception as e:
                            self.cog.logger.error(f"Error saving channel config: {e}")
                            await select_interaction.response.send_message(
                                f"❌ Error saving configuration: {str(e)}",
                                ephemeral=True
                            )
                    
                    async def previous_page(self, btn_interaction: discord.Interaction):
                        if self.current_page > 0:
                            self.current_page -= 1
                            self.update_components()
                            await btn_interaction.response.edit_message(view=self)
                    
                    async def next_page(self, btn_interaction: discord.Interaction):
                        if self.current_page < self.get_total_pages() - 1:
                            self.current_page += 1
                            self.update_components()
                            await btn_interaction.response.edit_message(view=self)
                
                view = ChannelSelectView(text_channels, self, interaction.guild.id, interaction.user.id)
                await interaction.followup.send(
                    f"**Select a new channel to monitor for FID codes:**\n\nTotal channels: {len(text_channels)}",
                    view=view,
                    ephemeral=True
                )
                
            except Exception as e:
                self.logger.exception(f"Error in change channel: {e}")
                await interaction.followup.send(
                    f"❌ An error occurred: {str(e)}",
                    ephemeral=True
                )
            return


        # Handle enable auto redeem
        if custom_id == "auto_redeem_enable":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can configure auto redeem.",
                    ephemeral=True
                )
                return
            
            # Update MongoDB first
            _mongo_enabled = globals().get('mongo_enabled', lambda: False)
            mongo_saved = False
            if _mongo_enabled() and AutoRedeemSettingsAdapter:
                try:
                    self.logger.info(f"📊 MongoDB: Saving auto-redeem ENABLED for guild {interaction.guild.id}...")
                    AutoRedeemSettingsAdapter.set_enabled(
                        interaction.guild.id,
                        True,
                        interaction.user.id
                    )
                    mongo_saved = True
                    self.logger.info(f"✅ MongoDB: Successfully saved auto-redeem ENABLED for guild {interaction.guild.id}")
                except Exception as e:
                    self.logger.error(f"❌ MongoDB: Failed to save auto redeem settings: {e}")
            else:
                if not _mongo_enabled():
                    self.logger.warning("⚠️ MongoDB is not enabled - settings will be lost on restart!")
                elif not AutoRedeemSettingsAdapter:
                    self.logger.warning("⚠️ AutoRedeemSettingsAdapter not available - settings will be lost on restart!")
            
            # Also update SQLite for backward compatibility
            sqlite_saved = False
            try:
                self.logger.info(f"📂 SQLite: Saving auto-redeem ENABLED for guild {interaction.guild.id}...")
                self.cursor.execute("""
                    INSERT OR REPLACE INTO auto_redeem_settings 
                    (guild_id, enabled, updated_by, updated_at)
                    VALUES (?, 1, ?, ?)
                """, (interaction.guild.id, interaction.user.id, datetime.now()))
                self.giftcode_db.commit()
                sqlite_saved = True
                self.logger.info(f"✅ SQLite: Successfully saved auto-redeem ENABLED for guild {interaction.guild.id}")
            except Exception as e:
                self.logger.error(f"❌ SQLite: Failed to save auto redeem settings: {e}")
            
            # Log final persistence status
            if mongo_saved:
                self.logger.info(f"🎉 AUTO-REDEEM ENABLED: Settings saved to MongoDB (PERSISTENT on Render)")
            elif sqlite_saved:
                self.logger.warning(f"⚠️ AUTO-REDEEM ENABLED: Settings saved to SQLite only (TEMPORARY - will reset on Render restart!)")
            else:
                self.logger.error(f"❌ AUTO-REDEEM ENABLED: Failed to save to ANY database!")
            
            embed = discord.Embed(
                title="✅ Auto Redeem Enabled",
                description=(
                    "Automatic gift code redemption is now **enabled**!\n\n"
                    "**What happens next:**\n"
                    "• New gift codes will be automatically redeemed for all members\n"
                    "• Process animation will be shown in the configured channel\n"
                    "• Members will see real-time redemption progress\n\n"
                    "You can disable this anytime from the configure menu."
                ),
                color=0x57F287
            )
            embed.set_footer(text=f"Enabled by {interaction.user.name}")
            
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Handle disable auto redeem
        if custom_id == "auto_redeem_disable":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can configure auto redeem.",
                    ephemeral=True
                )
                return
            
            # Update MongoDB first
            _mongo_enabled = globals().get('mongo_enabled', lambda: False)
            mongo_saved = False
            if _mongo_enabled() and AutoRedeemSettingsAdapter:
                try:
                    self.logger.info(f"📊 MongoDB: Saving auto-redeem DISABLED for guild {interaction.guild.id}...")
                    AutoRedeemSettingsAdapter.set_enabled(
                        interaction.guild.id,
                        False,
                        interaction.user.id
                    )
                    mongo_saved = True
                    self.logger.info(f"✅ MongoDB: Successfully saved auto-redeem DISABLED for guild {interaction.guild.id}")
                except Exception as e:
                    self.logger.error(f"❌ MongoDB: Failed to save auto redeem settings: {e}")
            else:
                if not _mongo_enabled():
                    self.logger.warning("⚠️ MongoDB is not enabled")
                elif not AutoRedeemSettingsAdapter:
                    self.logger.warning("⚠️ AutoRedeemSettingsAdapter not available")
            
            # Also update SQLite for backward compatibility
            sqlite_saved = False
            try:
                self.logger.info(f"📂 SQLite: Saving auto-redeem DISABLED for guild {interaction.guild.id}...")
                self.cursor.execute("""
                    INSERT OR REPLACE INTO auto_redeem_settings 
                    (guild_id, enabled, updated_by, updated_at)
                    VALUES (?, 0, ?, ?)
                """, (interaction.guild.id, interaction.user.id, datetime.now()))
                self.giftcode_db.commit()
                sqlite_saved = True
                self.logger.info(f"✅ SQLite: Successfully saved auto-redeem DISABLED for guild {interaction.guild.id}")
            except Exception as e:
                self.logger.error(f"❌ SQLite: Failed to save auto redeem settings: {e}")
            
            # Log final persistence status
            if mongo_saved:
                self.logger.info(f"🚫 AUTO-REDEEM DISABLED: Settings saved to MongoDB (PERSISTENT)")
            elif sqlite_saved:
                self.logger.warning(f"⚠️ AUTO-REDEEM DISABLED: Settings saved to SQLite only (TEMPORARY)")
            else:
                self.logger.error(f"❌ AUTO-REDEEM DISABLED: Failed to save to ANY database!")
            
            embed = discord.Embed(
                title="🔴 Auto Redeem Disabled",
                description=(
                    "Automatic gift code redemption is now **disabled**.\n\n"
                    "**What this means:**\n"
                    "• New gift codes will NOT be automatically redeemed\n"
                    "• You can still manually redeem codes\n"
                    "• Member list is preserved\n\n"
                    "You can re-enable this anytime from the configure menu."
                ),
                color=0xED4245
            )
            embed.set_footer(text=f"Disabled by {interaction.user.name}")
            
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Handle reset code status
        if custom_id == "auto_redeem_reset_code":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can reset code status.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                # Fetch all gift codes from database
                all_codes = []
                
                # Try MongoDB first - use get_all() method
                _mongo_enabled = globals().get('mongo_enabled', lambda: False)
                if _mongo_enabled() and GiftCodesAdapter:
                    try:
                        mongo_codes = GiftCodesAdapter.get_all()
                        if mongo_codes:
                            all_codes = []
                            for code_data in mongo_codes:
                                try:
                                    # Handle different formats: tuple, dict, or other
                                    if isinstance(code_data, tuple):
                                        code_str = str(code_data[0]) if code_data else ''
                                        date_str = str(code_data[1]) if len(code_data) > 1 else ''
                                        processed = code_data[2] if len(code_data) > 2 else False
                                    elif isinstance(code_data, dict):
                                        code_str = str(code_data.get('giftcode', ''))
                                        date_str = str(code_data.get('date', ''))
                                        processed = code_data.get('auto_redeem_processed', False)
                                    else:
                                        # Unknown format, convert to string
                                        code_str = str(code_data)
                                        date_str = ''
                                        processed = False
                                    
                                    if code_str:  # Only add non-empty codes
                                        all_codes.append((code_str, date_str, processed))
                                except Exception as e:
                                    self.logger.warning(f"Failed to parse MongoDB code entry: {e}")
                                    continue
                            
                            self.logger.info(f"Fetched {len(all_codes)} codes from MongoDB for reset")
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch codes from MongoDB: {e}")
                
                # Fallback to SQLite if MongoDB failed or not enabled
                if not all_codes:
                    try:
                        self.logger.info("📂 Fetching codes from SQLite database...")
                        self.cursor.execute("""
                            SELECT giftcode, date, auto_redeem_processed
                            FROM gift_codes
                            ORDER BY added_at DESC
                        """)
                        all_codes = self.cursor.fetchall()
                        self.logger.info(f"Fetched {len(all_codes)} codes from SQLite for reset")
                    except Exception as e:
                        self.logger.error(f"❌ SQLite fetch failed: {e}")
                
                if not all_codes:
                    await interaction.followup.send(
                        "📋 No gift codes found in the database.",
                        ephemeral=True
                    )
                    return
                
                # Limit to most recent 25 codes for dropdown
                recent_codes = all_codes[:25]
                
                # Create dropdown select view
                class CodeResetSelectView(discord.ui.View):
                    def __init__(self, codes_list, cog_instance):
                        super().__init__(timeout=300)
                        self.codes = codes_list
                        self.cog = cog_instance
                        
                        # Create select menu
                        options = []
                        for code, date, processed in self.codes:
                            status_emoji = "✅" if processed else "⏳"
                            status_text = "Processed" if processed else "Unprocessed"
                            
                            options.append(
                                discord.SelectOption(
                                    label=f"{code[:50]}",  # Truncate long codes
                                    description=f"{status_text} • {date if date else 'No date'}",
                                    value=code,
                                    emoji=status_emoji
                                )
                            )
                        
                        select = discord.ui.Select(
                            placeholder="Select a code to reset...",
                            options=options,
                            custom_id="code_to_reset_select"
                        )
                        select.callback = self.reset_code
                        self.add_item(select)
                    
                    async def reset_code(self, select_interaction: discord.Interaction):
                        try:
                            await select_interaction.response.defer(ephemeral=True)
                            
                            selected_code = select_interaction.data["values"][0]
                            
                            # Reset in MongoDB if available - use insert() to update
                            _mongo_enabled = globals().get('mongo_enabled', lambda: False)
                            mongo_success = False
                            if _mongo_enabled() and GiftCodesAdapter:
                                try:
                                    # MongoDB adapter doesn't have update_code, so we need to use insert with replace
                                    # Or just skip MongoDB update and rely on SQLite
                                    self.cog.logger.info(f"Skipping MongoDB update (no update_code method), using SQLite only")
                                except Exception as e:
                                    self.cog.logger.error(f"MongoDB operation failed: {e}")
                            
                            # Also reset in SQLite for consistency
                            sqlite_success = False
                            try:
                                self.cog.cursor.execute(
                                    "UPDATE gift_codes SET auto_redeem_processed = 0 WHERE giftcode = ?",
                                    (selected_code,)
                                )
                                self.cog.giftcode_db.commit()
                                sqlite_success = True
                                self.cog.logger.info(f"Reset code {selected_code} in SQLite")
                            except Exception as e:
                                self.cog.logger.error(f"Failed to reset code in SQLite: {e}")
                            
                            if mongo_success or sqlite_success:
                                embed = discord.Embed(
                                    title="✅ Code Status Reset",
                                    description=(
                                        f"**Code:** `{selected_code}`\n\n"
                                        "The auto-redeem processed status has been reset.\n\n"
                                        "**What happens next:**\n"
                                        "• This code will be detected as unprocessed\n"
                                        "• Auto-redeem will trigger for this code on next check\n"
                                        "• You can test the auto-redeem functionality again\n\n"
                                        f"**Updated in:** {('MongoDB, ' if mongo_success else '') + ('SQLite' if sqlite_success else '')}"
                                    ),
                                    color=0x57F287
                                )
                                embed.set_footer(
                                    text=f"Reset by {select_interaction.user.name}",
                                    icon_url=select_interaction.user.display_avatar.url
                                )
                                await select_interaction.followup.send(embed=embed, ephemeral=True)
                            else:
                                await select_interaction.followup.send(
                                    "❌ Failed to reset code status in both databases.",
                                    ephemeral=True
                                )
                        
                        except Exception as e:
                            self.cog.logger.exception(f"Error resetting code: {e}")
                            try:
                                await select_interaction.followup.send(
                                    f"❌ An error occurred: {str(e)}",
                                    ephemeral=True
                                )
                            except:
                                pass
                
                view = CodeResetSelectView(recent_codes, self)
                
                embed = discord.Embed(
                    title="🔄 Reset Code Status",
                    description=(
                        f"**Total Codes:** {len(all_codes)}\n"
                        f"**Showing:** {len(recent_codes)} most recent\n\n"
                        "Select a code below to reset its auto-redeem processed status.\n\n"
                        "**Legend:**\n"
                        "✅ - Already processed\n"
                        "⏳ - Unprocessed\n\n"
                        "*Resetting will allow the code to be auto-redeemed again.*"
                    ),
                    color=0x5865F2
                )
                embed.set_footer(
                    text=f"{interaction.guild.name} • Magnus🚀",
                    icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
                )
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
            except Exception as e:
                self.logger.exception(f"Error in reset code status: {e}")
                try:
                    await interaction.followup.send(
                        f"❌ An error occurred: {str(e)}",
                        ephemeral=True
                    )
                except:
                    pass
            return


        # Handle delete code
        if custom_id == "auto_redeem_delete_code":
            if not await self.check_admin_permission(interaction.user.id):
                await interaction.response.send_message(
                    "❌ Only administrators can delete codes.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                # Fetch all gift codes from database
                all_codes = []
                
                # Try MongoDB first - but use get_all() instead of get_all_codes()
                _mongo_enabled = globals().get('mongo_enabled', lambda: False)
                if _mongo_enabled() and GiftCodesAdapter:
                    try:
                        mongo_codes = GiftCodesAdapter.get_all()
                        if mongo_codes:
                            all_codes = []
                            for code_data in mongo_codes:
                                try:
                                    # Handle different formats: tuple, dict, or other
                                    if isinstance(code_data, tuple):
                                        code_str = str(code_data[0]) if code_data else ''
                                        date_str = str(code_data[1]) if len(code_data) > 1 else ''
                                    elif isinstance(code_data, dict):
                                        code_str = str(code_data.get('giftcode', ''))
                                        date_str = str(code_data.get('date', ''))
                                    else:
                                        # Unknown format, convert to string
                                        code_str = str(code_data)
                                        date_str = ''
                                    
                                    if code_str:  # Only add non-empty codes
                                        all_codes.append((code_str, date_str, False))
                                except Exception as e:
                                    self.logger.warning(f"Failed to parse MongoDB code entry: {e}")
                                    continue
                            
                            self.logger.info(f"Fetched {len(all_codes)} codes from MongoDB for deletion")
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch codes from MongoDB: {e}")
                
                # Fallback to SQLite if MongoDB failed or not enabled
                if not all_codes:
                    try:
                        self.logger.info("📂 Fetching codes from SQLite database...")
                        self.cursor.execute("""
                            SELECT giftcode, date, auto_redeem_processed
                            FROM gift_codes
                            ORDER BY added_at DESC
                        """)
                        all_codes = self.cursor.fetchall()
                        self.logger.info(f"Fetched {len(all_codes)} codes from SQLite for deletion")
                    except Exception as e:
                        self.logger.error(f"❌ SQLite fetch failed: {e}")
                
                if not all_codes:
                    await interaction.followup.send(
                        "📋 No gift codes found in the database.",
                        ephemeral=True
                    )
                    return
                
                # Limit to most recent 25 codes for dropdown
                recent_codes = all_codes[:25]
                
                # Create dropdown select view
                class CodeDeleteSelectView(discord.ui.View):
                    def __init__(self, codes_list, cog_instance):
                        super().__init__(timeout=300)
                        self.codes = codes_list
                        self.cog = cog_instance
                        
                        # Create select menu
                        options = []
                        for code, date, processed in self.codes:
                            options.append(
                                discord.SelectOption(
                                    label=f"{code[:50]}",  # Truncate long codes
                                    description=f"Added: {date if date else 'Unknown date'}",
                                    value=code,
                                    emoji="🗑️"
                                )
                            )
                        
                        select = discord.ui.Select(
                            placeholder="Select a code to delete...",
                            options=options,
                            custom_id="code_to_delete_select"
                        )
                        select.callback = self.confirm_delete
                        self.add_item(select)
                    
                    async def confirm_delete(self, select_interaction: discord.Interaction):
                        try:
                            selected_code = select_interaction.data["values"][0]
                            
                            # Create confirmation view
                            class ConfirmDeleteView(discord.ui.View):
                                def __init__(self, code_to_delete, cog_instance):
                                    super().__init__(timeout=60)
                                    self.code = code_to_delete
                                    self.cog = cog_instance
                                
                                @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger, emoji="✅")
                                async def confirm(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                                    await btn_interaction.response.defer(ephemeral=True)
                                    
                                    # Delete from MongoDB if available
                                    _mongo_enabled = globals().get('mongo_enabled', lambda: False)
                                    mongo_deleted = False
                                    if _mongo_enabled() and GiftCodesAdapter:
                                        try:
                                            # Use the delete method if available, otherwise skip
                                            if hasattr(GiftCodesAdapter, 'delete'):
                                                GiftCodesAdapter.delete(self.code)
                                                mongo_deleted = True
                                                self.cog.logger.info(f"Deleted code {self.code} from MongoDB")
                                            else:
                                                self.cog.logger.info("MongoDB delete method not available, using SQLite only")
                                        except Exception as e:
                                            self.cog.logger.error(f"Failed to delete code from MongoDB: {e}")
                                    
                                    # Delete from SQLite
                                    sqlite_deleted = False
                                    try:
                                        self.cog.cursor.execute(
                                            "DELETE FROM gift_codes WHERE giftcode = ?",
                                            (self.code,)
                                        )
                                        rows_affected = self.cog.cursor.rowcount
                                        self.cog.giftcode_db.commit()
                                        if rows_affected > 0:
                                            sqlite_deleted = True
                                            self.cog.logger.info(f"Deleted code {self.code} from SQLite")
                                        else:
                                            self.cog.logger.warning(f"Code {self.code} not found in SQLite")
                                    except Exception as e:
                                        self.cog.logger.error(f"Failed to delete code from SQLite: {e}")
                                    
                                    if mongo_deleted or sqlite_deleted:
                                        embed = discord.Embed(
                                            title="✅ Code Deleted",
                                            description=(
                                                f"**Code:** `{self.code}`\n\n"
                                                "The gift code has been permanently deleted.\n\n"
                                                "**Deleted from:**\n"
                                                f"{'• MongoDB ✅\n' if mongo_deleted else ''}"
                                                f"{'• SQLite ✅\n' if sqlite_deleted else ''}\n"
                                                "**Note:** This action cannot be undone."
                                            ),
                                            color=0x57F287
                                        )
                                        embed.set_footer(
                                            text=f"Deleted by {btn_interaction.user.name}",
                                            icon_url=btn_interaction.user.display_avatar.url
                                        )
                                        await btn_interaction.followup.send(embed=embed, ephemeral=True)
                                    else:
                                        await btn_interaction.followup.send(
                                            "❌ Failed to delete code from both databases.",
                                            ephemeral=True
                                        )
                                
                                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
                                async def cancel(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                                    embed = discord.Embed(
                                        title="❌ Deletion Cancelled",
                                        description="The code was not deleted.",
                                        color=0x5865F2
                                    )
                                    await btn_interaction.response.edit_message(embed=embed, view=None)
                            
                            # Show confirmation dialog
                            confirm_embed = discord.Embed(
                                title="⚠️ Confirm Code Deletion",
                                description=(
                                    f"Are you sure you want to **permanently delete** this code?\n\n"
                                    f"**Code:** `{selected_code}`\n\n"
                                    "⚠️ **This action cannot be undone!**\n"
                                    "The code will be removed from both MongoDB and SQLite databases."
                                ),
                                color=0xED4245
                            )
                            
                            confirm_view = ConfirmDeleteView(selected_code, self.cog)
                            await select_interaction.response.edit_message(embed=confirm_embed, view=confirm_view)
                        
                        except Exception as e:
                            self.cog.logger.exception(f"Error in delete confirmation: {e}")
                            try:
                                await select_interaction.followup.send(
                                    f"❌ An error occurred: {str(e)}",
                                    ephemeral=True
                                )
                            except:
                                pass
                
                view = CodeDeleteSelectView(recent_codes, self)
                
                embed = discord.Embed(
                    title="🗑️ Delete Gift Code",
                    description=(
                        f"**Total Codes:** {len(all_codes)}\n"
                        f"**Showing:** {len(recent_codes)} most recent\n\n"
                        "Select a code below to permanently delete it.\n\n"
                        "⚠️ **Warning:** Deleted codes cannot be recovered!\n"
                        "*You will be asked to confirm before deletion.*"
                    ),
                    color=0xED4245
                )
                embed.set_footer(
                    text=f"{interaction.guild.name} • Magnus🚀",
                    icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1436745053442805830/unnamed_5.png"
                )
                
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
            except Exception as e:
                self.logger.exception(f"Error in delete code: {e}")
                try:
                    await interaction.followup.send(
                        f"❌ An error occurred: {str(e)}",
                        ephemeral=True
                    )
                except:
                    pass
            return


    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor configured channels for FID codes"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in a monitored channel
        try:
            # Import at method level to avoid scope issues
            from db.mongo_adapters import mongo_enabled, AutoRedeemChannelsAdapter
            
            monitored_channel_id = None
            
            # Check MongoDB first
            if mongo_enabled() and AutoRedeemChannelsAdapter:
                try:
                    channel_config = AutoRedeemChannelsAdapter.get_channel(message.guild.id)
                    if channel_config:
                        monitored_channel_id = channel_config.get('channel_id')
                        self.logger.debug(f"Found monitored channel {monitored_channel_id} in MongoDB for guild {message.guild.id}")
                except Exception as e:
                    self.logger.warning(f"Failed to get channel from MongoDB: {e}")
            
            # Fallback to SQLite if MongoDB didn't return a result
            if monitored_channel_id is None:
                self.cursor.execute(
                    "SELECT channel_id FROM auto_redeem_channels WHERE guild_id = ?",
                    (message.guild.id,)
                )
                result = self.cursor.fetchone()
                if result:
                    monitored_channel_id = result[0]
                    self.logger.debug(f"Found monitored channel {monitored_channel_id} in SQLite for guild {message.guild.id}")
                    
                    # Sync to MongoDB if found in SQLite but not in MongoDB
                    if mongo_enabled() and AutoRedeemChannelsAdapter:
                        try:
                            AutoRedeemChannelsAdapter.set_channel(
                                message.guild.id,
                                monitored_channel_id,
                                message.author.id
                            )
                            self.logger.info(f"Synced channel config to MongoDB for guild {message.guild.id}")
                        except Exception as e:
                            self.logger.warning(f"Failed to sync channel to MongoDB: {e}")
            
            # Check if current channel is the monitored channel
            if not monitored_channel_id or monitored_channel_id != message.channel.id:
                return  # Not a monitored channel
            
            # Extract 9-digit codes from message
            fid_pattern = r'\b\d{9}\b'
            fids = re.findall(fid_pattern, message.content)
            
            if not fids:
                return  # No FIDs found
            
            self.logger.info(f"Detected {len(fids)} FID(s) in monitored channel {message.channel.id} (guild {message.guild.id}): {fids}")
            
            # Process each FID
            for fid in fids:
                try:
                    self.logger.debug(f"Processing FID {fid} from user {message.author.id}")
                    
                    # Check if already exists
                    if self.AutoRedeemDB.member_exists(self, message.guild.id, fid):
                        self.logger.info(f"FID {fid} already exists in auto-redeem list for guild {message.guild.id}")
                        await message.reply(
                            f"⚠️ {message.author.mention} Your FID `{fid}` is already in the auto-redeem list!",
                            delete_after=10
                        )
                        continue
                    
                    # Fetch player data from API
                    self.logger.debug(f"Fetching player data for FID {fid}")
                    player_data = await self.fetch_player_data(fid)
                    
                    if not player_data:
                        self.logger.warning(f"Invalid FID {fid} - API returned no data")
                        await message.reply(
                            f"❌ {message.author.mention} Invalid FID `{fid}`. Please check and try again.",
                            delete_after=15
                        )
                        continue
                    
                    # Add to auto-redeem list
                    member_data = {
                        'nickname': player_data['nickname'],
                        'furnace_lv': player_data['furnace_lv'],
                        'avatar_image': player_data.get('avatar_image', ''),
                        'added_by': message.author.id
                    }
                    
                    self.logger.debug(f"Adding FID {fid} ({player_data['nickname']}) to auto-redeem list")
                    success = self.AutoRedeemDB.add_member(
                        self,
                        message.guild.id,
                        fid,
                        member_data
                    )
                    
                    if success:
                        formatted_fc = self.format_furnace_level(player_data['furnace_lv'])
                        embed = discord.Embed(
                            title="✨ Auto-Redeem Registered",
                            description=f"✅ **{player_data['nickname']}** is now enrolled for automated gift codes.",
                            color=0x2ecc71
                        )
                        embed.add_field(name="Player ID", value=f"`{fid}`", inline=True)
                        embed.add_field(name="Furnace", value=f"`{formatted_fc}`", inline=True)
                        embed.add_field(name="🚀 Auto-Processing", value="`Initializing...`", inline=False)
                        
                        # Add player avatar if available
                        avatar = player_data.get('avatar_image')
                        if avatar and str(avatar).startswith('http'):
                            embed.set_thumbnail(url=avatar)
                        
                        embed.set_footer(
                            text="Whiteout Survival || Magnus", 
                            icon_url=self.bot.user.display_avatar.url if self.bot.user.display_avatar else None
                        )
                        
                        sent_msg = await message.reply(embed=embed)
                        self.logger.info(f"✅ Successfully auto-added {player_data['nickname']} ({fid}) from channel in guild {message.guild.id}")
                        
                        # Start immediate redemption process for active codes
                        async def process_initial_redemptions():
                            try:
                                # Get all valid/active gift codes from DB
                                self.cursor.execute("SELECT giftcode FROM gift_codes WHERE validation_status = 'validated' OR validation_status = 'pending'")
                                active_codes = [r[0] for r in self.cursor.fetchall()]
                                
                                if not active_codes:
                                    embed.set_field_at(2, name="🚀 Auto-Processing", value="`No active codes found to redeem.`", inline=False)
                                    await sent_msg.edit(embed=embed)
                                    return

                                total = len(active_codes)
                                embed.set_field_at(2, name="🚀 Auto-Processing", value=f"`Checking {total} active codes...`", inline=False)
                                await sent_msg.edit(embed=embed)
                                
                                redeemed = 0
                                already = 0
                                failed = 0
                                
                                # Process each code
                                for i, code in enumerate(active_codes):
                                    embed.set_field_at(2, name="🚀 Auto-Processing", value=f"`Processing code {i+1}/{total}:` **`{code}`**", inline=False)
                                    await sent_msg.edit(embed=embed)
                                    
                                    # Use the core redemption method
                                    status, s_count, a_count, f_count = await self._redeem_for_member(
                                        message.guild.id, 
                                        fid, 
                                        player_data['nickname'], 
                                        player_data['furnace_lv'], 
                                        code
                                    )
                                    
                                    redeemed += s_count
                                    already += a_count
                                    failed += f_count
                                    
                                    # Small delay between codes to be safe with rate limits
                                    await asyncio.sleep(1)
                                
                                # Final update
                                embed.set_field_at(2, name="🚀 Redemption Results", value=(
                                    f"✅ Success: `{redeemed}`\n"
                                    f"ℹ️ Already Claimed: `{already}`\n"
                                    f"❌ Failed: `{failed}`"
                                ), inline=False)
                                embed.title = "✨ Auto-Redeem Complete"
                                await sent_msg.edit(embed=embed)
                                
                            except Exception as e:
                                self.logger.error(f"Error in initial redemption process for FID {fid}: {e}")
                                embed.set_field_at(2, name="🚀 Auto-Processing", value="`⚠️ Error during batch redemption.`", inline=False)
                                try: await sent_msg.edit(embed=embed)
                                except: pass
                        
                        # Run in background
                        asyncio.create_task(process_initial_redemptions())
                    else:
                        self.logger.error(f"Failed to add ID {fid} to database for guild {message.guild.id}")
                        await message.reply(
                            f"❌ {message.author.mention} Failed to add ID `{fid}`. It may already exist.",
                            delete_after=10
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error processing ID {fid} from channel: {e}", exc_info=True)
                    await message.reply(
                        f"❌ {message.author.mention} An error occurred while processing ID `{fid}`.",
                        delete_after=10
                    )
                    
        except Exception as e:
            self.logger.error(f"Error in on_message FID detection: {e}", exc_info=True)
    
    @commands.command(name='test_auto_redeem')
    @commands.is_owner()
    async def test_auto_redeem_command(self, ctx, giftcode: str):
        """Test auto-redeem with an existing gift code (Owner only)"""
        await ctx.send(f"🧪 Testing auto-redeem with code: `{giftcode}`\nPlease wait...")
        
        try:
            # Check if auto-redeem is enabled first
            enabled = False
            if mongo_enabled() and AutoRedeemSettingsAdapter:
                try:
                    settings = AutoRedeemSettingsAdapter.get_settings(ctx.guild.id)
                    if settings:
                        enabled = settings.get('enabled', False)
                except Exception as e:
                    self.logger.warning(f"Failed to check MongoDB settings: {e}")
            
            if not enabled:
                self.cursor.execute(
                    "SELECT enabled FROM auto_redeem_settings WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                result = self.cursor.fetchone()
                enabled = result[0] == 1 if result else False
            
            if not enabled:
                await ctx.send(f"❌ Auto-redeem is **disabled** for this server!\nPlease enable it first using the `/manage` command → Auto Redeem Configuration → Enable Auto-Redeem")
                return
            
            # Trigger the auto-redeem process and wait for it to complete
            await self.process_auto_redeem(ctx.guild.id, giftcode)
            await ctx.send(f"✅ Auto-redeem test completed! Check the auto-redeem channel for results.")
        except Exception as e:
            await ctx.send(f"❌ Error during test: {str(e)}")
            self.logger.exception(f"Error in test_auto_redeem: {e}")

    @commands.command(name="stop_auto_redeem", aliases=["stop_redeem"])
    async def stop_auto_redeem_text(self, ctx):
        """Stop the ongoing auto-redeem process for this server"""
        if not await self.check_admin_permission(ctx.author.id):
            await ctx.reply("❌ Only administrators can use this command.", delete_after=5)
            return
            
        guild_id = ctx.guild.id
        
        # Set stop signal to halt current execution
        self.stop_signals[guild_id] = True
        
        # PERSISTENCE: Disable auto-redeem in database to prevent future runs
        # Update MongoDB first
        _mongo_enabled = globals().get('mongo_enabled', lambda: False)
        mongo_saved = False
        if _mongo_enabled() and AutoRedeemSettingsAdapter:
            try:
                self.logger.info(f"📊 MongoDB: Saving auto-redeem DISABLED for guild {guild_id} (via STOP command)...")
                AutoRedeemSettingsAdapter.set_enabled(
                    guild_id,
                    False,
                    ctx.author.id
                )
                mongo_saved = True
            except Exception as e:
                self.logger.error(f"❌ MongoDB: Failed to save auto redeem settings: {e}")
        
        # Also update SQLite for backward compatibility
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO auto_redeem_settings 
                (guild_id, enabled, updated_by, updated_at)
                VALUES (?, 0, ?, ?)
            """, (guild_id, ctx.author.id, datetime.now()))
            self.giftcode_db.commit()
        except Exception as e:
            self.logger.error(f"❌ SQLite: Failed to save auto redeem settings: {e}")
            
        # Check if any redemption is active
        active_count = 0
        current_active = []
        async with self._redemption_lock:
            for gid, code in self._active_redemptions:
                if gid == guild_id:
                    active_count += 1
                    current_active.append(code)
        
        if active_count > 0:
            codes_str = ", ".join(current_active)
            await ctx.reply(f"🛑 **Stopping Auto-Redeem**\n\nSignal sent to stop redemption for code(s): `{codes_str}`.\nProcesses should halt shortly.")
            self.logger.info(f"Stop signal sent for guild {guild_id} by {ctx.author}")
        else:
            await ctx.reply("ℹ️ No auto-redeem process is currently running for this server.")


async def setup(bot):
    await bot.add_cog(ManageGiftCode(bot))
