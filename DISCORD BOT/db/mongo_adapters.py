from typing import Optional
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import uuid

from .mongo_client_wrapper import get_mongo_client_sync, get_mongo_client

logger = logging.getLogger(__name__)


def _get_db_main():
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise ValueError('MONGO_URI not set')
    client = get_mongo_client_sync(uri)
    db_name = os.getenv('MONGO_DB_NAME', 'reminderbot')
    return client[db_name]

def _get_db_wos():
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise ValueError('MONGO_URI not set')
    client = get_mongo_client_sync(uri)
    db_name = os.getenv('MONGO_DB_WOS', 'reminderbot')
    return client[db_name]

def _get_db_reminders():
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise ValueError('MONGO_URI not set')
    client = get_mongo_client_sync(uri)
    db_name = os.getenv('MONGO_DB_REMINDERS', 'reminderbot')
    return client[db_name]


async def _get_db_main_async():
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise ValueError('MONGO_URI not set')
    client = await get_mongo_client(uri)
    db_name = os.getenv('MONGO_DB_NAME', 'reminderbot')
    return client[db_name]

async def _get_db_wos_async():
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise ValueError('MONGO_URI not set')
    client = await get_mongo_client(uri)
    db_name = os.getenv('MONGO_DB_WOS', 'reminderbot')
    return client[db_name]

async def _get_db_reminders_async():
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise ValueError('MONGO_URI not set')
    client = await get_mongo_client(uri)
    db_name = os.getenv('MONGO_DB_REMINDERS', 'reminderbot')
    return client[db_name]


def mongo_enabled() -> bool:
    return bool(os.getenv('MONGO_URI'))


def get_mongo_db():
    """Public function to get MongoDB database instance (Main)"""
    return _get_db_main()


class UserTimezonesAdapter:
    COLL = 'user_timezones'

    @staticmethod
    def load_all() -> Dict[str, str]:
        try:
            db = _get_db_main()
            docs = db[UserTimezonesAdapter.COLL].find({})
            return {str(d['_id']): d.get('timezone') for d in docs}
        except Exception as e:
            logger.error(f'Failed to load user_timezones from Mongo: {e}')
            return {}

    @staticmethod
    def get(user_id: str) -> Optional[str]:
        try:
            db = _get_db_main()
            d = db[UserTimezonesAdapter.COLL].find_one({'_id': str(user_id)})
            return d.get('timezone') if d else None
        except Exception as e:
            logger.error(f'Failed to get timezone for {user_id}: {e}')
            return None

    @staticmethod
    def set(user_id: str, tz_abbr: str) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[UserTimezonesAdapter.COLL].update_one(
                {'_id': str(user_id)},
                {'$set': {'timezone': tz_abbr.lower(), 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set timezone for {user_id}: {e}')
            return False

    @staticmethod
    async def get_async(user_id: str) -> Optional[str]:
        try:
            db = await _get_db_main_async()
            d = await db[UserTimezonesAdapter.COLL].find_one({'_id': str(user_id)})
            return d.get('timezone') if d else None
        except Exception as e:
            logger.error(f'Failed to get timezone (async) for {user_id}: {e}')
            return None

    @staticmethod
    async def set_async(user_id: str, tz_abbr: str) -> bool:
        try:
            db = await _get_db_main_async()
            now = datetime.utcnow().isoformat()
            await db[UserTimezonesAdapter.COLL].update_one(
                {'_id': str(user_id)},
                {'$set': {'timezone': tz_abbr.lower(), 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set timezone (async) for {user_id}: {e}')
            return False


class BirthdaysAdapter:
    COLL = 'birthdays'

    @staticmethod
    def load_all() -> Dict[str, Any]:
        try:
            db = _get_db_main()
            docs = db[BirthdaysAdapter.COLL].find({})
            return {str(d['_id']): {'day': int(d.get('day')), 'month': int(d.get('month'))} for d in docs}
        except Exception as e:
            logger.error(f'Failed to load birthdays from Mongo: {e}')
            return {}

    @staticmethod
    def get(user_id: str):
        try:
            db = _get_db_main()
            d = db[BirthdaysAdapter.COLL].find_one({'_id': str(user_id)})
            if not d:
                return None
            return {'day': int(d['day']), 'month': int(d['month'])}
        except Exception as e:
            logger.error(f'Failed to get birthday for {user_id}: {e}')
            return None

    @staticmethod
    def set(user_id: str, day: int, month: int) -> bool:
        try:
            db = _get_db_main()
            db[BirthdaysAdapter.COLL].update_one(
                {'_id': str(user_id)},
                {'$set': {'day': int(day), 'month': int(month), 'updated_at': datetime.utcnow().isoformat()},
                 '$setOnInsert': {'created_at': datetime.utcnow().isoformat()}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set birthday for {user_id}: {e}')
            return False

    @staticmethod
    def remove(user_id: str) -> bool:
        try:
            db = _get_db_main()
            res = db[BirthdaysAdapter.COLL].delete_one({'_id': str(user_id)})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to remove birthday for {user_id}: {e}')
            return False


class UserProfilesAdapter:
    COLL = 'user_profiles'

    @staticmethod
    def load_all() -> Dict[str, Any]:
        try:
            db = _get_db_main()
            docs = db[UserProfilesAdapter.COLL].find({})
            result = {}
            for d in docs:
                data = d.copy()
                data.pop('_id', None)
                result[str(d['_id'])] = data
            return result
        except Exception as e:
            logger.error(f'Failed to load user profiles from Mongo: {e}')
            return {}

    @staticmethod
    def get(user_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = _get_db_main()
            d = db[UserProfilesAdapter.COLL].find_one({'_id': str(user_id)})
            if not d:
                return None
            d.pop('_id', None)
            return d
        except Exception as e:
            logger.error(f'Failed to get profile for {user_id}: {e}')
            return None

    @staticmethod
    def set(user_id: str, data: Dict[str, Any]) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            payload = data.copy()
            # Avoid conflicts where payload already contains 'created_at' which
            # would clash with our $setOnInsert created_at below.
            payload.pop('created_at', None)
            payload['updated_at'] = now
            db[UserProfilesAdapter.COLL].update_one({'_id': str(user_id)}, {'$set': payload, '$setOnInsert': {'created_at': now}}, upsert=True)
            return True
        except Exception as e:
            logger.error(f'Failed to set profile for {user_id}: {e}')
            return False


class GiftcodeStateAdapter:
    COLL = 'giftcode_state'

    @staticmethod
    def get_state() -> Dict[str, Any]:
        try:
            db = _get_db_main()
            d = db[GiftcodeStateAdapter.COLL].find_one({'_id': 'giftcode_state'})
            if not d:
                return {}
            d.pop('_id', None)
            return d
        except Exception as e:
            logger.error(f'Failed to get giftcode state from Mongo: {e}')
            return {}

    @staticmethod
    def set_state(state: Dict[str, Any]) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            payload = state.copy()
            # Remove created_at from payload to avoid $set vs $setOnInsert conflict
            payload.pop('created_at', None)
            payload['updated_at'] = now
            db[GiftcodeStateAdapter.COLL].update_one({'_id': 'giftcode_state'}, {'$set': payload, '$setOnInsert': {'created_at': now}}, upsert=True)
            return True
        except Exception as e:
            logger.error(f'Failed to set giftcode state in Mongo: {e}')
            return False



class RemindersAdapter:
    """Adapter for managing reminders in MongoDB"""
    COLL = 'reminders'

    @staticmethod
    def add_reminder(data: Dict[str, Any]) -> str:
        """Add a new reminder"""
        try:
            db = _get_db_reminders()
            now = datetime.utcnow().isoformat()
            
            # Ensure required fields
            data['created_at'] = data.get('created_at', now)
            data['is_active'] = 1
            data['is_sent'] = 0
            
            # Check for duplicate active reminder
            existing = db[RemindersAdapter.COLL].find_one({
                'user_id': data['user_id'],
                'channel_id': data['channel_id'],
                'reminder_time': data['reminder_time'],
                'message': data['message'],
                'is_active': 1,
                'is_sent': 0
            })
            
            if existing:
                # Update existing
                updates = {k: v for k, v in data.items() if v is not None and k not in ['_id', 'user_id', 'channel_id', 'reminder_time', 'message', 'created_at']}
                if updates:
                    db[RemindersAdapter.COLL].update_one({'_id': existing['_id']}, {'$set': updates})
                return str(existing['_id'])
            
            # Insert new
            # Generate a pseudo-unique int ID for compatibility
            import time
            import random
            reminder_id = int(time.time() * 1000) + random.randint(0, 999)
            data['_id'] = reminder_id
            
            db[RemindersAdapter.COLL].insert_one(data)
            return reminder_id
        except Exception as e:
            logger.error(f'Failed to add reminder to Mongo: {e}')
            return -1

    @staticmethod
    def get_due_reminders() -> List[Dict[str, Any]]:
        """Get all active reminders that are due"""
        try:
            db = _get_db_reminders()
            now = datetime.utcnow().isoformat()
            
            cursor = db[RemindersAdapter.COLL].find({
                'is_active': 1, 
                'is_sent': 0,
                'reminder_time': {'$lte': now}
            }).sort('reminder_time', 1)
            
            docs = list(cursor)
            for doc in docs:
                # Ensure _id is serializable
                if '_id' in doc and not isinstance(doc['_id'], (str, int, float)):
                    doc['_id'] = str(doc['_id'])
            return docs
        except Exception as e:
            logger.error(f'Failed to get due reminders from Mongo: {e}')
            return []

    @staticmethod
    def mark_reminder_sent(reminder_id: Union[int, str]) -> bool:
        """Mark a reminder as sent"""
        try:
            db = _get_db_reminders()
            try:
                if isinstance(reminder_id, str) and reminder_id.isdigit():
                    reminder_id = int(reminder_id)
            except:
                pass
                
            res = db[RemindersAdapter.COLL].update_one(
                {'_id': reminder_id, 'is_sent': 0},
                {'$set': {'is_sent': 1}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f'Failed to mark reminder {reminder_id} sent in Mongo: {e}')
            return False

    @staticmethod
    def update_reminder_fields(reminder_id: Union[int, str], fields: Dict[str, Any]) -> bool:
        """Update arbitrary fields"""
        try:
            db = _get_db_reminders()
            try:
                if isinstance(reminder_id, str) and reminder_id.isdigit():
                    reminder_id = int(reminder_id)
            except:
                pass

            allowed = {'image_url', 'thumbnail_url', 'body', 'footer_text', 'footer_icon_url', 'mention', 'reminder_time', 'author_url'}
            updates = {k: v for k, v in fields.items() if k in allowed}
            
            if not updates:
                return False
                
            res = db[RemindersAdapter.COLL].update_one(
                {'_id': reminder_id},
                {'$set': updates}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f'Failed to update reminder {reminder_id} in Mongo: {e}')
            return False

    @staticmethod
    def get_user_reminders(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get active reminders for a user"""
        try:
            db = _get_db_reminders()
            cursor = db[RemindersAdapter.COLL].find({
                'user_id': str(user_id),
                'is_active': 1,
                'is_sent': 0
            }).sort('reminder_time', 1).limit(limit)
            docs = list(cursor)
            for doc in docs:
                if '_id' in doc and not isinstance(doc['_id'], (str, int, float)):
                    doc['_id'] = str(doc['_id'])
            return docs
        except Exception as e:
            logger.error(f'Failed to get reminders for {user_id} from Mongo: {e}')
            return []

    @staticmethod
    def delete_reminder(reminder_id: Union[int, str], user_id: str) -> bool:
        """Delete (deactivate) a reminder"""
        try:
            db = _get_db_reminders()
            try:
                if isinstance(reminder_id, str) and reminder_id.isdigit():
                    reminder_id = int(reminder_id)
            except:
                pass

            res = db[RemindersAdapter.COLL].update_one(
                {'_id': reminder_id, 'user_id': str(user_id), 'is_active': 1},
                {'$set': {'is_active': 0}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f'Failed to delete reminder {reminder_id} in Mongo: {e}')
            return False

    @staticmethod
    def get_all_active_reminders() -> List[Dict[str, Any]]:
        """Get ALL active reminders (admin)"""
        try:
            db = _get_db_reminders()
            cursor = db[RemindersAdapter.COLL].find({
                'is_active': 1,
                'is_sent': 0
            }).sort('reminder_time', 1)
            docs = list(cursor)
            for doc in docs:
                if '_id' in doc and not isinstance(doc['_id'], (str, int, float)):
                    doc['_id'] = str(doc['_id'])
            return docs
        except Exception as e:
            logger.error(f'Failed to get all active reminders from Mongo: {e}')
            return []


# ============================================================================
# ALLIANCE DATA ADAPTERS - For storing all alliance member info
# ============================================================================

class AllianceMembersAdapter:
    """Stores alliance members with all their data (player IDs, levels, etc.)"""
    COLL = 'alliance_members'

    @staticmethod
    def upsert_member(fid: str, data: Dict[str, Any]) -> bool:
        """Insert or update a single alliance member"""
        try:
            db = _get_db_wos()
            now = datetime.utcnow().isoformat()
            
            # Ensure _id is string fid
            data_copy = data.copy()
            data_copy['updated_at'] = now
            data_copy.pop('created_at', None)
            
            db[AllianceMembersAdapter.COLL].update_one(
                {'_id': str(fid)},
                {'$set': data_copy, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to upsert alliance member {fid} in Mongo: {e}')
            return False

    @staticmethod
    async def upsert_member_async(fid: str, data: Dict[str, Any]) -> bool:
        """Insert or update a single alliance member asynchronously"""
        try:
            db = await _get_db_wos_async()
            now = datetime.utcnow().isoformat()
            
            data_copy = data.copy()
            data_copy['updated_at'] = now
            data_copy.pop('created_at', None)
            
            await db[AllianceMembersAdapter.COLL].update_one(
                {'_id': str(fid)},
                {'$set': data_copy, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to upsert alliance member (async) {fid} in Mongo: {e}')
            return False

    @staticmethod
    async def get_all_members_async() -> list:
        """Get all alliance members asynchronously"""
        try:
            db = await _get_db_wos_async()
            cursor = db[AllianceMembersAdapter.COLL].find({})
            docs = await cursor.to_list(length=None)
            for doc in docs:
                doc.pop('_id', None)
            return docs
        except Exception as e:
            logger.error(f'Failed to get all alliance members (async) from Mongo: {e}')
            return []

    @staticmethod
    def get_member(fid: str) -> Optional[Dict[str, Any]]:
        """Get a single alliance member"""
        try:
            db = _get_db_wos()
            doc = db[AllianceMembersAdapter.COLL].find_one({'_id': str(fid)})
            if doc:
                doc.pop('_id', None)  # Remove MongoDB _id
            return doc
        except Exception as e:
            logger.error(f'Failed to get alliance member {fid} from Mongo: {e}')
            return None

    @staticmethod
    async def get_member_async(fid: str) -> Optional[Dict[str, Any]]:
        """Get a single alliance member asynchronously"""
        try:
            db = await _get_db_wos_async()
            doc = await db[AllianceMembersAdapter.COLL].find_one({'_id': str(fid)})
            if doc:
                doc.pop('_id', None)
            return doc
        except Exception as e:
            logger.error(f'Failed to get alliance member (async) {fid} from Mongo: {e}')
            return None

    @staticmethod
    def get_all_members() -> list:
        """Get all alliance members"""
        try:
            db = _get_db_wos()
            docs = list(db[AllianceMembersAdapter.COLL].find({}))
            for doc in docs:
                doc.pop('_id', None)  # Remove MongoDB _id
            return docs
        except Exception as e:
            logger.error(f'Failed to get all alliance members from Mongo: {e}')
            return []

    @staticmethod
    def delete_member(fid: str) -> bool:
        """Delete a single alliance member"""
        try:
            db = _get_db_wos()
            result = db[AllianceMembersAdapter.COLL].delete_one({'_id': str(fid)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to delete alliance member {fid} from Mongo: {e}')
            return False

    @staticmethod
    def clear_all() -> bool:
        """Clear all alliance members"""
        try:
            db = _get_db_wos()
            db[AllianceMembersAdapter.COLL].delete_many({})
            logger.info('[Mongo] Cleared all alliance members')
            return True
        except Exception as e:
            logger.error(f'Failed to clear alliance members from Mongo: {e}')
            return False


class AllianceMetadataAdapter:
    """Stores alliance metadata (settings, config, etc.)"""
    COLL = 'alliance_metadata'

    @staticmethod
    def set_metadata(key: str, value: Any) -> bool:
        """Set alliance metadata"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            
            db[AllianceMetadataAdapter.COLL].update_one(
                {'_id': str(key)},
                {'$set': {'value': value, 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set alliance metadata {key}: {e}')
            return False

    @staticmethod
    def get_metadata(key: str) -> Optional[Any]:
        """Get alliance metadata"""
        try:
            db = _get_db_main()
            doc = db[AllianceMetadataAdapter.COLL].find_one({'_id': str(key)})
            return doc.get('value') if doc else None
        except Exception as e:
            logger.error(f'Failed to get alliance metadata {key}: {e}')
            return None

    @staticmethod
    async def set_metadata_async(key: str, value: Any) -> bool:
        """Set alliance metadata asynchronously"""
        try:
            db = await _get_db_main_async()
            now = datetime.utcnow().isoformat()
            await db[AllianceMetadataAdapter.COLL].update_one(
                {'_id': str(key)},
                {'$set': {'value': value, 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set alliance metadata (async) {key}: {e}')
            return False


class GiftCodesAdapter:
    """Adapter for managing gift codes in MongoDB (for gift_operationsapi cog)"""
    COLL = 'gift_codes'

    @staticmethod
    def get_all():
        """Get all gift codes as list of tuples: (code, date, validation_status)"""
        try:
            db = _get_db_wos()
            docs = db[GiftCodesAdapter.COLL].find({})
            # Filter out docs where _id is not a string (e.g. malformed ObjectId docs)
            return [
                (d.get('_id'), d.get('date'), d.get('validation_status')) 
                for d in docs 
                if isinstance(d.get('_id'), str)
            ]
        except Exception as e:
            logger.error(f'Failed to get all gift codes from Mongo: {e}')
            return []

    @staticmethod
    def insert(code: str, date: str, validation_status: str = 'pending') -> bool:
        """Insert a new gift code (ignores if already exists)"""
        try:
            db = _get_db_wos()
            db[GiftCodesAdapter.COLL].update_one(
                {'_id': code},
                {'$set': {'date': date, 'validation_status': validation_status, 'created_at': datetime.utcnow().isoformat()}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to insert gift code {code}: {e}')
            return False

    @staticmethod
    def update_status(code: str, validation_status: str) -> bool:
        """Update validation status of a gift code"""
        try:
            db = _get_db_wos()
            db[GiftCodesAdapter.COLL].update_one(
                {'_id': code},
                {'$set': {'validation_status': validation_status, 'updated_at': datetime.utcnow().isoformat()}}
            )
            return True
        except Exception as e:
            logger.error(f'Failed to update status for {code}: {e}')
            return False

    @staticmethod
    def delete(code: str) -> bool:
        """Delete a gift code"""
        try:
            db = _get_db_wos()
            result = db[GiftCodesAdapter.COLL].delete_one({'_id': code})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to delete gift code {code}: {e}')
            return False

    @staticmethod
    def clear_all() -> bool:
        """Clear all gift codes (use with caution)"""
        try:
            db = _get_db_wos()
            db[GiftCodesAdapter.COLL].delete_many({})
            return True
        except Exception as e:
            logger.error(f'Failed to clear all gift codes: {e}')
            return False

    @staticmethod
    def get_code(code: str) -> Optional[Dict[str, Any]]:
        """Get a single gift code with all its fields"""
        try:
            db = _get_db_wos()
            doc = db[GiftCodesAdapter.COLL].find_one({'_id': code})
            if doc:
                return {
                    'giftcode': doc.get('_id'),
                    'date': doc.get('date'),
                    'validation_status': doc.get('validation_status'),
                    'auto_redeem_processed': doc.get('auto_redeem_processed', False),
                    'created_at': doc.get('created_at'),
                    'updated_at': doc.get('updated_at')
                }
            return None
        except Exception as e:
            logger.error(f'Failed to get gift code {code}: {e}')
            return None

    @staticmethod
    def get_all_with_status() -> List[Dict[str, Any]]:
        """Get all gift codes with their auto_redeem_processed status"""
        try:
            db = _get_db_wos()
            docs = db[GiftCodesAdapter.COLL].find({})
            return [
                {
                    'giftcode': d.get('_id'),
                    'date': d.get('date'),
                    'validation_status': d.get('validation_status'),
                    'auto_redeem_processed': d.get('auto_redeem_processed', False),
                    'created_at': d.get('created_at'),
                    'updated_at': d.get('updated_at')
                }
                for d in docs
            ]
        except Exception as e:
            logger.error(f'Failed to get all gift codes with status: {e}')
            return []

    @staticmethod
    def mark_code_processed(code: str) -> bool:
        """Mark a gift code as processed for auto-redeem"""
        try:
            db = _get_db_wos()
            result = db[GiftCodesAdapter.COLL].update_one(
                {'_id': code},
                {
                    '$set': {
                        'auto_redeem_processed': True,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                }
            )
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            logger.error(f'Failed to mark code {code} as processed: {e}')
            return False

    @staticmethod
    async def mark_code_processed_async(code: str) -> bool:
        """Mark a gift code as processed for auto-redeem asynchronously"""
        try:
            db = await _get_db_wos_async()
            result = await db[GiftCodesAdapter.COLL].update_one(
                {'_id': code},
                {
                    '$set': {
                        'auto_redeem_processed': True,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                }
            )
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            logger.error(f'Failed to mark code (async) {code} as processed: {e}')
            return False


class AutoRedeemSettingsAdapter:
    """Adapter for managing auto redeem settings in MongoDB"""
    COLL = 'auto_redeem_settings'

    @staticmethod
    def get_settings(guild_id: int) -> Optional[Dict[str, Any]]:
        """Get auto redeem settings for a guild"""
        try:
            db = _get_db_main()
            doc = db[AutoRedeemSettingsAdapter.COLL].find_one({'_id': str(guild_id)})
            if not doc:
                return None
            return {
                'enabled': bool(doc.get('enabled', False)),
                'updated_by': int(doc.get('updated_by', 0)),
                'updated_at': doc.get('updated_at')
            }
        except Exception as e:
            logger.error(f'Failed to get auto redeem settings for guild {guild_id}: {e}')
            return None

    @staticmethod
    def set_enabled(guild_id: int, enabled: bool, updated_by: int) -> bool:
        """Set auto redeem enabled/disabled state for a guild"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AutoRedeemSettingsAdapter.COLL].update_one(
                {'_id': str(guild_id)},
                {
                    '$set': {
                        'guild_id': int(guild_id),
                        'enabled': bool(enabled),
                        'updated_by': int(updated_by),
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            logger.info(f'Set auto redeem enabled={enabled} for guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to set auto redeem settings for guild {guild_id}: {e}')
            return False

    @staticmethod
    def get_all_settings() -> List[Dict[str, Any]]:
        """Get all auto redeem settings for all guilds"""
        try:
            db = _get_db_main()
            docs = db[AutoRedeemSettingsAdapter.COLL].find({})
            return [
                {
                    'guild_id': int(d.get('guild_id', d.get('_id'))),
                    'enabled': bool(d.get('enabled', False)),
                    'updated_by': int(d.get('updated_by', 0)),
                    'updated_at': d.get('updated_at'),
                    'created_at': d.get('created_at')
                }
                for d in docs
            ]
        except Exception as e:
            logger.error(f'Failed to get all auto redeem settings: {e}')
            return []


class AutoRedeemMembersAdapter:
    """Adapter for managing auto-redeem members in MongoDB"""
    COLL = 'auto_redeem_members'

    @staticmethod
    def get_members(guild_id: int) -> List[Dict[str, Any]]:
        """Get all auto-redeem members for a guild (filters out invalid FIDs)"""
        try:
            db = _get_db_main()
            # Query with filter to exclude null/empty FIDs at database level
            docs = db[AutoRedeemMembersAdapter.COLL].find({
                'guild_id': int(guild_id),
                'fid': {'$nin': [None, '', 'None']}
            })
            return [
                {
                    'fid': d.get('fid'),
                    'nickname': d.get('nickname'),
                    'furnace_lv': int(d.get('furnace_lv', 0)),
                    'avatar_image': d.get('avatar_image', ''),
                    'added_by': int(d.get('added_by', 0)),
                    'added_at': d.get('added_at')
                }
                for d in docs
                # Additional Python-level filter as safety
                if d.get('fid') and str(d.get('fid', '')).strip() and str(d.get('fid', '')).lower() != 'none'
            ]
        except Exception as e:
            logger.error(f'Failed to get auto-redeem members for guild {guild_id}: {e}')
            return []

    @staticmethod
    def add_member(guild_id: int, fid: str, member_data: Dict[str, Any]) -> bool:
        """Add a member to auto-redeem list"""
        try:
            # Validate FID - reject null, empty, or 'None' values
            if not fid or not str(fid).strip() or str(fid).strip().lower() == 'none':
                logger.warning(f'Rejected adding member with invalid FID: {fid}')
                return False
            
            # Ensure fid is a clean string
            fid = str(fid).strip()
            
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AutoRedeemMembersAdapter.COLL].update_one(
                {'guild_id': int(guild_id), 'fid': str(fid)},
                {
                    '$set': {
                        'guild_id': int(guild_id),
                        'fid': str(fid),
                        'nickname': member_data.get('nickname', ''),
                        'furnace_lv': int(member_data.get('furnace_lv', 0)),
                        'avatar_image': member_data.get('avatar_image', ''),
                        'added_by': int(member_data.get('added_by', 0)),
                        'added_at': member_data.get('added_at', now),
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            logger.info(f'Added auto-redeem member {fid} for guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to add auto-redeem member {fid} for guild {guild_id}: {e}')
            return False

    @staticmethod
    def remove_member(guild_id: int, fid: str) -> bool:
        """Remove a member from auto-redeem list"""
        try:
            db = _get_db_main()
            result = db[AutoRedeemMembersAdapter.COLL].delete_one({
                'guild_id': int(guild_id),
                'fid': str(fid)
            })
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to remove auto-redeem member {fid} for guild {guild_id}: {e}')
            return False

    @staticmethod
    def member_exists(guild_id: int, fid: str) -> bool:
        """Check if member exists in auto-redeem list"""
        try:
            db = _get_db_main()
            doc = db[AutoRedeemMembersAdapter.COLL].find_one({
                'guild_id': int(guild_id),
                'fid': str(fid)
            })
            return doc is not None
        except Exception as e:
            logger.error(f'Failed to check if member {fid} exists for guild {guild_id}: {e}')
            return False

    @staticmethod
    def batch_member_exists(guild_id: int, fids: List[str]) -> Dict[str, bool]:
        """Batch check if multiple members exist in auto-redeem list"""
        try:
            db = _get_db_main()
            docs = db[AutoRedeemMembersAdapter.COLL].find({
                'guild_id': int(guild_id),
                'fid': {'$in': [str(fid) for fid in fids]}
            })
            existing_fids = {str(d.get('fid')) for d in docs}
            return {str(fid): str(fid) in existing_fids for fid in fids}
        except Exception as e:
            logger.error(f'Failed to batch check members for guild {guild_id}: {e}')
            return {str(fid): False for fid in fids}


class AutoRedeemChannelsAdapter:
    """Adapter for managing auto redeem channel configuration in MongoDB"""
    COLL = 'auto_redeem_channels'

    @staticmethod
    def get_channel(guild_id: int) -> Optional[Dict[str, Any]]:
        """Get auto redeem channel configuration for a guild"""
        try:
            db = _get_db_main()
            doc = db[AutoRedeemChannelsAdapter.COLL].find_one({'_id': str(guild_id)})
            if not doc:
                return None
            return {
                'channel_id': int(doc.get('channel_id')),
                'added_by': int(doc.get('added_by', 0)),
                'added_at': doc.get('added_at')
            }
        except Exception as e:
            logger.error(f'Failed to get auto redeem channel for guild {guild_id}: {e}')
            return None

    @staticmethod
    def set_channel(guild_id: int, channel_id: int, added_by: int) -> bool:
        """Set auto redeem channel for a guild"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AutoRedeemChannelsAdapter.COLL].update_one(
                {'_id': str(guild_id)},
                {
                    '$set': {
                        'guild_id': int(guild_id),
                        'channel_id': int(channel_id),
                        'added_by': int(added_by),
                        'added_at': now,
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            logger.info(f'Set auto redeem channel {channel_id} for guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to set auto redeem channel for guild {guild_id}: {e}')
            return False


class WelcomeChannelAdapter:
    """Adapter for managing welcome channel settings in MongoDB"""
    COLL = 'welcome_channels'

    @staticmethod
    def get(guild_id: int) -> Optional[Dict[str, Any]]:
        """Get welcome channel settings for a guild"""
        try:
            db = _get_db_main()
            doc = db[WelcomeChannelAdapter.COLL].find_one({'_id': str(guild_id)})
            if not doc:
                return None
            # Handle channel_id being None (e.g., when only bg_image_url was set)
            channel_id_raw = doc.get('channel_id')
            channel_id = int(channel_id_raw) if channel_id_raw is not None else None
            return {
                'channel_id': channel_id,
                'enabled': bool(doc.get('enabled', True)),
                'bg_image_url': doc.get('bg_image_url')
            }
        except Exception as e:
            logger.error(f'Failed to get welcome channel for guild {guild_id}: {e}')
            return None

    @staticmethod
    def set(guild_id: int, channel_id: int, enabled: bool = True) -> bool:
        """Set/update welcome channel for a guild"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[WelcomeChannelAdapter.COLL].update_one(
                {'_id': str(guild_id)},
                {
                    '$set': {
                        'channel_id': int(channel_id),
                        'enabled': bool(enabled),
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set welcome channel for guild {guild_id}: {e}')
            return False
    
    @staticmethod
    def set_bg_image(guild_id: int, bg_image_url: str) -> bool:
        """Set/update background image URL for a guild"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[WelcomeChannelAdapter.COLL].update_one(
                {'_id': str(guild_id)},
                {
                    '$set': {
                        'bg_image_url': str(bg_image_url),
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to set background image for guild {guild_id}: {e}')
            return False

    @staticmethod
    def delete(guild_id: int) -> bool:
        """Delete welcome channel configuration for a guild"""
        try:
            db = _get_db_main()
            result = db[WelcomeChannelAdapter.COLL].delete_one({'_id': str(guild_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to delete welcome channel for guild {guild_id}: {e}')
            return False

    @staticmethod
    def get_all() -> list:
        """Get all configured welcome channels"""
        try:
            db = _get_db_main()
            docs = list(db[WelcomeChannelAdapter.COLL].find({'enabled': True}))
            return [{
                'guild_id': int(d.get('_id')),
                'channel_id': int(d.get('channel_id')),
                'enabled': bool(d.get('enabled', True))
            } for d in docs]
        except Exception as e:
            logger.error(f'Failed to get all welcome channels: {e}')
            return []

class AdminsAdapter:
    COLL = 'admins'

    @staticmethod
    def count() -> int:
        try:
            db = _get_db_main()
            return db[AdminsAdapter.COLL].count_documents({})
        except Exception:
            return 0

    @staticmethod
    def get(user_id: int) -> Optional[Dict[str, Any]]:
        try:
            db = _get_db_main()
            d = db[AdminsAdapter.COLL].find_one({'_id': str(user_id)})
            return d
        except Exception:
            return None

    @staticmethod
    def upsert(user_id: int, is_initial: int) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AdminsAdapter.COLL].update_one(
                {'_id': str(user_id)},
                {'$set': {'is_initial': int(is_initial), 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception:
            return False

    @staticmethod
    def get_initial_admins() -> List[int]:
        try:
            db = _get_db_main()
            docs = list(db[AdminsAdapter.COLL].find({'is_initial': 1}))
            return [int(d['_id']) for d in docs]
        except Exception:
            return []

class AlliancesAdapter:
    COLL = 'alliance__alliance_list'

    @staticmethod
    def get_all() -> list:
        try:
            db = _get_db_main()
            docs = list(db[AlliancesAdapter.COLL].find({}))
            # Legacy field 'id' instead of 'alliance_id'? No, user said 'alliance_id' in schema but let's be safe
            # Debug output showed: "id": 1, "name": "S667", "discord_server_id": 1285973956424597554
            return [{'alliance_id': int(d.get('alliance_id') or d.get('id')), 'name': d.get('name'), 'discord_server_id': int(d.get('discord_server_id', 0))} for d in docs]
        except Exception:
            return []

    @staticmethod
    def find_by_name(name: str) -> Optional[Dict[str, Any]]:
        try:
            db = _get_db_main()
            d = db[AlliancesAdapter.COLL].find_one({'name': name})
            return d
        except Exception:
            return None

    @staticmethod
    def delete(alliance_id: int) -> bool:
        try:
            db = _get_db_main()
            res = db[AlliancesAdapter.COLL].delete_one({'_id': str(alliance_id)})
            return res.deleted_count > 0
        except Exception:
            return False

    @staticmethod
    async def get_all_async() -> list:
        try:
            db = await _get_db_main_async()
            cursor = db[AlliancesAdapter.COLL].find({})
            docs = await cursor.to_list(length=None)
            return [{'alliance_id': int(d.get('alliance_id') or d.get('id')), 'name': d.get('name'), 'discord_server_id': int(d.get('discord_server_id', 0))} for d in docs]
        except Exception:
            return []

    @staticmethod
    async def upsert_async(alliance_id: int, name: str, discord_server_id: int) -> bool:
        try:
            db = await _get_db_main_async()
            now = datetime.utcnow().isoformat()
            await db[AlliancesAdapter.COLL].update_one(
                {'_id': str(alliance_id)},
                {'$set': {'alliance_id': int(alliance_id), 'name': name, 'discord_server_id': int(discord_server_id), 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception:
            return False

    @staticmethod
    def delete(alliance_id: int) -> bool:
        try:
            db = _get_db_main()
            res = db[AlliancesAdapter.COLL].delete_one({'_id': str(alliance_id)})
            return res.deleted_count > 0
        except Exception:
            return False

class AllianceSettingsAdapter:
    COLL = 'alliance__alliancesettings'

    @staticmethod
    def get(alliance_id: int) -> Optional[Dict[str, Any]]:
        try:
            db = _get_db_main()
            # Query by 'alliance_id' as per schema: "alliance_id": 1
            d = db[AllianceSettingsAdapter.COLL].find_one({'alliance_id': int(alliance_id)})
            return d
        except Exception:
            return None

    @staticmethod
    def get_all() -> list:
        try:
            db = _get_db_main()
            docs = list(db[AllianceSettingsAdapter.COLL].find({}))
            # Schema: "alliance_id": 1, "channel_id": ...
            return [{'alliance_id': int(d.get('alliance_id')), 'channel_id': int(d.get('channel_id') or 0), 'interval': int(d.get('interval') or 0)} for d in docs]
        except Exception:
            return []

    @staticmethod
    def upsert(alliance_id: int, channel_id: int, interval: int, giftcodecontrol: Optional[int ] = None, giftcode_channel: Optional[int ] = None) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            payload = {'channel_id': int(channel_id), 'interval': int(interval)}
            if giftcodecontrol is not None:
                payload['giftcodecontrol'] = int(giftcodecontrol)
            if giftcode_channel is not None:
                payload['giftcode_channel'] = int(giftcode_channel)
            db[AllianceSettingsAdapter.COLL].update_one(
                {'_id': str(alliance_id)},
                {'$set': {**payload, 'updated_at': now}, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception:
            return False

    @staticmethod
    def delete(alliance_id: int) -> bool:
        try:
            db = _get_db_main()
            res = db[AllianceSettingsAdapter.COLL].delete_one({'_id': str(alliance_id)})
            return res.deleted_count > 0
        except Exception:
            return False

    @staticmethod
    def get_auto_redeem_alliances() -> List[int]:
        try:
            db = _get_db_main()
            docs = list(db[AllianceSettingsAdapter.COLL].find({'giftcodecontrol': 1}))
            return [int(d['_id']) for d in docs]
        except Exception:
            return []


class FurnaceHistoryAdapter:
    COLLECTION = 'furnace_history'

    @staticmethod
    def insert(data: Dict[str, Any]) -> bool:
        try:
            db = _get_db_wos()
            if db is None:
                return False
            
            if "change_date" not in data:
                data["change_date"] = datetime.utcnow()
                
            db[FurnaceHistoryAdapter.COLLECTION].insert_one(data)
            return True
        except Exception as e:
            logging.error(f"Error inserting furnace history: {e}")
            return False

    @staticmethod
    async def insert_async(data: Dict[str, Any]) -> bool:
        """Insert a single furnace history record asynchronously"""
        try:
            db = await _get_db_wos_async()
            if db is None:
                return False
            
            if "change_date" not in data:
                data["change_date"] = datetime.utcnow()
                
            await db[FurnaceHistoryAdapter.COLLECTION].insert_one(data)
            return True
        except Exception as e:
            logging.error(f"Error inserting furnace history (async): {e}")
            return False

    @staticmethod
    def get_recent_changes(days: int = 7, alliance_id: Optional[int] = None) -> list:
        try:
            db = _get_db_wos()
            if db is None:
                return []
            
            match_stage = {
                "change_date": {
                    "$gte": datetime.utcnow() - timedelta(days=days)
                }
            }
            
            if alliance_id is not None:
                match_stage["alliance_id"] = int(alliance_id)
            
            pipeline = [
                {
                    "$match": match_stage
                },
                {
                    "$group": {
                        "_id": "$fid",
                        "nickname": {"$first": "$nickname"},
                        "total_growth": {"$sum": {"$subtract": ["$new_level", "$old_level"]}}
                    }
                },
                {
                    "$match": {
                        "total_growth": {"$gt": 0}
                    }
                },
                {
                    "$sort": {"total_growth": -1}
                }
            ]
            
            return list(db[FurnaceHistoryAdapter.COLLECTION].aggregate(pipeline))
        except Exception as e:
            logging.error(f"Error fetching furnace history: {e}")
            return []


class AllianceMonitoringAdapter:
    COLL = 'alliance_monitoring'

    @staticmethod
    def get_all_monitors() -> list:
        try:
            db = _get_db_main()
            docs = list(db[AllianceMonitoringAdapter.COLL].find({'enabled': 1}))
            return [{
                'guild_id': int(d.get('guild_id')),
                'alliance_id': int(d.get('alliance_id')),
                'channel_id': int(d.get('channel_id')),
                'enabled': int(d.get('enabled', 1)),
                'check_interval': int(d.get('check_interval', 240))
            } for d in docs]
        except Exception as e:
            logger.error(f"Error getting alliance monitors from Mongo: {e}")
            return []

    @staticmethod
    async def get_all_monitors_async() -> list:
        try:
            db = await _get_db_main_async()
            cursor = db[AllianceMonitoringAdapter.COLL].find({'enabled': 1})
            docs = await cursor.to_list(length=None)
            return [{
                'guild_id': int(d.get('guild_id')),
                'alliance_id': int(d.get('alliance_id')),
                'channel_id': int(d.get('channel_id')),
                'enabled': int(d.get('enabled', 1)),
                'check_interval': int(d.get('check_interval', 240))
            } for d in docs]
        except Exception as e:
            logger.error(f"Error getting alliance monitors (async) from Mongo: {e}")
            return []

    @staticmethod
    def upsert_monitor(guild_id: int, alliance_id: int, channel_id: int, enabled: int = 1, check_interval: int = 240) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AllianceMonitoringAdapter.COLL].update_one(
                {'guild_id': int(guild_id), 'alliance_id': int(alliance_id)},
                {
                    '$set': {
                        'guild_id': int(guild_id),
                        'alliance_id': int(alliance_id),
                        'channel_id': int(channel_id),
                        'enabled': int(enabled),
                        'check_interval': int(check_interval),
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error upserting alliance monitor: {e}")
            return False

    @staticmethod
    def delete_monitor(guild_id: int, alliance_id: int) -> bool:
        try:
            db = _get_db_main()
            res = db[AllianceMonitoringAdapter.COLL].delete_one({'guild_id': int(guild_id), 'alliance_id': int(alliance_id)})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting alliance monitor: {e}")
            return False


class ServerAllianceAdapter:
    """Adapter for managing server-alliance assignments in MongoDB"""
    COLL = 'server_alliances'

    @staticmethod
    def set_alliance(guild_id: int, alliance_id: int, assigned_by: int) -> bool:
        """Assign an alliance to a Discord server"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            # Legacy collection uses 'id' as guild_id and 'alliances_id' as alliance_id
            db[ServerAllianceAdapter.COLL].update_one(
                {'_id': str(guild_id)},
                {
                    '$set': {
                        'id': int(guild_id),
                        'alliances_id': int(alliance_id),
                        'assigned_by': int(assigned_by),
                        'assigned_at': now,
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            logger.info(f'Assigned alliance {alliance_id} to server {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to assign alliance to server {guild_id}: {e}')
            return False

    @staticmethod
    def get_alliance(guild_id: int) -> Optional[int]:
        """Get the assigned alliance ID for a Discord server"""
        try:
            db = _get_db_main()
            # Try finding by _id first (modern) or id (legacy)
            doc = db[ServerAllianceAdapter.COLL].find_one({'_id': str(guild_id)})
            if not doc:
                doc = db[ServerAllianceAdapter.COLL].find_one({'_id': int(guild_id)})
            if not doc:
                 # Fallback for documents that might have auto-generated _id
                 doc = db[ServerAllianceAdapter.COLL].find_one({'id': str(guild_id)})
            if not doc:
                 doc = db[ServerAllianceAdapter.COLL].find_one({'id': int(guild_id)})
            
            if doc:
                # Legacy field is 'alliances_id', modern might be 'alliance_id'
                return int(doc.get('alliances_id') or doc.get('alliance_id'))
            return None
        except Exception as e:
            logger.error(f'Failed to get alliance for server {guild_id}: {e}')
            return None

    @staticmethod
    def remove_alliance(guild_id: int) -> bool:
        """Remove alliance assignment from a Discord server"""
        try:
            db = _get_db_main()
            result = db[ServerAllianceAdapter.COLL].delete_one({'_id': str(guild_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to remove alliance from server {guild_id}: {e}')
            return False

    @staticmethod
    def get_all() -> list:
        """Get all server-alliance mappings"""
        try:
            db = _get_db_main()
            docs = list(db[ServerAllianceAdapter.COLL].find({}))
            return [{
                'guild_id': int(d.get('guild_id')),
                'alliance_id': int(d.get('alliance_id')),
                'assigned_by': int(d.get('assigned_by')),
                'assigned_at': d.get('assigned_at')
            } for d in docs]
        except Exception as e:
            logger.error(f'Failed to get all server-alliance mappings: {e}')
            return []

    @staticmethod
    def set_password(guild_id: int, password: str, set_by: int) -> bool:
        """Set member list password for a Discord server"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[ServerAllianceAdapter.COLL].update_one(
                {'_id': str(guild_id)},
                {
                    '$set': {
                        'member_list_password': str(password),
                        'password_set_by': int(set_by),
                        'password_set_at': now,
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now, 'guild_id': int(guild_id)}
                },
                upsert=True
            )
            logger.info(f'Set member list password for server {guild_id}')
            
            # Invalidate all existing auth sessions when password changes
            try:
                from db.mongo_adapters import AuthSessionsAdapter
                AuthSessionsAdapter.invalidate_all_sessions(guild_id)
            except Exception as session_error:
                logger.warning(f'Failed to invalidate auth sessions for guild {guild_id}: {session_error}')
            
            return True
        except Exception as e:
            logger.error(f'Failed to set password for server {guild_id}: {e}')
            return False

    @staticmethod
    def get_password(guild_id: int) -> Optional[str]:
        """Get member list password for a Discord server"""
        try:
            db = _get_db_main()
            doc = db[ServerAllianceAdapter.COLL].find_one({'_id': str(guild_id)})
            if doc:
                return doc.get('member_list_password')
            return None
        except Exception as e:
            logger.error(f'Failed to get password for server {guild_id}: {e}')
            return None

    @staticmethod
    async def get_password_async(guild_id: int) -> Optional[str]:
        """Get member list password for a Discord server asynchronously"""
        try:
            db = await _get_db_main_async()
            doc = await db[ServerAllianceAdapter.COLL].find_one({'_id': str(guild_id)})
            if doc:
                return doc.get('member_list_password')
            return None
        except Exception as e:
            logger.error(f'Failed to get password (async) for server {guild_id}: {e}')
            return None

    @staticmethod
    def verify_password(guild_id: int, password: str) -> bool:
        """Verify member list password for a Discord server"""
        try:
            stored_password = ServerAllianceAdapter.get_password(guild_id)
            if stored_password is None:
                return False
            return str(password) == str(stored_password)
        except Exception as e:
            logger.error(f'Failed to verify password for server {guild_id}: {e}')
            return False


class AuthSessionsAdapter:
    """Adapter for managing authentication sessions for /manage command"""
    COLL = 'auth_sessions'
    SESSION_DURATION_DAYS = 7

    @staticmethod
    def create_session(guild_id: int, user_id: int, password_hash: str) -> bool:
        """Create or update an authentication session for a user"""
        try:
            db = _get_db_main()
            now = datetime.utcnow()
            expires_at = now + timedelta(days=AuthSessionsAdapter.SESSION_DURATION_DAYS)
            
            db[AuthSessionsAdapter.COLL].update_one(
                {'_id': f"{guild_id}:{user_id}"},
                {
                    '$set': {
                        'guild_id': int(guild_id),
                        'user_id': int(user_id),
                        'password_hash': str(password_hash),
                        'created_at': now.isoformat(),
                        'expires_at': expires_at.isoformat(),
                        'updated_at': now.isoformat()
                    }
                },
                upsert=True
            )
            logger.info(f'Created auth session for user {user_id} in guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to create auth session for user {user_id} in guild {guild_id}: {e}')
            return False

    @staticmethod
    def get_session(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get authentication session for a user"""
        try:
            db = _get_db_main()
            doc = db[AuthSessionsAdapter.COLL].find_one({'_id': f"{guild_id}:{user_id}"})
            if doc:
                doc.pop('_id', None)
            return doc
        except Exception as e:
            logger.error(f'Failed to get auth session for user {user_id} in guild {guild_id}: {e}')
            return None

    @staticmethod
    def is_session_valid(guild_id: int, user_id: int, current_password: str) -> bool:
        """Check if user has a valid authentication session"""
        try:
            session = AuthSessionsAdapter.get_session(guild_id, user_id)
            if not session:
                return False
            
            # Check if session has expired
            expires_at = datetime.fromisoformat(session.get('expires_at'))
            if datetime.utcnow() > expires_at:
                logger.info(f'Auth session expired for user {user_id} in guild {guild_id}')
                return False
            
            # Check if password has changed (compare with current password)
            stored_password_hash = session.get('password_hash')
            if str(current_password) != str(stored_password_hash):
                logger.info(f'Password changed, invalidating session for user {user_id} in guild {guild_id}')
                return False
            
            return True
        except Exception as e:
            logger.error(f'Failed to validate auth session for user {user_id} in guild {guild_id}: {e}')
            return False

    @staticmethod
    def invalidate_all_sessions(guild_id: int) -> bool:
        """Invalidate all authentication sessions for a guild (called when password changes)"""
        try:
            db = _get_db_main()
            result = db[AuthSessionsAdapter.COLL].delete_many({'guild_id': int(guild_id)})
            logger.info(f'Invalidated {result.deleted_count} auth sessions for guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to invalidate auth sessions for guild {guild_id}: {e}')
            return False

    @staticmethod
    def cleanup_expired_sessions() -> int:
        """Remove all expired sessions from the database"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            result = db[AuthSessionsAdapter.COLL].delete_many({
                'expires_at': {'$lt': now}
            })
            logger.info(f'Cleaned up {result.deleted_count} expired auth sessions')
            return result.deleted_count
        except Exception as e:
            logger.error(f'Failed to cleanup expired auth sessions: {e}')
            return 0


class RecordsAdapter:
    """Adapter for managing custom player records in MongoDB"""
    COLL = 'custom_records'

    @staticmethod
    def create_record(guild_id: int, record_name: str, created_by: int) -> bool:
        """Create a new custom record"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            
            # Check if record already exists
            existing = db[RecordsAdapter.COLL].find_one({
                '_id': f"{guild_id}:{record_name}"
            })
            
            if existing:
                logger.warning(f'Record {record_name} already exists for guild {guild_id}')
                return False
            
            db[RecordsAdapter.COLL].insert_one({
                '_id': f"{guild_id}:{record_name}",
                'guild_id': int(guild_id),
                'record_name': str(record_name),
                'created_by': int(created_by),
                'created_at': now,
                'updated_at': now,
                'members': []
            })
            logger.info(f'Created record {record_name} for guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to create record {record_name} for guild {guild_id}: {e}')
            return False

    @staticmethod
    def delete_record(guild_id: int, record_name: str) -> bool:
        """Delete a custom record"""
        try:
            db = _get_db_main()
            result = db[RecordsAdapter.COLL].delete_one({
                '_id': f"{guild_id}:{record_name}"
            })
            if result.deleted_count > 0:
                logger.info(f'Deleted record {record_name} from guild {guild_id}')
                return True
            return False
        except Exception as e:
            logger.error(f'Failed to delete record {record_name} from guild {guild_id}: {e}')
            return False

    @staticmethod
    def get_record(guild_id: int, record_name: str) -> Optional[dict]:
        """Get a specific record"""
        try:
            db = _get_db_main()
            doc = db[RecordsAdapter.COLL].find_one({
                '_id': f"{guild_id}:{record_name}"
            })
            return doc
        except Exception as e:
            logger.error(f'Failed to get record {record_name} for guild {guild_id}: {e}')
            return None

    @staticmethod
    def get_all_records(guild_id: int) -> list:
        """Get all records for a guild"""
        try:
            db = _get_db_main()
            docs = list(db[RecordsAdapter.COLL].find({'guild_id': int(guild_id)}))
            return [{
                'record_name': d.get('record_name'),
                'created_by': d.get('created_by'),
                'created_at': d.get('created_at'),
                'member_count': len(d.get('members', []))
            } for d in docs]
        except Exception as e:
            logger.error(f'Failed to get all records for guild {guild_id}: {e}')
            return []

    @staticmethod
    def add_member_to_record(guild_id: int, record_name: str, fid: str, member_data: dict) -> bool:
        """Add a member to a record"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            
            # Check if member already exists in record
            record = db[RecordsAdapter.COLL].find_one({
                '_id': f"{guild_id}:{record_name}"
            })
            
            if not record:
                logger.warning(f'Record {record_name} not found for guild {guild_id}')
                return False
            
            # Remove existing member if present
            members = [m for m in record.get('members', []) if m.get('fid') != str(fid)]
            
            # Add new member data
            member_entry = {
                'fid': str(fid),
                'nickname': member_data.get('nickname', 'Unknown'),
                'furnace_lv': int(member_data.get('furnace_lv', 0)),
                'avatar_image': member_data.get('avatar_image', ''),
                'added_at': now,
                'added_by': member_data.get('added_by', 0)
            }
            members.append(member_entry)
            
            # Update record
            db[RecordsAdapter.COLL].update_one(
                {'_id': f"{guild_id}:{record_name}"},
                {
                    '$set': {
                        'members': members,
                        'updated_at': now
                    }
                }
            )
            logger.info(f'Added member {fid} to record {record_name} in guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to add member {fid} to record {record_name}: {e}')
            return False

    @staticmethod
    def remove_member_from_record(guild_id: int, record_name: str, fid: str) -> bool:
        """Remove a member from a record"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            
            record = db[RecordsAdapter.COLL].find_one({
                '_id': f"{guild_id}:{record_name}"
            })
            
            if not record:
                return False
            
            # Remove member
            members = [m for m in record.get('members', []) if m.get('fid') != str(fid)]
            
            # Update record
            db[RecordsAdapter.COLL].update_one(
                {'_id': f"{guild_id}:{record_name}"},
                {
                    '$set': {
                        'members': members,
                        'updated_at': now
                    }
                }
            )
            logger.info(f'Removed member {fid} from record {record_name} in guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to remove member {fid} from record {record_name}: {e}')
            return False

    @staticmethod
    def get_record_members(guild_id: int, record_name: str) -> list:
        """Get all members in a record"""
        try:
            record = RecordsAdapter.get_record(guild_id, record_name)
            if record:
                return record.get('members', [])
            return []
        except Exception as e:
            logger.error(f'Failed to get members for record {record_name}: {e}')
            return []

    @staticmethod
    def rename_record(guild_id: int, old_name: str, new_name: str) -> bool:
        """Rename a record"""
        try:
            db = _get_db_main()
            
            # Check if new name already exists
            existing = db[RecordsAdapter.COLL].find_one({
                '_id': f"{guild_id}:{new_name}"
            })
            
            if existing:
                logger.warning(f'Record {new_name} already exists for guild {guild_id}')
                return False
            
            # Get old record
            old_record = db[RecordsAdapter.COLL].find_one({
                '_id': f"{guild_id}:{old_name}"
            })
            
            if not old_record:
                return False
            
            # Create new record with new name
            old_record['_id'] = f"{guild_id}:{new_name}"
            old_record['record_name'] = new_name
            old_record['updated_at'] = datetime.utcnow().isoformat()
            
            db[RecordsAdapter.COLL].insert_one(old_record)
            
            # Delete old record
            db[RecordsAdapter.COLL].delete_one({
                '_id': f"{guild_id}:{old_name}"
            })
            
            logger.info(f'Renamed record {old_name} to {new_name} in guild {guild_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to rename record {old_name} to {new_name}: {e}')
            return False


class GiftCodeRedemptionAdapter:
    """Adapter for tracking gift code redemptions per server"""
    COLL = 'giftcode_redemptions'
    
    @staticmethod
    def track_redemption(guild_id: int, code: str, fid: str, status: str) -> bool:
        """
        Track a gift code redemption attempt
        
        Args:
            guild_id: Discord server ID
            code: Gift code that was redeemed
            fid: Player FID
            status: Redemption status ('success' or 'failed')
        """
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            
            # Create unique document ID per guild+code
            doc_id = f"{guild_id}:{code}"
            
            # Add redemption to array and update stats
            db[GiftCodeRedemptionAdapter.COLL].update_one(
                {'_id': doc_id},
                {
                    '$push': {
                        'redemptions': {
                            'fid': str(fid),
                            'redeemed_at': now,
                            'status': status
                        }
                    },
                    '$inc': {
                        f'stats.{status}': 1,
                        'stats.total_attempts': 1
                    },
                    '$set': {
                        'guild_id': int(guild_id),
                        'code': str(code),
                        'last_redeemed_at': now,
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to track redemption for {code} in guild {guild_id}: {e}')
            return False
    
    @staticmethod
    def get_code_stats(guild_id: int, code: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific code in a server
        
        Returns:
            {
                'total_attempts': int,
                'success': int,
                'failed': int,
                'unique_users': int,
                'last_redeemed_at': str
            }
        """
        try:
            db = _get_db_main()
            doc_id = f"{guild_id}:{code}"
            doc = db[GiftCodeRedemptionAdapter.COLL].find_one({'_id': doc_id})
            
            if not doc:
                return None
            
            # Count unique users
            redemptions = doc.get('redemptions', [])
            unique_fids = set(r['fid'] for r in redemptions if r.get('status') == 'success')
            
            stats = doc.get('stats', {})
            return {
                'total_attempts': stats.get('total_attempts', 0),
                'success': stats.get('success', 0),
                'failed': stats.get('failed', 0),
                'unique_users': len(unique_fids),
                'last_redeemed_at': doc.get('last_redeemed_at')
            }
        except Exception as e:
            logger.error(f'Failed to get stats for {code} in guild {guild_id}: {e}')
            return None
    
    @staticmethod
    def get_all_stats(guild_id: int) -> list:
        """
        Get statistics for all codes in a server
        
        Returns list of:
            {
                'code': str,
                'total_attempts': int,
                'success': int,
                'failed': int,
                'unique_users': int,
                'last_redeemed_at': str
            }
        """
        try:
            db = _get_db_main()
            docs = list(db[GiftCodeRedemptionAdapter.COLL].find({'guild_id': int(guild_id)}))
            
            results = []
            for doc in docs:
                redemptions = doc.get('redemptions', [])
                unique_fids = set(r['fid'] for r in redemptions if r.get('status') == 'success')
                stats = doc.get('stats', {})
                
                results.append({
                    'code': doc.get('code'),
                    'total_attempts': stats.get('total_attempts', 0),
                    'success': stats.get('success', 0),
                    'failed': stats.get('failed', 0),
                    'unique_users': len(unique_fids),
                    'last_redeemed_at': doc.get('last_redeemed_at')
                })
            
            # Sort by most used
            results.sort(key=lambda x: x['unique_users'], reverse=True)
            return results
        except Exception as e:
            logger.error(f'Failed to get all stats for guild {guild_id}: {e}')
            return []
    
    @staticmethod
    def get_top_codes(guild_id: int, limit: int = 10) -> list:
        """Get most-used gift codes in a server"""
        try:
            all_stats = GiftCodeRedemptionAdapter.get_all_stats(guild_id)
            return all_stats[:limit]
        except Exception as e:
            logger.error(f'Failed to get top codes for guild {guild_id}: {e}')
            return []

class PersistentViewsAdapter:
    """Adapter for managing persistent views in MongoDB"""
    COLL = 'persistent_views'

    @staticmethod
    def register_view(guild_id: int, channel_id: int, message_id: int, view_type: str, metadata: Dict[str, Any] = None) -> bool:
        """Register a persistent view to be restored on startup"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            if metadata is None:
                metadata = {}
                
            data = {
                'guild_id': int(guild_id),
                'channel_id': int(channel_id),
                'message_id': int(message_id),
                'view_type': view_type,
                'metadata': metadata,
                'updated_at': now
            }
            
            # Use message_id as the document ID
            db[PersistentViewsAdapter.COLL].update_one(
                {'_id': str(message_id)},
                {'$set': data, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to register persistent view {message_id}: {e}')
            return False

    @staticmethod
    def get_all_views() -> list:
        """Get all registered persistent views"""
        try:
            db = _get_db_main()
            docs = list(db[PersistentViewsAdapter.COLL].find({}))
            return docs
        except Exception as e:
            logger.error(f'Failed to get all persistent views: {e}')
            return []

    @staticmethod
    def remove_view(message_id: int) -> bool:
        """Remove a persistent view (e.g. if message is deleted)"""
        try:
            db = _get_db_main()
            result = db[PersistentViewsAdapter.COLL].delete_one({'_id': str(message_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f'Failed to remove persistent view {message_id}: {e}')
            return False

    @staticmethod
    def view_exists(message_id: int) -> bool:
        """Check if a persistent view exists"""
        try:
            db = _get_db_main()
            count = db[PersistentViewsAdapter.COLL].count_documents({'_id': str(message_id)})
            return count > 0
        except Exception as e:
            logger.error(f'Failed to check view existence {message_id}: {e}')
            return False



class AutoRedeemedCodesAdapter:
    COLL = 'auto_redeemed_codes'
    
    @staticmethod
    def mark_code_redeemed_for_member(guild_id: int, code: str, fid: str, status: str) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AutoRedeemedCodesAdapter.COLL].update_one(
                {'guild_id': int(guild_id), 'code': code, 'fid': str(fid)},
                {
                    '$set': {
                        'status': status,
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f'Failed to mark code {code} redeemed for {fid}: {e}')
            return False

    @staticmethod
    def is_redeemed(guild_id: int, code: str, fid: str) -> bool:
        try:
            db = _get_db_main()
            return db[AutoRedeemedCodesAdapter.COLL].count_documents({'guild_id': int(guild_id), 'code': code, 'fid': str(fid)}) > 0
        except Exception:
            return False

    @staticmethod
    def batch_check_members(guild_id: int, giftcode: str, fids: List[str]) -> Dict[str, bool]:
        """Batch check if multiple members have redeemed a code"""
        try:
            db = _get_db_main()
            # Find all redemptions for this code and these FIDs
            docs = db[AutoRedeemedCodesAdapter.COLL].find({
                'guild_id': int(guild_id),
                'code': giftcode,
                'fid': {'$in': [str(fid) for fid in fids]}
            })
            
            redeemed_fids = {d.get('fid') for d in docs}
            return {str(fid): str(fid) in redeemed_fids for fid in fids}
        except Exception as e:
            logger.error(f'Failed to batch check redemptions for {giftcode}: {e}')
            return {str(fid): False for fid in fids}


# Alias for backward compatibility
PlayerTimezonesAdapter = UserTimezonesAdapter


class AutoTranslateAdapter:
    """Adapter for managing auto-translate configurations in MongoDB"""
    COLL = 'auto_translate_configs'

    @staticmethod
    def create_config(guild_id: int, data: Dict[str, Any]) -> Optional[str]:
        """Create a new auto-translate configuration"""
        try:
            db = _get_db_main()
            config_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            
            doc = data.copy()
            doc['_id'] = config_id
            doc['config_id'] = config_id
            doc['guild_id'] = int(guild_id)
            doc['enabled'] = True
            doc['created_at'] = now
            doc['updated_at'] = now
            
            db[AutoTranslateAdapter.COLL].insert_one(doc)
            logger.info(f"Created auto-translate config {config_id} for guild {guild_id}")
            return config_id
        except Exception as e:
            logger.error(f"Failed to create auto-translate config: {e}")
            return None

    @staticmethod
    def get_config(config_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific configuration by ID"""
        try:
            db = _get_db_main()
            doc = db[AutoTranslateAdapter.COLL].find_one({'_id': config_id})
            if doc:
                doc['config_id'] = str(doc['_id'])
                doc.pop('_id', None)
            return doc
        except Exception as e:
            logger.error(f"Failed to get auto-translate config {config_id}: {e}")
            return None

    @staticmethod
    def get_guild_configs(guild_id: int) -> List[Dict[str, Any]]:
        """Get all configurations for a guild"""
        try:
            db = _get_db_main()
            docs = list(db[AutoTranslateAdapter.COLL].find({'guild_id': int(guild_id)}))
            for doc in docs:
                doc['config_id'] = str(doc['_id'])
                doc.pop('_id', None)
            return docs
        except Exception as e:
            logger.error(f"Failed to get auto-translate configs for guild {guild_id}: {e}")
            return []

    @staticmethod
    def get_configs_for_channel(channel_id: int) -> List[Dict[str, Any]]:
        """Get all enabled configurations where channel_id is the source"""
        try:
            db = _get_db_main()
            # Find configs where source_channel_id matches and enabled is True
            docs = list(db[AutoTranslateAdapter.COLL].find({
                'source_channel_id': int(channel_id),
                'enabled': True
            }))
            for doc in docs:
                doc['config_id'] = str(doc['_id'])
                doc.pop('_id', None)
            return docs
        except Exception as e:
            logger.error(f"Failed to get auto-translate configs for channel {channel_id}: {e}")
            return []

    @staticmethod
    def update_config(config_id: str, data: Dict[str, Any]) -> bool:
        """Update a configuration"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            
            update_data = data.copy()
            update_data['updated_at'] = now
            # Remove immutable fields if present
            update_data.pop('config_id', None)
            update_data.pop('guild_id', None)
            update_data.pop('_id', None)
            update_data.pop('created_at', None)
            
            result = db[AutoTranslateAdapter.COLL].update_one(
                {'_id': config_id},
                {'$set': update_data}
            )
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            logger.error(f"Failed to update auto-translate config {config_id}: {e}")
            return False

    @staticmethod
    def delete_config(config_id: str) -> bool:
        """Delete a configuration"""
        try:
            db = _get_db_main()
            result = db[AutoTranslateAdapter.COLL].delete_one({'_id': config_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete auto-translate config {config_id}: {e}")
            return False

    @staticmethod
    def toggle_config(config_id: str, enabled: bool) -> bool:
        """Enable or disable a configuration"""
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            result = db[AutoTranslateAdapter.COLL].update_one(
                {'_id': config_id},
                {'$set': {'enabled': enabled, 'updated_at': now}}
            )
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            logger.error(f"Failed to toggle auto-translate config {config_id}: {e}")
            return False


class AlliancesAdapter:
    COLL = 'alliances'

    @staticmethod
    def get_all() -> list:
        try:
            db = _get_db_main()
            return list(db[AlliancesAdapter.COLL].find({}))
        except Exception as e:
            logger.error(f"Failed to get all alliances: {e}")
            return []

    @staticmethod
    async def get_all_async() -> list:
        try:
            db = await _get_db_main_async()
            return await db[AlliancesAdapter.COLL].find({}).to_list(length=None)
        except Exception as e:
            logger.error(f"Failed to get async alliances: {e}")
            return []

    @staticmethod
    def get(alliance_id: int) -> Optional[dict]:
        try:
            db = _get_db_main()
            return db[AlliancesAdapter.COLL].find_one({'alliance_id': int(alliance_id)})
        except Exception as e:
            logger.error(f"Failed to get alliance {alliance_id}: {e}")
            return None


class AllianceSettingsAdapter:
    COLL = 'alliance_settings'

    @staticmethod
    def get(alliance_id: int) -> Optional[dict]:
        try:
            db = _get_db_main()
            return db[AllianceSettingsAdapter.COLL].find_one({'alliance_id': int(alliance_id)})
        except Exception as e:
            logger.error(f"Failed to get alliance settings {alliance_id}: {e}")
            return None


class AllianceMembersAdapter:
    COLL = 'alliance_members'

    @staticmethod
    def get_all_members() -> list:
        try:
            db = _get_db_main()
            return list(db[AllianceMembersAdapter.COLL].find({}))
        except Exception as e:
            logger.error(f"Failed to get all members: {e}")
            return []

    @staticmethod
    async def get_all_members_async() -> list:
        try:
            db = await _get_db_main_async()
            return await db[AllianceMembersAdapter.COLL].find({}).to_list(length=None)
        except Exception as e:
            logger.error(f"Failed to get async members: {e}")
            return []

    @staticmethod
    def get_member(fid: str) -> Optional[dict]:
        try:
            db = _get_db_main()
            return db[AllianceMembersAdapter.COLL].find_one({'fid': str(fid)})
        except Exception as e:
            logger.error(f"Failed to get member {fid}: {e}")
            return None

    @staticmethod
    async def get_member_async(fid: str) -> Optional[dict]:
        try:
            db = await _get_db_main_async()
            return await db[AllianceMembersAdapter.COLL].find_one({'fid': str(fid)})
        except Exception as e:
            logger.error(f"Failed to get async member {fid}: {e}")
            return None

    @staticmethod
    def upsert_member(fid: str, data: dict) -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            update_data = data.copy()
            update_data['updated_at'] = now
            db[AllianceMembersAdapter.COLL].update_one(
                {'fid': str(fid)},
                {'$set': update_data, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upsert member {fid}: {e}")
            return False

    @staticmethod
    async def upsert_member_async(fid: str, data: dict) -> bool:
        try:
            db = await _get_db_main_async()
            now = datetime.utcnow().isoformat()
            update_data = data.copy()
            update_data['updated_at'] = now
            await db[AllianceMembersAdapter.COLL].update_one(
                {'fid': str(fid)},
                {'$set': update_data, '$setOnInsert': {'created_at': now}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to async upsert member {fid}: {e}")
            return False


class AllianceMonitoringAdapter:
    COLL = 'alliance_monitoring'

    @staticmethod
    def get_all_monitors() -> list:
        try:
            db = _get_db_main()
            return list(db[AllianceMonitoringAdapter.COLL].find({}))
        except Exception as e:
            logger.error(f"Failed to get all monitors: {e}")
            return []

    @staticmethod
    async def get_all_monitors_async() -> list:
        try:
            db = await _get_db_main_async()
            return await db[AllianceMonitoringAdapter.COLL].find({}).to_list(length=None)
        except Exception as e:
            logger.error(f"Failed to get async monitors: {e}")
            return []


class FurnaceHistoryAdapter:
    COLL = 'furnace_history'

    @staticmethod
    def insert(data: dict) -> bool:
        try:
            db = _get_db_main()
            data['created_at'] = datetime.utcnow().isoformat()
            db[FurnaceHistoryAdapter.COLL].insert_one(data)
            return True
        except Exception as e:
            logger.error(f"Failed to insert furnace history: {e}")
            return False

    @staticmethod
    async def insert_async(data: dict) -> bool:
        try:
            db = await _get_db_main_async()
            data['created_at'] = datetime.utcnow().isoformat()
            await db[FurnaceHistoryAdapter.COLL].insert_one(data)
            return True
        except Exception as e:
            logger.error(f"Failed to async insert furnace history: {e}")
            return False


class AutoRedeemMembersAdapter:
    COLL = 'auto_redeem_members'

    @staticmethod
    def get_members(guild_id: int) -> list:
        try:
            db = _get_db_main()
            return list(db[AutoRedeemMembersAdapter.COLL].find({'guild_id': int(guild_id)}))
        except Exception as e:
            logger.error(f"Failed to get auto redeem members for guild {guild_id}: {e}")
            return []

    @staticmethod
    def member_exists(guild_id: int, fid: str) -> bool:
        try:
            db = _get_db_main()
            return db[AutoRedeemMembersAdapter.COLL].count_documents({'guild_id': int(guild_id), 'fid': str(fid)}) > 0
        except Exception as e:
            return False

    @staticmethod
    def add_member(guild_id: int, fid: str, nickname: str = "", furnace_lv: int = 0, avatar: str = "") -> bool:
        try:
            db = _get_db_main()
            now = datetime.utcnow().isoformat()
            db[AutoRedeemMembersAdapter.COLL].update_one(
                {'guild_id': int(guild_id), 'fid': str(fid)},
                {
                    '$set': {
                        'nickname': str(nickname),
                        'furnace_lv': int(furnace_lv),
                        'avatar_image': str(avatar),
                        'updated_at': now
                    },
                    '$setOnInsert': {'created_at': now}
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add auto redeem member {fid}: {e}")
            return False

    @staticmethod
    def remove_member(guild_id: int, fid: str) -> bool:
        try:
            db = _get_db_main()
            res = db[AutoRedeemMembersAdapter.COLL].delete_one({'guild_id': int(guild_id), 'fid': str(fid)})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to remove auto redeem member {fid}: {e}")
            return False

    @staticmethod
    def clear_all(guild_id: int) -> bool:
        try:
            db = _get_db_main()
            res = db[AutoRedeemMembersAdapter.COLL].delete_many({'guild_id': int(guild_id)})
            return True
        except Exception as e:
            logger.error(f"Failed to clear auto redeem members for {guild_id}: {e}")
            return False
